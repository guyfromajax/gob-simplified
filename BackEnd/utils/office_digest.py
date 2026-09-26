"""Office digest for GET /franchise/command-center/data.

The week-advance snapshot is the only new stored data. It is merged into the
existing franchise week-persist ``$set`` (see ``capture_office_week_snapshot``).
Everything else in ``office_digest`` is derived on read from fields the game
already stores. Missing handoff values are JSON null — they are not invented.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from bson import ObjectId

from BackEnd.utils.franchise_standings import (
    calculate_franchise_standings,
    standings_display_sort_key,
)
from BackEnd.utils.rt_display import rt_letter_grade

# Same field the rank/prestige writer uses. Duplicated as a string so this
# module does not import franchise_routes.
RANK_PRESTIGE_LAST_APPLIED_WEEK_FIELD = "rank_prestige_last_applied_week"
OFFICE_WEEK_SNAPSHOTS_FIELD = "office_week_snapshots"

# Team measures that move week to week. Chemistry is reported on its own row.
TEAM_MEASURE_KEYS = (
    "offensive_efficiency",
    "defensive_efficiency",
    "fb_efficiency",
    "pt_efficiency",
    "fb_opp_modifier",
    "pt_opp_modifier",
    "discipline",
    "fight",
    "rebound_modifier",
    "shot_threshold",
    "momentum_score",
)

CHEMISTRY_MAX = 25

# HOME_EMOJI_BUCKETS in franchise-command-center.js: 0–19, 20–39, 40–59, 60–79, 80+.
ATTITUDE_BUCKETS = (
    ("em_0_19", 0, 19),
    ("em_20_39", 20, 39),
    ("em_40_59", 40, 59),
    ("em_60_79", 60, 79),
    ("em_80_plus", 80, None),
)

# Modes where the Advance button is that task instead of Play Next Game.
GATING_MODES = frozenset({
    "finish-cpu-sims",
    "cut-players",
    "recruit-invites",
    "week35-run",
    "week35-recruiting",
    "view-recruiting-results",
    "training",
})

MODE_ROUTES = {
    "finish-cpu-sims": "/franchise/complete-week/phase-b",
    "cut-players": "/cut-players.html",
    "recruit-invites": "/recruiting.html",
    "week35-run": "/recruiting.html",
    "week35-recruiting": "/recruiting.html",
    "view-recruiting-results": "/recruiting.html",
    "new-season": "/franchise/finish-season",
    "sim-rest-tournament": "/franchise/sim-rest-of-tournament",
    "training": "/training.html",
    "play": "/set-lineup.html",
}

# Calendar labels already used by the Advance ladder (gobAdvance.js), without the Play/Sim prefix.
ROUND_NAME_BY_WEEK = {
    27: "Conference Tourney First Round",
    28: "Conference Tourney Semifinals",
    29: "Conference Tourney Championship",
    30: "Region Tourney First Round",
    31: "Region Tourney Championship",
    32: "National Tourney First Round",
    33: "National Tourney Semifinals",
    34: "National Championship",
}

LAST_GAME_PROJECTION = {
    "_id": 1,
    "week": 1,
    "quarter": 1,
    "is_final": 1,
    "game_id": 1,
    "team1_id": 1,
    "team2_id": 1,
    "home_team_id": 1,
    "away_team_id": 1,
    "team1_score": 1,
    "team2_score": 1,
    "score": 1,
    "players": 1,
    "box_score": 1,
    "home_team": 1,
    "away_team": 1,
    "team_totals": 1,
    "teams.box_score": 1,
    "teams.name": 1,
    "teams.display_name": 1,
    "teams.team_id": 1,
    "teams.score": 1,
    "teams.totals": 1,
}

_UP_KINDS = frozenset({"gained_you", "moved_up"})
_DOWN_KINDS = frozenset({"dropped_you", "moved_down", "rival_took_your_top"})


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def id_variants(value: Any) -> list[Any]:
    """String and ObjectId forms. Game docs store team1_id as ObjectId; results store strings."""
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    out: list[Any] = [text]
    try:
        oid = ObjectId(text)
    except Exception:
        return out
    out.append(oid)
    return out


def last_game_match_query(franchise_id: Any, week: int, away_id: Any, home_id: Any) -> dict[str, Any]:
    """One games query for the user's completed matchup. Both id types, both slot orders."""
    ors: list[dict[str, Any]] = []
    for away in id_variants(away_id):
        for home in id_variants(home_id):
            ors.append({"team1_id": away, "team2_id": home})
            ors.append({"team1_id": home, "team2_id": away})
    return {
        "week": int(week),
        "franchise_id": str(franchise_id),
        "$or": ors or [{"_id": None}],
    }


