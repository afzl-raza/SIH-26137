"""Current weather from Open-Meteo.

NOT YET IMPLEMENTED - this is Phase 8. The module exists now so the package
layout is settled; it is deliberately not re-exported from
`realdata/__init__.py`.

Contract agreed for Phase 8
---------------------------
Input is a latitude/longitude (from `realdata.geocoding.ResolvedLocation`),
so weather follows whatever location the user asked for - Lucknow, London or
a raw coordinate pair - with no per-city configuration.

Open-Meteo needs no API key. Planned return: temperature, precipitation,
wind_speed, weather_code, timestamp, and `source = "open-meteo"`, cached
through `realdata.cache` with a short TTL and the usual NETWORK / CACHE /
CACHE_STALE provenance labelling.

Weather observations are real and must never be invented; when neither the
network nor a cached reading is available, the caller reports that no weather
was applied rather than substituting a plausible-looking value. The
documented weather-impact model that turns an observation into a travel-time
multiplier lives in `realdata.traffic_model`, so there is exactly one place
where edge cost is assembled.
"""
from __future__ import annotations


def fetch_current_weather(*args, **kwargs):
    raise NotImplementedError(
        "Open-Meteo weather ingestion is implemented in Phase 8."
    )
