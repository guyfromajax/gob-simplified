# BackEnd/models/player.py

from BackEnd.constants import ALL_ATTRS, BOX_SCORE_KEYS

class Player:
    def __init__(self, data):
        self.first_name = data["first_name"]
        self.last_name = data["last_name"]
        self.team = data.get("team", None)
        self.attributes = self._extract_attributes(data)
        self.stats = self._init_stats()

    def _extract_attributes(self, data):
        attrs = {k: v for k, v in data.items() if k in ALL_ATTRS}
        for k in list(attrs):
            attrs[f"anchor_{k}"] = attrs[k]
        attrs["NG"] = 1.0
        return attrs

    def _init_stats(self):
        return {
            "game": {k: 0 for k in BOX_SCORE_KEYS},
            "season": {k: 0 for k in BOX_SCORE_KEYS},
            "career": {k: 0 for k in BOX_SCORE_KEYS},
        }

    def record_stat(self, stat, amount=1):
        self.stats["game"][stat] += amount
        if stat in ["FGM", "3PTM", "FTM"]:
            s = self.stats["game"]
            s["PTS"] = (2 * s["FGM"]) + s["3PTM"] + s["FTM"]

    def recalculate_energy_scaled_attributes(self):
        ng = self.attributes["NG"]
        for k in ALL_ATTRS:
            if f"anchor_{k}" in self.attributes:
                self.attributes[k] = int(self.attributes[f"anchor_{k}"] * ng)

    def reset_energy(self):
        self.attributes["NG"] = 1.0
        self.recalculate_energy_scaled_attributes()

    def get_name(self):
        return f"{self.first_name} {self.last_name}"
