import mongomock
from bson import ObjectId

from BackEnd.tournament.bracket_logic import update_bracket_from_results


def test_update_bracket_advances_using_matchup_winners():
    # Set up a mock tournaments collection using mongomock
    client = mongomock.MongoClient()
    collection = client["gob"]["tournaments"]

    # Create a tournament document with winners in round1 but no results
    tid = ObjectId()
    tournament = {
        "_id": tid,
        "current_round": 1,
        "results": [],
        "bracket": {
            "round1": [
                {"home_team": "A", "away_team": "B", "game_id": None, "winner": "A", "score": {}},
                {"home_team": "C", "away_team": "D", "game_id": None, "winner": "C", "score": {}},
                {"home_team": "E", "away_team": "F", "game_id": None, "winner": "E", "score": {}},
                {"home_team": "G", "away_team": "H", "game_id": None, "winner": "H", "score": {}},
            ]
        },
    }
    collection.insert_one(tournament)

    # Update the bracket and verify progression to round 2
    updated = update_bracket_from_results(tid, tournaments_collection=collection)

    assert updated["current_round"] == 2
    round2 = updated["bracket"].get("round2")
    assert round2 is not None and len(round2) == 2
    assert round2[0]["home_team"] == "A"
    assert round2[0]["away_team"] == "C"
    assert round2[1]["home_team"] == "E"
    assert round2[1]["away_team"] == "H"
