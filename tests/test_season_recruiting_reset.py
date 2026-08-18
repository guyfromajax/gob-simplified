"""A new season must not inherit last season's recruiting record.

The recruit pool is regenerated at rollover, so every per-recruit record from the old
season is stale the moment the season turns. The wire was the visible symptom: week-28
lean events showed under a Season 2 / Week 1 header, with the badge still counting them.
"""
import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[1] / "BackEnd" / "api" / "franchise_routes.py"
TEXT = SRC.read_text()


def _reset_block() -> str:
    """The single $set that re-initialises the franchise doc in finish_season."""
    i = TEXT.index('"current_season": next_season,')
    return TEXT[i:TEXT.index("}}", i)]


# Every recruiting field on the franchise doc, and whether a new season keeps it.
RECRUITING_FIELDS = {
    "RECRUITING_LEAN_EVENTS_FIELD": "reset",       # the wire
    "RECRUITING_WIRE_SEEN_WEEK_FIELD": "reset",    # unseen-count marker
    "RECRUITING_WATCHLIST_FIELD": "reset",         # shortlist of last season's recruits
    "RECRUITING_BOARD_SAVED_WEEK_FIELD": "reset",  # invite-board saved marker
    "WEEK_35_RECRUITING_RESULTS_FIELD": "reset",
}


def test_every_recruiting_field_is_reset_for_the_new_season():
    block = _reset_block()
    for field in RECRUITING_FIELDS:
        assert field in block, f"{field} survives the season rollover"


def test_the_guards_and_results_are_reset_too():
    block = _reset_block()
    for literal in ('"recruiting_results": {}',
                    '"recruiting_lean_updates_applied": {}',
                    '"recruiting_performance_lean_applied": {}',
                    '"week_35_recruiting_ran": False'):
        assert literal in block


def test_season_stamped_markers_are_deliberately_not_reset():
    """These carry the season number, so a new season invalidates them by itself.

    Resetting them would be harmless but is unnecessary; asserting it here records the
    decision so a future reader does not "fix" a non-bug.
    """
    block = _reset_block()
    for field in ("RECRUITING_RESULTS_MODAL_SEEN_SEASON_FIELD",
                  "WEEK_35_REVEAL_SEEN_SEASON_FIELD"):
        assert field not in block
        assert field in TEXT   # ...but they do exist


def test_the_team_side_recruiting_state_is_reset():
    """FTD carries the invite board and the week-35 orders; both must clear."""
    i = TEXT.index('"Recruits": {str(i): None for i in range(1, 21)}')
    block = TEXT[i:i + 400]
    assert "RECRUITING_ORDERS_WEEK_35_FIELD" in block
    assert '"recruit_visit": None' in block


def test_the_recruit_pool_itself_is_regenerated():
    """Which is why carrying any per-recruit record forward is meaningless."""
    assert "franchise_recruits_data_collection.delete_many" in TEXT
    assert "load_unused_set_or_generate" in TEXT
