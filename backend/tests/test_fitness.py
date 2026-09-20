import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import Node, Edge, Vehicle, Job, ProblemScenario, VehicleRoute, ObjectiveWeights
from fitness import evaluate_solution


def _minimal_scenario(edges=None):
    return ProblemScenario(
        nodes=[Node(id=0, name="Depot", lat=0.0, lng=0.0, is_depot=True),
               Node(id=1, name="N1", lat=0.0, lng=0.0)],
        edges=edges or [],
        vehicles=[Vehicle(id=1, capacity=10.0, start_node=0, end_node=0, max_route_time=100.0)],
        jobs=[Job(id=1, node_id=1, demand=1.0, service_time=0.0)],
        depot_node_id=0,
        seed=1
    )


def test_capacity_violation_penalty():
    scenario = _minimal_scenario()
    weights = ObjectiveWeights(alpha=1.0, beta=1.0, gamma=1.0, penalty_weight=100.0)
    route = VehicleRoute(
        vehicle_id=1, job_ids=[1], node_path=[0, 1, 0],
        route_distance=5.0, route_travel_time=10.0, total_demand=8.0,
        capacity_exceeded=3.0, time_exceeded=0.0
    )

    result = evaluate_solution([route], scenario, weights)

    assert result.constraint_violations == 1
    assert result.is_feasible is False
    # raw_cost = 1*10 + 1*5 + 1*0 = 15
    # penalty = 100 * (capacity_exceeded / vehicle.capacity)^2 = 100 * (3/10)^2 = 9
    assert result.total_cost == pytest.approx(24.0)


def test_time_violation_penalty():
    scenario = _minimal_scenario()
    weights = ObjectiveWeights(alpha=1.0, beta=1.0, gamma=1.0, penalty_weight=50.0)
    route = VehicleRoute(
        vehicle_id=1, job_ids=[1], node_path=[0, 1, 0],
        route_distance=4.0, route_travel_time=6.0, total_demand=1.0,
        capacity_exceeded=0.0, time_exceeded=2.0
    )

    result = evaluate_solution([route], scenario, weights)

    assert result.constraint_violations == 1
    assert result.is_feasible is False
    # raw_cost = 1*6 + 1*4 + 1*0 = 10
    # penalty = 50 * (time_exceeded / vehicle.max_route_time)^2 = 50 * (2/100)^2 = 0.02
    assert result.total_cost == pytest.approx(10.02)


def test_capacity_penalty_normalized_by_vehicle_capacity():
    """A fixed absolute overage must cost less penalty on a bigger vehicle -
    guards against the regression where an unnormalized (violation ** 2)
    let a handful of trivially-over-capacity vehicles at large problem
    scales (e.g. 5% over) inflate total_cost 10-100x, because capacity
    overages (single digits to tens of units) and time overages (tens to
    hundreds of minutes) were squared on completely different absolute
    scales."""
    weights = ObjectiveWeights(alpha=0.0, beta=0.0, gamma=0.0, penalty_weight=100.0)

    def scenario_with_capacity(capacity):
        return ProblemScenario(
            nodes=[Node(id=0, name="Depot", lat=0.0, lng=0.0, is_depot=True),
                   Node(id=1, name="N1", lat=0.0, lng=0.0)],
            edges=[],
            vehicles=[Vehicle(id=1, capacity=capacity, start_node=0, end_node=0, max_route_time=100.0)],
            jobs=[Job(id=1, node_id=1, demand=1.0, service_time=0.0)],
            depot_node_id=0,
            seed=1
        )

    route = VehicleRoute(
        vehicle_id=1, job_ids=[1], node_path=[0, 1, 0],
        route_distance=0.0, route_travel_time=0.0, total_demand=0.0,
        capacity_exceeded=5.0, time_exceeded=0.0
    )

    small_vehicle_cost = evaluate_solution([route], scenario_with_capacity(10.0), weights).total_cost
    large_vehicle_cost = evaluate_solution([route], scenario_with_capacity(100.0), weights).total_cost

    # penalty = 100 * (5/10)^2 = 25 vs 100 * (5/100)^2 = 0.25
    # (total_cost is rounded to 2dp by evaluate_solution, so capacity=100
    # rather than 1000 keeps the smaller expected value above that floor)
    assert small_vehicle_cost == pytest.approx(25.0)
    assert large_vehicle_cost == pytest.approx(0.25)
    assert small_vehicle_cost > large_vehicle_cost


