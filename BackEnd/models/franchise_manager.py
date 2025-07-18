import random
from datetime import datetime

class FranchiseManager:
    def __init__(self, db):
        self.db = db
        self.teams = self.load_teams()
        self.week = 1
        self.schedule_manager = ScheduleManager(self.teams)
        self.recruit_manager = RecruitManager(self.db)
        self.schedule = []

    def load_teams(self):
        return list(self.db.teams.find())

    def initialize_season(self):
        self.schedule = self.schedule_manager.generate_schedule()
        self.week = 1
        self.reset_stats()
        self.save_season_state()

    def reset_stats(self):
        for team in self.teams:
            self.db.players.update_many({"team_id": team["_id"]}, {"$set": {"season_stats": {}}})
            self.db.teams.update_one({"_id": team["_id"]}, {"$set": {"season_stats": {}, "record": {"W": 0, "L": 0}}})

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
        self.db.franchise_state.update_one(
            {"_id": "state"},
            {"$set": {"week": self.week, "schedule": self.schedule}},
            upsert=True
        )

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
        matchups = []
        for i in range(len(self.teams)):
            for j in range(i + 1, len(self.teams)):
                matchups.append((self.teams[i], self.teams[j]))
                matchups.append((self.teams[j], self.teams[i]))
        random.shuffle(matchups)
        return [matchups[i:i+4] for i in range(0, 56, 4)]  # 14 weeks * 4 games

class RecruitManager:
    def __init__(self, db):
        self.db = db
        self.first_names = ["Jalen", "Marcus", "Tyrese", "Zion", "Cade"]
        self.last_names = ["Walker", "Jackson", "Robinson", "Wright", "Anderson"]

    def generate_recruits(self, count=40):
        recruits = []
        for _ in range(count):
            name = f"{random.choice(self.first_names)} {random.choice(self.last_names)}"
            attributes = {
                "SC": random.randint(1, 30),
                "SH": random.randint(1, 30),
                "ID": random.randint(1, 30),
                "OD": random.randint(1, 30),
                "PS": random.randint(1, 30),
                "BH": random.randint(1, 30),
                "RB": random.randint(1, 30),
                "AG": random.randint(1, 30),
                "ST": random.randint(1, 30),
                "ND": random.randint(1, 30),
                "IQ": random.randint(1, 30),
                "FT": random.randint(1, 30),
            }
            recruit = {
                "name": name,
                "attributes": attributes,
                "year": "Freshman",
                "created_at": datetime.utcnow()
            }
            recruits.append(recruit)

        if recruits:
            self.db.recruits.delete_many({})  # Optional: clear previous recruits
            self.db.recruits.insert_many(recruits)
