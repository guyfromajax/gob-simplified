"""Rim Runner Fast Break animation step emitter.

Converts a Rim Runner FB ``turn_result`` into the unified ``AnimationStep[]``
payload defined in ``BackEnd/utils/animation_step_schema.py``.

Rim Runner has five terminal branches. Steps 0–1 (Burst, Outlet pass) are
shared across four of them; outlet-denied forks at step 1.

- **Outlet → Shot Attempt** (MAKE / MISS / BLOCK / FOUL):
    step 0 burst → step 1 outlet pass → step 2 lane pass (BH → RR catch,
    "Fast Break!" announcement on step start) → step 3 shot motion
    (``turn_stop: SHOT_ATTEMPT``).
- **Outlet → STEAL**: step 0 → step 1 → step 2 lane pass intercepted
    ("Interception!" announcement, ``turn_stop: STEAL``).
- **Outlet → Bat OOB**: step 0 → step 1 → step 2 lane pass batted
    ("Out of bounds!" announcement, ``turn_stop: DEAD_BALL_TURNOVER``).
- **Outlet → Hold-up → HCO settle**: step 0 → step 1 → step 2 hold-up
    lead-in ("No Fast Break" announcement, implicit end → caller transitions
    to HCO).
- **Outlet Denied → HCO settle**: step 0 → step 1 defender close-out
    ("FB Outlet Pass Denied!" announcement) → step 2 receiver cutback +
    drift → step 3 recovery pass (implicit end → HCO).

Edge case: when rebounder == outlet receiver (``skip_outlet_pass == true``),
step 1 is skipped — the burst step chains directly to the branch's step 2
(or step 1 for outlet-denied).

Branch dispatch is keyed off ``turn_result``:

- ``rim_runner_outlet_failed`` (bool) → Outlet Denied branch.
- ``rim_runner_no_lane_pass`` (bool) → Hold-up branch.
- ``rim_runner_interception`` (bool) → STEAL branch.
- ``rim_runner_bat_oob`` (bool) → Bat OOB branch.
- otherwise (``result_type`` MAKE/MISS/BLOCK/FOUL) → Shot branch.

Triangle (next migration) drafts off the same burst + outlet pass steps,
so ``_build_burst_step`` and ``_build_outlet_pass_step`` are designed for
reuse by ``triangle_step_emitter.py``.

See ``_documentation_master/05_Animation_System/Advance_Triggers.md`` —
"Rim Runner" — for the per-step trigger spec.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    FB_OUTLET_QUALITY_THRESHOLD,
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY,
    FB_PASS_MIN_GAME_SECONDS,
    HOME_RIM_COORDS,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    Announcement,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
    StepEnd,
    StepStart,
)


# --- Vocabulary helpers ----------------------------------------------------


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _coord(obj: Any, fallback: Optional[GridCoord] = None) -> Optional[GridCoord]:
    if obj is None:
        return fallback
    coords = getattr(obj, "coords", None) if not isinstance(obj, dict) else obj
    if not coords or "x" not in coords or "y" not in coords:
        return fallback
    return {"x": float(coords["x"]), "y": float(coords["y"])}


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


def _all_player_start_coords(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> Dict[str, GridCoord]:
    """Per-player start coords for step 0. Reads ``player.coords`` for every
    player in both lineups; skips players without coords."""
    out: Dict[str, GridCoord] = {}
    for lineup in (off_lineup, def_lineup):
        for player in lineup.values():
            if player is None:
                continue
            pid = getattr(player, "player_id", None)
            if pid is None:
                continue
            c = _coord(player)
            if c is None:
                continue
            out[str(pid)] = c
    return out


def _euclid(a: GridCoord, b: GridCoord) -> float:
    dx = a["x"] - b["x"]
    dy = a["y"] - b["y"]
    return (dx * dx + dy * dy) ** 0.5


def _movement_end_coord(
    animations: List[Dict[str, Any]],
    player_id: str,
) -> Optional[GridCoord]:
    """Legacy animator's pre-computed end coord for a given player. Used by
    the shot-motion step to pick up shot-spot / defender-spot positions the
    legacy ``capture_fast_break_animation`` already resolved."""
    target = str(player_id)
    for anim in animations:
        if str(anim.get("playerId")) != target:
            continue
        movement = anim.get("movement") or []
        if not movement:
            return None
        last = movement[-1] or {}
        coords = last.get("coords") or {}
        if "x" not in coords or "y" not in coords:
            return None
        return {"x": float(coords["x"]), "y": float(coords["y"])}
    return None


def _is_offense_player(pid: str, off_lineup: Dict[str, Any]) -> bool:
    target = str(pid)
    for player in (off_lineup or {}).values():
        if player is None:
            continue
        if str(getattr(player, "player_id", "")) == target:
            return True
    return False


# --- AG-rate / interrupted-coord math ---------------------------------------


def _ag_grid_per_game_sec(player: Any, archetype: PlayerArchetype) -> float:
    """grid/game-sec rate for a player at a given archetype. Single AG curve
    (``rate = 9 + (AG/100) × 6``) anchored at AG=50 → 12, multiplied by the
    archetype constant. See ``Animation_System_Updated.md`` — Cross-cutting
    invariants — AG curve.
    """
    try:
        from BackEnd.utils.shared import ag_to_grid_per_game_sec
        from BackEnd.constants import (
            BURST_GRID_PER_GAME_SEC,
            CRUISE_GRID_PER_GAME_SEC,
            STANDARD_GRID_PER_GAME_SEC,
            SHOT_MOTION_GRID_PER_GAME_SEC,
            SPRINT_GRID_PER_GAME_SEC,
        )
    except Exception:
        return 12.0

    if player is None:
        ag = 50
    else:
        attrs = getattr(player, "attributes", None) or {}
        ag = attrs.get("AG", 50) if isinstance(attrs, dict) else 50
    ag_scale = float(ag_to_grid_per_game_sec(ag)) / float(STANDARD_GRID_PER_GAME_SEC)
    if archetype == "standard":
        return STANDARD_GRID_PER_GAME_SEC * ag_scale
    if archetype in ("shot_motion", "compressed_hco"):
        return SHOT_MOTION_GRID_PER_GAME_SEC * ag_scale
    if archetype == "sprint":
        return SPRINT_GRID_PER_GAME_SEC * ag_scale
    if archetype == "burst":
        return BURST_GRID_PER_GAME_SEC * ag_scale
    if archetype == "cruise":
        return CRUISE_GRID_PER_GAME_SEC * ag_scale
    return STANDARD_GRID_PER_GAME_SEC * ag_scale


def _traversal_seconds(start: GridCoord, end: GridCoord, rate: float) -> float:
    if rate <= 0:
        return 0.0
    return _euclid(start, end) / rate


def _interrupted_coord(
    start: Optional[GridCoord],
    target: Optional[GridCoord],
    rate: float,
    t: float,
) -> GridCoord:
    """Schema interrupted-coord math: position along start→target at
    ``rate × t``; clamped to ``target`` if the player can complete the
    traversal in ``t`` seconds."""
    if start is None and target is None:
        return {"x": 50.0, "y": 25.0}
    if start is None:
        return {"x": float(target["x"]), "y": float(target["y"])}
    if target is None:
        return {"x": float(start["x"]), "y": float(start["y"])}
    dist = _euclid(start, target)
    max_traversal = max(0.0, rate * t)
    if dist <= max_traversal or dist == 0.0:
        return {"x": float(target["x"]), "y": float(target["y"])}
    ratio = max_traversal / dist
    return {
        "x": float(start["x"] + (target["x"] - start["x"]) * ratio),
        "y": float(start["y"] + (target["y"] - start["y"]) * ratio),
    }


def _attacking_basket(is_away_offense: bool) -> GridCoord:
    rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
    return {"x": float(rim["x"]), "y": float(rim["y"])}


def _stamp_tween_durations(
    start: StepStart,
    end_coords: Dict[str, GridCoord],
    step_t: float,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> None:
    """Stamp per-player tween durations on ``start["tween_durations"]``
    (in game-seconds). For each player who moves: ``duration = min(distance
    / rate, step_t)``. Stationary players are omitted (no tween fires for
    zero-distance start→end anyway).

    Cross-cutting fix: without this, the playback engine falls back to step
    T for every player, which stretches fast-finishing players' tweens
    across the gating player's duration (the "lazy drift" anti-pattern).
    With this, each player tweens for their natural duration then idles at
    their end coord until step T elapses. See Animation_System_Updated.md.
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
        arch = archetype.get(pid, "standard")
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        if rate <= 0:
            continue
        durations[pid] = float(min(dist / rate, step_t))
    if durations:
        start["tween_durations"] = durations


