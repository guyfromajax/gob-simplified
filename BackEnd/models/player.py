# BackEnd/models/player.py

from BackEnd.constants import ALL_ATTRS, BOX_SCORE_KEYS, LEAGUE_MEDIAN_HEIGHT_IN, MALLEABLE_ATTRS
from BackEnd.constants.momentum import (
    MO_CONSECUTIVE_THRESHOLD,
    MO_CONSECUTIVE_DELTA,
    MO_OREB_THRESHOLD,
    MO_OREB_DELTA,
    MO_MIN,
    MO_MAX,
    MO_NG_DECAY_BONUS_PCT_PER_LEVEL,
)
import uuid
import os
from BackEnd.utils.sim_random import sim_rng as random

DEBUG_SERIALIZATION = os.getenv("DEBUG_SERIALIZATION")

# MO (Momentum) scale is the single source of truth in BackEnd/constants/momentum.py
# (MO_MIN/MO_MAX). This is the canonical hard bound, enforced on every Player load so
# no persisted/legacy value can ever exceed the scale. See Player_Momentum_System.md.


def clamp_mo(value):
    """Clamp a Momentum value to its defined [MO_MIN, MO_MAX] scale (0 on bad input)."""
    try:
        return max(MO_MIN, min(MO_MAX, int(value)))
    except (TypeError, ValueError):
        return 0


