"""Sim-arm post-shot crash parity: overlay players advance toward the destinations played renders.

Played reaches those positions through the emitted [shoot] / [ball_flight] / [rattle] / [bounce]
sub-steps; a full simulation emits none for the HCO family, so ``apply_sim_crash_destinations``
performs the same interruption arithmetically. The guard below measures the overlay position error
against that arithmetic on a real simulated quarter; its poison (flag off) must trip the threshold.
"""

import logging
import math
import random as _stdlib
from types import SimpleNamespace

import pytest

from BackEnd.utils import shared as SH
from BackEnd.utils.animation_step_helpers import _ag_grid_per_game_sec

POSITIONS = ("PG", "SG", "SF", "PF", "C")
HOME_ID, AWAY_ID = "home-1", "away-1"


def _player(pid, x=50.0, y=25.0, ag=50):
    return SimpleNamespace(player_id=pid, coords={"x": x, "y": y}, attributes={"AG": ag})


def _game(full_sim=True):
    home = SimpleNamespace(team_id=HOME_ID, lineup={p: _player(f"h{i}") for i, p in enumerate(POSITIONS)})
    away = SimpleNamespace(team_id=AWAY_ID, lineup={p: _player(f"a{i}") for i, p in enumerate(POSITIONS)})
    return SimpleNamespace(home_team=home, away_team=away,
                           game_state={"_is_full_simulation": full_sim, "game_id": "t"})


def _turn(result_type="MISS", current_turn="HCO", **extra):
    tr = {
        "result_type": result_type,
        "current_turn": current_turn,
        "offense_team_id": HOME_ID,
        "shooter_id": "h0",
        "shot_spot": {"x": 80.0, "y": 25.0},
        "shot_variant": "CLEAN",
        "ball_bounce_x": 88.0,
        "ball_bounce_y": 25.0,
        "offense_rebounder_coords": {"h1": {"x": 88.0, "y": 22.0}},
        "defense_rebounder_coords": {"a1": {"x": 89.0, "y": 27.0}},
    }
    tr.update(extra)
    return tr


def _positions(game):
    out = {}
    for team in (game.home_team, game.away_team):
        for p in team.lineup.values():
            out[str(p.player_id)] = dict(p.coords)
    return out


def test_advances_overlay_players_toward_their_destination(monkeypatch, caplog):
    monkeypatch.setenv("GOB_SIM_CRASH_APPLY", "1")
    game, tr = _game(), _turn()
    pos = _positions(game)
    caplog.set_level(logging.INFO)
    moved = SH.apply_sim_crash_destinations(game, tr, pos)
    assert moved == 2
    for pid, dest in (("h1", (88.0, 22.0)), ("a1", (89.0, 27.0))):
        start, end = (50.0, 25.0), (pos[pid]["x"], pos[pid]["y"])
        assert math.dist(end, dest) < math.dist(start, dest), f"{pid} did not move toward its destination"
    assert any("[SIM CRASH]" in r.getMessage() for r in caplog.records)


def test_matches_a_single_interruption_over_the_window(monkeypatch):
    monkeypatch.setenv("GOB_SIM_CRASH_APPLY", "1")
    game, tr = _game(), _turn()
    pos = _positions(game)
    seconds = SH.sim_post_shot_window_seconds(tr, away_offense=False, shot_spot=tr["shot_spot"])
    SH.apply_sim_crash_destinations(game, tr, pos)
    from BackEnd.engine.skeleton_step_emitter import _interpolate_step_end

    rate = _ag_grid_per_game_sec(game.home_team.lineup["SG"], "standard")
    want, _ = _interpolate_step_end({"x": 50.0, "y": 25.0}, {"x": 88.0, "y": 22.0}, rate, seconds)
    assert pos["h1"] == pytest.approx({"x": want["x"], "y": want["y"]})


@pytest.mark.parametrize("branch, turn", [
    ("MAKE", _turn("MAKE")),
    ("shooting foul on a miss", _turn("MISS", is_shooting_foul=True)),
    ("defensive foul on a miss", _turn("MISS", foul_on_defense=True)),
    ("fast-break miss", _turn("MISS", current_turn="FAST_BREAK", fast_break=True)),
    ("HCO miss", _turn("MISS")),
])
def test_fires_for_every_authoring_branch(monkeypatch, branch, turn):
    monkeypatch.setenv("GOB_SIM_CRASH_APPLY", "1")
    game = _game()
    pos = _positions(game)
    assert SH.apply_sim_crash_destinations(game, turn, pos) == 2, f"writer did not fire for {branch}"


@pytest.mark.parametrize("kwargs, why", [
    ({"animation_steps": [{"end": {"coords": {}}}]}, "schema steps already carry the positions"),
    ({"animations": [{"playerId": "h1"}]}, "legacy animations already carry them (played)"),
])
def test_skips_a_turn_that_already_rendered(monkeypatch, kwargs, why):
    monkeypatch.setenv("GOB_SIM_CRASH_APPLY", "1")
    game, tr = _game(), _turn(**kwargs)
    pos = _positions(game)
    assert SH.apply_sim_crash_destinations(game, tr, pos) == 0, why
    assert pos["h1"] == {"x": 50.0, "y": 25.0}


