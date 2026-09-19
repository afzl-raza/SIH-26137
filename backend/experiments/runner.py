"""Q-DFRO experiment runner.

Implements experiments E1-E6 from Engineering.md Sec.9 / Task.md Phase 8.
Each experiment writes its own frozen config.json (so a run's parameters are
always traceable) plus raw/processed output, under <repo_root>/experiments/.

Uses only the Python stdlib (json, csv) for output - no new dependency is
introduced (see Agent.md rule #7, minimal dependencies).

Run all experiments from `backend/`:

    python -m experiments.runner --experiment all
"""
import argparse
import csv
import json
import time
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from models import OptimizationConfig
from problem_generator import generate_synthetic_scenario
from optimizers.benchmark import run_benchmark
from optimizers.qpso import QPSOOptimizer

from experiments.config import (
    ScenarioSpec,
    DEFAULT_SCENARIO,
    DEFAULT_SOLVER_CONFIG,
    E3_SOLVER_CONFIG,
)


def _default_output_root() -> Path:
    # backend/experiments/runner.py -> backend/experiments -> backend -> repo root
    return Path(__file__).resolve().parents[2] / "experiments"


def _resolve_output_dir(output_root: Optional[Path], name: str) -> Path:
    root = Path(output_root) if output_root is not None else _default_output_root()
    out_dir = root / name
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _write_frozen_config(out_dir: Path, config_dict: dict) -> None:
    """Writes config.json on first run. On a later run into the same folder,
    raises if the configuration differs - protects experiment evidence from
    being silently overwritten by a differently-configured run."""
    config_path = out_dir / "config.json"
    if config_path.exists():
        existing = json.loads(config_path.read_text())
        if existing != config_dict:
            raise RuntimeError(
                f"'{out_dir.name}' already has a frozen config.json with "
                f"different parameters. Delete {out_dir} first if you intend "
                f"to re-run this experiment with new parameters."
            )
    else:
        config_path.write_text(json.dumps(config_dict, indent=2))


