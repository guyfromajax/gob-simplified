import logging
import random
from typing import Any

from bson import ObjectId

from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.constants import computer_game_constants as cgc
from BackEnd.db import (
    db,
    franchise_players_data_collection,
    franchise_team_data_collection,
)
from BackEnd.utils.game_id_utils import generate_game_id
from BackEnd.utils.roster_builder import build_roster_players

logger = logging.getLogger(__name__)

ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]
POSITION_KEYS = ["PG", "SG", "SF", "PF", "C"]
FALLBACK_HEIGHT = 63
FALLBACK_ATTR = 20
FALLBACK_POS_RATING = 20
TEAM_MINUTES_TOTAL = 160
MAX_PLAYER_MINUTES = 32


def _normalize_constants() -> dict[str, float]:
    return {
        "points": float(cgc.TEAM_POINTS),
        "FGM": float(cgc.TEAM_FGM),
        "FGA": float(cgc.TEAM_FGA),
        "FG_pct": float(cgc.TEAM_FG_PCT) / 100.0,
        "3PTM": float(cgc.TEAM_3PT_MADE),
        "3PTA": float(cgc.TEAM_3PTA),
        "3PT_pct": float(cgc.TEAM_3PT_PCT) / 100.0,
        "FTM": float(cgc.TEAM_FT_MADE),
        "FTA": float(cgc.TEAM_FTA),
        "FT_pct": float(cgc.TEAM_FT_PCT) / 100.0,
        "total_rebounds": float(cgc.TEAM_REB),
        "OREB": float(cgc.TEAM_OREB),
        "DREB": float(cgc.TEAM_DREB),
        "assists": float(cgc.TEAM_AST),
        "steals": float(cgc.TEAM_STL),
        "blocks": float(cgc.TEAM_BLK),
        "fouls": float(cgc.TEAM_FOUL),
        "turnovers": float(cgc.TEAM_TURNOVER),
    }


def _normalize_player(player: dict[str, Any]) -> dict[str, Any]:
    player = dict(player)
    pid = str(player.get("_id") or "")
    attrs = dict(player.get("attributes") or {})
    ratings = dict(player.get("position_ratings") or {})
    missing = []
    for key in ATTR_KEYS:
        if not isinstance(attrs.get(key), (int, float)):
            attrs[key] = FALLBACK_ATTR
            missing.append(f"attributes.{key}")
    for key in POSITION_KEYS:
        if not isinstance(ratings.get(key), (int, float)):
            ratings[key] = FALLBACK_POS_RATING
            missing.append(f"position_ratings.{key}")
    height = player.get("height")
    if not isinstance(height, (int, float)):
        height = FALLBACK_HEIGHT
        missing.append("height")
    if missing:
        logger.error(
            "[DISTANT-SIM] Missing player data for player_id=%s; using fallbacks for %s",
            pid or "<unknown>",
            ", ".join(missing),
        )
    player["attributes"] = attrs
    player["position_ratings"] = ratings
    player["height"] = int(height)
    return player


def _best_position_key(player: dict[str, Any]) -> str:
    ratings = player.get("position_ratings") or {}
    return max(POSITION_KEYS, key=lambda pos: ratings.get(pos, 0))


def identify_starters(players: list[dict[str, Any]]) -> tuple[set[str], dict[str, str]]:
    positions = POSITION_KEYS.copy()
    random.shuffle(positions)
    starters: dict[str, str] = {}
    assigned: set[str] = set()
    for pos in positions:
        best_player = None
        best_rating = -1
        for player in players:
            pid = str(player["_id"])
            if pid in assigned:
                continue
            rating = player.get("position_ratings", {}).get(pos, 0)
            if rating > best_rating:
                best_rating = rating
                best_player = pid
        if best_player:
            starters[pos] = best_player
            assigned.add(best_player)
    player_to_pos = {pid: pos for pos, pid in starters.items()}
    return set(assigned), player_to_pos


def _rebalance_integer_totals(
    values: dict[str, int],
    target_total: int,
    *,
    minimums: dict[str, int] | None = None,
    maximums: dict[str, int] | None = None,
    preferred_order: list[str] | None = None,
) -> dict[str, int]:
    minimums = minimums or {}
    maximums = maximums or {}
    order = preferred_order or list(values.keys())
    current = sum(values.values())
    diff = target_total - current
    if diff == 0:
        return values

    if diff > 0:
        while diff > 0:
            progressed = False
            for pid in order:
                max_allowed = maximums.get(pid)
                if max_allowed is not None and values[pid] >= max_allowed:
                    continue
                values[pid] += 1
                diff -= 1
                progressed = True
                if diff == 0:
                    break
            if not progressed:
                break
    else:
        while diff < 0:
            progressed = False
            for pid in reversed(order):
                min_allowed = minimums.get(pid, 0)
                if values[pid] <= min_allowed:
                    continue
                values[pid] -= 1
                diff += 1
                progressed = True
                if diff == 0:
                    break
            if not progressed:
                break
    return values


