"""Phase 7, Objective 3 - real-city end-to-end validation.

Drives the actual FastAPI app (the same code path the frontend uses) through
the full demo workflow against real external services: Nominatim (geocoding),
Overpass (OSM road network) and Open-Meteo (weather). No network call is
mocked here - a failure of any external service is recorded honestly rather
than papered over.

Usage (from backend/):
    python -m experiments.phase7_validation.run_real_city_validation

Writes experiments/phase7_validation/validation_results.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

import main as main_module

client = TestClient(main_module.app)

LOCATIONS = [
    {"place": "Hazratganj, Lucknow, India", "radius_m": 1200},
    {"place": "Sector 18, Noida, India", "radius_m": 1200},
    {"place": "Piccadilly Circus, London, United Kingdom", "radius_m": 1200},
]

SEED = 42
NUM_JOBS = 12
NUM_VEHICLES = 3


def _pick_active_edge(routes) -> Optional[Dict[str, int]]:
    for route in routes:
        path = route["node_path"]
        if len(path) >= 2:
            return {"source": path[0], "destination": path[1]}
    return None


def validate_location(spec: Dict[str, Any]) -> Dict[str, Any]:
    place = spec["place"]
    result: Dict[str, Any] = {"place": place, "radius_m": spec["radius_m"], "steps": {}}

    # 1-4: geocode + load OSM + build scenario + node/edge counts
    t0 = time.perf_counter()
    gen_resp = client.post("/api/problem/generate", json={
        "source": "osm",
        "place": place,
        "radius_m": spec["radius_m"],
        "num_jobs": NUM_JOBS,
        "num_vehicles": NUM_VEHICLES,
        "seed": SEED,
    })
    scenario_load_s = time.perf_counter() - t0
    result["steps"]["generate"] = {
        "status_code": gen_resp.status_code,
        "duration_s": round(scenario_load_s, 3),
    }
    if gen_resp.status_code != 200:
        result["steps"]["generate"]["error"] = gen_resp.text[:1000]
        result["failed_at"] = "generate"
        return result

    body = gen_resp.json()
    scenario_id = body["scenario_id"]
    result["scenario_id"] = scenario_id
    result["location"] = body.get("location")
    result["node_count"] = body["node_count"]
    result["edge_count"] = body["edge_count"]
    result["geometry_source"] = body.get("geometry_source")
    result["osm_provenance"] = body.get("provenance")
    result["osm_endpoint"] = body.get("osm_endpoint")
    result["osm_stats"] = body.get("osm")

    # 5. Weather
    t0 = time.perf_counter()
    weather_resp = client.get("/api/weather", params={"scenario_id": scenario_id})
    result["steps"]["weather"] = {
        "status_code": weather_resp.status_code,
        "duration_s": round(time.perf_counter() - t0, 3),
    }
    if weather_resp.status_code == 200:
        w = weather_resp.json()
        result["weather"] = {
            "source": w.get("source"),
            "condition": w.get("condition"),
            "temperature_c": w.get("temperature_c"),
            "fallback": w.get("source") != "network",
        }

    # 6. Apply traffic model (moderate + weather)
    cond_resp = client.post("/api/scenario/conditions", json={
        "scenario_id": scenario_id,
        "traffic_mode": "moderate",
        "traffic_source": "simulated",
        "weather_enabled": True,
    })
    result["steps"]["conditions"] = {"status_code": cond_resp.status_code}
    if cond_resp.status_code != 200:
        result["failed_at"] = "conditions"
        return result
    cond_body = cond_resp.json()
    result["traffic_source"] = cond_body.get("traffic_source")
    result["weather_source"] = cond_body.get("weather_source")
    result["fallback_used"] = cond_body.get("fallback_used")

    # 7-8. Run QPSO, record metrics
    optimize_config = {"algorithm": "qpso", "population_size": 30, "max_iterations": 60, "seed": SEED}
    t0 = time.perf_counter()
    opt_resp = client.post("/api/optimize", json={"scenario_id": scenario_id, "config": optimize_config})
    qpso_runtime_s = time.perf_counter() - t0
    result["steps"]["optimize"] = {"status_code": opt_resp.status_code, "duration_s": round(qpso_runtime_s, 3)}
    if opt_resp.status_code != 200:
        result["failed_at"] = "optimize"
        return result
    before = opt_resp.json()
    result["before"] = {
        "total_cost": before["total_cost"],
        "total_travel_time": before["total_travel_time"],
        "total_distance": before["total_distance"],
    }

    # Route geometry check
    geom_resp = client.post("/api/routes/geometry", json={"scenario_id": scenario_id, "routes": before["routes"]})
    result["steps"]["route_geometry"] = {"status_code": geom_resp.status_code}
    if geom_resp.status_code == 200:
        geom_body = geom_resp.json()
        result["route_geometry_source"] = geom_body.get("geometry_source")

    # 9. Apply an incident on an edge of an active route
    target = _pick_active_edge(before["routes"])
    result["incident_target_edge"] = target
    if target is not None:
        traffic_resp = client.post("/api/traffic/update", json={
            "scenario_id": scenario_id,
            "updates": [{"source": target["source"], "destination": target["destination"], "traffic_factor": 5.0}],
        })
        result["steps"]["incident"] = {"status_code": traffic_resp.status_code}

        # 10. Re-optimize
        t0 = time.perf_counter()
        reopt_resp = client.post("/api/optimize", json={"scenario_id": scenario_id, "config": optimize_config})
        reopt_runtime_s = time.perf_counter() - t0
        result["steps"]["reoptimize"] = {"status_code": reopt_resp.status_code, "duration_s": round(reopt_runtime_s, 3)}
        if reopt_resp.status_code == 200:
            after = reopt_resp.json()
            result["after"] = {
                "total_cost": after["total_cost"],
                "total_travel_time": after["total_travel_time"],
                "total_distance": after["total_distance"],
            }
            before_jobs = {r["vehicle_id"]: r["job_ids"] for r in before["routes"]}
            after_jobs = {r["vehicle_id"]: r["job_ids"] for r in after["routes"]}
            changed = [vid for vid, jobs in after_jobs.items() if before_jobs.get(vid) != jobs]
            result["changed_vehicle_ids_after_incident"] = changed
            result["route_changed"] = before["total_cost"] != after["total_cost"] or len(changed) > 0

    # 11. Benchmark: Greedy / PSO / GA / QPSO on identical scenario+config
    t0 = time.perf_counter()
    bench_resp = client.post("/api/benchmark", json={"scenario_id": scenario_id, "config": optimize_config})
    result["steps"]["benchmark"] = {"status_code": bench_resp.status_code, "duration_s": round(time.perf_counter() - t0, 3)}
    if bench_resp.status_code == 200:
        bench_body = bench_resp.json()
        result["benchmark"] = {
            key: {
                "algorithm": r["algorithm"],
                "total_cost": r["total_cost"],
                "runtime_ms": r["runtime_ms"],
                "is_feasible": r["is_feasible"],
                "constraint_violations": r["constraint_violations"],
            }
            for key, r in bench_body["results"].items()
        }

    # 12. Reproducibility: same scenario_id + same seed + same config, run twice more
    repro_costs = []
    for _ in range(2):
        r = client.post("/api/optimize", json={"scenario_id": scenario_id, "config": optimize_config})
        if r.status_code == 200:
            repro_costs.append(r.json()["total_cost"])
    result["reproducibility"] = {
        "costs": repro_costs,
        "all_equal_to_original": all(c == result["after"]["total_cost"] if "after" in result else c == before["total_cost"] for c in repro_costs) if repro_costs else None,
    }

    result["failed_at"] = None
    return result


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for spec in LOCATIONS:
        print(f"Validating {spec['place']} ...")
        try:
            r = validate_location(spec)
        except Exception as e:  # noqa: BLE001 - record, never fabricate a pass
            r = {"place": spec["place"], "error": str(e), "failed_at": "exception"}
        results.append(r)
        print(f"  -> failed_at={r.get('failed_at')}")

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seed": SEED,
        "num_jobs": NUM_JOBS,
        "num_vehicles": NUM_VEHICLES,
        "locations": results,
    }
    (out_dir / "validation_results.json").write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_dir / 'validation_results.json'}")


if __name__ == "__main__":
    main()
