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
from BackEnd.constants import HCO_STRING_SPOTS, ACTIONS, RIM_COORDS, TOP_KEY_COORDS
import random
import logging

class Animator:
    def __init__(self, game):
        self.game = game
        self.latest_packet = []

    def _log_step_timestamps(self, animations):
        for anim in animations:
            movement = anim.get("movement", [])
            timestamps = [step.get("timestamp") for step in movement]
            logging.debug("Animator timestamps for %s: %s", anim.get("playerId"), timestamps)

    def capture_fast_break_animation(
        self,
        fb_roles,
        hold_up=False,
        stopper_id=None,
        in_play_defenders=None,
    ):
        """Build a fast break animation packet.

        Args:
            fb_roles (dict):
                {"ball_handler": Player}
            hold_up (bool): Whether the break was stopped.
            stopper_id (str): Player ID of the defender who stopped it.
            in_play_defenders (list[Player]): Defenders ahead of the ball.

        Returns:
            list[dict]: Animation payload for the frontend.
        """

        offense_team = self.game.offense_team
        defense_team = self.game.defense_team
        is_away_offense = offense_team.team_id == self.game.away_team.team_id

        ball_handler = fb_roles.get("ball_handler")
        defenders = in_play_defenders or []

        animations = []
        duration = 800

        def build_movement(player, end_coords, has_ball=False, action=ACTIONS["DRIFT"]):
            start = getattr(player, "coords", {"x": 25, "y": 50})
            if is_away_offense:
                start = get_away_player_coords(start)
                end = get_away_player_coords(end_coords)
            else:
                end = end_coords

            movement = [
                {"timestamp": 0, "coords": start, "action": action if not has_ball else ACTIONS["HANDLE"]},
                {"timestamp": duration, "coords": end, "action": action if not has_ball else ACTIONS["HANDLE"]},
            ]

            animations.append({
                "playerId": getattr(player, "player_id", str(id(player))),
                "start": start,
                "end": end,
                "movement": movement,
                "hasBallAtStep": [has_ball, has_ball],
                "duration": duration,
            })

        # Helper to generate spots between the top of the key and the rim
        def between_key_and_rim():
            min_x = min(TOP_KEY_COORDS["x"], RIM_COORDS["x"])
            max_x = max(TOP_KEY_COORDS["x"], RIM_COORDS["x"])
            x = random.randint(min_x + 1, max_x - 1)
            y = random.randint(10, 40)
            return {"x": x, "y": y}

        def half_court_spot():
            return {"x": random.randint(40, 60), "y": random.randint(10, 40)}

        # Track which players are already animated
        animated_player_ids = set()

        # Ball handler path
        if ball_handler:
            bh_end = TOP_KEY_COORDS if hold_up else RIM_COORDS
            build_movement(ball_handler, bh_end, has_ball=True)
            animated_player_ids.add(getattr(ball_handler, "player_id", None))

        # Identify stopper
        stopper = None
        if hold_up and stopper_id:
            for d in defenders:
                if getattr(d, "player_id", None) == stopper_id:
                    stopper = d
                    break
        if hold_up:
            # Stopping defender
            if stopper:
                offset_x = 6 if not is_away_offense else -6
                end = {
                    "x": TOP_KEY_COORDS["x"] + offset_x,
                    "y": TOP_KEY_COORDS["y"] + random.randint(-3, 3),
                }
                build_movement(stopper, end, action=ACTIONS["GUARD_BALL"])
                animated_player_ids.add(getattr(stopper, "player_id", None))

            # Other in-play defenders
            for d in defenders:
                if d is stopper:
                    continue
                build_movement(d, between_key_and_rim(), action=ACTIONS["GUARD_OFFBALL"])
                animated_player_ids.add(getattr(d, "player_id", None))
        
        # Animate non-involved players to half court
        # Get all players from both teams
        all_offensive_players = list(offense_team.lineup.values())
        all_defensive_players = list(defense_team.lineup.values())
        
        for player in all_offensive_players + all_defensive_players:
            player_id = getattr(player, "player_id", None)
            if player_id and player_id not in animated_player_ids:
                # Move to random half court spot
                build_movement(player, half_court_spot(), has_ball=False, action=ACTIONS["DRIFT"])
        self._log_step_timestamps(animations)
        self.latest_packet = animations
        logging.debug(
            "capture_fast_break_animation generated %d animations first=%s",
            len(animations),
            animations[0] if animations else None,
        )
        return animations

    def capture_free_throw_animation(
        self,
        game,
        shooter,
        attempts,
        offense_is_home,
        no_lane=False,
    ):
        """Build a free throw animation packet.

        Args:
            game (GameManager): Current game instance.
            shooter (Player): Player shooting free throws.
            attempts (list[str]): List of results ("MAKE"/"MISS") for each attempt.
            offense_is_home (bool): True if offense is attacking the home rim.
            no_lane (bool): If True, only the shooter moves to the line.

        Returns:
            list[dict]: Animation payload for the frontend.
        """

        offense_team = game.offense_team
        defense_team = game.defense_team
        shooter_pos = get_player_position(offense_team.lineup, shooter)
        if not shooter_pos:
            logging.warning(
                "capture_free_throw_animation: shooter %s not found in lineup",
                getattr(shooter, "player_id", shooter),
            )
            self.latest_packet = []
            return []

        HOME_CFG = {
            "shooterSpot": {"x": 74, "y": 25},
            "offenseAlignList": [
                {"x": 56, "y": 44},
                {"x": 80, "y": 32},
                {"x": 86, "y": 19},
                {"x": 86, "y": 32},
            ],
            "dDestinations": {
                "PG": {"x": 54, "y": 37},
                "SG": {"x": 83, "y": 32},
                "SF": {"x": 83, "y": 19},
                "PF": {"x": 89, "y": 32},
                "C": {"x": 89, "y": 19},
            },
            "rim": {"x": 91, "y": 25},
        }

        AWAY_CFG = {
            "shooterSpot": {"x": 27, "y": 25},
            "offenseAlignList": [
                {"x": 45, "y": 44},
                {"x": 20, "y": 32},
                {"x": 14, "y": 19},
                {"x": 14, "y": 32},
            ],
            "dDestinations": {
                "PG": {"x": 47, "y": 37},
                "SG": {"x": 17, "y": 32},
                "SF": {"x": 17, "y": 19},
                "PF": {"x": 11, "y": 32},
                "C": {"x": 11, "y": 19},
            },
            "rim": {"x": 9, "y": 25},
        }

        cfg = HOME_CFG if offense_is_home else AWAY_CFG
        shooter_spot = cfg["shooterSpot"]
        rim = cfg["rim"]
        duration = 800

        animations = []
        position_list = ["PG", "SG", "SF", "PF", "C"]

        if not no_lane:
            o_destinations = {shooter_pos: shooter_spot}
            other_positions = [p for p in position_list if p != shooter_pos]
            for i, pos in enumerate(other_positions[: len(cfg["offenseAlignList"]) ]):
                o_destinations[pos] = cfg["offenseAlignList"][i]

            for pos, player in offense_team.lineup.items():
                if pos not in o_destinations or not player:
                    continue
                start = getattr(player, "coords", {"x": 25, "y": 50})
                end = o_destinations[pos]
                movement = [
                    {"timestamp": 0, "coords": start, "action": ACTIONS["DRIFT"]},
                    {"timestamp": duration, "coords": end, "action": ACTIONS["DRIFT"]},
                ]
                animations.append(
                    {
                        "playerId": getattr(player, "player_id", str(id(player))),
                        "start": start,
                        "end": end,
                        "movement": movement,
                        "hasBallAtStep": [player is shooter, False],
                        "duration": duration,
                    }
                )

            for pos, player in defense_team.lineup.items():
                dest = cfg["dDestinations"].get(pos)
                if not player or not dest:
                    continue
                start = getattr(player, "coords", {"x": 25, "y": 50})
                movement = [
                    {"timestamp": 0, "coords": start, "action": ACTIONS["DRIFT"]},
                    {"timestamp": duration, "coords": dest, "action": ACTIONS["DRIFT"]},
                ]
                animations.append(
                    {
                        "playerId": getattr(player, "player_id", str(id(player))),
                        "start": start,
                        "end": dest,
                        "movement": movement,
                        "hasBallAtStep": [False, False],
                        "duration": duration,
                    }
                )
        else:
            start = getattr(shooter, "coords", {"x": 25, "y": 50})
            movement = [
                {"timestamp": 0, "coords": start, "action": ACTIONS["DRIFT"]},
                {"timestamp": duration, "coords": shooter_spot, "action": ACTIONS["DRIFT"]},
            ]
            animations.append(
                {
                    "playerId": getattr(shooter, "player_id", str(id(shooter))),
                    "start": start,
                    "end": shooter_spot,
                    "movement": movement,
                    "hasBallAtStep": [True, False],
                    "duration": duration,
                }
            )

        # Ball movement across attempts
        shot_ms = 500
        rim_hold_ms = 300
        time = 0
        ball_movement = [
            {"timestamp": time, "coords": shooter_spot, "action": ACTIONS["HANDLE"]}
        ]

        for idx, outcome in enumerate(attempts or []):
            time += shot_ms
            
            # Calculate ball landing position based on make/miss
            from BackEnd.constants import MADE_SHOT_BALL_OFFSET
            
            if outcome == "MAKE":
                # Made shot: ball lands closer to shooter
                ball_coords = {
                    "x": rim["x"] - MADE_SHOT_BALL_OFFSET if offense_is_home else rim["x"] + MADE_SHOT_BALL_OFFSET,
                    "y": rim["y"]
                }
            else:
                # Missed shot: ball goes to rim first
                ball_coords = rim
            
            ball_movement.append(
                {"timestamp": time, "coords": ball_coords, "action": ACTIONS["SHOOT"]}
            )
            
            # Handle post-shot animation
            if outcome == "MAKE":
                # Made shot: ball stays at landing spot
                time += rim_hold_ms
            else:
                # Missed shot: ball bounces away from rim
                # First, ball hits rim (already added above)
                time += rim_hold_ms  # Brief pause at rim
                
                # Then bounce to random spot AWAY from basket
                # Y: ±6 from rim center
                # X: 1-6 grid units AWAY from basket (outward)
                y_bounce = random.randint(-6, 6)
                x_bounce = random.randint(1, 6)
                
                # Home basket (X=91): bounce left (decrease X)
                # Away basket (X=9): bounce right (increase X)
                bounce_coords = {
                    "x": rim["x"] - x_bounce if offense_is_home else rim["x"] + x_bounce,
                    "y": rim["y"] + y_bounce
                }
                # Clamp to valid court bounds
                bounce_coords["x"] = max(0, min(100, bounce_coords["x"]))
                bounce_coords["y"] = max(0, min(50, bounce_coords["y"]))
                
                # Add bounce animation
                ball_movement.append(
                    {"timestamp": time, "coords": bounce_coords, "action": ACTIONS["DRIFT"]}
                )
            
            # If more attempts remain, return ball to shooter
            if idx < len(attempts) - 1:
                time += shot_ms
                ball_movement.append(
                    {"timestamp": time, "coords": shooter_spot, "action": ACTIONS["DRIFT"]}
                )

        animations.append(
            {
                "playerId": "ball",
                "start": shooter_spot,
                "end": rim if attempts else shooter_spot,
                "movement": ball_movement,
                "hasBallAtStep": [True] + [False] * (len(ball_movement) - 1),
                "duration": time,
            }
        )
        self._log_step_timestamps(animations)
        self.latest_packet = animations
        logging.debug(
            "capture_free_throw_animation generated %d animations first=%s",
            len(animations),
            animations[0] if animations else None,
        )
        return animations

    def capture_halfcourt_animation(self, roles, event_step=None):
        offense_team = self.game.offense_team
        defense_team = self.game.defense_team
        off_lineup = offense_team.lineup
        def_lineup = defense_team.lineup
        aggression_call = defense_team.strategy_calls.get("aggression_call", "normal")
        is_away_offense = offense_team.team_id == self.game.away_team.team_id
        
        # Check if next play will be FCP/HCT (set after made shots)
        next_defensive_setup = roles.get("next_defensive_setup")


        steps = roles["steps"]
        action_timeline = roles["action_timeline"]
        logging.debug("action_timeline: %s", action_timeline)
        shooter = roles["shooter"]
        ball_handler = roles["ball_handler"]

        if event_step is not None:
            steps = steps[:event_step + 1]

        if not steps:
            logging.warning("capture_halfcourt_animation: no steps provided")
            self.latest_packet = []
            return []

        animations = []

        # ----------------
        # 🔵 OFFENSIVE ANIMATION
        # ----------------
        bh_pos = get_player_position(off_lineup, ball_handler)
        ball_handler_end_coords = None

        # Determine which offensive player has the ball at each step
        ball_actions = {"handle_ball", "receive", "shoot"}
        ball_owner_by_step = []
        # Map all players by their ID for quick lookup on events
        players_by_id = {
            getattr(p, "player_id", str(id(p))): p for p in off_lineup.values()
        }
        players_by_id.update(
            {getattr(p, "player_id", str(id(p))): p for p in def_lineup.values()}
        )

        rebounder = None
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
                    elif event.get("event_type") in {"offReb", "defReb"}:
                        owner = players_by_id.get(event.get("rebounderId"))
                        rebounder = owner or rebounder
                        if owner:
                            break
            ball_owner_by_step.append(owner)

        # Extend ball ownership to cover any additional timeline steps
        max_timeline_len = max(
            [len(tl) for tl in action_timeline.values()] + [len(ball_owner_by_step)]
        )
        if len(ball_owner_by_step) < max_timeline_len:
            filler = rebounder or (ball_owner_by_step[-1] if ball_owner_by_step else None)
            ball_owner_by_step.extend([filler] * (max_timeline_len - len(ball_owner_by_step)))

        for idx, owner in enumerate(ball_owner_by_step):
            if owner is None:
                logging.warning("No ball owner detected for step %d", idx)

        for pos, player in off_lineup.items():
            timeline = action_timeline.get(player, [])
            logging.debug("Inside capture_halfcourt_animation")
            logging.debug("timeline for %s: %s", pos, timeline)
            if not timeline:
                continue

            logging.debug(
                "capture_halfcourt_animation: %s timeline=%d ball_owner_steps=%d",
                pos,
                len(timeline),
                len(ball_owner_by_step),
            )

            max_steps = min(len(timeline), len(ball_owner_by_step))
            if max_steps == 0:
                logging.warning(
                    "capture_halfcourt_animation: %s timeline has no matching steps",
                    pos,
                )
                continue

            timeline = timeline[:max_steps]
            hasBallAtStep = [ball_owner_by_step[i] is player for i in range(max_steps)]

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

            hasBallAtStep = [ball_owner_by_step[i] is defender for i in range(len(ball_owner_by_step))]

            if pos == bh_pos:
                bh_timeline = action_timeline.get(ball_handler, [])
                bh_first_spot = bh_timeline[0][2] if bh_timeline else None
                bh_last_spot = bh_timeline[-1][2] if bh_timeline else None
                first_coords = HCO_STRING_SPOTS.get(bh_first_spot, ball_handler_end_coords)
                final_coords = HCO_STRING_SPOTS.get(bh_last_spot, ball_handler_end_coords)
                if is_away_offense:
                    first_coords = get_away_player_coords(first_coords)
                    final_coords = get_away_player_coords(final_coords)
                
                # Override end position if FCP is next
                if next_defensive_setup == "FCP":
                    # Position for full court press: same Y as offensive player, 3 units closer to new offensive basket
                    # After possession flip, this team will be on offense attacking opposite basket
                    # So "closer to new offensive basket" means closer to where they currently are on defense
                    x_offset = 3 if is_away_offense else -3
                    def_coords = {
                        "x": max(0, min(100, final_coords["x"] + x_offset)),
                        "y": final_coords["y"]
                    }
                else:
                    def_coords = assign_bh_defender_coords(final_coords, aggression_call, is_away_offense)
                action_type = ACTIONS["GUARD_BALL"]
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                last_spot = next(
                    (step[2] for step in reversed(action_timeline.get(off_player, [])) if step[2]),
                    "key"
                )
                o_coords = HCO_STRING_SPOTS.get(last_spot, HCO_STRING_SPOTS["key"])
                
                # Flip offensive coords to actual orientation if away team is on offense
                if is_away_offense:
                    o_coords = get_away_player_coords(o_coords)
                
                # Override end position if FCP is next
                if next_defensive_setup == "FCP":
                    # Position for full court press
                    x_offset = 3 if is_away_offense else -3
                    def_coords = {
                        "x": max(0, min(100, o_coords["x"] + x_offset)),
                        "y": o_coords["y"]
                    }
                else:
                    def_coords = assign_non_bh_defender_coords(o_coords, ball_handler_end_coords, aggression_call, is_away_offense)
            else:
                logging.warning("No offensive match for defender %s, skipping.", pos)
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


        self._log_step_timestamps(animations)
        self.latest_packet = animations
        logging.debug(
            "capture_halfcourt_animation generated %d animations first=%s",
            len(animations),
            animations[0] if animations else None,
        )

        return animations

    def skeleton_to_animations(self, skeleton, off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False):
        """
        Convert skeleton data to animation format.
        
        Args:
            skeleton: Skeleton data with steps and pos_actions
            off_lineup: Dict of offensive players by position
            def_lineup: Dict of defensive players by position
            add_defenders: Whether to add defensive player animations
            is_fcp: Whether this is a full court press (uses special defensive positioning)
            
        Returns:
            List of animation dicts for each player
        """
        if not skeleton or "steps" not in skeleton:
            return []
        
        animations = []
        steps = skeleton["steps"]
        
        # Group all positions that appear in any step
        all_positions = set()
        for step in steps:
            all_positions.update(step.get("pos_actions", {}).keys())
        
        # Build animation for OFFENSIVE players from skeleton
        offensive_animations = {}  # Store by position for defensive matching
        
        for position in all_positions:
            player = off_lineup.get(position)
            if not player:
                continue
            
            player_id = getattr(player, "player_id", None)
            if not player_id:
                continue
            
            # Build movement array from steps
            movement = []
            has_ball_steps = []
            start_coords = None
            end_coords = None
            
            for step in steps:
                pos_action = step.get("pos_actions", {}).get(position)
                if not pos_action:
                    continue
                
                timestamp = step.get("timestamp", 0)
                coords = pos_action.get("coords", {"x": 50, "y": 25})
                action = pos_action.get("action", "drift")
                
                if start_coords is None:
                    start_coords = coords
                end_coords = coords
                
                # Determine if player has ball at this step
                has_ball = action in ["handle_ball", "receive", "shoot", "pass"]
                
                movement.append({
                    "timestamp": timestamp,
                    "coords": coords,
                    "action": action
                })
                has_ball_steps.append(has_ball)
            
            if not movement:
                continue
            
            # Calculate duration (last timestamp)
            duration = movement[-1]["timestamp"] if movement else 0
            
            anim = {
                "playerId": player_id,
                "start": start_coords or {"x": 50, "y": 25},
                "end": end_coords or {"x": 50, "y": 25},
                "movement": movement,
                "hasBallAtStep": has_ball_steps,
                "duration": duration
            }
            
            animations.append(anim)
            offensive_animations[position] = anim  # Store for defensive matching
        
        # Add DEFENSIVE player animations
        if add_defenders and def_lineup:
            if is_fcp:
                # Use FCP-specific defensive positioning
                defensive_anims = self._position_fcp_defenders(
                    offensive_animations, 
                    def_lineup, 
                    steps
                )
                animations.extend(defensive_anims)
            elif is_hct:
                # Use HCT-specific defensive positioning
                defensive_anims = self._position_hct_defenders(
                    def_lineup,
                    steps
                )
                animations.extend(defensive_anims)
            else:
                # Use standard defensive positioning (future implementation)
                pass
        
        return animations
    
    def _position_fcp_defenders(self, offensive_animations, def_lineup, skeleton_steps):
        """
        Position defensive players for Full Court Press scenarios.
        
        Strategy:
        - Each defender guards the offensive player at their position
        - Defender maintains same Y coordinate as their assignment
        - Defender is positioned 3 grid units closer to the offensive basket
        
        Args:
            offensive_animations: Dict mapping position → offensive player animation
            def_lineup: Dict of defensive players by position
            skeleton_steps: List of skeleton steps for timing
            
        Returns:
            List of defensive player animations
        """
        defensive_animations = []
        
        # Determine which direction is "closer to offensive basket"
        is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
        
        # For away team offense: offensive basket is on the LEFT (lower x)
        # For home team offense: offensive basket is on the RIGHT (higher x)
        x_offset = -3 if is_away_offense else 3
        
        # Match each defensive position to offensive position
        for position, off_anim in offensive_animations.items():
            # Get the defensive player at this position
            def_player = def_lineup.get(position)
            if not def_player:
                continue
            
            def_player_id = getattr(def_player, "player_id", None)
            if not def_player_id:
                continue
            
            # Build defensive movement matching offensive player's path
            def_movement = []
            def_start = None
            def_end = None
            
            for off_step in off_anim["movement"]:
                timestamp = off_step["timestamp"]
                off_coords = off_step["coords"]
                
                # Defender position: same Y, X offset toward offensive basket
                def_coords = {
                    "x": off_coords["x"] + x_offset,
                    "y": off_coords["y"]
                }
                
                # Clamp X to valid court bounds (0-100)
                def_coords["x"] = max(0, min(100, def_coords["x"]))
                
                # Determine defensive action based on offensive action
                if off_step.get("action") in ["handle_ball", "receive", "shoot", "pass"]:
                    def_action = "guard_ball"  # Guarding ball handler
                else:
                    def_action = "guard_offball"  # Guarding off-ball player
                
                if def_start is None:
                    def_start = def_coords
                def_end = def_coords
                
                def_movement.append({
                    "timestamp": timestamp,
                    "coords": def_coords,
                    "action": def_action
                })
            
            if not def_movement:
                continue
            
            # All defenders have ball at no steps
            has_ball_steps = [False] * len(def_movement)
            duration = def_movement[-1]["timestamp"] if def_movement else 0
            
            defensive_animations.append({
                "playerId": def_player_id,
                "start": def_start or {"x": 50, "y": 25},
                "end": def_end or {"x": 50, "y": 25},
                "movement": def_movement,
                "hasBallAtStep": has_ball_steps,
                "duration": duration
            })
        
        return defensive_animations

    def _position_hct_defenders(self, def_lineup, skeleton_steps):
        """
        Position defensive players for Half Court Trap scenarios.
        
        Strategy:
        - Defenders take specific court positions based on trap setup
        - PG: Deep Key (protecting basket)
        - SG: Deep Upper Wing (trap position)
        - SF: Deep Lower Wing (trap position)
        - PF: Key (mid-range defense)
        - C: Mid Lane (protecting paint)
        
        Positions are mirrored based on which team is on offense.
        
        Args:
            def_lineup: Dict of defensive players by position
            skeleton_steps: List of skeleton steps for timing
            
        Returns:
            List of defensive player animations
        """
        defensive_animations = []
        
        # Determine court orientation
        is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
        
        # Define base positions for away team defending (home team on offense)
        # These are the RIGHT side positions (defending right basket)
        hct_away_defending_positions = {
            "PG": {"x": 57, "y": 25},   # Deep Key (right)
            "SG": {"x": 57, "y": 35},   # Deep Upper Wing (right)
            "SF": {"x": 57, "y": 15},   # Deep Lower Wing (right)
            "PF": {"x": 64, "y": 25},   # Key (right)
            "C": {"x": 80, "y": 25}     # Mid Lane (right)
        }
        
        # Determine actual positions based on who's defending
        hct_positions = {}
        for pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            base_coords = hct_away_defending_positions[pos]
            if is_away_offense:
                # Home team defending - flip to LEFT side
                hct_positions[pos] = {
                    "x": 101 - base_coords["x"],
                    "y": base_coords["y"]
                }
            else:
                # Away team defending RIGHT basket - use base positions
                hct_positions[pos] = base_coords
        
        # Get the duration from skeleton steps
        duration = skeleton_steps[-1].get("timestamp", 0) if skeleton_steps else 0
        
        # Create animation for each defensive position
        for position in ['PG', 'SG', 'SF', 'PF', 'C']:
            def_player = def_lineup.get(position)
            if not def_player:
                continue
            
            def_player_id = getattr(def_player, "player_id", None)
            if not def_player_id:
                continue
            
            # Get the position for this defender
            def_coords = hct_positions[position]
            
            # Create simple movement to the trap position
            movement = [
                {
                    "timestamp": 0,
                    "coords": def_coords,
                    "action": "trap_position"
                },
                {
                    "timestamp": duration,
                    "coords": def_coords,
                    "action": "trap_position"
                }
            ]
            
            defensive_animations.append({
                "playerId": def_player_id,
                "start": def_coords,
                "end": def_coords,
                "movement": movement,
                "hasBallAtStep": [False, False],
                "duration": duration
            })
        
        return defensive_animations

    def get_latest_animation_packet(self):
        return self.latest_packet
