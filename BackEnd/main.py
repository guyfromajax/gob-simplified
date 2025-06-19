import random
import json
from BackEnd.db import players_collection, teams_collection

#PRE-GAME SETTINGS

ALL_ATTRS = [
    "SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT",  # malleable
    "ND", "IQ", "CH", "EM", "MO"  # static or macro-adjusted
    ]

BOX_SCORE_KEYS = [
    "FGA", "FGM", "3PTA", "3PTM", "FTA", "FTM",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "MIN", "PTS",
    "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S"
]


PLAYCALL_ATTRIBUTE_WEIGHTS = {
    "Base": {"SH": 2, "SC": 2, "AG": 2, "ST": 2, "IQ": 1, "CH": 1},
    "Freelance": {"SH": 2, "SC": 2, "AG": 1, "ST": 1, "IQ": 3, "CH": 1},
    "Inside": {"SC": 6, "ST": 2, "IQ": 1, "CH": 1},
    "Attack": {"SC": 5, "AG": 2, "ST": 1, "IQ": 1, "CH": 1},
    "Outside": {"SH": 8, "IQ": 1, "CH": 1},
    "Set": "Same as Attack"
}

THREE_POINT_PROBABILITY = {
    "Outside": 0.8,
    "Base": 0.4,
    "Freelance": 0.2
    # All others default to 0.0
}

BLOCK_PROBABILITY = {
    "Inside": 0.2,
    "Attack": 0.1,
    "Base": 0.1,
    "Freelance": 0.1
    # All others default to 0.0
}

MALLEABLE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT"]

STRATEGY_CALL_DICTS = {
    "defense": {
        0: ["Man"],
        1: ["Man", "Man", "Zone"],
        2: ["Man", "Zone"],
        3: ["Man", "Zone", "Zone"],
        4: ["Zone"]},
    "tempo": {
        0: ["slow"],
        1: ["slow", "normal"],
        2: ["normal"],
        3: ["normal", "fast"],
        4: ["fast"],
    },
    "aggression": {
        0: ["passive"],
        1: ["passive", "normal"],
        2: ["normal"],
        3: ["normal", "aggressive"],
        4: ["aggressive"],
    },
}

TEMPO_PASS_DICT = {
    "slow": random.randint(1,6),
    "normal": random.randint(2,4),
    "fast": random.randint(1,3)
}

TURNOVER_CALC_DICT = {
    0: ["PG"],
    1: ["PG", "SG"],
    2: ["PG", "SG", "PG"],
    3: ["PG", "SG", "SF", "PG"],
    4: ["PG", "SG", "SF", "PF", "PG"],
    5: ["PG", "SG", "SF", "PF", "C", "PG"],
    6: ["PG", "SG", "SF", "PF", "C", "PG", "PG"]
}

POSITION_LIST = ["PG", "SG", "SF", "PF", "C"]

def default_rebounder_dict():
    return {
        "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
        "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
    }

def initialize_playcall_settings():
    playcalls = ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]
    settings = {}
    for team in ["Lancaster", "Bentley-Truman"]:
        settings[team] = {call: random.randint(1, 4) for call in playcalls}
    return settings

def initialize_team_attributes():
    settings = {}
    for team in ["Lancaster", "Bentley-Truman"]:
        # Initialize dictionary for each team
        team_settings = {
            "shot_threshold": random.randint(150, 250),
            "ft_shot_threshold": random.randint(150, 250),
            "turnover_threshold": random.randint(-250, -150),
            "foul_threshold": random.randint(40, 90),
            "rebound_modifier": random.choice([0.8, 0.9, 1.0, 1.1, 1.2]),
            "momentum_score": random.randint(0,20),
            "momentum_delta": random.choice([1,2,3,4,5]),
            "offensive_efficienty": random.randint(1,10),
            "offensive_adjust": random.randint(1,10),
            "o_tendency_reads": random.randint(1,10),
            "d_tendency_reads": random.randint(1,10),
            "team_chemistry": random.randint(7,25)
        }
        settings[team] = team_settings
    return settings

def initialize_strategy_calls():
    calls = ["offense_playcall", "defense_playcall", "tempo_call", "aggression_call"]
    settings = {}
    for team in ["Lancaster", "Bentley-Truman"]:
        settings[team] = {call: "" for call in calls}
    return settings

def initialize_strategy_settings():
    strategies = ["defense","tempo", "aggression", "fast_break"]
    settings = {}

    for team in ["Lancaster", "Bentley-Truman"]:
        team_settings = {s: random.randint(0, 4) for s in strategies}
        team_settings["half_court_trap"] = 0
        team_settings["full_court_press"] = 0
        settings[team] = team_settings

    return settings

def print_initial_settings(game_state):
    print("\n=== GAME INITIALIZATION SETTINGS ===")

    print("\n--- Playcall Weights ---")
    for team, weights in game_state["playcall_weights"].items():
        print(f"{team}:")
        for k, v in weights.items():
            print(f"  {k.ljust(10)}: {v}")
    
    print("\n--- Team Attributes ---")
    for team, attrs in game_state["team_attributes"].items():
        print(f"{team}:")
        for k, v in attrs.items():
            print(f"  {k.ljust(20)}: {v}")

    print("\n--- Strategy Settings ---")
    for team, strat in game_state["strategy_settings"].items():
        print(f"{team}:")
        for k, v in strat.items():
            print(f"  {k.ljust(20)}: {v}")

    print("\n--- Strategy Calls ---")
    for team, calls in game_state["strategy_calls"].items():
        print(f"{team}:")
        for k, v in calls.items():
            print(f"  {k.ljust(20)}: {v}")

# --- Aggregator for simulation results ---
def initialize_aggregates():
    return {
        "team_results": [],
        "player_box_scores": []
    }

def collect_simulation_stats(game_state, aggregates):
    aggregates["team_results"].append({
        "score": dict(game_state["score"]),
        "points_by_quarter": dict(game_state["points_by_quarter"])
    })
    player_stats_snapshot = {
        team: {
            player: dict(stats)
            for player, stats in game_state["box_score"][team].items()
        }
        for team in game_state["box_score"]
    }
    aggregates["player_box_scores"].append(player_stats_snapshot)

