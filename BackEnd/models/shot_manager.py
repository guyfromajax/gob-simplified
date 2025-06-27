import random
from BackEnd.constants import (
    THREE_POINT_PROBABILITY, 
    PLAYCALL_ATTRIBUTE_WEIGHTS, 
    BLOCK_PROBABILITY,
    AGGRESSION_FOUL_MULTIPLIER
)
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
    get_name_safe,
    calculate_gravity_score,
    unpack_game_context,
)


class ShotManager:
    def __init__(self, game):
        self.game = game
        self.game_state = game.game_state  # still accessible
        # Add defense score tracking
        self.defense_scores = []


    def resolve_shot(self, roles):
        
        game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(self.game)
        
        time_elapsed = 0

        shooter = roles["shooter"]
        passer = roles.get("passer", "")
        screener = roles.get("screener", "")
        defender = roles.get("defender", "")

        playcall = self.game_state["current_playcall"]
        defense_call = self.game_state["defense_playcall"]
        is_three = random.random() < THREE_POINT_PROBABILITY.get(playcall, 0.0)
        shot_threshold = off_team.team_attributes["shot_threshold"]
        if is_three:
            shot_threshold += 100
        if playcall == "Set":
            playcall = "Attack"

        # ✅ New: returns shot_score, help defender, and foul info
        shot_score, help_defender, d_foul, foul_player = self.calculate_shot_score(
            shooter, passer, screener, defender, playcall, defense_call, is_three
        )

        made = shot_score >= shot_threshold

        # Stat tracking (attempts)
        shooter.record_stat("FGA")
        if is_three:
            shooter.record_stat("3PTA")

        # ------------------------
        # 🎯 Shot is Made
        # ------------------------
        if made:
            shooter.record_stat("FGM")
            if passer:
                passer.record_stat("AST")
            if is_three:
                shooter.record_stat("3PTM")

            points = 3 if is_three else 2
            record_team_points(self.game, off_team, points)

            possession_flips = True
            if screener:
                screener.record_stat("SCR_S")

            if d_foul:
                # AND-1 situation
                foul_player.record_stat("F")
                self.game_state["foul_team"] = "DEFENSE"
                self.game_state["offensive_state"] = "FREE_THROW"
                self.game_state["free_throws"] = 1
                self.game_state["free_throws_remaining"] = 1
                text = f"{get_name_safe(shooter)} makes the shot. {get_name_safe(foul_player)} fouls him! AND-1 opportunity!"
            else:
                text = f"{get_name_safe(shooter)} drains a 3!" if is_three else f"{get_name_safe(shooter)} makes the shot."

        # ------------------------
        # ❌ Shot is Missed
        # ------------------------
        else:
            text = f"{get_name_safe(shooter)} misses the {'3' if is_three else 'shot'}."
            if defender:
                defender.record_stat("DEF_S")

            if d_foul:
                # Shooting foul → free throws
                foul_player.record_stat("F")
                self.game_state["foul_team"] = "DEFENSE"
                self.game_state["offensive_state"] = "FREE_THROW"
                self.game_state["free_throws"] = 3 if is_three else 2
                self.game_state["free_throws_remaining"] = self.game_state["free_throws"]
                text = f"{get_name_safe(foul_player)} fouls {get_name_safe(shooter)} on the shot."
                possession_flips = False
            else:
                # Regular miss → rebound logic
                defense_attrs = defender.attributes if defender else {"ID": 0}
                base_block_prob = BLOCK_PROBABILITY.get(playcall, 0.0)
                block_skill = defense_attrs["ID"] / 100
                final_block_chance = base_block_prob * (0.5 + block_skill)
                is_block = random.random() < final_block_chance
                if is_block:
                    text += f" {get_name_safe(defender)} blocks the shot! Great block!"
                    defender.record_stat("BLK")

                # Rebound system
                rebounder_dict = {
                    "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
                    "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
                }

                o_pos = choose_rebounder(rebounder_dict, "offense")
                d_pos = choose_rebounder(rebounder_dict, "defense")
                o_rebounder = off_team.lineup[o_pos]
                d_rebounder = def_team.lineup[d_pos]

                o_score = calculate_rebound_score(o_rebounder)
                d_score = calculate_rebound_score(d_rebounder)

                off_mod = off_team.team_attributes["rebound_modifier"]
                def_mod = def_team.team_attributes["rebound_modifier"]
                bias = def_mod - off_mod
                def_prob = min(0.95, max(0.55, 0.75 + bias))

                total_score = d_score + o_score
                d_weight = (d_score / total_score) if total_score else 0.5
                d_weight += (def_prob - 0.5)
                d_weight = min(0.95, max(0.05, d_weight))
                if defense_call == "Zone":
                    d_weight *= 0.9
                o_weight = 1 - d_weight

                rebound_team = def_team if random.random() < d_weight else off_team
                rebounder = d_rebounder if rebound_team == def_team else o_rebounder
                stat = "DREB" if rebound_team == def_team else "OREB"
                self.game_state["last_rebound"] = stat
                rebounder.record_stat(stat)
                text += f"...{get_name_safe(rebounder)} grabs the rebound."
                possession_flips = rebound_team != off_team

                if stat == "OREB":
                    if random.random() < 0.65:
                        text += "... he attempts the putback..."
                        putback_result = resolve_offensive_rebound_loop(self.game, rebounder)
                        text += putback_result["text"]
                        possession_flips = putback_result["possession_flips"]
                        time_elapsed += putback_result["time_elapsed"]
                    else:
                        text += "...and he kicks it back out to reset the half-court offense"
                else:
                    self.game_state["last_rebounder"] = rebounder
                    self.game_state["offensive_state"] = (
                        "FAST_BREAK" if random.random() < get_fast_break_chance(self.game) else "HCO"
                    )

        # ⏱️ Add tempo-based time to turn
        tempo = off_team.strategy_calls["tempo_call"]
        time_elapsed += get_time_elapsed(tempo)

        shooter_pos = get_player_position(off_lineup, shooter)
        print(f"end of resolve_shot, possession_flips: {possession_flips}")

        return {
            "result_type": "MAKE" if made else "MISS",
            "ball_handler": shooter,
            "shooter": shooter,
            "screener": screener,
            "passer": passer,
            "defender": defender,
            "text": text,
            "possession_flips": possession_flips,
            "start_coords": {shooter_pos: {"x": 72, "y": 25}},
            "end_coords": {shooter_pos: {"x": 82, "y": 23}},
            "time_elapsed": time_elapsed
        }

    
    def calculate_shot_score(self, shooter, passer, screener, defender, playcall, defense_call, is_three):
        """
        Calculate shot score based on attributes, playcall, defense, gravity, etc.
        Also returns:
            - help_defender: if one triggered
            - d_foul: whether a defensive foul occurred
            - foul_player: who committed the foul
        """

        shot_score = 0
        attrs = shooter.attributes
        weights = PLAYCALL_ATTRIBUTE_WEIGHTS.get(playcall, {})

        # Base shot score based on shooter attributes and playcall weights
        shot_score += sum(attrs[attr] * (weight / 10) for attr, weight in weights.items()) * random.randint(1, 6)

        # Passing or dribbling bonus
        if passer:
            passer_attrs = passer.attributes
            passer_score = (passer_attrs["PS"] * 0.8 + passer_attrs["IQ"] * 0.2) * random.randint(1, 6)
            shot_score += passer_score * 0.2
        else:
            dribble_score = (attrs["AG"] * 0.8 + attrs["IQ"] * 0.2) * random.randint(1, 6)
            shot_score += dribble_score * 0.2

        # Defensive impact
        defense_attrs = defender.attributes if defender else {"OD": 0, "IQ": 0, "CH": 0}
        defense_score = (
            defense_attrs["OD"] * 0.8 +
            defense_attrs["IQ"] * 0.1 +
            defense_attrs["CH"] * 0.1
        ) * random.randint(1, 6)
        
        # Track defense score for statistics
        self.defense_scores.append(defense_score)

        d_foul, foul_player = self.check_defensive_foul_on_shot(defender, defense_score)

        shot_score -= defense_score * 0.2
        if defender:
            defender.record_stat("DEF_A")

        # Defense scheme multiplier
        if (defense_call == "Zone" and is_three) or (defense_call == "Man" and not is_three):
            shot_score *= 0.9
        else:
            shot_score *= 1.1

        # Help defense
        help_defender = None
        if defender:
            shot_score, help_defender, help_penalty = apply_help_defense_if_triggered(
                self.game, playcall, is_three, defender, shot_score
            )

        # Screener bonus
        if screener and screener != shooter:
            screen_attrs = screener.attributes
            screen_score = calculate_screen_score(screen_attrs)
            shot_score += screen_score * 0.15
            screener.record_stat("SCR_A")

        # Gravity contribution from off-ball players
        off_lineup = self.game.offense_team.lineup
        shooter_pos = get_player_position(off_lineup, shooter)
        passer_pos = get_player_position(off_lineup, passer) if passer else None
        screener_pos = get_player_position(off_lineup, screener) if screener else None

        gravity_contributors = [
            pos for pos in off_lineup
            if pos not in [shooter_pos, passer_pos, screener_pos]
        ]

        total_gravity = sum(
            calculate_gravity_score(off_lineup[pos].attributes)
            for pos in gravity_contributors
        )

        gravity_boost = total_gravity * 0.02
        shot_score += gravity_boost

        print(f"Off-ball gravity boost: +{round(gravity_boost, 2)} from {gravity_contributors}")
        print(f"offense call: {playcall} // defense call: {defense_call}")
        print(f"shooter: {get_name_safe(shooter)} | passer: {get_name_safe(passer)}")
        print(f"shot score = {round(shot_score, 2)} | (defense penalty: {round(defense_score * 0.2, 2)})")

        return shot_score, help_defender, d_foul, foul_player

    
    def check_defensive_foul_on_shot(self, defender, defense_score):
        """
        Determines if a defensive foul occurs based on defender skill and team aggression.
        Returns (bool, player) → (was_foul_committed, fouling_defender)
        """
        if not defender:
            return False, None

        defense_team = self.game.defense_team
        defense_attrs = defender.attributes

        aggression_level = defense_team.strategy_calls.get("aggression", 2)
        aggression_factor = AGGRESSION_FOUL_MULTIPLIER.get(aggression_level, 0.2)
        foul_threshold = defense_team.team_attributes.get("foul_threshold", 30)

        d_foul = defense_score < (foul_threshold * aggression_factor)
        print("End of check_defensive_foul_on_shot")
        print(f"defense_score: {defense_score} < foul_threshold: {foul_threshold} * aggression_factor: {aggression_factor}")
        return d_foul, defender if d_foul else None


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
        defense_attrs = defender.attributes if defender else {"ID": 0, "IQ": 0, "CH": 0}
        defense_score = (
            defense_attrs.get("ID", 0) * 0.8 +
            defense_attrs.get("IQ", 0) * 0.1 +
            defense_attrs.get("CH", 0) * 0.1
        ) * random.randint(1, 6)
        # Track defense score for statistics (fast break)
        self.defense_scores.append(defense_score)
        shot_score -= defense_score * 0.2
        if defender:
            defender.record_stat("DEF_A")
        

        made = shot_score >= off_team.team_attributes["shot_threshold"]
        shooter.record_stat("FGA")
        # print(f"{get_name_safe(shooter)} attempts a fast breakshot")

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
            # print(f"+1 rebound for {get_name_safe(rebounder)} / shot manager - resolve_fast_break_shot")
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

    def print_defense_score_stats(self):
        """Print defense score statistics for the game."""
        if not self.defense_scores:
            print("No defense scores recorded in this game.")
            return
            
        import statistics
        
        count = len(self.defense_scores)
        avg = statistics.mean(self.defense_scores)
        median = statistics.median(self.defense_scores)
        stdev = statistics.stdev(self.defense_scores) if count > 1 else 0
        
        print("\n" + "="*50)
        print("DEFENSE SCORE STATISTICS")
        print("="*50)
        print(f"Total calculations: {count}")
        print(f"Average: {avg:.2f}")
        print(f"Median: {median:.2f}")
        print(f"Standard Deviation: {stdev:.2f}")
        print(f"1st Standard Deviation Range: {avg - stdev:.2f} to {avg + stdev:.2f}")
        print(f"2nd Standard Deviation Range: {avg - 2*stdev:.2f} to {avg + 2*stdev:.2f}")
        print(f"Min: {min(self.defense_scores):.2f}")
        print(f"Max: {max(self.defense_scores):.2f}")
        print("="*50)
