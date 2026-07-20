"""Practice Squad roster pool gathering and team construction."""

from __future__ import annotations

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any

from BackEnd.practice_squad.constants import (
    LOCKED_TIER_ROSTER_SIZE,
    POSITIONS,
    REGION_LETTERS,
    SCRUBS_MIN_PLAYERS_TO_COMPETE,
    SCRUBS_ROSTER_SIZE,
    TIER_NAMES,
)


def ps_team_id(region: str, tier: int) -> str:
    return f"ps_{region.upper()}_{tier}"


def ps_display_name(region: str, tier: int) -> str:
    return f"Region {region.upper()} {TIER_NAMES[tier]}"


def _best_position_rt(position_ratings: dict[str, Any]) -> int:
    best = 0
    for val in (position_ratings or {}).values():
        try:
            iv = int(float(val))
        except (TypeError, ValueError):
            continue
        if iv > best:
            best = iv
    return best


def _rt_at_position(position_ratings: dict[str, Any], pos: str) -> int:
    try:
        return int(float((position_ratings or {}).get(pos) or 0))
    except (TypeError, ValueError):
        return 0


def _split_recruit_name(name: str) -> tuple[str, str]:
    parts = str(name or "").strip().split(None, 1)
    if not parts:
        return "Recruit", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _fpd_pool_entry(fpd: dict, parent_team_name: str) -> dict[str, Any]:
    meta = fpd.get("meta") or {}
    first = str(meta.get("first_name") or "")
    last = str(meta.get("last_name") or "")
    name = f"{first} {last}".strip() or str(meta.get("name") or "Player")
    pr = fpd.get("position_ratings") or {}
    return {
        "source": "fpd",
        "player_id": str(fpd.get("player_id") or ""),
        "name": name,
        "parent_team_name": parent_team_name,
        "position_ratings": dict(pr),
        "best_rt": _best_position_rt(pr),
        "attributes": dict(fpd.get("attributes") or {}),
        "height": meta.get("height"),
        "weight": meta.get("weight"),
        "year": meta.get("year") or "",
        "archetype": meta.get("archetype") or "",
    }


def _frd_pool_entry(recruit: dict) -> dict[str, Any]:
    name = str(recruit.get("name") or "").strip()
    first, last = _split_recruit_name(name)
    pr = recruit.get("position_ratings") or {}
    return {
        "source": "frd",
        "player_id": str(recruit.get("recruit_id") or ""),
        "name": name or f"{first} {last}".strip(),
        "parent_team_name": None,
        "position_ratings": dict(pr),
        "best_rt": _best_position_rt(pr),
        "attributes": dict(recruit.get("attributes") or {}),
        "height": recruit.get("height"),
        "weight": recruit.get("weight"),
        "year": recruit.get("year") or "",
        "archetype": recruit.get("archetype") or "",
        "first_name": first,
        "last_name": last,
    }


