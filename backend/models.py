from typing import List, Dict, Optional
from pydantic import BaseModel, Field, model_validator


class Node(BaseModel):
    id: int
    name: str
    lat: float
    lng: float
    is_depot: bool = False
    # Populated only for scenarios built from OpenStreetMap. `id` stays a
    # small contiguous integer because the optimizers and the route matrix
    # index by it; the original OSM identity is preserved alongside it.
    osm_id: Optional[int] = None


class Edge(BaseModel):
    source: int
    destination: int
    distance: float  # kilometers
    # Free-flow time from the road's own length and speed. Never modified
    # after the scenario is built - every dynamic condition is a multiplier
    # over this, so the unconditioned baseline is always recoverable.
    base_travel_time: float  # minutes

    # --- dynamic condition multipliers -----------------------------------
    # Three independent axes, each 1.0 when that condition is not active.
    # `realdata.conditions` is the only module that writes them, and the only
    # module that writes `traffic_factor` or `current_travel_time` from them.
    traffic_multiplier: float = 1.0   # simulated (or external) congestion
    weather_multiplier: float = 1.0   # derived from an observed weather condition
    incident_multiplier: float = 1.0  # operator-injected disruption on one road

    # The effective multiplier actually applied:
    #     traffic_multiplier * weather_multiplier * incident_multiplier
    # Kept under its original name because the route-matrix cache key, the
    # objective function and the map all read it, and because a pre-Phase-5
    # client that writes it directly still behaves exactly as it did before.
    traffic_factor: float = 1.0  # multiplier (1.0 = free flow, 3.0 = heavy congestion)
    current_travel_time: float  # base_travel_time * traffic_factor
    road_name: str = ""

    # Which congestion band this edge currently sits in, derived from
    # `traffic_factor` against the documented thresholds in
    # `realdata.conditions.CONGESTION_BANDS`. Written by the same single
    # function that writes traffic_factor, so it can never disagree with it.
    #
    # It exists so the map colours a road from a backend-declared state rather
    # than from numeric thresholds duplicated in React. Values:
    #     free_flow | light | moderate | heavy | severe
    congestion_level: str = "free_flow"
    # True when this specific road carries an operator-injected incident, as
    # opposed to merely being congested by the network-wide traffic level.
    # The map needs to distinguish the two and cannot infer it from
    # traffic_factor alone.
    has_incident: bool = False

    # --- OpenStreetMap provenance (None for synthetic scenarios) ----------
    osm_way_id: Optional[int] = None
    highway: Optional[str] = None          # OSM highway class, e.g. "residential"
    # Road shape as [[lat, lng], ...] including intermediate OSM nodes, so the
    # map can draw the actual curve rather than a straight line between
    # intersections. Ordered along the direction of travel.
    geometry: Optional[List[List[float]]] = None
    speed_kph: Optional[float] = None
    # "osm_maxspeed" when the value came from an OSM maxspeed tag,
    # "fallback:<highway class>" when it was derived from the road class.
    speed_source: Optional[str] = None
    lanes: Optional[int] = None
    lanes_source: Optional[str] = None
    capacity_vph: Optional[float] = None


class Vehicle(BaseModel):
    id: int
    capacity: float
    start_node: int
    end_node: int
    max_route_time: float = 120.0  # minutes limit per vehicle route
    color: str = "#3B82F6"  # visual hex color


class Job(BaseModel):
    id: int
    node_id: int
    demand: float
    service_time: float = 5.0  # minutes service time at destination
    priority: int = 1
    # Delivery time window, in minutes from shift start (t=0 at depot
    # departure). None means no window - existing scenarios/fixtures that
    # never set these behave exactly as before (see schedule.simulate_route).
    ready_time: Optional[float] = None
    due_time: Optional[float] = None

    @model_validator(mode="after")
    def _validate_time_window(self) -> "Job":
        if self.ready_time is not None and self.ready_time < 0:
            raise ValueError("ready_time must be >= 0")
        if self.due_time is not None and self.due_time < 0:
            raise ValueError("due_time must be >= 0")
        if self.ready_time is not None and self.due_time is not None:
            if self.ready_time > self.due_time:
                raise ValueError("ready_time must be <= due_time")
        return self


class WeatherState(BaseModel):
    """A weather observation as reported over the API, or the explicit absence
    of one. Mirrors realdata.weather.WeatherObservation.

    `source` is "open-meteo" territory: network / cache / cache-stale for a
    real reading, "fallback" when none was available. When `fallback_used` is
    true every measured field is null - a fallback never carries invented
    values, and `multiplier` is then exactly 1.0.
    """
    source: str
    provider: str = "open-meteo"
    condition: str = "unknown"
    description: str = ""
    multiplier: float = 1.0
    weather_code: Optional[int] = None
    temperature_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kph: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    observed_at: Optional[str] = None
    retrieved_at: str = ""
    fallback_used: bool = False
    is_real_observation: bool = False
    error: Optional[str] = None


class ConditionSummary(BaseModel):
    """What conditions are currently baked into a scenario's edge costs.

    Carried on the scenario itself so every endpoint that returns a scenario
    reports its conditions too, and so the frontend never has to infer them.
    Nothing here is computed client-side.
    """
    # --- traffic ---
    traffic_mode: str = "normal"
    traffic_source: str = "simulated"   # "simulated" | "external"
    traffic_provider: str = "simulated-model"
    traffic_is_simulated: bool = True
    traffic_formulation: str = "level-table"

    # --- weather ---
    weather_enabled: bool = False
    weather_source: Optional[str] = None   # network|cache|cache-stale|fallback
    weather_condition: Optional[str] = None
    weather_multiplier: float = 1.0
    weather: Optional[WeatherState] = None

    # --- incidents ---
    incident_edge_count: int = 0

    # --- provenance ---
    updated_at: str = ""
    fallback_used: bool = False
    # Short deterministic fingerprint of the applied condition state. Two
    # scenarios with the same signature had the same conditions applied.
    signature: str = ""


