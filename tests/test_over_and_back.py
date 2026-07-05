"""Universal over-and-back pass geometry and passer awareness."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from BackEnd.engine.over_and_back import (
    CROSS_HALF_URGENCY_X_MAX,
    CROSS_HALF_URGENCY_X_MIN,
    HALF_COURT_X,
    cross_half_urgency_target,
    gate_offense_backcourt_reentry,
    is_over_and_back_pass,
    passer_commits_over_and_back_pass,
    passer_over_and_back_threshold,
    should_hold_instead_of_backcourt_pass,
    update_frontcourt_established,
)

_POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(ps=50, ch=50):
    return SimpleNamespace(attributes={"PS": ps, "CH": ch})


def test_threshold_formula():
    assert passer_over_and_back_threshold(_player(80, 60)) == 76.0


def test_smart_passer_holds_high_roll():
    rng = MagicMock()
    rng.randint.return_value = 77
    assert passer_commits_over_and_back_pass(_player(80, 60), rng=rng) is True
    rng.randint.return_value = 76
    assert passer_commits_over_and_back_pass(_player(80, 60), rng=rng) is False
    rng.randint.return_value = 50
    assert passer_commits_over_and_back_pass(_player(80, 60), rng=rng) is False


def test_weak_passer_commits_on_low_roll():
    rng = MagicMock()
    rng.randint.return_value = 50
    assert passer_commits_over_and_back_pass(_player(40, 40), rng=rng) is True


def test_is_over_and_back_requires_frontcourt_established():
    assert not is_over_and_back_pass(False, {"x": 45, "y": 25}, False)
    assert is_over_and_back_pass(True, {"x": 45, "y": 25}, False)


def test_frontcourt_established_on_pass_receipt_enables_over_and_back():
    """FC can be established by catch spot (away: x<=50), not only BH dribble."""
    fc = update_frontcourt_established(False, {"x": 75, "y": 25}, is_away_offense=True)
    assert not fc
    fc = update_frontcourt_established(fc, {"x": 48, "y": 25}, is_away_offense=True)
    assert fc
    assert is_over_and_back_pass(fc, {"x": 55, "y": 28}, is_away_offense=True)


def test_frontcourt_established_on_pass_receipt_home_offense():
    fc = update_frontcourt_established(False, {"x": 45, "y": 25}, is_away_offense=False)
    assert not fc
    fc = update_frontcourt_established(fc, {"x": 52, "y": 25}, is_away_offense=False)
    assert fc
    assert is_over_and_back_pass(fc, {"x": 45, "y": 25}, is_away_offense=False)


def test_grace_beat_always_holds_backcourt_pass():
    rng = MagicMock()
    rng.randint.return_value = 100  # would commit if not grace
    assert should_hold_instead_of_backcourt_pass(
        True,
        {"x": 45, "y": 25},
        False,
        _player(99, 99),
        grace_bh_pos="PG",
        current_bh_pos="PG",
        rng=rng,
    )


def test_after_grace_uses_passer_awareness():
    rng = MagicMock()
    rng.randint.return_value = 40
    assert should_hold_instead_of_backcourt_pass(
        True,
        {"x": 45, "y": 25},
        False,
        _player(40, 40),
        grace_bh_pos=None,
        current_bh_pos="PG",
        rng=rng,
    )
    rng.randint.return_value = 99
    assert not should_hold_instead_of_backcourt_pass(
        True,
        {"x": 45, "y": 25},
        False,
        _player(99, 99),
        grace_bh_pos=None,
        current_bh_pos="PG",
        rng=rng,
    )


def test_cross_half_urgency_target_is_frontcourt_side():
    rng = MagicMock()
    rng.randint.side_effect = [55, 0]
    target = cross_half_urgency_target(
        {"x": 40, "y": 25},
        is_away_offense=False,
        clamp_fn=lambda xy: {"x": int(xy["x"]), "y": int(xy["y"])},
        flip_fn=lambda xy: xy,
        rng=rng,
    )
    assert CROSS_HALF_URGENCY_X_MIN <= target["x"] <= CROSS_HALF_URGENCY_X_MAX


def test_gate_is_noop_before_frontcourt_established():
    off = {"PG": {"x": 40, "y": 25}, "SG": {"x": 60, "y": 25}}
    ratcheted = set()
    gate_offense_backcourt_reentry(off, ratcheted, ("PG", "SG"), False, False)
    assert off["SG"]["x"] == 60
    assert ratcheted == set()


def test_gate_ratchets_frontcourt_offenders_and_clamps_reentry():
    off = {
        "PG": {"x": 40, "y": 25},  # backcourt, not gated
        "SG": {"x": 60, "y": 25},  # frontcourt -> ratcheted
        "SF": {"x": 55, "y": 30},  # frontcourt -> ratcheted
        "PF": {"x": 45, "y": 25},  # backcourt, not gated
        "C": {"x": 52, "y": 25},   # frontcourt -> ratcheted
    }
    ratcheted = set()
    gate_offense_backcourt_reentry(off, ratcheted, _POSITIONS, False, True, skip={"PG"})
    assert ratcheted == {"SG", "SF", "C"}
    assert off["PG"]["x"] == 40 and off["PF"]["x"] == 45  # backcourt untouched

    # A ratcheted player drifting back over half is clamped to the line.
    off["SG"]["x"] = 44
    gate_offense_backcourt_reentry(off, ratcheted, _POSITIONS, False, True, skip={"PG"})
    assert off["SG"]["x"] == HALF_COURT_X

    # A player who never crossed is still free to move in the backcourt.
    off["PF"]["x"] = 42
    gate_offense_backcourt_reentry(off, ratcheted, _POSITIONS, False, True, skip={"PG"})
    assert off["PF"]["x"] == 42


def test_gate_skip_never_clamps_live_receiver():
    # A backcourt "receiver" (skipped) must not be clamped, so over-and-back on
    # a completed backward pass stays detectable at the true catch spot.
    off = {"PG": {"x": 60, "y": 25}, "SG": {"x": 45, "y": 25}}
    ratcheted = {"SG"}  # SG had previously crossed
    gate_offense_backcourt_reentry(
        off, ratcheted, ("PG", "SG"), False, True, skip={"SG"}
    )
    assert off["SG"]["x"] == 45


def test_gate_away_offense_mirrors_line():
    off = {"PG": {"x": 60, "y": 25}, "SG": {"x": 40, "y": 25}}  # away frontcourt is x<=50
    ratcheted = set()
    gate_offense_backcourt_reentry(off, ratcheted, ("PG", "SG"), True, True)
    assert ratcheted == {"SG"}
    off["SG"]["x"] = 56  # drifts back over half (away backcourt is x>50)
    gate_offense_backcourt_reentry(off, ratcheted, ("PG", "SG"), True, True)
    assert off["SG"]["x"] == HALF_COURT_X
