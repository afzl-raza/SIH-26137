import csv
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from models import (
    ProblemScenario,
    OptimizationConfig,
    OptimizationResult,
    TrafficUpdate,
    TrafficUpdateBatch,
    BenchmarkResult,
    VehicleRoute,
    ObjectiveWeights
)
from problem_generator import generate_synthetic_scenario, customize_scenario
from realdata.scenario_store import SCENARIO_STORE, ScenarioNotFoundError
from realdata.geocoding import GeocodingError, resolve_location
from realdata.osm_loader import OsmLoaderError, load_osm_graph
from realdata.osm_scenario import osm_graph_to_scenario
from realdata.conditions import (
    ConditionRequest,
    apply_conditions,
    apply_incidents,
    scenario_center,
    weather_multiplier_for,
)
from realdata.traffic_model import (
    MODE_NORMAL,
    TRAFFIC_MODES,
    TRAFFIC_SOURCE_SIMULATED,
    TrafficProviderError,
)
from realdata.weather import DEFAULT_WEATHER_PROVIDER
from route_cache import ROUTE_MATRIX_CACHE
from route_geometry import route_geometries, scenario_geometry_source
from optimizers.greedy import GreedyOptimizer
from optimizers.pso import PSOOptimizer
from optimizers.qpso import QPSOOptimizer
from optimizers.exact import ExactOptimizer, ExactSolverTooLargeError
from optimizers.benchmark import run_benchmark
from fitness import evaluate_solution
from experiments.runner import (
    run_e1_algorithm_comparison,
    run_e2_convergence,
    run_e3_scalability,
    run_e4_traffic_disruption,
    run_e5_traffic_severity,
    run_e6_reproducibility,
)


app = FastAPI(
    title="Q-DFRO API",
    description="Quantum-Inspired Intelligent Traffic Route Optimization API",
    version="1.0.0"
)

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    # "synthetic" keeps the original generated network; "osm" builds the
    # scenario from real OpenStreetMap road data for the requested location.
    source: str = "synthetic"

    num_jobs: int = 15
    num_vehicles: int = 3
    seed: int = 42
    num_nodes: int = 30  # synthetic only - OSM node count comes from the map

    # Synthetic only - bounds on each job's randomly drawn demand, and an
    # optional flat vehicle capacity that skips the demand-derived formula.
    demand_min: float = 5.0
    demand_max: float = 15.0
    vehicle_capacity_override: Optional[float] = None

    # Location inputs, any one of which resolves to a bounded area. No city is
    # special: a place name goes through the geocoder, coordinates and boxes
    # are used directly.
    place: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    bbox: Optional[List[float]] = None  # [min_lat, min_lon, max_lat, max_lon]
    radius_m: Optional[float] = None


# Scenario-carrying payloads accept either a `scenario_id` (the backend owns
# the scenario, which is what keeps request bodies small once scenarios carry
# OpenStreetMap geometry) or a full inline `scenario` (the original format,
# kept working during the migration). When both are present, scenario_id wins.
class ScenarioRefMixin(BaseModel):
    scenario: Optional[ProblemScenario] = None
    scenario_id: Optional[str] = None


class OptimizePayload(ScenarioRefMixin):
    config: OptimizationConfig


class TrafficPayload(ScenarioRefMixin):
    updates: List[TrafficUpdate]


class EvaluatePayload(ScenarioRefMixin):
    routes: List[VehicleRoute]
    weights: ObjectiveWeights


class RouteGeometryPayload(ScenarioRefMixin):
    """Asks for the road shape of an already-computed set of routes."""
    routes: List[VehicleRoute]


