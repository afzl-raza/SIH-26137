"""Tests for the CVRPTW time-window pipeline.

This file builds up in the same order the feature was implemented:
  1. schedule.simulate_route - the one timing function (this section)
  2. fitness.py's lateness penalty
  3. decoder/greedy no-windows-unchanged guarantees
  4. problem_generator's window generation + RNG isolation + hash stability
  5. the incident + windows interaction
  6. the API surface

Hand-computed numbers use a tiny 3-node network (depot=0, job nodes 1 and 2)
with a simple symmetric time_matrix, the same style as test_decoder.py.
"""
import os
import sys

import networkx as nx
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import Edge, Job, Node, ObjectiveWeights, ProblemScenario, Vehicle, VehicleRoute
from schedule import simulate_route
from fitness import evaluate_solution
from problem_generator import compute_route_matrix, compute_scenario_hash, generate_synthetic_scenario
from realdata.conditions import apply_incidents

from fastapi.testclient import TestClient
import main as main_module

client = TestClient(main_module.app)

DEPOT = 0

# time_matrix[a, b]: depot<->node1 = 4, depot<->node2 = 6, node1<->node2 = 3.
TIME_MATRIX = np.array([
    [0.0, 4.0, 6.0],
    [4.0, 0.0, 3.0],
    [6.0, 3.0, 0.0],
])


def _vehicle(max_route_time=1000.0):
    return Vehicle(id=1, capacity=100.0, start_node=DEPOT, end_node=DEPOT, max_route_time=max_route_time)


# ---------------------------------------------------------------- schedule.py

def test_simulate_route_no_windows_matches_old_leg_plus_service_sum():
    """With no ready_time/due_time, totals must equal the pre-time-windows
    sum of time_matrix legs plus service time - the byte-identical
    guarantee the whole feature depends on."""
    job = Job(id=1, node_id=1, demand=1.0, service_time=2.0)
    jobs_by_id = {1: job}

    sched = simulate_route([1], _vehicle(), DEPOT, TIME_MATRIX, jobs_by_id)

    # Old formula: leg(0->1) + service + leg(1->0) = 4 + 2 + 4 = 10
    assert sched.travel_time == pytest.approx(10.0)
    assert sched.wait_time == pytest.approx(0.0)
    assert sched.lateness == pytest.approx(0.0)
    assert sched.late_jobs == 0
    assert sched.stops[0].arrival == pytest.approx(4.0)
    assert sched.stops[0].service_start == pytest.approx(4.0)
    assert sched.stops[0].wait == pytest.approx(0.0)


def test_simulate_route_early_arrival_waits_for_ready_time():
    """Arriving before the window opens must wait, not start service early."""
    job = Job(id=1, node_id=1, demand=1.0, service_time=2.0, ready_time=10.0)
    jobs_by_id = {1: job}

    sched = simulate_route([1], _vehicle(), DEPOT, TIME_MATRIX, jobs_by_id)
    stop = sched.stops[0]

    # arrival = leg(0->1) = 4; wait = ready_time - arrival = 10 - 4 = 6
    assert stop.arrival == pytest.approx(4.0)
    assert stop.wait == pytest.approx(6.0)
    assert stop.service_start == pytest.approx(10.0)
    assert stop.departure == pytest.approx(12.0)
    assert sched.wait_time == pytest.approx(6.0)
    assert sched.lateness == pytest.approx(0.0)


def test_simulate_route_late_arrival_reports_lateness_and_continues():
    """A missed due_time is a soft constraint: it's reported as lateness, and
    the route keeps going to serve the remaining stops, not rejected."""
    job1 = Job(id=1, node_id=1, demand=1.0, service_time=2.0, due_time=2.0)
    job2 = Job(id=2, node_id=2, demand=1.0, service_time=1.0)
    jobs_by_id = {1: job1, 2: job2}

    sched = simulate_route([1, 2], _vehicle(), DEPOT, TIME_MATRIX, jobs_by_id)

    # job1: arrival = 4, due = 2 -> lateness = 4 - 2 = 2
    assert sched.stops[0].lateness == pytest.approx(2.0)
    assert sched.late_jobs == 1

    # Route continues: job2 is still simulated from job1's real departure (6),
    # not abandoned because job1 was late.
    job2_stop = sched.stops[1]
    assert job2_stop.arrival == pytest.approx(6.0 + 3.0)  # departure(job1) + leg(1->2)
    assert job2_stop.lateness == pytest.approx(0.0)
    assert sched.lateness == pytest.approx(2.0)


