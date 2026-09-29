"""OpenStreetMap road-network ingestion via the Overpass API.

Real road data, no synthesis. Given a bounded area from
`realdata.geocoding.resolve_location`, this module downloads the drivable
ways inside it and turns them into a directed road graph with real
coordinates, real distances, real one-way restrictions and real geometry.

There is no city table and no city-specific branch anywhere: the loader only
ever sees a bounding box, so "Lucknow", "London" and a raw coordinate pair
are literally the same code path.

Topology
--------
An OSM way is a polyline through many nodes, most of which are just shape
points rather than junctions. Keeping every one as a routing node would
inflate the graph enormously (in a sample 600 m extract, 818 OSM nodes but
only 168 shared junctions). So ways are split at *shared* nodes - the first
node, the last node, and any node used by more than one way - and the nodes
in between are retained as edge `geometry`. The routing graph stays small
while the map still gets the true road shape.

Distance is the sum of haversine lengths along that real geometry, so a
curving road is longer than the straight line between its endpoints, as it
should be.

What this module does NOT provide
---------------------------------
OSM has no traffic information. Every edge is created with
`traffic_factor = 1.0`, meaning free-flow. Congestion is applied separately
and is simulated; nothing here is a live traffic feed.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import networkx as nx

from .cache import (
    DISK_CACHE,
    DiskCache,
    SOURCE_CACHE,
    SOURCE_CACHE_STALE,
    SOURCE_NETWORK,
)
from .geocoding import BoundingBox, ResolvedLocation

# --- configuration -------------------------------------------------------

# Endpoints are configuration, not business logic. QDFRO_OVERPASS_URL may hold
# a single URL or a comma-separated list; they are tried in order. The public
# instances return 504 under load fairly often, so a fallback list is not
# optional in practice - the primary instance returned 504 twice during
# development before succeeding on retry.
DEFAULT_OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

# Drivable classes. Deliberately excludes footway, cycleway, path, steps,
# pedestrian, track and service: those are not general vehicle roads, and
# including them would invent routes a delivery vehicle cannot take.
DEFAULT_HIGHWAY_CLASSES = (
    "motorway", "motorway_link",
    "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "unclassified",
    "residential",
    "living_street",
)

# Bumped when parsing changes in a way that makes old cache entries wrong.
PARSER_VERSION = 1
CACHE_NAMESPACE = "osm"
OSM_TTL_SECONDS = 30 * 24 * 60 * 60  # road layouts change slowly

DEFAULT_TIMEOUT_S = 180.0
# Retries per endpoint before moving to the next mirror.
ATTEMPTS_PER_ENDPOINT = int(os.environ.get("QDFRO_OVERPASS_ATTEMPTS", 2))
RETRY_BACKOFF_S = float(os.environ.get("QDFRO_OVERPASS_BACKOFF_S", 2.0))
OVERPASS_QUERY_TIMEOUT_S = 120
MAX_BBOX_AREA_KM2 = float(os.environ.get("QDFRO_MAX_BBOX_AREA_KM2", 900.0))

EARTH_RADIUS_M = 6_371_000.0

# --- documented fallbacks ------------------------------------------------
# In the sampled real extract, 132 of 133 ways carried no maxspeed tag, so
# these fallbacks are the normal path rather than a rare edge case. They are
# ordinary urban defaults in km/h, deterministic, and never randomised.
SPEED_FALLBACK_KPH: Dict[str, float] = {
    "motorway": 90.0, "motorway_link": 45.0,
    "trunk": 70.0, "trunk_link": 40.0,
    "primary": 55.0, "primary_link": 35.0,
    "secondary": 45.0, "secondary_link": 30.0,
    "tertiary": 40.0, "tertiary_link": 30.0,
    "unclassified": 35.0,
    "residential": 30.0,
    "living_street": 15.0,
}
UNKNOWN_CLASS_SPEED_KPH = 30.0

# Lanes per direction when OSM does not say.
LANES_FALLBACK: Dict[str, int] = {
    "motorway": 2, "motorway_link": 1,
    "trunk": 2, "trunk_link": 1,
    "primary": 2, "primary_link": 1,
    "secondary": 2, "secondary_link": 1,
    "tertiary": 1, "tertiary_link": 1,
    "unclassified": 1,
    "residential": 1,
    "living_street": 1,
}
UNKNOWN_CLASS_LANES = 1

# Saturation-flow capacity per lane (veh/h), by road class. Used to derive an
# edge capacity for the later BPR traffic model; not used for routing here.
CAPACITY_PER_LANE_VPH: Dict[str, float] = {
    "motorway": 2000.0, "motorway_link": 1500.0,
    "trunk": 1800.0, "trunk_link": 1200.0,
    "primary": 1400.0, "primary_link": 1000.0,
    "secondary": 1200.0, "secondary_link": 900.0,
    "tertiary": 1000.0, "tertiary_link": 800.0,
    "unclassified": 800.0,
    "residential": 600.0,
    "living_street": 300.0,
}
UNKNOWN_CLASS_CAPACITY_VPH = 600.0

MPH_TO_KPH = 1.609344
KNOTS_TO_KPH = 1.852


class OsmLoaderError(RuntimeError):
    """Raised when a road network cannot be obtained from network or cache."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def polyline_length_m(points: Sequence[Tuple[float, float]]) -> float:
    """Length along a (lat, lon) polyline - the real road distance, not the
    straight line between its endpoints."""
    return sum(
        haversine_m(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])
        for i in range(len(points) - 1)
    )


