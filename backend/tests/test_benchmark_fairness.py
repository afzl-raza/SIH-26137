import sys
import os
import copy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import OptimizationConfig
from problem_generator import generate_synthetic_scenario
from optimizers.benchmark import run_benchmark


def test_benchmark_scenario_not_mutated():
    """No optimizer may mutate the shared scenario - otherwise later
    algorithms in the same benchmark run would see a different problem than
    earlier ones, breaking the fairness guarantee."""
    scenario = generate_synthetic_scenario(num_nodes=15, num_jobs=6, num_vehicles=2, seed=5)
    original = copy.deepcopy(scenario)
    config = OptimizationConfig(population_size=8, max_iterations=5)

    run_benchmark(scenario, config)

    assert scenario == original


def test_benchmark_all_algorithms_present_and_feasible_or_flagged():
    scenario = generate_synthetic_scenario(num_nodes=15, num_jobs=6, num_vehicles=2, seed=5)
    config = OptimizationConfig(population_size=8, max_iterations=5)

    benchmark_result = run_benchmark(scenario, config)

    assert set(benchmark_result.results.keys()) == {"greedy", "pso", "ga", "qpso"}
    for algorithm, result in benchmark_result.results.items():
        assert result.is_feasible == (result.constraint_violations == 0), (
            f"{algorithm}: is_feasible must match constraint_violations exactly"
        )
