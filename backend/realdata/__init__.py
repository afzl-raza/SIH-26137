"""Real-world data ingestion and scenario management for Q-DFRO.

Only modules that actually work are re-exported here. `osm_loader` is left
out deliberately - it is imported directly by the API layer, which handles
its error type.

`conditions` is the single authoritative edge-cost engine; `traffic_model`
supplies simulated congestion and the seam for a real feed; `weather` supplies
real Open-Meteo observations with explicit fallback labelling.
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
from .traffic_model import (
    DEFAULT_TRAFFIC_PROVIDER,
    LEVEL_MULTIPLIERS,
    MODE_HEAVY,
    MODE_MODERATE,
    MODE_NORMAL,
    MODE_SEVERE,
    TRAFFIC_MODES,
    TRAFFIC_SOURCE_EXTERNAL,
    TRAFFIC_SOURCE_SIMULATED,
    ExternalTrafficProvider,
    SimulatedTrafficProvider,
    TrafficConditions,
    TrafficProvider,
    TrafficProviderError,
    get_traffic_provider,
    normalize_mode,
)
from .weather import (
    DEFAULT_WEATHER_PROVIDER,
    SOURCE_FALLBACK,
    OpenMeteoProvider,
    WeatherObservation,
    WeatherProvider,
    fetch_current_weather,
)
from .conditions import (
    DEFAULT_INCIDENT_MULTIPLIER,
    WEATHER_IMPACT,
    ConditionRequest,
    apply_conditions,
    apply_incidents,
    clear_conditions,
    recompute_edge_cost,
    scenario_center,
    weather_multiplier_for,
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
    # traffic model (simulated congestion + provider seam)
    "TrafficProvider",
    "TrafficConditions",
    "TrafficProviderError",
    "SimulatedTrafficProvider",
    "ExternalTrafficProvider",
    "DEFAULT_TRAFFIC_PROVIDER",
    "get_traffic_provider",
    "normalize_mode",
    "LEVEL_MULTIPLIERS",
    "TRAFFIC_MODES",
    "MODE_NORMAL",
    "MODE_MODERATE",
    "MODE_HEAVY",
    "MODE_SEVERE",
    "TRAFFIC_SOURCE_SIMULATED",
    "TRAFFIC_SOURCE_EXTERNAL",
    # weather (real observations)
    "WeatherProvider",
    "WeatherObservation",
    "OpenMeteoProvider",
    "DEFAULT_WEATHER_PROVIDER",
    "fetch_current_weather",
    "SOURCE_FALLBACK",
    # condition engine (the one place edge cost is assembled)
    "ConditionRequest",
    "apply_conditions",
    "apply_incidents",
    "clear_conditions",
    "recompute_edge_cost",
    "scenario_center",
    "weather_multiplier_for",
    "WEATHER_IMPACT",
    "DEFAULT_INCIDENT_MULTIPLIER",
]
