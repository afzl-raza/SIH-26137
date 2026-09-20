"""Phase 7, Objective 5 - reproducibility across all four algorithms.

For a fixed synthetic scenario (no external network calls - reproducibility
of the OPTIMIZER, isolated from geocoding/weather variability, which is
documented separately in validation_results.json), runs each algorithm twice
with the identical seed/config and compares cost, route assignments, node
paths, distance and travel time bit-for-bit.

Usage (from backend/):
    python -m experiments.phase7_validation.run_reproducibility

Writes experiments/phase7_validation/reproducibility_results.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import OptimizationConfig
from problem_generator import generate_synthetic_scenario
from optimizers.qpso import QPSOOptimizer
from optimizers.pso import PSOOptimizer
from optimizers.ga import GAOptimizer
from optimizers.greedy import GreedyOptimizer

SEED = 42
SCENARIO = dict(num_nodes=30, num_jobs=15, num_vehicles=3, seed=SEED)
CONFIG = OptimizationConfig(algorithm="qpso", population_size=40, max_iterations=100, seed=SEED)

ALGORITHMS = {
    "greedy": GreedyOptimizer,
    "pso": PSOOptimizer,
    "ga": GAOptimizer,
    "qpso": QPSOOptimizer,
}


def route_signature(result) -> list:
    return [
        {"vehicle_id": r.vehicle_id, "job_ids": r.job_ids, "node_path": r.node_path}
        for r in sorted(result.routes, key=lambda r: r.vehicle_id)
    ]


def run_twice(name: str, cls) -> dict:
    scenario_a = generate_synthetic_scenario(**SCENARIO)
    scenario_b = generate_synthetic_scenario(**SCENARIO)
    config = CONFIG.model_copy(update={"algorithm": name, "seed": SEED})

    optimizer_a = cls()
    t0 = time.perf_counter()
    result_a = optimizer_a.optimize(scenario_a, config)
    time_a = time.perf_counter() - t0

    optimizer_b = cls()
    t0 = time.perf_counter()
    result_b = optimizer_b.optimize(scenario_b, config)
    time_b = time.perf_counter() - t0

    sig_a = route_signature(result_a)
    sig_b = route_signature(result_b)

    convergence_a = getattr(result_a, "convergence_history", None)
    convergence_b = getattr(result_b, "convergence_history", None)

    return {
        "algorithm": name,
        "seed": SEED,
        "run_a": {"total_cost": result_a.total_cost, "total_travel_time": result_a.total_travel_time,
                   "total_distance": result_a.total_distance, "runtime_ms": round(time_a * 1000, 2)},
        "run_b": {"total_cost": result_b.total_cost, "total_travel_time": result_b.total_travel_time,
                   "total_distance": result_b.total_distance, "runtime_ms": round(time_b * 1000, 2)},
        "cost_identical": result_a.total_cost == result_b.total_cost,
        "travel_time_identical": result_a.total_travel_time == result_b.total_travel_time,
        "distance_identical": result_a.total_distance == result_b.total_distance,
        "route_assignments_identical": sig_a == sig_b,
        "convergence_history_identical": (convergence_a == convergence_b) if convergence_a is not None else None,
    }


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for name, cls in ALGORITHMS.items():
        print(f"Checking reproducibility of {name} ...")
        r = run_twice(name, cls)
        results.append(r)
        print(f"  cost_identical={r['cost_identical']} routes_identical={r['route_assignments_identical']}")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenario": SCENARIO,
        "note": (
            "Scenario is regenerated from the same seed for each run rather than "
            "reused in-memory, so this also validates that generate_synthetic_scenario "
            "itself is deterministic, not just the optimizer given a fixed scenario object."
        ),
        "results": results,
    }
    (out_dir / "reproducibility_results.json").write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_dir / 'reproducibility_results.json'}")


if __name__ == "__main__":
    main()
