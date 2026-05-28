"""Free throw animation step emitter (UESS / SS&S).

One backend turn = one FT attempt. Emits ``animation_steps[]`` for:
  lane setup → shoot → ball flight → hold (make) or rim hold → bounce → … (miss).

Miss (non-final): bounce hold → ``ft_return_teleport`` (ball attached to shooter).
Miss (final): turn_stop at bounce; discrete DREB / OREB handles rebound.

Lane geometry matches ``Animator.capture_free_throw_animation`` (HOME_CFG /
AWAY_CFG). Clock is pinned for the full turn (no game-clock burn).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from BackEnd.constants import (
    AIRBALL_OOB_AWAY_COORDS,
    AIRBALL_OOB_GAME_SECONDS,
    AIRBALL_OOB_HOME_COORDS,
    BANK_MAKE_SETTLE_GAME_SECONDS,
    BANK_MISS_GRAZE_GAME_SECONDS,
    BOUNCE_STEP_GAME_SECONDS,
    FREE_THROW_SHOT_GRID_PER_GAME_SECOND,
    MADE_SHOT_SWEET_SPOT_AWAY_RIM,
    MADE_SHOT_SWEET_SPOT_HOME_RIM,
    RATTLE_HOP_GAME_SECONDS,
    RATTLE_MAKE_SETTLE_GAME_SECONDS,
)
from BackEnd.engine.skeleton_step_emitter import (
    _airball_announcement,
    _rattle_hop_targets,
    _variant_flight_end,
)
from BackEnd.utils.animation_step_helpers import (
    _euclid,
    _player_lookup_by_id,
    build_final_coords,
    rattle_hop_sfx,
    rattle_make_settle_sfx,
    shot_followup_timed_sfx,
    shot_launch_sfx_free_throw,
    shot_result_sfx,
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
    StepEnd,
    StepStart,
)
from BackEnd.utils.shared import get_player_position
from BackEnd.utils.transition_bridge import build_walk_up_step

_FT_HOME_CFG = {
    "shooterSpot": {"x": 74, "y": 25},
    "offenseAlignList": [
        {"x": 56, "y": 44},
        {"x": 80, "y": 32},
        {"x": 86, "y": 19},
        {"x": 86, "y": 32},
    ],
    "dDestinations": {
        "PG": {"x": 54, "y": 37},
        "SG": {"x": 83, "y": 32},
        "SF": {"x": 83, "y": 19},
        "PF": {"x": 89, "y": 32},
        "C": {"x": 89, "y": 19},
    },
    "rim": {"x": 91, "y": 25},
}

_FT_AWAY_CFG = {
    "shooterSpot": {"x": 27, "y": 25},
    "offenseAlignList": [
        {"x": 45, "y": 44},
        {"x": 20, "y": 32},
        {"x": 14, "y": 19},
        {"x": 14, "y": 32},
    ],
    "dDestinations": {
        "PG": {"x": 47, "y": 37},
        "SG": {"x": 17, "y": 32},
        "SF": {"x": 17, "y": 19},
        "PF": {"x": 11, "y": 32},
        "C": {"x": 11, "y": 19},
    },
    "rim": {"x": 9, "y": 25},
}

_FT_RATTLE_VARIANTS = frozenset({
    "LITTLE_RATTLE",
    "NORMAL_RATTLE",
    "HEAVY_RATTLE",
})

_SHOOT_STEP_T = 0.35
_BOUNCE_HOLD_GAME_SECONDS = 1000.0 / 350.0
_POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _safe_id(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, (str, int)):
        return str(val)
    pid = getattr(val, "player_id", None)
    return str(pid) if pid is not None else None


def _prior_turn_start_coords(game: Any) -> Dict[str, GridCoord]:
    """Coords at end of the previous turn (before FT lane ``apply_coords``).

    ``resolve_free_throw_logic`` syncs lineup coords to the lane before
    ``build_ft_animation_steps`` runs, so ``build_final_coords(game)`` would
    make setup step 0 a no-op (teleport at snap). Use the prior turn's
    stamped ``final_coords`` instead.
    """
    turns = getattr(game, "turns", None) or []
    if turns:
        prior = turns[-1]
        if isinstance(prior, dict):
            fc = prior.get("final_coords")
            if isinstance(fc, dict) and fc:
                return {str(pid): dict(c) for pid, c in fc.items()}
    return build_final_coords(game)


def _next_step_index(steps: List[AnimationStep]) -> int:
    """Index of the step that follows the one about to be appended."""
    return len(steps) + 1


def _pin_ft_clock(steps: List[AnimationStep], clock: ClockState) -> None:
    """FT turns do not burn game or shot clock (Real Time Clock doc)."""
    pinned = {
        "clock_remaining": float(clock["clock_remaining"]),
        "shot_clock_remaining": float(clock["shot_clock_remaining"]),
    }
    for step in steps:
        step["start"]["clock"] = dict(pinned)
        step["end"]["clock"] = dict(pinned)


def _lane_destinations_by_player_id(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    shooter: Any,
    offense_is_home: bool,
    no_lane: bool,
) -> Dict[str, GridCoord]:
    """Map player_id → FT lane spot (mirrors ``capture_free_throw_animation``)."""
    cfg = _FT_HOME_CFG if offense_is_home else _FT_AWAY_CFG
    shooter_pos = get_player_position(off_lineup, shooter)
    out: Dict[str, GridCoord] = {}

    if not no_lane:
        if shooter_pos:
            sid = _safe_id(shooter)
            if sid:
                out[sid] = dict(cfg["shooterSpot"])
        other_positions = [p for p in _POSITIONS if p != shooter_pos]
        align_idx = 0
        for pos in other_positions:
            player = off_lineup.get(pos)
            if not player or align_idx >= len(cfg["offenseAlignList"]):
                continue
            pid = _safe_id(player)
            if pid:
                out[pid] = dict(cfg["offenseAlignList"][align_idx])
                align_idx += 1
        for pos, player in def_lineup.items():
            if not player:
                continue
            dest = cfg["dDestinations"].get(pos)
            if not dest:
                continue
            pid = _safe_id(player)
            if pid:
                out[pid] = dict(dest)
    else:
        sid = _safe_id(shooter)
        if sid:
            out[sid] = dict(cfg["shooterSpot"])

    return out


def _all_player_ids(
    off_lineup: Dict[str, Any], def_lineup: Dict[str, Any]
) -> List[str]:
    ids: List[str] = []
    for lineup in (off_lineup, def_lineup):
        for player in lineup.values():
            if player is None:
                continue
            pid = _safe_id(player)
            if pid:
                ids.append(pid)
    return ids


def _stationary_step(
    *,
    coords: Dict[str, GridCoord],
    ball: BallState,
    clock: ClockState,
    next_step: NextStep,
    step_t: float = 0.0,
    shooter_id: Optional[str] = None,
    shooter_action: PlayerAction = "stationary",
) -> AnimationStep:
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in coords}
    archetypes: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in coords}
    destinations: Dict[str, Optional[GridCoord]] = {pid: None for pid in coords}
    if shooter_id and shooter_id in coords:
        actions[shooter_id] = shooter_action
        archetypes[shooter_id] = (
            "shot_motion" if shooter_action == "shoot" else "stationary"
        )

    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": float(step_t),
        "metadata": {"reason": "ft_stationary"},
    }
    start: StepStart = {
        "coords": dict(coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetypes,
        "ball": ball,
        "clock": dict(clock),
        "advance_trigger": trigger,
    }
    end: StepEnd = {
        "coords": dict(coords),
        "ball": ball,
        "time_elapsed": float(step_t),
        "clock": dict(clock),
        "next": next_step,
    }
    return {"start": start, "end": end}


def _ball_motion_step(
    *,
    coords: Dict[str, GridCoord],
    ball_start: GridCoord,
    ball_end: GridCoord,
    clock: ClockState,
    step_t: float,
    next_step: NextStep,
    ball_motion_style: str = "shot",
    sfx_on_ball_release: Optional[Dict[str, Any]] = None,
    sfx_on_ball_arrival: Optional[Dict[str, Any]] = None,
    timed_sfx: Optional[list] = None,
    advance_metadata: Optional[Dict[str, Any]] = None,
) -> AnimationStep:
    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in coords}
    archetypes: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in coords}
    destinations: Dict[str, Optional[GridCoord]] = {pid: None for pid in coords}
    # Universal FT meta — flags this step as a free-throw ball motion so
    # `animationPlayback.isFreeThrowShotStep` returns True and the
    # SHOT_BALL_MIN_WALL_CLOCK_MS (400ms) step-wait floor is bypassed.
    # Without this, every FT ball-motion step (rim arrival, bounce,
    # return-to-shooter) would hold for 400ms because they all use
    # ``ball_motion_style="shot"``. Callers can still pass extra
    # ``advance_metadata`` (e.g., per-step ``result`` tags) — those merge
    # on top.
    meta = {
        "reason": "ft_ball_motion",
        "target_coords": dict(ball_end),
        "free_throw_shot": True,
        "ball_grid_per_game_second": FREE_THROW_SHOT_GRID_PER_GAME_SECOND,
    }
    if advance_metadata:
        meta.update(advance_metadata)
    trigger: AdvanceTrigger = {
        "condition": "shot_resolved",
        "T_game_seconds": float(step_t),
        "metadata": meta,
    }
    start: StepStart = {
        "coords": dict(coords),
        "destination": destinations,
        "action": actions,
        "archetype": archetypes,
        "ball": {"coords": dict(ball_start)},
        "clock": dict(clock),
        "advance_trigger": trigger,
        "ball_motion_style": ball_motion_style,
    }
    if sfx_on_ball_release:
        start["sfx_on_ball_release"] = dict(sfx_on_ball_release)
    if sfx_on_ball_arrival:
        start["sfx_on_ball_arrival"] = dict(sfx_on_ball_arrival)
    if timed_sfx:
        start["timed_sfx"] = list(timed_sfx)
    end: StepEnd = {
        "coords": dict(coords),
        "ball": {"coords": dict(ball_end)},
        "time_elapsed": float(step_t),
        "clock": dict(clock),
        "next": next_step,
    }
    return {"start": start, "end": end}


def _ft_ball_stationary_hold_step(
    *,
    coords: Dict[str, GridCoord],
    ball_coord: GridCoord,
    clock: ClockState,
    step_t: float,
    next_step: NextStep,
    metadata_kind: str,
) -> AnimationStep:
    """Ball holds at ``ball_coord``; all players stationary (rim / bounce holds)."""
    ball: BallState = {"coords": dict(ball_coord)}
    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": float(step_t),
        "metadata": {"kind": metadata_kind, "reason": f"ft_{metadata_kind}"},
    }
    start: StepStart = {
        "coords": dict(coords),
        "destination": {pid: None for pid in coords},
        "action": {pid: "stationary" for pid in coords},
        "archetype": {pid: "stationary" for pid in coords},
        "ball": ball,
        "clock": dict(clock),
        "advance_trigger": trigger,
    }
    end: StepEnd = {
        "coords": dict(coords),
        "ball": {"coords": dict(ball_coord)},
        "time_elapsed": float(step_t),
        "clock": dict(clock),
        "next": next_step,
    }
    return {"start": start, "end": end}


def _ft_bounce_motion_step(
    *,
    coords: Dict[str, GridCoord],
    ball_start: GridCoord,
    ball_end: GridCoord,
    clock: ClockState,
    next_step: NextStep,
) -> AnimationStep:
    """Rim → bounce_spot using fixed 300ms wall (matches skeleton ``[bounce]``)."""
    step_t = float(BOUNCE_STEP_GAME_SECONDS)
    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": step_t,
        "metadata": {
            "kind": "bounce",
            "target_coords": dict(ball_end),
            "reason": "ft_miss_bounce",
        },
    }
    start: StepStart = {
        "coords": dict(coords),
        "destination": {pid: None for pid in coords},
        "action": {pid: "stationary" for pid in coords},
        "archetype": {pid: "stationary" for pid in coords},
        "ball": {"coords": dict(ball_start)},
        "clock": dict(clock),
        "advance_trigger": trigger,
    }
    end: StepEnd = {
        "coords": dict(coords),
        "ball": {"coords": dict(ball_end)},
        "time_elapsed": step_t,
        "clock": dict(clock),
        "next": next_step,
    }
    return {"start": start, "end": end}


def _build_ft_return_teleport_step(
    *,
    coords: Dict[str, GridCoord],
    bounce_coord: GridCoord,
    shooter_id: str,
    shooter_lane_coord: GridCoord,
    clock: ClockState,
    next_step: NextStep,
) -> AnimationStep:
    """Rare FT-only exception: instant ball snap bounce → shooter (attached)."""
    trigger: AdvanceTrigger = {
        "condition": "fixed_duration",
        "T_game_seconds": 0.0,
        "metadata": {
            "kind": "ft_return_teleport",
            "target_player_id": str(shooter_id),
            "reason": "ft_mid_miss_return",
        },
    }
    start: StepStart = {
        "coords": dict(coords),
        "destination": {pid: None for pid in coords},
        "action": {pid: "stationary" for pid in coords},
        "archetype": {pid: "stationary" for pid in coords},
        "ball": {"coords": dict(bounce_coord)},
        "clock": dict(clock),
        "advance_trigger": trigger,
    }
    end: StepEnd = {
        "coords": dict(coords),
        "ball": {
            "owner_player_id": str(shooter_id),
            "coords": dict(shooter_lane_coord),
        },
        "time_elapsed": 0.0,
        "clock": dict(clock),
        "next": next_step,
    }
    return {"start": start, "end": end}


def _append_ft_variant_post_shot_chain(
    steps: List[AnimationStep],
    *,
    shoot_step: AnimationStep,
    turn_result: Dict[str, Any],
    cursor_coords: Dict[str, GridCoord],
    cursor_clock: ClockState,
    away_offense: bool,
    shooter_id: str,
    shot_spot: GridCoord,
    is_make: bool,
    outcome: str,
) -> tuple[Dict[str, GridCoord], GridCoord, AnimationStep]:
    """Append [ball_flight] + variant sub-steps after the FT shoot step."""
    shot_variant = turn_result.get("shot_variant")
    make_settle = turn_result.get("make_settle_sfx_file") or "free-throw-swish.wav"
    result_type = "MAKE" if is_make else "MISS"
    variant_upper = (shot_variant or "").upper()
    is_rattle = variant_upper in _FT_RATTLE_VARIANTS
    is_airball = variant_upper == "AIRBALL"

    ball_flight_end = _variant_flight_end(
        shot_variant, result_type, away_offense, turn_result,
    )
    flight_dist = _euclid(shot_spot, ball_flight_end)
    flight_t = max(
        0.05, flight_dist / float(FREE_THROW_SHOT_GRID_PER_GAME_SECOND),
    )
    launch_sfx = shot_launch_sfx_free_throw()
    arrival_sfx = shot_result_sfx(
        shot_variant,
        result_type,
        bank_miss_sfx_file=turn_result.get("shot_variant_bank_miss_sfx_file"),
    )
    timed_sfx = shot_followup_timed_sfx(
        shot_variant,
        result_type,
        make_settle_sfx_file=make_settle,
    )

    flight_step = _ball_motion_step(
        coords=cursor_coords,
        ball_start=dict(shot_spot),
        ball_end=ball_flight_end,
        clock=cursor_clock,
        step_t=flight_t,
        next_step={"kind": "next_step", "index": _next_step_index(steps)},
        sfx_on_ball_release=launch_sfx,
        sfx_on_ball_arrival=arrival_sfx,
        timed_sfx=timed_sfx,
        advance_metadata={
            "free_throw_shot": True,
            "ball_grid_per_game_second": FREE_THROW_SHOT_GRID_PER_GAME_SECOND,
            "result": outcome,
            "kind": "ball_flight",
        },
    )
    shoot_step["end"]["next"] = {"kind": "next_step", "index": len(steps)}
    steps.append(flight_step)

    if is_airball and not is_make:
        airball_ann = _airball_announcement(turn_result, away_offense)
        if airball_ann:
            flight_step["end"]["announcement"] = airball_ann

    cursor_ball: GridCoord = dict(ball_flight_end)
    last_appended = flight_step

    def _append_motion(
        *,
        ball_end: GridCoord,
        step_t: float,
        trigger_kind: str,
        sfx_arrival: Optional[Dict[str, Any]] = None,
    ) -> None:
        nonlocal cursor_coords, cursor_ball, last_appended
        step = _ball_motion_step(
            coords=cursor_coords,
            ball_start=dict(cursor_ball),
            ball_end=ball_end,
            clock=cursor_clock,
            step_t=float(step_t),
            next_step={"kind": "next_step", "index": _next_step_index(steps)},
            sfx_on_ball_arrival=sfx_arrival,
            advance_metadata={
                "free_throw_shot": True,
                "ball_grid_per_game_second": FREE_THROW_SHOT_GRID_PER_GAME_SECOND,
                "kind": trigger_kind,
                "target_coords": dict(ball_end),
            },
        )
        last_appended["end"]["next"] = {"kind": "next_step", "index": len(steps)}
        steps.append(step)
        cursor_ball = dict(ball_end)
        last_appended = step

    if is_rattle:
        hop_targets = _rattle_hop_targets(variant_upper, away_offense, turn_result)
        for hop_target in hop_targets:
            _append_motion(
                ball_end=hop_target,
                step_t=float(RATTLE_HOP_GAME_SECONDS),
                trigger_kind="rattle_hop",
                sfx_arrival=rattle_hop_sfx(),
            )
        if is_make:
            msss = (
                dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM)
                if away_offense
                else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)
            )
            _append_motion(
                ball_end=msss,
                step_t=float(RATTLE_MAKE_SETTLE_GAME_SECONDS),
                trigger_kind="rattle_settle",
                sfx_arrival=rattle_make_settle_sfx(
                    make_settle_sfx_file=make_settle,
                ),
            )
    elif variant_upper == "BANK_MAKE":
        msss = (
            dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM)
            if away_offense
            else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)
        )
        _append_motion(
            ball_end=msss,
            step_t=float(BANK_MAKE_SETTLE_GAME_SECONDS),
            trigger_kind="bank_settle",
        )
    elif variant_upper == "BANK_MISS":
        msss = (
            dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM)
            if away_offense
            else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)
        )
        graze = {
            "x": float(msss["x"]) + float(
                turn_result.get("shot_variant_backboard_miss_rim_offset_x") or 0
            ),
            "y": float(msss["y"]) + float(
                turn_result.get("shot_variant_backboard_miss_rim_offset_y") or 0
            ),
        }
        _append_motion(
            ball_end=graze,
            step_t=float(BANK_MISS_GRAZE_GAME_SECONDS),
            trigger_kind="bank_graze",
        )
    elif is_airball:
        oob_target = (
            dict(AIRBALL_OOB_AWAY_COORDS)
            if away_offense
            else dict(AIRBALL_OOB_HOME_COORDS)
        )
        _append_motion(
            ball_end=oob_target,
            step_t=float(AIRBALL_OOB_GAME_SECONDS),
            trigger_kind="airball_oob",
        )

    return dict(cursor_coords), cursor_ball, last_appended


def build_ft_animation_steps(
    turn_result: Dict[str, Any],
    game: Any,
) -> Optional[List[AnimationStep]]:
    """Build schema steps for a single free-throw attempt turn."""
    if game.game_state.get("_is_full_simulation", False):
        return None

    attempts = turn_result.get("attempts") or []
    if not attempts:
        return None
    outcome = str(attempts[0]).upper()
    if outcome not in ("MAKE", "MISS"):
        return None

    shooter_id = _safe_id(turn_result.get("shooter_id") or turn_result.get("shooter"))
    if not shooter_id:
        return None

    off_team = game.offense_team
    def_team = game.defense_team
    off_lineup = off_team.lineup
    def_lineup = def_team.lineup
    shooter = _player_lookup_by_id(off_lineup, def_lineup, shooter_id)
    if shooter is None:
        for player in off_lineup.values():
            if player is not None and _safe_id(player) == shooter_id:
                shooter = player
                break
    if shooter is None:
        return None

    offense_is_home = off_team.team_id == game.home_team.team_id
    no_lane = bool(turn_result.get("no_lane"))
    away_offense = not offense_is_home

    clock_remaining = float(game.game_state.get("time_remaining", 0) or 0)
    shot_clock_remaining = float(game.game_state.get("shot_clock_remaining", 0) or 0)
    clock: ClockState = {
        "clock_remaining": clock_remaining,
        "shot_clock_remaining": shot_clock_remaining,
    }

    start_coords = _prior_turn_start_coords(game)
    if shooter_id not in start_coords:
        sc = getattr(shooter, "coords", None) or {}
        if "x" in sc and "y" in sc:
            start_coords[shooter_id] = {"x": float(sc["x"]), "y": float(sc["y"])}

    lane_targets = _lane_destinations_by_player_id(
        off_lineup, def_lineup, shooter, offense_is_home, no_lane
    )
    if shooter_id not in lane_targets:
        return None

    # Players not in lane_targets (no_lane defense) hold current coords.
    end_lane: Dict[str, GridCoord] = dict(start_coords)
    for pid, dest in lane_targets.items():
        end_lane[pid] = dict(dest)

    steps: List[AnimationStep] = []

    # --- Step 0: Lane setup ---
    setup_start = dict(start_coords)
    if no_lane:
        # Shooter only; others hold their current coords.
        setup_targets = dict(start_coords)
        setup_targets[shooter_id] = dict(lane_targets[shooter_id])
    else:
        setup_targets = dict(end_lane)

    setup_step = build_walk_up_step(
        off_lineup=off_lineup,
        def_lineup=def_lineup,
        start_coords=setup_start,
        end_coords=setup_targets,
        bh_id=shooter_id,
        clock_remaining_at_start=clock_remaining,
        shot_clock_remaining_at_start=shot_clock_remaining,
        next_step_index=1,
        bh_archetype="standard",
        other_archetype="standard",
        # Gate on all 10 so every lane player is fully aligned before the
        # FT shot fires. Non-movers have natural_t=0 and don't bottleneck;
        # the actual gate becomes the slowest mover (= the lane player
        # with the longest natural traversal). In no_lane branches, only
        # shooter moves, so this still resolves to shooter-as-gate.
        gate_player_ids=list(setup_targets.keys()),
        metadata_reason="ft_lane_setup",
    )
    setup_step["start"]["ball"] = {
        "owner_player_id": shooter_id,
    }
    setup_step["end"]["ball"] = {
        "owner_player_id": shooter_id,
    }
    stamp_tween_durations(
        setup_step["start"],
        setup_step["end"]["coords"],
        float(setup_step["end"]["time_elapsed"]),
        off_lineup,
        def_lineup,
    )
    steps.append(setup_step)

    cursor_coords = dict(setup_step["end"]["coords"])
    cursor_clock = dict(setup_step["end"]["clock"])

    # --- Step 1: Shoot (release) ---
    shoot_ball: BallState = {"owner_player_id": shooter_id}
    shoot_step = _stationary_step(
        coords=cursor_coords,
        ball=shoot_ball,
        clock=cursor_clock,
        next_step={"kind": "next_step", "index": _next_step_index(steps)},
        step_t=_SHOOT_STEP_T,
        shooter_id=shooter_id,
        shooter_action="shoot",
    )
    steps.append(shoot_step)
    cursor_coords = dict(shoot_step["end"]["coords"])
    cursor_clock = dict(shoot_step["end"]["clock"])

    shot_spot = cursor_coords.get(shooter_id) or lane_targets[shooter_id]
    sweet = (
        dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM)
        if away_offense
        else dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)
    )

    is_make = outcome == "MAKE"
    cursor_coords, cursor_ball, _last_variant_step = _append_ft_variant_post_shot_chain(
        steps,
        shoot_step=shoot_step,
        turn_result=turn_result,
        cursor_coords=cursor_coords,
        cursor_clock=cursor_clock,
        away_offense=away_offense,
        shooter_id=shooter_id,
        shot_spot=dict(shot_spot),
        is_make=is_make,
        outcome=outcome,
    )

    free_throws_remaining = int(turn_result.get("free_throws_remaining", 0) or 0)
    is_final_attempt = free_throws_remaining <= 0
    shot_variant = str(turn_result.get("shot_variant") or "").upper()
    is_airball = (not is_make) and shot_variant == "AIRBALL"

    if is_make:
        # Make hold at settle point while "It's Good!" announcement plays.
        hold_step = _ball_motion_step(
            coords=cursor_coords,
            ball_start=dict(cursor_ball),
            ball_end=dict(cursor_ball),
            clock=cursor_clock,
            step_t=0.0,
            next_step={"kind": "next_step", "index": _next_step_index(steps)},
            ball_motion_style="shot",
        )
        hold_step["start"]["announcement"] = {
            "text": "It's Good!",
            "team": "away" if away_offense else "home",
            "hold_ms": 1000.0,
            "style": "primary",
            "player_data": {"playerId": str(shooter_id)},
        }
        hold_step["start"]["advance_trigger"]["condition"] = "fixed_duration"
        hold_step["start"]["advance_trigger"]["metadata"]["kind"] = "make_hold"
        _last_variant_step["end"]["next"] = {
            "kind": "next_step",
            "index": len(steps),
        }
        steps.append(hold_step)
        cursor_coords = dict(hold_step["end"]["coords"])

        if not is_final_attempt:
            teleport_step = _build_ft_return_teleport_step(
                coords=cursor_coords,
                bounce_coord=dict(cursor_ball),
                shooter_id=str(shooter_id),
                shooter_lane_coord=dict(lane_targets[shooter_id]),
                clock=cursor_clock,
                next_step={"kind": "next_step", "index": _next_step_index(steps)},
            )
            steps.append(teleport_step)
            cursor_coords = dict(teleport_step["end"]["coords"])
    elif is_airball:
        if is_final_attempt:
            _last_variant_step["end"]["next"] = _implicit_turn_end_next(turn_result)
        else:
            bounce_hold = _ft_ball_stationary_hold_step(
                coords=cursor_coords,
                ball_coord=dict(cursor_ball),
                clock=cursor_clock,
                step_t=_BOUNCE_HOLD_GAME_SECONDS,
                next_step={"kind": "next_step", "index": _next_step_index(steps)},
                metadata_kind="bounce_hold",
            )
            _last_variant_step["end"]["next"] = {
                "kind": "next_step",
                "index": len(steps),
            }
            steps.append(bounce_hold)
            cursor_coords = dict(bounce_hold["end"]["coords"])

            teleport_step = _build_ft_return_teleport_step(
                coords=cursor_coords,
                bounce_coord=dict(cursor_ball),
                shooter_id=str(shooter_id),
                shooter_lane_coord=dict(lane_targets[shooter_id]),
                clock=cursor_clock,
                next_step={"kind": "next_step", "index": _next_step_index(steps)},
            )
            steps.append(teleport_step)
            cursor_coords = dict(teleport_step["end"]["coords"])
    else:
        bx = turn_result.get("ball_bounce_x")
        by = turn_result.get("ball_bounce_y")
        if bx is None or by is None:
            return steps if steps else None
        bounce = {"x": float(bx), "y": float(by)}

        bounce_step = _ft_bounce_motion_step(
            coords=cursor_coords,
            ball_start=dict(cursor_ball),
            ball_end=dict(bounce),
            clock=cursor_clock,
            next_step=(
                _implicit_turn_end_next(turn_result)
                if is_final_attempt
                else {"kind": "next_step", "index": _next_step_index(steps)}
            ),
        )
        _last_variant_step["end"]["next"] = {
            "kind": "next_step",
            "index": len(steps),
        }
        steps.append(bounce_step)
        cursor_coords = dict(bounce_step["end"]["coords"])

        if not is_final_attempt:
            bounce_hold = _ft_ball_stationary_hold_step(
                coords=cursor_coords,
                ball_coord=dict(bounce),
                clock=cursor_clock,
                step_t=_BOUNCE_HOLD_GAME_SECONDS,
                next_step={"kind": "next_step", "index": _next_step_index(steps)},
                metadata_kind="bounce_hold",
            )
            steps.append(bounce_hold)
            cursor_coords = dict(bounce_hold["end"]["coords"])

            teleport_step = _build_ft_return_teleport_step(
                coords=cursor_coords,
                bounce_coord=dict(bounce),
                shooter_id=str(shooter_id),
                shooter_lane_coord=dict(lane_targets[shooter_id]),
                clock=cursor_clock,
                next_step={"kind": "next_step", "index": _next_step_index(steps)},
            )
            steps.append(teleport_step)
            cursor_coords = dict(teleport_step["end"]["coords"])

    _pin_ft_clock(steps, clock)

    # Ensure every on-court player appears in final step coords.
    last = steps[-1]
    for pid in _all_player_ids(off_lineup, def_lineup):
        if pid not in last["end"]["coords"]:
            last["end"]["coords"][pid] = dict(
                cursor_coords.get(pid) or start_coords.get(pid) or {"x": 50, "y": 25}
            )
        if pid not in last["start"]["coords"]:
            last["start"]["coords"][pid] = dict(last["end"]["coords"][pid])

    return steps


def _implicit_turn_end_next(turn_result: Dict[str, Any]) -> NextStep:
    """Terminal step: next turn is DREB, OREB (pending), BIP (airball), or end."""
    npt = str(turn_result.get("next_play_type") or "").upper()
    if npt == "BASELINE_INBOUND":
        return {
            "kind": "turn_stop",
            "event": "SHOT_ATTEMPT",
            "payload": {
                "schema_rendered_arc": True,
                "free_throw_final_miss": True,
                "airball": True,
            },
        }
    if npt in ("HCO", "FAST_BREAK", "DREB"):
        return {
            "kind": "turn_stop",
            "event": "SHOT_ATTEMPT",
            "payload": {"schema_rendered_arc": True, "free_throw_final_miss": True},
        }
    if turn_result.get("rebound_type") == "OREB":
        return {
            "kind": "turn_stop",
            "event": "SHOT_ATTEMPT",
            "payload": {"schema_rendered_arc": True, "free_throw_final_miss": True},
        }
    return {"kind": "next_step", "index": 999}


def collect_ft_rebound_crashers(
    off_lineup: Dict[str, Any],
    def_lineup: Dict[str, Any],
    bounce_spot: GridCoord,
    *,
    rebounder_id: str,
    shooter_id: str,
    max_x_delta: float,
) -> tuple[List[str], List[str]]:
    """Eligible crashers per team (FT x-gate), excluding captor and shooter."""
    from BackEnd.utils.shared import _filter_lineup_by_max_x_delta_from_bounce

    bx = float(bounce_spot["x"])
    off_f = _filter_lineup_by_max_x_delta_from_bounce(
        off_lineup, bx, max_x_delta
    )
    def_f = _filter_lineup_by_max_x_delta_from_bounce(
        def_lineup, bx, max_x_delta
    )
    if not off_f and not def_f:
        off_f, def_f = off_lineup, def_lineup

    captor = str(rebounder_id)
    shooter = str(shooter_id)
    off_ids: List[str] = []
    def_ids: List[str] = []

    for lineup, bucket in ((off_f, off_ids), (def_f, def_ids)):
        for player in lineup.values():
            if player is None:
                continue
            pid = _safe_id(player)
            if not pid or pid in (captor, shooter):
                continue
            bucket.append(pid)

    return off_ids, def_ids
