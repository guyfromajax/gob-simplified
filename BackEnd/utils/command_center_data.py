"""
Shared command center data building for Franchise and Tournament modes (Phase 5.3).
Produces the common response keys with consistent defaults; callers add mode-specific keys.
No DB access; callers pass resolved team_name, team_id, and team_attrs.
"""
from typing import Any, Dict, Optional

DEFAULT_GRADE = "-"


def build_command_center_base(
    team_name: Optional[str],
    team_id: Optional[str],
    team_attrs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the common command-center response keys used by both Franchise and Tournament.

    Args:
        team_name: User team display name.
        team_id: User team ObjectId string (for consistent navigation).
        team_attrs: Optional dict with team_chemistry, offense, defense, athleticism,
                    and optionally intangibles, prestige, rank (Franchise uses these).

    Returns:
        Dict with keys: team, team_id, team_chemistry, offense, defense, athleticism,
        and optionally intangibles, prestige, rank (if present in team_attrs).
    """
    attrs = team_attrs or {}
    base: Dict[str, Any] = {
        "team": team_name,
        "team_id": team_id,
        "team_chemistry": attrs.get("team_chemistry", 0),
        "offense": attrs.get("offense", DEFAULT_GRADE),
        "defense": attrs.get("defense", DEFAULT_GRADE),
        "athleticism": attrs.get("athleticism", DEFAULT_GRADE),
    }
    if "intangibles" in attrs:
        base["intangibles"] = attrs.get("intangibles", DEFAULT_GRADE)
    if "prestige" in attrs:
        base["prestige"] = attrs.get("prestige", DEFAULT_GRADE)
    if "rank" in attrs:
        base["rank"] = attrs.get("rank", DEFAULT_GRADE)
    return base