#RESOLVE_TURN
def resolve_strategy_calls(game_state):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    tempo_setting = game_state["strategy_settings"][off_team]["tempo"]
    aggression_setting = game_state["strategy_settings"][def_team]["aggression"]
    game_state["strategy_calls"][off_team]["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
    game_state["strategy_calls"][def_team]["aggression_call"] = random.choice(STRATEGY_CALL_DICTS["aggression"][aggression_setting])
    
    return game_state["strategy_calls"] 

def resolve_turn(game_state):
    off_team = game_state["offense_team"]
    # print(f"game_state: {game_state}")
    if game_state["offensive_state"] == "FREE_THROW":
        return resolve_free_throw(game_state)

    # Only allow fast break if last play ended with a defensive rebound or steal
    # ✅ Fast break check — only if previous result was a rebound or steal
    elif game_state["offensive_state"] == "FAST_BREAK":
        game_state["offensive_state"] = ""
        return resolve_fast_break(game_state)
    
    return resolve_half_court_offense(game_state)


#FAST BREAK
def resolve_fast_break(game_state):
    print("Entering resolve_fast_break()")
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
        rebounder = game_state.get("last_rebounder", None)

        bh_pos = random.choices(["PG", "SG", "SF"], weights=[75, 15, 10])[0]
        ball_handler = players[off_team][bh_pos]

        # Ensure outlet passer != ball handler
        if rebounder and rebounder != ball_handler:
            fb_roles["outlet_passer"] = rebounder
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

        return resolve_half_court_offense(game_state)
    
    #get shooter and passer (if applicable)
    # Assign shooter and passer for shot, turnover, or foul scenarios
    offense_in_play = [fb_roles["ball_handler"]] + fb_roles["offense"]
    shooter = random.choice(offense_in_play)

    fb_roles["shooter"] = shooter
    # If shooter is not the ball handler, then ball handler is the passer
    fb_roles["passer"] = fb_roles["ball_handler"] if shooter != fb_roles["ball_handler"] else ""
    if fb_roles["passer"] not in game_state["players"][off_team] and fb_roles["passer"] != "":
        print(f"⚠️ Invalid passer assignment: {roles['passer']} not in team {off_team}")
        print(f"players in offense team: {game_state['players'][off_team]}")
    fb_roles["screener"] = ""

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
        turn_result = resolve_fast_break_shot(game_state, fb_roles)
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

#FREE_THROW
def resolve_free_throw(game_state):
    shooter = game_state["last_ball_handler"] #this is a player object, not a position string
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    attrs = game_state["players"][off_team][shooter]["attributes"]

    # Use player's FT attribute
    ft_shot_score = ((attrs["FT"] * 0.8) + (attrs["CH"] * 0.2)) * random.randint(1, 6)
    makes_shot = ft_shot_score >= game_state["team_attributes"][off_team]["ft_shot_threshold"]
    possession_flips = False
    text = ""

    # Always record FTA
    record_stat(shooter, "FTA") #confirmed

    if makes_shot:
        record_stat(shooter, "FTM") #confirmed
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
            o_attr = game_state["players"][off_team][o_rebounder]["attributes"]
            d_attr = game_state["players"][def_team][d_rebounder]["attributes"]

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
            record_stat(rebounder, stat) #confirmed

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

    return {
        "result_type": "FREE_THROW",
        "ball_handler": shooter,
        "text": text,
        "start_coords": {shooter: {"x": 88, "y": 25}},
        "end_coords": {shooter: {"x": 88, "y": 25}},
        "time_elapsed": 0,
        "possession_flips": possession_flips,
    }

#HCO
def get_playcalls(game_state):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    off_weights = game_state["playcall_weights"][off_team]
    chosen_playcall = weighted_random_from_dict(off_weights)

    # DEFENSIVE PLAYCALL
    def_setting = game_state["strategy_settings"][def_team]["defense"]
    defense_options = STRATEGY_CALL_DICTS["defense"].get(def_setting, ["Man"])
    chosen_defense = random.choice(defense_options)

    # Track it
    game_state["playcall_tracker"][off_team][chosen_playcall] += 1
    game_state["defense_playcall_tracker"][def_team][chosen_defense] += 1

    return {
        "offense": chosen_playcall,
        "defense": chosen_defense
    }

def assign_roles(game_state, playcall):
    off_team = game_state["offense_team"]
    players = game_state["players"][off_team]

    # Compute shot weights using attributes embedded in each player object
    weights_dict = PLAYCALL_ATTRIBUTE_WEIGHTS.get("Attack" if playcall == "Set" else playcall, {})

    shot_weights = {
        pos: sum(
            players[pos]["attributes"][attr] * weight
            for attr, weight in weights_dict.items()
        )
        for pos in players
    }

    shooter_pos = weighted_random_from_dict(shot_weights)

    # Compute screener weights (excluding the shooter)
    screen_weights = {
        pos: (
            players[pos]["attributes"]["ST"] * 6 +
            players[pos]["attributes"]["AG"] * 2 +
            players[pos]["attributes"]["IQ"] * 1 +
            players[pos]["attributes"]["CH"] * 1
        )
        for pos in players if pos != shooter_pos
    }
    screener_pos = max(screen_weights, key=screen_weights.get)

    # Pass chain and passer
    pass_chain = generate_pass_chain(game_state, shooter_pos)
    passer_pos = pass_chain[-2] if len(pass_chain) >= 2 else ""
    passer = passer_pos if passer_pos != shooter_pos else ""

    if game_state["defense_playcall"] == "Zone":
        defender_pos = random.choice(POSITION_LIST)
    else:
        defender_pos = shooter_pos

    return {
        "shooter": shooter_pos,
        "screener": screener_pos,
        "ball_handler": shooter_pos,
        "passer": passer,
        "pass_chain": pass_chain,
        "defender": defender_pos,
    }



def get_shot_weights_for_playcall(team_attrs, playcall_name):
    if playcall_name == "Set":
        playcall_name = "Attack"
    weights = PLAYCALL_ATTRIBUTE_WEIGHTS[playcall_name]
    
    shot_scores = {}
    for player, attr in team_attrs.items():
        score = sum(attr[stat] * wt for stat, wt in weights.items())
        shot_scores[player] = score

    return shot_scores



def determine_event_type(game_state, roles):
    # Base weights (can be tuned later)
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    thresholds = get_team_thresholds(game_state)
    tempo_call = game_state["strategy_calls"][off_team]["tempo_call"]
    pass_count = TEMPO_PASS_DICT[tempo_call]
    positions = get_random_positions(pass_count)
    event_type = calculate_foul_turnover(game_state, positions, thresholds, roles)
   
    #determine number of turnover RNGs based on defense team'saggression
    for pos, player_obj in game_state["players"][off_team].items():
        player_name = f"{player_obj['first_name']} {player_obj['last_name']}"
        attr = game_state["players"][off_team][pos]["attributes"]
        ng = attr["NG"]
        for key in MALLEABLE_ATTRS:
            anchor_val = attr[f"anchor_{key}"]
            attr[key] = int(anchor_val * ng)

    return event_type

def resolve_half_court_offense(game_state):
    playcalls = get_playcalls(game_state)
    game_state["current_playcall"] = playcalls["offense"]
    game_state["defense_playcall"] = playcalls["defense"]
    roles = assign_roles(game_state, playcalls["offense"])
    # Track offensive playcall use
    off_team = game_state["offense_team"]
    off_playcall = playcalls["offense"]
    game_state["scouting_data"][off_team]["offense"]["Playcalls"][off_playcall]["used"] += 1
    def_team = game_state["defense_team"]
    def_call = playcalls["defense"]
    game_state["scouting_data"][def_team]["defense"][def_call]["used"] += 1

    event_type = determine_event_type(game_state, roles)

    if event_type == "O_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "OFFENSE"
    elif event_type == "D_FOUL":
        event_type = "FOUL"
        game_state["foul_team"] = "DEFENSE"

    if event_type == "SHOT":
        turn_result = resolve_shot(roles, game_state)
    elif event_type == "TURNOVER":
        turnover_type = random.choice(["STEAL", "DEAD BALL"])
        turn_result = resolve_turnover(roles, game_state, turnover_type)
    elif event_type == "FOUL":
        #assign the player committing the foul here, which is assigned the calculate_foul_turnover function
        turn_result = resolve_foul(roles, game_state)

    # Define what counts as offensive success & defensive success
    if turn_result["result_type"] == "MAKE" or (turn_result["result_type"] == "FOUL" and game_state.get("foul_team") == "DEFENSE"):
        game_state["scouting_data"][off_team]["offense"]["Playcalls"][off_playcall]["success"] += 1
    else:
        game_state["scouting_data"][def_team]["defense"][def_call]["success"] += 1

    # ✅ Add safety checks before returning
    assert turn_result is not None, "turn_result is None"
    assert "time_elapsed" in turn_result, "turn_result missing 'time_elapsed'"
    # print(f"turn_result: {turn_result}")
    return turn_result

#POST-TURN
def generate_animation_packet(turn_result):
    """
    Creates the final JSON animation payload to send to the frontend:
    - Player coordinates
    - Action types
    - Time elapsed
    - Narration string
    - Game state deltas
    """
    return {
        "coords": {
            "start": turn_result["start_coords"],
            "end": turn_result["end_coords"]
        },
        "text": turn_result["text"],
        "time_elapsed": turn_result["time_elapsed"],
        "offensive_state": turn_result.get("new_offense_state", "HALF_COURT"),
        "foul_type": turn_result.get("foul_type", None),
    }

def recalculate_energy_scaled_attributes(game_state):
    for team in game_state["players"]:
        for pos, player_obj in game_state["players"][team].items():
            player_name = f"{player_obj['first_name']} {player_obj['last_name']}"
            attr = game_state["players"][team][pos]["attributes"]
            ng = attr["NG"]
            for key in MALLEABLE_ATTRS:
                anchor_val = attr[f"anchor_{key}"]
                attr[key] = int(anchor_val * ng)



#RESOLVE FUNCTIONS
def resolve_fast_break_shot(game_state, fb_roles):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    
    shooter_pos = fb_roles["shooter"]
    shooter = game_state["players"][off_team][shooter_pos]
    passer_pos = fb_roles.get("passer", "")
    passer = game_state["players"][off_team][passer_pos]
    if shooter_pos == passer_pos:
        passer = ""
        passer_pos = ""
    
    attrs = game_state["players"][off_team][shooter]["attributes"]
    if shooter == passer:
        passer = ""

    shot_score = (attrs["SC"] * 0.6 + attrs["CH"] * 0.2 + attrs["MO"] * 0.2) * random.randint(1, 6)

    defender_pos = random.choice(fb_roles["defense"]) if fb_roles["defense"] else ""
    defender = game_state["players"][def_team][defender_pos]
    if defender:
        defense_attrs = game_state["players"][def_team][defender_pos]["attributes"]
        defense_penalty = (defense_attrs["ID"] * 0.8 + defense_attrs["IQ"] * 0.1 + defense_attrs["CH"] * 0.1) * random.randint(1, 6)
        shot_score -= defense_penalty * 0.2
        record_stat(defender, "DEF_A") #confirmed, assuming fb_roles is an array of strings
    else:
        defense_penalty = 0

    made = shot_score >= game_state["team_attributes"][off_team]["shot_threshold"]
    record_stat(shooter, "FGA") #confirmed

    if made:
        record_stat(shooter, "FGM") #confirmed
        if passer:
            record_stat(passer, "AST") #confirmed
        text = f"{shooter} converts the fast break shot!"
        possession_flips = True
        game_state["offensive_state"] = "HCO"
        is_three = False
        points = 3 if is_three else 2
        game_state["score"][off_team] += points
        quarter_index = game_state["quarter"] - 1
        game_state["points_by_quarter"][off_team][quarter_index] += points
    else:
        if defender:
            record_stat(defender, "DEF_S") #confirmed
        rebounder_pos = random.choice(fb_roles["defense"]) if fb_roles["defense"] else ["PG"]
        rebounder = game_state["players"][def_team][rebounder_pos]
        text = f"{shooter} misses the fast break shot -- {rebounder} grabs the rebound."
        record_stat(rebounder, "DREB") #confirmed
        possession_flips = True
        if random.random() < get_fast_break_chance(game_state):
            text += " -- entering a fast break!"
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            text += " -- entering half court."
            game_state["offensive_state"] = "HCO"
        game_state["last_rebounder"] = rebounder
        game_state["last_rebound"] = "DREB"

    time_elapsed = random.randint(5, 15)

    return {
        "result_type": "MAKE" if made else "MISS",
        "ball_handler": shooter,
        "screener": None,
        "passer": passer,
        "defender": defender,
        "text": text,
        "possession_flips": possession_flips,
        "start_coords": {shooter: {"x": 72, "y": 25}},
        "end_coords": {shooter: {"x": 82, "y": 23}},
        "time_elapsed": time_elapsed
    }


def resolve_shot(roles, game_state):

    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    time_elapsed = 0
    shooter_pos = roles["shooter"]
    shooter = game_state["players"][off_team][shooter_pos]
    passer_pos = roles.get("passer", "")
    passer = game_state["players"][off_team][passer_pos]
    screener_pos = roles.get("screener", "")
    screener = game_state["players"][off_team][screener_pos]
    defender_pos = roles.get("defender", "")
    if defender_pos:
        defender = game_state["players"][def_team][defender_pos]

    print(f"-------Inside resolve_shot---------")
    print(f"shooter: {shooter_pos} | passer: {passer_pos} | screener: {screener_pos} | defender: {defender_pos}")
    
    attrs = game_state["players"][off_team][shooter_pos]["attributes"]
    
    playcall = game_state["current_playcall"]
    defense_call = game_state["defense_playcall"]
    is_three = random.random() < THREE_POINT_PROBABILITY.get(playcall, 0.0)
    shot_threshold = game_state["team_attributes"][off_team]["shot_threshold"]
    if is_three:
        shot_threshold += 100

    if playcall == "Set":
        playcall = "Attack"
    weights = PLAYCALL_ATTRIBUTE_WEIGHTS.get(playcall, {})
    shot_score = sum(attrs[attr] * (weight / 10) for attr, weight in weights.items()) * random.randint(1, 6)
    if passer_pos:
        passer_attrs = game_state["players"][off_team][passer_pos]["attributes"]
        passer_score = (passer_attrs["PS"] * 0.8 + passer_attrs["IQ"] * 0.2) * random.randint(1, 6)
        shot_score += passer_score * 0.2
    else:
        dribble_score = (attrs["AG"] * 0.8 + attrs["IQ"] * 0.2) * random.randint(1, 6)
        shot_score += dribble_score * 0.2
    defense_attrs = game_state["players"][def_team][defender_pos]["attributes"]
    defense_penalty = (defense_attrs["OD"] * 0.8 + defense_attrs["IQ"] * 0.1 + defense_attrs["CH"] * 0.1) * random.randint(1, 6)
    if defense_call == "Zone":
        defense_penalty *= 0.9
    shot_score -= defense_penalty * 0.2  # Scaling factor to tune
    if defender:
        record_stat(defender, "DEF_A") #confirmed
    # Apply bonus/penalty based on defense type and shot type
    if (defense_call == "Zone" and is_three) or (defense_call == "Man" and not is_three):
        shot_score *= 0.9
    else:
        shot_score *= 1.1


    # help defense logic
    shot_score, help_defender, help_penalty = apply_help_defense_if_triggered(
        game_state, playcall, is_three, defender_pos, shot_score
    )
    if help_defender:
        print(f"Help defense by {help_defender} → penalty applied: {round(help_penalty, 2)}")

    # Screen bonus (if applicable)
    screener_pos = roles.get("screener", "")
    if screener_pos and screener_pos != shooter_pos:
        screener = game_state["players"][off_team][screener_pos]
        screen_attrs = game_state["players"][off_team][screener_pos]["attributes"]
        screen_score = calculate_screen_score(screen_attrs)
        shot_score += screen_score * 0.15
        print(f"screen by {screener} adds {round(screen_score * 0.15, 2)} to shot score")
        record_stat(screener, "SCR_A") #confirmed
        #need to add shot defender's ability to work through the screen

    # Gravity contribution from off-ball players
    gravity_contributors = [
        pos for pos in game_state["players"][off_team]
        if pos not in [shooter_pos, passer_pos, screener_pos]
    ]

    total_gravity = 0
    for pos in gravity_contributors:
        player = game_state["players"][off_team][pos]
        attrs = game_state["players"][off_team][player]["attributes"]
        total_gravity += calculate_gravity_score(attrs)
    gravity_boost = total_gravity * 0.02  # Tunable
    shot_score += gravity_boost
    print(f"Off-ball gravity boost: +{round(gravity_boost, 2)} from {gravity_contributors}")

    print(f"offense call: {playcall} // defense call: {defense_call}")
    print(f"shooter: {shooter_pos} | passer: {passer_pos}")
    print(f"shot score = {round(shot_score, 2)} | (defense score: {round(defense_penalty * 0.2, 2)})")
    made = shot_score >= shot_threshold


    # Track attempts
    record_stat(shooter, "FGA") #confirmed
    if is_three:
        record_stat(shooter, "3PTA") #confirmed

    if made:
        record_stat(shooter, "FGM") #confirmed
        if passer_pos:
            record_stat(passer, "AST") #confirmed
        if is_three:
            record_stat(shooter, "3PTM") #confirmed
        points = 3 if is_three else 2
        game_state["score"][off_team] += points
        quarter_index = game_state["quarter"] - 1
        game_state["points_by_quarter"][off_team][quarter_index] += points
        text = f"{shooter_pos} drains a 3!" if is_three else f"{shooter_pos} makes the shot."
        possession_flips = True
        if screener_pos:
            screener = game_state["players"][off_team][screener_pos]
            record_stat(screener, "SCR_S") #confirmed
    else:
        text = f"{shooter_pos} misses the {'3' if is_three else 'shot'}."
        if defender:
            record_stat(defender, "DEF_S") #confirmed
        #Build dict based on player proximity to the ball in the future
        base_block_prob = BLOCK_PROBABILITY.get(playcall, 0.0)
        # Defensive player's ID score (scaled 0–1)
        block_skill = defense_attrs["ID"] / 100  
        # Final block chance: scaled by skill
        final_block_chance = base_block_prob * (0.5 + block_skill)  # scales 50–150% of base
        is_block = random.random() < final_block_chance
        if is_block:
            text += f"{defender_pos} blocks the shot!"
            record_stat(defender, "BLK") #confirmed
            

        rebounder_dict = {
            "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
            "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
        }

        o_pos = choose_rebounder(rebounder_dict, "offense")
        d_pos = choose_rebounder(rebounder_dict, "defense")
        o_rebounder = game_state["players"][off_team][o_pos]
        d_rebounder = game_state["players"][def_team][d_pos]

        o_attr = game_state["players"][off_team][o_rebounder]["attributes"]
        d_attr = game_state["players"][def_team][d_rebounder]["attributes"]

        o_score = calculate_rebound_score(o_attr)
        d_score = calculate_rebound_score(d_attr)

        off_mod = game_state["team_attributes"][off_team]["rebound_modifier"]
        def_mod = game_state["team_attributes"][def_team]["rebound_modifier"]
        bias = def_mod - off_mod
        def_prob = 0.75 + bias
        def_prob = min(0.95, max(0.55, def_prob))  # Clamp

        # Adjust weights
        total_score = d_score + o_score
        d_weight = (d_score / total_score) if total_score else 0.5
        o_weight = 1 - d_weight

        d_weight += (def_prob - 0.5)
        o_weight -= (def_prob - 0.5)

        # Clamp again to valid probabilities
        d_weight = min(0.95, max(0.05, d_weight))
        if defense_call == "Zone":
            d_weight *= 0.9
        o_weight = 1 - d_weight

        rebound_team = def_team if random.random() < d_weight else off_team
        rebounder = d_rebounder if rebound_team == def_team else o_rebounder
        stat = "DREB" if rebound_team == def_team else "OREB"
        game_state["last_rebound"] = stat  # stat is either "DREB" or "OREB"
        record_stat(rebounder, stat) #confirmed

        text += f"...{rebounder} grabs the rebound."
        possession_flips = (rebound_team != off_team)
        
        if stat == "OREB":
            attempt_putback = random.random() < 0.65
            
            if attempt_putback:
                text += (f"... he attempts the putback...")

                # Basic putback shot calculation (we'll refine later)
                attrs = game_state["players"][off_team][rebounder]["attributes"]
                shot_score = (
                    attrs["SC"] * 0.6 +
                    attrs["CH"] * 0.2 +
                    attrs["MO"] * 0.2
                ) * random.randint(1, 6)

                defender_pos = random.choice(["C", "C", "C", "C", "C", "PF", "PF", "PF", "SF", "SF", "SG", "PG"])
                defender = game_state["players"][def_team][defender_pos]
                defense_attrs = game_state["players"][def_team][defender_pos]["attributes"]
                defense_penalty = (defense_attrs["ID"] * 0.8 + defense_attrs["IQ"] * 0.1 + defense_attrs["CH"] * 0.1) * random.randint(1, 6)
                shot_score -= defense_penalty * 0.2
                made = shot_score >= game_state["team_attributes"][off_team]["shot_threshold"]

                # Track stats
                record_stat(rebounder, "FGA") #confirmed
                if made:
                    record_stat(rebounder, "FGM") #confirmed
                    points = 2
                    game_state["score"][off_team] += points
                    game_state["points_by_quarter"][off_team][game_state["quarter"] - 1] += points
                    text += f" and he scores!"
                    possession_flips = True
                else:
                    # Use dynamic logic for the missed putback
                    putback_result = resolve_offensive_rebound_loop(game_state, off_team, def_team, rebounder)
                    # Add result text and update turn metadata
                    text += f" and misses the putback. {putback_result['text']}"
                    possession_flips = putback_result["possession_flips"]
                    time_elapsed += putback_result["time_elapsed"]
        else:
            game_state["last_rebounder"] = rebounder
            if random.random() < get_fast_break_chance(game_state):
                game_state["offensive_state"] = "FAST_BREAK"
            else:
                game_state["offensive_state"] = "HCO"
    
    tempo = game_state["strategy_calls"][off_team]["tempo_call"]
    time_elapsed += get_time_elapsed(tempo)

    return {
        "result_type": "MAKE" if made else "MISS",
        "ball_handler": shooter_pos,
        "screener": screener_pos,
        "passer": passer_pos,
        "defender": defender_pos,
        "text": text,
        "possession_flips": possession_flips,
        "start_coords": {shooter_pos: {"x": 72, "y": 25}},
        "end_coords": {shooter_pos: {"x": 82, "y": 23}},
        "time_elapsed": time_elapsed
    }

def resolve_turnover(roles, game_state, turnover_type="DEAD BALL"):
    team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    bh_pos = roles["ball_handler"]
    ball_handler = game_state["players"][team][bh_pos]
    defender_pos = roles.get("defender", "")
    defender = game_state["players"][def_team][defender_pos]
    record_stat(ball_handler, "TO") #confirmed

    if turnover_type == "STEAL":
        record_stat(defender, "STL") #confirmed
        if random.random() < get_fast_break_chance(game_state):
            game_state["offensive_state"] = "FAST_BREAK"
        else:
            game_state["offensive_state"] = "HCO"
        game_state["last_stealer"] = defender_pos
        game_state["last_rebound"] = ""
        text = f"{defender['last_name']} jumps the pass and takes it the other way!"
    else:
        game_state["offensive_state"] = "HCO"
        text = f"{ball_handler} throws it out of bounds."
        game_state["offensive_state"] = "HCO"

    return {
        "result_type": turnover_type,
        "ball_handler": ball_handler,
        "text": text,
        "start_coords": {ball_handler: {"x": 72, "y": 25}},
        "end_coords": {ball_handler: {"x": 68, "y": 25}},
        "time_elapsed": random.randint(3, 8),
        "possession_flips": True  # Let the turn loop handle the flip
    }


def resolve_foul(roles, game_state):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    foul_team = game_state["foul_team"]
    
    bh_pos = roles["ball_handler"]
    ball_handler = game_state["players"][off_team][bh_pos]
    defender_pos = roles.get("defender", "")
    foul_pos = roles["foul_player"]
    foul_player = game_state["players"][foul_team][foul_pos]
    
    shooter = roles["shooter"]
    tempo = game_state["strategy_calls"][off_team]["tempo_call"]
    time_elapsed = get_time_elapsed(tempo)

    # Track the foul
    record_stat(foul_player, "F")
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
    return {
        "result_type": "FOUL",
        "ball_handler": ball_handler,
        "screener": roles["screener"],
        "passer": roles["passer"],
        "defender": defender_pos,
        "foul_type": foul_type,
        "text": text,
        "possession_flips": False,
        "start_coords": {ball_handler: {"x": 72, "y": 25}},
        "end_coords": {ball_handler: {"x": 72, "y": 25}},
        "time_elapsed": time_elapsed
    }

#HELPER FUNCTIONS
def get_fast_break_chance(game_state):
    team = game_state["defense_team"]
    level = game_state["strategy_settings"][team]["fast_break"]
    return [0.0, 0.25, 0.5, 0.75, 1.0][level]

def record_stat(player_obj, stat, amount=1):
    player_obj["stats"]["game"][stat] += amount

    if stat in ["FGM", "3PTM", "FTM"]:
        s = player_obj["stats"]["game"]
        s["PTS"] = (2 * s["FGM"]) + s["3PTM"] + s["FTM"]





def weighted_random_from_dict(weight_dict):
    total = sum(weight_dict.values())
    roll = random.uniform(0, total)
    upto = 0
    for key, weight in weight_dict.items():
        if upto + weight >= roll:
            return key
        upto += weight
    return random.choice(list(weight_dict.keys()))  # fallback

def generate_pass_chain(game_state, shooter_pos):
    positions = ["PG", "SG", "SF", "PF", "C"]
    chain = ["PG"]  # Start with PG
    last_added = "PG"

    tempo = game_state["strategy_calls"][game_state["offense_team"]]["tempo_call"]
    if tempo == "slow":
        num_passes = 3
    elif tempo == "fast":
        num_passes = 1
    else:
        num_passes = 2

    while len(chain) < num_passes:
        candidate = random.choice(positions)
        if candidate != last_added and candidate != shooter_pos:
            chain.append(candidate)
            last_added = candidate

    chain.append(shooter_pos)  # Shooter always last
    return chain

def calculate_gravity_score(attrs):
    return (
        attrs["SH"] * 0.3 +
        attrs["SC"] * 0.3 +
        attrs["MO"] * 0.4
    )


def calculate_screen_score(screen_attrs):
    """
    Calculates screen effectiveness score using weighted attributes:
    ST (0.5), AG (0.2), IQ (0.2), CH (0.1) scaled by RNG 1–6
    """
    base_score = (
        screen_attrs["ST"] * 0.5 +
        screen_attrs["AG"] * 0.2 +
        screen_attrs["IQ"] * 0.2 +
        screen_attrs["CH"] * 0.1
    )
    return base_score * random.randint(1, 6)


def choose_rebounder(rebounders, side):
    players = list(rebounders[side].keys())
    weights = list(rebounders[side].values())
    return random.choices(players, weights=weights, k=1)[0]

def calculate_rebound_score(player_attr):
    """
    Calculate rebound score based on attributes:
    - RB (50%), ST (30%), IQ (10%), CH (10%)
    - Scaled by a random multiplier between 1 and 6
    """
    base_score = (
        player_attr["RB"] * 0.5 +
        player_attr["ST"] * 0.3 +
        player_attr["IQ"] * 0.1 +
        player_attr["CH"] * 0.1
    )
    return base_score * random.randint(1, 6)

def select_weighted_playcall(user_settings):
    playcall_names = list(user_settings.keys())
    weights = list(user_settings.values())
    return random.choices(playcall_names, weights=weights, k=1)[0]

def get_time_elapsed(tempo_call):
    if tempo_call == "slow":
        return int(max(5, min(35, random.gauss(22, 6))))
    elif tempo_call == "normal":
        return int(max(5, min(35, random.gauss(15, 6))))
    elif tempo_call == "fast":
        return int(max(4, min(15, random.gauss(8, 3))))
    else:
        return int(max(5, min(35, random.gauss(12, 6))))  # Fallback

def get_random_positions(pass_count):
    return {
        "turnover": random.choice(TURNOVER_CALC_DICT[pass_count]),
        "o_foul": random.choice(POSITION_LIST),
        "d_foul": random.choice(POSITION_LIST)
    }

def get_team_thresholds(game_state):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]

    off_attr = game_state["team_attributes"][off_team]
    def_attr = game_state["team_attributes"][def_team]

    return {
        "turnover_threshold": off_attr.get("turnover_threshold", 10),
        "d_foul_threshold": def_attr.get("foul_threshold", 10),
        "o_foul_threshold": off_attr.get("foul_threshold", 10)
    }

