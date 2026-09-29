"""Career + season-review data the server computes for Home Base and the Trophy Case.

Everything here is read-side arithmetic on top of what already exists: the coach
doc (``users`` online, the save's ``local_coach`` doc on desktop), the trophy log,
and the live franchise docs. The client formats these numbers; it never derives
win %, GP, a ranking, the best players or a count.

Season Geek Points live on the coach as ``season_gp.<franchise_id>:<season>``,
incremented beside the per-game award in ``franchise_geek_points``.

A field whose source does not exist is **omitted**, never approximated.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Optional

from bson import ObjectId

from BackEnd.persistence import get_store
from BackEnd.utils.franchise_geek_points import SEASON_GP_FIELD, season_gp_key
from BackEnd.utils.leaders_snapshot import _roster_position
from BackEnd.utils.player_year import format_player_year_abbrev
from BackEnd.utils.t3_detail import stat_line

_store = get_store()
db = _store.db
franchise_players_data_collection = _store.franchise_players_data_collection
franchise_team_data_collection = _store.franchise_team_data_collection

logger = logging.getLogger(__name__)

BEST_PLAYERS = 3
TOP_SEASONS = 5

# The three All-American teams in the order a review lists them.
_ALL_AMERICAN_TEAM_ORDER = (
    ("first_team", "all_american_1"),
    ("second_team", "all_american_2"),
    ("third_team", "all_american_3"),
)
_BEST_PLAYER_PROJECTION = {
    "player_id": 1,
    "meta.first_name": 1,
    "meta.last_name": 1,
    "meta.position": 1,
    "meta.year": 1,
    "position_ratings": 1,
    "training_position": 1,
    "resolved_training_position": 1,
    "season": 1,
}


def _int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def read_season_gp(owner_user_id: Any) -> dict[str, int]:
    """The coach's ``season_gp`` map in one projected read. ``{}`` when absent."""
    from BackEnd.utils.local_coach import coach_field

    raw = coach_field(owner_user_id, SEASON_GP_FIELD)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        total = _int(value)
        if total is not None:
            out[str(key)] = total
    return out


def season_gp_for(season_gp: Mapping[str, int], franchise_id: Any, season: Any) -> Optional[int]:
    key = season_gp_key(franchise_id, season)
    return None if key is None else season_gp.get(key)


# --- season review snapshot ------------------------------------------------------------------


def final_national_rank(franchise_id: Any, team_id: Any) -> Optional[int]:
    """``franchise_team_data.natl_rank`` for the team — the rank the season ended on."""
    try:
        fid = franchise_id if isinstance(franchise_id, ObjectId) else ObjectId(str(franchise_id))
        tid = team_id if isinstance(team_id, ObjectId) else ObjectId(str(team_id))
    except Exception:
        return None
    ftd = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": tid},
        {"natl_rank": 1, "_id": 0},
    ) or {}
    rank = _int(ftd.get("natl_rank"))
    return rank if rank and rank > 0 else None


def region_seed(franchise_doc: Mapping[str, Any], team_id: Any) -> Optional[int]:
    """Seed on the team's region bracket, when one was stored.

    ``initialize_region_tournaments`` writes ``round1`` / ``final`` / ``current_round``
    and no ``seeds`` map, so this is absent today and the field is omitted rather
    than derived from the bracket graph.
    """
    tid = str(team_id or "")
    for region in (franchise_doc.get("region_tournaments") or {}).values():
        seeds = region.get("seeds") if isinstance(region, dict) else None
        if not isinstance(seeds, dict):
            continue
        for key, value in seeds.items():
            if str(key) == tid:
                return _int(value)
    return None


def _player_name(meta: Mapping[str, Any]) -> str:
    first = str(meta.get("first_name") or "").strip()
    last = str(meta.get("last_name") or "").strip()
    return " ".join(part for part in (first, last) if part)


def _per_game_stats(season: Mapping[str, Any]) -> dict[str, Any]:
    """``ppg``/``rpg``/``apg``, plus ``spg`` only when ``STL`` is on the season line."""
    line = stat_line(season)
    stats: dict[str, Any] = {
        "ppg": line["pts_per_game"],
        "rpg": line["reb_per_game"],
        "apg": line["ast_per_game"],
    }
    if "STL" in (season or {}):
        stats["spg"] = line["stl_per_game"]
    return {key: value for key, value in stats.items() if value is not None}


