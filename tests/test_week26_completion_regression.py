"""
Regression tests for week 26 (regular-season final) completion.

- BSON keys: conference_tournaments must use string keys (not int) for MongoDB.
- Payload size: assert the week-26 update does not exceed BSON doc limit.
- Integration: run complete-week for week 26 and assert results are persisted.

Does NOT delete or erase any existing DB data; integration test inserts
only new documents with unique IDs and cleans up only those.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch, MagicMock
from bson import ObjectId
import pytest

# MongoDB document size limit (16MB)
BSON_DOCUMENT_SIZE_LIMIT = 16 * 1024 * 1024


class _MockTeamsCollection:
    """Minimal teams collection for franchise_tournament.initialize_conference_tournaments."""
    def __init__(self, team_docs):
        self._by_id = {str(d["_id"]): d for d in team_docs}

    def find(self, query, projection=None):
        ids = query.get("_id", {}).get("$in", [])
        for tid in ids:
            d = self._by_id.get(str(tid))
            if d is None:
                continue
            if projection:
                yield {k: d[k] for k in projection if k in d}
            else:
                yield d


def _mock_ftd_collection(team_ids):
    """Return a mock FTD 'collection' so eos_tournament.calculate_standings doesn't hit DB."""
    ftd_docs = [{"team_id": tid, "natl_rank": (i % 128) + 1} for i, tid in enumerate(team_ids)]
    mock = MagicMock()
    mock.find.return_value = iter(ftd_docs)
    return mock


