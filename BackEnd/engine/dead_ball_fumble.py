"""Dead-ball turnover fumble beat — insert before DEAD_BALL_TURNOVER turn_stop."""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
import logging
from typing import Any, Dict, List, Optional, Tuple

from BackEnd.constants import AWAY_RIM_COORDS, HOME_RIM_COORDS
from BackEnd.constants.dead_ball_fumble_constants import (
    DEAD_BALL_FUMBLE_HEADLINE,
    DEAD_BALL_FUMBLE_WHISTLE_SFX,
    FUMBLE_ANNOUNCE_HOLD_MS,
    FUMBLE_FREQ_HZ,
    FUMBLE_MAG_PX,
    FUMBLE_WALL_CLOCK_MS,
)
from BackEnd.utils.animation_step_schema import (
    AnimationStep,
    ClockState,
    GridCoord,
    NextStep,
    PlayerAction,
    PlayerArchetype,
)


def _normalize_result_type(turn_result: Dict[str, Any]) -> str:
    return (turn_result.get("result_type") or "").upper().replace(" ", "_")


def is_dead_ball_fumble_turn(turn_result: Dict[str, Any]) -> bool:
    """True for travel/double-dribble class dead-ball turnovers (not shot clock / steals)."""
    if (turn_result.get("turnover_type") or "").upper() in (
        "SHOT_CLOCK",
        "TEN_SECOND",
        "OVER_BACK",
    ):
        return False
    if turn_result.get("stealer_id"):
        return False
    if turn_result.get("bat_oob") or turn_result.get("rim_runner_bat_oob"):
        return False
    rt = _normalize_result_type(turn_result)
    if rt == "TURNOVER":
        text = (turn_result.get("text") or "").lower()
        if "steal" in text:
            return False
    return rt in ("DEAD_BALL_TURNOVER", "DEAD_BALL", "TURNOVER")


def roll_dead_ball_fumble_label() -> str:
    """50/50 Travel vs Double Dribble headline (backend-authored for UESS)."""
    return "TRAVEL" if random.random() < 0.5 else "DOUBLE_DRIBBLE"


def _safe_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "player_id"):
        return str(getattr(value, "player_id"))
    return str(value) if value else None


def _resolve_ball_handler_id(
    turn_result: Dict[str, Any],
    coords: Dict[str, GridCoord],
) -> Optional[str]:
    for key in ("victim_id", "shooter_id", "ball_handler_id"):
        pid = _safe_id(turn_result.get(key))
        if pid and pid in coords:
            return pid
    bh = turn_result.get("ball_handler")
    pid = _safe_id(bh)
    if pid and pid in coords:
        return pid
    return pid


def _rim_axis_unit_vectors(
    handler_coord: GridCoord,
    away_offense: bool,
) -> Tuple[float, float, float, float]:
    """Return (rim_unit_x, rim_unit_y, perp_x, perp_y) in display orientation."""
    rim = AWAY_RIM_COORDS if away_offense else HOME_RIM_COORDS
    dx = float(rim["x"]) - float(handler_coord["x"])
    dy = float(rim["y"]) - float(handler_coord["y"])
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-6:
        ux, uy = (1.0 if not away_offense else -1.0), 0.0
    else:
        ux, uy = dx / length, dy / length
    perp_x, perp_y = -uy, ux
    return ux, uy, perp_x, perp_y


def _find_dead_ball_turn_stop_step_index(steps: List[AnimationStep]) -> Optional[int]:
    for idx, step in enumerate(steps):
        nxt = (step.get("end") or {}).get("next")
        if not isinstance(nxt, dict) or nxt.get("kind") != "turn_stop":
            continue
        if nxt.get("event") == "DEAD_BALL_TURNOVER":
            return idx
    return None


def _has_fumble_flourish_step(steps: List[AnimationStep]) -> bool:
    for step in steps:
        flourish = (step.get("start") or {}).get("flourish") or {}
        if not isinstance(flourish, dict):
            continue
        for payload in flourish.values():
            if isinstance(payload, dict) and payload.get("kind") == "fumble":
                return True
    return False