def measure_values(team_attributes: Mapping[str, Any] | None) -> dict[str, float]:
    attrs = team_attributes or {}
    out: dict[str, float] = {}
    for key in TEAM_MEASURE_KEYS:
        number = _num(attrs.get(key))
        if number is not None:
            out[key] = number
    return out


def attitude_counts(em_values: Iterable[Any]) -> dict[str, Any]:
    counts = {bucket_id: 0 for bucket_id, _lo, _hi in ATTITUDE_BUCKETS}
    counted = 0
    for raw in em_values:
        number = _num(raw)
        if number is None:
            continue
        counted += 1
        for bucket_id, lo, hi in ATTITUDE_BUCKETS:
            if number >= lo and (hi is None or number <= hi):
                counts[bucket_id] += 1
                break
    return {
        "player_count": counted,
        "buckets": [
            {"id": bucket_id, "min": lo, "max": hi, "count": counts[bucket_id]}
            for bucket_id, lo, hi in ATTITUDE_BUCKETS
        ],
    }


def conference_position(
    standings: Mapping[str, Mapping[str, Any]],
    conference_by_team: Mapping[str, Any],
    user_team_id: str,
    user_conference: Any,
) -> Optional[int]:
    """1-based place in the user's conference, using ``standings_display_sort_key``."""
    if user_conference is None or not user_team_id:
        return None
    rows: list[dict[str, Any]] = []
    for team_id, conference in conference_by_team.items():
        if conference != user_conference:
            continue
        tid = str(team_id)
        row = dict(standings.get(tid) or {})
        row["team_id"] = tid
        rows.append(row)
    rows.sort(key=standings_display_sort_key)
    for index, row in enumerate(rows, start=1):
        if row["team_id"] == str(user_team_id):
            return index
    return None


def _season_snapshots(franchise_doc: Mapping[str, Any]) -> dict[str, Any]:
    root = franchise_doc.get(OFFICE_WEEK_SNAPSHOTS_FIELD)
    if not isinstance(root, dict):
        return {}
    season = str(_as_int(franchise_doc.get("current_season"), 1) or 1)
    season_map = root.get(season)
    return dict(season_map) if isinstance(season_map, dict) else {}


def _snapshot_key_present(franchise_doc: Mapping[str, Any], completed_week: int) -> bool:
    return str(int(completed_week)) in _season_snapshots(franchise_doc)


def prior_measure_baseline(franchise_doc: Mapping[str, Any], completed_week: int) -> Optional[dict[str, float]]:
    """Team measures stored on the previous week of this season, if a snapshot exists."""
    snaps = _season_snapshots(franchise_doc)
    earlier = sorted(int(key) for key in snaps if str(key).isdigit() and int(key) < int(completed_week))
    if not earlier:
        return None
    payload = snaps.get(str(earlier[-1])) or {}
    measures = payload.get("team_measures") if isinstance(payload, dict) else None
    if not isinstance(measures, dict):
        return None
    return {str(key): value for key, value in measures.items() if _num(value) is not None}


def office_snapshot_payload(
    *,
    completed_week: int,
    national_rank_before: Optional[int],
    conference_position_before: Optional[int],
    team_measures: Mapping[str, Any],
    team_measures_before: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "week": int(completed_week),
        "national_rank_before": national_rank_before,
        "conference_position_before": conference_position_before,
        "team_measures": dict(team_measures),
    }
    if team_measures_before:
        payload["team_measures_before"] = dict(team_measures_before)
    return payload


def merge_office_snapshot(
    franchise_doc: Mapping[str, Any],
    completed_week: int,
    payload: Mapping[str, Any],
) -> Optional[dict[str, Any]]:
    """Full ``office_week_snapshots`` map to ``$set``, or None when this week is already stored.

    A retry after rank/prestige has already been applied must not write a snapshot
    that is missing: the pre-update rank is no longer recoverable from FTD.
    """
    if _snapshot_key_present(franchise_doc, completed_week):
        return None
    last_applied = _as_int(franchise_doc.get(RANK_PRESTIGE_LAST_APPLIED_WEEK_FIELD), 0) or 0
    if last_applied >= int(completed_week):
        return None

    season = str(_as_int(franchise_doc.get("current_season"), 1) or 1)
    root = franchise_doc.get(OFFICE_WEEK_SNAPSHOTS_FIELD)
    new_root: dict[str, Any] = {}
    if isinstance(root, dict):
        for key, value in root.items():
            new_root[str(key)] = dict(value) if isinstance(value, dict) else value
    season_map = dict(new_root.get(season) or {})
    season_map[str(int(completed_week))] = dict(payload)
    new_root[season] = season_map
    return new_root


