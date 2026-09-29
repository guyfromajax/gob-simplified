"""One week of the national schedule for League › Schedule.

The whole-season national payload walks every game document. On an offline
save that is several hundred milliseconds. This module keeps a process cache
of team identity, ranks, records, and matchup ids, then slices one week.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from bson import ObjectId
from fastapi import HTTPException

from BackEnd.persistence import get_store
from BackEnd.utils.franchise_standings import calculate_franchise_standings
from BackEnd.utils.franchise_team_display import get_team_builder_overlay, resolve_team_display

_store = get_store()
db = _store.db
franchise_team_data_collection = _store.franchise_team_data_collection

_WEEK_MIN = 1
_WEEK_MAX = 34
_REGULAR_MAX = 26

_TOURNAMENT_LABELS = {
    27: "Conference Tourney - R1",
    28: "Conference Tourney - R2",
    29: "Conference Tourney - Championships",
    30: "Region Tourney - R1",
    31: "Region Tourney - Championships",
    32: "National Tourney - R1",
    33: "National Tourney - R2",
    34: "National Championship",
}

_SIDE_ID = re.compile(r'"(home_team_id|away_team_id)"\s*:\s*"([^"]+)"')
_PREFIX_CHARS = 3200
_ID_IN_CHUNK = 400
_TEAM_OID = re.compile(r'"team_id"\s*:\s*\{\s*"\$oid"\s*:\s*"([0-9a-fA-F]{24})"\s*\}')
_TEAM_STR = re.compile(r'"team_id"\s*:\s*"([0-9a-fA-F]{24})"')
_RANK = re.compile(r'"natl_rank"\s*:\s*(-?\d+)')
_HEX_ID = re.compile(r"^[0-9a-fA-F]{24}$")

# One slot per franchise: the latest (stamp, value). A new week, browse_rev,
# season, or result count replaces the previous slot, so seasons do not pile up.
_BUNDLES: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}
_GAME_IDS: dict[str, tuple[tuple[Any, ...], dict[tuple[int, str, str], str]]] = {}


def clear_schedule_browse_cache() -> None:
    _BUNDLES.clear()
    _GAME_IDS.clear()


def _canon(value: Any) -> str:
    return str(value or "").replace("-", "_").replace(" ", "_").upper()


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decode_row_id(row_id: str) -> str:
    if row_id.startswith("raw:"):
        try:
            return str(json.loads(row_id[4:]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return row_id[4:].strip('"')
    if row_id.startswith("oid:"):
        return row_id[4:]
    return row_id


def _sql_rows(collection: Any, sql: str, params: tuple[Any, ...]) -> list[tuple] | None:
    conn = getattr(collection, "_conn", None)
    if conn is None:
        return None
    lock = getattr(collection, "_lock", None)
    if lock is None:
        return list(conn.execute(sql, params))
    with lock:
        return list(conn.execute(sql, params))


def _rank_map(franchise_id: str) -> dict[str, int | None]:
    coll = franchise_team_data_collection
    table = getattr(coll, "name", "franchise_team_data")
    rows = _sql_rows(
        coll,
        f'SELECT substr(doc, 1, 500), substr(doc, max(1, length(doc) - 1400), 1400) '
        f'FROM "{table}" WHERE g_franchise_id = ?',
        (str(franchise_id),),
    )
    ranks: dict[str, int | None] = {}
    if rows is not None:
        for head, tail in rows:
            blob = f"{head or ''} {tail or ''}"
            team = _TEAM_OID.search(blob) or _TEAM_STR.search(blob)
            rank = _RANK.search(blob)
            if not team:
                continue
            ranks[team.group(1)] = _as_int(rank.group(1)) if rank else None
        return ranks
    try:
        key: Any = ObjectId(str(franchise_id))
    except Exception:
        key = franchise_id
    for doc in coll.find({"franchise_id": key}, {"team_id": 1, "natl_rank": 1}):
        team_id = doc.get("team_id")
        if team_id is None:
            continue
        ranks[str(team_id)] = _as_int(doc.get("natl_rank"))
    return ranks


def matchup_game_ids(franchise_id: str, stamp: tuple[Any, ...] | None = None) -> dict[tuple[int, str, str], str]:
    """(week, away id, home id) -> game id. Latest stamp only, per franchise."""
    key = str(franchise_id)
    if stamp is None:
        stamp = _light_stamp(key)
    cached = _GAME_IDS.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    found = _read_game_ids(key)
    _GAME_IDS[key] = (stamp, found)
    return found


def _side_text(value: Any) -> str:
    """Team id as stored: a slug, a hex id, or an ``{'$oid': ...}`` object."""
    if value is None:
        return ""
    if isinstance(value, dict):
        oid = value.get("$oid")
        return str(oid) if oid else ""
    if isinstance(value, ObjectId):
        return str(value)
    text = str(value).strip()
    if text.startswith("{") and "$oid" in text:
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return text
        if isinstance(parsed, dict) and parsed.get("$oid"):
            return str(parsed["$oid"])
    return text


def _store_matchup(
    found: dict[tuple[int, str, str], str],
    resolve,
    week_raw: Any,
    away_raw: Any,
    home_raw: Any,
    team1_raw: Any,
    team2_raw: Any,
    game_id: Any,
) -> None:
    week = _as_int(week_raw)
    away = resolve(_side_text(away_raw) or _side_text(team1_raw))
    home = resolve(_side_text(home_raw) or _side_text(team2_raw))
    ident = _side_text(game_id)
    if week is None or not away or not home or not ident:
        return
    # Two documents can share a week and matchup. Keep the greater id so
    # Mongo find order and the SQLite scan return the same link.
    previous = found.get((week, away, home))
    if previous is None or ident > previous:
        found[(week, away, home)] = ident


def _read_game_ids(franchise_id: str) -> dict[tuple[int, str, str], str]:
    teams = list(db.teams.find({}, {"_id": 1, "name": 1, "team_id": 1}))
    by_canon: dict[str, str] = {}
    for team in teams:
        oid = str(team.get("_id") or "")
        if not oid:
            continue
        by_canon[_canon(team.get("name"))] = oid
        slug = team.get("team_id")
        if slug:
            by_canon[_canon(slug)] = oid

    def resolve(raw: str) -> str:
        text = str(raw or "")
        if _HEX_ID.match(text):
            return text
        return by_canon.get(_canon(text), "")

    games = db.games
    from BackEnd.persistence.sqlite_collection import SqliteCollection

    if isinstance(games, SqliteCollection):
        return _read_game_ids_sqlite(games, franchise_id, resolve)
    return _read_game_ids_find(games, franchise_id, resolve)


_GAME_ID_FIELDS = ["_id", "week", "away_team_id", "home_team_id", "team1_id", "team2_id"]


def _apply_projected_rows(found: dict[tuple[int, str, str], str], resolve, rows: list[tuple]) -> None:
    for game_id, week_raw, away_raw, home_raw, team1_raw, team2_raw in rows:
        _store_matchup(found, resolve, week_raw, away_raw, home_raw, team1_raw, team2_raw, game_id)


def _read_game_ids_find(games: Any, franchise_id: str, resolve) -> dict[tuple[int, str, str], str]:
    found: dict[tuple[int, str, str], str] = {}
    for doc in games.find({"franchise_id": franchise_id}, {name: 1 for name in _GAME_ID_FIELDS}):
        _store_matchup(
            found,
            resolve,
            doc.get("week"),
            doc.get("away_team_id"),
            doc.get("home_team_id"),
            doc.get("team1_id"),
            doc.get("team2_id"),
            doc.get("_id"),
        )
    return found


def projected_game_ids(franchise_id: str) -> dict[tuple[int, str, str], str]:
    """Every matchup via json_extract. The hybrid reader must match this."""
    teams = list(db.teams.find({}, {"_id": 1, "name": 1, "team_id": 1}))
    by_canon: dict[str, str] = {}
    for team in teams:
        oid = str(team.get("_id") or "")
        if not oid:
            continue
        by_canon[_canon(team.get("name"))] = oid
        slug = team.get("team_id")
        if slug:
            by_canon[_canon(slug)] = oid

    def resolve(raw: str) -> str:
        text = str(raw or "")
        if _HEX_ID.match(text):
            return text
        return by_canon.get(_canon(text), "")

    games = db.games
    from BackEnd.persistence.sqlite_collection import SqliteCollection

    if isinstance(games, SqliteCollection):
        found: dict[tuple[int, str, str], str] = {}
        _apply_projected_rows(
            found,
            resolve,
            games.projected_tuples({"franchise_id": str(franchise_id)}, _GAME_ID_FIELDS),
        )
        return found
    return _read_game_ids_find(games, str(franchise_id), resolve)


def _read_game_ids_sqlite(games: Any, franchise_id: str, resolve) -> dict[tuple[int, str, str], str]:
    """Prefix scan, then one projected read for documents the prefix did not finish."""
    table = getattr(games, "name", "games")
    rows = _sql_rows(
        games,
        f'SELECT g_week, id, substr(doc, 1, {_PREFIX_CHARS}) FROM "{table}" WHERE g_franchise_id = ?',
        (franchise_id,),
    )
    found: dict[tuple[int, str, str], str] = {}
    if rows is None:
        _apply_projected_rows(
            found,
            resolve,
            games.projected_tuples({"franchise_id": franchise_id}, _GAME_ID_FIELDS),
        )
        return found
    missing: list[str] = []
    for week_raw, row_id, prefix in rows:
        sides: dict[str, str] = {}
        for match in _SIDE_ID.finditer(prefix or ""):
            sides.setdefault(match.group(1), match.group(2))
        away = sides.get("away_team_id", "")
        home = sides.get("home_team_id", "")
        if away and home:
            _store_matchup(found, resolve, week_raw, away, home, None, None, _decode_row_id(str(row_id)))
            continue
        missing.append(_decode_row_id(str(row_id)))
    for start in range(0, len(missing), _ID_IN_CHUNK):
        chunk = missing[start:start + _ID_IN_CHUNK]
        _apply_projected_rows(
            found,
            resolve,
            games.projected_tuples({"_id": {"$in": chunk}}, _GAME_ID_FIELDS),
        )
    return found


def _user_team_id(franchise: dict[str, Any]) -> str:
    raw = franchise.get("user_team_object_id") or franchise.get("user_team_id") or ""
    return str(raw) if raw else ""


def _result_scores(results: Any, week: int, away_id: str, home_id: str) -> tuple[int | None, int | None]:
    if not isinstance(results, dict):
        return None, None
    games = results.get(str(week)) or results.get(week) or []
    if not isinstance(games, list):
        return None, None
    for game in games:
        if not isinstance(game, dict):
            continue
        away = str(game.get("away_id") or "")
        home = str(game.get("home_id") or "")
        if away == away_id and home == home_id:
            return _as_int(game.get("away_score")), _as_int(game.get("home_score"))
        if away == home_id and home == away_id:
            return _as_int(game.get("home_score")), _as_int(game.get("away_score"))
    return None, None


def _side(team_id: str, directory: dict[str, dict[str, Any]]) -> dict[str, Any]:
    row = directory.get(team_id) or {}
    rank = row.get("natl_rank")
    if isinstance(rank, int) and rank >= 999:
        rank = None
    return {
        "team_id": team_id,
        "name": row.get("name") or team_id,
        "primary_color": row.get("primary_color"),
        "natl_rank": rank,
        "wins": int(row.get("wins") or 0),
        "losses": int(row.get("losses") or 0),
    }


def _conference_of(value: Any) -> int | None:
    number = _as_int(value)
    if number is None:
        return None
    return number


def _primary_conference(away_c: int | None, home_c: int | None, user_c: int | None, sister: int | None) -> int | None:
    if away_c is not None and away_c == home_c:
        return away_c
    if user_c is not None and away_c == user_c:
        return away_c
    if user_c is not None and home_c == user_c:
        return home_c
    if sister is not None and away_c == sister:
        return away_c
    if sister is not None and home_c == sister:
        return home_c
    if away_c is not None and home_c is not None:
        return min(away_c, home_c)
    return away_c if away_c is not None else home_c


def _sort_key(game: dict[str, Any], user_c: int | None, sister: int | None) -> tuple:
    conf = _primary_conference(game.get("_away_c"), game.get("_home_c"), user_c, sister)
    if user_c is not None and conf == user_c:
        priority = 0
    elif sister is not None and conf == sister:
        priority = 1
    else:
        priority = 2
    return (
        priority,
        conf if conf is not None else 999,
        str((game.get("away") or {}).get("name") or ""),
        str((game.get("home") or {}).get("name") or ""),
    )


def _week_label(week: int) -> str:
    title = _TOURNAMENT_LABELS.get(week)
    if title:
        return f"Week {week}: {title}"
    return f"Week {week}"


def _default_week(current: int, enabled: dict[int, bool]) -> int:
    if enabled.get(current):
        return current
    earlier = [week for week in range(_WEEK_MIN, _WEEK_MAX + 1) if enabled.get(week) and week <= current]
    if earlier:
        return earlier[-1]
    later = [week for week in range(_WEEK_MIN, _WEEK_MAX + 1) if enabled.get(week)]
    if later:
        return later[0]
    return current if _WEEK_MIN <= current <= _WEEK_MAX else 1


def _result_count(results: Any) -> int:
    if not isinstance(results, dict):
        return 0
    total = 0
    for games in results.values():
        if isinstance(games, list):
            total += len(games)
    return total


def _stamp(franchise: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _as_int(franchise.get("week")) or 0,
        _as_int(franchise.get("browse_rev")) or 0,
        _as_int(franchise.get("current_season")) or 0,
        _result_count(franchise.get("results")),
    )


def _light_stamp(franchise_id: str) -> tuple[Any, ...]:
    try:
        key: Any = ObjectId(str(franchise_id))
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid franchise ID") from exc
    doc = db.franchises.find_one(
        {"_id": key},
        {"week": 1, "browse_rev": 1, "current_season": 1, "results": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    return _stamp(doc)


def _load_franchise(franchise_id: str) -> dict[str, Any]:
    try:
        key: Any = ObjectId(str(franchise_id))
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid franchise ID") from exc
    doc = db.franchises.find_one(
        {"_id": key},
        {
            "schedule": 1,
            "results": 1,
            "week": 1,
            "browse_rev": 1,
            "current_season": 1,
            "user_team_id": 1,
            "user_team_object_id": 1,
            "team_builder": 1,
            "eos_tournament": 1,
            "eos_tournament_active": 1,
            "conference_tournaments": 1,
            "region_tournaments": 1,
            "national_tournament": 1,
        },
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    return doc


def _directory(franchise: dict[str, Any], ranks: dict[str, int | None]) -> dict[str, dict[str, Any]]:
    teams = list(db.teams.find({}, {"_id": 1, "name": 1, "primary_color": 1, "conference": 1, "team_id": 1}))
    overlay = get_team_builder_overlay(franchise)
    replaced = ""
    if overlay:
        replaced = str(overlay.get("replaced_object_id") or "")
    ids = {str(team.get("_id")): team for team in teams if team.get("_id")}
    standings = calculate_franchise_standings(franchise.get("results") or {}, {key: {} for key in ids})
    directory: dict[str, dict[str, Any]] = {}
    for team_id, team in ids.items():
        name = team.get("name") or team_id
        color = team.get("primary_color")
        if overlay and replaced and team_id == replaced:
            display = resolve_team_display(franchise, team_id, core_doc=team)
            name = display.get("name") or name
            color = display.get("primary_color") or color
        record = standings.get(team_id) or {}
        directory[team_id] = {
            "name": name,
            "primary_color": color,
            "conference": _conference_of(team.get("conference")),
            "natl_rank": ranks.get(team_id),
            "wins": int(record.get("W") or 0),
            "losses": int(record.get("L") or 0),
        }
    return directory


def _regular_games(franchise: dict[str, Any], directory: dict[str, dict[str, Any]], game_ids: dict[tuple[int, str, str], str]) -> dict[int, list[dict[str, Any]]]:
    schedule = franchise.get("schedule") or []
    results = franchise.get("results") or {}
    user_id = _user_team_id(franchise)
    by_week: dict[int, list[dict[str, Any]]] = {}
    if not isinstance(schedule, list):
        return by_week
    for index, games in enumerate(schedule, start=1):
        if index > _REGULAR_MAX or not isinstance(games, list):
            continue
        rows = []
        for pair in games:
            if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                continue
            away_id = str(pair[0] or "")
            home_id = str(pair[1] or "")
            if not away_id or not home_id:
                continue
            away_score, home_score = _result_scores(results, index, away_id, home_id)
            complete = away_score is not None and home_score is not None
            away = directory.get(away_id) or {}
            home = directory.get(home_id) or {}
            rows.append({
                "away": _side(away_id, directory),
                "home": _side(home_id, directory),
                "away_score": away_score if complete else None,
                "home_score": home_score if complete else None,
                "status": "complete" if complete else "scheduled",
                "game_id": game_ids.get((index, away_id, home_id)) if complete else None,
                "is_user": bool(user_id and user_id in {away_id, home_id}),
                "tournament_context": None,
                "_away_c": away.get("conference"),
                "_home_c": home.get("conference"),
            })
        by_week[index] = rows
    return by_week


def _eos_games(eos_schedule: dict[Any, Any], directory: dict[str, dict[str, Any]], user_id: str) -> dict[int, list[dict[str, Any]]]:
    by_week: dict[int, list[dict[str, Any]]] = {}
    for raw_week, games in (eos_schedule or {}).items():
        week = _as_int(raw_week)
        if week is None or week < 27 or week > _WEEK_MAX or not isinstance(games, list):
            continue
        rows = []
        for game in games:
            if not isinstance(game, dict):
                continue
            away_id = str(game.get("away_team_id") or "")
            home_id = str(game.get("home_team_id") or "")
            if not away_id or not home_id:
                continue
            away_score = _as_int(game.get("away_score"))
            home_score = _as_int(game.get("home_score"))
            complete = game.get("status") == "complete" or (away_score is not None and home_score is not None)
            away = directory.get(away_id) or {}
            home = directory.get(home_id) or {}
            rows.append({
                "away": _side(away_id, directory),
                "home": _side(home_id, directory),
                "away_score": away_score if complete else None,
                "home_score": home_score if complete else None,
                "status": "complete" if complete else "scheduled",
                "game_id": str(game.get("game_id")) if complete and game.get("game_id") else None,
                "is_user": bool(user_id and user_id in {away_id, home_id}),
                "tournament_context": game.get("tournament_context") or None,
                "_away_c": _conference_of(game.get("away_conference") if game.get("away_conference") is not None else away.get("conference")),
                "_home_c": _conference_of(game.get("home_conference") if game.get("home_conference") is not None else home.get("conference")),
            })
        by_week[week] = rows
    return by_week


def _bundle(franchise_id: str, eos_builder: Callable[..., Any]) -> dict[str, Any]:
    stamp = _light_stamp(franchise_id)
    cached = _BUNDLES.get(str(franchise_id))
    if cached and cached[0] == stamp:
        return cached[1]
    franchise = _load_franchise(franchise_id)
    ranks = _rank_map(str(franchise_id))
    directory = _directory(franchise, ranks)
    game_ids = matchup_game_ids(str(franchise_id), stamp)
    conferences = {team_id: row.get("conference") for team_id, row in directory.items()}
    eos_schedule, _ids = eos_builder(franchise, conferences)
    user_id = _user_team_id(franchise)
    weeks = _regular_games(franchise, directory, game_ids)
    weeks.update(_eos_games(eos_schedule, directory, user_id))
    user_c = (directory.get(user_id) or {}).get("conference")
    sister = None
    if isinstance(user_c, int):
        sister = user_c - 1 if user_c % 2 == 0 else user_c + 1
    for rows in weeks.values():
        rows.sort(key=lambda game: _sort_key(game, user_c, sister))
    enabled = {week: bool(weeks.get(week)) for week in range(_WEEK_MIN, _WEEK_MAX + 1)}
    current = _as_int(franchise.get("week")) or 1
    if current < _WEEK_MIN:
        current = 1
    if current > _WEEK_MAX:
        current = _WEEK_MAX
    bundle = {
        "current_week": current,
        "default_week": _default_week(current, enabled),
        "user_team_id": user_id,
        "weeks": weeks,
        "enabled": enabled,
    }
    _BUNDLES[str(franchise_id)] = (stamp, bundle)
    return bundle


def _public_game(game: dict[str, Any]) -> dict[str, Any]:
    return {
        "away": game["away"],
        "home": game["home"],
        "away_score": game["away_score"],
        "home_score": game["home_score"],
        "status": game["status"],
        "game_id": game.get("game_id"),
        "is_user": bool(game.get("is_user")),
        "tournament_context": game.get("tournament_context"),
    }


def build_schedule_week(
    franchise_id: str,
    week: int | None,
    eos_builder: Callable[..., Any],
) -> dict[str, Any]:
    bundle = _bundle(str(franchise_id), eos_builder)
    chosen = week if week is not None else bundle["default_week"]
    if chosen < _WEEK_MIN or chosen > _WEEK_MAX:
        raise HTTPException(status_code=422, detail="week must be from 1 to 34")
    catalog = []
    for number in range(_WEEK_MIN, _WEEK_MAX + 1):
        catalog.append({
            "week": number,
            "label": _week_label(number),
            "enabled": bool(bundle["enabled"].get(number)),
        })
    return {
        "week": chosen,
        "label": _week_label(chosen),
        "current_week": bundle["current_week"],
        "user_team_id": bundle["user_team_id"],
        "weeks": catalog,
        "games": [_public_game(game) for game in bundle["weeks"].get(chosen) or []],
    }
