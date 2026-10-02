"""The week-1 Office (the season preview) and the all-season Top Recruits list.

Pure builders: every function takes documents the caller already loaded and returns
JSON-ready rows. Nothing here reads a database, runs a sim, or shows a hidden attribute.
The routes file does the reads (``_season_preview_context``) and the season rollover
stores one small snapshot (``last_season_snapshot``) so next season's preview can say
what the rollover is about to wipe: the results and the seniors who leave.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

LAST_SEASON_FIELD = "last_season"
SECTION_ROWS = 5  # no section runs longer than this
CIRCLE_GAMES = 3

# How the season ended, as a clause after the record ("18-8, lost in the Region semifinal").
_ROUND_CLAUSE = {
    "national_final": "lost in the National final",
    "national_semis": "lost in the National semifinal",
    "national_quarters": "lost in the National quarterfinal",
    "region_final": "lost in the Region final",
    "region_semis": "lost in the Region semifinal",
    "conference_final": "lost in the Conference final",
    "conference_semis": "lost in the Conference semifinal",
    "conference_quarters": "lost in the Conference quarterfinal",
    "missed": "missed the bracket",
}
_NATIONAL_TITLE_CLAUSE = "won the National championship"


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def region_letter(conference: Any) -> Optional[str]:
    """Conferences pair into regions: 1-2 = A ... 15-16 = H."""
    number = _int(conference)
    if number is None or number < 1:
        return None
    return chr(ord("A") + (number - 1) // 2)


def _ranking_rows(rankings: Iterable[Any]) -> list[dict[str, Any]]:
    rows = []
    for row in rankings or []:
        if not isinstance(row, Mapping) or row.get("team_id") is None:
            continue
        rank = _int(row.get("natl_rank"))
        if rank is None:
            continue
        rows.append({
            "team_id": str(row.get("team_id")),
            "team_name": row.get("team_name") or None,
            "conference": row.get("conference"),
            "natl_rank": rank,
        })
    rows.sort(key=lambda row: (row["natl_rank"], str(row["team_name"] or "")))
    return rows


def _place(rows: list[dict[str, Any]], team_id: str) -> Optional[dict[str, int]]:
    for index, row in enumerate(rows, start=1):
        if row["team_id"] == team_id:
            return {"rank": index, "of": len(rows)}
    return None


def rankings_block(rankings: Iterable[Any], user_team_id: Any, user_conference: Any) -> Optional[dict[str, Any]]:
    """Where the preseason national rank puts the team: in its conference, its region, the nation."""
    rows = _ranking_rows(rankings)
    tid = str(user_team_id or "")
    if not rows or not any(row["team_id"] == tid for row in rows):
        return None
    region = region_letter(user_conference)
    conference_rows = [row for row in rows if row["conference"] == user_conference]
    region_rows = [row for row in rows if region and region_letter(row["conference"]) == region]
    return {
        "conference": _place(conference_rows, tid),
        "region": _place(region_rows, tid),
        "national": _place(rows, tid),
    }


def preseason_rankings(rankings: Iterable[Any], user_team_id: Any, user_conference: Any) -> Optional[dict[str, Any]]:
    """The user's conference, best national rank first."""
    tid = str(user_team_id or "")
    rows = [row for row in _ranking_rows(rankings) if row["conference"] == user_conference]
    if not rows:
        return None
    return {
        "conference": user_conference,
        "rows": [
            {
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "national_rank": row["natl_rank"],
                "is_user": row["team_id"] == tid,
            }
            for row in rows
        ],
    }


def last_season_line(
    trophies: Iterable[Any],
    franchise_id: Any,
    season: Any,
) -> Optional[dict[str, Any]]:
    """Last season's record and how it ended, from the coach's season-record trophy."""
    fid = str(franchise_id or "")
    wanted = _int(season)
    record = None
    titles: set[str] = set()
    for trophy in trophies or []:
        if not isinstance(trophy, Mapping) or str(trophy.get("franchise_id") or "") != fid:
            continue
        if _int(trophy.get("season")) != wanted:
            continue
        kind = str(trophy.get("kind") or "")
        if kind == "season_record":
            record = trophy.get("detail") if isinstance(trophy.get("detail"), Mapping) else {}
        elif kind in {"national", "region", "conf_t", "conf_rs"}:
            titles.add(kind)
    if record is None:
        return None
    wins, losses = _int(record.get("wins")), _int(record.get("losses"))
    if wins is None or losses is None:
        return None
    if "national" in titles:
        finish = _NATIONAL_TITLE_CLAUSE
    else:
        finish = _ROUND_CLAUSE.get(str(record.get("furthest_round") or ""))
    return {"wins": wins, "losses": losses, "finish": finish}


