import random
import json
from BackEnd.db import players_collection, teams_collection
from BackEnd.models.player import Player
from BackEnd.models.game_manager import GameManager
from BackEnd.constants import (
    ALL_ATTRS,
    BOX_SCORE_KEYS,
    PLAYCALL_ATTRIBUTE_WEIGHTS,
    THREE_POINT_PROBABILITY,
    BLOCK_PROBABILITY,
    MALLEABLE_ATTRS,
    STRATEGY_CALL_DICTS,
    TEMPO_PASS_DICT,
    TURNOVER_CALC_DICT,
    POSITION_LIST,
)
from BackEnd.utils.shared import (
    calculate_screen_score,
    choose_rebounder,
    calculate_rebound_score,
    get_fast_break_chance,
    get_time_elapsed,
    apply_help_defense_if_triggered,
    resolve_offensive_rebound_loop,
    weighted_random_from_dict,
    generate_pass_chain,
    get_name_safe,
    default_rebounder_dict
)

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
        attr = player_obj.attributes
        ng = attr["NG"]
        for key in MALLEABLE_ATTRS:
            anchor_val = attr[f"anchor_{key}"]
            attr[key] = int(anchor_val * ng)


    return event_type

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
            attr = game_state["players"][team][pos].attributes
            ng = attr["NG"]
            for key in MALLEABLE_ATTRS:
                anchor_val = attr[f"anchor_{key}"]
                attr[key] = int(anchor_val * ng)

#RESOLVE FUNCTIONS

def calculate_gravity_score(attrs):
    return (
        attrs["SH"] * 0.3 +
        attrs["SC"] * 0.3 +
        attrs["IQ"] * 0.4
    )

def select_weighted_playcall(user_settings):
    playcall_names = list(user_settings.keys())
    weights = list(user_settings.values())
    return random.choices(playcall_names, weights=weights, k=1)[0]


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
    ball_handler = roles["ball_handler"]
    defense_call = game_state["defense_playcall"]

    # === Defensive Foul ===
    d_pos = positions["d_foul"]
    d_foul_player = game_state["players"][def_team][d_pos]
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
    o_foul_player = game_state["players"][off_team][o_pos]
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
    turnover_player = game_state["players"][off_team][t_pos]
    t_attr = turnover_player.attributes

    bh_score = (
        t_attr["BH"] * 0.5 +
        t_attr["AG"] * 0.2 +
        t_attr["IQ"] * 0.2 +
        t_attr["CH"] * 0.1
    ) * random.randint(1, 6)

    def_mod_player = game_state["players"][def_team][t_pos]
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

    print(f"Turnover → {get_name_safe(turnover_player)} vs {get_name_safe(def_mod_player)}: score={round(turnover_score, 2)} vs threshold={thresholds['turnover_threshold']} | flag={is_turnover}")

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

def build_box_score_from_player_stats(game_state):
    box_score = {}

    for team in game_state["players"]:
        box_score[team] = {}
        for pos, player in game_state["players"][team].items():
            name = player.get_name()
            box_score[team][name] = dict(player.stats["game"])  # Deep copy
    return box_score


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

def run_simulation(home_team, away_team, home_players, away_players, turns=1):
    gm = GameManager(home_team, away_team, home_players, away_players)

    for _ in range(turns):
        gm.simulate_turn()

    return gm.to_dict()


#MAIN
# def main(return_game_state=False):
#     energy_rng_seed = 1.0  # Default for first turn
    
#     # Get team documents
#     lancaster_team = teams_collection.find_one({"name": "Lancaster"})
#     bt_team = teams_collection.find_one({"name": "Bentley-Truman"})
#     print("🔍 Checking live team names in /simulate:")


#     print("🧠 Inserted teams:")
#     for team in teams_collection.find({}):
#         print("📁", team.get("name"))


#     if not lancaster_team or not bt_team:
#         raise ValueError("One or both teams not found in the database.")

#     # Pull 5 player documents from Mongo based on stored IDs
#     lancaster_roster = [
#         Player(players_collection.find_one({"_id": pid}))
#         for pid in lancaster_team["player_ids"][:5]
#     ]
#     bt_roster = [
#         Player(players_collection.find_one({"_id": pid}))
#         for pid in bt_team["player_ids"][:5]
#     ]

#     print(lancaster_roster)
#     print(bt_roster)


#     game_state = {
#         "offense_team": "Lancaster",
#         "defense_team": "Bentley-Truman",
#         "players": {
#             "Lancaster": {
#                 "PG": lancaster_roster[0],
#                 "SG": lancaster_roster[1],
#                 "SF": lancaster_roster[2],
#                 "PF": lancaster_roster[3],
#                 "C":  lancaster_roster[4]
#             },
#             "Bentley-Truman": {
#                 "PG": bt_roster[0],
#                 "SG": bt_roster[1],
#                 "SF": bt_roster[2],
#                 "PF": bt_roster[3],
#                 "C":  bt_roster[4]
#             }
#         },
#         "score": {"Lancaster": 0, "Bentley-Truman": 0},
#         "time_remaining": 480,
#         "quarter": 1,
#         "offensive_state": "HALF_COURT",
#         "tempo": 2,
#         "playcall": {"offense": "Base", "defense": "Man"},
#         "defense_playcall": "Man",  # Add this line
#         "turn_number": 17,
#         "team_fouls": {
#             "Lancaster": 0,
#             "Bentley-Truman": 0
#         },
#         "free_throws": 0,
#         "free_throws_remaining": 0,
#         "last_ball_handler": None,
#         "bonsu_active": False,
#         "box_score": {
#             "Lancaster": {},
#             "Bentley-Truman": {}
#         }
#     }
    
