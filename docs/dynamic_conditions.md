# Dynamic Conditions: Traffic, Weather and Incidents

How Q-DFRO turns a static road network into a dynamic one, and exactly which
parts of it are real data and which are a simulation.

Every claim in this document is backed by code in `backend/realdata/` and by
tests in `backend/tests/test_conditions.py`, `test_weather.py` and
`test_conditions_api.py`. Nothing here is aspirational.

---

## 1. Architecture

```
REAL OSM ROAD NETWORK        realdata/osm_loader.py, osm_scenario.py
        |
   BASE EDGE COST            Edge.base_travel_time   (never modified)
        |
  TRAFFIC CONDITIONS         realdata/traffic_model.py   -> traffic_multiplier
        |
  WEATHER CONDITIONS         realdata/weather.py         -> weather_multiplier
        |
 INCIDENT CONDITIONS         operator action             -> incident_multiplier
        |
  CURRENT EDGE COST          realdata/conditions.py      -> current_travel_time
        |
    ROUTE MATRIX             problem_generator.compute_route_matrix
        |                    cached by route_cache.py
  GA / PSO / QPSO / GREEDY   backend/optimizers/*        (unchanged)
        |
   ROUTES + METRICS          backend/fitness.py          (unchanged)
        |
      FRONTEND               frontend/src/
```

The optimizers were not modified. They consume edge costs through the route
matrix exactly as they did in Phases 1-4; what changed is that those costs are
now assembled from three condition axes instead of one.

### Module responsibilities

| Module | Owns |
|---|---|
| `backend/realdata/weather.py` | Fetching a **real** observation from Open-Meteo, with provenance and fallback. Contains no cost model. |
| `backend/realdata/traffic_model.py` | **Simulated** congestion; the `TrafficProvider` seam for a future real feed. Produces multipliers only. |
| `backend/realdata/conditions.py` | The **one** place multipliers are composed into an actual travel time. |
| `backend/route_cache.py` | Ensures a condition change can never serve a stale route matrix. |

---

## 2. The condition calculation

```
current_travel_time = base_travel_time
                    * traffic_multiplier
                    * weather_multiplier
                    * incident_multiplier

traffic_factor      = traffic_multiplier * weather_multiplier * incident_multiplier
```

Implemented once, in `conditions.recompute_edge_cost`. That function is the
only code in the backend that writes `traffic_factor` or
`current_travel_time`.

Properties, each covered by a test:

- **`base_travel_time` is never modified.** The free-flow baseline is always
  recoverable, so conditions can be raised, lowered or cleared without drift.
- **The axes are independent.** Clearing an incident does not disturb traffic
  or weather, and raising the traffic level does not clear an incident.
- **Composition is order-independent** and multiplicative.
- **Normal traffic with weather off is exactly free flow** — every multiplier
  is exactly `1.0`, so an unconditioned scenario is bit-identical to a
  scenario conditioned at `normal`.
- **It is deterministic.** No randomness anywhere. Same scenario + same
  conditions produce byte-identical edge costs.

### Why `traffic_factor` kept its name

`Edge.traffic_factor` existed before Phase 5 as the single congestion
multiplier. It now holds the *product* of the three axes, under the same name,
because the route-matrix cache key, the objective function's congestion term
and the map legend all read it. A pre-Phase-5 client that writes it directly
still behaves exactly as it did.

---

## 3. Traffic model — SIMULATED

> **This is a simulation.** OpenStreetMap supplies road geometry, topology and
> speed limits. It carries no traffic data, and no traffic feed is wired up.
> Every number in this section is a model parameter — a calibration assumption
> chosen so the prototype behaves plausibly. It is **not** a measurement, and
> must be labelled "Simulated Traffic" or "Traffic Model" in any UI or report.

### Congestion levels

| Mode | Multiplier | Meaning |
|---|---|---|
| `normal` | 1.0 | Free-flowing |
| `moderate` | 1.5 | Busy but moving |
| `heavy` | 2.5 | Congested peak-hour conditions |
| `severe` | 4.0 | Near-gridlock |

The Phase 5 brief lists a fourth level as `incident = 4.0`. Here an incident is
a *separate axis* (an operator disrupting one specific road), so the
network-wide fourth level is named `severe` and the 4.0 incident value lives on
the incident axis as `conditions.DEFAULT_INCIDENT_MULTIPLIER`. The numbers are
unchanged; only the axis is made explicit.

### Why congestion is not uniform

A single multiplier applied to every edge is a **no-op for routing**: scaling
all travel times by the same constant leaves every shortest path exactly where
it was. "Traffic got worse" would change the reported cost without ever
changing a route, which would make the dynamic demo misleading.

So the level is modulated per road by a documented susceptibility factor —
high-capacity through-roads absorb more of the peak, residential streets stay
closer to free flow:

```
edge_multiplier = 1 + (level_multiplier - 1) * susceptibility
```

Susceptibility comes from the OSM `highway` tag when present, and otherwise
from the edge's free-flow speed band (synthetic networks have no road class).
This is an assumption, stated as one — but it is the assumption that makes
congestion actually re-route vehicles.

