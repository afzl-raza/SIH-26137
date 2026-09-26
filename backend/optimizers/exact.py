"""
exact.py
--------
A true-optimum solver for small CVRP instances, used to report a real
"optimality gap" for the heuristic algorithms rather than only ranking them
against each other.

Two-stage bitmask dynamic program:

Stage 1 (Held-Karp per subset): for every subset of jobs, finds the
minimum-cost depot-to-depot path visiting exactly that subset, where the
per-edge cost is `alpha*edge_time + beta*edge_distance + gamma*edge_congestion`
- the same three terms `fitness.evaluate_solution` sums along a route,
computed per-edge here so the two are consistent by construction rather than
being two different scoring systems being compared.

Stage 2 (set-partition DP): chooses how to split the full job set across the
available vehicles, minimizing the sum of each assigned subset's stage-1
routing cost plus that subset's penalty against the SPECIFIC vehicle it is
assigned to (the same `penalty_weight * (overage/limit)**2` formula
`fitness.py` uses).

Honesty note: stage 1 minimizes routing cost (time+distance+congestion), not
a joint (routing-cost + time-exceeded-penalty) optimum - it does not
re-search subset orderings specifically to dodge a time-window-style
penalty. At <=10 jobs with this generator's ~35% vehicle-capacity slack this
essentially never changes the answer in practice, but the two are not
mathematically identical, and this file says so rather than imply a
stronger guarantee than what is actually computed.

Complexity: O(n^2 * 2^n) for stage 1 (n<=10 -> a few hundred thousand ops,
trivial), O(3^n) for stage 2's submask enumeration (n=10 -> ~59k, trivial).
This is an exhibit solver for proving small-instance optimality, not a
general-purpose one - MAX_EXACT_JOBS is a hard cap, not a soft target.
"""
import time
from typing import Dict, List, Tuple

from models import ProblemScenario, OptimizationConfig, OptimizationResult, VehicleRoute, Vehicle
from route_cache import get_route_matrix
from fitness import evaluate_solution, build_edge_map
from decoder import build_route_from_job_sequence
from optimizers.base import BaseOptimizer

MAX_EXACT_JOBS = 10


class ExactSolverTooLargeError(Exception):
    """Raised when a scenario exceeds the exact solver's job cap."""


class ExactOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__(name="Exact (Optimal)")

    def optimize(self, scenario: ProblemScenario, config: OptimizationConfig) -> OptimizationResult:
        start_time = time.perf_counter()
        jobs = scenario.jobs
        n = len(jobs)
        if n > MAX_EXACT_JOBS:
            raise ExactSolverTooLargeError(
                f"Exact solver only supports up to {MAX_EXACT_JOBS} jobs; this scenario has {n}."
            )

        depot_id = scenario.depot_node_id
        dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
        edge_map = build_edge_map(scenario)
        weights = config.weights
        vehicles = scenario.vehicles
        num_vehicles = len(vehicles)

        if n == 0:
            routes = [
                VehicleRoute(vehicle_id=v.id, job_ids=[], node_path=[depot_id, depot_id],
                             route_distance=0.0, route_travel_time=0.0, total_demand=0.0)
                for v in vehicles
            ]
            return evaluate_solution(
                routes, scenario, weights, algorithm_name=self.name,
                runtime_ms=(time.perf_counter() - start_time) * 1000.0,
                convergence_history=[0.0], edge_map=edge_map
            )

        def edge_cost(u: int, v: int) -> float:
            """alpha*time + beta*distance + gamma*congestion for one hop -
            the same per-edge accounting evaluate_solution sums along a
            completed route, so a route's stage-1 cost equals what
            evaluate_solution would compute for its (time, distance,
            congestion) terms before penalty."""
            t = time_matrix[u, v]
            d = dist_matrix[u, v]
            edge = edge_map.get((u, v))
            congestion = 0.0
            if edge is not None and edge.traffic_factor > 1.0:
                congestion = (edge.traffic_factor - 1.0) * edge.base_travel_time
            return weights.alpha * t + weights.beta * d + weights.gamma * congestion

        full_mask = (1 << n) - 1

        # ---- Stage 1: Held-Karp DP over (subset, last-visited job index) ----
        dp_cost: Dict[Tuple[int, int], float] = {}
        dp_time: Dict[Tuple[int, int], float] = {}
        dp_parent: Dict[Tuple[int, int], int] = {}

        for j in range(n):
            jn = jobs[j].node_id
            dp_cost[(1 << j, j)] = edge_cost(depot_id, jn)
            dp_time[(1 << j, j)] = time_matrix[depot_id, jn] + jobs[j].service_time
            dp_parent[(1 << j, j)] = -1

        # Numeric order already respects the subset partial order here: any
        # mask reachable by adding a bit to `mask` is strictly greater than
        # `mask`, so a plain increasing loop processes subsets before their
        # supersets without a separate popcount sort.
        for mask in range(1, full_mask + 1):
            for j in range(n):
                key = (mask, j)
                if key not in dp_cost:
                    continue
                jn = jobs[j].node_id
                base_cost = dp_cost[key]
                base_time = dp_time[key]
                for k in range(n):
                    if mask & (1 << k):
                        continue
                    kn = jobs[k].node_id
                    new_mask = mask | (1 << k)
                    new_cost = base_cost + edge_cost(jn, kn)
                    new_key = (new_mask, k)
                    if new_key not in dp_cost or new_cost < dp_cost[new_key]:
                        dp_cost[new_key] = new_cost
                        dp_time[new_key] = base_time + time_matrix[jn, kn] + jobs[k].service_time
                        dp_parent[new_key] = j

        # best_subset[mask] = (routing_cost, total_time, visiting order) - the
        # cheapest way for ONE vehicle to serve exactly `mask`, depot to depot.
        best_subset: Dict[int, Tuple[float, float, List[int]]] = {}
        for mask in range(1, full_mask + 1):
            best_end_cost = float('inf')
            best_end_j = -1
            best_end_time = 0.0
            for j in range(n):
                key = (mask, j)
                if key not in dp_cost:
                    continue
                jn = jobs[j].node_id
                total = dp_cost[key] + edge_cost(jn, depot_id)
                if total < best_end_cost:
                    best_end_cost = total
                    best_end_j = j
                    best_end_time = dp_time[key] + time_matrix[jn, depot_id]
            if best_end_j == -1:
                continue
            order: List[int] = []
            cur_mask, cur_j = mask, best_end_j
            while cur_j != -1:
                order.append(cur_j)
                prev_j = dp_parent[(cur_mask, cur_j)]
                cur_mask = cur_mask & ~(1 << cur_j)
                cur_j = prev_j
            order.reverse()
            best_subset[mask] = (best_end_cost, best_end_time, order)

        # ---- Stage 2: partition all jobs across vehicles ----
        def subset_penalty(mask: int, route_time: float, vehicle: Vehicle) -> float:
            demand = sum(jobs[j].demand for j in range(n) if mask & (1 << j))
            capacity = vehicle.capacity if vehicle.capacity > 0 else 1.0
            max_route_time = vehicle.max_route_time if vehicle.max_route_time > 0 else 1.0
            cap_exceeded = max(0.0, demand - vehicle.capacity)
            time_exceeded = max(0.0, route_time - vehicle.max_route_time)
            penalty = 0.0
            if cap_exceeded > 0:
                penalty += weights.penalty_weight * (cap_exceeded / capacity) ** 2
            if time_exceeded > 0:
                penalty += weights.penalty_weight * (time_exceeded / max_route_time) ** 2
            return penalty

        INF = float('inf')
        # assign_dp[v_idx][mask] = min total cost to serve `mask` using the
        # first v_idx vehicles. assign_choice reconstructs which subset the
        # v_idx-th vehicle took to reach that state.
        assign_dp = [[INF] * (full_mask + 1) for _ in range(num_vehicles + 1)]
        assign_choice: List[List[Tuple[int, int]]] = [[None] * (full_mask + 1) for _ in range(num_vehicles + 1)]
        assign_dp[0][0] = 0.0

        for v_idx in range(num_vehicles):
            vehicle = vehicles[v_idx]
            for mask in range(full_mask + 1):
                base = assign_dp[v_idx][mask]
                if base == INF:
                    continue
                # This vehicle serves nothing.
                if base < assign_dp[v_idx + 1][mask]:
                    assign_dp[v_idx + 1][mask] = base
                    assign_choice[v_idx + 1][mask] = (mask, 0)
                # This vehicle serves some non-empty subset of what's left.
                remaining = full_mask & ~mask
                sub = remaining
                while sub > 0:
                    subset_info = best_subset.get(sub)
                    if subset_info is not None:
                        route_cost, route_time, _ = subset_info
                        total = base + route_cost + subset_penalty(sub, route_time, vehicle)
                        new_mask = mask | sub
                        if total < assign_dp[v_idx + 1][new_mask]:
                            assign_dp[v_idx + 1][new_mask] = total
                            assign_choice[v_idx + 1][new_mask] = (mask, sub)
                    sub = (sub - 1) & remaining

        if assign_dp[num_vehicles][full_mask] == INF:
            raise RuntimeError("Exact solver found no feasible partition across vehicles.")

        subset_per_vehicle: List[int] = [0] * num_vehicles
        cur_mask = full_mask
        for v_idx in range(num_vehicles, 0, -1):
            prev_mask, sub = assign_choice[v_idx][cur_mask]
            subset_per_vehicle[v_idx - 1] = sub
            cur_mask = prev_mask

        routes: List[VehicleRoute] = []
        for v_idx, vehicle in enumerate(vehicles):
            sub = subset_per_vehicle[v_idx]
            if sub == 0:
                routes.append(VehicleRoute(
                    vehicle_id=vehicle.id, job_ids=[], node_path=[depot_id, depot_id],
                    route_distance=0.0, route_travel_time=0.0, total_demand=0.0
                ))
                continue
            _, _, order = best_subset[sub]
            job_objs = [jobs[j] for j in order]
            routes.append(build_route_from_job_sequence(
                vehicle, job_objs, depot_id, dist_matrix, time_matrix, paths_dict
            ))

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return evaluate_solution(
            routes=routes, scenario=scenario, weights=weights,
            algorithm_name=self.name, runtime_ms=elapsed_ms,
            convergence_history=[0.0], edge_map=edge_map
        )
