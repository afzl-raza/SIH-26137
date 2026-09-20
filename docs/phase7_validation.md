# Phase 7 — Validation, Scalability & Demo Hardening

This documents what was actually measured for Phase 7 (validate → measure →
fix → harden → reproduce → prepare demo). No feature work was done here; see
`backend/experiments/phase7_validation/` for the raw evidence files this
document summarizes.

## 1. Methodology

Every claim below comes from running the real backend code path — the same
FastAPI app the frontend calls (`fastapi.testclient.TestClient(main.app)`) —
against either live external services (Nominatim, Overpass, Open-Meteo) or
the deterministic synthetic generator. Nothing here is estimated or
hand-computed; each script under `backend/experiments/phase7_validation/`
writes its own JSON/CSV evidence file, and this document only restates those
files.

Reproduce any of it from `backend/`:

```bash
python -m pytest tests/ -q
python -m experiments.phase7_validation.run_real_city_validation
python -m experiments.phase7_validation.run_scalability
python -m experiments.phase7_validation.run_reproducibility
python -m experiments.phase7_validation.run_demo_timing
```

## 2. Test suite

`pytest tests/ -q` → **342 passed, 0 failed, 0 skipped** (1 pre-existing
`DeprecationWarning` from a third-party library, unrelated to this project).

### Sioux Falls edge-count bug (`test_qdfro_graph.py::test_sioux_falls_network_and_msa`)

