from BackEnd.utils.shared import (
    get_player_by_pos, 
    get_player_position,
    get_away_player_coords,
)
from BackEnd.utils.shared_defense import (
    assign_bh_defender_coords,
    assign_non_bh_defender_coords
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
            start_coords = player.coords  # This reflects where they ended last turn
            end_coords = HCO_STRING_SPOTS.get(last_spot, start_coords)
            if is_away_offense:
                start_coords = get_away_player_coords(start_coords)
                end_coords = get_away_player_coords(end_coords)

            if pos == bh_pos:
                ball_handler_end_coords = end_coords  # capture for defensive positioning

            actions = [{"timestamp": t, "type": action} for t, action, _ in timeline]
            # movement = [{"timestamp": t, "spot": spot} for t, _, spot in timeline]
            movement = []
            for t, _, spot in timeline:
                coord = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
                if is_away_offense:
                    coord = get_away_player_coords(coord)
                movement.append({"timestamp": t, "coords": coord})

            animations.append({
                "playerId": player.player_id,
                "start": start_coords,
                "end": end_coords,
                "actions": actions,
                "movement": movement,
                "hasBall": player == shooter,
                "duration": timeline[-1][0]
            })

        for pos, defender in def_lineup.items():
            def_coords = None  # ✅ Safe default
            action_type = ACTIONS["GUARD_OFFBALL"]

            if pos == bh_pos:
                def_coords = assign_bh_defender_coords(ball_handler_end_coords, aggression_call, is_away_offense)
                action_type = ACTIONS["GUARD_BALL"]
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                last_spot = next(
                    (step[2] for step in reversed(action_timeline.get(off_player, [])) if step[2]),
                    "key"
                )
                o_coords = HCO_STRING_SPOTS.get(last_spot, HCO_STRING_SPOTS["key"])
                def_coords = def_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call, is_away_offense)
            else:
                print(f"[WARN] No offensive match for defender {pos}, skipping.")
                continue  # skip player if we can't map them

            # ✅ Only continue if def_coords is safe
            start = defender.coords
            if pos == bh_pos and steps:
                bh_start = steps[0].get("coords", ball_handler_end_coords)
                start = assign_bh_defender_coords(bh_start, aggression_call, is_away_offense)

            # ✅ Flip if away team has the ball so all coordinates are in the
            # same orientation as the offense
            if is_away_offense:
                def_coords = get_away_player_coords(def_coords)
                start = get_away_player_coords(start)

            movement = []
            if pos == bh_pos:
                for step in steps:
                    t = step["timestamp"]
                    bh_coords = step.get("coords", ball_handler_end_coords)
                    d_coords = assign_bh_defender_coords(bh_coords, aggression_call, is_away_offense)
                    if is_away_offense:
                        d_coords = get_away_player_coords(d_coords)
                    movement.append({"timestamp": t, "coords": d_coords})
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                timeline = action_timeline.get(off_player, [])
                for t, _, spot in timeline:
                    o_coords = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
                    d_coords = def_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call, is_away_offense)
                    if is_away_offense:
                        d_coords = get_away_player_coords(d_coords)
                    movement.append({"timestamp": t, "coords": d_coords})

            animations.append({
                "playerId": defender.player_id,
                "start": start,
                "end": def_coords,
                "actions": [{"timestamp": 0, "type": action_type}],
                "movement": movement,
                "hasBall": False,
                "duration": steps[-1]["timestamp"] if steps else 800
            })


        self.latest_packet = animations
        print(f"[DEBUG] Generated {len(animations)} animations")

        return animations

    def get_latest_animation_packet(self):
        return self.latest_packet