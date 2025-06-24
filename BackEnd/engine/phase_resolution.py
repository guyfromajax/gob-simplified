import random
from BackEnd.models.shot_manager import ShotManager
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from BackEnd.models.game_manager import GameManager

from BackEnd.utils.shared import (
    get_name_safe, 
    get_time_elapsed, 
    get_fast_break_chance, 
    calculate_rebound_score, 
    choose_rebounder, 
    default_rebounder_dict, 
    resolve_offensive_rebound_loop
)
    
def resolve_foul(roles, game_state):
    
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    foul_team = off_team if game_state["foul_team"] == "OFFENSE" else def_team
    
    ball_handler = roles["ball_handler"]
    defender = roles.get("defender", "")
    foul_player = roles["foul_player"]
    shooter = roles["shooter"]
    screener = roles.get("screener", "")
    passer = roles.get("passer", "")
    tempo = game_state["strategy_calls"][off_team]["tempo_call"]
    time_elapsed = get_time_elapsed(tempo)

    # Track the foul
    foul_player.record_stat("F")
    if foul_team == "DEFENSE":
        game_state["team_fouls"][def_team] += 1
        text = f"{foul_player} fouls {ball_handler}!"
    else:
        game_state["team_fouls"][off_team] += 1
        text = f"{foul_player} commits an offensive foul!"

    foul_type = random.choice(["SHOOTING", "NON_SHOOTING"]) if foul_team == "DEFENSE" else "NON_SHOOTING" # Future logic: determine if this was shooting or not

    if foul_type == "SHOOTING":
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 2  # Future: support 3 FT on 3PT attempt
        game_state["free_throws_remaining"] = 2
        game_state["last_ball_handler"] = ball_handler
        ball_handler = shooter
    elif game_state["team_fouls"][def_team] >= 10:
        game_state["free_throws"] = 2
        game_state["free_throws_remaining"] = 2
        game_state["bonus_active"] = False
        game_state["last_ball_handler"] = ball_handler
    elif game_state["team_fouls"][def_team] >= 5:
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 2
        game_state["free_throws_remaining"] = 2
        game_state["bonus_active"] = False
        game_state["last_ball_handler"] = ball_handler
    else:
        game_state["offensive_state"] = "HALF_COURT"
        game_state["free_throws"] = 0
        game_state["free_throws_remaining"] = 0

    #craft foul statement here and assign to game_state["text"]
    bh_pos = next(
        (pos for pos, obj in game_state["players"][off_team].items() if obj == ball_handler),
        None
    )
    
    return {
        "result_type": "FOUL",
        "ball_handler": ball_handler,
        "screener": screener,
        "passer": passer,
        "defender": defender,
        "foul_type": foul_type,
        "text": text,
        "possession_flips": False,
        "start_coords": {bh_pos: {"x": 72, "y": 25}},
        "end_coords": {bh_pos: {"x": 72, "y": 25}},
        "time_elapsed": time_elapsed
    }