def test_per_vehicle_congestion_sums_to_total():
    """Congestion delay must be broken out per route (for the Vehicle
    Inspector's per-vehicle Congestion field) while still summing to the
    same fleet-level total the formula has always produced."""
    congested_edge = Edge(source=0, destination=1, distance=2.0, base_travel_time=5.0,
                           traffic_factor=2.0, current_travel_time=10.0)
    normal_edge = Edge(source=0, destination=2, distance=3.0, base_travel_time=3.0,
                        traffic_factor=1.0, current_travel_time=3.0)
    scenario = ProblemScenario(
        nodes=[Node(id=0, name="Depot", lat=0.0, lng=0.0, is_depot=True),
               Node(id=1, name="N1", lat=0.0, lng=0.0),
               Node(id=2, name="N2", lat=0.0, lng=0.0)],
        edges=[congested_edge, normal_edge],
        vehicles=[
            Vehicle(id=1, capacity=10.0, start_node=0, end_node=0, max_route_time=100.0),
            Vehicle(id=2, capacity=10.0, start_node=0, end_node=0, max_route_time=100.0),
        ],
        jobs=[Job(id=1, node_id=1, demand=1.0, service_time=0.0),
              Job(id=2, node_id=2, demand=1.0, service_time=0.0)],
        depot_node_id=0,
        seed=1
    )
    weights = ObjectiveWeights(alpha=1.0, beta=1.0, gamma=1.0, penalty_weight=1000.0)
    route_congested = VehicleRoute(
        vehicle_id=1, job_ids=[1], node_path=[0, 1, 0],
        route_distance=2.0, route_travel_time=10.0, total_demand=1.0
    )
    route_normal = VehicleRoute(
        vehicle_id=2, job_ids=[2], node_path=[0, 2, 0],
        route_distance=3.0, route_travel_time=3.0, total_demand=1.0
    )

    result = evaluate_solution([route_congested, route_normal], scenario, weights)

    assert route_congested.congestion_delay == pytest.approx(5.0)
    assert route_normal.congestion_delay == 0.0
    total_from_routes = route_congested.congestion_delay + route_normal.congestion_delay
    # total_cost = alpha*travel_time + beta*distance + gamma*congestion (no penalty)
    # => congestion contribution = total_cost - travel_time - distance
    congestion_in_cost = result.total_cost - result.total_travel_time - result.total_distance
    assert total_from_routes == pytest.approx(congestion_in_cost)


def test_congestion_cost_matches_formula():
    edge = Edge(source=0, destination=1, distance=2.0, base_travel_time=5.0,
                traffic_factor=2.0, current_travel_time=10.0)
    scenario = _minimal_scenario(edges=[edge])
    weights = ObjectiveWeights(alpha=1.0, beta=0.5, gamma=2.0, penalty_weight=1000.0)
    route = VehicleRoute(
        vehicle_id=1, job_ids=[1], node_path=[0, 1, 0],
        route_distance=2.0, route_travel_time=10.0, total_demand=1.0,
        capacity_exceeded=0.0, time_exceeded=0.0
    )

    result = evaluate_solution([route], scenario, weights)

    # congestion delay = (traffic_factor - 1) * base_travel_time = (2-1)*5 = 5
    # total_cost = alpha*10 + beta*2 + gamma*5 = 10 + 1 + 10 = 21, no penalty
    assert result.constraint_violations == 0
    assert result.is_feasible is True
    assert result.total_cost == pytest.approx(21.0)
