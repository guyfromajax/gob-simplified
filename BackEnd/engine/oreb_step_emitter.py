"""OREB animation step emitter.

Builds the multi-step ``AnimationStep[]`` payload for offensive-rebound
turns. The OREB turn produces one of three outcomes; each renders as a
distinct sub-step sequence:

  OREB_KICKOUT
      [rebound_capture] → [kickout_positioning] → [kickout_pass]
      → implicit turn end (next_step past array). The kickout pair is
      built by ``transition_bridge.build_kickout_step`` (same primitive
      HCO uses for its kickout entry).

  PUTBACK_MAKE
      [rebound_capture] → [putback_shoot] → [ball_flight] → [hold]
      → turn_stop SHOT_ATTEMPT (with schema_rendered_arc=True so the FE
      dispatcher's runShotAttempt is a no-op).

  PUTBACK_MISS
      [rebound_capture] → [putback_shoot] → [ball_flight] → [bounce]
      → turn_stop SHOT_ATTEMPT. The OREB turn deliberately ENDS at
      [bounce]; the second rebound (DREB or chained OREB) is dispatched
      as its own next turn — see ``game_manager._build_dreb_turn_from_miss``
      (extended to fire on PUTBACK_MISS) and ``pending_oreb`` chaining
      for the recursive case.

Cross-cutting contract:

- Step 0 ``start.coords`` seeds from ``prior_turn.final_coords`` (= where
  players landed after the prior MISS turn's post-shot sub-steps).
- Ball at step 0 is BallLoose at the prior turn's ``ball_bounce_x/y``;
  ends BallAttached to the rebounder.
- Putback overlays are NOT applied — players hold their post-MISS coords
  through the putback flight (per the OREB design choice to skip overlays
  for the short putback motion).
- Per-action archetypes follow HCO's vocabulary (shoot → shot_motion,
  stationary → stationary, all else → cruise). The rebound capture step
  uses sprint for the rebounder so he reaches the ball at urgency pace.
"""

from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    AWAY_RIM_COORDS,
    BOUNCE_STEP_GAME_SECONDS,
    HCO_STEP_T_FLOOR_GAME_SECONDS,
    HOME_RIM_COORDS,
    MADE_SHOT_SWEET_SPOT_AWAY_RIM,
    MADE_SHOT_SWEET_SPOT_HOME_RIM,
    SHOT_BALL_GRID_PER_GAME_SECOND,
)
from BackEnd.engine.skeleton_step_emitter import _build_make_hold_sub_step
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _player_lookup_by_id,
    rebound_attemptor_ids,
    stamp_rebound_capture_player_motion,
    stamp_tween_durations,
)
from BackEnd.utils.animation_step_schema import (
    AdvanceTrigger,
    AnimationStep,
    BallState,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
)
from BackEnd.utils.transition_bridge import build_kickout_step


_OFFENSE_POSITIONS = ("PG", "SG", "SF", "PF", "C")


# --- Helpers ---------------------------------------------------------------


def _safe_id(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    pid = getattr(obj, "player_id", None)
    return str(pid) if pid is not None else None


def _player_iter(off_lineup: Dict[str, Any], def_lineup: Dict[str, Any]):
    for pos in _OFFENSE_POSITIONS:
        for lineup in (off_lineup, def_lineup):
            player = lineup.get(pos)
            if player is not None:
                yield player


def _build_start_coords_from_prior(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    prior_final_coords: Dict[str, GridCoord],
) -> Dict[str, GridCoord]:
    """Seed step-0 start_coords from ``prior_turn.final_coords`` for all
    10 on-court players. Falls back to ``player.coords`` if a player is
    missing from ``final_coords``.
    """
    out: Dict[str, GridCoord] = {}
    for player in _player_iter(off_lineup, def_lineup):
        pid = _safe_id(player)
        if pid is None:
            continue
        coord = prior_final_coords.get(pid) if isinstance(prior_final_coords, dict) else None
        if not isinstance(coord, dict) or coord.get("x") is None or coord.get("y") is None:
            coord = getattr(player, "coords", None)
        if isinstance(coord, dict) and "x" in coord and "y" in coord:
            out[pid] = {"x": float(coord["x"]), "y": float(coord["y"])}
    return out


def _stationary_maps(coords: Dict[str, GridCoord]):
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in coords}
    archetypes: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in coords}
    destinations: Dict[str, Optional[GridCoord]] = {pid: None for pid in coords}
    return actions, archetypes, destinations


