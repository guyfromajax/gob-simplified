"""T3 player and team detail routes. Runs on mongomock and on SQLite."""

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.db import db, franchise_players_data_collection, franchise_team_data_collection

client = TestClient(app)

USER = ObjectId()
CPU = ObjectId()
DONE = ObjectId()
ADA = "ada-player"
BOB = "bob-player"


def setup_function(_fn):
    db.franchises.delete_many({})
    db.teams.delete_many({})
    franchise_players_data_collection.delete_many({})
    franchise_team_data_collection.delete_many({})


def _team(oid, name, conference, color):
    db.teams.insert_one({
        "_id": oid,
        "name": name,
        "conference": conference,
        "region": "A",
        "primary_color": color,
        "team_id": name.upper().replace(" ", "_"),
    })


def seed():
    fid = db.franchises.insert_one({
        "user_team_id": "Lancaster",
        "user_team_object_id": str(USER),
        "week": 3,
        "current_season": 1,
        "browse_rev": 0,
        "schedule": [
            [[str(CPU), str(USER)]],
            [[str(USER), str(CPU)]],
            [[str(CPU), str(USER)]],
            [[str(USER), str(CPU)]],
        ],
        "results": {
            "1": [{
                "away_id": str(CPU),
                "home_id": str(USER),
                "away_score": 60,
                "home_score": 70,
            }],
            "2": [{
                "away_id": str(USER),
                "home_id": str(CPU),
                "away_score": 50,
                "home_score": 55,
            }],
        },
    }).inserted_id
    _team(USER, "Lancaster", 2, "#112233")
    _team(CPU, "Four-Corners", 2, "#445566")
    _team(DONE, "York", 2, "#778899")
    for oid, rank in ((USER, 52), (CPU, 21), (DONE, 80)):
        franchise_team_data_collection.insert_one({
            "franchise_id": fid,
            "team_id": oid,
            "natl_rank": rank,
            "training_reports": {},
        })
    franchise_team_data_collection.update_one(
        {"franchise_id": fid, "team_id": USER},
        {"$set": {"training_reports": {
            "1": {
                "week": 1,
                "session_type": "preseason",
                "player_changes": {
                    "Ada Player": {"SC": -0.24, "SH": 0, "year": "freshman"},
                },
            },
            "3": {
                "week": 3,
                "session_type": "in-season",
                "player_attribute_display_movements": {
                    ADA: {
                        "name": "Ada Player",
                        "SC": {"from": 6, "to": 7},
                        "SH": {"from": 5, "to": 5},
                    },
                },
                "player_changes": {
                    "Ada Player": {"SC": 1.11},
                },
            },
        }}},
    )
    franchise_players_data_collection.insert_many([
        {
            "franchise_id": str(fid),
            "player_id": ADA,
            "meta": {
                "first_name": "Ada",
                "last_name": "Player",
                "team": "Lancaster",
                "team_id": str(USER),
                "position": "SG",
                "year": "freshman",
                "height": 71,
                "weight": 174,
                "jersey": 6,
            },
            "attributes": {"SC": 72.4, "SH": 19},
            "position_ratings": {"PG": 60, "SG": 80},
            "entry_tier": "Average",
            "potential_factor": 1.0,
            "training_position": "SG",
            "training_focus": "athletic",
            "season": {"GP": 2, "MIN": 40, "PTS": 20, "REB": 6, "AST": 4, "STL": 2, "BLK": 0, "FGM": 5, "FGA": 10, "3PTM": 1, "3PTA": 4, "FTM": 2, "FTA": 2, "DEF_S": 3, "DEF_A": 6},
            "career": {"GP": 2, "MIN": 40, "PTS": 20, "FGM": 5, "FGA": 10},
        },
        {
            "franchise_id": str(fid),
            "player_id": BOB,
            "meta": {
                "first_name": "Bob",
                "last_name": "Cpu",
                "team": "Four-Corners",
                "team_id": str(CPU),
                "position": "PG",
                "year": "senior",
                "height": 74,
                "weight": 190,
                "jersey": 1,
            },
            "attributes": {"SC": 50},
            "position_ratings": {"PG": 55},
            "training_focus": "standard",
            "season": {"GP": 1, "MIN": 10, "PTS": 4, "FGM": 0, "FGA": 0, "3PTM": 0, "3PTA": 0, "FTM": 0, "FTA": 0, "DEF_S": 0, "DEF_A": 0},
            "career": {"GP": 1, "PTS": 4, "FGA": 0},
        },
    ])
    return str(fid)


