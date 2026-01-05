from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.models.team_manager import TeamManager

from BackEnd.constants import POSITION_LIST, PLAYCALLS, BOX_SCORE_KEYS
from copy import deepcopy
import random

from BackEnd.utils.stat_updater import update_game_stats
from BackEnd.utils.transition_validator import validate_transition, get_turn_type_from_offensive_state
from BackEnd.utils.transition_event_detector import detect_instigating_event, validate_event_matches_transition
from BackEnd.utils.transition_registry import TurnType
import logging

class GameManager:
    def __init__(self, home_team_name, away_team_name, home_strategy_settings=None, away_strategy_settings=None, home_team_attributes=None, away_team_attributes=None, home_scouting_data=None, away_scouting_data=None, home_plays_data=None, away_plays_data=None, home_strategy_calls=None, away_strategy_calls=None, mode="single", user_team_side=None):
        # ✅ SS&S: Set is_user_team flag based on user_team_side
        is_home_user = user_team_side == "home"
        is_away_user = user_team_side == "away"
        
        self.home_team = TeamManager(home_team_name, is_home_team=True, strategy_settings=home_strategy_settings, team_attributes=home_team_attributes, scouting_data=home_scouting_data, plays_data=home_plays_data, strategy_calls=home_strategy_calls, mode=mode, is_user_team=is_home_user)
        self.away_team = TeamManager(away_team_name, is_home_team=False, strategy_settings=away_strategy_settings, team_attributes=away_team_attributes, scouting_data=away_scouting_data, plays_data=away_plays_data, strategy_calls=away_strategy_calls, mode=mode, is_user_team=is_away_user)

        # ✅ Initialize tempo randomly per game (not per team)
        # Tempo is used for time_elapsed calculations, not fast break logic
        tempo_value = TeamManager.init_tempo_random()
        if "tempo" not in self.home_team.strategy_settings:
            self.home_team.strategy_settings["tempo"] = tempo_value
        if "tempo" not in self.away_team.strategy_settings:
            self.away_team.strategy_settings["tempo"] = tempo_value

        # Recalculate position ratings for all players (attributes may have changed)
        self._update_position_ratings()

        self.score = {home_team_name: 0, away_team_name: 0}
        self.quarter = 1
        self.turns = []
        self.text_log = []
        
        # Set default offense/defense teams (will be updated by opening tip)
        self.offense_team = self.home_team
        self.defense_team = self.away_team

        self.game_state = self._init_game_state()
        
        # ✅ SS&S: Store user_team_side in game_state for persistent override checking
        # This is more reliable than is_user_team flag which isn't persisted to DB
        if user_team_side:
            self.game_state["user_team_side"] = user_team_side
            import logging
            logging.warning(f"✅ [GAME MANAGER] Set user_team_side in game_state: {user_team_side}")
            logging.warning(f"   - Home team: {self.home_team.name} (team_id: {self.home_team.team_id}, is_home_team: {self.home_team.is_home_team})")
            logging.warning(f"   - Away team: {self.away_team.name} (team_id: {self.away_team.team_id}, is_home_team: {self.away_team.is_home_team})")
        else:
            import logging
            logging.warning(f"⚠️ [GAME MANAGER] No user_team_side provided - override checking will not work!")

        self.turn_manager = TurnManager(self)
        self.shot_manager = ShotManager(self)

        # Add counters for function calls
        self.macro_turn_count = 0
        self.micro_turn_count = 0

        # optional database identifier for live games
        self.game_id: str | None = None

    def _update_position_ratings(self):
        """Recalculate position ratings for all players based on current attributes.
        
        Uses bulk write operations to batch all database updates into a single call,
        reducing network overhead by ~90% for games with 10+ players.
        """
        from BackEnd.utils.position_ratings import compute_position_ratings
        from BackEnd.db import players_collection
        from pymongo.operations import UpdateOne
        
        # Collect all updates first
        bulk_operations = []
        
        for team in [self.home_team, self.away_team]:
            for player in team.get_all_players():
                # Convert player object to dict for rating calculation
                player_dict = {
                    "attributes": player.attributes,
                    "height": player.height,
                    "name": player.name
                }
                
                # Recalculate ratings
                new_ratings = compute_position_ratings(player_dict)
                
                # Update player object
                player.ratings = new_ratings
                
                # Queue database update for bulk operation
                if hasattr(player, 'player_id') and player.player_id:
                    bulk_operations.append(
                        UpdateOne(
                            {"_id": player.player_id},
                            {"$set": {"position_ratings": new_ratings}}
                        )
                    )
        
        # Execute all updates in a single bulk write operation
        if bulk_operations:
            players_collection.bulk_write(bulk_operations, ordered=False)
    
    def setup_opening_tip(self):
        """Execute opening tip logic and update offense/defense teams."""
        from BackEnd.utils.opening_tip import execute_opening_tip
        
        offense_team, defense_team, turn_result = execute_opening_tip(self)
        
        # Update offense/defense teams
        self.offense_team = offense_team
        self.defense_team = defense_team
        
        # Update game_state to reflect the correct teams
        self.game_state["offense_team"] = offense_team.name
        self.game_state["defense_team"] = defense_team.name
        
        print(f"Opening tip winner: {offense_team.name}")
        logging.warning(f"🏀 [OPENING TIP] Winner: {offense_team.name}, offense_team_id={offense_team.team_id}, defense_team={defense_team.name}")

    
    def _init_game_state(self):
        import random
        return {
            "offense_team": self.offense_team.name,
            "defense_team": self.defense_team.name,
            "score": self.score,
            "points_by_quarter": {
                self.home_team.name: self.home_team.points_by_quarter,
                self.away_team.name: self.away_team.points_by_quarter
            },
            "quarter": self.quarter,
            "time_remaining": 480,
            "clock": "8:00",
            "time_elapsed": 0,
            "turns": self.turns,
            "current_playcall": "Outside",
            "defense_playcall": "Zone",
            "offensive_state": "HCO",
            "team_fouls": {
                self.home_team.name: 0,
                self.away_team.name: 0,
            },
            "team_timeouts": {
                self.home_team.name: 5,
                self.away_team.name: 5,
            },
            "box_score": {
                self.home_team.name: {},
                self.away_team.name: {}
            },
            "shooter": None,
            "free_throws": 0,
            "free_throws_remaining": 0,
            "one_and_one": False,
            "last_ball_handler": None,
            "foul_team": None,
            "foul_type": None,
            "foul_player": None,
            "last_ball_handler": None,
            "last_rebounder": None,
            "last_rebound": None,
            "last_stealer": None,
            "last_turnover_player": None,
            "ineligible_players": []  # Track players with 5+ fouls (fouled out)
        }


    def call_timeout(self, calling_team, timeout_reason="USER", rebuild_both_lineups=False, game_id=None):
        """
        Unified timeout creation method used by both user and computer timeouts.
        This ensures consistent behavior and state management.
        
        Args:
            calling_team: TeamManager instance for the team calling timeout
            timeout_reason: "USER", "COMPUTER", or "FOUL_OUT"
            rebuild_both_lineups: If True, rebuild both team lineups (for computer timeouts during simmed quarters)
            game_id: Optional game_id for database save (if None, skips save)
        
        Returns:
            dict: Timeout turn payload
        """
        # Check if team has timeouts remaining (skip for FOUL_OUT)
        if timeout_reason != "FOUL_OUT":
            if not self.turn_manager.can_call_timeout(calling_team):
                logging.warning(f"⏸️ TIMEOUT: {calling_team.name} cannot call timeout (no timeouts remaining)")
                return None
        
        # Create timeout turn
        timeout_turn = self.turn_manager.setup_timeout_turn(
            timeout_reason=timeout_reason,
            calling_team=calling_team
        )
        
        # Store next_play_type and offense_team_id for resume
        self.game_state["timeout_next_play_type"] = timeout_turn.get("next_play_type", "SIDE_INBOUND")
        self.game_state["timeout_offense_team_id"] = self.offense_team.team_id
        logging.info(f"✅ TIMEOUT: Stored next_play_type '{self.game_state['timeout_next_play_type']}' and offense_team_id '{self.offense_team.team_id}' for resume")
        
        # Rebuild lineups
        from BackEnd.utils.db_utils import build_lineup_from_mongo
        try:
            if rebuild_both_lineups:
                # Computer timeout during simmed quarters: rebuild both teams
                calling_team.lineup = build_lineup_from_mongo(calling_team, self.game_state)
                other_team = self.away_team if calling_team == self.home_team else self.home_team
                other_team.lineup = build_lineup_from_mongo(other_team, self.game_state)
                logging.info(f"✅ TIMEOUT: Rebuilt both team lineups ({calling_team.name} and {other_team.name})")
            elif timeout_reason == "USER":
                # User timeout: rebuild computer team only
                computer_team = self.away_team if not self.away_team.is_user_team else self.home_team
                if not computer_team.is_user_team:
                    computer_team.lineup = build_lineup_from_mongo(computer_team, self.game_state)
                    logging.info(f"✅ TIMEOUT: Rebuilt computer team ({computer_team.name}) lineup")
        except Exception as e:
            logging.error(f"⚠️ TIMEOUT: Failed to rebuild lineups: {e}")
            # Don't fail the timeout if lineup rebuild fails
        
        # ✅ TIMEOUT ENERGY RECHARGE: All players get random recharge at start of timeout
        # This happens before lineup selection screen, so user sees updated energy values
        import random
        timeout_recharge_amounts = [0.03, 0.04, 0.05, 0.06]
        
        # 🔍 DEBUG: Log NG values BEFORE timeout recharge for user team
        user_team = self.home_team if self.home_team.is_user_team else self.away_team
        logging.info(f"🔍 [TIMEOUT BEFORE RECHARGE] User team ({user_team.name}) NG values:")
        for player in user_team.get_all_players():
            ng = player.attributes.get("NG", 1.0)
            in_lineup = player.player_id in [p.player_id for p in user_team.lineup.values() if p]
            lineup_status = "LINEUP" if in_lineup else "BENCH"
            logging.info(f"   {lineup_status}: {player.name} (ID: {player.player_id[:8]}): NG = {ng}")
        
        for team in [self.home_team, self.away_team]:
            for player in team.get_all_players():
                recharge_amount = random.choice(timeout_recharge_amounts)
                if hasattr(player, "recharge_energy"):
                    old_ng = player.attributes.get("NG", 1.0)
                    player.recharge_energy(recharge_amount)
                    new_ng = player.attributes.get("NG", 1.0)
                    if team.is_user_team:
                        in_lineup = player.player_id in [p.player_id for p in team.lineup.values() if p]
                        lineup_status = "LINEUP" if in_lineup else "BENCH"
                        logging.info(f"   {lineup_status}: {player.name}: NG {old_ng:.3f} + {recharge_amount:.3f} → {new_ng:.3f}")
        
        # 🔍 DEBUG: Log NG values AFTER timeout recharge for user team
        logging.info(f"🔍 [TIMEOUT AFTER RECHARGE] User team ({user_team.name}) NG values:")
        for player in user_team.get_all_players():
            ng = player.attributes.get("NG", 1.0)
            in_lineup = player.player_id in [p.player_id for p in user_team.lineup.values() if p]
            lineup_status = "LINEUP" if in_lineup else "BENCH"
            logging.info(f"   {lineup_status}: {player.name} (ID: {player.player_id[:8]}): NG = {ng}")
        
        # Append timeout turn to turns list
        self.turns.append(timeout_turn)
        self.text_log.append(timeout_turn["text"])
        
        # Set timeout_called flag (for simulation loop stopping)
        self.game_state["timeout_called"] = True
        
        # Save game state to database if game_id provided
        # Note: Database save is handled by the API endpoint to avoid circular imports
        # This method just sets up the timeout turn and state
        
        # logging.warning(f"⏸️ TIMEOUT: {calling_team.name} called timeout (reason: {timeout_reason}, turn {len(self.turns)})")
        return timeout_turn

    def simulate_macro_turn(self): #run_simulation
        # Clear timeout flag at start of each turn (will be set if timeout is called)
        self.game_state["timeout_called"] = False
        
        # Increment macro turn counter
        self.macro_turn_count += 1
        
        # Track previous turn result for transition validation
        # Get the last turn result (before this turn executes)
        previous_result = self.turns[-1] if self.turns else None
        previous_offensive_state = self.game_state.get("_previous_offensive_state")
        
        # print("Starting new turn")
        # print(f"offense_team: {self.offense_team}")
        result = self.turn_manager.run_micro_turn()
        
        # ✅ SS&S: Centralized next_turn determination (single source of truth)
        # Sets explicit next_turn based on result and conditions
        # This ensures ALL turns have accurate next_turn (no None values)
        result["next_turn"] = self.determine_next_turn(result)
        
        self.turns.append(result)
        self.text_log.append(result["text"])

        # If the turn ended with an offensive rebound, create a separate OREB turn
        # Process ALL consecutive OREBs in this same call (for batch efficiency)
        while self.game_state.get("pending_oreb"):
            # print(f"📦 OREB detected - creating separate OREB turn")
            
            oreb_turn = self.turn_manager.resolve_offensive_rebound_turn()
            if oreb_turn:
                # print(f"📦 OREB turn created: {oreb_turn.get('result_type')} - {oreb_turn.get('text')}")
                
                # ✅ SS&S: Set next_turn for OREB turns (same centralized logic)
                oreb_turn["next_turn"] = self.determine_next_turn(oreb_turn)
                
                self.turns.append(oreb_turn)
                self.text_log.append(oreb_turn["text"])
                
                # Handle possession flip for OREB turn (doesn't go through run_micro_turn)
                if oreb_turn.get("possession_flips"):
                    # print(f"📦 OREB turn flipping possession")
                    old_offense = self.offense_team.name
                    self.switch_possession()
                    oreb_turn["possession_flips"] = False  # ✅ Clear flag to prevent double flip
                    # logging.warning(f"🔄 [OREB] Flipped possession after putback: {old_offense} → {self.offense_team.name}")
                
                # If the OREB turn resulted in another OREB, resolve_offensive_rebound_turn
                # will have set pending_oreb again. The while loop will process it.
                # This allows consecutive OREBs (miss → OREB → miss → OREB → ...)
                # to all be batched in one API call for better performance.
            else:
                print(f"⚠️ OREB turn returned None!")
                # Clear pending if processing failed to prevent infinite loop
                self.game_state["pending_oreb"] = None
                break

        # ✅ FIX 3: Backend flip for DREB → HCO (Pattern B)
        # Handle possession flips for DREB transitions that go directly to HCO (not through inbound)
        # This includes: MISS with DREB → HCO, STEAL → HCO (direct, not via Fast Break)
        # ✅ SS&S FIX: Only flip if possession_flips is True (prevents double flip for Fast Break → HCO)
        # Fast Break defensive stop sets possession_flips: False, so it won't trigger this flip
        if result.get("next_play_type") == "HCO" and result.get("possession_flips") is True:
            old_offense = self.offense_team.name
            self.switch_possession()
            result["possession_flips"] = False
            # ✅ CRITICAL FIX: Update offense_team_id AFTER flip (was set to old team in turn_manager)
            result["offense_team_id"] = self.offense_team.team_id
            logging.debug(f"🔄 [DREB→HCO] Flipped possession before HCO: {old_offense} → {self.offense_team.name}, updated offense_team_id={result['offense_team_id']}")

        # ✅ FIX 4: Backend flip for DREB → Fast Break (Pattern C)
        # Handle possession flips for DREB transitions that go to Fast Break
        # This includes: MISS with DREB → Fast Break, STEAL → Fast Break
        if result.get("next_play_type") == "FAST_BREAK" and result.get("possession_flips"):
            old_offense = self.offense_team.name
            self.switch_possession()
            result["possession_flips"] = False
            # ✅ CRITICAL FIX: Update offense_team_id AFTER flip (was set to old team in turn_manager)
            result["offense_team_id"] = self.offense_team.team_id
            logging.debug(f"🔄 [DREB→FB] Flipped possession before Fast Break: {old_offense} → {self.offense_team.name}, updated offense_team_id={result['offense_team_id']}")

        # ✅ TIMEOUT: Check for foul out and create timeout turn
        if result.get("fouled_out"):
            foul_out_player_data = result.get("foul_out_player", {})
            # Find the actual player object
            foul_out_player = None
            foul_out_player_id = foul_out_player_data.get("player_id") if isinstance(foul_out_player_data, dict) else None
            if foul_out_player_id:
                for team in [self.home_team, self.away_team]:
                    # Try get_all_players() first (returns all roster players)
                    players = team.get_all_players() if hasattr(team, 'get_all_players') else []
                    for player in players:
                        if hasattr(player, 'player_id') and player.player_id == foul_out_player_id:
                            foul_out_player = player
                            break
                    if foul_out_player:
                        break
                    # Fallback: check lineup players
                    if not foul_out_player:
                        for player in team.lineup.values():
                            if player and hasattr(player, 'player_id') and player.player_id == foul_out_player_id:
                                foul_out_player = player
                                break
                    if foul_out_player:
                        break
            
            # ✅ FOUL OUT: Store offense team for debugging (game.offense_team is source of truth)
            # Possession has already been flipped by foul resolution if needed (offensive fouls)
            self.game_state["timeout_offense_team_id"] = self.offense_team.team_id
            logging.info(f"✅ FOUL OUT: Current offense team '{self.offense_team.name}' (team_id: {self.offense_team.team_id})")
            
            # Get foul context if available (set by foul resolution)
            foul_out_context = self.game_state.get("foul_out_context", {})
            if foul_out_context:
                logging.info(f"✅ FOUL OUT: Using foul context - type={foul_out_context.get('foul_type')}, next={foul_out_context.get('next_play_type')}")
            
            # Create timeout turn
            timeout_turn = self.turn_manager.setup_timeout_turn(
                timeout_reason="FOUL_OUT",
                calling_team=None,
                foul_out_player=foul_out_player,
                foul_out_context=foul_out_context  # ✅ NEW: Pass foul context
            )
            self.turns.append(timeout_turn)
            self.text_log.append(timeout_turn["text"])
            logging.info(f"⏸️ TIMEOUT: Created timeout turn for foul out - {foul_out_player_data.get('name', 'Unknown')}")
            
            # ✅ FOUL OUT TIMEOUT: Save game state to database immediately (same pattern as user-initiated timeout)
            # This ensures timeout state persists even if user navigates away before simulate-turn saves
            if self.game_id:
                try:
                    from BackEnd.utils.shared import summarize_game_state
                    from BackEnd.db import games_collection
                    db_summary = summarize_game_state(self, exclude_animations=True)
                    games_collection.update_one({"_id": self.game_id}, {"$set": db_summary}, upsert=True)
                    logging.info(
                        f"💾 FOUL OUT TIMEOUT: Saved game state immediately: "
                        f"game_id={self.game_id}, quarter={db_summary.get('quarter')}, "
                        f"clock={db_summary.get('clock')}, next_play_type={timeout_turn.get('next_play_type')}"
                    )
                except Exception as e:
                    logging.error(f"🚨 FOUL OUT TIMEOUT: Failed to save game state: {e}")
                    # Don't fail the foul out if save fails - game continues normally

        # If the turn ended with a dead-ball turnover or a non-shooting foul
        # that does not result in free throws, prepare a sideline inbound
        # sequence and append its payload so the front end can animate it.
        if (
            (result.get("result_type") == "FOUL" and self.game_state.get("free_throws_remaining", 0) == 0)
            or result.get("result_type") == "DEAD BALL"
        ):
            # ✅ FIX: Flip possession BEFORE setup_side_inbound so correct team inbounds
            # Dead ball turnovers and offensive fouls always flip possession
            # logging.warning(f"🔍 [SIP SETUP] Checking possession flip: result_type={result.get('result_type')}, possession_flips={result.get('possession_flips')}, current_turn={result.get('current_turn')}, current_offense={self.offense_team.name}")
            if result.get("possession_flips"):
                old_offense = self.offense_team.name
                self.switch_possession()
                # ✅ FIX: Clear possession_flips flag after flipping to prevent frontend double flip
                result["possession_flips"] = False
                # logging.warning(f"🔄 [SIP] Flipped possession before SIP: {old_offense} → {self.offense_team.name}, set possession_flips=False")
            # else:
            #     logging.warning(f"⏭️ [SIP] No possession flip needed (possession_flips={result.get('possession_flips')})")
            
            inbound_payload = self.turn_manager.setup_side_inbound()
            # logging.warning(f"✅ [SIP CREATE] Created SIDE_INBOUND, offense_team={inbound_payload.get('offense_team_id')}, result_was={result.get('current_turn')} {result.get('result_type')}")
            
            # ✅ COMPUTER TIMEOUT: Check if any computer team should call timeout
            # Check both teams if both are computer teams, otherwise check the non-user team
            computer_teams_to_check = []
            if not self.home_team.is_user_team:
                computer_teams_to_check.append(self.home_team)
            if not self.away_team.is_user_team:
                computer_teams_to_check.append(self.away_team)
            
            calling_team = None
            for computer_team in computer_teams_to_check:
                if self.turn_manager.should_computer_call_timeout(computer_team, "SIDE_INBOUND"):
                    calling_team = computer_team
                    break  # First team to call timeout wins
            
            if calling_team:
                # Increment computer timeout count for this quarter
                if "computer_timeouts" not in self.game_state:
                    self.game_state["computer_timeouts"] = {}
                if calling_team.name not in self.game_state["computer_timeouts"]:
                    self.game_state["computer_timeouts"][calling_team.name] = {}
                quarter = self.quarter
                if quarter not in self.game_state["computer_timeouts"][calling_team.name]:
                    self.game_state["computer_timeouts"][calling_team.name][quarter] = {"count": 0, "checked_conditions": set()}
                self.game_state["computer_timeouts"][calling_team.name][quarter]["count"] += 1
                
                # ✅ FULL SIMULATION: Immediately create timeout and rebuild lineups
                # ✅ TURN-BY-TURN: Defer timeout creation for animation
                is_full_simulation = self.game_state.get("_is_full_simulation", False)
                
                if is_full_simulation:
                    # Full simulation mode: Create timeout immediately and rebuild lineups
                    # logging.warning(f"⏸️ COMPUTER TIMEOUT: {calling_team.name} calling timeout immediately (full simulation mode)")
                    timeout_turn = self.call_timeout(
                        calling_team=calling_team,
                        timeout_reason="COMPUTER",
                        rebuild_both_lineups=True,
                        game_id=self.game_id  # Pass game_id if available
                    )
                    if timeout_turn:
                        logging.info(f"✅ COMPUTER TIMEOUT: Created timeout turn and rebuilt lineups for {calling_team.name}")
                        # Clear timeout_called flag so simulation continues normally
                        # The timeout turn is just one turn - simulation should continue
                        self.game_state["timeout_called"] = False
                    # Don't append SIP turn - timeout turn was created instead
                    return
                else:
                    # Turn-by-turn mode: Store pending timeout for deferred creation (after animation)
                    self.game_state["pending_computer_timeout"] = {
                        "calling_team": calling_team,
                        "turn_type": "SIDE_INBOUND",
                        "timeout_reason": "COMPUTER"
                    }
                    logging.warning(f"⏸️ COMPUTER TIMEOUT: {calling_team.name} will call timeout on next turn (deferred for animation)")
                    # Don't append SIP turn - timeout will be created instead on next API call
                    return
            else:
                # No computer timeout - proceed with SIP
                self.turns.append(inbound_payload)
            
            # Reset offensive state to HCO after side inbound (FCP/HCT only apply after made shots)
            self.game_state["offensive_state"] = "HCO"

        # ✅ FIX 2: Backend flip for Made Shots → Inbound (Pattern A)
        # Create BASELINE_INBOUND turns for ALL made shots (HCO, FT, FB, FCP/HCT, OREB)
        # Check LAST turn (handles OREB putbacks which append in while loop above)
        # ✅ TIMEOUT: Skip BIP creation if timeout was just called (full sim) or pending (turn-by-turn)
        if self.game_state.get("timeout_called") or self.game_state.get("pending_computer_timeout"):
            if self.game_state.get("timeout_called"):
                logging.debug(f"⏸️ COMPUTER TIMEOUT: Skipping BIP creation - timeout was just called (full simulation)")
            else:
                logging.debug(f"⏸️ COMPUTER TIMEOUT: Skipping BIP creation - pending timeout exists (turn-by-turn)")
            return
        
        last_turn = self.turns[-1] if self.turns else None
        if last_turn and last_turn.get("next_play_type") == "BASELINE_INBOUND":
            # ✅ Flip possession BEFORE creating BASELINE_INBOUND (gold standard pattern)
            if last_turn.get("possession_flips"):
                old_offense = self.offense_team.name
                self.switch_possession()
                last_turn["possession_flips"] = False  # Clear flag
                # logging.warning(f"🔄 [MAKE→BIP] Flipped possession before BASELINE_INBOUND: {old_offense} → {self.offense_team.name}")
            
            # Get next_defensive_setup from the made shot turn
            next_defensive_setup = last_turn.get("next_defensive_setup")
            # logging.warning(f"✅ [BIP CREATE] Creating BASELINE_INBOUND, next_defensive_setup={next_defensive_setup}, offense_team={self.offense_team.name}")
            
            inbound_payload = self.turn_manager.setup_baseline_inbound(next_defensive_setup=next_defensive_setup)
            
            # ✅ COMPUTER TIMEOUT: Check if any computer team should call timeout
            # Check both teams if both are computer teams, otherwise check the non-user team
            computer_teams_to_check = []
            if not self.home_team.is_user_team:
                computer_teams_to_check.append(self.home_team)
            if not self.away_team.is_user_team:
                computer_teams_to_check.append(self.away_team)
            
            calling_team = None
            for computer_team in computer_teams_to_check:
                if self.turn_manager.should_computer_call_timeout(computer_team, "BASELINE_INBOUND"):
                    calling_team = computer_team
                    break  # First team to call timeout wins
            
            if calling_team:
                # Increment computer timeout count for this quarter
                if "computer_timeouts" not in self.game_state:
                    self.game_state["computer_timeouts"] = {}
                if calling_team.name not in self.game_state["computer_timeouts"]:
                    self.game_state["computer_timeouts"][calling_team.name] = {}
                quarter = self.quarter
                if quarter not in self.game_state["computer_timeouts"][calling_team.name]:
                    self.game_state["computer_timeouts"][calling_team.name][quarter] = {"count": 0, "checked_conditions": set()}
                self.game_state["computer_timeouts"][calling_team.name][quarter]["count"] += 1
                
                # ✅ FULL SIMULATION: Immediately create timeout and rebuild lineups
                # ✅ TURN-BY-TURN: Defer timeout creation for animation
                is_full_simulation = self.game_state.get("_is_full_simulation", False)
                
                if is_full_simulation:
                    # Full simulation mode: Create timeout immediately and rebuild lineups
                    # logging.warning(f"⏸️ COMPUTER TIMEOUT: {calling_team.name} calling timeout immediately (full simulation mode)")
                    timeout_turn = self.call_timeout(
                        calling_team=calling_team,
                        timeout_reason="COMPUTER",
                        rebuild_both_lineups=True,
                        game_id=self.game_id  # Pass game_id if available
                    )
                    if timeout_turn:
                        logging.info(f"✅ COMPUTER TIMEOUT: Created timeout turn and rebuilt lineups for {calling_team.name}")
                        # Clear timeout_called flag so simulation continues normally
                        # The timeout turn is just one turn - simulation should continue
                        self.game_state["timeout_called"] = False
                    # Don't append BIP turn - timeout turn was created instead
                    return
                else:
                    # Turn-by-turn mode: Store pending timeout for deferred creation (after animation)
                    self.game_state["pending_computer_timeout"] = {
                        "calling_team": calling_team,
                        "turn_type": "BASELINE_INBOUND",
                        "timeout_reason": "COMPUTER"
                    }
                    logging.debug(f"⏸️ COMPUTER TIMEOUT: {calling_team.name} will call timeout on next turn (deferred for animation)")
                    # Don't append BIP turn - timeout will be created instead on next API call
                    return
            else:
                # No computer timeout - proceed with BIP
                self.turns.append(inbound_payload)
                self.text_log.append("Baseline inbound after made shot")
            
            # Preserve offensive_state for next API call
            if next_defensive_setup:
                self.game_state["offensive_state"] = next_defensive_setup
            self.text_log.append("Baseline inbound after made shot")
            
            # ✅ CRITICAL: Preserve offensive_state for the next API call
            # After BASELINE_INBOUND, preserve offensive_state for all pressure types (FCP, HCT, or HCO)
            # This ensures consistency across all three cases:
            # - FCP: Next API call generates FCP setup turn (FOUL/HCO/TURNOVER)
            # - HCT: Next API call generates HCT setup turn (FOUL/HCO/TURNOVER)
            # - HCO: Next API call generates regular HCO turn (no pressure)
            # This matches the pattern used in OREB putback and Free Throw flows
            if next_defensive_setup:
                self.game_state["offensive_state"] = next_defensive_setup

        # Update team stats after each turn
        self.update_team_stats()

        # ✅ TRANSITION VALIDATION: Validate the transition from previous turn to current turn
        # This is non-blocking - just logs warnings for debugging
        # Note: We validate the transition from the PREVIOUS turn to THIS turn's outcome
        # (not from batched turns like OREBs/inbounds, which are part of the same sequence)
        if previous_result and len(self.turns) > 1:
            # Use the result from BEFORE this turn started (the actual previous turn)
            from_result = previous_result
            
            # Get the offensive_state that was set for the NEXT turn (after this turn completes)
            to_offensive_state = self.game_state.get("offensive_state", "HCO")
            
            # Determine if possession changed in THIS turn
            # (not counting batched turns, as those are part of the same sequence)
            possession_changed = result.get("possession_flips", False)
            
            # Validate the transition
            is_valid, error_msg = validate_transition(
                from_result=from_result,
                to_offensive_state=to_offensive_state,
                possession_changed=possession_changed,
                game_state=self.game_state
            )
            
            if not is_valid and error_msg:
                # Use len(turns) to match frontend turnCount (turn has already been added at this point)
                turn_num = len(self.turns)
                # logging.warning(
                #     f"⚠️ [TRANSITION VALIDATION] Invalid transition detected in turn #{turn_num}: {error_msg}",
                #     extra={
                #         "turn_number": turn_num,
                #         "from_result_type": from_result.get("result_type"),
                #         "from_result_text": from_result.get("text", "")[:50],
                #         "to_offensive_state": to_offensive_state,
                #         "possession_changed": possession_changed,
                #         "previous_offensive_state": previous_offensive_state,
                #         "current_result_type": result.get("result_type"),
                #     }
                # )
            
            # ✅ OPTIONAL: Enhanced event detection and validation
            # This provides additional observability but is not required for game functionality
            try:
                # Detect the instigating event
                detected_event = detect_instigating_event(
                    result=result,
                    game_state=self.game_state,
                    previous_offensive_state=previous_offensive_state
                )
                
                # If we can determine turn types, validate the event matches the transition
                from_turn_type = None
                if from_result.get("result_type") in ["BASELINE_INBOUND", "SIDE_INBOUND"]:
                    from_turn_type = TurnType.INBOUND_PASS if from_result.get("result_type") == "BASELINE_INBOUND" else TurnType.SIDE_INBOUND_PASS
                elif from_result.get("result_type") in ["PUTBACK_MAKE", "PUTBACK_MISS", "KICKOUT"]:
                    from_turn_type = TurnType.OREB
                else:
                    if previous_offensive_state:
                        from_turn_type = get_turn_type_from_offensive_state(previous_offensive_state)
                
                to_turn_type = get_turn_type_from_offensive_state(to_offensive_state)
                
                if from_turn_type and to_turn_type and detected_event:
                    event_valid, event_error = validate_event_matches_transition(
                        detected_event=detected_event,
                        from_turn_type=from_turn_type,
                        to_turn_type=to_turn_type,
                        possession_change=possession_changed
                    )
                    
                    if not event_valid and event_error:
                        # logging.warning(
                        #     f"⚠️ [EVENT VALIDATION] {event_error}",
                        #     extra={
                        #         "turn_number": len(self.turns),
                        #         "detected_event": detected_event,
                        #         "from_turn_type": from_turn_type.value,
                        #         "to_turn_type": to_turn_type.value,
                        #         "possession_change": possession_changed,
                        #     }
                        # )
                        pass  # Event validation logging commented out
                    elif detected_event:
                        # Log successful event detection (info level, not warning)
                        # Use len(turns) to match frontend turnCount (turn has already been added at this point)
                        turn_num = len(self.turns)
                        logging.debug(
                            f"✅ [EVENT DETECTION] Turn #{turn_num}: {detected_event} → {from_turn_type.value} -> {to_turn_type.value}",
                            extra={
                                "turn_number": turn_num,
                                "detected_event": detected_event,
                                "transition": f"{from_turn_type.value} -> {to_turn_type.value}",
                            }
                        )
            except Exception as e:
                # Don't let event detection break the game
                logging.debug(f"Event detection failed (non-critical): {e}")

        # Log steal-to-score sequences if applicable
        self._log_steal_to_points(result)

        # Persist incremental stats for active games
        deltas = result.get("deltas")
        if self.game_id and deltas:
            update_game_stats(self.game_id, deltas, dict(self.score))

        # print("End of simulate_macro_turn")
        # print(f"result: {result}")

        return result

    def determine_next_turn(self, result):
        """
        Centralized function to determine next turn type based on current result.
        Single source of truth for all 51 turn-to-turn transitions.
        
        Uses transition registry from TRANSITION_SYSTEM.md as reference.
        
        Returns: str - Next turn type ("HCO", "BASELINE_INBOUND", "SIDE_INBOUND", etc.)
        """
        current = result.get("current_turn")
        result_type = result.get("result_type")
        
        # OPENING_TIP → HCO (always)
        if current == "OPENING_TIP":
            return "HCO"
        
        # BASELINE_INBOUND → FCP/HCT/HCO (based on next_defensive_setup)
        if current == "BASELINE_INBOUND":
            return result.get("next_defensive_setup", "HCO")
        
        # SIDE_INBOUND → HCO (always)
        if current == "SIDE_INBOUND":
            return "HCO"
        
        # TIMEOUT → SIP/Free Throw/BIP (based on next_play_type in timeout turn)
        if current == "TIMEOUT":
            return result.get("next_play_type", "SIDE_INBOUND")
        
        # HCO, OREB, FAST_BREAK, FCP, HCT → Multiple options based on result_type
        # These already set next_play_type in their handlers, so use that
        if result.get("next_play_type"):
            return result["next_play_type"]
        
        # For results without explicit next_play_type, determine based on result_type and game state:
        
        # Check if offensive_state was set to FREE_THROW (defensive foul in bonus)
        if self.game_state.get("offensive_state") == "FREE_THROW":
            return "FREE_THROW"
        
        # Check for pending OREB (miss with offensive rebound)
        if self.game_state.get("pending_oreb"):
            return "OREB"
        
        # FOUL results (non-shooting or no bonus)
        if result_type == "FOUL":
            # Check if free throws were awarded (shooting foul or bonus)
            if self.game_state.get("free_throws_remaining", 0) > 0:
                return "FREE_THROW"
            else:
                # Non-shooting foul or defensive foul without bonus
                return "SIDE_INBOUND"
        
        # DEAD BALL turnovers → SIDE_INBOUND
        if result_type == "DEAD BALL":
            return "SIDE_INBOUND"
        
        # Default to HCO if no explicit routing
        return "HCO"

    def switch_possession(self):
        self.offense_team, self.defense_team = self.defense_team, self.offense_team
        self.game_state["offense_team"] = self.offense_team.name
        self.game_state["defense_team"] = self.defense_team.name
        self.game_state["current_playcall"] = ""
        self.game_state["defense_playcall"] = ""

    def get_box_score(self):
        """Get box score with all players (lineup + bench) to match team totals."""
        box_score = {}
        for team in [self.home_team, self.away_team]:
            team_box = {}
            # Include all players from roster (not just lineup) to match team_totals calculation
            # First, add lineup players with their positions
            for pos, player in team.lineup.items():
                if player:  # Skip None players
                    team_box[pos] = {
                    "name": player.get_name(),
                        "playerId": player.player_id,
                        "jersey": player.jersey,
                    **player.stats["game"]
                }
            # Then add bench players (players not in current lineup)
            lineup_player_ids = {p.player_id for p in team.lineup.values() if p}
            for player in team.players.values():
                if player.player_id not in lineup_player_ids:
                    # Use player's position attribute or default to bench
                    pos = getattr(player, "position", None) or getattr(player, "pos", None) or "BENCH"
                    # Handle multiple bench players with same position by appending player_id
                    if pos in team_box:
                        pos = f"{pos}_{player.player_id[:8]}"
                    team_box[pos] = {
                        "name": player.get_name(),
                        "playerId": player.player_id,
                        "jersey": player.jersey,
                        **player.stats["game"]
        }
            box_score[team.name] = team_box
        return box_score

    def to_dict(self):
        output = deepcopy(self.game_state)
        flat_box_score = []

        for team in [self.home_team, self.away_team]:
            for player in team.players:
                flat_box_score.append({
                    "team": team.name,
                    "name": player.get_name(),
                    "stats": player.stats["game"]
                })

        output["box_score"] = flat_box_score
        output["team_totals"] = {
            self.home_team.name: self.home_team.get_team_game_stats(),
            self.away_team.name: self.away_team.get_team_game_stats()
        }

        return output

    @property
    def home_team_name(self):
        return self.home_team.name

    @property
    def away_team_name(self):
        return self.away_team.name
    
    @property
    def team_totals(self):
        return {
            self.home_team.name: self.home_team.get_team_game_stats(),
            self.away_team.name: self.away_team.get_team_game_stats()
        }

    def _find_player_by_name(self, name):
        for team in [self.home_team, self.away_team]:
            for player in team.get_all_players():
                if player.get_name() == name:
                    return player
        return None

    def _log_steal_to_points(self, result):
        last_stealer = self.game_state.get("last_stealer")
        points = result.get("points")
        scoring_team = result.get("scoring_team")
        if last_stealer and points and scoring_team == getattr(last_stealer, "team", None):
            scorer = self._find_player_by_name(result.get("shooter"))
            turnover_player = self.game_state.get("last_turnover_player")
            team_tot_after = self.score.get(scoring_team, 0)
            scorer_pts_after = scorer.stats["game"].get("PTS", 0) if scorer else 0
            stealer_stl_after = last_stealer.stats["game"].get("STL", 0)
            to_player_to_after = turnover_player.stats["game"].get("TO", 0) if turnover_player else 0
            log_line = f"{result.get('turn_count')}, {result.get('result_type')}, {getattr(scorer, 'player_id', '')}, {points}, {last_stealer.player_id}, {getattr(turnover_player, 'player_id', '')}, {team_tot_after}, {scorer_pts_after}, {stealer_stl_after}, {to_player_to_after}"
            print(log_line)
            self.game_state["last_stealer"] = None
            self.game_state["last_turnover_player"] = None

    def print_function_counts(self):
        """Print the number of times each function was called."""
        print(f"=== FUNCTION CALL COUNTS ===")
        print(f"simulate_macro_turn() called: {self.macro_turn_count} times")
        print(f"run_micro_turn() called: {self.micro_turn_count} times")
        print(f"Total turns: {len(self.turns)}")
        print(f"=============================")

    def update_team_stats(self):
        """Update team totals based on all rostered players."""
        # Delegate aggregation to each team, which sums over all players
        self.home_team.update_team_stats()
        self.away_team.update_team_stats()
        # ✅ TIMEOUT: Update team timeout counts in game_state
        self.game_state["team_timeouts"] = {
            self.home_team.name: getattr(self.home_team, 'timeouts', 4),
            self.away_team.name: getattr(self.away_team, 'timeouts', 4),
        }

    def print_game_statistics(self):
        """Print all game statistics including defense score stats."""
        # Print function call counts
        self.print_function_counts()
        
        # Print defense score statistics
        self.shot_manager.print_defense_score_stats()





