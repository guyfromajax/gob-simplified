"""Consolidated, read-only league-news payload for the training load screen."""

from __future__ import annotations

from typing import Any

from bson import ObjectId

from BackEnd.db import db, franchise_players_data_collection, franchise_team_data_collection
from BackEnd.utils.franchise_standings import calculate_franchise_standings
from BackEnd.utils.franchise_team_display import resolve_team_name_map


LEADER_SPECS: tuple[tuple[str, str, str | None, float | None], ...] = (
    ("pts", "PTS", None, None),
    ("treb", "REB", None, None),
    ("ast", "AST", None, None),
    ("def_pct", "DEF_S", "DEF_A", 6.0),
    ("stl", "STL", None, None),
    ("blk", "BLK", None, None),
    ("tpm", "3PTM", None, None),
    ("fg_pct", "FGM", "FGA", 7.0),
)

PER_GAME_LEADER_BOARDS = frozenset({"pts", "treb", "ast"})


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _region_from_conference(conference: Any) -> str:
    conf = _int(conference)
    if conf < 1 or conf > 16:
        return ""
    return chr(65 + ((conf - 1) // 2))


def _team_slug(team: dict[str, Any]) -> str:
    stored = str(team.get("team_id") or "").strip()
    if stored:
        return stored.lower()
    name = str(team.get("name") or "general").strip().lower()
    return "_".join(name.replace("-", " ").replace("'", "").replace(".", "").split()) or "general"


def _team_rows(
    franchise_doc: dict[str, Any],
    franchise_id: ObjectId,
) -> tuple[dict[str, dict[str, Any]], dict[str, int], dict[str, str], dict[str, dict[str, int]]]:
    ftd_docs = list(
        franchise_team_data_collection.find(
            {"franchise_id": franchise_id},
            {"team_id": 1, "natl_rank": 1},
        )
    )
    team_ids = [row.get("team_id") for row in ftd_docs if row.get("team_id")]
    core_by_id = {
        str(team["_id"]): team
        for team in db.teams.find(
            {"_id": {"$in": team_ids}},
            {"name": 1, "team_id": 1, "conference": 1, "region": 1},
        )
    }
    ranks = {
        str(row["team_id"]): _int(row.get("natl_rank"), 999)
        for row in ftd_docs
        if row.get("team_id")
    }
    names = resolve_team_name_map(franchise_doc, team_ids)
    standings = calculate_franchise_standings(
        franchise_doc.get("results") or {},
        {str(team_id): {} for team_id in team_ids},
    )
    return core_by_id, ranks, names, standings


def _team_payload(
    team_id: str,
    core_by_id: dict[str, dict[str, Any]],
    ranks: dict[str, int],
    names: dict[str, str],
) -> dict[str, Any]:
    core = core_by_id.get(str(team_id), {})
    conference = _int(core.get("conference"))
    return {
        "team_id": str(team_id),
        "team_slug": _team_slug(core),
        "team_name": names.get(str(team_id)) or str(core.get("name") or "Team"),
        "rank": _int(ranks.get(str(team_id)), 999),
        "conference": conference,
        "region": str(core.get("region") or _region_from_conference(conference)),
    }


def _build_top10(
    core_by_id: dict[str, dict[str, Any]],
    ranks: dict[str, int],
    names: dict[str, str],
    standings: dict[str, dict[str, int]],
    *,
    include_record: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for team_id, rank in sorted(ranks.items(), key=lambda item: (item[1], item[0]))[:10]:
        row = _team_payload(team_id, core_by_id, ranks, names)
        row["rank"] = rank
        if include_record:
            record = standings.get(team_id) or {}
            row["wins"] = _int(record.get("W"))
            row["losses"] = _int(record.get("L"))
        rows.append(row)
    return rows if len(rows) == 10 else []


def _build_games(
    games: list[Any],
    core_by_id: dict[str, dict[str, Any]],
    ranks: dict[str, int],
    names: dict[str, str],
    *,
    week: int | None = None,
    require_ten: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(games or []):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            continue
        away_id, home_id = str(pair[0]), str(pair[1])
        away = _team_payload(away_id, core_by_id, ranks, names)
        home = _team_payload(home_id, core_by_id, ranks, names)
        row = {
            "away_rank": away["rank"],
            "away_slug": away["team_slug"],
            "away_name": away["team_name"],
            "home_rank": home["rank"],
            "home_slug": home["team_slug"],
            "home_name": home["team_name"],
            "rank_sum": away["rank"] + home["rank"],
            "_index": index,
        }
        if week is not None:
            row["week"] = int(week)
        rows.append(row)
    rows.sort(key=lambda row: (row["rank_sum"], row.get("week", 0), row["_index"]))
    for row in rows:
        row.pop("_index", None)
    if require_ten and len(rows) < 10:
        return []
    return rows[:10]


def _build_leaders(
    franchise_id: ObjectId,
    core_by_id: dict[str, dict[str, Any]],
    names: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    players = list(
        franchise_players_data_collection.find(
            {"franchise_id": str(franchise_id)},
            {"player_id": 1, "meta": 1, "season": 1},
        )
    )
    core_name_to_id = {
        str(team.get("name") or "").strip().casefold(): team_id
        for team_id, team in core_by_id.items()
        if team.get("name")
    }
    boards: dict[str, list[dict[str, Any]]] = {}
    for board_id, numerator, denominator, qualifier in LEADER_SPECS:
        candidates: list[dict[str, Any]] = []
        for player in players:
            season = player.get("season") or {}
            meta = player.get("meta") or {}
            gp = _float(season.get("GP"))
            numerator_value = _float(season.get(numerator))
            denominator_value = _float(season.get(denominator)) if denominator else 0.0
            if denominator:
                if gp <= 0 or denominator_value <= 0:
                    continue
                if qualifier is not None and denominator_value / gp < qualifier:
                    continue
                value = numerator_value / denominator_value * 100.0
                tiebreak = denominator_value
            elif board_id in PER_GAME_LEADER_BOARDS:
                if gp <= 0:
                    continue
                value = numerator_value / gp
                tiebreak = numerator_value
            else:
                value = numerator_value
                tiebreak = 0.0

            team_id = str(meta.get("team_id") or "")
            if team_id not in core_by_id:
                team_id = core_name_to_id.get(str(meta.get("team") or "").strip().casefold(), "")
            if team_id not in core_by_id:
                continue
            core = core_by_id[team_id]
            name = " ".join(
                part for part in [str(meta.get("first_name") or "").strip(), str(meta.get("last_name") or "").strip()] if part
            ) or str(player.get("player_id") or "Player")
            candidates.append(
                {
                    "player_id": str(player.get("player_id") or ""),
                    "name": name,
                    "team_slug": _team_slug(core),
                    "team_name": names.get(team_id) or str(core.get("name") or "Team"),
                    "value": round(value, 1) if denominator or board_id in PER_GAME_LEADER_BOARDS else int(value),
                    "display": (
                        f"{value:.1f}%"
                        if denominator
                        else f"{value:.1f}"
                        if board_id in PER_GAME_LEADER_BOARDS
                        else str(int(value))
                    ),
                    "_sort_value": value,
                    "_tiebreak": tiebreak,
                }
            )
        candidates.sort(key=lambda row: (-row["_sort_value"], -row["_tiebreak"], row["name"].casefold()))
        top = candidates[:10]
        if len(top) != 10:
            continue
        for rank, row in enumerate(top, start=1):
            row["rank"] = rank
            row.pop("_sort_value", None)
            row.pop("_tiebreak", None)
        boards[board_id] = top
    return boards


def build_franchise_league_news(franchise_doc: dict[str, Any]) -> dict[str, Any]:
    """Build the complete newswire payload from one franchise snapshot."""
    franchise_id = franchise_doc.get("_id")
    if not isinstance(franchise_id, ObjectId):
        franchise_id = ObjectId(str(franchise_id))
    current_week = max(1, _int(franchise_doc.get("week"), 1))
    completed_week = max(0, current_week - 1)
    season = max(1, _int(franchise_doc.get("current_season"), 1))
    phase = "preseason" if current_week == 1 else "in_season"
    core_by_id, ranks, names, standings = _team_rows(franchise_doc, franchise_id)
    schedule = list(franchise_doc.get("schedule") or [])

    payload: dict[str, Any] = {
        "phase": phase,
        "season": season,
        "week": completed_week,
        "current_week": current_week,
        "completed_week": completed_week,
        "top10": [],
        "leaders": {},
        "key_games": [],
        "preseason": {"top10": [], "marquee": []},
    }
    if phase == "preseason":
        # Week 1 training previews the actual Week 1 slate. The previous
        # preseason treatment ranked games from the entire 26-week schedule,
        # which surfaced future matchups and could show both legs of the same
        # conference pairing.
        current_games = schedule[0] if schedule else []
        payload["key_games"] = _build_games(current_games, core_by_id, ranks, names)
        payload["preseason"] = {
            "top10": _build_top10(core_by_id, ranks, names, standings, include_record=False),
            "marquee": [],
        }
        return payload

    current_games = schedule[current_week - 1] if current_week - 1 < len(schedule) else []
    payload["top10"] = _build_top10(core_by_id, ranks, names, standings, include_record=True)
    payload["key_games"] = _build_games(current_games, core_by_id, ranks, names)
    payload["leaders"] = _build_leaders(franchise_id, core_by_id, names)
    return payload
