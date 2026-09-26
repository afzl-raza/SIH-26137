# Q-DFRO — Technical Documentation & Project Summary

> **Note (2026-09-18):** This file is kept as a dated change log of past
> implementation decisions (e.g. the CARTO→OpenStreetMap tile switch below). The
> canonical, currently-accurate architecture reference is now
> [`Engineering.md`](Engineering.md); the task tracker is [`Task.md`](Task.md).
> A couple of factual corrections were made below where this file had drifted
> from the actual code — each is marked inline.

## Executive Summary

**Q-DFRO (Quantum-Inspired Dynamic Fleet Route Optimizer)** is a concept prototype developed for Smart India Hackathon (SIH 2024 / Problem Statement SIH26137). 

The application demonstrates real-time dynamic vehicle route optimization under shifting traffic conditions, comparing a **Quantum-Inspired Particle Swarm Optimization (QPSO)** metaheuristic against classical baselines (Greedy Nearest-Neighbor, Standard PSO, and Genetic Algorithms).

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────┐
│              React + Vite Frontend (UI Layer)           │
│  - Interactive Leaflet Network Map                      │
│  - Traffic Incident Trigger Control                     │
│  - Real-Time Route Overlay & Pre/Post Comparison        │
│  - Benchmark & Convergence Analytics Charts             │
└────────────────────────────┬────────────────────────────┘
                             │ HTTP / JSON API
┌────────────────────────────▼────────────────────────────┐
│               FastAPI Python (Backend Engine)           │
│  - Synthetic Urban Network & Traffic Model Generator    │
│  - Multi-Constraint Fitness & Penalty Function Evaluator │
│  - QPSO / PSO / GA / Greedy Metaheuristic Solvers       │
│  - Automated Comparative Benchmark Runner               │
└─────────────────────────────────────────────────────────┘
```

---

## Work Completed & System Components

### 1. Backend Core Services (`/backend`)

* **[main.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/main.py)**: FastAPI REST API exposing standard endpoints for problem scenario generation, algorithm execution, dynamic traffic updates, and benchmark comparisons.
* **[problem_generator.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/problem_generator.py)**: Synthesizes reproducible urban road graphs using NetworkX & NumPy with spatial node placement (Bengaluru coordinates), depot assignment, vehicle capacity attributes, and delivery demand constraints.
* **[fitness.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/fitness.py)**: Evaluates solution feasibility, calculating total travel time, distance, capacity violation penalties, duration constraints, and traffic congestion delays.
* **[decoder.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/decoder.py)**: Converts continuous particle velocity/position vectors into valid vehicle node routes.

### 2. Metaheuristic Solvers (`/backend/optimizers`)

* **[qpso.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/optimizers/qpso.py)**: Implements Quantum-Inspired Particle Swarm Optimization utilizing delta-potential well wavefunctions for global search space exploration and fast convergence.
* **[pso.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/optimizers/pso.py)**: Standard Particle Swarm Optimization baseline with inertia weight and cognitive/social acceleration constants.
* **[ga.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/optimizers/ga.py)**: Genetic Algorithm baseline utilizing order crossover (OX) and swap mutation operators.
* **[greedy.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/optimizers/greedy.py)**: Nearest-Neighbor heuristic baseline for rapid initial feasibility assessment.
* **[benchmark.py](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/backend/optimizers/benchmark.py)**: Runs all algorithms side-by-side on identical problem instances to calculate execution time, total distance, travel time, and convergence rate.

### 3. Interactive Frontend (`/frontend`)

* **Network Map ([NetworkMap.jsx](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/frontend/src/components/NetworkMap.jsx))**: Leaflet interactive map displaying road networks, depot nodes, delivery targets, active vehicle routes, and incident pulse animations.
* **Incident Control Panel ([ControlPanel.jsx](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/frontend/src/components/ControlPanel.jsx))**: Allows users to configure problem parameters, trigger real-time road congestion disruptions, and initiate re-optimization.
* **Metrics Dashboard ([MetricCards.jsx](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/frontend/src/components/MetricCards.jsx))**: Displays active optimization metrics, route distance, travel duration, and before/after deltas after re-optimization.
* **Benchmark Panel ([BenchmarkPanel.jsx](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/frontend/src/components/BenchmarkPanel.jsx))**: Visual comparative table comparing QPSO, PSO, GA, and Greedy performance.

*(Corrected 2026-09-18: this section originally named `MetricsPanel.jsx`/`BenchmarkModal.jsx`, which never matched the actual file names in `frontend/src/components/`.)*

---

## API Reference Table

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health status check |
| `POST` | `/api/problem/generate` | Generates synthetic urban road scenario |
| `POST` | `/api/optimize` | Solves routing using selected algorithm |
| `POST` | `/api/traffic/update` | Applies dynamic traffic multiplier to road edges |
| `POST` | `/api/benchmark` | Runs comparative benchmark across all algorithms |

---

## Project Setup & Execution Guide

### 1. Prerequisites
* Python 3.10+
* Node.js v18+

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install dependencies from root or backend requirements file
pip install -r ../requirements.txt

# Start FastAPI server
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install packages
npm install

# Run Vite dev server
npm run dev
```

