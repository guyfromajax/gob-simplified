"""Collision Phase 1 ships behind ``GOB_COLLISION_SEPARATION``, **default OFF** (2026-09-24).

Defender-defender partial-overlap separation. The threshold is PER PAIR and derived from each
player's height, mirroring the frontend's `headRadiusForHeight`; a pair is pushed apart when it
is closer than ``COLLISION_OVERLAP_TOLERANCE * (r_a + r_b)``.

This is a shipped-defaults guard. It also pins the properties the build rests on, because every
one of them is a way the pass could go wrong without failing loudly:

  * **default OFF** — flag-off is byte-identical by construction (the pass returns immediately);
  * **the offence never moves** — the pass only ever writes defender entries;
  * **a defender doing deliberate coverage is never pushed off it** — deny sits at 2.0 on
    purpose, and the audit measured a naive flat rule moving 28.6% deliberate work;
  * **deterministic** — sorted ids, capped passes, capped displacement, and NO RNG, so the pass
    cannot move the draw stream;
  * **the midpoint is preserved** when neither member is pinned.
"""

import math
import random

import pytest

from BackEnd.utils import collision_separation as CS


class _P:
    def __init__(self, height=75):
        self.height = height


FIVE = {p: _P(75) for p in ("PG", "SG", "SF", "PF", "C")}


def _gap(c, a, b):
    return math.hypot(c[a]["x"] - c[b]["x"], c[a]["y"] - c[b]["y"])


@pytest.fixture
def sep_off(monkeypatch):
    monkeypatch.delenv(CS.COLLISION_SEPARATION_FLAG, raising=False)


def test_separation_defaults_off(sep_off):
    assert CS.collision_separation_enabled() is False, (
        "GOB_COLLISION_SEPARATION must default OFF. Phase 1 is built and measured, not flipped."
    )


def test_kill_switch(monkeypatch):
    monkeypatch.setenv(CS.COLLISION_SEPARATION_FLAG, "1")
    assert CS.collision_separation_enabled() is True
    monkeypatch.setenv(CS.COLLISION_SEPARATION_FLAG, "0")
    assert CS.collision_separation_enabled() is False


def test_the_applier_is_inert_with_the_flag_off(sep_off):
    """The whole engine-facing entry point must do nothing at all when the flag is off."""
    anims = [{"playerId": "d1", "movement": [{"coords": {"x": 50.0, "y": 25.0}}]},
             {"playerId": "d2", "movement": [{"coords": {"x": 50.0, "y": 25.0}}]}]
    before = [dict(a["movement"][0]["coords"]) for a in anims]
    stats = CS.apply_separation_to_animations(anims, None, {"PG": _P(), "SG": _P()})
    assert stats["enabled"] is False
    assert [dict(a["movement"][0]["coords"]) for a in anims] == before


# ---------------------------------------------------------------------------
# the threshold is derived, not hardcoded
# ---------------------------------------------------------------------------


def test_threshold_is_derived_from_height():
    """Mirrors createHeadshotMarkerV2.js: clamp(25.5, 39, 30 + (h-72)*0.75) px, / 12.29 px-per-grid.

    The audit's four widths (4.15 / 5.25 / 6.35) are the EXPECTED OUTPUT of this derivation,
    never an input — if someone hardcodes them, the clamp behaviour is lost.
    """
    assert CS.defender_radius_grid(_P(66)) * 2 == pytest.approx(4.15, abs=0.01)   # short clamp
    assert CS.defender_radius_grid(_P(75)) * 2 == pytest.approx(5.25, abs=0.01)   # league median
    assert CS.defender_radius_grid(_P(84)) * 2 == pytest.approx(6.35, abs=0.01)   # tall clamp
    # clamped, not extrapolated
    assert CS.defender_radius_grid(_P(40)) == CS.defender_radius_grid(_P(66))
    assert CS.defender_radius_grid(_P(120)) == CS.defender_radius_grid(_P(84))
    # unknown height falls back to the frontend's own default, not to zero
    assert CS.defender_radius_grid(_P(None)) > 0
    assert CS.defender_radius_grid(None) > 0


def test_threshold_is_half_the_combined_width():
    a, b = _P(75), _P(84)
    expected = CS.COLLISION_OVERLAP_TOLERANCE * (
        CS.defender_radius_grid(a) + CS.defender_radius_grid(b))
    assert CS.separation_threshold(a, b) == pytest.approx(expected)
    assert CS.separation_threshold(_P(75), _P(75)) == pytest.approx(2.62, abs=0.02)


def test_constants_unchanged():
    """Nothing retuned to build this. Jamie tunes once, at the end."""
    assert CS.COLLISION_OVERLAP_TOLERANCE == 0.5
    assert CS.COLLISION_MAX_PASSES == 3
    assert CS.COLLISION_MAX_DISPLACEMENT == 2.0
    assert CS.pinned_coverage_distance() == 2.5      # max(deny 2.0, on-ball tight 2.5)


# ---------------------------------------------------------------------------
# the separation itself
# ---------------------------------------------------------------------------


def test_overlapping_pair_is_pushed_to_the_threshold_and_midpoint_is_preserved():
    c = {"PG": {"x": 50.0, "y": 25.0}, "SG": {"x": 51.0, "y": 25.0}}
    out, _ = CS.separate_defenders(c, FIVE)
    thr = CS.separation_threshold(FIVE["PG"], FIVE["SG"])
    assert _gap(out, "PG", "SG") == pytest.approx(thr)
    assert (out["PG"]["x"] + out["SG"]["x"]) / 2 == pytest.approx(50.5)
    assert (out["PG"]["y"] + out["SG"]["y"]) / 2 == pytest.approx(25.0)


