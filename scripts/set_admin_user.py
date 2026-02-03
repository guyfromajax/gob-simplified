#!/usr/bin/env python3
"""
Set a user's role to 'admin' by email (Step 12.1).

Run from repo root. Uses MONGO_URI from .env (or .env.local).
Usage:
    python scripts/set_admin_user.py you@example.com
    python scripts/set_admin_user.py you@example.com gob-staging   # specify database name
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv
    if os.path.exists(".env.local"):
        load_dotenv(".env.local")
    else:
        load_dotenv()
except ImportError:
    pass  # MONGO_URI can be set in environment

from pymongo import MongoClient
from pymongo.errors import OperationFailure
from bson import ObjectId

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    print("MONGO_URI not set. Set it in .env or .env.local")
    sys.exit(1)

# Parse DB name from URI or use default
db_name = os.environ.get("MONGO_DB_NAME", "gob")
if not db_name and MONGO_URI:
    try:
        from urllib.parse import urlparse
        p = urlparse(MONGO_URI)
        if p.path and p.path != "/":
            db_name = p.path.lstrip("/")
    except Exception:
        pass
if not db_name:
    db_name = "gob"

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_admin_user.py <email> [database_name]")
        print("  e.g. python scripts/set_admin_user.py you@example.com gob-staging")
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    use_db = sys.argv[2].strip() if len(sys.argv) > 2 else db_name
    try:
        client = MongoClient(MONGO_URI)
        db = client[use_db]
        users = db["users"]
        result = users.update_one(
            {"email": email},
            {"$set": {"role": "admin", "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            print(f"No user found with email: {email}")
            sys.exit(1)
        print(f"Set role=admin for {email} (database: {use_db})")
    except OperationFailure as e:
        if "auth" in str(e).lower() or "8000" in str(e):
            print("MongoDB authentication failed. Check:")
            print("  1. MONGO_URI in .env or .env.local (same as your app uses).")
            print("  2. Atlas user password: special characters must be URL-encoded in the URI.")
            print("  3. Or set admin manually: Atlas → Browse Collections → users → find the doc by email → set role to 'admin'.")
        raise

if __name__ == "__main__":
    main()
