import json
import os
import sys

from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
from problem_generator import generate_synthetic_scenario


def _scenario():
    scenario = generate_synthetic_scenario(num_nodes=12, num_jobs=4, num_vehicles=2, seed=3)
    scenario.edges[0].road_name = "Café Road – हज़रतगंज"
    return scenario


def test_fast_serialization_matches_the_default_encoder_exactly():
    scenario = _scenario()
    body = {"scenario_id": "abc", "node_count": 12, "location": {"q": "x"}, "scenario": scenario, "tail": [1, 2]}

    response = main_module._fast_scenario_json(lambda: body)()

    expected = json.loads(json.dumps(jsonable_encoder(body)))
    assert json.loads(response.body) == expected
    assert response.media_type == "application/json"
    # Key order is part of the contract with existing clients.
    assert list(json.loads(response.body).keys()) == list(body.keys())


def test_unicode_survives_the_round_trip():
    response = main_module._fast_scenario_json(lambda: {"scenario": _scenario()})()
    names = [e["road_name"] for e in json.loads(response.body)["scenario"]["edges"]]
    assert "Café Road – हज़रतगंज" in names


def test_non_scenario_and_non_dict_responses_pass_through_untouched():
    plain = {"message": "hi"}
    assert main_module._fast_scenario_json(lambda: plain)() is plain
    assert main_module._fast_scenario_json(lambda: "text")() == "text"


def test_generate_endpoint_still_returns_a_normal_json_response():
    client = TestClient(main_module.app)
    resp = client.post("/api/problem/generate", json={
        "source": "synthetic", "num_nodes": 15, "num_jobs": 5, "num_vehicles": 2, "seed": 1})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert body["node_count"] == len(body["scenario"]["nodes"]) == 15
    assert list(body.keys())[:3] == ["scenario_id", "scenario_hash", "data_source"]
