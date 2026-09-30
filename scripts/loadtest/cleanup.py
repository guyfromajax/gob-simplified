#!/usr/bin/env python3
"""Remove ONLY tagged load-test data from gob-staging (STAGING ONLY).

A franchise is removed only if BOTH hold:
  - its owner is a tagged user (email loadtest+<n>@example.com AND loadtest: true)
  - it carries loadtest_name starting "LOADTEST" (stamped by seed.py)

Order:
  1. Each tagged franchise goes through the app's real delete path,
     DELETE /franchise/{id} as its owner. That cascades franchise_team_data,
     franchise_players_data, franchise_recruits_data, games,
     press_conference_sessions and the franchise doc, and GCs R2 portrait masters.
  2. Sweep what that API delete leaves behind: the 6 collection types only
     PersistenceStore.delete_franchise covers — leaders_snapshots,
     standings_snapshots (_id = fid and meta:fid), training_sessions, tournaments,
     franchise_state, eog_band_log — plus any leftover from step 1 if the API call
     failed.
  3. Pull tagged rows from the shared feeds: community_highlights entries whose
     username is loadtest_<n>, around_the_league slots whose user_id is tagged.
  4. Delete the tagged users (+ their password_reset_tokens).
  5. Verify: every count above is zero.

Dry run by default (prints what it would remove). Execute with:
    GOB_DB_ACCESS=write ../gob-simplified/.venv/bin/python scripts/loadtest/cleanup.py --yes
"""

from __future__ import annotations

import argparse
import re
import sys

import httpx
from bson import ObjectId

from common import (
    EMAIL_RE,
    FRANCHISE_PREFIX,
    STAGING_BASE_URL,
    connect_staging,
    is_tagged_email,
    load_users,
    require_staging_url,
)

USERNAME_RE = re.compile(r"^loadtest_\d+$")
# Shared single-doc feeds (BackEnd/utils/community_highlights.py FEED_DOC_ID,
# BackEnd/utils/around_the_league.py BOARD_DOC_ID). Not imported: those modules
# open the app store on import.
FEED_DOC_ID = "global_feed"
BOARD_DOC_ID = "global_board"

# franchise-keyed collections: (name, how the franchise id is stored)
CASCADE_API = [
    ("franchise_team_data", "oid"),
    ("franchise_players_data", "sid"),
    ("franchise_recruits_data", "sid"),
    ("games", "sid"),
    ("press_conference_sessions", "either"),
]
API_ORPHANS = [
    ("training_sessions", "either"),
    ("tournaments", "either"),
    ("franchise_state", "either"),
    ("eog_band_log", "either"),
]
SNAPSHOTS = ["leaders_snapshots", "standings_snapshots"]  # _id = fid / meta:fid


def _filter(kind: str, oid: ObjectId) -> dict:
    sid = str(oid)
    if kind == "oid":
        return {"franchise_id": oid}
    if kind == "sid":
        return {"franchise_id": sid}
    return {"franchise_id": {"$in": [oid, sid]}}


def find_tagged(db) -> tuple[list[dict], list[dict]]:
    users = [
        u for u in db["users"].find({"email": {"$regex": EMAIL_RE.pattern}, "loadtest": True},
                                    {"email": 1, "username": 1})
        if is_tagged_email(u.get("email"))
    ]
    uids = [str(u["_id"]) for u in users]
    franchises = [
        f for f in db["franchises"].find({"user_id": {"$in": uids}}, {"user_id": 1, "loadtest_name": 1})
        if str(f.get("loadtest_name") or "").startswith(FRANCHISE_PREFIX)
    ]
    return users, franchises


