from BackEnd.utils.shared import get_player_by_pos


class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def capture(self, result):
        packet = []

        start_dict = result.get("start_coords", {})
        end_dict = result.get("end_coords", {})

        all_players = {**self.game.home_team.lineup, **self.game.away_team.lineup}

        for pos, player in all_players.items():
            # Fallback to player.coords if not in start_coords
            start = start_dict.get(pos, getattr(player, "coords", {"x": 0, "y": 0}))
            end = end_dict.get(pos, start)

            # Update the player's internal coords for continuity
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
