import BackEnd.main as main
from BackEnd.utils import db_utils
from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player


def fake_simulate_macro_turn(self):
    # End the quarter immediately
    self.game_state["time_remaining"] = 0


def fake_build_lineup(team, game_state=None):
    """Return a simple deterministic lineup for tests.

    Constructs new :class:`Player` objects each call without relying on any
    database state, allowing the simulation to proceed with minimal data.
    """
    name = team.name if hasattr(team, "name") else str(team)
    positions = ["PG", "SG", "SF", "PF", "C"]
    lineup = {}
    for i, pos in enumerate(positions):
        pdata = {
            "_id": f"{name}_{i}",
            "first_name": f"{name}{i}",
            "last_name": pos,
            "team": name,
            "attributes": {},
        }
        lineup[pos] = Player(pdata)
    return lineup


def test_simulate_quarter_advances_game(monkeypatch):
    monkeypatch.setattr(GameManager, "simulate_macro_turn", fake_simulate_macro_turn)
    monkeypatch.setattr(main, "build_lineup_from_mongo", fake_build_lineup)

    gm = GameManager("Lancaster", "Bentley-Truman")
    gm.home_team.lineup = fake_build_lineup(gm.home_team)
    gm.away_team.lineup = fake_build_lineup(gm.away_team)

    main.simulate_quarter(gm)
    assert gm.quarter == 2
    assert gm.game_state["time_remaining"] == 0

    # add fouls to ensure reset
    gm.home_team.team_fouls = 3
    gm.away_team.team_fouls = 4

    main.simulate_quarter(gm)
    assert gm.quarter == 3
    assert gm.game_state["team_fouls"][gm.home_team.name] == 0
    assert gm.game_state["team_fouls"][gm.away_team.name] == 0


def test_simulate_quarter_autofills_missing_positions(monkeypatch):
    """Lineups missing positions are automatically completed from the roster."""

    def fake_load_roster(team_name, **_kwargs):
        players = []
        for i, pos in enumerate(["PG", "SG", "SF", "PF", "C"]):
            players.append(
                {
                    "_id": f"{team_name}_{i}",
                    "first_name": f"{team_name}{i}",
                    "last_name": pos,
                    "team": team_name,
                    "attributes": {},
                }
            )
        return {"name": team_name}, players

    def roster_build_lineup(team, game_state=None):
        roster = list(team.players.values())
        positions = ["PG", "SG", "SF", "PF", "C"]
        return {pos: roster[i] for i, pos in enumerate(positions)}

    monkeypatch.setattr(GameManager, "simulate_macro_turn", fake_simulate_macro_turn)
    monkeypatch.setattr("BackEnd.models.team_manager.load_roster", fake_load_roster)
    monkeypatch.setattr(main, "build_lineup_from_mongo", roster_build_lineup)

    gm = GameManager("Lancaster", "Bentley-Truman")

    partial_home = {
        "PG": "Lancaster_0",
        "SG": "Lancaster_1",
        "SF": "Lancaster_2",
        "PF": "Lancaster_3",
    }

    main.simulate_quarter(gm, home_lineup_ids=partial_home)

    assert set(gm.home_team.lineup.keys()) == set(["PG", "SG", "SF", "PF", "C"])
    assert gm.home_team.lineup["PG"].player_id == "Lancaster_0"
    assert gm.home_team.lineup["C"].player_id == "Lancaster_4"


def test_full_sim_rebuilds_both_absent_lineups_but_never_autosets_user(monkeypatch):
    monkeypatch.setattr(GameManager, "simulate_macro_turn", fake_simulate_macro_turn)
    gm = GameManager("Lancaster", "Bentley-Truman")
    gm.home_team.lineup = fake_build_lineup(gm.home_team)
    gm.away_team.lineup = fake_build_lineup(gm.away_team)
    gm.home_team.is_user_team = True
    gm.away_team.is_user_team = False
    built = []
    autoset = []

    def tracked_build(team, game_state):
        built.append(team.name)
        return dict(team.lineup)

    monkeypatch.setattr(main, "build_lineup_from_mongo", tracked_build)
    monkeypatch.setattr(db_utils, "autoset_strategy_settings", lambda team, _state: autoset.append(team.name))

    main.simulate_quarter(gm, turn_by_turn_mode=False)

    assert built == [gm.home_team.name, gm.away_team.name]
    assert autoset == [gm.away_team.name]


def test_full_sim_explicit_lineup_ids_win_per_team(monkeypatch):
    monkeypatch.setattr(GameManager, "simulate_macro_turn", fake_simulate_macro_turn)
    gm = GameManager("Lancaster", "Bentley-Truman")
    gm.home_team.lineup = fake_build_lineup(gm.home_team)
    gm.away_team.lineup = fake_build_lineup(gm.away_team)
    explicit_home = {
        pos: player.player_id for pos, player in gm.home_team.lineup.items()
    }
    built = []

    def tracked_build(team, game_state):
        built.append(team.name)
        return dict(team.lineup)

    monkeypatch.setattr(main, "build_lineup_from_mongo", tracked_build)
    monkeypatch.setattr(db_utils, "autoset_strategy_settings", lambda *_args: None)

    main.simulate_quarter(
        gm,
        home_lineup_ids=explicit_home,
        turn_by_turn_mode=False,
    )

    assert built == [gm.away_team.name]
    assert {
        pos: player.player_id for pos, player in gm.home_team.lineup.items()
    } == explicit_home


def test_turn_by_turn_without_checkpoint_preserves_both_lineups_byte_for_byte(monkeypatch):
    gm = GameManager("Lancaster", "Bentley-Truman")
    gm.home_team.lineup = fake_build_lineup(gm.home_team)
    gm.away_team.lineup = fake_build_lineup(gm.away_team)
    before = {
        "home": {pos: player.player_id for pos, player in gm.home_team.lineup.items()},
        "away": {pos: player.player_id for pos, player in gm.away_team.lineup.items()},
    }

    def forbidden_build(*_args, **_kwargs):
        raise AssertionError("turn-by-turn unexpectedly rebuilt a lineup")

    monkeypatch.setattr(main, "build_lineup_from_mongo", forbidden_build)
    main.simulate_quarter(gm, turn_by_turn_mode=True)
    after = {
        "home": {pos: player.player_id for pos, player in gm.home_team.lineup.items()},
        "away": {pos: player.player_id for pos, player in gm.away_team.lineup.items()},
    }

    assert after == before
