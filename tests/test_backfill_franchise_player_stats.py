from BackEnd.db import db
from BackEnd.utils.stat_updater import backfill_franchise_player_stats


def setup_function(_fn):
    db.franchises.delete_many({})


def test_backfill_franchise_player_stats_transforms_document():
    fid = db.franchises.insert_one(
        {
            "players": {
                "p1": {
                    "meta": {"first_name": "A", "last_name": "One", "team": "Team1"},
                    "season": {"PTS": 10, "FGA": 5, "FGM": 4, "STL": -1, "GP": 1},
                    "career": {"PTS": 20, "FGA": 10, "FGM": 8, "GP": 2},
                }
            },
            "applied_games": ["g1"],
        }
    ).inserted_id

    backfill_franchise_player_stats(str(fid))
    doc = db.franchises.find_one({"_id": fid}) or {}

    assert "players" not in doc
    assert "applied_games" not in doc
    assert doc.get("processed_games") == ["g1"]

    p1 = doc.get("player_stats", {}).get("p1", {})
    assert p1.get("first_name") == "A"
    assert p1.get("season", {}).get("PTS") == 10
    assert "STL" not in p1.get("season", {})
    assert p1.get("season", {}).get("per_game", {}).get("PTS") == 10
    assert p1.get("season", {}).get("percentages", {}).get("FG%") == 80.0
