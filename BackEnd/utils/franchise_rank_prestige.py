import random
from typing import Any


FRANCHISE_RANK_PRESTIGE_SYSTEM_VERSION = 2
SOS_AVG_DEFAULT = 64.0
PRESTIGE_FLOOR = 200
PRESTIGE_CEILING = 800


def use_franchise_rank_prestige_v2(franchise_doc: dict[str, Any] | None) -> bool:
    return int((franchise_doc or {}).get("rank_prestige_system_version", 1) or 1) >= FRANCHISE_RANK_PRESTIGE_SYSTEM_VERSION


def core_total_player_attrs(attrs: dict[str, Any] | None) -> int:
    if not attrs:
        return 0
    return sum(
        int(attrs.get(attr, 0) or 0)
        for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
    )


def _prestige_delta_multiplier(week: int | None = None) -> int:
    return 2 if week is not None and 1 <= int(week) <= 4 else 1


def calculate_prestige_delta(
    winner_prestige: int,
    loser_prestige: int,
    week: int | None = None,
) -> tuple[int, int]:
    diff = winner_prestige - loser_prestige
    if diff > 100:
        winner_gain = 8
        loser_loss = 6
    elif diff > 50:
        winner_gain = 9
        loser_loss = 8
    elif diff >= -50:
        winner_gain = 10
        loser_loss = 10
    elif diff >= -100:
        winner_gain = 13
        loser_loss = 12
    else:
        winner_gain = 18
        loser_loss = 15

    multiplier = _prestige_delta_multiplier(week)
    winner_gain *= multiplier
    loser_loss *= multiplier

    floor_proximity = min(1.0, max(0.0, (loser_prestige - PRESTIGE_FLOOR) / 100.0))
    loser_loss = round(loser_loss * floor_proximity)

    ceiling_proximity = min(1.0, max(0.0, (PRESTIGE_CEILING - winner_prestige) / 100.0))
    winner_gain = round(winner_gain * ceiling_proximity)
    return winner_gain, loser_loss


def apply_prestige_delta(
    winner_prestige: int,
    loser_prestige: int,
    week: int | None = None,
) -> tuple[int, int]:
    winner_gain, loser_loss = calculate_prestige_delta(winner_prestige, loser_prestige, week=week)
    new_winner_prestige = min(PRESTIGE_CEILING, winner_prestige + winner_gain)
    new_loser_prestige = max(PRESTIGE_FLOOR, loser_prestige - loser_loss)
    return new_winner_prestige, new_loser_prestige


def calculate_ranking_score(
    prestige: int,
    total_player_attrs: int,
    week: int,
    sos_avg: float = SOS_AVG_DEFAULT,
) -> float:
    if week <= 0:
        return prestige + (total_player_attrs * 0.10)
    if week == 1:
        return prestige + (total_player_attrs * 0.04)
    if week == 2:
        return prestige + (total_player_attrs * 0.03)
    if week == 3:
        return prestige + (total_player_attrs * 0.02)
    if week == 4:
        return prestige + (total_player_attrs * 0.01)
    return prestige + ((129 - sos_avg) * 4)


def rank_teams_for_week(
    teams: list[dict[str, Any]],
    week: int,
    previous_rank_by_team: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    previous_rank_by_team = previous_rank_by_team or {}
    for team in teams:
        team_id = str(team.get("team_id") or "")
        entry = dict(team)
        entry["ranking_score"] = calculate_ranking_score(
            prestige=int(team.get("prestige", 0) or 0),
            total_player_attrs=int(team.get("total_player_attrs", 0) or 0),
            week=week,
            sos_avg=float(team.get("sos_avg", SOS_AVG_DEFAULT) or SOS_AVG_DEFAULT),
        )
        entry["_previous_rank"] = int(previous_rank_by_team.get(team_id, 999))
        entry["_random_tiebreak"] = random.random()
        scored.append(entry)

    if week <= 0:
        scored.sort(key=lambda x: (-x["ranking_score"], x["_random_tiebreak"]))
    else:
        scored.sort(key=lambda x: (-x["ranking_score"], x["_previous_rank"], x["_random_tiebreak"]))

    for idx, entry in enumerate(scored, start=1):
        entry["natl_rank"] = idx
    return scored
