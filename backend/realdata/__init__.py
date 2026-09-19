"""Real-world data ingestion and scenario management for Q-DFRO.

Only modules that actually work are re-exported here. `osm_loader`,
`weather` and `traffic_model` exist as interface stubs for Phases 4, 8 and
9/10 and are intentionally left out, so nothing can import them by accident
and mistake a stub for a working feature.
"""

from .cache import (
    DISK_CACHE,
    DiskCache,
    CacheEntry,
    SOURCE_CACHE,
    SOURCE_CACHE_STALE,
    SOURCE_ERROR,
    SOURCE_NETWORK,
    default_cache_root,
)
from .geocoding import (
    BoundingBox,
    GeocodingError,
    ResolvedLocation,
    geocode_place,
    resolve_location,
)
from .scenario_store import (
    SCENARIO_STORE,
    ScenarioNotFoundError,
    ScenarioRecord,
    ScenarioStore,
)

__all__ = [
    # cache
    "DISK_CACHE",
    "DiskCache",
    "CacheEntry",
    "SOURCE_NETWORK",
    "SOURCE_CACHE",
    "SOURCE_CACHE_STALE",
    "SOURCE_ERROR",
    "default_cache_root",
    # geocoding
    "BoundingBox",
    "GeocodingError",
    "ResolvedLocation",
    "geocode_place",
    "resolve_location",
    # scenario store
    "ScenarioStore",
    "ScenarioRecord",
    "ScenarioNotFoundError",
    "SCENARIO_STORE",
]
