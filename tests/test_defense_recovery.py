"""Defensive mid-court recovery: stranded backcourt defenders sprint across
once the offense establishes frontcourt (`_recover_defense_targets`)."""

from BackEnd.engine.dynamic_hct import _recover_defense_targets

_POS = ("PG", "SG", "SF", "PF", "C")


def _frontcourt(x, is_away):
    return x <= 50 if is_away else x >= 50


def test_noop_before_frontcourt_established():
    targets = {p: {"x": 40, "y": 25} for p in _POS}
    before = {p: dict(targets[p]) for p in _POS}
    recovered = _recover_defense_targets(
        targets, dict(before), {p: {"x": 55, "y": 25} for p in _POS},
        {"x": 55, "y": 25}, False, frontcourt_established=False,
    )
    assert recovered == set()
    assert targets == before


def test_noop_without_off_coords():
    targets = {p: {"x": 40, "y": 25} for p in _POS}
    recovered = _recover_defense_targets(
        targets, dict(targets), None, {"x": 55, "y": 25}, False,
        frontcourt_established=True,
    )
    assert recovered == set()


def test_stranded_backcourt_defenders_recover_across_midcourt():
    # PG on-ball + PF/C zone are frontcourt (not stranded); SG/SF held deep.
    targets = {
        "PG": {"x": 55, "y": 25},
        "SG": {"x": 40, "y": 20},
        "SF": {"x": 38, "y": 30},
        "PF": {"x": 70, "y": 25},
        "C": {"x": 72, "y": 25},
    }
    def_coords = {p: dict(targets[p]) for p in _POS}
    off_coords = {
        "PG": {"x": 55, "y": 25},
        "SG": {"x": 58, "y": 15},
        "SF": {"x": 58, "y": 35},
        "PF": {"x": 62, "y": 22},
        "C": {"x": 62, "y": 28},
    }
    recovered = _recover_defense_targets(
        targets, def_coords, off_coords, {"x": 55, "y": 25}, False,
        frontcourt_established=True,
    )
    assert recovered == {"SG", "SF"}
    # Both stranded defenders are pulled to the frontcourt side of half court.
    assert _frontcourt(targets["SG"]["x"], False)
    assert _frontcourt(targets["SF"]["x"], False)
    # And onto distinct men (no double-team when men are available).
    assert targets["SG"] != targets["SF"]
    # Ball/zone defenders are untouched.
    assert targets["PG"] == {"x": 55, "y": 25}
    assert targets["PF"] == {"x": 70, "y": 25}


def test_trailing_backcourt_man_keeps_his_defender_home():
    # Only SG def is stranded; one offender (off C) genuinely trails in the
    # backcourt and is unguarded, so the stranded defender picks HIM up rather
    # than abandoning him for the frontcourt.
    targets = {
        "PG": {"x": 55, "y": 25},
        "SG": {"x": 40, "y": 20},
        "SF": {"x": 58, "y": 35},
        "PF": {"x": 58, "y": 15},
        "C": {"x": 62, "y": 28},
    }
    def_coords = {p: dict(targets[p]) for p in _POS}
    off_coords = {
        "PG": {"x": 55, "y": 25},   # guarded by PG def
        "SG": {"x": 58, "y": 35},   # guarded by SF def
        "SF": {"x": 58, "y": 15},   # guarded by PF def
        "PF": {"x": 62, "y": 28},   # guarded by C def
        "C": {"x": 42, "y": 22},    # trailing, unguarded, in backcourt
    }
    recovered = _recover_defense_targets(
        targets, def_coords, off_coords, {"x": 55, "y": 25}, False,
        frontcourt_established=True,
    )
    assert recovered == {"SG"}
    # Denies ball-side toward the trailing man → stays back near him, not sprinting
    # all the way across to a frontcourt help spot.
    assert targets["SG"]["x"] < 55


def test_away_offense_mirrors_line():
    # Away offense attacks toward x=0; frontcourt is x<=50, backcourt is x>50.
    targets = {
        "PG": {"x": 45, "y": 25},
        "SG": {"x": 60, "y": 20},   # stranded (backcourt for away)
        "SF": {"x": 62, "y": 30},   # stranded
        "PF": {"x": 30, "y": 25},
        "C": {"x": 28, "y": 25},
    }
    def_coords = {p: dict(targets[p]) for p in _POS}
    off_coords = {
        "PG": {"x": 45, "y": 25},
        "SG": {"x": 42, "y": 15},
        "SF": {"x": 42, "y": 35},
        "PF": {"x": 38, "y": 22},
        "C": {"x": 38, "y": 28},
    }
    recovered = _recover_defense_targets(
        targets, def_coords, off_coords, {"x": 45, "y": 25}, True,
        frontcourt_established=True,
    )
    assert recovered == {"SG", "SF"}
    assert _frontcourt(targets["SG"]["x"], True)
    assert _frontcourt(targets["SF"]["x"], True)