#     game_state["scouting_data"] = {
#         team: {
#             "offense": {
#                 "Fast_Break_Entries": 0,
#                 "Fast_Break_Success": 0,
#                 "Playcalls": {call: {"used": 0, "success": 0} for call in ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]},
#             },
#             "defense": {
#                 "Man": {"used": 0, "success": 0},
#                 "Zone": {"used": 0, "success": 0},
#                 "vs_Fast_Break": {"used": 0, "success": 0},
#             }
#         }
#         for team in game_state["players"]
#     }
    
#     game_state["playcall_weights"] = initialize_playcall_settings()
#     game_state["team_attributes"] = initialize_team_attributes()
#     game_state["strategy_settings"] = initialize_strategy_settings()
#     game_state["strategy_calls"] = initialize_strategy_calls()

#     game_state["playcall_tracker"] = {
#         team: {call: 0 for call in ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]}
#         for team in game_state["players"]
#     }
#     game_state["defense_playcall_tracker"] = {
#         team: {call: 0 for call in ["Man", "Zone"]}
#         for team in game_state["players"]
#     }

#     game_state["points_by_quarter"] = {
#         team: [0, 0, 0, 0] for team in game_state["players"]
#     }


#     i = 1
#     for q in range(1, 5):  # quarters 1 to 4
#         game_state["quarter"] = q
#         recharge_amount = 0.3 if q == 3 else 0.2
#         # Reset fouls at start of quarter
#         for team in game_state["team_fouls"]:
#             game_state["team_fouls"][team] = 0
#         game_state["time_remaining"] = 480  # 8 minutes per quarter
#         # Recharge NG at quarter break
#         for team in game_state["players"]:
#             for player in game_state["players"][team].values():
#                 player.recharge_energy(recharge_amount)


#         if not return_game_state:
#             print(f"\n=== Start of Q{q} ===")
#         while game_state["time_remaining"] > 0:
#             if not return_game_state:
#                 print(f"--- Turn {i} ---")
#             game_state["last_ball_handler"] = game_state["players"][game_state["offense_team"]]["PG"]
#             # game_state["last_ball_handler"] = "PG"
#             game_state["strategy_calls"] = resolve_strategy_calls(game_state)
#             # for team, calls in game_state["strategy_calls"].items():
#             #     print(f"{team} Tempo = {calls['tempo_call']}, Aggression = {calls['aggression_call']}")
#             turn_result = resolve_turn(game_state)
#             game_state["time_remaining"] = max(0, game_state["time_remaining"] - turn_result["time_elapsed"])
            
#             for player in game_state["players"][game_state["offense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])
#             for player in game_state["players"][game_state["defense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])

#             #Energy System
#             if i % 2 == 0 or i == 1:
#                 energy_rng_seed = random.choices(
#                     [0.9, 0.95, 1.0, 1.05, 1.1],
#                     weights=[1, 2, 5, 2, 1]
#                 )[0]
#             # print(f"Turn {i} | Energy RNG: {energy_rng_seed}")
#             base_decay = 0.025  # Base amount of NG lost per turn
#             fatigue_mod = 1.1 if game_state["defense_playcall"] == "Man" else 0.9
#             def_team = game_state["defense_team"]
#             for team in [game_state["offense_team"], game_state["defense_team"]]:
#                 for pos, player_obj in game_state["players"][team].items():
#                     attr = game_state["players"][team][pos].attributes
#                     endurance = attr["ND"]
#                     decay = max(0.001, base_decay - (endurance / 1000))  # Prevent negative decay
#                     decay = max(0.001, decay * energy_rng_seed)  # Apply seeded RNG
#                      # ✅ Only apply to defenders
#                     if team == def_team:
#                         decay *= fatigue_mod
#                     player_obj.decay_energy(decay) # Floor at 0.1
#             recalculate_energy_scaled_attributes(game_state)

#             minutes = game_state["time_remaining"] // 60
#             seconds = game_state["time_remaining"] % 60
#             clock_display = f"{minutes}:{seconds:02d}"
#             if not return_game_state:
#                 print()
#                 print(turn_result.get("text", "No description"))
#                 print()
#                 print(f"Score: {game_state['score']}")
#                 print(f"Clock: {clock_display} // Q{game_state['quarter']}")
#                 print(f"Team Fouls: {game_state['team_fouls']}")
#                 # if turn_result.get("possession_flips"):
#                 #     print("Possession changes.")
#                 # else:
#                 #     print("Possession retained.")
#                 print()
#             if turn_result.get("possession_flips", False):
#                 game_state["offense_team"], game_state["defense_team"] = (
#                     game_state["defense_team"],
#                     game_state["offense_team"]
#                 )
#             i += 1