# ------------------------------------------------------------ tag parsing

def parse_maxspeed(raw: Optional[str]) -> Optional[float]:
    """OSM maxspeed -> km/h, or None when no usable number is present.

    Handles the documented forms: a bare number (implicitly km/h), an explicit
    "km/h"/"kph" suffix, "mph", and "knots". Non-numeric values such as
    "none", "signals", "walk" or country codes like "IN:urban" carry no
    concrete limit and return None so the caller applies its class fallback.
    """
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None

    if text == "walk":
        return 5.0

    multiplier = 1.0
    for suffix, factor in (("mph", MPH_TO_KPH), ("knots", KNOTS_TO_KPH),
                           ("km/h", 1.0), ("kmh", 1.0), ("kph", 1.0)):
        if text.endswith(suffix):
            multiplier = factor
            text = text[: -len(suffix)].strip()
            break

    # A multi-value tag ("30;50") or a range: take the first number.
    for separator in (";", "-"):
        if separator in text:
            text = text.split(separator)[0].strip()

    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value * multiplier


def parse_lanes(raw: Optional[str]) -> Optional[int]:
    """OSM lanes -> int, or None. Values like "2;3" take the first entry."""
    if raw is None:
        return None
    text = str(raw).strip()
    if ";" in text:
        text = text.split(";")[0].strip()
    try:
        value = int(float(text))
    except ValueError:
        return None
    return value if value > 0 else None


def resolve_directions(tags: Dict[str, str], highway: str) -> Tuple[bool, bool]:
    """Returns (forward_allowed, backward_allowed) for a way.

    OSM one-way semantics, all documented cases:
      * "yes" / "1" / "true"  -> forward only
      * "-1" / "reverse"      -> backward only (the way is drawn against travel)
      * "no" / "0" / "false"  -> explicitly bidirectional
      * missing               -> bidirectional, EXCEPT where OSM convention
                                 makes one-way implicit: motorways,
                                 motorway_links, and roundabouts.

    Treating every untagged road as bidirectional would wrongly allow driving
    the wrong way up a motorway; treating every road as one-way would sever
    the network. Both mistakes are avoided explicitly rather than by default.
    """
    raw = str(tags.get("oneway", "")).strip().lower()

    if raw in ("yes", "1", "true"):
        return True, False
    if raw in ("-1", "reverse"):
        return False, True
    if raw in ("no", "0", "false"):
        return True, True

    junction = str(tags.get("junction", "")).strip().lower()
    if junction in ("roundabout", "circular"):
        return True, False
    if highway in ("motorway", "motorway_link"):
        return True, False

    return True, True


def speed_for(tags: Dict[str, str], highway: str) -> Tuple[float, str]:
    """(km/h, provenance). Provenance is 'osm_maxspeed' or 'fallback:<class>'."""
    parsed = parse_maxspeed(tags.get("maxspeed"))
    if parsed is not None:
        return parsed, "osm_maxspeed"
    return SPEED_FALLBACK_KPH.get(highway, UNKNOWN_CLASS_SPEED_KPH), f"fallback:{highway}"


def lanes_for(tags: Dict[str, str], highway: str) -> Tuple[int, str]:
    parsed = parse_lanes(tags.get("lanes"))
    if parsed is not None:
        return parsed, "osm_lanes"
    return LANES_FALLBACK.get(highway, UNKNOWN_CLASS_LANES), f"fallback:{highway}"


def capacity_for(highway: str, lanes: int) -> float:
    per_lane = CAPACITY_PER_LANE_VPH.get(highway, UNKNOWN_CLASS_CAPACITY_VPH)
    return per_lane * max(1, lanes)


