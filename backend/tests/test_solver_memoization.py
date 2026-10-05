"""The solvers reuse work they would otherwise repeat (decoder.RouteMemo, the
local-search cost cache, the congestion cache). These tests pin that this is
purely a speed-up: the numbers must be exactly what the un-memoized code
produced.

The golden values below were captured from the code as it was BEFORE the
memoization was added (commit 80a29bf's solver), for fixed scenarios, budgets
and seeds. If a future change alters them, either the objective/solver changed
on purpose (update the pins and say so) or something broke.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from decoder import RouteMemo, decode_random_keys
from fitness import build_edge_map, evaluate_solution
from models import OptimizationConfig
from optimizers.ga import GAOptimizer
from optimizers.local_search import local_search_refine
from optimizers.pso import PSOOptimizer
from optimizers.qpso import QPSOOptimizer
from problem_generator import generate_synthetic_scenario
from realdata.conditions import apply_incidents
from route_cache import get_route_matrix


def _jobs(result):
    return [r.job_ids for r in result.routes]


def _scenario():
    return generate_synthetic_scenario(num_nodes=30, num_jobs=15, num_vehicles=3, seed=42)


# ----------------------------------------------------------- golden results

def test_qpso_local_search_matches_the_pre_memoization_result():
    r = QPSOOptimizer().optimize(
        _scenario(), OptimizationConfig(algorithm="qpso", population_size=40, max_iterations=100, seed=42))
    assert (r.total_cost, r.total_travel_time, r.total_distance) == (192.98, 162.84, 60.28)
    assert _jobs(r) == [[14, 13], [5, 6, 3, 7, 9, 11, 10], [2, 12, 1, 8, 15, 4]]
    assert len(r.convergence_history) == 100
    assert round(sum(r.convergence_history), 2) == 19957.23


def test_pso_matches_the_pre_memoization_result():
    r = PSOOptimizer().optimize(
        _scenario(), OptimizationConfig(algorithm="pso", population_size=40, max_iterations=100, seed=9))
    assert (r.total_cost, r.total_travel_time, r.total_distance) == (209.06, 173.89, 70.33)
    assert _jobs(r) == [[8, 15, 1, 12, 3, 6], [13, 7, 9, 11, 10], [4, 2, 5, 14]]
    assert round(sum(r.convergence_history), 2) == 21192.5


def test_ga_matches_the_pre_memoization_result():
    r = GAOptimizer().optimize(
        _scenario(), OptimizationConfig(algorithm="ga", population_size=40, max_iterations=100, seed=13))
    assert (r.total_cost, r.total_travel_time, r.total_distance) == (204.53, 170.45, 68.17)
    assert _jobs(r) == [[6, 3, 12, 4], [10, 11, 9, 7, 5], [1, 8, 15, 2, 13, 14]]
    assert round(sum(r.convergence_history), 2) == 21635.48


def test_qpso_with_a_traffic_incident_matches_the_pre_memoization_result():
    base = _scenario()
    edge = base.edges[3]
    scenario, _ = apply_incidents(base, {(edge.source, edge.destination): 4.0})
    r = QPSOOptimizer().optimize(
        scenario, OptimizationConfig(algorithm="qpso", population_size=20, max_iterations=40, seed=42))
    assert (r.total_cost, r.total_travel_time, r.total_distance) == (198.75, 166.25, 65.0)
    assert _jobs(r) == [[4, 1, 8, 15, 12, 3], [14, 13], [2, 5, 6, 7, 9, 11, 10]]
    assert round(sum(r.convergence_history), 2) == 8554.86


def test_qpso_with_time_windows_matches_the_pre_memoization_result():
    scenario = generate_synthetic_scenario(
        num_nodes=30, num_jobs=12, num_vehicles=3, seed=5, time_windows=True, tw_width_min=45)
    r = QPSOOptimizer().optimize(
        scenario, OptimizationConfig(algorithm="qpso", population_size=20, max_iterations=40, seed=42))
    assert (r.total_cost, r.total_travel_time, r.total_distance) == (269.85, 229.1, 80.7)
    assert _jobs(r) == [[5], [6, 1, 9, 8, 4], [10, 11, 12, 7, 2, 3]]
    assert round(sum(r.convergence_history), 2) == 11806.1


# ------------------------------------------------------------- the pieces

def _decode_args(scenario):
    dist, tm, paths = get_route_matrix(scenario).as_tuple()
    return dist, tm, paths


def test_route_memo_returns_the_same_routes_as_building_directly():
    scenario = _scenario()
    dist, tm, paths = _decode_args(scenario)
    memo = RouteMemo()
    rng = np.random.default_rng(1)

    for _ in range(25):
        keys = rng.random(len(scenario.jobs))
        plain = decode_random_keys(keys, scenario, dist, tm, paths, include_stops=False)
        memoised = decode_random_keys(keys, scenario, dist, tm, paths, include_stops=False, memo=memo)
        assert [r.model_dump() for r in memoised] == [r.model_dump() for r in plain]


def test_route_memo_reuses_a_route_for_the_same_vehicle_and_job_order():
    scenario = _scenario()
    dist, tm, paths = _decode_args(scenario)
    memo = RouteMemo()
    keys = np.random.default_rng(2).random(len(scenario.jobs))

    first = decode_random_keys(keys, scenario, dist, tm, paths, include_stops=False, memo=memo)
    second = decode_random_keys(keys, scenario, dist, tm, paths, include_stops=False, memo=memo)

    assert all(a is b for a, b in zip(first, second))


def test_route_memo_keeps_stops_and_no_stops_builds_separate():
    scenario = _scenario()
    dist, tm, paths = _decode_args(scenario)
    memo = RouteMemo()
    keys = np.random.default_rng(3).random(len(scenario.jobs))

    lean = decode_random_keys(keys, scenario, dist, tm, paths, include_stops=False, memo=memo)
    full = decode_random_keys(keys, scenario, dist, tm, paths, include_stops=True, memo=memo)

    assert all(not r.stops for r in lean if r.job_ids)
    assert all(len(r.stops) == len(r.job_ids) for r in full)


def test_route_memo_is_bounded_and_clears_its_congestion_map_with_it():
    scenario = _scenario()
    dist, tm, paths = _decode_args(scenario)
    memo = RouteMemo(max_entries=5)
    rng = np.random.default_rng(4)

    for _ in range(40):
        routes = decode_random_keys(rng.random(len(scenario.jobs)), scenario, dist, tm, paths,
                                    include_stops=False, memo=memo)
        evaluate_solution(routes, scenario, OptimizationConfig().weights, "t",
                          edge_map=build_edge_map(scenario), congestion_cache=memo.congestion)

    assert len(memo._routes) <= 5
    assert len(memo.congestion) <= 5 + len(scenario.vehicles)


def test_congestion_cache_does_not_change_the_evaluation():
    base = _scenario()
    edges = {(e.source, e.destination): 3.0 for e in base.edges[:10]}
    scenario, _ = apply_incidents(base, edges)
    dist, tm, paths = _decode_args(scenario)
    edge_map = build_edge_map(scenario)
    weights = OptimizationConfig().weights
    memo = RouteMemo()
    rng = np.random.default_rng(5)

    for _ in range(20):
        keys = rng.random(len(scenario.jobs))
        a = evaluate_solution(
            decode_random_keys(keys, scenario, dist, tm, paths, include_stops=False),
            scenario, weights, "t", edge_map=edge_map)
        b = evaluate_solution(
            decode_random_keys(keys, scenario, dist, tm, paths, include_stops=False, memo=memo),
            scenario, weights, "t", edge_map=edge_map, congestion_cache=memo.congestion)
        assert a.total_cost == b.total_cost
        assert [r.congestion_delay for r in a.routes] == [r.congestion_delay for r in b.routes]


def test_local_search_cost_cache_does_not_change_the_refined_routes():
    scenario = _scenario()
    dist, tm, paths = _decode_args(scenario)
    edge_map = build_edge_map(scenario)
    weights = OptimizationConfig().weights
    rng = np.random.default_rng(6)

    shared_cache = {}
    for _ in range(6):
        routes = decode_random_keys(rng.random(len(scenario.jobs)), scenario, dist, tm, paths, include_stops=False)
        plain = local_search_refine(scenario, routes, dist, tm, paths, weights, edge_map=edge_map)
        cached = local_search_refine(scenario, routes, dist, tm, paths, weights, edge_map=edge_map,
                                     cost_cache=shared_cache)
        assert [r.model_dump() for r in cached] == [r.model_dump() for r in plain]

    assert shared_cache, "the cache should have been used"
