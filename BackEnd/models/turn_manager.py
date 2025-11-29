from BackEnd.models.logger import Logger
from BackEnd.models.rebound_manager import ReboundManager
from BackEnd.models.playbook_manager import PlaybookManager
from BackEnd.models.animator import Animator
import random
import json
import logging
from BackEnd.db import players_collection, teams_collection, plays_collection
from BackEnd.models.player import Player, player_to_dict
from collections import defaultdict
from BackEnd.playcall_skeletons.inside_skeletons import INSIDE_SCENES
from BackEnd.constants import ACTIONS
from BackEnd.constants import (
    PLAYCALL_ATTRIBUTE_WEIGHTS,
    POSITION_LIST,
    STRATEGY_CALL_DICTS,
    TEMPO_PASS_DICT,
    MALLEABLE_ATTRS
)
from BackEnd.utils.shared import (
    weighted_random_from_dict,
    generate_pass_chain,
    get_team_thresholds,
    get_foul_and_turnover_positions,
    get_name_safe,
    get_player_position,
    update_player_coords_from_animations,
    serialize_lineup,
    getAwayTeamCoords
)
from BackEnd.utils.shared_defense import (
    get_defender_coords
)
from BackEnd.engine.phase_resolution import (
    resolve_fast_break_logic, 
    resolve_free_throw_logic, 
    resolve_turnover_logic, 
    calculate_foul_turnover,
    resolve_full_court_press_logic,
    resolve_half_court_trap_logic
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from BackEnd.models.game_manager import GameManager

class TurnManager:
    def __init__(self, game_manager: "GameManager"):
        self.game = game_manager
        self.logger = Logger()
        self.rebound_manager = ReboundManager(self.game)
        self.playbook_manager = PlaybookManager(self.game.offense_team)
        self.animator = Animator(self.game)
        self._ensure_lineup_fields()

    def _ensure_lineup_fields(self):
        for team in [self.game.home_team, self.game.away_team]:
            for player in team.lineup.values():
                if not hasattr(player, "player_id"):
                    setattr(player, "player_id", str(id(player)))
                if not hasattr(player, "coords"):
                    setattr(player, "coords", {"x": 25, "y": 50})

    def setup_side_inbound(self):
        """
        Prepare coordinates for a sideline inbound following a dead-ball
        turnover or a non-shooting foul with no free throws.

        Returns a payload describing offensive and defensive destination
        coordinates which the front-end can use to animate the inbound
        sequence.
        """

        game = self.game
        offense_team = game.offense_team
        defense_team = game.defense_team
        aggression = defense_team.strategy_calls.get("aggression_call", "normal")
        is_away_offense = offense_team.team_id == game.away_team.team_id

        self.logger.log("sideInbound:start")

        # Sideline spot for the inbounder (SF). These coordinates assume the
        # home team is on offense. They will be mirrored if the away team has
        # the ball. Y=51 is out of bounds at the top of the court.
        inbound_spot_home = {"x": 47, "y": 48}

        # Destination ranges for other offensive players (home orientation).
        home_ranges = {
            "PG": {"x": (50, 54), "y": (37, 43)},
            "SG": {"x": (55, 64), "y": (18, 32)},
            "PF": {"x": (65, 80), "y": (26, 36)},
            "C":  {"x": (65, 80), "y": (14, 24)},
        }

        o_dest_home = {}
        for pos, ranges in home_ranges.items():
            o_dest_home[pos] = {
                "x": random.randint(*ranges["x"]),
                "y": random.randint(*ranges["y"]),
            }
            self.logger.log(f"destAssigned:{pos}")

        # Inbounder (SF) stays at the inbound spot
        o_dest_home["SF"] = inbound_spot_home.copy()

        # Flip offensive coordinates if the away team has possession
        o_dest = getAwayTeamCoords(o_dest_home.copy()) if is_away_offense else o_dest_home

        # Determine ball-handler (PG) coordinates in actual orientation
        bh_coords = o_dest["PG"]

        # --- Defensive positioning ---
        # Fixed positions for home team defense (when home is defending)
        self.logger.log("defenseUpdate:start")
        d_dest_home = {
            "PG": {"x": 60, "y": 25},
            "SG": {"x": 64, "y": 33},
            "SF": {"x": 66, "y": 17},
            "PF": {"x": 80, "y": 25},
            "C": {"x": 85, "y": 28}
        }
        
        # Flip defensive coordinates if away team is defending (home team has ball)
        d_dest = getAwayTeamCoords(d_dest_home.copy()) if is_away_offense else d_dest_home
        self.logger.log("defenseUpdate:end")

        payload = {
            "result_type": "SIDE_INBOUND",
            "ball_spot": getAwayTeamCoords({"tmp": inbound_spot_home})["tmp"] if is_away_offense else inbound_spot_home,
            "oDestinations": o_dest,
            "dDestinations": d_dest,
            "possession_team_id": offense_team.team_id,
            "quarter": self.game.quarter,
        }

        return payload

    def setup_baseline_inbound(self, next_defensive_setup=None):
        """
        Prepare coordinates for a baseline inbound following a made shot.
        The opposing team gets the ball and starts their possession from the baseline.

        Args:
            next_defensive_setup: Optional defensive pressure type ("FCP" or "HCT") 
                                  that will be applied after the inbound pass.

        Returns a payload describing offensive and defensive destination
        coordinates which the front-end can use to animate the inbound
        sequence.
        """

        game = self.game
        offense_team = game.offense_team
        defense_team = game.defense_team
        aggression = defense_team.strategy_calls.get("aggression_call", "normal")
        is_away_offense = offense_team.team_id == game.away_team.team_id

        self.logger.log("baselineInbound:start")

        # Baseline spot for the inbounder (PG). These coordinates assume the
        # home team is on offense. They will be mirrored if the away team has
        # the ball.
        inbound_spot_home = {"x": 50, "y": 25}  # Center baseline

        # Destination ranges for other offensive players (home orientation).
        home_ranges = {
            "SG": {"x": (52, 56), "y": (22, 28)},
            "SF": {"x": (54, 58), "y": (18, 32)},
            "PF": {"x": (54, 58), "y": (30, 36)},
            "C":  {"x": (54, 58), "y": (14, 20)},
        }

        o_dest_home = {}
        for pos, ranges in home_ranges.items():
            o_dest_home[pos] = {
                "x": random.randint(*ranges["x"]),
                "y": random.randint(*ranges["y"]),
            }
            self.logger.log(f"destAssigned:{pos}")

        # Inbounder (PG) stays at the inbound spot
        o_dest_home["PG"] = inbound_spot_home.copy()

        # Flip offensive coordinates if the away team has possession
        o_dest = getAwayTeamCoords(o_dest_home.copy()) if is_away_offense else o_dest_home

        # Determine ball-handler (PG) coordinates in actual orientation
        bh_coords = o_dest["PG"]

        # --- Defensive positioning ---
        # PHASE 6: Use new unified defender coordinate system
        # get_defender_coords handles coordinate orientation automatically
        self.logger.log("defenseUpdate:start")
        d_dest = {}
        for pos, defender in defense_team.lineup.items():
            if pos == "PG":
                # BH defender - get_defender_coords handles orientation automatically
                d_coords = get_defender_coords(
                    bh_coords,
                    is_away_offense,
                    aggression,
                    "baseline_inbound",
                    None,
                    is_ball_handler=True
                )
                d_dest[pos] = d_coords
            elif pos in o_dest:
                o_coords = o_dest[pos]
                # Non-BH defender - get_defender_coords handles orientation automatically
                # Need to determine offensive player's spot (default to "key" for baseline inbound)
                o_spot = "key"  # Default spot for baseline inbound
                d_coords = get_defender_coords(
                    o_coords,
                    is_away_offense,
                    aggression,
                    o_spot,
                    bh_coords,
                    is_ball_handler=False,
                    ball_spot="baseline_inbound"  # Ball handler's spot
                )
                d_dest[pos] = d_coords
        self.logger.log("defenseUpdate:end")

        payload = {
            "result_type": "BASELINE_INBOUND",
            "ball_spot": getAwayTeamCoords({"tmp": inbound_spot_home})["tmp"] if is_away_offense else inbound_spot_home,
            "oDestinations": o_dest,
            "dDestinations": d_dest,
            "possession_team_id": offense_team.team_id,
            "quarter": self.game.quarter,
        }
        
        # Include next_defensive_setup if provided (for FCP/HCT pressure)
        if next_defensive_setup:
            payload["next_defensive_setup"] = next_defensive_setup

        return payload

    def run_micro_turn(self):
        # Increment micro turn counter
        self.game.micro_turn_count += 1

        def convert_players(obj):
            """Recursively replace Player objects with serializable dicts."""
            if isinstance(obj, Player):
                return player_to_dict(obj)
            if isinstance(obj, list):
                return [convert_players(x) for x in obj]
            if isinstance(obj, dict):
                return {k: convert_players(v) for k, v in obj.items()}
            return obj

        # Snapshot player stats to compute deltas after the turn
        pre_stats = {}
        for team in (self.game.home_team, self.game.away_team):
            for player in team.get_all_players():
                pre_stats[player.player_id] = player.stats["game"].copy()

        # STEP 1: Set strategy calls (tempo + aggression)
        self.set_strategy_calls()

        # ✅ DEBUG: Log offensive_state transition (previous turn → current turn)
        # This is the critical transition point where offensive_state determines routing
        state = self.game.game_state.get("offensive_state", "HCO")
        turn_num = self.game.micro_turn_count
        from BackEnd.constants import DEBUG
        time_remaining = self.game.game_state.get("clock", "N/A")
        
        # Get previous turn's offensive_state (if available from game_state history)
        # Note: We can't easily get previous turn's state here, but we log what we have
        import logging
        logging.info(f"🔄 [OFFENSIVE_STATE TRANSITION] Turn #{turn_num}", {
            "turn_number": turn_num,
            "current_offensive_state": state,
            "time_remaining": time_remaining,
            "offense_team": self.game.offense_team.name,
            "defense_team": self.game.defense_team.name,
            "note": "This is the offensive_state that determines routing for this turn"
        })
        
        # Create debug string for frontend display
        debug_turn_start = f"***** RUN TURN, turn number: {turn_num}, time remaining: {time_remaining}, offensive state: {state} *****"
        # if state in ["HCO", "HALF_COURT"]:
        #     print(f"{self.game.offense_team.name}: {self.game.game_state['current_playcall']}")
        #     print(f"{self.game.defense_team.name}: {self.game.game_state['defense_playcall']}")

        # STEP 3: Route based on offensive state
        if state == "FREE_THROW":
            result = self.resolve_free_throw()
        elif state == "FAST_BREAK":
            self.logger.log("fb:start")
            self.game.game_state["fastBreakInProgress"] = True
            result = resolve_fast_break_logic(self.game)
        elif state == "FCP":
            self.logger.log("fcp:start")
            result = resolve_full_court_press_logic(self.game)
        elif state == "HCT":
            self.logger.log("hct:start")
            result = resolve_half_court_trap_logic(self.game)
        else:
            calls = self.set_playcalls()
            self.game.game_state["current_playcall"] = calls["offense"]
            self.game.game_state["defense_playcall"] = calls["defense"]
            
            # Track defensive playcall usage
            from BackEnd.utils.defense_utils import map_defense_playcall_to_tracking_name
            def_team = self.game.defense_team
            defense_playcall = calls["defense"]  # "Man", "2-3 Zone", "3-2 Zone", etc.
            # Defense playcall is now stored as specific name (e.g., "2-3 Zone")
            tracking_name = defense_playcall  # Use specific name directly
            if tracking_name in def_team.scouting_data["defense"]:
                # Get offensive play type and focus for granular tracking
                offense_play_type = calls.get("offense_type", "").lower()  # "motion" or "set_play"
                offense_focus = calls.get("offense_focus", "")  # "inside", "attack", "outside"
                
                # Normalize play type (set_play -> set) to match phase_resolution.py
                if offense_play_type == "set_play":
                    offense_play_type = "set"
                
                def_team.scouting_data["defense"][tracking_name]["used"] += 1
                def_team.scouting_data["defense"][tracking_name]["game_stats"]["used"] += 1
                
                # Track granular usage by play type
                if offense_play_type == "motion":
                    def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_motion"]["attempts"] += 1
                elif offense_play_type == "set":
                    def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_set"]["attempts"] += 1
                
                # Track granular usage by focus type
                if offense_focus in ["inside", "attack", "outside"]:
                    def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_{offense_focus}"]["attempts"] += 1
                    
                    # Track combination of play type + focus
                    if offense_play_type == "motion":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_motion_{offense_focus}"]["attempts"] += 1
                    elif offense_play_type == "set":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_set_{offense_focus}"]["attempts"] += 1
            
            # Calculate EV (Expected Value) for the playcall matchup
            ev = self.calculate_ev(
                offensive_playcall=calls["offense"],
                defensive_playcall=calls["defense"],
                offensive_lineup=self.game.offense_team.lineup,
                defensive_lineup=self.game.defense_team.lineup,
                offensive_team=self.game.offense_team,
                defensive_team=self.game.defense_team
            )
            
            # Store EV score in scouting data
            self._store_ev_score(ev, calls, self.game.offense_team, self.game.defense_team)
            
            result = self.resolve_half_court_offense()
            # Add playcalls to result for frontend display
            result["offensive_playcall"] = calls["offense"]
            result["defensive_playcall"] = calls["defense"]
            
            # Add play type and focus for frontend display
            result["offensive_play_type"] = calls.get("offense_type", "-")
            result["offensive_play_focus"] = calls.get("offense_focus", None)
            result["defensive_play_type"] = calls.get("defense_type", "-")
            result["defensive_play_focus"] = calls.get("defense_focus", None)
            
            # Add EV to result for frontend display
            result["ev"] = ev

        # Record possession team before any potential flip
        result["starting_possession_team_id"] = self.game.offense_team.team_id

        # STEP 4: Final updates (clock, logs, animation)
        try:
            self.update_clock_and_possession(result)
            self.logger.log_turn_result(result)
            
            # ✅ DEBUG: Log offensive_state after handler execution (current turn → next turn)
            # This shows what offensive_state will be for the NEXT turn
            final_state = self.game.game_state.get("offensive_state", "HCO")
            next_play_type = result.get("next_play_type", "None")
            result_type = result.get("result_type", "N/A")
            import logging
            logging.info(f"🔄 [OFFENSIVE_STATE TRANSITION] Turn #{turn_num} Complete", {
                "turn_number": turn_num,
                "result_type": result_type,
                "previous_offensive_state": state,  # State at start of this turn
                "next_offensive_state": final_state,  # State for next turn (set by handler)
                "next_play_type": next_play_type,  # Informational only
                "offense_team": self.game.offense_team.name,
                "defense_team": self.game.defense_team.name,
                "state_changed": state != final_state,
                "note": "next_offensive_state is what will be used to route the NEXT turn"
            })
            
            # ✅ REMOVED: Overwrite logic that was causing transition bugs
            # 
            # Rationale: Handlers (shot_manager, phase_resolution, etc.) are the source of truth for offensive_state.
            # They explicitly set offensive_state when needed (e.g., "FREE_THROW" for AND-1, "FAST_BREAK" for steals).
            # 
            # next_play_type is informational only (for frontend display/logging), not for routing.
            # If a handler doesn't set offensive_state, that's a bug in the handler, not something we should patch here.
            # 
            # This restores the previous transition system behavior where handlers control state transitions.
            # 
            # Examples of handlers setting offensive_state:
            # - shot_manager.py line 351: Sets "FREE_THROW" for AND-1
            # - shot_manager.py line 372: Sets pressure_type for made shots
            # - shot_manager.py line 405: Sets "FREE_THROW" for missed shots with fouls
            # - phase_resolution.py line 585: Sets pressure_type after free throw
            # - phase_resolution.py line 698: Sets "FAST_BREAK" for steals
            # - phase_resolution.py line 714: Sets "HCO" for dead ball turnovers
                
        finally:
            if state == "FAST_BREAK":
                self.logger.log("fb:end")
                self.game.game_state["fastBreakInProgress"] = False
        # If animations weren’t assigned yet (e.g. fast break, free throw), use fallback
        if "animations" not in result:
            roles = result.get("roles")
            if roles:
                from BackEnd.models.animator import Animator
                animator = Animator(self.game)
                result["animations"] = animator.capture_halfcourt_animation(
                    roles=roles,
                    event_step=result.get("event_step")
                )
            else:
                result["animations"] = []  # No animation possible (e.g., free throw or turnover with no roles)
        result["possession_team_id"] = self.game.offense_team.team_id

        if "roles" in result:
            result["roles"] = convert_players(result["roles"])

        for key in [
            "ball_handler",
            "shooter",
            "passer",
            "screener",
            "defender",
            "stealer_name",
            "victim_name",
        ]:
            if key in result:
                result[key] = get_name_safe(result[key])
        for key in [
            "ball_handler",
            "shooter",
            "shooter_id",
            "screener",
            "passer",
            "defender",
            "stealer_name",
            "victim_name",
            "stealer_id",
            "victim_id",
        ]:
            if key in result:
                val = result[key]
                if hasattr(val, "name"):
                    result[key] = val.name
                elif hasattr(val, "player_id"):  # fallback to player_id
                    result[key] = val.player_id
                else:
                    result[key] = str(val)  # final fallback (safe for non-class data)

        result["turn_count"] = self.game.micro_turn_count
        # result["possession_team_id"] = self.game.offense_team.team_id
        update_player_coords_from_animations(self.game, result["animations"])
        
        # Print turn result summary for debugging
        turn_num = self.game.micro_turn_count
        result_type = result.get("result_type", "N/A")
        next_play_type = result.get("next_play_type", "None")
        next_defensive_setup = result.get("next_defensive_setup", "None")
        text = result.get("text", "")
        possession_flips = result.get("possession_flips", False)
        from BackEnd.constants import DEBUG
        
        # Create debug string for frontend display
        debug_turn_result = f"Turn {turn_num} RESULT: {result_type} | Next: {next_play_type} | Defense Setup: {next_defensive_setup} | Possession Flips: {possession_flips}"
        
        if DEBUG:
            print(debug_turn_result)
        
        # Add debug info to result for frontend display
        result["debug_turn_start"] = debug_turn_start
        result["debug_turn_result"] = debug_turn_result
        
        # self._print_turn_summary(result, state)

        result["home_lineup"] = serialize_lineup(self.game.home_team.lineup)
        result["away_lineup"] = serialize_lineup(self.game.away_team.lineup)

        result["score"] = dict(self.game.score)

        # Include current team stats for frontend updates (from scouting_data)
        result["team_stats"] = {
            self.game.home_team.name: {
                "offense": self.game.home_team.scouting_data.get("offense", {}),
                "defense": self.game.home_team.scouting_data.get("defense", {})
            },
            self.game.away_team.name: {
                "offense": self.game.away_team.scouting_data.get("offense", {}),
                "defense": self.game.away_team.scouting_data.get("defense", {})
            }
        }
        
        # Include cumulative team stats (from all players) for S1 tab
        # Update team stats before sending
        self.game.update_team_stats()
        result["team_totals"] = {
            self.game.home_team.name: self.game.home_team.get_team_game_stats(),
            self.game.away_team.name: self.game.away_team.get_team_game_stats()
        }
        
        # Include play data for tooltips (effectiveness and tracking)
        result["team_plays"] = {
            self.game.home_team.name: list(self.game.home_team.plays.values()),
            self.game.away_team.name: list(self.game.away_team.plays.values())
        }

        # Compute stat deltas for each player
        # Exclude REB from deltas since it's automatically calculated from OREB + DREB
        # The frontend will calculate REB from OREB + DREB to avoid double-counting
        deltas = {}
        for team in (self.game.home_team, self.game.away_team):
            for player in team.get_all_players():
                prev = pre_stats.get(player.player_id, {})
                diff = {
                    stat: player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                    for stat in player.stats["game"]
                    if stat != "REB" and player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                }
                if diff:
                    deltas[player.player_id] = {"team": team.name, "stats": diff}
                    
                    # ✅ Debug logging for assists on made shots
                    if "AST" in diff and result.get("result_type") in ["MAKE", "MISS"]:
                        logging.info(f"🎯 ASSIST DELTA: {get_name_safe(player)} has AST in deltas: {diff}, result_type={result.get('result_type')}")
                    
                    # ✅ Debug logging for free throw rebounds
                    if result.get("result_type") == "FREE_THROW" and ("OREB" in diff or "DREB" in diff):
                        logging.info(f"🏀 Free Throw Turn Deltas: {get_name_safe(player)} has rebound in deltas: {diff}")
        
        # ✅ Additional debug logging for FREE_THROW turns to check if rebound stats were recorded
        if result.get("result_type") == "FREE_THROW" and result.get("rebound_type"):
            rebounder_id = result.get("rebounderId")
            logging.info(f"🏀 Free Throw Turn - rebound_type={result.get('rebound_type')}, rebounderId={rebounder_id}")
            if rebounder_id:
                # Check if rebounder exists in deltas
                if rebounder_id in deltas:
                    logging.info(f"🏀 Free Throw Turn - Rebounder {rebounder_id} found in deltas: {deltas[rebounder_id]}")
                else:
                    logging.warning(f"⚠️ Free Throw Turn - Rebounder {rebounder_id} NOT found in deltas. Available player_ids: {list(deltas.keys())}")
                    # Check if rebounder exists in pre_stats (might be from previous turn)
                    if rebounder_id in pre_stats:
                        prev_reb = pre_stats[rebounder_id].get(result.get("rebound_type"), 0)
                        # Find the player object to check current stats
                        for team in (self.game.home_team, self.game.away_team):
                            for player in team.get_all_players():
                                if player.player_id == rebounder_id:
                                    current_reb = player.stats["game"].get(result.get("rebound_type"), 0)
                                    logging.warning(f"⚠️ Free Throw Turn - Rebounder stats mismatch: prev={prev_reb}, current={current_reb}, should_diff={current_reb - prev_reb}, player_name={get_name_safe(player)}")
                                    # If there's a diff but it's not in deltas, this is a bug
                                    if current_reb != prev_reb:
                                        expected_diff = {result.get("rebound_type"): current_reb - prev_reb}
                                        logging.error(f"❌ Free Throw Turn - Rebound stat recorded but NOT in deltas! Expected: {expected_diff}, Player: {get_name_safe(player)}")
                                    break
                    else:
                        logging.warning(f"⚠️ Free Throw Turn - Rebounder {rebounder_id} not found in pre_stats")
        
        result["deltas"] = deltas
        
        # ✅ Debug logging for assists - check if AST is in deltas after a made shot
        if result.get("result_type") == "MAKE":
            # Check if any player has AST in deltas
            has_ast_in_deltas = any("AST" in delta.get("stats", {}) for delta in deltas.values())
            if has_ast_in_deltas:
                ast_players = []
                for pid, delta in deltas.items():
                    if "AST" in delta.get("stats", {}):
                        for team in (self.game.home_team, self.game.away_team):
                            player = team.get_player_by_id(pid)
                            if player:
                                ast_players.append(get_name_safe(player))
                                break
                logging.info(f"🎯 ASSIST CHECK: Made shot - AST found in deltas for: {', '.join(ast_players) if ast_players else 'unknown'}")
            else:
                delta_summary = {pid: list(d.get("stats", {}).keys()) for pid, d in deltas.items()}
                logging.warning(f"⚠️ ASSIST CHECK: Made shot - NO AST found in deltas! Deltas: {delta_summary}")
        
        # ✅ Debug logging for free throw rebound deltas
        if result.get("result_type") == "FREE_THROW" and result.get("rebound_type"):
            rebounder_id = result.get("rebounderId")
            if rebounder_id and rebounder_id in deltas:
                rebounder_deltas = deltas[rebounder_id].get("stats", {})
                logging.info(f"🏀 Free Throw Turn Result: rebound_type={result.get('rebound_type')}, rebounderId={rebounder_id}, deltas={rebounder_deltas}")
            else:
                logging.warn(f"⚠️ Free Throw Rebound Missing in Deltas: rebound_type={result.get('rebound_type')}, rebounderId={rebounder_id}, deltas_keys={list(deltas.keys())}")
        
        # Include current energy levels for all active players (for frontend fatigue display)
        player_energy = {}
        for team in (self.game.home_team, self.game.away_team):
            for pos, player in team.lineup.items():
                if player is None:
                    continue  # Skip None players in lineup
                player_energy[player.player_id] = {
                    "NG": player.attributes.get("NG", 1.0),
                    "team": team.name
                }
        result["player_energy"] = player_energy
        
        # Include strategy calls for frontend strategy bars (actual calls, not settings)
        result["offense_tempo_call"] = self.game.offense_team.strategy_calls.get("tempo_call", "normal")
        result["offense_aggression_call"] = self.game.offense_team.strategy_calls.get("aggression_call", "normal")
        result["defense_tempo_call"] = self.game.defense_team.strategy_calls.get("tempo_call", "normal")
        result["defense_aggression_call"] = self.game.defense_team.strategy_calls.get("aggression_call", "normal")
        
        from BackEnd.constants import DEBUG
        if DEBUG:
            print(f"📤 TURN RESULT - Sending to frontend: offense_tempo={result['offense_tempo_call']}, offense_aggr={result['offense_aggression_call']}, defense_tempo={result['defense_tempo_call']}, defense_aggr={result['defense_aggression_call']}")

        # Reconcile player point totals with the authoritative team score.
        # Clients should treat ``turn.score`` and ``turn.deltas`` as canonical
        # and never re-apply ``turn.points`` to avoid double counting. To guard
        # against any desync, compare the team score against the sum of player
        # PTS at the end of a possession or quarter and push a corrective delta
        # if they differ.
        self._reconcile_player_points(result)

        # Sync and expose fouls/clock/quarter for live scoreboard updates
        self.game.game_state["team_fouls"] = {
            self.game.home_team.name: self.game.home_team.team_fouls,
            self.game.away_team.name: self.game.away_team.team_fouls,
        }
        result["homeFouls"] = self.game.home_team.team_fouls
        result["awayFouls"] = self.game.away_team.team_fouls
        
        result["clock"] = self.game.game_state["clock"]
        result["quarter"] = self.game.game_state["quarter"]
        result["period_label"] = self.game.game_state.get("period_label")
        # Ensure no Player objects remain in the result payload
        result = convert_players(result)

        # Ensure every turn has text for the in-game text scroll
        if not result.get("text") or result.get("text").strip() == "":
            result["text"] = "No text in this turn"

        # print(f"inside run_micro_turn result: {result}")
        
        return result


    def set_playcalls(self):
        """
        Two-level play selection system:
        Level 1: Determine motion vs set play based on offense setting
        Level 2: Determine play focus (inside/attack/outside) based on weighted settings
        
        User overrides take precedence for turn-by-turn gameplay.
        """
        
        # Check for user overrides FIRST (for turn-by-turn gameplay)
        user_offense = self.game.game_state.get("user_offense_override")
        user_defense = self.game.game_state.get("user_defense_override")
        
        # If user provided an offense override, use the specific play name
        if user_offense:
            self.game.game_state["user_offense_override"] = None  # Clear after use
            
            # User now provides specific play name (e.g., "3-2 Motion", "Base Post Play")
            chosen_playcall = user_offense
            logging.info(f"🎮 User offense override (play): {chosen_playcall}")
            
            # Lookup play details from database to get play_type and play_focus
            play_doc = plays_collection.find_one({"name": chosen_playcall})
            
            if play_doc:
                chosen_play_type = play_doc.get("play_type", "motion")
                user_focus = play_doc.get("play_focus", "inside")
                logging.info(f"🎯 User override play details: {chosen_playcall} (type={chosen_play_type}, focus={user_focus})")
            else:
                # Fallback if play not found
                logging.warning(f"⚠️ Play '{chosen_playcall}' not found in database, using fallback")
                chosen_play_type = "motion"
                user_focus = "inside"
            
            # Still need to choose defense normally
            if user_defense:
                chosen_defense = user_defense
                self.game.game_state["user_defense_override"] = None  # Clear after use
                logging.info(f"🎮 Using user defense override: {chosen_defense}")
            else:
                defense_setting = self.game.defense_team.strategy_settings.get("defense", 2)
                chosen_defense = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])
                
                # If "Zone" is selected, randomly choose between 2-3 Zone, 3-2 Zone, and 1-3-1 Zone (1/3 each)
                if chosen_defense == "Zone":
                    chosen_defense = random.choice(["2-3 Zone", "3-2 Zone", "1-3-1 Zone"])
            
            # Return early with user's choices
            return {
                "offense": chosen_playcall,
                "defense": chosen_defense,
                "offense_type": "User",  # Mark as user-selected
                "offense_play_type": chosen_play_type,  # Include play type for Playcall Center highlighting
                "offense_focus": user_focus,
                "defense_type": chosen_defense.title() if chosen_defense else "-",
                "defense_focus": None
            }
        
        # If only defense override (user on offense, setting defense for next possession)
        if user_defense:
            chosen_defense = user_defense
            self.game.game_state["user_defense_override"] = None  # Clear after use
            logging.info(f"🎮 Using user defense override: {chosen_defense}")
        else:
            # No override, choose defense normally (will be set below)
            chosen_defense = None
        
        # Level 1: Determine play type (motion vs set_play)
        offense_setting = self.game.offense_team.strategy_settings.get("offense", 2)
        
        play_type_weights = {
            0: {"motion": 100, "set_play": 0},
            1: {"motion": 75, "set_play": 25},
            2: {"motion": 50, "set_play": 50},
            3: {"motion": 25, "set_play": 75},
            4: {"motion": 0, "set_play": 100}
        }
        
        weights = play_type_weights.get(offense_setting, {"motion": 50, "set_play": 50})
        chosen_play_type = weighted_random_from_dict(weights)
        
        # Level 2: Determine play focus (inside/attack/outside)
        inside_val = self.game.offense_team.strategy_settings.get("inside", 2)
        attack_val = self.game.offense_team.strategy_settings.get("attack", 2)
        outside_val = self.game.offense_team.strategy_settings.get("outside", 2)
        
        total = inside_val + attack_val + outside_val
        
        if total == 0:
            # Fallback if all are zero (shouldn't happen but safe)
            chosen_focus = "inside"
        else:
            # Roll random number from 1 to total
            roll = random.randint(1, total)
            
            if roll <= inside_val:
                chosen_focus = "inside"
            elif roll <= inside_val + attack_val:
                chosen_focus = "attack"
            else:
                chosen_focus = "outside"
        
        # Query plays collection for matching play
        query = {
            "play_type": chosen_play_type,
            "play_focus": chosen_focus
        }
        
        matching_plays = list(plays_collection.find(query))
        
        if not matching_plays:
            # Fallback: if no plays match, log warning and use a default
            print(f"⚠️ No plays found for {chosen_play_type}/{chosen_focus}, using fallback")
            chosen_playcall = "Inside"  # Fallback to old system
        else:
            # Randomly select one play from matches
            selected_play = random.choice(matching_plays)
            chosen_playcall = selected_play["name"]
        
        # Defense setting - use override if set, otherwise choose normally
        # NOTE: This must happen BEFORE offense attempt tracking so we know the correct defense
        if chosen_defense is None:  # Not set by user override
            defense_setting = self.game.defense_team.strategy_settings.get("defense", 2)
            chosen_defense = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])
            
            # If "Zone" is selected, randomly choose between 2-3 Zone, 3-2 Zone, and 1-3-1 Zone (1/3 each)
            if chosen_defense == "Zone":
                chosen_defense = random.choice(["2-3 Zone", "3-2 Zone", "1-3-1 Zone"])
        
        # Record playcall attempt under new buckets
        try:
            # Normalize type/focus labels
            play_type_label = "Motion" if chosen_play_type == "motion" else ("Set" if chosen_play_type == "set_play" else None)
            focus_label = chosen_focus if chosen_focus in ["inside", "attack", "outside"] else None
            if play_type_label and focus_label:
                pc = self.game.offense_team.scouting_data["offense"]["Playcalls"]
                # Use chosen_defense for granular tracking (not from game_state, which isn't set yet)
                defense_playcall = chosen_defense  # Use the defense we just determined
                from BackEnd.utils.defense_utils import is_zone_defense
                
                # Determine defense tracking key based on specific defense name
                if defense_playcall == "Man":
                    vs_key = "vs_man"
                elif defense_playcall == "2-3 Zone":
                    vs_key = "vs_2-3_zone"
                elif defense_playcall == "3-2 Zone":
                    vs_key = "vs_3-2_zone"
                elif defense_playcall == "1-3-1 Zone":
                    vs_key = "vs_1-3-1_zone"
                else:
                    vs_key = None
                
                # Motion/Set overall + focus
                pc[play_type_label]["overall"]["attempts"] += 1
                pc[play_type_label][focus_label]["attempts"] += 1
                
                # Track granular attempts against defensive playcall
                if vs_key:
                    # Overall attempts vs defense
                    if vs_key in pc[play_type_label]["overall"]:
                        pc[play_type_label]["overall"][vs_key]["attempts"] += 1
                    # Focus attempts vs defense
                    if vs_key in pc[play_type_label][focus_label]:
                        pc[play_type_label][focus_label][vs_key]["attempts"] += 1
                    
                    # Track aggregate vs_zone for any zone type
                    if is_zone_defense(defense_playcall) and "vs_zone" in pc[play_type_label]["overall"]:
                        pc[play_type_label]["overall"]["vs_zone"]["attempts"] += 1
                        pc[play_type_label][focus_label]["vs_zone"]["attempts"] += 1
                
                # Cumulative by focus
                pc["Cumulative"][focus_label]["attempts"] += 1
                
                # Track last play run for this category (for tooltips)
                category_key = f"{play_type_label.lower()}_{focus_label}"
                self.game.offense_team.scouting_data["offense"]["last_play_by_category"][category_key] = chosen_playcall
        except Exception:
            pass

        # Persist play type/focus to game_state for later success attribution
        self.game.game_state["offense_play_type"] = chosen_play_type
        self.game.game_state["offense_play_focus"] = chosen_focus
        
        # Legacy trackers removed from incrementing to avoid serving old structure

        return {
            "offense": chosen_playcall,
            "defense": chosen_defense,
            "offense_type": chosen_play_type.title() if chosen_play_type else "-",
            "offense_focus": chosen_focus if chosen_focus else None,
            "defense_type": chosen_defense.title() if chosen_defense else "-",  # Man or Zone
            "defense_focus": None
        }


    def set_strategy_calls(self):
        # Ensure strategy_settings are initialized for both teams (but don't overwrite existing settings)
        # Only initialize if it's completely missing (None), not if it's an empty dict
        if not hasattr(self.game.offense_team, 'strategy_settings') or self.game.offense_team.strategy_settings is None:
            import logging
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {self.game.offense_team.name} missing strategy_settings in set_strategy_calls, initializing with defaults")
            self.game.offense_team.strategy_settings = self.game.offense_team._init_strategy_settings()
        elif isinstance(self.game.offense_team.strategy_settings, dict) and len(self.game.offense_team.strategy_settings) == 0:
            import logging
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {self.game.offense_team.name} has empty strategy_settings dict in set_strategy_calls, initializing with defaults")
            self.game.offense_team.strategy_settings = self.game.offense_team._init_strategy_settings()
        
        if not hasattr(self.game.defense_team, 'strategy_settings') or self.game.defense_team.strategy_settings is None:
            import logging
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {self.game.defense_team.name} missing strategy_settings in set_strategy_calls, initializing with defaults")
            self.game.defense_team.strategy_settings = self.game.defense_team._init_strategy_settings()
        elif isinstance(self.game.defense_team.strategy_settings, dict) and len(self.game.defense_team.strategy_settings) == 0:
            import logging
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {self.game.defense_team.name} has empty strategy_settings dict in set_strategy_calls, initializing with defaults")
            self.game.defense_team.strategy_settings = self.game.defense_team._init_strategy_settings()
        
        # 🐛 DEBUG: Log strategy settings being used
        import logging
        logging.warning(f"🔧 [SET STRATEGY CALLS] Offense: {self.game.offense_team.name}, Defense: {self.game.defense_team.name}")
        logging.warning(f"   - Offense strategy_settings: {self.game.offense_team.strategy_settings}")
        logging.warning(f"   - Defense strategy_settings: {self.game.defense_team.strategy_settings}")
        
        # Ensure strategy_calls dictionaries exist
        if not hasattr(self.game.offense_team, 'strategy_calls') or not self.game.offense_team.strategy_calls:
            self.game.offense_team.strategy_calls = {}
        if not hasattr(self.game.defense_team, 'strategy_calls') or not self.game.defense_team.strategy_calls:
            self.game.defense_team.strategy_calls = {}

        # Set tempo/aggression calls (string values for time elapsed and foul calculations)
        tempo_setting = self.game.offense_team.strategy_settings.get("tempo", 2)
        aggression_setting = self.game.defense_team.strategy_settings.get("aggression", 2)
        
        self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
        self.game.defense_team.strategy_calls["aggression_call"] = random.choice(STRATEGY_CALL_DICTS["aggression"][aggression_setting])
        
        # NOTE: rebounding and defense tempo for fast break release are now read directly 
        # from strategy_settings (numeric 0-4) in shot_manager.py - no string conversion needed
        


    
    def calculate_ev(self, offensive_playcall, defensive_playcall, offensive_lineup, defensive_lineup, offensive_team, defensive_team):
        """
        Calculate Expected Value (EV) for the playcall matchup.
        
        Args:
            offensive_playcall (str): Offensive playcall (e.g., "Motion - Inside Focus")
            defensive_playcall (str): Defensive playcall (e.g., "Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone")
            offensive_lineup (dict): Offensive lineup {pos: player}
            defensive_lineup (dict): Defensive lineup {pos: player}
            offensive_team: Offensive team object with attributes
            defensive_team: Defensive team object with attributes
        
        Returns:
            float: EV percentage from -99.0 to 99.0
                Positive: Offensive advantage
                Negative: Defensive advantage
        """
        import random
        
        # Implement EV calculation
        from BackEnd.db import plays_collection
        from BackEnd.engine.phase_resolution import get_hco_skeleton
        from BackEnd.utils.shared_defense import (
            _get_23_zone_boundaries,
            _get_32_zone_boundaries,
            _get_131_zone_boundaries,
            _point_in_zone
        )
        from BackEnd.constants import HCO_STRING_SPOTS
        from BackEnd.utils.shared import get_away_player_coords
        
        # Step 1: Get play type and focus from playcall
        play_doc = plays_collection.find_one({"name": offensive_playcall})
        if not play_doc:
            return 0.0
        
        play_type = play_doc.get("play_type", "motion")
        play_focus = play_doc.get("play_focus", "inside")
        
        # Step 2: Get successful variant skeleton to find projected shooter and passer
        successful_skeleton = get_hco_skeleton(None, self.game, lean_score=1.0)
        if not successful_skeleton or "steps" not in successful_skeleton:
            return 0.0
        
        steps = successful_skeleton.get("steps", [])
        if not steps:
            return 0.0
        
        # Extract projected shooter and passer
        projected_shooter_pos = None
        projected_passer_pos = None
        
        final_step = steps[-1]
        for pos, action_info in final_step.get("pos_actions", {}).items():
            if action_info.get("action", "").lower() == "shoot":
                projected_shooter_pos = pos
                break
        
        if projected_shooter_pos:
            shot_step_index = len(steps) - 1
            for step_index in range(shot_step_index - 1, max(0, shot_step_index - 5) - 1, -1):
                if step_index < 0:
                    break
                step = steps[step_index]
                pos_actions = step.get("pos_actions", {})
                shooter_action_info = pos_actions.get(projected_shooter_pos)
                if shooter_action_info and shooter_action_info.get("action", "").lower() == "receive":
                    for pos, action_info in pos_actions.items():
                        if pos != projected_shooter_pos and action_info.get("action", "").lower() == "pass":
                            projected_passer_pos = pos
                            break
                    if projected_passer_pos:
                        break
        
        # Step 3: Calculate offense score
        offense_score = 0.0
        
        if play_type == "motion":
            total_sc = sum(player.attributes.get("SC", 50) for player in offensive_lineup.values() if player)
            total_st = sum(player.attributes.get("ST", 50) for player in offensive_lineup.values() if player)
            total_ag = sum(player.attributes.get("AG", 50) for player in offensive_lineup.values() if player)
            total_sh = sum(player.attributes.get("SH", 50) for player in offensive_lineup.values() if player)
            
            if play_focus == "inside":
                offense_score = (total_sc + total_st * 0.5) / 5
            elif play_focus == "attack":
                offense_score = (total_sc + total_ag * 0.5) / 5
            elif play_focus == "outside":
                offense_score = (total_sh * 1.5) / 5
        else:  # set_play
            shooter = offensive_lineup.get(projected_shooter_pos) if projected_shooter_pos else None
            passer = offensive_lineup.get(projected_passer_pos) if projected_passer_pos else None
            
            if not shooter:
                return 0.0
            
            shooter_sc = shooter.attributes.get("SC", 50)
            shooter_st = shooter.attributes.get("ST", 50)
            shooter_ag = shooter.attributes.get("AG", 50)
            shooter_sh = shooter.attributes.get("SH", 50)
            
            if play_focus == "inside":
                if passer:
                    offense_score = shooter_sc + shooter_st * 0.25 + passer.attributes.get("PS", 50) * 0.25
                else:
                    offense_score = shooter_sc + shooter_st * 0.5
            elif play_focus == "attack":
                if passer:
                    offense_score = shooter_sc + shooter_ag * 0.25 + passer.attributes.get("PS", 50) * 0.25
                else:
                    offense_score = shooter_sc + shooter_ag * 0.5
            elif play_focus == "outside":
                if passer:
                    offense_score = shooter_sh * 1.25 + passer.attributes.get("IQ", 50) * 0.25
                else:
                    offense_score = shooter_sh * 1.5
        
        # Step 4: Calculate defense score
        defense_score = 0.0
        
        if defensive_playcall == "Man":
            if play_type == "motion":
                total_id = sum(player.attributes.get("ID", 50) for player in defensive_lineup.values() if player)
                total_st = sum(player.attributes.get("ST", 50) for player in defensive_lineup.values() if player)
                defense_score = (total_id + total_st * 0.5) / 5
            else:  # set_play
                defender = defensive_lineup.get(projected_shooter_pos) if projected_shooter_pos else None
                if not defender:
                    defense_score = 0.0
                else:
                    def_id = defender.attributes.get("ID", 50)
                    def_od = defender.attributes.get("OD", 50)
                    def_ag = defender.attributes.get("AG", 50)
                    def_st = defender.attributes.get("ST", 50)
                    
                    if play_focus == "inside":
                        defense_score = def_id + def_st * 0.25
                    elif play_focus == "attack":
                        defense_score = def_id + def_ag * 0.25
                    elif play_focus == "outside":
                        defense_score = def_od * 1.25
        else:
            # Zone defense: team_d + 0.5 * player_d
            zone_team_d_values = {
                "2-3 Zone": {"inside": 80, "attack": 40, "outside": 5},
                "3-2 Zone": {"inside": 10, "attack": 30, "outside": 80},
                "1-3-1 Zone": {"inside": 20, "attack": 60, "outside": 20}
            }
            team_d = zone_team_d_values.get(defensive_playcall, {}).get(play_focus, 0)
            
            shooter_spot = "key"
            if steps and projected_shooter_pos:
                final_step = steps[-1]
                shooter_action = final_step.get("pos_actions", {}).get(projected_shooter_pos, {})
                shooter_spot = shooter_action.get("location") or shooter_action.get("spot") or "key"
            
            shooter_coords = HCO_STRING_SPOTS.get(shooter_spot, {"x": 50, "y": 25})
            is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
            if is_away_offense:
                shooter_coords = get_away_player_coords(shooter_coords)
            
            if defensive_playcall == "3-2 Zone":
                zone_boundaries = _get_32_zone_boundaries(shooter_spot, is_away_offense)
            elif defensive_playcall == "1-3-1 Zone":
                zone_boundaries = _get_131_zone_boundaries(shooter_spot, is_away_offense)
            else:
                zone_boundaries = _get_23_zone_boundaries(shooter_spot, is_away_offense)
            
            zone_defender_pos = None
            for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                if def_pos in defensive_lineup and def_pos in zone_boundaries:
                    zone_coords = zone_boundaries[def_pos]
                    if _point_in_zone(shooter_coords, zone_coords, False):
                        zone_defender_pos = def_pos
                        break
            
            if not zone_defender_pos:
                min_dist = float('inf')
                for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                    if def_pos in defensive_lineup and def_pos in zone_boundaries:
                        zone_coords = zone_boundaries[def_pos]
                        if zone_coords:
                            avg_x = sum(c[0] for c in zone_coords) / len(zone_coords)
                            avg_y = sum(c[1] for c in zone_coords) / len(zone_coords)
                            zone_center = {"x": avg_x, "y": avg_y}
                            dist = ((shooter_coords["x"] - zone_center["x"]) ** 2 + 
                                   (shooter_coords["y"] - zone_center["y"]) ** 2) ** 0.5
                            if dist < min_dist:
                                min_dist = dist
                                zone_defender_pos = def_pos
                
                if not zone_defender_pos:
                    zone_defender_pos = "C"
            
            zone_defender = defensive_lineup.get(zone_defender_pos) if zone_defender_pos else None
            if not zone_defender:
                player_d = 0.0
            else:
                def_id = zone_defender.attributes.get("ID", 50)
                def_od = zone_defender.attributes.get("OD", 50)
                def_ag = zone_defender.attributes.get("AG", 50)
                def_st = zone_defender.attributes.get("ST", 50)
                
                if play_focus == "inside":
                    player_d = def_id + def_st * 0.25
                elif play_focus == "attack":
                    player_d = def_id + def_ag * 0.25
                elif play_focus == "outside":
                    player_d = def_od * 1.25
            
            if defensive_playcall == "1-3-1 Zone":
                player_d *= 1.15
            
            defense_score = team_d + 0.5 * player_d
        
        # Step 5: Calculate EV = (offense - defense) * 2, capped at ±99%
        ev_diff = offense_score - defense_score
        ev_percentage = ev_diff * 2.0
        
        if ev_percentage > 99.0:
            ev_percentage = 99.0
        elif ev_percentage < -99.0:
            ev_percentage = -99.0
        
        return ev_percentage
    
    def _store_ev_score(self, ev, calls, offense_team, defense_team):
        """
        Store EV score in offense and defense scouting data.
        
        Args:
            ev (float): EV percentage from -99.0 to 99.0
            calls (dict): Playcall information with offense_type, offense_focus, defense_playcall
            offense_team: Offensive team object
            defense_team: Defensive team object
        """
        try:
            # Get play type and focus
            offense_play_type = calls.get("offense_type", "").lower()
            offense_focus = calls.get("offense_focus", "")
            defense_playcall = calls.get("defense", "")
            
            # Normalize play type
            if offense_play_type == "set_play":
                offense_play_type = "set"
            
            # Store in offense scouting data
            if offense_play_type in ["motion", "set"] and offense_focus in ["inside", "attack", "outside"]:
                play_type_label = "Motion" if offense_play_type == "motion" else "Set"
                pc = offense_team.scouting_data["offense"]["Playcalls"]
                
                # Determine defense tracking key
                if defense_playcall == "Man":
                    vs_key = "vs_man"
                elif defense_playcall == "2-3 Zone":
                    vs_key = "vs_2-3_zone"
                elif defense_playcall == "3-2 Zone":
                    vs_key = "vs_3-2_zone"
                elif defense_playcall == "1-3-1 Zone":
                    vs_key = "vs_1-3-1_zone"
                else:
                    vs_key = None
                
                # Store EV in overall and focus buckets
                if "ev_scores" not in pc[play_type_label]["overall"]:
                    pc[play_type_label]["overall"]["ev_scores"] = []
                if "ev_scores" not in pc[play_type_label][offense_focus]:
                    pc[play_type_label][offense_focus]["ev_scores"] = []
                
                pc[play_type_label]["overall"]["ev_scores"].append(ev)
                pc[play_type_label][offense_focus]["ev_scores"].append(ev)
                
                # Store EV in vs_* buckets
                if vs_key and vs_key in pc[play_type_label]["overall"]:
                    if "ev_scores" not in pc[play_type_label]["overall"][vs_key]:
                        pc[play_type_label]["overall"][vs_key]["ev_scores"] = []
                    pc[play_type_label]["overall"][vs_key]["ev_scores"].append(ev)
                
                if vs_key and vs_key in pc[play_type_label][offense_focus]:
                    if "ev_scores" not in pc[play_type_label][offense_focus][vs_key]:
                        pc[play_type_label][offense_focus][vs_key]["ev_scores"] = []
                    pc[play_type_label][offense_focus][vs_key]["ev_scores"].append(ev)
                
                # Store in vs_zone aggregate if zone defense
                from BackEnd.utils.defense_utils import is_zone_defense
                if is_zone_defense(defense_playcall) and "vs_zone" in pc[play_type_label]["overall"]:
                    if "ev_scores" not in pc[play_type_label]["overall"]["vs_zone"]:
                        pc[play_type_label]["overall"]["vs_zone"]["ev_scores"] = []
                    if "ev_scores" not in pc[play_type_label][offense_focus]["vs_zone"]:
                        pc[play_type_label][offense_focus]["vs_zone"]["ev_scores"] = []
                    pc[play_type_label]["overall"]["vs_zone"]["ev_scores"].append(ev)
                    pc[play_type_label][offense_focus]["vs_zone"]["ev_scores"].append(ev)
                
                # Store in Cumulative
                if "ev_scores" not in pc["Cumulative"][offense_focus]:
                    pc["Cumulative"][offense_focus]["ev_scores"] = []
                pc["Cumulative"][offense_focus]["ev_scores"].append(ev)
            
            # Store in defense scouting data
            if defense_playcall in defense_team.scouting_data["defense"]:
                def_data = defense_team.scouting_data["defense"][defense_playcall]
                game_stats = def_data.get("game_stats", {})
                
                # Store EV in top-level game_stats
                if "ev_scores" not in game_stats:
                    game_stats["ev_scores"] = []
                game_stats["ev_scores"].append(ev)
                
                # Store EV in vs_* buckets
                if offense_play_type == "motion":
                    if "ev_scores" not in game_stats.get("vs_motion", {}):
                        game_stats.setdefault("vs_motion", {})["ev_scores"] = []
                    game_stats["vs_motion"]["ev_scores"].append(ev)
                elif offense_play_type == "set":
                    if "ev_scores" not in game_stats.get("vs_set", {}):
                        game_stats.setdefault("vs_set", {})["ev_scores"] = []
                    game_stats["vs_set"]["ev_scores"].append(ev)
                
                if offense_focus in ["inside", "attack", "outside"]:
                    vs_focus_key = f"vs_{offense_focus}"
                    if "ev_scores" not in game_stats.get(vs_focus_key, {}):
                        game_stats.setdefault(vs_focus_key, {})["ev_scores"] = []
                    game_stats[vs_focus_key]["ev_scores"].append(ev)
                    
                    # Store in combination buckets
                    if offense_play_type == "motion":
                        combo_key = f"vs_motion_{offense_focus}"
                        if "ev_scores" not in game_stats.get(combo_key, {}):
                            game_stats.setdefault(combo_key, {})["ev_scores"] = []
                        game_stats[combo_key]["ev_scores"].append(ev)
                    elif offense_play_type == "set":
                        combo_key = f"vs_set_{offense_focus}"
                        if "ev_scores" not in game_stats.get(combo_key, {}):
                            game_stats.setdefault(combo_key, {})["ev_scores"] = []
                        game_stats[combo_key]["ev_scores"].append(ev)
        except Exception as e:
            # Silently handle errors to avoid disrupting gameplay
            pass
    
    def resolve_half_court_offense(self):
        from BackEnd.engine.phase_resolution import resolve_half_court_offense_logic
        return resolve_half_court_offense_logic(self.game)


    def resolve_fast_break(self):
        return resolve_fast_break_logic(self.game) 

    def resolve_free_throw(self):
        return resolve_free_throw_logic(self.game)
    
    def resolve_turnover(self):
        return resolve_turnover_logic(self.game)
    
    def resolve_offensive_rebound_turn(self):
        """
        Process an offensive rebound as a separate turn.
        This is called after a MISS turn that had an OREB.
        
        Returns a turn result for: PUTBACK_MAKE, PUTBACK_MISS, or KICKOUT
        """
        from BackEnd.utils.shared import resolve_offensive_rebound, get_name_safe, unpack_game_context, serialize_lineup
        from BackEnd.models.shot_manager import ShotManager
        
        pending_oreb = self.game.game_state.get("pending_oreb")
        if not pending_oreb:
            return None
        
        # Clear the pending OREB immediately (before processing)
        # If this OREB results in another OREB, it will be set again
        self.game.game_state["pending_oreb"] = None
        
        # Capture player stats before OREB resolution (for deltas)
        pre_stats = {}
        for team in (self.game.home_team, self.game.away_team):
            for player in team.get_all_players():
                pre_stats[player.player_id] = dict(player.stats["game"])
        
        rebounder = pending_oreb["rebounder"]
        game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(self.game)
        
        # Resolve what happens with the offensive rebound
        oreb_event = resolve_offensive_rebound(self.game, rebounder)
        
        if oreb_event["event_type"] == "PUTBACK_ATTEMPT":
            self.logger.log("putbackStart")
            self.logger.log(oreb_event["result"].lower())
            
            # Build roles for the putback shot (for animation and three-point determination)
            # Putback shots don't have a skeleton, so we'll use current coords
            defender_pos = ["C", "PF", "SF"][0]  # Simplified - closest big
            defender = def_lineup.get(defender_pos, list(def_lineup.values())[0])
            
            putback_roles = {
                "shooter": rebounder,
                "ball_handler": rebounder,
                "defender": defender,
                "passer": None,
                "screener": None,
                "steps": [],  # No skeleton for putbacks
            }
            
            if oreb_event["result"] == "MAKE":
                text = f"{get_name_safe(rebounder)} goes back up and puts it in!"
                possession_flips = True
                # Check for defensive pressure opportunity (FCP/HCT) after putback make
                pressure_type = self.determine_defensive_pressure_type()
                game_state["offensive_state"] = pressure_type
                
                shooter_team_id = getattr(rebounder, "team_id", None) or off_team.team_id
                # print(f"🏀 PUTBACK_MAKE: shooter={get_name_safe(rebounder)} team_id={shooter_team_id} off_team={off_team.name}")
                
                # Compute stat deltas (same as run_micro_turn)
                deltas = {}
                for team in (self.game.home_team, self.game.away_team):
                    for player in team.get_all_players():
                        prev = pre_stats.get(player.player_id, {})
                        diff = {
                            stat: player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                            for stat in player.stats["game"]
                            if player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                        }
                        if diff:
                            deltas[player.player_id] = {"team": team.name, "stats": diff}
                
                # Include current energy levels
                player_energy = {}
                for team in (self.game.home_team, self.game.away_team):
                    for pos, player in team.lineup.items():
                        player_energy[player.player_id] = {
                            "NG": player.attributes.get("NG", 1.0),
                            "team": team.name
                        }
                
                # Update team stats before sending
                self.game.update_team_stats()
                
                return {
                    "result_type": "PUTBACK_MAKE",
                    "ball_handler": getattr(rebounder, "player_id", None),
                    "shooter": getattr(rebounder, "player_id", None),
                    "shooter_team_id": shooter_team_id,
                    "defender": getattr(defender, "player_id", None),
                    "text": text,
                    "possession_flips": possession_flips,
                    "time_elapsed": oreb_event.get("timeElapsed", 3),
                    "points": oreb_event.get("points", 2),
                    "scoring_team": off_team.name,
                    "next_defensive_setup": pressure_type,
                    "animations": [],  # Putbacks use simple animation, not skeleton
                    "rebounderId": getattr(rebounder, "player_id", None),
                    "quarter": self.game.quarter,
                    # Add fields needed by frontend for stat display
                    "deltas": deltas,
                    "player_energy": player_energy,
                    "score": dict(self.game.score),
                    "home_lineup": serialize_lineup(self.game.home_team.lineup),
                    "away_lineup": serialize_lineup(self.game.away_team.lineup),
                    "team_totals": {
                        self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                        self.game.away_team.name: self.game.away_team.get_team_game_stats()
                    },
                    "team_stats": {
                        self.game.home_team.name: {
                            "offense": self.game.home_team.scouting_data.get("offense", {}),
                            "defense": self.game.home_team.scouting_data.get("defense", {})
                        },
                        self.game.away_team.name: {
                            "offense": self.game.away_team.scouting_data.get("offense", {}),
                            "defense": self.game.away_team.scouting_data.get("defense", {})
                        }
                    },
                }
            else:
                # Putback missed - check for rebound
                text = f"{get_name_safe(rebounder)} goes back up but misses."
                
                # Initialize possession_flips based on rebound type
                possession_flips = False
                
                shooter_team_id = getattr(rebounder, "team_id", None) or off_team.team_id
                # print(f"🏀 PUTBACK_MISS: shooter={get_name_safe(rebounder)} rebounder.team_id={getattr(rebounder, 'team_id', None)} off_team.team_id={off_team.team_id} off_team.name={off_team.name} final_shooter_team_id={shooter_team_id}")
                
                result = {
                    "result_type": "PUTBACK_MISS",
                    "ball_handler": getattr(rebounder, "player_id", None),
                    "shooter": getattr(rebounder, "player_id", None),
                    "shooter_team_id": shooter_team_id,
                    "defender": getattr(defender, "player_id", None),
                    "text": text,
                    "possession_flips": possession_flips,  # Will be updated based on rebound type
                    "time_elapsed": oreb_event.get("timeElapsed", 3),
                    "animations": [],
                    "rebounderId": getattr(rebounder, "player_id", None),
                    "quarter": self.game.quarter,
                }
                
                # Check if there's another rebound
                if oreb_event.get("rebound"):
                    rebound_data = oreb_event["rebound"]
                    rebound_type = rebound_data.get("rebound_type", "DREB")
                    result["rebound_type"] = rebound_type
                    result["rebounderId"] = rebound_data.get("rebounderId")
                    result["ballSpot"] = rebound_data.get("ballSpot")  # Add ballSpot for frontend animation
                    
                    # Set possession flip based on rebound type
                    possession_flips = (rebound_type == "DREB")
                    result["possession_flips"] = possession_flips
                    
                    rebounder_id = rebound_data.get("rebounderId")
                    new_rebounder = None
                    for player in list(off_team.get_all_players()) + list(def_team.get_all_players()):
                        if getattr(player, "player_id", None) == rebounder_id:
                            new_rebounder = player
                            break
                    
                    if new_rebounder:
                        text += f" {get_name_safe(new_rebounder)} grabs the rebound."
                        result["text"] = text
                    
                    # If it's another OREB, set pending for next turn
                    if rebound_data.get("rebound_type") == "OREB" and new_rebounder:
                        game_state["pending_oreb"] = {
                            "rebounder": new_rebounder,
                            "rebounder_id": rebounder_id,
                        }
                    elif rebound_data.get("rebound_type") == "DREB":
                        # Defensive rebound - preserve next_play_type from original shot
                        # Fast Break is determined DURING the shot (by defense tempo), not after DREB
                        # If defense_release_list was set during the shot, next_play_type was already set to FAST_BREAK
                        # If not, it was set to HCO. We preserve that decision here.
                        # Legacy: Don't recalculate fast break here - it causes bugs where fast break has no release player
                        next_play_type = game_state.get("offensive_state", "HCO")
                        result["next_play_type"] = next_play_type
                
                # Compute stat deltas (same as run_micro_turn)
                # Exclude REB from deltas since it's automatically calculated from OREB + DREB
                # The frontend will calculate REB from OREB + DREB to avoid double-counting
                deltas = {}
                for team in (self.game.home_team, self.game.away_team):
                    for player in team.get_all_players():
                        prev = pre_stats.get(player.player_id, {})
                        diff = {
                            stat: player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                            for stat in player.stats["game"]
                            if stat != "REB" and player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                        }
                        if diff:
                            deltas[player.player_id] = {"team": team.name, "stats": diff}
                
                # Include current energy levels
                player_energy = {}
                for team in (self.game.home_team, self.game.away_team):
                    for pos, player in team.lineup.items():
                        player_energy[player.player_id] = {
                            "NG": player.attributes.get("NG", 1.0),
                            "team": team.name
                        }
                
                # Update team stats before sending
                self.game.update_team_stats()
                
                # Add fields needed by frontend for stat display
                result["deltas"] = deltas
                result["player_energy"] = player_energy
                result["score"] = dict(self.game.score)
                result["home_lineup"] = serialize_lineup(self.game.home_team.lineup)
                result["away_lineup"] = serialize_lineup(self.game.away_team.lineup)
                result["team_totals"] = {
                    self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                    self.game.away_team.name: self.game.away_team.get_team_game_stats()
                }
                result["team_stats"] = {
                    self.game.home_team.name: {
                        "offense": self.game.home_team.scouting_data.get("offense", {}),
                        "defense": self.game.home_team.scouting_data.get("defense", {})
                    },
                    self.game.away_team.name: {
                        "offense": self.game.away_team.scouting_data.get("offense", {}),
                        "defense": self.game.away_team.scouting_data.get("defense", {})
                    }
                }
                
                return result
        
        else:
            # Kickout
            self.logger.log("kickoutStart")
            pg = off_team.lineup.get("PG")
            text = f"{get_name_safe(rebounder)} kicks it out to reset."
            game_state["offensive_state"] = "HCO"
            
            # Compute stat deltas (same as run_micro_turn)
            deltas = {}
            for team in (self.game.home_team, self.game.away_team):
                for player in team.get_all_players():
                    prev = pre_stats.get(player.player_id, {})
                    diff = {
                        stat: player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                        for stat in player.stats["game"]
                        if player.stats["game"].get(stat, 0) - prev.get(stat, 0)
                    }
                    if diff:
                        deltas[player.player_id] = {"team": team.name, "stats": diff}
            
            # Include current energy levels
            player_energy = {}
            for team in (self.game.home_team, self.game.away_team):
                for pos, player in team.lineup.items():
                    player_energy[player.player_id] = {
                        "NG": player.attributes.get("NG", 1.0),
                        "team": team.name
                    }
            
            # Update team stats before sending
            self.game.update_team_stats()
            
            return {
                "result_type": "OREB_KICKOUT",
                "ball_handler": getattr(rebounder, "player_id", None),
                "text": text,
                "possession_flips": False,
                "time_elapsed": oreb_event.get("timeElapsed", 2),
                "animations": [],
                "rebounderId": getattr(rebounder, "player_id", None),
                "pgId": getattr(pg, "player_id", None) if pg else None,
                "quarter": self.game.quarter,
                # Add fields needed by frontend for stat display
                "deltas": deltas,
                "player_energy": player_energy,
                "score": dict(self.game.score),
                "home_lineup": serialize_lineup(self.game.home_team.lineup),
                "away_lineup": serialize_lineup(self.game.away_team.lineup),
                "team_totals": {
                    self.game.home_team.name: self.game.home_team.get_team_game_stats(),
                    self.game.away_team.name: self.game.away_team.get_team_game_stats()
                },
                "team_stats": {
                    self.game.home_team.name: {
                        "offense": self.game.home_team.scouting_data.get("offense", {}),
                        "defense": self.game.home_team.scouting_data.get("defense", {})
                    },
                    self.game.away_team.name: {
                        "offense": self.game.away_team.scouting_data.get("offense", {}),
                        "defense": self.game.away_team.scouting_data.get("defense", {})
                    }
                },
            }

    def update_clock_and_possession(self, result):
        # 🕒 Reduce clock by time_elapsed
        time_elapsed = result.get("time_elapsed", 0)
        self.game.game_state["time_remaining"] -= time_elapsed

        # Clamp to 0
        if self.game.game_state["time_remaining"] < 0:
            self.game.game_state["time_remaining"] = 0

        # Convert to clock display (e.g., 400 → "6:40")
        minutes = self.game.game_state["time_remaining"] // 60
        seconds = self.game.game_state["time_remaining"] % 60
        self.game.game_state["clock"] = f"{minutes}:{seconds:02d}"

        # 🔁 Flip possession if flagged
        if result.get("possession_flips"):
            self.game.switch_possession()

    def _reconcile_player_points(self, result):
        """Ensure summed player PTS match the official team score.

        This check runs when a possession ends or the quarter expires. If the
        total points recorded across players for a team does not match the
        team's score, a corrective delta is added and the discrepancy is
        logged. This prevents clients from double counting when ``turn.points``
        is present in the payload.
        """
        possession_end = result.get("possession_flips")
        quarter_end = self.game.game_state.get("time_remaining", 0) == 0
        if not (possession_end or quarter_end):
            return

        for team in (self.game.home_team, self.game.away_team):
            team_score = self.game.score[team.name]
            total_pts = sum(
                player.stats["game"].get("PTS", 0) for player in team.get_all_players()
            )
            if total_pts == team_score:
                continue

            diff = team_score - total_pts
            # Log the discrepancy for debugging/auditing purposes
            self.logger.log(f"ptsReconcile:{team.name}:{total_pts}->{team_score}")

            # Choose a player to receive the adjustment. Prefer the players on
            # the floor (``team.lineup``) so the correction reflects what
            # viewers see.  Fall back to the full roster for edge cases where
            # the lineup has not yet been populated.
            players = list(team.lineup.values()) or list(team.get_all_players())
            if not players:
                continue  # nothing we can do
            player = players[0]
            player.stats["game"]["PTS"] = player.stats["game"].get("PTS", 0) + diff

            # Reflect the correction in the deltas payload
            deltas = result.setdefault("deltas", {})
            entry = deltas.setdefault(player.player_id, {"team": team.name, "stats": {}})
            entry["stats"]["PTS"] = entry["stats"].get("PTS", 0) + diff

    def assign_roles(self, off_call="INSIDE", def_call="MAN", skeleton=None):
        from BackEnd.utils.shared import get_name_safe
        import logging
        
        game = self.game
        game_state = game.game_state
        off_team = game.offense_team
        def_team = game.defense_team
        off_lineup = off_team.lineup
        def_lineup = def_team.lineup
        tempo_call = off_team.strategy_calls["tempo_call"]
        
        # Log lineup state to diagnose KeyError
        logging.info(f"🏀 assign_roles: offense_team={off_team.name} ({'HOME' if off_team.is_home_team else 'AWAY'}), offense_lineup_keys={list(off_lineup.keys()) if off_lineup else 'EMPTY'}, defense_team={def_team.name} ({'HOME' if def_team.is_home_team else 'AWAY'}), defense_lineup_keys={list(def_lineup.keys()) if def_lineup else 'EMPTY'}")

        # --- Step 1: Pick scene based on playcall
        from BackEnd.playcall_skeletons.outside_skeletons import OUTSIDE_SCENES
        from BackEnd.playcall_skeletons.attack_skeletons import ATTACK_SCENES
        from BackEnd.playcall_skeletons.set_play_skeletons import SET_PLAY_SCENES
        from BackEnd.playcall_skeletons.freelance_skeletons import FREELANCE_SCENES
        from BackEnd.playcall_skeletons.base_skeletons import BASE_SCENES
        
        def derive_roles_from_steps(steps, off_lineup):
            """
            Derive shooter, passer, screener from the skeleton steps.
            Optimized to focus on final steps for turn-level roles (backend logic).
            Still tracks ball ownership per step for animation (frontend).
            """
            from BackEnd.constants import HCO_STRING_SPOTS
            
            shooter_pos = None
            screener_pos = None
            passer_pos = None
            ball_owner_by_step = []
            ball_handler_coords_by_step = []

            # Track ball ownership through all steps (needed for frontend animation)
            current_owner_pos = None
            for step in steps:
                pos_actions = step.get("pos_actions", {})
                step_owner = None
                step_coords = {"x": 50, "y": 25}  # Default center court
                
                # Find who has ball at this step
                for pos, action_info in pos_actions.items():
                    action = action_info.get("action", "")
                    
                    if action in ["handle_ball", "receive", "shoot", "pass"]:
                        step_owner = pos
                        # MongoDB skeletons use "location", old skeletons use "spot"
                        location_key = action_info.get("location") or action_info.get("spot", "key")
                        step_coords = HCO_STRING_SPOTS.get(location_key, {"x": 50, "y": 25})
                        
                        if action == "receive":
                            current_owner_pos = pos
                        elif action == "handle_ball":
                            if current_owner_pos is None:
                                current_owner_pos = pos
                        
                        break
                
                ball_owner_by_step.append(step_owner or current_owner_pos)
                ball_handler_coords_by_step.append(step_coords)
            
            # === TURN-LEVEL ROLES (for backend shot calculation) ===
            # Extract from final steps only - much simpler and more accurate
            # Debug logging removed - was cluttering logs
            
            if not steps:
                return {
                    "shooter_pos": None,
                    "screener_pos": "PF",
                    "passer_pos": None,
                    "ball_owner_by_step": ball_owner_by_step,
                    "ball_handler_coords_by_step": ball_handler_coords_by_step
                }
            
            # 1. Get SHOOTER from final step
            final_step = steps[-1]
            for pos, action_info in final_step.get("pos_actions", {}).items():
                action = action_info.get("action", "").lower()
                if action == "shoot":
                    shooter_pos = pos
                    break
            
            # Also check events in final step
            if not shooter_pos:
                for event in final_step.get("events", []):
                    if event.get("type") == "shot":
                        shooter_pos = event.get("by")
                        break
            
            # Fallback: use final ball handler
            if not shooter_pos and ball_owner_by_step:
                final_owner = ball_owner_by_step[-1]
                shooter_pos = final_owner if isinstance(final_owner, str) else None
            
            # 2. Get PASSER based on three criteria:
            #    a) Last player to make a pass to the shooter
            #    b) The pass and receive happened in the same step (passer has "pass" action, shooter has "receive" action)
            #    c) The pass was within 5 steps of the shot being taken
            if shooter_pos:
                # Look back up to 5 steps from the final shot step
                shot_step_index = len(steps) - 1
                last_pass_step_index = None
                
                # Find the last step where shooter received a pass (within last 5 steps)
                # Start from the step before the shot and work backwards up to 5 steps
                search_start = max(0, shot_step_index - 5)
                for step_index in range(shot_step_index - 1, search_start - 1, -1):
                    if step_index < 0:
                        break
                    
                    step = steps[step_index]
                    pos_actions = step.get("pos_actions", {})
                    
                    # Check if shooter has "receive" action in this step
                    shooter_action_info = pos_actions.get(shooter_pos)
                    if shooter_action_info:
                        shooter_action = shooter_action_info.get("action", "").lower()
                        
                        if shooter_action == "receive":
                            # Shooter received the ball - now find who passed it
                            # Look for a player with "pass" action in this same step
                            for pos, action_info in pos_actions.items():
                                if pos == shooter_pos:
                                    continue  # Skip shooter themselves
                                
                                action = action_info.get("action", "").lower()
                                if action == "pass":
                                    # Found a pass in the same step as shooter receiving
                                    # This is the last pass to the shooter (we're searching backwards)
                                    last_pass_step_index = step_index
                                    passer_pos = pos
                                    logging.info(f"🎯 ASSIST DEBUG: Found pass to shooter! passer_pos={passer_pos}, shooter_pos={shooter_pos}, step_index={step_index}, shot_step_index={shot_step_index}")
                                    break
                            
                            # If we found a pass, stop searching (we want the LAST pass to the shooter)
                            if last_pass_step_index is not None:
                                break
                
                # Verify the pass was within 5 steps of the shot
                if last_pass_step_index is not None:
                    steps_from_shot = shot_step_index - last_pass_step_index
                    if steps_from_shot <= 5:
                        # All criteria met: last pass to shooter within 5 steps
                        logging.info(f"🎯 ASSIST DEBUG: Found passer_pos={passer_pos}, shooter_pos={shooter_pos}, steps_from_shot={steps_from_shot}")
                    else:
                        logging.info(f"🎯 ASSIST DEBUG: Pass found but too far from shot (steps_from_shot={steps_from_shot}, max=5)")
                        passer_pos = None  # Pass too far, no assist
                else:
                    logging.warning(f"⚠️ ASSIST DEBUG: No pass to shooter found in last 5 steps (shooter_pos={shooter_pos}, shot_step_index={shot_step_index}, search_start={search_start}, total_steps={len(steps)})")
                    passer_pos = None  # No pass found, no assist
            
            # print(f"🎯 ASSIST DEBUG: Final passer_pos={passer_pos}")
            
            # 3. Get SCREENER - find last screen that helped the shooter
            if shooter_pos:
                for step in reversed(steps):
                    for event in step.get("events", []):
                        if event.get("type") == "screen" and event.get("for") == shooter_pos:
                            screener_pos = event.get("by")
                            break
                    if screener_pos:
                        break
            
            # Fallback screener
            if not screener_pos:
                screener_pos = "PF"
            
            return {
                "shooter_pos": shooter_pos,
                "screener_pos": screener_pos,
                "passer_pos": passer_pos,
                "ball_owner_by_step": ball_owner_by_step,
                "ball_handler_coords_by_step": ball_handler_coords_by_step
            }
        
        # Use provided skeleton from MongoDB if available, otherwise fall back to old system
        if skeleton and "steps" in skeleton:
            # Use the MongoDB skeleton - animate all steps (tempo no longer affects HCO step count)
            steps = skeleton["steps"]
        else:
            # Fallback to old hardcoded skeleton system
            playcall_scenes_map = {
                "Inside": INSIDE_SCENES,
                "Outside": OUTSIDE_SCENES,
                "Attack": ATTACK_SCENES,
                "Set": SET_PLAY_SCENES,
                "Freelance": FREELANCE_SCENES,
                "Base": BASE_SCENES
            }
            
            scenes_list = playcall_scenes_map.get(off_call, INSIDE_SCENES)
            scene = random.choice(scenes_list)
            # print(f"🎬 assign_roles using '{off_call}' skeleton with {len(scene['steps'])} steps")
            
            tempo_to_steps = {"slow": 7, "normal": 5, "fast": 4}
            requested = tempo_to_steps.get(tempo_call.lower(), len(scene["steps"]))

            # Always include the final shot step
            if requested >= len(scene["steps"]):
                steps = scene["steps"]
            else:
                steps = scene["steps"][:requested - 1] + [scene["steps"][-1]]

        # --- Step 2: Initialize outputs
        action_timeline = defaultdict(list)
        touch_counts = defaultdict(int)

        # --- Step 3: Build action timeline + touch counts
        for step_index, step in enumerate(steps):
            pos_actions = step["pos_actions"]
            events = step.get("events", [])

            for pos, action_info in pos_actions.items():
                if pos not in off_lineup:
                    logging.error(f"❌ assign_roles KeyError: position '{pos}' not in offense_lineup. offense_team={off_team.name}, offense_lineup_keys={list(off_lineup.keys()) if off_lineup else 'EMPTY'}")
                    raise KeyError(f"Position '{pos}' not found in offense lineup for {off_team.name}. Available positions: {list(off_lineup.keys()) if off_lineup else 'EMPTY'}")
                player = off_lineup[pos]
                action = action_info["action"]
                # MongoDB skeletons use "location", old skeletons use "spot"
                location_key = action_info.get("location") or action_info.get("spot")
                action_timeline[player].append((step["timestamp"], action, location_key))

                # Count touch if action involves ball
                if action in [ACTIONS["HANDLE"], ACTIONS["PASS"], ACTIONS["RECEIVE"], ACTIONS["SHOOT"]]:
                    touch_counts[player] += 1

            for event in events:
                if event["type"] == "pass":
                    passer = off_lineup[event["from"]]
                    receiver = off_lineup[event["to"]]
                    touch_counts[passer] += 1
                    touch_counts[receiver] += 1
                elif event["type"] == "shot":
                    shooter = off_lineup[event["by"]]
                    touch_counts[shooter] += 1

        # --- Step 4: Derive primary roles from steps (optimized - uses final steps only)
        derived_roles = derive_roles_from_steps(steps, off_lineup)
        
        shooter_pos = derived_roles["shooter_pos"]
        screener_pos = derived_roles["screener_pos"]
        passer_pos = derived_roles["passer_pos"]
        
        # Override passer if it conflicts with shooter/screener
        if passer_pos in [shooter_pos, screener_pos]:
            logging.info(f"🎯 ASSIST DEBUG: Passer conflicts with shooter/screener, setting to None (passer_pos={passer_pos}, shooter_pos={shooter_pos}, screener_pos={screener_pos})")
            passer_pos = None

        # Determine shot defender based on defense type
        from BackEnd.utils.defense_utils import is_zone_defense
        second_defender_pos = None  # Initialize second defender position
        if is_zone_defense(game_state.get("defense_playcall", "Man")):
            # For zone defense: find defender whose zone contains the shooter
            from BackEnd.utils.shared_defense import _get_23_zone_boundaries, _get_32_zone_boundaries, _get_131_zone_boundaries, _point_in_zone
            from BackEnd.constants import HCO_STRING_SPOTS
            from BackEnd.utils.shared import get_away_player_coords
            
            # Get shooter's spot from final step (where they shoot)
            shooter_spot = "key"  # Default fallback
            if steps and shooter_pos:
                final_step = steps[-1]
                shooter_action = final_step.get("pos_actions", {}).get(shooter_pos, {})
                shooter_spot = shooter_action.get("location") or shooter_action.get("spot") or "key"
            
            # Get shooter's coordinates
            shooter_coords = HCO_STRING_SPOTS.get(shooter_spot, {"x": 50, "y": 25})
            
            # Determine court orientation (away team is on offense if offense team ID matches away team ID)
            game = self.game
            is_away_offense = game.offense_team.team_id == game.away_team.team_id
            if is_away_offense:
                shooter_coords = get_away_player_coords(shooter_coords)
            
            # Determine ball location for zone shift (use ball handler's location from steps)
            ball_spot = "key"  # Default fallback
            ball_handler_pos = None
            for step in steps:
                pos_actions = step.get("pos_actions", {})
                for pos, action_info in pos_actions.items():
                    action = action_info.get("action", "")
                    if action in ["handle_ball", "shoot"]:
                        ball_handler_pos = pos
                        ball_spot = action_info.get("location") or action_info.get("spot") or "key"
                        break
                if ball_handler_pos:
                    break
            
            # Get zone boundaries based on ball location (applies shifts)
            # Check if it's 2-3 or 3-2 zone and use appropriate function
            defense_playcall = game_state.get("defense_playcall", "Man")
            if defense_playcall == "3-2 Zone":
                zone_boundaries = _get_32_zone_boundaries(ball_spot, is_away_offense)
            elif defense_playcall == "1-3-1 Zone":
                zone_boundaries = _get_131_zone_boundaries(ball_spot, is_away_offense)
            else:
                zone_boundaries = _get_23_zone_boundaries(ball_spot, is_away_offense)
            
            # Find which defender's zone contains the shooter (check for multiple defenders)
            defender_positions = []
            for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                if def_pos in def_lineup and def_pos in zone_boundaries:
                    zone_coords = zone_boundaries[def_pos]
                    if _point_in_zone(shooter_coords, zone_coords, False):
                        defender_positions.append(def_pos)
            
            # If shooter has two defenders, store both; otherwise use single defender
            if len(defender_positions) >= 2:
                defender_pos = defender_positions[0]  # Primary defender
                second_defender_pos = defender_positions[1]  # Second defender
            elif len(defender_positions) == 1:
                defender_pos = defender_positions[0]
                second_defender_pos = None
            else:
                defender_pos = None
                second_defender_pos = None
            
            # Fallback: if shooter not in any zone, use closest defender
            if not defender_pos:
                # Find defender whose zone center is closest to shooter
                min_dist = float('inf')
                for def_pos in ["PG", "SG", "SF", "PF", "C"]:
                    if def_pos in def_lineup and def_pos in zone_boundaries:
                        zone_coords = zone_boundaries[def_pos]
                        if zone_coords:
                            # Calculate zone center
                            avg_x = sum(c[0] for c in zone_coords) / len(zone_coords)
                            avg_y = sum(c[1] for c in zone_coords) / len(zone_coords)
                            zone_center = {"x": avg_x, "y": avg_y}
                            
                            # Calculate distance
                            dist = ((shooter_coords["x"] - zone_center["x"]) ** 2 + 
                                   (shooter_coords["y"] - zone_center["y"]) ** 2) ** 0.5
                            if dist < min_dist:
                                min_dist = dist
                                defender_pos = def_pos
                
                if not defender_pos:
                    # Final fallback: random defender
                    defender_pos = random.choice(list(def_lineup))
        else:
            # Man-to-man: defender matches shooter position
            defender_pos = shooter_pos

        # --- Step 5: Lookup player objects
        shooter = off_lineup.get(shooter_pos) if shooter_pos else off_lineup["PG"]  # Fallback to PG
        screener = off_lineup.get(screener_pos) if screener_pos else off_lineup["PF"]  # Fallback to PF
        passer = off_lineup.get(passer_pos) if passer_pos else None
        defender = def_lineup.get(defender_pos) if defender_pos else def_lineup["PG"]
        second_defender = def_lineup.get(second_defender_pos) if second_defender_pos and second_defender_pos in def_lineup else None
        
        # Debug logging for passer assignment
        if passer:
            logging.info(f"🎯 ASSIST DEBUG: passer_pos={passer_pos}, passer={get_name_safe(passer)}, shooter={get_name_safe(shooter)}")
        else:
            logging.info(f"🎯 ASSIST DEBUG: No passer found (passer_pos={passer_pos}, shooter={get_name_safe(shooter)})")

        return {
            "shooter": shooter,
            "screener": screener,
            "ball_handler": shooter,
            "passer": passer,
            "defender": defender,
            "second_defender": second_defender,  # Second defender if shooter has two defenders in zone
            "steps": steps,
            "skeleton": skeleton,  # Include skeleton for variant info
            "action_timeline": action_timeline,
            "touch_counts": touch_counts,
            "ball_owner_by_step": derived_roles["ball_owner_by_step"],
            "ball_handler_coords_by_step": derived_roles["ball_handler_coords_by_step"]
        }
    
    def determine_event_type(self, roles):
        game = self.game
        game_state = game.game_state
        off_team = game.offense_team
        def_team = game.defense_team
        def_lineup = def_team.lineup
        off_lineup = off_team.lineup
        defense_call = game_state["defense_playcall"]
        action_timeline = roles["action_timeline"]
        touch_counts = roles["touch_counts"]
        steps = roles["steps"]

        # Step 1: Decay energy for all players
        for player in off_lineup.values():
            if hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
                player.decay_energy(player.get_fatigue_decay_amount())
        for player in def_lineup.values():
            if hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
                player.decay_energy(player.get_fatigue_decay_amount())

        # Step 2: Calculate score for each potential turnover candidate
        turnover_risks = []
        for player, touches in touch_counts.items():
            if touches == 0:
                continue

            attr = player.attributes
            bh_score = (
                attr["BH"] * 0.5 +
                attr["AG"] * 0.2 +
                attr["IQ"] * 0.2 +
                attr["CH"] * 0.1
            ) * random.randint(1, 6)

            def_pos = get_player_position(off_lineup, player)
            from BackEnd.utils.defense_utils import is_zone_defense
            defender = def_lineup.get(def_pos) if not is_zone_defense(defense_call) else random.choice(list(def_lineup.values()))
            
            # Handle case where defender is None (no defender assigned)
            if defender is None:
                pressure = 0
            else:
                def_attr = defender.attributes
            pressure = (
                def_attr["OD"] * 0.3 +
                def_attr["AG"] * 0.3 +
                def_attr["IQ"] * 0.2 +
                def_attr["CH"] * 0.2
            ) * random.randint(1, 6)
            if is_zone_defense(defense_call):
                pressure *= 0.9

            score = bh_score - pressure - (touches * 2)
            turnover_risks.append((score, player, defender))

        # Step 3: Calculate foul risks
        foul_risks = []
        for step_index, step in enumerate(steps):
            for pos, action_data in step["pos_actions"].items():
                action = action_data["action"]
                if action not in ["screen", "post_up", "handle_ball"]:
                    continue  # Only consider foul-prone actions

                offender = off_lineup[pos]
                from BackEnd.utils.defense_utils import is_zone_defense
                defender = def_lineup.get(pos) if not is_zone_defense(defense_call) else random.choice([p for p in def_lineup.values() if p is not None])
                o_attr = offender.attributes

                # Handle case where defender is None (no defender assigned)
                if defender is None:
                    d_score = 0
                else:
                    d_attr = defender.attributes
                d_score = (d_attr["IQ"] * 0.3 + d_attr["CH"] * 0.3 + d_attr["AG"] * 0.2 + d_attr["OD"] * 0.2) * random.randint(1, 6)
                o_score = (o_attr["IQ"] * 0.3 + o_attr["CH"] * 0.3 + o_attr["AG"] * 0.2 + o_attr["ST"] * 0.2) * random.randint(1, 6)

                # Slightly bias toward foul when high activity + tempo
                foul_margin = o_score - d_score
                if foul_margin < off_team.team_attributes["foul_threshold"] * 0.7:
                    foul_risks.append(("O_FOUL", step_index, offender, defender))
                elif d_score < def_team.team_attributes["foul_threshold"] * 1.3:
                    foul_risks.append(("D_FOUL", step_index, offender, defender))

        # Step 4: Decide event
        turnover_risks.sort(key=lambda x: x[0])
        foul_risks.sort(key=lambda x: x[1])  # prioritize earlier fouls

        if turnover_risks and turnover_risks[0][0] < off_team.team_attributes["turnover_threshold"]:
            _, player, defender = turnover_risks[0]
            roles["event_step"] = None  # You could optionally track when
            roles["turnover_player"] = player
            roles["turnover_defender"] = defender
            roles["ball_handler"] = player
            return "TURNOVER"

        elif foul_risks:
            foul_type, step_index, offender, defender = foul_risks[0]
            roles["event_step"] = step_index
            roles["foul_player"] = defender if foul_type == "D_FOUL" else offender
            return foul_type

        # No event = clean possession
        return "SHOT"

    def determine_defensive_pressure_type(self):
        """
        Determine if defensive team should attempt FCP or HCT after a made shot.
        Returns 'FCP', 'HCT', or 'HCO' based on strategy settings and random rolls.
        
        NOTE: After a made shot, possession will flip. The team that just scored
        (currently offense_team) will become the defense team. So we use offense_team's
        settings, not defense_team's settings.
        """
        # After a made shot, possession will flip. The team that just scored
        # (currently offense_team) will become the defense team and apply pressure.
        def_team = self.game.offense_team
        
        # Ensure strategy_settings is initialized (but don't overwrite existing settings)
        # Only initialize if it's completely missing (None), not if it's an empty dict
        if not hasattr(def_team, 'strategy_settings') or def_team.strategy_settings is None:
            import logging
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {def_team.name} missing strategy_settings, initializing with defaults")
            def_team.strategy_settings = def_team._init_strategy_settings()
        elif isinstance(def_team.strategy_settings, dict) and len(def_team.strategy_settings) == 0:
            import logging
            logging.warning(f"⚠️ [STRATEGY SETTINGS] {def_team.name} has empty strategy_settings dict, initializing with defaults")
            def_team.strategy_settings = def_team._init_strategy_settings()
        
        # Get strategy settings - explicitly check for 0 values
        hct_value = def_team.strategy_settings.get("hc_trap", 0)
        fcp_value = def_team.strategy_settings.get("fc_press", 0)
        
        # 🐛 DEBUG: Log strategy settings being used
        import logging
        logging.warning(f"🛡️ [DEFENSIVE PRESSURE] {def_team.name} - HCT={hct_value}, FCP={fcp_value}")
        logging.warning(f"   - Full strategy_settings: {def_team.strategy_settings}")
        logging.warning(f"   - HCT type: {type(hct_value)}, FCP type: {type(fcp_value)}")
        logging.warning(f"   - HCT == 0: {hct_value == 0}, FCP == 0: {fcp_value == 0}")
        
        # If both are 0, default to HCO (no pressure)
        # CRITICAL: Check for 0 explicitly - if user set both to 0, they want NO pressure
        if hct_value == 0 and fcp_value == 0:
            logging.warning(f"   - ✅ Both HCT and FCP are 0, returning HCO (no pressure)")
            return "HCO"
        
        # Remove any strategy with value 0 from consideration
        # CRITICAL: Only add strategies if their values are > 0
        # If user set hc_trap=0 and fc_press=0, neither should be added to strategies dict
        strategies = {"HCO": 8}
        hco_removed = False
        
        # Only add HCT if value is > 0 (user wants it enabled)
        if hct_value and hct_value > 0:
            strategies["HCT"] = hct_value
            if hct_value == 4:
                strategies.pop("HCO", None)  # Remove HCO entirely, don't set to 0
                hco_removed = True
            elif not hco_removed:
                strategies["HCO"] = max(0, strategies["HCO"] - hct_value)
        else:
            logging.warning(f"   - ⚠️ HCT value is {hct_value} (0 or invalid), NOT adding to strategies")
        
        # Only add FCP if value is > 0 (user wants it enabled)
        if fcp_value and fcp_value > 0:
            strategies["FCP"] = fcp_value
            if fcp_value == 4:
                strategies.pop("HCO", None)  # Remove HCO entirely, don't set to 0
                hco_removed = True
            elif not hco_removed:
                strategies["HCO"] = max(0, strategies.get("HCO", 8) - fcp_value)
        else:
            logging.warning(f"   - ⚠️ FCP value is {fcp_value} (0 or invalid), NOT adding to strategies")
        
        # Remove any strategies with value 0 from consideration
        strategies = {k: v for k, v in strategies.items() if v > 0}

        # If only one strategy available, use it
        if len(strategies) == 1:
            selected_strategy = list(strategies.keys())[0]
        else:
            # Weighted random selection between all available strategies
            total_value = sum(strategies.values())
            rand = random.randint(1, 100)
            
            cumulative = 0
            for strategy, value in strategies.items():
                chance = (value / total_value) * 100
                cumulative += chance
                if rand <= cumulative:
                    selected_strategy = strategy
                    break
            else:
                # Fallback to last strategy (shouldn't happen, but safety)
                selected_strategy = list(strategies.keys())[-1]
        
        # Return the selected strategy (no execution roll - weighted selection is the final decision)
        # print(f"🛡️ DEFENSIVE PRESSURE RESULT: Selected {selected_strategy} (strategies={strategies})")
        return selected_strategy
    
    def _print_turn_summary(self, result, offensive_state):
        """Print a clean summary of the turn for debugging."""
        print("\n" + "="*80)
        print(f"TURN #{result.get('turn_count', 0)} SUMMARY")
        print("="*80)
        print(f"Offensive State: {offensive_state}")
        print(f"Result Type: {result.get('result_type', 'N/A')}")
        print(f"Text: {result.get('text', 'N/A')}")
        print(f"Possession Flips: {result.get('possession_flips', False)}")
        
        # Animation data summary
        animations = result.get('animations', [])
        skeleton = result.get('skeleton', {})
        
        print(f"\nAnimation Data for turn {result.get('turn_count', 0)} {offensive_state}:")
        print(f"  - Animations array: {len(animations)} players")
        if skeleton and 'steps' in skeleton:
            print(f"  - Skeleton steps: {len(skeleton['steps'])} timestamps")
        else:
            print(f"  - Skeleton: None")
        
        # Roles summary
        roles = result.get('roles', {})
        if roles:
            print(f"\nRoles:")
            for role_name, role_value in roles.items():
                if role_name in ['offense', 'defense']:
                    print(f"  - {role_name}: {len(role_value) if isinstance(role_value, list) else role_value}")
                else:
                    print(f"  - {role_name}: {role_value}")
        
        # Key player info
        print(f"\nKey Players:")
        for key in ['ball_handler', 'shooter', 'passer', 'defender']:
            if key in result and result[key]:
                print(f"  - {key}: {result[key]}")
        
        print("="*80 + "\n")

