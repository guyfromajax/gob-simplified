"""Payloads for the T3 player and team pages.

The page formats these numbers. It does not derive them. Reads are projected
the same way team stats extracts a season line: equality on indexed
``franchise_id`` / ``player_id`` / ``team_id`` / ``_id``, so SQLite does not
decode the rest of the document.
"""

from __future__ import annotations

from typing import Any, Mapping

from bson import ObjectId
from fastapi import HTTPException

from BackEnd.constants.training_shape import (
    TRAINING_FOCUS_PERCENTAGES,
    TRAINING_FOCUSES,
    resolve_training_focus,
    resolve_training_position,
)
from BackEnd.models.training_execution_v2 import training_report_display_bucket
from BackEnd.utils.franchise_standings import (
    calculate_franchise_standings,
    current_streaks,
    standings_display_sort_key,
)
from BackEnd.utils.franchise_team_display import resolve_team_display
from BackEnd.utils.leaders_snapshot import _roster_position
from BackEnd.utils.player_year import format_player_year_abbrev
from BackEnd.utils.rt_projection import potential_rt_for_player

# Offense, Defense, Skills, Grit, Body, Mind. Display order is this tuple.
ATTRIBUTE_GROUPS: tuple[tuple[str, str, tuple[str, str]], ...] = (
    ("offense", "Offense", ("SC", "SH")),
    ("defense", "Defense", ("ID", "OD")),
    ("skills", "Skills", ("PS", "BH")),
    ("grit", "Grit", ("RB", "ST")),
    ("body", "Body", ("AG", "ND")),
    ("mind", "Mind", ("IQ", "FT")),
)
ATTR_ORDER: tuple[str, ...] = tuple(
    attr for _group_id, _label, attrs in ATTRIBUTE_GROUPS for attr in attrs
)
FOCUS_LABELS = {
    "standard": "Standard",
    "offensive": "Offensive",
    "defensive": "Defensive",
    "athletic": "Athletic",
    "fundamentals": "Fundamentals",
    "rebounding": "Rebounding",
}
_TOTAL_KEYS = (
    "GP", "MIN", "PTS", "REB", "AST", "STL", "BLK",
    "FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA", "DEF_S", "DEF_A",
)
_PLAYER_PROJECTION = {
    "player_id": 1,
    "meta.first_name": 1,
    "meta.last_name": 1,
    "meta.team": 1,
    "meta.team_id": 1,
    "meta.position": 1,
    "meta.year": 1,
    "meta.height": 1,
    "meta.weight": 1,
    "meta.jersey": 1,
    "attributes": 1,
    "position_ratings": 1,
    "season": 1,
    "career": 1,
    "training_position": 1,
    "training_focus": 1,
    "resolved_training_position": 1,
    "position_intent": 1,
    "entry_tier": 1,
    "potential_factor": 1,
}
_TEAM_PROJECTION = {
    "name": 1,
    "primary_color": 1,
    "conference": 1,
    "region": 1,
    "team_id": 1,
    "mascot": 1,
}


def _store():
    from BackEnd.persistence import get_store

    return get_store()


def _oid(value: str, label: str) -> ObjectId:
    try:
        return ObjectId(str(value))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {label} format")


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    return int(number)