def distribute_minutes(players: list[dict[str, Any]], starters: set[str]) -> dict[str, int]:
    minutes: dict[str, int] = {}
    for player in players:
        pid = str(player["_id"])
        if pid in starters:
            roll = random.random()
            if roll < 0.10:
                base = random.randint(14, 18)
            elif roll < 0.20:
                base = random.randint(28, 32)
            else:
                base = random.randint(22, 27)
        else:
            roll = random.random()
            if roll < 0.10:
                base = random.randint(0, 3)
            elif roll < 0.20:
                base = random.randint(14, 20)
            else:
                base = random.randint(5, 12)
        minutes[pid] = base

    total = sum(minutes.values()) or 1
    normalized = {
        pid: round((val / total) * TEAM_MINUTES_TOTAL)
        for pid, val in minutes.items()
    }
    minimums = {pid: 0 for pid in normalized}
    maximums = {pid: MAX_PLAYER_MINUTES for pid in normalized}
    preferred = sorted(normalized, key=lambda pid: (pid not in starters, -normalized[pid]))
    for pid in list(normalized.keys()):
        normalized[pid] = max(minimums[pid], min(maximums[pid], normalized[pid]))
    return _rebalance_integer_totals(
        normalized,
        TEAM_MINUTES_TOTAL,
        minimums=minimums,
        maximums=maximums,
        preferred_order=preferred,
    )


def apply_minutes_scaling(weights: dict[str, float], minutes: dict[str, int]) -> dict[str, float]:
    return {
        pid: weight * (minutes.get(pid, 0) / MAX_PLAYER_MINUTES)
        for pid, weight in weights.items()
    }


def get_variance_multiplier() -> float:
    return random.uniform(0.70, 1.30)


def distribute_stat(
    players: list[dict[str, Any]],
    weights: dict[str, float],
    team_total: int,
    minutes: dict[str, int],
) -> dict[str, int]:
    if team_total <= 0:
        return {str(player["_id"]): 0 for player in players}

    player_ids = [str(player["_id"]) for player in players]
    scaled_weights = apply_minutes_scaling(weights, minutes)
    total_weight = sum(max(0.0, scaled_weights.get(pid, 0.0)) for pid in player_ids)
    if total_weight <= 0:
        fallback_ids = [pid for pid in player_ids if minutes.get(pid, 0) > 0] or player_ids
        equal = team_total / max(1, len(fallback_ids))
        raw = {pid: (equal if pid in fallback_ids else 0.0) for pid in player_ids}
    else:
        raw = {
            pid: (max(0.0, scaled_weights.get(pid, 0.0)) / total_weight) * team_total
            for pid in player_ids
        }

    varied = {pid: raw.get(pid, 0.0) * get_variance_multiplier() for pid in player_ids}
    varied_total = sum(varied.values()) or 1.0
    final = {pid: round((varied[pid] / varied_total) * team_total) for pid in player_ids}
    preferred = sorted(
        player_ids,
        key=lambda pid: (minutes.get(pid, 0), weights.get(pid, 0.0)),
        reverse=True,
    )
    return _rebalance_integer_totals(final, team_total, preferred_order=preferred)


def calculate_player_scoring_weight(player: dict[str, Any]) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos
    backcourt_blend = (pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)) / total_pos
    inside_score = attrs.get("SC", 0) * (0.5 + 0.5 * frontcourt_blend)
    outside_score = attrs.get("SH", 0) * (0.5 + 0.5 * backcourt_blend)
    ft_score = attrs.get("FT", 0) * 0.3
    return inside_score + outside_score + ft_score


def simulate_team_points(
    players: list[dict[str, Any]],
    team_total: int,
    minutes: dict[str, int],
) -> dict[str, int]:
    weights = {str(p["_id"]): calculate_player_scoring_weight(p) for p in players}
    return distribute_stat(players, weights, team_total, minutes)


def calculate_team_shooting_targets(team_points: int, constants: dict[str, float]) -> dict[str, int]:
    ft_pct_of_points = constants["FTM"] / max(1.0, constants["points"])
    ft_made = round(team_points * ft_pct_of_points * random.uniform(0.85, 1.15))
    ft_made = max(0, ft_made)

    ft_pct = constants["FT_pct"] * random.uniform(0.90, 1.10)
    ft_attempts = round(ft_made / ft_pct) if ft_pct > 0 else 0

    fg_points = max(0, team_points - ft_made)
    fg_den = max(1.0, constants["points"] - constants["FTM"])
    three_pt_pct_of_fg = (constants["3PTM"] * 3.0) / fg_den
    three_pt_points = round(fg_points * three_pt_pct_of_fg * random.uniform(0.80, 1.20))
    three_pt_points = max(0, min(fg_points, three_pt_points))
    two_pt_points = max(0, fg_points - three_pt_points)

    three_pt_made = round(three_pt_points / 3)
    two_pt_made = round(two_pt_points / 2)
    fg_made = two_pt_made + three_pt_made

    fg_pct = constants["FG_pct"] * random.uniform(0.92, 1.08)
    fg_attempts = round(fg_made / fg_pct) if fg_pct > 0 else 0

    three_pt_pct = constants["3PT_pct"] * random.uniform(0.90, 1.10)
    three_pt_attempts = round(three_pt_made / three_pt_pct) if three_pt_pct > 0 else 0

    implied_points = (two_pt_made * 2) + (three_pt_made * 3) + ft_made
    drift = team_points - implied_points
    if drift != 0:
        ft_made = max(0, ft_made + drift)
        ft_attempts = max(ft_made, round(ft_made / ft_pct) if ft_pct > 0 else ft_made)

    fg_attempts = max(fg_made, three_pt_attempts, fg_attempts)
    three_pt_attempts = max(three_pt_made, three_pt_attempts)
    ft_attempts = max(ft_made, ft_attempts)
    return {
        "FGM": max(0, fg_made),
        "FGA": max(0, fg_attempts),
        "3PTM": max(0, three_pt_made),
        "3PTA": max(0, three_pt_attempts),
        "2PTM": max(0, two_pt_made),
        "FTM": max(0, ft_made),
        "FTA": max(0, ft_attempts),
        "fg_missed": max(0, fg_attempts - fg_made),
        "ft_missed": max(0, ft_attempts - ft_made),
        "total_missed": max(0, (fg_attempts - fg_made) + (ft_attempts - ft_made)),
    }


