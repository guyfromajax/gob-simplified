"""Clock-driven end-of-quarter progression (Final Shot / FLSS chains).

Quarter end is determined by ``time_remaining`` reaching 0, not by possession
flags alone. When the game clock still has time after a late-clock shot or final
free throw, possession chains continue (BIP → FLSS, OREB putback, terminal DREB).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

LATE_CLOCK_THRESHOLD = 30
OREB_PUTBACK_ONLY_THRESHOLD = 6


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


def _late_chain_active(game: Any, result: Dict[str, Any]) -> bool:
    gs = getattr(game, "game_state", None) or {}
    return bool(
        gs.get("final_turn")
        or result.get("late_clock_eoq")
        or result.get("flss")
        or result.get("final_turn")
        or gs.get("flss_possession_pending")
    )


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
    """Tag makes in a late-clock chain so BIP/SIP can route to FLSS."""
    gs = game.game_state
    time_remaining = int(gs.get("time_remaining") or 0)
    if time_remaining <= 0:
        result["quarter_ends_after"] = True
        result["next_play_type"] = None
        result.pop("next_turn", None)
        return
    if _late_chain_active(game, result) or is_late_clock_eoq(time_remaining):
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
    game.game_state["flss_possession_pending"] = True
    game.game_state["offensive_state"] = "HCO"


def finalize_terminal_dreb_turn(game: Any, dreb_turn: Dict[str, Any]) -> None:
    """Burn remaining game clock after terminal late-clock DREB animation."""
    if not dreb_turn.get("terminal_dreb_eoq"):
        return
    clock_before = int(game.game_state.get("time_remaining") or 0)
    dreb_turn["quarter_ends_after"] = True
    dreb_turn["next_play_type"] = None
    dreb_turn.pop("next_turn", None)
    if clock_before > 0:
        dreb_turn["time_elapsed"] = clock_before
        dreb_turn["clock_start"] = clock_before
        dreb_turn["clock_end"] = 0


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
        if clock_before > 0:
            result["time_elapsed"] = clock_before
            result["clock_start"] = clock_before
            result["clock_end"] = 0
        result["quarter_ends_after"] = True
        result["next_play_type"] = None
        result.pop("next_turn", None)
        return

    mark_late_clock_eoq_turn(result)

    if result_type == "MAKE" and result.get("next_play_type") == "BASELINE_INBOUND":
        return

    if result_type in ("MISS", "BLOCK") and result.get("terminal_dreb_eoq"):
        return

    if result_type in ("MISS", "BLOCK") and result.get("next_play_type") == "OREB":
        return

    if result.get("next_play_type") == "FREE_THROW":
        return

    result["time_elapsed"] = max(1, int(result.get("time_elapsed") or 1))
