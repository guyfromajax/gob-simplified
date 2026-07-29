"""Legacy franchise season-momentum updates.

This remains temporarily for behavior compatibility after removal of the distant
game engine. It is output-only: full simulations do not read these values.
"""

from __future__ import annotations

from typing import Any


MOMENTUM_SCORE_MIN = -10
MOMENTUM_SCORE_MAX = 10
MOMENTUM_WIN_GAIN = 1.5
MOMENTUM_LOSS_DECAY = 0.8
MOMENTUM_STREAK_WIN_BONUS = 0.5
MOMENTUM_STREAK_LOSS_RESET = 2.0


def _clamp_momentum_score(value: Any) -> float:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        raw = 0.0
    return max(MOMENTUM_SCORE_MIN, min(MOMENTUM_SCORE_MAX, raw))


def _chemistry_scale(team_chemistry_raw: Any) -> float:
    try:
        chemistry = int(team_chemistry_raw)
    except (TypeError, ValueError):
        chemistry = 7
    chemistry = max(7, min(25, chemistry))
    return max(1.0, chemistry / 10.0)


def _streak_int(team_attributes: dict | None, key: str) -> int:
    if not team_attributes:
        return 0
    try:
        return max(0, int(team_attributes.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def compute_season_momentum_updates(
    winner_team_attributes: dict | None,
    loser_team_attributes: dict | None,
) -> tuple[dict[str, float | int], dict[str, float | int]]:
    """Return the unchanged legacy momentum/streak updates for a game result."""
    winner_attrs = winner_team_attributes or {}
    loser_attrs = loser_team_attributes or {}

    winner_momentum = _clamp_momentum_score(winner_attrs.get("momentum_score", 0))
    loser_momentum = _clamp_momentum_score(loser_attrs.get("momentum_score", 0))
    winner_old_win_streak = _streak_int(winner_attrs, "distant_win_streak")
    loser_old_win_streak = _streak_int(loser_attrs, "distant_win_streak")
    loser_old_loss_streak = _streak_int(loser_attrs, "distant_loss_streak")

    winner_gain = MOMENTUM_WIN_GAIN * _chemistry_scale(
        winner_attrs.get("team_chemistry")
    )
    winner_new_win_streak = winner_old_win_streak + 1
    if winner_new_win_streak >= 3:
        winner_gain += MOMENTUM_STREAK_WIN_BONUS * (winner_new_win_streak - 2)
    winner_new_momentum = _clamp_momentum_score(winner_momentum + winner_gain)

    loser_decay = MOMENTUM_LOSS_DECAY * _chemistry_scale(
        loser_attrs.get("team_chemistry")
    )
    loser_new_momentum = loser_momentum - loser_decay
    if loser_old_win_streak >= 3:
        loser_new_momentum -= MOMENTUM_STREAK_LOSS_RESET
    loser_new_momentum = _clamp_momentum_score(loser_new_momentum)

    return (
        {
            "momentum_score": winner_new_momentum,
            "distant_win_streak": winner_new_win_streak,
            "distant_loss_streak": 0,
        },
        {
            "momentum_score": loser_new_momentum,
            "distant_win_streak": 0,
            "distant_loss_streak": loser_old_loss_streak + 1,
        },
    )
