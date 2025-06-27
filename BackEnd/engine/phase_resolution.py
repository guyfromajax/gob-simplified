import random
from typing import TYPE_CHECKING
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

from BackEnd.utils.shared import (
    get_name_safe, 
    get_time_elapsed, 
    get_fast_break_chance, 
    calculate_rebound_score, 
    choose_rebounder, 
    default_rebounder_dict, 
    resolve_offensive_rebound_loop,
    record_team_points,
    unpack_game_context
)
    
def resolve_foul(roles, game):
    
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
    if foul_team == "DEFENSE":
        def_team.team_fouls += 1
        text = f"{get_name_safe(foul_player)} fouls {get_name_safe(ball_handler)}!"
    else:
        off_team.team_fouls += 1
        text = f"{get_name_safe(foul_player)} commits an offensive foul!"

    foul_type = random.choice(["SHOOTING", "NON_SHOOTING"]) if foul_team == "DEFENSE" else "NON_SHOOTING" # Future logic: determine if this was shooting or not

    if foul_type == "SHOOTING":
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 2  # Future: support 3 FT on 3PT attempt
        game_state["free_throws_remaining"] = 2
        game_state["last_ball_handler"] = ball_handler
        ball_handler = shooter
    elif def_team.team_fouls >= 10:
        game_state["free_throws"] = 2
        game_state["free_throws_remaining"] = 2
        game_state["bonus_active"] = False
        game_state["last_ball_handler"] = ball_handler
    elif def_team.team_fouls >= 5:
        game_state["offensive_state"] = "FREE_THROW"
        game_state["free_throws"] = 2
        game_state["free_throws_remaining"] = 2
        game_state["bonus_active"] = False
        game_state["last_ball_handler"] = ball_handler
    else:
        game_state["offensive_state"] = "HALF_COURT"
        game_state["free_throws"] = 0
        game_state["free_throws_remaining"] = 0

    bh_pos = get_player_position(off_team.lineup, ball_handler)
    
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
        "outlet_passer": None
    }
    
    rebound = game_state.get("last_rebound") == "DREB"

    if rebound:
        #resetting last_rebound to avoid carry over bugs
        game_state["last_rebound"] = "" 
        
        # Choose outlet passer (rebounder)
        rebounder = game_state.get("last_rebounder", None) #object

        bh_pos = random.choices(["PG", "SG", "SF"], weights=[75, 15, 10])[0]
        ball_handler = off_lineup[bh_pos]

        # Ensure outlet passer != ball handler
        if rebounder and rebounder != ball_handler:
            fb_roles["outlet_passer"] = rebounder
        else:
            fb_roles["outlet_passer"] = None
        fb_roles["ball_handler"] = ball_handler
        # Add other offensive players in play
        for pos in ["PG", "SG", "SF", "PF"]:
            if off_lineup[pos] != ball_handler and off_lineup[pos] != rebounder:
                if random.random() < {"PG": 0.5, "SG": 0.5, "SF": 0.2, "PF": 0.05}.get(pos, 0):
                    fb_roles["offense"].append(off_lineup[pos])

        # Add defensive players
        for pos in ["PG", "SG", "SF", "PF"]:
            if random.random() < {"PG": 0.9, "SG": 0.8, "SF": 0.4, "PF": 0.1}.get(pos, 0):
                fb_roles["defense"].append(def_lineup[pos])

    else:  # STEAL
        ball_handler = game_state.get("last_stealer")
        if ball_handler is None:
            ball_handler = off_lineup["PG"]
        fb_roles["ball_handler"] = ball_handler

        for pos in ["PG", "SG", "SF"]:
            if off_lineup[pos] != ball_handler:
                if random.random() < {"PG": 0.5, "SG": 0.4, "SF": 0.05}.get(pos, 0):
                    fb_roles["offense"].append(off_lineup[pos])

        for pos in ["PG", "SG", "SF"]:
            if random.random() < {"PG": 0.8, "SG": 0.5, "SF": 0.2}.get(pos, 0):
                fb_roles["defense"].append(def_lineup[pos])

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
        return TurnManager(game).run_turn()

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
        turn_result = resolve_foul(fb_roles, game)
    
    if turn_result["result_type"] == "MAKE": #def_scouting
        off_scouting["offense"]["Fast_Break_Success"] += 1

    elif turn_result["result_type"] == "FOUL":
        if game_state.get("foul_team") == "DEFENSE":
            off_scouting["offense"]["Fast_Break_Success"] += 1
        elif game_state.get("foul_team") == "OFFENSE":
            def_scouting["defense"]["vs_Fast_Break"]["success"] += 1

    elif turn_result["result_type"] in ["MISS", "TURNOVER"]:
        def_scouting["defense"]["vs_Fast_Break"]["success"] += 1


    
    # ✅ Add safety checks before returning
    assert turn_result is not None, "turn_result is None"
    assert "time_elapsed" in turn_result, "turn_result missing 'time_elapsed'"
    return turn_result

