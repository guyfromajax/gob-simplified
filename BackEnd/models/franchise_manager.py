import random
import time
from collections import Counter
from datetime import datetime
from functools import lru_cache
from itertools import combinations, permutations
from pathlib import Path
import json
import logging
import os

from BackEnd.main import run_simulation
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils import stat_updater
from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.utils.franchise_rank_prestige import (
    FRANCHISE_RANK_PRESTIGE_SYSTEM_VERSION,
    SOS_AVG_DEFAULT,
    core_total_player_attrs,
    rank_teams_for_week,
)


logger = logging.getLogger(__name__)


# Helper ---------------------------------------------------------------------
def _load_franchise_names_payload(filename: str, env_var: str | None = None) -> dict:
    paths_to_try = []

    env_path = os.environ.get(env_var) if env_var else None
    if env_path:
        paths_to_try.append(Path(env_path).expanduser())

    paths_to_try.append(Path(__file__).resolve().parents[1] / "data" / "names" / filename)
    paths_to_try.append(Path("BackEnd/data/names") / filename)

    try:
        import importlib.resources as pkg_resources
        from BackEnd.data import names
        if hasattr(pkg_resources, "files"):
            names_path = pkg_resources.files(names) / filename
            paths_to_try.append(Path(str(names_path)))
        elif hasattr(pkg_resources, "path"):
            with pkg_resources.path(names, filename) as p:
                paths_to_try.append(p)
    except Exception as e:
        logger.debug("Could not use importlib.resources for %s: %s", filename, e)

    for path in paths_to_try:
        abs_path = path.resolve() if hasattr(path, "resolve") else Path(path)
        exists = abs_path.is_file()
        logger.info("Checking franchise names resource at %s (exists=%s)", abs_path, exists)
        if not exists:
            continue
        try:
            with abs_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to parse franchise names resource %s: %s", abs_path, exc)

    msg = f"franchise names resource {filename} not found. Tried paths: {[str(p) for p in paths_to_try]}"
    logger.error(msg)
    raise FileNotFoundError(msg)


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

    payload = _load_franchise_names_payload("franchise_names.json", env_var="FRANCHISE_NAMES_FILE")
    fn = payload.get("first_names")
    ln = payload.get("last_names")
    if not isinstance(fn, list) or not isinstance(ln, list) or not fn or not ln:
        raise ValueError("franchise_names.json missing non-empty first_names/last_names lists")

    logger.info("✅ Loaded %d first names and %d last names", len(fn), len(ln))
    return fn, ln


@lru_cache(maxsize=1)
def _load_franchise_first_name_rankings() -> tuple[str, ...]:
    try:
        payload = _load_franchise_names_payload("franchise_first_name_rankings.json")
    except FileNotFoundError:
        logger.warning("Franchise first-name rankings not found; using uniform weighting")
        return tuple()

    ordered = payload.get("ordered_top_500")
    if not isinstance(ordered, list):
        logger.warning("Franchise first-name rankings malformed; using uniform weighting")
        return tuple()
    return tuple(str(name) for name in ordered if str(name).strip())


def build_franchise_first_name_weights(first_names: list[str]) -> list[float]:
    rankings = _load_franchise_first_name_rankings()
    if not rankings:
        return [1.0] * len(first_names)

    weights_by_name: dict[str, float] = {}
    for idx, ranked_name in enumerate(rankings):
        key = ranked_name.casefold()
        if idx < 250:
            weights_by_name[key] = 1.2
        else:
            weights_by_name[key] = 1.1

    weighted_count = 0
    weights = []
    for first_name in first_names:
        weight = weights_by_name.get(first_name.casefold(), 1.0)
        if weight > 1.0:
            weighted_count += 1
        weights.append(weight)

    logger.info(
        "Loaded Franchise first-name weights for %d/%d names (top250=1.2x, next250=1.1x)",
        weighted_count,
        len(first_names),
    )
    return weights


def choose_franchise_first_name(first_names: list[str], weights: list[float] | None = None) -> str:
    if not first_names:
        raise ValueError("No first names available for Franchise generation")
    if weights and len(weights) == len(first_names):
        return random.choices(first_names, weights=weights, k=1)[0]
    return random.choice(first_names)


