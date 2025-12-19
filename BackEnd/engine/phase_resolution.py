import random
import logging
import copy
import time
from typing import TYPE_CHECKING
from fastapi import HTTPException
from BackEnd.utils.shared import (
    get_name_safe, 
    get_player_position,
    get_quarter_index_from_game
)
from BackEnd.models.shot_manager import ShotManager
if TYPE_CHECKING:
    from BackEnd.models.turn_manager import TurnManager
if TYPE_CHECKING:
    from BackEnd.models.game_manager import GameManager
from BackEnd.models.animator import Animator

from BackEnd.utils.shared import (
    get_name_safe,
    get_time_elapsed,
    get_fast_break_chance,
    calculate_rebound_score,
    calculate_outlet_pass_score,
    choose_rebounder,
    default_rebounder_dict,
    resolve_offensive_rebound,
    apply_scoring,
    unpack_game_context
)
from BackEnd.playcall_skeletons.fcp_skeletons import FCP_1, FCP_SKELETONS_DICT
from BackEnd.playcall_skeletons.inside_skeletons import INSIDE_SCENES


def get_in_play_defenders(ball_handler, defense_lineup, target_is_away):
    """Return defenders ahead of the ball handler on the fast break.

    Args:
        ball_handler (Player): The player leading the break.
        defense_lineup (dict): Mapping of positions to defensive players.
        target_is_away (bool): True if the offense is attacking the away hoop.

    Returns:
        list[Player]: Defensive players considered in play.
    """

    bh_x = getattr(ball_handler, "coords", {}).get("x", 0)
    in_play = []
    for defender in defense_lineup.values():
        d_x = getattr(defender, "coords", {}).get("x", 0)
        if target_is_away:
            if d_x < bh_x:
                in_play.append(defender)
        else:
            if d_x > bh_x:
                in_play.append(defender)
    return in_play


def apply_energy_decay(off_lineup, def_lineup):
    """
    Apply energy decay to all players in both lineups.
    
    This is extracted from determine_event_type() to ensure energy decay
    happens for all HCO turns, regardless of whether determine_event_type()
    is called (e.g., when stopper system bypasses it for SHOT results).
    
    Args:
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
    """
    for player in off_lineup.values():
        if player and hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
            player.decay_energy(player.get_fatigue_decay_amount())
    for player in def_lineup.values():
        if player and hasattr(player, "decay_energy") and hasattr(player, "get_fatigue_decay_amount"):
            player.decay_energy(player.get_fatigue_decay_amount())


def apply_bench_energy_recharge(game):
    """
    Recharge energy for players not in the active lineup.
    
    For each bench player (not in active lineup), per turn:
    - 20% chance: no recharge (0)
    - 70% chance: recharge +0.01 energy
    - 10% chance: recharge +0.02 energy
    
    Args:
        game: GameManager instance containing home and away teams
    """
    # Get all lineup player IDs from both teams
    lineup_player_ids = set()
    for team in [game.home_team, game.away_team]:
        for player in team.lineup.values():
            if player and hasattr(player, "player_id"):
                lineup_player_ids.add(player.player_id)
    
    # Recharge bench players (not in lineup)
    for team in [game.home_team, game.away_team]:
        for player in team.get_all_players():
            if player and hasattr(player, "player_id") and player.player_id not in lineup_player_ids:
                if hasattr(player, "recharge_energy"):
                    roll = random.random()
                    if roll < 0.2:
                        # 20% chance: no recharge
                        pass
                    elif roll < 0.9:
                        # 70% chance: recharge +0.01
                        player.recharge_energy(0.01)
                    else:
                        # 10% chance: recharge +0.02
                        player.recharge_energy(0.02)


def check_and_handle_foul_out(foul_player, game_state, foul_team):
    """
    Check if player fouled out (5+ fouls) and handle accordingly.
    Returns dict with foul_out info.
    """
    if not foul_player:
        return {"fouled_out": False, "foul_count": 0}
    
    foul_count = foul_player.get_stat("F", "game")
    fouled_out = foul_count >= 5
    
    if fouled_out:
        # Add to ineligible players list if not already there
        if "ineligible_players" not in game_state:
            game_state["ineligible_players"] = []
        if foul_player.player_id not in game_state["ineligible_players"]:
            game_state["ineligible_players"].append(foul_player.player_id)
        
        # Remove from lineup if currently in lineup
        for pos, player in list(foul_team.lineup.items()):
            if player and hasattr(player, "player_id") and player.player_id == foul_player.player_id:
                foul_team.lineup[pos] = None
                # Immediately replace the fouled-out player to ensure lineup is always complete
                from BackEnd.main import _ensure_complete_lineup
                _ensure_complete_lineup(foul_team, game_state)
                break
    
    return {
        "fouled_out": fouled_out,
        "foul_count": foul_count,
        "foul_player_id": foul_player.player_id if fouled_out else None,
        "foul_player_name": foul_player.get_name() if fouled_out else None,
        "foul_player_photo": getattr(foul_player, "photo", None) if fouled_out else None,
        "foul_player_team": foul_team.name if fouled_out else None
    }

def _find_most_recent_shot_turn(game, max_turns=10):
    """
    Find the most recent MISS or MAKE turn.
    
    Args:
        game: Game object with turns list
        max_turns: Maximum number of turns to check (default: 10)
    
    Returns:
        dict: Most recent MISS/MAKE turn, or None if not found
    """
    if not game.turns or len(game.turns) == 0:
        return None
    
    for turn in reversed(game.turns[-max_turns:]):
        if turn.get("result_type") in ["MISS", "MAKE"]:
            return turn
    
    return None

def get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=None):
    """
    Determine the ball handler from skeleton steps.
    
    Args:
        skeleton: Skeleton dict with "steps" key
        off_lineup: Dictionary of offensive players by position
        step_index: Optional step index to check (defaults to last step if None)
    
    Returns:
        Player object who has the ball, or PG (or first player) as fallback
    """
    if not skeleton or not skeleton.get("steps"):
        # Fallback: use PG or first player
        return off_lineup.get("PG", list(off_lineup.values())[0])
    
    steps = skeleton.get("steps", [])
    if not steps:
        return off_lineup.get("PG", list(off_lineup.values())[0])
    
    # Determine which step to check
    if step_index is None:
        # Default to last step (where event likely occurs)
        step_index = len(steps) - 1
    
    # Clamp step_index to valid range
    step_index = max(0, min(step_index, len(steps) - 1))
    
    # Check steps from step_index backwards to find ball handler
    # (ball handler might be determined earlier in the sequence)
    for i in range(step_index, -1, -1):
        step = steps[i]
        pos_actions = step.get("pos_actions", {})
        
        # Find who has ball at this step
        for pos, action_info in pos_actions.items():
            action = action_info.get("action", "")
            # Actions that indicate ball possession
            if action in ["handle_ball", "receive", "shoot"]:
                # Found ball handler position
                ball_handler_player = off_lineup.get(pos)
                if ball_handler_player:
                    return ball_handler_player
    
    # Fallback: use PG or first player
    return off_lineup.get("PG", list(off_lineup.values())[0])


def get_stealer_position_from_skeleton_step(skeleton, step_index, ball_handler_pos, defender, off_team, def_team, game):
    """
    Extract the stealer's (defender's) position from a specific skeleton step.
    
    Args:
        skeleton: Skeleton dict with "steps" key
        step_index: Index of the step where steal occurs
        ball_handler_pos: Position of the ball handler (e.g., "PG", "SG")
        defender: Defender (stealer) player object
        off_team: Offensive team object
        def_team: Defensive team object
        game: GameManager instance
    
    Returns:
        dict: Stealer's coordinates {"x": int, "y": int} or None if cannot determine
    """
    if not skeleton or not skeleton.get("steps"):
        return None
    
    steps = skeleton.get("steps", [])
    if step_index < 0 or step_index >= len(steps):
        return None
    
    step = steps[step_index]
    pos_actions = step.get("pos_actions", {})
    
    # Get ball handler's position from this step
    ball_handler_action = pos_actions.get(ball_handler_pos, {})
    ball_handler_location = ball_handler_action.get("location") or ball_handler_action.get("spot") or "key"
    
    # Convert location string to coordinates
    from BackEnd.constants import HCO_STRING_SPOTS
    ball_handler_coords = HCO_STRING_SPOTS.get(ball_handler_location, {"x": 50, "y": 25})
    
    # Calculate defender's position based on ball handler's position
    from BackEnd.utils.shared_defense import get_defender_coords
    
    # Determine if away team is on offense
    is_away_offense = off_team.team_id == game.away_team.team_id
    
    # Get defense aggression level
    aggression_level = def_team.strategy_settings.get("aggression", "normal")
    aggression_map = {0: "passive", 1: "passive", 2: "normal", 3: "aggressive", 4: "aggressive"}
    aggression = aggression_map.get(aggression_level, "normal")
    
    # Calculate defender coordinates (stealer is the ball handler's defender)
    stealer_coords = get_defender_coords(
        ball_handler_coords,
        is_away_offense,
        aggression,
        ball_handler_location,
        None,
        is_ball_handler=True
    )
    
    return stealer_coords


def select_foul_player(foul_team_type, ball_handler, off_lineup, def_lineup):
    """
    Select which player committed the foul based on probabilistic logic.
    
    Args:
        foul_team_type: "OFFENSE" or "DEFENSE"
        ball_handler: The current ball handler
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
    
    Returns:
        Player object who committed the foul
    """
    if foul_team_type == "OFFENSE":
        # 60% chance it's the ball handler, 40% distributed among other 4 players (10% each)
        players = list(off_lineup.values())
        weights = []
        for player in players:
            if player == ball_handler:
                weights.append(0.6)
            else:
                weights.append(0.1)
        
        foul_player = random.choices(players, weights=weights)[0]
    
    else:  # DEFENSE
        # 60% chance it's the defender matched to ball handler's position
        # 40% distributed among other 4 defenders (10% each)
        ball_handler_pos = getattr(ball_handler, 'position', None)
        matched_defender = def_lineup.get(ball_handler_pos) if ball_handler_pos else None
        
        players = list(def_lineup.values())
        weights = []
        for player in players:
            if matched_defender and player == matched_defender:
                weights.append(0.6)
            else:
                weights.append(0.1)
        
        foul_player = random.choices(players, weights=weights)[0]
    
    return foul_player

    
def resolve_non_shooting_foul(roles, game):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    foul_team = off_team if game_state["foul_team"] == "OFFENSE" else def_team
    
    ball_handler = roles["ball_handler"]
    defender = roles.get("defender", "")
    foul_player = roles["foul_player"]
    shooter = roles["shooter"]
    screener = roles.get("screener", "")
    passer = roles.get("passer", "")
    tempo = off_team.strategy_calls["tempo_call"]
    time_elapsed = get_time_elapsed(tempo)

    # Track the foul
    foul_player.record_stat("F")
    
    # Check if player fouled out and handle accordingly
    foul_out_info = check_and_handle_foul_out(foul_player, game_state, foul_team)
    
    if foul_team == def_team:
        def_team.team_fouls += 1
        text = f"{get_name_safe(foul_player)} fouls {get_name_safe(ball_handler)}!"
    else:
        off_team.team_fouls += 1
        text = f"{get_name_safe(foul_player)} commits an offensive foul!"

    # Bonus free throw logic - ONLY for defensive fouls
    # Offensive fouls NEVER award free throws (always possession change)
    if foul_team == def_team:
        # Defensive foul - check for bonus free throws
        if def_team.team_fouls >= 10:
            # Double bonus (10+ fouls): 2 free throws, no 1 & 1
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2
            game_state["free_throws_remaining"] = 2
            game_state["one_and_one"] = False
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        elif def_team.team_fouls >= 5:
            # Bonus (5-9 fouls): 1 & 1 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2  # Maximum possible (if front end is made)
            game_state["free_throws_remaining"] = 1  # Start with 1 (front end)
            game_state["one_and_one"] = True
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        else:
            # Less than 5 fouls: possession change, side inbound
            game_state["offensive_state"] = "HCO"
            game_state["free_throws"] = 0
            game_state["free_throws_remaining"] = 0
    else:
        # Offensive foul - ALWAYS possession change, no free throws
        game_state["offensive_state"] = "HCO"
        game_state["free_throws"] = 0
        game_state["free_throws_remaining"] = 0

    bh_pos = get_player_position(off_team.lineup, ball_handler)
    
    # ✅ SS&S FIX: Set possession_flips based on foul_team (matches FCP/HCT logic)
    # Offensive fouls always flip possession, defensive fouls don't (handled by bonus logic)
    possession_flips = (foul_team == off_team)  # True for offensive fouls, False for defensive
    
    logging.warning(f"🔍 [RESOLVE_FOUL] foul_team={foul_team.name}, off_team={off_team.name}, possession_flips={possession_flips}")
    logging.warning(f"🔍 [RESOLVE_FOUL] Current offense_team={game.offense_team.name}, defense_team={game.defense_team.name}")
    
    # ✅ FIX: Do NOT flip possession here for offensive fouls - let SIP setup handle it
    # This prevents double-flipping: resolve_non_shooting_foul() sets possession_flips=True,
    # then game_manager.py SIP setup flips based on that flag (same pattern as dead ball turnovers)
    # The flip happens in game_manager.py simulate_macro_turn() before setup_side_inbound()
    # This ensures consistent behavior: all possession flips for SIP transitions happen in one place
    logging.warning(f"⏭️ [RESOLVE_FOUL] NOT flipping possession here - SIP setup will handle it (possession_flips={possession_flips})")
    
    result = {
        "result_type": "FOUL",
        "ball_handler": ball_handler,
        "screener": screener,
        "passer": passer,
        "defender": defender,
        "text": text,
        "possession_flips": possession_flips,
        "time_elapsed": time_elapsed,
        "offense_team_id": game.offense_team.team_id,  # ✅ SS&S: Add offense_team_id to all results
        "current_turn": "HCO",  # ✅ SS&S: Standalone fouls occur in HCO context
        "foul_player_id": getattr(foul_player, "player_id", None) if foul_player else None,
        "foul_team": game_state.get("foul_team"),
        "foul_count": foul_out_info["foul_count"],
        "fouled_out": foul_out_info["fouled_out"]
    }
    
    # Add foul out player info if applicable
    if foul_out_info["fouled_out"]:
        result["foul_out_player"] = {
            "player_id": foul_out_info["foul_player_id"],
            "name": foul_out_info["foul_player_name"],
            "photo": foul_out_info["foul_player_photo"],
            "team": foul_out_info["foul_player_team"]
        }
        
        # ✅ FOUL OUT: Store foul context for timeout creation
        # This allows setup_timeout_turn() to determine next_play_type correctly
        is_bonus = def_team.team_fouls >= 5 if foul_team == def_team else False
        next_play_type = "FREE_THROW" if game_state.get("offensive_state") == "FREE_THROW" else "SIDE_INBOUND"
        
        game_state["foul_out_context"] = {
            "foul_type": "OFFENSIVE" if foul_team == off_team else "DEFENSIVE",
            "is_shooting_foul": False,
            "is_bonus": is_bonus,
            "next_play_type": next_play_type,
            "shooter": ball_handler if game_state.get("offensive_state") == "FREE_THROW" else None
        }
        logging.info(f"✅ FOUL OUT: Stored foul context - type={game_state['foul_out_context']['foul_type']}, next={next_play_type}")
    
    return result

# #FAST BREAK
from BackEnd.constants.fast_break_constants import (
    BALL_HANDLER_MOVE_X_MIN,
    BALL_HANDLER_MOVE_X_MAX,
    BALL_HANDLER_MOVE_Y_RANGE,
    DEFENSIVE_STOP_Y_RANGE,
    STEAL_ENTRY_MOVE_X_MIN,
    STEAL_ENTRY_MOVE_X_MAX,
    STEAL_ENTRY_MOVE_Y_RANGE,
    STEAL_ENTRY_Y_MIN,
    STEAL_ENTRY_Y_MAX,
    STEAL_HCO_SETUP_MOVE_X_MIN,
    STEAL_HCO_SETUP_MOVE_X_MAX,
    STEAL_HCO_SETUP_MOVE_Y_RANGE,
    STEAL_HCO_SETUP_Y_MIN,
    STEAL_HCO_SETUP_Y_MAX,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE,
    STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN,
    STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MAX,
)

