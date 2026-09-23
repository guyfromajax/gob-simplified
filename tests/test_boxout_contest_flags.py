"""The box-out contest must ship in the state Jamie approved (2026-09-23).

``GOB_BOXOUT_CONTEST`` is **ON**: when a defensive crasher has an offensive crasher within
``BOXOUT_PAIR_RADIUS``, the two contest the box-out and the loser's crash destination is
pushed back away from the rim. ``GOB_BOXOUT_CONTEST=0`` is the rollback and reproduces
``equiv_v3_reference_f2a060488_manhelpshade.json``.

This is a shipped-defaults guard; the model's own behaviour is covered by
``tests/test_boxout_contest.py``. If someone flips it, they should have to edit this file
and say why. It also pins the decisions that made the flip defensible:

  * **two-directional** -- the defender is not privileged. Either side can lose and be
    pushed back, and at n=120 the defender won 48.3% of 8,792 contests. Making it
    defender-only would be a different model, and a silent one;
  * the **d6** is intact -- ``rand(1, 6)`` is what keeps an attribute edge a tilt rather
    than a certainty;
  * ``BOXOUT_SCORE_WEIGHTS`` and ``BOXOUT_PUSHBACK_FRACTION`` are **reused, not copied**,
    so a later retune moves the behaviour instead of leaving a stale duplicate behind;
  * the constants are DERIVED, not chosen: ``BOXOUT_PAIR_RADIUS`` 8.0 is the pooled median
    shot-moment distance from a defensive crasher to his nearest offensive crasher, and
    ``BOXOUT_PUSHBACK_FRACTION`` 0.5 is half the loser's remaining travel, which is on
    average the size of the gap between the pair's two destinations.
"""

import inspect

import pytest

from BackEnd.utils import boxout_contest as BO


class _P:
    def __init__(self, pid, x, y, rb=50, st=50, iq=50, ch=50):
        self.player_id = pid
        self.coords = {"x": float(x), "y": float(y)}
        self.attributes = {"RB": rb, "ST": st, "IQ": iq, "CH": ch}


