import random
from BackEnd.constants import THREE_POINT_PROBABILITY, PLAYCALL_ATTRIBUTE_WEIGHTS, BLOCK_PROBABILITY
from BackEnd.utils.shared import (
    apply_help_defense_if_triggered, 
    get_fast_break_chance, 
    get_time_elapsed, 
    resolve_offensive_rebound_loop,
    get_player_position,
    record_team_points,
    calculate_screen_score,
    choose_rebounder,
    calculate_rebound_score,
    get_name_safe
)


class ShotManager:
    def __init__(self, game):
        self.game = game
        self.game_state = game.game_state  # still accessible


    def resolve_shot(self, roles):

        off_team = self.game.offense_team
        def_team = self.game.defense_team
        off_lineup = off_team.lineup
        def_lineup = def_team.lineup

        time_elapsed = 0
        shooter = roles["shooter"]
        passer = roles.get("passer", "")
        screener = roles.get("screener", "")
        defender = roles.get("defender", "")

        # print(f"-------Inside resolve_shot---------")
        # print(f"shooter: {get_name_safe(shooter)} | passer: {get_name_safe(passer)} | screener: {get_name_safe(screener)} | defender: {get_name_safe(defender)}")
        
        attrs = shooter.attributes
        
        playcall = self.game_state["current_playcall"]
        defense_call = self.game_state["defense_playcall"]
        is_three = random.random() < THREE_POINT_PROBABILITY.get(playcall, 0.0)
        shot_threshold = self.game.offense_team.team_attributes["shot_threshold"]
        if is_three:
            shot_threshold += 100

        if playcall == "Set":
            playcall = "Attack"
        weights = PLAYCALL_ATTRIBUTE_WEIGHTS.get(playcall, {})
        shot_score = sum(attrs[attr] * (weight / 10) for attr, weight in weights.items()) * random.randint(1, 6)
        if passer:
            passer_attrs = passer.attributes
            passer_score = (passer_attrs["PS"] * 0.8 + passer_attrs["IQ"] * 0.2) * random.randint(1, 6)
            shot_score += passer_score * 0.2
        else:
            dribble_score = (attrs["AG"] * 0.8 + attrs["IQ"] * 0.2) * random.randint(1, 6)
            shot_score += dribble_score * 0.2
        defense_attrs = defender.attributes
        defense_penalty = (defense_attrs["OD"] * 0.8 + defense_attrs["IQ"] * 0.1 + defense_attrs["CH"] * 0.1) * random.randint(1, 6)
        if defense_call == "Zone":
            defense_penalty *= 0.9
        shot_score -= defense_penalty * 0.2  # Scaling factor to tune
        if defender:
            defender.record_stat("DEF_A")
        # Apply bonus/penalty based on defense type and shot type
        if (defense_call == "Zone" and is_three) or (defense_call == "Man" and not is_three):
            shot_score *= 0.9
        else:
            shot_score *= 1.1


        # help defense logic
        if defender:
            shot_score, help_defender, help_penalty = apply_help_defense_if_triggered(
                self.game, playcall, is_three, defender, shot_score
            )
            # if help_defender:
            #     print(f"Help defense by {help_defender} → penalty applied: {round(help_penalty, 2)}")

        # Screen bonus (if applicable)
        
        if screener and screener != shooter:
            
            screen_attrs = screener.attributes
            screen_score = calculate_screen_score(screen_attrs)
            shot_score += screen_score * 0.15
            # print(f"screen by {screener} adds {round(screen_score * 0.15, 2)} to shot score")
            screener.record_stat("SCR_A")
            #need to add shot defender's ability to work through the screen

        # Gravity contribution from off-ball players
        # gravity_contributors = [
        #     pos for pos in game_state["players"][off_team]
        #     if pos not in [shooter_pos, passer_pos, screener_pos]
        # ]

        # total_gravity = 0
        # for pos in gravity_contributors:
        #     player = game_state["players"][off_team][pos]
        #     attrs = player.attributes
        #     total_gravity += calculate_gravity_score(attrs)
        # gravity_boost = total_gravity * 0.02  # Tunable
        # shot_score += gravity_boost
        # print(f"Off-ball gravity boost: +{round(gravity_boost, 2)} from {gravity_contributors}")

        # print(f"offense call: {playcall} // defense call: {defense_call}")
        # print(f"shooter: {get_name_safe(shooter)} | passer: {get_name_safe(passer)}")
        # print(f"shot score = {round(shot_score, 2)} | (defense score: {round(defense_penalty * 0.2, 2)})")
        made = shot_score >= shot_threshold


        # Track attempts
        shooter.record_stat("FGA")
        if is_three:
            shooter.record_stat("3PTA")

        if made:
            shooter.record_stat("FGM")
            if passer:
                passer.record_stat("AST")
            if is_three:
                shooter.record_stat("3PTM")
            points = 3 if is_three else 2
            record_team_points(self.game, off_team, points)
            text = f"{get_name_safe(shooter)} drains a 3!" if is_three else f"{get_name_safe(shooter)} makes the shot."
            possession_flips = True
            if screener:
                screener.record_stat("SCR_S")
        else:
            #apply determine_rebounder logic here
            text = f"{get_name_safe(shooter)} misses the {'3' if is_three else 'shot'}."
            if defender:
                defender.record_stat("DEF_S")
            #Build dict based on player proximity to the ball in the future
            base_block_prob = BLOCK_PROBABILITY.get(playcall, 0.0)
            # Defensive player's ID score (scaled 0–1)
            block_skill = defense_attrs["ID"] / 100  
            # Final block chance: scaled by skill
            final_block_chance = base_block_prob * (0.5 + block_skill)  # scales 50–150% of base
            is_block = random.random() < final_block_chance
            if is_block:
                text += f"{get_name_safe(defender)} blocks the shot!"
                defender.record_stat("BLK")
                

            rebounder_dict = {
                "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
                "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
            }

            o_pos = choose_rebounder(rebounder_dict, "offense")
            d_pos = choose_rebounder(rebounder_dict, "defense")
            o_rebounder = self.game.offense_team.lineup[o_pos]
            d_rebounder = self.game.defense_team.lineup[d_pos]

            o_score = calculate_rebound_score(o_rebounder)
            d_score = calculate_rebound_score(d_rebounder)

            off_mod = self.game.offense_team.team_attributes["rebound_modifier"]
            def_mod = self.game.defense_team.team_attributes["rebound_modifier"]
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
            self.game_state["last_rebound"] = stat  # stat is either "DREB" or "OREB"
            # rebounder.record_stat(stat)
            # print(f"+1 rebound for {get_name_safe(rebounder)} / shot manager - resolve_shot")

            text += f"...{rebounder} grabs the rebound."
            possession_flips = (rebound_team != off_team)
            
            if stat == "OREB":
                attempt_putback = random.random() < 0.65
                
                if attempt_putback:
                    text += (f"... he attempts the putback...")

                    # Basic putback shot calculation (we'll refine later)
                    attrs = rebounder.attributes
                    shot_score = (
                        attrs["SC"] * 0.6 +
                        attrs["CH"] * 0.2 +
                        attrs["IQ"] * 0.2
                    ) * random.randint(1, 6)

                    defender_pos = random.choice(["C", "C", "C", "C", "C", "PF", "PF", "PF", "SF", "SF", "SG", "PG"])
                    defender = self.game.defense_team.lineup[defender_pos]
                    defense_attrs = defender.attributes
                    defense_penalty = (defense_attrs["ID"] * 0.8 + defense_attrs["IQ"] * 0.1 + defense_attrs["CH"] * 0.1) * random.randint(1, 6)
                    shot_score -= defense_penalty * 0.2
                    made = shot_score >= off_team.team_attributes["shot_threshold"]

                    # Track stats
                    rebounder.record_stat("FGA")
                    if made:
                        rebounder.record_stat("FGM")
                        points = 2
                        record_team_points(self.game, off_team, points)
                        text += f" and he scores!"
                        possession_flips = True
                    else:
                        # Use dynamic logic for the missed putback
                        putback_result = resolve_offensive_rebound_loop(self.game, rebounder)
                        # Add result text and update turn metadata
                        text += f" and misses the putback. {putback_result['text']}"
                        possession_flips = putback_result["possession_flips"]
                        time_elapsed += putback_result["time_elapsed"]
            else:
                self.game_state["last_rebounder"] = rebounder
                if random.random() < get_fast_break_chance(self.game):
                    self.game_state["offensive_state"] = "FAST_BREAK"
                else:
                    self.game_state["offensive_state"] = "HCO"
        
        tempo = off_team.strategy_calls["tempo_call"]
        time_elapsed += get_time_elapsed(tempo)

        shooter_pos = get_player_position(off_lineup, shooter)

        # print(f"{text}")
        return {
            "result_type": "MAKE" if made else "MISS",
            "ball_handler": shooter,
            "shooter": shooter,
            "shot_score": shot_score,
            "screener": screener,
            "passer": passer,
            "defender": defender,
            "text": text,
            "possession_flips": possession_flips,
            "start_coords": {shooter_pos: {"x": 72, "y": 25}},
            "end_coords": {shooter_pos: {"x": 82, "y": 23}},
            "time_elapsed": time_elapsed
        }
    
    def resolve_fast_break_shot(self, fb_roles):
        off_team = self.game.offense_team
        def_team = self.game.defense_team
        off_lineup = off_team.lineup
        def_lineup = def_team.lineup
        
        shooter = fb_roles["shooter"]
        passer = fb_roles.get("passer", "")
        if shooter == passer:
            passer = None
        
        attrs = shooter.attributes
        
        shot_score = (attrs["SC"] * 0.6 + attrs["CH"] * 0.2 + attrs["IQ"] * 0.2) * random.randint(1, 6)

        defender = random.choice(fb_roles["defense"]) if fb_roles["defense"] else None
        if defender:
            defense_attrs = defender.attributes
            defense_penalty = (defense_attrs["ID"] * 0.8 + defense_attrs["IQ"] * 0.1 + defense_attrs["CH"] * 0.1) * random.randint(1, 6)
            shot_score -= defense_penalty * 0.2
            defender.record_stat("DEF_A")
        else:
            defense_penalty = 0

        made = shot_score >= off_team.team_attributes["shot_threshold"]
        shooter.record_stat("FGA")

        if made:
            shooter.record_stat("FGM")
            if passer:
                passer.record_stat("AST")
            text = f"{shooter} converts the fast break shot!"
            possession_flips = True
            self.game_state["offensive_state"] = "HCO"
            is_three = False
            points = 3 if is_three else 2
            record_team_points(self.game, off_team, points)
        else:
            if defender:
                defender.record_stat("DEF_S")
            rebounder = random.choice(fb_roles["defense"]) if fb_roles["defense"] else self.game.defense_team.lineup["PG"]
            text = f"{shooter} misses the fast break shot -- {rebounder} grabs the rebound."
            rebounder.record_stat("DREB")
            print(f"+1 rebound for {get_name_safe(rebounder)} / shot manager - resolve_fast_break_shot")
            possession_flips = True
            if random.random() < get_fast_break_chance(self.game):
                text += " -- entering a fast break!"
                self.game_state["offensive_state"] = "FAST_BREAK"
            else:
                text += " -- entering half court."
                self.game_state["offensive_state"] = "HCO"
            self.game_state["last_rebounder"] = rebounder
            self.game_state["last_rebound"] = "DREB"

        time_elapsed = random.randint(5, 15)

        shooter_pos = get_player_position(off_lineup, shooter)
        
        return {
            "result_type": "MAKE" if made else "MISS",
            "ball_handler": shooter,
            "shooter": shooter,
            "shot_score": shot_score,
            "screener": None,
            "passer": passer,
            "defender": defender,
            "text": text,
            "possession_flips": possession_flips,
            "start_coords": {shooter_pos: {"x": 72, "y": 25}},
            "end_coords": {shooter_pos: {"x": 82, "y": 23}},
            "time_elapsed": time_elapsed
        }