def run_e1_algorithm_comparison(
    scenario_spec: ScenarioSpec = DEFAULT_SCENARIO,
    solver_config: OptimizationConfig = None,
    output_root: Optional[Path] = None,
) -> dict:
    """E1 - Solution quality: Greedy/PSO/GA/QPSO on one identical scenario."""
    solver_config = solver_config or DEFAULT_SOLVER_CONFIG
    out_dir = _resolve_output_dir(output_root, "E1_algorithm_comparison")

    config_dict = {
        "scenario": scenario_spec.as_dict(),
        "solver": solver_config.model_dump(),
    }
    _write_frozen_config(out_dir, config_dict)

    scenario = generate_synthetic_scenario(**scenario_spec.as_dict())
    benchmark_result = run_benchmark(scenario, solver_config)

    raw = {key: result.model_dump() for key, result in benchmark_result.results.items()}
    (out_dir / "raw_results.json").write_text(json.dumps(raw, indent=2))

    fieldnames = ["algorithm_key", "algorithm", "total_cost", "total_travel_time",
                  "total_distance", "runtime_ms", "constraint_violations", "is_feasible"]
    with (out_dir / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for key, result in benchmark_result.results.items():
            writer.writerow({
                "algorithm_key": key,
                "algorithm": result.algorithm,
                "total_cost": result.total_cost,
                "total_travel_time": result.total_travel_time,
                "total_distance": result.total_distance,
                "runtime_ms": result.runtime_ms,
                "constraint_violations": result.constraint_violations,
                "is_feasible": result.is_feasible,
            })

    return raw


def run_e2_convergence(
    scenario_spec: ScenarioSpec = DEFAULT_SCENARIO,
    solver_config: OptimizationConfig = None,
    output_root: Optional[Path] = None,
    raw_results: Optional[dict] = None,
) -> None:
    """E2 - Convergence: best-cost-per-iteration for PSO/GA/QPSO (Greedy has
    no iterative convergence history). Reuses E1's results if provided,
    otherwise runs E1 itself so this can be called standalone."""
    solver_config = solver_config or DEFAULT_SOLVER_CONFIG
    out_dir = _resolve_output_dir(output_root, "E2_convergence")

    if raw_results is None:
        raw_results = run_e1_algorithm_comparison(scenario_spec, solver_config, output_root)

    with (out_dir / "convergence.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["algorithm", "iteration", "best_cost"])
        for key in ("pso", "ga", "qpso"):
            history = raw_results.get(key, {}).get("convergence_history", [])
            for iteration, best_cost in enumerate(history):
                writer.writerow([key, iteration, best_cost])


def run_e3_scalability(
    node_counts: Iterable[int] = (20, 50, 100, 200),
    jobs_per_node_ratio: float = 0.5,
    jobs_per_vehicle: float = 5.0,
    seed: int = 42,
    solver_config: OptimizationConfig = None,
    output_root: Optional[Path] = None,
) -> list:
    """E3 - Scalability: runtime and cost as the network grows. Uses a
    reduced solver budget (E3_SOLVER_CONFIG) so a 4-algorithm sweep across
    several sizes completes in reasonable time - never compare these costs
    directly against E1's full-budget numbers.

    Fleet size scales with job count (jobs_per_vehicle, matching the default
    demo's ~5 jobs/vehicle ratio) rather than staying fixed. A fixed vehicle
    count was tried first and produced exploding "infeasible" costs at 100+
    nodes - not because the optimizers got worse, but because a fixed-size
    fleet becomes structurally unable to serve a growing job list within
    max_route_time. That measures fleet undersizing, not scalability, so the
    fleet is kept proportional to isolate the actual variable of interest.
    """
    solver_config = solver_config or E3_SOLVER_CONFIG
    node_counts = list(node_counts)
    out_dir = _resolve_output_dir(output_root, "E3_scalability")

    config_dict = {
        "node_counts": node_counts,
        "jobs_per_node_ratio": jobs_per_node_ratio,
        "jobs_per_vehicle": jobs_per_vehicle,
        "seed": seed,
        "solver": solver_config.model_dump(),
        "note": ("Uses a reduced solver budget relative to E1 so the sweep "
                  "completes in reasonable time; do not compare these costs "
                  "directly against E1's. Vehicle count scales with job count "
                  "(jobs_per_vehicle) so the fleet stays large enough to "
                  "remain feasible as the problem grows - this experiment "
                  "measures optimizer scalability, not fleet sizing."),
    }
    _write_frozen_config(out_dir, config_dict)

    rows = []
    for num_nodes in node_counts:
        num_jobs = max(1, int(num_nodes * jobs_per_node_ratio))
        num_vehicles = max(1, round(num_jobs / jobs_per_vehicle))
        scenario = generate_synthetic_scenario(
            num_nodes=num_nodes, num_jobs=num_jobs, num_vehicles=num_vehicles, seed=seed
        )
        benchmark_result = run_benchmark(scenario, solver_config)
        for algo_key, result in benchmark_result.results.items():
            rows.append({
                "num_nodes": num_nodes,
                "num_jobs": num_jobs,
                "algorithm": algo_key,
                "total_cost": result.total_cost,
                "runtime_ms": result.runtime_ms,
                "is_feasible": result.is_feasible,
            })

    fieldnames = ["num_nodes", "num_jobs", "algorithm", "total_cost", "runtime_ms", "is_feasible"]
    with (out_dir / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def _pick_active_route_edge(routes):
    for route in routes:
        if len(route.node_path) >= 2:
            return route.node_path[0], route.node_path[1]
    return None


def run_e4_traffic_disruption(
    scenario_spec: ScenarioSpec = DEFAULT_SCENARIO,
    solver_config: OptimizationConfig = None,
    congestion_factor: float = 3.5,
    output_root: Optional[Path] = None,
) -> dict:
    """E4 - Traffic disruption: before/after cost and re-optimization runtime
    when an active-route edge gets congested, matching the live demo."""
    solver_config = solver_config or DEFAULT_SOLVER_CONFIG
    out_dir = _resolve_output_dir(output_root, "E4_traffic_disruption")

    config_dict = {
        "scenario": scenario_spec.as_dict(),
        "solver": solver_config.model_dump(),
        "congestion_factor": congestion_factor,
    }
    _write_frozen_config(out_dir, config_dict)

    scenario = generate_synthetic_scenario(**scenario_spec.as_dict())
    optimizer = QPSOOptimizer()

    before = optimizer.optimize(scenario, solver_config)
    before_vehicle_jobs = {r.vehicle_id: list(r.job_ids) for r in before.routes}

    target_edge = _pick_active_route_edge(before.routes)
    if target_edge is None and scenario.edges:
        target_edge = (scenario.edges[0].source, scenario.edges[0].destination)

    for edge in scenario.edges:
        if (edge.source, edge.destination) == target_edge or \
           (edge.destination, edge.source) == target_edge:
            edge.traffic_factor = congestion_factor
            edge.current_travel_time = edge.base_travel_time * congestion_factor

    start = time.perf_counter()
    after = optimizer.optimize(scenario, solver_config)
    reoptimization_runtime_ms = (time.perf_counter() - start) * 1000.0

    after_vehicle_jobs = {r.vehicle_id: list(r.job_ids) for r in after.routes}
    changed_vehicle_ids = [
        vid for vid, jobs in after_vehicle_jobs.items()
        if before_vehicle_jobs.get(vid) != jobs
    ]

    result = {
        "target_edge": {"source": target_edge[0], "destination": target_edge[1]} if target_edge else None,
        "congestion_factor": congestion_factor,
        "before_cost": before.total_cost,
        "after_cost": after.total_cost,
        "reoptimization_runtime_ms": round(reoptimization_runtime_ms, 2),
        "changed_vehicle_ids": changed_vehicle_ids,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2))
    return result


def run_e5_traffic_severity(
    scenario_spec: ScenarioSpec = DEFAULT_SCENARIO,
    solver_config: OptimizationConfig = None,
    factors: Iterable[float] = (1.0, 1.5, 2.5, 3.5, 5.0),
    output_root: Optional[Path] = None,
) -> list:
    """E5 - Traffic severity: cost/runtime as one edge's congestion increases,
    holding everything else (including which edge) fixed across levels."""
    solver_config = solver_config or DEFAULT_SOLVER_CONFIG
    factors = list(factors)
    out_dir = _resolve_output_dir(output_root, "E5_traffic_severity")

    config_dict = {
        "scenario": scenario_spec.as_dict(),
        "solver": solver_config.model_dump(),
        "factors": factors,
    }
    _write_frozen_config(out_dir, config_dict)

    baseline_scenario = generate_synthetic_scenario(**scenario_spec.as_dict())
    optimizer = QPSOOptimizer()
    baseline = optimizer.optimize(baseline_scenario, solver_config)
    target_edge = _pick_active_route_edge(baseline.routes)
    if target_edge is None and baseline_scenario.edges:
        target_edge = (baseline_scenario.edges[0].source, baseline_scenario.edges[0].destination)

    rows = []
    for factor in factors:
        scenario = generate_synthetic_scenario(**scenario_spec.as_dict())
        for edge in scenario.edges:
            if (edge.source, edge.destination) == target_edge or \
               (edge.destination, edge.source) == target_edge:
                edge.traffic_factor = factor
                edge.current_travel_time = edge.base_travel_time * factor
        result = optimizer.optimize(scenario, solver_config)
        rows.append({
            "traffic_factor": factor,
            "total_cost": result.total_cost,
            "runtime_ms": result.runtime_ms,
            "is_feasible": result.is_feasible,
        })

    fieldnames = ["traffic_factor", "total_cost", "runtime_ms", "is_feasible"]
    with (out_dir / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def run_e6_reproducibility(
    scenario_spec: ScenarioSpec = DEFAULT_SCENARIO,
    solver_config: OptimizationConfig = None,
    seeds: Iterable[int] = (1, 2, 3, 4, 5),
    output_root: Optional[Path] = None,
) -> dict:
    """E6 - Reproducibility: mean/std/min/max of QPSO cost on one fixed
    scenario across several solver seeds."""
    base_config = solver_config or DEFAULT_SOLVER_CONFIG
    seeds = list(seeds)
    out_dir = _resolve_output_dir(output_root, "E6_reproducibility")

    config_dict = {
        "scenario": scenario_spec.as_dict(),
        "solver_base": base_config.model_dump(),
        "seeds": seeds,
        "note": "scenario is fixed; only the QPSO solver seed varies across runs",
    }
    _write_frozen_config(out_dir, config_dict)

    scenario = generate_synthetic_scenario(**scenario_spec.as_dict())
    optimizer = QPSOOptimizer()

    costs = []
    rows = []
    for seed in seeds:
        run_config = base_config.model_copy(update={"seed": seed})
        result = optimizer.optimize(scenario, run_config)
        costs.append(result.total_cost)
        rows.append({"seed": seed, "total_cost": result.total_cost, "runtime_ms": result.runtime_ms})

    with (out_dir / "raw_runs.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["seed", "total_cost", "runtime_ms"])
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "seeds_tested": len(seeds),
        "mean_cost": float(np.mean(costs)),
        "std_cost": float(np.std(costs)),
        "min_cost": float(np.min(costs)),
        "max_cost": float(np.max(costs)),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Q-DFRO experiment runner")
    parser.add_argument(
        "--experiment", required=True,
        choices=["e1", "e2", "e3", "e4", "e5", "e6", "all"]
    )
    args = parser.parse_args()

    raw_e1 = None

    if args.experiment in ("e1", "all"):
        print("Running E1 - algorithm comparison...")
        raw_e1 = run_e1_algorithm_comparison()
        print("  wrote experiments/E1_algorithm_comparison/")

    if args.experiment in ("e2", "all"):
        print("Running E2 - convergence...")
        run_e2_convergence(raw_results=raw_e1)
        print("  wrote experiments/E2_convergence/")

    if args.experiment in ("e3", "all"):
        print("Running E3 - scalability...")
        run_e3_scalability()
        print("  wrote experiments/E3_scalability/")

    if args.experiment in ("e4", "all"):
        print("Running E4 - traffic disruption...")
        run_e4_traffic_disruption()
        print("  wrote experiments/E4_traffic_disruption/")

    if args.experiment in ("e5", "all"):
        print("Running E5 - traffic severity...")
        run_e5_traffic_severity()
        print("  wrote experiments/E5_traffic_severity/")

    if args.experiment in ("e6", "all"):
        print("Running E6 - reproducibility...")
        run_e6_reproducibility()
        print("  wrote experiments/E6_reproducibility/")


if __name__ == "__main__":
    main()