---

## Summary of Deliverables & Requirements File

1. **Root Requirements File**: Created `requirements.txt` containing all Python backend dependencies (`fastapi`, `uvicorn`, `pydantic`, `numpy`, `scipy`, `networkx`, `pytest`). Note: `backend/requirements.txt` is an identical copy — harmless duplication, but keep both in sync if dependencies change.
2. **Tasks Documentation**: `Task.md` at the time marked all Phase 0–8 items and the final demo checklist as complete. That version has since been superseded — see the current [`Task.md`](Task.md), which tracks status against the larger Grand-Finale roadmap in [`Engineering.md`](Engineering.md) and verifies each item against the actual code/tests rather than assuming completion.
3. **Technical Documentation**: Fully updated `Documnetation.md` with complete project architecture, file references, API specification, and setup instructions. Superseded as the primary architecture reference by [`Engineering.md`](Engineering.md); this file remains as a dated change log of decisions made along the way.

---

## Executive Overview / Engineering Control Room Split (2026-09-26)

The frontend previously had a single dense workspace. That workspace is now
called the **Engineering Control Room** (functionally unchanged) and sits
behind a header nav alongside a new **Executive Overview** — a narrative
summary page (`ExecutiveOverview.jsx`) built only from state `App.jsx`
already computes: no new API calls, no fabricated baselines or percentages.
Full detail is in [`Task.md`](Task.md)'s "Executive Overview / Engineering
Control Room Split + UI Design System" entry.

Alongside it, a shared UI primitive layer was added under
`frontend/src/components/ui/` (`Button`, `IconButton`, `SegmentedControl`,
`Badge`, `ControlSection`, `ComparisonBars`, `VehicleLoader`, `Toast`),
replacing per-component hand-rolled Tailwind button/toggle strings. The
brand mark (`Logo.jsx`, `favicon.svg`) changed from an accent-colored
route/quantum-node glyph to a minimal flat white car + destination-pin
glyph, reused unchanged in the header, the Executive Overview empty state,
and the loading indicator (`VehicleLoader`).

This work was done on branch `frontend/ui-polish-executive-overview`, not
directly on `main`. `npm run build` succeeds; a live in-browser
click-through was **not** performed this round (skipped per instruction) —
verification was build success plus manual review of prop wiring, so treat
this as code-reviewed rather than demo-verified until someone clicks
through it.

**Revision (same day):** the Executive Overview was reworked after review —
it led with scenario stats and duplicated the operational map as a second
smaller instance, which read as redundant rather than insightful. It's now
an 8-section results narrative (`frontend/src/components/executive/`)
leading with the outcome/impact, with a purpose-built tilted SVG
before/after route visualization (real node/route data, not a second
Leaflet map) instead of the duplicate map, one real interactive map for
route inspection instead of two, and a single global `OperationOverlay`
(non-technical copy, indeterminate progress) replacing the scattered
per-panel loading blocks. This pass **was** verified live via a headless
Playwright run, which caught and led to fixing a real CSS bug in
`VehicleLoader` (percentage-width labels collapsing inside a shrink-to-fit
flex parent). See `Task.md`'s "Executive Overview Revision" entry for
detail.

## Map Tile Layer & Dark Mode

### Problem
The prototype originally used CARTO's dark basemap tiles (`basemaps.cartocdn.com`). CARTO enforces an API key policy — requests without a key receive tile images with a baked-in **"API KEY REQUIRED"** watermark across the entire map.

### Solution
The tile provider was replaced with **OpenStreetMap** standard tiles (`tile.openstreetmap.org`), which are:
- **100% free** — no API key required, no usage limits for prototypes
- **No watermarks** — clean, production-quality map imagery
- **Reliable** — the most widely-used open tile server

To maintain the dark UI aesthetic, a **CSS filter chain** was applied to the tile pane in `index.css`:

```css
.leaflet-tile-pane {
  filter: invert(1) hue-rotate(200deg) saturate(0.4) brightness(0.75) contrast(1.1);
}
```

This inverted, shifted, and dimmed the standard light-theme OSM tiles to produce a dark-mode map, with a counter-filter on popups/controls so they stayed legible.

> **Status as of 2026-09-18:** this filter is **not present** in the current
> `frontend/src/index.css` — the map currently renders with standard light OSM
> tiles. This was confirmed by inspecting the live app rather than assumed. Kept
> here as a decision record; re-apply the snippet above if the dark map treatment
> is wanted again.

### Files Changed
| File | Change |
| :--- | :--- |
| [NetworkMap.jsx](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/frontend/src/components/NetworkMap.jsx) | Tile URL changed from CARTO → OpenStreetMap |
| [index.css](file:///c:/Users/LENOVO/OneDrive/Desktop/SIH/DEMO/frontend/src/index.css) | Added `.leaflet-tile-pane` dark filter and counter-filter for controls |
