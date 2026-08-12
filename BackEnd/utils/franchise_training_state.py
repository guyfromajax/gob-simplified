"""Franchise training split-phase state (user team vs CPU teams)."""

from __future__ import annotations

from typing import Any, Mapping


def franchise_training_fully_complete_for_week(
    training_status: Mapping[str, Any] | None,
    franchise_week: int,
) -> bool:
    """
    True when the franchise week is fully done: user and CPU training persisted.

    Legacy saves have training_completed True and no user_training_applied_week (single-shot path).
    """
    if not training_status:
        return False
    if not training_status.get("training_completed"):
        return False
    try:
        ts_week = int(training_status.get("week") or 0)
    except (TypeError, ValueError):
        return False
    if ts_week != int(franchise_week):
        return False
    if "user_training_applied_week" not in training_status:
        return True
    try:
        cpu_week = int(training_status.get("cpu_training_complete_week") or 0)
    except (TypeError, ValueError):
        return False
    return cpu_week == int(franchise_week)


def franchise_user_training_applied_for_week(
    training_status: Mapping[str, Any] | None,
    franchise_week: int,
) -> bool:
    if not training_status:
        return False
    try:
        return int(training_status.get("user_training_applied_week") or 0) == int(franchise_week)
    except (TypeError, ValueError):
        return False
