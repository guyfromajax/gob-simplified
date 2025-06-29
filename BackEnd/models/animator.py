class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def capture(self, result):
        packet = []

        start_dict = result.get("start_coords", {})
        end_dict = result.get("end_coords", {})

        for pos, start in start_dict.items():
            player = self.game.get_player_by_pos(pos)  # or lookup via offense/defense team

            if not player:
                continue

            end = end_dict.get(pos, start)

            packet.append({
                "playerId": player["playerId"],
                "start": start,
                "end": end,
                "event": result["result_type"].lower(),
                "hasBall": player["playerId"] == result.get("ball_handler_id"),
                "duration": 600  # adjust later if needed
            })

        self.latest_packet = packet

    def get_latest_animation_packet(self):
        return self.latest_packet
