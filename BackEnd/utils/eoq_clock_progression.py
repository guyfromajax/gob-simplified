"""Clock-driven end-of-quarter progression (Final Shot / FLSS chains).

Quarter end is determined by ``time_remaining`` reaching 0, not by possession
flags alone. When the game clock still has time after a late-clock shot or final
free throw, possession chains continue (BIP → FLSS, OREB putback, terminal DREB).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

LATE_CLOCK_THRESHOLD = 30
OREB_PUTBACK_ONLY_THRESHOLD = 6
# Preflight may only fall back to FLSS at or below this clock; above it we emit
# best-effort Final Turn (walk-up consumes game time per Situational_Logic_System.md).
FLSS_PREFLIGHT_FALLBACK_MAX_CLOCK = 8
LATE_CLOCK_BIP_RUNOFF_SECONDS = 2

TIMEOUT_SNAPSHOT_KEYS = (
    "timeout_next_play_type",
    "timeout_offense_team_id",
    "timeout_trace_id",
    "timeout_seam_ball_handler_id",
    "timeout_free_throws_remaining",
    "timeout_free_throws",
    "timeout_shooter_id",
    "timeout_one_and_one",
    "timeout_reason",
)


def is_late_clock_eoq(time_remaining: Optional[int]) -> bool:
    if time_remaining is None:
        return False
    return int(time_remaining) <= LATE_CLOCK_THRESHOLD


def should_force_oreb_putback(time_remaining: Optional[int]) -> bool:
    """Universal OREB rule: under 6 seconds remaining → 100% putback."""
    if time_remaining is None:
        return False
    return int(time_remaining) < OREB_PUTBACK_ONLY_THRESHOLD


def mark_late_clock_eoq_turn(result: Dict[str, Any]) -> None:
    result["late_clock_eoq"] = True


def activate_late_clock_eoq_chain(game_state: Dict[str, Any]) -> None:
    """Mark that an EOQ possession chain is in progress for this quarter."""
    game_state["late_clock_eoq_chain_active"] = True


def is_late_clock_eoq_chain_active(game_state: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(game_state, dict):
        return False
    return bool(game_state.get("late_clock_eoq_chain_active"))


def clear_late_clock_eoq_chain(game_state: Dict[str, Any]) -> None:
    game_state.pop("late_clock_eoq_chain_active", None)
    game_state.pop("flss_possession_pending", None)
    game_state.pop("final_shot_possession_active", None)
    game_state.pop("eoq_trace_seq", None)
    game_state.pop("eoq_trace_turn_in_seq", None)


def _late_chain_active(game: Any, result: Dict[str, Any]) -> bool:
    gs = getattr(game, "game_state", None) or {}
    return bool(
        is_late_clock_eoq_chain_active(gs)
        or gs.get("final_turn")
        or result.get("late_clock_eoq")
        or result.get("flss")
        or result.get("final_turn")
        or gs.get("flss_possession_pending")
    )


def should_route_final_turn_to_flss(time_remaining: Optional[int]) -> bool:
    """True when preflight budget failure should route to FLSS instead of full Final Turn."""
    tr = int(time_remaining or 0)
    if tr <= 0:
        return True
    return tr <= FLSS_PREFLIGHT_FALLBACK_MAX_CLOCK


def should_route_eoq_rebound(game: Any, result: Dict[str, Any]) -> bool:
    """True when late-clock EOQ rules govern the rebound (not normal HCO promotion)."""
    time_remaining = int(game.game_state.get("time_remaining") or 0)
    if time_remaining <= 0:
        return True
    return is_late_clock_eoq(time_remaining) and _late_chain_active(game, result)


def apply_post_miss_rebound_routing(
    game: Any,
    result: Dict[str, Any],
    rebounder: Any,
    stat: str,
) -> bool:
    """Route OREB/DREB after a miss or block. Returns possession_flips."""
    gs = game.game_state
    time_remaining = int(gs.get("time_remaining") or 0)
    from_block = getattr(game.shot_manager, "_block_spot", None) is not None

    if stat == "OREB":
        gs.pop("_shot_dreb_fb_play_key", None)
        if time_remaining <= 0:
            result["quarter_ends_after"] = True
            result["next_play_type"] = None
            result.pop("next_turn", None)
            return False
        activate_late_clock_eoq_chain(gs)
        gs["pending_oreb"] = {
            "rebounder": rebounder,
            "rebounder_id": getattr(rebounder, "player_id", None),
            "from_block": from_block,
        }
        result["next_play_type"] = "OREB"
        result["next_turn"] = "OREB"
        mark_late_clock_eoq_turn(result)
        return False

    # DREB
    if time_remaining <= 0:
        result["quarter_ends_after"] = True
        result["next_play_type"] = None
        result.pop("next_turn", None)
        return True

    if is_late_clock_eoq(time_remaining) and _late_chain_active(game, result):
        result["terminal_dreb_eoq"] = True
        mark_late_clock_eoq_turn(result)
        result["next_play_type"] = "DREB"
        result["next_turn"] = "DREB"
        gs.pop("_shot_dreb_fb_play_key", None)
        return True

    gs["offensive_state"] = "HCO"
    gs["last_rebounder"] = rebounder
    result["next_play_type"] = "HCO"
    result["next_turn"] = "HCO"
    return True


def apply_post_make_late_clock_routing(game: Any, result: Dict[str, Any]) -> None:
    """Tag makes in an active late-clock chain so BIP/SIP can route to FLSS."""
    gs = game.game_state
    time_remaining = int(gs.get("time_remaining") or 0)
    if time_remaining <= 0:
        result["quarter_ends_after"] = True
        result["next_play_type"] = None
        result.pop("next_turn", None)
        return
    if not _late_chain_active(game, result):
        return
    activate_late_clock_eoq_chain(gs)
    mark_late_clock_eoq_turn(result)


def apply_eoq_final_free_throw_routing(
    game: Any,
    result: Dict[str, Any],
    *,
    makes_shot: bool,
) -> None:
    """After the final FT of a trip, apply clock-driven continuation rules."""
    gs = game.game_state
    time_remaining = int(gs.get("time_remaining") or 0)

    if time_remaining <= 0:
        result["quarter_ends_after"] = True
        result["next_play_type"] = None
        result.pop("next_turn", None)
        return

    if not is_late_clock_eoq(time_remaining):
        return

    activate_late_clock_eoq_chain(gs)
    mark_late_clock_eoq_turn(result)

    if makes_shot:
        result["next_play_type"] = "BASELINE_INBOUND"
        result["next_turn"] = "BASELINE_INBOUND"
        return

    rebound_type = result.get("rebound_type") or gs.get("last_rebound")
    if rebound_type == "OREB":
        rebounder = gs.get("last_rebounder")
        if rebounder is not None:
            gs["pending_oreb"] = {
                "rebounder": rebounder,
                "rebounder_id": getattr(rebounder, "player_id", None),
                "from_block": False,
            }
        result["next_play_type"] = "OREB"
        result["next_turn"] = "OREB"
    elif rebound_type == "DREB":
        result["terminal_dreb_eoq"] = True
        result["next_play_type"] = "DREB"
        result["next_turn"] = "DREB"


def schedule_flss_after_inbound(game: Any, inbound_source_turn: Optional[Dict[str, Any]]) -> None:
    """After BIP/SIP when clock remains, next possession is FLSS sprint-and-shoot."""
    if not isinstance(inbound_source_turn, dict):
        return
    if not inbound_source_turn.get("late_clock_eoq"):
        return
    if int(game.game_state.get("time_remaining") or 0) <= 0:
        return
    activate_late_clock_eoq_chain(game.game_state)
    game.game_state["flss_possession_pending"] = True
    game.game_state["offensive_state"] = "HCO"
    try:
        from BackEnd.engine.eoq_debug_log import begin_eoq_trace_sequence, log_eoq_chain_event

        begin_eoq_trace_sequence(game)
        log_eoq_chain_event(
            game,
            "FLSS_SCHEDULED_AFTER_INBOUND",
            extra={
                "inbound_source_result_type": inbound_source_turn.get("result_type"),
                "inbound_source_late_clock_eoq": inbound_source_turn.get("late_clock_eoq"),
                "time_remaining": game.game_state.get("time_remaining"),
            },
        )
    except Exception:
        pass


def resolve_late_clock_bip_runoff(last_turn: dict | None, time_remaining: int) -> int:
    """Game-clock seconds to burn on BIP after a late-clock EOQ-chain make."""
    if not isinstance(last_turn, dict):
        return 0
    if not last_turn.get("late_clock_eoq"):
        return 0
    if time_remaining <= 0:
        return 0
    return max(0, min(LATE_CLOCK_BIP_RUNOFF_SECONDS, int(time_remaining)))


def ensure_quarter_end_clock_drain(game: Any, result: Dict[str, Any]) -> None:
    """Force remaining game clock onto the turn when the period ends on this possession."""
    if not isinstance(result, dict):
        return
    clock_before = int(getattr(game, "game_state", {}).get("time_remaining") or 0)
    if clock_before <= 0:
        return
    terminal = bool(
        result.get("quarter_ends_after")
        or (
            result.get("next_play_type") is None
            and result.get("next_turn") is None
            and str(result.get("result_type") or "").upper()
            in {"MAKE", "MISS", "BLOCK", "PUTBACK_MAKE", "PUTBACK_MISS", "FINAL_HOLD", "RUN_OUT_CLOCK"}
        )
    )
    if not terminal:
        return
    result["time_elapsed"] = clock_before
    result["clock_start"] = clock_before
    result["clock_end"] = 0
    result["quarter_ends_after"] = True
    result["next_play_type"] = None
    result.pop("next_turn", None)


def finalize_terminal_dreb_turn(game: Any, dreb_turn: Dict[str, Any]) -> None:
    """Burn remaining game clock after terminal late-clock DREB animation."""
    if not dreb_turn.get("terminal_dreb_eoq"):
        return
    ensure_quarter_end_clock_drain(game, dreb_turn)


def finalize_flss_post_emit(game: Any, result: Dict[str, Any]) -> None:
    """Post-emit FLSS clock/quarter-end — respect shot outcome when time remains."""
    if not result.get("flss"):
        return

    clock_before = int(game.game_state.get("time_remaining") or 0)
    result_type = (result.get("result_type") or "").upper()

    anim = result.get("animation_steps") or []
    if anim:
        first_clock = (anim[0].get("start") or {}).get("clock") or {}
        last_clock = (anim[-1].get("end") or {}).get("clock") or {}
        cs_start = first_clock.get("clock_remaining")
        cs_end = last_clock.get("clock_remaining")
        if cs_start is not None and cs_end is not None:
            schema_burn = max(0.0, float(cs_start) - float(cs_end))
            result["time_elapsed"] = max(1, int(round(schema_burn)))

    if clock_before <= 0 or (
        result.get("quarter_ends_after") and not result.get("next_play_type")
    ):
        ensure_quarter_end_clock_drain(game, result)
        return

    # Low-clock makes must burn the full remaining second so BIP is skipped at 0:00.
    if clock_before <= 1 and result_type == "MAKE":
        result["time_elapsed"] = clock_before

    mark_late_clock_eoq_turn(result)
    activate_late_clock_eoq_chain(game.game_state)

    if result_type == "MAKE" and result.get("next_play_type") == "BASELINE_INBOUND":
        return

    if result_type in ("MISS", "BLOCK") and result.get("terminal_dreb_eoq"):
        ensure_quarter_end_clock_drain(game, result)
        return

    if result_type in ("MISS", "BLOCK") and result.get("next_play_type") == "OREB":
        return

    if result.get("next_play_type") == "FREE_THROW":
        return

    result["time_elapsed"] = max(1, int(result.get("time_elapsed") or 1))


def scrub_timeout_fields_from_snapshot(snapshot: Dict[str, Any]) -> None:
    """Remove timeout restart metadata from a quarter-break anchor snapshot."""
    if not isinstance(snapshot, dict):
        return
    gs = snapshot.get("game_state")
    if isinstance(gs, dict):
        for key in TIMEOUT_SNAPSHOT_KEYS:
            gs.pop(key, None)
    for key in TIMEOUT_SNAPSHOT_KEYS:
        snapshot.pop(key, None)
