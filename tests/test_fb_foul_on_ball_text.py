"""Fast-break foul announcements must follow foul_is_on_ball, not assume it.

`fb_terminal_announce` is the only live caller of `pick_defensive_foul_text`, and it
read `turn_result.get("foul_is_on_ball", True)`. The fast-break drive integrations build
their own turn_result and never went through `select_foul_player`, so the key was absent
on every fast-break foul and every one of them got on-ball copy.

`GOB_FB_FOUL_ON_BALL_TEXT` (default ON) stamps the key at the three integration sites.
"""
import random

import pytest

import BackEnd.engine.fb_terminal_announce as FTA
import BackEnd.engine.foul_announcement_language as FAL


class _P:
    def __init__(self, pid):
        self.player_id = pid


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setenv("GOB_FB_FOUL_ON_BALL_TEXT", "1")


ON_BALL_ONLY = {"Blocking Foul!", "Hand-Checking!"}
ROLE_ASSERTING = ON_BALL_ONLY | {"Illegal Post Defense!"}
NEUTRAL = {"Illegal Contact!", "Holding!", "Arm Bar!", "Pushing!"}


def _texts(turn_result, n=400):
    return {FTA.build_fb_terminal_announcement(
        dict(turn_result), is_away_offense=False, rng=random.Random(i))["text"]
        for i in range(n)}


# ── the rule ────────────────────────────────────────────────────────────────────────────

def test_the_stopper_is_the_on_ball_defender():
    stopper = _P("d1")
    assert FAL.fb_defensive_foul_is_on_ball(stopper, stopper) is True


def test_a_help_defender_is_off_ball():
    assert FAL.fb_defensive_foul_is_on_ball(_P("help"), _P("stopper")) is False


@pytest.mark.parametrize("fouler,stopper", [(None, _P("s")), (_P("f"), None), (None, None)])
def test_unknown_when_there_is_nothing_to_compare(fouler, stopper):
    assert FAL.fb_defensive_foul_is_on_ball(fouler, stopper) is None


# ── the stamp ───────────────────────────────────────────────────────────────────────────

def test_turn_result_carries_foul_is_on_ball_for_a_stopper_foul():
    stopper = _P("d1")
    tr = {}
    FAL.stamp_fb_foul_on_ball(tr, foul_team="DEFENSE", foul_player=stopper, stopper=stopper)
    assert tr["foul_is_on_ball"] is True


def test_turn_result_carries_false_for_a_help_foul():
    tr = {}
    FAL.stamp_fb_foul_on_ball(tr, foul_team="DEFENSE",
                              foul_player=_P("help"), stopper=_P("stopper"))
    assert tr["foul_is_on_ball"] is False


def test_unknown_is_stamped_as_none_and_the_key_is_still_present():
    tr = {}
    FAL.stamp_fb_foul_on_ball(tr, foul_team="DEFENSE", foul_player=_P("f"), stopper=None)
    assert "foul_is_on_ball" in tr and tr["foul_is_on_ball"] is None


def test_a_shooting_foul_is_on_ball_by_definition():
    tr = {}
    FAL.stamp_fb_foul_on_ball(tr, foul_team="DEFENSE", is_shooting_foul=True)
    assert tr["foul_is_on_ball"] is True


def test_kill_switch_leaves_the_key_absent(monkeypatch):
    monkeypatch.setenv("GOB_FB_FOUL_ON_BALL_TEXT", "0")
    tr = {}
    FAL.stamp_fb_foul_on_ball(tr, foul_team="DEFENSE",
                              foul_player=_P("help"), stopper=_P("stopper"))
    assert "foul_is_on_ball" not in tr


def test_flag_defaults_on(monkeypatch):
    monkeypatch.delenv("GOB_FB_FOUL_ON_BALL_TEXT", raising=False)
    assert FAL.fb_foul_on_ball_text_enabled() is True


# ── the text follows the stamp ──────────────────────────────────────────────────────────

BASE = {"result_type": "FOUL", "foul_team": "DEFENSE", "foul_player_id": "d1"}


def test_on_ball_copy_is_reachable_only_when_the_stamp_says_on_ball():
    assert _texts({**BASE, "foul_is_on_ball": True}) & ON_BALL_ONLY
    assert not (_texts({**BASE, "foul_is_on_ball": False}) & ON_BALL_ONLY)


def test_unknown_uses_neutral_copy_only():
    got = _texts({**BASE, "foul_is_on_ball": None, "location": "midLane"})
    assert got <= NEUTRAL
    assert not (got & ROLE_ASSERTING)


def test_unknown_is_not_treated_as_on_ball():
    """The whole point: a missing role must not silently become on-ball copy."""
    assert not (_texts({**BASE, "foul_is_on_ball": None}) & ON_BALL_ONLY)


def test_absent_key_still_falls_back_to_the_legacy_on_ball_default():
    """The kill switch leaves the key absent, and that path must not change."""
    assert _texts(BASE) & ON_BALL_ONLY


def test_off_ball_post_defense_needs_a_known_role():
    """`Illegal Post Defense!` asserts a role, so `unknown` must not reach it."""
    lane = {"location": "midLane"}
    assert "Illegal Post Defense!" in _texts({**BASE, **lane, "foul_is_on_ball": False})
    assert "Illegal Post Defense!" not in _texts({**BASE, **lane, "foul_is_on_ball": None})


def test_the_announcement_draw_count_is_unchanged_by_the_role():
    """One announcement_rng draw either way - this is why game results cannot move."""
    for state in (True, False, None):
        rng = random.Random(7)
        before = rng.getstate()
        FTA.build_fb_terminal_announcement(
            {**BASE, "foul_is_on_ball": state}, is_away_offense=False, rng=rng)
        after = rng.getstate()
        probe = random.Random(7)
        probe.setstate(before)
        probe.random()
        assert probe.getstate() == after, state


# ── the integration sites actually call the stamper ─────────────────────────────────────

@pytest.mark.parametrize("mod", [
    "BackEnd.engine.rim_runner_drive_integration",
    "BackEnd.engine.covert_release_drive_integration",
    "BackEnd.engine.after_steal_drive_integration",
])
def test_every_fb_drive_integration_stamps_the_role(mod):
    import importlib
    import inspect
    src = inspect.getsource(importlib.import_module(mod))
    assert "stamp_fb_foul_on_ball(" in src, mod
