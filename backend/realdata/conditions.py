"""The single authoritative edge-cost engine.

Before Phase 5, congestion was one number written in two different places
(`main.update_traffic` and `experiments.runner`), each recomputing
`current_travel_time` by hand. This module replaces all of that. It is the
only code in the backend allowed to write `Edge.traffic_multiplier`,
`Edge.weather_multiplier`, `Edge.incident_multiplier`, `Edge.traffic_factor`
or `Edge.current_travel_time`.

The pipeline
------------
    base_travel_time            free flow, from OSM geometry + speed, or from
                                the synthetic generator. Never modified.
        x traffic_multiplier    simulated congestion (realdata.traffic_model)
        x weather_multiplier    from an observed condition (realdata.weather),
                                through the documented table below
        x incident_multiplier   operator-injected disruption on one road
        = current_travel_time   the Dijkstra edge weight the optimizers use

`traffic_factor` holds the product of the three, under its original name, so
the route-matrix cache key, the objective function's congestion term and the
map all keep reading the field they always read.

    current_travel_time = base_travel_time * traffic_factor
    traffic_factor      = traffic_m * weather_m * incident_m

Both invariants are enforced in exactly one function, `recompute_edge_cost`,
and are covered by tests.

What flows where
----------------
The optimizers are not touched. They consume the scenario's edge costs through
the route matrix, exactly as they did in Phase 1-4; changing a condition
changes `current_travel_time`, which changes the route-matrix cache key, which
forces a rebuild, which is what the optimizers then search over.

Real vs simulated
-----------------
    REAL       road network, geometry, topology, speed limits (OpenStreetMap);
               geocoding (Nominatim); the weather observation itself
               (Open-Meteo) when `weather.source` is network/cache/cache-stale.
    SIMULATED  the congestion level and its per-road distribution; incident
               severity; and the weather-impact multipliers in this module.

The weather *observation* is real. Turning "it is raining" into "travel takes
10% longer" is an assumption, and it is made here, once, in the open.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from models import ConditionSummary, Edge, ProblemScenario, WeatherState, clone_scenario

from .traffic_model import (
    DEFAULT_TRAFFIC_PROVIDER,
    LEVEL_MULTIPLIERS,
    MODE_HEAVY,
    MODE_MODERATE,
    MODE_NORMAL,
    MODE_SEVERE,
    TRAFFIC_SOURCE_SIMULATED,
    TrafficConditions,
    TrafficProvider,
    TrafficProviderError,
    get_traffic_provider,
    normalize_mode,
)
from .weather import (
    CONDITION_CLEAR,
    CONDITION_CLOUDY,
    CONDITION_DRIZZLE,
    CONDITION_FOG,
    CONDITION_FREEZING,
    CONDITION_HEAVY_RAIN,
    CONDITION_RAIN,
    CONDITION_SNOW,
    CONDITION_THUNDERSTORM,
    CONDITION_UNKNOWN,
    DEFAULT_WEATHER_PROVIDER,
    SOURCE_FALLBACK,
    WeatherObservation,
    WeatherProvider,
)

# ---------------------------------------------------------------- constants

# MODEL PARAMETERS - assumed travel-time impact of each weather condition.
#
# These are calibration assumptions for a prototype. They are broadly in line
# with the direction and rough magnitude reported in road-weather literature
# (precipitation and reduced visibility lower free-flow speed and capacity),
# but they are NOT taken from a specific calibrated study and must not be
# presented as measured effects. They are deliberately conservative: the
# largest is 1.35, so weather never dominates the objective.
#
# Unknown is 1.0 by design. When no observation is available, no weather
# effect is applied - the system does not guess.
WEATHER_IMPACT: Dict[str, float] = {
    CONDITION_CLEAR: 1.00,
    CONDITION_CLOUDY: 1.00,
    CONDITION_FOG: 1.15,
    CONDITION_DRIZZLE: 1.05,
    CONDITION_RAIN: 1.10,
    CONDITION_HEAVY_RAIN: 1.25,
    CONDITION_FREEZING: 1.30,
    CONDITION_SNOW: 1.35,
    CONDITION_THUNDERSTORM: 1.30,
    CONDITION_UNKNOWN: 1.00,
}

# MODEL PARAMETER - default severity when an incident is injected without an
# explicit factor. This is the "incident = 4.0" level from the Phase 5 brief,
# sitting on the incident axis where it belongs.
DEFAULT_INCIDENT_MULTIPLIER = 4.0

# No incident, i.e. the road is back to whatever traffic and weather say.
NO_INCIDENT = 1.0

# The congestion bands a road is reported in.
#
# These are presentation thresholds over the effective multiplier, not a second
# cost model: nothing here feeds routing, and changing a threshold cannot
# change a route. They exist so the map colours a road from a state the backend
# declared, instead of from numeric cutoffs written out again in React where
# they would silently drift from the traffic model's own levels.
#
# The thresholds are NOT free parameters - they are the documented level
# multipliers themselves (realdata.traffic_model.LEVEL_MULTIPLIERS). A road is
# reported at level X exactly when its effective multiplier has reached the
# multiplier that level denotes. That definition is worth stating because it is
# what makes the picture informative: the traffic model modulates the
# network-wide level per road by class susceptibility, so at `heavy` a
# residential street sits around 2.1x while a motorway sits around 2.7x. Bands
# pinned to the level table put those on opposite sides of the 2.5 boundary and
# the map shows the variation that is genuinely there. Bands chosen
# independently of the table straddled it and painted the whole network one
# colour, hiding a spread that does change routes.
#
# `light` is the one threshold with no level of its own: it means "measurably
# above free flow", and 1.05 is where that is called.
#
# Ordered high to low; the first band whose threshold is met wins.
LIGHT_CONGESTION_THRESHOLD = 1.05

CONGESTION_BANDS: Tuple[Tuple[str, float], ...] = (
    ("severe", LEVEL_MULTIPLIERS[MODE_SEVERE]),
    ("heavy", LEVEL_MULTIPLIERS[MODE_HEAVY]),
    ("moderate", LEVEL_MULTIPLIERS[MODE_MODERATE]),
    ("light", LIGHT_CONGESTION_THRESHOLD),
    ("free_flow", 0.0),
)

CONGESTION_LEVELS: Tuple[str, ...] = tuple(name for name, _ in CONGESTION_BANDS)


def classify_congestion(traffic_factor: float) -> str:
    """The band an effective multiplier falls into. Display only."""
    value = float(traffic_factor)
    for name, threshold in CONGESTION_BANDS:
        if value >= threshold:
            return name
    return "free_flow"


# Multipliers are stored rounded so that two runs that computed the same value
# by different float paths still produce byte-identical scenarios, which is
# what keeps the content-addressed route-matrix cache hitting.
MULTIPLIER_PRECISION = 6
TRAVEL_TIME_PRECISION = 5


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------ the one write

def recompute_edge_cost(edge: Edge) -> Edge:
    """Composes an edge's three multipliers into its effective cost.

    The ONLY place `traffic_factor` and `current_travel_time` are derived.
    Mutates and returns the edge.
    """
    effective = (
        float(edge.traffic_multiplier)
        * float(edge.weather_multiplier)
        * float(edge.incident_multiplier)
    )
    edge.traffic_factor = round(effective, MULTIPLIER_PRECISION)
    edge.current_travel_time = round(
        float(edge.base_travel_time) * effective, TRAVEL_TIME_PRECISION
    )
    # Derived alongside the cost, never separately, so the state the UI paints
    # always describes the multiplier the optimizer actually routed against.
    edge.congestion_level = classify_congestion(edge.traffic_factor)
    edge.has_incident = float(edge.incident_multiplier) != NO_INCIDENT
    return edge


def recompute_scenario_costs(scenario: ProblemScenario) -> ProblemScenario:
    """Re-derives every edge cost from its multipliers. Mutates in place."""
    for edge in scenario.edges:
        recompute_edge_cost(edge)
    return scenario


# -------------------------------------------------------------- the inputs

def weather_multiplier_for(observation: Optional[WeatherObservation]) -> float:
    """Observed condition -> travel-time multiplier, via WEATHER_IMPACT.

    No observation, or a fallback observation, means exactly 1.0: the absence
    of weather data is never dressed up as fair weather, it simply has no
    effect on cost and is reported as a fallback.
    """
    if observation is None or observation.fallback_used:
        return 1.0
    return WEATHER_IMPACT.get(observation.condition, 1.0)


def scenario_center(scenario: ProblemScenario) -> Tuple[float, float]:
    """The coordinate weather is fetched for: the depot when there is one,
    otherwise the mean of the node coordinates.

    Depot-first keeps the lookup tied to a real place in the scenario, and
    works identically for synthetic and OpenStreetMap networks. No city is
    special-cased anywhere.
    """
    if not scenario.nodes:
        raise ValueError("Cannot locate a scenario with no nodes.")

    for node in scenario.nodes:
        if node.id == scenario.depot_node_id:
            return float(node.lat), float(node.lng)

    lat = sum(float(n.lat) for n in scenario.nodes) / len(scenario.nodes)
    lng = sum(float(n.lng) for n in scenario.nodes) / len(scenario.nodes)
    return lat, lng


def count_incident_edges(scenario: ProblemScenario) -> int:
    """How many directed edges currently carry an incident."""
    return sum(1 for e in scenario.edges if e.incident_multiplier != NO_INCIDENT)


# ---------------------------------------------------------------- signature

def condition_signature(
    traffic: TrafficConditions,
    weather_multiplier: float,
    weather_condition: str,
    weather_source: Optional[str],
    incidents: Iterable[Tuple[int, int, float]],
) -> str:
    """Deterministic fingerprint of an applied condition state.

    Used for display and for the "did the conditions actually change?" check.
    It is NOT what protects the route-matrix cache - that is keyed on the edge
    costs themselves (see route_cache.py), which is strictly stronger, because
    it stays correct even if a caller writes multipliers without going through
    this module.
    """
    parts: List[str] = [
        "c1",
        f"traffic:{traffic.mode}:{traffic.source}:{traffic.provider}",
        f"weather:{weather_source or 'off'}:{weather_condition}:{weather_multiplier:.6f}",
    ]
    incident_rows = sorted(f"{u}>{v}:{m:.6f}" for u, v, m in incidents)
    parts.append("incidents:" + ";".join(incident_rows))
    blob = "|".join(parts)
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=8).hexdigest()


def _weather_state(
    observation: Optional[WeatherObservation],
    multiplier: float,
) -> Optional[WeatherState]:
    if observation is None:
        return None
    payload = observation.to_dict()
    payload["multiplier"] = round(multiplier, MULTIPLIER_PRECISION)
    return WeatherState(**payload)


def _summary(
    scenario: ProblemScenario,
    traffic: TrafficConditions,
    observation: Optional[WeatherObservation],
    weather_enabled: bool,
    use_bpr: bool,
) -> ConditionSummary:
    weather_m = weather_multiplier_for(observation) if weather_enabled else 1.0
    incidents = [
        (e.source, e.destination, e.incident_multiplier)
        for e in scenario.edges
        if e.incident_multiplier != NO_INCIDENT
    ]
    condition = observation.condition if observation is not None else CONDITION_UNKNOWN
    source = observation.source if observation is not None else None
    fallback = bool(traffic.fallback_used or (observation is not None and observation.fallback_used))

    return ConditionSummary(
        traffic_mode=traffic.mode,
        traffic_source=traffic.source,
        traffic_provider=traffic.provider,
        traffic_is_simulated=traffic.is_simulated,
        traffic_formulation="bpr" if use_bpr else "level-table",
        weather_enabled=weather_enabled,
        weather_source=source,
        weather_condition=condition if weather_enabled else None,
        weather_multiplier=round(weather_m, MULTIPLIER_PRECISION),
        weather=_weather_state(observation, weather_m),
        incident_edge_count=len(incidents),
        updated_at=_utc_now_iso(),
        fallback_used=fallback,
        signature=condition_signature(traffic, weather_m, condition, source, incidents),
    )


# ------------------------------------------------------------------ engine

@dataclass(frozen=True)
class ConditionRequest:
    """What the caller wants applied. Incidents are not listed here: they are
    per-edge state that survives traffic and weather changes, and are set
    through `apply_incidents`."""
    traffic_mode: str = MODE_NORMAL
    traffic_source: str = TRAFFIC_SOURCE_SIMULATED
    weather_enabled: bool = False
    use_bpr: bool = False


def _resolve_traffic_provider(request: ConditionRequest) -> TrafficProvider:
    """Picks the provider for a request. The shared simulated instance is
    reused for the common case; a BPR run needs its own, since the
    formulation is per-instance state."""
    if request.traffic_source == TRAFFIC_SOURCE_SIMULATED and request.use_bpr:
        from .traffic_model import SimulatedTrafficProvider
        return SimulatedTrafficProvider(use_bpr=True)
    return get_traffic_provider(request.traffic_source)


def apply_conditions(
    scenario: ProblemScenario,
    request: Optional[ConditionRequest] = None,
    *,
    traffic_provider: Optional[TrafficProvider] = None,
    weather_provider: Optional[WeatherProvider] = None,
    weather_observation: Optional[WeatherObservation] = None,
) -> ProblemScenario:
    """Applies traffic and weather to a copy of `scenario`, and returns it.

    The input scenario is never mutated - a deep copy is conditioned and
    handed back, matching how the scenario store expects to be updated.

    Existing incident multipliers are preserved: raising the traffic level or
    turning weather on must not quietly clear a road closure the operator set.

    Weather is fetched at the scenario's own coordinate. A weather failure is
    not an error - the provider returns a fallback observation, the multiplier
    stays 1.0, and `conditions.fallback_used` records it.
    """
    request = request or ConditionRequest()
    conditioned = clone_scenario(scenario)

    # --- traffic -------------------------------------------------------
    if traffic_provider is None:
        traffic_provider = _resolve_traffic_provider(request)

    mode = normalize_mode(request.traffic_mode)
    traffic = traffic_provider.get_traffic(conditioned, mode)

    # --- weather -------------------------------------------------------
    observation: Optional[WeatherObservation] = None
    if request.weather_enabled:
        if weather_observation is not None:
            observation = weather_observation
        else:
            lat, lng = scenario_center(conditioned)
            provider = weather_provider or DEFAULT_WEATHER_PROVIDER
            observation = provider.get_weather(lat, lng)
    weather_m = weather_multiplier_for(observation) if request.weather_enabled else 1.0

    # --- compose -------------------------------------------------------
    for edge in conditioned.edges:
        edge.traffic_multiplier = round(
            traffic.multiplier_for(edge.source, edge.destination), MULTIPLIER_PRECISION
        )
        edge.weather_multiplier = round(weather_m, MULTIPLIER_PRECISION)
        recompute_edge_cost(edge)

    conditioned.conditions = _summary(
        conditioned, traffic, observation, request.weather_enabled, request.use_bpr
    )
    return conditioned


def apply_incidents(
    scenario: ProblemScenario,
    updates: Dict[Tuple[int, int], float],
    *,
    symmetric: bool = True,
) -> Tuple[ProblemScenario, int]:
    """Sets incident multipliers on specific edges. Returns (scenario, count).

    `symmetric=True` mirrors each update onto the reverse direction, which is
    what a real road closure means and what the endpoint has always done.

    A multiplier of 1.0 clears the incident on that edge, leaving traffic and
    weather untouched - which is exactly why the three axes are stored
    separately rather than collapsed into one number.
    """
    conditioned = clone_scenario(scenario)

    lookup: Dict[Tuple[int, int], float] = {}
    for (u, v), factor in updates.items():
        lookup[(u, v)] = float(factor)
        if symmetric:
            lookup.setdefault((v, u), float(factor))

    changed = 0
    for edge in conditioned.edges:
        factor = lookup.get((edge.source, edge.destination))
        if factor is None:
            continue
        edge.incident_multiplier = round(factor, MULTIPLIER_PRECISION)
        recompute_edge_cost(edge)
        changed += 1

    if conditioned.conditions is not None:
        summary = conditioned.conditions.model_copy(deep=True)
        summary.incident_edge_count = count_incident_edges(conditioned)
        summary.updated_at = _utc_now_iso()
        conditioned.conditions = summary

    return conditioned, changed


def clear_conditions(scenario: ProblemScenario) -> ProblemScenario:
    """Returns a copy back at free flow: all three multipliers 1.0.

    Used by tests and by an explicit reset; nothing calls it implicitly.
    """
    conditioned = clone_scenario(scenario)
    for edge in conditioned.edges:
        edge.traffic_multiplier = 1.0
        edge.weather_multiplier = 1.0
        edge.incident_multiplier = 1.0
        recompute_edge_cost(edge)
    conditioned.conditions = None
    return conditioned


__all__ = [
    "CONGESTION_BANDS",
    "CONGESTION_LEVELS",
    "WEATHER_IMPACT",
    "DEFAULT_INCIDENT_MULTIPLIER",
    "NO_INCIDENT",
    "ConditionRequest",
    "classify_congestion",
    "apply_conditions",
    "apply_incidents",
    "clear_conditions",
    "condition_signature",
    "count_incident_edges",
    "recompute_edge_cost",
    "recompute_scenario_costs",
    "scenario_center",
    "weather_multiplier_for",
]
