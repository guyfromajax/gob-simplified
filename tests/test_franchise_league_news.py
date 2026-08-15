from types import SimpleNamespace

import mongomock
from bson import ObjectId

from BackEnd.utils import franchise_league_news as news


def _fixture(monkeypatch, *, week=4):
    client = mongomock.MongoClient()
    mongo = client.test
    teams = []
    ftd = mongo.franchise_team_data
    fpd = mongo.franchise_players_data
    franchise_id = ObjectId()
    for index in range(128):
        team_id = ObjectId()
        teams.append(
            {
                "_id": team_id,
                "team_id": f"team_{index:03d}",
                "name": f"Team {index:03d}",
                "conference": index // 8 + 1,
            }
        )
        ftd.insert_one({"franchise_id": franchise_id, "team_id": team_id, "natl_rank": index + 1})
    mongo.teams.insert_many(teams)
    for index in range(12):
        team = teams[index]
        fpd.insert_one(
            {
                "franchise_id": str(franchise_id),
                "player_id": f"player_{index}",
                "meta": {
                    "first_name": "Player",
                    "last_name": str(index),
                    "team_id": str(team["_id"]),
                },
                "season": {
                    "GP": 3,
                    "PTS": 90 - index,
                    "REB": 50 - index,
                    "AST": 40 - index,
                    "STL": 20 - index,
                    "BLK": 15 - index,
                    "3PTM": 12 - index,
                    "FGM": 30 - index,
                    "FGA": 30,
                    "DEF_S": 20 - index,
                    "DEF_A": 24,
                },
            }
        )
    names = {str(team["_id"]): team["name"] for team in teams}
    monkeypatch.setattr(news, "db", SimpleNamespace(teams=mongo.teams))
    monkeypatch.setattr(news, "franchise_team_data_collection", ftd)
    monkeypatch.setattr(news, "franchise_players_data_collection", fpd)
    monkeypatch.setattr(news, "resolve_team_name_map", lambda _doc, _ids: names)
    monkeypatch.setattr(
        news,
        "calculate_franchise_standings",
        lambda _results, team_map: {team_id: {"W": 3, "L": 0} for team_id in team_map},
    )
    pairs = [[str(teams[i]["_id"]), str(teams[i + 64]["_id"])] for i in range(64)]
    return {
        "_id": franchise_id,
        "week": week,
        "current_season": 2,
        "schedule": [pairs for _ in range(26)],
        "results": {},
    }


def test_in_season_payload_uses_completed_week_for_results_and_current_week_for_games(monkeypatch):
    payload = news.build_franchise_league_news(_fixture(monkeypatch, week=4))

    assert payload["phase"] == "in_season"
    assert payload["season"] == 2
    assert payload["week"] == 3
    assert payload["completed_week"] == 3
    assert payload["current_week"] == 4
    assert len(payload["top10"]) == 10
    assert len(payload["key_games"]) == 10
    assert set(payload["leaders"]) == {spec[0] for spec in news.LEADER_SPECS}
    assert all(len(rows) == 10 for rows in payload["leaders"].values())
    assert payload["leaders"]["pts"][0]["value"] == 30.0
    assert payload["leaders"]["pts"][0]["display"] == "30.0"
    assert payload["leaders"]["treb"][0]["display"] == "16.7"
    assert payload["leaders"]["ast"][0]["display"] == "13.3"


def test_preseason_top10_omits_trailing_record(monkeypatch):
    payload = news.build_franchise_league_news(_fixture(monkeypatch, week=1))

    assert payload["phase"] == "preseason"
    assert len(payload["preseason"]["top10"]) == 10
    assert len(payload["preseason"]["marquee"]) == 10
    assert all("wins" not in row and "losses" not in row for row in payload["preseason"]["top10"])
