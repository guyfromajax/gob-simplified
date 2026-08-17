"""Watchlist state — and the hard rule that it never touches FTD "Recruits".

The watchlist seeds the week-20 invite board, but only as client state. If it ever
persisted into FTD "Recruits", ``_team_order_list`` would become non-empty before the
player saved anything, and ``has_saved_board`` would flip True — silently reopening the
week-20 gate that the previous review closed. That is seedAlloc()'s mistake in a new
location, so it is asserted here rather than left to code review.

The watchlist is also a SHORTLIST, not a board: no ranks, no cap.
"""

import pytest

from BackEnd.api import franchise_routes as fr


FID = "fid-watch"
TEAM_ID = "507f1f77bcf86cd799439011"
EMPTY_INIT_RECRUITS = {str(i): None for i in range(1, 21)}


class _FakeFtd:
    def __init__(self, doc):
        self.doc = doc
        self.updates = []

    def find_one(self, query, projection=None):
        return self.doc

    def update_one(self, query, update, **kw):
        self.updates.append((query, update))
        return type("R", (), {"modified_count": 1})()

    def update_many(self, query, update, **kw):
        self.updates.append((query, update))
        return type("R", (), {"modified_count": 1})()


class _FakeRecruits:
    def __init__(self, ids):
        self.ids = set(ids)

    def count_documents(self, query, limit=None):
        rid = (query or {}).get("recruit_id")
        return 1 if rid in self.ids else 0


class _FakeFranchises:
    def __init__(self, doc):
        self.doc = doc
        self.updates = []

    def update_one(self, query, update, **kw):
        self.updates.append((query, update))
        self.doc.update((update or {}).get("$set") or {})
        return type("R", (), {"modified_count": 1})()


@pytest.fixture
def wired(monkeypatch):
    """Patch the collections and auth so the endpoint runs without a DB."""
    state = {}

    def _make(franchise_doc, ftd_doc=None, recruit_ids=("r-1", "r-2", "r-3")):
        doc = dict(franchise_doc)
        doc.setdefault("_id", FID)
        ftd = _FakeFtd(ftd_doc if ftd_doc is not None else {"Recruits": dict(EMPTY_INIT_RECRUITS)})
        franchises = _FakeFranchises(doc)
        monkeypatch.setattr(fr, "franchise_team_data_collection", ftd)
        monkeypatch.setattr(fr, "franchise_recruits_data_collection", _FakeRecruits(recruit_ids))
        monkeypatch.setattr(fr.db, "franchises", franchises, raising=False)
        monkeypatch.setattr(fr, "verify_franchise_owned_by_user", lambda *a, **k: doc)
        state.update(doc=doc, ftd=ftd, franchises=franchises)
        return state

    return _make


def _toggle(recruit_id, watching=None):
    req = fr.RecruitingWatchlistRequest(
        franchise_id=FID, recruit_id=recruit_id, watching=watching
    )
    return fr.toggle_recruiting_watchlist(req, user={"user_id": "u1"})


# ---------------------------------------------------------------------------
# The hard rule
# ---------------------------------------------------------------------------

def test_toggling_never_writes_ftd_recruits(wired):
    """The whole point: watchlist writes must not reach the board field."""
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: []})
    _toggle("r-1", True)
    _toggle("r-2", True)
    _toggle("r-1", False)
    assert s["ftd"].updates == [], "watchlist toggling wrote to FTD"


def test_toggling_only_writes_the_watchlist_field(wired):
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: []})
    _toggle("r-1", True)
    written_keys = set()
    for _query, update in s["franchises"].updates:
        written_keys |= set((update.get("$set") or {}).keys())
    assert written_keys == {fr.RECRUITING_WATCHLIST_FIELD}


def test_has_saved_board_stays_false_after_watchlisting(wired):
    """A full watchlist must not make the week-20 gate think a board exists."""
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: []})
    for rid in ("r-1", "r-2", "r-3"):
        _toggle(rid, True)
    payload = fr._build_recruiting_wire_payload(s["doc"], TEAM_ID)
    assert payload["has_saved_board"] is False
    assert fr._team_order_list(s["ftd"].doc.get("Recruits")) == []


def test_has_saved_board_still_true_once_a_board_is_actually_saved(wired):
    """Control: the flag is not simply hard-wired false."""
    saved = dict(EMPTY_INIT_RECRUITS)
    saved["1"] = "r-1"
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: ["r-1"]}, ftd_doc={"Recruits": saved})
    payload = fr._build_recruiting_wire_payload(s["doc"], TEAM_ID)
    assert payload["has_saved_board"] is True


# ---------------------------------------------------------------------------
# Shortlist semantics: no ranks, no cap
# ---------------------------------------------------------------------------

def test_watchlist_is_a_flat_list_not_a_slot_dict(wired):
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: []})
    res = _toggle("r-1", True)
    assert isinstance(res["watchlist"], list)
    assert res["watchlist"] == ["r-1"]


def test_watchlist_has_no_cap(wired):
    """MAX_BOARD (20) is the BOARD's cap. The shortlist is uncapped."""
    many = [f"r-{i}" for i in range(60)]
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: list(many[:-1])}, recruit_ids=many)
    res = _toggle(many[-1], True)
    assert res["count"] == 60
    assert len(res["watchlist"]) == 60


def test_insertion_order_preserved_and_deduped(wired):
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: ["r-2", "r-2", "r-1"]})
    res = _toggle("r-3", True)
    assert res["watchlist"] == ["r-2", "r-1", "r-3"]


# ---------------------------------------------------------------------------
# Toggle behaviour
# ---------------------------------------------------------------------------

def test_omitting_watching_toggles(wired):
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: []})
    assert _toggle("r-1")["watching"] is True
    assert _toggle("r-1")["watching"] is False


def test_explicit_watching_is_idempotent(wired):
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: ["r-1"]})
    res = _toggle("r-1", True)
    assert res["watching"] is True
    assert res["watchlist"] == ["r-1"]


def test_removing_an_absent_recruit_is_a_no_op(wired):
    s = wired({fr.RECRUITING_WATCHLIST_FIELD: ["r-2"]})
    res = _toggle("r-1", False)
    assert res["watching"] is False
    assert res["watchlist"] == ["r-2"]


def test_unknown_recruit_rejected(wired):
    from fastapi import HTTPException
    wired({fr.RECRUITING_WATCHLIST_FIELD: []})
    with pytest.raises(HTTPException) as exc:
        _toggle("not-a-recruit", True)
    assert exc.value.status_code == 400


def test_blank_recruit_id_rejected(wired):
    from fastapi import HTTPException
    wired({fr.RECRUITING_WATCHLIST_FIELD: []})
    with pytest.raises(HTTPException) as exc:
        _toggle("   ", True)
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Reader helper
# ---------------------------------------------------------------------------

def test_reader_normalizes_junk():
    assert fr._recruiting_watchlist(None) == []
    assert fr._recruiting_watchlist({}) == []
    assert fr._recruiting_watchlist({fr.RECRUITING_WATCHLIST_FIELD: None}) == []
    assert fr._recruiting_watchlist(
        {fr.RECRUITING_WATCHLIST_FIELD: ["a", "", None, " b ", "a"]}
    ) == ["a", "b"]
