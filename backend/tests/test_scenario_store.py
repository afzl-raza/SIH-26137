"""Tests for the server-side scenario store and the scenario_id API flow."""
import os
import sys
import threading
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
from models import OptimizationConfig
from optimizers.qpso import QPSOOptimizer
from problem_generator import generate_synthetic_scenario
from realdata.scenario_store import (
    ScenarioStore,
    ScenarioNotFoundError,
    SCENARIO_STORE,
)

client = TestClient(main_module.app)


def _scenario(**kw):
    params = dict(num_nodes=15, num_jobs=6, num_vehicles=2, seed=3)
    params.update(kw)
    return generate_synthetic_scenario(**params)


# ============================================================ store: basics

def test_create_returns_id_that_embeds_the_existing_scenario_hash():
    store = ScenarioStore()
    s = _scenario()
    record = store.create(s)

    assert record.scenario_id.startswith(s.scenario_hash)
    assert record.scenario_hash == s.scenario_hash
    assert record.data_source == "synthetic"
    assert len(store) == 1


def test_two_creates_with_identical_parameters_get_distinct_ids():
    """Same generation parameters produce the same scenario_hash by design.
    They must still occupy separate slots, or one client's traffic incident
    would silently rewrite another client's scenario."""
    store = ScenarioStore()
    a = store.create(_scenario())
    b = store.create(_scenario())

    assert a.scenario_hash == b.scenario_hash
    assert a.scenario_id != b.scenario_id
    assert len(store) == 2


def test_get_returns_the_stored_scenario():
    store = ScenarioStore()
    s = _scenario()
    record = store.create(s)

    fetched = store.get(record.scenario_id)
    assert fetched.scenario_id == record.scenario_id
    assert len(fetched.scenario.nodes) == len(s.nodes)
    assert len(fetched.scenario.edges) == len(s.edges)


def test_get_unknown_id_raises():
    store = ScenarioStore()
    with pytest.raises(ScenarioNotFoundError):
        store.get("does-not-exist")


def test_update_replaces_scenario_and_keeps_identity():
    store = ScenarioStore()
    record = store.create(_scenario())
    original_created = record.created_at

    changed = record.scenario.model_copy(deep=True)
    changed.edges[0].traffic_factor = 3.5
    changed.edges[0].current_travel_time = changed.edges[0].base_travel_time * 3.5

    time.sleep(0.01)
    updated = store.update(record.scenario_id, changed)

    assert updated.scenario_id == record.scenario_id
    assert updated.created_at == original_created
    assert updated.updated_at > original_created
    assert store.get(record.scenario_id).scenario.edges[0].traffic_factor == 3.5


def test_update_unknown_id_raises():
    store = ScenarioStore()
    with pytest.raises(ScenarioNotFoundError):
        store.update("nope", _scenario())


# ========================================================= store: isolation

def test_mutating_the_caller_object_after_create_does_not_touch_the_store():
    store = ScenarioStore()
    s = _scenario()
    record = store.create(s)

    s.edges[0].traffic_factor = 9.9  # caller keeps fiddling with its own copy

    assert store.get(record.scenario_id).scenario.edges[0].traffic_factor == 1.0


def test_updating_one_scenario_does_not_affect_another():
    store = ScenarioStore()
    a = store.create(_scenario(seed=1))
    b = store.create(_scenario(seed=2))

    changed = a.scenario.model_copy(deep=True)
    changed.edges[0].traffic_factor = 4.0
    store.update(a.scenario_id, changed)

    assert store.get(a.scenario_id).scenario.edges[0].traffic_factor == 4.0
    assert store.get(b.scenario_id).scenario.edges[0].traffic_factor == 1.0


# ======================================================= store: TTL and cap

def test_expired_entries_are_dropped():
    store = ScenarioStore(ttl_seconds=0.05)
    record = store.create(_scenario())
    assert store.get(record.scenario_id) is not None

    time.sleep(0.1)
    with pytest.raises(ScenarioNotFoundError):
        store.get(record.scenario_id)


def test_store_is_capped_and_evicts_least_recently_updated():
    store = ScenarioStore(max_entries=3)
    ids = []
    for seed in range(5):
        ids.append(store.create(_scenario(seed=seed)).scenario_id)
        time.sleep(0.001)

    assert len(store) <= 3
    # The most recent survive; the oldest are gone.
    assert ids[-1] in store.ids()
    with pytest.raises(ScenarioNotFoundError):
        store.get(ids[0])


def test_concurrent_create_and_get_are_safe():
    """FastAPI runs sync endpoints in a threadpool, so the store really is
    touched concurrently."""
    store = ScenarioStore(max_entries=500)
    s = _scenario()
    errors = []

    def worker():
        try:
            for _ in range(20):
                rec = store.create(s)
                store.get(rec.scenario_id)
        except Exception as exc:  # pragma: no cover - only on a real race
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(store) == 160


# ============================================================== API: id flow

def test_generate_returns_envelope_with_scenario_id():
    response = client.post("/api/problem/generate", json={
        "num_nodes": 15, "num_jobs": 6, "num_vehicles": 2, "seed": 3
    })
    assert response.status_code == 200
    body = response.json()

    assert body["scenario_id"]
    assert body["scenario_hash"]
    assert body["data_source"] == "synthetic"
    assert body["node_count"] == 15
    assert body["job_count"] == 6
    assert body["vehicle_count"] == 2
    assert body["edge_count"] == len(body["scenario"]["edges"])
    # The scenario itself is still returned - the frontend needs it to draw.
    assert len(body["scenario"]["nodes"]) == 15