def test_week26_conference_tournaments_bson_serializable():
    """Ensure conference_tournaments structure is BSON-serializable (no custom types)."""
    from bson import BSON
    from BackEnd.tournament import franchise_tournament as ft
    from BackEnd.tournament import eos_tournament as eos

    team_ids = [ObjectId() for _ in range(128)]
    team_docs = []
    for i, tid in enumerate(team_ids):
        c = (i % 16) + 1
        r = chr(ord("A") + (c - 1) // 2)
        team_docs.append({"_id": tid, "name": f"Team{i}", "conference": c, "region": r})
    mock_teams = _MockTeamsCollection(team_docs)

    franchise_doc = {"_id": ObjectId(), "results": {}}
    for w in range(1, 26):
        franchise_doc["results"][str(w)] = [
            {"away_id": str(team_ids[0]), "home_id": str(team_ids[1]), "away_score": 70, "home_score": 60}
        ]

    with patch.object(eos, "franchise_team_data_collection", _mock_ftd_collection(team_ids)):
        conference_tournaments = ft.initialize_conference_tournaments(
            franchise_doc, mock_teams, team_ids=team_ids
        )
    raw = BSON.encode(conference_tournaments)
    assert len(raw) > 0, "conference_tournaments should serialize"
    assert len(raw) < BSON_DOCUMENT_SIZE_LIMIT, (
        f"conference_tournaments alone is {len(raw) / (1024*1024):.2f} MB"
    )


def test_week26_full_update_payload_size():
    """
    Build the same payload that complete_week would $set on week 26 completion.
    Fail if the full resulting document would exceed MongoDB 16MB limit.
    """
    from bson import BSON
    from BackEnd.tournament import franchise_tournament as ft
    from BackEnd.tournament import eos_tournament as eos

    team_ids = [ObjectId() for _ in range(128)]
    team_docs = []
    for i, tid in enumerate(team_ids):
        c = (i % 16) + 1
        r = chr(ord("A") + (c - 1) // 2)
        team_docs.append({"_id": tid, "name": f"Team{i}", "conference": c, "region": r})
    mock_teams = _MockTeamsCollection(team_docs)

    franchise_doc = {"_id": ObjectId(), "results": {}}
    for w in range(1, 26):
        franchise_doc["results"][str(w)] = [
            {"away_id": str(team_ids[(w + 0) % 128]), "home_id": str(team_ids[(w + 1) % 128]),
             "away_score": 70, "home_score": 60}
        ]

    with patch.object(eos, "franchise_team_data_collection", _mock_ftd_collection(team_ids)):
        conference_tournaments = ft.initialize_conference_tournaments(
            franchise_doc, mock_teams, team_ids=team_ids
        )

    existing_results = dict(franchise_doc["results"])
    week_26_results = []
    for i in range(64):
        away_idx = (i * 2) % 128
        home_idx = (i * 2 + 1) % 128
        week_26_results.append({
            "away_id": str(team_ids[away_idx]),
            "home_id": str(team_ids[home_idx]),
            "away_score": 70 + (i % 20),
            "home_score": 60 + (i % 15),
        })
    existing_results["26"] = week_26_results

    update_fields = {
        "results": existing_results,
        "week": 27,
        "conference_tournaments": conference_tournaments,
        "eos_tournament_active": True,
    }
    payload_bytes = BSON.encode(update_fields)
    size_mb = len(payload_bytes) / (1024 * 1024)
    assert len(payload_bytes) < BSON_DOCUMENT_SIZE_LIMIT, (
        f"Week 26 update payload is {size_mb:.2f} MB (MongoDB limit 16 MB). "
        "Likely cause of week 26 completion failure."
    )


def test_week26_builds_update_fields_week_27_and_16_conference_tournaments():
    """
    Regression: complete_week(week=26) must set update_fields['week'] = 27 and
    update_fields['conference_tournaments'] with 16 entries (all conferences).
    """
    from BackEnd.models.franchise_manager import ScheduleManager
    from BackEnd.tournament import franchise_tournament as ft
    from BackEnd.tournament import eos_tournament as eos

    req_week = 26
    assert req_week == ScheduleManager.REGULAR_SEASON_WEEKS

    team_ids = [ObjectId() for _ in range(128)]
    team_docs = []
    for i, tid in enumerate(team_ids):
        c = (i % 16) + 1
        r = chr(ord("A") + (c - 1) // 2)
        team_docs.append({"_id": tid, "name": f"T{i}", "conference": c, "region": r})
    mock_teams = _MockTeamsCollection(team_docs)

    franchise_doc = {"_id": ObjectId(), "results": {}}
    for w in range(1, 26):
        franchise_doc["results"][str(w)] = [
            {"away_id": str(team_ids[0]), "home_id": str(team_ids[1]), "away_score": 70, "home_score": 60}
        ]
    results_26 = [{"away_id": str(team_ids[i % 128]), "home_id": str(team_ids[(i + 1) % 128]), "away_score": 70, "home_score": 60} for i in range(64)]
    existing_results = dict(franchise_doc["results"])
    existing_results["26"] = results_26

    next_week = req_week + 1
    update_fields = {
        "results": existing_results,
        "week": next_week,
        "training_status.training_completed": False,
        "training_status.session_type": "in-season",
    }

    if req_week == ScheduleManager.REGULAR_SEASON_WEEKS:
        franchise_doc["results"] = existing_results
        with patch.object(eos, "franchise_team_data_collection", _mock_ftd_collection(team_ids)):
            conference_tournaments = ft.initialize_conference_tournaments(
                franchise_doc, mock_teams, team_ids=team_ids
            )
        update_fields["conference_tournaments"] = conference_tournaments
        update_fields["eos_tournament_active"] = True
        update_fields["week"] = ft.EOS_CONFERENCE_WEEKS[0]

    assert update_fields["week"] == 27, "Week 26 completion must set week to 27"
    assert update_fields.get("eos_tournament_active") is True
    assert "conference_tournaments" in update_fields
    ct = update_fields["conference_tournaments"]
    assert len(ct) == 16, "Must have 16 conference tournaments (one per conference)"
    for k in ["1", "2", "8", "16"]:
        assert k in ct, f"Conference key {k} must be present (string keys for BSON)"


@pytest.mark.skipif(
    not os.environ.get("MONGO_URI"),
    reason="MONGO_URI not set; integration test requires real DB (uses unique IDs, does not delete)"
)
def test_week26_completion_integration_no_delete():
    """
    Call POST /franchise/complete-week for week 26 with a minimal 128-team franchise.
    Asserts: 200, results['26'] present, week advanced to 27, conference_tournaments set.
    Does NOT delete any data; inserts only new docs with unique ObjectIds.
    """
    from fastapi.testclient import TestClient
    from BackEnd.api.api import app
    from BackEnd.db import db, franchise_team_data_collection

    client = TestClient(app)
    team_ids = [ObjectId() for _ in range(128)]
    team_docs = []
    for i, tid in enumerate(team_ids):
        c = (i % 16) + 1
        r = chr(ord("A") + (c - 1) // 2)
        team_docs.append({
            "_id": tid,
            "name": f"RegressTeam{i}",
            "conference": c,
            "region": r,
        })
    db.teams.insert_many(team_docs)

    schedule = []
    for _ in range(26):
        week_games = []
        for i in range(64):
            week_games.append((team_ids[(i * 2) % 128], team_ids[(i * 2 + 1) % 128]))
        schedule.append(week_games)

    franchise_id = ObjectId()
    user_team_id = team_ids[0]
    results_1_25 = {}
    for w in range(1, 26):
        results_1_25[str(w)] = [
            {"away_id": str(team_ids[0]), "home_id": str(team_ids[1]), "away_score": 70, "home_score": 60}
        ]

    db.franchises.insert_one({
        "_id": franchise_id,
        "schedule": schedule,
        "week": 26,
        "results": results_1_25,
        "user_team_id": str(user_team_id),
    })

    ftd_docs = [{"franchise_id": franchise_id, "team_id": tid, "natl_rank": (i % 128) + 1}
                for i, tid in enumerate(team_ids)]
    franchise_team_data_collection.insert_many(ftd_docs)

    payload = {
        "franchise_id": str(franchise_id),
        "week": 26,
        "result": {
            "team1_id": str(team_ids[0]),
            "team2_id": str(team_ids[1]),
            "team1_score": 72,
            "team2_score": 68,
        },
    }

    try:
        res = client.post("/franchise/complete-week", json=payload)
        assert res.status_code == 200, (
            f"Week 26 complete-week failed: {res.status_code} body={res.text}"
        )
        data = res.json()
        assert "results" in data

        doc = db.franchises.find_one({"_id": franchise_id})
        assert doc is not None
        assert "26" in doc.get("results", {}), "results['26'] should be present after week 26 completion"
        assert doc.get("week") == 27, "week should advance to 27"
        assert doc.get("eos_tournament_active") is True
        assert doc.get("conference_tournaments") is not None
    finally:
        db.teams.delete_many({"_id": {"$in": team_ids}})
        db.franchises.delete_one({"_id": franchise_id})
        franchise_team_data_collection.delete_many({"franchise_id": franchise_id})
