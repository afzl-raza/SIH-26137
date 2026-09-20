# Route and Traffic Visualization

How what is drawn on the map relates to what the backend computed.

The short version: the frontend draws, the backend decides. Every coordinate on
the map came from OpenStreetMap or from a scenario node; every colour came from
a state the backend assigned while it was writing the edge cost. React
calculates no route, classifies no congestion and derives no travel time.

---

## 1. Road geometry

### Where it comes from

`realdata/osm_loader.py` splits each OSM way at shared junctions only. The
nodes in between are not routing nodes — keeping them would inflate the graph —
but they are retained on the edge as `Edge.geometry`, an ordered
`[[lat, lon], ...]` polyline running source → destination.

That means a scenario already carries the true shape of every road it contains.
Drawing it is a lookup, not a computation.

| Network | `Edge.geometry` | Rendered as |
|---|---|---|
| OpenStreetMap | the way's own polyline | the actual road curve |
| Synthetic | `null` | a straight line between the two nodes |

A synthetic network's roads genuinely *are* straight lines between generated
points, so the fallback is not a degradation — it is an accurate picture of
that network. `geometry_source` on the generate response says which one you
are looking at (`openstreetmap` or `straight-line`), and the map legend states
it.

### Route geometry

`VehicleRoute.node_path` is already the complete node-by-node road path — the
Dijkstra path out of `RouteMatrix.paths`, stitched in `decoder.py`, not just
the ordered job list. What was missing was each hop's shape.

`backend/route_geometry.py` resolves it:

```
node_path  ->  for each consecutive (u, v):
                   look up the edge the router used
                   take its OSM geometry (or the straight line if it has none)
               stitch, dropping the duplicated shared junction
           ->  polyline
```

Served by `POST /api/routes/geometry`.

Two details are load-bearing:

* **The same edge the router used.** When a node pair has parallel edges,
  `build_routing_graph` hands the weight to the *last* one added, because that
  is how `networkx.DiGraph.add_edge` behaves. `_edge_index` resolves ties the
  same way on purpose. Picking a different parallel edge would draw a road the
  optimizer never costed.
* **Direction.** Geometry runs source → destination, so hops stitch without any
  orientation check. `test_edge_geometry_endpoints_match_its_nodes` holds this.

**Why the backend and not React.** Three reasons: the frontend must never
compute a route, and stitching geometry in the client is one refactor away from
becoming exactly that; the parallel-edge rule has to match the router exactly
and there should be one place to keep that correct; and this way it is covered
by pytest, which the React code is not.

**Measured** (Hazratganj, Lucknow, 800 m radius — 354 nodes, 805 edges, 420 of
them with intermediate shape points): a 55-node vehicle path resolves to a
133-point polyline, and a 49-node path to 94 points. The drawn route follows
the road rather than cutting between junctions.

---

## 2. Traffic visualization

### The bands

An edge's `congestion_level` is assigned by `conditions.recompute_edge_cost` —
the same function, in the same call, that writes `traffic_factor` and
`current_travel_time`. They therefore cannot disagree, which
`test_congestion_level_always_agrees_with_the_multiplier_it_describes` checks.

The thresholds are **not free parameters**. They are the documented level
multipliers themselves:

| Band | Threshold on `traffic_factor` | Where the number comes from |
|---|---|---|
| `severe` | ≥ 4.0 | `LEVEL_MULTIPLIERS["severe"]` |
| `heavy` | ≥ 2.5 | `LEVEL_MULTIPLIERS["heavy"]` |
| `moderate` | ≥ 1.5 | `LEVEL_MULTIPLIERS["moderate"]` |
| `light` | ≥ 1.05 | "measurably above free flow" |
| `free_flow` | otherwise | — |

A road is reported at level X exactly when its effective multiplier has reached
the multiplier that level denotes. Published at
`GET /api/conditions/model` → `simulated.congestion_bands`.

### Why they are pinned to the level table

The traffic model modulates the network-wide level per road by class
susceptibility, so at `heavy` a residential street sits near 2.125× while a
motorway sits near 2.725×. Bands chosen independently of the level table
straddled that whole range and painted the entire network one colour — the
spread was real, and genuinely re-routes vehicles, but was invisible. Pinning
the boundaries to the table puts those roads on opposite sides of 2.5.

**Measured** (Hazratganj extract at `heavy`): 101 edges `heavy`, 704
`moderate`. Previously: 805 edges, all one band.

Note that under the BPR formulation the same modes produce much gentler
multipliers (~1.26 at `heavy`), so most roads report `light` or `free_flow`.
That is correct, not a bug: BPR is an alternative calibration and the display
reflects what it actually produces.

### Incidents are a separate axis

`Edge.has_incident` is true when `incident_multiplier != 1.0` — an operator
disrupted *this specific road*, as opposed to the road merely being congested
by the network-wide level. The map needs to tell those apart and cannot infer
it from `traffic_factor` alone, so the backend states it.

### Labelling

Congestion is **simulated**. The map legend heads the band swatches with
"Simulated Traffic (model)", the edge popup says "Sim. traffic state", and
`traffic_source` is `simulated` throughout.
`test_nothing_in_the_visualization_payload_claims_live_traffic` asserts the
strings "live traffic" and "real-time traffic" appear nowhere in the payload.

---

## 3. Weather in the UI

Weather is the one genuinely observed condition input, so the panel shows what
the provider returned and nothing more: condition and description, temperature,
precipitation, wind, the applied multiplier, `source`
(`network` / `cache` / `cache-stale` / `fallback`), provider, `observed_at` and
`retrieved_at`.

A field the provider did not return is simply absent. On a fallback, every
measured field is null, the multiplier is exactly 1.0, and the panel says the
provider was unavailable — a fallback is never dressed up as fair weather.

---

## 4. Reproducibility manifest

`GET /api/scenario/{scenario_id}/manifest` reports what the server holds for a
run, so it can be read back rather than taken on trust:

| Field | Source |
|---|---|
| `location` | the `ResolvedLocation` the network was built from; `null` for synthetic |
| `seed`, `scenario_hash` | the scenario itself |
| `solver.*` | echoed from the caller — the backend does not retain solver settings |
| `conditions.traffic_*` | the applied `ConditionSummary` |
| `conditions.weather_*` | ditto, including `weather_observed_at` |
| `conditions.signature` | deterministic fingerprint of the condition state |
| `geometry_source` | whether the roads are real OSM shapes |

Fields the backend genuinely does not know are `null`, never filled in. A
synthetic network reports no location; solver settings the caller did not pass
come back as `null` rather than as defaults.

The signature fingerprints **provenance**, not just values: the same weather
served from cache is a different condition state from one just fetched, and the
manifest says so
(`test_the_signature_distinguishes_a_fetched_reading_from_a_cached_one`).

---

## 5. API additions

| Endpoint | Purpose |
|---|---|
| `POST /api/routes/geometry` | Road shape of an already-computed set of routes. Does not route. |
| `GET /api/scenario/{id}/manifest` | Reproducibility metadata for a stored scenario. |

Additive fields on existing responses: `geometry_source` on
`POST /api/problem/generate`; `congestion_level` and `has_incident` on every
`Edge`; `congestion_levels` / `congestion_bands` under `simulated` on
`GET /api/conditions/model`.

No existing field changed shape or meaning.

---

## 6. Testing

| File | Covers |
|---|---|
| `backend/tests/test_route_geometry.py` | OSM geometry, route polyline stitching, parallel-edge resolution, synthetic fallback |
| `backend/tests/test_phase6_api.py` | geometry over the API, traffic visualization data, incident → re-optimization, weather metadata, reproducibility manifest |
