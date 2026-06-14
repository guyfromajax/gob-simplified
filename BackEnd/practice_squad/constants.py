"""Practice Squad regional games — constants and tier metadata."""

from __future__ import annotations

REGION_LETTERS = list("ABCDEFGH")

# Tier index 1–5 play regular season + tournament; 6 = Scrubs (regular season only).
TIER_NAMES = {
    1: "All-Americans",
    2: "All-Stars",
    3: "Varsity",
    4: "JV",
    5: "Squad",
    6: "Scrubs",
}

PS_REGULAR_WEEKS = tuple(range(2, 16))  # weeks 2–15
PS_TOURNAMENT_WEEKS = (16, 17, 18)
PS_CHAMPIONSHIP_WEEK = 19
PS_ACTIVE_WEEKS = tuple(range(2, 20))  # weeks 2–19

POSITIONS = ("PG", "SG", "SF", "PF", "C")

SCRUBS_MIN_PLAYERS_TO_COMPETE = 5
SCRUBS_ROSTER_SIZE = 12
LOCKED_TIER_ROSTER_SIZE = 12
