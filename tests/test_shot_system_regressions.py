from types import SimpleNamespace

from BackEnd.constants import POSITION_LIST
from BackEnd.models.shot_manager import ShotManager
from BackEnd.utils.shared import _resolve_oreb_putback_defender
from tests.test_utils import MockPlayer


def _build_stub_team(name: str, team_id: str) -> SimpleNamespace:
    template = {
        "first_name": "Test",
        "last_name": "Player",
        "SC": 5,
        "SH": 5,
        "ID": 8,
        "OD": 3,
        "PS": 8,
        "BH": 9,
        "RB": 1,
        "AG": 4,
        "ST": 9,
        "ND": 3,
        "IQ": 5,
        "FT": 4,
        "CH": 5,
        "height": 78,
        "NG": 1.0,
    }
    lineup = {}
    for pos in POSITION_LIST:
        player = MockPlayer(
            {
                **template,
                "first_name": name,
                "last_name": pos,
                "team": name,
                "player_id": f"{team_id}_{pos}",
            }
        )
        player.coords = {"x": 50, "y": 25}
        lineup[pos] = player

    return SimpleNamespace(
        name=name,
        team_id=team_id,
        lineup=lineup,
        strategy_settings={"rebounding": 2, "fast_breaks": 2, "aggression": 2},
        team_attributes={
            "shot_threshold": 0,
            "momentum": 0,
            "fight": 0,
            "team_chemistry": 10,
            "offensive_efficiency": 0,
            "defensive_efficiency": 0,
            "fb_efficiency": 0,
            "pt_efficiency": 0,
            "fb_opp_modifier": 0,
            "pt_opp_modifier": 0,
        },
        points_by_quarter=[],
        team_fouls=0,
        team_stats={},
        playbook_settings={},
        is_user_team=False,
    )


def _build_stub_game():
    home_team = _build_stub_team("Home", "HOME")
    away_team = _build_stub_team("Away", "AWAY")
    game = SimpleNamespace()
    game.home_team = home_team
    game.away_team = away_team
    game.offense_team = home_team
    game.defense_team = away_team
    game.game_id = "test-game"
    game.game_state = {
        "current_playcall": "Base",
        "defense_playcall": "Man",
        "offensive_state": "HCO",
        "quarter": 1,
        "no_defender_shots": 0,
        "no_defender_shots_breakdown": {},
    }
    game.score = {home_team.name: 0, away_team.name: 0}
    game.turn_manager = SimpleNamespace(determine_defensive_pressure_type=lambda: "HCO")
    return game


def test_hco_assignment_overrides_geometry_for_defender_presence(monkeypatch):
    game = _build_stub_game()
    shot_manager = ShotManager(game)

    shooter = game.offense_team.lineup["PG"]
    assigned_defender = game.defense_team.lineup["PG"]

    game.game_state["offensive_state"] = "HCO"
    game.game_state["current_playcall"] = "Base"
    game.game_state["defense_playcall"] = "Man"

    roles = {
        "shooter": shooter,
        "passer": game.offense_team.lineup["SG"],
        "screener": game.offense_team.lineup["SF"],
        "shot_spot": {"x": 14, "y": 32},
    }

    shooter.coords = {"x": 14, "y": 32}
    assigned_defender.coords = {"x": 90, "y": 22}
    for pos, player in game.defense_team.lineup.items():
        if pos != "PG":
            player.coords = {"x": 88, "y": 24}

    captured = {}

    def fake_calculate(
        self,
        shooter,
        passer,
        screener,
        defender,
        shot_type,
        defense_call,
        is_three,
        is_paint=False,
        second_defender=None,
        shooter_location=None,
        apply_defense=True,
        **kwargs,
    ):
        captured["defender"] = defender
        captured["apply_defense"] = apply_defense
        return 0, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calculate)

    result = shot_manager.resolve_shot(roles)

    assert result["result_type"] in {"MAKE", "MISS"}
    assert captured["defender"] is assigned_defender
    assert captured["apply_defense"] is True
    assert game.game_state["no_defender_shots"] == 0


def test_fast_break_no_defender_path_does_not_crash(monkeypatch):
    game = _build_stub_game()
    shot_manager = ShotManager(game)

    shooter = game.offense_team.lineup["PG"]
    shooter.coords = {"x": 87, "y": 24}
    for player in game.defense_team.lineup.values():
        player.coords = {"x": 43, "y": 23}

    game.game_state["offensive_state"] = "FAST_BREAK"
    game.offense_team.team_attributes["shot_threshold"] = 100

    roles = {
        "shooter": shooter,
        "passer": game.offense_team.lineup["SG"],
        "is_fast_break": True,
    }

    def fake_calculate(
        self,
        shooter,
        passer,
        screener,
        defender,
        shot_type,
        defense_call,
        is_three,
        is_paint=False,
        second_defender=None,
        shooter_location=None,
        apply_defense=True,
        **kwargs,
    ):
        return 0, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calculate)

    result = shot_manager.resolve_shot(roles)

    assert result["result_type"] in {"MAKE", "MISS"}
    assert game.game_state["no_defender_shots"] == 1


def test_oreb_putback_uses_nearest_defender_without_distance_gate():
    game = _build_stub_game()
    rebounder = game.offense_team.lineup["PF"]
    rebounder.coords = {"x": 90, "y": 25}

    game.defense_team.lineup["PG"].coords = {"x": 40, "y": 25}
    game.defense_team.lineup["SG"].coords = {"x": 75, "y": 25}
    game.defense_team.lineup["SF"].coords = {"x": 83, "y": 29}
    game.defense_team.lineup["PF"].coords = {"x": 70, "y": 10}
    game.defense_team.lineup["C"].coords = {"x": 60, "y": 25}

    defender, has_shot_defender = _resolve_oreb_putback_defender(
        game,
        rebounder,
        game.defense_team.lineup,
        basket_x=91,
    )

    assert has_shot_defender is True
    assert defender is game.defense_team.lineup["SF"]