def calculate_foul_turnover(game_state, positions, thresholds, roles):
    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]
    roles["foul_player"] = None
    bh_pos = roles["ball_handler"]
    ball_handler = game_state["players"][off_team][bh_pos]
    defense_call = game_state["defense_playcall"]

    # === Defensive Foul ===
    d_pos = positions["d_foul"]
    d_foul_player = game_state["players"][def_team][d_pos]
    d_attr = d_foul_player["attributes"]

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
    o_foul_player = game_state["players"][off_team][o_pos]
    o_attr = o_foul_player["attributes"]

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
    turnover_player = game_state["players"][off_team][t_pos]
    t_attr = turnover_player["attributes"]

    bh_score = (
        t_attr["BH"] * 0.5 +
        t_attr["AG"] * 0.2 +
        t_attr["IQ"] * 0.2 +
        t_attr["CH"] * 0.1
    ) * random.randint(1, 6)

    def_mod_player = game_state["players"][def_team][t_pos]
    def_mod_attr = def_mod_player["attributes"]
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

    print(f"Turnover → {turnover_player['first_name']} {turnover_player['last_name']} vs {def_mod_player['first_name']} {def_mod_player['last_name']}: score={round(turnover_score, 2)} vs threshold={thresholds['turnover_threshold']} | flag={is_turnover}")

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

