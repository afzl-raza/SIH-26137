# Q-DFRO Engineering Specification

**Project:** SIH26137 — Quantum-Inspired Intelligent Traffic Route Optimization
**Organization:** Egreen Quanta · **Team:** Byte Brain
**Status:** Prototype implemented and demoable. This document is the single technical
source of truth for architecture, algorithms, data contracts and the path from the
current prototype to the Grand Finale system described in
`Q_DFRO_SIH2026_Final_Implementation_Master_Plan.docx`.

This file is the canonical engineering reference, superseding the old
`specs.md` / `Prototype Technical Specification.md` / `SIH26137 — Prototype
Documentation.md` / `Prototype Tasks.md` / `Claude Development Instructions.md`
(removed 2026-09-18 — their content is fully absorbed here and in `Task.md` /
`Agent.md`). `Documnetation.md` is kept as a dated change log of past decisions,
not an architecture reference — update this file instead going forward.

---

## 1. Guiding Principles

These apply to every phase below, current or future:

1. **Research core before presentation.** The optimization engine, evaluator and
   experiment evidence matter more than UI polish. See [`CLAUDE.md`](CLAUDE.md) and
   [`Agent.md`](Agent.md) for the enforced version of this rule.
2. **One evaluator, every algorithm.** Greedy, PSO, GA and QPSO are never scored by
   different logic. `backend/fitness.py::evaluate_solution` is the only source of cost,
   feasibility and violation counts.
3. **No fabricated numbers.** Every cost, runtime, convergence curve and benchmark
   value shown in the UI, PPT, video or paper must come from an actual run. If QPSO
   loses to PSO/GA on a given scenario, that result is reported as-is.
4. **Frozen constraints.** Only constraints that are implemented and tested are
   documented as "supported." Do not describe capabilities the code doesn't have.
5. **Reproducibility.** Every scenario is generated from a seed; every optimizer run
   accepts a seed. Same seed + same config ⇒ same result.
6. **Don't overbuild.** No auth, payments, driver accounts, notifications, live GPS,
   or production deployment infrastructure. See §9 for what's deliberately deferred.

---

## 2. System Architecture

```
 Simulation Environment          →  creates the transportation problem
        │  (problem_generator.py)
        ▼
 Route Representation/Decoder    →  turns a candidate solution into fleet routes
        │  (decoder.py)
        ▼
 Optimization Engine             →  searches for low-cost feasible solutions
        │  (optimizers/{greedy,pso,ga,qpso}.py)
        ▼
 Common Evaluator                →  scores every candidate identically
        │  (fitness.py)
        ▼
 FastAPI Backend                 →  exposes scenario / optimize / traffic / benchmark
        │  (main.py)
        ▼
 React Frontend                  →  Plan → Optimize → Disrupt → Re-optimize → Prove
           (frontend/src)
```

The critical separation, unchanged from prototype through Grand Finale: **simulation
creates the world, optimization solves it, the evaluator measures it, the platform
communicates it.** No algorithm module is allowed to reach into the UI, and no UI
component is allowed to compute cost, feasibility, or route metrics itself — all of
that comes from the backend.

---

## 3. Current Implementation Map