def _resolve_scenario(payload: ScenarioRefMixin):
    """Returns (scenario, scenario_id). `scenario_id` is None when the caller
    used the legacy inline-scenario format, in which case the backend holds no
    stored copy to write back to."""
    if payload.scenario_id:
        try:
            record = SCENARIO_STORE.get(payload.scenario_id)
        except ScenarioNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Unknown scenario_id '{payload.scenario_id}'. It may have "
                    f"expired - generate the scenario again."
                ),
            )
        return record.scenario, record.scenario_id

    if payload.scenario is not None:
        return payload.scenario, None

    raise HTTPException(
        status_code=422,
        detail="Either 'scenario_id' or 'scenario' must be provided.",
    )


# Read-only surface for backend/experiments/runner.py output. No persistence
# layer is introduced here - this just serves files the runner already wrote
# to <repo_root>/experiments/, so the frontend can show real evidence
# (scalability, reproducibility) instead of fabricating it.
EXPERIMENTS_ROOT = Path(__file__).resolve().parent.parent / "experiments"
KNOWN_EXPERIMENTS = {
    "E1_algorithm_comparison",
    "E2_convergence",
    "E3_scalability",
    "E4_traffic_disruption",
    "E5_traffic_severity",
    "E6_reproducibility",
}


@app.get("/api/health")
def health_check():
    # Route-matrix cache counters are reported here as plain diagnostics, so
    # the "one build, three hits per benchmark" behaviour can be observed
    # rather than taken on trust.
    return {
        "status": "ok",
        "app": "Q-DFRO Backend",
        "stored_scenarios": len(SCENARIO_STORE),
        "route_matrix_cache": ROUTE_MATRIX_CACHE.stats(),
    }