# --- RR-specific geometry helpers ------------------------------------------


def _compute_interception_contact_grid(
    passer_coord: GridCoord,
    receiver_target: GridCoord,
) -> GridCoord:
    """Universal FB intercept / bat-OOB contact point. Mirrors the frontend
    helper ``resolveFbInterceptionContactGrid`` in ``fastBreak.js`` — keyed
    off the intended receiver pass target, with a ±3 grid offset on the
    side of the passer."""
    rx = float(receiver_target["x"])
    ry = float(receiver_target["y"])
    px = float(passer_coord["x"])
    py = float(passer_coord["y"])
    cx = rx + 3.0 if px > rx else rx - 3.0
    if py >= ry + 3.0:
        cy = ry + 3.0
    elif py <= ry - 3.0:
        cy = ry - 3.0
    else:
        cy = ry
    return {
        "x": float(max(0.0, min(100.0, cx))),
        "y": float(max(0.0, min(50.0, cy))),
    }


def _nearest_oob_grid(contact_coord: GridCoord) -> GridCoord:
    """Nearest sideline / baseline endpoint for a batted-OOB ball. Court
    bounds: x ∈ [0, 100], y ∈ [0, 50]."""
    cx = float(contact_coord["x"])
    cy = float(contact_coord["y"])
    distances = {
        "left": cx,
        "right": 100.0 - cx,
        "bottom": cy,
        "top": 50.0 - cy,
    }
    nearest = min(distances, key=distances.get)
    if nearest == "left":
        return {"x": 0.0, "y": cy}
    if nearest == "right":
        return {"x": 100.0, "y": cy}
    if nearest == "bottom":
        return {"x": cx, "y": 0.0}
    return {"x": cx, "y": 50.0}


# --- Announcement helpers --------------------------------------------------


def _decision_pill_meta(turn_result: Dict[str, Any]) -> Dict[str, str]:
    """RR decision-pill text + tone, mirroring the frontend
    ``getRimRunnerDecisionPillMeta`` so the backend stamps the pill explicitly
    rather than relying on the frontend to recompute it. Backend already
    stamps ``rim_runner_decision_good`` upstream via
    ``_apply_rr_decision_metadata``."""
    explicit_good = turn_result.get("rim_runner_decision_good")
    if isinstance(explicit_good, bool):
        is_good = explicit_good
    else:
        pass_attempted = bool(turn_result.get("rim_runner_pass_attempted"))
        fb_open = bool(turn_result.get("rim_runner_fb_open"))
        is_good = pass_attempted == fb_open
    return {
        "decisionPillText": "Good Decision" if is_good else "Bad Decision",
        "decisionPillTone": "good" if is_good else "bad",
    }


