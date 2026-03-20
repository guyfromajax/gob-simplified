# BackEnd/models/player.py

from BackEnd.constants import ALL_ATTRS, BOX_SCORE_KEYS, MALLEABLE_ATTRS
import uuid
import os
import random
import logging


DEBUG_SERIALIZATION = os.getenv("DEBUG_SERIALIZATION")


class Player:
    def __init__(self, data):
        self.player_id = str(data.get("_id", uuid.uuid4()))
        self.first_name = data["first_name"]
        self.last_name = data["last_name"]
        self.name = f"{self.first_name} {self.last_name}"
        self.team = data.get("team")
        # Expose common biographical fields directly so downstream logic can
        # reference them without depending on the ``attributes`` payload. Many
        # tests construct lightweight player dictionaries (or patch lineup
        # builders) that omit a dedicated attribute block, so default to a
        # reasonable value when ``height``/``weight`` are missing.
        self.height = data.get("height", data.get("HT", 75))
        self.weight = data.get("weight", data.get("WT", 200))
        self.attributes = self._extract_attributes(data)
        self.jersey = data.get("jersey", 0)
        self.year = data.get("year", "")
        self.photo = data.get("photo", None)  # Player headshot image path
        # Optional per-position ratings (franchise / universal roster payloads)
        self.position_ratings = dict(data.get("position_ratings") or {})
        self.stats = self._init_stats()
        self._merge_stats_from_data(data)
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

    def _merge_stats_from_data(self, data):
        """Overlay game (or flattened) stats from roster/API payloads onto init stats."""
        raw = data.get("stats")
        if not isinstance(raw, dict):
            return
        game = raw.get("game", raw)
        if not isinstance(game, dict):
            return
        for k, v in game.items():
            if k not in self.stats.get("game", {}):
                continue
            if isinstance(self.stats["game"][k], list):
                continue
            try:
                if k in ("MIN",):
                    self.stats["game"][k] = v
                else:
                    self.stats["game"][k] = int(v) if v is not None else 0
            except (TypeError, ValueError):
                pass
    
    @staticmethod
    def randomize_game_attributes(attributes: dict) -> dict:
        """
        Initialize player attributes for a new mode instance.
        Copies exact values from universal collection for most attributes,
        then randomizes NG, CH, MO, and EM according to mode initialization rules.
        
        Should be called when initializing players for a new Single Game, Tournament, or Franchise.
        
        Args:
            attributes: Player attributes dict (from universal players collection)
            
        Returns:
            Modified attributes dict with:
            - Exact values copied for: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT
            - NG = 1.0
            - CH (Character) = random.randint(1, 100)
            - MO (Momentum) = 0 (always 0 at game init)
            - EM (Emotion) = random.randint(1, 100)
        """
        # NG is always 1.0 at start of new mode instance
        attributes["NG"] = 1.0
        attributes["anchor_NG"] = 1.0
        
        # CH (Character) is random 1-100
        attributes["CH"] = random.randint(1, 100)
        attributes["anchor_CH"] = attributes["CH"]
        
        # MO (Momentum) is always 0 at game init for all game modes
        attributes["MO"] = 0
        attributes["anchor_MO"] = 0
        
        # EM is random 1-100
        attributes["EM"] = random.randint(1, 100)
        attributes["anchor_EM"] = attributes["EM"]
        
        return attributes

    def _init_stats(self):
        stats = {
            "game": {stat: 0 for stat in BOX_SCORE_KEYS},
            "season": {stat: 0 for stat in BOX_SCORE_KEYS},
            "career": {stat: 0 for stat in BOX_SCORE_KEYS},
        }
        # Outlet_Score_List is an array (game-specific), initialize as empty array
        for level in ["game", "season", "career"]:
            stats[level]["Outlet_Score_List"] = []
        return stats

    def record_stat(self, stat, amount=1):
        # 🔍 DEBUG: Log stat recording for OREB/DREB to trace putback miss bug
        if stat in {"OREB", "DREB"}:
            player_name = getattr(self, "name", None) or f"{getattr(self, 'first_name', '')} {getattr(self, 'last_name', '')}".strip()
            player_id = getattr(self, "player_id", None)
            obj_id = id(self)
            oreb_before = self.stats["game"].get("OREB", 0)
            dreb_before = self.stats["game"].get("DREB", 0)
            reb_before = self.stats["game"].get("REB", 0)
            logging.warning(f"🔍 [PLAYER.record_stat] ENTRY: {player_name} (ID: {player_id}), Object ID: {obj_id}, "
                          f"Stat: {stat}, Amount: {amount}, OREB: {oreb_before}, DREB: {dreb_before}, REB: {reb_before}")
        
        self.stats["game"][stat] += amount
        if stat in {"FGM", "3PTM", "FTM"}:
            s = self.stats["game"]
            s["PTS"] = (2 * s["FGM"]) + s["3PTM"] + s["FTM"]
        elif stat in {"OREB", "DREB"}:
            s = self.stats["game"]
            s["REB"] = s["OREB"] + s["DREB"]
            # 🔍 DEBUG: Log after REB calculation
            player_name = getattr(self, "name", None) or f"{getattr(self, 'first_name', '')} {getattr(self, 'last_name', '')}".strip()
            player_id = getattr(self, "player_id", None)
            obj_id = id(self)
            oreb_after = s.get("OREB", 0)
            dreb_after = s.get("DREB", 0)
            reb_after = s.get("REB", 0)
            logging.warning(f"🔍 [PLAYER.record_stat] EXIT: {player_name} (ID: {player_id}), Object ID: {obj_id}, "
                          f"OREB: {oreb_after}, DREB: {dreb_after}, REB: {reb_after} (calculated from OREB+DREB)")

    def get_fatigue_decay_amount(self, omit_zeros=False):
        """
        Calculate fatigue decay amount based on ND (Natural Durability) attribute.
        
        Args:
            omit_zeros: If True, removes all zero values from the depletion list before selection.
                        Used for defensive players on HCT/FCP turns to ensure they always lose some energy.
        
        Returns:
            Random depletion amount based on ND thresholds.
        """
        nd = self.attributes.get("ND", 50)  # Default to 50 if not set

        if nd >= 89:
            decay_list = [0, 0.01]
        elif nd >= 79:
            decay_list = [0, 0.01, 0.01]
        elif nd >= 69:
            decay_list = [0, 0, 0.01, 0.01, 0.01]
        elif nd >= 59:
            decay_list = [0, 0, 0.01, 0.01, 0.02]
        elif nd >= 49:
            decay_list = [0, 0.01, 0.01, 0.01, 0.02]
        elif nd >= 39:
            decay_list = [0, 0.01, 0.01, 0.02, 0.02]
        elif nd >= 29:
            decay_list = [0, 0.01, 0.01, 0.02, 0.03]
        elif nd >= 19:
            decay_list = [0, 0.01, 0.02, 0.02, 0.03]
        elif nd >= 9:
            decay_list = [0, 0.01, 0.02, 0.02, 0.02, 0.03]
        else:
            decay_list = [0, 0.01, 0.02, 0.02, 0.03, 0.03]
        
        # ✅ FCP/HCT DEFENSIVE PLAYERS: Omit zeros for defensive players on pressure defense turns
        if omit_zeros:
            decay_list = [x for x in decay_list if x > 0]
            # If list becomes empty (shouldn't happen, but safety check), use minimum depletion
            if not decay_list:
                decay_list = [0.01]
        
        return random.choice(decay_list)
    
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
        try:
            attrs = object.__getattribute__(self, "attributes")
        except AttributeError:
            raise AttributeError(f"{item} not found")
        if item in attrs:
            return attrs[item]
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
        self.stats["game"]["Outlet_Score_List"] = []  # Outlet_Score_List is an array, not an integer

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


def player_to_dict(player):
    """Return a minimal serializable representation of a Player."""
    if player is None:
        return None
    team = getattr(player, "team", None)
    team_name = getattr(team, "name", team)
    data = {
        "player_id": getattr(player, "player_id", None),
        "name": getattr(player, "name", None),
        "team": team_name,
    }
    if DEBUG_SERIALIZATION:
        print(f"[DEBUG_SERIALIZATION] player_to_dict keys: {list(data.keys())}")
    return data

    
    