def test_a_clear_pair_is_untouched():
    c = {"PG": {"x": 10.0, "y": 10.0}, "SG": {"x": 40.0, "y": 40.0}}
    out, s = CS.separate_defenders(c, FIVE)
    assert out == {k: dict(v) for k, v in c.items()}
    assert s["pairs_overlapping"] == 0


def test_a_pinned_defender_is_never_moved():
    """THE exemption. Deny at 2.0 and on-ball tight at 2.5 are deliberate; a defender doing that
    work stays put and his partner absorbs the whole separation."""
    c = {"PG": {"x": 50.0, "y": 25.0}, "SG": {"x": 51.0, "y": 25.0}}
    out, s = CS.separate_defenders(c, FIVE, pinned={"PG"})
    assert out["PG"] == {"x": 50.0, "y": 25.0}, "a pinned defender was pushed off his coverage"
    assert "PG" not in s["moved"]
    assert _gap(out, "PG", "SG") == pytest.approx(
        CS.separation_threshold(FIVE["PG"], FIVE["SG"]))


def test_both_pinned_means_the_overlap_is_accepted():
    c = {"PG": {"x": 50.0, "y": 25.0}, "SG": {"x": 51.0, "y": 25.0}}
    out, s = CS.separate_defenders(c, FIVE, pinned={"PG", "SG"})
    assert out == {k: dict(v) for k, v in c.items()}
    assert s["pairs_skipped_both_pinned"] == 1
    assert not s["moved"]


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_result_does_not_depend_on_dict_order():
    """Iteration is by SORTED id. If someone switches to dict or set order the sim stops being
    reproducible, which the equiv-v3 reference would catch only after the fact."""
    import collections
    base = {"PG": {"x": 50.0, "y": 25.0}, "SG": {"x": 50.4, "y": 25.0},
            "SF": {"x": 50.8, "y": 25.0}}
    ref, _ = CS.separate_defenders(base, FIVE)
    rnd = random.Random(7)
    for _ in range(25):
        keys = list(base)
        rnd.shuffle(keys)
        shuffled = collections.OrderedDict((k, dict(base[k])) for k in keys)
        out, _ = CS.separate_defenders(shuffled, FIVE)
        for k in base:
            assert out[k]["x"] == pytest.approx(ref[k]["x"])
            assert out[k]["y"] == pytest.approx(ref[k]["y"])


def test_exact_coincidence_is_resolved_without_randomness():
    c = {"PG": {"x": 50.0, "y": 25.0}, "SG": {"x": 50.0, "y": 25.0}}
    first, _ = CS.separate_defenders(c, FIVE)
    for _ in range(5):
        again, _ = CS.separate_defenders(c, FIVE)
        assert again == first
    assert _gap(first, "PG", "SG") > 0


def test_it_draws_no_rng():
    """A placement pass that draws would move the draw stream and break every reference."""
    from BackEnd.utils import sim_random
    c = {"PG": {"x": 50.0, "y": 25.0}, "SG": {"x": 50.0001, "y": 25.0},
         "SF": {"x": 50.0002, "y": 25.0}}
    st_std = random.getstate()
    st_sim = sim_random.sim_rng.getstate()
    CS.separate_defenders(c, FIVE)
    assert random.getstate() == st_std
    assert sim_random.sim_rng.getstate() == st_sim


def test_displacement_is_capped_and_residual_is_accepted():
    """Five defenders stacked on one cell cannot all be resolved inside the cap — the pass must
    bound the push and ACCEPT the residual rather than iterating to convergence."""
    c = {p: {"x": 50.0 + i * 0.0001, "y": 25.0} for i, p in enumerate(FIVE)}
    out, s = CS.separate_defenders(c, FIVE)
    assert max(s["moved"].values()) <= CS.COLLISION_MAX_DISPLACEMENT + 1e-9
    assert s["residual"], "a 5-way pileup inside the cap should leave measurable residual"


def test_the_applier_never_writes_an_offensive_entry(monkeypatch):
    """SCOPE. Offensive entries are read (to find each defender's man) and never written."""
    monkeypatch.setenv(CS.COLLISION_SEPARATION_FLAG, "1")
    anims = [
        {"playerId": "d_PG", "movement": [{"coords": {"x": 50.0, "y": 25.0}}]},
        {"playerId": "d_SG", "movement": [{"coords": {"x": 50.2, "y": 25.0}}]},
        {"playerId": "o_PG", "movement": [{"coords": {"x": 80.0, "y": 25.0}}]},
        {"playerId": "o_SG", "movement": [{"coords": {"x": 81.0, "y": 25.0}}]},
    ]

    class _Pl:
        def __init__(self, pid):
            self.player_id = pid
            self.height = 75

    off_before = [dict(a["movement"][0]["coords"]) for a in anims if a["playerId"].startswith("o_")]
    CS.apply_separation_to_animations(
        anims, None,
        {"PG": _Pl("d_PG"), "SG": _Pl("d_SG")},
        off_lineup={"PG": _Pl("o_PG"), "SG": _Pl("o_SG")},
    )
    off_after = [dict(a["movement"][0]["coords"]) for a in anims if a["playerId"].startswith("o_")]
    assert off_after == off_before, "an OFFENSIVE coordinate moved — Phase 1 is defenders only"
    d = [a for a in anims if a["playerId"] == "d_SG"][0]["movement"][0]["coords"]
    assert d["x"] != 50.2, "the defenders should have separated"
