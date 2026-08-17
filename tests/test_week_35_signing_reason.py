"""The one-line "why" on the results screen.

Hard rule: the reason is assembled ONLY from numbers the resolution recorded. It must
never re-run _week_35_team_score — a second implementation of the scoring rule is exactly
how the client drifted from the engine (slot 3 is x2, not x1).

These tests also pin WEEK_35_LEAN_MULTIPLIERS as the single definition, so the scorer and
the client can't disagree again.
"""

import inspect

import pytest

from BackEnd.api import franchise_routes as fr


US = "user-team"
RIVAL = "rival-team"
THIRD = "third-team"


def resolution(**over):
    base = {
        "field_size": 2,
        "points_by_team": {US: 8, RIVAL: 12},
        "scores_by_team": {US: 45, RIVAL: 65},
        "winner_team_id": RIVAL,
        "winner_score": 65,
        "winner_points": 12,
        "lean_multipliers": {US: 5, RIVAL: 3},
        "lean_at_resolution": {"1": US, "2": RIVAL, "3": None},
        "pt_offer_count": 1,
    }
    base.update(over)
    return base


def reason(res, signed_with_user, winner_name="Fairview"):
    return fr.week_35_signing_reason(res, US, winner_name, signed_with_user)


# ---------------------------------------------------------------------------
# Single definition of the multiplier
# ---------------------------------------------------------------------------

def test_multiplier_map_is_the_single_source():
    assert fr.WEEK_35_LEAN_MULTIPLIERS == {"1": 5, "2": 3, "3": 2}


def test_scorer_uses_the_shared_multiplier_helper():
    """The scoring function must not carry its own inline 5/3/2 ladder."""
    src = inspect.getsource(fr._week_35_team_score)
    assert "_week_35_lean_multiplier" in src
    assert "multiplier = 5" not in src


@pytest.mark.parametrize("slot,expected", [("1", 5), ("2", 3), ("3", 2)])
def test_slot_multipliers_including_slot_three(slot, expected):
    """Slot 3 is x2. An earlier client table defaulted it to x1 — that was the drift."""
    assert fr._week_35_lean_multiplier({slot: US}, US) == expected


def test_no_lean_is_one():
    assert fr._week_35_lean_multiplier({"1": RIVAL}, US) == 1
    assert fr._week_35_lean_multiplier(None, US) == 1


def test_scorer_scores_slot_three_at_double():
    """End-to-end on the real scorer, not the helper."""
    entry = {"points": 9, "playing_time": False}
    assert fr._week_35_team_score(US, entry, {"3": US}, 0, 0) == (1 + 9) * 2
    assert fr._week_35_team_score(US, entry, {"1": US}, 0, 0) == (1 + 9) * 5


# ---------------------------------------------------------------------------
# The reason itself
# ---------------------------------------------------------------------------

def test_won_with_a_thin_field_names_the_standing_and_the_field():
    r = reason(resolution(field_size=2, winner_team_id=US), True)
    assert r == "#1 lean x5 · only 2 programs funding"


def test_won_uncontested():
    r = reason(resolution(field_size=1, winner_team_id=US), True)
    assert r == "Uncontested — nobody else boarded him"


def test_lost_reports_the_field_and_your_points():
    r = reason(resolution(field_size=6, points_by_team={US: 5, RIVAL: 20}), False)
    assert r == "6 programs funding · 5 points didn't carry"


def test_lost_with_one_point_is_singular():
    r = reason(resolution(field_size=3, points_by_team={US: 1}), False)
    assert r == "3 programs funding · 1 point didn't carry"


def test_boarded_with_zero_points_says_so():
    r = reason(
        resolution(field_size=2, points_by_team={RIVAL: 9}, scores_by_team={US: 5, RIVAL: 30}),
        False, winner_name="Fairview",
    )
    assert r == "You boarded him with 0 points · Fairview funded him"


def test_never_boarded_reports_the_field_only():
    r = reason(resolution(field_size=4, scores_by_team={RIVAL: 30}, points_by_team={RIVAL: 9}), False)
    assert r == "You never boarded him · 4 programs did"


def test_never_boarded_with_no_field():
    r = reason(resolution(field_size=0, scores_by_team={}, points_by_team={}), False)
    assert r == "You never boarded him"


@pytest.mark.parametrize("mult,phrase", [(5, "#1 lean x5"), (3, "#2 lean x3"), (2, "#3 lean x2"), (1, "no lean x1")])
def test_won_phrase_covers_every_multiplier_including_slot_three(mult, phrase):
    r = reason(resolution(field_size=3, winner_team_id=US, lean_multipliers={US: mult}), True)
    assert r.startswith(phrase)


def test_missing_resolution_returns_empty_rather_than_guessing():
    """Pre-existing results have no resolution block; the UI shows a dash, not a lie."""
    assert fr.week_35_signing_reason(None, US, "Fairview", False) == ""
    assert fr.week_35_signing_reason({}, US, "Fairview", True) == ""


def test_reason_contains_no_percentage():
    for signed in (True, False):
        for res in (resolution(), resolution(field_size=1, winner_team_id=US), resolution(field_size=9)):
            assert "%" not in reason(res, signed)


def test_reason_never_calls_the_scorer():
    """Structural guard on the rule: no re-derivation on the read side.

    Checks the function BODY only — the docstring deliberately names the scorer in order
    to explain why it must not be called.
    """
    import ast, textwrap
    fn = ast.parse(textwrap.dedent(inspect.getsource(fr.week_35_signing_reason))).body[0]
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    code = "\n".join(ast.unparse(node) for node in body)
    assert "_week_35_team_score" not in code
    assert "* multiplier" not in code
    # And it reads the resolution dict rather than the recruit/lean documents.
    assert "points_by_team" in code and "lean_multipliers" in code
