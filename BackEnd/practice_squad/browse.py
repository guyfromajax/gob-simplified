"""Browse shaping for the Practice Squad league pages.

Game results stay on the franchise ``practice_squad`` blob. This module only
orders and labels that blob the way the standings page already did.
"""

from __future__ import annotations

from typing import Any

from BackEnd.practice_squad.constants import TIER_NAMES

# Tiers the standings page shows. Scrubs (6) stay on the blob and off the table.
DISPLAY_TIERS = (1, 2, 3, 4, 5)
PS_FIRST_WEEK = 2
PS_LAST_WEEK = 19


def ps_open_week(franchise_week: Any) -> int:
    """Week the schedule stepper should open on. Clamped to the PS slate."""
    try:
        week = int(franchise_week or 1)
    except (TypeError, ValueError):
        week = 1
    if week < PS_FIRST_WEEK:
        return PS_FIRST_WEEK
    if week > PS_LAST_WEEK:
        return PS_LAST_WEEK
    return week


def _wins_losses(record: Any) -> tuple[int, int]:
    rec = record if isinstance(record, dict) else {}
    try:
        wins = int(rec.get("w") or 0)
    except (TypeError, ValueError):
        wins = 0
    try:
        losses = int(rec.get("l") or 0)
    except (TypeError, ValueError):
        losses = 0
    return wins, losses


def win_pct(wins: int, losses: int) -> float:
    """Same rounding as franchise standings ``pct``: three decimals, 0.0 if unplayed."""
    played = wins + losses
    if played <= 0:
        return 0.0
    return round(wins / played, 3)


def user_ps_team_id(region: str, tier: int) -> str:
    return f"ps_{str(region or '').upper()}_{int(tier)}"


def standings_tiers(
    standings: dict | None,
    teams: dict | None,
    user_region: str,
) -> list[dict[str, Any]]:
    """Tiers 1–5, each row sorted wins desc then losses asc (the page's order)."""
    board = standings if isinstance(standings, dict) else {}
    roster = teams if isinstance(teams, dict) else {}
    region = str(user_region or "").strip().upper()
    tiers: list[dict[str, Any]] = []
    for tier in DISPLAY_TIERS:
        raw = board.get(str(tier)) or board.get(tier) or {}
        if not isinstance(raw, dict):
            raw = {}
        rows = []
        for team_id, record in raw.items():
            tid = str(team_id)
            wins, losses = _wins_losses(record)
            team = roster.get(tid) if isinstance(roster.get(tid), dict) else {}
            rows.append({
                "team_id": tid,
                "name": team.get("display_name") or tid,
                "w": wins,
                "l": losses,
                "win_pct": win_pct(wins, losses),
                "is_user": bool(region) and tid == user_ps_team_id(region, tier),
            })
        rows.sort(key=lambda row: (-row["w"], row["l"]))
        tiers.append({
            "tier": str(tier),
            "label": TIER_NAMES[tier],
            "rows": rows,
        })
    return tiers
