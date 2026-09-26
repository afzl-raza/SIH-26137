# Q-DFRO — Quantum-Inspired Dynamic Fleet Route Optimizer

**SIH26137** — Quantum-Inspired Intelligent Traffic Route Optimization in
Transportation Systems Using Metaheuristic Optimization.
**Organization:** Egreen Quanta · **Team:** Byte Brain

A concept prototype that generates an urban road network, runs multiple vehicles
against delivery jobs under simulated traffic, optimizes fleet routes with a
Quantum-behaved Particle Swarm Optimization (QPSO) engine, and benchmarks it
against Greedy, classical PSO and GA baselines — all through one shared evaluator
so the comparison is fair. It demonstrates the full loop:

```
Generate network → Optimize routes → Trigger traffic incident
   → Re-optimize → Compare QPSO vs classical algorithms
```

This is a prototype, not the final production system — see
[`Engineering.md`](Engineering.md) §13 for what's deliberately out of scope.

---

## Documentation map

| Doc | What it's for |
|---|---|
| [`Engineering.md`](Engineering.md) | Canonical architecture, math formulation, algorithm and API spec |
| [`Task.md`](Task.md) | Phased task tracker — what's done vs outstanding |
| [`Agent.md`](Agent.md) | Rules for any AI coding agent working in this repo |
| [`CLAUDE.md`](CLAUDE.md) | Claude-Code-specific project instructions |
| [`Documnetation.md`](Documnetation.md) | Dated change log of past implementation decisions |

## Prerequisites

- Python 3.10+
- Node.js v18+

## Backend setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Health check: `GET http://localhost:8000/api/health`

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:3000` (Vite proxies `/api` to `localhost:8000`, see
`frontend/vite.config.js`).

## Running the backend tests

```bash
cd backend
python -m pytest tests/ -q
```

## Two views

The frontend opens on the **Executive Overview** — a narrative summary (real
scenario stats, primary outcome, key metrics, before/after comparison, the
route map, operational insights, and a benchmark comparison once one has been
run) meant to be readable at a glance, with no solver internals on it. The
header's **Engineering Control Room** toggle switches to the full operator
workspace — network map, scenario/conditions/operations/solver controls,
vehicle inspector, and the benchmark/scalability/reproducibility panels. Both
views read the same live application state; nothing is duplicated data, and
switching between them never re-runs anything.

## Demo flow

1. Generate a scenario (auto-generated on load, or click **Generate New Scenario**
   in the Engineering Control Room).
2. Click **Optimize Fleet** — QPSO produces fleet routes, metrics update.
3. Click **Simulate Incident** — a road on an active route gets congested.
4. Click **Re-Optimize** — routes recalculate around the disruption; before/after
   metrics are shown.
5. Click **Run Benchmark** — Greedy, PSO, GA and QPSO are run on the identical
   scenario and compared side by side.
6. Switch to **Executive Overview** at any point to see the same run summarized
   for a non-technical audience.

See `Task.md`'s "Immediate Next" section for what's actively being worked on.
