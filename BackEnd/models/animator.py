from BackEnd.utils.shared import get_player_by_pos
from collections import defaultdict
from BackEnd.constants import HCO_STRING_SPOTS
import random

class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def capture_halfcourt_animation(self, roles, event_step=None):
        offense_team = self.game.offense_team
        lineup = offense_team.lineup
        steps = roles["steps"]
        action_timeline = roles["action_timeline"]
        shooter = roles["shooter"]

        if event_step is not None:
            steps = steps[:event_step + 1]

        animations = []

        for pos, player in lineup.items():
            timeline = action_timeline.get(player, [])
            if not timeline:
                continue

            timeline.sort(key=lambda tup: tup[0])
            first_spot = timeline[0][2]
            last_spot = timeline[-1][2]
            start_coords = HCO_STRING_SPOTS.get(first_spot, {"x": 64, "y": 25})
            end_coords = HCO_STRING_SPOTS.get(last_spot, start_coords)

            actions = [
                {"timestamp": t, "type": action}
                for t, action, _ in timeline
            ]

            animations.append({
                "playerId": player.player_id,
                "start": start_coords,
                "end": end_coords,
                "actions": actions,
                "hasBall": player == shooter,
                "duration": timeline[-1][0]
            })

        self.latest_packet = animations
        print(f"[DEBUG] Generated {len(animations)} animations")

        return animations
    
    def capture(self, result):
        packet = []

        # Predefined spread of destination points
        spread = [
            {"x": 80, "y": 40}, {"x": 80, "y": 11}, {"x": 89, "y": 40}, {"x": 89, "y": 11}, {"x": 80, "y": 36},
            {"x": 80, "y": 15}, {"x": 89, "y": 36}, {"x": 89, "y": 15}, {"x": 88, "y": 40}, {"x": 88, "y": 11},
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
