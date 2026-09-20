"""Simulated congestion, and the provider seam for a future real traffic feed.

THIS IS A SIMULATION
--------------------
Every number in this module is a MODEL PARAMETER - a calibration assumption
chosen so the prototype behaves plausibly - not a traffic measurement.
OpenStreetMap supplies road geometry, topology and speed limits; it carries no
traffic data whatsoever, and no free traffic feed is wired up. Anything this
module produces must be labelled "Simulated Traffic" or "Traffic Model" in the
UI and in any report. It must never be called live traffic.

Two modes, per the Phase 5 contract
-----------------------------------
    simulated  - SimulatedTrafficProvider, below. Fully functional.
    external   - ExternalTrafficProvider, below. A deliberate placeholder that
                 refuses to run rather than fabricating numbers. The seam
                 exists so a real provider can be dropped in without touching
                 the optimizers, the cost engine or the API.

The documented level table
--------------------------
    normal    = 1.0     free-flowing
    moderate  = 1.5     busy but moving
    heavy     = 2.5     congested peak-hour conditions
    severe    = 4.0     near-gridlock

The Phase 5 brief lists a fourth level as "incident = 4.0". In this codebase an
incident is a *separate multiplier axis* (an operator disrupts one specific
road), so the fourth network-wide level is named `severe` here and the 4.0
incident value lives on the incident axis as
`realdata.conditions.DEFAULT_INCIDENT_MULTIPLIER`. The numbers are unchanged;
only the axis they sit on is made explicit.

Why congestion is not uniform
-----------------------------
A single multiplier applied to every edge is a no-op for routing: scaling all
travel times by the same constant leaves every shortest path exactly where it
was, so "traffic got worse" would change the reported cost without ever
changing a route. That would make the dynamic demo dishonest.

So the level above is modulated per road by a documented susceptibility
factor. High-capacity through-roads carry the peak flow and degrade most;
residential streets stay closer to free-flow. This is an assumption, stated as
one - but it is the assumption that makes congestion actually re-route
vehicles, which is the behaviour Phase 5 is about.

    multiplier = 1 + (level_multiplier - 1) * susceptibility

At `normal` the level multiplier is exactly 1.0, so every edge is exactly 1.0
regardless of susceptibility, and a normal-conditions scenario is bit-identical
to a scenario with no traffic model applied at all.

Optional BPR formulation
------------------------
`use_bpr=True` derives the level multiplier from the Bureau of Public Roads
volume-delay function instead of the flat table, reusing
`qdfro_graph.weights.bpr_travel_time` so there is exactly one BPR in the
codebase:

    t(v)/t0 = 1 + alpha * (v/c)^beta

Each mode then declares an assumed volume/capacity saturation rather than a
travel-time ratio. It is off by default: the flat table is easier to explain to
a judge and easier to test, and the BPR variant is offered as the more
defensible alternative formulation, not as a more accurate one - the assumed
saturations are just as much an assumption as the ratios they replace.

Determinism
-----------
No randomness anywhere. The same scenario and the same mode always produce the
same multipliers, which is what keeps `same seed + same conditions` reproducible.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional, Tuple

from models import Edge, ProblemScenario

# --------------------------------------------------------------- constants

MODE_NORMAL = "normal"
MODE_MODERATE = "moderate"
MODE_HEAVY = "heavy"
MODE_SEVERE = "severe"

TRAFFIC_MODES = (MODE_NORMAL, MODE_MODERATE, MODE_HEAVY, MODE_SEVERE)

# MODEL PARAMETERS - simulation calibration, not measurements.
LEVEL_MULTIPLIERS: Dict[str, float] = {
    MODE_NORMAL: 1.0,
    MODE_MODERATE: 1.5,
    MODE_HEAVY: 2.5,
    MODE_SEVERE: 4.0,
}

# MODEL PARAMETERS - assumed volume/capacity saturation per mode, used only
# when the BPR formulation is enabled. With the standard alpha=0.15, beta=4
# these give roughly 1.01 / 1.08 / 1.26 / 1.66, i.e. a much gentler curve than
# the flat table; the two are alternative calibrations of the same idea.
MODE_SATURATIONS: Dict[str, float] = {
    MODE_NORMAL: 0.00,
    MODE_MODERATE: 0.85,
    MODE_HEAVY: 1.15,
    MODE_SEVERE: 1.45,
}

BPR_ALPHA = 0.15
BPR_BETA = 4.0

# MODEL PARAMETERS - how much of the network-wide congestion level each road
# class actually absorbs. Keyed by the OSM `highway` tag, which real OSM edges
# carry. 1.0 means "takes the full level multiplier".
CLASS_SUSCEPTIBILITY: Dict[str, float] = {
    "motorway": 1.15, "motorway_link": 1.15,
    "trunk": 1.10, "trunk_link": 1.10,
    "primary": 1.05, "primary_link": 1.05,
    "secondary": 1.00, "secondary_link": 1.00,
    "tertiary": 0.90, "tertiary_link": 0.90,
    "unclassified": 0.80,
    "residential": 0.75,
    "living_street": 0.70,
    "service": 0.70,
    "road": 0.90,
}

DEFAULT_SUSCEPTIBILITY = 1.0

# Synthetic scenarios have no road class, so susceptibility falls back to the
# edge's free-flow speed, which the synthetic generator does vary (30-50 km/h).
# Faster roads stand in for arterials. Bands are (min_kph, susceptibility),
# checked in descending order.
SPEED_SUSCEPTIBILITY_BANDS: Tuple[Tuple[float, float], ...] = (
    (60.0, 1.15),
    (45.0, 1.05),
    (30.0, 0.95),
    (0.0, 0.80),
)

# Provenance labels, reported verbatim by the API.
TRAFFIC_SOURCE_SIMULATED = "simulated"
TRAFFIC_SOURCE_EXTERNAL = "external"


class TrafficProviderError(RuntimeError):
    """Raised when a traffic provider cannot supply conditions."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_mode(mode: Optional[str]) -> str:
    """Accepts a mode name case-insensitively; anything unknown is rejected
    rather than silently treated as normal, so a typo in a request cannot
    quietly turn congestion off."""
    candidate = (mode or MODE_NORMAL).strip().lower()
    if candidate in ("free_flow", "free-flow", "none"):
        return MODE_NORMAL
    if candidate not in LEVEL_MULTIPLIERS:
        raise TrafficProviderError(
            f"Unknown traffic mode '{mode}'. Expected one of: "
            f"{', '.join(TRAFFIC_MODES)}."
        )
    return candidate