# Fatigue (NG) decay tiers by ND (Endurance), ordered high-ND → low-ND
# (least → most depletion). A player's tier is the first whose threshold his ND
# meets (last tier = ND < 9). The MO momentum bonus pulls the decay from the
# highest tier (index 0, ND>89). See Energy_System.md § Depletion Calculation.
_ND_DECAY_TIERS = [
    (89, [0, 0.01]),
    (79, [0, 0.01, 0.01]),
    (69, [0, 0, 0.01, 0.01, 0.01]),
    (59, [0, 0, 0.01, 0.01, 0.02]),
    (49, [0, 0.01, 0.01, 0.01, 0.02]),
    (39, [0, 0.01, 0.01, 0.02, 0.02]),
    (29, [0, 0.01, 0.01, 0.02, 0.03]),
    (19, [0, 0.01, 0.02, 0.02, 0.03]),
    (9, [0, 0.01, 0.02, 0.02, 0.02, 0.03]),
    (0, [0, 0.01, 0.02, 0.02, 0.03, 0.03]),
]


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
        self.height = data.get("height", data.get("HT", LEAGUE_MEDIAN_HEIGHT_IN))
        self.weight = data.get("weight", data.get("WT", 200))
        self.attributes = self._extract_attributes(data)
        self.jersey = data.get("jersey", 0)
        self.year = data.get("year", "")
        self.photo = data.get("photo", None)  # Player headshot image path
        # Display-only portrait contract. Practice Squad recruits resolve their
        # white master by image_id; signed/league players resolve by player_id.
        self.portrait_source = data.get("portrait_source", "player")
        self.image_id = data.get("image_id")
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

        # Hard-bound MO to its defined scale before anchors are derived, so every
        # Player the engine/UI uses (and any value re-persisted from one) stays in range.
        if "MO" in attrs:
            attrs["MO"] = clamp_mo(attrs["MO"])

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
    def randomize_game_attributes(attributes: dict, *, preserve_character: bool = False) -> dict:
        """
        Initialize player attributes for a new mode instance.
        Copies exact values from universal collection for most attributes,
        then randomizes NG, CH, MO, and EM according to mode initialization rules.
        
        Should be called when initializing players for a new Single Game, Tournament, or Franchise.
        
        Args:
            attributes: Player attributes dict (from universal players collection)
            preserve_character: When True, keep an existing CH value (e.g. recruit generation).
            
        Returns:
            Modified attributes dict with:
            - Exact values copied for: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT
            - NG = 1.0
            - CH (Character) = random.randint(1, 100) unless preserve_character and CH set
            - MO (Momentum) = 0 (always 0 at game init)
            - EM (Emotion) = random.randint(1, 100)
        """
        # NG is always 1.0 at start of new mode instance
        attributes["NG"] = 1.0
        attributes["anchor_NG"] = 1.0
        
        if preserve_character and attributes.get("CH") is not None:
            attributes["anchor_CH"] = attributes["CH"]
        else:
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
        # Shot_Result_List: per-game field-goal/putback outcomes (True=made,
        # False=miss/block). Shooting-foul misses & free throws excluded. Game-
        # only — never aggregated to season/career (intentionally not in
        # BOX_SCORE_KEYS). See Player_Momentum_System.md.
        stats["game"]["Shot_Result_List"] = []
        return stats

    def record_stat(self, stat, amount=1):
        self.stats["game"][stat] += amount
        if stat in {"FGM", "3PTM", "FTM"}:
            from BackEnd.utils.shared import derive_pts_from_shooting_stats

            s = self.stats["game"]
            s["PTS"] = derive_pts_from_shooting_stats(s)
        elif stat in {"OREB", "DREB"}:
            s = self.stats["game"]
            s["REB"] = s["OREB"] + s["DREB"]
            # Momentum: a player's 5th OREB of the game (and each one after) → +MO.
            if stat == "OREB" and amount > 0 and s["OREB"] >= MO_OREB_THRESHOLD:
                self.add_momentum(MO_OREB_DELTA)

    def add_momentum(self, delta):
        """Apply a clamped change to this player's in-game momentum (MO).
        Writes attributes["MO"] only (never anchor_MO); clamped to ±10."""
        self.attributes["MO"] = clamp_mo(self.attributes.get("MO", 0) + int(delta))

    def get_fatigue_decay_amount(self, omit_zeros=False):
        """
        Calculate fatigue decay amount based on ND (Endurance) attribute.
        
        Args:
            omit_zeros: If True, removes all zero values from the depletion list before selection.
                        Used for defensive players on HCT/FCP turns to ensure they always lose some energy.
        
        Returns:
            Random depletion amount based on ND thresholds.
        """
        nd = self.attributes.get("ND", 50)  # Default to 50 if not set

        # Ordered high-ND → low-ND tiers (threshold, decay_list). Higher ND = less
        # depletion. The player's tier is the first whose threshold ND meets.
        tier_index = next(
            (i for i, (threshold, _) in enumerate(_ND_DECAY_TIERS) if nd >= threshold),
            len(_ND_DECAY_TIERS) - 1,
        )

        # Momentum bonus (Player_Momentum_System.md / Energy_System.md): MO > 0
        # gives a |MO| × MO_NG_DECAY_BONUS_PCT_PER_LEVEL % chance to take the
        # turn's decay from the HIGHEST tier (index 0, ND>89 — least fatigue),
        # capped at the top tier. MO <= 0 → normal decay. Each player rolls
        # independently.
        mo = int(self.attributes.get("MO", 0) or 0)
        if mo > 0 and tier_index > 0:
            chance = min(100, mo * MO_NG_DECAY_BONUS_PCT_PER_LEVEL)
            if random.randint(1, 100) <= chance:
                tier_index = 0

        decay_list = list(_ND_DECAY_TIERS[tier_index][1])

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
        self.stats["game"]["Shot_Result_List"] = []  # per-game shot outcomes (array, not numeric)

    def record_shot_result(self, made):
        """Append a field-goal/putback outcome to the per-game Shot_Result_List
        (True=made, False=missed/blocked). Callers exclude shooting-foul misses
        and free throws. Defensive: ensures the entry is a list before append.

        Momentum: on the player's 3rd consecutive make (and each after) → +MO;
        3rd consecutive miss (and each after) → −MO. Streak is the trailing run
        of identical results in Shot_Result_List (self-relative, whole game;
        excluded shots are simply absent, so they don't break a streak)."""
        srl = self.stats["game"].get("Shot_Result_List")
        if not isinstance(srl, list):
            srl = []
            self.stats["game"]["Shot_Result_List"] = srl
        made = bool(made)
        srl.append(made)

        run = 0
        for prior in reversed(srl):
            if prior == made:
                run += 1
            else:
                break
        if run >= MO_CONSECUTIVE_THRESHOLD:
            self.add_momentum(MO_CONSECUTIVE_DELTA if made else -MO_CONSECUTIVE_DELTA)

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

    
    