def capture_office_week_snapshot(
    franchise_doc: Mapping[str, Any],
    user_team_id: Any,
    completed_week: int,
    *,
    ftd_collection: Any,
    teams_collection: Any,
) -> Optional[dict[str, Any]]:
    """Read pre-update rank, conference place, and team measures. Returns the map to ``$set``.

    Call this before ``_apply_regular_season_rank_prestige_updates``. No write of its own.
    """
    if _snapshot_key_present(franchise_doc, completed_week):
        return None
    last_applied = _as_int(franchise_doc.get(RANK_PRESTIGE_LAST_APPLIED_WEEK_FIELD), 0) or 0
    if last_applied >= int(completed_week):
        return None
    if not user_team_id or franchise_doc.get("_id") is None:
        return None

    franchise_id = franchise_doc["_id"]
    ftd_docs = list(ftd_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "natl_rank": 1, "team_attributes": 1},
    ))
    rank_by_team: dict[str, int] = {}
    user_measures: dict[str, float] = {}
    team_oids: list[ObjectId] = []
    user_key = str(user_team_id)
    for doc in ftd_docs:
        team_id = doc.get("team_id")
        if team_id is None:
            continue
        tid = str(team_id)
        rank_by_team[tid] = _as_int(doc.get("natl_rank"), 999) or 999
        if isinstance(team_id, ObjectId):
            team_oids.append(team_id)
        else:
            for variant in id_variants(team_id):
                if isinstance(variant, ObjectId):
                    team_oids.append(variant)
        if tid == user_key:
            user_measures = measure_values(doc.get("team_attributes") or {})

    conference_by_team: dict[str, Any] = {}
    if team_oids and teams_collection is not None:
        for team in teams_collection.find({"_id": {"$in": team_oids}}, {"conference": 1}):
            conference_by_team[str(team["_id"])] = team.get("conference")

    results = dict(franchise_doc.get("results") or {})
    before_results = {key: value for key, value in results.items() if str(key) != str(int(completed_week))}
    standings = calculate_franchise_standings(before_results, {tid: {} for tid in rank_by_team})
    position = conference_position(
        standings,
        conference_by_team,
        user_key,
        conference_by_team.get(user_key),
    )
    payload = office_snapshot_payload(
        completed_week=int(completed_week),
        national_rank_before=rank_by_team.get(user_key),
        conference_position_before=position,
        team_measures=user_measures,
        team_measures_before=prior_measure_baseline(franchise_doc, int(completed_week)),
    )
    return merge_office_snapshot(franchise_doc, int(completed_week), payload)


def latest_snapshot(franchise_doc: Mapping[str, Any], current_week: int) -> Optional[dict[str, Any]]:
    snaps = _season_snapshots(franchise_doc)
    earlier = sorted(int(key) for key in snaps if str(key).isdigit() and int(key) < int(current_week))
    if not earlier:
        return None
    payload = snaps.get(str(earlier[-1]))
    return dict(payload) if isinstance(payload, dict) else None


def _rank_delta(now: Optional[int], prev: Optional[int]) -> Optional[int]:
    """Positive means the team climbed (a smaller rank number)."""
    if now is None or prev is None:
        return None
    return int(prev) - int(now)


def _user_game_outcomes(results: Mapping[str, Any], user_team_id: str) -> list[str]:
    """Newest week first. One outcome per week the user played. 'T' for a tie."""
    outcomes: list[str] = []
    weeks: list[int] = []
    for raw in results:
        week = _as_int(raw)
        if week is not None:
            weeks.append(week)
    for week in sorted(weeks, reverse=True):
        for result in list(results.get(str(week)) or []):
            if not isinstance(result, dict):
                continue
            away_id = str(result.get("away_id") or "")
            home_id = str(result.get("home_id") or "")
            if user_team_id not in {away_id, home_id}:
                continue
            away_score = _as_int(result.get("away_score"), 0) or 0
            home_score = _as_int(result.get("home_score"), 0) or 0
            user_score = home_score if user_team_id == home_id else away_score
            opp_score = away_score if user_team_id == home_id else home_score
            if user_score > opp_score:
                outcomes.append("W")
            elif user_score < opp_score:
                outcomes.append("L")
            else:
                outcomes.append("T")
            break
    return outcomes


def record_and_streak(results: Mapping[str, Any], user_team_id: str, standings: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, int], Optional[str]]:
    row = standings.get(str(user_team_id)) or {}
    wins = _as_int(row.get("W"))
    losses = _as_int(row.get("L"))
    if wins is None or losses is None:
        wins = 0
        losses = 0
        for outcome in _user_game_outcomes(results, user_team_id):
            if outcome == "W":
                wins += 1
            elif outcome == "L":
                losses += 1
    streak: Optional[str] = None
    outcomes = _user_game_outcomes(results, user_team_id)
    if outcomes and outcomes[0] in {"W", "L"}:
        kind = outcomes[0]
        count = 0
        for outcome in outcomes:
            if outcome != kind:
                break
            count += 1
        streak = f"{kind}{count}"
    return {"wins": int(wins), "losses": int(losses)}, streak


