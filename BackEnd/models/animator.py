from BackEnd.utils.shared import get_player_by_pos, get_player_position
from BackEnd.utils.shared_defense import (
    assign_ball_handler_defender_coords,
    assign_non_bh_defender_coords
)
from collections import defaultdict
from BackEnd.constants import HCO_STRING_SPOTS
import random

class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def capture_halfcourt_animation(self, roles, event_step=None):
        offense_team = self.game.offense_team
        defense_team = self.game.defense_team
        off_lineup = offense_team.lineup
        def_lineup = defense_team.lineup
        aggression_call = defense_team.strategy_calls.get("aggression_call", "normal")

        steps = roles["steps"]
        action_timeline = roles["action_timeline"]
        shooter = roles["shooter"]
        ball_handler = roles["ball_handler"]

        if event_step is not None:
            steps = steps[:event_step + 1]

        animations = []

        # ----------------
        # 🔵 OFFENSIVE ANIMATION
        # ----------------
        bh_pos = get_player_position(off_lineup, ball_handler)
        ball_handler_end_coords = None

        for pos, player in off_lineup.items():
            timeline = action_timeline.get(player, [])
            if not timeline:
                continue

            timeline.sort(key=lambda tup: tup[0])
            first_spot = timeline[0][2]
            last_spot = timeline[-1][2]
            start_coords = HCO_STRING_SPOTS.get(first_spot, {"x": 64, "y": 25})
            end_coords = HCO_STRING_SPOTS.get(last_spot, start_coords)

            if pos == bh_pos:
                ball_handler_end_coords = end_coords  # capture for defensive positioning

            actions = [{"timestamp": t, "type": action} for t, action, _ in timeline]

            animations.append({
                "playerId": player.player_id,
                "start": start_coords,
                "end": end_coords,
                "actions": actions,
                "hasBall": player == shooter,
                "duration": timeline[-1][0]
            })

        for pos, defender in def_lineup.items():
            if pos == bh_pos:
                def_coords = assign_ball_handler_defender_coords(ball_handler_end_coords, aggression_call)
                action_type = "GUARD_BALL"
            else:
                off_player = off_lineup[pos]
                last_spot = next((
                    step[2] for step in reversed(action_timeline.get(off_player, []))
                    if step[2] is not None
                ), "top_of_the_key")

                end_coords = HCO_STRING_SPOTS.get(last_spot, {"x": 64, "y": 25})

                def_coords = assign_non_bh_defender_coords(end_coords, ball_handler_end_coords, aggression_call)
                action_type = "GUARD_OFFBALL"

            animations.append({
                "playerId": defender.player_id,
                "start": def_coords,
                "end": def_coords,
                "actions": [{"timestamp": 0, "type": action_type}],
                "hasBall": False,
                "duration": steps[-1]["timestamp"] if steps else 800
            })

        self.latest_packet = animations
        print(f"[DEBUG] Generated {len(animations)} animations")

        return animations

    def get_latest_animation_packet(self):
        return self.latest_packet