def calculate_team_rebounds(shooting: dict[str, int], constants: dict[str, float]) -> dict[str, int]:
    unrebounded = random.randint(2, 5)
    total_reboundable = max(0, shooting["total_missed"] - unrebounded)
    oreb_rate = constants["OREB"] / max(1.0, constants["total_rebounds"])
    oreb_rate_varied = max(0.0, min(1.0, oreb_rate * random.uniform(0.85, 1.15)))
    total_rebounds = round(total_reboundable * random.uniform(0.90, 1.10))
    oreb = round(total_rebounds * oreb_rate_varied)
    dreb = total_rebounds - oreb
    return {
        "total_rebounds": max(0, total_rebounds),
        "OREB": max(0, oreb),
        "DREB": max(0, dreb),
        "total_reboundable": max(0, total_reboundable),
    }


def reconcile_rebounds(team_a: dict[str, int], team_b: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    team_a_total = min(team_a["total_rebounds"], team_b["total_reboundable"])
    team_b_total = min(team_b["total_rebounds"], team_a["total_reboundable"])
    team_a_oreb = min(team_a["OREB"], team_a_total)
    team_b_oreb = min(team_b["OREB"], team_b_total)
    return (
        {"total_rebounds": team_a_total, "OREB": team_a_oreb, "DREB": max(0, team_a_total - team_a_oreb)},
        {"total_rebounds": team_b_total, "OREB": team_b_oreb, "DREB": max(0, team_b_total - team_b_oreb)},
    )


def calculate_team_steals(constants: dict[str, float]) -> int:
    mean = constants["steals"]
    return round(max(0.0, random.gauss(mean, mean * 0.25)))


def calculate_team_blocks(constants: dict[str, float], opponent_fga: int) -> int:
    mean = constants["blocks"]
    return min(opponent_fga, round(max(0.0, random.gauss(mean, mean * 0.30))))


def calculate_team_assists(shooting: dict[str, int], constants: dict[str, float]) -> int:
    assist_rate = constants["assists"] / max(1.0, constants["FGM"])
    varied_rate = min(0.95, assist_rate * random.uniform(0.85, 1.15))
    return max(0, round(shooting["FGM"] * varied_rate))


def calculate_team_turnovers(constants: dict[str, float], opponent_steals: int) -> int:
    mean = constants["turnovers"]
    total = round(max(0.0, random.gauss(mean, mean * 0.20)))
    return max(total, opponent_steals)


def calculate_team_fouls(constants: dict[str, float], opponent_fta: int, minutes: dict[str, int]) -> int:
    mean = constants["fouls"]
    total = round(max(0.0, random.gauss(mean, mean * 0.15)))
    fta_implied = round(opponent_fta / 0.95) if opponent_fta > 0 else total
    total = round((total + fta_implied) / 2)
    active_players = sum(1 for val in minutes.values() if val > 0)
    return max(0, min(total, active_players * 5))


def calculate_player_rebound_weight(player: dict[str, Any]) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    height_norm = (player.get("height", FALLBACK_HEIGHT) - 66) / (84 - 66)
    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos
    return (
        attrs.get("RB", 0) * 1.0
        + attrs.get("ST", 0) * 0.4
        + height_norm * 30
    ) * (0.6 + 0.8 * frontcourt_blend)


def calculate_player_steal_weight(player: dict[str, Any]) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    total_pos = sum(pos.values()) or 1
    backcourt_blend = (pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)) / total_pos
    return (attrs.get("OD", 0) + attrs.get("AG", 0) * 0.5) * (0.6 + 0.8 * backcourt_blend)


def calculate_player_block_weight(player: dict[str, Any]) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    height_norm = (player.get("height", FALLBACK_HEIGHT) - 66) / (84 - 66)
    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos
    return (attrs.get("ID", 0) + height_norm * 40) * (0.4 + 1.2 * frontcourt_blend)


