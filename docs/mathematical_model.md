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
- `J` — delivery jobs, each at a node with demand `d_j`, service time `s_j`,
  and an optional delivery time window `[ready_j, due_j]` (CVRPTW, see below)
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

- `TravelTime = Σ_k route_travel_time_k` (includes job service time **and**
  any waiting for a job's window to open — `route_travel_time` is the
  vehicle's total elapsed clock time from depot departure to depot return,
  not travel-only time; see "Time windows" below)
- `Distance = Σ_k route_distance_k`
- `Congestion = Σ (traffic_factor_ij − 1.0) × base_travel_time_ij`, summed over
  every traversed congested edge — the *extra* delay traffic adds, not total time
- `Penalty = penalty_weight × (capacity_exceeded² + time_exceeded²)`, summed
  per vehicle, **plus** the lateness penalty defined below
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
| C7 | Delivery time windows respected | Soft constraint via `lateness`/`late_jobs` → quadratic + fixed penalty (CVRPTW, see below) |

C4/C5/C7 are penalty-based, not hard-rejected: an over-capacity, over-time or
late route is still returned but penalized, and `constraint_violations` /
`is_feasible` reflect it honestly.

Only these seven constraints are implemented. Vehicle availability windows,
multiple depots, and vehicle-type constraints appear in earlier concept
material but are **not** implemented — do not claim them in the PPT or paper.

## Time windows (CVRPTW)

Each job optionally carries a delivery window `[ready_j, due_j]`, in minutes
from shift start (`t=0` at depot departure). `None` on either field means "no
window" — a job with no window behaves exactly as it did before this section
existed, and this is what keeps every pre-existing (non-TW) scenario's
results byte-identical.

Implemented in exactly one function, `schedule.simulate_route`, called by
`decoder.decode_random_keys`, `optimizers/greedy.py` and
`optimizers/qpso_memetic.py::_route_cost` — there is no second timing
computation anywhere in the codebase. For a vehicle visiting jobs in order,
starting a running clock at `t=0` at the depot:

```
arrival_j       = departure_{j-1} + travel_time(prev_node, node_j)   (depot if j is first)
service_start_j = max(arrival_j, ready_j)             (waiting is allowed and counted, not skipped)
wait_j          = service_start_j − arrival_j
lateness_j      = max(0, service_start_j − due_j)      (0 when due_j is None)
departure_j     = service_start_j + service_time_j
```

Completion is the return leg from the last stop to the depot. Because
`service_start_j` already advances the clock through any `wait_j`,
`route_travel_time` (the completion time) **includes waiting** — a vehicle
that waits has spent part of its `T_k` budget doing so, so `time_exceeded`
(measured against `route_travel_time`) counts it too.

**Lateness is a soft constraint.** A missed `due_j` does not stop the route:
`simulate_route` keeps simulating the remaining stops from the real
(late) departure time, and the violation is reported, not hidden or
rejected.

### Lateness penalty

Implemented in `fitness.evaluate_solution`, added to `Penalty` above:

```
Penalty_lateness = Σ_k [ penalty_weight × (lateness_k / T_k)²  +  penalty_weight × 0.05 × late_jobs_k ]
```

`lateness_k` and `late_jobs_k` are `VehicleRoute.lateness` (total minutes
late, summed over that route's stops) and `VehicleRoute.late_jobs` (count of
stops served after their own `due_j`). The fixed `× 0.05 × late_jobs_k` term
exists for the same reason the normalized-by-limit form of the
capacity/time penalties exists (see `fitness.py`'s own comment): a small
violation, once squared and normalized, can otherwise register as
negligible next to the routing cost it's competing against. `is_feasible`
additionally requires total lateness across the fleet to be exactly zero,
independent of `constraint_violations`.

### Generation

`problem_generator.generate_time_windows` (used by both
`generate_synthetic_scenario` and `realdata.osm_scenario.osm_graph_to_scenario`,
opt-in via `time_windows`/`tw_width_min`) draws windows from a RNG seeded
independently of — and never advanced by — the RNG that generates the rest
of the scenario, so a scenario generated with `time_windows=True` has
byte-identical job nodes, demands and service times to the same seed with
`time_windows=False`:

```
t0    = depot → job node free-flow travel time
ready = uniform(0, max(0, max_route_time × 0.6 − t0))
due   = max(ready + tw_width_min, t0 + service_time)
```

`due ≥ t0 + service_time` always, so a dedicated vehicle leaving the depot
alone can always reach and serve the job on time — no generated window is
impossible to hit by construction.

`compute_scenario_hash` folds the window-width parameter into the hash
**only** when `time_windows=True`, so every scenario hash and frozen E1–E6
experiment config generated before this feature — and every call that leaves
`time_windows` at its default — stays byte-for-byte unchanged.

### Windows are absolute, not relative to a simulation clock

Windows are minutes from shift start, not from "now" — and this backend has
no simulation clock (every `/api/optimize` call re-decodes routes from
`t=0`). `realdata.conditions` never writes to `Job`, only to `Edge`, so an
incident or traffic/weather change leaves every window untouched; only the
edge costs — and therefore how much of a window is actually met — change.
See `docs/dynamic_conditions.md` §5b.

## Per-vehicle congestion breakdown

`VehicleRoute.congestion_delay` gives each vehicle's individual share of the
fleet-wide congestion term (added to support the Vehicle Inspector UI); it
always sums back to the aggregate `Congestion` term above.
