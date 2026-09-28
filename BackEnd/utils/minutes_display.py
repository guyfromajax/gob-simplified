"""Whole minutes shown for a game box-score MIN.

Game ``MIN`` is seconds. The box score (`formatMinutes`) shows ``floor(seconds / 60)``.
Season and career ``MIN`` are already unrounded minutes (`stat_updater.season_minutes`)
and do not go through this helper.
"""

from typing import Any


def display_minutes(seconds: Any) -> int:
    """Box-score minutes: floor(game seconds / 60). Missing or non-numeric → 0."""
    try:
        n = int(seconds)
    except (TypeError, ValueError):
        return 0
    if n < 0:
        return 0
    return n // 60
