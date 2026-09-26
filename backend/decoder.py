import numpy as np
from typing import List, Tuple, Dict
from models import ProblemScenario, VehicleRoute, Vehicle, Job


def build_route_from_job_sequence(
    vehicle: Vehicle,
    job_objs: List[Job],
    depot_id: int,
    dist_matrix: np.ndarray,
    time_matrix: np.ndarray,
    paths_dict: Dict[Tuple[int, int], List[int]]
) -> VehicleRoute:
    """Builds one vehicle's VehicleRoute from an already-decided job visiting
    order. This is the per-vehicle accumulation loop `decode_random_keys`
    runs for every vehicle, extracted so `optimizers/local_search.py` and
    `optimizers/exact.py` can build a route from a job sequence they arrived
    at some other way (a 2-opt/or-opt move, a DP reconstruction) without
    duplicating this math - the "one shared evaluator" principle applies to
    route construction too, not just scoring."""
    node_path: List[int] = [depot_id]
    total_dist = 0.0
    total_time = 0.0
    total_demand = 0.0
    curr_n = depot_id

    for j in job_objs:
        jn = j.node_id
        total_demand += j.demand
        path_segment = paths_dict.get((curr_n, jn), [curr_n, jn])
        node_path.extend(path_segment[1:])
        total_dist += dist_matrix[curr_n, jn]
        total_time += time_matrix[curr_n, jn] + j.service_time
        curr_n = jn

    return_segment = paths_dict.get((curr_n, depot_id), [curr_n, depot_id])
    node_path.extend(return_segment[1:])
    total_dist += dist_matrix[curr_n, depot_id]
    total_time += time_matrix[curr_n, depot_id]

    cap_exceeded = max(0.0, total_demand - vehicle.capacity)
    time_exceeded = max(0.0, total_time - vehicle.max_route_time)

    return VehicleRoute(
        vehicle_id=vehicle.id,
        job_ids=[j.id for j in job_objs],
        node_path=node_path,
        route_distance=round(total_dist, 2),
        route_travel_time=round(total_time, 2),
        total_demand=round(total_demand, 1),
        capacity_exceeded=round(cap_exceeded, 1),
        time_exceeded=round(time_exceeded, 2)
    )


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

        routes.append(build_route_from_job_sequence(
            v, v_job_objs, depot_id, dist_matrix, time_matrix, paths_dict
        ))

    return routes


def chromosome_from_routes(routes: List[VehicleRoute], scenario: ProblemScenario) -> np.ndarray:
    """Inverse of decode_random_keys: encodes an already-decided per-vehicle
    job order back into a [0,1]^num_jobs random-key vector.

    Needed so an externally-improved route set (e.g. from
    optimizers/local_search.py) can be reinjected into the swarm as a real
    particle position, not just used to report a better fitness number -
    the Lamarckian step in qpso.py's local-search hybrid depends on this.

    For a vehicle at index v_idx (of num_vehicles) whose route visits jobs
    in order [job_0, ..., job_{k-1}], job at position m gets
    sequence_key = (m+1)/(k+1) - evenly spaced in (0, 1), strictly
    increasing with m - and key = (v_idx + sequence_key) / num_vehicles.
    This is the exact inverse of decode_random_keys's own
    `vehicle_idx = min(num_vehicles-1, int(key*num_vehicles))` /
    `sequence_key = key*num_vehicles - vehicle_idx` pair: decoding this key
    recovers v_idx exactly (0 <= sequence_key < 1) and the same relative
    visiting order (sequence_key is strictly increasing with m).
    """
    num_jobs = len(scenario.jobs)
    num_vehicles = len(scenario.vehicles)
    job_id_to_index = {j.id: idx for idx, j in enumerate(scenario.jobs)}
    vehicle_id_to_idx = {v.id: idx for idx, v in enumerate(scenario.vehicles)}

    keys = np.zeros(num_jobs)
    for route in routes:
        v_idx = vehicle_id_to_idx[route.vehicle_id]
        k = len(route.job_ids)
        for m, job_id in enumerate(route.job_ids):
            sequence_key = (m + 1) / (k + 1)
            keys[job_id_to_index[job_id]] = (v_idx + sequence_key) / num_vehicles

    return keys
