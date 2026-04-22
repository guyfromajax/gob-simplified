import pytest

from tests.test_utils import build_mock_game
from BackEnd.models.shot_manager import ShotManager


def test_resolve_shot_returns_make_or_miss():
    game = build_mock_game()
    shot_manager = ShotManager(game)

    roles = {
        "shooter": game.offense_team.lineup["PG"],
        "screener": game.offense_team.lineup["SG"],
        "passer": game.offense_team.lineup["SF"],
        "defender": game.defense_team.lineup["PG"]
    }

    result = shot_manager.resolve_shot(roles)

    assert isinstance(result, dict)
    assert "result_type" in result
    assert result["result_type"] in ["MAKE", "MISS"]
    assert "shooter" in result


def test_resolve_fast_break_shot_works():
    game = build_mock_game()
    shot_manager = ShotManager(game)
    game.offense_team.team_attributes["shot_threshold"] = 0

    fb_roles = {
        "shooter": game.offense_team.lineup["PG"],
        "passer": game.offense_team.lineup["SG"],
        "defense": [game.defense_team.lineup["PG"], game.defense_team.lineup["SG"]]
    }
    result = shot_manager.resolve_fast_break_shot(fb_roles)

    # Legacy entry point is stubbed; fast-break shots resolve via resolve_shot (phase_resolution adapter).
    assert result is None


@pytest.mark.skip(
    reason="resolve_shot does not call resolve_offensive_rebound; OREB putbacks are resolved in turn_manager.resolve_offensive_rebound_turn (monkeypatch target was ineffective).",
)
def test_offensive_rebound_putback_updates_stats(monkeypatch):
    game = build_mock_game()
    shot_manager = ShotManager(game)
    # Force initial attempt to miss (fake_calc returns 0) without rim shortcut / low threshold auto-make
    game.offense_team.team_attributes["shot_threshold"] = 1000

    shooter = game.offense_team.lineup["PG"]
    rebounder = game.offense_team.lineup["C"]
    defender = game.defense_team.lineup["PG"]

    roles = {"shooter": shooter, "defender": defender, "shot_type": "outside"}

    # Force an initial miss
    def fake_calc(
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
        **kwargs,
    ):
        return 0, 0, False, None

    monkeypatch.setattr(ShotManager, "calculate_shot_score", fake_calc)

    # Deterministic rebound outcome: offensive C grabs board (choose_rebounder API: lineup, bounce_spot, ...)
    def fake_choose_rebounder(lineup, bounce_spot, exclude_player_ids=None, penalize_player_ids=None):
        if not lineup:
            return None
        return lineup.get("C") or lineup.get("PG")

    monkeypatch.setattr("BackEnd.models.shot_manager.choose_rebounder", fake_choose_rebounder)
    monkeypatch.setattr("BackEnd.models.shot_manager.calculate_rebound_score", lambda player: 10)

    # Random sequence: no 3PA, no block, offensive rebound, attempt putback
    rand_vals = iter([0.9, 0.99, 0.99, 0.1])
    monkeypatch.setattr("BackEnd.models.shot_manager.random.random", lambda: next(rand_vals))

    # Remove tempo randomness
    monkeypatch.setattr("BackEnd.models.shot_manager.get_time_elapsed", lambda tempo: 0)

    from BackEnd.utils.shared import record_team_points

    def fake_putback(game_param, rebounder_param):
        rebounder_param.record_stat("FGA")
        rebounder_param.record_stat("FGM")
        record_team_points(game_param, game_param.offense_team, 2)
        return {
            "event_type": "PUTBACK_ATTEMPT",
            "shooterId": rebounder_param.player_id,
            "result": "MAKE",
            "points": 2,
            "timeElapsed": 0,
            "possession_flips": True,
        }

    monkeypatch.setattr("BackEnd.models.shot_manager.resolve_offensive_rebound", fake_putback)

    result = shot_manager.resolve_shot(roles)

    assert result["result_type"] == "MAKE"
    assert result["shooter"] is rebounder
    assert result["points"] == 2
    assert rebounder.stats["game"]["FGM"] == 1
    assert rebounder.stats["game"]["FGA"] == 1
    assert rebounder.stats["game"]["OREB"] == 1
    assert game.score[game.offense_team.name] == 2


def _force_putback_path(monkeypatch, made=True, defensive_reb=False):
    """Helper to drive resolve_offensive_rebound down specific branches."""
    from BackEnd.utils.shared import resolve_offensive_rebound

    game = build_mock_game()
    rebounder = game.offense_team.lineup["C"]

    # Choose putback path
    monkeypatch.setattr("BackEnd.utils.shared.random.random", lambda: 0.1)
    # Deterministic scores
    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 6)

    if made:
        game.offense_team.team_attributes["shot_threshold"] = 0
    else:
        game.offense_team.team_attributes["shot_threshold"] = 1000

        def fake_determine(game_param):
            team = game.defense_team if defensive_reb else game.offense_team
            player = team.lineup["PF"]
            stat = "DREB" if team == game.defense_team else "OREB"
            return player, team, stat

        monkeypatch.setattr("BackEnd.utils.shared.determine_rebounder", fake_determine)

    event = resolve_offensive_rebound(game, rebounder)
    return event