def _build_player_data(
    player: Any,
    fallback_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Headshot card payload for an Announcement. Frontend enriches from
    ``scene.playerInfo`` (photo, team color, jersey, etc.)."""
    pid = _safe_id(player) or (str(fallback_id) if fallback_id is not None else None)
    if pid is None:
        return None
    return {
        "playerId": pid,
        "photo": getattr(player, "photo", None) if player is not None else None,
        "teamName": None,
    }


def _fb_play_label(fb_play_key: Optional[str]) -> Optional[str]:
    """Human-readable subtitle for the "Fast Break!" announcement.
    Mirrors the frontend ``getFastBreakPlayLabel``."""
    if not fb_play_key:
        return None
    mapping = {
        "rim_runner": "Rim Runner",
        "triangle": "Triangle",
        "covert_release": "Covert Release",
        "after_steal": "After Steal",
    }
    return mapping.get(fb_play_key, fb_play_key.replace("_", " ").title())


# --- Reusable step builders (importable by Triangle) ------------------------


def _build_burst_step(
    *,
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    all_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> Optional[AnimationStep]:
    """Step 0: burst phase. All burst movers (RR, outlet receiver, outlet
    defender, ``other_players``) fire in parallel toward their burst targets.

    Gate: RR reaches ``rr_to``. T = RR traversal time at ``burst`` archetype.
    Other movers' end coords = ``rate × T`` along their path (interrupted-coord
    math); the receiver completes earlier and is clamped at ``receiver_to``
    so the outlet pass step starts with both RR and receiver settled at their
    burst endpoints.

    Reusable by Triangle's step emitter — Triangle's burst is identical to
    RR's; the divergence happens after the outlet pass.
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    rr_id = _safe_id(phase.get("rr_id"))
    receiver_id = _safe_id(phase.get("outlet_receiver_id"))
    passer_id = _safe_id(phase.get("outlet_passer_id"))
    defender_id = _safe_id(phase.get("outlet_defender_id"))
    receiver_to = phase.get("receiver_to") or {}
    rr_to = phase.get("rr_to") or {}
    defender_to = phase.get("outlet_defender_to")
    other_players = phase.get("other_players") or []

    if not rr_id or not receiver_id:
        import logging
        logging.warning(
            "🐛 [BURST_STEP_NONE] reason=missing_id rr_id=%s receiver_id=%s",
            rr_id, receiver_id,
        )
        return None
    if "x" not in receiver_to or "y" not in receiver_to:
        import logging
        logging.warning(
            "🐛 [BURST_STEP_NONE] reason=receiver_to_invalid receiver_to=%s",
            receiver_to,
        )
        return None
    if "x" not in rr_to or "y" not in rr_to:
        import logging
        logging.warning(
            "🐛 [BURST_STEP_NONE] reason=rr_to_invalid rr_to=%s",
            rr_to,
        )
        return None
    if rr_id not in all_start_coords or receiver_id not in all_start_coords:
        import logging
        logging.warning(
            "🐛 [BURST_STEP_NONE] reason=id_not_in_start_coords rr_id=%s receiver_id=%s start_keys=%s",
            rr_id, receiver_id, list(all_start_coords.keys()),
        )
        return None

    # Gate on RR reaching rr_to at burst rate. Receiver always reaches
    # receiver_to earlier (shorter distance, lower archetype) and clamps at
    # destination via _interrupted_coord.
    rr_start = all_start_coords[rr_id]
    rr_end_target: GridCoord = {
        "x": float(rr_to["x"]),
        "y": float(rr_to["y"]),
    }
    rr_archetype: PlayerArchetype = "burst"
    rr_player = _player_lookup_by_id(off_lineup, def_lineup, rr_id)
    rr_rate = _ag_grid_per_game_sec(rr_player, rr_archetype)
    t = max(0.1, _traversal_seconds(rr_start, rr_end_target, rr_rate))

    receiver_end_target: GridCoord = {
        "x": float(receiver_to["x"]),
        "y": float(receiver_to["y"]),
    }
    receiver_archetype: PlayerArchetype = "sprint"

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in all_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in all_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in all_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in all_start_coords.items()
    }

    def _commit_mover(
        pid: str,
        target: GridCoord,
        action: PlayerAction,
        arch: PlayerArchetype,
    ) -> None:
        if pid not in all_start_coords:
            return
        actions[pid] = action
        archetype[pid] = arch
        destinations[pid] = dict(target)
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, arch)
        end_coords[pid] = _interrupted_coord(
            all_start_coords[pid], target, rate, t
        )

    _commit_mover(rr_id, rr_end_target, "sprint", "burst")
    end_coords[rr_id] = dict(rr_end_target)

    _commit_mover(receiver_id, receiver_end_target, "cut", receiver_archetype)

    if passer_id and passer_id in all_start_coords:
        actions[passer_id] = "handle_ball"
        archetype[passer_id] = "stationary"

    if defender_id and defender_to and defender_id in all_start_coords:
        d_target: GridCoord = {
            "x": float(defender_to["x"]),
            "y": float(defender_to["y"]),
        }
        _commit_mover(defender_id, d_target, "guard_ball", "standard")

    getback_ids = {
        str(pid) for pid in (fb_roles.get("getback_player_ids") or []) if pid is not None
    }
    key_ids = {rr_id, receiver_id, passer_id, defender_id}
    for row in other_players:
        pid = _safe_id(row.get("player_id"))
        if not pid or pid in key_ids or pid not in all_start_coords:
            continue
        target: GridCoord = {
            "x": float(row.get("to_x", all_start_coords[pid]["x"])),
            "y": float(row.get("to_y", all_start_coords[pid]["y"])),
        }
        is_off = _is_offense_player(pid, off_lineup)
        action: PlayerAction = "cut" if is_off else "guard_offball"
        # Get-back defenders sprint back; other non-key movers default.
        arch: PlayerArchetype = "sprint" if pid in getback_ids else "standard"
        _commit_mover(pid, target, action, arch)

    skip_outlet_pass = bool(phase.get("skip_outlet_pass"))
    ball_owner = receiver_id if skip_outlet_pass else (passer_id or receiver_id)
    ball_start: BallState = {"owner_player_id": ball_owner}
    ball_end: BallState = {"owner_player_id": ball_owner}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": rr_id,
            "target_coords": dict(rr_end_target),
        },
    }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(all_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_outlet_pass_step(
    *,
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> Optional[AnimationStep]:
    """Step 1: outlet pass (rebounder → outlet receiver). Pass rate gated on
    outlet quality — sharp (``outlet_score >= 50``) flies at
    ``FB_PASS_GRID_SPOTS_PER_GAME_SECOND``; sloppy at hardcoded 22 grid/sec.
    Floored at 0.5 game-sec for very short passes.

    Per-player movement: passer / receiver stationary at their burst
    endpoints; all other movers continue toward their step 0 burst
    destinations (drift reads continuously through the pass).

    Reusable by Triangle. Caller skips this step entirely when
    ``skip_outlet_pass == true`` (rebounder == receiver).
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    passer_id = _safe_id(phase.get("outlet_passer_id"))
    receiver_id = _safe_id(phase.get("outlet_receiver_id"))
    if not passer_id or not receiver_id or passer_id == receiver_id:
        import logging
        logging.warning(
            "🐛 [OUTLET_PASS_STEP_NONE] reason=passer_receiver_invalid passer_id=%s receiver_id=%s skip_outlet_pass=%s",
            passer_id, receiver_id, phase.get("skip_outlet_pass"),
        )
        return None
    if passer_id not in step_start_coords or receiver_id not in step_start_coords:
        import logging
        logging.warning(
            "🐛 [OUTLET_PASS_STEP_NONE] reason=id_not_in_start_coords passer_id=%s receiver_id=%s",
            passer_id, receiver_id,
        )
        return None

    passer_coord = step_start_coords[passer_id]
    receiver_coord = step_start_coords[receiver_id]

    outlet_score = fb_roles.get("outlet_score")
    pass_rate = (
        float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND)
        if outlet_score is not None and outlet_score >= FB_OUTLET_QUALITY_THRESHOLD
        else float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY)
    )
    dist = _euclid(passer_coord, receiver_coord)
    t = max(FB_PASS_MIN_GAME_SECONDS, dist / pass_rate)

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    actions[passer_id] = "pass"
    actions[receiver_id] = "receive"

    rr_id = _safe_id(phase.get("rr_id"))
    defender_id = _safe_id(phase.get("outlet_defender_id"))
    other_targets: Dict[str, GridCoord] = {}
    if rr_id and isinstance(phase.get("rr_to"), dict):
        other_targets[rr_id] = {
            "x": float(phase["rr_to"]["x"]),
            "y": float(phase["rr_to"]["y"]),
        }
    if defender_id and isinstance(phase.get("outlet_defender_to"), dict):
        other_targets[defender_id] = {
            "x": float(phase["outlet_defender_to"]["x"]),
            "y": float(phase["outlet_defender_to"]["y"]),
        }
    for row in phase.get("other_players") or []:
        pid = _safe_id(row.get("player_id"))
        if not pid or pid in (passer_id, receiver_id):
            continue
        other_targets[pid] = {
            "x": float(row.get("to_x", step_start_coords.get(pid, {}).get("x", 50))),
            "y": float(row.get("to_y", step_start_coords.get(pid, {}).get("y", 25))),
        }

    for pid, target in other_targets.items():
        if pid not in step_start_coords:
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        if pid == rr_id:
            arch: PlayerArchetype = "sprint"
            action: PlayerAction = "sprint"
        elif pid == defender_id:
            arch = "standard"
            action = "guard_ball"
        else:
            arch = "standard"
            action = (
                "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
            )
        archetype[pid] = arch
        actions[pid] = action
        destinations[pid] = dict(target)
        rate = _ag_grid_per_game_sec(player, arch)
        end_coords[pid] = _interrupted_coord(step_start_coords[pid], target, rate, t)

    # Ball state continuity: step start = attached to passer (carries over from
    # the prior step's end.ball, which was the burst's BallAttached(passer)).
    # Step end = attached to receiver. Schema engine's renderBallTransition
    # detects the ownership change, detaches from passer's parent transform,
    # tweens world coords, and reattaches at end. Without this (i.e., starting
    # in_flight here) the detach never fires and the ball renders glued to
    # the passer's follow callback for the whole step — visible teleport.
    ball_start: BallState = {"owner_player_id": passer_id}
    ball_end: BallState = {"owner_player_id": receiver_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": passer_id,
            "to_player_id": receiver_id,
            "target_coords": dict(receiver_coord),
            "outlet_score": int(outlet_score) if outlet_score is not None else None,
        },
    }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


# --- Shot-outcome helpers --------------------------------------------------


def _ball_bounce_coords(turn_result: Dict[str, Any]) -> Optional[GridCoord]:
    bx = turn_result.get("ball_bounce_x")
    by = turn_result.get("ball_bounce_y")
    if bx is None or by is None:
        return None
    return {"x": float(bx), "y": float(by)}


def _resolve_shot_next(turn_result: Dict[str, Any]) -> NextStep:
    """``next`` pointer for the shot-motion terminal step."""
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type in ("MAKE", "MISS", "BLOCK"):
        return {
            "kind": "turn_stop",
            "event": "SHOT_ATTEMPT",
            "payload": {
                "result": result_type,
                "shooter_id": _safe_id(turn_result.get("shooter")),
                "defender_id": _safe_id(turn_result.get("defender")),
                "ball_bounce_coords": _ball_bounce_coords(turn_result),
            },
        }
    if result_type == "FOUL":
        return {
            "kind": "turn_stop",
            "event": "FOUL",
            "payload": {
                "foul_team": turn_result.get("foul_team"),
                "fouler_id": turn_result.get("foul_player_id"),
                "victim_id": turn_result.get("victim_id"),
            },
        }
    return {"kind": "next_step", "index": 999}


# --- Branch step builders: Shot branch -------------------------------------


def _build_lane_pass_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> Optional[AnimationStep]:
    """Shot branch step 2: lane pass (BH → RR catch).

    Gate: ball reaches RR at catch grid (RR.x_post_burst + 6 toward
    attacking basket, RR.y_post_burst). RR sprints to catch grid; ball
    flies passer → catch grid concurrently. Co-arrival at T.

    ``step.start.announcement = "Fast Break!"`` secondary, offense side,
    passer headshot, decision pill + FB play subtitle.
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    bh_id = _safe_id(phase.get("outlet_receiver_id"))
    rr_id = _safe_id(phase.get("rr_id"))
    if not bh_id or not rr_id or bh_id == rr_id:
        return None
    if bh_id not in step_start_coords or rr_id not in step_start_coords:
        return None

    bh_coord = step_start_coords[bh_id]
    rr_coord = step_start_coords[rr_id]
    x_dir = -1 if is_away_offense else 1
    catch_grid: GridCoord = {
        "x": float(max(4.0, min(97.0, rr_coord["x"] + 6 * x_dir))),
        "y": float(rr_coord["y"]),
    }

    rr_player = _player_lookup_by_id(off_lineup, def_lineup, rr_id)
    rr_rate = _ag_grid_per_game_sec(rr_player, "sprint")
    t = max(0.3, _traversal_seconds(rr_coord, catch_grid, rr_rate))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    actions[bh_id] = "pass"
    actions[rr_id] = "receive"
    archetype[rr_id] = "sprint"
    destinations[rr_id] = dict(catch_grid)
    end_coords[rr_id] = dict(catch_grid)

    # Ball state continuity (see _build_outlet_pass_step). BH had the ball
    # at end of step 1; lane pass is BallAttached(BH) → BallAttached(RR).
    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"owner_player_id": rr_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": bh_id,
            "to_player_id": rr_id,
            "target_coords": dict(catch_grid),
        },
    }

    bh_player = _player_lookup_by_id(off_lineup, def_lineup, bh_id)
    announcement: Announcement = {
        "text": "Fast Break!",
        "team": "away" if is_away_offense else "home",
        "player_data": _build_player_data(bh_player, fallback_id=bh_id),
        "meta": {
            **_decision_pill_meta(turn_result),
            "eventSubtitle": _fb_play_label(turn_result.get("fast_break_play")),
        },
        "hold_ms": 1000,
        "style": "secondary",
    }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
        "announcement": announcement,
        # FE pass-mode machinery: drives ball detach + tween at the
        # canonical pass grid/game-sec rate, and re-attaches to the
        # receiver on tween onComplete. Without this, the FE falls back
        # to using step T (RR's short sprint, ~0.3 game-sec) as the ball
        # duration — and since the passer is mid-court while catch_grid
        # is near the rim, the ball teleports across that distance in the
        # tiny step T window. See animationPlayback.js `isSchemaPassStep`
        # and the `ball_motion_style === "pass"` branches in
        # `renderBallTransition`.
        "ball_motion_style": "pass",
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_shot_motion_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    animations: List[Dict[str, Any]],
    step_start_coords: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> Optional[AnimationStep]:
    """Shot branch step 3: shot motion (RR → shot spot). Ends with
    ``turn_stop: SHOT_ATTEMPT``. Reads end coords from legacy
    ``animations[]`` since ``shot_manager`` has already computed shot spot
    + defender spot. Mirrors CR's outcome-step pattern.
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    rr_id = _safe_id(phase.get("rr_id"))
    if not rr_id or rr_id not in step_start_coords:
        return None

    end_coords: Dict[str, GridCoord] = {
        pid: dict(step_start_coords[pid]) for pid in step_start_coords
    }
    for pid in step_start_coords:
        anim_end = _movement_end_coord(animations, pid)
        if anim_end is not None:
            end_coords[pid] = anim_end

    rr_coord_start = step_start_coords[rr_id]
    rr_coord_end = end_coords.get(rr_id, rr_coord_start)
    rr_player = _player_lookup_by_id(off_lineup, def_lineup, rr_id)
    rr_rate = _ag_grid_per_game_sec(rr_player, "sprint")
    t = max(0.2, _traversal_seconds(rr_coord_start, rr_coord_end, rr_rate))

    defender_id = _safe_id(turn_result.get("defender") or fb_roles.get("defender"))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(end_coords.get(pid, step_start_coords[pid]))
        for pid in step_start_coords
    }

    actions[rr_id] = "shoot"
    archetype[rr_id] = "sprint"

    if defender_id and defender_id in step_start_coords:
        actions[defender_id] = "guard_ball"
        archetype[defender_id] = "sprint"

    for pid in step_start_coords:
        if pid in (rr_id, defender_id):
            continue
        if _movement_end_coord(animations, pid) is not None:
            if _is_offense_player(pid, off_lineup):
                actions[pid] = "cut"
                archetype[pid] = "standard"
            else:
                actions[pid] = "guard_offball"
                archetype[pid] = "standard"

    # Clamp non-gate movers via interrupted-coord at archetype rate × t,
    # mirroring CR's shot-outcome clamp so support players don't teleport.
    for pid, start_coord in step_start_coords.items():
        if pid == rr_id:
            continue
        target = end_coords.get(pid)
        if target is None:
            continue
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, archetype[pid])
        end_coords[pid] = _interrupted_coord(start_coord, target, rate, t)

    ball_start: BallState = {"owner_player_id": rr_id}
    ball_end: BallState = {"owner_player_id": rr_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": rr_id,
            "target_coords": dict(rr_coord_end),
        },
    }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": _resolve_shot_next(turn_result),
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


# --- Branch step builders: STEAL & Bat OOB ---------------------------------


def _build_lane_pass_intercepted_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> Optional[AnimationStep]:
    """STEAL branch step 2: lane pass intercepted.

    Gate: ball reaches stealer at contact grid (intercept contact point
    via ``_compute_interception_contact_grid``). RR partial sprint to
    ``(rr.x + 3 toward basket, rr.y)``; stealer sprint to contact grid.

    ``step.end.announcement = "Interception!"`` secondary defense,
    stealer headshot, 1000ms hold, steal SFX.
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    bh_id = _safe_id(phase.get("outlet_receiver_id"))
    rr_id = _safe_id(phase.get("rr_id"))
    stealer_id = _safe_id(turn_result.get("stealer_id")) or _safe_id(
        fb_roles.get("defender")
    )
    if not bh_id or not rr_id or not stealer_id:
        return None
    if bh_id not in step_start_coords or rr_id not in step_start_coords:
        return None
    if stealer_id not in step_start_coords:
        return None

    bh_coord = step_start_coords[bh_id]
    rr_coord = step_start_coords[rr_id]
    x_dir = -1 if is_away_offense else 1

    # RR moves to the full catch_grid even though the pass is cut off — matches
    # the shot-branch destination for consistency across all three lane-pass
    # variants. The contact_grid (where the defender intercepts) is computed
    # from the same target.
    catch_target: GridCoord = {
        "x": float(max(4.0, min(97.0, rr_coord["x"] + 6 * x_dir))),
        "y": float(rr_coord["y"]),
    }
    rr_partial: GridCoord = dict(catch_target)
    contact_grid = _compute_interception_contact_grid(bh_coord, catch_target)

    stealer_coord = step_start_coords[stealer_id]
    stealer_player = _player_lookup_by_id(off_lineup, def_lineup, stealer_id)
    stealer_rate = _ag_grid_per_game_sec(stealer_player, "sprint")
    t = max(0.3, _traversal_seconds(stealer_coord, contact_grid, stealer_rate))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    actions[bh_id] = "pass"
    actions[rr_id] = "cut"
    archetype[rr_id] = "sprint"
    destinations[rr_id] = dict(rr_partial)
    end_coords[rr_id] = dict(rr_partial)

    actions[stealer_id] = "guard_ball"
    archetype[stealer_id] = "sprint"
    destinations[stealer_id] = dict(contact_grid)
    end_coords[stealer_id] = dict(contact_grid)

    # Ball state continuity (see _build_outlet_pass_step). BH had the ball
    # at end of step 1; intercept is BallAttached(BH) → BallAttached(stealer).
    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"owner_player_id": stealer_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": bh_id,
            "to_player_id": stealer_id,
            "target_coords": dict(contact_grid),
            "contact_coords": dict(contact_grid),
        },
    }

    defense_team = "home" if is_away_offense else "away"
    announcement: Announcement = {
        "text": "Interception!",
        "team": defense_team,
        "player_data": _build_player_data(stealer_player, fallback_id=stealer_id),
        "meta": {"sfx": "steal"},
        "hold_ms": 1000,
        "style": "secondary",
    }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {
            "kind": "turn_stop",
            "event": "STEAL",
            "payload": {"stealer_id": stealer_id, "victim_id": bh_id},
        },
        "announcement": announcement,
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


