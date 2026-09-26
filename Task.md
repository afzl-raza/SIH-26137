# Q-DFRO Task Tracker

Source plan: `Q_DFRO_SIH2026_Final_Implementation_Master_Plan.docx`.
Architecture/spec reference: [`Engineering.md`](Engineering.md).
Agent rules while executing any of this: [`Agent.md`](Agent.md).
Implementation plan for this round: `Evidence Layer + Frontend Gap-Closure`
(Modules A–G), approved and executed on 2026-09-18.

Status legend: ✅ Done · ⚠️ Partial · ❌ Not started. Statuses below are
verified against the actual code and a full test run (`pytest backend/tests
-q` → **36/36 passing**), not assumed from the plan.

---

## CVRPTW — Customer Time Windows ✅ Done (2026-09-26)

Turns the problem from CVRP into CVRPTW: jobs may carry a delivery window
`[ready_time, due_time]` (minutes from shift start), opt-in and off by
default so every pre-existing scenario/result stays byte-identical.

- [x] `models.py`: `Job.ready_time`/`due_time` (+ validator), `StopTiming`,
      `VehicleRoute.stops`/`wait_time`/`lateness`/`late_jobs`
- [x] `schedule.py` (new): `simulate_route` — the single timing function,
      replacing three separately-duplicated timing loops across
      `decoder.py` and `optimizers/greedy.py` (and used by
      `optimizers/qpso_memetic.py::_route_cost`)
- [x] `optimizers/greedy.py`: candidate ranking is time-until-service-start
      (`t_leg + wait`), tie-broken by earliest `due_time`, skips a candidate
      that would arrive late when an on-time option exists — a no-op when
      windows are off (verified byte-identical against the full pre-existing
      suite)
- [x] `fitness.py`: lateness penalty (normalized quadratic + a fixed
      per-late-job term, same shape as the capacity/time terms);
      `is_feasible` independently requires zero fleet-wide lateness
- [x] `optimizers/qpso_memetic.py`: registered in `optimizers/benchmark.py`
      as `"qpso_memetic"`; its local-search cost model uses the same
      `simulate_route` and mirrors the lateness penalty exactly (its
      capacity/time terms carry an additional fixed search-only penalty not
      present in `fitness.py` — documented in its own docstring, never
      affects the reported score)
- [x] `problem_generator.py` / `realdata/osm_scenario.py`:
      `time_windows`/`tw_width_min` params; windows drawn from an RNG seeded
      independently of the rest of generation, so job nodes/demands/service
      times are identical with windows on or off; `compute_scenario_hash`
      only changes when `time_windows=True`
- [x] `main.py`: `time_windows`/`tw_width_min` on `POST /api/problem/generate`
      (both synthetic and OSM paths); `/api/optimize`/`/api/benchmark`
      responses carry the new route fields with no shape change otherwise
- [x] Frontend: `ControlPanel.jsx` toggle + 30–120 min width slider;
      `VehicleInspector.jsx` per-stop table (arrival/window/wait/late, late
      rows red, waits amber); `NetworkMap.jsx` job popup shows the window and
      rings a late job's marker red; `MetricCards.jsx` "Late Deliveries" card
- [x] `docs/mathematical_model.md`: CVRPTW formulation (states that
      `route_travel_time` includes waiting); `docs/dynamic_conditions.md`
      §5b: windows are absolute, and there is no simulation clock;
      `docs/requirements_traceability.md`: new row
- [x] 14 new tests in `backend/tests/test_time_windows.py` (timing,
      fitness, generator RNG-isolation/hash-stability/reproducibility,
      incident-vs-window interaction, API). Full suite: 366 total (352
      pre-existing + 14 new), no existing test weakened. One pre-existing,
      unrelated test — `test_scenario_store.py::test_expired_entries_are_dropped`
      (a 50ms-TTL timing assertion) — is intermittently flaky under full-suite
      CPU load; it passes reliably in isolation and is untouched by this
      feature, not a regression introduced here.

