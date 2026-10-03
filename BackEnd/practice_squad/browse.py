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


# A game with one of these statuses has a result; "skipped" has none and is left out.
_PLAYED = ("completed", "fallback_completed", "forfeit")


def _ordinal(place: int) -> str:
    if 10 <= place % 100 <= 20:
        return f"{place}th"
    return f"{place}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(place % 10, 'th') }"


def _score(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _team_games(ps_state: dict, ps_team_id: str, extra_completed: list[dict] | None) -> list[dict]:
    """The squad's regular-season games, then any completed tournament games passed in."""
    games: list[dict] = []
    schedule = ps_state.get("schedule") if isinstance(ps_state.get("schedule"), dict) else {}
    for week_key, week_games in schedule.items():
        for game in week_games or []:
            if not isinstance(game, dict):
                continue
            if ps_team_id in (str(game.get("home_team_id") or ""), str(game.get("away_team_id") or "")):
                games.append({**game, "week": _score(game.get("week")) or _score(week_key)})
    for game in extra_completed or []:
        if ps_team_id in (str(game.get("home_team_id") or ""), str(game.get("away_team_id") or "")):
            games.append(dict(game))
    games.sort(key=lambda g: g.get("week") or 0)
    return games


def team_page(
    ps_state: dict | None,
    ps_team_id: str,
    completed_tournament_games: list[dict] | None = None,
) -> dict[str, Any]:
    """A practice squad in the standard team page's shape (``build_team_detail``'s keys).

    Only what a practice squad has: its tier and region, record, place in the tier
    table, results and games ahead. No national rank, conference or streak.
    """
    ps = ps_state if isinstance(ps_state, dict) else {}
    teams = ps.get("teams") if isinstance(ps.get("teams"), dict) else {}
    team = teams.get(ps_team_id) if isinstance(teams.get(ps_team_id), dict) else {}
    try:
        tier = int(team.get("tier") or 0)
    except (TypeError, ValueError):
        tier = 0
    board = ps.get("standings") if isinstance(ps.get("standings"), dict) else {}
    tier_board = board.get(str(tier)) or board.get(tier) or {}
    if not isinstance(tier_board, dict):
        tier_board = {}
    wins, losses = _wins_losses(tier_board.get(ps_team_id))
    order = sorted(
        ((tid, _wins_losses(rec)) for tid, rec in tier_board.items()),
        key=lambda item: (-item[1][0], item[1][1]),
    )
    ids = [str(tid) for tid, _rec in order]
    place = f"{_ordinal(ids.index(ps_team_id) + 1)} of {len(ids)}" if ps_team_id in ids else None

    def _name(team_id: str) -> str:
        other = teams.get(team_id) if isinstance(teams.get(team_id), dict) else {}
        return other.get("display_name") or team_id

    results: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for game in _team_games(ps, ps_team_id, completed_tournament_games):
        home = str(game.get("home_team_id") or "")
        away = str(game.get("away_team_id") or "")
        at_home = home == ps_team_id
        opponent = away if at_home else home
        if not opponent:
            continue
        row: dict[str, Any] = {
            "week": game.get("week"),
            "site": "home" if at_home else "away",
            "opponent_id": opponent,
            "opponent_name": _name(opponent),
        }
        status = str(game.get("status") or "")
        if status in _PLAYED:
            mine = _score(game.get("home_score") if at_home else game.get("away_score"))
            theirs = _score(game.get("away_score") if at_home else game.get("home_score"))
            winner = str(game.get("winner") or "")
            if status == "forfeit":
                letter = "W" if winner == ps_team_id else ("L" if winner else None)
            elif mine is None or theirs is None or mine == theirs:
                letter = None
            else:
                letter = "W" if mine > theirs else "L"
            row.update({
                "team_score": mine,
                "opp_score": theirs,
                "result": letter,
                "forfeit": status == "forfeit",
                "game_id": str(game.get("game_id")) if game.get("game_id") else None,
            })
            results.append(row)
        elif status != "skipped":
            upcoming.append(row)
    return {
        "team_id": ps_team_id,
        "name": team.get("display_name") or ps_team_id,
        "practice_squad": True,
        "tier": tier,
        "tier_label": TIER_NAMES.get(tier) or "",
        "region": str(team.get("region") or "").strip().upper() or None,
        "record": {"wins": wins, "losses": losses},
        "tier_place": place,
        "results": results,
        "upcoming": upcoming,
        "next_game": upcoming[0] if upcoming else None,
    }