# --------------------------------------------------------------- datatypes

@dataclass(frozen=True)
class OsmNode:
    osm_id: int
    lat: float
    lon: float


@dataclass
class OsmEdge:
    """One directed road segment between two junction nodes."""
    source: int              # OSM node id
    target: int              # OSM node id
    way_id: int
    highway: str
    name: str
    length_m: float
    speed_kph: float
    speed_source: str
    lanes: int
    lanes_source: str
    capacity_vph: float
    geometry: List[List[float]]  # [[lat, lon], ...] along the direction of travel

    @property
    def travel_time_minutes(self) -> float:
        """distance / speed, in minutes. Units kept explicit: metres and km/h
        in, minutes out, matching what ProblemScenario.Edge expects."""
        km = self.length_m / 1000.0
        return (km / max(1e-6, self.speed_kph)) * 60.0


@dataclass
class OsmRoadGraph:
    nodes: Dict[int, OsmNode]
    edges: List[OsmEdge]
    location: ResolvedLocation
    provenance: str = SOURCE_NETWORK
    retrieved_at: str = field(default_factory=_utc_now_iso)
    endpoint: str = ""
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_digraph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        for osm_id, node in self.nodes.items():
            g.add_node(osm_id, lat=node.lat, lon=node.lon)
        for edge in self.edges:
            # Parallel segments can occur between the same junction pair;
            # keep the shorter one, which is what a router would use.
            existing = g.get_edge_data(edge.source, edge.target)
            if existing is None or edge.length_m < existing["edge"].length_m:
                g.add_edge(edge.source, edge.target, edge=edge, weight=edge.length_m)
        return g


# ------------------------------------------------------------------ query

def build_overpass_query(
    bbox: BoundingBox,
    highway_classes: Sequence[str] = DEFAULT_HIGHWAY_CLASSES,
    timeout_s: int = OVERPASS_QUERY_TIMEOUT_S,
) -> str:
    """Bounded query for drivable ways.

    `out body geom` returns both the node id list and the coordinate list for
    each way, with matching lengths - the node ids are needed to detect shared
    junctions, the coordinates to measure real distance and keep geometry.
    """
    classes = "|".join(highway_classes)
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        f"(\n"
        f'  way["highway"~"^({classes})$"]["area"!~"yes"]'
        f"({bbox.to_overpass_bbox()});\n"
        f");\n"
        f"out body geom;\n"
    )


def bbox_area_km2(bbox: BoundingBox) -> float:
    mid_lat = (bbox.min_lat + bbox.max_lat) / 2.0
    height_km = (bbox.max_lat - bbox.min_lat) * 111.32
    width_km = (bbox.max_lon - bbox.min_lon) * 111.32 * math.cos(math.radians(mid_lat))
    return abs(height_km * width_km)


def overpass_endpoints() -> List[str]:
    configured = os.environ.get("QDFRO_OVERPASS_URL", "").strip()
    if configured:
        return [u.strip() for u in configured.split(",") if u.strip()]
    return list(DEFAULT_OVERPASS_ENDPOINTS)


def _http_post_overpass(url: str, query: str, timeout_s: float) -> Any:
    """Default transport. Imported lazily so this module stays importable and
    testable without httpx present."""
    import httpx

    from .geocoding import DEFAULT_USER_AGENT

    response = httpx.post(
        url,
        data={"data": query},
        timeout=httpx.Timeout(timeout_s, connect=20.0),
        headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
    )
    response.raise_for_status()
    return response.json()


PostOverpass = Callable[[str, str, float], Any]


# ------------------------------------------------------------------ parse

