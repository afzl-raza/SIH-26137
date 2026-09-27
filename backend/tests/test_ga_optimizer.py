"""Regression tests for two confirmed GAOptimizer crashes on small,
legitimate (not malformed) configurations - both reproduced against the
pre-fix code before being addressed in optimizers/ga.py:

1. A single-job scenario crashes `_crossover`: `np.random.randint(1, len(p1))`
   is `randint(1, 1)` when the chromosome has one gene, which numpy raises
   ValueError on. crossover_rate=0.85 makes this near-certain within a few
   generations whenever GA is selected for a 1-job scenario.
2. population_size < 3 (e.g. 2) crashes `_tournament_select`:
   `np.random.choice(len(costs), size=3, replace=False)` raises ValueError
   when asked for more samples than the population contains. Nothing in the
   UI or the model enforces a minimum population_size, so this is directly
   reachable by typing "2" into the Pop Size field with GA selected.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from problem_generator import generate_synthetic_scenario
from models import OptimizationConfig
from optimizers.ga import GAOptimizer


def test_ga_does_not_crash_on_a_single_job_scenario():
    scenario = generate_synthetic_scenario(num_nodes=8, num_jobs=1, num_vehicles=2, seed=1)
    config = OptimizationConfig(algorithm="ga", population_size=10, max_iterations=5, seed=1)
    result = GAOptimizer().optimize(scenario, config)
    assert result.total_cost >= 0
    assert len(result.routes) == len(scenario.vehicles)
    assert sum(len(r.job_ids) for r in result.routes) == 1


@pytest.mark.parametrize("pop_size", [1, 2, 3, 4, 5])
def test_ga_does_not_crash_across_small_population_sizes(pop_size):
    scenario = generate_synthetic_scenario(num_nodes=8, num_jobs=4, num_vehicles=2, seed=1)
    config = OptimizationConfig(algorithm="ga", population_size=pop_size, max_iterations=5, seed=1)
    result = GAOptimizer().optimize(scenario, config)
    assert result.total_cost >= 0
    assert sum(len(r.job_ids) for r in result.routes) == 4


def test_ga_still_reaches_a_good_solution_at_normal_population_sizes():
    """The k=min(k, len(costs)) clamp and the len(p1)<2 crossover guard must
    not change behaviour at ordinary population/job sizes - the clamp is a
    no-op once population_size >= 3, and the guard is a no-op once
    num_jobs >= 2."""
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=9, num_vehicles=3, seed=7)
    config = OptimizationConfig(algorithm="ga", population_size=30, max_iterations=25, seed=7)
    result = GAOptimizer().optimize(scenario, config)
    assert result.is_feasible
    assert sum(len(r.job_ids) for r in result.routes) == 9
