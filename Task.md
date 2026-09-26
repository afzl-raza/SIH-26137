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

## Overview screen + benchmark visual upgrade ✅ Done (2026-09-26)

Source: a Figma file (fetched via its REST API - real design tokens pulled,
not guessed) plus 8 reference screenshots for a redesigned benchmark view.
Full plan: `adaptive-squishing-hinton` plan file.

- [x] New `Overview.jsx` home screen (gate in front of the real workflow, not
      a replacement of it) - sidebar, top bar, greeting/3-step cards,
      onboarding checklist, "today at a glance" metrics, live-map card,
      traffic alerts, recent routes, activity feed. SaaS-only chrome
      (workspace switcher, invites, notifications, onboarding checklist,
      alerts/recent-routes/activity feeds) is static decoration - no real
      multi-user or run-history backend exists.
- [x] **Revised**: "Today at a glance" and the live-map card were upgraded
      from illustrative placeholders to a real, independent
      `/api/problem/generate` + `/api/optimize` run (same endpoints and
      config shape Dashboard.jsx uses - no new backend code). Metric cards
      now show real vehicle/stop counts, travel time, distance, cost,
      runtime and feasibility; the map card embeds the real
      `NetworkMap.jsx` component showing the real optimized routes, labeled
      as a snapshot ("not a live vehicle feed"), not a live feed. This was
      a direct response to comparing against a teammate's parallel
      `ExecutiveOverview.jsx` (100% real-data, no illustrative exceptions
      at all) - see the note below.
      New Space Grotesk/near-black/orange visual system, scoped to this page
      only (`Inter`/`JetBrains Mono`/`Space Grotesk` were already all loaded
      as `font-sans`/`font-mono`/`font-display` - no new font loading).
- [x] `App.jsx` 3-way routing: Landing → Overview → Dashboard, with
      Dashboard's back button now returning to Overview, not Landing.
- [x] `BenchmarkPanel.jsx`: existing single-metric bar chart split into a
      grouped "Execution Speed" / "Solution Cost & Quality" two-panel view,
      plus a Log/Linear scale toggle and a Bars/Data Table toggle (the table
      already existed - this is a pure view switch). "Comparison Conditions"
      content was already word-for-word what the reference design showed.
- [x] `ArchetypeBenchmarkPanel.jsx`: added a Cost/Travel Time/Distance/Runtime
      metric-tab selector, best-feasible-value cell highlighting, and a
      "QPSO+LS wins N of M archetypes on {metric}" callout - computed from
      real benchmark results, with an explicit ✕ marker on infeasible cells
      so a good-looking number from a constraint-breaking run can't read as
      a win. No 5th algorithm or new script added (reference screenshot's
      "Five algorithms, five cities" concept was treated as inspiration
      only, per explicit decision).

Verified live end-to-end: Landing → Get Started → Overview → Plan your first
route → real Dashboard.jsx (Generate/Optimize/Disrupt/Re-Optimize/Benchmark
all unaffected) → grouped bars + Log scale + Data Table toggle all correct
on real data → Archetype matrix's win-count and cell highlighting verified
against actual computed values (not just visually) via direct DOM inspection.
Zero console errors on a clean session. Backend untouched, 373/373 passing.

**Outstanding: `origin/main` has diverged significantly** while this was
built - three teammate branches merged (`feature/authentication-flow`,
`time-window`, `frontend/ui-polish-executive-overview`), touching many of
the same files this round touched (`App.jsx`, `Dashboard.jsx`,
`BenchmarkPanel.jsx`, `ArchetypeBenchmarkPanel.jsx`, `ControlPanel.jsx`,
`NetworkMap.jsx` on the frontend; `fitness.py`, `decoder.py`, `models.py`,
`optimizers/benchmark.py`, `problem_generator.py` on the backend). Two
things flagged to the user, not yet resolved:
1. The authentication flow directly contradicts `CLAUDE.md`'s "Do not
   implement: Authentication" - left as-is per the user's explicit
   decision ("leave it, flag it to the team"), not reverted.
2. A teammate's `ExecutiveOverview.jsx` (a real-data-only results view,
   toggled as a mode inside `Dashboard.jsx` rather than a separate page)
   covers similar ground to this round's `Overview.jsx`. Compared live
   side-by-side (both stacks run simultaneously on different ports); the
   user preferred this round's visual design once its metrics/map were made
   real (see the "Revised" bullet above) but **the merge/reconciliation
   with `origin/main` has not happened yet** - this local `main` is still
   ahead of and diverged from `origin/main`, not pushed.

---

## Algorithm Correctness + Interactivity + Evidence Layer ✅ Done (2026-09-26)

Full plan: `adaptive-squishing-hinton` plan file. Fixes a real, measured
regression (plain QPSO losing to Greedy at 30+ jobs, frequently infeasible)
plus nine user-selected interactivity/evidence items.

