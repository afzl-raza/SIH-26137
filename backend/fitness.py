from typing import Dict, List, Optional, Tuple
from models import Edge, ProblemScenario, VehicleRoute, ObjectiveWeights, OptimizationResult


def build_edge_map(scenario: ProblemScenario) -> Dict[Tuple[int, int], Edge]:
    """(source, destination) -> Edge lookup, the same one `evaluate_solution`
    builds internally when not given one. Exposed so a caller evaluating many
    candidates against the same scenario - every population-based optimizer's
    search loop - can build it once and pass it in, instead of paying an
    O(scenario edges) rebuild on every single candidate. On a real
    OpenStreetMap-scale scenario (thousands of edges) that rebuild, repeated
    pop_size * iterations times, was measured to dominate optimizer runtime -
    a QPSO/PSO/GA run on an 8,942-edge extract took ~13-27s each, the large
    majority of it this rebuild, not the search itself."""
    return {(e.source, e.destination): e for e in scenario.edges}


def evaluate_solution(
    routes: List[VehicleRoute],
    scenario: ProblemScenario,
    weights: ObjectiveWeights,
    algorithm_name: str = "",
    runtime_ms: float = 0.0,
    convergence_history: List[float] = None,
    convergence_elapsed_ms: List[float] = None,
    edge_map: Optional[Dict[Tuple[int, int], Edge]] = None,
) -> OptimizationResult:
    """
    Evaluates a candidate route set using the single centralized objective function:
    Cost = alpha * TravelTime + beta * Distance + gamma * Congestion + Penalty

    Penalty includes capacity, route-time and (CVRPTW) lateness violations,
    all normalized and quadratic - see the per-term comments below.

    `edge_map` lets a caller pass a pre-built build_edge_map(scenario) result
    when evaluating many candidates against the same scenario; built here
    when omitted, so single-shot callers (Greedy, /api/evaluate, tests) are
    unaffected.
    """
    if convergence_history is None:
        convergence_history = []
    if convergence_elapsed_ms is None:
        convergence_elapsed_ms = []

    total_travel_time = sum(r.route_travel_time for r in routes)
    total_distance = sum(r.route_distance for r in routes)

    # Congestion cost calculation: extra delay from traffic multipliers (> 1.0)
    # We query edge traffic factors for consecutive nodes in routes
    if edge_map is None:
        edge_map = build_edge_map(scenario)
    total_congestion_delay = 0.0

    for r in routes:
        route_congestion_delay = 0.0
        path = r.node_path
        for u, v in zip(path[:-1], path[1:]):
            edge = edge_map.get((u, v))
            if edge and edge.traffic_factor > 1.0:
                extra_delay = (edge.traffic_factor - 1.0) * edge.base_travel_time
                route_congestion_delay += extra_delay
        r.congestion_delay = round(route_congestion_delay, 2)
        total_congestion_delay += route_congestion_delay

    # Constraint violations & quadratic penalties.
    #
    # Violations are normalized to a fraction of their own limit
    # (capacity_exceeded / vehicle.capacity, time_exceeded / vehicle.max_route_time)
    # before squaring, so a given percentage overage costs the same penalty
    # regardless of whether it's measured in demand units or minutes. Squaring
    # the raw values directly (the original approach) let time violations -
    # typically tens to hundreds of minutes - dwarf capacity violations -
    # typically single digits to tens of units - by several orders of
    # magnitude for a comparable "how infeasible is this" severity, which at
    # larger problem sizes let a handful of trivially-over-capacity vehicles
    # (e.g. 5% over) inflate total_cost by 10-100x and swamp the actual
    # routing cost the objective is supposed to be measuring.
    vehicles_by_id = {v.id: v for v in scenario.vehicles}
    constraint_violations = 0
    penalty = 0.0

    for r in routes:
        vehicle = vehicles_by_id.get(r.vehicle_id)
        capacity = vehicle.capacity if vehicle and vehicle.capacity > 0 else 1.0
        max_route_time = vehicle.max_route_time if vehicle and vehicle.max_route_time > 0 else 1.0

        if r.capacity_exceeded > 0:
            constraint_violations += 1
            penalty += weights.penalty_weight * (r.capacity_exceeded / capacity) ** 2
        if r.time_exceeded > 0:
            constraint_violations += 1
            penalty += weights.penalty_weight * (r.time_exceeded / max_route_time) ** 2
        # Lateness (soft, CVRPTW): normalized the same way as time_exceeded,
        # PLUS a fixed per-late-job penalty so a handful of small violations
        # (each individually tiny once squared and normalized) can't win out
        # over a feasible plan just because the quadratic term alone barely
        # registers - see the E1-style regression this fix mirrors for
        # capacity/time above.
        if r.lateness > 0:
            constraint_violations += r.late_jobs
            penalty += weights.penalty_weight * (r.lateness / max_route_time) ** 2
            penalty += weights.penalty_weight * 0.05 * r.late_jobs

    total_lateness = sum(r.lateness for r in routes)

    raw_cost = (
        weights.alpha * total_travel_time +
        weights.beta * total_distance +
        weights.gamma * total_congestion_delay
    )
    total_cost = raw_cost + penalty

    # Lateness is checked independently of constraint_violations (rather than
    # relying solely on the late_jobs count folded into it above) so a route
    # is never reported feasible while any job on it is still late.
    is_feasible = (constraint_violations == 0) and (total_lateness == 0)

    return OptimizationResult(
        algorithm=algorithm_name,
        routes=routes,
        total_cost=round(total_cost, 2),
        total_travel_time=round(total_travel_time, 2),
        total_distance=round(total_distance, 2),
        runtime_ms=round(runtime_ms, 2),
        constraint_violations=constraint_violations,
        convergence_history=[round(c, 2) for c in convergence_history],
        convergence_elapsed_ms=[round(t, 2) for t in convergence_elapsed_ms],
        is_feasible=is_feasible
    )
