#!/usr/bin/env python3
"""Throwaway SQLite save for tournament-view offline screenshot (week 27)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.chdir(REPO)

SQLITE = Path(os.environ.get("GOB_TOURNEY_OFFLINE_SQLITE") or "/tmp/tournament-view-offline.sqlite")
if SQLITE.exists():
    SQLITE.unlink()

os.environ["GOB_SQLITE_PATH"] = str(SQLITE)
os.environ["GOB_PERSISTENCE"] = "sqlite"
os.environ["GOB_DB_MODE"] = "mongomock"
os.environ["ENVIRONMENT"] = "test"
os.environ["MONGO_DB_NAME"] = "gob-test"

from bson import ObjectId

from tests.test_persistence_adapter import _mongomock_env
from BackEnd.persistence import create_store
from BackEnd.local_identity import LOCAL_USER_ID

env = _mongomock_env(
    Path("/tmp/gob-tourney-offline-seed"),
    GOB_PERSISTENCE="sqlite",
    GOB_SQLITE_PATH=str(SQLITE),
)
store = create_store(env)

fid = ObjectId()
team_oid = ObjectId()
user_team = str(team_oid)
opp_oid = ObjectId()
opp = str(opp_oid)

store.teams_collection.insert_many([
    {"_id": team_oid, "name": "Lancaster", "conference": 1, "region": "A", "W": 20, "L": 6},
    {"_id": opp_oid, "name": "Rival U", "conference": 1, "region": "A", "W": 18, "L": 8},
])
store.franchise_team_data_collection.insert_one({
    "franchise_id": fid,
    "team_id": user_team,
    "natl_rank": 4,
})

store.franchises_collection.insert_one({
    "_id": fid,
    "user_id": LOCAL_USER_ID,
    "user_team_id": user_team,
    "user_team_object_id": user_team,
    "week": 27,
    "browse_rev": 1,
    "conference_tournaments": {
        "1": {
            "current_round": 1,
            "bracket": {
                "round1": [{
                    "home_team": user_team,
                    "away_team": opp,
                    "winner": user_team,
                    "game_id": "g-offline-1",
                    "score": {"home": 72, "away": 65},
                }],
                "round2": [],
                "final": [],
            },
            "seeds": {user_team: 3, opp: 6},
        }
    },
    "region_tournaments": {},
    "national_tournament": {},
    "results": {},
})

meta = {
    "franchise_id": str(fid),
    "team_id": user_team,
    "sqlite": str(SQLITE),
}
print(json.dumps(meta))
