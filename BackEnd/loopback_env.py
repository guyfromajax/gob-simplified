"""Loopback / desktop profile flags. Import-safe: stdlib only."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_loopback() -> bool:
    return (
        os.environ.get("GOB_LOOPBACK") == "1"
        or os.environ.get("GOB_BUILD_PROFILE") == "desktop"
    )


def default_sqlite_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "GOB" / "local.sqlite"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "GOB" / "local.sqlite"
    return Path.home() / ".local" / "share" / "GOB" / "local.sqlite"


def apply_loopback_env() -> None:
    """Set loopback defaults. Call before importing the FastAPI app or the store.

    ENVIRONMENT=development so FastAPI mounts static files and SQLite remotes
    refuse (not mongomock). MONGO_* satisfies env_config only — local collections
    live in the SQLite file.
    """
    os.environ["GOB_LOOPBACK"] = "1"
    os.environ["GOB_BUILD_PROFILE"] = "desktop"
    os.environ["GOB_PERSISTENCE"] = "sqlite"
    os.environ["ENVIRONMENT"] = "development"
    os.environ.setdefault("GOB_SQLITE_PATH", str(default_sqlite_path()))
    # Desktop default is spawn, not threads. The hosted kill-switch defaults
    # to "0"; without this setdefault the shipped app pays ~136s/week.
    os.environ.setdefault("FRANCHISE_CPU_SIM_USE_POOL", "1")
    # Placeholders for env_config only — force a matching pair so a leftover
    # test/web export cannot leave URI=staging and NAME=test for spawn children.
    os.environ["MONGO_URI"] = "mongodb://127.0.0.1:27017/gob-staging"
    os.environ["MONGO_DB_NAME"] = "gob-staging"
    os.environ.pop("SENTRY_DSN", None)
    os.environ.pop("GOB_DB_MODE", None)