def test_simulate_route_waiting_counts_toward_completion_and_time_exceeded():
    """Waiting must extend the route's completion time (and therefore count
    against max_route_time) rather than being a free pause on the clock."""
    job = Job(id=1, node_id=1, demand=1.0, service_time=2.0, ready_time=10.0)
    jobs_by_id = {1: job}
    vehicle = _vehicle(max_route_time=11.0)

    sched = simulate_route([1], vehicle, DEPOT, TIME_MATRIX, jobs_by_id)

    # completion = service_start(10) + service(2) + return leg(4) = 16
    assert sched.travel_time == pytest.approx(16.0)
    time_exceeded = max(0.0, sched.travel_time - vehicle.max_route_time)
    assert time_exceeded == pytest.approx(5.0)
    # Had waiting NOT counted (arrival(4) + service(2) + return(4) = 10), this
    # same vehicle/window would have looked feasible (10 <= 11) - the whole
    # point of this test is that it isn't, because the vehicle actually is
    # occupied while it waits.


# ----------------------------------------------------------------- fitness.py

def _lateness_scenario(max_route_time=100.0):
    return ProblemScenario(
        nodes=[Node(id=0, name="Depot", lat=0.0, lng=0.0, is_depot=True),
               Node(id=1, name="N1", lat=0.0, lng=0.0)],
        edges=[],
        vehicles=[Vehicle(id=1, capacity=10.0, start_node=0, end_node=0, max_route_time=max_route_time)],
        jobs=[Job(id=1, node_id=1, demand=1.0, service_time=0.0, due_time=5.0)],
        depot_node_id=0,
        seed=1
    )


def _route_with_lateness(lateness, late_jobs):
    return VehicleRoute(
        vehicle_id=1, job_ids=[1], node_path=[0, 1, 0],
        route_distance=1.0, route_travel_time=10.0, total_demand=1.0,
        lateness=lateness, late_jobs=late_jobs
    )


def test_fitness_lateness_penalty_grows_with_lateness():
    scenario = _lateness_scenario()
    weights = ObjectiveWeights(alpha=0.0, beta=0.0, gamma=0.0, penalty_weight=100.0)

    small = evaluate_solution([_route_with_lateness(2.0, 1)], scenario, weights)
    large = evaluate_solution([_route_with_lateness(20.0, 1)], scenario, weights)

    # small: 100*(2/100)^2 + 100*0.05*1 = 0.04 + 5 = 5.04
    # large: 100*(20/100)^2 + 100*0.05*1 = 4 + 5 = 9.0
    assert small.total_cost == pytest.approx(5.04)
    assert large.total_cost == pytest.approx(9.0)
    assert large.total_cost > small.total_cost
    assert small.is_feasible is False
    assert large.is_feasible is False


def test_fitness_feasible_plan_beats_plan_with_small_lateness_violation():
    """A perfectly on-time plan must always cost less than an otherwise
    identical plan with even a small lateness violation - the fixed
    per-late-job penalty exists exactly so a small violation can't win by
    virtue of the quadratic term alone being tiny."""
    scenario = _lateness_scenario()
    weights = ObjectiveWeights(alpha=1.0, beta=1.0, gamma=1.0, penalty_weight=100.0)

    on_time_route = VehicleRoute(
        vehicle_id=1, job_ids=[1], node_path=[0, 1, 0],
        route_distance=1.0, route_travel_time=10.0, total_demand=1.0,
        lateness=0.0, late_jobs=0
    )
    slightly_late_route = _route_with_lateness(0.5, 1)  # a tiny violation

    on_time = evaluate_solution([on_time_route], scenario, weights)
    slightly_late = evaluate_solution([slightly_late_route], scenario, weights)

    assert on_time.is_feasible is True
    assert slightly_late.is_feasible is False
    assert on_time.total_cost < slightly_late.total_cost