def _rim_coords(is_away_offense: bool) -> GridCoord:
    return dict(AWAY_RIM_COORDS) if is_away_offense else dict(HOME_RIM_COORDS)


def _sweet_spot_coords(is_away_offense: bool) -> GridCoord:
    return (
        dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM)
        if is_away_offense
        else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)
    )


def _shot_attempt_turn_stop(turn_result: Dict[str, Any], result: str) -> NextStep:
    """Build a SHOT_ATTEMPT turn_stop with schema_rendered_arc=True so the FE
    dispatcher's ``runShotAttempt`` doesn't double-render the arc/bounce.
    """
    bx = turn_result.get("ball_bounce_x")
    by = turn_result.get("ball_bounce_y")
    bounce_coords = None
    if bx is not None and by is not None:
        bounce_coords = {"x": float(bx), "y": float(by)}
    payload: Dict[str, Any] = {
        "result": result,
        "shooter_id": _safe_id(turn_result.get("shooter"))
            or str(turn_result.get("rebounderId") or ""),
        "defender_id": _safe_id(turn_result.get("defender")),
        "ball_bounce_coords": bounce_coords,
        "schema_rendered_arc": True,
    }
    return {"kind": "turn_stop", "event": "SHOT_ATTEMPT", "payload": payload}


# --- Sub-step builders -----------------------------------------------------


def _build_rebound_capture_step(
    *,
    start_coords: Dict[str, GridCoord],
    rebounder_id: str,
    bounce_coords: GridCoord,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    clock_remaining: float,
    shot_clock_remaining: float,
    next_step_index: int,
    offense_rebounders: Optional[List[Any]] = None,
    defense_rebounders: Optional[List[Any]] = None,
) -> AnimationStep:
    """Rebound capture: captor sprints to bounce; attemptors collapse near it.

    - Gate: rebounder reaches bounce_coords.
    - Ball: ``BallLoose @ bounce_coords`` → ``BallAttached(rebounder)``.
    - Attemptors: prior MISS ``offense_rebounders`` + ``defense_rebounders``
      (minus captor) → bounce ± (4 x, 6 y) at cruise.
    - Others: stationary at post-MISS coords.
    - SFX cue: ``inside-shot-strong.wav`` on ball arrival (= step-end snap,
      since the ball doesn't move during this step — only the rebounder
      moves to it). Mirrors DREB's ``attack-shot-strong.wav`` cue mechanic.
    """
    rebounder = _player_lookup_by_id(off_lineup, def_lineup, rebounder_id)
    rebounder_start = start_coords.get(rebounder_id)
    if rebounder_start is None:
        # Degenerate input — caller should bail.
        rebounder_start = dict(bounce_coords)

    # T = rebounder's natural travel time at sprint pace.
    sprint_rate = _ag_grid_per_game_sec(rebounder, "sprint")
    dist = _euclid(rebounder_start, bounce_coords)
    natural_t = (dist / sprint_rate) if sprint_rate > 0 else 0.0
    t = max(HCO_STEP_T_FLOOR_GAME_SECONDS, natural_t)

    attemptor_ids = rebound_attemptor_ids(
        offense_rebounders, defense_rebounders, rebounder_id,
    )
    actions, archetypes, destinations = _stationary_maps(start_coords)
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }
    tween_durations: Dict[str, float] = {}
    stamp_rebound_capture_player_motion(
        start_coords=start_coords,
        end_coords=end_coords,
        destinations=destinations,
        actions=actions,
        archetypes=archetypes,
        tween_durations=tween_durations,
        rebounder_id=str(rebounder_id),
        bounce_coords=bounce_coords,
        attemptor_ids=attemptor_ids,
        step_t=float(t),
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )

    trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": str(rebounder_id),
            "target_coords": dict(bounce_coords),
        },
    }

    step: AnimationStep = {
        "start": {
            "coords": {pid: dict(c) for pid, c in start_coords.items()},
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": {"coords": dict(bounce_coords)},
            "clock": {
                "clock_remaining": float(clock_remaining),
                "shot_clock_remaining": float(shot_clock_remaining),
            },
            "advance_trigger": trigger,
            # SFX: rebound capture stinger (Sound_Design_Update.md → OREB).
            # FE fires from the step-end snap path since the ball tween
            # early-returns (ball doesn't move; only the rebounder moves
            # to it). Same wiring DREB uses.
            "sfx_on_ball_arrival": {
                "file": "inside-shot-strong.wav",
                "volume": 0.7,
                "event": "rebound_oreb",
            },
        },
        "end": {
            "coords": end_coords,
            "ball": {"owner_player_id": str(rebounder_id)},
            "time_elapsed": float(t),
            "clock": {
                "clock_remaining": float(clock_remaining) - t,
                "shot_clock_remaining": float(shot_clock_remaining) - t,
            },
            "next": {"kind": "next_step", "index": next_step_index},
        },
    }
    if tween_durations:
        step["start"]["tween_durations"] = tween_durations
    return step


