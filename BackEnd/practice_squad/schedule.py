"""Practice Squad schedule generation (regular season + tournament slots)."""

from __future__ import annotations

from typing import Any

from BackEnd.practice_squad.constants import (
    PS_CHAMPIONSHIP_WEEK,
    PS_REGULAR_WEEKS,
    PS_TOURNAMENT_WEEKS,
    REGION_LETTERS,
    TIER_NAMES,
)
from BackEnd.practice_squad.roster import ps_team_id
from BackEnd.tournament import bracket_engine


def _round_robin_pairings(n: int) -> list[list[tuple[int, int]]]:
    """Circle method; n must be even. Returns (n-1) rounds of index pairings."""
    if n % 2 != 0:
        raise ValueError("round robin requires even team count")
    teams = list(range(n))
    rounds: list[list[tuple[int, int]]] = []
    for _ in range(n - 1):
        pairs: list[tuple[int, int]] = []
        for i in range(n // 2):
            pairs.append((teams[i], teams[n - 1 - i]))
        rounds.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return rounds


def _region_index(letter: str) -> int:
    return REGION_LETTERS.index(letter.upper())


def _index_region(idx: int) -> str:
    return REGION_LETTERS[idx]


def build_regular_season_schedule(
    *,
    tiers: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
    include_scrubs: bool = True,
    scrubs_forfeit: dict[str, bool] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """
    Double round-robin across 8 regions per tier, weeks 2–15.
    schedule[str(week)] = list of matchup dicts.
    """
    scrubs_forfeit = scrubs_forfeit or {}
    pairings = _round_robin_pairings(len(REGION_LETTERS))
    schedule: dict[str, list[dict[str, Any]]] = {str(w): [] for w in PS_REGULAR_WEEKS}

    for leg in (0, 1):
        for round_idx, pairs in enumerate(pairings):
            week = PS_REGULAR_WEEKS[round_idx + leg * len(pairings)]
            week_key = str(week)
            for tier in tiers:
                if tier == 6 and not include_scrubs:
                    continue
                for a_idx, b_idx in pairs:
                    region_a = _index_region(a_idx)
                    region_b = _index_region(b_idx)
                    home_region, away_region = (region_a, region_b) if leg == 0 else (region_b, region_a)
                    home_id = ps_team_id(home_region, tier)
                    away_id = ps_team_id(away_region, tier)
                    status = "scheduled"
                    if tier == 6 and (scrubs_forfeit.get(home_region) or scrubs_forfeit.get(away_region)):
                        status = "forfeit"
                    schedule[week_key].append(
                        {
                            "home_team_id": home_id,
                            "away_team_id": away_id,
                            "tier": tier,
                            "week": week,
                            "phase": "regular",
                            "status": status,
                            "game_id": None,
                            "home_score": None,
                            "away_score": None,
                        }
                    )
    return schedule


def init_tier_tournaments(seed_order_by_tier: dict[int, list[str]]) -> dict[str, dict[str, Any]]:
    """Build five tier brackets from seed orders (tier int -> 8 team ids)."""
    out: dict[str, dict[str, Any]] = {}
    for tier in range(1, 6):
        seed_order = seed_order_by_tier.get(tier) or []
        if len(seed_order) < 8:
            continue
        bracket = bracket_engine.generate_bracket(seed_order[:8])
        seeds = {tid: i + 1 for i, tid in enumerate(seed_order[:8])}
        out[str(tier)] = {
            "bracket": bracket,
            "current_round": 1,
            "seeds": seeds,
            "champion": None,
            "tier_name": TIER_NAMES[tier],
        }
    return out


def tournament_games_for_week(
    week: int,
    tournaments: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return matchup slots to play this week from tier brackets."""
    if week not in PS_TOURNAMENT_WEEKS:
        return []
    round_num = week - PS_TOURNAMENT_WEEKS[0] + 1
    round_key = bracket_engine.get_round_name(round_num)
    games: list[dict[str, Any]] = []
    for tier_key, tstate in (tournaments or {}).items():
        bracket = tstate.get("bracket") or {}
        matchups = bracket.get(round_key) or []
        for idx, m in enumerate(matchups):
            if m.get("game_id"):
                continue
            home = m.get("home_team")
            away = m.get("away_team")
            if not home or not away:
                continue
            games.append(
                {
                    "home_team_id": str(home),
                    "away_team_id": str(away),
                    "tier": int(tier_key),
                    "week": week,
                    "phase": "tournament",
                    "round": round_num,
                    "match_index": idx,
                    "status": "scheduled",
                    "game_id": None,
                    "home_score": None,
                    "away_score": None,
                }
            )
    return games


def championship_game_slot(
    *,
    all_americans_champ: str | None,
    all_stars_champ: str | None,
) -> dict[str, Any] | None:
    if not all_americans_champ or not all_stars_champ:
        return None
    return {
        "home_team_id": None,
        "away_team_id": None,
        "tier": 0,
        "week": PS_CHAMPIONSHIP_WEEK,
        "phase": "championship",
        "status": "scheduled",
        "game_id": None,
        "home_score": None,
        "away_score": None,
        "candidates": [all_americans_champ, all_stars_champ],
    }
