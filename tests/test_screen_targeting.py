"""Spatial screens Stage A ships behind ``GOB_SCREEN_TARGETING``, **default OFF** (2026-09-24).

The screener is aimed at a point on the receiver's DEFENDER, one contact-distance in front
of him along his path to where the receiver is heading — instead of at
``OFFSET_SPOTS[location]``, a cosmetic nudge off the receiver's own spot that knows about
no defender at all.

This pins the properties the build rests on, each of which is a way it could go wrong
without failing loudly:

  * **default OFF** — flag-off returns before touching anything, so it is byte-identical;
  * **no RNG on either side of the flag** — a draw here would move the whole stream;
  * **the defence never moves** — Stage A writes offensive screeners only;
  * **NOT CLAIRVOYANT** — the target reads the receiver's authored next spot and the
    defender's current coordinate, never the step's outcome;
  * **no new tuning constant** — the stand-off IS Phase 1's derived contact distance;
  * **deterministic** — sorted positions, timestamp-matched movement entries.
"""

import math
import random

import pytest

from BackEnd.utils import screen_targeting as ST
from BackEnd.utils import collision_separation as CS


class _P:
    def __init__(self, pid, height=75):
        self.player_id = pid
        self.height = height


def _steps():
    """Two steps: PF screens for SG at 'key'; SG then moves on to 'upper wing'."""
    return [
        {"timestamp": 0, "pos_actions": {
            "PF": {"action": "screen", "location": "key"},
            "SG": {"action": "cut", "location": "key"},
            "PG": {"action": "handle_ball", "location": "deep key"},
        }},
        {"timestamp": 300, "pos_actions": {
            "SG": {"action": "receive", "location": "upper wing"},
            "PG": {"action": "pass", "location": "deep key"},
        }},
    ]


@pytest.fixture
def flag_off(monkeypatch):
    monkeypatch.delenv(ST.SCREEN_TARGETING_FLAG, raising=False)


@pytest.fixture
def flag_on(monkeypatch):
    monkeypatch.setenv(ST.SCREEN_TARGETING_FLAG, "1")


# ---------------------------------------------------------------------------
# shipped defaults
# ---------------------------------------------------------------------------


def test_targeting_defaults_off(flag_off):
    assert ST.screen_targeting_enabled() is False, (
        "GOB_SCREEN_TARGETING must default OFF. Stage A is built and measured, not flipped."
    )


def test_kill_switch(monkeypatch):
    monkeypatch.setenv(ST.SCREEN_TARGETING_FLAG, "1")
    assert ST.screen_targeting_enabled() is True
    monkeypatch.setenv(ST.SCREEN_TARGETING_FLAG, "0")
    assert ST.screen_targeting_enabled() is False


def test_the_applier_is_inert_with_the_flag_off(flag_off):
    anims = [{"playerId": "o_PF", "start": {"x": 1.0, "y": 1.0}, "end": {"x": 1.0, "y": 1.0},
              "movement": [{"timestamp": 0, "coords": {"x": 1.0, "y": 1.0}, "action": "screen"}]}]
    before = [dict(a["movement"][0]["coords"]) for a in anims]
    stats = ST.apply_screen_targeting(anims, None, {"steps": _steps()},
                                      {"PF": _P("o_PF")}, {"PF": _P("d_PF")})
    assert stats["enabled"] is False
    assert stats["applied"] == 0
    assert [dict(a["movement"][0]["coords"]) for a in anims] == before


# ---------------------------------------------------------------------------
# the geometry
# ---------------------------------------------------------------------------


def test_stand_off_is_phase_1s_derived_contact_distance_not_a_new_constant():
    """If someone replaces this with a literal, the sprite-geometry derivation is lost and
    Stage A silently acquires a tuning knob the brief forbids."""
    scr, dfn = _P("s"), _P("d")
    pt = ST.screen_point({"x": 50.0, "y": 25.0}, {"x": 90.0, "y": 25.0}, scr, dfn)
    gap = math.hypot(pt["x"] - 50.0, pt["y"] - 25.0)
    assert gap == pytest.approx(CS.separation_threshold(scr, dfn))
    assert gap == pytest.approx(2.62, abs=0.02)          # two median players


