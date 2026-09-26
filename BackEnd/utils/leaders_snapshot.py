"""Compact season/career lines for GET /franchise/leaders.

The live scan used to aggregate ``franchise_players_data`` once per category.
On SQLite each aggregate decodes every player document in the save. This
module keeps one row per player — the fields the eight leader categories
actually read — and the route sorts that list in Python.

The snapshot is fresh only when it was built for this franchise week and
season and no later writer has marked it stale. Anything else falls back to
the same ranker over a live read, then stores a new snapshot. Week 1 and
saves that have never built one take that fallback and do not error.

Stale, not browse_rev: a game finalizes player season totals before the
franchise document's ``browse_rev`` moves (CPU games between heartbeats,
the user game before phase A returns). ``note_season_stats_written`` bumps
``gen`` on a small meta document. The player lines live in a second
document stamped with the generation they were built at. A rebuild writes
the lines, then clears stale only if that generation is still current.
"""

from __future__ import annotations

import logging
from typing import Any

from BackEnd.constants.leader_qualification import qualifies
from BackEnd.utils.franchise_standings import calculate_franchise_standings

logger = logging.getLogger(__name__)

STAT_KEYS: tuple[str, ...] = (
    "GP",
    "PTS",
    "REB",
    "AST",
    "3PTM",
    "BLK",
    "STL",
    "FGM",
    "FGA",
    "DEF_S",
    "DEF_A",
)

PER_GAME_STATS = frozenset({"PTS", "REB", "AST"})
RATE_STATS = frozenset({"FG%", "DEF%"})


def _collection():
    from BackEnd.persistence import get_store

    return get_store().leaders_snapshots_collection


def _players():
    from BackEnd.persistence import get_store

    return get_store().franchise_players_data_collection


def _franchises():
    from BackEnd.persistence import get_store

    return get_store().franchises_collection


def leader_projection() -> dict[str, int]:
    projection = {
        "player_id": 1,
        "meta.first_name": 1,
        "meta.last_name": 1,
        "meta.team": 1,
        "meta.team_id": 1,
        "meta.position": 1,
        "meta.year": 1,
        "meta.yr": 1,
    }
    for scope in ("season", "career"):
        for key in STAT_KEYS:
            projection[f"{scope}.{key}"] = 1
    return projection


def team_games_from_results(results: dict | None) -> dict[str, int]:
    from BackEnd.constants.leader_qualification import team_games_from_record

    standings = calculate_franchise_standings(results or {}, {})
    return {
        str(team_id): team_games_from_record(row.get("W"), row.get("L"))
        for team_id, row in standings.items()
    }


def _display_year(raw: Any) -> str:
    """Class year as the UI abbreviation. Empty stays empty."""
    if raw is None or str(raw).strip() in ("", "--"):
        return ""
    from BackEnd.utils.player_year import format_player_year_abbrev

    text = format_player_year_abbrev(raw)
    return "" if text == "--" else text


def _stat_block(raw: dict | None) -> list[int | float]:
    block = raw or {}
    values: list[int | float] = []
    for key in STAT_KEYS:
        number = block.get(key, 0)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            try:
                number = float(number or 0)
            except (TypeError, ValueError):
                number = 0
        values.append(number)
    return values


def lines_from_player_docs(docs) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for doc in docs:
        meta = doc.get("meta") or {}
        # Display matches the old response. Scope matching uses the raw team
        # name only, the same rule as the old ``meta.team`` filter.
        rows.append(
            [
                doc.get("player_id"),
                meta.get("first_name", ""),
                meta.get("last_name", ""),
                meta.get("team", meta.get("team_id", "")),
                str(meta.get("team_id") or ""),
                str(meta.get("team") or ""),
                *_stat_block(doc.get("season")),
                *_stat_block(doc.get("career")),
                meta.get("position") or "",
                _display_year(meta.get("year") or meta.get("yr")),
            ]
        )
    return rows


def _line_fields() -> list[str]:
    fields = [
        "player_id",
        "meta.first_name",
        "meta.last_name",
        "meta.team",
        "meta.team_id",
    ]
    for scope in ("season", "career"):
        fields.extend(f"{scope}.{key}" for key in STAT_KEYS)
    fields.extend(["meta.position", "meta.year", "meta.yr"])
    return fields


