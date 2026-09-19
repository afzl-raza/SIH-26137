"""OpenStreetMap road-network ingestion via the Overpass API.

NOT YET IMPLEMENTED - this is Phase 4. The module exists now so the package
layout and the location contract are settled; nothing imports it as working
code and it is deliberately not re-exported from `realdata/__init__.py`.

Contract agreed for Phase 4
---------------------------
Input is a `ResolvedLocation` from `realdata.geocoding`, never a place name
directly: resolving "Lucknow" or "New York" to a bounded box is the
geocoder's job, and this module only ever sees a box. There is no city table
here and there must never be one.

    resolve_location(place="Lucknow", radius_m=3000)   # geocoding.py
        -> ResolvedLocation.bbox
        -> Overpass query for drivable ways inside that box
        -> directed road graph (one-way aware)

Planned output carries, per node: internal id, osm_id, lat, lon. Per edge:
source, destination, osm way id, distance, highway class, geometry, speed,
lanes, derived capacity, base travel time, current travel time, traffic
factor. Missing OSM attributes get documented per-highway-class fallbacks.

Results are cached through `realdata.cache` keyed on the bounding box and
network type, so the demo runs offline and Overpass is not re-queried on
every click.
"""
from __future__ import annotations


def load_osm_graph(*args, **kwargs):
    raise NotImplementedError(
        "OpenStreetMap ingestion is implemented in Phase 4. "
        "Use realdata.geocoding.resolve_location() to obtain a bounded area first."
    )