def _record_fast_break_stats(fb_roles, turn_result, game):
    """
    Record Fast Break statistics for release player (offensive) and get-back players (defensive).
    
    Args:
        fb_roles: Fast Break roles dict with outlet_receiver, getback_player_ids
        turn_result: Final turn result dict with result_type
        game: GameManager instance
    """
    result_type = turn_result.get("result_type")
    if not result_type:
        return
    
    # Determine success/failure criteria (aligned with team-level Fast_Break_Success)
    # FB_S (offense): Shot Make, Defensive Foul (non-shooting)
    # Note: MISS does NOT count as success (matches team-level criteria)
    # FB_F (offense): Steal, Dead Ball Turnover, Offensive Foul
    # FB_S_D (defense): DEFENSIVE_STOP
    # FB_F_D (defense): Shot Make, Shot Miss, Defensive Foul (any shot attempt or defensive foul)
    
    is_fb_s_offense = result_type == "MAKE" or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    is_fb_f_offense = result_type in ["TURNOVER", "STEAL", "DEAD BALL"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "OFFENSE"
    )
    is_fb_s_defense = result_type == "DEFENSIVE_STOP"
    is_fb_f_defense = result_type in ["MAKE", "MISS"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    
    # Track stats for offensive player - OFFENSIVE stats
    # ✅ SS&S FIX: For DREB-initiated Fast Breaks, use outlet_receiver
    # For STEAL-initiated Fast Breaks, use ball_handler (stealer)
    outlet_receiver_id = fb_roles.get("outlet_receiver")
    ball_handler = fb_roles.get("ball_handler")
    
    offensive_player = None
    if outlet_receiver_id:
        # DREB-initiated: Use outlet receiver
        for team in (game.home_team, game.away_team):
            for player in team.get_all_players():
                if getattr(player, "player_id", None) == outlet_receiver_id:
                    offensive_player = player
                    break
            if offensive_player:
                break
    elif ball_handler:
        # STEAL-initiated: Use ball handler (stealer)
        offensive_player = ball_handler
    
    if offensive_player:
        # Always increment FB_A (Fast Break Attempt)
        offensive_player.record_stat("FB_A", 1)
        
        # Increment FB_S or FB_F based on result
        if is_fb_s_offense:
            offensive_player.record_stat("FB_S", 1)
        elif is_fb_f_offense:
            offensive_player.record_stat("FB_F", 1)
        # FB_N is calculated: FB_A - (FB_S + FB_F)
    
    # Track stats for get-back players - DEFENSIVE stats
    # ✅ SS&S FIX: For DREB-initiated Fast Breaks, use getback_player_ids
    # For STEAL-initiated Fast Breaks, use fb_roles["defense"] (defensive players)
    getback_player_ids = fb_roles.get("getback_player_ids", [])
    defensive_players = []
    
    if getback_player_ids:
        # DREB-initiated: Use get-back players
        for getback_id in getback_player_ids:
            getback_player = None
            for team in (game.home_team, game.away_team):
                for player in team.get_all_players():
                    if getattr(player, "player_id", None) == getback_id:
                        getback_player = player
                        break
                if getback_player:
                    break
            if getback_player:
                defensive_players.append(getback_player)
    else:
        # STEAL-initiated: Use defensive players from fb_roles["defense"]
        defensive_players = fb_roles.get("defense", [])
    
    # Record defensive stats for all defensive players
    for defensive_player in defensive_players:
        if defensive_player:
            # Always increment FB_A_D (Fast Break Attempt Defense)
            defensive_player.record_stat("FB_A_D", 1)
            
            # Increment FB_S_D or FB_F_D based on result
            if is_fb_s_defense:
                defensive_player.record_stat("FB_S_D", 1)
            elif is_fb_f_defense:
                defensive_player.record_stat("FB_F_D", 1)
            # FB_S_N removed (no instances)

def _record_outlet_pass_stats(outlet_passer_id, outlet_score, is_successful, game):
    """
    Record outlet pass statistics for the outlet passer.
    
    Args:
        outlet_passer_id: Player ID of the outlet passer
        outlet_score: Scaled outlet pass score (1-100)
        is_successful: True if outlet pass led to shot attempt, False if defensive stop
        game: GameManager instance
    """
    if not outlet_passer_id or outlet_score is None:
        return
    
    # Find outlet passer player object
    outlet_passer = None
    for team in (game.home_team, game.away_team):
        for player in team.get_all_players():
            if getattr(player, "player_id", None) == outlet_passer_id:
                outlet_passer = player
                break
        if outlet_passer:
            break
    
    if not outlet_passer:
        return
    
    # Record Outlet_A (always increment on outlet pass)
    outlet_passer.record_stat("Outlet_A", 1)
    
    # Record Outlet_S if successful (led to shot attempt)
    if is_successful:
        outlet_passer.record_stat("Outlet_S", 1)
    
    # Update Outlet_Score_List (append score to array)
    outlet_passer.stats["game"]["Outlet_Score_List"].append(outlet_score)
    
    # Calculate and update Outlet_Score (average of list)
    score_list = outlet_passer.stats["game"]["Outlet_Score_List"]
    if score_list:
        outlet_passer.stats["game"]["Outlet_Score"] = int(round(sum(score_list) / len(score_list)))
    
    # Update Outlet_Score_Cum (cumulative sum)
    outlet_passer.stats["game"]["Outlet_Score_Cum"] += outlet_score

def _record_fcp_stats(fcp_roles, turn_result, game, off_lineup, def_lineup):
    """
    Record FCP (Full Court Press) statistics for all players in active lineups.
    
    Args:
        fcp_roles: FCP roles dict with ball_handler, shooter, defender, etc.
        turn_result: Final turn result dict with result_type
        game: GameManager instance
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
    """
    result_type = turn_result.get("result_type")
    if not result_type:
        return
    
    # Determine success criteria
    # FCP_S (offense): MAKE, HCO (press break), Defensive Foul
    # FCP_S_D (defense): MISS, O_FOUL, DEAD_BALL_TURNOVER, STEAL
    
    is_fcp_s_offense = result_type in ["MAKE", "HCO"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    is_fcp_s_defense = result_type in ["MISS", "TURNOVER", "STEAL", "DEAD BALL"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "OFFENSE"
    )
    
    # Track stats for ALL offensive players in active lineup
    for player in off_lineup.values():
        if player:
            player.record_stat("FCP_A", 1)
            if is_fcp_s_offense:
                player.record_stat("FCP_S", 1)
    
    # Track stats for ALL defensive players in active lineup
    for player in def_lineup.values():
        if player:
            player.record_stat("FCP_A_D", 1)
            if is_fcp_s_defense:
                player.record_stat("FCP_S_D", 1)

def _record_hct_stats(hct_roles, turn_result, game, off_lineup, def_lineup):
    """
    Record HCT (Half Court Trap) statistics for all players in active lineups.
    
    Args:
        hct_roles: HCT roles dict with ball_handler, shooter, defender, etc.
        turn_result: Final turn result dict with result_type
        game: GameManager instance
        off_lineup: Dictionary of offensive players by position
        def_lineup: Dictionary of defensive players by position
    """
    result_type = turn_result.get("result_type")
    if not result_type:
        return
    
    # Determine success criteria (same as FCP)
    # HCT_S (offense): MAKE, HCO (trap break), Defensive Foul
    # HCT_S_D (defense): MISS, O_FOUL, DEAD_BALL_TURNOVER, STEAL
    
    is_hct_s_offense = result_type in ["MAKE", "HCO"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "DEFENSE"
    )
    is_hct_s_defense = result_type in ["MISS", "TURNOVER", "STEAL", "DEAD BALL"] or (
        result_type == "FOUL" and game.game_state.get("foul_team") == "OFFENSE"
    )
    
    # Track stats for ALL offensive players in active lineup
    for player in off_lineup.values():
        if player:
            player.record_stat("HCT_A", 1)
            if is_hct_s_offense:
                player.record_stat("HCT_S", 1)
    
    # Track stats for ALL defensive players in active lineup
    for player in def_lineup.values():
        if player:
            player.record_stat("HCT_A_D", 1)
            if is_hct_s_defense:
                player.record_stat("HCT_S_D", 1)

def resolve_fast_break_logic(game: "GameManager"):
    from BackEnd.models.game_manager import GameManager
    # print("Entering resolve_fast_break()")
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    off_scouting = off_team.scouting_data
    def_scouting = def_team.scouting_data
    off_scouting["offense"]["Fast_Break_Entries"] += 1
    def_scouting["defense"]["vs_Fast_Break"]["used"] += 1

    fb_roles = {
        "offense": [],
        "defense": [],
        "ball_handler": None,
        "outlet_passer": None,
        "outlet_receiver": None,
    }
    
    rebound = game_state.get("last_rebound") == "DREB"

    if rebound:
        #resetting last_rebound to avoid carry over bugs
        game_state["last_rebound"] = "" 
        
        # Choose outlet passer (rebounder)
        rebounder = game_state.get("last_rebounder", None)
        
        # ✅ Use release player as outlet receiver (if available), otherwise fallback to random ball handler
        # The release player is the defender who released for fast break during the shot
        # This ensures outlet passes go to the player who was set up to receive it
        release_player = game_state.get("last_release_player", None)
        
        if release_player:
            # Use release player as ball handler and outlet receiver
            ball_handler = release_player
            fb_roles["ball_handler"] = ball_handler
            fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)  # ✅ Store ID for frontend
            
            # Clear release player after use to avoid carry-over bugs
            game_state["last_release_player"] = None
            
            # Ensure outlet passer and receiver are set to IDs and only if different
            if rebounder and rebounder != ball_handler:
                fb_roles["outlet_passer"] = getattr(rebounder, "player_id", None)
                fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
                
                # Calculate outlet pass score for stat tracking
                outlet_score = calculate_outlet_pass_score(rebounder)
                fb_roles["outlet_score"] = outlet_score
                
                # ✅ COMMENTED OUT: Fast break outlet pass logs (cluttering transition debugging)
                # logging.warning(f"🏀 Fast Break outlet pass: outlet_passer={get_name_safe(rebounder)} (rebounder), outlet_receiver={get_name_safe(ball_handler)} (release player)")
            else:
                fb_roles["outlet_passer"] = None
                fb_roles["outlet_receiver"] = None
                fb_roles["outlet_score"] = None
        else:
            # Fallback: Random ball handler if no release player (shouldn't happen, but safety check)
            bh_pos = random.choices(["PG", "SG", "SF"], weights=[75, 15, 10])[0]
            ball_handler = off_lineup[bh_pos]

            fb_roles["ball_handler"] = ball_handler
            fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)  # ✅ Store ID for frontend

            # Ensure outlet passer and receiver are set to IDs and only if different
            if rebounder and rebounder != ball_handler:
                fb_roles["outlet_passer"] = getattr(rebounder, "player_id", None)
                fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
                
                # Calculate outlet pass score for stat tracking
                outlet_score = calculate_outlet_pass_score(rebounder)
                fb_roles["outlet_score"] = outlet_score
                
                # ✅ COMMENTED OUT: Fast break outlet pass logs (cluttering transition debugging)
                # logging.warning(f"⚠️ Fast Break outlet pass (FALLBACK - no release player): outlet_passer={get_name_safe(rebounder)} (rebounder), outlet_receiver={get_name_safe(ball_handler)} (random)")
            else:
                fb_roles["outlet_passer"] = None
                fb_roles["outlet_receiver"] = None
                fb_roles["outlet_score"] = None

        # No additional offensive players when starting from a rebound
        fb_roles["offense"] = []


    else:  # STEAL
        ball_handler = game_state.get("last_stealer")
        
        if ball_handler is None:
            ball_handler = off_lineup["PG"]
        
        fb_roles["ball_handler"] = ball_handler
        fb_roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)  # ✅ Store ID for frontend
        fb_roles["outlet_passer"] = None
        fb_roles["outlet_receiver"] = None
        fb_roles["outlet_score"] = None  # No outlet pass on steals

        # Previous logic added additional offensive players to the fast break,
        # potentially scheduling runners beyond the ball handler. The current
        # approach freezes all non-ball-handlers so no extra offense is added
        # to the break.
        # for pos in ["PG", "SG", "SF"]:
        #     if off_lineup[pos] != ball_handler:
        #         if random.random() < {"PG": 0.5, "SG": 0.4, "SF": 0.05}.get(pos, 0):
        #             fb_roles["offense"].append(off_lineup[pos])

    target_is_away = off_team.team_id == game.away_team.team_id
    fb_roles["defense"] = get_in_play_defenders(ball_handler, def_lineup, target_is_away)
    
    # If no defenders are ahead, add defensive PG as chaser
    # This ensures we always have at least one defender for animation purposes
    if not fb_roles["defense"]:
        defensive_pg = def_lineup.get("PG")
        if defensive_pg:
            fb_roles["defense"] = [defensive_pg]
            print(f"⚡ Fast Break: No defenders ahead, adding defensive PG {get_name_safe(defensive_pg)} as chaser")

    # Defensive pressure check
    die = random.randint(1, 6)
    bh_x = getattr(ball_handler, "coords", {}).get("x", 0)
    break_score = ball_handler.attributes["AG"] + ball_handler.attributes["BH"] * die
    best_defender = None
    best_stop_score = float("-inf")
    for defender in fb_roles["defense"]:
        stop_score = defender.attributes["AG"] + defender.attributes["OD"] * die
        d_x = getattr(defender, "coords", {}).get("x", 0)
        if (
            best_defender is None
            or stop_score > best_stop_score
            or (
                stop_score == best_stop_score
                and (
                    abs(d_x - bh_x)
                    < abs(getattr(best_defender, "coords", {}).get("x", 0) - bh_x)
                )
            )
            or (
                stop_score == best_stop_score
                and abs(d_x - bh_x)
                == abs(getattr(best_defender, "coords", {}).get("x", 0) - bh_x)
                and defender.player_id < best_defender.player_id
            )
        ):
            best_stop_score = stop_score
            best_defender = defender

    hold_up = False
    stopper_id = None
    if best_defender and best_stop_score >= break_score:
        hold_up = True
        stopper_id = best_defender.player_id

    # ✅ NEW LOGIC: Determine event type based on defender positions relative to ball handler
    # Note: This will override hold_up/stopper_id if a defender is ahead after outlet pass
    # after outlet pass simulation (matching frontend outlet pass animation)
    
    # ✅ SS&S: Determine if away team is on offense using offense_team_id
    # Using team_id is more explicit and traceable than a derived boolean
    is_away_offense = off_team.team_id == game.away_team.team_id
    
    # ✅ DEBUG: Log offense team determination
    logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Offense team determination:")
    logging.debug(f"  off_team.team_id: {off_team.team_id}")
    logging.debug(f"  game.away_team.team_id: {game.away_team.team_id}")
    logging.debug(f"  game.home_team.team_id: {game.home_team.team_id}")
    logging.debug(f"  is_away_offense: {is_away_offense}")
    
    # Determine direction toward basket
    # Home offense: basket at x=90, so direction = +1 (right)
    # Away offense: basket at x=10, so direction = -1 (left)
    if is_away_offense:
        # Away offense: smaller x is closer to basket
        direction = -1
        basket_x = 10
    else:
        # Home offense: larger x is closer to basket
        direction = 1
        basket_x = 90
    
    # ============================================================================
    # STEAL ENTRY vs OUTLET PASS: Different logic for steals vs rebounds
    # ============================================================================
    if rebound:
        # ==================== DREB → FAST BREAK: OUTLET PASS LOGIC ====================
        # Simulate ball handler position after outlet pass
        # Frontend logic: ball handler moves 5-10 spots toward basket, ±6 Y
        # ✅ SS&S: PRIORITIZE release/get-back coordinates for ball handler
        # The outlet receiver is typically a release player (defensive team), so check release coords first
        # Then check get-back coordinates (for offensive players who might be ball handler)
        ball_handler_start_x = None
        ball_handler_start_y = None
        
        ball_handler_id = getattr(ball_handler, "player_id", None)
        logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Looking for coordinates for ball_handler_id: {ball_handler_id}")
        
        # ✅ SS&S: Use helper function to find most recent shot turn
        most_recent_shot_turn = _find_most_recent_shot_turn(game, max_turns=10)
        if most_recent_shot_turn:
            # FIRST: Check if ball handler is a release player (outlet receiver is typically a release player)
            release_coords = most_recent_shot_turn.get("defense_release_coords", {})
            if release_coords and ball_handler_id and ball_handler_id in release_coords:
                stored_coords = release_coords[ball_handler_id]
                ball_handler_start_x = stored_coords.get("x")
                ball_handler_start_y = stored_coords.get("y")
                logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] ✅ Using release coords for ball handler: {ball_handler_start_x}, {ball_handler_start_y}")
            else:
                # SECOND: Check if ball handler is a get-back player
                getback_coords = most_recent_shot_turn.get("offense_getback_coords", {})
                if getback_coords and ball_handler_id and ball_handler_id in getback_coords:
                    stored_coords = getback_coords[ball_handler_id]
                    ball_handler_start_x = stored_coords.get("x")
                    ball_handler_start_y = stored_coords.get("y")
                    logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] ✅ Using get-back coords for ball handler: {ball_handler_start_x}, {ball_handler_start_y}")
        
        # FALLBACK: Use player.coords if not a release/get-back player or coords not found
        if ball_handler_start_x is None or ball_handler_start_y is None:
            ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
            ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)
            logging.warning(f"🏀 [FAST BREAK PHASE DEBUG] ⚠️ Using player.coords (fallback): {ball_handler_start_x}, {ball_handler_start_y}")
            logging.warning(f"🏀 [FAST BREAK PHASE DEBUG] ⚠️ This suggests ball handler is NOT a release/get-back player or coords not found in previous turn")
        
        # Simulate ball handler position after outlet pass (NO MOVEMENT - receives pass at starting position)
        # Ball handler will only move during defensive stop/shot attempt step
        ball_handler_move_x = 0
        ball_handler_move_y = 0
        ball_handler_outlet_x = ball_handler_start_x  # No movement during outlet pass
        ball_handler_outlet_y = ball_handler_start_y  # No movement during outlet pass
        
        # ✅ DEBUG: Log outlet position calculation
        logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Outlet position calculation:")
        logging.debug(f"  ball_handler_start_x: {ball_handler_start_x}")
        logging.debug(f"  ball_handler_start_y: {ball_handler_start_y}")
        logging.debug(f"  direction: {direction}")
        logging.debug(f"  ball_handler_move_x: {ball_handler_move_x}")
        logging.debug(f"  ball_handler_move_y: {ball_handler_move_y}")
        logging.debug(f"  ball_handler_outlet_x: {ball_handler_outlet_x}")
        logging.debug(f"  ball_handler_outlet_y: {ball_handler_outlet_y}")
        logging.debug(f"  calculation: {ball_handler_start_x} + {direction} * {ball_handler_move_x} = {ball_handler_outlet_x}")
        logging.debug(f"📍 [OUTLET RECEIVER] Receives pass at: x={ball_handler_outlet_x}, y={ball_handler_outlet_y} (HOME orientation)")
    else:
        # ==================== STEAL → FAST BREAK: STEAL ENTRY LOGIC ====================
        # Stealer (ball handler) moves 5-10 x spots toward basket, ±4 y spots (clamped to 3-47)
        # This movement happens BEFORE checking for defensive stop vs shot
        # ✅ FIX: Use stored stealer position from skeleton step (if available)
        if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
            stealer_coords = game_state["last_stealer_coords"]
            ball_handler_start_x = stealer_coords.get("x", 50)
            ball_handler_start_y = stealer_coords.get("y", 25)
        else:
            ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
            ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)
        
        # Calculate steal entry movement
        steal_entry_move_x = random.randint(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX)
        steal_entry_move_y = random.randint(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE)
        
        # Apply movement toward basket
        ball_handler_after_entry_x = ball_handler_start_x + (direction * steal_entry_move_x)
        ball_handler_after_entry_y = max(STEAL_ENTRY_Y_MIN, min(STEAL_ENTRY_Y_MAX, ball_handler_start_y + steal_entry_move_y))
        
        # Store steal entry movement for animation
        ball_handler_move_x = steal_entry_move_x
        ball_handler_move_y = steal_entry_move_y
        ball_handler_outlet_x = ball_handler_after_entry_x  # Position after steal entry movement
        ball_handler_outlet_y = ball_handler_after_entry_y  # Position after steal entry movement
    
    # Store ball handler position for animation (after outlet pass for DREB, after steal entry for steals)
    fb_roles["ball_handler_outlet_x"] = ball_handler_outlet_x
    fb_roles["ball_handler_outlet_y"] = ball_handler_outlet_y
    fb_roles["ball_handler_move_x"] = ball_handler_move_x
    fb_roles["ball_handler_move_y"] = ball_handler_move_y
    fb_roles["is_away_offense"] = is_away_offense  # ✅ Store for animator to use
    fb_roles["is_steal_entry"] = not rebound  # ✅ Flag to indicate steal entry vs outlet pass
    
    # ✅ SS&S: Clear steal-related data after using it (so it doesn't persist to subsequent turns)
    if not rebound:
        game_state.pop("last_stealer_coords", None)
        game_state["last_stealer"] = None
    
    # ✅ FIX: Use actual defender coordinates instead of simulating random positions
    # Defenders are already positioned on the court after the shot attempt
    # They don't move during the outlet pass - only the ball handler moves
    # So we compare ball handler's outlet position to defender's actual current position
    # ✅ NEW: Defender must be ahead AND within ±6 y-coords to force defensive stop
    # If multiple get-back players meet both conditions, the closest one forces the stop
    # If no defender meets both conditions, it's a shot attempt and closest defender overall becomes shot defender
    defender_ahead = False
    closest_stopping_defender = None  # Defender who is ahead AND within ±6 y-coords
    closest_stopping_distance = float('inf')
    closest_defender_overall = None  # Closest defender overall (for shot attempts, uses Euclidean distance)
    closest_distance_overall = float('inf')
    
    # ✅ Find the most recent MISS/MAKE turn (the one that triggered this fast break)
    # Only use get-back coords from THIS turn, not from previous turns
    # ✅ SS&S: Use helper function to find most recent shot turn
    most_recent_shot_turn = _find_most_recent_shot_turn(game, max_turns=10)
    getback_player_ids = []
    if most_recent_shot_turn:
        getback_player_ids = most_recent_shot_turn.get("offense_getback", [])
    
    # ✅ Store get-back player IDs in fb_roles for animator to use
    fb_roles["getback_player_ids"] = getback_player_ids
    
    # ✅ Log all get-back players and their coordinates from the most recent shot attempt
    logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Most recent shot turn:")
    if most_recent_shot_turn:
        turn_result_type = most_recent_shot_turn.get("result_type")
        getback_coords = most_recent_shot_turn.get("offense_getback_coords", {})
        getback_player_ids = most_recent_shot_turn.get("offense_getback", [])
        
        logging.debug(f"  Found {turn_result_type} turn:")
        logging.debug(f"  offense_getback (player IDs): {getback_player_ids}")
        logging.debug(f"  offense_getback_coords keys: {list(getback_coords.keys()) if getback_coords else 'None'}")
        
        if getback_coords:
            logging.debug(f"  Get-back players with coordinates:")
            for player_id, coords in getback_coords.items():
                logging.debug(f"    Get-back player {player_id}: x={coords.get('x')}, y={coords.get('y')}")
        elif getback_player_ids:
            logging.warning(f"  ⚠️ WARNING: Get-back player IDs exist but no coordinates stored!")
            logging.warning(f"    Player IDs: {getback_player_ids}")
        else:
            logging.debug(f"  No get-back players in this turn")
    else:
        logging.warning(f"  ⚠️ No MISS or MAKE turn found in last 10 turns")
    
    # ✅ FIX: Check ALL defenders in def_lineup, not just those in fb_roles["defense"]
    # The get_in_play_defenders() function uses stale ball_handler.coords, which might exclude
    # get-back players who are actually ahead of the outlet receiver position
    # We need to check all defenders against the outlet receiver position (ball_handler_outlet_x)
    logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Checking {len(def_lineup)} defenders for defensive stop")
    logging.debug(f"  Ball handler outlet position: x={ball_handler_outlet_x}, y={ball_handler_outlet_y}")
    
    for defender in def_lineup.values():
        # Use defender's actual coordinates (where they are on the court)
        # These defenders are the team that was on offense during the shot attempt
        # They might have get-back coordinates stored, so check those first
        defender_actual_x = None
        defender_actual_y = None
        defender_id = getattr(defender, "player_id", None)
        
        # ✅ Check if defender has get-back coordinates from the MOST RECENT shot attempt only
        # Only use get-back coords if this defender was actually a get-back player in the turn that triggered this fast break
        if most_recent_shot_turn and defender_id:
            logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Looking for get-back coords for defender {defender_id}")
            getback_coords = most_recent_shot_turn.get("offense_getback_coords", {})
            logging.debug(f"  Most recent {most_recent_shot_turn.get('result_type')} turn, getback_coords keys: {list(getback_coords.keys()) if getback_coords else 'None'}")
            if getback_coords and defender_id in getback_coords:
                stored_coords = getback_coords[defender_id]
                defender_actual_x = stored_coords.get("x")
                defender_actual_y = stored_coords.get("y")
                logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] ✅ Using get-back coords for defender {defender_id}: {defender_actual_x}, {defender_actual_y}")
            elif getback_coords:
                logging.debug(f"  ⚠️ Defender {defender_id} not found in getback_coords (not a get-back player in most recent shot)")
            else:
                logging.debug(f"  ⚠️ No getback_coords in most recent shot turn")
        
        # Fallback to defender's current coords if no get-back coords found
        if defender_actual_x is None or defender_actual_y is None:
            defender_actual_x = getattr(defender, "coords", {}).get("x", 50)
            defender_actual_y = getattr(defender, "coords", {}).get("y", 25)
            logging.warning(f"🏀 [FAST BREAK PHASE DEBUG] ⚠️ Using defender.coords (fallback) for defender {defender_id}: {defender_actual_x}, {defender_actual_y}")
        
        # ✅ Defender position after outlet step (NO MOVEMENT - same as ball handler)
        # Defenders stay at their starting position during outlet pass, only move during defensive stop/shot attempt
        defender_move_x = 0
        defender_move_y = 0
        defender_outlet_x = defender_actual_x  # No movement during outlet pass
        defender_outlet_y = defender_actual_y  # No movement during outlet pass
        
        # Store defender outlet position for animation
        if not hasattr(defender, "outlet_coords"):
            defender.outlet_coords = {}
        defender.outlet_coords["x"] = defender_outlet_x
        defender.outlet_coords["y"] = defender_outlet_y
        
        # Check if defender is ahead of ball handler (using outlet positions after both have moved)
        # ✅ FIX: Compare in HOME orientation for both home and away offense
        # Coordinates are stored in HOME orientation, so we compare directly in HOME orientation
        # For away offense: basket is at x=10, smaller x is closer → defender ahead if x <= ball handler x
        # For home offense: basket is at x=90, larger x is closer → defender ahead if x >= ball handler x
        # ✅ NEW: Defender must also be within ±6 y-coords to force defensive stop
        
        logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Defender comparison for {defender_id}:")
        logging.debug(f"  defender_actual_x (start, HOME): {defender_actual_x}")
        logging.debug(f"  defender_actual_y (start, HOME): {defender_actual_y}")
        logging.debug(f"  defender_move_x: {defender_move_x}")
        logging.debug(f"  defender_outlet_x (after outlet step, HOME): {defender_outlet_x}")
        logging.debug(f"  defender_outlet_y (after outlet step, HOME): {defender_outlet_y}")
        logging.debug(f"  ball_handler_outlet_x (after outlet step, HOME): {ball_handler_outlet_x}")
        logging.debug(f"  ball_handler_outlet_y (after outlet step, HOME): {ball_handler_outlet_y}")
        logging.debug(f"  is_away_offense: {is_away_offense}")
        
        # Calculate distance for closest defender tracking (for shot attempts)
        x_distance = abs(defender_outlet_x - ball_handler_outlet_x)
        y_distance = abs(defender_outlet_y - ball_handler_outlet_y)
        total_distance = (x_distance ** 2 + y_distance ** 2) ** 0.5  # Euclidean distance
        
        # Track closest defender overall (for shot attempts)
        if total_distance < closest_distance_overall:
            closest_distance_overall = total_distance
            closest_defender_overall = defender
        
        # Check if defender is ahead (x-coordinate check)
        if is_away_offense:
            # Away offense: basket at x=10 in HOME orientation, smaller x is closer to basket
            # Defender ahead if defender_x <= ball_handler_x (defender is closer to x=10)
            is_ahead = defender_outlet_x <= ball_handler_outlet_x
            logging.debug(f"  X Comparison (HOME orientation, away offense): {defender_outlet_x} <= {ball_handler_outlet_x} = {is_ahead}")
        else:
            # Home offense: basket at x=90 in HOME orientation, larger x is closer to basket
            # Defender ahead if defender_x >= ball_handler_x (defender is closer to x=90)
            is_ahead = defender_outlet_x >= ball_handler_outlet_x
            logging.debug(f"  X Comparison (HOME orientation, home offense): {defender_outlet_x} >= {ball_handler_outlet_x} = {is_ahead}")
        
        # ✅ NEW: Check if defender is within ±6 y-coords of outlet receiver
        y_diff = abs(defender_outlet_y - ball_handler_outlet_y)
        is_within_y_range = y_diff <= DEFENSIVE_STOP_Y_RANGE
        logging.debug(f"  Y Comparison: |{defender_outlet_y} - {ball_handler_outlet_y}| = {y_diff} <= 6 = {is_within_y_range}")
        
        # Defender can force defensive stop if: ahead AND within y-range
        if is_ahead and is_within_y_range:
            defender_ahead = True
            logging.debug(f"  ✅ Defender can force DEFENSIVE_STOP! (ahead AND within y-range)")
            # Find closest stopping defender (x-distance only, as per original logic)
            x_distance_only = abs(defender_outlet_x - ball_handler_outlet_x)
            if x_distance_only < closest_stopping_distance:
                closest_stopping_distance = x_distance_only
                closest_stopping_defender = defender
        elif is_ahead:
            logging.debug(f"  ⚠️ Defender is ahead but NOT within y-range (y_diff={y_diff}), cannot force defensive stop")
        else:
            logging.debug(f"  ❌ Defender is NOT ahead")
    
    # ✅ If we found a stopping defender who wasn't in fb_roles["defense"], add them for animation
    if closest_stopping_defender and closest_stopping_defender not in fb_roles["defense"]:
        fb_roles["defense"].append(closest_stopping_defender)
        logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Added stopping defender to fb_roles['defense']: {get_name_safe(closest_stopping_defender)} (was not in initial list)")
    
    # ✅ For shot attempts, store closest defender overall as shot defender
    if closest_defender_overall:
        fb_roles["shot_defender"] = closest_defender_overall
        logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Closest defender overall (for shot attempts): {get_name_safe(closest_defender_overall)}, distance: {closest_distance_overall:.2f}")
    
    # Determine event type based on defender positions
    d_count = len(fb_roles["defense"])
    
    # Store defender count for shot resolution logic
    fb_roles["defender_count"] = d_count
    
    # ==================== STAT TRACKING ====================
    # Track Fast Break defender count for offense team (team running the break)
    if not hasattr(off_team, 'team_stats'):
        off_team.team_stats = {}
    
    if d_count == 0:
        off_team.team_stats['zero_defenders_back'] = off_team.team_stats.get('zero_defenders_back', 0) + 1
    elif d_count == 1:
        off_team.team_stats['one_defender_back'] = off_team.team_stats.get('one_defender_back', 0) + 1
    else:  # d_count >= 2
        off_team.team_stats['two_defenders_back'] = off_team.team_stats.get('two_defenders_back', 0) + 1
    # ==================== END STAT TRACKING ====================

    # ✅ NEW LOGIC: If any defender is ahead of ball handler → defensive stop
    # Otherwise → shot attempt
    logging.debug(f"🏀 [FAST BREAK PHASE DEBUG] Final determination:")
    logging.debug(f"  d_count: {d_count}")
    logging.debug(f"  defender_ahead: {defender_ahead}")
    logging.debug(f"  ball_handler_outlet_x: {ball_handler_outlet_x}")
    logging.debug(f"  is_away_offense: {is_away_offense}")
    
    if d_count == 0:
        # 0 defenders: Always shot
        event_type = "SHOT"
        logging.debug(f"  ✅ Decision: SHOT (0 defenders)")
    elif defender_ahead and closest_stopping_defender:
        # Defender ahead AND within ±6 y-coords: defensive stop
        event_type = "DEFENSIVE_STOP"
        logging.debug(f"  ✅ Decision: DEFENSIVE_STOP (defender ahead AND within ±6 y-coords)")
        logging.debug(f"  closest_stopping_defender: {get_name_safe(closest_stopping_defender)}")
        logging.debug(f"  closest_stopping_distance: {closest_stopping_distance}")
        # Store closest stopping defender as stopper (override previous stopper logic)
        if closest_stopping_defender:
            stopper_id = closest_stopping_defender.player_id
            best_defender = closest_stopping_defender
            hold_up = True  # Set hold_up since we're stopping the break
            closest_defender = closest_stopping_defender  # For compatibility with existing code
    else:
        # No defender ahead AND within y-range: shot attempt
        # Use closest defender overall as shot defender
        event_type = "SHOT"
        if closest_defender_overall:
            logging.debug(f"  ✅ Decision: SHOT (no defender ahead within y-range)")
            logging.debug(f"  closest_defender_overall (shot defender): {get_name_safe(closest_defender_overall)}")
            logging.debug(f"  closest_distance_overall: {closest_distance_overall:.2f}")
            # Store closest defender overall as shot defender for animation
            fb_roles["defender"] = closest_defender_overall
        else:
            logging.debug(f"  ✅ Decision: SHOT (no defender ahead)")
            # Fallback: use first defender in list if available
            if fb_roles["defense"] and len(fb_roles["defense"]) > 0:
                fb_roles["defender"] = fb_roles["defense"][0]

    # ==================== OUTLET PASS STAT TRACKING ====================
    # Record outlet pass stats if outlet pass occurred
    outlet_passer_id = fb_roles.get("outlet_passer")
    outlet_score = fb_roles.get("outlet_score")
    if outlet_passer_id and outlet_score is not None:
        # Outlet pass is successful if it leads to a shot attempt (not defensive stop)
        is_successful = (event_type == "SHOT")
        _record_outlet_pass_stats(outlet_passer_id, outlet_score, is_successful, game)
    # ==================== END OUTLET PASS STAT TRACKING ====================

    # If defensive stop triggered, defense stopped the fast break
    # NOTE: This should NOT happen if has_outlet_pass is True (handled above)
    if event_type == "DEFENSIVE_STOP":
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
        game.game_state["offensive_state"] = "HCO"
        
        # Build animation packet for the fast break play (for outlet pass animation)
        animator = Animator(game)
        animations = animator.capture_fast_break_animation(
            fb_roles, hold_up, stopper_id
        )
        
        # Return a defensive stop result but include Fast Break roles and flags
        # This ensures the frontend can animate the outlet pass before showing the stop
        ball_handler = fb_roles["ball_handler"]
        defender_name = get_name_safe(best_defender) if best_defender else "Defense"
        result = {
            "result_type": "DEFENSIVE_STOP",
            "ball_handler": ball_handler,
            "defender": best_defender,
            "text": f"Fast Break! Nice stop by {defender_name}!",
            "possession_flips": False,
            "time_elapsed": 3,
            "animations": animations,
            "current_turn": "FAST_BREAK",  # ✅ SS&S: Explicit turn type
            "next_play_type": "HCO",
            "next_turn": "HCO",  # ✅ SS&S: Explicit next turn
            "offense_team_id": off_team.team_id,  # ✅ FIX: Add offense_team_id (possession doesn't flip, same team continues)
            "roles": fb_roles,  # ✅ Include roles so frontend can animate outlet pass
            "fast_break": True,  # Legacy flag for backwards compatibility
        }
        
        # ✅ DEBUG: Log fast break defensive stop result to verify data is being set correctly
        import json
        debug_data = {
            "result_type": result.get("result_type"),
            "fast_break": result.get("fast_break"),
            "has_roles": "roles" in result,
            "outlet_passer": fb_roles.get("outlet_passer"),
            "outlet_receiver": fb_roles.get("outlet_receiver"),
            "ball_handler_id": getattr(ball_handler, "player_id", None) if ball_handler else None,
            "has_animations": len(animations) > 0 if animations else False,
            "animation_count": len(animations) if animations else 0
        }
        logging.debug(f"🏀 [FAST BREAK DEBUG] DEFENSIVE_STOP result created: {json.dumps(debug_data, default=str)}")
        
        if hold_up:
            result["hold_up"] = True
            result["stopper_id"] = stopper_id
        
        # ==================== FAST BREAK STAT TRACKING ====================
        # Record Fast Break stats for release player (offensive) and get-back players (defensive)
        _record_fast_break_stats(fb_roles, result, game)
        # ==================== END FAST BREAK STAT TRACKING ====================
        
        return result

    #get shooter and passer (if applicable)
    # Assign shooter and passer for shot, turnover, or foul scenarios
    offense_in_play = [fb_roles["ball_handler"]] + fb_roles["offense"]
    shooter = random.choice(offense_in_play)

    fb_roles["shooter"] = shooter
    
    # Determine passer for assist tracking
    shooter_id = getattr(shooter, "player_id", None)
    outlet_receiver_id = fb_roles.get("outlet_receiver")
    outlet_passer_id = fb_roles.get("outlet_passer")
    
    # If shooter is the outlet receiver (who received the outlet pass after DREB), passer is the outlet passer (rebounder)
    if outlet_receiver_id and outlet_passer_id and shooter_id == outlet_receiver_id:
        # Find the outlet passer player object
        passer = None
        for player in off_team.get_all_players():
            if getattr(player, "player_id", None) == outlet_passer_id:
                passer = player
                break
        fb_roles["passer"] = passer
    # Otherwise, if shooter is not the ball handler, then ball handler is the passer
    elif shooter != fb_roles["ball_handler"]:
        fb_roles["passer"] = fb_roles["ball_handler"]
    else:
        fb_roles["passer"] = None
    
    fb_roles["screener"] = None

    # Foul or turnover possibilities
    if event_type == "O_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "OFFENSE"
    elif event_type == "D_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "DEFENSE"

    # print(f"Event type: {event_type}")
    # print(f"Roles: {fb_roles}")
    
    if event_type == "SHOT":
        shot_manager = ShotManager(game)
        turn_result = shot_manager.resolve_fast_break_shot(fb_roles)

    elif event_type == "TURNOVER":
        turnover_type = random.choice(["STEAL", "DEAD BALL"])
        turn_result = resolve_turnover_logic(fb_roles, game, turnover_type)
    elif event_type == "FOUL":
        turn_result = resolve_non_shooting_foul(fb_roles, game)
    
    if turn_result["result_type"] == "MAKE": #def_scouting
        off_scouting["offense"]["Fast_Break_Success"] += 1

    elif turn_result["result_type"] == "FOUL":
        if game_state.get("foul_team") == "DEFENSE":
            off_scouting["offense"]["Fast_Break_Success"] += 1
        elif game_state.get("foul_team") == "OFFENSE":
            def_scouting["defense"]["vs_Fast_Break"]["success"] += 1

    elif turn_result["result_type"] in ["MISS", "TURNOVER"]:
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1


    # Build animation packet for the fast break play
    animator = Animator(game)
    turn_result["animations"] = animator.capture_fast_break_animation(
        fb_roles, hold_up, stopper_id
    )
    turn_result["roles"] = fb_roles
    turn_result["fast_break"] = True  # ✅ Add fast_break flag for frontend routing
    
    # ==================== FAST BREAK STAT TRACKING ====================
    # Record Fast Break stats for release player (offensive) and get-back players (defensive)
    _record_fast_break_stats(fb_roles, turn_result, game)
    # ==================== END FAST BREAK STAT TRACKING ====================
    
    # ✅ DEBUG: Log fast break result (MAKE/MISS/TURNOVER/FOUL) to verify data is being set correctly
    import json
    debug_data = {
        "result_type": turn_result.get("result_type"),
        "fast_break": turn_result.get("fast_break"),
        "has_roles": "roles" in turn_result,
        "outlet_passer": fb_roles.get("outlet_passer"),
        "outlet_receiver": fb_roles.get("outlet_receiver"),
        "ball_handler_id": getattr(fb_roles.get("ball_handler"), "player_id", None) if fb_roles.get("ball_handler") else None,
        "has_animations": len(turn_result.get("animations", [])) > 0,
        "animation_count": len(turn_result.get("animations", []))
    }
    logging.debug(f"🏀 [FAST BREAK DEBUG] {turn_result.get('result_type')} result created: {json.dumps(debug_data, default=str)}")
    if hold_up:
        turn_result["hold_up"] = True
        turn_result["stopper_id"] = stopper_id
    
    # Prepend "Fast Break!" to the text
    turn_result["text"] = "Fast Break! " + turn_result.get("text", "")

    # ✅ Add safety checks before returning
    assert turn_result is not None, "turn_result is None"
    assert "time_elapsed" in turn_result, "turn_result missing 'time_elapsed'"
    return turn_result

