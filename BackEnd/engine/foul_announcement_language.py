"""Canonical foul announcement language — the single source of truth.

**UESS compliance.** Choosing announcement copy is game logic, so it lives on the
backend. This module is the only place the foul-text tables exist. The frontend
renders `turn_result["foul_announcement_text"]`; it must not pick copy itself.
(`FrontEnd/static/js/phaser/utils/foulAnnouncementLanguage.js` held a verbatim
duplicate of these tables — it is now a deprecated fallback that only fires when
the backend supplied no text.)

**Two independent axes** select the weight pool for a defensive foul:

1. *Court region* — lane vs non-lane, from the foul's location context.
2. *Defender role* — was the fouler the on-ball defender, or off-ball?

Axis 2 is the new one. `select_foul_player` deliberately spreads 40% of
defensive fouls across the four non-matched defenders, because not every
defensive foul is on the ball. That distribution is correct and unchanged — but
the *language* has to match. An off-ball defender cannot commit a hand-check.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from BackEnd.utils.sim_random import announcement_rng as _default_rng

# --- Defender role vocabulary ------------------------------------------------

ON_BALL = "on_ball"
OFF_BALL = "off_ball"
EITHER = "either"
#: Off-ball by default, but legal on the ball when the ball handler is posting up.
POST_CONTEXT = "post_context"

#: Spots that count as "in the lane" for weight-pool selection.
LANE_LOCATIONS = frozenset(
    {
        "upper lowpost",
        "lower lowpost",
        "midpost",
        "highpost",
        "basketspot",
        "midlane",
        "toplane",
    }
)

#: Spots where the ball handler is posting up, which makes post-defense fouls
#: legal on the ball. Per user classification: lowPost and midPost only —
#: highPost / midLane / topLane do not qualify.
POST_UP_LOCATIONS = frozenset(
    {
        "upper lowpost",
        "lower lowpost",
        "midpost",
    }
)

# --- Weight tables -----------------------------------------------------------
# (text, non-lane weight, lane weight, defender role)

_DEFENSIVE_FOUL_ROWS: Sequence[Tuple[str, int, int, str]] = (
    ("Blocking Foul!", 25, 5, ON_BALL),
    ("Hand-Checking!", 25, 0, ON_BALL),
    ("Illegal Contact!", 10, 10, EITHER),
    ("Holding!", 15, 20, EITHER),
    ("Arm Bar!", 15, 10, EITHER),
    ("Pushing!", 10, 30, EITHER),
    ("Illegal Post Defense!", 0, 25, POST_CONTEXT),
)

#: Offensive fouls are always committed by the ball handler or a screener, so
#: they carry no defender-role axis.
_OFFENSIVE_FOUL_ROWS: Sequence[Tuple[str, int, int]] = (
    ("Push Off!", 30, 10),
    ("Illegal Screen!", 20, 10),
    ("Arm Extension!", 15, 10),
    ("Hooking!", 5, 5),
    ("Illegal Use Of Hands!", 10, 5),
    ("Elbowing!", 20, 20),
    ("Illegal Post Up!", 0, 40),
)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _location_candidates(turn_result: Dict[str, Any]) -> list:
    return [
        _norm(turn_result.get("location")),
        _norm(turn_result.get("spot")),
        _norm(turn_result.get("ball_spot")),
        _norm(turn_result.get("foul_location")),
        _norm(turn_result.get("foul_spot")),
    ]


def _matches_location_set(turn_result: Dict[str, Any], location_set) -> bool:
    if any(value in location_set for value in _location_candidates(turn_result)):
        return True
    text = _norm(turn_result.get("text"))
    if not text:
        return False
    return any(loc in text for loc in location_set)


def is_lane_foul_context(turn_result: Dict[str, Any]) -> bool:
    """True when the foul happened in the lane (selects the lane weight pool)."""
    return _matches_location_set(turn_result, LANE_LOCATIONS)


def is_post_up_context(turn_result: Dict[str, Any]) -> bool:
    """True when the ball handler is posting up at lowPost / midPost.

    This is what makes ``Illegal Post Defense!`` legal for an *on-ball* defender:
    the man he is guarding has the ball with his back to the basket.
    """
    return _matches_location_set(turn_result, POST_UP_LOCATIONS)


def defensive_foul_is_on_ball(foul_player: Any, ball_handler: Any) -> bool:
    """Was the fouler the defender matched to the ball handler?

    Mirrors ``select_foul_player``'s own matching rule: the on-ball defender is
    the one occupying the ball handler's lineup position.
    """
    if foul_player is None or ball_handler is None:
        return False
    fouler_pos = _norm(getattr(foul_player, "position", None))
    bh_pos = _norm(getattr(ball_handler, "position", None))
    if not fouler_pos or not bh_pos:
        return False
    return fouler_pos == bh_pos


def _role_is_eligible(role: str, *, is_on_ball: bool, post_up: bool) -> bool:
    if role == EITHER:
        return True
    if role == ON_BALL:
        return is_on_ball
    if role == OFF_BALL:
        return not is_on_ball
    if role == POST_CONTEXT:
        # Off-ball post battles are always fair game; on the ball it only reads
        # correctly when the man being guarded is actually posting up.
        return post_up if is_on_ball else True
    return True


def _weighted_pick(rows: Sequence[Tuple[str, int]], rng) -> Optional[str]:
    total = sum(max(0, int(w)) for _t, w in rows)
    if total <= 0:
        return None
    cursor = rng.random() * total
    for text, weight in rows:
        cursor -= max(0, int(weight))
        if cursor < 0:
            return text
    return rows[-1][0] if rows else None


def pick_defensive_foul_text(
    turn_result: Dict[str, Any],
    *,
    is_on_ball: bool = True,
    rng=_default_rng,
) -> str:
    """Pick defensive foul copy matching the fouler's role and court region.

    Flag-driven fouls short-circuit the table: over-the-back is inherently an
    off-ball rebounding foul, while quick fouls and reach-ins are inherently
    on-ball.
    """
    if turn_result.get("otb_foul"):
        return "Over The Back!"
    if turn_result.get("quick_foul"):
        return "Quick Foul!"
    if turn_result.get("reach_in_foul"):
        return "Reaching In!"

    lane = is_lane_foul_context(turn_result)
    post_up = is_post_up_context(turn_result)

    eligible = [
        (text, lane_w if lane else nonlane_w)
        for text, nonlane_w, lane_w, role in _DEFENSIVE_FOUL_ROWS
        if _role_is_eligible(role, is_on_ball=is_on_ball, post_up=post_up)
    ]
    return _weighted_pick(eligible, rng) or "DEFENSIVE FOUL!"


def pick_offensive_foul_text(turn_result: Dict[str, Any], rng=_default_rng) -> str:
    if turn_result.get("otb_foul"):
        return "Over The Back!"
    lane = is_lane_foul_context(turn_result)
    rows = [
        (text, lane_w if lane else nonlane_w)
        for text, nonlane_w, lane_w in _OFFENSIVE_FOUL_ROWS
    ]
    return _weighted_pick(rows, rng) or "OFFENSIVE FOUL!"


def stamp_foul_announcement_text(
    turn_result: Dict[str, Any],
    *,
    foul_team_type: str,
    is_on_ball: bool = True,
    rng=_default_rng,
) -> str:
    """Resolve foul copy once and stamp it for the frontend to render.

    Idempotent: an already-stamped payload is left alone so re-emission (batch
    replay, projection) cannot reroll the language mid-turn.
    """
    existing = turn_result.get("foul_announcement_text")
    if existing:
        return str(existing)

    if str(foul_team_type or "").upper() == "OFFENSE":
        text = pick_offensive_foul_text(turn_result, rng)
    else:
        text = pick_defensive_foul_text(turn_result, is_on_ball=is_on_ball, rng=rng)

    turn_result["foul_announcement_text"] = text
    turn_result["foul_is_on_ball"] = bool(is_on_ball)
    return text