# #FREE_THROW
def resolve_free_throw_logic(game):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    shooter = game_state["last_ball_handler"] #this is a player object, not a position string
    attrs = shooter.attributes

    # Use player's FT attribute
    ft_shot_score = ((attrs["FT"] * 0.8) + (attrs["CH"] * 0.2)) * random.randint(1, 6)
    makes_shot = ft_shot_score >= off_team.team_attributes["ft_shot_threshold"]
    possession_flips = False
    text = ""

    # Always record FTA
    shooter.record_stat("FTA")

    if makes_shot:
        shooter.record_stat("FTM")
        record_team_points(game, off_team, 1)
        text = f"{get_name_safe(shooter)} hits the free throw!"
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
            game_state["last_rebound"] = stat  # stat is either "DREB" or "OREB"
            rebounder.record_stat(stat)
            print(f"+1 rebound for {get_name_safe(rebounder)}")

            if rebound_team == def_team:
                possession_flips = True
                if random.random() < get_fast_break_chance(game):
                    game_state["offensive_state"] = "FAST_BREAK"
                else:
                    game_state["offensive_state"] = "HCO"
                game_state["last_rebounder"] = rebounder
                game_state["last_rebound"] = stat
                text += f" {rebounder} grabs the defensive rebound."
            else:
                # 🟡 Offensive rebound — enter putback loop!
                putback_result = resolve_offensive_rebound_loop(
                    game, rebounder
                )
                return putback_result
        else:
            possession_flips = True
            game_state["offensive_state"] = "HCO"

    shooter_pos = get_player_position(off_lineup, shooter)
    
    return {
        "result_type": "FREE_THROW",
        "ball_handler": shooter,
        "text": text,
        "start_coords": {shooter_pos: {"x": 88, "y": 25}},
        "end_coords": {shooter_pos: {"x": 88, "y": 25}},
        "time_elapsed": 0,
        "possession_flips": possession_flips,
    }


def resolve_turnover_logic(roles, game, turnover_type="DEAD BALL"):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    ball_handler = roles["ball_handler"]
    defender = roles.get("defender", "")
    ball_handler.record_stat("TO")

    if turnover_type == "STEAL":
        defender.record_stat("STL")
        if random.random() < get_fast_break_chance(game):
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

    bh_pos = get_player_position(off_lineup, ball_handler)
    
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

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    off_call = game_state["current_playcall"]
    def_call = game_state["defense_playcall"]

    # Track usage
    off_scouting = off_team.scouting_data
    def_scouting = def_team.scouting_data
    off_scouting["offense"]["Playcalls"][off_call]["used"] += 1
    def_scouting["defense"][def_call]["used"] += 1

    roles = game.turn_manager.assign_roles()
    
    # 🧠 Determine event type (SHOT / TURNOVER / O_FOUL / D_FOUL)
    from BackEnd.models.turn_manager import TurnManager
    event_type = game.turn_manager.determine_event_type(roles)
    if event_type == "TURNOVER":
        return resolve_turnover_logic(roles, game, turnover_type="DEAD BALL")

    elif event_type == "O_FOUL":
        game_state["foul_team"] = "OFFENSE"
        return resolve_foul(roles, game)

    elif event_type == "D_FOUL":
        game_state["foul_team"] = "DEFENSE"
        return resolve_foul(roles, game)
    
    shot_result = game.shot_manager.resolve_shot(roles)

    # Track success
    if shot_result["result_type"] == "MAKE":
        off_scouting["offense"]["Playcalls"][off_call]["success"] += 1
    elif shot_result["result_type"] in ["MISS", "TURNOVER"]:
        def_scouting["defense"][def_call]["success"] += 1

    if shot_result["result_type"] == "MISS":
        return game.turn_manager.rebound_manager.handle_rebound()


    return shot_result

