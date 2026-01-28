import random
from datetime import datetime
from itertools import combinations, permutations
from pathlib import Path
import json
import logging
import os

from BackEnd.main import run_simulation
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils import stat_updater
from BackEnd.constants import BOX_SCORE_KEYS


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

    # Try multiple path resolution strategies
    paths_to_try = []
    
    # 1. Environment variable
    env_path = os.environ.get("FRANCHISE_NAMES_FILE")
    if env_path:
        paths_to_try.append(Path(env_path).expanduser())
    
    # 2. Relative to this file
    paths_to_try.append(Path(__file__).resolve().parents[1] / "data" / "names" / "franchise_names.json")
    
    # 3. Relative to current working directory (for deployed environments)
    paths_to_try.append(Path("BackEnd/data/names/franchise_names.json"))
    
    # 4. Try using importlib.resources for packaged data
    try:
        import importlib.resources as pkg_resources
        from BackEnd.data import names
        if hasattr(pkg_resources, 'files'):
            # Python 3.9+
            names_path = pkg_resources.files(names) / "franchise_names.json"
            paths_to_try.append(Path(str(names_path)))
        elif hasattr(pkg_resources, 'path'):
            # Python 3.7-3.8
            with pkg_resources.path(names, "franchise_names.json") as p:
                paths_to_try.append(p)
    except Exception as e:
        logger.debug("Could not use importlib.resources: %s", e)
    
    # Try each path
    for path in paths_to_try:
        abs_path = path.resolve() if hasattr(path, 'resolve') else Path(path)
        exists = abs_path.is_file()
        logger.info("Checking franchise names at %s (exists=%s)", abs_path, exists)
        
        if exists:
            try:
                with abs_path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                
                fn = payload.get("first_names")
                ln = payload.get("last_names")
                if not isinstance(fn, list) or not isinstance(ln, list) or not fn or not ln:
                    logger.warning("Names JSON malformed at %s", abs_path)
                    continue
                
                logger.info("✅ Loaded %d first names and %d last names from %s", len(fn), len(ln), abs_path)
                return fn, ln
            except Exception as exc:
                logger.warning("Failed to parse franchise names JSON %s: %s", abs_path, exc)
                continue
    
    # If we get here, none of the paths worked
    msg = f"franchise names file not found. Tried paths: {[str(p) for p in paths_to_try]}"
    logger.error(msg)
    raise FileNotFoundError(msg)


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

    def initialize_season(self, user_team_id: str | None = None, user_team_object_id: str | None = None):
        """
        Initialize a new franchise season.
        
        Args:
            user_team_id: Team name (e.g., "Morristown") - human-readable identifier
            user_team_object_id: Team ObjectId string (e.g., "507f1f77bcf86cd799439011") - database identifier
        """
        # Clear any previous season game data to ensure a fresh start
        self.db.games.delete_many({})
        self.schedule = self.schedule_manager.generate_schedule()
        self.week = 1
        self.reset_stats()

        zero_stats = {k: 0 for k in BOX_SCORE_KEYS}
        zero_stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
        existing = {}
        if self.franchise_id:
            existing = (
                self.db.franchises.find_one(
                    {"_id": self.franchise_id}, {"players": 1}
                )
                or {}
            )
        prev_stats = existing.get("players", {})
        players_map: dict[str, dict] = {}
        
        # Load all players with their full attributes for franchise-specific storage
        players = self.db.players.find(
            {}, {"first_name": 1, "last_name": 1, "team": 1, "team_id": 1, "attributes": 1, "position_ratings": 1}
        )
        for p in players:
            from BackEnd.models.player import Player
            pid = str(p.get("_id"))
            career = prev_stats.get(pid, {}).get("career", zero_stats.copy())
            meta = {
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "team": p.get("team", ""),
            }
            tid = p.get("team_id")
            if tid is not None:
                meta["team_id"] = str(tid)
            
            # Clone player attributes and randomize EM, CH, MO for this franchise instance
            attrs = p.get("attributes", {}).copy()
            attrs = Player.randomize_game_attributes(attrs)
            
            # Store franchise-specific player attributes and position ratings (cloned from core collection)
            players_map[pid] = {
                "meta": meta,
                "season": zero_stats.copy(),
                "career": career,
                "attributes": attrs,  # Franchise-specific attributes with randomized EM/CH/MO
                "position_ratings": p.get("position_ratings", {}).copy(),  # Clone position ratings for this franchise
            }

        # Initialize franchise-specific team stats using mode initialization system
        from BackEnd.models.team_manager import TeamManager
        from BackEnd.api.gameplan_routes import populate_team_plays, populate_scouting_data, initialize_playbook_settings
        
        # Get populated plays and scouting data for all teams (franchise mode)
        populated_plays = populate_team_plays(mode="franchise")
        scouting_data = populate_scouting_data(mode="franchise")
        playbook_settings = initialize_playbook_settings()
        
        franchise_teams = {}  # Keep empty for backward compatibility (or remove later)

        # Initialize training status - training camp happens at week 1 before games are played
        training_status = {
            "training_completed": False,
            "session_type": "preseason",  # First training is always training camp
            "last_training_date": None  # No training completed yet
        }

        # Generate initial recruits for the franchise
        recruits = self.recruit_manager.generate_recruits_list()
        
        # Store user team identifiers in franchise document
        from datetime import datetime
        extra_state = {
            "players": players_map, 
            "applied_games": [],
            "franchise_teams": franchise_teams,
            "training_status": training_status,
            "recruits": recruits,
            # Add missing document-level fields (matches Tournament pattern)
            "created_at": datetime.utcnow(),
            "current_season": 1,  # Start at season 1
            "stats": {
                "top_10_points": [],
                "top_10_rebounds": [],
                "top_10_assists": [],
                "top_10_blocks": [],
                "top_10_steals": []
            }
        }
        
        # Add user team identifiers if provided
        if user_team_id:
            extra_state["user_team_id"] = user_team_id
        if user_team_object_id:
            extra_state["user_team_object_id"] = user_team_object_id
        
        self.save_season_state(extra_state=extra_state)

        # ✅ FTD: Create franchise_team_data documents *after* franchise insert so we have franchise_id.
        from BackEnd.db import franchise_team_data_collection, ensure_ftd_index
        from datetime import datetime

        ensure_ftd_index()
        for team in self.teams:
            team_object_id = team["_id"]
            team_attrs = TeamManager.init_team_attributes(mode="franchise")
            team_attributes = {
                "shot_threshold": team_attrs["shot_threshold"],
                "rebound_modifier": team_attrs["rebound_modifier"],
                "team_chemistry": team_attrs["team_chemistry"],
                "momentum_score": 0,
                "offensive_efficiency": team_attrs["offensive_efficiency"],
                "defensive_efficiency": team_attrs["defensive_efficiency"],
                "discipline": team_attrs["discipline"],
                "fight": team_attrs["fight"],
                "pt_opp_modifier": team_attrs["pt_opp_modifier"],
                "fb_opp_modifier": team_attrs["fb_opp_modifier"],
                "fb_efficiency": team_attrs["fb_efficiency"],
                "pt_efficiency": team_attrs["pt_efficiency"],
            }
            strategy_settings = {
                "offense": 2, "inside": 2, "attack": 2, "outside": 2,
                "tempo": 2, "defense": 2, "aggression": 2,
                "hc_trap": 2, "fc_press": 2, "rebounding": 2,
            }
            ftd_doc = {
                "franchise_id": self.franchise_id,
                "team_id": team_object_id,
                "team_attributes": team_attributes,
                "strategy_settings": strategy_settings,
                "playbook_settings": playbook_settings.copy(),
                "plays": populated_plays.copy(),
                "scouting_data": scouting_data.copy(),
                "training_reports": {},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            franchise_team_data_collection.update_one(
                {"franchise_id": self.franchise_id, "team_id": team_object_id},
                {"$set": ftd_doc},
                upsert=True,
            )

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

    def _save_game_result(self, team1_id, team2_id, team1_score, team2_score):
        """
        Save or update game result in games collection.
        
        ✅ FIX: This function no longer updates the universal teams collection.
        Franchise mode stores W/L and PF/PA in franchise.results, which is calculated
        when displaying team stats. This ensures franchise stats are isolated from
        other game modes and franchise instances.
        """
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
            filter_doc = {"_id": existing["_id"]}
        else:
            filter_doc = {"week": self.week, "team1_id": team1_id, "team2_id": team2_id}

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
            summary["_id"] = game_token
            self.db.games.update_one(
                {"_id": game_token}, {"$set": summary}, upsert=True
            )
            if self.franchise_id:
                stat_updater.finalize_game(
                    game_token,
                    mode="franchise",
                    franchise_id=str(self.franchise_id),
                )
            else:
                stat_updater.apply_stats_from_summary(summary, game_token)
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
        """
        Generate recruits and save them to the franchise document.
        Each franchise gets its own unique recruit pool with 40 players.
        Recruits are stored in the franchise.recruits field for isolation.
        """
        recruits = self.recruit_manager.generate_recruits_list()
        if self.franchise_id:
            self.db.franchises.update_one(
                {"_id": self.franchise_id}, 
                {"$set": {"recruits": recruits}}
            )
        return recruits

    def save_season_state(self, extra_state: dict | None = None):
        state = {"week": self.week, "schedule": self.schedule}
        if extra_state:
            state.update(extra_state)
        if self.franchise_id:
            self.db.franchises.update_one({"_id": self.franchise_id}, {"$set": state})
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
            loaded_first, loaded_last = load_franchise_names()
            self.first_names = loaded_first
            self.last_names = loaded_last
            logger.info(f"✅ Loaded {len(self.first_names)} first names and {len(self.last_names)} last names for recruits")
        except Exception as exc:
            logger.error(f"❌ Failed to load franchise names, using fallback: {exc}")
            logger.error(f"Fallback names: {len(self.first_names)} first, {len(self.last_names)} last")

    def generate_recruits_list(self, count=40):
        """Generate and return a list of recruits (does not save to DB)."""
        from BackEnd.utils.position_ratings import compute_position_ratings
        
        recruits = []
        for _ in range(count):
            first_name = random.choice(self.first_names)
            last_name = random.choice(self.last_names)
            # Format last name to title case (only first letter capitalized)
            last_name_formatted = last_name.title()
            name = f"{first_name} {last_name_formatted}"
            
            # Select archetype with weighted probabilities
            archetype = self._select_archetype()
            
            # Generate attributes, height, and weight based on archetype
            attributes, height, weight = self._generate_recruit_profile(archetype)
            
            # Randomize EM, CH, MO for recruits
            from BackEnd.models.player import Player
            attributes = Player.randomize_game_attributes(attributes)
            
            # Calculate position ratings for the recruit
            recruit_for_ratings = {
                "attributes": attributes,
                "height": height,
                "name": name
            }
            position_ratings = compute_position_ratings(recruit_for_ratings)
            
            recruits.append({
                "name": name, 
                "attributes": attributes,
                "position_ratings": position_ratings,
                "height": height,
                "weight": weight,
                "archetype": archetype,
                "year": "Freshman", 
                "created_at": datetime.utcnow()
            })
        
        return recruits
    
    def generate_recruits(self, count=40):
        """Legacy method: Generate recruits and save to global recruits collection.
        Deprecated - use generate_recruits_list() and store in franchise document instead.
        """
        recruits = self.generate_recruits_list(count)
        if recruits:
            self.db.recruits.delete_many({})
            self.db.recruits.insert_many(recruits)
    
    def _select_archetype(self):
        """Select a recruit archetype with weighted probabilities."""
        # Define archetypes with their selection weights
        # Five-Star and Four-Star are rare, others are equally common
        archetypes_weights = [
            ("Five-Star", 1),
            ("Four-Star", 4),
            ("Defensive Wizard", 3.6),
            ("All-Around Scorer", 3.6),
            ("Classic PG", 3.6),
            ("Classic SG", 3.6),
            ("Classic SF", 3.6),
            ("Classic PF", 3.6),
            ("Classic C", 3.6),
            ("Pure Shooter", 3.6),
            ("Intangibles", 3.6),
            ("Athlete", 3.6),
            ("Inside Defender", 3.6),
            ("Outside Defender", 3.6),
            ("Average", 13.6),
            ("Below Average", 13.6),
            ("Outside Dual Threat", 3.6),
            ("Driver", 3.6),
            ("Outside C", 3.6),
            ("Three & D", 3.6),
        ]
        
        archetypes = [a[0] for a in archetypes_weights]
        weights = [a[1] for a in archetypes_weights]
        
        return random.choices(archetypes, weights=weights, k=1)[0]
    
    def _generate_recruit_profile(self, archetype):
        """Generate attributes, height, and weight for a recruit based on archetype."""
        # Define attribute ranges
        STRONG = (20, 80)
        SECONDARY = (10, 60)
        STANDARD = (1, 40)
        WEAK = (1, 20)
        
        # All attributes start as STANDARD
        ALL_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "CH"]
        
        # Define archetype configurations: (strong_attrs, secondary_attrs, height_range)
        archetype_configs = {
            "Five-Star": (ALL_ATTRS, [], (69, 80)),
            "Four-Star": ([], ALL_ATTRS, (66, 78)),
            "Defensive Wizard": (["ID", "OD"], ["ST", "AG"], (66, 75)),
            "All-Around Scorer": (["SH", "SC"], ["ST", "AG"], (66, 75)),
            "Classic PG": (["BH", "PS"], ["OD", "IQ"], (66, 72)),
            "Classic SG": (["SH"], ["OD"], (66, 74)),
            "Classic SF": (["SC", "OD"], ["AG"], (69, 75)),
            "Classic PF": (["RB"], ["ST"], (70, 76)),
            "Classic C": (["ID", "ST"], ["RB", "SC"], (72, 78)),
            "Pure Shooter": (["SH", "FT"], [], (66, 73)),
            "Intangibles": (["IQ", "ND", "CH"], [], (66, 75)),
            "Athlete": (["AG", "ST", "ND"], [], (66, 75)),
            "Inside Defender": (["ST", "ID"], [], (71, 80)),
            "Outside Defender": (["AG", "OD"], [], (66, 74)),
            "Average": ([], [], (66, 75)),
            "Below Average": ([], [], (66, 74)),  # All weak
            "Outside Dual Threat": (["SH", "AG"], [], (66, 75)),
            "Driver": (["SC", "AG"], [], (66, 75)),
            "Outside C": (["ST", "SH"], [], (72, 77)),
            "Three & D": (["SH"], ["ID", "OD"], (69, 75)),
        }
        
        strong_attrs, secondary_attrs, height_range = archetype_configs[archetype]
        
        # Generate height first (needed for weight calculation)
        height = random.randint(height_range[0], height_range[1])
        
        # Generate weight based on height
        weight = self._generate_weight(height)
        
        # Generate attributes
        attributes = {}
        for attr in ALL_ATTRS:
            if archetype == "Below Average":
                # All attributes are weak for Below Average
                value = random.randint(WEAK[0], WEAK[1])
            elif attr in strong_attrs:
                value = random.randint(STRONG[0], STRONG[1])
            elif attr in secondary_attrs:
                value = random.randint(SECONDARY[0], SECONDARY[1])
            else:
                value = random.randint(STANDARD[0], STANDARD[1])
            
            attributes[attr] = value
        
        return attributes, height, weight
    
    def _generate_weight(self, height):
        """Generate weight based on height."""
        if height < 72:
            return random.randint(150, 181)
        elif 72 <= height <= 75:
            return random.randint(170, 194)
        elif 76 <= height <= 80:
            return random.randint(195, 231)
        else:  # > 80
            return random.randint(209, 260)

