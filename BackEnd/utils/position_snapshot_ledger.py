"""
Position snapshot ledger — append-only snapshots for location-based gameplay (see
docs/docs_1_systems/00_General_Systems/Position_Checkpoints_and_Snapshot_Schema.md).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


SCHEMA_VERSION = 1


class PositionSnapshotLedger:
    """Append-only list of CourtPositionSnapshot dicts for the current resolution scope."""

    def __init__(self) -> None:
        self._snapshots: List[Dict[str, Any]] = []

    def append(self, snapshot: Dict[str, Any]) -> None:
        self._snapshots.append(snapshot)

    def snapshots(self) -> List[Dict[str, Any]]:
        return list(self._snapshots)

    def clear(self) -> None:
        self._snapshots.clear()


def collect_lineup_positions(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    """
    Build player_id -> {x, y} from both lineups using each player's current ``coords``.
    Missing coords default to (50, 25) to match sync fallbacks.
    """
    positions: Dict[str, Dict[str, float]] = {}
    for lineup in (off_lineup, def_lineup):
        if not lineup:
            continue
        for _pos, player in lineup.items():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is None:
                continue
            key = str(pid)
            c = getattr(player, "coords", None) or {}
            if not isinstance(c, dict):
                c = {}
            try:
                x = float(c.get("x", 50))
            except (TypeError, ValueError):
                x = 50.0
            try:
                y = float(c.get("y", 25))
            except (TypeError, ValueError):
                y = 25.0
            positions[key] = {"x": x, "y": y}
    return positions


def _possession_team_id(game: Any) -> Optional[str]:
    off_team = getattr(game, "offense_team", None)
    if off_team is not None and getattr(off_team, "team_id", None) is not None:
        return str(off_team.team_id)
    return None


def _ball_handler_id_from_roles(roles: Optional[Dict[str, Any]]) -> Optional[str]:
    if not roles:
        return None
    bh = roles.get("ball_handler")
    if bh is None:
        return None
    pid = getattr(bh, "player_id", None)
    return str(pid) if pid is not None else None


def _finalize_snapshot(
    checkpoint: Dict[str, Any],
    positions: Dict[str, Dict[str, float]],
    game: Any,
    roles: Optional[Dict[str, Any]],
    source: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "checkpoint": checkpoint,
        "positions": positions,
        "schema_version": SCHEMA_VERSION,
        "source": source,
    }
    bh = _ball_handler_id_from_roles(roles)
    if bh is not None:
        out["ball_handler_id"] = bh
    pt = _possession_team_id(game)
    if pt is not None:
        out["possession_team_id"] = pt
    return out


def build_skeleton_pre_resolve_shot_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    skeleton: Optional[Dict[str, Any]],
    roles: Optional[Dict[str, Any]],
    turn_type: str,
    source: str,
) -> Dict[str, Any]:
    """
    Snapshot immediately before ``resolve_shot`` after skeleton-driven coord sync
    (HCO, FCP, HCT, Final Turn, shot-clock forced shot).
    """
    steps = (skeleton or {}).get("steps") or []
    step_count = len(steps)
    step_index = max(0, step_count - 1) if step_count else 0
    positions = collect_lineup_positions(off_lineup, def_lineup)
    checkpoint: Dict[str, Any] = {
        "turn_type": turn_type,
        "checkpoint_kind": "skeleton_step",
        "step_index": step_index,
        "step_count": step_count,
        "label": "pre_resolve_shot",
    }
    return _finalize_snapshot(checkpoint, positions, game, roles, source)


def build_hco_pre_resolve_shot_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    skeleton: Optional[Dict[str, Any]],
    roles: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """HCO half-court shot path (``resolve_half_court_offense_logic``)."""
    return build_skeleton_pre_resolve_shot_snapshot(
        game, off_lineup, def_lineup, skeleton, roles, "HCO", "hco_pre_resolve_shot"
    )


def build_phase_post_stopper_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    skeleton: Optional[Dict[str, Any]],
    roles: Optional[Dict[str, Any]],
    turn_type: str,
    outcome_kind: str,
    source: str,
) -> Dict[str, Any]:
    """
    After stopper-animated non-shot outcomes (turnover or non-shooting foul).
    Callers should run ``apply_coords_from_animations_list`` first when animations exist.

    outcome_kind: turnover or non_shooting_foul.

    turn_type: HCO, FCP, HCT, or FAST_BREAK (skeleton may be None on FB path).
    """
    positions = collect_lineup_positions(off_lineup, def_lineup)
    if turn_type == "FAST_BREAK":
        checkpoint: Dict[str, Any] = {
            "turn_type": "FAST_BREAK",
            "checkpoint_kind": "custom",
            "custom_id": f"fb_{outcome_kind}",
            "label": "post_stopper_animation",
            "outcome_kind": outcome_kind,
        }
    else:
        steps = (skeleton or {}).get("steps") or []
        step_count = len(steps)
        step_index = max(0, step_count - 1) if step_count else 0
        checkpoint = {
            "turn_type": turn_type,
            "checkpoint_kind": "skeleton_step",
            "step_index": step_index,
            "step_count": step_count,
            "label": "post_stopper_animation",
            "outcome_kind": outcome_kind,
        }
    return _finalize_snapshot(checkpoint, positions, game, roles, source)


def build_fast_break_pre_shot_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    roles: Optional[Dict[str, Any]],
    fast_break_phase: str,
) -> Dict[str, Any]:
    """
    Fast break immediately before ``resolve_shot`` (standard FB or Rim Runner).
    ``fast_break_phase``: e.g. ``fb_logic_pre_shot``, ``fb_rr_pre_shot`` (see schema doc §6.2).
    """
    positions = collect_lineup_positions(off_lineup, def_lineup)
    checkpoint: Dict[str, Any] = {
        "turn_type": "FAST_BREAK",
        "checkpoint_kind": "fast_break_phase",
        "phase": fast_break_phase,
        "label": "pre_resolve_shot",
    }
    return _finalize_snapshot(checkpoint, positions, game, roles, fast_break_phase)


def build_free_throw_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    shooter: Any,
) -> Dict[str, Any]:
    """After FT animation build; uses current ``Player.coords`` on the floor."""
    positions = collect_lineup_positions(off_lineup, def_lineup)
    roles = {"ball_handler": shooter}
    checkpoint: Dict[str, Any] = {
        "turn_type": "FREE_THROW",
        "checkpoint_kind": "custom",
        "custom_id": "ft_attempt",
        "label": "free_throw_attempt",
    }
    return _finalize_snapshot(checkpoint, positions, game, roles, "free_throw_attempt")


def build_oreb_putback_attempt_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, Any]:
    """OREB putback path before putback make/miss resolution (``resolve_offensive_rebound`` putback branch)."""
    positions = collect_lineup_positions(off_lineup, def_lineup)
    checkpoint: Dict[str, Any] = {
        "turn_type": "OREB",
        "checkpoint_kind": "custom",
        "custom_id": "oreb_putback_attempt",
        "label": "oreb_putback_attempt",
    }
    return _finalize_snapshot(checkpoint, positions, game, None, "oreb_putback_attempt")


def build_oreb_kickout_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, Any]:
    """OREB kickout reset (``resolve_offensive_rebound`` kickout branch)."""
    positions = collect_lineup_positions(off_lineup, def_lineup)
    checkpoint: Dict[str, Any] = {
        "turn_type": "OREB",
        "checkpoint_kind": "custom",
        "custom_id": "oreb_kickout_reset",
        "label": "oreb_kickout_reset",
    }
    return _finalize_snapshot(checkpoint, positions, game, None, "oreb_kickout_reset")


def build_positions_from_destinations(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    o_dest: Dict[str, Any],
    d_dest: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    """Map slot destinations (oDestinations / dDestinations) to player_id keys."""
    positions: Dict[str, Dict[str, float]] = {}
    for pos, player in off_lineup.items():
        if player is None:
            continue
        pid = getattr(player, "player_id", None)
        if pid is None:
            continue
        key = str(pid)
        slot = o_dest.get(pos) if isinstance(o_dest, dict) else None
        if isinstance(slot, dict) and slot.get("x") is not None and slot.get("y") is not None:
            try:
                positions[key] = {"x": float(slot["x"]), "y": float(slot["y"])}
                continue
            except (TypeError, ValueError):
                pass
        c = getattr(player, "coords", None) or {}
        positions[key] = {
            "x": float(c.get("x", 50)) if isinstance(c, dict) else 50.0,
            "y": float(c.get("y", 25)) if isinstance(c, dict) else 25.0,
        }
    for pos, player in def_lineup.items():
        if player is None:
            continue
        pid = getattr(player, "player_id", None)
        if pid is None:
            continue
        key = str(pid)
        slot = d_dest.get(pos) if isinstance(d_dest, dict) else None
        if isinstance(slot, dict) and slot.get("x") is not None and slot.get("y") is not None:
            try:
                positions[key] = {"x": float(slot["x"]), "y": float(slot["y"])}
                continue
            except (TypeError, ValueError):
                pass
        c = getattr(player, "coords", None) or {}
        positions[key] = {
            "x": float(c.get("x", 50)) if isinstance(c, dict) else 50.0,
            "y": float(c.get("y", 25)) if isinstance(c, dict) else 25.0,
        }
    return positions


def build_inbound_destinations_snapshot(
    game: Any,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    o_dest: Dict[str, Any],
    d_dest: Dict[str, Any],
    turn_type: str,
    source: str,
) -> Dict[str, Any]:
    """
    ``turn_type``: ``SIDE_INBOUND`` or ``BASELINE_INBOUND`` (and quarter-start BIP uses BASELINE_INBOUND).
    Positions derived from oDestinations/dDestinations for the inbound turn payload.
    """
    positions = build_positions_from_destinations(off_lineup, def_lineup, o_dest, d_dest)
    checkpoint: Dict[str, Any] = {
        "turn_type": turn_type,
        "checkpoint_kind": "custom",
        "custom_id": "inbound_destinations",
        "label": "inbound_setup",
    }
    return _finalize_snapshot(checkpoint, positions, game, None, source)


def build_opening_tip_snapshot_from_animations(
    game: Any,
    animations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Derive player positions from opening-tip animation rows (``end``, else ``jumpCoords`` for
    centers, else ``start``). Matches ``BackEnd/utils/opening_tip.py`` payload shape.
    """
    positions: Dict[str, Dict[str, float]] = {}
    for anim in animations:
        if not isinstance(anim, dict):
            continue
        pid = anim.get("playerId")
        if pid is None:
            continue
        key = str(pid)
        xy: Optional[Dict[str, float]] = None
        if isinstance(anim.get("end"), dict):
            e = anim["end"]
            xy = {"x": float(e.get("x", 50)), "y": float(e.get("y", 25))}
        elif isinstance(anim.get("jumpCoords"), dict):
            j = anim["jumpCoords"]
            xy = {"x": float(j.get("x", 50)), "y": float(j.get("y", 25))}
        elif isinstance(anim.get("start"), dict):
            s = anim["start"]
            xy = {"x": float(s.get("x", 50)), "y": float(s.get("y", 25))}
        if xy is not None:
            positions[key] = xy
    checkpoint: Dict[str, Any] = {
        "turn_type": "OPENING_TIP",
        "checkpoint_kind": "custom",
        "custom_id": "opening_tip",
        "label": "opening_tip_animation_finals",
    }
    out: Dict[str, Any] = {
        "checkpoint": checkpoint,
        "positions": positions,
        "schema_version": SCHEMA_VERSION,
        "source": "opening_tip",
    }
    pt = _possession_team_id(game)
    if pt is not None:
        out["possession_team_id"] = pt
    return out


def attach_position_snapshots(turn_result: Dict[str, Any], snapshots: List[Dict[str, Any]]) -> None:
    """Attach non-empty snapshot list to a turn result dict."""
    if snapshots:
        turn_result["position_snapshots"] = snapshots