def build_dead_ball_fumble_step(
    *,
    start_coords: Dict[str, GridCoord],
    ball_handler_id: str,
    away_offense: bool,
    clock: ClockState,
    turnover_label: str,
    turn_stop_next: NextStep,
) -> AnimationStep:
    """Stationary fumble beat: render-space stumble, then whistle announcement."""
    bh_coord = dict(start_coords[ball_handler_id])
    ux, uy, perp_x, perp_y = _rim_axis_unit_vectors(bh_coord, away_offense)
    headline = DEAD_BALL_FUMBLE_HEADLINE.get(turnover_label, "TURNOVER!")

    actions: Dict[str, PlayerAction] = {pid: "stationary" for pid in start_coords}
    actions[ball_handler_id] = "handle_ball"
    archetypes: Dict[str, PlayerArchetype] = {pid: "stationary" for pid in start_coords}
    destinations = {pid: None for pid in start_coords}

    flourish = {
        "kind": "fumble",
        "duration_ms": float(FUMBLE_WALL_CLOCK_MS),
        "mag_px": float(FUMBLE_MAG_PX),
        "freq_hz": float(FUMBLE_FREQ_HZ),
        "rim_unit_x": float(ux),
        "rim_unit_y": float(uy),
        "perp_x": float(perp_x),
        "perp_y": float(perp_y),
    }

    pinned_clock = dict(clock)
    ball_state = {"owner_player_id": str(ball_handler_id)}

    return {
        "start": {
            "coords": {pid: dict(c) for pid, c in start_coords.items()},
            "destination": destinations,
            "action": actions,
            "archetype": archetypes,
            "ball": dict(ball_state),
            "clock": pinned_clock,
            "flourish": {str(ball_handler_id): flourish},
            "advance_trigger": {
                "condition": "dead_ball_fumble",
                "T_game_seconds": 0.0,
                "metadata": {
                    "wall_clock_hold_ms": float(FUMBLE_WALL_CLOCK_MS),
                    "dead_ball_fumble": True,
                },
            },
        },
        "end": {
            "coords": {pid: dict(c) for pid, c in start_coords.items()},
            "ball": dict(ball_state),
            "time_elapsed": 0.0,
            "clock": pinned_clock,
            "announcement": {
                "text": headline,
                "team": "away" if away_offense else "home",
                "hold_ms": int(FUMBLE_ANNOUNCE_HOLD_MS),
                "style": "primary",
                "player_data": {"playerId": str(ball_handler_id)},
                "meta": {"sfx": DEAD_BALL_FUMBLE_WHISTLE_SFX},
            },
            "next": turn_stop_next,
        },
    }