def apply_help_defense_if_triggered(game_state, playcall, is_three, defender_pos, shot_score):
    """
    Determines if help defense is triggered and applies a penalty to the shot_score.
    Returns: updated_shot_score, help_defender (or None), help_defense_penalty
    """
    if is_three:
        return shot_score, None, 0

    off_team = game_state["offense_team"]
    def_team = game_state["defense_team"]

    base_help_chance_by_playcall = {
        "Attack": 0.70,
        "Inside": 0.20,
        "Set": 0.20,
        "Base": 0.30,
        "Freelance": 0.30,
        "Outside": 0.0
    }

    help_playcall = "Attack" if playcall == "Set" else playcall
    base_help_chance = base_help_chance_by_playcall.get(help_playcall, 0)

    # Adjust for aggression
    aggression = game_state["strategy_calls"][def_team]["aggression_call"]
    if aggression == "passive":
        base_help_chance += 0.20
    elif aggression == "aggressive":
        base_help_chance -= 0.20
    base_help_chance = max(0, min(1, base_help_chance))

    if random.random() >= base_help_chance:
        return shot_score, None, 0

    possible_helpers = [
        pos for pos in game_state["players"][def_team]
        if pos != defender_pos
    ]
    help_pos = random.choice(possible_helpers)
    help_defender = game_state["players"][def_team][help_pos]
    help_attrs = game_state["players"][def_team][help_pos]["attributes"]

    if help_playcall == "Attack":
        help_score = (
            help_attrs["ID"] * 0.2 +
            help_attrs["OD"] * 0.2 +
            help_attrs["AG"] * 0.4 +
            help_attrs["IQ"] * 0.1 +
            help_attrs["CH"] * 0.1
        ) * random.randint(1, 6)
    else:
        help_score = (
            help_attrs["AG"] * 0.2 +
            help_attrs["IQ"] * 0.4 +
            help_attrs["CH"] * 0.4
        ) * random.randint(1, 6)

    penalty = help_score * 0.15
    return shot_score - penalty, help_defender, penalty