def calculate_player_assist_weight(player: dict[str, Any]) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    total_pos = sum(pos.values()) or 1
    backcourt_blend = (pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)) / total_pos
    pg_blend = pos.get("PG", 0) / total_pos
    return (
        attrs.get("IQ", 0) * 1.0
        + attrs.get("PS", 0) * 0.8
        + attrs.get("BH", 0) * 0.5
    ) * (0.4 + 0.8 * backcourt_blend + 0.4 * pg_blend)


def calculate_player_turnover_weight(player: dict[str, Any]) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    total_pos = sum(pos.values()) or 1
    backcourt_blend = (pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)) / total_pos
    return (
        (100 - attrs.get("BH", 50)) * 0.6
        + (100 - attrs.get("IQ", 50)) * 0.4
    ) * (0.5 + 0.8 * backcourt_blend)


def calculate_player_foul_weight(player: dict[str, Any]) -> float:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    height_norm = (player.get("height", FALLBACK_HEIGHT) - 66) / (84 - 66)
    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos
    return (
        attrs.get("ST", 0) * 0.5
        + height_norm * 20
        + (100 - attrs.get("IQ", 50)) * 0.3
    ) * (0.6 + 0.8 * frontcourt_blend)


def calculate_player_shot_profile(player: dict[str, Any]) -> dict[str, float]:
    attrs = player.get("attributes", {})
    pos = player.get("position_ratings", {})
    total_pos = sum(pos.values()) or 1
    frontcourt_blend = (pos.get("PF", 0) + pos.get("C", 0)) / total_pos
    backcourt_blend = (pos.get("PG", 0) + pos.get("SG", 0) + pos.get("SF", 0)) / total_pos
    inside = attrs.get("SC", 0) * (0.5 + 0.5 * frontcourt_blend)
    outside = attrs.get("SH", 0) * (0.5 + 0.5 * backcourt_blend)
    ft = attrs.get("FT", 0) * 0.3
    total = inside + outside + ft or 1.0
    return {
        "inside_pct": inside / total,
        "outside_pct": outside / total,
        "ft_pct": ft / total,
    }


def calculate_player_fg_pct(player: dict[str, Any], shot_profile: dict[str, float]) -> float:
    attrs = player.get("attributes", {})
    sc_fg_pct = 0.30 + (attrs.get("SC", 0) / 100.0) * 0.35
    sh_fg_pct = 0.28 + (attrs.get("SH", 0) / 100.0) * 0.25
    blended = sc_fg_pct * shot_profile["inside_pct"] + sh_fg_pct * shot_profile["outside_pct"]
    return max(0.28, min(0.70, blended * random.uniform(0.92, 1.08)))


def calculate_player_3pt_pct(player: dict[str, Any]) -> float:
    base_pct = 0.20 + (player.get("attributes", {}).get("SH", 0) / 100.0) * 0.30
    return max(0.15, min(0.55, base_pct * random.uniform(0.88, 1.12)))


def calculate_player_ft_pct(player: dict[str, Any]) -> float:
    base_pct = 0.45 + (player.get("attributes", {}).get("FT", 0) / 100.0) * 0.50
    return max(0.40, min(0.98, base_pct * random.uniform(0.93, 1.07)))


def calculate_player_shooting_breakdown(
    player: dict[str, Any],
    player_points: int,
    shot_profile: dict[str, float],
    player_minutes: int,
) -> dict[str, int]:
    if player_points <= 0 or player_minutes == 0:
        return {"FGM": 0, "FGA": 0, "3PTM": 0, "3PTA": 0, "2PTM": 0, "FTM": 0, "FTA": 0}

    ft_points = round(player_points * shot_profile["ft_pct"])
    fg_points = max(0, player_points - ft_points)
    ft_pct = calculate_player_ft_pct(player)
    ft_made = max(0, ft_points)
    ft_attempts = round(ft_made / ft_pct) if ft_pct > 0 else 0

    three_pt_points = round(fg_points * shot_profile["outside_pct"])
    two_pt_points = max(0, fg_points - three_pt_points)
    three_pt_made = round(three_pt_points / 3)
    two_pt_made = round(two_pt_points / 2)
    fg_made = two_pt_made + three_pt_made

    fg_pct = calculate_player_fg_pct(player, shot_profile)
    three_pt_pct = calculate_player_3pt_pct(player)
    fg_attempts = round(fg_made / fg_pct) if fg_pct > 0 else 0
    three_pt_attempts = round(three_pt_made / three_pt_pct) if three_pt_pct > 0 else 0

    implied_points = two_pt_made * 2 + three_pt_made * 3 + ft_made
    drift = player_points - implied_points
    if drift != 0:
        ft_made = max(0, ft_made + drift)
        ft_attempts = max(ft_made, round(ft_made / ft_pct) if ft_pct > 0 else ft_made)

    fg_attempts = max(fg_made, three_pt_attempts, fg_attempts)
    three_pt_attempts = max(three_pt_made, three_pt_attempts)
    return {
        "FGM": max(0, fg_made),
        "FGA": max(0, fg_attempts),
        "3PTM": max(0, three_pt_made),
        "3PTA": max(0, three_pt_attempts),
        "2PTM": max(0, two_pt_made),
        "FTM": max(0, ft_made),
        "FTA": max(0, ft_attempts),
    }


