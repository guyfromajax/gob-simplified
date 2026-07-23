"""Shared policy for calibration diagnostics in simulation hot paths."""

from collections.abc import Mapping
from typing import Any


def calibration_diagnostics_enabled(game_or_state: Any) -> bool:
    """Return whether optional calibration diagnostics should run.

    Interactive and turn-by-turn games retain diagnostics by default. Bulk CPU
    games use ``_is_full_simulation`` while Practice Squad games use
    ``_headless_simulation``; either mode disables diagnostic-only work.

    The helper accepts a GameManager-like object or its ``game_state`` mapping so
    callers do not need to duplicate mode detection.
    """
    if isinstance(game_or_state, Mapping):
        game_state = game_or_state
    else:
        game_state = getattr(game_or_state, "game_state", None)

    if not isinstance(game_state, Mapping):
        return True

    return not (
        bool(game_state.get("_is_full_simulation"))
        or bool(game_state.get("_headless_simulation"))
    )