def test_the_screener_lands_between_the_defender_and_where_the_receiver_is_going():
    """THE point of Stage A. Not beside the receiver — in the defender's path."""
    dfn_c, dest = {"x": 50.0, "y": 25.0}, {"x": 80.0, "y": 40.0}
    pt = ST.screen_point(dfn_c, dest, _P("s"), _P("d"))
    # same direction as defender->dest, and strictly nearer the defender than the dest is
    v = (dest["x"] - dfn_c["x"], dest["y"] - dfn_c["y"])
    w = (pt["x"] - dfn_c["x"], pt["y"] - dfn_c["y"])
    cross = v[0] * w[1] - v[1] * w[0]
    assert abs(cross) < 1e-6, "screen point is off the defender->destination line"
    assert v[0] * w[0] + v[1] * w[1] > 0, "screen point is BEHIND the defender"
    assert math.hypot(*w) < math.hypot(*v)


def test_no_path_means_no_screen_point():
    """A defender already standing on the receiver's destination has no path to block;
    inventing a direction there would be manufacturing geometry."""
    assert ST.screen_point({"x": 50.0, "y": 25.0}, {"x": 50.0, "y": 25.0},
                           _P("s"), _P("d")) is None


def test_screen_point_is_clamped_to_the_floor():
    pt = ST.screen_point({"x": 99.9, "y": 49.9}, {"x": 200.0, "y": 200.0}, _P("s"), _P("d"))
    assert 0.0 <= pt["x"] <= ST.COURT_MAX_X and 0.0 <= pt["y"] <= ST.COURT_MAX_Y


# ---------------------------------------------------------------------------
# receiver derivation — the thing that has no runtime event to read
# ---------------------------------------------------------------------------


def test_receiver_is_the_teammate_on_the_screeners_authored_spot():
    pas = _steps()[0]["pos_actions"]
    assert ST.derive_receiver(pas, "PF") == ("SG", "unique_same_location")


def test_no_co_located_teammate_is_reported_not_guessed():
    """12.7% of real screens have nobody on the screener's spot. Stage A must fall back to
    today's placement and COUNT it, never pick an arbitrary teammate."""
    pas = {"PF": {"action": "screen", "location": "key"},
           "SG": {"action": "cut", "location": "upper wing"}}
    recv, why = ST.derive_receiver(pas, "PF")
    assert recv is None and why == "none_same_location"


def test_ambiguity_resolves_by_lineup_slot_order_not_dict_order():
    import collections
    base = {"PF": {"action": "screen", "location": "key"},
            "SG": {"action": "cut", "location": "key"},
            "SF": {"action": "cut", "location": "key"}}
    rnd = random.Random(11)
    for _ in range(25):
        keys = list(base)
        rnd.shuffle(keys)
        shuffled = collections.OrderedDict((k, base[k]) for k in keys)
        assert ST.derive_receiver(shuffled, "PF") == ("SF", "ambiguous_same_location")


def test_receiver_destination_is_the_next_authored_spot_that_differs():
    steps = _steps()
    assert ST.receiver_next_location(steps, 0, "SG", "key") == "upper wing"


def test_a_receiver_who_never_moves_has_no_destination():
    steps = [{"timestamp": 0, "pos_actions": {"PF": {"action": "screen", "location": "key"},
                                              "SG": {"action": "cut", "location": "key"}}},
             {"timestamp": 300, "pos_actions": {"SG": {"action": "shoot", "location": "key"}}}]
    assert ST.receiver_next_location(steps, 0, "SG", "key") is None


