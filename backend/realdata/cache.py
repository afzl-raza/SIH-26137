"""On-disk cache for external data (geocoding, OSM extracts, weather).

Two jobs:

1. Stop hammering free public services. Nominatim and Overpass both have
   usage policies, and clicking "Generate" should not re-download a road
   network that has not changed.
2. Let the demo run with no internet. A cached extract is served when the
   network is unavailable - but it is *always* labelled as cached, never
   passed off as a fresh fetch.

Provenance is therefore part of the return value, not an implementation
detail. Every caller reports which of NETWORK / CACHE / CACHE_STALE / ERROR
it actually got, so the UI can never claim fresh data it did not fetch.

The cache root is configurable with the QDFRO_CACHE_DIR environment variable
and defaults to <repo_root>/.cache. Nothing secret is stored: entries hold
public geocoding, road and weather data only.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# --- provenance labels ---------------------------------------------------
# Used verbatim in API responses and in the UI, so they must stay honest.
SOURCE_NETWORK = "network"        # freshly fetched from the external service
SOURCE_CACHE = "cache"            # served from cache, still within TTL
SOURCE_CACHE_STALE = "cache-stale"  # served from cache past its TTL (offline)
SOURCE_ERROR = "error"            # nothing usable available

DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # road networks change slowly


def default_cache_root() -> Path:
    """<repo_root>/.cache unless QDFRO_CACHE_DIR overrides it."""
    env = os.environ.get("QDFRO_CACHE_DIR")
    if env:
        return Path(env)
    # backend/realdata/cache.py -> backend/realdata -> backend -> repo root
    return Path(__file__).resolve().parents[2] / ".cache"


def canonical_key(key: Dict[str, Any]) -> str:
    """Stable hash of a key dict.

    `sort_keys` plus a fixed separator means the same logical request always
    produces the same filename, regardless of dict ordering.
    """
    blob = json.dumps(key, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=16).hexdigest()


@dataclass
class CacheEntry:
    """A cache hit, with enough context for the caller to report provenance."""
    payload: Any
    cached_at: float
    key: Dict[str, Any]
    path: Path

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.cached_at)

    def is_stale(self, ttl_seconds: float) -> bool:
        return ttl_seconds > 0 and self.age_seconds > ttl_seconds


class DiskCache:
    """Namespaced JSON file cache.

    Each namespace gets its own subdirectory (`geocoding/`, `osm/`,
    `weather/`), so one namespace can be cleared without touching the others.
    """

    def __init__(
        self,
        root: Optional[Path] = None,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ):
        self.root = Path(root) if root is not None else default_cache_root()
        self.ttl_seconds = ttl_seconds

    def path_for(self, namespace: str, key: Dict[str, Any]) -> Path:
        return self.root / namespace / f"{canonical_key(key)}.json"

    def get(self, namespace: str, key: Dict[str, Any]) -> Optional[CacheEntry]:
        """Returns the entry if one exists, regardless of age.

        Staleness is the caller's decision: when the network is down, a stale
        entry is far better than no map at all - it just has to be labelled
        SOURCE_CACHE_STALE.
        """
        path = self.path_for(namespace, key)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return CacheEntry(
                payload=raw["payload"],
                cached_at=float(raw.get("cached_at", 0.0)),
                key=raw.get("key", key),
                path=path,
            )
        except (json.JSONDecodeError, KeyError, OSError, ValueError):
            # A corrupt or half-written entry must never break a request.
            return None

    def set(self, namespace: str, key: Dict[str, Any], payload: Any) -> Path:
        """Writes an entry atomically, so a crash mid-write cannot leave a
        truncated file that later reads would choke on."""
        path = self.path_for(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"cached_at": time.time(), "key": key, "payload": payload}

        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record), encoding="utf-8")
        os.replace(tmp, path)
        return path

    def delete(self, namespace: str, key: Dict[str, Any]) -> None:
        self.path_for(namespace, key).unlink(missing_ok=True)

    def clear(self, namespace: Optional[str] = None) -> int:
        """Removes every entry in one namespace, or in the whole cache.
        Returns how many files were deleted."""
        target = self.root / namespace if namespace else self.root
        if not target.exists():
            return 0
        removed = 0
        for path in target.rglob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed

    def entries(self, namespace: str) -> int:
        target = self.root / namespace
        if not target.exists():
            return 0
        return sum(1 for _ in target.glob("*.json"))


# Shared cache used by the real-data modules.
DISK_CACHE = DiskCache()
