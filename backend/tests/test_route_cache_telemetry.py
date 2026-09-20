"""Unit tests for RouteMatrixCache telemetry, peek, and capacity controls."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from problem_generator import generate_synthetic_scenario
from route_cache import RouteMatrixCache, route_matrix_key
from route_geometry import node_path_polyline, route_geometries


@pytest.fixture
def cache():
    return RouteMatrixCache(max_entries=4)


def _scenario(seed=42):
    return generate_synthetic_scenario(num_nodes=15, num_jobs=6, num_vehicles=2, seed=seed)


def test_hit_ratio_telemetry(cache):
    s = _scenario()
    assert cache.stats()["hit_ratio"] == 0.0

    # Miss
    cache.get(s)
    assert cache.stats()["hits"] == 0
    assert cache.stats()["misses"] == 1
    assert cache.stats()["hit_ratio"] == 0.0

    # Hit
    cache.get(s)
    assert cache.stats()["hits"] == 1
    assert cache.stats()["misses"] == 1
    assert cache.stats()["hit_ratio"] == 0.5


def test_peek_does_not_mutate_stats_or_lru(cache):
    s = _scenario()
    assert cache.peek(s) is False
    assert cache.stats()["misses"] == 0

    cache.get(s)
    assert cache.peek(s) is True
    assert cache.stats()["hits"] == 0


def test_set_max_entries_eviction(cache):
    scenarios = [_scenario(seed=i) for i in range(5)]
    for s in scenarios[:4]:
        cache.get(s)

    assert cache.stats()["entries"] == 4

    # Resize to 2 entries, forcing eviction of oldest items
    cache.set_max_entries(2)
    assert cache.stats()["entries"] == 2
    assert cache.stats()["max_entries"] == 2


def test_invalid_max_entries_raises_value_error(cache):
    with pytest.raises(ValueError, match="max_entries must be at least 1"):
        cache.set_max_entries(0)


def test_route_geometry_pre_indexing():
    scenario = _scenario()
    routes = [
        type('VR', (), {'vehicle_id': 1, 'node_path': [0, 1, 2]})(),
        type('VR', (), {'vehicle_id': 2, 'node_path': [0, 3, 4]})()
    ]
    res = route_geometries(scenario, routes)
    assert len(res) == 2
    assert res[0]["vehicle_id"] == 1
    assert res[1]["vehicle_id"] == 2
