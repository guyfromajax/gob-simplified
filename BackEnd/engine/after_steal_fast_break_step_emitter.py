"""After-Steal Fast Break animation step emitter.

Converts an ``after_steal`` Fast Break ``turn_result`` into the unified
``AnimationStep[]`` payload defined in
``BackEnd/utils/animation_step_schema.py``.

UESS compliance contract — this turn type has NO frontend logic. All
choreography (positions, transitions, announcements, SFX) is emitted as
schema steps; the FE is a pure renderer driven by ``runStepAnnouncement``
and the step dispatcher.

Branches
--------
- **Shot Attempt** (MAKE / MISS / BLOCK):
    step 0 steal-entry burst (stealer → drive target, defenders chase, ball
    attached, "Fast Break!" announcement on start) → step 1 shot motion
    (shooter settles at shot spot; optional stopper closes out) → post-shot
    sub-steps via skeleton's ``_build_post_shot_sub_steps`` (ball flight,
    variant rim animation incl. RATTLE hops, then hold-with-"Fast Break
    Score!" on make or bounce on miss). Shooting-foul-on-miss announcement
    stamped on the terminal step.
- **Defensive Stop** (``result_type == "DEFENSIVE_STOP"``):
    step 0 burst → step 1 step-back (stealer steps back to top-of-key,
    stopper closes 2 spots in front; the step's ``end.coords`` is the
    authoritative coord snapshot for the next HCO turn's handoff). The
    "Great Stop!" secondary announcement is stamped on step 1's
    ``end.announcement``. Implicit end → caller transitions to HCO.

Notes
-----
- Make announcement text is "Fast Break Score!" (and "Fast Break Score!
  And 1!" for and-1) per design — overrides the default "It's Good!" used
  by HCO / OREB. Implemented by post-processing the hold step emitted by
  the shared helper.
- Step-back ``end.coords`` capture is intentional and load-bearing: the
  next HCO turn's first step (handoff) consumes these as its start coords
  so the BH and stopper don't teleport. Fixing this for after_steal also
  establishes the pattern for the related HCO-steal teleport bug.
- The "Fast Break!" headline (secondary tier) is embedded in the burst
  step's ``start.announcement`` so the FE's ``announceGameEvent`` path no
  longer needs to fire it for steal-initiated FBs. Idempotency on the FE
  is via ``turn._contextAnnouncementsShown`` (existing guard).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    AWAY_TOP_KEY,
    HOME_RIM_COORDS,
    HOME_TOP_KEY,
    HCO_STEP_T_FLOOR_GAME_SECONDS,
)
from BackEnd.engine.skeleton_step_emitter import (
    _build_post_shot_sub_steps,
    _stamp_shooting_foul_on_miss_end,
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


# Hold durations (game-seconds). The FE's ``runStepAnnouncement`` resumes
# clocks after ``hold_ms`` wall-clock, so the step T can be 0 for the
# announcement-only beats below.
FB_ANNOUNCE_HOLD_MS: float = 1000.0
DEFENSIVE_STOP_HOLD_MS: float = 1000.0
STEP_BACK_STEP_T: float = HCO_STEP_T_FLOOR_GAME_SECONDS  # 0.5 game-sec floor


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _player_iter(off_lineup: Dict[str, Any], def_lineup: Dict[str, Any]):
    for lineup in (off_lineup, def_lineup):
        for pos, player in (lineup or {}).items():
            if player is None:
                continue
            yield player


def _build_start_coords(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prior_final_coords: Dict[str, Any],
) -> Dict[str, GridCoord]:
    """Seed all-player start coords from the prior turn's final_coords (the
    STEAL turn's post-snap positions). Falls back to ``player.coords`` when a
    player is missing from the prior snapshot.
    """
    start: Dict[str, GridCoord] = {}
    for player in _player_iter(off_lineup, def_lineup):
        pid = _safe_id(player)
        if not pid:
            continue
        coord = None
        if isinstance(prior_final_coords, dict):
            entry = prior_final_coords.get(pid) or prior_final_coords.get(str(pid))
            if isinstance(entry, dict) and "x" in entry and "y" in entry:
                coord = {"x": float(entry["x"]), "y": float(entry["y"])}
        if coord is None:
            raw = getattr(player, "coords", None) or {}
            if isinstance(raw, dict) and "x" in raw and "y" in raw:
                coord = {"x": float(raw["x"]), "y": float(raw["y"])}
        if coord is not None:
            start[pid] = coord
    return start


def _stationary_maps(coords: Dict[str, GridCoord]):
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in coords}
    archetypes: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in coords}
    destinations: Dict[str, Optional[GridCoord]] = {pid: None for pid in coords}
    return actions, archetypes, destinations


def _fb_secondary_announcement(team: str) -> Announcement:
    """Burst step start announcement: ``Fast Break!`` (secondary tier)."""
    return {
        "text": "Fast Break!",
        "team": team,
        "hold_ms": FB_ANNOUNCE_HOLD_MS,
        "style": "primary",  # tier resolved by FE based on payload
        "tier": "secondary",
        # FE secondary headline resolver picks SFX from gameSfx.js
        # (fast-break-braddock.mp3) when meta.sfx absent on the payload.
    }


def _great_stop_announcement(team: str, stopper_id: Optional[str]) -> Announcement:
    """Step-back step end announcement: ``Great Stop!`` (secondary tier,
    stopper headshot if available)."""
    ann: Announcement = {
        "text": "Great Stop!",
        "team": team,
        "hold_ms": DEFENSIVE_STOP_HOLD_MS,
        "style": "primary",
        "tier": "secondary",
    }
    if stopper_id:
        ann["player_data"] = {"playerId": str(stopper_id)}
    return ann


# --- Step builders ---------------------------------------------------------


def _build_steal_entry_burst_step(
    *,
    start_coords: Dict[str, GridCoord],
    stealer_id: str,
    stealer_target: GridCoord,
    getback_defender_ids: List[str],
    is_away_offense: bool,
    clock_remaining: float,
    shot_clock_remaining: float,
    next_step_index: int,
) -> AnimationStep:
    """Step 0: stealer bursts toward the basket, get-back defenders chase.

    Ball is already attached to the stealer (from the prior STEAL turn).
    Get-back defenders' end coords are sourced from the prior shot turn's
    ``offense_getback_coords`` (carried into ``getback_defender_ids`` here)
    — they tween at ``sprint`` archetype toward those spots in parallel
    with the stealer's burst.

    The ``Fast Break!`` secondary announcement is stamped on ``start`` so
    the FE plays it as the burst begins; ``runStepAnnouncement`` does NOT
    pause clocks for a secondary headline, so wall-clock overlap with the
    burst tween is intentional.
    """
    actions, archetypes, destinations = _stationary_maps(start_coords)
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }

    # Stealer is the gating mover; sprint archetype, end at target.
    actions[stealer_id] = "sprint"
    archetypes[stealer_id] = "sprint"
    destinations[stealer_id] = dict(stealer_target)
    end_coords[stealer_id] = dict(stealer_target)

    # Get-back defenders chase at sprint. Their end coords stay at start
    # (no precomputed targets here — they'll settle in the shot-motion
    # step's overlay below); they just need to look like they're running.
    for did in getback_defender_ids:
        if did in start_coords:
            actions[did] = "sprint"
            archetypes[did] = "sprint"

    t = max(0.4, STEP_BACK_STEP_T)
    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": stealer_id,
            "target_coords": dict(stealer_target),
            "kind": "steal_entry_burst",
        },
    }

    team = "away" if is_away_offense else "home"

    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetypes,
        "ball": {"owner_player_id": stealer_id},
        "clock": {
            "clock_remaining": float(clock_remaining),
            "shot_clock_remaining": float(shot_clock_remaining),
        },
        "advance_trigger": advance_trigger,
        "announcement": _fb_secondary_announcement(team),
    }
    end: StepEnd = {
        "coords": dict(end_coords),
        "ball": {"owner_player_id": stealer_id},
        "time_elapsed": float(t),
        "clock": {
            "clock_remaining": float(clock_remaining) - t,
            "shot_clock_remaining": float(shot_clock_remaining) - t,
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    return {"start": start, "end": end}


def _build_shot_motion_step(
    *,
    start_coords: Dict[str, GridCoord],
    shooter_id: str,
    shot_spot: GridCoord,
    defender_id: Optional[str],
    stopper_id: Optional[str],
    clock_remaining: float,
    shot_clock_remaining: float,
    next_step_index: int,
) -> AnimationStep:
    """Shot motion: shooter (= stealer) settles at shot spot. If a stopper
    is present, the stopper closes out 2 spots in front of the shooter
    (between shooter and basket). The ball is still attached to the
    shooter; the post-shot sub-step builder will detach it on flight.

    Step T floors at ``HCO_STEP_T_FLOOR_GAME_SECONDS`` so the shoot beat
    reads visibly before the ball detaches.
    """
    actions, archetypes, destinations = _stationary_maps(start_coords)
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }

    # Shooter snaps to the shot spot (small delta from burst end).
    actions[shooter_id] = "shoot"
    archetypes[shooter_id] = "shot_motion"
    destinations[shooter_id] = dict(shot_spot)
    end_coords[shooter_id] = dict(shot_spot)

    # Primary shot defender (if distinct from stopper) closes on shooter.
    if defender_id and defender_id in start_coords and defender_id != shooter_id:
        actions[defender_id] = "guard_ball"
        archetypes[defender_id] = "sprint"

    # Stopper closes 2 grid spots in front of shooter (toward own basket).
    if stopper_id and stopper_id in start_coords:
        # Direction toward own basket from shooter perspective: if home
        # offense is attacking right (rim x=91), stopper is at shot_spot.x+2
        # (between shooter and rim). Mirror for away.
        actions[stopper_id] = "guard_ball"
        archetypes[stopper_id] = "sprint"

    t = STEP_BACK_STEP_T  # short pre-flight beat
    advance_trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": float(t),
        "metadata": {"kind": "shot_motion"},
    }

    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetypes,
        "ball": {"owner_player_id": shooter_id},
        "clock": {
            "clock_remaining": float(clock_remaining),
            "shot_clock_remaining": float(shot_clock_remaining),
        },
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": dict(end_coords),
        "ball": {"owner_player_id": shooter_id},
        "time_elapsed": float(t),
        "clock": {
            "clock_remaining": float(clock_remaining) - t,
            "shot_clock_remaining": float(shot_clock_remaining) - t,
        },
        "next": {"kind": "next_step", "index": next_step_index},
    }
    return {"start": start, "end": end}


def _build_step_back_step(
    *,
    start_coords: Dict[str, GridCoord],
    ball_handler_id: str,
    top_key: GridCoord,
    stopper_id: Optional[str],
    is_away_offense: bool,
    clock_remaining: float,
    shot_clock_remaining: float,
) -> AnimationStep:
    """Defensive Stop branch step 1: ball handler step-backs to top-of-key,
    stopper closes 2 spots in front. The step's ``end.coords`` is THE
    authoritative coord snapshot — the next HCO turn's first step reads
    these as its start coords so the BH and stopper don't teleport on the
    handoff.

    The ``Great Stop!`` secondary announcement is stamped on
    ``end.announcement`` so it fires after the step-back tween settles.
    """
    actions, archetypes, destinations = _stationary_maps(start_coords)
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }

    # BH step-backs to top of key.
    actions[ball_handler_id] = "dribble"
    archetypes[ball_handler_id] = "standard"
    destinations[ball_handler_id] = dict(top_key)
    end_coords[ball_handler_id] = dict(top_key)

    # Stopper closes directly between BH and basket (2 grid spots in front).
    if stopper_id and stopper_id in start_coords:
        stopper_spot: GridCoord = {
            "x": float(top_key["x"]) + (2.0 if not is_away_offense else -2.0),
            "y": float(top_key["y"]),
        }
        actions[stopper_id] = "guard_ball"
        archetypes[stopper_id] = "sprint"
        destinations[stopper_id] = dict(stopper_spot)
        end_coords[stopper_id] = dict(stopper_spot)

    t = STEP_BACK_STEP_T
    advance_trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": ball_handler_id,
            "target_coords": dict(top_key),
            "kind": "step_back",
        },
    }

    team = "home" if is_away_offense else "away"  # defense team

    start: StepStart = {
        "coords": dict(start_coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetypes,
        "ball": {"owner_player_id": ball_handler_id},
        "clock": {
            "clock_remaining": float(clock_remaining),
            "shot_clock_remaining": float(shot_clock_remaining),
        },
        "advance_trigger": advance_trigger,
    }
    end: StepEnd = {
        "coords": dict(end_coords),
        "ball": {"owner_player_id": ball_handler_id},
        "time_elapsed": float(t),
        "clock": {
            "clock_remaining": float(clock_remaining) - t,
            "shot_clock_remaining": float(shot_clock_remaining) - t,
        },
        "next": {
            "kind": "turn_stop",
            "event": "FAST_BREAK",
            "payload": {"result": "DEFENSIVE_STOP"},
        },
        "announcement": _great_stop_announcement(team, stopper_id),
    }
    return {"start": start, "end": end}


# --- Make-text override ----------------------------------------------------


def _override_fb_make_announcement(steps: List[AnimationStep]) -> None:
    """Rewrite the make-hold step's announcement text from
    "It's Good!" → "Fast Break Score!" (and the and-1 variant). The shared
    ``_build_make_hold_sub_step`` (from skeleton) emits the HCO defaults;
    we post-process here so the steal-FB make reads as a fast-break score.

    No-op if there's no make-hold step (e.g., MISS / BLOCK / DEFENSIVE_STOP).
    """
    for step in reversed(steps):
        start = step.get("start") if isinstance(step, dict) else None
        if not isinstance(start, dict):
            continue
        ann = start.get("announcement")
        if not isinstance(ann, dict):
            continue
        text = str(ann.get("text") or "")
        style = str(ann.get("style") or "")
        if style == "and_one" or text.startswith("It's Good! And 1!"):
            ann["text"] = "Fast Break Score! And 1!"
            return
        if style == "primary" and text.startswith("It's Good!"):
            ann["text"] = "Fast Break Score!"
            return


# --- Top-level builder -----------------------------------------------------


def build_after_steal_fast_break_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert an ``after_steal`` FB ``turn_result`` into AnimationStep[].

    Returns ``None`` for unrecognized ``result_type``s or when required
    inputs (stealer ID, prior coords) are missing — caller falls back to
    legacy rendering and a warning is logged.
    """
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type not in ("MAKE", "MISS", "BLOCK", "DEFENSIVE_STOP"):
        logging.warning(
            "🐛 [AFTER_STEAL_NONE site=unsupported_result_type] result_type=%s",
            result_type,
        )
        return None

    roles = turn_result.get("roles") or {}
    stealer_id = (
        _safe_id(turn_result.get("shooter"))
        or _safe_id(roles.get("ball_handler"))
        or _safe_id(roles.get("ball_handler_id"))
    )
    if not stealer_id:
        logging.warning(
            "🐛 [AFTER_STEAL_NONE site=stealer_id_missing] turn_keys=%s",
            list(turn_result.keys())[:10],
        )
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(
        off_team is not None
        and getattr(off_team, "team_id", None)
        == getattr(getattr(game, "away_team", None), "team_id", None)
    )

    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    prior_final_coords = (
        prior_turn.get("final_coords")
        if isinstance(prior_turn, dict)
        else None
    ) or {}

    start_coords = _build_start_coords(off_lineup, def_lineup, prior_final_coords)
    if stealer_id not in start_coords:
        logging.warning(
            "🐛 [AFTER_STEAL_NONE site=stealer_not_in_start_coords] stealer_id=%s start_keys=%s",
            stealer_id, list(start_coords.keys()),
        )
        return None

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    # --- Step 0: steal-entry burst --------------------------------------
    outlet_x = roles.get("ball_handler_outlet_x")
    outlet_y = roles.get("ball_handler_outlet_y")
    if outlet_x is None or outlet_y is None:
        # Fallback: nudge stealer halfway to the rim if backend didn't
        # stamp a target. This shouldn't happen — log loudly.
        rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
        sx = start_coords[stealer_id]["x"]
        sy = start_coords[stealer_id]["y"]
        outlet_x = (sx + rim["x"]) / 2.0
        outlet_y = sy
        logging.warning(
            "🚨 [AFTER_STEAL] ball_handler_outlet_x/y missing on roles — using midpoint fallback to rim"
        )
    stealer_target: GridCoord = {"x": float(outlet_x), "y": float(outlet_y)}

    getback_defender_ids: List[str] = []
    raw_getback = roles.get("getback_player_ids") or []
    for pid in raw_getback:
        sid = _safe_id(pid) if not isinstance(pid, str) else pid
        if sid and sid in start_coords:
            getback_defender_ids.append(sid)

    burst_step = _build_steal_entry_burst_step(
        start_coords=start_coords,
        stealer_id=stealer_id,
        stealer_target=stealer_target,
        getback_defender_ids=getback_defender_ids,
        is_away_offense=is_away_offense,
        clock_remaining=clock_remaining,
        shot_clock_remaining=shot_clock_remaining,
        next_step_index=1,
    )
    steps: List[AnimationStep] = [burst_step]
    elapsed = burst_step["end"]["time_elapsed"]

    # --- Defensive Stop branch ------------------------------------------
    if result_type == "DEFENSIVE_STOP":
        top_key = AWAY_TOP_KEY if is_away_offense else HOME_TOP_KEY
        stopper_id = (
            _safe_id(turn_result.get("stopper_id"))
            or _safe_id(turn_result.get("stopper"))
        )
        step_back = _build_step_back_step(
            start_coords=burst_step["end"]["coords"],
            ball_handler_id=stealer_id,
            top_key=top_key,
            stopper_id=stopper_id,
            is_away_offense=is_away_offense,
            clock_remaining=clock_remaining - elapsed,
            shot_clock_remaining=shot_clock_remaining - elapsed,
        )
        steps.append(step_back)
        return steps

    # --- Shot branch (MAKE / MISS / BLOCK) -------------------------------
    # Determine shot spot. Prefer backend-stamped shooter destination from
    # ``animations[]`` end coord (set by shot_manager) if present; else use
    # the rim coords as a sensible default.
    animations = turn_result.get("animations") or []
    shot_spot: Optional[GridCoord] = None
    for entry in animations:
        if not isinstance(entry, dict):
            continue
        if _safe_id(entry.get("player_id")) == stealer_id:
            end = entry.get("end") or entry.get("end_coords")
            if isinstance(end, dict) and "x" in end and "y" in end:
                shot_spot = {"x": float(end["x"]), "y": float(end["y"])}
                break
    if shot_spot is None:
        rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
        # Step in 1 grid spot from the rim so the shot motion reads.
        shot_spot = {
            "x": float(rim["x"]) + (1.0 if is_away_offense else -1.0),
            "y": float(rim["y"]),
        }

    defender_id = _safe_id(turn_result.get("defender") or roles.get("defender"))
    stopper_id = (
        _safe_id(turn_result.get("stopper_id"))
        or _safe_id(turn_result.get("stopper"))
    )

    shot_step = _build_shot_motion_step(
        start_coords=burst_step["end"]["coords"],
        shooter_id=stealer_id,
        shot_spot=shot_spot,
        defender_id=defender_id,
        stopper_id=stopper_id,
        clock_remaining=clock_remaining - elapsed,
        shot_clock_remaining=shot_clock_remaining - elapsed,
        next_step_index=2,  # placeholder; post-shot sub-steps may extend
    )
    steps.append(shot_step)

    # Hand off to skeleton's post-shot sub-step builder: emits ball_flight
    # (with variant launch + arrival SFX), variant sub-steps (rattle hops,
    # bank settle, airball OOB), and either [hold] on make or [bounce] on
    # miss. Shooting-foul-on-miss announcement is stamped on the terminal
    # step. This is the SAME path HCO / OREB use → fixes the rim SFX bug
    # for steal-FB shots, including RATTLE variants.
    _build_post_shot_sub_steps(
        steps, turn_result, off_lineup, def_lineup, is_away_offense,
    )

    # Override the make-hold announcement text from "It's Good!" to
    # "Fast Break Score!" (per design — steal-FB makes read as fast-break
    # scores rather than HCO makes). No-op for MISS / BLOCK.
    if result_type == "MAKE":
        _override_fb_make_announcement(steps)

    return steps
