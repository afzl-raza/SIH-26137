"""Location resolution: turn whatever the user typed into a bounded area.

The system is deliberately location-agnostic. There is no city table anywhere
in this module - "Lucknow", "Patna", "London" and "New York" all take the
identical code path, because place names are resolved by a geocoding service
rather than looked up locally.

Three input modes, all producing the same ResolvedLocation:

    place="Lucknow", radius_m=3000        -> geocode, then box around the hit
    latitude=..., longitude=..., radius_m -> box around the given point
    bbox=(min_lat, min_lon, max_lat, max_lon) -> used directly

Geocoder: Nominatim, the OpenStreetMap project's own service. It needs no API
key, which keeps the prototype free to run, and it resolves against the same
dataset the road network comes from. Its usage policy requires an identifying
User-Agent and at most one request per second; both are honoured here, and
results are cached on disk so repeated demos do not re-query at all.

Area size is always bounded. `radius_m` is clamped to MAX_RADIUS_M so a
careless request cannot try to pull an entire metropolitan area through
Overpass.
"""
from __future__ import annotations

import math
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from .cache import (
    DISK_CACHE,
    DiskCache,
    SOURCE_CACHE,
    SOURCE_CACHE_STALE,
    SOURCE_NETWORK,
)
from observability import trace_event

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CACHE_NAMESPACE = "geocoding"

# Nominatim's usage policy: identify the application, one request per second.
DEFAULT_USER_AGENT = os.environ.get(
    "QDFRO_USER_AGENT",
    "SIH26137-QDFRO/1.0 (+https://github.com/afzl-raza/SIH-26137)",
)
MIN_REQUEST_INTERVAL_S = 1.0
DEFAULT_TIMEOUT_S = 15.0

# Area bounds. The default is a neighbourhood-sized extract, not a city.
DEFAULT_RADIUS_M = 3000.0
MIN_RADIUS_M = 200.0


def _default_max_radius_m(environ=None) -> float:
    """Largest radius a request may ask for. A 10 km extract of a dense city is
    tens of megabytes of Overpass JSON, which then has to be parsed into
    Python objects and shipped to the browser; on a small hosted instance
    (Render's free tier has 512 MB) that risks an out-of-memory restart. So
    the hosted default is 5 km; local development keeps 10 km. Either is
    overridden by QDFRO_MAX_RADIUS_M."""
    environ = os.environ if environ is None else environ
    if environ.get("QDFRO_MAX_RADIUS_M"):
        return float(environ["QDFRO_MAX_RADIUS_M"])
    production = environ.get("QDFRO_ENVIRONMENT", "development").strip().lower() == "production"
    return 5000.0 if production else 10000.0


MAX_RADIUS_M = _default_max_radius_m()

# Place names are stable; cache them for a good long while.
GEOCODE_TTL_SECONDS = 30 * 24 * 60 * 60

_METERS_PER_DEG_LAT = 111_320.0


