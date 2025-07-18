from enum import Enum
from typing import List, Dict
import random
from bson import ObjectId
from pymongo.collection import Collection
from BackEnd.db import players_collection, teams_collection, training_log_collection  # adjust if needed
from datetime import datetime
from bson.errors import InvalidId




class TrainingCategory(Enum):
    OFFENSIVE_DRILLS = "offensive_drills"
    DEFENSIVE_DRILLS = "defensive_drills"
    TECHNICAL_DRILLS = "technical_drills"
    WEIGHT_ROOM = "weight_room"
    CONDITIONING = "conditioning"
    TEAM_BUILDING = "team_building"
    FREE_THROWS = "free_throws"
    FILM_STUDY = "film_study"
    SCRIMMAGE = "scrimmage"
    BREAKS = "breaks"

class TrainingManager:
    def __init__(self, team_name: str):
        self.team_name = team_name
        self.team_doc = None
        self.players = []

    def load_team_and_players(self):
        self.team_doc = teams_collection.find_one({"name": self.team_name})
        # print(self.team_name)
        print(self.team_doc)
        if not self.team_doc:
            raise ValueError(f"❌ No team found with name {self.team_name}")

        valid_ids = self.team_doc.get("player_ids", [])
        self.players = list(players_collection.find({"_id": {"$in": valid_ids}}))

        if not self.players:
            raise ValueError(f"❌ No players found for team {self.team_name}")
        return self

    def create_training_session(self, session_type: str = "in-season", date: str = None):
        if not self.team_doc:
            raise RuntimeError("⚠️ Must load team before creating training session.")
        date = date or datetime.now().strftime("%Y-%m-%d")
        return TrainingSession(session_type=session_type, date=date, team_id=str(self.team_doc["_id"]))

    def run_and_save_session(self, training_session: "TrainingSession"):
        updates = training_session.apply_training(self.players, self.team_doc)
        save_training_results(
            player_updates=updates,
            players_collection=players_collection,
            team_doc=self.team_doc,
            teams_collection=teams_collection,
            training_session=training_session,
            training_log_collection=training_log_collection
        )
        return training_session.log


class Allocation:
    def __init__(self, total_points: int, subtypes: Dict[str, int] = None):
        self.total_points = total_points
        self.subtypes = subtypes or {}  # e.g., {"inside": 1, "outside": 1}

    def to_dict(self):
        return {
            "total_points": self.total_points,
            "subtypes": self.subtypes
        }

class TrainingSession:
    def __init__(self, session_type: str, date: str, team_id: str):
        self.session_type = session_type  # 'preseason' or 'in-season'
        self.date = date
        self.team_id = team_id
        self.practice_points = 24
        self.allocations = {}  # category: Allocation object
        self.log = []

    def apply_training(self, players: List[dict], team: dict) -> List[dict]:
        player_updates = {player["_id"]: {} for player in players}
        all_players_by_id = {player["_id"]: player for player in players}

        # === Phase 1: Apply trait changes from training ===
        for category, allocation in self.allocations.items():
            # TEAM trait changes
            if category in ["team_building", "film_study", "scrimmage"]:
                trait = self._get_team_trait_from_category(category)
                change = self._get_trait_change(allocation.total_points, team_level=True)
                team[trait] = team.get(trait, 0) + change
                self.log.append(f"Team {trait} changed by {change}")
                continue

            # PLAYER trait changes
            affected_traits = self._get_affected_traits(category)
            for trait in affected_traits:
                for player in players:
                    points = self._resolve_player_points(player, category, trait, allocation)
                    if points == 0:
                        continue
                    delta = self._get_trait_change(points)
                    anchor_field = f"anchor_{trait}"
                    player_updates[player["_id"]][anchor_field] = player["attributes"].get(anchor_field, 0) + delta
                    self.log.append(f"{player['first_name']} {player['last_name']} {anchor_field} +{delta}")

        # === Phase 2: Apply Break Effects ===
        break_points = self.allocations.get("breaks", Allocation(0)).total_points
        self._handle_break_effects(break_points, player_updates, all_players_by_id)

        # === Phase 3: Apply NG changes ===
        for player in players:
            ng_loss = self._get_ng_loss_for_breaks(break_points)
            if ng_loss > 0:
                player["attributes"]["NG"] = round(player["attributes"].get("NG", 0) - ng_loss, 2)
                self.log.append(f"{player['first_name']} {player['last_name']} NG decreased by {ng_loss}")

        # Return updated documents
        return player_updates

    def _get_trait_change(self, points: int, team_level=False) -> int:
        # Probabilities per point level
        lookup = {
            0: [(0, 0.25), (-1, 0.50), (-2, 0.20), (-3, 0.05)],
            1: [(2, 0.10), (1, 0.50), (0, 0.20), (-1, 0.15), (-2, 0.05)],
            2: [(4, 0.025), (3, 0.075), (2, 0.50), (1, 0.20), (0, 0.15), (-1, 0.05)],
            3: [(5, 0.025), (4, 0.075), (3, 0.35), (2, 0.35), (1, 0.125), (0, 0.05), (-1, 0.025)],
            4: [(5, 0.05), (4, 0.125), (3, 0.325), (2, 0.325), (1, 0.125), (0, 0.025), (-1, 0.025)],
        }
        if points >= 5:
            dist = [(5, 0.075), (4, 0.125), (3, 0.325), (2, 0.30), (1, 0.15), (0, 0.0125), (-1, 0.0125)]
        else:
            dist = lookup.get(points, [(0, 1.0)])

        outcomes, probs = zip(*dist)
        result = random.choices(outcomes, probs)[0]
        return result * 10 if team_level else result

    def _handle_break_effects(self, break_points: int, updates: Dict, players_by_id: Dict):
        roll_map = {
            0: (6, 2),
            1: (4, 2),
            2: (2, 1),
        }
        if break_points >= 3:
            return  # No penalties

        num_players, traits_to_clear = roll_map.get(break_points, (0, 0))
        affected_players = random.sample(list(updates.keys()), min(num_players, len(updates)))

        for pid in affected_players:
            trait_keys = list(updates[pid].keys())
            to_zero = random.sample(trait_keys, min(traits_to_clear, len(trait_keys)))
            for trait in to_zero:
                updates[pid][trait] = players_by_id[pid]["attributes"][trait]
                self.log.append(f"{players_by_id[pid]['first_name']} {players_by_id[pid]['last_name']} had training gains removed from {trait}")

    def _get_ng_loss_for_breaks(self, break_points: int) -> float:
        roll = random.random()
        if break_points == 0:
            return self._roll_ng_loss(roll, [0.10, 0.30, 0.60, 1.00], [0, 0.01, 0.02, 0.03])
        elif break_points == 1:
            return self._roll_ng_loss(roll, [0.30, 0.70, 0.90, 1.00], [0, 0.01, 0.02, 0.03])
        elif break_points == 2:
            return self._roll_ng_loss(roll, [0.80, 0.95, 1.00], [0, 0.01, 0.02])
        else:
            return self._roll_ng_loss(roll, [0.90, 1.00], [0, 0.01])

    def _roll_ng_loss(self, roll: float, thresholds: List[float], values: List[float]) -> float:
        for i, threshold in enumerate(thresholds):
            if roll <= threshold:
                return values[i]
        return 0.0

    def _resolve_player_points(self, player, category, trait, allocation):
        """Determine how many points this player got toward this trait based on category"""
        if category in ["offensive_drills", "defensive_drills"]:
            return allocation.subtypes.get("inside" if trait in ["SC", "ID"] else "outside", 0)
        if category == "technical_drills":
            return allocation.subtypes.get(trait, 0)
        if category == "weight_room":
            return allocation.subtypes.get(trait, 0)
        if category in ["conditioning", "free_throws", "film_study", "team_building"]:
            # All players get full points
            return allocation.total_points
        return 0

    def _get_affected_traits(self, category: str):
        return {
            "offensive_drills": ["SC", "SH"],
            "defensive_drills": ["ID", "OD"],
            "technical_drills": ["PS", "BH", "RB"],
            "weight_room": ["ST", "AG"],
            "conditioning": ["ND"],
            "free_throws": ["FT"],
            "film_study": ["IQ"],
            "team_building": ["EM"],
        }.get(category, [])

    def _get_team_trait_from_category(self, category: str) -> str:

        return {
            "team_building": "team_chemistry",
            "film_study": "defense_threshold",
            "scrimmage": "offensive_efficiency"
        }.get(category, "team_chemistry")  # Default fallback
    
