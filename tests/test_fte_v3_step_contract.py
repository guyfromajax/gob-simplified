"""Executable contract for the FTE v3 tutorial step machine.

FTE v3 inserts two steps and MOVES one. Three things must hold or the funnel
breaks in ways that are silent at import time:

  1. `_TUTORIAL_STEP_ORDER` drives FORWARD-ONLY validation on the server. If an
     index is out of order a legitimate advance is rejected with a 400 and the
     user is stuck mid-funnel.
  2. No v2 step name may be RENAMED. `tutorial_state.step` is a live resume
     pointer on real user documents; renaming strands anyone parked on it.
  3. `TutorialState` must carry `opponent_pick` and `game_id`. init-game moved
     four steps earlier (to the opponent pick), so the game id can no longer be
     hand-carried in query params — a refresh would drop it and the next screen
     would init a SECOND game, orphaning the first.
"""
import pytest

from BackEnd.api.auth_routes import TutorialState, _TUTORIAL_STEP_ORDER

# The v2 names, which must survive verbatim.
V2_STEPS = ("persona_intro", "team_select", "username", "situation", "set_lineup", "in_game", "complete")

EXPECTED_ORDER = [
    "persona_intro",
    "team_select",
    "username",
    "opponent_pick",
    "game_plan",
    "set_lineup",
    "situation",   # tip-off, now AFTER lineup
    "in_game",
    "complete",
]


def test_v2_step_names_are_not_renamed():
    """Real users carry these values in tutorial_state.step."""
    for name in V2_STEPS:
        assert name in _TUTORIAL_STEP_ORDER, f"v2 step {name!r} was renamed or removed"


def test_v3_steps_exist():
    assert "opponent_pick" in _TUTORIAL_STEP_ORDER
    assert "game_plan" in _TUTORIAL_STEP_ORDER


def test_order_is_exact_and_contiguous():
    ordered = sorted(_TUTORIAL_STEP_ORDER, key=lambda k: _TUTORIAL_STEP_ORDER[k])
    assert ordered == EXPECTED_ORDER
    assert sorted(_TUTORIAL_STEP_ORDER.values()) == list(range(len(EXPECTED_ORDER))), \
        "indices must be contiguous — gaps/dupes break forward-only comparison"


def test_game_plan_precedes_lineup_which_precedes_tipoff():
    """The v3 reorder: strategy, then roster, then tip. Game Plan must come after
    opponent pick because init-game (and therefore the doc it writes to) happens
    at the opponent step."""
    o = _TUTORIAL_STEP_ORDER
    assert o["opponent_pick"] < o["game_plan"] < o["set_lineup"] < o["situation"] < o["in_game"]


def test_tipoff_moved_after_lineup():
    """v2 had situation BEFORE set_lineup. v3 inverts it; this is the regression guard."""
    assert _TUTORIAL_STEP_ORDER["situation"] > _TUTORIAL_STEP_ORDER["set_lineup"]


def test_complete_is_terminal():
    assert _TUTORIAL_STEP_ORDER["complete"] == max(_TUTORIAL_STEP_ORDER.values())


@pytest.mark.parametrize("field", ["opponent_pick", "game_id"])
def test_tutorial_state_carries_resume_fields(field):
    assert field in TutorialState.model_fields, \
        f"TutorialState.{field} is required for FTE v3 resume; without it an " \
        f"interrupted funnel orphans its game doc and inits a second one"


def test_tutorial_state_round_trips_resume_fields():
    t = TutorialState(step="game_plan", team_pick="Durham", opponent_pick="Xavien", game_id="abc123")
    d = t.model_dump()
    assert d["opponent_pick"] == "Xavien"
    assert d["game_id"] == "abc123"


def test_resume_fields_are_optional():
    """Users who predate FTE v3 have neither field; /me must still build the model."""
    t = TutorialState(step="persona_intro")
    assert t.opponent_pick is None and t.game_id is None