@app.post("/api/problem/generate")
def generate_problem(req: GenerateRequest):
    """Generates a scenario, stores it server-side, and returns it together
    with the `scenario_id` later calls should refer to.

    The full scenario is still included in the response because the frontend
    needs the nodes and edges to draw the map. What moves server-side is the
    scenario on every *subsequent* request body.
    """
    if req.source.strip().lower() in ("osm", "openstreetmap"):
        return _generate_from_openstreetmap(req)

    if req.demand_min > req.demand_max:
        raise HTTPException(status_code=400, detail="demand_min cannot exceed demand_max")

    try:
        scenario = generate_synthetic_scenario(
            num_nodes=req.num_nodes,
            num_jobs=req.num_jobs,
            num_vehicles=req.num_vehicles,
            seed=req.seed,
            demand_min=req.demand_min,
            demand_max=req.demand_max,
            vehicle_capacity_override=req.vehicle_capacity_override
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    record = SCENARIO_STORE.create(scenario, data_source="synthetic")
    return {
        **record.metadata(),
        **_condition_envelope(record.scenario),
        # Stated up front so the map knows whether these roads have real
        # shapes or are the generator's straight lines, without inspecting
        # every edge itself.
        "geometry_source": scenario_geometry_source(record.scenario),
        "scenario": record.scenario,
    }


class CustomizePayload(ScenarioRefMixin):
    depot_node_id: int
    job_node_ids: List[int]
    demand_min: float = 5.0
    demand_max: float = 15.0


@app.post("/api/problem/customize")
def customize_problem(payload: CustomizePayload):
    """Rebuilds a stored scenario's depot and delivery stops from
    operator-picked existing map nodes, instead of the generator's random
    placement. Requires a stored scenario_id - unlike other scenario-carrying
    endpoints, the legacy inline-scenario format has nowhere to write the
    result back to.
    """
    if not payload.scenario_id:
        raise HTTPException(status_code=400, detail="customize requires a stored scenario_id")
    if payload.demand_min > payload.demand_max:
        raise HTTPException(status_code=400, detail="demand_min cannot exceed demand_max")

    stored_scenario, scenario_id = _resolve_scenario(payload)

    try:
        scenario = customize_scenario(
            stored_scenario,
            depot_node_id=payload.depot_node_id,
            job_node_ids=payload.job_node_ids,
            demand_min=payload.demand_min,
            demand_max=payload.demand_max,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = SCENARIO_STORE.update(scenario_id, scenario)
    return {
        **record.metadata(),
        **_condition_envelope(record.scenario),
        "geometry_source": scenario_geometry_source(record.scenario),
        "scenario": record.scenario,
    }


# OpenStreetMap supplies the road network only. It carries no traffic
# information, so congestion is a simulation the operator drives. These labels
# exist so the UI can never imply a live traffic feed.
#
# Weather is different: it IS fetched from a real provider (Open-Meteo), but
# only once conditions are applied with weather enabled, so a freshly
# generated scenario reports no weather source yet.
TRAFFIC_SOURCE_LABEL = TRAFFIC_SOURCE_SIMULATED
WEATHER_SOURCE_LABEL = None


def _condition_envelope(scenario: ProblemScenario) -> dict:
    """The condition metadata every scenario-carrying response reports.

    Always answers "where did these numbers come from": which traffic source,
    which weather source, whether a fallback was used. A scenario that has had
    no conditions applied reports free-flow defaults rather than nothing, so a
    client never has to distinguish missing from normal.
    """
    conditions = scenario.conditions
    if conditions is None:
        return {
            "traffic_source": TRAFFIC_SOURCE_LABEL,
            "traffic_mode": MODE_NORMAL,
            "weather_source": WEATHER_SOURCE_LABEL,
            "weather_condition": None,
            "fallback_used": False,
            "conditions": None,
        }
    return {
        "traffic_source": conditions.traffic_source,
        "traffic_mode": conditions.traffic_mode,
        "weather_source": conditions.weather_source,
        "weather_condition": conditions.weather_condition,
        "fallback_used": conditions.fallback_used,
        "conditions": conditions,
    }


def _generate_from_openstreetmap(req: GenerateRequest):
    """location -> bbox -> Overpass -> real road graph -> ProblemScenario."""
    try:
        location = resolve_location(
            place=req.place,
            latitude=req.latitude,
            longitude=req.longitude,
            bbox=tuple(req.bbox) if req.bbox else None,
            radius_m=req.radius_m,
        )
    except GeocodingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        graph = load_osm_graph(location)
    except OsmLoaderError as e:
        # Upstream is unavailable and nothing is cached. This deliberately
        # fails rather than quietly returning a synthetic network, which would
        # misrepresent generated roads as real map data.
        raise HTTPException(status_code=502, detail=str(e))

    try:
        scenario = osm_graph_to_scenario(
            graph,
            num_jobs=req.num_jobs,
            num_vehicles=req.num_vehicles,
            seed=req.seed,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    record = SCENARIO_STORE.create(
        scenario, data_source="openstreetmap", location=location.to_dict()
    )
    body = {**record.metadata(), **location.to_dict()}
    body.update(_condition_envelope(record.scenario))
    body.update({
        "geometry_source": scenario_geometry_source(record.scenario),
        "scenario": record.scenario,
        "provenance": graph.provenance,
        "retrieved_at": graph.retrieved_at,
        "osm": graph.stats,
        "osm_endpoint": graph.endpoint,
    })
    return body


@app.post("/api/optimize", response_model=OptimizationResult)
def optimize_route(payload: OptimizePayload):
    scenario, _ = _resolve_scenario(payload)
    try:
        algo = payload.config.algorithm.lower()
        if "exact" in algo:
            optimizer = ExactOptimizer()
        elif "qpso" in algo:
            optimizer = QPSOOptimizer()
        elif "pso" in algo:
            optimizer = PSOOptimizer()
        elif "ga" in algo or "genetic" in algo:
            from optimizers.ga import GAOptimizer
            optimizer = GAOptimizer()
        elif "greedy" in algo or "neighbour" in algo:
            optimizer = GreedyOptimizer()
        else:
            optimizer = QPSOOptimizer()

        result = optimizer.optimize(scenario, payload.config)
        return result
    except ExactSolverTooLargeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization error: {str(e)}")


@app.post("/api/traffic/update")
def update_traffic(payload: TrafficPayload):
    """Injects a simulated road incident on selected edges and persists it.

    The request field is still called `traffic_factor`, unchanged, so existing
    clients keep working. What it sets is the edge's *incident* multiplier:
    the operator is disrupting one specific road, which is a different axis
    from the network-wide traffic level and from weather. When no traffic
    level or weather is applied - the default - the resulting effective
    multiplier is exactly the requested number, so behaviour is identical to
    before Phase 5. When they are applied, the three compose, which is the
    point of separating them.

    The incident goes through realdata.conditions like every other condition,
    so there is no second edge-cost calculation anywhere.

    The stored scenario is never mutated in place: a copy is conditioned and
    handed back to the store. The route-matrix cache needs no explicit
    invalidation because its key is derived from the edge costs themselves -
    a changed edge simply produces a different key, so a stale matrix cannot
    be served.
    """
    stored_scenario, scenario_id = _resolve_scenario(payload)

    try:
        updates = {
            (u.source, u.destination): u.traffic_factor for u in payload.updates
        }
        scenario, updated_edges = apply_incidents(stored_scenario, updates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if scenario_id is not None:
        record = SCENARIO_STORE.update(scenario_id, scenario)
        return {
            **record.metadata(),
            **_condition_envelope(record.scenario),
            "updated_edges": updated_edges,
            "scenario": record.scenario,
        }

    # Legacy inline-scenario call: nothing stored, so echo the updated scenario.
    return {
        "scenario_id": None,
        "scenario_hash": scenario.scenario_hash,
        "data_source": "inline",
        "node_count": len(scenario.nodes),
        "edge_count": len(scenario.edges),
        "job_count": len(scenario.jobs),
        "vehicle_count": len(scenario.vehicles),
        **_condition_envelope(scenario),
        "updated_edges": updated_edges,
        "scenario": scenario,
    }


class ConditionsPayload(ScenarioRefMixin):
    """Requests a new environmental condition state for a scenario.

    Incidents are not settable here: they are per-road operator actions with
    their own endpoint (/api/traffic/update), and they deliberately survive a
    traffic or weather change rather than being reset by one.
    """
    traffic_mode: str = MODE_NORMAL          # normal | moderate | heavy | severe
    traffic_source: str = TRAFFIC_SOURCE_SIMULATED  # simulated | external
    weather_enabled: bool = False
    # Opt in to the BPR volume-delay formulation instead of the flat level
    # table. Both are documented model assumptions; see realdata.traffic_model.
    use_bpr: bool = False


@app.post("/api/scenario/conditions")
def set_scenario_conditions(payload: ConditionsPayload):
    """Applies a traffic level and (optionally) real weather to a scenario.

    This only changes edge costs. It does not re-optimize: the client calls
    /api/optimize afterwards, exactly as it does after an incident, so the
    "conditions changed -> routes changed" causality stays visible instead of
    being hidden inside one endpoint.

    A weather-provider failure is not an error here. The provider returns an
    explicit fallback observation, no weather multiplier is applied, and the
    response says `weather_source: "fallback"` with `fallback_used: true`.
    """
    stored_scenario, scenario_id = _resolve_scenario(payload)

    try:
        request = ConditionRequest(
            traffic_mode=payload.traffic_mode,
            traffic_source=payload.traffic_source,
            weather_enabled=payload.weather_enabled,
            use_bpr=payload.use_bpr,
        )
        scenario = apply_conditions(stored_scenario, request)
    except TrafficProviderError as e:
        # Unknown mode, or the external provider that deliberately refuses to
        # fabricate data. Both are client-visible configuration problems.
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if scenario_id is not None:
        record = SCENARIO_STORE.update(scenario_id, scenario)
        return {
            **record.metadata(),
            **_condition_envelope(record.scenario),
            "scenario": record.scenario,
        }

    return {
        "scenario_id": None,
        "scenario_hash": scenario.scenario_hash,
        "data_source": "inline",
        "node_count": len(scenario.nodes),
        "edge_count": len(scenario.edges),
        "job_count": len(scenario.jobs),
        "vehicle_count": len(scenario.vehicles),
        **_condition_envelope(scenario),
        "scenario": scenario,
    }


@app.get("/api/weather")
def get_weather(
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    scenario_id: Optional[str] = None,
):
    """Current weather at a coordinate, or at a stored scenario's own location.

    Read-only: it does not touch any scenario's edge costs. Useful for showing
    conditions before deciding to apply them, and for making the fallback
    behaviour observable on its own.
    """
    if scenario_id:
        try:
            record = SCENARIO_STORE.get(scenario_id)
        except ScenarioNotFoundError:
            raise HTTPException(
                status_code=404, detail=f"Unknown scenario_id '{scenario_id}'."
            )
        latitude, longitude = scenario_center(record.scenario)

    if latitude is None or longitude is None:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'scenario_id' or both 'latitude' and 'longitude'.",
        )

    observation = DEFAULT_WEATHER_PROVIDER.get_weather(latitude, longitude)
    body = observation.to_dict()
    body["multiplier"] = weather_multiplier_for(observation)
    return body


@app.post("/api/routes/geometry")
def get_route_geometry(payload: RouteGeometryPayload):
    """The road shape of an already-computed set of routes.

    This does not route. It takes the node path the optimizer already produced
    - which is the full node-by-node Dijkstra path, not just the job order -
    and looks up the OpenStreetMap geometry of each hop, using the same
    parallel-edge rule the router used. The result is the actual road the
    vehicle drives, drawn from OSM's own way geometry.

    It lives here rather than in the frontend so that no route calculation of
    any kind exists in React, and so the stitching is covered by tests.

    For a synthetic network, whose edges carry no geometry, every hop falls
    back to the straight line between its two nodes and says so in
    `geometry_source` - the same picture the map has always drawn, now
    labelled.
    """
    scenario, _ = _resolve_scenario(payload)
    try:
        routes = route_geometries(scenario, payload.routes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route geometry error: {str(e)}")

    return {
        "data_source": scenario.data_source,
        "geometry_source": scenario_geometry_source(scenario),
        "routes": routes,
    }


@app.get("/api/scenario/{scenario_id}/manifest")
def get_scenario_manifest(
    scenario_id: str,
    algorithm: Optional[str] = None,
    population_size: Optional[int] = None,
    max_iterations: Optional[int] = None,
):
    """Everything needed to reproduce a run, read back from the server.

    The point is that a judge can read the manifest rather than take the
    demonstrator's word for what was configured. Every field is either stored
    state or the caller's own solver settings echoed back - nothing is
    reconstructed or guessed, and a field the backend genuinely does not know
    (a synthetic network has no real location; a solver setting the caller did
    not pass) is reported as null instead of being filled in.
    """
    try:
        record = SCENARIO_STORE.get(scenario_id)
    except ScenarioNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown scenario_id '{scenario_id}'.")

    scenario = record.scenario
    conditions = scenario.conditions

    return {
        "scenario_id": record.scenario_id,
        # The deterministic fingerprint of the generation parameters: same
        # hash means the same network can be regenerated.
        "scenario_hash": record.scenario_hash,
        "seed": scenario.seed,
        "data_source": record.data_source,
        "geometry_source": scenario_geometry_source(scenario),
        # Null for synthetic networks, which have no real-world location.
        "location": record.location,
        "network": {
            "node_count": len(scenario.nodes),
            "edge_count": len(scenario.edges),
            "job_count": len(scenario.jobs),
            "vehicle_count": len(scenario.vehicles),
            "depot_node_id": scenario.depot_node_id,
        },
        # Echoed from the caller: these are the solver settings the client
        # used, which the backend does not otherwise retain.
        "solver": {
            "algorithm": algorithm,
            "population_size": population_size,
            "max_iterations": max_iterations,
        },
        "conditions": {
            "applied": conditions is not None,
            "traffic_mode": conditions.traffic_mode if conditions else MODE_NORMAL,
            "traffic_source": conditions.traffic_source if conditions else TRAFFIC_SOURCE_LABEL,
            "traffic_provider": conditions.traffic_provider if conditions else None,
            "traffic_is_simulated": conditions.traffic_is_simulated if conditions else True,
            "traffic_formulation": conditions.traffic_formulation if conditions else None,
            "weather_enabled": conditions.weather_enabled if conditions else False,
            "weather_source": conditions.weather_source if conditions else None,
            "weather_condition": conditions.weather_condition if conditions else None,
            "weather_multiplier": conditions.weather_multiplier if conditions else 1.0,
            "weather_observed_at": (
                conditions.weather.observed_at if conditions and conditions.weather else None
            ),
            "incident_edge_count": conditions.incident_edge_count if conditions else 0,
            "fallback_used": conditions.fallback_used if conditions else False,
            "signature": conditions.signature if conditions else None,
            "updated_at": conditions.updated_at if conditions else None,
        },
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@app.get("/api/conditions/model")
def get_condition_model():
    """The condition model's own parameters, served so the UI and any report
    can state the assumptions rather than restating them by hand (and drifting).

    Everything under `simulated` is a model assumption. Everything under `real`
    is genuinely observed or measured data.
    """
    from realdata.conditions import (
        CONGESTION_BANDS,
        CONGESTION_LEVELS,
        DEFAULT_INCIDENT_MULTIPLIER,
        WEATHER_IMPACT,
    )
    from realdata.traffic_model import (
        CLASS_SUSCEPTIBILITY,
        LEVEL_MULTIPLIERS,
        MODE_SATURATIONS,
    )

    return {
        "formula": (
            "current_travel_time = base_travel_time * traffic_multiplier "
            "* weather_multiplier * incident_multiplier"
        ),
        "simulated": {
            "traffic_modes": TRAFFIC_MODES,
            "traffic_level_multipliers": LEVEL_MULTIPLIERS,
            "traffic_bpr_saturations": MODE_SATURATIONS,
            "road_class_susceptibility": CLASS_SUSCEPTIBILITY,
            "weather_impact_multipliers": WEATHER_IMPACT,
            "default_incident_multiplier": DEFAULT_INCIDENT_MULTIPLIER,
            # Display bands only. Published so the map's colours and the
            # thresholds behind them are the same declared numbers, and so a
            # reader can check what "heavy" on screen actually means.
            "congestion_levels": list(CONGESTION_LEVELS),
            "congestion_bands": [
                {"level": name, "min_traffic_factor": threshold}
                for name, threshold in CONGESTION_BANDS
            ],
            "disclaimer": (
                "Model parameters / calibration assumptions for a prototype. "
                "Not traffic measurements, and not calibrated weather-impact "
                "research findings."
            ),
        },
        "real": {
            "road_network": "OpenStreetMap (geometry, topology, speed limits)",
            "geocoding": "Nominatim",
            "weather_observations": "Open-Meteo",
        },
    }


@app.post("/api/benchmark", response_model=BenchmarkResult)
def benchmark_scenario(payload: OptimizePayload):
    scenario, _ = _resolve_scenario(payload)
    try:
        return run_benchmark(scenario, payload.config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/evaluate", response_model=OptimizationResult)
def evaluate_routes(payload: EvaluatePayload):
    """Re-scores an already-computed set of routes against a new set of
    objective weights, without re-optimizing. Used for the live "what would
    this cost under different weights" preview - the score always comes
    from the same evaluator every optimizer uses, never computed client-side.
    """
    scenario, _ = _resolve_scenario(payload)
    try:
        return evaluate_solution(payload.routes, scenario, payload.weights, algorithm_name="preview")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/experiments/{name}")
def get_experiment_results(name: str):
    if name not in KNOWN_EXPERIMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown experiment '{name}'.")

    exp_dir = EXPERIMENTS_ROOT / name
    if not exp_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Experiment '{name}' has not been run yet. Run "
                f"`python -m experiments.runner --experiment all` from backend/."
            )
        )

    response: dict = {"name": name}

    config_path = exp_dir / "config.json"
    if config_path.exists():
        response["config"] = json.loads(config_path.read_text())

    for json_file in ("raw_results.json", "summary.json", "result.json"):
        path = exp_dir / json_file
        if path.exists():
            response["result"] = json.loads(path.read_text())
            break

    for csv_file in ("results.csv", "convergence.csv", "raw_runs.csv"):
        path = exp_dir / csv_file
        if path.exists():
            with path.open(newline="") as f:
                response["rows"] = list(csv.DictReader(f))
            break

    return response


EXPERIMENT_RUNNERS = {
    "E1_algorithm_comparison": run_e1_algorithm_comparison,
    "E2_convergence": run_e2_convergence,
    "E3_scalability": run_e3_scalability,
    "E4_traffic_disruption": run_e4_traffic_disruption,
    "E5_traffic_severity": run_e5_traffic_severity,
    "E6_reproducibility": run_e6_reproducibility,
}


@app.post("/api/experiments/{name}/run")
def run_experiment_live(name: str):
    """Runs the real experiment function (the identical code path the CLI
    uses) synchronously and returns its output - a UI trigger for the same
    evidence-generation code, not a separate/simulated computation."""
    if name not in EXPERIMENT_RUNNERS:
        raise HTTPException(status_code=400, detail=f"Unknown experiment '{name}'.")

    try:
        EXPERIMENT_RUNNERS[name]()
    except RuntimeError as e:
        # Frozen-config guard: a prior run with different parameters exists.
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Experiment run failed: {str(e)}")

    return get_experiment_results(name)


# =====================================================================
# Q-DFRO Graph Engine API Surface (/api/qdfro-graph/*)
# Self-contained Sioux Falls benchmark network + live graph-based QPSO
# routing engine. Does not touch or depend on the synthetic-scenario
# pipeline (models.py / problem_generator.py) above.
# =====================================================================

from qdfro_graph import (
    build_sioux_falls_real,
    load_sioux_falls_od_demand,
    msa_assignment,
    CostMatrixUpdater,
    ReservationTable,
    GraphQPSOInterface,
    QPSOSolver,
    VehicleRoute as GraphVehicleRoute
)

# Global Graph Engine state
_GRAPH_ENGINE = {
    "graph": None,
    "updater": None,
    "reservations": None,
    "iface": None,
    "routes": {}
}


def _get_or_init_graph():
    if _GRAPH_ENGINE["graph"] is None:
        graph = build_sioux_falls_real()
        od_demand = load_sioux_falls_od_demand()
        msa_assignment(graph, od_demand, n_iterations=15)

        updater = CostMatrixUpdater(graph, theta=0.15)
        reservations = ReservationTable(slice_seconds=10.0, k_penalty=500.0)
        iface = GraphQPSOInterface(updater, reservations)

        _GRAPH_ENGINE["graph"] = graph
        _GRAPH_ENGINE["updater"] = updater
        _GRAPH_ENGINE["reservations"] = reservations
        _GRAPH_ENGINE["iface"] = iface

    return _GRAPH_ENGINE


class IncidentPayload(BaseModel):
    source: str
    target: str
    flag: str = "blocked"
    severity: float = 1.0


class ReoptimizePayload(BaseModel):
    num_particles: int = 30
    max_iterations: int = 50
    seed: int = 42


@app.post("/api/qdfro-graph/sioux-falls")
def init_sioux_falls():
    """Initializes Sioux Falls network with equilibrium MSA traffic assignment."""
    engine = _get_or_init_graph()
    graph = engine["graph"]

    # Initial solver run for fleet vehicles
    solver = QPSOSolver(engine["iface"], num_particles=20, max_iterations=30)
    job_nodes = [("10", 15.0), ("15", 20.0), ("20", 25.0), ("24", 30.0)]
    vehicles = [
        ("V1", "1", "1", 50.0),
        ("V2", "1", "1", 60.0),
    ]
    routes = solver.solve(job_nodes, vehicles)
    for r in routes.values():
        engine["updater"].register_route(r)
    engine["routes"] = routes

    return {
        "status": "success",
        "nodes": len(graph.nodes()),
        "edges": len(graph.edges()),
        "vehicles": list(routes.keys())
    }


@app.post("/api/qdfro-graph/incident")
def trigger_graph_incident(payload: IncidentPayload):
    """Triggers dynamic road incident and returns affected vehicle set."""
    engine = _get_or_init_graph()
    updater = engine["updater"]

    events = updater.apply_incident((payload.source, payload.target), flag=payload.flag, severity=payload.severity)
    affected = engine["iface"].notify_events(events)

    return {
        "status": "incident_applied",
        "events": [
            {
                "edge": evt.edge,
                "event_type": evt.event_type,
                "old_weight": evt.old_weight,
                "new_weight": evt.new_weight,
                "is_blocked": evt.is_blocked
            }
            for evt in events
        ],
        "affected_vehicles": list(affected)
    }


@app.post("/api/qdfro-graph/reoptimize")
def reoptimize_graph_fleet(payload: ReoptimizePayload):
    """Re-optimizes fleet routes using GraphQPSOInterface."""
    engine = _get_or_init_graph()
    iface = engine["iface"]

    solver = QPSOSolver(
        iface,
        num_particles=payload.num_particles,
        max_iterations=payload.max_iterations,
        seed=payload.seed
    )
    job_nodes = [("10", 15.0), ("15", 20.0), ("20", 25.0), ("24", 30.0)]
    vehicles = [
        ("V1", "1", "1", 50.0),
        ("V2", "1", "1", 60.0),
    ]
    routes = solver.solve(job_nodes, vehicles)
    for r in routes.values():
        engine["updater"].register_route(r)
    engine["routes"] = routes

    return {
        "status": "reoptimized",
        "routes": {v_id: r.to_dict() for v_id, r in routes.items()}
    }


@app.get("/api/qdfro-graph/metrics")
def get_graph_metrics():
    """Returns concrete quantitative evaluation metrics from the graph model."""
    engine = _get_or_init_graph()
    graph = engine["graph"]
    reservations = engine["reservations"]

    saturations = [e.volume_vph / max(1.0, e.capacity_vph) for e in graph.edges()]
    min_sat = min(saturations) if saturations else 0.0
    max_sat = max(saturations) if saturations else 0.0
    mean_sat = sum(saturations) / len(saturations) if saturations else 0.0

    reservations.clear()
    for r in engine["routes"].values():
        reservations.add_route_reservation(r, graph)

    conflicts = reservations.detect_conflicts()
    penalty = reservations.calculate_conflict_penalty(conflicts)

    return {
        "link_saturation": {
            "min": round(min_sat, 4),
            "max": round(max_sat, 4),
            "mean": round(mean_sat, 4),
        },
        "spacetime": {
            "conflict_count": len(conflicts),
            "penalty_score": round(penalty, 2),
            "conflicts": [
                {
                    "type": c.conflict_type,
                    "location": c.location,
                    "vehicles": c.vehicle_ids,
                    "time_slice": c.time_slice
                }
                for c in conflicts
            ]
        },
        "active_vehicles": len(engine["routes"])
    }


@app.get("/api/qdfro-graph/geojson")
def get_graph_geojson():
    """Returns standard GeoJSON FeatureCollection of nodes, dynamic edges, and vehicle routes."""
    engine = _get_or_init_graph()
    graph = engine["graph"]
    active_routes = list(engine["routes"].values())
    return graph.to_geojson(active_routes=active_routes)
