import random

def weighted_random_from_dict(weight_dict):
    total = sum(weight_dict.values())
    roll = random.uniform(0, total)
    upto = 0
    for key, weight in weight_dict.items():
        if upto + weight >= roll:
            return key
        upto += weight
    return random.choice(list(weight_dict.keys()))  # fallback

def apply_help_defense_if_triggered(game_state, playcall, is_three, defender, shot_score):
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

    defender_pos = next(
        (pos for pos, obj in game_state["players"][def_team].items() if obj == defender),
        None
    )

    possible_helpers = [
        pos for pos in game_state["players"][def_team]
        if pos != defender_pos
    ]
    help_pos = random.choice(possible_helpers)
    help_defender = game_state["players"][def_team][help_pos]
    help_attrs = help_defender.attributes

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

def get_fast_break_chance(game_state):
    team = game_state["defense_team"]
    level = game_state["strategy_settings"][team]["fast_break"]
    return [0.0, 0.25, 0.5, 0.75, 1.0][level]

def get_time_elapsed(tempo_call):
    if tempo_call == "slow":
        return int(max(5, min(35, random.gauss(22, 6))))
    elif tempo_call == "normal":
        return int(max(5, min(35, random.gauss(15, 6))))
    elif tempo_call == "fast":
        return int(max(4, min(15, random.gauss(8, 3))))
    else:
        return int(max(5, min(35, random.gauss(12, 6))))  # Fallback

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
        attrs = rebounder.attributes
        shot_score = (
            attrs["SC"] * 0.6 +
            attrs["CH"] * 0.2 +
            attrs["IQ"] * 0.2
        ) * random.randint(1, 6)
        time_elapsed = random.randint(2, 5)
        total_time += time_elapsed

        # contested by random defender
        defender_pos = random.choice(["C", "C", "C", "PF", "PF", "SF", "SF", "SG", "PG"])
        defender = game_state["players"][def_team][defender_pos]
        defense_attrs = defender.attributes
        defense_penalty = (
            defense_attrs["ID"] * 0.8 + 
            defense_attrs["IQ"] * 0.1 + 
            defense_attrs["CH"] * 0.1
        ) * random.randint(1, 6)
        shot_score -= defense_penalty * 0.2

        made = shot_score >= game_state["team_attributes"][off_team]["shot_threshold"]
        rebounder.record_stat("FGA")

        if made:
            rebounder.record_stat("FGM")
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
        new_rebounder.record_stat(new_stat)
        text_log += f" but misses the shot. {new_rebounder} grabs the rebound."

        if new_team != off_team:
            return {
                "text": text_log,
                "possession_flips": True,
                "time_elapsed": total_time
            }

        # else: new offensive rebound, repeat loop
        rebounder = new_rebounder

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

def clean_mongo_ids(doc: dict) -> dict:
    """
    Converts MongoDB ObjectId fields to strings so FastAPI can serialize them.
    """
    if "_id" in doc and hasattr(doc["_id"], "__str__"):
        doc["_id"] = str(doc["_id"])
    return doc

def get_name_safe(p):

    if isinstance(p, dict):
        return p.get("name", "")
    return getattr(p, "name", "")

def default_rebounder_dict():
    return {
        "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
        "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
    }

def determine_rebounder(game_state, off_team, def_team):
    rebounder_dict = {
        "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
        "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
    }

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