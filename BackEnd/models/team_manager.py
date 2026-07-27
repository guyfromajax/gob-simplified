from BackEnd.utils.sim_random import sim_rng as random
from copy import deepcopy
from BackEnd.db import teams_collection
from BackEnd.utils.roster_loader import load_roster
from BackEnd.models.player import Player
from BackEnd.constants import PLAYCALLS
from BackEnd.constants.fast_break_play_types import default_fast_break_plays
from BackEnd.constants.hct_trap_play_types import default_hct_trap_plays

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
            # Per-play fast break (offense only); aggregates also in Fast_Break_* above
            "fast_break_plays": default_fast_break_plays(),
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
            "man": create_fresh_defense(),
            # First-class man plays (integrating_new_d_plays.md Step A): own scouting rows. Stats still
            # collapse to `man` until the Step C `canonical_scouting_defense_key` flip — these stay at
            # 0 until then (Deny/Loose start at 0 EFF by design; Base keeps the `man` row's EFF).
            "man-tight": create_fresh_defense(),
            "man-loose": create_fresh_defense(),
            "2-3-zone": create_fresh_defense(),
            "3-2-zone": create_fresh_defense(),
            "1-3-1-zone": create_fresh_defense(),
            "vs_Fast_Break": {"used": 0, "success": 0},
            "FCP": {"used": 0, "success": 0},
            "HCT": {"used": 0, "success": 0},
            # Per-trap-play A/S (defense-side mirror of offense.fast_break_plays).
            # Recorded in _record_hct_stats; explicit init for parity + safe
            # Scouting Report reads on fresh teams (lazy ensure_hct_trap_plays
            # still backfills older saves).
            "hct_trap_plays": default_hct_trap_plays()
        }
    }


def _deep_merge_scouting_dict(dst: dict, src: dict) -> None:
    """Merge src into dst in place. Preserves dst keys/skeleton when src omits them."""
    if not isinstance(src, dict):
        return
    for k, v in src.items():
        if k not in dst:
            dst[k] = deepcopy(v) if isinstance(v, dict) else v
        elif isinstance(dst[k], dict) and isinstance(v, dict):
            _deep_merge_scouting_dict(dst[k], v)
        else:
            dst[k] = v


def _remap_defense_scouting_keys_for_merge(defense_block: dict) -> dict:
    """Fold legacy display / variant keys onto canonical `defense_id` row keys before template merge."""
    from BackEnd.utils.defense_identity import SYNTHETIC_DEFENSE_IDS, canonical_scouting_defense_key

    if not isinstance(defense_block, dict):
        return {}
    out: dict = {}
    for k, v in defense_block.items():
        if not isinstance(k, str):
            continue
        if k in SYNTHETIC_DEFENSE_IDS:
            out[k] = deepcopy(v) if isinstance(v, dict) else v
            continue
        ck = canonical_scouting_defense_key(k)
        if not ck:
            out[k] = deepcopy(v) if isinstance(v, dict) else v
            continue
        if ck not in out:
            out[ck] = deepcopy(v) if isinstance(v, dict) else v
        elif isinstance(out[ck], dict) and isinstance(v, dict):
            _deep_merge_scouting_dict(out[ck], v)
        else:
            out[ck] = v
    return out


def _sync_defense_top_level_from_game_stats(defense: dict) -> None:
    """Keep legacy mirror fields aligned with game_stats when both exist (turn_manager updates both)."""
    for row in defense.values():
        if not isinstance(row, dict):
            continue
        gs = row.get("game_stats")
        if isinstance(gs, dict):
            if "used" in gs:
                row["used"] = gs["used"]
            if "success" in gs:
                row["success"] = gs["success"]


