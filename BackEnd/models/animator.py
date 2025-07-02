from BackEnd.utils.shared import get_player_by_pos, get_player_position
from BackEnd.utils.shared_defense import (
    assign_ball_handler_defender_coords,
    assign_non_bh_defender_coords,
    get_away_player_coords
)
from collections import defaultdict
from BackEnd.constants import HCO_STRING_SPOTS, ACTIONS
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
        is_away_offense = offense_team.team_id == self.game.away_team.team_id
        print("Inside capture_halfcourt_animation")
        print(f"offense_team_id: {offense_team.team_id}")
        print(f"away_team_id: {self.game.away_team.team_id}")
        print(f"is_away_offense: {is_away_offense}")


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
            if is_away_offense:
                start_coords = get_away_player_coords(start_coords)
                end_coords = get_away_player_coords(end_coords)

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
            def_coords = None  # ✅ Safe default
            action_type = ACTIONS["GUARD_OFFBALL"]

            if pos == bh_pos:
                def_coords = assign_ball_handler_defender_coords(ball_handler_end_coords, aggression_call)
                action_type = ACTIONS["GUARD_BALL"]
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                last_spot = next(
                    (step[2] for step in reversed(action_timeline.get(off_player, [])) if step[2]),
                    "key"
                )
                o_coords = HCO_STRING_SPOTS.get(last_spot, HCO_STRING_SPOTS["key"])
                def_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call)
            else:
                print(f"[WARN] No offensive match for defender {pos}, skipping.")
                continue  # skip player if we can't map them

            # ✅ Only continue if def_coords is safe
            start = {
                "x": def_coords["x"] + random.choice([-2, -1, 0, 1, 2]),
                "y": def_coords["y"] + random.choice([-1, 0, 1])
            }

            animations.append({
                "playerId": defender.player_id,
                "start": start,
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