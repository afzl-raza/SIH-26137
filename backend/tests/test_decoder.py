import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import Node, Job, Vehicle, ProblemScenario
from decoder import decode_random_keys


def test_decode_hand_computed_route():
    """One vehicle, three jobs, hand-picked keys - the decoded route must
    match a manually computed expected sequence exactly."""
    nodes = [Node(id=i, name=f"N{i}", lat=0.0, lng=0.0, is_depot=(i == 0)) for i in range(4)]
    jobs = [
        Job(id=1, node_id=1, demand=2.0, service_time=0.0),
        Job(id=2, node_id=2, demand=3.0, service_time=0.0),
        Job(id=3, node_id=3, demand=1.0, service_time=0.0),
    ]
    vehicle = Vehicle(id=1, capacity=100.0, start_node=0, end_node=0, max_route_time=1000.0)
    scenario = ProblemScenario(nodes=nodes, edges=[], vehicles=[vehicle], jobs=jobs, depot_node_id=0, seed=1)

    dist_matrix = np.array([
        [0, 1, 2, 3],
        [1, 0, 1, 2],
        [2, 1, 0, 1],
        [3, 2, 1, 0],
    ], dtype=float)
    time_matrix = dist_matrix.copy()
    paths_dict = {}  # decoder falls back to a direct hop when no path is precomputed

    # One key per job (job1, job2, job3). With a single vehicle every key maps
    # to vehicle 0, and jobs are visited in ascending key order:
    # job2 (0.1) -> job1 (0.5) -> job3 (0.9)
    keys = np.array([0.5, 0.1, 0.9])

    routes = decode_random_keys(keys, scenario, dist_matrix, time_matrix, paths_dict)

    assert len(routes) == 1
    route = routes[0]
    assert route.job_ids == [2, 1, 3]
    assert route.node_path == [0, 2, 1, 3, 0]
    assert route.route_distance == pytest.approx(2 + 1 + 2 + 3)
    assert route.route_travel_time == pytest.approx(2 + 1 + 2 + 3)
    assert route.total_demand == pytest.approx(2 + 3 + 1)


def test_decode_multi_vehicle_split():
    """Hand-picked keys must split jobs across vehicles exactly as the
    key -> vehicle_idx formula dictates."""
    nodes = [Node(id=i, name=f"N{i}", lat=0.0, lng=0.0, is_depot=(i == 0)) for i in range(5)]
    jobs = [Job(id=jid, node_id=jid, demand=1.0, service_time=0.0) for jid in range(1, 5)]
    vehicles = [
        Vehicle(id=1, capacity=100.0, start_node=0, end_node=0, max_route_time=1000.0),
        Vehicle(id=2, capacity=100.0, start_node=0, end_node=0, max_route_time=1000.0),
    ]
    scenario = ProblemScenario(nodes=nodes, edges=[], vehicles=vehicles, jobs=jobs, depot_node_id=0, seed=1)

    size = 5
    dist_matrix = np.ones((size, size)) - np.eye(size)
    time_matrix = dist_matrix.copy()
    paths_dict = {}

    # jobs 1,2 -> vehicle 0 (key < 0.5); jobs 3,4 -> vehicle 1 (key >= 0.5)
    keys = np.array([0.1, 0.3, 0.6, 0.9])

    routes = decode_random_keys(keys, scenario, dist_matrix, time_matrix, paths_dict)

    assert len(routes) == 2
    assert routes[0].vehicle_id == 1
    assert routes[0].job_ids == [1, 2]
    assert routes[1].vehicle_id == 2
    assert routes[1].job_ids == [3, 4]


def test_decode_more_vehicles_than_jobs():
    """5 vehicles, 2 jobs - unused vehicles must get a valid depot-only
    route instead of crashing or being omitted."""
    nodes = [Node(id=i, name=f"N{i}", lat=0.0, lng=0.0, is_depot=(i == 0)) for i in range(3)]
    jobs = [
        Job(id=1, node_id=1, demand=1.0, service_time=0.0),
        Job(id=2, node_id=2, demand=1.0, service_time=0.0),
    ]
    vehicles = [Vehicle(id=v, capacity=10.0, start_node=0, end_node=0, max_route_time=100.0) for v in range(1, 6)]
    scenario = ProblemScenario(nodes=nodes, edges=[], vehicles=vehicles, jobs=jobs, depot_node_id=0, seed=1)

    size = 3
    dist_matrix = np.ones((size, size)) - np.eye(size)
    time_matrix = dist_matrix.copy()
    paths_dict = {}

    # job1 (key 0.05) -> vehicle 0; job2 (key 0.25) -> vehicle 1
    keys = np.array([0.05, 0.25])

    routes = decode_random_keys(keys, scenario, dist_matrix, time_matrix, paths_dict)

    assert len(routes) == 5
    assert routes[0].job_ids == [1]
    assert routes[1].job_ids == [2]
    for empty_route in routes[2:]:
        assert empty_route.job_ids == []
        assert empty_route.node_path == [0, 0]
        assert empty_route.route_distance == 0.0
        assert empty_route.total_demand == 0.0


def test_decode_zero_jobs():
    """Documents the current, intentional contract: with zero jobs the
    decoder returns no routes at all (unlike Greedy, which always emits one
    empty route per vehicle - a known, accepted asymmetry, see Engineering.md)."""
    nodes = [Node(id=0, name="Depot", lat=0.0, lng=0.0, is_depot=True)]
    vehicle = Vehicle(id=1, capacity=10.0, start_node=0, end_node=0, max_route_time=100.0)
    scenario = ProblemScenario(nodes=nodes, edges=[], vehicles=[vehicle], jobs=[], depot_node_id=0, seed=1)

    routes = decode_random_keys(np.array([]), scenario, np.zeros((1, 1)), np.zeros((1, 1)), {})

    assert routes == []
