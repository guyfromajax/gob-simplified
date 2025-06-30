from BackEnd.utils.shared import get_player_by_pos
import random

class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def capture(self, result):
        packet = []
        all_players = {**self.game.home_team.lineup, **self.game.away_team.lineup}

        spread = [
            {"x": 10, "y": 10}, {"x": 20, "y": 20}, {"x": 30, "y": 30}, {"x": 40, "y": 40}, {"x": 50, "y": 50},
            {"x": 60, "y": 40}, {"x": 70, "y": 30}, {"x": 80, "y": 20}, {"x": 90, "y": 10}, {"x": 25, "y": 25},
        ]

        for i, (pos, player) in enumerate(all_players.items()):
            start = getattr(player, "coords", {"x": 25, "y": 50})
            end = {"x": spread[i]["x"], "y": spread[i]["y"]}
            player.set_coords(end["x"], end["y"])

            packet.append({
                "playerId": player.player_id,
                "start": start,
                "end": end,
                "event": result.get("result_type", "idle").lower(),
                "hasBall": player.player_id == result.get("ball_handler_id"),
                "duration": 600
            })

        self.latest_packet = packet



    def get_latest_animation_packet(self):
        return self.latest_packet
