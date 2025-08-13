import random
from datetime import datetime
from itertools import combinations, permutations
from pathlib import Path
import json
import logging
import os

from BackEnd.main import run_simulation
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils.stat_updater import apply_stats_from_summary


logger = logging.getLogger(__name__)


# Helper ---------------------------------------------------------------------
def load_franchise_names() -> tuple[list[str], list[str]]:
    """Load recruit name lists from ``franchise_names.json``.

    The path is resolved from the ``FRANCHISE_NAMES_FILE`` environment
    variable, falling back to ``BackEnd/data/names/franchise_names.json``
    relative to this file. ``BackEnd.data.names`` must be importable so the
    JSON resource is packaged and available at runtime.

    Logs the absolute path checked (and whether it exists) along with counts of
    loaded first and last names.

    Returns:
        Tuple of ``(first_names, last_names)``.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the JSON is malformed or missing required keys.
    """

    env_path = os.environ.get("FRANCHISE_NAMES_FILE")
    default_path = Path(__file__).resolve().parents[1] / "data" / "names" / "franchise_names.json"
    path = Path(env_path).expanduser() if env_path else default_path
    abs_path = path.resolve()
    exists = abs_path.is_file()
    logger.info("Loading franchise names from %s (exists=%s)", abs_path, exists)
    if not exists:
        msg = f"franchise names file not found: {abs_path}"
        logger.warning(msg)
        raise FileNotFoundError(msg)

    try:
        with abs_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:  # pragma: no cover - json errors
        logger.warning("Failed to parse franchise names JSON %s: %s", abs_path, exc)
        raise ValueError(f"invalid franchise names JSON: {exc}") from exc

    fn = payload.get("first_names")
    ln = payload.get("last_names")
    if not isinstance(fn, list) or not isinstance(ln, list) or not fn or not ln:
        msg = "Names JSON malformed: expected non-empty 'first_names' and 'last_names' lists"
        logger.warning(msg)
        raise ValueError(msg)

    logger.info("Loaded %d first names and %d last names", len(fn), len(ln))
    return fn, ln


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
            self.db.players.update_many(
                {"team_id": team["_id"]},
                {
                    "$set": {
                        "stats.game": {},
                        "stats.season": {},
                        "stats.career": {},
                        "stats.applied_games": [],
                    },
                    "$unset": {"season_stats": ""},
                },
            )
            self.db.teams.update_one(
                {"_id": team["_id"]},
                {
                    "$set": {
                        "stats.season": {},
                        "record": {"W": 0, "L": 0},
                        "PF": 0,
                        "PA": 0,
                    },
                    "$unset": {"season_stats": ""},
                },
            )

    def run_week(self):
        if self.week > 14:
            return "Regular season complete"
        games = self.schedule[self.week - 1]
        for team1_id, team2_id in games:
            self.simulate_game(team1_id, team2_id)
        self.week += 1
        self.save_season_state()

    def _apply_team_result(self, team1_id, team2_id, team1_score, team2_score, sign=1):
        self.db.teams.update_one(
            {"_id": team1_id},
            {"$inc": {"PF": sign * team1_score, "PA": sign * team2_score, "record.W": 0, "record.L": 0}},
        )
        self.db.teams.update_one(
            {"_id": team2_id},
            {"$inc": {"PF": sign * team2_score, "PA": sign * team1_score, "record.W": 0, "record.L": 0}},
        )
        if team1_score > team2_score:
            self.db.teams.update_one({"_id": team1_id}, {"$inc": {"record.W": sign}})
            self.db.teams.update_one({"_id": team2_id}, {"$inc": {"record.L": sign}})
        elif team2_score > team1_score:
            self.db.teams.update_one({"_id": team2_id}, {"$inc": {"record.W": sign}})
            self.db.teams.update_one({"_id": team1_id}, {"$inc": {"record.L": sign}})

    def _save_game_result(self, team1_id, team2_id, team1_score, team2_score):
        existing = self.db.games.find_one(
            {
                "week": self.week,
                "$or": [
                    {"team1_id": team1_id, "team2_id": team2_id},
                    {"team1_id": team2_id, "team2_id": team1_id},
                ],
            }
        )
        if existing:
            self._apply_team_result(
                existing["team1_id"],
                existing["team2_id"],
                existing["team1_score"],
                existing["team2_score"],
                sign=-1,
            )
            filter_doc = {"_id": existing["_id"]}
        else:
            filter_doc = {"week": self.week, "team1_id": team1_id, "team2_id": team2_id}

        self._apply_team_result(team1_id, team2_id, team1_score, team2_score, sign=1)
        self.db.games.update_one(
            filter_doc,
            {
                "$set": {
                    "team1_id": team1_id,
                    "team2_id": team2_id,
                    "team1_score": team1_score,
                    "team2_score": team2_score,
                    "week": self.week,
                }
            },
            upsert=True,
        )

    def simulate_game(self, team1_id, team2_id):
        away_doc = self.db.teams.find_one({"_id": team1_id}, {"name": 1}) or {}
        home_doc = self.db.teams.find_one({"_id": team2_id}, {"name": 1}) or {}
        home_name = home_doc.get("name", "")
        away_name = away_doc.get("name", "")

        try:
            gm = run_simulation(home_name, away_name)
            team1_score = gm.score.get(away_name, 0)
            team2_score = gm.score.get(home_name, 0)
            summary = summarize_game_state(gm)
            game_token = f"{self.week}-{team1_id}-{team2_id}"
            apply_stats_from_summary(summary, game_token)
        except Exception:
            team1_score = random.randint(50, 90)
            team2_score = random.randint(50, 90)

        self._save_game_result(team1_id, team2_id, team1_score, team2_score)

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
    # /franchise/stats → aggregate from self.db.players (stats.season)
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

class RecruitManager:
    """Manage recruit generation using optional external name data."""

    def __init__(self, db):
        self.db = db

        # Defaults only if file truly missing/malformed
        self.first_names = ["Jalen", "Marcus", "Tyrese", "Zion", "Cade"]
        self.last_names = ["Walker", "Jackson", "Robinson", "Wright", "Anderson"]

        self.diagnostics = None

        try:
            self.first_names, self.last_names = load_franchise_names()
        except Exception as exc:
            logger.warning("Using fallback recruit names: %s", exc)

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

