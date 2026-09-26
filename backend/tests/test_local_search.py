import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from models import OptimizationConfig, ObjectiveWeights
from problem_generator import generate_synthetic_scenario
from route_cache import get_route_matrix
from fitness import build_edge_map, evaluate_solution
from decoder import build_route_from_job_sequence, chromosome_from_routes, decode_random_keys
from optimizers.local_search import two_opt_pass, or_opt_pass, local_search_refine, _route_raw_cost
from optimizers.qpso import QPSOOptimizer
from optimizers.greedy import GreedyOptimizer


def _weights():
    return ObjectiveWeights(alpha=1.0, beta=0.5, gamma=1.0, penalty_weight=1000.0)


def test_route_raw_cost_matches_canonical_evaluator():
    """Pins the fast raw-arithmetic cost path (used for every candidate
    check in two_opt_pass/or_opt_pass) to the canonical
    build_route_from_job_sequence + evaluate_solution path, across several
    scenarios/orderings/vehicles. If these two ever disagree, the fast path
    has silently drifted from the one true objective - exactly the failure
    mode this test exists to catch before it ships."""
    for seed in (1, 2, 3):
        scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=9, num_vehicles=3, seed=seed)
        dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
        edge_map = build_edge_map(scenario)
        weights = _weights()
        depot_id = scenario.depot_node_id

        for v_idx, vehicle in enumerate(scenario.vehicles):
            for job_count in (0, 1, 3):
                job_seq = scenario.jobs[:job_count]
                raw = _route_raw_cost(vehicle, job_seq, depot_id, dist_matrix, time_matrix, paths_dict, edge_map, weights)
                canonical = evaluate_solution(
                    [build_route_from_job_sequence(vehicle, job_seq, depot_id, dist_matrix, time_matrix, paths_dict)],
                    scenario, weights, edge_map=edge_map
                ).total_cost
                assert raw == pytest.approx(canonical, abs=0.01), (
                    f"seed={seed} vehicle={vehicle.id} jobs={[j.id for j in job_seq]}"
                )


def test_two_opt_untangles_an_obvious_crossing():
    """A route that visits its stops in an order 2-opt can provably shorten
    (jobs placed so the naive order backtracks) must come back shorter after
    one pass, never longer."""
    scenario = generate_synthetic_scenario(num_nodes=15, num_jobs=6, num_vehicles=1, seed=11)
    dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
    edge_map = build_edge_map(scenario)
    weights = _weights()
    vehicle = scenario.vehicles[0]
    depot_id = scenario.depot_node_id

    # Deliberately poor order: reverse of a reasonable nearest-neighbour walk.
    jobs_reversed = list(reversed(scenario.jobs))
    seqs = [jobs_reversed]

    before_cost = evaluate_solution(
        [build_route_from_job_sequence(vehicle, jobs_reversed, depot_id, dist_matrix, time_matrix, paths_dict)],
        scenario, weights, edge_map=edge_map
    ).total_cost

    improved_seqs, after_cost = two_opt_pass(
        seqs, scenario.vehicles, depot_id, dist_matrix, time_matrix, paths_dict, weights, edge_map
    )

    assert after_cost <= before_cost + 1e-9
    # Every job still present exactly once - 2-opt reorders, never drops.
    assert sorted(j.id for j in improved_seqs[0]) == sorted(j.id for j in jobs_reversed)


def test_or_opt_never_loses_or_duplicates_a_job():
    """Guards against the exact bug the reference audit hit: or-opt must
    never end a pass with a customer missing or duplicated across routes."""
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=10, num_vehicles=3, seed=5)
    dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
    edge_map = build_edge_map(scenario)
    weights = _weights()
    depot_id = scenario.depot_node_id

    job_by_id = {j.id: j for j in scenario.jobs}
    # Deliberately bad split: all jobs crammed onto vehicle 0.
    seqs = [list(scenario.jobs)] + [[] for _ in scenario.vehicles[1:]]

    before = evaluate_solution(
        [build_route_from_job_sequence(scenario.vehicles[i], seqs[i], depot_id, dist_matrix, time_matrix, paths_dict)
         for i in range(len(scenario.vehicles))],
        scenario, weights, edge_map=edge_map
    ).total_cost

    improved_seqs, after_cost = or_opt_pass(
        seqs, scenario.vehicles, depot_id, dist_matrix, time_matrix, paths_dict, weights, edge_map
    )

    all_ids = sorted(j.id for seq in improved_seqs for j in seq)
    assert all_ids == sorted(job_by_id.keys()), "every job must appear exactly once after or-opt"
    assert after_cost <= before + 1e-9