def _lines_from_tuples(raw_rows: list[tuple]) -> list[list[Any]]:
    season_at = 5
    career_at = season_at + len(STAT_KEYS)
    tail_at = career_at + len(STAT_KEYS)
    lines: list[list[Any]] = []
    for raw in raw_rows:
        team = raw[3]
        team_id = raw[4]
        display = team if team is not None else ("" if team_id is None else team_id)
        season = [0 if value is None else value for value in raw[season_at:career_at]]
        career = [0 if value is None else value for value in raw[career_at:tail_at]]
        position = raw[tail_at] if len(raw) > tail_at else ""
        year = raw[tail_at + 1] if len(raw) > tail_at + 1 else ""
        yr = raw[tail_at + 2] if len(raw) > tail_at + 2 else ""
        lines.append(
            [
                raw[0],
                raw[1] or "",
                raw[2] or "",
                display,
                "" if team_id is None else str(team_id),
                str(team or ""),
                *season,
                *career,
                "" if position is None else str(position),
                _display_year(year or yr),
            ]
        )
    return lines


def _as_sqlite(coll):
    """Mongomock's ``__getattr__`` invents missing methods, so ``getattr`` is not a test."""
    from BackEnd.persistence.sqlite_collection import SqliteCollection

    return coll if isinstance(coll, SqliteCollection) else None


def load_lines(franchise_id: str) -> list[list[Any]]:
    """Compact rows in the same order as an aggregate ``$match``."""
    coll = _players()
    sqlite_coll = _as_sqlite(coll)
    if sqlite_coll is not None:
        return _lines_from_tuples(
            sqlite_coll.projected_tuples(
                {"franchise_id": str(franchise_id)},
                _line_fields(),
                natural_order=True,
            )
        )
    return lines_from_player_docs(load_player_docs(franchise_id))


def load_player_docs(franchise_id: str) -> list[dict[str, Any]]:
    """Player lines in aggregate ``$match`` order so tied counting stats stay put."""
    coll = _players()
    filt = {"franchise_id": str(franchise_id)}
    projection = leader_projection()
    sqlite_coll = _as_sqlite(coll)
    if sqlite_coll is not None:
        return list(sqlite_coll.find_in_natural_order(filt, projection))
    cursor = coll.find(filt, projection)
    sort = getattr(cursor, "sort", None)
    if sort is not None:
        try:
            cursor = sort([("$natural", 1)])
        except Exception:
            pass
    return list(cursor)


def _in_scope(team_id: str, team_name: str, allowed_team_ids, allowed_team_names) -> bool:
    if not allowed_team_ids and not allowed_team_names:
        return True
    if allowed_team_ids and team_id in allowed_team_ids:
        return True
    if allowed_team_names and team_name in allowed_team_names:
        return True
    return False


def line_width() -> int:
    """Identity, both stat blocks, then position and year."""
    return 6 + (2 * len(STAT_KEYS)) + 2


def _identity(row: list[Any]) -> tuple[str, str]:
    pos_at = 6 + (2 * len(STAT_KEYS))
    position = row[pos_at] if len(row) > pos_at else ""
    year = row[pos_at + 1] if len(row) > pos_at + 1 else ""
    return str(position or ""), str(year or "")


