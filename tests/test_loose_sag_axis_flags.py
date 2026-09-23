"""The loose sag axis ships behind ``GOB_MAN_LOOSE_SAG_AXIS``, **default ON** (2026-09-23).

`HELP_SAG` moves the off-ball helper a fraction of the way from his man toward a TARGET, and
that target is the ball — so "loose" means drifting ball-ward, away from the man *and* away
from the basket. This blends the target toward the defended rim by
``HELP_BASKET_PULL[posture]``, which is 0.25 at loose and **0.0 at normal**.

This is a shipped-defaults guard. It also pins the properties the build rests on:

  * **normal is byte-identical at any flag state and at any pull value** — the pull is 0.0
    there, which is also why the equiv-v3 reference (base man) cannot see this change;
  * ``HELP_BASKET_PULL`` is reused, not copied, so doubling it doubles the blend;
  * deny and the inside-man lock return before this branch and must stay untouched;
  * no clamp;
  * it is independent of ``GOB_MAN_HELP_SHADE`` — the shade is a separate second term.

Note on the kill switch: ``GOB_MAN_LOOSE_SAG_AXIS=0`` does NOT on its own restore the main
equiv-v3 reference, because that reference runs base man where the pull is 0.0 either way. What
it restores is ``equiv_v3_loose_baseline_ef00985ce.json``, the loose footing.

Because the default is now ON, every paired before/after test below sets the flag to "0"
explicitly for its "before" state. An unset flag is no longer the off state, and without that
they would silently compare ON against ON.
"""

import inspect
import math

import pytest

from BackEnd.utils import shared_defense as SD

