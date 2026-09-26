"""
local_search.py
----------------
2-opt / or-opt local search, used to refine QPSO's swarm-found solutions
(see qpso.py's periodic call into `local_search_refine`). Both passes
operate on job-OBJECT sequences per vehicle (not the continuous random-key
encoding).

Performance note (the reason this file looks the way it does): the search
loop below tries thousands of candidate route rearrangements per call.
Scoring each candidate by building a real `VehicleRoute` and calling
`fitness.evaluate_solution` - which is what every optimizer does for a
*final* result - costs Pydantic construction/validation on every single
candidate, which measured at ~90 seconds wall-clock for a single 50-job
QPSO+local-search run (unusable for a live demo). `_route_raw_cost` below
computes the exact same number - the same terms `evaluate_solution` sums
per route, no more, no less - via plain arithmetic with no object
construction, and is what every candidate check in this file actually
calls. `test_local_search.py::test_route_raw_cost_matches_canonical_evaluator`
pins the two together so this fast path can never silently drift from the
one true objective. Real `VehicleRoute` objects (the slower, canonical
path) are built only once, for the final accepted result, in
`local_search_refine`.

First-improvement throughout: each pass accepts the first move it finds
that lowers cost, then restarts scanning from there, until a full scan
finds nothing more.
"""
from typing import Dict, List, Optional, Sequence, Tuple

from models import ProblemScenario, Vehicle, Job, ObjectiveWeights, VehicleRoute, Edge
from decoder import build_route_from_job_sequence
from fitness import evaluate_solution, build_edge_map

Seqs = List[List[Job]]


def _route_raw_cost(
    vehicle: Vehicle,
    job_seq: Sequence[Job],
    depot_id: int,
    dist_matrix,
    time_matrix,
    paths_dict,
    edge_map: Dict[Tuple[int, int], Edge],
    weights: ObjectiveWeights,
) -> float:
    """This route's exact contribution to evaluate_solution's total cost -
    alpha*time + beta*distance + gamma*congestion + this route's own
    capacity/time penalty - computed with no Pydantic object construction.
    See the module docstring for why this exists and how it's kept honest."""
    total_dist = 0.0
    total_time = 0.0
    total_demand = 0.0
    congestion = 0.0
    curr_n = depot_id

    for j in job_seq:
        jn = j.node_id
        total_demand += j.demand
        total_dist += dist_matrix[curr_n, jn]
        total_time += time_matrix[curr_n, jn] + j.service_time
        segment = paths_dict.get((curr_n, jn), (curr_n, jn))
        for u, v in zip(segment[:-1], segment[1:]):
            edge = edge_map.get((u, v))
            if edge is not None and edge.traffic_factor > 1.0:
                congestion += (edge.traffic_factor - 1.0) * edge.base_travel_time
        curr_n = jn

    total_dist += dist_matrix[curr_n, depot_id]
    total_time += time_matrix[curr_n, depot_id]
    return_segment = paths_dict.get((curr_n, depot_id), (curr_n, depot_id))
    for u, v in zip(return_segment[:-1], return_segment[1:]):
        edge = edge_map.get((u, v))
        if edge is not None and edge.traffic_factor > 1.0:
            congestion += (edge.traffic_factor - 1.0) * edge.base_travel_time

    capacity = vehicle.capacity if vehicle.capacity > 0 else 1.0
    max_route_time = vehicle.max_route_time if vehicle.max_route_time > 0 else 1.0
    cap_exceeded = max(0.0, total_demand - vehicle.capacity)
    time_exceeded = max(0.0, total_time - vehicle.max_route_time)
    penalty = 0.0
    if cap_exceeded > 0:
        penalty += weights.penalty_weight * (cap_exceeded / capacity) ** 2
    if time_exceeded > 0:
        penalty += weights.penalty_weight * (time_exceeded / max_route_time) ** 2

    return weights.alpha * total_time + weights.beta * total_dist + weights.gamma * congestion + penalty


def two_opt_pass(
    seqs: Seqs,
    vehicles: List[Vehicle],
    depot_id: int,
    dist_matrix,
    time_matrix,
    paths_dict,
    weights: ObjectiveWeights,
    edge_map: Dict[Tuple[int, int], Edge],
) -> Tuple[Seqs, float]:
    """First-improvement 2-opt: within each vehicle's own route, reverse a
    segment if that lowers the route's cost. Each vehicle's route is
    optimized to convergence independently - a 2-opt move never touches
    another vehicle's route, so there is no need to restart the whole
    multi-vehicle scan after every accepted move."""
    seqs = [list(s) for s in seqs]
    route_cost = [0.0] * len(seqs)

    for v_idx in range(len(seqs)):
        vehicle = vehicles[v_idx]
        seq = seqs[v_idx]
        cur_cost = _route_raw_cost(vehicle, seq, depot_id, dist_matrix, time_matrix, paths_dict, edge_map, weights)

        improved = True
        while improved:
            improved = False
            n = len(seq)
            for i in range(n - 1):
                for j in range(i + 1, n):
                    candidate = seq[:i] + list(reversed(seq[i:j + 1])) + seq[j + 1:]
                    cost = _route_raw_cost(vehicle, candidate, depot_id, dist_matrix, time_matrix, paths_dict, edge_map, weights)
                    if cost < cur_cost - 1e-9:
                        seq, cur_cost = candidate, cost
                        improved = True
                        break
                if improved:
                    break

        seqs[v_idx] = seq
        route_cost[v_idx] = cur_cost

    return seqs, sum(route_cost)


