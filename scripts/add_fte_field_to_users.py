#!/usr/bin/env python3
"""
Add an "fte" field to all users in the users collection and set it to True.

Run from repo root. Uses MONGO_URI from .env (or .env.local).
Updates both gob and gob-staging in one run.

Usage:
  python scripts/add_fte_field_to_users.py

To run against a single database:
  python scripts/add_fte_field_to_users.py gob
  python scripts/add_fte_field_to_users.py gob-staging
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv
    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
    else:
        load_dotenv()
except ImportError:
    pass

from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    print("MONGO_URI not set. Set it in .env or .env.local")
    sys.exit(1)

# Default: run against both databases
DATABASES = ["gob", "gob-staging"]


def main():
    if len(sys.argv) > 1:
        databases = [sys.argv[1].strip()]
    else:
        databases = DATABASES

    client = MongoClient(MONGO_URI)

    for db_name in databases:
        db = client[db_name]
        users = db["users"]
        result = users.update_many(
            {},
            {"$set": {"fte": True}},
        )
        print(f"Database: {db_name}")
        print(f"  Matched:  {result.matched_count}")
        print(f"  Modified: {result.modified_count}")

    print("Done.")


if __name__ == "__main__":
    main()
