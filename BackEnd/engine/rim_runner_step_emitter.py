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

import random
from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    FB_PASS_GRID_SPOTS_PER_GAME_SECOND,
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

    Gate: outlet receiver reaches ``receiver_to``. T = receiver traversal time
    at ``default`` archetype. Other movers' end coords = ``rate × T`` along
    their path (interrupted-coord math); they continue toward the same
    targets through step 1 so the drift reads continuously across the
    outlet pass.

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
        return None
    if "x" not in receiver_to or "y" not in receiver_to:
        return None
    if rr_id not in all_start_coords or receiver_id not in all_start_coords:
        return None

    receiver_start = all_start_coords[receiver_id]
    receiver_end_target: GridCoord = {
        "x": float(receiver_to["x"]),
        "y": float(receiver_to["y"]),
    }
    receiver_player = _player_lookup_by_id(off_lineup, def_lineup, receiver_id)
    receiver_rate = _ag_grid_per_game_sec(receiver_player, "default")
    t = max(0.1, _traversal_seconds(receiver_start, receiver_end_target, receiver_rate))

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

    if "x" in rr_to and "y" in rr_to:
        _commit_mover(
            rr_id,
            {"x": float(rr_to["x"]), "y": float(rr_to["y"])},
            "sprint",
            "sprint",
        )

    _commit_mover(receiver_id, receiver_end_target, "cut", "default")
    end_coords[receiver_id] = dict(receiver_end_target)

    if passer_id and passer_id in all_start_coords:
        actions[passer_id] = "handle_ball"
        archetype[passer_id] = "stationary"

    if defender_id and defender_to and defender_id in all_start_coords:
        d_target: GridCoord = {
            "x": float(defender_to["x"]),
            "y": float(defender_to["y"]),
        }
        _commit_mover(defender_id, d_target, "guard_ball", "default")

    key_ids = {rr_id, receiver_id, passer_id, defender_id}
    for row in other_players:
        pid = _safe_id(row.get("player_id"))
        if not pid or pid in key_ids or pid not in all_start_coords:
            continue
        target: GridCoord = {
            "x": float(row.get("to_x", all_start_coords[pid]["x"])),
            "y": float(row.get("to_y", all_start_coords[pid]["y"])),
        }
        action: PlayerAction = (
            "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
        )
        _commit_mover(pid, target, action, "default")

    skip_outlet_pass = bool(phase.get("skip_outlet_pass"))
    ball_owner = receiver_id if skip_outlet_pass else (passer_id or receiver_id)
    ball_start: BallState = {"owner_player_id": ball_owner}
    ball_end: BallState = {"owner_player_id": ball_owner}

    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": receiver_id,
            "target_coords": dict(receiver_end_target),
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
        return None
    if passer_id not in step_start_coords or receiver_id not in step_start_coords:
        return None

    passer_coord = step_start_coords[passer_id]
    receiver_coord = step_start_coords[receiver_id]

    outlet_score = fb_roles.get("outlet_score")
    pass_rate = (
        float(FB_PASS_GRID_SPOTS_PER_GAME_SECOND)
        if outlet_score is not None and outlet_score >= 50
        else 22.0
    )
    dist = _euclid(passer_coord, receiver_coord)
    t = max(0.5, dist / pass_rate)

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
            arch = "default"
            action = "guard_ball"
        else:
            arch = "default"
            action = (
                "cut" if _is_offense_player(pid, off_lineup) else "guard_offball"
            )
        archetype[pid] = arch
        actions[pid] = action
        destinations[pid] = dict(target)
        rate = _ag_grid_per_game_sec(player, arch)
        end_coords[pid] = _interrupted_coord(step_start_coords[pid], target, rate, t)

    ball_start: BallState = {
        "from_player_id": passer_id,
        "to_player_id": receiver_id,
        "current_coords": dict(passer_coord),
    }
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
    return {"start": start, "end": end}


# --- Main entry point (stub — branch builders land next) -------------------


def build_rim_runner_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert a Rim Runner FB ``turn_result`` into ``AnimationStep[]``.

    Returns ``None`` when required data is missing (graceful degradation
    during parallel-build phase — caller falls back to legacy renderer).

    **STATUS:** Foundation + reusable burst/outlet builders implemented.
    Branch-specific step builders (shot motion, intercept, bat OOB, hold-up,
    outlet denied) are TODO; this entry point currently returns ``None`` so
    callers stay on the legacy path until the branch builders land in the
    follow-up patch.
    """
    fast_break_play = turn_result.get("fast_break_play")
    if fast_break_play != "rim_runner":
        return None

    # TODO(phase 2): dispatch on
    #   rim_runner_outlet_failed / rim_runner_no_lane_pass /
    #   rim_runner_interception / rim_runner_bat_oob / result_type
    # and assemble the per-branch step list using the reusable builders
    # above plus branch-specific builders.
    return None