def rank_lines(
    rows: list[list[Any]],
    *,
    scope: str,
    stat: str,
    limit: int,
    team_games: dict[str, int],
    allowed_team_ids=None,
    allowed_team_names=None,
    basis: str | None = None,
) -> list[dict[str, Any]]:
    """Same order and rounding as the old aggregate: value, then volume, stable.

    Omitted basis keeps the previous defaults: PTS/REB/AST per game, other
    counting stats as totals. ``per_game`` divides every counting stat by GP.
    ``totals`` leaves counting stats as sums. Percentages ignore basis.
    """
    use_career = str(scope or "season") == "career"
    stat_field = {"TPM": "3PTM", "TPA": "3PTA"}.get(stat, stat)
    leader_basis = basis if basis in {"per_game", "totals"} else None
    per_game = stat not in RATE_STATS and (
        leader_basis == "per_game" or (leader_basis is None and stat in PER_GAME_STATS)
    )
    offset = 6 + (len(STAT_KEYS) if use_career else 0)
    index = {key: offset + position for position, key in enumerate(STAT_KEYS)}
    caption = ""
    if stat in RATE_STATS and not use_career:
        from BackEnd.constants.leader_qualification import (
            ATTEMPT_FIELDS,
            LEADER_QUALIFICATION_FLOORS,
        )
        caption = f"min {LEADER_QUALIFICATION_FLOORS[stat]} {ATTEMPT_FIELDS[stat]} per team game"
    ranked: list[tuple[float, float, dict[str, Any]]] = []
    for row in rows:
        team_id = str(row[4] or "")
        team_name = row[3] if row[3] is not None else ""
        scope_name = str(row[5] or "")
        if not _in_scope(team_id, scope_name, allowed_team_ids, allowed_team_names):
            continue
        position, year = _identity(row)
        gp = float(row[index["GP"]] or 0)
        if stat in RATE_STATS:
            made_key = "FGM" if stat == "FG%" else "DEF_S"
            miss_key = "FGA" if stat == "FG%" else "DEF_A"
            made = float(row[index[made_key]] or 0)
            attempts = float(row[index[miss_key]] or 0)
            if use_career:
                if gp <= 0 or attempts < gp * 5:
                    continue
            elif not qualifies(stat, attempts, team_games.get(team_id, 0)):
                continue
            value = (made / attempts) * 100.0 if attempts else 0.0
            tiebreak = attempts
        elif per_game:
            if gp <= 0:
                continue
            if stat_field not in index:
                continue
            total = float(row[index[stat_field]] or 0)
            value = total / gp
            tiebreak = total
        else:
            if stat_field not in index:
                value = 0.0
            else:
                value = float(row[index[stat_field]] or 0)
            tiebreak = 0.0
        payload = {
            "player_id": row[0],
            "first_name": row[1] or "",
            "last_name": row[2] or "",
            "team": team_name,
            "team_id": team_id,
            "position": position,
            "year": year,
            "value": value,
        }
        if caption:
            payload["qualification_caption"] = caption
        ranked.append((value, tiebreak, payload))
    # Two stable passes match the SQLite aggregate ($sort value, then volume).
    ranked.sort(key=lambda item: item[1], reverse=True)
    ranked.sort(key=lambda item: item[0], reverse=True)
    chosen = ranked[:limit]
    results: list[dict[str, Any]] = []
    for value, _tiebreak, payload in chosen:
        if per_game or stat == "FG%":
            payload["value"] = round(float(value or 0), 1)
        elif stat == "DEF%":
            payload["value"] = int(round(float(value or 0)))
        else:
            number = float(value or 0)
            payload["value"] = int(number) if number.is_integer() else number
        results.append(payload)
    return results


def snapshot_id(franchise_id: str) -> str:
    return str(franchise_id)


def meta_id(franchise_id: str) -> str:
    return f"meta:{franchise_id}"


def read_snapshot(franchise_id: str) -> dict[str, Any] | None:
    """The lines document. Freshness lives on the meta document."""
    doc = _collection().find_one({"_id": snapshot_id(franchise_id)})
    return doc if isinstance(doc, dict) else None


def read_meta(franchise_id: str) -> dict[str, Any] | None:
    doc = _collection().find_one({"_id": meta_id(franchise_id)})
    return doc if isinstance(doc, dict) else None


def _meta_matches_week(meta: dict[str, Any] | None, *, week: int, season: int) -> bool:
    if not meta or meta.get("stale"):
        return False
    try:
        return int(meta.get("week")) == int(week) and int(meta.get("season") or 1) == int(season)
    except (TypeError, ValueError):
        return False


def _generation(doc: dict[str, Any] | None) -> int:
    if not doc:
        return 0
    try:
        return int(doc.get("gen") or 0)
    except (TypeError, ValueError):
        return 0


def fresh_lines(franchise_id: str, *, week: int, season: int) -> tuple[list[list[Any]], dict[str, int]] | None:
    """Lines when meta is current and the lines document was built at that generation."""
    meta = read_meta(franchise_id)
    if not _meta_matches_week(meta, week=week, season=season):
        return None
    lines = read_snapshot(franchise_id)
    if not lines:
        return None
    try:
        built = int(meta.get("built_gen"))
    except (TypeError, ValueError):
        return None
    if _generation(lines) != built:
        return None
    rows = list(lines.get("rows") or [])
    # A line from before position/year were stored cannot match a live scan.
    if any(len(row) < line_width() for row in rows):
        return None
    return rows, dict(lines.get("team_games") or {})


