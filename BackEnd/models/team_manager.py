import random
from copy import deepcopy
from BackEnd.db import teams_collection
from BackEnd.utils.roster_loader import load_roster
from BackEnd.models.player import Player
from BackEnd.constants import PLAYCALLS

# ✅ PERFORMANCE: Cache plays collection to avoid reloading during GameManager initialization
# This dramatically speeds up GameManager creation (from ~16s to <1s)
_plays_cache = None
_plays_names_cache = None

# ✅ PERFORMANCE: Cache scouting_data template to avoid recreating massive nested structure
# The first TeamManager creation is slow (~7.5s) because Python has to parse/allocate the structure.
# Subsequent creations are fast (~3ms) because memory allocator is warmed up.
# By caching the template and using deepcopy, we make ALL creations fast.
_scouting_data_template_cache = None

def _get_cached_scouting_data_template():
    """Get scouting_data template, creating and caching it if needed."""
    global _scouting_data_template_cache
    if _scouting_data_template_cache is None:
        # Create the template once (this will be slow the first time, but only once)
        _scouting_data_template_cache = _create_scouting_data_template_base()
    return deepcopy(_scouting_data_template_cache)

def _create_scouting_data_template_base():
    """Create the base scouting_data template structure (called once to populate cache)."""
    # Helper function to create a fresh defense structure
    def create_fresh_defense():
        template = TeamManager._create_defense_structure_template()
        return template
    
    # New playcall tracking structure
    return {
        "offense": {
            "Fast_Break_Entries": 0,
            "Fast_Break_Success": 0,
            # Motion / Set buckets and cumulative (attempts/success)
            "Playcalls": {
                "Motion": {
                    "overall": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                    "inside": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                    "attack": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                    "outside": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                },
                "Set": {
                    "overall": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                    "inside": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                    "attack": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                    "outside": {
                        "attempts": 0, 
                        "success": 0,
                        "ev_scores": [],
                        "lean_scores": [],
                        "vs_man": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_2-3_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_3-2_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                        "vs_1-3-1_zone": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
                    },
                },
                "Cumulative": {
                    "inside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                    "attack": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                    "outside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                }
            },
            # Track last play run for each category (for tooltips)
            "last_play_by_category": {
                "motion_inside": None,
                "motion_attack": None,
                "motion_outside": None,
                "set_inside": None,
                "set_attack": None,
                "set_outside": None
            }
        },
        "defense": {
            # Create fresh defense structures (will be customized per team/mode)
            "Man": create_fresh_defense(),
            "2-3 Zone": create_fresh_defense(),
            "3-2 Zone": create_fresh_defense(),
            "1-3-1 Zone": create_fresh_defense(),
            "vs_Fast_Break": {"used": 0, "success": 0},
            "FCP": {"used": 0, "success": 0},
            "HCT": {"used": 0, "success": 0}
        }
    }

def _get_cached_plays():
    """Get all plays from database, using cache if available."""
    global _plays_cache
    if _plays_cache is None:
        from BackEnd.db import plays_collection
        _plays_cache = list(plays_collection.find({}))
    return _plays_cache

def _get_cached_play_names():
    """Get play names from database, using cache if available."""
    global _plays_names_cache
    if _plays_names_cache is None:
        plays = _get_cached_plays()
        _plays_names_cache = [play["name"] for play in plays]
    return _plays_names_cache

