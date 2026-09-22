"""The man weak-side help shade must ship in the state Jamie approved (2026-09-22).

``GOB_MAN_HELP_SHADE`` is **ON**: the man off-ball basket shade is scaled by how weak-side
the man is, on the same ramp the shipped zone help shade uses, so the strong side is
untouched and the far weak side doubles. ``GOB_MAN_HELP_SHADE=0`` is the rollback and
reproduces ``equiv_v3_reference_32db56c77_helpshade.json``.

This is a shipped-defaults guard. If someone flips it, they should have to edit this file
and say why. It also pins the things that make the change defensible:

  * the shade REUSES ``HELP_BASKET_SHADE`` and the zone sink's ramp rather than copying
    their values, so a later retune moves this too instead of leaving a stale duplicate;
  * **one ramp, not two** -- the zone shade and the man shade both read
    ``help_side_weakness``, so they cannot drift apart;
  * a central ball produces NO extra shade, which is the sink's own rule ("with the ball in
    the middle there is no weak side") and the reason the strong side is left alone;
  * deny is untouched -- it already sits 2.09 off the man and is in the passing lane 99.7%
    of the time, so it is the one posture that needs nothing;
  * no clamp.
"""

import math

import pytest

from BackEnd.utils import shared_defense as SD
from BackEnd.utils import zone_sink as ZS

# A man on the far weak side: the ball is up at y=44, he is down at y=8.
WEAK_MAN = {"x": 68.0, "y": 8.0}
# A man on the ball's own side, at the ball's y -- weakness is exactly 0 there.
STRONG_MAN = {"x": 68.0, "y": 44.0}
BALL = {"x": 68.0, "y": 44.0}
CENTRAL_BALL = {"x": 64.0, "y": 25.0}
BASE = {"x": 0.0, "y": 0.0}       # the aggression base; the help branch discards it


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so the helper returns its shipped default (ON since 2026-09-22)."""
    monkeypatch.delenv(SD.MAN_HELP_SHADE_FLAG, raising=False)


@pytest.fixture
def no_jitter(monkeypatch):
    """Pin the human jitter so a placement is a function of geometry alone."""
    monkeypatch.setattr(SD, "HELP_SAG_JITTER", 0.0)


def place(man, ball, posture="normal", away=False, spot="lower wing"):
    return SD._apply_defender_posture(dict(BASE), man, ball, False, spot, posture, away)


def test_shade_defaults_on(clean_env):
    assert SD.man_help_shade_enabled() is True, (
        "GOB_MAN_HELP_SHADE must default ON. The weak-side off-ball helper sagging toward "
        "the basket, scaled by how weak-side he is, is the shipped behaviour."
    )


def test_shade_kill_switch(clean_env, monkeypatch):
    """The rollback path to equiv_v3_reference_32db56c77_helpshade.json."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    assert SD.man_help_shade_enabled() is False


def test_flag_off_is_a_no_op_at_the_function(clean_env, monkeypatch):
    """OFF must return the constant itself, not a recomputed value that happens to match."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    assert SD._man_help_basket_shade(WEAK_MAN["y"], BALL["y"]) == SD.HELP_BASKET_SHADE
    assert SD._man_help_basket_shade(STRONG_MAN["y"], BALL["y"]) == SD.HELP_BASKET_SHADE


def test_off_and_on_agree_on_the_strong_side(clean_env, no_jitter, monkeypatch):
    """Weakness is 0 for a man on the ball's own side, so ON must not move him at all."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    off = place(STRONG_MAN, BALL, spot="upper wing")
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    on = place(STRONG_MAN, BALL, spot="upper wing")
    assert on == off


def test_weak_side_moves_toward_the_defended_rim(clean_env, no_jitter, monkeypatch):
    from BackEnd.constants import HOME_RIM_COORDS
    rim = (float(HOME_RIM_COORDS["x"]), float(HOME_RIM_COORDS["y"]))
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    off = place(WEAK_MAN, BALL)
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    on = place(WEAK_MAN, BALL)
    d_off = math.hypot(off["x"] - rim[0], off["y"] - rim[1])
    d_on = math.hypot(on["x"] - rim[0], on["y"] - rim[1])
    assert d_on < d_off, "the weak-side helper must end up NEARER the basket he defends"


def test_away_offense_uses_the_mirrored_rim(clean_env, no_jitter, monkeypatch):
    """Away offense attacks the low-x basket; the shade must follow it, not the home rim,
    or the weak-side helper sags to the wrong end of the floor."""
    from BackEnd.constants import AWAY_RIM_COORDS
    rim = (float(AWAY_RIM_COORDS["x"]), float(AWAY_RIM_COORDS["y"]))
    man = {"x": 32.0, "y": 8.0}
    ball = {"x": 32.0, "y": 44.0}
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    off = place(man, ball, away=True)
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    on = place(man, ball, away=True)
    assert math.hypot(on["x"] - rim[0], on["y"] - rim[1]) < \
        math.hypot(off["x"] - rim[0], off["y"] - rim[1])
    assert on["x"] < off["x"], "away offense defends the low-x rim"


