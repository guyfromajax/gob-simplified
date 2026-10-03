"""Spatial screens Stage B ships behind ``GOB_SCREEN_CONTEST``, **default OFF** (2026-09-24).

FIGHT THROUGH / GO AROUND / SWITCH, decided by the two defenders' and the screener's
attributes on the house ``composite x randint(1, 6)`` idiom.

What this pins, each one a way it could go wrong quietly:

  * **default OFF**, and **requires Stage A** — contest without targeting logs once and
    no-ops rather than half-applying;
  * **the draw itself is gated**, not just its effect — a draw with the flag off would
    move every reference;
  * **``sim_rng``, never the global ``random``** — the defect in
    ``shared.calculate_screen_score`` is not copied;
  * **the stored matchup map is never mutated** — a SWITCH writes an override layer, so
    the user's Defense Matchups choice is not silently rewritten or persisted;
  * **the override is cleared at every possession boundary**;
  * **a switch keeps the map 1-to-1** — never two defenders on one man.
"""

import random

import pytest

from BackEnd.utils import screen_contest as SC
from BackEnd.utils import screen_targeting as ST
from BackEnd.utils import man_defense_matchups as MM


class _P:
    def __init__(self, pid="p", **attrs):
        self.player_id = pid
        self.height = 75
        base = {"AG": 50, "ST": 50, "IQ": 50, "ND": 50, "CH": 50}
        base.update(attrs)
        self.attributes = base


# ---------------------------------------------------------------------------
# shipped defaults and the Stage A dependency
# ---------------------------------------------------------------------------


def test_contest_defaults_off(monkeypatch):
    monkeypatch.delenv(SC.SCREEN_CONTEST_FLAG, raising=False)
    assert SC.screen_contest_enabled() is False


def test_kill_switch(monkeypatch):
    monkeypatch.setenv(SC.SCREEN_CONTEST_FLAG, "1")
    assert SC.screen_contest_enabled() is True
    monkeypatch.setenv(SC.SCREEN_CONTEST_FLAG, "0")
    assert SC.screen_contest_enabled() is False


def test_contest_without_targeting_warns_once_and_does_nothing(monkeypatch, caplog):
    """It must NOT silently half-apply: no placement means no screen to contest."""
    monkeypatch.setenv(SC.SCREEN_CONTEST_FLAG, "1")
    monkeypatch.delenv(ST.SCREEN_TARGETING_FLAG, raising=False)
    monkeypatch.setattr(SC, "_WARNED", [False])
    with caplog.at_level("WARNING"):
        for _ in range(3):
            stats = ST.apply_screen_targeting([], None, {"steps": []}, {"a": 1}, {"b": 2})
    assert stats["enabled"] is False and stats["applied"] == 0
    hits = [r for r in caplog.records if "GOB_SCREEN_CONTEST=1" in r.getMessage()]
    assert len(hits) == 1, "the no-op warning must fire exactly once per process"


def test_the_draw_is_gated_not_just_its_effect(monkeypatch):
    """A draw with the flag off would shift the stream and break every reference — which
    is why the 240/240 gate is on draws as well as fingerprint."""
    from BackEnd.utils import sim_random
    monkeypatch.delenv(SC.SCREEN_CONTEST_FLAG, raising=False)
    monkeypatch.setenv(ST.SCREEN_TARGETING_FLAG, "1")
    steps = [{"timestamp": 0, "pos_actions": {
        "PF": {"action": "screen", "location": "key"},
        "SG": {"action": "cut", "location": "key"}}},
        {"timestamp": 300, "pos_actions": {"SG": {"action": "receive", "location": "upper wing"}}}]
    anims = [{"playerId": "o_PF", "start": {"x": 1.0, "y": 1.0}, "end": {"x": 1.0, "y": 1.0},
              "movement": [{"timestamp": 0, "coords": {"x": 1.0, "y": 1.0}}]}]
    before = sim_random.sim_rng.getstate()
    ST.apply_screen_targeting(anims, None, {"steps": steps},
                              {"PF": _P("o_PF"), "SG": _P("o_SG")}, {"PF": _P("d_PF")})
    assert sim_random.sim_rng.getstate() == before


# ---------------------------------------------------------------------------
# the contest itself
# ---------------------------------------------------------------------------


def test_weights_sum_to_one_the_house_contract():
    """A composite multiplied by rand(1,6) must be on the 0-100 scale, same as
    BOXOUT_SCORE_WEIGHTS and calculate_rebound_score."""
    for w in (SC.NAVIGATE_WEIGHTS, SC.SCREEN_HOLD_WEIGHTS, SC.SWITCH_WEIGHTS):
        assert sum(w.values()) == pytest.approx(1.0)


def test_it_uses_sim_rng_and_the_house_d6(monkeypatch):
    """Not the global module — shared.calculate_screen_score draws globally and that is a
    defect, not a pattern. And the die stays a d6."""
    seen = []

    class _R:
        def randint(self, a, b):
            seen.append((a, b))
            return 3

    SC.resolve_screen_contest(_P(), _P(ST=99), _P(), rng=_R())
    assert seen and all(x == (1, 6) for x in seen), seen
    from BackEnd.utils import sim_random
    st = sim_random.sim_rng.getstate()
    SC.resolve_screen_contest(_P(), _P(), _P())
    assert sim_random.sim_rng.getstate() != st, "default rng must be sim_rng"
    assert random.getstate() == random.getstate()


