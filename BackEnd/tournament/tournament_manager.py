from datetime import datetime
import random
from bson import ObjectId

from BackEnd.db import tournaments_collection as default_tournaments_collection
from BackEnd.utils.roster_loader import load_roster

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

        # Build roster mapping for all teams in the bracket
        tournament_teams = {
            team
            for matchup in round1
            for team in (matchup["home_team"], matchup["away_team"])
        }
        players_map = {}
        for team_name in tournament_teams:
            team_doc, players = load_roster(team_name)
            team_entry = team_doc.copy() if team_doc else {"name": team_name}
            team_entry["players"] = players
            players_map[team_name] = team_entry

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
            "players": players_map,
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
        return [{"home_team": home, "away_team": away, "game_id": None, "winner": None} for home, away in matchups]

    def save_game_result(self, round_name, matchup_index, game_id, winner_id):
        self.tournament["bracket"][round_name][matchup_index]["game_id"] = game_id
        self.tournament["bracket"][round_name][matchup_index]["winner"] = winner_id
        self.tournaments_collection.update_one(
            {"_id": self.tournament_id},
            {
                "$set": {
                    f"bracket.{round_name}.{matchup_index}.game_id": game_id,
                    f"bracket.{round_name}.{matchup_index}.winner": winner_id,
                }
            },
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
