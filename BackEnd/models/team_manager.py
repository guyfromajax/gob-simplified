import random
from BackEnd.db import players_collection, teams_collection
from BackEnd.utils.roster_loader import load_roster
from BackEnd.models.player import Player
from BackEnd.constants import PLAYCALLS

class TeamManager:
    def __init__(self, name: str, is_home_team=False):
        self.name = name
        self.is_home_team = is_home_team
        self.players = self._load_roster()
        self.lineup = self._load_lineup()
        
        team_doc = teams_collection.find_one({"name": name})
        if not team_doc:
            print(f"⚠️ No team document found for team: {name}")
        self.team_id = team_doc.get("team_id") if team_doc else None
        self.primary_color = team_doc.get("primary_color", "#000000") if team_doc else "#000000"
        self.secondary_color = team_doc.get("secondary_color", "#ffffff") if team_doc else "#ffffff"

        self.points = 0
        self.points_by_quarter = [0, 0, 0, 0]
        self.team_fouls = 0
        self.stats = {}
        self.scouting_data = self._init_scouting_data()

        self.strategy_settings = self._init_strategy_settings()
        self.strategy_calls = {}
        self.playcall_settings = self._init_playcall_settings()
        self.playcall_weights = self.playcall_settings.copy()

        self.playcall_tracker = {pc: 0 for pc in PLAYCALLS}
        self.defense_playcall_tracker = {"Man": 0, "Zone": 0}
        self.team_attributes = self._init_team_attributes()

    def _load_roster(self):
        _, players = load_roster(self.name)
        return [Player(p) for p in players]

    def _load_lineup(self):
        # If you’re still defining self.players before this
        return {}  # default to empty dict — lineup will be set later


    def get_player(self, position):
        return self.players.get(position)

    def get_all_players(self):
        return self.players.values()

    def _init_strategy_settings(self):
        return {
            "defense": random.randint(0, 4),
            "tempo": random.randint(0, 4),
            "aggression": random.randint(0, 4),
            "fast_break": random.randint(0, 4),
            "half_court_trap": 0,
            "full_court_press": 0,
        }

    def _init_playcall_settings(self):
        return {pc: random.randint(1, 4) for pc in PLAYCALLS}

    def _init_team_attributes(self):
        return {
            "shot_threshold": random.randint(150, 250),
            "ft_shot_threshold": random.randint(150, 250),
            "turnover_threshold": random.randint(-250, -150),
            "foul_threshold": random.randint(40, 90),
            "rebound_modifier": random.choice([0.8, 0.9, 1.0, 1.1, 1.2]),
            "momentum_score": random.randint(0,20),
            "momentum_delta": random.choice([1,2,3,4,5]),
            "offensive_efficiency": random.randint(1,10),
            "offensive_adjust": random.randint(1,10),
            "o_tendency_reads": random.randint(1,10),
            "d_tendency_reads": random.randint(1,10),
            "team_chemistry": random.randint(7,25)
        }

    def _init_scouting_data(self):
        return {
            "offense": {
                "Fast_Break_Entries": 0,
                "Fast_Break_Success": 0,
                "Playcalls": {pc: {"used": 0, "success": 0} for pc in PLAYCALLS}
            },
            "defense": {
                "Man": {"used": 0, "success": 0},
                "Zone": {"used": 0, "success": 0},
                "vs_Fast_Break": {"used": 0, "success": 0}
            }
        }

    def record_team_foul(self):
        self.team_fouls += 1

    def update_team_stats(self):
        totals = {}
        for player in self.players.values():
            for stat, val in player.stats["game"].items():
                totals[stat] = totals.get(stat, 0) + val
        self.stats = totals

    def reset_for_new_game(self):
        self.points_by_quarter = [0, 0, 0, 0]
        self.team_fouls = 0
        self.stats = {}
        self.scouting_data = self._init_scouting_data()
        for player in self.players.values():
            player.stats["game"] = {stat: 0 for stat in player.stats["game"]}
            player.reset_energy()

    def get_player(self, position):
        return self.lineup.get(position)

    def get_all_lineup_players(self):
        return self.lineup.values()

    def get_full_roster(self):
        return self.players

    def get_team_game_stats(self):
        team_stats = {
            "PTS": 0,
            "FGM": 0,
            "FGA": 0,
            "3PTM": 0,
            "3PTA": 0,
            "FTM": 0,
            "FTA": 0,
            "OREB": 0,
            "DREB": 0,
            "REB": 0,
            "AST": 0,
            "STL": 0,
            "BLK": 0,
            "TO": 0,
            "F": 0,
        }

        for player in self.lineup.values():
            stats = player.stats["game"]
            for key in team_stats:
                team_stats[key] += stats.get(key, 0)

        team_stats["REB"] = team_stats["OREB"] + team_stats["DREB"]
        return team_stats

