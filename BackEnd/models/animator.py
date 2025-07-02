from BackEnd.utils.shared import get_player_by_pos
import random

class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def capture(self, result):
        packet = []

        # Predefined spread of destination points
        spread = [
            {"x": 64, "y": 25}, {"x": 68, "y": 37}, {"x": 68, "y": 14}, {"x": 73, "y": 42}, {"x": 73, "y": 9},
            {"x": 80, "y": 46}, {"x": 80, "y": 5}, {"x": 88, "y": 47}, {"x": 88, "y": 4}, {"x": 74, "y": 32},
        ]
        #  "top_of_the_key": {"x": 64, "y": random.randint(25,26)},
        # "upper midWing": {"x": 68, "y": 37}, 
        # "lower midWing": {"x": 68, "y": 14},
        # "upper wing": {"x": 73, "y": 42}, 
        # "lower wing": {"x": 73, "y": 9},
        # "upper midCorner": {"x": 80, "y": 46}, 
        # "lower midCorner": {"x": 80, "y": 5},
        # "upper corner": {"x": 88, "y": 47}, 
        # "lower corner": {"x": 88, "y": 4},
        # "upper highPost": {"x": 74, "y": 32}, 

        i = 0  # Index to assign spread coords

        for team in [self.game.home_team, self.game.away_team]:
            for pos, player in team.lineup.items():
                start = getattr(player, "coords", {"x": 25, "y": 50})
                end = spread[i % len(spread)]  # cycle through spread points

                player.set_coords(end["x"], end["y"])

                packet.append({
                    "playerId": player.player_id,
                    "start": start,
                    "end": end,
                    "event": result.get("result_type", "idle").lower(),
                    "hasBall": player.player_id == result.get("ball_handler_id"),
                    "duration": 600
                })

                i += 1

        self.latest_packet = packet



    def get_latest_animation_packet(self):
        return self.latest_packet
