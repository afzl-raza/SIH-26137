import time
import numpy as np
from typing import List, Dict, Tuple
from models import ProblemScenario, OptimizationConfig, OptimizationResult, VehicleRoute, Job
from problem_generator import compute_route_matrix
from fitness import evaluate_solution
from optimizers.base import BaseOptimizer


class GreedyOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__(name="Greedy (Nearest Neighbour)")

    def optimize(
        self,
        scenario: ProblemScenario,
        config: OptimizationConfig
    ) -> OptimizationResult:
        start_time = time.perf_counter()

        dist_matrix, time_matrix, paths_dict = compute_route_matrix(scenario).as_tuple()
        depot_id = scenario.depot_node_id

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
            v_time = 0.0
            curr_node = depot_id

            while unvisited:
                # Find nearest unvisited job
                best_job = None
                best_time_leg = float('inf')
                best_idx = -1

                for idx, job in enumerate(unvisited):
                    t_leg = time_matrix[curr_node, job.node_id] + job.service_time
                    t_return = time_matrix[job.node_id, depot_id]

                    # Check feasibility
                    if (v_load + job.demand <= v.capacity) and (v_time + t_leg + t_return <= v.max_route_time):
                        if t_leg < best_time_leg:
                            best_time_leg = t_leg
                            best_job = job
                            best_idx = idx

                if best_job is not None:
                    v_jobs.append(best_job)
                    v_load += best_job.demand
                    v_time += best_time_leg
                    curr_node = best_job.node_id
                    unvisited.pop(best_idx)
                else:
                    # Vehicle cannot take more jobs within constraints
                    break

            # Calculate path & metrics for this vehicle
            node_path = [depot_id]
            total_dist = 0.0
            total_time = 0.0
            cn = depot_id

            for j in v_jobs:
                jn = j.node_id
                node_path.extend(paths_dict.get((cn, jn), [cn, jn])[1:])
                total_dist += dist_matrix[cn, jn]
                total_time += time_matrix[cn, jn] + j.service_time
                cn = jn

            node_path.extend(paths_dict.get((cn, depot_id), [cn, depot_id])[1:])
            total_dist += dist_matrix[cn, depot_id]
            total_time += time_matrix[cn, depot_id]

            routes.append(VehicleRoute(
                vehicle_id=v.id,
                job_ids=[j.id for j in v_jobs],
                node_path=node_path,
                route_distance=round(total_dist, 2),
                route_travel_time=round(total_time, 2),
                total_demand=round(v_load, 1),
                capacity_exceeded=round(max(0.0, v_load - v.capacity), 1),
                time_exceeded=round(max(0.0, total_time - v.max_route_time), 2)
            ))

        # If any jobs remain unvisited (due to tight vehicle limits), force assign to vehicle with min load
        while unvisited:
            j = unvisited.pop(0)
            min_v_idx = int(np.argmin([r.total_demand for r in routes]))
            r = routes[min_v_idx]
            r.job_ids.append(j.id)
            r.total_demand += j.demand

            # Rebuild path
            v_map = {v.id: v for v in scenario.vehicles}
            v = v_map[r.vehicle_id]
            job_map = {job.id: job for job in scenario.jobs}
            n_path = [depot_id]
            t_dist = 0.0
            t_time = 0.0
            cn = depot_id
            for j_id in r.job_ids:
                job_obj = job_map[j_id]
                jn = job_obj.node_id
                n_path.extend(paths_dict.get((cn, jn), [cn, jn])[1:])
                t_dist += dist_matrix[cn, jn]
                t_time += time_matrix[cn, jn] + job_obj.service_time
                cn = jn
            n_path.extend(paths_dict.get((cn, depot_id), [cn, depot_id])[1:])
            t_dist += dist_matrix[cn, depot_id]
            t_time += time_matrix[cn, depot_id]

            r.node_path = n_path
            r.route_distance = round(t_dist, 2)
            r.route_travel_time = round(t_time, 2)
            r.capacity_exceeded = round(max(0.0, r.total_demand - v.capacity), 1)
            r.time_exceeded = round(max(0.0, t_time - v.max_route_time), 2)

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
