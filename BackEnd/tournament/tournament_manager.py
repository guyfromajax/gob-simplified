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

logger = logging.getLogger(__name__)

class TournamentManager:
    """Manage tournament creation and progression."""

    def __init__(self, user_team_id: str | None = None, *,
                 tournaments_collection=None, team_ids=None) -> None:
        self.user_team_id = user_team_id
        self.tournaments_collection = default_tournaments_collection if tournaments_collection is None else tournaments_collection

        self.team_ids = team_ids or [
            "Bentley-Truman",
            "Four Corners",
            "Lancaster",
            "Little York",
            "Morristown",
            "Ocean City",
            "South Lancaster",
            "Xavien",
        ]
        self.tournament_id: ObjectId | None = None
        self.tournament: dict | None = None

    def create_tournament(self):
        teams = self.team_ids[:]
        random.shuffle(teams)
        seeds = {team_id: i + 1 for i, team_id in enumerate(teams)}
        round1 = self._generate_first_round(seeds)

        zero_stats = {key: 0 for key in BOX_SCORE_KEYS}
        zero_stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
        players_dict: dict[str, dict] = {}  # ✅ MIGRATION: Changed from player_stats to players_dict
        players = players_collection.find(
            {"team": {"$in": teams}},
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
                # Fallback: resolve team name to team_id
                from BackEnd.db import teams_collection
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
        
        # ✅ FIX: Only initialize the 8 teams in the tournament (matches Franchise pattern)
        # Franchise mode initializes only the 8 teams in self.teams, not all teams from database
        teams_obj = {}
        
        for team_name in teams:  # teams is the list of 8 team names in the tournament
            # Resolve team name to team document and ObjectId
            team_doc = teams_collection.find_one({"name": team_name})
            if not team_doc:
                continue  # Skip if team not found
            
            team_id = str(team_doc["_id"])
            # Use TeamManager static method to generate mode-specific team attributes
            team_attrs = TeamManager.init_team_attributes(mode="tournament")
            teams_obj[team_id] = {
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
            from BackEnd.db import teams_collection
            team_doc = teams_collection.find_one({"name": self.user_team_id})
            if team_doc:
                user_team_object_id = str(team_doc["_id"])
            else:
                logger.warning(f"⚠️ [TOURNAMENT] Could not resolve user_team_id '{self.user_team_id}' to ObjectId")
        
        tournament_doc = {
            "user_team_id": self.user_team_id,
            "user_team_object_id": user_team_object_id,  # ✅ MIGRATION: Store ObjectId for authoritative team resolution
            "created_at": datetime.utcnow(),
            "bracket": {
                "round1": round1,
                "round2": [],
                "final": []
            },
            "current_round": 1,
            "stats": {
                "top_10_points": [],
                "top_10_rebounds": [],
                "top_10_assists": [],
                "top_10_blocks": [],
                "top_10_steals": []
            },
            "players": players_dict,  # ✅ MIGRATION: Changed from player_stats to players (aligns with Franchise)
            "teams": teams_obj,  # Initialize all teams upfront
            "applied_games": [],
            "completed": False
        }
        self.tournament_id = self.tournaments_collection.insert_one(tournament_doc).inserted_id
        self.tournament = tournament_doc
        self.tournament["_id"] = str(self.tournament_id)  
        return self.tournament

    def _generate_first_round(self, seeds):
        sorted_teams = sorted(seeds.items(), key=lambda x: x[1])
        matchups = [
            (sorted_teams[0][0], sorted_teams[7][0]),
            (sorted_teams[3][0], sorted_teams[4][0]),
            (sorted_teams[1][0], sorted_teams[6][0]),
            (sorted_teams[2][0], sorted_teams[5][0])
        ]
        return [
            {
                "home_team": home,
                "away_team": away,
                "game_id": None,
                "winner": None,
                "score": {},
            }
            for home, away in matchups
        ]

    def save_game_result(self, round_name, matchup_index, game_id, winner_id, score=None):
        match = self.tournament["bracket"][round_name][matchup_index]
        match["game_id"] = game_id
        match["winner"] = winner_id
        if score is not None:
            match["score"] = score
        update_fields = {
            f"bracket.{round_name}.{matchup_index}.game_id": game_id,
            f"bracket.{round_name}.{matchup_index}.winner": winner_id,
        }
        if score is not None:
            update_fields[f"bracket.{round_name}.{matchup_index}.score"] = score
        self.tournaments_collection.update_one(
            {"_id": self.tournament_id},
            {"$set": update_fields},
        )

    def advance_round(self):
        current_round = self.tournament["current_round"]
        if current_round == 1:
            r1_winners = [m["winner"] for m in self.tournament["bracket"]["round1"]]
            r2 = [
                {
                    "home_team": r1_winners[0],
                    "away_team": r1_winners[1],
                    "game_id": None,
                    "winner": None,
                    "score": {},
                },
                {
                    "home_team": r1_winners[2],
                    "away_team": r1_winners[3],
                    "game_id": None,
                    "winner": None,
                    "score": {},
                },
            ]
            self.tournament["bracket"]["round2"] = r2
            self.tournament["current_round"] = 2
        elif current_round == 2:
            r2_winners = [m["winner"] for m in self.tournament["bracket"]["round2"]]
            final = [
                {
                    "home_team": r2_winners[0],
                    "away_team": r2_winners[1],
                    "game_id": None,
                    "winner": None,
                    "score": {},
                }
            ]
            self.tournament["bracket"]["final"] = final
            self.tournament["current_round"] = 3
        elif current_round == 3:
            self.tournament["completed"] = True

        self.tournaments_collection.update_one(
            {"_id": self.tournament_id},
            {
                "$set": {
                    "bracket": self.tournament["bracket"],
                    "current_round": self.tournament["current_round"],
                    "completed": self.tournament["completed"],
                }
            },
        )
