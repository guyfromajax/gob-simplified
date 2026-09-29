"""Bounded in-memory cache of live GameManagers (``api.ongoing_games``).

A plain ``dict`` to its callers (``get``, ``[]``, ``in``, ``del``, ``pop``,
``keys``, ``len``, ``clear``). Each GameManager holds the full turn log
(~30-36 MB), so entries must not outlive their game:

- finished games are evicted explicitly (``evict_game``) once the final save
  has run;
- abandoned games (tab closed mid-game) are swept by an idle TTL and an LRU
  cap whenever a game is stored.

A swept mid-game entry recovers exactly like a server restart: the next
request misses the cache and the frontend resumes from the saved doc /
resume anchor.

One GameManager can sit under several keys (raw + normalized game id, see
simulate-quarter's ``_store_cached_game``); keys are aged and evicted per
GameManager, never one alias at a time.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Evict a game nobody has touched for this long (user abandoned it).
ONGOING_GAMES_IDLE_TTL_SECONDS = 2 * 60 * 60
# Max distinct GameManagers held; least-recently-touched are evicted beyond it.
ONGOING_GAMES_MAX_GAMES = 150


class LiveGameCache(dict):
    def __init__(
        self,
        idle_ttl_seconds: float = ONGOING_GAMES_IDLE_TTL_SECONDS,
        max_games: int = ONGOING_GAMES_MAX_GAMES,
        clock=time.monotonic,
    ):
        super().__init__()
        self.idle_ttl_seconds = idle_ttl_seconds
        self.max_games = max_games
        self._clock = clock
        self._touched: dict[Any, float] = {}
        self._lock = threading.RLock()

    # --- reads touch -------------------------------------------------------
    def __getitem__(self, key):
        value = super().__getitem__(key)
        self._touched[key] = self._clock()
        return value

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    # --- writes keep _touched in sync ---------------------------------------
    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)
            self._touched[key] = self._clock()
            self.sweep(keep=value)

    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)
            self._touched.pop(key, None)

    def pop(self, key, *default):
        with self._lock:
            self._touched.pop(key, None)
            return super().pop(key, *default)

    def clear(self):
        with self._lock:
            super().clear()
            self._touched.clear()

    # --- bounds -------------------------------------------------------------
    def _groups(self) -> list[tuple[Any, list, float]]:
        """(GameManager, keys, last_touch) per distinct GameManager."""
        now = self._clock()
        groups: dict[int, tuple[Any, list, float]] = {}
        for key, value in list(super().items()):
            touched = self._touched.setdefault(key, now)
            gm, keys, last = groups.get(id(value), (value, [], float("-inf")))
            keys.append(key)
            groups[id(value)] = (gm, keys, max(last, touched))
        return list(groups.values())

    def sweep(self, keep: Any = None) -> None:
        """Evict idle games, then the least recently used beyond the cap.

        ``keep`` (the GameManager just stored) is never evicted by the sweep.
        """
        with self._lock:
            now = self._clock()
            groups = [g for g in self._groups() if g[0] is not keep]
            live = []
            for gm, keys, last in groups:
                if now - last >= self.idle_ttl_seconds:
                    self._evict_keys(keys, "idle_ttl")
                else:
                    live.append((gm, keys, last))
            room = self.max_games - (1 if keep is not None else 0)
            if len(live) > room:
                live.sort(key=lambda g: g[2])
                for _gm, keys, _last in live[: len(live) - max(room, 0)]:
                    self._evict_keys(keys, "lru_cap")

    def _evict_keys(self, keys: Iterable, reason: str) -> None:
        # dict.pop, not super(): zero-arg super() inside a comprehension raises
        # TypeError on Python < 3.12 (comprehensions weren't inlined yet).
        removed = [k for k in keys if dict.pop(self, k, None) is not None]
        for k in keys:
            self._touched.pop(k, None)
        if removed:
            log_eviction(removed, reason, len(self))


def log_eviction(keys: Iterable, reason: str, remaining: int) -> None:
    logger.info(
        "[ONGOING-GAMES-EVICT] game_id=%s reason=%s remaining=%d",
        ",".join(str(k) for k in keys),
        reason,
        remaining,
    )


def evict_game(cache: dict, reason: str, *game_ids) -> list:
    """Remove a game (every key holding its GameManager) from ``cache``.

    Works on a plain dict too (tests monkeypatch ``api.ongoing_games``).
    Returns the keys removed; logs one INFO line when anything was removed.
    """
    ids = [g for g in dict.fromkeys(game_ids) if g is not None]
    gm = None
    for gid in ids:
        gm = dict.get(cache, gid)
        if gm is not None:
            break
    if gm is not None:
        ids += [k for k, v in list(dict.items(cache)) if v is gm and k not in ids]
    removed = [gid for gid in ids if cache.pop(gid, None) is not None]
    if removed:
        log_eviction(removed, reason, len(cache))
    return removed
