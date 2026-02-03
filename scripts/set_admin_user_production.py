#!/usr/bin/env python3
"""
Set a user's role to 'admin' in the PRODUCTION database (gob).

Uses production credentials only — does not use .env or .env.local.
Run from repo root.

Setup (choose one):
  A) Create .env.production in repo root with:
       MONGO_URI=<your-production-atlas-connection-string>
     (Optional: MONGO_DB_NAME=gob if not in the URI path.)
  B) Or set env vars before running:
       export MONGO_URI_PRODUCTION="mongodb+srv://..."
       python scripts/set_admin_user_production.py jamie@geekedoutgames.com

Usage:
    python scripts/set_admin_user_production.py jamie@geekedoutgames.com
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load production env only (do not load .env or .env.local)
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_prod_env = os.path.join(_repo_root, ".env.production")
if os.path.exists(_prod_env):
    try:
        from dotenv import load_dotenv
        load_dotenv(_prod_env)
    except ImportError:
        pass
elif os.path.exists(".env.production"):
    try:
        from dotenv import load_dotenv
        load_dotenv(".env.production")
    except ImportError:
        pass

# Production URI: from .env.production or MONGO_URI_PRODUCTION
MONGO_URI = os.environ.get("MONGO_URI_PRODUCTION") or os.environ.get("MONGO_URI")
if not MONGO_URI:
    print("Production MongoDB URI not set.")
    print("  Option A: Create .env.production in repo root with one line:")
    print("    MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/gob?retryWrites=...")
    print("    (Repo root .env.production path: " + _prod_env + ")")
    print("  Option B: export MONGO_URI_PRODUCTION='mongodb+srv://...' then run this script again.")
    sys.exit(1)

# Production database name (default gob)
db_name = os.environ.get("MONGO_DB_NAME_PRODUCTION") or os.environ.get("MONGO_DB_NAME", "gob")

try:
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure
except ImportError:
    print("Run from venv: source venv/bin/activate")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_admin_user_production.py <email>")
        print("  e.g. python scripts/set_admin_user_production.py jamie@geekedoutgames.com")
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    try:
        client = MongoClient(MONGO_URI)
        db = client[db_name]
        users = db["users"]
        result = users.update_one(
            {"email": email},
            {"$set": {"role": "admin", "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            print(f"No user found with email: {email} in production DB '{db_name}'.")
            sys.exit(1)
        print(f"Set role=admin for {email} in production (database: {db_name}).")
    except OperationFailure as e:
        if "auth" in str(e).lower() or "8000" in str(e):
            print("MongoDB authentication failed. Check your production MONGO_URI credentials.")
        raise


if __name__ == "__main__":
    main()
