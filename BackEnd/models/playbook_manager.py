import random
from BackEnd.constants import STRATEGY_CALL_DICTS
from BackEnd.utils.shared import weighted_random_from_dict

class PlaybookManager:
    def __init__(self, team):
        self.team = team
        self.scouting = team.scouting_data
        self.playcalls = self.scouting.get("playcalls", {})
        self.fast_break_tendency = self.scouting.get("fast_break_tendency", 0.0)

    def get_offensive_playcall(self):
        return self.playcalls.get("offense", "Base")

    def get_defensive_playcall(self):
        return self.playcalls.get("defense", "Man")

    def get_fast_break_tendency(self):
        return self.fast_break_tendency

    def record_playcall_result(self, call_type, call_name, success):
        """
        Tracks usage and success of playcalls in the team's scouting data.
        call_type: 'offense' or 'defense'
        call_name: e.g., 'Set', 'Zone', 'Fast Break'
        success: bool
        """
        playcall_data = self.scouting.get("Playcalls", {}).get(call_name, {"used": 0, "success": 0})
        playcall_data["used"] += 1
        if success:
            playcall_data["success"] += 1
        self.scouting["Playcalls"][call_name] = playcall_data