def or_opt_pass(
    seqs: Seqs,
    vehicles: List[Vehicle],
    depot_id: int,
    dist_matrix,
    time_matrix,
    paths_dict,
    weights: ObjectiveWeights,
    edge_map: Dict[Tuple[int, int], Edge],
) -> Tuple[Seqs, float]:
    """First-improvement or-opt: relocate each job to every position in
    every vehicle's route, including a different vehicle than it started
    in, keeping the move if it lowers the combined cost of the (at most
    two) routes it touches.

    Each job's current (vehicle, position) is looked up fresh on every
    attempt rather than trusted from a cached index - an earlier accepted
    move in the same pass shifts every later index in that vehicle's list,
    so a stale cached position would silently point at the wrong job. This
    is the exact bug an earlier or-opt implementation elsewhere hit (it
    surfaced as a duplicated customer on the rendered map, not as a wrong
    fitness number) - worth guarding against explicitly rather than
    rediscovering it.
    """
    seqs = [list(s) for s in seqs]
    route_cost = [
        _route_raw_cost(vehicles[v], seqs[v], depot_id, dist_matrix, time_matrix, paths_dict, edge_map, weights)
        for v in range(len(seqs))
    ]
    job_ids_in_scope = [j.id for seq in seqs for j in seq]

    improved = True
    while improved:
        improved = False
        for job_id in job_ids_in_scope:
            v_from: Optional[int] = None
            from_pos: Optional[int] = None
            job_obj: Optional[Job] = None
            for v_idx, seq in enumerate(seqs):
                for pos, j in enumerate(seq):
                    if j.id == job_id:
                        v_from, from_pos, job_obj = v_idx, pos, j
                        break
                if v_from is not None:
                    break
            if v_from is None:
                continue  # already relocated out of scope this pass - skip

            base_from_seq = seqs[v_from][:from_pos] + seqs[v_from][from_pos + 1:]
            base_from_cost = _route_raw_cost(
                vehicles[v_from], base_from_seq, depot_id, dist_matrix, time_matrix, paths_dict, edge_map, weights
            )

            found = False
            for v_to in range(len(seqs)):
                target_seq = base_from_seq if v_to == v_from else seqs[v_to]
                old_combined = route_cost[v_from] if v_to == v_from else (route_cost[v_from] + route_cost[v_to])

                for pos in range(len(target_seq) + 1):
                    new_to_seq = target_seq[:pos] + [job_obj] + target_seq[pos:]
                    new_to_cost = _route_raw_cost(
                        vehicles[v_to], new_to_seq, depot_id, dist_matrix, time_matrix, paths_dict, edge_map, weights
                    )
                    new_combined = new_to_cost if v_to == v_from else (base_from_cost + new_to_cost)

                    if new_combined < old_combined - 1e-9:
                        if v_to == v_from:
                            seqs[v_from] = new_to_seq
                            route_cost[v_from] = new_to_cost
                        else:
                            seqs[v_from] = base_from_seq
                            seqs[v_to] = new_to_seq
                            route_cost[v_from] = base_from_cost
                            route_cost[v_to] = new_to_cost
                        improved = True
                        found = True
                        break
                if found:
                    break
            if found:
                break

    return seqs, sum(route_cost)


def local_search_refine(
    scenario: ProblemScenario,
    routes: List[VehicleRoute],
    dist_matrix,
    time_matrix,
    paths_dict,
    weights: ObjectiveWeights,
    edge_map: Optional[Dict[Tuple[int, int], Edge]] = None,
    max_passes: int = 2,
) -> List[VehicleRoute]:
    """Runs 2-opt then or-opt (each up to `max_passes` times) on an
    already-decoded route set using the fast raw-cost path throughout, then
    builds real `VehicleRoute` objects exactly once at the end, via the
    same `build_route_from_job_sequence` every other optimizer uses - so
    the final result is scored identically to everything else, even though
    the search that found it wasn't."""
    if edge_map is None:
        edge_map = build_edge_map(scenario)
    depot_id = scenario.depot_node_id
    vehicles = scenario.vehicles
    job_by_id = {j.id: j for j in scenario.jobs}

    seqs: Seqs = [[job_by_id[jid] for jid in r.job_ids] for r in routes]

    for _ in range(max_passes):
        seqs, _ = two_opt_pass(seqs, vehicles, depot_id, dist_matrix, time_matrix, paths_dict, weights, edge_map)
        seqs, _ = or_opt_pass(seqs, vehicles, depot_id, dist_matrix, time_matrix, paths_dict, weights, edge_map)

    return [
        build_route_from_job_sequence(vehicles[v_idx], seq, depot_id, dist_matrix, time_matrix, paths_dict)
        for v_idx, seq in enumerate(seqs)
    ]
