#!/usr/bin/env python3
"""
Add username to existing user documents that lack it.

Prompts interactively for each user. Usernames must be unique (case-insensitive).
Run against an explicit database target through the shared script boundary.

USAGE:
    # Interactive - prompt for each user
    python scripts/add_username_to_existing_users.py

    # Dry run - list users needing usernames without making changes
    python scripts/add_username_to_existing_users.py --dry-run
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target


def validate_username(username: str) -> str | None:
    """Returns None if valid; otherwise returns error message."""
    u = username.strip()
    if " " in u:
        return "Username cannot contain spaces"
    if len(u) < 3:
        return "Username must be at least 3 characters"
    if len(u) > 24:
        return "Username must be at most 24 characters"
    if not re.match(r"^[a-zA-Z0-9_]+$", u):
        return "Username can only contain letters, numbers, and underscores"
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    parser.add_argument("--apply", action="store_true", help="Prompt and write; default lists only")
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=args.apply)
    users_collection = connection.database["users"]

    # Users missing username or username_lower
    query = {"$or": [{"username": {"$exists": False}}, {"username": None}, {"username_lower": {"$exists": False}}]}
    users = list(users_collection.find(query, {"_id": 1, "email": 1, "username": 1}))
    users = [u for u in users if not u.get("username") or not u.get("username_lower")]

    print("=" * 60)
    print("Add username to existing users")
    print("=" * 60)
    print(f"Database: {args.db}")
    print(f"Users needing username: {len(users)}")
    print("=" * 60)

    if not users:
        print("No users need a username.")
        return

    if not args.apply:
        for u in users:
            print(f"  {u['_id']}  {u.get('email', 'no-email')}")
        connection.close()
        return

    taken = set()
    for u in users:
        uid = str(u["_id"])
        email = u.get("email", "no-email")
        print(f"\nUser: {email} (id: {uid})")
        while True:
            raw = input("  Username (or 'skip'): ").strip()
            if raw.lower() == "skip":
                print("  Skipped.")
                break
            err = validate_username(raw)
            if err:
                print(f"  {err}")
                continue
            uname = raw.strip()
            ulower = uname.lower()
            if ulower in taken:
                print(f"  Username already used in this session.")
                continue
            existing = users_collection.find_one({"username_lower": ulower, "_id": {"$ne": u["_id"]}})
            if existing:
                print(f"  Username already taken by another user.")
                continue
            users_collection.update_one(
                {"_id": u["_id"]},
                {"$set": {"username": uname, "username_lower": ulower}}
            )
            taken.add(ulower)
            print(f"  Updated: {uname}")
            break

    print("\nDone.")
    connection.close()


if __name__ == "__main__":
    main()
