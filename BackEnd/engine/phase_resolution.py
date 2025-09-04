import random
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
    record_team_points,
    unpack_game_context
)


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

    # foul_type = random.choice(["SHOOTING", "NON_SHOOTING"]) if foul_team == "DEFENSE" else "NON_SHOOTING" # Future logic: determine if this was shooting or not
    # foul_type = "NON_SHOOTING"

    # if foul_type == "SHOOTING":
    #     game_state["offensive_state"] = "FREE_THROW"
    #     game_state["free_throws"] = 2  # Future: support 3 FT on 3PT attempt
    #     game_state["free_throws_remaining"] = 2
    #     game_state["last_ball_handler"] = ball_handler
    #     ball_handler = shooter
    
    if def_team.team_fouls >= 10:
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 2
        game_state["free_throws_remaining"] = 2
        game_state["one_and_one"] = False
        game_state["last_ball_handler"] = ball_handler
        game_state["shooter"] = ball_handler
    elif def_team.team_fouls >= 5:
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 2
        game_state["free_throws_remaining"] = 2
        game_state["one_and_one"] = True
        game_state["last_ball_handler"] = ball_handler
        game_state["shooter"] = ball_handler
    else:
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
        "time_elapsed": time_elapsed
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

    # Determine event type
    o_count = len(fb_roles["offense"]) + 1  # include ball handler
    d_count = len(fb_roles["defense"])

    if d_count == 0:
        event_type = "SHOT"
    elif o_count > d_count:
        event_type = random.choices(["SHOT", "HCO"], weights=[0.9, 0.1])[0]
    elif o_count == d_count:
        event_type = random.choices(["SHOT", "HCO"], weights=[0.75, 0.25])[0]
    else:
        event_type = random.choices(["SHOT", "HCO"], weights=[0.4, 0.6])[0]

    # If HCO triggered, skip fast break
    if event_type == "HCO":
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1
        game.game_state["offensive_state"] = "HCO"

        from BackEnd.models.turn_manager import TurnManager
        return TurnManager(game).run_micro_turn()

    #get shooter and passer (if applicable)
    # Assign shooter and passer for shot, turnover, or foul scenarios
    offense_in_play = [fb_roles["ball_handler"]] + fb_roles["offense"]
    shooter = random.choice(offense_in_play)

    fb_roles["shooter"] = shooter
    # If shooter is not the ball handler, then ball handler is the passer
    fb_roles["passer"] = fb_roles["ball_handler"] if shooter != fb_roles["ball_handler"] else None
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
        fb_roles, hold_up, stopper_id, fb_roles.get("defense", [])
    )
    turn_result["roles"] = fb_roles
    if hold_up:
        turn_result["hold_up"] = True
        turn_result["stopper_id"] = stopper_id

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
    ft_shot_score = ((attrs["FT"] * 0.8) + (attrs["CH"] * 0.2)) * random.randint(1, 6)
    # print(f"ft_shot_score: {ft_shot_score}")
    # print(f"off_team.team_attributes['ft_shot_threshold']: {off_team.team_attributes['ft_shot_threshold']}")
    makes_shot = ft_shot_score >= off_team.team_attributes["ft_shot_threshold"]

    shooter.record_stat("FTA")
    text = f"{get_name_safe(shooter)} steps to the line... "
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
        shooter.record_stat("FTM")
        record_team_points(game, off_team, 1)
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
                if random.random() < get_fast_break_chance(game):
                    game_state["offensive_state"] = "FAST_BREAK"
            else:
                # Offensive rebound handling
                off_event = resolve_offensive_rebound(game, rebounder)
                if off_event["event_type"] == "PUTBACK_ATTEMPT":
                    text += f" {get_name_safe(rebounder)} goes back up."
                    result = {
                        "result_type": "MAKE" if off_event["result"] == "MAKE" else "MISS",
                        "ball_handler": rebounder,
                        "shooter": rebounder,
                        "text": text,
                        "time_elapsed": off_event["timeElapsed"],
                        "possession_flips": off_event.get("possession_flips", False),
                    }
                    if off_event["result"] == "MAKE":
                        result["points"] = off_event.get("points", 2)
                        result["scoring_team"] = off_team.name
                    return result
                else:
                    text += f" {get_name_safe(rebounder)} kicks it out to reset."
                    return {
                        "result_type": "MISS",
                        "ball_handler": rebounder,
                        "shooter": shooter,
                        "text": text,
                        "time_elapsed": off_event["timeElapsed"],
                        "possession_flips": False,
                    }
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
    }

    if makes_shot:
        result["points"] = 1
        result["scoring_team"] = off_team.name

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

def resolve_half_court_offense_logic(game):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    # 1. Tactical Setup
    off_call = game_state["current_playcall"]
    def_call = game_state["defense_playcall"]
    roles = game.turn_manager.assign_roles(off_call, def_call)
    # print("inside resolve_half_court_offense_logic")
    # print("[DEBUG] roles:", roles.keys())
    # print("[DEBUG] event_step:", roles.get("event_step"))
    # print("[DEBUG] steps:", roles.get("steps"))
    # print("[DEBUG] shooter:", roles.get("shooter"))

    # 2. Event Determination
    event_type = game.turn_manager.determine_event_type(roles)

    print(f"event_type: {event_type}")
    # event_type = "SHOT"

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
    animator = Animator(game)
    shot_result["animations"] = animator.capture_halfcourt_animation(roles)


    # 4. scouting report update
    if shot_result["result_type"] == "MAKE":
        off_team.scouting_data["offense"]["Playcalls"][off_call]["success"] += 1
    elif shot_result["result_type"] in ["MISS", "TURNOVER"]:
        def_team.scouting_data["defense"][def_call]["success"] += 1

    return shot_result


# def resolve_half_court_offense_logic(game: "GameManager") -> dict:

#     game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
#     off_call = game_state["current_playcall"]
#     def_call = game_state["defense_playcall"]

#     # Track usage
#     off_scouting = off_team.scouting_data
#     def_scouting = def_team.scouting_data
#     off_scouting["offense"]["Playcalls"][off_call]["used"] += 1
#     def_scouting["defense"][def_call]["used"] += 1

#     roles = game.turn_manager.assign_roles()
    
#     # 🧠 Determine event type (SHOT / TURNOVER / O_FOUL / D_FOUL)
#     from BackEnd.models.turn_manager import TurnManager
#     event_type = game.turn_manager.determine_event_type(roles)
#     if event_type == "TURNOVER":
#         return resolve_turnover_logic(roles, game, turnover_type="DEAD BALL")

#     elif event_type == "O_FOUL":
#         game_state["foul_team"] = "OFFENSE"
#         return resolve_non_shooting_foul(roles, game)

#     elif event_type == "D_FOUL":
#         game_state["foul_team"] = "DEFENSE"
#         return resolve_non_shooting_foul(roles, game)
    
#     shot_result = game.shot_manager.resolve_shot(roles)
#     # shot_result = {
#     #         "result_type": "MAKE" if made else "MISS",
#     #         "ball_handler": shooter,
#     #         "shooter": shooter,
#     #         "shot_score": shot_score,
#     #         "screener": screener,
#     #         "passer": passer,
#     #         "defender": defender,
#     #         "text": text,
#     #         "possession_flips": possession_flips,
#     #         "time_elapsed": time_elapsed
#     #     }

#     # Track success
#     if shot_result["result_type"] == "MAKE":
#         off_scouting["offense"]["Playcalls"][off_call]["success"] += 1
#     elif shot_result["result_type"] in ["MISS", "TURNOVER"]:
#         def_scouting["defense"][def_call]["success"] += 1


#     return shot_result


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