def resolve_free_throw_logic(game):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    shooter = game_state.get("shooter") or game_state.get("last_ball_handler")
    if shooter is None:
        raise HTTPException(status_code=400, detail="No shooter set for free throw")
    attrs = shooter.attributes

    # FT outcome calculation
    # Formula: (FT * 0.7) + (CH * 0.2) + MO
    ft_shot_score = (attrs["FT"] * 0.7) + (attrs["CH"] * 0.2) + attrs["MO"]
    result = random.randint(1, 100)
    text = f"ft_shot_score: {ft_shot_score}, roll: {result}  "
    makes_shot = result < ft_shot_score

    shooter.record_stat("FTA")
    text += f"{get_name_safe(shooter)} steps to the line... "
    possession_flips = False

    attempts = ["MAKE" if makes_shot else "MISS"]
    animator = Animator(game)
    animations = animator.capture_free_throw_animation(
        game,
        shooter,
        attempts,
        offense_is_home=(off_team.team_id == game.home_team.team_id),
        no_lane=game_state.get("no_lane", False),
    )
    shooter_pos = get_player_position(off_lineup, shooter)

    if makes_shot:
        apply_scoring(game, off_team, shooter, 1, ["FTM"])
        text += "and hits the free throw!"
    else:
        text += "but misses the free throw."

    # Handle 1-and-1 front-end logic
    if game_state.get("one_and_one", False):
        if game_state["free_throws_remaining"] == 1:
            if makes_shot:
                # Made front end → unlock second FT
                game_state["free_throws_remaining"] = 1
                game_state["one_and_one"] = False
                return {
                    "result_type": "FREE_THROW",
                    "ball_handler": shooter,
                    "shooter": shooter,
                    "text": text,
                    "time_elapsed": 0,
                    "possession_flips": False,
                    "points": 1,
                    "scoring_team": off_team.name,
                    "animations": animations,
                    "attempts": attempts,
                    "shooter_id": getattr(shooter, "player_id", None),
                    "shooter_pos": shooter_pos,
                    "offense_team_id": off_team.team_id,
                    "no_lane": game_state.get("no_lane", False),
                    "free_throws_remaining": game_state["free_throws_remaining"],  # ✅ FIX: Include free_throws_remaining so frontend knows more FTs remain
                    "one_and_one": False,  # ✅ FIX: Include one_and_one flag (now False since second FT is unlocked)
                }
            else:
                # Missed front end → dead ball, rebound
                game_state["free_throws_remaining"] = 0
                game_state["one_and_one"] = False
                game_state["offensive_state"] = "HCO"

    # Standard decrement for non-1-and-1 logic
    game_state["free_throws_remaining"] -= 1

    # If no FTs remain, determine next state
    if game_state["free_throws_remaining"] <= 0:
        # Check for defensive pressure if the last FT was made
        if makes_shot:
            from BackEnd.models.turn_manager import TurnManager
            pressure_type = TurnManager(game).determine_defensive_pressure_type()
            game_state["offensive_state"] = pressure_type
            # print(f"🏀 Last FT made - setting offensive_state to: {pressure_type}")
        else:
            game_state["offensive_state"] = "HCO"

        if not makes_shot:
            # Rebound logic
            rebounder_dict = default_rebounder_dict()
            o_pos = choose_rebounder(rebounder_dict, "offense")
            d_pos = choose_rebounder(rebounder_dict, "defense")
            o_rebounder = off_lineup[o_pos]
            d_rebounder = def_lineup[d_pos]

            o_score = calculate_rebound_score(o_rebounder)
            d_score = calculate_rebound_score(d_rebounder)

            off_mod = off_team.team_attributes["rebound_modifier"]
            def_mod = def_team.team_attributes["rebound_modifier"]
            bias = def_mod - off_mod
            def_prob = min(0.95, max(0.55, 0.75 + bias))

            total = d_score + o_score
            d_weight = d_score / total if total > 0 else 0.5
            d_weight += (def_prob - 0.5)
            d_weight = min(0.95, max(0.05, d_weight))

            rebound_team = def_team if random.random() < d_weight else off_team
            rebounder = d_rebounder if rebound_team == def_team else o_rebounder
            stat = "DREB" if rebound_team == def_team else "OREB"
            game_state["last_rebound"] = stat
            game_state["last_rebounder"] = rebounder
            
            # ✅ Record rebound stat BEFORE checking team (applies to both DREB and OREB)
            rebounder.record_stat(stat)
            
            # Debug logging for free throw rebounds
            # ✅ COMMENTED OUT: Free throw rebound logs (cluttering transition debugging)
            # logging.info(f"🏀 Free Throw Rebound: {get_name_safe(rebounder)} credited with {stat} (Free Throw miss)")
            rebounder_game_reb = rebounder.stats["game"].get(stat, 0)
            # logging.info(f"🏀 Free Throw Rebound: {get_name_safe(rebounder)} now has {rebounder_game_reb} {stat} (game total)")

            if rebound_team == def_team:
                possession_flips = True
                text += f" {get_name_safe(rebounder)} grabs the defensive rebound."
                next_play_type = "FAST_BREAK" if random.random() < get_fast_break_chance(game) else "HCO"
                game_state["offensive_state"] = next_play_type
            else:
                # Offensive rebound - store for separate turn processing
                game_state["pending_oreb"] = {
                    "rebounder": rebounder,
                    "rebounder_id": getattr(rebounder, "player_id", None),
                }
                text += f" {get_name_safe(rebounder)} grabs the offensive rebound."
                # OREB will be processed as a separate turn
        else:
            if not game_state.get("no_lane", False):
                possession_flips = True
    # When additional free throws remain, possession stays with the shooter’s team

    result = {
        "result_type": "FREE_THROW",
        "ball_handler": shooter,
        "shooter": shooter,
        "text": text,
        "time_elapsed": 0,  # clock does not run
        "possession_flips": possession_flips,
        "animations": animations,
        "attempts": attempts,
        "shooter_id": getattr(shooter, "player_id", None),
        "shooter_pos": shooter_pos,
        "offense_team_id": off_team.team_id,
        "current_turn": "FREE_THROW",  # ✅ SS&S: Explicit turn type
        "no_lane": game_state.get("no_lane", False),
        "free_throws_remaining": game_state["free_throws_remaining"],  # For frontend to know if final FT
        "one_and_one": game_state.get("one_and_one", False),  # For frontend 1&1 display
    }

    if makes_shot:
        result["points"] = 1
        result["scoring_team"] = off_team.name
        # Add next_defensive_setup if final FT was made
        if game_state["free_throws_remaining"] <= 0:
            result["next_defensive_setup"] = game_state.get("offensive_state", "HCO")
            # ✅ FIX 2: Set next_play_type so backend creates BASELINE_INBOUND turn (Pattern A)
            result["next_play_type"] = "BASELINE_INBOUND"
            result["next_turn"] = "BASELINE_INBOUND"  # ✅ SS&S: Explicit next turn
    else:
        # Add rebounder information for missed free throws
        if game_state.get("last_rebounder"):
            result["rebounderId"] = getattr(game_state["last_rebounder"], "player_id", None)
            result["rebound_type"] = game_state.get("last_rebound", "")
            # Add next play type for defensive rebounds
            if game_state.get("last_rebound") == "DREB":
                result["next_play_type"] = game_state.get("offensive_state", "HCO")

    return result


def resolve_turnover_logic(roles, game, turnover_type="DEAD BALL"):

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    ball_handler = roles["ball_handler"]
    defender = roles.get("defender")
    ball_handler.record_stat("TO")
    # ✅ FIX: Only use random choice if turnover_type is not explicitly provided
    # This respects the actual turnover type instead of always randomizing
    if turnover_type == "DEAD BALL" and defender:
        # If defender is present, could be either STEAL or DEAD BALL
        # Use random choice only when both are possible
        turnover_type = random.choice(["STEAL", "DEAD BALL"])
    elif turnover_type == "DEAD BALL":
        # No defender, must be DEAD BALL
        turnover_type = "DEAD BALL"
    # If turnover_type is already "STEAL", keep it as STEAL
    game_state["last_turnover_player"] = ball_handler

    # Pre-compute IDs/names for logging and return payload
    stealer_id = getattr(defender, "player_id", None)
    stealer_name = get_name_safe(defender) if defender else None
    victim_id = getattr(ball_handler, "player_id", None)
    victim_name = get_name_safe(ball_handler)
    events = []

    if turnover_type == "STEAL" and defender:
        defender.record_stat("STL")
        text = f"{stealer_name} jumps the pass"
        fast_break_chance = get_fast_break_chance(game)
        fast_break_roll = random.random()
        if fast_break_roll < fast_break_chance:
            game_state["offensive_state"] = "FAST_BREAK"
            text += " and takes it the other way!"
        else:
            game_state["offensive_state"] = "HCO"
            text += " and waits to set up the half-court offense."
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""
        
        # ✅ FIX: Use stored stealer position from skeleton step (if available)
        # This ensures intermediate steps use the position at the exact moment of the steal
        if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
            stealer_coords = game_state["last_stealer_coords"]
            defender.coords = stealer_coords.copy()
            logging.warning(f"🏀 [STEAL POSITION] Using stored stealer position: x={stealer_coords['x']}, y={stealer_coords['y']}")
        else:
            logging.warning(f"⚠️ [STEAL POSITION] No stored stealer position, using defender.coords: x={getattr(defender, 'coords', {}).get('x', 'N/A')}, y={getattr(defender, 'coords', {}).get('y', 'N/A')}")
        
        # ✅ DEBUG: Log steal flow for HCO steals
        logging.warning(f"🏀 [STEAL FLOW] HCO Steal detected:")
        logging.warning(f"  Stealer: {get_name_safe(defender)} (ID: {stealer_id})")
        logging.warning(f"  Victim: {get_name_safe(ball_handler)} (ID: {victim_id})")
        logging.warning(f"  Fast break chance: {fast_break_chance:.2%}, Roll: {fast_break_roll:.3f}")
        logging.warning(f"  Next offensive_state: {game_state['offensive_state']}")
        logging.warning(f"  last_stealer SET: {get_name_safe(defender)} (ID: {stealer_id})")

        events.append({
            "event_type": "STEAL",
            "stealer_id": stealer_id,
            "victim_id": victim_id,
            "timestamp": game_state.get("time_remaining"),
            "coords": getattr(defender, "coords", None),
        })
    else:
        game_state["offensive_state"] = "HCO"
        description = random.choice([
            "throws it out of bounds",
            "commits a travel.",
            "commits a double dribble.",
            "travels with the ball.",
            "with an errant pass.",
            "dribbles it off his foot and the ball goes out of bounds."
        ])
        text = f"{victim_name} {description}"
        game_state["last_stealer"] = None

    bh_pos = get_player_position(off_lineup, ball_handler)

    # ✅ SS&S FIX: Set next_play_type when offensive_state is FAST_BREAK
    # This allows game_manager.py to flip possession before the Fast Break turn
    # Matches the pattern used in FCP/HCT steals (lines 2482, 3330)
    next_play_type = None
    if game_state.get("offensive_state") == "FAST_BREAK":
        next_play_type = "FAST_BREAK"
    elif game_state.get("offensive_state") == "HCO":
        next_play_type = "HCO"

    result = {
        "result_type": turnover_type,
        "ball_handler": ball_handler,
        "text": text,
        "time_elapsed": random.randint(3, 8),
        "possession_flips": True,  # Let the turn loop handle the flip
        "offense_team_id": game.offense_team.team_id,  # ✅ SS&S: Add offense_team_id to all results
        "current_turn": "HCO",  # ✅ SS&S: Standalone turnovers occur in HCO context
        "victim_id": victim_id,
        "victim_name": victim_name,
    }
    
    # ✅ SS&S FIX: Add next_play_type to result (only if set)
    if next_play_type:
        result["next_play_type"] = next_play_type
        result["next_turn"] = next_play_type  # ✅ SS&S: Explicit next turn

    if stealer_id:
        result["stealer_id"] = stealer_id
        result["stealer_name"] = stealer_name
    if events:
        result["events"] = events

    return result


def resolve_hco_outcome(game, skeleton):
    """
    Resolve HCO turn outcome using the new Resolution System.
    
    Processes outcomes in sequential priority order:
    1. Standard fouls (O_FOUL, D_FOUL)
    2. Steal attempt
    3. Dead ball turnover
    4. Shot attempt (with skeleton variant selection)
    
    Args:
        game: GameManager object
        skeleton: Skeleton dict (needed for step selection and variant determination)
    
    Returns:
        tuple: (result, variant_result)
            - result: "SHOT", "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", or "STEAL"
            - variant_result: For SHOT results, the skeleton variant ("successful", "mid_play_change", "contested", "broken")
                          For non-SHOT results, None
    """
    import random
    from BackEnd.constants import (
        STANDARD_D_FOUL, STANDARD_O_FOUL, HARD_STEAL, SOFT_STEAL,
        HARD_FOUL, SOFT_FOUL, SOFT_PROB, STEAL_ATTEMPT, DEAD_BALL_TURNOVER
    )
    from BackEnd.utils.shared import (
        calculate_ball_handling_score, calculate_defender_pressure_score,
        get_player_position, unpack_game_context
    )
    # get_ball_handler_from_skeleton is defined in this file (phase_resolution.py)
    from BackEnd.utils.defense_utils import is_zone_defense
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    # Step 1: Get Team Attributes and Settings
    off_attrs = off_team.team_attributes
    def_attrs = def_team.team_attributes
    
    offensive_efficiency = off_attrs.get("offensive_efficiency", 0)
    turnover_modifier = off_attrs.get("turnover_modifier", 0)
    foul_modifier_off = off_attrs.get("foul_modifier", 0)
    
    defensive_efficiency = def_attrs.get("defensive_efficiency", 0)
    foul_modifier_def = def_attrs.get("foul_modifier", 0)
    
    # Get aggression setting (0-4, where 2 is normal)
    aggression_level = def_team.strategy_calls.get("aggression", 2)
    
    # Step 2: Calibrate Universal Constants
    # Standard D Foul calibration
    calibrated_d_foul = STANDARD_D_FOUL + int(foul_modifier_def * 0.4)
    calibrated_d_foul = min(98, calibrated_d_foul)  # Max 98
    
    # Standard O Foul calibration
    calibrated_o_foul = STANDARD_O_FOUL - foul_modifier_off
    calibrated_o_foul = max(2, calibrated_o_foul)  # Min 2
    
    # Steal thresholds calibration
    calibrated_hard_steal = HARD_STEAL + turnover_modifier
    calibrated_soft_steal = SOFT_STEAL + turnover_modifier
    
    # Foul thresholds calibration (on steal attempts)
    calibrated_hard_foul = HARD_FOUL - int(foul_modifier_def * 0.6)
    calibrated_soft_foul = SOFT_FOUL - int(foul_modifier_def * 0.6)
    
    # Dead Ball Turnover calibration
    calibrated_dead_ball_to = DEAD_BALL_TURNOVER - int(0.5 * turnover_modifier)
    calibrated_dead_ball_to = max(2, calibrated_dead_ball_to)  # Min 2
    
    # Step 3: Calculate Standard Foul Result
    foul_roll = random.randint(1, 100)
    if foul_roll <= calibrated_o_foul:
        return ("O_FOUL", None)
    elif foul_roll >= calibrated_d_foul:
        return ("D_FOUL", None)
    
    # Step 4: Calculate Steal Attempt
    # Apply aggression modifier to steal attempt rate
    steal_attempt_rate = STEAL_ATTEMPT
    if aggression_level == 4:  # Aggressive
        steal_attempt_rate += 10
    elif aggression_level == 0:  # Passive
        steal_attempt_rate -= 10
    steal_attempt_rate = max(10, min(30, steal_attempt_rate))  # Clamp between 10-30
    
    steal_roll = random.randint(1, 100)
    if steal_roll < steal_attempt_rate:
        # Steal attempt occurs - select random step and determine ball handler/defender
        if skeleton and "steps" in skeleton and len(skeleton["steps"]) > 0:
            steps = skeleton["steps"]
            # Exclude step 0 (initial setup)
            available_steps = [i for i in range(1, len(steps)) if i < len(steps)]
            if available_steps:
                selected_step_index = random.choice(available_steps)
                game_state["steal_stop_step_index"] = selected_step_index
                
                # Get ball handler at selected step
                ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=selected_step_index)
                if ball_handler:
                    ball_handler_pos = get_player_position(off_lineup, ball_handler)
                    defense_call = game_state.get("defense_playcall", "Man")
                    
                    # Get defender
                    if is_zone_defense(defense_call):
                        # Zone defense: use zone assignment logic
                        from BackEnd.utils.shared_defense import assign_all_zone_defenders
                        from BackEnd.constants import HCO_STRING_SPOTS
                        from BackEnd.utils.shared import get_away_player_coords
                        
                        # Get ball handler's location from step
                        ball_handler_spot = "key"  # Default
                        step = steps[selected_step_index]
                        pos_actions = step.get("pos_actions", {})
                        if ball_handler_pos in pos_actions:
                            action_info = pos_actions[ball_handler_pos]
                            ball_handler_spot = action_info.get("location") or action_info.get("spot") or "key"
                        
                        # Get ball handler coordinates
                        if ball_handler_spot in HCO_STRING_SPOTS:
                            ball_handler_coords = HCO_STRING_SPOTS[ball_handler_spot]
                        else:
                            ball_handler_coords = {"x": 64, "y": 25}  # Default to key
                        
                        ball_handler_coords = get_away_player_coords(ball_handler_coords, game)
                        zone_assignments = assign_all_zone_defenders(
                            defense_call, ball_handler_coords, def_lineup, game
                        )
                        # Get first defender assigned to ball handler
                        defender = None
                        for def_pos, guarded_player in zone_assignments.items():
                            if guarded_player == ball_handler:
                                defender = def_lineup.get(def_pos)
                                break
                        if not defender:
                            # Fallback: use ball handler's position
                            defender = def_lineup.get(ball_handler_pos)
                    else:
                        # Man defense: defender matches position
                        defender = def_lineup.get(ball_handler_pos)
                    
                    if defender:
                        # Calculate offense and defense values
                        bh_score = calculate_ball_handling_score(ball_handler)
                        pressure = calculate_defender_pressure_score(defender, defense_call)
                        
                        # Resolve steal attempt
                        from BackEnd.utils.shared import resolve_steal_attempt
                        steal_result = resolve_steal_attempt(
                            bh_score, pressure,
                            calibrated_soft_steal, calibrated_hard_steal,
                            calibrated_soft_foul, calibrated_hard_foul
                        )
                        
                        if steal_result == "STEAL":
                            return ("STEAL", None)
                        elif steal_result == "D_FOUL":
                            return ("D_FOUL", None)
                        # If "NO_EVENT", continue to Step 5
    
    # Step 5: Calculate Dead Ball Turnover
    turnover_roll = random.randint(1, 100)
    if turnover_roll < calibrated_dead_ball_to:
        # Turnover check occurs - select random step (may differ from Step 4)
        if skeleton and "steps" in skeleton and len(skeleton["steps"]) > 0:
            steps = skeleton["steps"]
            available_steps = [i for i in range(1, len(steps)) if i < len(steps)]
            if available_steps:
                selected_step_index = random.choice(available_steps)
                game_state["turnover_stop_step_index"] = selected_step_index
                
                # Get ball handler at selected step
                ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=selected_step_index)
                if ball_handler:
                    ball_handler_pos = get_player_position(off_lineup, ball_handler)
                    defense_call = game_state.get("defense_playcall", "Man")
                    
                    # Get defender
                    if is_zone_defense(defense_call):
                        # Zone defense: use zone assignment logic
                        from BackEnd.utils.shared_defense import assign_all_zone_defenders
                        from BackEnd.constants import HCO_STRING_SPOTS
                        from BackEnd.utils.shared import get_away_player_coords
                        
                        # Get ball handler's location from step
                        ball_handler_spot = "key"  # Default
                        step = steps[selected_step_index]
                        pos_actions = step.get("pos_actions", {})
                        if ball_handler_pos in pos_actions:
                            action_info = pos_actions[ball_handler_pos]
                            ball_handler_spot = action_info.get("location") or action_info.get("spot") or "key"
                        
                        # Get ball handler coordinates
                        if ball_handler_spot in HCO_STRING_SPOTS:
                            ball_handler_coords = HCO_STRING_SPOTS[ball_handler_spot]
                        else:
                            ball_handler_coords = {"x": 64, "y": 25}  # Default to key
                        
                        ball_handler_coords = get_away_player_coords(ball_handler_coords, game)
                        zone_assignments = assign_all_zone_defenders(
                            defense_call, ball_handler_coords, def_lineup, game
                        )
                        # Get first defender assigned to ball handler
                        defender = None
                        for def_pos, guarded_player in zone_assignments.items():
                            if guarded_player == ball_handler:
                                defender = def_lineup.get(def_pos)
                                break
                        if not defender:
                            # Fallback: use ball handler's position
                            defender = def_lineup.get(ball_handler_pos)
                    else:
                        # Man defense: defender matches position
                        defender = def_lineup.get(ball_handler_pos)
                    
                    if defender:
                        # Calculate scores
                        bh_score = calculate_ball_handling_score(ball_handler)
                        defender_score = calculate_defender_pressure_score(defender, defense_call)
                        
                        if defender_score > bh_score:
                            return ("DEAD_BALL_TURNOVER", None)
                        # Else continue to Step 6
    
    # Step 6: Shot Attempt
    # Calculate play effectiveness scores
    # For now, use random numbers until effectiveness scores are added to database
    o_score = offensive_efficiency + random.randint(1, 100)
    d_score = defensive_efficiency + random.randint(1, 100)
    
    result = o_score - d_score
    
    # Select skeleton variant based on result
    if result > 50:
        variant_result = "successful"
    elif result > 0:
        variant_result = "mid_play_change"
    elif result > -50:
        variant_result = "contested"
    else:
        variant_result = "broken"
    
    return ("SHOT", variant_result)


