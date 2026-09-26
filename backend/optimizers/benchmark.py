from typing import Dict
from models import ProblemScenario, OptimizationConfig, BenchmarkResult, OptimizationResult
from optimizers.greedy import GreedyOptimizer
from optimizers.pso import PSOOptimizer
from optimizers.ga import GAOptimizer
from optimizers.qpso import QPSOOptimizer
from optimizers.exact import ExactOptimizer, MAX_EXACT_JOBS


def run_benchmark(
    scenario: ProblemScenario,
    config: OptimizationConfig
) -> BenchmarkResult:
    """
    Executes all available optimizers on the EXACT same problem scenario and
    parameters, collecting actual experimental results: Greedy, Classical
    PSO, GA, and QPSO twice (once with its 2-opt/or-opt local search hybrid
    off - the "qpso" ablation baseline - and once with it on, "qpso_ls",
    the default algorithm). The exact solver is added as a fifth/sixth entry
    only when the scenario is small enough for it to run (<=MAX_EXACT_JOBS
    jobs) - it is never silently skipped without the caller being able to
    tell, since its absence from `results` for a larger scenario is itself
    the signal that it wasn't run.
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

    # 4. Plain QPSO - kept as the explicit ablation/comparison entry against
    # QPSO+local-search below, per the finding that plain QPSO alone loses
    # to Greedy at 30+ jobs.
    plain_config = config.model_copy(update={"use_local_search": False})
    qpso_opt = QPSOOptimizer()
    results["qpso"] = qpso_opt.optimize(scenario, plain_config)

    # 5. QPSO + 2-opt/or-opt local search - the default algorithm.
    ls_config = config.model_copy(update={"use_local_search": True})
    qpso_ls_opt = QPSOOptimizer()
    results["qpso_ls"] = qpso_ls_opt.optimize(scenario, ls_config)

    # 6. Exact optimum, only when the scenario is small enough.
    if len(scenario.jobs) <= MAX_EXACT_JOBS:
        exact_opt = ExactOptimizer()
        results["exact"] = exact_opt.optimize(scenario, config)

    return BenchmarkResult(
        scenario_seed=scenario.seed,
        results=results
    )
