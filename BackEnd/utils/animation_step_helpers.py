"""Shared helpers for animation step emitters.

Consolidates math + lookup helpers that multiple emitters (CR FB, RR FB,
HCT, HCO/skeleton, DREB) would otherwise duplicate. New emitters should
import from here; existing emitters (CR, RR) currently keep local copies
of the underlying helpers (``_safe_id``, ``_euclid``, etc.) and only
import the cross-cutting writers like ``stamp_tween_durations`` — full
consolidation of the older emitters is a separate cleanup pass.

Currently provides ``stamp_tween_durations`` — the per-player duration
computation that ensures fast-finishing players don't get their tweens
stretched across the gating player's step duration. See
``Animation_System_Updated.md`` for the schema field this writes.
"""

from typing import Any, Dict, Optional

from BackEnd.utils.animation_step_schema import GridCoord, PlayerArchetype


def _player_lookup_by_id(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    player_id: Optional[str],
) -> Optional[Any]:
    if not player_id:
        return None
    target = str(player_id)
    for lineup in (off_lineup, def_lineup):
        for player in lineup.values():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is not None and str(pid) == target:
                return player
    return None


def _euclid(a: GridCoord, b: GridCoord) -> float:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    return (dx * dx + dy * dy) ** 0.5


def _ag_grid_per_game_sec(player: Any, archetype: PlayerArchetype) -> float:
    """grid/game-sec rate for a player at a given archetype. AG curve
    anchored at AG=50 → 12, multiplied by archetype constant. See
    ``Animation_System_Updated.md`` — Cross-cutting invariants — AG curve.
    """
    try:
        from BackEnd.utils.shared import ag_to_grid_per_game_sec
        from BackEnd.constants import (
            DRIVE_MULTIPLIER,
            SHOT_MOTION_MULTIPLIER,
            SPRINT_MULTIPLIER,
        )
    except Exception:
        return 12.0

    if player is None:
        ag = 50
    else:
        attrs = getattr(player, "attributes", None) or {}
        ag = attrs.get("AG", 50) if isinstance(attrs, dict) else 50
    base_rate = float(ag_to_grid_per_game_sec(ag))
    if archetype == "drive":
        return base_rate * DRIVE_MULTIPLIER
    if archetype in ("shot_motion", "compressed_hco"):
        return base_rate * SHOT_MOTION_MULTIPLIER
    if archetype == "sprint":
        return base_rate * SPRINT_MULTIPLIER
    return base_rate


def stamp_tween_durations(
    start: Dict[str, Any],
    end_coords: Dict[str, GridCoord],
    step_t: float,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Stamp per-player tween durations (game-seconds) on
    ``start["tween_durations"]``. For each player who moves:
    ``duration = min(distance / rate, step_t)``. Stationary players omitted.

    Without this, the playback engine falls back to step T per player,
    which stretches fast finishers' tweens — the "lazy drift" anti-pattern.
    With this, each player tweens for their natural duration then idles at
    their end coord until step T elapses.
    """
    start_coords = start.get("coords") or {}
    archetype = start.get("archetype") or {}
    durations: Dict[str, float] = {}
    for pid, sc in start_coords.items():
        ec = end_coords.get(pid)
        if ec is None:
            continue
        dist = _euclid(sc, ec)
        if dist < 1e-6:
            continue
        arch = archetype.get(pid, "default")
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        if rate <= 0:
            continue
        durations[pid] = float(min(dist / rate, step_t))
    if durations:
        start["tween_durations"] = durations
