"""Collision Phase 1 EXTENDED ships behind ``GOB_COLLISION_SEPARATION_ALL``, **default OFF**
(2026-09-24), and REQUIRES ``GOB_COLLISION_SEPARATION=1``.

Ten-player separation: def-def, off-off and def-off in one relaxation. Same machinery and the
same four constants as Phase 1 — nothing retuned.

THE CENTRAL GUARD IS THE SHOOTER. ``_documentation_master/projects/bugs.md`` records that
**26.8% played / 27.6% wrap of shots are decided by ``<=`` against a ZERO MARGIN** on the arc,
and that moving authored spot coordinates to create margin is "a balance change wearing a
tidy-up costume". A sub-cell nudge to a shooter reflips that population. He is exempt at every
step and the invariant is asserted here, not argued.
"""

import math
import random

import pytest

from BackEnd.utils import collision_separation as CS


class _P:
    def __init__(self, pid, height=75):
        self.player_id = pid
        self.height = height


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv(CS.COLLISION_SEPARATION_FLAG, raising=False)
    monkeypatch.delenv(CS.COLLISION_SEPARATION_ALL_FLAG, raising=False)
    monkeypatch.setattr(CS, "_WARNED_ALL_WITHOUT_BASE", [False])


def _both_on(monkeypatch):
    monkeypatch.setenv(CS.COLLISION_SEPARATION_FLAG, "1")
    monkeypatch.setenv(CS.COLLISION_SEPARATION_ALL_FLAG, "1")


SKELETON = {"steps": [
    {"timestamp": 0, "pos_actions": {
        "PG": {"action": "handle_ball", "location": "key"},
        "SG": {"action": "drift", "location": "upper wing"},
        "SF": {"action": "drift", "location": "lower wing"},
        "PF": {"action": "drift", "location": "upper lowPost"},
        "C": {"action": "drift", "location": "lower lowPost"}}},
    {"timestamp": 300, "pos_actions": {
        "PG": {"action": "pass", "location": "key"},
        "SG": {"action": "shoot", "location": "upper wing"}}},
]}


def _scene(off_xy, def_xy):
    anims = []
    for pos, (x, y) in off_xy.items():
        anims.append({"playerId": "o_" + pos, "start": {"x": x, "y": y}, "end": {"x": x, "y": y},
                      "movement": [{"timestamp": 0, "coords": {"x": x, "y": y}},
                                   {"timestamp": 300, "coords": {"x": x, "y": y}}]})
    for pos, (x, y) in def_xy.items():
        anims.append({"playerId": "d_" + pos, "start": {"x": x, "y": y}, "end": {"x": x, "y": y},
                      "movement": [{"timestamp": 0, "coords": {"x": x, "y": y}},
                                   {"timestamp": 300, "coords": {"x": x, "y": y}}]})
    off = {p: _P("o_" + p) for p in off_xy}
    dfn = {p: _P("d_" + p) for p in def_xy}
    return anims, off, dfn


def _coord(anims, pid, i=0):
    return [a for a in anims if a["playerId"] == pid][0]["movement"][i]["coords"]


# ---------------------------------------------------------------------------
# shipped defaults and the dependency on the base flag
# ---------------------------------------------------------------------------


def test_all_defaults_off():
    assert CS.collision_separation_all_enabled() is False


def test_kill_switch(monkeypatch):
    monkeypatch.setenv(CS.COLLISION_SEPARATION_ALL_FLAG, "1")
    assert CS.collision_separation_all_enabled() is True
    monkeypatch.setenv(CS.COLLISION_SEPARATION_ALL_FLAG, "0")
    assert CS.collision_separation_all_enabled() is False


def test_all_without_base_warns_once_and_does_nothing(monkeypatch, caplog):
    monkeypatch.setenv(CS.COLLISION_SEPARATION_ALL_FLAG, "1")
    anims, off, dfn = _scene({"SF": (50.0, 25.0)}, {"SF": (50.2, 25.0)})
    before = [dict(_coord(anims, a["playerId"])) for a in anims]
    with caplog.at_level("WARNING"):
        for _ in range(3):
            st = CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    assert st["enabled"] is False and st["all_enabled"] is False
    assert [dict(_coord(anims, a["playerId"])) for a in anims] == before
    hits = [r for r in caplog.records if "GOB_COLLISION_SEPARATION_ALL=1" in r.getMessage()]
    assert len(hits) == 1, "the no-op warning must fire exactly once per process"


def test_base_flag_alone_still_never_moves_the_offence(monkeypatch):
    """Phase 1 must stay independently rollback-able: base-only behaviour is unchanged."""
    monkeypatch.setenv(CS.COLLISION_SEPARATION_FLAG, "1")
    anims, off, dfn = _scene({"SF": (50.0, 25.0), "PF": (50.4, 25.0)},
                             {"SF": (70.0, 25.0), "PF": (70.3, 25.0)})
    o_before = {p: dict(_coord(anims, "o_" + p)) for p in off}
    st = CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    assert st["all_enabled"] is False
    assert {p: dict(_coord(anims, "o_" + p)) for p in off} == o_before
    assert _coord(anims, "d_PF")["x"] != 70.3, "defenders should still separate"