# #FAST BREAK
def resolve_fast_break_logic(game: "GameManager"):
    from BackEnd.models.game_manager import GameManager
    print("Entering resolve_fast_break()")
    game_state = game.game_state
    print(f"game_state rebound: {game_state.get('last_rebound')}")

    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    players = game_state["players"]
    game_state["scouting_data"][off_team]["offense"]["Fast_Break_Entries"] += 1
    game_state["scouting_data"][def_team]["defense"]["vs_Fast_Break"]["used"] += 1

    fb_roles = {
        "offense": [],
        "defense": [],
        "ball_handler": None,
        "outlet_passer": None
    }
    
    rebound = game_state.get("last_rebound") == "DREB"

    if rebound:
        #resetting last_rebound to avoid carry over bugs
        game_state["last_rebound"] = "" 
        
        # Choose outlet passer (rebounder)
        rebounder = game_state.get("last_rebounder", None) #object

        bh_pos = random.choices(["PG", "SG", "SF"], weights=[75, 15, 10])[0]
        ball_handler = players[off_team][bh_pos]

        # Ensure outlet passer != ball handler
        if rebounder and rebounder != ball_handler:
            fb_roles["outlet_passer"] = rebounder
        else:
            fb_roles["outlet_passer"] = None
        fb_roles["ball_handler"] = ball_handler
        # Add other offensive players in play
        for pos in ["PG", "SG", "SF", "PF"]:
            if players[off_team][pos] != ball_handler and players[off_team][pos] != rebounder:
                if random.random() < {"PG": 0.5, "SG": 0.5, "SF": 0.2, "PF": 0.05}.get(pos, 0):
                    fb_roles["offense"].append(players[off_team][pos])

        # Add defensive players
        for pos in ["PG", "SG", "SF", "PF"]:
            if random.random() < {"PG": 0.9, "SG": 0.8, "SF": 0.4, "PF": 0.1}.get(pos, 0):
                fb_roles["defense"].append(players[def_team][pos])

    else:  # STEAL
        ball_handler = game_state.get("last_stealer")
        if ball_handler is None:
            ball_handler = game_state["players"][off_team]["PG"]
        fb_roles["ball_handler"] = ball_handler

        for pos in ["PG", "SG", "SF"]:
            if players[off_team][pos] != ball_handler:
                if random.random() < {"PG": 0.5, "SG": 0.4, "SF": 0.05}.get(pos, 0):
                    fb_roles["offense"].append(players[off_team][pos])

        for pos in ["PG", "SG", "SF"]:
            if random.random() < {"PG": 0.8, "SG": 0.5, "SF": 0.2}.get(pos, 0):
                fb_roles["defense"].append(players[def_team][pos])

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
        print("HCO triggered")
        game_state["scouting_data"][def_team]["defense"]["vs_Fast_Break"]["success"] += 1

        from BackEnd.models.turn_manager import TurnManager

        return TurnManager(game).resolve_half_court_offense()
    
    #get shooter and passer (if applicable)
    # Assign shooter and passer for shot, turnover, or foul scenarios
    offense_in_play = [fb_roles["ball_handler"]] + fb_roles["offense"]
    shooter = random.choice(offense_in_play)

    fb_roles["shooter"] = shooter
    # If shooter is not the ball handler, then ball handler is the passer
    fb_roles["passer"] = fb_roles["ball_handler"] if shooter != fb_roles["ball_handler"] else ""
    if fb_roles["passer"] != None and fb_roles["passer"] not in game_state["players"][off_team].values():
        print(f"⚠️ Invalid passer assignment: {fb_roles['passer']} not in team {off_team}")
        print(f"players in offense team: {game_state['players'][off_team]}")
    fb_roles["screener"] = None

    # Foul or turnover possibilities
    if event_type == "O_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "OFFENSE"
    elif event_type == "D_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "DEFENSE"

    print(f"Event type: {event_type}")
    print(f"Roles: {fb_roles}")
    
    if event_type == "SHOT":
        shot_manager = ShotManager(game_state)
        turn_result = shot_manager.resolve_fast_break_shot(fb_roles)

    elif event_type == "TURNOVER":
        turnover_type = random.choice(["STEAL", "DEAD BALL"])
        turn_result = resolve_turnover(fb_roles, game_state, turnover_type)
    elif event_type == "FOUL":
        turn_result = resolve_foul(fb_roles, game_state)
    
    if turn_result["result_type"] == "MAKE":
        game_state["scouting_data"][game_state["offense_team"]]["offense"]["Fast_Break_Success"] += 1

    elif turn_result["result_type"] == "FOUL":
        if game_state.get("foul_team") == "DEFENSE":
            game_state["scouting_data"][game_state["offense_team"]]["offense"]["Fast_Break_Success"] += 1
        elif game_state.get("foul_team") == "OFFENSE":
            game_state["scouting_data"][game_state["defense_team"]]["defense"]["vs_Fast_Break"]["success"] += 1

    elif turn_result["result_type"] in ["MISS", "TURNOVER"]:
        game_state["scouting_data"][game_state["defense_team"]]["defense"]["vs_Fast_Break"]["success"] += 1


    
    # ✅ Add safety checks before returning
    assert turn_result is not None, "turn_result is None"
    assert "time_elapsed" in turn_result, "turn_result missing 'time_elapsed'"
    return turn_result

