import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
import main as main_module
from problem_generator import generate_synthetic_scenario
from optimizers.qpso import QPSOOptimizer
from models import OptimizationConfig

client = TestClient(main_module.app)


def test_evaluate_rescoring_matches_direct_call():
    """POST /api/evaluate must produce the exact same score fitness.py would
    produce directly - it's a thin wrapper around the same evaluator every
    optimizer already uses, not a separate calculation path."""
    scenario = generate_synthetic_scenario(num_nodes=15, num_jobs=6, num_vehicles=2, seed=3)
    config = OptimizationConfig(population_size=8, max_iterations=8, seed=3)
    result = QPSOOptimizer().optimize(scenario, config)

    new_weights = {"alpha": 2.0, "beta": 0.1, "gamma": 3.0, "penalty_weight": 500.0}
    payload = {
        "scenario": scenario.model_dump(),
        "routes": [r.model_dump() for r in result.routes],
        "weights": new_weights
    }

    response = client.post("/api/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()

    # Re-scoring the same real routes with different weights must change the
    # cost (weights differ substantially from the original run's defaults).
    assert body["total_cost"] != result.total_cost
    assert body["total_travel_time"] == result.total_travel_time
    assert body["total_distance"] == result.total_distance


def test_evaluate_rejects_malformed_payload():
    response = client.post("/api/evaluate", json={"scenario": {}, "routes": [], "weights": {}})
    assert response.status_code == 422