def parse_overpass_response(
    payload: Dict[str, Any],
    highway_classes: Sequence[str] = DEFAULT_HIGHWAY_CLASSES,
) -> Tuple[Dict[int, OsmNode], List[OsmEdge], Dict[str, Any]]:
    """Overpass JSON -> (junction nodes, directed edges, stats).

    Ways are split at shared nodes; intermediate nodes survive as geometry.
    """
    allowed = set(highway_classes)
    ways = [
        element for element in payload.get("elements", [])
        if element.get("type") == "way"
        and (element.get("tags") or {}).get("highway") in allowed
        and element.get("nodes")
        and element.get("geometry")
    ]

    # How many ways use each node? A node used more than once is a junction.
    usage: Dict[int, int] = {}
    for way in ways:
        for node_id in way["nodes"]:
            usage[node_id] = usage.get(node_id, 0) + 1

    nodes: Dict[int, OsmNode] = {}
    edges: List[OsmEdge] = []
    skipped_ways = 0
    oneway_forward = oneway_reverse = bidirectional = 0
    speed_from_osm = 0

    for way in ways:
        tags = way.get("tags") or {}
        node_ids: List[int] = way["nodes"]
        geometry = way["geometry"]

        # Overpass returns these in parallel; if a way is clipped by the bbox
        # the lists can disagree, in which case the way is unusable.
        if len(node_ids) != len(geometry) or len(node_ids) < 2:
            skipped_ways += 1
            continue

        highway = tags["highway"]
        name = tags.get("name", "")
        way_id = int(way["id"])
        forward_ok, backward_ok = resolve_directions(tags, highway)
        speed_kph, speed_source = speed_for(tags, highway)
        lane_count, lanes_source = lanes_for(tags, highway)
        capacity = capacity_for(highway, lane_count)

        if speed_source == "osm_maxspeed":
            speed_from_osm += 1
        if forward_ok and backward_ok:
            bidirectional += 1
        elif forward_ok:
            oneway_forward += 1
        else:
            oneway_reverse += 1

        points = [(float(p["lat"]), float(p["lon"])) for p in geometry]

        # Split indices: endpoints plus every shared node.
        split_at = [
            i for i, node_id in enumerate(node_ids)
            if i == 0 or i == len(node_ids) - 1 or usage.get(node_id, 0) > 1
        ]

        for start, end in zip(split_at[:-1], split_at[1:]):
            if end <= start:
                continue
            segment_points = points[start:end + 1]
            source_id, target_id = node_ids[start], node_ids[end]
            if source_id == target_id:
                continue  # closed loop segment, not routable between junctions

            length_m = polyline_length_m(segment_points)
            if length_m <= 0.0:
                continue

            nodes[source_id] = OsmNode(source_id, *segment_points[0])
            nodes[target_id] = OsmNode(target_id, *segment_points[-1])

            forward_geometry = [[lat, lon] for lat, lon in segment_points]

            if forward_ok:
                edges.append(OsmEdge(
                    source=source_id, target=target_id, way_id=way_id,
                    highway=highway, name=name, length_m=length_m,
                    speed_kph=speed_kph, speed_source=speed_source,
                    lanes=lane_count, lanes_source=lanes_source,
                    capacity_vph=capacity, geometry=forward_geometry,
                ))
            if backward_ok:
                edges.append(OsmEdge(
                    source=target_id, target=source_id, way_id=way_id,
                    highway=highway, name=name, length_m=length_m,
                    speed_kph=speed_kph, speed_source=speed_source,
                    lanes=lane_count, lanes_source=lanes_source,
                    capacity_vph=capacity,
                    geometry=list(reversed(forward_geometry)),
                ))

    stats = {
        "ways_considered": len(ways),
        "ways_skipped": skipped_ways,
        "junction_nodes": len(nodes),
        "directed_edges": len(edges),
        "oneway_forward": oneway_forward,
        "oneway_reverse": oneway_reverse,
        "bidirectional": bidirectional,
        "ways_with_osm_maxspeed": speed_from_osm,
        "ways_using_speed_fallback": len(ways) - speed_from_osm,
    }
    return nodes, edges, stats


def largest_routable_component(
    nodes: Dict[int, OsmNode],
    edges: List[OsmEdge],
) -> Tuple[Dict[int, OsmNode], List[OsmEdge], Dict[str, Any]]:
    """Restricts the graph to its largest strongly connected component.

    Strong, not weak, connectivity: with one-way roads a weakly connected
    graph can still contain nodes a vehicle can reach but never leave. Every
    terminal must be able to reach every other terminal *and* return to the
    depot, which is exactly what an SCC guarantees.

    Components are compared by size and ties broken on the smallest node id,
    so the choice is deterministic across runs. Disconnected fragments are
    dropped, never stitched together with invented roads.
    """
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes.keys())
    for edge in edges:
        graph.add_edge(edge.source, edge.target)

    components = list(nx.strongly_connected_components(graph))
    if not components:
        return {}, [], {"components": 0, "kept_nodes": 0, "dropped_nodes": len(nodes)}

    best = max(components, key=lambda c: (len(c), -min(c)))
    kept_nodes = {nid: node for nid, node in nodes.items() if nid in best}
    kept_edges = [e for e in edges if e.source in best and e.target in best]

    stats = {
        "components": len(components),
        "kept_nodes": len(kept_nodes),
        "dropped_nodes": len(nodes) - len(kept_nodes),
        "kept_edges": len(kept_edges),
        "dropped_edges": len(edges) - len(kept_edges),
    }
    return kept_nodes, kept_edges, stats


