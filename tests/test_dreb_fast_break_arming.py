"""Tests for shared DREB → Fast Break arming (FT / putback / FB-miss)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from BackEnd.constants.fast_break_play_types import COVERT_RELEASE, RIM_RUNNER
from BackEnd.engine import dreb_fast_break_arming as arm


def _player(pid: str, x: float, y: float = 25.0, **attrs):
    p = SimpleNamespace(
        player_id=pid,
        coords={"x": x, "y": y},
        attributes=attrs or {"IQ": 50, "AG": 50},
    )
    return p


def _team(lineup, team_id="T1", fast_breaks=4):
    t = SimpleNamespace(
        team_id=team_id,
        lineup=lineup,
        strategy_settings={"fast_breaks": fast_breaks},
        playbook_settings={"fast_breaks": {COVERT_RELEASE: 100, RIM_RUNNER: 0, "triangle": 0}},
    )
    t.get_player_by_id = lambda pid: next(
        (p for p in lineup.values() if str(getattr(p, "player_id", None)) == str(pid)),
        None,
    )
    return t


def _game(home, away, turns=None):
    gs = {
        "time_remaining": 400,
        "offensive_state": "HCO",
    }
    g = SimpleNamespace(
        game_state=gs,
        home_team=home,
        away_team=away,
        quarter=1,
        turns=turns or [],
        offense_team=home,
        defense_team=away,
    )
    return g


@pytest.fixture(autouse=True)
def _no_force_foul(monkeypatch):
    monkeypatch.setattr(
        "BackEnd.utils.situational_logic.is_situational_active", lambda *_a, **_k: False
    )
    monkeypatch.setattr(
        "BackEnd.utils.situational_logic.is_slow_it_down", lambda *_a, **_k: False
    )
    monkeypatch.setattr(
        "BackEnd.utils.situational_logic.should_force_foul", lambda *_a, **_k: False
    )
    monkeypatch.setattr(
        "BackEnd.utils.situational_logic.slow_it_down_defense_setting",
        lambda gs, team, key, raw: raw,
    )


def test_arm_hco_probability_miss_goes_hco(monkeypatch):
    import random as _rnd

    rebounder = _player("r1", 80)
    # Slider 2 → 50% — force roll above threshold.
    reb_team = _team({"C": rebounder}, fast_breaks=2)
    home = _team({"PG": _player("h1", 50)}, team_id="H")
    game = _game(home, reb_team)
    monkeypatch.setattr(_rnd, "random", lambda: 0.99)
    result = {}
    out = arm.arm_dreb_fast_break(
        game,
        source=arm.SOURCE_FT,
        rebounder=rebounder,
        rebounding_team=reb_team,
        result=result,
        ft_offense_lineup=home.lineup,
        ft_defense_lineup=reb_team.lineup,
    )
    assert out == "HCO"
    assert result["next_play_type"] == "HCO"
    assert game.game_state.get("pending_dreb_fb_play_key") is None


def test_prepare_covert_ft_geo_picks_nearest_center():
    ft_off = {
        "PG": _player("o_near", 52, 25),
        "SG": _player("o_far", 80, 25),
    }
    ft_def = {
        "PG": _player("d_near", 48, 25),
        "C": _player("d_far", 90, 25),
    }
    home = _team(ft_off, team_id="H")
    away = _team(ft_def, team_id="A")
    game = _game(home, away)
    result = {}
    release = arm.prepare_covert_ft_geo(
        game,
        ft_offense_lineup=ft_off,
        ft_defense_lineup=ft_def,
        result=result,
        getback_count=1,
    )
    assert release.player_id == "d_near"
    assert result["defense_release"] == ["d_near"]
    assert result["offense_getback"] == ["o_near"]


def test_prepare_covert_fb_miss_skip_outlet_when_rebounder_nearest_center():
    shooting = {
        "PG": _player("s1", 85, 25),
        "SG": _player("s2", 88, 20),
    }
    # Rebounder is nearest center on rebounding team → skip outlet / dribble
    rebounder = _player("reb", 51, 25)
    rebounding = {
        "C": rebounder,
        "PG": _player("r_pg", 40, 25),
    }
    home = _team(shooting, team_id="H")
    away = _team(rebounding, team_id="A")
    game = _game(home, away)
    result = {}
    release, skip = arm.prepare_covert_fb_miss_geo(
        game,
        shooting_lineup=shooting,
        rebounding_lineup=rebounding,
        rebounder=rebounder,
        is_away_shooting=False,  # home was shooting → new FB rim at x=9
        result=result,
    )
    assert release.player_id == "reb"
    assert skip is True
    assert result.get("skip_outlet_pass") is True


def test_prepare_covert_oreb_carry_from_prior_hco_miss():
    release = _player("rel", 45, 25)
    getback = _player("gb", 55, 25)
    prior = {
        "result_type": "MISS",
        "defense_release": ["rel"],
        "offense_getback": ["gb"],
        "defense_release_coords": {"rel": {"x": 45, "y": 25}},
        "offense_getback_coords": {"gb": {"x": 55, "y": 25}},
    }
    home = _team({"PG": getback}, team_id="H")
    away = _team({"PG": release}, team_id="A")
    away.get_player_by_id = lambda pid: release if str(pid) == "rel" else None
    home.get_player_by_id = lambda pid: getback if str(pid) == "gb" else None
    game = _game(home, away, turns=[prior])
    result = {}
    rp = arm.prepare_covert_oreb_carry(game, result)
    assert rp is release
    assert result["defense_release"] == ["rel"]
    assert result["offense_getback"] == ["gb"]
    assert result["defense_release_coords"]["rel"]["x"] == 45


def test_arm_ft_sets_pending_play_key(monkeypatch):
    import random as _rnd

    monkeypatch.setattr(_rnd, "random", lambda: 0.0)  # always eligible at slider 4
    rebounder = _player("r1", 80)
    reb = _team({"C": rebounder, "PG": _player("d_pg", 50)}, team_id="A", fast_breaks=4)
    home = _team({"PG": _player("o_pg", 52), "SG": _player("o_sg", 80)}, team_id="H")
    game = _game(home, reb)
    result = {}
    out = arm.arm_dreb_fast_break(
        game,
        source=arm.SOURCE_FT,
        rebounder=rebounder,
        rebounding_team=reb,
        result=result,
        ft_offense_lineup=home.lineup,
        ft_defense_lineup=reb.lineup,
        force_play_key=COVERT_RELEASE,
    )
    assert out == "FAST_BREAK"
    assert result["next_play_type"] == "FAST_BREAK"
    assert game.game_state["pending_dreb_fb_play_key"] == COVERT_RELEASE
    assert game.game_state["last_release_player"] is not None
