from datetime import datetime
import random
import logging
from bson import ObjectId

from BackEnd.db import (
    tournaments_collection as default_tournaments_collection,
    players_collection,
    teams_collection,
)
from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.tournament.bracket_engine import generate_bracket, save_game_result as engine_save_game_result, get_round_name

logger = logging.getLogger(__name__)


def _default_team_docs():
    """Default 8 teams when none provided (e.g. tests)."""
    names = [
        "Bentley-Truman", "Four Corners", "Lancaster", "Little York",
        "Morristown", "Ocean City", "South Lancaster", "Xavien",
    ]
    out = []
    for n in names:
        t = teams_collection.find_one({"name": n}, {"name": 1, "_id": 1})
        if t:
            out.append({"name": t["name"], "_id": t["_id"]})
    return out[:8]


class TournamentManager:
    """Manage tournament creation and progression.

    Bracket and results use ObjectId strings for team IDs. Name resolution
    happens at API/game boundaries (see Tournament_Execution_System.md).
    """

    def __init__(self, user_team_id: str | None = None, *,
                 tournaments_collection=None, team_ids=None, team_docs=None) -> None:
        self.user_team_id = user_team_id
        self.tournaments_collection = default_tournaments_collection if tournaments_collection is None else tournaments_collection
        self.team_ids = team_ids
        if team_docs:
            self.team_docs = team_docs
        elif team_ids and len(team_ids) >= 8:
            self.team_docs = []
            for name in team_ids[:8]:
                t = teams_collection.find_one({"name": name}, {"name": 1, "_id": 1})
                if t:
                    self.team_docs.append({"name": t["name"], "_id": t["_id"]})
            self.team_docs = self.team_docs[:8]
        else:
            self.team_docs = _default_team_docs()
        self.tournament_id: ObjectId | None = None
        self.tournament: dict | None = None

    def create_tournament(self):
        docs = list(self.team_docs)
        if len(docs) < 8:
            raise ValueError(f"Tournament requires 8 teams; got {len(docs)}.")
        random.shuffle(docs)
        seed_order = [str(t["_id"]) for t in docs]
        names = [t["name"] for t in docs]
        bracket = generate_bracket(seed_order)

        zero_stats = {key: 0 for key in BOX_SCORE_KEYS}
        zero_stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
        players_dict: dict[str, dict] = {}
        players = players_collection.find(
            {"team": {"$in": names}},
            {"first_name": 1, "last_name": 1, "team": 1, "team_id": 1, "attributes": 1, "position_ratings": 1},
        )
        for p in players:
            from BackEnd.models.player import Player
            pid = str(p.get("_id"))
            # Clone attributes and randomize EM, CH, MO for this tournament instance
            # Store ALL attributes (like franchise mode) to support training and evolution
            attrs = p.get("attributes", {}).copy()
            attrs = Player.randomize_game_attributes(attrs)
            
            # Get team_id from player document or resolve from team name
            team_id = None
            if p.get("team_id"):
                team_id = str(p.get("team_id"))
            else:
                team_doc = teams_collection.find_one({"name": p.get("team", "")})
                if team_doc:
                    team_id = str(team_doc.get("_id", ""))
            
            # Wrap metadata in meta object (matches Franchise pattern)
            meta = {
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "team": p.get("team", ""),
            }
            if team_id:
                meta["team_id"] = team_id
            
            players_dict[pid] = {
                "meta": meta,  # Wrap metadata in meta object (matches Franchise pattern)
                "season": zero_stats.copy(),  # ✅ MIGRATION: Tournament only tracks season stats (no career)
                "attributes": attrs,  # Store all attributes (not just EM, CH, MO)
                "position_ratings": p.get("position_ratings", {}).copy()  # Store position ratings (needed for training)
            }

        # ✅ INITIALIZATION: Initialize team objects for all 8 teams upfront (matches Franchise pattern)
        # This ensures all team objects exist from the start, eliminating race conditions and lazy initialization issues
        from BackEnd.models.team_manager import TeamManager
        from BackEnd.api.gameplan_routes import populate_team_plays, populate_scouting_data, initialize_playbook_settings
        
        # Get populated plays and scouting data for all teams (tournament mode)
        populated_plays = populate_team_plays(mode="tournament")
        scouting_data = populate_scouting_data(mode="tournament")
        playbook_settings = initialize_playbook_settings()
        
        teams_obj = {}
        for t in docs:
            team_id = str(t["_id"])
            team_name = t["name"]
            # Use TeamManager static method to generate mode-specific team attributes
            team_attrs = TeamManager.init_team_attributes(mode="tournament")
            teams_obj[team_id] = {
                "name": team_name,
                "team_chemistry": team_attrs["team_chemistry"],
                "offensive_efficiency": team_attrs["offensive_efficiency"],
                "shot_threshold": team_attrs["shot_threshold"],
                "discipline": team_attrs["discipline"],
                "fight": team_attrs["fight"],
                "rebound_modifier": team_attrs["rebound_modifier"],
                "defensive_efficiency": team_attrs["defensive_efficiency"],
                "fb_efficiency": team_attrs["fb_efficiency"],
                "pt_efficiency": team_attrs["pt_efficiency"],
                "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                # Game plan settings (all start at 2 = Normal)
                "strategy_settings": {
                    "offense": 2,  # Motion vs Set Play split (0=motion only, 4=set plays only)
                    "inside": 2,   # Inside focus preference
                    "attack": 2,   # Attack focus preference
                    "outside": 2,  # Outside focus preference
                    "tempo": 2,   # Tempo preference
                    "defense": 2,  # Man vs Zone defense preference
                    "aggression": 2,  # Defensive aggression level
                    "hc_trap": 2,  # Half court trap usage (matches frontend key)
                    "fc_press": 2, # Full court press usage (matches frontend key)
                    "rebounding": 2  # Crash boards vs get back preference
                },
                "plays": populated_plays.copy(),
                "scouting_data": scouting_data.copy(),
                "playbook_settings": playbook_settings.copy()
            }

        # ✅ MIGRATION: Resolve user_team_id (team name) to user_team_object_id (ObjectId)
        # This matches Franchise mode pattern for consistent team ID resolution
        user_team_object_id = None
        if self.user_team_id:
            for t in docs:
                if t.get("name") == self.user_team_id:
                    user_team_object_id = str(t["_id"])
                    break
            if not user_team_object_id:
                team_doc = teams_collection.find_one({"name": self.user_team_id})
                if team_doc:
                    user_team_object_id = str(team_doc["_id"])
                else:
                    logger.warning(f"⚠️ [TOURNAMENT] Could not resolve user_team_id '{self.user_team_id}' to ObjectId")
        
        tournament_doc = {
            "user_team_id": self.user_team_id,
            "user_team_object_id": user_team_object_id,
            "created_at": datetime.utcnow(),
            "bracket": bracket,
            "current_round": 1,
            "results": [],
            "stats": {
                "top_10_points": [],
                "top_10_rebounds": [],
                "top_10_assists": [],
                "top_10_blocks": [],
                "top_10_steals": []
            },
            "players": players_dict,
            "teams": teams_obj,
            "applied_games": [],
            "completed": False,
        }
        self.tournament_id = self.tournaments_collection.insert_one(tournament_doc).inserted_id
        self.tournament = tournament_doc
        self.tournament["_id"] = str(self.tournament_id)  
        return self.tournament

    def save_game_result(self, round_num: int, matchup_index: int, game_id, winner_id: str, score=None):
        """Update bracket with game result. winner_id must be ObjectId string."""
        bracket = self.tournament["bracket"]
        engine_save_game_result(bracket, round_num, matchup_index, game_id, winner_id, score)
        round_key = get_round_name(round_num)
        update_fields = {
            f"bracket.{round_key}.{matchup_index}.game_id": game_id,
            f"bracket.{round_key}.{matchup_index}.winner": winner_id,
        }
        if score is not None:
            update_fields[f"bracket.{round_key}.{matchup_index}.score"] = score
        self.tournaments_collection.update_one(
            {"_id": self.tournament_id},
            {"$set": update_fields},
        )

    def advance_round(self):
        """Advance bracket from current-round matchup winners. Uses bracket_engine. For unit tests / legacy callers."""
        from BackEnd.tournament.bracket_engine import advance_bracket
        cr = self.tournament.get("current_round", 1)
        bracket = self.tournament["bracket"]
        bracket, next_r, completed, champion = advance_bracket(bracket, cr, winners_from_matchups=True)
        self.tournament["bracket"] = bracket
        self.tournament["current_round"] = next_r
        upd = {"bracket": bracket, "current_round": next_r}
        if completed and champion is not None:
            self.tournament["completed"] = True
            self.tournament["champion"] = champion
            upd["completed"] = True
            upd["champion"] = champion
        self.tournaments_collection.update_one({"_id": self.tournament_id}, {"$set": upd})
