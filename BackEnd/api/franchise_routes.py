from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from starlette.responses import Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from pathlib import Path
from bson import ObjectId
import logging
import math
import random
import re
import uuid
from typing import Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from BackEnd.main import run_simulation

from BackEnd.db import (
    db,
    franchise_state_collection,
    franchise_team_data_collection,
    franchise_players_data_collection,
    franchise_recruits_data_collection,
)
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils import stat_updater
from BackEnd.utils.team_stats_aggregator import aggregate_team_stats_from_players
from BackEnd.models.franchise_manager import FranchiseManager, ScheduleManager
from BackEnd.tournament.bracket_engine import get_round_name
from BackEnd.tournament import franchise_tournament as ft
from BackEnd.utils.db_utils import build_lineup_from_mongo
from BackEnd.utils.roster_builder import build_roster_players
from BackEnd.utils.command_center_data import build_command_center_base
from BackEnd.utils.game_id_utils import generate_game_id
from BackEnd.models.training_execution_v2 import TEAM_ATTR_CLAMPS, PLAYER_ATTR_CLAMP
from BackEnd.models.player import Player
from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.eog_attr_rules import (
    build_eog_inputs_from_game_doc,
    calculate_fb_opp_modifier_change,
    calculate_pt_opp_modifier_change,
)
from BackEnd.utils.auth import get_current_user
from BackEnd.utils.ownership import verify_franchise_owned_by_user
from BackEnd.utils.position_ratings import compute_position_ratings
from BackEnd.models.franchise_manager import load_franchise_names

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"
RECRUITING_ORDERS_WEEK_35_FIELD = "recruiting_orders_week_35"
WEEK_35_RECRUITING_RESULTS_FIELD = "week_35_recruiting_results"
AWARDS_FIELD = "awards"
WEEK_35_RECRUITING_POINTS_BUDGET = 20


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
) -> None:
    """
    Run update_team_attributes_after_game once for this game and persist
    team_attribute_changes on the game doc so the box score can display them.
    game_id: string or ObjectId (game doc _id).
    """
    try:
        gid = game_id
        logger.warning(
            "🧭 [EOG-CALL-SITE] About to call update_team_attributes_after_game game_id=%s gid=%s franchise_id=%s home=%s away=%s winner=%s loser=%s",
            str(game_id),
            str(gid),
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
        game_id_str = str(game_id) if not isinstance(game_id, str) else game_id
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
            home_team_id: {"shot_threshold": +5, "discipline": -1, ...},
            away_team_id: {"shot_threshold": +12, "discipline": -2, ...}
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
    
    # Calculate attribute changes for each team. team_object_id = ObjectId for FTD; team_id_label = string for logging.
    def calculate_attr_changes(team_object_id, team_id_label, is_winner, team_totals, opponent_totals, team_scouting, opponent_scouting):
        """Calculate attribute changes for a team."""
        changes = {}
        
        # Calculate FG%
        fgm = team_totals.get("FGM", 0)
        fga = team_totals.get("FGA", 0)
        fg_pct = (fgm / fga * 100) if fga > 0 else 0
        
        # Calculate TREB
        treb = team_totals.get("DREB", 0) + team_totals.get("OREB", 0)
        opp_treb = opponent_totals.get("DREB", 0) + opponent_totals.get("OREB", 0)
        
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
        
        # shot_threshold: winning team by FG%; losing team by FG% (different ranges)
        if is_winner:
            if fg_pct > 50:
                changes["shot_threshold"] = random.randint(-20, -10)   # −(10 to 20)
            elif fg_pct > 45:
                changes["shot_threshold"] = random.randint(-10, 0)    # −(0 to 10)
            else:
                changes["shot_threshold"] = random.randint(0, 10)     # +(0 to 10)
        else:
            if fg_pct > 50:
                changes["shot_threshold"] = random.randint(-15, -5)   # −(5 to 15)
            elif fg_pct > 45:
                changes["shot_threshold"] = random.randint(-5, 0)    # −(0 to 5)
            else:
                changes["shot_threshold"] = random.randint(0, 15)     # +(0 to 15)
        
        # discipline: both teams same criteria — if team (F+TO) < opponent (F+TO) then +(0,1), else −(1 to 3)
        team_f_plus_to = team_totals.get("F", 0) + team_totals.get("TO", 0)
        opp_f_plus_to = opponent_totals.get("F", 0) + opponent_totals.get("TO", 0)
        discipline_branch = "f_plus_to_ge_opp"
        if team_f_plus_to < opp_f_plus_to:
            discipline_branch = "f_plus_to_lt_opp"
            changes["discipline"] = random.randint(0, 1)
        else:
            changes["discipline"] = random.randint(-3, -1)
        logger.warning(
            "🧪 [EOG-BRANCH] team=%s attr=discipline branch=%s team_f_plus_to=%s opp_f_plus_to=%s raw_change=%s",
            str(team_id_label),
            discipline_branch,
            team_f_plus_to,
            opp_f_plus_to,
            changes.get("discipline"),
        )
        
        # fight: winning +(0, 1), losing +(−3 to −1)
        if is_winner:
            changes["fight"] = random.randint(0, 1)
        else:
            changes["fight"] = random.randint(-3, -1)
        
        # rebound_modifier
        if treb > (opp_treb + 5):
            changes["rebound_modifier"] = random.uniform(0, 0.1)
        elif treb < (opp_treb - 5):
            changes["rebound_modifier"] = random.uniform(-0.1, 0)
        else:
            changes["rebound_modifier"] = random.uniform(-0.05, 0.05)
        
        # offensive_efficiency: both teams +(−2, −1)
        changes["offensive_efficiency"] = random.randint(-2, -1)
        
        # defensive_efficiency: both teams +(−2, −1)
        changes["defensive_efficiency"] = random.randint(-2, -1)
        
        # fb_efficiency
        if team_scouting["fb_rate"] > 60:
            changes["fb_efficiency"] = random.randint(0, 1)
        else:
            changes["fb_efficiency"] = random.randint(-2, -1)
        
        # fb_opp_modifier
        changes["fb_opp_modifier"] = calculate_fb_opp_modifier_change(opponent_scouting)
        logger.warning(
            "🧪 [EOG-BRANCH] team=%s attr=fb_opp_modifier opp_fb_rate=%.2f opp_fb_entries=%s raw_change=%s",
            str(team_id_label),
            float(opponent_scouting.get("fb_rate", 0)),
            opponent_scouting.get("fb_entries", 0),
            changes.get("fb_opp_modifier"),
        )
        
        # pt_efficiency
        if team_scouting["pt_combined_rate"] > 60:
            changes["pt_efficiency"] = random.randint(1, 2)
        elif team_scouting["pt_combined_rate"] < 30:
            changes["pt_efficiency"] = random.randint(-3, -1)
        else:
            changes["pt_efficiency"] = random.randint(-1, 0)
        
        # pt_opp_modifier
        changes["pt_opp_modifier"] = calculate_pt_opp_modifier_change(opponent_scouting)
        logger.warning(
            "🧪 [EOG-BRANCH] team=%s attr=pt_opp_modifier opp_pt_rate=%.2f opp_pt_attempts=%s opp_hct=%s/%s opp_fcp=%s/%s raw_change=%s",
            str(team_id_label),
            float(opponent_scouting.get("pt_combined_rate", 0)),
            opponent_scouting.get("pt_total_attempts", 0),
            opponent_scouting.get("hct_success", 0),
            opponent_scouting.get("hct_used", 0),
            opponent_scouting.get("fcp_success", 0),
            opponent_scouting.get("fcp_used", 0),
            changes.get("pt_opp_modifier"),
        )
        
        # team_chemistry
        score_delta = winner_score - loser_score
        if is_winner:
            if score_delta < 4:
                changes["team_chemistry"] = random.randint(1, 2)
            elif score_delta < 10:
                changes["team_chemistry"] = random.randint(1, 3)
            else:
                changes["team_chemistry"] = random.randint(1, 4)
        else:
            if score_delta < 4:
                changes["team_chemistry"] = random.randint(-2, -1)
            elif score_delta < 10:
                changes["team_chemistry"] = random.randint(-3, -1)
            else:
                changes["team_chemistry"] = random.randint(-6, -2)

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
        home_scouting, away_scouting
    ) if home_oid else {}
    away_changes = calculate_attr_changes(
        away_oid, away_team_id, away_is_winner, away_totals, home_totals,
        away_scouting, home_scouting
    ) if away_oid else {}
    
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
        "authoritarian-teamwork",
        "systems-coach",
        "systems-coach-offense",
        "systems-coach-defense",
        "systems-coach-fast-breaks",
        "systems-coach-press-trap",
        "player-maximizer",
        "player-maximizer-top-3",
        "player-maximizer-attributes-4-6",
        "player-maximizer-custom",
        "player-maximizer-opportunity",
        "culture-builder",
        "culture-builder-inspire",
        "culture-builder-community",
        "culture-builder-teamwork",
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
            {"$or": [{"_id": team_id}, {"name": team_id}, {"code": team_id}]}
        )
        if not doc:
            # Fallback: canonical key (e.g. LANCASTER, SOUTH_LANCASTER) -> resolve via name (e.g. "Lancaster", "South Lancaster")
            # Frontend may send canonical ids from game doc when URL params are missing (e.g. Play Quarter)
            name_from_canonical = team_id.replace("_", " ").title()
            doc = db.teams.find_one({"name": name_from_canonical})
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