def _build_lane_pass_batted_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> Optional[AnimationStep]:
    """Bat OOB branch step 2: lane pass batted out of bounds.

    Gate: ``ball_reaches_player`` with player = the batting defender at
    contact grid (per the decision in Q-A: defender doubles as gate even
    though they bat rather than catch). RR partial sprint to ``(rr.x + 4
    toward basket, rr.y)``; defender sprints to contact grid; ball flies
    BH → contact → drifts to nearest OOB grid (loose at step end).

    ``step.end.announcement = "Out of bounds!"`` secondary neutral, no
    headshot, 650ms hold, text scroll = "Batted out of bounds."
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    bh_id = _safe_id(phase.get("outlet_receiver_id"))
    rr_id = _safe_id(phase.get("rr_id"))
    defender_id = (
        _safe_id(turn_result.get("defender_id"))
        or _safe_id(turn_result.get("defender"))
        or _safe_id(fb_roles.get("defender"))
    )
    if not bh_id or not rr_id or not defender_id:
        return None
    if bh_id not in step_start_coords or rr_id not in step_start_coords:
        return None
    if defender_id not in step_start_coords:
        return None

    bh_coord = step_start_coords[bh_id]
    rr_coord = step_start_coords[rr_id]
    x_dir = -1 if is_away_offense else 1

    # RR moves to the full catch_grid even though the pass gets batted —
    # matches the shot-branch destination.
    catch_target: GridCoord = {
        "x": float(max(4.0, min(97.0, rr_coord["x"] + 6 * x_dir))),
        "y": float(rr_coord["y"]),
    }
    rr_partial: GridCoord = dict(catch_target)
    contact_grid = _compute_interception_contact_grid(bh_coord, catch_target)
    oob_grid = _nearest_oob_grid(contact_grid)

    defender_coord = step_start_coords[defender_id]
    defender_player = _player_lookup_by_id(off_lineup, def_lineup, defender_id)
    defender_rate = _ag_grid_per_game_sec(defender_player, "sprint")
    t = max(0.3, _traversal_seconds(defender_coord, contact_grid, defender_rate))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    actions[bh_id] = "pass"
    actions[rr_id] = "cut"
    archetype[rr_id] = "sprint"
    destinations[rr_id] = dict(rr_partial)
    end_coords[rr_id] = dict(rr_partial)

    actions[defender_id] = "guard_ball"
    archetype[defender_id] = "sprint"
    destinations[defender_id] = dict(contact_grid)
    end_coords[defender_id] = dict(contact_grid)

    # Ball state continuity (see _build_outlet_pass_step). BH had the ball
    # at end of step 1; batted is BallAttached(BH) → BallLoose(OOB grid).
    # advance_trigger.metadata.contact_coords + oob_coords let the frontend
    # render the bend (passer → contact → drift to OOB).
    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"coords": dict(oob_grid)}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": bh_id,
            "to_player_id": defender_id,
            "target_coords": dict(contact_grid),
            "contact_coords": dict(contact_grid),
            "oob_coords": dict(oob_grid),
        },
    }

    announcement: Announcement = {
        "text": "Out of bounds!",
        "team": "neutral",
        "player_data": None,
        "meta": {"text_scroll": "Batted out of bounds."},
        "hold_ms": 650,
        "style": "secondary",
    }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {
            "kind": "turn_stop",
            "event": "DEAD_BALL_TURNOVER",
            "payload": {"victim_id": bh_id, "ball_oob_coords": dict(oob_grid)},
        },
        "announcement": announcement,
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


# --- Branch step builders: Hold-up -----------------------------------------


def _build_hold_up_step(
    *,
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> Optional[AnimationStep]:
    """Hold-up branch step 2: BH settle + supporting drift.

    Gate: BH reaches hold-up spot (``bh.x + 6 toward attacking basket,
    bh.y ± 8 toward y=25``). Other players drift toward attacking basket
    at cruise rate; end coords clamped via interrupted-coord at ``rate × T``.

    ``step.start.announcement = "No Fast Break"`` secondary offense, BH
    headshot, decision pill — only fires when ``rim_runner_no_lane_pass``.
    Implicit end (next = ``next_step`` past array) — caller transitions to
    HCO (with optional ``hco_setup`` inbound pass when BH ≠ PG).
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    bh_id = _safe_id(phase.get("outlet_receiver_id"))
    if not bh_id or bh_id not in step_start_coords:
        import logging
        logging.warning(
            "🐛 [HOLD_UP_STEP_NONE] reason=bh_invalid bh_id=%s in_start_coords=%s",
            bh_id, bh_id in step_start_coords if bh_id else False,
        )
        return None

    bh_coord = step_start_coords[bh_id]
    x_dir = -1 if is_away_offense else 1
    settle_y_delta = 8.0 if bh_coord["y"] < 25 else -8.0
    settle_target: GridCoord = {
        "x": float(max(4.0, min(97.0, bh_coord["x"] + 6 * x_dir))),
        "y": float(max(1.0, min(49.0, bh_coord["y"] + settle_y_delta))),
    }

    bh_player = _player_lookup_by_id(off_lineup, def_lineup, bh_id)
    bh_rate = _ag_grid_per_game_sec(bh_player, "standard")
    t = max(0.5, _traversal_seconds(bh_coord, settle_target, bh_rate))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    actions[bh_id] = "handle_ball"
    archetype[bh_id] = "standard"
    destinations[bh_id] = dict(settle_target)
    end_coords[bh_id] = dict(settle_target)

    for pid, start_coord in step_start_coords.items():
        if pid == bh_id:
            continue
        drift_target: GridCoord = {
            "x": float(max(4.0, min(97.0, start_coord["x"] + 40 * x_dir))),
            "y": float(start_coord["y"]),
        }
        destinations[pid] = dict(drift_target)
        actions[pid] = (
            "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
        )
        archetype[pid] = "standard"
        player = _player_lookup_by_id(off_lineup, def_lineup, pid)
        rate = _ag_grid_per_game_sec(player, "standard")
        end_coords[pid] = _interrupted_coord(start_coord, drift_target, rate, t)

    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"owner_player_id": bh_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": bh_id,
            "target_coords": dict(settle_target),
        },
    }

    no_lane_pass = bool(turn_result.get("rim_runner_no_lane_pass"))
    announcement: Optional[Announcement] = None
    if no_lane_pass:
        announcement = {
            "text": "No Fast Break",
            "team": "away" if is_away_offense else "home",
            "player_data": _build_player_data(bh_player, fallback_id=bh_id),
            "meta": {**_decision_pill_meta(turn_result), "sfx": "no_fast_break"},
            "hold_ms": 1000,
            "style": "secondary",
        }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    if announcement is not None:
        start["announcement"] = announcement
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": 999},
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


