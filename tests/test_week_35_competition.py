"""Week-35 competition counts and the shared roster-capacity payload.

The Field column on signing day shows "how many programs are funding him". That number
must come from the seeded CPU week-35 boards, and must count FUNDING (points > 0) rather
than mere presence on a board — a zero-point slot is not competition.

Capacity is deliberately one server-side helper: signing day and the invite board's rail
both read it, and two independent client derivations would drift.
"""

import pytest

from BackEnd.api import franchise_routes as fr


FID = "fid-comp"
TEAM_A = "507f1f77bcf86cd799439011"
TEAM_B = "507f1f77bcf86cd799439012"


def _orders(*entries):
    """Build an FTD recruiting_orders_week_35 dict, 1-indexed like the normalizer."""
    return {str(i + 1): e for i, e in enumerate(entries)}


class _FakeFtd:
    def __init__(self, docs):
        self.docs = docs

    def find(self, query, projection=None):
        return list(self.docs)

    def find_one(self, query, projection=None):
        return self.docs[0] if self.docs else {}


def _counts(monkeypatch, docs):
    monkeypatch.setattr(fr, "franchise_team_data_collection", _FakeFtd(docs))
    return fr._week_35_competition_counts(FID)


# ---------------------------------------------------------------------------
# Counting rules
# ---------------------------------------------------------------------------

def test_counts_one_program_per_funded_recruit(monkeypatch):
    docs = [
        {fr.RECRUITING_ORDERS_WEEK_35_FIELD: _orders(
            {"id": "r-1", "points": 12}, {"id": "r-2", "points": 5})},
        {fr.RECRUITING_ORDERS_WEEK_35_FIELD: _orders({"id": "r-1", "points": 3})},
    ]
    assert _counts(monkeypatch, docs) == {"r-1": 2, "r-2": 1}


def test_zero_point_slots_are_not_funding(monkeypatch):
    """A recruit ranked with no points behind him is not competition."""
    docs = [
        {fr.RECRUITING_ORDERS_WEEK_35_FIELD: _orders(
            {"id": "r-1", "points": 0}, {"id": "r-2", "points": 7})},
    ]
    assert _counts(monkeypatch, docs) == {"r-2": 1}


def test_a_team_counts_once_even_if_listed_twice(monkeypatch):
    docs = [
        {fr.RECRUITING_ORDERS_WEEK_35_FIELD: _orders(
            {"id": "r-1", "points": 4}, {"id": "r-1", "points": 6})},
    ]
    assert _counts(monkeypatch, docs) == {"r-1": 1}


def test_no_boards_yields_empty_not_zeros(monkeypatch):
    """Empty means "no field yet" on the UI, which is different from zero competition."""
    assert _counts(monkeypatch, [{}]) == {}
    assert _counts(monkeypatch, []) == {}


def test_malformed_entries_are_skipped(monkeypatch):
    docs = [
        {fr.RECRUITING_ORDERS_WEEK_35_FIELD: _orders(
            {"id": "", "points": 9},
            {"id": "r-2", "points": "not-a-number"},
            {"id": "r-3", "points": 2},
            "junk",
        )},
    ]
    # Blank id, non-numeric points and a non-dict entry are all skipped; only r-3 counts.
    assert _counts(monkeypatch, docs) == {"r-3": 1}


def test_negative_points_do_not_count(monkeypatch):
    docs = [{fr.RECRUITING_ORDERS_WEEK_35_FIELD: _orders({"id": "r-1", "points": -5})}]
    assert _counts(monkeypatch, docs) == {}


# ---------------------------------------------------------------------------
# Shared capacity payload
# ---------------------------------------------------------------------------

def test_capacity_payload_shape(monkeypatch):
    monkeypatch.setattr(fr, "_calculate_available_roster_spots", lambda fid, tid: 4)
    monkeypatch.setattr(fr, "_calculate_available_scholarships", lambda fid, tid: 2)
    payload = fr._roster_capacity_payload(FID, TEAM_A)
    assert payload == {
        "roster_spots": 4, "scholarships": 2,
        "roster_cap": fr.ROSTER_CAP, "roster_used": fr.ROSTER_CAP - 4,
    }


def test_capacity_payload_reuses_the_existing_helpers(monkeypatch):
    """It must not recompute — a changed helper must change the payload."""
    calls = []

    def spots(fid, tid):
        calls.append("spots")
        return 9

    monkeypatch.setattr(fr, "_calculate_available_roster_spots", spots)
    monkeypatch.setattr(fr, "_calculate_available_scholarships", lambda fid, tid: 1)
    payload = fr._roster_capacity_payload(FID, TEAM_A)
    assert calls == ["spots"]
    assert payload["roster_spots"] == 9
    assert payload["roster_used"] == fr.ROSTER_CAP - 9


def test_capacity_payload_without_a_team_is_safe(monkeypatch):
    payload = fr._roster_capacity_payload(FID, None)
    assert payload["roster_spots"] == 0
    assert payload["roster_used"] == fr.ROSTER_CAP


def test_roster_used_never_goes_negative(monkeypatch):
    monkeypatch.setattr(fr, "_calculate_available_roster_spots", lambda fid, tid: 99)
    monkeypatch.setattr(fr, "_calculate_available_scholarships", lambda fid, tid: 0)
    assert fr._roster_capacity_payload(FID, TEAM_A)["roster_used"] == 0