@pytest.mark.parametrize("full_sim, flag", [(False, "1"), (True, "0")])
def test_no_write_on_played_or_when_disabled(monkeypatch, full_sim, flag):
    monkeypatch.setenv("GOB_SIM_CRASH_APPLY", flag)
    game, tr = _game(full_sim), _turn()
    pos = _positions(game)
    assert SH.apply_sim_crash_destinations(game, tr, pos) == 0
    assert pos["h1"] == {"x": 50.0, "y": 25.0}


def test_window_is_none_for_a_non_shot_turn():
    assert SH.sim_post_shot_window_seconds(_turn("STEAL"), False, {"x": 80.0, "y": 25.0}) is None
    assert SH.sim_post_shot_window_seconds(_turn(), False, None) is None


def test_apply_consumes_no_rng(monkeypatch):
    """The hard stop: the writer is arithmetic. It must not touch sim_rng."""
    monkeypatch.setenv("GOB_SIM_CRASH_APPLY", "1")
    from BackEnd.utils import sim_random

    calls = []
    for name in ("random", "getrandbits", "randint", "choice", "uniform"):
        orig = getattr(sim_random.sim_rng, name)
        monkeypatch.setattr(sim_random.sim_rng, name,
                            lambda *a, _n=name, _o=orig, **k: (calls.append(_n), _o(*a, **k))[1])
    game, tr = _game(), _turn()
    SH.apply_sim_crash_destinations(game, tr, _positions(game))
    assert calls == []


# --- Guard: overlay position error on a real simulated quarter -------------------------------------

ERROR_LIMIT = 1.0  # grid units; ~0 with the write, ~13 with it off


def _simmed_quarter_overlay_error(monkeypatch, flag):
    from BackEnd.db import defenses_collection, players_collection, plays_collection, teams_collection
    from BackEnd.main import simulate_quarter
    from BackEnd.models.game_manager import GameManager
    from BackEnd.engine.skeleton_step_emitter import _OVERLAY_ARCHETYPES, _interpolate_step_end
    from BackEnd.utils import sim_random, training_random
    from tests.roster_fixtures import seed_universal_defenses, seed_universal_plays, seed_universal_rosters

    monkeypatch.setenv("GOB_SIM_CRASH_APPLY", flag)
    monkeypatch.setenv("GOB_SIM_CRASH_CLOCK", "0")
    seed_universal_rosters(teams_collection, players_collection)
    seed_universal_plays(plays_collection)
    seed_universal_defenses(defenses_collection)

    errors = []
    real_sync = SH.sync_lineup_coords_from_turn

    def measured(game, turn_result):
        maps = [(k, a, turn_result.get(k)) for k, a in _OVERLAY_ARCHETYPES]
        rendered = bool(turn_result.get("animation_steps") or turn_result.get("animations"))
        by_id, before = {}, {}
        for team in (game.home_team, game.away_team):
            for p in (team.lineup or {}).values():
                if p is not None:
                    by_id[str(p.player_id)] = p
                    before[str(p.player_id)] = dict(p.coords)
        want = {}
        if not rendered and game.game_state.get("_is_full_simulation"):
            away = str(turn_result.get("offense_team_id") or "") == str(game.away_team.team_id)
            spot = turn_result.get("shot_spot")
            secs = SH.sim_post_shot_window_seconds(turn_result, away, spot)
            if secs:
                for _k, arch, overlay in maps:
                    for pid, dest in (overlay or {}).items():
                        pid = str(pid)
                        if pid in by_id and isinstance(dest, dict) and dest.get("x") is not None:
                            rate = _ag_grid_per_game_sec(by_id[pid], arch)
                            end, _d = _interpolate_step_end(before[pid], dest, rate, secs)
                            want[pid] = end
        real_sync(game, turn_result)
        for pid, target in want.items():
            got = by_id[pid].coords
            errors.append(math.dist((got["x"], got["y"]), (target["x"], target["y"])))

    monkeypatch.setattr(SH, "sync_lineup_coords_from_turn", measured)
    from BackEnd.models import game_manager as GMM
    monkeypatch.setattr(GMM, "sync_lineup_coords_from_turn", measured)

    sim_random.seed(8000)
    training_random.seed(8000)
    _stdlib.seed(8000)
    gm = GameManager("Lancaster", "Bentley-Truman")
    settings = {"defense": 2, "tempo": 2, "aggression": 2, "fast_break": 2, "hc_trap": 5, "fc_press": 5}
    gm.home_team.strategy_settings = dict(settings)
    gm.away_team.strategy_settings = dict(settings)
    simulate_quarter(gm, game_id="%024x" % 0xE0000)
    assert len(errors) > 50, "the guard measured too few overlay players to mean anything"
    return sum(errors) / len(errors)


def test_guard_sim_overlay_players_reach_the_predicted_positions(monkeypatch):
    assert _simmed_quarter_overlay_error(monkeypatch, "1") < ERROR_LIMIT


def test_guard_poison_flag_off_trips_the_threshold(monkeypatch):
    """Poison: with the writer off, the same measure must fail the guard above."""
    assert _simmed_quarter_overlay_error(monkeypatch, "0") >= ERROR_LIMIT
