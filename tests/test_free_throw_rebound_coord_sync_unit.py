from BackEnd.engine.phase_resolution import resolve_free_throw_logic
import BackEnd.engine.phase_resolution as phase_resolution_module
from BackEnd.models.animator import Animator


class _DummyPlayer:
    def __init__(self, player_id, name, team_id, coords):
        self.player_id = player_id
        self.name = name
        self.team_id = team_id
        self.coords = dict(coords)
        self.attributes = {"FT": 1, "CH": 1, "MO": 0}
        self.stats = {"game": {}}

    def record_stat(self, stat_key):
        game_stats = self.stats.setdefault("game", {})
        game_stats[stat_key] = game_stats.get(stat_key, 0) + 1


class _DummyTeam:
    def __init__(self, team_id, name, lineup):
        self.team_id = team_id
        self.name = name
        self.lineup = lineup
        self.strategy_settings = {"fast_breaks": 2}


class _DummyGame:
    def __init__(self):
        self.offense_team = None
        self.defense_team = None
        self.home_team = None
        self.away_team = None
        self.game_state = {}
        self.score = {}


def test_free_throw_miss_rebound_uses_coords_synced_from_ft_animation(monkeypatch):
    offense_pg = _DummyPlayer(
        player_id="off_pg",
        name="Offense PG",
        team_id="home_id",
        coords={"x": 12, "y": 8},
    )
    defense_c = _DummyPlayer(
        player_id="def_c",
        name="Defense C",
        team_id="away_id",
        coords={"x": 95, "y": 42},
    )
    offense_team = _DummyTeam("home_id", "Home", {"PG": offense_pg})
    defense_team = _DummyTeam("away_id", "Away", {"C": defense_c})

    game = _DummyGame()
    game.home_team = offense_team
    game.away_team = defense_team
    game.offense_team = offense_team
    game.defense_team = defense_team
    game.score = {offense_team.name: 0, defense_team.name: 0}
    game.game_state = {
        "offensive_state": "FREE_THROW",
        "shooter": offense_pg,
        "last_ball_handler": offense_pg,
        "free_throws_remaining": 1,
        "one_and_one": False,
        "no_lane": False,
    }

    expected_offense_end = {"x": 74.0, "y": 25.0}
    expected_defense_end = {"x": 89.0, "y": 19.0}
    ft_anims = [
        {
            "playerId": offense_pg.player_id,
            "end": expected_offense_end,
            "movement": [],
        },
        {
            "playerId": defense_c.player_id,
            "end": expected_defense_end,
            "movement": [],
        },
        {
            "playerId": "ball",
            "end": {"x": 91.0, "y": 25.0},
            "movement": [],
        },
    ]

    monkeypatch.setattr(
        Animator,
        "capture_free_throw_animation",
        lambda self, game, shooter, attempts, offense_is_home, no_lane=False: ft_anims,
    )
    monkeypatch.setattr(
        phase_resolution_module,
        "build_free_throw_snapshot",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        phase_resolution_module,
        "attach_position_snapshots",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        phase_resolution_module,
        "get_player_position",
        lambda lineup, player: "PG",
    )
    monkeypatch.setattr(
        phase_resolution_module,
        "effective_ft_miss_to_make_second_chance",
        lambda game, team: 0.0,
    )
    monkeypatch.setattr(
        phase_resolution_module.random,
        "randint",
        lambda a, b: 100 if (a, b) == (1, 100) else 1,
    )
    monkeypatch.setattr(phase_resolution_module.random, "random", lambda: 1.0)

    def _fake_determine_rebounder(game, bounce_spot=None, exclude_player_ids=None, penalize_player_ids=None):
        # Core assertion: rebound selection sees FT-updated coords, not stale pre-FT coords.
        assert offense_pg.coords == expected_offense_end
        assert defense_c.coords == expected_defense_end
        return defense_c, defense_team, "DREB"

    monkeypatch.setattr(
        phase_resolution_module,
        "determine_rebounder",
        _fake_determine_rebounder,
    )

    result = resolve_free_throw_logic(game)
    assert result.get("result_type") == "FREE_THROW"
    assert result.get("rebound_type") == "DREB"
    assert result.get("rebounderId") == defense_c.player_id
