"""Server-side scenario store.

The frontend used to POST the entire ProblemScenario to /api/optimize,
/api/traffic/update, /api/benchmark and /api/evaluate on every interaction.
That is workable for a 30-node synthetic graph but not once scenarios carry
real OpenStreetMap geometry, so the backend now owns the scenario after
generation and clients refer to it by `scenario_id`.

Scope: this is an in-process, in-memory store for a single-process prototype
deployment. It is deliberately not a database - no persistence layer is being
introduced here. Nothing secret is ever stored: a ProblemScenario contains only
graph topology, jobs and vehicles.

Identity
--------
`scenario_hash` (from problem_generator.compute_scenario_hash) stays exactly
what it always was: a deterministic fingerprint of the *generation parameters*,
used as the user-visible "Run ID" and for replay. It is intentionally NOT used
on its own as the store key, because it is stable across two independent
generations with identical parameters - two clients would then share one slot
and one client's traffic incident would silently mutate the other's scenario.
A `scenario_id` is therefore the scenario hash plus a short random instance
suffix. No second hashing scheme is introduced; the hash itself is reused as-is.

Mutation
--------
`create()` and `update()` each store an independent copy (`models.clone_scenario`),
so a caller can never mutate stored state by holding on to the object it
passed in. `get()` returns the
stored object directly and callers must treat it as read-only - to change a
scenario, copy it, mutate the copy, and hand it back via `update()`.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from models import ProblemScenario, clone_scenario

# Six hours comfortably outlives any demo session while keeping a long-running
# server from accumulating scenarios indefinitely.
DEFAULT_TTL_SECONDS = 6 * 60 * 60
DEFAULT_MAX_ENTRIES = 64


class ScenarioNotFoundError(KeyError):
    """Raised when a scenario_id is unknown, expired or evicted."""


@dataclass
class ScenarioRecord:
    """A stored scenario plus the provenance the API reports back."""
    scenario_id: str
    scenario: ProblemScenario
    data_source: str
    created_at: float
    updated_at: float
    # Where this scenario's network came from geographically, as
    # `realdata.geocoding.ResolvedLocation.to_dict()` returned it. Present only
    # for OpenStreetMap scenarios - a synthetic network has no real location to
    # report, and inventing one would misstate the run's provenance. Kept on
    # the record rather than on the scenario so nothing about the optimizer's
    # input changes.
    location: Optional[dict] = None

    @property
    def scenario_hash(self) -> str:
        return self.scenario.scenario_hash

    def metadata(self) -> dict:
        """The envelope fields every scenario-aware endpoint reports."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_hash": self.scenario_hash,
            "data_source": self.data_source,
            "node_count": len(self.scenario.nodes),
            "edge_count": len(self.scenario.edges),
            "job_count": len(self.scenario.jobs),
            "vehicle_count": len(self.scenario.vehicles),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ScenarioStore:
    """Thread-safe in-memory scenario store with TTL and a size cap.

    FastAPI runs `def` (non-async) endpoints in a worker threadpool, so several
    requests really can touch the store concurrently - hence the lock rather
    than relying on the GIL plus dict atomicity.
    """

    def __init__(
        self,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.time,
    ):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._lock = threading.RLock()
        self._records: Dict[str, ScenarioRecord] = {}
        # Injectable so tests can drive expiry with a fake clock instead of
        # real sleep() calls, which are inherently flaky under full-suite
        # load (GC/scheduler pauses can alone exceed a tight TTL). Defaults
        # to the real wall clock, so production behaviour is unchanged.
        self._clock = clock

    # ------------------------------------------------------------ internals

    def _new_id(self, scenario: ProblemScenario) -> str:
        """`<scenario_hash>-<random suffix>`: keeps the reproducible hash
        visible in the id while keeping concurrent sessions isolated."""
        base = scenario.scenario_hash or "scenario"
        return f"{base}-{secrets.token_hex(4)}"

    def _evict_locked(self, now: float) -> None:
        expired = [
            sid for sid, rec in self._records.items()
            if self._ttl > 0 and (now - rec.updated_at) > self._ttl
        ]
        for sid in expired:
            del self._records[sid]

        # Size cap: drop least-recently-updated entries first.
        overflow = len(self._records) - self._max_entries
        if overflow > 0:
            oldest = sorted(self._records.items(), key=lambda kv: kv[1].updated_at)
            for sid, _ in oldest[:overflow]:
                del self._records[sid]

    # ---------------------------------------------------------------- public

    def create(
        self,
        scenario: ProblemScenario,
        data_source: str = "synthetic",
        location: Optional[dict] = None,
    ) -> ScenarioRecord:
        """Stores a deep copy of `scenario` under a fresh id."""
        now = self._clock()
        with self._lock:
            self._evict_locked(now)
            scenario_id = self._new_id(scenario)
            while scenario_id in self._records:  # astronomically unlikely
                scenario_id = self._new_id(scenario)
            record = ScenarioRecord(
                scenario_id=scenario_id,
                scenario=clone_scenario(scenario),
                data_source=data_source,
                created_at=now,
                updated_at=now,
                location=dict(location) if location else None,
            )
            self._records[scenario_id] = record
            # Evict again *after* inserting: the pre-insert sweep leaves room
            # for the new record, so trimming only before it would allow the
            # store to settle at max_entries + 1.
            self._evict_locked(now)
            return record

    def get(self, scenario_id: str) -> ScenarioRecord:
        """Returns the stored record. The scenario it holds must be treated as
        read-only; mutate a copy and call `update()` instead.

        Raises ScenarioNotFoundError for unknown, expired or evicted ids.
        """
        now = self._clock()
        with self._lock:
            self._evict_locked(now)
            record = self._records.get(scenario_id)
            if record is None:
                raise ScenarioNotFoundError(scenario_id)
            return record

    def update(self, scenario_id: str, scenario: ProblemScenario) -> ScenarioRecord:
        """Replaces the scenario behind an existing id with a deep copy of
        `scenario`, preserving the id, data_source and creation time."""
        now = self._clock()
        with self._lock:
            record = self._records.get(scenario_id)
            if record is None:
                raise ScenarioNotFoundError(scenario_id)
            record.scenario = clone_scenario(scenario)
            record.updated_at = now
            return record

    def delete(self, scenario_id: str) -> None:
        with self._lock:
            self._records.pop(scenario_id, None)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def ids(self) -> List[str]:
        with self._lock:
            return list(self._records.keys())

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


# Module-level store used by the API layer.
SCENARIO_STORE = ScenarioStore()
