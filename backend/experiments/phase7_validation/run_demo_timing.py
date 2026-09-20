"""Phase 7, Objectives 7/8/10 - cached OSM demo scenario + presentation timing.

Exercises the exact demo workflow (load network -> optimize -> incident ->
re-optimize -> benchmark) against a location whose geocoding/OSM/weather
responses are already present in the on-disk cache (backend/../.cache/),
so this "Cached OSM Demo Scenario" runs without depending on live Overpass
or Nominatim availability during a presentation. This reuses the existing
cache architecture (realdata/cache.py) - no second cache is introduced, and
the network is still real OSM data, only served from disk instead of
re-fetched. Weather is fetched live if the (short) weather cache TTL has
expired; if the provider is unreachable, the app's own fallback path
(realdata/weather.py) reports that honestly via `weather_source`.

This does NOT hardcode a route or a benchmark result: /api/optimize and
/api/benchmark are still called for real on every run.

Usage (from backend/, after run_real_city_validation.py has populated the
cache for this place at least once):
    python -m experiments.phase7_validation.run_demo_timing

Writes experiments/phase7_validation/demo_run.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

import main as main_module

client = TestClient(main_module.app)

# Must match a location already run through run_real_city_validation.py so
# its geocoding + OSM extract are on disk. Smallest/fastest of the three
# validated locations, chosen for a snappy live demo.
DEMO_PLACE = "Hazratganj, Lucknow, India"
DEMO_RADIUS_M = 1200
SEED = 42
CONFIG = {"algorithm": "qpso", "population_size": 30, "max_iterations": 60, "seed": SEED}


def main() -> None:
    timings: dict = {}

    t0 = time.perf_counter()
    gen = client.post("/api/problem/generate", json={
        "source": "osm", "place": DEMO_PLACE, "radius_m": DEMO_RADIUS_M,
        "num_jobs": 12, "num_vehicles": 3, "seed": SEED,
    })
    timings["scenario_load_s"] = round(time.perf_counter() - t0, 3)
    assert gen.status_code == 200, gen.text
    body = gen.json()
    scenario_id = body["scenario_id"]
    cache_provenance = {"location": body.get("location", {}).get("provenance"), "osm": body.get("provenance")}

    t0 = time.perf_counter()
    weather = client.get("/api/weather", params={"scenario_id": scenario_id})
    timings["weather_fetch_s"] = round(time.perf_counter() - t0, 3)
    weather_body = weather.json() if weather.status_code == 200 else {}

    cond = client.post("/api/scenario/conditions", json={
        "scenario_id": scenario_id, "traffic_mode": "moderate",
        "traffic_source": "simulated", "weather_enabled": True,
    })
    assert cond.status_code == 200, cond.text

    t0 = time.perf_counter()
    opt = client.post("/api/optimize", json={"scenario_id": scenario_id, "config": CONFIG})
    timings["initial_optimization_s"] = round(time.perf_counter() - t0, 3)
    assert opt.status_code == 200, opt.text
    before = opt.json()

    target = None
    for route in before["routes"]:
        if len(route["node_path"]) >= 2:
            target = {"source": route["node_path"][0], "destination": route["node_path"][1]}
            break

    t0 = time.perf_counter()
    if target:
        inc = client.post("/api/traffic/update", json={
            "scenario_id": scenario_id,
            "updates": [{"source": target["source"], "destination": target["destination"], "traffic_factor": 5.0}],
        })
        assert inc.status_code == 200, inc.text
    timings["incident_update_s"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    reopt = client.post("/api/optimize", json={"scenario_id": scenario_id, "config": CONFIG})
    timings["reoptimization_s"] = round(time.perf_counter() - t0, 3)
    assert reopt.status_code == 200, reopt.text
    after = reopt.json()

    t0 = time.perf_counter()
    bench = client.post("/api/benchmark", json={"scenario_id": scenario_id, "config": CONFIG})
    timings["benchmark_s"] = round(time.perf_counter() - t0, 3)
    assert bench.status_code == 200, bench.text
    bench_body = bench.json()

    timings["total_demo_workflow_s"] = round(sum(timings.values()), 3)

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": "Cached OSM Demo Scenario",
        "place": DEMO_PLACE,
        "radius_m": DEMO_RADIUS_M,
        "seed": SEED,
        "config": CONFIG,
        "cache_provenance": cache_provenance,
        "node_count": body["node_count"],
        "edge_count": body["edge_count"],
        "weather": {
            "source": weather_body.get("source"),
            "condition": weather_body.get("condition"),
            "note": "source == 'network' or 'cache' means a real Open-Meteo observation; "
                    "'fallback' means the provider failed and no invented value was used.",
        },
        "external_dependencies": {
            "nominatim_geocoding": cache_provenance["location"],
            "overpass_osm": cache_provenance["osm"],
            "open_meteo_weather": weather_body.get("source"),
        },
        "before": {"total_cost": before["total_cost"], "total_travel_time": before["total_travel_time"],
                   "total_distance": before["total_distance"]},
        "after": {"total_cost": after["total_cost"], "total_travel_time": after["total_travel_time"],
                  "total_distance": after["total_distance"]},
        "route_changed": before["total_cost"] != after["total_cost"],
        "benchmark_summary": {k: {"algorithm": r["algorithm"], "total_cost": r["total_cost"], "runtime_ms": r["runtime_ms"]}
                               for k, r in bench_body["results"].items()},
        "timings_seconds": timings,
    }

    out_dir = Path(__file__).resolve().parent
    (out_dir / "demo_run.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps(timings, indent=2))
    print(f"Wrote {out_dir / 'demo_run.json'}")


if __name__ == "__main__":
    main()
