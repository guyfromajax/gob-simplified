"""Sim-arm HCO coords come from the placement stamp for all ten players, not the shooter alone.

On a full simulation ``skeleton_to_animations`` returns [], so before this fix only the shooter's
coords moved during an HCO possession. ``_write_sim_hco_placement_coords`` writes all ten from the
``_step_state`` placement the contest already reads. The guard below measures staleness at the shot;
its poison (flag off = shooter-only) must trip the same threshold.
"""

import logging
import math
import random as _stdlib
from types import SimpleNamespace

import pytest

from BackEnd.engine import phase_resolution as PR
from BackEnd.engine.defender_placement import offense_grid_from_animations

POSITIONS = ("PG", "SG", "SF", "PF", "C")


@pytest.fixture(autouse=True)
def _b1a_off(monkeypatch):
    """These guards describe the B1-A-OFF configuration, so pin it.

    ``GOB_SIM_BUILD_ANIM_FOR_EMITTER`` is ON by default since 2026-09-20, which gives the
    sim arm real ``animation_steps`` and leaves this module's subject dormant - the guards
    then measure 0-1 overlay players and correctly refuse to draw a conclusion. Forcing the
    flag off keeps them running against the configuration they are written for (B1-A's kill
    switch), rather than skipping and losing the coverage. No assertion is weakened.
    """
    monkeypatch.setenv("GOB_SIM_BUILD_ANIM_FOR_EMITTER", "0")


def _lineup(prefix, x0):
    return {
        pos: SimpleNamespace(player_id=f"{prefix}{i}", coords={"x": x0, "y": 25})
        for i, pos in enumerate(POSITIONS)
    }


def _stamped_skeleton(off, dfn, *, stopper=False):
    rows_off = {pos: {"x": 60 + i, "y": 10 + i} for i, pos in enumerate(POSITIONS)}
    rows_def = {pos: {"x": 70 + i, "y": 20 + i} for i, pos in enumerate(POSITIONS)}
    steps = [
        {"timestamp": 0, "_step_state": {"index": 0, "defense": {}, "offense": {}}},
        {"timestamp": 1000, "_step_state": {"index": 1, "defense": rows_def, "offense": rows_off}},
    ]
    if stopper:  # appended after stamping, as apply_stopper_system_to_skeleton does
        steps.append({"timestamp": 1300, "pos_actions": {}, "events": [{"type": "steal"}]})
    return {"steps": steps}, rows_off, rows_def


def _game(full_sim=True):
    return SimpleNamespace(game_state={"_is_full_simulation": full_sim, "game_id": "t"})


def test_writes_all_ten_from_stamp(monkeypatch, caplog):
    monkeypatch.setenv("GOB_SIM_HCO_COORD_WRITE", "1")
    off, dfn = _lineup("o", 10), _lineup("d", 10)
    skeleton, rows_off, rows_def = _stamped_skeleton(off, dfn)
    caplog.set_level(logging.INFO)
    assert PR._write_sim_hco_placement_coords(_game(), skeleton, off, dfn, "HCO shot") == 10
    for pos in POSITIONS:
        assert off[pos].coords == {"x": float(rows_off[pos]["x"]), "y": float(rows_off[pos]["y"])}
        assert dfn[pos].coords == {"x": float(rows_def[pos]["x"]), "y": float(rows_def[pos]["y"])}
    assert any("[SIM HCO COORDS] HCO shot: wrote 10 players" in r.getMessage() for r in caplog.records)


def test_stopper_step_uses_last_complete_stamp(monkeypatch):
    monkeypatch.setenv("GOB_SIM_HCO_COORD_WRITE", "1")
    off, dfn = _lineup("o", 10), _lineup("d", 10)
    skeleton, rows_off, _ = _stamped_skeleton(off, dfn, stopper=True)
    assert PR._write_sim_hco_placement_coords(_game(), skeleton, off, dfn, "HCO stopper") == 10
    assert off["C"].coords == {"x": float(rows_off["C"]["x"]), "y": float(rows_off["C"]["y"])}


@pytest.mark.parametrize("full_sim, flag", [(False, "1"), (True, "0")])
def test_no_write_on_played_or_when_disabled(monkeypatch, full_sim, flag):
    monkeypatch.setenv("GOB_SIM_HCO_COORD_WRITE", flag)
    off, dfn = _lineup("o", 10), _lineup("d", 10)
    skeleton, _, _ = _stamped_skeleton(off, dfn)
    assert PR._write_sim_hco_placement_coords(_game(full_sim), skeleton, off, dfn, "HCO shot") == 0
    assert all(p.coords == {"x": 10, "y": 25} for p in list(off.values()) + list(dfn.values()))


