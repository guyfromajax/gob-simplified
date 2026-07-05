"""
Auto-capture FCP/HCT over-and-back repro data.

Logs when a dynamic press/trap turn completes a §6 pass to a backcourt receiver,
when the engine fires OVER_BACK, or when dead_ball_fumble overwrites OVER_BACK.

Toggle ``LOG_OOB_FCP_HCT_CAPTURE`` off when done debugging.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# Set False to silence O&B capture logs.
LOG_OOB_FCP_HCT_CAPTURE = True

_CAPTURE_PREFIX = "[OOB FCP/HCT CAPTURE]"


def _emit(payload: Dict[str, Any]) -> None:
    if not LOG_OOB_FCP_HCT_CAPTURE:
        return
    print(f"{_CAPTURE_PREFIX} {json.dumps(payload, default=str)}", flush=True)


def _summarize_pass_segments(
    loop_segments: List[Dict[str, Any]],
    is_away_offense: bool,
) -> List[Dict[str, Any]]:
    from BackEnd.engine.over_and_back import in_backcourt, is_over_and_back_pass

    out: List[Dict[str, Any]] = []
    for idx, seg in enumerate(loop_segments):
        if (seg.get("reason") or "") != "hct_pass":
            continue
        receiver_pos = seg.get("pass_to_pos") or seg.get("ball_owner_pos")
        receiver_xy = (seg.get("off_end") or {}).get(receiver_pos) or {}
        rx = float(receiver_xy.get("x", 50))
        passer_pos = seg.get("pass_from_pos")
        passer_xy = (seg.get("off_end") or {}).get(passer_pos) or {}
        out.append(
            {
                "segment_index": idx,
                "passer_pos": passer_pos,
                "receiver_pos": receiver_pos,
                "passer_xy": dict(passer_xy),
                "receiver_xy": dict(receiver_xy),
                "receiver_in_backcourt": in_backcourt(rx, is_away_offense),
            }
        )
    return out


def log_pass_oob_check(
    *,
    turn_mode: str,
    frontcourt_established: bool,
    is_away_offense: bool,
    passer_pos: str,
    receiver_pos: str,
    passer_xy: Dict[str, Any],
    receiver_xy: Dict[str, Any],
    violation_fired: bool,
    loop_segment_count: int,
    frontcourt_grace_bh_pos: Optional[str] = None,
) -> None:
    """Engine: immediately after §6 pass completes and O&B is evaluated."""
    if not LOG_OOB_FCP_HCT_CAPTURE:
        return
    from BackEnd.engine.over_and_back import in_backcourt

    rx = float(receiver_xy.get("x", 50))
    if not in_backcourt(rx, is_away_offense) and not violation_fired:
        return

    _emit(
        {
            "phase": "engine_pass_check",
            "turn_mode": turn_mode,
            "frontcourt_established": frontcourt_established,
            "frontcourt_grace_bh_pos": frontcourt_grace_bh_pos,
            "is_away_offense": is_away_offense,
            "passer_pos": passer_pos,
            "receiver_pos": receiver_pos,
            "passer_xy": dict(passer_xy),
            "receiver_xy": dict(receiver_xy),
            "receiver_in_backcourt": in_backcourt(rx, is_away_offense),
            "violation_fired": violation_fired,
            "loop_segment_count_before_break": loop_segment_count,
        }
    )


def log_turn_terminal_oob(
    *,
    turn_mode: str,
    result_type: str,
    turnover_type: str,
    text_suffix: str,
    loop_segments: List[Dict[str, Any]],
    is_away_offense: bool,
    bh_pos: str,
) -> None:
    """Engine: end of ``compute_dynamic_hct_turn`` when capture-worthy."""
    if not LOG_OOB_FCP_HCT_CAPTURE:
        return

    passes = _summarize_pass_segments(loop_segments, is_away_offense)
    backcourt_passes = [p for p in passes if p.get("receiver_in_backcourt")]
    if (
        not backcourt_passes
        and (turnover_type or "").upper() != "OVER_BACK"
        and "over & back" not in (text_suffix or "").lower()
    ):
        return

    _emit(
        {
            "phase": "engine_turn_end",
            "turn_mode": turn_mode,
            "result_type": result_type,
            "turnover_type": turnover_type,
            "text_suffix": text_suffix,
            "bh_pos": bh_pos,
            "is_away_offense": is_away_offense,
            "backcourt_pass_count": len(backcourt_passes),
            "backcourt_passes": backcourt_passes,
            "loop_segment_count": len(loop_segments),
        }
    )


def log_fumble_overwrote_oob(
    turn_result: Dict[str, Any],
    *,
    new_label: str,
) -> None:
    """Emitter: dead_ball_fumble replaced OVER_BACK (or over-and-back text) with travel/DD."""
    if not LOG_OOB_FCP_HCT_CAPTURE:
        return

    prior_type = (turn_result.get("turnover_type") or "").upper()
    text = (turn_result.get("text") or "").lower()
    is_oob = prior_type == "OVER_BACK" or "over & back" in text or "over and back" in text
    if not is_oob:
        return

    _emit(
        {
            "phase": "fumble_override",
            "result_type": turn_result.get("result_type"),
            "prior_turnover_type": turn_result.get("turnover_type"),
            "new_turnover_type": new_label,
            "text": turn_result.get("text"),
            "current_turn": turn_result.get("current_turn"),
            "suppress_turn_prep_turnover_announce": True,
        }
    )