def gather_region_pool(
    region: str,
    *,
    team_ids_in_region: list[str],
    ftd_by_team: dict[str, dict],
    fpd_by_player: dict[str, dict],
    recruits_in_region: list[dict],
    team_name_map: dict[str, str],
) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    seen: set[str] = set()

    for tid in team_ids_in_region:
        ftd = ftd_by_team.get(str(tid)) or {}
        for pid in ftd.get("training_squad_players") or []:
            pid_str = str(pid)
            if pid_str in seen:
                continue
            fpd = fpd_by_player.get(pid_str)
            if not fpd:
                continue
            seen.add(pid_str)
            parent = team_name_map.get(str(tid), "")
            pool.append(_fpd_pool_entry(fpd, parent))

    for recruit in recruits_in_region:
        rid = str(recruit.get("recruit_id") or "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        pool.append(_frd_pool_entry(recruit))

    return pool


def _pick_best_at_position(candidates: list[dict], pos: str) -> dict | None:
    eligible = [p for p in candidates if _rt_at_position(p.get("position_ratings") or {}, pos) > 0]
    if not eligible:
        return None
    eligible.sort(
        key=lambda p: (
            -_rt_at_position(p.get("position_ratings") or {}, pos),
            -int(p.get("best_rt") or 0),
            p.get("name") or "",
        )
    )
    return eligible[0]


def _pick_best_overall(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda p: (-int(p.get("best_rt") or 0), p.get("name") or ""),
    )
    return ranked[0]


def build_locked_tier_roster(pool: list[dict]) -> list[dict]:
    """Build a 12-man roster using the tier draft rules; mutates pool in place."""
    working = list(pool)
    roster: list[dict] = []
    pos_order = list(POSITIONS)
    random.shuffle(pos_order)

    for pos in pos_order:
        for _ in range(2):
            pick = _pick_best_at_position(working, pos)
            if pick is None:
                pick = _pick_best_overall(working)
            if pick is None:
                break
            roster.append(pick)
            working.remove(pick)

    while len(roster) < LOCKED_TIER_ROSTER_SIZE and working:
        pick = _pick_best_overall(working)
        if pick is None:
            break
        roster.append(pick)
        working.remove(pick)

    for p in roster:
        if p in pool:
            pool.remove(p)

    return [_roster_slot(p) for p in roster[:LOCKED_TIER_ROSTER_SIZE]]


def _roster_slot(player: dict) -> dict[str, Any]:
    return {
        "source": player.get("source"),
        "player_id": player.get("player_id"),
        "name": player.get("name"),
        "parent_team_name": player.get("parent_team_name"),
        "best_rt": int(player.get("best_rt") or 0),
    }


def build_scrubs_week_roster(scrubs_pool: list[dict]) -> list[dict]:
    if len(scrubs_pool) < SCRUBS_MIN_PLAYERS_TO_COMPETE:
        return []
    size = min(SCRUBS_ROSTER_SIZE, len(scrubs_pool))
    picked = random.sample(scrubs_pool, size)
    return [_roster_slot(p) for p in picked]


def build_all_region_rosters(
    *,
    region_team_map: dict[str, list[str]],
    ftd_by_team: dict[str, dict],
    fpd_by_player: dict[str, dict],
    recruits_by_region: dict[str, list[dict]],
    team_name_map: dict[str, str],
) -> tuple[dict[str, dict], dict[str, list[dict]], bool]:
    """
    Returns (teams dict, scrubs_pool_by_region, scrubs_forfeit_by_region).
    teams keyed by ps_team_id.
    """
    teams: dict[str, dict] = {}
    scrubs_pools: dict[str, list[dict]] = {}
    scrubs_forfeit: dict[str, bool] = {}

    for region in REGION_LETTERS:
        team_ids = region_team_map.get(region) or []
        pool = gather_region_pool(
            region,
            team_ids_in_region=[str(t) for t in team_ids],
            ftd_by_team=ftd_by_team,
            fpd_by_player=fpd_by_player,
            recruits_in_region=recruits_by_region.get(region) or [],
            team_name_map=team_name_map,
        )

        scrubs_pool: list[dict] = []

        for tier in range(1, 6):
            tid = ps_team_id(region, tier)
            roster = build_locked_tier_roster(pool)
            teams[tid] = {
                "team_id": tid,
                "region": region,
                "tier": tier,
                "tier_name": TIER_NAMES[tier],
                "display_name": ps_display_name(region, tier),
                "roster": roster,
            }

        scrubs_pool = list(pool)
        scrubs_pools[region] = scrubs_pool
        scrubs_forfeit[region] = len(scrubs_pool) < SCRUBS_MIN_PLAYERS_TO_COMPETE

        tid_scrubs = ps_team_id(region, 6)
        teams[tid_scrubs] = {
            "team_id": tid_scrubs,
            "region": region,
            "tier": 6,
            "tier_name": TIER_NAMES[6],
            "display_name": ps_display_name(region, 6),
            "roster": [],
        }

    return teams, scrubs_pools, scrubs_forfeit
