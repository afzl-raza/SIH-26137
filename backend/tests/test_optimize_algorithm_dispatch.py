"""POST /api/optimize resolves `config.algorithm` (a free-text string) to a
concrete optimizer via substring matching in main.py. These tests pin down
that every distinct algorithm name reaches the optimizer it names -
including `qpso_memetic`, which a plain `"qpso" in algo` check would
otherwise resolve to plain QPSOOptimizer since "qpso_memetic" contains
"qpso" as a substring (a real, reproduced bug: fixed by checking for
"memetic" before the generic "qpso" branch)."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient

import main as main_module
from problem_generator import generate_synthetic_scenario

client = TestClient(main_module.app)


def _optimize(algorithm):
    scenario = generate_synthetic_scenario(num_nodes=10, num_jobs=4, num_vehicles=2, seed=1)
    payload = {
        "scenario": scenario.model_dump(),
        "config": {"algorithm": algorithm, "population_size": 5, "max_iterations": 3, "seed": 1},
    }
    response = client.post("/api/optimize", json=payload)
    assert response.status_code == 200
    return response.json()["algorithm"]


def test_qpso_memetic_dispatches_to_memetic_optimizer_not_plain_qpso():
    """Regression test: `algorithm="qpso_memetic"` must run
    MemeticQPSOOptimizer ("QPSO + Local Search (Memetic)"), not plain
    QPSOOptimizer ("QPSO (Quantum-behaved PSO)...") - before the fix, the
    generic `"qpso" in algo` branch matched first and silently ran the
    wrong solver."""
    result_algo = _optimize("qpso_memetic")
    assert "Memetic" in result_algo
    assert result_algo == "QPSO + Local Search (Memetic)"


def test_plain_qpso_still_dispatches_to_plain_qpso():
    """The fix must not disturb the existing, correct `qpso` resolution."""
    result_algo = _optimize("qpso")
    assert "Memetic" not in result_algo
    assert result_algo.startswith("QPSO (Quantum-behaved PSO)")


def test_exact_still_takes_priority_over_qpso_substring_checks():
    """`exact` is checked first regardless of any future qpso-family
    additions; small scenario stays within the exact solver's <=10 job cap."""
    assert _optimize("exact") == "Exact (Optimal)"


def test_unknown_algorithm_name_falls_back_to_qpso():
    """Documented fallback behaviour, unchanged by this fix."""
    result_algo = _optimize("not-a-real-algorithm")
    assert result_algo.startswith("QPSO (Quantum-behaved PSO)")
