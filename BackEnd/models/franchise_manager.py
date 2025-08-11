import random
from datetime import datetime
from itertools import combinations, permutations
from importlib import resources
from pathlib import Path
import json
import logging
import sys


logger = logging.getLogger(__name__)


class FranchiseManager:
    def __init__(self, db):
        self.db = db
        self.teams = self.load_teams()
        self.week = 1
        self.schedule_manager = ScheduleManager(self.teams)
        self.recruit_manager = RecruitManager(self.db)
        self.schedule = []
        self.franchise_id = None

    def load_teams(self):
        return list(self.db.teams.find())

    def initialize_season(self):
        # Clear any previous season game data to ensure a fresh start
        self.db.games.delete_many({})
        self.schedule = self.schedule_manager.generate_schedule()
        self.week = 1
        self.reset_stats()
        self.save_season_state()

    def reset_stats(self):
        for team in self.teams:
            self.db.players.update_many({"team_id": team["_id"]}, {"$set": {"season_stats": {}}})
            self.db.teams.update_one(
                {"_id": team["_id"]},
                {"$set": {"season_stats": {}, "record": {"W": 0, "L": 0}, "PF": 0, "PA": 0}}
            )

    def run_week(self):
        if self.week > 14:
            return "Regular season complete"
        games = self.schedule[self.week - 1]
        for team1_id, team2_id in games:
            self.simulate_game(team1_id, team2_id)
        self.week += 1
        self.save_season_state()

    def simulate_game(self, team1_id, team2_id):
        team1_score = random.randint(50, 90)
        team2_score = random.randint(50, 90)
        winner = team1_id if team1_score > team2_score else team2_id
        loser = team2_id if winner == team1_id else team1_id

        self.db.teams.update_one({"_id": winner}, {"$inc": {"record.W": 1}})
        self.db.teams.update_one({"_id": loser}, {"$inc": {"record.L": 1}})
        self.db.teams.update_one(
            {"_id": team1_id},
            {"$inc": {"PF": team1_score, "PA": team2_score}}
        )
        self.db.teams.update_one(
            {"_id": team2_id},
            {"$inc": {"PF": team2_score, "PA": team1_score}}
        )
        self.db.games.insert_one({
            "team1_id": team1_id,
            "team2_id": team2_id,
            "team1_score": team1_score,
            "team2_score": team2_score,
            "week": self.week
        })

    def age_players(self):
        for team in self.teams:
            players = self.db.players.find({"team_id": team["_id"]})
            for player in players:
                if player["year"] == "Senior":
                    self.db.players.delete_one({"_id": player["_id"]})
                else:
                    new_year = self.promote_year(player["year"])
                    self.db.players.update_one({"_id": player["_id"]}, {"$set": {"year": new_year}})

    def promote_year(self, year):
        return {"Freshman": "Sophomore", "Sophomore": "Junior", "Junior": "Senior"}.get(year, year)

    def generate_recruits(self):
        self.recruit_manager.generate_recruits()

    def save_season_state(self):
        state = {"week": self.week, "schedule": self.schedule}
        if self.franchise_id:
            self.db.franchises.update_one(
                {"_id": self.franchise_id},
                {"$set": state}
            )
        else:
            result = self.db.franchises.insert_one(state)
            self.franchise_id = result.inserted_id

    # --- UI Integration Recommendations ---
    # /franchise/standings → use team records from self.db.teams
    # /franchise/roster → use self.db.players.find({"team_id": team_id})
    # /franchise/schedule → use self.schedule
    # /franchise/stats → aggregate from self.db.players (season_stats)
    # /franchise/recruits → use self.db.recruits.find()

class ScheduleManager:
    def __init__(self, teams):
        self.teams = [team["_id"] for team in teams]

    def generate_schedule(self):
        if len(self.teams) != 8:
            raise ValueError("This round-robin generator expects exactly 8 teams.")

        teams = list(self.teams)
        random.shuffle(teams)  # Randomize starting order

        schedule = []

        for round_index in range(len(teams) - 1):
            week = []
            for i in range(len(teams) // 2):
                home = teams[i]
                away = teams[-i - 1]
                # Alternate home/away each round
                if round_index % 2 == 0:
                    week.append((away, home))  # away at home
                else:
                    week.append((home, away))  # away at home
            schedule.append(week)
            # Rotate the teams (keep the first fixed)
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]

        # Second half of season: reverse home/away of first 7 weeks
        mirrored_schedule = [(home, away) for week in schedule for (away, home) in week]
        schedule += [mirrored_schedule[i:i+4] for i in range(0, len(mirrored_schedule), 4)]

        return schedule

# --- Drop-in replacement for RecruitManager (path-robust + same JSON schema) ---
class RecruitManager:
    def __init__(self, db, names_file: Path | None = None):
        self.db = db

        # Defaults only if file truly missing/malformed
        self.first_names = ["Jalen", "Marcus", "Tyrese", "Zion", "Cade"]
        self.last_names  = ["Walker", "Jackson", "Robinson", "Wright", "Anderson"]

        payload = None

        # 1) Try local path relative to this file: BackEnd/data/names/franchise_names.json
        try:
            default_path = (Path(__file__).resolve()
                            .parents[1] / "data" / "names" / "franchise_names.json")
            path = Path(names_file) if names_file else default_path
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            payload = None

        # 2) Fallback: importlib.resources (works when BackEnd is on sys.path)
        if payload is None:
            try:
                pkg = resources.files("BackEnd.data.names")
                with resources.open_text("BackEnd.data.names", "franchise_names.json", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                payload = None

        # 3) If we got data, validate keys and apply
        if isinstance(payload, dict):
            fn = payload.get("first_names")
            ln = payload.get("last_names")
            if isinstance(fn, list) and fn and isinstance(ln, list) and ln:
                self.first_names, self.last_names = fn, ln
            else:
                logger.warning("Names JSON missing non-empty 'first_names'/'last_names'; using fallback lists.")
        else:
            logger.warning("Could not load franchise_names.json from disk or package; using fallback lists.")

    def generate_recruits(self, count=40):
        recruits = []
        for _ in range(count):
            name = f"{random.choice(self.first_names)} {random.choice(self.last_names)}"
            attributes = {k: random.randint(1, 30) for k in
                          ["SC","SH","ID","OD","PS","BH","RB","AG","ST","ND","IQ","FT"]}
            recruits.append({"name": name, "attributes": attributes,
                             "year": "Freshman", "created_at": datetime.utcnow()})

        if recruits:
            self.db.recruits.delete_many({})
            self.db.recruits.insert_many(recruits)