def conference_label(conference: Any) -> str | None:
    """Region letter plus the conference's own number: A1, A2, B3 … H16."""
    if isinstance(conference, bool):
        return None
    if not isinstance(conference, int):
        number = _as_int(conference)
        if number is None:
            return None
        conference = number
    if conference < 1 or conference > 16:
        return None
    letter = chr(ord("A") + (conference - 1) // 2)
    return f"{letter}{conference}"


def _region_letter(conference: Any) -> str | None:
    label = conference_label(conference)
    return label[:1] if label else None


def _ordinal(place: int) -> str:
    if 10 <= (place % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(place % 10, "th")
    return f"{place}{suffix}"


def _user_team(franchise: Mapping[str, Any]) -> tuple[str, str]:
    return (
        str(franchise.get("user_team_object_id") or ""),
        str(franchise.get("user_team_id") or ""),
    )


def _on_user_team(team_id: Any, team_name: Any, user_team_id: str, user_team_name: str) -> bool:
    if user_team_id and str(team_id or "") == user_team_id:
        return True
    if user_team_name and str(team_name or "") == user_team_name:
        return True
    return False


def _whole(number: float) -> int | float:
    if number == int(number):
        return int(number)
    return number


def _highest_rt(ratings: Any) -> int | float | None:
    if not isinstance(ratings, dict):
        return None
    best: float | None = None
    for value in ratings.values():
        number = _num(value)
        if number is None:
            continue
        if best is None or number > best:
            best = number
    return None if best is None else _whole(best)


def _attribute_groups(attributes: Any) -> list[dict[str, Any]]:
    attrs = attributes if isinstance(attributes, dict) else {}
    groups = []
    for group_id, label, keys in ATTRIBUTE_GROUPS:
        rows = []
        for attr in keys:
            raw = _num(attrs.get(attr))
            if raw is None:
                raw = _num(attrs.get(f"anchor_{attr}"))
            if raw is not None:
                raw = _whole(raw)
            rows.append({
                "attr": attr,
                "raw": raw,
                "display": None if raw is None else training_report_display_bucket(raw),
            })
        groups.append({"id": group_id, "label": label, "attrs": rows})
    return groups


def _total(block: Mapping[str, Any], key: str) -> int | float:
    number = _num(block.get(key))
    return 0 if number is None else _whole(number)


def _per_game(total: float, games: float) -> int | float | None:
    if games <= 0:
        return None
    return _whole(total / games)


def _pct(made: float, attempts: float) -> int | float | None:
    if attempts <= 0:
        return None
    return _whole((made / attempts) * 100.0)


def stat_line(block: Any) -> dict[str, Any]:
    """Season or career line. Rates are null when that attempt count is 0."""
    raw = block if isinstance(block, dict) else {}
    totals = {key: _total(raw, key) for key in _TOTAL_KEYS}
    games = totals["GP"]
    return {
        "gp": totals["GP"],
        "min_per_game": _per_game(totals["MIN"], games),
        "pts_per_game": _per_game(totals["PTS"], games),
        "reb_per_game": _per_game(totals["REB"], games),
        "ast_per_game": _per_game(totals["AST"], games),
        "stl_per_game": _per_game(totals["STL"], games),
        "blk_per_game": _per_game(totals["BLK"], games),
        "fg_pct": _pct(totals["FGM"], totals["FGA"]),
        "tp_pct": _pct(totals["3PTM"], totals["3PTA"]),
        "ft_pct": _pct(totals["FTM"], totals["FTA"]),
        "def_pct": _pct(totals["DEF_S"], totals["DEF_A"]),
        "totals": totals,
    }


def emphasises(position: str, focus: str) -> list[str]:
    """Up to three attributes this focus weights above ``standard``.

    ``standard`` emphasises nothing. Ties keep attribute-group order.
    """
    if focus == "standard" or focus not in TRAINING_FOCUSES:
        return []
    table = TRAINING_FOCUS_PERCENTAGES.get(position)
    if not table:
        return []
    standard = table.get("standard") or {}
    chosen = table.get(focus) or {}
    ranked: list[tuple[float, str]] = []
    for attr in ATTR_ORDER:
        delta = float(chosen.get(attr, 100)) - float(standard.get(attr, 100))
        if delta > 0:
            ranked.append((delta, attr))
    ranked.sort(key=lambda item: -item[0])
    return [attr for _delta, attr in ranked[:3]]


def _player_name(meta: Mapping[str, Any]) -> str:
    return f"{meta.get('first_name') or ''} {meta.get('last_name') or ''}".strip()


def _name_entry(bucket: Mapping[str, Any], player_name: str) -> dict | None:
    if player_name and isinstance(bucket.get(player_name), dict):
        return bucket[player_name]
    folded = player_name.casefold()
    for key, value in bucket.items():
        if isinstance(value, dict) and str(key).strip().casefold() == folded and folded:
            return value
    return None


def _has_from_to(entry: Mapping[str, Any]) -> bool:
    return any(
        isinstance(value, dict) and "from" in value and "to" in value
        for value in entry.values()
    )


def _from_to_changes(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for attr in ATTR_ORDER:
        cell = entry.get(attr)
        if not isinstance(cell, dict) or "from" not in cell or "to" not in cell:
            continue
        start = _num(cell.get("from"))
        end = _num(cell.get("to"))
        if start is None or end is None or start == end:
            continue
        rows.append({"attr": attr, "from": _whole(start), "to": _whole(end)})
    return rows


def _delta_changes(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for attr in ATTR_ORDER:
        value = entry.get(attr)
        if isinstance(value, dict) and "from" in value and "to" in value:
            start = _num(value.get("from"))
            end = _num(value.get("to"))
            if start is None or end is None or start == end:
                continue
            rows.append({"attr": attr, "from": _whole(start), "to": _whole(end)})
            continue
        delta = _num(value)
        if delta is None or delta == 0:
            continue
        rows.append({"attr": attr, "delta": _whole(delta)})
    return rows


def recent_changes(reports: Any, player_id: str, player_name: str) -> list[dict[str, Any]]:
    """Current-season training reports for one player, newest week first.

    The current writer stores display buckets under
    ``player_attribute_display_movements``. Older weeks store a name-keyed
    map of signed raw deltas (``player_changes`` / ``player_logs``). A delta
    week has no from/to, so the change is ``{attr, delta}`` only.
    """
    if not isinstance(reports, dict):
        return []
    weeks: list[tuple[int, Mapping[str, Any]]] = []
    for key, report in reports.items():
        if not isinstance(report, dict):
            continue
        try:
            week = int(key)
        except (TypeError, ValueError):
            week = _as_int(report.get("week"))
        if week is None:
            continue
        weeks.append((week, report))
    weeks.sort(key=lambda item: -item[0])
    rows = []
    for week, report in weeks:
        movements = report.get("player_attribute_display_movements")
        changes: list[dict[str, Any]] = []
        used_display = False
        if isinstance(movements, dict):
            entry = movements.get(player_id) or movements.get(str(player_id))
            if isinstance(entry, dict) and _has_from_to(entry):
                changes = _from_to_changes(entry)
                used_display = True
        if not changes and not used_display:
            for bucket_name in ("player_changes", "player_logs"):
                bucket = report.get(bucket_name)
                if isinstance(bucket, dict):
                    entry = _name_entry(bucket, player_name)
                    if isinstance(entry, dict):
                        changes = _delta_changes(entry)
                        break
        if not changes and not used_display and isinstance(movements, dict):
            entry = _name_entry(movements, player_name)
            if isinstance(entry, dict):
                changes = _delta_changes(entry)
        if not changes:
            continue
        session = report.get("session_type")
        if not session:
            session = "preseason" if week <= 1 else "in-season"
        rows.append({
            "week": week,
            "session_type": str(session),
            "changes": changes,
        })
    return rows


def _development(doc: Mapping[str, Any], position: str, editable: bool) -> dict[str, Any]:
    focus = resolve_training_focus(doc)
    train_pos = position if position in TRAINING_FOCUS_PERCENTAGES else resolve_training_position(doc)
    return {
        "focus": focus,
        "focus_label": FOCUS_LABELS.get(focus, focus.title() if focus else "Standard"),
        "emphasises": emphasises(train_pos, focus),
        "editable": editable,
    }


def build_player_detail(franchise_id: str, player_id: str) -> dict[str, Any]:
    store = _store()
    fid = _oid(franchise_id, "franchise ID")
    franchise = store.franchises_collection.find_one(
        {"_id": fid},
        {"user_team_id": 1, "user_team_object_id": 1, "team_builder": 1},
    )
    if not franchise:
        raise HTTPException(status_code=404, detail="Franchise not found")
    player = store.franchise_players_data_collection.find_one(
        {"franchise_id": str(franchise_id), "player_id": str(player_id)},
        _PLAYER_PROJECTION,
    )
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    meta = player.get("meta") if isinstance(player.get("meta"), dict) else {}
    user_team_id, user_team_name = _user_team(franchise)
    team_id = str(meta.get("team_id") or "")
    is_user = _on_user_team(team_id, meta.get("team"), user_team_id, user_team_name)
    ratings = player.get("position_ratings") if isinstance(player.get("position_ratings"), dict) else {}
    position = _roster_position(
        meta.get("position"),
        ratings,
        player.get("training_position"),
        player.get("resolved_training_position"),
        on_user_team=is_user,
    )
    team_doc = None
    if team_id and ObjectId.is_valid(team_id):
        team_doc = store.teams_collection.find_one({"_id": ObjectId(team_id)}, _TEAM_PROJECTION)
    display = resolve_team_display(franchise, team_id, core_doc=team_doc or {})
    team_name = display.get("name") or (str(meta.get("team")) if meta.get("team") else None)
    reports = None
    if team_id and ObjectId.is_valid(team_id):
        ftd = store.franchise_team_data_collection.find_one(
            {"franchise_id": fid, "team_id": ObjectId(team_id)},
            {"training_reports": 1},
        )
        if ftd:
            reports = ftd.get("training_reports")
    name = _player_name(meta)
    year = format_player_year_abbrev(meta.get("year"))
    return {
        "player_id": str(player_id),
        "name": name,
        "team_id": team_id or None,
        "team_name": team_name or None,
        "team_primary_color": display.get("primary_color") if team_doc else None,
        "position": position,
        "year": year,
        "height_in": _as_int(meta.get("height")),
        "weight": None if (weight := _num(meta.get("weight"))) is None else _whole(weight),
        "jersey": meta.get("jersey"),
        "is_user_team": is_user,
        "rt": _highest_rt(ratings),
        "potential": potential_rt_for_player(
            player_id,
            player.get("entry_tier"),
            player.get("potential_factor"),
            ratings,
        ),
        "attributes": _attribute_groups(player.get("attributes")),
        "season": stat_line(player.get("season")),
        "career": stat_line(player.get("career")),
        "recent_changes": recent_changes(reports, str(player_id), name),
        "development": _development(player, position, is_user),
    }


def _team_docs(store, team_ids: list[str]) -> dict[str, dict]:
    oids = []
    for team_id in team_ids:
        if ObjectId.is_valid(team_id):
            oids.append(ObjectId(team_id))
    if not oids:
        return {}
    found = store.teams_collection.find({"_id": {"$in": oids}}, _TEAM_PROJECTION)
    return {str(doc.get("_id")): doc for doc in found}


def _opponent(
    opponent_id: str,
    teams_by_id: Mapping[str, Mapping[str, Any]],
    ranks: Mapping[str, Any],
    franchise: Mapping[str, Any],
) -> dict[str, Any]:
    display = resolve_team_display(
        franchise,
        opponent_id,
        core_doc=teams_by_id.get(opponent_id) or {},
    )
    name = display.get("name") or None
    return {
        "opponent_id": opponent_id,
        "opponent_name": name or None,
        "opponent_primary_color": display.get("primary_color") if teams_by_id.get(opponent_id) else None,
        "opponent_natl_rank": _as_int(ranks.get(opponent_id)),
    }


def _schedule_rows(schedule: Any) -> list[tuple[int, str, str]]:
    rows = []
    if not isinstance(schedule, list):
        return rows
    for index, games in enumerate(schedule, start=1):
        if not isinstance(games, list):
            continue
        for game in games:
            if isinstance(game, (list, tuple)) and len(game) >= 2:
                away_id = str(game[0] or "")
                home_id = str(game[1] or "")
                if away_id and home_id:
                    rows.append((index, away_id, home_id))
    return rows


def _completed(results: Any) -> dict[tuple[int, str, str], tuple[int, int]]:
    done: dict[tuple[int, str, str], tuple[int, int]] = {}
    if not isinstance(results, dict):
        return done
    for key, games in results.items():
        week = _as_int(key)
        if week is None or not isinstance(games, list):
            continue
        for game in games:
            if not isinstance(game, dict):
                continue
            away_id = str(game.get("away_id") or "")
            home_id = str(game.get("home_id") or "")
            if not away_id or not home_id:
                continue
            away_score = _as_int(game.get("away_score"))
            home_score = _as_int(game.get("home_score"))
            if away_score is None or home_score is None:
                continue
            done[(week, away_id, home_id)] = (away_score, home_score)
    return done


def _result_letter(team_score: int, opp_score: int) -> str | None:
    if team_score > opp_score:
        return "W"
    if team_score < opp_score:
        return "L"
    return None


def build_team_detail(franchise_id: str, team_id: str) -> dict[str, Any]:
    store = _store()
    fid = _oid(franchise_id, "franchise ID")
    tid = _oid(team_id, "team ID")
    team_id = str(tid)
    franchise = store.franchises_collection.find_one(
        {"_id": fid},
        {
            "week": 1,
            "schedule": 1,
            "results": 1,
            "user_team_id": 1,
            "user_team_object_id": 1,
            "team_builder": 1,
        },
    )
    if not franchise:
        raise HTTPException(status_code=404, detail="Franchise not found")
    ftd_rows = list(store.franchise_team_data_collection.find(
        {"franchise_id": fid},
        {"team_id": 1, "natl_rank": 1},
    ))
    ranks = {
        str(row.get("team_id")): row.get("natl_rank")
        for row in ftd_rows
        if row.get("team_id")
    }
    if team_id not in ranks:
        raise HTTPException(status_code=404, detail="Team not found")

    results = franchise.get("results") or {}
    standings = calculate_franchise_standings(results, {key: {} for key in ranks})
    teams_by_id = _team_docs(store, list(ranks))
    team_doc = teams_by_id.get(team_id) or {}
    display = resolve_team_display(franchise, team_id, core_doc=team_doc)
    conference = team_doc.get("conference")
    label = conference_label(conference)
    region = team_doc.get("region")
    if region:
        region = str(region)
    else:
        region = _region_letter(conference)

    members = []
    for member_id, member_doc in teams_by_id.items():
        if member_doc.get("conference") != conference or conference is None:
            continue
        row = dict(standings.get(member_id) or {})
        row["team_id"] = member_id
        members.append(row)
    members.sort(key=standings_display_sort_key)
    place = None
    for index, row in enumerate(members, start=1):
        if row["team_id"] == team_id:
            place = f"{_ordinal(index)} of {len(members)}"
            break

    record_row = standings.get(team_id) or {}
    streak = current_streaks(results).get(team_id)

    completed = _completed(results)
    played_keys = set(completed)
    results_rows = []
    for (week, away_id, home_id), (away_score, home_score) in completed.items():
        if team_id not in {away_id, home_id}:
            continue
        if team_id == home_id:
            site = "home"
            opponent_id = away_id
            team_score, opp_score = home_score, away_score
        else:
            site = "away"
            opponent_id = home_id
            team_score, opp_score = away_score, home_score
        results_rows.append({
            "week": week,
            "site": site,
            "team_score": team_score,
            "opp_score": opp_score,
            "result": _result_letter(team_score, opp_score),
            **_opponent(opponent_id, teams_by_id, ranks, franchise),
        })
    results_rows.sort(key=lambda row: -row["week"])

    remaining = []
    for week, away_id, home_id in _schedule_rows(franchise.get("schedule")):
        if team_id not in {away_id, home_id}:
            continue
        if (week, away_id, home_id) in played_keys:
            continue
        if team_id == home_id:
            site, opponent_id = "home", away_id
        else:
            site, opponent_id = "away", home_id
        remaining.append({
            "week": week,
            "site": site,
            **_opponent(opponent_id, teams_by_id, ranks, franchise),
        })
    remaining.sort(key=lambda row: row["week"])
    next_game = remaining[0] if remaining else None
    upcoming = remaining[1:] if remaining else []

    return {
        "team_id": team_id,
        "name": display.get("name") or None,
        "primary_color": display.get("primary_color") if team_doc else None,
        "conference": label,
        "region": region,
        "record": {
            "wins": int(record_row.get("W") or 0),
            "losses": int(record_row.get("L") or 0),
        },
        "natl_rank": _as_int(ranks.get(team_id)),
        "conference_place": place,
        "streak": streak,
        "next_game": next_game,
        "results": results_rows,
        "upcoming": upcoming,
    }