def normalize_scouting_data_for_gameplay(raw: dict | None) -> dict:
    """
    Merge persisted or partial scouting_data onto the canonical template.

    Ensures defense rows include top-level used/success, game_stats, season_stats, etc.,
    so turn resolution (e.g. run_micro_turn) does not KeyError on legacy/FTD-shaped rows.
    """
    base = _get_cached_scouting_data_template()
    if not raw:
        return base
    if isinstance(raw.get("offense"), dict):
        _deep_merge_scouting_dict(base["offense"], raw["offense"])
    if isinstance(raw.get("defense"), dict):
        remapped_def = _remap_defense_scouting_keys_for_merge(raw["defense"])
        _deep_merge_scouting_dict(base["defense"], remapped_def)
    _sync_defense_top_level_from_game_stats(base["defense"])
    return base


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
    def __init__(self, name: str, is_home_team=False, strategy_settings=None, team_attributes=None, scouting_data=None, plays_data=None, strategy_calls=None, mode="single", is_user_team=False, franchise_id=None, roster_override=None, synthetic_team_id=None):
        import time
        import logging
        self.name = name
        self.is_home_team = is_home_team
        self.is_user_team = is_user_team  # ✅ SS&S: Track if this is the user's team for override logic
        self.mode = mode  # Store mode for use in _init_scouting_data() and other methods
        self.franchise_id = franchise_id  # ✅ FRANCHISE MODE: Store franchise_id for loading trained attributes
        
        roster_start = time.time()
        if roster_override is not None:
            from BackEnd.models.player import Player
            self.players = {}
            for pdata in roster_override:
                player = Player(dict(pdata))
                self.players[str(player.player_id)] = player
        else:
            self.players = self._load_roster()
        roster_time = (time.time() - roster_start) * 1000

        lineup_start = time.time()
        self.lineup = self._load_lineup()
        lineup_time = (time.time() - lineup_start) * 1000

        # Load BASE team data from universal teams collection (name, team_id, colors, mascot)
        team_doc_start = time.time()
        team_doc = teams_collection.find_one({"name": name}) if roster_override is None else None
        team_doc_time = (time.time() - team_doc_start) * 1000
        if not team_doc and roster_override is None:
            print(f"⚠️ No team document found for team: {name}")
        # Players came from a caller-supplied roster (Practice Squad: FPD/FRD docs),
        # NOT from players_collection — so nothing about them should be written back
        # to the universal players collection. See GameManager._update_position_ratings.
        self.is_synthetic_roster = roster_override is not None
        if synthetic_team_id is not None:
            self.team_id = synthetic_team_id
        else:
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
            self.scouting_data = normalize_scouting_data_for_gameplay(scouting_data)
        else:
            self.scouting_data = self._init_scouting_data()
        scouting_time = (time.time() - scouting_start) * 1000

        import logging
        logging.debug(
            "⏱️ [PERF] TeamManager(%s): roster=%.0fms lineup=%.0fms team_doc=%.0fms scouting=%.0fms",
            name, roster_time, lineup_time, team_doc_time, scouting_time,
        )

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
            # Computer teams derive a strategic game plan from their projected
            # starting five (Game_Init_System.md § Computer Team Strategy Logic);
            # user teams keep the legacy random defaults (never auto-set).
            if not self.is_user_team:
                self.strategy_settings = self._compute_strategic_strategy_settings()
            else:
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
                "press_trap_override": None,  # "press", "trap", "none", or None
                "aggression_roll": None,      # per-break aggression roll (passive/normal/aggressive); set by roll_aggression_calls()
            }
            self.strategy_calls = {**default_calls, **strategy_calls}  # Saved calls override defaults
        else:
            # Initialize fresh (new game or no saved calls)
            self.strategy_calls = {
                "offense_call": None,          # Play name string or None (user override persists until used)
                "defense_call": None,          # Canonical slug (man, 2-3-zone) or legacy display; coerced in turn_manager
                "aggression_override": None,   # "normal", "aggressive", "passive", or None (temporary override)
                "tempo_override": None,        # "slow", "normal", "fast", or None (temporary override)
                "press_override": None,        # Future: FCP override
                "trap_override": None,         # Future: HCT override
                "press_trap_override": None,   # "press", "trap", "none", or None (playcall center)
                "aggression_roll": None,       # per-break aggression roll (passive/normal/aggressive); set by roll_aggression_calls()
            }
        self.playbook_settings = {}
        self.playcall_tracker = {pc: 0 for pc in PLAYCALLS}
        self.defense_playcall_tracker = {"man": 0, "zone": 0}
        
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
        Weighted roll centered on 2 (10/20/50/20/10 on 0–4).
        Used for CPU tempo (Q1–Q3 / init), CPU alterations, and GameManager
        fallback when tempo is missing from a team snapshot.
        """
        return random.choices([0, 1, 2, 3, 4], weights=[10, 20, 50, 20, 10], k=1)[0]

    def _compute_cpu_tempo(self, game_state=None):
        """CPU tempo slider (0–4). Game init and Q1–Q3: weighted roll centered on 2.
        Q4+ (including OT): score/time situational logic from the computer team's
        perspective (Game_Init_System.md § Computer Team Strategy Logic, point 5).
        """
        if not game_state:
            return TeamManager.init_tempo_random()

        quarter = int(game_state.get("quarter") or 1)
        if quarter < 4:
            return TeamManager.init_tempo_random()

        time_remaining = float(game_state.get("time_remaining") or 0)
        score_map = game_state.get("score") or {}
        my_score = int(score_map.get(self.name, 0) or 0)
        opp_score = None
        for team_name, score_val in score_map.items():
            if team_name != self.name:
                opp_score = int(score_val or 0)
                break
        if opp_score is None:
            return TeamManager.init_tempo_random()

        if my_score > opp_score:
            score_diff = my_score - opp_score
            if score_diff > time_remaining / 30:
                return 0
            return TeamManager.init_tempo_random()
        if my_score < opp_score:
            score_diff = opp_score - my_score
            if time_remaining > 90:
                if score_diff > time_remaining / 30:
                    return 4
                return TeamManager.init_tempo_random()
            if score_diff > time_remaining / 4:
                return 0
            if score_diff > time_remaining / 30:
                return 4
            return TeamManager.init_tempo_random()

        return TeamManager.init_tempo_random()
    
    def _init_strategy_settings(self):
        """
        Initialize strategy settings with weighted randomization for CPU teams (0-4 scale).
        If team document has strategy_settings, those will be used instead via constructor.
        
        Weighted Distribution (for offense, fast_breaks, defense):
        - 5% chance for 0
        - 15% chance for 1
        - 60% chance for 2 (normal/balanced)
        - 15% chance for 3
        - 5% chance for 4

        Weighted Distribution (for aggression):
        - 10% chance for 0
        - 20% chance for 1
        - 40% chance for 2
        - 20% chance for 3
        - 10% chance for 4

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
            "aggression": random.choices([0, 1, 2, 3, 4], weights=[10, 20, 40, 20, 10], k=1)[0],
            "hc_trap": trap_press_choice,
            "fc_press": trap_press_choice,
            "rebounding": random.choices([0, 1, 2, 3, 4], weights=[5, 10, 15, 30, 40], k=1)[0],
            "tempo": TeamManager.init_tempo_random(),
            "alterations": TeamManager.init_tempo_random(),
        }

    # --- Strategic (player-based) CPU strategy settings -----------------------
    # Game_Init_System.md § Computer Team Strategy Logic. Derives a computer
    # team's game-plan sliders from its five active players instead of pure
    # randomization. Used for COMPUTER teams at game init (projected starting
    # five) and at every quarter break / timeout / foul-out (the rebuilt
    # lineup). User-team settings are never auto-set.

    # Legacy weighted distributions, reused as the "standard logic" fallback.
    @staticmethod
    def _strategy_roll_balanced():
        return random.choices([0, 1, 2, 3, 4], weights=[5, 15, 60, 15, 5], k=1)[0]

    @staticmethod
    def _strategy_roll_aggression():
        return random.choices([0, 1, 2, 3, 4], weights=[10, 20, 40, 20, 10], k=1)[0]

    @staticmethod
    def _strategy_roll_trap_press():
        return random.choices([0, 1, 2, 3, 4], weights=[34, 40, 20, 5, 1], k=1)[0]

    @staticmethod
    def _strategy_roll_rebounding():
        return random.choices([0, 1, 2, 3, 4], weights=[5, 10, 15, 30, 40], k=1)[0]

    @staticmethod
    def _strategy_attr(player, key):
        """Player attribute value for strategy math. Mirrors the Scouting Report
        tab: prefer the ``anchor_<attr>`` baseline, fall back to the raw attr.
        """
        attrs = getattr(player, "attributes", {}) or {}
        try:
            return float(attrs.get(f"anchor_{key}", attrs.get(key, 0)) or 0)
        except (TypeError, ValueError):
            return 0.0

    def _resolve_strategy_active_five(self):
        """The five players strategy is derived from: the current 5-man lineup
        when set (in-game quarter break / timeout / foul-out), otherwise the
        projected starting five from the roster (game init — same selection the
        FCC Scouting Report uses: greedy best (player, open position) by rating).
        """
        lineup_players = [p for p in (self.lineup or {}).values() if p is not None]
        if len(lineup_players) >= 5:
            return lineup_players[:5]

        players = [p for p in self.players.values() if p is not None]
        positions = ("PG", "SG", "SF", "PF", "C")
        assigned: set = set()
        filled: set = set()
        chosen: list = []
        while len(filled) < 5:
            best = None  # (rt, player, pos)
            for p in players:
                pid = str(getattr(p, "player_id", "") or "")
                if not pid or pid in assigned:
                    continue
                pr = getattr(p, "position_ratings", {}) or {}
                for pos in positions:
                    if pos in filled:
                        continue
                    try:
                        rt = float(pr.get(pos))
                    except (TypeError, ValueError):
                        continue
                    if best is None or rt > best[0]:
                        best = (rt, p, pos)
            if best is None:
                break
            _, bp, bpos = best
            chosen.append(bp)
            filled.add(bpos)
            assigned.add(str(getattr(bp, "player_id", "") or ""))
        return chosen

    def _compute_strategic_strategy_settings(self, game_state=None):
        """Compute CPU strategy settings from the five active players.
        Falls back to the legacy random init if five players can't be resolved.
        """
        five = self._resolve_strategy_active_five()
        if len(five) < 5:
            settings = self._init_strategy_settings()
            settings["tempo"] = self._compute_cpu_tempo(game_state)
            settings["alterations"] = TeamManager.init_tempo_random()
            return settings

        def cum(key):
            return sum(self._strategy_attr(p, key) for p in five)

        settings = {}

        # Point 5: legacy rolls for offense / rebounding / play_calling; tempo and
        # alterations use weighted center-2 rolls (tempo is situational in Q4+).
        settings["offense"] = self._strategy_roll_balanced()
        settings["rebounding"] = self._strategy_roll_rebounding()
        settings["play_calling"] = self._strategy_roll_balanced()
        settings["tempo"] = self._compute_cpu_tempo(game_state)
        settings["alterations"] = TeamManager.init_tempo_random()

        # Point 2: offense-type tendencies (inside / attack / outside).
        scores = {
            "inside": cum("SC"),
            "outside": cum("SH"),
            "attack": (cum("SC") + cum("AG")) / 2.0,
        }
        ranked = sorted(scores, key=lambda k: scores[k])  # [lowest, middle, highest]
        lowest_k, middle_k, highest_k = ranked[0], ranked[1], ranked[2]
        middle_v = scores[middle_k]
        strong_k = highest_k if (scores[highest_k] - 70 > middle_v) else None
        weak_k = lowest_k if (scores[lowest_k] + 70 < middle_v) else None
        for k in ("inside", "attack", "outside"):
            if k == strong_k:
                settings[k] = random.randint(3, 4)
            elif k == weak_k:
                settings[k] = random.randint(0, 1)
            else:
                settings[k] = random.randint(1, 3)

        # Point 3: endurance-based hustle settings (hc_trap / fc_press /
        # fast_breaks / aggression). Independent rolls; fallbacks use legacy.
        cum_nd = cum("ND")
        endurance_d = cum("AG") + cum("OD")
        endurance_o = cum("AG") + cum("SC")
        intelligence = cum("IQ")
        if cum_nd < 200:  # weak endurance
            settings["hc_trap"] = random.randint(0, 2)
            settings["fc_press"] = random.randint(0, 2)
            settings["fast_breaks"] = random.randint(0, 2)
            settings["aggression"] = random.randint(0, 2)
        elif cum_nd > 350:  # strong endurance
            if endurance_d > 600:
                settings["hc_trap"] = random.randint(0, 4)
                settings["fc_press"] = random.randint(0, 4)
            else:
                settings["hc_trap"] = self._strategy_roll_trap_press()
                settings["fc_press"] = self._strategy_roll_trap_press()
            settings["fast_breaks"] = (
                random.randint(1, 4) if endurance_o > 600 else self._strategy_roll_balanced()
            )
            settings["aggression"] = (
                random.randint(2, 4) if intelligence > 300 else self._strategy_roll_aggression()
            )
        else:  # middle endurance → legacy standard rolls
            settings["hc_trap"] = self._strategy_roll_trap_press()
            settings["fc_press"] = self._strategy_roll_trap_press()
            settings["fast_breaks"] = self._strategy_roll_balanced()
            settings["aggression"] = self._strategy_roll_aggression()

        # Point 4: defensive strength scale.
        d_ability = cum("AG") + cum("ID") + cum("OD")
        if d_ability > 1200:
            settings["defense"] = random.randint(0, 2)
        elif d_ability > 900:
            settings["defense"] = random.randint(0, 3)
        elif d_ability > 700:
            settings["defense"] = random.randint(0, 4)
        elif d_ability > 500:
            settings["defense"] = random.randint(1, 4)
        else:
            settings["defense"] = random.randint(2, 4)

        return settings

    @staticmethod
    def init_team_attributes(mode="single", tournament_seed=None, shot_threshold_override=None):
        """
        Initialize team attributes for a new mode instance.

        Args:
            mode (str): Game mode ("single", "tournament", "franchise", or "tutorial")
            tournament_seed (int | None): For mode "tournament" only, seed 1-8 (1=best).
                When provided, uses seed-based ranges per Mode_Init_System.md.
            shot_threshold_override (int | None): If provided, replaces the randomly
                rolled shot_threshold. Used by the FTE v2 tutorial mode to pin the
                user team and computer team to forced-make / forced-miss values
                (see fte_inject_state.md §3). All other attributes still randomize
                per the standard mode logic.

        Returns:
            dict: Team attributes with mode-specific randomization
        """
        from BackEnd.constants import TEAM_ATTR_RANGES
        from BackEnd.constants.shot_threshold_scale import (
            FRANCHISE_INIT_HI,
            FRANCHISE_INIT_LO,
            TOURNAMENT_SEED_ST_RANGES,
        )

        # Tournament seed-based ranges (Mode_Init_System.md): Seed 1 = best, Seed 8 = worst
        if mode == "tournament" and tournament_seed is not None and 1 <= tournament_seed <= 8:
            # Tournament is a SUNSET mode: rebound cents left on the original 0.0-0.4
            # spread (harmless + truthful inside the 0.0-1.0 clamp; not re-centered).
            if tournament_seed == 1:
                a_lo, a_hi = 5, 10
                tc_lo, tc_hi = 20, 25
                rm_lo, rm_hi = 30, 40  # 0.30-0.40
            elif tournament_seed <= 4:
                a_lo, a_hi = -2, 10
                tc_lo, tc_hi = 12, 25
                rm_lo, rm_hi = 15, 40  # 0.15-0.40
            elif tournament_seed <= 7:
                a_lo, a_hi = -8, 5
                tc_lo, tc_hi = 8, 18
                rm_lo, rm_hi = 1, 40  # 0.01-0.40
            else:  # seed 8
                a_lo, a_hi = -10, -2
                tc_lo, tc_hi = 7, 12
                rm_lo, rm_hi = 1, 20  # 0.01-0.20
            st_lo, st_hi = TOURNAMENT_SEED_ST_RANGES[tournament_seed]
            attr_range = (a_lo, a_hi)
            team_chemistry = random.randint(tc_lo, tc_hi)
            rebound_modifier = round(random.randint(rm_lo, rm_hi) / 100.0, 2)
            shot_threshold = random.randint(st_lo, st_hi)
        else:
            # Common/single/franchise or tournament without seed (fallback).
            # Single-game is a SUNSET mode: keep its original 0.0-0.4 rebound spread
            # (not the widened 0.0-1.0 clamp range) — harmless + not re-centered.
            rm_lo, rm_hi = 0.0, 0.4
            if mode == "franchise":
                attr_range = (-2, 0)
                team_chemistry = random.randint(7, 10)
                rebound_modifier = 0.2  # init center stays 0.2 on the new 0.0-1.0 scale (Task 2)
                shot_threshold = random.randint(FRANCHISE_INIT_LO, FRANCHISE_INIT_HI)
            else:
                # Single Game or tournament fallback (no seed)
                st_lo, st_hi = TEAM_ATTR_RANGES["shot_threshold"]
                shot_threshold = random.randint(int(st_lo), int(st_hi))
                attr_range = (-10, 10)
                team_chemistry = random.randint(7, 25)
                rebound_modifier = round(rm_lo + random.random() * (rm_hi - rm_lo), 2)

        # Tutorial-only override: forced make/miss per fte_inject_state.md §3.
        if shot_threshold_override is not None:
            shot_threshold = int(shot_threshold_override)

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

    # The 8 core team attributes that re-roll at a new-season franchise rollover.
    ROLLOVER_CORE_ATTRS = (
        "discipline", "fight", "offensive_efficiency", "defensive_efficiency",
        "fb_efficiency", "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier",
    )

    @staticmethod
    def rollover_core_attr_range(carryover_count):
        """(lo, hi) randint range for the 8 core team attributes at a new-season
        rollover, scaled by how many players carry over from the prior season
        (active roster + training/practice squad, graduating seniors excluded):

            >=10 -> (-1, 2)   strong continuity
             7-9 -> (-2, 1)
              <7 -> (-3, 0)   heavy turnover

        See Team_Attribute_System.md (§ Season Rollover Re-Roll).
        """
        if carryover_count >= 10:
            return (-1, 2)
        if carryover_count >= 7:
            return (-2, 1)
        return (-3, 0)

    @staticmethod
    def init_franchise_rollover_team_attributes(carryover_count):
        """Fresh team_attributes for a new season in an EXISTING franchise.

        Nothing carries over from the prior season. Non-core fields
        (shot_threshold, rebound_modifier, team_chemistry) plus momentum/streaks
        re-initialize exactly like franchise creation; the 8 core attributes
        re-roll with a carryover-scaled range (rollover_core_attr_range).
        """
        base = TeamManager.init_team_attributes(mode="franchise")
        lo, hi = TeamManager.rollover_core_attr_range(carryover_count)
        return {
            "shot_threshold": base["shot_threshold"],
            "rebound_modifier": base["rebound_modifier"],
            "team_chemistry": base["team_chemistry"],
            "momentum_score": 0,
            "distant_win_streak": 0,
            "distant_loss_streak": 0,
            "offensive_efficiency": random.randint(lo, hi),
            "defensive_efficiency": random.randint(lo, hi),
            "discipline": random.randint(lo, hi),
            "fight": random.randint(lo, hi),
            "pt_opp_modifier": random.randint(lo, hi),
            "fb_opp_modifier": random.randint(lo, hi),
            "fb_efficiency": random.randint(lo, hi),
            "pt_efficiency": random.randint(lo, hi),
        }

    def _init_team_attributes(self, mode="single", shot_threshold_override=None):
        """Instance method wrapper for static init_team_attributes."""
        return TeamManager.init_team_attributes(mode, shot_threshold_override=shot_threshold_override)

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
            for defense_name in ("man", "2-3-zone", "3-2-zone", "1-3-1-zone"):
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
                "target_shooter": play.get("target_shooter"),
                "motion_focus": None if play.get("play_type") == "motion" else None,
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
        from BackEnd.utils.shared import sync_player_pts_from_shooting

        totals = {}
        for player in self.players.values():
            sync_player_pts_from_shooting(player)
            for stat, val in player.stats["game"].items():
                if stat == "Outlet_Score_List":
                    # Outlet_Score_List is an array - concatenate lists from all players
                    if stat not in totals:
                        totals[stat] = []
                    if isinstance(val, list):
                        totals[stat].extend(val)
                elif isinstance(val, list):
                    # Other per-player game arrays (e.g. Shot_Result_List) are
                    # per-player only — not aggregated into team totals.
                    continue
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