def _name(meta: Mapping[str, Any]) -> str:
    return f"{meta.get('first_name', '') or ''} {meta.get('last_name', '') or ''}".strip()


def _best(position_ratings: Any) -> tuple[Optional[str], Optional[int]]:
    """(position, rating) of the highest slot rating: the roster's RT."""
    best_pos, best = None, None
    if isinstance(position_ratings, Mapping):
        for pos, raw in position_ratings.items():
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if best is None or value > best:
                best_pos, best = str(pos), value
    return best_pos, (int(round(best)) if best is not None else None)


def roster_rows(player_docs: Iterable[Any]) -> list[dict[str, Any]]:
    """One row per roster player: the visible identity fields, best RT first."""
    from BackEnd.utils.player_year import format_player_year_abbrev
    from BackEnd.utils.walk_on_portraits import is_walk_on_fpd

    rows = []
    for doc in player_docs or []:
        if not isinstance(doc, Mapping) or not doc.get("player_id"):
            continue
        meta = doc.get("meta") if isinstance(doc.get("meta"), Mapping) else {}
        pos, rt = _best(doc.get("position_ratings"))
        rows.append({
            "player_id": str(doc.get("player_id")),
            "name": _name(meta),
            "rt": rt,
            "pos": pos,
            "year": format_player_year_abbrev(meta.get("year")),
            "height": _int(meta.get("height")),
            "weight": _int(meta.get("weight")),
            "walk_on": is_walk_on_fpd(dict(doc)),
        })
    rows.sort(key=lambda row: (-(row["rt"] if row["rt"] is not None else -1), row["name"]))
    return rows


def _public(row: Mapping[str, Any], *fields: str) -> dict[str, Any]:
    return {field: row.get(field) for field in fields}


def key_players(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _public(row, "player_id", "name", "rt", "pos", "year", "height", "weight")
        for row in rows[:SECTION_ROWS]
    ]


def walk_on_rows(
    rows: list[dict[str, Any]],
    *,
    season: int,
    pending_walk_ons: Iterable[Any],
) -> list[dict[str, Any]]:
    """This season's walk-ons on the roster.

    A walk-on is a franchise player whose ``meta.archetype`` is the "Walk On" sentinel.
    Season 1 creates three per team with the franchise, so every walk-on is this season's.
    From season 2 the archetype alone cannot tell this season's arrivals from walk-ons who
    stayed, so the rollover's ``pending_walk_on_welcome`` list names them.
    """
    if season <= 1:
        picked = [row for row in rows if row.get("walk_on")]
    else:
        ids = {
            str(item.get("player_id"))
            for item in (pending_walk_ons or [])
            if isinstance(item, Mapping) and item.get("player_id")
        }
        picked = [row for row in rows if row["player_id"] in ids]
    return [_public(row, "player_id", "name", "pos", "year", "rt") for row in picked[:SECTION_ROWS]]


def newcomers_block(
    rows: list[dict[str, Any]],
    *,
    season: int,
    last_season: Mapping[str, Any] | None,
    class_signed: Iterable[Any],
    walk_on_ids: Iterable[str],
) -> Optional[dict[str, Any]]:
    """Last season's signing class now on the roster, and the roster's turnover line.

    The class is the rollover snapshot's player ids when the save has one, else the names on
    the coach's season review (a save that rolled over before the snapshot existed). ``None``
    in season 1 and whenever no prior class is on the roster.
    """
    if season <= 1:
        return None
    snapshot = last_season if isinstance(last_season, Mapping) else {}
    ids = {
        str(item.get("player_id"))
        for item in (snapshot.get("signed_class") or [])
        if isinstance(item, Mapping) and item.get("player_id")
    }
    names = {
        str(item.get("name") or "").strip().lower()
        for item in list(snapshot.get("signed_class") or []) + list(class_signed or [])
        if isinstance(item, Mapping) and item.get("name")
    }
    walk_ons = {str(pid) for pid in walk_on_ids or []}
    signed = [
        row for row in rows
        if row["player_id"] not in walk_ons
        and (row["player_id"] in ids or (not ids and row["name"].strip().lower() in names))
    ]
    if not signed:
        return None
    lost = _int(snapshot.get("graduated_seniors"))
    return {
        "players": [_public(row, "player_id", "name", "pos", "rt") for row in signed[:SECTION_ROWS]],
        "returning": max(0, len(rows) - len(signed) - len(walk_ons.intersection(row["player_id"] for row in rows))),
        "lost_seniors": lost,
        "newcomers": len(signed),
    }