def _generate(**kw):
    params = {"num_nodes": 15, "num_jobs": 6, "num_vehicles": 2, "seed": 3}
    params.update(kw)
    return client.post("/api/problem/generate", json=params).json()


def test_generate_rejects_demand_min_above_demand_max():
    response = client.post("/api/problem/generate", json={
        "num_nodes": 15, "num_jobs": 6, "num_vehicles": 2, "seed": 3,
        "demand_min": 20.0, "demand_max": 5.0
    })
    assert response.status_code == 400


def test_generate_applies_demand_range_and_capacity_override():
    body = _generate(demand_min=9.0, demand_max=9.0, vehicle_capacity_override=42.0)
    scenario = body["scenario"]

    assert all(job["demand"] == 9.0 for job in scenario["jobs"])
    assert all(v["capacity"] == 42.0 for v in scenario["vehicles"])


def test_optimize_accepts_scenario_id():
    body = _generate()
    response = client.post("/api/optimize", json={
        "scenario_id": body["scenario_id"],
        "config": {"algorithm": "qpso", "population_size": 8, "max_iterations": 5, "seed": 3},
    })
    assert response.status_code == 200
    assert response.json()["total_cost"] > 0


def test_optimize_rejects_unknown_scenario_id():
    response = client.post("/api/optimize", json={
        "scenario_id": "nonexistent-id",
        "config": {"algorithm": "qpso", "population_size": 5, "max_iterations": 2},
    })
    assert response.status_code == 404
    assert "Unknown scenario_id" in response.json()["detail"]


def test_optimize_requires_a_scenario_reference():
    response = client.post("/api/optimize", json={
        "config": {"algorithm": "qpso", "population_size": 5, "max_iterations": 2},
    })
    assert response.status_code == 422


def test_scenario_id_takes_precedence_over_inline_scenario():
    """Both supplied: the stored scenario must win. The two scenarios have
    different vehicle counts, so the route count reveals which one was used."""
    stored = _generate(num_vehicles=2)
    inline = generate_synthetic_scenario(num_nodes=15, num_jobs=6, num_vehicles=5, seed=7)

    response = client.post("/api/optimize", json={
        "scenario_id": stored["scenario_id"],
        "scenario": inline.model_dump(),
        "config": {"algorithm": "greedy"},
    })
    assert response.status_code == 200
    assert len(response.json()["routes"]) == 2


def test_traffic_update_by_id_persists_server_side():
    body = _generate()
    scenario_id = body["scenario_id"]
    edge = body["scenario"]["edges"][0]

    response = client.post("/api/traffic/update", json={
        "scenario_id": scenario_id,
        "updates": [{
            "source": edge["source"],
            "destination": edge["destination"],
            "traffic_factor": 3.5,
        }],
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_id"] == scenario_id
    assert payload["updated_edges"] >= 1

    # The change must be visible to a later call that only sends the id.
    stored = SCENARIO_STORE.get(scenario_id).scenario
    changed = [e for e in stored.edges
               if (e.source, e.destination) == (edge["source"], edge["destination"])]
    assert changed and changed[0].traffic_factor == 3.5
    assert changed[0].current_travel_time > edge["current_travel_time"]


def test_benchmark_and_evaluate_accept_scenario_id():
    body = _generate()
    scenario_id = body["scenario_id"]
    config = {"algorithm": "qpso", "population_size": 6, "max_iterations": 4, "seed": 3}

    bench = client.post("/api/benchmark", json={"scenario_id": scenario_id, "config": config})
    assert bench.status_code == 200
    # 6 jobs is within the exact solver's cap, so it's expected here too.
    assert set(bench.json()["results"].keys()) == {"greedy", "pso", "ga", "qpso", "qpso_ls", "exact"}

    routes = bench.json()["results"]["qpso"]["routes"]
    ev = client.post("/api/evaluate", json={
        "scenario_id": scenario_id,
        "routes": routes,
        "weights": {"alpha": 2.0, "beta": 0.1, "gamma": 3.0, "penalty_weight": 500.0},
    })
    assert ev.status_code == 200
    assert ev.json()["total_cost"] > 0


# ================================================== API: backward compatible

def test_legacy_inline_scenario_still_works_for_every_endpoint():
    """The pre-Phase-2 request format must keep working during the migration."""
    scenario = generate_synthetic_scenario(num_nodes=12, num_jobs=5, num_vehicles=2, seed=4)
    dumped = scenario.model_dump()
    config = {"algorithm": "greedy"}

    opt = client.post("/api/optimize", json={"scenario": dumped, "config": config})
    assert opt.status_code == 200
    assert opt.json()["total_cost"] > 0

    bench = client.post("/api/benchmark", json={
        "scenario": dumped,
        "config": {"algorithm": "qpso", "population_size": 5, "max_iterations": 3, "seed": 4},
    })
    assert bench.status_code == 200

    traffic = client.post("/api/traffic/update", json={
        "scenario": dumped,
        "updates": [{
            "source": dumped["edges"][0]["source"],
            "destination": dumped["edges"][0]["destination"],
            "traffic_factor": 2.5,
        }],
    })
    assert traffic.status_code == 200
    assert traffic.json()["scenario_id"] is None
    assert traffic.json()["data_source"] == "inline"
    assert traffic.json()["scenario"]["edges"][0]["traffic_factor"] == 2.5

    result = QPSOOptimizer().optimize(
        scenario, OptimizationConfig(population_size=5, max_iterations=3, seed=4))
    ev = client.post("/api/evaluate", json={
        "scenario": dumped,
        "routes": [r.model_dump() for r in result.routes],
        "weights": {"alpha": 1.0, "beta": 0.5, "gamma": 1.0, "penalty_weight": 1000.0},
    })
    assert ev.status_code == 200