class ProblemScenario(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    vehicles: List[Vehicle]
    jobs: List[Job]
    depot_node_id: int
    seed: int = 42
    scenario_hash: str = ""  # deterministic id of the generation parameters, for display/replay
    # "synthetic" or "openstreetmap". Travels with the scenario so the UI can
    # state what the network actually is without a second lookup.
    data_source: str = "synthetic"
    # None means no condition layer has been applied - edges are at free flow,
    # exactly as they were before Phase 5.
    conditions: Optional[ConditionSummary] = None


def clone_scenario(scenario: ProblemScenario) -> ProblemScenario:
    """Independent copy of a scenario: safe to mutate without affecting the
    original, same as `scenario.model_copy(deep=True)`, but far cheaper on
    real OpenStreetMap-scale scenarios.

    `model_copy(deep=True)` recursively deep-copies every nested list,
    including each Edge's `geometry` point list - measured to dominate
    request time (up to several seconds) once scenarios carry real road
    shapes instead of the synthetic generator's straight lines.

    This instead makes a new top-level list of shallow-copied Node/Edge/
    Vehicle/Job instances. That's sufficient independence because every
    mutation in this codebase (`realdata.conditions.recompute_edge_cost` and
    friends) only ever reassigns scalar fields on an edge/node - never
    mutates a nested container in place. `Edge.geometry` is the only nested
    mutable field on any of these models, and it is read-only after
    construction everywhere in this codebase, so sharing the same geometry
    list between the original and the clone is safe and avoids copying it.
    """
    return scenario.model_copy(update={
        "nodes": [n.model_copy() for n in scenario.nodes],
        "edges": [e.model_copy() for e in scenario.edges],
        "vehicles": [v.model_copy() for v in scenario.vehicles],
        "jobs": [j.model_copy() for j in scenario.jobs],
        "conditions": scenario.conditions.model_copy(deep=True) if scenario.conditions is not None else None,
    })


class ObjectiveWeights(BaseModel):
    alpha: float = 1.0  # weight for travel time
    beta: float = 0.5   # weight for distance
    gamma: float = 1.0  # weight for congestion cost
    penalty_weight: float = 1000.0  # penalty multiplier for constraint violations


class OptimizationConfig(BaseModel):
    algorithm: str = "qpso"  # greedy, pso, ga, qpso, exact
    population_size: int = 40
    max_iterations: int = 100
    seed: int = 42
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    # QPSO's 2-opt/or-opt local-search hybrid (optimizers/local_search.py).
    # Defaults on: plain QPSO alone loses to Greedy at 30+ jobs and often
    # goes infeasible (measured, not assumed) - this is the fix, not an
    # optional extra. Set False to run the old, un-hybridized QPSO as an
    # explicit ablation/comparison baseline.
    use_local_search: bool = True
    local_search_interval: int = 10  # run it every N iterations on gbest


class StopTiming(BaseModel):
    """One job's timing on a route, as computed by schedule.simulate_route."""
    job_id: int
    arrival: float       # clock reading when the vehicle reaches this stop
    service_start: float  # max(arrival, job.ready_time) - waiting is counted, not skipped
    departure: float      # service_start + job.service_time
    wait: float           # service_start - arrival
    lateness: float       # max(0, service_start - job.due_time), 0 when no due_time


class VehicleRoute(BaseModel):
    vehicle_id: int
    job_ids: List[int]
    node_path: List[int]  # sequence of graph nodes starting and ending at depot
    route_distance: float
    route_travel_time: float
    total_demand: float
    capacity_exceeded: float = 0.0
    time_exceeded: float = 0.0
    congestion_delay: float = 0.0  # this route's share of total fleet congestion delay
    # Time-window fields (schedule.simulate_route). All zero/empty when no
    # job on this route carries a ready_time/due_time.
    stops: List[StopTiming] = []
    wait_time: float = 0.0   # total minutes waited across all stops
    lateness: float = 0.0    # total minutes late across all stops (soft constraint)
    late_jobs: int = 0       # count of stops served after their due_time


class OptimizationResult(BaseModel):
    algorithm: str
    routes: List[VehicleRoute]
    total_cost: float
    total_travel_time: float
    total_distance: float
    runtime_ms: float
    constraint_violations: int
    convergence_history: List[float]
    # Real elapsed time (ms, from optimization start) at the point each
    # convergence_history entry was recorded - one entry per iteration, same
    # length as convergence_history when populated. Empty for algorithms
    # that don't record per-iteration timing (e.g. Greedy).
    convergence_elapsed_ms: List[float] = []
    is_feasible: bool


class TrafficUpdate(BaseModel):
    source: int
    destination: int
    traffic_factor: float


class TrafficUpdateBatch(BaseModel):
    updates: List[TrafficUpdate]


class BenchmarkResult(BaseModel):
    scenario_seed: int
    results: Dict[str, OptimizationResult]
    # True when served from the deterministic result cache (identical
    # scenario content + config as an earlier run) rather than recomputed.
    # Each result's runtime_ms is still the time genuinely measured when it
    # was computed.
    cached: bool = False
