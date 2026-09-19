import numpy as np
from typing import List, Tuple, Dict
from models import ProblemScenario, VehicleRoute, Vehicle, Job


def decode_random_keys(
    keys: np.ndarray,
    scenario: ProblemScenario,
    dist_matrix: np.ndarray,
    time_matrix: np.ndarray,
    paths_dict: Dict[Tuple[int, int], List[int]]
) -> List[VehicleRoute]:
    """
    Decodes continuous random keys in [0, 1]^M into discrete multi-vehicle CVRP routes.
    Uses Random-Key Vehicle Assignment:
      - For job i with key x_i in [0, 1]:
        vehicle_idx = min(num_vehicles - 1, int(x_i * num_vehicles))
        sequence_key = x_i * num_vehicles - vehicle_idx
      - Within each vehicle, jobs are visited in increasing order of sequence_key.
    This allows the optimizer (QPSO/PSO/GA) to search vehicle assignments and route order simultaneously.
    """
    jobs = scenario.jobs
    num_jobs = len(jobs)
    vehicles = scenario.vehicles
    num_vehicles = len(vehicles)
    depot_id = scenario.depot_node_id

    if num_jobs == 0:
        return []

    # Group jobs by assigned vehicle
    vehicle_jobs: Dict[int, List[Tuple[float, Job]]] = {v_idx: [] for v_idx in range(num_vehicles)}

    for idx, key_val in enumerate(keys):
        job = jobs[idx]
        v_idx = min(num_vehicles - 1, int(key_val * num_vehicles))
        seq_key = key_val * num_vehicles - v_idx
        vehicle_jobs[v_idx].append((seq_key, job))

    routes: List[VehicleRoute] = []

    for v_idx, v in enumerate(vehicles):
        assigned = vehicle_jobs[v_idx]
        # Sort jobs within vehicle by sequence key
        assigned.sort(key=lambda item: item[0])
        v_job_objs = [item[1] for item in assigned]

        node_path: List[int] = [depot_id]
        total_dist = 0.0
        total_time = 0.0
        total_demand = 0.0
        curr_n = depot_id

        for j in v_job_objs:
            jn = j.node_id
            total_demand += j.demand
            path_segment = paths_dict.get((curr_n, jn), [curr_n, jn])
            node_path.extend(path_segment[1:])
            total_dist += dist_matrix[curr_n, jn]
            total_time += time_matrix[curr_n, jn] + j.service_time
            curr_n = jn

        # Return to depot
        return_segment = paths_dict.get((curr_n, depot_id), [curr_n, depot_id])
        node_path.extend(return_segment[1:])
        total_dist += dist_matrix[curr_n, depot_id]
        total_time += time_matrix[curr_n, depot_id]

        cap_exceeded = max(0.0, total_demand - v.capacity)
        time_exceeded = max(0.0, total_time - v.max_route_time)

        routes.append(VehicleRoute(
            vehicle_id=v.id,
            job_ids=[j.id for j in v_job_objs],
            node_path=node_path,
            route_distance=round(total_dist, 2),
            route_travel_time=round(total_time, 2),
            total_demand=round(total_demand, 1),
            capacity_exceeded=round(cap_exceeded, 1),
            time_exceeded=round(time_exceeded, 2)
        ))

    return routes
