"""Content-addressed cache for RouteMatrix objects.

Each of the four optimizers used to build its own route matrix, so a single
/api/benchmark call built the identical matrix four times. This cache makes
that one build plus three hits.

Cache key
---------
The key is a hash of a canonical description of *everything that can change a
shortest-path result*:

  * the node set                      - graph identity
  * every directed edge, as
    (source, destination, current_travel_time, distance, traffic_factor)
  * the routing terminal set

`current_travel_time` is the Dijkstra edge weight, so it is what actually
decides routes; `distance` feeds the distance matrix. `traffic_factor` does not
influence the matrix on its own - it only matters through current_travel_time -
but it is included deliberately: over-invalidating is harmless, while serving a
stale matrix after an incident would be a correctness bug.

Keying on content rather than on a scenario id or Python object identity is
what makes the "no stale matrix after a traffic incident" guarantee hold: an
incident changes an edge's travel time, which changes the key, which misses.
"""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import Dict, List, Optional

from models import ProblemScenario
from problem_generator import RouteMatrix, compute_route_matrix, terminal_nodes

# A handful of entries is plenty: a session works on one scenario at a time,
# and we want the pre-incident and post-incident matrices to coexist.
DEFAULT_MAX_ENTRIES = 8


def _canonical_scenario_repr(scenario: ProblemScenario, terminals: List[int]) -> str:
    """Deterministic text description of the routing-relevant state.

    `repr()` on a float round-trips exactly in Python 3, so two structurally
    identical scenarios always produce byte-identical text.
    """
    parts: List[str] = ["v1"]

    parts.append("nodes:" + ",".join(str(n) for n in sorted(n.id for n in scenario.nodes)))
    parts.append("terminals:" + ",".join(str(t) for t in sorted(terminals)))

    edge_rows = sorted(
        (
            e.source,
            e.destination,
            repr(float(e.current_travel_time)),
            repr(float(e.distance)),
            repr(float(e.traffic_factor)),
        )
        for e in scenario.edges
    )
    parts.append("edges:" + ";".join(
        f"{s}>{d}:{ctt}:{dist}:{tf}" for s, d, ctt, dist, tf in edge_rows
    ))

    return "|".join(parts)


def route_matrix_key(scenario: ProblemScenario, terminals: Optional[List[int]] = None) -> str:
    """Deterministic cache key for a scenario's routing state."""
    if terminals is None:
        terminals = terminal_nodes(scenario)
    canonical = _canonical_scenario_repr(scenario, terminals)
    return hashlib.blake2b(canonical.encode("utf-8"), digest_size=16).hexdigest()


class RouteMatrixCache:
    """Thread-safe bounded LRU cache of RouteMatrix objects.

    A RouteMatrix is read-only once built, so handing the same instance to all
    four optimizers is safe - none of them mutate it.
    """

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES):
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._entries: "OrderedDict[str, RouteMatrix]" = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.builds = 0

    def get(
        self,
        scenario: ProblemScenario,
        terminals: Optional[List[int]] = None,
    ) -> RouteMatrix:
        if terminals is None:
            terminals = terminal_nodes(scenario)
        key = route_matrix_key(scenario, terminals)

        with self._lock:
            cached = self._entries.get(key)
            if cached is not None:
                self._entries.move_to_end(key)
                self.hits += 1
                return cached
            self.misses += 1

        # Built outside the lock: a large OSM matrix takes a while, and holding
        # the lock would serialize unrelated requests. A concurrent duplicate
        # build is possible but harmless - both produce the same matrix.
        matrix = compute_route_matrix(scenario, terminals=terminals)

        with self._lock:
            self.builds += 1
            self._entries[key] = matrix
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

        return matrix

    def invalidate(self, scenario: ProblemScenario, terminals: Optional[List[int]] = None) -> None:
        """Drops the entry for one specific routing state, if present.

        Not required for correctness - the key is content-addressed, so a
        changed scenario simply misses - but useful for explicit cleanup.
        """
        key = route_matrix_key(scenario, terminals)
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def reset_stats(self) -> None:
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.builds = 0

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "builds": self.builds,
                "entries": len(self._entries),
            }


# Module-level cache shared by all optimizers.
ROUTE_MATRIX_CACHE = RouteMatrixCache()


def get_route_matrix(
    scenario: ProblemScenario,
    terminals: Optional[List[int]] = None,
) -> RouteMatrix:
    """Cached entry point the optimizers call instead of compute_route_matrix."""
    return ROUTE_MATRIX_CACHE.get(scenario, terminals=terminals)