**Measured effect** (`backend/tests/test_conditions_api.py`): on the default
30-node synthetic network, moving from `normal` to `heavy` changes **40 of 256**
terminal-to-terminal shortest paths. On the real OSM fixture (205 nodes, 480
edges) it changes **4 of 121**, with multipliers ordering
`primary 2.575 > secondary 2.5 > tertiary 2.35 > residential 2.125 > living_street 2.05`.

### Optional BPR formulation

`use_bpr=True` derives the level multiplier from the Bureau of Public Roads
volume-delay function instead of the flat table, reusing
`qdfro_graph.weights.bpr_travel_time` so there is exactly one BPR implementation
in the codebase:

```
t(v)/t0 = 1 + alpha * (v/c)^beta        alpha = 0.15, beta = 4.0
```

Each mode then declares an assumed saturation rather than a travel-time ratio.
It is **off by default**. The assumed saturations are just as much an
assumption as the ratios they replace, so this is an alternative formulation,
not a more accurate one.

### Traffic providers

| Provider | Status |
|---|---|
| `SimulatedTrafficProvider` | Fully functional. The default. |
| `ExternalTrafficProvider` | Deliberately raises. See below. |

`ExternalTrafficProvider` refuses to run rather than returning invented
numbers, and never silently falls back to the simulation — either would let the
UI report an external source it never contacted. A real implementation replaces
that class body and nothing else: the cost engine, the cache, the optimizers
and the API all consume `TrafficConditions` and are already indifferent to its
origin.

---

## 4. Weather model

### The observation — REAL

