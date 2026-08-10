"""Shared jersey-number assignment for signed recruits and walk-on roster makers.

Position ranges match week-35 signing. Conflict set = numbers already worn on the
team's active roster (non-graduating). Preference: ``position_intent``, then an
explicit ``pos`` string, then best RT position.
"""
from __future__ import annotations

import random
from typing import Any, Iterable, Mapping, Optional


def allowed_jersey_numbers(position: str) -> list[int]:
    pos = str(position or "").upper()
    if pos == "PG":
        return list(range(0, 37))
    if pos in {"SG", "SF"}:
        return list(range(0, 46)) + [77]
    return [number for number in range(0, 56) if number < 20 or number > 29] + [88, 91, 99]


def jersey_position_for_player(player: Mapping[str, Any]) -> str:
    """Resolve the position used for jersey pool selection."""
    intent = player.get("position_intent")
    if isinstance(intent, str) and intent.strip():
        return intent.strip().upper()
    meta = player.get("meta") if isinstance(player.get("meta"), Mapping) else {}
    meta_intent = meta.get("position_intent") if isinstance(meta, Mapping) else None
    if isinstance(meta_intent, str) and meta_intent.strip():
        return meta_intent.strip().upper()
    pos = player.get("pos")
    if isinstance(pos, str) and pos.strip() and pos.strip() != "--":
        return pos.strip().upper()
    ratings = player.get("position_ratings") or meta.get("position_ratings") or {}
    if isinstance(ratings, Mapping) and ratings:
        try:
            return max(
                ((k, v) for k, v in ratings.items() if isinstance(v, (int, float))),
                key=lambda kv: kv[1],
            )[0]
        except ValueError:
            pass
    return "SF"


def pick_jersey_number(
    position: str,
    taken: Iterable[Any],
    rng: Optional[random.Random] = None,
) -> int:
    """Pick a jersey from the position pool excluding ``taken``. Reuses full pool if empty."""
    chooser = rng.choice if rng is not None else random.choice
    taken_set: set[int] = set()
    for n in taken:
        try:
            taken_set.add(int(n))
        except (TypeError, ValueError):
            continue
    allowed = [n for n in allowed_jersey_numbers(position) if n not in taken_set]
    if not allowed:
        allowed = allowed_jersey_numbers(position)
    return int(chooser(allowed))