class _Dice:
    """A scripted d6, so a contest's winner is a fact about the model, not a draw."""

    def __init__(self, *rolls):
        self.rolls = list(rolls)

    def randint(self, a, b):
        assert (a, b) == (1, 6), "the box-out must roll a d6, not %r" % ((a, b),)
        return self.rolls.pop(0)


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so ``enabled()`` returns its shipped default (ON since 2026-09-23)."""
    monkeypatch.delenv("GOB_BOXOUT_CONTEST", raising=False)


def test_contest_defaults_on(clean_env):
    assert BO.enabled() is True, (
        "GOB_BOXOUT_CONTEST must default ON. Paired crashers contesting the box-out, with "
        "the loser pushed back off the rim, is the shipped behaviour."
    )


def test_contest_kill_switch(clean_env, monkeypatch):
    """The rollback path to equiv_v3_reference_f2a060488_manhelpshade.json."""
    monkeypatch.setenv("GOB_BOXOUT_CONTEST", "0")
    assert BO.enabled() is False


def test_it_is_two_directional_the_defender_can_lose(clean_env):
    """Jamie's decision: KEEP IT TWO-DIRECTIONAL. The defender is not privileged.

    Same two players, same pairing - only the dice differ, and the loser swaps sides. If
    someone makes this defender-only, the second half of this test fails.
    """
    d = _P("D", 80, 25)
    o = _P("O", 84, 25)

    off_loses = BO.resolve_boxout(d, o, rng=_Dice(6, 1))
    assert off_loses["defender_wins"] is True
    assert off_loses["winner"] is d and off_loses["loser"] is o

    def_loses = BO.resolve_boxout(d, o, rng=_Dice(1, 6))
    assert def_loses["defender_wins"] is False, (
        "the DEFENDER must be able to lose the box-out and be pushed back; this contest "
        "is two-directional, not a defender-only bonus"
    )
    assert def_loses["winner"] is o and def_loses["loser"] is d


def test_the_d6_is_intact(clean_env):
    """`_Dice` asserts the (1, 6) bounds, and the score must scale with the roll."""
    p = _P("A", 80, 25, rb=100, st=100, iq=100, ch=100)
    one = BO.boxout_score(p, rng=_Dice(1))
    six = BO.boxout_score(p, rng=_Dice(6))
    assert one == pytest.approx(100.0)
    assert six == pytest.approx(600.0)
    assert "randint(1, 6)" in inspect.getsource(BO.boxout_score)


def test_weights_are_reused_not_copied(clean_env, monkeypatch):
    """The composite must come from BOXOUT_SCORE_WEIGHTS itself, not an inlined 0.4/0.1."""
    p = _P("A", 80, 25, rb=100, st=0, iq=0, ch=0)
    assert BO.boxout_score(p, rng=_Dice(1)) == pytest.approx(40.0)
    monkeypatch.setattr(BO, "BOXOUT_SCORE_WEIGHTS", {"RB": 0.8, "ST": 0.2, "IQ": 0.0, "CH": 0.0})
    assert BO.boxout_score(p, rng=_Dice(1)) == pytest.approx(80.0)


# ``find_boxout_pairs`` and ``push_back`` take their constant as a DEFAULT ARGUMENT, which
# Python binds once at import. So editing the constant in source does change the behaviour
# (that is the tuning surface), but monkeypatching the module attribute at runtime does not
# reach it. These tests therefore pin the binding itself - the default IS the named
# constant, so no literal can be inlined - and exercise the magnitude through the parameter.


def test_pushback_fraction_is_reused_not_copied(clean_env):
    """The default must BE BOXOUT_PUSHBACK_FRACTION, and the magnitude must scale with it."""
    default = inspect.signature(BO.push_back).parameters["fraction"].default
    assert default is BO.BOXOUT_PUSHBACK_FRACTION, (
        "push_back's `fraction` default must be the named constant, not an inlined 0.5"
    )
    origin = (70.0, 25.0)
    dest = {"x": 80.0, "y": 25.0}          # 10 units of remaining travel, straight at the rim
    rim_x = 91.0
    a = BO.push_back(dict(dest), origin, rim_x)
    assert a["x"] == pytest.approx(80.0 - 5.0)   # 0.5 x 10, away from the rim
    b = BO.push_back(dict(dest), origin, rim_x, fraction=BO.BOXOUT_PUSHBACK_FRACTION * 2)
    assert (dest["x"] - b["x"]) == pytest.approx(2 * (dest["x"] - a["x"]))


def test_pair_radius_is_reused_not_copied(clean_env):
    """The default must BE BOXOUT_PAIR_RADIUS, and widening it must pair men out of range."""
    default = inspect.signature(BO.find_boxout_pairs).parameters["radius"].default
    assert default is BO.BOXOUT_PAIR_RADIUS, (
        "find_boxout_pairs's `radius` default must be the named constant, not an inlined 8.0"
    )
    d = [_P("D", 70, 25)]
    o = [_P("O", 82, 25)]                  # 12 apart: outside the shipped 8.0
    assert BO.find_boxout_pairs(d, o) == []
    assert len(BO.find_boxout_pairs(d, o, radius=20.0)) == 1


def test_constants_unchanged():
    """Nothing was retuned to ship this. The flip moved a default, not a number."""
    assert BO.BOXOUT_SCORE_WEIGHTS == {"RB": 0.4, "ST": 0.4, "IQ": 0.1, "CH": 0.1}
    assert sum(BO.BOXOUT_SCORE_WEIGHTS.values()) == pytest.approx(1.0)
    assert BO.BOXOUT_PUSHBACK_FRACTION == 0.5
    assert BO.BOXOUT_PAIR_RADIUS == 8.0


def test_a_tie_still_goes_to_the_defender(clean_env):
    """The one structural edge this model asserts, kept explicit rather than buried."""
    d = _P("D", 80, 25)
    o = _P("O", 84, 25)
    tie = BO.resolve_boxout(d, o, rng=_Dice(3, 3))
    assert tie["def_score"] == tie["off_score"]
    assert tie["defender_wins"] is True