def generate_logic(off_call, def_call, off_team, def_team, off_lineup, def_lineup, game=None):
    """
    Calculate lean score based on offensive/defensive matchup.
    
    This function evaluates the effectiveness of the offensive play vs defensive setup
    by considering team attributes, player attributes, and tactical matchups.
    
    Args:
        off_call (str): Offensive playcall (e.g., "Motion - Inside Focus")
        def_call (str): Defensive playcall (e.g., "Man Defense")
        off_team: Offensive team object with attributes
        def_team: Defensive team object with attributes
        off_lineup (dict): Offensive lineup {pos: player}
        def_lineup (dict): Defensive lineup {pos: player}
        game: Game context object (optional, needed to retrieve skeleton)
    
    Returns:
        float: Lean score from -1 to 1
            >= 0.5: successful - play works perfectly
            0 to 0.49: mid_play_change - play adjusts mid-execution
            -0.01 to -0.5: contested - defense engaged, tougher execution
            < -0.5: broken - defense disrupts, offense forced to react
    
    TODO: Implement full logic based on:
        - Team attributes (team speed, execution, discipline, etc.)
        - Player attributes (relevant to play type/focus)
        - Defensive matchup effectiveness
        - Game situation (score, time, quarter)
    """
    import random
    from BackEnd.constants import ACTIONS
    
    result = random.choices(
        ["SHOT", "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL"],
        weights=[6, 1, 1, 1, 1],
        k=1
    )[0]
    
    # Analyze skeleton to count screen attempts
    screen_attempts_by_pos = {}
    if game:
        try:
            # Get the successful variant skeleton to analyze screen usage
            skeleton = get_hco_skeleton(None, game, lean_score=1.0)
            if skeleton and "steps" in skeleton:
                steps = skeleton.get("steps", [])
                for step in steps:
                    # Check pos_actions for SCREEN actions
                    pos_actions = step.get("pos_actions", {})
                    for pos, action_info in pos_actions.items():
                        action = action_info.get("action", "")
                        if action == ACTIONS["SCREEN"] or action == "screen":
                            screen_attempts_by_pos[pos] = screen_attempts_by_pos.get(pos, 0) + 1
                    
                    # Check events for screen events
                    events = step.get("events", [])
                    for event in events:
                        if event.get("type") == "screen":
                            screener_pos = event.get("by")
                            if screener_pos:
                                screen_attempts_by_pos[screener_pos] = screen_attempts_by_pos.get(screener_pos, 0) + 1
                
                # Record screen stats for each player
                if screen_attempts_by_pos:
                    for pos, count in sorted(screen_attempts_by_pos.items()):
                        player = off_lineup.get(pos)
                        if player:
                            # Increment SCR_A for each screen attempt
                            for _ in range(count):
                                player.record_stat("SCR_A")
                                
                                # 50% chance to increment SCR_S for each attempt
                                success = random.randint(1, 2)
                                if success == 1:
                                    player.record_stat("SCR_S")
        except Exception as e:
            pass  # Silently handle skeleton analysis errors
    
    # PLACEHOLDER: Return random lean score for now
    # This allows the system to work while full logic is implemented
    lean_score = random.uniform(-1, 1)
    
    return result, lean_score


def _store_lean_score(lean_score, game, offense_team, defense_team):
    """
    Store lean_score in offense and defense scouting data.
    
    Args:
        lean_score (float): Lean score from -1.0 to 1.0
        game: Game context object
        offense_team: Offensive team object
        defense_team: Defensive team object
    """
    try:
        # Get play type and focus from game_state
        offense_play_type = game.game_state.get("offense_play_type", "").lower()
        offense_focus = game.game_state.get("offense_play_focus", "")
        defense_playcall = game.game_state.get("defense_playcall", "")
        
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
            
            # Store lean_score in overall and focus buckets
            if "lean_scores" not in pc[play_type_label]["overall"]:
                pc[play_type_label]["overall"]["lean_scores"] = []
            if "lean_scores" not in pc[play_type_label][offense_focus]:
                pc[play_type_label][offense_focus]["lean_scores"] = []
            
            pc[play_type_label]["overall"]["lean_scores"].append(lean_score)
            pc[play_type_label][offense_focus]["lean_scores"].append(lean_score)
            
            # Store lean_score in vs_* buckets
            if vs_key and vs_key in pc[play_type_label]["overall"]:
                if "lean_scores" not in pc[play_type_label]["overall"][vs_key]:
                    pc[play_type_label]["overall"][vs_key]["lean_scores"] = []
                pc[play_type_label]["overall"][vs_key]["lean_scores"].append(lean_score)
            
            if vs_key and vs_key in pc[play_type_label][offense_focus]:
                if "lean_scores" not in pc[play_type_label][offense_focus][vs_key]:
                    pc[play_type_label][offense_focus][vs_key]["lean_scores"] = []
                pc[play_type_label][offense_focus][vs_key]["lean_scores"].append(lean_score)
            
            # Store in vs_zone aggregate if zone defense
            from BackEnd.utils.defense_utils import is_zone_defense
            if is_zone_defense(defense_playcall) and "vs_zone" in pc[play_type_label]["overall"]:
                if "lean_scores" not in pc[play_type_label]["overall"]["vs_zone"]:
                    pc[play_type_label]["overall"]["vs_zone"]["lean_scores"] = []
                if "lean_scores" not in pc[play_type_label][offense_focus]["vs_zone"]:
                    pc[play_type_label][offense_focus]["vs_zone"]["lean_scores"] = []
                pc[play_type_label]["overall"]["vs_zone"]["lean_scores"].append(lean_score)
                pc[play_type_label][offense_focus]["vs_zone"]["lean_scores"].append(lean_score)
            
            # Store in Cumulative
            if "lean_scores" not in pc["Cumulative"][offense_focus]:
                pc["Cumulative"][offense_focus]["lean_scores"] = []
            pc["Cumulative"][offense_focus]["lean_scores"].append(lean_score)
        
        # Store lean_score in defense scouting data
        if defense_playcall in defense_team.scouting_data["defense"]:
            def_data = defense_team.scouting_data["defense"][defense_playcall]
            game_stats = def_data.get("game_stats", {})
            
            # Store lean_score in top-level game_stats
            if "lean_scores" not in game_stats:
                game_stats["lean_scores"] = []
            game_stats["lean_scores"].append(lean_score)
            
            # Store lean_score in vs_* buckets
            if offense_play_type == "motion":
                if "lean_scores" not in game_stats.get("vs_motion", {}):
                    game_stats.setdefault("vs_motion", {})["lean_scores"] = []
                game_stats["vs_motion"]["lean_scores"].append(lean_score)
            elif offense_play_type == "set":
                if "lean_scores" not in game_stats.get("vs_set", {}):
                    game_stats.setdefault("vs_set", {})["lean_scores"] = []
                game_stats["vs_set"]["lean_scores"].append(lean_score)
            
            if offense_focus in ["inside", "attack", "outside"]:
                vs_focus_key = f"vs_{offense_focus}"
                if "lean_scores" not in game_stats.get(vs_focus_key, {}):
                    game_stats.setdefault(vs_focus_key, {})["lean_scores"] = []
                game_stats[vs_focus_key]["lean_scores"].append(lean_score)
                
                # Store in combination buckets
                if offense_play_type == "motion":
                    combo_key = f"vs_motion_{offense_focus}"
                    if "lean_scores" not in game_stats.get(combo_key, {}):
                        game_stats.setdefault(combo_key, {})["lean_scores"] = []
                    game_stats[combo_key]["lean_scores"].append(lean_score)
                elif offense_play_type == "set":
                    combo_key = f"vs_set_{offense_focus}"
                    if "lean_scores" not in game_stats.get(combo_key, {}):
                        game_stats.setdefault(combo_key, {})["lean_scores"] = []
                    game_stats[combo_key]["lean_scores"].append(lean_score)
    except Exception as e:
        # Silently handle errors to avoid disrupting gameplay
        pass


def apply_stopper_system_to_skeleton(skeleton, result, game_state):
    """
    Apply stopper system to skeleton: truncate and add stopper step for non-shot results.
    
    Args:
        skeleton: Skeleton dict with "steps" array
        result: Result type ("O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", or "HCO")
        game_state: Game state dict (for storing steal position data)
    
    Returns:
        Modified skeleton (truncated + stopper step, or full skeleton if result == "HCO")
    """
    import copy
    
    # If result is HCO, return full skeleton (no truncation)
    if result == "HCO":
        return skeleton
    
    # If result is SHOT, return full skeleton (no truncation)
    if result == "SHOT":
        return skeleton
    
    # Deep copy skeleton to avoid mutating original
    skeleton = copy.deepcopy(skeleton)
    
    if not skeleton or "steps" not in skeleton:
        logging.warning(f"⚠️ [STOPPER] Cannot apply stopper - skeleton or steps missing (result: {result})")
        return skeleton
    
    steps = skeleton.get("steps", [])
    if len(steps) <= 1:
        logging.warning(f"⚠️ [STOPPER] Cannot apply stopper - skeleton has {len(steps)} steps (need at least 2)")
        return skeleton
    
    # Determine which step to stop at based on result type
    if result in ["O_FOUL", "D_FOUL"]:
        # Random step before final (exclude step 0 and final step)
        # If skeleton has 7 steps (0-6), choose from steps 1-5
        stop_step_index = random.randint(1, len(steps) - 2) if len(steps) > 2 else 1
    elif result in ["DEAD_BALL_TURNOVER", "STEAL"]:
        # Strategic step - use middle step, excluding step 0 for consistency with fouls
        # Calculate middle of steps 1 through len(steps)-1 (excluding step 0 and final step)
        if len(steps) > 2:
            # Middle of steps 1 to len(steps)-2
            stop_step_index = 1 + (len(steps) - 2 - 1) // 2
        else:
            stop_step_index = 1
    else:
        # Default: stop at step before final
        stop_step_index = len(steps) - 2
    
    # Truncate skeleton to stop_step_index
    truncated_steps = steps[:stop_step_index + 1]  # Include the stop step
    
    # Get the ball handler at the stop step for the stopper action
    stop_step = truncated_steps[-1]
    ball_handler_pos = None
    ball_handler_location = "key"  # Default location
    
    # Find ball handler in the stop step
    pos_actions = stop_step.get("pos_actions", {})
    for pos, action_info in pos_actions.items():
        action = action_info.get("action", "").lower()
        if action in ["handle_ball", "receive", "pass"]:
            ball_handler_pos = pos
            ball_handler_location = action_info.get("location", "key")
            break
    
    # If no ball handler found in stop step, check previous step
    if not ball_handler_pos and len(truncated_steps) > 1:
        prev_step = truncated_steps[-2]
        prev_pos_actions = prev_step.get("pos_actions", {})
        for pos, action_info in prev_pos_actions.items():
            action = action_info.get("action", "").lower()
            if action in ["handle_ball", "receive"]:
                ball_handler_pos = pos
                ball_handler_location = action_info.get("location", "key")
                break
    
    # Create stopper step as final step
    stopper_timestamp = stop_step.get("timestamp", 0) + 300  # 300ms after stop step
    
    # Map result to stopper action
    stopper_action_map = {
        "O_FOUL": "o_foul",
        "D_FOUL": "d_foul",
        "DEAD_BALL_TURNOVER": "dead_ball_turnover",
        "STEAL": "steal"
    }
    stopper_action = stopper_action_map.get(result, "turnover")
    
    # Create stopper step
    stopper_step = {
        "timestamp": stopper_timestamp,
        "pos_actions": {},
        "events": [{"type": stopper_action}]
    }
    
    # Add ball handler position (if found) - ball remains with them until stopper
    if ball_handler_pos:
        stopper_step["pos_actions"][ball_handler_pos] = {
            "location": ball_handler_location,
            "action": "handle_ball"  # Ball still with them
        }
    
    # ✅ FIX: Store stop_step_index for later use in determining ball handler and defender
    # This ensures we use the actual ball handler at the step where the steal/foul/turnover occurred
    # Store for all non-shot results (steals, fouls, turnovers) so defender determination uses correct ball handler
    if result in ["STEAL", "DEAD_BALL_TURNOVER", "O_FOUL", "D_FOUL"]:
        game_state["steal_stop_step_index"] = stop_step_index
        # Also store a reference to the original skeleton steps before truncation
        # (we'll use this to extract position from the correct step)
        if result == "STEAL":
            game_state["steal_original_skeleton_steps"] = steps.copy()
    
    # Replace skeleton steps with truncated steps + stopper step
    skeleton["steps"] = truncated_steps + [stopper_step]
    
    return skeleton


# ==================== MOTION OFFENSE SHOT RESOLUTION ====================

def _is_inside_location(location):
    """Check if a location is an inside shot location."""
    inside_locations = ["lower lowPost", "lower midPost", "midLane", "basketSpot", "upper lowPost", "upper midPost"]
    return location in inside_locations


def _is_deep_location(location):
    """Check if a location has 'deep' in the name."""
    return "deep" in location.lower()


def _is_outside_location(location):
    """Check if a location is an outside shot location (not inside, not deep)."""
    return not _is_inside_location(location) and not _is_deep_location(location)


def _is_upper_location(location):
    """Check if a location is in the upper half of the court."""
    upper_keywords = ["upper", "top"]
    return any(keyword in location.lower() for keyword in upper_keywords)


def _is_lower_location(location):
    """Check if a location is in the lower half of the court."""
    lower_keywords = ["lower"]
    return any(keyword in location.lower() for keyword in lower_keywords)


def _is_central_location(location):
    """Check if a location is central (key, topLane, deep key)."""
    central_locations = ["key", "topLane", "deep key"]
    return location in central_locations


def _get_upper_inside_locations():
    """Get list of upper half inside shot locations."""
    return ["upper lowPost", "upper midPost", "midLane", "basketSpot"]


def _get_lower_inside_locations():
    """Get list of lower half inside shot locations."""
    return ["lower lowPost", "lower midPost", "midLane", "basketSpot"]


def _check_inside_shot_possibility(selected_step, ball_handler_location, off_lineup):
    """
    Check if an inside shot is possible based on conducive pass logic.
    
    Returns:
        tuple: (is_possible, list of viable receivers with their positions)
    """
    inside_locations = ["lower lowPost", "lower midPost", "midLane", "basketSpot", "upper lowPost", "upper midPost"]
    viable_receivers = []
    
    # Determine which inside locations are viable based on ball handler location
    if _is_upper_location(ball_handler_location):
        viable_inside_locations = _get_upper_inside_locations()
    elif _is_lower_location(ball_handler_location):
        viable_inside_locations = _get_lower_inside_locations()
    elif _is_central_location(ball_handler_location):
        # Central locations can pass to all inside spots
        viable_inside_locations = inside_locations
    else:
        # Default: use all inside locations
        viable_inside_locations = inside_locations
    
    # Find players at viable inside locations
    pos_actions = selected_step.get("pos_actions", {})
    logging.warning(f"🔍 [INSIDE CHECK] Ball handler at: {ball_handler_location}, Viable inside locations: {viable_inside_locations}")
    logging.warning(f"🔍 [INSIDE CHECK] All players in step: {[(pos, action_info.get('location', '')) for pos, action_info in pos_actions.items()]}")
    
    for pos, action_info in pos_actions.items():
        location = action_info.get("location", "")
        if location in viable_inside_locations:
            player = off_lineup.get(pos)
            if player:
                logging.warning(f"🔍 [INSIDE CHECK] Found viable receiver: {pos} at {location}")
                viable_receivers.append({
                    "position": pos,
                    "player": player,
                    "location": location
                })
    
    logging.warning(f"🔍 [INSIDE CHECK] Total viable receivers: {len(viable_receivers)}")
    return len(viable_receivers) > 0, viable_receivers


def _check_attack_shot_possibility(ball_handler_location):
    """
    Check if an attack shot is possible.
    Attack shots are not possible if ball handler is at an inside location.
    """
    return not _is_inside_location(ball_handler_location)


def _check_outside_shot_possibility(selected_step, off_lineup):
    """
    Check if an outside shot is possible (any player at outside location).
    
    Returns:
        tuple: (is_possible, list of players at outside locations)
    """
    outside_players = []
    pos_actions = selected_step.get("pos_actions", {})
    
    for pos, action_info in pos_actions.items():
        location = action_info.get("location", "")
        if _is_outside_location(location):
            player = off_lineup.get(pos)
            if player:
                outside_players.append({
                    "position": pos,
                    "player": player,
                    "location": location
                })
    
    return len(outside_players) > 0, outside_players


def _build_shot_type_weighted_list(strategy_settings, inside_possible, attack_possible, outside_possible, ball_handler_at_inside):
    """
    Build weighted list for shot type selection based on strategy settings and possibilities.
    
    Returns:
        list: Weighted list of shot types (e.g., ["inside", "inside", "attack", "outside"])
    """
    inside_weight = strategy_settings.get("inside", 2)
    attack_weight = strategy_settings.get("attack", 2)
    outside_weight = strategy_settings.get("outside", 2)
    
    # Special case: ball handler at inside location
    if ball_handler_at_inside:
        # No attack possible, weighted: 4 inside, 2 outside
        weighted_list = ["inside"] * 4 + ["outside"] * 2
        if not outside_possible:
            # Only inside possible
            return ["inside"] * 4
        return weighted_list
    
    # Build initial weighted list
    weighted_list = []
    if inside_possible:
        weighted_list.extend(["inside"] * inside_weight)
    if attack_possible:
        weighted_list.extend(["attack"] * attack_weight)
    if outside_possible:
        weighted_list.extend(["outside"] * outside_weight)
    
    # Handle edge cases where list is empty or only one type possible
    if not weighted_list:
        # All three not possible (shouldn't happen, but handle gracefully)
        if inside_possible:
            return ["inside"]
        elif attack_possible:
            return ["attack"]
        elif outside_possible:
            return ["outside"]
        else:
            # Fallback: default to outside
            return ["outside"]
    
    # Handle cases where chosen type has 0 weight
    if inside_possible and attack_possible and not outside_possible:
        if inside_weight == 0 and attack_weight == 0:
            return ["inside", "attack"]  # Random between available
    elif inside_possible and outside_possible and not attack_possible:
        if inside_weight == 0 and outside_weight == 0:
            return ["inside", "outside"]  # Random between available
    elif attack_possible and outside_possible and not inside_possible:
        if attack_weight == 0 and outside_weight == 0:
            return ["attack", "outside"]  # Random between available
    
    return weighted_list


def _find_closest_receiver(ball_handler_location, receivers, off_lineup):
    """
    Find closest receiver to ball handler (75% chance) or random other (25% chance).
    
    Args:
        ball_handler_location: Location string of ball handler
        receivers: List of receiver dicts with "position", "player", "location"
        off_lineup: Offensive lineup dict
    
    Returns:
        dict: Selected receiver
    """
    from BackEnd.constants import HCO_STRING_SPOTS
    
    if len(receivers) == 1:
        return receivers[0]
    
    # Get ball handler coordinates
    bh_coords = HCO_STRING_SPOTS.get(ball_handler_location, {"x": 50, "y": 25})
    
    # Calculate distances
    receiver_distances = []
    for receiver in receivers:
        receiver_location = receiver["location"]
        receiver_coords = HCO_STRING_SPOTS.get(receiver_location, {"x": 50, "y": 25})
        
        # Euclidean distance
        distance = ((bh_coords["x"] - receiver_coords["x"]) ** 2 + 
                   (bh_coords["y"] - receiver_coords["y"]) ** 2) ** 0.5
        
        receiver_distances.append({
            "receiver": receiver,
            "distance": distance
        })
    
    # Sort by distance
    receiver_distances.sort(key=lambda x: x["distance"])
    closest = receiver_distances[0]
    others = receiver_distances[1:]
    
    # 75% chance closest, 25% chance random other
    if random.random() < 0.75 or len(others) == 0:
        return closest["receiver"]
    else:
        return random.choice(others)["receiver"]


def _determine_attack_drive_destination(ball_handler_location):
    """
    Determine valid drive destinations based on starting location.
    
    Returns:
        list: Valid destination locations
    """
    if _is_upper_location(ball_handler_location):
        return ["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot"]
    elif _is_lower_location(ball_handler_location):
        return ["lower lowPost", "lower midPost", "lower bird", "midLane", "basketSpot"]
    elif _is_central_location(ball_handler_location):
        # Central: all destinations
        return ["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot",
                "lower lowPost", "lower midPost", "lower bird"]
    else:
        # Default: all destinations
        return ["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot",
                "lower lowPost", "lower midPost", "lower bird"]


def _create_pass_receive_step(passer_pos, receiver_pos, passer_location, receiver_location, timestamp):
    """
    Create a step for pass and receive.
    
    Returns:
        dict: Step with pass and receive actions
    """
    return {
        "timestamp": timestamp,
        "pos_actions": {
            passer_pos: {
                "location": passer_location,
                "action": "pass"
            },
            receiver_pos: {
                "location": receiver_location,
                "action": "receive"
            }
        },
        "events": []
    }


def _create_shoot_step(shooter_pos, shooter_location, timestamp):
    """
    Create a step for shooting.
    
    Returns:
        dict: Step with shoot action
    """
    return {
        "timestamp": timestamp,
        "pos_actions": {
            shooter_pos: {
                "location": shooter_location,
                "action": "shoot"
            }
        },
        "events": [{"type": "shot"}]
    }


def _create_attack_drive_shoot_step(ball_handler_pos, start_location, destination_location, timestamp, is_away_offense=False):
    """
    Create a step for attack drive and shoot.
    Player drives to destination and shoots immediately.
    
    Args:
        is_away_offense: Whether away team is on offense (for coordinate flipping)
    
    Returns:
        dict: Step with drive and shoot actions
    """
    from BackEnd.constants import HCO_STRING_SPOTS
    
    # Get destination coordinates
    dest_coords = HCO_STRING_SPOTS.get(destination_location, {"x": 50, "y": 25})
    
    # TODO: Add defensive stop logic here (player may be stopped short)
    # For now, assume player reaches destination
    final_location = destination_location
    
    return {
        "timestamp": timestamp,
        "pos_actions": {
            ball_handler_pos: {
                "location": final_location,
                "action": "shoot"  # Drive and shoot in same step
            }
        },
        "events": [{"type": "shot"}],
        "_attack_drive": {
            "start_location": start_location,
            "intended_destination": destination_location,
            "final_location": final_location,
            "stopped_short": False  # TODO: Implement defensive stop logic
        }
    }


