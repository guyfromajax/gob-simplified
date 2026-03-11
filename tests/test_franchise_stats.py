from BackEnd.models.franchise_manager import FranchiseManager
from BackEnd.db import db, players_collection


def setup_db():
    db.games.delete_many({})
    db.teams.delete_many({})
    players_collection.delete_many({})
    # Conference 1 required so ScheduleManager gets exactly 8 teams for round-robin
    teams = [
        {"_id": f"T{i}", "name": f"Team{i}", "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0, "conference": 1}
        for i in range(8)
    ]
    db.teams.insert_many(teams)


def test_initialize_season_zeros_buckets():
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
    assert p1["stats"]["game"] == {}
    assert p1["stats"]["season"] == {}
    assert p1["stats"]["career"] == {}
    assert p1["stats"]["applied_games"] == []


def test_simulated_game_accumulates_stats(monkeypatch):
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
    assert p1["stats"]["season"]["PTS"] == 7
    assert p1["stats"]["career"]["PTS"] == 7
    assert p2["stats"]["season"]["PTS"] == 12
    assert p2["stats"]["career"]["PTS"] == 12
    assert p1["stats"]["game"].get("PTS") == 0
    assert p2["stats"]["game"].get("PTS") == 0
