class PlaybookManager:
    def __init__(self, scouting_data, team_name):
        self.scouting = scouting_data[team_name]
        self.playcalls = self.scouting.get("playcalls", {})
        self.fast_break_tendency = self.scouting.get("fast_break_tendency", 0.0)

    def get_offensive_playcall(self):
        return self.playcalls.get("offense", "Base")

    def get_defensive_playcall(self):
        return self.playcalls.get("defense", "Man")

    def get_fast_break_tendency(self):
        return self.fast_break_tendency