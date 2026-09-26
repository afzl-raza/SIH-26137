import time
import numpy as np
from typing import List, Dict, Optional, Tuple
from models import ProblemScenario, OptimizationConfig, OptimizationResult, VehicleRoute, Job, Vehicle
from route_cache import get_route_matrix
from fitness import evaluate_solution
from schedule import simulate_route
from optimizers.base import BaseOptimizer


class GreedyOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__(name="Greedy (Nearest Neighbour)")

    def optimize(
        self,
        scenario: ProblemScenario,
        config: OptimizationConfig,
        route_matrix: Optional[Tuple[np.ndarray, np.ndarray, Dict[Tuple[int, int], List[int]]]] = None,
    ) -> OptimizationResult:
        """`route_matrix` lets a caller that already fetched
        route_cache.get_route_matrix(scenario).as_tuple() (qpso_memetic's
        greedy warm start) pass it straight in instead of paying a second
        cache lookup for the same scenario. Fetched internally when omitted,
        so every other caller (benchmark, /api/optimize, tests) is
        unaffected."""
        start_time = time.perf_counter()

        if route_matrix is not None:
            dist_matrix, time_matrix, paths_dict = route_matrix
        else:
            dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
        depot_id = scenario.depot_node_id
        job_map: Dict[int, Job] = {j.id: j for j in scenario.jobs}

        unvisited = list(scenario.jobs)
        routes: List[VehicleRoute] = []

        for v in scenario.vehicles:
            if not unvisited:
                # Add empty route if no jobs remaining
                routes.append(VehicleRoute(
                    vehicle_id=v.id,
                    job_ids=[],
                    node_path=[depot_id, depot_id],
                    route_distance=0.0,
                    route_travel_time=0.0,
                    total_demand=0.0
                ))
                continue

            v_jobs: List[Job] = []
            v_load = 0.0
            v_clock = 0.0  # departure time at curr_node; 0 = depot at shift start
            curr_node = depot_id

            while unvisited:
                # Find the unvisited job the vehicle can start serving soonest
                # among the feasible ones, tie-broken by earliest due_time.
                # Both are no-ops when every job's ready_time/due_time is
                # None: wait is then always 0, so rank_key reduces to the
                # original t_leg-only ranking, and due_key is +inf for every
                # candidate, so ties resolve exactly as before (first
                # candidate found wins).
                best_job = None
                best_rank_key = float('inf')
                best_due_key = float('inf')
                best_idx = -1
                best_departure = None

                for idx, job in enumerate(unvisited):
                    t_leg = time_matrix[curr_node, job.node_id] + job.service_time
                    t_return = time_matrix[job.node_id, depot_id]

                    arrival = v_clock + time_matrix[curr_node, job.node_id]
                    wait = 0.0 if job.ready_time is None else max(0.0, job.ready_time - arrival)
                    service_start = arrival + wait
                    is_late = job.due_time is not None and service_start > job.due_time
                    departure = service_start + job.service_time
                    completion_if_chosen = departure + t_return

                    capacity_ok = v_load + job.demand <= v.capacity
                    time_ok = completion_if_chosen <= v.max_route_time

                    if capacity_ok and time_ok and not is_late:
                        # Rank by time-until-service-start (t_leg + wait), not
                        # raw travel distance - a job that's geometrically
                        # nearer but not open yet for a long time should lose
                        # to one the vehicle can actually start serving sooner.
                        rank_key = t_leg + wait
                        due_key = job.due_time if job.due_time is not None else float('inf')
                        if (rank_key, due_key) < (best_rank_key, best_due_key):
                            best_rank_key = rank_key
                            best_due_key = due_key
                            best_job = job
                            best_idx = idx
                            best_departure = departure

                if best_job is not None:
                    v_jobs.append(best_job)
                    v_load += best_job.demand
                    v_clock = best_departure
                    curr_node = best_job.node_id
                    unvisited.pop(best_idx)
                else:
                    # Vehicle cannot take more jobs within constraints
                    break

            # Calculate path & metrics for this vehicle. Distance/node_path
            # stay a plain leg sum (schedule.simulate_route only owns timing).
            node_path = [depot_id]
            total_dist = 0.0
            cn = depot_id

            for j in v_jobs:
                jn = j.node_id
                node_path.extend(paths_dict.get((cn, jn), [cn, jn])[1:])
                total_dist += dist_matrix[cn, jn]
                cn = jn

            node_path.extend(paths_dict.get((cn, depot_id), [cn, depot_id])[1:])
            total_dist += dist_matrix[cn, depot_id]

            job_ids = [j.id for j in v_jobs]
            sched = simulate_route(job_ids, v, depot_id, time_matrix, job_map)

            routes.append(VehicleRoute(
                vehicle_id=v.id,
                job_ids=job_ids,
                node_path=node_path,
                route_distance=round(total_dist, 2),
                route_travel_time=round(sched.travel_time, 2),
                total_demand=round(v_load, 1),
                capacity_exceeded=round(max(0.0, v_load - v.capacity), 1),
                time_exceeded=round(max(0.0, sched.travel_time - v.max_route_time), 2),
                stops=sched.stops,
                wait_time=round(sched.wait_time, 2),
                lateness=round(sched.lateness, 2),
                late_jobs=sched.late_jobs
            ))

        # If any jobs remain unvisited (due to tight vehicle limits), force
        # assign to vehicle with min load. These may end up late - windows
        # here are a soft constraint, so simulate_route reports the lateness
        # honestly rather than the job being rejected.
        v_map: Dict[int, Vehicle] = {v.id: v for v in scenario.vehicles}
        while unvisited:
            j = unvisited.pop(0)
            min_v_idx = int(np.argmin([r.total_demand for r in routes]))
            r = routes[min_v_idx]
            r.job_ids.append(j.id)
            r.total_demand += j.demand

            # Rebuild path
            v = v_map[r.vehicle_id]
            n_path = [depot_id]
            t_dist = 0.0
            cn = depot_id
            for j_id in r.job_ids:
                job_obj = job_map[j_id]
                jn = job_obj.node_id
                n_path.extend(paths_dict.get((cn, jn), [cn, jn])[1:])
                t_dist += dist_matrix[cn, jn]
                cn = jn
            n_path.extend(paths_dict.get((cn, depot_id), [cn, depot_id])[1:])
            t_dist += dist_matrix[cn, depot_id]

            sched = simulate_route(r.job_ids, v, depot_id, time_matrix, job_map)

            r.node_path = n_path
            r.route_distance = round(t_dist, 2)
            r.route_travel_time = round(sched.travel_time, 2)
            r.capacity_exceeded = round(max(0.0, r.total_demand - v.capacity), 1)
            r.time_exceeded = round(max(0.0, sched.travel_time - v.max_route_time), 2)
            r.stops = sched.stops
            r.wait_time = round(sched.wait_time, 2)
            r.lateness = round(sched.lateness, 2)
            r.late_jobs = sched.late_jobs

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Evaluated through central objective function
        result = evaluate_solution(
            routes=routes,
            scenario=scenario,
            weights=config.weights,
            algorithm_name=self.name,
            runtime_ms=elapsed_ms,
            convergence_history=[0.0]
        )
        return result
