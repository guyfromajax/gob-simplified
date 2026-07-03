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
    ("FB Outlet Pass Denied!" announcement) → implicit end → HCO. The
    cutback + recovery-pass beats live on the next HCO turn's Reset step
    (destination-turn pattern, signalled via ``hco_setup``).

Edge case: when rebounder == outlet receiver (``skip_outlet_pass == true``),
step 1 is skipped — the burst step chains directly to the branch's step 2
(or step 1 for outlet-denied).

Branch dispatch is keyed off ``turn_result``:

- ``rim_runner_outlet_failed`` (bool) → Outlet Denied branch.
- ``rim_runner_no_lane_pass`` (bool) → Hold-up branch.
- ``rim_runner_interception`` (bool) → STEAL branch.
- ``rim_runner_bat_oob`` (bool) → Bat OOB branch.
- otherwise (``result_type`` MAKE/MISS/BLOCK/FOUL) → Shot branch.

Triangle reuses burst, outlet, and ``append_lane_pass_to_rr_resolution_steps``
for the open-lane pass-ahead path; full Triangle setup uses
``triangle_step_emitter.py``.

See ``_documentation_master/00_General_Systems/Step_By_Step_System.md`` —
"Rim Runner" — for the per-step trigger spec.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    FB_OUTLET_QUALITY_THRESHOLD,
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY,
    FB_PASS_MIN_GAME_SECONDS,
    HCO_STRING_SPOTS,
    HOME_RIM_COORDS,
)
from BackEnd.engine.skeleton_step_emitter import _compute_pass_meet_point
from BackEnd.utils.animation_step_helpers import floor_step_t_to_traversal
from BackEnd.utils.shared import get_away_player_coords
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


def _coord_of(raw: Any) -> Optional[GridCoord]:
    if not isinstance(raw, dict) or "x" not in raw or "y" not in raw:
        return None
    return {"x": float(raw["x"]), "y": float(raw["y"])}


def shot_spot_from_roles(
    turn_result: Dict[str, Any],
    fb_roles: Dict[str, Any],
) -> Optional[GridCoord]:
    """Authoritative shot spot for a FB shot-motion step, sourced from
    backend geometry rather than the legacy ``capture_fast_break_animation``
    packet. Keeps the shooter rendering at the geo-correct spot regardless of
    live-coord / mid-game-resume state (see the Triangle ``rr_post`` fix)."""
    roles = turn_result.get("roles") if isinstance(turn_result, dict) else None
    return _coord_of(
        (fb_roles or {}).get("shot_spot")
        or (turn_result or {}).get("shot_spot")
        or (roles or {}).get("shot_spot")
    )


def closeout_contest_coord(
    defender_start: GridCoord,
    shot_spot: GridCoord,
    standoff: float = 2.0,
) -> GridCoord:
    """Deterministic contest position: the defender closes toward the shot
    spot and stops ``standoff`` grid units short. Pure geometry (no legacy
    packet) so the closeout is stable across resumes."""
    dx = float(defender_start["x"]) - float(shot_spot["x"])
    dy = float(defender_start["y"]) - float(shot_spot["y"])
    dist = math.hypot(dx, dy)
    if dist <= standoff or dist == 0.0:
        return {"x": float(defender_start["x"]), "y": float(defender_start["y"])}
    scale = standoff / dist
    return {
        "x": float(shot_spot["x"]) + dx * scale,
        "y": float(shot_spot["y"]) + dy * scale,
    }


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


def _rr_payload_archetype(phase: Dict[str, Any]) -> PlayerArchetype:
    rr_to = phase.get("rr_to") if isinstance(phase, dict) else None
    raw = rr_to.get("movement_archetype") if isinstance(rr_to, dict) else None
    return raw if raw in ("burst", "sprint") else "sprint"


