#!/usr/bin/env python3
"""
Add subscription and geek_points to all documents in the users collection.

Sets:
  subscription: "alpha" (string)
  geek_points: 0 (integer)

Run from repo root. Uses MONGO_URI from .env (or .env.local).
Usage:
  python scripts/add_user_subscription_geek_points.py gob
  python scripts/add_user_subscription_geek_points.py gob-staging
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


def get_default_db_name():
    db_name = os.environ.get("MONGO_DB_NAME")
    if db_name:
        return db_name
    if MONGO_URI:
        try:
            from urllib.parse import urlparse
            p = urlparse(MONGO_URI)
            if p.path and p.path != "/":
                return p.path.lstrip("/").split("?")[0] or "gob"
        except Exception:
            pass
    return "gob"


def main():
    use_db = sys.argv[1].strip() if len(sys.argv) > 1 else get_default_db_name()
    client = MongoClient(MONGO_URI)
    db = client[use_db]
    users = db["users"]

    result = users.update_many(
        {},
        {"$set": {"subscription": "alpha", "geek_points": 0}},
    )
    print(f"Database: {use_db}")
    print(f"Matched:  {result.matched_count}")
    print(f"Modified: {result.modified_count}")
    print("Done.")


if __name__ == "__main__":
    main()