def all_americans(projection: Mapping[str, Any] | None, user_team_id: Any) -> list[dict[str, Any]]:
    """The projection's first team: who, where and how good. Never the score behind it."""
    teams = (projection or {}).get("all_american_teams") if isinstance(projection, Mapping) else None
    first = (teams or {}).get("first_team") if isinstance(teams, Mapping) else None
    tid = str(user_team_id or "")
    rows = []
    for pick in first or []:
        if not isinstance(pick, Mapping) or not pick.get("name"):
            continue
        rating = pick.get("rating")
        try:
            rt = int(round(float(rating)))
        except (TypeError, ValueError):
            rt = None
        rows.append({
            "position": pick.get("position"),
            "player_id": str(pick.get("player_id") or "") or None,
            "name": pick.get("name"),
            "team_id": str(pick.get("team_id") or "") or None,
            "team_name": pick.get("team_name") or None,
            "rt": rt,
            "is_user": bool(tid) and str(pick.get("team_id") or "") == tid,
        })
    return rows[:SECTION_ROWS]


def user_schedule(schedule: Iterable[Any], user_team_id: Any) -> list[dict[str, Any]]:
    """The user's regular-season games in week order."""
    tid = str(user_team_id or "")
    games = []
    for index, week_games in enumerate(schedule or [], start=1):
        for pair in week_games or []:
            try:
                away_id, home_id = str(pair[0]), str(pair[1])
            except (TypeError, IndexError, KeyError):
                continue
            if tid not in {away_id, home_id}:
                continue
            games.append({
                "week": index,
                "opponent_team_id": away_id if home_id == tid else home_id,
                "site": "home" if home_id == tid else "away",
            })
            break
    return games


def circle_these(
    schedule: Iterable[Any],
    user_team_id: Any,
    rankings: Iterable[Any],
) -> list[dict[str, Any]]:
    """The toughest games on the schedule by the opponent's national rank, in week order."""
    by_team = {row["team_id"]: row for row in _ranking_rows(rankings)}
    games = []
    for game in user_schedule(schedule, user_team_id):
        opponent = by_team.get(game["opponent_team_id"])
        if not opponent:
            continue
        games.append({
            "week": game["week"],
            "site": game["site"],
            "opponent_team_id": opponent["team_id"],
            "opponent": opponent["team_name"],
            "rank": opponent["natl_rank"],
        })
    toughest = sorted(games, key=lambda game: (game["rank"], game["week"]))[:CIRCLE_GAMES]
    return sorted(toughest, key=lambda game: game["week"])


def last_meeting(last_season: Mapping[str, Any] | None, opponent_team_id: Any) -> Optional[dict[str, Any]]:
    """Last season's most recent game against this opponent, from the rollover snapshot."""
    meetings = (last_season or {}).get("meetings") if isinstance(last_season, Mapping) else None
    row = (meetings or {}).get(str(opponent_team_id or "")) if isinstance(meetings, Mapping) else None
    if not isinstance(row, Mapping):
        return None
    user_score, opp_score = _int(row.get("user_score")), _int(row.get("opp_score"))
    if user_score is None or opp_score is None or user_score == opp_score:
        return None
    return {
        "won": user_score > opp_score,
        "user_score": user_score,
        "opp_score": opp_score,
        "week": _int(row.get("week")),
    }


def top_recruits(
    recruit_docs: Iterable[Any],
    *,
    region: Any,
    user_team_id: Any,
    team_name_map: Mapping[str, Any] | None,
) -> Optional[dict[str, Any]]:
    """The best-rated recruits from the user's region, each with the team leading for him."""
    letter = str(region or "").strip().upper()
    if not letter:
        return None
    names = team_name_map or {}
    tid = str(user_team_id or "")
    rows = []
    for doc in recruit_docs or []:
        if not isinstance(doc, Mapping) or not doc.get("recruit_id"):
            continue
        if str(doc.get("Home Region") or "").strip().upper() != letter:
            continue
        pos, rt = _best(doc.get("position_ratings"))
        if rt is None:
            continue
        lean = doc.get("Lean") if isinstance(doc.get("Lean"), Mapping) else {}
        lean_id = str(lean.get("1") or "") or None
        rows.append({
            "recruit_id": str(doc.get("recruit_id")),
            "name": str(doc.get("name") or "").strip() or None,
            "position": pos or (str(doc.get("position") or "").strip() or None),
            "rt": rt,
            "lean_team_id": lean_id,
            "lean_team_name": (str(names.get(lean_id) or "") or None) if lean_id else None,
            "lean_is_user": bool(tid) and lean_id == tid,
        })
    rows.sort(key=lambda row: (-row["rt"], str(row["name"] or "")))
    return {"region": letter, "rows": rows[:SECTION_ROWS]}