# --- Branch step builders: Outlet Denied (3 sub-steps) ---------------------


def _build_outlet_denied_defender_step(
    *,
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    step_start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
    next_step_index: int,
) -> Optional[AnimationStep]:
    """Outlet denied branch step 1: defender close-out beat.

    Gate: outlet defender reaches ``(ball_holder.x + 2 toward basket,
    ball_holder.y)``. Ball stays with the ball holder — no pass fires.

    Ball holder = outlet passer (rebounder) normally; when
    ``skip_outlet_pass`` is true (rebounder == outlet receiver), the
    receiver IS the rebounder holding the ball, so the defender anchors on
    the receiver instead.

    ``step.end.announcement = "FB Outlet Pass Denied!"`` secondary defense,
    defender headshot, 1000ms hold, court SFX.
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    passer_id = _safe_id(phase.get("outlet_passer_id"))
    receiver_id = _safe_id(phase.get("outlet_receiver_id"))
    defender_id = _safe_id(phase.get("outlet_defender_id"))
    ball_holder_id = passer_id or receiver_id
    if not ball_holder_id or not defender_id:
        import logging
        logging.warning(
            "🐛 [OUTLET_DENIED_DEFENDER_STEP_NONE] reason=missing_id passer_id=%s receiver_id=%s defender_id=%s",
            passer_id, receiver_id, defender_id,
        )
        return None
    if defender_id not in step_start_coords or ball_holder_id not in step_start_coords:
        import logging
        logging.warning(
            "🐛 [OUTLET_DENIED_DEFENDER_STEP_NONE] reason=id_not_in_start_coords ball_holder_id=%s defender_id=%s",
            ball_holder_id, defender_id,
        )
        return None

    ball_holder_coord = step_start_coords[ball_holder_id]
    x_dir = -1 if is_away_offense else 1
    defender_target: GridCoord = {
        "x": float(max(4.0, min(97.0, ball_holder_coord["x"] + 2 * x_dir))),
        "y": float(ball_holder_coord["y"]),
    }

    defender_coord = step_start_coords[defender_id]
    defender_player = _player_lookup_by_id(off_lineup, def_lineup, defender_id)
    defender_rate = _ag_grid_per_game_sec(defender_player, "standard")
    t = max(0.3, _traversal_seconds(defender_coord, defender_target, defender_rate))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }
    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in step_start_coords.items()
    }

    actions[ball_holder_id] = "handle_ball"
    actions[defender_id] = "guard_ball"
    archetype[defender_id] = "standard"
    destinations[defender_id] = dict(defender_target)
    end_coords[defender_id] = dict(defender_target)

    ball_start: BallState = {"owner_player_id": ball_holder_id}
    ball_end: BallState = {"owner_player_id": ball_holder_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": defender_id,
            "target_coords": dict(defender_target),
        },
    }

    defense_team = "home" if is_away_offense else "away"
    announcement: Announcement = {
        "text": "FB Outlet Pass Denied!",
        "team": defense_team,
        "player_data": _build_player_data(defender_player, fallback_id=defender_id),
        "meta": {"sfx": "fb_outlet_denied_court"},
        "hold_ms": 1000,
        "style": "secondary",
    }

    clock_start: ClockState = {
        "clock_remaining": clock_remaining_at_start,
        "shot_clock_remaining": shot_clock_remaining_at_start,
    }
    clock_end: ClockState = {
        "clock_remaining": clock_remaining_at_start - t,
        "shot_clock_remaining": shot_clock_remaining_at_start - t,
    }

    start: StepStart = {
        "coords": dict(step_start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetype,
        "ball": ball_start,
        "clock": clock_start,
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": end_coords,
        "ball": ball_end,
        "time_elapsed": t,
        "clock": clock_end,
        "next": {"kind": "next_step", "index": next_step_index},
        "announcement": announcement,
    }
    _stamp_tween_durations(start, end_coords, t, off_lineup, def_lineup)
    return {"start": start, "end": end}


# --- Post-emit hooks (canonicalize overlays + hco_setup) -------------------


def _stamp_hco_setup(
    turn_result: Dict[str, Any],
    game: Any,
    steps: List[AnimationStep],
) -> None:
    """When the FB turn ends with the BH (outlet receiver) holding the ball
    away from the offensive PG (hold-up or outlet-denied branches), stamp
    ``hco_setup.inbound_pass`` so the next HCO turn can render a BH → PG
    inbound during HCO step 0.

    Backend-source-of-truth signal (replaces the legacy frontend
    ``scene._rimRunnerHoldUpInboundPass`` flag). Game manager propagates
    this onto the next HCO turn payload; HCO consumer reads from there.
    """
    needs_inbound = bool(turn_result.get("rim_runner_no_lane_pass")) or bool(
        turn_result.get("rim_runner_outlet_failed")
    )
    if not needs_inbound:
        return

    fb_roles = turn_result.get("roles") or {}
    burst_phase = fb_roles.get("rim_runner_burst_phase") or {}

    # BH at end of FB turn = ball owner at last step's end.ball. This is
    # whoever physically has the ball when the FB closes (outlet receiver
    # for hold-up; rebounder/outlet passer for outlet-denied where the
    # pass never fired).
    bh_id: Optional[str] = None
    if steps:
        last_end = steps[-1].get("end") or {}
        last_ball = last_end.get("ball") or {}
        bh_id = _safe_id(last_ball.get("owner_player_id"))
    if not bh_id:
        # Fallback: outlet receiver from burst phase.
        bh_id = _safe_id(burst_phase.get("outlet_receiver_id"))
    if not bh_id:
        return

    off_team = getattr(game, "offense_team", None)
    if off_team is None:
        return
    pg = (getattr(off_team, "lineup", {}) or {}).get("PG")
    pg_id = _safe_id(pg)
    if not pg_id or bh_id == pg_id:
        return

    from_coords: Optional[GridCoord] = None
    if steps:
        last_end = (steps[-1].get("end") or {})
        last_end_coords = last_end.get("coords") or {}
        bh_coords = last_end_coords.get(bh_id)
        if isinstance(bh_coords, dict) and "x" in bh_coords and "y" in bh_coords:
            from_coords = {"x": float(bh_coords["x"]), "y": float(bh_coords["y"])}

    turn_result["hco_setup"] = {
        "inbound_pass": {
            "from_player_id": bh_id,
            "to_player_id": pg_id,
            "from_coords": from_coords,
        }
    }


def _ensure_turn_shooter_for_post_shot(turn_result: Dict[str, Any]) -> None:
    """``_build_post_shot_sub_steps`` reads ``turn_result[\"shooter\"]``.
    Rim Runner sometimes only has ``shooter_id`` or ``roles`` populated."""
    if _safe_id(turn_result.get("shooter")):
        return
    sid = _safe_id(turn_result.get("shooter_id"))
    if sid:
        turn_result["shooter"] = sid
        return
    roles = turn_result.get("roles") or {}
    phase = roles.get("rim_runner_burst_phase") or {}
    rr_id = _safe_id(phase.get("rr_id"))
    if rr_id:
        turn_result["shooter"] = rr_id
        return
    fb_shooter = _safe_id(roles.get("shooter"))
    if fb_shooter:
        turn_result["shooter"] = fb_shooter


def _warn_if_post_shot_sfx_missing(
    turn_result: Dict[str, Any],
    steps: List[AnimationStep],
) -> None:
    """UESS contract: MAKE/MISS/BLOCK shot branches must emit [ball_flight] SFX."""
    rt = (turn_result.get("result_type") or "").upper()
    if rt not in ("MAKE", "MISS", "BLOCK"):
        return
    has_shot_flight_sfx = False
    for step in steps:
        start = step.get("start") or {}
        if start.get("ball_motion_style") == "shot" and (
            start.get("sfx_on_ball_release") or start.get("sfx_on_ball_arrival")
        ):
            has_shot_flight_sfx = True
            break
    if not has_shot_flight_sfx:
        logging.warning(
            "🎵 [RR POST_SHOT SFX] result_type=%s fast_break_play=%s steps=%d "
            "— no [ball_flight] shot SFX cues after _build_post_shot_sub_steps",
            rt,
            turn_result.get("fast_break_play"),
            len(steps),
        )


def _finalize_rr_steps(
    turn_result: Dict[str, Any],
    game: Any,
    steps: List[AnimationStep],
) -> Optional[List[AnimationStep]]:
    """Single exit hook for the RR dispatcher. Re-canonicalizes post-shot
    overlays (factors in the FB-specific ``outlet_passer`` role that
    ``shot_manager`` didn't know about), appends variant-aware post-shot
    sub-steps ([ball_flight] / variant / [hold] / [bounce]) for MAKE /
    MISS / BLOCK so FB shots get the same schema-pure resolution + SFX +
    announcements as HCO/OREB shots, and stamps ``hco_setup`` for
    hold-up / outlet-denied. Returns ``None`` when no steps were built so
    the caller falls back to legacy rendering."""
    if not steps:
        return None
    try:
        from BackEnd.utils.shared import canonicalize_post_shot_overlays

        canonicalize_post_shot_overlays(turn_result)
    except Exception:
        # Canonicalize is best-effort; failure shouldn't block the steps emit.
        pass

    # Variant-aware post-shot sub-steps (audit remediation item 4). Brings
    # FB shots onto the same end-state schema as HCO/FCP/OREB so:
    #   - the [ball_flight] step stamps `sfx_on_ball_release`,
    #     `sfx_on_ball_arrival`, and per-variant `timed_sfx` cues
    #   - variant intermediates (rattle hops / settle, bank settle/graze,
    #     airball OOB) render correctly
    #   - the [hold] sub-step holds the "It's Good!" beat at MSSS for makes
    #   - the [bounce] sub-step animates ball → ball_bounce_coords for misses
    #   - the turn_stop SHOT_ATTEMPT is flagged with `schema_rendered_arc:true`
    #     so FE `runShotAttempt` short-circuits and the legacy arc/hold
    #     doesn't double-fire
    # No-op for non-MAKE/MISS/BLOCK result_types and when the final step
    # isn't a shoot step (the helper guards both cases internally).
    off_lineup = getattr(getattr(game, "offense_team", None), "lineup", {}) or {}
    def_lineup = getattr(getattr(game, "defense_team", None), "lineup", {}) or {}
    _ensure_turn_shooter_for_post_shot(turn_result)
    try:
        from BackEnd.engine.skeleton_step_emitter import _build_post_shot_sub_steps
        away_team_id = getattr(getattr(game, "away_team", None), "team_id", None)
        offense_team_id = getattr(getattr(game, "offense_team", None), "team_id", None)
        away_offense = bool(
            away_team_id is not None
            and offense_team_id is not None
            and str(offense_team_id) == str(away_team_id)
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, away_offense,
        )
    except Exception:
        logging.exception("FB post-shot sub-steps failed")
    _warn_if_post_shot_sfx_missing(turn_result, steps)

    _stamp_hco_setup(turn_result, game, steps)

    from BackEnd.utils.animation_step_helpers import log_fb_animation_steps
    label = str(turn_result.get("fast_break_play") or "FB").upper()
    log_fb_animation_steps(label, steps, off_lineup, def_lineup)

    return steps


# --- Main entry point: branch dispatcher -----------------------------------


def build_rim_runner_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert a Rim Runner FB ``turn_result`` into ``AnimationStep[]``.

    Branch dispatch keyed off turn_result flags + ``result_type``:
        ``rim_runner_outlet_failed`` → Outlet Denied (3 sub-steps after burst)
        ``rim_runner_no_lane_pass``  → Hold-up
        ``rim_runner_interception``  → STEAL
        ``rim_runner_bat_oob``       → Bat OOB
        otherwise                    → Shot (lane pass + shot motion)

    Returns ``None`` when required data is missing — caller falls back to
    the legacy renderer.
    """
    if turn_result.get("fast_break_play") != "rim_runner":
        return None

    fb_roles = turn_result.get("roles") or {}
    burst_phase = fb_roles.get("rim_runner_burst_phase")
    if not burst_phase:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(
        fb_roles.get("is_away_offense") or burst_phase.get("is_away_offense")
    )

    all_start_coords = _all_player_start_coords(off_lineup, def_lineup)
    if not all_start_coords:
        return None

    from BackEnd.utils.animation_step_helpers import log_fb_emitter_entry
    log_fb_emitter_entry("RR", all_start_coords, game, off_lineup, def_lineup)

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    outlet_failed = bool(turn_result.get("rim_runner_outlet_failed"))
    no_lane_pass = bool(turn_result.get("rim_runner_no_lane_pass"))
    interception = bool(turn_result.get("rim_runner_interception"))
    bat_oob = bool(turn_result.get("rim_runner_bat_oob"))

    steps: List[AnimationStep] = []
    elapsed = 0.0

    # Step 0: burst (all branches).
    burst_step = _build_burst_step(
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        all_start_coords=all_start_coords,
        is_away_offense=is_away_offense,
        clock_remaining_at_start=clock_remaining,
        shot_clock_remaining_at_start=shot_clock_remaining,
        next_step_index=1,
    )
    if burst_step is None:
        return None
    steps.append(burst_step)
    elapsed += float(burst_step["end"]["time_elapsed"])
    last_end_coords = dict(burst_step["end"]["coords"])

    # Outlet denied: forks at step 1 (no outlet pass; defender close-out).
    # The cutback + recovery-pass beats have been moved to HCO's Reset step
    # (destination-turn pattern). This branch ends at the defender close-out
    # with the rebounder still holding the ball; hco_setup signals the next
    # HCO turn to fire Reset for the inbound to PG.
    if outlet_failed:
        denied_defender = _build_outlet_denied_defender_step(
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
            next_step_index=999,  # implicit end → HCO turn
        )
        if denied_defender is None:
            return None
        steps.append(denied_defender)
        return _finalize_rr_steps(turn_result, game, steps)

    # All other branches: outlet pass (unless skip_outlet_pass).
    skip_outlet_pass = bool(burst_phase.get("skip_outlet_pass"))
    if not skip_outlet_pass:
        outlet_step = _build_outlet_pass_step(
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
            next_step_index=2,
        )
        if outlet_step is None:
            return None
        steps.append(outlet_step)
        elapsed += float(outlet_step["end"]["time_elapsed"])
        last_end_coords = dict(outlet_step["end"]["coords"])

    next_idx = len(steps) + 1

    if interception:
        intercept = _build_lane_pass_intercepted_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        )
        if intercept is not None:
            steps.append(intercept)
        return _finalize_rr_steps(turn_result, game, steps)

    if bat_oob:
        batted = _build_lane_pass_batted_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        )
        if batted is not None:
            steps.append(batted)
        return _finalize_rr_steps(turn_result, game, steps)

    if no_lane_pass:
        hold_up = _build_hold_up_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=last_end_coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        )
        if hold_up is not None:
            steps.append(hold_up)
        return _finalize_rr_steps(turn_result, game, steps)

    # Shot branch: lane pass + shot motion.
    lane_pass = _build_lane_pass_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_start_coords=last_end_coords,
        is_away_offense=is_away_offense,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
        next_step_index=next_idx,
    )
    if lane_pass is None:
        return None
    steps.append(lane_pass)
    elapsed += float(lane_pass["end"]["time_elapsed"])
    last_end_coords = dict(lane_pass["end"]["coords"])

    shot_motion = _build_shot_motion_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        animations=turn_result.get("animations") or [],
        step_start_coords=last_end_coords,
        clock_remaining_at_start=clock_remaining - elapsed,
        shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
    )
    if shot_motion is not None:
        steps.append(shot_motion)

    return _finalize_rr_steps(turn_result, game, steps)