#         if not return_game_state:
#             print(f"=== End of Q{q} ===")
    
#     for team in game_state["box_score"]:
#         for player in game_state["box_score"][team]:
#             raw_seconds = game_state["box_score"][team][player]["MIN"]
#             game_state["box_score"][team][player]["MIN"] = int(raw_seconds / 60)

#     # --- Overtime if tied after regulation ---
#     while game_state["score"]["Lancaster"] == game_state["score"]["Bentley-Truman"]:
#         game_state["quarter"] += 1
#         for team in game_state["points_by_quarter"]:
#             game_state["points_by_quarter"][team].append(0)

#         game_state["time_remaining"] = 240  # 4 minutes for OT

#         if not return_game_state:
#             print(f"\n=== Start of Overtime Q{game_state['quarter']} ===")

#         while game_state["time_remaining"] > 0:
#             if not return_game_state:
#                 print(f"--- Turn {i} (OT) ---")
#             turn_result = resolve_turn(game_state)
#             game_state["time_remaining"] = max(0, game_state["time_remaining"] - turn_result["time_elapsed"])

#             for player in game_state["players"][game_state["offense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])
#             for player in game_state["players"][game_state["defense_team"]].values():
#                 player.record_stat("MIN", turn_result["time_elapsed"])

#             # Energy and movement logic remains unchanged
#             if i % 2 == 0 or i == 1:
#                 energy_rng_seed = random.choices([0.9, 0.95, 1.0, 1.05, 1.1], weights=[1, 2, 5, 2, 1])[0]
#             base_decay = 0.025
#             for team in [game_state["offense_team"], game_state["defense_team"]]:
#                 for pos, player_obj in game_state["players"][team].items():
#                     attr = game_state["players"][team][pos].attributes
#                     endurance = attr["ND"]
#                     decay = max(0.001, base_decay - (endurance / 1000))
#                     decay = max(0.001, decay * energy_rng_seed)
#                     attr["NG"] = max(0.1, round(attr["NG"] - decay, 3))
#             recalculate_energy_scaled_attributes(game_state)

#             minutes = game_state["time_remaining"] // 60
#             seconds = game_state["time_remaining"] % 60
#             clock_display = f"{minutes}:{seconds:02d}"
#             if not return_game_state:
#                 print(turn_result.get("text", "No description"))
#                 print(f"Clock: {clock_display}")
#                 print(f"Quarter: Q{game_state['quarter']}")
#                 print(f"Score: {game_state['score']}")
#                 print(f"Team Fouls: {game_state['team_fouls']}")
#                 print("Possession changes." if turn_result.get("possession_flips") else "Possession retained.")
#                 print()

#             if turn_result.get("possession_flips", False):
#                 game_state["offense_team"], game_state["defense_team"] = (
#                     game_state["defense_team"],
#                     game_state["offense_team"]
#                 )
#             i += 1

#         if not return_game_state:
#             print(f"=== End of Overtime Q{game_state['quarter']} ===")

    
#     if not return_game_state:
#         print(f"\n=== Box Score After {i} Turns ===")
#     for team in game_state["box_score"]:
#         team_score = game_state["score"][team]
#         if not return_game_state:
#             print(f"\n{team} {team_score}")
#         for player, stats in game_state["box_score"][team].items():
#             # Recalculate PTS if you're not auto-updating it in record_stat()
#             stats["PTS"] = (2 * stats["FGM"]) + stats["3PTM"] + stats["FTM"]
#             stats["REB"] = stats["OREB"] + stats["DREB"]
#             if not return_game_state:
#                 print(f"{player}: {stats}")

#     if not return_game_state:
#         print(f"\n=== Team Points by Quarter ===")
#         for team, q_points in game_state["points_by_quarter"].items():
#             print(f"{team}: Q1={q_points[0]}  Q2={q_points[1]}  Q3={q_points[2]}  Q4={q_points[3]}  Total={sum(q_points)}")

#     # Reset all player attributes to anchor values after the game
#     for team in game_state["players"]:
#         for pos, player in game_state["players"][team].items():
#             player.reset_energy()

#     if not return_game_state:
#         print(f"\n=== Team Stats Summary ===")
#     team_stats = calculate_team_stats(game_state)
#     stat_keys = ["FGM", "FGA", "3PTM", "3PTA", "FTM", "FTA", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "PTS",
#                     "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S"]

#     # Print header
#     column_width = max(len(k) for k in stat_keys) + 2
#     header = "TEAM".ljust(18) + "".join(k.rjust(column_width) for k in stat_keys)
#     if not return_game_state:
#         print(header)
#         print("-" * len(header))

#         for team, stats in team_stats.items():
#             row = team.ljust(18) + "".join(str(stats.get(k, 0)).rjust(column_width) for k in stat_keys)
#             print(row)

#     # if not return_game_state:
#     #     print_scouting_report(game_state["scouting_data"])



#     if return_game_state:
#         return game_state

# # if __name__ == "__main__":
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