def note_season_stats_written(franchise_id: str | None) -> None:
    """Bump meta ``gen`` and mark the lines stale. Creates the counter if needed."""
    if not franchise_id:
        return
    try:
        _collection().update_one(
            {"_id": meta_id(franchise_id)},
            {
                "$inc": {"gen": 1},
                "$set": {"stale": True, "franchise_id": str(franchise_id)},
            },
            upsert=True,
        )
    except Exception:
        logger.exception("[LEADERS] snapshot invalidate failed franchise_id=%s", franchise_id)


def _write_lines(doc: dict[str, Any]) -> None:
    coll = _collection()
    sqlite_coll = _as_sqlite(coll)
    if sqlite_coll is not None:
        sqlite_coll.upsert_owned(doc)
    else:
        coll.replace_one({"_id": doc["_id"]}, doc, upsert=True)


def _commit_meta(franchise_id: str, gen: int, week: int, season: int, *, existed: bool) -> bool:
    """Clear stale only while ``gen`` is still the value read before the scan."""
    coll = _collection()
    mid = meta_id(franchise_id)
    fields = {
        "franchise_id": str(franchise_id),
        "stale": False,
        "week": int(week),
        "season": int(season or 1),
        "built_gen": int(gen),
    }
    if not existed:
        result = coll.update_one(
            {"_id": mid},
            {"$setOnInsert": {**fields, "gen": int(gen)}},
            upsert=True,
        )
        return getattr(result, "upserted_id", None) is not None
    result = coll.update_one(
        {"_id": mid, "gen": int(gen)},
        {"$set": fields},
    )
    return getattr(result, "matched_count", 0) > 0


def _publish(franchise_id: str, *, week: int, season: int, results: dict | None, rows: list[list[Any]], meta: dict[str, Any] | None) -> bool:
    """Write lines stamped with the generation read before the scan, then clear stale if it still matches."""
    existed = meta is not None
    gen = _generation(meta) if existed else 0
    _write_lines(
        {
            "_id": snapshot_id(franchise_id),
            "franchise_id": str(franchise_id),
            "gen": gen,
            "team_games": team_games_from_results(results),
            "rows": rows,
        }
    )
    return _commit_meta(franchise_id, gen, week, season, existed=existed)


def write_snapshot(
    franchise_id: str,
    *,
    week: int,
    season: int,
    results: dict | None,
    rows: list[list[Any]] | None = None,
) -> bool:
    """Rebuild lines. Meta is cleared only if ``gen`` did not move during the load."""
    meta = read_meta(franchise_id)
    if rows is None:
        rows = load_lines(franchise_id)
    return _publish(franchise_id, week=week, season=season, results=results, rows=rows, meta=meta)


def refresh_leaders_snapshot(franchise_id: str, *, week: int, season: int, results: dict | None) -> None:
    """Rebuild after the week's games are already on ``franchise_players_data``."""
    try:
        write_snapshot(franchise_id, week=week, season=season, results=results)
    except Exception:
        logger.exception("[LEADERS] snapshot rebuild failed franchise_id=%s week=%s", franchise_id, week)


def lines_for_request(franchise_id: str, *, week: int, season: int, results: dict | None) -> tuple[list[list[Any]], dict[str, int], str]:
    """Return lines, team games, and ``snapshot`` or ``live``.

    A miss stores a fresh snapshot so the next open of this week does not scan.
    """
    cached = fresh_lines(franchise_id, week=week, season=season)
    if cached is not None:
        rows, team_games = cached
        return rows, team_games, "snapshot"
    meta = read_meta(franchise_id)
    rows = load_lines(franchise_id)
    team_games = team_games_from_results(results)
    try:
        _publish(franchise_id, week=week, season=season, results=results, rows=rows, meta=meta)
    except Exception:
        logger.exception("[LEADERS] snapshot store failed franchise_id=%s", franchise_id)
    return rows, team_games, "live"