def counts(db, users: list[dict], franchises: list[dict]) -> dict:
    out: dict = {"users": len(users), "franchises": len(franchises)}
    for name, kind in CASCADE_API + API_ORPHANS:
        out[name] = sum(db[name].count_documents(_filter(kind, f["_id"])) for f in franchises)
    for name in SNAPSHOTS:
        ids = [str(f["_id"]) for f in franchises] + [f"meta:{f['_id']}" for f in franchises]
        out[name] = db[name].count_documents({"_id": {"$in": ids}})
    uids = [str(u["_id"]) for u in users]
    feed = db["community_highlights"].find_one({"_id": FEED_DOC_ID}) or {}
    names = {str(u.get("username")) for u in users if USERNAME_RE.match(str(u.get("username") or ""))}
    out["community_highlights.entries"] = sum(
        1 for e in (feed.get("entries") or []) if str(e.get("username") or "") in names
    )
    board = db["around_the_league"].find_one({"_id": BOARD_DOC_ID}) or {}
    out["around_the_league.slots"] = sum(1 for s in (board.get("slots") or []) if str(s.get("user_id")) in uids)
    out["password_reset_tokens"] = db["password_reset_tokens"].count_documents(
        {"user_id": {"$in": [u["_id"] for u in users]}})
    return out


def api_delete(franchises: list[dict], users: list[dict]) -> dict:
    """DELETE /franchise/{id} as the owner (the app's real delete path)."""
    base = require_staging_url(STAGING_BASE_URL)
    creds = {u["email"]: u for u in load_users()}
    email_by_uid = {str(u["_id"]): u["email"] for u in users}
    results = {}
    tokens: dict[str, str] = {}
    with httpx.Client(base_url=base, timeout=180) as client:
        for f in franchises:
            email = email_by_uid.get(str(f["user_id"]))
            cred = creds.get(email or "")
            if not cred:
                results[str(f["_id"])] = "no-credentials (DB sweep only)"
                continue
            if email not in tokens:
                r = client.post("/api/auth/login", json={"email": email, "password": cred["password"]})
                if r.status_code != 200:
                    results[str(f["_id"])] = f"login {r.status_code} (DB sweep only)"
                    continue
                tokens[email] = r.json()["token"]
            r = client.delete(f"/franchise/{f['_id']}", headers={"Authorization": f"Bearer {tokens[email]}"})
            results[str(f["_id"])] = f"DELETE {r.status_code}"
    return results


def sweep(db, users: list[dict], franchises: list[dict]) -> None:
    for f in franchises:
        oid = f["_id"]
        for name, kind in CASCADE_API + API_ORPHANS:
            db[name].delete_many(_filter(kind, oid))
        for name in SNAPSHOTS:
            db[name].delete_many({"_id": {"$in": [str(oid), f"meta:{oid}"]}})
        # Only if the API delete didn't already remove it; still double-checked.
        db["franchises"].delete_one({"_id": oid, "user_id": f["user_id"],
                                     "loadtest_name": {"$regex": f"^{FRANCHISE_PREFIX}"}})
    uids = [str(u["_id"]) for u in users]
    # Exact tagged usernames only (never a pattern a real user could match).
    names = sorted({str(u.get("username")) for u in users if USERNAME_RE.match(str(u.get("username") or ""))})
    if names:
        db["community_highlights"].update_one(
            {"_id": FEED_DOC_ID}, {"$pull": {"entries": {"username": {"$in": names}}}})
    db["around_the_league"].update_one(
        {"_id": BOARD_DOC_ID}, {"$pull": {"slots": {"user_id": {"$in": uids}}}})
    oids = [u["_id"] for u in users]
    db["password_reset_tokens"].delete_many({"user_id": {"$in": oids}})
    for u in users:
        db["users"].delete_one({"_id": u["_id"], "email": u["email"], "loadtest": True})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="Actually delete (default: dry run).")
    args = parser.parse_args()

    conn = connect_staging("write" if args.yes else "read")
    try:
        db = conn.database
        users, franchises = find_tagged(db)
        before = counts(db, users, franchises)
        print("tagged data found:", before)
        if not args.yes:
            print("dry run — nothing removed. Re-run with GOB_DB_ACCESS=write ... --yes")
            return 0
        print("API delete:", api_delete(franchises, users))
        sweep(db, users, franchises)
        after = counts(db, users, franchises)
        users_left, franchises_left = find_tagged(db)
        after.update({"users": len(users_left), "franchises": len(franchises_left)})
        print("after cleanup:", after)
        leftover = {k: v for k, v in after.items() if v}
        if leftover:
            print("NOT CLEAN:", leftover, file=sys.stderr)
            return 1
        print("clean: no tagged data left")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
