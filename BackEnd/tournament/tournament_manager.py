from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import random

class TournamentManager:
    def __init__(self, user_team_id=None, tournaments_collection=None):
        self.user_team_id = user_team_id
        self.tournaments_collection = tournaments_collection
        self.tournament_id = None
        self.tournament = None

    def create_tournament(self):
        teams = self.team_ids[:]
        random.shuffle(teams)
        seeds = {team_id: i + 1 for i, team_id in enumerate(teams)}
        round1 = self._generate_first_round(seeds)
        tournament_doc = {
            "user_team_id": self.user_team_id,
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
            "completed": False
        }
        self.tournament_id = self.tournaments_collection.insert_one(tournament_doc).inserted_id
        # self.tournament_id = self.db.tournaments.insert_one(tournament_doc).inserted_id
        self.tournament = tournament_doc
        self.tournament["_id"] = self.tournament_id
        return self.tournament

    def _generate_first_round(self, seeds):
        sorted_teams = sorted(seeds.items(), key=lambda x: x[1])
        matchups = [
            (sorted_teams[0][0], sorted_teams[7][0]),
            (sorted_teams[3][0], sorted_teams[4][0]),
            (sorted_teams[1][0], sorted_teams[6][0]),
            (sorted_teams[2][0], sorted_teams[5][0])
        ]
        return [{"home_team": home, "away_team": away, "game_id": None, "winner": None} for home, away in matchups]

    def save_game_result(self, round_name, matchup_index, game_id, winner_id):
        self.tournament["bracket"][round_name][matchup_index]["game_id"] = game_id
        self.tournament["bracket"][round_name][matchup_index]["winner"] = winner_id
        self.db.tournaments.update_one(
            {"_id": self.tournament_id},
            {"$set": {f"bracket.{round_name}.{matchup_index}.game_id": game_id,
                      f"bracket.{round_name}.{matchup_index}.winner": winner_id}}
        )

    def advance_round(self):
        current_round = self.tournament["current_round"]
        if current_round == 1:
            r1_winners = [m["winner"] for m in self.tournament["bracket"]["round1"]]
            r2 = [
                {"home_team": r1_winners[0], "away_team": r1_winners[1], "game_id": None, "winner": None},
                {"home_team": r1_winners[2], "away_team": r1_winners[3], "game_id": None, "winner": None}
            ]
            self.tournament["bracket"]["round2"] = r2
            self.tournament["current_round"] = 2
        elif current_round == 2:
            r2_winners = [m["winner"] for m in self.tournament["bracket"]["round2"]]
            final = [
                {"home_team": r2_winners[0], "away_team": r2_winners[1], "game_id": None, "winner": None}
            ]
            self.tournament["bracket"]["final"] = final
            self.tournament["current_round"] = 3
        elif current_round == 3:
            self.tournament["completed"] = True

        self.db.tournaments.update_one(
            {"_id": self.tournament_id},
            {"$set": {
                "bracket": self.tournament["bracket"],
                "current_round": self.tournament["current_round"],
                "completed": self.tournament["completed"]
            }}
        )
