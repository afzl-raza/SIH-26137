# Q-DFRO — Quantum-Inspired Dynamic Fleet Route Optimizer

### SIH26137 · Quantum-Inspired Intelligent Traffic Route Optimization in Transportation Systems Using Metaheuristic Optimization

**Organization:** Egreen Quanta  
**Team:** Byte Brain 2.0  
**Project Type:** Concept Prototype / Intelligent Transportation System

---

## 🚦 What is Q-DFRO?

**Q-DFRO (Quantum-Inspired Dynamic Fleet Route Optimizer)** is a simulation-based intelligent transportation platform that demonstrates how a fleet of vehicles can dynamically plan and re-plan delivery routes when traffic conditions change.

Instead of evaluating route optimization in isolation, Q-DFRO demonstrates the complete operational cycle:

```text
Generate Road Network
        ↓
Create Fleet & Delivery Jobs
        ↓
Optimize Routes
        ↓
Simulate Traffic Disruption
        ↓
Detect Changed Conditions
        ↓
Re-Optimize Fleet
        ↓
Benchmark Optimization Strategies
```

The system uses **Quantum-behaved Particle Swarm Optimization (QPSO)** as its primary optimization approach and compares its results against classical optimization baselines:

- Greedy
- Particle Swarm Optimization (PSO)
- Genetic Algorithm (GA)
- Quantum-behaved Particle Swarm Optimization (QPSO)

All algorithms are evaluated through the **same scenario and evaluation pipeline**, making the comparison consistent and reproducible.

> **Important:** Q-DFRO is a research-oriented concept prototype designed to demonstrate the optimization workflow. It is not intended to represent a production-ready traffic management system.

---

# 🎯 Problem We Are Addressing

Urban fleet operations operate in environments where road conditions can change continuously.

A route that is efficient when a vehicle starts its journey may become inefficient because of:

- 🚧 Road congestion
- 🚦 Traffic incidents
- 🛣️ Changed travel conditions
- 🚚 Multiple vehicles competing for efficient routes
- 📦 Multiple delivery jobs
- ⏱️ Increasing travel time

Traditional static route planning does not naturally demonstrate how an entire fleet should respond when the environment changes.

Q-DFRO explores a different approach:

> **Optimize the fleet → introduce a disruption → adapt the routes → measure the impact.**

---

# 💡 Core Idea

Q-DFRO treats fleet routing as a dynamic optimization problem.

A scenario contains:

- A generated urban road network
- Multiple vehicles
- Delivery jobs
- Vehicle capacities
- Travel costs
- Simulated traffic conditions
- Traffic incidents

The optimizer searches for a fleet-level route configuration that balances operational objectives such as:

- Total travel distance
- Travel time
- Route cost
- Delivery feasibility
- Fleet utilization

When a traffic incident affects an active route, the system modifies the scenario and performs another optimization cycle.

This allows the platform to demonstrate **dynamic re-routing rather than one-time route planning**.

---

# 🧠 Why QPSO?

The primary optimization engine is based on **Quantum-behaved Particle Swarm Optimization (QPSO)**.

QPSO extends the particle-swarm optimization idea using a quantum-inspired search mechanism.

In Q-DFRO, QPSO is used to explore possible fleet route configurations and search for improved solutions within the simulated environment.

The prototype does not assume that QPSO is automatically superior.

Instead, it provides a common evaluation framework where QPSO can be compared with classical approaches under the **same scenario, jobs, fleet and evaluation criteria**.

This makes the experiment more meaningful than comparing algorithms using different inputs or evaluation logic.

---

# 🏗️ System Architecture

```text
┌──────────────────────────────────────────────┐
│                  Frontend                    │
│                                              │
│  Executive Overview  ↔  Engineering Control  │
│                           Room               │
└──────────────────────┬───────────────────────┘
                       │
                       │ REST API
                       ▼
┌──────────────────────────────────────────────┐
│                  FastAPI                     │
│                                              │
│  Scenario Management                         │
│  Fleet & Job Management                      │
│  Optimization                                │
│  Incident Simulation                         │
│  Re-optimization                             │
│  Benchmarking                                │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│             Optimization Engine              │
│                                              │
│  Greedy   │   PSO   │   GA   │   QPSO       │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│              Shared Evaluator                │
│                                              │
│  Distance │ Time │ Cost │ Feasibility        │
│  Fleet Metrics │ Route Metrics               │
└──────────────────────────────────────────────┘
```

The frontend and backend operate on the same live scenario state.

The **Executive Overview** and **Engineering Control Room** are two representations of the same application state — not two separate implementations.

---

# 🖥️ Two User Experiences

Q-DFRO is designed for both **non-technical stakeholders** and **technical users**.

## 1. Executive Overview

The Executive Overview is designed for someone who wants to understand:

> **What happened? What changed? What was the outcome?**

It focuses on the story of the simulation rather than algorithm internals.

It presents information such as:

