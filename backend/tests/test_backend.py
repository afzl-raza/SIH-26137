import sys
import os
import pytest

# Add parent directory to path so imports work smoothly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import ProblemScenario, OptimizationConfig, TrafficUpdate
from problem_generator import generate_synthetic_scenario, compute_shortest_paths
from fitness import evaluate_solution
from optimizers.greedy import GreedyOptimizer
from optimizers.pso import PSOOptimizer
from optimizers.qpso import QPSOOptimizer
from optimizers.benchmark import run_benchmark


def test_problem_generator_seed():
    s1 = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    s2 = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    assert len(s1.nodes) == 20
    assert len(s1.jobs) == 10
    assert s1.nodes[0].is_depot is True
    assert s1.nodes[1].lat == s2.nodes[1].lat
    assert s1.jobs[0].demand == s2.jobs[0].demand


def test_scenario_hash_deterministic_and_distinguishing():
    same_a = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    same_b = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    different_seed = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=7)

    assert same_a.scenario_hash != ""
    assert same_a.scenario_hash == same_b.scenario_hash
    assert same_a.scenario_hash != different_seed.scenario_hash


def test_shortest_paths():
    s = generate_synthetic_scenario(num_nodes=15, num_jobs=8, num_vehicles=2, seed=123)
    dist_matrix, time_matrix, paths_dict = compute_shortest_paths(s)
    assert dist_matrix.shape == (15, 15)
    assert time_matrix.shape == (15, 15)
    assert dist_matrix[0, 0] == 0.0
    assert (0, 1) in paths_dict


def test_shortest_paths_correctness_small_graph():
    from models import Node, Edge, Vehicle, ProblemScenario

    # 0 -> 1 -> 2 -> 3 chain (cost 3) plus a direct 0 -> 3 shortcut (cost 10).
    # The shortest path from 0 to 3 must go via 1, 2, not the direct edge.
    nodes = [Node(id=i, name=f"N{i}", lat=0.0, lng=0.0, is_depot=(i == 0)) for i in range(4)]
    edges = [
        Edge(source=0, destination=1, distance=1.0, base_travel_time=1.0, current_travel_time=1.0),
        Edge(source=1, destination=2, distance=1.0, base_travel_time=1.0, current_travel_time=1.0),
        Edge(source=2, destination=3, distance=1.0, base_travel_time=1.0, current_travel_time=1.0),
        Edge(source=0, destination=3, distance=10.0, base_travel_time=10.0, current_travel_time=10.0),
    ]
    scenario = ProblemScenario(
        nodes=nodes,
        edges=edges,
        vehicles=[Vehicle(id=1, capacity=10, start_node=0, end_node=0)],
        jobs=[],
        depot_node_id=0,
        seed=1
    )

    dist_matrix, time_matrix, paths_dict = compute_shortest_paths(scenario)

    assert paths_dict[(0, 3)] == [0, 1, 2, 3]
    assert time_matrix[0, 3] == pytest.approx(3.0)
    assert dist_matrix[0, 3] == pytest.approx(3.0)

    assert paths_dict[(0, 1)] == [0, 1]
    assert time_matrix[0, 1] == pytest.approx(1.0)

    assert dist_matrix[2, 2] == 0.0

    # The graph is directed with no edges back toward the depot, so node 3
    # cannot reach node 0 - this must be reported as unreachable, not crash.
    assert time_matrix[3, 0] == 1e6
    assert dist_matrix[3, 0] == 1e6


def test_shortest_paths_performance():
    import time as timer

    s = generate_synthetic_scenario(num_nodes=150, num_jobs=30, num_vehicles=5, seed=7)
    start = timer.perf_counter()
    compute_shortest_paths(s)
    elapsed = timer.perf_counter() - start

    # Generous bound: guards against a regression back to the O(V^2) approach
    # without making CI flaky on slower machines.
    assert elapsed < 5.0


def test_greedy_optimizer():
    s = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    config = OptimizationConfig(algorithm="greedy")
    opt = GreedyOptimizer()
    res = opt.optimize(s, config)
    assert res.algorithm == "Greedy (Nearest Neighbour)"
    assert len(res.routes) > 0
    assert res.total_cost > 0
    assert res.runtime_ms >= 0


def test_pso_optimizer():
    s = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    config = OptimizationConfig(algorithm="pso", population_size=10, max_iterations=15)
    opt = PSOOptimizer()
    res = opt.optimize(s, config)
    assert res.algorithm == "Classical PSO"
    assert len(res.routes) > 0
    assert len(res.convergence_history) == 15


def test_qpso_optimizer():
    s = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    config = OptimizationConfig(algorithm="qpso", population_size=10, max_iterations=15)
    opt = QPSOOptimizer()
    res = opt.optimize(s, config)
    # use_local_search defaults True, and the label says so - plain QPSO and
    # QPSO+local-search share this one class, so the two must be
    # distinguishable in a benchmark table.
    assert res.algorithm == "QPSO (Quantum-behaved PSO) + Local Search"
    assert len(res.routes) > 0
    assert len(res.convergence_history) == 15


def test_qpso_optimizer_ablation_label_when_local_search_disabled():
    s = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    config = OptimizationConfig(algorithm="qpso", population_size=10, max_iterations=15, use_local_search=False)
    opt = QPSOOptimizer()
    res = opt.optimize(s, config)
    assert res.algorithm == "QPSO (Quantum-behaved PSO) (ablation, no local search)"


def test_qpso_convergence_elapsed_ms_is_real_and_monotonic():
    """Per-iteration timing must be actually recorded (not estimated) and
    strictly non-decreasing, matching convergence_history one-to-one."""
    s = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    config = OptimizationConfig(algorithm="qpso", population_size=10, max_iterations=15)
    res = QPSOOptimizer().optimize(s, config)

    assert len(res.convergence_elapsed_ms) == len(res.convergence_history)
    assert all(t >= 0 for t in res.convergence_elapsed_ms)
    assert res.convergence_elapsed_ms == sorted(res.convergence_elapsed_ms)
    # The final recorded elapsed time cannot exceed the total reported runtime.
    assert res.convergence_elapsed_ms[-1] <= res.runtime_ms


def test_ga_optimizer():
    s = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    config = OptimizationConfig(algorithm="ga", population_size=10, max_iterations=15)
    from optimizers.ga import GAOptimizer
    opt = GAOptimizer()
    res = opt.optimize(s, config)
    assert res.algorithm == "Genetic Algorithm (GA)"
    assert len(res.routes) > 0
    assert len(res.convergence_history) == 15


def test_traffic_incident_update():
    s = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)
    edge = s.edges[0]
    initial_time = edge.current_travel_time
    
    # Apply traffic congestion (factor = 3.5)
    edge.traffic_factor = 3.5
    edge.current_travel_time = edge.base_travel_time * 3.5

    assert edge.current_travel_time > initial_time

    # Optimize after traffic incident
    config = OptimizationConfig(algorithm="qpso", population_size=10, max_iterations=10)
    opt = QPSOOptimizer()
    res_after = opt.optimize(s, config)
    assert res_after.total_cost > 0


def test_benchmark_runner():
    s = generate_synthetic_scenario(num_nodes=15, num_jobs=8, num_vehicles=2, seed=99)
    config = OptimizationConfig(population_size=10, max_iterations=10)
    bm = run_benchmark(s, config)
    assert "greedy" in bm.results
    assert "pso" in bm.results
    assert "qpso" in bm.results
    assert bm.results["qpso"].total_cost > 0