def test_is_feasible_false_whenever_any_job_is_late():
    scenario = _lateness_scenario()
    weights = ObjectiveWeights(alpha=1.0, beta=1.0, gamma=1.0, penalty_weight=1000.0)

    result = evaluate_solution([_route_with_lateness(3.0, 1)], scenario, weights)

    assert result.constraint_violations >= 1
    assert result.is_feasible is False


# --------------------------------------------------------- problem_generator.py

def test_generator_time_windows_rng_isolation():
    """time_windows=True must draw ready/due from a SEPARATE RNG, so every
    other field (node ids, demands, service times, vehicle capacity) is
    byte-identical to the same seed with windows off - only ready_time/
    due_time may differ."""
    off = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=11)
    on = generate_synthetic_scenario(
        num_nodes=20, num_jobs=8, num_vehicles=3, seed=11, time_windows=True, tw_width_min=60.0
    )

    assert [n.model_dump() for n in off.nodes] == [n.model_dump() for n in on.nodes]
    assert [e.model_dump() for e in off.edges] == [e.model_dump() for e in on.edges]
    assert [v.model_dump() for v in off.vehicles] == [v.model_dump() for v in on.vehicles]

    for job_off, job_on in zip(off.jobs, on.jobs):
        assert job_off.id == job_on.id
        assert job_off.node_id == job_on.node_id
        assert job_off.demand == job_on.demand
        assert job_off.service_time == job_on.service_time
        assert job_off.priority == job_on.priority
        assert job_off.ready_time is None
        assert job_on.ready_time is not None
        assert job_on.due_time is not None


def test_generator_old_hash_unchanged_without_time_windows():
    """A scenario generated with time_windows left at its default (False)
    must hash exactly as it did before the feature existed - the TW params
    are folded into the hash ONLY when time_windows=True, so every existing
    scenario hash and frozen E1-E6 experiment config stays unchanged."""
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=11)

    # The exact pre-time-windows formula: no `extra` suffix at all.
    assert scenario.scenario_hash == compute_scenario_hash(20, 8, 3, 11)
    assert scenario.scenario_hash == "f9e11d2ce8"  # pinned so a future change is caught


def test_generator_hash_changes_when_time_windows_enabled():
    off = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=11)
    on = generate_synthetic_scenario(
        num_nodes=20, num_jobs=8, num_vehicles=3, seed=11, time_windows=True, tw_width_min=60.0
    )
    assert on.scenario_hash != off.scenario_hash


def test_generator_time_windows_reproducible_with_same_seed():
    a = generate_synthetic_scenario(
        num_nodes=20, num_jobs=8, num_vehicles=3, seed=11, time_windows=True, tw_width_min=60.0
    )
    b = generate_synthetic_scenario(
        num_nodes=20, num_jobs=8, num_vehicles=3, seed=11, time_windows=True, tw_width_min=60.0
    )
    for job_a, job_b in zip(a.jobs, b.jobs):
        assert job_a.ready_time == job_b.ready_time
        assert job_a.due_time == job_b.due_time


def test_generator_time_windows_are_satisfiable():
    """Every generated window must be reachable on time by a dedicated
    vehicle: due_time >= (depot -> job free-flow time) + service_time."""
    scenario = generate_synthetic_scenario(
        num_nodes=20, num_jobs=8, num_vehicles=3, seed=11, time_windows=True, tw_width_min=60.0
    )
    G = nx.DiGraph()
    for e in scenario.edges:
        G.add_edge(e.source, e.destination, weight=e.base_travel_time)
    depot_time = nx.single_source_dijkstra_path_length(G, source=scenario.depot_node_id, weight="weight")

    for job in scenario.jobs:
        assert job.ready_time is not None and job.due_time is not None
        assert job.ready_time <= job.due_time
        assert job.ready_time >= 0.0
        t0 = depot_time[job.node_id]
        # Small tolerance: due_time was rounded to 2dp at generation time.
        assert job.due_time >= t0 + job.service_time - 1e-2


