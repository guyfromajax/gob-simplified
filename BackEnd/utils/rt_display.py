"""Presentation-only formatting for player and recruit RT values.

RT remains numeric in storage, calculations, sorting, and API payloads. Change
``RT_DISPLAY_MODE`` to ``"number"`` to roll the display experiment back.
"""

from __future__ import annotations

from typing import Any


RT_DISPLAY_MODE = "letter"


def rt_letter_grade(value: Any) -> str:
    """Return the shared RT grade, or ``--`` for a missing/invalid value."""
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return "--"

    if rating >= 100:
        return "A++"
    if rating >= 90:
        return "A+"
    if rating >= 80:
        return "A"
    if rating >= 70:
        return "B+"
    if rating >= 60:
        return "B"
    if rating >= 50:
        return "C+"
    if rating >= 40:
        return "C"
    if rating >= 30:
        return "D"
    return "F"


def format_rt_display(value: Any) -> str:
    """Format RT for user-facing copy without changing the underlying value."""
    if RT_DISPLAY_MODE == "number":
        try:
            rating = float(value)
        except (TypeError, ValueError):
            return "--"
        return str(int(rating)) if rating.is_integer() else str(rating)
    return rt_letter_grade(value)
