"""Shared debug toggles (env + optional query mirrors)."""

from __future__ import annotations

import os


def debug_pc_enabled(query_flag: str | None = None, *, env_name: str = "DEBUG_PC") -> bool:
    """
    Playcall / playbook tracing for GET /api/playbooks and simulate-quarter.

    True when:
    - query_flag is 1 / true / yes (case-insensitive), or
    - env DEBUG_PC (or env_name) is 1 / true / yes.
    """
    # HTTP passes str; direct Python calls to get_playbooks() may leave FastAPI Query() as the default.
    if not isinstance(query_flag, str):
        q = ""
    else:
        q = query_flag.strip().lower()
    if q in ("1", "true", "yes"):
        return True
    return os.getenv(env_name, "").strip().lower() in ("1", "true", "yes")
