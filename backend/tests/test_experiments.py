import sys
import os
import csv

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import OptimizationConfig
from experiments.config import ScenarioSpec
from experiments.runner import (
    run_e1_algorithm_comparison,
    run_e3_scalability,
    run_e4_traffic_disruption,
    run_e6_reproducibility,
)

# Small/fast scenario + solver budget so this whole test module stays quick;
# the "real" E1-E6 numbers are produced separately by running the CLI.
SMALL_SCENARIO = ScenarioSpec(num_nodes=12, num_jobs=5, num_vehicles=2, seed=7)
FAST_SOLVER = OptimizationConfig(population_size=6, max_iterations=6, seed=7)


def test_e1_writes_expected_files_and_schema(tmp_path):
    raw = run_e1_algorithm_comparison(SMALL_SCENARIO, FAST_SOLVER, output_root=tmp_path)

    out_dir = tmp_path / "E1_algorithm_comparison"
    assert (out_dir / "config.json").exists()
    assert (out_dir / "raw_results.json").exists()
    assert (out_dir / "results.csv").exists()

    assert set(raw.keys()) == {"greedy", "pso", "ga", "qpso", "qpso_memetic"}
    for result in raw.values():
        assert "total_cost" in result
        assert "runtime_ms" in result

    with (out_dir / "results.csv").open() as f:
        header = f.readline().strip().split(",")
    assert "algorithm_key" in header
    assert "total_cost" in header


def test_e3_scalability_small_sweep(tmp_path):
    rows = run_e3_scalability(
        node_counts=[10, 15],
        jobs_per_vehicle=5.0,
        seed=3,
        solver_config=FAST_SOLVER,
        output_root=tmp_path,
    )

    sizes_seen = {row["num_nodes"] for row in rows}
    assert sizes_seen == {10, 15}
    for row in rows:
        assert row["runtime_ms"] >= 0

    assert (tmp_path / "E3_scalability" / "config.json").exists()
    assert (tmp_path / "E3_scalability" / "results.csv").exists()


def test_e4_before_after_present(tmp_path):
    result = run_e4_traffic_disruption(SMALL_SCENARIO, FAST_SOLVER, output_root=tmp_path)

    assert "before_cost" in result
    assert "after_cost" in result
    assert result["reoptimization_runtime_ms"] >= 0
    assert (tmp_path / "E4_traffic_disruption" / "result.json").exists()


def test_e6_reproducibility_determinism_and_stats(tmp_path):
    summary = run_e6_reproducibility(
        SMALL_SCENARIO, FAST_SOLVER, seeds=[1, 1, 2], output_root=tmp_path
    )

    assert summary["seeds_tested"] == 3
    assert summary["min_cost"] <= summary["mean_cost"] <= summary["max_cost"]

    raw_path = tmp_path / "E6_reproducibility" / "raw_runs.csv"
    assert raw_path.exists()
    with raw_path.open() as f:
        rows = list(csv.DictReader(f))

    # Same seed (1) must produce an identical cost - QPSO is deterministic
    # given a seed, which is the entire premise of the reproducibility claim.
    seed1_costs = [row["total_cost"] for row in rows if row["seed"] == "1"]
    assert len(seed1_costs) == 2
    assert seed1_costs[0] == seed1_costs[1]


def test_experiment_config_frozen_guard(tmp_path):
    run_e1_algorithm_comparison(SMALL_SCENARIO, FAST_SOLVER, output_root=tmp_path)

    different_solver = OptimizationConfig(population_size=99, max_iterations=99, seed=7)
    with pytest.raises(RuntimeError):
        run_e1_algorithm_comparison(SMALL_SCENARIO, different_solver, output_root=tmp_path)


# --- GET /api/experiments/{name} ---

import main as main_module
from fastapi.testclient import TestClient


def test_experiments_endpoint_404_when_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "EXPERIMENTS_ROOT", tmp_path)
    client = TestClient(main_module.app)

    response = client.get("/api/experiments/E3_scalability")

    assert response.status_code == 404


def test_experiments_endpoint_200_with_data_when_run(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "EXPERIMENTS_ROOT", tmp_path)
    run_e3_scalability(
        node_counts=[8], jobs_per_vehicle=5.0, seed=1,
        solver_config=FAST_SOLVER, output_root=tmp_path
    )
    client = TestClient(main_module.app)

    response = client.get("/api/experiments/E3_scalability")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "E3_scalability"
    assert "config" in body
    assert "rows" in body


def test_experiments_endpoint_rejects_unknown_name():
    client = TestClient(main_module.app)
    response = client.get("/api/experiments/not_a_real_experiment")
    assert response.status_code == 400