- Scenario summary
- Fleet status
- Delivery status
- Primary outcome
- Key operational metrics
- Before/after comparison
- Route visualization
- Operational insights
- Benchmark results after a benchmark has been executed

The goal is to make the system understandable even to someone without knowledge of optimization algorithms.

### Example narrative

Instead of exposing technical solver details:

> `QPSO iteration 37 achieved minimum objective = ...`

the Executive Overview can communicate the result in operational language:

> **Traffic disruption detected on an active delivery route. The fleet was re-optimized and alternative routes were generated.**

Technical information remains available in the Engineering Control Room.

---

## 2. Engineering Control Room

The Engineering Control Room is the technical workspace for interacting with the simulation.

It provides access to:

- 🗺️ Network map
- ⚙️ Scenario configuration
- 🚚 Fleet controls
- 📦 Delivery jobs
- 🚧 Traffic conditions
- 🧠 Solver controls
- 🔍 Vehicle inspection
- 📊 Benchmarking
- 📈 Scalability information
- 🔁 Reproducibility controls
- 🧪 Experiment information

The control room is intended for users who want to understand **how the system works and how the optimization behaves**.

---

# 🔄 End-to-End Demo

The complete demonstration can be run in a few steps.

### Step 1 — Generate Scenario

A road network, fleet and delivery jobs are generated.

The application can automatically create a scenario on startup, or a new scenario can be generated from the Engineering Control Room.

---

### Step 2 — Optimize Fleet

Click:

**Optimize Fleet**

QPSO generates a fleet routing solution.

The application updates the route map and operational metrics.

---

### Step 3 — Simulate Traffic Incident

Click:

**Simulate Incident**

A traffic disruption is introduced on a road that affects an active route.

The scenario has now changed.

---

### Step 4 — Re-Optimize

Click:

**Re-Optimize**

The optimizer searches for a new fleet routing configuration based on the changed conditions.

The application can then display the difference between:

```text
Before Incident
       ↓
Traffic Disruption
       ↓
After Re-optimization
```

---

### Step 5 — Run Benchmark

Click:

**Run Benchmark**

The same scenario is evaluated using:

```text
Greedy
PSO
GA
QPSO
```

The results are presented side by side using the shared evaluation framework.

---

### Step 6 — View Executive Summary

Switch to:

**Executive Overview**

The same live scenario is transformed into a stakeholder-friendly summary.

No new optimization is triggered.

No duplicate simulation is performed.

The overview simply presents the current state in a more accessible format.

---

# 📊 Fair Benchmarking

One of the important design principles of Q-DFRO is **consistent evaluation**.

The algorithms are evaluated using the same:

- Road network
- Fleet
- Delivery jobs
- Traffic conditions
- Constraints
- Objective evaluation
- Scenario state

Conceptually:

```text
                 Same Scenario
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
      Greedy          PSO           GA
        │             │             │
        └─────────────┼─────────────┘
                      ↓
                     QPSO
                      │
                      ↓
              Shared Evaluator
                      │
                      ↓
             Comparable Results
```

This architecture makes the benchmark useful for experimentation because differences in results are not intentionally created by giving algorithms different scenarios.

---

# 🚧 Dynamic Traffic Simulation

The project specifically demonstrates the effect of changing conditions.

A typical experiment follows:

```text
Initial Network
      ↓
Initial Fleet Routes
      ↓
Traffic Incident
      ↓
Affected Route
      ↓
Re-optimization
      ↓
Updated Fleet Routes
```

This allows the system to investigate how an optimization strategy responds to a changing environment rather than only measuring a static routing solution.

---

# 📈 Metrics

The platform tracks operational and optimization metrics that can be used to understand the quality of a routing solution.

Examples include:

| Metric | Purpose |
|---|---|
| Total Distance | Measures overall route distance |
| Travel Time | Estimates fleet travel duration |
| Route Cost | Represents optimization cost |
| Feasibility | Checks whether routing constraints are satisfied |
| Vehicle Utilization | Shows how fleet capacity is being used |
| Delivery Completion | Tracks delivery-job coverage |
| Before/After Metrics | Shows the effect of disruption and re-optimization |
| Benchmark Metrics | Enables algorithm comparison |

The exact objective formulation and constraints are defined in [`Engineering.md`](Engineering.md).

---

# 🧪 Reproducibility

Q-DFRO is structured as an experimental prototype.

Scenarios and optimization runs can be treated as repeatable experiments using controlled inputs and shared evaluation logic.

This is useful for:

- Algorithm experimentation
- Parameter testing
- Benchmark comparisons
- Demonstration scenarios
- Performance analysis

Detailed reproducibility and engineering specifications are documented in [`Engineering.md`](Engineering.md).

---

# 🛠️ Technology Stack

## Frontend

- React
- Vite
- JavaScript
- Interactive map and visualization components

## Backend

- Python
- FastAPI
- Uvicorn
- Pytest

## Optimization