def _rr_post_burst_archetype(phase: Dict[str, Any]) -> PlayerArchetype:
    """Post-burst RR pace for the lane-pass receive/drive.

    The ``burst`` archetype (``BURST_GRID_PER_GAME_SEC`` = 32 g/s) is the peak
    explosive START only — Step 0's fixed one-game-second advance. It must NOT
    carry into the lane-pass step or the RR jets to the rim while receiving the
    pass. Decelerate ``burst`` → ``sprint`` here, mirroring the
    ``rr_archetype_override="sprint"`` the normal outlet-pass path applies
    (``triangle_step_emitter``). ``skip_outlet_pass`` turns bypass that outlet
    step, which is how the burst rate leaked into the lane pass / drive.
    """
    payload = _rr_payload_archetype(phase)
    return "sprint" if payload == "burst" else payload


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

    Gate: fixed 1.0 game-second. RR targets the basket spot and advances
    exactly one game-second at the payload's ``burst`` / ``sprint`` archetype.
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

    # RR targets rr_to but Step 0 is a fixed one-game-second advance, so the
    # end coord is rate-capped instead of forced to the final target.
    rr_end_target: GridCoord = {
        "x": float(rr_to["x"]),
        "y": float(rr_to["y"]),
    }
    rr_archetype = _rr_payload_archetype(phase)
    t = 1.0

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

    _commit_mover(rr_id, rr_end_target, "sprint", rr_archetype)

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
        "condition": "fixed_duration",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": rr_id,
            "target_coords": dict(rr_end_target),
            "reason": "rim_runner_fixed_burst_advance",
            "movement_archetype": rr_archetype,
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
    rr_archetype_override: Optional[PlayerArchetype] = None,
) -> Optional[AnimationStep]:
    """Step 1: outlet pass (rebounder → outlet receiver). Pass rate gated on
    outlet quality — sharp (``outlet_score >= FB_OUTLET_QUALITY_THRESHOLD``)
    flies at ``FB_PASS_GRID_SPOTS_PER_GAME_SECOND``; sloppy at
    ``FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY``.
    Floored at ``FB_PASS_MIN_GAME_SECONDS`` for very short passes.

    Per-player movement: passer / receiver stationary at their current
    carried-forward coords; RR continues toward the basket target using the
    same archetype chosen in step 0; all other movers continue toward their
    step 0 burst destinations.

    ``rr_archetype_override`` forces the RR's movement archetype for this step
    only (Triangle passes ``"sprint"`` so the RR settles out of the burst once
    the outlet pass goes); when ``None`` (Rim Runner) the carried-forward
    step-0 archetype is used.

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
            arch: PlayerArchetype = rr_archetype_override or _rr_payload_archetype(phase)
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


# --- Lane pass (shot branch) helpers ---------------------------------------

LANE_PASS_LEAD_RAW_THRESHOLD = 125


def _fb_spot_coords(spot: str, is_away_offense: bool) -> GridCoord:
    coords = dict(HCO_STRING_SPOTS.get(spot, {"x": 50, "y": 25}))
    if is_away_offense:
        coords = get_away_player_coords(coords)
    return {"x": float(coords["x"]), "y": float(coords["y"])}


def _lane_pass_vertical_half(y: float) -> str:
    return "upper" if float(y) > 25.0 else "lower"


def _calculate_lane_pass_raw_score(bh_player: Any, fb_efficiency: int) -> float:
    """Animation-only lane-pass quality roll for the outlet receiver (BH).

    ``((PS*0.6 + ST*0.2 + IQ*0.2) + fb_efficiency) * d6`` with
    ``fb_efficiency`` clamped to the same −10…+10 band used in RR resolution.
    """
    attrs = getattr(bh_player, "attributes", None) or {}
    fb_eff = max(-10, min(10, int(fb_efficiency or 0)))
    composite = (
        float(attrs.get("PS", 0) or 0) * 0.6
        + float(attrs.get("ST", 0) or 0) * 0.2
        + float(attrs.get("IQ", 0) or 0) * 0.2
        + float(fb_eff)
    )
    return composite * random.randint(1, 6)


def _lane_pass_getback_targets(
    getback_ids: List[Any],
    step_start_coords: Dict[str, GridCoord],
    rr_y: float,
    is_away_offense: bool,
    basket_spot: GridCoord,
) -> Dict[str, GridCoord]:
    """Assign get-back sprint targets for the lane-pass help-defender beat."""
    valid = [
        str(pid)
        for pid in (getback_ids or [])
        if pid is not None and str(pid) in step_start_coords
    ]
    if not valid:
        return {}

    half = _lane_pass_vertical_half(rr_y)
    mid_post = _fb_spot_coords(f"{half} midPost", is_away_offense)

    if len(valid) == 1:
        return {valid[0]: dict(basket_spot)}

    def _dist_to_basket(pid: str) -> float:
        return _euclid(step_start_coords[pid], basket_spot)

    min_dist = min(_dist_to_basket(pid) for pid in valid)
    tied_closest = [pid for pid in valid if abs(_dist_to_basket(pid) - min_dist) < 1e-6]
    basket_id = random.choice(tied_closest)
    targets: Dict[str, GridCoord] = {basket_id: dict(basket_spot)}
    remaining = [pid for pid in valid if pid != basket_id]

    if len(valid) == 2:
        targets[remaining[0]] = dict(mid_post)
        return targets

    remaining_sorted = sorted(remaining, key=_dist_to_basket)
    targets[remaining_sorted[0]] = dict(mid_post)
    for pid in remaining_sorted[1:]:
        targets[pid] = dict(basket_spot)
    return targets


def _commit_lane_pass_sprint_mover(
    *,
    pid: str,
    target: GridCoord,
    step_start_coords: Dict[str, GridCoord],
    end_coords: Dict[str, GridCoord],
    destinations: Dict[str, Optional[GridCoord]],
    actions: Dict[str, PlayerAction],
    archetype: Dict[str, PlayerArchetype],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    t: float,
    mover_archetype: PlayerArchetype = "sprint",
) -> None:
    if pid not in step_start_coords:
        return
    player = _player_lookup_by_id(off_lineup, def_lineup, pid)
    rate = _ag_grid_per_game_sec(player, mover_archetype)
    actions[pid] = "cut"
    archetype[pid] = mover_archetype
    destinations[pid] = dict(target)
    end_coords[pid] = _interrupted_coord(step_start_coords[pid], target, rate, t)


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

    Pass quality (animation-only): fresh roll on the outlet receiver using
    ``((PS*0.6 + ST*0.2 + IQ*0.2) + fb_efficiency) * d6``. Raw score
    **> 125** → lead pass to ``rr_to`` at sharp FB pass rate (40); else pass
    to RR's step-start coords at sloppy rate (30).

    Non-passer/non-receiver players sprint toward ``basketSpot`` (get-backs
    split basket vs same-half ``midPost`` when two or more). All help
    defenders/offense freeze at interrupted coords when the ball reaches RR.

    Step ``T`` = ball flight time only (``ball_reaches_player``). RR may still
    be en route to ``catch_grid``; ``end.coords[rr]`` = pass meet point, not
    the full catch spot when the ball arrives first.

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
    rr_to = phase.get("rr_to") or {}

    bh_player = _player_lookup_by_id(off_lineup, def_lineup, bh_id)
    rr_player = _player_lookup_by_id(off_lineup, def_lineup, rr_id)
    fb_eff = int(phase.get("fb_efficiency") or 0)
    raw_score = _calculate_lane_pass_raw_score(bh_player, fb_eff)
    lead_pass = raw_score > LANE_PASS_LEAD_RAW_THRESHOLD
    pass_rate = (
        float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND)
        if lead_pass
        else float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY)
    )

    if lead_pass:
        catch_grid: GridCoord = {
            "x": float(rr_to.get("x", rr_coord["x"])),
            "y": float(rr_to.get("y", rr_coord["y"])),
        }
        rr_archetype = _rr_post_burst_archetype(phase)
        rr_rate = _ag_grid_per_game_sec(rr_player, rr_archetype)
        meet_point = _compute_pass_meet_point(
            bh_coord,
            rr_coord,
            catch_grid,
            rr_rate,
            ball_rate=pass_rate,
        )
        ball_pass_t = _traversal_seconds(bh_coord, meet_point, pass_rate)
    else:
        catch_grid = dict(rr_coord)
        meet_point = dict(catch_grid)
        rr_archetype = "stationary"
        ball_pass_t = _traversal_seconds(bh_coord, meet_point, pass_rate)

    t = float(ball_pass_t)

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
    if lead_pass:
        archetype[rr_id] = _rr_post_burst_archetype(phase)
        destinations[rr_id] = dict(catch_grid)
        end_coords[rr_id] = dict(meet_point)
    else:
        archetype[rr_id] = "stationary"

    basket_spot = _fb_spot_coords("basketSpot", is_away_offense)
    getback_targets = _lane_pass_getback_targets(
        fb_roles.get("getback_player_ids") or [],
        step_start_coords,
        rr_coord["y"],
        is_away_offense,
        basket_spot,
    )
    excluded = {bh_id, rr_id}
    for pid, target in getback_targets.items():
        if pid in excluded:
            continue
        _commit_lane_pass_sprint_mover(
            pid=pid,
            target=target,
            step_start_coords=step_start_coords,
            end_coords=end_coords,
            destinations=destinations,
            actions=actions,
            archetype=archetype,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            t=t,
            mover_archetype="sprint",
        )
        excluded.add(pid)

    for pid in step_start_coords:
        if pid in excluded:
            continue
        _commit_lane_pass_sprint_mover(
            pid=pid,
            target=basket_spot,
            step_start_coords=step_start_coords,
            end_coords=end_coords,
            destinations=destinations,
            actions=actions,
            archetype=archetype,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            t=t,
            # Full-break budget: the off-ball cast sprints (not standard) toward
            # the rim on the lane pass so they keep advancing in stride with the
            # break instead of drifting and then parking on the drive step.
            mover_archetype="sprint",
        )

    ball_start: BallState = {"owner_player_id": bh_id}
    ball_end: BallState = {"owner_player_id": rr_id}

    advance_trigger: AdvanceTrigger = {
        "condition": "ball_reaches_player",
        "T_game_seconds": float(t),
        "metadata": {
            "from_player_id": bh_id,
            "to_player_id": rr_id,
            "target_coords": dict(meet_point),
            "pass_grid_per_game_second": float(pass_rate),
        },
    }

    announcement: Announcement = {
        "text": "Fast Break!",
        "team": "away" if is_away_offense else "home",
        "player_data": _build_player_data(bh_player, fallback_id=bh_id),
        "meta": {
            **_decision_pill_meta(turn_result),
            "eventSubtitle": _fb_play_label(turn_result.get("fast_break_play")),
        },
        # Non-blocking: the "Fast Break!" callout rides ALONGSIDE the lane pass to the
        # rim runner instead of freezing the court for a full second before it. The FE
        # shows the overlay without a clock pause / hold wait. See Announcement_System.md.
        "hold_ms": 1000,
        "non_blocking": True,
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
        "ball_motion_style": "pass",
        "ball_arrival_coord": dict(meet_point),
        "pass_grid_per_game_second": float(pass_rate),
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
    step_start_coords: Dict[str, GridCoord],
    clock_remaining_at_start: float,
    shot_clock_remaining_at_start: float,
) -> Optional[AnimationStep]:
    """Shot branch step 3: shot motion (RR → shot spot). Ends with
    ``turn_stop: SHOT_ATTEMPT``.

    Fully UESS: the shooter's end is the authoritative backend ``shot_spot``
    (not the legacy ``capture_fast_break_animation`` packet), the primary
    defender does a deterministic geo closeout, and all off-ball players hold
    their post-lane-pass positions. This is the reachable lane-pass quick-shot
    path; anchoring to ``shot_spot`` prevents the RR from jetting to a stale
    packet spot (same class of bug as the Triangle ``rr_post`` fix).
    """
    phase = fb_roles.get("rim_runner_burst_phase") or {}
    rr_id = _safe_id(phase.get("rr_id"))
    if not rr_id or rr_id not in step_start_coords:
        return None

    # Everyone holds their post-lane-pass position by default (no legacy
    # ``_movement_end_coord`` lookups).
    end_coords: Dict[str, GridCoord] = {
        pid: dict(step_start_coords[pid]) for pid in step_start_coords
    }

    rr_coord_start = step_start_coords[rr_id]
    shot_spot = shot_spot_from_roles(turn_result, fb_roles)
    rr_coord_end = shot_spot or dict(rr_coord_start)
    rr_player = _player_lookup_by_id(off_lineup, def_lineup, rr_id)
    rr_rate = _ag_grid_per_game_sec(rr_player, "sprint")
    t = max(0.2, _traversal_seconds(rr_coord_start, rr_coord_end, rr_rate))

    defender_id = _safe_id(turn_result.get("defender") or fb_roles.get("defender"))

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in step_start_coords}
    archetype: Dict[str, PlayerArchetype] = {
        pid: "stationary" for pid in step_start_coords
    }

    actions[rr_id] = "shoot"
    archetype[rr_id] = "sprint"
    end_coords[rr_id] = dict(rr_coord_end)

    # Primary defender: deterministic geo closeout toward the shot spot,
    # clamped by sprint rate × t (no teleport, no legacy packet).
    if defender_id and defender_id in step_start_coords:
        actions[defender_id] = "guard_ball"
        archetype[defender_id] = "sprint"
        d_start = step_start_coords[defender_id]
        contest = closeout_contest_coord(d_start, rr_coord_end)
        d_player = _player_lookup_by_id(off_lineup, def_lineup, defender_id)
        d_rate = _ag_grid_per_game_sec(d_player, "sprint")
        end_coords[defender_id] = _interrupted_coord(d_start, contest, d_rate, t)

    destinations: Dict[str, Optional[GridCoord]] = {
        pid: dict(end_coords[pid]) for pid in step_start_coords
    }

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

    # RR moves to the full catch_grid even though the pass is cut off — matches
    # the shot-branch destination for consistency across all three lane-pass
    # variants. The contact_grid (where the defender intercepts) is computed
    # from the same target.
    rr_to = phase.get("rr_to") or {}
    catch_target: GridCoord = {
        "x": float(rr_to.get("x", rr_coord["x"])),
        "y": float(rr_to.get("y", rr_coord["y"])),
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
    archetype[rr_id] = _rr_payload_archetype(phase)
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
        # Non-blocking: show the callout without freezing the court. See
        # Announcement_System.md §Secondary-style announcements — freeze status.
        "hold_ms": 1000,
        "non_blocking": True,
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

    # RR moves to the full catch_grid even though the pass gets batted —
    # matches the shot-branch destination.
    rr_to = phase.get("rr_to") or {}
    catch_target: GridCoord = {
        "x": float(rr_to.get("x", rr_coord["x"])),
        "y": float(rr_to.get("y", rr_coord["y"])),
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
    archetype[rr_id] = _rr_payload_archetype(phase)
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
            # Non-blocking: show the callout without freezing the court. See
            # Announcement_System.md §Secondary-style announcements — freeze status.
            "hold_ms": 1000,
            "non_blocking": True,
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
        # Non-blocking: the callout rides alongside the denied-outlet beat instead of
        # freezing the court for a full second. See Announcement_System.md.
        "hold_ms": 1000,
        "non_blocking": True,
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
        from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot
        away_team_id = getattr(getattr(game, "away_team", None), "team_id", None)
        offense_team_id = getattr(getattr(game, "offense_team", None), "team_id", None)
        away_offense = bool(
            away_team_id is not None
            and offense_team_id is not None
            and str(offense_team_id) == str(away_team_id)
        )
        inject_shot_micro_before_post_shot(
            steps, turn_result, off_lineup, def_lineup, away_offense,
        )
        _build_post_shot_sub_steps(
            steps, turn_result, off_lineup, def_lineup, away_offense,
        )
    except Exception:
        logging.exception("FB post-shot sub-steps failed")
    _warn_if_post_shot_sfx_missing(turn_result, steps)

    _stamp_hco_setup(turn_result, game, steps)

    return steps


# --- Lane pass → RR resolution (RR + Triangle + future FB plays) ------------


def is_lane_pass_to_rr_resolution_turn(
    turn_result: Dict[str, Any],
    fb_roles: Optional[Dict[str, Any]] = None,
) -> bool:
    """True when post-outlet animation should use the shared lane-pass emitter.

    Rim Runner always uses this path after a non-denied outlet (hold-up,
    intercept, bat OOB, or lane pass + shot). Triangle uses it only when
    ``rim_runner_pass_attempted`` is set (open-lane quick shot); the full
    Triangle setup/decision tree omits ``triangle_setup_phase`` and sets
    ``pass_attempted`` false instead.
    """
    roles = fb_roles if fb_roles is not None else (turn_result.get("roles") or {})
    if roles.get("triangle_setup_phase") or turn_result.get("triangle_setup_phase"):
        return False
    if turn_result.get("triangle_enter_hco"):
        return False
    if turn_result.get("rim_runner_outlet_failed"):
        return False

    play = turn_result.get("fast_break_play")
    if play == "triangle":
        return bool(turn_result.get("rim_runner_pass_attempted"))
    if play == "rim_runner":
        return True
    return bool(turn_result.get("rim_runner_pass_attempted"))


def _build_finisher_drive_resolution_steps(
    *,
    turn_result: Dict[str, Any],
    game: Any,
    start_coords: Dict[str, GridCoord],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
    clock_remaining: float,
    shot_clock_remaining: float,
    fb_roles: Dict[str, Any],
) -> Optional[List[AnimationStep]]:
    """Drive-resolution steps after lane pass (RR / Triangle finisher).

    Thin adapter over the universal ``build_fb_drive_resolution_steps``: derives
    the RR/Triangle ``stealer_id`` (shooter / burst-phase rr) and end coords
    (``rr_end_coords``), then delegates the meet / neutral / NO_MEET drive
    orchestration to the shared emitter. RR/Triangle announce "Fast Break!" on
    the burst/lane pass, so the drive steps pass
    ``stamp_fb_start_announcement=False`` and don't re-stamp it.
    """
    from BackEnd.engine.fb_drive_step_emitter import build_fb_drive_resolution_steps

    phase = fb_roles.get("rim_runner_burst_phase") or {}
    stealer_id = (
        _safe_id(turn_result.get("shooter"))
        or _safe_id(fb_roles.get("shooter"))
        or _safe_id(phase.get("rr_id"))
    )

    raw_end_coords = turn_result.get("rr_end_coords") or {}
    end_coords: Dict[str, GridCoord] = {}
    for pid, coord in raw_end_coords.items():
        if isinstance(coord, dict) and "x" in coord and "y" in coord:
            end_coords[str(pid)] = {"x": float(coord["x"]), "y": float(coord["y"])}
    for pid, sc in start_coords.items():
        end_coords.setdefault(pid, dict(sc))

    return build_fb_drive_resolution_steps(
        turn_result=turn_result,
        game=game,
        start_coords=start_coords,
        end_coords=end_coords,
        stealer_id=stealer_id or "",
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        is_away_offense=is_away_offense,
        clock_remaining=clock_remaining,
        shot_clock_remaining=shot_clock_remaining,
        fb_roles=fb_roles,
        kind_prefix="rim_runner",
        stamp_fb_start_announcement=False,
        suppress_stinger=False,
    )


def append_lane_pass_to_rr_resolution_steps(
    *,
    turn_result: Dict[str, Any],
    game: Any,
    steps: List[AnimationStep],
    last_end_coords: Dict[str, GridCoord],
    elapsed: float,
    clock_remaining: float,
    shot_clock_remaining: float,
    fb_roles: Dict[str, Any],
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    is_away_offense: bool,
) -> Optional[List[AnimationStep]]:
    """Append post-outlet lane-pass resolution steps and finalize.

    Shared by Rim Runner and Triangle (and future FB plays that reuse
    ``resolve_rim_runner_fast_break`` lane-pass shot resolution). Caller
    must already have appended burst and optional outlet pass steps.

    Branches: hold-up, intercept, bat OOB, lane pass + shot motion.
    """
    no_lane_pass = bool(turn_result.get("rim_runner_no_lane_pass"))
    interception = bool(turn_result.get("rim_runner_interception"))
    bat_oob = bool(turn_result.get("rim_runner_bat_oob"))

    clock_at = clock_remaining - elapsed
    sc_at = shot_clock_remaining - elapsed
    coords = dict(last_end_coords)
    next_idx = len(steps) + 1

    if interception:
        intercept = _build_lane_pass_intercepted_step(
            turn_result=turn_result,
            fb_roles=fb_roles,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_start_coords=coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_at,
            shot_clock_remaining_at_start=sc_at,
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
            step_start_coords=coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_at,
            shot_clock_remaining_at_start=sc_at,
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
            step_start_coords=coords,
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_at,
            shot_clock_remaining_at_start=sc_at,
        )
        if hold_up is not None:
            steps.append(hold_up)
        return _finalize_rr_steps(turn_result, game, steps)

    clock_at = clock_remaining - elapsed
    sc_at = shot_clock_remaining - elapsed

    lane_pass = _build_lane_pass_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_start_coords=coords,
        is_away_offense=is_away_offense,
        clock_remaining_at_start=clock_at,
        shot_clock_remaining_at_start=sc_at,
        next_step_index=next_idx,
    )
    if lane_pass is None:
        return None
    steps.append(lane_pass)
    elapsed += float(lane_pass["end"]["time_elapsed"])
    coords = dict(lane_pass["end"]["coords"])
    clock_at = clock_remaining - elapsed
    sc_at = shot_clock_remaining - elapsed

    if turn_result.get("fb_drive_resolution"):
        dr_steps = _build_finisher_drive_resolution_steps(
            turn_result=turn_result,
            game=game,
            start_coords=coords,
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            is_away_offense=is_away_offense,
            clock_remaining=clock_at,
            shot_clock_remaining=sc_at,
            fb_roles=fb_roles,
        )
        if dr_steps:
            from BackEnd.utils.animation_step_helpers import (
                rebase_animation_step_next_indices,
            )

            rebase_animation_step_next_indices(dr_steps, len(steps))
            steps.extend(dr_steps)
            return _finalize_rr_steps(turn_result, game, steps)

    shot_motion = _build_shot_motion_step(
        turn_result=turn_result,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        step_start_coords=coords,
        clock_remaining_at_start=clock_at,
        shot_clock_remaining_at_start=sc_at,
    )
    if shot_motion is not None:
        steps.append(shot_motion)

    return _finalize_rr_steps(turn_result, game, steps)


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
        logging.warning(
            "🚨 [RR EMITTER NULL] guard=fast_break_play_mismatch "
            "fast_break_play=%s result_type=%s — FE will fall to LEGACY_HANDLER",
            turn_result.get("fast_break_play"), turn_result.get("result_type"),
        )
        return None

    fb_roles = turn_result.get("roles") or {}
    burst_phase = fb_roles.get("rim_runner_burst_phase")
    if not burst_phase:
        logging.warning(
            "🚨 [RR EMITTER NULL] guard=missing_burst_phase result_type=%s "
            "fb_roles_keys=%s — FE will fall to LEGACY_HANDLER",
            turn_result.get("result_type"),
            list(fb_roles.keys()) if isinstance(fb_roles, dict) else None,
        )
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
        logging.warning(
            "🚨 [RR EMITTER NULL] guard=empty_start_coords result_type=%s "
            "— FE will fall to LEGACY_HANDLER",
            turn_result.get("result_type"),
        )
        return None

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    outlet_failed = bool(turn_result.get("rim_runner_outlet_failed"))

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

    return append_lane_pass_to_rr_resolution_steps(
        turn_result=turn_result,
        game=game,
        steps=steps,
        last_end_coords=last_end_coords,
        elapsed=elapsed,
        clock_remaining=clock_remaining,
        shot_clock_remaining=shot_clock_remaining,
        fb_roles=fb_roles,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        is_away_offense=is_away_offense,
    )