| Layer | Module | Status |
|---|---|---|
| Scenario generation (graph, depot, vehicles, jobs) | `backend/problem_generator.py` | ✅ Implemented |
| Deterministic seeding | `generate_synthetic_scenario(seed=...)` | ✅ Implemented, tested |
| Shortest-path infrastructure (NetworkX) | `compute_route_matrix()` — K single-source Dijkstra runs over the full graph, K = depot + jobs | ✅ Implemented |
| Dynamic traffic update | `POST /api/traffic/update` | ✅ Implemented |
| Route representation (random-key encoding) | `backend/decoder.py` | ✅ Implemented |
| Common evaluator (incl. per-vehicle congestion) | `backend/fitness.py` | ✅ Implemented |
| Greedy baseline | `optimizers/greedy.py` | ✅ Implemented |
| Classical PSO | `optimizers/pso.py` | ✅ Implemented |
| GA | `optimizers/ga.py` | ✅ Implemented |
| QPSO | `optimizers/qpso.py` | ✅ Implemented |
| Benchmark runner (single scenario, all algorithms) | `optimizers/benchmark.py` | ✅ Implemented |
| Re-optimization after incident | `handleReOptimize` → `POST /api/optimize` | ✅ Implemented (client-driven) |
| FastAPI surface | `backend/main.py` | ✅ Implemented |
| Map-first frontend (Plan/Disrupt/Re-optimize/Prove) | `frontend/src/*` | ✅ Implemented |
| Unit tests | `backend/tests/*.py` (25 files) | ✅ 360/360 passing |
| Experiment runner (E1–E6, saved to disk) | `backend/experiments/runner.py` | ✅ Implemented, run for real |
| Experiment results API | `GET /api/experiments/{name}` | ✅ Implemented |
| Live experiment trigger | `POST /api/experiments/{name}/run` — runs the real `run_eX` synchronously | ✅ Implemented |
| Server-side objective preview (re-score without re-optimizing) | `POST /api/evaluate` → `fitness.evaluate_solution` | ✅ Implemented |
| Deterministic scenario hash ("Run ID") | `problem_generator.compute_scenario_hash` | ✅ Implemented |
| Per-iteration wall-clock timing | `convergence_elapsed_ms` in `models.OptimizationResult`, recorded in `qpso.py`/`pso.py`/`ga.py` | ✅ Implemented |
| Multi-seed reproducibility statistics | `run_e6_reproducibility` | ✅ Implemented |
| Scalability sweep | `run_e3_scalability` (20→200 nodes) | ✅ Implemented |
| Research/evidence docs (`docs/*.md`) | `docs/mathematical_model.md`, `qpso_specification.md`, `experiment_protocol.md`, `requirements_traceability.md` | ✅ Implemented |
| Exact solver for small instances (bitmask DP, ≤10 jobs) | `optimizers/exact.py` | ✅ Implemented |
| 2-opt/or-opt local search (Lamarckian, on QPSO) | `optimizers/local_search.py` | ✅ Implemented |
| Persisted scenario/run history (DB) | — | ❌ Not started, deferred (§9) |
| OSM/OSMnx realistic network | `realdata/osm_loader.py`, `realdata/osm_scenario.py` | ✅ Implemented |
| SUMO traffic simulation | — | ❌ Not started, deferred (§9) |

This table is the ground truth for [`Task.md`](Task.md). Update both together.

---

## 4. Mathematical Formulation

**Problem.** Given a transportation network represented as a weighted graph whose
edge costs change dynamically with traffic, determine feasible routes for multiple
vehicles serving a set of delivery jobs while minimizing fleet-wide cost.

**Sets**
- `V` — graph nodes (intersections, depot)
- `E` — directed edges (roads), `(i, j) ∈ E`
- `K` — vehicles, each with capacity `Q_k` and max route time `T_k`
- `J` — delivery jobs, each at a node with demand `d_j` and service time `s_j`
- `depot ∈ V` — shared start/end node for every vehicle

**Edge parameters** (per `models.Edge`)
- `distance_ij` — km
- `base_travel_time_ij` — minutes at free-flow speed
- `traffic_factor_ij(t)` — congestion multiplier, 1.0 = normal
- `current_travel_time_ij(t) = base_travel_time_ij × traffic_factor_ij(t)` — this is
  the dynamic cost `c_ij(t)` referenced in the master plan

**Objective** (implemented exactly in `fitness.evaluate_solution`)

```
Cost = α · TravelTime + β · Distance + γ · Congestion + Penalty
```

where:
- `TravelTime = Σ_k route_travel_time_k` (includes job service time)
- `Distance = Σ_k route_distance_k`
- `Congestion = Σ (traffic_factor_ij − 1.0) × base_travel_time_ij` summed over every
  traversed congested edge — i.e. the *extra* delay traffic adds, not total time
- `Penalty = penalty_weight × (capacity_exceeded² + time_exceeded²)`, summed per vehicle
- `α, β, γ, penalty_weight` are configurable (`OptimizationConfig.weights`)

Each `VehicleRoute` also carries `congestion_delay`, its own share of the
`Congestion` term above (added to support the Vehicle Inspector UI) — the
per-route values always sum back to the aggregate term.

**Constraints implemented**

| ID | Constraint | Enforcement |
|---|---|---|
| C1 | Every job visited exactly once | Guaranteed by the decoder's job partition (§5) |
| C2 | Every vehicle starts at depot | `decode_random_keys` always begins `node_path` at `depot_node_id` |
| C3 | Every vehicle ends at depot | Decoder always appends the return-to-depot path segment |
| C4 | Vehicle capacity respected | Soft constraint via `capacity_exceeded` → quadratic penalty |
| C5 | Route duration respected | Soft constraint via `time_exceeded` → quadratic penalty |
| C6 | Routes use valid graph edges | Guaranteed — routes are built from `paths_dict` (NetworkX shortest paths) |