def test_user_player_mixes_old_and_new_training_reports():
    fid = seed()
    resp = client.get("/franchise/player-detail", params={"franchise_id": fid, "player_id": ADA})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["player_id"] == ADA
    assert body["name"] == "Ada Player"
    assert body["team_id"] == str(USER)
    assert body["team_name"] == "Lancaster"
    assert body["team_primary_color"] == "#112233"
    assert body["position"] == "SG"
    assert body["year"] == "FR"
    assert body["height_in"] == 71
    assert body["weight"] == 174
    assert body["jersey"] == 6
    assert body["is_user_team"] is True
    assert body["rt"] == 80
    assert body["potential"] == 80
    offense = body["attributes"][0]
    assert offense["label"] == "Offense"
    assert offense["attrs"][0] == {"attr": "SC", "raw": 72.4, "display": 7}
    assert offense["attrs"][1] == {"attr": "SH", "raw": 19, "display": 1}
    assert [group["label"] for group in body["attributes"]] == [
        "Offense", "Defense", "Skills", "Grit", "Body", "Mind",
    ]
    season = body["season"]
    assert season["gp"] == 2
    assert season["pts_per_game"] == 10
    assert season["min_per_game"] == 20
    assert season["fg_pct"] == 50
    assert season["tp_pct"] == 25
    assert season["ft_pct"] == 100
    assert season["def_pct"] == 50
    assert season["totals"]["FGA"] == 10
    assert body["recent_changes"] == [
        {
            "week": 3,
            "session_type": "in-season",
            "changes": [{"attr": "SC", "from": 6, "to": 7}],
        },
        {
            "week": 1,
            "session_type": "preseason",
            "changes": [{"attr": "SC", "delta": -0.24}],
        },
    ]
    assert body["development"] == {
        "focus": "athletic",
        "focus_label": "Athletic",
        "emphasises": ["ST", "AG"],
        "editable": True,
    }


def test_cpu_player_is_not_editable_and_zero_attempts_are_null():
    fid = seed()
    resp = client.get("/franchise/player-detail", params={"franchise_id": fid, "player_id": BOB})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_user_team"] is False
    assert body["team_name"] == "Four-Corners"
    assert body["position"] == "PG"
    assert body["year"] == "SR"
    assert body["recent_changes"] == []
    assert body["development"]["focus"] == "standard"
    assert body["development"]["emphasises"] == []
    assert body["development"]["editable"] is False
    season = body["season"]
    assert season["pts_per_game"] == 4
    assert season["fg_pct"] is None
    assert season["tp_pct"] is None
    assert season["ft_pct"] is None
    assert season["def_pct"] is None
    assert season["totals"]["FGA"] == 0


def test_team_detail_record_place_and_a_team_with_no_games_left():
    fid = seed()
    user = client.get("/franchise/team-detail", params={"franchise_id": fid, "team_id": str(USER)})
    assert user.status_code == 200, user.text
    body = user.json()
    assert body["name"] == "Lancaster"
    assert body["primary_color"] == "#112233"
    assert body["conference"] == "A2"
    assert body["region"] == "A"
    assert body["record"] == {"wins": 1, "losses": 1}
    assert body["natl_rank"] == 52
    assert body["conference_place"] == "1st of 3"
    assert body["streak"] == "L1"
    assert body["next_game"]["week"] == 3
    assert body["next_game"]["site"] == "home"
    assert body["next_game"]["opponent_id"] == str(CPU)
    assert body["next_game"]["opponent_name"] == "Four-Corners"
    assert body["next_game"]["opponent_primary_color"] == "#445566"
    assert body["next_game"]["opponent_natl_rank"] == 21
    assert [row["week"] for row in body["results"]] == [2, 1]
    assert body["results"][0]["result"] == "L"
    assert body["results"][0]["site"] == "away"
    assert body["results"][0]["team_score"] == 50
    assert body["results"][0]["opp_score"] == 55
    assert body["results"][0]["opponent_natl_rank"] == 21
    assert body["results"][1]["result"] == "W"
    assert body["results"][1]["site"] == "home"
    assert body["upcoming"] == [{
        "week": 4,
        "site": "away",
        "opponent_id": str(CPU),
        "opponent_name": "Four-Corners",
        "opponent_primary_color": "#445566",
        "opponent_natl_rank": 21,
        "opponent_wins": 1,
        "opponent_losses": 1,
    }]

    done = client.get("/franchise/team-detail", params={"franchise_id": fid, "team_id": str(DONE)})
    assert done.status_code == 200, done.text
    quiet = done.json()
    assert quiet["name"] == "York"
    assert quiet["record"] == {"wins": 0, "losses": 0}
    assert quiet["conference_place"] == "3rd of 3"
    assert quiet["streak"] is None
    assert quiet["next_game"] is None
    assert quiet["results"] == []
    assert quiet["upcoming"] == []


def test_missing_player_and_bad_ids():
    fid = seed()
    missing = client.get("/franchise/player-detail", params={"franchise_id": fid, "player_id": "nope"})
    assert missing.status_code == 404
    bad = client.get("/franchise/team-detail", params={"franchise_id": fid, "team_id": "not-an-id"})
    assert bad.status_code == 400
