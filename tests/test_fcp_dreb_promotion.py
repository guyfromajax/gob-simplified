from tests.test_utils import build_mock_game


def _seed_player_ids_and_coords(game):
    for team in (game.home_team, game.away_team):
        for idx, (pos, player) in enumerate((team.lineup or {}).items()):
            player.player_id = f"{team.name}_{pos}"
            player.coords = {"x": 45.0, "y": 10.0 + (5.0 * idx)}
            player.stats["game"].setdefault("MIN", 0)


def _coord_map(game):
    out = {}
    for team in (game.home_team, game.away_team):
        for player in (team.lineup or {}).values():
            out[str(player.player_id)] = dict(player.coords)
    return out


def _miss_with_loose_ball(game, *, current_turn, next_play_type, rebounder, shooter, defender):
    end_coords = _coord_map(game)
    bounce = {"x": 11.0, "y": 31.0}
    return {
        "current_turn": current_turn,
        "result_type": "MISS",
        "text": "Missed jumper.",
        "offense_team_id": game.offense_team.team_id,
        "time_elapsed": 6,
        "possession_flips": True,
        "next_play_type": next_play_type,
        "rebound_type": "DREB",
        "rebounderId": rebounder.player_id,
        "ball_bounce_x": bounce["x"],
        "ball_bounce_y": bounce["y"],
        "skeleton": {"steps": []},
        "animations": [],
        "roles": {
            "ball_handler": shooter,
            "shooter": shooter,
            "defender": defender,
        },
        "animation_steps": [
            {
                "start": {
                    "coords": end_coords,
                    "ball": {"owner_player_id": shooter.player_id},
                    "clock": {
                        "clock_remaining": 480.0,
                        "shot_clock_remaining": 24.0,
                    },
                },
                "end": {
                    "coords": end_coords,
                    "ball": {"coords": bounce},
                    "time_elapsed": 6.0,
                    "clock": {
                        "clock_remaining": 474.0,
                        "shot_clock_remaining": 18.0,
                    },
                    "next": {
                        "kind": "turn_stop",
                        "event": "SHOT_ATTEMPT",
                        "payload": {"result": "MISS"},
                    },
                },
            }
        ],
    }


def _assert_promotes_to_discrete_dreb(game, shot_turn, rebounder, original_next):
    assert shot_turn["next_play_type"] == "DREB"
    assert shot_turn["next_turn"] == "DREB"

    assert len(game.turns) == 2
    dreb_turn = game.turns[-1]
    assert dreb_turn["current_turn"] == "DREB"
    assert dreb_turn["result_type"] == "DREB"
    assert dreb_turn["next_play_type"] == original_next
    assert dreb_turn["next_turn"] == original_next
    assert dreb_turn["rebounderId"] == rebounder.player_id
    assert dreb_turn["final_ball_handler_id"] == rebounder.player_id
    assert dreb_turn["animation_steps"][-1]["end"]["ball"]["owner_player_id"] == rebounder.player_id


def test_fcp_miss_dreb_promotes_to_discrete_dreb_turn(monkeypatch):
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    game.game_state["offensive_state"] = "FCP"
    game.game_state["time_remaining"] = 480
    game.game_state["shot_clock_remaining"] = 24
    game.offense_team = game.home_team
    game.defense_team = game.away_team

    rebounder = game.defense_team.lineup["C"]
    shooter = game.offense_team.lineup["SG"]
    defender = game.defense_team.lineup["SG"]
    fcp_miss = _miss_with_loose_ball(
        game,
        current_turn="FCP",
        next_play_type="FAST_BREAK",
        rebounder=rebounder,
        shooter=shooter,
        defender=defender,
    )

    monkeypatch.setattr(game.turn_manager, "run_micro_turn", lambda: fcp_miss)

    result = game.simulate_macro_turn()

    assert result is fcp_miss
    _assert_promotes_to_discrete_dreb(game, fcp_miss, rebounder, "FAST_BREAK")


