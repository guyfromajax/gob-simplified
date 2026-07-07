"""Tests for Around The League board reorder and week labels."""

from __future__ import annotations

from BackEnd.utils.around_the_league import (
    ATL_WEEK_LABELS,
    _apply_reorder,
    atl_week_label,
)


def _slot(user_id: str) -> dict:
    return {"user_id": user_id, "completed_at": f"2026-07-07T12:00:00Z-{user_id}"}


def test_apply_reorder_new_user_enters_slot_one_and_drops_eighth():
    slots = [_slot(str(i)) for i in range(1, 9)]
    entry = _slot("new")
    result = _apply_reorder(slots, entry)
    assert [s["user_id"] for s in result] == ["new", "1", "2", "3", "4", "5", "6", "7"]
    assert len(result) == 8


def test_apply_reorder_existing_user_at_slot_three_shifts_only_preceding():
    slots = [_slot(str(i)) for i in range(1, 9)]
    entry = _slot("3")
    result = _apply_reorder(slots, entry)
    assert [s["user_id"] for s in result] == ["3", "1", "2", "4", "5", "6", "7", "8"]


def test_apply_reorder_existing_user_at_slot_one_stays_head():
    slots = [_slot(str(i)) for i in range(1, 5)]
    entry = _slot("1")
    result = _apply_reorder(slots, entry)
    assert [s["user_id"] for s in result] == ["1", "2", "3", "4"]


def test_apply_reorder_partial_board_newcomer_fills_without_dropping():
    slots = [_slot("a"), _slot("b"), _slot("c")]
    entry = _slot("d")
    result = _apply_reorder(slots, entry)
    assert [s["user_id"] for s in result] == ["d", "a", "b", "c"]


def test_atl_week_label_regular_season():
    assert atl_week_label(12) == "Week 12"
    assert atl_week_label(26) == "Week 26"


def test_atl_week_label_tournament_uses_fcc_copy():
    assert atl_week_label(27) == "Conference Tourney First Round"
    assert atl_week_label(28) == "Conference Tourney Semifinals"
    assert atl_week_label(30) == "Region Tourney First Round"
    assert atl_week_label(34) == "National Championship"


def test_atl_week_labels_cover_eos_weeks_27_through_34():
    for week in range(27, 35):
        assert atl_week_label(week) == ATL_WEEK_LABELS[week]