def determine_rebounder(game_state, off_team, def_team):
    rebounder_dict = {
        "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
        "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
    }

    o_pos = choose_rebounder(rebounder_dict, "offense")
    d_pos = choose_rebounder(rebounder_dict, "defense")
    o_rebounder = game_state["players"][off_team][o_pos]
    d_rebounder = game_state["players"][def_team][d_pos]

    o_attr = game_state["players"][off_team][o_rebounder]["attributes"]
    d_attr = game_state["players"][def_team][d_rebounder]["attributes"]

    o_score = calculate_rebound_score(o_attr)
    d_score = calculate_rebound_score(d_attr)

    off_mod = game_state["team_attributes"][off_team]["rebound_modifier"]
    def_mod = game_state["team_attributes"][def_team]["rebound_modifier"]
    bias = def_mod - off_mod
    def_prob = min(0.95, max(0.55, 0.75 + bias))

    total_score = d_score + o_score
    d_weight = (d_score / total_score) if total_score else 0.5
    o_weight = 1 - d_weight
    d_weight += (def_prob - 0.5)
    d_weight = min(0.95, max(0.05, d_weight))
    o_weight = 1 - d_weight

    new_team = def_team if random.random() < d_weight else off_team
    new_rebounder = d_rebounder if new_team == def_team else o_rebounder
    new_stat = "DREB" if new_team == def_team else "OREB"

    return new_rebounder, new_team, new_stat