def _preferred_player_order(
    player_stats: dict[str, dict[str, int]],
    minutes: dict[str, int],
    players_by_id: dict[str, dict[str, Any]],
    *,
    stat_hint: str = "PTS",
) -> list[str]:
    def _score(pid: str) -> tuple[int, int, int]:
        stats = player_stats.get(pid, {})
        return (
            minutes.get(pid, 0),
            stats.get(stat_hint, 0),
            max(players_by_id.get(pid, {}).get("position_ratings", {}).values() or [0]),
        )
    return sorted(player_stats.keys(), key=_score, reverse=True)


def _adjust_stat_total(
    player_stats: dict[str, dict[str, int]],
    target_total: int,
    stat: str,
    *,
    minimum_stat: str | None = None,
    order: list[str],
) -> None:
    minimums = {pid: player_stats[pid].get(minimum_stat, 0) if minimum_stat else 0 for pid in player_stats}
    current = {pid: player_stats[pid].get(stat, 0) for pid in player_stats}
    adjusted = _rebalance_integer_totals(current, target_total, minimums=minimums, preferred_order=order)
    for pid, value in adjusted.items():
        player_stats[pid][stat] = value


def reconcile_team_shooting(
    player_stats: dict[str, dict[str, int]],
    team_targets: dict[str, int],
    team_points: int,
    minutes: dict[str, int],
    players_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, int]]:
    order = _preferred_player_order(player_stats, minutes, players_by_id)
    _adjust_stat_total(player_stats, team_targets["FTM"], "FTM", order=order)
    _adjust_stat_total(player_stats, team_targets["3PTM"], "3PTM", order=order)

    current_fgm = {pid: player_stats[pid].get("FGM", 0) for pid in player_stats}
    target_fgm = max(team_targets["FGM"], team_targets["3PTM"])
    minimums = {pid: player_stats[pid].get("3PTM", 0) for pid in player_stats}
    adjusted_fgm = _rebalance_integer_totals(current_fgm, target_fgm, minimums=minimums, preferred_order=order)
    for pid, value in adjusted_fgm.items():
        player_stats[pid]["FGM"] = value
        player_stats[pid]["2PTM"] = max(0, value - player_stats[pid].get("3PTM", 0))

    target_fta = max(team_targets["FTA"], team_targets["FTM"])
    target_3pta = max(team_targets["3PTA"], team_targets["3PTM"])
    target_fga = max(team_targets["FGA"], target_fgm, target_3pta)
    _adjust_stat_total(player_stats, target_fta, "FTA", minimum_stat="FTM", order=order)
    _adjust_stat_total(player_stats, target_3pta, "3PTA", minimum_stat="3PTM", order=order)

    fga_minimums = {
        pid: max(player_stats[pid].get("FGM", 0), player_stats[pid].get("3PTA", 0))
        for pid in player_stats
    }
    adjusted_fga = _rebalance_integer_totals(
        {pid: player_stats[pid].get("FGA", 0) for pid in player_stats},
        target_fga,
        minimums=fga_minimums,
        preferred_order=order,
    )
    for pid, value in adjusted_fga.items():
        player_stats[pid]["FGA"] = value

    for pid, stats in player_stats.items():
        stats["PTS"] = (2 * stats.get("FGM", 0)) + stats.get("3PTM", 0) + stats.get("FTM", 0)

    points_diff = team_points - sum(stats.get("PTS", 0) for stats in player_stats.values())
    if points_diff != 0 and order:
        top_pid = order[0]
        player_stats[top_pid]["FTM"] = max(0, player_stats[top_pid].get("FTM", 0) + points_diff)
        player_stats[top_pid]["FTA"] = max(player_stats[top_pid]["FTM"], player_stats[top_pid].get("FTA", 0))
        player_stats[top_pid]["PTS"] = (
            2 * player_stats[top_pid].get("FGM", 0)
            + player_stats[top_pid].get("3PTM", 0)
            + player_stats[top_pid].get("FTM", 0)
        )
    return player_stats


def _build_zero_stat_block() -> dict[str, Any]:
    zero_stats = {k: 0 for k in BOX_SCORE_KEYS}
    zero_stats["Outlet_Score_List"] = []
    return zero_stats


def _calculate_points_by_quarter(total_points: int) -> list[int]:
    if total_points <= 0:
        return [0, 0, 0, 0]
    weights = [random.uniform(0.18, 0.32) for _ in range(4)]
    denom = sum(weights) or 1.0
    quarters = [round((w / denom) * total_points) for w in weights]
    current = sum(quarters)
    diff = total_points - current
    order = sorted(range(4), key=lambda idx: weights[idx], reverse=True)
    while diff != 0:
        progressed = False
        for idx in order:
            if diff > 0:
                quarters[idx] += 1
                diff -= 1
                progressed = True
            elif diff < 0 and quarters[idx] > 0:
                quarters[idx] -= 1
                diff += 1
                progressed = True
            if diff == 0:
                break
        if not progressed:
            break
    return quarters