**Root cause:** `backend/qdfro_graph/real_data.py` hand-transcribes the
canonical 24-node/76-directed-link Sioux Falls benchmark network (LeBlanc et
al. 1975; the version everyone cites is the TNTP file at
[bstabler/TransportationNetworks](https://github.com/bstabler/TransportationNetworks/blob/master/SiouxFalls/SiouxFalls_net.tntp)).
The implementation had 72 edges, not 76. Diffing the implementation's edge
list against the published TNTP link table showed the transcription had:

- dropped physical link 10↔17 (2 directed edges),
- dropped physical link 16↔18 (2 directed edges),
- dropped physical link 20↔22 (2 directed edges),
- and added a spurious link 17↔20 (2 directed edges) that does not exist in
  the canonical network.

Net: 76 − 6 + 2 = 72, matching the observed failure exactly. The test's
expectation of 76 was correct (it also matches the file's own docstring,
"24-node, 76-directed-link" — the code just didn't deliver what its own
comment promised).

**Fix:** replaced the incorrect edges with the three real links, using
capacity/length values derived from the same TNTP source (rounded to match
this file's existing precision convention), and removed the spurious 17↔20
edge. `backend/qdfro_graph/real_data.py` now reproduces the canonical
topology exactly (verified: implementation edge set == canonical edge set,
zero missing, zero extra).

**Evidence:** `pytest tests/test_qdfro_graph.py -q` → all pass; the diff is
in `backend/qdfro_graph/real_data.py` (search "16", "18", "20", "22" in the
edge list).

## 3. Test side effects

**Before:** `test_run_experiment_endpoint.py::test_run_experiment_e6_executes_real_runner_and_returns_result`
called the live `/api/experiments/E6_reproducibility/run` endpoint with no
output override, which writes into the real, tracked
`experiments/E6_reproducibility/raw_runs.csv` and `summary.json`. Every
`pytest` run silently modified committed evidence (confirmed: `git status`
showed `experiments/E6_reproducibility/raw_runs.csv` as modified after a
plain test run, with only `runtime_ms` differing — cost values were
identical, incidentally reinforcing Section 6's QPSO reproducibility result).

**After:** the test now uses `monkeypatch` to redirect
`main.EXPERIMENT_RUNNERS["E6_reproducibility"]` to call the real runner
function with `output_root=tmp_path`, and patches `main.EXPERIMENTS_ROOT` so
the endpoint's read-back also resolves against the temp directory. This
exercises the identical runner code the production endpoint uses, but writes
nowhere near the tracked `experiments/` directory. Confirmed:
`git status` is clean after a full `pytest` run.

## 4. Real-city validation

All three locations were validated end-to-end (geocode → OSM load → build
scenario → verify nodes/edges → weather → traffic conditions → QPSO →
route geometry → incident → re-optimize → benchmark → repeat-run
reproducibility check). Full detail: `validation_results.json`.

| Location | Nodes | Edges | QPSO Runtime | Incident → Route Changed | Re-optimize Runtime |
|---|---|---|---|---|---|
| Hazratganj, Lucknow, India | 652 | 1446 | 1.55 s | Yes (cost 117.53 → 117.00) | 1.62 s |
| Sector 18, Noida, India | 890 | 2098 | 1.89 s | Yes (cost 107.56 → 111.07) | 1.93 s |
| Piccadilly Circus, London, UK | 2054 | 3412 | 5.97 s | Yes (cost 122.22 → 125.48) | 4.74 s |

(Runtimes include the FastAPI request/response cycle, not just the solver
loop; the London OSM extract also had to fail over to a mirror Overpass
endpoint the first time, which is reflected in the 56.8 s `generate` step in
`validation_results.json` — see Section 7.)

**Algorithm comparison was not predetermined.** On the same
scenario/config, QPSO was the best of the four in none of the three cities
outright: PSO was cheapest in Lucknow (114.46 vs QPSO's 117.00), and GA was
cheapest in both Noida (110.69 vs 111.07) and London (121.24 vs 125.48).
QPSO was consistently competitive (within ~1–4% of the best) but never
declared "the winner" here — see `validation_results.json` → `benchmark`
per location.

## 5. Scalability

Measured with `run_scalability.py`: synthetic networks, QPSO only (population
30, iterations 50), matrix-build timed separately from the solve. Full data:
`scalability_results.csv`.

| Nodes | Edges | Matrix Time | QPSO Time | Peak Memory | Status |
|---|---|---|---|---|---|
| 100 | 496 | 0.150 s | 5.04 s | 0.48 MB | feasible |
| 250 | 1262 | 1.118 s | 14.48 s | 2.15 MB | **infeasible** (3 constraint violations) |
| 500 | 2454 | 4.278 s | 12.76 s | 8.00 MB | **infeasible** (8 constraint violations) |
| 1000 | 4844 | 8.907 s | 37.41 s | 35.29 MB | **infeasible** (12 constraint violations) |
| 2500 | 12164 | 74.607 s | 180.81 s | 243.61 MB | **infeasible** (37 constraint violations) |

All five requested sizes (100/250/500/1000/2500) completed without crashing.
**The honest limitation:** with a fixed solver budget (population 30,
iterations 50) and a fleet sized only for job count (not tuned per scale),
QPSO stops finding fully feasible solutions past 100 nodes, and the reported
`total_cost` at 250+ nodes is inflated by constraint-violation penalties, not
a genuine routing cost — those numbers are not comparable to the feasible
100-node run or to the E1/E3 evidence (smaller, fully-tuned scenarios). This
matches the same pattern already visible in the pre-existing
`experiments/E3_scalability/results.csv` (PSO/QPSO both go infeasible at 200
nodes there too). **The system's demonstrated feasible operating range on
this hardware, at this solver budget, is on the order of ~100 routing
terminals**, not "2500 nodes" — the code accepted 2500 nodes, but did not
solve them well. Runtime scaling itself (matrix build and QPSO time both
growing with size) is well-behaved and did not fail.

## 6. Reproducibility

**Optimizer-level (isolated from external data):** `run_reproducibility.py`
regenerates the identical scenario (30 nodes / 15 jobs / 3 vehicles, seed 42)
twice per algorithm and runs Greedy, PSO, GA and QPSO with the same seed and
config both times. Result: **cost, travel time, distance, full route
assignments (vehicle→job→node-path) and convergence history were bit-identical**
across both runs, for all four algorithms (`reproducibility_results.json`).
Only wall-clock `runtime_ms` differed, as expected.

**End-to-end (real-city):** each of the three real-city runs in Section 4
also re-ran `/api/optimize` twice more on the same `scenario_id` with the
same seed/config; QPSO cost was identical across all three repeats in every
city (see `reproducibility.all_equal_to_original` in `validation_results.json`).

**Documented reproducibility boundary:** this holds for the *optimizer and
scenario construction*. It does **not** extend to re-fetching a fresh scenario
from scratch on a later day: Nominatim/Overpass could return different data
if OSM has since been edited, and weather is a live observation with a
15-minute cache TTL, so re-running the full pipeline hours apart can
legitimately return a different weather multiplier (not a bug — it is a
live external reading, correctly labelled with its own `weather_source`).

## 7. Incident validation

Verified on 4 independent scenarios: the pre-existing synthetic
`experiments/E4_traffic_disruption/result.json` (untouched), and all three
real-city runs plus the cached demo run in Section 8. In every case the
workflow NORMAL → OPTIMIZE → INCIDENT → re-optimize produced a real,
measured route change:

| Scenario | Before cost | After cost | Vehicles changed |
|---|---|---|---|
| E4 (synthetic, pre-existing) | 196.55 | 200.92 | 3 |
| Lucknow (real OSM) | 117.53 | 117.00 | 3 |
| Noida (real OSM) | 107.56 | 111.07 | 3 |
| London (real OSM) | 122.22 | 125.48 | 3 |
| Cached demo (Lucknow) | 117.53 | 117.00 | (see `demo_run.json`) |

No scenario needed to be discarded for failing to show a route change — a
5x congestion factor on an active-route edge reliably triggered
re-routing across every case tested.

## 8. Demo mode — Cached OSM Demo Scenario

**Location:** Hazratganj, Lucknow, India (radius 1200 m; 652 nodes, 1446
edges — the smallest/fastest of the three validated real networks).

This is real OpenStreetMap data, not synthetic or invented: it was fetched
live from Overpass during Section 4's validation run and is now served from
the existing on-disk cache (`backend/realdata/cache.py` / `.cache/` at the
repo root — no second caching system was introduced). Confirmed by directly
re-requesting the same location and observing `provenance: "cache"` for both
the Nominatim geocode and the Overpass extract, with the request dropping
from ~3.0 s (first, live fetch) to ~0.15 s (served from cache).

Label it explicitly as **"Cached OSM Demo Scenario"** in any presentation
material — never "Live" — since the road network is not being re-fetched
during the demo. Routes and benchmarks are still computed live, at
presentation time, by the real optimizer; only the network/geocode fetch is
served from disk.

**External dependencies during the cached run:**

| Dependency | Source during demo run |
|---|---|
| Nominatim (geocoding) | cache |
| Overpass (road network) | cache |
| Open-Meteo (weather) | cache (15-minute TTL; falls back to a live fetch, or to the app's explicit no-data fallback, if expired/unreachable — never fabricated) |

See `demo_run.json` for the full run this table summarizes.

## 9. Frontend hardening

No redesign. Reviewed `App.jsx` and all operator-facing components for
loading/error/empty states and for any client-side computation of
optimization numbers. Three real gaps were found and fixed:

1. `handleOptimize`, `applyIncident` and `handleRunBenchmark` in `App.jsx`
   previously showed a generic hardcoded error string on failure
   ("Optimization failed", etc.) instead of the backend's actual `detail`
   message, unlike the other two handlers which already did this. All five
   now surface the backend's real error text.
2. `NetworkMap.jsx`'s empty state showed the same static "Generate a
   scenario..." message during the automatic initial load as when truly
   idle, with no feedback that a request was in flight. Added a loading
   spinner state for that case.
3. `ControlPanel.jsx` had no visible loading indicator for
   generate/conditions/incident/benchmark requests (only Optimize/Re-Optimize
   had one) — buttons just disabled silently. Added a generic "Working..."
   indicator.

**Fabrication check:** one real instance found and removed —
`NetworkMap.jsx`'s per-edge popup was recomputing the α/β/γ cost terms
client-side, duplicating `backend/fitness.py`'s objective function with no
backend field backing it (a latent drift risk: it currently agreed with the
backend by coincidence, not by construction, in violation of this project's
"no duplicated objective functions" rule). Removed; the popup now shows only
real backend-reported fields. Everything else in the UI (route metrics,
benchmark metrics, traffic state, weather metadata, route geometry) reads
directly from API response fields; the only client-side arithmetic left is
cosmetic (percentage deltas between two already-fetched numbers, pixel
positions for a chart), not fabricated metrics.

Files touched: `frontend/src/App.jsx`, `frontend/src/components/NetworkMap.jsx`,
`frontend/src/components/ControlPanel.jsx`. Verified with a production
`vite build` (succeeds) after the changes.

## 10. Demo performance

Measured with `run_demo_timing.py` on the Cached OSM Demo Scenario
(Section 8):

| Step | Time |
|---|---|
| Scenario load (cached geocode + OSM) | 0.148 s |
| Weather fetch | 0.069 s |
| Initial optimization (QPSO) | 0.546 s |
| Incident update | 0.142 s |
| Re-optimization (QPSO) | 0.558 s |
| Benchmark (Greedy + PSO + GA + QPSO) | 1.503 s |
| **Total workflow** | **2.966 s** |

This is measured, end-to-end wall-clock time for the full demo sequence on
one machine, for one scenario size (652 nodes / 12 jobs / 3 vehicles). It
supports describing the demo as running in "under 3 seconds end-to-end on a
cached network of this size" — it does not support a general "real-time"
claim, since Section 5 shows both matrix-build and solve time grow
substantially with network size (74.6 s and 180.8 s respectively at 2500
nodes).

## 11. Known limitations

- **Feasibility at scale (Section 5):** the current fixed solver budget does
  not reliably find feasible solutions above ~100 routing terminals; cost
  values above that size are penalty-dominated, not genuine routing costs.
- **No single "best" algorithm:** QPSO does not universally beat PSO/GA
  (Section 4) — algorithm choice is scenario-dependent, and the prototype
  reports this rather than asserting QPSO superiority.
- **Weather reproducibility boundary:** repeated runs hours/days apart can
  see a different (still real, still labelled) weather observation; this is
  expected, not a bug.
- **OSM data quality varies by place:** the three validated cities showed
  meaningfully different fractions of ways with an explicit OSM `maxspeed`
  tag (Lucknow: 3/414 ways; Noida: 8/698; London: 2296/2337) — most speeds in
  the two Indian cities come from the code's highway-class fallback table,
  not from OSM tags, which is expected of that data and is reported by the
  API's own `speed_source` field, not hidden.
- **Overpass endpoint variability:** the London validation run needed 56.8 s
  because the primary Overpass mirror was slow/unavailable and the loader
  fell through to a secondary mirror (`overpass.kumi.systems`) — this
  fallback worked as designed, but first-load time for an unfamiliar large
  area is not guaranteed to be fast; the Cached OSM Demo Scenario exists
  specifically so a live presentation does not depend on this.
- **Secondary Q-DFRO graph engine** (`/api/qdfro-graph/*`, the Sioux Falls
  MSA-assignment surface) was fixed for topology correctness (Section 2) but
  was not separately re-validated end-to-end for Phase 7's real-city/demo
  objectives — those objectives target the primary `ProblemScenario`
  pipeline (`/api/problem/generate`, `/api/optimize`, etc.), which is what
  the frontend actually drives.

## 12. External dependency risk

Nominatim, Overpass and Open-Meteo are all free public services with usage
policies and no uptime guarantee. All three failure modes are already
handled by existing, tested code (not new to Phase 7):
`realdata/osm_loader.py` serves a stale cached network (explicitly labelled
`cache-stale`) rather than failing when every Overpass mirror is
unreachable and a prior extract exists; `realdata/weather.py` returns an
explicit no-data fallback (never a fabricated reading) when Open-Meteo is
unreachable; both are covered by existing unit tests
(`test_network_failure_serves_cached_network_marked_stale`,
`test_a_provider_failure_with_no_cache_returns_an_explicit_fallback`, etc.).
Phase 7's contribution is verifying this behavior holds for a real cached
location end-to-end (Section 8), not building new fallback logic.

## 13. Real vs. simulated data — summary

| Data | Real or simulated | Source |
|---|---|---|
| Road network (geometry, topology, speed limits) | Real | OpenStreetMap via Overpass |
| Place resolution | Real | Nominatim |
| Weather | Real | Open-Meteo (or an explicit, clearly-labelled fallback on failure) |
| Traffic congestion / incidents | Simulated | Operator-driven condition model (OSM carries no live traffic) |
| Delivery jobs, vehicle capacities/demand | Simulated | Seeded generator over real road nodes |

## 14. How to reproduce

```bash
cd backend
python -m pytest tests/ -q
python -m experiments.phase7_validation.run_real_city_validation   # needs internet
python -m experiments.phase7_validation.run_scalability            # ~5 minutes, CPU-bound
python -m experiments.phase7_validation.run_reproducibility
python -m experiments.phase7_validation.run_demo_timing            # needs run_real_city_validation to have cached Lucknow at least once
```

All four scripts are idempotent and safe to re-run; none of them write into
`experiments/E1_algorithm_comparison/` … `E6_reproducibility/` (the pre-existing
evidence from earlier phases), only into `backend/experiments/phase7_validation/`.
