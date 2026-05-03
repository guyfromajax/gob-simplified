"""Tests for ``BackEnd.utils.repair_franchise_eos_bracket``."""
from unittest.mock import MagicMock

from bson import ObjectId

from BackEnd.utils.repair_franchise_eos_bracket import (
    repair_franchise_eos_bracket_from_results,
)


def test_repair_fills_null_conference_r1_from_results_row():
    th, ta, tb, tc, td, te, tf = (str(ObjectId()) for _ in range(7))
    tw = str(ObjectId())
    fid = ObjectId()
    doc = {
        "_id": fid,
        "results": {
            "27": [
                {
                    "away_id": tw,
                    "home_id": th,
                    "away_score": 70,
                    "home_score": 60,
                    "game_id": "",
                },
                {
                    "away_id": tb,
                    "home_id": ta,
                    "away_score": 65,
                    "home_score": 70,
                    "game_id": "g1",
                },
                {
                    "away_id": td,
                    "home_id": tc,
                    "away_score": 60,
                    "home_score": 68,
                    "game_id": "g2",
                },
                {
                    "away_id": tf,
                    "home_id": te,
                    "away_score": 71,
                    "home_score": 72,
                    "game_id": "g3",
                },
            ],
        },
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {
                            "home_team": th,
                            "away_team": tw,
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        },
                        {
                            "home_team": ta,
                            "away_team": tb,
                            "winner": ta,
                            "game_id": "g1",
                            "score": {"home": 70, "away": 65},
                        },
                        {
                            "home_team": tc,
                            "away_team": td,
                            "winner": tc,
                            "game_id": "g2",
                            "score": {"home": 68, "away": 60},
                        },
                        {
                            "home_team": te,
                            "away_team": tf,
                            "winner": te,
                            "game_id": "g3",
                            "score": {"home": 72, "away": 71},
                        },
                    ],
                    "round2": [],
                    "final": [],
                },
            },
        },
    }

    mock_db = MagicMock()
    mock_db.games.find_one.return_value = None
    mock_db.franchises = MagicMock()

    out = repair_franchise_eos_bracket_from_results(
        doc,
        mongo_db=mock_db,
        weeks=(27,),
        dry_run=False,
    )
    assert out["applied_count"] >= 1
    assert out["changed"] is True
    r1 = doc["conference_tournaments"]["1"]["bracket"]["round1"]
    assert r1[0]["winner"] == tw
    mock_db.franchises.update_one.assert_called_once()


def test_repair_dry_run_does_not_call_update():
    fid = ObjectId()
    doc = {"_id": fid, "results": {}, "conference_tournaments": {}}
    mock_db = MagicMock()
    repair_franchise_eos_bracket_from_results(doc, mongo_db=mock_db, weeks=(27,), dry_run=True)
    mock_db.franchises.update_one.assert_not_called()