Weather comes from [Open-Meteo](https://open-meteo.com), which needs no API
key. The request is made for the scenario's own coordinate (its depot), so
weather follows whatever location the user asked for. No city is special-cased.

WMO 4677 present-weather codes are mapped to condition categories in
`weather.WMO_CODE_CONDITIONS`.

### Provenance labels

| `weather_source` | Meaning |
|---|---|
| `network` | Fetched from Open-Meteo just now |
| `cache` | A previous fetch, still within the 15-minute TTL |
| `cache-stale` | A previous fetch past TTL, served because the network failed. Still a real past observation, labelled as old. |
| `fallback` | **No observation available.** No weather effect applied. |

### Fallback behaviour

When Open-Meteo is unreachable and nothing is cached, the provider returns an
observation with `source: "fallback"`, `fallback_used: true`, and **every
measured field null**. It never invents a plausible-looking reading.

The multiplier is then exactly `1.0` — the absence of weather data is never
dressed up as fair weather — and the API reports the fallback so the UI can say
so. A weather outage cannot raise an exception and cannot stop an
optimization; this is covered by
`test_optimization_still_works_when_weather_is_unavailable`.

### The impact multipliers — SIMULATED

> These are **model assumptions**, not calibrated research findings. They are
> broadly in line with the direction and rough magnitude reported in
> road-weather literature (precipitation and reduced visibility lower free-flow
> speed and capacity), but they are not taken from a specific study and must
> not be presented as measured effects.

| Condition | Multiplier |
|---|---|
| `clear`, `cloudy` | 1.00 |
| `drizzle` | 1.05 |
| `rain` | 1.10 |
| `fog` | 1.15 |
| `heavy_rain` | 1.25 |
| `freezing`, `thunderstorm` | 1.30 |
| `snow` | 1.35 |
| `unknown` | 1.00 |

They are deliberately conservative — the largest is 1.35 — so weather never
dominates the objective.

Weather is **uniform across the extract**: it is one observation for the whole
area, so unlike traffic it scales every edge equally. It therefore changes
costs and travel times but rarely changes route *choice*. This is asserted by
`test_weather_is_applied_to_every_edge_uniformly`.

---

## 5. Incidents

An incident is an operator action on one specific road, set through
`POST /api/traffic/update`. The request field is still called `traffic_factor`
for backward compatibility; what it sets is the edge's `incident_multiplier`,
mirrored onto the reverse direction.

When no traffic level and no weather are applied — the default — the resulting
effective multiplier is exactly the number requested, so behaviour is identical
to before Phase 5. When they are applied, the three compose.

A multiplier of `1.0` clears the incident, leaving traffic and weather intact.

The incident path goes through `conditions.apply_incidents` like every other
condition, so there is no second edge-cost calculation anywhere in the backend.
`backend/experiments/runner.py` (E4, E5) was also moved onto it.

---

## 6. Cache invalidation

The route-matrix cache is content-addressed. Its key covers, per directed edge:

```
(source, destination, current_travel_time, distance, traffic_factor,
 traffic_multiplier, weather_multiplier, incident_multiplier)
```

plus the node set and the routing terminal set.

- **Same conditions → reuse.** Multipliers are stored rounded
  (`MULTIPLIER_PRECISION = 6`, `TRAVEL_TIME_PRECISION = 5`) precisely so two
  applications of the same conditions produce byte-identical values and still
  hit. Measured: applying identical conditions three times gives
  `{builds: 1, hits: 2}`.
- **Changed conditions → miss.** A traffic, weather or incident change alters
  edge travel times, which alters the key. Measured: three different traffic
  modes give `{builds: 3, hits: 0}`.
- **The individual multipliers are keyed too**, so the guarantee survives even
  the pathological case where a different combination composes to the same
  effective travel time (`test_the_cache_key_separates_conditions_that_multiply_to_the_same_total`).
- **A benchmark is still one build plus three hits**, now under conditions.

No explicit invalidation call exists or is needed — a changed scenario simply
produces a different key.

---

## 7. API

### Preserved unchanged

`POST /api/problem/generate`, `POST /api/optimize`, `POST /api/traffic/update`,
`POST /api/benchmark`, `POST /api/evaluate`.

`/api/traffic/update` keeps its request shape exactly; it now writes the
incident axis instead of the single factor.

### Added

| Endpoint | Purpose |
|---|---|
| `POST /api/scenario/conditions` | Apply a traffic level and/or weather to a stored scenario. Does not re-optimize. |
| `GET /api/weather` | Current weather at a coordinate or at a stored scenario's location. Read-only. |
| `GET /api/conditions/model` | The model's own parameters, so the UI and reports state assumptions rather than restating them by hand. |

### Condition metadata

Every scenario-carrying response now includes:

```json
{
  "traffic_source": "simulated",
  "traffic_mode": "heavy",
  "weather_source": "network",
  "weather_condition": "drizzle",
  "fallback_used": false,
  "conditions": { "...full ConditionSummary..." }
}
```

`conditions` also travels on the scenario itself (`ProblemScenario.conditions`),
so the frontend reads it off state it already holds.

`POST /api/scenario/conditions` deliberately does **not** re-optimize. The
client calls `/api/optimize` afterwards, exactly as it does after an incident,
so the "conditions changed → routes changed" causality stays visible as two
steps.

---

## 8. Real vs simulated — the honest summary

| Real | Source |
|---|---|
| Road network, geometry, topology | OpenStreetMap via Overpass |
| Road speed limits, lanes | OSM `maxspeed` / `lanes` tags, with labelled fallbacks |
| Place-name resolution | Nominatim |
| Weather observation | Open-Meteo, when `weather_source` is `network` / `cache` / `cache-stale` |

| Simulated | Where |
|---|---|
| Congestion level and its per-road distribution | `traffic_model.py` |
| Incident severity | operator input, `conditions.py` |
| Weather-impact multipliers | `conditions.WEATHER_IMPACT` |
| Delivery jobs, vehicles, demands | `osm_scenario.py`, `problem_generator.py` |

**Never label simulated congestion as "Live Traffic".** Use "Simulated
Traffic" or "Traffic Model". The UI string is `Sim. Traffic:` and the API
reports `traffic_source: "simulated"`; `test_simulated_traffic_is_never_labelled_live`
guards it.

---

## 9. Configuration

| Variable | Effect |
|---|---|
| `QDFRO_CACHE_DIR` | Cache root for geocoding, OSM and weather. Default `<repo>/.cache`. |
| `QDFRO_USER_AGENT` | User-Agent for Nominatim (its usage policy requires one). |
| `QDFRO_MAX_RADIUS_M` | Upper bound on OSM extract radius. Default 10000. |

Weather TTL (`weather.WEATHER_TTL_SECONDS`, 15 min) and the model parameter
tables are module constants, deliberately not environment-tunable — they are
part of the documented model, not deployment configuration.

---

## 10. Performance

Measured on the default 30-node synthetic scenario, single run, one developer
machine. These are observations, not claims of improvement.

| Operation | Time |
|---|---|
| Condition update, engine only | ~2.2 ms |
| Incident update (2 edges) | ~1.8 ms |
| Route-matrix rebuild (30 nodes, 16 terminals) | ~1.4 ms |
| QPSO optimization (pop 40 × 100 iters) | ~340 ms |
| Benchmark, all four solvers | ~1280 ms |
| Condition update **including** a live Open-Meteo fetch | ~950 ms (first call only; cached for 15 min thereafter) |

A condition change does **not** rebuild the OSM graph or regenerate the
scenario — it recomputes multipliers on the existing scenario and lets the
content-addressed cache rebuild only the route matrix.

The uncached weather fetch dominates the condition-update path. It is a single
network round trip, cached for 15 minutes, and it is skipped entirely when
weather is disabled.

---

## 11. Testing

| Area | File |
|---|---|
| Composition, axes, determinism, traffic/weather tables | `backend/tests/test_conditions.py` |
| Open-Meteo adapter, provenance, fallback | `backend/tests/test_weather.py` |
| API metadata, cache invalidation, optimizers, OSM | `backend/tests/test_conditions_api.py` |

Run from `backend/`:

```bash
python -m pytest -q
python -m pytest tests/test_conditions.py tests/test_weather.py tests/test_conditions_api.py -q
```

No test touches the network: the weather transport is injected, as the
Overpass and Nominatim transports already were.
