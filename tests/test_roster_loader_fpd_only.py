from types import SimpleNamespace

from bson import ObjectId

from BackEnd.utils import roster_loader


def test_load_from_db_returns_fpd_only_player_when_universal_missing(monkeypatch):
    franchise_id = str(ObjectId())
    team_object_id = ObjectId()
    player_id = "franchise-only-player"

    monkeypatch.setattr(
        roster_loader,
        "teams_collection",
        SimpleNamespace(find_one=lambda query: {"_id": team_object_id, "name": "Bentley-Truman"}),
    )
    monkeypatch.setattr(
        roster_loader,
        "franchise_team_data_collection",
        SimpleNamespace(find_one=lambda query, projection=None: {"players": [player_id]}),
    )
    monkeypatch.setattr(
        roster_loader,
        "franchise_players_data_collection",
        SimpleNamespace(
            find=lambda query, projection=None: [
                {
                    "player_id": player_id,
                    "meta": {
                        "first_name": "Fresh",
                        "last_name": "Recruit",
                        "team": "Bentley-Truman",
                        "height": 82,
                        "weight": 215,
                        "year": "Freshman",
                        "jersey": 44,
                    },
                    "attributes": {"SC": 10, "SH": 9, "ID": 8, "OD": 7, "PS": 6, "BH": 5, "RB": 4, "AG": 3, "ST": 2, "ND": 1, "IQ": 11, "FT": 12},
                    "position_ratings": {"PF": 61, "C": 58},
                }
            ]
        ),
    )
    monkeypatch.setattr(
        roster_loader,
        "players_collection",
        SimpleNamespace(find=lambda query: []),
    )

    team_doc, players = roster_loader._load_from_db("Bentley-Truman", franchise_id=franchise_id)

    assert team_doc["name"] == "Bentley-Truman"
    assert len(players) == 1
    assert players[0]["_id"] == player_id
    assert players[0]["first_name"] == "Fresh"
    assert players[0]["last_name"] == "Recruit"
    assert players[0]["year"] == "Freshman"
    assert players[0]["attributes"]["SC"] == 10
    assert players[0]["position_ratings"]["PF"] == 61