class TeamManager:
    def __init__(self, name: str, is_home_team=False, strategy_settings=None, team_attributes=None, scouting_data=None, plays_data=None, strategy_calls=None, mode="single", is_user_team=False, franchise_id=None):
        import time
        import logging
        self.name = name
        self.is_home_team = is_home_team
        self.is_user_team = is_user_team  # ✅ SS&S: Track if this is the user's team for override logic
        self.mode = mode  # Store mode for use in _init_scouting_data() and other methods
        self.franchise_id = franchise_id  # ✅ FRANCHISE MODE: Store franchise_id for loading trained attributes
        
        roster_start = time.time()
        self.players = self._load_roster()
        roster_time = (time.time() - roster_start) * 1000
        # ✅ REMOVED: Verbose performance logs - redundant
        
        self.lineup = self._load_lineup()
        
        # Load BASE team data from universal teams collection (name, team_id, colors, mascot)
        team_doc_start = time.time()
        team_doc = teams_collection.find_one({"name": name})
        team_doc_time = (time.time() - team_doc_start) * 1000
        # ✅ REMOVED: Verbose performance logs - redundant
        if not team_doc:
            print(f"⚠️ No team document found for team: {name}")
        self.team_id = team_doc.get("team_id") if team_doc else None
        self.primary_color = team_doc.get("primary_color", "#000000") if team_doc else "#000000"
        self.secondary_color = team_doc.get("secondary_color", "#ffffff") if team_doc else "#ffffff"
        self.mascot = team_doc.get("mascot", "") if team_doc else ""

        self.points = 0
        self.points_by_quarter = [0, 0, 0, 0]
        self.team_fouls = 0
        self.timeouts = 4  # Each team starts with 4 timeouts per game
        self.stats = {}
        self.team_stats = {}  # Team-level stats (release/get back tracking, fast break defender counts)
        
        # Use provided scouting_data or initialize fresh
        scouting_start = time.time()
        if scouting_data:
            self.scouting_data = scouting_data
        else:
            self.scouting_data = self._init_scouting_data()
        scouting_time = (time.time() - scouting_start) * 1000
        # ✅ REMOVED: Verbose performance logs - redundant

        # Use provided strategy_settings or fall back to random initialization
        # MALLEABLE: Generated per game instance (not loaded from universal teams collection)
        if strategy_settings and isinstance(strategy_settings, dict) and len(strategy_settings) > 0:
            # Ensure all required keys exist (merge with defaults if missing keys)
            default_settings = self._init_strategy_settings()
            self.strategy_settings = {**default_settings, **strategy_settings}  # User settings override defaults
        else:
            import logging
            if strategy_settings is not None:
                logging.warning(f"⚠️ [STRATEGY SETTINGS] {self.name} - strategy_settings provided but invalid (type={type(strategy_settings)}, len={len(strategy_settings) if isinstance(strategy_settings, dict) else 'N/A'}), using defaults")
            self.strategy_settings = self._init_strategy_settings()
        
        # ✅ SS&S: Initialize strategy_calls with call fields (None = use normal selection, value = use this call and clear after)
        # Use provided strategy_calls (from saved game) or initialize fresh
        if strategy_calls and isinstance(strategy_calls, dict):
            # Restore from saved game - ensure all keys exist (merge with defaults if missing keys)
            default_calls = {
                "offense_call": None,
                "defense_call": None,
                "aggression_override": None,
                "tempo_override": None,
                "press_override": None,
                "trap_override": None,
            }
            self.strategy_calls = {**default_calls, **strategy_calls}  # Saved calls override defaults
        else:
            # Initialize fresh (new game or no saved calls)
            self.strategy_calls = {
                "offense_call": None,          # Play name string or None (user override persists until used)
                "defense_call": None,          # "Man", "Zone", or None (user override persists until used)
                "aggression_override": None,   # "normal", "aggressive", "passive", or None (temporary override)
                "tempo_override": None,        # "slow", "normal", "fast", or None (temporary override)
                "press_override": None,        # Future: FCP override
                "trap_override": None,         # Future: HCT override
            }
        self.playcall_tracker = {pc: 0 for pc in PLAYCALLS}
        self.defense_playcall_tracker = {"Man": 0, "Zone": 0}
        
        # Use provided plays_data (from saved game) or initialize fresh from universal collection
        # MALLEABLE: Each game instance has its own copy with tracking stats
        plays_start = time.time()
        if plays_data:
            # Handle both dict (saved games) and list (new games) formats
            if isinstance(plays_data, dict):
                # Already in correct format (keyed by play name)
                self.plays = plays_data
            elif isinstance(plays_data, list):
                # Convert list to dict keyed by play name
                self.plays = {play["name"]: play for play in plays_data}
            else:
                # Invalid format, initialize fresh
                self.plays = self._init_plays_from_universal(mode)
        else:
            self.plays = self._init_plays_from_universal(mode)
        plays_time = (time.time() - plays_start) * 1000
        # ✅ REMOVED: Verbose performance logs - redundant
        
        # Use provided team_attributes or generate random values
        # MALLEABLE: Generated per game instance (not loaded from universal teams collection)
        if team_attributes:
            self.team_attributes = team_attributes
        else:
            self.team_attributes = self._init_team_attributes(mode)

    def _load_roster(self):
        _, players = load_roster(self.name, franchise_id=self.franchise_id)
        roster = {}
        for pdata in players:
            player = Player(pdata)
            roster[player.player_id] = player
        return roster

    def _load_lineup(self):
        # If you’re still defining self.players before this
        return {}  # default to empty dict — lineup will be set later

    def get_player_by_id(self, player_id):
        return self.players.get(player_id)

    def get_all_players(self):
        return self.players.values()

    @staticmethod
    def init_tempo_random():
        """
        Initialize tempo randomly per game with specified distribution:
        - 10% chance for 0
        - 20% chance for 1
        - 50% chance for 2
        - 20% chance for 3
        - 10% chance for 4
        """
        return random.choices([0, 1, 2, 3, 4], weights=[10, 20, 50, 20, 10], k=1)[0]
    
    def _init_strategy_settings(self):
        """
        Initialize strategy settings with weighted randomization for CPU teams (0-4 scale).
        If team document has strategy_settings, those will be used instead via constructor.
        
        Weighted Distribution (for offense, fast_breaks, defense, aggression):
        - 5% chance for 0
        - 15% chance for 1
        - 60% chance for 2 (normal/balanced)
        - 15% chance for 3
        - 5% chance for 4

        Weighted Distribution (for rebounding only):
        - 5% chance for 0, 10% for 1, 15% for 2, 30% for 3, 40% for 4
        
        Weighted Distribution (for hc_trap, fc_press):
        - 34% chance for 0
        - 40% chance for 1
        - 20% chance for 2
        - 5% chance for 3
        - 1% chance for 4
        
        Uniform Distribution (for inside, attack, outside):
        - Random 1-4 (never zero, ensures at least some focus on each area)
        
        Note: tempo is NOT initialized here - it's initialized randomly per game via init_tempo_random()
        """
        # Weighted distribution: 5% for 0/4, 15% for 1/3, 60% for 2
        weighted_choice = random.choices(
            [0, 1, 2, 3, 4],
            weights=[5, 15, 60, 15, 5],
            k=1
        )[0]
        
        # Special weighted distribution for hc_trap and fc_press
        trap_press_choice = random.choices(
            [0, 1, 2, 3, 4],
            weights=[34, 40, 20, 5, 1],
            k=1
        )[0]
        
        return {
            "offense": weighted_choice,
            "inside": random.randint(1, 4),  # Uniform 1-4 (never zero)
            "attack": random.randint(1, 4),  # Uniform 1-4 (never zero)
            "outside": random.randint(1, 4),  # Uniform 1-4 (never zero)
            "fast_breaks": random.choices([0, 1, 2, 3, 4], weights=[5, 15, 60, 15, 5], k=1)[0],
            "play_calling": random.choices([0, 1, 2, 3, 4], weights=[5, 15, 60, 15, 5], k=1)[0],
            "defense": random.choices([0, 1, 2, 3, 4], weights=[5, 15, 60, 15, 5], k=1)[0],
            "aggression": random.choices([0, 1, 2, 3, 4], weights=[5, 15, 60, 15, 5], k=1)[0],
            "hc_trap": trap_press_choice,
            "fc_press": trap_press_choice,
            "rebounding": random.choices([0, 1, 2, 3, 4], weights=[5, 10, 15, 30, 40], k=1)[0],
            # tempo is initialized per game, not per team
            "tempo": TeamManager.init_tempo_random()
        }

    @staticmethod
    def init_team_attributes(mode="single"):
        """
        Initialize team attributes for a new mode instance.
        
        Args:
            mode (str): Game mode ("single", "tournament", or "franchise")
                - Single Game & Tournament: Attributes use range -10 to 10, team_chemistry 7-25
                - Franchise: Attributes use range -3 to 3, team_chemistry 7-13
        
        Returns:
            dict: Team attributes with mode-specific randomization
        """
        # Common attributes for all modes
        shot_threshold = random.randint(-10, 190)
        
        # Mode-specific ranges
        if mode == "franchise":
            # Franchise mode: tighter ranges for more controlled progression
            attr_range = (-1, 1)
            team_chemistry = random.randint(7, 10)
            # Franchise: All teams start at center value (0.2)
            rebound_modifier = 0.2
        else:
            # Single Game & Tournament mode: wider ranges
            attr_range = (-10, 10)
            team_chemistry = random.randint(7, 25)
            # Single/Tournament: Random value 0.0-0.4 in 0.01 increments
            rebound_modifier = random.randint(0, 40) / 100.0
        
        return {
            "shot_threshold": shot_threshold,
            "discipline": random.randint(attr_range[0], attr_range[1]),
            "fight": random.randint(attr_range[0], attr_range[1]),
            "rebound_modifier": rebound_modifier,
            "offensive_efficiency": random.randint(attr_range[0], attr_range[1]),
            "team_chemistry": team_chemistry,
            "defensive_efficiency": random.randint(attr_range[0], attr_range[1]),
            "fb_efficiency": random.randint(attr_range[0], attr_range[1]),
            "pt_efficiency": random.randint(attr_range[0], attr_range[1]),
            "fb_opp_modifier": random.randint(attr_range[0], attr_range[1]),
            "pt_opp_modifier": random.randint(attr_range[0], attr_range[1])
        }
    
    def _init_team_attributes(self, mode="single"):
        """Instance method wrapper for static init_team_attributes."""
        return TeamManager.init_team_attributes(mode)

    @staticmethod
    def _create_defense_structure_template():
        """Create the standard defense structure template used by all defense types.
        
        Returns a dictionary with the standard structure for Man, 2-3 Zone, 3-2 Zone, and 1-3-1 Zone.
        This eliminates code duplication and makes it easier to add new defense types.
        
        ✅ PERFORMANCE: Made static and creates fresh structure each time (avoids deepcopy overhead).
        """
        return {
            "used": 0,
            "success": 0,
            "effectiveness": 0.0,  # Per-team effectiveness (training-impacted)
            "momentum": 0,          # Per-team momentum (training-impacted)
            "cloaking": 0,          # Per-team cloaking (training-impacted)
            "game_stats": {
                "used": 0,
                "success": 0,
                "ev_scores": [],
                "lean_scores": [],
                "vs_motion": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_set": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_inside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_attack": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_outside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_motion_inside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_motion_attack": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_motion_outside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_set_inside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_set_attack": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []},
                "vs_set_outside": {"attempts": 0, "success": 0, "ev_scores": [], "lean_scores": []}
            },
            "season_stats": {
                "used": 0,
                "success": 0,
                "vs_motion": {"attempts": 0, "success": 0},
                "vs_set": {"attempts": 0, "success": 0},
                "vs_inside": {"attempts": 0, "success": 0},
                "vs_attack": {"attempts": 0, "success": 0},
                "vs_outside": {"attempts": 0, "success": 0},
                "vs_motion_inside": {"attempts": 0, "success": 0},
                "vs_motion_attack": {"attempts": 0, "success": 0},
                "vs_motion_outside": {"attempts": 0, "success": 0},
                "vs_set_inside": {"attempts": 0, "success": 0},
                "vs_set_attack": {"attempts": 0, "success": 0},
                "vs_set_outside": {"attempts": 0, "success": 0}
            }
        }

    def _init_scouting_data(self):
        # Get actual play names from database (using cache)
        play_names = []
        try:
            play_names = _get_cached_play_names()
        except Exception as e:
            print(f"⚠️ Could not load play names for scouting data: {e}")
            play_names = PLAYCALLS  # Fallback to constants
        
        # ✅ PERFORMANCE: Use cached template and deepcopy (much faster than creating from scratch)
        # The first call will create the template (one-time cost), subsequent calls just deepcopy
        scouting_data = _get_cached_scouting_data_template()
        
        # Customize defense structures for tournament mode
        if self.mode == "tournament":
            for defense_name in ["Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"]:
                if defense_name in scouting_data["defense"]:
                    scouting_data["defense"][defense_name]["effectiveness"] = random.randint(0, 80)
                    scouting_data["defense"][defense_name]["momentum"] = random.randint(0, 10)
                    scouting_data["defense"][defense_name]["cloaking"] = random.randint(0, 10)
        
        return scouting_data
    
    def _init_plays_from_universal(self, mode="single"):
        """
        Initialize plays with REFERENCES to universal plays collection (not full skeletons).
        Creates team-specific copy with tracking stats based on mode.
        
        Args:
            mode: "single", "tournament", or "franchise"
            
        Returns:
            dict: {play_name: play_data} with play_id reference and stats (NO skeletons)
        """
        plays_dict = {}
        # ✅ PERFORMANCE: Use cached plays instead of reloading from database
        universal_plays = _get_cached_plays()
        
        for play in universal_plays:
            # Get initial values from universal play (if they exist), otherwise default to 0
            # In future, these will be modified by team training and in-game performance
            initial_effectiveness = play.get("effectiveness", 0)
            initial_momentum = play.get("momentum", 0)
            initial_cloaking = play.get("cloaking", 0)
            
            play_data = {
                "play_id": str(play["_id"]),  # Reference to universal play (the "library card")
                "name": play["name"],
                "play_type": play["play_type"], 
                "play_focus": play["play_focus"],
                # Per-team effectiveness, momentum, and cloaking (separate from calculated effectiveness in stats)
                "effectiveness": initial_effectiveness,
                "momentum": initial_momentum,
                "cloaking": initial_cloaking,
                # NO SKELETONS - fetched from universal collection when needed
                "game_stats": {
                    "times_run": 0,
                    "successes": 0,
                    "player_points": {},  # {player_id: total_points} - tracks points scored per player on this play
                    "effectiveness": 0.0  # Calculated effectiveness from stats
                }
            }
            
            # Add season_stats for tournament and franchise modes
            if mode in ["tournament", "franchise"]:
                play_data["season_stats"] = {
                    "times_run": 0,
                    "successes": 0,
                    "player_points": {},  # {player_id: total_points} - tracks points scored per player on this play
                    "effectiveness": 0.0  # Calculated effectiveness from stats
                }
            
            plays_dict[play["name"]] = play_data
        
        # Debug logging removed - was cluttering logs
        # logging.debug(f"📋 Initialized {len(plays_dict)} plays (reference-based) for {self.name} (mode: {mode})")
        return plays_dict

    def record_team_foul(self):
        self.team_fouls += 1

    def update_team_stats(self):
        totals = {}
        for player in self.players.values():
            for stat, val in player.stats["game"].items():
                if stat == "Outlet_Score_List":
                    # Outlet_Score_List is an array - concatenate lists from all players
                    if stat not in totals:
                        totals[stat] = []
                    if isinstance(val, list):
                        totals[stat].extend(val)
                else:
                    # Regular stat - sum numeric values
                    totals[stat] = totals.get(stat, 0) + val
        self.stats = totals

    def reset_for_new_game(self):
        self.points_by_quarter = [0, 0, 0, 0]
        self.team_fouls = 0
        self.timeouts = 4  # Reset to 4 timeouts for new game (timeouts carry over whole game, not reset per quarter)
        self.stats = {}
        self.team_stats = {}  # Reset team-level stats
        self.scouting_data = self._init_scouting_data()
        for player in self.players.values():
            player.stats["game"] = {stat: 0 for stat in player.stats["game"]}
            player.reset_energy()

    def get_player(self, position):
        return self.lineup.get(position)

    def get_all_lineup_players(self):
        return self.lineup.values()

    def get_full_roster(self):
        return self.players

    def get_team_game_stats(self):
        team_stats = {
            "PTS": 0,
            "FGM": 0,
            "FGA": 0,
            "3PTM": 0,
            "3PTA": 0,
            "FTM": 0,
            "FTA": 0,
            "OREB": 0,
            "DREB": 0,
            "REB": 0,
            "AST": 0,
            "STL": 0,
            "BLK": 0,
            "TO": 0,
            "F": 0,
            "PIP": 0,  # Points in Paint
            "FB_PTS": 0,  # Fast Break Points
            "POT": 0,  # Points Off Turnovers (from steal-initiated fast breaks)
            "DEF_A": 0,  # Defensive Attempts
            "DEF_S": 0,  # Defensive Stops
            "SCR_A": 0,  # Screen Attempts
            "SCR_S": 0,  # Screen Successes
        }

        # Include all players (not just current lineup) to capture bench contributions
        for player in self.players.values():
            stats = player.stats["game"]
            for key in team_stats:
                team_stats[key] += stats.get(key, 0)

        team_stats["REB"] = team_stats["OREB"] + team_stats["DREB"]
        
        # Add team-level stats (not aggregated from player stats)
        if hasattr(self, 'team_stats'):
            team_stats["release_instances"] = self.team_stats.get("release_instances", 0)
            team_stats["get_back_instances"] = self.team_stats.get("get_back_instances", 0)
            team_stats["actual_releases"] = self.team_stats.get("actual_releases", 0)
            team_stats["zero_defenders_back"] = self.team_stats.get("zero_defenders_back", 0)
            team_stats["one_defender_back"] = self.team_stats.get("one_defender_back", 0)
            team_stats["two_defenders_back"] = self.team_stats.get("two_defenders_back", 0)
        
        return team_stats

