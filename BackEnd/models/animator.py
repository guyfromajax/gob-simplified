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
            {"x": 10, "y": 10}, {"x": 20, "y": 20}, {"x": 30, "y": 30}, {"x": 40, "y": 40}, {"x": 50, "y": 50},
            {"x": 60, "y": 40}, {"x": 70, "y": 30}, {"x": 80, "y": 20}, {"x": 90, "y": 10}, {"x": 25, "y": 25},
        ]

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