- [x] Exact solver (`optimizers/exact.py`, bitmask Held-Karp + assignment DP,
      capped ≤10 jobs), wired into `/api/optimize` and `run_benchmark`
- [x] 2-opt/or-opt local search hybrid on QPSO (`optimizers/local_search.py`),
      Lamarckian reinjection, jump-term cap on the quantum update — closes the
      gap against Greedy at scale (measured, see `experiments/E3_scalability/`)
- [x] E1–E6 evidence regenerated against the corrected default
      (`qpso_ls`); a real bug this caught: the first regeneration showed
      `qpso`/`qpso_ls` byte-identical at 100+ jobs because the local-search
      interval could exceed the iteration budget — fixed and re-verified
      (`qpso.py`'s `effective_interval` now capped at `max_iter // 2`)
- [x] `Engineering.md`/`Task.md` stale references corrected (test count
      36→360, files 9→25, "four algorithms"→six, OSM marked done, exact
      solver marked done)
- [x] Configurable scenario params in UI (`demand_min`/`demand_max`/
      `vehicle_capacity_override`, folded into the scenario hash only when
      they diverge from the old defaults; collapsible "Scenario Shape"
      section in `ControlPanel.jsx`; verified live)
- [x] Manual depot/stop placement (`POST /api/problem/customize`, click an
      existing map node to set depot/stops; deterministic demand redraw
      seeded by the scenario's own seed; works for OSM scenarios too since
      both share `Node.id`; verified live end-to-end including optimize)
- [x] Road-closure toggle with reopen (frontend-only: reused the existing
      `POST /api/traffic/update` factor=1.0-clears-an-incident behavior;
      "Closed Roads (N)" panel + per-row Reopen button in `NetworkMap.jsx`;
      fixed a real bug caught while building this - a reopen was being
      reported as a *new* incident since `applyIncident` didn't distinguish
      the two; verified live)
- [x] Synthetic city archetype presets + feasibility matrix
      (`ArchetypeBenchmarkPanel.jsx` - 3 named parameter presets for the
      existing generator, explicitly labeled as synthetic presets, not a new
      topology engine; sequential real generate+benchmark calls per
      archetype, no client-side objective math; verified live - correctly
      showed an honest 1/5 feasible result for "Sprawling Network" and
      omitted the Exact column where >10 jobs, nothing smoothed over)
- [x] Before/after map slider (4-state toggle - Show Both/Before Only/After
      Only/Overlay - in `NetworkMap.jsx`, controlling the existing
      previous/active route opacity rather than adding new coordinates;
      BEFORE/AFTER legend chips so the line-style distinction isn't the only
      cue; verified live by inspecting actual SVG stroke-opacity per mode)
- [x] Run-reproducibility footer (`MetricCards.jsx` - scenario_hash, seed,
      algorithm, pop/iter and a client-captured completion timestamp shown
      directly under the results, all from the existing
      `/api/scenario/{id}/manifest` endpoint or a timestamp taken the moment
      the result actually arrived - nothing invented; verified live)

Backend: **373/373 passing**, verified after every backend-touching change,
not assumed. All 9 user-selected items complete.

Note: while verifying this item, `MetricCards.jsx`'s cost/time/distance
count-up animation appeared stuck at 0.00 in the automated browser pane used
for live verification this session. Traced to the pane's
`requestAnimationFrame` never firing in that specific tool environment (a
bare `requestAnimationFrame` test call also never fired, despite
`document.hidden` reporting `false`) - not a code bug. The raw
(non-animated) figures elsewhere in the same component, and the reported
runtime, were correct throughout. Left the animation code as-is.

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

## Phase 9 — Scalability / Realistic Network ⚠️ Partially done

- [x] OSM/OSMnx real road-network loading (`backend/realdata/osm_loader.py`,
      `osm_scenario.py`) — implemented since this section was last written
- [ ] SUMO traffic simulation — still deliberately deferred (`Engineering.md` §13)

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
- [x] Greedy, GA, PSO, QPSO (+ local search), and the exact solver all run
      through the same evaluator
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
2. ~~Exact solver for E1's optimality gap (Phase 5)~~ — done: `optimizers/exact.py`,
   auto-included in benchmarks at ≤10 jobs, "Gap vs Optimum" shown in
   `BenchmarkPanel.jsx`
3. Server-side `ReoptimizationResult` if/when a dedicated reoptimize endpoint
   is built (Phase 7)
4. Multi-scenario repetition of E1 (Phase 8) before making any "X beats Y"
   claim in the paper/PPT — a single scenario is not enough to generalize
5. Persistence/Docker/SUMO — only if a human explicitly decides to move
   into that phase (`Engineering.md` §13); OSM is done, see Phase 9 above