def test_destination_never_reads_a_step_before_the_screen():
    """CLAIRVOYANCE'S MIRROR IMAGE: the screener reads the play FORWARD. A spot the receiver
    already left is not where he is heading."""
    steps = [{"timestamp": 0, "pos_actions": {"SG": {"action": "cut", "location": "lower wing"}}},
             {"timestamp": 300, "pos_actions": {"PF": {"action": "screen", "location": "key"},
                                                "SG": {"action": "cut", "location": "key"}}}]
    assert ST.receiver_next_location(steps, 1, "SG", "key") is None


# ---------------------------------------------------------------------------
# guard resolution
# ---------------------------------------------------------------------------


def test_zone_uses_the_zone_guard_map_and_not_the_man_matchups():
    """In a zone nobody is playing man; reading the matchup dict would invent a defender.
    Measured: zone legitimately resolves nobody on 48.2% of screens."""
    off = {"SG": _P("o_SG")}
    guard_of = {"SG": "SG"}          # a man answer that must NOT be used
    assert ST.resolve_receiver_guard("SG", 0, zone=True, guard_of=guard_of,
                                     zone_assignments={}, off_lineup=off) is None
    assert ST.resolve_receiver_guard(
        "SG", 0, zone=True, guard_of=guard_of,
        zone_assignments={0: {"PF": "o_SG"}}, off_lineup=off) == "PF"


def test_man_uses_the_matchup_map_including_a_cross_match():
    assert ST.resolve_receiver_guard("SG", 0, zone=False, guard_of={"SG": "PG"},
                                     zone_assignments=None, off_lineup={}) == "PG"


# ---------------------------------------------------------------------------
# no RNG, no defenders moved
# ---------------------------------------------------------------------------


def test_it_draws_no_rng_on_either_side_of_the_flag(monkeypatch):
    from BackEnd.utils import sim_random
    anims = [{"playerId": "o_PF", "start": {"x": 1.0, "y": 1.0}, "end": {"x": 1.0, "y": 1.0},
              "movement": [{"timestamp": 0, "coords": {"x": 1.0, "y": 1.0}, "action": "screen"}]}]
    for val in ("0", "1"):
        monkeypatch.setenv(ST.SCREEN_TARGETING_FLAG, val)
        st_std = random.getstate()
        st_sim = sim_random.sim_rng.getstate()
        ST.apply_screen_targeting(anims, None, {"steps": _steps()},
                                  {"PF": _P("o_PF")}, {"PF": _P("d_PF")})
        assert random.getstate() == st_std
        assert sim_random.sim_rng.getstate() == st_sim


def test_start_and_end_follow_a_retargeted_first_or_last_step():
    """``start``/``end`` are snapshots of movement[0]/movement[-1] taken during the build. A
    retarget that does not resync leaves the entry disagreeing with its own movement list."""
    anim = {"playerId": "o_PF", "start": {"x": 1.0, "y": 1.0}, "end": {"x": 9.0, "y": 9.0},
            "movement": [{"timestamp": 0, "coords": {"x": 5.0, "y": 5.0}},
                         {"timestamp": 300, "coords": {"x": 7.0, "y": 7.0}}]}
    ST._resync_start_end(anim)
    assert anim["start"] == {"x": 5.0, "y": 5.0}
    assert anim["end"] == {"x": 7.0, "y": 7.0}


def test_movement_entry_is_matched_by_timestamp_not_by_step_index():
    """An offensive player's movement only gains an entry on steps where he HAS a
    pos_action, so movement[i] is not step i. Indexing would retarget the wrong beat."""
    anim = {"playerId": "o_PF", "movement": [{"timestamp": 600, "coords": {"x": 3.0, "y": 3.0}}]}
    by_pid = {"o_PF": anim}
    p = _P("o_PF")
    assert ST._movement_entry(by_pid, p, 0) is None
    assert ST._movement_entry(by_pid, p, 600) is anim["movement"][0]