**Benchmark finding, reported as-is (30 jobs/6 vans and 50 jobs/10 vans,
seed 42):** Memetic QPSO is the only algorithm besides Greedy that stays
feasible with time windows on at both sizes, and remains the lowest-cost
feasible algorithm throughout. GA and QPSO, at 50 jobs/10 vans with windows
on, report actual late jobs (1 and 5 respectively) rather than just
crossing the existing capacity/time infeasibility this default
population/iteration budget already showed even with windows off — an
honest new failure mode, not smoothed over.

---

## Visual Identity & UI Polish Pass ✅ Done (2026-09-18)

Plan: `Q-DFRO — Visual Identity & UI Polish Plan`. Pure presentation-layer
pass — no new backend calls, no new data, no change to what any number
means. Direction ("Traffic Amber & Asphalt": warm near-black base, amber
reserved strictly for traffic-caution semantics, a separate rust/terracotta
accent reserved for product identity — logo, primary CTA, active state)
was chosen after an initial graphite+violet "generic tech" direction was
explicitly rejected as still too AI-dashboard-generic.

- [x] New design tokens (`tailwind.config.js`, `index.css`): asphalt
      neutral scale replacing Tailwind's stock slate defaults;
      `brand.accent`/`brand.accentSoft` (rust/terracotta, product
      identity only) kept deliberately separate from `traffic.amber`
      (real traffic-caution semantics only) so one color doesn't have to
      mean both "brand" and "pay attention"; muted highway-green/brake-
      light-red status colors; Space Grotesk added for headings/hero
      numbers; `.tabular-nums` utility on every animated/metric number
- [x] Custom brand mark (`Logo.jsx` + real `frontend/public/favicon.svg`)
      — fixes a real pre-existing bug: `index.html` referenced
      `/favicon.svg` but the file never existed, so the browser tab
      showed a broken icon; header wordmark restyled to "Q-DFRO Engine"
      / "Quantum-Inspired Fleet Optimization Engine"
- [x] Map visual upgrade (`NetworkMap.jsx`): swapped the bright default
      OSM tiles for the same OSM tiles darkened via a CSS `filter`
      (invert+hue-rotate+sepia) — CartoDB's free dark basemap was tried
      first but now requires an API key and rendered a visible "API KEY
      REQUIRED" watermark, so this stays key-free; emoji markers (🚚,
      ◉, ●) replaced with hand-drawn inline SVG glyphs; active routes
      get a `drop-shadow` glow via a per-vehicle-color `<style>` block
      (not a duplicated `Polyline`, to avoid zoom/pan stutter); Graph
      View gets a faint accent-tinted dot-grid background
- [x] Layout density fixes: `MetricCards.jsx`'s oversized standalone
      "hero" cost block folded into the same 5-column density as the
      other metrics (α/β/γ formula moved to an info-icon hover reveal);
      `ReproducibilityPanel.jsx` gained a min→mean→max range bar with a
      soft ±std-dev band, built from the exact same fields the panel
      already fetches — no new backend call
- [x] Palette/type sweep across every remaining panel (`ControlPanel`,
      `BenchmarkPanel`, `ScalabilityPanel`, `VehicleInspector`,
      `WorkflowIndicator`, `QPSOExplainability`, `ArchitectureSnapshot`,
      `RecoveryTimeline`) plus the vehicle route color palette in
      `backend/problem_generator.py` (cosmetic hex list only, no logic
      change — no test asserts specific colors)

**Real bugs found and fixed while implementing this (logged, not
hidden):**
1. `.clean-card`/`.clean-panel`'s own plain `border` shorthand rule in
   `index.css` sits after `@tailwind utilities` in source order, so it
   silently overrides any Tailwind `border-*`/`border-l-*` utility of a
   different color applied to the same element (equal specificity, later
   source wins) — the accent-bordered hero metric card and the selected
   `VehicleInspector` panel were rendering the wrong border color/width
   until fixed with an inline `style` override instead.
