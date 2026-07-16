"""Shared Fast Break UESS observability helpers.

These helpers are intentionally read-only. They summarize the emitted Fast
Break schema/StepState facts without changing game, animation, or possession
state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


_reported_fb_uess_fallback_keys = set()


def build_fb_uess_summary(
    result: Dict[str, Any],
    game: Optional[Any] = None,
    *,
    fallback_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a compact, searchable summary for one Fast Break result."""
    if not isinstance(result, dict):
        result = {}

    steps = result.get("animation_steps") or []
    steps = steps if isinstance(steps, list) else []
    first_step = steps[0] if steps and isinstance(steps[0], dict) else {}
    last_step = steps[-1] if steps and isinstance(steps[-1], dict) else {}
    first_start = first_step.get("start") or {}
    last_end = last_step.get("end") or {}
    first_clock = first_start.get("clock") or {}
    last_clock = last_end.get("clock") or {}
    final_coords = last_end.get("coords") or {}

    start_clock = _number(first_clock.get("clock_remaining"))
    end_clock = _number(last_clock.get("clock_remaining"))
    schema_clock_burn = None
    if start_clock is not None and end_clock is not None:
        schema_clock_burn = round(max(0.0, start_clock - end_clock), 3)

    return {
        "game_id": _game_id(result, game),
        "fast_break_play": result.get("fast_break_play")
        or (result.get("roles") or {}).get("fast_break_play")
        or "unknown",
        "result_type": result.get("result_type") or "unknown",
        "step_count": len(steps),
        "schema_clock_burn": schema_clock_burn,
        "time_elapsed": result.get("time_elapsed"),
        "first_ball_owner": _ball_owner(first_start.get("ball") or {}),
        "final_ball_owner": _ball_owner(last_end.get("ball") or {}),
        "final_coords_count": len(final_coords) if isinstance(final_coords, dict) else 0,
        "fb_step_state_count": len(result.get("fb_step_states") or []),
        "fallback_reason": fallback_reason,
        "next_play_type": result.get("next_play_type"),
        "is_full_simulation": _is_full_simulation(game),
    }


def log_fb_uess_summary(
    result: Dict[str, Any],
    game: Optional[Any] = None,
    *,
    fallback_reason: Optional[str] = None,
    level: int = logging.WARNING,
) -> Dict[str, Any]:
    """Emit one low-noise summary log line for a Fast Break result."""
    summary = build_fb_uess_summary(
        result,
        game,
        fallback_reason=fallback_reason,
    )
    logging.log(
        level,
        "[FB_UESS] game_id=%s play=%s result=%s steps=%s schema_burn=%s "
        "time_elapsed=%s first_owner=%s final_owner=%s final_coords=%s "
        "states=%s fallback=%s",
        summary["game_id"],
        summary["fast_break_play"],
        summary["result_type"],
        summary["step_count"],
        summary["schema_clock_burn"],
        summary["time_elapsed"],
        summary["first_ball_owner"],
        summary["final_ball_owner"],
        summary["final_coords_count"],
        summary["fb_step_state_count"],
        summary["fallback_reason"],
    )
    _report_fb_uess_fallback_to_sentry(summary, result)
    return summary


def mark_fb_emitter_fallback(
    result: Dict[str, Any],
    family: str,
    guard: str,
    *,
    detail: Optional[str] = None,
) -> None:
    """Stamp a machine-readable fallback reason before an emitter returns None."""
    if isinstance(result, dict):
        result["fb_emitter_fallback_reason"] = f"{family}:{guard}"
    logging.warning(
        "[FB_EMITTER_FALLBACK] family=%s guard=%s detail=%s result_type=%s play=%s",
        family,
        guard,
        detail,
        result.get("result_type") if isinstance(result, dict) else None,
        result.get("fast_break_play") if isinstance(result, dict) else None,
    )


def _game_id(result: Dict[str, Any], game: Optional[Any]) -> Optional[str]:
    explicit = result.get("game_id")
    if explicit is not None:
        return str(explicit)
    if game is None:
        return None
    for attr in ("game_id", "game_doc_id"):
        value = getattr(game, attr, None)
        if value is not None:
            return str(value)
    game_state = getattr(game, "game_state", None)
    if isinstance(game_state, dict) and game_state.get("game_id") is not None:
        return str(game_state.get("game_id"))
    return None


def _is_full_simulation(game: Optional[Any]) -> bool:
    game_state = getattr(game, "game_state", None)
    if isinstance(game_state, dict):
        return bool(game_state.get("_is_full_simulation"))
    return False


def _report_fb_uess_fallback_to_sentry(
    summary: Dict[str, Any],
    result: Dict[str, Any],
) -> None:
    """Report live Fast Break UESS fallbacks without spamming full-sim noise."""
    fallback_reason = summary.get("fallback_reason")
    game_id = summary.get("game_id")
    if not fallback_reason or not game_id or summary.get("is_full_simulation"):
        return

    key = (
        game_id,
        summary.get("fast_break_play"),
        summary.get("result_type"),
        fallback_reason,
        summary.get("step_count"),
        summary.get("next_play_type"),
    )
    if key in _reported_fb_uess_fallback_keys:
        return
    _reported_fb_uess_fallback_keys.add(key)

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("gob.area", "fb_uess")
            scope.set_tag("gob.issue", "fast_break_uess_fallback")
            scope.set_tag("gob.fast_break_play", summary.get("fast_break_play"))
            scope.set_tag("gob.result_type", summary.get("result_type"))
            scope.set_tag("gob.fallback_reason", fallback_reason)
            scope.set_tag("gob.next_play_type", summary.get("next_play_type"))
            scope.set_context(
                "fb_uess_fallback",
                {
                    "game_id": game_id,
                    "fast_break_play": summary.get("fast_break_play"),
                    "result_type": summary.get("result_type"),
                    "next_play_type": summary.get("next_play_type"),
                    "step_count": summary.get("step_count"),
                    "fb_step_state_count": summary.get("fb_step_state_count"),
                    "schema_clock_burn": summary.get("schema_clock_burn"),
                    "time_elapsed": summary.get("time_elapsed"),
                    "first_ball_owner": summary.get("first_ball_owner"),
                    "final_ball_owner": summary.get("final_ball_owner"),
                    "final_coords_count": summary.get("final_coords_count"),
                    "fallback_reason": fallback_reason,
                    "fb_emitter_fallback_reason": result.get("fb_emitter_fallback_reason"),
                },
            )
            sentry_sdk.capture_message(
                "Fast Break UESS emitted fallback/no animation steps",
                level="error",
            )
    except Exception as exc:
        logging.warning("[FB_UESS_SENTRY] report failed: %s", exc)


def _ball_owner(ball: Dict[str, Any]) -> Optional[str]:
    for key in ("owner_player_id", "to_player_id", "from_player_id"):
        value = ball.get(key)
        if value is not None:
            return str(value)
    return None


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
