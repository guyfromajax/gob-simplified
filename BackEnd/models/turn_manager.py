from BackEnd.models.logger import Logger
from BackEnd.models.rebound_manager import ReboundManager
from BackEnd.models.playbook_manager import PlaybookManager
from BackEnd.models.animator import Animator
import random
import json
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
    assign_bh_defender_coords,
    assign_non_bh_defender_coords
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

    def setup_baseline_inbound(self):
        """
        Prepare coordinates for a baseline inbound following a made shot.
        The opposing team gets the ball and starts their possession from the baseline.

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
        self.logger.log("defenseUpdate:start")
        d_dest = {}
        for pos, defender in defense_team.lineup.items():
            if pos == "PG":
                d_coords = assign_bh_defender_coords(
                    bh_coords, aggression, is_away_offense
                )
                if is_away_offense:
                    d_coords = getAwayTeamCoords({"tmp": d_coords})["tmp"]
                d_dest[pos] = d_coords
            elif pos in o_dest:
                o_coords = o_dest[pos]
                # Convert offensive coords back to home orientation for calc
                o_calc = getAwayTeamCoords({"tmp": o_coords})["tmp"] if is_away_offense else o_coords
                d_coords = assign_non_bh_defender_coords(
                    o_calc, bh_coords, aggression, is_away_offense
                )
                if is_away_offense:
                    d_coords = getAwayTeamCoords({"tmp": d_coords})["tmp"]
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

        state = self.game.game_state.get("offensive_state", "HCO")
        turn_num = self.game.micro_turn_count
        time_remaining = self.game.game_state.get("clock", "N/A")
        print(f"***** RUN TURN, turn number: {turn_num}, time remaining: {time_remaining}, offensive state: {state} *****")
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
            result = self.resolve_half_court_offense()
            # Add playcalls to result for frontend display
            result["offensive_playcall"] = calls["offense"]
            result["defensive_playcall"] = calls["defense"]
            
            # Add play type and focus for frontend display
            result["offensive_play_type"] = calls.get("offense_type", "-")
            result["offensive_play_focus"] = calls.get("offense_focus", None)
            result["defensive_play_type"] = calls.get("defense_type", "-")
            result["defensive_play_focus"] = calls.get("defense_focus", None)

        # Record possession team before any potential flip
        result["starting_possession_team_id"] = self.game.offense_team.team_id

        # STEP 4: Final updates (clock, logs, animation)
        try:
            self.update_clock_and_possession(result)
            self.logger.log_turn_result(result)
            
            # Update offensive_state based on next_play_type (e.g., after FCP/HCT)
            next_play = result.get("next_play_type")
            if next_play:
                self.game.game_state["offensive_state"] = next_play
                
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
        print(f"Turn {turn_num} RESULT: {result_type} | Next: {next_play_type} | Defense Setup: {next_defensive_setup} | Possession Flips: {possession_flips}")
        print(f"Turn {turn_num} TEXT: {text}")
        
        # self._print_turn_summary(result, state)

        result["home_lineup"] = serialize_lineup(self.game.home_team.lineup)
        result["away_lineup"] = serialize_lineup(self.game.away_team.lineup)

        result["score"] = dict(self.game.score)

        # Include current team stats for frontend updates (from scouting_data)
        result["team_stats"] = {
            self.game.home_team.name: {
                "offense": self.game.home_team.scouting_data.get("offense", {})
            },
            self.game.away_team.name: {
                "offense": self.game.away_team.scouting_data.get("offense", {})
            }
        }
        
        # Include cumulative team stats (from all players) for S1 tab
        # Update team stats before sending
        self.game.update_team_stats()
        result["team_totals"] = {
            self.game.home_team.name: self.game.home_team.get_team_game_stats(),
            self.game.away_team.name: self.game.away_team.get_team_game_stats()
        }

        # Compute stat deltas for each player
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
        result["deltas"] = deltas
        
        # Include current energy levels for all active players (for frontend fatigue display)
        player_energy = {}
        for team in (self.game.home_team, self.game.away_team):
            for pos, player in team.lineup.items():
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
        """
        
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
            print(f"🎯 Selected play: {chosen_playcall} (type={chosen_play_type}, focus={chosen_focus})")
        
        # Record playcall attempt under new buckets
        try:
            # Normalize type/focus labels
            play_type_label = "Motion" if chosen_play_type == "motion" else ("Set" if chosen_play_type == "set_play" else None)
            focus_label = chosen_focus if chosen_focus in ["inside", "attack", "outside"] else None
            if play_type_label and focus_label:
                pc = self.game.offense_team.scouting_data["offense"]["Playcalls"]
                # Motion/Set overall + focus
                pc[play_type_label]["overall"]["attempts"] += 1
                pc[play_type_label][focus_label]["attempts"] += 1
                # Cumulative by focus
                pc["Cumulative"][focus_label]["attempts"] += 1
        except Exception:
            pass

        # Persist play type/focus to game_state for later success attribution
        self.game.game_state["offense_play_type"] = chosen_play_type
        self.game.game_state["offense_play_focus"] = chosen_focus

        # Defense setting (unchanged)
        defense_setting = self.game.defense_team.strategy_settings["defense"]
        chosen_defense = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])
        
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
        # Ensure strategy_settings are initialized for both teams
        if not hasattr(self.game.offense_team, 'strategy_settings') or not self.game.offense_team.strategy_settings:
            self.game.offense_team.strategy_settings = self.game.offense_team._init_strategy_settings()
        if not hasattr(self.game.defense_team, 'strategy_settings') or not self.game.defense_team.strategy_settings:
            self.game.defense_team.strategy_settings = self.game.defense_team._init_strategy_settings()
        
        # Ensure strategy_calls dictionaries exist
        if not hasattr(self.game.offense_team, 'strategy_calls') or not self.game.offense_team.strategy_calls:
            self.game.offense_team.strategy_calls = {}
        if not hasattr(self.game.defense_team, 'strategy_calls') or not self.game.defense_team.strategy_calls:
            self.game.defense_team.strategy_calls = {}

        tempo_setting = self.game.offense_team.strategy_settings["tempo"]
        aggression_setting = self.game.defense_team.strategy_settings["aggression"]

        self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
        self.game.defense_team.strategy_calls["aggression_call"] = random.choice(STRATEGY_CALL_DICTS["aggression"][aggression_setting])
        
        print(f"🎯 STRATEGY CALLS SET - OFF: {self.game.offense_team.name} tempo={self.game.offense_team.strategy_calls['tempo_call']} | DEF: {self.game.defense_team.name} aggr={self.game.defense_team.strategy_calls['aggression_call']}")


    
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
        from BackEnd.utils.shared import resolve_offensive_rebound, get_name_safe, unpack_game_context
        from BackEnd.models.shot_manager import ShotManager
        
        pending_oreb = self.game.game_state.get("pending_oreb")
        if not pending_oreb:
            return None
        
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
                print(f"🏀 PUTBACK_MAKE: shooter={get_name_safe(rebounder)} team_id={shooter_team_id} off_team={off_team.name}")
                
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
                }
            else:
                # Putback missed - check for rebound
                text = f"{get_name_safe(rebounder)} goes back up but misses."
                
                # Initialize possession_flips based on rebound type
                possession_flips = False
                
                shooter_team_id = getattr(rebounder, "team_id", None) or off_team.team_id
                print(f"🏀 PUTBACK_MISS: shooter={get_name_safe(rebounder)} rebounder.team_id={getattr(rebounder, 'team_id', None)} off_team.team_id={off_team.team_id} off_team.name={off_team.name} final_shooter_team_id={shooter_team_id}")
                
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
                        # Defensive rebound - check for fast break
                        from BackEnd.utils.shared import get_fast_break_chance
                        import random
                        next_play_type = "FAST_BREAK" if random.random() < get_fast_break_chance(self.game) else "HCO"
                        game_state["offensive_state"] = next_play_type
                        result["next_play_type"] = next_play_type
                
                return result
        
        else:
            # Kickout
            self.logger.log("kickoutStart")
            pg = off_team.lineup.get("PG")
            text = f"{get_name_safe(rebounder)} kicks it out to reset."
            game_state["offensive_state"] = "HCO"
            
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
        game = self.game
        game_state = game.game_state
        off_team = game.offense_team
        def_team = game.defense_team
        off_lineup = off_team.lineup
        def_lineup = def_team.lineup
        tempo_call = off_team.strategy_calls["tempo_call"]

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

            print("Inside derive_roles_from_steps")
            print(f"steps: {steps}")
            
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
            print(f"🎭 DERIVE ROLES: Final step pos_actions: {final_step.get('pos_actions', {})}")
            for pos, action_info in final_step.get("pos_actions", {}).items():
                action = action_info.get("action", "").lower()
                print(f"🎭 DERIVE ROLES: {pos} action: {action}")
                if action == "shoot":
                    shooter_pos = pos
                    print(f"🎭 DERIVE ROLES: Found shooter in pos_actions: {pos}")
                    break
            
            # Also check events in final step
            if not shooter_pos:
                print(f"🎭 DERIVE ROLES: No shooter in pos_actions, checking events: {final_step.get('events', [])}")
                for event in final_step.get("events", []):
                    if event.get("type") == "shot":
                        shooter_pos = event.get("by")
                        print(f"🎭 DERIVE ROLES: Found shooter in events: {shooter_pos}")
                        break
            
            # Fallback: use final ball handler
            if not shooter_pos and ball_owner_by_step:
                final_owner = ball_owner_by_step[-1]
                shooter_pos = final_owner if isinstance(final_owner, str) else None
                print(f"🎭 DERIVE ROLES: Using fallback shooter (final ball handler): {shooter_pos}")
            
            # 2. Get PASSER from last pass event (check last 2 steps)
            for step in reversed(steps[-2:]):
                for event in step.get("events", []):
                    if event.get("type") == "pass":
                        potential_passer = event.get("from")
                        # Only count as passer if they passed TO the shooter
                        if event.get("to") == shooter_pos:
                            passer_pos = potential_passer
                            break
                if passer_pos:
                    break
            
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
            # Use the MongoDB skeleton
            scene_steps = skeleton["steps"]
            tempo_to_steps = {"slow": 7, "normal": 5, "fast": 4}
            requested = tempo_to_steps.get(tempo_call.lower(), len(scene_steps))
            
            # Always include the final shot step
            if requested >= len(scene_steps):
                steps = scene_steps
            else:
                steps = scene_steps[:requested - 1] + [scene_steps[-1]]
            print(f"🎬 assign_roles using MongoDB skeleton '{off_call}' with {len(steps)} steps (from {len(scene_steps)} total)")
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
            passer_pos = None

        if game_state["defense_playcall"] == "Zone":
            defender_pos = random.choice(list(def_lineup))
        else:
            defender_pos = shooter_pos

        # --- Step 5: Lookup player objects
        shooter = off_lineup.get(shooter_pos) if shooter_pos else off_lineup["PG"]  # Fallback to PG
        screener = off_lineup.get(screener_pos) if screener_pos else off_lineup["PF"]  # Fallback to PF
        passer = off_lineup.get(passer_pos)
        defender = def_lineup.get(defender_pos) if defender_pos else def_lineup["PG"]

        # Debug: Print role assignments
        print(f"🎭 ROLES DEBUG: shooter_pos={shooter_pos}, shooter={get_name_safe(shooter)}, shooter_position={get_player_position(off_lineup, shooter)}")

        return {
            "shooter": shooter,
            "screener": screener,
            "ball_handler": shooter,
            "passer": passer,
            "defender": defender,
            "steps": steps,
            "action_timeline": action_timeline,
            "touch_counts": touch_counts,
            "ball_owner_by_step": derived_roles["ball_owner_by_step"],
            "ball_handler_coords_by_step": derived_roles["ball_handler_coords_by_step"]
        }
    
    # def assign_roles(self):
        
    #     off_team = self.game.offense_team
    #     def_team = self.game.defense_team
    #     off_lineup = self.game.offense_team.lineup
    #     def_lineup = self.game.defense_team.lineup
    #     playcall = self.game.game_state["current_playcall"]
    #     # print(f"playcall: {playcall}")

    #     # Compute shot weights using attributes embedded in each player object
    #     weights_dict = PLAYCALL_ATTRIBUTE_WEIGHTS.get("Attack" if playcall == "Set" else playcall, {})
    #     # print(f"weights_dict: {weights_dict}")

    #     # for pos, player in off_lineup.items():
    #     #     print(f"{pos}: {player.attributes}")
        
    #     shot_weights = {
    #         pos: sum(
    #             off_lineup[pos].attributes[attr] * weight
    #             for attr, weight in weights_dict.items()
    #         )
    #         for pos in off_lineup
    #     }
    #     # print(f"shot_weights: {shot_weights}")
    #     shooter_pos = weighted_random_from_dict(shot_weights)

    #     # Compute screener weights (excluding the shooter)
    #     screen_weights = {
    #         pos: (
    #             off_lineup[pos].attributes["ST"] * 6 +
    #             off_lineup[pos].attributes["AG"] * 2 +
    #             off_lineup[pos].attributes["IQ"] * 1 +
    #             off_lineup[pos].attributes["CH"] * 1
    #         )
    #         for pos in off_lineup if pos != shooter_pos
    #     }

    #     screener_pos = max(screen_weights, key=screen_weights.get)
    #     if screener_pos == shooter_pos:
    #         screener_pos = ""

    #     # Pass chain and passer
    #     pass_chain = generate_pass_chain(self.game, shooter_pos)

    #     passer_pos = pass_chain[-2] if len(pass_chain) >= 2 else ""
    #     if passer_pos == shooter_pos or passer_pos == screener_pos:
    #         passer_pos = ""

    #     if self.game.game_state["defense_playcall"] == "Zone":
    #         defender_pos = random.choice(POSITION_LIST)
    #     else:
    #         defender_pos = shooter_pos

    #     shooter = self.game.offense_team.lineup[shooter_pos]
    #     screener = self.game.offense_team.lineup[screener_pos]
    #     passer = self.game.offense_team.lineup[passer_pos] if passer_pos else None
    #     defender = self.game.defense_team.lineup[defender_pos]

        
    #     return {
    #         "shooter": shooter,
    #         "screener": screener,
    #         "ball_handler": shooter,
    #         "passer": passer,
    #         "pass_chain": pass_chain,
    #         "defender": defender
    #     }
    
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
            defender = def_lineup.get(def_pos) if defense_call != "Zone" else random.choice(list(def_lineup.values()))
            def_attr = defender.attributes
            pressure = (
                def_attr["OD"] * 0.3 +
                def_attr["AG"] * 0.3 +
                def_attr["IQ"] * 0.2 +
                def_attr["CH"] * 0.2
            ) * random.randint(1, 6)
            if defense_call == "Zone":
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
                defender = def_lineup[pos] if defense_call != "Zone" else random.choice(list(def_lineup.values()))
                o_attr = offender.attributes
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
        """
        def_team = self.game.defense_team
        
        # Ensure strategy_settings is initialized
        if not hasattr(def_team, 'strategy_settings') or not def_team.strategy_settings:
            def_team.strategy_settings = def_team._init_strategy_settings()
        
        # Get strategy settings
        hct_value = def_team.strategy_settings.get("hc_trap", 0)
        fcp_value = def_team.strategy_settings.get("fc_press", 0)
        
        # print(f"🛡️ DEFENSIVE PRESSURE: {def_team.name} - HCT={hct_value}, FCP={fcp_value}")
        
        # print(f"🛡️ Defense pressure check - {def_team.name}: HCT={hct_value}, FCP={fcp_value}")
        
        # If both are 0, default to HCO
        if hct_value == 0 and fcp_value == 0:
            return "HCO"
        
        # Remove any strategy with value 0 from consideration
        strategies = {"HCO": 8}
        hco_removed = False
        
        if hct_value > 0:
            strategies["HCT"] = hct_value
            if hct_value == 4:
                strategies.pop("HCO", None)  # Remove HCO entirely, don't set to 0
                hco_removed = True
            elif not hco_removed:
                strategies["HCO"] = max(0, strategies["HCO"] - hct_value)
        
        if fcp_value > 0:
            strategies["FCP"] = fcp_value
            if fcp_value == 4:
                strategies.pop("HCO", None)  # Remove HCO entirely, don't set to 0
                hco_removed = True
            elif not hco_removed:
                strategies["HCO"] = max(0, strategies.get("HCO", 8) - fcp_value)
        
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

