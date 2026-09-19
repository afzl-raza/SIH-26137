"""Current weather from Open-Meteo.

Open-Meteo is a free, key-less weather API. What it returns here is a *real
observation* for a real coordinate, and it is labelled as such. When it cannot
be reached and nothing usable is cached, this module does NOT invent a
plausible-looking reading: it returns an observation whose `source` is
"fallback" and whose `fallback_used` flag is True, carrying no weather values
at all. The caller (realdata.conditions) then applies a multiplier of exactly
1.0 - no weather effect - and the API reports the fallback so the UI can say
so.

Location
--------
Input is a latitude/longitude, so weather follows whatever location the
scenario is actually about: a geocoded place name, a raw coordinate pair or a
bounding box centre. There is no per-city configuration anywhere.

Provenance
----------
The same labels the rest of realdata uses, plus one:

    network      - fetched from Open-Meteo just now
    cache        - a previous fetch, still within TTL
    cache-stale  - a previous fetch past its TTL, served because the network
                   failed; still a real past observation, labelled as old
    fallback     - no observation available at all; no weather applied

Provider abstraction
--------------------
`WeatherProvider` is the seam another provider would plug into later.
`OpenMeteoProvider` is the only implementation, and nothing outside this
module knows the Open-Meteo request shape.

What is a model assumption
--------------------------
Nothing in this module is. The observation is real or explicitly absent. The
step that turns "it is raining" into "travel takes 10% longer" is a documented
*assumption*, and it lives in realdata.conditions together with every other
edge-cost assumption, so there is exactly one place where edge cost is
assembled.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from .cache import (
    DISK_CACHE,
    DiskCache,
    SOURCE_CACHE,
    SOURCE_CACHE_STALE,
    SOURCE_NETWORK,
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_NAMESPACE = "weather"

# Weather changes on a timescale of minutes-to-hours, unlike road layouts.
# Fifteen minutes keeps a demo session on a single fetch without ever showing
# a reading that is meaningfully out of date.
WEATHER_TTL_SECONDS = 15 * 60
DEFAULT_TIMEOUT_S = 10.0

# Fifth provenance label, specific to weather: we have no observation at all.
SOURCE_FALLBACK = "fallback"

# Cache locality. Two decimal places of latitude is ~1.1 km, comfortably finer
# than any weather gradient that matters here, so scenarios in the same
# neighbourhood share one cache entry instead of re-querying per run.
_COORD_PRECISION = 2

# Condition categories this module reports. realdata.conditions maps each one
# to a travel-time multiplier.
CONDITION_CLEAR = "clear"
CONDITION_CLOUDY = "cloudy"
CONDITION_FOG = "fog"
CONDITION_DRIZZLE = "drizzle"
CONDITION_RAIN = "rain"
CONDITION_HEAVY_RAIN = "heavy_rain"
CONDITION_FREEZING = "freezing"
CONDITION_SNOW = "snow"
CONDITION_THUNDERSTORM = "thunderstorm"
CONDITION_UNKNOWN = "unknown"

# WMO 4677 present-weather codes, which is what Open-Meteo's `weather_code`
# field reports, grouped into the categories above.
# Reference: https://open-meteo.com/en/docs - "WMO Weather interpretation codes".
WMO_CODE_CONDITIONS: Dict[int, str] = {
    0: CONDITION_CLEAR,
    1: CONDITION_CLOUDY, 2: CONDITION_CLOUDY, 3: CONDITION_CLOUDY,
    45: CONDITION_FOG, 48: CONDITION_FOG,
    51: CONDITION_DRIZZLE, 53: CONDITION_DRIZZLE, 55: CONDITION_DRIZZLE,
    56: CONDITION_FREEZING, 57: CONDITION_FREEZING,
    61: CONDITION_RAIN, 63: CONDITION_RAIN,
    65: CONDITION_HEAVY_RAIN,
    66: CONDITION_FREEZING, 67: CONDITION_FREEZING,
    71: CONDITION_SNOW, 73: CONDITION_SNOW, 75: CONDITION_SNOW, 77: CONDITION_SNOW,
    80: CONDITION_RAIN, 81: CONDITION_RAIN,
    82: CONDITION_HEAVY_RAIN,
    85: CONDITION_SNOW, 86: CONDITION_SNOW,
    95: CONDITION_THUNDERSTORM, 96: CONDITION_THUNDERSTORM, 99: CONDITION_THUNDERSTORM,
}

CONDITION_DESCRIPTIONS: Dict[str, str] = {
    CONDITION_CLEAR: "Clear sky",
    CONDITION_CLOUDY: "Cloudy",
    CONDITION_FOG: "Fog",
    CONDITION_DRIZZLE: "Drizzle",
    CONDITION_RAIN: "Rain",
    CONDITION_HEAVY_RAIN: "Heavy rain",
    CONDITION_FREEZING: "Freezing rain",
    CONDITION_SNOW: "Snow",
    CONDITION_THUNDERSTORM: "Thunderstorm",
    CONDITION_UNKNOWN: "No weather observation available",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify_wmo_code(code: Optional[int]) -> str:
    """WMO present-weather code -> one of this module's condition categories.

    An unmapped or missing code becomes CONDITION_UNKNOWN rather than being
    guessed at; unknown carries no travel-time effect downstream.
    """
    if code is None:
        return CONDITION_UNKNOWN
    try:
        return WMO_CODE_CONDITIONS.get(int(code), CONDITION_UNKNOWN)
    except (TypeError, ValueError):
        return CONDITION_UNKNOWN


@dataclass(frozen=True)
class WeatherObservation:
    """One weather reading, or an explicit statement that we have none.

    `source` is always one of network / cache / cache-stale / fallback, and
    `fallback_used` is True only in the last case. When it is True every
    measured field is None - this object never carries an invented value.
    """
    latitude: float
    longitude: float
    source: str
    condition: str = CONDITION_UNKNOWN
    weather_code: Optional[int] = None
    temperature_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_kph: Optional[float] = None
    observed_at: Optional[str] = None
    retrieved_at: str = ""
    provider: str = "open-meteo"
    fallback_used: bool = False
    error: Optional[str] = None

    @property
    def is_real_observation(self) -> bool:
        """True when this came from the provider (now or earlier), False for
        the fallback. The UI uses this to decide whether it may claim to be
        showing weather at all."""
        return not self.fallback_used

    @property
    def description(self) -> str:
        return CONDITION_DESCRIPTIONS.get(self.condition, self.condition)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": round(self.latitude, 4),
            "longitude": round(self.longitude, 4),
            "source": self.source,
            "provider": self.provider,
            "condition": self.condition,
            "description": self.description,
            "weather_code": self.weather_code,
            "temperature_c": self.temperature_c,
            "precipitation_mm": self.precipitation_mm,
            "wind_speed_kph": self.wind_speed_kph,
            "observed_at": self.observed_at,
            "retrieved_at": self.retrieved_at,
            "fallback_used": self.fallback_used,
            "is_real_observation": self.is_real_observation,
            "error": self.error,
        }


def fallback_observation(
    latitude: float,
    longitude: float,
    error: Optional[str] = None,
) -> WeatherObservation:
    """The explicit "we have no weather" result.

    Deliberately carries no temperature, no precipitation and no condition - a
    fallback must never be mistakable for a reading.
    """
    return WeatherObservation(
        latitude=latitude,
        longitude=longitude,
        source=SOURCE_FALLBACK,
        condition=CONDITION_UNKNOWN,
        retrieved_at=_utc_now_iso(),
        fallback_used=True,
        error=error,
    )


# --------------------------------------------------------------- transport

def _http_get_json(url: str, params: Dict[str, Any], timeout_s: float) -> Any:
    """Default transport. Imported lazily, and injectable, so the module stays
    importable and fully testable without httpx or a network."""
    import httpx

    response = httpx.get(url, params=params, timeout=timeout_s, follow_redirects=True)
    response.raise_for_status()
    return response.json()


FetchJson = Callable[[str, Dict[str, Any], float], Any]


# ---------------------------------------------------------------- provider

class WeatherProvider(ABC):
    """Seam for swapping in a different weather source later.

    An implementation must never raise for a network problem: it returns a
    fallback observation instead, so a weather outage cannot take the
    optimizer down with it.
    """

    name: str = "abstract"

    @abstractmethod
    def get_weather(self, latitude: float, longitude: float) -> WeatherObservation:
        """Current weather at a coordinate. Always returns an observation."""


class OpenMeteoProvider(WeatherProvider):
    """Open-Meteo current-conditions adapter.

    Cache first, network second, stale cache third, fallback last - the same
    order geocoding and the OSM loader use, with the same labels.
    """

    name = "open-meteo"

    def __init__(
        self,
        cache: Optional[DiskCache] = None,
        fetch_json: Optional[FetchJson] = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        ttl_seconds: float = WEATHER_TTL_SECONDS,
        allow_stale: bool = True,
    ):
        self._cache = cache if cache is not None else DISK_CACHE
        self._fetch = fetch_json if fetch_json is not None else _http_get_json
        self._timeout_s = timeout_s
        self._ttl = ttl_seconds
        self._allow_stale = allow_stale

    def _cache_key(self, latitude: float, longitude: float) -> Dict[str, Any]:
        return {
            "provider": self.name,
            "lat": round(float(latitude), _COORD_PRECISION),
            "lon": round(float(longitude), _COORD_PRECISION),
        }

    def get_weather(self, latitude: float, longitude: float) -> WeatherObservation:
        lat, lon = float(latitude), float(longitude)
        key = self._cache_key(lat, lon)

        entry = self._cache.get(CACHE_NAMESPACE, key)
        if entry is not None and not entry.is_stale(self._ttl):
            return self._observation_from_payload(entry.payload, lat, lon, SOURCE_CACHE)

        try:
            payload = self._fetch(
                OPEN_METEO_URL,
                {
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
                    "wind_speed_unit": "kmh",
                    "timezone": "UTC",
                },
                self._timeout_s,
            )
            stored = _extract_current(payload)
            self._cache.set(CACHE_NAMESPACE, key, stored)
            return self._observation_from_payload(stored, lat, lon, SOURCE_NETWORK)
        except Exception as exc:
            # Never propagate: a weather outage must not break optimization.
            if self._allow_stale and entry is not None:
                return self._observation_from_payload(
                    entry.payload, lat, lon, SOURCE_CACHE_STALE
                )
            return fallback_observation(lat, lon, error=f"{type(exc).__name__}: {exc}")

    def _observation_from_payload(
        self,
        payload: Dict[str, Any],
        latitude: float,
        longitude: float,
        provenance: str,
    ) -> WeatherObservation:
        code = payload.get("weather_code")
        return WeatherObservation(
            latitude=latitude,
            longitude=longitude,
            source=provenance,
            condition=classify_wmo_code(code),
            weather_code=int(code) if code is not None else None,
            temperature_c=payload.get("temperature_c"),
            precipitation_mm=payload.get("precipitation_mm"),
            wind_speed_kph=payload.get("wind_speed_kph"),
            observed_at=payload.get("observed_at"),
            retrieved_at=_utc_now_iso(),
            provider=self.name,
            fallback_used=False,
        )


def _extract_current(payload: Any) -> Dict[str, Any]:
    """Open-Meteo response -> the flat record we cache.

    Caching the normalised record rather than the raw response keeps the
    provider's wire format out of the cache, so a response-shape change
    cannot silently corrupt old entries.
    """
    if not isinstance(payload, dict):
        raise ValueError("Open-Meteo returned an unexpected payload type.")
    current = payload.get("current")
    if not isinstance(current, dict):
        raise ValueError("Open-Meteo response contained no 'current' block.")

    def _num(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    code = current.get("weather_code")
    return {
        "weather_code": int(code) if code is not None else None,
        "temperature_c": _num(current.get("temperature_2m")),
        "precipitation_mm": _num(current.get("precipitation")),
        "wind_speed_kph": _num(current.get("wind_speed_10m")),
        "observed_at": current.get("time"),
    }


# Shared provider instance used by the API layer.
DEFAULT_WEATHER_PROVIDER = OpenMeteoProvider()


def fetch_current_weather(
    latitude: float,
    longitude: float,
    *,
    provider: Optional[WeatherProvider] = None,
) -> WeatherObservation:
    """Module-level convenience entry point. Always returns an observation."""
    active = provider if provider is not None else DEFAULT_WEATHER_PROVIDER
    return active.get_weather(latitude, longitude)