def _load_team_context(
    franchise_id: ObjectId,
    team_object_id: ObjectId,
) -> dict[str, Any]:
    team_doc = db.teams.find_one({"_id": team_object_id})
    if not team_doc:
        raise ValueError(f"Team not found for ObjectId={team_object_id}")

    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": team_object_id}
    ) or {}
    roster_ids = ftd_doc.get("players") or team_doc.get("player_ids") or []
    pid_list = [str(pid) for pid in roster_ids]
    fpd_docs = list(
        franchise_players_data_collection.find(
            {"franchise_id": str(franchise_id), "player_id": {"$in": pid_list}},
            {"player_id": 1, "meta": 1, "attributes": 1, "position_ratings": 1},
        )
    )
    fpd_by_id = {doc["player_id"]: doc for doc in fpd_docs}
    core_players = {
        str(doc["_id"]): doc
        for doc in db.players.find(
            {"_id": {"$in": roster_ids}},
            {
                "first_name": 1,
                "last_name": 1,
                "height": 1,
                "weight": 1,
                "jersey": 1,
                "year": 1,
                "attributes": 1,
                "position_ratings": 1,
            },
        )
    }

    mode_overrides: dict[str, dict[str, Any]] = {}
    ordered_ids = []
    for pid in roster_ids:
        pid_str = str(pid)
        fpd = fpd_by_id.get(pid_str) or {}
        meta = fpd.get("meta", {})
        mode_overrides[pid_str] = {
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "attributes": (fpd.get("attributes") or {}).copy(),
            "position_ratings": (fpd.get("position_ratings") or {}).copy(),
            "height": meta.get("height"),
            "weight": meta.get("weight"),
            "jersey": meta.get("jersey"),
            "year": meta.get("year"),
        }
        ordered_ids.append(pid)

    players = [
        _normalize_player(player)
        for player in build_roster_players(ordered_ids, mode_overrides, core_players, team_doc.get("name", ""))
    ]
    return {
        "team_object_id": str(team_object_id),
        "team_id": team_doc.get("team_id"),
        "name": team_doc.get("name"),
        "mascot": team_doc.get("mascot"),
        "primary_color": team_doc.get("primary_color"),
        "secondary_color": team_doc.get("secondary_color"),
        "team_attributes": (ftd_doc.get("team_attributes") or {}).copy(),
        "players": players,
    }