@lru_cache(maxsize=1)
def get_franchise_name_assets() -> tuple[tuple[str, ...], tuple[str, ...], tuple[float, ...]]:
    first_names, last_names = load_franchise_names()
    first_name_weights = build_franchise_first_name_weights(first_names)
    return tuple(first_names), tuple(last_names), tuple(first_name_weights)


class FranchiseManager:
    def __init__(self, db):
        self.db = db
        self.teams = self.load_teams()
        self.week = 1
        # Phase 1: 26-week schedule for all 128 teams (conference → region → OOR).
        self.schedule_manager = ScheduleManager(self.teams)
        self.recruit_manager = RecruitManager(self.db)
        self.schedule = []
        self.franchise_id = None

    def _build_region_team_map(self) -> dict[str, list[str]]:
        region_map: dict[str, list[str]] = {r: [] for r in "ABCDEFGH"}
        for team in self.teams:
            region = str(team.get("region") or "").upper()
            if len(region) == 1 and region in region_map:
                region_map[region].append(str(team["_id"]))
        return region_map

    def _build_recruit_lean(self, home_region: str, region_team_ids: dict[str, list[str]]) -> dict[str, str | None]:
        lean = {"1": None, "2": None, "3": None}
        team_ids = list(region_team_ids.get(home_region, []))
        if not team_ids:
            lean["1"] = "open"
            return lean

        if random.random() < 0.75:
            lean["1"] = "open"
            return lean

        first_team_id = random.choice(team_ids)
        lean["1"] = first_team_id

        if random.random() < 0.20:
            remaining = [team_id for team_id in team_ids if team_id != first_team_id]
            if remaining:
                lean["2"] = random.choice(remaining)

        return lean

    def load_teams(self):
        return list(self.db.teams.find())

    def initialize_season(
        self,
        user_team_id: str | None = None,
        user_team_object_id: str | None = None,
        user_id: str | None = None,
    ):
        """
        Initialize a new franchise season.

        Args:
            user_team_id: Team name (e.g., "Morristown") - human-readable identifier
            user_team_object_id: Team ObjectId string (e.g., "507f1f77bcf86cd799439011") - database identifier
            user_id: Optional user ID for ownership (set when authenticated)
        """
        # ⏱️ Coarse timers: log step times at end to pinpoint init_season cost
        _perf = {}

        _t0 = time.time()
        # ✅ Do not delete all games: multi-tenant DB; franchise games are deleted when franchise is deleted.
        self.schedule = self.schedule_manager.generate_schedule()
        self.week = 1
        _perf["generate_schedule"] = (time.time() - _t0) * 1000
        # Optional: start at a later week for testing (e.g. week 14→15 transition)
        start_week_env = os.environ.get("FRANCHISE_START_WEEK")
        if start_week_env:
            try:
                w = int(start_week_env)
                if 1 <= w <= ScheduleManager.REGULAR_SEASON_WEEKS:
                    self.week = w
                    logger.info("FRANCHISE_START_WEEK=%s: starting franchise at week %s (testing)", start_week_env, self.week)
            except ValueError:
                pass
        # Diagnostic: always log so Railway search for FRANCHISE_START_WEEK returns a hit (WARNING so it shows)
        logger.warning(
            "FRANCHISE_START_WEEK env=%s -> starting at week %s",
            start_week_env if start_week_env is not None else "not set",
            self.week,
        )
        # ✅ Do not reset_stats(): that updates universal players/teams; franchise uses FPD/FTD only.

        zero_stats = {k: 0 for k in BOX_SCORE_KEYS}
        zero_stats["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer
        _t0 = time.time()
        existing = {}
        if self.franchise_id:
            existing = (
                self.db.franchises.find_one(
                    {"_id": self.franchise_id}, {"players": 1}
                )
                or {}
            )
        _perf["find_franchise"] = (time.time() - _t0) * 1000
        prev_stats = existing.get("players", {})
        players_map: dict[str, dict] = {}

        _t0 = time.time()
        # Load all players with their full attributes for franchise-specific storage
        players = self.db.players.find(
            {}, {"first_name": 1, "last_name": 1, "team": 1, "team_id": 1, "attributes": 1, "position_ratings": 1, "height": 1, "weight": 1, "year": 1, "jersey": 1}
        )
        for p in players:
            from BackEnd.models.player import Player
            pid = str(p.get("_id"))
            career = prev_stats.get(pid, {}).get("career", zero_stats.copy())
            meta = {
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
                "team": p.get("team", ""),
                "height": p.get("height"),
                "weight": p.get("weight"),
                "year": p.get("year"),
                "jersey": p.get("jersey"),
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
        _perf["players_find_and_loop"] = (time.time() - _t0) * 1000

        # Initialize franchise-specific team stats using mode initialization system
        from BackEnd.models.team_manager import TeamManager
        from BackEnd.api.gameplan_routes import populate_team_plays, populate_scouting_data, _get_cached_playbook_settings

        _t0 = time.time()
        populated_plays = populate_team_plays(mode="franchise")
        _perf["populate_team_plays"] = (time.time() - _t0) * 1000
        _t0 = time.time()
        scouting_data = populate_scouting_data(mode="franchise")
        _perf["populate_scouting_data"] = (time.time() - _t0) * 1000
        _t0 = time.time()
        playbook_settings = _get_cached_playbook_settings()
        _perf["initialize_playbook_settings"] = (time.time() - _t0) * 1000

        # Initialize training status - training camp happens at week 1 before games are played
        training_status = {
            "training_completed": False,
            "session_type": "preseason",  # First training is always training camp
            "last_training_date": None  # No training completed yet
        }

        _t0 = time.time()
        # Generate initial recruits for the franchise
        recruits = self.recruit_manager.generate_recruits_list(count=300)
        _perf["generate_recruits"] = (time.time() - _t0) * 1000

        # ✅ FPD/FRD: Store players and recruits in standalone collections; keep franchise doc lean
        # Team data lives in FTD (franchise_team_data); we no longer write franchise_teams on the franchise doc.
        extra_state = {
            "players": {},  # FPD holds player data; empty here for legacy safety
            "recruits": [],  # FRD holds recruit data; empty here for legacy safety
            "recruiting_results": {},
            "recruiting_lean_updates_applied": {},
            "applied_games": [],
            "rank_prestige_system_version": FRANCHISE_RANK_PRESTIGE_SYSTEM_VERSION,
            "rank_prestige_last_applied_week": 0,
            "training_status": training_status,
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
        if user_id:
            extra_state["user_id"] = user_id

        _t0 = time.time()
        self.save_season_state(extra_state=extra_state)
        _perf["save_season_state"] = (time.time() - _t0) * 1000

        # ✅ FTD/FPD/FRD: Create franchise_team_data, franchise_players_data, franchise_recruits_data
        # *after* franchise insert so we have franchise_id.
        import uuid as uuid_module
        from BackEnd.db import (
            franchise_team_data_collection,
            franchise_players_data_collection,
            franchise_recruits_data_collection,
            ensure_ftd_index,
            ensure_fpd_index,
            ensure_frd_index,
        )

        ensure_ftd_index()
        ensure_fpd_index()
        ensure_frd_index()

        # New season flow rewrites FPD/FRD for the current franchise.
        franchise_players_data_collection.delete_many({"franchise_id": str(self.franchise_id)})
        franchise_recruits_data_collection.delete_many({"franchise_id": str(self.franchise_id)})

        # ✅ FPD: Batch insert (one round-trip instead of N)
        fpd_docs = [
            {
                "franchise_id": str(self.franchise_id),
                "player_id": pid,
                "meta": data["meta"],
                "season": data["season"],
                "career": data["career"],
                "attributes": data["attributes"],
                "position_ratings": data["position_ratings"],
            }
            for pid, data in players_map.items()
        ]
        _t0 = time.time()
        if fpd_docs:
            franchise_players_data_collection.insert_many(fpd_docs)
        _perf["fpd_insert_many"] = (time.time() - _t0) * 1000

        region_team_ids = self._build_region_team_map()

        # ✅ FRD: Batch insert (one round-trip instead of N)
        frd_docs = [
            {
                "franchise_id": str(self.franchise_id),
                "recruit_id": str(uuid_module.uuid4()),
                "name": recruit["name"],
                "attributes": recruit["attributes"],
                "position_ratings": recruit["position_ratings"],
                "height": recruit["height"],
                "weight": recruit["weight"],
                "archetype": recruit["archetype"],
                "year": recruit["year"],
                "Home Region": home_region,
                "Lean": self._build_recruit_lean(home_region, region_team_ids),
                "created_at": recruit["created_at"],
            }
            for recruit in recruits
            for home_region in [random.choice(list(region_team_ids.keys()))]
        ]
        _t0 = time.time()
        if frd_docs:
            franchise_recruits_data_collection.insert_many(frd_docs)
        _perf["frd_insert_many"] = (time.time() - _t0) * 1000

        _t0 = time.time()
        team_name_to_total_attrs = {}
        for p in self.db.players.find({}, {"team": 1, "attributes": 1}):
            tname = (p.get("team") or "").strip()
            if tname:
                team_name_to_total_attrs[tname] = team_name_to_total_attrs.get(tname, 0) + core_total_player_attrs(p.get("attributes") or {})
        _perf["team_total_attrs_agg"] = (time.time() - _t0) * 1000

        # Preseason natl_rank: prestige + 10% total_player_attrs; ties broken randomly once.
        rank_inputs = []
        for team in self.teams:
            team_object_id = team["_id"]
            team_name = team.get("name") or ""
            total_attrs = team.get("total_player_attrs") if team.get("total_player_attrs") is not None else team_name_to_total_attrs.get(team_name, 0)
            base_prestige = int(team.get("prestige") or 0)
            prestige_ftd = max(200, base_prestige + random.randint(-30, 30))
            rank_inputs.append({
                "team_id": str(team_object_id),
                "team_name": team_name,
                "total_player_attrs": total_attrs,
                "prestige": prestige_ftd,
                "sos_avg": SOS_AVG_DEFAULT,
            })

        team_id_to_rank_data = {}
        for ranked in rank_teams_for_week(rank_inputs, week=0):
            team_id_to_rank_data[ranked["team_id"]] = {
                "prestige": ranked["prestige"],
                "total_player_attrs": ranked["total_player_attrs"],
                "natl_rank": ranked["natl_rank"],
                "sos_avg": SOS_AVG_DEFAULT,
                "sos_rank_sum": 0,
                "sos_games_played": 0,
            }
        _perf["natl_rank_compute"] = (time.time() - _t0) * 1000

        _t0 = time.time()
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
                "offense": 2,
                "inside": 2,
                "attack": 2,
                "outside": 2,
                "fast_breaks": 2,
                "tempo": 2,
                "defense": 2,
                "aggression": 2,
                "hc_trap": 2,
                "fc_press": 2,
                "rebounding": 2,
            }
            # Roster for this team in this franchise (player _id UUID strings); used for roster/stats lookups
            team_player_ids = team.get("player_ids", [])
            players = [str(pid) for pid in team_player_ids]

            rank_data = team_id_to_rank_data.get(str(team_object_id), {})
            prestige_ftd = rank_data.get("prestige", 0)
            total_player_attrs = rank_data.get("total_player_attrs", 0)
            natl_rank = rank_data.get("natl_rank", 128)

            ftd_doc = {
                "franchise_id": self.franchise_id,
                "team_id": team_object_id,
                "players": players,
                "scholarship_players": players[:12],
                "training_squad_players": players[12:15],
                "playing_time_promise_players": [],
                "Recruits": {str(i): None for i in range(1, 21)},
                "recruiting_orders_week_35": {},
                "recruit_visit": None,
                "team_attributes": team_attributes,
                "strategy_settings": strategy_settings,
                "playbook_settings": playbook_settings.copy(),
                "plays": populated_plays.copy(),
                "scouting_data": scouting_data.copy(),
                "training_reports": {},
                "prestige": prestige_ftd,
                "total_player_attrs": total_player_attrs,
                "natl_rank": natl_rank,
                "sos_avg": rank_data.get("sos_avg", SOS_AVG_DEFAULT),
                "sos_rank_sum": rank_data.get("sos_rank_sum", 0),
                "sos_games_played": rank_data.get("sos_games_played", 0),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            franchise_team_data_collection.update_one(
                {"franchise_id": self.franchise_id, "team_id": team_object_id},
                {"$set": ftd_doc},
                upsert=True,
            )
        _perf["ftd_update_one_loop"] = (time.time() - _t0) * 1000

        logger.warning(
            "⏱️ [PERF] init_season breakdown: %s",
            " ".join(f"{k}={v:.0f}ms" for k, v in _perf.items()),
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
        if self.week > ScheduleManager.REGULAR_SEASON_WEEKS:
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

def _double_round_robin_8(team_ids):
    """Generate 14 rounds of 4 games (away_id, home_id) for 8 teams. Double round-robin, 1H/1A per pair."""
    if len(team_ids) != 8:
        raise ValueError("_double_round_robin_8 expects exactly 8 team IDs.")
    teams = list(team_ids)
    random.shuffle(teams)
    schedule = []
    for round_index in range(7):
        week = []
        for i in range(4):
            home = teams[i]
            away = teams[-i - 1]
            if round_index % 2 == 0:
                week.append((away, home))
            else:
                week.append((home, away))
        schedule.append(week)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    mirrored = [(home, away) for week in schedule for (away, home) in week]
    schedule += [mirrored[i : i + 4] for i in range(0, len(mirrored), 4)]
    return schedule


def _validate_schedule_one_game_per_team_per_week(schedule, expected_teams=128):
    """Ensure every week has each of expected_teams playing exactly one game. O(weeks * games)."""
    for week_idx, week_games in enumerate(schedule):
        counts = Counter()
        for away_id, home_id in week_games:
            counts[str(away_id)] += 1
            counts[str(home_id)] += 1
        if len(counts) != expected_teams:
            raise ValueError(
                "Schedule validation failed: week %d has %d distinct teams (expected %d)."
                % (week_idx + 1, len(counts), expected_teams)
            )
        if any(c != 1 for c in counts.values()):
            bad = [tid for tid, c in counts.items() if c != 1]
            raise ValueError(
                "Schedule validation failed: week %d has teams playing != 1 game: %s."
                % (week_idx + 1, bad[:5])
            )


class ScheduleManager:
    """
    Phase 1 franchise schedule: 26 weeks for 128 teams.
    Weeks 1–14: conference (14 games per team, 64 games/week).
    Weeks 15–22: region (8 games per team, 64 games/week).
    Weeks 23–26: out-of-region (4 games per team, 64 games/week).
    """

    REGULAR_SEASON_WEEKS = 26
    CONFERENCE_WEEKS = 14
    REGION_WEEKS = 8
    OOR_WEEKS = 4

    def __init__(self, teams):
        """
        Args:
            teams: List of team docs with _id, conference (1–16), region ("A"–"H").
        """
        self.teams = teams
        self._by_conference = None
        self._by_region = None

    def _index_teams(self):
        if self._by_conference is not None:
            return
        by_conf = {}
        by_region = {}
        for t in self.teams:
            c = t.get("conference")
            r = t.get("region")
            if c is not None:
                by_conf.setdefault(c, []).append(t["_id"])
            if r is not None:
                by_region.setdefault(r, []).append(t["_id"])
        self._by_conference = by_conf
        self._by_region = by_region

    def generate_schedule(self):
        """Return 26 weeks, each a list of (away_id, home_id). 64 games per week."""
        self._index_teams()
        if len(self.teams) != 128:
            raise ValueError(
                "Franchise schedule expects exactly 128 teams, got %d." % len(self.teams)
            )
        out = []
        # Weeks 1–14: conference block
        conf_rounds = []
        for c in range(1, 17):
            ids = self._by_conference.get(c, [])
            if len(ids) != 8:
                raise ValueError(
                    "Conference %d has %d teams, expected 8." % (c, len(ids))
                )
            conf_rounds.append(_double_round_robin_8(ids))
        for w in range(self.CONFERENCE_WEEKS):
            week = []
            for conf_sched in conf_rounds:
                week.extend(conf_sched[w])
            out.append(week)

        # Weeks 15–22: region block (sister-conference matchups). 8 weeks, 64 games/week.
        region_letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
        region_weeks = []
        for round_idx in range(8):
            week = []
            for r in region_letters:
                conf1, conf2 = (ord(r) - ord("A")) * 2 + 1, (ord(r) - ord("A")) * 2 + 2
                c1_ids = self._by_conference.get(conf1, [])
                c2_ids = self._by_conference.get(conf2, [])
                for i in range(8):
                    j = (i + round_idx) % 8
                    if i in [(round_idx + k) % 8 for k in range(4)]:
                        week.append((c2_ids[j], c1_ids[i]))
                    else:
                        week.append((c1_ids[i], c2_ids[j]))
            region_weeks.append(week)
        out = out[: self.CONFERENCE_WEEKS] + region_weeks

        # Weeks 23–26: out-of-region. Each team gets 2 home and 2 away OOR games.
        # Rotate which 8 teams in each region are home each week: week w uses indices
        # (w*4+j)%16 for j in 0..7 as home, (w*4+8+j)%16 as away.
        pairings = [
            [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H")],
            [("A", "C"), ("B", "D"), ("E", "G"), ("F", "H")],
            [("A", "D"), ("B", "C"), ("E", "H"), ("F", "G")],
            [("A", "E"), ("B", "F"), ("C", "G"), ("D", "H")],
        ]
        for week_idx, pairing_list in enumerate(pairings):
            week = []
            for r1, r2 in pairing_list:
                ids1 = self._by_region.get(r1, [])
                ids2 = self._by_region.get(r2, [])
                if len(ids1) != 16 or len(ids2) != 16:
                    raise ValueError(
                        "Region %s or %s has wrong size." % (r1, r2)
                    )
                w = week_idx
                # 8 games: r1 home (r1 indices (w*4+j)%16), r2 away (same slot pattern)
                for i in range(8):
                    week.append((ids2[(w * 4 + i) % 16], ids1[(w * 4 + i) % 16]))
                # 8 games: r1 away, r2 home (use other 8 from r2 as home: (w*4+8+i)%16)
                for i in range(8):
                    week.append((ids1[(w * 4 + 8 + i) % 16], ids2[(w * 4 + 8 + i) % 16]))
            out.append(week)

        # Randomize week order: same 14 conf + 8 region + 4 OOR blocks, shuffled each new season
        random.shuffle(out)
        _validate_schedule_one_game_per_team_per_week(out)
        return out

class RecruitManager:
    """Manage recruit generation using optional external name data."""

    def __init__(self, db):
        self.db = db

        # Defaults only if file truly missing/malformed
        self.first_names = ["Jalen", "Marcus", "Tyrese", "Zion", "Cade"]
        self.last_names = ["Walker", "Jackson", "Robinson", "Wright", "Anderson"]

        self.diagnostics = None

        try:
            loaded_first, loaded_last, loaded_weights = get_franchise_name_assets()
            self.first_names = list(loaded_first)
            self.last_names = list(loaded_last)
            self.first_name_weights = list(loaded_weights)
            logger.info(f"✅ Loaded {len(self.first_names)} first names and {len(self.last_names)} last names for recruits")
        except Exception as exc:
            logger.error(f"❌ Failed to load franchise names, using fallback: {exc}")
            logger.error(f"Fallback names: {len(self.first_names)} first, {len(self.last_names)} last")
            self.first_name_weights = [1.0] * len(self.first_names)

    def generate_recruits_list(self, count=40):
        """Generate and return a list of recruits (does not save to DB)."""
        from BackEnd.utils.position_ratings import compute_position_ratings
        
        recruits = []
        for _ in range(count):
            first_name = choose_franchise_first_name(self.first_names, self.first_name_weights)
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