def _apply_attack_penalty(shot_location, is_away_offense):
    """
    Calculate attack shot penalty if player was stopped short.
    
    Args:
        shot_location: Final location where shot was taken
        is_away_offense: Whether away team is on offense
    
    Returns:
        float: Penalty value (0 if no penalty)
    """
    from BackEnd.constants import HCO_STRING_SPOTS, HOME_RIM_COORDS, AWAY_RIM_COORDS
    
    # No penalty for ideal spots
    ideal_spots = ["basketSpot", "upper lowPost", "lower lowPost"]
    if shot_location in ideal_spots:
        return 0.0
    
    # Get shot location coordinates
    shot_coords = HCO_STRING_SPOTS.get(shot_location, {"x": 50, "y": 25})
    
    # Get basket spot coordinates
    if is_away_offense:
        basket_coords = AWAY_RIM_COORDS  # x=10
    else:
        basket_coords = HOME_RIM_COORDS  # x=90
    
    # Calculate penalty
    penalty = abs(shot_coords["x"] - basket_coords["x"])
    
    return penalty


def resolve_motion_offense_shot(skeleton, game, off_lineup, def_lineup):
    """
    Resolve Motion offense shot attempt.
    
    This function:
    1. Selects a random step (excluding step 0) for shot attempt
    2. Determines shot type (inside/outside/attack) based on possibilities and strategy
    3. Truncates skeleton at selected step
    4. Appends necessary steps (pass/receive, drive, shoot)
    5. Returns modified skeleton and shot information
    
    Args:
        skeleton: Motion play skeleton with base_loop steps
        game: GameManager instance
        off_lineup: Offensive lineup dict
        def_lineup: Defensive lineup dict
    
    Returns:
        dict: {
            "skeleton": modified skeleton with shot steps appended,
            "shooter": Player object,
            "shooter_location": location string,
            "shot_type": "inside" | "outside" | "attack",
            "playcall": "Inside" | "Outside" | "Attack",
            "attack_penalty": float (0 if not attack or no penalty)
        }
    """
    import copy
    from BackEnd.constants import HCO_STRING_SPOTS
    from BackEnd.utils.shared import get_away_player_coords
    
    game_state = game.game_state
    off_team = game.offense_team
    is_away_offense = off_team.team_id == game.away_team.team_id
    
    # Deep copy skeleton to avoid mutating original
    skeleton = copy.deepcopy(skeleton)
    steps = skeleton.get("steps", [])
    
    if len(steps) < 2:
        logging.warning(f"⚠️ [MOTION SHOT] Skeleton has insufficient steps ({len(steps)}), cannot select shot step")
        return None
    
    # Phase 1: Select random step (excluding step 0)
    shot_step_index = random.randint(1, len(steps) - 1)
    selected_step = steps[shot_step_index]
    
    # Truncate skeleton at selected step
    truncated_steps = steps[:shot_step_index + 1]
    last_timestamp = truncated_steps[-1].get("timestamp", 0)
    
    # Phase 2: Identify ball handler at selected step
    ball_handler_pos = None
    ball_handler_location = "key"
    pos_actions = selected_step.get("pos_actions", {})
    
    for pos, action_info in pos_actions.items():
        action = action_info.get("action", "").lower()
        if action in ["handle_ball", "receive", "pass"]:
            ball_handler_pos = pos
            ball_handler_location = action_info.get("location", "key")
            break
    
    if not ball_handler_pos:
        logging.warning(f"⚠️ [MOTION SHOT] No ball handler found at selected step {shot_step_index}")
        return None
    
    ball_handler = off_lineup.get(ball_handler_pos)
    if not ball_handler:
        logging.warning(f"⚠️ [MOTION SHOT] Ball handler position {ball_handler_pos} not found in lineup")
        return None
    
    # Phase 3: Check shot possibilities
    inside_possible, inside_receivers = _check_inside_shot_possibility(selected_step, ball_handler_location, off_lineup)
    attack_possible = _check_attack_shot_possibility(ball_handler_location)
    outside_possible, outside_players = _check_outside_shot_possibility(selected_step, off_lineup)
    
    ball_handler_at_inside = _is_inside_location(ball_handler_location)
    
    # 🔍 DEBUG: Log shot possibilities
    logging.warning(f"🎯 [MOTION SHOT] Step {shot_step_index}, Ball handler: {ball_handler_pos} at {ball_handler_location}")
    logging.warning(f"🎯 [MOTION SHOT] Inside possible: {inside_possible}, Receivers: {len(inside_receivers)}")
    if inside_receivers:
        logging.warning(f"🎯 [MOTION SHOT] Inside receivers: {[(r['position'], r['location']) for r in inside_receivers]}")
    logging.warning(f"🎯 [MOTION SHOT] Attack possible: {attack_possible}, Outside possible: {outside_possible}")
    logging.warning(f"🎯 [MOTION SHOT] Ball handler at inside: {ball_handler_at_inside}")
    
    # Phase 4: Get strategy settings and build weighted list
    strategy_settings = off_team.strategy_settings
    weighted_list = _build_shot_type_weighted_list(
        strategy_settings, inside_possible, attack_possible, outside_possible, ball_handler_at_inside
    )
    
    logging.warning(f"🎯 [MOTION SHOT] Weighted list: {weighted_list} (inside_weight={strategy_settings.get('inside', 2)}, attack_weight={strategy_settings.get('attack', 2)}, outside_weight={strategy_settings.get('outside', 2)})")
    
    # Phase 5: Select shot type
    selected_shot_type = random.choice(weighted_list)
    logging.warning(f"🎯 [MOTION SHOT] Selected shot type: {selected_shot_type}")
    
    # Phase 6: Execute shot - build additional steps
    new_steps = []
    shooter = ball_handler
    shooter_pos = ball_handler_pos
    shooter_location = ball_handler_location
    attack_penalty = 0.0
    
    if selected_shot_type == "inside":
        if ball_handler_at_inside:
            # Ball handler shoots from current location
            shoot_step = _create_shoot_step(ball_handler_pos, ball_handler_location, last_timestamp + 300)
            new_steps.append(shoot_step)
        else:
            # Pass to inside receiver
            receiver = _find_closest_receiver(ball_handler_location, inside_receivers, off_lineup)
            receiver_pos = receiver["position"]
            receiver_location = receiver["location"]
            
            # Step 1: Pass and receive
            pass_step = _create_pass_receive_step(
                ball_handler_pos, receiver_pos, ball_handler_location, receiver_location, last_timestamp + 300
            )
            new_steps.append(pass_step)
            
            # Step 2: Receiver shoots
            shoot_step = _create_shoot_step(receiver_pos, receiver_location, last_timestamp + 600)
            new_steps.append(shoot_step)
            
            shooter = receiver["player"]
            shooter_pos = receiver_pos
            shooter_location = receiver_location
    
    elif selected_shot_type == "outside":
        if _is_outside_location(ball_handler_location):
            # Ball handler shoots from current location
            shoot_step = _create_shoot_step(ball_handler_pos, ball_handler_location, last_timestamp + 300)
            new_steps.append(shoot_step)
        else:
            # Pass to outside receiver
            receiver = _find_closest_receiver(ball_handler_location, outside_players, off_lineup)
            receiver_pos = receiver["position"]
            receiver_location = receiver["location"]
            
            # Step 1: Pass and receive
            pass_step = _create_pass_receive_step(
                ball_handler_pos, receiver_pos, ball_handler_location, receiver_location, last_timestamp + 300
            )
            new_steps.append(pass_step)
            
            # Step 2: Receiver shoots
            shoot_step = _create_shoot_step(receiver_pos, receiver_location, last_timestamp + 600)
            new_steps.append(shoot_step)
            
            shooter = receiver["player"]
            shooter_pos = receiver_pos
            shooter_location = receiver_location
    
    elif selected_shot_type == "attack":
        # Determine drive destination
        valid_destinations = _determine_attack_drive_destination(ball_handler_location)
        destination = random.choice(valid_destinations)
        
        # Create drive + shoot step
        drive_shoot_step = _create_attack_drive_shoot_step(
            ball_handler_pos, ball_handler_location, destination, last_timestamp + 300, is_away_offense
        )
        new_steps.append(drive_shoot_step)
        
        # Get final location (may be stopped short)
        final_location = drive_shoot_step["_attack_drive"]["final_location"]
        shooter_location = final_location
        
        # Calculate attack penalty if stopped short
        attack_penalty = _apply_attack_penalty(final_location, is_away_offense)
    
    # Phase 7: Append new steps to truncated skeleton
    skeleton["steps"] = truncated_steps + new_steps
    
    # Phase 8: Map shot type to playcall for shot calculation
    playcall_map = {
        "inside": "Inside",
        "outside": "Outside",
        "attack": "Attack"
    }
    playcall = playcall_map.get(selected_shot_type, "Inside")
    
    return {
        "skeleton": skeleton,
        "shooter": shooter,
        "shooter_pos": shooter_pos,
        "shooter_location": shooter_location,
        "shot_type": selected_shot_type,
        "playcall": playcall,
        "attack_penalty": attack_penalty
    }


