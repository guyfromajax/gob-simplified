"""URI database name and id-to-name box comparison for the integrity checker."""

import pytest

from scripts.check_season_stats_integrity import (
    _Store,
    check,
    database_name_from_uri,
    resolve_mongo_database,
)


def test_database_name_comes_from_the_uri_path():
    assert database_name_from_uri("mongodb://localhost:27017/gob-live") == "gob-live"
    assert database_name_from_uri(
        "mongodb+srv://user:pass@cluster.example.net/alpha?retryWrites=true"
    ) == "alpha"
    assert database_name_from_uri("mongodb://localhost:27017") is None
    assert database_name_from_uri("mongodb://localhost:27017/") is None
    assert resolve_mongo_database(None, "mongodb://localhost:27017/from-uri") == "from-uri"
    assert resolve_mongo_database("explicit", "mongodb://localhost:27017/other") == "explicit"
    with pytest.raises(SystemExit, match="database name"):
        resolve_mongo_database(None, "mongodb://localhost:27017")
    with pytest.raises(SystemExit, match="database name"):
        resolve_mongo_database(None, None)


class _Mem(_Store):
    def __init__(self, rows):
        self._rows = rows

    def rows(self, collection):
        return self._rows.get(collection, [])

    def franchises(self):
        return self.rows("franchises")


def test_object_ids_resolve_to_names_before_the_box_comparison(capsys):
    lancaster = "69a6fcb68d2c56aa82e48a54"
    casino = "69a6fcb68d2c56aa82e48a5f"
    appalachia = "69a6fcb68d2c56aa82e48a5e"
    teams = [
        ("oid:" + lancaster, {"_id": lancaster, "name": "Lancaster", "team_id": "LANCASTER"}),
        ("oid:" + casino, {"_id": casino, "name": "Casino Row", "team_id": "CASINO_ROW"}),
        ("oid:" + appalachia, {"_id": appalachia, "name": "Appalachia", "team_id": "APPALACHIA"}),
    ]
    same_teams = {
        "franchise_id": "f1",
        "week": 1,
        "team1_id": "Lancaster",
        "team2_id": "Casino Row",
        "teams": {
            lancaster: {"box_score": {"p": {"playerId": "p1"}}},
            casino: {"box_score": {"q": {"playerId": "p2"}}},
        },
    }
    different_teams = {
        "franchise_id": "f1",
        "week": 2,
        "team1_id": appalachia,
        "team2_id": lancaster,
        "teams": {
            "Casino Row": {"box_score": {"p": {"playerId": "p1"}}},
            "Lancaster": {"box_score": {"q": {"playerId": "p2"}}},
        },
    }
    store = _Mem({
        "teams": teams,
        "games": [("g-same", same_teams), ("g-diff", different_teams)],
        "franchises": [],
        "franchise_players_data": [],
    })
    check(store, None, "gob-live")
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "database gob-live"
    disagreements = [line for line in lines if line.startswith("box/matchup")]
    assert len(disagreements) == 1
    assert "Casino Row" in disagreements[0]
    assert "Appalachia" in disagreements[0]
    assert lines[-1].startswith("SUMMARY ")
