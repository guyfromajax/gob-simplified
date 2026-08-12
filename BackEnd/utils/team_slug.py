"""
Display-name → path slug, and core name → stored team_id lookup.

Identity keys are ObjectIds and stored ``teams.team_id`` (e.g. ``QUEENS_GUARD``,
``couer_d_alene``). Apostrophe conventions in stored slugs are not uniform, so
**do not derive** a team_id when a core row exists — look it up.

``slug_from_display_name`` remains for custom programs (no stored slug) and for
FE asset-path parity. Identity boundaries must call ``team_id_for_display_name``.
"""
from __future__ import annotations

import re
import threading
from typing import Optional

_NAME_TO_TEAM_ID: dict[str, str] | None = None
_NAME_TO_TEAM_ID_LOCK = threading.Lock()


def slug_from_display_name(team_name: str | None) -> str:
    """
    Derive path slug from a team display name (custom / asset fallback).

    ``"Queen's Guard"`` → ``queens_guard``.
    Empty / non-string → ``general``.
    Must match FrontEnd ``nameToTeamSlug``.
    """
    if not team_name or not isinstance(team_name, str):
        return "general"
    s = team_name.strip().lower()
    s = re.sub(r"['.]", "", s)  # remove apostrophes and periods
    s = s.replace("-", " ").replace("  ", " ").strip()
    s = s.replace(" ", "_")
    return s if s else "general"


# Back-compat alias.
get_team_slug = slug_from_display_name


def _load_name_to_team_id_map() -> dict[str, str]:
    """Casefolded display name → stored ``teams.team_id`` (core collection)."""
    global _NAME_TO_TEAM_ID
    if _NAME_TO_TEAM_ID is not None:
        return _NAME_TO_TEAM_ID
    with _NAME_TO_TEAM_ID_LOCK:
        if _NAME_TO_TEAM_ID is not None:
            return _NAME_TO_TEAM_ID
        mapping: dict[str, str] = {}
        try:
            from BackEnd.db import teams_collection

            for doc in teams_collection.find({}, {"name": 1, "team_id": 1}):
                name = doc.get("name")
                tid = doc.get("team_id")
                if not name or not tid:
                    continue
                mapping[str(name).strip().casefold()] = str(tid)
        except Exception:
            mapping = {}
        _NAME_TO_TEAM_ID = mapping
        return mapping


def clear_name_to_team_id_cache() -> None:
    """Test helper — drop the cached name→team_id map."""
    global _NAME_TO_TEAM_ID
    with _NAME_TO_TEAM_ID_LOCK:
        _NAME_TO_TEAM_ID = None


def team_id_for_display_name(team_name: str | None) -> Optional[str]:
    """
    Resolve a core display name to its stored ``teams.team_id``.

    Returns None for unknown / custom names (no stored slug) — callers should
    fall back to ``slug_from_display_name`` only for custom chrome paths, not
    for identity matching against the 128.
    """
    if not team_name or not isinstance(team_name, str):
        return None
    key = team_name.strip().casefold()
    if not key:
        return None
    return _load_name_to_team_id_map().get(key)


def path_slug_for_display_name(team_name: str | None) -> str:
    """
    On-disk / path key for a display name.

    Core: stored ``teams.team_id`` (lowercased). Custom: ``slug_from_display_name``.
    """
    stored = team_id_for_display_name(team_name)
    if stored:
        return stored.lower()
    return slug_from_display_name(team_name)


def identity_slugs_for_display_name(team_name: str | None) -> list[str]:
    """
    Tokens to try when matching a display name to a stored slug / path key.

    Core teams: stored ``team_id`` plus lower/upper variants (authoritative).
    Custom / unknown: ``slug_from_display_name`` only.
    """
    if not team_name:
        return []
    stored = team_id_for_display_name(team_name)
    if stored:
        out = [stored]
        lower = stored.lower()
        upper = stored.upper()
        if lower not in out:
            out.append(lower)
        if upper not in out:
            out.append(upper)
        return out
    derived = slug_from_display_name(team_name)
    if not derived or derived == "general":
        return []
    return [derived, derived.upper()]
