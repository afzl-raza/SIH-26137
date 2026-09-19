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
from problem_generator import generate_synthetic_scenario
from optimizers.greedy import GreedyOptimizer
from optimizers.pso import PSOOptimizer
from optimizers.qpso import QPSOOptimizer
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
    num_nodes: int = 30
    num_jobs: int = 15
    num_vehicles: int = 3
    seed: int = 42


class OptimizePayload(BaseModel):
    scenario: ProblemScenario
    config: OptimizationConfig


class TrafficPayload(BaseModel):
    scenario: ProblemScenario
    updates: List[TrafficUpdate]


class EvaluatePayload(BaseModel):
    scenario: ProblemScenario
    routes: List[VehicleRoute]
    weights: ObjectiveWeights


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
    return {"status": "ok", "app": "Q-DFRO Backend"}


@app.post("/api/problem/generate", response_model=ProblemScenario)
def generate_problem(req: GenerateRequest):
    try:
        scenario = generate_synthetic_scenario(
            num_nodes=req.num_nodes,
            num_jobs=req.num_jobs,
            num_vehicles=req.num_vehicles,
            seed=req.seed
        )
        return scenario
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/optimize", response_model=OptimizationResult)
def optimize_route(payload: OptimizePayload):
    try:
        algo = payload.config.algorithm.lower()
        if "qpso" in algo:
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

        result = optimizer.optimize(payload.scenario, payload.config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization error: {str(e)}")


@app.post("/api/traffic/update", response_model=ProblemScenario)
def update_traffic(payload: TrafficPayload):
    try:
        scenario = payload.scenario
        update_map = {(u.source, u.destination): u.traffic_factor for u in payload.updates}
        # Also map symmetric reverse directions
        for u in payload.updates:
            update_map[(u.destination, u.source)] = u.traffic_factor

        for edge in scenario.edges:
            pair = (edge.source, edge.destination)
            if pair in update_map:
                edge.traffic_factor = round(update_map[pair], 2)
                edge.current_travel_time = round(edge.base_travel_time * edge.traffic_factor, 2)

        return scenario
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/benchmark", response_model=BenchmarkResult)
def benchmark_scenario(payload: OptimizePayload):
    try:
        return run_benchmark(payload.scenario, payload.config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/evaluate", response_model=OptimizationResult)
def evaluate_routes(payload: EvaluatePayload):
    """Re-scores an already-computed set of routes against a new set of
    objective weights, without re-optimizing. Used for the live "what would
    this cost under different weights" preview - the score always comes
    from the same evaluator every optimizer uses, never computed client-side.
    """
    try:
        return evaluate_solution(payload.routes, payload.scenario, payload.weights, algorithm_name="preview")
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