# ------------------------------------------------------------------- load

def _cache_key(bbox: BoundingBox, highway_classes: Sequence[str]) -> Dict[str, Any]:
    """Keyed on everything that changes the result: the area, the road filter
    and the parser version."""
    return {
        "bbox": [round(v, 6) for v in
                 (bbox.min_lat, bbox.min_lon, bbox.max_lat, bbox.max_lon)],
        "highway": sorted(highway_classes),
        "parser_version": PARSER_VERSION,
    }


def load_osm_graph(
    location: ResolvedLocation,
    *,
    highway_classes: Sequence[str] = DEFAULT_HIGHWAY_CLASSES,
    cache: Optional[DiskCache] = None,
    post_overpass: Optional[PostOverpass] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    endpoints: Optional[Sequence[str]] = None,
    force_refresh: bool = False,
) -> OsmRoadGraph:
    """Downloads (or serves from cache) the road network inside `location`.

    Order of preference: fresh cache, then network, then stale cache. When
    neither the network nor any cached extract is available this raises -
    it never silently substitutes synthetic roads, because a fabricated
    network presented as OSM data would be exactly the kind of claim this
    project must not make.
    """
    bbox = location.bbox
    area = bbox_area_km2(bbox)
    if area > MAX_BBOX_AREA_KM2:
        raise OsmLoaderError(
            f"Requested area is {area:.0f} km2, above the {MAX_BBOX_AREA_KM2:.0f} km2 "
            f"limit. Reduce radius_m or use a smaller bounding box."
        )

    cache = cache if cache is not None else DISK_CACHE
    post = post_overpass if post_overpass is not None else _http_post_overpass
    key = _cache_key(bbox, highway_classes)

    entry = None if force_refresh else cache.get(CACHE_NAMESPACE, key)
    if entry is not None and not entry.is_stale(OSM_TTL_SECONDS):
        return _graph_from_payload(
            entry.payload, location, highway_classes, SOURCE_CACHE, endpoint="cache")

    query = build_overpass_query(bbox, highway_classes)
    errors: List[str] = []
    for url in (endpoints if endpoints is not None else overpass_endpoints()):
        # Public Overpass instances return 504 under load often enough that a
        # single attempt is not reliable: during development the same query
        # failed on one attempt and succeeded moments later. One retry per
        # endpoint costs little and materially improves the odds.
        payload = None
        for attempt in range(ATTEMPTS_PER_ENDPOINT):
            try:
                payload = post(url, query, timeout_s)
                break
            except Exception as exc:
                errors.append(f"{url} (attempt {attempt + 1}): {type(exc).__name__}: {exc}")
                if attempt + 1 < ATTEMPTS_PER_ENDPOINT:
                    time.sleep(RETRY_BACKOFF_S)
        if payload is None:
            continue

        if not isinstance(payload, dict) or "elements" not in payload:
            errors.append(f"{url}: unexpected response shape")
            continue

        cache.set(CACHE_NAMESPACE, key, payload)
        return _graph_from_payload(
            payload, location, highway_classes, SOURCE_NETWORK, endpoint=url)

    # Every endpoint failed. A stale extract is far better than no map, as
    # long as it is labelled stale.
    if entry is not None:
        return _graph_from_payload(
            entry.payload, location, highway_classes, SOURCE_CACHE_STALE,
            endpoint="cache")

    raise OsmLoaderError(
        "Could not retrieve OpenStreetMap data and no cached extract is "
        "available for this area. Tried: " + "; ".join(errors or ["no endpoints"])
    )


def _graph_from_payload(
    payload: Dict[str, Any],
    location: ResolvedLocation,
    highway_classes: Sequence[str],
    provenance: str,
    endpoint: str,
) -> OsmRoadGraph:
    nodes, edges, stats = parse_overpass_response(payload, highway_classes)
    if not edges:
        raise OsmLoaderError(
            "No drivable roads were found in the requested area. Try a larger "
            "radius or a different location."
        )

    nodes, edges, component_stats = largest_routable_component(nodes, edges)
    if not edges:
        raise OsmLoaderError(
            "The road network in this area has no strongly connected component "
            "large enough to route on. Try a larger radius."
        )

    stats.update(component_stats)
    stats["total_length_km"] = round(sum(e.length_m for e in edges) / 1000.0, 3)

    return OsmRoadGraph(
        nodes=nodes,
        edges=edges,
        location=location,
        provenance=provenance,
        endpoint=endpoint,
        stats=stats,
    )
