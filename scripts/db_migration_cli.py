"""Small CLI adapter for retained one-target migration scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from BackEnd.script_db import connect_script_database

ROOT = Path(__file__).resolve().parents[1]
TARGET_NAMES = {
    "staging": "gob-staging",
    "production": "gob",
    "gob-staging": "gob-staging",
    "gob": "gob",
}


def connect_migration_target(target: str, *, write: bool) -> Any:
    try:
        database_name = TARGET_NAMES[target]
    except KeyError as exc:
        raise ValueError(f"Unsupported database target {target!r}") from exc
    return connect_script_database(
        target=database_name,
        access="write" if write else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
