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
            {"x": 80, "y": 40}, {"x": 80, "y": 11}, {"x": 89, "y": 40}, {"x": 89, "y": 11}, {"x": 80, "y": 36},
            {"x": 80, "y": 15}, {"x": 89, "y": 36}, {"x": 89, "y": 15}, {"x": 88, "y": 40}, {"x": 88, "y": 11},
        ]

        # "upper longAllen": {"x": 80, "y": 40}, 
        # "lower longAllen": {"x": 80, "y": 11},
        # "upper shortAllen": {"x": 89, "y": 40}, 
        # "lower shortAllen": {"x": 89, "y": 11},
        # "upper longBird": {"x": 80, "y": 36}, 
        # "lower longBird": {"x": 80, "y": 15},
        # "upper shortBird": {"x": 89, "y": 36}, 
        # "lower shortBird": {"x": 89, "y": 15},
        # "upper longBaseline": {"x": 88, "y": 40}, 
        # "lower longBaseline": {"x": 88, "y": 11},

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
