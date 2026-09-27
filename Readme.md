# 🚦 Q-DFRO

### Quantum-Inspired Dynamic Fleet Route Optimizer

**SIH26137 · Egreen Quanta · Byte Brain 2.0**

> **Plan → Disrupt → Adapt → Compare**

---

## 🚀 Live Demo

### [Open Q-DFRO](https://sih-26137-six.vercel.app/)

---

# 🌍 What does Q-DFRO do?

### A visual simulation of how a fleet adapts when traffic conditions change.

```text
        🗺️ PLAN
           │
           ▼
     🚚 Fleet Routes
           │
           ▼
       🚧 DISRUPT
     Traffic Incident
           │
           ▼
        🔄 ADAPT
     Re-route Fleet
           │
           ▼
       📊 COMPARE
   Evaluate Algorithms
```

---

# ⚡ The Entire Project at a Glance

```text
┌──────────────┐     ┌──────────────┐
│ 🗺️ ROAD      │     │ 🚚 FLEET     │
│    NETWORK   │     │    + JOBS    │
└──────┬───────┘     └──────┬───────┘
       └──────────┬──────────┘
                  ▼
          ┌───────────────┐
          │ 🧠 OPTIMIZE   │
          │    ROUTES     │
          └───────┬───────┘
                  ▼
          ┌───────────────┐
          │ 🚧 INCIDENT  │
          │    OCCURS     │
          └───────┬───────┘
                  ▼
          ┌───────────────┐
          │ 🔄 RE-ROUTE   │
          │     FLEET     │
          └───────┬───────┘
                  ▼
          ┌───────────────┐
          │ 📊 BENCHMARK  │
          │  GREEDY PSO   │
          │   GA   QPSO   │
          └───────────────┘
```

---

# 🎯 Why?

```text
STATIC ROUTING
      │
      ▼
Route is created
      │
      ▼
🚧 Conditions change
      │
      ▼
❌ Original route may no longer be efficient
```

### Q-DFRO

```text
ROUTE
  ↓
🚧 CHANGE
  ↓
🔍 DETECT
  ↓
🔄 ADAPT
  ↓
✅ UPDATED ROUTE
```

---

# 🖥️ Two Views · One System

```text
                 Q-DFRO
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
 👔 EXECUTIVE            🧑‍💻 ENGINEERING
   OVERVIEW               CONTROL ROOM
        │                     │
        ▼                     ▼
   WHAT HAPPENED?        HOW IT WORKS?
        │                     │
        ▼                     ▼
 📊 Metrics              ⚙️ Controls
 🗺️ Routes              🗺️ Network
 🚧 Impact               🧠 Solvers
 📈 Results              📊 Benchmark
 💡 Insights             🔍 Inspection
```

---

# 📊 Executive Overview

### Everything important — visually condensed.

```text
┌─────────────────────────────────────────────────────┐
│                 FLEET OVERVIEW                      │
├──────────┬──────────┬──────────┬───────────────────┤
│ 🚚 FLEET │ 📦 JOBS  │ 🚧 ALERT │ 🔄 STATUS        │
│    —     │    —     │    —     │     —             │
├──────────┴──────────┴──────────┴───────────────────┤
│                                                     │
│                  🗺️ ROUTE MAP                       │
│                                                     │
│       🚚 ───────────────→ 🚚                       │
│             ╲                                         │
│              ╲ 🚧 INCIDENT                          │
│               ╲                                       │
│                ─────────→ 🔄 NEW ROUTE              │
│                                                     │
├───────────────────────┬─────────────────────────────┤
│   BEFORE → AFTER      │      ALGORITHM BENCHMARK   │
│                       │                             │
│ Distance    ↕         │ Greedy  ████               │
│ Time        ↕         │ PSO     █████              │
│ Cost        ↕         │ GA      █████              │
│ Deliveries  ✓         │ QPSO    ██████             │
├───────────────────────┴─────────────────────────────┤
│ 💡 INSIGHT                                          │
│ Traffic disruption detected → fleet re-routed      │
└─────────────────────────────────────────────────────┘
```

---

# 📈 What We Measure

| 🚚 Fleet | 📦 Delivery | 🛣️ Route | 🚧 Impact |
|---|---|---|---|
| Utilization | Completion | Distance | Before/After |
| Vehicle status | Job coverage | Travel time | Affected routes |
| Route assignment | Feasibility | Route cost | Re-optimization |

---

# 🧠 Optimization Engine