def inject_dead_ball_fumble_before_turn_stop(
    steps: List[AnimationStep],
    turn_result: Dict[str, Any],
    *,
    away_offense: bool,
) -> None:
    """Insert fumble beat immediately before terminal DEAD_BALL_TURNOVER turn_stop."""
    if not is_dead_ball_fumble_turn(turn_result):
        return
    if not steps:
        logging.warning(
            "[DEAD-BALL-FUMBLE] skip=no_steps current_turn=%s result_type=%s "
            "turnover_type=%s text=%s",
            turn_result.get("current_turn"),
            turn_result.get("result_type"),
            turn_result.get("turnover_type"),
            turn_result.get("text"),
        )
        return
    if _has_fumble_flourish_step(steps):
        logging.warning(
            "[DEAD-BALL-FUMBLE] skip=already_injected current_turn=%s result_type=%s "
            "steps=%s",
            turn_result.get("current_turn"),
            turn_result.get("result_type"),
            len(steps),
        )
        return

    anchor_idx = _find_dead_ball_turn_stop_step_index(steps)
    if anchor_idx is None:
        terminal_next = (steps[-1].get("end") or {}).get("next") if steps else None
        logging.warning(
            "[DEAD-BALL-FUMBLE] skip=no_dead_ball_turn_stop current_turn=%s "
            "result_type=%s turnover_type=%s steps=%s terminal_next=%s",
            turn_result.get("current_turn"),
            turn_result.get("result_type"),
            turn_result.get("turnover_type"),
            len(steps),
            terminal_next,
        )
        return

    anchor = steps[anchor_idx]
    turn_stop_next = (anchor.get("end") or {}).get("next")
    if not isinstance(turn_stop_next, dict):
        logging.warning(
            "[DEAD-BALL-FUMBLE] skip=bad_turn_stop_next current_turn=%s "
            "result_type=%s anchor_idx=%s next=%s",
            turn_result.get("current_turn"),
            turn_result.get("result_type"),
            anchor_idx,
            turn_stop_next,
        )
        return

    end_coords = (anchor.get("end") or {}).get("coords") or {}
    if not end_coords:
        logging.warning(
            "[DEAD-BALL-FUMBLE] skip=no_end_coords current_turn=%s result_type=%s "
            "anchor_idx=%s",
            turn_result.get("current_turn"),
            turn_result.get("result_type"),
            anchor_idx,
        )
        return

    bh_id = _resolve_ball_handler_id(turn_result, end_coords)
    if not bh_id or bh_id not in end_coords:
        logging.warning(
            "[DEAD-BALL-FUMBLE] skip=no_handler_coord current_turn=%s result_type=%s "
            "anchor_idx=%s resolved_bh_id=%s victim_id=%s shooter_id=%s "
            "ball_handler_id=%s coords_count=%s",
            turn_result.get("current_turn"),
            turn_result.get("result_type"),
            anchor_idx,
            bh_id,
            turn_result.get("victim_id"),
            turn_result.get("shooter_id"),
            turn_result.get("ball_handler_id"),
            len(end_coords),
        )
        return

    clock = dict((anchor.get("end") or {}).get("clock") or {"clock_remaining": 0.0, "shot_clock_remaining": 0.0})
    label = roll_dead_ball_fumble_label()
    turn_result["turnover_type"] = label
    turn_result["suppress_turn_prep_turnover_announce"] = True

    fumble_idx = len(steps)
    anchor["end"]["next"] = {"kind": "next_step", "index": fumble_idx}

    fumble_step = build_dead_ball_fumble_step(
        start_coords={pid: dict(c) for pid, c in end_coords.items()},
        ball_handler_id=bh_id,
        away_offense=away_offense,
        clock=clock,
        turnover_label=label,
        turn_stop_next=turn_stop_next,
    )
    steps.append(fumble_step)
    logging.warning(
        "[DEAD-BALL-FUMBLE] injected current_turn=%s result_type=%s label=%s "
        "handler_id=%s anchor_idx=%s fumble_idx=%s steps=%s",
        turn_result.get("current_turn"),
        turn_result.get("result_type"),
        label,
        bh_id,
        anchor_idx,
        fumble_idx,
        len(steps),
    )


def finalize_dead_ball_fumble_for_turn(
    turn_result: Dict[str, Any],
    game: Any,
) -> None:
    """Universal finalization pass for schema-rendered dead-ball turnovers.

    Emitters may still call ``inject_dead_ball_fumble_before_turn_stop`` locally.
    This pass is idempotent and catches any qualifying turn that attached
    ``animation_steps`` outside those emitter-specific call sites.
    """
    if not isinstance(turn_result, dict):
        return
    steps = turn_result.get("animation_steps")
    if not isinstance(steps, list) or not steps:
        if is_dead_ball_fumble_turn(turn_result):
            logging.warning(
                "[DEAD-BALL-FUMBLE] finalize_skip=no_animation_steps current_turn=%s "
                "result_type=%s turnover_type=%s text=%s",
                turn_result.get("current_turn"),
                turn_result.get("result_type"),
                turn_result.get("turnover_type"),
                turn_result.get("text"),
            )
        return
    off_team = getattr(game, "offense_team", None)
    away_team = getattr(game, "away_team", None)
    away_offense = bool(
        off_team is not None
        and getattr(off_team, "team_id", None)
        == getattr(away_team, "team_id", None)
    )
    inject_dead_ball_fumble_before_turn_stop(
        steps,
        turn_result,
        away_offense=away_offense,
    )


def propagate_fumble_turn_flags(
    source: Dict[str, Any],
    dest: Dict[str, Any],
) -> None:
    """Copy fumble announce fields from an emitter working copy onto the canonical turn.

    Dynamic FCP builds steps against ``dict(turn_result)``; inject stamps
    ``suppress_turn_prep_turnover_announce`` and ``turnover_type`` on that copy.
    Merge them back so the FE turn-prep path stays suppressed.
    """
    if source.get("suppress_turn_prep_turnover_announce"):
        dest["suppress_turn_prep_turnover_announce"] = True
    turnover_type = source.get("turnover_type")
    if turnover_type:
        dest["turnover_type"] = turnover_type