def calculate_foul_turnover(game, positions, thresholds, roles):
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    roles["foul_player"] = None
    ball_handler = roles["ball_handler"]
    defense_call = game_state["defense_playcall"]

    # === Defensive Foul ===
    d_pos = positions["d_foul"]
    d_foul_player = def_team.lineup[d_pos]
    d_attr = d_foul_player.attributes

    iq = d_attr["IQ"] * 0.3
    ch = d_attr["CH"] * 0.3
    if d_pos in ["PG", "SG"]:
        movement = d_attr["OD"] * 0.2 + d_attr["AG"] * 0.2
    elif d_pos == "SF":
        movement = d_attr["OD"] * 0.1 + d_attr["ID"] * 0.1 + d_attr["AG"] * 0.1 + d_attr["ST"] * 0.1
    elif d_pos in ["PF", "C"]:
        movement = d_attr["ID"] * 0.2 + d_attr["ST"] * 0.2
    else:
        movement = 0

    d_foul_score = (iq + ch + movement) * random.randint(1, 6)
    if defense_call == "Zone":
        d_foul_score *= 1.1
    is_d_foul = d_foul_score < (thresholds["d_foul_threshold"] * 1.2)

    # === Offensive Foul ===
    o_pos = positions["o_foul"]
    o_foul_player = off_lineup[o_pos]
    o_attr = o_foul_player.attributes

    iq = o_attr["IQ"] * 0.3
    ch = o_attr["CH"] * 0.3
    if o_pos in ["PG", "SG"]:
        movement = o_attr["AG"] * 0.4
    elif o_pos == "SF":
        movement = o_attr["AG"] * 0.2 + o_attr["ST"] * 0.2
    elif o_pos in ["PF", "C"]:
        movement = o_attr["ST"] * 0.4
    else:
        movement = 0

    o_foul_score = (iq + ch + movement) * random.randint(1, 6)
    is_o_foul = o_foul_score < (thresholds["o_foul_threshold"] * 0.8)

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
    is_turnover = turnover_score < thresholds["turnover_threshold"]

    # print(f"Turnover → {get_name_safe(turnover_player)} vs {get_name_safe(def_mod_player)}: score={round(turnover_score, 2)} vs threshold={thresholds['turnover_threshold']} | flag={is_turnover}")

    decisions = {
        "TURNOVER": (is_turnover, turnover_score),
        "D_FOUL": (is_d_foul, d_foul_score),
        "O_FOUL": (is_o_foul, o_foul_score)
    }

    active = [(k, v[1]) for k, v in decisions.items() if v[0]]
    if not active:
        print()
        return "SHOT"

    active.sort(key=lambda x: (x[1], ["TURNOVER", "D_FOUL", "O_FOUL"].index(x[0])))

    if active[0][0] == "TURNOVER":
        roles["turnover_player"] = turnover_player
        roles["turnover_defender"] = def_mod_player
        roles["ball_handler"] = turnover_player
    elif active[0][0] == "D_FOUL":
        roles["foul_player"] = d_foul_player
    elif active[0][0] == "O_FOUL":
        roles["foul_player"] = o_foul_player

    print()
    return active[0][0]