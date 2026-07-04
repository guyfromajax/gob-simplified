"""Authoritative on-court coords for FB shot overlay / rebound logic.

UESS Rim Runner and Triangle emitters animate burst/setup payload geometry
while ``player.coords`` may still reflect the prior turn (DREB end state).
FB miss overlay maps and geo attemptor lists must use the same logical
positions the animation will render, not stale runtime coords.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _norm_player_id(pid: Any) -> Optional[str]:
    if pid is None:
        return None
    if hasattr(pid, "player_id"):
        raw = getattr(pid, "player_id", None)
        return str(raw) if raw is not None else None
    return str(pid) if pid else None


def _stamp_coord(
    out: Dict[str, Dict[str, float]],
    player_id: Any,
    coord: Any,
) -> None:
    pid = _norm_player_id(player_id)
    if not pid or not isinstance(coord, dict):
        return
    x, y = coord.get("x"), coord.get("y")
    if x is None or y is None:
        return
    out[pid] = {"x": float(x), "y": float(y)}


def _merge_triangle_setup_coords(
    out: Dict[str, Dict[str, float]],
    setup: Dict[str, Any],
) -> None:
    if not isinstance(setup, dict):
        return
    _stamp_coord(out, setup.get("ball_handler_id"), setup.get("ball_handler_to"))
    _stamp_coord(out, setup.get("rim_runner_id"), setup.get("rim_runner_to"))
    _stamp_coord(out, setup.get("trailer_id"), setup.get("trailer_to"))
    _stamp_coord(out, setup.get("same_side_corner_id"), setup.get("same_side_corner_to"))
    _stamp_coord(
        out,
        setup.get("opposite_side_corner_id"),
        setup.get("opposite_side_corner_to"),
    )
    _stamp_coord(out, setup.get("rr_defender_id"), setup.get("rr_defender_to"))
    _stamp_coord(out, setup.get("bh_defender_id"), setup.get("bh_defender_to"))
    for corner in setup.get("corner_players") or []:
        if isinstance(corner, dict):
            _stamp_coord(out, corner.get("player_id"), corner.get("to"))
    for helper in setup.get("helper_defenders") or []:
        if isinstance(helper, dict):
            _stamp_coord(out, helper.get("player_id"), helper.get("to"))


def _merge_burst_phase_coords(
    out: Dict[str, Dict[str, float]],
    burst: Dict[str, Any],
) -> None:
    if not isinstance(burst, dict):
        return
    _stamp_coord(out, burst.get("rr_id"), burst.get("rr_to"))
    _stamp_coord(out, burst.get("outlet_receiver_id"), burst.get("receiver_to"))
    _stamp_coord(out, burst.get("outlet_defender_id"), burst.get("outlet_defender_to"))
    for other in burst.get("other_players") or []:
        if not isinstance(other, dict):
            continue
        pid = other.get("player_id")
        if pid is None:
            continue
        if other.get("to_x") is not None and other.get("to_y") is not None:
            _stamp_coord(out, pid, {"x": other["to_x"], "y": other["to_y"]})


def _fill_from_lineups(
    out: Dict[str, Dict[str, float]],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Fallback: anyone not in the logical map keeps ``player.coords``."""
    for lineup in (off_lineup or {}, def_lineup or {}):
        for player in lineup.values():
            if player is None:
                continue
            pid = _norm_player_id(getattr(player, "player_id", None))
            if not pid or pid in out:
                continue
            coords = getattr(player, "coords", None) or {}
            if coords.get("x") is not None:
                out[pid] = {
                    "x": float(coords["x"]),
                    "y": float(coords.get("y", 25)),
                }


def build_fb_shot_logical_coords(
    roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    """Return ``{player_id: {x, y}}`` for FB overlay / rebound eligibility."""
    prebuilt = roles.get("fb_shot_logical_coords")
    if isinstance(prebuilt, dict) and prebuilt:
        return {str(k): dict(v) for k, v in prebuilt.items() if isinstance(v, dict)}

    out: Dict[str, Dict[str, float]] = {}

    setup = roles.get("triangle_setup_phase")
    if isinstance(setup, dict):
        _merge_triangle_setup_coords(out, setup)

    burst = roles.get("rim_runner_burst_phase")
    if isinstance(burst, dict):
        _merge_burst_phase_coords(out, burst)

    shot_spot = roles.get("shot_spot")
    shooter_id = _norm_player_id(roles.get("shooter"))
    if shooter_id and isinstance(shot_spot, dict):
        _stamp_coord(out, shooter_id, shot_spot)

    _fill_from_lineups(out, off_lineup, def_lineup)
    return out


def attach_fb_shot_overlay_context(
    shot_roles: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Merge FB geometry into ``shot_roles`` before ``ShotManager.resolve_shot``."""
    if not shot_roles.get("is_fast_break"):
        return
    for key in (
        "triangle_setup_phase",
        "rim_runner_burst_phase",
        "is_away_offense",
        "outlet_passer",
        "ball_handler",
        "shot_spot",
    ):
        if key in fb_roles and key not in shot_roles:
            shot_roles[key] = fb_roles[key]
    merged = {**fb_roles, **shot_roles}
    shot_roles["fb_shot_logical_coords"] = build_fb_shot_logical_coords(
        merged, off_lineup, def_lineup,
    )


def coords_for_fb_overlay_player(
    player: Any,
    logical_coords: Optional[Dict[str, Dict[str, float]]],
) -> Dict[str, float]:
    """Resolve coords for one player during FB overlay math."""
    pid = _norm_player_id(getattr(player, "player_id", None))
    if logical_coords and pid and pid in logical_coords:
        return dict(logical_coords[pid])
    runtime = getattr(player, "coords", None) or {}
    if runtime.get("x") is not None:
        return {
            "x": float(runtime["x"]),
            "y": float(runtime.get("y", 25)),
        }
    return {"x": 50.0, "y": 25.0}
