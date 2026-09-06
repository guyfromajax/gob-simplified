"""Every HCO_STRING_SPOTS key must be classified, and the freelance pool must
never offer a spot behind the half-court line.

The table serves two masters — the half-court offensive vocabulary and the
global named-spot registry that inbound setup draws from. Motion freelance
iterated all of it, so a player running half-court offense could relocate onto
an inbound spot in the backcourt. Membership is now positive and exhaustive
rather than an opt-out list, because an opt-out list is exactly how six
backcourt spots accumulated here: a new entry leaks into the pool by default.

``test_every_spot_is_classified`` is the part that catches the next one.
"""
import math

import pytest

from BackEnd.constants import (
    HCO_STRING_SPOTS,
    HCO_OFFENSIVE_SPOTS,
    HCO_NON_OFFENSIVE_SPOTS,
)
from BackEnd.engine.attack_drive_clearance import _spot_display_coords
from BackEnd.engine.motion_freelance import (
    _predefined_spots_within,
    nearest_named_spot,
    FREELANCE_RELOCATE_RADIUS,
)
from BackEnd.engine.over_and_back import in_backcourt

# Removed 2026-09-06 as dead data: their only consumer was the
# FCP_SETUP_POSITIONS mapping, deleted when FCP moved to
# FCP_OFFENSE_SETUP_RANGES, leaving the freelance pool as the sole reader.
DELETED_FCP_ENTRIES = {
    "fcp_inbound_pg": {"x": 15, "y": 15},
    "fcp_inbound_sg": {"x": 11, "y": 36},
    "fcp_outlet_pf": {"x": 43, "y": 25},
}


def test_every_spot_is_classified():
    """A key in neither set fails here. This is the guard that catches the next one."""
    classified = set(HCO_OFFENSIVE_SPOTS) | set(HCO_NON_OFFENSIVE_SPOTS)
    unclassified = sorted(set(HCO_STRING_SPOTS) - classified)
    assert not unclassified, (
        "HCO_STRING_SPOTS entries in neither HCO_OFFENSIVE_SPOTS nor "
        f"HCO_NON_OFFENSIVE_SPOTS: {unclassified}. Add each to exactly one — "
        "if it is not an offensive relocate target, put it in the "
        "non-offensive map with a one-line reason."
    )


def test_no_spot_is_in_both_sets():
    both = sorted(set(HCO_OFFENSIVE_SPOTS) & set(HCO_NON_OFFENSIVE_SPOTS))
    assert not both, f"classified as both offensive and non-offensive: {both}"


def test_neither_set_has_stale_entries():
    """Renaming or deleting a spot must not leave a dangling classification."""
    stale_off = sorted(set(HCO_OFFENSIVE_SPOTS) - set(HCO_STRING_SPOTS))
    stale_non = sorted(set(HCO_NON_OFFENSIVE_SPOTS) - set(HCO_STRING_SPOTS))
    assert not stale_off, f"HCO_OFFENSIVE_SPOTS names no longer in the table: {stale_off}"
    assert not stale_non, f"HCO_NON_OFFENSIVE_SPOTS names no longer in the table: {stale_non}"


def test_every_non_offensive_entry_carries_a_reason():
    missing = sorted(k for k, v in HCO_NON_OFFENSIVE_SPOTS.items() if not str(v or "").strip())
    assert not missing, f"non-offensive spots with no stated reason: {missing}"


def test_deleted_fcp_entries_stay_deleted():
    """Blame trail: these three held real coords and a live pool drew from them."""
    resurrected = sorted(k for k in DELETED_FCP_ENTRIES if k in HCO_STRING_SPOTS)
    assert not resurrected, (
        f"dead FCP entries are back in HCO_STRING_SPOTS: {resurrected}. If FCP "
        "needs them again, give them their own table rather than an HCO_* one, "
        f"and re-classify them here. Original coords: "
        f"{ {k: DELETED_FCP_ENTRIES[k] for k in resurrected} }"
    )


@pytest.mark.parametrize("is_away_offense", [False, True])
def test_no_offensive_spot_is_behind_the_half_court_line(is_away_offense):
    """The whole point of the pool: an offensive relocate target is never backcourt."""
    offenders = []
    for name in HCO_OFFENSIVE_SPOTS:
        c = _spot_display_coords(name, is_away_offense)
        if in_backcourt(float(c["x"]), is_away_offense):
            offenders.append((name, c))
    assert not offenders, (
        f"offensive spots behind the line (is_away_offense={is_away_offense}): {offenders}"
    )


@pytest.mark.parametrize("is_away_offense", [False, True])
def test_relocate_candidates_are_never_behind_the_line(is_away_offense):
    """Sweep the frontcourt: no starting point yields a backcourt candidate.

    Before the pool fix, a player at x=51 was within 9.0 of fcp_outlet_pf
    (x=43) and could relocate 7 grid behind the line.
    """
    for x in range(50, 100):
        for y in range(5, 46, 5):
            here = {"x": float(x if not is_away_offense else 100 - x), "y": float(y)}
            for c in _predefined_spots_within(here, is_away_offense):
                assert not in_backcourt(float(c["x"]), is_away_offense), (
                    f"relocate candidate {c} from {here} is behind the line "
                    f"(is_away_offense={is_away_offense})"
                )


@pytest.mark.parametrize("is_away_offense", [False, True])
def test_nearest_named_spot_never_returns_a_registry_only_spot(is_away_offense):
    """It feeds shooter_location for freelance shot resolution."""
    for x in range(40, 100, 3):
        for y in range(5, 46, 5):
            here = {"x": float(x if not is_away_offense else 100 - x), "y": float(y)}
            got = nearest_named_spot(here, is_away_offense)
            assert got in HCO_OFFENSIVE_SPOTS, (
                f"nearest_named_spot({here}) returned {got!r}, which is "
                "registry-only and not an offensive spot"
            )


def test_pool_filter_preserves_table_order():
    """Candidate order must not depend on set iteration (hash-seed dependent).

    ``_predefined_spots_within`` feeds ``rng.choice``, so order is part of the
    seeded contract.
    """
    expected = [n for n in HCO_STRING_SPOTS if n in HCO_OFFENSIVE_SPOTS]
    here = {"x": 64.0, "y": 25.0}
    got = _predefined_spots_within(here, False, radius=200.0)
    got_pairs = [(c["x"], c["y"]) for c in got]
    exp_pairs = []
    for n in expected:
        c = _spot_display_coords(n, False)
        cx, cy = round(c["x"], 1), round(c["y"], 1)
        if (cx, cy) == (round(here["x"], 1), round(here["y"], 1)):
            continue
        if math.hypot(cx - here["x"], cy - here["y"]) <= 200.0:
            exp_pairs.append((cx, cy))
    assert got_pairs == exp_pairs, "candidate order diverged from table order"