def implied_speed_kph(edge: Edge) -> Optional[float]:
    """Free-flow speed implied by the edge's own distance and base time.

    Used only for synthetic edges, which carry no `speed_kph`. Returns None
    when the edge has no usable travel time.
    """
    if edge.speed_kph is not None and edge.speed_kph > 0:
        return float(edge.speed_kph)
    if edge.base_travel_time and edge.base_travel_time > 0:
        return float(edge.distance) / (float(edge.base_travel_time) / 60.0)
    return None


def edge_susceptibility(edge: Edge) -> float:
    """How strongly one road absorbs the network-wide congestion level.

    OSM road class first (it is the real attribute when we have it), then the
    free-flow speed band, then a neutral 1.0.
    """
    if edge.highway:
        known = CLASS_SUSCEPTIBILITY.get(edge.highway.strip().lower())
        if known is not None:
            return known

    speed = implied_speed_kph(edge)
    if speed is not None:
        for min_kph, susceptibility in SPEED_SUSCEPTIBILITY_BANDS:
            if speed >= min_kph:
                return susceptibility

    return DEFAULT_SUSCEPTIBILITY


def bpr_level_multiplier(
    saturation: float,
    alpha: float = BPR_ALPHA,
    beta: float = BPR_BETA,
) -> float:
    """BPR travel-time ratio at a given volume/capacity saturation.

    Delegates to `qdfro_graph.weights.bpr_travel_time` with t0=1 and c=1 so the
    result is the ratio t(v)/t0 directly. Imported lazily to keep `realdata`
    independent of the graph engine's import cost.
    """
    from qdfro_graph.weights import bpr_travel_time

    return bpr_travel_time(1.0, max(0.0, float(saturation)), 1.0, alpha=alpha, beta=beta)


def level_multiplier(mode: str, use_bpr: bool = False) -> float:
    """The network-wide congestion level, before per-road susceptibility."""
    mode = normalize_mode(mode)
    if use_bpr:
        return bpr_level_multiplier(MODE_SATURATIONS[mode])
    return LEVEL_MULTIPLIERS[mode]


def edge_traffic_multiplier(edge: Edge, mode: str, use_bpr: bool = False) -> float:
    """Final per-edge traffic multiplier: level modulated by susceptibility.

    Never returns below 1.0 - this model makes roads slower, never faster than
    their free-flow time.
    """
    level = level_multiplier(mode, use_bpr=use_bpr)
    if level <= 1.0:
        return 1.0
    return max(1.0, 1.0 + (level - 1.0) * edge_susceptibility(edge))


# ------------------------------------------------------------- conditions