# #FREE_THROW
def resolve_free_throw_logic(game_state):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    shooter = game_state["last_ball_handler"] #this is a player object, not a position string
    attrs = shooter.attributes

    # Use player's FT attribute
    ft_shot_score = ((attrs["FT"] * 0.8) + (attrs["CH"] * 0.2)) * random.randint(1, 6)
    makes_shot = ft_shot_score >= game_state["team_attributes"][off_team]["ft_shot_threshold"]
    possession_flips = False
    text = ""

    # Always record FTA
    shooter.record_stat("FTA")

    if makes_shot:
        shooter.record_stat("FTM")
        game_state["score"][off_team] += 1
        quarter_index = game_state["quarter"] - 1
        game_state["points_by_quarter"][off_team][quarter_index] += 1
        text = f"{shooter} hits the free throw!"
    else:
        text = f"{shooter} misses the free throw."

    game_state["free_throws_remaining"] -= 1

    # If no FTs remain, switch state and determine rebound if missed
    if game_state["free_throws_remaining"] <= 0:
        game_state["offensive_state"] = "HALF_COURT"

        if not makes_shot:
            # Last FT missed → live rebound
            rebounder_dict = default_rebounder_dict()
            o_pos = choose_rebounder(rebounder_dict, "offense")
            d_pos = choose_rebounder(rebounder_dict, "defense")
            o_rebounder = game_state["players"][off_team][o_pos]
            d_rebounder = game_state["players"][def_team][d_pos]
            o_attr = o_rebounder.attributes
            d_attr = d_rebounder.attributes


            o_score = calculate_rebound_score(o_attr)
            d_score = calculate_rebound_score(d_attr)

            off_mod = game_state["team_attributes"][off_team]["rebound_modifier"]
            def_mod = game_state["team_attributes"][def_team]["rebound_modifier"]
            bias = def_mod - off_mod
            def_prob = min(0.95, max(0.55, 0.75 + bias))

            total = d_score + o_score
            d_weight = d_score / total if total > 0 else 0.5
            d_weight += (def_prob - 0.5)
            d_weight = min(0.95, max(0.05, d_weight))

            rebound_team = def_team if random.random() < d_weight else off_team
            rebounder = d_rebounder if rebound_team == def_team else o_rebounder
            stat = "DREB" if rebound_team == def_team else "OREB"
            game_state["last_rebound"] = stat  # stat is either "DREB" or "OREB"
            rebounder.record_stat(stat)

            if rebound_team == def_team:
                possession_flips = True
                if random.random() < get_fast_break_chance(game_state):
                    game_state["offensive_state"] = "FAST_BREAK"
                else:
                    game_state["offensive_state"] = "HCO"
                game_state["last_rebounder"] = rebounder
                game_state["last_rebound"] = stat
                text += f" {rebounder} grabs the defensive rebound."
            else:
                # 🟡 Offensive rebound — enter putback loop!
                putback_result = resolve_offensive_rebound_loop(
                    game_state, off_team, def_team, rebounder
                )
                return putback_result
        else:
            possession_flips = True
            game_state["offensive_state"] = "HCO"

    shooter_pos = next(
        (pos for pos, obj in game_state["players"][off_team].items() if obj == shooter),
        None
    )
    
    return {
        "result_type": "FREE_THROW",
        "ball_handler": shooter,
        "text": text,
        "start_coords": {shooter_pos: {"x": 88, "y": 25}},
        "end_coords": {shooter_pos: {"x": 88, "y": 25}},
        "time_elapsed": 0,
        "possession_flips": possession_flips,
    }

# def resolve_half_court_offense(game_state):
#     # Assume you already have game_state, and team name is known
#     pbm = PlaybookManager(game_state["scouting_data"], game_state["offense_team"])
#     playcalls = pbm.get_playcalls(game_state)

