"""Team Builder (Team Mod) feature flag.

Authoring is gated by ``TEAM_BUILDER_ENABLED``. Overlay *resolution* for
franchises that already have a modded program stays live either way — this flag
only blocks creating/editing via Team Builder routes and UI entry points.

Env:
  TEAM_BUILDER_ENABLED=true|false|1|0|yes|no|on|off

Default: enabled (``true``) so local/staging keep working without an explicit var.
Set ``false`` on production until the feature is ready to ship.
"""
from __future__ import annotations

import os


def team_builder_enabled() -> bool:
    raw = (os.getenv("TEAM_BUILDER_ENABLED", "true") or "true").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    # Default / unknown → enabled (explicit false is required to disable).
    return True


def team_builder_disabled_detail() -> str:
    return "Team Builder is not available."