def resolve_half_court_offense_logic(game):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    # 1. Tactical Setup
    off_call = game_state.get("current_playcall", "Inside")
    def_call = game_state.get("defense_playcall", "Man")
    
    # 🔍 DEBUG: Log playcall being used
    logging.warning(f"🔍 [HCO RESOLVE] Using playcall: '{off_call}' (from game_state['current_playcall'])")
    if not off_call or off_call == "Inside":
        logging.warning(f"⚠️ [HCO RESOLVE] WARNING: playcall is '{off_call}' - may fall back to old skeleton system")

    # ✅ NEW RESOLUTION SYSTEM: Get skeleton first (needed for step selection in resolution)
    # For Motion plays, get base_loop skeleton
    # For Set Plays, get a temporary skeleton to use for resolution (will get correct variant after)
    offense_play_type = game_state.get("offense_play_type", "")
    is_motion_play = offense_play_type == "motion"
    
    if is_motion_play:
        # Motion plays use base_loop skeleton
        skeleton = get_hco_skeleton(None, game, lean_score=None)
    else:
        # Set Plays: Get successful variant skeleton for resolution (will get correct variant after)
        skeleton = get_hco_skeleton(None, game, lean_score=1.0)
    
    # ✅ NEW RESOLUTION SYSTEM: Use new sequential resolution system
    result, variant_result = resolve_hco_outcome(game, skeleton)
    
    # ✅ REMOVED: Old generate_logic() call and lean_score storage
    # Store variant_result for skeleton selection (replaces lean_score)
    if variant_result:
        game_state["_skeleton_variant"] = variant_result
    
    # 🔍 DEBUG: Log skeleton retrieval result
    if skeleton:
        logging.warning(f"✅ [HCO RESOLVE] Skeleton retrieved successfully: {len(skeleton.get('steps', []))} steps")
    else:
        logging.warning(f"⚠️ [HCO RESOLVE] WARNING: No skeleton retrieved! Will fall back to old system")
    
    # CRITICAL: Always create a deep copy to avoid mutating cached skeleton
    # This prevents any modifications (from stopper system or elsewhere) from affecting future turns
    if skeleton:
        skeleton = copy.deepcopy(skeleton)
    
    # ✅ NEW RESOLUTION SYSTEM: Get correct skeleton variant based on resolution result
    # For Motion plays, use base_loop (no variants)
    # For Set Plays, use variant_result from resolution system
    if is_motion_play:
        # Motion plays use base_loop skeleton (already retrieved)
        final_skeleton = skeleton
    else:
        # Set Plays: Get skeleton with correct variant based on resolution result
        if variant_result:
            # Map variant_result to lean_score for get_hco_skeleton
            variant_to_lean = {
                "successful": 1.0,
                "mid_play_change": 0.3,
                "contested": -0.3,
                "broken": -1.0
            }
            lean_score = variant_to_lean.get(variant_result, 0.0)
            final_skeleton = get_hco_skeleton(None, game, lean_score=lean_score)
        else:
            # Fallback: use successful variant
            final_skeleton = get_hco_skeleton(None, game, lean_score=1.0)
    
    # CRITICAL: Always create a deep copy to avoid mutating cached skeleton
    if final_skeleton:
        final_skeleton = copy.deepcopy(final_skeleton)
    
    # ✅ STOPER SYSTEM: Apply stopper system to skeleton (truncate and add stopper step if needed)
    skeleton = apply_stopper_system_to_skeleton(final_skeleton, result, game_state)
    
    # Get the successful variant to determine intended shooter (only for Set Plays)
    # Motion plays don't have variants, so we'll use the base_loop skeleton
    if is_motion_play:
        # For Motion plays, use the same skeleton (base_loop)
        successful_skeleton = skeleton
    else:
        # For Set Plays, get the successful variant
        successful_skeleton = get_hco_skeleton(None, game, lean_score=1.0)  # Force successful variant
    
    roles = game.turn_manager.assign_roles(off_call, def_call, skeleton=skeleton)
    
    # ✅ FIX: For non-shot outcomes (steals, turnovers, fouls), override defender
    # to be based on ball handler's position, not shooter's position
    # assign_roles() assigns defender based on shooter, but for steals we need
    # whoever is guarding the ball handler at the time of the steal
    if result in ["STEAL", "DEAD_BALL_TURNOVER", "O_FOUL", "D_FOUL"]:
        # ✅ FIX: Get ball handler from the stop step where the steal/foul/turnover occurs,
        # not from roles (which may be the shooter from a different step)
        # This is critical for Motion plays where the ball handler changes throughout the motion
        # Check for both steal and turnover stop step indices
        # Also check the generic stop_step_index that apply_stopper_system_to_skeleton sets
        stop_step_index = (
            game_state.get("steal_stop_step_index") or 
            game_state.get("turnover_stop_step_index") or
            game_state.get("stop_step_index")
        )
        if stop_step_index is not None and skeleton and "steps" in skeleton:
            # Use the actual ball handler at the stop step
            ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=stop_step_index)
        else:
            # Fallback: use ball handler from roles (for backwards compatibility or if stop step not available)
            ball_handler = roles.get("ball_handler")
        
        if ball_handler:
            ball_handler_pos = get_player_position(off_lineup, ball_handler)
            
            from BackEnd.utils.defense_utils import is_zone_defense
            is_zone = is_zone_defense(def_call)
            if is_zone:
                # Zone defense: use actual zone assignment logic to find which defender(s) are guarding the ball handler
                from BackEnd.utils.shared_defense import (
                    _get_23_zone_boundaries, _get_32_zone_boundaries, _get_131_zone_boundaries,
                    assign_all_zone_defenders
                )
                from BackEnd.constants import HCO_STRING_SPOTS
                from BackEnd.utils.shared import get_away_player_coords
                
                # Get ball handler's location from the skeleton step where steal occurs
                ball_handler_spot = "key"  # Default fallback
                if skeleton and "steps" in skeleton:
                    # For steals, use the stop step (where steal occurs)
                    # For other outcomes, use the last step before stopper
                    steps = skeleton.get("steps", [])
                    if steps:
                        # Find the step where the ball handler has the ball
                        for step in reversed(steps):
                            pos_actions = step.get("pos_actions", {})
                            for pos, action_info in pos_actions.items():
                                action = action_info.get("action", "").lower()
                                if action in ["handle_ball", "receive", "pass"] and pos == ball_handler_pos:
                                    ball_handler_spot = action_info.get("location") or action_info.get("spot") or "key"
                                    break
                            if ball_handler_spot != "key":
                                break
                
                # Get ball handler's coordinates
                ball_handler_coords = HCO_STRING_SPOTS.get(ball_handler_spot, {"x": 50, "y": 25})
                
                # Determine court orientation
                is_away_offense = off_team.team_id == game.away_team.team_id
                if is_away_offense:
                    ball_handler_coords = get_away_player_coords(ball_handler_coords)
                
                # Get zone boundaries based on ball location (applies shifts)
                if def_call == "3-2 Zone":
                    zone_boundaries = _get_32_zone_boundaries(ball_handler_spot, is_away_offense)
                elif def_call == "1-3-1 Zone":
                    zone_boundaries = _get_131_zone_boundaries(ball_handler_spot, is_away_offense)
                else:
                    zone_boundaries = _get_23_zone_boundaries(ball_handler_spot, is_away_offense)
                
                # Build offensive players list for zone assignment
                ball_handler_id = getattr(ball_handler, "player_id", None)
                offensive_players = []
                for pos, player in off_lineup.items():
                    player_id = getattr(player, "player_id", None)
                    player_coords = getattr(player, "coords", {})
                    # Get player's spot from skeleton if available
                    player_spot = "key"
                    if skeleton and "steps" in skeleton:
                        steps = skeleton.get("steps", [])
                        if steps:
                            for step in reversed(steps):
                                pos_actions = step.get("pos_actions", {})
                                if pos in pos_actions:
                                    action_info = pos_actions[pos]
                                    player_spot = action_info.get("location") or action_info.get("spot") or "key"
                                    break
                    
                    # Convert spot to coordinates
                    spot_coords = HCO_STRING_SPOTS.get(player_spot, {"x": 50, "y": 25})
                    if is_away_offense:
                        spot_coords = get_away_player_coords(spot_coords)
                    
                    # Use player's coords if available, otherwise use spot coords
                    final_coords = player_coords if player_coords.get("x") and player_coords.get("y") else spot_coords
                    
                    offensive_players.append({
                        "player_id": player_id,
                        "coords": final_coords,
                        "spot": player_spot,
                        "is_ball_handler": (player_id == ball_handler_id)
                    })
                
                # Get aggression level
                aggression_level = def_team.strategy_settings.get("aggression", "normal")
                aggression_map = {0: "passive", 1: "passive", 2: "normal", 3: "aggressive", 4: "aggressive"}
                aggression = aggression_map.get(aggression_level, "normal")
                
                # Call zone assignment logic to get actual defender assignments
                _, defender_to_offensive_player = assign_all_zone_defenders(
                    zone_boundaries,
                    offensive_players,
                    ball_handler_coords,
                    ball_handler_spot,
                    aggression,
                    is_away_offense
                )
                
                # Find which defender(s) are actually guarding the ball handler
                defenders_guarding_ball_handler = []
                for def_pos, guarded_player_id in defender_to_offensive_player.items():
                    if guarded_player_id == ball_handler_id:
                        defenders_guarding_ball_handler.append(def_pos)
                
                # Handle overlapping zones per user requirements:
                # 1. If only one defender is guarding the ball handler, use that one
                # 2. If two defenders are guarding the ball handler, randomly pick one
                if len(defenders_guarding_ball_handler) == 1:
                    defender_pos = defenders_guarding_ball_handler[0]
                elif len(defenders_guarding_ball_handler) >= 2:
                    # Two or more defenders guarding ball handler - randomly pick one
                    defender_pos = random.choice(defenders_guarding_ball_handler)
                else:
                    # No defender assigned to guard ball handler (shouldn't happen, but fallback)
                    # Fallback: use position match
                    defender_pos = ball_handler_pos
                
                defender = def_lineup.get(defender_pos) if defender_pos else def_lineup.get("PG")
            else:
                # Man-to-man: defender matches ball handler position
                defender = def_lineup.get(ball_handler_pos) if ball_handler_pos else def_lineup.get("PG")
            
            if defender:
                roles["defender"] = defender
    
    # Extract intended shooter from successful variant
    intended_shooter_pos = None
    if successful_skeleton and "steps" in successful_skeleton and successful_skeleton["steps"]:
        final_step = successful_skeleton["steps"][-1]
        for pos, action_info in final_step.get("pos_actions", {}).items():
            action = action_info.get("action", "").lower()
            if action == "shoot":
                intended_shooter_pos = pos
                break
    
    # Store intended shooter in roles for later comparison
    roles["intended_shooter_pos"] = intended_shooter_pos
    
    # ============================================================================
    # STEAL HCO SETUP: Check if this HCO turn comes from a steal
    # ============================================================================
    # ✅ FIX: Only check for Steal HCO Setup if this is NOT a steal turn itself
    # For HCO steals, this function is called during the steal turn, but last_stealer
    # isn't set until resolve_turnover_logic() runs later. We should only run this
    # check in the NEXT HCO turn (after last_stealer has been set).
    last_stealer = game_state.get("last_stealer")
    is_steal_hco_setup = False
    hco_setup_move_x = 0
    hco_setup_move_y = 0
    hco_setup_final_x = None
    hco_setup_final_y = None
    
    # ✅ FIX: Run HCO Setup if last_stealer exists and next turn is HCO
    # This runs regardless of the current turn's result (even if it's another steal)
    # Once a steal happens and transitions to HCO, the HCO Setup Step should always run in the next HCO turn
    if last_stealer:
        # Check if the previous turn was a steal that transitioned to HCO
        # This happens when last_stealer is set and offensive_state is HCO (not FAST_BREAK)
        offensive_state = game_state.get("offensive_state")
        if offensive_state == "HCO":
            is_steal_hco_setup = True
            ball_handler = last_stealer
            
            # ✅ FIX: Use stored stealer position from skeleton step (if available)
            # This ensures we use the position at the exact moment of the steal, not stale coords
            if "last_stealer_coords" in game_state and game_state["last_stealer_coords"]:
                stealer_coords = game_state["last_stealer_coords"]
                ball_handler_start_x = stealer_coords.get("x", 50)
                ball_handler_start_y = stealer_coords.get("y", 25)
            else:
                ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
                ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)
            
            # Determine direction away from basket (opposite of steal entry)
            # Home offense: basket at x=90, so away = -1 (left, toward x=10)
            # Away offense: basket at x=10, so away = +1 (right, toward x=90)
            is_away_offense = off_team.team_id == game.away_team.team_id
            if is_away_offense:
                direction = 1  # Away from x=10 (toward x=90)
            else:
                direction = -1  # Away from x=90 (toward x=10)
            
            # Calculate steal HCO setup movement (away from basket)
            hco_setup_move_x = random.randint(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX)
            hco_setup_move_y = random.randint(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE)
            
            # Apply movement away from basket
            hco_setup_final_x = ball_handler_start_x + (direction * hco_setup_move_x)
            hco_setup_final_y = max(STEAL_HCO_SETUP_Y_MIN, min(STEAL_HCO_SETUP_Y_MAX, ball_handler_start_y + hco_setup_move_y))
            
            # Calculate movement for all 9 other players (toward the new offense basket)
            # x_direction: +1 for home offense (toward x=90), -1 for away offense (toward x=10)
            x_direction = 1 if not is_away_offense else -1
            
            # Get ball handler position to check if they're the PG
            ball_handler_pos = get_player_position(off_lineup, ball_handler)
            ball_handler_id = getattr(ball_handler, "player_id", None)
            is_ball_handler_pg = (ball_handler_pos == "PG")
            
            # Calculate target positions for offensive players (excluding ball handler and PG)
            other_players_movements = []
            pg_movement = None
            
            # First, handle PG positioning if ball handler is not the PG
            if not is_ball_handler_pg and "PG" in off_lineup:
                pg_player = off_lineup["PG"]
                pg_id = getattr(pg_player, "player_id", None)
                pg_coords = getattr(pg_player, "coords", {})
                pg_start_x = pg_coords.get("x", 50)
                pg_start_y = pg_coords.get("y", 25)
                
                # PG moves to a spot relative to ball handler
                # Y: ±6 coords from ball handler
                pg_move_y = random.randint(-6, 6)
                pg_final_y = max(4, min(46, ball_handler_start_y + pg_move_y))
                
                # X: 3-9 coords from ball handler in direction of offense basket
                # Away team: -9 to -3 (toward x=10), Home team: 3 to 9 (toward x=90)
                pg_move_x_distance = random.randint(3, 9)
                pg_move_x = x_direction * pg_move_x_distance  # x_direction: -1 for away, +1 for home
                pg_final_x = ball_handler_start_x + pg_move_x
                # Clamp x to court bounds (4-97)
                pg_final_x = max(4, min(97, pg_final_x))
                
                pg_movement = {
                    "player_id": pg_id,
                    "start_x": pg_start_x,
                    "start_y": pg_start_y,
                    "final_x": pg_final_x,
                    "final_y": pg_final_y,
                    "move_x": pg_move_x,  # Already signed (x_direction * distance)
                    "move_y": pg_move_y
                }
            
            # Now handle all other players from both teams (excluding ball handler and offensive PG)
            # Get offensive PG ID to exclude it
            offensive_pg_id = None
            if "PG" in off_lineup:
                offensive_pg_id = getattr(off_lineup["PG"], "player_id", None)
            
            # Helper function to calculate and add player movement
            def add_player_movement(player, player_id):
                # Get player's current position
                player_coords = getattr(player, "coords", {})
                player_start_x = player_coords.get("x", 50)
                player_start_y = player_coords.get("y", 25)
                
                # Calculate movement toward new offense basket
                other_move_x = random.randint(
                    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN,
                    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX
                )
                other_move_y = random.randint(
                    -STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE,
                    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE
                )
                
                # Apply movement toward basket
                other_final_x = player_start_x + (x_direction * other_move_x)
                # Clamp x to court bounds (4-97)
                other_final_x = max(4, min(97, other_final_x))
                # Apply y movement and clamp
                other_final_y = max(
                    STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN,
                    min(STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MAX, player_start_y + other_move_y)
                )
                
                other_players_movements.append({
                    "player_id": player_id,
                    "start_x": player_start_x,
                    "start_y": player_start_y,
                    "final_x": other_final_x,
                    "final_y": other_final_y,
                    "move_x": other_move_x,
                    "move_y": other_move_y
                })
            
            # Iterate through offensive players (excluding ball handler and PG)
            for pos, player in off_lineup.items():
                player_id = getattr(player, "player_id", None)
                if player_id == ball_handler_id:
                    continue  # Skip ball handler
                if player_id == offensive_pg_id:
                    continue  # Skip offensive PG (handled separately above)
                
                add_player_movement(player, player_id)
            
            # Iterate through defensive players (all defensive players move, none can be ball handler or offensive PG)
            for pos, player in def_lineup.items():
                player_id = getattr(player, "player_id", None)
                add_player_movement(player, player_id)
            
            # Add PG movement to the list if it exists
            if pg_movement:
                other_players_movements.append(pg_movement)
            
            # Store in roles for frontend
            roles["is_steal_hco_setup"] = True
            roles["ball_handler_hco_setup_x"] = hco_setup_final_x
            roles["ball_handler_hco_setup_y"] = hco_setup_final_y
            roles["ball_handler_hco_setup_move_x"] = hco_setup_move_x
            roles["ball_handler_hco_setup_move_y"] = hco_setup_move_y
            roles["ball_handler_id"] = ball_handler_id
            roles["other_players_hco_setup_movements"] = other_players_movements
            roles["hco_setup_x_direction"] = x_direction
            
            # Clear last_stealer and stored skeleton data after using it (so it doesn't persist to subsequent turns)
            game_state["last_stealer"] = None
            game_state.pop("steal_stop_step_index", None)
            game_state.pop("steal_original_skeleton_steps", None)
            game_state.pop("last_stealer_coords", None)
    
    # print("inside resolve_half_court_offense_logic")
    # print("[DEBUG] roles:", roles.keys())
    # print("[DEBUG] event_step:", roles.get("event_step"))
    # print("[DEBUG] steps:", roles.get("steps"))
    # print("[DEBUG] shooter:", roles.get("shooter"))

    # ✅ SS&S FIX: Apply energy decay for ALL HCO turns (both SHOT and non-SHOT)
    # Energy decay was previously inside determine_event_type(), but we bypass that
    # for SHOT results in the stopper system. Extract energy decay to ensure it
    # always runs regardless of event type.
    apply_energy_decay(off_lineup, def_lineup)
    
    # ✅ SS&S: Recharge energy for bench players (50% chance to add 0.01 per turn)
    apply_bench_energy_recharge(game)

    # 2. Event Determination
    # Use result from generate_logic() for stopper results, otherwise determine from skeleton
    if result != "SHOT":
        # Map stopper result to event_type
        if result == "O_FOUL":
            event_type = "O_FOUL"
            logging.warning(f"🔍 [HCO] result=O_FOUL, setting event_type=O_FOUL - offense_team={game.offense_team.name}, defense_team={game.defense_team.name}")
        elif result == "D_FOUL":
            event_type = "D_FOUL"
        elif result == "DEAD_BALL_TURNOVER":
            event_type = "TURNOVER"
        elif result == "STEAL":
            event_type = "TURNOVER"
        else:
            # Fallback: determine from skeleton analysis
            event_type = game.turn_manager.determine_event_type(roles)
    else:
        # Normal flow: result == "SHOT", proceed to shot resolution
        # ✅ SS&S FIX: Commented out determine_event_type() call to avoid conflicts
        # When result == "SHOT" from generate_logic(), we should proceed directly to shot resolution
        # determine_event_type() can return non-SHOT values (e.g., "D_FOUL") which conflicts with stopper system
        # TODO: Revisit determine_event_type() usage if needed for future enhancements
        # event_type = game.turn_manager.determine_event_type(roles)
        # if event_type == "SHOT" or event_type is None:
        #     event_type = "SHOT"
        event_type = "SHOT"

    if event_type != "SHOT":
        # ✅ STOPER SYSTEM: Populate roles for stopper results using SS&S helper functions
        # Use same player determination logic as FCP/HCT for consistency
        
        # Determine ball handler from skeleton (from stopper step or last step)
        # ✅ FIX: Use ball_handler from roles if already set (from defender override logic)
        # Otherwise, determine from skeleton (for cases where override didn't run)
        if "ball_handler" in roles and roles["ball_handler"]:
            ball_handler = roles["ball_handler"]
        else:
            ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
            roles["ball_handler"] = ball_handler
        
        ball_handler_pos = getattr(ball_handler, 'position', None) or "PG"
        
        # ✅ FIX: Only set defender if not already set by override logic
        # The defender override logic (for steals/turnovers/fouls) should have already set
        # the correct defender based on ball handler position and zone/man defense
        if "defender" not in roles or not roles["defender"]:
            # Determine defender based on ball handler position (same as FCP/HCT)
            defender = def_lineup.get(ball_handler_pos, def_lineup.get("PG", list(def_lineup.values())[0] if def_lineup else None))
            roles["defender"] = defender
        else:
            # Use the defender that was already set by override logic
            defender = roles["defender"]
        
        # Set foul_player using SS&S helper function (same as FCP/HCT)
        if event_type in ["O_FOUL", "D_FOUL"]:
            foul_team_type = "OFFENSE" if event_type == "O_FOUL" else "DEFENSE"
            foul_player = select_foul_player(foul_team_type, ball_handler, off_lineup, def_lineup)
            roles["foul_player"] = foul_player
            # Ensure shooter is set (needed by resolve_non_shooting_foul)
            if "shooter" not in roles or not roles["shooter"]:
                roles["shooter"] = ball_handler
        
        # Convert truncated skeleton to animations
        animator = Animator(game)
        animations = []
        if skeleton and "steps" in skeleton:
            animations = animator.skeleton_to_animations(
                skeleton,
                off_lineup,
                def_lineup,
                add_defenders=True
            )
        
        # ✅ FIX: Extract stealer position from generated animations (SS&S approach)
        # This uses the actual calculated defensive position from the animation system,
        # avoiding coordinate orientation issues and reusing existing calculations
        # Always extract for new steals - coordinates will be cleared after use in followup turn
        # For stopper results (steal, foul, turnover), the stopper step is always the final step,
        # so we can simply use animation["end"] to get the final coordinates
        if event_type == "TURNOVER" and result == "STEAL" and animations and defender:
            # ✅ SS&S: Clear old steal data before setting new steal data (prevents stale data from previous steals)
            game_state.pop("last_stealer_coords", None)
            game_state["last_stealer"] = None
            
            stealer_id = getattr(defender, "player_id", None)
            
            if stealer_id:
                # Find the defensive animation for the stealer
                stealer_animation = None
                for anim in animations:
                    if anim.get("playerId") == stealer_id:
                        stealer_animation = anim
                        break
                
                if stealer_animation and "end" in stealer_animation:
                    # Use the final coordinates from the animation (stopper step is always final)
                    stealer_coords = stealer_animation["end"]
                    game_state["last_stealer_coords"] = stealer_coords.copy()
                    logging.warning(f"🏀 [STEAL POSITION] Extracted final coords from animation end: x={stealer_coords['x']}, y={stealer_coords['y']}")
                else:
                    logging.warning(f"⚠️ [STEAL POSITION] Could not find stealer animation or 'end' field (stealer_id={stealer_id}, has_animation={stealer_animation is not None}, has_end={stealer_animation and 'end' in stealer_animation if stealer_animation else False})")
            else:
                logging.warning(f"⚠️ [STEAL POSITION] Missing stealer_id")
        
        #need to add animations to each of these
        if event_type == "TURNOVER":
            # Use result to determine turnover type (STEAL vs DEAD BALL)
            turnover_type = "STEAL" if result == "STEAL" else "DEAD BALL"
            turn_result = resolve_turnover_logic(roles, game, turnover_type=turnover_type)
            # Add skeleton and animations to result
            turn_result["skeleton"] = skeleton or {}
            turn_result["animations"] = animations
            # ✅ FIX: Add serializable roles data (only include fields needed for frontend, not Player objects)
            serializable_roles = {}
            if roles.get("is_steal_hco_setup"):
                serializable_roles["is_steal_hco_setup"] = True
                serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
                serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
                serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
                serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
                serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
                serializable_roles["other_players_hco_setup_movements"] = roles.get("other_players_hco_setup_movements", [])
                serializable_roles["hco_setup_x_direction"] = roles.get("hco_setup_x_direction")
            if serializable_roles:
                turn_result["roles"] = serializable_roles
            return turn_result

        elif event_type == "O_FOUL":
            game_state["foul_team"] = "OFFENSE"
            logging.warning(f"🔍 [HCO O_FOUL] About to call resolve_non_shooting_foul() - offense_team={game.offense_team.name}, defense_team={game.defense_team.name}")
            foul_result = resolve_non_shooting_foul(roles, game)
            logging.warning(f"🔍 [HCO O_FOUL] After resolve_non_shooting_foul() - offense_team={game.offense_team.name}, defense_team={game.defense_team.name}, possession_flips={foul_result.get('possession_flips')}")
            # Add skeleton and animations to result
            foul_result["skeleton"] = skeleton or {}
            foul_result["animations"] = animations
            # ✅ FIX: Add serializable roles data (only include fields needed for frontend, not Player objects)
            serializable_roles = {}
            if roles.get("is_steal_hco_setup"):
                serializable_roles["is_steal_hco_setup"] = True
                serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
                serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
                serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
                serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
                serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
                serializable_roles["other_players_hco_setup_movements"] = roles.get("other_players_hco_setup_movements", [])
                serializable_roles["hco_setup_x_direction"] = roles.get("hco_setup_x_direction")
            if serializable_roles:
                foul_result["roles"] = serializable_roles
            return foul_result

        elif event_type == "D_FOUL":
            game_state["foul_team"] = "DEFENSE"
            foul_result = resolve_non_shooting_foul(roles, game)
            # Add skeleton and animations to result
            foul_result["skeleton"] = skeleton or {}
            foul_result["animations"] = animations
            # ✅ FIX: Add serializable roles data (only include fields needed for frontend, not Player objects)
            serializable_roles = {}
            if roles.get("is_steal_hco_setup"):
                serializable_roles["is_steal_hco_setup"] = True
                serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
                serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
                serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
                serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
                serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
                serializable_roles["other_players_hco_setup_movements"] = roles.get("other_players_hco_setup_movements", [])
                serializable_roles["hco_setup_x_direction"] = roles.get("hco_setup_x_direction")
            if serializable_roles:
                foul_result["roles"] = serializable_roles
            return foul_result

    # 3. Shot Result
    # ✅ MOTION OFFENSE: Check if this is a Motion play and route to Motion shot logic
    offense_play_type = game_state.get("offense_play_type", "")
    is_motion_play = offense_play_type == "motion"
    
    if is_motion_play and event_type == "SHOT":
        # Motion play shot resolution
        motion_shot_info = resolve_motion_offense_shot(skeleton, game, off_lineup, def_lineup)
        
        if motion_shot_info:
            # Update skeleton with Motion shot modifications
            skeleton = motion_shot_info["skeleton"]
            
            # ✅ FIX 1: Update roles["steps"] with modified skeleton steps for 3-point detection
            # The shot detection logic looks in roles["steps"], so we need to update it
            if "steps" in skeleton:
                roles["steps"] = skeleton["steps"]
            
            # Update roles with Motion shot information
            roles["shooter"] = motion_shot_info["shooter"]
            roles["shooter_pos"] = motion_shot_info["shooter_pos"]
            roles["shooter_location"] = motion_shot_info["shooter_location"]
            roles["motion_shot_type"] = motion_shot_info["shot_type"]
            roles["motion_playcall"] = motion_shot_info["playcall"]
            roles["motion_attack_penalty"] = motion_shot_info["attack_penalty"]
            
            # Store attack penalty in game_state for shot calculation
            if motion_shot_info["attack_penalty"] > 0:
                game_state["motion_attack_penalty"] = motion_shot_info["attack_penalty"]
    
    # Resolve shot (standard logic for Set Plays, Motion-specific logic applied above)
    shot_result = game.shot_manager.resolve_shot(roles)
    
    # Add playcall and variant debug info to the text
    variant = skeleton.get("_variant", "unknown") if skeleton else "unknown"
    variant_modifiers = {
        "successful": -50,
        "mid_play_change": 0,
        "contested": 25,
        "broken": 100
    }
    modifier = variant_modifiers.get(variant, 0)
    
    # Use variant_result from resolution system (replaces lean_score)
    variant_display = variant_result if variant_result else variant
    debug_info = f"[{off_call}] {variant_display}, modifier:{modifier:+d} | "
    shot_result["text"] = debug_info + shot_result.get("text", "")
    
    # Pass next_defensive_setup to animator via roles
    if "next_defensive_setup" in shot_result:
        roles["next_defensive_setup"] = shot_result["next_defensive_setup"]
    
    animator = Animator(game)
    # OLD ANIMATION SYSTEM - REMOVED (conflicts with skeleton-based system)
    # shot_result["animations"] = animator.capture_halfcourt_animation(roles)
    
    # Add skeleton data for unified animation system (reuse skeleton from line 556)
    shot_result["skeleton"] = skeleton or {}
    # Add skeleton variant for debugging (temporary - will be removed after debugging)
    if skeleton and "_variant" in skeleton:
        shot_result["skeleton_variant"] = skeleton["_variant"]
    
    # ✅ FIX 2: Add playcall name to result for Playcall Center display (Motion plays)
    if is_motion_play:
        shot_result["offensive_playcall"] = game_state["current_playcall"]
        shot_result["current_playcall"] = game_state["current_playcall"]  # Also set current_playcall for compatibility
    
    # ✅ Add serializable roles data to result (includes steal HCO setup data if applicable)
    # Only include serializable fields, not player objects
    # Note: turn_manager.convert_players() will handle player objects in other result fields,
    # but we only store the specific fields we need here to avoid serialization issues
    serializable_roles = {}
    if roles.get("is_steal_hco_setup"):
        serializable_roles["is_steal_hco_setup"] = True
        serializable_roles["ball_handler_hco_setup_x"] = roles.get("ball_handler_hco_setup_x")
        serializable_roles["ball_handler_hco_setup_y"] = roles.get("ball_handler_hco_setup_y")
        serializable_roles["ball_handler_hco_setup_move_x"] = roles.get("ball_handler_hco_setup_move_x")
        serializable_roles["ball_handler_hco_setup_move_y"] = roles.get("ball_handler_hco_setup_move_y")
        serializable_roles["ball_handler_id"] = roles.get("ball_handler_id")
    if roles.get("next_defensive_setup"):
        serializable_roles["next_defensive_setup"] = roles.get("next_defensive_setup")
    if roles.get("intended_shooter_pos"):
        serializable_roles["intended_shooter_pos"] = roles.get("intended_shooter_pos")
    if serializable_roles:  # Only add roles if we have something to add
        shot_result["roles"] = serializable_roles
    
    # Convert skeleton to animations if skeleton exists
    if skeleton and "steps" in skeleton:
        skeleton_animations = animator.skeleton_to_animations(
            skeleton, 
            off_lineup, 
            def_lineup, 
            add_defenders=True
        )
        if skeleton_animations:
            shot_result["animations"] = skeleton_animations

    # 4. scouting report update (new buckets)
    try:
        play_type = game.game_state.get("offense_play_type")  # 'motion' or 'set_play'
        # ✅ MOTION OFFENSE: Use actual shot type for Motion plays, intended focus for Set Plays
        if play_type == "motion":
            # For Motion plays, use the actual shot type that was attempted
            motion_shot_type = roles.get("motion_shot_type")  # 'inside', 'attack', or 'outside'
            focus = motion_shot_type if motion_shot_type in ["inside", "attack", "outside"] else game.game_state.get("offense_play_focus", "")
        else:
            # For Set Plays, use the intended focus from strategy settings
            focus = game.game_state.get("offense_play_focus")     # 'inside' | 'attack' | 'outside'
        type_label = "Motion" if play_type == "motion" else ("Set" if play_type == "set_play" else None)
        if type_label and focus in ["inside", "attack", "outside"]:
            pc = off_team.scouting_data["offense"]["Playcalls"]
            
            # ✅ MOTION OFFENSE: Track attempts using actual shot type (after shot resolution)
            # Set Plays: Attempts already tracked in turn_manager.py using intended focus
            if play_type == "motion":
                # Track attempts for Motion plays using actual shot type
                pc[type_label]["overall"]["attempts"] += 1
                pc[type_label][focus]["attempts"] += 1
                pc["Cumulative"][focus]["attempts"] += 1
                
                # Track granular attempts against defensive playcall
                from BackEnd.utils.defense_utils import is_zone_defense
                defense_playcall = game.game_state.get("defense_playcall", "Man")  # "Man", "2-3 Zone", etc.
                
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
                
                if vs_key:
                    # Overall attempts vs defense
                    if vs_key in pc[type_label]["overall"]:
                        pc[type_label]["overall"][vs_key]["attempts"] += 1
                    # Focus attempts vs defense
                    if vs_key in pc[type_label][focus]:
                        pc[type_label][focus][vs_key]["attempts"] += 1
                    
                    # Track aggregate vs_zone for any zone type
                    if is_zone_defense(defense_playcall) and "vs_zone" in pc[type_label]["overall"]:
                        pc[type_label]["overall"]["vs_zone"]["attempts"] += 1
                        pc[type_label][focus]["vs_zone"]["attempts"] += 1
            
            rt = shot_result.get("result_type")
            foul_team = game.game_state.get("foul_team")
            # print(f"🎯 SUCCESS DEBUG: rt={rt}, foul_team={foul_team}")
            # Offense success conditions: made shot OR any defensive foul (shooting or non-shooting)
            # Note: When defensive foul occurs on a missed shot, rt is still "MISS" but foul_team is "DEFENSE"
            offense_success = (rt == "MAKE") or (foul_team == "DEFENSE")
            # print(f"🎯 SUCCESS DEBUG: offense_success={offense_success}, rt=='MAKE'={rt == 'MAKE'}, foul_team=='DEFENSE'={foul_team == 'DEFENSE'}")
            # if rt == "MAKE":
            #     print(f"🎯 MADE SHOT SUCCESS: Play type={type_label}, focus={focus} - should increment success")
            # Defense success conditions
            offense_failure = (rt == "MISS" and not (foul_team == "DEFENSE")) or (rt == "TURNOVER") or (rt == "O_FOUL")
            # print(f"🎯 SUCCESS DEBUG: offense_failure={offense_failure}")
            if offense_success:
                # print(f"🎯 SUCCESS DEBUG: Incrementing success for {type_label}/{focus}")
                # print(f"🎯 SUCCESS DEBUG: Before - overall: {pc[type_label]['overall']['success']}, {focus}: {pc[type_label][focus]['success']}, Cumulative: {pc['Cumulative'][focus]['success']}")
                pc[type_label]["overall"]["success"] += 1
                pc[type_label][focus]["success"] += 1
                pc["Cumulative"][focus]["success"] += 1
                
                # Track granular success against defensive playcall
                from BackEnd.utils.defense_utils import is_zone_defense
                defense_playcall = game.game_state.get("defense_playcall", "Man")  # "Man", "2-3 Zone", etc.
                
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
                
                if vs_key:
                    # Overall success vs defense
                    if vs_key in pc[type_label]["overall"]:
                        pc[type_label]["overall"][vs_key]["success"] += 1
                    # Focus success vs defense
                    if vs_key in pc[type_label][focus]:
                        pc[type_label][focus][vs_key]["success"] += 1
                    
                    # Track aggregate vs_zone for any zone type
                    if is_zone_defense(defense_playcall) and "vs_zone" in pc[type_label]["overall"]:
                        pc[type_label]["overall"]["vs_zone"]["success"] += 1
                        pc[type_label][focus]["vs_zone"]["success"] += 1
                
                # print(f"🎯 SUCCESS DEBUG: After - overall: {pc[type_label]['overall']['success']}, {focus}: {pc[type_label][focus]['success']}, Cumulative: {pc['Cumulative'][focus]['success']}")
            elif offense_failure:
                # We don't increment offense success; defensive success can be tracked separately if needed
                pass
            
            # Track defensive playcall success with granular tracking
            defense_playcall = game.game_state.get("defense_playcall", "Man")  # "Man", "2-3 Zone", etc.
            # Defense playcall is now stored as specific name (e.g., "2-3 Zone")
            tracking_name = defense_playcall  # Use specific name directly
            if tracking_name in def_team.scouting_data["defense"]:
                # Defense success = MISS (without defensive foul) OR TURNOVER OR O_FOUL
                # Defense failure = MAKE OR DEFENSIVE FOUL
                defense_success = (rt == "MISS" and not (foul_team == "DEFENSE")) or (rt == "TURNOVER") or (rt == "O_FOUL")
                defense_failure = (rt == "MAKE") or (foul_team == "DEFENSE")
                
                # Get offensive play type and focus for granular tracking
                offense_play_type = game.game_state.get("offense_play_type", "").lower()  # "motion" or "set_play"
                offense_focus = game.game_state.get("offense_play_focus", "")  # "inside", "attack", "outside"
                
                # Normalize play type (set_play -> set)
                if offense_play_type == "set_play":
                    offense_play_type = "set"
                
                if defense_success:
                    def_team.scouting_data["defense"][tracking_name]["success"] += 1
                    def_team.scouting_data["defense"][tracking_name]["game_stats"]["success"] += 1
                    
                    # Track granular success by play type
                    if offense_play_type == "motion":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_motion"]["success"] += 1
                    elif offense_play_type == "set":
                        def_team.scouting_data["defense"][tracking_name]["game_stats"]["vs_set"]["success"] += 1
                    
                    # Track granular success by focus type
                    if offense_focus in ["inside", "attack", "outside"]:
                        def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_{offense_focus}"]["success"] += 1
                        
                        # Track combination of play type + focus
                        if offense_play_type == "motion":
                            def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_motion_{offense_focus}"]["success"] += 1
                        elif offense_play_type == "set":
                            def_team.scouting_data["defense"][tracking_name]["game_stats"][f"vs_set_{offense_focus}"]["success"] += 1
                elif defense_failure:
                    # Defense failed (offense scored or committed defensive foul)
                    pass  # Don't increment success (already at current count)
            
            # Clear foul_team after success tracking to prevent it from affecting subsequent actions (like putbacks)
            # Note: Only clear if this is the original HCO play, not a putback (putbacks have result_type PUTBACK_MAKE/PUTBACK_MISS)
            if rt in ["MAKE", "MISS"]:
                game.game_state["foul_team"] = None
                # print(f"🎯 SUCCESS DEBUG: Cleared foul_team after HCO play (rt={rt})")
        else:
            pass
            # print(f"🎯 SUCCESS DEBUG: Skipping - type_label={type_label}, focus={focus}")
    except Exception as e:
        # Error logging kept - important for debugging actual errors
        logging.error(f"🎯 SUCCESS DEBUG ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    return shot_result


def calculate_foul_turnover(game, positions, roles):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    roles["foul_player"] = None
    ball_handler = roles["ball_handler"]
    defense_call = game_state["defense_playcall"]

    # === Defensive Foul ===
    d_pos = positions["d_foul"]
    d_foul_player = def_lineup[d_pos]
    d_attr = d_foul_player.attributes

    d_movement = (
        d_attr["OD"] * 0.2 + d_attr["AG"] * 0.2 if d_pos in ["PG", "SG"] else
        d_attr["OD"] * 0.1 + d_attr["ID"] * 0.1 + d_attr["AG"] * 0.1 + d_attr["ST"] * 0.1 if d_pos == "SF" else
        d_attr["ID"] * 0.2 + d_attr["ST"] * 0.2 if d_pos in ["PF", "C"] else
        0
    )

    d_foul_score = (d_attr["IQ"] * 0.3 + d_attr["CH"] * 0.3 + d_movement) * random.randint(1, 6)
    from BackEnd.utils.defense_utils import is_zone_defense
    if is_zone_defense(defense_call):
        d_foul_score *= 1.1
    is_d_foul = d_foul_score < def_team.team_attributes["foul_modifier"] * 1.2

    # === Offensive Foul ===
    o_pos = positions["o_foul"]
    o_foul_player = off_lineup[o_pos]
    o_attr = o_foul_player.attributes

    o_movement = (
        o_attr["AG"] * 0.4 if o_pos in ["PG", "SG"] else
        o_attr["AG"] * 0.2 + o_attr["ST"] * 0.2 if o_pos == "SF" else
        o_attr["ST"] * 0.4 if o_pos in ["PF", "C"] else
        0
    )

    o_foul_score = (o_attr["IQ"] * 0.3 + o_attr["CH"] * 0.3 + o_movement) * random.randint(1, 6)
    is_o_foul = o_foul_score < off_team.team_attributes["foul_modifier"] * 0.8

    # === Turnover ===
    t_pos = positions["turnover"]
    turnover_player = off_lineup[t_pos]
    t_attr = turnover_player.attributes

    bh_score = (
        t_attr["BH"] * 0.5 +
        t_attr["AG"] * 0.2 +
        t_attr["IQ"] * 0.2 +
        t_attr["CH"] * 0.1
    ) * random.randint(1, 6)

    def_mod_player = def_lineup[t_pos]
    def_mod_attr = def_mod_player.attributes

    pressure = (
        def_mod_attr["OD"] * 0.3 +
        def_mod_attr["AG"] * 0.3 +
        def_mod_attr["IQ"] * 0.2 +
        def_mod_attr["CH"] * 0.2
    ) * random.randint(1, 6)
    from BackEnd.utils.defense_utils import is_zone_defense
    if is_zone_defense(defense_call):
        pressure *= 0.9

    turnover_score = bh_score - pressure
    is_turnover = turnover_score < off_team.team_attributes["turnover_modifier"]

    # === Decide event type
    decisions = {
        "TURNOVER": (is_turnover, turnover_score),
        "D_FOUL": (is_d_foul, d_foul_score),
        "O_FOUL": (is_o_foul, o_foul_score),
    }

    active = [(k, v[1]) for k, v in decisions.items() if v[0]]
    if not active:
        return "SHOT"

    # Prioritize by score, then priority: TURNOVER > D_FOUL > O_FOUL
    active.sort(key=lambda x: (x[1], ["TURNOVER", "D_FOUL", "O_FOUL"].index(x[0])))

    event_type = active[0][0]
    if event_type == "TURNOVER":
        roles["turnover_player"] = turnover_player
        roles["turnover_defender"] = def_mod_player
        roles["ball_handler"] = turnover_player
    elif event_type == "D_FOUL":
        roles["foul_player"] = d_foul_player
    elif event_type == "O_FOUL":
        roles["foul_player"] = o_foul_player

    return event_type


def resolve_full_court_press_logic(game: "GameManager"):
    """
    Resolve full court press defensive pressure.
    Returns turn data with FCP result and potential progression to HCO.
    """
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    # Track FCP attempt (defensive team)
    def_scouting = def_team.scouting_data
    def_scouting["defense"]["FCP"]["used"] += 1

    text = "PRESS!"
    offenseScore = 0
    defenseScore = 0

    for pos, player in off_lineup.items():
        if pos == "PG":
            offenseScore += 3 * (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
        elif pos in ["SG", "SF"]:
            offenseScore += (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
    for pos, player in def_lineup.items():
        if pos == "PG":
            defenseScore += 3 * (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
        elif pos in ["SG", "SF"]:
            defenseScore += (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
    
    offenseScore *= random.randint(1, 6)
    defenseScore *= random.randint(1, 6)
    turnover_type = random.choices(["TRAVEL", "DOUBLE DRIBBLE", "BAD PASS"], weights=[0.6, 0.3, 0.1])[0]
    # print("Inside resolve_full_court_press_logic")
    # print(f"offenseScore: {offenseScore}")
    # print(f"defenseScore: {defenseScore}")

    # Real FCP result calculation
    if (offenseScore + 500) > defenseScore:
        if offenseScore - defenseScore > 1000:
            result_type = random.choices(["D_FOUL", "HCO", "SHOT"], weights=[0.3, 0.5, 0.2])[0]
        else:
            result_type = "HCO"
    else:
        result_type = random.choices(["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"], weights=[0.2, 0.5, 0.3])[0]
    
    result_text_dict = {
        "HCO": "they break the press & establish their half court offense",
        "D_FOUL": "defensive foul!",
        "O_FOUL": "offensive foul!",
        "DEAD_BALL_TURNOVER": f"they force a {turnover_type}!",
        "STEAL": "steal!",
        "SHOT": "they break the press & attempt a shot!"
    }
    
    text += "\n" + result_text_dict[result_type]

    # Initialize shot_result for all cases
    shot_result = {}
    
    # Initialize animator for all cases
    from BackEnd.models.animator import Animator
    animator = Animator(game)
    animations = []
    
    # Handle SHOT result - execute actual shot resolution
    if result_type == "SHOT":
        # Build roles for shot
        passer = off_lineup.get("PG", list(off_lineup.values())[0])
        shooter = random.choice([off_lineup.get("PF"), off_lineup.get("C")])
        defender = def_lineup.get("PG", list(def_lineup.values())[0])
        
        shot_roles = {
            "ball_handler": passer,
            "shooter": shooter,
            "passer": passer,
            "screener": None,
            "defender": defender,
        }
        
        # Use shot manager to resolve the shot
        shot_result = game.shot_manager.resolve_shot(shot_roles)
        
        # FCP/HCT is over once shot is taken - reset to HCO
        # (Unless it's a made shot, in which case pressure might apply on the inbound)
        if shot_result.get("result_type") == "MISS":
            game_state["offensive_state"] = "HCO"
            # Track MISS as defensive success for team
            def_scouting["defense"]["FCP"]["success"] += 1
        
        # Track FCP player stats for SHOT results
        fcp_roles = {
            "ball_handler": passer,
            "shooter": shooter,
            "defender": defender,
        }
        _record_fcp_stats(fcp_roles, shot_result, game, off_lineup, def_lineup)
        
        # Add FCP-specific data
        shot_result["fcp_shot"] = True
        shot_result["text"] = "PRESS! " + shot_result.get("text", "")
        
        # Generate animations from skeleton for the pass, then rely on standard shot animation
        # ✅ FCP/HCT SHOT: Use FCP shot skeleton with version selection (filters non-empty versions)
        logging.warning(f"🔍 [FCP SHOT] Getting skeleton for SHOT variant")
        skeleton = get_fcp_skeleton("SHOT", game) or {}
        logging.warning(f"🔍 [FCP SHOT] Retrieved skeleton: has_steps={bool(skeleton.get('steps'))}, step_count={len(skeleton.get('steps', []))}")
        
        if skeleton and "steps" in skeleton:
            logging.warning(f"🔍 [FCP SHOT] Converting skeleton to animations...")
            animations = animator.skeleton_to_animations(
                skeleton, 
                off_lineup, 
                def_lineup, 
                add_defenders=True,
                is_fcp=True
            )
            logging.warning(f"🔍 [FCP SHOT] Generated {len(animations)} animations")
            if animations:
                shot_result["animations"] = animations
                logging.warning(f"✅ [FCP SHOT] Added animations to shot_result")
            else:
                logging.warning(f"⚠️ [FCP SHOT] No animations generated from skeleton!")
        else:
            logging.warning(f"⚠️ [FCP SHOT] Skeleton has no steps!")
        
        shot_result["skeleton"] = skeleton
        shot_result["roles"] = shot_roles
        
        return shot_result
    
    # ✅ FCP NON-SHOT: Get FCP "base" variant skeleton and apply stopper system
    # For non-shot results (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO), use FCP "base" variant
    # Apply stopper system if result is not HCO (truncate and add stopper step)
    logging.warning(f"🔍 [FCP NON-SHOT] Getting FCP base skeleton for result_type={result_type}")
    skeleton = get_fcp_skeleton(result_type, game)  # Get FCP "base" variant (has step 0 with press break positions)
    
    # Deep copy skeleton to avoid mutating cached skeleton
    if skeleton:
        skeleton = copy.deepcopy(skeleton)
    
    # ✅ DEBUG: Log step 0 positions from HCO skeleton
    if skeleton and "steps" in skeleton and len(skeleton.get("steps", [])) > 0:
        step_0 = skeleton["steps"][0]
        step_0_positions = step_0.get("pos_actions", {})
        logging.warning(f"🔍 [FCP NON-SHOT] HCO skeleton step 0 has {len(step_0_positions)} positions: {list(step_0_positions.keys())}")
        for pos, pos_action in step_0_positions.items():
            location = pos_action.get("location", "N/A")
            coords = pos_action.get("coords", "N/A")
            logging.warning(f"🔍 [FCP NON-SHOT] Step 0 {pos}: location={location}, coords={coords}")
    
    # Apply stopper system (truncates if needed, or returns full skeleton if result == "HCO")
    skeleton = apply_stopper_system_to_skeleton(skeleton, result_type, game_state)
    logging.warning(f"🔍 [FCP NON-SHOT] Retrieved skeleton: has_steps={bool(skeleton.get('steps'))}, step_count={len(skeleton.get('steps', []))}")
    
    # ✅ DEBUG: Log step 0 positions AFTER stopper system (should still be there)
    if skeleton and "steps" in skeleton and len(skeleton.get("steps", [])) > 0:
        step_0_after = skeleton["steps"][0]
        step_0_positions_after = step_0_after.get("pos_actions", {})
        logging.warning(f"🔍 [FCP NON-SHOT] After stopper, step 0 has {len(step_0_positions_after)} positions: {list(step_0_positions_after.keys())}")
    
    # ✅ Determine ball handler from skeleton (who actually has the ball)
    ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
    ball_handler_pos = getattr(ball_handler, 'position', None) or "PG"
    
    # ✅ Determine defender based on ball handler position (position matching for now)
    defender = def_lineup.get(ball_handler_pos, def_lineup.get("PG", list(def_lineup.values())[0]))
    
    # Build roles dict for animation generation
    roles = {
        "ball_handler": ball_handler,
        "defender": defender,
        "shooter": ball_handler,
        "passer": None,
        "screener": None,
    }
    
    # Handle foul results - use standard foul types for frontend
    if result_type == "D_FOUL":
        game_state["foul_team"] = "DEFENSE"
        # ✅ Use dynamically determined ball handler and defender
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("DEFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        def_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out
        check_and_handle_foul_out(foul_player, game_state, def_team)
        result_type = "FOUL"
        # ✅ FIX: Check bonus status for defensive fouls in FCP (per game_flows.md)
        # Defensive fouls should route to FREE_THROW if in bonus, otherwise HCO
        if def_team.team_fouls >= 10:
            # Double bonus (10+ fouls): 2 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2
            game_state["free_throws_remaining"] = 2
            game_state["one_and_one"] = False
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        elif def_team.team_fouls >= 5:
            # Bonus (5-9 fouls): 1 & 1 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2  # Maximum possible (if front end is made)
            game_state["free_throws_remaining"] = 1  # Start with 1 (front end)
            game_state["one_and_one"] = True
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        else:
            # Less than 5 fouls: possession change, side inbound
            game_state["offensive_state"] = "HCO"
            game_state["free_throws"] = 0
            game_state["free_throws_remaining"] = 0
        # text = "PRESS! Defensive foul"
    elif result_type == "O_FOUL":
        game_state["foul_team"] = "OFFENSE"
        # ✅ Use dynamically determined ball handler
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("OFFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        off_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out
        check_and_handle_foul_out(foul_player, game_state, off_team)
        result_type = "FOUL"
        # text = "PRESS! Offensive foul"
        # Track FCP success: offensive foul = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
    elif result_type == "DEAD_BALL_TURNOVER":
        result_type = "DEAD BALL"
        # text = "PRESS! Turnover"
        # ✅ Use dynamically determined ball handler
        # Record TO stat for the ball handler
        ball_handler.record_stat("TO")
        # Track FCP success: turnover = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
    elif result_type == "STEAL":
        # ✅ Use dynamically determined ball handler and defender
        # Record TO stat for the ball handler (victim of steal)
        ball_handler.record_stat("TO")
        # Record STL stat for the defender (guarding ball handler)
        if defender:
            defender.record_stat("STL")
        # Track FCP success: steal = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
        
        # ✅ FIX: Set last_stealer for FCP steals (so Steal HCO Setup runs in next turn)
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""
    
    if skeleton and "steps" in skeleton:
        logging.warning(f"🔍 [FCP] Converting skeleton to animations (result_type={result_type})...")
        animations = animator.skeleton_to_animations(
            skeleton, 
            off_lineup, 
            def_lineup, 
            add_defenders=True,
            is_fcp=True
        )
        logging.warning(f"🔍 [FCP] Generated {len(animations)} animations")
        
        # ✅ DEBUG: Log step 0 positions from generated animations
        for anim in animations[:5]:  # Log first 5 animations
            player_id = anim.get("playerId", "UNKNOWN")
            movement = anim.get("movement", [])
            if movement and len(movement) > 0:
                step_0_coords = movement[0].get("coords", "N/A")
                logging.warning(f"🔍 [FCP] Animation {player_id[:8]}: step 0 coords={step_0_coords}")
            else:
                logging.warning(f"⚠️ [FCP] Animation {player_id[:8]}: NO MOVEMENT ARRAY or EMPTY!")
        
        # ✅ FIX: Extract stealer position from generated animations (SS&S approach)
        # This uses the actual calculated defensive position from the animation system
        # For stopper results (steal, foul, turnover), the stopper step is always the final step,
        # so we can simply use animation["end"] to get the final coordinates
        if result_type == "STEAL" and animations and defender:
            stealer_id = getattr(defender, "player_id", None)
            
            if stealer_id:
                # Find the defensive animation for the stealer
                stealer_animation = None
                for anim in animations:
                    if anim.get("playerId") == stealer_id:
                        stealer_animation = anim
                        break
                
                if stealer_animation and "end" in stealer_animation:
                    # Use the final coordinates from the animation (stopper step is always final)
                    stealer_coords = stealer_animation["end"]
                    game_state["last_stealer_coords"] = stealer_coords.copy()
                    defender.coords = stealer_coords.copy()
                    logging.warning(f"🏀 [STEAL POSITION] FCP: Extracted final coords from animation end: x={stealer_coords['x']}, y={stealer_coords['y']}")
                else:
                    logging.warning(f"⚠️ [STEAL POSITION] FCP: Could not find stealer animation or 'end' field (stealer_id={stealer_id}, has_animation={stealer_animation is not None}, has_end={stealer_animation and 'end' in stealer_animation if stealer_animation else False})")
            else:
                logging.warning(f"⚠️ [STEAL POSITION] FCP: Missing stealer_id")
        
        if animations:
            shot_result["animations"] = animations
            logging.warning(f"✅ [FCP] Added {len(animations)} animations to shot_result")
        else:
            logging.warning(f"⚠️ [FCP] No animations generated from skeleton!")
    else:
        logging.warning(f"⚠️ [FCP] Skeleton has no steps! skeleton={bool(skeleton)}, has_steps={skeleton.get('steps') if skeleton else False}")
        animations = []
    
    # Determine possession flip
    possession_flips = False
    if result_type == "FOUL" and game_state.get("foul_team") == "OFFENSE":
        possession_flips = True
    elif result_type in ["DEAD BALL", "STEAL"]:
        possession_flips = True
    
    # Handle STEAL: Check for fast break opportunity (STEAL only, not DEAD BALL)
    next_play_type = None
    if result_type == "STEAL":
        if random.random() < get_fast_break_chance(game):
            next_play_type = "FAST_BREAK"
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            next_play_type = "HCO"
            game_state["offensive_state"] = "HCO"
    elif result_type == "HCO":
        # ✅ SS&S: Match Fast Break pattern - set offensive_state when transitioning to HCO
        # This prevents duplicate FCP turns (offensive_state must change from "FCP" to "HCO")
        next_play_type = "HCO"
        game_state["offensive_state"] = "HCO"
    # For DEAD BALL, O_FOUL, D_FOUL: next_play_type stays None (will use side inbound → HCO)
    
    # Calculate time elapsed for FCP phase
    fcp_time_elapsed = random.randint(5, 9)
    
    # If transitioning to HCO, store the FCP time for HCO to add to its time
    if result_type == "HCO":
        game_state["pressure_phase_time"] = fcp_time_elapsed
    
    # Track FCP player stats for non-SHOT results
    fcp_roles = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,  # For non-shot results, ball handler is the "shooter"
        "defender": defender,
    }
    turn_result = {"result_type": result_type}
    _record_fcp_stats(fcp_roles, turn_result, game, off_lineup, def_lineup)
    
    # ✅ SS&S: Set offense_team_id (team on offense DURING this turn)
    # Backend calls switch_possession() after turn if needed, so next turn has correct offense_team
    result = {
        "result_type": result_type,
        "text": text,
        "current_turn": "FCP",  # ✅ SS&S: Explicit turn type
        "next_play_type": next_play_type,
        "next_turn": next_play_type,  # ✅ SS&S: Explicit next turn (HCO, FAST_BREAK, or None)
        "ball_handler": roles["ball_handler"],
        "defender": roles["defender"],
        "shooter": roles["shooter"],
        "passer": "",
        "screener": "",
        "offense_team_id": off_team.team_id,  # ✅ SS&S: Team on offense DURING this turn
        "possession_flips": possession_flips,  # ✅ Backend internal flag (tells backend when to call switch_possession)
        "time_elapsed": fcp_time_elapsed,  # Time spent in FCP phase
        "events": [],
        "skeleton": skeleton,
        "animations": animations,
        "roles": roles,
        "foul_team": game_state.get("foul_team"),  # Include foul_team for frontend announcement
        "foul_player_id": getattr(roles.get("foul_player"), "player_id", None) if roles.get("foul_player") else None,  # For foul announcements
        "victim_id": getattr(roles["ball_handler"], "player_id", None),  # For turnover announcements
        "defender_id": getattr(roles["defender"], "player_id", None) if roles["defender"] else None  # For steal announcements
    }
    
    return result


def get_skeleton_for_turn(result_type, turn_type, game_context=None):
    """
    Universal skeleton getter for all turn types.
    Returns filtered skeleton data based on result_type and turn_type.
    """
    if turn_type == "FCP":
        return get_fcp_skeleton(result_type, game_context)
    elif turn_type == "HCT":
        return get_hct_skeleton(result_type, game_context)
    elif turn_type == "HCO":
        return get_hco_skeleton(result_type, game_context)
    # Future: Add FAST_BREAK, FREE_THROW, etc.
    return None


def get_fcp_skeleton(result_type, game_context=None):
    """
    Get FCP skeleton from MongoDB based on result_type.
    Maps result_type to variant name and randomly selects from available versions.
    
    Args:
        result_type: One of "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", "SHOT", "HCO"
        game_context: Game context object for opposite side logic
    
    Returns:
        dict: Skeleton with steps, or fallback to old hardcoded system
    """
    import random
    from BackEnd.db import fcp_skeletons_collection
    
    # Map result_type to variant name
    # All non-shot results use "base" variant (has step 0 with press break positions)
    variant_map = {
        "O_FOUL": "base",
        "D_FOUL": "base",
        "DEAD_BALL_TURNOVER": "base",
        "STEAL": "base",
        "SHOT": "shot",
        "HCO": "base"  # Press break → HCO transition uses base variant
    }
    
    variant_name = variant_map.get(result_type, "base")  # Default to base
    
    # Try to get skeleton from MongoDB
    try:
        # Get all FCP skeletons (for now, we'll use the first one - can be enhanced later)
        skeleton_doc = fcp_skeletons_collection.find_one({})
        
        if skeleton_doc and "variants" in skeleton_doc:
            variants = skeleton_doc.get("variants", {})
            variant_data = variants.get(variant_name)
            
            if variant_data and "versions" in variant_data:
                versions = variant_data["versions"]
                
                # Ensure versions is a list
                if not isinstance(versions, list):
                    logging.warning(f"⚠️ FCP {variant_name} versions is not a list, falling back to hardcoded")
                else:
                    # Filter to only non-empty versions with valid skeleton data
                    non_empty_versions = []
                    for idx, v in enumerate(versions):
                        steps = v.get("steps") if v else None
                        # Check that steps exists, is a list, and has at least one step
                        if steps and isinstance(steps, list) and len(steps) > 0:
                            non_empty_versions.append(v)
                        # Version validation (spam removed)
                
                if non_empty_versions:
                    # Randomly select one non-empty version
                    selected_version = random.choice(non_empty_versions)
                    selected_steps = selected_version.get("steps", [])
                    skeleton_data = {
                        "steps": selected_steps
                    }
                    
                    # Apply opposite side logic if game context is provided
                    if game_context:
                        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
                        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
                    
                    return skeleton_data
                else:
                    logging.warning(f"⚠️ No non-empty versions for FCP {variant_name} (checked {len(versions)} versions), falling back to hardcoded")
            else:
                logging.warning(f"⚠️ Variant {variant_name} not found in FCP skeleton, falling back to hardcoded")
        else:
            logging.warning("⚠️ No FCP skeletons in MongoDB, falling back to hardcoded")
    except Exception as e:
        logging.warning(f"⚠️ Error loading FCP skeleton from MongoDB: {e}, falling back to hardcoded")
    
    # Fallback to old hardcoded system
    from BackEnd.playcall_skeletons.fcp_skeletons import FCP_SKELETONS_DICT, FCP_1
    end_timestamp = FCP_SKELETONS_DICT.get(result_type, 1200)  # Default to HCO timestamp
    
    skeleton_data = {
        "steps": [step for step in FCP_1["steps"] if step["timestamp"] <= end_timestamp]
    }
    
    # Apply opposite side logic if game context is provided
    if game_context:
        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
    
    return skeleton_data


def get_hct_skeleton(result_type, game_context=None):
    """
    Get HCT skeleton from MongoDB based on result_type.
    Maps result_type to variant name and randomly selects from available versions.
    
    Args:
        result_type: One of "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL", "SHOT", "HCO"
        game_context: Game context object for opposite side logic
    
    Returns:
        dict: Skeleton with steps, or fallback to old hardcoded system
    """
    import random
    from BackEnd.db import hct_skeletons_collection
    
    # Map result_type to variant name
    # All non-shot results use "base" variant (has step 0 with trap break positions)
    variant_map = {
        "O_FOUL": "base",
        "D_FOUL": "base",
        "DEAD_BALL_TURNOVER": "base",
        "STEAL": "base",
        "SHOT": "shot",
        "HCO": "base"  # Trap break → HCO transition uses base variant
    }
    
    variant_name = variant_map.get(result_type, "base")  # Default to base
    
    # Try to get skeleton from MongoDB
    try:
        # Get all HCT skeletons (for now, we'll use the first one - can be enhanced later)
        skeleton_doc = hct_skeletons_collection.find_one({})
        
        if skeleton_doc and "variants" in skeleton_doc:
            variants = skeleton_doc.get("variants", {})
            variant_data = variants.get(variant_name)
            
            if variant_data and "versions" in variant_data:
                versions = variant_data["versions"]
                
                # Ensure versions is a list
                if not isinstance(versions, list):
                    logging.warning(f"⚠️ HCT {variant_name} versions is not a list, falling back to hardcoded")
                else:
                    # Filter to only non-empty versions with valid skeleton data
                    non_empty_versions = []
                    for idx, v in enumerate(versions):
                        steps = v.get("steps") if v else None
                        # Check that steps exists, is a list, and has at least one step
                        if steps and isinstance(steps, list) and len(steps) > 0:
                            non_empty_versions.append(v)
                        # Version validation (spam removed)
                
                if non_empty_versions:
                    # Randomly select one non-empty version
                    selected_version = random.choice(non_empty_versions)
                    selected_steps = selected_version.get("steps", [])
                    skeleton_data = {
                        "steps": selected_steps
                    }
                    
                    # Apply opposite side logic if game context is provided
                    if game_context:
                        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
                        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
                    
                    return skeleton_data
                else:
                    logging.warning(f"⚠️ No non-empty versions for HCT {variant_name} (checked {len(versions)} versions), falling back to hardcoded")
            else:
                logging.warning(f"⚠️ Variant {variant_name} not found in HCT skeleton, falling back to hardcoded")
        else:
            logging.warning("⚠️ No HCT skeletons in MongoDB, falling back to hardcoded")
    except Exception as e:
        logging.warning(f"⚠️ Error loading HCT skeleton from MongoDB: {e}, falling back to hardcoded")
    
    # Fallback to old hardcoded system
    from BackEnd.playcall_skeletons.hct_skeletons import HCT_SCENES, HCT_SKELETONS_DICT
    
    # Get the appropriate end timestamp for this result type
    end_timestamp = HCT_SKELETONS_DICT.get(result_type, 1200)
    
    # Randomly select an HCT scene
    selected_scene = random.choice(HCT_SCENES)
    
    # Filter steps by timestamp
    skeleton_data = {
        "steps": [step for step in selected_scene["steps"] if step["timestamp"] <= end_timestamp]
    }
    
    # Apply opposite side logic if game context is provided (same as FCP - HCT also uses opp field)
    if game_context:
        is_away_offense = game_context.offense_team.team_id == game_context.away_team.team_id
        skeleton_data = apply_opposite_side_logic(skeleton_data, is_away_offense)
    
    return skeleton_data


def get_skeleton_by_lean(play_doc, lean_score):
    """
    Map lean score to the appropriate skeleton variant.
    
    Args:
        play_doc (dict): Play document from MongoDB with skeletons
        lean_score (float): Lean score from generate_logic() function
            >= 0.5: successful - play works perfectly
            0 to 0.49: mid_play_change - play adjusts mid-execution
            -0.01 to -0.5: contested - defense engaged, tougher execution
            < -0.5: broken - defense disrupts, offense forced to react
    
    Returns:
        tuple: (skeleton dict, variant name string)
    """
    skeletons = play_doc.get("skeletons", {})
    
    # Map lean score to skeleton variant
    if lean_score >= 0.5:
        variant = "successful"
    elif lean_score >= 0:
        variant = "mid_play_change"
    elif lean_score >= -0.5:
        variant = "contested"
    else:
        variant = "broken"
    
    # Get the skeleton, fallback to successful if variant doesn't exist
    skeleton = skeletons.get(variant)
    
    # Handle multi-version variants (v1-v6 for non-successful)
    if skeleton and variant != "successful":
        # Check if this variant has multiple versions
        if "versions" in skeleton and isinstance(skeleton["versions"], list):
            # Filter to only non-empty versions
            versions_list = skeleton["versions"]
            non_empty_versions = [v for v in versions_list if v.get("steps") and len(v.get("steps", [])) > 0]
            
            if non_empty_versions:
                # Randomly select one non-empty version
                selected_version = random.choice(non_empty_versions)
                # Create skeleton dict with the selected version's steps
                skeleton = {
                    "steps": selected_version.get("steps", []),
                    "version": selected_version.get("version", "v1")
                }
                logging.debug(f"Selected {selected_version.get('version')} for {variant} (from {len(non_empty_versions)} available)")
            else:
                # No non-empty versions available, fallback to successful
                logging.debug(f"No non-empty versions for {variant}, falling back to successful")
                skeleton = skeletons.get("successful")
                variant = "successful"
        # Old format (single steps array) - maintain backwards compatibility
        elif not skeleton.get("steps"):
            # Empty skeleton, fallback to successful
            skeleton = skeletons.get("successful")
            variant = "successful"
    
    # If selected variant is empty or None, fallback to successful
    if not skeleton or not skeleton.get("steps"):
        skeleton = skeletons.get("successful")
        variant = "successful"  # Update variant to match fallback
    
    return skeleton, variant


def get_hco_skeleton(result_type, game_context, lean_score=None):
    """
    Get HCO skeleton based on the current playcall from team-specific play objects.
    
    Args:
        result_type: Legacy parameter (kept for backward compatibility)
        game_context: Game context object
        lean_score (float, optional): Lean score to select skeleton variant
            If provided, selects from: successful, mid_play_change, contested, broken
            If None, defaults to successful
    
    Returns:
        dict: Selected skeleton with steps
    """
    from BackEnd.db import plays_collection, games_collection, tournaments_collection, franchises_collection
    
    # Get the current playcall from game context
    playcall = game_context.game_state.get("current_playcall", "Inside") if game_context else "Inside"
    
    # Get the offensive team
    offense_team = game_context.offense_team
    offense_team_id = offense_team.team_id
    
    # Try to get skeleton from team-specific play objects first
    skeleton = _get_skeleton_from_team_plays(playcall, offense_team_id, game_context, lean_score=lean_score)
    if skeleton:
        return skeleton
    
    # Fallback to universal plays collection
    play_doc = plays_collection.find_one({"name": playcall})
    
    if play_doc and "skeletons" in play_doc:
        # Check if this is a Motion play
        play_type = play_doc.get("play_type", "set_play")
        
        if play_type == "motion":
            # Motion plays: use base_loop skeleton (no variant selection)
            skeletons = play_doc.get("skeletons", {})
            if "base_loop" in skeletons:
                skeleton = skeletons["base_loop"]
                if skeleton and skeleton.get("steps"):
                    return skeleton
        
        # Set Play: Use lean score to select skeleton variant if provided
        if lean_score is not None:
            skeleton, variant = get_skeleton_by_lean(play_doc, lean_score)
            if skeleton:
                # Add variant name to skeleton metadata for shot modifier
                skeleton["_variant"] = variant
                return skeleton
        
        # Default to successful skeleton (Set Play only)
        skeletons = play_doc.get("skeletons", {})
        if "successful" in skeletons:
            skeleton = skeletons["successful"]
            return skeleton
    
    # Final fallback to old skeleton system
    from BackEnd.playcall_skeletons.inside_skeletons import INSIDE_SCENES
    from BackEnd.playcall_skeletons.outside_skeletons import OUTSIDE_SCENES
    from BackEnd.playcall_skeletons.attack_skeletons import ATTACK_SCENES
    from BackEnd.playcall_skeletons.set_play_skeletons import SET_PLAY_SCENES
    from BackEnd.playcall_skeletons.freelance_skeletons import FREELANCE_SCENES
    from BackEnd.playcall_skeletons.base_skeletons import BASE_SCENES
    
    # Map playcall to skeleton scenes (old system)
    playcall_map = {
        "Inside": INSIDE_SCENES,
        "Outside": OUTSIDE_SCENES,
        "Attack": ATTACK_SCENES,
        "Set": SET_PLAY_SCENES,
        "Freelance": FREELANCE_SCENES,
        "Base": BASE_SCENES
    }
    
    scenes = playcall_map.get(playcall, INSIDE_SCENES)
    
    # Randomly select one scene from the available scenes
    if scenes and len(scenes) > 0:
        selected_scene = random.choice(scenes)
        # Debug logging removed - was cluttering logs
        # logging.debug(f"📋 Using fallback skeleton with {len(selected_scene.get('steps', []))} steps")
        return selected_scene


def _get_skeleton_from_team_plays(playcall, team_id, game_context, lean_score=None):
    """
    Get skeleton using reference-based architecture.
    Looks up play_id from team plays, then fetches skeleton from universal plays collection.
    Uses in-memory cache to avoid repeated DB queries.
    
    Args:
        playcall (str): Name of the play to find
        team_id (str): Team ID
        game_context: Game context object
        lean_score (float, optional): Lean score to select skeleton variant
    
    Returns:
        dict: Selected skeleton, or None if not found
    """
    from BackEnd.db import games_collection, tournaments_collection, franchises_collection, plays_collection
    from bson import ObjectId
    
    # Initialize skeleton cache on game_context if it doesn't exist
    if not hasattr(game_context, '_skeleton_cache'):
        game_context._skeleton_cache = {}
    
    play_id = None
    
    # STEP 1: Get play_id from team plays (in-memory or database)
    offense_team = game_context.offense_team
    if hasattr(offense_team, 'plays') and offense_team.plays:
        if playcall in offense_team.plays:
            play_obj = offense_team.plays[playcall]
            play_id = play_obj.get("play_id")
    
    # If not found in memory, check database
    if not play_id:
        game_id = getattr(game_context, 'game_id', None)
        if game_id:
            game_doc = games_collection.find_one({"_id": game_id})
            if game_doc and "teams" in game_doc:
                team_obj = game_doc["teams"].get(team_id, {})
                plays = team_obj.get("plays", {})
                if playcall in plays:
                    play_obj = plays[playcall]
                    play_id = play_obj.get("play_id")
    
    if not play_id:
        # print(f"🔍 NOT FOUND: No play_id for '{playcall}'")
        return None
    
    # STEP 2: Check cache first (avoid repeated DB queries)
    cache_key = f"{play_id}"
    if cache_key in game_context._skeleton_cache:
        play_doc = game_context._skeleton_cache[cache_key]
        # print(f"🔍 CACHE HIT: '{playcall}' (play_id: {play_id})")
    else:
        # STEP 3: Fetch full play document from universal collection
        try:
            play_doc = plays_collection.find_one({"_id": ObjectId(play_id)})
            if not play_doc:
                # print(f"🔍 NOT FOUND: No play document for play_id '{play_id}'")
                return None
            
            # Cache it for future use
            game_context._skeleton_cache[cache_key] = play_doc
            # print(f"🔍 FETCHED from universal: '{playcall}' (play_id: {play_id})")
        except Exception as e:
            print(f"🚨 Error fetching play from universal collection: {e}")
            return None
    
    # STEP 4: Select skeleton variant based on play type
    if "skeletons" not in play_doc:
        return None
    
    # Check if this is a Motion play
    play_type = play_doc.get("play_type", "set_play")
    
    if play_type == "motion":
        # Motion plays: use base_loop skeleton (no variant selection, ignore lean_score)
        skeletons = play_doc.get("skeletons", {})
        if "base_loop" in skeletons:
            skeleton = skeletons["base_loop"]
            if skeleton and skeleton.get("steps"):
                return skeleton
        return None
    
    # Set Play: Select skeleton variant based on lean score
    if lean_score is not None:
        skeleton, variant = get_skeleton_by_lean(play_doc, lean_score)
        if skeleton and skeleton.get("steps"):
            skeleton["_variant"] = variant
            return skeleton
    
    # Default to successful variant (Set Play only)
    skeletons = play_doc.get("skeletons", {})
    if "successful" in skeletons:
        skeleton = skeletons["successful"]
        if skeleton and skeleton.get("steps"):
            return skeleton
    
    return None


def apply_opposite_side_logic(skeleton_data, is_away_offense):
    """
    Apply opposite side logic to skeleton data based on 'opp' field.
    
    For FCP scenarios:
    - Offensive players with 'opp': True should be positioned on the opposite side 
      of the court (defensive side) - these are ball handlers trying to break the press
    - Offensive players without 'opp' field stay on the same side as normal offense
      (offensive side) - these are outlet options
    
    All players in skeleton are offensive players. Defensive players are positioned 
    separately based on how they guard the offensive players.
    """
    if not skeleton_data or "steps" not in skeleton_data:
        return skeleton_data
    
    # Opp field handling (debug logs removed for cleaner output)
    
    from BackEnd.utils.shared import get_away_player_coords
    from BackEnd.constants import HCO_STRING_SPOTS
    
    steps = skeleton_data.get("steps", [])
    if not steps or len(steps) == 0:
        return skeleton_data
    
    modified_skeleton = {"steps": []}
    total_steps = len(steps)
    
    for step_idx, step in enumerate(steps):
        modified_step = {
            "timestamp": step["timestamp"],
            "pos_actions": {},
            "events": step.get("events", [])
        }
        
        # ✅ FIX: Determine ball handler position (usually PG, or first position with ball)
        # For FCP/HCT, ball handler should be on opposite side
        ball_handler_pos = None
        for pos, action in step.get("pos_actions", {}).items():
            if action.get("has_ball") or pos == "PG":  # PG is usually ball handler
                ball_handler_pos = pos
                break
        if not ball_handler_pos:
            ball_handler_pos = "PG"  # Default to PG if no ball handler found
        
        # ✅ DEBUG: Check if this is final step
        step_is_final = step_idx == total_steps - 1
        
        pos_actions = step.get("pos_actions", {})
        if not pos_actions:
            # Skip steps with no pos_actions
            modified_skeleton["steps"].append(modified_step)
            continue
        
        for position, action_data in pos_actions.items():
            if not isinstance(action_data, dict):
                # Skip invalid action_data
                continue
                
            modified_action = action_data.copy()
            
            # Get the spot coordinates (MongoDB skeletons use "location", old skeletons use "spot")
            location_key = action_data.get("location") or action_data.get("spot", "key")
            spot_coords = HCO_STRING_SPOTS.get(location_key, {"x": 64, "y": 25})
            
            # ✅ FIX: Always default to opp=False unless explicitly set to True
            # If opp key doesn't exist → assume False
            # If opp key exists → use its explicit value (True or False)
            has_opp = action_data.get("opp", False)  # Defaults to False if key doesn't exist
            
            # Check if this offensive player should be on opposite side
            if has_opp:
                # Offensive player with opp=True should be on opposite side (defensive side)
                if is_away_offense:
                    # Away team offense - ball handlers go to home side (defensive side)
                    # No coordinate flip needed - they stay on home side
                    pass
                else:
                    # Home team offense - ball handlers go to away side (defensive side)
                    # Flip coordinates to away side
                    spot_coords = get_away_player_coords(spot_coords)
            else:
                # Offensive player without opp field stays on same side as normal offense
                if is_away_offense:
                    # Away team offense - outlet players go to away side (offensive side)
                    # Flip coordinates to away side
                    spot_coords = get_away_player_coords(spot_coords)
                else:
                    # Home team offense - outlet players stay on home side (offensive side)
                    # No coordinate flip needed
                    pass
            
            # Update the spot coordinates in the action data
            modified_action["coords"] = spot_coords
            modified_step["pos_actions"][position] = modified_action
        
        modified_skeleton["steps"].append(modified_step)
    
    return modified_skeleton


def resolve_half_court_trap_logic(game: "GameManager"):
    """
    Resolve half court trap defensive pressure.
    Returns turn data with HCT result and potential progression to HCO.
    """
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    
    # Track HCT attempt (defensive team)
    def_scouting = def_team.scouting_data
    def_scouting["defense"]["HCT"]["used"] += 1

    # Initialize variables to prevent UnboundLocalError
    shot_result = {}
    animator = None
    skeleton = {}
    animations = []

    text = "TRAP!"
    offenseScore = 0
    defenseScore = 0

    for pos, player in off_lineup.items():
        if pos == "PG":
            offenseScore += 3 * (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
        elif pos in ["SG", "SF"]:
            offenseScore += (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
    for pos, player in def_lineup.items():
        if pos == "PG":
            defenseScore += 3 * (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
        elif pos in ["SG", "SF"]:
            defenseScore += (player.attributes["BH"] * player.attributes["AG"] * 0.2 + player.attributes["IQ"] * 0.2 + player.attributes["CH"] * 0.1)
    
    offenseScore *= random.randint(1, 6)
    defenseScore *= random.randint(1, 6)
    # print("Inside resolve_half_court_trap_logic")
    # print(f"offenseScore: {offenseScore}")
    # print(f"defenseScore: {defenseScore}")

    # Real HCT result calculation
    if (offenseScore + 300) > defenseScore:
        if offenseScore - defenseScore > 1000:
            result_type = random.choices(["D_FOUL", "HCO", "SHOT"], weights=[0.3, 0.5, 0.2])[0]
        else:
            result_type = "HCO"
    else:
        result_type = random.choices(["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"], weights=[0.2, 0.5, 0.3])[0]
    
    # ✅ REMOVED: Test code that forced all HCT turns to be steals
    
    result_text_dict = {
        "HCO": "they break the trap & establish their half court offense",
        "D_FOUL": "defensive foul!",
        "O_FOUL": "offensive foul!",
        "DEAD_BALL_TURNOVER": f"they force a turnover!",
        "STEAL": "steal!",
        "SHOT": "they break the trap & attempt a shot!"
    }
    
    text += " " + result_text_dict.get(result_type, result_type)

    # Handle SHOT result - execute actual shot resolution (same as FCP)
    if result_type == "SHOT":
        # Build roles for shot
        passer = off_lineup.get("PG", list(off_lineup.values())[0])
        shooter = random.choice([off_lineup.get("PF"), off_lineup.get("C")])
        defender = def_lineup.get("PG", list(def_lineup.values())[0])
        
        shot_roles = {
            "ball_handler": passer,
            "shooter": shooter,
            "passer": passer,
            "screener": None,
            "defender": defender,
        }
        
        # Use shot manager to resolve the shot
        shot_result = game.shot_manager.resolve_shot(shot_roles)
        
        # HCT/FCP is over once shot is taken - reset to HCO
        # (Unless it's a made shot, in which case pressure might apply on the inbound)
        if shot_result.get("result_type") == "MISS":
            game_state["offensive_state"] = "HCO"
            # Track MISS as defensive success for team
            def_scouting["defense"]["HCT"]["success"] += 1
        
        # Track HCT player stats for SHOT results
        hct_roles = {
            "ball_handler": passer,
            "shooter": shooter,
            "defender": defender,
        }
        _record_hct_stats(hct_roles, shot_result, game, off_lineup, def_lineup)
        
        # Add HCT-specific data
        shot_result["hct_shot"] = True
        shot_result["text"] = "TRAP! " + shot_result.get("text", "")
        
        # Generate animations from skeleton
        from BackEnd.models.animator import Animator
        animator = Animator(game)
        # ✅ FCP/HCT SHOT: Use HCT shot skeleton with version selection (filters non-empty versions)
        logging.warning(f"🔍 [HCT SHOT] Getting skeleton for SHOT variant")
        skeleton = get_hct_skeleton("SHOT", game) or {}
        logging.warning(f"🔍 [HCT SHOT] Retrieved skeleton: has_steps={bool(skeleton.get('steps'))}, step_count={len(skeleton.get('steps', []))}")
        
        if skeleton and "steps" in skeleton:
            logging.warning(f"🔍 [HCT SHOT] Converting skeleton to animations...")
            animations = animator.skeleton_to_animations(
                skeleton, 
                off_lineup, 
                def_lineup, 
                add_defenders=True,
                is_fcp=False,
                is_hct=True
            )
            logging.warning(f"🔍 [HCT SHOT] Generated {len(animations)} animations")
            if animations:
                shot_result["animations"] = animations
                logging.warning(f"✅ [HCT SHOT] Added animations to shot_result")
            else:
                logging.warning(f"⚠️ [HCT SHOT] No animations generated from skeleton!")
        else:
            logging.warning(f"⚠️ [HCT SHOT] Skeleton has no steps!")
            animations = []
        
        shot_result["skeleton"] = skeleton
        shot_result["roles"] = shot_roles
        
        return shot_result
    
    # ✅ HCT NON-SHOT: Get HCT "base" variant skeleton and apply stopper system
    # For non-shot results (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO), use HCT "base" variant
    # Apply stopper system if result is not HCO (truncate and add stopper step)
    logging.warning(f"🔍 [HCT NON-SHOT] Getting HCT base skeleton for result_type={result_type}")
    skeleton = get_hct_skeleton(result_type, game)  # Get HCT "base" variant (has step 0 with trap break positions)
    
    # Deep copy skeleton to avoid mutating cached skeleton
    if skeleton:
        skeleton = copy.deepcopy(skeleton)
    
    # Apply stopper system (truncates if needed, or returns full skeleton if result == "HCO")
    skeleton = apply_stopper_system_to_skeleton(skeleton, result_type, game_state)
    logging.warning(f"🔍 [HCT NON-SHOT] Retrieved skeleton: has_steps={bool(skeleton.get('steps'))}, step_count={len(skeleton.get('steps', []))}")
    
    # ✅ Determine ball handler from skeleton (who actually has the ball)
    ball_handler = get_ball_handler_from_skeleton(skeleton, off_lineup)
    ball_handler_pos = getattr(ball_handler, 'position', None) or "PG"
    
    # ✅ Determine defender based on ball handler position (position matching for now)
    defender = def_lineup.get(ball_handler_pos, def_lineup.get("PG", list(def_lineup.values())[0]))
    
    # Build roles dict for animation generation
    roles = {
        "ball_handler": ball_handler,
        "defender": defender,
        "shooter": ball_handler,
        "passer": None,
        "screener": None,
    }
    
    # Initialize animator if not already initialized
    from BackEnd.models.animator import Animator
    if animator is None:
        animator = Animator(game)
    
    # Handle foul results - use standard foul types for frontend (same as FCP)
    if result_type == "D_FOUL":
        game_state["foul_team"] = "DEFENSE"
        # ✅ Use dynamically determined ball handler and defender
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("DEFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        def_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out
        check_and_handle_foul_out(foul_player, game_state, def_team)
        result_type = "FOUL"
        # ✅ FIX: Check bonus status for defensive fouls in HCT (per game_flows.md)
        # Defensive fouls should route to FREE_THROW if in bonus, otherwise HCO
        if def_team.team_fouls >= 10:
            # Double bonus (10+ fouls): 2 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2
            game_state["free_throws_remaining"] = 2
            game_state["one_and_one"] = False
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        elif def_team.team_fouls >= 5:
            # Bonus (5-9 fouls): 1 & 1 free throws
            game_state["offensive_state"] = "FREE_THROW"
            game_state["free_throws"] = 2  # Maximum possible (if front end is made)
            game_state["free_throws_remaining"] = 1  # Start with 1 (front end)
            game_state["one_and_one"] = True
            game_state["last_ball_handler"] = ball_handler
            game_state["shooter"] = ball_handler
        else:
            # Less than 5 fouls: possession change, side inbound
            game_state["offensive_state"] = "HCO"
            game_state["free_throws"] = 0
            game_state["free_throws_remaining"] = 0
    elif result_type == "O_FOUL":
        game_state["foul_team"] = "OFFENSE"
        # ✅ Use dynamically determined ball handler
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("OFFENSE", ball_handler, off_lineup, def_lineup)
        foul_player.record_stat("F")
        off_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # Check for foul out
        check_and_handle_foul_out(foul_player, game_state, off_team)
        result_type = "FOUL"
        # Track HCT success: offensive foul = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
    elif result_type == "DEAD_BALL_TURNOVER":
        result_type = "DEAD BALL"
        # ✅ Use dynamically determined ball handler
        # Record TO stat for the ball handler
        ball_handler.record_stat("TO")
        # Track HCT success: turnover = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
    elif result_type == "STEAL":
        # ✅ Use dynamically determined ball handler and defender
        # Record TO stat for the ball handler (victim of steal)
        ball_handler.record_stat("TO")
        # Record STL stat for the defender (guarding ball handler)
        if defender:
            defender.record_stat("STL")
        # Track HCT success: steal = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
        
        # ✅ FIX: Set last_stealer for HCT steals (so Steal HCO Setup runs in next turn)
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""
    
    if skeleton and "steps" in skeleton:
        logging.warning(f"🔍 [HCT] Converting skeleton to animations (result_type={result_type})...")
        animations = animator.skeleton_to_animations(
            skeleton, 
            off_lineup, 
            def_lineup, 
            add_defenders=True,
            is_fcp=False,
            is_hct=True
        )
        logging.warning(f"🔍 [HCT] Generated {len(animations)} animations")
        
        # ✅ FIX: Extract stealer position from generated animations (SS&S approach)
        # This uses the actual calculated defensive position from the animation system
        # For stopper results (steal, foul, turnover), the stopper step is always the final step,
        # so we can simply use animation["end"] to get the final coordinates
        if result_type == "STEAL" and animations and defender:
            stealer_id = getattr(defender, "player_id", None)
            
            if stealer_id:
                # Find the defensive animation for the stealer
                stealer_animation = None
                for anim in animations:
                    if anim.get("playerId") == stealer_id:
                        stealer_animation = anim
                        break
                
                if stealer_animation and "end" in stealer_animation:
                    # Use the final coordinates from the animation (stopper step is always final)
                    stealer_coords = stealer_animation["end"]
                    game_state["last_stealer_coords"] = stealer_coords.copy()
                    defender.coords = stealer_coords.copy()
                    logging.warning(f"🏀 [STEAL POSITION] HCT: Extracted final coords from animation end: x={stealer_coords['x']}, y={stealer_coords['y']}")
                else:
                    logging.warning(f"⚠️ [STEAL POSITION] HCT: Could not find stealer animation or 'end' field (stealer_id={stealer_id}, has_animation={stealer_animation is not None}, has_end={stealer_animation and 'end' in stealer_animation if stealer_animation else False})")
            else:
                logging.warning(f"⚠️ [STEAL POSITION] HCT: Missing stealer_id")
        
        if animations:
            shot_result["animations"] = animations
            logging.warning(f"✅ [HCT] Added {len(animations)} animations to shot_result")
        else:
            logging.warning(f"⚠️ [HCT] No animations generated from skeleton!")
    else:
        logging.warning(f"⚠️ [HCT] Skeleton has no steps! skeleton={bool(skeleton)}, has_steps={skeleton.get('steps') if skeleton else False}")
        animations = []
    
    # Determine possession flip (same logic as FCP)
    possession_flips = False
    if result_type == "FOUL" and game_state.get("foul_team") == "OFFENSE":
        possession_flips = True
    elif result_type in ["DEAD BALL", "STEAL"]:
        possession_flips = True
    
    # Handle STEAL: Check for fast break opportunity (STEAL only, not DEAD BALL)
    next_play_type = None
    if result_type == "STEAL":
        if random.random() < get_fast_break_chance(game):
            next_play_type = "FAST_BREAK"
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            next_play_type = "HCO"
            game_state["offensive_state"] = "HCO"
    elif result_type == "HCO":
        # ✅ SS&S: Match Fast Break pattern - set offensive_state when transitioning to HCO
        # This prevents duplicate HCT turns (offensive_state must change from "HCT" to "HCO")
        next_play_type = "HCO"
        game_state["offensive_state"] = "HCO"
    # For DEAD BALL, O_FOUL, D_FOUL: next_play_type stays None (will use side inbound → HCO)
    
    # Calculate time elapsed for HCT phase
    hct_time_elapsed = random.randint(5, 9)
    
    # If transitioning to HCO, store the HCT time for HCO to add to its time
    if result_type == "HCO":
        game_state["pressure_phase_time"] = hct_time_elapsed
    
    # Track HCT player stats for non-SHOT results
    hct_roles = {
        "ball_handler": ball_handler,
        "shooter": ball_handler,  # For non-shot results, ball handler is the "shooter"
        "defender": defender,
    }
    turn_result = {"result_type": result_type}
    _record_hct_stats(hct_roles, turn_result, game, off_lineup, def_lineup)
    
    # ✅ SS&S: Set offense_team_id (team on offense DURING this turn)
    # Backend calls switch_possession() after turn if needed, so next turn has correct offense_team
    result = {
        "result_type": result_type,
        "text": text,
        "current_turn": "HCT",  # ✅ SS&S: Explicit turn type
        "next_play_type": next_play_type,
        "next_turn": next_play_type,  # ✅ SS&S: Explicit next turn (HCO, FAST_BREAK, or None)
        "ball_handler": roles["ball_handler"],
        "defender": roles["defender"],
        "shooter": roles["shooter"],
        "passer": "",
        "screener": "",
        "offense_team_id": off_team.team_id,  # ✅ SS&S: Team on offense DURING this turn
        "possession_flips": possession_flips,  # ✅ Backend internal flag (tells backend when to call switch_possession)
        "time_elapsed": hct_time_elapsed,  # Time spent in HCT phase
        "events": [],
        "skeleton": skeleton,
        "animations": animations,
        "roles": roles,
        "foul_team": game_state.get("foul_team"),  # Include foul_team for frontend announcement
        "foul_player_id": getattr(roles.get("foul_player"), "player_id", None) if roles.get("foul_player") else None,  # For foul announcements
        "victim_id": getattr(roles["ball_handler"], "player_id", None),  # For turnover announcements
        "defender_id": getattr(roles["defender"], "player_id", None) if roles["defender"] else None  # For steal announcements
    }
    
    logging.warning(f"✅ [HCT] Returning result with {len(animations)} animations, result_type={result_type}")
    return result