def _build_putback_shoot_step(
    *,
    start_coords: Dict[str, GridCoord],
    shooter_id: str,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    clock_remaining: float,
    shot_clock_remaining: float,
    next_step_index: int,
) -> AnimationStep:
    """The [putback_shoot] step. Shooter (= rebounder) is already at his
    shot spot from the prior [rebound_capture] step, so this step is a
    short pre-flight beat: action=shoot, archetype=shot_motion, no
    movement, ball still attached.

    Step T floors at ``HCO_STEP_T_FLOOR_GAME_SECONDS`` (0.5 game-sec) so
    the shoot beat reads visibly before the ball detaches.
    """
    t = HCO_STEP_T_FLOOR_GAME_SECONDS

    actions, archetypes, destinations = _stationary_maps(start_coords)
    actions[shooter_id] = "shoot"
    archetypes[shooter_id] = "shot_motion"

    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }

    shooter_coord = start_coords.get(shooter_id) or {"x": 50.0, "y": 25.0}
    trigger: AdvanceTrigger = {
        "condition": "player_reaches_position",
        "T_game_seconds": float(t),
        "metadata": {
            "target_player_id": str(shooter_id),
            "target_coords": dict(shooter_coord),
        },
    }

    step: AnimationStep = {
        "start": {
            "coords": {pid: dict(c) for pid, c in start_coords.items()},
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": {"owner_player_id": str(shooter_id)},
            "clock": {
                "clock_remaining": float(clock_remaining),
                "shot_clock_remaining": float(shot_clock_remaining),
            },
            "advance_trigger": trigger,
        },
        "end": {
            "coords": end_coords,
            "ball": {"owner_player_id": str(shooter_id)},
            "time_elapsed": float(t),
            "clock": {
                "clock_remaining": float(clock_remaining) - t,
                "shot_clock_remaining": float(shot_clock_remaining) - t,
            },
            "next": {"kind": "next_step", "index": next_step_index},
        },
    }
    stamp_tween_durations(
        step["start"], end_coords, float(t), off_lineup, def_lineup,
    )
    return step


def _build_ball_flight_step(
    *,
    start_coords: Dict[str, GridCoord],
    shooter_id: str,
    is_away_offense: bool,
    is_make: bool,
    result_type: str,
    clock_remaining: float,
    shot_clock_remaining: float,
    next_step: NextStep,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> AnimationStep:
    """Putback ball-flight step. Ball travels from shot_spot (= shooter
    coord) to MSSS (make) or rim (miss). Game clock burns; shot clock
    pinned. All 10 players hold position (no overlay motion per D2)."""
    shot_spot = start_coords.get(shooter_id) or {"x": 50.0, "y": 25.0}
    flight_end = _sweet_spot_coords(is_away_offense) if is_make else _rim_coords(is_away_offense)
    dist = _euclid(shot_spot, flight_end)
    t = dist / float(SHOT_BALL_GRID_PER_GAME_SECOND) if dist > 0 else 0.0

    actions, archetypes, destinations = _stationary_maps(start_coords)
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }

    trigger: AdvanceTrigger = {
        "condition": "shot_resolved",
        "T_game_seconds": float(t),
        "metadata": {
            "target_coords": dict(flight_end),
            "result": result_type,
        },
    }

    step: AnimationStep = {
        "start": {
            "coords": {pid: dict(c) for pid, c in start_coords.items()},
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": {"coords": dict(shot_spot)},
            "clock": {
                "clock_remaining": float(clock_remaining),
                "shot_clock_remaining": float(shot_clock_remaining),
            },
            "advance_trigger": trigger,
            "ball_motion_style": "shot",
        },
        "end": {
            "coords": end_coords,
            "ball": {"coords": dict(flight_end)},
            "time_elapsed": float(t),
            "clock": {
                # Game clock burns ball-flight time. Shot clock pinned —
                # detach happens at the start of this step (end of putback_shoot).
                "clock_remaining": float(clock_remaining) - t,
                "shot_clock_remaining": float(shot_clock_remaining),
            },
            "next": next_step,
        },
    }
    return step


