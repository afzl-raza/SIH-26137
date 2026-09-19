# Q-DFRO — Experiment Protocol

Methodology for experiments E1–E6, implemented in `backend/experiments/runner.py`
and runnable via:

```bash
cd backend
python -m experiments.runner --experiment all
```

Each experiment writes a frozen `config.json` (its exact parameters) plus raw
and processed output to `experiments/<name>/` at the repo root. A second run
into the same folder with different parameters raises rather than silently
overwriting evidence (`runner.py::_write_frozen_config`).

**Fair-benchmark rule, held everywhere in E1–E6:** every algorithm receives
the identical graph, vehicles, jobs, traffic state, seed and objective
weights within a given experiment; only the algorithm (and, in E3, its
runtime-appropriate solver budget — see below) varies.

The numbers below are the actual output of the run described, generated on
this date — not illustrative placeholders. Re-running with the same
`config.json` parameters reproduces them exactly (QPSO/PSO/GA are seeded).

---

## E1 — Algorithm comparison

**Question:** how do Greedy/PSO/GA/QPSO compare on an identical scenario?

**Config:** 30 nodes / 15 jobs / 3 vehicles / seed 42, full solver budget
(population 40, iterations 100).

**Result** (`experiments/E1_algorithm_comparison/results.csv`):

| Algorithm | Total Cost | Travel Time | Distance | Runtime (ms) | Feasible |
|---|---|---|---|---|---|
| Greedy | 222.73 | 183.42 | 78.63 | 7.0 | ✓ |
| PSO | 192.98 | 162.84 | 60.28 | 521.6 | ✓ |
| GA | 198.36 | 165.38 | 65.96 | 631.9 | ✓ |
| QPSO | 196.55 | 165.15 | 62.81 | 518.7 | ✓ |

On this scenario, PSO edges out QPSO and GA slightly, and all three
metaheuristics beat Greedy substantially. **This is reported as-is** — the
project's own principle is that QPSO is a hypothesis to test, not a
predetermined winner (see `Engineering.md` §1, `CLAUDE.md`). A single
30/15/3 scenario is not sufficient to generalize "PSO > QPSO" — that would
need E6-style repetition across more scenarios, which is listed as future
work.

## E2 — Convergence

**Question:** how does best cost evolve over iterations for PSO/GA/QPSO?

Reuses E1's `convergence_history` arrays. Output:
`experiments/E2_convergence/convergence.csv` (columns: `algorithm,iteration,best_cost`).
QPSO's recorded curve drops from `271.04` (iteration 0, shared initial
population with PSO) and settles at `196.55` by iteration 97, unchanged
through iteration 99 — i.e. it converged before the iteration budget was
exhausted, not because iterations ran out.

## E3 — Scalability

**Question:** how does runtime and solution quality change as the network
grows?

**Design note (found by actually running this, not assumed):** an earlier
version of this experiment held the fleet size fixed at 3 vehicles while
scaling jobs up to 100. That produced exploding "infeasible" costs (into the
tens of millions) at 100+ nodes — not because the optimizers got worse, but
because a 3-vehicle fleet is structurally incapable of serving 100 jobs
within the default `max_route_time`. That measured fleet undersizing, not
optimizer scalability, so `run_e3_scalability` now scales vehicle count with
job count (`jobs_per_vehicle=5.0`, matching the default demo's ratio) to keep
the underlying problem feasible as it grows.

**Config:** node counts `[20, 50, 100, 200]`, jobs = `0.5 × nodes`, vehicles =
`jobs / 5` (rounded), reduced solver budget (population 20, iterations 30 —
deliberately smaller than E1's so a 4-algorithm × 4-size sweep completes in
reasonable time; **do not compare these costs directly against E1's**, which
uses the full budget).

**Result** (`experiments/E3_scalability/results.csv`):

| Nodes | Jobs | Vehicles | Greedy | PSO | GA | QPSO |
|---|---|---|---|---|---|---|
| 20 | 10 | 2 | 173.4 (✓, 4.1ms) | 133.8 (✓, 51.1ms) | 133.1 (✓, 60.7ms) | 133.1 (✓, 50.4ms) |
| 50 | 25 | 5 | 327.4 (✓, 19.3ms) | 369.9 (✓, 137.2ms) | 386.5 (✓, 160.2ms) | 392.1 (✓, 140.6ms) |
| 100 | 50 | 10 | 562.5 (✓, 56.8ms) | 868.6 (✓, 309.5ms) | 809.1 (✓, 337.3ms) | 845.6 (✓, 353.2ms) |
| 200 | 100 | 20 | 1218.9 (✓, 277.0ms) | 78145.4 (✗, 893.5ms) | 2142.7 (✓, 856.5ms) | 41724.3 (✗, 810.3ms) |

**Honest finding:** at 200 nodes, under the *reduced* E3 solver budget, PSO
and QPSO both fail to reach a fully feasible solution within 30 iterations
(their reported cost includes an unresolved penalty term), while Greedy and
GA in this run reached feasibility. This is reported as a genuine limitation
of the reduced-budget scalability sweep, not smoothed over — a
production-scale deployment would need a larger iteration/population budget
at larger problem sizes, which is itself a useful scalability finding.
Runtime scales roughly with problem size for all four algorithms, as expected.

## E4 — Traffic disruption

**Question:** what happens to cost and routing when an active-route edge
gets congested?

**Config:** default 30/15/3/seed 42 scenario, QPSO, congestion factor 3.5×
applied to an edge on an active route (edge `0 → 5` in this run).

**Result** (`experiments/E4_traffic_disruption/result.json`):

- `before_cost`: 196.55
- `after_cost`: 200.92
- `reoptimization_runtime_ms`: 508.8
- `changed_vehicle_ids`: `[1, 2, 3]` — all three vehicles' routes changed in
  response to one congested edge, since QPSO re-searches the whole fleet
  assignment rather than patching a single route.

## E5 — Traffic severity

**Question:** how does cost respond as congestion on one edge increases?

**Config:** same scenario/edge as E4, factors `[1.0, 1.5, 2.5, 3.5, 5.0]`, QPSO.

**Result** (`experiments/E5_traffic_severity/results.csv`): cost rises
non-monotonically at low congestion (196.55 → 196.22 at 1.5×, within QPSO's
stochastic run-to-run noise) then increases with severity (199.14 at 2.5×,
200.92 at 3.5× and 5.0× — cost plateaus past 3.5× in this run, meaning QPSO
found an alternate route whose cost no longer depends on that specific edge's
severity beyond a point).

## E6 — Reproducibility

**Question:** how stable is QPSO's result across different solver seeds on
the same scenario?

**Config:** default 30/15/3 scenario, QPSO, seeds `[1, 2, 3, 4, 5]`.

**Result** (`experiments/E6_reproducibility/summary.json`):

- Mean cost: 196.96, Std. dev.: 2.90, Min: 192.98, Max: 200.65

A ~1.5% coefficient of variation across 5 independent seeds on the same
problem — QPSO's solution quality is stable but not perfectly deterministic
across seeds (expected for a stochastic metaheuristic; re-running the *same*
seed is exactly reproducible, per `test_e6_reproducibility_determinism_and_stats`).