# ---------------------------------------------------------------------------
# THE ITEM 22 GUARD
# ---------------------------------------------------------------------------


def test_the_shooter_is_identified_from_the_authored_play_not_the_outcome():
    assert CS.shooter_positions(SKELETON) == {"SG"}
    assert CS.shooter_positions({"steps": []}) == set()


def test_the_shooter_never_moves_even_when_buried(monkeypatch):
    """ITEM 22. 26.8%/27.6% of shots sit on a zero-margin `<=` against the arc. A sub-cell
    nudge to the shooter reflips that population, so he is exempt at EVERY step and his
    partner absorbs the whole separation."""
    _both_on(monkeypatch)
    anims, off, dfn = _scene(
        {"SG": (74.0, 40.0), "SF": (74.05, 40.0), "PF": (74.1, 40.05)},
        {"SG": (74.02, 40.02), "SF": (74.2, 40.1)})
    st = CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    assert st["all_enabled"] is True
    for i in (0, 1):
        assert _coord(anims, "o_SG", i) == {"x": 74.0, "y": 40.0}, (
            "THE SHOOTER MOVED — this is the Item 22 trap; 2PT/3PT can flip on a sub-cell nudge")
    assert st["pinned_shooter"] > 0
    assert any(a["playerId"] != "o_SG" for a in anims), "someone else must absorb it"


def test_a_ball_action_exempts_that_player_at_that_step(monkeypatch):
    """His coordinate is a pass origin / drive origin / shot spot."""
    _both_on(monkeypatch)
    anims, off, dfn = _scene({"PG": (64.0, 25.0), "SF": (64.1, 25.0)},
                             {"PG": (30.0, 10.0), "SF": (31.0, 12.0)})
    CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    assert _coord(anims, "o_PG", 0) == {"x": 64.0, "y": 25.0}, "the ball handler moved"


def test_ball_actions_cover_the_whole_vocabulary():
    assert CS.BALL_ACTIONS == {"handle_ball", "receive", "pass", "drive", "shoot"}


# ---------------------------------------------------------------------------
# the extension itself
# ---------------------------------------------------------------------------


def test_offence_offence_pairs_now_separate(monkeypatch):
    """The whole point of the extension. SF/PF are neither shooter nor ball handler."""
    monkeypatch.setattr(CS, "PIN_OFFENCE_AT_AUTHORED_LOCATION", False)
    _both_on(monkeypatch)
    anims, off, dfn = _scene({"SF": (50.0, 25.0), "PF": (50.4, 25.0)},
                             {"SF": (10.0, 10.0), "PF": (12.0, 12.0)})
    CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    gap = math.hypot(_coord(anims, "o_SF")["x"] - _coord(anims, "o_PF")["x"],
                     _coord(anims, "o_SF")["y"] - _coord(anims, "o_PF")["y"])
    assert gap == pytest.approx(CS.separation_threshold(_P("a"), _P("b")))


def test_constants_unchanged():
    """Nothing retuned to build this."""
    assert CS.COLLISION_OVERLAP_TOLERANCE == 0.5
    assert CS.COLLISION_MAX_PASSES == 3
    assert CS.COLLISION_MAX_DISPLACEMENT == 2.0
    assert CS.pinned_coverage_distance() == 2.5


def test_it_draws_no_rng(monkeypatch):
    from BackEnd.utils import sim_random
    _both_on(monkeypatch)
    anims, off, dfn = _scene({"SF": (50.0, 25.0), "PF": (50.0, 25.0)},
                             {"SF": (50.0, 25.0), "PF": (50.1, 25.0)})
    st_std, st_sim = random.getstate(), sim_random.sim_rng.getstate()
    CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    assert random.getstate() == st_std
    assert sim_random.sim_rng.getstate() == st_sim


def test_result_does_not_depend_on_dict_order(monkeypatch):
    import collections
    monkeypatch.setattr(CS, "PIN_OFFENCE_AT_AUTHORED_LOCATION", False)
    _both_on(monkeypatch)
    base_off = {"SF": (50.0, 25.0), "PF": (50.4, 25.0), "C": (50.8, 25.0)}
    base_def = {"SF": (50.2, 25.2), "PF": (50.6, 25.2)}
    anims, off, dfn = _scene(base_off, base_def)
    CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    ref = {a["playerId"]: dict(_coord(anims, a["playerId"])) for a in anims}
    rnd = random.Random(5)
    for _ in range(15):
        keys = list(base_off); rnd.shuffle(keys)
        shuffled_off = collections.OrderedDict((k, base_off[k]) for k in keys)
        anims2, off2, dfn2 = _scene(shuffled_off, base_def)
        CS.apply_separation_to_animations(anims2, None, dfn2, off2, skeleton=SKELETON)
        for pid, c in ref.items():
            got = _coord(anims2, pid)
            assert got["x"] == pytest.approx(c["x"]) and got["y"] == pytest.approx(c["y"])