def test_missing_stamp_announces_and_writes_nothing(monkeypatch, caplog):
    monkeypatch.setenv("GOB_SIM_HCO_COORD_WRITE", "1")
    off, dfn = _lineup("o", 10), _lineup("d", 10)
    caplog.set_level(logging.WARNING)
    skeleton = {"steps": [{"timestamp": 0, "_step_state": {"defense": {}}}]}
    assert PR._write_sim_hco_placement_coords(_game(), skeleton, off, dfn, "HCO shot") == 0
    assert any("no step with a complete placement stamp" in r.getMessage() for r in caplog.records)


def test_offense_grid_carries_last_entry_forward():
    lineup = {"PG": SimpleNamespace(player_id="p"), "SG": SimpleNamespace(player_id="s")}
    anims = [
        {"playerId": "p", "movement": [{"timestamp": 0, "coords": {"x": 1, "y": 1}},
                                       {"timestamp": 2000, "coords": {"x": 3, "y": 3}}]},
        {"playerId": "s", "movement": [{"timestamp": 1000, "coords": {"x": 5, "y": 5}}]},
    ]
    steps = [{"timestamp": 0}, {"timestamp": 1000}, {"timestamp": 2000}]
    grid = offense_grid_from_animations(anims, lineup, steps)
    assert grid[0] == {"PG": {"x": 1.0, "y": 1.0}}
    assert grid[1] == {"PG": {"x": 1.0, "y": 1.0}, "SG": {"x": 5.0, "y": 5.0}}
    assert grid[2] == {"PG": {"x": 3.0, "y": 3.0}, "SG": {"x": 5.0, "y": 5.0}}


# --- Guard: staleness at the shot on a real simulated quarter -------------------------------------

STALE_LIMIT = 2.0  # grid units; measured ~26 shooter-only, 0 with the write


def _simmed_quarter_staleness(monkeypatch, flag):
    from BackEnd.db import defenses_collection, players_collection, plays_collection, teams_collection
    from BackEnd.main import simulate_quarter
    from BackEnd.models.game_manager import GameManager
    from BackEnd.utils import sim_random, training_random
    from tests.roster_fixtures import seed_universal_defenses, seed_universal_plays, seed_universal_rosters

    monkeypatch.setenv("GOB_SIM_HCO_COORD_WRITE", flag)
    seed_universal_rosters(teams_collection, players_collection)
    seed_universal_plays(plays_collection)
    seed_universal_defenses(defenses_collection)

    gaps = []
    freeze = PR._freeze_hco_shot_attempt_geometry

    def measured(game, skeleton, roles, *, emitted_sync_succeeded):
        if game.game_state.get("_is_full_simulation"):
            steps = (skeleton or {}).get("steps") or []
            stamp = ((steps[-1].get("_step_state") or {}).get("defense") or {}) if steps else {}
            for pos, player in (game.defense_team.lineup or {}).items():
                c = stamp.get(pos)
                if player is not None and c:
                    gaps.append(math.hypot(player.coords["x"] - c["x"], player.coords["y"] - c["y"]))
        return freeze(game, skeleton, roles, emitted_sync_succeeded=emitted_sync_succeeded)

    monkeypatch.setattr(PR, "_freeze_hco_shot_attempt_geometry", measured)
    sim_random.seed(8000)
    training_random.seed(8000)
    _stdlib.seed(8000)
    gm = GameManager("Lancaster", "Bentley-Truman")
    settings = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = dict(settings)
    gm.away_team.strategy_settings = dict(settings)
    simulate_quarter(gm, game_id="%024x" % 0xE0000)
    assert len(gaps) > 50, "the guard measured too few defender samples to mean anything"
    return sum(gaps) / len(gaps)


def test_guard_sim_defenders_are_fresh_at_the_shot(monkeypatch):
    assert _simmed_quarter_staleness(monkeypatch, "1") < STALE_LIMIT


def test_guard_poison_shooter_only_trips_the_threshold(monkeypatch):
    """Poison: the pre-fix shooter-only behaviour. The guard above must fail against it."""
    assert _simmed_quarter_staleness(monkeypatch, "0") >= STALE_LIMIT
