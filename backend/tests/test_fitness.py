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
    # raw_cost = 1*10 + 1*5 + 1*0 = 15; penalty = 100 * 3^2 = 900
    assert result.total_cost == pytest.approx(915.0)


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
    # raw_cost = 1*6 + 1*4 + 1*0 = 10; penalty = 50 * 2^2 = 200
    assert result.total_cost == pytest.approx(210.0)


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
