import random
from BackEnd.db import teams_collection
from BackEnd.utils.roster_loader import load_roster
from BackEnd.models.player import Player
from BackEnd.constants import PLAYCALLS

class TeamManager:
    def __init__(self, name: str, is_home_team=False, strategy_settings=None, team_attributes=None, scouting_data=None, plays_data=None, mode="single"):
        self.name = name
        self.is_home_team = is_home_team
        self.players = self._load_roster()
        self.lineup = self._load_lineup()
        
        # Load BASE team data from universal teams collection (name, team_id, colors, mascot)
        team_doc = teams_collection.find_one({"name": name})
        if not team_doc:
            print(f"⚠️ No team document found for team: {name}")
        self.team_id = team_doc.get("team_id") if team_doc else None
        self.primary_color = team_doc.get("primary_color", "#000000") if team_doc else "#000000"
        self.secondary_color = team_doc.get("secondary_color", "#ffffff") if team_doc else "#ffffff"
        self.mascot = team_doc.get("mascot", "") if team_doc else ""

        self.points = 0
        self.points_by_quarter = [0, 0, 0, 0]
        self.team_fouls = 0
        self.timeouts = 5  # Each team starts with 5 timeouts per game
        self.stats = {}
        self.team_stats = {}  # Team-level stats (release/get back tracking, fast break defender counts)
        
        # Use provided scouting_data or initialize fresh
        if scouting_data:
            self.scouting_data = scouting_data
        else:
            self.scouting_data = self._init_scouting_data()

        # Use provided strategy_settings or fall back to random initialization
        # MALLEABLE: Generated per game instance (not loaded from universal teams collection)
        if strategy_settings:
            self.strategy_settings = strategy_settings
        else:
            self.strategy_settings = self._init_strategy_settings()
        
        self.strategy_calls = {}
        self.playcall_tracker = {pc: 0 for pc in PLAYCALLS}
        self.defense_playcall_tracker = {"Man": 0, "Zone": 0}
        
        # Use provided plays_data (from saved game) or initialize fresh from universal collection
        # MALLEABLE: Each game instance has its own copy with tracking stats
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
        
        # Use provided team_attributes or generate random values
        # MALLEABLE: Generated per game instance (not loaded from universal teams collection)
        if team_attributes:
            self.team_attributes = team_attributes
        else:
            self.team_attributes = self._init_team_attributes()

    def _load_roster(self):
        _, players = load_roster(self.name)
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

    def _init_strategy_settings(self):
        """
        Initialize strategy settings with randomization for CPU teams (0-4 scale).
        If team document has strategy_settings, those will be used instead via constructor.
        
        Randomization:
        - inside, attack, outside: 1-4 (never zero)
        - all others: 0-4
        """
        return {
            "offense": random.randint(0, 4),
            "inside": random.randint(1, 4),
            "attack": random.randint(1, 4),
            "outside": random.randint(1, 4),
            "tempo": random.randint(0, 4),
            "play_calling": random.randint(0, 4),
            "defense": random.randint(0, 4),
            "aggression": random.randint(0, 4),
            "hc_trap": random.randint(0, 4),
            "fc_press": random.randint(0, 4),
            "rebounding": random.randint(0, 4)
        }

    def _init_team_attributes(self):
        return {
            "shot_threshold": random.randint(-50, 50),
            "ft_shot_threshold": random.randint(100, 200),
            "turnover_threshold": random.randint(-250, -150),
            "foul_threshold": random.randint(40, 90),
            "rebound_modifier": random.choice([0.8, 0.9, 1.0, 1.1, 1.2]),
            "momentum_score": random.randint(0,20),
            "momentum_delta": random.choice([1,2,3,4,5]),
            "offensive_efficiency": random.randint(1,10),
            "offensive_adjust": random.randint(1,10),
            "o_tendency_reads": random.randint(1,10),
            "d_tendency_reads": random.randint(1,10),
            "team_chemistry": random.randint(7,25)
        }

    def _init_scouting_data(self):
        # Get actual play names from database
        play_names = []
        try:
            from BackEnd.db import plays_collection
            plays = list(plays_collection.find({}, {"name": 1}))
            play_names = [play["name"] for play in plays]
        except Exception as e:
            print(f"⚠️ Could not load play names for scouting data: {e}")
            play_names = PLAYCALLS  # Fallback to constants
        
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
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                        "inside": {
                            "attempts": 0, 
                            "success": 0,
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                        "attack": {
                            "attempts": 0, 
                            "success": 0,
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                        "outside": {
                            "attempts": 0, 
                            "success": 0,
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                    },
                    "Set": {
                        "overall": {
                            "attempts": 0, 
                            "success": 0,
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                        "inside": {
                            "attempts": 0, 
                            "success": 0,
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                        "attack": {
                            "attempts": 0, 
                            "success": 0,
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                        "outside": {
                            "attempts": 0, 
                            "success": 0,
                            "vs_man": {"attempts": 0, "success": 0},
                            "vs_zone": {"attempts": 0, "success": 0},
                            "vs_2-3_zone": {"attempts": 0, "success": 0},
                            "vs_3-2_zone": {"attempts": 0, "success": 0},
                            "vs_1-3-1_zone": {"attempts": 0, "success": 0}
                        },
                    },
                    "Cumulative": {
                        "inside": {"attempts": 0, "success": 0},
                        "attack": {"attempts": 0, "success": 0},
                        "outside": {"attempts": 0, "success": 0},
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
                "Man": {
                    "used": 0, 
                    "success": 0, 
                    "effectiveness": 0.0,
                    "game_stats": {
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
                },
                "2-3 Zone": {
                    "used": 0, 
                    "success": 0, 
                    "effectiveness": 0.0,
                    "game_stats": {
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
                },
                "3-2 Zone": {
                    "used": 0, 
                    "success": 0, 
                    "effectiveness": 0.0,
                    "game_stats": {
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
                },
                "1-3-1 Zone": {
                    "used": 0, 
                    "success": 0, 
                    "effectiveness": 0.0,
                    "game_stats": {
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
                },
                "vs_Fast_Break": {"used": 0, "success": 0},
                "FCP": {"used": 0, "success": 0},
                "HCT": {"used": 0, "success": 0}
            }
        }
    
    def _init_plays_from_universal(self, mode="single"):
        """
        Initialize plays with REFERENCES to universal plays collection (not full skeletons).
        Creates team-specific copy with tracking stats based on mode.
        
        Args:
            mode: "single", "tournament", or "franchise"
            
        Returns:
            dict: {play_name: play_data} with play_id reference and stats (NO skeletons)
        """
        from BackEnd.db import plays_collection
        
        plays_dict = {}
        universal_plays = list(plays_collection.find({}))
        
        for play in universal_plays:
            # Initialize with random effectiveness score (-10 to 10)
            # In future, this will be determined by team training and in-game performance
            initial_effectiveness = round(random.uniform(-10, 10), 1)
            
            play_data = {
                "play_id": str(play["_id"]),  # Reference to universal play (the "library card")
                "name": play["name"],
                "play_type": play["play_type"], 
                "play_focus": play["play_focus"],
                # NO SKELETONS - fetched from universal collection when needed
                "game_stats": {
                    "times_run": 0,
                    "shot_attempts": 0,
                    "made_shots": 0,
                    "turnovers": 0,
                    "offensive_fouls": 0,
                    "defensive_fouls": 0,
                    "effectiveness": initial_effectiveness
                }
            }
            
            # Add season_stats for tournament and franchise modes
            if mode in ["tournament", "franchise"]:
                play_data["season_stats"] = {
                    "times_run": 0,
                    "shot_attempts": 0,
                    "made_shots": 0,
                    "turnovers": 0,
                    "offensive_fouls": 0,
                    "defensive_fouls": 0,
                    "effectiveness": initial_effectiveness  # Same initial value
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
                totals[stat] = totals.get(stat, 0) + val
        self.stats = totals

    def reset_for_new_game(self):
        self.points_by_quarter = [0, 0, 0, 0]
        self.team_fouls = 0
        self.timeouts = 5  # Reset to 5 timeouts for new game (timeouts carry over whole game, not reset per quarter)
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
            "DEF_A": 0,  # Defensive Attempts
            "DEF_S": 0,  # Defensive Stops
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