C4/C5 are **penalty-based, not hard-rejected**: an over-capacity or over-time route
is still returned but heavily penalized, and `constraint_violations` /
`is_feasible` reflect it honestly. This must not be described as "infeasible
solutions are discarded" — they are repaired via cost pressure, not removed.

Only these six constraints are documented as supported. Time windows, vehicle
availability windows, multiple depots, and vehicle-type constraints all appear in
earlier concept material (the original SIH26137 concept-prototype slide brief and
the master plan's future-work list, §9) but are **not** implemented — do not claim
them in the PPT or paper.

---

## 5. Route Representation & Decoding (QPSO ↔ VRP bridge)

This is the section the master plan calls "one of the most technically important
parts of the project" — judges will ask how a continuous optimizer produces a
discrete multi-vehicle route.

**Encoding.** A candidate solution is a vector of `num_jobs` continuous keys in
`[0, 1]`, one per job — not one per vehicle, and not a permutation.

**Decoding** (`decoder.decode_random_keys`), for job `i` with key `x_i`:

```
vehicle_idx  = min(num_vehicles - 1, floor(x_i * num_vehicles))
sequence_key = x_i * num_vehicles - vehicle_idx
```

- The integer part of `x_i * num_vehicles` selects **which vehicle** serves job `i`.
- The fractional part (`sequence_key`) determines **visit order** within that
  vehicle: jobs assigned to the same vehicle are sorted ascending by `sequence_key`.

This single continuous vector therefore encodes both the vehicle-assignment
decision and the intra-route ordering decision simultaneously, which is exactly
what lets QPSO/PSO/GA search both dimensions of the VRP at once without a separate
splitting heuristic.

**From job sequence to road-level path:** consecutive jobs (and depot↔first/last
job) are joined using `paths_dict`, the NetworkX shortest-path lookup computed once
per scenario/traffic-state by `compute_route_matrix`. So the optimizer decides
*which jobs, in what order, for which vehicle*; the graph router decides *how a
vehicle physically gets from one stop to the next*. These two decisions are
deliberately separate.

**Feasibility handling:** there is no separate `RouteRepair` step in the current
prototype — capacity/time violations are surfaced as penalties (§4) rather than
repaired or rejected. If a hard repair/repair-or-reject step is added later
(master plan `RouteRepair`), it must be documented here and the constraint table
in §4 updated to match.

---

## 6. Common Evaluator

`fitness.evaluate_solution(routes, scenario, weights, ...)` is called by **every**
optimizer with no exceptions. It returns an `OptimizationResult` containing
`total_cost`, `total_travel_time`, `total_distance`, `runtime_ms`,
`constraint_violations`, `convergence_history`, and `is_feasible`. Because Greedy,
PSO, GA and QPSO all call this same function on the same `ProblemScenario`, benchmark
comparisons are fair by construction — no algorithm gets a different cost formula.

---

## 7. Algorithm Library

All optimizers implement `BaseOptimizer.optimize(scenario, config) -> OptimizationResult`
(`optimizers/base.py`), so `optimizers/benchmark.py::run_benchmark` can call them
interchangeably.

| Algorithm | File | Mechanism |
|---|---|---|
| Greedy / Nearest-Neighbour | `greedy.py` | Deterministic baseline: repeatedly assigns the nearest feasible unvisited job. Used to sanity-check the decoder/evaluator independent of any stochastic search. |
| Classical PSO | `pso.py` | Standard velocity/position update over the same random-key encoding as QPSO. |
| GA | `ga.py` | Tournament selection (`_tournament_select`), crossover (`_crossover`), mutation (`_mutate`) over the random-key chromosome. |
| QPSO | `qpso.py` | Quantum-behaved PSO — see below. |

**QPSO — exact mechanism implemented** (`optimizers/qpso.py`):

1. Initialize `pop_size` particles as `X ~ U(0,1)^num_jobs`.
2. Each iteration, compute the mean best position: `mbest = mean(pbest_pos)` across
   the population.
3. Local attractor per particle/dimension: `p = φ·pbest + (1−φ)·gbest`,
   `φ ~ U(0,1)`.
4. Quantum position update (delta-potential-well formulation):
   `X = p ± α·|mbest − X|·ln(1/u)`, `u ~ U(0,1)`, sign chosen uniformly at random.
5. `α` (contraction-expansion coefficient) decays linearly from `1.0` to `0.4` over
   `max_iterations`.
6. Positions are clipped back to `[0, 1]` after the update (keeps keys valid for the
   decoder in §5).
7. Decode → evaluate → update `pbest`/`gbest` → append `gbest_cost` to
   `convergence_history` → repeat.

This is the exact and only QPSO variant implemented. If the research paper cites a
different QPSO formulation, `qpso.py` must be changed to match, not the other way
around — per the master plan's explicit warning against documenting equations that
aren't what's actually running.

---

## 8. Dynamic Traffic & Re-optimization

- `POST /api/traffic/update` takes a scenario and a list of `{source, destination,
  traffic_factor}` updates, applies them symmetrically, and recomputes
  `current_travel_time` for affected edges. It does not re-run optimization itself.
- The frontend's re-optimize flow (`App.jsx::handleReOptimize`) simply calls
  `POST /api/optimize` again on the updated scenario and keeps the previous result
  for the before/after comparison (`previousResult` vs `currentResult` in
  `NetworkMap.jsx`).
- There is currently no server-side `ReoptimizationResult` object that bundles
  `cost_delta` / `changed_vehicle_ids` — those deltas are computed ad hoc in the
  frontend (`MetricCards.jsx`) from the two `OptimizationResult` payloads. This is
  fine for the current demo; if the master plan's dedicated reoptimize endpoint is
  built later, keep the delta computation server-side and update this section.

---

## 9. Benchmarking & Experiment Protocol

`POST /api/benchmark` runs Greedy, PSO, GA and QPSO on one scenario/config and
returns all four `OptimizationResult`s keyed by algorithm name
(`optimizers/benchmark.py`) — this is E1 done live, on demand.

**`backend/experiments/runner.py`** turns all six experiments into saved,
reproducible evidence under `experiments/<name>/` at the repo root, run via
`python -m experiments.runner --experiment {e1..e6,all}` from `backend/`.
Every experiment freezes its own `config.json` first and refuses to silently
overwrite a differently-configured prior run.

| Experiment | Question | Status |
|---|---|---|
| E1 — Solution quality | How do algorithms compare on an identical scenario? | ✅ Run, saved to `experiments/E1_algorithm_comparison/` |
| E2 — Convergence | How does best-cost evolve per iteration? | ✅ Run, saved to `experiments/E2_convergence/` |
| E3 — Scalability | How does runtime/quality change as the problem grows? | ✅ Run, saved to `experiments/E3_scalability/` |
| E4 — Traffic disruption | Old cost vs new cost vs re-optimization runtime | ✅ Run, saved to `experiments/E4_traffic_disruption/` |
| E5 — Traffic severity | Behavior across increasing congestion factors | ✅ Run, saved to `experiments/E5_traffic_severity/` |
| E6 — Reproducibility | Mean/std of QPSO cost across multiple seeds | ✅ Run, saved to `experiments/E6_reproducibility/` |

Full methodology and the actual measured numbers are written up in
[`docs/experiment_protocol.md`](docs/experiment_protocol.md) — including one
finding worth calling out here because it shapes how E3 must be read: **an
earlier version of E3 held the fleet fixed at 3 vehicles while jobs scaled to
100, which made the fleet structurally unable to serve demand and produced
exploding "infeasible" costs.** That measured fleet undersizing, not optimizer
scalability, so `run_e3_scalability` scales vehicle count with job count
(`jobs_per_vehicle=5.0`). The corrected results still show PSO/QPSO failing to
reach full feasibility at 200 nodes under E3's deliberately reduced solver
budget — reported as-is in the protocol doc, not smoothed over.

**Fair-benchmark rule (satisfied everywhere, E1–E6):** every algorithm receives
the same `ProblemScenario` — same graph, vehicles, jobs, traffic, seed and
objective weights — and only the algorithm (and, in E3 only, its
runtime-appropriate reduced solver budget, always documented alongside the
result) varies.

An exact solver (`optimizers/exact.py`, bitmask Held-Karp + assignment DP,
capped at ≤10 jobs) is implemented and auto-included in `run_benchmark`
whenever a scenario is small enough. `BenchmarkPanel.jsx` shows a "Gap vs
Optimum" column once `results.exact` is present.

---

## 10. Testing Strategy

**360/360 tests passing** across 25 files in `backend/tests/`, including:

- `test_backend.py` — seed determinism, shortest-path correctness/performance,
  Greedy/PSO/GA/QPSO smoke tests, traffic incident sanity, benchmark smoke
  test, scenario-hash determinism/distinguishing, and
  `convergence_elapsed_ms` real-and-monotonic
- `test_decoder.py` — hand-computed route, multi-vehicle split, more vehicles
  than jobs, zero-jobs contract
- `test_fitness.py` — capacity/time penalty exactness, congestion formula,
  per-vehicle congestion breakdown
- `test_exact_optimizer.py` — brute-force-vs-exact agreement, shared-evaluator
  route completeness, job-cap rejection
- `test_local_search.py` — raw-cost/canonical-evaluator equivalence, 2-opt
  untangling, or-opt never losing/duplicating a job, refinement never
  increasing cost, QPSO+local-search closing the gap against Greedy at scale
- `test_benchmark_fairness.py` — scenario not mutated across a benchmark run,
  feasibility flag consistency across all six algorithms (greedy, pso, ga,
  qpso, qpso_ls, exact when ≤10 jobs)
- `test_e2e.py` — full generate → optimize → incident → traffic update →
  re-optimize → benchmark workflow
- `test_experiments.py` — experiment schema/output, small scalability sweep,
  before/after presence, reproducibility determinism, frozen-config guard,
  and the `GET /api/experiments/{name}` endpoint (200/404/400)
- `test_evaluate_endpoint.py` — `POST /api/evaluate` matches a direct
  `fitness.py` call for the same inputs, rejects malformed payloads (422)
- `test_run_experiment_endpoint.py` — `POST /api/experiments/{name}/run`
  rejects an unknown name (400) and executes the real E6 runner end-to-end
  over HTTP
- `test_docs_consistency.py` — every file path referenced in
  `requirements_traceability.md` is verified to actually exist

**Remaining gap:** frontend automated tests (no Vitest/Jest configured) — an
explicit scope decision for this round, not an oversight. Module F (the
frontend gap-closure work) was verified instead by a live manual walkthrough
in the browser against real backend data.

---

## 11. API Reference (current)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness check |
| POST | `/api/problem/generate` | Create a scenario from `{num_nodes, num_jobs, num_vehicles, seed}` |
| POST | `/api/optimize` | Run `{scenario, config}` through the selected algorithm |
| POST | `/api/traffic/update` | Apply edge traffic-factor updates to a scenario |
| POST | `/api/benchmark` | Run greedy/pso/ga/qpso/qpso_ls on one scenario/config, plus `exact` when the scenario has ≤10 jobs |
| POST | `/api/evaluate` | Re-score an already-computed set of routes against new objective weights via the same `fitness.evaluate_solution` every optimizer uses — no re-optimization, no client-side math |
| GET | `/api/experiments/{name}` | Read-only: serves `backend/experiments/runner.py`'s saved output for one of the six known experiment names; 404 with a clear "not yet run" message if the experiment hasn't been executed, 400 for an unknown name |
| POST | `/api/experiments/{name}/run` | Synchronously invokes the real `run_eX` function (same code path as the CLI) and returns its output; 400 for an unknown name, 409 if a frozen prior config conflicts |

The backend is **stateless**: the client holds the `ProblemScenario` and passes it
back on every call. There is no scenario ID, no stored run history, and no
database — the one exception, `/api/experiments/{name}` (and its `/run`
counterpart), only reads/writes files the offline experiment runner already
uses under `experiments/` at the repo root; it does not add a persistence
layer. Do not add real persistence without updating this section and
`Task.md` together.

---

## 12. Frontend Architecture (current)

`frontend/src/App.jsx` owns all state (`scenario`, `currentResult`, `previousResult`,
`benchmarkData`, `incidentInfo`, `statusState`, `networkState`) and drives the
Plan → Optimize → Disrupt → Re-optimize → Prove workflow shown by
`WorkflowIndicator.jsx`. `NetworkMap.jsx` (Leaflet) is the primary visual — roads,
depot, jobs, vehicle routes, and the incident-highlighted edge. `ControlPanel.jsx`
holds the primary actions plus a collapsed "Advanced Solver Settings" panel for
population size / iterations / α β γ / seed. It also enforces the demo state
machine: "Simulate Incident" is disabled until a route exists, "Re-Optimize" is
disabled until an incident has been triggered, and a one-line causal-explanation
sentence appears after re-optimization completes. `MetricCards.jsx` and
`BenchmarkPanel.jsx` render only backend-sourced numbers — no client-side cost
math, no fake progress bars — and `MetricCards.jsx` now also surfaces the exact
α/β/γ/penalty weights behind the displayed cost.

`VehicleInspector.jsx` shows each vehicle's per-vehicle `congestion_delay`
(from Module C's evaluator extension) alongside distance/time/feasibility.
`QPSOExplainability.jsx` is a small static+live panel showing the live
population/iterations/seed plus the fixed encode→decode→evaluate pipeline,
the server-computed `scenario.scenario_hash` as a "Run ID", so
a judge can see QPSO is actually wired into route generation. `BenchmarkPanel.jsx`
includes a "Comparison Conditions" fairness badge (scenario/graph/jobs/fleet/
constraints/objective/evaluation-function — seed and solver params shown
separately as configuration, not as a fairness claim), a neutral,
symmetric summary of the empirically cheapest algorithm — no algorithm gets
special celebratory treatment for winning — and a clickable results row that
previews that algorithm's real routes on the map (`previewedAlgorithm` state
in `App.jsx`, consumed by `NetworkMap.jsx` as `displayedResult =
previewResult || currentResult`, with a "PREVIEWING: {ALGO}" badge so it's
never confused with the applied result). `ScalabilityPanel.jsx` and
`ReproducibilityPanel.jsx` fetch `GET /api/experiments/{name}` and show an
honest "not yet run" empty state with a "Run Now" button
(`POST /api/experiments/{name}/run`) rather than fabricating data when an
experiment hasn't been executed.

**Presentation-script UI additions (Tier 1/2, 2026-09-18):** `NetworkMap.jsx`
gained a GIS↔bare-graph view toggle (same `nodes`/`edges` data, just hides
the OSM tile layer), a `useRouteTransition` hook that fades the previous
route out / new route in via opacity over real before/after route arrays
(never interpolates fabricated intermediate waypoints), an edge-click popup
breaking cost into its real Travel Time/Distance/Congestion contributions
plus "Disrupt This Road" severity buttons wired to
`App.jsx::handleDisruptEdge` (which reuses `POST /api/traffic/update`, same
as the existing incident flow). `ControlPanel.jsx` gained a real-data
Scenario Health Strip, a Route Impact Count badge, a `RecoveryTimeline.jsx`
mount (Disruption/Detection timestamps are real client event times; the
Optimizing segment is sourced from the backend's own `runtime_ms`, never a
client stopwatch), a "Replay Run" button (`App.jsx::handleReplay`, re-issues
the same real generate+optimize calls with the same seed/config), and a
debounced live objective-weight preview against `POST /api/evaluate`.
`MetricCards.jsx` gained `useCountUp`-tweened KPI displays (the tween only
animates the display between two real endpoint values) and a route-change
count. `BenchmarkPanel.jsx`'s convergence chart uses Chart.js's own 400ms
`animation` config as an honest draw-in, not a paced replay implying the
algorithm is still running. `ArchitectureSnapshot.jsx` is a static
Prototype↔Deployment toggle mirroring §2/§13 of this document, explicitly
not live telemetry.

---

## 13. Deliberately Deferred (Grand-Finale-stage, not this round)

Per `CLAUDE.md` and the master plan's own "not required initially" list, the
following are **not** part of the current prototype and should not be started
without an explicit decision to move into that phase:

- PostgreSQL / SQLAlchemy / Alembic persistence layer
- Docker / docker-compose packaging
- Full REST resource model (`/api/scenarios/{id}`, stored optimization runs, etc.)
- SUMO traffic simulation
- Exact solver (OR-Tools) beyond a small optional reference case
- Authentication, payments, driver accounts, notifications, live GPS, traffic
  prediction, production deployment

These appear in the master plan as the path to a full research platform. They are
valid future work — list them as such in the paper/PPT — but building them now
would trade research-core time for infrastructure the judges did not ask to see
running.

---

## 14. Where This Fits With Task.md and Agent.md

- **`Task.md`** turns §3's status table and §9's experiment gaps into an ordered,
  checkable task list. Update `Task.md` whenever a row in §3 changes state.
- **`Agent.md`** is the tool-agnostic contract (for Claude Code, Copilot, Cursor,
  Codex, etc.) that enforces the principles in §1 while any of this is being built.