2. `react-leaflet`'s `MapContainer` does not reactively re-apply its own
   `className` prop after the underlying Leaflet instance mounts (Leaflet
   imperatively owns that DOM node's class list from then on) — the
   GIS↔Graph View toggle's dot-grid class silently never applied. Fixed
   by moving the toggled class to a wrapper `<div>` around `MapContainer`
   instead, targeted via a CSS descendant selector.

Verified live in-browser: full Plan→Optimize→Disrupt→Re-optimize→Prove
flow, vehicle/job/edge popups, Simulate Incident → Re-Optimize → Recovery
Timeline, Run Benchmark table + convergence chart, Scalability "Run Now",
Reproducibility range bar — all render with real data and the new
palette, no console errors beyond stale pre-existing buffered entries.
Backend: **36/36 passing** (only change was the cosmetic vehicle color
list).

---

## Presentation-Script UI Plan (Tier 1 + Tier 2) ✅ Done (2026-09-18)

Plan: `Q-DFRO — Presentation-Script UI Implementation Plan` (18 items across
two tiers), derived from a 28-row SIH judging-parameter/demo-script table.
**Hard rule enforced throughout, per your explicit correction mid-plan:**
every visual is backed by a real backend-produced value — no fabricated
telemetry, no client-side objective computation, no animation paced to imply
live computation once a call has already returned. All items verified live
in-browser against real backend responses, not just code-reviewed.

**Tier 1 (9/9 done):** Scenario Health Strip; server-computed `scenario_hash`
as Run ID (`problem_generator.py::compute_scenario_hash`, `models.py`); Route
Impact Count badge; animated KPI counters + route-change count
(`useCountUp` in `MetricCards.jsx`, tweens only the display between two real
values); edge-click "why this road costs what it costs" cost-decomposition
popup (`NetworkMap.jsx`); QPSO disclaimer wording check; Recovery Timeline
(`RecoveryTimeline.jsx`, real client event timestamps + backend `runtime_ms`
for the optimizing segment — never a client stopwatch guess); Replay Run
button (`handleReplay` in `App.jsx`, re-issues the same real
generate+optimize calls); Architecture Snapshot toggle
(`ArchitectureSnapshot.jsx`, explicitly labeled static, not live telemetry).

**Tier 2 — frontend-only (5/5 done):** GIS↔Graph map view toggle
(`NetworkMap.jsx`); interactive click-any-edge disruption with severity
picker (`handleDisruptEdge` in `App.jsx`, reuses `POST /api/traffic/update`);
Chart.js 400ms entrance transition on the convergence chart — deliberately
*not* a paced "looks still running" reveal; Before→After route
opacity-transition on re-optimize (`useRouteTransition` hook in
`NetworkMap.jsx`, transitions between two already-computed route arrays);
click a Benchmark Panel row to preview that algorithm's real routes on the
map (`previewedAlgorithm` state, `BenchmarkPanel.jsx` → `App.jsx` →
`NetworkMap.jsx`).

**Tier 2 — backend-touching (3/3 done):** live objective-weight preview via
new `POST /api/evaluate` (re-scores already-computed routes server-side
through the same `fitness.evaluate_solution`, never client-side math) with a
debounced preview in `ControlPanel.jsx`, confirmed correct by manual
math-check (β=10 preview = 793.25, matches `196.55 + 9.5×62.8`); real
per-iteration `convergence_elapsed_ms` recorded in `qpso.py`/`pso.py`/`ga.py`
(actual `time.perf_counter()` samples, not estimated); "Run Now" button on
`ScalabilityPanel.jsx` calling new `POST /api/experiments/{name}/run`, which
invokes the exact same `run_eX` function the CLI uses — verified live by
diffing the DOM table against a direct `GET /api/experiments/E3_scalability`
fetch after clicking Run Now (16/16 rows matched exactly, including the
genuine PSO/QPSO infeasible-at-200-nodes result, reported as-is).

New backend tests: `test_evaluate_endpoint.py`, `test_run_experiment_endpoint.py`,
plus `test_scenario_hash_deterministic_and_distinguishing` and
`test_qpso_convergence_elapsed_ms_is_real_and_monotonic` added to
`test_backend.py`. Full suite: **36/36 passing**.

**Tier 3 — explicitly deferred, not started:** QPSO particle-cloud
visualization, impact heatmap (skipped, no new mapping dependency), full
"Proof Mode" dashboard, Executive Impact Summary freeze-frame. Do not start
without asking first, per the plan's own build order.

---

## Frontend Refinement (UX audit + reconciliation) ✅ Done (2026-09-18)

Separate plan (`Q-DFRO Frontend Refinement Plan`, Modules A–E), scoped to
desktop/tablet (1024px+), no backend changes:

- [x] **Module A — Design System Reconciliation**: fixed a real bug (marker
      hover CSS class names didn't match `NetworkMap.jsx`'s actual classes —
      silently dead); wired up the previously-unused `.advanced-collapse`
      animation into `ControlPanel.jsx`; refactored `WorkflowIndicator.jsx`
      to use the already-written `.workflow-step--*`/`.workflow-connector--*`
      classes instead of duplicated inline ternaries; consolidated
      `BenchmarkPanel.jsx`'s three separate algorithm-color functions into
      one `ALGORITHM_COLORS` map; applied the `.hero-metric` gradient;
      deleted ~130 lines of genuinely redundant dead CSS
- [x] **Module B — Responsive Hardening**: confirmed header/workflow
      indicator/button layout hold up at 1024–1440px (live-tested); removed
      redundant emoji+icon pairs from action button labels; added
      `overflow-x-auto` safety nets to the workflow indicator and the map's
      vehicle filter bar so they degrade gracefully rather than silently
      clip if a scenario has more vehicles
- [x] **Module C — Accessibility Quick Wins**: `label`/`htmlFor`/`id` wiring
      on all Advanced Settings inputs; `aria-label` on icon-only close
      buttons (Leaflet's zoom controls already had proper `aria-label`s,
      verified rather than assumed); `focus-visible` rings on every primary
      action button and filter chip (verified via `:focus-visible` match in
      the live app)
- [x] **Module D — Map Legend Completion**: legend now explains that route
      line color identifies the vehicle (was previously undocumented) and
      clarifies the pre-incident dashed-line meaning
- [x] **Module E — Micro-interaction Consistency**: normalized two bare
      `transition` classes to `transition-colors` to match the dominant
      pattern; audit found the existing transition usage was otherwise
      already sensible per-case, not the inconsistency originally assumed
- [ ] **Marker decluttering at low zoom** — explicitly flagged in the plan as
      needing your sign-off (adds a new dependency, `react-leaflet-markercluster`
      or equivalent). Not done pending that decision.
- [ ] **Metrics-out-of-footer / persistent vehicle roster** — surfaced as
      genuine "standard fleet dashboard" patterns Q-DFRO lacks, deliberately
      left out of this pass as bigger structural changes. Say the word if
      you want either taken up.

Verified live in-browser throughout (not just code-reviewed): marker hover,
advanced-settings collapse, workflow indicator states, keyboard focus rings,
label-input association, full Plan→Optimize→Disrupt→Re-optimize→Prove flow
with no console errors. Backend untouched; 30/30 backend tests still passing
at the time (now 36/36, see the Presentation-Script UI Plan section above).

---

## Phase 0 — Research Specification Freeze ✅ Done

- [x] Problem, objective and constraints frozen (`Engineering.md` §4)
- [x] `docs/mathematical_model.md` — extracted, standalone, citable
- [x] `docs/qpso_specification.md` — exact QPSO equations + continuous→discrete bridge

## Phase 1 — Simulation Environment ✅ Done

- [x] Graph generation, deterministic seeding, traffic update — unchanged, tested
- [x] Shortest-path routing performance fixed: `compute_shortest_paths` now
      uses `nx.single_source_dijkstra` per node (O(V)) instead of one
      `nx.shortest_path` call per (source, target) pair (O(V²)) — the latter
      did not scale past ~150 nodes. Tested
      (`test_shortest_paths_correctness_small_graph`, `test_shortest_paths_performance`).
- [ ] Named traffic levels (NORMAL/MODERATE/HIGH/DISRUPTED) as a reusable enum
      — still ad hoc per-call factors; low priority, not blocking anything

## Phase 2 — Mathematical Formulation ✅ Done

- [x] Formalized in `docs/mathematical_model.md`
- [x] Per-vehicle congestion breakdown added (`VehicleRoute.congestion_delay`)
      so the fleet-level congestion term can be attributed per route —
      required by the Vehicle Inspector UI, tested
      (`test_per_vehicle_congestion_sums_to_total`)

## Phase 3 — Route Representation ✅ Done

- [x] Documented in `docs/qpso_specification.md`
- [x] Decoder unit tests with hand-computed expected routes
      (`test_decoder.py`: hand-computed route, multi-vehicle split, more
      vehicles than jobs, zero-jobs contract)

## Phase 4 — Common Evaluator ✅ Done

- [x] Capacity/time penalty tests, congestion-formula test (`test_fitness.py`)
- [x] Benchmark-fairness tests: scenario not mutated, all 4 algorithms
      feasible-flag consistent (`test_benchmark_fairness.py`)

## Phase 5 — Baselines ✅ Done

- [x] Greedy, GA, PSO — unchanged, tested
- [ ] Exact reference solver — still skipped this round (optional per master plan)

## Phase 6 — QPSO ✅ Done

- [x] Documented exactly in `docs/qpso_specification.md`

## Phase 7 — Dynamic Re-optimization ✅ Done

- [x] End-to-end tested (`test_e2e.py::test_full_demo_workflow`): generate →
      optimize → incident → traffic update → re-optimize → benchmark
- [x] Causal explanation surfaced in the UI after re-optimization
      (`ControlPanel.jsx`)
- [ ] Server-side `ReoptimizationResult` object — still computed ad hoc in the
      frontend; not needed unless a dedicated `/api/reoptimize` endpoint is
      added later

## Phase 8 — Experiment & Benchmark Framework ✅ Done

- [x] `backend/experiments/` package built: `config.py` (scenario/solver
      specs, reusing `models.OptimizationConfig`), `runner.py` (E1–E6 + CLI)
- [x] `GET /api/experiments/{name}` — read-only endpoint serving the
      runner's output to the frontend, 404s honestly if not yet run
- [x] `POST /api/experiments/{name}/run` — triggers the real `run_eX`
      function live from the UI (`ScalabilityPanel.jsx`'s "Run Now"),
      identical code path to the CLI, 409 if a frozen prior config conflicts
- [x] **E1 — Solution quality**: run and saved (`experiments/E1_algorithm_comparison/`)
- [x] **E2 — Convergence**: run and saved (`experiments/E2_convergence/`)
- [x] **E3 — Scalability**: run and saved (`experiments/E3_scalability/`) —
      see the design-flaw note below
- [x] **E4 — Traffic disruption**: run and saved (`experiments/E4_traffic_disruption/`)
- [x] **E5 — Traffic severity**: run and saved (`experiments/E5_traffic_severity/`)
- [x] **E6 — Reproducibility**: run and saved (`experiments/E6_reproducibility/`)
- [x] Full methodology + real results written up in `docs/experiment_protocol.md`

**Design flaw found and fixed while running this (logged, not hidden):** the
first version of E3 held vehicle count fixed at 3 while scaling jobs to 100,
which made the fleet structurally incapable of servicing demand and produced
exploding "infeasible" costs (tens of millions) at 100+ nodes — that measured
fleet undersizing, not optimizer scalability. Fixed by scaling vehicle count
with job count (`jobs_per_vehicle=5.0`). The corrected run still shows PSO/QPSO
failing to reach full feasibility at 200 nodes under E3's *reduced* solver
budget — reported as a genuine finding in `docs/experiment_protocol.md`, not
smoothed over.

## Phase 9 — Scalability / Realistic Network ❌ Not started (deferred)

- [ ] OSM/OSMnx, SUMO — unchanged, deliberately deferred (`Engineering.md` §13)

## Phase 10 — Software Platform ✅ Done for this round's scope

- [x] All Phase 10 items from the previous tracker, plus:
- [x] State-machine guards: "Simulate Incident" disabled until a route exists,
      "Re-Optimize" disabled until an incident exists (`ControlPanel.jsx`)
- [x] Per-vehicle Congestion field in the Vehicle Inspector
- [x] QPSO Explainability panel (population/iterations/seed + search pipeline)
- [x] Benchmark Comparison-Conditions fairness badge, worded precisely (seed
      shown as configuration, not a fairness condition)
- [x] Neutral, symmetric benchmark summary (no algorithm gets special
      celebratory treatment for winning)
- [x] Scalability panel and Reproducibility panel, reading real E3/E6 data via
      the new endpoint, with an honest "not yet run" empty state
- [ ] Persistence layer — still intentionally deferred (`Engineering.md` §13)

## Phase 11 — Validation & Hardening ✅ Done

**30/30 backend tests passing** (`pytest backend/tests -q`), across 7 files:
`test_backend.py`, `test_decoder.py`, `test_fitness.py`,
`test_benchmark_fairness.py`, `test_e2e.py`, `test_experiments.py`,
`test_docs_consistency.py`.

- [x] Decoder hand-computed route test
- [x] Constraint/penalty tests
- [x] Benchmark-fairness tests
- [x] Full end-to-end workflow test
- [x] Experiment-framework tests (schema, scalability sweep, before/after,
      reproducibility determinism, frozen-config guard, API 200/404/400)
- [x] Docs-consistency guard (`requirements_traceability.md` paths verified
      to exist, so it can't rot silently)
- [ ] Frontend automated tests — still out of scope this round (no Vitest/Jest
      configured); Module F was verified by live manual walkthrough instead

## Phase 12 — Evidence Package ✅ Done

- [x] `docs/mathematical_model.md`
- [x] `docs/qpso_specification.md`
- [x] `docs/experiment_protocol.md` — with real E1–E6 numbers, not placeholders
- [x] `docs/requirements_traceability.md` — corrected against real module names
- [x] Frozen `experiments/` results directory (all 6 experiments, raw + processed)
- [ ] README instructions re-verified against the actual current run commands
      — `Readme.md` was already rewritten in the prior documentation pass;
      no changes needed this round, spot-checked and still accurate

## Documentation Housekeeping ✅ Done (2026-09-18, carried over)

- [x] Removed duplicate/superseded docs (see prior entry, unchanged)
- [x] `Readme.md` rewritten as a real setup/run entry point (unchanged this round)
- [x] `Documnetation.md` corrections (unchanged this round)

---

## Definition of Done (this round)

- [x] Scenario, traffic, vehicles, jobs, depot, constraints implemented
- [x] Traffic can dynamically change edge costs and trigger visible re-optimization
- [x] Greedy, GA, PSO, QPSO all run through the same evaluator
- [x] QPSO records convergence history
- [x] API and UI show only backend-computed values
- [x] Benchmark/scalability/reproducibility results are measured **and saved**
      (previously the biggest gap — now closed via `backend/experiments/`)
- [x] No fabricated numbers appear anywhere claims are made — including the
      UI's Scalability/Reproducibility panels, which show a "not yet run"
      state rather than inventing data when the experiment hasn't executed
- [x] An honest, unfavorable result (PSO/QPSO infeasible at 200 nodes under
      the reduced E3 budget) was found and reported, not hidden

## What's next (beyond this round)

1. Named traffic-level enum (Phase 1) — small, low priority
2. Exact solver for E1's optimality gap (Phase 5) — optional per master plan
3. Server-side `ReoptimizationResult` if/when a dedicated reoptimize endpoint
   is built (Phase 7)
4. Multi-scenario repetition of E1 (Phase 8) before making any "X beats Y"
   claim in the paper/PPT — a single scenario is not enough to generalize
5. Persistence/Docker/OSM/SUMO — only if a human explicitly decides to move
   into that phase (`Engineering.md` §13)
