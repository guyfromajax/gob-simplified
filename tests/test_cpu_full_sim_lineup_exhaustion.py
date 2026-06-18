import pytest

import BackEnd.main as main
from BackEnd.utils import db_utils
from BackEnd.engine.phase_resolution import check_and_handle_foul_out
from BackEnd.models.player import Player
from BackEnd.models.team_manager import TeamManager
from BackEnd.models.game_manager import GameManager


class _Team(TeamManager):
    def __init__(self, players, lineup, *, is_user_team=False):
        self.name = "Lineup Exhaustion Test"
        self.players = {player.player_id: player for player in players}
        self.lineup = lineup
        self.team_attributes = {"team_chemistry": 15}
        self.is_user_team = is_user_team

    def get_all_players(self):
        return self.players.values()


def _player(index, fouls):
    player = Player(
        {
            "_id": f"player-{index}",
            "first_name": "Player",
            "last_name": str(index),
            "team": "Lineup Exhaustion Test",
            "attributes": {"NG": 0.0},
        }
    )
    for _ in range(fouls):
        player.record_stat("F")
    return player


def _exhausted_team(*, is_user_team=False):
    active = [_player(index, 0) for index in range(4)]
    fouled_out = [_player(index, 5) for index in range(4, 12)]
    lineup = {
        "PG": active[0],
        "SG": active[1],
        "SF": None,
        "PF": active[2],
        "C": active[3],
    }
    return _Team(
        active + fouled_out,
        lineup,
        is_user_team=is_user_team,
    ), fouled_out


def test_cpu_full_sim_randomly_readmits_fouled_out_player(monkeypatch):
    team, fouled_out = _exhausted_team()
    selected = fouled_out[-1]
    monkeypatch.setattr(main.random, "sample", lambda population, count: [selected])
    game_state = {
        "quarter": 4,
        "time_remaining": 46,
        "allow_fouled_out_lineup_reentry": True,
    }

    main._ensure_complete_lineup(
        team,
        game_state,
    )

    assert all(team.lineup.get(pos) is not None for pos in main.POSITION_LIST)
    assert team.lineup["SF"] is selected
    assert team.lineup["SF"].get_stat("F", "game") == 5
    assert game_state["emergency_fouled_out_lineup_player_ids"] == [
        selected.player_id
    ]


def test_build_lineup_from_mongo_readmits_fouled_out_player_when_enabled(monkeypatch):
    team, fouled_out = _exhausted_team()
    selected = fouled_out[-1]
    monkeypatch.setattr(db_utils.random, "sample", lambda population, count: [selected])
    game_state = {
        "quarter": 4,
        "time_remaining": 46,
        "allow_fouled_out_lineup_reentry": True,
    }

    lineup = db_utils.build_lineup_from_mongo(team, game_state)

    assert len(lineup) == 5
    assert selected in lineup.values()
    assert selected.get_stat("F", "game") == 5
    assert game_state["emergency_fouled_out_lineup_player_ids"] == [
        selected.player_id
    ]


def test_emergency_readmitted_player_remains_after_additional_foul(monkeypatch):
    team, fouled_out = _exhausted_team()
    selected = fouled_out[-1]
    game_state = {
        "quarter": 4,
        "time_remaining": 46,
        "allow_fouled_out_lineup_reentry": True,
    }
    monkeypatch.setattr(main.random, "sample", lambda population, count: [selected])
    main._ensure_complete_lineup(team, game_state)
    selected.record_stat("F")

    result = check_and_handle_foul_out(selected, game_state, team)

    assert result["fouled_out"] is False
    assert result["foul_count"] == 6
    assert team.lineup["SF"] is selected


def test_computer_team_in_user_game_randomly_readmits_fouled_out_player(monkeypatch):
    team, fouled_out = _exhausted_team()
    selected = fouled_out[0]
    monkeypatch.setattr(main.random, "sample", lambda population, count: [selected])

    main._ensure_complete_lineup(
        team,
        {"quarter": 4, "time_remaining": 46},
    )

    assert team.lineup["SF"] is selected


def test_cpu_full_sim_uses_normal_player_before_fouled_out_shortfall(monkeypatch):
    active = [_player(index, 0) for index in range(3)]
    low_ng_bench = _player(3, 0)
    fouled_out = [_player(index, 5) for index in range(4, 12)]
    team = _Team(
        active + [low_ng_bench] + fouled_out,
        {
            "PG": active[0],
            "SG": active[1],
            "SF": None,
            "PF": active[2],
            "C": None,
        },
    )
    selected = fouled_out[2]
    sampled_counts = []

    def _sample(population, count):
        sampled_counts.append(count)
        return [selected]

    monkeypatch.setattr(main.random, "sample", _sample)

    main._ensure_complete_lineup(
        team,
        {
            "quarter": 4,
            "time_remaining": 46,
            "allow_fouled_out_lineup_reentry": True,
        },
    )

    replacements = {team.lineup["SF"], team.lineup["C"]}
    assert replacements == {low_ng_bench, selected}
    assert sampled_counts == [1]


def test_user_game_still_rejects_lineup_exhaustion():
    team, _ = _exhausted_team(is_user_team=True)

    with pytest.raises(ValueError, match="even after relaxing NG and foul limits"):
        main._ensure_complete_lineup(
            team,
            {"quarter": 4, "time_remaining": 46},
        )


def test_user_foul_out_transition_can_defer_to_locked_lineup_screen():
    team, _ = _exhausted_team(is_user_team=True)

    main._ensure_complete_lineup(
        team,
        {"quarter": 4, "time_remaining": 46},
        allow_incomplete_user_foul_out_transition=True,
    )

    assert team.lineup["SF"] is None


def test_locked_user_lineup_requires_all_non_fouled_out_players():
    team, fouled_out = _exhausted_team(is_user_team=True)
    gm = object.__new__(GameManager)
    gm.home_team = team
    gm.away_team = _exhausted_team()[0]
    gm.game_state = {}
    selected = {
        "PG": team.lineup["PG"].player_id,
        "SG": team.lineup["SG"].player_id,
        "SF": fouled_out[0].player_id,
        "PF": team.lineup["PF"].player_id,
        "C": team.lineup["C"].player_id,
    }

    main.activate_locked_exhausted_user_lineup(gm, "home", selected)

    assert set(gm.game_state["locked_exhausted_lineup_player_ids"]) == set(selected.values())


def test_locked_user_lineup_rejects_missing_eligible_player():
    team, fouled_out = _exhausted_team(is_user_team=True)
    gm = object.__new__(GameManager)
    gm.home_team = team
    gm.away_team = _exhausted_team()[0]
    gm.game_state = {}
    selected = {
        "PG": team.lineup["PG"].player_id,
        "SG": team.lineup["SG"].player_id,
        "SF": fouled_out[0].player_id,
        "PF": fouled_out[1].player_id,
        "C": team.lineup["C"].player_id,
    }

    with pytest.raises(ValueError, match="include every player"):
        main.activate_locked_exhausted_user_lineup(gm, "home", selected)


def test_locked_reinstated_player_remains_after_additional_foul():
    team, fouled_out = _exhausted_team(is_user_team=True)
    reinstated = fouled_out[0]
    team.lineup["SF"] = reinstated
    game_state = {
        "locked_exhausted_lineup_player_ids": [
            str(player.player_id) for player in team.lineup.values()
        ]
    }
    reinstated.record_stat("F")

    result = check_and_handle_foul_out(reinstated, game_state, team)

    assert result["fouled_out"] is False
    assert team.lineup["SF"] is reinstated
