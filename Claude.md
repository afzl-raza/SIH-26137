# Claude Development Instructions

## Project

SIH26137 — Quantum-Inspired Intelligent Traffic Route Optimization

You are building a **concept prototype**, not the final production system.

The primary goal is to create a convincing technical demonstration for SIH judges/mentors.

---

## Primary Demonstration

The complete demonstration must follow this scenario:

```text
1. Load urban transportation network
2. Display vehicles and delivery locations
3. Display current traffic conditions
4. Generate optimized routes
5. Show route metrics
6. Increase congestion on selected road(s)
7. Trigger re-optimization
8. Show changed routes
9. Compare QPSO with classical algorithms
```

---

## Implementation Priority

Build in this order:

### Phase 1 — Problem Model

Create:

* Graph
* Road
* Vehicle
* Customer/job
* Traffic state
* Routing constraints

---

### Phase 2 — Objective Function

Implement a configurable objective:

```text
Cost =
    α × TravelTime
  + β × Distance
  + γ × Congestion
```

The function must also account for infeasible solutions through constraint penalties or repair.

---

### Phase 3 — Baseline

Implement a simple:

**Nearest Neighbour / Greedy**

This establishes a basic reference solution.

---

### Phase 4 — QPSO

Implement the QPSO optimization engine.

Required capabilities:

* Population initialization
* Solution evaluation
* Personal/global best or equivalent QPSO state
* Iterative update
* Route decoding
* Constraint handling
* Best-solution tracking
* Convergence history

Keep the implementation understandable and modular.

---

### Phase 5 — Dynamic Traffic

Implement simulated traffic changes.

Example:

```text
Before:
Road A → travel time = 5 min

After incident:
Road A → travel time = 20 min
```

Then rerun the optimizer.

The UI should visibly demonstrate that route selection changes.

---

### Phase 6 — Benchmarking

Run the same problem using:

* Greedy
* PSO or GA
* QPSO

For small instances optionally include an exact OR-Tools solution.

Record:

```text
algorithm
total_cost
travel_time
distance
runtime
constraint_violations
convergence_history
```

---

## Important Rules

### Do not fabricate results

Never hard-code claims such as:

> QPSO is 20% faster than PSO.

Results must come from actual experiments.

---

### Do not overbuild

Do not implement:

* Authentication
* Payments
* Driver management
* Notifications
* Live GPS
* Production deployment
* Advanced traffic prediction

---

### Do not hide algorithm limitations

If QPSO performs worse than PSO or GA, display the actual result.

The prototype should demonstrate **scientific evaluation**, not predetermined superiority.

---

## Code Quality

Prefer:

* Small modules
* Clear names
* Type hints
* Configuration files
* Deterministic experiments
* Unit tests for important functions
* Minimal dependencies

Avoid:

* Monolithic files
* Hard-coded routing logic
* Algorithm logic inside frontend components
* Duplicated objective functions

---

## Definition of Done

The prototype is considered complete when:

```text
Map
 ↓
Traffic
 ↓
Vehicles + Jobs
 ↓
QPSO
 ↓
Routes
 ↓
Traffic Change
 ↓
Re-optimization
 ↓
Benchmark
```

can be demonstrated end-to-end from the UI.

---

## Git Workflow

This repo's remote is `https://github.com/afzl-raza/SIH-26137.git`, branch `main`.

After completing any meaningful change to this project (a fix, a feature, a
config change, a new file), commit it and push to `main` automatically —
do not stop to ask for confirmation to commit or push. Still show the user
what was committed (files changed, commit message) so they can see it after
the fact.

This does not override the general rule against destructive git operations
(`push --force`, `reset --hard`, etc.) — those still require explicit
confirmation every time.
