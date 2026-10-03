"""The one exceptional-attribute-gain rule, shared by the Office and the training report.

Ported from ``FrontEnd/static/training-report.js::getExceptionalGainThreshold``:

    function getExceptionalGainThreshold() {
      return getReportWeekNumber() === 1 ? 10 : 5;
    }

so the rule is **one raw training gain at or above the report week's threshold**:

    week 1 (training camp)   delta >= 10
    weeks 2+ (in season)     delta >= 5

Inputs, both off the stored training report (``franchise.latest_training`` /
``franchise_team_data.training_reports.<week>``):

* ``week`` — the report's own ``week``, not the franchise's current week. A camp
  report read in week 2 keeps the camp threshold.
* the **raw** per-attribute delta from ``player_logs`` (legacy name
  ``player_changes``): ``{player name: {attribute: delta}}``, written by
  ``training_execution_v2`` as ``(anchor + banked fraction)`` after minus before.

Only gains qualify: a drop is never exceptional, and the marker shows on a loss
week too (it is about the gain, not the result).

Note the two scales. ``player_logs`` deltas are raw attribute points (0–99
scale); ``player_attribute_display_movements`` carries the first-digit display
bucket (``raw // 10``) the Office lists. The threshold is raw, so the digest
joins its display rows back to the raw delta rather than comparing buckets.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

CAMP_WEEK = 1
CAMP_THRESHOLD = 10
IN_SEASON_THRESHOLD = 5


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN is not a gain


def exceptional_gain_threshold(week: Any) -> int:
    """``10`` for the camp report (week 1), ``5`` for every in-season report."""
    try:
        week_n = int(week)
    except (TypeError, ValueError):
        week_n = 0
    return CAMP_THRESHOLD if week_n == CAMP_WEEK else IN_SEASON_THRESHOLD


def is_exceptional_gain(delta: Any, week: Any) -> bool:
    """True when one raw attribute delta is a gain at or above the week's threshold."""
    number = _number(delta)
    if number is None:
        return False
    return number >= exceptional_gain_threshold(week)


def raw_player_gains(report: Mapping[str, Any] | None) -> dict[str, dict[str, float]]:
    """``{player name: {attribute: raw delta}}`` from the report's ``player_logs``.

    ``player_logs`` is keyed by display name (its legacy shape), so two players
    with the same name share one entry — the same limitation every other reader
    of this map has.
    """
    if not isinstance(report, Mapping):
        return {}
    logs = report.get("player_logs")
    if not isinstance(logs, Mapping):
        logs = report.get("player_changes")
    if not isinstance(logs, Mapping):
        return {}
    out: dict[str, dict[str, float]] = {}
    for name, changes in logs.items():
        if not isinstance(changes, Mapping):
            continue
        row: dict[str, float] = {}
        for attribute, delta in changes.items():
            number = _number(delta)
            if number is not None:
                row[str(attribute)] = number
        if row:
            out[str(name)] = row
    return out


def exceptional_attributes(report: Mapping[str, Any] | None) -> set[tuple[str, str]]:
    """``(player name, attribute)`` pairs whose raw gain clears the report's threshold."""
    week = (report or {}).get("week")
    return {
        (name, attribute)
        for name, changes in raw_player_gains(report).items()
        for attribute, delta in changes.items()
        if is_exceptional_gain(delta, week)
    }


def exceptional_gain_rows(report: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """The same pairs as JSON rows, for the training-report route. Stable order."""
    return [
        {"name": name, "attribute": attribute}
        for name, attribute in sorted(exceptional_attributes(report))
    ]
