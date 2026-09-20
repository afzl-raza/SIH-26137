"""Tests for the terminal-restricted route matrix (Phase 1 scaling fix).

The optimization path used to build two V x V matrices plus a dict of V^2 node
paths. That is fine for a 30-node synthetic graph but not for a real
OpenStreetMap extract, so the matrices are now built only over routing
terminals (depot, vehicle start/end nodes, job nodes).

These tests pin down that the restriction changed *cost*, not *behaviour*.
"""
import copy
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import Node, Edge, Vehicle, Job, ProblemScenario, OptimizationConfig, ObjectiveWeights
from problem_generator import (
    generate_synthetic_scenario,
    compute_shortest_paths,
    compute_route_matrix,
    terminal_nodes,
    UNREACHABLE,
)
from decoder import decode_random_keys
from fitness import evaluate_solution
from optimizers.greedy import GreedyOptimizer
from optimizers.qpso import QPSOOptimizer


def _chain_scenario():
    """0 -> 1 -> 2 -> 3 chain (cost 3) plus a direct 0 -> 3 shortcut (cost 10),
    with node 3 as a job. The shortest path must still go via 1 and 2 even
    though neither is a terminal - the full graph is still traversed."""
    nodes = [Node(id=i, name=f"N{i}", lat=0.0, lng=0.0, is_depot=(i == 0)) for i in range(4)]
    edges = [
        Edge(source=0, destination=1, distance=1.0, base_travel_time=1.0, current_travel_time=1.0),
        Edge(source=1, destination=2, distance=1.0, base_travel_time=1.0, current_travel_time=1.0),
        Edge(source=2, destination=3, distance=1.0, base_travel_time=1.0, current_travel_time=1.0),
        Edge(source=0, destination=3, distance=10.0, base_travel_time=10.0, current_travel_time=10.0),
        Edge(source=3, destination=0, distance=2.0, base_travel_time=2.0, current_travel_time=2.0),
    ]
    return ProblemScenario(
        nodes=nodes,
        edges=edges,
        vehicles=[Vehicle(id=1, capacity=100.0, start_node=0, end_node=0)],
        jobs=[Job(id=1, node_id=3, demand=1.0, service_time=0.0)],
        depot_node_id=0,
        seed=1,
    )


# ---------------------------------------------------------------- terminals

def test_terminals_are_depot_vehicles_and_jobs_only():
    s = generate_synthetic_scenario(num_nodes=40, num_jobs=12, num_vehicles=3, seed=5)
    terms = terminal_nodes(s)

    expected = {s.depot_node_id}
    expected |= {v.start_node for v in s.vehicles} | {v.end_node for v in s.vehicles}
    expected |= {j.node_id for j in s.jobs}

    assert terms == sorted(expected)
    assert terms == sorted(set(terms)), "terminals must be de-duplicated"
    # Vehicles start and end at the depot here, so K = 1 depot + 12 jobs.
    assert len(terms) == 13


def test_matrix_is_quadratic_in_terminals_not_in_nodes():
    """The whole point of Phase 1: matrix size must track job count, not the
    size of the road graph."""
    small_graph = generate_synthetic_scenario(num_nodes=40, num_jobs=10, num_vehicles=2, seed=3)
    large_graph = generate_synthetic_scenario(num_nodes=400, num_jobs=10, num_vehicles=2, seed=3)

    small = compute_route_matrix(small_graph)
    large = compute_route_matrix(large_graph)

    assert small.dist.shape == (11, 11)
    assert large.dist.shape == (11, 11), "10x more road nodes must not grow the matrix"
    assert large.time.shape == (11, 11)


def test_non_terminal_lookup_raises_a_clear_error():
    s = _chain_scenario()
    rm = compute_route_matrix(s)
    # Node 1 is an intermediate road node, not a terminal.
    assert 1 not in rm.terminals
    with pytest.raises(KeyError, match="not a routing terminal"):
        rm.dist[0, 1]


# -------------------------------------------------------------- correctness

def test_matches_all_pairs_result_on_every_terminal_pair():
    """Strongest correctness check: for several scenarios the restricted
    matrix must agree exactly with the all-pairs computation on every pair it
    covers - same distance, same travel time, same node path."""
    for seed in (1, 42, 123):
        s = generate_synthetic_scenario(num_nodes=60, num_jobs=14, num_vehicles=3, seed=seed)
        dist_all, time_all, paths_all = compute_shortest_paths(s)
        rm = compute_route_matrix(s)

        for u in rm.terminals:
            for v in rm.terminals:
                assert rm.dist[u, v] == pytest.approx(dist_all[u, v], abs=0.0)
                assert rm.time[u, v] == pytest.approx(time_all[u, v], abs=0.0)
                assert rm.paths[(u, v)] == paths_all[(u, v)]


def test_shortest_path_routes_through_non_terminal_nodes():
    """Intermediate nodes are excluded from the matrix but must still be used
    for routing, and must still appear in the returned node path."""
    s = _chain_scenario()
    rm = compute_route_matrix(s)

    assert rm.paths[(0, 3)] == [0, 1, 2, 3], "must take the 3-hop chain, not the 10-cost shortcut"
    assert rm.time[0, 3] == pytest.approx(3.0)
    assert rm.dist[0, 3] == pytest.approx(3.0)
    assert rm.time[3, 0] == pytest.approx(2.0)
    assert rm.dist[0, 0] == 0.0
    assert rm.paths[(0, 0)] == [0]