#     game_state["current_playcall"] = playcalls["offense"]
#     game_state["defense_playcall"] = playcalls["defense"]
#     roles = assign_roles(game_state, playcalls["offense"]) #shooter, screener, ball_handler, passer, pass_chain, defender
#     # Track offensive playcall use
#     off_team = game_state["offense_team"]
#     off_playcall = playcalls["offense"]
#     game_state["scouting_data"][off_team]["offense"]["Playcalls"][off_playcall]["used"] += 1
#     def_team = game_state["defense_team"]
#     def_call = playcalls["defense"]
#     game_state["scouting_data"][def_team]["defense"][def_call]["used"] += 1

#     event_type = determine_event_type(game_state, roles)

#     if event_type == "O_FOUL":
#         event_type = "FOUL"
#         game_state["foul_team"] = "OFFENSE"
#     elif event_type == "D_FOUL":
#         event_type = "FOUL"
#         game_state["foul_team"] = "DEFENSE"

#     if event_type == "SHOT":
#         turn_result = resolve_shot(roles, game_state)
#     elif event_type == "TURNOVER":
#         turnover_type = random.choice(["STEAL", "DEAD BALL"])
#         turn_result = resolve_turnover(roles, game_state, turnover_type)
#     elif event_type == "FOUL":
#         #assign the player committing the foul here, which is assigned the calculate_foul_turnover function
#         turn_result = resolve_foul(roles, game_state)

#     # Define what counts as offensive success & defensive success
#     if turn_result["result_type"] == "MAKE" or (turn_result["result_type"] == "FOUL" and game_state.get("foul_team") == "DEFENSE"):
#         game_state["scouting_data"][off_team]["offense"]["Playcalls"][off_playcall]["success"] += 1
#     else:
#         game_state["scouting_data"][def_team]["defense"][def_call]["success"] += 1

#     # ✅ Add safety checks before returning
#     assert turn_result is not None, "turn_result is None"
#     assert "time_elapsed" in turn_result, "turn_result missing 'time_elapsed'"
#     # print(f"turn_result: {turn_result}")
#     return turn_result

def resolve_turnover_logic(roles, game_state, turnover_type="DEAD BALL"):

    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    ball_handler = roles["ball_handler"]
    defender = roles.get("defender", "")
    ball_handler.record_stat("TO")

    if turnover_type == "STEAL":
        defender.record_stat("STL")
        if random.random() < get_fast_break_chance(game_state):
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            game_state["offensive_state"] = "HCO"
        game_state["last_stealer"] = defender
        game_state["last_rebound"] = ""
        text = f"{get_name_safe(defender)} jumps the pass and takes it the other way!"
    else:
        game_state["offensive_state"] = "HCO"
        text = f"{ball_handler} throws it out of bounds."
        game_state["offensive_state"] = "HCO"

    bh_pos = next(
        (pos for pos, obj in game_state["players"][off_team].items() if obj == ball_handler),
        None
    )
    
    return {
        "result_type": turnover_type,
        "ball_handler": ball_handler,
        "text": text,
        "start_coords": {bh_pos: {"x": 72, "y": 25}},
        "end_coords": {bh_pos: {"x": 68, "y": 25}},
        "time_elapsed": random.randint(3, 8),
        "possession_flips": True  # Let the turn loop handle the flip
    }

def resolve_half_court_offense_logic(game: "GameManager") -> dict:
    game_state = game.game_state
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    off_call = game_state["current_playcall"]
    def_call = game_state["defense_playcall"]

    # Track usage
    game.scouting_data[off_team]["offense"]["Playcalls"][off_call]["used"] += 1
    game.scouting_data[def_team]["defense"][def_call]["used"] += 1

    roles = game.turn_manager.assign_roles(game)
    shot_result = game.shot_manager.resolve_shot(roles)

    # Track success
    if shot_result["result_type"] == "MAKE":
        game.scouting_data[off_team]["offense"]["Playcalls"][off_call]["success"] += 1
    elif shot_result["result_type"] in ["MISS", "TURNOVER"]:
        game.scouting_data[def_team]["defense"][def_call]["success"] += 1

    if shot_result.get("missed"):
        return game.turn_manager.rebound_manager.handle_rebound(game, roles)

    return shot_result
