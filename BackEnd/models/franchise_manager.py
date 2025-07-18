import random
from datetime import datetime

class FranchiseManager:
    def __init__(self, db):
        self.db = db  # MongoDB connection or collection wrapper
        self.teams = self.load_teams()
        self.week = 1
        self.schedule = []

    def load_teams(self):
        return list(self.db.teams.find())

    def initialize_season(self):
        self.schedule = self.generate_schedule()
        self.week = 1
        self.reset_stats()
        self.save_season_state()

    def generate_schedule(self):
        teams = [team["_id"] for team in self.teams]
        matchups = []
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                matchups.append((teams[i], teams[j]))
                matchups.append((teams[j], teams[i]))
        random.shuffle(matchups)
        return [matchups[i:i+4] for i in range(0, 56, 4)]  # 14 weeks * 4 games

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
        # Stub for now - would use existing game simulation engine
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
        first_names = ["Jalen", "Marcus", "Tyrese", "Zion", "Cade"]
        last_names = ["Walker", "Jackson", "Robinson", "Wright", "Anderson"]
        for _ in range(40):
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            attributes = {
                "SC": random.randint(1, 5),
                "SH": random.randint(1, 5),
                "ID": random.randint(1, 5),
                "OD": random.randint(1, 5),
                "PS": random.randint(1, 5),
                "BH": random.randint(1, 5),
                "RB": random.randint(1, 5),
                "AG": random.randint(1, 5),
                "ST": random.randint(1, 5),
                "ND": random.randint(1, 5),
                "IQ": random.randint(1, 5),
                "FT": random.randint(1, 5),
            }
            self.db.recruits.insert_one({
                "name": name,
                "attributes": attributes,
                "year": "Freshman",
                "created_at": datetime.utcnow()
            })

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