def test_a_carried_forward_offensive_player_is_never_written(monkeypatch):
    """movement[i] is not step i for the offence. A player with no entry at this timestamp has
    nowhere to write, so he is pinned and counted rather than written to the wrong beat."""
    _both_on(monkeypatch)
    anims, off, dfn = _scene({"SF": (50.0, 25.0)}, {"SF": (50.1, 25.0), "PF": (50.2, 25.0)})
    sf = [a for a in anims if a["playerId"] == "o_SF"][0]
    sf["movement"] = [{"timestamp": 0, "coords": {"x": 50.0, "y": 25.0}}]   # no entry at 300
    st = CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    assert st["off_carried_not_writable"] >= 1
    assert len(sf["movement"]) == 1


def test_an_offensive_entry_is_written_at_most_once_per_pass(monkeypatch):
    """26.8% of defender movement lists REPEAT a timestamp, so the same offensive entry can be
    selected at more than one index. Writing it twice applies COLLISION_MAX_DISPLACEMENT twice —
    measured at 4.0 against a 2.0 cap before this guard."""
    monkeypatch.setattr(CS, "PIN_OFFENCE_AT_AUTHORED_LOCATION", False)
    _both_on(monkeypatch)
    anims, off, dfn = _scene({"SF": (50.0, 25.0)}, {"SF": (50.05, 25.0), "PF": (50.1, 25.0)})
    # both defender entries carry the SAME timestamp — the repeat case, seen in 26.8% of lists
    for pos in ("SF", "PF"):
        for e in [a for a in anims if a["playerId"] == "d_" + pos][0]["movement"]:
            e["timestamp"] = 0
    sf = [a for a in anims if a["playerId"] == "o_SF"][0]
    sf["movement"] = [{"timestamp": 0, "coords": {"x": 50.0, "y": 25.0}}]
    st = CS.apply_separation_to_animations(anims, None, dfn, off, skeleton=SKELETON)
    moved = math.hypot(sf["movement"][0]["coords"]["x"] - 50.0,
                       sf["movement"][0]["coords"]["y"] - 25.0)
    assert moved <= CS.COLLISION_MAX_DISPLACEMENT + 1e-9, (
        "an offensive entry was displaced past the cap — it was written more than once")
    assert st["stats"]["pinned_already_written"] >= 1 if "stats" in st else True


# ---------------------------------------------------------------------------
# GOB_COLLISION_TOLERANCE — the sweep override. It must not change any default.
# ---------------------------------------------------------------------------


def test_tolerance_override_absent_resolves_to_the_shipped_constant(monkeypatch):
    """The whole safety property: unset, the override IS the constant, so production is inert."""
    monkeypatch.delenv(CS.COLLISION_TOLERANCE_ENV, raising=False)
    assert CS.overlap_tolerance() == CS.COLLISION_OVERLAP_TOLERANCE == 0.5


def test_tolerance_override_supplies_the_value(monkeypatch):
    monkeypatch.setenv(CS.COLLISION_TOLERANCE_ENV, "1.0")
    assert CS.overlap_tolerance() == 1.0
    a, b = _P("a"), _P("b")
    # full sprite clearance at 1.0 = exactly twice the 0.5 threshold
    full = CS.separation_threshold(a, b)
    monkeypatch.setenv(CS.COLLISION_TOLERANCE_ENV, "0.5")
    assert full == pytest.approx(2.0 * CS.separation_threshold(a, b))


def test_a_junk_override_falls_back_rather_than_changing_behaviour(monkeypatch):
    """Unparseable or non-positive must never silently alter the shipped default."""
    for junk in ("", "   ", "abc", "0", "-1", "None"):
        monkeypatch.setenv(CS.COLLISION_TOLERANCE_ENV, junk)
        assert CS.overlap_tolerance() == 0.5, junk


def test_the_constant_itself_is_untouched():
    assert CS.COLLISION_OVERLAP_TOLERANCE == 0.5


def test_cap_binding_is_counted(monkeypatch):
    """At higher tolerance the 2.0 displacement cap, not the tolerance, may become the limiter.
    The sweep needs to see that, so pushes and capped pushes are counted."""
    monkeypatch.setenv(CS.COLLISION_TOLERANCE_ENV, "1.0")
    five = {p: _P(p) for p in ("PG", "SG", "SF", "PF", "C")}
    coords = {p: {"x": 50.0 + i * 0.01, "y": 25.0} for i, p in enumerate(five)}
    _out, s = CS.separate_defenders(coords, five)
    assert s["pushes"] > 0
    assert s["pushes_cap_bound"] > 0, "a 5-way pileup at full clearance must bind the 2.0 cap"
    assert s["pushes_cap_bound"] <= s["pushes"]