def _run_distant_game_sim(home_combined: int, away_combined: int) -> Tuple[int, int]:
    """
    Lightweight sim for distant (non-user-conference) games.
    Uses win probability roll, margin from dominance buckets, and clamped final scores.
    Returns (home_score, away_score).
    See docs/docs_1_systems/06_GMO_Supporting_Systems/Distant_Game_Sim_System.md
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
    }
    if not franchise_doc or not user_team_id_str or week not in ft.EOS_WEEKS:
        return status

    scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)
    week_games_meta = ft.get_eos_week_games(franchise_doc, week)
    found = ft.find_user_game_in_eos_week(week_games_meta, user_team_id_str)
    if found:
        status["has_game_this_week"] = True
        status["active_this_week"] = True

    if week in ft.EOS_CONFERENCE_WEEKS:
        status["phase"] = "conference"
        status["eliminated_from_current_phase"] = not status["has_game_this_week"]
        return status

    if week in ft.EOS_REGION_WEEKS:
        status["phase"] = "region"
        user_region = scope.get("region")
        rt = (franchise_doc.get("region_tournaments") or {}).get(user_region or "", {})
        final_list = rt.get("final", []) or []
        final_matchup = final_list[0] if final_list else {}
        final_has_user = (
            str(final_matchup.get("away_team")) == user_team_id_str
            or str(final_matchup.get("home_team")) == user_team_id_str
        )
        final_unplayed = not final_matchup.get("winner")
        if week == ft.EOS_REGION_WEEKS[0] and not status["has_game_this_week"] and final_has_user and final_unplayed:
            status["has_bye_this_week"] = True
            status["active_this_week"] = True
        elif not status["has_game_this_week"]:
            status["eliminated_from_current_phase"] = True
        return status

    if week in ft.EOS_NATIONAL_WEEKS:
        status["phase"] = "national"
        status["eliminated_from_current_phase"] = not status["has_game_this_week"]
        return status

    return status


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
        week_games_meta = ft.get_eos_week_games(franchise_doc, manager.week)
        found = ft.find_user_game_in_eos_week(week_games_meta, str(user_team_id))
        if found:
            _, g = found
            home_id = g["home_id"]
            away_id = g["away_id"]
            home_doc = db.teams.find_one({"_id": home_id}, {"name": 1})
            away_doc = db.teams.find_one({"_id": away_id}, {"name": 1})
            matchup = {
                "home": home_doc.get("name", "") if home_doc else "",
                "away": away_doc.get("name", "") if away_doc else "",
                "home_id": str(home_id),
                "away_id": str(away_id),
                "week": manager.week,
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
    )

    return {"status": "success"}


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

    schedule = franchise_doc.get("schedule", [])
    eos_active = bool(
        franchise_doc.get("eos_tournament_active")
        and (franchise_doc.get("conference_tournaments") or franchise_doc.get("region_tournaments") or franchise_doc.get("national_tournament"))
    )
    eos_current_round = None
    week_games_meta = None
    _u_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    user_eos_sim_scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)
    if req.week in ft.EOS_WEEKS and eos_active:
        week_games_meta = ft.get_eos_week_games(franchise_doc, req.week)
        week_games = [(g["away_id"], g["home_id"]) for g in week_games_meta]
        eos_current_round = req.week - 26 if req.week <= 29 else (req.week - 29 if req.week <= 31 else req.week - 31)
    elif req.week <= ScheduleManager.REGULAR_SEASON_WEEKS:
        if req.week < 1 or req.week > len(schedule):
            raise HTTPException(status_code=400, detail="Invalid week")
        week_games = schedule[req.week - 1]
    else:
        raise HTTPException(status_code=400, detail="Invalid week")
    results = []

    user = req.result
    team1_id = _normalize_team_id(user.team1_id)
    team2_id = _normalize_team_id(user.team2_id)

    # ✅ SS&S: Use provided game_id if available (this is the actual gameplay document with box_score)
    user_game_id = req.game_id
    user_res = _save_game_result(team1_id, team2_id, user.team1_score, user.team2_score, req.week, franchise_id=req.franchise_id, game_id=user_game_id)
    results.append({
        "away_id": user_res["team1_id"],
        "home_id": user_res["team2_id"],
        "away_score": user_res["team1_score"],
        "home_score": user_res["team2_score"],
    })

    # ✅ EOS (weeks 27–34): save user's game result to the correct bracket (conference/region/national)
    if week_games_meta and user_game_id:
        found = ft.find_user_game_in_eos_week(week_games_meta, user_team_id_str)
        if found:
            _, g = found
            winner_id = team1_id if user.team1_score > user.team2_score else team2_id
            home_id_g = g["home_id"]
            score = {
                "home": user.team1_score if str(team1_id) == str(home_id_g) else user.team2_score,
                "away": user.team2_score if str(team1_id) == str(home_id_g) else user.team1_score,
            }
            if g["phase"] == "conference":
                ft.save_conference_game_result(
                    franchise_doc, g["conference"], g["round"], g["matchup_index"],
                    str(user_game_id), str(winner_id), score,
                )
            elif g["phase"] == "region":
                ft.save_region_game_result(
                    franchise_doc, g["region"], g["round"], g["matchup_index"],
                    str(user_game_id), str(winner_id), score,
                )
            elif g["phase"] == "national":
                ft.save_national_game_result(
                    franchise_doc, g["round"], g["matchup_index"],
                    str(user_game_id), str(winner_id), score,
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
                incoming_set = {k: v for k, v in summary.items() if k != "_id"}
                incoming_set["franchise_id"] = str(req.franchise_id)
                incoming_set["week"] = req.week
                user_game_id_str = str(user_game_id)
                db.games.update_one(
                    {"_id": user_game_id_str},
                    {"$set": incoming_set},
                    upsert=True,
                )
                if ObjectId.is_valid(user_game_id_str):
                    # If a legacy ObjectId duplicate exists, sync it too.
                    db.games.update_one(
                        {"_id": ObjectId(user_game_id_str)},
                        {"$set": incoming_set},
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
        )
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
                )
            else:
                logger.error(f"❌ [COMPLETE_WEEK] User game found but _id is empty: {user_game}")
        else:
            logger.error(f"❌ [COMPLETE_WEEK] User's game not found in games collection. Query: week={req.week}, team1_id={team1_id}, team2_id={team2_id}, franchise_id={req.franchise_id}")

    # Distant game sim: batch-load FTD (prestige, total_player_attrs) and team conferences for partition
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "prestige": 1, "total_player_attrs": 1},
    ))
    ftd_by_team_id = {str(d["team_id"]): d for d in ftd_docs if d.get("team_id")}
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
            "week": req.week,
            "franchise_id": str(req.franchise_id),
            "$or": [
                {"team1_id": away_id, "team2_id": home_id},
                {"team1_id": home_id, "team2_id": away_id},
            ],
        })
        if existing:
            results.append({
                "away_id": str(existing["team1_id"]),
                "home_id": str(existing["team2_id"]),
                "away_score": existing["team1_score"],
                "home_score": existing["team2_score"],
            })
            continue

        if week_games_meta and idx < len(week_games_meta):
            g = week_games_meta[idx]
            if not _should_use_tbt_for_eos_game(req.week, g, user_eos_sim_scope):
                home_ftd = ftd_by_team_id.get(str(home_id), {})
                away_ftd = ftd_by_team_id.get(str(away_id), {})
                home_combined = (home_ftd.get("prestige") or 0) + int(0.1 * (home_ftd.get("total_player_attrs") or 0)) + 100
                away_combined = (away_ftd.get("prestige") or 0) + int(0.1 * (away_ftd.get("total_player_attrs") or 0))
                home_score, away_score = _run_distant_game_sim(home_combined, away_combined)
                results.append({
                    "away_id": str(away_id),
                    "home_id": str(home_id),
                    "away_score": away_score,
                    "home_score": home_score,
                })
                _save_game_result(away_id, home_id, away_score, home_score, req.week, franchise_id=req.franchise_id, game_id=None)
                winner_id = home_id if home_score > away_score else away_id
                if g["phase"] == "conference":
                    ft.save_conference_game_result(
                        franchise_doc, g["conference"], g["round"], g["matchup_index"],
                        "", str(winner_id), {"home": home_score, "away": away_score},
                    )
                elif g["phase"] == "region":
                    ft.save_region_game_result(
                        franchise_doc, g["region"], g["round"], g["matchup_index"],
                        "", str(winner_id), {"home": home_score, "away": away_score},
                    )
                elif g["phase"] == "national":
                    ft.save_national_game_result(
                        franchise_doc, g["round"], g["matchup_index"],
                        "", str(winner_id), {"home": home_score, "away": away_score},
                    )
                continue

        # Distant sim: regular season only; neither team in user's conference → lightweight sim (no game doc, no EOG)
        away_conf = team_id_to_conference.get(str(away_id))
        home_conf = team_id_to_conference.get(str(home_id))
        is_distant = (
            eos_current_round is None
            and user_conference is not None
            and away_conf != user_conference
            and home_conf != user_conference
        )
        if is_distant:
            home_ftd = ftd_by_team_id.get(str(home_id), {})
            away_ftd = ftd_by_team_id.get(str(away_id), {})
            home_combined = (home_ftd.get("prestige") or 0) + int(0.1 * (home_ftd.get("total_player_attrs") or 0)) + 100
            away_combined = (away_ftd.get("prestige") or 0) + int(0.1 * (away_ftd.get("total_player_attrs") or 0))
            home_score, away_score = _run_distant_game_sim(home_combined, away_combined)
            results.append({
                "away_id": str(away_id),
                "home_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
            })
            continue

        away_doc = db.teams.find_one({"_id": away_id}, {"name": 1}) or {}
        home_doc = db.teams.find_one({"_id": home_id}, {"name": 1}) or {}
        home_name = home_doc.get("name", "")
        away_name = away_doc.get("name", "")
        try:
            gm = run_simulation(home_name, away_name)
            away_score = gm.score.get(away_name, 0)
            home_score = gm.score.get(home_name, 0)
            summary = summarize_game_state(gm)
            from BackEnd.utils.game_id_utils import generate_game_id
            computer_game_id = generate_game_id()
            summary["_id"] = computer_game_id
            summary["franchise_id"] = str(req.franchise_id)
            summary["week"] = req.week
            db.games.update_one({"_id": computer_game_id}, {"$set": summary}, upsert=True)
            stat_updater.finalize_game(
                computer_game_id, mode="franchise", franchise_id=req.franchise_id
            )
            sim_res = _save_game_result(away_id, home_id, away_score, home_score, req.week, franchise_id=req.franchise_id, game_id=computer_game_id)
            # Run team attribute update once for this computer game and set on doc for box score display
            home_id_str = _normalize_team_id_to_string(home_id) or str(home_id)
            away_id_str = _normalize_team_id_to_string(away_id) or str(away_id)
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
            )
            if week_games_meta and idx < len(week_games_meta):
                g = week_games_meta[idx]
                winner_id = home_id if home_score > away_score else away_id
                score = {"home": home_score, "away": away_score}
                if g["phase"] == "conference":
                    ft.save_conference_game_result(
                        franchise_doc, g["conference"], g["round"], g["matchup_index"],
                        str(computer_game_id), str(winner_id), score,
                    )
                elif g["phase"] == "region":
                    ft.save_region_game_result(
                        franchise_doc, g["region"], g["round"], g["matchup_index"],
                        str(computer_game_id), str(winner_id), score,
                    )
                elif g["phase"] == "national":
                    ft.save_national_game_result(
                        franchise_doc, g["round"], g["matchup_index"],
                        str(computer_game_id), str(winner_id), score,
                    )
        except Exception:
            away_score = random.randint(50, 90)
            home_score = random.randint(50, 90)
            sim_res = _save_game_result(away_id, home_id, away_score, home_score, req.week, franchise_id=req.franchise_id)
        results.append({
            "away_id": sim_res["team1_id"],
            "home_id": sim_res["team2_id"],
            "away_score": sim_res["team1_score"],
            "home_score": sim_res["team2_score"],
        })

    existing_results = franchise_doc.get("results", {})
    existing_results[str(req.week)] = results
    _apply_complete_week_recruiting_lean_updates(franchise_doc, req.week, results)
    
    # Reset training status for next week
    next_week = req.week + 1
    
    # ✅ EOS TOURNAMENT: Initialize tournament after week 26 (regular season) completion
    update_fields = {
        "results": existing_results,
        "week": next_week,
        "training_status.training_completed": False,
        "training_status.session_type": "in-season"
    }
    
    if req.week == ScheduleManager.REGULAR_SEASON_WEEKS:
        # Regular season complete - initialize Conference Tournaments (EOS weeks 27–34)
        ftd_docs = list(franchise_team_data_collection.find(
            {"franchise_id": franchise_id},
            {"team_id": 1}
        ))
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
    elif req.week in ft.EOS_WEEKS:
        # EOS week: advance brackets and set next week (or init region/national)
        next_week = req.week + 1
        if req.week in ft.EOS_CONFERENCE_WEEKS:
            for c in range(1, 17):
                advanced, champ = ft.advance_conference_bracket(franchise_doc, c)
            if req.week == ft.EOS_CONFERENCE_WEEKS[-1]:
                eos_team_ids = [d["team_id"] for d in franchise_team_data_collection.find(
                    {"franchise_id": franchise_id}, {"team_id": 1}
                ) if d.get("team_id")]
                region_tournaments = ft.initialize_region_tournaments(
                    franchise_doc, db.teams, team_ids=eos_team_ids
                )
                update_fields["region_tournaments"] = region_tournaments
                next_week = ft.EOS_REGION_WEEKS[0]
            update_fields["week"] = next_week
            update_fields["conference_tournaments"] = franchise_doc.get("conference_tournaments", {})
        elif req.week in ft.EOS_REGION_WEEKS:
            if req.week == ft.EOS_REGION_WEEKS[-1]:
                region_champions = ft.get_region_champions(franchise_doc)
                ftd_docs = list(franchise_team_data_collection.find(
                    {"franchise_id": franchise_id}, {"team_id": 1}
                ))
                team_ids = [d["team_id"] for d in ftd_docs if d.get("team_id")]
                national_tournament = ft.initialize_national_tournament(
                    franchise_doc, db.teams, region_champions,
                    franchise_doc.get("results", {}), team_ids,
                )
                update_fields["national_tournament"] = national_tournament
                next_week = ft.EOS_NATIONAL_WEEKS[0]
            else:
                next_week = ft.EOS_REGION_WEEKS[1]
            update_fields["week"] = next_week
            update_fields["region_tournaments"] = franchise_doc.get("region_tournaments", {})
        elif req.week in ft.EOS_NATIONAL_WEEKS:
            advanced, champion = ft.advance_national_bracket(franchise_doc)
            update_fields["national_tournament"] = franchise_doc.get("national_tournament", {})
            if req.week == ft.EOS_NATIONAL_WEEKS[-1]:
                update_fields["eos_tournament_active"] = False
                next_week = 35
            else:
                next_week = ft.EOS_NATIONAL_WEEKS[ft.EOS_NATIONAL_WEEKS.index(req.week) + 1]
            update_fields["week"] = next_week
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": update_fields},
    )
    if update_fields.get("week") == 35:
        refreshed = db.franchises.find_one({"_id": franchise_id})
        if refreshed:
            _persist_week_35_awards_if_needed(refreshed)

    id_to_name = {str(t["_id"]): t.get("name", "") for t in db.teams.find({}, {"name": 1})}
    scoreboard = []
    for r in results:
        scoreboard.append({
            "team1": id_to_name.get(r["away_id"], r["away_id"]),
            "team2": id_to_name.get(r["home_id"], r["home_id"]),
            "team1_score": r["away_score"],
            "team2_score": r["home_score"],
        })

    return {"week": req.week, "results": scoreboard}


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
                    training_status = franchise_doc.get("training_status", {})
                    training_completed = training_status.get("training_completed", False)
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
        response["user_conference"] = team_doc.get("conference")
        response["user_region"] = team_doc.get("region", "")
        # Rankings list for Rankings tab: all FTD teams with natl_rank and team name, sorted by natl_rank
        if franchise_id and franchise_doc:
            try:
                fid = franchise_doc["_id"]
                ftd_rank_docs = list(franchise_team_data_collection.find(
                    {"franchise_id": fid},
                    {"team_id": 1, "natl_rank": 1}
                ))
                if ftd_rank_docs:
                    team_ids = [d["team_id"] for d in ftd_rank_docs if d.get("team_id") is not None]
                    teams_docs = {str(t["_id"]): t for t in db.teams.find(
                        {"_id": {"$in": team_ids}},
                        {"name": 1, "primary_color": 1, "conference": 1}
                    )}
                    rankings = [
                        {
                            "natl_rank": d.get("natl_rank", 128),
                            "team_name": teams_docs.get(str(d["team_id"]), {}).get("name", "?"),
                            "primary_color": teams_docs.get(str(d["team_id"]), {}).get("primary_color") or "#000000",
                            "conference": teams_docs.get(str(d["team_id"]), {}).get("conference"),
                        }
                        for d in ftd_rank_docs
                    ]
                    rankings.sort(key=lambda x: x["natl_rank"])
                    response["rankings"] = rankings
                else:
                    response["rankings"] = []
            except Exception as e:
                logger.debug("rankings for FCC: %s", e)
                response["rankings"] = []
        else:
            response["rankings"] = []
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
            except Exception as e:
                logger.debug("fcc lean recruits: %s", e)
                response["lean_recruits"] = []
                response["team_name_map"] = {}
                response["week_35_user_recruits"] = []
        else:
            response["lean_recruits"] = []
            response["team_name_map"] = {}
            response["week_35_user_recruits"] = []
        response["training_status"] = (
            {"training_completed": training_completed, "session_type": session_type}
            if franchise_id and franchise_doc else {}
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
        if eos_tournament_active or post_eos_bracket_history_visible:
            response["eos_tournament_active"] = True
            response["conference_tournaments"] = franchise_doc.get("conference_tournaments")
            response["region_tournaments"] = franchise_doc.get("region_tournaments")
            response["national_tournament"] = national_tournament
            # Derive single eos_tournament (old shape) for FCC bracket display: pick current phase by week
            week_val = week if week is not None else 1
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
        user_eliminated = training_disabled_for_eos
        tournament_complete = bool(national_tournament.get("champion")) if national_tournament else False
        user_has_bye = bool(eos_status.get("has_bye_this_week", False)) if eos_status else False
        offer_sim_rest = (user_eliminated or user_has_bye) and eos_tournament_active and not tournament_complete
        response["user_eliminated"] = user_eliminated
        response["offer_sim_rest"] = offer_sim_rest
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
        id_to_name = {t["_id"]: t["name"] for t in db.teams.find({}, {"name": 1})}
        matchup_map = {}
        eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
        eos_has_state = bool(
            franchise_doc.get("conference_tournaments") or franchise_doc.get("region_tournaments") or franchise_doc.get("national_tournament")
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
                        home_name = id_to_name.get(hid, "")
                        away_name = id_to_name.get(aid, "")
                        matchup_map[str(aid)] = f"at {home_name}"
                        matchup_map[str(hid)] = f"vs {away_name}"
                    except Exception:
                        continue
        else:
            next_games = schedule[week - 1] if week - 1 < len(schedule) else []
            for away_id, home_id in next_games:
                home_name = id_to_name.get(home_id, "")
                away_name = id_to_name.get(away_id, "")
                matchup_map[str(away_id)] = f"at {home_name}"
                matchup_map[str(home_id)] = f"vs {away_name}"
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
def season_schedule(franchise_id: str, conference: Optional[int] = None):
    import time
    start_time = time.time()
    # logger.info(f"⏱️ [PERF] /franchise/schedule START - franchise_id={franchise_id}")
    
    # ✅ PERFORMANCE: Only fetch needed fields (reduces from 402KB to ~30KB, 92% reduction)
    db_query_start = time.time()
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
            "_id": 1
        }
    )
    db_query_time = time.time() - db_query_start
    # logger.info(f"⏱️ [PERF] /franchise/schedule DB query: {db_query_time:.3f}s")
    
    found = franchise_doc is not None
    logger.info("season_schedule franchise_id=%s found=%s", franchise_id, found)
    if not franchise_doc:
        raise HTTPException(status_code=404, detail="Franchise not found")
    schedule = franchise_doc.get("schedule", [])

    # ✅ SS&S: Always use user_team_object_id from franchise document as source of truth
    user_team_id, user_team_object_id = get_user_team_from_franchise(franchise_doc)
    if not user_team_id or not user_team_object_id:
        # Fallback: try to resolve from team name if user_team_object_id is missing
        team_name = user_team_id
        if team_name:
            team_doc = db.teams.find_one({"name": team_name})
            if team_doc:
                team_id = str(team_doc["_id"])
            else:
                team_id = None
        else:
            team_id = None
    else:
        # Use franchise document's user_team_object_id directly (authoritative)
        team_id = user_team_object_id
        team_name = user_team_id
    
    # Get training reports for user's team from FTD
    training_reports = {}
    if team_id:
        try:
            ftd = franchise_team_data_collection.find_one(
                {"franchise_id": ObjectId(franchise_id), "team_id": ObjectId(team_id)},
                {"training_reports": 1}
            )
            if ftd:
                training_reports = ftd.get("training_reports", {})
        except Exception:
            pass

    weeks = []
    results_by_week = franchise_doc.get("results", {})
    included_team_ids = set()
    for idx, games in enumerate(schedule, start=1):
        week_games = []
        week_results = {
            (r["away_id"], r["home_id"]): (r["away_score"], r["home_score"])
            for r in results_by_week.get(str(idx), [])
        }
        for away_id, home_id in games:
            res = week_results.get((str(away_id), str(home_id))) or \
                  week_results.get((str(home_id), str(away_id)))
            game_doc = None  # ✅ SS&S: Initialize game_doc before conditional
            if res:
                away_score, home_score = res
                status = "complete"
                # ✅ SS&S: Try to find game_doc even when status comes from results
                game_doc = db.games.find_one({"week": idx, "franchise_id": str(franchise_id), "team1_id": away_id, "team2_id": home_id}) or \
                           db.games.find_one({"week": idx, "franchise_id": str(franchise_id), "team1_id": home_id, "team2_id": away_id})
            else:
                game_doc = db.games.find_one({"week": idx, "franchise_id": str(franchise_id), "team1_id": away_id, "team2_id": home_id}) or \
                           db.games.find_one({"week": idx, "franchise_id": str(franchise_id), "team1_id": home_id, "team2_id": away_id})
                if game_doc:
                    status = "complete"
                    if game_doc["team1_id"] == away_id:
                        away_score = game_doc.get("team1_score")
                        home_score = game_doc.get("team2_score")
                    else:
                        away_score = game_doc.get("team2_score")
                        home_score = game_doc.get("team1_score")
                else:
                    status = "scheduled"
                    away_score = None
                    home_score = None
            
            # Check if this is the user's team's game and if training report exists
            has_training_report = False
            if team_id and (str(away_id) == team_id or str(home_id) == team_id):
                has_training_report = str(idx) in training_reports
            
            # ✅ SS&S: Include game_id for completed games (needed for box score links)
            game_id = None
            if status == "complete" and game_doc:
                game_id = str(game_doc.get("_id", ""))
            
            week_games.append({
                "week": idx,
                "away_team_id": str(away_id),
                "home_team_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
                "status": status,
                "has_training_report": has_training_report,
                "is_user_team": str(away_id) == team_id or str(home_id) == team_id,
                "game_id": game_id  # ✅ SS&S: Include game_id for box score links
            })
            included_team_ids.add(str(away_id))
            included_team_ids.add(str(home_id))
        weeks.append(week_games)

    # ✅ EOS: Add tournament games (weeks 27–34) from conference / region / national
    eos_tournament_active = franchise_doc.get("eos_tournament_active", False)
    eos_has_state = bool(
        franchise_doc.get("conference_tournaments") or franchise_doc.get("region_tournaments") or franchise_doc.get("national_tournament")
    )
    if eos_tournament_active and eos_has_state:
        round_labels = {
            27: "Conference R1", 28: "Conference R2", 29: "Conference Final",
            30: "Region R1", 31: "Region Final",
            32: "National QF", 33: "National SF", 34: "National Final",
        }
        for eos_week in ft.EOS_WEEKS:
            week_games_meta = ft.get_eos_week_games(franchise_doc, eos_week, include_completed=True)
            week_games = []
            for g in week_games_meta:
                away_id = g.get("away_id")
                home_id = g.get("home_id")
                if not away_id or not home_id:
                    continue
                away_str = str(away_id)
                home_str = str(home_id)
                score = g.get("score", {})
                away_score = score.get("away")
                home_score = score.get("home")
                status = "complete" if g.get("winner") else "scheduled"
                has_training_report = bool(team_id and (away_str == team_id or home_str == team_id) and str(eos_week) in training_reports)
                week_games.append({
                    "week": eos_week,
                    "away_team_id": away_str,
                    "home_team_id": home_str,
                    "away_score": away_score,
                    "home_score": home_score,
                    "status": status,
                    "has_training_report": has_training_report,
                    "is_user_team": away_str == team_id or home_str == team_id,
                    "game_id": g.get("game_id"),
                    "is_tournament": True,
                    "round": round_labels.get(eos_week, ""),
                })
                included_team_ids.add(away_str)
                included_team_ids.add(home_str)
            weeks.append(week_games)

    team_docs = list(db.teams.find({}, {"_id": 1, "conference": 1, "name": 1, "mascot": 1}))
    team_conferences = {str(t["_id"]): t.get("conference") for t in team_docs}
    if conference is not None:
        if not isinstance(conference, int) or conference < 1 or conference > 16:
            raise HTTPException(status_code=422, detail="conference must be an integer from 1 to 16")
        filtered_weeks = []
        included_team_ids = set()
        for week_games in weeks:
            filtered_week_games = [
                game for game in (week_games or [])
                if team_conferences.get(game.get("away_team_id")) == conference
                or team_conferences.get(game.get("home_team_id")) == conference
            ]
            for game in filtered_week_games:
                included_team_ids.add(game.get("away_team_id"))
                included_team_ids.add(game.get("home_team_id"))
            filtered_weeks.append(filtered_week_games)
        weeks = filtered_weeks

    team_name_map = {
        str(team_doc["_id"]): team_doc.get("name")
        for team_doc in team_docs
        if str(team_doc["_id"]) in included_team_ids
    }
    logger.info("season_schedule returning franchise_id=%s found=%s", franchise_id, found)
    return {
        "schedule": weeks,
        "team_id": team_id,
        "team_conferences": team_conferences,
        "team_name_map": team_name_map,
        "conference": conference,
    }


def get_leaders(
    franchise_id: str,
    scope: str = "season",
    stat: str = "PTS",
    limit: int = 10,
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
    pipeline = [
        {"$match": {"franchise_id": str(franchise_id)}},
        {
            "$project": {
                "player_id": 1,
                "meta": 1,
                "value": {"$ifNull": [f"${scope}.{stat_field}", 0]},
            }
        },
        {"$sort": {"value": -1}},
        {"$limit": limit},
    ]
    agg = list(franchise_players_data_collection.aggregate(pipeline))
    aggregation_time = time.time() - aggregation_start
    # logger.info(f"⏱️ [PERF] get_leaders('{stat}') Aggregation pipeline (FPD): {aggregation_time:.3f}s")
    results: list[dict[str, Any]] = []
    for p in agg:
        meta = p.get("meta", {})
        results.append(
            {
                "player_id": p.get("player_id"),
                "first_name": meta.get("first_name", ""),
                "last_name": meta.get("last_name", ""),
                "team": meta.get("team", meta.get("team_id", "")),
                "value": p.get("value", 0),
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
    
    categories = ["PTS", "AST", "3PTM", "REB", "BLK", "STL"]  # ✅ SS&S: Use standardized field name "3PTM" instead of "TPM"
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
        top = get_leaders(franchise_id, scope=scope, stat=cat, limit=256)
        if allowed_team_ids is not None or allowed_team_names is not None:
            filtered_top = []
            for player in top:
                player_team = player.get("team")
                player_team_id = str(player_team) if player_team is not None else ""
                if allowed_team_ids and player_team_id in allowed_team_ids:
                    filtered_top.append(player)
                    continue
                if allowed_team_names and player_team in allowed_team_names:
                    filtered_top.append(player)
            top = filtered_top[:limit]
        else:
            top = top[:limit]
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
    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": fid}, {"team_id": 1, "players": 1}))
    franchise_team_rosters = {}
    for ftd in ftd_docs:
        tid_str = str(ftd["team_id"])
        roster = ftd.get("players") or []
        franchise_team_rosters[tid_str] = [str(pid) for pid in roster]
    
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
) -> None:
    applied = (franchise_doc.get("recruiting_lean_updates_applied") or {}).get(str(week))
    if applied:
        logger.info("Skipping recruiting lean updates for franchise=%s week=%s; already applied", franchise_doc.get("_id"), week)
        return
    if week < 20 or week > 26:
        return

    fid = franchise_doc["_id"]
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": fid},
        {"team_id": 1, "recruit_visit": 1},
    ))
    if not ftd_docs:
        db.franchises.update_one({"_id": fid}, {"$set": {f"recruiting_lean_updates_applied.{week}": True}})
        return

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
        return

    recruit_ids = [recruit_id for _, recruit_id in recruit_visit_pairs]
    recruit_docs_by_id = {
        recruit["recruit_id"]: recruit
        for recruit in franchise_recruits_data_collection.find(
            {"franchise_id": str(fid), "recruit_id": {"$in": recruit_ids}},
            {"recruit_id": 1, "Home Region": 1, "Lean": 1},
        )
    }
    team_outcomes = _team_outcomes_by_week_results(results)

    bulk_updates = []
    for team_id, recruit_id in recruit_visit_pairs:
        recruit_doc = recruit_docs_by_id.get(recruit_id)
        team_doc = team_docs_by_id.get(team_id)
        if not recruit_doc or not team_doc:
            continue
        updated_lean = _update_recruit_lean_after_visit(
            recruit_doc.get("Lean"),
            team_id,
            str(team_doc.get("region") or "").upper() == str(recruit_doc.get("Home Region") or "").upper(),
            team_outcomes.get(team_id) == "win",
        )
        bulk_updates.append({
            "filter": {"franchise_id": str(fid), "recruit_id": recruit_id},
            "update": {"$set": {"Lean": updated_lean}},
        })

    for op in bulk_updates:
        franchise_recruits_data_collection.update_one(op["filter"], op["update"])

    franchise_team_data_collection.update_many(
        {"franchise_id": fid},
        {"$set": {"recruit_visit": None, "updated_at": datetime.utcnow()}},
    )
    db.franchises.update_one(
        {"_id": fid},
        {"$set": {f"recruiting_lean_updates_applied.{week}": True}},
    )


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

    return Player.randomize_game_attributes(attrs)


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
        {"players": 1},
    ) or {}
    roster_player_ids = [str(player_id) for player_id in (ftd_doc.get("players") or []) if player_id]
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
    if week != 1 or not training_status.get("training_completed", False):
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

        cut_ids = set(_choose_cut_player_ids(roster_player_ids, fpd_map, cut_count))
        remaining_ids = [player_id for player_id in roster_player_ids if player_id not in cut_ids]
        remaining_scholarships = [
            str(player_id) for player_id in (ftd_doc.get("scholarship_players") or [])
            if str(player_id) in remaining_ids
        ]
        remaining_ptp = [
            str(player_id) for player_id in (ftd_doc.get("playing_time_promise_players") or [])
            if str(player_id) in remaining_ids
        ]
        total_player_attrs = 0
        for player_id in remaining_ids:
            attrs = (fpd_map.get(player_id) or {}).get("attributes") or {}
            total_player_attrs += sum(int(attrs.get(attr, 0) or 0) for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"])

        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": ftd_doc.get("team_id")},
            {
                "$set": {
                    "players": remaining_ids,
                    "scholarship_players": remaining_scholarships,
                    "training_squad_players": [],
                    "playing_time_promise_players": remaining_ptp,
                    "total_player_attrs": total_player_attrs,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        if cut_ids:
            franchise_players_data_collection.delete_many(
                {"franchise_id": str(franchise_id), "player_id": {"$in": list(cut_ids)}}
            )


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
        "player_id": str(uuid.uuid4()),
        "recruit_id": recruit_doc.get("recruit_id"),
        "team_id": str(team_doc["_id"]),
        "team_name": team_doc.get("name", ""),
        "name": recruit_doc.get("name", "--"),
        "archetype": "Walk On" if walk_on else recruit_doc.get("archetype", "--"),
        "home_region": recruit_doc.get("Home Region", "--"),
        "height": recruit_doc.get("height"),
        "weight": recruit_doc.get("weight"),
        "year": "Freshman",
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
        assigned = add_points_to_entry(selected_low[0].get("recruit_id"), 1)
        points_remaining -= assigned
    if selected_high and points_remaining > 0:
        assigned = add_points_to_entry(
            random.choice(selected_high).get("recruit_id"),
            min(points_remaining, random.randint(1, 3)),
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
            lead_pool = lean_entries[:3]
            chosen = random.choice(lead_pool)
            lead_points = math.floor(points_remaining * 0.6)
            remainder = points_remaining - lead_points
            chosen["points"] += lead_points
            others = lean_entries
            base = remainder // len(others)
            extra = remainder % len(others)
            for index, entry in enumerate(others):
                entry["points"] += base + (1 if index < extra else 0)
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


def _generate_walk_on_profile() -> dict[str, Any]:
    first_names, last_names = load_franchise_names()
    attr_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
    attrs = {}
    over_19 = 0
    for key in attr_keys:
        value = random.randint(1, 22)
        if value > 19 and over_19 >= 3:
            value = random.randint(1, 19)
        if value > 19:
            over_19 += 1
        attrs[key] = value
    attrs = Player.randomize_game_attributes(attrs)
    first_name = random.choice(first_names)
    last_name = random.choice(last_names).title()
    name = f"{first_name} {last_name}"
    height = random.randint(66, 72)
    weight = random.randint(155, 179)
    position_ratings = compute_position_ratings({
        "attributes": attrs,
        "height": height,
        "name": name,
    })
    return {
        "recruit_id": None,
        "name": name,
        "attributes": attrs,
        "position_ratings": position_ratings,
        "height": height,
        "weight": weight,
        "archetype": "Walk On",
        "year": "Freshman",
        "Home Region": "",
    }


def _current_team_capacity_state(franchise_id: ObjectId) -> dict[str, dict[str, Any]]:
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "players": 1, "scholarship_players": 1},
    ))
    roster_player_ids = []
    for doc in ftd_docs:
        roster_player_ids.extend([str(player_id) for player_id in (doc.get("players") or []) if player_id])
    fpd_map = _load_fpd_map(franchise_id, roster_player_ids)
    state: dict[str, dict[str, Any]] = {}
    for doc in ftd_docs:
        team_id = str(doc.get("team_id"))
        players = [str(player_id) for player_id in (doc.get("players") or []) if player_id]
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
            subtotal += 7
        elif pt_offer_count > 2:
            subtotal += 4
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
            walk_on = _generate_walk_on_profile()
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
        "recruits": recruits,
        "team_name_map": team_name_map,
        "week_35_recruiting_results": week_35_results,
        "week_35_recruiting_ran": bool(franchise_doc.get("week_35_recruiting_ran", False)),
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
            raise HTTPException(status_code=400, detail="Recruiting orders cannot exceed 20 total recruiting points")

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

    results = _run_week_35_signings(franchise_doc)
    db.franchises.update_one(
        {"_id": fid},
        {
            "$set": {
                "week": 36,
                "week_35_recruiting_ran": True,
                WEEK_35_RECRUITING_RESULTS_FIELD: results,
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
            "Man": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "2-3 Zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "3-2 Zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0},
            "1-3-1 Zone": {"effectiveness": 0, "momentum": 0, "cloaking": 0}
        }
    else:
        # Ensure each defense has effectiveness value
        defenses = ["Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
        for def_name in defenses:
            if def_name not in scouting_data["defense"]:
                scouting_data["defense"][def_name] = {"effectiveness": 0, "momentum": 0, "cloaking": 0}
            elif "effectiveness" not in scouting_data["defense"][def_name]:
                scouting_data["defense"][def_name]["effectiveness"] = 0
    
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

    remaining_roster_ids = [player_id for player_id in roster_player_ids if player_id not in set(requested_ids)]
    if len(remaining_roster_ids) != 12:
        raise HTTPException(status_code=400, detail="Cuts must leave exactly 12 players on the roster")

    remaining_scholarships = [
        str(player_id) for player_id in (ftd_doc.get("scholarship_players") or [])
        if str(player_id) in remaining_roster_ids
    ]
    remaining_training_squad = [
        str(player_id) for player_id in (ftd_doc.get("training_squad_players") or [])
        if str(player_id) in remaining_roster_ids
    ]
    remaining_ptp = [
        str(player_id) for player_id in (ftd_doc.get("playing_time_promise_players") or [])
        if str(player_id) in remaining_roster_ids
    ]

    total_player_attrs = 0
    for player_id in remaining_roster_ids:
        attrs = (fpd_map.get(player_id) or {}).get("attributes") or {}
        total_player_attrs += sum(int(attrs.get(attr, 0) or 0) for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"])

    franchise_team_data_collection.update_one(
        {"franchise_id": fid, "team_id": team_object_id},
        {
            "$set": {
                "players": remaining_roster_ids,
                "scholarship_players": remaining_scholarships,
                "training_squad_players": remaining_training_squad,
                "playing_time_promise_players": remaining_ptp,
                "total_player_attrs": total_player_attrs,
                "updated_at": datetime.utcnow(),
            }
        },
    )
    franchise_players_data_collection.delete_many(
        {"franchise_id": str(fid), "player_id": {"$in": requested_ids}}
    )

    return {
        "status": "success",
        "cut_count": required_cut_count,
        "cut_names": cut_names,
        "remaining_roster_count": len(remaining_roster_ids),
    }


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
    
    return {
        "team_attributes": team_attributes,
        "plays": plays_data
    }


class FranchiseTrainingRequest(BaseModel):
    franchise_id: str
    team_id: Optional[str] = None
    training_data: dict  # Contains player_drills, team_drills, general, coaching_focus


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
    
    return {
        "training_points": training_points,
        "is_first_training": is_first_training,
        "week": week,
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


def _run_franchise_training_impl(req: FranchiseTrainingRequest):
    """Inner implementation so run_franchise_training can be profiled with ?profile=1."""
    import time
    endpoint_start = time.time()
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

    # Get training status and check for duplicate submission
    training_status = franchise_doc.get("training_status", {})
    week = franchise_doc.get("week", 1)
    results = franchise_doc.get("results", {})
    
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
    if training_status.get("training_completed", False) and training_status.get("week") == week:
        # Training already completed for this week, redirect to report
        # ✅ SS&S: Use user_team_object_id from franchise document for redirect (authoritative)
        user_team_id_name, user_team_object_id = get_user_team_from_franchise(franchise_doc)
        redirect_team_id = user_team_object_id if user_team_object_id else req.team_id
        return {
            "status": "already_completed",
            "week": week,
            "redirect": f"/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={redirect_team_id}&week={week}"
        }

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

    # Build player list with franchise-specific attributes
    players_load_start = time.time()
    players_for_training = []
    for pid in team_player_ids:
        pid_str = str(pid)
        franchise_player_data = franchise_players.get(pid_str, {})
        if not franchise_player_data:
            continue
        
        meta = franchise_player_data.get("meta", {})
        # Build player dict for training
        player = {
            "_id": pid_str,
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "team": team_name or team_id,  # Use team_name if available, otherwise use team_id
            "attributes": franchise_player_data.get("attributes", {}),
            "position_ratings": franchise_player_data.get("position_ratings", {}),
            "year": meta.get("year")
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

    # Execute new training system
    # This applies pre-training conditions, then training points, and returns training report
    from BackEnd.models.training_execution_v2 import execute_training
    
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
        playbook_training_mode=training_data.get("playbook_training_mode", "current-playbooks"),
        skip_pre_training_depreciation=is_first_training
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
        meta = (franchise_players.get(pid) or {}).get("meta", {})
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

    if 20 <= week <= 26 and str(week) not in recruiting_results:
        _process_weekly_recruiting_invites(franchise_doc)

    # Mark training as completed and update status (still in franchise doc)
    session_type = training_status.get("session_type", "in-season")
    franchise_update["training_status.training_completed"] = True
    franchise_update["training_status.week"] = week
    franchise_update["training_status.last_training_date"] = datetime.now().strftime("%Y-%m-%d")
    
    # Store training report data
    training_report_data = {
        "week": week,
        "player_logs": player_logs,  # Standardized name (was player_changes)
        "team_log": team_log,  # Standardized name (was team_changes)
        "coaching_focus": training_report.get("coaching_focus", {}),
        "training_notes": training_report.get("training_notes", []),
        "plays_data": training_report.get("plays_data", {}),
        "scouting_data": training_report.get("scouting_data", {}),
        "plays_effectiveness_changes": training_report.get("plays_effectiveness_changes", {}),
        "defenses_effectiveness_changes": training_report.get("defenses_effectiveness_changes", {}),
        "session_type": session_type,
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    # ✅ FTD: Store training report in FTD collection
    ftd_update[f"training_reports.{week}"] = training_report_data
    
    # Also save latest training for quick access (still in franchise doc for backward compatibility)
    franchise_update["latest_training"] = training_report_data
    
    # ✅ FTD: Update FTD collection with all changes
    if ftd_update:
        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": team_object_id},
            {"$set": ftd_update}
        )

    # ✅ Distant training: all non-user teams use template-based training (Distant_Team_Training_System.md)
    # During EOS weeks, skip training for teams eliminated from tournament (Franchise_Tournament_System.md)
    all_ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id}))
    training_type = "tc" if is_first_training else "regular"
    eliminated_team_ids = set()
    if week > ScheduleManager.REGULAR_SEASON_WEEKS and franchise_doc.get("eos_tournament_active"):
        eliminated_team_ids = ft.get_eliminated_team_ids(franchise_doc)
    distant_templates = list(db["distant_training"].find({"training_type": training_type}))
    if not distant_templates:
        logger.warning(f"⚠️ [DISTANT TRAINING] No templates found for training_type={training_type}, skipping computer teams")
    else:
        for ftd_doc in all_ftd_docs:
            computer_team_oid = ftd_doc.get("team_id")
            if computer_team_oid is None:
                continue
            computer_team_id_str = str(computer_team_oid)
            if computer_team_id_str == str(team_id):
                continue
            if computer_team_id_str in eliminated_team_ids:
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
                if ftd_update:
                    franchise_team_data_collection.update_one(
                        {"franchise_id": franchise_id, "team_id": computer_team_oid},
                        {"$set": ftd_update},
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
                logger.info(f"✅ [DISTANT TRAINING] Applied template for team_id={computer_team_id_str}")
            except Exception as e:
                logger.error(f"❌ [DISTANT TRAINING] Error for team_id={computer_team_id_str}: {e}", exc_info=True)
                continue

    if is_first_training:
        _apply_cpu_training_camp_cuts(franchise_id, excluded_team_id=str(team_id))

    # Save to franchise document (includes both user team and computer teams)
    db_update_start = time.time()
    db.franchises.update_one({"_id": franchise_id}, {"$set": franchise_update})
    db_update_time = (time.time() - db_update_start) * 1000
    # logger.warning(f"⏱️ [DB TIMING] run_franchise_training: franchises.update_one(): {db_update_time:.2f}ms")
    
    total_time = (time.time() - endpoint_start) * 1000
    # logger.warning(f"⏱️ [DB TIMING] run_franchise_training TOTAL: {total_time:.2f}ms")
    
    return {
        "status": "success",
        "week": week,
        "player_changes": player_logs,
        "team_changes": team_log,
        "coaching_focus": training_report.get("coaching_focus", {}),
        "session_type": session_type,
        "redirect": f"/training-report.html?mode=franchise&franchise_id={req.franchise_id}&team_id={team_id}&week={week}"
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
                    players.append({
                        "id": pid_str,
                        "name": player_name,
                        "attributes": player_attrs,
                        "position_ratings": player_data.get("position_ratings", {}),
                    })
            
            logger.info(f"🔍 [TRAINING REPORT] Found {len(players)} players for team {team_id_str}")
            
            # Get current team attributes (after training)
            team_attrs = {
                "shot_threshold": team_data.get("shot_threshold", 0),
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
            
            # Get upcoming opponent from bracket
            current_round = doc.get("current_round", 1)
            round_key = get_round_name(current_round)
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
                    players.append({
                        "id": pid_str,
                        "name": player_name,
                        "attributes": player_attrs,
                        "position_ratings": tournament_player_data.get("position_ratings", {}),
                    })
            
            # Get current team attributes from tournament teams (matches Franchise pattern)
            team_attrs = {
                "shot_threshold": team_data.get("shot_threshold", 0),
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

        return {
            "status": "success",
            "week": week if mode == "franchise" else None,  # Only for franchise mode
            "round": current_round if mode == "tournament" else None,  # Only for tournament mode
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
            "team_attributes": team_attrs
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

    week_games_meta = ft.get_eos_week_games(franchise_doc, week)
    if not week_games_meta:
        raise HTTPException(status_code=400, detail="No games in current EOS round (e.g. week 30 with all double-winners)")

    _user_team_name, user_team_id_str = get_user_team_from_franchise(franchise_doc)
    user_eos_sim_scope = _build_user_eos_sim_scope(franchise_doc, user_team_id_str)
    ftd_docs = list(franchise_team_data_collection.find(
        {"franchise_id": franchise_id},
        {"team_id": 1, "prestige": 1, "total_player_attrs": 1},
    ))
    ftd_by_team_id = {str(d["team_id"]): d for d in ftd_docs if d.get("team_id")}

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
            home_combined = (home_ftd.get("prestige") or 0) + int(0.1 * (home_ftd.get("total_player_attrs") or 0)) + 100
            away_combined = (away_ftd.get("prestige") or 0) + int(0.1 * (away_ftd.get("total_player_attrs") or 0))
            home_score, away_score = _run_distant_game_sim(home_combined, away_combined)
            winner_id = home_id if home_score > away_score else away_id
            score = {"home": home_score, "away": away_score}
            if g["phase"] == "conference":
                ft.save_conference_game_result(
                    franchise_doc, g["conference"], g["round"], g["matchup_index"],
                    "", str(winner_id), score,
                )
            elif g["phase"] == "region":
                ft.save_region_game_result(
                    franchise_doc, g["region"], g["round"], g["matchup_index"],
                    "", str(winner_id), score,
                )
            elif g["phase"] == "national":
                ft.save_national_game_result(
                    franchise_doc, g["round"], g["matchup_index"],
                    "", str(winner_id), score,
                )
            results.append({
                "away_id": str(away_id),
                "home_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
            })
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
            score = {"home": home_score, "away": away_score}
            if g["phase"] == "conference":
                ft.save_conference_game_result(
                    franchise_doc, g["conference"], g["round"], g["matchup_index"],
                    str(game_id), str(winner_id), score,
                )
            elif g["phase"] == "region":
                ft.save_region_game_result(
                    franchise_doc, g["region"], g["round"], g["matchup_index"],
                    str(game_id), str(winner_id), score,
                )
            elif g["phase"] == "national":
                ft.save_national_game_result(
                    franchise_doc, g["round"], g["matchup_index"],
                    str(game_id), str(winner_id), score,
                )
            results.append({
                "away_id": str(away_id),
                "home_id": str(home_id),
                "away_score": away_score,
                "home_score": home_score,
            })
            logger.info("✅ [EOS] Simulated %s: %s vs %s", g["phase"], away_name, home_name)
        except Exception as e:
            logger.error("❌ [EOS] Error simulating game: %s", e, exc_info=True)

    existing_results = franchise_doc.get("results", {})
    existing_results[str(week)] = results
    update_fields = {"results": existing_results}
    # After advancing the round, cue user to run training for the new week (e.g. bye in week 30 → sim → week 31 → "Run Training")
    update_fields["training_status.training_completed"] = False
    update_fields["training_status.session_type"] = "in-season"

    if week in ft.EOS_CONFERENCE_WEEKS:
        for c in range(1, 17):
            ft.advance_conference_bracket(franchise_doc, c)
        update_fields["conference_tournaments"] = franchise_doc.get("conference_tournaments", {})
        if week == ft.EOS_CONFERENCE_WEEKS[-1]:
            eos_team_ids = [d["team_id"] for d in franchise_team_data_collection.find(
                {"franchise_id": franchise_id}, {"team_id": 1}
            ) if d.get("team_id")]
            update_fields["region_tournaments"] = ft.initialize_region_tournaments(
                franchise_doc, db.teams, team_ids=eos_team_ids
            )
            update_fields["week"] = ft.EOS_REGION_WEEKS[0]
        else:
            update_fields["week"] = week + 1
    elif week in ft.EOS_REGION_WEEKS:
        update_fields["region_tournaments"] = franchise_doc.get("region_tournaments", {})
        if week == ft.EOS_REGION_WEEKS[-1]:
            region_champions = ft.get_region_champions(franchise_doc)
            team_ids = [d["team_id"] for d in franchise_team_data_collection.find(
                {"franchise_id": franchise_id}, {"team_id": 1}
            ) if d.get("team_id")]
            update_fields["national_tournament"] = ft.initialize_national_tournament(
                franchise_doc, db.teams, region_champions,
                franchise_doc.get("results", {}), team_ids,
            )
            update_fields["week"] = ft.EOS_NATIONAL_WEEKS[0]
        else:
            update_fields["week"] = ft.EOS_REGION_WEEKS[1]
    elif week in ft.EOS_NATIONAL_WEEKS:
        ft.advance_national_bracket(franchise_doc)
        update_fields["national_tournament"] = franchise_doc.get("national_tournament", {})
        if week == ft.EOS_NATIONAL_WEEKS[-1]:
            update_fields["eos_tournament_active"] = False
            update_fields["week"] = 35
        else:
            update_fields["week"] = ft.EOS_NATIONAL_WEEKS[ft.EOS_NATIONAL_WEEKS.index(week) + 1]

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
        ft.save_national_game_result(
            franchise_doc, 3, 0, str(game_id), str(winner_id),
            {"home": home_score, "away": away_score},
        )
        ft.advance_national_bracket(franchise_doc)
        national_tournament = franchise_doc.get("national_tournament", {})
        db.franchises.update_one(
            {"_id": franchise_id},
            {"$set": {"national_tournament": national_tournament, "eos_tournament_active": False, "week": 35}}
        )
        refreshed = db.franchises.find_one({"_id": franchise_id})
        if refreshed:
            _persist_week_35_awards_if_needed(refreshed)
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
    
    # Get current season
    current_season = franchise_doc.get("current_season", 1)
    next_season = current_season + 1

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
        for player_id in (ftd_doc.get("players") or []):
            player_id_str = str(player_id)
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
                "year": "Freshman",
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

    def highest_rt(player_id: str) -> int:
        return int((_best_position((next_fpd_map.get(player_id) or {}).get("position_ratings") or {}).get("rating") or 0))

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

        total_player_attrs = 0
        for player_id in ordered_roster:
            attrs = (next_fpd_map.get(player_id) or {}).get("attributes") or {}
            total_player_attrs += sum(int(attrs.get(attr, 0) or 0) for attr in ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"])

        franchise_team_data_collection.update_one(
            {"franchise_id": franchise_id, "team_id": ftd_doc["team_id"]},
            {
                "$set": {
                    "players": ordered_roster,
                    "scholarship_players": sorted(scholarship_players, key=highest_rt, reverse=True),
                    "training_squad_players": [],
                    "playing_time_promise_players": pt_promise_players,
                    "Recruits": {str(i): None for i in range(1, 21)},
                    RECRUITING_ORDERS_WEEK_35_FIELD: {},
                    "recruit_visit": None,
                    "training_reports": {},
                    "total_player_attrs": total_player_attrs,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    franchise_players_data_collection.delete_many({"franchise_id": str(franchise_id)})
    if next_fpd_docs:
        franchise_players_data_collection.insert_many(next_fpd_docs)

    fm = FranchiseManager(db)
    fm.franchise_id = franchise_id
    schedule = fm.schedule_manager.generate_schedule()
    recruits = fm.recruit_manager.generate_recruits_list(count=300)
    region_team_ids = fm._build_region_team_map()

    franchise_recruits_data_collection.delete_many({"franchise_id": str(franchise_id)})
    frd_docs = [
        {
            "franchise_id": str(franchise_id),
            "recruit_id": str(uuid.uuid4()),
            "name": recruit["name"],
            "attributes": recruit["attributes"],
            "position_ratings": recruit["position_ratings"],
            "height": recruit["height"],
            "weight": recruit["weight"],
            "archetype": recruit["archetype"],
            "year": recruit["year"],
            "Home Region": home_region,
            "Lean": fm._build_recruit_lean(home_region, region_team_ids),
            "created_at": recruit["created_at"],
        }
        for recruit in recruits
        for home_region in [random.choice(list(region_team_ids.keys()))]
    ]
    if frd_docs:
        franchise_recruits_data_collection.insert_many(frd_docs)

    db.games.delete_many({"franchise_id": str(franchise_id)})
    awards_reset = {}
    db.franchises.update_one(
        {"_id": franchise_id},
        {"$set": {
            "current_season": next_season,
            "week": 1,
            "results": {},
            "schedule": schedule,
            "eos_tournament_active": False,
            "conference_tournaments": {},
            "region_tournaments": {},
            "national_tournament": {},
            "recruiting_results": {},
            "recruiting_lean_updates_applied": {},
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
