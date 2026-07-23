from types import SimpleNamespace

from BackEnd.constants import POSITION_LIST
from BackEnd.models.shot_manager import ShotManager
from BackEnd.utils.shared import _resolve_oreb_putback_defender
from BackEnd.models.shot_manager import (
    _inside_shot_threshold_bonus,
    _shot_distance_threshold_bump,
)


def test_shot_distance_threshold_bump_applies_only_to_threes():
    assert _shot_distance_threshold_bump(0, is_three=False) == 0
    assert _shot_distance_threshold_bump(25, is_three=False) == 0
    assert _shot_distance_threshold_bump(0, is_three=True) == 0
    assert _shot_distance_threshold_bump(25, is_three=True) == 50


def test_inside_shot_threshold_bonus_uses_contiguous_distance_bands():
    assert _inside_shot_threshold_bonus(12, is_three=False) == -40
    assert _inside_shot_threshold_bonus(12.01, is_three=False) == -20
    assert _inside_shot_threshold_bonus(13, is_three=False) == -20
    assert _inside_shot_threshold_bonus(19, is_three=False) == -20
    assert _inside_shot_threshold_bonus(19.01, is_three=False) == 0
    assert _inside_shot_threshold_bonus(5, is_three=True) == 0
from BackEnd.utils.shot_geometry import is_three_point_shot_from_coords
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
        "shot_spot": {"x": 80, "y": 32},
    }

    shooter.coords = {"x": 80, "y": 32}
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
        return 0, 0, 0, False, None

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
        return 0, 0, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calculate)

    result = shot_manager.resolve_shot(roles)

    assert result["result_type"] in {"MAKE", "MISS"}
    assert game.game_state["no_defender_shots"] == 1


def test_three_point_geometry_matches_home_and_away_arc():
    assert is_three_point_shot_from_coords({"x": 64, "y": 25}, is_away_offense=False)
    assert is_three_point_shot_from_coords({"x": 36, "y": 25}, is_away_offense=True)
    assert not is_three_point_shot_from_coords({"x": 80, "y": 25}, is_away_offense=False)
    assert not is_three_point_shot_from_coords({"x": 20, "y": 25}, is_away_offense=True)


def test_shot_manager_prefers_shot_spot_geometry_over_skeleton_name():
    game = _build_stub_game()
    shot_manager = ShotManager(game)
    shooter = game.offense_team.lineup["PG"]

    roles = {
        "shooter": shooter,
        "shot_spot": {"x": 64, "y": 25},
        "steps": [
            {
                "pos_actions": {
                    "PG": {"action": "shoot", "location": "basketSpot"},
                }
            }
        ],
    }

    assert shot_manager.is_three_point_shot(shooter, roles) is True


def test_fast_break_outside_branch_can_classify_as_three(monkeypatch):
    game = _build_stub_game()
    shot_manager = ShotManager(game)
    shooter = game.offense_team.lineup["PG"]
    game.game_state["offensive_state"] = "FAST_BREAK"
    game.offense_team.team_attributes["shot_threshold"] = 100

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
        captured["is_three"] = is_three
        captured["is_paint"] = is_paint
        return 999, 999, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calculate)

    result = shot_manager.resolve_shot(
        {
            "shooter": shooter,
            "passer": game.offense_team.lineup["SG"],
            "defender": None,
            "is_fast_break": True,
            "shot_type": "outside",
            "motion_playcall": "Outside",
            "shot_spot": {"x": 64, "y": 25},
        }
    )

    assert result["result_type"] == "MAKE"
    assert captured["is_three"] is True
    assert captured["is_paint"] is False
    assert shooter.get_stat("3PTA") == 1
    assert shooter.get_stat("3PTM") == 1


def test_regular_fast_break_miss_uses_25_grid_rebound_geo_filter(monkeypatch):
    game = _build_stub_game()
    shot_manager = ShotManager(game)
    game.game_state["offensive_state"] = "FAST_BREAK"
    game.offense_team.team_attributes["shot_threshold"] = 1000
    game.offense_team.team_attributes["rebound_modifier"] = 0
    game.defense_team.team_attributes["rebound_modifier"] = 0

    shooter = game.offense_team.lineup["PG"]
    near_off = game.offense_team.lineup["SG"]
    far_off = game.offense_team.lineup["SF"]
    near_def = game.defense_team.lineup["SG"]

    shooter.coords = {"x": 60, "y": 25}
    near_off.coords = {"x": 65, "y": 25}  # 24 from bounce: eligible
    far_off.coords = {"x": 63, "y": 25}   # 26 from bounce: excluded
    near_off.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})
    far_off.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})
    for pos, player in game.offense_team.lineup.items():
        if player not in (shooter, near_off, far_off):
            player.coords = {"x": 60, "y": 25}
    near_def.coords = {"x": 89, "y": 50}  # 25 from bounce: animation attemptor
    near_def.attributes.update({"RB": 1, "ST": 1, "IQ": 1, "CH": 1})
    for pos, player in game.defense_team.lineup.items():
        if player is not near_def:
            player.coords = {"x": 63, "y": 25}  # frontcourt, outside 25
            player.attributes.update({"RB": 1, "ST": 1, "IQ": 1, "CH": 1})

    roles = {
        "shooter": shooter,
        "passer": game.offense_team.lineup["C"],
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
        return 0, 0, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calculate)
    monkeypatch.setattr(
        "BackEnd.models.shot_manager.calculate_bounce_spot",
        lambda *args, **kwargs: {"x": 89, "y": 25},
    )
    monkeypatch.setattr("BackEnd.models.shot_manager.random.random", lambda: 0.99)
    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    result = shot_manager.resolve_shot(roles)

    assert result["result_type"] == "MISS"
    assert result["rebound_type"] == "OREB"
    assert result["rebounderId"] == near_off.player_id
    assert near_off.player_id not in result["offense_rebounders"]
    assert far_off.player_id not in result["offense_rebounders"]
    assert near_def.player_id in result["defense_rebounders"]


def test_regular_fast_break_rebound_falls_back_when_frontcourt_x_filter_empty(monkeypatch):
    game = _build_stub_game()
    shot_manager = ShotManager(game)
    game.game_state["offensive_state"] = "FAST_BREAK"
    game.offense_team.team_attributes["shot_threshold"] = 1000
    game.offense_team.team_attributes["rebound_modifier"] = 0
    game.defense_team.team_attributes["rebound_modifier"] = 0

    shooter = game.offense_team.lineup["PG"]
    fallback_rebounder = game.defense_team.lineup["C"]

    # Home offense fast-break rebound prefilter wants x >= 50. Force every
    # active player to the other half so only the full-lineup fallback can
    # recover a legal rebounder.
    for player in list(game.offense_team.lineup.values()) + list(game.defense_team.lineup.values()):
        player.coords = {"x": 10, "y": 25}
        player.attributes.update({"RB": 1, "ST": 1, "IQ": 1, "CH": 1})
    fallback_rebounder.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})

    roles = {
        "shooter": shooter,
        "passer": game.offense_team.lineup["C"],
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
        return 0, 0, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calculate)
    monkeypatch.setattr(
        "BackEnd.models.shot_manager.calculate_bounce_spot",
        lambda *args, **kwargs: {"x": 89, "y": 25},
    )
    monkeypatch.setattr("BackEnd.models.shot_manager.random.random", lambda: 0.99)
    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    result = shot_manager.resolve_shot(roles)

    assert result["result_type"] == "MISS"
    assert result["rebounderId"] == fallback_rebounder.player_id
    assert result["rebound_type"] == "DREB"


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
