from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.models.team_manager import TeamManager

from BackEnd.constants import POSITION_LIST, PLAYCALLS, BOX_SCORE_KEYS
from copy import deepcopy
import random

from BackEnd.utils.shared import sync_lineup_coords_from_turn
from BackEnd.utils.position_snapshot_ledger import (
    attach_position_snapshots,
    build_phase_post_stopper_snapshot,
)
from BackEnd.utils.stat_updater import update_game_stats
from BackEnd.utils.transition_validator import validate_transition, get_turn_type_from_offensive_state
from BackEnd.utils.transition_event_detector import detect_instigating_event, validate_event_matches_transition
from BackEnd.utils.transition_registry import TurnType
import logging
import uuid

class GameManager:
    def __init__(self, home_team_name, away_team_name, home_strategy_settings=None, away_strategy_settings=None, home_team_attributes=None, away_team_attributes=None, home_scouting_data=None, away_scouting_data=None, home_plays_data=None, away_plays_data=None, home_strategy_calls=None, away_strategy_calls=None, mode="single", user_team_side=None, franchise_id=None, community_engagement_crowd_shift="none"):
        import time
        # ⏱️ Coarse timers for gm_create breakdown
        _t0 = time.time()
        # ✅ SS&S: Set is_user_team flag based on user_team_side
        is_home_user = user_team_side == "home"
        is_away_user = user_team_side == "away"

        self.home_team = TeamManager(home_team_name, is_home_team=True, strategy_settings=home_strategy_settings, team_attributes=home_team_attributes, scouting_data=home_scouting_data, plays_data=home_plays_data, strategy_calls=home_strategy_calls, mode=mode, is_user_team=is_home_user, franchise_id=franchise_id)
        _home_ms = (time.time() - _t0) * 1000
        _t0 = time.time()
        self.away_team = TeamManager(away_team_name, is_home_team=False, strategy_settings=away_strategy_settings, team_attributes=away_team_attributes, scouting_data=away_scouting_data, plays_data=away_plays_data, strategy_calls=away_strategy_calls, mode=mode, is_user_team=is_away_user, franchise_id=franchise_id)
        _away_ms = (time.time() - _t0) * 1000
        _t0 = time.time()
        # ✅ Initialize tempo randomly per game (not per team)
        # Tempo is used for time_elapsed calculations, not fast break logic
        tempo_value = TeamManager.init_tempo_random()
        if "tempo" not in self.home_team.strategy_settings:
            self.home_team.strategy_settings["tempo"] = tempo_value
        if "tempo" not in self.away_team.strategy_settings:
            self.away_team.strategy_settings["tempo"] = tempo_value

        # Recalculate position ratings for all players (attributes may have changed)
        self._update_position_ratings()
        _ratings_ms = (time.time() - _t0) * 1000
        logging.warning(
            "⏱️ [PERF] gm_create breakdown: home_team=%.0fms away_team=%.0fms update_position_ratings=%.0fms",
            _home_ms, _away_ms, _ratings_ms,
        )

        self.score = {home_team_name: 0, away_team_name: 0}
        self.quarter = 1
        self.turns = []
        self.text_log = []
        
        # Set default offense/defense teams (will be updated by opening tip)
        self.offense_team = self.home_team
        self.defense_team = self.away_team

        self.game_state = self._init_game_state()
        from BackEnd.utils.home_crowd import initialize_home_crowd_in_game_state

        _ce_shift = community_engagement_crowd_shift or "none"
        if _ce_shift not in ("none", "up", "down"):
            _ce_shift = "none"
        initialize_home_crowd_in_game_state(self.game_state, self.home_team, crowd_shift=_ce_shift)

        # ✅ SS&S: Store user_team_side in game_state for persistent override checking
        # This is more reliable than is_user_team flag which isn't persisted to DB
        if user_team_side:
            self.game_state["user_team_side"] = user_team_side
            logging.warning(f"✅ [GAME MANAGER] Set user_team_side in game_state: {user_team_side}")
            # logging.warning(f"   - Home team: {self.home_team.name} (team_id: {self.home_team.team_id}, is_home_team: {self.home_team.is_home_team})")
            # logging.warning(f"   - Away team: {self.away_team.name} (team_id: {self.away_team.team_id}, is_home_team: {self.away_team.is_home_team})")
        else:
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
        In-memory player.ratings are always updated. DB write only in single/tournament
        (franchise uses FPD; do not write to universal players_collection).
        """
        from BackEnd.utils.position_ratings import compute_position_ratings
        from pymongo.operations import UpdateOne

        is_franchise = getattr(self.home_team, "franchise_id", None) or getattr(self.away_team, "franchise_id", None)
        bulk_operations = []

        for team in [self.home_team, self.away_team]:
            for player in team.get_all_players():
                player_dict = {
                    "attributes": player.attributes,
                    "height": player.height,
                    "name": player.name
                }
                new_ratings = compute_position_ratings(player_dict)
                player.ratings = new_ratings
                if not is_franchise and hasattr(player, "player_id") and player.player_id:
                    bulk_operations.append(
                        UpdateOne(
                            {"_id": player.player_id},
                            {"$set": {"position_ratings": new_ratings}}
                        )
                    )

        if bulk_operations:
            from BackEnd.db import players_collection
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
                # IMPORTANT: Do not alias the TeamManager lists directly here.
                # Quarter scoring is incremented in both team.points_by_quarter and the
                # game_state mirror for backward compatibility. If these reference the
                # same list object, points get double-counted.
                self.home_team.name: list(self.home_team.points_by_quarter),
                self.away_team.name: list(self.away_team.points_by_quarter),
            },
            "quarter": self.quarter,
            "time_remaining": 480,
            "clock": "8:00",
            "shot_clock_remaining": 30,
            "time_elapsed": 0,
            "uess_clock_authority_mode": "observe",
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
            "man_defense_matchups": {  # User team matchups when user is on defense (set via popup; resets at each break)
                "PG": "PG",
                "SG": "SG",
                "SF": "SF",
                "PF": "PF",
                "C": "C"
            },
            "man_defense_matchups_computer": {  # Computer team matchups when computer is on defense (default for now; future logic may set)
                "PG": "PG",
                "SG": "SG",
                "SF": "SF",
                "PF": "PF",
                "C": "C"
            },
            "rim_runner_by_team_id": {},  # team_id str -> player_id for designated Rim Runner
        }


    def call_timeout(
        self,
        calling_team,
        timeout_reason="USER",
        rebuild_both_lineups=False,
        game_id=None,
        foul_out_player=None,
        foul_out_context=None,
    ):
        """
        Unified timeout creation method used by both user and computer timeouts.
        This ensures consistent behavior and state management.
        
        Args:
            calling_team: TeamManager instance for the team calling timeout
            timeout_reason: "USER", "COMPUTER", or "FOUL_OUT"
            rebuild_both_lineups: If True, rebuild both team lineups (for computer timeouts during simmed quarters)
            game_id: Optional game_id for database save (if None, skips save)
            foul_out_player: Optional player object for FOUL_OUT timeout payload
            foul_out_context: Optional foul context dict for FOUL_OUT timeout payload
        
        Returns:
            dict: Timeout turn payload
        """
        # ✅ MAN DEFENSE MATCHUPS: Reset to defaults at start of timeout break
        from BackEnd.utils.man_defense_matchups import reset_matchups_to_defaults
        reset_matchups_to_defaults(self.game_state)
        logging.info("✅ TIMEOUT: Reset man defense matchups to defaults")
        
        # Check if team has timeouts remaining (skip for FOUL_OUT)
        if timeout_reason != "FOUL_OUT":
            if not self.turn_manager.can_call_timeout(calling_team):
                logging.warning(f"⏸️ TIMEOUT: {calling_team.name} cannot call timeout (no timeouts remaining)")
                return None
        
        # Create timeout turn
        timeout_turn = self.turn_manager.setup_timeout_turn(
            timeout_reason=timeout_reason,
            calling_team=calling_team,
            foul_out_player=foul_out_player,
            foul_out_context=foul_out_context,
        )
        
        # Store next_play_type and offense_team_id for resume
        self.game_state["timeout_next_play_type"] = timeout_turn.get("next_play_type", "SIDE_INBOUND")
        # Stable trace id for end-to-end timeout resume diagnostics.
        self.game_state["timeout_trace_id"] = self.game_state.get("timeout_trace_id") or f"to-{uuid.uuid4().hex[:10]}"
        
        # ✅ FIX: For DREB => HCO transitions, read offense_team_id from the last turn (which was updated after flip)
        # For SIP/BIP, self.offense_team.team_id is already correct (possession flipped before turn creation)
        # This fixes the bug where timeout_offense_team_id was saved as the wrong team during DREB => HCO
        last_turn = self.turns[-1] if self.turns else None
        foul_out_ctx = self.game_state.get("foul_out_context") or {}
        if timeout_reason == "FOUL_OUT" and foul_out_ctx.get("foul_type") == "OFFENSIVE":
            # Offensive foul (charge or HCO o-foul): possession flips after this turn; save the team that receives the ball (current defense)
            timeout_offense_team_id = self.defense_team.team_id
            logging.info(f"✅ TIMEOUT: FOUL_OUT offensive foul - using defense_team as next offense (ball goes to them): {timeout_offense_team_id}")
        elif (last_turn and 
            last_turn.get("next_play_type") == "HCO" and 
            last_turn.get("rebound_type") == "DREB" and
            last_turn.get("offense_team_id")):
            # DREB => HCO transition: use the turn's offense_team_id (updated after flip at line 347)
            timeout_offense_team_id = last_turn.get("offense_team_id")
            logging.info(f"✅ TIMEOUT: DREB => HCO transition detected - using last turn's offense_team_id: {timeout_offense_team_id} (was: {self.offense_team.team_id})")
        else:
            # SIP/BIP or other cases: use GameManager's offense_team (already correct)
            timeout_offense_team_id = self.offense_team.team_id
        
        self.game_state["timeout_offense_team_id"] = timeout_offense_team_id
        
        logging.info(
            "✅ TIMEOUT: Stored next_play_type '%s' offense_team_id '%s' trace_id '%s' for resume",
            self.game_state["timeout_next_play_type"],
            timeout_offense_team_id,
            self.game_state.get("timeout_trace_id"),
        )
        
        # Rebuild lineups
        from BackEnd.utils.db_utils import build_lineup_from_mongo, autoset_strategy_settings
        try:
            if rebuild_both_lineups:
                # Computer timeout during simmed quarters: rebuild both teams
                calling_team.lineup = build_lineup_from_mongo(calling_team, self.game_state)
                other_team = self.away_team if calling_team == self.home_team else self.home_team
                other_team.lineup = build_lineup_from_mongo(other_team, self.game_state)
                # Autoset strategy settings for both computer teams
                if not calling_team.is_user_team:
                    autoset_strategy_settings(calling_team)
                    logging.info(f"✅ TIMEOUT: Autoset strategy settings for {calling_team.name}")
                if not other_team.is_user_team:
                    autoset_strategy_settings(other_team)
                    logging.info(f"✅ TIMEOUT: Autoset strategy settings for {other_team.name}")
                logging.info(f"✅ TIMEOUT: Rebuilt both team lineups ({calling_team.name} and {other_team.name})")
            elif timeout_reason == "USER":
                # User timeout: rebuild computer team only
                computer_team = self.away_team if not self.away_team.is_user_team else self.home_team
                if not computer_team.is_user_team:
                    computer_team.lineup = build_lineup_from_mongo(computer_team, self.game_state)
                    # Autoset strategy settings for computer team
                    autoset_strategy_settings(computer_team)
                    logging.info(f"✅ TIMEOUT: Rebuilt computer team ({computer_team.name}) lineup and autoset strategy settings")
            elif timeout_reason == "FOUL_OUT":
                # Foul out timeout: rebuild computer team lineup and autoset strategy
                computer_team = self.away_team if not self.away_team.is_user_team else self.home_team
                if not computer_team.is_user_team:
                    computer_team.lineup = build_lineup_from_mongo(computer_team, self.game_state)
                    # Autoset strategy settings for computer team
                    autoset_strategy_settings(computer_team)
                    logging.info(f"✅ TIMEOUT (FOUL_OUT): Rebuilt computer team ({computer_team.name}) lineup and autoset strategy settings")
        except Exception as e:
            logging.error(f"⚠️ TIMEOUT: Failed to rebuild lineups: {e}")
            # Don't fail the timeout if lineup rebuild fails
        
        # ✅ TIMEOUT ENERGY RECHARGE: All players get random recharge at start of timeout
        # This happens before lineup selection screen, so user sees updated energy values
        import random
        timeout_recharge_amounts = [0.03, 0.04, 0.05, 0.06]
        
        for team in [self.home_team, self.away_team]:
            for player in team.get_all_players():
                    recharge_amount = random.choice(timeout_recharge_amounts)
                    if hasattr(player, "recharge_energy"):
                        player.recharge_energy(recharge_amount)
        
        self.turn_manager._attach_clock_contract(
            timeout_turn,
            clock_start=int(self.game_state.get("time_remaining", 0)),
            shot_clock_start=int(self.game_state.get("shot_clock_remaining", 30)),
            game_state=self.game_state,
            source="bypass:TIMEOUT",
        )
        self._append_turn(timeout_turn)
        
        # Set timeout_called flag (for simulation loop stopping)
        self.game_state["timeout_called"] = True
        
        # Save game state to database if game_id provided
        # Note: Database save is handled by the API endpoint to avoid circular imports
        # This method just sets up the timeout turn and state
        
        # logging.warning(f"⏸️ TIMEOUT: {calling_team.name} called timeout (reason: {timeout_reason}, turn {len(self.turns)})")
        return timeout_turn

    def _check_lineups_for_foul_out(self, result):
        """
        SS&S: After every turn, check both teams' active lineups for any player with >= 5 fouls.
        If found and this turn did not already trigger foul-out, run the foul-out process so we
        never miss a player fouling out (e.g. from a code path that didn't call check_and_handle_foul_out).
        """
        if result.get("fouled_out"):
            return
        if result.get("timeout_reason"):
            return
        from BackEnd.engine.phase_resolution import check_and_handle_foul_out
        for team in [self.home_team, self.away_team]:
            for player in (team.lineup or {}).values():
                if not player:
                    continue
                foul_count = (player.get_stat("F", "game") or 0) if hasattr(player, "get_stat") else 0
                if foul_count >= 5:
                    foul_out_info = check_and_handle_foul_out(player, self.game_state, team)
                    result["fouled_out"] = True
                    result["foul_out_player"] = {
                        "player_id": foul_out_info.get("foul_player_id"),
                        "name": foul_out_info.get("foul_player_name"),
                        "photo": foul_out_info.get("foul_player_photo"),
                        "team": foul_out_info.get("foul_player_team"),
                    }
                    result["foul_count"] = foul_out_info.get("foul_count", foul_count)
                    next_play_type = result.get("next_play_type", "SIDE_INBOUND")
                    is_defensive = team == self.defense_team
                    self.game_state["foul_out_context"] = {
                        "foul_type": "DEFENSIVE" if is_defensive else "OFFENSIVE",
                        "is_shooting_foul": False,
                        "is_bonus": team.team_fouls >= 5 if is_defensive else False,
                        "next_play_type": next_play_type,
                        "shooter": result.get("shooter") if next_play_type == "FREE_THROW" else None,
                    }
                    logging.info(
                        f"✅ FOUL OUT (end-of-turn check): {foul_out_info.get('foul_player_name', 'Unknown')} "
                        f"has 5 fouls; instigating Player Foul Out process"
                    )
                    return

    def _append_turn(self, turn_result, text=None):
        """
        Single funnel for appending any turn. Appends to turns + text_log, then runs
        the universal foul-out check. If the check finds a player with >= 5 fouls,
        creates and appends the foul-out timeout turn. Ensures we check after every
        turn (main result, OREB, SIP, BIP, timeouts).
        """
        # Keep clock payload fields present on every emitted turn so frontend scoreboard
        # and shot-clock sync remain authoritative even for non-micro helper turns.
        if isinstance(turn_result, dict):
            turn_result.setdefault("time_remaining", self.game_state.get("time_remaining", 0))
            turn_result.setdefault("clock", self.game_state.get("clock", "0:00"))
            turn_result.setdefault(
                "shot_clock_remaining",
                self.game_state.get(
                    "shot_clock_remaining",
                    min(30, int(self.game_state.get("time_remaining", 0) or 0)),
                ),
            )
            turn_result.setdefault("quarter", self.game_state.get("quarter", self.quarter))

        self.turns.append(turn_result)
        self.text_log.append(text if text is not None else turn_result.get("text", ""))
        if isinstance(turn_result, dict):
            sync_lineup_coords_from_turn(self, turn_result)
        self._check_lineups_for_foul_out(turn_result)
        if turn_result.get("fouled_out"):
            self._handle_foul_out_timeout(turn_result)

    def _handle_foul_out_timeout(self, result):
        """Create foul-out timeout turn using the unified timeout path, then save."""

        foul_out_player_data = result.get("foul_out_player", {})
        foul_out_player = None
        foul_out_player_id = foul_out_player_data.get("player_id") if isinstance(foul_out_player_data, dict) else None
        if foul_out_player_id:
            for team in [self.home_team, self.away_team]:
                players = team.get_all_players() if hasattr(team, "get_all_players") else []
                for player in players:
                    if hasattr(player, "player_id") and player.player_id == foul_out_player_id:
                        foul_out_player = player
                        break
                if foul_out_player:
                    break
                if not foul_out_player:
                    for player in (team.lineup or {}).values():
                        if player and hasattr(player, "player_id") and player.player_id == foul_out_player_id:
                            foul_out_player = player
                            break
                if foul_out_player:
                    break

        foul_out_context = self.game_state.get("foul_out_context", {})
        if foul_out_context:
            logging.info(f"✅ FOUL OUT: Using foul context - type={foul_out_context.get('foul_type')}, next={foul_out_context.get('next_play_type')}")

        # Resolve fouled-out player's team so FOUL_OUT uses the same lineup refresh flow
        # as other timeout types (including autoset/rebuild behavior for computer teams).
        calling_team = None
        if foul_out_player and getattr(foul_out_player, "team", None):
            foul_team = foul_out_player.team
            if foul_team == self.home_team.name or foul_team == self.home_team.team_id:
                calling_team = self.home_team
            elif foul_team == self.away_team.name or foul_team == self.away_team.team_id:
                calling_team = self.away_team

        timeout_turn = self.call_timeout(
            calling_team=calling_team,
            timeout_reason="FOUL_OUT",
            foul_out_player=foul_out_player,
            foul_out_context=foul_out_context,
        )
        if not timeout_turn:
            logging.error("🚨 FOUL OUT TIMEOUT: call_timeout returned no timeout turn")
            return
        # Ensure frontend always receives foul_out_player: if lookup failed, attach the dict from the result
        if not timeout_turn.get("foul_out_player") and isinstance(foul_out_player_data, dict) and foul_out_player_data:
            timeout_turn["foul_out_player"] = dict(foul_out_player_data)
            logging.warning(
                "⚠️ FOUL OUT: Player lookup failed; attached foul_out_player from result so frontend can show popup - player_id=%s name=%s",
                foul_out_player_data.get("player_id"), foul_out_player_data.get("name", "Unknown")
            )
        elif not foul_out_player and foul_out_player_data:
            logging.warning(
                "⚠️ FOUL OUT: Could not resolve Player object for foul_out_player_id=%s (name=%s); timeout turn may lack foul_out_player",
                foul_out_player_id, foul_out_player_data.get("name", "Unknown") if isinstance(foul_out_player_data, dict) else None
            )
        # Contract: timeout turn always has foul_out_player so frontend can show popup (use placeholder if missing)
        if not timeout_turn.get("foul_out_player"):
            timeout_turn["foul_out_player"] = (
                dict(foul_out_player_data) if isinstance(foul_out_player_data, dict) and foul_out_player_data
                else {"name": "Unknown", "player_id": None, "team": None, "photo": None}
            )
            logging.warning(
                "⚠️ FOUL OUT: Attached placeholder foul_out_player so frontend always receives one (result had fouled_out=True but no usable data)"
            )
        logging.warning(
            "⏸️ FOUL OUT TIMEOUT: Created timeout turn for foul out - %s (game_id=%s)",
            foul_out_player_data.get("name", "Unknown"),
            self.game_id,
        )

        if self.game_id:
            try:
                from BackEnd.utils.shared import summarize_game_state
                from BackEnd.db import games_collection
                # 🔍 FOUL_OUT DATA-LOSS DEBUG: Log before save (Hypothesis 2)
                logging.warning(
                    "🔍 [FOUL_OUT DEBUG] _handle_foul_out_timeout saving: game_id=%s, type=%s",
                    self.game_id, type(self.game_id).__name__,
                )
                db_summary = summarize_game_state(self, exclude_animations=True)
                result = games_collection.update_one(
                    {"_id": self.game_id}, {"$set": db_summary}, upsert=False
                )
                save_matched = result.matched_count > 0
                logging.warning(
                    "🔍 [FOUL_OUT DEBUG] _handle_foul_out_timeout first update_one: matched_count=%s, modified_count=%s",
                    result.matched_count, result.modified_count,
                )
                # If no match, document may have been created with ObjectId _id (string vs ObjectId mismatch)
                if result.matched_count == 0 and self.game_id and len(self.game_id) == 24:
                    try:
                        from bson import ObjectId
                        oid = ObjectId(self.game_id)
                        result2 = games_collection.update_one(
                            {"_id": oid}, {"$set": db_summary}, upsert=False
                        )
                        save_matched = result2.matched_count > 0
                        logging.warning(
                            "🔍 [FOUL_OUT DEBUG] _handle_foul_out_timeout ObjectId retry: matched_count=%s, modified_count=%s",
                            result2.matched_count, result2.modified_count,
                        )
                        if result2.matched_count > 0:
                            logging.warning(
                                "⚠️ FOUL OUT TIMEOUT: Initial update matched 0 documents; retried with ObjectId and matched %s",
                                result2.matched_count,
                            )
                    except (ValueError, TypeError):
                        pass  # Invalid ObjectId format - leave as is
                if not save_matched:
                    logging.error(
                        "🚨 FOUL OUT TIMEOUT: Save matched 0 documents (game_id=%s) - timeout state not persisted; "
                        "return to court may reset / data loss possible",
                        self.game_id,
                    )
                logging.warning(
                    "💾 FOUL OUT TIMEOUT: Saved game state immediately: game_id=%s, quarter=%s, clock=%s, next_play_type=%s",
                    self.game_id,
                    db_summary.get("quarter"),
                    db_summary.get("clock"),
                    timeout_turn.get("next_play_type"),
                )
            except Exception as e:
                logging.error(
                    "🚨 FOUL OUT TIMEOUT: Exception during save - data loss on return to court possible: %s", e
                )
        else:
            logging.warning(
                "⚠️ FOUL OUT TIMEOUT: Skipped save - game_id is missing (game_id=%s)",
                self.game_id,
            )

    def _maybe_set_force_foul_pending_after_inbound(self, inbound_payload, inbound_type):
        """
        Situational Logic (Q4/OT): If Slow It Down + Force Foul, set pending so the next
        API turn returns a defensive foul on the inbound pass receiver (after frontend animates the pass).
        """
        from BackEnd.utils import situational_logic as sl
        time_remaining = self.game_state.get("time_remaining")
        if not (
            sl.is_situational_active(self.quarter)
            and sl.is_slow_it_down(self, time_remaining)
            and sl.should_force_foul(self, time_remaining)
        ):
            return
        receiver_pos = inbound_payload.get("receiver_pos", "SG")
        off_lineup = self.offense_team.lineup
        if receiver_pos not in off_lineup or not off_lineup[receiver_pos]:
            return
        self.game_state["situational_force_foul_pending"] = {
            "victim_id": getattr(off_lineup[receiver_pos], "player_id", None),
            "victim_coords": inbound_payload.get("oDestinations", {}).get(receiver_pos, {"x": 50, "y": 25}),
            "defender_coords_by_pos": inbound_payload.get("dDestinations", {}),
        }

    def simulate_macro_turn(self): #run_simulation
        import time as _time
        # ⏱️ Coarse timers for full_sim (logged on sample turns)
        _perf = {}

        # Clear timeout flag at start of each turn (will be set if timeout is called)
        self.game_state["timeout_called"] = False

        # Increment macro turn counter
        self.macro_turn_count += 1

        # Track previous turn result for transition validation
        # Get the last turn result (before this turn executes)
        previous_result = self.turns[-1] if self.turns else None
        previous_offensive_state = self.game_state.get("_previous_offensive_state")

        _t0 = _time.time()
        result = self.turn_manager.run_micro_turn()
        _perf["run_micro_turn"] = (_time.time() - _t0) * 1000

        # ✅ SS&S: Centralized next_turn determination (single source of truth)
        # Sets explicit next_turn based on result and conditions
        # This ensures ALL turns have accurate next_turn (no None values)
        _t0 = _time.time()
        result["next_turn"] = self.determine_next_turn(result)
        self._append_turn(result)
        _perf["next_turn_append"] = (_time.time() - _t0) * 1000

        # 🔍 [FB MISS DEBUG] Log Fast Break miss: outcome, next_turn we're set to process, possession_flips value
        if result.get("fast_break") and result.get("result_type") == "MISS":
            outcome = "shooting_foul" if result.get("next_play_type") == "FREE_THROW" else result.get("rebound_type", "?")
            logging.warning(
                "🔍 [FB MISS] game_manager: outcome=%s next_turn=%s possession_flips=%s (before flip logic)",
                outcome,
                result.get("next_turn"),
                result.get("possession_flips"),
            )

        # If the turn ended with an offensive rebound, create a separate OREB turn
        # Process ALL consecutive OREBs in this same call (for batch efficiency)
        _t0 = _time.time()
        while self.game_state.get("pending_oreb"):
            # print(f"📦 OREB detected - creating separate OREB turn")
            
            oreb_turn = self.turn_manager.resolve_offensive_rebound_turn()
            if oreb_turn:
                # print(f"📦 OREB turn created: {oreb_turn.get('result_type')} - {oreb_turn.get('text')}")
                
                # ✅ SS&S: Set next_turn for OREB turns (same centralized logic)
                oreb_turn["next_turn"] = self.determine_next_turn(oreb_turn)
                
                self._append_turn(oreb_turn)
                # Apply OREB turn's time_elapsed to game state (same method as run_micro_turn)
                self.turn_manager.update_clock_and_possession(oreb_turn)
                
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
        _perf["oreb_loop"] = (_time.time() - _t0) * 1000

        # Log breakdown on sample turns during full_sim to see what drives user-game slowness
        if self.game_state.get("_is_full_simulation") and (
            self.macro_turn_count <= 3 or self.macro_turn_count % 10 == 0
        ):
            logging.warning(
                "⏱️ [PERF] macro_turn %s breakdown: run_micro_turn=%.0fms next_turn_append=%.0fms oreb_loop=%.0fms",
                self.macro_turn_count, _perf["run_micro_turn"], _perf["next_turn_append"], _perf["oreb_loop"],
            )

        # ✅ FIX 3: Backend flip for DREB → HCO (Pattern B)
        # Handle possession flips for DREB transitions that go directly to HCO (not through inbound)
        # This includes: MISS with DREB → HCO, STEAL → HCO (direct, not via Fast Break)
        # ✅ SS&S FIX: Only flip if possession_flips is True (prevents double flip for Fast Break → HCO)
        # Fast Break defensive stop sets possession_flips: False, so it won't trigger this flip
        if result.get("next_play_type") == "HCO" and result.get("possession_flips") is True:
            if result.get("fast_break"):
                logging.warning(
                    "🔍 [FB MISS] game_manager: processing DREB→HCO flip possession_flips=%s next_turn=%s",
                    result.get("possession_flips"), result.get("next_turn"),
                )
            old_offense = self.offense_team.name
            self.switch_possession()
            result["possession_flips"] = False
            # ✅ ANIMATION FIX: Do NOT update result["offense_team_id"] here. The skeleton was built
            # with the team that had the ball during the play (old offense). The frontend uses
            # offense_team_id to classify offense/defense for the step loop; if we set it to the new
            # team, defenders animate first and the pass animates after (wrong order). Keep the
            # result turn's offense_team_id = old team so pass steps animate in sync.
            logging.debug(f"🔄 [DREB→HCO] Flipped possession before HCO: {old_offense} → {self.offense_team.name} (result keeps offense_team_id=old team for animation)")

        # ✅ FIX 4: Backend flip for DREB → Fast Break (Pattern C)
        # Handle possession flips for DREB transitions that go to Fast Break
        # This includes: MISS with DREB → Fast Break, STEAL → Fast Break
        if result.get("next_play_type") == "FAST_BREAK" and result.get("possession_flips"):
            if result.get("fast_break"):
                logging.warning(
                    "🔍 [FB MISS] game_manager: processing DREB→FAST_BREAK flip possession_flips=%s next_turn=%s",
                    result.get("possession_flips"), result.get("next_turn"),
                )
            old_offense = self.offense_team.name
            self.switch_possession()
            result["possession_flips"] = False
            # ✅ ANIMATION FIX: Do NOT update result["offense_team_id"] here (same as DREB→HCO).
            # Keep result turn's offense_team_id = old team so frontend classifies correctly for step animation.
            logging.debug(f"🔄 [DREB→FB] Flipped possession before Fast Break: {old_offense} → {self.offense_team.name} (result keeps offense_team_id=old team for animation)")

        # ✅ Situational Logic: Force Foul after DREB — inject FOUL turn and forgo outlet/FB/HCO
        if result.get("force_foul_after_dreb"):
            from BackEnd.utils import situational_logic as sl
            from BackEnd.engine.phase_resolution import (
                resolve_non_shooting_foul,
                select_defender_closest_to_victim,
            )
            victim = self.game_state.get("last_rebounder")
            def_lineup = self.defense_team.lineup  # After DREB flip, rebounder's team is offense; fouling team is defense
            victim_coords = {"x": 50, "y": 25}  # Rebounder at half-court; defender positions use HCO fallback
            foul_player = select_defender_closest_to_victim(victim_coords, def_lineup, None)
            if victim and foul_player:
                self.game_state["foul_team"] = "DEFENSE"
                roles = {
                    "ball_handler": victim,
                    "defender": foul_player,
                    "foul_player": foul_player,
                    "shooter": victim,
                    "screener": None,
                    "passer": None,
                }
                foul_result = resolve_non_shooting_foul(
                    roles, self, time_elapsed_override=sl.force_foul_time_elapsed()
                )
                victim.coords = {
                    "x": float(victim_coords.get("x", 50)),
                    "y": float(victim_coords.get("y", 25)),
                }
                attach_position_snapshots(
                    foul_result,
                    [
                        build_phase_post_stopper_snapshot(
                            self,
                            self.offense_team.lineup,
                            self.defense_team.lineup,
                            None,
                            roles,
                            "HCO",
                            "non_shooting_foul",
                            "hco_force_foul_after_dreb",
                        )
                    ],
                )
                foul_result["offense_team_id"] = self.offense_team.team_id
                foul_result["current_turn"] = "HCO"
                foul_result["quick_foul"] = True
                foul_result["force_foul_after_dreb"] = True  # Frontend: animate defender→rebounder, no outlet
                foul_result["victim_id"] = getattr(victim, "player_id", None)  # Rebounder (fouled player) for animation
                foul_result["next_turn"] = foul_result.get("next_play_type") or "SIDE_INBOUND"
                self.turn_manager._attach_clock_contract(
                    foul_result,
                    clock_start=int(self.game_state.get("time_remaining", 0)),
                    shot_clock_start=int(self.game_state.get("shot_clock_remaining", 30)),
                    game_state=self.game_state,
                    source="bypass:FOUL_AFTER_DREB",
                )
                self._append_turn(foul_result)
                result = foul_result  # So FOUL/SIP block below runs

        # (Foul-out check and timeout creation now run inside _append_turn for the main result)

        # If the turn ended with a dead-ball turnover, a non-shooting foul
        # that does not result in free throws, or a charge (offensive foul),
        # prepare a sideline inbound and append its payload so the front end can animate it.
        if (
            (result.get("result_type") == "FOUL" and self.game_state.get("free_throws_remaining", 0) == 0)
            or result.get("result_type") == "DEAD BALL"
            or result.get("result_type") == "CHARGE"
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
            # should_computer_call_timeout() already filters out user teams (checks is_user_team flag)
            # This allows computer teams to call timeouts during Play Quarter mode
            # Play Quarter: Only computer teams can call timeouts (user team filtered out by should_computer_call_timeout)
            # Sim Quarter/Sim Full Game: Both teams checked, but user team still filtered out by should_computer_call_timeout
            calling_team = None
            
            # Check both teams - should_computer_call_timeout will filter out user teams
            computer_teams_to_check = []
            # In full simulation, allow the user team to use the same timeout logic silently.
            # In turn-by-turn, keep user timeouts manual-only.
            is_full_simulation = self.game_state.get("_is_full_simulation", False)
            if is_full_simulation:
                computer_teams_to_check = [self.home_team, self.away_team]
            else:
                if not self.home_team.is_user_team:
                    computer_teams_to_check.append(self.home_team)
                if not self.away_team.is_user_team:
                    computer_teams_to_check.append(self.away_team)
            
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
                
                # ✅ COMPUTER TIMEOUT: Conditional creation based on simulation mode
                is_full_simulation = self.game_state.get("_is_full_simulation", False)
                
                if is_full_simulation:
                    # ✅ FULL SIMULATION: Create timeout immediately and rebuild lineups
                    timeout_turn = self.call_timeout(
                        calling_team=calling_team,
                        timeout_reason="COMPUTER",
                        rebuild_both_lineups=True,
                        game_id=self.game_id  # Pass game_id if available
                    )
                    if timeout_turn:
                        logging.info(f"✅ COMPUTER TIMEOUT: Created timeout turn immediately (full simulation mode) for {calling_team.name}")
                        # Clear timeout_called flag so simulation continues normally
                        # The timeout turn is just one turn - simulation should continue
                        self.game_state["timeout_called"] = False
                    # Don't append SIP turn - timeout turn was created instead
                    return
                else:
                    # ✅ TURN-BY-TURN: Defer timeout creation until next API call
                    # This allows the current turn to be animated first, then timeout is created on next /api/simulate-turn call
                    # DO NOT append inbound_payload - timeout will replace it
                    self.game_state["pending_computer_timeout"] = {
                        "calling_team": calling_team,
                        "turn_type": "SIDE_INBOUND"
                    }
                    logging.info(f"⏸️ COMPUTER TIMEOUT: Deferred for {calling_team.name} (turn-by-turn mode) - will be created on next API call")
                    # Don't append SIP turn - timeout will replace it on next API call
                    return
            else:
                # ✅ Situational Logic: Force Foul after SIP — set pending so next turn is the foul
                self._maybe_set_force_foul_pending_after_inbound(inbound_payload, "SIDE_INBOUND")
                self.turn_manager._attach_clock_contract(
                    inbound_payload,
                    clock_start=int(self.game_state.get("time_remaining", 0)),
                    shot_clock_start=int(self.game_state.get("shot_clock_remaining", 30)),
                    game_state=self.game_state,
                    source="bypass:SIP",
                )
                # Store offense destinations so next HCO turn can use pre-step-0 bring-up (max distance to step 0)
                self.game_state["_prev_offense_positions_for_hco"] = inbound_payload.get("oDestinations") or {}
                self._append_turn(inbound_payload)
            
            # Reset offensive state to HCO after side inbound (FCP/HCT only apply after made shots)
            self.game_state["offensive_state"] = "HCO"
            # Any time we come out of a SIP, shot clock resets to 30 (next turn is HCO with full clock)
            self.game_state["shot_clock_remaining"] = min(30, int(self.game_state.get("time_remaining", 30)))

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
        # ✅ Final play of quarter: no BIP after make or after FTs when time_remaining == 0
        if last_turn and last_turn.get("next_play_type") == "BASELINE_INBOUND":
            if self.game_state.get("time_remaining", 1) == 0:
                last_turn["quarter_ends_after"] = True
                last_turn["next_play_type"] = None
                logging.debug("✅ [FINAL PLAY] Skipping BIP — quarter ends after this turn (time_remaining=0)")
                return
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
            # should_computer_call_timeout() already filters out user teams (checks is_user_team flag)
            # This allows computer teams to call timeouts during Play Quarter mode
            # Play Quarter: Only computer teams can call timeouts (user team filtered out by should_computer_call_timeout)
            # Sim Quarter/Sim Full Game: Both teams checked, but user team still filtered out by should_computer_call_timeout
            calling_team = None
            
            # Check both teams - should_computer_call_timeout will filter out user teams
            computer_teams_to_check = []
            # In full simulation, allow the user team to use the same timeout logic silently.
            # In turn-by-turn, keep user timeouts manual-only.
            is_full_simulation = self.game_state.get("_is_full_simulation", False)
            if is_full_simulation:
                computer_teams_to_check = [self.home_team, self.away_team]
            else:
                if not self.home_team.is_user_team:
                    computer_teams_to_check.append(self.home_team)
                if not self.away_team.is_user_team:
                    computer_teams_to_check.append(self.away_team)
            
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
                
                # ✅ COMPUTER TIMEOUT: Conditional creation based on simulation mode
                is_full_simulation = self.game_state.get("_is_full_simulation", False)
                
                if is_full_simulation:
                    # ✅ FULL SIMULATION: Create timeout immediately and rebuild lineups
                    timeout_turn = self.call_timeout(
                        calling_team=calling_team,
                        timeout_reason="COMPUTER",
                        rebuild_both_lineups=True,
                        game_id=self.game_id  # Pass game_id if available
                    )
                    if timeout_turn:
                        logging.info(f"✅ COMPUTER TIMEOUT: Created timeout turn immediately (full simulation mode) for {calling_team.name}")
                        # Clear timeout_called flag so simulation continues normally
                        # The timeout turn is just one turn - simulation should continue
                        self.game_state["timeout_called"] = False
                    # Don't append BIP turn - timeout turn was created instead
                    return
                else:
                    # ✅ TURN-BY-TURN: Defer timeout creation until next API call
                    # This allows the current turn to be animated first, then timeout is created on next /api/simulate-turn call
                    # DO NOT append inbound_payload - timeout will replace it
                    self.game_state["pending_computer_timeout"] = {
                        "calling_team": calling_team,
                        "turn_type": "BASELINE_INBOUND"
                    }
                    logging.info(f"⏸️ COMPUTER TIMEOUT: Deferred for {calling_team.name} (turn-by-turn mode) - will be created on next API call")
                    # Don't append BIP turn - timeout will replace it on next API call
                    return
            else:
                # ✅ Situational Logic: Force Foul after BIP — set pending so next turn is the foul
                self._maybe_set_force_foul_pending_after_inbound(inbound_payload, "BASELINE_INBOUND")
                self.turn_manager._attach_clock_contract(
                    inbound_payload,
                    clock_start=int(self.game_state.get("time_remaining", 0)),
                    shot_clock_start=int(self.game_state.get("shot_clock_remaining", 30)),
                    game_state=self.game_state,
                    source="bypass:BIP",
                )
                # Store offense destinations for pre-step-0 bring-up when next turn is HCO
                if not next_defensive_setup:
                    self.game_state["_prev_offense_positions_for_hco"] = inbound_payload.get("oDestinations") or {}
                self._append_turn(inbound_payload, text="Baseline inbound after made shot")
            
            # Preserve offensive_state for next API call
            if next_defensive_setup:
                self.game_state["offensive_state"] = next_defensive_setup
            
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
        
        # FINAL_HOLD is terminal for the possession/period boundary.
        if result_type == "FINAL_HOLD":
            return None

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
        import logging
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
            # ✅ SS&S: Use team_id as key instead of team.name
            team_key = team.team_id if team.team_id else team.name
            box_score[team_key] = team_box
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
