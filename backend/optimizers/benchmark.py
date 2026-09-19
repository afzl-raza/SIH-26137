from typing import Dict
from models import ProblemScenario, OptimizationConfig, BenchmarkResult, OptimizationResult
from optimizers.greedy import GreedyOptimizer
from optimizers.pso import PSOOptimizer
from optimizers.ga import GAOptimizer
from optimizers.qpso import QPSOOptimizer


def run_benchmark(
    scenario: ProblemScenario,
    config: OptimizationConfig
) -> BenchmarkResult:
    """
    Executes all available optimizers (Greedy, Classical PSO, GA, QPSO) on the EXACT same
    problem scenario and parameters, collecting actual experimental results.
    """
    results: Dict[str, OptimizationResult] = {}

    # 1. Baseline Greedy
    greedy_opt = GreedyOptimizer()
    results["greedy"] = greedy_opt.optimize(scenario, config)

    # 2. Classical PSO
    pso_opt = PSOOptimizer()
    results["pso"] = pso_opt.optimize(scenario, config)

    # 3. Genetic Algorithm (GA)
    ga_opt = GAOptimizer()
    results["ga"] = ga_opt.optimize(scenario, config)

    # 4. Quantum-behaved PSO (QPSO)
    qpso_opt = QPSOOptimizer()
    results["qpso"] = qpso_opt.optimize(scenario, config)

    return BenchmarkResult(
        scenario_seed=scenario.seed,
        results=results
    )
