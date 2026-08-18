"""Walk-ons must not surface before the next season's Walk-On Welcome modal.

Week 35 records walk-ons in `week_35_recruiting_results.signed_players` as roster
backfill. They are not a signing outcome, and their first reveal is the modal on the
next season's opening FCC landing — so every pre-rollover surface has to exclude them.
"""
import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[1] / "BackEnd" / "api" / "franchise_routes.py"
TEXT = SRC.read_text()


def _block(anchor: str, size: int = 900) -> str:
    i = TEXT.index(anchor)
    return TEXT[i:i + size]


def test_fcc_recruits_tab_excludes_walk_ons():
    """`week_35_user_recruits` feeds the FCC Recruits tab; it listed walk-ons at week 35."""
    block = _block('response["week_35_user_recruits"] = [')
    assert 'not player.get("walk_on")' in block


def test_the_signing_news_story_excludes_walk_ons():
    block = _block("week_35_results.get(\"signed_players\") or []")
    assert 'walk_on' in block


def _enclosing_def(offset: int) -> str:
    defs = list(re.finditer(r"^(?:async )?def (\w+)", TEXT[:offset], re.M))
    return defs[-1].group(1) if defs else "?"


# Every function that reads week_35 signed_players, and what it does about walk-ons.
# Enumerated rather than pattern-matched: a regex cannot tell a reader that filters in
# place from one that hands the list to a callee that filters, nor from the one reader
# that is SUPPOSED to see them. A new reader fails this test and forces the decision.
SIGNED_PLAYERS_READERS = {
    "_build_recruiting_results_modal_payload": "filters in place",
    "command_center_data": "filters in place",
    "run_week_35_recruiting": "callee _build_season_recruiting_results_story filters",
    "finish_season": "INTENDED — this is where walk-ons become roster players",
}


def test_every_signed_players_reader_is_accounted_for():
    found = {
        _enclosing_def(m.start())
        for m in re.finditer(r"signed_players[\"']\s*\)\s*or\s*\[\]", TEXT)
    }
    assert found == set(SIGNED_PLAYERS_READERS), (
        f"signed_players readers changed: {found ^ set(SIGNED_PLAYERS_READERS)}"
    )


def test_the_two_display_readers_filter_in_place():
    for fn in ("_build_recruiting_results_modal_payload", "command_center_data"):
        i = TEXT.index(f"def {fn}")
        j = TEXT.index('signed_players") or []', i)
        assert 'not player.get("walk_on")' in TEXT[j:j + 400], f"{fn} does not filter"


def test_the_welcome_modal_is_still_the_reveal():
    """The one surface that SHOULD show them keeps doing so."""
    block = _block("def _build_walk_on_welcome_modal_payload")
    assert "PENDING_WALK_ON_WELCOME_FIELD" in block
    assert "walk_ons" in block


def test_walk_ons_are_still_recorded_at_week_35():
    """Filtering is a display rule — the roster backfill itself must not change."""
    assert "walk_on=True," in TEXT
    assert "generate_walk_on_profile()" in TEXT


def test_the_recruiting_results_ranking_excludes_walk_ons():
    """Backfill must not score: it inflated the teams that recruited worst."""
    block = _block("def _build_season_recruiting_results_story", 1200)
    assert 'not player.get("walk_on")' in block


def test_the_shared_scorer_is_left_general():
    """The filter belongs at the caller — team_points_from_signings has its own tests."""
    scorer = (SRC.parents[2] / "BackEnd" / "utils" / "recruiting_report_news.py").read_text()
    i = scorer.index("def team_points_from_signings")
    assert "walk_on" not in scorer[i:i + 600]