def _user_all_american_kind_by_player(awards: Mapping[str, Any], user_team_id: str) -> list[tuple[str, str]]:
    """``(player_id, kind)`` for user-team picks, in 1st → 2nd → 3rd team order."""
    teams = (awards or {}).get("all_american_teams") or {}
    if not isinstance(teams, dict):
        return []
    picks: list[tuple[str, str]] = []
    for team_key, kind in _ALL_AMERICAN_TEAM_ORDER:
        for pick in teams.get(team_key) or []:
            if not isinstance(pick, dict) or str(pick.get("team_id") or "") != user_team_id:
                continue
            pid = str(pick.get("player_id") or "")
            if pid:
                picks.append((pid, kind))
    return picks


def _roster_player_ids(franchise_id: Any, team_id: Any) -> list[str]:
    try:
        fid = franchise_id if isinstance(franchise_id, ObjectId) else ObjectId(str(franchise_id))
        tid = team_id if isinstance(team_id, ObjectId) else ObjectId(str(team_id))
    except Exception:
        return []
    ftd = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": tid},
        {"players": 1, "_id": 0},
    ) or {}
    return [str(pid) for pid in (ftd.get("players") or []) if pid]


def best_players(
    franchise_doc: Mapping[str, Any],
    team_id: Any,
    awards: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """The three the review shows: user-team All-Americans first, then by PPG.

    All-Americans come in team order (1st, then 2nd, then 3rd). The rest of the
    roster fills the remaining slots by points per game; equal PPG keeps roster
    order, so the list is stable across reads.
    """
    fid = franchise_doc.get("_id")
    roster = _roster_player_ids(fid, team_id)
    if not roster:
        return []
    by_id: dict[str, Mapping[str, Any]] = {}
    for doc in franchise_players_data_collection.find(
        {"franchise_id": str(fid), "player_id": {"$in": roster}},
        _BEST_PLAYER_PROJECTION,
    ):
        by_id[str(doc.get("player_id") or "")] = doc

    all_americans = _user_all_american_kind_by_player(awards or {}, str(team_id or ""))
    aa_kind = dict(all_americans)
    chosen = [pid for pid, _kind in all_americans if pid in by_id][:BEST_PLAYERS]
    if len(chosen) < BEST_PLAYERS:
        rest = [pid for pid in roster if pid in by_id and pid not in chosen]
        rest.sort(key=lambda pid: -(_int((by_id[pid].get("season") or {}).get("PTS")) or 0))
        chosen += rest[: BEST_PLAYERS - len(chosen)]

    rows: list[dict[str, Any]] = []
    for pid in chosen:
        doc = by_id[pid]
        meta = doc.get("meta") if isinstance(doc.get("meta"), dict) else {}
        season = doc.get("season") if isinstance(doc.get("season"), dict) else {}
        row: dict[str, Any] = {
            "player_id": pid,
            "name": _player_name(meta),
            "position": _roster_position(
                meta.get("position"),
                doc.get("position_ratings"),
                doc.get("training_position"),
                doc.get("resolved_training_position"),
                on_user_team=True,
            ),
            "class_year": format_player_year_abbrev(meta.get("year")),
            "stats": _per_game_stats(season),
        }
        if pid in aa_kind:
            row["all_american"] = aa_kind[pid]
        rows.append(row)
    return rows


def class_signed(franchise_doc: Mapping[str, Any], team_id: Any) -> list[dict[str, Any]]:
    """The user team's signed recruits from ``week_35_recruiting_results``.

    Walk-ons are not a signing class. Each field is copied straight off the stored
    signing entry and omitted when that entry does not carry it.
    """
    tid = str(team_id or "")
    signed = (franchise_doc.get("week_35_recruiting_results") or {}).get("signed_players") or []
    rows: list[dict[str, Any]] = []
    for player in signed:
        if not isinstance(player, dict) or player.get("walk_on"):
            continue
        if str(player.get("team_id") or "") != tid:
            continue
        row: dict[str, Any] = {"name": str(player.get("name") or "")}
        for field, source in (
            ("position", "pos"),
            ("home_region", "home_region"),
            ("rt_now", "rt"),
            ("rt_potential", "potential_rt_ratcheted"),
        ):
            value = player.get(source)
            if value is None or value == "" or value == "--":
                continue
            row[field] = value
        rows.append(row)
    return rows


def season_review_snapshot(
    franchise_doc: Mapping[str, Any],
    team_id: Any,
    *,
    season_gp: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """The review fields, read off the franchise before the season transition wipes it."""
    fid = franchise_doc.get("_id")
    season = franchise_doc.get("current_season", 1)
    out: dict[str, Any] = {}
    rank = final_national_rank(fid, team_id)
    if rank is not None:
        out["national_rank"] = rank
    seed = region_seed(franchise_doc, team_id)
    if seed is not None:
        out["region_seed"] = seed
    buckets = season_gp if season_gp is not None else read_season_gp(franchise_doc.get("user_id"))
    gp = season_gp_for(buckets, fid, season)
    if gp is not None:
        out["season_gp"] = gp
    players = best_players(franchise_doc, team_id, franchise_doc.get("awards") or {})
    if players:
        out["best_players"] = players
    recruits = class_signed(franchise_doc, team_id)
    if recruits:
        out["class_signed"] = recruits
    return out


# --- coach career ----------------------------------------------------------------------------

_FINISH_LABELS = {
    "national_final": "National final",
    "national_semis": "National semifinal",
    "national_quarters": "National quarterfinal",
    "region_final": "Region final",
    "region_semis": "Region semifinal",
    "conference_final": "Conference final",
    "conference_semis": "Conference semifinal",
    "conference_quarters": "Conference quarterfinal",
    "missed": "Missed the bracket",
}
_TITLE_FINISH_LABELS = {
    "national": "National champions",
    "region": "Region champions",
    "conf_t": "Conference champions",
    "conf_rs": "Conference regular-season #1",
}
_TITLE_FINISH_ORDER = ("national", "region", "conf_t", "conf_rs")


def finish_label(detail: Mapping[str, Any] | None, title_kinds: Iterable[str]) -> Optional[str]:
    """A title outranks a round; ``None`` when neither source exists."""
    titles = set(title_kinds or ())
    for kind in _TITLE_FINISH_ORDER:
        if kind in titles:
            return _TITLE_FINISH_LABELS[kind]
    furthest = (detail or {}).get("furthest_round")
    return _FINISH_LABELS.get(str(furthest or ""))


def _team_slug(team_name: Any) -> Optional[str]:
    from BackEnd.utils.team_slug import path_slug_for_display_name

    slug = path_slug_for_display_name(str(team_name or "") or None)
    return None if slug == "general" else slug


def _win_rate(wins: int, losses: int) -> float:
    total = wins + losses
    return (wins / total) if total else 0.0


def win_pct_display(record: Mapping[str, Any] | None) -> Optional[str]:
    """Career win % as the UI prints it: ``.770``, ``1.000``. ``None`` before any game.

    ``record.win_rate`` stays the whole-percent integer every other caller reads.
    This is the three-decimal string the career strip shows, formatted here because
    the client does not do arithmetic.
    """
    record = record or {}
    wins = _int(record.get("wins")) or 0
    losses = _int(record.get("losses")) or 0
    if wins + losses <= 0:
        return None
    text = f"{_win_rate(wins, losses):.3f}"
    return text[1:] if text.startswith("0.") else text


def _season_row(
    *,
    franchise_id: str,
    team_name: str,
    season: int,
    wins: int,
    losses: int,
    finish: Optional[str],
    gp: Optional[int],
    in_progress: bool,
    week: Optional[int],
) -> dict[str, Any]:
    return {
        "franchise_id": franchise_id,
        "team_name": team_name,
        "team_slug": _team_slug(team_name),
        "season": season,
        "wins": wins,
        "losses": losses,
        "finish": finish,
        "season_gp": gp,
        "in_progress": in_progress,
        "week": week,
    }


def _completed_season_rows(trophies: Iterable[Mapping[str, Any]], season_gp: Mapping[str, int]) -> list[dict[str, Any]]:
    from BackEnd.utils.trophy_log import SEASON_RECORD_KIND, TITLE_TROPHY_KINDS

    titles_by_season: dict[tuple[str, int], set[str]] = {}
    for trophy in trophies:
        kind = str(trophy.get("kind") or "")
        if kind not in TITLE_TROPHY_KINDS:
            continue
        key = (str(trophy.get("franchise_id") or ""), _int(trophy.get("season")) or 0)
        titles_by_season.setdefault(key, set()).add(kind)

    rows: list[dict[str, Any]] = []
    for trophy in trophies:
        if str(trophy.get("kind") or "") != SEASON_RECORD_KIND:
            continue
        fid = str(trophy.get("franchise_id") or "")
        season = _int(trophy.get("season")) or 0
        detail = trophy.get("detail") if isinstance(trophy.get("detail"), dict) else {}
        gp = _int(detail.get("season_gp"))
        if gp is None:
            gp = season_gp_for(season_gp, fid, season)
        rows.append(
            _season_row(
                franchise_id=fid,
                team_name=str(trophy.get("team_name") or ""),
                season=season,
                wins=_int(detail.get("wins")) or 0,
                losses=_int(detail.get("losses")) or 0,
                finish=finish_label(detail, titles_by_season.get((fid, season), set())),
                gp=gp,
                in_progress=False,
                week=None,
            )
        )
    return rows


def _in_progress_rows(franchises: Iterable[Mapping[str, Any]], season_gp: Mapping[str, int]) -> list[dict[str, Any]]:
    from BackEnd.utils.franchise_standings import calculate_franchise_standings
    from BackEnd.utils.franchise_team_display import resolve_team_display

    rows: list[dict[str, Any]] = []
    for doc in franchises:
        tid = str(doc.get("user_team_object_id") or "")
        if not tid:
            continue
        fid = str(doc.get("_id"))
        season = _int(doc.get("current_season")) or 1
        standings = calculate_franchise_standings(doc.get("results") or {}, {tid: {}}).get(tid) or {}
        display = {}
        try:
            display = resolve_team_display(doc, tid) or {}
        except Exception:
            logger.exception("[CAREER] display lookup failed franchise_id=%s", fid)
        name = display.get("name") or doc.get("user_team_id") or ""
        if display.get("core_missing"):
            name = doc.get("user_team_id") or name
        rows.append(
            _season_row(
                franchise_id=fid,
                team_name=str(name),
                season=season,
                wins=_int(standings.get("W")) or 0,
                losses=_int(standings.get("L")) or 0,
                finish=None,
                gp=season_gp_for(season_gp, fid, season),
                in_progress=True,
                week=_int(doc.get("week")) or 1,
            )
        )
    return rows


def top_seasons(
    trophies: Iterable[Mapping[str, Any]],
    franchises: Iterable[Mapping[str, Any]],
    season_gp: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Up to five seasons by season GP, ties by win %. In-progress seasons rank too."""
    trophies = list(trophies)
    completed = _completed_season_rows(trophies, season_gp)
    live = _in_progress_rows(franchises, season_gp)
    done = {(row["franchise_id"], row["season"]) for row in completed}
    rows = completed + [row for row in live if (row["franchise_id"], row["season"]) not in done]
    rows.sort(
        key=lambda row: (
            -(row["season_gp"] or 0),
            -_win_rate(row["wins"], row["losses"]),
        )
    )
    return rows[:TOP_SEASONS]


def coach_career_extras(
    coach_doc: Mapping[str, Any] | None,
    franchises: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Career totals and Top Seasons for ``GET /franchise/coach-career``."""
    from BackEnd.utils.trophy_log import SEASON_RECORD_KIND, TROPHIES_FIELD

    coach_doc = coach_doc or {}
    franchises = list(franchises)
    raw = coach_doc.get(TROPHIES_FIELD)
    trophies = [t for t in (raw or []) if isinstance(t, dict)]
    season_gp = coach_doc.get(SEASON_GP_FIELD)
    season_gp = {
        str(k): (_int(v) or 0) for k, v in season_gp.items()
    } if isinstance(season_gp, dict) else {}
    programs = {str(t.get("franchise_id") or "") for t in trophies if t.get("franchise_id")}
    programs |= {str(doc.get("_id")) for doc in franchises if doc.get("_id")}
    return {
        "win_pct_display": win_pct_display(coach_doc.get("record")),
        "geek_points": _int(coach_doc.get("geek_points")) or 0,
        "seasons_completed": sum(
            1 for t in trophies if str(t.get("kind") or "") == SEASON_RECORD_KIND
        ),
        "programs": len(programs),
        "top_seasons": top_seasons(trophies, franchises, season_gp),
    }
