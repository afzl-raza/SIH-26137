"""Phase 7, Objective 4 - scalability experiment.

Measures actual matrix-construction time and QPSO runtime on synthetic
networks of increasing size. Node counts are the ones requested by Phase 7
(100, 250, 500, 1000, 2500); any size that fails or takes unreasonably long
is recorded honestly rather than omitted or faked.

GA/PSO/Greedy are intentionally excluded here (see Phase 7 Objective 4) to
keep this experiment's cost bounded - E1/E3 already benchmark all four
algorithms together on smaller synthetic scenarios.

Usage (from backend/):
    python -m experiments.phase7_validation.run_scalability

Writes experiments/phase7_validation/scalability_results.csv.
"""
from __future__ import annotations

import csv
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models import OptimizationConfig
from problem_generator import generate_synthetic_scenario, compute_route_matrix, terminal_nodes
from optimizers.qpso import QPSOOptimizer

NODE_COUNTS = [100, 250, 500, 1000, 2500]
JOBS_PER_NODE_RATIO = 0.3
JOBS_PER_VEHICLE = 8.0
SEED = 42
SOLVER_CONFIG = OptimizationConfig(algorithm="qpso", population_size=30, max_iterations=50, seed=SEED)

FIELDNAMES = [
    "num_nodes", "num_edges", "num_jobs", "num_vehicles", "seed",
    "matrix_build_time_s", "qpso_runtime_s", "total_optimization_time_s",
    "peak_memory_mb", "total_cost", "is_feasible", "constraint_violations",
    "status", "error",
]


def run_one(num_nodes: int) -> dict:
    num_jobs = max(1, int(num_nodes * JOBS_PER_NODE_RATIO))
    num_vehicles = max(1, round(num_jobs / JOBS_PER_VEHICLE))
    row = {
        "num_nodes": num_nodes, "num_jobs": num_jobs, "num_vehicles": num_vehicles,
        "seed": SEED, "status": "ok", "error": "",
    }
    try:
        scenario = generate_synthetic_scenario(
            num_nodes=num_nodes, num_jobs=num_jobs, num_vehicles=num_vehicles, seed=SEED
        )
        row["num_edges"] = len(scenario.edges)

        tracemalloc.start()
        t0 = time.perf_counter()
        compute_route_matrix(scenario, terminal_nodes(scenario))
        matrix_build_time_s = time.perf_counter() - t0

        optimizer = QPSOOptimizer()
        t0 = time.perf_counter()
        result = optimizer.optimize(scenario, SOLVER_CONFIG)
        qpso_runtime_s = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        row.update({
            "matrix_build_time_s": round(matrix_build_time_s, 4),
            "qpso_runtime_s": round(qpso_runtime_s, 4),
            "total_optimization_time_s": round(matrix_build_time_s + qpso_runtime_s, 4),
            "peak_memory_mb": round(peak / (1024 * 1024), 2),
            "total_cost": result.total_cost,
            "is_feasible": all(r.capacity_exceeded == 0 and r.time_exceeded == 0 for r in result.routes),
            "constraint_violations": sum(1 for r in result.routes if r.capacity_exceeded > 0 or r.time_exceeded > 0),
        })
    except Exception as e:  # noqa: BLE001 - record the real limitation, don't fabricate a pass
        tracemalloc.stop() if tracemalloc.is_tracing() else None
        row["status"] = "failed"
        row["error"] = str(e)[:300]
    return row


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in NODE_COUNTS:
        print(f"Running scalability at {n} nodes ...")
        t0 = time.perf_counter()
        row = run_one(n)
        wall = time.perf_counter() - t0
        print(f"  status={row['status']} wall_time_s={wall:.2f} "
              f"matrix={row.get('matrix_build_time_s')} qpso={row.get('qpso_runtime_s')}")
        rows.append(row)

    with (out_dir / "scalability_results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDNAMES})
    print(f"Wrote {out_dir / 'scalability_results.csv'}")


if __name__ == "__main__":
    main()
