import functools
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
import main as main_module

client = TestClient(main_module.app)


def test_run_experiment_rejects_unknown_name():
    response = client.post("/api/experiments/not_a_real_experiment/run")
    assert response.status_code == 400


def test_run_experiment_e6_executes_real_runner_and_returns_result(tmp_path, monkeypatch):
    """Exercises the real E6 runner end to end via the live-run endpoint -
    same code path python -m experiments.runner uses, just triggered over
    HTTP. Redirects output_root to a temp directory so this doesn't
    overwrite the tracked experiments/E6_reproducibility/ evidence on every
    test run; get_experiment_results is patched to look there too since it
    otherwise reads from the real repo experiments/ directory.
    """
    real_runner = main_module.EXPERIMENT_RUNNERS["E6_reproducibility"]
    monkeypatch.setitem(
        main_module.EXPERIMENT_RUNNERS,
        "E6_reproducibility",
        functools.partial(real_runner, output_root=tmp_path),
    )
    monkeypatch.setattr(main_module, "EXPERIMENTS_ROOT", tmp_path)

    response = client.post("/api/experiments/E6_reproducibility/run")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "E6_reproducibility"
    assert "result" in body
    assert body["result"]["seeds_tested"] >= 1
    assert "mean_cost" in body["result"]

    assert (tmp_path / "E6_reproducibility" / "raw_runs.csv").exists()
