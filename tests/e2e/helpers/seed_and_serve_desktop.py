#!/usr/bin/env python3
"""Playwright webServer for the desktop profile against SQLite.

Uses the loopback principal and the bundled base league when present.
Does not touch Jamie's Application Support save — writes a throwaway sqlite.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

os.environ["GOB_SQLITE_PATH"] = str(
    Path(os.environ.get("GOB_DESKTOP_E2E_SQLITE") or "/tmp/gob-desktop-e2e.sqlite")
)
league = REPO_ROOT / "base_league.sqlite"
if league.is_file():
    os.environ["GOB_BASE_LEAGUE_SQLITE"] = str(league)
catalog = REPO_ROOT / "catalog.sqlite"
if catalog.is_file():
    os.environ["GOB_CATALOG_SQLITE"] = str(catalog)

from BackEnd.loopback_env import apply_loopback_env

apply_loopback_env()
os.environ["GOB_LOOPBACK_PORT"] = os.environ.get("PORT") or os.environ.get("GOB_LOOPBACK_PORT") or "8767"
os.environ["PORT"] = os.environ["GOB_LOOPBACK_PORT"]

from BackEnd.loopback import main

if __name__ == "__main__":
    main(["--host", "127.0.0.1", "--port", os.environ["GOB_LOOPBACK_PORT"]])