def choose_rebounder(rebounders, side):
    players = list(rebounders[side].keys())
    weights = list(rebounders[side].values())
    return random.choices(players, weights=weights, k=1)[0]

def calculate_rebound_score(player_attr):
    base_score = (
        player_attr["RB"] * 0.5 +
        player_attr["ST"] * 0.3 +
        player_attr["IQ"] * 0.1 +
        player_attr["CH"] * 0.1
    )
    return base_score * random.randint(1, 6)

def resolve_offensive_rebound_loop(game_state, off_team, def_team, rebounder):
    total_time = 0
    text_log = ""
    
    while True:
        # 65% chance to shoot, else kick out
        if random.random() > 0.65:
            text_log += f"{rebounder} kicks it out."
            return {
                "text": text_log,
                "possession_flips": False,
                "time_elapsed": total_time
            }

        # attempt putback
        text_log += f"{rebounder} goes back up..."
        attrs = game_state["players"][off_team][rebounder]["attributes"]
        shot_score = (
            attrs["SC"] * 0.6 +
            attrs["CH"] * 0.2 +
            attrs["MO"] * 0.2
        ) * random.randint(1, 6)
        time_elapsed = random.randint(2, 5)
        total_time += time_elapsed

        # contested by random defender
        defender_pos = random.choice(["C", "C", "C", "PF", "PF", "SF", "SF", "SG", "PG"])
        defender = game_state["players"][def_team][defender_pos]
        defense_attrs = game_state["players"][def_team][defender]["attributes"]
        defense_penalty = (
            defense_attrs["ID"] * 0.8 + 
            defense_attrs["IQ"] * 0.1 + 
            defense_attrs["CH"] * 0.1
        ) * random.randint(1, 6)
        shot_score -= defense_penalty * 0.2

        made = shot_score >= game_state["team_attributes"][off_team]["shot_threshold"]
        record_stat(rebounder, "FGA") #confirmed

        if made:
            record_stat(rebounder, "FGM") #confirmed
            points = 2
            game_state["score"][off_team] += points
            game_state["points_by_quarter"][off_team][game_state["quarter"] - 1] += points
            text_log += f" and he scores!"
            return {
                "text": text_log,
                "possession_flips": True,
                "time_elapsed": total_time
            }

        # shot missed — determine rebound
        new_rebounder, new_team, new_stat = determine_rebounder(game_state, off_team, def_team)
        record_stat(new_rebounder, new_stat) #confirmed
        text_log += f" but misses the shot. {new_rebounder} grabs the rebound."

        if new_team != off_team:
            return {
                "text": text_log,
                "possession_flips": True,
                "time_elapsed": total_time
            }

        # else: new offensive rebound, repeat loop
        rebounder = new_rebounder

#POST-GAME
def calculate_team_stats(game_state):
    team_stats = {}
    stat_keys = ["FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "PTS",
                 "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S"]

    for team, player_dict in game_state["box_score"].items():
        team_totals = {k: 0 for k in stat_keys}
        for player_stats in player_dict.values():
            if isinstance(player_stats, dict):
                for k in stat_keys:
                    team_totals[k] += player_stats.get(k, 0)
        team_stats[team] = team_totals

    return team_stats

def print_scouting_report(data):
    for team in data:
        print(f"\n=== {team.upper()} SCOUTING REPORT ===")

        print("\nOffensive Playcall Usage & Success:")
        for call, val in data[team]["offense"]["Playcalls"].items():
            print(f"{call.ljust(10)} — Used: {val['used']}, Success: {val['success']}")

        print("\nFast Break:")
        fb_used = data[team]["offense"]["Fast_Break_Entries"]
        fb_success = data[team]["offense"]["Fast_Break_Success"]
        print(f"Entries: {fb_used}, Success: {fb_success}")

        print("\nDefensive Success:")
        for def_type, val in data[team]["defense"].items():
            print(f"{def_type.ljust(14)} — Used: {val['used']}, Success: {val['success']}")

