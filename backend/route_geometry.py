"""Resolves an optimizer's node path into the road geometry it actually follows.

Why this lives in the backend
-----------------------------
The optimizers already produce the complete road path: `VehicleRoute.node_path`
is the node-by-node Dijkstra path through the real graph (see
`problem_generator.compute_route_matrix` and `decoder.decode_random_keys`), not
just the ordered job list. What was missing was the *shape* of each hop.

That shape is already known - every OpenStreetMap edge carries the polyline it
was built from, including the intermediate shape points that were dropped from
the routing graph (`realdata.osm_loader` splits ways at shared junctions only).
So drawing a route on a real road network is a lookup, not a computation.

Doing that lookup here rather than in React is deliberate:

  * the frontend must never compute a route, and stitching geometry in the
    client is one refactor away from becoming exactly that;
  * the same edge-selection rule the router used has to be reproduced exactly
    (see `_edge_index` below), and there is only one place to keep it correct;
  * it is testable in the existing pytest suite, which the React code is not.

Nothing here invents a coordinate. Every point returned came either from an
OSM way's own geometry or from a scenario node's own position.

Synthetic scenarios
-------------------
A synthetic network has no geometry - its "roads" are straight lines between
generated points, which is what the map has always drawn. Those hops fall back
to the two endpoint coordinates and are labelled `straight-line`, so the UI can
state which kind of network it is showing instead of implying OSM fidelity it
does not have.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from models import Edge, ProblemScenario, VehicleRoute

# How a hop's shape was obtained. Reported per segment and aggregated per route.
GEOMETRY_OSM = "openstreetmap"       # the edge's own OSM way geometry
GEOMETRY_STRAIGHT = "straight-line"  # endpoint-to-endpoint (synthetic, or an
                                     # OSM edge that carried no geometry)
GEOMETRY_MIXED = "mixed"             # a route combining both
GEOMETRY_NONE = "none"               # nothing drawable (empty path)

EdgeKey = Tuple[int, int]


def _edge_index(scenario: ProblemScenario) -> Dict[EdgeKey, Edge]:
    """Directed (source, destination) -> the edge the router would have used.

    `problem_generator.build_routing_graph` adds every scenario edge to a
    `networkx.DiGraph`, so when a node pair has parallel edges the *last* one
    added is the one that ends up carrying the weight Dijkstra saw. This index
    resolves ties the same way, on purpose: picking a different parallel edge
    here would draw a road the optimizer did not actually cost.
    """
    index: Dict[EdgeKey, Edge] = {}
    for edge in scenario.edges:
        index[(edge.source, edge.destination)] = edge
    return index


def _node_index(scenario: ProblemScenario) -> Dict[int, Tuple[float, float]]:
    return {n.id: (float(n.lat), float(n.lng)) for n in scenario.nodes}


def _append_points(polyline: List[List[float]], points: Sequence[Sequence[float]]) -> None:
    """Appends `points`, dropping a leading duplicate of the current last point.

    Consecutive hops share a junction, and each edge's geometry includes both
    of its endpoints, so without this the shared node would be emitted twice.
    """
    for point in points:
        pair = [float(point[0]), float(point[1])]
        if polyline and polyline[-1] == pair:
            continue
        polyline.append(pair)


def segment_geometry(
    edge: Optional[Edge],
    start: Optional[Tuple[float, float]],
    end: Optional[Tuple[float, float]],
) -> Tuple[List[List[float]], str]:
    """One hop's shape, plus how it was obtained.

    Prefers the edge's real OSM polyline; falls back to the straight line
    between the two nodes when the edge has none (every synthetic edge, and any
    OSM edge whose geometry was not retained).
    """
    if edge is not None and edge.geometry and len(edge.geometry) >= 2:
        return [[float(p[0]), float(p[1])] for p in edge.geometry], GEOMETRY_OSM

    if start is not None and end is not None:
        return [[start[0], start[1]], [end[0], end[1]]], GEOMETRY_STRAIGHT

    return [], GEOMETRY_NONE


def _aggregate_source(sources: Iterable[str]) -> str:
    distinct = {s for s in sources if s != GEOMETRY_NONE}
    if not distinct:
        return GEOMETRY_NONE
    if len(distinct) == 1:
        return distinct.pop()
    return GEOMETRY_MIXED


def node_path_polyline(
    scenario: ProblemScenario,
    node_path: Sequence[int],
) -> Dict[str, object]:
    """Turns a node path into the polyline the vehicle actually drives.

    Returns the stitched `polyline`, the per-hop `segments` (kept so the map can
    highlight one road without a second request), and `geometry_source`.
    """
    edges = _edge_index(scenario)
    nodes = _node_index(scenario)

    polyline: List[List[float]] = []
    segments: List[Dict[str, object]] = []
    sources: List[str] = []

    for source_id, destination_id in zip(node_path[:-1], node_path[1:]):
        edge = edges.get((source_id, destination_id))
        points, origin = segment_geometry(
            edge, nodes.get(source_id), nodes.get(destination_id)
        )
        if not points:
            continue

        _append_points(polyline, points)
        sources.append(origin)
        segments.append({
            "source": source_id,
            "destination": destination_id,
            "geometry_source": origin,
            "point_count": len(points),
            "road_name": edge.road_name if edge is not None else "",
            "osm_way_id": edge.osm_way_id if edge is not None else None,
            "highway": edge.highway if edge is not None else None,
            "congestion_level": edge.congestion_level if edge is not None else None,
            "traffic_factor": edge.traffic_factor if edge is not None else None,
        })

    # A single-node path (a vehicle with no assigned jobs) still has a
    # position worth drawing; it just has no hops.
    if not polyline and node_path:
        only = nodes.get(node_path[0])
        if only is not None:
            polyline = [[only[0], only[1]]]

    return {
        "polyline": polyline,
        "segments": segments,
        "geometry_source": _aggregate_source(sources),
        "point_count": len(polyline),
        "node_count": len(node_path),
    }


def route_geometries(
    scenario: ProblemScenario,
    routes: Sequence[VehicleRoute],
) -> List[Dict[str, object]]:
    """Per-vehicle geometry for a whole optimization result."""
    resolved: List[Dict[str, object]] = []
    for route in routes:
        payload = node_path_polyline(scenario, route.node_path)
        payload["vehicle_id"] = route.vehicle_id
        resolved.append(payload)
    return resolved


def edge_polylines(scenario: ProblemScenario) -> List[Dict[str, object]]:
    """Drawable shape for every edge in the network.

    Offered for completeness - the map reads `Edge.geometry` straight off the
    scenario it already holds, so this is used by tests and by any client that
    wants the geometry without the rest of the edge record.
    """
    nodes = _node_index(scenario)
    out: List[Dict[str, object]] = []
    for edge in scenario.edges:
        points, origin = segment_geometry(
            edge, nodes.get(edge.source), nodes.get(edge.destination)
        )
        out.append({
            "source": edge.source,
            "destination": edge.destination,
            "polyline": points,
            "geometry_source": origin,
            "congestion_level": edge.congestion_level,
            "traffic_factor": edge.traffic_factor,
            "road_name": edge.road_name,
        })
    return out


def scenario_geometry_source(scenario: ProblemScenario) -> str:
    """Whether this network's roads have real OSM shapes."""
    return _aggregate_source(
        GEOMETRY_OSM if (e.geometry and len(e.geometry) >= 2) else GEOMETRY_STRAIGHT
        for e in scenario.edges
    )


__all__ = [
    "GEOMETRY_MIXED",
    "GEOMETRY_NONE",
    "GEOMETRY_OSM",
    "GEOMETRY_STRAIGHT",
    "edge_polylines",
    "node_path_polyline",
    "route_geometries",
    "scenario_geometry_source",
    "segment_geometry",
]
