# Q-DFRO — Requirements Traceability

Maps each SIH26137 requirement to the module that actually implements it.
Corrected against the real current file layout (the master plan's draft
table used hypothetical class names like `GraphGenerator`/`ReoptimizationService`
that don't match this codebase — every path below is verified to exist).

| Requirement | Implementation |
|---|---|
| Graph-based network model | `backend/problem_generator.py` (`generate_synthetic_scenario`), `backend/models.py` (`Node`, `Edge`) |
| Weighted roads with dynamic cost | `backend/models.py::Edge` (`traffic_factor`, `current_travel_time`) |
| Dynamic weight update | `POST /api/traffic/update` in `backend/main.py` |
| VRP mathematical formulation | `docs/mathematical_model.md`, implemented in `backend/fitness.py` |
| Vehicle/route constraints | `backend/fitness.py::evaluate_solution` (capacity/time penalties) |
| Route representation & decoding | `backend/decoder.py::decode_random_keys`, documented in `docs/qpso_specification.md` |
| Greedy baseline | `backend/optimizers/greedy.py` |
| Classical PSO baseline | `backend/optimizers/pso.py` |
| GA baseline | `backend/optimizers/ga.py` |
| QPSO (quantum-inspired algorithm) | `backend/optimizers/qpso.py` |
| Common evaluator (fair comparison) | `backend/fitness.py`, used by all four optimizers |
| Dynamic traffic incident | `frontend/src/App.jsx::handleSimulateIncident` + `POST /api/traffic/update` |
| Unified edge-cost engine (one pipeline) | `backend/realdata/conditions.py::recompute_edge_cost`, documented in `docs/dynamic_conditions.md` |
| Simulated traffic model + provider seam | `backend/realdata/traffic_model.py` (`SimulatedTrafficProvider`, `ExternalTrafficProvider`) |
| Real weather ingestion (Open-Meteo) | `backend/realdata/weather.py::OpenMeteoProvider`, exposed via `GET /api/weather` |
| Weather/traffic condition application | `POST /api/scenario/conditions` in `backend/main.py` |
| Condition model transparency | `GET /api/conditions/model` in `backend/main.py` |
| Condition-aware cache invalidation | `backend/route_cache.py::_canonical_scenario_repr` |
| Re-optimization after disruption | `frontend/src/App.jsx::handleReOptimize` → `POST /api/optimize` |
| Benchmarking across algorithms | `backend/optimizers/benchmark.py::run_benchmark`, `POST /api/benchmark` |
| Convergence tracking | `OptimizationResult.convergence_history` (all iterative optimizers) |
| Runtime measurement | `OptimizationResult.runtime_ms` |
| Scalability experiments | `backend/experiments/runner.py::run_e3_scalability` |
| Reproducibility (seeded, repeatable) | `seed` field throughout `models.py`; `backend/experiments/runner.py::run_e6_reproducibility` |
| Experiment evidence storage | `experiments/<name>/{config.json,*.csv,*.json}`, served read-only via `GET /api/experiments/{name}` |
| Executable software platform | `backend/main.py` (FastAPI) + `frontend/src/` (React/Leaflet) |
| Route/traffic/incident visualization | `frontend/src/components/NetworkMap.jsx` |
| Per-vehicle inspection | `frontend/src/components/VehicleInspector.jsx` |

Every path above is verified to exist in the repository as of this writing —
if a future change removes or renames one of these, update this table in the
same change, not later (`Agent.md` rule #8). See
`backend/tests/test_docs_consistency.py::test_traceability_paths_exist` for
the automated guard.
