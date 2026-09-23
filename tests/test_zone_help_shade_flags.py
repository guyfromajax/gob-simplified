"""The zone weak-side help shade must ship in the state Jamie approved (2026-09-22).

``GOB_ZONE_HELP_SHADE`` is ON: a zone defender WITH a man in his area sags toward the
rim he is defending, scaled by how weak-side he is.

This is a shipped-defaults guard. If someone flips it, they should have to edit this
file and say why. It also pins the things that make the change defensible:

  * the shade REUSES existing constants rather than copying their values, so a later
    retune of ``HELP_BASKET_SHADE`` or the sink's ramp moves this too instead of
    silently leaving a stale duplicate behind;
  * a central ball produces NO shade, which is the sink's own rule ("with the ball in
    the middle there is no weak side") and the reason the strong side is left alone;
  * no clamp — the defender is deliberately NOT confined to his polygon, because the
    ones already outside it are the ones already nearest the rim.
"""

import math

import pytest

from BackEnd.utils import shared_defense as SD
from BackEnd.utils import zone_sink as ZS


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so the helper returns its shipped default."""
    monkeypatch.delenv(SD.ZONE_HELP_SHADE_FLAG, raising=False)


def test_shade_defaults_on(clean_env):
    assert SD.zone_help_shade_enabled() is True, (
        "GOB_ZONE_HELP_SHADE must default ON. The weak-side zone defender sagging "
        "toward the basket is the shipped behaviour."
    )


def test_shade_kill_switch(clean_env, monkeypatch):
    """The rollback path to equiv_v3_reference_5ea94694f_sinkescape.json."""
    monkeypatch.setenv(SD.ZONE_HELP_SHADE_FLAG, "0")
    assert SD.zone_help_shade_enabled() is False


def test_constants_are_reused_not_copied(clean_env, monkeypatch):
    """The magnitude must come from HELP_BASKET_SHADE itself, not a copy of 0.20.

    Doubling the constant must double the shade; if someone inlines the value this
    test fails rather than leaving a duplicate to drift.
    """
    man = {"x": 40.0, "y": 10.0}
    ball = {"x": 40.0, "y": 45.0}          # far weak side
    coords = {"x": 40.0, "y": 10.0}

    base = SD._apply_zone_help_shade(dict(coords), man, ball, False)
    moved_base = math.hypot(base["x"]-coords["x"], base["y"]-coords["y"])
    assert moved_base > 0.0

    monkeypatch.setattr(SD, "HELP_BASKET_SHADE", SD.HELP_BASKET_SHADE * 2)
    doubled = SD._apply_zone_help_shade(dict(coords), man, ball, False)
    moved_doubled = math.hypot(doubled["x"]-coords["x"], doubled["y"]-coords["y"])
    assert moved_doubled == pytest.approx(moved_base * 2, rel=1e-6)


def test_ramp_is_the_sinks_own(clean_env, monkeypatch):
    """The weak/strong ramp must come from zone_sink.SIDE_SPAN, not a private copy."""
    man = {"x": 40.0, "y": 10.0}
    ball = {"x": 40.0, "y": 40.0}
    coords = {"x": 40.0, "y": 10.0}
    base = SD._apply_zone_help_shade(dict(coords), man, ball, False)
    monkeypatch.setattr(ZS, "SIDE_SPAN", ZS.SIDE_SPAN * 4)   # everyone looks strong-side
    widened = SD._apply_zone_help_shade(dict(coords), man, ball, False)
    d_base = math.hypot(base["x"]-coords["x"], base["y"]-coords["y"])
    d_wide = math.hypot(widened["x"]-coords["x"], widened["y"]-coords["y"])
    assert d_wide < d_base


def test_central_ball_gets_no_shade(clean_env):
    """The sink's rule: with the ball in the middle there is no weak side."""
    man = {"x": 40.0, "y": 10.0}
    ball = {"x": 50.0, "y": 25.0}          # dead centre, inside CENTRALITY_PLATEAU
    coords = {"x": 40.0, "y": 10.0}
    out = SD._apply_zone_help_shade(dict(coords), man, ball, False)
    assert out["x"] == pytest.approx(coords["x"])
    assert out["y"] == pytest.approx(coords["y"])


def test_weak_side_moves_toward_the_defended_rim(clean_env):
    from BackEnd.constants import HOME_RIM_COORDS
    man = {"x": 40.0, "y": 8.0}
    ball = {"x": 40.0, "y": 45.0}
    coords = {"x": 40.0, "y": 8.0}
    out = SD._apply_zone_help_shade(dict(coords), man, ball, False)
    rim = (float(HOME_RIM_COORDS["x"]), float(HOME_RIM_COORDS["y"]))
    before = math.hypot(coords["x"]-rim[0], coords["y"]-rim[1])
    after = math.hypot(out["x"]-rim[0], out["y"]-rim[1])
    assert after < before


def test_away_offense_uses_the_mirrored_rim(clean_env):
    """Away offense attacks the mirrored basket; the shade must follow it, not the
    home rim, or the defender sags to the wrong end."""
    man = {"x": 60.0, "y": 8.0}
    ball = {"x": 60.0, "y": 45.0}
    coords = {"x": 60.0, "y": 8.0}
    out = SD._apply_zone_help_shade(dict(coords), man, ball, True)
    assert out["x"] < coords["x"], "away offense defends the low-x rim"


def test_flag_off_is_a_no_op(clean_env, monkeypatch):
    monkeypatch.setenv(SD.ZONE_HELP_SHADE_FLAG, "0")
    coords = {"x": 40.0, "y": 8.0}
    out = SD._apply_zone_help_shade(dict(coords), {"x": 40.0, "y": 8.0},
                                    {"x": 40.0, "y": 45.0}, False)
    assert out == coords


def test_no_clamp_is_applied(clean_env):
    """Deliberate: he is NOT confined to his zone polygon. The shade takes no ring and
    must not acquire one — the defenders already outside their polygon are the ones
    already nearest the rim, so clamping would undo the fix."""
    import inspect
    sig = inspect.signature(SD._apply_zone_help_shade)
    assert list(sig.parameters) == ["coords", "man_coords", "ball_coords", "is_away_offense"]
