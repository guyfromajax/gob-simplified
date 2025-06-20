# BackEnd/models/player.py

from BackEnd.constants import ALL_ATTRS, BOX_SCORE_KEYS, MALLEABLE_ATTRS

class Player:
    def __init__(self, data):
        self.first_name = data["first_name"]
        self.last_name = data["last_name"]
        self.name = f"{self.first_name} {self.last_name}"
        self.team = data.get("team")
        self.attributes = self._extract_attributes(data)
        self.stats = self._init_stats()

    def _extract_attributes(self, data):
        attrs = {k: data.get(k, 0) for k in ALL_ATTRS}
        for k in list(attrs):
            attrs[f"anchor_{k}"] = attrs[k]
        attrs["NG"] = 1.0
        return attrs

    def _init_stats(self):
        return {
            "game": {stat: 0 for stat in BOX_SCORE_KEYS},
            "season": {stat: 0 for stat in BOX_SCORE_KEYS},
            "career": {stat: 0 for stat in BOX_SCORE_KEYS},
        }

    def record_stat(self, stat, amount=1):
        self.stats["game"][stat] += amount
        if stat in {"FGM", "3PTM", "FTM"}:
            s = self.stats["game"]
            s["PTS"] = (2 * s["FGM"]) + s["3PTM"] + s["FTM"]

    def decay_energy(self, amount):
        self.attributes["NG"] = max(0.1, round(self.attributes["NG"] - amount, 3))
        self._rescale_attributes()

    def recharge_energy(self, amount):
        self.attributes["NG"] = min(1.0, round(self.attributes["NG"] + amount, 3))
        self._rescale_attributes()

    def reset_energy(self):
        self.attributes["NG"] = 1.0
        self._rescale_attributes()

    def _rescale_attributes(self):
        ng = self.attributes["NG"]
        for k in MALLEABLE_ATTRS:
            self.attributes[k] = int(self.attributes[f"anchor_{k}"] * ng)

    def get_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return self.get_name()