class GeocodingError(RuntimeError):
    """Raised when a location cannot be resolved by any available means.

    `status_code` is what an API should answer with: 400 when the request
    itself is the problem (unknown place, bad coordinates), 503 when the
    geocoding provider could not be reached or refused us (rate limit, policy
    block, timeout) - the caller did nothing wrong and retrying later may work.
    """

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _provider_failure_label(exc: Exception) -> str:
    """Stable, URL-free reason for an upstream failure."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return f"HTTP {status_code}"
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "timeout"
    if "connect" in name or "network" in name or "connection" in name:
        return "connection error"
    return "request error"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clamp_radius(radius_m: Optional[float]) -> float:
    """Keeps requested areas inside sane bounds, so no single request can try
    to download a whole city."""
    if radius_m is None:
        return DEFAULT_RADIUS_M
    radius = float(radius_m)
    if not math.isfinite(radius):
        raise GeocodingError("radius_m must be a finite number.")
    return float(min(MAX_RADIUS_M, max(MIN_RADIUS_M, radius)))


@dataclass(frozen=True)
class BoundingBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    @classmethod
    def from_center_radius(cls, latitude: float, longitude: float, radius_m: float) -> "BoundingBox":
        """Square box around a point.

        One degree of latitude is ~111.32 km everywhere; one degree of
        longitude shrinks by cos(latitude), which matters a lot at London's
        latitude and very little near the equator. The cosine is floored so a
        near-polar request cannot blow up into a planet-wide box.
        """
        d_lat = radius_m / _METERS_PER_DEG_LAT
        cos_lat = max(0.01, math.cos(math.radians(latitude)))
        d_lon = radius_m / (_METERS_PER_DEG_LAT * cos_lat)
        return cls(
            min_lat=latitude - d_lat,
            min_lon=longitude - d_lon,
            max_lat=latitude + d_lat,
            max_lon=longitude + d_lon,
        )

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.min_lat + self.max_lat) / 2.0, (self.min_lon + self.max_lon) / 2.0)

    def to_dict(self) -> Dict[str, float]:
        return {
            "min_lat": round(self.min_lat, 7),
            "min_lon": round(self.min_lon, 7),
            "max_lat": round(self.max_lat, 7),
            "max_lon": round(self.max_lon, 7),
        }

    def to_overpass_bbox(self) -> str:
        """Overpass expects south,west,north,east."""
        return f"{self.min_lat},{self.min_lon},{self.max_lat},{self.max_lon}"


@dataclass
class ResolvedLocation:
    """A bounded geographic area plus where the answer came from."""
    query: str
    latitude: float
    longitude: float
    bbox: BoundingBox
    radius_m: float
    display_name: str = ""
    resolver: str = "nominatim"   # nominatim | coordinates | bbox
    provenance: str = SOURCE_NETWORK
    retrieved_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": {
                "query": self.query,
                "latitude": round(self.latitude, 7),
                "longitude": round(self.longitude, 7),
                "display_name": self.display_name,
                "resolver": self.resolver,
                "provenance": self.provenance,
            },
            "bbox": self.bbox.to_dict(),
            "radius_m": self.radius_m,
            "retrieved_at": self.retrieved_at,
        }


# --------------------------------------------------------------- transport

_rate_limit_lock = threading.Lock()
_last_request_at = 0.0


def _respect_rate_limit() -> None:
    global _last_request_at
    with _rate_limit_lock:
        elapsed = time.monotonic() - _last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_S:
            time.sleep(MIN_REQUEST_INTERVAL_S - elapsed)
        _last_request_at = time.monotonic()


def _http_get_json(url: str, params: Dict[str, Any], timeout_s: float) -> Any:
    """Default transport. Imported lazily so the module stays importable (and
    testable with a fake transport) even where httpx is not installed."""
    import httpx

    _respect_rate_limit()
    response = httpx.get(
        url,
        params=params,
        timeout=timeout_s,
        headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )
    response.raise_for_status()
    return response.json()


# Injectable so tests never touch the network.
FetchJson = Callable[[str, Dict[str, Any], float], Any]


# ----------------------------------------------------------------- resolve

def geocode_place(
    place: str,
    radius_m: float = DEFAULT_RADIUS_M,
    *,
    cache: Optional[DiskCache] = None,
    fetch_json: Optional[FetchJson] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    allow_stale: bool = True,
) -> ResolvedLocation:
    """Resolves a free-text place name to coordinates and a bounded box.

    Cache first, network second, stale cache last. A stale answer is returned
    only when the network fails, and is labelled SOURCE_CACHE_STALE so no
    caller can mistake it for a fresh lookup.
    """
    query = (place or "").strip()
    if not query:
        raise GeocodingError("A place name is required.")

    radius_m = clamp_radius(radius_m)
    cache = cache if cache is not None else DISK_CACHE
    fetch = fetch_json if fetch_json is not None else _http_get_json
    cache_key = {"provider": "nominatim", "q": query.lower()}

    entry = cache.get(CACHE_NAMESPACE, cache_key)
    if entry is not None and not entry.is_stale(GEOCODE_TTL_SECONDS):
        trace_event("osm.geocode_cache_hit", provenance=SOURCE_CACHE)
        return _location_from_payload(entry.payload, query, radius_m, SOURCE_CACHE)

    try:
        trace_event("osm.geocode_request_started", provider="nominatim")
        started_at = time.monotonic()
        payload = fetch(
            NOMINATIM_URL,
            {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 0},
            timeout_s,
        )
        if not isinstance(payload, list) or not payload:
            message = (
                str(payload.get("error", f"No location found for '{query}'."))
                if isinstance(payload, dict)
                else f"No location found for '{query}'."
            )
            raise GeocodingError(message)
        if not isinstance(payload[0], dict):
            raise GeocodingError(f"The geocoding service returned an invalid result for '{query}'.")
        hit = payload[0]
        stored = {
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "display_name": hit.get("display_name", query),
        }
        cache.set(CACHE_NAMESPACE, cache_key, stored)
        trace_event(
            "osm.geocode_request_completed",
            provider="nominatim",
            duration_ms=round((time.monotonic() - started_at) * 1000),
        )
        return _location_from_payload(stored, query, radius_m, SOURCE_NETWORK)

    except GeocodingError:
        raise
    except Exception as exc:
        # Network down / service unavailable: fall back to a stale entry if we
        # have one, clearly labelled as such.
        if allow_stale and entry is not None:
            trace_event("osm.geocode_cache_stale", provider="nominatim")
            return _location_from_payload(
                entry.payload, query, radius_m, SOURCE_CACHE_STALE)
        trace_event("osm.geocode_request_failed", provider="nominatim", error_type=type(exc).__name__)
        raise GeocodingError(
            f"Could not resolve '{query}' and no cached result is available: "
            f"the geocoding provider is unavailable ({_provider_failure_label(exc)}). "
            f"Please try again later or load the prefetched demo network.",
            status_code=503,
        ) from exc


def cached_location(
    place: str,
    radius_m: float = DEFAULT_RADIUS_M,
    *,
    cache: Optional[DiskCache] = None,
) -> Optional[ResolvedLocation]:
    """The location for `place` if a FRESH geocoding entry is already cached,
    else None. Never touches the network - used to pre-warm things at startup,
    where a slow or blocked provider must not matter."""
    query = (place or "").strip()
    if not query:
        return None
    cache = cache if cache is not None else DISK_CACHE
    entry = cache.get(CACHE_NAMESPACE, {"provider": "nominatim", "q": query.lower()})
    if entry is None or entry.is_stale(GEOCODE_TTL_SECONDS):
        return None
    try:
        return _location_from_payload(entry.payload, query, clamp_radius(radius_m), SOURCE_CACHE)
    except (GeocodingError, KeyError, TypeError, ValueError):
        return None


def _location_from_payload(
    payload: Dict[str, Any],
    query: str,
    radius_m: float,
    provenance: str,
) -> ResolvedLocation:
    lat = float(payload["lat"])
    lon = float(payload["lon"])
    if (
        not math.isfinite(lat)
        or not math.isfinite(lon)
        or not (-90.0 <= lat <= 90.0)
        or not (-180.0 <= lon <= 180.0)
    ):
        raise GeocodingError("The geocoding service returned coordinates outside valid ranges.")
    return ResolvedLocation(
        query=query,
        latitude=lat,
        longitude=lon,
        bbox=BoundingBox.from_center_radius(lat, lon, radius_m),
        radius_m=radius_m,
        display_name=payload.get("display_name", query),
        resolver="nominatim",
        provenance=provenance,
    )


def resolve_location(
    place: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    radius_m: Optional[float] = None,
    *,
    cache: Optional[DiskCache] = None,
    fetch_json: Optional[FetchJson] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ResolvedLocation:
    """Single entry point for all three location input modes.

    Precedence: an explicit bbox wins, then explicit coordinates, then a place
    name. Only the place-name branch touches the network.
    """
    radius = clamp_radius(radius_m)

    if bbox is not None:
        try:
            coordinates = tuple(bbox)
        except TypeError as exc:
            raise GeocodingError("Invalid bbox: expected 4 coordinates.") from exc
        if len(coordinates) != 4:
            raise GeocodingError("Invalid bbox: expected 4 coordinates.")
        try:
            min_lat, min_lon, max_lat, max_lon = (float(v) for v in coordinates)
        except (TypeError, ValueError) as exc:
            raise GeocodingError("Invalid bbox: all coordinates must be numbers.") from exc
        if not all(math.isfinite(value) for value in (min_lat, min_lon, max_lat, max_lon)):
            raise GeocodingError("Invalid bbox: all coordinates must be finite.")
        if (
            min_lat > max_lat
            or min_lon > max_lon
            or min_lat < -90.0
            or max_lat > 90.0
            or min_lon < -180.0
            or max_lon > 180.0
        ):
            raise GeocodingError(
                "Invalid bbox: expected ordered coordinates within latitude and longitude ranges."
            )
        box = BoundingBox(min_lat, min_lon, max_lat, max_lon)
        center_lat, center_lon = box.center
        return ResolvedLocation(
            query=place or f"bbox {box.to_overpass_bbox()}",
            latitude=center_lat,
            longitude=center_lon,
            bbox=box,
            radius_m=radius,
            display_name=place or "custom bounding box",
            resolver="bbox",
            provenance="explicit",
        )

    if latitude is not None and longitude is not None:
        lat, lon = float(latitude), float(longitude)
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not (-90.0 <= lat <= 90.0)
            or not (-180.0 <= lon <= 180.0)
        ):
            raise GeocodingError(f"Coordinates out of range: {lat}, {lon}.")
        return ResolvedLocation(
            query=place or f"{lat},{lon}",
            latitude=lat,
            longitude=lon,
            bbox=BoundingBox.from_center_radius(lat, lon, radius),
            radius_m=radius,
            display_name=place or f"{lat}, {lon}",
            resolver="coordinates",
            provenance="explicit",
        )

    if place:
        return geocode_place(
            place,
            radius_m=radius,
            cache=cache,
            fetch_json=fetch_json,
            timeout_s=timeout_s,
        )

    raise GeocodingError(
        "Provide a place name, latitude/longitude, or a bounding box."
    )