- QPSO
- Particle Swarm Optimization
- Genetic Algorithm
- Greedy baseline

## Development

- Node.js 18+
- Python 3.10+
- npm
- Git

---

# 📁 Project Documentation

The repository contains dedicated documentation for different audiences.

| Document | Purpose |
|---|---|
| [`Engineering.md`](Engineering.md) | Architecture, mathematical formulation, algorithms, API specification and engineering decisions |
| [`Task.md`](Task.md) | Implementation tracker and current development status |
| [`Agent.md`](Agent.md) | General instructions for AI coding agents |
| [`CLAUDE.md`](CLAUDE.md) | Claude Code-specific development instructions |
| [`Documnetation.md`](Documnetation.md) | Historical implementation decisions and change log |

---

# ⚙️ Installation

## Prerequisites

Make sure the following are installed:

- Python 3.10+
- Node.js 18+
- npm

---

## Backend

```bash
cd backend

pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

Backend health check:

```text
GET /api/health
```

Local endpoint:

```text
http://localhost:8000/api/health
```

---

## Frontend

Open another terminal:

```bash
cd frontend

npm install

npm run dev
```

The frontend will be available at:

```text
http://localhost:3000
```

The Vite development server proxies `/api` requests to the backend running on port `8000`.

Configuration can be found in:

```text
frontend/vite.config.js
```

---

# 🧪 Running Tests

From the backend directory:

```bash
cd backend

python -m pytest tests/ -q
```

This runs the backend test suite.

---

# 🚀 Quick Start

For the fastest demonstration:

```text
1. Start Backend
       ↓
2. Start Frontend
       ↓
3. Open localhost:3000
       ↓
4. Generate Scenario
       ↓
5. Optimize Fleet
       ↓
6. Simulate Incident
       ↓
7. Re-Optimize
       ↓
8. Run Benchmark
       ↓
9. View Executive Overview
```

---

# 🎬 Recommended SIH Demonstration

For a short project demonstration, the following sequence tells the complete story:

### **1 — Show the network**

Introduce the generated urban road network, vehicles and delivery jobs.

### **2 — Optimize**

Run the initial QPSO optimization and show the generated fleet routes.

### **3 — Disrupt**

Trigger a simulated traffic incident affecting an active route.

### **4 — Adapt**

Run re-optimization and show the updated routes.

### **5 — Compare**

Run the benchmark and compare Greedy, PSO, GA and QPSO using the same scenario.

### **6 — Explain**

Switch to Executive Overview and present the operational outcome in a non-technical format.

This creates a simple narrative:

> **Plan → Disrupt → Adapt → Compare**

---

# 🌍 Potential Real-World Direction

Q-DFRO is currently a simulation prototype.

A future production-oriented system could potentially incorporate real-world data sources such as:

- Live traffic information
- GPS fleet telemetry
- Historical traffic patterns
- Real road-network data
- Delivery time windows
- Vehicle-specific constraints
- Fuel or energy consumption
- Dynamic fleet availability
- Real-time incident feeds

These capabilities are **outside the current prototype scope** and are intentionally separated from the current implementation.

---

# 🔬 Current Scope

The current prototype focuses on demonstrating:

- Dynamic fleet routing
- Simulated urban road networks
- Traffic disruption
- Route re-optimization
- QPSO-based optimization
- Classical algorithm baselines
- Shared evaluation
- Benchmarking
- Executive-level visualization
- Engineering-level controls
- Reproducible experiments

---

# 🚫 Out of Scope

Q-DFRO does not currently claim to be:

- A production traffic-management platform
- A replacement for navigation systems
- A live traffic prediction service
- A city-scale deployment
- A guaranteed globally optimal routing system
- A direct integration with real-world fleet infrastructure

The prototype is intended to demonstrate the **optimization concept and experimental workflow**.

See [`Engineering.md`](Engineering.md) §13 for the detailed out-of-scope definition.

---

# 👥 Team

### Byte Brain

**SIH26137 — Egreen Quanta**

Project:

**Quantum-Inspired Intelligent Traffic Route Optimization in Transportation Systems Using Metaheuristic Optimization**

---

# 📌 Project Status

**Current stage:** Concept Prototype

The core demonstration loop is:

```text
✅ Generate Scenario
      ↓
✅ Optimize Fleet
      ↓
✅ Simulate Traffic Incident
      ↓
✅ Re-Optimize
      ↓
✅ Benchmark Algorithms
      ↓
✅ Executive Overview
      ↕
✅ Engineering Control Room
```

Further implementation details and outstanding work are tracked in [`Task.md`](Task.md).

---

## ⭐ The Core Demonstration

At its heart, Q-DFRO demonstrates one simple idea:

> **When the road conditions change, the fleet should not simply continue following an outdated plan — it should be able to adapt.**

Q-DFRO provides a controlled environment to simulate that process, optimize the response, and compare different optimization strategies using the same evaluation framework.