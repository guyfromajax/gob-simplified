from BackEnd.models.logger import Logger
from BackEnd.models.rebound_manager import ReboundManager
from BackEnd.models.playbook_manager import PlaybookManager
from BackEnd.models.animator import Animator
import random
import json
from BackEnd.db import players_collection, teams_collection
from BackEnd.models.player import Player
from collections import defaultdict
from BackEnd.playcall_skeletons.inside_skeletons import INSIDE_SCENES
from BackEnd.constants import ACTIONS
from BackEnd.constants import (
    PLAYCALL_ATTRIBUTE_WEIGHTS, 
    POSITION_LIST, 
    STRATEGY_CALL_DICTS, 
    TEMPO_PASS_DICT,
    MALLEABLE_ATTRS
)
from BackEnd.utils.shared import (
    weighted_random_from_dict, 
    generate_pass_chain, 
    get_team_thresholds, 
    get_foul_and_turnover_positions,
    get_name_safe,
    get_player_position,
    update_player_coords_from_animations,
    serialize_lineup
)
from BackEnd.engine.phase_resolution import (
    resolve_fast_break_logic, 
    resolve_free_throw_logic, 
    resolve_turnover_logic, 
    calculate_foul_turnover
)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from BackEnd.models.game_manager import GameManager

class TurnManager:
    def __init__(self, game_manager: "GameManager"):
        self.game = game_manager
        self.logger = Logger()
        self.rebound_manager = ReboundManager(self.game)
        self.playbook_manager = PlaybookManager(self.game.offense_team)
        self.animator = Animator(self.game)

    def run_micro_turn(self):
        # Increment micro turn counter
        self.game.micro_turn_count += 1
        
        # STEP 1: Set strategy calls (tempo + aggression)
        self.set_strategy_calls()

        print("*****RUN TURN*****")
        print(f"offensive state: {self.game.game_state['offensive_state']}")
        if self.game.game_state["offensive_state"] in ["HCO", "HALF_COURT"]:
            print(f"{self.game.offense_team.name}: {self.game.game_state['current_playcall']}")
            print(f"{self.game.defense_team.name}: {self.game.game_state['defense_playcall']}")

        # STEP 3: Route based on offensive state
        state = self.game.game_state["offensive_state"]
        if state == "FREE_THROW":
            result = self.resolve_free_throw()
        elif state == "FAST_BREAK":
            result = self.resolve_fast_break()
        else:
            calls = self.set_playcalls()
            self.game.game_state["current_playcall"] = calls["offense"]
            self.game.game_state["defense_playcall"] = calls["defense"]
            result = self.resolve_half_court_offense()

        print("Inside run_micro_turn // coming out of resolve offensive state functions")
        print(f"offense team id: {self.game.offense_team.team_id}")
        print(f"defense team id: {self.game.defense_team.team_id}")

        # STEP 4: Final updates (clock, logs, animation)
        self.update_clock_and_possession(result)
        self.logger.log_turn_result(result)
        # If animations weren’t assigned yet (e.g. fast break, free throw), use fallback
        if "animations" not in result:
            roles = result.get("roles")
            if roles:
                from BackEnd.models.animator import Animator
                animator = Animator(self.game)
                result["animations"] = animator.capture_halfcourt_animation(
                    roles=roles,
                    event_step=result.get("event_step")
                )
            else:
                result["animations"] = []  # No animation possible (e.g., free throw or turnover with no roles)


        result["possession_team_id"] = self.game.offense_team.team_id

        for key in ["ball_handler", "shooter", "passer", "screener", "defender"]:
            if key in result:
                result[key] = get_name_safe(result[key])
        for key in ["ball_handler", "shooter", "screener", "passer", "defender"]:
            if key in result:
                val = result[key]
                if hasattr(val, "name"):
                    result[key] = val.name
                elif hasattr(val, "player_id"):  # fallback to player_id
                    result[key] = val.player_id
                else:
                    result[key] = str(val)  # final fallback (safe for non-class data)

        result["turn_count"] = self.game.micro_turn_count
        # result["possession_team_id"] = self.game.offense_team.team_id
        update_player_coords_from_animations(self.game, result["animations"])

        result["home_lineup"] = serialize_lineup(self.game.home_team.lineup)
        result["away_lineup"] = serialize_lineup(self.game.away_team.lineup)

        # print(f"inside run_micro_turn result: {result}")
        # print(f"result: {result}")
        return result


    def set_playcalls(self):

        chosen_playcall = weighted_random_from_dict(self.game.offense_team.playcall_weights)
        defense_setting = self.game.defense_team.strategy_settings["defense"]
        chosen_defense = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])

        # Track usage
        self.game.offense_team.playcall_tracker[chosen_playcall] += 1
        self.game.defense_team.defense_playcall_tracker[chosen_defense] += 1

        return {
            "offense": chosen_playcall,
            "defense": chosen_defense
        }


    def set_strategy_calls(self):

        tempo_setting = self.game.offense_team.strategy_settings["tempo"]
        aggression_setting = self.game.defense_team.strategy_settings["aggression"]

        self.game.offense_team.strategy_calls["tempo_call"] = random.choice(STRATEGY_CALL_DICTS["tempo"][tempo_setting])
        self.game.defense_team.strategy_calls["aggression_call"] = random.choice(STRATEGY_CALL_DICTS["aggression"][aggression_setting])


    
    def resolve_half_court_offense(self):
        from BackEnd.engine.phase_resolution import resolve_half_court_offense_logic
        return resolve_half_court_offense_logic(self.game)


    def resolve_fast_break(self):
        return resolve_fast_break_logic(self.game) 

    def resolve_free_throw(self):
        return resolve_free_throw_logic(self.game)
    
    def resolve_turnover(self):
        return resolve_turnover_logic(self.game)

    def update_clock_and_possession(self, result):
        # 🕒 Reduce clock by time_elapsed
        time_elapsed = result.get("time_elapsed", 0)
        self.game.game_state["time_remaining"] -= time_elapsed

        # Clamp to 0
        if self.game.game_state["time_remaining"] < 0:
            self.game.game_state["time_remaining"] = 0

        # Convert to clock display (e.g., 400 → "6:40")
        minutes = self.game.game_state["time_remaining"] // 60
        seconds = self.game.game_state["time_remaining"] % 60
        self.game.game_state["clock"] = f"{minutes}:{seconds:02d}"

        # 🔁 Flip possession if flagged
        if result.get("possession_flips"):
            self.game.switch_possession()

    def assign_roles(self, off_call="INSIDE", def_call="MAN"):
        game = self.game
        game_state = game.game_state
        off_team = game.offense_team
        def_team = game.defense_team
        off_lineup = off_team.lineup
        def_lineup = def_team.lineup
        tempo_call = off_team.strategy_calls["tempo_call"]

        # --- Step 1: Pick scene and step count
        scene = random.choice(INSIDE_SCENES)
        tempo_to_steps = {"slow": 6, "normal": 4, "fast": 3}
        max_steps = tempo_to_steps.get(tempo_call.lower(), 4)
        steps = scene["steps"][:max_steps]

        # --- Step 2: Initialize outputs
        action_timeline = defaultdict(list)
        touch_counts = defaultdict(int)

        # --- Step 3: Build action timeline + touch counts
        for step_index, step in enumerate(steps):
            pos_actions = step["pos_actions"]
            events = step.get("events", [])

            for pos, action_info in pos_actions.items():
                player = off_lineup[pos]
                action = action_info["action"]
                action_timeline[player].append((step["timestamp"], action, action_info.get("spot")))

                # Count touch if action involves ball
                if action in [ACTIONS["HANDLE"], ACTIONS["PASS"], ACTIONS["RECEIVE"], ACTIONS["SHOOT"]]:
                    touch_counts[player] += 1

            for event in events:
                if event["type"] == "pass":
                    passer = off_lineup[event["from"]]
                    receiver = off_lineup[event["to"]]
                    touch_counts[passer] += 1
                    touch_counts[receiver] += 1
                elif event["type"] == "shot":
                    shooter = off_lineup[event["by"]]
                    touch_counts[shooter] += 1

        # --- Step 4: Determine primary roles
        shooter_pos = scene["primary_shooter"]
        screener_pos = scene["screener"]
        pass_chain = scene["pass_sequence"]

        passer_pos = pass_chain[-2] if len(pass_chain) >= 2 else ""
        if passer_pos in [shooter_pos, screener_pos]:
            passer_pos = ""

        if game_state["defense_playcall"] == "Zone":
            defender_pos = random.choice(list(def_lineup))
        else:
            defender_pos = shooter_pos

        # --- Step 5: Lookup player objects
        shooter = off_lineup[shooter_pos]
        screener = off_lineup[screener_pos]
        passer = off_lineup.get(passer_pos)
        defender = def_lineup[defender_pos]

        return {
            "shooter": shooter,
            "screener": screener,
            "ball_handler": shooter,
            "passer": passer,
            "pass_chain": pass_chain,
            "defender": defender,
            "steps": steps,
            "action_timeline": action_timeline,
            "touch_counts": touch_counts
        }
    
    # def assign_roles(self):
        
    #     off_team = self.game.offense_team
    #     def_team = self.game.defense_team
    #     off_lineup = self.game.offense_team.lineup
    #     def_lineup = self.game.defense_team.lineup
    #     playcall = self.game.game_state["current_playcall"]
    #     # print(f"playcall: {playcall}")

    #     # Compute shot weights using attributes embedded in each player object
    #     weights_dict = PLAYCALL_ATTRIBUTE_WEIGHTS.get("Attack" if playcall == "Set" else playcall, {})
    #     # print(f"weights_dict: {weights_dict}")

    #     # for pos, player in off_lineup.items():
    #     #     print(f"{pos}: {player.attributes}")
        
    #     shot_weights = {
    #         pos: sum(
    #             off_lineup[pos].attributes[attr] * weight
    #             for attr, weight in weights_dict.items()
    #         )
    #         for pos in off_lineup
    #     }
    #     # print(f"shot_weights: {shot_weights}")
    #     shooter_pos = weighted_random_from_dict(shot_weights)

    #     # Compute screener weights (excluding the shooter)
    #     screen_weights = {
    #         pos: (
    #             off_lineup[pos].attributes["ST"] * 6 +
    #             off_lineup[pos].attributes["AG"] * 2 +
    #             off_lineup[pos].attributes["IQ"] * 1 +
    #             off_lineup[pos].attributes["CH"] * 1
    #         )
    #         for pos in off_lineup if pos != shooter_pos
    #     }

    #     screener_pos = max(screen_weights, key=screen_weights.get)
    #     if screener_pos == shooter_pos:
    #         screener_pos = ""

    #     # Pass chain and passer
    #     pass_chain = generate_pass_chain(self.game, shooter_pos)

    #     passer_pos = pass_chain[-2] if len(pass_chain) >= 2 else ""
    #     if passer_pos == shooter_pos or passer_pos == screener_pos:
    #         passer_pos = ""

    #     if self.game.game_state["defense_playcall"] == "Zone":
    #         defender_pos = random.choice(POSITION_LIST)
    #     else:
    #         defender_pos = shooter_pos

    #     shooter = self.game.offense_team.lineup[shooter_pos]
    #     screener = self.game.offense_team.lineup[screener_pos]
    #     passer = self.game.offense_team.lineup[passer_pos] if passer_pos else None
    #     defender = self.game.defense_team.lineup[defender_pos]

        
    #     return {
    #         "shooter": shooter,
    #         "screener": screener,
    #         "ball_handler": shooter,
    #         "passer": passer,
    #         "pass_chain": pass_chain,
    #         "defender": defender
    #     }
    
    def determine_event_type(self, roles):
        game = self.game
        game_state = game.game_state
        off_team = game.offense_team
        def_team = game.defense_team
        def_lineup = def_team.lineup
        off_lineup = off_team.lineup
        defense_call = game_state["defense_playcall"]
        action_timeline = roles["action_timeline"]
        touch_counts = roles["touch_counts"]
        steps = roles["steps"]

        # Step 1: Decay energy for all players
        for player in off_lineup.values():
            player.decay_energy(player.get_fatigue_decay_amount())
        for player in def_lineup.values():
            player.decay_energy(player.get_fatigue_decay_amount())

        # Step 2: Calculate score for each potential turnover candidate
        turnover_risks = []
        for player, touches in touch_counts.items():
            if touches == 0:
                continue

            attr = player.attributes
            bh_score = (
                attr["BH"] * 0.5 +
                attr["AG"] * 0.2 +
                attr["IQ"] * 0.2 +
                attr["CH"] * 0.1
            ) * random.randint(1, 6)

            def_pos = get_player_position(off_lineup, player)
            defender = def_lineup.get(def_pos) if defense_call != "Zone" else random.choice(list(def_lineup.values()))
            def_attr = defender.attributes
            pressure = (
                def_attr["OD"] * 0.3 +
                def_attr["AG"] * 0.3 +
                def_attr["IQ"] * 0.2 +
                def_attr["CH"] * 0.2
            ) * random.randint(1, 6)
            if defense_call == "Zone":
                pressure *= 0.9

            score = bh_score - pressure - (touches * 2)
            turnover_risks.append((score, player, defender))

        # Step 3: Calculate foul risks
        foul_risks = []
        for step_index, step in enumerate(steps):
            for pos, action_data in step["pos_actions"].items():
                action = action_data["action"]
                if action not in ["screen", "post_up", "handle_ball"]:
                    continue  # Only consider foul-prone actions

                offender = off_lineup[pos]
                defender = def_lineup[pos] if defense_call != "Zone" else random.choice(list(def_lineup.values()))
                o_attr = offender.attributes
                d_attr = defender.attributes

                d_score = (d_attr["IQ"] * 0.3 + d_attr["CH"] * 0.3 + d_attr["AG"] * 0.2 + d_attr["OD"] * 0.2) * random.randint(1, 6)
                o_score = (o_attr["IQ"] * 0.3 + o_attr["CH"] * 0.3 + o_attr["AG"] * 0.2 + o_attr["ST"] * 0.2) * random.randint(1, 6)

                # Slightly bias toward foul when high activity + tempo
                foul_margin = o_score - d_score
                if foul_margin < off_team.team_attributes["foul_threshold"] * 0.7:
                    foul_risks.append(("O_FOUL", step_index, offender, defender))
                elif d_score < def_team.team_attributes["foul_threshold"] * 1.3:
                    foul_risks.append(("D_FOUL", step_index, offender, defender))

        # Step 4: Decide event
        turnover_risks.sort(key=lambda x: x[0])
        foul_risks.sort(key=lambda x: x[1])  # prioritize earlier fouls

        if turnover_risks and turnover_risks[0][0] < off_team.team_attributes["turnover_threshold"]:
            _, player, defender = turnover_risks[0]
            roles["event_step"] = None  # You could optionally track when
            roles["turnover_player"] = player
            roles["turnover_defender"] = defender
            roles["ball_handler"] = player
            return "TURNOVER"

        elif foul_risks:
            foul_type, step_index, offender, defender = foul_risks[0]
            roles["event_step"] = step_index
            roles["foul_player"] = defender if foul_type == "D_FOUL" else offender
            return foul_type

        # No event = clean possession
        return "SHOT"