# --------------------------------------------------- incident + windows

def test_incident_increases_lateness_while_windows_stay_unchanged():
    """The dynamic-conditions story for CVRPTW: an incident that slows a
    road on the route can only ever increase (or leave unchanged) a job's
    lateness - never decrease it - while the job's own window is untouched,
    because realdata.conditions only ever mutates Edge fields, never Job
    fields. Windows are absolute (minutes from shift start); this is what
    lets them survive a traffic/incident change with no extra code."""
    nodes = [Node(id=0, name="Depot", lat=0.0, lng=0.0, is_depot=True),
             Node(id=1, name="N1", lat=0.0, lng=0.0)]
    edges = [
        Edge(source=0, destination=1, distance=1.0, base_travel_time=5.0,
             traffic_factor=1.0, current_travel_time=5.0),
        Edge(source=1, destination=0, distance=1.0, base_travel_time=5.0,
             traffic_factor=1.0, current_travel_time=5.0),
    ]
    vehicle = Vehicle(id=1, capacity=10.0, start_node=0, end_node=0, max_route_time=1000.0)
    # due_time=6: on time at free-flow (arrival=5); a slowed edge will miss it.
    job = Job(id=1, node_id=1, demand=1.0, service_time=0.0, due_time=6.0)
    scenario = ProblemScenario(
        nodes=nodes, edges=edges, vehicles=[vehicle], jobs=[job],
        depot_node_id=0, seed=1,
    )

    _, time_before, _ = compute_route_matrix(scenario).as_tuple()
    sched_before = simulate_route([1], vehicle, 0, time_before, {1: job})
    assert sched_before.lateness == 0.0

    # Incident: this road now takes twice as long.
    disrupted, changed = apply_incidents(scenario, {(0, 1): 2.0})
    assert changed == 2  # symmetric: both directions

    disrupted_job = disrupted.jobs[0]
    # The window is unchanged (a different Job object - clone_scenario copies
    # jobs - but the same ready_time/due_time values).
    assert disrupted_job.due_time == job.due_time
    assert disrupted_job.ready_time == job.ready_time

    _, time_after, _ = compute_route_matrix(disrupted).as_tuple()
    sched_after = simulate_route([1], vehicle, 0, time_after, {1: disrupted_job})

    assert sched_after.lateness >= sched_before.lateness
    assert sched_after.lateness > 0.0


# ------------------------------------------------------------------- API

def test_api_generate_with_time_windows_then_optimize():
    """POST /api/problem/generate with time_windows=True must return jobs
    carrying ready_time/due_time, and POST /api/optimize against that
    scenario must return routes with the new CVRPTW fields populated."""
    gen_response = client.post("/api/problem/generate", json={
        "source": "synthetic",
        "num_nodes": 20,
        "num_jobs": 8,
        "num_vehicles": 3,
        "seed": 42,
        "time_windows": True,
        "tw_width_min": 60.0,
    })
    assert gen_response.status_code == 200
    gen_body = gen_response.json()
    scenario_id = gen_body["scenario_id"]
    jobs = gen_body["scenario"]["jobs"]

    assert len(jobs) == 8
    assert all(j["ready_time"] is not None and j["due_time"] is not None for j in jobs)

    opt_response = client.post("/api/optimize", json={
        "scenario_id": scenario_id,
        "config": {
            "algorithm": "greedy",
            "population_size": 10,
            "max_iterations": 5,
            "seed": 42,
        },
    })
    assert opt_response.status_code == 200
    result = opt_response.json()

    assert len(result["routes"]) == 3
    for route in result["routes"]:
        assert "stops" in route
        assert "wait_time" in route
        assert "lateness" in route
        assert "late_jobs" in route
        for stop in route["stops"]:
            assert set(stop.keys()) >= {"job_id", "arrival", "service_start", "departure", "wait", "lateness"}
