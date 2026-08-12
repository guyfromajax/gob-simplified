from BackEnd.models.franchise_manager import FranchiseManager
from BackEnd.db import db, players_collection


def setup_db():
    db.games.delete_many({})
    db.teams.delete_many({})
    players_collection.delete_many({})
    db.franchises.delete_many({})
    # Canonical league: 16 conferences of eight, grouped two per region.
    teams = [
        {
            "_id": f"T{i}",
            "name": f"Team{i}",
            "record": {"W": 0, "L": 0},
            "PF": 0,
            "PA": 0,
            "conference": (i % 16) + 1,
            "region": chr(ord("A") + ((i % 16) // 2)),
            "prestige": 500,
        }
        for i in range(128)
    ]
    db.teams.insert_many(teams)


def test_initialize_season_does_not_reset_universal_player_buckets():
    setup_db()
    players_collection.insert_one(
        {
            "_id": "p1",
            "team_id": "T0",
            "team": "Team0",
            "stats": {
                "game": {"PTS": 5},
                "season": {"PTS": 10},
                "career": {"PTS": 20},
                "applied_games": ["old"]
            },
        }
    )
    manager = FranchiseManager(db)
    manager.initialize_season()
    p1 = players_collection.find_one({"_id": "p1"})
    # Franchise state is isolated in FPD/FTD. Starting a franchise must never
    # erase the shared catalog player's legacy/universal stat fields.
    assert p1["stats"]["game"] == {"PTS": 5}
    assert p1["stats"]["season"] == {"PTS": 10}
    assert p1["stats"]["career"] == {"PTS": 20}
    assert p1["stats"]["applied_games"] == ["old"]


def test_unscoped_simulated_game_does_not_write_universal_player_stats(monkeypatch):
    setup_db()
    players_collection.insert_many(
        [
            {
                "_id": "p1",
                "team_id": "T0",
                "team": "Team0",
                "first_name": "A",
                "last_name": "One",
                "stats": {"game": {}, "season": {}, "career": {}, "applied_games": []},
            },
            {
                "_id": "p2",
                "team_id": "T1",
                "team": "Team1",
                "first_name": "B",
                "last_name": "Two",
                "stats": {"game": {}, "season": {}, "career": {}, "applied_games": []},
            },
        ]
    )
    manager = FranchiseManager(db)
    manager.reset_stats()

    def fake_run_simulation(home, away):
        class GM:
            def __init__(self, h, a):
                self.score = {h: 80, a: 70}
        return GM(home, away)

    def fake_summary(game):
        return {
            "home_team": "Team1",
            "away_team": "Team0",
            "box_score": {
                "Team1": {"PG": {"name": "B Two", "PTS": 12}},
                "Team0": {"PG": {"name": "A One", "PTS": 7}},
            },
            "players": [
                {"playerId": "p2", "team": "home", "pos": "PG"},
                {"playerId": "p1", "team": "away", "pos": "PG"},
            ],
        }

    monkeypatch.setattr("BackEnd.models.franchise_manager.run_simulation", fake_run_simulation)
    monkeypatch.setattr("BackEnd.models.franchise_manager.summarize_game_state", fake_summary)

    manager.simulate_game("T0", "T1")

    p1 = players_collection.find_one({"_id": "p1"})
    p2 = players_collection.find_one({"_id": "p2"})
    # Franchise accumulation requires a franchise_id and is persisted through
    # finalize_game into FPD. This legacy unscoped helper must not write the
    # universal player catalog.
    assert p1["stats"]["season"] == {}
    assert p1["stats"]["career"] == {}
    assert p2["stats"]["season"] == {}
    assert p2["stats"]["career"] == {}
    assert p1["stats"]["game"] == {}
    assert p2["stats"]["game"] == {}