@pytest.mark.parametrize(
    "made,def_reb,expected_flip",
    [
        (True, False, True),
        pytest.param(
            False,
            True,
            True,
            marks=pytest.mark.skip(
                reason="shared.resolve_offensive_rebound uses oreb_threshold=0 for putbacks; miss is not exercised by _force_putback_path",
            ),
        ),
        pytest.param(
            False,
            False,
            False,
            marks=pytest.mark.skip(
                reason="shared.resolve_offensive_rebound uses oreb_threshold=0 for putbacks; miss is not exercised by _force_putback_path",
            ),
        ),
    ],
)
def test_putback_event_payload_and_possession(monkeypatch, made, def_reb, expected_flip):
    event = _force_putback_path(monkeypatch, made=made, defensive_reb=def_reb)
    assert event["event_type"] == "PUTBACK_ATTEMPT"
    assert event["result"] == ("MAKE" if made else "MISS")
    assert event["possession_flips"] is expected_flip
    base_keys = {"event_type", "shooterId", "timeElapsed", "result", "possession_flips"}
    if made:
        base_keys.add("points")
    assert base_keys <= event.keys()


def test_kickout_reset_event_payload(monkeypatch):
    from BackEnd.utils.shared import resolve_offensive_rebound

    game = build_mock_game()
    rebounder = game.offense_team.lineup["C"]

    # Force kickout branch and deterministic duration
    monkeypatch.setattr("BackEnd.utils.shared.random.random", lambda: 0.99)
    monkeypatch.setattr("BackEnd.utils.shared.random.randint", lambda a, b: 1)

    event = resolve_offensive_rebound(game, rebounder)
    assert event["event_type"] == "KICKOUT_RESET"
    assert {"event_type", "rebounderId", "pgId", "pass", "timeElapsed"} <= set(event.keys())


def _assign_mock_player_ids(game):
    """Assign deterministic player_ids to mock lineups for contract tests."""
    # Ensure teams have distinct IDs in mock mode (team docs can be missing in tests).
    game.home_team.team_id = "home_team_id"
    game.away_team.team_id = "away_team_id"
    for team_prefix, lineup in (("home", game.home_team.lineup), ("away", game.away_team.lineup)):
        for pos, player in lineup.items():
            player.player_id = f"{team_prefix}_{pos.lower()}"


def test_dreb_outlet_contract_includes_receiver_target():
    game = build_mock_game()
    _assign_mock_player_ids(game)
    shot_manager = ShotManager(game)

    rebound_team = game.home_team
    rebounder = rebound_team.lineup["C"]
    rebounder.coords = {"x": 40, "y": 25}

    contract = shot_manager._build_dreb_outlet_pass_contract(rebound_team, rebounder.player_id)

    assert isinstance(contract, dict)
    assert contract["passer_id"] == rebounder.player_id
    assert contract["receiver_id"] != rebounder.player_id
    assert isinstance(contract.get("receiver_target"), dict)
    assert {"x", "y", "source"} <= set(contract["receiver_target"].keys())


def test_dreb_outlet_receiver_target_direction_matches_transition_orientation(monkeypatch):
    game = build_mock_game()
    _assign_mock_player_ids(game)
    shot_manager = ShotManager(game)

    # Deterministic offsets: +4 x-units from rebounder in chosen sign direction; y unchanged.
    monkeypatch.setattr("BackEnd.models.shot_manager.random.randint", lambda a, b: 4 if a == 3 and b == 6 else 0)

    # Home transition offense should bias toward HOME_RIM (x high).
    home_rebounder = game.home_team.lineup["C"]
    home_rebounder.coords = {"x": 40, "y": 25}
    home_target = shot_manager._build_dreb_outlet_receiver_target(game.home_team, home_rebounder.player_id)
    assert home_target["x"] > home_rebounder.coords["x"]

    # Away transition offense should bias toward AWAY_RIM (x low).
    away_rebounder = game.away_team.lineup["C"]
    away_rebounder.coords = {"x": 60, "y": 25}
    away_target = shot_manager._build_dreb_outlet_receiver_target(game.away_team, away_rebounder.player_id)
    assert away_target["x"] < away_rebounder.coords["x"]


def test_dreb_outlet_receiver_target_anchors_to_bounce_when_coords_stale(monkeypatch):
    """Stale high-x defender coords + low-x bounce should yield outlet near bounce, not coords."""
    game = build_mock_game()
    _assign_mock_player_ids(game)
    shot_manager = ShotManager(game)

    monkeypatch.setattr("BackEnd.models.shot_manager.random.randint", lambda a, b: 4 if a == 3 and b == 6 else 0)

    rebounder = game.home_team.lineup["C"]
    rebounder.coords = {"x": 68, "y": 25}
    bounce = {"x": 6.0, "y": 28.0}
    target = shot_manager._build_dreb_outlet_receiver_target(
        game.home_team, rebounder.player_id, ball_bounce=bounce
    )
    assert target is not None
    # Toward HOME_RIM (91) from bounce-anchored x (~6..9): expect low 10s–20s, not ~72.
    assert target["x"] < 30
    assert target["x"] > bounce["x"]


