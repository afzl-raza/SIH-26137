import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
import main as main_module

client = TestClient(main_module.app)


def test_run_experiment_rejects_unknown_name():
    response = client.post("/api/experiments/not_a_real_experiment/run")
    assert response.status_code == 400


def test_run_experiment_e6_executes_real_runner_and_returns_result():
    """Exercises the real E6 runner end to end via the live-run endpoint -
    same code path python -m experiments.runner uses, just triggered over
    HTTP. Runs against the real experiments/ directory since E6's defaults
    are unchanged (frozen-config guard passes), so this legitimately
    refreshes real evidence rather than writing throwaway test output.
    """
    response = client.post("/api/experiments/E6_reproducibility/run")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "E6_reproducibility"
    assert "result" in body
    assert body["result"]["seeds_tested"] >= 1
    assert "mean_cost" in body["result"]