def test_emergency_foul_out_reentry_does_not_interrupt_dreb_promotion(monkeypatch):
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    game.game_state["offensive_state"] = "HCO"
    game.game_state["time_remaining"] = 480
    game.game_state["shot_clock_remaining"] = 24
    game.game_state["allow_fouled_out_lineup_reentry"] = True
    game.offense_team = game.home_team
    game.defense_team = game.away_team

    rebounder = game.defense_team.lineup["C"]
    shooter = game.offense_team.lineup["SG"]
    defender = game.defense_team.lineup["SG"]
    for _ in range(5):
        rebounder.record_stat("F")
    game.game_state["emergency_fouled_out_lineup_player_ids"] = [
        rebounder.player_id
    ]
    hco_miss = _miss_with_loose_ball(
        game,
        current_turn="HCO",
        next_play_type="FAST_BREAK",
        rebounder=rebounder,
        shooter=shooter,
        defender=defender,
    )

    monkeypatch.setattr(game.turn_manager, "run_micro_turn", lambda: hco_miss)

    result = game.simulate_macro_turn()

    assert result is hco_miss
    assert result.get("fouled_out") is not True
    _assert_promotes_to_discrete_dreb(game, hco_miss, rebounder, "FAST_BREAK")


def test_after_steal_fast_break_miss_dreb_promotes_to_discrete_dreb_turn(monkeypatch):
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    game.game_state["offensive_state"] = "FAST_BREAK"
    game.game_state["time_remaining"] = 480
    game.game_state["shot_clock_remaining"] = 24
    game.offense_team = game.home_team
    game.defense_team = game.away_team

    rebounder = game.defense_team.lineup["SF"]
    shooter = game.offense_team.lineup["PG"]
    defender = game.defense_team.lineup["PG"]
    after_steal_miss = _miss_with_loose_ball(
        game,
        current_turn="FAST_BREAK",
        next_play_type="HCO",
        rebounder=rebounder,
        shooter=shooter,
        defender=defender,
    )
    after_steal_miss["fast_break_play"] = "after_steal"

    monkeypatch.setattr(game.turn_manager, "run_micro_turn", lambda: after_steal_miss)

    result = game.simulate_macro_turn()

    assert result is after_steal_miss
    _assert_promotes_to_discrete_dreb(game, after_steal_miss, rebounder, "HCO")


def test_hco_miss_dreb_otb_resolves_inside_dreb_turn(monkeypatch):
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    game.game_state["offensive_state"] = "HCO"
    game.game_state["time_remaining"] = 480
    game.game_state["shot_clock_remaining"] = 24
    game.home_team.team_fouls = 0
    game.away_team.team_fouls = 0
    game.offense_team = game.home_team
    game.defense_team = game.away_team

    rebounder = game.defense_team.lineup["SF"]
    shooter = game.offense_team.lineup["PG"]
    defender = game.defense_team.lineup["PG"]
    offender = game.offense_team.lineup["PF"]

    rebounder.coords = {"x": 11.0, "y": 31.0}
    offender.coords = {"x": 12.0, "y": 31.0}
    shooter.coords = {"x": 70.0, "y": 12.0}
    defender.coords = {"x": 68.0, "y": 12.0}

    hco_miss = _miss_with_loose_ball(
        game,
        current_turn="HCO",
        next_play_type="HCO",
        rebounder=rebounder,
        shooter=shooter,
        defender=defender,
    )

    rolls = iter([100, 100, 1])

    def rigged_randint(low, high):
        try:
            return next(rolls)
        except StopIteration:
            return low

    monkeypatch.setattr(game.turn_manager, "run_micro_turn", lambda: hco_miss)
    monkeypatch.setattr("BackEnd.utils.shared.random.randint", rigged_randint)

    result = game.simulate_macro_turn()

    assert result is hco_miss
    assert hco_miss["next_play_type"] == "DREB"
    assert hco_miss["next_turn"] == "DREB"

    assert len(game.turns) == 3
    dreb_foul = game.turns[1]
    assert dreb_foul["current_turn"] == "DREB"
    assert dreb_foul["result_type"] == "FOUL"
    assert dreb_foul["otb_foul"] is True
    assert dreb_foul["foul_team"] == "OFFENSE"
    assert dreb_foul["foul_player_id"] == offender.player_id
    assert dreb_foul["victim_id"] == rebounder.player_id
    assert dreb_foul["rebounderId"] == rebounder.player_id
    assert dreb_foul["final_ball_handler_id"] == rebounder.player_id
    assert dreb_foul["next_play_type"] == "SIDE_INBOUND"
    assert dreb_foul["next_turn"] == "SIDE_INBOUND"

    final_step = dreb_foul["animation_steps"][-1]["end"]
    assert final_step["ball"]["owner_player_id"] == rebounder.player_id
    assert final_step["announcement"]["text"] == "Over The Back!"
    assert final_step["announcement"]["player_data"]["playerId"] == offender.player_id
    assert final_step["next"]["event"] == "FOUL"
    assert final_step["next"]["payload"]["over_the_back"] is True

    side_inbound = game.turns[-1]
    assert side_inbound["current_turn"] == "SIDE_INBOUND"