def _generate_team_player_stats(
    players: list[dict[str, Any]],
    team_points: int,
    team_targets: dict[str, int],
    team_rebounds: dict[str, int],
    team_steals: int,
    team_blocks: int,
    team_assists: int,
    team_turnovers: int,
    team_fouls: int,
) -> tuple[dict[str, dict[str, int]], dict[str, int], dict[str, int], dict[str, str]]:
    starters, starter_positions = identify_starters(players)
    minutes = distribute_minutes(players, starters)
    players_by_id = {str(player["_id"]): player for player in players}

    point_targets = simulate_team_points(players, team_points, minutes)
    player_stats: dict[str, dict[str, int]] = {}
    for player in players:
        pid = str(player["_id"])
        shot_profile = calculate_player_shot_profile(player)
        shooting = calculate_player_shooting_breakdown(player, point_targets.get(pid, 0), shot_profile, minutes.get(pid, 0))
        base = _build_zero_stat_block()
        base.update(
            {
                "FGM": shooting["FGM"],
                "FGA": shooting["FGA"],
                "3PTM": shooting["3PTM"],
                "3PTA": shooting["3PTA"],
                "FTM": shooting["FTM"],
                "FTA": shooting["FTA"],
                "MIN": minutes.get(pid, 0) * 60,
            }
        )
        player_stats[pid] = base

    reconcile_team_shooting(player_stats, team_targets, team_points, minutes, players_by_id)

    rebound_weights = {str(p["_id"]): calculate_player_rebound_weight(p) for p in players}
    steal_weights = {str(p["_id"]): calculate_player_steal_weight(p) for p in players}
    block_weights = {str(p["_id"]): calculate_player_block_weight(p) for p in players}
    assist_weights = {str(p["_id"]): calculate_player_assist_weight(p) for p in players}
    turnover_weights = {str(p["_id"]): calculate_player_turnover_weight(p) for p in players}
    foul_weights = {str(p["_id"]): calculate_player_foul_weight(p) for p in players}

    oreb = distribute_stat(players, rebound_weights, team_rebounds["OREB"], minutes)
    dreb = distribute_stat(players, rebound_weights, team_rebounds["DREB"], minutes)
    ast = distribute_stat(players, assist_weights, team_assists, minutes)
    stl = distribute_stat(players, steal_weights, team_steals, minutes)
    blk = distribute_stat(players, block_weights, team_blocks, minutes)
    tov = distribute_stat(players, turnover_weights, team_turnovers, minutes)
    fouls = distribute_stat(players, foul_weights, team_fouls, minutes)

    for pid in player_stats:
        player_stats[pid]["OREB"] = oreb.get(pid, 0)
        player_stats[pid]["DREB"] = dreb.get(pid, 0)
        player_stats[pid]["REB"] = player_stats[pid]["OREB"] + player_stats[pid]["DREB"]
        player_stats[pid]["AST"] = ast.get(pid, 0)
        player_stats[pid]["STL"] = stl.get(pid, 0)
        player_stats[pid]["BLK"] = blk.get(pid, 0)
        player_stats[pid]["TO"] = tov.get(pid, 0)
        player_stats[pid]["F"] = fouls.get(pid, 0)
        player_stats[pid]["PTS"] = (
            2 * player_stats[pid].get("FGM", 0)
            + player_stats[pid].get("3PTM", 0)
            + player_stats[pid].get("FTM", 0)
        )

    team_totals = _build_zero_stat_block()
    for stats in player_stats.values():
        for key in ["PTS", "FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "MIN"]:
            team_totals[key] += stats.get(key, 0)

    if team_totals["PTS"] != team_points:
        order = _preferred_player_order(player_stats, minutes, players_by_id)
        if order:
            pid = order[0]
            diff = team_points - team_totals["PTS"]
            player_stats[pid]["FTM"] = max(0, player_stats[pid]["FTM"] + diff)
            player_stats[pid]["FTA"] = max(player_stats[pid]["FTM"], player_stats[pid]["FTA"])
            player_stats[pid]["PTS"] = (
                2 * player_stats[pid]["FGM"] + player_stats[pid]["3PTM"] + player_stats[pid]["FTM"]
            )
            team_totals["FTM"] += diff
            team_totals["FTA"] = max(team_totals["FTM"], team_totals["FTA"])
            team_totals["PTS"] = team_points

    return player_stats, team_totals, minutes, starter_positions


def _build_team_box_score(
    players: list[dict[str, Any]],
    player_stats: dict[str, dict[str, int]],
    starter_positions: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    box: dict[str, dict[str, Any]] = {}
    players_list: list[dict[str, Any]] = []
    bench_index = 1
    for player in players:
        pid = str(player["_id"])
        row_key = starter_positions.get(pid)
        if not row_key:
            row_key = f"BENCH_{bench_index}"
            bench_index += 1
        stats = dict(player_stats[pid])
        row = {
            "name": player.get("name", "").strip() or pid,
            "playerId": pid,
            "jersey": player.get("jersey"),
            "pos": row_key if row_key in POSITION_KEYS else _best_position_key(player),
            **stats,
        }
        box[row_key] = row
        players_list.append(
            {
                "playerId": pid,
                "name": row["name"],
                "team": None,
                "team_id": None,
                "pos": row["pos"],
                "jersey": row["jersey"],
                "stats": dict(stats),
                "attributes": {"EM": 0, "CH": 0, "MO": 0, "NG": 1.0},
            }
        )
    return box, players_list


def build_distant_game_summary(
    franchise_id: str | ObjectId,
    week: int,
    home_team_object_id: str | ObjectId,
    away_team_object_id: str | ObjectId,
    home_score: int,
    away_score: int,
    *,
    game_id: str | None = None,
) -> dict[str, Any]:
    fid = ObjectId(franchise_id) if isinstance(franchise_id, str) else franchise_id
    home_oid = ObjectId(home_team_object_id) if isinstance(home_team_object_id, str) else home_team_object_id
    away_oid = ObjectId(away_team_object_id) if isinstance(away_team_object_id, str) else away_team_object_id

    home_ctx = _load_team_context(fid, home_oid)
    away_ctx = _load_team_context(fid, away_oid)
    constants = _normalize_constants()

    home_shooting = calculate_team_shooting_targets(home_score, constants)
    away_shooting = calculate_team_shooting_targets(away_score, constants)

    home_rebounds_raw = calculate_team_rebounds(home_shooting, constants)
    away_rebounds_raw = calculate_team_rebounds(away_shooting, constants)
    home_rebounds, away_rebounds = reconcile_rebounds(home_rebounds_raw, away_rebounds_raw)

    home_steals = calculate_team_steals(constants)
    away_turnovers = calculate_team_turnovers(constants, home_steals)
    away_steals = calculate_team_steals(constants)
    home_turnovers = calculate_team_turnovers(constants, away_steals)
    home_blocks = calculate_team_blocks(constants, away_shooting["FGA"])
    away_blocks = calculate_team_blocks(constants, home_shooting["FGA"])
    home_assists = calculate_team_assists(home_shooting, constants)
    away_assists = calculate_team_assists(away_shooting, constants)

    # Minutes affect the foul clamp, so compute player minutes during generation first.
    home_player_stats, home_team_totals, home_minutes, home_starters = _generate_team_player_stats(
        home_ctx["players"],
        home_score,
        home_shooting,
        home_rebounds,
        home_steals,
        home_blocks,
        home_assists,
        home_turnovers,
        max(0, calculate_team_fouls(constants, away_shooting["FTA"], {str(p["_id"]): 1 for p in home_ctx["players"]})),
    )
    away_player_stats, away_team_totals, away_minutes, away_starters = _generate_team_player_stats(
        away_ctx["players"],
        away_score,
        away_shooting,
        away_rebounds,
        away_steals,
        away_blocks,
        away_assists,
        away_turnovers,
        max(0, calculate_team_fouls(constants, home_shooting["FTA"], {str(p["_id"]): 1 for p in away_ctx["players"]})),
    )

    # Rebalance fouls using actual minute distributions now that they exist.
    home_fouls_target = calculate_team_fouls(constants, away_shooting["FTA"], home_minutes)
    away_fouls_target = calculate_team_fouls(constants, home_shooting["FTA"], away_minutes)
    home_order = _preferred_player_order(home_player_stats, home_minutes, {str(p["_id"]): p for p in home_ctx["players"]}, stat_hint="F")
    away_order = _preferred_player_order(away_player_stats, away_minutes, {str(p["_id"]): p for p in away_ctx["players"]}, stat_hint="F")
    _adjust_stat_total(home_player_stats, home_fouls_target, "F", order=home_order)
    _adjust_stat_total(away_player_stats, away_fouls_target, "F", order=away_order)
    home_team_totals["F"] = sum(stats.get("F", 0) for stats in home_player_stats.values())
    away_team_totals["F"] = sum(stats.get("F", 0) for stats in away_player_stats.values())

    home_box, home_players_list = _build_team_box_score(home_ctx["players"], home_player_stats, home_starters)
    away_box, away_players_list = _build_team_box_score(away_ctx["players"], away_player_stats, away_starters)

    for entry in home_players_list:
        entry["team"] = "home"
        entry["team_id"] = home_ctx["team_id"]
    for entry in away_players_list:
        entry["team"] = "away"
        entry["team_id"] = away_ctx["team_id"]

    home_points_by_quarter = _calculate_points_by_quarter(home_score)
    away_points_by_quarter = _calculate_points_by_quarter(away_score)

    gid = game_id or generate_game_id()
    teams_obj = {
        home_ctx["team_id"]: {
            "name": home_ctx["name"],
            "team_id": home_ctx["team_id"],
            "mascot": home_ctx["mascot"],
            "colors": {
                "primary_color": home_ctx["primary_color"],
                "secondary_color": home_ctx["secondary_color"],
            },
            "score": home_score,
            "points_by_quarter": home_points_by_quarter,
            "team_fouls": home_team_totals.get("F", 0),
            "timeouts": 4,
            "attributes": home_ctx["team_attributes"],
            "box_score": home_box,
            "totals": home_team_totals,
            "strategy_settings": {},
            "strategy_calls": {},
            "plays": {},
            "scouting": {},
            "playbook_settings": {},
        },
        away_ctx["team_id"]: {
            "name": away_ctx["name"],
            "team_id": away_ctx["team_id"],
            "mascot": away_ctx["mascot"],
            "colors": {
                "primary_color": away_ctx["primary_color"],
                "secondary_color": away_ctx["secondary_color"],
            },
            "score": away_score,
            "points_by_quarter": away_points_by_quarter,
            "team_fouls": away_team_totals.get("F", 0),
            "timeouts": 4,
            "attributes": away_ctx["team_attributes"],
            "box_score": away_box,
            "totals": away_team_totals,
            "strategy_settings": {},
            "strategy_calls": {},
            "plays": {},
            "scouting": {},
            "playbook_settings": {},
        },
    }

    return {
        "_id": gid,
        "game_id": gid,
        "simulation_engine": "distant",
        "quarter": 5,
        "is_final": home_score != away_score,
        "home_team_id": home_ctx["team_id"],
        "away_team_id": away_ctx["team_id"],
        "home_team": {
            "name": home_ctx["name"],
            "score": home_score,
            "points_by_quarter": home_points_by_quarter,
            "team_fouls": home_team_totals.get("F", 0),
            "box_score": home_box,
            "totals": home_team_totals,
            "scouting": {},
        },
        "away_team": {
            "name": away_ctx["name"],
            "score": away_score,
            "points_by_quarter": away_points_by_quarter,
            "team_fouls": away_team_totals.get("F", 0),
            "box_score": away_box,
            "totals": away_team_totals,
            "scouting": {},
        },
        "score": {
            home_ctx["name"]: home_score,
            away_ctx["name"]: away_score,
        },
        "points_by_quarter": {
            home_ctx["name"]: home_points_by_quarter,
            away_ctx["name"]: away_points_by_quarter,
        },
        "box_score": {
            home_ctx["team_id"]: home_box,
            away_ctx["team_id"]: away_box,
            home_ctx["name"]: home_box,
            away_ctx["name"]: away_box,
        },
        "team_totals": {
            home_ctx["name"]: home_team_totals,
            away_ctx["name"]: away_team_totals,
        },
        "teams": teams_obj,
        "team_stats": {},
        "players": home_players_list + away_players_list,
        "turns": [],
        "clock": "0:00",
        "time_remaining": 0,
        "shot_clock_remaining": 0,
        "franchise_id": str(fid),
        "week": week,
    }
