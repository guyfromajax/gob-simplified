from BackEnd.utils.shared import get_player_by_pos
import random

class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def capture(self, result):
        packet = []

        all_players = {**self.game.home_team.lineup, **self.game.away_team.lineup}

        for pos, player in all_players.items():
            start = getattr(player, "coords", {"x": 25, "y": 50})

            # TEMP: insert dummy movement for testing
            end = {"x": start["x"] + random.randint(5, 15), "y": start["y"] + random.randint(5, 15)}

            # Update player coords for continuity
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