def save_training_results(
    player_updates: dict,
    players_collection: Collection,
    team_doc: dict,
    teams_collection: Collection,
    training_session: TrainingSession,
    training_log_collection: Collection = None
):
    # --- Player Updates ---
    for player_id, updates in player_updates.items():
        update_fields = {f"attributes.{k}": v for k, v in updates.items()}
        players_collection.update_one({"_id": ObjectId(player_id)}, {"$set": update_fields})

    # --- Team Updates ---
    TEAM_FIELDS = [
        "team_chemistry", "offensive_efficiency", "offensive_adjust",
        "defense_threshold", "shot_threshold", "turnover_threshold",
        "foul_threshold", "rebound_modifier", "o_tendency_reads", "d_tendency_reads"
    ]
    team_fields = {k: v for k, v in team_doc.items() if k in TEAM_FIELDS}
    if team_fields:
        teams_collection.update_one({"_id": team_doc["_id"]}, {"$set": team_fields})

    # --- Optional Training Log ---
    if training_log_collection:
        training_log_collection.insert_one(training_session.to_dict())

# class TrainingManager:
#     def __init__(self, team_name: str):
#         self.team_name = team_name
#         self.team_doc = None
#         self.players = []

#     def load_team_and_players(self):
#         self.team_doc = teams_collection.find_one({"name": self.team_name})
#         if not self.team_doc:
#             raise ValueError(f"❌ No team found with name {self.team_name}")

#         player_ids = self.team_doc.get("player_ids", [])
#         self.players = list(players_collection.find({"_id": {"$in": [ObjectId(pid) for pid in player_ids]}}))

#         if not self.players:
#             raise ValueError(f"❌ No players found for team {self.team_name}")
#         return self

#     def create_training_session(self, session_type: str = "in-season", date: str = None):
#         if not self.team_doc:
#             raise RuntimeError("⚠️ Must load team before creating training session.")

#         date = date or datetime.now().strftime("%Y-%m-%d")
#         session = TrainingSession(session_type=session_type, date=date, team_id=str(self.team_doc["_id"]))
#         return session

#     def run_and_save_session(self, training_session: TrainingSession):
#         updates = training_session.apply_training(self.players, self.team_doc)
#         save_training_results(
#             player_updates=updates,
#             players_collection=players_collection,
#             team_doc=self.team_doc,
#             teams_collection=teams_collection,
#             training_session=training_session,
#             training_log_collection=training_log_collection
#         )
#         return training_session.log


# 🧪 Example Usage
# You could use this in your test or simulation pipeline:

# python
# Copy
# Edit
# manager = TrainingManager("Four Corners").load_team_and_players()

# session = manager.create_training_session(session_type="preseason")
# session.assign_points("offensive_drills", {"inside": 2, "outside": 1})
# session.assign_points("conditioning", 3)
# session.assign_points("breaks", 1)

# log = manager.run_and_save_session(session)

# for entry in log:
#     print(entry)

