"""Shared guards + tagging for the staging load test. STAGING ONLY.

Every piece of data the load test creates is tagged:
  users       email loadtest+<n>@example.com, username loadtest_<n>
  franchises  owned by a tagged user AND name starting "LOADTEST"
Cleanup only ever touches data that passes both checks.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STAGING_BASE_URL = "https://gob-simplified-staging.up.railway.app"
STAGING_DB = "gob-staging"

EMAIL_RE = re.compile(r"^loadtest\+(\d+)@example\.com$")
FRANCHISE_PREFIX = "LOADTEST"
STATE_DIR = Path(__file__).resolve().parent / ".state"  # gitignored: passwords live here
USERS_FILE = STATE_DIR / "users.json"


class LoadTestGuardError(SystemExit):
    pass


def email_for(n: int) -> str:
    return f"loadtest+{int(n)}@example.com"


def username_for(n: int) -> str:
    return f"loadtest_{int(n)}"


def is_tagged_email(email: str) -> bool:
    return bool(EMAIL_RE.match(str(email or "")))


def require_staging_url(base_url: str) -> str:
    url = str(base_url or "").rstrip("/")
    if url != STAGING_BASE_URL:
        raise LoadTestGuardError(f"REFUSED: base URL must be exactly {STAGING_BASE_URL} (got {url!r})")
    return url


def require_staging_db(db_name: str) -> str:
    if db_name != STAGING_DB:
        raise LoadTestGuardError(f"REFUSED: database must be {STAGING_DB!r} (got {db_name!r})")
    return db_name


def require_write_access() -> None:
    if os.environ.get("GOB_DB_ACCESS", "").strip().lower() != "write":
        raise LoadTestGuardError("REFUSED: seed/cleanup writes need process-level GOB_DB_ACCESS=write")


def connect_staging(access: str):
    """Staging connection through the shared script helper (never production)."""
    from BackEnd.script_db import connect_script_database

    require_staging_db(STAGING_DB)
    if access == "write":
        require_write_access()
    conn = connect_script_database(
        target=STAGING_DB,
        access=access,
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    require_staging_db(conn.database.name)
    return conn


def load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    return json.loads(USERS_FILE.read_text())


def save_users(users: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, indent=2))
    os.chmod(USERS_FILE, 0o600)
