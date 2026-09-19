# Q-DFRO — Mathematical Model

Extracted from [`Engineering.md`](../Engineering.md) §4. This is the standalone,
citable version for the research paper — if the two ever disagree, the actual
code (`backend/models.py`, `backend/fitness.py`) is the source of truth and
both documents should be corrected to match it.

## Problem

Given a transportation network represented as a weighted graph whose edge
costs change dynamically with traffic, determine feasible routes for multiple
vehicles serving a set of delivery jobs while minimizing fleet-wide cost.

## Sets

- `V` — graph nodes (intersections, depot)
- `E` — directed edges (roads), `(i, j) ∈ E`
- `K` — vehicles, each with capacity `Q_k` and max route time `T_k`
- `J` — delivery jobs, each at a node with demand `d_j` and service time `s_j`
- `depot ∈ V` — shared start/end node for every vehicle

## Edge parameters

Per `models.Edge`:

- `distance_ij` — kilometers
- `base_travel_time_ij` — minutes at free-flow speed
- `traffic_factor_ij(t)` — congestion multiplier, `1.0` = normal
- `current_travel_time_ij(t) = base_travel_time_ij × traffic_factor_ij(t)` —
  this is the dynamic cost `c_ij(t)`

## Objective

Implemented exactly in `fitness.evaluate_solution`:

```
Cost = α · TravelTime + β · Distance + γ · Congestion + Penalty
```

where:

- `TravelTime = Σ_k route_travel_time_k` (includes job service time)
- `Distance = Σ_k route_distance_k`
- `Congestion = Σ (traffic_factor_ij − 1.0) × base_travel_time_ij`, summed over
  every traversed congested edge — the *extra* delay traffic adds, not total time
- `Penalty = penalty_weight × (capacity_exceeded² + time_exceeded²)`, summed
  per vehicle
- `α, β, γ, penalty_weight` are configurable (`OptimizationConfig.weights`)

Default weights used in E1–E6 evidence: `α=1.0, β=0.5, γ=1.0,
penalty_weight=1000.0` (see `experiments/E1_algorithm_comparison/config.json`).

## Constraints implemented

| ID | Constraint | Enforcement |
|---|---|---|
| C1 | Every job visited exactly once | Guaranteed by the decoder's job partition |
| C2 | Every vehicle starts at depot | Decoder always begins `node_path` at `depot_node_id` |
| C3 | Every vehicle ends at depot | Decoder always appends the return-to-depot path segment |
| C4 | Vehicle capacity respected | Soft constraint via `capacity_exceeded` → quadratic penalty |
| C5 | Route duration respected | Soft constraint via `time_exceeded` → quadratic penalty |
| C6 | Routes use valid graph edges | Guaranteed — built from precomputed shortest paths |

C4/C5 are penalty-based, not hard-rejected: an over-capacity or over-time
route is still returned but heavily penalized, and `constraint_violations` /
`is_feasible` reflect it honestly.

Only these six constraints are implemented. Time windows, vehicle
availability windows, multiple depots, and vehicle-type constraints appear in
earlier concept material but are **not** implemented — do not claim them in
the PPT or paper.

## Per-vehicle congestion breakdown

`VehicleRoute.congestion_delay` gives each vehicle's individual share of the
fleet-wide congestion term (added to support the Vehicle Inspector UI); it
always sums back to the aggregate `Congestion` term above.
