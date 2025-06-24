import random

class ReboundManager:
    def __init__(self, game_state):
        self.game_state = game_state
        self.off_team = game_state["offense_team"]
        self.def_team = game_state["defense_team"]
        self.players = game_state["players"]
        self.team_attrs = game_state["team_attributes"]

    def choose_rebounder(self, side):
        candidates = self.players[self.off_team if side == "offense" else self.def_team]
        weights = {
            pos: (player.attributes["RB"] * 0.5 + player.attributes["ST"] * 0.3 + player.attributes["AG"] * 0.2)
            for pos, player in candidates.items()
        }
        return self._weighted_choice(weights)

    def _weighted_choice(self, weight_dict):
        total = sum(weight_dict.values())
        rand = random.uniform(0, total)
        upto = 0
        for key, weight in weight_dict.items():
            if upto + weight >= rand:
                return key
            upto += weight
        return random.choice(list(weight_dict.keys()))  # fallback

    def handle_rebound(self):
        o_pos = self.choose_rebounder("offense")
        d_pos = self.choose_rebounder("defense")

        o_player = self.players[self.off_team][o_pos]
        d_player = self.players[self.def_team][d_pos]

        o_score = self._calc_rebound_score(o_player.attributes)
        d_score = self._calc_rebound_score(d_player.attributes)

        off_mod = self.team_attrs[self.off_team]["rebound_modifier"]
        def_mod = self.team_attrs[self.def_team]["rebound_modifier"]
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
        rebounder.record_stat("REB")

        return {
            "rebound_team": rebound_team,
            "rebounder": rebounder,
            "rebound_stat": stat
        }

    def _calc_rebound_score(self, attr):
        return attr["RB"] * 0.5 + attr["ST"] * 0.3 + attr["AG"] * 0.2
