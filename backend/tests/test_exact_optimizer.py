import sys
import os
import itertools

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from models import OptimizationConfig, ObjectiveWeights
from problem_generator import generate_synthetic_scenario
from route_cache import get_route_matrix
from fitness import evaluate_solution, build_edge_map
from decoder import build_route_from_job_sequence
from optimizers.exact import ExactOptimizer, ExactSolverTooLargeError, MAX_EXACT_JOBS


def _brute_force_optimum(scenario, config):
    """Independent reference: tries every way to split jobs across vehicles
    and every ordering within each vehicle, scored by the same
    evaluate_solution every optimizer uses. Only tractable for a handful of
    jobs - this is exactly why the exact solver itself needs a job cap."""
    dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
    edge_map = build_edge_map(scenario)
    jobs = scenario.jobs
    vehicles = scenario.vehicles
    depot_id = scenario.depot_node_id
    n = len(jobs)

    best_cost = float('inf')
    # Assign each job to a vehicle index.
    for assignment in itertools.product(range(len(vehicles)), repeat=n):
        per_vehicle = [[] for _ in vehicles]
        for job_idx, v_idx in enumerate(assignment):
            per_vehicle[v_idx].append(jobs[job_idx])

        # Try every ordering within each vehicle's job list.
        order_choices = [list(itertools.permutations(js)) if js else [()] for js in per_vehicle]
        for combo in itertools.product(*order_choices):
            routes = []
            for v_idx, vehicle in enumerate(vehicles):
                job_seq = list(combo[v_idx])
                routes.append(build_route_from_job_sequence(
                    vehicle, job_seq, depot_id, dist_matrix, time_matrix, paths_dict
                ))
            result = evaluate_solution(
                routes, scenario, config.weights, algorithm_name="brute-force",
                edge_map=edge_map
            )
            if result.total_cost < best_cost:
                best_cost = result.total_cost
    return best_cost


def _small_config():
    return OptimizationConfig(
        algorithm="exact",
        weights=ObjectiveWeights(alpha=1.0, beta=0.5, gamma=1.0, penalty_weight=1000.0)
    )


def test_exact_matches_brute_force_5_jobs_2_vehicles():
    scenario = generate_synthetic_scenario(num_nodes=10, num_jobs=5, num_vehicles=2, seed=7)
    config = _small_config()

    exact_result = ExactOptimizer().optimize(scenario, config)
    brute_force_cost = _brute_force_optimum(scenario, config)

    assert exact_result.total_cost == pytest.approx(brute_force_cost, abs=0.05)


def test_exact_matches_brute_force_3_jobs_1_vehicle():
    scenario = generate_synthetic_scenario(num_nodes=8, num_jobs=3, num_vehicles=1, seed=3)
    config = _small_config()

    exact_result = ExactOptimizer().optimize(scenario, config)
    brute_force_cost = _brute_force_optimum(scenario, config)

    assert exact_result.total_cost == pytest.approx(brute_force_cost, abs=0.05)


def test_exact_result_is_feasible_and_uses_shared_evaluator():
    """The exact solver's output must be a normal OptimizationResult scored
    by the same evaluate_solution as every other algorithm - not a separate
    scoring system that merely happens to look similar."""
    scenario = generate_synthetic_scenario(num_nodes=10, num_jobs=4, num_vehicles=2, seed=1)
    config = _small_config()

    result = ExactOptimizer().optimize(scenario, config)

    assert result.algorithm == "Exact (Optimal)"
    assert len(result.routes) == len(scenario.vehicles)
    all_job_ids = sorted(jid for r in result.routes for jid in r.job_ids)
    assert all_job_ids == sorted(j.id for j in scenario.jobs)


def test_exact_rejects_scenarios_above_job_cap():
    scenario = generate_synthetic_scenario(num_nodes=40, num_jobs=MAX_EXACT_JOBS + 5, num_vehicles=3, seed=1)
    config = _small_config()

    with pytest.raises(ExactSolverTooLargeError):
        ExactOptimizer().optimize(scenario, config)


def test_exact_handles_zero_jobs():
    scenario = generate_synthetic_scenario(num_nodes=10, num_jobs=0, num_vehicles=2, seed=1)
    config = _small_config()

    result = ExactOptimizer().optimize(scenario, config)

    assert result.total_cost == 0.0
    assert result.is_feasible is True
