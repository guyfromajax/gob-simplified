#!/usr/bin/env python3
"""Seed N tagged load-test users + one franchise each on staging (STAGING ONLY).

Staging runs in alpha mode (signup needs an access code), so users are inserted
directly, shaped like a real signup that has finished the tutorial. Each user then
logs in through the real POST /api/auth/login and creates a franchise through the
real flow (GET /teams, POST /franchise/select-team?profile=1 {team_name}), and the
franchise is stamped loadtest_name="LOADTEST-<n>" (the create API has no name field).

    GOB_DB_ACCESS=write ../gob-simplified/.venv/bin/python scripts/loadtest/seed.py --n 2

Idempotent: an existing loadtest+<n> user gets its password reset to this run's.
Passwords are written to scripts/loadtest/.state/users.json (gitignored, 0600).
"""

from __future__ import annotations

import argparse
import secrets
import time
from datetime import datetime, timezone

import bcrypt
import httpx

from common import (
    FRANCHISE_PREFIX,
    STAGING_BASE_URL,
    connect_staging,
    email_for,
    is_tagged_email,
    require_staging_url,
    save_users,
    username_for,
)

AUTH_LIMIT_PER_MIN = 10  # RATE_LIMIT_AUTH on staging (per IP); pace logins under it


def user_doc(n: int, password: str, now: datetime) -> dict:
    from BackEnd.utils.user_tracking import default_user_tracking

    return {
        "email": email_for(n),
        "username": username_for(n),
        "username_lower": username_for(n),
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "role": "user",
        "subscription": "alpha",
        "account_settings": {"display_color": "default"},
        "geek_points": 0,
        # Past onboarding, as /fte-complete + /tutorial-complete leave a real user.
        "fte": False,
        "fte_v2_complete": True,
        "tutorial_state": {"step": "complete", "team_pick": None, "started_at": now, "completed_at": now},
        **default_user_tracking(),
        "loadtest": True,
        "created_at": now,
        "updated_at": now,
        "version": 1,
    }


def create_franchises(db, users: list[dict]) -> None:
    """Real client flow per user: login -> GET /teams -> select-team; then tag it."""
    base = require_staging_url(STAGING_BASE_URL)
    with httpx.Client(base_url=base, timeout=300) as client:
        teams = None
        for i, u in enumerate(users):
            if i and i % (AUTH_LIMIT_PER_MIN - 1) == 0:
                time.sleep(61)  # stay under the per-IP auth limit
            r = client.post("/api/auth/login", json={"email": u["email"], "password": u["password"]})
            r.raise_for_status()
            u["token"] = r.json()["token"]
            auth = {"Authorization": f"Bearer {u['token']}"}
            existing = db["franchises"].find_one({"user_id": u["user_id"],
                                                  "loadtest_name": {"$regex": f"^{FRANCHISE_PREFIX}"}}, {"_id": 1})
            if existing:
                u["franchise_id"] = str(existing["_id"])
                continue
            if teams is None:
                t = client.get("/teams", headers=auth)
                t.raise_for_status()
                teams = [row.get("name") for row in t.json() if isinstance(row, dict) and row.get("name")]
            team_name = teams[(u["n"] - 1) % len(teams)]
            started = time.time()
            r = client.post("/franchise/select-team", params={"profile": 1},
                            json={"team_name": team_name}, headers=auth)
            r.raise_for_status()
            fid = r.json()["franchise_id"]
            # Tag only a franchise this tagged user owns.
            from bson import ObjectId
            res = db["franchises"].update_one(
                {"_id": ObjectId(fid), "user_id": u["user_id"]},
                {"$set": {"loadtest_name": f"{FRANCHISE_PREFIX}-{u['n']}"}},
            )
            assert res.matched_count == 1, f"could not tag franchise {fid}"
            u.update({"franchise_id": fid, "team_name": team_name,
                      "select_team_s": round(time.time() - started, 2)})
            print(f"  user {u['n']}: franchise {fid} ({team_name}) in {u['select_team_s']}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, required=True, help="Number of users (loadtest+1 .. loadtest+N).")
    args = parser.parse_args()

    password = "Lt" + secrets.token_urlsafe(12) + "9"
    now = datetime.now(timezone.utc)
    conn = connect_staging("write")
    users = []
    try:
        coll = conn.database["users"]
        for n in range(1, args.n + 1):
            email = email_for(n)
            assert is_tagged_email(email)
            doc = user_doc(n, password, now)
            existing = coll.find_one({"email": email}, {"_id": 1})
            if existing:
                coll.update_one({"_id": existing["_id"], "email": email},
                                {"$set": {"password_hash": doc["password_hash"], "updated_at": now}})
                uid = existing["_id"]
            else:
                uid = coll.insert_one(doc).inserted_id
            users.append({"n": n, "email": email, "password": password, "user_id": str(uid)})
        save_users(users)
        print(f"seeded {len(users)} tagged users in gob-staging; creating franchises")
        create_franchises(conn.database, users)
    finally:
        save_users(users)
        conn.close()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
