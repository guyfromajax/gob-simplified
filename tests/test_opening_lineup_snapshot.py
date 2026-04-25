"""Opening lineup snapshot for PGPC (Q1 only, immutable after first set)."""

from types import SimpleNamespace

from BackEnd.constants import POSITION_LIST
from BackEnd.opening_lineup_snapshot import snapshot_opening_lineups_to_game_state


def _game_with_lineups():
    def lineup(prefix):
        return {pos: SimpleNamespace(player_id=f"{prefix}-{pos}") for pos in POSITION_LIST}

    home_team = SimpleNamespace(team_id="team_home", lineup=lineup("H"))
    away_team = SimpleNamespace(team_id="team_away", lineup=lineup("A"))
    return SimpleNamespace(
        quarter=1,
        game_state={},
        home_team=home_team,
        away_team=away_team,
    )


def test_snapshot_q1_records_five_starters_per_team():
    game = _game_with_lineups()
    snapshot_opening_lineups_to_game_state(game)

    ol = game.game_state.get("opening_lineup")
    assert isinstance(ol, dict)
    assert len(ol["team_home"]) == 5
    assert len(ol["team_away"]) == 5
    assert ol["team_home"][0] == "H-PG"


def test_snapshot_not_run_for_ot_quarter():
    game = _game_with_lineups()
    game.quarter = 5
    snapshot_opening_lineups_to_game_state(game)
    assert "opening_lineup" not in game.game_state


def test_snapshot_immutable_second_call():
    game = _game_with_lineups()
    game.game_state["opening_lineup"] = {
        "team_home": ["x1", "x2", "x3", "x4", "x5"],
        "team_away": ["y1", "y2", "y3", "y4", "y5"],
    }
    snapshot_opening_lineups_to_game_state(game)
    assert game.game_state["opening_lineup"]["team_home"][0] == "x1"