def test_a_dominant_defender_fights_through_and_a_dominant_screener_does_not():
    strong_d = _P(AG=99, ST=99, IQ=99, ND=99)
    weak_s = _P(ST=1, IQ=1, CH=1)
    out = [SC.resolve_screen_contest(strong_d, weak_s, _P())["outcome"] for _ in range(300)]
    assert set(out) == {SC.FIGHT_THROUGH}
    weak_d = _P(AG=1, ST=1, IQ=1, ND=1)
    strong_s = _P(ST=99, IQ=99, CH=99)
    out = [SC.resolve_screen_contest(weak_d, strong_s, _P())["outcome"] for _ in range(300)]
    assert SC.FIGHT_THROUGH not in out


def test_a_tie_goes_to_the_defender():
    """The stable non-RNG tiebreak, same as resolve_boxout: 'nobody wins the leverage'
    means the assignment does not change hands."""
    class _R:
        def randint(self, a, b):
            return 4
    # identical composites, identical rolls -> navigate == hold
    r = SC.resolve_screen_contest(_P(AG=50, ST=50, IQ=50, ND=50),
                                  _P(ST=50, IQ=50, CH=50), _P(), rng=_R())
    assert r["navigate"] == r["hold"]
    assert r["outcome"] == SC.FIGHT_THROUGH


def test_all_three_outcomes_are_reachable():
    """If an outcome cannot happen the model has two branches and a dead one."""
    seen = set()
    for _ in range(4000):
        seen.add(SC.resolve_screen_contest(_P(), _P(), _P())["outcome"])
        if len(seen) == 3:
            break
    assert seen == {SC.FIGHT_THROUGH, SC.GO_AROUND, SC.SWITCH}


def test_draw_count_is_branch_determined():
    """Two rolls on a fight-through, four otherwise — fixed per branch, so the stream
    stays reproducible."""
    class _Count:
        def __init__(self, vals):
            self.vals, self.n = list(vals), 0

        def randint(self, a, b):
            self.n += 1
            return self.vals.pop(0)

    c = _Count([6, 1])           # defender rolls high -> fight through
    SC.resolve_screen_contest(_P(), _P(), _P(), rng=c)
    assert c.n == 2
    c = _Count([1, 6, 3, 3])     # defender rolls low -> switch/go-around branch
    SC.resolve_screen_contest(_P(), _P(), _P(), rng=c)
    assert c.n == 4


# ---------------------------------------------------------------------------
# the override layer
# ---------------------------------------------------------------------------


def test_a_switch_never_mutates_the_stored_map():
    """man_defense_matchups is the USER'S setting and is persisted with the save
    (shared.py:3294). A switch that wrote into it would rewrite what they chose."""
    gs = {MM.USER_MATCHUPS_KEY: MM.get_default_matchups(),
          MM.COMPUTER_MATCHUPS_KEY: MM.get_default_matchups()}
    stored = dict(gs[MM.USER_MATCHUPS_KEY])
    MM.set_matchup_override(gs, {"PG": "SG", "SG": "PG", "SF": "SF", "PF": "PF", "C": "C"})
    assert gs[MM.USER_MATCHUPS_KEY] == stored
    assert MM.get_matchups_for_defending_team(gs, True)["PG"] == "SG"


def test_the_override_reaches_the_reverse_lookup_too():
    """get_defender_position_for_man_defense has a backward-compat branch that used to
    read the raw key — the ONE site the override could have missed."""
    gs = {MM.USER_MATCHUPS_KEY: MM.get_default_matchups()}
    MM.set_matchup_override(gs, {"PG": "SG", "SG": "PG", "SF": "SF", "PF": "PF", "C": "C"})
    assert MM.get_defender_position_for_man_defense("SG", gs) == "PG"
    assert MM.get_defender_position_for_man_defense("SG", gs, defending_team_is_user=True) == "PG"


def test_an_override_that_would_break_one_to_one_is_discarded():
    """Two defenders on one man and nobody on another is worse than no switch at all."""
    gs = {MM.USER_MATCHUPS_KEY: MM.get_default_matchups()}
    MM.set_matchup_override(gs, {"PG": "SG"})          # SG now guarded twice
    assert MM.get_matchups_for_defending_team(gs, True) == MM.get_default_matchups()


def test_the_override_clears_at_a_break_and_is_idempotent():
    gs = {}
    MM.set_matchup_override(gs, {"PG": "SG", "SG": "PG", "SF": "SF", "PF": "PF", "C": "C"})
    MM.reset_matchups_to_defaults(gs)
    assert MM.get_matchup_override(gs) == {}
    MM.clear_matchup_override(gs)
    assert MM.get_matchup_override(gs) == {}


def test_the_override_clears_on_the_live_possession_flip():
    """A switch lasts the possession, never past it."""
    from BackEnd.models.game_manager import GameManager
    import types
    gm = types.SimpleNamespace(
        game_state={}, offense_team=types.SimpleNamespace(name="A"),
        defense_team=types.SimpleNamespace(name="B"),
        reset_frontcourt_state=lambda: None)
    MM.set_matchup_override(gm.game_state,
                            {"PG": "SG", "SG": "PG", "SF": "SF", "PF": "PF", "C": "C"})
    GameManager.switch_possession(gm)
    assert MM.get_matchup_override(gm.game_state) == {}


def test_stored_copy_is_defensive():
    gs = {}
    mine = {"PG": "SG", "SG": "PG", "SF": "SF", "PF": "PF", "C": "C"}
    MM.set_matchup_override(gs, mine)
    mine["PG"] = "C"
    assert MM.get_matchups_for_defending_team(gs, True)["PG"] == "SG"