WEAK_MAN = {"x": 68.0, "y": 8.0}
BALL = {"x": 68.0, "y": 44.0}
BASE = {"x": 0.0, "y": 0.0}


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so the helper returns its shipped default (ON since 2026-09-23)."""
    monkeypatch.delenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, raising=False)


@pytest.fixture
def no_jitter(monkeypatch):
    monkeypatch.setattr(SD, "HELP_SAG_JITTER", 0.0)


def place(man, ball, posture="loose", away=False, spot="lower wing"):
    return SD._apply_defender_posture(dict(BASE), man, ball, False, spot, posture, away)


def test_axis_defaults_on(clean_env):
    assert SD.loose_sag_axis_enabled() is True, (
        "GOB_MAN_LOOSE_SAG_AXIS must default ON. The loose helper sagging toward a target "
        "blended a quarter of the way to the rim is the shipped behaviour."
    )


def test_axis_kill_switch(clean_env, monkeypatch):
    """The rollback path to equiv_v3_loose_baseline_ef00985ce.json."""
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    assert SD.loose_sag_axis_enabled() is False
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    assert SD.loose_sag_axis_enabled() is True


def test_flag_off_targets_the_ball_exactly(clean_env, monkeypatch):
    """OFF must return the ball itself, not a recomputed value that happens to match."""
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    assert SD._help_sag_target((68.0, 44.0), (91.0, 25.0), "loose") == (68.0, 44.0)
    assert SD._help_sag_target((68.0, 44.0), (91.0, 25.0), "normal") == (68.0, 44.0)


def test_normal_is_byte_identical_with_the_flag_on(clean_env, no_jitter, monkeypatch):
    """The whole reason the equiv-v3 reference cannot see this change."""
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    off = place(WEAK_MAN, BALL, posture="normal")
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    assert place(WEAK_MAN, BALL, posture="normal") == off
    assert SD._help_sag_target((68.0, 44.0), (91.0, 25.0), "normal") == (68.0, 44.0)


def test_normal_is_unchanged_at_any_pull_value(clean_env, no_jitter, monkeypatch):
    """Not just at the shipped 0.25 - normal must be pinned at 0.0 whatever loose is set to."""
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    off = place(WEAK_MAN, BALL, posture="normal")
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    for loose_pull in (0.25, 0.5, 1.0):
        monkeypatch.setattr(SD, "HELP_BASKET_PULL", {"normal": 0.0, "loose": loose_pull})
        assert place(WEAK_MAN, BALL, posture="normal") == off


def test_loose_moves_toward_the_defended_rim(clean_env, no_jitter, monkeypatch):
    from BackEnd.constants import HOME_RIM_COORDS
    rim = (float(HOME_RIM_COORDS["x"]), float(HOME_RIM_COORDS["y"]))
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    off = place(WEAK_MAN, BALL)
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    on = place(WEAK_MAN, BALL)
    assert math.hypot(on["x"]-rim[0], on["y"]-rim[1]) < math.hypot(off["x"]-rim[0], off["y"]-rim[1])


def test_away_offense_uses_the_mirrored_rim(clean_env, no_jitter, monkeypatch):
    from BackEnd.constants import AWAY_RIM_COORDS
    rim = (float(AWAY_RIM_COORDS["x"]), float(AWAY_RIM_COORDS["y"]))
    man, ball = {"x": 32.0, "y": 8.0}, {"x": 32.0, "y": 44.0}
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    off = place(man, ball, away=True)
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    on = place(man, ball, away=True)
    assert math.hypot(on["x"]-rim[0], on["y"]-rim[1]) < math.hypot(off["x"]-rim[0], off["y"]-rim[1])
    assert on["x"] < off["x"], "away offense defends the low-x rim, so the blend moves toward -x"


def test_pull_is_reused_not_copied(clean_env, monkeypatch):
    """Doubling HELP_BASKET_PULL must double the blend away from the ball."""
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    ball, rim = (68.0, 44.0), (91.0, 25.0)
    base = SD._help_sag_target(ball, rim, "loose")
    d1 = math.hypot(base[0]-ball[0], base[1]-ball[1])
    assert d1 > 0
    monkeypatch.setattr(SD, "HELP_BASKET_PULL",
                        {"normal": 0.0, "loose": SD.HELP_BASKET_PULL["loose"] * 2})
    doubled = SD._help_sag_target(ball, rim, "loose")
    assert math.hypot(doubled[0]-ball[0], doubled[1]-ball[1]) == pytest.approx(d1 * 2)


def test_pull_1_targets_the_rim_exactly(clean_env, monkeypatch):
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    monkeypatch.setattr(SD, "HELP_BASKET_PULL", {"normal": 0.0, "loose": 1.0})
    assert SD._help_sag_target((68.0, 44.0), (91.0, 25.0), "loose") == pytest.approx((91.0, 25.0))


def test_deny_is_untouched(clean_env, no_jitter, monkeypatch):
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    off = place(WEAK_MAN, BALL, posture="tight")
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    assert place(WEAK_MAN, BALL, posture="tight") == off


def test_inside_man_lock_is_untouched(clean_env, no_jitter, monkeypatch):
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    assert place(WEAK_MAN, BALL, spot="lower lowPost") == BASE


def test_on_ball_cushion_is_untouched(clean_env, no_jitter, monkeypatch):
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    off = SD._apply_defender_posture(dict(BASE), WEAK_MAN, BALL, True, "lower wing", "loose", False)
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    on = SD._apply_defender_posture(dict(BASE), WEAK_MAN, BALL, True, "lower wing", "loose", False)
    assert on == off


def test_independent_of_the_help_shade(clean_env, no_jitter, monkeypatch):
    """Two separate terms. Killing the shade must not disable the axis, or vice versa."""
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "1")
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "0")
    shade_off_axis_on = place(WEAK_MAN, BALL)
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    shade_off_axis_off = place(WEAK_MAN, BALL)
    assert shade_off_axis_on != shade_off_axis_off, "the axis must still act with the shade off"
    monkeypatch.setenv(SD.MAN_HELP_SHADE_FLAG, "1")
    monkeypatch.setenv(SD.MAN_LOOSE_SAG_AXIS_FLAG, "0")
    assert SD._man_help_basket_shade(WEAK_MAN["y"], BALL["y"]) > SD.HELP_BASKET_SHADE, \
        "the shade must still act with the axis off"


def test_no_clamp_is_applied(clean_env):
    """The blend takes a ball, a rim and a posture - and must not acquire a ring."""
    assert list(inspect.signature(SD._help_sag_target).parameters) == ["ball_xy", "rim_xy", "posture"]


def test_constants_unchanged():
    """Nothing was retuned to build this."""
    assert SD.HELP_BASKET_PULL == {"normal": 0.0, "loose": 0.25}
    assert SD.HELP_SAG == {"normal": 0.30, "loose": 0.55}
    assert SD.HELP_ANCHOR_FLOOR == 0.30
    assert SD.HELP_SAG_JITTER == 0.10
    assert SD.HELP_BASKET_SHADE == 0.20
    assert SD.POSTURE_DENY_DISTANCE == 2.0