def attribute_changes_from_report(report: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Display-scale from/to rows. Legacy name-keyed direction maps have no from/to and are skipped."""
    if not isinstance(report, dict):
        return []
    movements = report.get("player_attribute_display_movements")
    if not isinstance(movements, dict):
        return []
    rows: list[dict[str, Any]] = []
    for key, entry in movements.items():
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        player_id = str(key)
        # Legacy reports are keyed by display name and store -1/1, not from/to.
        if not any(isinstance(value, dict) and "from" in value and "to" in value for value in entry.values()):
            continue
        for attr, cell in entry.items():
            if attr == "name" or not isinstance(cell, dict):
                continue
            if "from" not in cell or "to" not in cell:
                continue
            rows.append({
                "player_id": player_id,
                "name": name if isinstance(name, str) else None,
                "attribute": str(attr),
                "from": cell.get("from"),
                "to": cell.get("to"),
            })
    rows.sort(key=lambda row: (str(row.get("name") or ""), str(row.get("player_id")), str(row.get("attribute"))))
    return rows


def moved_most(snapshot: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    after = snapshot.get("team_measures")
    before = snapshot.get("team_measures_before")
    if not isinstance(after, dict) or not isinstance(before, dict):
        return []
    ranked: list[tuple[float, str, float, float]] = []
    for key, raw_after in after.items():
        if key not in before:
            continue
        now = _num(raw_after)
        prev = _num(before.get(key))
        if now is None or prev is None:
            continue
        delta = now - prev
        if delta == 0:
            continue
        ranked.append((abs(delta), str(key), now, delta))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"measure": key, "value": value, "delta": delta}
        for _abs, key, value, delta in ranked[:2]
    ]


def resolve_advance_mode(flags: Mapping[str, Any]) -> str:
    """Same priority as gobAdvance.updatePlayButton. One mode, no new rules."""
    week = _as_int(flags.get("week"), 1) or 1
    if flags.get("cpu_phase_b_required"):
        return "finish-cpu-sims"
    if flags.get("cut_required"):
        return "cut-players"
    saved_week = _as_int(flags.get("board_saved_week"), 0) or 0
    if 20 <= week <= 26 and saved_week != week:
        return "recruit-invites"
    if week == 35 and flags.get("week_35_orders_submitted"):
        return "week35-run"
    if week == 35:
        return "week35-recruiting"
    if week == 36 and not flags.get("week_36_results_seen"):
        return "view-recruiting-results"
    if week == 36:
        return "new-season"
    if flags.get("tournament_complete") and week >= 37:
        return "new-season"
    postseason = bool(flags.get("training_disabled_for_postseason") or week >= 27)
    eliminated = flags.get("user_eliminated")
    if eliminated is None:
        eliminated = False
    if flags.get("offer_sim_rest") and flags.get("eos_tournament_active"):
        return "sim-rest-tournament"
    if (
        postseason
        and not eliminated
        and flags.get("region_qualified")
        and 27 <= week <= 29
        and not flags.get("has_eos_game_this_week")
    ):
        return "sim-rest-tournament"
    if postseason and not eliminated and week <= 34:
        return "play"
    if flags.get("training_disabled_for_eos") or eliminated:
        return "new-season"
    if not flags.get("training_completed"):
        return "training"
    return "play"


def _todo(todo_id: str, mode_key: str, *, required: bool, done: bool, current_mode: str) -> dict[str, Any]:
    return {
        "id": todo_id,
        "label_key": todo_id,
        "required": required,
        "done": bool(done),
        "gates_advance": (not done) and mode_key in GATING_MODES,
        "is_advance_action": mode_key == current_mode,
        "route": MODE_ROUTES[mode_key],
    }


def build_todos(flags: Mapping[str, Any]) -> list[dict[str, Any]]:
    mode = resolve_advance_mode(flags)
    week = _as_int(flags.get("week"), 1) or 1
    items: list[dict[str, Any]] = []

    if mode == "finish-cpu-sims":
        return [_todo("finish_cpu_sims", "finish-cpu-sims", required=True, done=False, current_mode=mode)]

    if flags.get("cut_required"):
        items.append(_todo("assign_practice_squad", "cut-players", required=True, done=False, current_mode=mode))

    if 20 <= week <= 26:
        saved = (_as_int(flags.get("board_saved_week"), 0) or 0) == week
        items.append(_todo("review_recruit_invites", "recruit-invites", required=True, done=saved, current_mode=mode))

    if week == 35:
        if flags.get("week_35_orders_submitted"):
            items.append(_todo("run_recruiting_day", "week35-run", required=True, done=False, current_mode=mode))
        else:
            items.append(_todo("run_signing_day", "week35-recruiting", required=True, done=False, current_mode=mode))

    if week == 36:
        seen = bool(flags.get("week_36_results_seen"))
        items.append(_todo("view_recruiting_results", "view-recruiting-results", required=True, done=seen, current_mode=mode))
        if seen:
            items.append(_todo("go_to_next_season", "new-season", required=True, done=False, current_mode=mode))

    postseason = bool(flags.get("training_disabled_for_postseason") or week >= 27)
    eliminated = bool(flags.get("user_eliminated") or flags.get("training_disabled_for_eos"))
    if week >= 37 or (flags.get("tournament_complete") and week >= 37):
        if not any(item["id"] == "go_to_next_season" for item in items):
            items.append(_todo("go_to_next_season", "new-season", required=True, done=False, current_mode=mode))
    elif 27 <= week <= 34:
        if mode == "sim-rest-tournament":
            items.append(_todo("sim_next_round", "sim-rest-tournament", required=True, done=False, current_mode=mode))
        elif mode == "new-season":
            items.append(_todo("go_to_next_season", "new-season", required=True, done=False, current_mode=mode))
        elif not eliminated:
            items.append(_todo("play_next_game", "play", required=True, done=False, current_mode=mode))
    elif week < 35 and not eliminated:
        training_done = bool(flags.get("training_completed"))
        if flags.get("cpu_training_resume") and not training_done:
            items.append(_todo("resume_training", "training", required=True, done=False, current_mode=mode))
        elif (flags.get("session_type") or "in-season") == "preseason" and not training_done:
            items.append(_todo("run_training_camp", "training", required=True, done=False, current_mode=mode))
        else:
            items.append(_todo("run_training", "training", required=True, done=training_done, current_mode=mode))
        items.append(_todo("play_next_game", "play", required=True, done=False, current_mode=mode))
    elif mode == "new-season" and not any(item["id"] == "go_to_next_season" for item in items):
        items.append(_todo("go_to_next_season", "new-season", required=True, done=False, current_mode=mode))

    if mode and not any(item["is_advance_action"] for item in items):
        # The ladder selected a mode this list did not emit. Surface it so Advance still matches.
        fallback_id = {
            "play": "play_next_game",
            "training": "run_training",
            "sim-rest-tournament": "sim_next_round",
            "new-season": "go_to_next_season",
        }.get(mode)
        if fallback_id and mode in MODE_ROUTES:
            items.append(_todo(fallback_id, mode, required=True, done=False, current_mode=mode))
    return items


def office_state(
    *,
    week: int,
    eos_tournament_active: bool,
    user_won: Optional[bool],
) -> str:
    if week == 35:
        return "signing_day"
    if week <= 1:
        return "first_week"
    if eos_tournament_active and 27 <= week <= 34:
        return "tournament"
    if user_won is True:
        return "win"
    if user_won is False:
        return "loss"
    return "regular"


def headline_for_game(stories: Any, game_id: Optional[str]) -> Optional[str]:
    """A headline only when a stored story is tied to this game. Weekly reports are not game headlines."""
    if not game_id:
        return None
    target = str(game_id)
    for story in stories or []:
        if not isinstance(story, dict):
            continue
        if str(story.get("game_id") or "") == target and story.get("headline"):
            return str(story.get("headline"))
    return None


def _direction(kind: str) -> Optional[str]:
    if kind in _UP_KINDS:
        return "up"
    if kind in _DOWN_KINDS:
        return "down"
    return None


def _best_position(position_ratings: Any) -> Optional[str]:
    best_pos = None
    best_rating = None
    if not isinstance(position_ratings, dict):
        return None
    for pos, rating in position_ratings.items():
        number = _num(rating)
        if number is None:
            continue
        if best_rating is None or number > best_rating:
            best_pos = str(pos)
            best_rating = number
    return best_pos


def _best_rt_letter(position_ratings: Any) -> Optional[str]:
    best = None
    if not isinstance(position_ratings, dict):
        return None
    for rating in position_ratings.values():
        number = _num(rating)
        if number is None:
            continue
        if best is None or number > best:
            best = number
    if best is None:
        return None
    letter = rt_letter_grade(best)
    return None if letter == "--" else letter


def recruiting_wire_digest(
    wire: Mapping[str, Any] | None,
    recruit_lookup: Mapping[str, Mapping[str, Any]] | None,
    *,
    week: int,
) -> dict[str, Any]:
    wire = wire or {}
    lookup = recruit_lookup or {}
    counts = wire.get("counts") if isinstance(wire.get("counts"), dict) else {}
    moved = _as_int(counts.get("moved"), 0) or 0
    dropped = _as_int(counts.get("dropped"), 0) or 0
    if moved or dropped:
        status = f"{moved} moved, {dropped} dropped"
    else:
        status = "No recruiting movement"
    events: list[dict[str, Any]] = []
    for event in wire.get("events") or []:
        if not isinstance(event, dict):
            continue
        recruit_id = str(event.get("recruit_id") or "") or None
        recruit = lookup.get(recruit_id or "") or {}
        kind = str(event.get("kind") or "")
        events.append({
            "recruit_id": recruit_id,
            "recruit": recruit.get("name") or event.get("recruit") or None,
            "position": recruit.get("position"),
            "stars": None,
            "filmed_grade": None,
            "event_type": kind or None,
            "event_text": event.get("line") or None,
            "list_position": event.get("rank"),
            "direction": _direction(kind),
        })
    saved = _as_int(wire.get("board_saved_week"), 0) or 0
    pending = 0
    if 20 <= week <= 26 and saved != week:
        pending += 1
    if week == 35:
        pending += 1
    if week == 36 and not wire.get("week_36_results_seen"):
        pending += 1
    return {
        "status": status,
        "events": events,
        "pending_count": pending,
        "urgent": pending > 0,
        "unseen_count": _as_int(wire.get("unseen_count"), 0) or 0,
    }


def signing_day_digest(
    *,
    week: int,
    orders: Any,
    points_total: int,
    roster_spots: Optional[int],
    recruit_lookup: Mapping[str, Mapping[str, Any]],
    events: Any,
) -> Optional[dict[str, Any]]:
    if week != 35:
        return None
    entries: list[dict[str, Any]] = []
    if isinstance(orders, dict):
        for key in sorted(orders, key=lambda value: int(value) if str(value).isdigit() else 10**9):
            entry = orders.get(key)
            if not isinstance(entry, dict):
                continue
            recruit_id = str(entry.get("id") or "").strip()
            if not recruit_id:
                continue
            entries.append({
                "recruit_id": recruit_id,
                "points": _as_int(entry.get("points"), 0) or 0,
                "playing_time": bool(entry.get("playing_time")),
            })
    spent = sum(entry["points"] for entry in entries)
    direction_by_recruit: dict[str, str] = {}
    for event in events or []:
        if not isinstance(event, dict):
            continue
        rid = str(event.get("recruit_id") or "")
        direction = _direction(str(event.get("kind") or ""))
        if rid and direction and rid not in direction_by_recruit:
            direction_by_recruit[rid] = direction
    ranked_entries = sorted(entries, key=lambda entry: (-entry["points"], entry["recruit_id"]))
    if ranked_entries:
        chosen = [entry["recruit_id"] for entry in ranked_entries if entry["points"] > 0][:3]
    else:
        leaning = [
            ( _as_int(info.get("lean_rank"), 99) or 99, rid)
            for rid, info in recruit_lookup.items()
            if info.get("lean_rank") is not None
        ]
        leaning.sort()
        chosen = [rid for _rank, rid in leaning[:3]]
    targets = []
    for rid in chosen:
        info = recruit_lookup.get(rid) or {}
        targets.append({
            "recruit_id": rid,
            "name": info.get("name"),
            "position": info.get("position"),
            "stars": None,
            "rt": info.get("rt"),
            "lean_rank": info.get("lean_rank"),
            "direction": direction_by_recruit.get(rid),
        })
    return {
        "points_remaining": int(points_total) - spent if entries else None,
        "points_total": int(points_total),
        "promises_made": sum(1 for entry in entries if entry["playing_time"]) if entries else None,
        "open_roster_spots": roster_spots,
        "targets": targets,
    }


def _player_stat_line(raw: Mapping[str, Any]) -> dict[str, Any]:
    stats = raw.get("stats")
    if isinstance(stats, dict) and isinstance(stats.get("game"), dict):
        stats = stats["game"]
    elif not isinstance(stats, dict):
        stats = raw
    if not isinstance(stats, dict):
        stats = {}
    reb = stats.get("REB")
    if reb is None:
        oreb = _as_int(stats.get("OREB"), 0) or 0
        dreb = _as_int(stats.get("DREB"), 0) or 0
        reb = oreb + dreb
    line: dict[str, Any] = {
        "pts": _as_int(stats.get("PTS"), 0) or 0,
        "reb": _as_int(reb, 0) or 0,
        "ast": _as_int(stats.get("AST"), 0) or 0,
    }
    for src, dest in (("FGM", "fgm"), ("FGA", "fga"), ("3PTM", "fg3m"), ("3PTA", "fg3a"), ("MIN", "min")):
        if stats.get(src) is not None:
            line[dest] = stats.get(src)
    return line


def user_team_leader(game_doc: Mapping[str, Any] | None, *, user_is_home: bool) -> Optional[dict[str, Any]]:
    """Highest-PTS player on the user's side. Used after a loss, in place of POTG."""
    if not isinstance(game_doc, dict):
        return None
    side = "home" if user_is_home else "away"
    best: Optional[dict[str, Any]] = None
    best_pts = -1

    def consider(raw: Mapping[str, Any], team_side: Optional[str]) -> None:
        nonlocal best, best_pts
        if team_side != side:
            return
        line = _player_stat_line(raw)
        pts = int(line["pts"])
        if pts < best_pts:
            return
        name = str(raw.get("name") or "").strip() or None
        player_id = raw.get("playerId") or raw.get("player_id") or raw.get("_id")
        best_pts = pts
        best = {
            "player_id": str(player_id) if player_id is not None else None,
            "name": name,
            "stats": line,
        }

    players = game_doc.get("players")
    if isinstance(players, list):
        for player in players:
            if isinstance(player, dict):
                team = player.get("team")
                consider(player, team if team in {"home", "away"} else None)
    teams = game_doc.get("teams") if isinstance(game_doc.get("teams"), dict) else {}
    home_id = str(game_doc.get("home_team_id") or "")
    away_id = str(game_doc.get("away_team_id") or "")
    for team_key, team_row in teams.items():
        if not isinstance(team_row, dict):
            continue
        key = str(team_key)
        row_team_id = str(team_row.get("team_id") or "")
        if key == home_id or row_team_id == home_id:
            inferred = "home"
        elif key == away_id or row_team_id == away_id:
            inferred = "away"
        else:
            inferred = None
        box = team_row.get("box_score")
        if not isinstance(box, dict):
            continue
        for player_row in box.values():
            if isinstance(player_row, dict):
                consider(player_row, inferred)
    return best


def build_office_digest(ctx: Mapping[str, Any]) -> dict[str, Any]:
    """Pure digest. ``ctx`` is data the command-center load already has, plus the snapshot on the franchise."""
    franchise_doc = ctx.get("franchise_doc") or {}
    user_team_id = str(ctx.get("user_team_id") or "")
    week = _as_int(ctx.get("week"), 1) or 1
    rankings = ctx.get("rankings") or []
    standings = {
        str(row.get("team_id")): {
            "W": row.get("W", 0),
            "L": row.get("L", 0),
            "PF": row.get("PF", 0),
            "PA": row.get("PA", 0),
        }
        for row in rankings
        if isinstance(row, dict) and row.get("team_id") is not None
    }
    rank_by_team = {
        str(row.get("team_id")): _as_int(row.get("natl_rank"), 999) or 999
        for row in rankings
        if isinstance(row, dict) and row.get("team_id") is not None
    }
    conference_by_team = {
        str(row.get("team_id")): row.get("conference")
        for row in rankings
        if isinstance(row, dict) and row.get("team_id") is not None
    }
    user_conference = ctx.get("user_conference")
    if user_conference is None:
        user_conference = conference_by_team.get(user_team_id)
    now_rank = _as_int(ctx.get("national_rank"))
    if now_rank is None:
        now_rank = rank_by_team.get(user_team_id)
    now_position = conference_position(standings, conference_by_team, user_team_id, user_conference)
    snapshot = latest_snapshot(franchise_doc, week)
    prev_rank = _as_int(snapshot.get("national_rank_before")) if snapshot else None
    prev_position = _as_int(snapshot.get("conference_position_before")) if snapshot else None
    record, streak = record_and_streak(franchise_doc.get("results") or {}, user_team_id, standings)

    chemistry = _num(ctx.get("chemistry"))
    em_values = ctx.get("em_values") or []
    measures_state = "set_after_camp" if snapshot is None else "ready"
    team_snapshot = {
        "state": measures_state,
        "chemistry": {
            "value": chemistry,
            "max": CHEMISTRY_MAX,
        },
        "attitude": attitude_counts(em_values),
        "moved_most": moved_most(snapshot) if snapshot else [],
    }

    flags = ctx.get("advance_flags") or {}
    last = ctx.get("last_game") if isinstance(ctx.get("last_game"), dict) else None
    user_won: Optional[bool] = None
    result = None
    if last:
        home_id = str(last.get("home_team_id") or "")
        away_id = str(last.get("away_team_id") or "")
        user_is_home = home_id == user_team_id
        home_score = _as_int(last.get("home_score"), 0) or 0
        away_score = _as_int(last.get("away_score"), 0) or 0
        user_score = home_score if user_is_home else away_score
        opp_score = away_score if user_is_home else home_score
        if user_score != opp_score:
            user_won = user_score > opp_score
        opp_id = away_id if user_is_home else home_id
        game_doc = last.get("game_doc") if isinstance(last.get("game_doc"), dict) else None
        if user_won:
            leader = last.get("potg") if isinstance(last.get("potg"), dict) else None
            role = "potg"
        else:
            leader = user_team_leader(game_doc, user_is_home=user_is_home)
            role = "team_leader"
        game_id = last.get("game_id")
        result = {
            "week": last.get("week"),
            "home_team_id": home_id or None,
            "away_team_id": away_id or None,
            "home_team_name": last.get("home_team_name"),
            "away_team_name": last.get("away_team_name"),
            "home_score": home_score,
            "away_score": away_score,
            "user_is_home": user_is_home,
            "site": "home" if user_is_home else "away",
            "neutral": None,
            "opponent_team_id": opp_id or None,
            "opponent_team_name": last.get("opponent_team_name"),
            "opponent_rank": rank_by_team.get(opp_id),
            "round_name": ROUND_NAME_BY_WEEK.get(_as_int(last.get("week")) or -1),
            "user_won": user_won,
            "leader_role": role if leader else None,
            "leader": leader,
            "headline": headline_for_game(franchise_doc.get("season_news"), str(game_id) if game_id else None),
            "box_score": {
                "path": "/box-score.html",
                "params": {
                    "mode": "franchise",
                    "franchise_id": str(franchise_doc.get("_id") or ""),
                    "game_id": str(game_id) if game_id else None,
                    "home": last.get("home_team_name"),
                    "away": last.get("away_team_name"),
                },
            },
        }

    next_summary = ctx.get("next_game") if isinstance(ctx.get("next_game"), dict) else None
    next_game = None
    if next_summary:
        site_label = str(next_summary.get("matchup_label") or "")
        site = "home" if site_label == "vs" else "away"
        next_week = _as_int(next_summary.get("week"))
        next_game = {
            "week": next_week,
            "date": None,
            "site": site,
            "neutral": None,
            "opponent_team_id": next_summary.get("opponent_team_id"),
            "opponent": next_summary.get("opponent_team_name"),
            "rank": next_summary.get("rank"),
            "record": next_summary.get("record"),
            "conference": next_summary.get("opponent_team_conference"),
            "top_scorer": next_summary.get("top_scorer"),
            "top_rebounder": next_summary.get("top_rebounder"),
            "projected_starting_five": None,
            "round_name": ROUND_NAME_BY_WEEK.get(next_week or -1),
            "seeds": None,
            "stakes": None,
            "team_rt": None,
        }

    state = office_state(week=week, eos_tournament_active=bool(flags.get("eos_tournament_active")), user_won=user_won)
    wire = recruiting_wire_digest(ctx.get("recruiting_wire"), ctx.get("recruit_lookup"), week=week)
    signing = signing_day_digest(
        week=week,
        orders=ctx.get("signing_orders"),
        points_total=_as_int(ctx.get("signing_points_total"), 50) or 50,
        roster_spots=ctx.get("roster_spots"),
        recruit_lookup=ctx.get("recruit_lookup") or {},
        events=(ctx.get("recruiting_wire") or {}).get("events") if isinstance(ctx.get("recruiting_wire"), dict) else [],
    )
    season_preview = None
    if state == "first_week":
        newcomers = ctx.get("newcomers")
        season_preview = {
            "preseason_rank": now_rank,
            "conference_projection": None,
            "team_rt": None,
            "national_rank": now_rank,
            "returning_starters": None,
            "top_returner": None,
            "newcomers": newcomers if newcomers else None,
            "opener": next_game,
        }

    return {
        "state": state,
        "what_moved": {
            "national_rank": {"now": now_rank, "prev": prev_rank, "delta": _rank_delta(now_rank, prev_rank)},
            "conference_standing": {
                "now": now_position,
                "prev": prev_position,
                "delta": _rank_delta(now_position, prev_position),
            },
            "record": record,
            "streak": streak,
            "attribute_changes": attribute_changes_from_report(ctx.get("training_report")),
        },
        "team_snapshot": team_snapshot,
        "result": result,
        "next_game": next_game,
        "todos": build_todos(flags),
        "recruiting_wire": wire,
        "signing_day": signing,
        "season_preview": season_preview,
    }


def recruit_lookup_from_docs(recruits: Any, user_team_id: str) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for recruit in recruits or []:
        if not isinstance(recruit, dict):
            continue
        rid = str(recruit.get("recruit_id") or "")
        if not rid:
            continue
        lean = recruit.get("Lean") if isinstance(recruit.get("Lean"), dict) else {}
        lean_rank = None
        for slot in ("1", "2", "3"):
            if str(lean.get(slot) or "") == str(user_team_id):
                lean_rank = int(slot)
                break
        ratings = recruit.get("position_ratings")
        lookup[rid] = {
            "name": recruit.get("name"),
            "position": _best_position(ratings),
            "rt": _best_rt_letter(ratings),
            "lean_rank": lean_rank,
        }
    return lookup
