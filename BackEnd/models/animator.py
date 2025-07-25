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
        print(f"[DEBUG] action_timeline: {action_timeline}")
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

        # Determine which offensive player has the ball at each step
        ball_actions = {"handle_ball", "receive", "shoot"}
        ball_owner_by_step = []
        for step in steps:
            owner = None
            for pos_key, action_info in step["pos_actions"].items():
                if action_info["action"] in ball_actions:
                    owner = off_lineup[pos_key]
                    break
            if owner is None:
                for event in step.get("events", []):
                    if event.get("type") == "pass":
                        owner = off_lineup.get(event.get("to"))
                        if owner:
                            break
                    elif event.get("type") == "shot":
                        owner = off_lineup.get(event.get("by"))
                        if owner:
                            break
            ball_owner_by_step.append(owner)

        for idx, owner in enumerate(ball_owner_by_step):
            if owner is None:
                print(f"[WARN] No ball owner detected for step {idx}")

        for pos, player in off_lineup.items():
            timeline = action_timeline.get(player, [])
            print("Inside capture_halfcourt_animation")
            print(f"[DEBUG] timeline for {pos}: {timeline}")
            if not timeline:
                continue

            hasBallAtStep = [ball_owner_by_step[i] is player for i in range(len(timeline))]

            timeline.sort(key=lambda tup: tup[0])
            first_spot = timeline[0][2]
            last_spot = timeline[-1][2]
            start_coords = getattr(player, "coords", {"x": 25, "y": 50})
            end_coords = HCO_STRING_SPOTS.get(last_spot, start_coords)

            if is_away_offense:
                start_coords = get_away_player_coords(start_coords)
                end_coords = get_away_player_coords(end_coords)

            if pos == bh_pos:
                ball_handler_end_coords = end_coords  # For defense setup

            movement = []
            for t, action, spot in timeline:
                coord = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
                if is_away_offense:
                    coord = get_away_player_coords(coord)

                movement.append({
                    "timestamp": t,
                    "coords": coord,
                    "action": action # e.g., "pass", "screen", "shoot", "cut"
                })

            animations.append({
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start_coords,
                "end": end_coords,
                "movement": movement,
                "hasBallAtStep": hasBallAtStep,
                "duration": timeline[-1][0]
            })

        for pos, defender in def_lineup.items():
            def_coords = None
            action_type = ACTIONS["GUARD_OFFBALL"]

            hasBallAtStep = [False for _ in ball_owner_by_step]

            if pos == bh_pos:
                bh_timeline = action_timeline.get(ball_handler, [])
                bh_first_spot = bh_timeline[0][2] if bh_timeline else None
                bh_last_spot = bh_timeline[-1][2] if bh_timeline else None
                first_coords = HCO_STRING_SPOTS.get(bh_first_spot, ball_handler_end_coords)
                final_coords = HCO_STRING_SPOTS.get(bh_last_spot, ball_handler_end_coords)
                if is_away_offense:
                    first_coords = get_away_player_coords(first_coords)
                    final_coords = get_away_player_coords(final_coords)
                def_coords = assign_bh_defender_coords(final_coords, aggression_call, is_away_offense)
                action_type = ACTIONS["GUARD_BALL"]
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                last_spot = next(
                    (step[2] for step in reversed(action_timeline.get(off_player, [])) if step[2]),
                    "key"
                )
                o_coords = HCO_STRING_SPOTS.get(last_spot, HCO_STRING_SPOTS["key"])
                def_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call, is_away_offense)
            else:
                print(f"[WARN] No offensive match for defender {pos}, skipping.")
                continue

            start = getattr(defender, "coords", {"x": 25, "y": 50})
            if pos == bh_pos:
                start = assign_bh_defender_coords(first_coords, aggression_call, is_away_offense)

            if is_away_offense:
                def_coords = get_away_player_coords(def_coords)
                start = get_away_player_coords(start)

            movement = []

            if pos == bh_pos:
                for t, _, spot in bh_timeline:
                    bh_coords = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
                    if is_away_offense:
                        bh_coords = get_away_player_coords(bh_coords)
                    d_coords = assign_bh_defender_coords(bh_coords, aggression_call, is_away_offense)
                    if is_away_offense:
                        d_coords = get_away_player_coords(d_coords)
                    movement.append({
                        "timestamp": t,
                        "coords": d_coords,
                        "action": ACTIONS["GUARD_BALL"]
                    })
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                timeline = action_timeline.get(off_player, [])
                for t, _, spot in timeline:
                    o_coords = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
                    d_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call, is_away_offense)
                    if is_away_offense:
                        d_coords = get_away_player_coords(d_coords)
                    movement.append({
                        "timestamp": t,
                        "coords": d_coords,
                        "action": ACTIONS["GUARD_OFFBALL"]
                    })

            animations.append({
                "playerId": getattr(defender, "player_id", str(id(defender))),
                "start": start,
                "end": def_coords,
                "movement": movement,
                "hasBallAtStep": hasBallAtStep,
                "duration": steps[-1]["timestamp"] if steps else 800
            })


        # for pos, defender in def_lineup.items():
        #     def_coords = None  # ✅ Safe default
        #     action_type = ACTIONS["GUARD_OFFBALL"]

        #     if pos == bh_pos:
        #         def_coords = assign_bh_defender_coords(ball_handler_end_coords, aggression_call, is_away_offense)
        #         action_type = ACTIONS["GUARD_BALL"]
        #     elif pos in off_lineup:
        #         off_player = off_lineup[pos]
        #         last_spot = next(
        #             (step[2] for step in reversed(action_timeline.get(off_player, [])) if step[2]),
        #             "key"
        #         )
        #         o_coords = HCO_STRING_SPOTS.get(last_spot, HCO_STRING_SPOTS["key"])
        #         def_coords = def_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call, is_away_offense)
        #     else:
        #         print(f"[WARN] No offensive match for defender {pos}, skipping.")
        #         continue  # skip player if we can't map them

        #     # ✅ Only continue if def_coords is safe
        #     start = defender.coords
        #     if pos == bh_pos and steps:
        #         bh_start = steps[0].get("coords", ball_handler_end_coords)
        #         start = assign_bh_defender_coords(bh_start, aggression_call, is_away_offense)

        #     # ✅ Flip if away team has the ball so all coordinates are in the
        #     # same orientation as the offense
        #     if is_away_offense:
        #         def_coords = get_away_player_coords(def_coords)
        #         start = get_away_player_coords(start)

        #     movement = []
        #     if pos == bh_pos:
        #         for step in steps:
        #             t = step["timestamp"]
        #             bh_coords = step.get("coords", ball_handler_end_coords)
        #             d_coords = assign_bh_defender_coords(bh_coords, aggression_call, is_away_offense)
        #             if is_away_offense:
        #                 d_coords = get_away_player_coords(d_coords)
        #             movement.append({"timestamp": t, "coords": d_coords})
        #     elif pos in off_lineup:
        #         off_player = off_lineup[pos]
        #         timeline = action_timeline.get(off_player, [])
        #         for t, _, spot in timeline:
        #             o_coords = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
        #             d_coords = def_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call, is_away_offense)
        #             if is_away_offense:
        #                 d_coords = get_away_player_coords(d_coords)
        #             movement.append({"timestamp": t, "coords": d_coords})

        #     animations.append({
        #         "playerId": defender.player_id,
        #         "start": start,
        #         "end": def_coords,
        #         "actions": [{"timestamp": 0, "type": action_type}],
        #         "movement": movement,
        #         "hasBall": False,
        #         "duration": steps[-1]["timestamp"] if steps else 800
        #     })


        self.latest_packet = animations
        print(f"[DEBUG] Generated {len(animations)} animations")

        return animations

    def get_latest_animation_packet(self):
        return self.latest_packet