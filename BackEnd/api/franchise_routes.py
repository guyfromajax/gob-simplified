from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from starlette.responses import Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from pathlib import Path
from bson import ObjectId
import logging
import math
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import uuid
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlencode
from BackEnd.main import run_simulation, simulate_quarter

from BackEnd.db import (
    db,
    franchise_state_collection,
    franchise_team_data_collection,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
    games_collection,
)
from BackEnd.utils.shared import format_height, summarize_game_state
from BackEnd.utils.player_year import format_player_year_display
from BackEnd.utils import stat_updater
from BackEnd.utils.team_stats_aggregator import aggregate_team_stats_from_players
from BackEnd.models.franchise_manager import FranchiseManager, ScheduleManager
from BackEnd.tournament.bracket_engine import get_round_name
from BackEnd.tournament import franchise_tournament as ft
from BackEnd.tournament import franchise_tournament_progression as ftp
from BackEnd.utils.db_utils import build_lineup_from_mongo
from BackEnd.utils.roster_builder import build_roster_players
from BackEnd.utils.command_center_data import build_command_center_base
from BackEnd.utils.game_id_utils import (
    generate_game_id,
    purge_game_id_format_duplicates,
    resolve_game_write_id,
)
from BackEnd.models.training_execution_v2 import (
    TEAM_ATTR_CLAMPS,
    PLAYER_ATTR_CLAMP,
    parse_coaching_focus,
    build_eog_defensive_effectiveness_decay_ftd_updates,
    build_eog_offensive_play_effectiveness_decay_ftd_updates,
)
from BackEnd.models.distant_game_stats import build_distant_game_summary
from BackEnd.models.player import Player
from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.eog_attr_rules import (
    build_eog_inputs_from_game_doc,
)
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.ownership import verify_franchise_owned_by_user
from BackEnd.utils.franchise_training_state import (
    franchise_training_fully_complete_for_week,
    franchise_user_training_applied_for_week,
)
from BackEnd.utils.training_loading_highlights import build_training_loading_highlights
from BackEnd.utils.franchise_coaching_focus_counts import (
    COACHING_FOCUS_FTD_COUNT_KEYS,
    carryover_coaching_focus_counts_for_new_season,
    user_ftd_coaching_focus_increment,
)
from BackEnd.utils.franchise_geek_points import (
    maybe_award_franchise_loss_geek_points,
    maybe_award_franchise_win_geek_points,
)
from BackEnd.utils.community_highlights import (
    build_community_highlight_pending,
    flush_community_highlight_pending_after_week,
    lead_archetype_for_user,
    record_archetype_change_if_any,
    user_geek_points_delta_for_user_game_block,
    user_geek_points_snapshot_for_franchise,
)
from BackEnd.utils.franchise_championships import (
    maybe_award_conference_rs_championship,
    maybe_award_franchise_eos_title_championship,
)
from BackEnd.utils.position_ratings import compute_position_ratings
from BackEnd.utils.team_play_utils import iter_team_plays
from BackEnd.utils.franchise_ftd_game_seed import prepare_ftd_for_new_game
from BackEnd.models.game_manager import GameManager
from BackEnd.models.franchise_manager import choose_franchise_first_name, get_franchise_name_assets, generate_walk_on_profile
from BackEnd.utils.franchise_rank_prestige import (
    FRANCHISE_RANK_PRESTIGE_SYSTEM_VERSION,
    SOS_AVG_DEFAULT,
    apply_prestige_delta,
    core_total_player_attrs,
    rank_teams_for_week,
    use_franchise_rank_prestige_v2,
)

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"
RECRUITING_ORDERS_WEEK_35_FIELD = "recruiting_orders_week_35"
FCC_PENDING_NEW_LEAN_RECRUITS_FIELD = "fcc_pending_new_lean_recruit_ids"
WEEK_35_RECRUITING_RESULTS_FIELD = "week_35_recruiting_results"
AWARDS_FIELD = "awards"
WEEK_35_RECRUITING_POINTS_BUDGET = 50
SEASON_TRANSITION_TOKEN_FIELD = "season_transition_token"
RANK_PRESTIGE_SYSTEM_VERSION_FIELD = "rank_prestige_system_version"
RANK_PRESTIGE_LAST_APPLIED_WEEK_FIELD = "rank_prestige_last_applied_week"
POSTSEASON_TRAINING_DISABLED_WEEKS = range(27, 35)
POSTSEASON_EOG_TEAM_ATTRS_DISABLED_WEEKS = range(27, 35)
CPU_SIM_RUNNING_STALE_SECONDS = 180


def _week_in_policy_range(week: Any, policy_weeks: range) -> bool:
    try:
        return int(week) in policy_weeks
    except (TypeError, ValueError):
        return False


def _postseason_training_disabled_for_week(week: Any) -> bool:
    return _week_in_policy_range(week, POSTSEASON_TRAINING_DISABLED_WEEKS)


def _training_status_reset_after_advance_to_week(dest_week: Any) -> dict[str, Any] | None:
    """
    Weekly training applies when entering a normal franchise week.
    EOS tournament weeks (27-34) do not use training; do not churn training_status there.
    """
    if _postseason_training_disabled_for_week(dest_week):
        return None
    return {
        "training_status.training_completed": False,
        "training_status.session_type": "in-season",
    }


def _postseason_eog_team_attrs_disabled_for_week(week: Any) -> bool:
    return _week_in_policy_range(week, POSTSEASON_EOG_TEAM_ATTRS_DISABLED_WEEKS)


def _mint_season_transition_token() -> str:
    return str(uuid.uuid4())


def _ensure_season_transition_token(
    franchise_id: ObjectId,
    franchise_doc: dict[str, Any],
) -> str:
    token = str(franchise_doc.get(SEASON_TRANSITION_TOKEN_FIELD) or "").strip()
    if token:
        return token
    if int(franchise_doc.get("week", 1) or 1) != 36:
        return ""

    token = _mint_season_transition_token()
    result = db.franchises.update_one(
        {
            "_id": franchise_id,
            "$or": [
                {SEASON_TRANSITION_TOKEN_FIELD: {"$exists": False}},
                {SEASON_TRANSITION_TOKEN_FIELD: None},
                {SEASON_TRANSITION_TOKEN_FIELD: ""},
            ],
        },
        {"$set": {SEASON_TRANSITION_TOKEN_FIELD: token}},
    )
    if result.modified_count:
        franchise_doc[SEASON_TRANSITION_TOKEN_FIELD] = token
        return token

    refreshed = db.franchises.find_one({"_id": franchise_id}, {SEASON_TRANSITION_TOKEN_FIELD: 1}) or {}
    refreshed_token = str(refreshed.get(SEASON_TRANSITION_TOKEN_FIELD) or "").strip()
    if refreshed_token:
        franchise_doc[SEASON_TRANSITION_TOKEN_FIELD] = refreshed_token
    return refreshed_token


def _should_freeze_total_player_attrs(franchise_doc: dict[str, Any] | None) -> bool:
    return use_franchise_rank_prestige_v2(franchise_doc)


def _update_ftd_roster_state(
    franchise_id: ObjectId,
    team_object_id: ObjectId,
    update_fields: dict[str, Any],
) -> None:
    franchise_doc = db.franchises.find_one({"_id": franchise_id}, {RANK_PRESTIGE_SYSTEM_VERSION_FIELD: 1}) or {}
    if _should_freeze_total_player_attrs(franchise_doc):
        update_fields = {k: v for k, v in update_fields.items() if k != "total_player_attrs"}
    franchise_team_data_collection.update_one(
        {"franchise_id": franchise_id, "team_id": team_object_id},
        {"$set": update_fields},
    )


def _reset_team_play_scorers_for_new_season(plays: dict[str, Any] | None) -> dict[str, Any]:
    """Preserve team play config while clearing season-bound top-scorer tracking."""
    reset_plays = deepcopy(plays or {})
    for _play_key, play_data, _display_name in iter_team_plays(reset_plays):
        if not isinstance(play_data, dict):
            continue
        season_stats = play_data.get("season_stats")
        if isinstance(season_stats, dict):
            season_stats["player_points"] = {}
    return reset_plays


def _apply_regular_season_rank_prestige_updates(
    franchise_id: ObjectId,
    franchise_doc: dict[str, Any],
    completed_week: int,
    week_results: list[dict[str, Any]],
) -> None:
    if not use_franchise_rank_prestige_v2(franchise_doc):
        return
    if completed_week < 1 or completed_week > ScheduleManager.REGULAR_SEASON_WEEKS:
        return

    last_applied_week = int(franchise_doc.get(RANK_PRESTIGE_LAST_APPLIED_WEEK_FIELD, 0) or 0)
    if last_applied_week >= completed_week:
        logger.info(
            "⏭️ [RANK_PRESTIGE] Skipping franchise=%s week=%s; already applied through week=%s",
            franchise_id,
            completed_week,
            last_applied_week,
        )
        return

    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "prestige": 1, "total_player_attrs": 1, "natl_rank": 1, "sos_avg": 1, "sos_rank_sum": 1, "sos_games_played": 1},
    ))
    team_state_by_id: dict[str, dict[str, Any]] = {}
    previous_rank_by_team: dict[str, int] = {}
    for doc in ftd_docs:
        team_id = str(doc.get("team_id") or "")
        if not team_id:
            continue
        previous_rank = int(doc.get("natl_rank", 999) or 999)
        previous_rank_by_team[team_id] = previous_rank
        team_state_by_id[team_id] = {
            "team_id": team_id,
            "prestige": int(doc.get("prestige", 0) or 0),
            "total_player_attrs": int(doc.get("total_player_attrs", 0) or 0),
            "natl_rank": previous_rank,
            "sos_avg": float(doc.get("sos_avg", SOS_AVG_DEFAULT) or SOS_AVG_DEFAULT),
            "sos_rank_sum": float(doc.get("sos_rank_sum", 0) or 0),
            "sos_games_played": int(doc.get("sos_games_played", 0) or 0),
        }

    for result in week_results:
        away_id = str(result.get("away_id") or "")
        home_id = str(result.get("home_id") or "")
        if away_id not in team_state_by_id or home_id not in team_state_by_id:
            continue
        away_state = team_state_by_id[away_id]
        home_state = team_state_by_id[home_id]

        away_rank_entering_week = previous_rank_by_team.get(away_id, 64)
        home_rank_entering_week = previous_rank_by_team.get(home_id, 64)
        away_state["sos_rank_sum"] += home_rank_entering_week
        away_state["sos_games_played"] += 1
        home_state["sos_rank_sum"] += away_rank_entering_week
        home_state["sos_games_played"] += 1

        away_score = int(result.get("away_score", 0) or 0)
        home_score = int(result.get("home_score", 0) or 0)
        if away_score == home_score:
            logger.warning("⚠️ [RANK_PRESTIGE] Tied game detected for franchise=%s week=%s teams=%s/%s; prestige unchanged", franchise_id, completed_week, away_id, home_id)
            continue

        if away_score > home_score:
            new_winner_prestige, new_loser_prestige = apply_prestige_delta(
                away_state["prestige"],
                home_state["prestige"],
                week=completed_week,
            )
            away_state["prestige"] = new_winner_prestige
            home_state["prestige"] = new_loser_prestige
        else:
            new_winner_prestige, new_loser_prestige = apply_prestige_delta(
                home_state["prestige"],
                away_state["prestige"],
                week=completed_week,
            )
            home_state["prestige"] = new_winner_prestige
            away_state["prestige"] = new_loser_prestige

    from BackEnd.utils.franchise_standings import calculate_franchise_standings

    results_snapshot = dict(franchise_doc.get("results", {}) or {})
    results_snapshot[str(completed_week)] = week_results
    standings_data = calculate_franchise_standings(results_snapshot, team_state_by_id)

    ranking_inputs: list[dict[str, Any]] = []
    for team_id, state in team_state_by_id.items():
        games_played = int(state.get("sos_games_played", 0) or 0)
        sos_avg = SOS_AVG_DEFAULT if games_played <= 0 else float(state.get("sos_rank_sum", 0) or 0) / games_played
        state["sos_avg"] = sos_avg
        team_standings = standings_data.get(team_id, {"W": 0, "L": 0})
        ranking_inputs.append({
            "team_id": team_id,
            "prestige": int(state.get("prestige", 0) or 0),
            "total_player_attrs": int(state.get("total_player_attrs", 0) or 0),
            "team_wins": int(team_standings.get("W", 0) or 0),
            "sos_avg": sos_avg,
        })

    ranked = rank_teams_for_week(ranking_inputs, week=completed_week, previous_rank_by_team=previous_rank_by_team)
    ranked_by_team = {str(entry["team_id"]): entry for entry in ranked}

    for doc in ftd_docs:
        team_id = str(doc.get("team_id") or "")
        if team_id not in team_state_by_id or team_id not in ranked_by_team:
            continue
        state = team_state_by_id[team_id]
        ranked_entry = ranked_by_team[team_id]
        team_standings = standings_data.get(team_id, {"W": 0, "L": 0})
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": doc["team_id"]},
            {"$set": {
                "prestige": int(state["prestige"]),
                "natl_rank": int(ranked_entry["natl_rank"]),
                "sos_avg": float(state["sos_avg"]),
                "sos_rank_sum": float(state["sos_rank_sum"]),
                "sos_games_played": int(state["sos_games_played"]),
                "season_wins": int(team_standings.get("W", 0) or 0),
                "season_losses": int(team_standings.get("L", 0) or 0),
                "updated_at": datetime.utcnow(),
            }},
        )

    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {RANK_PRESTIGE_LAST_APPLIED_WEEK_FIELD: completed_week}},
    )


def _game_doc_richness_score(game_doc: dict) -> int:
    """
    Score how complete/useful a game document is for EOG processing.
    Higher score means better canonical snapshot source.
    """
    if not isinstance(game_doc, dict):
        return -1

    score = 0
    teams_obj = game_doc.get("teams")
    if isinstance(teams_obj, dict) and teams_obj:
        score += 5
        for team_data in teams_obj.values():
            if not isinstance(team_data, dict):
                continue
            totals = team_data.get("totals", {})
            if isinstance(totals, dict) and totals.get("FGA", 0) > 0:
                score += 10
                break
            team_box = team_data.get("box_score", {})
            if isinstance(team_box, dict) and team_box:
                score += 6
                break

    top_box = game_doc.get("box_score", {})
    if isinstance(top_box, dict) and top_box:
        score += 3

    team_totals = game_doc.get("team_totals", {})
    if isinstance(team_totals, dict) and team_totals:
        score += 3

    return score


def _build_next_matchup_map(
    franchise_doc: dict[str, Any],
    team_name_by_id: dict[str, str],
    natl_rank_by_team_id: dict[str, int],
) -> dict[str, str]:
    schedule = franchise_doc.get("schedule", [])
    week = int(franchise_doc.get("week", 1) or 1)
    matchup_map: dict[str, str] = {}
    eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
    eos_has_state = bool(
        franchise_doc.get("conference_tournaments")
        or franchise_doc.get("region_tournaments")
        or franchise_doc.get("national_tournament")
    )
    if eos_tournament_active and eos_has_state and week in ft.EOS_WEEKS:
        week_games_meta = ft.get_eos_week_games(franchise_doc, week)
        for g in week_games_meta:
            away_id = g.get("away_id")
            home_id = g.get("home_id")
            if away_id and home_id:
                try:
                    aid = ObjectId(away_id) if isinstance(away_id, str) else away_id
                    hid = ObjectId(home_id) if isinstance(home_id, str) else home_id
                    home_name = _format_team_name_with_rank(
                        str(hid),
                        team_name_by_id.get(str(hid), ""),
                        natl_rank_by_team_id,
                    )
                    away_name = _format_team_name_with_rank(
                        str(aid),
                        team_name_by_id.get(str(aid), ""),
                        natl_rank_by_team_id,
                    )
                    matchup_map[str(aid)] = f"at {home_name}"
                    matchup_map[str(hid)] = f"vs {away_name}"
                except Exception:
                    continue
        return matchup_map

    next_games = schedule[week - 1] if week - 1 < len(schedule) else []
    for away_id, home_id in next_games:
        home_name = _format_team_name_with_rank(
            str(home_id),
            team_name_by_id.get(str(home_id), ""),
            natl_rank_by_team_id,
        )
        away_name = _format_team_name_with_rank(
            str(away_id),
            team_name_by_id.get(str(away_id), ""),
            natl_rank_by_team_id,
        )
        matchup_map[str(away_id)] = f"at {home_name}"
        matchup_map[str(home_id)] = f"vs {away_name}"
    return matchup_map


def _build_previous_week_result_map(
    franchise_doc: dict[str, Any],
    team_name_by_id: dict[str, str],
    natl_rank_by_team_id: dict[str, int],
) -> dict[str, dict[str, str]]:
    week = int(franchise_doc.get("week", 1) or 1)
    previous_week = week - 1
    if previous_week < 1:
        return {}

    previous_results = list((franchise_doc.get("results", {}) or {}).get(str(previous_week), []) or [])
    result_map: dict[str, dict[str, str]] = {}
    for result in previous_results:
        away_id = str(result.get("away_id") or "")
        home_id = str(result.get("home_id") or "")
        if not away_id or not home_id:
            continue
        away_name = _format_team_name_with_rank(
            away_id,
            team_name_by_id.get(away_id, away_id),
            natl_rank_by_team_id,
        )
        home_name = _format_team_name_with_rank(
            home_id,
            team_name_by_id.get(home_id, home_id),
            natl_rank_by_team_id,
        )
        away_score = int(result.get("away_score", 0) or 0)
        home_score = int(result.get("home_score", 0) or 0)
        if away_score > home_score:
            away_outcome = "W"
            home_outcome = "L"
        elif home_score > away_score:
            away_outcome = "L"
            home_outcome = "W"
        else:
            away_outcome = "T"
            home_outcome = "T"

        result_map[away_id] = {
            "text": f"@ {home_name}, {away_score}-{home_score}",
            "result": away_outcome,
        }
        result_map[home_id] = {
            "text": f"vs {away_name}, {home_score}-{away_score}",
            "result": home_outcome,
        }
    return result_map


def _format_team_name_with_rank(
    team_id: str,
    team_name: str,
    natl_rank_by_team_id: dict[str, int],
) -> str:
    natl_rank = int(natl_rank_by_team_id.get(str(team_id), 999) or 999)
    if 1 <= natl_rank <= 25:
        return f"#{natl_rank} {team_name}"
    return team_name


def _canonical_team_name(value: str) -> str:
    if not value:
        return ""
    return str(value).replace("-", "_").replace(" ", "_").upper()


def _normalize_team_name(value: str) -> str:
    return str(value or "").strip().lower()


def _extract_game_box_score(game_doc: dict[str, Any]) -> dict[str, Any]:
    box_score = game_doc.get("box_score")
    if isinstance(box_score, dict) and box_score:
        return box_score

    result: dict[str, Any] = {}
    teams_obj = game_doc.get("teams")
    if isinstance(teams_obj, dict):
        for team_key, team_data in teams_obj.items():
            if isinstance(team_data, dict):
                team_box = team_data.get("box_score")
                if isinstance(team_box, dict) and team_box:
                    result[str(team_key)] = team_box

    if result:
        return result

    for team_side in ("home_team", "away_team"):
        team_data = game_doc.get(team_side)
        if isinstance(team_data, dict) and isinstance(team_data.get("box_score"), dict):
            team_name = str(team_data.get("name") or team_side)
            result[team_name] = team_data["box_score"]
    return result


def _infer_box_score_team_side(team_key: str, home_team_id: str, away_team_id: str, home_team_name: str, away_team_name: str) -> Optional[str]:
    home_names = {
        str(home_team_id or ""),
        str(home_team_name or ""),
        _canonical_team_name(home_team_name),
        _normalize_team_name(home_team_name),
    }
    away_names = {
        str(away_team_id or ""),
        str(away_team_name or ""),
        _canonical_team_name(away_team_name),
        _normalize_team_name(away_team_name),
    }
    key_normalized = _normalize_team_name(team_key)
    if team_key in home_names or key_normalized in home_names:
        return "home"
    if team_key in away_names or key_normalized in away_names:
        return "away"
    return None


def _calculate_potg_summary(game_doc: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(game_doc, dict):
        logger.warning("🧭 [FCC-POTG] game_doc is not a dict; cannot calculate POTG")
        return None

    selected_game_id = str(game_doc.get("_id") or game_doc.get("game_id") or "")
    home_team_id = str(game_doc.get("home_team_id") or "")
    away_team_id = str(game_doc.get("away_team_id") or "")
    teams_obj = game_doc.get("teams") or {}
    home_team_obj = teams_obj.get(home_team_id, {}) if isinstance(teams_obj, dict) else {}
    away_team_obj = teams_obj.get(away_team_id, {}) if isinstance(teams_obj, dict) else {}
    if not home_team_obj and isinstance(game_doc.get("home_team"), dict):
        home_team_obj = game_doc.get("home_team") or {}
    if not away_team_obj and isinstance(game_doc.get("away_team"), dict):
        away_team_obj = game_doc.get("away_team") or {}

    home_team_name = str(home_team_obj.get("name") or (game_doc.get("home_team", {}) or {}).get("name") or "Home Team")
    away_team_name = str(away_team_obj.get("name") or (game_doc.get("away_team", {}) or {}).get("name") or "Away Team")

    score_map = game_doc.get("score") or {}
    home_score = int(score_map.get(home_team_name, home_team_obj.get("score", 0)) or 0)
    away_score = int(score_map.get(away_team_name, away_team_obj.get("score", 0)) or 0)
    winning_team = "home" if home_score > away_score else ("away" if away_score > home_score else None)

    candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    players_source_count = 0
    box_score_source_count = 0

    def upsert_player(raw: dict[str, Any], fallback_team: Optional[str] = None) -> None:
        nonlocal players_source_count, box_score_source_count
        if not isinstance(raw, dict):
            return
        stats = raw.get("stats", {}).get("game") if isinstance(raw.get("stats"), dict) and isinstance(raw.get("stats", {}).get("game"), dict) else raw.get("stats", raw)
        if not isinstance(stats, dict):
            stats = raw
        name = str(raw.get("name") or "").strip()
        if not name:
            return
        player_id = str(raw.get("playerId") or raw.get("player_id") or raw.get("_id") or f"{fallback_team or 'unknown'}:{name}")
        dedupe_key = f"{player_id}:{fallback_team or raw.get('team') or 'unknown'}"
        if dedupe_key in seen_keys:
            return
        seen_keys.add(dedupe_key)
        if fallback_team:
            box_score_source_count += 1
        else:
            players_source_count += 1
        candidates.append({
            "player_id": player_id,
            "name": name,
            "team": fallback_team or raw.get("team") or "",
            "stats": stats,
        })

    players = game_doc.get("players")
    if isinstance(players, list):
        for player in players:
            if isinstance(player, dict):
                team = player.get("team")
                upsert_player(player, team if team in {"home", "away"} else None)

    for team_key, team_box in (_extract_game_box_score(game_doc) or {}).items():
        if not isinstance(team_box, dict):
            continue
        inferred_team = _infer_box_score_team_side(str(team_key), home_team_id, away_team_id, home_team_name, away_team_name)
        for player_data in team_box.values():
            if isinstance(player_data, dict):
                upsert_player(player_data, inferred_team)

    logger.warning(
        "🧭 [FCC-POTG] Selected game_id=%s home=%s away=%s has_players=%s top_box_score=%s nested_teams=%s candidate_count=%s from_players=%s from_box_score=%s",
        selected_game_id,
        home_team_name,
        away_team_name,
        isinstance(players, list) and len(players) > 0,
        isinstance(game_doc.get("box_score"), dict) and bool(game_doc.get("box_score")),
        isinstance(game_doc.get("teams"), dict) and bool(game_doc.get("teams")),
        len(candidates),
        players_source_count,
        box_score_source_count,
    )

    if not candidates:
        logger.warning("🧭 [FCC-POTG] No POTG candidates found for game_id=%s", selected_game_id)
        return None

    scored: list[dict[str, Any]] = []
    for player in candidates:
        stats = player.get("stats") or {}
        pts = int(stats.get("PTS", 0) or 0)
        ast = int(stats.get("AST", 0) or 0)
        reb = int(stats.get("TREB", (stats.get("OREB", 0) or 0) + (stats.get("DREB", 0) or 0)) or 0)
        stl = int(stats.get("STL", 0) or 0)
        blk = int(stats.get("BLK", 0) or 0)
        def_a = int(stats.get("DEF_A", 0) or 0)
        def_s = int(stats.get("DEF_S", 0) or 0)
        def_pct = round((def_s / def_a) * 100) if def_a > 0 else 0
        score = 2 * (pts + ast + reb + stl + blk)
        if def_a > 10:
            if def_pct > 80:
                score += 15
            elif def_pct > 60:
                score += 10
            elif def_pct > 40:
                score += 5
        if winning_team and player.get("team") == winning_team:
            score += 3
        scored.append({
            "name": player["name"],
            "team": player.get("team"),
            "score": score,
            "stats": {
                "pts": pts,
                "reb": reb,
                "ast": ast,
                "stl": stl,
                "blk": blk,
                "defPct": def_pct,
            },
        })

    scored.sort(key=lambda item: (-item["score"], -item["stats"]["pts"], -item["stats"]["reb"], -item["stats"]["ast"]))
    top = scored[0]
    logger.warning(
        "🧭 [FCC-POTG] POTG resolved for game_id=%s winner=%s pts=%s reb=%s ast=%s stl=%s blk=%s defPct=%s",
        selected_game_id,
        top["name"],
        top["stats"]["pts"],
        top["stats"]["reb"],
        top["stats"]["ast"],
        top["stats"]["stl"],
        top["stats"]["blk"],
        top["stats"]["defPct"],
    )
    return {
        "name": top["name"],
        "stats": top["stats"],
    }


def _build_team_leader_summary(franchise_id: ObjectId, team_id: str) -> dict[str, Any]:
    players = get_team_player_stats(str(franchise_id), team_id, scope="season", sort=None, direction="desc")
    top_scorer: Optional[dict[str, Any]] = None
    top_rebounder: Optional[dict[str, Any]] = None
    top_scoring_avg = -1.0
    top_rebounding_avg = -1.0
    # Raw FPD season totals for the leader row (FCC Next container); logged for debugging PTS/GP mismatch.
    leader_pts_total = 0.0
    leader_pts_gp = 0
    leader_pts_name = ""
    leader_reb_total = 0.0
    leader_reb_gp = 0
    leader_reb_name = ""

    for player in players:
        stats = player.get("stats") or {}
        gp = int(stats.get("GP", 0) or 0)
        if gp <= 0:
            continue
        pts_total = float(stats.get("PTS", 0) or 0)
        pts_avg = pts_total / gp
        reb_total = float(stats.get("TREB", ((stats.get("OREB", 0) or 0) + (stats.get("DREB", 0) or 0))) or 0)
        reb_avg = reb_total / gp
        player_name = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip() or "Unknown"
        if pts_avg > top_scoring_avg:
            top_scoring_avg = pts_avg
            top_scorer = {"name": player_name, "average": round(pts_avg, 1)}
            leader_pts_total = pts_total
            leader_pts_gp = gp
            leader_pts_name = player_name
        if reb_avg > top_rebounding_avg:
            top_rebounding_avg = reb_avg
            top_rebounder = {"name": player_name, "average": round(reb_avg, 1)}
            leader_reb_total = reb_total
            leader_reb_gp = gp
            leader_reb_name = player_name

    logger.warning(
        "🧭 [FCC-NEXT-LEADERS] franchise_id=%s team_id=%s roster_players=%s | "
        "top_scorer name=%s PTS_season=%s GP=%s pts_per_game=%s card_avg=%s | "
        "top_rebounder name=%s REB_season=%s GP=%s reb_per_game=%s card_avg=%s",
        str(franchise_id),
        str(team_id),
        len(players),
        leader_pts_name or "(none)",
        leader_pts_total,
        leader_pts_gp,
        round(leader_pts_total / leader_pts_gp, 3) if leader_pts_gp else 0.0,
        top_scorer.get("average") if top_scorer else None,
        leader_reb_name or "(none)",
        leader_reb_total,
        leader_reb_gp,
        round(leader_reb_total / leader_reb_gp, 3) if leader_reb_gp else 0.0,
        top_rebounder.get("average") if top_rebounder else None,
    )

    return {
        "top_scorer": top_scorer,
        "top_rebounder": top_rebounder,
    }


def _find_user_next_game(franchise_doc: dict[str, Any], user_team_id_str: str) -> Optional[dict[str, Any]]:
    week = int(franchise_doc.get("week", 1) or 1)
    eos_active = bool(
        franchise_doc.get("eos_tournament_active")
        and (franchise_doc.get("conference_tournaments") or franchise_doc.get("region_tournaments") or franchise_doc.get("national_tournament"))
    )
    if week in ft.EOS_WEEKS and eos_active:
        for game in ft.get_eos_week_games(franchise_doc, week):
            away_id = str(game.get("away_id") or "")
            home_id = str(game.get("home_id") or "")
            if user_team_id_str in {away_id, home_id}:
                return {"week": week, "away_team_id": away_id, "home_team_id": home_id}

    schedule = franchise_doc.get("schedule", []) or []
    if week < 1 or week > len(schedule):
        return None
    for away_id, home_id in schedule[week - 1]:
        away_str = str(away_id)
        home_str = str(home_id)
        if user_team_id_str in {away_str, home_str}:
            return {"week": week, "away_team_id": away_str, "home_team_id": home_str}
    return None


def _clock_from_time_remaining(seconds: Any) -> str:
    try:
        total = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        total = 480
    return f"{total // 60}:{total % 60:02d}"


def _find_active_user_game_resume(franchise_doc: dict[str, Any], user_team_id_str: str) -> Optional[dict[str, Any]]:
    next_game = _find_user_next_game(franchise_doc, user_team_id_str)
    if not next_game:
        logger.warning(
            "🧭 [MODE-RESUME-LOOKUP] no_next_game franchise_id=%s user_team_id=%s week=%s",
            str(franchise_doc.get("_id") or ""),
            user_team_id_str,
            franchise_doc.get("week"),
        )
        return None

    franchise_id = str(franchise_doc.get("_id") or "")
    away_id = str(next_game.get("away_team_id") or "")
    home_id = str(next_game.get("home_team_id") or "")
    if not franchise_id or not away_id or not home_id:
        logger.warning(
            "🧭 [MODE-RESUME-LOOKUP] incomplete_next_game franchise_id=%s user_team_id=%s next_game=%s",
            franchise_id,
            user_team_id_str,
            next_game,
        )
        return None

    team_object_ids = []
    for raw_id in (home_id, away_id):
        try:
            team_object_ids.append(ObjectId(raw_id))
        except Exception:
            pass
    team_docs_raw = list(db.teams.find({"_id": {"$in": team_object_ids}})) if team_object_ids else []
    team_docs_by_id = {str(team.get("_id")): team for team in team_docs_raw}

    def _identifier_tokens(*values: Any) -> set[str]:
        tokens: set[str] = set()
        for value in values:
            if value is None:
                continue
            raw = str(value).strip()
            if not raw:
                continue
            tokens.add(raw.casefold())
            tokens.add(raw.replace(" ", "_").casefold())
            tokens.add(raw.replace("_", " ").casefold())
        return tokens

    def _team_tokens(canonical_id: str) -> set[str]:
        team_doc = team_docs_by_id.get(canonical_id, {})
        values: list[Any] = [canonical_id]
        for key in ("_id", "id", "team_id", "slug", "name", "display_name"):
            value = team_doc.get(key) if isinstance(team_doc, dict) else None
            if value:
                values.append(value)
        return _identifier_tokens(*values)

    expected_home_tokens = _team_tokens(home_id)
    expected_away_tokens = _team_tokens(away_id)
    logger.warning(
        "🧭 [MODE-RESUME-LOOKUP] start franchise_id=%s week=%s user_team_id=%s expected_away=%s expected_home=%s expected_away_tokens=%s expected_home_tokens=%s",
        franchise_id,
        next_game.get("week"),
        user_team_id_str,
        away_id,
        home_id,
        sorted(expected_away_tokens),
        sorted(expected_home_tokens),
    )

    def _anchor_snapshot(doc: dict[str, Any]) -> dict[str, Any]:
        anchor = doc.get("resume_anchor") if isinstance(doc.get("resume_anchor"), dict) else {}
        snapshot = anchor.get("snapshot") if isinstance(anchor.get("snapshot"), dict) else None
        return snapshot or {}

    def _extract_team_tokens(team_obj: Any) -> set[str]:
        if not isinstance(team_obj, dict):
            return set()
        values: list[Any] = []
        for key in ("_id", "id", "team_id", "slug", "name", "display_name"):
            value = team_obj.get(key)
            if value:
                values.append(value)
        return _identifier_tokens(*values)

    def _candidate_side_tokens(doc: dict[str, Any], side: str) -> set[str]:
        snapshot = _anchor_snapshot(doc)
        tokens: set[str] = set()
        direct_keys = {
            "home": ("home_team_id", "team1_id"),
            "away": ("away_team_id", "team2_id"),
        }[side]
        for source in (doc, snapshot):
            if not isinstance(source, dict):
                continue
            for key in direct_keys:
                value = source.get(key)
                if value:
                    tokens.update(_identifier_tokens(value))

            team_obj = source.get(f"{side}_team")
            tokens.update(_extract_team_tokens(team_obj))

            teams_obj = source.get("teams") if isinstance(source.get("teams"), dict) else {}
            for team_key, team_row in teams_obj.items():
                row_tokens = _identifier_tokens(team_key)
                row_tokens.update(_extract_team_tokens(team_row))
                if tokens.intersection(row_tokens):
                    tokens.update(row_tokens)
        return tokens

    def _candidate_pair(doc: dict[str, Any]) -> set[str]:
        return _candidate_side_tokens(doc, "home").union(_candidate_side_tokens(doc, "away"))

    def _matches_current_user_game(doc: dict[str, Any]) -> bool:
        candidate_home_tokens = _candidate_side_tokens(doc, "home")
        candidate_away_tokens = _candidate_side_tokens(doc, "away")
        direct_match = bool(expected_home_tokens.intersection(candidate_home_tokens)) and bool(
            expected_away_tokens.intersection(candidate_away_tokens)
        )
        swapped_match = bool(expected_home_tokens.intersection(candidate_away_tokens)) and bool(
            expected_away_tokens.intersection(candidate_home_tokens)
        )
        return direct_match or swapped_match

    def _parse_anchor_saved_at(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return datetime.min
        return datetime.min

    def _parse_anchor_quarter(doc: dict[str, Any]) -> int:
        anchor = doc.get("resume_anchor") if isinstance(doc.get("resume_anchor"), dict) else {}
        snapshot = anchor.get("snapshot") if isinstance(anchor.get("snapshot"), dict) else {}
        for value in (snapshot.get("quarter"), anchor.get("quarter"), doc.get("quarter")):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                continue
        return 0

    def _candidate_sort_key(doc: dict[str, Any]) -> tuple[int, datetime, Any]:
        anchor = doc.get("resume_anchor") if isinstance(doc.get("resume_anchor"), dict) else {}
        oid = doc.get("_id")
        return (
            _parse_anchor_quarter(doc),
            _parse_anchor_saved_at(anchor.get("saved_at")),
            oid if isinstance(oid, ObjectId) else ObjectId("000000000000000000000000"),
        )

    game_doc = None
    matched_candidates: list[dict[str, Any]] = []
    anchor_cursor = db.games.find(
        {
            "franchise_id": franchise_id,
            "is_final": {"$ne": True},
            "resume_anchor": {"$type": "object"},
        },
        sort=[("_id", -1)],
        limit=12,
    )
    anchor_candidate_count = 0
    rejected_candidates: list[dict[str, Any]] = []
    for candidate in anchor_cursor:
        anchor_candidate_count += 1
        if _matches_current_user_game(candidate):
            matched_candidates.append(candidate)
            continue
        if len(rejected_candidates) < 5:
            rejected_candidates.append(
                {
                    "game_id": str(candidate.get("_id")),
                    "pair": sorted(_candidate_pair(candidate)),
                    "has_snapshot": bool(_anchor_snapshot(candidate)),
                }
            )

    if matched_candidates:
        game_doc = max(matched_candidates, key=_candidate_sort_key)

    matched_sample = []
    for candidate in matched_candidates[:8]:
        anchor = candidate.get("resume_anchor") if isinstance(candidate.get("resume_anchor"), dict) else {}
        snapshot = anchor.get("snapshot") if isinstance(anchor.get("snapshot"), dict) else {}
        matched_sample.append(
            {
                "game_id": str(candidate.get("_id")),
                "anchor_type": anchor.get("anchor_type"),
                "anchor_quarter": _parse_anchor_quarter(candidate),
                "saved_at": anchor.get("saved_at"),
                "clock": snapshot.get("clock") or anchor.get("clock") or candidate.get("clock"),
                "time_remaining": snapshot.get("time_remaining") or anchor.get("time_remaining") or candidate.get("time_remaining"),
            }
        )

    logger.warning(
        "🧭 [MODE-RESUME-LOOKUP] anchored_scan franchise_id=%s candidates=%s matched=%s selected_game_id=%s matched_sample=%s rejected_sample=%s",
        franchise_id,
        anchor_candidate_count,
        len(matched_candidates),
        str(game_doc.get("_id")) if game_doc else None,
        matched_sample,
        rejected_candidates,
    )

    if not game_doc:
        logger.warning(
            "🧭 [MODE-RESUME-LOOKUP] no_match franchise_id=%s expected_away_tokens=%s expected_home_tokens=%s",
            franchise_id,
            sorted(expected_away_tokens),
            sorted(expected_home_tokens),
        )
        return None

    resume_anchor = game_doc.get("resume_anchor") if isinstance(game_doc.get("resume_anchor"), dict) else {}
    if not resume_anchor:
        logger.warning(
            "🧭 [MODE-RESUME-LOOKUP] matched_without_anchor_ignored game_id=%s franchise_id=%s",
            str(game_doc.get("_id")),
            franchise_id,
        )
        return None
    source_doc = _anchor_snapshot(game_doc) if resume_anchor else game_doc

    def _parse_int(value, default: int) -> int:
        if value is None:
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def _norm_key(value) -> str:
        return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

    def _find_team_row(teams: dict, *candidates):
        if not isinstance(teams, dict):
            return {}
        raw_candidates = [str(c) for c in candidates if c is not None and str(c) != ""]
        normalized = {_norm_key(c) for c in raw_candidates}
        for candidate in raw_candidates:
            row = teams.get(candidate)
            if isinstance(row, dict):
                return row
        for key, row in teams.items():
            if not isinstance(row, dict):
                continue
            if _norm_key(key) in normalized:
                return row
            row_candidates = {
                _norm_key(row.get("team_id")),
                _norm_key(row.get("_id")),
                _norm_key(row.get("name")),
                _norm_key(row.get("slug")),
            }
            if normalized.intersection(row_candidates):
                return row
        return {}

    def _score_from_source(row: dict, team: dict, score_map: dict, names: list[str], direct_key: str) -> int:
        for value in (
            row.get("score") if isinstance(row, dict) else None,
            team.get("score") if isinstance(team, dict) else None,
            source_doc.get(direct_key),
        ):
            if value is not None:
                return _parse_int(value, 0)
        if isinstance(score_map, dict):
            for name in names:
                if name and score_map.get(name) is not None:
                    return _parse_int(score_map.get(name), 0)
            normalized_score = {_norm_key(k): v for k, v in score_map.items()}
            for name in names:
                key = _norm_key(name)
                if key and normalized_score.get(key) is not None:
                    return _parse_int(normalized_score.get(key), 0)
        return 0

    try:
        quarter = int(source_doc.get("quarter", resume_anchor.get("quarter", 1) if resume_anchor else 1) or 1)
    except (TypeError, ValueError):
        quarter = 1
    time_remaining = _parse_int(
        source_doc.get("time_remaining", resume_anchor.get("time_remaining") if resume_anchor else None),
        480,
    )

    home_team = source_doc.get("home_team") if isinstance(source_doc.get("home_team"), dict) else {}
    away_team = source_doc.get("away_team") if isinstance(source_doc.get("away_team"), dict) else {}
    teams_obj = source_doc.get("teams") if isinstance(source_doc.get("teams"), dict) else {}
    source_home_id = str(source_doc.get("home_team_id") or game_doc.get("home_team_id") or home_id)
    source_away_id = str(source_doc.get("away_team_id") or game_doc.get("away_team_id") or away_id)
    home_row = _find_team_row(teams_obj, source_home_id, home_id, home_team.get("name"), source_doc.get("home_team_name"))
    away_row = _find_team_row(teams_obj, source_away_id, away_id, away_team.get("name"), source_doc.get("away_team_name"))
    score_map = source_doc.get("score") if isinstance(source_doc.get("score"), dict) else {}
    team_docs = {
        str(team["_id"]): team.get("name", str(team["_id"]))
        for team in team_docs_raw
    }
    home_name = home_row.get("name") or home_team.get("name") or source_doc.get("home_team_name") or team_docs.get(source_home_id, team_docs.get(home_id, home_id))
    away_name = away_row.get("name") or away_team.get("name") or source_doc.get("away_team_name") or team_docs.get(source_away_id, team_docs.get(away_id, away_id))
    home_score = _score_from_source(home_row, home_team, score_map, [home_name, source_home_id, home_id], "home_score")
    away_score = _score_from_source(away_row, away_team, score_map, [away_name, source_away_id, away_id], "away_score")
    resume_from_timeout = bool(
        resume_anchor.get("resume_from_timeout")
        or source_doc.get("timeout_next_play_type")
        or game_doc.get("timeout_next_play_type")
    )
    anchor_type = resume_anchor.get("anchor_type") if resume_anchor else None
    if resume_anchor and not anchor_type:
        anchor_type = "timeout" if resume_from_timeout else "quarter_break"
    has_started = (
        quarter > 1
        or time_remaining < 480
        or home_score != 0
        or away_score != 0
        or bool(source_doc.get("opening_tip_winner") or game_doc.get("opening_tip_winner"))
    )
    if not has_started:
        logger.warning(
            "🧭 [MODE-RESUME-LOOKUP] matched_but_not_started game_id=%s quarter=%s time_remaining=%s home_score=%s away_score=%s has_anchor=%s",
            str(game_doc.get("_id")),
            quarter,
            time_remaining,
            home_score,
            away_score,
            bool(resume_anchor),
        )
        return None

    payload = {
        "game_id": str(game_doc.get("_id")),
        "franchise_id": franchise_id,
        "week": int(next_game.get("week", franchise_doc.get("week", 1)) or 1),
        "quarter": quarter,
        "clock": source_doc.get("clock") or resume_anchor.get("clock") or game_doc.get("clock") or _clock_from_time_remaining(time_remaining),
        "time_remaining": time_remaining,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "home_team_name": home_name,
        "away_team_name": away_name,
        "home_score": home_score,
        "away_score": away_score,
        "user_team_side": "home" if user_team_id_str == home_id else "away",
        "status": "stoppage_anchor" if resume_anchor else "active_mid_quarter",
        "anchor_type": anchor_type,
        "resume_from_timeout": resume_from_timeout,
        "timeout_next_play_type": resume_anchor.get("timeout_next_play_type") or source_doc.get("timeout_next_play_type") or game_doc.get("timeout_next_play_type"),
        "timeout_trace_id": resume_anchor.get("timeout_trace_id") or source_doc.get("timeout_trace_id") or game_doc.get("timeout_trace_id"),
    }
    logger.warning(
        "🧭 [MODE-RESUME-RETURN] game_id=%s status=%s type=%s quarter=%s clock=%s time_remaining=%s away_score=%s home_score=%s resume_from_timeout=%s next_play=%s",
        payload.get("game_id"),
        payload.get("status"),
        payload.get("anchor_type"),
        payload.get("quarter"),
        payload.get("clock"),
        payload.get("time_remaining"),
        payload.get("away_score"),
        payload.get("home_score"),
        payload.get("resume_from_timeout"),
        payload.get("timeout_next_play_type"),
    )
    logger.info(
        "[MGR-RESUME] command-center active_game_resume game_id=%s status=%s anchor_type=%s quarter=%s clock=%s away_score=%s home_score=%s next_play=%s",
        payload.get("game_id"),
        payload.get("status"),
        payload.get("anchor_type"),
        payload.get("quarter"),
        payload.get("clock"),
        payload.get("away_score"),
        payload.get("home_score"),
        payload.get("timeout_next_play_type"),
    )
    return payload


def _find_user_last_completed_game(franchise_doc: dict[str, Any], user_team_id_str: str) -> Optional[dict[str, Any]]:
    results = franchise_doc.get("results", {}) or {}
    current_week = int(franchise_doc.get("week", 1) or 1)
    for week in range(current_week - 1, 0, -1):
        for result in list(results.get(str(week), []) or []):
            away_id = str(result.get("away_id") or "")
            home_id = str(result.get("home_id") or "")
            if user_team_id_str in {away_id, home_id}:
                exact_query = {
                    "week": week,
                    "franchise_id": str(franchise_doc.get("_id")),
                    "$or": [
                        {"team1_id": away_id, "team2_id": home_id},
                        {"team1_id": home_id, "team2_id": away_id},
                    ],
                }
                game_docs = list(db.games.find(exact_query))
                logger.warning(
                    "🧭 [FCC-LAST-GAME] franchise_id=%s week=%s user_team_id=%s matchup=%s/%s matched_docs=%s",
                    str(franchise_doc.get("_id")),
                    week,
                    user_team_id_str,
                    away_id,
                    home_id,
                    len(game_docs),
                )
                if not game_docs:
                    fallback_docs = list(db.games.find({
                        "week": week,
                        "franchise_id": str(franchise_doc.get("_id")),
                    }))
                    target_ids = {away_id, home_id}
                    filtered_docs = []
                    for doc in fallback_docs:
                        candidate_ids = {
                            str(doc.get("team1_id") or ""),
                            str(doc.get("team2_id") or ""),
                            str(doc.get("home_team_id") or ""),
                            str(doc.get("away_team_id") or ""),
                        }
                        teams_obj = doc.get("teams") if isinstance(doc.get("teams"), dict) else {}
                        if isinstance(teams_obj, dict) and teams_obj:
                            candidate_ids.update(str(key or "") for key in teams_obj.keys())
                        candidate_ids.discard("")
                        if target_ids.issubset(candidate_ids):
                            filtered_docs.append(doc)
                    game_docs = filtered_docs
                    logger.warning(
                        "🧭 [FCC-LAST-GAME] fallback lookup franchise_id=%s week=%s scanned_docs=%s fallback_matches=%s",
                        str(franchise_doc.get("_id")),
                        week,
                        len(fallback_docs),
                        len(game_docs),
                    )
                for doc in game_docs:
                    teams_obj = doc.get("teams") if isinstance(doc.get("teams"), dict) else {}
                    logger.warning(
                        "🧭 [FCC-LAST-GAME] candidate_game_id=%s richness=%s quarter=%s is_final=%s has_players=%s top_box_score=%s nested_team_boxes=%s",
                        str(doc.get("_id") or doc.get("game_id") or ""),
                        _game_doc_richness_score(doc),
                        doc.get("quarter"),
                        doc.get("is_final"),
                        isinstance(doc.get("players"), list) and len(doc.get("players")) > 0,
                        isinstance(doc.get("box_score"), dict) and bool(doc.get("box_score")),
                        any(isinstance(team_data, dict) and isinstance(team_data.get("box_score"), dict) and bool(team_data.get("box_score")) for team_data in teams_obj.values()),
                    )
                game_doc = None
                if game_docs:
                    game_doc = max(game_docs, key=_game_doc_richness_score)
                    logger.warning(
                        "🧭 [FCC-LAST-GAME] selected_game_id=%s selected_richness=%s",
                        str(game_doc.get("_id") or game_doc.get("game_id") or ""),
                        _game_doc_richness_score(game_doc),
                    )
                return {
                    "week": week,
                    "away_team_id": away_id,
                    "home_team_id": home_id,
                    "away_score": int(result.get("away_score", 0) or 0),
                    "home_score": int(result.get("home_score", 0) or 0),
                    "game_id": str(game_doc.get("_id")) if game_doc and game_doc.get("_id") is not None else None,
                    "game_doc": game_doc,
                }
    return None


def _resolve_team_id_to_object_id(team_id: str):
    """Resolve team_id (canonical string e.g. MORRISTOWN, or ObjectId string) to ObjectId for FTD lookup. Returns None if not found."""
    import re
    if not team_id:
        return None
    try:
        oid = ObjectId(team_id)
        if db.teams.find_one({"_id": oid}, {"_id": 1}):
            return oid
    except Exception:
        pass
    doc = db.teams.find_one(
        {"$or": [{"team_id": team_id}, {"name": team_id}, {"code": team_id}]},
        {"_id": 1}
    )
    if doc:
        return doc["_id"]
    doc = db.teams.find_one(
        {"name": {"$regex": f"^{re.escape(team_id)}$", "$options": "i"}},
        {"_id": 1}
    )
    return doc["_id"] if doc else None

def _normalize_team_id_to_string(team_id):
    """Normalize team_id (ObjectId, ObjectId string, or team_id string) to canonical team_id string (e.g. 'LANCASTER').
    Returns None if team not found. Used to ensure team_attribute_changes keys match box score expectations."""
    if not team_id:
        return None
    # If already a team_id string (like "LANCASTER"), return as-is
    doc = db.teams.find_one({"team_id": team_id}, {"team_id": 1})
    if doc:
        return doc["team_id"]
    # Try as ObjectId (or ObjectId string)
    try:
        oid = ObjectId(team_id) if not isinstance(team_id, ObjectId) else team_id
        doc = db.teams.find_one({"_id": oid}, {"team_id": 1})
        if doc:
            return doc["team_id"]
    except Exception:
        pass
    # Try as name or code
    doc = db.teams.find_one(
        {"$or": [{"name": team_id}, {"code": team_id}]},
        {"team_id": 1}
    )
    if doc:
        return doc["team_id"]
    # Case-insensitive name match
    import re
    doc = db.teams.find_one(
        {"name": {"$regex": f"^{re.escape(str(team_id))}$", "$options": "i"}},
        {"team_id": 1}
    )
    return doc["team_id"] if doc else None


def _set_team_attribute_changes_on_game(game_id_str: str, tac: dict) -> bool:
    """
    $set team_attribute_changes on the game doc. Init-game stores _id as string;
    simulate-quarter may use ObjectId. Try string first, then ObjectId. Return True if matched.
    """
    r = db.games.update_one(
        {"_id": game_id_str},
        {"$set": {"team_attribute_changes": tac}}
    )
    if r.matched_count > 0:
        logger.warning(f"✅ [COMPLETE_WEEK] team_attribute_changes $set on game_id={game_id_str!r} (string _id) (keys={list(tac.keys())})")
        return True
    try:
        oid = ObjectId(game_id_str)
        r2 = db.games.update_one(
            {"_id": oid},
            {"$set": {"team_attribute_changes": tac}}
        )
        if r2.matched_count > 0:
            logger.warning(f"✅ [COMPLETE_WEEK] team_attribute_changes $set on game_id={game_id_str!r} (ObjectId _id) (keys={list(tac.keys())})")
            return True
    except Exception:
        pass
    logger.error(f"❌ [COMPLETE_WEEK] team_attribute_changes $set matched 0 docs for game_id={game_id_str!r} (tried string and ObjectId)")
    return False


def _finalize_team_attributes_for_game(
    game_id,
    franchise_id: ObjectId,
    home_team_id: str,
    away_team_id: str,
    winner_id: str,
    loser_id: str,
    winner_score: int,
    loser_score: int,
    week: int | None = None,
) -> None:
    """
    Run update_team_attributes_after_game once for this game and persist
    team_attribute_changes on the game doc so the box score can display them.
    game_id: string or ObjectId (game doc _id).
    """
    try:
        gid = game_id
        game_id_str = str(game_id) if not isinstance(game_id, str) else game_id
        if _postseason_eog_team_attrs_disabled_for_week(week):
            logger.warning(
                "🧊 [EOG-POSTSEASON-FREEZE] Skipping team attribute updates for game_id=%s week=%s; writing empty team_attribute_changes",
                str(game_id),
                str(week),
            )
            _set_team_attribute_changes_on_game(game_id_str, {})
            return
        logger.warning(
            "🧭 [EOG-CALL-SITE] About to call update_team_attributes_after_game game_id=%s gid=%s week=%s franchise_id=%s home=%s away=%s winner=%s loser=%s",
            str(game_id),
            str(gid),
            str(week),
            str(franchise_id),
            str(home_team_id),
            str(away_team_id),
            str(winner_id),
            str(loser_id),
        )
        attribute_changes = update_team_attributes_after_game(
            game_id=gid,
            franchise_id=franchise_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            winner_id=winner_id,
            loser_id=loser_id,
            winner_score=winner_score,
            loser_score=loser_score,
        )
        logger.warning(
            "🧭 [EOG-CALL-SITE] update_team_attributes_after_game returned game_id=%s has_changes=%s keys=%s",
            str(game_id),
            bool(attribute_changes),
            list((attribute_changes or {}).keys()),
        )
        tac = attribute_changes if attribute_changes else {}
        _set_team_attribute_changes_on_game(game_id_str, tac)
    except Exception as e:
        logger.error(f"❌ [FINALIZE-TEAM-ATTRS] Error for game_id={game_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())


def update_team_attributes_after_game(
    game_id: ObjectId,
    franchise_id: ObjectId,
    home_team_id: str,
    away_team_id: str,
    winner_id: str,
    loser_id: str,
    winner_score: int,
    loser_score: int
) -> dict:
    """
    Update team attributes based on game performance.
    Replaces the team attribute decay that was in the training system.
    
    Returns:
        dict: Attribute changes for each team, e.g.:
        {
            home_team_id: {"shot_threshold": +5, "discipline": +2, "fight": +1, ...},
            away_team_id: {"shot_threshold": +12, "discipline": -2, "fight": -2, ...}
        }
    """
    logger.warning(
        "🧪 [EOG-FUNC-ENTRY] update_team_attributes_after_game entered game_id=%s franchise_id=%s",
        str(game_id),
        str(franchise_id),
    )
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] FUNCTION CALLED")
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Input parameters - game_id={game_id}, franchise_id={franchise_id}")
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Team IDs - home_team_id={home_team_id} (type: {type(home_team_id)}), away_team_id={away_team_id} (type: {type(away_team_id)})")
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Winner/Loser - winner_id={winner_id} (type: {type(winner_id)}), loser_id={loser_id} (type: {type(loser_id)})")
    import random
    
    # Load game document to get stats.
    # Some historical paths created duplicate docs for the same logical game:
    # one with string _id (canonical gameplay snapshot), one with ObjectId _id
    # (partial/upsert metadata only). We pick the richer snapshot.
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Loading game document")
    game_id_str = str(game_id)
    candidate_docs: list[tuple[str, dict]] = []
    try:
        doc_str = db.games.find_one({"_id": game_id_str})
        if doc_str:
            candidate_docs.append(("string", doc_str))
    except Exception:
        pass
    try:
        if ObjectId.is_valid(game_id_str):
            game_oid = ObjectId(game_id_str)
            doc_oid = db.games.find_one({"_id": game_oid})
            if doc_oid:
                candidate_docs.append(("objectid", doc_oid))
    except Exception:
        pass

    if not candidate_docs:
        logger.error(f"❌ [UPDATE-TEAM-ATTRS] Game {game_id} not found (tried string and ObjectId)")
        return {}

    selected_kind, game_doc = max(
        candidate_docs,
        key=lambda pair: _game_doc_richness_score(pair[1]),
    )
    logger.warning(
        "🧭 [EOG-GAME-DOC-SELECT] game_id=%s selected=%s score=%s candidates=%s",
        game_id_str,
        selected_kind,
        _game_doc_richness_score(game_doc),
        [
            {"kind": kind, "score": _game_doc_richness_score(doc), "_id": str(doc.get("_id"))}
            for kind, doc in candidate_docs
        ],
    )
    
    # Get teams object for name fallback only
    teams_obj = game_doc.get("teams", {})
    
    # Resolve canonical team IDs for EOG source lookup.
    # We prefer IDs stored on the game doc, then fall back to endpoint inputs.
    game_home_team_id = _normalize_team_id_to_string(game_doc.get("home_team_id"))
    game_away_team_id = _normalize_team_id_to_string(game_doc.get("away_team_id"))
    input_home_team_id = _normalize_team_id_to_string(home_team_id)
    input_away_team_id = _normalize_team_id_to_string(away_team_id)

    canonical_home_team_id = game_home_team_id or input_home_team_id or home_team_id
    canonical_away_team_id = game_away_team_id or input_away_team_id or away_team_id

    # Build a single canonical EOG snapshot and persist it on the game document.
    # EOG team-attribute logic reads only from this snapshot to avoid source drift.
    eog_inputs = build_eog_inputs_from_game_doc(
        game_doc, canonical_home_team_id, canonical_away_team_id
    )
    db.games.update_one(
        {"_id": game_doc.get("_id")},
        {"$set": {"eog_inputs": eog_inputs}},
    )

    home_team_name = eog_inputs.get("home", {}).get("team_name", canonical_home_team_id)
    away_team_name = eog_inputs.get("away", {}).get("team_name", canonical_away_team_id)
    home_totals = eog_inputs.get("home", {}).get("totals", {})
    away_totals = eog_inputs.get("away", {}).get("totals", {})
    home_scouting = eog_inputs.get("home", {}).get("scouting", {})
    away_scouting = eog_inputs.get("away", {}).get("scouting", {})
    is_distant_sim = (game_doc.get("simulation_engine") == "distant")

    logger.info(
        "🔍 [UPDATE-TEAM-ATTRS] EOG canonical snapshot source=%s home=%s[%s] (fb_rate=%.1f, pt_rate=%.1f, pt_attempts=%s) away=%s[%s] (fb_rate=%.1f, pt_rate=%.1f, pt_attempts=%s)",
        eog_inputs.get("source", "unknown"),
        home_team_name,
        canonical_home_team_id,
        home_scouting.get("fb_rate", 0),
        home_scouting.get("pt_combined_rate", 0),
        home_scouting.get("pt_total_attempts", 0),
        away_team_name,
        canonical_away_team_id,
        away_scouting.get("fb_rate", 0),
        away_scouting.get("pt_combined_rate", 0),
        away_scouting.get("pt_total_attempts", 0),
    )
    logger.warning(
        "🧪 [EOG-SNAPSHOT-SOURCES] game_id=%s home_totals_source=%s home_scouting_source=%s away_totals_source=%s away_scouting_source=%s",
        str(game_doc.get("_id")),
        eog_inputs.get("home", {}).get("totals_source", "unknown"),
        eog_inputs.get("home", {}).get("scouting_source", "unknown"),
        eog_inputs.get("away", {}).get("totals_source", "unknown"),
        eog_inputs.get("away", {}).get("scouting_source", "unknown"),
    )
    logger.info(
        "🧪 [EOG-INPUTS-DEBUG] game_id=%s eog_inputs=%s",
        str(game_doc.get("_id")),
        eog_inputs,
    )

    def _resolve_game_team_obj(team_id_label: str, team_name: str) -> dict:
        if not isinstance(teams_obj, dict):
            return {}
        candidates = [
            team_id_label,
            team_name,
            str(team_name).replace("-", "_").replace(" ", "_").upper() if team_name else None,
        ]
        for key in candidates:
            if key and isinstance(teams_obj.get(key), dict):
                return teams_obj.get(key, {})
        lowered = {str(k).lower(): v for k, v in teams_obj.items()}
        for key in candidates:
            if key:
                val = lowered.get(str(key).lower())
                if isinstance(val, dict):
                    return val
        return {}

    def _stat_bucket(entry: Any) -> dict:
        if not isinstance(entry, dict):
            return {}
        game_stats = entry.get("game_stats")
        if isinstance(game_stats, dict):
            return game_stats
        season_stats = entry.get("season_stats")
        if isinstance(season_stats, dict):
            return season_stats
        return entry

    def _max_share_from_counts(counts: list[int]) -> float:
        positive_counts = [int(count) for count in counts if int(count) > 0]
        if not positive_counts:
            return 0.0
        total = sum(positive_counts)
        return max(positive_counts) / total if total > 0 else 0.0

    def _offensive_play_usage(team_obj: dict) -> int:
        total = 0
        for _play_key, play_data, _display_name in iter_team_plays(team_obj.get("plays", {})):
            total += int((play_data.get("game_stats", {}) or {}).get("times_run", 0) or 0)
        return total

    def _defensive_play_max_share(team_obj: dict) -> float:
        defense = (team_obj.get("scouting", {}) or {}).get("defense", {}) or {}
        from BackEnd.utils.defense_identity import CANONICAL_HCO_DEFENSE_ROW_KEYS

        counts = [
            int((_stat_bucket(defense.get(key, {}))).get("used", 0) or 0)
            for key in CANONICAL_HCO_DEFENSE_ROW_KEYS
        ]
        return _max_share_from_counts(counts)

    def _fast_break_usage(team_obj: dict) -> tuple[int, float]:
        offense = (team_obj.get("scouting", {}) or {}).get("offense", {}) or {}
        fb_plays = offense.get("fast_break_plays", {}) or {}
        counts = [
            int((fb_plays.get(key, {}) or {}).get("A", 0) or 0)
            for key in ("covert_release", "rim_runner", "triangle", "after_steal")
        ]
        return sum(counts), _max_share_from_counts(counts)

    home_team_obj = _resolve_game_team_obj(canonical_home_team_id, home_team_name)
    away_team_obj = _resolve_game_team_obj(canonical_away_team_id, away_team_name)
    
    # Calculate attribute changes for each team. team_object_id = ObjectId for FTD; team_id_label = string for logging.
    def calculate_attr_changes(
        team_object_id,
        team_id_label,
        is_winner,
        team_totals,
        opponent_totals,
        team_scouting,
        opponent_scouting,
        team_obj,
        opponent_team_obj,
    ):
        """Calculate attribute changes for a team."""
        changes = {}
        
        # Calculate FG%
        fgm = team_totals.get("FGM", 0)
        fga = team_totals.get("FGA", 0)
        fg_pct = (fgm / fga * 100) if fga > 0 else 0
        
        # Calculate TREB
        treb = team_totals.get("DREB", 0) + team_totals.get("OREB", 0)
        opp_treb = opponent_totals.get("DREB", 0) + opponent_totals.get("OREB", 0)
        offensive_play_count = _offensive_play_usage(team_obj)
        defensive_max_share = _defensive_play_max_share(team_obj)
        _team_fb_total, team_fb_max_share = _fast_break_usage(team_obj)
        opponent_fb_total, _ = _fast_break_usage(opponent_team_obj)
        team_pt_total = int(team_scouting.get("pt_total_attempts", 0) or 0)
        opponent_pt_total = int(opponent_scouting.get("pt_total_attempts", 0) or 0)
        
        # ✅ FTD: Get current team attributes from FTD collection (keyed by ObjectId)
        ftd_doc = franchise_team_data_collection.find_one(
            {"franchise_id": franchise_id, "team_id": team_object_id},
            {"team_attributes": 1}
        )
        if not ftd_doc:
            logger.error(f"❌ [UPDATE-TEAM-ATTRS] FTD not found for franchise={franchise_id}, team={team_id_label}")
            return {}
        
        team_attrs = ftd_doc.get("team_attributes", {})

        logger.warning(
            "🧪 [EOG-TEAM-INPUTS] team=%s winner=%s totals=%s opp_totals=%s scouting=%s opp_scouting=%s",
            str(team_id_label),
            bool(is_winner),
            {
                "FGM": team_totals.get("FGM", 0),
                "FGA": team_totals.get("FGA", 0),
                "TO": team_totals.get("TO", 0),
                "STL": team_totals.get("STL", 0),
                "DREB": team_totals.get("DREB", 0),
                "OREB": team_totals.get("OREB", 0),
            },
            {
                "FGM": opponent_totals.get("FGM", 0),
                "FGA": opponent_totals.get("FGA", 0),
                "TO": opponent_totals.get("TO", 0),
                "STL": opponent_totals.get("STL", 0),
                "DREB": opponent_totals.get("DREB", 0),
                "OREB": opponent_totals.get("OREB", 0),
            },
            {
                "fb_rate": team_scouting.get("fb_rate", 0),
                "fb_entries": team_scouting.get("fb_entries", 0),
                "fb_success": team_scouting.get("fb_success", 0),
                "pt_rate": team_scouting.get("pt_combined_rate", 0),
                "pt_attempts": team_scouting.get("pt_total_attempts", 0),
                "pt_success": team_scouting.get("pt_total_successes", 0),
                "hct_used": team_scouting.get("hct_used", 0),
                "hct_success": team_scouting.get("hct_success", 0),
                "fcp_used": team_scouting.get("fcp_used", 0),
                "fcp_success": team_scouting.get("fcp_success", 0),
            },
            {
                "fb_rate": opponent_scouting.get("fb_rate", 0),
                "fb_entries": opponent_scouting.get("fb_entries", 0),
                "fb_success": opponent_scouting.get("fb_success", 0),
                "pt_rate": opponent_scouting.get("pt_combined_rate", 0),
                "pt_attempts": opponent_scouting.get("pt_total_attempts", 0),
                "pt_success": opponent_scouting.get("pt_total_successes", 0),
                "hct_used": opponent_scouting.get("hct_used", 0),
                "hct_success": opponent_scouting.get("hct_success", 0),
                "fcp_used": opponent_scouting.get("fcp_used", 0),
                "fcp_success": opponent_scouting.get("fcp_success", 0),
            },
        )
        
        # shot_threshold is a golf score: lower is better, higher is worse.
        if fg_pct > 50:
            changes["shot_threshold"] = random.randint(-10, -5)
        elif fg_pct > 45:
            if is_winner:
                changes["shot_threshold"] = random.randint(-5, 0)
            else:
                changes["shot_threshold"] = random.randint(0, 5)
        else:
            changes["shot_threshold"] = random.randint(5, 10)
        
        team_f_plus_to = team_totals.get("F", 0) + team_totals.get("TO", 0)
        opp_f_plus_to_with_buffer = opponent_totals.get("F", 0) + opponent_totals.get("TO", 0) + 8
        if team_f_plus_to < opp_f_plus_to_with_buffer:
            changes["discipline"] = random.randint(1, 2)
        elif team_f_plus_to > opp_f_plus_to_with_buffer:
            changes["discipline"] = random.randint(-3, -2)
        else:
            changes["discipline"] = random.randint(-1, 0)
        
        # fight: winning 0..+2, losing −3..−1
        if is_winner:
            changes["fight"] = random.randint(0, 2)
        else:
            changes["fight"] = random.randint(-3, -1)
        
        # rebound_modifier
        if treb > (opp_treb + 8):
            changes["rebound_modifier"] = random.randint(0, 5) / 100.0
        elif treb < (opp_treb - 8):
            changes["rebound_modifier"] = -random.randint(5, 10) / 100.0
        else:
            changes["rebound_modifier"] = -random.randint(1, 5) / 100.0
        
        if is_distant_sim:
            changes["offensive_efficiency"] = random.randint(-2, 1)
            changes["defensive_efficiency"] = random.randint(-2, 1)
            changes["fb_efficiency"] = random.randint(-2, 1)
            changes["fb_opp_modifier"] = random.randint(-2, 1)
            changes["pt_efficiency"] = random.randint(-2, 1)
            changes["pt_opp_modifier"] = random.randint(-2, 1)
            logger.warning(
                "🧪 [EOG-DISTANT-ATTRS] team=%s off_eff=%s def_eff=%s fb_eff=%s fb_opp=%s pt_eff=%s pt_opp=%s",
                str(team_id_label),
                changes.get("offensive_efficiency"),
                changes.get("defensive_efficiency"),
                changes.get("fb_efficiency"),
                changes.get("fb_opp_modifier"),
                changes.get("pt_efficiency"),
                changes.get("pt_opp_modifier"),
            )
        else:
            if offensive_play_count > 12:
                changes["offensive_efficiency"] = random.randint(0, 1)
            elif offensive_play_count > 7:
                changes["offensive_efficiency"] = random.randint(-2, -1)
            else:
                changes["offensive_efficiency"] = random.randint(-3, -2)

            if defensive_max_share <= 0.39:
                changes["defensive_efficiency"] = random.randint(0, 1)
            elif defensive_max_share <= 0.49:
                changes["defensive_efficiency"] = random.randint(-2, -1)
            else:
                changes["defensive_efficiency"] = random.randint(-3, -2)

            if team_fb_max_share > 0.60:
                changes["fb_efficiency"] = random.randint(-3, -2)
            elif team_fb_max_share > 0.50:
                changes["fb_efficiency"] = random.randint(-2, -1)
            else:
                changes["fb_efficiency"] = random.randint(-1, 1)

            if opponent_fb_total > 15:
                changes["fb_opp_modifier"] = random.randint(-3, -2)
            elif opponent_fb_total > 10:
                changes["fb_opp_modifier"] = random.randint(-2, -1)
            else:
                changes["fb_opp_modifier"] = random.randint(0, 1)

            if team_pt_total > 20:
                changes["pt_efficiency"] = random.randint(-3, -1)
            elif team_pt_total > 16:
                changes["pt_efficiency"] = random.randint(-2, -1)
            elif team_pt_total <= 12:
                changes["pt_efficiency"] = random.randint(0, 1)
            else:
                # 13–16 attempts (between ≤12 and >16 bands in EOG doc).
                changes["pt_efficiency"] = random.randint(0, 1)

            if opponent_pt_total > 16:
                changes["pt_opp_modifier"] = random.randint(-3, -2)
            elif opponent_pt_total > 12:
                changes["pt_opp_modifier"] = random.randint(-2, -1)
            else:
                changes["pt_opp_modifier"] = random.randint(0, 1)
        
        # team_chemistry
        score_delta = winner_score - loser_score
        if is_winner:
            if score_delta < 4:
                changes["team_chemistry"] = random.randint(1, 2)
            elif score_delta < 10:
                changes["team_chemistry"] = random.randint(1, 3)
            else:
                changes["team_chemistry"] = random.randint(2, 4)
        else:
            if score_delta < 4:
                changes["team_chemistry"] = random.randint(-2, -1)
            elif score_delta < 10:
                changes["team_chemistry"] = random.randint(-3, -2)
            else:
                changes["team_chemistry"] = random.randint(-5, -3)

        # Apply changes and clamp to valid ranges
        ftd_update = {}
        for attr_name, change in changes.items():
            if attr_name in TEAM_ATTR_CLAMPS:
                current_val = team_attrs.get(attr_name, 0)
                new_val = current_val + change
                lower, upper = TEAM_ATTR_CLAMPS[attr_name]
                clamped_val = max(lower, min(upper, new_val))
                ftd_update[f"team_attributes.{attr_name}"] = clamped_val
                # Store the actual change (may be different if clamped)
                changes[attr_name] = clamped_val - current_val
                logger.warning(
                    "🧪 [EOG-APPLY] team=%s attr=%s current=%s raw_change=%s unclamped=%s clamped=%s applied_change=%s",
                    str(team_id_label),
                    attr_name,
                    current_val,
                    change,
                    new_val,
                    clamped_val,
                    changes[attr_name],
                )
        
        # ✅ FTD: Update FTD collection instead of franchise document
        if ftd_update:
            franchise_team_data_collection.update_one(
                {"franchise_id": franchise_id, "team_id": team_object_id},
                {"$set": ftd_update}
            )
            logger.info(f"✅ [UPDATE-TEAM-ATTRS] Updated {len(ftd_update)} attributes for team {team_id_label} in FTD")
        
        return changes
    
    # Resolve team_id strings (e.g. MORRISTOWN, XAVIEN) to ObjectIds for FTD lookup. Keep original strings for result keys.
    home_oid = _resolve_team_id_to_object_id(home_team_id)
    away_oid = _resolve_team_id_to_object_id(away_team_id)
    if not home_oid:
        logger.error(f"❌ [UPDATE-TEAM-ATTRS] Could not resolve home_team_id to ObjectId: {home_team_id}")
    if not away_oid:
        logger.error(f"❌ [UPDATE-TEAM-ATTRS] Could not resolve away_team_id to ObjectId: {away_team_id}")
    
    home_is_winner = (home_team_id == winner_id)
    away_is_winner = (away_team_id == winner_id)
    
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Calculating changes - home_team_id={home_team_id}, away_team_id={away_team_id}, winner_id={winner_id}")
    
    home_changes = calculate_attr_changes(
        home_oid, home_team_id, home_is_winner, home_totals, away_totals,
        home_scouting, away_scouting, home_team_obj, away_team_obj
    ) if home_oid else {}
    away_changes = calculate_attr_changes(
        away_oid, away_team_id, away_is_winner, away_totals, home_totals,
        away_scouting, home_scouting, away_team_obj, home_team_obj
    ) if away_oid else {}

    def _persist_eog_offensive_play_effectiveness_decay(team_oid: ObjectId | None, team_plays: Any) -> None:
        """Reduce FTD play CMD from this game's offensive playcall mix (EOG team-attributes pass)."""
        if not team_oid:
            return
        gp = team_plays if isinstance(team_plays, dict) else {}
        ftd = franchise_team_data_collection.find_one(
            {"franchise_id": franchise_id, "team_id": team_oid},
            {"plays": 1},
        )
        if not ftd:
            return
        set_doc = build_eog_offensive_play_effectiveness_decay_ftd_updates(gp, ftd.get("plays") or {})
        if set_doc:
            franchise_team_data_collection.update_one(
                {"franchise_id": franchise_id, "team_id": team_oid},
                {"$set": set_doc},
            )

    _persist_eog_offensive_play_effectiveness_decay(home_oid, home_team_obj.get("plays"))
    _persist_eog_offensive_play_effectiveness_decay(away_oid, away_team_obj.get("plays"))

    def _persist_eog_defensive_effectiveness_decay(team_oid: ObjectId | None, team_scouting: Any) -> None:
        """Reduce FTD defense row effectiveness from this game's defensive playcall mix (EOG pass)."""
        if not team_oid:
            return
        ts = team_scouting if isinstance(team_scouting, dict) else {}
        ftd = franchise_team_data_collection.find_one(
            {"franchise_id": franchise_id, "team_id": team_oid},
            {"scouting_data": 1},
        )
        if not ftd:
            return
        sd = ftd.get("scouting_data") or {}
        set_doc = build_eog_defensive_effectiveness_decay_ftd_updates(ts, sd)
        if set_doc:
            franchise_team_data_collection.update_one(
                {"franchise_id": franchise_id, "team_id": team_oid},
                {"$set": set_doc},
            )

    _persist_eog_defensive_effectiveness_decay(home_oid, home_team_obj.get("scouting"))
    _persist_eog_defensive_effectiveness_decay(away_oid, away_team_obj.get("scouting"))

    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Calculated changes - home_changes keys: {list(home_changes.keys())}, away_changes keys: {list(away_changes.keys())}")
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Home changes sample: {dict(list(home_changes.items())[:3]) if home_changes else 'None'}")
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Away changes sample: {dict(list(away_changes.items())[:3]) if away_changes else 'None'}")
    
    result = {
        home_team_id: home_changes,
        away_team_id: away_changes
    }
    
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Returning result with keys: {list(result.keys())}")
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Result key types - home_team_id key type: {type(list(result.keys())[0]) if result.keys() else 'None'}")
    logger.info(f"🔍 [UPDATE-TEAM-ATTRS] Result structure: {result}")
    
    return result


def get_user_team_from_franchise(franchise_doc: dict) -> tuple[str | None, str | None]:
    """
    Get user team identifiers from franchise document with backward compatibility.
    
    Returns:
        tuple: (user_team_id: team name, user_team_object_id: ObjectId string)
        Falls back to franchise_state_collection if not found in franchise document.
    """
    # Try franchise document first (new approach)
    user_team_id = franchise_doc.get("user_team_id")
    user_team_object_id = franchise_doc.get("user_team_object_id")
    
    if user_team_id and user_team_object_id:
        return (user_team_id, user_team_object_id)
    
    # Fallback to state collection (backward compatibility for old franchises)
    # Note: This is deprecated - new franchises should use franchise document fields
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        team_name = state.get("team")
        if team_name:
            logger.warning(f"⚠️ [DEPRECATED] Using franchise_state fallback for team: {team_name}. "
                         f"Franchise should have user_team_id and user_team_object_id in document.")
            team_doc = db.teams.find_one({"name": team_name})
            if team_doc:
                return (team_name, str(team_doc["_id"]))
    except Exception as e:
        logger.debug(f"franchise_state collection not available (expected for new franchises): {e}")
    
    return (None, None)


def generate_random_training_allocations(total_points: int) -> dict:
    """
    Generate random training allocations similar to auto-train logic.
    
    Logic:
    - Set all 20 sliders to 1 (20 points)
    - Randomly pick (total_points - 20) sliders to set to 2
    
    Args:
        total_points: Total training points (30 for first training, 24 otherwise)
    
    Returns:
        Dict with player_drills, team_drills, general structure
    """
    # Initialize all to 1
    allocations = {
        "player_drills": {
            "offense": {"inside": 1, "outside": 1},
            "defense": {"inside": 1, "outside": 1},
            "technical": {"passing": 1, "ball_handling": 1, "rebounding": 1},
            "weight_room": {"strength": 1, "agility": 1}
        },
        "team_drills": {
            "team_offense": {"install": 1},
            "team_defense": {"install": 1},
            "fast_breaks": {"offense_install": 1, "defense_install": 1},
            "scrimmages": 1,
            "presses_traps": {"defense_install": 1, "offense_install": 1}
        },
        "general": {
            "conditioning": 1,
            "free_throws": 1,
            "film_study": 1,
            "breaks": 1
        }
    }
    
    # Define all 20 sliders for random selection
    sliders = [
        # Player Drills (9 sliders)
        ("player_drills", "offense", "inside"),
        ("player_drills", "offense", "outside"),
        ("player_drills", "defense", "inside"),
        ("player_drills", "defense", "outside"),
        ("player_drills", "technical", "passing"),
        ("player_drills", "technical", "ball_handling"),
        ("player_drills", "technical", "rebounding"),
        ("player_drills", "weight_room", "strength"),
        ("player_drills", "weight_room", "agility"),
        # Team Drills (7 sliders)
        ("team_drills", "team_offense", "install"),
        ("team_drills", "team_defense", "install"),
        ("team_drills", "fast_breaks", "offense_install"),
        ("team_drills", "fast_breaks", "defense_install"),
        ("team_drills", "scrimmages", None),
        ("team_drills", "presses_traps", "defense_install"),
        ("team_drills", "presses_traps", "offense_install"),
        # General (4 sliders)
        ("general", None, "conditioning"),
        ("general", None, "free_throws"),
        ("general", None, "film_study"),
        ("general", None, "breaks"),
    ]
    
    # Randomly pick (total_points - 20) sliders to set to 2
    remaining_points = total_points - 20
    shuffled = sliders.copy()
    random.shuffle(shuffled)
    
    for i in range(min(remaining_points, len(shuffled))):
        category, subcategory, key = shuffled[i]
        
        if category == "player_drills":
            allocations[category][subcategory][key] = 2
        elif category == "team_drills":
            if subcategory == "scrimmages":
                allocations[category][subcategory] = 2
            else:
                allocations[category][subcategory][key] = 2
        elif category == "general":
            allocations[category][key] = 2
    
    return allocations


def generate_random_coaching_focus() -> str:
    """
    Randomly select a coaching focus from all available options.
    
    Returns:
        String value matching the radio button value (e.g., "authoritarian-discipline")
    """
    coaching_focus_options = [
        "authoritarian",
        "authoritarian-discipline",
        "authoritarian-rebounding",
        "authoritarian-execution",
        "authoritarian-teamwork",  # UI "Teamwork" (Authoritarian); differs from Culture `culture-builder-teamwork`
        "systems-coach",
        "systems-coach-offense",
        "systems-coach-defense",
        "systems-coach-fast-breaks",
        "systems-coach-press-trap",
        "player-maximizer",
        "player-maximizer-top-3",
        "player-maximizer-attributes-4-6",
        "player-maximizer-positional-focus",
        "culture-builder",
        "culture-builder-inspire",
        "culture-builder-community",
        "culture-builder-teamwork",  # UI "Team Building"; not Authoritarian "Teamwork"
        "culture-builder-confidence",
    ]
    
    return random.choice(coaching_focus_options)


@router.get("/court.html")
def serve_court_html():
    """Return the court page so query params work in production."""
    return FileResponse(STATIC_DIR / "court.html")

# @router.get("/franchise/start")
# def franchise_start():
#     state = franchise_state_collection.find_one({"_id": "state"}) or {}
#     if not state.get("team"):
#         return RedirectResponse(url="/franchise/select-team")
#     return RedirectResponse(url="/franchise/command-center")
@router.get("/franchise/start")
def franchise_start():
    return RedirectResponse(url="/franchise/select-team")


@router.get("/franchise/select-team")
def get_select_team_page():
    return FileResponse(STATIC_DIR / "franchise-select-team.html")

class TeamSelection(BaseModel):
    team_name: str

class PlayGameRequest(BaseModel):
    franchise_id: str


class FranchiseResultRequest(BaseModel):
    franchise_id: str
    game_id: str
    winner: str


class GameResult(BaseModel):
    team1_id: str
    team2_id: str
    team1_score: int
    team2_score: int


class CompleteWeekRequest(BaseModel):
    franchise_id: str
    week: int
    result: GameResult
    game_id: str | None = None  # Optional: actual gameplay game_id (ObjectId format)
    game_document: dict | None = None  # Optional: complete game document from simulate-quarter (eliminates race condition)


class CompleteWeekPhaseBRequest(BaseModel):
    franchise_id: str
    week: int


class CompleteWeekStartCpuSimsRequest(BaseModel):
    """Start simming non-user CPU games for a week before phase A (e.g. first Play Quarter)."""

    franchise_id: str
    week: int


class SaveRecruitingOrdersRequest(BaseModel):
    franchise_id: str
    recruit_ids: list[str] | None = None
    order_entries: list[dict[str, Any]] | None = None


class RunWeek35RecruitingRequest(BaseModel):
    franchise_id: str


class CutPlayersRequest(BaseModel):
    franchise_id: str
    player_ids: list[str]


MAX_RECRUITING_ORDER_SLOTS = 20


def _normalize_team_id(team_id: str):
    try:
        return ObjectId(team_id)
    except Exception:
        doc = db.teams.find_one(
            {"$or": [{"_id": team_id}, {"name": team_id}, {"code": team_id}, {"team_id": team_id}]}
        )
        if not doc:
            # Fallback: canonical key (e.g. LANCASTER, SOUTH_LANCASTER, BENTLEY_TRUMAN)
            # -> resolve via team name variants ("Lancaster", "South Lancaster", "Bentley-Truman").
            # Frontend may send canonical ids from game doc when URL params are missing (e.g. Play Quarter).
            canonical_base = str(team_id or "").strip()
            candidate_names = []
            if canonical_base:
                candidate_names.extend([
                    canonical_base.replace("_", " ").title(),
                    canonical_base.replace("_", "-").title(),
                ])
            seen = set()
            candidate_names = [name for name in candidate_names if name and not (name in seen or seen.add(name))]
            if candidate_names:
                doc = db.teams.find_one({"name": {"$in": candidate_names}})
        if not doc:
            raise HTTPException(status_code=400, detail=f"Unknown team id {team_id}")
        return doc["_id"]


def _save_game_result(team1_id, team2_id, team1_score, team2_score, week, franchise_id=None, game_id=None):
    """
    Save or update game result in games collection.
    
    ✅ FIX: This function no longer updates the universal teams collection.
    Franchise mode stores W/L and PF/PA in franchise.results, which is calculated
    when displaying team stats. This ensures franchise stats are isolated from
    other game modes and franchise instances.
    
    Args:
        team1_id: Team 1 ObjectId
        team2_id: Team 2 ObjectId
        team1_score: Team 1 score
        team2_score: Team 2 score
        week: Week number
        franchise_id: Optional franchise ID
        game_id: Optional game_id (ObjectId format). If provided, updates that specific game document.
                 If None, uses legacy lookup by week + team IDs.
    
    Returns:
        Dictionary with team IDs and scores
    """
    # ✅ SS&S: If game_id is provided, use it directly (this is the actual gameplay document)
    if game_id:
        try:
            game_id_str = str(game_id)
            existing = db.games.find_one({"_id": game_id_str})
            if existing:
                filter_doc = {"_id": game_id_str}
            else:
                # Try ObjectId only for existing legacy docs; if not found, upsert string _id.
                existing_oid = None
                if ObjectId.is_valid(game_id_str):
                    game_oid = ObjectId(game_id_str)
                    existing_oid = db.games.find_one({"_id": game_oid})
                if existing_oid:
                    filter_doc = {"_id": game_oid}
                else:
                    filter_doc = {"_id": game_id_str}
        except Exception as e:
            logger.warning(f"⚠️ [_SAVE_GAME_RESULT] Invalid game_id format: {game_id}, error: {e}. Falling back to legacy lookup.")
            game_id = None  # Fall through to legacy logic
    
    # Legacy lookup (when game_id not provided or invalid)
    if not game_id:
        lookup_doc = {
            "week": week,
            "$or": [
                {"team1_id": team1_id, "team2_id": team2_id},
                {"team1_id": team2_id, "team2_id": team1_id},
            ],
        }
        if franchise_id:
            lookup_doc["franchise_id"] = str(franchise_id)
        existing = db.games.find_one(lookup_doc)

        if existing:
            filter_doc = {"_id": existing["_id"]}
        else:
            filter_doc = {"week": week, "team1_id": team1_id, "team2_id": team2_id}

    update_fields = {
        "team1_id": team1_id,
        "team2_id": team2_id,
        "team1_score": team1_score,
        "team2_score": team2_score,
        "week": week,
    }
    
    if franchise_id:
        update_fields["franchise_id"] = str(franchise_id)

    db.games.update_one(
        filter_doc,
        {"$set": update_fields},
        upsert=True,
    )

    return {
        "team1_id": str(team1_id),
        "team2_id": str(team2_id),
        "team1_score": team1_score,
        "team2_score": team2_score,
    }


def _persist_franchise_user_game_snapshot(
    *,
    game_id: str,
    payload: dict,
    franchise_id: str,
    week: int,
    away_id: Any = None,
    home_id: Any = None,
) -> str:
    """
    Persist the final user-game snapshot on the canonical games _id.

    Avoids string/ObjectId duplicate game docs (which bypass applied_games and
    double-apply FPD season stats) and purges other week/matchup duplicates.
    """
    incoming_set = {k: v for k, v in payload.items() if k != "_id"}
    incoming_set["franchise_id"] = str(franchise_id)
    incoming_set["week"] = week

    write_id = resolve_game_write_id(games_collection, str(game_id))
    games_collection.update_one({"_id": write_id}, {"$set": incoming_set}, upsert=True)
    purge_game_id_format_duplicates(games_collection, str(game_id), keep_id=write_id)

    keep_ids: list[Any] = [write_id, str(write_id)]
    if isinstance(write_id, ObjectId):
        keep_ids.append(str(write_id))
    if ObjectId.is_valid(str(game_id)):
        try:
            keep_ids.append(ObjectId(str(game_id)))
        except Exception:
            pass

    if away_id and home_id:
        games_collection.delete_many(
            {
                "franchise_id": str(franchise_id),
                "week": week,
                "$or": [
                    {"team1_id": away_id, "team2_id": home_id},
                    {"team1_id": home_id, "team2_id": away_id},
                ],
                "_id": {"$nin": keep_ids},
            }
        )
    return str(write_id)


def _resolve_team_name_from_any(team_ref) -> str | None:
    if not team_ref:
        return None
    doc = db.teams.find_one(
        {"$or": [{"team_id": str(team_ref)}, {"name": str(team_ref)}, {"code": str(team_ref)}]},
        {"name": 1},
    )
    if doc and doc.get("name"):
        return str(doc["name"])
    try:
        oid = ObjectId(team_ref) if not isinstance(team_ref, ObjectId) else team_ref
        doc = db.teams.find_one({"_id": oid}, {"name": 1})
        if doc and doc.get("name"):
            return str(doc["name"])
    except Exception:
        pass
    return str(team_ref)


def _build_franchise_game_inbox_entry(
    *,
    franchise_id: str,
    user_team_name: str | None,
    user_team_object_id: str | None,
    game_id: str | None,
    home_team_id: str | None,
    away_team_id: str | None,
    home_team_name: str | None,
    away_team_name: str | None,
    home_score: int,
    away_score: int,
    week: int,
) -> dict | None:
    if not franchise_id or not user_team_name or not user_team_object_id or not game_id:
        return None

    resolved_home_name = home_team_name or _resolve_team_name_from_any(home_team_id)
    resolved_away_name = away_team_name or _resolve_team_name_from_any(away_team_id)
    if not resolved_home_name or not resolved_away_name:
        return None

    user_is_home = str(user_team_name) == str(resolved_home_name)
    user_is_away = str(user_team_name) == str(resolved_away_name)
    if not user_is_home and not user_is_away:
        return None

    user_score = int(home_score if user_is_home else away_score)
    opponent_score = int(away_score if user_is_home else home_score)
    opponent_team_name = resolved_away_name if user_is_home else resolved_home_name
    result = "win" if user_score > opponent_score else "loss"
    verb = "defeated" if result == "win" else "lost to"
    my_team = "home" if user_is_home else "away"
    box_score_params = urlencode({
        "game_id": str(game_id),
        "mode": "franchise",
        "franchise_id": str(franchise_id),
        "team_id": str(user_team_object_id),
        "my_team": my_team,
        "home": resolved_home_name,
        "away": resolved_away_name,
    })

    return {
        "type": "game_result",
        "week": int(week),
        "game_id": str(game_id),
        "result": result,
        "user_team_name": str(user_team_name),
        "opponent_team_name": str(opponent_team_name),
        "user_score": user_score,
        "opponent_score": opponent_score,
        "copy": f"Week #{int(week)}: {user_team_name} {verb} {opponent_team_name} {user_score}-{opponent_score}",
        "box_score_url": f"/box-score.html?{box_score_params}",
        "created_at": datetime.utcnow().isoformat(),
    }


def _distant_sim_home_team_chemistry_bonus(home_ftd: dict) -> int:
    """Home win-roll bonus: 2 × team_chemistry from FTD team_attributes (Distant_Game_Sim_System.md)."""
    from BackEnd.distant_sim_engine import distant_sim_home_chemistry_bonus

    raw = (home_ftd.get("team_attributes") or {}).get("team_chemistry")
    return distant_sim_home_chemistry_bonus(raw)


def _distant_sim_regular_season_standings(
    franchise_doc: dict[str, Any],
    team_ids_map: dict[str, Any],
) -> dict[str, dict[str, int]]:
    """
    W/L/PF/PA from franchise.results for regular season weeks only (same slice as standings W/L
    when postseason rows live under higher week keys). Uses calculate_franchise_standings.
    """
    from BackEnd.utils.franchise_standings import calculate_franchise_standings

    rs_slice: dict[str, Any] = {}
    for wk, games in (franchise_doc.get("results") or {}).items():
        try:
            wi = int(wk)
        except (TypeError, ValueError):
            continue
        if 1 <= wi <= ScheduleManager.REGULAR_SEASON_WEEKS:
            rs_slice[str(wk)] = games
    return calculate_franchise_standings(rs_slice, team_ids_map)


def _distant_sim_batch_fpd_map(
    franchise_id: ObjectId,
    ftd_by_team_id: dict[str, dict],
) -> dict[str, dict[str, Any]]:
    """Batch-load FPD attributes for all active rosters in a distant-sim week."""
    player_ids: list[str] = []
    seen: set[str] = set()
    for doc in ftd_by_team_id.values():
        for pid in doc.get("players") or []:
            s = str(pid)
            if s and s not in seen:
                seen.add(s)
                player_ids.append(s)
    if not player_ids:
        return {}
    return _load_fpd_map(franchise_id, player_ids)


def _distant_sim_momentum_multiplier(team_chemistry_raw: Any) -> int:
    """Momentum multiplier from team chemistry. Distant_Game_Sim_System.md."""
    from BackEnd.distant_sim_engine import distant_sim_momentum_multiplier

    return distant_sim_momentum_multiplier(team_chemistry_raw)


def _distant_sim_momentum_term(
    ftd_doc: dict,
    season_wins: int,
    season_losses: int,
) -> int:
    """DISTANT_MO_MULT × (regular-season wins − losses). Distant_Game_Sim_System.md."""
    from BackEnd.distant_sim_engine import distant_sim_record_momentum

    raw = (ftd_doc.get("team_attributes") or {}).get("team_chemistry")
    return distant_sim_record_momentum(
        raw,
        season_wins=season_wins,
        season_losses=season_losses,
    )


def _distant_sim_team_combined(
    ftd_doc: dict,
    team_object_id: Any,
    *,
    is_home: bool,
    rs_standings: dict[str, dict[str, int]],
    fpd_by_player_id: dict[str, dict] | None = None,
    current_week: int = 0,
) -> int:
    """Base + record momentum + season momentum + tier adj + home bonus. See Distant_Game_Sim_System.md."""
    from BackEnd.distant_sim_engine import distant_sim_team_combined

    tid = str(team_object_id)
    row = rs_standings.get(tid) or {}
    wins = int(row.get("W", 0) or 0)
    losses = int(row.get("L", 0) or 0)
    return distant_sim_team_combined(
        ftd_doc,
        season_wins=wins,
        season_losses=losses,
        is_home=is_home,
        fpd_by_player_id=fpd_by_player_id,
        current_week=current_week,
    )


def _run_distant_game_sim(home_combined: int, away_combined: int) -> Tuple[int, int]:
    """
    Lightweight sim for distant (non-user-conference) games.
    Uses win probability roll, margin from dominance buckets, and clamped final scores.
    Returns (home_score, away_score).
    Callers pass home_combined / away_combined after base + momentum + home chemistry bonus.
    See _documentation_master/06_GMO_Supporting_Systems/Distant_Game_Sim_System.md
    """
    combined_total = home_combined + away_combined
    if combined_total <= 0:
        combined_total = 1
    roll = random.randint(1, combined_total)
    home_won = roll <= home_combined
    threshold = home_combined

    # Dominance: 0.0 = nail-biter, 1.0 = blowout
    if home_won:
        dominance = (threshold - roll) / threshold if threshold > 0 else 0.0
    else:
        denom = combined_total - threshold
        dominance = (roll - threshold) / denom if denom > 0 else 0.0
    dominance = max(0.0, min(1.0, dominance))

    # Map dominance to margin bucket (D1 distribution)
    if dominance < 0.18:
        margin = random.randint(1, 3)
    elif dominance < 0.45:
        margin = random.randint(4, 9)
    elif dominance < 0.77:
        margin = random.randint(10, 19)
    else:
        margin = random.randint(20, 40)

    # Rating gap modifier
    gap = abs(home_combined - away_combined) / combined_total
    if gap > 0.35:
        margin = int(margin * 1.50)
    elif gap > 0.20:
        margin = int(margin * 1.25)

    # Final scores: total_points from normal(138, 15) clamped [78, 220]
    total_points = int(round(max(78, min(220, random.gauss(138, 15)))))
    winning_score = math.ceil((total_points + margin) / 2)
    losing_score = winning_score - margin

    # Clamp losing floor
    if losing_score < 39:
        losing_score = 39
        winning_score = losing_score + margin
    # Clamp winning ceiling
    if winning_score > 121:
        winning_score = 121
        losing_score = winning_score - margin
    # If both clamps conflict, margin gives way
    if losing_score < 39:
        losing_score = 39
        margin = winning_score - losing_score

    if home_won:
        return (winning_score, losing_score)
    return (losing_score, winning_score)


def _distant_sim_persist_momentum_score_updates(
    franchise_id: ObjectId,
    *,
    winner_team_object_id: ObjectId,
    loser_team_object_id: ObjectId,
    ftd_cache: dict[str, dict] | None = None,
) -> None:
    """Update FTD momentum_score + distant win/loss streaks after a distant game."""
    from BackEnd.distant_sim_engine import compute_distant_momentum_score_updates

    winner_doc = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": winner_team_object_id},
        {"team_attributes": 1},
    )
    loser_doc = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": loser_team_object_id},
        {"team_attributes": 1},
    )
    if not winner_doc or not loser_doc:
        return

    winner_updates, loser_updates = compute_distant_momentum_score_updates(
        winner_doc.get("team_attributes"),
        loser_doc.get("team_attributes"),
    )
    for team_oid, partial in (
        (winner_team_object_id, winner_updates),
        (loser_team_object_id, loser_updates),
    ):
        set_payload = {f"team_attributes.{k}": v for k, v in partial.items()}
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": team_oid},
            {"$set": set_payload},
        )
        if ftd_cache is not None:
            cache_key = str(team_oid)
            cached = ftd_cache.get(cache_key)
            if cached is not None:
                team_attrs = cached.setdefault("team_attributes", {})
                team_attrs.update(partial)


def _distant_sim_apply_result_to_standings_cache(
    rs_standings: dict[str, dict[str, int]],
    away_id: Any,
    home_id: Any,
    away_score: int,
    home_score: int,
) -> None:
    from BackEnd.distant_sim_engine import distant_sim_apply_result_to_standings_cache

    distant_sim_apply_result_to_standings_cache(
        rs_standings, away_id, home_id, away_score, home_score
    )


def _persist_distant_franchise_game(
    *,
    franchise_id: ObjectId,
    week: int,
    away_team_object_id: ObjectId,
    home_team_object_id: ObjectId,
    away_score: int,
    home_score: int,
    ftd_cache: dict[str, dict] | None = None,
) -> tuple[dict[str, Any], str]:
    summary = build_distant_game_summary(
        franchise_id=str(franchise_id),
        week=week,
        home_team_object_id=home_team_object_id,
        away_team_object_id=away_team_object_id,
        home_score=home_score,
        away_score=away_score,
    )
    game_id = str(summary["_id"])
    db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
    stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(franchise_id))

    home_team_id = _normalize_team_id_to_string(home_team_object_id) or str(home_team_object_id)
    away_team_id = _normalize_team_id_to_string(away_team_object_id) or str(away_team_object_id)
    if home_score > away_score:
        winner_id, loser_id = home_team_id, away_team_id
        winner_oid, loser_oid = home_team_object_id, away_team_object_id
        winner_score, loser_score = home_score, away_score
    else:
        winner_id, loser_id = away_team_id, home_team_id
        winner_oid, loser_oid = away_team_object_id, home_team_object_id
        winner_score, loser_score = away_score, home_score
    _finalize_team_attributes_for_game(
        game_id=game_id,
        franchise_id=franchise_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        winner_id=winner_id,
        loser_id=loser_id,
        winner_score=winner_score,
        loser_score=loser_score,
        week=week,
    )
    _distant_sim_persist_momentum_score_updates(
        franchise_id,
        winner_team_object_id=winner_oid,
        loser_team_object_id=loser_oid,
        ftd_cache=ftd_cache,
    )

    sim_res = _save_game_result(
        away_team_object_id,
        home_team_object_id,
        away_score,
        home_score,
        week,
        franchise_id=str(franchise_id),
        game_id=game_id,
    )
    return sim_res, game_id


def _build_user_eos_sim_scope(
    franchise_doc: dict[str, Any],
    user_team_id_str: Optional[str],
) -> dict[str, Any]:
    """Snapshot the user's EOS sim scope at the start of a week."""
    scope = {
        "active": False,
        "conference": None,
        "region": None,
        "region_conferences": tuple(),
    }
    if not user_team_id_str:
        return scope

    eliminated_team_ids = ft.get_eliminated_team_ids(franchise_doc)
    scope["active"] = user_team_id_str not in eliminated_team_ids

    team_doc = None
    if ObjectId.is_valid(user_team_id_str):
        team_doc = db.teams.find_one(
            {"_id": ObjectId(user_team_id_str)},
            {"conference": 1, "region": 1},
        )
    conference = team_doc.get("conference") if team_doc else None
    region = team_doc.get("region") if team_doc else None
    if region is None and conference is not None:
        region = ft._conference_to_region(conference)

    scope["conference"] = conference
    scope["region"] = region
    scope["region_conferences"] = (
        ft._region_to_conferences(region) if region else tuple()
    )
    return scope


def _should_use_tbt_for_eos_game(
    week: int,
    game_meta: dict[str, Any],
    user_scope: dict[str, Any],
) -> bool:
    """Return True when an EOS matchup should use turn-by-turn sim."""
    if not user_scope.get("active"):
        return False

    if week in ft.EOS_CONFERENCE_WEEKS:
        conference = game_meta.get("conference")
        if week in (27, 28):
            return conference == user_scope.get("conference")
        if week == 29:
            return conference in set(user_scope.get("region_conferences") or ())
        return False

    if week in ft.EOS_REGION_WEEKS:
        return (
            game_meta.get("phase") == "region"
            and game_meta.get("region") == user_scope.get("region")
        )

    if week in ft.EOS_NATIONAL_WEEKS:
        return True

    return False


def _get_user_eos_phase_status(
    franchise_doc: dict[str, Any],
    user_team_id_str: Optional[str],
    week: int,
) -> dict[str, Any]:
    """Derive user EOS status from the current phase bracket instead of a sticky flag."""
    status = {
        "phase": None,
        "active_this_week": False,
        "has_game_this_week": False,
        "has_bye_this_week": False,
        "eliminated_from_current_phase": False,
        "region_qualified": False,
    }
    if not franchise_doc or not user_team_id_str or week not in ft.EOS_WEEKS:
        return status

    scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)
    user_conference = scope.get("conference")
    user_region = scope.get("region")
    week_games_meta = ft.get_eos_week_games(franchise_doc, week)
    found = ft.find_user_game_in_eos_week(week_games_meta, user_team_id_str)
    if found:
        status["has_game_this_week"] = True
        status["active_this_week"] = True

    region_qual = ft.user_qualifies_for_region_tournament(
        franchise_doc, user_team_id_str, user_conference
    )
    region_bracket_active = ft.user_has_active_region_bracket_path(
        franchise_doc, user_team_id_str, str(user_region or "")
    )

    if week in ft.EOS_CONFERENCE_WEEKS:
        status["phase"] = "conference"
        status["region_qualified"] = region_qual or region_bracket_active
        if status["has_game_this_week"]:
            status["eliminated_from_current_phase"] = False
        elif status["region_qualified"]:
            status["eliminated_from_current_phase"] = False
        else:
            status["eliminated_from_current_phase"] = True
        return status

    if week in ft.EOS_REGION_WEEKS:
        status["phase"] = "region"
        rt = (franchise_doc.get("region_tournaments") or {}).get(user_region or "", {})
        final_list = rt.get("final", []) or []
        final_matchup = final_list[0] if final_list else {}
        final_has_user = (
            ft._eos_team_id_canonical(final_matchup.get("away_team"))
            == ft._eos_team_id_canonical(user_team_id_str)
            or ft._eos_team_id_canonical(final_matchup.get("home_team"))
            == ft._eos_team_id_canonical(user_team_id_str)
        )
        final_unplayed = not final_matchup.get("winner")
        if week == ft.EOS_REGION_WEEKS[0] and not status["has_game_this_week"] and final_has_user and final_unplayed:
            status["has_bye_this_week"] = True
            status["active_this_week"] = True
        elif not status["has_game_this_week"]:
            if region_bracket_active:
                status["eliminated_from_current_phase"] = False
                status["active_this_week"] = True
            else:
                status["eliminated_from_current_phase"] = True
        status["region_qualified"] = (
            status["has_game_this_week"]
            or status["has_bye_this_week"]
            or region_bracket_active
        )
        return status

    if week in ft.EOS_NATIONAL_WEEKS:
        status["phase"] = "national"
        status["eliminated_from_current_phase"] = not status["has_game_this_week"]
        return status

    return status


REGION_BYE_MODAL_SEEN_SEASON_FIELD = "region_bye_modal_seen_season"
BRACKET_REVEAL_SEEN_FIELD = "bracket_reveal_seen"
BRACKET_UPDATE_SEEN_FIELD = "bracket_update_seen"
RECRUITING_RESULTS_MODAL_SEEN_SEASON_FIELD = "recruiting_results_modal_seen_season"

BRACKET_REVEAL_WEEKS = {
    27: ("conference", "Conference Tournament · Weeks 27–29", "full"),
    30: ("region", "Region Tournament · Weeks 30–31", "compact4"),
    32: ("national", "National Tournament · Weeks 32–34", "full"),
}

# FCC landing weeks after an EOS round completes (not phase-start reveal weeks).
BRACKET_UPDATE_WEEKS = {
    28: ("conference", "Conference Tournament · Weeks 27–29", "full"),
    29: ("conference", "Conference Tournament · Weeks 27–29", "full"),
    31: ("region", "Region Tournament · Weeks 30–31", "compact4"),
    33: ("national", "National Tournament · Weeks 32–34", "full"),
    34: ("national", "National Tournament · Weeks 32–34", "full"),
    35: ("national", "National Tournament · Weeks 32–34", "full"),
}


def _franchise_current_season(franchise_doc: dict[str, Any]) -> int:
    return int(franchise_doc.get("current_season", 1) or 1)


def _bracket_reveal_seen_key(tier: str, season: int) -> str:
    return f"{tier}:{season}"


def _bracket_update_seen_key(tier: str, season: int, week: int) -> str:
    return f"update:{tier}:{season}:{week}"


def _user_eos_bracket_and_seeds(
    franchise_doc: dict[str, Any],
    team_doc: dict[str, Any],
    tier: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """User-affiliated EOS bracket + seeds for conference / region / national."""
    if tier == "conference":
        conf = team_doc.get("conference")
        if conf is None:
            return None, {}
        ct = (franchise_doc.get("conference_tournaments") or {}).get(str(conf)) or {}
        return deepcopy(ct.get("bracket") or {}), dict(ct.get("seeds") or {})
    if tier == "region":
        region = str(team_doc.get("region") or "").upper()
        if len(region) != 1:
            return None, {}
        rt = (franchise_doc.get("region_tournaments") or {}).get(region) or {}
        bracket = {
            "round1": deepcopy(rt.get("round1") or []),
            "round2": [],
            "final": deepcopy(rt.get("final") or []),
        }
        return bracket, dict(rt.get("seeds") or {})
    nt = franchise_doc.get("national_tournament") or {}
    return deepcopy(nt.get("bracket") or {}), dict(nt.get("seeds") or {})


def _bracket_has_any_winner(bracket: dict[str, Any] | None) -> bool:
    if not bracket:
        return False
    for round_key in ("round1", "round2", "final"):
        for matchup in bracket.get(round_key) or []:
            if isinstance(matchup, dict) and matchup.get("winner"):
                return True
    return False


def _round1_not_started(bracket: dict[str, Any] | None) -> bool:
    if not bracket:
        return False
    round1 = bracket.get("round1") or []
    if not round1:
        return False
    for matchup in round1:
        if isinstance(matchup, dict) and matchup.get("winner"):
            return False
    return True


def _sanitize_bracket_for_reveal(bracket: dict[str, Any] | None, *, keep_final: bool = False) -> dict[str, Any]:
    b = deepcopy(bracket or {})
    for round_key in ("round1", "round2", "final"):
        for matchup in b.get(round_key) or []:
            if not isinstance(matchup, dict):
                continue
            matchup.pop("winner", None)
            if "score" in matchup:
                matchup["score"] = {}
    b["round2"] = []
    if not keep_final:
        b["final"] = []
    return b


def _build_bracket_reveal_modal_payload(
    franchise_doc: dict[str, Any] | None,
    team_doc: dict[str, Any] | None,
    week: int | None,
) -> dict[str, Any] | None:
    """Bracket Reveal modal: first FCC entry at EOS phase start before round 1 is played."""
    if not franchise_doc or not team_doc:
        return None
    week_val = int(week or 0)
    spec = BRACKET_REVEAL_WEEKS.get(week_val)
    if not spec:
        return None
    if not franchise_doc.get("eos_tournament_active"):
        return None

    tier, eyebrow, layout = spec
    season = _franchise_current_season(franchise_doc)
    reveal_key = _bracket_reveal_seen_key(tier, season)
    seen = franchise_doc.get(BRACKET_REVEAL_SEEN_FIELD) or {}
    if seen.get(reveal_key):
        return None

    raw, seeds = _user_eos_bracket_and_seeds(franchise_doc, team_doc, tier)
    if not raw or not _round1_not_started(raw):
        return None

    if tier == "region":
        bracket = _sanitize_bracket_for_reveal(raw, keep_final=True)
    else:
        bracket = _sanitize_bracket_for_reveal(raw)

    if not bracket or not (bracket.get("round1") or []):
        return None

    return {
        "eligible": True,
        "tier": tier,
        "eyebrow": eyebrow,
        "layout": layout,
        "reveal_key": reveal_key,
        "bracket": bracket,
        "seeds": seeds,
        "display_week": week_val,
    }


def _build_bracket_update_modal_payload(
    franchise_doc: dict[str, Any] | None,
    team_doc: dict[str, Any] | None,
    week: int | None,
) -> dict[str, Any] | None:
    """Bracket Update modal: FCC entry after an EOS round completes (active or eliminated)."""
    if not franchise_doc or not team_doc:
        return None
    week_val = int(week or 0)
    spec = BRACKET_UPDATE_WEEKS.get(week_val)
    if not spec:
        return None

    tier, eyebrow, layout = spec
    if week_val == 35:
        if not franchise_doc.get("national_tournament"):
            return None
    elif not franchise_doc.get("eos_tournament_active"):
        return None

    season = _franchise_current_season(franchise_doc)
    update_key = _bracket_update_seen_key(tier, season, week_val)
    seen = franchise_doc.get(BRACKET_UPDATE_SEEN_FIELD) or {}
    if seen.get(update_key):
        return None

    bracket, seeds = _user_eos_bracket_and_seeds(franchise_doc, team_doc, tier)
    if not bracket or not _bracket_has_any_winner(bracket):
        return None
    if tier in ("conference", "national") and not (bracket.get("round1") or []):
        return None
    if tier == "region" and not ((bracket.get("round1") or []) or (bracket.get("final") or [])):
        return None

    return {
        "eligible": True,
        "tier": tier,
        "eyebrow": eyebrow,
        "layout": layout,
        "update_key": update_key,
        "bracket": bracket,
        "seeds": seeds,
        "display_week": week_val,
    }


def _build_recruiting_results_modal_payload(
    franchise_doc: dict[str, Any] | None,
    team_id: str | None,
) -> dict[str, Any] | None:
    """Recruiting Results modal: first FCC entry after week-35 signings for the user team."""
    if not franchise_doc or not team_id:
        return None
    if not franchise_doc.get("week_35_recruiting_ran"):
        return None
    season = _franchise_current_season(franchise_doc)
    if int(franchise_doc.get(RECRUITING_RESULTS_MODAL_SEEN_SEASON_FIELD, 0) or 0) == season:
        return None

    week_35_results = franchise_doc.get(WEEK_35_RECRUITING_RESULTS_FIELD) or {}
    signed = [
        player
        for player in (week_35_results.get("signed_players") or [])
        if str(player.get("team_id") or "") == str(team_id)
    ]
    if not signed:
        return None

    recruits = []
    for player in signed[:5]:
        recruits.append(
            {
                "name": player.get("name") or "--",
                "pos": player.get("pos") or "--",
                "archetype": player.get("archetype") or "--",
                "height": player.get("height"),
                "weight": player.get("weight"),
                "year": player.get("year") or "JH",
                "rt": player.get("rt"),
            }
        )

    return {
        "eligible": True,
        "recruits": recruits,
        "count": len(recruits),
    }


def _should_show_region_bye_modal(
    franchise_doc: dict[str, Any],
    user_team_id_str: Optional[str],
) -> bool:
    """True once per franchise season when the user has a week-30 region bye."""
    if not franchise_doc or not user_team_id_str:
        return False
    if not franchise_doc.get("eos_tournament_active", False):
        return False
    week = int(franchise_doc.get("week", 0) or 0)
    eos_status = _get_user_eos_phase_status(franchise_doc, user_team_id_str, week)
    if not eos_status.get("has_bye_this_week", False):
        return False
    current_season = int(franchise_doc.get("current_season", 1) or 1)
    seen_season = int(franchise_doc.get(REGION_BYE_MODAL_SEEN_SEASON_FIELD, 0) or 0)
    return seen_season != current_season


@router.options("/franchise/select-team")
async def select_team_options():
    """
    Explicit OPTIONS handler for CORS preflight debugging.
    This bypasses CORSMiddleware to see if requests reach FastAPI at all.
    """
    import sys
    print(f"🔵 [DEBUG] select_team_options: OPTIONS /franchise/select-team called", file=sys.stderr, flush=True)
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "https://gob-test.netlify.app",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        }
    )

@router.post("/franchise/select-team")
def select_team(
    selection: TeamSelection,
    user: dict = Depends(get_current_user),
    profile: bool = False,
):
    import sys
    import time
    endpoint_start = time.time()
    print(f"🔵 [DEBUG] select_team: POST /franchise/select-team called with team: {selection.team_name}", file=sys.stderr, flush=True)
    try:
        # Step 7.2: One franchise per user - block creation if user already has one
        existing_franchises = db.franchises.count_documents({"user_id": user.get("user_id")})
        if existing_franchises >= 1:
            raise HTTPException(
                status_code=400,
                detail="You already have an active franchise. Delete it first to start a new one.",
            )

        # Resolve team name to ObjectId - try multiple strategies for matching
        print(f"🔵 [DEBUG] select_team: Looking up team in database: {selection.team_name}", file=sys.stderr, flush=True)
        
        # Strategy 1: Exact match
        team_query_start = time.time()
        team_doc = db.teams.find_one({"name": selection.team_name})
        team_query_time = (time.time() - team_query_start) * 1000
        # logger.warning(f"⏱️ [DB TIMING] select-team: teams.find_one(name={selection.team_name}): {team_query_time:.2f}ms")
        
        # Strategy 2: Case-insensitive regex match
        if not team_doc:
            print(f"🔵 [DEBUG] select_team: Exact match failed, trying case-insensitive search...", file=sys.stderr, flush=True)
            team_doc = db.teams.find_one({"name": {"$regex": f"^{re.escape(selection.team_name)}$", "$options": "i"}})
        
        # Strategy 3: Try with hyphen/underscore normalization (e.g., "Bentley-Truman" -> "Bentley Truman")
        if not team_doc and ("-" in selection.team_name or "_" in selection.team_name):
            print(f"🔵 [DEBUG] select_team: Case-insensitive failed, trying normalized format...", file=sys.stderr, flush=True)
            normalized = selection.team_name.replace("_", " ").replace("-", " ")
            team_doc = db.teams.find_one({"name": {"$regex": f"^{re.escape(normalized)}$", "$options": "i"}})
        
        # Strategy 4: Search all teams and find case-insensitive match
        if not team_doc:
            print(f"🔵 [DEBUG] select_team: Normalized format failed, trying full collection search...", file=sys.stderr, flush=True)
            all_teams = db.teams.find({}, {"name": 1})
            for t in all_teams:
                if t.get("name", "").upper().strip() == selection.team_name.upper().strip():
                    team_doc = t
                    print(f"✅ [DEBUG] select_team: Found match via full search: '{t.get('name')}' matches '{selection.team_name}'", file=sys.stderr, flush=True)
                    break
        
        if not team_doc:
            # Log all available team names for debugging
            available_teams = [t.get("name") for t in db.teams.find({}, {"name": 1})]
            print(f"❌ [ERROR] select_team: Team not found in database: {selection.team_name}", file=sys.stderr, flush=True)
            print(f"🔍 [DEBUG] select_team: Available teams in database: {available_teams}", file=sys.stderr, flush=True)
            raise HTTPException(status_code=404, detail=f"Team '{selection.team_name}' not found. Available teams: {', '.join(available_teams[:10])}")
        
        print(f"✅ [DEBUG] select_team: Team found, _id: {team_doc['_id']}", file=sys.stderr, flush=True)
        user_team_id = selection.team_name  # Team name (human-readable)
        user_team_object_id = str(team_doc["_id"])  # ObjectId string (database identifier)
        
        # Note: franchise_state_collection removed - using franchise document instead
        # Old franchises may still have data in franchise_state, but new ones won't create it
        
        print(f"🔵 [DEBUG] select_team: Initializing FranchiseManager...", file=sys.stderr, flush=True)
        franchise_init_start = time.time()
        if profile:
            from BackEnd.utils.profiling import run_profiled
            def _init():
                m = FranchiseManager(db)
                m.initialize_season(
                    user_team_id=user_team_id,
                    user_team_object_id=user_team_object_id,
                    user_id=user.get("user_id"),
                )
                return m
            # run_profiled takes a no-arg callable; we need to pass manager out
            _manager_ref = [None]
            def _wrapped():
                _manager_ref[0] = _init()
            profile_summary = run_profiled(_wrapped)
            manager = _manager_ref[0]
        else:
            manager = FranchiseManager(db)
            manager.initialize_season(
                user_team_id=user_team_id,
                user_team_object_id=user_team_object_id,
                user_id=user.get("user_id"),
            )
        franchise_init_time = (time.time() - franchise_init_start) * 1000
        total_time = (time.time() - endpoint_start) * 1000
        logger.warning(
            f"⏱️ [PERF] select-team total={total_time/1000:.2f}s init_season={franchise_init_time/1000:.2f}s"
        )

        print(f"✅ [DEBUG] select_team: Franchise initialized successfully, franchise_id: {manager.franchise_id}", file=sys.stderr, flush=True)
        result = {"status": "ok", "franchise_id": str(manager.franchise_id)}
        if profile:
            result["profile_summary"] = profile_summary
        print(f"🔵 [DEBUG] select_team: Returning response: {result}", file=sys.stderr, flush=True)
        return result
    except HTTPException as e:
        print(f"❌ [ERROR] select_team: HTTPException raised: {e.status_code} - {e.detail}", file=sys.stderr, flush=True)
        raise
    except Exception as e:
        print(f"❌ [ERROR] select_team: Unexpected exception: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/franchise/command-center")
def command_center():
    return FileResponse(STATIC_DIR / "franchise-command-center.html")


@router.get("/animation")
def get_animation_page():
    return FileResponse(STATIC_DIR / "court.html")


@router.post("/franchise/play-next-game")
def play_next_game(
    req: PlayGameRequest,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    # Get user team info (with backward compatibility)
    user_team_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_name or not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in franchise")
    
    # Resolve user_team_object_id to ObjectId for matching
    try:
        user_team_id = ObjectId(user_team_object_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user team ObjectId")

    manager = FranchiseManager(db)
    manager.schedule = franchise_doc.get("schedule", [])
    manager.week = franchise_doc.get("week", 1)
    manager.franchise_id = franchise_doc.get("_id")

    # ✅ EOS: Conference / Region / National (weeks 27–34)
    eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
    eos_has_state = bool(
        franchise_doc.get("conference_tournaments") or franchise_doc.get("region_tournaments") or franchise_doc.get("national_tournament")
    )
    matchup = None

    if eos_tournament_active and eos_has_state and manager.week in ft.EOS_WEEKS:
        # Reconcile region brackets before reading the slate so a user who clicks
        # Play without first hitting /franchise/command-center/data does not land on
        # a half-built region bracket with placeholder TBD slots.
        _maybe_reconcile_region_for_eos(
            franchise_doc,
            franchise_doc.get("_id"),
            week=int(manager.week),
            context_label="play_next_game",
        )
        week_games_meta = ft.get_eos_week_games(franchise_doc, manager.week)
        found = ft.find_user_game_in_eos_week(week_games_meta, str(user_team_id))
        if found:
            _, g = found
            home_id = g["home_id"]
            away_id = g["away_id"]
            home_doc = db.teams.find_one({"_id": home_id}, {"name": 1})
            away_doc = db.teams.find_one({"_id": away_id}, {"name": 1})
            # eos_meta locks the bracket slot at game-start time. When the FE plumbs
            # this through to ``complete-week`` via ``req.game_document.eos_meta``,
            # bracket resolution becomes immune to slate / week drift.
            eos_meta = {
                "phase": g.get("phase"),
                "round": g.get("round"),
                "matchup_index": g.get("matchup_index"),
                "away_id": str(away_id),
                "home_id": str(home_id),
            }
            if g.get("conference") is not None:
                eos_meta["conference"] = g.get("conference")
            if g.get("region") is not None:
                eos_meta["region"] = g.get("region")
            matchup = {
                "home": home_doc.get("name", "") if home_doc else "",
                "away": away_doc.get("name", "") if away_doc else "",
                "home_id": str(home_id),
                "away_id": str(away_id),
                "week": manager.week,
                "eos_meta": eos_meta,
            }
    if matchup is None and manager.week <= ScheduleManager.REGULAR_SEASON_WEEKS:
        # Regular season (weeks 1–26)
        if manager.week - 1 < len(manager.schedule):
            for away_id, home_id in manager.schedule[manager.week - 1]:
                # Compare ObjectIds (schedule uses ObjectIds, user_team_id is now ObjectId)
                if away_id == user_team_id or home_id == user_team_id:
                    away_doc = db.teams.find_one({"_id": away_id}, {"name": 1})
                    home_doc = db.teams.find_one({"_id": home_id}, {"name": 1})
                    matchup = {
                        "home": home_doc.get("name", ""),
                        "away": away_doc.get("name", ""),
                        "home_id": str(home_id),
                        "away_id": str(away_id),
                        "week": manager.week,
                    }
                    break

    if not matchup:
        raise HTTPException(status_code=404, detail="User matchup not found")
    return matchup


@router.post("/franchise/save-result")
def save_result(req: FranchiseResultRequest):
    logger.info(f"🔍 [SAVE-RESULT] ENDPOINT CALLED - franchise_id={req.franchise_id}, game_id={req.game_id}")
    logger.info(f"🔍 [SAVE-RESULT] Request object: {req}")
    try:
        franchise_id = ObjectId(req.franchise_id)
        game_id = ObjectId(req.game_id)
        logger.info(f"🔍 [SAVE-RESULT] IDs converted successfully - franchise_id={franchise_id}, game_id={game_id}")
    except Exception as e:
        logger.error(f"❌ [SAVE-RESULT] ID conversion failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid ID format")

    logger.info(f"🔍 [SAVE-RESULT] Looking up franchise and game documents")
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        logger.error(f"❌ [SAVE-RESULT] Franchise not found: {franchise_id}")
        raise HTTPException(status_code=404, detail="Franchise not found")

    game_doc = db.games.find_one({"_id": game_id})
    if not game_doc:
        logger.error(f"❌ [SAVE-RESULT] Game not found: {game_id}")
        raise HTTPException(status_code=404, detail="Game not found")

    # Snapshot the user's lead coaching archetype before finalize_game commits this
    # game's archetype counts; compared after to flag a first-time/changed archetype
    # for the community-highlights feed (consumed by the phase-B flush).
    archetype_owner_user_id = franchise_doc.get("user_id")
    lead_archetype_before = lead_archetype_for_user(archetype_owner_user_id)

    logger.info(f"🔍 [SAVE-RESULT] Documents found, extracting team info")
    home = game_doc.get("homeTeam", {}) or {}
    away = game_doc.get("awayTeam", {}) or {}
    home_name = home.get("name") or game_doc.get("home_team")
    away_name = away.get("name") or game_doc.get("away_team")
    home_id_raw = home.get("team_id") or game_doc.get("home_team_id")
    away_id_raw = away.get("team_id") or game_doc.get("away_team_id")
    
    # ✅ NORMALIZE: Convert ObjectIds/ObjectId strings to team_id strings (e.g. "LANCASTER") for SS&S
    # This ensures team_attribute_changes keys match box score expectations (home_team_id/away_team_id are team_id strings)
    home_id = _normalize_team_id_to_string(home_id_raw)
    away_id = _normalize_team_id_to_string(away_id_raw)
    
    if not home_id:
        logger.error(f"❌ [SAVE-RESULT] Could not normalize home_id: {home_id_raw} (type: {type(home_id_raw)})")
    if not away_id:
        logger.error(f"❌ [SAVE-RESULT] Could not normalize away_id: {away_id_raw} (type: {type(away_id_raw)})")
    
    logger.info(f"🔍 [SAVE-RESULT] Team IDs extracted and normalized - home_id={home_id} (was {home_id_raw}, type: {type(home_id)}), away_id={away_id} (was {away_id_raw}, type: {type(away_id)})")
    logger.info(f"🔍 [SAVE-RESULT] Team names - home_name={home_name}, away_name={away_name}")
    score_map = game_doc.get("score") or game_doc.get("final_score") or {}
    home_score = home.get("score", score_map.get(home_name, 0))
    away_score = away.get("score", score_map.get(away_name, 0))

    if req.winner == home_name:
        winner_id, loser_id = home_id, away_id
        winner_score, loser_score = home_score, away_score
    else:
        winner_id, loser_id = away_id, home_id
        winner_score, loser_score = away_score, home_score

    # ✅ FIX: Removed updates to universal teams collection.
    # Franchise mode stores W/L and PF/PA in franchise.results (set in complete-week endpoint),
    # and team stats are calculated from franchise.results when displayed.
    # This ensures franchise stats are isolated from other game modes and franchise instances.

    week = franchise_doc.get("week", 1) - 1
    if week < 1:
        week = 1

    db.games.delete_many(
        {
            "week": week,
            "$or": [
                {"team1_id": away_id, "team2_id": home_id},
                {"team1_id": home_id, "team2_id": away_id},
            ],
            "_id": {"$ne": game_id},
        }
    )

    db.games.update_one(
        {"_id": game_id},
        {
            "$set": {
                "franchise_id": str(franchise_id),
                "team1_id": away_id,
                "team2_id": home_id,
                "team1_score": away_score,
                "team2_score": home_score,
                "week": week,
            }
        },
        upsert=True,
    )
    
    # ✅ FIX: Verify box_score exists before finalize_game()
    # box_score should already exist from summarize_game_state() which calls game.get_box_score()
    # (includes all players: lineup + bench). If it's missing/incomplete, log error but don't rebuild
    # from players array (which only has final 5 players per team).
    game_doc_updated = db.games.find_one({"_id": game_id})
    if game_doc_updated:
        box_score = game_doc_updated.get("box_score", {})
        home_team_obj = game_doc_updated.get("home_team", {})
        away_team_obj = game_doc_updated.get("away_team", {})
        
        # Check if box_score exists in nested structure (where summarize_game_state stores it)
        if not box_score:
            if isinstance(home_team_obj, dict) and "box_score" in home_team_obj:
                home_team_name = home_team_obj.get("name")
                if home_team_name:
                    box_score[home_team_name] = home_team_obj.get("box_score", {})
            if isinstance(away_team_obj, dict) and "box_score" in away_team_obj:
                away_team_name = away_team_obj.get("name")
                if away_team_name:
                    box_score[away_team_name] = away_team_obj.get("box_score", {})
        
        # Verify box_score is complete (has reasonable number of players per team)
        # Expected: ~12 players per team (5 starters + 7 bench), minimum 5 (just starters)
        if box_score:
            for team_name, team_box in box_score.items():
                player_count = len(team_box) if isinstance(team_box, dict) else 0
                if player_count < 5:
                    logger.warning(f"⚠️ [SAVE-RESULT] box_score for {team_name} has only {player_count} players (expected 12). Game_id={game_id}")
        else:
            logger.error(f"❌ [SAVE-RESULT] No box_score found in game document (game_id={game_id}). finalize_game() may fail or produce incomplete stats.")
    
    logger.info(f"🔍 [SAVE-RESULT] Calling finalize_game()")
    stat_updater.finalize_game(
        req.game_id, mode="franchise", franchise_id=req.franchise_id
    )
    logger.info(f"🔍 [SAVE-RESULT] finalize_game() completed")

    # Flag a coaching-archetype change (established for the first time, or evolved)
    # for the community-highlights feed. No-op when unchanged.
    record_archetype_change_if_any(franchise_id, archetype_owner_user_id, lead_archetype_before)

    # Run team attribute update once and set team_attribute_changes on game doc for box score display
    _finalize_team_attributes_for_game(
        game_id=game_id,
        franchise_id=franchise_id,
        home_team_id=home_id,
        away_team_id=away_id,
        winner_id=winner_id,
        loser_id=loser_id,
        winner_score=winner_score,
        loser_score=loser_score,
        week=req.week,
    )

    return {"status": "success"}


def _phase_a_user_week_done(franchise_doc: dict, week: int) -> bool:
    pg = franchise_doc.get("post_game_status") or {}
    try:
        return int(pg.get("phase_a_user_week") or 0) == int(week)
    except (TypeError, ValueError):
        return False


def _week_result_matchup_key(row: dict) -> frozenset:
    """
    Canonical franchise week slot id: unordered pair of team ids for one scheduled game.
    Used for dedupe, idempotent phase-B retries, and completeness checks (Phase 2).
    """
    return frozenset({str(row.get("away_id")), str(row.get("home_id"))})


def _dedupe_franchise_week_results_by_matchup(results: list) -> list:
    """First row wins per matchup key; stable order."""
    seen: set[frozenset] = set()
    out: list = []
    for r in results:
        k = _week_result_matchup_key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(dict(r))
    return out


def _expected_franchise_week_matchup_key_set(week_games: list) -> set[frozenset]:
    keys: set[frozenset] = set()
    for pair in week_games:
        if not pair or len(pair) < 2:
            continue
        keys.add(frozenset({str(pair[0]), str(pair[1])}))
    return keys


def _week_results_list_contains_matchup(
    results: list, away_id: Any, home_id: Any
) -> bool:
    k = frozenset({str(away_id), str(home_id)})
    for r in results:
        if _week_result_matchup_key(r) == k:
            return True
    return False


def _week_results_row_for_matchup(
    results: list, away_id: Any, home_id: Any
) -> dict | None:
    k = frozenset({str(away_id), str(home_id)})
    for r in results:
        if _week_result_matchup_key(r) == k:
            return dict(r)
    return None


def _franchise_week_results_cover_schedule(results: list, week_games: list) -> bool:
    """True iff deduped results contain exactly one row per scheduled matchup in week_games."""
    deduped = _dedupe_franchise_week_results_by_matchup(results)
    if len(deduped) != len(week_games):
        return False
    expected = _expected_franchise_week_matchup_key_set(week_games)
    actual = {_week_result_matchup_key(r) for r in deduped}
    return expected == actual


def _order_franchise_week_results_like_schedule(results: list, week_games: list) -> list:
    """Stable schedule order (enumerate week_games) for scoreboard / downstream parity."""
    key_to_pos: dict[frozenset, int] = {}
    for i, pair in enumerate(week_games):
        if not pair or len(pair) < 2:
            continue
        key_to_pos[frozenset({str(pair[0]), str(pair[1])})] = i
    return sorted(
        [dict(r) for r in results],
        key=lambda r: key_to_pos.get(_week_result_matchup_key(r), 10**9),
    )


def _franchise_cpu_full_sim_max_workers() -> int:
    """Phase 3: cap parallel turn-based CPU sims."""
    try:
        return max(1, int(os.environ.get("FRANCHISE_CPU_SIM_MAX_WORKERS", "4")))
    except (TypeError, ValueError):
        return 4


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _cpu_sim_matchup_key(away_id: Any, home_id: Any) -> str:
    """Stable unordered CPU-sim matchup key used only for orchestration state."""
    return "|".join(sorted([str(away_id), str(home_id)]))


def _cpu_sim_user_matchup_key(team1_id: Any, team2_id: Any) -> str:
    if team1_id is None or team2_id is None:
        return ""
    return _cpu_sim_matchup_key(team1_id, team2_id)


def _cpu_sim_job_path(week: int) -> str:
    return f"cpu_sim_jobs.{str(week)}"


def _cpu_sim_completed_matchup_from_result(row: dict) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    away_id = row.get("away_id")
    home_id = row.get("home_id")
    if away_id is None or home_id is None:
        return None
    return {
        "away_id": str(away_id),
        "home_id": str(home_id),
        "away_score": row.get("away_score"),
        "home_score": row.get("home_score"),
        "status": "complete",
        "updated_at": _utc_now_iso(),
    }


def _cpu_sim_status_priority(status: Any) -> int:
    return {
        "pending": 0,
        "running": 1,
        "failed": 2,
        "complete": 3,
    }.get(str(status or ""), 0)


def _cpu_sim_is_stale_running(row: dict, *, now_ts: float | None = None) -> bool:
    if not isinstance(row, dict) or row.get("status") != "running":
        return False
    raw = row.get("updated_at") or row.get("started_at")
    if not raw:
        return True
    try:
        clean = str(raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is not None:
            started = dt.timestamp()
        else:
            started = dt.replace(tzinfo=None).timestamp()
    except Exception:
        return True
    now = now_ts if now_ts is not None else datetime.utcnow().timestamp()
    return (now - started) > CPU_SIM_RUNNING_STALE_SECONDS


def _merge_cpu_sim_matchup_state(existing: dict | None, incoming: dict | None) -> dict:
    existing = dict(existing or {})
    incoming = dict(incoming or {})
    if not existing:
        return incoming
    if not incoming:
        return existing

    if _cpu_sim_status_priority(existing.get("status")) > _cpu_sim_status_priority(incoming.get("status")):
        merged = {**incoming, **existing}
    else:
        merged = {**existing, **incoming}
    if existing.get("status") == "complete" or incoming.get("status") == "complete":
        merged["status"] = "complete"
        for src in (existing, incoming):
            for key in ("game_id", "away_score", "home_score", "completed_at"):
                if src.get(key) is not None:
                    merged[key] = src.get(key)
    return merged


def _compute_cpu_sim_job_rollup(job: dict) -> dict:
    matchups = job.get("matchups") if isinstance(job.get("matchups"), dict) else {}
    expected = len(matchups)
    complete = 0
    failed = 0
    running = 0
    pending = 0
    for row in matchups.values():
        status = row.get("status") if isinstance(row, dict) else None
        if status == "complete":
            complete += 1
        elif status == "failed":
            failed += 1
        elif status == "running":
            running += 1
        else:
            pending += 1
    job["expected_matchups"] = expected
    job["completed_matchups"] = complete
    job["failed_matchups"] = failed
    job["running_matchups"] = running
    job["pending_matchups"] = pending
    if job.get("status") == "finalized":
        job["updated_at"] = job.get("updated_at") or _utc_now_iso()
        return job
    if expected and complete >= expected:
        job["status"] = "complete"
        job.setdefault("completed_at", _utc_now_iso())
    elif failed:
        job["status"] = "failed"
    elif running:
        job["status"] = "running"
    elif complete:
        job["status"] = "partial"
    else:
        job["status"] = "pending"
    job["updated_at"] = _utc_now_iso()
    return job


def _build_cpu_sim_job(
    franchise_doc: dict,
    week: int,
    week_games: list,
    team1_id: Any,
    team2_id: Any,
    results: list,
    *,
    phase: str,
) -> dict:
    wk = str(week)
    existing_jobs = franchise_doc.get("cpu_sim_jobs") if isinstance(franchise_doc, dict) else {}
    existing_job = dict((existing_jobs or {}).get(wk) or {})
    existing_matchups = existing_job.get("matchups") if isinstance(existing_job.get("matchups"), dict) else {}
    user_key = _cpu_sim_user_matchup_key(team1_id, team2_id)
    now_iso = _utc_now_iso()

    matchups: dict[str, dict] = {}
    for idx, pair in enumerate(week_games):
        if not pair or len(pair) < 2:
            continue
        away_id, home_id = pair[0], pair[1]
        key = _cpu_sim_matchup_key(away_id, home_id)
        if user_key and key == user_key:
            continue
        base = {
            "away_id": str(away_id),
            "home_id": str(home_id),
            "schedule_index": idx,
            "status": "pending",
            "attempts": 0,
            "updated_at": now_iso,
        }
        matchups[key] = _merge_cpu_sim_matchup_state(existing_matchups.get(key), base)

    for row in results or []:
        completed = _cpu_sim_completed_matchup_from_result(row)
        if not completed:
            continue
        key = _cpu_sim_matchup_key(completed["away_id"], completed["home_id"])
        if key in matchups:
            completed["completed_at"] = completed.get("completed_at") or now_iso
            matchups[key] = _merge_cpu_sim_matchup_state(matchups.get(key), completed)

    now_ts = datetime.utcnow().timestamp()
    for key, row in list(matchups.items()):
        if _cpu_sim_is_stale_running(row, now_ts=now_ts):
            retry = dict(row)
            retry["status"] = "pending"
            retry["stale_reclaimed_at"] = now_iso
            retry["updated_at"] = now_iso
            matchups[key] = retry

    job = {
        **existing_job,
        "version": 1,
        "week": int(week),
        "phase": phase,
        "started_at": existing_job.get("started_at") or now_iso,
        "updated_at": now_iso,
        "matchups": matchups,
    }
    return _compute_cpu_sim_job_rollup(job)


def _persist_cpu_sim_job(franchise_id: ObjectId, week: int, local_job: dict) -> dict:
    """Persist orchestration state without clobbering completed rows from another request."""
    wk = str(week)
    fresh = db.franchises.find_one({"_id": franchise_id}, {_cpu_sim_job_path(week): 1}) or {}
    fresh_jobs = fresh.get("cpu_sim_jobs") if isinstance(fresh.get("cpu_sim_jobs"), dict) else {}
    fresh_job = dict((fresh_jobs or {}).get(wk) or {})
    fresh_matchups = fresh_job.get("matchups") if isinstance(fresh_job.get("matchups"), dict) else {}
    local_matchups = local_job.get("matchups") if isinstance(local_job.get("matchups"), dict) else {}
    merged_matchups: dict[str, dict] = {}
    for key in set(fresh_matchups.keys()) | set(local_matchups.keys()):
        merged_matchups[key] = _merge_cpu_sim_matchup_state(
            fresh_matchups.get(key),
            local_matchups.get(key),
        )
    merged_job = {**fresh_job, **local_job, "matchups": merged_matchups}
    merged_job = _compute_cpu_sim_job_rollup(merged_job)
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {_cpu_sim_job_path(week): merged_job}},
    )
    return merged_job


def _cpu_sim_mark_job_running(job: dict, *, phase: str) -> dict:
    job = dict(job or {})
    job["phase"] = phase
    job["status"] = "running"
    job["running_started_at"] = _utc_now_iso()
    job["updated_at"] = _utc_now_iso()
    return job


def _cpu_sim_mark_matchup_running(job: dict, away_id: Any, home_id: Any, *, engine: str) -> dict:
    key = _cpu_sim_matchup_key(away_id, home_id)
    matchups = dict(job.get("matchups") or {})
    row = dict(matchups.get(key) or {})
    now_iso = _utc_now_iso()
    row.update({
        "away_id": str(away_id),
        "home_id": str(home_id),
        "simulation_engine": engine,
        "status": "running",
        "started_at": row.get("started_at") or now_iso,
        "updated_at": now_iso,
        "attempts": int(row.get("attempts") or 0) + 1,
        "last_error": None,
    })
    matchups[key] = row
    job["matchups"] = matchups
    return _compute_cpu_sim_job_rollup(job)


def _cpu_sim_mark_matchup_complete(
    job: dict,
    away_id: Any,
    home_id: Any,
    *,
    engine: str,
    away_score: Any,
    home_score: Any,
    game_id: Any = None,
) -> dict:
    key = _cpu_sim_matchup_key(away_id, home_id)
    matchups = dict(job.get("matchups") or {})
    row = dict(matchups.get(key) or {})
    now_iso = _utc_now_iso()
    row.update({
        "away_id": str(away_id),
        "home_id": str(home_id),
        "simulation_engine": engine,
        "status": "complete",
        "away_score": away_score,
        "home_score": home_score,
        "game_id": str(game_id) if game_id else row.get("game_id"),
        "completed_at": now_iso,
        "updated_at": now_iso,
        "last_error": None,
    })
    matchups[key] = row
    job["matchups"] = matchups
    return _compute_cpu_sim_job_rollup(job)


def _cpu_sim_mark_matchup_failed(job: dict, away_id: Any, home_id: Any, *, engine: str, error: Any) -> dict:
    key = _cpu_sim_matchup_key(away_id, home_id)
    matchups = dict(job.get("matchups") or {})
    row = dict(matchups.get(key) or {})
    now_iso = _utc_now_iso()
    row.update({
        "away_id": str(away_id),
        "home_id": str(home_id),
        "simulation_engine": engine,
        "status": "failed",
        "updated_at": now_iso,
        "last_error": str(error),
    })
    matchups[key] = row
    job["matchups"] = matchups
    return _compute_cpu_sim_job_rollup(job)


def _cpu_sim_job_public_summary(franchise_doc: dict | None, week: int | None = None) -> dict | None:
    """Return the durable CPU sim status the frontend needs for recovery UI."""
    if not isinstance(franchise_doc, dict):
        return None
    try:
        resolved_week = int(week if week is not None else franchise_doc.get("week", 1) or 1)
    except (TypeError, ValueError):
        resolved_week = 1

    jobs = franchise_doc.get("cpu_sim_jobs") if isinstance(franchise_doc.get("cpu_sim_jobs"), dict) else {}
    raw_job = jobs.get(str(resolved_week)) if isinstance(jobs, dict) else None
    job = _compute_cpu_sim_job_rollup(raw_job) if isinstance(raw_job, dict) else None
    post_game_status = franchise_doc.get("post_game_status") or {}
    try:
        phase_a_week = int(post_game_status.get("phase_a_user_week") or 0)
    except (TypeError, ValueError):
        phase_a_week = 0
    phase_a_complete = phase_a_week == resolved_week
    status = str((job or {}).get("status") or "pending")
    phase_b_required = bool(phase_a_complete and status != "finalized")

    if not job and not phase_b_required:
        return None

    return {
        "week": resolved_week,
        "status": status,
        "phase": (job or {}).get("phase") or ("phase_b" if phase_b_required else None),
        "phase_a_complete": phase_a_complete,
        "phase_b_required": phase_b_required,
        "can_resume_phase_b": phase_b_required,
        "expected_matchups": int((job or {}).get("expected_matchups", 0) or 0),
        "completed_matchups": int((job or {}).get("completed_matchups", 0) or 0),
        "failed_matchups": int((job or {}).get("failed_matchups", 0) or 0),
        "updated_at": (job or {}).get("updated_at"),
        "started_at": (job or {}).get("started_at"),
        "completed_at": (job or {}).get("completed_at"),
        "finalized_at": (job or {}).get("finalized_at"),
        "last_error": (job or {}).get("last_error"),
    }


_FRANCHISE_CPU_FULL_SIM_FTD_PROJECTION = {
    "team_id": 1,
    "team_attributes": 1,
    "strategy_settings": 1,
    "playbook_settings": 1,
    "plays": 1,
    "scouting_data": 1,
}


def _franchise_cpu_full_sim_ftd_doc(franchise_id: Any, team_id: Any) -> dict:
    fid_candidates: list[Any] = [franchise_id]
    if isinstance(franchise_id, str) and ObjectId.is_valid(franchise_id):
        fid_candidates.append(ObjectId(franchise_id))

    tid_candidates: list[Any] = [team_id]
    tid_str = str(team_id) if team_id is not None else ""
    if tid_str and ObjectId.is_valid(tid_str):
        tid_candidates.append(ObjectId(tid_str))
    if tid_str:
        tid_candidates.append(tid_str)

    seen: set[tuple[str, str]] = set()
    for fid in fid_candidates:
        for tid in tid_candidates:
            key = (type(fid).__name__ + ":" + str(fid), type(tid).__name__ + ":" + str(tid))
            if key in seen:
                continue
            seen.add(key)
            doc = franchise_team_data_collection.find_one(
                {"franchise_id": fid, "team_id": tid},
                _FRANCHISE_CPU_FULL_SIM_FTD_PROJECTION,
            )
            if doc:
                return doc
    return {}


def _run_franchise_cpu_full_simulation_core(
    franchise_id: Any,
    home_id: Any,
    away_id: Any,
    home_name: str,
    away_name: str,
) -> tuple[int, int, dict]:
    """CPU-only turn-based franchise sim; hydrate FTD data and avoid DB writes."""
    home_prepared = prepare_ftd_for_new_game(
        _franchise_cpu_full_sim_ftd_doc(franchise_id, home_id)
    )
    away_prepared = prepare_ftd_for_new_game(
        _franchise_cpu_full_sim_ftd_doc(franchise_id, away_id)
    )

    gm = GameManager(
        home_name,
        away_name,
        home_strategy_settings=home_prepared.get("strategy_settings"),
        away_strategy_settings=away_prepared.get("strategy_settings"),
        home_team_attributes=home_prepared.get("team_attributes"),
        away_team_attributes=away_prepared.get("team_attributes"),
        home_scouting_data=home_prepared.get("scouting_data"),
        away_scouting_data=away_prepared.get("scouting_data"),
        home_plays_data=home_prepared.get("plays_data"),
        away_plays_data=away_prepared.get("plays_data"),
        mode="franchise",
        franchise_id=str(franchise_id) if franchise_id is not None else None,
    )
    gm.home_team.playbook_settings = dict(home_prepared.get("playbook_settings") or {})
    gm.away_team.playbook_settings = dict(away_prepared.get("playbook_settings") or {})
    gm.game_state["allow_fouled_out_lineup_reentry"] = True

    if not gm.home_team.lineup:
        gm.home_team.lineup = build_lineup_from_mongo(gm.home_team, gm.game_state)
    if not gm.away_team.lineup:
        gm.away_team.lineup = build_lineup_from_mongo(gm.away_team, gm.game_state)

    gm.setup_opening_tip()

    gm.quarter = 1
    while True:
        simulate_quarter(gm)

        current_q = gm.quarter - 1
        if current_q >= 4:
            h_pts = gm.game_state["score"][gm.home_team.name]
            a_pts = gm.game_state["score"][gm.away_team.name]
            if h_pts != a_pts:
                gm.quarter = current_q
                gm.game_state["quarter"] = current_q
                break
            gm.home_team.points_by_quarter.append(0)
            gm.away_team.points_by_quarter.append(0)

    away_score = int(gm.score.get(away_name, 0) or 0)
    home_score = int(gm.score.get(home_name, 0) or 0)
    summary = summarize_game_state(gm)
    if not isinstance(summary, dict):
        summary = {}
    return away_score, home_score, summary


def _merge_phase_a_user_row_into_week_results(
    existing_week_results: list | None, user_row: dict
) -> list:
    existing = list(existing_week_results or [])
    ukey = _week_result_matchup_key(user_row)
    merged = [r for r in existing if _week_result_matchup_key(r) != ukey]
    merged.append(dict(user_row))
    return merged


def _game_document_week_int(game_document: dict | None) -> int | None:
    if not isinstance(game_document, dict):
        return None
    raw = game_document.get("week")
    if raw is None:
        return None
    try:
        w = int(raw)
    except (TypeError, ValueError):
        return None
    return w if w >= 1 else None


def _harden_complete_week_request_week(
    franchise_doc: dict, req: CompleteWeekRequest
) -> CompleteWeekRequest:
    """
    Bring ``req.week`` into agreement with the actual played EOS slot.

    Two coalescing rules:

    1. **Future-week guard.** When ``req.week > franchise.week`` (client one week ahead
       from a stale URL / localStorage), coalesce to ``franchise.week``.

    2. **Trust ``game_document.week`` when the slate disagrees.** When ``req.week`` and
       ``game_document.week`` are both EOS weeks but disagree, and the team pair appears
       in ``game_document.week``'s slate but not in ``req.week``'s, coalesce to
       ``game_document.week``. Symmetric: applies in both directions (``gw < rw`` *and*
       ``gw > rw``). The earlier asymmetric form caused silent bracket-cell misses when
       the client posted a stale older week for a game that had actually been played in
       a later EOS round.
    """
    try:
        fr_w = int(franchise_doc.get("week") or 0) or 1
    except (TypeError, ValueError):
        fr_w = 1
    rw = int(req.week)

    if rw > fr_w:
        logger.warning(
            "[COMPLETE-WEEK-WEEK-HARDEN] req.week=%s > franchise.week=%s; coalescing to franchise.week",
            rw,
            fr_w,
        )
        return CompleteWeekRequest(
            franchise_id=req.franchise_id,
            week=fr_w,
            result=req.result,
            game_id=req.game_id,
            game_document=req.game_document,
        )

    gw = _game_document_week_int(req.game_document)
    if (
        gw is not None
        and gw in ft.EOS_WEEKS
        and rw in ft.EOS_WEEKS
        and gw != rw
    ):
        t1 = _normalize_team_id(req.result.team1_id)
        t2 = _normalize_team_id(req.result.team2_id)
        try:
            meta_rw = ft.get_eos_week_games(franchise_doc, rw, include_completed=True)
            meta_gw = ft.get_eos_week_games(franchise_doc, gw, include_completed=True)
        except Exception:
            return req
        has_rw = ftp.find_eos_game_meta_for_team_pair(meta_rw, t1, t2) is not None
        has_gw = ftp.find_eos_game_meta_for_team_pair(meta_gw, t1, t2) is not None
        if not has_rw and has_gw:
            logger.warning(
                "[COMPLETE-WEEK-WEEK-HARDEN] eos_trust_game_document week req=%s doc=%s franchise.week=%s direction=%s",
                rw,
                gw,
                fr_w,
                "doc_behind" if gw < rw else "doc_ahead",
            )
            return CompleteWeekRequest(
                franchise_id=req.franchise_id,
                week=gw,
                result=req.result,
                game_id=req.game_id,
                game_document=req.game_document,
            )
        if not has_rw and not has_gw:
            logger.warning(
                "[COMPLETE-WEEK-WEEK-HARDEN] no_slate_match_either_week req=%s doc=%s franchise.week=%s; "
                "downstream invariant will raise if this is a user game",
                rw,
                gw,
                fr_w,
            )

    return req


def _maybe_reconcile_region_for_eos(
    franchise_doc: dict,
    franchise_id: Any,
    *,
    week: int,
    context_label: str,
) -> bool:
    """
    Reconcile region brackets against canonical (conference champions + RS#1) when in
    region weeks. Mutates ``franchise_doc`` in memory and persists the new
    ``region_tournaments`` blob if anything changed. Returns ``True`` iff a write happened.

    Runs on the play / complete-week entry points so a user who clicks Play (or whose
    client posts complete-week) without first hitting ``/franchise/command-center/data``
    cannot land on a half-built region bracket with placeholder TBD slots — the
    placeholder rows would otherwise drop the user pair out of ``get_eos_week_games``,
    causing the bracket-write invariant to fire.

    Idempotent: ``reconcile_region_tournaments_with_canonical`` returns ``None`` when
    nothing changed, in which case we skip the persist.
    """
    if week not in ft.EOS_REGION_WEEKS:
        return False
    if not franchise_doc.get("region_tournaments"):
        return False
    try:
        franchise_oid = franchise_id if isinstance(franchise_id, ObjectId) else ObjectId(franchise_id)
    except Exception:
        return False
    eos_team_ids = [
        d["team_id"]
        for d in franchise_team_data_collection.find({"franchise_id": franchise_oid}, {"team_id": 1})
        if d.get("team_id") is not None
    ]
    if not eos_team_ids:
        return False
    updated_rt = ft.reconcile_region_tournaments_with_canonical(
        franchise_doc, db.teams, eos_team_ids
    )
    if updated_rt is None:
        return False
    franchise_doc["region_tournaments"] = updated_rt
    db.franchises.update_one({"_id": franchise_oid}, {"$set": {"region_tournaments": updated_rt}})
    logger.warning(
        "[EOS-REGION-RECONCILE] context=%s week=%s franchise_id=%s persisted=%s ftd_team_count=%s",
        context_label,
        week,
        str(franchise_oid),
        True,
        len(eos_team_ids),
    )
    return True


def _resolve_complete_week_week_games(franchise_doc: dict, req: CompleteWeekRequest):
    schedule = franchise_doc.get("schedule", [])
    eos_active = bool(
        franchise_doc.get("eos_tournament_active")
        and (
            franchise_doc.get("conference_tournaments")
            or franchise_doc.get("region_tournaments")
            or franchise_doc.get("national_tournament")
        )
    )
    eos_current_round = None
    week_games_meta = None
    if req.week in ft.EOS_WEEKS and eos_active:
        # Reconcile region brackets before reading the slate so placeholder TBD slots
        # cannot drop the user pair out of ``get_eos_week_games`` (which would trip
        # the bracket-write invariant in ``_complete_week_process_user_game_block``).
        # No-op outside region weeks; idempotent.
        _maybe_reconcile_region_for_eos(
            franchise_doc,
            req.franchise_id,
            week=int(req.week),
            context_label="complete_week",
        )
        # Full calendar slate for this EOS week (including matchups that already have a bracket winner).
        # Must match results[week] row count after phase A; omitting completed slots caused dedup vs
        # expected_matchups mismatch and phase-b HTTP 500.
        week_games_meta = ft.get_eos_week_games(franchise_doc, req.week, include_completed=True)
        week_games = [(g["away_id"], g["home_id"]) for g in week_games_meta]
        eos_current_round = (
            req.week - 26
            if req.week <= 29
            else (req.week - 29 if req.week <= 31 else req.week - 31)
        )
    elif req.week <= ScheduleManager.REGULAR_SEASON_WEEKS:
        if req.week < 1 or req.week > len(schedule):
            raise HTTPException(status_code=400, detail="Invalid week")
        week_games = schedule[req.week - 1]
    else:
        raise HTTPException(status_code=400, detail="Invalid week")
    return week_games, week_games_meta, eos_current_round


def _user_next_regular_season_opponent_id(
    franchise_doc: dict,
    *,
    current_week: int,
    user_team_id_str: Any,
) -> str | None:
    """
    Return the other team's id (as str) scheduled vs the user in regular-season week current_week + 1.
    Used to force full step-by-step CPU sim for that opponent's current-week game instead of distant sim.
    """
    if not user_team_id_str:
        return None
    next_w = int(current_week) + 1
    if next_w < 1 or next_w > ScheduleManager.REGULAR_SEASON_WEEKS:
        return None
    schedule = franchise_doc.get("schedule") or []
    idx = next_w - 1
    if idx < 0 or idx >= len(schedule):
        return None
    uid = str(user_team_id_str)
    for pair in schedule[idx]:
        if not pair or len(pair) < 2:
            continue
        away_id, home_id = pair[0], pair[1]
        a, h = str(away_id), str(home_id)
        if a == uid:
            return h
        if h == uid:
            return a
    return None


def _find_user_franchise_week_matchup_normalized_ids(
    week_games: list,
    user_team_id_str: str | None,
    *,
    week: int | None = None,
    saved_week_results: list | None = None,
) -> tuple[Any, Any]:
    if not user_team_id_str:
        raise HTTPException(status_code=400, detail="Franchise has no user team")
    ut = str(user_team_id_str)
    for away_id, home_id in week_games:
        if str(away_id) == ut or str(home_id) == ut:
            return _normalize_team_id(str(away_id)), _normalize_team_id(str(home_id))
    # If week_games omits the user slot (legacy include_completed=False lists), fall back to saved rows.
    if week is not None and week in ft.EOS_WEEKS and saved_week_results:
        for r in saved_week_results:
            if not isinstance(r, dict):
                continue
            away_id = r.get("away_id")
            home_id = r.get("home_id")
            if away_id is None or home_id is None:
                continue
            if str(away_id) == ut or str(home_id) == ut:
                return _normalize_team_id(str(away_id)), _normalize_team_id(str(home_id))
    raise HTTPException(status_code=400, detail="User team has no game this week")


def _save_user_eos_bracket_result(
    franchise_doc: dict,
    *,
    week_games_meta: list | None,
    user_team_id_str: Any,
    team1_id: Any,
    team2_id: Any,
    team1_score: int,
    team2_score: int,
    game_id: str | None,
    week: int | None = None,
    franchise_id_str: str | None = None,
) -> dict | None:
    """
    Persist the played user EOS game: ``games`` row + bracket slot via
    ``franchise_tournament_progression.record_tournament_game_result``.
    """
    g = ftp.find_user_eos_game_meta(franchise_doc, week_games_meta, user_team_id_str, week)
    if not g:
        return None
    fid = franchise_id_str or str(franchise_doc.get("_id") or "")
    wk = week
    if wk is None:
        ph = g.get("phase")
        if ph == "conference":
            wk = 26 + int(g.get("round", 1) or 1)
        elif ph == "region":
            wk = 30 if int(g.get("round", 1) or 1) == 1 else 31
        elif ph == "national":
            wk = 31 + int(g.get("round", 1) or 1)
        else:
            wk = 27
    ftp.record_tournament_game_result(
        franchise_doc,
        g,
        week=wk,
        franchise_id_str=fid or "000000000000000000000000",
        game_id=game_id,
        team1_id=team1_id,
        team2_id=team2_id,
        team1_score=team1_score,
        team2_score=team2_score,
        source="user",
    )
    logger.warning(
        "[EOS-BRACKET-DEBUG] user_eos_bracket_save_done franchise_id=%s phase=%s",
        str(franchise_doc.get("_id")),
        g.get("phase"),
    )
    return g


def _stamp_eos_meta_on_game_doc(
    game_id: Any,
    eos_g_meta: dict[str, Any],
    franchise_id_str: str,
) -> None:
    """
    Persist a copy of the resolved EOS bracket meta on the matching ``games`` document.

    Once stamped, future ``complete-week`` retries, phase-b syncs, and repair tooling
    can read the bracket slot directly off the game document via
    ``_eos_meta_from_game_document`` without re-running slate matching against a
    possibly-drifted ``franchise_doc``. No-op if ``game_id`` is empty.
    """
    if not game_id:
        return
    snapshot = {
        "phase": eos_g_meta.get("phase"),
        "round": eos_g_meta.get("round"),
        "matchup_index": eos_g_meta.get("matchup_index"),
        "away_id": str(eos_g_meta.get("away_id")) if eos_g_meta.get("away_id") is not None else None,
        "home_id": str(eos_g_meta.get("home_id")) if eos_g_meta.get("home_id") is not None else None,
        "franchise_id": franchise_id_str,
    }
    if eos_g_meta.get("conference") is not None:
        snapshot["conference"] = eos_g_meta.get("conference")
    if eos_g_meta.get("region") is not None:
        snapshot["region"] = eos_g_meta.get("region")
    # Championship Announce Moments: front-end reads ``franchise_season`` off the
    # stamped eos_meta to render the season number in the championship overlay
    # that replaces the standard EOG modal for live championship games.
    if eos_g_meta.get("franchise_season") is not None:
        snapshot["franchise_season"] = eos_g_meta.get("franchise_season")
    else:
        try:
            franchise_doc_local = db.franchises.find_one(
                {"_id": ObjectId(franchise_id_str)},
                {"current_season": 1},
            ) or {}
            snapshot["franchise_season"] = int(franchise_doc_local.get("current_season", 1) or 1)
        except Exception:
            pass
    try:
        gid_str = str(game_id)
        existing = db.games.find_one({"_id": gid_str})
        if existing:
            db.games.update_one({"_id": gid_str}, {"$set": {"eos_meta": snapshot}})
            return
        if ObjectId.is_valid(gid_str):
            db.games.update_one({"_id": ObjectId(gid_str)}, {"$set": {"eos_meta": snapshot}})
    except Exception as exc:
        # Stamping is best-effort: failure must not block the user game from completing.
        logger.warning(
            "[EOS-BRACKET-DEBUG] stamp_eos_meta_on_game_doc_failed game_id=%s err=%s",
            game_id,
            exc,
        )


def _eos_meta_from_game_document(req: CompleteWeekRequest) -> dict | None:
    """
    Read ``eos_meta`` off ``req.game_document`` if the game doc was stamped with one
    at game-creation time (forward-compat with future ``play-next-game`` plumbing).

    Required keys: ``phase``, ``round``, ``matchup_index``, plus ``conference`` (for
    ``conference``) or ``region`` (for ``region``); plus ``away_id`` / ``home_id``.
    """
    gd = getattr(req, "game_document", None)
    if not isinstance(gd, dict):
        return None
    raw = gd.get("eos_meta")
    if not isinstance(raw, dict):
        return None
    phase = raw.get("phase")
    if phase not in ("conference", "region", "national"):
        return None
    if "round" not in raw or "matchup_index" not in raw:
        return None
    if phase == "conference" and raw.get("conference") is None:
        return None
    if phase == "region" and raw.get("region") is None:
        return None
    if not raw.get("away_id") or not raw.get("home_id"):
        return None
    return dict(raw)


def _resolve_user_eos_game_meta_or_raise(
    *,
    franchise_doc: dict,
    req: CompleteWeekRequest,
    week_games_meta: list | None,
    user_team_id_str: Any,
    team1_id: Any,
    team2_id: Any,
) -> dict | None:
    """
    Resolve the user's EOS bracket slot for this complete-week request.

    Resolution order:
      1. ``req.game_document.eos_meta`` (if a future writer stamped it at game start) —
         single source of truth, immune to slate / week drift.
      2. ``find_user_eos_game_meta`` against this week's slate (calendar + playable fallback).
      3. ``find_eos_game_meta_for_team_pair`` against this week's slate (handles
         ``user_team_id_str`` mismatches against bracket ids).

    Hard invariant: when ``req.week`` is in ``EOS_WEEKS`` and the franchise has an
    active EOS slate (``week_games_meta`` non-empty), one of the resolutions must
    succeed. Otherwise we raise 409 instead of silently falling through to
    ``_save_game_result`` (which would persist a score-only result and leave the
    bracket cell empty). See ``Tournament_Execution_System.md`` §"User game bracket
    write invariant".
    """
    eos_g_meta = _eos_meta_from_game_document(req)
    if eos_g_meta is not None:
        logger.warning(
            "[EOS-BRACKET-DEBUG] eos_meta_from_game_document franchise_id=%s week=%s phase=%s",
            str(franchise_doc.get("_id")),
            req.week,
            eos_g_meta.get("phase"),
        )
        return eos_g_meta

    if not week_games_meta:
        # EOS week but no slate: this should not happen during normal play; calendar
        # finalize + sim-rest are responsible for keeping eos_tournament_active in sync
        # with the bracket blobs. Refuse to persist score-only.
        raise HTTPException(
            status_code=409,
            detail=(
                f"EOS week {req.week} has no playable slate "
                f"(eos_tournament_active=False or empty conference/region/national blobs). "
                f"Reload the franchise command center to reconcile, then retry."
            ),
        )

    eos_g_meta = ftp.find_user_eos_game_meta(
        franchise_doc, week_games_meta, user_team_id_str, req.week
    )
    if not eos_g_meta:
        eos_g_meta = ftp.find_eos_game_meta_for_team_pair(
            week_games_meta, team1_id, team2_id
        )
        if eos_g_meta:
            logger.warning(
                "[EOS-BRACKET-DEBUG] eos_meta_resolved_by_pair franchise_id=%s week=%s "
                "user_team_id_str=%s phase=%s",
                str(franchise_doc.get("_id")),
                req.week,
                user_team_id_str,
                eos_g_meta.get("phase"),
            )

    if not eos_g_meta:
        try:
            fr_w = int(franchise_doc.get("week") or 0)
        except (TypeError, ValueError):
            fr_w = 0
        gw = _game_document_week_int(getattr(req, "game_document", None))
        logger.error(
            "[EOS-BRACKET-DEBUG] eos_meta_unresolved_in_eos_week franchise_id=%s "
            "req_week=%s franchise_week=%s game_doc_week=%s user_team_id=%s "
            "team1=%s team2=%s slate_n=%s",
            str(franchise_doc.get("_id")),
            req.week,
            fr_w,
            gw,
            user_team_id_str,
            team1_id,
            team2_id,
            len(week_games_meta),
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Could not resolve an EOS bracket slot for the user's game "
                f"(franchise_id={req.franchise_id}, week={req.week}, "
                f"team1={team1_id}, team2={team2_id}). Refusing to persist a "
                f"score-only result that would leave the bracket cell empty. "
                f"Reload the franchise command center to reconcile region brackets, "
                f"or check that the franchise week matches the game being played."
            ),
        )
    return eos_g_meta


def _resolve_user_game_bulk_sim_used(req: CompleteWeekRequest) -> bool:
    """Read durable bulk-sim marker from the completed user game, when available."""
    if isinstance(getattr(req, "game_document", None), dict):
        if req.game_document.get("bulk_sim_used") is True:
            return True

    user_game_id = getattr(req, "game_id", None)
    if not user_game_id:
        return False

    lookup_ids: list[Any] = [user_game_id]
    try:
        if ObjectId.is_valid(str(user_game_id)):
            oid = ObjectId(str(user_game_id))
            if oid not in lookup_ids:
                lookup_ids.append(oid)
    except Exception:
        pass

    for lookup_id in lookup_ids:
        try:
            doc = db.games.find_one({"_id": lookup_id}, {"bulk_sim_used": 1})
        except Exception:
            doc = None
        if doc and doc.get("bulk_sim_used") is True:
            return True
    return False


def _complete_week_process_user_game_block(
    franchise_doc: dict,
    req: CompleteWeekRequest,
    franchise_id: ObjectId,
    week_games_meta: list | None,
    user_team_id_str: Any,
    _u_name: str | None,
) -> tuple[dict, dict, int, dict | None, str | None]:
    if user_team_id_str:
        _clear_fcc_pending_new_lean_recruits(franchise_doc, franchise_id)

    gp_before = user_geek_points_snapshot_for_franchise(franchise_doc)
    # Snapshot the user's lead coaching archetype before finalize_game commits this
    # game's archetype counts; compared after to flag a first-time/changed archetype
    # (community-highlights feed row + FCC "you have evolved" modal).
    archetype_owner_user_id = franchise_doc.get("user_id")
    lead_archetype_before = lead_archetype_for_user(archetype_owner_user_id)
    user = req.result
    team1_id = _normalize_team_id(user.team1_id)
    team2_id = _normalize_team_id(user.team2_id)
    
    # ✅ SS&S: Use provided game_id if available (this is the actual gameplay document with box_score)
    user_game_id = req.game_id
    bulk_sim_used = _resolve_user_game_bulk_sim_used(req)
    eos_g_meta = None
    if req.week in ft.EOS_WEEKS:
        eos_g_meta = _resolve_user_eos_game_meta_or_raise(
            franchise_doc=franchise_doc,
            req=req,
            week_games_meta=week_games_meta,
            user_team_id_str=user_team_id_str,
            team1_id=team1_id,
            team2_id=team2_id,
        )
    if eos_g_meta:
        ftp.record_tournament_game_result(
            franchise_doc,
            eos_g_meta,
            week=req.week,
            franchise_id_str=str(req.franchise_id),
            game_id=user_game_id,
            team1_id=team1_id,
            team2_id=team2_id,
            team1_score=user.team1_score,
            team2_score=user.team2_score,
            source="user",
        )
        # Stamp eos_meta on the games doc so future retries / phase-b syncs / repair
        # tooling can read the bracket slot without re-running slate matching. Safe to
        # do whether or not user_game_id is present — only persists when the doc exists.
        _stamp_eos_meta_on_game_doc(user_game_id, eos_g_meta, str(req.franchise_id))
        user_res = {
            "team1_id": str(team1_id),
            "team2_id": str(team2_id),
            "team1_score": user.team1_score,
            "team2_score": user.team2_score,
        }
    else:
        user_res = _save_game_result(
            team1_id,
            team2_id,
            user.team1_score,
            user.team2_score,
            req.week,
            franchise_id=req.franchise_id,
            game_id=user_game_id,
        )
    user_row = {
        "away_id": user_res["team1_id"],
        "home_id": user_res["team2_id"],
        "away_score": user_res["team1_score"],
        "home_score": user_res["team2_score"],
    }
    
    user_winner_id = team1_id if user.team1_score > user.team2_score else team2_id
    eos_matchup_for_user = eos_g_meta
    ch_game_id: str | None = None
    if eos_matchup_for_user is None and req.week in ft.EOS_WEEKS and week_games_meta:
        found_user_eos = ft.find_user_game_in_eos_week(week_games_meta, user_team_id_str)
        if found_user_eos:
            eos_matchup_for_user = found_user_eos[1]
    maybe_award_franchise_win_geek_points(
        owner_user_id=franchise_doc.get("user_id"),
        user_team_id_str=user_team_id_str,
        winner_team_id=user_winner_id,
        week=req.week,
        eos_game_meta=eos_matchup_for_user,
        bulk_sim_used=bulk_sim_used,
    )
    maybe_award_franchise_loss_geek_points(
        owner_user_id=franchise_doc.get("user_id"),
        user_team_id_str=user_team_id_str,
        winner_team_id=user_winner_id,
        participant_team_ids=(team1_id, team2_id),
        week=req.week,
        eos_game_meta=eos_matchup_for_user,
        bulk_sim_used=bulk_sim_used,
    )
    maybe_award_franchise_eos_title_championship(
        owner_user_id=franchise_doc.get("user_id"),
        user_team_id_str=user_team_id_str,
        winner_team_id=user_winner_id,
        week=req.week,
        eos_game_meta=eos_matchup_for_user,
    )
    
    # ✅ SS&S: Call finalize_game() with the actual gameplay game_id (if provided)
    # ✅ FIX: Use game_document from request if provided (eliminates race condition)
    # This matches Tournament mode pattern where game document is already available
    if user_game_id:
        logger.info(f"🔍 [COMPLETE_WEEK] Calling finalize_game() for user's game with provided game_id: {user_game_id}")
        
        # ✅ FIX: Use game_document from request if provided (returned from simulate-quarter when is_final=True)
        # This eliminates race condition where complete_week() is called before Q4 save completes
        if req.game_document:
            logger.info(f"✅ [COMPLETE_WEEK] Using game_document from request (no database lookup needed)")
            summary = req.game_document
            quarter = summary.get("quarter", "N/A")
            is_final = summary.get("is_final", False)
            logger.info(f"🔍 [COMPLETE_WEEK] game_document details: quarter={quarter}, is_final={is_final}, game_id={summary.get('_id') or summary.get('game_id')}")
            # Persist provided final snapshot so finalize/EOG read canonical data.
            # Exclude _id from payload to avoid immutable-field update errors.
            if isinstance(summary, dict):
                user_game_id = _persist_franchise_user_game_snapshot(
                    game_id=str(user_game_id),
                    payload=summary,
                    franchise_id=str(req.franchise_id),
                    week=req.week,
                    away_id=team1_id,
                    home_id=team2_id,
                )
        else:
            # Fallback: Look up from database (for backward compatibility)
            logger.info(f"🔍 [COMPLETE_WEEK] game_document not provided, looking up from database...")
            
            # ✅ DEBUG: Check all game documents with this game_id to see what quarters exist
            logger.info(f"🔍 [COMPLETE_WEEK] Checking all game documents with game_id: {user_game_id}")
            try:
                # Try to find all documents that might match (different formats)
                all_docs = []
                for lookup_id in [user_game_id, ObjectId(user_game_id) if ObjectId.is_valid(user_game_id) else None]:
                    if lookup_id:
                        doc = db.games.find_one({"_id": lookup_id})
                        if doc:
                            all_docs.append((lookup_id, doc))
                if all_docs:
                    for lookup_id, doc in all_docs:
                        quarter = doc.get("quarter", "N/A")
                        is_final = doc.get("is_final", False)
                        week = doc.get("week", "N/A")
                        home = doc.get("home_team", {}).get("name") if isinstance(doc.get("home_team"), dict) else doc.get("home_team", "N/A")
                        away = doc.get("away_team", {}).get("name") if isinstance(doc.get("away_team"), dict) else doc.get("away_team", "N/A")
                        logger.info(f"🔍 [COMPLETE_WEEK] Found document with _id={lookup_id}: quarter={quarter}, is_final={is_final}, week={week}, home={home}, away={away}")
                else:
                    logger.warning(f"⚠️ [COMPLETE_WEEK] No documents found with game_id: {user_game_id}")
            except Exception as e:
                logger.error(f"❌ [COMPLETE_WEEK] Error checking game documents: {e}")
            
            # ✅ SS&S: Replicate Tournament mode game document lookup pattern (with multiple fallback attempts)
            gid = (
                ObjectId(user_game_id)
                if ObjectId.is_valid(user_game_id)
                else user_game_id
            )
            logger.info(f"🔍 [COMPLETE_WEEK] User game - game_id from request: {user_game_id} (type: {type(user_game_id)}), converted gid: {gid} (type: {type(gid)})")
            
            # Try multiple formats to find the game document (matches Tournament mode pattern)
            summary = None
            # First try: Use gid as-is (ObjectId if conversion succeeded, string otherwise)
            summary = db.games.find_one({"_id": gid}) or {}
            if summary and summary.get("_id"):
                quarter = summary.get("quarter", "N/A")
                is_final = summary.get("is_final", False)
                logger.info(f"🔍 [COMPLETE_WEEK] First try found document: quarter={quarter}, is_final={is_final}")
            if not summary or not summary.get("_id"):
                logger.warning(f"⚠️ [COMPLETE_WEEK] Game not found with gid={gid}, trying string format")
                # Second try: Use string format
                try:
                    summary = db.games.find_one({"_id": user_game_id}) or {}
                    if summary and summary.get("_id"):
                        quarter = summary.get("quarter", "N/A")
                        is_final = summary.get("is_final", False)
                        logger.info(f"🔍 [COMPLETE_WEEK] Second try found document: quarter={quarter}, is_final={is_final}")
                except Exception:
                    pass
            if not summary or not summary.get("_id"):
                logger.warning(f"⚠️ [COMPLETE_WEEK] Game not found with string format, trying ObjectId conversion")
                # Third try: Convert string to ObjectId
                try:
                    oid = ObjectId(user_game_id)
                    summary = db.games.find_one({"_id": oid}) or {}
                    if summary and summary.get("_id"):
                        gid = summary.get("_id")
                        quarter = summary.get("quarter", "N/A")
                        is_final = summary.get("is_final", False)
                        logger.info(f"✅ [COMPLETE_WEEK] Found game document using ObjectId conversion: {gid}, quarter={quarter}, is_final={is_final}")
                except Exception as e:
                    logger.error(f"❌ [COMPLETE_WEEK] Error converting game_id to ObjectId: {e}")
            
            logger.info(f"🔍 [COMPLETE_WEEK] User game - Final lookup result: Found={bool(summary and summary.get('_id'))}, _id={summary.get('_id') if summary else None}")
            if summary and summary.get("_id"):
                quarter = summary.get("quarter", "N/A")
                is_final = summary.get("is_final", False)
                logger.info(f"🔍 [COMPLETE_WEEK] Final document details: quarter={quarter}, is_final={is_final}, week={summary.get('week', 'N/A')}")
            
            if not summary or not summary.get("_id"):
                logger.error(f"❌ [COMPLETE_WEEK] Game document not found in games_collection after all attempts. game_id: {user_game_id}, gid: {gid}")
                logger.error(f"❌ [COMPLETE_WEEK] This likely means the game document was never saved to the database.")
                logger.error(f"❌ [COMPLETE_WEEK] Check if simulate_quarter_endpoint successfully saved the game document.")
                raise HTTPException(status_code=404, detail="User game not found in database")
        
        # ✅ SS&S: Call finalize_game() directly (matches Tournament mode pattern)
        # Use game_id from request when we have game_document (avoids _id JSON serialization:
        # game_document._id can be {"$oid":"..."}; str() → invalid id → ObjectId() throws → we never $set)
        if req.game_document:
            user_game_id_final = user_game_id
        elif summary and summary.get("_id"):
            user_game_id_final = str(summary["_id"])  # From DB lookup; _id is ObjectId
        else:
            user_game_id_final = user_game_id
        
        logger.info(f"🎯 [COMPLETE_WEEK] Finalizing user's game (matches Tournament pattern) - game_id: {user_game_id_final}")
        logger.info(f"🔍 [COMPLETE_WEEK] Document being passed to finalize_game: quarter={summary.get('quarter', 'N/A')}, is_final={summary.get('is_final', False)}")
        stat_updater.finalize_game(
            user_game_id_final,
            mode="franchise",
            franchise_id=req.franchise_id,
        )
        logger.info(f"✅ [COMPLETE_WEEK] User game - finalize_game completed for game_id: {user_game_id_final}")
    
        # Recompute team attribute changes every time complete_week runs.
        # This prevents stale team_attribute_changes from bypassing new EOG logic.
        logger.warning(
            "🧭 [COMPLETE-WEEK-EOG] Recomputing team_attribute_changes for user game_id=%s",
            user_game_id_final,
        )
        home_id_raw = user_res["team2_id"]
        away_id_raw = user_res["team1_id"]
        home_id = _normalize_team_id_to_string(home_id_raw) or str(home_id_raw)
        away_id = _normalize_team_id_to_string(away_id_raw) or str(away_id_raw)
        home_score = user_res["team2_score"]
        away_score = user_res["team1_score"]
        if home_score > away_score:
            winner_id, loser_id = home_id, away_id
            winner_score, loser_score = home_score, away_score
        else:
            winner_id, loser_id = away_id, home_id
            winner_score, loser_score = away_score, home_score
        _finalize_team_attributes_for_game(
            game_id=user_game_id_final,
            franchise_id=franchise_id,
            home_team_id=home_id,
            away_team_id=away_id,
            winner_id=winner_id,
            loser_id=loser_id,
            winner_score=winner_score,
            loser_score=loser_score,
            week=req.week,
        )
        season_inbox = list(franchise_doc.get("season_inbox") or [])
        game_doc_for_inbox = summary if isinstance(summary, dict) else {}
        home_team_name = (
            game_doc_for_inbox.get("home_team", {}).get("name")
            if isinstance(game_doc_for_inbox.get("home_team"), dict)
            else game_doc_for_inbox.get("home_team")
        ) or _resolve_team_name_from_any(home_id)
        away_team_name = (
            game_doc_for_inbox.get("away_team", {}).get("name")
            if isinstance(game_doc_for_inbox.get("away_team"), dict)
            else game_doc_for_inbox.get("away_team")
        ) or _resolve_team_name_from_any(away_id)
        inbox_entry = _build_franchise_game_inbox_entry(
            franchise_id=str(req.franchise_id),
            user_team_name=_u_name,
            user_team_object_id=user_team_id_str,
            game_id=str(user_game_id_final),
            home_team_id=home_id,
            away_team_id=away_id,
            home_team_name=home_team_name,
            away_team_name=away_team_name,
            home_score=home_score,
            away_score=away_score,
            week=req.week,
        )
        if inbox_entry:
            season_inbox = [item for item in season_inbox if str(item.get("game_id") or "") != str(user_game_id_final)]
            season_inbox.insert(0, inbox_entry)
            franchise_doc["season_inbox"] = season_inbox
        ch_game_id = str(user_game_id_final)
    else:
        # Fallback: Try to find game by week + team IDs (legacy behavior)
        logger.warning(f"⚠️ [COMPLETE_WEEK] No game_id provided, attempting legacy lookup: week={req.week}, team1_id={team1_id}, team2_id={team2_id}, franchise_id={req.franchise_id}")
        user_game = db.games.find_one({
            "week": req.week,
            "$or": [
                {"team1_id": team1_id, "team2_id": team2_id},
                {"team1_id": team2_id, "team2_id": team1_id},
            ],
            "franchise_id": str(req.franchise_id)
        })
        if user_game:
            user_game_id = str(user_game.get("_id", ""))
            logger.info(f"✅ [COMPLETE_WEEK] Found user's game via legacy lookup: game_id={user_game_id}")
            if user_game_id:
                _save_user_eos_bracket_result(
                    franchise_doc,
                    week_games_meta=week_games_meta,
                    user_team_id_str=user_team_id_str,
                    team1_id=team1_id,
                    team2_id=team2_id,
                    team1_score=user.team1_score,
                    team2_score=user.team2_score,
                    game_id=user_game_id,
                    week=req.week,
                    franchise_id_str=str(req.franchise_id),
                )
                logger.info(f"🔍 [COMPLETE_WEEK] Calling finalize_game() for user's game: game_id={user_game_id}")
                stat_updater.finalize_game(
                    user_game_id, mode="franchise", franchise_id=req.franchise_id
                )
                logger.info(f"✅ [COMPLETE_WEEK] User game - finalize_game completed for game_id: {user_game_id}")
                # Legacy lookup path: also recompute every time for consistency.
                logger.warning(
                    "🧭 [COMPLETE-WEEK-EOG] Recomputing team_attribute_changes for legacy user game_id=%s",
                    user_game_id,
                )
                home_id_raw = user_res["team2_id"]
                away_id_raw = user_res["team1_id"]
                home_id = _normalize_team_id_to_string(home_id_raw) or str(home_id_raw)
                away_id = _normalize_team_id_to_string(away_id_raw) or str(away_id_raw)
                home_score = user_res["team2_score"]
                away_score = user_res["team1_score"]
                if home_score > away_score:
                    winner_id, loser_id = home_id, away_id
                    winner_score, loser_score = home_score, away_score
                else:
                    winner_id, loser_id = away_id, home_id
                    winner_score, loser_score = away_score, home_score
                _finalize_team_attributes_for_game(
                    game_id=user_game_id,
                    franchise_id=franchise_id,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    winner_id=winner_id,
                    loser_id=loser_id,
                    winner_score=winner_score,
                    loser_score=loser_score,
                    week=req.week,
                )
                season_inbox = list(franchise_doc.get("season_inbox") or [])
                inbox_entry = _build_franchise_game_inbox_entry(
                    franchise_id=str(req.franchise_id),
                    user_team_name=_u_name,
                    user_team_object_id=user_team_id_str,
                    game_id=str(user_game_id),
                    home_team_id=home_id,
                    away_team_id=away_id,
                    home_team_name=_resolve_team_name_from_any(home_id),
                    away_team_name=_resolve_team_name_from_any(away_id),
                    home_score=home_score,
                    away_score=away_score,
                    week=req.week,
                )
                if inbox_entry:
                    season_inbox = [item for item in season_inbox if str(item.get("game_id") or "") != str(user_game_id)]
                    season_inbox.insert(0, inbox_entry)
                    franchise_doc["season_inbox"] = season_inbox
                ch_game_id = str(user_game_id)
            else:
                logger.error(f"❌ [COMPLETE_WEEK] User game found but _id is empty: {user_game}")
        else:
            logger.error(f"❌ [COMPLETE_WEEK] User's game not found in games collection. Query: week={req.week}, team1_id={team1_id}, team2_id={team2_id}, franchise_id={req.franchise_id}")

    # Flag a coaching-archetype change (established for the first time, or evolved)
    # now that finalize_game has folded this game's archetype periods into the
    # user's counters. No-op when the lead archetype didn't change.
    record_archetype_change_if_any(franchise_id, archetype_owner_user_id, lead_archetype_before)

    gp_delta = user_geek_points_delta_for_user_game_block(franchise_doc, gp_before)
    return user_res, user_row, gp_delta, eos_matchup_for_user, ch_game_id


def _sync_eos_bracket_from_existing_game_doc(
    franchise_doc: dict,
    *,
    existing: dict,
    away_id: Any,
    home_id: Any,
    g: dict[str, Any],
    week: int | None = None,
    franchise_id_str: str | None = None,
) -> None:
    """Write EOS bracket winner/scores from an already-saved games row.

    When ``complete_week`` hits ``existing`` it used to ``continue`` without updating the
    in-memory bracket, so ``advance_bracket`` saw fewer than four R1 winners (e.g. 3/4).

    Delegates to ``franchise_tournament_progression.record_tournament_game_result`` with
    ``source="existing_games"`` (bracket only; ``games`` row is already authoritative).
    """
    ex_id = existing.get("_id")
    gid = str(ex_id) if ex_id is not None else ""
    t1 = existing.get("team1_id")
    t2 = existing.get("team2_id")
    s1 = int(existing.get("team1_score", 0) or 0)
    s2 = int(existing.get("team2_score", 0) or 0)
    ca = ft._eos_team_id_canonical(away_id)
    ch = ft._eos_team_id_canonical(home_id)
    c1 = ft._eos_team_id_canonical(t1)
    c2 = ft._eos_team_id_canonical(t2)
    if c1 == ca and c2 == ch:
        away_s, home_s = s1, s2
    elif c1 == ch and c2 == ca:
        away_s, home_s = s2, s1
    else:
        logger.warning(
            "[EOS-BRACKET-DEBUG] existing_game_team_order_unexpected c1=%s c2=%s ca=%s ch=%s raw_t1=%s raw_t2=%s",
            c1,
            c2,
            ca,
            ch,
            t1,
            t2,
        )
        away_s, home_s = s1, s2
    if home_s > away_s:
        winner_raw = home_id
    elif away_s > home_s:
        winner_raw = away_id
    else:
        winner_raw = home_id
    wid = ft._eos_team_id_canonical(winner_raw) or str(winner_raw)
    logger.warning(
        "[EOS-BRACKET-DEBUG] sync_from_existing_apply winner=%s home_s=%s away_s=%s phase=%s",
        wid[:16] if wid else "",
        home_s,
        away_s,
        g.get("phase"),
    )
    wk = week if week is not None else existing.get("week")
    if wk is None:
        ph = g.get("phase")
        if ph == "conference":
            wk = 26 + int(g.get("round", 1) or 1)
        elif ph == "region":
            wk = 30 if int(g.get("round", 1) or 1) == 1 else 31
        elif ph == "national":
            wk = 31 + int(g.get("round", 1) or 1)
        else:
            wk = 27
    fid = franchise_id_str or str(existing.get("franchise_id") or "") or str(franchise_doc.get("_id") or "")
    g_full = dict(g)
    g_full.setdefault("away_id", away_id)
    g_full.setdefault("home_id", home_id)
    ftp.record_tournament_game_result(
        franchise_doc,
        g_full,
        week=int(wk),
        franchise_id_str=fid or "000000000000000000000000",
        game_id=gid or None,
        team1_id=away_id,
        team2_id=home_id,
        team1_score=away_s,
        team2_score=home_s,
        source="existing_games",
        skip_games_upsert=True,
    )


def _sync_eos_bracket_from_result_row(
    franchise_doc: dict,
    *,
    row: dict,
    away_id: Any,
    home_id: Any,
    week: int,
    franchise_id_str: str,
    g: dict[str, Any],
) -> None:
    """Write EOS bracket winner/scores from an already-completed results row.

    Some phase-B retries can see a completed franchise ``results.week`` row before a
    matching ``games`` document exists. In that case, preserve the actual completed
    score and create a minimal game record so the bracket gets both winner and game_id.
    """
    row_away = row.get("away_id")
    row_home = row.get("home_id")
    row_away_s = int(row.get("away_score", 0) or 0)
    row_home_s = int(row.get("home_score", 0) or 0)
    sched_away = str(away_id)
    sched_home = str(home_id)

    if str(row_away) == sched_away and str(row_home) == sched_home:
        away_s, home_s = row_away_s, row_home_s
    elif str(row_away) == sched_home and str(row_home) == sched_away:
        away_s, home_s = row_home_s, row_away_s
    else:
        logger.warning(
            "[EOS-BRACKET-DEBUG] result_row_team_order_unexpected row_away=%s row_home=%s sched_away=%s sched_home=%s",
            row_away,
            row_home,
            sched_away,
            sched_home,
        )
        away_s, home_s = row_away_s, row_home_s

    game_id = generate_game_id()
    _save_game_result(
        away_id,
        home_id,
        away_s,
        home_s,
        week,
        franchise_id=franchise_id_str,
        game_id=game_id,
    )
    winner_raw = home_id if home_s >= away_s else away_id
    wid = ft._eos_team_id_canonical(winner_raw) or str(winner_raw)
    logger.warning(
        "[EOS-BRACKET-DEBUG] sync_from_result_row_apply winner=%s home_s=%s away_s=%s phase=%s conf=%s round=%s midx=%s game_id=%s",
        wid[:16] if wid else "",
        home_s,
        away_s,
        g.get("phase"),
        g.get("conference") or g.get("region"),
        g.get("round"),
        g.get("matchup_index"),
        game_id[:12],
    )
    g_full = dict(g)
    g_full.setdefault("away_id", away_id)
    g_full.setdefault("home_id", home_id)
    ftp.record_tournament_game_result(
        franchise_doc,
        g_full,
        week=week,
        franchise_id_str=franchise_id_str,
        game_id=game_id,
        team1_id=away_id,
        team2_id=home_id,
        team1_score=away_s,
        team2_score=home_s,
        source="existing_results",
        skip_games_upsert=True,
    )


def _eos_calendar_advance_update_fields(
    franchise_doc: dict[str, Any],
    franchise_id: ObjectId,
    completed_week: int,
    *,
    franchise_id_str: str | None = None,
    log_conference_bracket_snapshots: bool = False,
) -> dict[str, Any]:
    """
    Single funnel for the EOS franchise calendar step after a completed EOS week (27-34):
    mutates tournament state on ``franchise_doc`` and returns ``$set`` fragments
    (``week``, bracket fields, ``eos_tournament_active``). Does not set ``results`` or training.

    Used by ``_finalize_franchise_week_after_cpu_games`` and ``sim_rest_of_tournament``.

    Other writers (heal, repair, ``sim-championship``) are listed in
    ``_documentation_master/06_GMO_Supporting_Systems/EOS_Write_Path_Inventory.md``.
    """
    if completed_week not in ft.EOS_WEEKS:
        return {}

    out: dict[str, Any] = {}

    if completed_week in ft.EOS_CONFERENCE_WEEKS:
        if log_conference_bracket_snapshots and franchise_id_str:
            ft.log_eos_conference_bracket_snapshot(
                franchise_doc,
                f"complete_week_pre_advance week={completed_week} fid={franchise_id_str}",
            )
        for c in range(1, 17):
            ftp.advance_conference_bracket(franchise_doc, c)
        if log_conference_bracket_snapshots and franchise_id_str:
            ft.log_eos_conference_bracket_snapshot(
                franchise_doc,
                f"complete_week_post_advance week={completed_week} fid={franchise_id_str}",
            )
        next_w = completed_week + 1
        if completed_week == ft.EOS_CONFERENCE_WEEKS[-1]:
            eos_team_ids = [
                d["team_id"]
                for d in franchise_team_data_collection.find(
                    {"franchise_id": franchise_id}, {"team_id": 1}
                )
                if d.get("team_id")
            ]
            region_tournaments = ft.initialize_region_tournaments(
                franchise_doc, db.teams, team_ids=eos_team_ids
            )
            out["region_tournaments"] = region_tournaments
            next_w = ft.EOS_REGION_WEEKS[0]
        out["week"] = next_w
        out["conference_tournaments"] = franchise_doc.get("conference_tournaments", {})
    elif completed_week in ft.EOS_REGION_WEEKS:
        if completed_week == ft.EOS_REGION_WEEKS[-1]:
            region_champions = ft.get_region_champions(franchise_doc)
            ftd_docs = list(
                franchise_team_data_collection.find(
                    {"franchise_id": franchise_id}, {"team_id": 1}
                )
            )
            team_ids = [d["team_id"] for d in ftd_docs if d.get("team_id")]
            national_tournament = ft.initialize_national_tournament(
                franchise_doc,
                db.teams,
                region_champions,
                franchise_doc.get("results", {}),
                team_ids,
            )
            out["national_tournament"] = national_tournament
            next_w = ft.EOS_NATIONAL_WEEKS[0]
        else:
            next_w = ft.EOS_REGION_WEEKS[1]
        out["week"] = next_w
        out["region_tournaments"] = franchise_doc.get("region_tournaments", {})
    elif completed_week in ft.EOS_NATIONAL_WEEKS:
        ftp.advance_national_bracket(franchise_doc)
        out["national_tournament"] = franchise_doc.get("national_tournament", {})
        if completed_week == ft.EOS_NATIONAL_WEEKS[-1]:
            out["eos_tournament_active"] = False
            out["week"] = 35
        else:
            out["week"] = ft.EOS_NATIONAL_WEEKS[ft.EOS_NATIONAL_WEEKS.index(completed_week) + 1]
    return out


def _finalize_franchise_week_after_cpu_games(
    franchise_doc: dict,
    franchise_id: ObjectId,
    franchise_id_str: str,
    week: int,
    results: list,
    user_team_id_str: Any,
    community_highlight_pending: dict | None = None,
) -> dict:
    """
    Phase 1 week-closure extraction: everything that ran sequentially after the CPU sim loop
    in ``_complete_week_finish_cpu_and_persist``. Requires a full ``results`` list for ``week``
    (user row from phase A + all CPU rows). Mutates ``franchise_doc`` for recruiting / rank /
    EOS; persists franchise and follow-up hooks. Same behavior as the inlined block it replaced.
    """
    existing_results = franchise_doc.get("results", {})
    existing_results[str(week)] = results
    new_lean_events = _apply_performance_based_recruiting_lean_updates(franchise_doc, week, results)
    new_lean_events += _apply_complete_week_recruiting_lean_updates(franchise_doc, week, results)
    # Training-squad weekly progression (weeks 2–26) + milestone development report.
    ts_weekly_gains: list[dict[str, Any]] = []
    try:
        ts_weekly_gains = _apply_training_squad_progression_and_report(
            franchise_id, franchise_doc, week, user_team_id_str
        ) or []
    except Exception:
        logger.exception(
            "[TS-PROGRESSION] failed; continuing. franchise_id=%s week=%s",
            franchise_id_str, week,
        )
    # Weekly news (upset report + practice-squad all-stars + recruiting leans).
    # PS game-results news publishes at distant-CPU training, not here.
    # Must run before the rank update below so the upset criteria use
    # entering-week natl_rank values.
    try:
        _append_franchise_week_news(
            franchise_id, franchise_doc, week, results, ts_weekly_gains, new_lean_events
        )
    except Exception:
        logger.exception(
            "[NEWS] weekly news generation failed; continuing. franchise_id=%s week=%s",
            franchise_id_str, week,
        )
    try:
        _apply_regular_season_rank_prestige_updates(franchise_id, franchise_doc, week, results)
    except Exception:
        logger.exception(
            "❌ [COMPLETE-WEEK] Rank/prestige update failed; continuing with franchise week/results persistence. franchise_id=%s week=%s results_count=%s",
            franchise_id_str,
            week,
            len(results),
        )

    next_week = week + 1

    update_fields = {
        "results": existing_results,
        "week": next_week,
        "season_inbox": franchise_doc.get("season_inbox", []),
    }
    # Persist training-squad report state if the progression hook wrote any.
    if "training_squad_reports" in franchise_doc:
        update_fields["training_squad_reports"] = franchise_doc["training_squad_reports"]
    if "training_squad_report_baseline" in franchise_doc:
        update_fields["training_squad_report_baseline"] = franchise_doc["training_squad_report_baseline"]
    if "season_news" in franchise_doc:
        update_fields["season_news"] = franchise_doc["season_news"]

    if week == ScheduleManager.REGULAR_SEASON_WEEKS:
        ftd_docs = list(
            franchise_team_data_collection.find(
                {"franchise_id": franchise_id},
                {"team_id": 1},
            )
        )
        eos_team_ids = [doc["team_id"] for doc in ftd_docs if doc.get("team_id")]
        if len(eos_team_ids) < 128:
            logger.warning(
                "⚠️ [EOS] Fewer than 128 teams in FTD (got %s); conference brackets may be incomplete.",
                len(eos_team_ids),
            )
        franchise_doc["results"] = existing_results
        conference_tournaments = ft.initialize_conference_tournaments(
            franchise_doc, db.teams, team_ids=eos_team_ids
        )
        update_fields["conference_tournaments"] = conference_tournaments
        update_fields["eos_tournament_active"] = True
        update_fields["week"] = ft.EOS_CONFERENCE_WEEKS[0]
        logger.info("✅ [EOS] Conference tournaments initialized, week set to 27")
        maybe_award_conference_rs_championship(
            owner_user_id=franchise_doc.get("user_id"),
            user_team_id_str=user_team_id_str,
            conference_tournaments=conference_tournaments,
        )
        try:
            from BackEnd.utils.franchise_championship_moments import (
                enqueue_trophy_spotlight_for_user_conference,
            )

            franchise_doc["conference_tournaments"] = conference_tournaments
            enqueue_trophy_spotlight_for_user_conference(franchise_doc)
        except Exception:
            logger.exception(
                "[CHAMP-MOMENT] trophy_spotlight enqueue failed franchise_id=%s",
                franchise_id_str,
            )
    elif week in ft.EOS_WEEKS:
        eos_updates = _eos_calendar_advance_update_fields(
            franchise_doc,
            franchise_id,
            week,
            franchise_id_str=franchise_id_str,
            log_conference_bracket_snapshots=True,
        )
        update_fields.update(eos_updates)
    ts_reset = _training_status_reset_after_advance_to_week(update_fields.get("week"))
    if ts_reset:
        update_fields.update(ts_reset)
    logger.warning(
        "🧭 [COMPLETE-WEEK-PERSIST] Persisting franchise week/results update. franchise_id=%s completed_week=%s next_week=%s results_count=%s update_keys=%s",
        franchise_id_str,
        week,
        update_fields.get("week"),
        len(results),
        sorted(update_fields.keys()),
    )
    update_fields["post_game_status.phase_a_user_week"] = None
    if community_highlight_pending is not None:
        update_fields["post_game_status.community_highlight_pending"] = community_highlight_pending
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": update_fields},
    )
    try:
        flush_community_highlight_pending_after_week(franchise_id, week)
    except Exception:
        logger.exception(
            "[COMMUNITY_HIGHLIGHTS] flush after week persist failed franchise_id=%s week=%s",
            franchise_id_str,
            week,
        )
    if update_fields.get("week") == 35:
        refreshed = db.franchises.find_one({"_id": franchise_id})
        if refreshed:
            _persist_week_35_awards_if_needed(refreshed)

    id_to_name = {str(t["_id"]): t.get("name", "") for t in db.teams.find({}, {"name": 1})}
    scoreboard = []
    for r in results:
        scoreboard.append(
            {
                "team1": id_to_name.get(r["away_id"], r["away_id"]),
                "team2": id_to_name.get(r["home_id"], r["home_id"]),
                "team1_score": r["away_score"],
                "team2_score": r["home_score"],
            }
        )

    return {"week": week, "results": scoreboard}


def _eos_result_pair_key(away_id: Any, home_id: Any) -> frozenset:
    return frozenset({ft._eos_team_id_canonical(away_id), ft._eos_team_id_canonical(home_id)})


def _eos_sync_missing_result_rows_from_games_for_week(
    franchise_id_str: str,
    franchise_doc: dict,
    week: int,
) -> int:
    """
    Append ``results.{week}`` rows for EOS matchups that have a ``games`` doc but no results row.

    Fixes W/L display (``calculate_franchise_standings``) when the user game hit ``games`` + bracket
    but never landed in ``franchise.results`` (e.g. repair-from-games or partial phase-A).
    """
    if week not in ft.EOS_WEEKS:
        return 0
    wk = str(int(week))
    results_root = dict(franchise_doc.get("results") or {})
    week_list = list(results_root.get(wk) or [])
    keys_present = {_eos_result_pair_key(r.get("away_id"), r.get("home_id")) for r in week_list if isinstance(r, dict)}
    meta = ft.get_eos_week_games(franchise_doc, int(week), include_completed=True)
    n_added = 0
    for g in meta:
        if g.get("phase") not in ("conference", "region", "national"):
            continue
        away_id, home_id = g.get("away_id"), g.get("home_id")
        slot_key = _eos_result_pair_key(away_id, home_id)
        if slot_key in keys_present:
            continue
        existing = db.games.find_one(
            {
                "week": int(week),
                "franchise_id": franchise_id_str,
                "$or": [
                    {"team1_id": away_id, "team2_id": home_id},
                    {"team1_id": home_id, "team2_id": away_id},
                ],
            }
        )
        if not existing:
            continue
        t1 = existing.get("team1_id")
        t2 = existing.get("team2_id")
        s1 = int(existing.get("team1_score", 0) or 0)
        s2 = int(existing.get("team2_score", 0) or 0)
        ca = ft._eos_team_id_canonical(away_id)
        ch = ft._eos_team_id_canonical(home_id)
        c1 = ft._eos_team_id_canonical(t1)
        c2 = ft._eos_team_id_canonical(t2)
        if c1 == ca and c2 == ch:
            away_s, home_s = s1, s2
        elif c1 == ch and c2 == ca:
            away_s, home_s = s2, s1
        else:
            logger.warning(
                "[EOS-CATCH-UP] game_team_order_unexpected week=%s franchise_id=%s c1=%s c2=%s ca=%s ch=%s",
                week,
                franchise_id_str,
                c1,
                c2,
                ca,
                ch,
            )
            away_s, home_s = s1, s2
        week_list.append(
            {
                "away_id": ca,
                "home_id": ch,
                "away_score": away_s,
                "home_score": home_s,
            }
        )
        keys_present.add(slot_key)
        n_added += 1
    if n_added:
        results_root[wk] = week_list
        franchise_doc["results"] = results_root
    return n_added


def _eos_sync_bracket_slots_from_games_for_week(
    franchise_id_str: str,
    franchise_doc: dict,
    week: int,
) -> int:
    """
    For each EOS ``week`` calendar matchup with no bracket ``winner``, apply
    ``_sync_eos_bracket_from_existing_game_doc`` when a ``games`` row exists.

    Covers **R1, semis, and finals** (calendar weeks 27–29); fixes the user semi stuck at
    ``game_id: null`` while the CPU semi completed.
    """
    if week not in ft.EOS_WEEKS:
        return 0
    n = 0
    meta = ft.get_eos_week_games(franchise_doc, int(week), include_completed=True)
    for g in meta:
        if not isinstance(g, dict) or g.get("phase") not in ("conference", "region", "national"):
            continue
        if ft.eos_meta_bracket_slot_has_winner(franchise_doc, g):
            continue
        away_id, home_id = g.get("away_id"), g.get("home_id")
        existing = db.games.find_one(
            {
                "week": int(week),
                "franchise_id": franchise_id_str,
                "$or": [
                    {"team1_id": away_id, "team2_id": home_id},
                    {"team1_id": home_id, "team2_id": away_id},
                ],
            }
        )
        if not existing:
            continue
        _sync_eos_bracket_from_existing_game_doc(
            franchise_doc,
            existing=existing,
            away_id=away_id,
            home_id=home_id,
            g=g,
            week=int(week),
            franchise_id_str=franchise_id_str,
        )
        n += 1
    return n


def _eos_advance_all_conference_brackets_until_idle(franchise_doc: dict) -> int:
    """Repeatedly ``advance_conference_bracket`` (R1→R2→final) until no conference moves."""
    steps = 0
    for c in range(1, 17):
        for _ in range(4):
            advanced, _ch = ftp.advance_conference_bracket(franchise_doc, c)
            if not advanced:
                break
            steps += 1
    return steps


def _eos_advance_national_bracket_until_idle(franchise_doc: dict) -> int:
    """Repeatedly ``advance_national_bracket`` (R1→R2→final) until idle."""
    steps = 0
    for _ in range(4):
        advanced, _ch = ftp.advance_national_bracket(franchise_doc)
        if not advanced:
            break
        steps += 1
    return steps


# Region brackets do not have a separate "advance" step: ``save_region_game_result``
# fills the final slot from R1 winners directly when each R1 cell is written, so
# bracket-slot sync is sufficient to "advance" region. ``advance_region_bracket``
# only reports the champion when the final has a winner.


def _eos_heal_phase_from_games(
    franchise_id: ObjectId,
    franchise_id_str: str,
    *,
    weeks: tuple[int, ...],
    bracket_field: str,
    advance_until_idle,
    log_label: str,
) -> dict[str, Any]:
    """
    Generic EOS heal: backfill ``results`` rows + bracket slots from ``games`` for the
    given ``weeks`` (filtered to ≤ franchise.week), then run ``advance_until_idle``.

    Used by all three phases — conference, region, national. Persists ``results`` and
    the relevant bracket field (``conference_tournaments`` / ``region_tournaments`` /
    ``national_tournament``) only when something actually changed.
    """
    out: dict[str, Any] = {
        "did_work": False,
        "results_rows_added": 0,
        "bracket_slots_synced": 0,
        "advance_steps": 0,
    }
    fresh = db.franchises.find_one({"_id": franchise_id})
    if not fresh:
        return out
    cw = int(fresh.get("week") or 1)
    rows_total = 0
    slots_total = 0
    for w in weeks:
        if w > cw:
            continue
        rows_total += _eos_sync_missing_result_rows_from_games_for_week(franchise_id_str, fresh, int(w))
        slots_total += _eos_sync_bracket_slots_from_games_for_week(franchise_id_str, fresh, int(w))
    if log_label == "conference":
        ft.log_eos_conference_bracket_snapshot(fresh, f"eos_heal_pre_idle fid={franchise_id_str}")
    adv_steps = advance_until_idle(fresh) if advance_until_idle else 0
    if log_label == "conference":
        ft.log_eos_conference_bracket_snapshot(fresh, f"eos_heal_post_idle fid={franchise_id_str}")
    if rows_total == 0 and slots_total == 0 and adv_steps == 0:
        return out
    patch: dict[str, Any] = {}
    if rows_total:
        patch["results"] = fresh.get("results") or {}
    if slots_total or adv_steps:
        patch[bracket_field] = fresh.get(bracket_field) or ({} if bracket_field != "national_tournament" else {})
    db.franchises.update_one({"_id": franchise_id}, {"$set": patch})
    out["did_work"] = True
    out["results_rows_added"] = rows_total
    out["bracket_slots_synced"] = slots_total
    out["advance_steps"] = adv_steps
    logger.warning(
        "🧭 [EOS-HEAL] phase=%s franchise_id=%s calendar_week=%s results_rows_added=%s bracket_slots_synced=%s advance_steps=%s",
        log_label,
        franchise_id_str,
        cw,
        rows_total,
        slots_total,
        adv_steps,
    )
    return out


def _eos_heal_conference_eos_from_games(franchise_id: ObjectId, franchise_id_str: str) -> dict[str, Any]:
    """
    Backfill ``results`` + bracket from ``games`` for conference EOS weeks **≤ franchise.week**,
    then advance all conference brackets as far as outcomes allow.

    Runs at the start of ``complete_week_phase_b`` so a stuck **user semi** (week 28 meta) still
    heals when ``franchise.week`` is already **29** (calendar ahead of bracket).
    """
    return _eos_heal_phase_from_games(
        franchise_id,
        franchise_id_str,
        weeks=ft.EOS_CONFERENCE_WEEKS,
        bracket_field="conference_tournaments",
        advance_until_idle=_eos_advance_all_conference_brackets_until_idle,
        log_label="conference",
    )


def _eos_heal_region_eos_from_games(franchise_id: ObjectId, franchise_id_str: str) -> dict[str, Any]:
    """
    Backfill ``results`` + bracket from ``games`` for region EOS weeks (30, 31).

    Region final slots are filled in-line by ``save_region_game_result`` when R1 cells
    are written, so the bracket-slot sync alone is enough to "advance" the bracket.
    Mirrors ``_eos_heal_conference_eos_from_games`` so region/national user-game misses
    self-heal at the start of the next phase-b instead of staying broken until manual
    repair. Closes the heal-coverage gap that previously affected weeks 30–31.
    """
    return _eos_heal_phase_from_games(
        franchise_id,
        franchise_id_str,
        weeks=ft.EOS_REGION_WEEKS,
        bracket_field="region_tournaments",
        advance_until_idle=None,
        log_label="region",
    )


def _eos_heal_national_eos_from_games(franchise_id: ObjectId, franchise_id_str: str) -> dict[str, Any]:
    """
    Backfill ``results`` + bracket from ``games`` for national EOS weeks (32, 33, 34),
    then advance the national bracket as far as outcomes allow.

    Mirrors ``_eos_heal_conference_eos_from_games`` for national. Closes the
    heal-coverage gap that previously affected weeks 32–34.
    """
    return _eos_heal_phase_from_games(
        franchise_id,
        franchise_id_str,
        weeks=ft.EOS_NATIONAL_WEEKS,
        bracket_field="national_tournament",
        advance_until_idle=_eos_advance_national_bracket_until_idle,
        log_label="national",
    )


def _eos_heal_all_eos_from_games(franchise_id: ObjectId, franchise_id_str: str) -> dict[str, Any]:
    """
    Run all three EOS heals (conference, region, national) and aggregate their summary.

    Order matters: conference heal runs first because conference R1/R2/final winners
    feed region brackets via ``initialize_region_tournaments``; region winners feed
    national via ``initialize_national_tournament``. Heals are individually idempotent.
    """
    conf = _eos_heal_conference_eos_from_games(franchise_id, franchise_id_str)
    region = _eos_heal_region_eos_from_games(franchise_id, franchise_id_str)
    national = _eos_heal_national_eos_from_games(franchise_id, franchise_id_str)
    return {
        "did_work": bool(conf.get("did_work") or region.get("did_work") or national.get("did_work")),
        "conference": conf,
        "region": region,
        "national": national,
    }


def _try_finalize_franchise_week_if_complete(
    franchise_doc: dict,
    franchise_id: ObjectId,
    franchise_id_str: str,
    week: int,
    week_games: list,
    results: list,
    user_team_id_str: Any,
    community_highlight_pending: dict | None = None,
) -> dict | None:
    """
    Run week closure only when ``results`` holds one outcome per ``week_games`` slot.
    Used after the CPU loop today; later, parallel workers can call this after each merge.
    """
    deduped = _dedupe_franchise_week_results_by_matchup(results)
    if not _franchise_week_results_cover_schedule(deduped, week_games):
        expected = _expected_franchise_week_matchup_key_set(week_games)
        actual = {_week_result_matchup_key(r) for r in deduped}
        missing_n = len(expected - actual)
        extra_n = len(actual - expected)
        logger.info(
            "[TRY-FINALIZE-WEEK] outcome=waiting franchise_id=%s week=%s "
            "expected_matchups=%s deduped_rows=%s missing_matchups=%s extra_matchups=%s",
            franchise_id_str,
            week,
            len(expected),
            len(deduped),
            missing_n,
            extra_n,
        )
        return None
    out = _finalize_franchise_week_after_cpu_games(
        franchise_doc,
        franchise_id,
        franchise_id_str,
        week,
        deduped,
        user_team_id_str,
        community_highlight_pending,
    )
    logger.info(
        "[TRY-FINALIZE-WEEK] outcome=ran_closure franchise_id=%s week=%s deduped_matchups=%s",
        franchise_id_str,
        week,
        len(deduped),
    )
    return out


# Shot-diagnostic keys stamped onto a game summary by ``summarize_game_state``.
# The week-aggregate roll-up needs only these four; slimming keeps the persisted
# stash small (the full CPU summary is large).
_SHOT_DIAG_KEYS = (
    "shot_split_tracking",
    "fga_by_turn_type",
    "undefended_by_turn_type",
    "hco_shot_tier_counts",
)


def _slim_shot_diag(summary: dict | None) -> dict | None:
    """Extract just the shot-diagnostic keys from a game summary. Returns None when
    the summary carries no usable diagnostics."""
    if not isinstance(summary, dict):
        return None
    slim = {
        k: summary[k]
        for k in _SHOT_DIAG_KEYS
        if isinstance(summary.get(k), dict) and summary.get(k)
    }
    return slim or None


def _load_user_week_shot_diag(franchise_id_str, week, team1_id, team2_id) -> dict | None:
    """Load this week's user game_doc from db.games and return its slim shot
    diagnostics. The user game persists the four keys top-level (per-quarter via
    summarize_game_state), so this works whether the user played via the
    monolithic or phased complete-week flow. Defensive: None on any miss/error."""
    try:
        a, h = str(team1_id), str(team2_id)
        query = {
            "week": week,
            "franchise_id": str(franchise_id_str),
            "$or": [
                {"team1_id": a, "team2_id": h},
                {"team1_id": h, "team2_id": a},
            ],
        }
        docs = list(db.games.find(query))
        if not docs:
            return None
        return _slim_shot_diag(max(docs, key=_game_doc_richness_score))
    except Exception as e:
        logger.warning("[WEEK AGGREGATE] user game diag load failed: %s", e)
        return None


def _complete_week_finish_cpu_and_persist(
    franchise_doc: dict,
    franchise_id: ObjectId,
    franchise_id_str: str,
    week: int,
    week_games: list,
    week_games_meta: list | None,
    eos_current_round: int | None,
    user_team_id_str: Any,
    user_eos_sim_scope: Any,
    team1_id: Any,
    team2_id: Any,
    results: list,
    community_highlight_pending: dict | None = None,
    *,
    persist_cpu_results_only: bool = False,
) -> dict:
    def _award_gp_sim(winner_tid: Any, eos_g: dict | None, matchup_ids: tuple[Any, Any]) -> None:
        eos_meta = eos_g if week in ft.EOS_WEEKS else None
        maybe_award_franchise_win_geek_points(
            owner_user_id=franchise_doc.get("user_id"),
            user_team_id_str=user_team_id_str,
            winner_team_id=winner_tid,
            week=week,
            eos_game_meta=eos_meta,
        )
        maybe_award_franchise_loss_geek_points(
            owner_user_id=franchise_doc.get("user_id"),
            user_team_id_str=user_team_id_str,
            winner_team_id=winner_tid,
            participant_team_ids=matchup_ids,
            week=week,
            eos_game_meta=eos_meta,
        )
        maybe_award_franchise_eos_title_championship(
            owner_user_id=franchise_doc.get("user_id"),
            user_team_id_str=user_team_id_str,
            winner_team_id=winner_tid,
            week=week,
            eos_game_meta=eos_meta,
        )

    # Phase 2: stable matchup keys + dedupe so phase-B retries / merged rows cannot double-count games.
    results = _dedupe_franchise_week_results_by_matchup([dict(r) for r in results])
    cpu_job_phase = "start_cpu_sims" if persist_cpu_results_only else "phase_b"
    cpu_job = _build_cpu_sim_job(
        franchise_doc,
        week,
        week_games,
        team1_id,
        team2_id,
        results,
        phase=cpu_job_phase,
    )
    cpu_job = _persist_cpu_sim_job(
        franchise_id,
        week,
        _cpu_sim_mark_job_running(cpu_job, phase=cpu_job_phase),
    )
    logger.info(
        "[CPU-SIM-JOB] running franchise_id=%s week=%s phase=%s complete=%s expected=%s failed=%s",
        franchise_id_str,
        week,
        cpu_job_phase,
        cpu_job.get("completed_matchups"),
        cpu_job.get("expected_matchups"),
        cpu_job.get("failed_matchups"),
    )
    # Phase 3: deferred full turn-based sims (run in parallel, persist sequentially).
    full_jobs: list[tuple[int, Any, Any, str, str]] = []

    # Distant game sim: batch-load FTD (prestige, total_player_attrs) and team conferences for partition
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {
            "team_id": 1,
            "players": 1,
            "prestige": 1,
            "total_player_attrs": 1,
            "natl_rank": 1,
            "team_attributes.team_chemistry": 1,
            "team_attributes.momentum_score": 1,
            "team_attributes.distant_win_streak": 1,
            "team_attributes.distant_loss_streak": 1,
            "team_attributes.offensive_efficiency": 1,
            "team_attributes.defensive_efficiency": 1,
            "team_attributes.shot_threshold": 1,
        },
    ))
    ftd_by_team_id = {str(d["team_id"]): d for d in ftd_docs if d.get("team_id")}
    distant_fpd_by_player_id = _distant_sim_batch_fpd_map(franchise_id, ftd_by_team_id)
    distant_rs_standings = _distant_sim_regular_season_standings(franchise_doc, ftd_by_team_id)
    team_ids_for_conf = [d["team_id"] for d in ftd_docs if d.get("team_id")]
    if user_team_id_str and ObjectId.is_valid(user_team_id_str):
        team_ids_for_conf.append(ObjectId(user_team_id_str))
    team_conference_docs = list(db.teams.find(
        {"_id": {"$in": team_ids_for_conf}},
        {"_id": 1, "conference": 1},
    ))
    team_id_to_conference = {str(d["_id"]): d.get("conference") for d in team_conference_docs}
    user_conference = team_id_to_conference.get(str(user_team_id_str)) if user_team_id_str else None
    
    for idx, (away_id, home_id) in enumerate(week_games):
        if {str(away_id), str(home_id)} == {str(team1_id), str(team2_id)}:
            continue
        existing = db.games.find_one({
            "week": week,
            "franchise_id": str(franchise_id_str),
            "$or": [
                {"team1_id": away_id, "team2_id": home_id},
                {"team1_id": home_id, "team2_id": away_id},
            ],
        })
        # start-cpu-sims (or retries) can persist results.{week} rows before phase B runs. An early
        # continue here used to skip the entire block — including _sync_eos_bracket_from_existing_game_doc
        # — leaving bracket.round2 (etc.) null while results looked complete (week 28 semis stuck).
        existing_result_row = _week_results_row_for_matchup(results, away_id, home_id)
        if existing_result_row:
            cpu_job = _cpu_sim_mark_matchup_complete(
                cpu_job,
                away_id,
                home_id,
                engine="existing_result",
                away_score=existing_result_row.get("away_score"),
                home_score=existing_result_row.get("home_score"),
                game_id=existing.get("_id") if existing else None,
            )
            if (
                week in ft.EOS_WEEKS
                and week_games_meta
                and idx < len(week_games_meta)
            ):
                g_meta = week_games_meta[idx]
                if existing:
                    logger.warning(
                        "[EOS-BRACKET-DEBUG] sync_from_existing_results_row idx=%s phase=%s conf=%s round=%s midx=%s game_id=%s",
                        idx,
                        g_meta.get("phase"),
                        g_meta.get("conference"),
                        g_meta.get("round"),
                        g_meta.get("matchup_index"),
                        str(existing.get("_id")),
                    )
                    _sync_eos_bracket_from_existing_game_doc(
                        franchise_doc,
                        existing=existing,
                        away_id=away_id,
                        home_id=home_id,
                        g=g_meta,
                        week=week,
                        franchise_id_str=franchise_id_str,
                    )
                else:
                    _sync_eos_bracket_from_result_row(
                        franchise_doc,
                        row=existing_result_row,
                        away_id=away_id,
                        home_id=home_id,
                        week=week,
                        franchise_id_str=franchise_id_str,
                        g=g_meta,
                    )
            continue
        if existing:
            existing_row = {
                "away_id": str(existing["team1_id"]),
                "home_id": str(existing["team2_id"]),
                "away_score": existing["team1_score"],
                "home_score": existing["team2_score"],
            }
            results.append(existing_row)
            cpu_job = _cpu_sim_mark_matchup_complete(
                cpu_job,
                away_id,
                home_id,
                engine=str(existing.get("simulation_engine") or "existing_game"),
                away_score=existing_row["away_score"],
                home_score=existing_row["home_score"],
                game_id=existing.get("_id"),
            )
            if week in ft.EOS_WEEKS and week_games_meta and idx < len(week_games_meta):
                g_meta = week_games_meta[idx]
                logger.warning(
                    "[EOS-BRACKET-DEBUG] sync_from_existing idx=%s phase=%s conf=%s round=%s midx=%s game_id=%s",
                    idx,
                    g_meta.get("phase"),
                    g_meta.get("conference"),
                    g_meta.get("round"),
                    g_meta.get("matchup_index"),
                    str(existing.get("_id")),
                )
                _sync_eos_bracket_from_existing_game_doc(
                    franchise_doc,
                    existing=existing,
                    away_id=away_id,
                    home_id=home_id,
                    g=g_meta,
                    week=week,
                    franchise_id_str=franchise_id_str,
                )
            continue
    
        if week_games_meta and idx < len(week_games_meta):
            g = week_games_meta[idx]
            if not _should_use_tbt_for_eos_game(week, g, user_eos_sim_scope):
                cpu_job = _persist_cpu_sim_job(
                    franchise_id,
                    week,
                    _cpu_sim_mark_matchup_running(cpu_job, away_id, home_id, engine="distant"),
                )
                home_ftd = ftd_by_team_id.get(str(home_id), {})
                away_ftd = ftd_by_team_id.get(str(away_id), {})
                home_combined = _distant_sim_team_combined(
                    home_ftd, home_id, is_home=True, rs_standings=distant_rs_standings,
                    fpd_by_player_id=distant_fpd_by_player_id, current_week=week,
                )
                away_combined = _distant_sim_team_combined(
                    away_ftd, away_id, is_home=False, rs_standings=distant_rs_standings,
                    fpd_by_player_id=distant_fpd_by_player_id, current_week=week,
                )
                home_score, away_score = _run_distant_game_sim(home_combined, away_combined)
                try:
                    sim_res, distant_game_id = _persist_distant_franchise_game(
                        franchise_id=franchise_id,
                        week=week,
                        away_team_object_id=away_id,
                        home_team_object_id=home_id,
                        away_score=away_score,
                        home_score=home_score,
                        ftd_cache=ftd_by_team_id,
                    )
                except Exception:
                    logger.exception(
                        "❌ [COMPLETE-WEEK] EOS distant sim persistence failed; falling back to standings-only result. franchise_id=%s week=%s away_id=%s home_id=%s",
                        franchise_id_str,
                        week,
                        away_id,
                        home_id,
                    )
                    sim_res = _save_game_result(
                        away_id,
                        home_id,
                        away_score,
                        home_score,
                        week,
                        franchise_id=franchise_id_str,
                    )
                    distant_game_id = ""
                results.append({
                    "away_id": sim_res["team1_id"],
                    "home_id": sim_res["team2_id"],
                    "away_score": sim_res["team1_score"],
                    "home_score": sim_res["team2_score"],
                })
                cpu_job = _persist_cpu_sim_job(
                    franchise_id,
                    week,
                    _cpu_sim_mark_matchup_complete(
                        cpu_job,
                        away_id,
                        home_id,
                        engine="distant",
                        away_score=sim_res["team1_score"],
                        home_score=sim_res["team2_score"],
                        game_id=distant_game_id,
                    ),
                )
                winner_id = home_id if home_score > away_score else away_id
                ftp.record_tournament_game_result(
                    franchise_doc,
                    g,
                    week=week,
                    franchise_id_str=franchise_id_str,
                    game_id=distant_game_id or None,
                    team1_id=away_id,
                    team2_id=home_id,
                    team1_score=away_score,
                    team2_score=home_score,
                    source="distant",
                    skip_games_upsert=True,
                )
                _award_gp_sim(winner_id, g, (away_id, home_id))
                continue
    
        # Distant sim: regular season only; neither team in user's conference.
        away_conf = team_id_to_conference.get(str(away_id))
        home_conf = team_id_to_conference.get(str(home_id))
        is_distant = (
            eos_current_round is None
            and user_conference is not None
            and away_conf != user_conference
            and home_conf != user_conference
        )
        # Scout next opponent: always full sim for their game this week (not distant), any conference.
        next_opp = _user_next_regular_season_opponent_id(
            franchise_doc,
            current_week=week,
            user_team_id_str=user_team_id_str,
        )
        if is_distant and next_opp and (
            str(away_id) == str(next_opp) or str(home_id) == str(next_opp)
        ):
            is_distant = False
        if is_distant:
            from BackEnd.distant_sim_engine import distant_sim_should_promote_ranked_fullsim

            away_ftd = ftd_by_team_id.get(str(away_id), {})
            home_ftd = ftd_by_team_id.get(str(home_id), {})
            if distant_sim_should_promote_ranked_fullsim(away_ftd, home_ftd):
                is_distant = False
        if is_distant:
            cpu_job = _persist_cpu_sim_job(
                franchise_id,
                week,
                _cpu_sim_mark_matchup_running(cpu_job, away_id, home_id, engine="distant"),
            )
            home_ftd = ftd_by_team_id.get(str(home_id), {})
            away_ftd = ftd_by_team_id.get(str(away_id), {})
            home_combined = _distant_sim_team_combined(
                home_ftd, home_id, is_home=True, rs_standings=distant_rs_standings,
                fpd_by_player_id=distant_fpd_by_player_id, current_week=week,
            )
            away_combined = _distant_sim_team_combined(
                away_ftd, away_id, is_home=False, rs_standings=distant_rs_standings,
                fpd_by_player_id=distant_fpd_by_player_id, current_week=week,
            )
            home_score, away_score = _run_distant_game_sim(home_combined, away_combined)
            _distant_game_id = None
            try:
                sim_res, _distant_game_id = _persist_distant_franchise_game(
                    franchise_id=franchise_id,
                    week=week,
                    away_team_object_id=away_id,
                    home_team_object_id=home_id,
                    away_score=away_score,
                    home_score=home_score,
                    ftd_cache=ftd_by_team_id,
                )
            except Exception:
                logger.exception(
                    "❌ [COMPLETE-WEEK] Regular-season distant sim persistence failed; falling back to standings-only result. franchise_id=%s week=%s away_id=%s home_id=%s user_conference=%s away_conf=%s home_conf=%s",
                    franchise_id_str,
                    week,
                    away_id,
                    home_id,
                    user_conference,
                    away_conf,
                    home_conf,
                )
                sim_res = _save_game_result(
                    away_id,
                    home_id,
                    away_score,
                    home_score,
                    week,
                    franchise_id=franchise_id_str,
                )
            results.append({
                "away_id": sim_res["team1_id"],
                "home_id": sim_res["team2_id"],
                "away_score": sim_res["team1_score"],
                "home_score": sim_res["team2_score"],
            })
            cpu_job = _persist_cpu_sim_job(
                franchise_id,
                week,
                _cpu_sim_mark_matchup_complete(
                    cpu_job,
                    away_id,
                    home_id,
                    engine="distant",
                    away_score=sim_res["team1_score"],
                    home_score=sim_res["team2_score"],
                    game_id=_distant_game_id,
                ),
            )
            winner_id_rs = home_id if home_score > away_score else away_id
            _distant_sim_apply_result_to_standings_cache(
                distant_rs_standings, away_id, home_id, away_score, home_score
            )
            _award_gp_sim(winner_id_rs, None, (away_id, home_id))
            continue
    
        away_doc = db.teams.find_one({"_id": away_id}, {"name": 1}) or {}
        home_doc = db.teams.find_one({"_id": home_id}, {"name": 1}) or {}
        home_name = home_doc.get("name", "")
        away_name = away_doc.get("name", "")
        full_jobs.append((idx, away_id, home_id, away_name, home_name))
        continue

    # Defensive: duplicate sched_idx would run two full sims for the same EOS meta slot.
    _fj_seen: set[int] = set()
    _fj_dedup: list[tuple[int, Any, Any, str, str]] = []
    for job in full_jobs:
        jidx = job[0]
        if jidx in _fj_seen:
            logger.warning(
                "[EOS-BRACKET-DEBUG] full_jobs duplicate sched_idx=%s franchise_id=%s week=%s",
                jidx,
                franchise_id_str,
                week,
            )
            continue
        _fj_seen.add(jidx)
        _fj_dedup.append(job)
    full_jobs = _fj_dedup

    # Shot-diagnostic summaries from this week's full-sim CPU games (distant sims
    # carry no game_state and never reach here). Rolled up with the user's own
    # game into a single week-aggregate report after the full-sim block.
    _cpu_week_summaries: list[dict] = []

    if full_jobs:
        max_workers = min(_franchise_cpu_full_sim_max_workers(), len(full_jobs))
        logger.info(
            "[COMPLETE-WEEK-PHASE3] Parallel full CPU sims franchise_id=%s week=%s jobs=%s max_workers=%s",
            franchise_id_str,
            week,
            len(full_jobs),
            max_workers,
        )
        future_meta = {}
        for sched_idx, aid, hid, an, hn in full_jobs:
            cpu_job = _cpu_sim_mark_matchup_running(cpu_job, aid, hid, engine="cpu_full")
        cpu_job = _persist_cpu_sim_job(franchise_id, week, cpu_job)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for sched_idx, aid, hid, an, hn in full_jobs:
                fut = executor.submit(
                    _run_franchise_cpu_full_simulation_core,
                    franchise_id,
                    hid,
                    aid,
                    hn,
                    an,
                )
                future_meta[fut] = (sched_idx, aid, hid, an, hn)
        sim_ok: dict[int, tuple[int, int, dict]] = {}
        sim_err: dict[int, Exception] = {}
        for fut in as_completed(future_meta):
            sched_idx, aid, hid, an, hn = future_meta[fut]
            try:
                sim_ok[sched_idx] = fut.result()
            except Exception as ex:
                sim_err[sched_idx] = ex

        # Collect each full-sim CPU game's shot-diagnostic summary (both teams
        # combined, stamped by summarize_game_state) and stash a slim copy on the
        # franchise doc keyed by week. In the phased flow, CPU sims run in
        # start-cpu-sims (before the user plays), so the summaries must survive to
        # be rolled into the end-of-week report at phase-b.
        _cpu_week_summaries = [s for (_a, _h, s) in sim_ok.values() if isinstance(s, dict)]
        try:
            _slim_cpu = [d for d in (_slim_shot_diag(s) for s in _cpu_week_summaries) if d]
            db.franchises.update_one(
                {"_id": franchise_id},
                {"$set": {f"week_shot_diagnostics.{week}": _slim_cpu}},
            )
        except Exception as _stash_e:
            logger.warning("[WEEK AGGREGATE] stash cpu diagnostics failed: %s", _stash_e)

        for job_idx, aid, hid, an, hn in sorted(full_jobs, key=lambda t: t[0]):
            if job_idx in sim_err:
                logger.error(
                    "❌ [COMPLETE-WEEK] Parallel full-sim core failed; random fallback + bracket sync. franchise_id=%s week=%s idx=%s",
                    franchise_id_str,
                    week,
                    job_idx,
                    exc_info=sim_err[job_idx],
                )
                away_score = random.randint(50, 90)
                home_score = random.randint(50, 90)
                ex_g = week_games_meta[job_idx] if week_games_meta and job_idx < len(week_games_meta) else None
                if week in ft.EOS_WEEKS and ex_g is not None:
                    g_fb = ex_g
                    ftp.record_tournament_game_result(
                        franchise_doc,
                        g_fb,
                        week=week,
                        franchise_id_str=franchise_id_str,
                        game_id=None,
                        team1_id=aid,
                        team2_id=hid,
                        team1_score=away_score,
                        team2_score=home_score,
                        source="cpu_full",
                    )
                    sim_res = {
                        "team1_id": str(aid),
                        "team2_id": str(hid),
                        "team1_score": away_score,
                        "team2_score": home_score,
                    }
                else:
                    sim_res = _save_game_result(
                        aid, hid, away_score, home_score, week, franchise_id=franchise_id_str
                    )
                ex_winner = (
                    sim_res["team1_id"]
                    if sim_res["team1_score"] > sim_res["team2_score"]
                    else sim_res["team2_id"]
                )
                _award_gp_sim(ex_winner, ex_g, (aid, hid))
                if week in ft.EOS_WEEKS and ex_g is not None:
                    ph = ex_g.get("phase")
                    logger.warning(
                        "[EOS-BRACKET-DEBUG] eos_full_sim_fallback_bracket_sync week=%s idx=%s phase=%s conf=%s",
                        week,
                        job_idx,
                        ph,
                        ex_g.get("conference"),
                    )
                results.append(
                    {
                        "away_id": sim_res["team1_id"],
                        "home_id": sim_res["team2_id"],
                        "away_score": sim_res["team1_score"],
                        "home_score": sim_res["team2_score"],
                    }
                )
                cpu_job = _persist_cpu_sim_job(
                    franchise_id,
                    week,
                    _cpu_sim_mark_matchup_complete(
                        cpu_job,
                        aid,
                        hid,
                        engine="cpu_full_fallback",
                        away_score=sim_res["team1_score"],
                        home_score=sim_res["team2_score"],
                        game_id=None,
                    ),
                )
                continue

            away_score, home_score, summary = sim_ok[job_idx]
            computer_game_id = generate_game_id()
            summary = dict(summary)
            summary["_id"] = computer_game_id
            summary["franchise_id"] = str(franchise_id_str)
            summary["week"] = week
            db.games.update_one({"_id": computer_game_id}, {"$set": summary}, upsert=True)
            stat_updater.finalize_game(
                computer_game_id, mode="franchise", franchise_id=franchise_id_str
            )
            sim_res = {
                "team1_id": str(aid),
                "team2_id": str(hid),
                "team1_score": away_score,
                "team2_score": home_score,
            }
            if week_games_meta and job_idx < len(week_games_meta):
                g_cpu = week_games_meta[job_idx]
                ftp.record_tournament_game_result(
                    franchise_doc,
                    g_cpu,
                    week=week,
                    franchise_id_str=franchise_id_str,
                    game_id=str(computer_game_id),
                    team1_id=aid,
                    team2_id=hid,
                    team1_score=away_score,
                    team2_score=home_score,
                    source="cpu_full",
                    skip_games_upsert=True,
                )
            else:
                sim_res = _save_game_result(
                    aid, hid, away_score, home_score, week, franchise_id=franchise_id_str, game_id=computer_game_id
                )
            home_id_str = _normalize_team_id_to_string(hid) or str(hid)
            away_id_str = _normalize_team_id_to_string(aid) or str(aid)
            if home_score > away_score:
                winner_id_str, loser_id_str = home_id_str, away_id_str
                ws, ls = home_score, away_score
            else:
                winner_id_str, loser_id_str = away_id_str, home_id_str
                ws, ls = away_score, home_score
            _finalize_team_attributes_for_game(
                game_id=computer_game_id,
                franchise_id=franchise_id,
                home_team_id=home_id_str,
                away_team_id=away_id_str,
                winner_id=winner_id_str,
                loser_id=loser_id_str,
                winner_score=ws,
                loser_score=ls,
                week=week,
            )
            winner_oid = hid if home_score > away_score else aid
            sim_eos_g = week_games_meta[job_idx] if week_games_meta and job_idx < len(week_games_meta) else None
            _award_gp_sim(winner_oid, sim_eos_g, (aid, hid))
            results.append(
                {
                    "away_id": sim_res["team1_id"],
                    "home_id": sim_res["team2_id"],
                    "away_score": sim_res["team1_score"],
                    "home_score": sim_res["team2_score"],
                }
            )
            cpu_job = _persist_cpu_sim_job(
                franchise_id,
                week,
                _cpu_sim_mark_matchup_complete(
                    cpu_job,
                    aid,
                    hid,
                    engine="cpu_full",
                    away_score=away_score,
                    home_score=home_score,
                    game_id=computer_game_id,
                ),
            )

    results = _order_franchise_week_results_like_schedule(results, week_games)

    if persist_cpu_results_only:
        wk = str(week)
        # Re-read fresh state from DB so a concurrent phase-a write — which this path
        # never produces locally because it skips the user matchup — is preserved on
        # persist. Without this merge, both the blanket ``$set: {"results.{wk}":
        # results}`` and the EOS-blob ``$set`` clobber any row / bracket cell that
        # landed in the DB between when this request loaded ``franchise_doc`` and
        # now. That race is the silent root cause of two related symptoms:
        #   - "user team shows 0-0 after a played week" (regular season + EOS, due
        #     to ``results.{wk}`` getting overwritten with the CPU-only set), and
        #   - "EOS bracket cell stays null" (EOS only, due to ``conference_tournaments``
        #     / ``region_tournaments`` / ``national_tournament`` getting overwritten).
        # See ``Tournament_Execution_System.md`` §3b.
        projection: dict[str, Any] = {f"results.{wk}": 1}
        if week in ft.EOS_WEEKS:
            projection["conference_tournaments"] = 1
            projection["region_tournaments"] = 1
            projection["national_tournament"] = 1
        fresh_doc = db.franchises.find_one({"_id": franchise_id}, projection) or {}
        fresh_results_for_week = (fresh_doc.get("results") or {}).get(wk) or []
        # Union by matchup key. Local ``results`` (this request's CPU sims) wins for
        # any matchup it has data for; ``fresh_results_for_week`` contributes any
        # matchup local lacks — specifically the user's row from a concurrent
        # phase-a write. ``_dedupe_franchise_week_results_by_matchup`` keeps the
        # first occurrence per matchup key, and we put local first.
        merged_results = _dedupe_franchise_week_results_by_matchup(
            list(results) + list(fresh_results_for_week)
        )
        merged_results = _order_franchise_week_results_like_schedule(merged_results, week_games)
        partial_update: dict[str, Any] = {f"results.{wk}": merged_results}
        if week in ft.EOS_WEEKS:
            merged_eos = ft.merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise(
                fresh_doc,
                franchise_doc,
            )
            for _eos_key, _eos_val in merged_eos.items():
                partial_update[_eos_key] = _eos_val
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": partial_update},
        )
        cpu_job = _persist_cpu_sim_job(
            franchise_id,
            week,
            _build_cpu_sim_job(
                {**franchise_doc, "cpu_sim_jobs": {str(week): cpu_job}},
                week,
                week_games,
                team1_id,
                team2_id,
                merged_results,
                phase=cpu_job_phase,
            ),
        )
        logger.info(
            "[START-CPU-SIMS] persisted partial week results franchise_id=%s week=%s row_count=%s cpu_complete=%s/%s",
            franchise_id_str,
            week,
            len(results),
            cpu_job.get("completed_matchups"),
            cpu_job.get("expected_matchups"),
        )
        return {
            "status": "ok",
            "phase": "start_cpu_sims",
            "week": week,
            "results_count": len(results),
            "persist_cpu_results_only": True,
            "cpu_sim_job": {
                "status": cpu_job.get("status"),
                "completed_matchups": cpu_job.get("completed_matchups"),
                "expected_matchups": cpu_job.get("expected_matchups"),
                "failed_matchups": cpu_job.get("failed_matchups"),
            },
        }

    finalized = _try_finalize_franchise_week_if_complete(
        franchise_doc=franchise_doc,
        franchise_id=franchise_id,
        franchise_id_str=franchise_id_str,
        week=week,
        week_games=week_games,
        results=results,
        user_team_id_str=user_team_id_str,
        community_highlight_pending=community_highlight_pending,
    )
    if finalized is None:
        dedup_n = len(_dedupe_franchise_week_results_by_matchup(results))
        _persist_cpu_sim_job(franchise_id, week, cpu_job)
        logger.error(
            "[COMPLETE-WEEK] Week %s incomplete after CPU loop franchise_id=%s "
            "(deduped_rows=%s expected_matchups=%s); refusing week advance",
            week,
            franchise_id_str,
            dedup_n,
            len(week_games),
        )
        raise HTTPException(
            status_code=500,
            detail=(
                "Internal error: incomplete week results after CPU simulations; "
                "franchise week was not advanced."
            ),
        )
    finalized_job = dict(cpu_job)
    finalized_job["status"] = "finalized"
    finalized_job["finalized_at"] = _utc_now_iso()
    finalized_job["updated_at"] = finalized_job["finalized_at"]
    finalized_job = _persist_cpu_sim_job(franchise_id, week, finalized_job)
    if isinstance(finalized, dict):
        finalized["cpu_sim_job"] = {
            "status": finalized_job.get("status"),
            "completed_matchups": finalized_job.get("completed_matchups"),
            "expected_matchups": finalized_job.get("expected_matchups"),
            "failed_matchups": finalized_job.get("failed_matchups"),
        }

    # One macro shot-diagnostics report for the fully-completed week: the user's
    # own game rolled up with every full-sim CPU game (distant sims carry no
    # game_state and are excluded). This is the single end-of-week roll-up, fired
    # once here regardless of monolithic vs phased flow. CPU diagnostics come from
    # this call's in-memory summaries (monolithic) or the week stash written by
    # start-cpu-sims (phased); the user game is loaded from db.games. It still
    # prints with just the user game if the week had no CPU full sims. Grep
    # ``WEEK AGGREGATE``. (The user game also prints its own per-game report during
    # play; this is the weekly macro roll-up.)
    try:
        from BackEnd.utils.shot_split_tracker import (
            merge_shot_diagnostics, format_week_aggregate_report,
        )
        _cpu_diags = [d for d in (_cpu_week_summaries or []) if isinstance(d, dict)]
        if not _cpu_diags:
            _fresh = db.franchises.find_one(
                {"_id": franchise_id}, {f"week_shot_diagnostics.{week}": 1}
            ) or {}
            _cpu_diags = [
                d
                for d in ((_fresh.get("week_shot_diagnostics") or {}).get(str(week)) or [])
                if isinstance(d, dict)
            ]
        _summaries = list(_cpu_diags)
        _user_diag = _load_user_week_shot_diag(franchise_id_str, week, team1_id, team2_id)
        if isinstance(_user_diag, dict):
            _summaries.append(_user_diag)
        _merged, _ngames = merge_shot_diagnostics(_summaries)
        if _ngames:
            print(
                f"[WEEK AGGREGATE] franchise={franchise_id_str} week={week} "
                f"({'user game + ' if _user_diag else ''}{len(_cpu_diags)} full-sim CPU games)"
            )
            print(format_week_aggregate_report(_merged, _ngames))
    except Exception as _agg_e:
        logger.warning("[WEEK AGGREGATE] shot diagnostics failed: %s", _agg_e)

    return finalized

@router.post("/franchise/complete-week")
def complete_week(req: CompleteWeekRequest):
    logger.warning(
        "🧭 [COMPLETE-WEEK-ENTRY] franchise_id=%s week=%s game_id=%s has_game_document=%s",
        req.franchise_id,
        req.week,
        req.game_id,
        bool(req.game_document),
    )
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    req = _harden_complete_week_request_week(franchise_doc, req)

    _u_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    user_eos_sim_scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)

    week_games, week_games_meta, eos_current_round = _resolve_complete_week_week_games(
        franchise_doc, req
    )

    user = req.result
    team1_id = _normalize_team_id(user.team1_id)
    team2_id = _normalize_team_id(user.team2_id)

    results = []
    community_highlight_pending = None
    if _phase_a_user_week_done(franchise_doc, req.week):
        week_key = str(req.week)
        saved = franchise_doc.get("results", {}).get(week_key)
        if isinstance(saved, list) and len(saved) > 0:
            results = [dict(r) for r in saved]
            logger.warning(
                "🧭 [COMPLETE-WEEK] Skipping user game processing; phase-a already persisted week=%s",
                req.week,
            )
        else:
            _, user_row, gp_delta, eos_meta, ch_gid = _complete_week_process_user_game_block(
                franchise_doc,
                req,
                franchise_id,
                week_games_meta,
                user_team_id_str,
                _u_name,
            )
            results.append(user_row)
            _gid = (str(req.game_id).strip() if getattr(req, "game_id", None) else None) or ch_gid
            community_highlight_pending = build_community_highlight_pending(
                week=req.week,
                user_team_id_str=user_team_id_str,
                user_row=user_row,
                gp_delta=gp_delta,
                game_id=_gid,
                eos_game_meta=eos_meta,
            )
    else:
        _, user_row, gp_delta, eos_meta, ch_gid = _complete_week_process_user_game_block(
            franchise_doc,
            req,
            franchise_id,
            week_games_meta,
            user_team_id_str,
            _u_name,
        )
        results.append(user_row)
        _gid = (str(req.game_id).strip() if getattr(req, "game_id", None) else None) or ch_gid
        community_highlight_pending = build_community_highlight_pending(
            week=req.week,
            user_team_id_str=user_team_id_str,
            user_row=user_row,
            gp_delta=gp_delta,
            game_id=_gid,
            eos_game_meta=eos_meta,
        )

    return _complete_week_finish_cpu_and_persist(
        franchise_doc,
        franchise_id,
        str(req.franchise_id),
        req.week,
        week_games,
        week_games_meta,
        eos_current_round,
        user_team_id_str,
        user_eos_sim_scope,
        team1_id,
        team2_id,
        results,
        community_highlight_pending=community_highlight_pending,
    )




@router.post("/franchise/complete-week/phase-a")
def complete_week_phase_a(req: CompleteWeekRequest):
    logger.warning(
        "🧭 [COMPLETE-WEEK-PHASE-A] franchise_id=%s week=%s game_id=%s",
        req.franchise_id,
        req.week,
        req.game_id,
    )
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    req = _harden_complete_week_request_week(franchise_doc, req)

    if _phase_a_user_week_done(franchise_doc, req.week):
        wk = str(req.week)
        saved = franchise_doc.get("results", {}).get(wk) or []
        n = len(saved) if isinstance(saved, list) else 0
        return {
            "status": "ok",
            "phase": "a",
            "idempotent": True,
            "week": req.week,
            "results_count": n,
        }

    _u_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    _week_games, week_games_meta, _eos_cr = _resolve_complete_week_week_games(franchise_doc, req)

    _, user_row, gp_delta, eos_meta, ch_gid = _complete_week_process_user_game_block(
        franchise_doc,
        req,
        franchise_id,
        week_games_meta,
        user_team_id_str,
        _u_name,
    )

    merged = _merge_phase_a_user_row_into_week_results(
        franchise_doc.get("results", {}).get(str(req.week)),
        user_row,
    )

    _gid = (str(req.game_id).strip() if getattr(req, "game_id", None) else None) or ch_gid
    ch_pending = build_community_highlight_pending(
        week=req.week,
        user_team_id_str=user_team_id_str,
        user_row=user_row,
        gp_delta=gp_delta,
        game_id=_gid,
        eos_game_meta=eos_meta,
    )

    # Split phase B reloads the franchise from Mongo. `_complete_week_process_user_game_block`
    # mutates bracket blobs in memory only; without persisting them here, phase B skips the
    # user matchup row and never re-applies that winner → e.g. conference R1 stuck at 3/4.
    phase_a_fields: dict[str, Any] = {
        f"results.{str(req.week)}": merged,
        "season_inbox": franchise_doc.get("season_inbox", []),
        "post_game_status.phase_a_user_week": req.week,
        "post_game_status.community_highlight_pending": ch_pending,
    }
    if req.week in ft.EOS_WEEKS:
        # Re-read EOS blobs so ``start-cpu-sims`` (or any concurrent writer) is not clobbered by
        # ``franchise_doc`` loaded at the start of this request; merge in-memory user bracket edits.
        fresh_eos = db.franchises.find_one(
            {"_id": franchise_id},
            {
                "conference_tournaments": 1,
                "region_tournaments": 1,
                "national_tournament": 1,
            },
        ) or {}
        merged_eos = ft.merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise(
            fresh_eos,
            franchise_doc,
        )
        for _eos_key, _eos_val in merged_eos.items():
            phase_a_fields[_eos_key] = _eos_val

    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": phase_a_fields},
    )

    return {
        "status": "ok",
        "phase": "a",
        "idempotent": False,
        "week": req.week,
        "results_count": len(merged),
    }


@router.post("/franchise/complete-week/start-cpu-sims")
def complete_week_start_cpu_sims(req: CompleteWeekStartCpuSimsRequest):
    """
    Run distant + full CPU sims for all **non-user** week matchups and persist ``results.{week}``
    without advancing the franchise week. Idempotent per matchup (skips rows / games already present).

    Call when the user begins their franchise game for this week (e.g. first Play Quarter). After the
    user game is saved (phase A), phase B merges the user row and finalizes the week when the slate is complete.
    """
    logger.info(
        "[START-CPU-SIMS] entry franchise_id=%s week=%s",
        req.franchise_id,
        req.week,
    )
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    current_week = int(franchise_doc.get("week", 1))
    if current_week != req.week:
        raise HTTPException(
            status_code=400,
            detail=f"Franchise week is {current_week}, not {req.week}; cannot start CPU sims for this request.",
        )

    if _phase_a_user_week_done(franchise_doc, req.week):
        raise HTTPException(
            status_code=409,
            detail="User game for this week is already saved (phase A). Use POST /franchise/complete-week/phase-b to finalize.",
        )

    fake_req = SimpleNamespace(week=req.week, franchise_id=req.franchise_id)
    week_games, week_games_meta, eos_current_round = _resolve_complete_week_week_games(
        franchise_doc, fake_req  # type: ignore[arg-type]
    )
    _u_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    user_eos_sim_scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)
    wk = str(req.week)
    saved_existing = franchise_doc.get("results", {}).get(wk)
    saved_list = saved_existing if isinstance(saved_existing, list) else []
    team1_id, team2_id = _find_user_franchise_week_matchup_normalized_ids(
        week_games,
        user_team_id_str,
        week=req.week,
        saved_week_results=saved_list,
    )
    results = [dict(r) for r in saved_list]

    out = _complete_week_finish_cpu_and_persist(
        franchise_doc,
        franchise_id,
        req.franchise_id,
        req.week,
        week_games,
        week_games_meta,
        eos_current_round,
        user_team_id_str,
        user_eos_sim_scope,
        team1_id,
        team2_id,
        results,
        community_highlight_pending=None,
        persist_cpu_results_only=True,
    )
    out["idempotent"] = False
    logger.info(
        "[START-CPU-SIMS] complete franchise_id=%s week=%s results_count=%s week_matchups=%s",
        req.franchise_id,
        req.week,
        out.get("results_count"),
        len(week_games),
    )
    return out


@router.post("/franchise/complete-week/phase-b")
def complete_week_phase_b(req: CompleteWeekPhaseBRequest):
    logger.warning(
        "🧭 [COMPLETE-WEEK-PHASE-B] franchise_id=%s week=%s",
        req.franchise_id,
        req.week,
    )
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    eos_heal_summary: dict[str, Any] | None = None
    heal = _eos_heal_all_eos_from_games(franchise_id, req.franchise_id)
    if heal.get("did_work"):
        franchise_doc = db.franchises.find_one({"_id": franchise_id}) or franchise_doc
        eos_heal_summary = heal

    current_week = int(franchise_doc.get("week", 1))
    if current_week > req.week:
        logger.info(
            "[COMPLETE-WEEK-PHASE-B] outcome=already_finalized franchise_id=%s req_week=%s franchise_week=%s",
            req.franchise_id,
            req.week,
            current_week,
        )
        payload: dict[str, Any] = {
            "status": "ok",
            "phase": "b",
            "idempotent": True,
            "week": req.week,
            "results": [],
        }
        if eos_heal_summary:
            payload["eos_heal"] = eos_heal_summary
            payload["idempotent"] = False
        return payload
    if current_week < req.week:
        raise HTTPException(status_code=400, detail="Franchise week is behind requested week")

    if not _phase_a_user_week_done(franchise_doc, req.week):
        raise HTTPException(
            status_code=409,
            detail="Run POST /franchise/complete-week/phase-a first (or use monolithic complete-week).",
        )

    wk = str(req.week)
    saved = franchise_doc.get("results", {}).get(wk)
    if not isinstance(saved, list) or len(saved) == 0:
        raise HTTPException(
            status_code=409,
            detail="No saved results for this week; run phase A first.",
        )

    fake_req = SimpleNamespace(week=req.week, franchise_id=req.franchise_id)
    week_games, week_games_meta, eos_current_round = _resolve_complete_week_week_games(
        franchise_doc, fake_req  # type: ignore[arg-type]
    )
    _u_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    user_eos_sim_scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)
    team1_id, team2_id = _find_user_franchise_week_matchup_normalized_ids(
        week_games,
        user_team_id_str,
        week=req.week,
        saved_week_results=saved,
    )
    results = [dict(r) for r in saved]

    pre_summary = _cpu_sim_job_public_summary(franchise_doc, req.week)
    if pre_summary:
        logger.info(
            "[CPU-SIM-RESUME] phase-b recovery start franchise_id=%s week=%s status=%s completed=%s/%s failed=%s",
            req.franchise_id,
            req.week,
            pre_summary.get("status"),
            pre_summary.get("completed_matchups"),
            pre_summary.get("expected_matchups"),
            pre_summary.get("failed_matchups"),
        )

    out = _complete_week_finish_cpu_and_persist(
        franchise_doc,
        franchise_id,
        req.franchise_id,
        req.week,
        week_games,
        week_games_meta,
        eos_current_round,
        user_team_id_str,
        user_eos_sim_scope,
        team1_id,
        team2_id,
        results,
        community_highlight_pending=None,
    )
    out["status"] = "ok"
    out["phase"] = "b"
    out["idempotent"] = False
    if eos_heal_summary:
        out["eos_heal"] = eos_heal_summary
    post_summary = out.get("cpu_sim_job")
    if post_summary:
        logger.info(
            "[CPU-SIM-RESUME] phase-b recovery complete franchise_id=%s week=%s status=%s completed=%s/%s failed=%s",
            req.franchise_id,
            req.week,
            post_summary.get("status"),
            post_summary.get("completed_matchups"),
            post_summary.get("expected_matchups"),
            post_summary.get("failed_matchups"),
        )
    return out

@router.get("/franchise/current")
def get_current_franchise(user: dict = Depends(get_current_user)):
    """
    Return the current user's franchise.
    Used by mode-select to show instance and Play Now / New Franchise.
    Returns 404 if the user has no franchise.
    """
    doc = db.franchises.find_one(
        {"user_id": user.get("user_id")},
        projection={
            "_id": 1, "user_team_id": 1, "week": 1,
            "eos_tournament": 1, "eos_tournament_active": 1
        }
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No franchise found")
    eos = doc.get("eos_tournament") or {}
    return {
        "franchise_id": str(doc["_id"]),
        "user_team_id": doc.get("user_team_id"),
        "week": doc.get("week", 1),
        "eos_tournament_active": doc.get("eos_tournament_active", False),
        "eos_current_round": eos.get("current_round", 1),
        "eos_completed": eos.get("completed", False),
    }


@router.post("/franchise/delete-current")
@router.delete("/franchise/current")
def delete_current_franchise(user: dict = Depends(get_current_user)):
    """
    Delete the current user's franchise (and related FTD, FPD, FRD) so they can start a new one from mode-select.
    Used when user confirms "New Franchise" in the confirmation modal.
    Returns 200 with deleted=True if a franchise was deleted, deleted=False if none existed.
    """
    doc = db.franchises.find_one({"user_id": user.get("user_id")}, {"_id": 1})
    if not doc:
        return {"deleted": False, "count": 0}
    fid = doc["_id"]
    # FTD stores franchise_id as ObjectId; FPD/FRD store as string; games store franchise_id as string
    franchise_team_data_collection.delete_many({"franchise_id": fid})
    franchise_players_data_collection.delete_many({"franchise_id": str(fid)})
    franchise_recruits_data_collection.delete_many({"franchise_id": str(fid)})
    db.games.delete_many({"franchise_id": str(fid)})
    db.franchises.delete_one({"_id": fid})
    return {"deleted": True, "count": 1}


@router.get("/franchise/command-center/data")
def command_center_data(
    franchise_id: str = None,
    user: dict = Depends(get_current_user),
    profile: bool = False,
):
    """FCC main data load. Add ?profile=1 to get profile_summary in the response."""
    import time
    def _build():
        team_name = None
        team_id = None
        training_completed = False
        session_type = "in-season"
        franchise_doc = None
        if franchise_id:
            try:
                franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
                fid = franchise_doc["_id"]
                if franchise_doc:
                    team_name, team_id = get_user_team_from_franchise(franchise_doc)
                    training_status = franchise_doc.get("training_status", {}) or {}
                    try:
                        fcc_week = int(franchise_doc.get("week", 1) or 1)
                    except (TypeError, ValueError):
                        fcc_week = 1
                    training_completed = franchise_training_fully_complete_for_week(training_status, fcc_week)
                    session_type = training_status.get("session_type", "in-season")
                    if team_id:
                        team_doc = db.teams.find_one({"_id": ObjectId(team_id)}) or {}
                        ftd = franchise_team_data_collection.find_one(
                            {"franchise_id": fid, "team_id": ObjectId(team_id)},
                            {"team_attributes": 1, "prestige": 1, "natl_rank": 1}
                        )
                        if ftd:
                            attrs = ftd.get("team_attributes", {})
                            team_doc["team_chemistry"] = attrs.get("team_chemistry", 0)
                            if "prestige" in ftd:
                                team_doc["prestige"] = ftd["prestige"]
                            if "natl_rank" in ftd:
                                team_doc["rank"] = ftd["natl_rank"]
                        else:
                            team_doc["team_chemistry"] = 0
                    else:
                        team_doc = {}
                else:
                    team_doc = {}
            except HTTPException:
                raise
            except Exception:
                team_doc = {}
        else:
            try:
                state = franchise_state_collection.find_one({"_id": "state"}) or {}
                team_name = state.get("team", "")
                if team_name:
                    logger.warning(f"⚠️ [DEPRECATED] Using franchise_state fallback (no franchise_id provided). ")
                team_doc = db.teams.find_one({"name": team_name}) or {}
                team_id = str(team_doc.get("_id", "")) if team_doc.get("_id") else None
            except Exception as e:
                logger.debug(f"franchise_state collection not available: {e}")
                team_doc = {}
                team_id = None
        try:
            state = franchise_state_collection.find_one({"_id": "state"}) or {}
        except Exception as e:
            logger.debug(f"franchise_state collection not available: {e}")
            state = {}
        eos_tournament = franchise_doc.get("eos_tournament") if franchise_doc else None
        national_tournament = franchise_doc.get("national_tournament", {}) if franchise_doc else {}
        eos_tournament_active = franchise_doc.get("eos_tournament_active", False) if franchise_doc else False
        week = franchise_doc.get("week", 1) if franchise_doc else None
        response = build_command_center_base(team_name, team_id, team_doc)
        response["current_season"] = franchise_doc.get("current_season", 1) if franchise_doc else 1
        response["intangibles"] = team_doc.get("intangibles", "-")
        response["prestige"] = team_doc.get("prestige", "-")
        response["rank"] = team_doc.get("rank", "-")
        response["primary_color"] = team_doc.get("primary_color", "#27408E")
        response["user_conference"] = team_doc.get("conference")
        response["user_region"] = team_doc.get("region", "")
        # Rankings list for Rankings tab: all FTD teams with natl_rank and team name, sorted by natl_rank
        if franchise_id and franchise_doc:
            try:
                fid = franchise_doc["_id"]
                from BackEnd.utils.franchise_standings import calculate_franchise_standings
                ftd_rank_docs = list(franchise_team_data_collection.find(
                    {"franchise_id": fid},
                    {"team_id": 1, "natl_rank": 1}
                ))
                if ftd_rank_docs:
                    team_ids = [d["team_id"] for d in ftd_rank_docs if d.get("team_id") is not None]
                    teams_docs = {str(t["_id"]): t for t in db.teams.find(
                        {"_id": {"$in": team_ids}},
                        {"name": 1, "primary_color": 1, "conference": 1, "region": 1, "mascot": 1}
                    )}
                    natl_rank_by_team_id = {
                        str(d["team_id"]): int(d.get("natl_rank", 999) or 999)
                        for d in ftd_rank_docs
                        if d.get("team_id") is not None
                    }
                    team_name_by_id = {
                        str(team_id): teams_docs.get(str(team_id), {}).get("name", str(team_id))
                        for team_id in team_ids
                    }
                    team_list = _ftd_team_list_for_franchise(franchise_id)
                    standings_data = calculate_franchise_standings(
                        franchise_doc.get("results", {}),
                        team_list,
                    )
                    next_matchup_map = _build_next_matchup_map(franchise_doc, team_name_by_id, natl_rank_by_team_id)
                    previous_week_result_map = _build_previous_week_result_map(franchise_doc, team_name_by_id, natl_rank_by_team_id)
                    rankings = [
                        {
                            "team_id": str(d["team_id"]),
                            "natl_rank": d.get("natl_rank", 128),
                            "team_name": teams_docs.get(str(d["team_id"]), {}).get("name", "?"),
                            "primary_color": teams_docs.get(str(d["team_id"]), {}).get("primary_color") or "#000000",
                            "conference": teams_docs.get(str(d["team_id"]), {}).get("conference"),
                            "W": int((standings_data.get(str(d["team_id"]), {}) or {}).get("W", 0) or 0),
                            "L": int((standings_data.get(str(d["team_id"]), {}) or {}).get("L", 0) or 0),
                            "last_week": (previous_week_result_map.get(str(d["team_id"])) or {}).get("text", ""),
                            "last_week_result": (previous_week_result_map.get(str(d["team_id"])) or {}).get("result", ""),
                            "next": next_matchup_map.get(str(d["team_id"]), ""),
                        }
                        for d in ftd_rank_docs
                    ]
                    rankings.sort(key=lambda x: x["natl_rank"])
                    response["rankings"] = rankings

                    if team_id:
                        next_game = _find_user_next_game(franchise_doc, str(team_id))
                        if next_game:
                            opponent_id = (
                                str(next_game.get("away_team_id"))
                                if str(next_game.get("home_team_id")) == str(team_id)
                                else str(next_game.get("home_team_id"))
                            )
                            opponent_leaders = _build_team_leader_summary(fid, opponent_id)
                            opponent_standings = standings_data.get(opponent_id, {}) or {}
                            response["next_game_summary"] = {
                                "matchup_label": "vs" if str(next_game.get("home_team_id")) == str(team_id) else "@",
                                "opponent_team_id": opponent_id,
                                "opponent_team_name": teams_docs.get(opponent_id, {}).get("name", team_name_by_id.get(opponent_id, "Opponent")),
                                "opponent_team_mascot": teams_docs.get(opponent_id, {}).get("mascot", ""),
                                "opponent_team_region": teams_docs.get(opponent_id, {}).get("region", ""),
                                "opponent_team_conference": teams_docs.get(opponent_id, {}).get("conference"),
                                "record": {
                                    "wins": int(opponent_standings.get("W", 0) or 0),
                                    "losses": int(opponent_standings.get("L", 0) or 0),
                                },
                                "rank": int(natl_rank_by_team_id.get(opponent_id, 999) or 999),
                                "top_scorer": opponent_leaders.get("top_scorer"),
                                "top_rebounder": opponent_leaders.get("top_rebounder"),
                            }
                        else:
                            response["next_game_summary"] = None
                            if ft.user_has_region_round1_bye_waiting(
                                franchise_doc,
                                str(team_id),
                                str(response.get("user_region") or ""),
                            ):
                                response["next_game_is_bye"] = True

                        last_game = _find_user_last_completed_game(franchise_doc, str(team_id))
                        if last_game:
                            away_id = str(last_game.get("away_team_id") or "")
                            home_id = str(last_game.get("home_team_id") or "")
                            game_doc = last_game.get("game_doc") or {}
                            response["last_game_summary"] = {
                                "matchup_label": "vs" if home_id == str(team_id) else "@",
                                "opponent_team_id": away_id if home_id == str(team_id) else home_id,
                                "opponent_team_name": teams_docs.get(away_id if home_id == str(team_id) else home_id, {}).get("name", team_name_by_id.get(away_id if home_id == str(team_id) else home_id, "Opponent")),
                                "away_team_name": teams_docs.get(away_id, {}).get("name", team_name_by_id.get(away_id, away_id)),
                                "home_team_name": teams_docs.get(home_id, {}).get("name", team_name_by_id.get(home_id, home_id)),
                                "away_score": int(last_game.get("away_score", 0) or 0),
                                "home_score": int(last_game.get("home_score", 0) or 0),
                                "game_id": last_game.get("game_id"),
                                "potg": _calculate_potg_summary(game_doc) if game_doc else None,
                            }
                        else:
                            response["last_game_summary"] = None
                    else:
                        response["next_game_summary"] = None
                        response["last_game_summary"] = None
                else:
                    response["rankings"] = []
                    response["next_game_summary"] = None
                    response["last_game_summary"] = None
            except Exception as e:
                logger.debug("rankings for FCC: %s", e)
                response["rankings"] = []
                response["next_game_summary"] = None
                response["last_game_summary"] = None
        else:
            response["rankings"] = []
            response["next_game_summary"] = None
            response["last_game_summary"] = None
        response["username"] = state.get("username", "Coach")
        response["seed"] = state.get("seed", 1)
        response["training_completed"] = training_completed
        response["session_type"] = session_type
        response["week"] = week if week is not None else 1
        cut_state = _week_1_cut_requirement(franchise_doc, fid if franchise_doc else None, team_id)
        response["user_roster_count"] = int(cut_state.get("roster_count", 0) or 0)
        response["cut_count"] = int(cut_state.get("cut_count", 0) or 0)
        response["cut_required"] = bool(cut_state.get("cut_required", False))
        response["week_35_recruiting_ran"] = bool(franchise_doc.get("week_35_recruiting_ran", False)) if franchise_doc else False
        response["active_game_resume"] = None
        if franchise_doc and team_id:
            try:
                response["active_game_resume"] = _find_active_user_game_resume(franchise_doc, str(team_id))
            except Exception as e:
                logger.debug("active game resume lookup failed: %s", e)
                response["active_game_resume"] = None
        response["cpu_sim_resume"] = _cpu_sim_job_public_summary(franchise_doc, week) if franchise_doc else None
        if response.get("cpu_sim_resume"):
            _csr = response["cpu_sim_resume"]
            logger.info(
                "[CPU-SIM-RESUME] command-center status franchise_id=%s week=%s status=%s phase_b_required=%s completed=%s/%s failed=%s",
                franchise_id,
                _csr.get("week"),
                _csr.get("status"),
                _csr.get("phase_b_required"),
                _csr.get("completed_matchups"),
                _csr.get("expected_matchups"),
                _csr.get("failed_matchups"),
            )
        recruiting_results = franchise_doc.get("recruiting_results", {}) if franchise_doc else {}
        current_results_week = week if week is not None and str(week) in (recruiting_results or {}) else None
        response["current_recruiting_results_week"] = current_results_week
        if franchise_doc and week is not None and week >= 35:
            awards = _persist_week_35_awards_if_needed(franchise_doc)
            response["awards_ready"] = bool((awards or {}).get("all_american_teams"))
        else:
            response["awards_ready"] = False
        if franchise_id and franchise_doc and team_id:
            try:
                user_ftd_doc = franchise_team_data_collection.find_one(
                    {"franchise_id": fid, "team_id": ObjectId(str(team_id))},
                    {"Recruits": 1},
                ) or {}
                response["lean_recruits"] = list(
                    franchise_recruits_data_collection.find(
                        {
                            "franchise_id": str(fid),
                            "$or": [
                                {"Lean.1": team_id},
                                {"Lean.2": team_id},
                                {"Lean.3": team_id},
                            ],
                        },
                        {"_id": 0, "franchise_id": 0},
                    )
                )
                response["team_name_map"] = {
                    str(team["_id"]): team.get("name", str(team["_id"]))
                    for team in db.teams.find({}, {"name": 1})
                }
                week_35_results = franchise_doc.get(WEEK_35_RECRUITING_RESULTS_FIELD) or {}
                response["week_35_user_recruits"] = [
                    player
                    for player in (week_35_results.get("signed_players") or [])
                    if str(player.get("team_id") or "") == str(team_id)
                ]
                response["current_week_invite_recruit"] = _fcc_current_week_invite_recruit(
                    franchise_doc,
                    str(team_id),
                    user_ftd_doc.get("Recruits"),
                )
                pending_new_lean_ids = [
                    str(rid)
                    for rid in (franchise_doc.get(FCC_PENDING_NEW_LEAN_RECRUITS_FIELD) or [])
                    if rid
                ]
                if pending_new_lean_ids and _find_user_last_completed_game(franchise_doc, str(team_id)):
                    lean_recruit_ids = {
                        str(recruit.get("recruit_id"))
                        for recruit in response["lean_recruits"]
                        if recruit.get("recruit_id")
                    }
                    response["new_lean_recruit_ids"] = [
                        rid for rid in pending_new_lean_ids if rid in lean_recruit_ids
                    ]
                else:
                    response["new_lean_recruit_ids"] = []
            except Exception as e:
                logger.debug("fcc lean recruits: %s", e)
                response["lean_recruits"] = []
                response["team_name_map"] = {}
                response["week_35_user_recruits"] = []
                response["current_week_invite_recruit"] = None
                response["new_lean_recruit_ids"] = []
        else:
            response["lean_recruits"] = []
            response["team_name_map"] = {}
            response["week_35_user_recruits"] = []
            response["current_week_invite_recruit"] = None
            response["new_lean_recruit_ids"] = []
        response["training_status"] = (
            {"training_completed": training_completed, "session_type": session_type}
            if franchise_id and franchise_doc else {}
        )
        last_training_report_week = None
        if franchise_doc:
            lt = franchise_doc.get("latest_training") or {}
            w = lt.get("week")
            if w is not None:
                try:
                    last_training_report_week = int(w)
                except (TypeError, ValueError):
                    last_training_report_week = None
        response["last_training_report_week"] = last_training_report_week
        response["season_inbox"] = list(franchise_doc.get("season_inbox") or []) if franchise_doc else []
        response["news_headlines"] = _franchise_news_headlines(franchise_doc) if franchise_doc else []
        if franchise_doc:
            try:
                from BackEnd.utils.franchise_championship_moments import list_moments

                response["pending_championship_moments"] = list_moments(franchise_doc)
            except Exception:
                logger.exception(
                    "[CHAMP-MOMENT] list_moments failed franchise_id=%s", str(fid)
                )
                response["pending_championship_moments"] = []
        else:
            response["pending_championship_moments"] = []
        # Region EOS: ensure persisted brackets match conference champions + RS#1 (fixes legacy TBD / half rows).
        if (
            franchise_doc
            and franchise_doc.get("_id")
            and week in ft.EOS_REGION_WEEKS
            and franchise_doc.get("region_tournaments")
        ):
            fid_obj = franchise_doc["_id"]
            eos_team_ids = [
                d["team_id"]
                for d in franchise_team_data_collection.find({"franchise_id": fid_obj}, {"team_id": 1})
                if d.get("team_id") is not None
            ]
            fcc_reconcile_persisted = False
            if eos_team_ids:
                updated_rt = ft.reconcile_region_tournaments_with_canonical(
                    franchise_doc, db.teams, eos_team_ids
                )
                if updated_rt is not None:
                    franchise_doc["region_tournaments"] = updated_rt
                    db.franchises.update_one({"_id": fid_obj}, {"$set": {"region_tournaments": updated_rt}})
                    fcc_reconcile_persisted = True
                logger.warning(
                    "[EOS-REGION-RECONCILE] context=fcc week=%s franchise_id=%s persisted=%s ftd_team_count=%s",
                    week,
                    str(fid_obj),
                    fcc_reconcile_persisted,
                    len(eos_team_ids),
                )
            else:
                logger.warning(
                    "[EOS-REGION-RECONCILE] context=fcc week=%s franchise_id=%s persisted=%s ftd_team_count=0",
                    week,
                    str(fid_obj),
                    False,
                )
        post_eos_bracket_history_visible = bool(
            not eos_tournament_active
            and week in {35, 36}
            and (
                franchise_doc.get("conference_tournaments")
                or franchise_doc.get("region_tournaments")
                or franchise_doc.get("national_tournament")
            )
        )
        week_val = week if week is not None else 1
        if eos_tournament_active or post_eos_bracket_history_visible:
            response["eos_tournament_active"] = True
            response["conference_tournaments"] = franchise_doc.get("conference_tournaments")
            response["region_tournaments"] = franchise_doc.get("region_tournaments")
            response["national_tournament"] = national_tournament
            # Derive single eos_tournament (old shape) for FCC bracket display: pick current phase by week
            if week_val in ft.EOS_CONFERENCE_WEEKS:
                user_conf = team_doc.get("conference") if team_doc else None
                ct = (franchise_doc.get("conference_tournaments") or {}).get(str(user_conf), {}) if user_conf is not None else {}
                response["eos_tournament"] = ct if ct else None
            elif week_val in ft.EOS_REGION_WEEKS:
                user_region = (team_doc.get("region") or "").upper() if team_doc else ""
                if isinstance(user_region, str) and len(user_region) == 1:
                    rt = (franchise_doc.get("region_tournaments") or {}).get(user_region, {})
                    if rt:
                        final_list = rt.get("final", [])
                        champ = final_list[0].get("winner") if final_list and final_list[0].get("winner") else None
                        response["eos_tournament"] = {
                            "bracket": {"round1": rt.get("round1", []), "round2": [], "final": final_list},
                            "seeds": {},
                            "current_round": rt.get("current_round", 1),
                            "champion": champ,
                        }
                    else:
                        response["eos_tournament"] = None
                else:
                    response["eos_tournament"] = None
            elif week_val in ft.EOS_NATIONAL_WEEKS:
                response["eos_tournament"] = national_tournament if national_tournament else None
            else:
                response["eos_tournament"] = None
            # Championship summary when national tournament is complete (week 34 done)
            if national_tournament.get("champion"):
                bracket = national_tournament.get("bracket", {})
                final_list = bracket.get("final", [])
                final_matchup = final_list[0] if final_list else {}
                home_team_id = final_matchup.get("home_team")
                away_team_id = final_matchup.get("away_team")
                winner_id = final_matchup.get("winner") or national_tournament.get("champion")
                score = final_matchup.get("score") or {}
                home_score = score.get("home")
                away_score = score.get("away")
                id_to_name = {}
                for tid in [home_team_id, away_team_id, winner_id]:
                    if not tid:
                        continue
                    try:
                        tdoc = db.teams.find_one({"_id": ObjectId(tid)}, {"name": 1})
                        if tdoc:
                            id_to_name[str(tid)] = tdoc.get("name", str(tid))
                    except Exception:
                        id_to_name[str(tid)] = str(tid)
                response["championship_summary"] = {
                    "game_id": final_matchup.get("game_id"),
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "home_team_name": id_to_name.get(str(home_team_id), home_team_id),
                    "away_team_name": id_to_name.get(str(away_team_id), away_team_id),
                    "home_score": home_score,
                    "away_score": away_score,
                    "winner_team_id": winner_id,
                    "winner_team_name": id_to_name.get(str(winner_id), winner_id),
                }
        eos_status = (
            _get_user_eos_phase_status(franchise_doc, str(team_id), week)
            if franchise_id and franchise_doc and team_id and eos_tournament_active and week in ft.EOS_WEEKS
            else {}
        )
        training_disabled_for_eos = bool(
            eos_status.get("eliminated_from_current_phase", False)
        ) if eos_status else False
        response["training_disabled_for_eos"] = training_disabled_for_eos
        response["training_disabled_for_postseason"] = _postseason_training_disabled_for_week(week)
        response["eog_team_attrs_frozen_for_postseason"] = _postseason_eog_team_attrs_disabled_for_week(week)
        user_eliminated = training_disabled_for_eos
        tournament_complete = bool(national_tournament.get("champion")) if national_tournament else False
        user_has_bye = bool(eos_status.get("has_bye_this_week", False)) if eos_status else False
        region_qualified_waiting = bool(
            eos_status.get("region_qualified")
            and not eos_status.get("has_game_this_week")
            and week_val in ft.EOS_CONFERENCE_WEEKS
        ) if eos_status else False
        has_playable_eos_round = (
            week_val not in ft.EOS_WEEKS
            or week_val == ft.EOS_REGION_WEEKS[0]
            or (
                franchise_doc
                and len(ft.get_eos_week_games(franchise_doc, week_val, include_completed=False)) > 0
            )
        )
        offer_sim_rest = (
            (user_eliminated or user_has_bye or region_qualified_waiting)
            and eos_tournament_active
            and not tournament_complete
            and has_playable_eos_round
        )
        response["user_eliminated"] = user_eliminated
        response["offer_sim_rest"] = offer_sim_rest
        response["region_qualified"] = bool(eos_status.get("region_qualified")) if eos_status else False
        response["has_eos_game_this_week"] = bool(eos_status.get("has_game_this_week")) if eos_status else False
        response["region_bye_modal_eligible"] = bool(
            _should_show_region_bye_modal(
                franchise_doc,
                str(team_id) if team_id else None,
            )
        )
        response["bracket_reveal_modal"] = (
            _build_bracket_reveal_modal_payload(franchise_doc, team_doc, week)
            if franchise_doc and team_doc
            else None
        )
        response["bracket_update_modal"] = (
            _build_bracket_update_modal_payload(franchise_doc, team_doc, week)
            if franchise_doc and team_doc
            else None
        )
        response["recruiting_results_modal"] = (
            _build_recruiting_results_modal_payload(franchise_doc, str(team_id) if team_id else None)
            if franchise_doc
            else None
        )
        return response
    if profile:
        from BackEnd.utils.profiling import run_profiled
        _out = [None]
        def _wrapped():
            _out[0] = _build()
        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        result["profile_summary"] = profile_summary
        return result
    return _build()


def _ftd_team_list_for_franchise(franchise_id) -> dict:
    """Return {team_id_str: {}} for all teams in FTD. Used as team list by standings, stats, traits."""
    fid = ObjectId(franchise_id) if isinstance(franchise_id, str) else franchise_id
    docs = list(franchise_team_data_collection.find({"franchise_id": fid}, {"team_id": 1}))
    return {str(d["team_id"]): {} for d in docs}


def _sister_conference(conference: int) -> int:
    """Same region, other conference. Conferences 1-2 = region A, 3-4 = B, ... 15-16 = H."""
    if not isinstance(conference, int) or conference < 1 or conference > 16:
        return conference
    return conference + 1 if conference % 2 == 1 else conference - 1


def _schedule_game_key(week: int, away_id: Any, home_id: Any) -> tuple[int, str, str]:
    away_str = str(away_id)
    home_str = str(home_id)
    low, high = sorted([away_str, home_str])
    return (int(week), low, high)


def _get_schedule_game_doc_map(franchise_id: str, max_week: int = 26) -> dict[tuple[int, str, str], dict[str, Any]]:
    game_doc_map: dict[tuple[int, str, str], dict[str, Any]] = {}
    cursor = db.games.find(
        {
            "franchise_id": str(franchise_id),
            "week": {"$gte": 1, "$lte": int(max_week)},
        },
        {
            "_id": 1,
            "week": 1,
            "team1_id": 1,
            "team2_id": 1,
            "team1_score": 1,
            "team2_score": 1,
            "home_team_id": 1,
            "away_team_id": 1,
        },
    )
    for doc in cursor:
        week = doc.get("week")
        team1_id = doc.get("team1_id") or doc.get("away_team_id")
        team2_id = doc.get("team2_id") or doc.get("home_team_id")
        if week is None or not team1_id or not team2_id:
            continue
        key = _schedule_game_key(int(week), team1_id, team2_id)
        existing = game_doc_map.get(key)
        if not existing:
            game_doc_map[key] = doc
            continue
        existing_score = int(bool(existing.get("team1_score") is not None or existing.get("team2_score") is not None))
        current_score = int(bool(doc.get("team1_score") is not None or doc.get("team2_score") is not None))
        if current_score > existing_score:
            game_doc_map[key] = doc
    return game_doc_map


def _eos_schedule_score_for_side(score: dict[str, Any], side: str, team_id: str) -> Any:
    if not isinstance(score, dict):
        return None
    if side in score:
        return score.get(side)
    return score.get(team_id)


def _build_eos_schedule_payload(
    franchise_doc: dict[str, Any],
    team_conferences: dict[str, Any] | None = None,
) -> tuple[dict[int, list[dict[str, Any]]], set[str]]:
    eos_schedule: dict[int, list[dict[str, Any]]] = {}
    included_team_ids: set[str] = set()
    team_conf = team_conferences or {}

    for week in ft.EOS_WEEKS:
        week_games: list[dict[str, Any]] = []
        for game in ft.get_eos_week_games(franchise_doc, week, include_completed=True):
            away_str = str(game.get("away_id") or "")
            home_str = str(game.get("home_id") or "")
            if not away_str or not home_str:
                continue

            score = game.get("score") or {}
            away_score = _eos_schedule_score_for_side(score, "away", away_str)
            home_score = _eos_schedule_score_for_side(score, "home", home_str)
            is_complete = bool(game.get("winner")) or (away_score is not None and home_score is not None)

            phase = str(game.get("phase") or "")
            context = ""
            if phase == "conference":
                c_raw = game.get("conference")
                context = f"Conference {c_raw}"
                try:
                    c_int = int(c_raw)
                    away_c = home_c = c_int
                except (TypeError, ValueError):
                    away_c = team_conf.get(away_str)
                    home_c = team_conf.get(home_str)
            elif phase == "region":
                context = f"Region {game.get('region')}"
                away_c, home_c = team_conf.get(away_str), team_conf.get(home_str)
            elif phase == "national":
                context = "National"
                away_c, home_c = team_conf.get(away_str), team_conf.get(home_str)
            else:
                away_c, home_c = team_conf.get(away_str), team_conf.get(home_str)

            week_games.append({
                "week": week,
                "away_team_id": away_str,
                "home_team_id": home_str,
                "away_score": away_score,
                "home_score": home_score,
                "status": "complete" if is_complete else "scheduled",
                "game_id": str(game.get("game_id")) if game.get("game_id") else None,
                "phase": phase,
                "round": game.get("round"),
                "matchup_index": game.get("matchup_index"),
                "tournament_context": context,
                "away_conference": away_c,
                "home_conference": home_c,
            })
            included_team_ids.add(away_str)
            included_team_ids.add(home_str)
        eos_schedule[week] = week_games

    return eos_schedule, included_team_ids


def _build_season_schedule_payload(
    franchise_id: str,
    conference: Optional[int] = None,
    user_team_only: bool = False,
) -> dict[str, Any]:
    franchise_doc = db.franchises.find_one(
        {"_id": ObjectId(franchise_id)},
        {
            "schedule": 1,
            "results": 1,
            "eos_tournament": 1,
            "eos_tournament_active": 1,
            "conference_tournaments": 1,
            "region_tournaments": 1,
            "national_tournament": 1,
            "user_team_id": 1,
            "user_team_object_id": 1,
            "_id": 1,
        },
    )
    found = franchise_doc is not None
    logger.info("season_schedule franchise_id=%s found=%s", franchise_id, found)
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    schedule = franchise_doc.get("schedule", [])
    user_team_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    team_id = user_team_object_id if user_team_object_id else None

    training_reports = {}
    if team_id and ObjectId.is_valid(team_id):
        try:
            ftd = franchise_team_data_collection.find_one(
                {"franchise_id": ObjectId(franchise_id), "team_id": ObjectId(team_id)},
                {"training_reports": 1},
            )
            if ftd:
                training_reports = ftd.get("training_reports", {})
        except Exception:
            pass

    team_docs = list(db.teams.find({}, {"_id": 1, "conference": 1, "name": 1, "mascot": 1}))
    team_conferences = {str(t["_id"]): t.get("conference") for t in team_docs}
    team_name_lookup = {str(t["_id"]): t.get("name", str(t["_id"])) for t in team_docs}
    game_doc_map = _get_schedule_game_doc_map(franchise_id, 26)

    weeks: list[list[dict[str, Any]]] = []
    results_by_week = franchise_doc.get("results", {})
    included_team_ids: set[str] = set()

    for idx, games in enumerate(schedule, start=1):
        week_games = []
        week_results = {
            (str(r["away_id"]), str(r["home_id"])): (r["away_score"], r["home_score"])
            for r in results_by_week.get(str(idx), [])
        }
        for away_id, home_id in games:
            away_str = str(away_id)
            home_str = str(home_id)

            if user_team_only and team_id and team_id not in {away_str, home_str}:
                continue

            if conference is not None:
                away_conf = team_conferences.get(away_str)
                home_conf = team_conferences.get(home_str)
                if away_conf != conference and home_conf != conference:
                    continue

            res = week_results.get((away_str, home_str)) or week_results.get((home_str, away_str))
            game_doc = game_doc_map.get(_schedule_game_key(idx, away_str, home_str))

            if res:
                away_score, home_score = res
                status = "complete"
            elif game_doc:
                status = "complete"
                if str(game_doc.get("team1_id")) == away_str:
                    away_score = game_doc.get("team1_score")
                    home_score = game_doc.get("team2_score")
                elif str(game_doc.get("team2_id")) == away_str:
                    away_score = game_doc.get("team2_score")
                    home_score = game_doc.get("team1_score")
                else:
                    away_score = game_doc.get("team1_score")
                    home_score = game_doc.get("team2_score")
            else:
                status = "scheduled"
                away_score = None
                home_score = None

            has_training_report = bool(team_id and team_id in {away_str, home_str} and str(idx) in training_reports)
            game_id = str(game_doc.get("_id")) if status == "complete" and game_doc and game_doc.get("_id") else None

            week_games.append({
                "week": idx,
                "away_team_id": away_str,
                "home_team_id": home_str,
                "away_score": away_score,
                "home_score": home_score,
                "status": status,
                "has_training_report": has_training_report,
                "is_user_team": bool(team_id and team_id in {away_str, home_str}),
                "game_id": game_id,
                "away_conference": team_conferences.get(away_str),
                "home_conference": team_conferences.get(home_str),
            })
            included_team_ids.add(away_str)
            included_team_ids.add(home_str)
        weeks.append(week_games)

    eos_schedule, eos_team_ids = _build_eos_schedule_payload(franchise_doc, team_conferences)
    included_team_ids.update(eos_team_ids)

    team_name_map = {
        team_id_str: team_name_lookup.get(team_id_str, team_id_str)
        for team_id_str in included_team_ids
    }
    ftd_rank_docs = list(franchise_team_data_collection.find(
        {"franchise_id": ObjectId(franchise_id)},
        {"team_id": 1, "natl_rank": 1},
    ))
    natl_rank_by_team_id = {
        str(doc["team_id"]): int(doc.get("natl_rank", 999) or 999)
        for doc in ftd_rank_docs
        if doc.get("team_id")
    }
    team_display_name_map = {
        team_id_str: _format_team_name_with_rank(team_id_str, team_name, natl_rank_by_team_id)
        for team_id_str, team_name in team_name_map.items()
    }

    logger.info(
        "season_schedule returning franchise_id=%s found=%s conference=%s user_team_only=%s weeks=%s",
        franchise_id,
        found,
        conference,
        user_team_only,
        len(weeks),
    )
    return {
        "schedule": weeks,
        "tournament_schedule": eos_schedule,
        "team_id": team_id,
        "team_name": user_team_name,
        "team_conferences": team_conferences,
        "team_name_map": team_name_map,
        "team_display_name_map": team_display_name_map,
        "conference": conference,
    }


@router.get("/franchise/standings")
def standings(
    franchise_id: str,
    profile: bool = False,
    scope: Optional[str] = None,
    team_id: Optional[str] = None,
    region: Optional[str] = None,
):
    """Add ?profile=1 for profile_summary. scope=user_region&team_id=... returns only user + sister conference."""
    import time
    def _build():
        franchise_doc = db.franchises.find_one(
            {"_id": ObjectId(franchise_id)},
            {
                "schedule": 1,
                "week": 1,
                "eos_tournament": 1,
                "eos_tournament_active": 1,
                "conference_tournaments": 1,
                "region_tournaments": 1,
                "national_tournament": 1,
                "results": 1,
                "_id": 1,
            }
        )
        found = franchise_doc is not None
        logger.info("standings franchise_id=%s found=%s", franchise_id, found)
        if not franchise_doc:
            raise HTTPException(status_code=404, detail="Franchise not found")
        schedule = franchise_doc.get("schedule", [])
        week = franchise_doc.get("week", 1)
        from BackEnd.utils.franchise_standings import calculate_franchise_standings
        franchise_results = franchise_doc.get("results", {})
        team_list = _ftd_team_list_for_franchise(franchise_id)
        standings_data = calculate_franchise_standings(franchise_results, team_list)
        # Load natl_rank from FTD for tiebreaker (lower natl_rank = higher in standings)
        fid = ObjectId(franchise_id)
        ftd_rank_docs = list(franchise_team_data_collection.find(
            {"franchise_id": fid},
            {"team_id": 1, "natl_rank": 1},
        ))
        natl_rank_by_team_id = {str(d["team_id"]): d.get("natl_rank", 999) for d in ftd_rank_docs if d.get("team_id")}
        team_name_by_id = {
            str(t["_id"]): t.get("name", "")
            for t in db.teams.find({}, {"name": 1})
        }
        matchup_map = _build_next_matchup_map(franchise_doc, team_name_by_id, natl_rank_by_team_id)
        team_ids_list = [ObjectId(tid) for tid in team_list.keys()]
        teams = list(db.teams.find(
            {"_id": {"$in": team_ids_list}},
            {"name": 1, "_id": 1, "region": 1, "conference": 1}
        ))
        output = []
        for t in teams:
            team_id_str = str(t["_id"])
            team_standings = standings_data.get(team_id_str, {"W": 0, "L": 0, "PF": 0, "PA": 0})
            wins = team_standings.get("W", 0)
            losses = team_standings.get("L", 0)
            games_played = wins + losses
            pct = round(wins / games_played, 3) if games_played else 0.0
            pf = team_standings.get("PF", 0)
            pa = team_standings.get("PA", 0)
            differential = pf - pa
            natl_rank = natl_rank_by_team_id.get(team_id_str, 999)
            output.append({
                "team_id": team_id_str,
                "name": t.get("name", ""),
                "region": t.get("region") or "",
                "conference": t.get("conference"),
                "W": wins,
                "L": losses,
                "pct": pct,
                "PF": pf,
                "PA": pa,
                "differential": differential,
                "natl_rank": natl_rank,
                "next": matchup_map.get(team_id_str, "")
            })
        # Primary: wins desc. Tiebreaker: natl_rank asc (lower = higher in standings)
        output.sort(key=lambda x: (-x["W"], x["natl_rank"]))

        # Optional: return only user + sister conference (lighter payload for FCC Standings tab)
        result = {"standings": output}
        if scope == "user_region" and team_id:
            try:
                tid = ObjectId(team_id) if ObjectId.is_valid(team_id) else None
                if tid:
                    user_team_doc = db.teams.find_one({"_id": tid}, {"conference": 1})
                    user_conf = user_team_doc.get("conference") if user_team_doc else None
                    if user_conf is not None and isinstance(user_conf, int):
                        sister = _sister_conference(user_conf)
                        allowed = {user_conf, sister}
                        output_filtered = [x for x in output if x.get("conference") in allowed]
                        result["standings"] = output_filtered
                        result["user_conference"] = user_conf
                        result["sister_conference"] = sister
            except Exception as e:
                logger.warning("standings scope=user_region failed: %s", e)

        if region:
            region_normalized = str(region).strip().upper()
            result["standings"] = [
                item for item in (result.get("standings") or [])
                if str(item.get("region") or "").upper() == region_normalized
            ]

        logger.info("standings returning franchise_id=%s found=%s", franchise_id, found)
        return result
    if profile:
        from BackEnd.utils.profiling import run_profiled
        _out = [None]
        def _wrapped():
            _out[0] = _build()
        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        result["profile_summary"] = profile_summary
        return result
    return _build()


@router.get("/franchise/schedule")
def season_schedule(franchise_id: str, conference: Optional[int] = None, user_team_only: bool = False):
    if conference is not None and (not isinstance(conference, int) or conference < 1 or conference > 16):
        raise HTTPException(status_code=422, detail="conference must be an integer from 1 to 16")
    return _build_season_schedule_payload(
        franchise_id=franchise_id,
        conference=conference,
        user_team_only=bool(user_team_only),
    )


@router.get("/franchise/schedule/national")
def national_schedule(franchise_id: str):
    return _build_season_schedule_payload(franchise_id=franchise_id)


def get_leaders(
    franchise_id: str,
    scope: str = "season",
    stat: str = "PTS",
    limit: int = 10,
    allowed_team_ids: Optional[set[str]] = None,
    allowed_team_names: Optional[set[str]] = None,
):
    """Return the top players for a given stat within a franchise.

    ✅ FPD: Reads from franchise_players_data (season/career stats), not franchise.players.
    """
    import time
    start_time = time.time()

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    # ✅ FIX: Map TPM to 3PTM for aggregation
    stat_field = stat
    if stat == "TPM":
        stat_field = "3PTM"
    elif stat == "TPA":
        stat_field = "3PTA"

    # ✅ FPD: Aggregate from franchise_players_data (season/career live here)
    aggregation_start = time.time()
    pipeline = [{"$match": {"franchise_id": str(franchise_id)}}]
    if allowed_team_ids or allowed_team_names:
        team_filters = []
        if allowed_team_ids:
            team_filters.append({"meta.team_id": {"$in": list(allowed_team_ids)}})
        if allowed_team_names:
            team_filters.append({"meta.team": {"$in": list(allowed_team_names)}})
        pipeline.append({"$match": {"$or": team_filters}})

    if stat in {"FG%", "DEF%"}:
        numerator_field = "FGM" if stat == "FG%" else "DEF_S"
        denominator_field = "FGA" if stat == "FG%" else "DEF_A"
        pipeline.extend([
            {
                "$project": {
                    "player_id": 1,
                    "meta": 1,
                    "gp": {"$ifNull": [f"${scope}.GP", 0]},
                    "numerator": {"$ifNull": [f"${scope}.{numerator_field}", 0]},
                    "denominator": {"$ifNull": [f"${scope}.{denominator_field}", 0]},
                }
            },
            {
                "$match": {
                    "$expr": {
                        "$and": [
                            {"$gt": ["$gp", 0]},
                            {"$gte": ["$denominator", {"$multiply": ["$gp", 5]}]},
                        ]
                    }
                }
            },
            {
                "$project": {
                    "player_id": 1,
                    "meta": 1,
                    "value": {
                        "$cond": [
                            {"$gt": ["$denominator", 0]},
                            {"$multiply": [{"$divide": ["$numerator", "$denominator"]}, 100]},
                            0,
                        ]
                    },
                    "tiebreak_volume": "$denominator",
                }
            },
            {"$sort": {"value": -1, "tiebreak_volume": -1}},
            {"$limit": limit},
        ])
    else:
        pipeline.extend([
            {
                "$project": {
                    "player_id": 1,
                    "meta": 1,
                    "value": {"$ifNull": [f"${scope}.{stat_field}", 0]},
                }
            },
            {"$sort": {"value": -1}},
            {"$limit": limit},
        ])

    agg = list(franchise_players_data_collection.aggregate(pipeline))
    aggregation_time = time.time() - aggregation_start
    # logger.info(f"⏱️ [PERF] get_leaders('{stat}') Aggregation pipeline (FPD): {aggregation_time:.3f}s")
    results: list[dict[str, Any]] = []
    for p in agg:
        meta = p.get("meta", {})
        value = p.get("value", 0)
        if stat == "FG%":
            value = round(float(value or 0), 1)
        elif stat == "DEF%":
            value = int(round(float(value or 0)))
        results.append(
            {
                "player_id": p.get("player_id"),
                "first_name": meta.get("first_name", ""),
                "last_name": meta.get("last_name", ""),
                "team": meta.get("team", meta.get("team_id", "")),
                "value": value,
            }
        )
    total_time = time.time() - start_time
    # logger.info(f"⏱️ [PERF] get_leaders('{stat}') COMPLETE (aggregation): {total_time:.3f}s")
    return results


@router.get("/franchise/leaders")
def leaders(
    franchise_id: str,
    scope: str = "season",
    limit: int = 10,
    view_scope: str = "national",
):
    import time
    start_time = time.time()
    # logger.info(f"⏱️ [PERF] /franchise/leaders START - franchise_id={franchise_id}, scope={scope}")
    
    categories = ["PTS", "3PTM", "AST", "BLK", "FG%", "REB", "STL", "DEF%"]
    allowed_team_ids: Optional[set[str]] = None
    allowed_team_names: Optional[set[str]] = None
    if view_scope in {"conference", "region"}:
        franchise_doc = db.franchises.find_one(
            {"_id": ObjectId(franchise_id)},
            {"user_team_object_id": 1, "user_team_id": 1},
        )
        user_team_id = None
        if franchise_doc:
            _, user_team_id = get_user_team_from_franchise(franchise_doc)
        if user_team_id and ObjectId.is_valid(user_team_id):
            user_team_doc = db.teams.find_one({"_id": ObjectId(user_team_id)}, {"conference": 1, "region": 1})
            if user_team_doc:
                query = {}
                if view_scope == "conference":
                    query["conference"] = user_team_doc.get("conference")
                else:
                    query["region"] = user_team_doc.get("region", "")
                team_docs = list(db.teams.find(query, {"_id": 1, "name": 1}))
                allowed_team_ids = {str(team["_id"]) for team in team_docs}
                allowed_team_names = {team.get("name", "") for team in team_docs if team.get("name")}
    result: dict[str, list[dict[str, Any]]] = {}
    for cat in categories:
        cat_start = time.time()
        top = get_leaders(
            franchise_id,
            scope=scope,
            stat=cat,
            limit=limit,
            allowed_team_ids=allowed_team_ids,
            allowed_team_names=allowed_team_names,
        )
        cat_time = time.time() - cat_start
        result[cat] = [
            {
                "player_id": p.get("player_id"),
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "team": p.get("team"),
                "value": p.get("value", 0),
            }
            for p in top
        ]
    all_team_names = set()
    for cat in categories:
        for entry in result[cat]:
            tn = entry.get("team")
            if tn:
                all_team_names.add(tn)
    team_meta = {}
    if all_team_names:
        for t in db.teams.find({"name": {"$in": list(all_team_names)}}, {"name": 1, "conference": 1, "region": 1}):
            team_meta[t.get("name", "")] = {"conference": t.get("conference"), "region": t.get("region", "")}
    for cat in categories:
        for entry in result[cat]:
            meta = team_meta.get(entry.get("team") or "", {})
            entry["conference"] = meta.get("conference")
            entry["region"] = meta.get("region", "")
    
    total_time = time.time() - start_time
    # logger.info(f"⏱️ [PERF] /franchise/leaders COMPLETE: {total_time:.3f}s")
    return result


@router.get("/franchise/team-stats")
def team_stats(franchise_id: str, scope: str = "national"):
    """Get team stats by aggregating player stats from franchise document.
    
    ✅ SS&S: Aggregates from franchise.players object (franchise-specific stats),
    not from universal players_collection.
    """
    import time
    start_time = time.time()
    # logger.info(f"⏱️ [PERF] /franchise/team-stats START - franchise_id={franchise_id}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id")
    
    db_query_start = time.time()
    franchise_doc = db.franchises.find_one({"_id": fid}, {"results": 1, "user_team_id": 1, "user_team_object_id": 1})
    db_query_time = time.time() - db_query_start
    # logger.info(f"⏱️ [PERF] /franchise/team-stats DB query: {db_query_time:.3f}s")
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(franchise_id)}))
    players = {d["player_id"]: d for d in fpd_docs}
    franchise_results = franchise_doc.get("results", {})
    team_list = _ftd_team_list_for_franchise(fid)
    if scope in {"conference", "region"}:
        user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        if user_team_object_id and ObjectId.is_valid(user_team_object_id):
            user_team_doc = db.teams.find_one({"_id": ObjectId(user_team_object_id)}, {"conference": 1, "region": 1})
            if user_team_doc:
                filtered_team_list = {}
                for team_id_str, team_name in team_list.items():
                    if not ObjectId.is_valid(team_id_str):
                        continue
                    team_doc = db.teams.find_one({"_id": ObjectId(team_id_str)}, {"conference": 1, "region": 1})
                    if not team_doc:
                        continue
                    if scope == "conference" and team_doc.get("conference") == user_team_doc.get("conference"):
                        filtered_team_list[team_id_str] = team_name
                    if scope == "region" and team_doc.get("region", "") == user_team_doc.get("region", ""):
                        filtered_team_list[team_id_str] = team_name
                team_list = filtered_team_list
    # Build team_id -> [player_id, ...] from FTD.players for aggregation (prefer over meta.team_id)
    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": fid}, {"team_id": 1, "players": 1, "natl_rank": 1}))
    franchise_team_rosters = {}
    natl_rank_by_team_id = {}
    for ftd in ftd_docs:
        tid_str = str(ftd["team_id"])
        roster = ftd.get("players") or []
        franchise_team_rosters[tid_str] = [str(pid) for pid in roster]
        natl_rank_by_team_id[tid_str] = int(ftd.get("natl_rank", 999) or 999)
    
    # logger.info(f"⏱️ [PERF] /franchise/team-stats Found {len(players)} players, {len(team_list)} teams, {len(franchise_results)} weeks of results")
    
    aggregation_start = time.time()
    output = aggregate_team_stats_from_players(
        players=players,
        team_ids=team_list,
        teams_collection=db.teams,
        collection_type='franchise',
        logger=logger,
        franchise_results=franchise_results,
        franchise_team_rosters=franchise_team_rosters if franchise_team_rosters else None,
    )
    aggregation_time = time.time() - aggregation_start
    # logger.info(f"⏱️ [PERF] /franchise/team-stats Aggregation: {aggregation_time:.3f}s")
    team_ids_for_meta = [ObjectId(t["team_id"]) for t in output if t.get("team_id")]
    if team_ids_for_meta:
        team_meta_docs = list(db.teams.find({"_id": {"$in": team_ids_for_meta}}, {"_id": 1, "conference": 1, "region": 1, "mascot": 1}))
        id_to_meta = {
            str(d["_id"]): {
                "conference": d.get("conference"),
                "region": d.get("region", ""),
                "mascot": d.get("mascot", ""),
            }
            for d in team_meta_docs
        }
        for t in output:
            meta = id_to_meta.get(t.get("team_id", ""), {})
            t["conference"] = meta.get("conference")
            t["region"] = meta.get("region", "")
            t["mascot"] = meta.get("mascot", "")
            t["natl_rank"] = natl_rank_by_team_id.get(t.get("team_id", ""), 999)
    else:
        for t in output:
            t["natl_rank"] = natl_rank_by_team_id.get(t.get("team_id", ""), 999)

    total_time = time.time() - start_time
    # logger.info(f"⏱️ [PERF] /franchise/team-stats COMPLETE: {total_time:.3f}s")
    return {"teams": output}


@router.get("/franchise/team-traits")
def team_traits(franchise_id: str, scope: str = "national"):
    """Get team attribute totals for all teams in franchise.
    
    ✅ SS&S: Aggregates from franchise.players object (franchise-specific attributes),
    not from universal players_collection.
    """
    import time
    start_time = time.time()
    # logger.info(f"⏱️ [PERF] /franchise/team-traits START - franchise_id={franchise_id}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id")
    
    db_query_start = time.time()
    franchise_doc = db.franchises.find_one({"_id": fid}, {"_id": 1})
    db_query_time = time.time() - db_query_start
    # logger.info(f"⏱️ [PERF] /franchise/team-traits DB query: {db_query_time:.3f}s")
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(franchise_id)}))
    players = {d["player_id"]: d for d in fpd_docs}
    team_list = _ftd_team_list_for_franchise(fid)
    user_team_scope = None
    if scope in {"conference", "region"}:
        user_team_id, user_team_object_id = get_user_team_from_franchise(db.franchises.find_one({"_id": fid}, {"user_team_id": 1, "user_team_object_id": 1}))
        if user_team_object_id and ObjectId.is_valid(user_team_object_id):
            user_team_scope = db.teams.find_one({"_id": ObjectId(user_team_object_id)}, {"conference": 1, "region": 1})
    
    # logger.info(f"⏱️ [PERF] /franchise/team-traits Found {len(players)} players, {len(team_list)} teams")
    
    attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT"]
    team_totals = {}
    team_names = {}
    
    for team_id_str in team_list.keys():
        try:
            team_doc = db.teams.find_one({"_id": ObjectId(team_id_str)}, {"name": 1, "primary_color": 1, "conference": 1, "region": 1})
            if team_doc:
                if user_team_scope and scope == "conference" and team_doc.get("conference") != user_team_scope.get("conference"):
                    continue
                if user_team_scope and scope == "region" and team_doc.get("region", "") != user_team_scope.get("region", ""):
                    continue
                team_name = team_doc.get("name", team_id_str)
                team_names[team_id_str] = team_name
                team_totals[team_id_str] = {
                    "team_name": team_name,
                    "primary_color": team_doc.get("primary_color", "#000000"),
                    "conference": team_doc.get("conference"),
                    "region": team_doc.get("region", ""),
                    "attributes": {attr: 0 for attr in attributes}
                }
        except Exception:
            # Skip invalid ObjectIds
            continue
    
    # Aggregate attributes from players
    # ✅ SS&S: Use franchise.players as single source of truth (no merging with universal collection)
    for pid, player_data in players.items():
        meta = player_data.get("meta", {})
        player_team_id = str(meta.get("team_id", ""))
        
        # ✅ FIX: If team_id is missing or not in team_totals, resolve it from team name (similar to team_stats_aggregator.py)
        if not player_team_id or player_team_id not in team_totals:
            # Try to resolve team_id from team name
            team_name = meta.get("team", "")
            if team_name:
                try:
                    # Try to find team by name
                    team_doc = db.teams.find_one({"name": team_name}, {"_id": 1})
                    if team_doc:
                        resolved_team_id = str(team_doc["_id"])
                        # If resolved team_id is in team_totals, use it
                        if resolved_team_id in team_totals:
                            player_team_id = resolved_team_id
                        else:
                            # Team not in franchise (team_totals), skip this player
                            continue
                    else:
                        # Can't resolve team, skip this player
                        continue
                except Exception:
                    # Can't resolve team, skip this player
                    continue
            else:
                # No team name or team_id, skip this player
                continue
        
        # Final check - skip if still no valid team_id
        if not player_team_id or player_team_id not in team_totals:
            continue
        
        # ✅ SS&S: Get attributes directly from franchise.players (single source of truth)
        player_attrs = player_data.get("attributes", {})
        
        # Sum all attributes for this team
        # Use anchor_ prefixed if available (post-training values), otherwise use regular attributes
        for attr in attributes:
            # Try anchor_ prefixed first (franchise-specific evolved values), then regular
            attr_value = player_attrs.get(f"anchor_{attr}", player_attrs.get(attr, 0))
            if isinstance(attr_value, (int, float)):
                team_totals[player_team_id]["attributes"][attr] += attr_value
    
    # Convert to list format for response
    result = []
    for team_id, data in team_totals.items():
        result.append({
            "team_id": team_id,
            "team_name": data["team_name"],
            "primary_color": data["primary_color"],
            "conference": data.get("conference"),
            "region": data.get("region", ""),
            "attributes": data["attributes"]
        })
    
    total_time = time.time() - start_time
    # logger.info(f"⏱️ [PERF] /franchise/team-traits COMPLETE: {total_time:.3f}s")
    return {"teams": result}


def get_team_player_stats(
    franchise_id: str,
    team_id: str,
    scope: str = "season",
    *,
    sort: str | None = "PTS",
    direction: str = "desc",
    page: int = 1,
    limit: int | None = None,
):
    """Return players for ``team_id`` within ``franchise_id``.

    Prefer FTD.players (roster list) when present; else filter franchise.players by meta.team_id.
    Results may be sorted and paginated for UI consumption.
    """

    try:
        fid = ObjectId(franchise_id)
    except Exception:
        fid = franchise_id

    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(franchise_id) if isinstance(franchise_id, str) else str(fid)}))
    franchise_players = {d["player_id"]: d for d in fpd_docs}
    team_id_str = str(team_id)
    results: list[dict] = []

    # Prefer FTD.players (roster list) when present
    try:
        team_oid = ObjectId(team_id_str) if len(team_id_str) == 24 else None
    except Exception:
        team_oid = None
    if team_oid is not None:
        ftd = franchise_team_data_collection.find_one(
            {"franchise_id": fid, "team_id": team_oid},
            {"players": 1},
        )
        if ftd and ftd.get("players"):
            for pid in ftd["players"]:
                pid_str = str(pid)
                pdata = franchise_players.get(pid_str)
                if not pdata:
                    continue
                meta = pdata.get("meta", {})
                block = pdata.get(scope, {})
                results.append(
                    {
                        "player_id": pid_str,
                        "first_name": meta.get("first_name", ""),
                        "last_name": meta.get("last_name", ""),
                        "stats": block,
                    }
                )
            if sort:
                reverse = direction.lower() != "asc"
                results.sort(key=lambda x: x["stats"].get(sort, 0), reverse=reverse)
            if limit:
                start = max(page - 1, 0) * limit
                results = results[start : start + limit]
            return results

    # Fallback: filter by meta.team_id (legacy / no FTD.players)
    for pid, pdata in franchise_players.items():
        meta = pdata.get("meta", {})
        if str(meta.get("team_id")) != team_id_str:
            continue
        block = pdata.get(scope, {})
        results.append(
            {
                "player_id": pid,
                "first_name": meta.get("first_name", ""),
                "last_name": meta.get("last_name", ""),
                "stats": block,
            }
        )

    if sort:
        reverse = direction.lower() != "asc"
        results.sort(key=lambda x: x["stats"].get(sort, 0), reverse=reverse)

    if limit:
        start = max(page - 1, 0) * limit
        results = results[start : start + limit]

    return results


@router.get("/franchise/team-player-stats/{team_id}")
def team_player_stats_endpoint(
    team_id: str,
    franchise_id: str,
    scope: str = "season",
    page: int = 1,
    limit: int | None = None,
    sort: str | None = "PTS",
    direction: str = "desc",
):
    tid = _normalize_team_id(team_id)
    players = get_team_player_stats(
        franchise_id,
        str(tid),
        scope,
        sort=sort,
        direction=direction,
        page=page,
        limit=limit,
    )
    return {"players": players}


@router.get("/franchise/team-player-stats")
def user_team_player_stats_endpoint(
    franchise_id: str,
    scope: str = "season",
    page: int = 1,
    limit: int | None = None,
    sort: str | None = "PTS",
    direction: str = "desc",
):
    # Get user team info from franchise document (with backward compatibility)
    franchise_doc = db.franchises.find_one({"_id": ObjectId(franchise_id)})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    team_name = user_team_id
    if not team_name:
        raise HTTPException(status_code=404, detail="User team not selected")
    team_doc = db.teams.find_one({"name": team_name}, {"_id": 1})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    players = get_team_player_stats(
        franchise_id,
        str(team_doc["_id"]),
        scope,
        sort=sort,
        direction=direction,
        page=page,
        limit=limit,
    )
    return {"players": players}


@router.get("/franchise/recruits")
def recruits(franchise_id: str = Query(...)):
    """Get recruits for a specific franchise. Reads from FRD (franchise_recruits_data)."""
    import time
    start_time = time.time()
    # logger.info(f"⏱️ [PERF] /franchise/recruits START - franchise_id={franchise_id}")
    db_query_start = time.time()
    # ✅ FPD/FRD: Get recruits from franchise_recruits_data (not franchise.recruits)
    rec_docs = list(franchise_recruits_data_collection.find(
        {"franchise_id": str(franchise_id)},
        {"_id": 0, "franchise_id": 0}  # Exclude _id and franchise_id for response shape
    ))
    db_query_time = time.time() - db_query_start
    # logger.info(f"⏱️ [PERF] /franchise/recruits DB query: {db_query_time:.3f}s")
    total_time = time.time() - start_time
    # logger.info(f"⏱️ [PERF] /franchise/recruits COMPLETE: {total_time:.3f}s ({len(rec_docs)} recruits)")
    return {"recruits": rec_docs}


def _recruit_rt(recruit_doc: dict) -> int:
    ratings = recruit_doc.get("position_ratings") or {}
    values = [int(v or 0) for v in ratings.values() if isinstance(v, (int, float))]
    return max(values) if values else 0


def _recruit_display_name_for_training_report(recruit_doc: dict) -> str:
    name = str(recruit_doc.get("name") or "").strip()
    if name:
        return name
    first = str(recruit_doc.get("first_name") or "").strip()
    last = str(recruit_doc.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    return full or "Recruit"


def _user_week_visit_recruit_id(
    recruiting_results: dict | None,
    week: int,
    user_team_id: str,
) -> str | None:
    """Assigned visit recruit for one team/week (same key resolution as training report)."""
    assignments = (recruiting_results or {}).get(str(week)) or {}
    if not assignments:
        return None
    team_id_str = str(user_team_id)
    recruit_id = assignments.get(team_id_str)
    if not recruit_id:
        for key, value in assignments.items():
            if str(key) == team_id_str:
                recruit_id = value
                break
    return str(recruit_id) if recruit_id else None


def _fcc_recruit_invite_payload(
    recruit_doc: dict,
    recruit_id: str,
    status: str,
) -> dict[str, Any]:
    weight = recruit_doc.get("weight")
    return {
        "recruit_id": recruit_id,
        "name": _recruit_display_name_for_training_report(recruit_doc),
        "archetype": recruit_doc.get("archetype") or "--",
        "height": format_height(recruit_doc.get("height")) or "--",
        "weight": int(weight) if isinstance(weight, (int, float)) else None,
        "year": recruit_doc.get("year") or "JH",
        "rt": _recruit_rt(recruit_doc),
        "status": status,
    }


def _fcc_current_week_invite_recruit(
    franchise_doc: dict | None,
    user_team_id: str | None,
    saved_orders: dict | None,
) -> dict[str, Any] | None:
    """
    Weekly visit recruit for FCC recruiting surfaces (weeks 20–26).

    After that week's recruiting results exist: assigned visitor from recruiting_results
    (same source as training-report.html). Before processing: top remaining saved order.
    """
    if not franchise_doc or not user_team_id:
        return None
    try:
        week = int(franchise_doc.get("week", 1) or 1)
    except (TypeError, ValueError):
        return None
    if week < 20 or week > 26:
        return None

    fid = franchise_doc.get("_id")
    if fid is None:
        return None
    fid_str = str(fid)
    team_id_str = str(user_team_id)
    recruiting_results = franchise_doc.get("recruiting_results") or {}
    week_results_exist = str(week) in recruiting_results

    if week_results_exist:
        assigned_recruit_id = _user_week_visit_recruit_id(recruiting_results, week, team_id_str)
        if not assigned_recruit_id:
            return None
        recruit_doc = franchise_recruits_data_collection.find_one(
            {"franchise_id": fid_str, "recruit_id": assigned_recruit_id},
            {"_id": 0, "franchise_id": 0},
        )
        if recruit_doc:
            return _fcc_recruit_invite_payload(recruit_doc, assigned_recruit_id, "assigned")
        return None

    order_list = _team_order_list(saved_orders)
    if not order_list:
        return None

    used_recruit_ids: set[str] = set()
    for prior_week in range(20, week):
        prior_rid = _user_week_visit_recruit_id(recruiting_results, prior_week, team_id_str)
        if prior_rid:
            used_recruit_ids.add(prior_rid)

    pending_recruit_id = _highest_remaining_team_target(order_list, used_recruit_ids)
    if not pending_recruit_id:
        return None

    recruit_doc = franchise_recruits_data_collection.find_one(
        {"franchise_id": fid_str, "recruit_id": pending_recruit_id},
        {"_id": 0, "franchise_id": 0},
    )
    if not recruit_doc:
        return None

    return _fcc_recruit_invite_payload(recruit_doc, pending_recruit_id, "pending")


def _training_report_recruiting_display(
    franchise_doc: dict | None,
    report_week: int,
    user_team_object_id: str,
) -> dict[str, str | None] | None:
    """
    Copy for training-report.html recruiting column: visit weeks 20–26 vs lean weeks 1–19 / 27–34.
    Returns dict with keys header, meta_line (strings; meta_line may be empty) or None when out of scope.
    """
    if not franchise_doc or not user_team_object_id:
        return None
    try:
        w = int(report_week)
    except (TypeError, ValueError):
        return None
    fid = franchise_doc.get("_id")
    if fid is None:
        return None
    fid_str = str(fid)
    tid_str = str(user_team_object_id)

    if 20 <= w <= 26:
        rid = _user_week_visit_recruit_id(franchise_doc.get("recruiting_results"), w, tid_str)
        if not rid:
            return {"header": "Recruiting Visit", "meta_line": None}
        recruit = franchise_recruits_data_collection.find_one(
            {"franchise_id": fid_str, "recruit_id": rid},
            {"name": 1, "first_name": 1, "last_name": 1, "position_ratings": 1, "recruit_id": 1},
        )
        if not recruit:
            return {"header": "Recruiting Visit", "meta_line": None}
        nm = _recruit_display_name_for_training_report(recruit)
        rt = _recruit_rt(recruit)
        return {"header": "Recruiting Visit", "meta_line": f"{nm} - RT: {rt}"}

    if (1 <= w <= 19) or (27 <= w <= 34):
        lean_or = []
        for slot in ("1", "2", "3"):
            lean_or.append({f"Lean.{slot}": tid_str})
            try:
                lean_or.append({f"Lean.{slot}": ObjectId(tid_str)})
            except Exception:
                pass
        recruits = list(
            franchise_recruits_data_collection.find(
                {"franchise_id": fid_str, "$or": lean_or},
                {"name": 1, "first_name": 1, "last_name": 1, "position_ratings": 1, "recruit_id": 1},
            )
        )
        recruits.sort(key=lambda r: (-_recruit_rt(r), str(r.get("recruit_id") or "")))
        header = "Recruits Leaning Your Way"
        if not recruits:
            return {"header": header, "meta_line": ""}
        top = recruits[:3]
        parts = [f"{_recruit_display_name_for_training_report(r)} - RT: {_recruit_rt(r)}" for r in top]
        line = ", ".join(parts)
        if len(recruits) > 3:
            line += " ..."
        return {"header": header, "meta_line": line}

    return None


def _best_position(position_ratings: dict) -> dict:
    best_pos = "--"
    best_rating = None
    for pos, rating in (position_ratings or {}).items():
        if not isinstance(rating, (int, float)):
            continue
        if best_rating is None or rating > best_rating:
            best_pos = pos
            best_rating = int(rating)
    return {"pos": best_pos, "rating": best_rating}


def _team_order_list(order_doc: dict | None) -> list[str]:
    return [
        order_doc[key]
        for key in sorted((order_doc or {}).keys(), key=lambda item: int(item))
        if order_doc.get(key)
    ]


def _sort_recruits_by_rt(recruit_docs: list[dict]) -> list[dict]:
    rows = list(recruit_docs)
    rows.sort(key=lambda recruit: (-_recruit_rt(recruit), random.random()))
    return rows


def _generate_cpu_recruiting_orders(
    team_docs_by_id: dict[str, dict],
    user_team_id: str,
    recruits_by_region: dict[str, list[dict]],
) -> dict[str, dict[str, str]]:
    cpu_orders: dict[str, dict[str, str]] = {}
    all_regions = [region for region, recruits in recruits_by_region.items() if recruits]
    recruit_docs_by_id = {
        recruit["recruit_id"]: recruit
        for recruits in recruits_by_region.values()
        for recruit in recruits
    }

    for team_id, team_doc in team_docs_by_id.items():
        if team_id == user_team_id:
            continue

        team_region = str(team_doc.get("region") or "").upper()
        in_region_recruits = list(recruits_by_region.get(team_region, []))
        if not in_region_recruits:
            cpu_orders[team_id] = {}
            continue

        selected_ids: list[str] = []
        out_of_region_count = random.randint(0, 5)
        outside_regions = [region for region in all_regions if region != team_region]
        for _ in range(out_of_region_count):
            if not outside_regions:
                break
            outside_region = random.choice(outside_regions)
            outside_pool = recruits_by_region.get(outside_region, [])[:15]
            available_outside_pool = [
                recruit["recruit_id"]
                for recruit in outside_pool
                if recruit["recruit_id"] not in selected_ids
            ]
            if available_outside_pool:
                selected_ids.append(random.choice(available_outside_pool))

        desired_in_region = MAX_RECRUITING_ORDER_SLOTS - len(selected_ids)
        top_sixteen_pool = in_region_recruits[: min(16, len(in_region_recruits))]
        top_pick_count = min(10, len(top_sixteen_pool), desired_in_region)
        if top_pick_count > 0:
            selected_ids.extend([recruit["recruit_id"] for recruit in random.sample(top_sixteen_pool, top_pick_count)])

        remaining_needed = desired_in_region - top_pick_count
        remaining_pool = [
            recruit["recruit_id"]
            for recruit in in_region_recruits
            if recruit["recruit_id"] not in selected_ids
        ]
        if remaining_needed > 0 and remaining_pool:
            selected_ids.extend(random.sample(remaining_pool, min(remaining_needed, len(remaining_pool))))

        sorted_selected_ids = [
            recruit["recruit_id"]
            for recruit in _sort_recruits_by_rt([
                recruit_docs_by_id[recruit_id]
                for recruit_id in selected_ids[:MAX_RECRUITING_ORDER_SLOTS]
                if recruit_id in recruit_docs_by_id
            ])
        ]
        cpu_orders[team_id] = _normalize_recruiting_orders(sorted_selected_ids)

    return cpu_orders


def _highest_remaining_team_target(team_order: list[str], assigned_recruit_ids: set[str]) -> str | None:
    for recruit_id in team_order:
        if recruit_id not in assigned_recruit_ids:
            return recruit_id
    return None


def _team_prestige_draw_entries(team_doc: dict | None) -> int:
    prestige = int((team_doc or {}).get("prestige") or 0)
    return max(1, prestige // 10)


def _select_team_by_prestige_draw(team_ids: list[str], team_docs_by_id: dict[str, dict]) -> str:
    weighted_ranges: list[tuple[int, int, str]] = []
    current_start = 1
    for team_id in team_ids:
        entries = _team_prestige_draw_entries(team_docs_by_id.get(team_id))
        current_end = current_start + entries - 1
        weighted_ranges.append((current_start, current_end, team_id))
        current_start = current_end + 1

    draw = random.randint(1, weighted_ranges[-1][1])
    for range_start, range_end, team_id in weighted_ranges:
        if range_start <= draw <= range_end:
            return team_id
    return weighted_ranges[-1][2]


def _team_outcomes_by_week_results(results: list[dict]) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for result in results:
        away_id = str(result.get("away_id"))
        home_id = str(result.get("home_id"))
        away_score = int(result.get("away_score", 0) or 0)
        home_score = int(result.get("home_score", 0) or 0)
        if away_score > home_score:
            outcomes[away_id] = "win"
            outcomes[home_id] = "loss"
        elif home_score > away_score:
            outcomes[home_id] = "win"
            outcomes[away_id] = "loss"
    return outcomes


def _normalize_recruit_lean_doc(lean_doc: dict | None) -> dict[str, str | None]:
    lean = {"1": None, "2": None, "3": None}
    for key in ("1", "2", "3"):
        value = (lean_doc or {}).get(key)
        lean[key] = value if value not in ("",) else None
    return lean


def _team_on_recruit_lean(lean_doc: dict | None, team_id: str) -> bool:
    normalized = _normalize_recruit_lean_doc(lean_doc)
    team_id_str = str(team_id)
    return any(str(normalized.get(rank) or "") == team_id_str for rank in ("1", "2", "3"))


def _team_was_newly_added_to_lean(
    prior_lean: dict | None,
    updated_lean: dict | None,
    team_id: str,
) -> bool:
    """True when team_id was not on the lean list before but is after (not rank moves)."""
    return _team_on_recruit_lean(updated_lean, team_id) and not _team_on_recruit_lean(prior_lean, team_id)


def _clear_fcc_pending_new_lean_recruits(franchise_doc: dict, franchise_id: ObjectId) -> None:
    if not franchise_doc.get(FCC_PENDING_NEW_LEAN_RECRUITS_FIELD):
        return
    franchise_doc[FCC_PENDING_NEW_LEAN_RECRUITS_FIELD] = []
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {FCC_PENDING_NEW_LEAN_RECRUITS_FIELD: []}},
    )


def _append_fcc_pending_new_lean_recruits(
    franchise_doc: dict,
    franchise_id: ObjectId,
    recruit_ids: list[str],
    user_team_id: str,
) -> None:
    _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_object_id or str(user_team_object_id) != str(user_team_id):
        return
    unique_new = [str(rid) for rid in recruit_ids if rid]
    if not unique_new:
        return
    existing = [str(rid) for rid in (franchise_doc.get(FCC_PENDING_NEW_LEAN_RECRUITS_FIELD) or [])]
    merged = existing[:]
    for rid in unique_new:
        if rid not in merged:
            merged.append(rid)
    franchise_doc[FCC_PENDING_NEW_LEAN_RECRUITS_FIELD] = merged
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {FCC_PENDING_NEW_LEAN_RECRUITS_FIELD: merged}},
    )


def _lean_has_open_slot(lean_doc: dict[str, str | None]) -> bool:
    return lean_doc.get("1") in (None, "open") or lean_doc.get("2") is None or lean_doc.get("3") is None


def _insert_team_into_highest_open_lean_slot(lean_doc: dict[str, str | None], team_id: str) -> dict[str, str | None]:
    updated = _normalize_recruit_lean_doc(lean_doc)
    if updated.get("1") in (None, "open"):
        updated["1"] = team_id
        updated["2"] = None if updated.get("2") == "open" else updated.get("2")
        updated["3"] = None if updated.get("3") == "open" else updated.get("3")
        return updated
    if updated.get("2") is None:
        updated["2"] = team_id
        return updated
    if updated.get("3") is None:
        updated["3"] = team_id
        return updated
    return updated


def _apply_team_to_recruit_performance_lean(lean_doc: dict | None, team_id: str) -> dict[str, str | None]:
    """Weeks 1–19 & 27–34 complete-week rules: add/move team on recruit lean (Recruiting_System.md)."""
    updated = _normalize_recruit_lean_doc(lean_doc)
    existing_rank = next((rank for rank in ("1", "2", "3") if updated.get(rank) == team_id), None)
    if existing_rank == "1":
        if updated.get("3") is not None:
            updated["3"] = None
        elif updated.get("2") is not None:
            updated["2"] = None
        return updated
    if existing_rank == "2":
        updated["2"], updated["1"] = updated.get("1"), updated.get("2")
        return updated
    if existing_rank == "3":
        updated["3"], updated["2"] = updated.get("2"), updated.get("3")
        return updated
    if _lean_has_open_slot(updated):
        return _insert_team_into_highest_open_lean_slot(updated, team_id)
    updated["3"] = team_id
    return updated


def _game_performance_lean_chances_for_week(week: int) -> dict[str, tuple[float, float]] | None:
    """Returns win and quality_loss (low_rt, high_rt) probability pairs; None if not a performance-lean week."""
    if 1 <= week <= 10:
        return {"win": (0.50, 0.25), "quality_loss": (0.40, 0.20)}
    if 11 <= week <= 15:
        return {"win": (0.60, 0.40), "quality_loss": (0.40, 0.25)}
    if 16 <= week <= 19:
        return {"win": (0.80, 0.60), "quality_loss": (0.50, 0.30)}
    if 27 <= week <= 34:
        return {"win": (0.90, 0.75), "quality_loss": (0.60, 0.50)}
    return None


def _apply_performance_based_recruiting_lean_updates(
    franchise_doc: dict,
    week: int,
    results: list[dict],
) -> list[dict[str, str]]:
    """Applies the week's performance-based lean rolls. Returns the week's new-lean
    events ([{recruit_id, team_id}, ...] where the team was newly added to a recruit's
    lean list) for downstream consumers like the weekly news."""
    chances = _game_performance_lean_chances_for_week(week)
    if chances is None:
        return []

    fid = franchise_doc["_id"]
    applied_map = franchise_doc.get("recruiting_performance_lean_applied") or {}
    if applied_map.get(str(week)):
        logger.info(
            "Skipping performance recruiting lean updates for franchise=%s week=%s; already applied",
            franchise_doc.get("_id"),
            week,
        )
        return []

    ftd_docs = list(
        franchise_team_data_collection.find(
            {"franchise_id": fid},
            {"team_id": 1, "natl_rank": 1},
        )
    )
    natl_by_team_id = {
        str(d["team_id"]): int(d.get("natl_rank", 999) or 999)
        for d in ftd_docs
        if d.get("team_id") is not None
    }
    if not natl_by_team_id:
        db.franchises.update_one(
            {"_id": fid},
            {"$set": {f"recruiting_performance_lean_applied.{week}": True}},
        )
        franchise_doc.setdefault("recruiting_performance_lean_applied", {})
        franchise_doc["recruiting_performance_lean_applied"][str(week)] = True
        return []

    team_oid_list = [ObjectId(tid) for tid in natl_by_team_id]
    team_region_by_id: dict[str, str] = {}
    for team in db.teams.find({"_id": {"$in": team_oid_list}}, {"region": 1}):
        team_region_by_id[str(team["_id"])] = str(team.get("region") or "").upper()

    recruits = list(
        franchise_recruits_data_collection.find(
            {"franchise_id": str(fid)},
            {"_id": 0, "franchise_id": 0},
        )
    )
    recruit_by_id = {r["recruit_id"]: r for r in recruits}
    _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    user_team_id_str = str(user_team_object_id) if user_team_object_id else ""
    newly_added_for_user: list[str] = []
    new_lean_events: list[dict[str, str]] = []

    played: set[str] = set()
    game_by_team: dict[str, dict] = {}
    for row in results:
        away_id = str(row.get("away_id") or "")
        home_id = str(row.get("home_id") or "")
        if not away_id or not home_id:
            continue
        played.add(away_id)
        played.add(home_id)
        game_by_team[away_id] = row
        game_by_team[home_id] = row

    def _maybe_roll(team_id: str, probability: float, rt_low: bool) -> None:
        if probability <= 0 or random.random() > probability:
            return
        region = team_region_by_id.get(team_id) or ""
        if len(region) != 1:
            return

        def pool_pred(doc: dict) -> bool:
            if str(doc.get("Home Region") or "").upper() != region:
                return False
            rt = _recruit_rt(doc)
            return rt < 30 if rt_low else rt >= 30

        pool = [r for r in recruits if pool_pred(r)]
        if not pool:
            return
        chosen = random.choice(pool)
        rid = chosen["recruit_id"]
        doc = recruit_by_id.get(rid)
        if not doc:
            return
        old_lean = doc.get("Lean")
        new_lean = _apply_team_to_recruit_performance_lean(old_lean, team_id)
        if _team_was_newly_added_to_lean(old_lean, new_lean, team_id):
            new_lean_events.append({"recruit_id": rid, "team_id": team_id})
            if user_team_id_str and team_id == user_team_id_str:
                newly_added_for_user.append(rid)
        doc["Lean"] = new_lean
        franchise_recruits_data_collection.update_one(
            {"franchise_id": str(fid), "recruit_id": rid},
            {"$set": {"Lean": new_lean}},
        )

    win_chances = chances["win"]
    loss_chances = chances["quality_loss"]

    for team_id in played:
        row = game_by_team.get(team_id)
        if not row:
            continue
        away_id = str(row.get("away_id") or "")
        home_id = str(row.get("home_id") or "")
        away_score = int(row.get("away_score", 0) or 0)
        home_score = int(row.get("home_score", 0) or 0)

        if away_score == home_score:
            continue

        if team_id == away_id:
            my_score, opp_score = away_score, home_score
            opponent_id = home_id
        elif team_id == home_id:
            my_score, opp_score = home_score, away_score
            opponent_id = away_id
        else:
            continue

        won = my_score > opp_score
        if won:
            _maybe_roll(team_id, win_chances[0], rt_low=True)
            _maybe_roll(team_id, win_chances[1], rt_low=False)
            continue

        opp_rank = natl_by_team_id.get(opponent_id, 999)
        my_rank = natl_by_team_id.get(team_id, 999)
        loss_margin = opp_score - my_score
        quality = opp_rank < my_rank and loss_margin <= 8
        if not quality:
            continue
        _maybe_roll(team_id, loss_chances[0], rt_low=True)
        _maybe_roll(team_id, loss_chances[1], rt_low=False)

    _append_fcc_pending_new_lean_recruits(
        franchise_doc,
        fid,
        newly_added_for_user,
        user_team_id_str,
    )
    db.franchises.update_one(
        {"_id": fid},
        {"$set": {f"recruiting_performance_lean_applied.{week}": True}},
    )
    franchise_doc.setdefault("recruiting_performance_lean_applied", {})
    franchise_doc["recruiting_performance_lean_applied"][str(week)] = True
    return new_lean_events


def _update_recruit_lean_after_visit(
    lean_doc: dict | None,
    team_id: str,
    in_region: bool,
    won_game: bool,
) -> dict[str, str | None]:
    updated = _normalize_recruit_lean_doc(lean_doc)
    existing_rank = next((rank for rank in ("1", "2", "3") if updated.get(rank) == team_id), None)
    if existing_rank == "1":
        if updated.get("3") is not None:
            updated["3"] = None
        elif updated.get("2") is not None:
            updated["2"] = None
        return updated
    if existing_rank == "2":
        updated["2"], updated["1"] = updated.get("1"), updated.get("2")
        return updated
    if existing_rank == "3":
        updated["3"], updated["2"] = updated.get("2"), updated.get("3")
        return updated
    has_open_slot = _lean_has_open_slot(updated)
    if in_region:
        chance = 0.95 if won_game and has_open_slot else 0.75 if won_game else 0.75 if has_open_slot else 0.40
    else:
        chance = 0.80 if won_game and has_open_slot else 0.60 if won_game else 0.50 if has_open_slot else 0.30

    if random.random() > chance:
        return updated

    if has_open_slot:
        return _insert_team_into_highest_open_lean_slot(updated, team_id)

    updated["3"] = team_id
    return updated


def _apply_complete_week_recruiting_lean_updates(
    franchise_doc: dict,
    week: int,
    results: list[dict],
) -> list[dict[str, str]]:
    """Applies the week's visit-based lean updates (weeks 20-26). Returns the week's
    new-lean events ([{recruit_id, team_id}, ...] where the team was newly added to a
    recruit's lean list) for downstream consumers like the weekly news."""
    applied = (franchise_doc.get("recruiting_lean_updates_applied") or {}).get(str(week))
    if applied:
        logger.info("Skipping recruiting lean updates for franchise=%s week=%s; already applied", franchise_doc.get("_id"), week)
        return []
    if week < 20 or week > 26:
        return []

    fid = franchise_doc["_id"]
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": fid},
        {"team_id": 1, "recruit_visit": 1},
    ))
    if not ftd_docs:
        db.franchises.update_one({"_id": fid}, {"$set": {f"recruiting_lean_updates_applied.{week}": True}})
        return []

    visited_recruit_ids: set[str] = set()
    team_ids = [doc["team_id"] for doc in ftd_docs if doc.get("team_id") is not None]
    team_docs_by_id = {
        str(team["_id"]): team
        for team in db.teams.find({"_id": {"$in": team_ids}}, {"region": 1})
    }
    recruit_visit_pairs: list[tuple[str, str]] = []
    for ftd_doc in ftd_docs:
        team_id = str(ftd_doc.get("team_id"))
        recruit_id = ftd_doc.get("recruit_visit")
        if not team_id or not recruit_id:
            continue
        if recruit_id in visited_recruit_ids:
            logger.warning(
                "Duplicate recruit_visit detected for franchise=%s week=%s recruit_id=%s; keeping first occurrence",
                fid,
                week,
                recruit_id,
            )
            continue
        visited_recruit_ids.add(recruit_id)
        recruit_visit_pairs.append((team_id, recruit_id))

    if not recruit_visit_pairs:
        db.franchises.update_one({"_id": fid}, {"$set": {f"recruiting_lean_updates_applied.{week}": True}})
        return []

    recruit_ids = [recruit_id for _, recruit_id in recruit_visit_pairs]
    recruit_docs_by_id = {
        recruit["recruit_id"]: recruit
        for recruit in franchise_recruits_data_collection.find(
            {"franchise_id": str(fid), "recruit_id": {"$in": recruit_ids}},
            {"recruit_id": 1, "Home Region": 1, "Lean": 1},
        )
    }
    team_outcomes = _team_outcomes_by_week_results(results)
    _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    user_team_id_str = str(user_team_object_id) if user_team_object_id else ""
    newly_added_for_user: list[str] = []
    new_lean_events: list[dict[str, str]] = []

    bulk_updates = []
    for team_id, recruit_id in recruit_visit_pairs:
        recruit_doc = recruit_docs_by_id.get(recruit_id)
        team_doc = team_docs_by_id.get(team_id)
        if not recruit_doc or not team_doc:
            continue
        old_lean = recruit_doc.get("Lean")
        updated_lean = _update_recruit_lean_after_visit(
            old_lean,
            team_id,
            str(team_doc.get("region") or "").upper() == str(recruit_doc.get("Home Region") or "").upper(),
            team_outcomes.get(team_id) == "win",
        )
        if _team_was_newly_added_to_lean(old_lean, updated_lean, team_id):
            new_lean_events.append({"recruit_id": recruit_id, "team_id": team_id})
            if user_team_id_str and team_id == user_team_id_str:
                newly_added_for_user.append(recruit_id)
        bulk_updates.append({
            "filter": {"franchise_id": str(fid), "recruit_id": recruit_id},
            "update": {"$set": {"Lean": updated_lean}},
        })

    for op in bulk_updates:
        franchise_recruits_data_collection.update_one(op["filter"], op["update"])

    _append_fcc_pending_new_lean_recruits(
        franchise_doc,
        fid,
        newly_added_for_user,
        user_team_id_str,
    )

    franchise_team_data_collection.update_many(
        {"franchise_id": fid},
        {"$set": {"recruit_visit": None, "updated_at": datetime.utcnow()}},
    )
    db.franchises.update_one(
        {"_id": fid},
        {"$set": {f"recruiting_lean_updates_applied.{week}": True}},
    )
    return new_lean_events


def _resolve_weekly_recruiting_visits(
    team_docs_by_id: dict[str, dict],
    team_orders: dict[str, list[str]],
    recruit_docs_by_id: dict[str, dict],
) -> dict[str, str]:
    team_rank_lookup = {
        team_id: {recruit_id: index + 1 for index, recruit_id in enumerate(order)}
        for team_id, order in team_orders.items()
    }
    available_team_ids = set(team_docs_by_id.keys())
    assigned_recruit_ids: set[str] = set()
    assignments: dict[str, str] = {}
    shuffled_regions = list("ABCDEFGH")
    random.shuffle(shuffled_regions)

    for region in shuffled_regions:
        region_team_ids = [
            team_id
            for team_id, team_doc in team_docs_by_id.items()
            if str(team_doc.get("region") or "").upper() == region and team_id in available_team_ids
        ]
        if not region_team_ids:
            continue

        region_bid_recruit_ids = set()
        for team_id in region_team_ids:
            for recruit_id in team_orders.get(team_id, []):
                if recruit_id not in assigned_recruit_ids:
                    region_bid_recruit_ids.add(recruit_id)

        sorted_region_recruits = _sort_recruits_by_rt([
            recruit_docs_by_id[recruit_id]
            for recruit_id in region_bid_recruit_ids
            if recruit_id in recruit_docs_by_id
        ])

        for recruit_doc in sorted_region_recruits:
            recruit_id = recruit_doc["recruit_id"]
            if recruit_id in assigned_recruit_ids:
                continue

            while True:
                candidate_team_ids = [
                    team_id
                    for team_id in region_team_ids
                    if team_id in available_team_ids and recruit_id in team_rank_lookup.get(team_id, {})
                ]
                if not candidate_team_ids:
                    break

                best_rank = min(team_rank_lookup[team_id][recruit_id] for team_id in candidate_team_ids)
                eligible_team_ids = [
                    team_id
                    for team_id in candidate_team_ids
                    if team_rank_lookup[team_id][recruit_id] == best_rank
                ]

                lean_doc = recruit_doc.get("Lean") or {}
                if lean_doc.get("1") != "open":
                    lean_team_ids = {team_id for team_id in lean_doc.values() if team_id}
                    if lean_team_ids:
                        overlap = [team_id for team_id in eligible_team_ids if team_id in lean_team_ids]
                        if overlap:
                            eligible_team_ids = overlap

                if not eligible_team_ids:
                    break

                selected_team_id = _select_team_by_prestige_draw(eligible_team_ids, team_docs_by_id)
                top_remaining_recruit_id = _highest_remaining_team_target(
                    team_orders.get(selected_team_id, []),
                    assigned_recruit_ids,
                )
                if not top_remaining_recruit_id:
                    available_team_ids.discard(selected_team_id)
                    break

                if top_remaining_recruit_id != recruit_id:
                    assignments[selected_team_id] = top_remaining_recruit_id
                    assigned_recruit_ids.add(top_remaining_recruit_id)
                    available_team_ids.discard(selected_team_id)
                    continue

                assignments[selected_team_id] = recruit_id
                assigned_recruit_ids.add(recruit_id)
                available_team_ids.discard(selected_team_id)
                break

        fallback_team_ids = [
            team_id
            for team_id in region_team_ids
            if team_id in available_team_ids
        ]
        if fallback_team_ids:
            fallback_recruits = _sort_recruits_by_rt([
                recruit
                for recruit in recruit_docs_by_id.values()
                if str(recruit.get("Home Region") or "").upper() == region
                and recruit.get("recruit_id") not in assigned_recruit_ids
            ])
            for team_id, recruit_doc in zip(fallback_team_ids, fallback_recruits):
                recruit_id = recruit_doc["recruit_id"]
                assignments[team_id] = recruit_id
                assigned_recruit_ids.add(recruit_id)
                available_team_ids.discard(team_id)

    return assignments


def _region_display_order(user_region: str | None) -> list[str]:
    ordered = list("ABCDEFGH")
    user_region = str(user_region or "").upper()
    if user_region in ordered:
        ordered.remove(user_region)
        ordered.insert(0, user_region)
    return ordered


def _build_recruiting_results_payload(franchise_doc: dict, week: int) -> dict:
    fid = franchise_doc["_id"]
    week_key = str(week)
    recruiting_results = franchise_doc.get("recruiting_results", {}) or {}
    week_results = recruiting_results.get(week_key)
    if week_results is None:
        raise HTTPException(status_code=404, detail="Recruiting results not found for this week")

    user_team_name, user_team_id = get_user_team_from_franchise(franchise_doc)
    user_region = ""
    if user_team_id:
        try:
            team_doc = db.teams.find_one({"_id": ObjectId(user_team_id)}, {"region": 1})
            user_region = str(team_doc.get("region") or "").upper() if team_doc else ""
        except Exception:
            user_region = ""

    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": fid}, {"team_id": 1}))
    team_ids = [doc["team_id"] for doc in ftd_docs if doc.get("team_id") is not None]
    teams_by_id = {
        str(team["_id"]): team
        for team in db.teams.find(
            {"_id": {"$in": team_ids}},
            {"name": 1, "conference": 1, "region": 1},
        )
    }
    recruit_ids = [recruit_id for recruit_id in week_results.values() if recruit_id]
    recruit_docs_by_id = {
        recruit["recruit_id"]: recruit
        for recruit in franchise_recruits_data_collection.find(
            {"franchise_id": str(franchise_doc["_id"]), "recruit_id": {"$in": recruit_ids}},
            {"_id": 0, "franchise_id": 0},
        )
    }

    regions_payload = []
    for region in _region_display_order(user_region):
        region_teams = [
            {
                "team_id": team_id,
                "team_name": team_doc.get("name", team_id),
                "conference": team_doc.get("conference"),
                "region": str(team_doc.get("region") or "").upper(),
            }
            for team_id, team_doc in teams_by_id.items()
            if str(team_doc.get("region") or "").upper() == region
        ]
        if not region_teams:
            continue

        conferences_payload = []
        for conference in sorted({team["conference"] for team in region_teams if team.get("conference") is not None}):
            conference_teams = [team for team in region_teams if team.get("conference") == conference]
            conference_teams.sort(key=lambda team: team["team_name"])
            team_rows = []
            for team in conference_teams:
                recruit_id = week_results.get(team["team_id"])
                recruit_doc = recruit_docs_by_id.get(recruit_id) if recruit_id else None
                recruit_payload = None
                if recruit_doc:
                    best_pos = _best_position(recruit_doc.get("position_ratings") or {})
                    recruit_payload = {
                        "recruit_id": recruit_doc["recruit_id"],
                        "name": recruit_doc.get("name", "--"),
                        "home_region": recruit_doc.get("Home Region", "--"),
                        "archetype": recruit_doc.get("archetype", "--"),
                        "height": recruit_doc.get("height"),
                        "weight": recruit_doc.get("weight"),
                        "pos": best_pos.get("pos", "--"),
                        "year": recruit_doc.get("year") or "JH",
                        "rt": best_pos.get("rating"),
                    }
                team_rows.append({
                    "team_id": team["team_id"],
                    "team_name": team["team_name"],
                    "visit": recruit_payload,
                })
            conferences_payload.append({
                "conference": conference,
                "teams": team_rows,
            })
        regions_payload.append({
            "region": region,
            "conferences": conferences_payload,
        })

    return {
        "week": week,
        "user_team": user_team_name,
        "user_team_id": user_team_id,
        "regions": regions_payload,
    }


def _process_weekly_recruiting_invites(franchise_doc: dict[str, Any]) -> dict[str, Any]:
    fid = franchise_doc["_id"]
    week = int(franchise_doc.get("week", 1) or 1)
    if week < 20 or week > 26:
        raise HTTPException(status_code=400, detail="Weekly recruiting invites are only processed during weeks 20-26")
    if str(week) in (franchise_doc.get("recruiting_results", {}) or {}):
        return (franchise_doc.get("recruiting_results", {}) or {}).get(str(week)) or {}

    _, user_team_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id:
        raise HTTPException(status_code=404, detail="User team not selected")
    user_team_id_str = str(user_team_id)

    if week == 20:
        user_ftd = franchise_team_data_collection.find_one(
            {"franchise_id": fid, "team_id": ObjectId(user_team_id_str)},
            {"Recruits": 1},
        ) or {}
        if not _team_order_list(user_ftd.get("Recruits")):
            raise HTTPException(status_code=400, detail="You must save recruiting orders before running training in week 20")

    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": fid}, {"team_id": 1, "Recruits": 1}))
    team_ids = [doc["team_id"] for doc in ftd_docs if doc.get("team_id") is not None]
    ftd_by_team_id = {str(doc["team_id"]): doc for doc in ftd_docs if doc.get("team_id") is not None}
    team_docs_by_id = {}
    for team in db.teams.find(
        {"_id": {"$in": team_ids}},
        {"name": 1, "conference": 1, "region": 1},
    ):
        team_id = str(team["_id"])
        team_docs_by_id[team_id] = {
            **team,
            "prestige": (ftd_by_team_id.get(team_id) or {}).get("prestige", 0),
        }
    recruits = list(
        franchise_recruits_data_collection.find(
            {"franchise_id": str(franchise_doc["_id"])},
            {"_id": 0, "franchise_id": 0},
        )
    )
    recruit_docs_by_id = {recruit["recruit_id"]: recruit for recruit in recruits}
    recruits_by_region = {}
    for region in "ABCDEFGH":
        region_recruits = [recruit for recruit in recruits if str(recruit.get("Home Region") or "").upper() == region]
        recruits_by_region[region] = _sort_recruits_by_rt(region_recruits)

    cpu_orders = _generate_cpu_recruiting_orders(team_docs_by_id, user_team_id_str, recruits_by_region)
    for team_id, cpu_order in cpu_orders.items():
        franchise_team_data_collection.update_one(
            {"franchise_id": fid, "team_id": ObjectId(team_id)},
            {"$set": {"Recruits": cpu_order, "updated_at": datetime.utcnow()}},
        )

    all_ftd_docs = list(franchise_team_data_collection.find({"franchise_id": fid}, {"team_id": 1, "Recruits": 1}))
    team_orders = {
        str(doc["team_id"]): _team_order_list(doc.get("Recruits"))
        for doc in all_ftd_docs
    }
    assignments = _resolve_weekly_recruiting_visits(team_docs_by_id, team_orders, recruit_docs_by_id)

    db.franchises.update_one(
        {"_id": fid},
        {
            "$set": {
                f"recruiting_results.{week}": assignments,
            }
        },
    )
    for ftd_doc in all_ftd_docs:
        team_id = str(ftd_doc["team_id"])
        franchise_team_data_collection.update_one(
            {"franchise_id": fid, "team_id": ftd_doc["team_id"]},
            {
                "$set": {
                    "recruit_visit": assignments.get(team_id),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    return assignments


def _normalize_recruiting_orders(recruit_ids: list[str]) -> dict[str, str]:
    return {str(index): recruit_id for index, recruit_id in enumerate(recruit_ids, start=1)}


def _normalize_week_35_recruiting_orders(order_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(order_entries, start=1):
        recruit_id = str((entry or {}).get("id") or "").strip()
        if not recruit_id:
            continue
        try:
            points = int((entry or {}).get("points", 0) or 0)
        except Exception:
            points = 0
        normalized[str(index)] = {
            "id": recruit_id,
            "points": max(0, points),
            "scholarship": bool((entry or {}).get("scholarship", False)),
            "playing_time": bool((entry or {}).get("playing_time", False)),
        }
    return normalized


def _week_35_order_entries(saved_orders: Any) -> list[dict[str, Any]]:
    if not isinstance(saved_orders, dict):
        return []
    entries: list[dict[str, Any]] = []
    for key in sorted(saved_orders.keys(), key=lambda value: int(value) if str(value).isdigit() else 10**9):
        entry = saved_orders.get(key)
        if not isinstance(entry, dict):
            continue
        recruit_id = str(entry.get("id") or "").strip()
        if not recruit_id:
            continue
        entries.append(
            {
                "id": recruit_id,
                "points": _safe_int(entry.get("points", 0) or 0, 0),
                "scholarship": bool(entry.get("scholarship", False)),
                "playing_time": bool(entry.get("playing_time", False)),
            }
        )
    return entries


def _normalize_week_36_recruiting_orders(order_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return _normalize_week_35_recruiting_orders(order_entries)


def _week_36_order_entries(saved_orders: Any) -> list[dict[str, Any]]:
    return _week_35_order_entries(saved_orders)


def _zero_stats_block() -> dict[str, Any]:
    zero_stats = {key: 0 for key in BOX_SCORE_KEYS}
    zero_stats["Outlet_Score_List"] = []
    return zero_stats


def _normalize_new_franchise_player_attributes(raw_attributes: dict[str, Any] | None) -> dict[str, Any]:
    """
    Convert recruit-style attributes into the full franchise-player shape.
    New freshmen need anchor baselines plus CH/EM/MO/NG before week 1 training.
    """
    attrs = (raw_attributes or {}).copy()
    core_attrs = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]

    for attr in core_attrs:
        base_val = int(attrs.get(attr, 0) or 0)
        attrs[attr] = base_val
        attrs[f"anchor_{attr}"] = base_val

    return Player.randomize_game_attributes(attrs, preserve_character=True)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _best_position(position_ratings: dict[str, Any]) -> dict[str, Any]:
    best_pos = "--"
    best_rating = None
    for pos, value in (position_ratings or {}).items():
        try:
            rating = int(value)
        except Exception:
            continue
        if best_rating is None or rating > best_rating:
            best_pos = pos
            best_rating = rating
    return {"pos": best_pos, "rating": best_rating}


def _format_team_name_map(team_ids: list[ObjectId] | None = None) -> dict[str, str]:
    query: dict[str, Any] = {}
    if team_ids:
        query = {"_id": {"$in": team_ids}}
    return {
        str(team["_id"]): team.get("name", str(team["_id"]))
        for team in db.teams.find(query, {"name": 1})
    }


def _load_fpd_map(franchise_id: str | ObjectId, player_ids: list[str] | None = None) -> dict[str, dict[str, Any]]:
    franchise_id_str = str(franchise_id)
    query: dict[str, Any] = {"franchise_id": franchise_id_str}
    if player_ids is not None:
        query["player_id"] = {"$in": [str(player_id) for player_id in player_ids]}
    try:
        return {
            doc["player_id"]: doc
            for doc in franchise_players_data_collection.find(query)
            if doc.get("player_id")
        }
    except Exception:
        return {}


def _player_year_from_fpd_or_core(player_id: str, fpd_doc: dict[str, Any] | None) -> str:
    meta = (fpd_doc or {}).get("meta", {})
    year = meta.get("year")
    if year:
        return str(year)
    core_doc = db.players.find_one({"_id": player_id}, {"year": 1}) or {}
    return str(core_doc.get("year") or "")


def _is_graduating_year(year_value: str | None) -> bool:
    year = str(year_value or "").strip().lower()
    return year in {"senior", "graduate"}


def _calculate_available_roster_spots(fid: ObjectId, user_team_id: str) -> int:
    try:
        team_object_id = ObjectId(user_team_id)
    except Exception:
        return 0

    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {"players": 1, "training_squad_players": 1},
    ) or {}
    # Active + training-squad players both occupy roster slots next season (TS
    # rejoins the pool), so both count against the 15-man cap.
    roster_player_ids = (
        [str(player_id) for player_id in (ftd_doc.get("players") or []) if player_id]
        + [str(player_id) for player_id in (ftd_doc.get("training_squad_players") or []) if player_id]
    )
    if not roster_player_ids:
        return 15

    fpd_docs = _load_fpd_map(fid, roster_player_ids)
    if not fpd_docs:
        non_graduating_count = db.players.count_documents(
            {
                "_id": {"$in": roster_player_ids},
                "year": {"$nin": ["Senior", "senior", "Graduate", "graduate"]},
            }
        )
        return max(0, 15 - int(non_graduating_count))
    non_graduating_count = 0
    for player_id in roster_player_ids:
        if not _is_graduating_year(_player_year_from_fpd_or_core(player_id, fpd_docs.get(player_id))):
            non_graduating_count += 1
    return max(0, 15 - int(non_graduating_count))


def _calculate_available_scholarships(fid: ObjectId, user_team_id: str) -> int:
    try:
        team_object_id = ObjectId(user_team_id)
    except Exception:
        return 0

    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {"scholarship_players": 1},
    ) or {}
    scholarship_player_ids = [str(player_id) for player_id in (ftd_doc.get("scholarship_players") or []) if player_id]
    if not scholarship_player_ids:
        return 12

    fpd_docs = _load_fpd_map(fid, scholarship_player_ids)
    if not fpd_docs:
        non_graduating_count = db.players.count_documents(
            {
                "_id": {"$in": scholarship_player_ids},
                "year": {"$nin": ["Senior", "senior", "Graduate", "graduate"]},
            }
        )
        return max(0, 12 - int(non_graduating_count))
    non_graduating_count = 0
    for player_id in scholarship_player_ids:
        if not _is_graduating_year(_player_year_from_fpd_or_core(player_id, fpd_docs.get(player_id))):
            non_graduating_count += 1
    return max(0, 12 - int(non_graduating_count))


def _cut_year_rank(year_value: str | None) -> int:
    year = str(year_value or "").strip().lower()
    order = {
        "senior": 4,
        "junior": 3,
        "sophomore": 2,
        "freshman": 1,
    }
    return order.get(year, 0)


def _player_rt_from_doc(player_doc: dict[str, Any] | None) -> int:
    return int((_best_position((player_doc or {}).get("position_ratings") or {}).get("rating") or 0))


def _choose_cut_player_ids(
    roster_player_ids: list[str],
    fpd_map: dict[str, dict[str, Any]],
    cut_count: int,
) -> list[str]:
    if cut_count <= 0:
        return []

    players = [str(player_id) for player_id in roster_player_ids if player_id]

    def sort_key(player_id: str) -> tuple[Any, ...]:
        player_doc = fpd_map.get(player_id) or {}
        meta = (player_doc.get("meta") or {})
        return (
            _player_rt_from_doc(player_doc),
            -_cut_year_rank(meta.get("year")),
            random.random(),
        )

    ordered = sorted(players, key=sort_key)
    return ordered[:cut_count]


def _week_1_cut_requirement(
    franchise_doc: dict[str, Any] | None,
    fid: ObjectId | None,
    user_team_id: str | None,
) -> dict[str, int | bool]:
    if not franchise_doc or not fid or not user_team_id:
        return {"roster_count": 0, "cut_count": 0, "cut_required": False}
    week = int(franchise_doc.get("week", 1) or 1)
    training_status = franchise_doc.get("training_status", {}) or {}
    if week != 1 or not franchise_training_fully_complete_for_week(training_status, week):
        return {"roster_count": 0, "cut_count": 0, "cut_required": False}
    try:
        team_object_id = ObjectId(user_team_id)
    except Exception:
        return {"roster_count": 0, "cut_count": 0, "cut_required": False}
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {"players": 1},
    ) or {}
    roster_count = len([player_id for player_id in (ftd_doc.get("players") or []) if player_id])
    cut_count = max(0, roster_count - 12)
    return {"roster_count": roster_count, "cut_count": cut_count, "cut_required": cut_count > 0}


def _maybe_initialize_practice_squad_week_1(
    franchise_id: ObjectId,
    franchise_doc: dict[str, Any],
    *,
    user_team_object_id: Any,
    defer_if_user_cut_pending: bool = True,
) -> dict[str, Any] | None:
    """
    Build locked PS rosters after week-1 training camp cuts.

    CPU teams are cut during distant-CPU training; the user assigns their training
    squad via cut-players. Init is deferred until that assignment when
    defer_if_user_cut_pending=True (default). When the user roster is already
    legal (no cut required), init runs immediately from distant-CPU.
    """
    week = int(franchise_doc.get("week", 1) or 1)
    if week != 1:
        return None
    if (franchise_doc.get("practice_squad") or {}).get("initialized"):
        return None
    training_status = franchise_doc.get("training_status", {}) or {}
    if not bool(training_status.get("cpu_training_camp_cuts_applied")):
        return None
    if defer_if_user_cut_pending:
        cut_state = _week_1_cut_requirement(franchise_doc, franchise_id, user_team_object_id)
        if cut_state.get("cut_required"):
            return None

    from BackEnd.practice_squad.manager import (
        build_roster_announcement_story,
        initialize_practice_squad,
    )

    ps_state = initialize_practice_squad(franchise_id, franchise_doc)
    roster_story = build_roster_announcement_story(
        ps_state,
        franchise_id=str(franchise_id),
        team_id=str(user_team_object_id) if user_team_object_id else None,
    )
    _prepend_season_news_stories(franchise_doc, [roster_story])
    db.franchises.update_one(
        {"_id": franchise_id},
        {
            "$set": {
                "practice_squad": ps_state,
                "season_news": franchise_doc.get("season_news") or [],
            }
        },
    )
    franchise_doc["practice_squad"] = ps_state
    return ps_state


def _apply_cpu_training_camp_cuts(franchise_id: ObjectId, excluded_team_id: str | None = None) -> None:
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "players": 1, "scholarship_players": 1, "training_squad_players": 1, "playing_time_promise_players": 1},
    ))
    roster_ids = []
    for doc in ftd_docs:
        roster_ids.extend([str(player_id) for player_id in (doc.get("players") or []) if player_id])
    fpd_map = _load_fpd_map(franchise_id, roster_ids)

    for ftd_doc in ftd_docs:
        team_id = str(ftd_doc.get("team_id") or "")
        if not team_id or (excluded_team_id and team_id == str(excluded_team_id)):
            continue
        roster_player_ids = [str(player_id) for player_id in (ftd_doc.get("players") or []) if player_id]
        cut_count = max(0, len(roster_player_ids) - 12)
        if cut_count <= 0:
            franchise_team_data_collection.update_one(
                {"franchise_id": franchise_id, "team_id": ftd_doc.get("team_id")},
                {"$set": {"training_squad_players": [], "updated_at": datetime.utcnow()}},
            )
            continue

        # Lowest-RT players move to the training squad — NOT cut/deleted. They stay
        # in FPD (ineligible to play) and rejoin the pool at next Training Camp.
        ts_ids = _choose_cut_player_ids(roster_player_ids, fpd_map, cut_count)
        ts_set = set(ts_ids)
        remaining_ids = [player_id for player_id in roster_player_ids if player_id not in ts_set]
        existing_ts = [
            str(player_id) for player_id in (ftd_doc.get("training_squad_players") or []) if player_id
        ]
        new_training_squad = existing_ts + [pid for pid in ts_ids if pid not in existing_ts]
        remaining_scholarships = [
            str(player_id) for player_id in (ftd_doc.get("scholarship_players") or [])
            if str(player_id) in remaining_ids
        ]
        remaining_ptp = [
            str(player_id) for player_id in (ftd_doc.get("playing_time_promise_players") or [])
            if str(player_id) in remaining_ids
        ]
        total_player_attrs = sum(
            core_total_player_attrs((fpd_map.get(player_id) or {}).get("attributes") or {})
            for player_id in remaining_ids
        )
        _update_ftd_roster_state(
            franchise_id,
            ftd_doc.get("team_id"),
            {
                "players": remaining_ids,
                "scholarship_players": remaining_scholarships,
                "training_squad_players": new_training_squad,
                "playing_time_promise_players": remaining_ptp,
                "total_player_attrs": total_player_attrs,
                "updated_at": datetime.utcnow(),
            },
        )


TRAINING_SQUAD_ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH"]
TRAINING_SQUAD_REPORT_WEEKS = (6, 11, 16, 21, 26)


def _ts_progression_delta(ch_value: Any) -> int:
    """CH-gated weekly weighted attribute delta for training-squad players."""
    ch = int(ch_value or 0)
    if ch > 79:
        weights = [(-2, 10), (-1, 20), (0, 20), (1, 30), (2, 10)]
    elif ch > 59:
        weights = [(-2, 20), (-1, 20), (0, 30), (1, 20), (2, 10)]
    elif ch > 39:
        weights = [(-2, 20), (-1, 30), (0, 20), (1, 20), (2, 10)]
    elif ch > 19:
        weights = [(-2, 30), (-1, 20), (0, 20), (1, 20), (2, 10)]
    else:
        weights = [(-2, 40), (-1, 20), (0, 20), (1, 10), (2, 10)]
    values = [value for value, _weight in weights]
    relative_weights = [weight for _value, weight in weights]
    return int(random.choices(values, weights=relative_weights, k=1)[0])


def _ts_attr_snapshot(attrs: dict[str, Any]) -> dict[str, int]:
    """Anchor (base) values for the 13 evolving attrs."""
    out: dict[str, int] = {}
    for k in TRAINING_SQUAD_ATTR_KEYS:
        v = attrs.get("anchor_" + k, attrs.get(k))
        if v is not None:
            out[k] = int(v)
    return out


def _apply_training_squad_progression_and_report(
    franchise_id: ObjectId,
    franchise_doc: dict[str, Any],
    completed_week: int,
    user_team_id_str: Any,
) -> list[dict[str, Any]]:
    """Weeks 2–26: evolve every training-squad player's 13 attrs (CH-gated weighted delta) for
    user AND CPU teams (persisted to FPD; ratings recomputed). On report weeks
    (6/11/16/21/26) build the user's Training Squad Development report (delta vs the
    previous report) onto franchise_doc, with an inbox link. franchise_doc fields set
    here (season_inbox, training_squad_reports, training_squad_report_baseline) are
    persisted by the caller's update_fields.

    Returns this week's per-player gain records (all teams) for the news system:
    [{player_id, name, deltas, total_gain, rt, pos}, ...]."""
    if completed_week < 2 or completed_week > ScheduleManager.REGULAR_SEASON_WEEKS:
        return []
    from BackEnd.utils.position_ratings import compute_position_ratings

    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "training_squad_players": 1},
    ))
    all_ts_ids: list[str] = []
    for d in ftd_docs:
        all_ts_ids.extend([str(pid) for pid in (d.get("training_squad_players") or []) if pid])
    if not all_ts_ids:
        return []
    fpd_docs = list(franchise_players_data_collection.find(
        {"franchise_id": str(franchise_id), "player_id": {"$in": all_ts_ids}},
    ))
    fpd_by_id = {d["player_id"]: d for d in fpd_docs}

    # User team's TS players (report is user-only).
    user_ts_ids: list[str] = []
    if user_team_id_str:
        user_ftd = next((d for d in ftd_docs if str(d.get("team_id")) == str(user_team_id_str)), None)
        if user_ftd:
            user_ts_ids = [str(pid) for pid in (user_ftd.get("training_squad_players") or []) if pid]

    # Baseline (post-camp) captured on the first progression run, BEFORE evolving.
    baseline = franchise_doc.get("training_squad_report_baseline")
    if not baseline:
        baseline = {}
        for pid in user_ts_ids:
            d = fpd_by_id.get(pid)
            if d:
                baseline[pid] = _ts_attr_snapshot(d.get("attributes") or {})
        franchise_doc["training_squad_report_baseline"] = baseline

    # Evolve every training-squad player (all teams), recompute ratings.
    lo_clamp = 1  # PLAYER_ATTR_CLAMP[0] — min 1, no max
    weekly_gains: list[dict[str, Any]] = []
    for d in fpd_docs:
        attrs = d.get("attributes") or {}
        ch_for_progression = attrs.get("anchor_CH", attrs.get("CH"))
        deltas: dict[str, int] = {}
        for key in TRAINING_SQUAD_ATTR_KEYS:
            base = attrs.get("anchor_" + key, attrs.get(key))
            if base is None:
                continue
            new_val = max(lo_clamp, int(base) + _ts_progression_delta(ch_for_progression))
            deltas[key] = new_val - int(base)
            attrs[key] = new_val
            attrs["anchor_" + key] = new_val
        meta = d.get("meta") or {}
        player_name = (str(meta.get("first_name", "")) + " " + str(meta.get("last_name", ""))).strip()
        new_ratings = compute_position_ratings({
            "attributes": attrs,
            "height": meta.get("height"),
            "name": player_name,
        })
        franchise_players_data_collection.update_one(
            {"_id": d["_id"]},
            {"$set": {"attributes": attrs, "position_ratings": new_ratings, "updated_at": datetime.utcnow()}},
        )
        d["attributes"] = attrs  # keep in-memory copy current for the report
        best = _best_position(new_ratings or {})
        weekly_gains.append({
            "player_id": str(d.get("player_id") or ""),
            "name": player_name or str(d.get("player_id") or ""),
            "team_id": str(meta.get("team_id") or ""),
            "deltas": deltas,
            "total_gain": sum(deltas.values()),
            "rt": best.get("rating"),
            "pos": best.get("pos", "--"),
        })

    # Report (user only) on milestone weeks.
    if completed_week not in TRAINING_SQUAD_REPORT_WEEKS or not user_ts_ids:
        return weekly_gains
    players_report = []
    new_baseline: dict[str, Any] = {}
    for pid in user_ts_ids:
        d = fpd_by_id.get(pid)
        if not d:
            continue
        current = _ts_attr_snapshot(d.get("attributes") or {})
        meta = d.get("meta") or {}
        name = (str(meta.get("first_name", "")) + " " + str(meta.get("last_name", ""))).strip()
        players_report.append({
            "player_id": pid,
            "name": name or pid,
            "pos": _best_position(d.get("position_ratings") or {}).get("pos", "--"),
            "baseline": (baseline.get(pid) or {}),  # values at last report (or post-camp)
            "current": current,
        })
        new_baseline[pid] = current  # reset baseline for the next report period

    reports = franchise_doc.get("training_squad_reports") or {}
    reports[str(completed_week)] = {"week": int(completed_week), "players": players_report}
    franchise_doc["training_squad_reports"] = reports
    franchise_doc["training_squad_report_baseline"] = new_baseline

    season_inbox = list(franchise_doc.get("season_inbox") or [])
    season_inbox.insert(0, {
        "type": "training_squad_report",
        "week": int(completed_week),
        "message": "Week #" + str(int(completed_week)) + " Practice Squad Development report",
    })
    franchise_doc["season_inbox"] = season_inbox
    return weekly_gains


# ---------------------------------------------------------------------------
# Franchise News (see _documentation_master/projects/News_System.md)
# Stories live on the franchise doc as `season_news` (newest first) and are
# cleared at season rollover in finish_season.
# ---------------------------------------------------------------------------

NEWS_UPSET_RANK_GAP = 29  # winner_rank - loser_rank must exceed this
NEWS_UPSET_LOSER_RANK_MAX = 64  # losing team must be ranked 1–64 (inclusive)
NEWS_PS_ALL_STARS_MIN_GAIN = 4  # weekly cumulative attribute gain must exceed this

NEWS_ATTRIBUTE_FULL_NAMES = {
    "SC": "Scoring",
    "SH": "Shooting",
    "ID": "Inside Defense",
    "OD": "Outside Defense",
    "PS": "Passing",
    "BH": "Ball Handling",
    "RB": "Rebounding",
    "ST": "Strength",
    "AG": "Agility",
    "FT": "Free Throws",
    "ND": "Endurance",
    "IQ": "Basketball IQ",
    "CH": "Clutch",
}


def _join_with_and(items: list[str]) -> str:
    """Grammatical list join: 'A', 'A and B', 'A, B, and C'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + " and " + items[1]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _build_week_upset_report_story(
    week: int,
    results: list[dict[str, Any]],
    rank_by_team_id: dict[str, int],
    team_name_map: dict[str, str],
) -> dict[str, Any] | None:
    """Week {n} Upset Report: games where the winner's entering-week natl_rank was
    more than NEWS_UPSET_RANK_GAP spots worse than the loser's, and the losing team
    was ranked 1–NEWS_UPSET_LOSER_RANK_MAX. None when no games qualify."""
    upsets: list[tuple[int, str]] = []
    for row in results or []:
        away_id = str(row.get("away_id") or "")
        home_id = str(row.get("home_id") or "")
        away_score = int(row.get("away_score") or 0)
        home_score = int(row.get("home_score") or 0)
        if not away_id or not home_id or away_score == home_score:
            continue
        if away_score > home_score:
            winner_id, loser_id = away_id, home_id
            winner_score, loser_score = away_score, home_score
        else:
            winner_id, loser_id = home_id, away_id
            winner_score, loser_score = home_score, away_score
        winner_rank = rank_by_team_id.get(winner_id)
        loser_rank = rank_by_team_id.get(loser_id)
        if winner_rank is None or loser_rank is None:
            continue
        gap = int(winner_rank) - int(loser_rank)
        if gap <= NEWS_UPSET_RANK_GAP:
            continue
        loser_rank_int = int(loser_rank)
        if loser_rank_int < 1 or loser_rank_int > NEWS_UPSET_LOSER_RANK_MAX:
            continue
        line = (
            f"#{winner_rank}. {team_name_map.get(winner_id, winner_id)} upset "
            f"#{loser_rank}. {team_name_map.get(loser_id, loser_id)} "
            f"by a score of {winner_score}-{loser_score}."
        )
        upsets.append((int(loser_rank), line))
    if not upsets:
        return None
    # Ascending by the losing team's natl_rank (biggest-name victim first).
    upsets.sort(key=lambda item: item[0])
    return {
        "story_id": f"w{week}-upset-report",
        "week": int(week),
        "type": "upset_report",
        "headline": f"Week {week} Upset Report",
        "lines": [line for _, line in upsets],
        "created_at": datetime.utcnow(),
    }


NEWS_PS_ALL_STARS_MAX_LIST = 10


def _build_ps_all_stars_story(
    week: int,
    weekly_gains: list[dict[str, Any]],
    team_name_map: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Practice Squad All-Stars: training-squad players (league-wide) whose weekly
    cumulative attribute gain exceeds NEWS_PS_ALL_STARS_MIN_GAIN. None when nobody
    qualifies. Listed top NEWS_PS_ALL_STARS_MAX_LIST by cumulative gain; a tie at the
    cutoff extends the list to include everyone tied with the last spot."""
    team_name_map = team_name_map or {}
    qualifiers = [
        g for g in (weekly_gains or [])
        if int(g.get("total_gain") or 0) > NEWS_PS_ALL_STARS_MIN_GAIN
    ]
    if not qualifiers:
        return None
    qualifiers.sort(key=lambda g: int(g.get("total_gain") or 0), reverse=True)
    if len(qualifiers) > NEWS_PS_ALL_STARS_MAX_LIST:
        cutoff = int(qualifiers[NEWS_PS_ALL_STARS_MAX_LIST - 1].get("total_gain") or 0)
        qualifiers = [g for g in qualifiers if int(g.get("total_gain") or 0) >= cutoff]
    lines = []
    for g in qualifiers:
        deltas = g.get("deltas") or {}
        max_gain = max(deltas.values()) if deltas else 0
        top_attrs = [
            NEWS_ATTRIBUTE_FULL_NAMES.get(key, key)
            for key in TRAINING_SQUAD_ATTR_KEYS
            if deltas.get(key) == max_gain
        ]
        rt = g.get("rt")
        team_name = team_name_map.get(str(g.get("team_id") or ""), "")
        of_team = f" of {team_name}" if team_name else ""
        lines.append(
            f"{g.get('name')}{of_team} increased by {int(g.get('total_gain') or 0)} attribute points this week. "
            f"His strongest gains were in {_join_with_and(top_attrs)}. "
            f"He's now a {rt if rt is not None else '--'} rated {g.get('pos', '--')}."
        )
    return {
        "story_id": f"w{week}-ps-all-stars",
        "week": int(week),
        "type": "ps_all_stars",
        "headline": "Practice Squad All-Stars",
        "lines": lines,
        "created_at": datetime.utcnow(),
    }


NEWS_TOP_RECRUIT_MIN_RT = 49  # recruit RT must exceed this for the Top Rated section


def _build_recruiting_leans_story(
    week: int,
    lean_events: list[dict[str, str]],
    rank_by_team_id: dict[str, int],
    team_name_map: dict[str, str],
    recruit_by_id: dict[str, dict[str, Any]],
    conference_by_team_id: dict[str, str],
    user_conference: str | None,
) -> dict[str, Any] | None:
    """Updated Recruiting Leans Announced: recruits with RT > NEWS_TOP_RECRUIT_MIN_RT
    who newly added a team to their lean list this week, followed by new leans toward
    teams in the user's conference (a recruit can appear in both sections). None when
    neither section has content."""
    # Group the week's new-lean events per recruit (a recruit can pick up
    # multiple teams in performance-lean weeks; combine into one line).
    teams_by_recruit: dict[str, list[str]] = {}
    for event in lean_events or []:
        recruit_id = str(event.get("recruit_id") or "")
        team_id = str(event.get("team_id") or "")
        if not recruit_id or not team_id:
            continue
        team_ids = teams_by_recruit.setdefault(recruit_id, [])
        if team_id not in team_ids:
            team_ids.append(team_id)
    if not teams_by_recruit:
        return None

    top_entries: list[tuple[int, dict[str, Any], list[str]]] = []
    conference_recruits_by_team: dict[str, list[tuple[int, str]]] = {}
    for recruit_id, team_ids in teams_by_recruit.items():
        recruit_doc = recruit_by_id.get(recruit_id)
        if not recruit_doc:
            continue
        rt = _recruit_rt(recruit_doc)
        if rt > NEWS_TOP_RECRUIT_MIN_RT:
            top_entries.append((rt, recruit_doc, team_ids))
        if user_conference is None:
            continue
        for team_id in team_ids:
            if conference_by_team_id.get(team_id) == user_conference:
                conference_recruits_by_team.setdefault(team_id, []).append(
                    (rt, str(recruit_doc.get("name") or ""))
                )

    top_lines: list[str] = []
    top_entries.sort(key=lambda entry: entry[0], reverse=True)
    for rt, recruit_doc, team_ids in top_entries:
        team_names = _join_with_and([team_name_map.get(tid, tid) for tid in team_ids])
        top_lines.append(
            f"{recruit_doc.get('name')} who is a {rt} rated {recruit_doc.get('archetype')} "
            f"has announced a lean toward {team_names}."
        )

    conference_lines: list[str] = []
    # Conference teams from lowest natl_rank to highest (rank 1 first).
    for team_id in sorted(
        conference_recruits_by_team, key=lambda tid: rank_by_team_id.get(tid, 999)
    ):
        entries = sorted(conference_recruits_by_team[team_id], key=lambda e: e[0], reverse=True)
        conference_lines.append(team_name_map.get(team_id, team_id))
        conference_lines.append(", ".join(f"{name} ({rt})" for rt, name in entries))

    if not top_lines and not conference_lines:
        return None
    lines: list[str] = []
    if top_lines:
        lines.append("Top Rated Recruit Announcements")
        lines.extend(top_lines)
    if conference_lines:
        if lines:
            lines.append("")
        lines.append(f"Conference {user_conference} Lean Announcements")
        lines.extend(conference_lines)
    return {
        "story_id": f"w{week}-recruiting-leans",
        "week": int(week),
        "type": "recruiting_leans",
        "headline": "Updated Recruiting Leans Announced",
        "lines": lines,
        "created_at": datetime.utcnow(),
    }


def _prepend_season_news_stories(
    franchise_doc: dict[str, Any], stories: list[dict[str, Any]]
) -> None:
    """Prepend stories to season_news, skipping any story_id already present."""
    if not stories:
        return
    existing = list(franchise_doc.get("season_news") or [])
    existing_ids = {s.get("story_id") for s in existing}
    to_add = [s for s in stories if s.get("story_id") not in existing_ids]
    if to_add:
        franchise_doc["season_news"] = to_add + existing


def _build_ps_game_results_news_story(
    franchise_doc: dict[str, Any],
    week: int,
    franchise_id: ObjectId,
) -> dict[str, Any] | None:
    from BackEnd.practice_squad.manager import build_game_results_story

    ps_state = franchise_doc.get("practice_squad") or {}
    if not ps_state.get("initialized") or week < 2 or week > 19:
        return None
    _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    return build_game_results_story(
        ps_state,
        week,
        franchise_id=str(franchise_id),
        team_id=str(user_team_object_id) if user_team_object_id else None,
    )


def _append_franchise_week_news(
    franchise_id: ObjectId,
    franchise_doc: dict[str, Any],
    week: int,
    results: list[dict[str, Any]],
    ts_weekly_gains: list[dict[str, Any]],
    new_lean_events: list[dict[str, str]] | None = None,
) -> None:
    """Build the completed week's news stories and prepend them to franchise_doc['season_news'].

    Must run BEFORE _apply_regular_season_rank_prestige_updates so FTD natl_rank
    still holds the entering-week ranks the games were played under.
    """
    if week < 1 or week > ScheduleManager.REGULAR_SEASON_WEEKS:
        return
    rank_by_team_id: dict[str, int] = {}
    for doc in franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "natl_rank": 1},
    ):
        team_id = doc.get("team_id")
        rank = doc.get("natl_rank")
        if team_id is not None and rank is not None:
            rank_by_team_id[str(team_id)] = int(rank)

    team_name_map = _format_team_name_map()

    recruiting_leans_story = None
    if new_lean_events:
        recruit_ids = list({str(e.get("recruit_id") or "") for e in new_lean_events})
        recruit_by_id = {
            doc["recruit_id"]: doc
            for doc in franchise_recruits_data_collection.find(
                {"franchise_id": str(franchise_id), "recruit_id": {"$in": recruit_ids}},
                {"recruit_id": 1, "name": 1, "archetype": 1, "position_ratings": 1},
            )
        }
        event_team_oids = []
        for e in new_lean_events:
            try:
                event_team_oids.append(ObjectId(str(e.get("team_id"))))
            except Exception:
                continue
        conference_by_team_id = {
            str(t["_id"]): str(t.get("conference"))
            for t in db.teams.find({"_id": {"$in": event_team_oids}}, {"conference": 1})
            if t.get("conference") is not None
        }
        user_conference = None
        _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        if user_team_object_id:
            try:
                user_team_oid = ObjectId(str(user_team_object_id))
            except Exception:
                user_team_oid = None
            user_team_doc = (
                db.teams.find_one({"_id": user_team_oid}, {"conference": 1})
                if user_team_oid
                else None
            )
            if user_team_doc and user_team_doc.get("conference") is not None:
                user_conference = str(user_team_doc.get("conference"))
        recruiting_leans_story = _build_recruiting_leans_story(
            week,
            new_lean_events,
            rank_by_team_id,
            team_name_map,
            recruit_by_id,
            conference_by_team_id,
            user_conference,
        )

    # PS game-results news publishes at distant-CPU training (see _franchise_training_distant_phase_only).
    stories = [
        story
        for story in (
            _build_week_upset_report_story(week, results, rank_by_team_id, team_name_map),
            _build_ps_all_stars_story(week, ts_weekly_gains, team_name_map),
            recruiting_leans_story,
        )
        if story
    ]
    if not stories:
        return
    franchise_doc["season_news"] = stories + list(franchise_doc.get("season_news") or [])


def _franchise_news_headlines(franchise_doc: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    """Latest headlines for the Coach's Office News card (season_news is newest first)."""
    return [
        {
            "story_id": story.get("story_id"),
            "headline": story.get("headline"),
            "week": story.get("week"),
        }
        for story in (franchise_doc.get("season_news") or [])[:limit]
    ]


def _season_awards_score(season_stats: dict[str, Any]) -> tuple[int, int]:
    pts = int(season_stats.get("PTS", 0) or 0)
    ast = int(season_stats.get("AST", 0) or 0)
    reb = int(season_stats.get("REB", 0) or (int(season_stats.get("OREB", 0) or 0) + int(season_stats.get("DREB", 0) or 0)))
    stl = int(season_stats.get("STL", 0) or 0)
    blk = int(season_stats.get("BLK", 0) or 0)
    def_a = int(season_stats.get("DEF_A", 0) or 0)
    def_s = int(season_stats.get("DEF_S", 0) or 0)
    def_pct = int(round((def_s / def_a) * 100)) if def_a >= 130 else 0

    score = 2 * (pts + ast + reb + stl + blk)
    if def_a >= 130:
        if def_pct > 80:
            score += 15
        elif def_pct > 60:
            score += 10
        elif def_pct > 40:
            score += 5
    return score, def_pct


def _compute_all_american_teams(franchise_doc: dict[str, Any]) -> dict[str, Any]:
    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(franchise_doc["_id"])}))
    team_name_map = _format_team_name_map()
    candidates = []
    for doc in fpd_docs:
        meta = doc.get("meta", {})
        season_stats = doc.get("season", {}) or {}
        score, def_pct = _season_awards_score(season_stats)
        team_id = str(meta.get("team_id") or "")
        candidates.append({
            "player_id": doc.get("player_id"),
            "name": f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip(),
            "team_id": team_id,
            "team_name": team_name_map.get(team_id, meta.get("team", "")),
            "year": meta.get("year") or "",
            "score": score,
            "stats": {
                "PTS": int(season_stats.get("PTS", 0) or 0),
                "REB": int(season_stats.get("REB", 0) or (int(season_stats.get("OREB", 0) or 0) + int(season_stats.get("DREB", 0) or 0))),
                "AST": int(season_stats.get("AST", 0) or 0),
                "STL": int(season_stats.get("STL", 0) or 0),
                "BLK": int(season_stats.get("BLK", 0) or 0),
                "DEF%": def_pct,
            },
        })
    candidates.sort(key=lambda player: (-player["score"], -player["stats"]["PTS"], player["name"]))

    top_twenty = candidates[:20]
    third_team_pool = top_twenty[10:20]
    third_team = random.sample(third_team_pool, min(5, len(third_team_pool))) if third_team_pool else []
    return {
        "computed_at": datetime.utcnow(),
        "all_american_teams": {
            "first_team": top_twenty[:5],
            "second_team": top_twenty[5:10],
            "third_team": third_team,
        },
    }


def _persist_week_35_awards_if_needed(franchise_doc: dict[str, Any]) -> dict[str, Any]:
    awards = franchise_doc.get(AWARDS_FIELD) or {}
    if awards.get("all_american_teams"):
        return awards
    awards = _compute_all_american_teams(franchise_doc)
    db.franchises.update_one(
        {"_id": franchise_doc["_id"]},
        {"$set": {AWARDS_FIELD: awards}},
    )
    franchise_doc[AWARDS_FIELD] = awards
    return awards


def _week_35_result_entry_from_recruit(recruit_doc: dict[str, Any], team_doc: dict[str, Any], scholarship: bool, playing_time: bool, walk_on: bool = False) -> dict[str, Any]:
    best_pos = _best_position(recruit_doc.get("position_ratings") or {})
    return {
        # keep the recruit's stable id so its pre-generated portrait follows him onto the
        # roster (players/master/<id>.png). Walk-ons have no recruit_id -> fresh uuid.
        "player_id": recruit_doc.get("recruit_id") or str(uuid.uuid4()),
        "recruit_id": recruit_doc.get("recruit_id"),
        "team_id": str(team_doc["_id"]),
        "team_name": team_doc.get("name", ""),
        "name": recruit_doc.get("name", "--"),
        "archetype": "Walk On" if walk_on else recruit_doc.get("archetype", "--"),
        "home_region": recruit_doc.get("Home Region", "--"),
        "height": recruit_doc.get("height"),
        "weight": recruit_doc.get("weight"),
        # Carry the rolled year through signing (recruits and walk-ons both roll a
        # year at generation); it advances one step at the season transition.
        "year": recruit_doc.get("year") or "JH",
        "position_ratings": (recruit_doc.get("position_ratings") or {}).copy(),
        "attributes": (recruit_doc.get("attributes") or {}).copy(),
        "pos": best_pos.get("pos", "--"),
        "rt": best_pos.get("rating"),
        "scholarship": bool(scholarship),
        "playing_time": bool(playing_time),
        "walk_on": bool(walk_on),
        "signed_display": team_doc.get("name", "") + (" (walk on)" if walk_on else ""),
        "jersey": None,
    }


def _build_cpu_week_35_orders(
    team_doc: dict[str, Any],
    recruits: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    team_id = str(team_doc["_id"])
    region = str(team_doc.get("region") or "").upper()
    lean_matches = []
    in_region_rest = []
    for recruit in recruits:
        lean = recruit.get("Lean") or {}
        team_on_lean = any(lean.get(slot) == team_id for slot in ("1", "2", "3"))
        if team_on_lean:
            lean_matches.append(recruit)
        elif str(recruit.get("Home Region") or "").upper() == region:
            in_region_rest.append(recruit)

    lean_matches.sort(key=lambda recruit: (_best_position(recruit.get("position_ratings") or {}).get("rating") or -1), reverse=True)
    selected_ids = {recruit.get("recruit_id") for recruit in lean_matches if recruit.get("recruit_id")}
    remaining_slots = max(0, MAX_RECRUITING_ORDER_SLOTS - len(lean_matches))
    high_pool = []
    low_pool = []
    for recruit in in_region_rest:
        recruit_id = recruit.get("recruit_id")
        if not recruit_id or recruit_id in selected_ids:
            continue
        rt = _best_position(recruit.get("position_ratings") or {}).get("rating") or 0
        if rt >= 25:
            high_pool.append(recruit)
        else:
            low_pool.append(recruit)

    high_slots = remaining_slots // 2
    low_slots = remaining_slots - high_slots
    selected_high = random.sample(high_pool, min(high_slots, len(high_pool))) if high_pool else []
    selected_low = random.sample(low_pool, min(low_slots, len(low_pool))) if low_pool else []

    remaining_after_split = remaining_slots - len(selected_high) - len(selected_low)
    if remaining_after_split > 0:
        extra_high_pool = [recruit for recruit in high_pool if recruit not in selected_high]
        extra_low_pool = [recruit for recruit in low_pool if recruit not in selected_low]
        rollover_pool = extra_high_pool + extra_low_pool
        if rollover_pool:
            extras = random.sample(rollover_pool, min(remaining_after_split, len(rollover_pool)))
            for recruit in extras:
                rt = _best_position(recruit.get("position_ratings") or {}).get("rating") or 0
                if rt >= 25:
                    selected_high.append(recruit)
                else:
                    selected_low.append(recruit)

    ordered = lean_matches + selected_high + selected_low

    entries = []
    for recruit in ordered[:MAX_RECRUITING_ORDER_SLOTS]:
        entries.append({
            "id": recruit.get("recruit_id"),
            "points": 0,
            "scholarship": False,
            "playing_time": False,
        })

    def add_points_to_entry(recruit_id: str | None, points: int) -> int:
        if not recruit_id or points <= 0:
            return 0
        for entry in entries:
            if entry.get("id") == recruit_id:
                entry["points"] = int(entry.get("points", 0) or 0) + points
                return points
        return 0

    points_remaining = WEEK_35_RECRUITING_POINTS_BUDGET
    if selected_low:
        assigned = add_points_to_entry(
            random.choice(selected_low).get("recruit_id"),
            min(points_remaining, 3),
        )
        points_remaining -= assigned
    if selected_high and points_remaining > 0:
        assigned = add_points_to_entry(
            random.choice(selected_high).get("recruit_id"),
            min(points_remaining, random.randint(5, 7)),
        )
        points_remaining -= assigned

    lean_entries = [entry for entry in entries if any(((next((recruit for recruit in lean_matches if recruit.get("recruit_id") == entry.get("id")), {}) or {}).get("Lean") or {}).get(slot) == team_id for slot in ("1", "2", "3"))]
    if not lean_entries and points_remaining > 0:
        regional_fallback = sorted(
            [recruit for recruit in in_region_rest if recruit.get("recruit_id") in {entry.get("id") for entry in entries}],
            key=lambda recruit: (_best_position(recruit.get("position_ratings") or {}).get("rating") or -1),
            reverse=True,
        )[:5]
        fallback_ids = [recruit.get("recruit_id") for recruit in regional_fallback if recruit.get("recruit_id")]
        if fallback_ids:
            base = points_remaining // len(fallback_ids)
            remainder = points_remaining % len(fallback_ids)
            for index, recruit_id in enumerate(fallback_ids):
                add_points_to_entry(recruit_id, base + (1 if index < remainder else 0))
            points_remaining = 0
    elif lean_entries and points_remaining > 0:
        lean_entries.sort(
            key=lambda entry: (
                _best_position((next((recruit for recruit in lean_matches if recruit.get("recruit_id") == entry.get("id")), {}) or {}).get("position_ratings") or {}).get("rating") or -1
            ),
            reverse=True,
        )
        if points_remaining < len(lean_entries):
            for entry in random.sample(lean_entries, points_remaining):
                entry["points"] = int(entry.get("points", 0) or 0) + 1
            points_remaining = 0
        elif len(lean_entries) == 1:
            lean_entries[0]["points"] += points_remaining
            points_remaining = 0
        elif len(lean_entries) in {2, 3}:
            lead_points = math.floor(points_remaining * 0.8)
            remainder = points_remaining - lead_points
            lean_entries[0]["points"] += lead_points
            base = remainder // (len(lean_entries) - 1)
            extra = remainder % (len(lean_entries) - 1)
            for index, entry in enumerate(lean_entries[1:]):
                entry["points"] += base + (1 if index < extra else 0)
            points_remaining = 0
        else:
            # 4+ lean players:
            # (a) 40-60% of remaining points to one of the 4 highest RT lean players
            first_pct = random.randint(40, 60)
            first_points = math.floor(points_remaining * first_pct / 100)
            first_chosen = random.choice(lean_entries[:4])
            first_chosen["points"] += first_points
            points_remaining -= first_points
            chunk_recipients = {id(first_chosen)}
            # (b) if the roll in (a) was < 50%, a second 40-60% chunk of the
            # still-remaining points goes to one of the 3 highest RT remaining
            if first_pct < 50 and points_remaining > 0:
                remaining_sorted = [entry for entry in lean_entries if id(entry) not in chunk_recipients]
                second_points = math.floor(points_remaining * random.randint(40, 60) / 100)
                second_chosen = random.choice(remaining_sorted[:3])
                second_chosen["points"] += second_points
                points_remaining -= second_points
                chunk_recipients.add(id(second_chosen))
            # (c) shuffle the remaining lean players and deal 1-4 points each until
            # exhausted; leftover after the full list goes to one random lean player
            dealt_pool = [entry for entry in lean_entries if id(entry) not in chunk_recipients]
            random.shuffle(dealt_pool)
            for entry in dealt_pool:
                if points_remaining <= 0:
                    break
                deal = min(points_remaining, random.randint(1, 4))
                entry["points"] += deal
                points_remaining -= deal
            if points_remaining > 0:
                random.choice(lean_entries)["points"] += points_remaining
            points_remaining = 0
    return _normalize_week_35_recruiting_orders(entries)


def _allowed_jersey_numbers(position: str) -> list[int]:
    pos = str(position or "").upper()
    if pos == "PG":
        return list(range(0, 37))
    if pos in {"SG", "SF"}:
        return list(range(0, 46)) + [77]
    return [number for number in range(0, 56) if number < 20 or number > 29] + [88, 91, 99]


def _assign_jerseys_to_signed_players(
    signed_players: list[dict[str, Any]],
    franchise_id: str | ObjectId,
) -> None:
    team_to_existing_numbers: dict[str, set[int]] = defaultdict(set)
    franchise_id_obj = ObjectId(franchise_id) if isinstance(franchise_id, str) else franchise_id
    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id_obj}, {"team_id": 1, "players": 1}))
    roster_player_ids = []
    for ftd_doc in ftd_docs:
        for player_id in (ftd_doc.get("players") or []):
            roster_player_ids.append(str(player_id))
    fpd_map = _load_fpd_map(franchise_id, roster_player_ids)
    for ftd_doc in ftd_docs:
        team_id = str(ftd_doc.get("team_id"))
        for player_id in (ftd_doc.get("players") or []):
            player_id_str = str(player_id)
            player_fpd = fpd_map.get(player_id_str)
            if _is_graduating_year(_player_year_from_fpd_or_core(player_id_str, player_fpd)):
                continue
            meta = (player_fpd or {}).get("meta", {})
            jersey = meta.get("jersey")
            if jersey is None:
                core_doc = db.players.find_one({"_id": player_id_str}, {"jersey": 1}) or {}
                jersey = core_doc.get("jersey")
            if isinstance(jersey, int):
                team_to_existing_numbers[team_id].add(jersey)

    for player in signed_players:
        team_id = str(player.get("team_id") or "")
        allowed = [number for number in _allowed_jersey_numbers(player.get("pos")) if number not in team_to_existing_numbers[team_id]]
        if not allowed:
            allowed = _allowed_jersey_numbers(player.get("pos"))
        jersey = random.choice(allowed)
        player["jersey"] = jersey
        team_to_existing_numbers[team_id].add(jersey)


def _current_team_capacity_state(franchise_id: ObjectId) -> dict[str, dict[str, Any]]:
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "players": 1, "scholarship_players": 1, "training_squad_players": 1},
    ))
    roster_player_ids = []
    for doc in ftd_docs:
        roster_player_ids.extend([str(player_id) for player_id in (doc.get("players") or []) if player_id])
        roster_player_ids.extend([str(player_id) for player_id in (doc.get("training_squad_players") or []) if player_id])
    fpd_map = _load_fpd_map(franchise_id, roster_player_ids)
    state: dict[str, dict[str, Any]] = {}
    for doc in ftd_docs:
        team_id = str(doc.get("team_id"))
        # Active + training squad both occupy roster slots next season (TS returns to
        # the pool), so both count toward the 15-man cap when signing recruits.
        players = (
            [str(player_id) for player_id in (doc.get("players") or []) if player_id]
            + [str(player_id) for player_id in (doc.get("training_squad_players") or []) if player_id]
        )
        scholarship_players = {str(player_id) for player_id in (doc.get("scholarship_players") or []) if player_id}
        returning_players = []
        returning_scholarships = set()
        for player_id in players:
            if _is_graduating_year(_player_year_from_fpd_or_core(player_id, fpd_map.get(player_id))):
                continue
            returning_players.append(player_id)
            if player_id in scholarship_players:
                returning_scholarships.add(player_id)
        state[team_id] = {
            "roster_count": len(returning_players),
            "scholarship_count": len(returning_scholarships),
            "returning_players": returning_players,
            "returning_scholarship_players": returning_scholarships,
        }
    return state


def _choose_week_35_team_slots(chance_map: dict[str, int]) -> list[tuple[str, int]]:
    if not chance_map:
        return []
    ordered = sorted(chance_map.items(), key=lambda item: (-item[1], item[0]))
    grouped: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for team_id, value in ordered:
        grouped[int(value)].append((team_id, value))
    selected: list[tuple[str, int]] = []
    for value in sorted(grouped.keys(), reverse=True):
        group = grouped[value]
        remaining_slots = 4 - len(selected)
        if remaining_slots <= 0:
            break
        if len(group) <= remaining_slots:
            selected.extend(group)
            continue
        selected.extend(random.sample(group, remaining_slots))
        break
    selected.sort(key=lambda item: (-item[1], item[0]))
    return selected[:4]


def _week_35_team_score(
    team_id: str,
    entry: dict[str, Any],
    lean: dict[str, Any],
    scholarship_offer_count: int,
    pt_offer_count: int,
) -> int:
    assigned_points = int(entry.get("points", 0) or 0)
    subtotal = 1 + assigned_points
    if entry.get("playing_time"):
        if 1 <= pt_offer_count <= 2:
            subtotal += 15
        elif pt_offer_count > 2:
            subtotal += 7
    multiplier = 1
    if lean.get("1") == team_id:
        multiplier = 5
    elif lean.get("2") == team_id:
        multiplier = 3
    elif lean.get("3") == team_id:
        multiplier = 2
    return subtotal * multiplier


def _run_week_35_signings(franchise_doc: dict[str, Any]) -> dict[str, Any]:
    franchise_id = franchise_doc["_id"]
    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id}))
    team_ids = [doc["team_id"] for doc in ftd_docs if doc.get("team_id")]
    team_docs = {
        str(doc["_id"]): doc
        for doc in db.teams.find({"_id": {"$in": team_ids}})
    }
    recruits = list(franchise_recruits_data_collection.find({"franchise_id": str(franchise_id)}))
    recruits.sort(key=lambda recruit: (_best_position(recruit.get("position_ratings") or {}).get("rating") or -1), reverse=True)
    capacity = _current_team_capacity_state(franchise_id)

    signed_players: list[dict[str, Any]] = []
    signed_by_recruit_id: dict[str, dict[str, Any]] = {}

    for recruit in recruits:
        recruit_id = recruit.get("recruit_id")
        if not recruit_id:
            continue
        chance_map: dict[str, int] = {}
        scholarship_offers: list[str] = []
        pt_offers: list[str] = []
        lean = recruit.get("Lean") or {}
        entries_by_team: dict[str, dict[str, Any]] = {}
        for ftd_doc in ftd_docs:
            team_id = str(ftd_doc.get("team_id"))
            team_state = capacity.get(team_id, {})
            if team_state.get("roster_count", 0) >= 15:
                continue
            orders = ftd_doc.get(RECRUITING_ORDERS_WEEK_35_FIELD) or {}
            entry = next((value for value in orders.values() if isinstance(value, dict) and value.get("id") == recruit_id), None)
            if not entry:
                continue
            entries_by_team[team_id] = entry
            if entry.get("playing_time"):
                pt_offers.append(team_id)
            chance_map[team_id] = 0

        if not chance_map:
            continue

        scholarship_offer_count = len(scholarship_offers)
        pt_offer_count = len(pt_offers)
        for team_id, entry in entries_by_team.items():
            chance_map[team_id] = _week_35_team_score(
                team_id,
                entry,
                lean,
                scholarship_offer_count,
                pt_offer_count,
            )

        eligible_chances = {team_id: value for team_id, value in chance_map.items() if value > 0}
        if not eligible_chances:
            continue
        finalists = _choose_week_35_team_slots(eligible_chances)
        total = sum(value for _, value in finalists)
        if total <= 0:
            continue
        draw = random.randint(1, total)
        running = 0
        winner_team_id = None
        for team_id, value in finalists:
            running += value
            if draw <= running:
                winner_team_id = team_id
                break
        if not winner_team_id or winner_team_id not in team_docs:
            continue

        scholarship = False
        playing_time = winner_team_id in pt_offers
        signed_entry = _week_35_result_entry_from_recruit(
            recruit,
            team_docs[winner_team_id],
            scholarship=scholarship,
            playing_time=playing_time,
            walk_on=False,
        )
        signed_players.append(signed_entry)
        signed_by_recruit_id[recruit_id] = {
            "team_id": winner_team_id,
            "team_name": team_docs[winner_team_id].get("name", ""),
            "walk_on": False,
        }
        capacity[winner_team_id]["roster_count"] += 1
    for team_id, team_doc in team_docs.items():
        while capacity.get(team_id, {}).get("roster_count", 0) < 15:
            walk_on = generate_walk_on_profile()
            signed_players.append(
                _week_35_result_entry_from_recruit(
                    walk_on,
                    team_doc,
                    scholarship=False,
                    playing_time=False,
                    walk_on=True,
                )
            )
            capacity[team_id]["roster_count"] += 1

    _assign_jerseys_to_signed_players(signed_players, franchise_id)
    return {
        "generated_at": datetime.utcnow(),
        "signed_players": signed_players,
        "signed_by_recruit_id": signed_by_recruit_id,
    }

@router.get("/franchise/recruiting-data")
def get_recruiting_data(
    franchise_id: str,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    fid = franchise_doc["_id"]

    team_name, user_team_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id:
        raise HTTPException(status_code=404, detail="User team not selected")

    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": ObjectId(user_team_id)},
        {"Recruits": 1, RECRUITING_ORDERS_WEEK_35_FIELD: 1},
    )
    saved_orders = ftd_doc.get("Recruits", {}) if ftd_doc else {}
    saved_week_35_orders = ftd_doc.get(RECRUITING_ORDERS_WEEK_35_FIELD, {}) if ftd_doc else {}
    week_35_results = franchise_doc.get(WEEK_35_RECRUITING_RESULTS_FIELD) or {}

    recruits = list(
        franchise_recruits_data_collection.find(
            {"franchise_id": str(franchise_id)},
            {"_id": 0, "franchise_id": 0},
        )
    )
    team_name_map = {
        str(team["_id"]): team.get("name", str(team["_id"]))
        for team in db.teams.find({}, {"name": 1})
    }

    return {
        "team": team_name,
        "team_id": user_team_id,
        "week": franchise_doc.get("week", 1),
        "current_results_week": franchise_doc.get("week", 1) if str(franchise_doc.get("week", 1)) in (franchise_doc.get("recruiting_results", {}) or {}) else None,
        "saved_orders": saved_orders,
        "saved_orders_week_35": saved_week_35_orders,
        "saved_order_entries_week_35": _week_35_order_entries(saved_week_35_orders),
        "available_roster_spots": _calculate_available_roster_spots(fid, user_team_id),
        "available_scholarships": _calculate_available_scholarships(fid, user_team_id),
        "week_35_points_budget": WEEK_35_RECRUITING_POINTS_BUDGET,
        "recruits": recruits,
        "team_name_map": team_name_map,
        "week_35_recruiting_results": week_35_results,
        "week_35_recruiting_ran": bool(franchise_doc.get("week_35_recruiting_ran", False)),
    }


@router.get("/franchise/news")
def get_franchise_news(
    franchise_id: str,
    user: dict = Depends(get_current_user),
):
    """Season news feed for the standalone news page (newest first; cleared at season rollover)."""
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    return {
        "week": int(franchise_doc.get("week", 1) or 1),
        "news": franchise_doc.get("season_news") or [],
    }


@router.get("/franchise/practice-squad/standings")
def get_practice_squad_standings(
    franchise_id: str,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    ps = franchise_doc.get("practice_squad") or {}
    if not ps.get("initialized"):
        return {"initialized": False, "standings": {}, "teams": {}, "week": int(franchise_doc.get("week", 1) or 1)}
    return {
        "initialized": True,
        "week": int(franchise_doc.get("week", 1) or 1),
        "standings": ps.get("standings") or {},
        "teams": ps.get("teams") or {},
        "tier_names": {str(i): n for i, n in enumerate(["", "All-Americans", "All-Stars", "Varsity", "JV", "Squad", "Scrubs"]) if i},
    }


@router.get("/franchise/practice-squad/schedule")
def get_practice_squad_schedule(
    franchise_id: str,
    week: int | None = None,
    user: dict = Depends(get_current_user),
):
    from BackEnd.practice_squad.manager import _completed_games_for_week

    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    ps = franchise_doc.get("practice_squad") or {}
    current_week = int(franchise_doc.get("week", 1) or 1)
    if not ps.get("initialized"):
        return {"initialized": False, "week": current_week, "games": [], "weeks": []}
    schedule = ps.get("schedule") or {}
    teams = ps.get("teams") or {}
    weeks_available = sorted(set(list(int(w) for w in schedule.keys()) + list(range(16, 20))))

    def _enrich(games: list) -> list:
        out = []
        for g in games:
            row = dict(g)
            row["home_display"] = (teams.get(row.get("home_team_id")) or {}).get("display_name")
            row["away_display"] = (teams.get(row.get("away_team_id")) or {}).get("display_name")
            out.append(row)
        return out

    if week is not None:
        games = list(schedule.get(str(week)) or [])
        if week >= 16:
            completed = _completed_games_for_week(ps, week)
            from BackEnd.practice_squad.manager import _games_for_week
            upcoming = [g for g in _games_for_week(ps, week) if g.get("status") not in ("completed", "forfeit")]
            games = completed + upcoming
        return {"initialized": True, "week": week, "games": _enrich(games)}
    return {"initialized": True, "week": current_week, "weeks": weeks_available}


@router.get("/franchise/practice-squad/brackets")
def get_practice_squad_brackets(
    franchise_id: str,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    ps = franchise_doc.get("practice_squad") or {}
    return {
        "initialized": bool(ps.get("initialized")),
        "week": int(franchise_doc.get("week", 1) or 1),
        "tournaments": ps.get("tournaments") or {},
        "championship": ps.get("championship") or {},
        "teams": ps.get("teams") or {},
    }


@router.get("/franchise/practice-squad/team")
def get_practice_squad_team(
    franchise_id: str,
    ps_team_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Roster + ps_season_stats for a Practice Squad pseudo-team."""
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    ps = franchise_doc.get("practice_squad") or {}
    if ps.get("initialized") and not ps.get("ps_season_stats_backfilled"):
        from BackEnd.practice_squad.stats import ensure_ps_season_stats_backfilled

        ps = ensure_ps_season_stats_backfilled(str(franchise_id), ps)
        db.franchises.update_one(
            {"_id": franchise_doc["_id"]},
            {"$set": {"practice_squad": ps}},
        )
    team = (ps.get("teams") or {}).get(ps_team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Practice Squad team not found")

    fid = str(franchise_id)
    tier = int(team.get("tier") or 0)
    roster_slots = list(team.get("roster") or [])
    if tier == 6:
        player_ids = set()
        for week_roster in (ps.get("scrubs_rosters") or {}).values():
            for slot in week_roster or []:
                pid = str(slot.get("player_id") or "")
                if pid:
                    player_ids.add(pid)
        roster_slots = []
        seen: set[str] = set()
        for week_roster in (ps.get("scrubs_rosters") or {}).values():
            for slot in week_roster or []:
                pid = str(slot.get("player_id") or "")
                if pid and pid not in seen:
                    seen.add(pid)
                    roster_slots.append(slot)

    fpd_ids = [str(s["player_id"]) for s in roster_slots if s.get("source") == "fpd"]
    frd_ids = [str(s["player_id"]) for s in roster_slots if s.get("source") == "frd"]

    fpd_map = {
        d["player_id"]: d
        for d in franchise_players_data_collection.find(
            {"franchise_id": fid, "player_id": {"$in": fpd_ids}}
        )
    } if fpd_ids else {}
    frd_map = {
        d["recruit_id"]: d
        for d in franchise_recruits_data_collection.find(
            {"franchise_id": fid, "recruit_id": {"$in": frd_ids}}
        )
    } if frd_ids else {}

    team_name_map = _format_team_name_map()
    players = []
    for slot in roster_slots:
        pid = str(slot.get("player_id") or "")
        source = slot.get("source")
        if source == "fpd":
            doc = fpd_map.get(pid) or {}
            meta = doc.get("meta") or {}
            parent_id = str(meta.get("team_id") or "")
            parent_name = team_name_map.get(parent_id, "")
            players.append({
                "player_id": pid,
                "source": "fpd",
                "name": slot.get("name") or f"{meta.get('first_name', '')} {meta.get('last_name', '')}".strip(),
                "parent_team_name": parent_name,
                "position_ratings": doc.get("position_ratings") or {},
                "attributes": doc.get("attributes") or {},
                "year": format_player_year_display(meta.get("year")) if meta.get("year") else None,
                "archetype": meta.get("archetype") or "",
                "height": meta.get("height"),
                "weight": meta.get("weight"),
                "stats": doc.get("ps_season_stats") or {},
            })
        else:
            doc = frd_map.get(pid) or {}
            players.append({
                "player_id": pid,
                "source": "frd",
                "name": slot.get("name") or doc.get("name") or "",
                "parent_team_name": None,
                "position_ratings": doc.get("position_ratings") or {},
                "attributes": doc.get("attributes") or {},
                "year": format_player_year_display(doc.get("year")) if doc.get("year") else None,
                "archetype": doc.get("archetype") or "",
                "height": doc.get("height"),
                "weight": doc.get("weight"),
                "stats": doc.get("ps_season_stats") or {},
            })

    season_map = {
        str(p.get("player_id") or ""): dict(p.get("stats") or {})
        for p in players
        if p.get("player_id")
    }
    from BackEnd.utils.scouting_utils import build_enriched_projected_starting_five

    projected_starting_five = build_enriched_projected_starting_five(players, season_map)

    return {
        "team": team,
        "players": players,
        "projected_starting_five": projected_starting_five,
    }


@router.get("/franchise/recruiting-results")
def get_recruiting_results(
    franchise_id: str,
    week: int | None = None,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    requested_week = week if week is not None else int(franchise_doc.get("week", 1) or 1)
    return _build_recruiting_results_payload(franchise_doc, requested_week)


@router.get("/franchise/awards")
def get_franchise_awards(
    franchise_id: str,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    week = int(franchise_doc.get("week", 1) or 1)
    if week < 35:
        raise HTTPException(status_code=400, detail="Awards are not available until week 35")
    awards = _persist_week_35_awards_if_needed(franchise_doc)
    return awards


@router.post("/franchise/recruiting-orders")
def save_recruiting_orders(
    req: SaveRecruitingOrdersRequest,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    fid = franchise_doc["_id"]
    week = int(franchise_doc.get("week", 1) or 1)
    is_visit_window = 20 <= week <= 26
    is_week_35_window = week == 35
    if not is_visit_window and not is_week_35_window:
        raise HTTPException(status_code=400, detail="Recruiting orders can only be saved during weeks 20-26 or week 35")

    valid_recruit_ids = set(
        franchise_recruits_data_collection.distinct(
            "recruit_id",
            {"franchise_id": str(req.franchise_id)},
        )
    )

    _, user_team_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id:
        raise HTTPException(status_code=404, detail="User team not selected")

    user_team_id_str = str(user_team_id)

    if is_week_35_window:
        order_entries = [
            {
                "id": str((entry or {}).get("id") or "").strip(),
                "points": _safe_int((entry or {}).get("points", 0) or 0, 0),
                "scholarship": False,
                "playing_time": bool((entry or {}).get("playing_time", False)),
            }
            for entry in (req.order_entries or [])
        ]
        order_entries = [entry for entry in order_entries if entry["id"]]
        if len(order_entries) > MAX_RECRUITING_ORDER_SLOTS:
            raise HTTPException(status_code=400, detail=f"A maximum of {MAX_RECRUITING_ORDER_SLOTS} recruits can be ranked")
        for entry in order_entries:
            if entry["points"] < 0:
                raise HTTPException(status_code=400, detail="Recruiting points cannot be negative")
        recruit_ids = [entry["id"] for entry in order_entries]
        if len(set(recruit_ids)) != len(recruit_ids):
            raise HTTPException(status_code=400, detail="Recruiting orders cannot contain duplicate recruits")
        if any(recruit_id not in valid_recruit_ids for recruit_id in recruit_ids):
            raise HTTPException(status_code=400, detail="Recruiting orders include an invalid recruit id")
        if sum(int(entry.get("points", 0) or 0) for entry in order_entries) > WEEK_35_RECRUITING_POINTS_BUDGET:
            raise HTTPException(
                status_code=400,
                detail=f"Recruiting orders cannot exceed {WEEK_35_RECRUITING_POINTS_BUDGET} total recruiting points",
            )

        orders_payload = _normalize_week_35_recruiting_orders(order_entries)
        franchise_team_data_collection.update_one(
            {"franchise_id": fid, "team_id": ObjectId(user_team_id_str)},
            {
                "$set": {
                    RECRUITING_ORDERS_WEEK_35_FIELD: orders_payload,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        team_docs = {
            str(team["_id"]): team
            for team in db.teams.find(
                {"_id": {"$in": [doc["team_id"] for doc in franchise_team_data_collection.find({"franchise_id": fid}, {"team_id": 1}) if doc.get("team_id")]}},
                {"name": 1, "region": 1},
            )
        }
        recruits = list(
            franchise_recruits_data_collection.find(
                {"franchise_id": str(req.franchise_id)},
                {"_id": 0, "franchise_id": 0},
            )
        )
        for team_id, team_doc in team_docs.items():
            if team_id == user_team_id_str:
                continue
            existing = franchise_team_data_collection.find_one(
                {"franchise_id": fid, "team_id": ObjectId(team_id)},
                {RECRUITING_ORDERS_WEEK_35_FIELD: 1},
            ) or {}
            if existing.get(RECRUITING_ORDERS_WEEK_35_FIELD):
                continue
            franchise_team_data_collection.update_one(
                {"franchise_id": fid, "team_id": ObjectId(team_id)},
                {
                    "$set": {
                        RECRUITING_ORDERS_WEEK_35_FIELD: _build_cpu_week_35_orders(team_doc, recruits),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
        return {"status": "success", "saved_orders_week_35": orders_payload, "results_week": None}

    recruit_ids = [str(recruit_id) for recruit_id in (req.recruit_ids or []) if recruit_id]
    if len(recruit_ids) > MAX_RECRUITING_ORDER_SLOTS:
        raise HTTPException(status_code=400, detail=f"A maximum of {MAX_RECRUITING_ORDER_SLOTS} recruits can be ranked")
    if len(set(recruit_ids)) != len(recruit_ids):
        raise HTTPException(status_code=400, detail="Recruiting orders cannot contain duplicate recruits")
    if any(recruit_id not in valid_recruit_ids for recruit_id in recruit_ids):
        raise HTTPException(status_code=400, detail="Recruiting orders include an invalid recruit id")
    current_week_results = franchise_doc.get("recruiting_results", {}) or {}
    if is_visit_window and current_week_results.get(str(week)):
        raise HTTPException(status_code=400, detail="Recruiting invites have already been processed for this week")

    orders_payload = _normalize_recruiting_orders(recruit_ids)
    franchise_team_data_collection.update_one(
        {"franchise_id": fid, "team_id": ObjectId(user_team_id_str)},
        {
            "$set": {
                "Recruits": orders_payload,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    return {"status": "success", "saved_orders": orders_payload, "results_week": None}


@router.post("/franchise/run-week-35-recruiting")
def run_week_35_recruiting(
    req: RunWeek35RecruitingRequest,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    if int(franchise_doc.get("week", 1) or 1) != 35:
        raise HTTPException(status_code=400, detail="Week 35 recruiting can only run during week 35")
    if franchise_doc.get("week_35_recruiting_ran"):
        raise HTTPException(status_code=400, detail="Week 35 recruiting has already run")

    fid = franchise_doc["_id"]
    _, user_team_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id:
        raise HTTPException(status_code=404, detail="User team not selected")

    user_ftd = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": ObjectId(user_team_id)},
        {RECRUITING_ORDERS_WEEK_35_FIELD: 1},
    ) or {}
    if not user_ftd.get(RECRUITING_ORDERS_WEEK_35_FIELD):
        raise HTTPException(status_code=400, detail="Recruiting orders must be saved before recruiting can run")

    # CPU teams cut ahead of recruiting (real cuts), regardless of the user's choice,
    # so the freed slots are available to the recruiting fill that follows.
    try:
        _apply_cpu_week_35_cuts(fid, excluded_team_id=user_team_id)
    except Exception:
        logger.exception("[WK35-CPU-CUTS] failed; continuing. franchise_id=%s", str(fid))

    results = _run_week_35_signings(franchise_doc)
    season_transition_token = _mint_season_transition_token()
    db.franchises.update_one(
        {"_id": fid},
        {
            "$set": {
                "week": 36,
                "week_35_recruiting_ran": True,
                WEEK_35_RECRUITING_RESULTS_FIELD: results,
                SEASON_TRANSITION_TOKEN_FIELD: season_transition_token,
            }
        },
    )
    return {"status": "success", "week": 36, "results": results}


@router.get("/franchise/debug-names")
def debug_names():
    """Debug endpoint to check if franchise names are loading correctly."""
    from BackEnd.models.franchise_manager import RecruitManager
    rm = RecruitManager(db)
    return {
        "first_names_count": len(rm.first_names),
        "last_names_count": len(rm.last_names),
        "sample_first_names": rm.first_names[:10],
        "sample_last_names": rm.last_names[:10],
        "using_fallback": len(rm.first_names) == 5 and len(rm.last_names) == 5
    }


@router.get("/franchise/latest-training")
def get_latest_training(franchise_id: str):
    """
    Get the latest training session results for display on Training tab.
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    franchise_doc = db.franchises.find_one({"_id": fid}, {"latest_training": 1})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    latest_training = franchise_doc.get("latest_training", {})
    return latest_training if latest_training else {
        "player_logs": {},
        "team_log": {},
        "session_type": "in-season",
        "week": 0
    }


@router.get("/franchise/state")
def get_franchise_state(franchise_id: str, profile: bool = False):
    """
    Get the full franchise document (for loading team data in Command Center).
    Add ?profile=1 to get profile_summary in the response.
    """
    def _build():
        try:
            fid = ObjectId(franchise_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid franchise ID")
        franchise_doc = db.franchises.find_one({"_id": fid}, {"players": 0})
        if not franchise_doc:
            raise HTTPException(status_code=404, detail="Franchise not found")
        fpd_docs = list(franchise_players_data_collection.find(
            {"franchise_id": str(franchise_id)},
            {"player_id": 1, "meta": 1, "season": 1, "career": 1, "attributes": 1, "position_ratings": 1}
        ))
        franchise_doc["players"] = {d["player_id"]: {k: d[k] for k in ["meta", "season", "career", "attributes", "position_ratings"] if k in d} for d in fpd_docs}
        franchise_doc["_id"] = str(franchise_doc["_id"])
        return jsonable_encoder(franchise_doc, custom_encoder={ObjectId: str})
    if profile:
        from BackEnd.utils.profiling import run_profiled
        _out = [None]
        def _wrapped():
            _out[0] = _build()
        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        if isinstance(result, dict):
            result["profile_summary"] = profile_summary
        return result
    return _build()


@router.get("/franchise/team-data")
def get_franchise_team_data(franchise_id: str, team_id: str = None, team_name: str = None):
    """
    Get team data (attributes, plays, scouting_data) from FTD.
    Prefers team_id (ObjectId); falls back to team_name resolution.
    """
    import time
    start_time = time.time()
    # logger.info(f"⏱️ [PERF] /franchise/team-data START - franchise_id={franchise_id}, team_id={team_id}, team_name={team_name}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    franchise_doc = None
    
    # ✅ SS&S: Prefer team_id (ObjectId) if provided
    if team_id:
        try:
            # Validate it's a valid ObjectId
            ObjectId(team_id)
            actual_team_id = team_id
        except Exception:
            # If not a valid ObjectId, try to resolve as team name
            team_doc = db.teams.find_one({"name": team_id})
            if not team_doc:
                raise HTTPException(status_code=404, detail=f"Team not found: {team_id}")
            actual_team_id = str(team_doc["_id"])
    elif team_name:
        # Fallback to team_name resolution for backward compatibility
        team_doc = db.teams.find_one({"name": team_name})
        if not team_doc:
            raise HTTPException(status_code=404, detail="Team not found")
        actual_team_id = str(team_doc["_id"])
    else:
        # Get team name from franchise document if not provided (with backward compatibility)
        # ✅ PERFORMANCE: Load once with projection (only needed fields)
        franchise_doc = db.franchises.find_one(
            {"_id": ObjectId(franchise_id)},
            {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
        )
        if not franchise_doc:
            raise HTTPException(status_code=404, detail="Franchise not found")
        
        user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        team_name = user_team_id
        if not team_name:
            raise HTTPException(status_code=404, detail="Team not found")
        team_doc = db.teams.find_one({"name": team_name})
        if not team_doc:
            raise HTTPException(status_code=404, detail="Team not found")
        actual_team_id = str(team_doc["_id"])
    
    # ✅ FTD: Load team data from FTD collection instead of franchise doc
    from BackEnd.db import franchise_team_data_collection
    
    try:
        team_object_id = ObjectId(actual_team_id)
    except:
        raise HTTPException(status_code=400, detail=f"Invalid team_id format: {actual_team_id}")
    
    ftd_query_start = time.time()
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id}
    )
    ftd_query_time = time.time() - ftd_query_start
    # logger.info(f"⏱️ [PERF] /franchise/team-data FTD query: {ftd_query_time:.3f}s")
    
    if not ftd_doc:
        raise HTTPException(status_code=404, detail=f"Team data not found in FTD for team_id: {actual_team_id}")
    
    # Extract team attributes from FTD
    team_attributes = ftd_doc.get("team_attributes", {})
    # Ensure all expected keys exist (with defaults if missing)
    attr_keys = ['shot_threshold', 'discipline', 'fight', 'rebound_modifier', 
                 'momentum_score', 'offensive_efficiency', 'team_chemistry', 'defensive_efficiency',
                 'fb_efficiency', 'pt_efficiency', 'fb_opp_modifier', 'pt_opp_modifier']
    for key in attr_keys:
        if key not in team_attributes:
            team_attributes[key] = 0  # Default to 0 if not present
    
    # Get plays data from FTD
    plays_data = ftd_doc.get("plays", {})
    
    # 🔍 DEBUG: Log plays with season_stats
    plays_with_season_stats = {name: play for name, play in plays_data.items() if play.get("season_stats", {}).get("times_run", 0) > 0}
    if plays_with_season_stats:
        logger.warning(f"🔍 [TEAM_DATA API] Team {actual_team_id} has {len(plays_with_season_stats)} plays with season_stats: {list(plays_with_season_stats.keys())}")
        for play_name, play_data in list(plays_with_season_stats.items())[:3]:  # Log first 3
            season_stats = play_data.get("season_stats", {})
            logger.warning(f"🔍 [TEAM_DATA API] Play '{play_name}': times_run={season_stats.get('times_run', 0)}, successes={season_stats.get('successes', 0)}, player_points={len(season_stats.get('player_points', {}))} players")
    else:
        logger.warning(f"⚠️ [TEAM_DATA API] Team {actual_team_id} has {len(plays_data)} plays but NONE have season_stats with times_run > 0")
        # Log sample play structure to see what we have
        if plays_data:
            sample_play_name = list(plays_data.keys())[0]
            sample_play = plays_data[sample_play_name]
            logger.warning(f"🔍 [TEAM_DATA API] Sample play '{sample_play_name}' keys: {list(sample_play.keys())}")
            if "season_stats" in sample_play:
                logger.warning(f"🔍 [TEAM_DATA API] Sample play '{sample_play_name}' season_stats keys: {list(sample_play['season_stats'].keys())}")
            else:
                logger.warning(f"⚠️ [TEAM_DATA API] Sample play '{sample_play_name}' has NO season_stats key!")
    
    # Get scouting data from FTD - initialize defense structure if missing
    scouting_data = ftd_doc.get("scouting_data", {})
    if not scouting_data.get("defense"):
        scouting_data["defense"] = {
            "man": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "2-3-zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "3-2-zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "1-3-1-zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0}
        }
    else:
        # Ensure each HCO defense row exists for FCC; dual-read legacy keys (e.g. Man) into canonical slug.
        from BackEnd.utils.defense_identity import read_scouting_defense_row

        defenses = ["man", "2-3-zone", "3-2-zone", "1-3-1-zone"]
        def_block = scouting_data.get("defense")
        if not isinstance(def_block, dict):
            def_block = {}
            scouting_data["defense"] = def_block
        for def_name in defenses:
            if def_name not in def_block:
                row = read_scouting_defense_row(def_block, def_name)
                def_block[def_name] = dict(row) if row else {"effectiveness": 0, "momentum": 0, "cloaking": 0}
            elif "effectiveness" not in def_block[def_name]:
                def_block[def_name]["effectiveness"] = read_scouting_defense_row(def_block, def_name).get(
                    "effectiveness", 0
                ) or 0
    
    total_time = time.time() - start_time
    # logger.info(f"⏱️ [PERF] /franchise/team-data COMPLETE: {total_time:.3f}s")
    return {
        "team_attributes": team_attributes,
        "plays_data": plays_data,
        "scouting_data": scouting_data
    }


@router.get("/franchise/roster")
def get_franchise_roster(franchise_id: str, team_name: str = None):
    """
    Get roster with franchise-specific player attributes.
    """
    import time
    start_time = time.time()
    # logger.info(f"⏱️ [PERF] /franchise/roster START - franchise_id={franchise_id}, team_name={team_name}")
    
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    # ✅ PERFORMANCE: Get team name from franchise document with projection (only user_team fields)
    if not team_name:
        db_query_start = time.time()
        franchise_doc = db.franchises.find_one(
            {"_id": fid},
            {"user_team_id": 1, "user_team_object_id": 1, "_id": 1}
        )
        db_query_time = time.time() - db_query_start
        # logger.info(f"⏱️ [PERF] /franchise/roster DB query 1 (get team name): {db_query_time:.3f}s")
        if franchise_doc:
            user_team_id, _ = get_user_team_from_franchise(franchise_doc)
            team_name = user_team_id
    
    if not team_name:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get team document
    team_query_start = time.time()
    team_doc = db.teams.find_one({"name": team_name})
    team_query_time = time.time() - team_query_start
    # logger.info(f"⏱️ [PERF] /franchise/roster DB query (team doc): {team_query_time:.3f}s")
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_doc["_id"]},
        {"players": 1},
    ) or {}
    team_player_ids = ftd_doc.get("players") or team_doc.get("player_ids", [])
    pid_list = [str(pid) for pid in team_player_ids]
    franchise_query_start = time.time()
    fpd_docs = list(franchise_players_data_collection.find(
        {"franchise_id": str(franchise_id), "player_id": {"$in": pid_list}},
        {"player_id": 1, "meta": 1, "attributes": 1, "position_ratings": 1}
    ))
    franchise_query_time = time.time() - franchise_query_start
    # logger.info(f"⏱️ [PERF] /franchise/roster DB query 2 (FPD): {franchise_query_time:.3f}s")
    franchise_players = {d["player_id"]: d for d in fpd_docs}

    batch_query_start = time.time()
    core_players_dict = {str(p["_id"]): p for p in db.players.find(
        {"_id": {"$in": team_player_ids}},
        {"position_ratings": 1, "height": 1, "weight": 1, "jersey": 1, "year": 1, "attributes": 1}
    )}
    batch_query_time = time.time() - batch_query_start
    # logger.info(f"⏱️ [PERF] /franchise/roster Batch player query ({len(team_player_ids)} players): {batch_query_time:.3f}s")

    processing_start = time.time()
    # Only include players that have FPD (franchise_players); build overrides for shared roster builder
    pids_with_fpd = [pid for pid in team_player_ids if str(pid) in franchise_players]
    mode_overrides = {}
    for pid in pids_with_fpd:
        pid_str = str(pid)
        fpd = franchise_players[pid_str]
        meta = fpd.get("meta", {})
        mode_overrides[pid_str] = {
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "attributes": (fpd.get("attributes") or {}).copy(),
            "position_ratings": fpd.get("position_ratings") or {},
            "height": meta.get("height"),
            "weight": meta.get("weight"),
            "jersey": meta.get("jersey"),
            "year": meta.get("year"),
        }
    players = build_roster_players(pids_with_fpd, mode_overrides, core_players_dict, team_name)
    processing_time = time.time() - processing_start
    # logger.info(f"⏱️ [PERF] /franchise/roster Processing ({len(players)} players): {processing_time:.3f}s")
    
    total_time = time.time() - start_time
    # logger.info(f"⏱️ [PERF] /franchise/roster COMPLETE: {total_time:.3f}s")
    return {"players": players}


@router.post("/franchise/cut-players")
def cut_franchise_players(
    req: CutPlayersRequest,
    user: dict = Depends(get_current_user),
):
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    fid = franchise_doc["_id"]
    user_team_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_name or not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in franchise")

    cut_state = _week_1_cut_requirement(franchise_doc, fid, user_team_object_id)
    if not cut_state.get("cut_required"):
        raise HTTPException(status_code=400, detail="No player cuts are currently required")

    required_cut_count = int(cut_state.get("cut_count", 0) or 0)
    requested_ids = [str(player_id) for player_id in (req.player_ids or []) if player_id]
    if len(requested_ids) != required_cut_count or len(set(requested_ids)) != required_cut_count:
        raise HTTPException(status_code=400, detail=f"You must cut exactly {required_cut_count} players")

    team_object_id = ObjectId(user_team_object_id)
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {"players": 1, "scholarship_players": 1, "training_squad_players": 1, "playing_time_promise_players": 1},
    ) or {}
    roster_player_ids = [str(player_id) for player_id in (ftd_doc.get("players") or []) if player_id]
    if not set(requested_ids).issubset(set(roster_player_ids)):
        raise HTTPException(status_code=400, detail="One or more selected players are not on your roster")

    fpd_map = _load_fpd_map(fid, roster_player_ids)
    cut_names = []
    for player_id in requested_ids:
        fpd_doc = fpd_map.get(player_id) or {}
        meta = (fpd_doc.get("meta") or {})
        name = " ".join(part for part in [meta.get("first_name", ""), meta.get("last_name", "")] if part).strip() or player_id
        cut_names.append(name)

    # The selected players move to the training squad — they are NOT cut/deleted.
    # `players` becomes the 12-man active roster; training_squad holds the rest
    # (ineligible to play, retained in FPD, available again next Training Camp).
    remaining_roster_ids = [player_id for player_id in roster_player_ids if player_id not in set(requested_ids)]
    if len(remaining_roster_ids) != 12:
        raise HTTPException(status_code=400, detail="You must leave exactly 12 active players")

    existing_training_squad = [
        str(player_id) for player_id in (ftd_doc.get("training_squad_players") or []) if player_id
    ]
    new_training_squad = existing_training_squad + [
        pid for pid in requested_ids if pid not in existing_training_squad
    ]
    remaining_scholarships = [
        str(player_id) for player_id in (ftd_doc.get("scholarship_players") or [])
        if str(player_id) in remaining_roster_ids
    ]
    remaining_ptp = [
        str(player_id) for player_id in (ftd_doc.get("playing_time_promise_players") or [])
        if str(player_id) in remaining_roster_ids
    ]

    total_player_attrs = sum(
        core_total_player_attrs((fpd_map.get(player_id) or {}).get("attributes") or {})
        for player_id in remaining_roster_ids
    )
    _update_ftd_roster_state(
        fid,
        team_object_id,
        {
            "players": remaining_roster_ids,
            "scholarship_players": remaining_scholarships,
            "training_squad_players": new_training_squad,
            "playing_time_promise_players": remaining_ptp,
            "total_player_attrs": total_player_attrs,
            "updated_at": datetime.utcnow(),
        },
    )

    ps_initialized = False
    if int(franchise_doc.get("week", 1) or 1) == 1:
        ps_initialized = (
            _maybe_initialize_practice_squad_week_1(
                fid,
                franchise_doc,
                user_team_object_id=user_team_object_id,
                defer_if_user_cut_pending=False,
            )
            is not None
        )

    return {
        "status": "success",
        "cut_count": required_cut_count,
        "cut_names": cut_names,
        "remaining_roster_count": len(remaining_roster_ids),
        "practice_squad_initialized": ps_initialized,
    }


def _hard_release_players(fid: ObjectId, team_object_id: Any, release_ids) -> int:
    """Permanently release players: strip from every FTD roster list AND delete their
    FPD docs (the real week-35 cut — distinct from training-squad assignment)."""
    release_set = {str(p) for p in (release_ids or []) if p}
    if not release_set:
        return 0
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {"players": 1, "scholarship_players": 1, "training_squad_players": 1, "playing_time_promise_players": 1},
    ) or {}

    def _strip(field: str) -> list[str]:
        return [str(p) for p in (ftd_doc.get(field) or []) if p and str(p) not in release_set]

    remaining_players = _strip("players")
    fpd_map = _load_fpd_map(fid, remaining_players)
    total_player_attrs = sum(
        core_total_player_attrs((fpd_map.get(pid) or {}).get("attributes") or {})
        for pid in remaining_players
    )
    _update_ftd_roster_state(
        fid,
        team_object_id,
        {
            "players": remaining_players,
            "scholarship_players": _strip("scholarship_players"),
            "training_squad_players": _strip("training_squad_players"),
            "playing_time_promise_players": _strip("playing_time_promise_players"),
            "total_player_attrs": total_player_attrs,
            "updated_at": datetime.utcnow(),
        },
    )
    franchise_players_data_collection.delete_many(
        {"franchise_id": str(fid), "player_id": {"$in": list(release_set)}}
    )
    return len(release_set)


def _apply_cpu_week_35_cuts(fid: ObjectId, excluded_team_id: Any = None) -> None:
    """Week-35 real cuts for CPU teams ahead of recruiting. Rolls each player's best-RT:
    RT<10 → 100% cut, RT<15 → 50%, RT<20 → 25%. Applies to active + training-squad."""
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": fid},
        {"team_id": 1, "players": 1, "training_squad_players": 1},
    ))
    all_ids: list[str] = []
    for d in ftd_docs:
        all_ids += [str(p) for p in (d.get("players") or []) if p]
        all_ids += [str(p) for p in (d.get("training_squad_players") or []) if p]
    if not all_ids:
        return
    fpd_map = _load_fpd_map(fid, all_ids)
    for d in ftd_docs:
        team_id = d.get("team_id")
        if not team_id or (excluded_team_id and str(team_id) == str(excluded_team_id)):
            continue
        candidates = (
            [str(p) for p in (d.get("players") or []) if p]
            + [str(p) for p in (d.get("training_squad_players") or []) if p]
        )
        to_cut: list[str] = []
        for pid in candidates:
            rt = int(_best_position((fpd_map.get(pid) or {}).get("position_ratings") or {}).get("rating") or 0)
            if rt < 10:
                chance = 1.0
            elif rt < 15:
                chance = 0.5
            elif rt < 20:
                chance = 0.25
            else:
                chance = 0.0
            if chance > 0 and random.random() < chance:
                to_cut.append(pid)
        if to_cut:
            _hard_release_players(fid, team_id, to_cut)


@router.post("/franchise/cut-players-final")
def cut_franchise_players_final(
    req: CutPlayersRequest,
    user: dict = Depends(get_current_user),
):
    """Week-35 real cuts (FPD deleted, removed from all team lists). Any number incl. 0."""
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    fid = franchise_doc["_id"]
    if int(franchise_doc.get("week", 1) or 1) != 35:
        raise HTTPException(status_code=400, detail="Final cuts can only run during week 35")
    if franchise_doc.get("week_35_recruiting_ran"):
        raise HTTPException(status_code=400, detail="Recruiting has already run for this season")
    _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in franchise")
    team_object_id = ObjectId(user_team_object_id)
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {"players": 1, "training_squad_players": 1},
    ) or {}
    roster_set = (
        {str(p) for p in (ftd_doc.get("players") or []) if p}
        | {str(p) for p in (ftd_doc.get("training_squad_players") or []) if p}
    )
    requested = [str(p) for p in (req.player_ids or []) if p and str(p) in roster_set]
    fpd_map = _load_fpd_map(fid, requested)
    cut_names = []
    for pid in requested:
        meta = (fpd_map.get(pid) or {}).get("meta") or {}
        cut_names.append(
            " ".join(x for x in [meta.get("first_name", ""), meta.get("last_name", "")] if x).strip() or pid
        )
    _hard_release_players(fid, team_object_id, requested)
    return {"status": "success", "cut_count": len(requested), "cut_names": cut_names}


@router.get("/franchise/training-squad-reports")
def get_training_squad_reports(franchise_id: str, user: dict = Depends(get_current_user)):
    """Stored Training Squad Development reports (user team), newest week first."""
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    reports = franchise_doc.get("training_squad_reports") or {}
    ordered = [reports[k] for k in sorted(reports.keys(), key=lambda x: int(x), reverse=True)]
    return {"reports": ordered, "attr_keys": TRAINING_SQUAD_ATTR_KEYS}


def _scouting_usage_unlocks_for_week(current_week: int, user_film_study: int) -> tuple[bool, bool]:
    """Return (base_play_usage_unlocked, extended_usage_unlocked) for FCC scouting."""
    if 27 <= int(current_week or 0) <= 34:
        return True, True
    film_study = int(user_film_study or 0)
    return film_study > 0, film_study > 1


@router.get("/franchise/scouting-report")
def get_scouting_report(franchise_id: str, team_name: str):
    """
    Get scouting report for a team, including last game's play usage data.
    
    Returns:
    - team_attributes: Team attribute values
    - plays: Array of plays with game_stats from last completed game
    """
    try:
        fid = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID")
    
    # Get franchise document
    franchise_doc = db.franchises.find_one({"_id": fid})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    
    # Get team document to resolve ObjectId
    team_doc = db.teams.find_one({"name": team_name})
    if not team_doc:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team_object_id = team_doc["_id"]  # Keep as ObjectId for FTD query
    
    # Get team_id field for querying games (e.g., "XAVIEN")
    team_id_field = team_doc.get("team_id")
    
    # ✅ FTD: Get team attributes from FTD collection instead of franchise doc
    from BackEnd.db import franchise_team_data_collection
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {"team_attributes": 1}
    )
    
    if not ftd_doc:
        raise HTTPException(status_code=404, detail=f"Team data not found in FTD for team_id: {team_object_id}")
    
    team_attributes = ftd_doc.get("team_attributes", {})
    
    # Find last completed game for this team
    # Match against home_team_id and away_team_id (which are team_id strings like "XAVIEN")
    last_game = db.games.find_one(
        {
            "franchise_id": str(franchise_id),
            "$or": [
                {"home_team_id": team_id_field},
                {"away_team_id": team_id_field}
            ]
        },
        sort=[("_id", -1)]  # Most recent first
    )
    
    # ✅ SS&S: Use shared utility function to extract plays from game document
    from BackEnd.utils.scouting_utils import extract_plays_from_game_document
    plays_data = extract_plays_from_game_document(
        last_game,
        team_name,
        str(team_object_id),  # Convert to string for utility function
        team_id_field
    )

    from BackEnd.utils.roster_loader import load_roster
    from BackEnd.utils.scouting_utils import build_enriched_projected_starting_five

    _, scout_players = load_roster(team_name, franchise_id=str(franchise_id))

    team_oid_str = str(team_object_id)
    player_season_stats: dict[str, dict] = {}
    for fpd in franchise_players_data_collection.find(
        {
            "franchise_id": str(franchise_id),
            "$or": [
                {"meta.team_id": team_oid_str},
                {"meta.team": team_name},
            ],
        },
        {"player_id": 1, "season": 1},
    ):
        pid = str(fpd.get("player_id") or "")
        if not pid:
            continue
        season_raw = fpd.get("season") or {}
        if isinstance(season_raw, dict):
            player_season_stats[pid] = dict(season_raw)

    projected_starting_five = build_enriched_projected_starting_five(
        scout_players, player_season_stats
    )

    # Play Usage gate: regular-season prior-game usage is revealed by the USER's
    # Film Study allocation for that week. EOS tournament weeks 27-34 do not run
    # training, so all scouting usage panels are visible.
    current_week = int(franchise_doc.get("week", 1) or 1)
    _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    user_film_study = 0
    if user_team_object_id:
        try:
            user_ftd = franchise_team_data_collection.find_one(
                {"franchise_id": fid, "team_id": ObjectId(user_team_object_id)},
                {f"training_reports.{current_week}.general.film_study": 1},
            )
            user_film_study = int(
                (((user_ftd or {}).get("training_reports", {}) or {})
                 .get(str(current_week), {}) or {})
                .get("general", {}).get("film_study", 0) or 0
            )
        except Exception:
            user_film_study = 0
    play_usage_unlocked, extended_usage_unlocked = _scouting_usage_unlocks_for_week(
        current_week,
        user_film_study,
    )
    if not play_usage_unlocked:
        plays_data = []

    # Fast Break (offense) and HCT trap (defense) play usage unlock at a higher
    # Film Study tier (> 1) in regular-season weeks. Tournament weeks bypass this
    # gate because there is no weekly training.
    from BackEnd.utils.scouting_utils import extract_play_counters_from_game_document
    from BackEnd.constants.fast_break_play_types import FAST_BREAK_PLAY_LABELS
    from BackEnd.constants.hct_trap_play_types import HCT_TRAP_PLAY_LABELS
    fast_break_plays: list = []
    hct_trap_plays: list = []
    if extended_usage_unlocked:
        fast_break_plays = extract_play_counters_from_game_document(
            last_game, team_name, str(team_object_id), team_id_field,
            side="offense", subkey="fast_break_plays", label_map=FAST_BREAK_PLAY_LABELS,
        )
        hct_trap_plays = extract_play_counters_from_game_document(
            last_game, team_name, str(team_object_id), team_id_field,
            side="defense", subkey="hct_trap_plays", label_map=HCT_TRAP_PLAY_LABELS,
        )

    return {
        "team_attributes": team_attributes,
        "plays": plays_data,
        "projected_starting_five": projected_starting_five,
        "player_season_stats": player_season_stats,
        "play_usage_unlocked": play_usage_unlocked,
        "fast_break_plays": fast_break_plays,
        "hct_trap_plays": hct_trap_plays,
        "fast_break_usage_unlocked": extended_usage_unlocked,
        "hct_usage_unlocked": extended_usage_unlocked,
    }


class FranchiseTrainingRequest(BaseModel):
    franchise_id: str
    team_id: Optional[str] = None
    training_data: dict  # Contains player_drills, team_drills, general, coaching_focus


class FranchiseDistantTrainingRequest(BaseModel):
    franchise_id: str


def _apply_franchise_distant_cpu_training(
    franchise_id: ObjectId,
    *,
    franchise_doc: dict,
    user_team_id_str: str,
    week: int,
    is_first_training: bool,
    franchise_players: dict,
) -> None:
    """Template-based distant CPU training for all non-user FTDs. Idempotent per FTD via cpu_distant_trained_week."""
    all_ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id}))
    training_type = "tc" if is_first_training else "regular"
    eliminated_team_ids = set()
    if week > ScheduleManager.REGULAR_SEASON_WEEKS and franchise_doc.get("eos_tournament_active"):
        eliminated_team_ids = ft.get_eliminated_team_ids(franchise_doc)
    distant_templates = list(db["distant_training"].find({"training_type": training_type}))
    if not distant_templates:
        logger.warning(
            f"⚠️ [DISTANT TRAINING] No templates found for training_type={training_type}, skipping computer teams"
        )
        return
    for ftd_doc in all_ftd_docs:
        computer_team_oid = ftd_doc.get("team_id")
        if computer_team_oid is None:
            continue
        computer_team_id_str = str(computer_team_oid)
        if computer_team_id_str == str(user_team_id_str):
            continue
        if computer_team_id_str in eliminated_team_ids:
            continue
        if int(ftd_doc.get("cpu_distant_trained_week") or 0) == week:
            continue
        try:
            template = random.choice(distant_templates)
            team_values = template.get("team_values", {})
            players_template = template.get("players", {})
            current_team_attrs = ftd_doc.get("team_attributes", {})
            ftd_update = {}
            for attr_name, delta in team_values.items():
                if attr_name not in TEAM_ATTR_CLAMPS:
                    continue
                current = current_team_attrs.get(attr_name, 0)
                if isinstance(current, (int, float)) and isinstance(delta, (int, float)):
                    lower, upper = TEAM_ATTR_CLAMPS[attr_name]
                    delta_val = float(delta) if attr_name == "rebound_modifier" else int(delta)
                    new_val = current + delta_val
                    if upper is not None:
                        new_val = max(lower, min(upper, new_val))
                    else:
                        new_val = max(lower, new_val)
                    if attr_name == "rebound_modifier":
                        new_val = round(new_val, 2)
                    else:
                        new_val = int(round(new_val))
                    ftd_update[f"team_attributes.{attr_name}"] = new_val
            set_payload = dict(ftd_update)
            if template.get("community_engagement"):
                set_payload["pending_community_engagement"] = True
            if set_payload:
                franchise_team_data_collection.update_one(
                    {"franchise_id": franchise_id, "team_id": computer_team_oid},
                    {"$set": set_payload},
                )
            player_order = ftd_doc.get("players")
            if not player_order:
                team_doc = db.teams.find_one({"_id": computer_team_oid}, {"player_ids": 1})
                player_order = [str(pid) for pid in (team_doc.get("player_ids") or [])] if team_doc else []
            else:
                player_order = [str(pid) for pid in player_order]
            for i in range(min(12, len(player_order))):
                pid = player_order[i]
                player_key = f"player_{i}"
                if player_key not in players_template:
                    continue
                fpd = franchise_players.get(pid)
                if not fpd:
                    continue
                deltas = players_template[player_key]
                current_attrs = fpd.get("attributes", {})
                fpd_set = {}
                for attr_name, delta in deltas.items():
                    if not isinstance(delta, (int, float)):
                        continue
                    current = current_attrs.get(attr_name, 0) or current_attrs.get(f"anchor_{attr_name}", 0)
                    try:
                        cur = int(current) if isinstance(current, (int, float)) else 0
                    except (TypeError, ValueError):
                        cur = 0
                    new_val = cur + int(delta)
                    new_val = max(PLAYER_ATTR_CLAMP[0], new_val)
                    fpd_set[f"attributes.{attr_name}"] = new_val
                    fpd_set[f"attributes.anchor_{attr_name}"] = new_val
                if fpd_set:
                    franchise_players_data_collection.update_one(
                        {"franchise_id": str(franchise_id), "player_id": pid},
                        {"$set": fpd_set},
                    )
                core_player = db.players.find_one({"_id": pid}, {"height": 1})
                height = core_player.get("height") if core_player else None
                updated_attrs = dict(current_attrs)
                for k, v in fpd_set.items():
                    if k.startswith("attributes."):
                        updated_attrs[k.replace("attributes.", "")] = v
                meta = fpd.get("meta", {})
                player_for_ratings = {
                    "attributes": updated_attrs,
                    "height": height,
                    "name": f"{meta.get('first_name', '')} {meta.get('last_name', '')}",
                }
                new_ratings = compute_position_ratings(player_for_ratings)
                franchise_players_data_collection.update_one(
                    {"franchise_id": str(franchise_id), "player_id": pid},
                    {"$set": {"position_ratings": new_ratings}},
                )
            franchise_team_data_collection.update_one(
                {"franchise_id": franchise_id, "team_id": computer_team_oid},
                {"$set": {"cpu_distant_trained_week": week}},
            )
            logger.info(f"✅ [DISTANT TRAINING] Applied template for team_id={computer_team_id_str}")
        except Exception as e:
            logger.error(f"❌ [DISTANT TRAINING] Error for team_id={computer_team_id_str}: {e}", exc_info=True)
            continue


def _franchise_training_distant_phase_only(franchise_id_str: str) -> dict:
    """Finish franchise week training: distant CPU teams + optional camp cuts + training_completed."""
    try:
        franchise_id = ObjectId(franchise_id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    training_status = franchise_doc.get("training_status", {}) or {}
    week = int(franchise_doc.get("week", 1) or 1)
    results = franchise_doc.get("results", {})
    is_first_training = (week == 1 and not results.get("1"))

    if _postseason_training_disabled_for_week(week):
        raise HTTPException(
            status_code=400,
            detail="Training is disabled during postseason tournament weeks.",
        )

    if franchise_training_fully_complete_for_week(training_status, week):
        user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        redirect_team_id = user_team_object_id if user_team_object_id else None
        return {
            "status": "already_completed",
            "week": week,
            "redirect": f"/training-report.html?mode=franchise&franchise_id={franchise_id_str}&team_id={redirect_team_id}&week={week}&from=training",
        }

    if not franchise_user_training_applied_for_week(training_status, week):
        raise HTTPException(
            status_code=400,
            detail="User training has not been applied for this week. Complete the training screen first.",
        )

    if int(training_status.get("cpu_distant_complete_week") or 0) == week:
        db.franchises.update_one(
            {"_id": franchise_id},
            {
                "$set": {
                    "training_status.training_completed": True,
                    "training_status.week": week,
                    "training_status.last_training_date": datetime.now().strftime("%Y-%m-%d"),
                }
            },
        )
        user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        team_id = user_team_object_id
        session_type = training_status.get("session_type", "in-season")
        return {
            "status": "success",
            "week": week,
            "session_type": session_type,
            "redirect": f"/training-report.html?mode=franchise&franchise_id={franchise_id_str}&team_id={team_id}&week={week}&from=training",
        }

    user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id_name or not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in franchise document")
    team_id = user_team_object_id

    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": franchise_id_str}))
    franchise_players = {d["player_id"]: d for d in fpd_docs}

    _apply_franchise_distant_cpu_training(
        franchise_id,
        franchise_doc=franchise_doc,
        user_team_id_str=str(team_id),
        week=week,
        is_first_training=is_first_training,
        franchise_players=franchise_players,
    )

    cuts_ran_this_call = False
    if is_first_training and not bool(training_status.get("cpu_training_camp_cuts_applied")):
        _apply_cpu_training_camp_cuts(franchise_id, excluded_team_id=str(team_id))
        cuts_ran_this_call = True

    ps_fields: dict[str, Any] = {}
    season_news_prepend: list[dict[str, Any]] = []
    camp_done = cuts_ran_this_call or bool(training_status.get("cpu_training_camp_cuts_applied"))

    if camp_done:
        ps_state = _maybe_initialize_practice_squad_week_1(
            franchise_id,
            franchise_doc,
            user_team_object_id=team_id,
            defer_if_user_cut_pending=True,
        )
        if ps_state:
            ps_fields["practice_squad"] = ps_state

    if week >= 2 and week <= 19 and (franchise_doc.get("practice_squad") or {}).get("initialized"):
        from BackEnd.practice_squad.manager import run_practice_squad_week

        ps_state = run_practice_squad_week(franchise_id, franchise_doc, week)
        ps_fields["practice_squad"] = ps_state
        franchise_doc["practice_squad"] = ps_state
        ps_results_story = _build_ps_game_results_news_story(franchise_doc, week, franchise_id)
        if ps_results_story:
            season_news_prepend.append(ps_results_story)

    session_type = training_status.get("session_type", "in-season")
    distant_update: dict[str, Any] = {
        "training_status.training_completed": True,
        "training_status.cpu_distant_complete_week": week,
        "training_status.last_training_date": datetime.now().strftime("%Y-%m-%d"),
    }
    if cuts_ran_this_call:
        distant_update["training_status.cpu_training_camp_cuts_applied"] = True
    distant_update.update(ps_fields)
    if season_news_prepend:
        _prepend_season_news_stories(franchise_doc, season_news_prepend)
        distant_update["season_news"] = franchise_doc["season_news"]
    db.franchises.update_one({"_id": franchise_id}, {"$set": distant_update})
    return {
        "status": "success",
        "week": week,
        "session_type": session_type,
        "redirect": f"/training-report.html?mode=franchise&franchise_id={franchise_id_str}&team_id={team_id}&week={week}&from=training",
    }


def _max_position_rating_from_fpd(fpd: dict) -> int:
    """Highest position rating (PG/SG/SF/PF/C) for sort order (custom modal + training report)."""
    pr = (fpd or {}).get("position_ratings") or {}
    best = 0
    for v in pr.values():
        try:
            iv = int(float(v))
        except (TypeError, ValueError):
            continue
        if iv > best:
            best = iv
    return best


def _sort_training_report_players_by_max_rt(players: List[dict]) -> None:
    """In-place: descending max(RT), stable by original index on tie."""

    def max_rt(p: dict) -> float:
        pr = p.get("position_ratings") or {}
        vals = []
        for v in pr.values():
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                pass
        return max(vals) if vals else 0.0

    decorated = [(max_rt(p), i, p) for i, p in enumerate(players)]
    decorated.sort(key=lambda t: (-t[0], t[1]))
    players[:] = [t[2] for t in decorated]


def _build_custom_focus_roster_for_franchise(
    franchise_doc: dict,
    franchise_id_obj: ObjectId,
) -> Tuple[List[dict], List[str]]:
    """
    Rows for the Player Maximizer Custom modal: same roster order as franchise training execution.
    """
    from BackEnd.models.training_execution_v2 import PLAYER_MAXIMIZER_RANKING_ATTRS

    ranking = list(PLAYER_MAXIMIZER_RANKING_ATTRS)
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id or not user_team_object_id:
        return [], ranking

    fpd_docs = list(
        franchise_players_data_collection.find({"franchise_id": str(franchise_id_obj)})
    )
    franchise_players = {d["player_id"]: d for d in fpd_docs}

    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id_obj, "team_id": ObjectId(user_team_object_id)}
    )
    if not ftd_doc:
        return [], ranking

    team_player_ids = ftd_doc.get("players") or []
    rows: List[dict] = []
    for pid in team_player_ids:
        pid_str = str(pid)
        fpd = franchise_players.get(pid_str)
        if not fpd:
            continue
        meta = fpd.get("meta") or {}
        name = " ".join(
            p for p in [meta.get("first_name", ""), meta.get("last_name", "")] if p
        ).strip() or pid_str
        attrs_obj = fpd.get("attributes") or {}
        attr_vals = {}
        for a in ranking:
            attr_vals[a] = int(attrs_obj.get(f"anchor_{a}", attrs_obj.get(a, 0)) or 0)
        pr_raw = fpd.get("position_ratings") or {}
        position_ratings = (
            {str(k): v for k, v in pr_raw.items()} if isinstance(pr_raw, dict) else {}
        )
        rows.append(
            {
                "player_id": pid_str,
                "name": name,
                "attrs": attr_vals,
                "position_ratings": position_ratings,
                "_sort_max_rt": _max_position_rating_from_fpd(fpd),
            }
        )
    rows.sort(key=lambda r: r.get("_sort_max_rt", 0), reverse=True)
    for r in rows:
        r.pop("_sort_max_rt", None)
    return rows, ranking


@router.get("/franchise/training-points")
def get_training_points(franchise_id: str):
    """
    Get the number of training points available for a franchise.
    Returns 30 for first training (before first game), 24 otherwise.
    """
    import time
    endpoint_start = time.time()
    
    try:
        franchise_id_obj = ObjectId(franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID format")

    franchise_query_start = time.time()
    franchise_doc = db.franchises.find_one({"_id": franchise_id_obj})
    franchise_query_time = (time.time() - franchise_query_start) * 1000
    # logger.warning(f"⏱️ [DB TIMING] get_training_points: franchises.find_one(franchise_id={franchise_id}): {franchise_query_time:.2f}ms")
    
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    # Check if it's first training (training camp) - week 1 and no results yet
    week = franchise_doc.get("week", 1)
    results = franchise_doc.get("results", {})
    is_first_training = (week == 1 and not results.get("1"))
    
    # First training (training camp) gets 30 points, otherwise 24
    training_points = 30 if is_first_training else 24
    
    total_time = (time.time() - endpoint_start) * 1000
    # logger.warning(f"⏱️ [DB TIMING] get_training_points TOTAL: {total_time:.2f}ms, training_points={training_points}, is_first_training={is_first_training}")
    
    custom_roster, ranking_attrs = _build_custom_focus_roster_for_franchise(
        franchise_doc, franchise_id_obj
    )

    return {
        "training_points": training_points,
        "is_first_training": is_first_training,
        "week": week,
        "user_team_name": franchise_doc.get("user_team_id"),
        "custom_focus_roster": custom_roster,
        "player_maximizer_ranking_attrs": ranking_attrs,
    }


@router.post("/franchise/run-training")
def run_franchise_training(req: FranchiseTrainingRequest, profile: bool = False):
    """
    Run training for a franchise team using franchise-specific player/team attributes.
    Updates only the franchise document, not the core collections.
    Add ?profile=1 to get a profile_summary in the response.
    """
    import time
    if profile:
        from BackEnd.utils.profiling import run_profiled
        _out = [None]
        def _wrapped():
            _out[0] = _run_franchise_training_impl(req)
        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        if isinstance(result, dict):
            result["profile_summary"] = profile_summary
        return result
    return _run_franchise_training_impl(req)


@router.post("/franchise/run-training/user")
def run_franchise_training_user(
    req: FranchiseTrainingRequest,
    user: dict = Depends(get_current_user),
    profile: bool = False,
):
    """Persist user-team training only. Client should call /franchise/run-training/distant-cpu next."""
    verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    if profile:
        from BackEnd.utils.profiling import run_profiled

        _out = [None]

        def _wrapped():
            _out[0] = _run_franchise_training_impl(req, phase="user_only")

        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        if isinstance(result, dict):
            result["profile_summary"] = profile_summary
        return result
    return _run_franchise_training_impl(req, phase="user_only")


@router.post("/franchise/run-training/distant-cpu")
def run_franchise_training_distant_cpu(
    req: FranchiseDistantTrainingRequest,
    user: dict = Depends(get_current_user),
    profile: bool = False,
):
    """Apply distant CPU template training, camp cuts (week 1), and set training_completed."""
    verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    if profile:
        from BackEnd.utils.profiling import run_profiled

        _out = [None]

        def _wrapped():
            _out[0] = _franchise_training_distant_phase_only(req.franchise_id)

        profile_summary = run_profiled(_wrapped, top_n=60)
        result = _out[0]
        if isinstance(result, dict):
            result["profile_summary"] = profile_summary
        return result
    return _franchise_training_distant_phase_only(req.franchise_id)


def _run_franchise_training_impl(req: FranchiseTrainingRequest, *, phase: str = "full"):
    """Inner implementation so run_franchise_training can be profiled with ?profile=1."""
    import time

    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise ID format")

    # Load franchise document
    franchise_query_start = time.time()
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    franchise_query_time = (time.time() - franchise_query_start) * 1000
    # logger.warning(f"⏱️ [DB TIMING] run_franchise_training: franchises.find_one(franchise_id={req.franchise_id}): {franchise_query_time:.2f}ms")
    
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    training_status = franchise_doc.get("training_status", {}) or {}
    try:
        week = int(franchise_doc.get("week", 1) or 1)
    except (TypeError, ValueError):
        week = 1
    results = franchise_doc.get("results", {})

    if _postseason_training_disabled_for_week(week):
        raise HTTPException(
            status_code=400,
            detail="Training is disabled during postseason tournament weeks.",
        )
    
    # Check if it's first training (training camp) - week 1 and no results yet
    is_first_training = (week == 1 and not results.get("1"))
    expected_points = 30 if is_first_training else 24
    recruiting_results = franchise_doc.get("recruiting_results", {}) or {}

    if 20 <= week <= 26 and str(week) not in recruiting_results:
        _, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        if not user_team_object_id:
            raise HTTPException(status_code=404, detail="User team not found in franchise document")
        if week == 20:
            user_ftd = franchise_team_data_collection.find_one(
                {"franchise_id": franchise_id, "team_id": ObjectId(user_team_object_id)},
                {"Recruits": 1},
            ) or {}
            if not _team_order_list(user_ftd.get("Recruits")):
                raise HTTPException(
                    status_code=400,
                    detail="You must save recruiting orders before running training in week 20",
                )

    if phase == "full":
        if franchise_training_fully_complete_for_week(training_status, week):
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
            redirect_team_id = user_team_object_id if user_team_object_id else req.team_id
            return {
                "status": "already_completed",
                "week": week,
                "redirect": f"/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={redirect_team_id}&week={week}&from=training",
            }
        if franchise_user_training_applied_for_week(training_status, week) and int(
            training_status.get("cpu_distant_complete_week") or 0
        ) != week:
            return _franchise_training_distant_phase_only(req.franchise_id)
    elif phase == "user_only":
        if franchise_training_fully_complete_for_week(training_status, week):
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
            redirect_team_id = user_team_object_id if user_team_object_id else req.team_id
            return {
                "status": "already_completed",
                "week": week,
                "redirect": f"/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={redirect_team_id}&week={week}&from=training",
            }
        if franchise_user_training_applied_for_week(training_status, week):
            lt = franchise_doc.get("latest_training") or {}
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
            ftd_override = lt.get("ftd_coaching_focus")
            if not isinstance(ftd_override, dict):
                ftd_row = franchise_team_data_collection.find_one(
                    {"franchise_id": franchise_id, "team_id": ObjectId(user_team_object_id)},
                    {"coaching_focus": 1},
                ) or {}
                raw_cf = ftd_row.get("coaching_focus") or {}
                ftd_override = {
                    k: int(raw_cf.get(k, 0) or 0) for k in COACHING_FOCUS_FTD_COUNT_KEYS
                }
            return {
                "status": "user_training_already_applied",
                "week": week,
                "training_highlights": build_training_loading_highlights(
                    lt, ftd_coaching_focus=ftd_override
                ),
                "team_id": user_team_object_id,
                "redirect": None,
            }
    else:
        raise HTTPException(status_code=400, detail="Invalid training phase")
    
    # Validate total training points allocated
    training_data = req.training_data
    allocations = {
        "player_drills": training_data.get("player_drills", {}),
        "team_drills": training_data.get("team_drills", {}),
        "general": training_data.get("general", {})
    }
    
    # Calculate total points allocated
    total_allocated = 0
    for category in allocations.values():
        if isinstance(category, dict):
            for value in category.values():
                if isinstance(value, dict):
                    total_allocated += sum(value.values())
                elif isinstance(value, (int, float)):
                    total_allocated += value
    
    if total_allocated != expected_points:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid training points allocation. Expected {expected_points} points, got {total_allocated}."
        )

    # ✅ SS&S: Always use user_team_object_id from franchise document as source of truth
    # This ensures we're always using the correct team, even if URL params are wrong
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id or not user_team_object_id:
        raise HTTPException(status_code=404, detail="User team not found in franchise document")

    if week > ScheduleManager.REGULAR_SEASON_WEEKS and franchise_doc.get("eos_tournament_active"):
        eos_status = _get_user_eos_phase_status(franchise_doc, str(user_team_object_id), week)
        if eos_status.get("eliminated_from_current_phase"):
            raise HTTPException(
                status_code=400,
                detail="Training is disabled for the current EOS phase after elimination.",
            )
        if eos_status.get("has_bye_this_week"):
            raise HTTPException(
                status_code=400,
                detail="Training is not available during an EOS bye week.",
            )
    
    # Use franchise document's user_team_object_id as authoritative team_id
    team_id = user_team_object_id
    team_name = user_team_id
    
    # Verify team exists in teams collection
    team_doc = db.teams.find_one({"_id": ObjectId(team_id)})
    if not team_doc:
        raise HTTPException(status_code=404, detail=f"Team not found: {team_id}")
    team_object_id = team_doc["_id"]
    
    # Log if req.team_id was provided but doesn't match (for debugging)
    if req.team_id and req.team_id != team_id:
        logger.warning(f"⚠️ [TRAINING] Request team_id ({req.team_id}) doesn't match franchise document user_team_object_id ({team_id}). Using franchise document value.")

    # ✅ FPD: Load franchise player data from franchise_players_data (not franchise.players)
    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(req.franchise_id)}))
    franchise_players = {d["player_id"]: d for d in fpd_docs}

    # ✅ FTD: Use franchise roster order instead of universal team.player_ids
    ftd_doc = franchise_team_data_collection.find_one(
        {"franchise_id": franchise_id, "team_id": ObjectId(team_id)}
    )
    if not ftd_doc:
        raise HTTPException(status_code=404, detail=f"Team data not found in FTD for team_id: {team_id}")

    team_player_ids = ftd_doc.get("players") or team_doc.get("player_ids", [])
    if not team_player_ids:
        raise HTTPException(status_code=404, detail=f"No player_ids on team for team_id: {team_id}")

    # Core players height/weight when FPD meta omitted them (lazy FPD insert, legacy rows).
    roster_ids_for_core = [pid for pid in team_player_ids if franchise_players.get(str(pid), {})]
    core_physique_by_id: dict[str, dict] = {}
    if roster_ids_for_core:
        for doc in db.players.find(
            {"_id": {"$in": roster_ids_for_core}},
            {"height": 1, "weight": 1},
        ):
            core_physique_by_id[str(doc["_id"])] = doc

    # Build player list with franchise-specific attributes
    players_load_start = time.time()
    players_for_training = []
    for pid in team_player_ids:
        pid_str = str(pid)
        franchise_player_data = franchise_players.get(pid_str, {})
        if not franchise_player_data:
            continue

        meta_src = franchise_player_data.get("meta", {})
        meta = dict(meta_src) if isinstance(meta_src, dict) else {}
        core_doc = core_physique_by_id.get(pid_str) or {}
        if meta.get("height") is None and core_doc.get("height") is not None:
            meta["height"] = core_doc["height"]
        if meta.get("weight") is None and core_doc.get("weight") is not None:
            meta["weight"] = core_doc["weight"]

        # Build player dict for training
        player = {
            "_id": pid_str,
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "team": team_name or team_id,  # Use team_name if available, otherwise use team_id
            "attributes": franchise_player_data.get("attributes", {}),
            "position_ratings": franchise_player_data.get("position_ratings", {}),
            "year": meta.get("year"),
            "meta": meta,
        }
        players_for_training.append(player)

    if not players_for_training:
        raise HTTPException(status_code=404, detail="No players found for training")
    
    # Get team stats (team_attributes) from FTD
    team_stats = ftd_doc.get("team_attributes", {}).copy()
    
    # Extract training data
    training_data = req.training_data
    
    # ✅ FTD: Get plays, game plan settings, and playbook settings from FTD
    # These are the LATEST settings saved from Game Plan and Playbooks screens
    # When playbook_training_mode == "current-playbooks", these settings will be used
    plays_data = ftd_doc.get("plays", {})
    strategy_settings = ftd_doc.get("strategy_settings", {})
    playbook_settings = ftd_doc.get("playbook_settings", {})
    scouting_data = ftd_doc.get("scouting_data", {})
    
    # 🔍 DEBUG: Log settings loaded for training
    logger.warning(f"🔍 [TRAINING DEBUG] team_id used: {team_id}")
    logger.warning(f"🔍 [TRAINING DEBUG] strategy_settings keys: {list(strategy_settings.keys()) if strategy_settings else 'EMPTY/NONE'}")
    logger.warning(f"🔍 [TRAINING DEBUG] strategy_settings['offense']: {strategy_settings.get('offense') if strategy_settings else 'N/A'}")
    logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings keys: {list(playbook_settings.keys()) if playbook_settings else 'EMPTY/NONE'}")
    if playbook_settings:
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['motion'] keys: {list(playbook_settings.get('motion', {}).keys())}")
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['set_play_inside'] keys: {list(playbook_settings.get('set_play_inside', {}).keys())}")
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['set_play_outside'] keys: {list(playbook_settings.get('set_play_outside', {}).keys())}")
        logger.warning(f"🔍 [TRAINING DEBUG] playbook_settings['set_play_attack'] keys: {list(playbook_settings.get('set_play_attack', {}).keys())}")
    logger.warning(f"🔍 [TRAINING DEBUG] playbook_training_mode: {training_data.get('playbook_training_mode', 'not provided')}")
    
    # ✅ FTD: Initialize plays_data if empty (first time training for this team)
    # This ensures plays structure exists before training, preventing plays from being lost
    if not plays_data:
        logger.warning(f"📚 [API] plays_data is empty, populating from universal plays collection")
        from BackEnd.api.gameplan_routes import populate_team_plays
        plays_data = populate_team_plays(mode="franchise")
        # ✅ FTD: Save to FTD collection
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": team_object_id},
            {"$set": {"plays": plays_data}}
        )
        logger.info(f"✅ [API] Initialized {len(plays_data)} plays for team {team_id}")
    else:
        logger.info(f"✅ [API] Found {len(plays_data)} existing plays for team {team_id}")
    
    # Initialize scouting_data if empty or missing defense structure
    if not scouting_data or "defense" not in scouting_data:
        logger.warning(f"📚 [API] scouting_data is empty or missing defense structure, initializing")
        from BackEnd.models.team_manager import TeamManager
        # Create a temporary TeamManager to use its initialization method
        temp_team = TeamManager(name=team_name or team_id, mode="franchise")
        scouting_data = temp_team.scouting_data
        # ✅ FTD: Save to FTD collection
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": team_object_id},
            {"$set": {"scouting_data": scouting_data}}
        )
    
    logger.warning(f"📚 [API] Loading plays_data: {len(plays_data)} plays")
    logger.warning(f"📚 [API] Loading scouting_data: {list(scouting_data.keys()) if scouting_data else 'None'}")
    logger.warning(f"📚 [API] playbook_training_mode: {training_data.get('playbook_training_mode', 'not provided')}")
    logger.warning(f"🔋 [API] training_data keys: {list(training_data.keys())}")
    logger.warning(f"🔋 [API] team_drills in training_data: {'team_drills' in training_data}")
    if "team_drills" in training_data:
        logger.warning(f"🔋 [API] team_drills content: {training_data['team_drills']}")
        logger.warning(f"🔋 [API] scrimmages in team_drills: {'scrimmages' in training_data.get('team_drills', {})}")
        if "scrimmages" in training_data.get("team_drills", {}):
            logger.warning(f"🔋 [API] scrimmages value: {training_data['team_drills']['scrimmages']}")
    allocations = {
        "player_drills": training_data.get("player_drills", {}),
        "team_drills": training_data.get("team_drills", {}),
        "general": training_data.get("general", {})
    }
    logger.warning(f"🔋 [API] allocations.team_drills: {allocations.get('team_drills', {})}")
    coaching_focus = training_data.get("coaching_focus")
    raw_custom = training_data.get("coaching_focus_custom_by_player")

    if coaching_focus == "player-maximizer-choose-attributes":
        raise HTTPException(
            status_code=400,
            detail="Open Player Maximizer attributes, choose a mode, and tap Assign Focus Attributes before submitting.",
        )

    # Execute new training system
    # This applies pre-training conditions, then training points, and returns training report
    from BackEnd.models.training_execution_v2 import (
        execute_training,
        normalize_coaching_focus_custom_by_player,
    )

    try:
        normalized_custom = normalize_coaching_focus_custom_by_player(
            coaching_focus, raw_custom, players_for_training
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    playbook_mode = training_data.get("playbook_training_mode", "current-playbooks")
    raw_tpf = training_data.get("training_playbook_focus")
    training_playbook_focus_payload: dict | None = None
    if playbook_mode == "custom":
        if not isinstance(raw_tpf, dict):
            raise HTTPException(
                status_code=400,
                detail="Custom playbook training requires training_playbook_focus with offense and defense id lists.",
            )
        off_ids = [str(x) for x in (raw_tpf.get("offense") or []) if x is not None and str(x).strip()]
        def_ids = [str(x) for x in (raw_tpf.get("defense") or []) if x is not None and str(x).strip()]
        if len(off_ids) < 1 or len(def_ids) < 1:
            raise HTTPException(
                status_code=400,
                detail="training_playbook_focus must include at least one offense play_id and one defense row id.",
            )
        training_playbook_focus_payload = {"offense": off_ids, "defense": def_ids}
    elif raw_tpf is not None:
        # Ignore stray focus when using current playbooks
        if isinstance(training_data, dict):
            training_data.pop("training_playbook_focus", None)
    
    players_load_time = (time.time() - players_load_start) * 1000
    # logger.warning(f"⏱️ [DB TIMING] run_franchise_training: Loading {len(players_for_training)} players: {players_load_time:.2f}ms")
    
    # Execute training (applies pre-training conditions, then training points)
    # Skip pre-training depreciation for first training (training camp) - week 1 before games
    training_exec_start = time.time()
    updated_players, updated_team, updated_plays, updated_scouting_data, training_report = execute_training(
        players_for_training,
        team_stats,
        allocations,
        coaching_focus,
        plays_data=plays_data,
        strategy_settings=strategy_settings,
        playbook_settings=playbook_settings,
        scouting_data=scouting_data,
        playbook_training_mode=playbook_mode,
        skip_pre_training_depreciation=is_first_training,
        coaching_focus_custom_by_player=normalized_custom,
        training_playbook_focus=training_playbook_focus_payload,
    )
    training_exec_time = (time.time() - training_exec_start) * 1000
    # logger.warning(f"⏱️ [DB TIMING] run_franchise_training: execute_training(): {training_exec_time:.2f}ms")
    
    # Update players_for_training and team_stats with results
    players_for_training = updated_players
    team_stats = updated_team

    # Recalculate position ratings for each player after training (with updated attributes)
    from BackEnd.utils.position_ratings import compute_position_ratings
    position_ratings_updates = {}
    
    for player in players_for_training:
        pid = player["_id"]
        meta = player.get("meta") or {}
        height = meta.get("height")
        if height is None:
            core_player = db.players.find_one({"_id": pid}, {"height": 1}) or {}
            height = core_player.get("height")
        
        # Build player dict for position ratings calculation with updated attributes
        player_for_ratings = {
            "attributes": player.get("attributes", {}),  # Now contains updated values!
            "height": height,
            "name": f"{player.get('first_name', '')} {player.get('last_name', '')}"
        }
        
        # Compute new position ratings
        new_ratings = compute_position_ratings(player_for_ratings)
        position_ratings_updates[pid] = new_ratings

    # Use training report data for player and team changes
    # Support both old field names (player_changes, team_changes) and new standardized names (player_logs, team_log)
    player_logs = training_report.get("player_logs") or training_report.get("player_changes", {})
    team_log = training_report.get("team_log") or training_report.get("team_changes", {})

    # ✅ FPD: Update franchise_players_data with new attribute values and position ratings (not franchise.players)
    franchise_update = {}
    for player in players_for_training:
        pid = player["_id"]
        attrs = player.get("attributes", {})
        fpd_set = {}
        for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH", "EM", "MO"]:
            anchor_key = f"anchor_{attr}"
            if anchor_key in attrs:
                fpd_set[f"attributes.{anchor_key}"] = attrs[anchor_key]
                fpd_set[f"attributes.{attr}"] = attrs[attr]
        if "NG" in attrs:
            fpd_set["attributes.NG"] = attrs["NG"]
        if pid in position_ratings_updates:
            fpd_set["position_ratings"] = position_ratings_updates[pid]
        pm = player.get("meta") or {}
        if isinstance(pm, dict):
            if "height" in pm:
                fpd_set["meta.height"] = pm["height"]
            if "weight" in pm:
                fpd_set["meta.weight"] = pm["weight"]
        if fpd_set:
            franchise_players_data_collection.update_one(
                {"franchise_id": str(req.franchise_id), "player_id": pid},
                {"$set": fpd_set},
            )

    # ✅ FTD: Build FTD update document
    ftd_update = {}
    
    # Update team attributes (team_stats)
    for field, value in team_stats.items():
        # Skip non-numeric fields
        if isinstance(value, dict):
            continue
        ftd_update[f"team_attributes.{field}"] = value
    
    # ✅ FTD: Always save plays data (even if empty) to preserve structure after training
    # This ensures plays are not lost when playbooks page reloads
    if updated_plays is not None:
        ftd_update["plays"] = updated_plays
        logger.info(f"✅ [TRAINING] Saving {len(updated_plays)} plays to FTD")
    else:
        logger.warning(f"⚠️ [TRAINING] updated_plays is None, preserving existing plays data")
    
    # ✅ FTD: Always save scouting_data (even if empty) to preserve structure after training
    if updated_scouting_data is not None:
        ftd_update["scouting_data"] = updated_scouting_data
        logger.info(f"✅ [TRAINING] Saving scouting_data to FTD")
    else:
        logger.warning(f"⚠️ [TRAINING] updated_scouting_data is None, preserving existing scouting_data")
    if is_first_training:
        ftd_update["training_squad_players"] = []

    # Community Engagement → pending home-crowd band shift for user's next franchise game (consumed at game start)
    _, ce_sub = parse_coaching_focus(coaching_focus)
    if ce_sub == "culture-builder-community":
        ftd_update["pending_community_engagement"] = True

    if 20 <= week <= 26 and str(week) not in recruiting_results:
        week_assignments = _process_weekly_recruiting_invites(franchise_doc)
        if isinstance(week_assignments, dict) and week_assignments:
            franchise_doc.setdefault("recruiting_results", {})[str(week)] = week_assignments

    session_type = training_status.get("session_type", "in-season")
    ftd_counts_for_highlights: dict[str, int] = {}
    pre_cf = ftd_doc.get("coaching_focus") or {}
    for _k in COACHING_FOCUS_FTD_COUNT_KEYS:
        try:
            ftd_counts_for_highlights[_k] = int(pre_cf.get(_k, 0) or 0)
        except (TypeError, ValueError):
            ftd_counts_for_highlights[_k] = 0

    # Persist the `general` allocations (incl. film_study) so the FCC Scouting
    # Report can gate the opponent's Play Usage on Film Study > 0 for this week.
    _general_alloc = training_data.get("general") or {}
    _film_study = int(_general_alloc.get("film_study") or 0)
    _training_notes = list(training_report.get("training_notes", []) or [])
    # Weeks > 1 only (week 1 has no prior game): when Film Study was run, the
    # opponent's prior-game Play Usage is unlocked in the FCC Scouting Report.
    if int(week) > 1 and _film_study > 0:
        # Film Study > 0 unlocks Half-Court Offense usage; > 1 also unlocks Fast
        # Breaks + Half-Court Traps. The note's parenthetical lists what was added.
        _scope = "Half-Court Offense"
        if _film_study > 1:
            _scope = "Half-Court Offense, Fast Breaks, Half-Court Traps"
        _training_notes.append({
            "title": "Film Study",
            "body": f"Opponent's prior game play usage stats have been added to the scouting report in the command center ({_scope}).",
        })

    training_report_data = {
        "week": week,
        "player_logs": player_logs,
        "team_log": team_log,
        "coaching_focus": training_report.get("coaching_focus", {}),
        "training_notes": _training_notes,
        "plays_data": training_report.get("plays_data", {}),
        "scouting_data": training_report.get("scouting_data", {}),
        "plays_effectiveness_changes": training_report.get("plays_effectiveness_changes", {}),
        "defenses_effectiveness_changes": training_report.get("defenses_effectiveness_changes", {}),
        "session_type": session_type,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "ftd_coaching_focus": ftd_counts_for_highlights,
        "team_drills": training_data.get("team_drills") or {},
        "general": _general_alloc,
    }
    rec_ui = _training_report_recruiting_display(franchise_doc, int(week), str(team_id))
    if rec_ui is not None:
        training_report_data["recruiting_header"] = rec_ui.get("header")
        training_report_data["recruiting_meta_line"] = rec_ui.get("meta_line")

    franchise_update_user = {
        "training_status.user_training_applied_week": week,
        "training_status.training_completed": False,
        "training_status.week": week,
        "training_status.last_training_date": datetime.now().strftime("%Y-%m-%d"),
        "latest_training": training_report_data,
    }

    ftd_update[f"training_reports.{week}"] = training_report_data

    ftd_ops: dict[str, Any] = {}
    if ftd_update:
        ftd_ops["$set"] = ftd_update
    cf_inc = user_ftd_coaching_focus_increment(
        coaching_focus,
        training_camp_first_week=is_first_training,
    )
    if cf_inc:
        ftd_ops["$inc"] = cf_inc
        for _path, _inc in cf_inc.items():
            _sub = _path.replace("coaching_focus.", "")
            if _sub in ftd_counts_for_highlights:
                ftd_counts_for_highlights[_sub] = ftd_counts_for_highlights.get(_sub, 0) + int(_inc)
        training_report_data["ftd_coaching_focus"] = ftd_counts_for_highlights
    if ftd_ops:
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": team_object_id},
            ftd_ops,
        )

    db.franchises.update_one({"_id": franchise_id}, {"$set": franchise_update_user})

    training_highlights = build_training_loading_highlights(training_report_data)

    if phase == "user_only":
        return {
            "status": "success",
            "week": week,
            "training_highlights": training_highlights,
            "player_changes": player_logs,
            "team_changes": team_log,
            "coaching_focus": training_report.get("coaching_focus", {}),
            "session_type": session_type,
            "team_id": team_id,
            "redirect": None,
        }

    _apply_franchise_distant_cpu_training(
        franchise_id,
        franchise_doc=franchise_doc,
        user_team_id_str=str(team_id),
        week=week,
        is_first_training=is_first_training,
        franchise_players=franchise_players,
    )

    cuts_ran_this_call = False
    if is_first_training and not bool(training_status.get("cpu_training_camp_cuts_applied")):
        _apply_cpu_training_camp_cuts(franchise_id, excluded_team_id=str(team_id))
        cuts_ran_this_call = True

    distant_update: dict[str, Any] = {
        "training_status.training_completed": True,
        "training_status.cpu_distant_complete_week": week,
        "training_status.last_training_date": datetime.now().strftime("%Y-%m-%d"),
    }
    if cuts_ran_this_call:
        distant_update["training_status.cpu_training_camp_cuts_applied"] = True
    db.franchises.update_one({"_id": franchise_id}, {"$set": distant_update})

    return {
        "status": "success",
        "week": week,
        "training_highlights": training_highlights,
        "player_changes": player_logs,
        "team_changes": team_log,
        "coaching_focus": training_report.get("coaching_focus", {}),
        "session_type": session_type,
        "redirect": f"/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={team_id}&week={week}&from=training",
    }


@router.get("/franchise/training-report")
def get_training_report(franchise_id: str = None, tournament_id: str = None, team_id: str = None, week: int = None, round: int = None):
    """
    Get training report data for display on training-report.html page.
    Supports both franchise and tournament modes.
    
    SS&S Approach:
    - For franchise mode: 'week' parameter is required
    - For tournament mode: 'round' parameter is optional - if not provided, backend determines from training_status.round or latest_training.round
    - This allows direct navigation after training without needing round in URL
    - Historical reports from schedule links can still pass round parameter
    """
    try:
        mode = "franchise" if franchise_id else "tournament"
        doc_id = franchise_id if franchise_id else tournament_id
        
        if not doc_id or not team_id:
            raise HTTPException(status_code=400, detail="Missing required parameters (doc_id, team_id)")
        
        # For tournament mode, determine round from backend state if not provided
        if mode == "tournament":
            from BackEnd.db import tournaments_collection
            from BackEnd.api.tournament_routes import get_user_team_from_tournament
            doc_id_obj = ObjectId(doc_id)
            doc = tournaments_collection.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [TRAINING REPORT] URL team_id ({team_id}) doesn't match tournament document user_team_object_id ({authoritative_team_id}). Using tournament document value.")
            
            if round is not None:
                week = round  # Use round parameter if provided (for historical reports)
            elif week is not None:
                week = week  # Use week parameter if provided (backward compatibility)
            else:
                # SS&S: Determine round from backend state (training_status or latest_training)
                # Try training_status.round first, then latest_training.round
                training_status = doc.get("training_status", {})
                week = training_status.get("round")
                if week is None:
                    latest_training = doc.get("latest_training", {})
                    week = latest_training.get("round")
                
                if week is None:
                    raise HTTPException(status_code=400, detail="No training round found. Please specify 'round' parameter or complete training first.")
        
        # For franchise mode, week is required
        if mode == "franchise" and week is None:
            raise HTTPException(status_code=400, detail="Missing required parameter: 'week'")
        
        if mode == "franchise":
            doc_id_obj = ObjectId(doc_id)
            doc = db.franchises.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Franchise not found")
            
            # ✅ SS&S: Always use user_team_object_id from franchise document as source of truth
            # This ensures we're always using the correct team, even if URL params are wrong
            user_team_id_name, user_team_object_id = get_user_team_from_franchise(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in franchise document")
            
            # Use franchise document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            team_id_str = str(authoritative_team_id)  # Convert to string for logging and dict lookups
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [TRAINING REPORT] URL team_id ({team_id}) doesn't match franchise document user_team_object_id ({authoritative_team_id}). Using franchise document value.")
            
            # ✅ FTD: Get training report from FTD collection
            try:
                team_object_id = ObjectId(authoritative_team_id)
            except:
                raise HTTPException(status_code=400, detail=f"Invalid team_id format: {authoritative_team_id}")
            
            ftd_doc = franchise_team_data_collection.find_one(
                {"franchise_id": doc_id_obj, "team_id": team_object_id},
                {"training_reports": 1, "team_attributes": 1, "players": 1}
            )
            
            if ftd_doc:
                training_reports = ftd_doc.get("training_reports", {})
                report_data = training_reports.get(str(week)) or doc.get("latest_training", {})
                team_data = ftd_doc.get("team_attributes", {})
            else:
                # FTD doesn't exist - fallback to latest_training in franchise doc
                report_data = doc.get("latest_training", {})
                team_data = {}
            
            # Get schedule to find upcoming opponent
            schedule = doc.get("schedule", [])
            current_week = doc.get("week", 1)
            upcoming_opponent = None
            
            if current_week - 1 < len(schedule):
                week_games = schedule[current_week - 1]
                for away_id, home_id in week_games:
                    if str(away_id) == authoritative_team_id or str(home_id) == authoritative_team_id:
                        opponent_id = str(home_id) if str(away_id) == authoritative_team_id else str(away_id)
                        opponent_team = db.teams.find_one({"_id": ObjectId(opponent_id)}, {"name": 1})
                        if opponent_team:
                            upcoming_opponent = opponent_team.get("name", "")
                        break
            
            # Get current player attributes (after training)
            # ✅ FPD: Load franchise players from franchise_players_data (not franchise.players)
            players = []
            fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(doc_id)}))
            franchise_players = {d["player_id"]: d for d in fpd_docs}

            team_player_ids = (ftd_doc or {}).get("players") or []
            if not team_player_ids:
                team_doc = db.teams.find_one({"_id": ObjectId(authoritative_team_id)})
                if not team_doc:
                    raise HTTPException(status_code=404, detail=f"Team not found: {authoritative_team_id}")
                team_player_ids = team_doc.get("player_ids", [])
                logger.info(f"🔍 [TRAINING REPORT] Fallback to team_doc.player_ids: {len(team_player_ids)} players")
            else:
                logger.info(f"🔍 [TRAINING REPORT] Using FTD.players: {len(team_player_ids)} players")
            logger.info(f"🔍 [TRAINING REPORT] Total franchise players: {len(franchise_players)}")
            
            for pid in team_player_ids:
                pid_str = str(pid)
                player_data = franchise_players.get(pid_str, {})
                
                if not player_data:
                    # Player not in FPD (shouldn't happen, but handle gracefully)
                    logger.warning(f"🔍 [TRAINING REPORT] Player {pid_str} not found in FPD")
                    continue
                
                # Get meta for player name
                meta = player_data.get("meta", {})
                
                # Get attributes (after training)
                attrs = player_data.get("attributes", {})
                
                # Extract anchor attributes (current values after training)
                # Use anchor_ values if available (post-training), otherwise fallback to base values
                player_attrs = {}
                # First, collect all anchor_ attributes
                for k, v in attrs.items():
                    if k.startswith("anchor_"):
                        attr_name = k.replace("anchor_", "")
                        player_attrs[attr_name] = v
                
                # For attributes that don't have anchor_ keys, use base values as fallback
                # This ensures SC, SH, and other attributes are included even if they haven't been modified
                standard_attrs = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
                for attr in standard_attrs:
                    if attr not in player_attrs and attr in attrs:
                        player_attrs[attr] = attrs[attr]
                
                # NG, EM, MO don't have anchor_ keys, add them directly
                if "NG" in attrs:
                    player_attrs["NG"] = attrs["NG"]
                if "EM" in attrs:
                    player_attrs["EM"] = attrs["EM"]
                if "MO" in attrs:
                    player_attrs["MO"] = attrs["MO"]
                
                first_name = meta.get("first_name", "")
                last_name = meta.get("last_name", "")
                player_name = f"{first_name} {last_name}".strip()
                
                if player_name:  # Only add if we have a name
                    season_raw = player_data.get("season") or {}
                    season_stats = dict(season_raw) if isinstance(season_raw, dict) else {}
                    players.append({
                        "id": pid_str,
                        "player_id": pid_str,
                        "name": player_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "jersey": meta.get("jersey"),
                        "year": meta.get("year") or player_data.get("year"),
                        "height": meta.get("height") or player_data.get("height"),
                        "weight": meta.get("weight") or player_data.get("weight"),
                        "attributes": player_attrs,
                        "position_ratings": player_data.get("position_ratings", {}),
                        "season_stats": season_stats,
                    })
            
            logger.info(f"🔍 [TRAINING REPORT] Found {len(players)} players for team {team_id_str}")
            _sort_training_report_players_by_max_rt(players)
            
            # Get current team attributes (after training)
            team_attrs = {
                "shot_threshold": team_data.get("shot_threshold", 120),
                "rebound_modifier": team_data.get("rebound_modifier", 0.2),
                "offensive_efficiency": team_data.get("offensive_efficiency", 0),
                "defensive_efficiency": team_data.get("defensive_efficiency", 0),
                "fb_efficiency": team_data.get("fb_efficiency", 0),
                "pt_efficiency": team_data.get("pt_efficiency", 0),
                "fight": team_data.get("fight", 0),
                "discipline": team_data.get("discipline", 0),
                "momentum_score": team_data.get("momentum_score", 0),
                "team_chemistry": team_data.get("team_chemistry", 7),
                "fb_opp_modifier": team_data.get("fb_opp_modifier", 0),
                "pt_opp_modifier": team_data.get("pt_opp_modifier", 0)
            }
            
        else:  # tournament mode
            from BackEnd.db import tournaments_collection, teams_collection
            from BackEnd.api.tournament_routes import get_user_team_from_tournament
            doc_id_obj = ObjectId(doc_id)
            doc = tournaments_collection.find_one({"_id": doc_id_obj})
            if not doc:
                raise HTTPException(status_code=404, detail="Tournament not found")
            
            # ✅ MIGRATION: Use tournament document's user_team_object_id as source of truth
            user_team_id_name, user_team_object_id = get_user_team_from_tournament(doc)
            if not user_team_id_name or not user_team_object_id:
                raise HTTPException(status_code=404, detail="User team not found in tournament document")
            
            # Use tournament document's user_team_object_id as authoritative team_id
            authoritative_team_id = user_team_object_id
            
            # Log if URL team_id doesn't match (for debugging)
            if team_id and team_id != authoritative_team_id:
                logger.warning(f"⚠️ [TRAINING REPORT] URL team_id ({team_id}) doesn't match tournament document user_team_object_id ({authoritative_team_id}). Using tournament document value.")
            
            team_id_str = str(authoritative_team_id)
            current_round = week  # week parameter is used as round for tournament
            
            # Get training report for this round (matches Franchise pattern: try per-round storage first, then fallback)
            tournament_teams = doc.get("teams", {})
            team_data = tournament_teams.get(team_id_str, {})
            training_reports = team_data.get("training_reports", {})
            report_data = training_reports.get(str(current_round)) or doc.get("latest_training", {})
            
            # Verify round matches if using latest_training fallback
            if report_data and report_data.get("round") != current_round:
                report_data = {}
            
            # Get upcoming opponent from bracket (do not clobber report round `week`)
            bracket_round = doc.get("current_round", 1)
            round_key = get_round_name(bracket_round)
            matchups = doc.get("bracket", {}).get(round_key, [])
            upcoming_opponent = None
            
            user_team_id = doc.get("user_team_id")
            for matchup in matchups:
                if user_team_id in [matchup.get("home_team"), matchup.get("away_team")]:
                    upcoming_opponent = matchup.get("away_team") if matchup.get("home_team") == user_team_id else matchup.get("home_team")
                    break
            
            # Get current player attributes (after training)
            players = []
            # ✅ MIGRATION: Use players key instead of player_stats (aligns with Franchise)
            tournament_players = doc.get("players", {}) or doc.get("player_stats", {})  # Backward compatibility
            
            # ✅ MIGRATION: Use authoritative_team_id (already resolved from tournament document)
            # No need to resolve again - we already have the correct ObjectId
            team_doc = teams_collection.find_one({"_id": ObjectId(team_id_str)})
            if not team_doc:
                raise HTTPException(status_code=404, detail="Team not found")
            
            team_player_ids = team_doc.get("player_ids", [])
            for pid in team_player_ids:
                pid_str = str(pid)
                tournament_player_data = tournament_players.get(pid_str, {})
                if not tournament_player_data:
                    continue
                
                # Get attributes (after training)
                attrs = tournament_player_data.get("attributes", {})
                
                # For backward compatibility: if tournament only has EM, CH, MO (old format),
                # merge with core attributes. New tournaments will have all attributes stored.
                standard_attrs = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
                has_all_attrs = all(attr in attrs for attr in standard_attrs)
                
                if not has_all_attrs:
                    # Merge with core collection for backward compatibility
                    from BackEnd.db import players_collection
                    # ✅ FIX: Player IDs are UUIDs (strings), not ObjectIds - use directly
                    core_player = players_collection.find_one({"_id": pid_str}, {"attributes": 1})
                    if core_player:
                        core_attributes = core_player.get("attributes", {})
                        attrs = {**core_attributes, **attrs}  # Tournament attributes override core
                        logger.info(f"📊 [TRAINING REPORT] Merged core attributes for player {pid_str} (backward compatibility)")
                
                # Extract anchor attributes (current values after training)
                # Use anchor_ values if available (post-training), otherwise fallback to base values
                player_attrs = {}
                # First, collect all anchor_ attributes
                for k, v in attrs.items():
                    if k.startswith("anchor_"):
                        attr_name = k.replace("anchor_", "")
                        player_attrs[attr_name] = v
                
                # For attributes that don't have anchor_ keys, use base values as fallback
                # This ensures SC, SH, and other attributes are included even if they haven't been modified
                for attr in standard_attrs:
                    if attr not in player_attrs and attr in attrs:
                        player_attrs[attr] = attrs[attr]
                
                # NG, EM, MO don't have anchor_ keys, add them directly
                if "NG" in attrs:
                    player_attrs["NG"] = attrs["NG"]
                if "EM" in attrs:
                    player_attrs["EM"] = attrs["EM"]
                if "MO" in attrs:
                    player_attrs["MO"] = attrs["MO"]
                
                # Get player metadata (with meta wrapper support and backward compatibility)
                meta = tournament_player_data.get("meta", {})
                first_name = meta.get("first_name") or tournament_player_data.get("first_name", "")
                last_name = meta.get("last_name") or tournament_player_data.get("last_name", "")
                player_name = f"{first_name} {last_name}".strip()
                
                if player_name:
                    season_raw = tournament_player_data.get("season") or {}
                    season_stats = dict(season_raw) if isinstance(season_raw, dict) else {}
                    players.append({
                        "id": pid_str,
                        "player_id": pid_str,
                        "name": player_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "jersey": meta.get("jersey"),
                        "year": meta.get("year") or tournament_player_data.get("year"),
                        "height": meta.get("height") or tournament_player_data.get("height"),
                        "weight": meta.get("weight") or tournament_player_data.get("weight"),
                        "attributes": player_attrs,
                        "position_ratings": tournament_player_data.get("position_ratings", {}),
                        "season_stats": season_stats,
                    })
            
            _sort_training_report_players_by_max_rt(players)
            
            # Get current team attributes from tournament teams (matches Franchise pattern)
            team_attrs = {
                "shot_threshold": team_data.get("shot_threshold", 120),
                "rebound_modifier": team_data.get("rebound_modifier", 0.2),
                "offensive_efficiency": team_data.get("offensive_efficiency", 0),
                "defensive_efficiency": team_data.get("defensive_efficiency", 0),
                "fb_efficiency": team_data.get("fb_efficiency", 0),
                "pt_efficiency": team_data.get("pt_efficiency", 0),
                "fight": team_data.get("fight", 0),
                "discipline": team_data.get("discipline", 0),
                "momentum_score": team_data.get("momentum_score", 0),
                "team_chemistry": team_data.get("team_chemistry", 0),
                "fb_opp_modifier": team_data.get("fb_opp_modifier", 0),
                "pt_opp_modifier": team_data.get("pt_opp_modifier", 0)
            }
        
        if not report_data:
            raise HTTPException(status_code=404, detail="Training report not found")

        from BackEnd.utils.scouting_utils import compute_projected_starting_five

        projected_starting_five = compute_projected_starting_five(players) if players else []

        try:
            targeted_note_titles = {
                "Practice Player Of The Week",
                "Practice Players Of The Week",
                "Biggest Regression",
                "Most Positive Locker Room Influence",
            }
            note_debug = []
            for note in (report_data.get("training_notes", []) or []):
                if not isinstance(note, dict):
                    continue
                title = str(note.get("title", ""))
                if title not in targeted_note_titles:
                    continue
                note_debug.append({
                    "title": title,
                    "body": note.get("body"),
                    "player_id": note.get("player_id"),
                    "player_ids": note.get("player_ids"),
                })
            logger.info(
                "🧪 [TRAINING REPORT][NOTES] mode=%s doc_id=%s team_id=%s week=%s targeted_notes=%s player_count=%s",
                mode,
                str(doc_id),
                str(authoritative_team_id),
                week,
                note_debug,
                len(players),
            )
        except Exception as debug_exc:
            logger.warning("⚠️ [TRAINING REPORT][NOTES] debug logging failed: %s", debug_exc)

        rec_header = None
        rec_meta = None
        if mode == "franchise" and isinstance(report_data, dict):
            try:
                report_week_int = int(week)
            except (TypeError, ValueError):
                report_week_int = 0
            visit_window = 20 <= report_week_int <= 26
            rec_header_snap = report_data.get("recruiting_header")
            rec_meta_snap = report_data.get("recruiting_meta_line")
            meta_empty = (
                "recruiting_meta_line" not in report_data
                or rec_meta_snap is None
                or (isinstance(rec_meta_snap, str) and not str(rec_meta_snap).strip())
            )
            keys_present = (
                "recruiting_header" in report_data or "recruiting_meta_line" in report_data
            )
            # Snapshots that saved "Recruiting Visit" with null/empty meta never refreshed; recompute
            # from current franchise + FRD when visit-week meta is missing (Training_System.md).
            stale_visit_strip = visit_window and meta_empty
            if keys_present and not stale_visit_strip:
                rec_header = rec_header_snap
                rec_meta = rec_meta_snap
            else:
                rec_snap = _training_report_recruiting_display(
                    doc, report_week_int, str(authoritative_team_id)
                )
                if rec_snap is not None:
                    rec_header = rec_snap.get("header")
                    rec_meta = rec_snap.get("meta_line")

        return {
            "status": "success",
            "week": week if mode == "franchise" else None,  # Only for franchise mode
            "round": week if mode == "tournament" else None,  # Tournament: training report round (not bracket cursor)
            "upcoming_opponent": upcoming_opponent,
            "coaching_focus": report_data.get("coaching_focus", {}),
            # Support both old field names (player_changes, team_changes) and new standardized names (player_logs, team_log)
            "player_changes": report_data.get("player_logs") or report_data.get("player_changes", {}),
            "team_changes": report_data.get("team_log") or report_data.get("team_changes", {}),
            "training_notes": report_data.get("training_notes", []),
            "plays_data": report_data.get("plays_data", {}),
            "scouting_data": report_data.get("scouting_data", {}),
            "plays_effectiveness_changes": report_data.get("plays_effectiveness_changes", {}),
            "defenses_effectiveness_changes": report_data.get("defenses_effectiveness_changes", {}),
            "players": players,
            "team_attributes": team_attrs,
            "projected_starting_five": projected_starting_five,
            "recruiting_header": rec_header if mode == "franchise" else None,
            "recruiting_meta_line": rec_meta if mode == "franchise" else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching training report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


class SimRestOfTournamentRequest(BaseModel):
    franchise_id: str


class SimChampionshipRequest(BaseModel):
    franchise_id: str


class FinishSeasonRequest(BaseModel):
    franchise_id: str


class DismissChampionshipMomentRequest(BaseModel):
    franchise_id: str
    moment_id: str


class RegionByeModalSeenRequest(BaseModel):
    franchise_id: str


@router.patch("/franchise/region-bye-modal-seen")
def mark_region_bye_modal_seen(
    req: RegionByeModalSeenRequest,
    user: dict = Depends(get_current_user),
):
    """Persist that this franchise season's week-30 region-bye modal was presented."""
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    current_season = int(franchise_doc.get("current_season", 1) or 1)
    db.franchises.update_one(
        {"_id": franchise_doc["_id"]},
        {"$set": {REGION_BYE_MODAL_SEEN_SEASON_FIELD: current_season}},
    )
    return {"seen": True, "season": current_season}


class BracketRevealModalSeenRequest(BaseModel):
    franchise_id: str
    reveal_key: str


@router.patch("/franchise/bracket-reveal-modal-seen")
def mark_bracket_reveal_modal_seen(
    req: BracketRevealModalSeenRequest,
    user: dict = Depends(get_current_user),
):
    """Persist that a bracket-reveal or bracket-update modal was dismissed."""
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    reveal_key = str(req.reveal_key or "").strip()
    if not reveal_key:
        raise HTTPException(status_code=400, detail="reveal_key required")
    if reveal_key.startswith("update:"):
        seen_field = BRACKET_UPDATE_SEEN_FIELD
    else:
        seen_field = BRACKET_REVEAL_SEEN_FIELD
    seen = dict(franchise_doc.get(seen_field) or {})
    seen[reveal_key] = True
    db.franchises.update_one(
        {"_id": franchise_doc["_id"]},
        {"$set": {seen_field: seen}},
    )
    return {"seen": True, "reveal_key": reveal_key}


class RecruitingResultsModalSeenRequest(BaseModel):
    franchise_id: str


@router.patch("/franchise/recruiting-results-modal-seen")
def mark_recruiting_results_modal_seen(
    req: RecruitingResultsModalSeenRequest,
    user: dict = Depends(get_current_user),
):
    """Persist that the week-35 recruiting results modal was dismissed."""
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    current_season = _franchise_current_season(franchise_doc)
    db.franchises.update_one(
        {"_id": franchise_doc["_id"]},
        {"$set": {RECRUITING_RESULTS_MODAL_SEEN_SEASON_FIELD: current_season}},
    )
    return {"seen": True, "season": current_season}


@router.get("/franchise/championship-moments/context")
def championship_moment_context(
    franchise_id: str,
    game_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Return a Variation A/B moment payload for a finalized game when it is the
    user's conference / region / national championship. Used by the EOG modal
    on the live-game path to render the moment in place of the standard EOG.
    """
    franchise_doc = verify_franchise_owned_by_user(franchise_id, user["user_id"])
    game_doc = db.games.find_one({"_id": game_id})
    if not game_doc and ObjectId.is_valid(game_id):
        game_doc = db.games.find_one({"_id": ObjectId(game_id)})
    if not game_doc:
        return {"is_championship": False}

    from BackEnd.utils.franchise_championship_moments import (
        championship_moment_from_game_doc,
    )

    moment = championship_moment_from_game_doc(franchise_doc, game_doc)
    if not moment:
        return {"is_championship": False}
    return {"is_championship": True, "moment": moment}


@router.post("/franchise/championship-moments/dismiss")
def dismiss_championship_moment(
    req: DismissChampionshipMomentRequest,
    user: dict = Depends(get_current_user),
):
    """Pop one championship-announce moment from the franchise queue once the FCC overlay has shown it."""
    franchise_doc = verify_franchise_owned_by_user(req.franchise_id, user["user_id"])
    franchise_id = franchise_doc["_id"]
    from BackEnd.utils.franchise_championship_moments import consume_moment

    removed = consume_moment(franchise_id, req.moment_id)
    return {"status": "ok", "removed": bool(removed)}


@router.post("/franchise/sim-rest-of-tournament")
def sim_rest_of_tournament(req: SimRestOfTournamentRequest):
    """Simulate all games in the current EOS round (when user has no game: bye or did not qualify)."""
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    week = franchise_doc.get("week", ScheduleManager.REGULAR_SEASON_WEEKS + 1)
    if week not in ft.EOS_WEEKS:
        raise HTTPException(status_code=400, detail="Not in EOS weeks (27–34)")

    eos_active = bool(
        franchise_doc.get("eos_tournament_active")
        and (franchise_doc.get("conference_tournaments") or franchise_doc.get("region_tournaments") or franchise_doc.get("national_tournament"))
    )
    if not eos_active:
        raise HTTPException(status_code=400, detail="EOS tournaments not active")

    sim_rest_reconcile_persisted = False
    if week in ft.EOS_REGION_WEEKS and franchise_doc.get("region_tournaments"):
        eos_team_ids = [
            d["team_id"]
            for d in franchise_team_data_collection.find({"franchise_id": franchise_id}, {"team_id": 1})
            if d.get("team_id") is not None
        ]
        if eos_team_ids:
            updated_rt = ft.reconcile_region_tournaments_with_canonical(
                franchise_doc, db.teams, eos_team_ids
            )
            if updated_rt is not None:
                franchise_doc["region_tournaments"] = updated_rt
                db.franchises.update_one({"_id": franchise_id}, {"$set": {"region_tournaments": updated_rt}})
                sim_rest_reconcile_persisted = True
            logger.warning(
                "[EOS-REGION-RECONCILE] context=sim_rest week=%s franchise_id=%s persisted=%s ftd_team_count=%s",
                week,
                str(franchise_id),
                sim_rest_reconcile_persisted,
                len(eos_team_ids),
            )
        else:
            logger.warning(
                "[EOS-REGION-RECONCILE] context=sim_rest week=%s franchise_id=%s persisted=%s ftd_team_count=0",
                week,
                str(franchise_id),
                False,
            )

    week_games_meta = ft.get_eos_week_games(franchise_doc, week)
    meta_count = len(week_games_meta)
    if not week_games_meta:
        logger.warning(
            "[EOS-SIM-REST] empty_meta week=%s franchise_id=%s meta_count=%s reconcile_persisted=%s",
            week,
            str(franchise_id),
            meta_count,
            sim_rest_reconcile_persisted,
        )
        if week != ft.EOS_REGION_WEEKS[0]:
            raise HTTPException(status_code=400, detail="No games in current EOS round.")

    _user_team_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    user_eos_sim_scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {
            "team_id": 1,
            "players": 1,
            "prestige": 1,
            "total_player_attrs": 1,
            "natl_rank": 1,
            "team_attributes.team_chemistry": 1,
            "team_attributes.momentum_score": 1,
            "team_attributes.distant_win_streak": 1,
            "team_attributes.distant_loss_streak": 1,
            "team_attributes.offensive_efficiency": 1,
            "team_attributes.defensive_efficiency": 1,
            "team_attributes.shot_threshold": 1,
        },
    ))
    ftd_by_team_id = {str(d["team_id"]): d for d in ftd_docs if d.get("team_id")}
    distant_fpd_by_player_id = _distant_sim_batch_fpd_map(franchise_id, ftd_by_team_id)
    distant_rs_standings = _distant_sim_regular_season_standings(franchise_doc, ftd_by_team_id)

    results = []
    for g in week_games_meta:
        away_id = g["away_id"]
        home_id = g["home_id"]
        home_doc = db.teams.find_one({"_id": home_id}, {"name": 1}) or {}
        away_doc = db.teams.find_one({"_id": away_id}, {"name": 1}) or {}
        home_name = home_doc.get("name", "")
        away_name = away_doc.get("name", "")
        if not _should_use_tbt_for_eos_game(week, g, user_eos_sim_scope):
            home_ftd = ftd_by_team_id.get(str(home_id), {})
            away_ftd = ftd_by_team_id.get(str(away_id), {})
            home_combined = _distant_sim_team_combined(
                home_ftd, home_id, is_home=True, rs_standings=distant_rs_standings,
                fpd_by_player_id=distant_fpd_by_player_id, current_week=week,
            )
            away_combined = _distant_sim_team_combined(
                away_ftd, away_id, is_home=False, rs_standings=distant_rs_standings,
                fpd_by_player_id=distant_fpd_by_player_id, current_week=week,
            )
            home_score, away_score = _run_distant_game_sim(home_combined, away_combined)
            winner_id = home_id if home_score > away_score else away_id
            ftp.record_tournament_game_result(
                franchise_doc,
                g,
                week=week,
                franchise_id_str=str(franchise_id),
                game_id=None,
                team1_id=away_id,
                team2_id=home_id,
                team1_score=away_score,
                team2_score=home_score,
                source="distant",
            )
            results.append({
                "away_id": str(away_id),
                "home_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
            })
            maybe_award_franchise_win_geek_points(
                owner_user_id=franchise_doc.get("user_id"),
                user_team_id_str=user_team_id_str,
                winner_team_id=winner_id,
                week=week,
                eos_game_meta=g,
            )
            maybe_award_franchise_loss_geek_points(
                owner_user_id=franchise_doc.get("user_id"),
                user_team_id_str=user_team_id_str,
                winner_team_id=winner_id,
                participant_team_ids=(away_id, home_id),
                week=week,
                eos_game_meta=g,
            )
            maybe_award_franchise_eos_title_championship(
                owner_user_id=franchise_doc.get("user_id"),
                user_team_id_str=user_team_id_str,
                winner_team_id=winner_id,
                week=week,
                eos_game_meta=g,
            )
            logger.info("✅ [EOS] Distant-simmed %s: %s vs %s", g["phase"], away_id, home_id)
            continue

        if not home_name or not away_name:
            logger.error("❌ [EOS] Missing team names for sim round")
            continue
        try:
            gm = run_simulation(home_name, away_name)
            home_score = gm.score.get(home_name, 0)
            away_score = gm.score.get(away_name, 0)
            summary = summarize_game_state(gm)
            game_id = generate_game_id()
            summary["_id"] = game_id
            summary["franchise_id"] = str(franchise_id)
            summary["week"] = week
            db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
            stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(franchise_id))
            winner_id = home_id if home_score > away_score else away_id
            ftp.record_tournament_game_result(
                franchise_doc,
                g,
                week=week,
                franchise_id_str=str(franchise_id),
                game_id=str(game_id),
                team1_id=away_id,
                team2_id=home_id,
                team1_score=away_score,
                team2_score=home_score,
                source="cpu_full",
                skip_games_upsert=True,
            )
            results.append({
                "away_id": str(away_id),
                "home_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
            })
            maybe_award_franchise_win_geek_points(
                owner_user_id=franchise_doc.get("user_id"),
                user_team_id_str=user_team_id_str,
                winner_team_id=winner_id,
                week=week,
                eos_game_meta=g,
            )
            maybe_award_franchise_loss_geek_points(
                owner_user_id=franchise_doc.get("user_id"),
                user_team_id_str=user_team_id_str,
                winner_team_id=winner_id,
                participant_team_ids=(away_id, home_id),
                week=week,
                eos_game_meta=g,
            )
            maybe_award_franchise_eos_title_championship(
                owner_user_id=franchise_doc.get("user_id"),
                user_team_id_str=user_team_id_str,
                winner_team_id=winner_id,
                week=week,
                eos_game_meta=g,
            )
            logger.info("✅ [EOS] Simulated %s: %s vs %s", g["phase"], away_name, home_name)
        except Exception as e:
            logger.error("❌ [EOS] Error simulating game: %s", e, exc_info=True)

    existing_results = franchise_doc.get("results", {})
    existing_results[str(week)] = results
    update_fields = {"results": existing_results}

    eos_updates = _eos_calendar_advance_update_fields(
        franchise_doc,
        franchise_id,
        week,
        franchise_id_str=str(franchise_id),
        log_conference_bracket_snapshots=False,
    )
    update_fields.update(eos_updates)

    ts_reset = _training_status_reset_after_advance_to_week(update_fields.get("week", week))
    if ts_reset:
        update_fields.update(ts_reset)

    db.franchises.update_one({"_id": franchise_id}, {"$set": update_fields})
    if update_fields.get("week") == 35:
        refreshed = db.franchises.find_one({"_id": franchise_id})
        if refreshed:
            _persist_week_35_awards_if_needed(refreshed)
    return {"status": "success", "week": update_fields.get("week", week)}


@router.post("/franchise/sim-championship")
def sim_championship(req: SimChampionshipRequest):
    """Simulate the national championship game (week 34 final)."""
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id format")

    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")

    national_tournament = franchise_doc.get("national_tournament", {})
    if not national_tournament:
        raise HTTPException(status_code=400, detail="National tournament not initialized")

    bracket = national_tournament.get("bracket", {})
    final = bracket.get("final", [])
    if not final or not final[0]:
        raise HTTPException(status_code=400, detail="Final round not ready")
    if final[0].get("winner"):
        raise HTTPException(status_code=400, detail="Championship already completed")

    matchup = final[0]
    home_id = ObjectId(matchup["home_team"])
    away_id = ObjectId(matchup["away_team"])
    home_doc = db.teams.find_one({"_id": home_id}, {"name": 1}) or {}
    away_doc = db.teams.find_one({"_id": away_id}, {"name": 1}) or {}
    home_name = home_doc.get("name", "")
    away_name = away_doc.get("name", "")
    if not home_name or not away_name:
        raise HTTPException(status_code=400, detail="Could not find team names")

    _champ_user_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)

    week = ft.EOS_NATIONAL_WEEKS[-1]
    try:
        gm = run_simulation(home_name, away_name)
        home_score = gm.score.get(home_name, 0)
        away_score = gm.score.get(away_name, 0)
        summary = summarize_game_state(gm)
        game_id = generate_game_id()
        summary["_id"] = game_id
        summary["franchise_id"] = str(franchise_id)
        summary["week"] = week
        db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
        stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(franchise_id))
        winner_id = home_id if home_score > away_score else away_id
        nat_final_meta = {
            "phase": "national",
            "round": 3,
            "matchup_index": 0,
            "away_id": away_id,
            "home_id": home_id,
        }
        ftp.record_tournament_game_result(
            franchise_doc,
            nat_final_meta,
            week=week,
            franchise_id_str=str(franchise_id),
            game_id=str(game_id),
            team1_id=away_id,
            team2_id=home_id,
            team1_score=away_score,
            team2_score=home_score,
            source="cpu_full",
            skip_games_upsert=True,
        )
        ftp.advance_national_bracket(franchise_doc)
        national_tournament = franchise_doc.get("national_tournament", {})
        champ_patch: dict[str, Any] = {
            "national_tournament": national_tournament,
            "eos_tournament_active": False,
            "week": 35,
        }
        ts_reset = _training_status_reset_after_advance_to_week(35)
        if ts_reset:
            champ_patch.update(ts_reset)
        db.franchises.update_one({"_id": franchise_id}, {"$set": champ_patch})
        refreshed = db.franchises.find_one({"_id": franchise_id})
        if refreshed:
            _persist_week_35_awards_if_needed(refreshed)
        maybe_award_franchise_win_geek_points(
            owner_user_id=franchise_doc.get("user_id"),
            user_team_id_str=user_team_id_str,
            winner_team_id=winner_id,
            week=week,
            eos_game_meta={"phase": "national", "round": 3},
        )
        maybe_award_franchise_loss_geek_points(
            owner_user_id=franchise_doc.get("user_id"),
            user_team_id_str=user_team_id_str,
            winner_team_id=winner_id,
            participant_team_ids=(away_id, home_id),
            week=week,
            eos_game_meta={"phase": "national", "round": 3},
        )
        maybe_award_franchise_eos_title_championship(
            owner_user_id=franchise_doc.get("user_id"),
            user_team_id_str=user_team_id_str,
            winner_team_id=winner_id,
            week=week,
            eos_game_meta={"phase": "national", "round": 3},
        )
        logger.info("✅ [EOS] National championship complete! Winner: %s", winner_id)
        return {
            "status": "success",
            "winner": str(winner_id),
            "winner_name": home_name if str(winner_id) == str(home_id) else away_name,
            "game_id": str(game_id),
            "home_team_id": str(home_id),
            "away_team_id": str(away_id),
            "home_team_name": home_name,
            "away_team_name": away_name,
            "home_score": home_score,
            "away_score": away_score,
        }
    except Exception as e:
        logger.error("❌ [EOS] Error simulating championship: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/franchise/finish-season")
def finish_season(req: FinishSeasonRequest):
    """Finish current season and start new season."""
    try:
        franchise_id = ObjectId(req.franchise_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid franchise_id format")
    
    franchise_doc = db.franchises.find_one({"_id": franchise_id})
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    if int(franchise_doc.get("week", 1) or 1) != 36:
        raise HTTPException(status_code=400, detail="Season transition is only available during week 36")

    transition_token = _ensure_season_transition_token(franchise_id, franchise_doc)
    if not transition_token:
        raise HTTPException(status_code=409, detail="Season transition is not ready")

    consume_result = db.franchises.update_one(
        {
            "_id": franchise_id,
            "week": 36,
            SEASON_TRANSITION_TOKEN_FIELD: transition_token,
        },
        {"$unset": {SEASON_TRANSITION_TOKEN_FIELD: ""}},
    )
    if consume_result.modified_count == 0:
        raise HTTPException(status_code=409, detail="Season transition has already been processed")

    try:
        from BackEnd.utils.franchise_championship_moments import (
            enqueue_banner_raise_if_user_won_national,
        )

        enqueue_banner_raise_if_user_won_national(franchise_doc)
    except Exception:
        logger.exception(
            "[CHAMP-MOMENT] banner_raise enqueue failed franchise_id=%s",
            str(franchise_id),
        )

    # Get current season
    current_season = franchise_doc.get("current_season", 1)
    next_season = current_season + 1
    rank_prestige_system_version = int(
        franchise_doc.get(RANK_PRESTIGE_SYSTEM_VERSION_FIELD, 1) or 1
    )

    from BackEnd.models.franchise_manager import FranchiseManager

    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id}))
    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(franchise_id)}))
    fpd_by_id = {doc["player_id"]: doc for doc in fpd_docs if doc.get("player_id")}
    week_35_results = franchise_doc.get(WEEK_35_RECRUITING_RESULTS_FIELD) or {}
    signed_players = list(week_35_results.get("signed_players") or [])
    zero_stats = _zero_stats_block()

    def advance_year(year_value: str | None) -> str:
        year = str(year_value or "").strip().lower()
        mapping = {
            "jh": "Freshman",
            "freshman": "Sophomore",
            "sophomore": "Junior",
            "junior": "Senior",
        }
        return mapping.get(year, str(year_value or "Freshman").title())

    next_fpd_docs: list[dict[str, Any]] = []
    returning_players_by_team: dict[str, list[str]] = defaultdict(list)
    returning_scholarships_by_team: dict[str, set[str]] = defaultdict(set)

    for ftd_doc in ftd_docs:
        team_id = str(ftd_doc.get("team_id"))
        scholarship_players = {str(player_id) for player_id in (ftd_doc.get("scholarship_players") or []) if player_id}
        # Active roster AND training-squad players both return to the active pool for
        # next season (advance a year), then compete again in Training Camp. Graduating
        # seniors drop from either list.
        returning_candidate_ids = (
            [str(player_id) for player_id in (ftd_doc.get("players") or []) if player_id]
            + [str(player_id) for player_id in (ftd_doc.get("training_squad_players") or []) if player_id]
        )
        seen_returning: set[str] = set()
        for player_id_str in returning_candidate_ids:
            if player_id_str in seen_returning:
                continue
            seen_returning.add(player_id_str)
            fpd_doc = fpd_by_id.get(player_id_str)
            if not fpd_doc:
                continue
            meta = (fpd_doc.get("meta") or {}).copy()
            year = _player_year_from_fpd_or_core(player_id_str, fpd_doc)
            if _is_graduating_year(year):
                continue
            meta["year"] = advance_year(year)
            next_doc = {
                "franchise_id": str(franchise_id),
                "player_id": player_id_str,
                "meta": meta,
                "season": zero_stats.copy(),
                "career": (fpd_doc.get("career") or zero_stats.copy()),
                "attributes": (fpd_doc.get("attributes") or {}).copy(),
                "position_ratings": (fpd_doc.get("position_ratings") or {}).copy(),
            }
            next_fpd_docs.append(next_doc)
            returning_players_by_team[team_id].append(player_id_str)
            if player_id_str in scholarship_players:
                returning_scholarships_by_team[team_id].add(player_id_str)

    signed_players_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signed_player in signed_players:
        team_id = str(signed_player.get("team_id") or "")
        if not team_id:
            continue
        signed_players_by_team[team_id].append(signed_player)
        name_parts = str(signed_player.get("name") or "").split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        next_fpd_docs.append({
            "franchise_id": str(franchise_id),
            "player_id": str(signed_player["player_id"]),
            "meta": {
                "first_name": first_name,
                "last_name": last_name,
                "team": signed_player.get("team_name", ""),
                "team_id": team_id,
                "height": signed_player.get("height"),
                "weight": signed_player.get("weight"),
                # Signed recruits/walk-ons enter the roster advanced one year:
                # JH -> Freshman, ..., Junior -> Senior.
                "year": advance_year(signed_player.get("year")),
                "jersey": signed_player.get("jersey"),
                "archetype": signed_player.get("archetype"),
            },
            "season": zero_stats.copy(),
            "career": zero_stats.copy(),
            "attributes": _normalize_new_franchise_player_attributes(
                signed_player.get("attributes") or {}
            ),
            "position_ratings": (signed_player.get("position_ratings") or {}).copy(),
        })

    next_fpd_map = {doc["player_id"]: doc for doc in next_fpd_docs}
    existing_ftd_by_team_id = {
        str(doc.get("team_id")): doc
        for doc in ftd_docs
        if doc.get("team_id")
    }

    def highest_rt(player_id: str) -> int:
        return int((_best_position((next_fpd_map.get(player_id) or {}).get("position_ratings") or {}).get("rating") or 0))

    next_ftd_state_by_team_id: dict[str, dict[str, Any]] = {}
    for ftd_doc in ftd_docs:
        team_id = str(ftd_doc.get("team_id"))
        roster = list(returning_players_by_team.get(team_id, []))
        scholarship_players = set(returning_scholarships_by_team.get(team_id, set()))
        pt_promise_players = []
        for signed_player in signed_players_by_team.get(team_id, []):
            player_id = str(signed_player["player_id"])
            roster.append(player_id)
            if signed_player.get("scholarship"):
                scholarship_players.add(player_id)
            if signed_player.get("playing_time"):
                pt_promise_players.append(player_id)
        ordered_roster = sorted(roster, key=highest_rt, reverse=True)
        total_player_attrs = sum(
            core_total_player_attrs((next_fpd_map.get(player_id) or {}).get("attributes") or {})
            for player_id in ordered_roster
        )
        existing_ftd = existing_ftd_by_team_id.get(team_id) or {}
        next_ftd_state_by_team_id[team_id] = {
            "team_object_id": ftd_doc["team_id"],
            "players": ordered_roster,
            "plays": _reset_team_play_scorers_for_new_season(existing_ftd.get("plays") or {}),
            "scholarship_players": sorted(scholarship_players, key=highest_rt, reverse=True),
            "training_squad_players": [],
            "playing_time_promise_players": pt_promise_players,
            "Recruits": {str(i): None for i in range(1, 21)},
            RECRUITING_ORDERS_WEEK_35_FIELD: {},
            "recruit_visit": None,
            "training_reports": {},
            "coaching_focus": carryover_coaching_focus_counts_for_new_season(
                existing_ftd.get("coaching_focus")
            ),
            "total_player_attrs": total_player_attrs,
            "prestige": int(existing_ftd.get("prestige", 0) or 0),
            "sos_avg": SOS_AVG_DEFAULT,
            "sos_rank_sum": 0.0,
            "sos_games_played": 0,
            "updated_at": datetime.utcnow(),
        }

    if rank_prestige_system_version >= FRANCHISE_RANK_PRESTIGE_SYSTEM_VERSION:
        preseason_inputs = [
            {
                "team_id": team_id,
                "prestige": state["prestige"],
                "total_player_attrs": state["total_player_attrs"],
                "sos_avg": state["sos_avg"],
            }
            for team_id, state in next_ftd_state_by_team_id.items()
        ]
        for ranked in rank_teams_for_week(preseason_inputs, week=0):
            state = next_ftd_state_by_team_id.get(str(ranked["team_id"]))
            if state is not None:
                state["natl_rank"] = int(ranked["natl_rank"])
    else:
        legacy_ranked = sorted(
            next_ftd_state_by_team_id.items(),
            key=lambda item: (
                -(int(item[1]["total_player_attrs"]) + int(item[1]["prestige"])),
                random.random(),
            ),
        )
        for rank_index, (_, state) in enumerate(legacy_ranked, start=1):
            state["natl_rank"] = rank_index

    for team_id, state in next_ftd_state_by_team_id.items():
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": state["team_object_id"]},
            {
                "$set": {
                    "players": state["players"],
                    "plays": state["plays"],
                    "scholarship_players": state["scholarship_players"],
                    "training_squad_players": state["training_squad_players"],
                    "playing_time_promise_players": state["playing_time_promise_players"],
                    "Recruits": state["Recruits"],
                    RECRUITING_ORDERS_WEEK_35_FIELD: state[RECRUITING_ORDERS_WEEK_35_FIELD],
                    "recruit_visit": state["recruit_visit"],
                    "training_reports": state["training_reports"],
                    "coaching_focus": state["coaching_focus"],
                    "total_player_attrs": state["total_player_attrs"],
                    "sos_avg": state["sos_avg"],
                    "sos_rank_sum": state["sos_rank_sum"],
                    "sos_games_played": state["sos_games_played"],
                    "updated_at": state["updated_at"],
                    **({"natl_rank": state["natl_rank"]} if "natl_rank" in state else {}),
                }
            },
        )

    franchise_players_data_collection.delete_many({"franchise_id": str(franchise_id)})
    if next_fpd_docs:
        franchise_players_data_collection.insert_many(next_fpd_docs)

    fm = FranchiseManager(db)
    fm.franchise_id = franchise_id
    schedule = fm.schedule_manager.generate_schedule()
    from BackEnd.models.recruit_sets import load_unused_set_or_generate
    _prev_used = (db.franchises.find_one({"_id": franchise_id}, {"used_recruit_set_ids": 1})
                  or {}).get("used_recruit_set_ids") or []
    recruits, used_recruit_set_id = load_unused_set_or_generate(
        db, fm.recruit_manager, _prev_used, count=300)
    region_team_ids = fm._build_region_team_map()

    franchise_recruits_data_collection.delete_many({"franchise_id": str(franchise_id)})
    frd_docs = [
        {
            "franchise_id": str(franchise_id),
            # stable id from the pre-built set (keys the portrait); uuid4 for dynamic recruits
            "recruit_id": recruit.get("recruit_id") or str(uuid.uuid4()),
            "name": recruit["name"],
            "attributes": recruit["attributes"],
            "position_ratings": recruit["position_ratings"],
            "height": recruit["height"],
            "weight": recruit["weight"],
            "archetype": recruit["archetype"],
            "year": recruit["year"],
            "Home Region": home_region,
            "Lean": fm._build_recruit_lean(home_region, region_team_ids),
            "created_at": recruit.get("created_at") or datetime.utcnow(),
        }
        for recruit in recruits
        for home_region in [random.choice(list(region_team_ids.keys()))]
    ]
    if frd_docs:
        franchise_recruits_data_collection.insert_many(frd_docs)

    db.games.delete_many({"franchise_id": str(franchise_id)})
    from BackEnd.practice_squad.stats import clear_ps_season_stats_for_franchise

    clear_ps_season_stats_for_franchise(str(franchise_id))
    awards_reset = {}
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {
            "current_season": next_season,
            "week": 1,
            # append the set consumed this rollover (never reused within the franchise)
            "used_recruit_set_ids": _prev_used + ([used_recruit_set_id] if used_recruit_set_id else []),
            "results": {},
            "season_inbox": [],
            "season_news": [],
            "practice_squad": {},
            "schedule": schedule,
            "eos_tournament_active": False,
            "conference_tournaments": {},
            "region_tournaments": {},
            "national_tournament": {},
            "recruiting_results": {},
            "recruiting_lean_updates_applied": {},
            "recruiting_performance_lean_applied": {},
            FCC_PENDING_NEW_LEAN_RECRUITS_FIELD: [],
            "week_35_recruiting_ran": False,
            WEEK_35_RECRUITING_RESULTS_FIELD: {},
            AWARDS_FIELD: awards_reset,
            "training_status.training_completed": False,
            "training_status.session_type": "preseason",
            "training_status.training_disabled_for_eos": False,
            "stats.top_10_points": [],
            "stats.top_10_rebounds": [],
            "stats.top_10_assists": [],
            "stats.top_10_blocks": [],
            "stats.top_10_steals": [],
            RANK_PRESTIGE_SYSTEM_VERSION_FIELD: rank_prestige_system_version,
            RANK_PRESTIGE_LAST_APPLIED_WEEK_FIELD: 0,
        }}
    )
    
    logger.info(f"✅ [FINISH SEASON] Started season {next_season}")
    
    return {"status": "success", "season": next_season, "week": 1}


# ============================================================================
# 🛠️ DEV MODE: Simulate Entire Regular Season (Temporary Development Feature)
# ============================================================================
# ⚠️  THIS IS A TEMPORARY DEVELOPMENT FEATURE
# ⚠️  To disable: Comment out the endpoint below (lines 2995-3150)
# ⚠️  To re-enable: Uncomment the endpoint
# ============================================================================

# ⚠️ DISABLED: Dev sim functionality commented out for testing
# class DevSimRegularSeasonRequest(BaseModel):
#     franchise_id: str


# @router.post("/franchise/dev-sim-regular-season")
# def dev_sim_regular_season(req: DevSimRegularSeasonRequest):
#     """
#     🛠️ DEV MODE ONLY: Simulate entire regular season (weeks 1-14) with auto-training and auto-lineups.
    
#     This endpoint streams progress updates via Server-Sent Events (SSE):
#     1. Loops through weeks 1-14
#     2. For each week:
#        - Auto-trains all teams (including user team) with default training allocations
#        - Auto-sets lineups for all teams from roster
#        - Simulates all games (user game + computer games)
#     3. Stops before week 15 (tournament)
#     
#     ⚠️  TEMPORARY DEVELOPMENT FEATURE - Comment out to disable
#     """
# #     import json
    # 
# #     def generate_progress():
# #         """Generator that yields SSE events with progress updates"""
# #         try:
            # franchise_id = ObjectId(req.franchise_id)
        # except Exception:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid franchise_id format'})}\n\n"
            # return
        # 
        # franchise_doc = db.franchises.find_one({"_id": franchise_id})
        # if not franchise_doc:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'Franchise not found'})}\n\n"
            # return
        # 
        # # Get user team info
        # user_team_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        # if not user_team_name or not user_team_object_id:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'User team not found in franchise'})}\n\n"
            # return
        # 
        # try:
            # user_team_id = ObjectId(user_team_object_id)
        # except Exception:
            # yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid user team ObjectId'})}\n\n"
            # return
        # 
        # schedule = franchise_doc.get("schedule", [])
        # franchise_teams = franchise_doc.get("franchise_teams", {})
        # 
        # # Get all team IDs in franchise
        # all_team_ids = [ObjectId(tid) for tid in franchise_teams.keys() if ObjectId.is_valid(tid)]
        # all_team_docs = {str(t["_id"]): t for t in db.teams.find({"_id": {"$in": all_team_ids}}, {"name": 1, "_id": 1})}
        # 
        # yield f"data: {json.dumps({'type': 'start', 'message': f'Starting regular season simulation for {user_team_name}', 'total_weeks': 14})}\n\n"
        # logger.info(f"🛠️ [DEV SIM] Starting regular season simulation for franchise {req.franchise_id}")
        # logger.info(f"🛠️ [DEV SIM] User team: {user_team_name} ({user_team_object_id})")
        # logger.info(f"🛠️ [DEV SIM] Total teams: {len(all_team_ids)}")
        # 
        # # Helper function to generate training data with correct point allocation
        # def get_training_data_for_week(week_num, franchise_doc):
            # """Generate training data with 30 points for first training, 24 for subsequent"""
            # # Check if this is the first training (week 1, no completed games)
            # results = franchise_doc.get("results", {})
            # has_completed_games = len(results) > 0
            # if not has_completed_games:
                # completed_game = db.games.find_one({
                    # "franchise_id": str(franchise_id),
                    # "is_final": True
                # })
                # has_completed_games = completed_game is not None
            # 
            # is_first_training = (week_num == 1 and not has_completed_games)
            # total_points = 30 if is_first_training else 24
            # 
            # # Balanced allocation: 30 points = 18 player + 8 team + 4 general
            # # Balanced allocation: 24 points = 14 player + 7 team + 3 general
            # if is_first_training:
                # # 30 points: 18 player + 8 team + 4 general
                # return {
                    # "player_drills": {
                        # "shooting": {"SC": 3, "SH": 3},  # 6 points
                        # "ball_handling": {"BH": 3},  # 3 points
                        # "defense": {"ID": 3, "OD": 3},  # 6 points
                        # "rebounding": {"RB": 3},  # 3 points
                        # # Total player: 18 points
                    # },
                    # "team_drills": {
                        # "offense": {"offensive_efficiency": 2},  # 2 points
                        # "defense": {"defensive_efficiency": 2},  # 2 points
                        # "fast_break": {"fb_efficiency": 2},  # 2 points
                        # "press_trap": {"pt_efficiency": 2},  # 2 points
                        # # Total team: 8 points
                    # },
                    # "general": {
                        # "team_chemistry": 2,  # 2 points
                        # "discipline": 1,  # 1 point
                        # "fight": 1  # 1 point
                        # # Total general: 4 points
                    # },
                    # "coaching_focus": "balanced",
                    # "playbook_training_mode": "current-playbooks"
                # }
            # else:
                # # 24 points: 14 player + 7 team + 3 general
                # return {
                    # "player_drills": {
                        # "shooting": {"SC": 2, "SH": 2},  # 4 points
                        # "ball_handling": {"BH": 2},  # 2 points
                        # "defense": {"ID": 2, "OD": 2},  # 4 points
                        # "rebounding": {"RB": 2},  # 2 points
                        # "athleticism": {"AG": 1, "ST": 1},  # 2 points
                        # # Total player: 14 points
                    # },
                    # "team_drills": {
                        # "offense": {"offensive_efficiency": 2},  # 2 points
                        # "defense": {"defensive_efficiency": 2},  # 2 points
                        # "fast_break": {"fb_efficiency": 2},  # 2 points
                        # "press_trap": {"pt_efficiency": 1},  # 1 point
                        # # Total team: 7 points
                    # },
                    # "general": {
                        # "team_chemistry": 1,  # 1 point
                        # "discipline": 1,  # 1 point
                        # "fight": 1  # 1 point
                        # # Total general: 3 points
                    # },
                    # "coaching_focus": "balanced",
                    # "playbook_training_mode": "current-playbooks"
                # }
        # 
        # # Simulate weeks 1-14
        # for week in range(1, 15):
            # yield f"data: {json.dumps({'type': 'week_start', 'week': week, 'message': f'Processing Week {week}...'})}\n\n"
            # logger.info(f"🛠️ [DEV SIM] Processing Week {week}...")
            # 
            # # Reload franchise doc to get latest state
            # franchise_doc = db.franchises.find_one({"_id": franchise_id})
            # current_week = franchise_doc.get("week", 1)
            # 
            # # Skip if already past this week
            # if current_week > week:
                # yield f"data: {json.dumps({'type': 'week_skip', 'week': week, 'message': f'Week {week} already completed, skipping'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week} already completed (current_week={current_week}), skipping")
                # continue
            # 
            # # Step 1: Auto-train all teams (including user team)
            # # Check if training already completed for this week (training_status is global)
            # franchise_doc = db.franchises.find_one({"_id": franchise_id})
            # training_status = franchise_doc.get("training_status", {})
            # if not (training_status.get("training_completed") and training_status.get("current_week") == week):
                # yield f"data: {json.dumps({'type': 'training_start', 'week': week, 'message': f'Week {week}: Training all teams...'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week}: Auto-training all teams...")
                # trained_count = 0
                # for team_id_str, team_doc in all_team_docs.items():
                    # team_name = team_doc.get("name", "")
                    # if not team_name:
                        # continue
                    # 
                    # try:
                        # # Get training data with correct point allocation for this week
                        # training_data = get_training_data_for_week(week, franchise_doc)
                        # 
                        # # Create training request
                        # training_req = FranchiseTrainingRequest(
                            # franchise_id=req.franchise_id,
                            # team_id=team_id_str,
                            # training_data=training_data
                        # )
                        # 
                        # # Run training (reuse existing endpoint logic)
                        # training_result = run_franchise_training(training_req)
                        # trained_count += 1
                        # yield f"data: {json.dumps({'type': 'training_progress', 'week': week, 'team': team_name, 'message': f'Trained {team_name}'})}\n\n"
                        # logger.info(f"🛠️ [DEV SIM] Week {week}: Trained {team_name} - {training_result.get('status', 'unknown')}")
                        # 
                    # except Exception as e:
                        # logger.error(f"🛠️ [DEV SIM] Week {week}: Error training {team_name}: {e}")
                        # import traceback
                        # logger.error(f"🛠️ [DEV SIM] Traceback: {traceback.format_exc()}")
                        # yield f"data: {json.dumps({'type': 'training_error', 'week': week, 'team': team_name, 'message': f'Error training {team_name}: {str(e)}'})}\n\n"
                        # # Continue with other teams even if one fails
                # yield f"data: {json.dumps({'type': 'training_complete', 'week': week, 'message': f'Week {week}: Training complete ({trained_count} teams)'})}\n\n"
            # else:
                # yield f"data: {json.dumps({'type': 'training_skip', 'week': week, 'message': f'Week {week}: Training already completed, skipping'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week}: Training already completed, skipping")
            # 
            # # Step 2: Get user's matchup for this week
            # week_games = schedule[week - 1] if week - 1 < len(schedule) else []
            # user_matchup = None
            # for away_id, home_id in week_games:
                # if away_id == user_team_id or home_id == user_team_id:
                    # away_doc = db.teams.find_one({"_id": away_id}, {"name": 1})
                    # home_doc = db.teams.find_one({"_id": home_id}, {"name": 1})
                    # user_matchup = {
                        # "home": home_doc.get("name", ""),
                        # "away": away_doc.get("name", ""),
                        # "home_id": str(home_id),
                        # "away_id": str(away_id),
                    # }
                    # break
            # 
            # if not user_matchup:
                # yield f"data: {json.dumps({'type': 'week_error', 'week': week, 'message': f'Week {week}: User matchup not found, skipping'})}\n\n"
                # logger.warning(f"🛠️ [DEV SIM] Week {week}: User matchup not found, skipping user game")
                # continue
            # 
            # # Step 3: Simulate user's game (with auto-lineup)
            # game_msg = f"Week {week}: Simulating {user_matchup['away']} @ {user_matchup['home']}..."
            # yield f"data: {json.dumps({'type': 'game_start', 'week': week, 'home': user_matchup['home'], 'away': user_matchup['away'], 'message': game_msg})}\n\n"
            # logger.info(f"🛠️ [DEV SIM] Week {week}: Simulating user game ({user_matchup['away']} @ {user_matchup['home']})...")
            # try:
                # # Build auto-lineups for both teams
                # from BackEnd.models.team_manager import TeamManager
                # home_team_manager = TeamManager(user_matchup["home"])
                # away_team_manager = TeamManager(user_matchup["away"])
                # 
                # home_lineup = build_lineup_from_mongo(home_team_manager)
                # away_lineup = build_lineup_from_mongo(away_team_manager)
                # 
                # # Convert lineups to player ID format
                # home_lineup_ids = {pos: player.player_id for pos, player in home_lineup.items()}
                # away_lineup_ids = {pos: player.player_id for pos, player in away_lineup.items()}
                # 
                # yield f"data: {json.dumps({'type': 'game_simulating', 'week': week, 'message': 'Running game simulation...'})}\n\n"
                # 
                # # Run full game simulation
                # gm = run_simulation(
                    # user_matchup["home"],
                    # user_matchup["away"],
                    # home_lineup_ids,
                    # away_lineup_ids
                # )
                # 
                # # Get final scores
                # home_score = gm.score.get(user_matchup["home"], 0)
                # away_score = gm.score.get(user_matchup["away"], 0)
                # 
                # result_msg = f"Final: {user_matchup['away']} {away_score}, {user_matchup['home']} {home_score}"
                # yield f"data: {json.dumps({'type': 'game_result', 'week': week, 'home': user_matchup['home'], 'away': user_matchup['away'], 'home_score': home_score, 'away_score': away_score, 'message': result_msg})}\n\n"
                # 
                # # Save game to database
                # summary = summarize_game_state(gm)
                # game_id = generate_game_id()
                # summary["_id"] = game_id
                # summary["franchise_id"] = str(franchise_id)
                # summary["week"] = week
                # summary["is_final"] = True
                # db.games.update_one({"_id": game_id}, {"$set": summary}, upsert=True)
                # 
                # # Finalize game stats
                # yield f"data: {json.dumps({'type': 'game_finalizing', 'week': week, 'message': 'Finalizing game stats...'})}\n\n"
                # stat_updater.finalize_game(game_id, mode="franchise", franchise_id=str(franchise_id))
                # 
                # # Determine winner
                # winner_id = user_matchup["home_id"] if home_score > away_score else user_matchup["away_id"]
                # 
                # # Complete week (this will simulate computer games and advance week)
                # yield f"data: {json.dumps({'type': 'week_completing', 'week': week, 'message': 'Completing week (simulating computer games)...'})}\n\n"
                # complete_week_req = CompleteWeekRequest(
                    # franchise_id=req.franchise_id,
                    # week=week,
                    # result=GameResult(
                        # team1_id=user_matchup["away_id"],
                        # team2_id=user_matchup["home_id"],
                        # team1_score=away_score,
                        # team2_score=home_score
                    # ),
                    # game_id=str(game_id),
                    # game_document=summary
                # )
                # 
                # complete_week(complete_week_req)
                # yield f"data: {json.dumps({'type': 'week_complete', 'week': week, 'message': f'Week {week} complete!'})}\n\n"
                # logger.info(f"🛠️ [DEV SIM] Week {week}: Completed user game and all computer games")
                # 
            # except Exception as e:
                # error_msg = f"Week {week}: Error simulating user game: {str(e)}"
                # yield f"data: {json.dumps({'type': 'week_error', 'week': week, 'message': error_msg})}\n\n"
                # logger.error(f"🛠️ [DEV SIM] Week {week}: Error simulating user game: {e}")
                # import traceback
                # logger.error(f"🛠️ [DEV SIM] Traceback: {traceback.format_exc()}")
                # # Continue to next week even if this one fails
        # 
        # # Reload franchise doc to get final state
        # franchise_doc = db.franchises.find_one({"_id": franchise_id})
        # final_week = franchise_doc.get("week", 1)
        # 
        # logger.info(f"🛠️ [DEV SIM] Regular season simulation complete! Final week: {final_week}")
        # yield f"data: {json.dumps({'type': 'complete', 'status': 'success', 'final_week': final_week, 'message': f'Simulation complete! Current week: {final_week}'})}\n\n"
    # 
    # return StreamingResponse(
        # generate_progress(),
        # media_type="text/event-stream",
        # headers={
            # "Cache-Control": "no-cache",
            # "Connection": "keep-alive",
            # "X-Accel-Buffering": "no"  # Disable nginx buffering
        # }
    # )

# ============================================================================
# 🛠️ END DEV MODE FEATURE
# ============================================================================
