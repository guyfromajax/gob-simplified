"""The zone credited defender (non-shot HCO outcomes) must use the called zone's shell.

phase_resolution used to compare defense_playcall against "3-2 Zone" / "1-3-1 Zone" display
strings. set_playcalls stores catalogue ids ("3-2-zone"), so every zone was credited with 2-3
geometry. The catalogue is patched in memory; no collection is written.
"""
import inspect
import logging
import re

import pytest

import BackEnd.engine.attack_drive_clearance as ADC
import BackEnd.engine.phase_resolution as PR
from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.utils import defense_identity as DI
from BackEnd.utils.shared_defense import (
    _get_23_zone_boundaries,
    _get_32_zone_boundaries,
    _get_131_zone_boundaries,
)

CATALOG = [
    {"_id": "b", "defense_id": "2-3-zone", "defense_type": "Zone", "name": "2-3 Zone"},
    {"_id": "c", "defense_id": "3-2-zone", "defense_type": "Zone", "name": "3-2 Zone"},
    {"_id": "d", "defense_id": "1-3-1-zone", "defense_type": "Zone", "name": "1-3-1 Zone"},
]

# A layout whose credit is identical across RNG seeds (no overlap tie-breaks) and differs per shell.
BH_SPOT = "key"
LAYOUT = [BH_SPOT, "upper midWing", "upper wing", "upper corner", "lower corner"]

# RE-DERIVED after cd2a08c3e ("Turn the zone sink on by default"), 2026-09-19.
#
# This map depends on SINK PLACEMENT, not just on the shell's polygons. The credited
# defender comes from `defender_to_offensive_player`, which is built by asking "which
# offensive player is nearest this defender's assigned coordinate" - so moving the
# defenders moves the credit. The sink changed where empty-zone defenders stand, and
# the 1-3-1 entry went from ["PG", "PF"] to ["PG"] as a result: the PF no longer lands
# close enough to the ball handler to be credited with him.
#
# So a change to the sink's weights, its anchors or the zone spot lists can legitimately
# change these values. If this test fails after such a change, re-derive rather than
# assume a regression - but check the shells still differ from each other, because that
# (not the exact positions) is what the test exists to prove.
# Derived with GOB_ZONE_SINK at its shipped default (ON); GOB_ZONE_SINK=0 gives the
# pre-sink map and is expected to fail here.
EXPECTED = {"2-3-zone": ["SG", "C"], "3-2-zone": ["PG", "SF"], "1-3-1-zone": ["PG"]}

LEGACY_LITERAL = re.compile(r'==\s*"(3-2|1-3-1|2-3) Zone"')


@pytest.fixture(autouse=True)
def catalog(monkeypatch):
    DI.clear_defense_identity_cache()
    monkeypatch.setattr(DI, "_read_catalog_documents", lambda: list(CATALOG))
    yield
    DI.clear_defense_identity_cache()


def _players():
    return [
        {"player_id": f"p{i}", "coords": HCO_STRING_SPOTS[s], "spot": s, "is_ball_handler": i == 0}
        for i, s in enumerate(LAYOUT)
    ]


def _guards(call):
    return PR._zone_ball_handler_guards(
        call, _players(), HCO_STRING_SPOTS[BH_SPOT], BH_SPOT, "p0", "normal", False
    )


def _credits_by_zone():
    out = {}
    for call in EXPECTED:
        state = PR.random.getstate()
        out[call] = _guards(call)
        PR.random.setstate(state)
    return out


def _assert_per_zone_geometry(credits):
    assert credits == EXPECTED
    assert len({tuple(v) for v in credits.values()}) == 3


def test_each_zone_credits_with_its_own_shell():
    _assert_per_zone_geometry(_credits_by_zone())


def test_reattribution_is_logged_only_when_the_shell_changes_the_credit(caplog):
    caplog.set_level(logging.WARNING)
    for call in EXPECTED:
        caplog.clear()
        state = PR.random.getstate()
        _guards(call)
        PR.random.setstate(state)
        logged = [r for r in caplog.records if "[ZONE CREDIT]" in r.getMessage()]
        assert len(logged) == (0 if call == "2-3-zone" else 1), call


def test_two_three_comparison_does_not_move_the_sim_rng():
    from BackEnd.utils.shared_defense import assign_all_zone_defenders

    start = PR.random.getstate()
    assign_all_zone_defenders(
        _get_32_zone_boundaries(BH_SPOT, False), _players(), HCO_STRING_SPOTS[BH_SPOT],
        BH_SPOT, "normal", False,
    )
    only_real_assignment = PR.random.getstate()
    PR.random.setstate(start)
    _guards("3-2-zone")
    assert PR.random.getstate() == only_real_assignment


def test_poison_legacy_literals_collapse_every_zone_to_two_three(monkeypatch):
    """Reinstate the old literal comparison: the per-zone assertion must fail."""

    def legacy(defense_playcall, ball_spot, is_away_offense):
        if defense_playcall == "3-2 Zone":
            return _get_32_zone_boundaries(ball_spot, is_away_offense)
        if defense_playcall == "1-3-1 Zone":
            return _get_131_zone_boundaries(ball_spot, is_away_offense)
        return _get_23_zone_boundaries(ball_spot, is_away_offense)

    monkeypatch.setattr(ADC, "_zone_boundaries_for_spot", legacy)
    credits = _credits_by_zone()
    assert set(map(tuple, credits.values())) == {("SG", "C")}
    with pytest.raises(AssertionError):
        _assert_per_zone_geometry(credits)


def test_guard_no_legacy_zone_literal_comparisons_in_hco_resolution():
    source = inspect.getsource(PR.resolve_half_court_offense_logic)
    assert not LEGACY_LITERAL.search(source)
    assert "_zone_ball_handler_guards(" in source


def test_guard_detects_reinstated_literals():
    poisoned = 'if def_call == "3-2 Zone":\n    pass\nelif def_call == "1-3-1 Zone":\n    pass\n'
    assert LEGACY_LITERAL.search(poisoned)
