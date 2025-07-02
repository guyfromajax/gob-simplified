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
            {"x": 74, "y": 19}, {"x": 80, "y": 32}, {"x": 80, "y": 19}, {"x": 86, "y": 32}, {"x": 86, "y": 19},
            {"x": 74, "y": 26}, {"x": 74, "y": 25}, {"x": 80, "y": 26}, {"x": 80, "y": 25}, {"x": 74, "y": 38},
        ]

        # "lower highPost": {"x": 74, "y": 19},
        # "upper midPost": {"x": 80, "y": 32}, 
        # "lower midPost": {"x": 80, "y": 19},
        # "upper lowPost": {"x": 86, "y": 32}, 
        # "lower lowPost": {"x": 86, "y": 19}, 
        # "upper topLane": {"x": 74, "y": 26}, 
        # "lower topLane": {"x": 74, "y": 25},
        # "upper midLane": {"x": 80, "y": 26}, 
        # "lower midLane": {"x": 80, "y": 25}, #finished through here
        # "upper apex": {"x": 74, "y": 43}, 

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
