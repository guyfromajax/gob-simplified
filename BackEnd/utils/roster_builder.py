"""
Shared roster building logic for Franchise and Tournament modes (Phase 5.2).
Produces a list of player dicts in the same shape for both modes.
No DB access; callers pass team_player_ids, mode_overrides, and core_players_dict.
"""
from typing import Dict, List, Any

ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]


def _ensure_anchor_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure anchor_* keys exist for display/rating use. Mutates and returns the same dict."""
    for attr_key in ATTR_KEYS:
        if attr_key in attributes and f"anchor_{attr_key}" not in attributes:
            attributes[f"anchor_{attr_key}"] = attributes[attr_key]
    return attributes


def build_roster_players(
    team_player_ids: List[Any],
    mode_overrides: Dict[str, Dict[str, Any]],
    core_players_dict: Dict[str, Dict[str, Any]],
    team_name: str,
) -> List[Dict[str, Any]]:
    """
    Build roster player list from team IDs, mode-specific overrides, and core player data.

    Args:
        team_player_ids: List of player IDs (ObjectId or str) in roster order.
        mode_overrides: Map pid_str -> { first_name?, last_name?, attributes?, position_ratings? }.
                       Franchise: from FPD (meta.first_name, meta.last_name, attributes, position_ratings).
                       Tournament: from tournament.players (merged attributes, position_ratings, name from meta/root/core).
        core_players_dict: Map pid_str -> core player doc (height, weight, jersey, year, attributes, position_ratings).
        team_name: Team name for the "team" field on each player.

    Returns:
        List of player dicts with keys: _id, first_name, last_name, name, team, attributes, position_ratings, height, weight, jersey, year.
    """
    players: List[Dict[str, Any]] = []
    for pid in team_player_ids:
        pid_str = str(pid)
        override = mode_overrides.get(pid_str, {})
        core = core_players_dict.get(pid_str)

        first = override.get("first_name")
        if first is None and core:
            first = core.get("first_name", "")
        if first is None:
            first = ""

        last = override.get("last_name")
        if last is None and core:
            last = core.get("last_name", "")
        if last is None:
            last = ""

        attributes = override.get("attributes")
        if attributes is None and core:
            attributes = (core.get("attributes") or {}).copy()
        else:
            attributes = (attributes or {}).copy()
        _ensure_anchor_attributes(attributes)

        position_ratings = override.get("position_ratings")
        if position_ratings is None and core:
            position_ratings = core.get("position_ratings") or {}
        if position_ratings is None:
            position_ratings = {}

        player = {
            "_id": pid_str,
            "first_name": first,
            "last_name": last,
            "name": f"{first} {last}".strip(),
            "team": team_name,
            "attributes": attributes,
            "position_ratings": position_ratings,
            "height": override.get("height", core.get("height") if core else None),
            "weight": override.get("weight", core.get("weight") if core else None),
            "jersey": override.get("jersey", core.get("jersey", 0) if core else None),
            "year": override.get("year", core.get("year") if core else None),
        }
        players.append(player)
    return players
