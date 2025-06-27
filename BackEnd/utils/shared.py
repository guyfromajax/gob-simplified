import random
from BackEnd.constants import TURNOVER_CALC_DICT, POSITION_LIST

def weighted_random_from_dict(weight_dict: dict) -> str:
    if not weight_dict:
        raise ValueError("weighted_random_from_dict received an empty dict")

    total = sum(weight_dict.values())
    if total == 0:
        raise ValueError("All weights are zero in weighted_random_from_dict")

    rand_val = random.uniform(0, total)
    cumulative = 0
    for key, weight in weight_dict.items():
        cumulative += weight
        if rand_val <= cumulative:
            return key

    # fallback — should never hit if weights are valid
    return random.choice(list(weight_dict.keys()))


def apply_help_defense_if_triggered(game, playcall, is_three, defender, shot_score):
    """
    Determines if help defense is triggered and applies a penalty to the shot_score.
    Returns: updated_shot_score, help_defender (or None), help_defense_penalty
    """
    if is_three:
        return shot_score, None, 0

    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

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
    aggression = def_team.strategy_calls["aggression_call"]
    if aggression == "passive":
        base_help_chance += 0.20
    elif aggression == "aggressive":
        base_help_chance -= 0.20
    base_help_chance = max(0, min(1, base_help_chance))

    if random.random() >= base_help_chance:
        return shot_score, None, 0

    defender_pos = get_player_position(def_lineup, defender)

    possible_helpers = [pos for pos in def_lineup if pos != defender_pos]
    help_pos = random.choice(possible_helpers)
    help_defender = def_lineup[help_pos]
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

def get_fast_break_chance(game):
    game_state = game.game_state
    def_team = game.defense_team
    level = def_team.strategy_settings["fast_break"]
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

def resolve_offensive_rebound_loop(game, rebounder):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    total_time = 0
    text_log = ""
    turns = 0
    while True:

        # attempt putback
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
        defender = def_team.lineup[defender_pos]
        defense_attrs = defender.attributes
        defense_penalty = (
            defense_attrs["ID"] * 0.8 + 
            defense_attrs["IQ"] * 0.1 + 
            defense_attrs["CH"] * 0.1
        ) * random.randint(1, 6)
        shot_score -= defense_penalty * 0.2

        made = shot_score >= off_team.team_attributes["shot_threshold"]
        rebounder.record_stat("FGA")
        # print(f"{get_name_safe(rebounder)} attempts an offensive rebound shot")

        if made:
            rebounder.record_stat("FGM")
            points = 2
            record_team_points(game, off_team, points)
            text_log += f" and he scores!"
            return {
                "text": text_log,
                "possession_flips": True,
                "time_elapsed": total_time
            }

        # shot missed — determine rebound
        new_rebounder, new_team, new_stat = determine_rebounder(game)
        new_rebounder.record_stat(new_stat)
        # print(f"+1 rebound for {get_name_safe(new_rebounder)} / utils/shared - resolve_offensive_rebound_loop")
        text_log += f" but misses the shot. {new_rebounder} grabs the rebound."

        if new_team != off_team:
            return {
                "text": text_log,
                "possession_flips": True,
                "time_elapsed": total_time
            }

        # else: new offensive rebound, repeat loop
        rebounder = new_rebounder
        if random.random() > 0.65:
            text_log += f"{get_name_safe(rebounder)} kicks it out."
            return {
                "text": text_log,
                "possession_flips": False,
                "time_elapsed": total_time
            }
        
        if turns > 4:
            text_log += f"{get_name_safe(rebounder)} kicks it out."
            return {
                "text": text_log,
                "possession_flips": False,
                "time_elapsed": total_time
            }
        
        turns += 1

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

def generate_pass_chain(game, shooter_pos):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    positions = ["PG", "SG", "SF", "PF", "C"]
    chain = ["PG"]  # Start with PG
    last_added = "PG"

    tempo = off_team.strategy_calls["tempo_call"]
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

def determine_rebounder(game):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)
    rebounder_dict = {
        "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
        "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
    }

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

    total_score = d_score + o_score
    d_weight = (d_score / total_score) if total_score else 0.5
    o_weight = 1 - d_weight
    d_weight += (def_prob - 0.5)
    d_weight = min(0.95, max(0.05, d_weight))
    o_weight = 1 - d_weight

    new_team = def_team if random.random() < d_weight else off_team
    new_rebounder = d_rebounder if new_team == def_team else o_rebounder
    new_stat = "DREB" if new_team == def_team else "OREB"
    # new_rebounder.record_stat(new_stat)
    # print(f"+1 rebound for {get_name_safe(new_rebounder)} / utils/shared - determine_rebounder")

    return new_rebounder, new_team, new_stat

def get_team_thresholds(game):
    
    game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(game)

    off_attr = off_team.team_attributes
    def_attr = def_team.team_attributes

    return {
        "turnover_threshold": off_attr.get("turnover_threshold", 10),
        "d_foul_threshold": def_attr.get("foul_threshold", 10),
        "o_foul_threshold": off_attr.get("foul_threshold", 10)
    }

def get_foul_and_turnover_positions(pass_count):
    return {
        "turnover": random.choice(TURNOVER_CALC_DICT[pass_count]),
        "o_foul": random.choice(POSITION_LIST),
        "d_foul": random.choice(POSITION_LIST)
    }

def get_player_position(team_lineup, player_obj):
    return next((pos for pos, p in team_lineup.items() if p == player_obj), None)

def get_quarter_index_from_game(game):
    return game.game_state["quarter"] - 1

def calculate_rebound_score(player):
    attr = player.attributes
    return attr["RB"] * 0.5 + attr["ST"] * 0.3 + attr["AG"] * 0.2

def record_team_points(game, team, points):
    """
    Updates total game score and per-quarter score for the given team.
    
    Parameters:
    - game: GameManager object
    - team: TeamManager object (e.g., game.offense_team)
    - points: int, number of points to add
    """
    game.score[team.name] += points
    quarter_index = game.game_state["quarter"] - 1
    team.points_by_quarter[quarter_index] += points

def unpack_game_context(game):
    
    return (
        game.game_state,
        game.offense_team,
        game.defense_team,
        game.offense_team.lineup,
        game.defense_team.lineup,
    )

def summarize_game_state(game):

    return {
        "final_score": game.score,
        "points_by_quarter": game.game_state["points_by_quarter"],
        "box_score": game.get_box_score(),
        "scouting": {
            game.home_team.name: game.home_team.scouting_data,
            game.away_team.name: game.away_team.scouting_data
        },
        "team_totals": game.team_totals
    }

def check_defensive_foul(self, defender, is_three):
    """
    Returns True if a defensive foul is committed during a shot attempt.
    """
    if not defender:
        return False  # No defender, no foul

    attrs = defender.attributes
    discipline = attrs.get("ND", 5)  # ND = "No Dumb Fouls"

    # Base foul rate: higher on 3pt shots, but reduced by discipline
    base_foul_chance = 0.06 if is_three else 0.045
    foul_chance = max(0.01, base_foul_chance - (discipline * 0.0045))

    return random.random() < foul_chance

def calculate_gravity_score(attrs):
    return (
        attrs["SH"] * 0.3 +
        attrs["SC"] * 0.3 +
        attrs["IQ"] * 0.4
    )