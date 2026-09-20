"""Tests for the Open-Meteo weather adapter.

No test touches the network: the transport is injected. What matters here is
honesty about provenance - a fallback must be impossible to mistake for an
observation, and an outage must never break optimization.
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from realdata.cache import (
    DiskCache,
    SOURCE_CACHE,
    SOURCE_CACHE_STALE,
    SOURCE_NETWORK,
)
from realdata.weather import (
    CONDITION_CLEAR,
    CONDITION_HEAVY_RAIN,
    CONDITION_RAIN,
    CONDITION_SNOW,
    CONDITION_THUNDERSTORM,
    CONDITION_UNKNOWN,
    SOURCE_FALLBACK,
    OpenMeteoProvider,
    classify_wmo_code,
    fetch_current_weather,
)

LUCKNOW = (26.8381, 80.9346)


def _payload(weather_code=61, temp=27.4, precip=1.2, wind=11.0):
    """A response shaped like Open-Meteo's `current` block."""
    return {
        "latitude": LUCKNOW[0],
        "longitude": LUCKNOW[1],
        "current": {
            "time": "2026-09-19T10:00",
            "temperature_2m": temp,
            "precipitation": precip,
            "wind_speed_10m": wind,
            "weather_code": weather_code,
        },
    }


@pytest.fixture
def cache():
    return DiskCache(root=Path(tempfile.mkdtemp(prefix="weather_")))


def _provider(cache, payload=None, fail=False, **kw):
    calls = []

    def transport(url, params, timeout):
        calls.append(params)
        if fail:
            raise ConnectionError("open-meteo unreachable")
        return payload if payload is not None else _payload()

    provider = OpenMeteoProvider(cache=cache, fetch_json=transport, **kw)
    return provider, calls


# ======================================================== code classification

@pytest.mark.parametrize("code,expected", [
    (0, CONDITION_CLEAR),
    (3, "cloudy"),
    (45, "fog"),
    (61, CONDITION_RAIN),
    (65, CONDITION_HEAVY_RAIN),
    (75, CONDITION_SNOW),
    (95, CONDITION_THUNDERSTORM),
])
def test_wmo_codes_map_to_conditions(code, expected):
    assert classify_wmo_code(code) == expected


def test_unmapped_or_missing_code_is_unknown_not_guessed():
    assert classify_wmo_code(None) == CONDITION_UNKNOWN
    assert classify_wmo_code(4242) == CONDITION_UNKNOWN
    assert classify_wmo_code("not-a-code") == CONDITION_UNKNOWN


# ============================================================ the happy path

def test_a_successful_fetch_is_labelled_network_and_carries_real_values(cache):
    provider, calls = _provider(cache)

    obs = provider.get_weather(*LUCKNOW)

    assert obs.source == SOURCE_NETWORK
    assert obs.fallback_used is False
    assert obs.is_real_observation is True
    assert obs.condition == CONDITION_RAIN
    assert obs.temperature_c == 27.4
    assert obs.precipitation_mm == 1.2
    assert obs.wind_speed_kph == 11.0
    assert obs.observed_at == "2026-09-19T10:00"
    assert len(calls) == 1


def test_the_request_asks_for_the_fields_we_actually_use(cache):
    provider, calls = _provider(cache)
    provider.get_weather(*LUCKNOW)

    current = calls[0]["current"]
    for field in ("temperature_2m", "precipitation", "wind_speed_10m", "weather_code"):
        assert field in current


def test_a_second_lookup_is_served_from_cache_without_a_second_request(cache):
    provider, calls = _provider(cache)

    provider.get_weather(*LUCKNOW)
    second = provider.get_weather(*LUCKNOW)

    assert second.source == SOURCE_CACHE
    assert second.is_real_observation is True
    assert len(calls) == 1, "a cached reading must not re-query the provider"


def test_weather_follows_the_coordinate_it_is_asked_for(cache):
    """No city is special-cased: the coordinate is passed straight through."""
    provider, calls = _provider(cache)

    provider.get_weather(51.5074, -0.1278)

    assert calls[0]["latitude"] == pytest.approx(51.5074)
    assert calls[0]["longitude"] == pytest.approx(-0.1278)


# ================================================== 14. failure -> fallback

def test_a_provider_failure_with_no_cache_returns_an_explicit_fallback(cache):
    provider, calls = _provider(cache, fail=True)

    obs = provider.get_weather(*LUCKNOW)

    assert obs.source == SOURCE_FALLBACK
    assert obs.fallback_used is True
    assert obs.is_real_observation is False
    assert obs.condition == CONDITION_UNKNOWN
    assert obs.error is not None


def test_a_fallback_carries_no_invented_measurements(cache):
    provider, _ = _provider(cache, fail=True)

    obs = provider.get_weather(*LUCKNOW)

    assert obs.temperature_c is None
    assert obs.precipitation_mm is None
    assert obs.wind_speed_kph is None
    assert obs.weather_code is None


def test_a_provider_failure_never_raises(cache):
    """A weather outage must not be able to take the optimizer down."""
    provider, _ = _provider(cache, fail=True)
    provider.get_weather(*LUCKNOW)  # must not raise


def test_a_stale_cached_reading_is_served_but_labelled_stale(cache):
    working, _ = _provider(cache, ttl_seconds=0.01)
    working.get_weather(*LUCKNOW)
    time.sleep(0.02)

    broken = OpenMeteoProvider(
        cache=cache,
        fetch_json=lambda url, params, timeout: (_ for _ in ()).throw(ConnectionError()),
        ttl_seconds=0.01,
    )
    obs = broken.get_weather(*LUCKNOW)

    assert obs.source == SOURCE_CACHE_STALE
    assert obs.fallback_used is False, "a stale reading is old, but it is real"
    assert obs.condition == CONDITION_RAIN


def test_a_malformed_response_falls_back_rather_than_inventing_values(cache):
    provider, _ = _provider(cache, payload={"no": "current block"})

    obs = provider.get_weather(*LUCKNOW)

    assert obs.source == SOURCE_FALLBACK
    assert obs.condition == CONDITION_UNKNOWN


# ================================================================ reporting

def test_to_dict_states_provenance_explicitly(cache):
    provider, _ = _provider(cache)

    body = provider.get_weather(*LUCKNOW).to_dict()

    assert body["source"] == SOURCE_NETWORK
    assert body["provider"] == "open-meteo"
    assert body["fallback_used"] is False
    assert body["is_real_observation"] is True
    assert body["description"] == "Rain"


def test_module_level_helper_accepts_an_injected_provider(cache):
    provider, calls = _provider(cache)

    obs = fetch_current_weather(*LUCKNOW, provider=provider)

    assert obs.condition == CONDITION_RAIN
    assert len(calls) == 1
