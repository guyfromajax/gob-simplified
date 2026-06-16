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
    BANK_MAKE_SETTLE_GAME_SECONDS,
    BANK_MISS_GRAZE_GAME_SECONDS,
    BOUNCE_STEP_GAME_SECONDS,
    HCO_STEP_T_FLOOR_GAME_SECONDS,
    HOME_RIM_COORDS,
    MADE_SHOT_SWEET_SPOT_AWAY_RIM,
    MADE_SHOT_SWEET_SPOT_HOME_RIM,
    RATTLE_HOP_GAME_SECONDS,
    RATTLE_MAKE_SETTLE_GAME_SECONDS,
    SHOT_BALL_GRID_PER_GAME_SECOND,
)
from BackEnd.engine.skeleton_step_emitter import (
    _RATTLE_VARIANTS,
    _build_ball_motion_sub_step,
    _build_make_hold_sub_step,
    _rattle_hop_targets,
    _stamp_shooting_foul_on_miss_end,
    _variant_flight_end,
)
from BackEnd.utils.animation_step_helpers import (
    _ag_grid_per_game_sec,
    _euclid,
    _player_lookup_by_id,
    rattle_hop_sfx,
    rattle_make_settle_sfx,
    rebound_attemptor_ids,
    shot_followup_timed_sfx,
    shot_launch_sfx,
    shot_result_sfx,
    stamp_hot_shot_trail_metadata,
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
    is_away_offense: bool,
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
            # SFX: rebound capture stinger (SFX_System.md → OREB).
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
            # "Rebound!" headline — OREB rebounder is on the OFFENSIVE team
            # (same as away_offense). Mirrors DREB; fires after sprite snap
            # so it lands when the rebounder visually has the ball.
            "announcement": {
                "text": "Rebound!",
                "team": "away" if is_away_offense else "home",
                "hold_ms": 1000,
                "style": "primary",
                "player_data": {"playerId": str(rebounder_id)},
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
    turn_result: Optional[Dict[str, Any]] = None,
    flight_end: Optional[GridCoord] = None,
) -> AnimationStep:
    """Putback ball-flight step. Ball travels from shot_spot (= shooter
    coord) to ``flight_end`` — defaults to MSSS (make) / rim (miss), but
    callers pass a variant-specific terminal (rattle start, bank point) so
    the post-flight rim-action sub-steps continue from the right spot.
    Game clock burns; shot clock pinned. All 10 players hold position.

    Stamps the same SFX cues as the skeleton emitter's [ball_flight]
    (audit bug 4 — putback shots were silent because OREB has its own
    builder that didn't wire SFX):
      - ``sfx_on_ball_release`` — shot launch SFX (tier by shot score)
      - ``sfx_on_ball_arrival`` — variant-aware arrival cue (None for
        RATTLE — those fire per-hop on the rim-action sub-steps)
      - ``timed_sfx`` — secondary swish for BANK_MAKE / BACK_OF_RIM
    """
    shot_spot = start_coords.get(shooter_id) or {"x": 50.0, "y": 25.0}
    if flight_end is None:
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
    if turn_result:
        stamp_hot_shot_trail_metadata(
            trigger["metadata"],
            turn_result.get("shot_score_pre_defense"),
        )

    shot_variant = (turn_result or {}).get("shot_variant") if turn_result else None
    # The SFX helpers branch on a normalized MAKE/MISS (the PUTBACK_MAKE/MISS
    # result_type would miss the make/miss fallback in shot_result_sfx and the
    # BANK_MAKE/BACK_OF_RIM follow-up in shot_followup_timed_sfx).
    sfx_result = "MAKE" if is_make else "MISS"
    launch_sfx = shot_launch_sfx(
        (turn_result or {}).get("shot_score_pre_defense") if turn_result else None
    )
    arrival_sfx = shot_result_sfx(
        shot_variant,
        sfx_result,
        bank_miss_sfx_file=(turn_result or {}).get("shot_variant_bank_miss_sfx_file")
        if turn_result else None,
    )
    timed_sfx = shot_followup_timed_sfx(shot_variant, sfx_result)

    start_block: Dict[str, Any] = {
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
    }
    if launch_sfx:
        start_block["sfx_on_ball_release"] = launch_sfx
    if arrival_sfx:
        start_block["sfx_on_ball_arrival"] = arrival_sfx
    if timed_sfx:
        start_block["timed_sfx"] = timed_sfx

    step: AnimationStep = {
        "start": start_block,
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
    ball_start: Optional[GridCoord] = None,
) -> AnimationStep:
    """Putback bounce step (miss only). Ball travels from its current
    position (``ball_start``, default rim) to ``bounce_target`` over a
    fixed 300 ms wall-clock. Players hold.

    ``ball_start`` defaults to the rim for the legacy swish/clank/back-of-rim
    flight (which ends at the rim), but variant misses pass the ball's actual
    post-rim-action spot (last rattle hop, bank-miss graze) so the bounce
    doesn't teleport.
    """
    rim = dict(ball_start) if ball_start is not None else _rim_coords(is_away_offense)
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
    import logging as _oreb_log

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
        _oreb_log.warning(
            "🐛 [OREB_NONE site=rebounder_id_missing] result_type=%s shooter=%s rebounderId=%s",
            result_type, turn_result.get("shooter"), turn_result.get("rebounderId"),
        )
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
        _oreb_log.warning(
            "🐛 [OREB_NONE site=no_prior_turn] result_type=%s rebounder_id=%s",
            result_type, rebounder_id,
        )
        return None

    bx = prior_turn.get("ball_bounce_x")
    by = prior_turn.get("ball_bounce_y")
    if bx is None or by is None:
        _oreb_log.warning(
            "🐛 [OREB_NONE site=prior_bounce_missing] result_type=%s prior_turn_type=%s prior_result_type=%s bx=%s by=%s",
            result_type,
            prior_turn.get("current_turn"),
            prior_turn.get("result_type"),
            bx, by,
        )
        return None
    bounce_coords: GridCoord = {"x": float(bx), "y": float(by)}

    prior_final_coords = prior_turn.get("final_coords") or {}
    start_coords = _build_start_coords_from_prior(
        off_lineup, def_lineup, prior_final_coords,
    )
    if not start_coords or rebounder_id not in start_coords:
        _oreb_log.warning(
            "🐛 [OREB_NONE site=rebounder_not_in_start_coords] result_type=%s rebounder_id=%s start_coords_count=%d in_coords=%s",
            result_type, rebounder_id, len(start_coords),
            rebounder_id in start_coords,
        )
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
        is_away_offense=is_away_offense,
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
        # OREB is emitted before the next HCO skeleton exists, so the shared
        # kickout target helper falls back to organic HCO lane drift for
        # non-core players.
        kickout_steps = build_kickout_step(
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            start_coords=capture_step["end"]["coords"],
            bh_id=rebounder_id,
            receiver_id=pg_id,
            setup_coords=None,
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

    # --- [ball_flight] + variant rim action -------------------------------
    # Rattle / bank variants terminate the flight at their start point
    # (rattle start coord / bank point) so the per-hop / settle / graze
    # sub-steps continue from there. Other variants (swish, clank,
    # back-of-rim, airball) keep the legacy MSSS (make) / rim (miss) target.
    norm_result = "MAKE" if is_make else "MISS"
    shot_variant = turn_result.get("shot_variant")
    variant_upper = (shot_variant or "").upper()
    is_rattle = variant_upper in _RATTLE_VARIANTS
    is_bank_make = variant_upper == "BANK_MAKE"
    is_bank_miss = variant_upper == "BANK_MISS"

    flight_end_override: Optional[GridCoord] = None
    if is_rattle or is_bank_make or is_bank_miss:
        flight_end_override = _variant_flight_end(
            shot_variant, norm_result, is_away_offense, turn_result,
        )

    flight_step = _build_ball_flight_step(
        start_coords=shoot_step["end"]["coords"],
        shooter_id=rebounder_id,
        is_away_offense=is_away_offense,
        is_make=is_make,
        result_type=result_type,
        clock_remaining=clock_remaining - elapsed,
        shot_clock_remaining=shot_clock_remaining - elapsed,
        next_step={"kind": "next_step", "index": 3},  # placeholder; rewired below
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        turn_result=turn_result,
        flight_end=flight_end_override,
    )
    steps.append(flight_step)
    elapsed += flight_step["end"]["time_elapsed"]

    # Cursor tracks ball + clock as we append variant rim-action sub-steps
    # after the flight. All 10 players hold; game clock burns, shot pinned.
    cursor_ball = dict(flight_step["end"]["ball"]["coords"])
    cursor_coords = dict(flight_step["end"]["coords"])
    cursor_clock = dict(flight_step["end"]["clock"])
    prev_step = flight_step

    def _append_variant_step(*, ball_end, step_t, trigger_kind, sfx_arrival=None):
        """Append a stationary ball-motion sub-step (rattle hop / settle /
        bank graze) and rewire the previous step's next pointer to it."""
        nonlocal cursor_ball, cursor_coords, cursor_clock, prev_step
        idx = len(steps)
        trigger: AdvanceTrigger = {
            "condition": "fixed_duration",
            "T_game_seconds": float(step_t),
            "metadata": {"target_coords": dict(ball_end), "kind": trigger_kind},
        }
        step = _build_ball_motion_sub_step(
            start_coords_seed=dict(cursor_coords),
            overlay_players={},  # putback: all players hold
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            step_t=float(step_t),
            ball_start_coord=dict(cursor_ball),
            ball_end_coord=dict(ball_end),
            clock_start=dict(cursor_clock),
            advance_trigger=trigger,
            ball_motion_style=None,
            next_step={"kind": "next_step", "index": idx + 1},  # placeholder
            sfx_on_ball_arrival=sfx_arrival,
        )
        prev_step["end"]["next"] = {"kind": "next_step", "index": idx}
        steps.append(step)
        cursor_ball = dict(ball_end)
        cursor_coords = dict(step["end"]["coords"])
        cursor_clock = dict(step["end"]["clock"])
        prev_step = step

    if is_rattle:
        # Per-hop sub-steps — rattle-leather.wav fires at each hop arrival
        # (this is the SFX/rim-action that was missing on putbacks).
        for hop_target in _rattle_hop_targets(variant_upper, is_away_offense, turn_result):
            _append_variant_step(
                ball_end=hop_target,
                step_t=RATTLE_HOP_GAME_SECONDS,
                trigger_kind="rattle_hop",
                sfx_arrival=rattle_hop_sfx(),
            )
        if is_make:
            # Settle into MSSS with the terminal swish at arrival.
            _append_variant_step(
                ball_end=_sweet_spot_coords(is_away_offense),
                step_t=RATTLE_MAKE_SETTLE_GAME_SECONDS,
                trigger_kind="rattle_settle",
                sfx_arrival=rattle_make_settle_sfx(),
            )
    elif is_bank_make:
        # Bank → MSSS settle. Arrival SFX (bb-rim-swish + delayed swish) is
        # already on the flight step via arrival_sfx + timed_sfx.
        _append_variant_step(
            ball_end=_sweet_spot_coords(is_away_offense),
            step_t=BANK_MAKE_SETTLE_GAME_SECONDS,
            trigger_kind="bank_settle",
        )
    elif is_bank_miss:
        # Bank → rim-graze (per-shot rolled offsets). bb-clank already played
        # on the flight step's arrival cue.
        msss = _sweet_spot_coords(is_away_offense)
        graze: GridCoord = {
            "x": float(msss["x"]) + float(
                turn_result.get("shot_variant_backboard_miss_rim_offset_x") or 0
            ),
            "y": float(msss["y"]) + float(
                turn_result.get("shot_variant_backboard_miss_rim_offset_y") or 0
            ),
        }
        _append_variant_step(
            ball_end=graze,
            step_t=BANK_MISS_GRAZE_GAME_SECONDS,
            trigger_kind="bank_graze",
        )

    if is_make:
        # [hold] step — 1000 ms "It's Good!" beat (clocks paused). Ball is at
        # MSSS by now (settle steps moved it there for rattle / bank makes).
        hold_step = _build_make_hold_sub_step(
            prev_end_coords=dict(cursor_coords),
            prev_clock=dict(cursor_clock),
            ball_coord=_sweet_spot_coords(is_away_offense),
            shooter_id=str(rebounder_id),
            away_offense=is_away_offense,
            turn_result=turn_result,
            next_step=_shot_attempt_turn_stop(turn_result, "MAKE"),
        )
        prev_step["end"]["next"] = {"kind": "next_step", "index": len(steps)}
        steps.append(hold_step)
        return steps

    # PUTBACK_MISS → [bounce] then turn_stop SHOT_ATTEMPT. The OREB turn
    # ENDS HERE; second rebound (DREB or chained OREB) becomes its own
    # next turn — see ``game_manager._build_dreb_turn_from_miss``
    # (extended to fire on PUTBACK_MISS) for the DREB branch.
    sbx = turn_result.get("ball_bounce_x")
    sby = turn_result.get("ball_bounce_y")
    if sbx is None or sby is None:
        # No second-bounce coords — end the turn at the last rim-action
        # sub-step (the flight, or the final hop / graze for variants).
        prev_step["end"]["next"] = _shot_attempt_turn_stop(turn_result, "MISS")
        # Shooting-foul-on-miss announcement attaches to the terminal step
        # so the FE plays "Shooting Foul!" before turn_stop. Mirrors skeleton
        # emitter behavior on HCO miss + defensive shooting foul.
        _stamp_shooting_foul_on_miss_end(prev_step, turn_result)
        return steps
    bounce_target: GridCoord = {"x": float(sbx), "y": float(sby)}

    bounce_step = _build_bounce_step(
        start_coords=cursor_coords,
        is_away_offense=is_away_offense,
        bounce_target=bounce_target,
        clock_remaining=cursor_clock["clock_remaining"],
        shot_clock_remaining=cursor_clock["shot_clock_remaining"],
        next_step=_shot_attempt_turn_stop(turn_result, "MISS"),
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        ball_start=cursor_ball,
    )
    prev_step["end"]["next"] = {"kind": "next_step", "index": len(steps)}
    steps.append(bounce_step)
    # Shooting-foul-on-miss announcement attaches to the bounce step's end
    # so the FE plays "Shooting Foul!" before turn_stop. Mirrors skeleton
    # emitter behavior on HCO miss + defensive shooting foul.
    _stamp_shooting_foul_on_miss_end(bounce_step, turn_result)
    return steps
