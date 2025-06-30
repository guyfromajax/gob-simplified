import random
from BackEnd.utils.shared import calculate_rebound_score, get_name_safe

class ReboundManager:
    def __init__(self, game):
        self.game = game
        self.off_team = game.offense_team
        self.def_team = game.defense_team
        self.off_lineup = self.off_team.lineup
        self.def_lineup = self.def_team.lineup

    def choose_rebounder(self, side):
        candidates = self.off_lineup if side == "offense" else self.def_lineup
        weights = {
            pos: (player.attributes["RB"] * 0.5 + player.attributes["ST"] * 0.3 + player.attributes["AG"] * 0.2)
            for pos, player in candidates.items()
        }
        return self._weighted_choice(weights)

    def _weighted_choice(self, weight_dict):
        if not weight_dict:
            # fallback to default positions or raise a clearer error
            print("⚠️  Empty weight_dict passed to _weighted_choice")
            return random.choice(["PG", "SG", "SF", "PF", "C"])
        total = sum(weight_dict.values())
        r = random.uniform(0, total)
        upto = 0
        for k, w in weight_dict.items():
            if upto + w >= r:
                return k
            upto += w
        return random.choice(list(weight_dict.keys()))  # final fallback


    def handle_rebound(self):
        o_pos = self.choose_rebounder("offense")
        d_pos = self.choose_rebounder("defense")

        o_player = self.off_lineup[o_pos]
        d_player = self.def_lineup[d_pos]
        off_mod = self.off_team.team_attributes["rebound_modifier"]
        def_mod = self.def_team.team_attributes["rebound_modifier"]

        o_score = calculate_rebound_score(o_player)
        d_score = calculate_rebound_score(d_player)

        bias = def_mod - off_mod
        def_prob = min(0.95, max(0.55, 0.75 + bias))

        total = d_score + o_score
        d_weight = d_score / total if total > 0 else 0.5
        d_weight += (def_prob - 0.5)
        d_weight = min(0.95, max(0.05, d_weight))

        rebound_team = self.def_team if random.random() < d_weight else self.off_team
        rebounder = d_player if rebound_team == self.def_team else o_player
        stat = "DREB" if rebound_team == self.def_team else "OREB"

        rebounder.record_stat(stat)
        # print(f"+1 rebound for {get_name_safe(rebounder)} / rebound manager - handle_rebound")

        # Store for possible fast break or putback
        self.game.game_state["last_rebounder"] = rebounder
        self.game.game_state["last_rebound"] = stat

        print_variable = "defensive rebound" if stat == "DREB" else "offensive rebound"

        # Return a valid turn_result
        return {
            "result_type": stat,
            "ball_handler": rebounder,
            "text": f"{rebounder} grabs the {print_variable}.",
            "time_elapsed": random.randint(3, 6),
            "possession_flips": rebound_team == self.def_team,
        }