def last_season_snapshot(
    franchise_doc: Mapping[str, Any],
    user_team_id: Any,
    *,
    graduated_seniors: Optional[int],
    signed_class: Iterable[Any],
) -> dict[str, Any]:
    """What next season's preview needs and the rollover is about to wipe.

    The user's last meeting with each opponent (results are cleared), how many seniors
    leave (their documents are dropped) and who signed (the week-35 results are cleared).
    """
    tid = str(user_team_id or "")
    results = franchise_doc.get("results") if isinstance(franchise_doc.get("results"), Mapping) else {}
    meetings: dict[str, dict[str, Any]] = {}
    wins = losses = 0
    weeks = sorted(week for week in (_int(raw) for raw in results) if week is not None)
    for week in weeks:
        for result in results.get(str(week)) or []:
            if not isinstance(result, Mapping):
                continue
            away_id, home_id = str(result.get("away_id") or ""), str(result.get("home_id") or "")
            if tid not in {away_id, home_id}:
                continue
            away_score, home_score = _int(result.get("away_score")) or 0, _int(result.get("home_score")) or 0
            at_home = home_id == tid
            user_score, opp_score = (home_score, away_score) if at_home else (away_score, home_score)
            if user_score > opp_score:
                wins += 1
            elif user_score < opp_score:
                losses += 1
            # A later week overwrites an earlier one: the most recent meeting is kept.
            meetings[away_id if at_home else home_id] = {
                "week": week,
                "user_score": user_score,
                "opp_score": opp_score,
                "site": "home" if at_home else "away",
            }
    return {
        "season": _int(franchise_doc.get("current_season")) or 1,
        "wins": wins,
        "losses": losses,
        "meetings": meetings,
        "graduated_seniors": graduated_seniors,
        "signed_class": [
            {"player_id": str(player.get("player_id")), "name": str(player.get("name") or "")}
            for player in (signed_class or [])
            if isinstance(player, Mapping) and player.get("player_id") and not player.get("walk_on")
        ],
    }


def build_season_preview(ctx: Mapping[str, Any]) -> dict[str, Any]:
    """The week-1 Office payload. ``ctx`` is what ``_season_preview_context`` loaded."""
    franchise_doc = ctx.get("franchise_doc") or {}
    user_team_id = str(ctx.get("user_team_id") or "")
    season = _int(franchise_doc.get("current_season")) or 1
    rankings = ctx.get("rankings") or []
    user_conference = ctx.get("user_conference")
    last_season = franchise_doc.get(LAST_SEASON_FIELD)
    if not isinstance(last_season, Mapping) or _int(last_season.get("season")) != season - 1:
        last_season = None

    rows = roster_rows(ctx.get("roster_docs") or [])
    walk_ons = walk_on_rows(rows, season=season, pending_walk_ons=franchise_doc.get("pending_walk_on_welcome") or [])
    previous = last_season_line(ctx.get("trophies") or [], franchise_doc.get("_id"), season - 1) if season > 1 else None
    class_signed = []
    for trophy in ctx.get("trophies") or []:
        if (
            isinstance(trophy, Mapping)
            and trophy.get("kind") == "season_record"
            and str(trophy.get("franchise_id") or "") == str(franchise_doc.get("_id") or "")
            and _int(trophy.get("season")) == season - 1
        ):
            detail = trophy.get("detail") if isinstance(trophy.get("detail"), Mapping) else {}
            class_signed = list(detail.get("class_signed") or [])
    opener = ctx.get("next_game") if isinstance(ctx.get("next_game"), Mapping) else None
    projection = (franchise_doc.get("awards") or {}).get("all_american_projection")
    return {
        "season": season,
        "outlook": {
            "conference": user_conference,
            "picked": (rankings_block(rankings, user_team_id, user_conference) or {}).get("conference"),
            "last_season": previous,
        },
        "rankings": rankings_block(rankings, user_team_id, user_conference),
        "key_players": key_players(rows),
        "newcomers": newcomers_block(
            rows,
            season=season,
            last_season=last_season,
            class_signed=class_signed,
            walk_on_ids=[row["player_id"] for row in walk_ons],
        ),
        "all_americans": all_americans(projection, user_team_id),
        "opener": {
            "last_meeting": last_meeting(last_season, opener.get("opponent_team_id")) if opener else None,
        },
        "circle_these": circle_these(franchise_doc.get("schedule") or [], user_team_id, rankings),
        "preseason_rankings": preseason_rankings(rankings, user_team_id, user_conference),
        "walk_ons": walk_ons,
    }
