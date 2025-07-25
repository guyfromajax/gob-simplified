# BackEnd/models/player.py

from BackEnd.constants import ALL_ATTRS, BOX_SCORE_KEYS, MALLEABLE_ATTRS
import uuid


class Player:
    def __init__(self, data):
        self.player_id = str(data.get("_id", uuid.uuid4()))
        self.first_name = data["first_name"]
        self.last_name = data["last_name"]
        self.name = f"{self.first_name} {self.last_name}"
        self.team = data.get("team")
        self.attributes = self._extract_attributes(data)
        self.jersey = data.get("jersey", 0)
        self.year = data.get("year", "")
        self.stats = self._init_stats()
        self.metadata = {
            "fouls": 0,
            "minutes_played": 0,
            "abilities": data.get("abilities", [])
        }
        self.coords = {"x": 25, "y": 50}

    def _extract_attributes(self, data):
        attr_data = data.get("attributes", {})
        if not attr_data:
            attr_data = {k: data.get(k, 0) for k in ALL_ATTRS}
        attrs = {k: attr_data.get(k, 0) for k in ALL_ATTRS}
        
        for k in list(attrs):
            attrs[f"anchor_{k}"] = attrs[k]

        attrs["NG"] = attr_data.get("NG", data.get("NG", 1.0))

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
        elif stat in {"OREB", "DREB"}:
            s = self.stats["game"]
            s["REB"] = s["OREB"] + s["DREB"]

    def get_fatigue_decay_amount(self):
        nd = self.attributes.get("ND", 50)  # Default to 50 if not set

        if nd >= 85:
            return 0.0
        elif nd >= 60:
            return 0.01
        else:
            return 0.02
    
    def decay_energy(self, amount):
        self.attributes["NG"] = max(0.1, round(self.attributes["NG"] - amount, 3))
        self._rescale_attributes()


    def recharge_energy(self, amount):
        self.attributes["NG"] = min(1.0, round(self.attributes["NG"] + amount, 3))
        self._rescale_attributes()

    def reset_energy(self):
        self.attributes["NG"] = 1.0
        self._rescale_attributes()

    def __getattr__(self, item):
        if item in self.attributes:
            return self.attributes[item]
        raise AttributeError(f"{item} not found")


    def _rescale_attributes(self):
        ng = self.attributes["NG"]
        for k in MALLEABLE_ATTRS:
            self.attributes[k] = int(self.attributes[f"anchor_{k}"] * ng)

    def get_name(self):
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return self.get_name()
    
    def reset_stats(self):
        self.stats["game"] = {stat: 0 for stat in BOX_SCORE_KEYS}

    def get_stat(self, stat, level="game"):
        return self.stats.get(level, {}).get(stat, 0)
    
    def has_ability(self, ability_name):
        return ability_name in self.metadata["abilities"]

    def get_ability(self, ability_name):
        return self.metadata["abilities"].get(ability_name)

    def get_all_abilities(self):
        return self.metadata["abilities"]
    
    def set_coords(self, x, y):
        self.coords = {"x": x, "y": y}

    
    




