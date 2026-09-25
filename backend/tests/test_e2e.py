import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import OptimizationConfig
from problem_generator import generate_synthetic_scenario
from fitness import evaluate_solution
from optimizers.qpso import QPSOOptimizer
from optimizers.benchmark import run_benchmark


def test_full_demo_workflow():
    """Encodes the Definition of Done workflow end to end:
    generate -> optimize -> incident -> traffic update -> re-optimize -> benchmark.
    """
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=42)

    config = OptimizationConfig(algorithm="qpso", population_size=10, max_iterations=15, seed=42)
    optimizer = QPSOOptimizer()

    result_before = optimizer.optimize(scenario, config)
    assert len(result_before.routes) > 0
    assert result_before.total_cost > 0

    # Pick an edge actually used by an active route, matching how the live
    # demo selects its incident edge.
    used_edge = None
    for route in result_before.routes:
        if len(route.node_path) >= 2:
            used_edge = (route.node_path[0], route.node_path[1])
            break
    assert used_edge is not None

    congested = False
    for edge in scenario.edges:
        if (edge.source, edge.destination) == used_edge:
            edge.traffic_factor = 3.5
            edge.current_travel_time = edge.base_travel_time * 3.5
            congested = True
    assert congested

    # Deterministic check: re-evaluating the *same* pre-incident routes
    # against the now-congested scenario must cost strictly more. This is the
    # "traffic changed -> transportation problem changed" causal link.
    reevaluated = evaluate_solution(result_before.routes, scenario, config.weights)
    assert reevaluated.total_cost > result_before.total_cost

    # Re-optimizing on the changed scenario must still run to a valid result.
    # (QPSO may or may not find a cheaper alternative route - that's the
    # stochastic part - but it must not fail.)
    result_after = optimizer.optimize(scenario, config)
    assert len(result_after.routes) > 0
    assert result_after.total_cost > 0

    benchmark_result = run_benchmark(scenario, config)
    assert set(benchmark_result.results.keys()) == {"greedy", "pso", "ga", "qpso", "qpso_memetic"}
    for result in benchmark_result.results.values():
        assert result.total_cost > 0
