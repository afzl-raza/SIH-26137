import sys
import os

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
from models import OptimizationConfig
from problem_generator import generate_synthetic_scenario
from decoder import chromosome_from_job_orders, decode_random_keys
from optimizers.qpso import QPSOOptimizer
from route_cache import get_route_matrix

FAST = OptimizationConfig(population_size=8, max_iterations=8, seed=5)


def _scenario():
    return generate_synthetic_scenario(num_nodes=20, num_jobs=7, num_vehicles=2, seed=5)


def test_job_orders_round_trip_through_the_decoder():
    scenario = _scenario()
    dist, tm, paths = get_route_matrix(scenario).as_tuple()
    orders = {scenario.vehicles[0].id: [scenario.jobs[i].id for i in (0, 2, 4)],
              scenario.vehicles[1].id: [scenario.jobs[i].id for i in (6, 1, 3, 5)]}

    keys = chromosome_from_job_orders(orders, scenario)
    routes = decode_random_keys(keys, scenario, dist, tm, paths)

    assert {r.vehicle_id: r.job_ids for r in routes} == orders


def test_plan_that_does_not_fit_the_scenario_is_rejected():
    scenario = _scenario()
    with pytest.raises(ValueError):
        chromosome_from_job_orders({scenario.vehicles[0].id: [scenario.jobs[0].id]}, scenario)
    with pytest.raises(ValueError):
        chromosome_from_job_orders({999: [j.id for j in scenario.jobs]}, scenario)


def test_warm_start_never_ends_worse_than_the_plan_it_started_from():
    scenario = _scenario()
    optimizer = QPSOOptimizer()
    first = optimizer.optimize(scenario, FAST)
    plan = {r.vehicle_id: list(r.job_ids) for r in first.routes}

    warm = optimizer.optimize(scenario, FAST.model_copy(update={"seed": 99}), warm_start=plan)

    assert warm.warm_started is True
    # The previous plan is one initial particle, so the best-so-far can't be
    # worse than it (same scenario here, so its cost is unchanged).
    assert warm.total_cost <= first.total_cost + 1e-9


def test_cold_run_is_unchanged_by_the_warm_start_option_existing():
    scenario = _scenario()
    a = QPSOOptimizer().optimize(scenario, FAST)
    b = QPSOOptimizer().optimize(scenario, FAST, warm_start=None)
    assert a.warm_started is False and b.warm_started is False
    assert a.total_cost == b.total_cost
    assert [r.job_ids for r in a.routes] == [r.job_ids for r in b.routes]


def test_unusable_plan_falls_back_to_a_cold_start():
    scenario = _scenario()
    result = QPSOOptimizer().optimize(scenario, FAST, warm_start={999: [1, 2]})
    assert result.warm_started is False


def test_optimize_endpoint_accepts_warm_start_routes():
    client = TestClient(main_module.app)
    gen = client.post("/api/problem/generate", json={
        "source": "synthetic", "num_nodes": 20, "num_jobs": 7, "num_vehicles": 2, "seed": 5
    }).json()
    config = {"algorithm": "qpso", "population_size": 8, "max_iterations": 8, "seed": 5}

    first = client.post("/api/optimize", json={"scenario_id": gen["scenario_id"], "config": config}).json()
    assert first["warm_started"] is False

    plan = {str(r["vehicle_id"]): r["job_ids"] for r in first["routes"]}
    second = client.post("/api/optimize", json={
        "scenario_id": gen["scenario_id"], "config": config, "warm_start_routes": plan
    }).json()
    assert second["warm_started"] is True
    assert second["total_cost"] <= first["total_cost"] + 1e-9
