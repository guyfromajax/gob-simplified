import random
import logging
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
    
    return {
        "result_type": "FOUL",
        "ball_handler": ball_handler,
        "screener": screener,
        "passer": passer,
        "defender": defender,
        "text": text,
        "possession_flips": False,
        "time_elapsed": time_elapsed,
        "foul_player_id": getattr(foul_player, "player_id", None) if foul_player else None,
        "foul_team": game_state.get("foul_team")
    }

# #FAST BREAK
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

        bh_pos = random.choices(["PG", "SG", "SF"], weights=[75, 15, 10])[0]
        ball_handler = off_lineup[bh_pos]

        fb_roles["ball_handler"] = ball_handler

        # Ensure outlet passer and receiver are set to IDs and only if different
        if rebounder and rebounder != ball_handler:
            fb_roles["outlet_passer"] = getattr(rebounder, "player_id", None)
            fb_roles["outlet_receiver"] = getattr(ball_handler, "player_id", None)
        else:
            fb_roles["outlet_passer"] = None
            fb_roles["outlet_receiver"] = None

        # No additional offensive players when starting from a rebound
        fb_roles["offense"] = []


    else:  # STEAL
        ball_handler = game_state.get("last_stealer")
        if ball_handler is None:
            ball_handler = off_lineup["PG"]
        fb_roles["ball_handler"] = ball_handler
        fb_roles["outlet_passer"] = None
        fb_roles["outlet_receiver"] = None

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

    # Determine event type based on defender count
    # Note: o_count is always 1 (ball handler only) for rebounds
    o_count = len(fb_roles["offense"]) + 1  # include ball handler
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

    if d_count == 0:
        # 0 defenders: Always shot (99% make chance)
        event_type = "SHOT"
    elif d_count == 1:
        # 1 defender: 75% shot, 25% defensive stop
        event_type = random.choices(["SHOT", "DEFENSIVE_STOP"], weights=[0.75, 0.25])[0]
    else:  # d_count >= 2
        # 2+ defenders: 10% shot, 90% defensive stop
        event_type = random.choices(["SHOT", "DEFENSIVE_STOP"], weights=[0.10, 0.90])[0]

    # If defensive stop triggered, defense stopped the fast break
    if event_type == "DEFENSIVE_STOP":
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
        game.game_state["offensive_state"] = "HCO"
        
        # Return a defensive stop result instead of recursively calling run_micro_turn
        ball_handler = fb_roles["ball_handler"]
        defender_name = get_name_safe(best_defender) if best_defender else "Defense"
        return {
            "result_type": "DEFENSIVE_STOP",
            "ball_handler": ball_handler,
            "defender": best_defender,
            "text": f"Fast Break! Nice stop by {defender_name}!",
            "possession_flips": False,
            "time_elapsed": 3,
            "animations": [],
            "next_play_type": "HCO",
        }

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
    ft_shot_score = ((attrs["FT"] * 0.8) + (attrs["IQ"] * 0.2)) * random.randint(1, 6) #temp changed CH to IQ
    text = f"ft_shot_score: {ft_shot_score}, threshold: {off_team.team_attributes['ft_shot_threshold']}  "
    makes_shot = ft_shot_score >= off_team.team_attributes["ft_shot_threshold"]

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
            rebounder.record_stat(stat)

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
    turnover_type = random.choice(["STEAL", "DEAD BALL"])
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
        if random.random() < get_fast_break_chance(game):
            game_state["offensive_state"] = "FAST_BREAK"
            text += " and takes it the other way!"
        else:
            game_state["offensive_state"] = "HCO"
            text += " and waits to set up the half-court offense."
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""

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

    result = {
        "result_type": turnover_type,
        "ball_handler": ball_handler,
        "text": text,
        "time_elapsed": random.randint(3, 8),
        "possession_flips": True,  # Let the turn loop handle the flip
        "victim_id": victim_id,
        "victim_name": victim_name,
    }

    if stealer_id:
        result["stealer_id"] = stealer_id
        result["stealer_name"] = stealer_name
    if events:
        result["events"] = events

    return result


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
        float: Lean score from -2 to 2
            >= 1: successful - play works perfectly
            0 to 0.99: mid_play_change - play adjusts mid-execution
            -0.01 to -1: contested - defense engaged, tougher execution
            < -1: broken - defense disrupts, offense forced to react
    
    TODO: Implement full logic based on:
        - Team attributes (team speed, execution, discipline, etc.)
        - Player attributes (relevant to play type/focus)
        - Defensive matchup effectiveness
        - Game situation (score, time, quarter)
    """
    import random
    from BackEnd.constants import ACTIONS
    
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
                    print(f"[generate_logic] Screen attempts in skeleton:")
                    for pos, count in sorted(screen_attempts_by_pos.items()):
                        player = off_lineup.get(pos)
                        if player:
                            player_name = get_name_safe(player)
                            print(f"  {pos} ({player_name}): {count} screen attempt(s)")
                            
                            # Increment SCR_A for each screen attempt
                            for _ in range(count):
                                player.record_stat("SCR_A")
                                
                                # 50% chance to increment SCR_S for each attempt
                                success = random.randint(1, 2)
                                if success == 1:
                                    player.record_stat("SCR_S")
                                    print(f"    → Screen success! ({player_name} SCR_S incremented)")
                        else:
                            print(f"  {pos} (Unknown): {count} screen attempt(s) - player not found in lineup")
                else:
                    print(f"[generate_logic] No screen attempts found in skeleton")
        except Exception as e:
            print(f"[generate_logic] Error analyzing skeleton for screens: {e}")
    
    # PLACEHOLDER: Return random lean score for now
    # This allows the system to work while full logic is implemented
    lean_score = random.uniform(-2, 2)
    
    print(f"[generate_logic] Lean score: {lean_score:.2f}")
    
    return lean_score


def resolve_half_court_offense_logic(game):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    # 1. Tactical Setup
    off_call = game_state["current_playcall"]
    def_call = game_state["defense_playcall"]
    print("Entering resolve_half_court_offense_logic")
    print(f"off_call: {off_call}")
    print(f"def_call: {def_call}")

    # Generate logic to determine lean score
    lean_score = generate_logic(off_call, def_call, off_team, def_team, off_lineup, def_lineup, game=game)
    
    # Get skeleton from MongoDB BEFORE assigning roles, so assign_roles can use the correct skeleton
    # Pass lean_score to select the appropriate skeleton variant
    skeleton = get_hco_skeleton(None, game, lean_score=lean_score)
    
    # Get the successful variant to determine intended shooter
    successful_skeleton = get_hco_skeleton(None, game, lean_score=1.0)  # Force successful variant
    
    roles = game.turn_manager.assign_roles(off_call, def_call, skeleton=skeleton)
    
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
    
    # print("inside resolve_half_court_offense_logic")
    # print("[DEBUG] roles:", roles.keys())
    # print("[DEBUG] event_step:", roles.get("event_step"))
    # print("[DEBUG] steps:", roles.get("steps"))
    # print("[DEBUG] shooter:", roles.get("shooter"))

    # 2. Event Determination
    event_type = game.turn_manager.determine_event_type(roles)

    # print(f"event_type 0: {event_type}")
    event_type = "SHOT"
    # print(f"event_type 1: {event_type}")

    if event_type != "SHOT":
        #need to add animations to each of these
        if event_type == "TURNOVER":
            return resolve_turnover_logic(roles, game, turnover_type="DEAD BALL")

        elif event_type == "O_FOUL":
            game_state["foul_team"] = "OFFENSE"
            return resolve_non_shooting_foul(roles, game)

        elif event_type == "D_FOUL":
            game_state["foul_team"] = "DEFENSE"
            return resolve_non_shooting_foul(roles, game)

    # 3. Shot Result
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
    
    debug_info = f"[{off_call}] {variant}, lean:{lean_score:.2f}, modifier:{modifier:+d} | "
    shot_result["text"] = debug_info + shot_result.get("text", "")
    
    # Pass next_defensive_setup to animator via roles
    if "next_defensive_setup" in shot_result:
        roles["next_defensive_setup"] = shot_result["next_defensive_setup"]
    
    animator = Animator(game)
    # OLD ANIMATION SYSTEM - REMOVED (conflicts with skeleton-based system)
    # shot_result["animations"] = animator.capture_halfcourt_animation(roles)
    
    # Add skeleton data for unified animation system (reuse skeleton from line 556)
    shot_result["skeleton"] = skeleton or {}
    
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
        focus = game.game_state.get("offense_play_focus")     # 'inside' | 'attack' | 'outside'
        type_label = "Motion" if play_type == "motion" else ("Set" if play_type == "set_play" else None)
        print("Inside try statement")
        print(f"type_label: {type_label}")
        print(f"focus: {focus}")
        print(f"shot_result, i.e. rt = {shot_result.get('result_type')}")    
        if type_label and focus in ["inside", "attack", "outside"]:
            pc = off_team.scouting_data["offense"]["Playcalls"]
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
                # print(f"🎯 SUCCESS DEBUG: After - overall: {pc[type_label]['overall']['success']}, {focus}: {pc[type_label][focus]['success']}, Cumulative: {pc['Cumulative'][focus]['success']}")
            elif offense_failure:
                # We don't increment offense success; defensive success can be tracked separately if needed
                pass
            # Clear foul_team after success tracking to prevent it from affecting subsequent actions (like putbacks)
            # Note: Only clear if this is the original HCO play, not a putback (putbacks have result_type PUTBACK_MAKE/PUTBACK_MISS)
            if rt in ["MAKE", "MISS"]:
                game.game_state["foul_team"] = None
                # print(f"🎯 SUCCESS DEBUG: Cleared foul_team after HCO play (rt={rt})")
        else:
            pass
            # print(f"🎯 SUCCESS DEBUG: Skipping - type_label={type_label}, focus={focus}")
    except Exception as e:
        print(f"🎯 SUCCESS DEBUG ERROR: {type(e).__name__}: {e}")
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
    if defense_call == "Zone":
        d_foul_score *= 1.1
    is_d_foul = d_foul_score < def_team.team_attributes["foul_threshold"] * 1.2

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
    is_o_foul = o_foul_score < off_team.team_attributes["foul_threshold"] * 0.8

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
    if defense_call == "Zone":
        pressure *= 0.9

    turnover_score = bh_score - pressure
    is_turnover = turnover_score < off_team.team_attributes["turnover_threshold"]

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
            result_type = random.choices(["D_FOUL", "HCO", "SHOT"], weights=[0.5, 0.3, 0.2])[0]
        else:
            result_type = "HCO"
    else:
        result_type = random.choices(["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"], weights=[0.5, 0.3, 0.2])[0]
    
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
    
    # Initialize animator and skeleton for all cases
    from BackEnd.models.animator import Animator
    animator = Animator(game)
    skeleton = get_skeleton_for_turn(result_type, "FCP", game) or {}
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
        
        # Add FCP-specific data
        shot_result["fcp_shot"] = True
        shot_result["text"] = "PRESS! " + shot_result.get("text", "")
        
        # Generate animations from skeleton for the pass, then rely on standard shot animation
        skeleton = get_skeleton_for_turn("SHOT", "FCP", game) or {}
        
        if skeleton and "steps" in skeleton:
            animations = animator.skeleton_to_animations(
                skeleton, 
                off_lineup, 
                def_lineup, 
                add_defenders=True,
                is_fcp=True
            )
            if animations:
                shot_result["animations"] = animations
        
        shot_result["skeleton"] = skeleton
        shot_result["roles"] = shot_roles
        
        return shot_result
    
    # Build roles dict for animation generation
    roles = {
        "ball_handler": off_lineup.get("PG", list(off_lineup.values())[0]),
        "defender": def_lineup.get("PG", list(def_lineup.values())[0]),
        "shooter": off_lineup.get("PG", list(off_lineup.values())[0]),
        "passer": None,
        "screener": None,
    }
    
    # Generate animations from skeleton BEFORE changing result_type
    # (skeleton keys use D_FOUL/O_FOUL, not FOUL)
    from BackEnd.models.animator import Animator
    animator = Animator(game)
    skeleton = get_skeleton_for_turn(result_type, "FCP", game) or {}
    
    # Handle foul results - use standard foul types for frontend
    if result_type == "D_FOUL":
        game_state["foul_team"] = "DEFENSE"
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("DEFENSE", roles["ball_handler"], off_lineup, def_lineup)
        foul_player.record_stat("F")
        def_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        # For now, treat as non-shooting foul (FCP happens before shot attempt)
        # This will trigger side inbound or bonus free throws via existing logic
        result_type = "FOUL"
        # text = "PRESS! Defensive foul"
    elif result_type == "O_FOUL":
        game_state["foul_team"] = "OFFENSE"
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("OFFENSE", roles["ball_handler"], off_lineup, def_lineup)
        foul_player.record_stat("F")
        off_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        result_type = "FOUL"
        # text = "PRESS! Offensive foul"
        # Track FCP success: offensive foul = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
    elif result_type == "DEAD_BALL_TURNOVER":
        result_type = "DEAD BALL"
        # text = "PRESS! Turnover"
        # Record TO stat for the ball handler
        roles["ball_handler"].record_stat("TO")
        # Track FCP success: turnover = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
    elif result_type == "STEAL":
        # Record TO stat for the ball handler (victim of steal)
        roles["ball_handler"].record_stat("TO")
        # Record STL stat for the defender
        if roles["defender"]:
            roles["defender"].record_stat("STL")
        # Track FCP success: steal = defensive success
        def_scouting["defense"]["FCP"]["success"] += 1
    
    if skeleton and "steps" in skeleton:
        animations = animator.skeleton_to_animations(
            skeleton, 
            off_lineup, 
            def_lineup, 
            add_defenders=True,
            is_fcp=True
        )
        if animations:
            shot_result["animations"] = animations
    else:
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
        next_play_type = "HCO"
    # For DEAD BALL, O_FOUL, D_FOUL: next_play_type stays None (will use side inbound → HCO)
    
    # Calculate time elapsed for FCP phase
    fcp_time_elapsed = random.randint(5, 9)
    
    # If transitioning to HCO, store the FCP time for HCO to add to its time
    if result_type == "HCO":
        game_state["pressure_phase_time"] = fcp_time_elapsed
    
    result = {
        "result_type": result_type,
        "text": text,
        "next_play_type": next_play_type,
        "ball_handler": roles["ball_handler"],
        "defender": roles["defender"],
        "shooter": roles["shooter"],
        "passer": "",
        "screener": "",
        "possession_flips": possession_flips,
        "time_elapsed": fcp_time_elapsed,  # Time spent in FCP phase
        "events": [],
        "skeleton": skeleton,
        "animations": animations,
        "roles": roles,
        "fcp_foul": True,  # Flag to indicate this FOUL has FCP animations
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
    """Get FCP skeleton filtered by result_type"""
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
    """Get HCT skeleton filtered by result_type"""
    from BackEnd.playcall_skeletons.hct_skeletons import HCT_SCENES, HCT_SKELETONS_DICT
    
    # Get the appropriate end timestamp for this result type
    end_timestamp = HCT_SKELETONS_DICT.get(result_type, 1200)
    
    # Randomly select an HCT scene
    import random
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
            >= 1: successful - play works perfectly
            0 to 0.99: mid_play_change - play adjusts mid-execution
            -0.01 to -1: contested - defense engaged, tougher execution
            < -1: broken - defense disrupts, offense forced to react
    
    Returns:
        tuple: (skeleton dict, variant name string)
    """
    skeletons = play_doc.get("skeletons", {})
    
    # Map lean score to skeleton variant
    if lean_score >= 1:
        variant = "successful"
    elif lean_score >= 0:
        variant = "mid_play_change"
    elif lean_score >= -1:
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
    print("Entering get_hco_skeleton")
    print(f"playcall: {playcall}, lean_score: {lean_score}")
    
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
        # Use lean score to select skeleton variant if provided
        if lean_score is not None:
            skeleton, variant = get_skeleton_by_lean(play_doc, lean_score)
            if skeleton:
                # Add variant name to skeleton metadata for shot modifier
                skeleton["_variant"] = variant
                return skeleton
        
        # Default to successful skeleton
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
        print(f"📋 Using fallback skeleton with {len(selected_scene.get('steps', []))} steps")
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
    
    # STEP 4: Select skeleton variant based on lean score
    if "skeletons" not in play_doc:
        return None
    
    if lean_score is not None:
        skeleton, variant = get_skeleton_by_lean(play_doc, lean_score)
        if skeleton and skeleton.get("steps"):
            skeleton["_variant"] = variant
            return skeleton
    
    # Default to successful variant
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
    
    from BackEnd.utils.shared import get_away_player_coords
    from BackEnd.constants import HCO_STRING_SPOTS
    
    modified_skeleton = {"steps": []}
    
    for step in skeleton_data["steps"]:
        modified_step = {
            "timestamp": step["timestamp"],
            "pos_actions": {},
            "events": step.get("events", [])
        }
        
        for position, action_data in step["pos_actions"].items():
            modified_action = action_data.copy()
            
            # Get the spot coordinates (MongoDB skeletons use "location", old skeletons use "spot")
            location_key = action_data.get("location") or action_data.get("spot", "key")
            spot_coords = HCO_STRING_SPOTS.get(location_key, {"x": 64, "y": 25})
            
            # Check if this offensive player should be on opposite side
            if action_data.get("opp", False):
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
            result_type = random.choices(["D_FOUL", "HCO", "SHOT"], weights=[0.5, 0.3, 0.2])[0]
        else:
            result_type = "HCO"
    else:
        result_type = random.choices(["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"], weights=[0.5, 0.3, 0.2])[0]
    
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
        
        # Add HCT-specific data
        shot_result["hct_shot"] = True
        shot_result["text"] = "TRAP! " + shot_result.get("text", "")
        
        # Generate animations from skeleton
        from BackEnd.models.animator import Animator
        animator = Animator(game)
        skeleton = get_skeleton_for_turn("SHOT", "HCT", game) or {}
        
        if skeleton and "steps" in skeleton:
            animations = animator.skeleton_to_animations(
                skeleton, 
                off_lineup, 
                def_lineup, 
                add_defenders=True,
                is_fcp=False,
                is_hct=True
            )
            if animations:
                shot_result["animations"] = animations
        else:
            animations = []
        
        shot_result["skeleton"] = skeleton
        shot_result["roles"] = shot_roles
        
        return shot_result
    
    # Build roles dict for animation generation
    roles = {
        "ball_handler": off_lineup.get("PG", list(off_lineup.values())[0]),
        "defender": def_lineup.get("PG", list(def_lineup.values())[0]),
        "shooter": off_lineup.get("PG", list(off_lineup.values())[0]),
        "passer": None,
        "screener": None,
    }
    
    # Generate animations from skeleton BEFORE changing result_type
    from BackEnd.models.animator import Animator
    if animator is None:
        animator = Animator(game)
    skeleton = get_skeleton_for_turn(result_type, "HCT", game) or {}
    
    # Handle foul results - use standard foul types for frontend (same as FCP)
    if result_type == "D_FOUL":
        game_state["foul_team"] = "DEFENSE"
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("DEFENSE", roles["ball_handler"], off_lineup, def_lineup)
        foul_player.record_stat("F")
        def_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        result_type = "FOUL"
    elif result_type == "O_FOUL":
        game_state["foul_team"] = "OFFENSE"
        # Select the foul player and increment their fouls
        foul_player = select_foul_player("OFFENSE", roles["ball_handler"], off_lineup, def_lineup)
        foul_player.record_stat("F")
        off_team.team_fouls += 1  # Increment team fouls
        roles["foul_player"] = foul_player
        result_type = "FOUL"
        # Track HCT success: offensive foul = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
    elif result_type == "DEAD_BALL_TURNOVER":
        result_type = "DEAD BALL"
        # Record TO stat for the ball handler
        roles["ball_handler"].record_stat("TO")
        # Track HCT success: turnover = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
    elif result_type == "STEAL":
        # Record TO stat for the ball handler (victim of steal)
        roles["ball_handler"].record_stat("TO")
        # Record STL stat for the defender
        if roles["defender"]:
            roles["defender"].record_stat("STL")
        # Track HCT success: steal = defensive success
        def_scouting["defense"]["HCT"]["success"] += 1
    
    if skeleton and "steps" in skeleton:
        animations = animator.skeleton_to_animations(
            skeleton, 
            off_lineup, 
            def_lineup, 
            add_defenders=True,
            is_fcp=False,
            is_hct=True
        )
        if animations:
            shot_result["animations"] = animations
    else:
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
        next_play_type = "HCO"
    # For DEAD BALL, O_FOUL, D_FOUL: next_play_type stays None (will use side inbound → HCO)
    
    # Calculate time elapsed for HCT phase
    hct_time_elapsed = random.randint(5, 9)
    
    # If transitioning to HCO, store the HCT time for HCO to add to its time
    if result_type == "HCO":
        game_state["pressure_phase_time"] = hct_time_elapsed
    
    result = {
        "result_type": result_type,
        "text": text,
        "next_play_type": next_play_type,
        "ball_handler": roles["ball_handler"],
        "defender": roles["defender"],
        "shooter": roles["shooter"],
        "passer": "",
        "screener": "",
        "possession_flips": possession_flips,
        "time_elapsed": hct_time_elapsed,  # Time spent in HCT phase
        "events": [],
        "skeleton": skeleton,
        "animations": animations,
        "roles": roles,
        "hct_foul": True if result_type == "FOUL" else False,  # Flag for HCT fouls with animations
        "foul_team": game_state.get("foul_team"),  # Include foul_team for frontend announcement
        "foul_player_id": getattr(roles.get("foul_player"), "player_id", None) if roles.get("foul_player") else None,  # For foul announcements
        "victim_id": getattr(roles["ball_handler"], "player_id", None),  # For turnover announcements
        "defender_id": getattr(roles["defender"], "player_id", None) if roles["defender"] else None  # For steal announcements
    }
    
    return result