#MAIN
def main(return_game_state=False):
    energy_rng_seed = 1.0  # Default for first turn
    
    # Get team documents
    lancaster_team = teams_collection.find_one({"name": "Lancaster"})
    bt_team = teams_collection.find_one({"name": "Bentley-Truman"})
    print("🔍 Checking live team names in /simulate:")


    print("🧠 Inserted teams:")
    for team in teams_collection.find({}):
        print("📁", team.get("name"))


    if not lancaster_team or not bt_team:
        raise ValueError("One or both teams not found in the database.")

    # Pull 5 player documents from Mongo based on stored IDs
    lancaster_roster = [
        players_collection.find_one({"_id": pid})
        for pid in lancaster_team["player_ids"][:5]
    ]
    bt_roster = [
        players_collection.find_one({"_id": pid})
        for pid in bt_team["player_ids"][:5]
    ]
    print(lancaster_roster)
    print(bt_roster)


    game_state = {
        "offense_team": "Lancaster",
        "defense_team": "Bentley-Truman",
        "players": {
            "Lancaster": {
                "PG": lancaster_roster[0],
                "SG": lancaster_roster[1],
                "SF": lancaster_roster[2],
                "PF": lancaster_roster[3],
                "C":  lancaster_roster[4]
            },
            "Bentley-Truman": {
                "PG": bt_roster[0],
                "SG": bt_roster[1],
                "SF": bt_roster[2],
                "PF": bt_roster[3],
                "C":  bt_roster[4]
            }
        },
        "score": {"Lancaster": 0, "Bentley-Truman": 0},
        "time_remaining": 480,
        "quarter": 1,
        "offensive_state": "HALF_COURT",
        "tempo": 2,
        "playcall": {"offense": "Base", "defense": "Man"},
        "defense_playcall": "Man",  # Add this line
        "turn_number": 17,
        "team_fouls": {
            "Lancaster": 0,
            "Bentley-Truman": 0
        },
        "free_throws": 0,
        "free_throws_remaining": 0,
        "last_ball_handler": None,
        "bonsu_active": False,
        "box_score": {
            "Lancaster": {},
            "Bentley-Truman": {}
        }
    }

    # --- After assigning game_state["players"] ---
    for team in game_state["players"]:
        for pos, player_obj in game_state["players"][team].items():
            player_obj["attributes"] = {
                k: v for k, v in player_obj.items()
                if k not in ["_id", "first_name", "last_name", "team"]
            }
            for k in list(player_obj["attributes"]):
                player_obj["attributes"][f"anchor_{k}"] = player_obj["attributes"][k]

            player_obj["stats"] = {
                "game": { stat: 0 for stat in BOX_SCORE_KEYS },
                "season": { stat: 0 for stat in BOX_SCORE_KEYS },
                "career": { stat: 0 for stat in BOX_SCORE_KEYS }
            }


    
    game_state["scouting_data"] = {
        team: {
            "offense": {
                "Fast_Break_Entries": 0,
                "Fast_Break_Success": 0,
                "Playcalls": {call: {"used": 0, "success": 0} for call in ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]},
            },
            "defense": {
                "Man": {"used": 0, "success": 0},
                "Zone": {"used": 0, "success": 0},
                "vs_Fast_Break": {"used": 0, "success": 0},
            }
        }
        for team in game_state["players"]
    }
    
    game_state["playcall_weights"] = initialize_playcall_settings()
    game_state["team_attributes"] = initialize_team_attributes()
    game_state["strategy_settings"] = initialize_strategy_settings()
    game_state["strategy_calls"] = initialize_strategy_calls()

    game_state["playcall_tracker"] = {
        team: {call: 0 for call in ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]}
        for team in game_state["players"]
    }
    game_state["defense_playcall_tracker"] = {
        team: {call: 0 for call in ["Man", "Zone"]}
        for team in game_state["players"]
    }

    game_state["points_by_quarter"] = {
        team: [0, 0, 0, 0] for team in game_state["players"]
    }

    for team in game_state["players"]:
        game_state["box_score"][team] = {}
        for pos, player_obj in game_state["players"][team].items():
            player_name = f"{player_obj['first_name']} {player_obj['last_name']}"
            game_state["box_score"][team][player_name] = {
                "FGA": 0,
                "FGM": 0,
                "3PTA": 0,
                "3PTM": 0,
                "FTA": 0,
                "FTM": 0,
                "OREB": 0,
                "DREB": 0,
                "REB": 0,
                "AST": 0,
                "STL": 0,
                "BLK": 0,
                "TO": 0,
                "F": 0,
                "MIN": 0,
                "PTS": 0,
                "DEF_A": 0,
                "DEF_S": 0,
                "HELP_D": 0,
                "SCR_A": 0,
                "SCR_S": 0,
            }

    # game_state["player_attributes"] = {}

    # # Build player_attributes from the full player objects already loaded from Mongo
    # for team in game_state["players"]:
    #     game_state["player_attributes"][team] = {}
    #     for pos, player_obj in game_state["players"][team].items():
    #         attr = {k: v for k, v in player_obj.items() if k not in ["_id", "first_name", "last_name", "team"]}
    #         for key in list(attr):  # ✅ Safe copy of keys
    #             attr[f"anchor_{key}"] = attr[key]
    #         game_state["players"][team][pos]["attributes"] = attr

    #         if not return_game_state:
    #             print(game_state["players"][team][pos]["attributes"])  # Fix player to pos


    i = 1
    for q in range(1, 5):  # quarters 1 to 4
        game_state["quarter"] = q
        recharge_amount = 0.3 if q == 3 else 0.2
        # Reset fouls at start of quarter
        for team in game_state["team_fouls"]:
            game_state["team_fouls"][team] = 0
        game_state["time_remaining"] = 480  # 8 minutes per quarter
        # Recharge NG at quarter break
        for team in game_state["players"]:
            for pos, player_obj in game_state["players"][team].items():
                player_name = f"{player_obj['first_name']} {player_obj['last_name']}"
                attr = game_state["players"][team][pos]["attributes"]
                attr["NG"] = min(1.0, round(attr["NG"] + recharge_amount, 3))

        if not return_game_state:
            print(f"\n=== Start of Q{q} ===")
        while game_state["time_remaining"] > 0:
            if not return_game_state:
                print(f"--- Turn {i} ---")
            game_state["last_ball_handler"] = game_state["players"][game_state["offense_team"]]["PG"]
            game_state["strategy_calls"] = resolve_strategy_calls(game_state)
            # for team, calls in game_state["strategy_calls"].items():
            #     print(f"{team} Tempo = {calls['tempo_call']}, Aggression = {calls['aggression_call']}")
            turn_result = resolve_turn(game_state)
            game_state["time_remaining"] = max(0, game_state["time_remaining"] - turn_result["time_elapsed"])
            
            for player in game_state["players"][game_state["offense_team"]].values():
                record_stat(player, "MIN", turn_result["time_elapsed"]) #confirmed
            for player in game_state["players"][game_state["defense_team"]].values():
                record_stat(player, "MIN", turn_result["time_elapsed"]) #confirmed

            #Energy System
            if i % 2 == 0 or i == 1:
                energy_rng_seed = random.choices(
                    [0.9, 0.95, 1.0, 1.05, 1.1],
                    weights=[1, 2, 5, 2, 1]
                )[0]
            # print(f"Turn {i} | Energy RNG: {energy_rng_seed}")
            base_decay = 0.025  # Base amount of NG lost per turn
            fatigue_mod = 1.1 if game_state["defense_playcall"] == "Man" else 0.9
            def_team = game_state["defense_team"]
            for team in [game_state["offense_team"], game_state["defense_team"]]:
                for pos, player_obj in game_state["players"][team].items():
                    player_name = f"{player_obj['first_name']} {player_obj['last_name']}"
                    attr = game_state["players"][team][pos]["attributes"]
                    endurance = attr["ND"]
                    decay = max(0.001, base_decay - (endurance / 1000))  # Prevent negative decay
                    decay = max(0.001, decay * energy_rng_seed)  # Apply seeded RNG
                     # ✅ Only apply to defenders
                    if team == def_team:
                        decay *= fatigue_mod
                    attr["NG"] = max(0.1, round(attr["NG"] - decay, 3))  # Floor at 0.1
            recalculate_energy_scaled_attributes(game_state)

            minutes = game_state["time_remaining"] // 60
            seconds = game_state["time_remaining"] % 60
            clock_display = f"{minutes}:{seconds:02d}"
            if not return_game_state:
                print()
                print(turn_result.get("text", "No description"))
                print()
                print(f"Score: {game_state['score']}")
                print(f"Clock: {clock_display} // Q{game_state['quarter']}")
                print(f"Team Fouls: {game_state['team_fouls']}")
                # if turn_result.get("possession_flips"):
                #     print("Possession changes.")
                # else:
                #     print("Possession retained.")
                print()
            if turn_result.get("possession_flips", False):
                game_state["offense_team"], game_state["defense_team"] = (
                    game_state["defense_team"],
                    game_state["offense_team"]
                )
            i += 1

        if not return_game_state:
            print(f"=== End of Q{q} ===")
    
    for team in game_state["box_score"]:
        for player in game_state["box_score"][team]:
            raw_seconds = game_state["box_score"][team][player]["MIN"]
            game_state["box_score"][team][player]["MIN"] = int(raw_seconds / 60)

    # --- Overtime if tied after regulation ---
    while game_state["score"]["Lancaster"] == game_state["score"]["Bentley-Truman"]:
        game_state["quarter"] += 1
        for team in game_state["points_by_quarter"]:
            game_state["points_by_quarter"][team].append(0)

        game_state["time_remaining"] = 240  # 4 minutes for OT

        if not return_game_state:
            print(f"\n=== Start of Overtime Q{game_state['quarter']} ===")

        while game_state["time_remaining"] > 0:
            if not return_game_state:
                print(f"--- Turn {i} (OT) ---")
            turn_result = resolve_turn(game_state)
            game_state["time_remaining"] = max(0, game_state["time_remaining"] - turn_result["time_elapsed"])

            for player in game_state["players"][game_state["offense_team"]].values():
                record_stat(player, "MIN", turn_result["time_elapsed"]) #confirmed
            for player in game_state["players"][game_state["defense_team"]].values():
                record_stat(player, "MIN", turn_result["time_elapsed"]) #confirmed

            # Energy and movement logic remains unchanged
            if i % 2 == 0 or i == 1:
                energy_rng_seed = random.choices([0.9, 0.95, 1.0, 1.05, 1.1], weights=[1, 2, 5, 2, 1])[0]
            base_decay = 0.025
            for team in [game_state["offense_team"], game_state["defense_team"]]:
                for pos, player_obj in game_state["players"][team].items():
                    player_name = f"{player_obj['first_name']} {player_obj['last_name']}"
                    attr = game_state["players"][team][pos]["attributes"]
                    endurance = attr["ND"]
                    decay = max(0.001, base_decay - (endurance / 1000))
                    decay = max(0.001, decay * energy_rng_seed)
                    attr["NG"] = max(0.1, round(attr["NG"] - decay, 3))
            recalculate_energy_scaled_attributes(game_state)

            minutes = game_state["time_remaining"] // 60
            seconds = game_state["time_remaining"] % 60
            clock_display = f"{minutes}:{seconds:02d}"
            if not return_game_state:
                print(turn_result.get("text", "No description"))
                print(f"Clock: {clock_display}")
                print(f"Quarter: Q{game_state['quarter']}")
                print(f"Score: {game_state['score']}")
                print(f"Team Fouls: {game_state['team_fouls']}")
                print("Possession changes." if turn_result.get("possession_flips") else "Possession retained.")
                print()

            if turn_result.get("possession_flips", False):
                game_state["offense_team"], game_state["defense_team"] = (
                    game_state["defense_team"],
                    game_state["offense_team"]
                )
            i += 1

        if not return_game_state:
            print(f"=== End of Overtime Q{game_state['quarter']} ===")

    
    if not return_game_state:
        print(f"\n=== Box Score After {i} Turns ===")
    for team in game_state["box_score"]:
        team_score = game_state["score"][team]
        if not return_game_state:
            print(f"\n{team} {team_score}")
        for player, stats in game_state["box_score"][team].items():
            # Recalculate PTS if you're not auto-updating it in record_stat()
            stats["PTS"] = (2 * stats["FGM"]) + stats["3PTM"] + stats["FTM"]
            stats["REB"] = stats["OREB"] + stats["DREB"]
            if not return_game_state:
                print(f"{player}: {stats}")

    if not return_game_state:
        print(f"\n=== Team Points by Quarter ===")
        for team, q_points in game_state["points_by_quarter"].items():
            print(f"{team}: Q1={q_points[0]}  Q2={q_points[1]}  Q3={q_points[2]}  Q4={q_points[3]}  Total={sum(q_points)}")

    # Reset all player attributes to anchor values after the game
    for team in game_state["players"]:
        for pos, player in game_state["players"][team].items():
            attrs = player["attributes"]
            for key in list(attrs):  # Always use list() in case we modify keys during iteration
                if key.startswith("anchor_"):
                    base_attr = key.replace("anchor_", "")
                    attrs[base_attr] = attrs[key]

            # Reset energy to full
            attrs["NG"] = 1.0


    if not return_game_state:
        print(f"\n=== Team Stats Summary ===")
    team_stats = calculate_team_stats(game_state)
    stat_keys = ["FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "PTS",
                    "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S"]

    # Print header
    column_width = max(len(k) for k in stat_keys) + 2
    header = "TEAM".ljust(18) + "".join(k.rjust(column_width) for k in stat_keys)
    if not return_game_state:
        print(header)
        print("-" * len(header))

        for team, stats in team_stats.items():
            row = team.ljust(18) + "".join(str(stats.get(k, 0)).rjust(column_width) for k in stat_keys)
            print(row)

    # if not return_game_state:
    #     print_scouting_report(game_state["scouting_data"])



    if return_game_state:
        return game_state

# if __name__ == "__main__":
#     game_state = main(return_game_state=False)

# if __name__ == "__main__":
#     # This starts the FastAPI server when running locally or on Railway
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)


# if __name__ == "__main__":
    # aggregates = initialize_aggregates()

    # for sim in range(100):
    #     game_state = main(return_game_state=True)
    #     collect_simulation_stats(game_state, aggregates)

    # with open("aggregated_stats.json", "w") as f:
    #     json.dump(aggregates, f, indent=2)


