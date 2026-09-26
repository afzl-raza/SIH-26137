"""Tests for the content-addressed RouteMatrix cache.

The cache exists so a four-algorithm benchmark builds the matrix once instead
of four times. The rules that matter for correctness are the *miss* rules: a
stale matrix served after a traffic incident would silently produce routes
computed against the old road costs.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
from models import OptimizationConfig
from optimizers import benchmark
from optimizers.benchmark import run_benchmark
from problem_generator import compute_route_matrix, generate_synthetic_scenario, terminal_nodes
from route_cache import (
    ROUTE_MATRIX_CACHE,
    RouteMatrixCache,
    get_route_matrix,
    route_matrix_key,
)

client = TestClient(main_module.app)


@pytest.fixture
def cache():
    return RouteMatrixCache()


def _scenario(**kw):
    params = dict(num_nodes=20, num_jobs=8, num_vehicles=3, seed=42)
    params.update(kw)
    return generate_synthetic_scenario(**params)


def _congest(scenario, index=0, factor=3.5):
    """Applies congestion exactly the way /api/traffic/update does."""
    edge = scenario.edges[index]
    edge.traffic_factor = factor
    edge.current_travel_time = round(edge.base_travel_time * factor, 2)
    return edge


# ============================================================== cache hits

def test_same_scenario_same_terminals_is_a_hit(cache):
    s = _scenario()

    first = cache.get(s)
    second = cache.get(s)

    assert second is first, "a repeat lookup must return the very same matrix"
    stats = cache.stats()
    assert (stats["hits"], stats["misses"], stats["builds"], stats["entries"]) == (1, 1, 1, 1)


def test_two_structurally_identical_scenarios_share_a_cache_entry(cache):
    """The key is content-addressed, not object identity - two independently
    generated but identical scenarios must hit."""
    a = _scenario()
    b = _scenario()

    assert a is not b
    assert route_matrix_key(a) == route_matrix_key(b)

    cache.get(a)
    cache.get(b)
    assert cache.stats()["builds"] == 1
    assert cache.stats()["hits"] == 1


# ============================================================= cache misses

def test_changed_traffic_factor_is_a_miss(cache):
    s = _scenario()
    cache.get(s)

    _congest(s)
    cache.get(s)

    assert cache.stats()["builds"] == 2
    assert cache.stats()["hits"] == 0


def test_changed_edge_weight_alone_is_a_miss(cache):
    """Travel time changed but traffic_factor untouched - still a miss,
    because current_travel_time is the Dijkstra weight."""
    s = _scenario()
    cache.get(s)

    s.edges[0].current_travel_time = s.edges[0].current_travel_time + 7.0
    cache.get(s)

    assert cache.stats()["builds"] == 2


def test_traffic_factor_alone_is_a_miss(cache):
    """Defensive: traffic_factor does not drive routing on its own, but a
    change to it must never be able to serve a matrix built before it."""
    s = _scenario()
    cache.get(s)

    s.edges[0].traffic_factor = 2.0  # deliberately without touching travel time
    cache.get(s)

    assert cache.stats()["builds"] == 2


def test_different_terminal_set_is_a_miss(cache):
    s = _scenario()
    terminals = terminal_nodes(s)
    cache.get(s, terminals=terminals)

    cache.get(s, terminals=terminals[:-1])

    assert cache.stats()["builds"] == 2
    assert cache.stats()["hits"] == 0


def test_changed_distance_is_a_miss(cache):
    s = _scenario()
    cache.get(s)

    s.edges[0].distance = s.edges[0].distance + 5.0
    cache.get(s)

    assert cache.stats()["builds"] == 2


def test_different_graph_is_a_miss(cache):
    cache.get(_scenario(seed=1))
    cache.get(_scenario(seed=2))
    assert cache.stats()["builds"] == 2


# ================================================= no stale matrix, ever

def test_matrix_reflects_congestion_immediately_after_an_incident(cache):
    """The core safety property: after an incident the cache must hand back a
    matrix computed against the *new* road costs."""
    s = _scenario()
    edge = s.edges[0]
    u, v = edge.source, edge.destination

    before = cache.get(s)
    baseline = float(compute_route_matrix(s).time.array.sum())
    assert float(before.time.array.sum()) == pytest.approx(baseline)

    # Congest the edge hard, in both directions, so some terminal pair must
    # be affected.
    for e in s.edges:
        if {e.source, e.destination} == {u, v}:
            e.traffic_factor = 50.0
            e.current_travel_time = round(e.base_travel_time * 50.0, 2)

    after = cache.get(s)
    fresh = float(compute_route_matrix(s).time.array.sum())

    assert after is not before
    assert float(after.time.array.sum()) == pytest.approx(fresh)


def test_cached_matrix_equals_an_uncached_computation(cache):
    s = _scenario()
    cached = cache.get(s)
    direct = compute_route_matrix(s)

    assert cached.terminals == direct.terminals
    for u in direct.terminals:
        for v in direct.terminals:
            assert cached.time[u, v] == direct.time[u, v]
            assert cached.dist[u, v] == direct.dist[u, v]
            assert cached.paths[(u, v)] == direct.paths[(u, v)]


# ======================================================== benchmark reuse

def test_benchmark_builds_the_matrix_once_and_hits_three_times():
    """Greedy, PSO, GA, plain QPSO, QPSO+local-search, QPSO+local-search
    (memetic) and the exact solver (8 jobs is within its cap) run on one
    identical scenario, so the matrix must be built exactly once. Everything
    but Greedy runs in worker processes that are handed the parent's matrix,
    so: one build in the parent, zero in workers."""
    s = _scenario(num_nodes=25, num_jobs=8, num_vehicles=3, seed=17)
    config = OptimizationConfig(population_size=6, max_iterations=3, seed=17)

    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()
    benchmark.clear_result_cache()

    result = run_benchmark(s, config)
    stats = ROUTE_MATRIX_CACHE.stats()

    assert set(result.results.keys()) == {"greedy", "pso", "ga", "qpso", "qpso_ls", "qpso_memetic", "exact"}
    assert stats["builds"] == 1, f"expected a single matrix build, got {stats}"
    assert stats["hits"] >= 1, f"expected Greedy to reuse the build, got {stats}"
    assert benchmark.LAST_WORKER_ROUTE_MATRIX_BUILDS == 0


def test_benchmark_after_incident_rebuilds_once_more():
    s = _scenario(num_nodes=25, num_jobs=8, num_vehicles=3, seed=17)
    config = OptimizationConfig(population_size=6, max_iterations=3, seed=17)

    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()
    benchmark.clear_result_cache()

    first = run_benchmark(s, config)
    _congest(s)
    second = run_benchmark(s, config)

    stats = ROUTE_MATRIX_CACHE.stats()
    assert first.cached is False and second.cached is False, "an incident must never be served from the result cache"
    assert stats["builds"] == 2, f"incident must force exactly one rebuild, got {stats}"
    assert benchmark.LAST_WORKER_ROUTE_MATRIX_BUILDS == 0


# ==================================================== eviction and bounds

def test_cache_is_bounded():
    cache = RouteMatrixCache(max_entries=2)
    for seed in (1, 2, 3):
        cache.get(_scenario(seed=seed))
    assert cache.stats()["entries"] == 2


def test_module_level_helper_uses_the_shared_cache():
    s = _scenario(seed=99)
    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()

    get_route_matrix(s)
    get_route_matrix(s)

    assert ROUTE_MATRIX_CACHE.stats()["builds"] == 1
    assert ROUTE_MATRIX_CACHE.stats()["hits"] == 1


# ================================================ end-to-end through the API

def test_reoptimize_after_traffic_update_uses_fresh_costs():
    """Full incident loop through the API: the re-optimized result must be
    scored against the congested network, not a cached pre-incident one."""
    gen = client.post("/api/problem/generate", json={
        "num_nodes": 20, "num_jobs": 8, "num_vehicles": 3, "seed": 42
    }).json()
    scenario_id = gen["scenario_id"]
    config = {"algorithm": "greedy"}

    before = client.post("/api/optimize", json={
        "scenario_id": scenario_id, "config": config}).json()

    # Congest every edge on the first vehicle's active path, hard.
    path = before["routes"][0]["node_path"]
    updates = [
        {"source": u, "destination": v, "traffic_factor": 20.0}
        for u, v in zip(path[:-1], path[1:])
    ]
    assert updates
    traffic = client.post("/api/traffic/update", json={
        "scenario_id": scenario_id, "updates": updates})
    assert traffic.status_code == 200

    after = client.post("/api/optimize", json={
        "scenario_id": scenario_id, "config": config}).json()

    # Greedy is deterministic, so any difference is caused by the new costs
    # alone. A stale matrix would reproduce the pre-incident result exactly.
    assert after["total_travel_time"] != before["total_travel_time"]
