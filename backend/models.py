from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class Node(BaseModel):
    id: int
    name: str
    lat: float
    lng: float
    is_depot: bool = False


class Edge(BaseModel):
    source: int
    destination: int
    distance: float  # kilometers
    base_travel_time: float  # minutes
    traffic_factor: float = 1.0  # multiplier (1.0 = normal, 3.0 = heavy congestion)
    current_travel_time: float  # base_travel_time * traffic_factor
    road_name: str = ""


class Vehicle(BaseModel):
    id: int
    capacity: float
    start_node: int
    end_node: int
    max_route_time: float = 120.0  # minutes limit per vehicle route
    color: str = "#3B82F6"  # visual hex color


class Job(BaseModel):
    id: int
    node_id: int
    demand: float
    service_time: float = 5.0  # minutes service time at destination
    priority: int = 1


class ProblemScenario(BaseModel):
    nodes: List[Node]
    edges: List[Edge]
    vehicles: List[Vehicle]
    jobs: List[Job]
    depot_node_id: int
    seed: int = 42
    scenario_hash: str = ""  # deterministic id of the generation parameters, for display/replay


class ObjectiveWeights(BaseModel):
    alpha: float = 1.0  # weight for travel time
    beta: float = 0.5   # weight for distance
    gamma: float = 1.0  # weight for congestion cost
    penalty_weight: float = 1000.0  # penalty multiplier for constraint violations


class OptimizationConfig(BaseModel):
    algorithm: str = "qpso"  # greedy, pso, qpso
    population_size: int = 40
    max_iterations: int = 100
    seed: int = 42
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)


class VehicleRoute(BaseModel):
    vehicle_id: int
    job_ids: List[int]
    node_path: List[int]  # sequence of graph nodes starting and ending at depot
    route_distance: float
    route_travel_time: float
    total_demand: float
    capacity_exceeded: float = 0.0
    time_exceeded: float = 0.0
    congestion_delay: float = 0.0  # this route's share of total fleet congestion delay


class OptimizationResult(BaseModel):
    algorithm: str
    routes: List[VehicleRoute]
    total_cost: float
    total_travel_time: float
    total_distance: float
    runtime_ms: float
    constraint_violations: int
    convergence_history: List[float]
    # Real elapsed time (ms, from optimization start) at the point each
    # convergence_history entry was recorded - one entry per iteration, same
    # length as convergence_history when populated. Empty for algorithms
    # that don't record per-iteration timing (e.g. Greedy).
    convergence_elapsed_ms: List[float] = []
    is_feasible: bool


class TrafficUpdate(BaseModel):
    source: int
    destination: int
    traffic_factor: float


class TrafficUpdateBatch(BaseModel):
    updates: List[TrafficUpdate]


class BenchmarkResult(BaseModel):
    scenario_seed: int
    results: Dict[str, OptimizationResult]