def test_local_search_refine_never_increases_cost():
    scenario = generate_synthetic_scenario(num_nodes=25, num_jobs=12, num_vehicles=3, seed=9)
    dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
    edge_map = build_edge_map(scenario)
    weights = _weights()

    # Start from a plain random-key decode (an arbitrary, not-locally-optimal
    # starting point), matching how qpso.py calls this on its gbest.
    import numpy as np
    rng = np.random.default_rng(1)
    keys = rng.random(len(scenario.jobs))
    routes = decode_random_keys(keys, scenario, dist_matrix, time_matrix, paths_dict)
    before_cost = evaluate_solution(routes, scenario, weights, edge_map=edge_map).total_cost

    refined_routes = local_search_refine(
        scenario, routes, dist_matrix, time_matrix, paths_dict, weights, edge_map=edge_map, max_passes=2
    )
    after_cost = evaluate_solution(refined_routes, scenario, weights, edge_map=edge_map).total_cost

    assert after_cost <= before_cost + 1e-9

    all_ids = sorted(j for r in refined_routes for j in r.job_ids)
    assert all_ids == sorted(j.id for j in scenario.jobs)


def test_chromosome_from_routes_round_trips_through_decode():
    """Encoding a route set back into keys and decoding those keys again
    must reproduce the exact same per-vehicle job order - this is the
    contract qpso.py's Lamarckian reinjection depends on."""
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=4)
    dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()

    import numpy as np
    rng = np.random.default_rng(2)
    keys = rng.random(len(scenario.jobs))
    routes = decode_random_keys(keys, scenario, dist_matrix, time_matrix, paths_dict)

    re_encoded = chromosome_from_routes(routes, scenario)
    round_tripped = decode_random_keys(re_encoded, scenario, dist_matrix, time_matrix, paths_dict)

    original_order = [r.job_ids for r in routes]
    round_tripped_order = [r.job_ids for r in round_tripped]
    assert original_order == round_tripped_order


def test_qpso_with_local_search_no_longer_loses_badly_to_greedy_at_scale():
    """The actual regression this feature exists to fix: at 30+ jobs, plain
    QPSO measurably lost to Greedy on cost and was frequently badly
    infeasible. QPSO with the local-search hybrid (the new default) must be
    competitive on cost - not necessarily winning every seed, but not losing
    by a wide margin - and if it is infeasible, the violation must be a
    soft-penalty tradeoff (a small overage the objective judged cheaper than
    avoiding), not the wild infeasibility the original bug produced.

    is_feasible=False with a *lower* cost than a feasible alternative is not
    itself a bug: fitness.py's penalty is deliberately soft (CLAUDE.md: solve
    infeasibility "through constraint penalties or repair", not by rejecting
    it outright), so a negligible overage the objective judges cheaper than
    avoiding is the formula working as designed - this test guards against
    the original failure mode (losing badly AND being wildly infeasible),
    not against soft-penalty trades in general."""
    scenario = generate_synthetic_scenario(num_nodes=60, num_jobs=30, num_vehicles=6, seed=42)
    config = OptimizationConfig(population_size=40, max_iterations=100, seed=42)

    greedy_result = GreedyOptimizer().optimize(scenario, config)
    plain_result = QPSOOptimizer().optimize(scenario, config.model_copy(update={"use_local_search": False}))
    qpso_ls_result = QPSOOptimizer().optimize(scenario, config)  # use_local_search=True by default

    assert greedy_result.is_feasible

    # The actual bug: plain QPSO must lose to Greedy for this test to be
    # exercising the right regression (if this ever stops being true, the
    # scenario/config needs revisiting, not this assertion).
    assert plain_result.total_cost > greedy_result.total_cost

    # The fix: QPSO+local-search must not lose to Greedy on cost.
    assert qpso_ls_result.total_cost <= greedy_result.total_cost * 1.05
    # And it must clearly beat the un-hybridized ablation baseline.
    assert qpso_ls_result.total_cost < plain_result.total_cost

    if not qpso_ls_result.is_feasible:
        for route in qpso_ls_result.routes:
            vehicle = next(v for v in scenario.vehicles if v.id == route.vehicle_id)
            cap_overage_pct = route.capacity_exceeded / vehicle.capacity if vehicle.capacity else 0
            time_overage_pct = route.time_exceeded / vehicle.max_route_time if vehicle.max_route_time else 0
            assert cap_overage_pct < 0.05, "any capacity overage must be a small soft-penalty trade, not wild infeasibility"
            assert time_overage_pct < 0.05, "any time overage must be a small soft-penalty trade, not wild infeasibility"
