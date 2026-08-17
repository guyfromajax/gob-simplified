"""Recruiting wire payload — has_saved_board derivation.

Regression guard for a real bug: `has_saved_board` was `bool(ftd_doc.get("Recruits"))`,
but FTD "Recruits" is initialized to {"1".."20": None} at franchise creation
(franchise_manager.py) and again at every season rollover (franchise_routes.py). A
20-key dict of Nones is truthy, so the flag read True for a franchise that had never
saved a board — and for every season 2+ franchise arriving at week 20. That made the
week-20 gate unreachable, and the player would then hit the server-side 400 from the
week-20 training guard instead.

The Playwright suite structurally cannot catch this: it stubs `hasSavedBoard` rather
than deriving it from an FTD document.
"""

from BackEnd.api import franchise_routes as fr


# The exact shape written at franchise creation and at rollover.
EMPTY_INIT_RECRUITS = {str(i): None for i in range(1, 21)}

FID = "fid-sentinel"
TEAM_ID = "507f1f77bcf86cd799439011"


class _FakeFtdCollection:
    """Stands in for franchise_team_data_collection.find_one."""

    def __init__(self, doc):
        self._doc = doc
        self.queries = []

    def find_one(self, query, projection=None):
        self.queries.append(query)
        return self._doc


def _franchise_doc(**overrides):
    doc = {"_id": FID, "week": 20}
    doc.update(overrides)
    return doc


def _payload(monkeypatch, ftd_doc, franchise_doc=None, team_id=TEAM_ID):
    fake = _FakeFtdCollection(ftd_doc)
    monkeypatch.setattr(fr, "franchise_team_data_collection", fake)
    # No events in these cases, so the feed's name lookups never run.
    return fr._build_recruiting_wire_payload(franchise_doc or _franchise_doc(), team_id)


# ---------------------------------------------------------------------------
# The three cases named in review
# ---------------------------------------------------------------------------

def test_all_none_init_dict_is_not_a_saved_board(monkeypatch):
    """The bug: 20 keys of None is truthy, but it is not a board."""
    payload = _payload(monkeypatch, {"Recruits": dict(EMPTY_INIT_RECRUITS)})
    assert payload["has_saved_board"] is False


def test_one_populated_slot_is_a_saved_board(monkeypatch):
    recruits = dict(EMPTY_INIT_RECRUITS)
    recruits["1"] = "recruit-abc"
    payload = _payload(monkeypatch, {"Recruits": recruits})
    assert payload["has_saved_board"] is True


def test_missing_or_none_recruits_is_not_a_saved_board(monkeypatch):
    assert _payload(monkeypatch, {})["has_saved_board"] is False
    assert _payload(monkeypatch, {"Recruits": None})["has_saved_board"] is False
    assert _payload(monkeypatch, None)["has_saved_board"] is False


# ---------------------------------------------------------------------------
# Adjacent behaviour worth pinning
# ---------------------------------------------------------------------------

def test_populated_slot_anywhere_in_the_ladder_counts(monkeypatch):
    """A board saved into a later slot is still a board."""
    for slot in ("2", "7", "20"):
        recruits = dict(EMPTY_INIT_RECRUITS)
        recruits[slot] = "recruit-xyz"
        payload = _payload(monkeypatch, {"Recruits": recruits})
        assert payload["has_saved_board"] is True, f"slot {slot}"


def test_empty_string_slots_do_not_count(monkeypatch):
    """Falsy-but-present values are empty slots, matching _team_order_list."""
    recruits = dict(EMPTY_INIT_RECRUITS)
    recruits["1"] = ""
    payload = _payload(monkeypatch, {"Recruits": recruits})
    assert payload["has_saved_board"] is False


def test_matches_the_helper_the_week_20_guards_use(monkeypatch):
    """The flag must agree with _team_order_list, which the server-side week-20
    training guards use to decide whether to 400. Disagreement is the bug class."""
    cases = [
        dict(EMPTY_INIT_RECRUITS),
        {**EMPTY_INIT_RECRUITS, "1": "r1"},
        {**EMPTY_INIT_RECRUITS, "20": "r20"},
        {},
        None,
    ]
    for recruits in cases:
        payload = _payload(monkeypatch, {"Recruits": recruits})
        expected = bool(fr._team_order_list(recruits))
        assert payload["has_saved_board"] is expected, f"disagreed for {recruits}"


def test_no_team_id_reports_no_board_without_querying(monkeypatch):
    fake = _FakeFtdCollection({"Recruits": {**EMPTY_INIT_RECRUITS, "1": "r1"}})
    monkeypatch.setattr(fr, "franchise_team_data_collection", fake)
    payload = fr._build_recruiting_wire_payload(_franchise_doc(), None)
    assert payload["has_saved_board"] is False
    assert fake.queries == []


def test_absent_franchise_doc_returns_a_safe_shape(monkeypatch):
    payload = _payload(monkeypatch, {}, franchise_doc=None)
    assert payload["has_saved_board"] is False
    assert payload["unseen_count"] == 0
    assert payload["counts"] == {"moved": 0, "dropped": 0}
    assert payload["events"] == []


def test_board_saved_week_is_scalar_and_defaults_to_zero(monkeypatch):
    """The other marker the button reads — a scalar, so no sentinel-truthiness risk."""
    payload = _payload(monkeypatch, {"Recruits": None})
    assert payload["board_saved_week"] == 0
    payload = _payload(
        monkeypatch, {"Recruits": None},
        franchise_doc=_franchise_doc(**{fr.RECRUITING_BOARD_SAVED_WEEK_FIELD: 22}),
    )
    assert payload["board_saved_week"] == 22
