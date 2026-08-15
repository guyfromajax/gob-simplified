"""Process-level cache of the universal ``plays`` catalog.

``plays`` is a small (~23 doc), universal, effectively read-only collection that the
sim consults on hot paths: canonical-name resolution, skeleton fetch by id, EV
lookups, shot-weight fetches. Every one of those was a Mongo round trip memoized
only *per game*, so each game re-paid the same lookups — measured at **45 reads /
2.4 s per game** on a non-colocated Atlas, the second-largest phase in a CPU game
after the turn loop itself. One load per process replaces all of them.

**Mutation contract.** Callers mutate what they get back — skeleton selection writes
``skeleton["_variant"]`` and ``skeleton["steps"]`` straight into the returned document
(`phase_resolution.get_skeleton_by_lean` → 10086, `_select_default_set_play_skeleton`
returns a live sub-dict). Today each game gets a fresh document from Mongo, so those
mutations cannot escape the game that made them. To preserve that exactly, every
function here that returns a **document** returns a deep copy (~0.4–1.7 ms, against
a ~48 ms round trip); only metadata answers (``name_exists``, ``name_for_id``) are
served from shared state, because a bool and a string cannot be mutated into the cache.
Do not "optimise" the copy away — sharing documents across games would make a game's
result depend on which games ran before it in the same worker, breaking the
determinism contract in `Sim_Perf_Capstone.md`.

**Loaded-ness is its own flag**, deliberately not ``if not _by_name``. An empty
catalog and an unloaded one must be distinguishable, or every lookup re-reads the
whole collection forever — correct output, silently catastrophic. That is exactly the
2026-08-12 ``defenses`` regression (60x, no error, no log line); an empty load here is
logged once at ERROR.

The only writer to the live collection is ``play_routes.delete_play``, which calls
``invalidate()``. Play authoring happens against a separate staging collection.
"""

from __future__ import annotations

import copy
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_loaded = False
_by_name: dict[str, dict] = {}
_by_id: dict[str, dict] = {}
_all: list[dict] = []


def _ensure_loaded() -> None:
    global _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        from BackEnd.db import plays_collection

        docs = list(plays_collection.find({}))
        by_name: dict[str, dict] = {}
        by_id: dict[str, dict] = {}
        for doc in docs:
            name = doc.get("name")
            if isinstance(name, str) and name:
                by_name.setdefault(name, doc)
            _id = doc.get("_id")
            if _id is not None:
                by_id.setdefault(str(_id), doc)

        _all[:] = docs
        _by_name.clear()
        _by_name.update(by_name)
        _by_id.clear()
        _by_id.update(by_id)
        _loaded = True

        if not docs:
            logger.error(
                "[PLAYS-CATALOG] loaded EMPTY — the plays collection has no documents. "
                "Every playcall will fall back to the legacy skeleton path. Check the database."
            )
        else:
            logger.info("[PLAYS-CATALOG] loaded %s plays", len(docs))


def invalidate() -> None:
    """Drop the cache so the next lookup reloads. Call after any write to ``plays``."""
    global _loaded
    with _lock:
        _loaded = False
        _by_name.clear()
        _by_id.clear()
        _all.clear()


def name_exists(name: Any) -> bool:
    """Whether a play with this exact ``name`` is in the universal collection."""
    if not isinstance(name, str) or not name:
        return False
    _ensure_loaded()
    return name in _by_name


def name_for_id(play_id: Any) -> Optional[str]:
    """The current ``plays.name`` for a play id, or None if the id is unknown."""
    if play_id is None:
        return None
    _ensure_loaded()
    doc = _by_id.get(str(play_id))
    name = doc.get("name") if doc else None
    return name if isinstance(name, str) and name else None


def doc_by_name(name: Any) -> Optional[dict]:
    """A private copy of the play document with this name, or None."""
    if not isinstance(name, str) or not name:
        return None
    _ensure_loaded()
    doc = _by_name.get(name)
    return copy.deepcopy(doc) if doc is not None else None


def doc_by_id(play_id: Any) -> Optional[dict]:
    """A private copy of the play document with this id, or None."""
    if play_id is None:
        return None
    _ensure_loaded()
    doc = _by_id.get(str(play_id))
    return copy.deepcopy(doc) if doc is not None else None


def all_docs() -> list[dict]:
    """Private copies of every play document."""
    _ensure_loaded()
    return copy.deepcopy(_all)
