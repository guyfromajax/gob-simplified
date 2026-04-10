"""
Helpers for team-owned play collections.

During the migration away from name-keyed maps, team plays may be stored as:
- legacy: {play_name: play_data}
- new: {play_id: play_data}

These helpers make callers independent of the storage key.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Iterator, Optional, Tuple


def get_team_play_display_name(storage_key: str, play_data: Dict[str, Any] | None) -> str:
    """Return the best available display name for a team play."""
    if isinstance(play_data, dict):
        name = play_data.get("name")
        if isinstance(name, str) and name:
            return name
    return storage_key


def iter_team_plays(plays: Dict[str, Dict[str, Any]] | None) -> Iterator[Tuple[str, Dict[str, Any], str]]:
    """Iterate team plays while exposing storage key and stable display name."""
    if not isinstance(plays, dict):
        return
    for storage_key, play_data in plays.items():
        if not isinstance(play_data, dict):
            continue
        yield storage_key, play_data, get_team_play_display_name(storage_key, play_data)


def build_team_play_indexes(
    plays: Dict[str, Dict[str, Any]] | None,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Build indexes by storage key, play_id, and play name."""
    by_storage_key: Dict[str, Dict[str, Any]] = {}
    by_play_id: Dict[str, Dict[str, Any]] = {}
    by_play_name: Dict[str, Dict[str, Any]] = {}

    if not isinstance(plays, dict):
        return by_storage_key, by_play_id, by_play_name

    for storage_key, play_data, display_name in iter_team_plays(plays):
        by_storage_key[storage_key] = play_data
        play_id = play_data.get("play_id")
        if play_id:
            by_play_id[str(play_id)] = play_data
        if display_name:
            by_play_name[display_name] = play_data

    return by_storage_key, by_play_id, by_play_name


def resolve_team_play(
    plays: Dict[str, Dict[str, Any]] | None,
    reference: str | None,
) -> Optional[Dict[str, Any]]:
    """Resolve a team play by storage key, play_id, or display name."""
    if not reference or not isinstance(plays, dict):
        return None

    by_storage_key, by_play_id, by_play_name = build_team_play_indexes(plays)
    return (
        by_storage_key.get(reference)
        or by_play_id.get(str(reference))
        or by_play_name.get(reference)
    )