def _build_bounce_step(
    *,
    start_coords: Dict[str, GridCoord],
    is_away_offense: bool,
    bounce_target: GridCoord,
    clock_remaining: float,
    shot_clock_remaining: float,
    next_step: NextStep,
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
) -> AnimationStep:
    """Putback bounce step (miss only). Ball travels from rim to
    ``bounce_target`` over a fixed 300 ms wall-clock. Players hold."""
    rim = _rim_coords(is_away_offense)
    t = float(BOUNCE_STEP_GAME_SECONDS)

    actions, archetypes, destinations = _stationary_maps(start_coords)
    end_coords: Dict[str, GridCoord] = {
        pid: dict(coord) for pid, coord in start_coords.items()
    }

    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": float(t),
        "metadata": {
            "target_coords": dict(bounce_target),
            "kind": "bounce",
        },
    }

    return {
        "start": {
            "coords": {pid: dict(c) for pid, c in start_coords.items()},
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": {"coords": dict(rim)},
            "clock": {
                "clock_remaining": float(clock_remaining),
                "shot_clock_remaining": float(shot_clock_remaining),
            },
            "advance_trigger": trigger,
        },
        "end": {
            "coords": end_coords,
            "ball": {"coords": dict(bounce_target)},
            "time_elapsed": float(t),
            "clock": {
                "clock_remaining": float(clock_remaining) - t,
                "shot_clock_remaining": float(shot_clock_remaining),
            },
            "next": next_step,
        },
    }


# --- Top-level builder -----------------------------------------------------