EdgeKey = Tuple[int, int]


@dataclass(frozen=True)
class TrafficConditions:
    """One traffic snapshot: a multiplier per directed edge, plus provenance.

    `source` and `is_simulated` exist so no consumer has to guess whether these
    numbers were modelled or observed.
    """
    mode: str
    source: str
    provider: str
    multipliers: Dict[EdgeKey, float] = field(default_factory=dict)
    retrieved_at: str = field(default_factory=_utc_now_iso)
    fallback_used: bool = False
    notes: str = ""

    @property
    def is_simulated(self) -> bool:
        return self.source == TRAFFIC_SOURCE_SIMULATED

    def multiplier_for(self, source: int, destination: int) -> float:
        return self.multipliers.get((source, destination), 1.0)

    def to_dict(self) -> Dict[str, object]:
        return {
            "mode": self.mode,
            "source": self.source,
            "provider": self.provider,
            "is_simulated": self.is_simulated,
            "retrieved_at": self.retrieved_at,
            "fallback_used": self.fallback_used,
            "notes": self.notes,
            "edge_count": len(self.multipliers),
        }


class TrafficProvider(ABC):
    """Seam for supplying per-edge congestion.

    An implementation returns a multiplier over each edge's free-flow
    `base_travel_time`. It must not touch the scenario: composing multipliers
    into an actual travel time is `realdata.conditions`' job, and only its job.
    """

    name: str = "abstract"
    source: str = "abstract"

    @abstractmethod
    def get_traffic(self, scenario: ProblemScenario, mode: str = MODE_NORMAL) -> TrafficConditions:
        """Congestion multipliers for every edge in `scenario`."""


class SimulatedTrafficProvider(TrafficProvider):
    """The documented simulation described at the top of this module.

    Deterministic: same scenario + same mode -> same multipliers, always.
    """

    name = "simulated-model"
    source = TRAFFIC_SOURCE_SIMULATED

    def __init__(self, use_bpr: bool = False):
        self.use_bpr = use_bpr

    def get_traffic(
        self,
        scenario: ProblemScenario,
        mode: str = MODE_NORMAL,
    ) -> TrafficConditions:
        mode = normalize_mode(mode)
        multipliers: Dict[EdgeKey, float] = {
            (edge.source, edge.destination): edge_traffic_multiplier(
                edge, mode, use_bpr=self.use_bpr
            )
            for edge in scenario.edges
        }
        formulation = "bpr" if self.use_bpr else "level-table"
        return TrafficConditions(
            mode=mode,
            source=self.source,
            provider=self.name,
            multipliers=multipliers,
            notes=(
                f"Simulated congestion ({formulation} formulation). Model "
                f"parameters, not measured traffic."
            ),
        )


class ExternalTrafficProvider(TrafficProvider):
    """Placeholder for a real traffic feed.

    Intentionally refuses to run. Returning made-up numbers from something
    named "external" would be exactly the fabrication Phase 5 forbids, and a
    silent fall back to the simulation would let the UI report an external
    source it never contacted. A real implementation replaces this class body
    and nothing else: the cost engine, the route-matrix cache, the optimizers
    and the API all consume `TrafficConditions` and are already indifferent to
    where it came from.
    """

    name = "external-provider"
    source = TRAFFIC_SOURCE_EXTERNAL

    def __init__(self, provider_name: str = "external-provider"):
        self.name = provider_name

    def get_traffic(
        self,
        scenario: ProblemScenario,
        mode: str = MODE_NORMAL,
    ) -> TrafficConditions:
        raise TrafficProviderError(
            "No external traffic provider is configured. This prototype ships "
            "with simulated traffic only; the external interface exists so a "
            "real feed can be added later without changing the cost engine."
        )


# Shared provider used by the API layer.
DEFAULT_TRAFFIC_PROVIDER = SimulatedTrafficProvider()


def get_traffic_provider(traffic_source: str = TRAFFIC_SOURCE_SIMULATED) -> TrafficProvider:
    """Resolves a requested traffic source to a provider instance."""
    requested = (traffic_source or TRAFFIC_SOURCE_SIMULATED).strip().lower()
    if requested in (TRAFFIC_SOURCE_SIMULATED, "simulation", "model"):
        return DEFAULT_TRAFFIC_PROVIDER
    if requested == TRAFFIC_SOURCE_EXTERNAL:
        return ExternalTrafficProvider()
    raise TrafficProviderError(
        f"Unknown traffic source '{traffic_source}'. Expected "
        f"'{TRAFFIC_SOURCE_SIMULATED}' or '{TRAFFIC_SOURCE_EXTERNAL}'."
    )
