"""Tests for the unified edge-cost engine (realdata.conditions).

The contract under test is the Phase 5 pipeline:

    current_travel_time = base_travel_time
                          * traffic_multiplier
                          * weather_multiplier
                          * incident_multiplier

with `base_travel_time` never modified, the three axes independent, and the
whole thing deterministic.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import Edge, ProblemScenario
from problem_generator import generate_synthetic_scenario
from realdata.conditions import (
    DEFAULT_INCIDENT_MULTIPLIER,
    WEATHER_IMPACT,
    ConditionRequest,
    apply_conditions,
    apply_incidents,
    clear_conditions,
    count_incident_edges,
    recompute_edge_cost,
    scenario_center,
    weather_multiplier_for,
)
from realdata.traffic_model import (
    LEVEL_MULTIPLIERS,
    MODE_HEAVY,
    MODE_MODERATE,
    MODE_NORMAL,
    MODE_SEVERE,
    SimulatedTrafficProvider,
    TrafficProviderError,
    edge_susceptibility,
    edge_traffic_multiplier,
    level_multiplier,
)
from realdata.weather import (
    CONDITION_CLEAR,
    CONDITION_RAIN,
    CONDITION_SNOW,
    CONDITION_UNKNOWN,
    WeatherObservation,
    fallback_observation,
)


def _scenario(**kw):
    params = dict(num_nodes=20, num_jobs=8, num_vehicles=3, seed=42)
    params.update(kw)
    return generate_synthetic_scenario(**params)


def _edge(base=10.0, **kw):
    params = dict(
        source=0, destination=1, distance=5.0,
        base_travel_time=base, current_travel_time=base,
    )
    params.update(kw)
    return Edge(**params)


def _observation(condition, source="network"):
    return WeatherObservation(
        latitude=12.0, longitude=77.0, source=source, condition=condition,
    )


# ============================================== 1. base time is never touched

def test_base_travel_time_is_never_modified_by_any_condition():
    original = _scenario()
    before = [e.base_travel_time for e in original.edges]

    conditioned = apply_conditions(original, ConditionRequest(traffic_mode=MODE_SEVERE))
    conditioned, _ = apply_incidents(conditioned, {(conditioned.edges[0].source,
                                                    conditioned.edges[0].destination): 6.0})

    assert [e.base_travel_time for e in conditioned.edges] == before
    # ...and the input scenario itself was not mutated either.
    assert [e.base_travel_time for e in original.edges] == before
    assert all(e.traffic_factor == 1.0 for e in original.edges)


# ================================================ 2-4. each axis, in isolation

def test_traffic_multiplier_alone_changes_current_travel_time():
    edge = _edge(base=10.0)
    edge.traffic_multiplier = 2.5
    recompute_edge_cost(edge)

    assert edge.current_travel_time == pytest.approx(25.0)
    assert edge.traffic_factor == pytest.approx(2.5)
    assert edge.base_travel_time == 10.0


def test_weather_multiplier_alone_changes_current_travel_time():
    edge = _edge(base=10.0)
    edge.weather_multiplier = 1.25
    recompute_edge_cost(edge)

    assert edge.current_travel_time == pytest.approx(12.5)
    assert edge.traffic_factor == pytest.approx(1.25)


def test_incident_multiplier_alone_changes_current_travel_time():
    edge = _edge(base=10.0)
    edge.incident_multiplier = 4.0
    recompute_edge_cost(edge)

    assert edge.current_travel_time == pytest.approx(40.0)
    assert edge.traffic_factor == pytest.approx(4.0)


# ========================================================= 5. they compose

def test_multipliers_compose_multiplicatively():
    edge = _edge(base=10.0)
    edge.traffic_multiplier = 1.5
    edge.weather_multiplier = 1.2
    edge.incident_multiplier = 2.0
    recompute_edge_cost(edge)

    assert edge.traffic_factor == pytest.approx(3.6)
    assert edge.current_travel_time == pytest.approx(36.0)


def test_composition_order_does_not_matter():
    a = _edge(base=7.0)
    a.traffic_multiplier, a.weather_multiplier, a.incident_multiplier = 1.5, 1.1, 3.0
    recompute_edge_cost(a)

    b = _edge(base=7.0)
    b.incident_multiplier, b.weather_multiplier, b.traffic_multiplier = 3.0, 1.1, 1.5
    recompute_edge_cost(b)

    assert a.current_travel_time == b.current_travel_time


# ============================================== 6. normal conditions are a no-op

def test_normal_traffic_with_weather_off_preserves_free_flow_exactly():
    scenario = _scenario()
    conditioned = apply_conditions(
        scenario, ConditionRequest(traffic_mode=MODE_NORMAL, weather_enabled=False)
    )

    for edge in conditioned.edges:
        assert edge.traffic_multiplier == 1.0
        assert edge.weather_multiplier == 1.0
        assert edge.incident_multiplier == 1.0
        assert edge.traffic_factor == 1.0
        assert edge.current_travel_time == pytest.approx(edge.base_travel_time)


def test_clear_conditions_returns_to_free_flow():
    scenario = apply_conditions(_scenario(), ConditionRequest(traffic_mode=MODE_HEAVY))
    scenario, _ = apply_incidents(scenario, {(scenario.edges[0].source,
                                              scenario.edges[0].destination): 5.0})

    cleared = clear_conditions(scenario)

    assert cleared.conditions is None
    for edge in cleared.edges:
        assert edge.current_travel_time == pytest.approx(edge.base_travel_time)


# =================================================== the documented level table

@pytest.mark.parametrize("mode,expected", [
    (MODE_NORMAL, 1.0),
    (MODE_MODERATE, 1.5),
    (MODE_HEAVY, 2.5),
    (MODE_SEVERE, 4.0),
])
def test_documented_level_multipliers(mode, expected):
    """The published model parameters are what the code actually uses."""
    assert LEVEL_MULTIPLIERS[mode] == expected
    assert level_multiplier(mode) == expected


def test_heavier_mode_never_produces_a_faster_road():
    scenario = _scenario()
    previous = None
    for mode in (MODE_NORMAL, MODE_MODERATE, MODE_HEAVY, MODE_SEVERE):
        conditioned = apply_conditions(scenario, ConditionRequest(traffic_mode=mode))
        total = sum(e.current_travel_time for e in conditioned.edges)
        if previous is not None:
            assert total > previous
        previous = total


def test_unknown_traffic_mode_is_rejected_rather_than_silently_ignored():
    with pytest.raises(TrafficProviderError):
        apply_conditions(_scenario(), ConditionRequest(traffic_mode="rush-hour-ish"))


def test_congestion_is_not_uniform_so_it_can_actually_change_routes():
    """A single multiplier on every edge would leave all shortest paths
    unchanged. The per-road-class model exists precisely to avoid that."""
    conditioned = apply_conditions(_scenario(), ConditionRequest(traffic_mode=MODE_HEAVY))
    distinct = {round(e.traffic_multiplier, 6) for e in conditioned.edges}
    assert len(distinct) > 1


def test_susceptibility_prefers_osm_road_class_over_implied_speed():
    residential = _edge(base=10.0, highway="residential")
    motorway = _edge(base=10.0, highway="motorway")

    assert edge_susceptibility(residential) < edge_susceptibility(motorway)
    assert (edge_traffic_multiplier(residential, MODE_HEAVY)
            < edge_traffic_multiplier(motorway, MODE_HEAVY))


def test_bpr_formulation_is_available_and_differs_from_the_level_table():
    """The optional BPR variant reuses qdfro_graph.weights.bpr_travel_time."""
    flat = apply_conditions(_scenario(), ConditionRequest(traffic_mode=MODE_HEAVY))
    bpr = apply_conditions(
        _scenario(), ConditionRequest(traffic_mode=MODE_HEAVY, use_bpr=True)
    )

    assert bpr.conditions.traffic_formulation == "bpr"
    assert flat.conditions.traffic_formulation == "level-table"
    assert (sum(e.current_travel_time for e in bpr.edges)
            != sum(e.current_travel_time for e in flat.edges))


def test_bpr_at_normal_is_still_exactly_free_flow():
    bpr = apply_conditions(
        _scenario(), ConditionRequest(traffic_mode=MODE_NORMAL, use_bpr=True)
    )
    for edge in bpr.edges:
        assert edge.current_travel_time == pytest.approx(edge.base_travel_time)


# ============================================================ weather mapping

@pytest.mark.parametrize("condition", [CONDITION_CLEAR, CONDITION_RAIN, CONDITION_SNOW])
def test_weather_multiplier_comes_from_the_documented_table(condition):
    assert weather_multiplier_for(_observation(condition)) == WEATHER_IMPACT[condition]


def test_clear_weather_has_no_cost_effect():
    assert weather_multiplier_for(_observation(CONDITION_CLEAR)) == 1.0


def test_worse_weather_costs_more_than_better_weather():
    assert (weather_multiplier_for(_observation(CONDITION_SNOW))
            > weather_multiplier_for(_observation(CONDITION_RAIN))
            > weather_multiplier_for(_observation(CONDITION_CLEAR)))


def test_a_fallback_observation_applies_no_weather_effect():
    """The absence of weather data must never be dressed up as fair weather."""
    assert weather_multiplier_for(fallback_observation(12.0, 77.0)) == 1.0
    assert weather_multiplier_for(None) == 1.0
    assert weather_multiplier_for(_observation(CONDITION_UNKNOWN)) == 1.0


def test_weather_is_applied_to_every_edge_uniformly():
    """Weather is one observation for the whole extract, so unlike traffic it
    scales every edge equally - documented, and asserted so it stays true."""
    scenario = _scenario()
    conditioned = apply_conditions(
        scenario,
        ConditionRequest(weather_enabled=True),
        weather_observation=_observation(CONDITION_RAIN),
    )

    expected = WEATHER_IMPACT[CONDITION_RAIN]
    assert {e.weather_multiplier for e in conditioned.edges} == {expected}
    for edge in conditioned.edges:
        assert edge.current_travel_time == pytest.approx(edge.base_travel_time * expected)


def test_weather_and_traffic_compose_on_a_real_scenario():
    scenario = _scenario()
    conditioned = apply_conditions(
        scenario,
        ConditionRequest(traffic_mode=MODE_MODERATE, weather_enabled=True),
        weather_observation=_observation(CONDITION_RAIN),
    )

    # Stored travel times are rounded to TRAVEL_TIME_PRECISION (5 dp) so that
    # two runs of the same conditions are byte-identical and the
    # content-addressed route-matrix cache still hits - hence the absolute
    # tolerance at exactly that precision rather than an exact comparison.
    for edge in conditioned.edges:
        expected = (
            edge.base_travel_time
            * edge.traffic_multiplier
            * edge.weather_multiplier
            * edge.incident_multiplier
        )
        assert edge.current_travel_time == pytest.approx(expected, abs=1e-5)


# =============================================================== incidents

def test_incident_is_mirrored_onto_the_reverse_direction():
    scenario = _scenario()
    u, v = scenario.edges[0].source, scenario.edges[0].destination

    conditioned, changed = apply_incidents(scenario, {(u, v): 4.0})

    assert changed == 2
    for edge in conditioned.edges:
        if {edge.source, edge.destination} == {u, v}:
            assert edge.incident_multiplier == 4.0
            assert edge.current_travel_time == pytest.approx(edge.base_travel_time * 4.0)


def test_incidents_survive_a_traffic_level_change():
    """Raising the traffic level must not quietly clear a road closure."""
    scenario = _scenario()
    u, v = scenario.edges[0].source, scenario.edges[0].destination
    with_incident, _ = apply_incidents(scenario, {(u, v): 5.0})

    later = apply_conditions(with_incident, ConditionRequest(traffic_mode=MODE_HEAVY))

    disrupted = [e for e in later.edges if {e.source, e.destination} == {u, v}]
    assert disrupted
    for edge in disrupted:
        assert edge.incident_multiplier == 5.0
        assert edge.traffic_multiplier > 1.0
        assert edge.traffic_factor == pytest.approx(
            edge.traffic_multiplier * edge.weather_multiplier * 5.0
        )


def test_an_incident_can_be_cleared_without_touching_traffic_or_weather():
    scenario = apply_conditions(
        _scenario(),
        ConditionRequest(traffic_mode=MODE_HEAVY, weather_enabled=True),
        weather_observation=_observation(CONDITION_RAIN),
    )
    u, v = scenario.edges[0].source, scenario.edges[0].destination

    disrupted, _ = apply_incidents(scenario, {(u, v): 6.0})
    restored, _ = apply_incidents(disrupted, {(u, v): 1.0})

    assert count_incident_edges(restored) == 0
    for edge in restored.edges:
        if {edge.source, edge.destination} == {u, v}:
            assert edge.traffic_multiplier > 1.0
            assert edge.weather_multiplier == WEATHER_IMPACT[CONDITION_RAIN]


def test_incident_edge_count_is_reported():
    scenario = apply_conditions(_scenario(), ConditionRequest(traffic_mode=MODE_MODERATE))
    u, v = scenario.edges[0].source, scenario.edges[0].destination

    disrupted, _ = apply_incidents(scenario, {(u, v): DEFAULT_INCIDENT_MULTIPLIER})

    assert disrupted.conditions.incident_edge_count == 2


# ========================================================== 10. determinism

def test_same_scenario_and_conditions_produce_identical_edge_costs():
    a = apply_conditions(_scenario(seed=11), ConditionRequest(traffic_mode=MODE_HEAVY))
    b = apply_conditions(_scenario(seed=11), ConditionRequest(traffic_mode=MODE_HEAVY))

    assert [e.current_travel_time for e in a.edges] == [e.current_travel_time for e in b.edges]
    assert [e.traffic_multiplier for e in a.edges] == [e.traffic_multiplier for e in b.edges]
    assert a.conditions.signature == b.conditions.signature


def test_condition_signature_changes_when_conditions_change():
    normal = apply_conditions(_scenario(), ConditionRequest(traffic_mode=MODE_NORMAL))
    heavy = apply_conditions(_scenario(), ConditionRequest(traffic_mode=MODE_HEAVY))

    assert normal.conditions.signature != heavy.conditions.signature


def test_condition_summary_labels_simulated_traffic_as_simulated():
    conditioned = apply_conditions(_scenario(), ConditionRequest(traffic_mode=MODE_HEAVY))

    assert conditioned.conditions.traffic_source == "simulated"
    assert conditioned.conditions.traffic_is_simulated is True


# ============================================================== positioning

def test_weather_is_located_at_the_depot():
    scenario = _scenario()
    depot = next(n for n in scenario.nodes if n.id == scenario.depot_node_id)

    assert scenario_center(scenario) == (depot.lat, depot.lng)
