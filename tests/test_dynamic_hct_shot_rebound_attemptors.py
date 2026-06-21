from BackEnd.engine.dynamic_hct_shot import (
    _finalize_ab_shot,
    resolve_hct_fast_break_shot,
)
from BackEnd.models.shot_manager import ShotManager
from tests.test_utils import build_mock_game


def _sync_ids_and_rosters(game):
    for team in (game.home_team, game.away_team):
        for pos, player in team.lineup.items():
            if player.player_id is None:
                player.player_id = f"{team.name}-{pos}"
        team.players = {
            player.player_id: player
            for player in team.lineup.values()
        }
        team.scouting_data = {"defense": {"HCT": {"used": 0, "success": 0}}}


def _force_clean_miss(monkeypatch):
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
        return -100, -100, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calculate)


def test_hct_fast_break_miss_stamps_near_bounce_attemptors_from_shot_seed(monkeypatch):
    game = build_mock_game()
    _sync_ids_and_rosters(game)
    game.game_state["offensive_state"] = "HCT"
    game.offense_team.team_attributes["shot_threshold"] = 100
    _force_clean_miss(monkeypatch)
    monkeypatch.setattr(
        "BackEnd.utils.shared.calculate_bounce_spot",
        lambda *args, **kwargs: {"x": 89, "y": 25},
    )
    monkeypatch.setattr("BackEnd.utils.shared.random.random", lambda: 0.99)
    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    near_off = game.offense_team.lineup["SG"]
    far_off = game.offense_team.lineup["SF"]
    near_def = game.defense_team.lineup["SG"]
    actual_rebounder = game.offense_team.lineup["SG"]
    near_off.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})
    far_off.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})
    near_def.attributes.update({"RB": 1, "ST": 1, "IQ": 1, "CH": 1})
    monkeypatch.setattr(
        "BackEnd.utils.fast_break_shot_geometry.compute_fb_shot_geometry",
        lambda **kwargs: {
            "shooter_target": {"x": 60, "y": 25},
            "defender_target": {"x": 90, "y": 25},
            "defender_end_coords": {},
            "first_arriver_id": None,
            "contested": True,
            "shot_defender_id": near_def.player_id,
            "t_shooter_game_seconds": 1.0,
        },
    )

    # Deliberately stale runtime coords: the resolver should use the HCT seed
    # only during rebound selection/attemptor collection, then restore these.
    near_off.coords = {"x": 5, "y": 5}
    far_off.coords = {"x": 6, "y": 6}
    near_def.coords = {"x": 7, "y": 7}

    dyn = {
        "fb_seed": {
            "shooter_pos": "PG",
            "off_coords": {
                "PG": {"x": 75, "y": 25},
                "SG": {"x": 80, "y": 25},  # actual rebounder
                "SF": {"x": 60, "y": 25},  # 29 away: excluded
                "PF": {"x": 45, "y": 35},
                "C": {"x": 45, "y": 15},
            },
            "def_coords": {
                "PG": {"x": 55, "y": 20},
                "SG": {"x": 89, "y": 45},  # 20 away: included
                "SF": {"x": 55, "y": 30},
                "PF": {"x": 50, "y": 25},
                "C": {"x": 60, "y": 25},   # would be closest def without filter fallback
            },
        }
    }

    result = resolve_hct_fast_break_shot(game, dyn)

    assert result["result_type"] == "MISS"
    assert result["rebounderId"] == actual_rebounder.player_id
    assert near_off.player_id not in result["offense_rebounders"]
    assert far_off.player_id not in result["offense_rebounders"]
    assert near_def.player_id in result["defense_rebounders"]
    assert actual_rebounder.player_id not in result["offense_rebounders"]
    assert near_off.coords == {"x": 5, "y": 5}


def test_hct_attack_basket_miss_stamps_near_bounce_attemptors_from_shot_coords(monkeypatch):
    game = build_mock_game()
    _sync_ids_and_rosters(game)
    game.game_state["offensive_state"] = "HCT"
    game.offense_team.team_attributes["shot_threshold"] = 100
    monkeypatch.setattr(
        "BackEnd.utils.shared.calculate_bounce_spot",
        lambda *args, **kwargs: {"x": 89, "y": 25},
    )
    monkeypatch.setattr("BackEnd.utils.shared.random.random", lambda: 0.99)

    shooter = game.offense_team.lineup["PG"]
    near_off = game.offense_team.lineup["SG"]
    far_off = game.offense_team.lineup["SF"]
    near_def = game.defense_team.lineup["SG"]
    actual_rebounder = game.offense_team.lineup["SG"]
    near_off.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})
    far_off.attributes.update({"RB": 100, "ST": 100, "IQ": 100, "CH": 100})
    near_def.attributes.update({"RB": 1, "ST": 1, "IQ": 1, "CH": 1})
    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    original_near_off_coords = {"x": 10, "y": 10}
    original_rebounder_coords = dict(original_near_off_coords)
    near_off.coords = dict(original_near_off_coords)

    shot_moment_coords = {
        shooter.player_id: {"x": 87, "y": 25},
        near_off.player_id: {"x": 80, "y": 25},  # actual rebounder
        far_off.player_id: {"x": 60, "y": 25},   # 29 away: excluded
    }
    defender_end_coords = {
        near_def.player_id: {"x": 89, "y": 45},       # 20 away: included
        game.defense_team.lineup["C"].player_id: {"x": 60, "y": 25},
    }

    result = _finalize_ab_shot(
        game,
        shooter=shooter,
        shooter_id=shooter.player_id,
        shot_defender=None,
        shot_defender_id=None,
        contested=False,
        shot_type="attack",
        shot_spot={"x": 60, "y": 25},
        made=False,
        shot_score=-100,
        shot_score_pre_defense=-100,
        shot_defense_score_for_sfx=0,
        d_foul=False,
        foul_player=None,
        defender_end_coords=defender_end_coords,
        t_shot=0.8,
        shot_moment_coords=shot_moment_coords,
        extra_seed={"hct_ab_mode": "shoot"},
    )

    assert result["result_type"] == "MISS"
    assert result["rebounderId"] == actual_rebounder.player_id
    assert near_off.player_id not in result["offense_rebounders"]
    assert far_off.player_id not in result["offense_rebounders"]
    assert near_def.player_id in result["defense_rebounders"]
    assert actual_rebounder.player_id not in result["offense_rebounders"]
    assert near_off.coords == original_near_off_coords
