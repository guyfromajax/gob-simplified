"""
Team slug: normalized identifier for asset paths and folder names.
Rules: lowercase, spaces → underscores, remove punctuation, no hyphens.
Used by frontend for /images/teams/{slug}/{slug}_{asset}.ext paths.
"""
import re


def get_team_slug(team_name: str) -> str:
    """
    Derive team_slug from team display name.
    Lowercase, spaces → underscores, remove punctuation (apostrophes, periods), hyphens → underscores.
    """
    if not team_name or not isinstance(team_name, str):
        return "general"
    s = team_name.strip().lower()
    s = re.sub(r"['.]", "", s)  # remove apostrophes and periods
    s = s.replace("-", " ").replace("  ", " ").strip()
    s = s.replace(" ", "_")
    return s if s else "general"
