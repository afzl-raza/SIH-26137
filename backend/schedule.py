"""The single authoritative route-timing engine.

Before time windows, `decoder.py` and `optimizers/greedy.py` (three separate
places) each summed `time_matrix` legs plus service time by hand. This module
replaces every one of those loops so there is exactly one place that decides
what a route's travel time, waiting and lateness are - the same reason
`fitness.py` is the one place cost/feasibility are decided.

Every optimizer keeps calling `decoder.decode_random_keys`, which calls this;
Greedy calls it directly once per vehicle's finalized job sequence.
"""
from typing import Dict, List

from models import Job, StopTiming, Vehicle


class RouteSchedule:
    """Result of simulating one vehicle's visit order.

    `travel_time` is the route's total elapsed clock time from depot
    departure (t=0) to depot return, INCLUDING any waiting - this is exactly
    what `VehicleRoute.route_travel_time` and `time_exceeded` are measured
    against, so a vehicle that waits spends part of its `max_route_time`
    budget doing so.
    """

    __slots__ = ("stops", "travel_time", "wait_time", "lateness", "late_jobs")

    def __init__(
        self,
        stops: List[StopTiming],
        travel_time: float,
        wait_time: float,
        lateness: float,
        late_jobs: int,
    ):
        self.stops = stops
        self.travel_time = travel_time
        self.wait_time = wait_time
        self.lateness = lateness
        self.late_jobs = late_jobs


def simulate_route(
    job_seq: List[int],
    vehicle: Vehicle,
    depot: int,
    time_matrix,
    jobs_by_id: Dict[int, Job],
) -> RouteSchedule:
    """Simulates one vehicle visiting `job_seq` (a list of job ids, in visit
    order) starting and ending at `depot`.

    Rules (CVRPTW, reduces to plain CVRP timing when a job has no window):
      arrival       = previous departure (or 0 at the depot) + time_matrix leg
      service_start = max(arrival, ready_time) - waiting is allowed and
                      counted, never skipped
      lateness      = max(0, service_start - due_time) - a SOFT constraint;
                      the route continues rather than rejecting the stop
      departure     = service_start + service_time

    `vehicle` is accepted for symmetry with the rest of the routing pipeline
    (and so a future per-vehicle timing rule has somewhere to live) but is not
    read yet - every current rule is job-side only.

    With no `ready_time`/`due_time` set on any job in `job_seq`, every
    `service_start` equals its `arrival`, so `travel_time` is numerically
    identical to the pre-time-windows sum of `time_matrix` legs plus service
    time - this is what keeps existing (non-time-window) scenarios producing
    byte-identical results.
    """
    stops: List[StopTiming] = []
    total_wait = 0.0
    total_lateness = 0.0
    late_jobs = 0

    current_time = 0.0
    cur_node = depot

    for job_id in job_seq:
        job = jobs_by_id[job_id]
        node = job.node_id

        arrival = current_time + time_matrix[cur_node, node]
        service_start = arrival if job.ready_time is None else max(arrival, job.ready_time)
        wait = service_start - arrival
        lateness = 0.0 if job.due_time is None else max(0.0, service_start - job.due_time)
        departure = service_start + job.service_time

        stops.append(StopTiming(
            job_id=job_id,
            arrival=round(arrival, 4),
            service_start=round(service_start, 4),
            departure=round(departure, 4),
            wait=round(wait, 4),
            lateness=round(lateness, 4),
        ))

        total_wait += wait
        total_lateness += lateness
        if lateness > 0:
            late_jobs += 1

        current_time = departure
        cur_node = node

    current_time += time_matrix[cur_node, depot]

    return RouteSchedule(
        stops=stops,
        travel_time=current_time,
        wait_time=total_wait,
        lateness=total_lateness,
        late_jobs=late_jobs,
    )
