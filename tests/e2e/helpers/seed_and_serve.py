#!/usr/bin/env python3
"""Test-only Playwright webServer launcher.

Seeds canonical mongomock rosters/plays/defenses in this process, then serves
the FastAPI app with reload=False. Passing the app object (not an import
string) keeps the seeded singleton; uvicorn reload would fork an empty child.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

# Before importing BackEnd — mongomock only, never staging/prod.
os.environ.setdefault("GOB_DB_MODE", "mongomock")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_DB_NAME", "gob-test")
os.environ.setdefault("PYTHONHASHSEED", "0")

_FORBIDDEN_DB_NAMES = frozenset({"gob", "gob-staging"})


def _refuse_unsafe_env() -> None:
    mode = os.environ.get("GOB_DB_MODE", "")
    db_name = os.environ.get("MONGO_DB_NAME", "")
    if mode != "mongomock" or db_name in _FORBIDDEN_DB_NAMES:
        raise SystemExit(
            "seed_and_serve.py refuses to start: "
            f"GOB_DB_MODE={mode!r} MONGO_DB_NAME={db_name!r}. "
            "This launcher only seeds mongomock (never gob or gob-staging)."
        )


def main() -> None:
    _refuse_unsafe_env()

    from BackEnd.db import (
        defenses_collection,
        players_collection,
        plays_collection,
        teams_collection,
    )
    from tests.roster_fixtures import (
        seed_universal_defenses,
        seed_universal_plays,
        seed_universal_rosters,
    )

    seed_universal_rosters(teams_collection, players_collection)
    seed_universal_plays(plays_collection)
    seed_universal_defenses(defenses_collection)
    # mongomock has no $replaceAll, so the roster name-normalization aggregate
    # 500s. Strategy 1 is find_one({"team_id": lookup_value}); alias the court
    # URL identifiers so /roster/Lancaster and /roster/Four-Corners succeed.
    for url_id, name in (("Lancaster", "Lancaster"), ("Four-Corners", "Four Corners")):
        teams_collection.update_one(
            {"team_id": url_id},
            {"$set": {"name": name, "team_id": url_id}},
            upsert=True,
        )
    print("seed_and_serve: canonical rosters seeded (Lancaster, Four Corners, Bentley-Truman, Morristown)")

    import uvicorn
    from BackEnd.api.api import app

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
