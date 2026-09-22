"""The zone sink escape must ship in the state Jamie approved (2026-09-22).

``GOB_ZONE_SINK_ESCAPE`` is ON: an empty-area zone defender may leave his own polygon,
but only to the extent the movement takes him CLOSER TO THE RIM. Movement that is not
rim-ward is still clamped into his zone.

This is a shipped-defaults guard. If someone flips it, they should have to edit this
file and say why. It also pins the two guardrails, because both were DERIVED from
measured geometry and a silent edit would quietly change what "outside his zone" means:

  * ``RIM_FLOOR`` = the rim -> ``basketSpot`` distance, so a defender never stands
    closer to the basket than a man standing at the basket;
  * ``MIN_SEPARATION`` = the 5th percentile of the nearest-other-defender distance
    measured on zone turns, so the escape cannot create an overlap tighter than the
    game already tolerates.
"""

import math

import pytest

from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS
from BackEnd.utils import zone_sink as ZS


@pytest.fixture
def clean_env(monkeypatch):
    """No flag set - so ``escape_enabled()`` returns its shipped default."""
    monkeypatch.delenv(ZS.FLAG_ESCAPE, raising=False)


def test_escape_defaults_on(clean_env):
    assert ZS.escape_enabled() is True, (
        "GOB_ZONE_SINK_ESCAPE must default ON. An empty-area zone defender sinking out "
        "of his zone toward the rim is the shipped behaviour."
    )


def test_escape_kill_switch(clean_env, monkeypatch):
    """The rollback path to equiv_v3_reference_5cc98ee3e_freeze.json."""
    monkeypatch.setenv(ZS.FLAG_ESCAPE, "0")
    assert ZS.escape_enabled() is False


def test_rim_floor_is_the_basket_spot_distance():
    """RIM_FLOOR is not a chosen number: it is the rim -> basketSpot distance."""
    spot = HCO_STRING_SPOTS["basketSpot"]
    derived = math.hypot(spot["x"] - HOME_RIM_COORDS["x"], spot["y"] - HOME_RIM_COORDS["y"])
    assert ZS.RIM_FLOOR == pytest.approx(derived), (
        "RIM_FLOOR must stay equal to the rim->basketSpot distance (%.2f). If the court "
        "geometry moved, re-derive it rather than pinning the old number." % derived
    )


def test_min_separation_unchanged():
    assert ZS.MIN_SEPARATION == 2.0, (
        "MIN_SEPARATION is the measured 5th percentile of the nearest-other-defender "
        "distance on zone turns. Changing it is a tuning decision, not a tidy-up."
    )


def test_reach_and_sink_weights_untouched():
    """The escape deliberately did NOT touch these. They are the next lever, and the
    report prices them: lifting reach_perimeter would move the perimeter defender a
    further 1.69 units toward the rim."""
    w = ZS.WEIGHT_PRESETS["shape"]
    assert ZS.DEFAULT_PRESET == "shape"
    assert w["reach_perimeter"] == 8.0
    assert w["reach_spanning"] == 7.0
    assert w["reach_interior"] == 5.0
    assert w["basket_weak"] == 0.75
    assert w["basket_strong"] == 0.15


def test_escape_only_keeps_rim_ward_movement(clean_env):
    """The rule itself: a clamped-back move is allowed out of the zone only when it
    ends CLOSER to the rim than the clamp would have left him."""
    anchor = (20.0, 25.0)
    rim = (91.0, 25.0)
    clamped = (30.0, 25.0)

    rim_ward = (40.0, 25.0)            # nearer the rim than the clamp -> allowed out
    assert ZS._rim_ward_escape(anchor, rim_ward, clamped, rim, ()) == rim_ward

    away_from_rim = (25.0, 25.0)       # further from the rim -> stays clamped
    assert ZS._rim_ward_escape(anchor, away_from_rim, clamped, rim, ()) == clamped


def test_escape_stops_at_the_rim_floor(clean_env):
    """A guardrail that binds is a clamp too: he stops at it, he does not pass it."""
    anchor = (20.0, 25.0)
    rim = (91.0, 25.0)
    clamped = (30.0, 25.0)
    through_the_rim = (95.0, 25.0)     # past the basket entirely
    out = ZS._rim_ward_escape(anchor, through_the_rim, clamped, rim, ())
    assert math.dist(out, rim) >= ZS.RIM_FLOOR - 1e-6


def test_escape_respects_minimum_separation(clean_env):
    """He may not sink onto a team-mate."""
    anchor = (20.0, 25.0)
    rim = (91.0, 25.0)
    clamped = (30.0, 25.0)
    target = (60.0, 25.0)
    other = [(60.0, 25.0)]             # a defender standing exactly on the target
    out = ZS._rim_ward_escape(anchor, target, clamped, rim, other)
    assert math.dist(out, other[0]) >= ZS.MIN_SEPARATION - 1e-6


def test_counters_exist_and_reset(clean_env):
    ZS.reset_escape_counters()
    before = ZS.escape_counters()
    assert before["escaped"] == 0 and before["rim_floor_bound"] == 0
    ZS._rim_ward_escape((20.0, 25.0), (40.0, 25.0), (30.0, 25.0), (91.0, 25.0), ())
    assert ZS.escape_counters()["escaped"] == 1
    ZS.reset_escape_counters()
    assert ZS.escape_counters()["escaped"] == 0