### Same scenario. Same evaluation.

```text
                    SAME SCENARIO
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
     🟦 GREEDY         🟨 PSO           🟩 GA
        │                │                │
        └────────────────┼────────────────┘
                         ▼
                       🟪 QPSO
                         │
                         ▼
                  SHARED EVALUATOR
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
           Distance     Time       Cost
              │          │          │
              └──────────┼──────────┘
                         ▼
                  📊 RESULTS
```

---

# 🚧 Dynamic Routing

```text
🗺️ INITIAL
    │
    ▼
🚚 ROUTES
    │
    ▼
🚧 TRAFFIC INCIDENT
    │
    ▼
⚠️ AFFECTED VEHICLE
    │
    ▼
🧠 RE-OPTIMIZATION
    │
    ▼
🔄 NEW ROUTE
    │
    ▼
✅ UPDATED FLEET
```

---

# 🏗️ System Architecture

```text
┌──────────────────────────────┐
│          FRONTEND            │
│                              │
│ Executive ↔ Engineering      │
└──────────────┬───────────────┘
               │
             REST
               │
               ▼
┌──────────────────────────────┐
│           FASTAPI            │
│                              │
│ Scenario │ Fleet │ Jobs      │
│ Optimize │ Incident │ Bench  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│      OPTIMIZATION ENGINE     │
│                              │
│   Greedy │ PSO │ GA │ QPSO  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       SHARED EVALUATOR       │
│                              │
│ Distance │ Time │ Cost       │
│ Feasibility │ Fleet Metrics │
└──────────────────────────────┘
```

---

# 🧪 Demo Flow

### One scenario. Six simple steps.

```text
① GENERATE
   🗺️ Network + 🚚 Fleet + 📦 Jobs

          ↓

② OPTIMIZE
   🧠 Generate initial routes

          ↓

③ DISRUPT
   🚧 Introduce traffic incident

          ↓

④ ADAPT
   🔄 Re-optimize affected routes

          ↓

⑤ COMPARE
   📊 Greedy vs PSO vs GA vs QPSO

          ↓

⑥ EXPLAIN
   👔 View Executive Overview
```

---

# 🛠️ Technology

```text
FRONTEND              BACKEND
React                  Python
Vite                   FastAPI
JavaScript             Uvicorn
Interactive Maps       Pytest

             +

       OPTIMIZATION
       ─────────────
       Greedy
       PSO
       GA
       QPSO
```

---

# 🌱 Current Scope

```text
                 Q-DFRO
                    │
     ┌──────────────┼──────────────┐
     ▼              ▼              ▼
  🗺️ Network      🚚 Fleet       📦 Jobs
     │              │              │
     └──────────────┼──────────────┘
                    ▼
              🚧 Disruption
                    │
                    ▼
             🔄 Re-routing
                    │
                    ▼
              📊 Benchmark
```

---

# 🚀 Future Direction

```text
CURRENT
Simulation Prototype
       │
       ▼
      + 🛰️ Live Traffic
       │
      + 📍 GPS Telemetry
       │
      + 🗺️ Real Roads
       │
      + ⏰ Delivery Windows
       │
      + 🚚 Vehicle Constraints
       │
      + 🚧 Real-time Incidents
       │
       ▼
FUTURE INTELLIGENT FLEET SYSTEM
```

---

# 🚫 Current Limitations

Q-DFRO is a **concept prototype**.

It is currently not:

❌ A production traffic-management system  
❌ A navigation replacement  
❌ A live traffic prediction service  
❌ A city-scale deployment  
❌ A guaranteed globally optimal routing system  

---

# ⭐ The Idea in One Picture

```text
                  🚚 FLEET
                     │
                     ▼
                🧠 PLAN ROUTES
                     │
                     ▼
                🛣️ CITY NETWORK
                     │
                     ▼
                🚧 SOMETHING
                 CHANGES
                     │
                     ▼
                🔍 DETECT IMPACT
                     │
                     ▼
                🔄 RE-OPTIMIZE
                     │
                     ▼
                🚚 NEW ROUTES
                     │
                     ▼
                📊 COMPARE
                     │
                     ▼
              💡 UNDERSTAND
                 THE IMPACT
```

> ## 🚦 Q-DFRO
> ### **Plan → Disrupt → Adapt → Compare**

**Live Demo:**  
https://sih-26137-six.vercel.app/

**SIH26137 · Egreen Quanta · Byte Brain 2.0**