def build_oreb_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Convert an OREB turn_result into the unified AnimationStep[] payload.

    Returns None for unrecognized result_types or when required inputs are
    missing (graceful degradation).
    """
    result_type = (turn_result.get("result_type") or "").upper()
    if result_type not in ("OREB_KICKOUT", "PUTBACK_MAKE", "PUTBACK_MISS"):
        return None

    # For PUTBACK_MAKE/MISS the "OREB rebounder" (the player who runs to
    # the bounce in [rebound_capture] and then shoots) is the **shooter** —
    # ``rebounderId`` may be overwritten to the *second* rebounder on
    # PUTBACK_MISS (legacy convention consumed by the DREB trigger). For
    # OREB_KICKOUT there's no shooter; ``rebounderId`` is the kickout
    # passer and stays intact.
    rebounder_id = (
        str(turn_result.get("shooter") or "").strip()
        or str(turn_result.get("rebounderId") or "").strip()
    )
    if not rebounder_id:
        return None

    off_team = getattr(game, "offense_team", None)
    def_team = getattr(game, "defense_team", None)
    off_lineup = getattr(off_team, "lineup", {}) if off_team else {}
    def_lineup = getattr(def_team, "lineup", {}) if def_team else {}
    is_away_offense = bool(
        off_team is not None
        and getattr(off_team, "team_id", None) == getattr(getattr(game, "away_team", None), "team_id", None)
    )

    prior_turns = getattr(game, "turns", None) or []
    prior_turn = prior_turns[-1] if prior_turns else None
    if not isinstance(prior_turn, dict):
        return None

    bx = prior_turn.get("ball_bounce_x")
    by = prior_turn.get("ball_bounce_y")
    if bx is None or by is None:
        return None
    bounce_coords: GridCoord = {"x": float(bx), "y": float(by)}

    prior_final_coords = prior_turn.get("final_coords") or {}
    start_coords = _build_start_coords_from_prior(
        off_lineup, def_lineup, prior_final_coords,
    )
    if not start_coords or rebounder_id not in start_coords:
        return None

    game_state = getattr(game, "game_state", {}) or {}
    clock_remaining = float(game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game_state.get("shot_clock_remaining", 0) or 0)

    # --- Step 0: rebound capture (common to all three paths) ---
    capture_step = _build_rebound_capture_step(
        start_coords=start_coords,
        rebounder_id=rebounder_id,
        bounce_coords=bounce_coords,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        clock_remaining=clock_remaining,
        shot_clock_remaining=shot_clock_remaining,
        next_step_index=1,
        offense_rebounders=prior_turn.get("offense_rebounders"),
        defense_rebounders=prior_turn.get("defense_rebounders"),
    )
    steps: List[AnimationStep] = [capture_step]
    elapsed = capture_step["end"]["time_elapsed"]

    if result_type == "OREB_KICKOUT":
        pg_id = str(turn_result.get("pgId") or "")
        if not pg_id or pg_id == rebounder_id or pg_id not in start_coords:
            # Can't kick out to a missing PG; return capture step only.
            return steps
        # ``build_kickout_step`` produces 2 sub-steps (positioning + pass).
        # Other 8 hold (empty setup_coords → no drift targets).
        kickout_steps = build_kickout_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=capture_step["end"]["coords"],
            bh_id=rebounder_id,
            receiver_id=pg_id,
            setup_coords={},
            is_away_offense=is_away_offense,
            clock_remaining_at_start=clock_remaining - elapsed,
            shot_clock_remaining_at_start=shot_clock_remaining - elapsed,
            next_step_index=1,  # placeholder; rewired below
            metadata_reason="oreb_kickout",
        )
        if not kickout_steps:
            return steps
        # Rewire next-pointers across the appended kickout sub-steps.
        first_kickout_idx = len(steps)
        for offset, kstep in enumerate(kickout_steps):
            if offset < len(kickout_steps) - 1:
                kstep["end"]["next"] = {
                    "kind": "next_step",
                    "index": first_kickout_idx + offset + 1,
                }
            else:
                # Last kickout sub-step: implicit end of turn.
                kstep["end"]["next"] = {"kind": "next_step", "index": 999}
        capture_step["end"]["next"] = {"kind": "next_step", "index": first_kickout_idx}
        steps.extend(kickout_steps)
        return steps

    # PUTBACK_MAKE / PUTBACK_MISS share [putback_shoot] + [ball_flight];
    # MAKE adds [hold], MISS adds [bounce].
    is_make = result_type == "PUTBACK_MAKE"

    shoot_step = _build_putback_shoot_step(
        start_coords=capture_step["end"]["coords"],
        shooter_id=rebounder_id,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        clock_remaining=clock_remaining - elapsed,
        shot_clock_remaining=shot_clock_remaining - elapsed,
        next_step_index=2,
    )
    capture_step["end"]["next"] = {"kind": "next_step", "index": 1}
    steps.append(shoot_step)
    elapsed += shoot_step["end"]["time_elapsed"]

    # Decide flight step's `next` based on outcome.
    if is_make:
        flight_next: NextStep = {"kind": "next_step", "index": 3}  # → hold
    else:
        flight_next = {"kind": "next_step", "index": 3}  # → bounce

    flight_step = _build_ball_flight_step(
        start_coords=shoot_step["end"]["coords"],
        shooter_id=rebounder_id,
        is_away_offense=is_away_offense,
        is_make=is_make,
        result_type=result_type,
        clock_remaining=clock_remaining - elapsed,
        shot_clock_remaining=shot_clock_remaining - elapsed,
        next_step=flight_next,
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )
    steps.append(flight_step)
    elapsed += flight_step["end"]["time_elapsed"]

    if is_make:
        # [hold] step — 1000 ms "It's Good!" beat (clocks paused).
        hold_step = _build_make_hold_sub_step(
            prev_end_coords=dict(flight_step["end"]["coords"]),
            prev_clock=dict(flight_step["end"]["clock"]),
            ball_coord=_sweet_spot_coords(is_away_offense),
            shooter_id=str(rebounder_id),
            away_offense=is_away_offense,
            turn_result=turn_result,
            next_step=_shot_attempt_turn_stop(turn_result, "MAKE"),
        )
        steps.append(hold_step)
        return steps

    # PUTBACK_MISS → [bounce] then turn_stop SHOT_ATTEMPT. The OREB turn
    # ENDS HERE; second rebound (DREB or chained OREB) becomes its own
    # next turn — see ``game_manager._build_dreb_turn_from_miss``
    # (extended to fire on PUTBACK_MISS) for the DREB branch.
    sbx = turn_result.get("ball_bounce_x")
    sby = turn_result.get("ball_bounce_y")
    if sbx is None or sby is None:
        # No second-bounce coords on the turn — emit ball_flight ending the turn.
        flight_step["end"]["next"] = _shot_attempt_turn_stop(turn_result, "MISS")
        return steps
    bounce_target: GridCoord = {"x": float(sbx), "y": float(sby)}

    bounce_step = _build_bounce_step(
        start_coords=flight_step["end"]["coords"],
        is_away_offense=is_away_offense,
        bounce_target=bounce_target,
        clock_remaining=clock_remaining - elapsed,
        shot_clock_remaining=shot_clock_remaining - elapsed,
        next_step=_shot_attempt_turn_stop(turn_result, "MISS"),
        off_lineup=off_lineup,
        def_lineup=def_lineup,
    )
    steps.append(bounce_step)
    return steps