def test_central_ball_gets_no_extra_shade(clean_env, monkeypatch):
    """The sink's rule: with the ball in the middle there is no weak side."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    assert SD._man_help_basket_shade(8.0, CENTRAL_BALL["y"]) == SD.HELP_BASKET_SHADE


def test_far_weak_side_doubles(clean_env, monkeypatch):
    """weakness 1.0 -> HELP_BASKET_SHADE * 2, the shape the counterfactual priced."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    # a full SIDE_SPAN apart, and far enough out that ball_centrality is 0
    shade = SD._man_help_basket_shade(2.0, 2.0 + ZS.SIDE_SPAN + 5.0)
    assert shade == pytest.approx(SD.HELP_BASKET_SHADE * 2.0)


def test_constant_is_reused_not_copied(clean_env, monkeypatch):
    """The magnitude must come from HELP_BASKET_SHADE itself, not a copy of 0.20."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    base = SD._man_help_basket_shade(WEAK_MAN["y"], BALL["y"])
    assert base > SD.HELP_BASKET_SHADE
    monkeypatch.setattr(SD, "HELP_BASKET_SHADE", SD.HELP_BASKET_SHADE * 2)
    assert SD._man_help_basket_shade(WEAK_MAN["y"], BALL["y"]) == pytest.approx(base * 2)


def test_ramp_is_the_sinks_own(clean_env, monkeypatch):
    """The weak/strong ramp must come from zone_sink.SIDE_SPAN, not a private copy:
    widening the span makes everyone look strong-side, so the extra shade shrinks."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    base = SD._man_help_basket_shade(WEAK_MAN["y"], BALL["y"])
    monkeypatch.setattr(ZS, "SIDE_SPAN", ZS.SIDE_SPAN * 4)
    assert SD._man_help_basket_shade(WEAK_MAN["y"], BALL["y"]) < base


def test_one_ramp_serves_both_shades(clean_env, monkeypatch):
    """The zone shade and the man shade must read the SAME help_side_weakness, so they
    cannot drift apart. Neutralise the ramp and BOTH must fall back to no extra shade."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    monkeypatch.setattr(SD, "help_side_weakness", lambda man_y, ball_y: 0.0)
    assert SD._man_help_basket_shade(WEAK_MAN["y"], BALL["y"]) == SD.HELP_BASKET_SHADE
    coords = {"x": 40.0, "y": 8.0}
    assert SD._apply_zone_help_shade(dict(coords), {"x": 40.0, "y": 8.0},
                                     {"x": 40.0, "y": 45.0}, False) == coords


def test_deny_is_untouched(clean_env, no_jitter, monkeypatch):
    """Deny already sits POSTURE_DENY_DISTANCE off the man and in the passing lane 99.7%
    of the time. The shade must not reach it."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    off = place(WEAK_MAN, BALL, posture="tight")
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    assert place(WEAK_MAN, BALL, posture="tight") == off


def test_inside_man_lock_is_untouched(clean_env, no_jitter, monkeypatch):
    """Inside men get base post-D; posture, and so the shade, is ignored for them."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    assert place(WEAK_MAN, BALL, spot="lower lowPost") == BASE


def test_on_ball_cushion_is_untouched(clean_env, no_jitter, monkeypatch):
    """The shade is an OFF-ball term. The ball handler's defender must not move."""
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    off = SD._apply_defender_posture(dict(BASE), WEAK_MAN, BALL, True, "lower wing",
                                     "normal", False)
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    on = SD._apply_defender_posture(dict(BASE), WEAK_MAN, BALL, True, "lower wing",
                                    "normal", False)
    assert on == off


def test_no_clamp_is_applied(clean_env):
    """Deliberate: the shade takes no ring and must not acquire one. The helpers it moves
    furthest are the ones with nothing to guard on their own side."""
    import inspect
    assert list(inspect.signature(SD._man_help_basket_shade).parameters) == ["man_y", "ball_y"]


def test_constants_unchanged():
    """Nothing was retuned to build this. The shape changed, not the magnitude."""
    assert SD.HELP_BASKET_SHADE == 0.20
    assert SD.HELP_SAG == {"normal": 0.30, "loose": 0.55}
    assert SD.HELP_ANCHOR_FLOOR == 0.30
    assert SD.HELP_SAG_JITTER == 0.10
    assert SD.POSTURE_DENY_DISTANCE == 2.0
    assert ZS.SIDE_SPAN == 30.0