def test_unreachable_terminal_pair_is_reported_not_crashed():
    s = _chain_scenario()
    # Drop the only edge back to the depot, stranding the job node.
    s.edges = [e for e in s.edges if not (e.source == 3 and e.destination == 0)]
    rm = compute_route_matrix(s)

    assert rm.time[3, 0] == UNREACHABLE
    assert rm.dist[3, 0] == UNREACHABLE
    assert rm.paths[(3, 0)] == [3, 0]


def test_traffic_factor_changes_matrix_travel_time():
    """Congestion must propagate into the matrix the optimizers consume,
    otherwise re-optimization after an incident is meaningless."""
    s = _chain_scenario()
    before = compute_route_matrix(s).time[0, 3]

    for e in s.edges:
        if (e.source, e.destination) == (1, 2):
            e.traffic_factor = 4.0
            e.current_travel_time = e.base_travel_time * 4.0

    after = compute_route_matrix(s)
    # The chain now costs 1 + 4 + 1 = 6, still cheaper than the 10-cost
    # shortcut, so the path is unchanged but strictly slower than before.
    assert after.time[0, 3] == pytest.approx(6.0)
    assert after.time[0, 3] > before


# ------------------------------------------------------- decoder + fitness

def test_decoder_produces_identical_routes_under_both_matrix_variants():
    s = generate_synthetic_scenario(num_nodes=50, num_jobs=12, num_vehicles=3, seed=11)
    dist_all, time_all, paths_all = compute_shortest_paths(s)
    rm = compute_route_matrix(s)

    rng = np.random.default_rng(0)
    for _ in range(25):
        keys = rng.random(len(s.jobs))
        routes_all = decode_random_keys(keys, s, dist_all, time_all, paths_all)
        routes_rm = decode_random_keys(keys, s, *rm.as_tuple())

        assert len(routes_all) == len(routes_rm)
        for a, b in zip(routes_all, routes_rm):
            assert a.vehicle_id == b.vehicle_id
            assert a.job_ids == b.job_ids
            assert a.node_path == b.node_path
            assert a.route_distance == b.route_distance
            assert a.route_travel_time == b.route_travel_time
            assert a.total_demand == b.total_demand


def test_fitness_is_identical_under_both_matrix_variants():
    s = generate_synthetic_scenario(num_nodes=50, num_jobs=12, num_vehicles=3, seed=11)
    weights = ObjectiveWeights()
    dist_all, time_all, paths_all = compute_shortest_paths(s)
    rm = compute_route_matrix(s)

    rng = np.random.default_rng(1)
    for _ in range(25):
        keys = rng.random(len(s.jobs))
        r_all = evaluate_solution(
            decode_random_keys(keys, s, dist_all, time_all, paths_all), s, weights)
        r_rm = evaluate_solution(
            decode_random_keys(keys, s, *rm.as_tuple()), s, weights)

        assert r_rm.total_cost == r_all.total_cost
        assert r_rm.total_travel_time == r_all.total_travel_time
        assert r_rm.total_distance == r_all.total_distance
        assert r_rm.constraint_violations == r_all.constraint_violations
        assert r_rm.is_feasible == r_all.is_feasible


# ------------------------------------------------------------- no mutation

def test_compute_route_matrix_does_not_mutate_scenario():
    s = generate_synthetic_scenario(num_nodes=40, num_jobs=10, num_vehicles=3, seed=9)
    before = s.model_dump()
    compute_route_matrix(s)
    assert s.model_dump() == before


def test_optimizers_do_not_mutate_scenario():
    s = generate_synthetic_scenario(num_nodes=40, num_jobs=10, num_vehicles=3, seed=9)
    before = copy.deepcopy(s.model_dump())

    GreedyOptimizer().optimize(s, OptimizationConfig(algorithm="greedy"))
    assert s.model_dump() == before

    QPSOOptimizer().optimize(
        s, OptimizationConfig(algorithm="qpso", population_size=8, max_iterations=5))
    assert s.model_dump() == before


# -------------------------------------------------- end-to-end still valid

@pytest.mark.parametrize("seed", [1, 42])
def test_small_synthetic_scenarios_still_produce_valid_results(seed):
    """Regression guard: the classic small demo scenarios must still solve,
    stay feasible, and visit every job exactly once."""
    s = generate_synthetic_scenario(num_nodes=30, num_jobs=15, num_vehicles=3, seed=seed)
    config = OptimizationConfig(algorithm="qpso", population_size=12, max_iterations=10, seed=seed)

    result = QPSOOptimizer().optimize(s, config)

    assert result.total_cost > 0
    assert result.total_travel_time > 0
    assert len(result.routes) == len(s.vehicles)

    visited = [jid for r in result.routes for jid in r.job_ids]
    assert sorted(visited) == sorted(j.id for j in s.jobs), "every job visited exactly once"

    depot = s.depot_node_id
    for r in result.routes:
        assert r.node_path[0] == depot and r.node_path[-1] == depot
