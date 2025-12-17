from BackEnd.utils.shared import (
    get_player_by_pos, 
    get_player_position,
    get_away_player_coords,
)
from BackEnd.utils.shared_defense import (
    get_defender_coords
)
from collections import defaultdict
from BackEnd.constants import HCO_STRING_SPOTS, OFFSET_SPOTS, ACTIONS, RIM_COORDS, TOP_KEY_COORDS, HOME_RIM_COORDS, AWAY_RIM_COORDS, HOME_TOP_KEY, AWAY_TOP_KEY
import random
import logging
from BackEnd.constants.fast_break_constants import (
    BALL_HANDLER_MOVE_X_MIN,
    BALL_HANDLER_MOVE_X_MAX,
    BALL_HANDLER_MOVE_Y_RANGE,
    STOPPER_OFFSET_MIN,
    STOPPER_OFFSET_MAX,
    DEFENDER_X_OFFSET,
    REBOUNDER_X_MIN,
    REBOUNDER_X_MAX,
    REBOUNDER_Y_RANGE,
    SHOT_ATTEMPT_REBOUNDER_Y_RANGE,
    OUTLET_PASSER_MOVE_X,
)

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
    ):
        """Build a fast break animation packet.

        Args:
            fb_roles (dict):
                {
                    "ball_handler": Player,
                    "defense": list[Player],
                    "offense": list[Player],
                    "outlet_passer": str (player_id) or None,
                    "outlet_receiver": str (player_id) or None
                }
            hold_up (bool): Whether the break was stopped.
            stopper_id (str): Player ID of the defender who stopped it.

        Returns:
            list[dict]: Animation payload for the frontend.
        """

        offense_team = self.game.offense_team
        defense_team = self.game.defense_team
        # ✅ SS&S: Use is_away_offense from fb_roles (calculated from offense_team_id in phase_resolution)
        # This ensures consistency with phase_resolution.py calculations
        is_away_offense = fb_roles.get("is_away_offense")
        if is_away_offense is None:
            # Fallback to calculating from game state (shouldn't happen, but safety check)
            is_away_offense = offense_team.team_id == self.game.away_team.team_id
            logging.warning(f"⚠️ [FAST BREAK ANIMATION] is_away_offense not in fb_roles, calculated from game state: {is_away_offense}")
        
        # ✅ DEBUG: Verify is_away_offense is correct
        calculated_is_away = offense_team.team_id == self.game.away_team.team_id
        if is_away_offense != calculated_is_away:
            logging.warning(f"⚠️ [FAST BREAK ANIMATION] is_away_offense mismatch! fb_roles: {is_away_offense}, calculated: {calculated_is_away}")
            # Use the calculated value as it's more reliable
            is_away_offense = calculated_is_away

        ball_handler = fb_roles.get("ball_handler")
        defenders = fb_roles.get("defense", [])

        animations = []
        duration = 800

        def build_movement(player, end_coords, has_ball=False, action=ACTIONS["DRIFT"]):
            # ✅ FIX: For ball handler, use outlet position from fb_roles as start (guaranteed HOME orientation)
            # This ensures we're starting from the correct position after the outlet pass
            if has_ball:
                # Use outlet position as start (already in HOME orientation)
                ball_handler_outlet_x = fb_roles.get("ball_handler_outlet_x")
                ball_handler_outlet_y = fb_roles.get("ball_handler_outlet_y")
                if ball_handler_outlet_x is not None and ball_handler_outlet_y is not None:
                    start = {"x": ball_handler_outlet_x, "y": ball_handler_outlet_y}
                else:
                    # Fallback to player.coords if outlet position not available
                    start = getattr(player, "coords", {"x": 25, "y": 50})
            else:
                # For non-ball handlers, use player.coords as normal
                start = getattr(player, "coords", {"x": 25, "y": 50})
            
            # ✅ DEBUG: Log build_movement inputs
            if has_ball:  # Only log for ball handler to avoid spam
                logging.warning(f"🏀 [FAST BREAK ANIMATION DEBUG] build_movement for ball handler:")
                logging.warning(f"  is_away_offense: {is_away_offense}")
                logging.warning(f"  start (from outlet or player.coords): {start}")
                logging.warning(f"  end_coords (input, HOME orientation): {end_coords}")
            
            # ✅ COMMENTED OUT: Coordinate flipping removed - using coordinates as-is
            # if is_away_offense:
            #     start = get_away_player_coords(start)
            #     end = get_away_player_coords(end_coords)
            #     
            #     # ✅ DEBUG: Log after flipping
            #     if has_ball:
            #         logging.warning(f"  start (after flip): {start}")
            #         logging.warning(f"  end (after flip): {end}")
            # else:
            #     end = end_coords
            #     
            #     # ✅ DEBUG: Log for home offense
            #     if has_ball:
            #         logging.warning(f"  end (no flip, HOME orientation): {end}")
            
            # Use end_coords as-is (no coordinate flipping)
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
        
        # ✅ Get get-back player IDs (used in both defensive stop and shot attempt paths)
        getback_player_ids = fb_roles.get("getback_player_ids", [])
        getback_player_ids_set = set(getback_player_ids) if getback_player_ids else set()

        # Ball handler path
        # ✅ NEW LOGIC: Calculate ball handler's final position (used for both defensive stop and shot)
        import random
        ball_handler_outlet_x = fb_roles.get("ball_handler_outlet_x")
        ball_handler_outlet_y = fb_roles.get("ball_handler_outlet_y")
        ball_handler_move_x = fb_roles.get("ball_handler_move_x", 7)  # Default 7 if not set
        
        # ✅ DEBUG: Log initial state
        logging.warning(f"🏀 [FAST BREAK ANIMATION DEBUG] Ball handler movement calculation:")
        logging.warning(f"  is_away_offense: {is_away_offense}")
        logging.warning(f"  offense_team.team_id: {offense_team.team_id}")
        logging.warning(f"  game.away_team.team_id: {self.game.away_team.team_id}")
        logging.warning(f"  ball_handler_outlet_x: {ball_handler_outlet_x}")
        logging.warning(f"  ball_handler_outlet_y: {ball_handler_outlet_y}")
        
        # Calculate additional movement from outlet position
        # For defensive stops and shot attempts: 5-10 x spots (IN ADDITION to steal entry), ±3 y
        # Direction: -1 for away offense (toward x=10), +1 for home offense (toward x=90)
        # ✅ SS&S: Use direction directly, no coordinate flipping
        move_distance = random.randint(BALL_HANDLER_MOVE_X_MIN, BALL_HANDLER_MOVE_X_MAX)
        x_direction = -1 if is_away_offense else 1  # Away: -1 (toward x=10), Home: +1 (toward x=90)
        additional_move_x = x_direction * move_distance
        additional_move_y = random.randint(-BALL_HANDLER_MOVE_Y_RANGE, BALL_HANDLER_MOVE_Y_RANGE)
        
        # ✅ DEBUG: Log movement values
        logging.warning(f"  move_distance: {move_distance}")
        logging.warning(f"  x_direction: {x_direction} ({'toward x=10 (away basket)' if is_away_offense else 'toward x=90 (home basket)'})")
        logging.warning(f"  additional_move_x: {additional_move_x} ({x_direction} * {move_distance})")
        logging.warning(f"  additional_move_y: {additional_move_y}")
        
        # Calculate ball handler's final position (coordinates already in correct orientation)
        if ball_handler_outlet_x is not None and ball_handler_outlet_y is not None:
            # Use outlet position as starting point
            # Multiply direction by move_distance to get signed movement
            bh_end_x = max(4, min(97, ball_handler_outlet_x + additional_move_x))
            bh_end_y = max(1, min(49, ball_handler_outlet_y + additional_move_y))
            bh_end = {"x": bh_end_x, "y": bh_end_y}
            
            # ✅ DEBUG: Log calculated position with full calculation
            logging.warning(f"  Calculation: {ball_handler_outlet_x} + {additional_move_x} = {bh_end_x}")
            logging.warning(f"  bh_end_x (HOME orientation): {bh_end_x}")
            logging.warning(f"  bh_end_y (HOME orientation): {bh_end_y}")
            if hold_up:
                logging.warning(f"🛑 [DEFENSIVE STOP] Ball handler stopped at: x={bh_end_x}, y={bh_end_y} (HOME orientation)")
                logging.warning(f"🛑 [DEFENSIVE STOP] Movement from outlet: +{additional_move_x} x, {additional_move_y:+d} y")
        else:
            # Fallback: use old logic
            if hold_up:
                bh_end = HOME_TOP_KEY.copy()
            else:
                rim_x = HOME_RIM_COORDS["x"]
                shot_distance = random.randint(4, 6)
                shooter_x = rim_x - shot_distance
                shooter_y = random.randint(20, 30)
                bh_end = {"x": shooter_x, "y": shooter_y}
            
        # ✅ DEBUG: Log final position before build_movement
        logging.warning(f"  bh_end before build_movement: {bh_end}")
        
        # Store final position for defender calculations (in HOME orientation)
        fb_roles["_bh_final_x"] = bh_end["x"]
        fb_roles["_bh_final_y"] = bh_end["y"]
        fb_roles["_bh_additional_move_x"] = abs(additional_move_x)  # Store absolute value for calculations
        
        if ball_handler:
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
            # ✅ NEW LOGIC: Stopping defender positioned 1-3 x coords ahead of ball handler, same y
            if stopper:
                # Get ball handler's final position (calculated above)
                bh_stop_x = fb_roles.get("_bh_final_x", HOME_TOP_KEY["x"])
                bh_stop_y = fb_roles.get("_bh_final_y", HOME_TOP_KEY["y"])
                
                # Stopper positioned 1-3 x coords ahead of ball handler, same y
                # Note: bh_stop_x is in HOME orientation, build_movement will flip for away offense
                stopper_offset = random.randint(STOPPER_OFFSET_MIN, STOPPER_OFFSET_MAX)
                if is_away_offense:
                    # Away offense: ahead means smaller x in AWAY orientation (toward basket at x=10)
                    # In HOME orientation: smaller x in away = larger x in home
                    # Example: ball handler at x=45 (HOME) = x=55 (away), stopper should be x=53 (away) = x=47 (HOME)
                    # So we ADD offset in HOME orientation
                    stopper_x = min(97, bh_stop_x + stopper_offset)
                else:
                    # Home offense: ahead means larger x (toward basket at x=90)
                    stopper_x = min(97, bh_stop_x + stopper_offset)
                
                end = {
                    "x": stopper_x,
                    "y": bh_stop_y,  # Same Y as ball handler
                }
                build_movement(stopper, end, action=ACTIONS["GUARD_BALL"])
                animated_player_ids.add(getattr(stopper, "player_id", None))

            # ✅ Only animate get-back players as defenders (not all players in defense list)
            # (getback_player_ids_set already defined at top of function)
            
            # Other get-back defenders position between key and rim
            for d in defenders:
                if d is stopper:
                    continue
                player_id = getattr(d, "player_id", None)
                # Only animate if this defender was a get-back player in the most recent shot attempt
                if player_id and player_id in getback_player_ids_set:
                    build_movement(d, between_key_and_rim(), action=ACTIONS["GUARD_OFFBALL"])
                    animated_player_ids.add(player_id)
        else:
            # ✅ NEW LOGIC: Shot attempt - defender positioned based on ball handler movement
            shot_defender = fb_roles.get("defender")
            if shot_defender:
                # Get ball handler's final position and movement distance
                bh_shot_x = fb_roles.get("_bh_final_x", bh_end["x"])
                additional_move_x = fb_roles.get("_bh_additional_move_x", 7)
                
                # Defender X: 6 less than ball handler's additional move distance (home) or 6 more (away)
                # The defender is positioned relative to the ball handler's final position
                defender_x_offset = DEFENDER_X_OFFSET
                
                if is_away_offense:
                    # Away offense: defender at x = ball handler x + 6 (further from basket)
                    defender_x = min(97, bh_shot_x + defender_x_offset)
                else:
                    # Home offense: defender at x = ball handler x - 6 (further from basket)
                    defender_x = max(4, bh_shot_x - defender_x_offset)
                
                # Defender Y: based on starting y position (from outlet pass)
                defender_start_y = getattr(shot_defender, "outlet_coords", {}).get("y", 25)
                if defender_start_y > 25:
                    # Starting y > 25: reduce by 1-6
                    defender_y_adjust = -random.randint(1, 6)
                else:
                    # Starting y <= 25: increase by 1-6
                    defender_y_adjust = random.randint(1, 6)
                
                defender_y = max(1, min(49, defender_start_y + defender_y_adjust))
                
                defender_end = {"x": defender_x, "y": defender_y}
                build_movement(shot_defender, defender_end, action=ACTIONS["GUARD_BALL"])
                animated_player_ids.add(getattr(shot_defender, "player_id", None))
            
            # ✅ Only animate get-back players as defenders (not all players in defense list)
            # (getback_player_ids_set already defined at top of function)
            
            # Other get-back defenders position between key and rim
            for d in defenders:
                if d is shot_defender:
                    continue
                player_id = getattr(d, "player_id", None)
                # Only animate if this defender was a get-back player in the most recent shot attempt
                if player_id and player_id in getback_player_ids_set:
                    build_movement(d, between_key_and_rim(), action=ACTIONS["GUARD_OFFBALL"])
                    animated_player_ids.add(player_id)
        
        # ✅ Animate rebounders (players who stayed near rim, not get-back, not release)
        # Get outlet passer ID - they move forward 7 x-coords toward basket
        outlet_passer_id = fb_roles.get("outlet_passer")
        outlet_passer_id_set = {outlet_passer_id} if outlet_passer_id else set()
        
        # Get all players from both teams
        all_offensive_players = list(offense_team.lineup.values())
        all_defensive_players = list(defense_team.lineup.values())
        
        # Get release player IDs (they're already animated as ball handler)
        release_player_ids = set()
        if self.game.turns and len(self.game.turns) > 0:
            for turn in reversed(self.game.turns[-10:]):
                if turn.get("result_type") in ["MISS", "MAKE"]:
                    release_coords = turn.get("defense_release_coords", {})
                    if release_coords:
                        release_player_ids = set(release_coords.keys())
                    break
        
        # ✅ TEMP: Do not animate outlet passer during Fast Break turn to avoid side-flip bug
        # if outlet_passer_id:
        #     outlet_passer = None
        #     for player in all_offensive_players + all_defensive_players:
        #         if getattr(player, "player_id", None) == outlet_passer_id:
        #             outlet_passer = player
        #             break
        #     
        #     if outlet_passer:
        #         passer_coords = getattr(outlet_passer, "coords", {})
        #         passer_current_x = passer_coords.get("x", 50)
        #         passer_current_y = passer_coords.get("y", 25)
        #         
        #         # Home offense: +7 (toward x=90), Away offense: -7 (toward x=10)
        #         passer_target_x = max(4, min(97, passer_current_x + (OUTLET_PASSER_MOVE_X if not is_away_offense else -OUTLET_PASSER_MOVE_X)))
        #         outlet_passer_spot = {
        #             "x": passer_target_x,
        #             "y": passer_current_y  # Keep same y-coord
        #         }
        #         
        #         build_movement(outlet_passer, outlet_passer_spot, has_ball=False, action=ACTIONS["DRIFT"])
        #         animated_player_ids.add(outlet_passer_id)
        
        for player in all_offensive_players + all_defensive_players:
            player_id = getattr(player, "player_id", None)
            if not player_id or player_id in animated_player_ids:
                continue
            
            # Skip outlet passer - already animated above
            if player_id in outlet_passer_id_set:
                continue
            
            # Skip release players (already animated as ball handler)
            if player_id in release_player_ids:
                continue
            
            # Skip get-back players (already animated as defenders)
            if player_id in getback_player_ids_set:
                continue
            
            # This is a rebounder (stayed near rim for shot attempt)
            player_start_y = getattr(player, "coords", {}).get("y", 25)
            
            if hold_up:
                # ✅ Defensive Stop: x=40-60, y=starting_y ± 6 (clamped 1-49)
                target_y = max(1, min(49, player_start_y + random.randint(-REBOUNDER_Y_RANGE, REBOUNDER_Y_RANGE)))
                target_spot = {
                    "x": random.randint(REBOUNDER_X_MIN, REBOUNDER_X_MAX),
                    "y": target_y
                }
            else:
                # ✅ Shot Attempt: x=rim_x, y=rim_y ± 10 (clamped 1-49)
                rim_coords = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
                target_y = max(1, min(49, rim_coords["y"] + random.randint(-SHOT_ATTEMPT_REBOUNDER_Y_RANGE, SHOT_ATTEMPT_REBOUNDER_Y_RANGE)))
                target_spot = {
                    "x": rim_coords["x"],
                    "y": target_y
                }
            
            build_movement(player, target_spot, has_ball=False, action=ACTIONS["DRIFT"])
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
        #comment for push

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
                
                # Flip to away orientation if needed (wrapper expects coords in current orientation)
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
                    # PHASE 3: Use new unified defender coordinate system
                    def_coords = get_defender_coords(
                        final_coords,
                        is_away_offense,
                        aggression_call,
                        bh_last_spot or "key",
                        None,
                        is_ball_handler=True
                    )
                action_type = ACTIONS["GUARD_BALL"]
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                last_spot = next(
                    (step[2] for step in reversed(action_timeline.get(off_player, [])) if step[2]),
                    "key"
                )
                o_coords = HCO_STRING_SPOTS.get(last_spot, HCO_STRING_SPOTS["key"])
                
                # Override end position if FCP is next
                if next_defensive_setup == "FCP":
                    # Position for full court press
                    x_offset = 3 if is_away_offense else -3
                    def_coords = {
                        "x": max(0, min(100, o_coords["x"] + x_offset)),
                        "y": o_coords["y"]
                    }
                else:
                    # PHASE 4: Use new unified defender coordinate system
                    # get_defender_coords handles coordinate orientation automatically
                    # Need to extract spot from offensive player's action
                    o_spot = "key"  # Default spot, could be extracted from action if available
                    # Use ball handler's last spot for ball_spot parameter (required for non-BH logic)
                    ball_spot_for_non_bh = bh_last_spot or "key"
                    def_coords = get_defender_coords(
                        o_coords,
                        is_away_offense,
                        aggression_call,
                        o_spot,
                        ball_handler_end_coords,
                        is_ball_handler=False,
                        ball_spot=ball_spot_for_non_bh
                    )
            else:
                logging.warning("No offensive match for defender %s, skipping.", pos)
                continue

            start = getattr(defender, "coords", {"x": 25, "y": 50})
            if pos == bh_pos:
                # PHASE 3: Use new unified defender coordinate system
                # get_defender_coords handles coordinate orientation automatically
                start = get_defender_coords(
                    first_coords,
                    is_away_offense,
                    aggression_call,
                    bh_first_spot or "key",
                    None,
                    is_ball_handler=True
                )

            # PHASE 4: get_defender_coords returns coords in same orientation as input
            # No need to flip - wrapper handles orientation automatically
            # (Removed manual flipping for non-BH defenders)

            movement = []

            if pos == bh_pos:
                for t, _, spot in bh_timeline:
                    bh_coords = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
                    # HCO_STRING_SPOTS are in home orientation
                    # Flip to away orientation if needed (wrapper expects coords in current orientation)
                    if is_away_offense:
                        bh_coords = get_away_player_coords(bh_coords)
                    # PHASE 3: Use new unified defender coordinate system
                    # get_defender_coords handles coordinate orientation automatically
                    d_coords = get_defender_coords(
                        bh_coords,
                        is_away_offense,
                        aggression_call,
                        spot or "key",
                        None,
                        is_ball_handler=True
                    )
                    movement.append({
                        "timestamp": t,
                        "coords": d_coords,
                        "action": ACTIONS["GUARD_BALL"]
                    })
            elif pos in off_lineup:
                off_player = off_lineup[pos]
                timeline = action_timeline.get(off_player, [])
                
                # Get pre-calculated ball handler coords by step
                ball_handler_coords_by_step = roles.get("ball_handler_coords_by_step", [])
                
                for step_idx, (t, _, spot) in enumerate(timeline):
                    o_coords = HCO_STRING_SPOTS.get(spot, HCO_STRING_SPOTS["key"])
                    
                    # Use pre-calculated ball handler coords for this step index
                    if step_idx < len(ball_handler_coords_by_step):
                        current_bh_coords = ball_handler_coords_by_step[step_idx]
                    else:
                        # Fallback to final position if step index out of range
                        current_bh_coords = ball_handler_end_coords or HCO_STRING_SPOTS["key"]
                    
                    # print(f"🛡️ Defender {pos} at step {step_idx} (t={t}): Guarding player at {spot}, Ball at {current_bh_coords}")
                    
                    # PHASE 4: Use new unified defender coordinate system
                    # get_defender_coords handles coordinate orientation automatically
                    # Need ball handler's spot for this step (for non-BH defender complex logic)
                    bh_spot_for_step = next(
                        (step[2] for step in bh_timeline if step[0] == t),
                        bh_last_spot or "key"
                    )
                    d_coords = get_defender_coords(
                        o_coords,
                        is_away_offense,
                        aggression_call,
                        spot,  # Use spot from offensive player's action
                        current_bh_coords,
                        is_ball_handler=False,
                        ball_spot=bh_spot_for_step  # Pass ball handler's spot for non-BH defender logic
                    )
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
        
        # Determine if away team is on offense ONCE at the start (not inside loops)
        # This ensures consistency when loading saved games where game state may have changed
        is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
        
        # Group all positions that appear in any step
        all_positions = set()
        for step in steps:
            all_positions.update(step.get("pos_actions", {}).keys())
        
        # Build animation for OFFENSIVE players from skeleton
        offensive_animations = {}  # Store by position for defensive matching
        
        # Build animation for OFFENSIVE players from skeleton
        for position in all_positions:
            player = off_lineup.get(position)
            if not player:
                continue
            
            player_id = getattr(player, "player_id", None)
            if not player_id:
                continue
            
            # 🔍 DEBUG: Log position to player ID mapping for steps 15, 16, 17 (3-2 Motion bug)
            # Check steps around the problematic pass to identify indexing issue
            for check_step_idx in [15, 16, 17]:
                if len(steps) > check_step_idx and steps[check_step_idx].get("pos_actions", {}).get(position):
                    step_action = steps[check_step_idx].get("pos_actions", {}).get(position).get("action")
                    step_timestamp = steps[check_step_idx].get("timestamp", 0)
                    if step_action in ["pass", "receive"]:
                        player_name = getattr(player, "name", "unknown")
                        logging.warning(f"🔍 [SKELETON MAPPING] Step {check_step_idx} (timestamp {step_timestamp}) - Position {position} → Player {player_name} (ID: {player_id[:8]}) with action: {step_action}")
            
            # Build movement array from steps
            movement = []
            has_ball_steps = []
            start_coords = None
            end_coords = None
            total_steps = len(steps)
            
            # 🔍 DEBUG: Track which skeleton steps map to which movement array indices
            step_mapping = []  # Will store (skeleton_step_idx, timestamp) for each movement entry
            
            for step_idx, step in enumerate(steps):
                pos_action = step.get("pos_actions", {}).get(position)
                if not pos_action:
                    continue
                
                timestamp = step.get("timestamp", 0)
                step_mapping.append((step_idx, timestamp))  # Track mapping
                
                # Get action early to check if we should use offset coords for screeners
                action = pos_action.get("action", "drift")
                
                # Handle both coords and location formats
                has_opp = pos_action.get("opp", False)
                coords_from_location = False
                
                # Opp field handling (debug logs removed)
                
                if "coords" in pos_action:
                    coords = pos_action.get("coords", {"x": 50, "y": 25})
                    # Coords already exist - these should have been set by apply_opposite_side_logic()
                    coords_already_flipped = True
                elif "location" in pos_action:
                    # Convert location string to coordinates
                    location = pos_action.get("location", "key")
                    
                    # ✅ SCREEN OFFSET: Use OFFSET_SPOTS for screen actions, otherwise use HCO_STRING_SPOTS
                    # This ensures screeners animate to offset positions to avoid visual overlap
                    # Check both ACTIONS["SCREEN"] (which is "screen") and literal "screen" for safety
                    if action == ACTIONS["SCREEN"] or action == "screen":
                        # Try to use offset coords for screeners, fallback to standard if not available
                        coords = OFFSET_SPOTS.get(location) or HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
                    else:
                        # Use standard coordinates for non-screen actions
                        coords = HCO_STRING_SPOTS.get(location, {"x": 50, "y": 25})
                    
                    coords_from_location = True
                    coords_already_flipped = False
                else:
                    coords = {"x": 50, "y": 25}
                    coords_already_flipped = False
                
                # ✅ FIX: Handle "opp" field for FCP/HCT skeletons when location exists (coords need to be calculated)
                # Players with opp=True should be on the opposite side of the court
                if (is_fcp or is_hct) and has_opp and coords_from_location:
                    # Player with opp=True should be on opposite side (defensive side)
                    if is_away_offense:
                        # Away team offense - ball handlers go to home side (defensive side)
                        # No coordinate flip needed - they stay on home side (HCO_STRING_SPOTS are in home orientation)
                        pass
                    else:
                        # Home team offense - ball handlers go to away side (defensive side)
                        # Flip coordinates to away side
                        coords = get_away_player_coords(coords)
                        coords_already_flipped = True
                elif (is_fcp or is_hct) and not has_opp and coords_from_location:
                    # Player without opp field stays on same side as normal offense
                    if is_away_offense:
                        # Away team offense - outlet players go to away side (offensive side)
                        # Flip coordinates to away side (normal away team flip)
                        # This will happen in the normal away team flip logic below
                        pass
                    else:
                        # Home team offense - outlet players stay on home side (offensive side)
                        # No coordinate flip needed
                        pass
                
                # Apply coordinate flipping for AWAY team (HCO_STRING_SPOTS are in home orientation)
                # Home team uses coords as-is to attack home basket (x=90)
                # Away team needs to flip to attack away basket (x=10)
                # is_away_offense calculated once at function start (line 809) for consistency
                # Only flip if not already flipped by opp logic above
                # ✅ SCREEN OFFSET: Flip offset coords for away team (determine offset first, then flip)
                if is_away_offense and not coords_already_flipped:
                    coords = get_away_player_coords(coords)
                
                if start_coords is None:
                    start_coords = coords
                end_coords = coords
                
                # Determine if player has ball at this step
                # Note: "pass" means releasing ball, NOT holding it
                has_ball = action in ["handle_ball", "receive", "shoot", "drive"]
                
                movement.append({
                    "timestamp": timestamp,
                    "coords": coords,
                    "action": action
                })
                has_ball_steps.append(has_ball)
            
            if not movement:
                continue
            
            # 🔍 DEBUG: Log movement array mapping for SF and PG at indices 15, 16, 17 (3-2 Motion bug)
            if position in ["SF", "PG"] and len(movement) > 16:
                for check_mov_idx in [15, 16, 17]:
                    if check_mov_idx < len(step_mapping):
                        skeleton_idx, timestamp = step_mapping[check_mov_idx]
                        player_name = getattr(player, "name", "unknown")
                        logging.warning(f"🔍 [MOVEMENT MAPPING] {position} ({player_name}) - movement[{check_mov_idx}] = skeleton step {skeleton_idx} (timestamp {timestamp})")
            
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
                # Use HCT-specific defensive positioning with dynamic tracking
                defensive_anims = self._position_hct_defenders(
                    offensive_animations,  # Pass offensive animations dict (like FCP)
                    def_lineup,
                    steps
                )
                animations.extend(defensive_anims)
            else:
                # Check if defense is a zone type (e.g., "2-3 Zone", "3-2 Zone", "1-3-1 Zone")
                from BackEnd.utils.defense_utils import is_zone_defense
                defense_playcall = self.game.game_state.get("defense_playcall", "Man")
                if is_zone_defense(defense_playcall):
                    # Use zone defense positioning (currently supports 2-3 zone, will expand for other types)
                    defensive_anims = self._position_zone_defenders(
                        offensive_animations,
                        def_lineup,
                        steps
                    )
                    animations.extend(defensive_anims)
                else:
                    # Use standard defensive positioning for HCO (man-to-man)
                    defensive_anims = self._position_standard_defenders(
                        offensive_animations, 
                        def_lineup, 
                        steps
                    )
                    animations.extend(defensive_anims)
        
        return animations
    
    def _position_fcp_defenders(self, offensive_animations, def_lineup, skeleton_steps):
        """
        Position defensive players for Full Court Press scenarios.
        
        Strategy:
        - Each defender guards the offensive player at their position
        - Defender maintains same Y coordinate as their assignment
        - Defender is positioned 3 grid units closer to the offensive basket
        - Ball handler is determined per step (dynamic) for consistent guard logic
        
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

        # Precompute ball handler per timestamp (dynamic by step)
        ball_handler_by_timestamp = {}
        initial_ball_handler_pos = None
        for pos, off_anim in offensive_animations.items():
            has_ball_list = off_anim.get("hasBallAtStep", [])
            for idx, off_step in enumerate(off_anim.get("movement", [])):
                if idx < len(has_ball_list) and has_ball_list[idx]:
                    ts = off_step.get("timestamp")
                    if ts is not None:
                        ball_handler_by_timestamp[ts] = pos
                        if initial_ball_handler_pos is None:
                            initial_ball_handler_pos = pos
        if initial_ball_handler_pos is None:
            initial_ball_handler_pos = "PG"
        
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

                # Determine current ball handler at this timestamp
                current_ball_handler_pos = ball_handler_by_timestamp.get(timestamp, initial_ball_handler_pos)
                is_guarding_ball_handler = position == current_ball_handler_pos
                
                # Defender position: same Y, X offset toward offensive basket
                def_coords = {
                    "x": off_coords["x"] + x_offset,
                    "y": off_coords["y"]
                }
                
                # Clamp X to valid court bounds (0-100)
                def_coords["x"] = max(0, min(100, def_coords["x"]))
                
                # Determine defensive action based on offensive action
                if is_guarding_ball_handler:
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

    def _position_hct_defenders(self, offensive_animations, def_lineup, skeleton_steps):
        """
        Position defensive players for Half Court Trap scenarios.
        
        Strategy (parallel to FCP):
        - Defenders start at initial trap positions (Step 0 only)
        - Then use real-time tracking of offensive players (like FCP)
        - Each defender tracks their matched offensive player step-by-step
        - Never cross half court (x-boundary enforcement)
        - Primary trap defender (PG) follows ball handler more closely
        
        Args:
            offensive_animations: Dict mapping position → offensive player animation (same as FCP)
            def_lineup: Dict of defensive players by position
            skeleton_steps: List of skeleton steps for timing
            
        Returns:
            List of defensive player animations
        """
        defensive_animations = []
        
        # Determine court orientation
        is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
        
        # Define initial HCT positions based on court orientation (for Step 0 setup only)
        if is_away_offense:
            # Home team defending (away team on offense)
            initial_hct_positions = {
                "PG": {"x": 44, "y": 25},   # Deep Key
                "SG": {"x": 44, "y": 35},   # Deep Upper Wing
                "SF": {"x": 44, "y": 15},   # Deep Lower Wing
                "PF": {"x": 45, "y": 30},   # Opposite side upper (matches frontend)
                "C": {"x": 45, "y": 20}     # Opposite side lower (matches frontend)
            }
            # Half-court boundary for away offense (home defending)
            halfcourt_boundary = 53  # Max x coordinate defenders can reach
            x_offset_toward_basket = -2  # Offset toward offensive basket (left side)
        else:
            # Away team defending (home team on offense)
            initial_hct_positions = {
                "PG": {"x": 57, "y": 25},   # Deep Key
                "SG": {"x": 57, "y": 35},   # Deep Upper Wing
                "SF": {"x": 57, "y": 15},   # Deep Lower Wing
                "PF": {"x": 56, "y": 30},   # Opposite side upper (matches frontend flip: 101-45=56)
                "C": {"x": 56, "y": 20}     # Opposite side lower (matches frontend flip: 101-45=56)
            }
            # Half-court boundary for home offense (away defending)
            halfcourt_boundary = 47  # Min x coordinate defenders can reach
            x_offset_toward_basket = 2  # Offset toward offensive basket (right side)
        
        # Find ball handler position for trap focus
        ball_handler_pos = None
        ball_handler_by_timestamp = {}
        for pos, off_anim in offensive_animations.items():
            has_ball_list = off_anim.get("hasBallAtStep", [])
            for idx, off_step in enumerate(off_anim.get("movement", [])):
                if idx < len(has_ball_list) and has_ball_list[idx]:
                    ts = off_step.get("timestamp")
                    if ts is not None:
                        ball_handler_by_timestamp[ts] = pos
                        if ball_handler_pos is None:
                            ball_handler_pos = pos
        if not ball_handler_pos:
            ball_handler_pos = "PG"  # Fallback
        
        # Match each defensive position to offensive position (man-to-man, like FCP)
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
            
            # Step 0: Start at initial HCT position (setup/trap formation)
            setup_coords = initial_hct_positions[position]
            def_movement.append({
                "timestamp": 0,
                "coords": setup_coords,
                "action": "STAND"
            })
            def_start = setup_coords
            
            # Step 1+: Real-time tracking of offensive player (like FCP)
            for off_step in off_anim["movement"]:
                timestamp = off_step["timestamp"]
                off_coords = off_step["coords"]
                
                # Skip Step 0 since we already handled it above
                if timestamp == 0:
                    continue
                
                # Determine current ball handler at this timestamp
                current_ball_handler_pos = ball_handler_by_timestamp.get(timestamp, ball_handler_pos)
                
                # Calculate defensive position based on offensive position
                # For HCT: defenders are positioned closer with trap focus
                if position == "PG" and position == current_ball_handler_pos:
                    # Primary trap defender tracking ball handler - follow closely
                    def_coords = {
                        "x": off_coords["x"] + x_offset_toward_basket,
                        "y": off_coords["y"]
                    }
                elif position == "PG":
                    # PG tracks ball handler even if not guarding him
                    ball_handler_anim = offensive_animations.get(current_ball_handler_pos)
                    if ball_handler_anim and ball_handler_anim["movement"]:
                        # Find ball handler's position at this timestamp
                        bh_coords = off_coords  # Default to current offensive position
                        for bh_step in ball_handler_anim["movement"]:
                            if bh_step["timestamp"] == timestamp:
                                bh_coords = bh_step["coords"]
                                break
                        def_coords = {
                            "x": bh_coords["x"] + x_offset_toward_basket,
                            "y": bh_coords["y"]
                        }
                    else:
                        # Fallback: track assigned offensive player
                        def_coords = {
                            "x": off_coords["x"] + x_offset_toward_basket,
                            "y": off_coords["y"]
                        }
                else:
                    # Other defenders: track their assigned offensive player
                    # Tighter spacing than FCP (smaller offset)
                    tighter_offset = x_offset_toward_basket // 2 if abs(x_offset_toward_basket) > 1 else x_offset_toward_basket
                    def_coords = {
                        "x": off_coords["x"] + tighter_offset,
                        "y": off_coords["y"]
                    }
                
                # Enforce half-court boundary (defenders never cross x=50)
                if is_away_offense:
                    def_coords["x"] = min(halfcourt_boundary, def_coords["x"])
                else:
                    def_coords["x"] = max(halfcourt_boundary, def_coords["x"])
                
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
            
            if not def_movement or len(def_movement) == 1:
                # Only setup position, no movement - extend with same position
                def_end = setup_coords
                if len(off_anim["movement"]) > 1:
                    last_timestamp = off_anim["movement"][-1]["timestamp"]
                    def_movement.append({
                        "timestamp": last_timestamp,
                        "coords": setup_coords,
                        "action": "STAND"
                    })
            
            # All defenders have ball at no steps
            has_ball_steps = [False] * len(def_movement)
            duration = def_movement[-1]["timestamp"] if def_movement else 0
            
            defensive_animations.append({
                "playerId": def_player_id,
                "start": def_start or setup_coords,
                "end": def_end or setup_coords,
                "movement": def_movement,
                "hasBallAtStep": has_ball_steps,
                "duration": duration
            })
        
        return defensive_animations

    def _position_zone_defenders(self, offensive_animations, def_lineup, skeleton_steps):
        """
        Position defensive players for Zone Defense (2-3 zone).
        
        Strategy:
        - Each defender guards a zone area, not a specific player
        - Zones shift based on ball location
        - Overlapping zones handled with specific logic
        - Priorities: BH in zone → 1 player in zone → >1 player (closest to basket) → 0 players (closest spot to BH)
        
        Args:
            offensive_animations: Dict mapping position → offensive player animation
            def_lineup: Dict of defensive players by position
            skeleton_steps: List of skeleton steps for timing
            
        Returns:
            List of defensive player animations
        """
        from BackEnd.utils.shared_defense import (
            _get_23_zone_boundaries,
            _get_32_zone_boundaries,
            _get_131_zone_boundaries,
            assign_all_zone_defenders,
            _point_in_zone
        )
        from BackEnd.utils.shared import get_away_player_coords
        
        defensive_animations = []
        
        # Determine court orientation
        is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
        aggression = self.game.defense_team.strategy_calls.get("aggression_call", "normal")
        
        # Build offensive player positions by step for tracking
        offensive_positions_by_step = {}
        ball_handler_pos = None
        
        for pos, off_anim in offensive_animations.items():
            offensive_positions_by_step[pos] = []
            for step in off_anim.get("movement", []):
                coords = step.get("coords", {"x": 50, "y": 25})
                # ✅ DON'T unflip offensive coords - pass them as-is to zone functions
                # assign_bh_defender_coords and assign_non_bh_defender_coords expect
                # coords in their original flipped state (away orientation if away offense)
                # They will unflip internally, calculate in home orientation, and return home orientation coords
                offensive_positions_by_step[pos].append(coords)
            
            # Check if this is the ball handler (has ball at step 0)
            if off_anim.get("hasBallAtStep", [False])[0]:
                ball_handler_pos = pos
        
        if not ball_handler_pos:
            # Fallback: assume PG is ball handler
            ball_handler_pos = "PG"
        
        # Get ball handler's spot from first skeleton step
        ball_spot = "key"  # Default
        if skeleton_steps and len(skeleton_steps) > 0:
            first_step = skeleton_steps[0]
            bh_action = first_step.get("pos_actions", {}).get(ball_handler_pos, {})
            ball_spot = bh_action.get("location") or bh_action.get("spot") or "key"
        
        # Get zone boundaries based on ball location (applies shifts)
        # ✅ Zone boundaries should be in SAME orientation as offensive coords
        # When away team has ball, offensive coords are in away orientation (flipped)
        # So zone boundaries should also be in away orientation (flipped) to match
        defense_playcall = self.game.game_state.get("defense_playcall", "Man")
        if defense_playcall == "3-2 Zone":
            zone_boundaries = _get_32_zone_boundaries(ball_spot, is_away_offense)
        elif defense_playcall == "1-3-1 Zone":
            zone_boundaries = _get_131_zone_boundaries(ball_spot, is_away_offense)
        else:
            zone_boundaries = _get_23_zone_boundaries(ball_spot, is_away_offense)
        
        # Create defensive animations for each position
        for def_pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            def_player = def_lineup.get(def_pos)
            if not def_player:
                continue
            
            def_player_id = getattr(def_player, "player_id", None)
            if not def_player_id:
                continue
            
            def_movement = []
            def_start = None
            def_end = None
            
            # Process each step
            max_steps = max(
                len(off_anim.get("movement", [])) 
                for off_anim in offensive_animations.values()
            ) if offensive_animations else 1
            
            for step_index in range(max_steps):
                # Dynamically determine who has ball at THIS step (similar to man-to-man)
                current_ball_handler_pos = None
                for pos, off_anim in offensive_animations.items():
                    has_ball_list = off_anim.get("hasBallAtStep", [])
                    if step_index < len(has_ball_list) and has_ball_list[step_index]:
                        current_ball_handler_pos = pos
                        break
                
                # If no one has ball at this step, use previous ball handler (or fallback)
                if not current_ball_handler_pos:
                    current_ball_handler_pos = ball_handler_pos
                
                # Get ball handler coords for this step using CURRENT ball handler position
                bh_coords_list = offensive_positions_by_step.get(current_ball_handler_pos, [])
                ball_handler_coords = bh_coords_list[step_index] if step_index < len(bh_coords_list) else (
                    bh_coords_list[-1] if bh_coords_list else {"x": 50, "y": 25}
                )
                
                # Get ball handler's spot for this step using CURRENT ball handler position
                if step_index < len(skeleton_steps):
                    step = skeleton_steps[step_index]
                    bh_action = step.get("pos_actions", {}).get(current_ball_handler_pos, {})
                    current_ball_spot = bh_action.get("location") or bh_action.get("spot") or ball_spot
                else:
                    current_ball_spot = ball_spot
                
                # Update zone boundaries if ball spot changed (shift logic)
                # ✅ Zone boundaries should be in SAME orientation as offensive coords
                defense_playcall = self.game.game_state.get("defense_playcall", "Man")
                if defense_playcall == "3-2 Zone":
                    zone_boundaries = _get_32_zone_boundaries(current_ball_spot, is_away_offense)
                elif defense_playcall == "1-3-1 Zone":
                    zone_boundaries = _get_131_zone_boundaries(current_ball_spot, is_away_offense)
                else:
                    zone_boundaries = _get_23_zone_boundaries(current_ball_spot, is_away_offense)
                
                # Build list of offensive players with their coords and ball handler status
                offensive_players = []
                for off_pos, off_anim in offensive_animations.items():
                    coords_list = offensive_positions_by_step.get(off_pos, [])
                    coords = coords_list[step_index] if step_index < len(coords_list) else (
                        coords_list[-1] if coords_list else {"x": 50, "y": 25}
                    )
                    
                    # Get spot for this player
                    if step_index < len(skeleton_steps):
                        step = skeleton_steps[step_index]
                        off_action = step.get("pos_actions", {}).get(off_pos, {})
                        spot = off_action.get("location") or off_action.get("spot") or "key"
                    else:
                        spot = "key"
                    
                    # Get player object to get player_id
                    off_player_obj = self.game.offense_team.lineup.get(off_pos)
                    player_id = getattr(off_player_obj, "player_id", None) if off_player_obj else None
                    
                    offensive_players.append({
                        "player_id": player_id,
                        "coords": coords,
                        "is_ball_handler": off_pos == current_ball_handler_pos,
                        "spot": spot
                    })
                
                # Assign defensive coordinates for this defender at this step
                # Use assign_all_zone_defenders which handles overlaps and priorities
                # ✅ Pass is_away_offense as-is - zone functions expect coords in original flipped state
                # They will unflip internally, calculate in home orientation, and return home orientation coords
                defender_coords_dict, defender_to_offensive_player = assign_all_zone_defenders(
                    zone_boundaries,
                    offensive_players,
                    ball_handler_coords,
                    current_ball_spot,
                    aggression,
                    is_away_offense
                )
                
                # Store defender assignments for this step (for shot resolution)
                if not hasattr(self.game, 'zone_defender_assignments_by_step'):
                    self.game.zone_defender_assignments_by_step = {}
                self.game.zone_defender_assignments_by_step[step_index] = defender_to_offensive_player
                
                def_coords = defender_coords_dict.get(def_pos)
                if not def_coords:
                    # Fallback: use center of zone
                    zone_coords_list = zone_boundaries.get(def_pos, [])
                    if zone_coords_list:
                        # Average of zone coordinates (zone boundaries are in away orientation if away offense)
                        avg_x = sum(c[0] for c in zone_coords_list) / len(zone_coords_list)
                        avg_y = sum(c[1] for c in zone_coords_list) / len(zone_coords_list)
                        def_coords = {"x": int(avg_x), "y": int(avg_y)}
                    else:
                        def_coords = {"x": 50, "y": 25}
                
                # Check if this defender is guarding the ball handler
                zone_coords_for_check = zone_boundaries.get(def_pos, [])
                is_guarding_bh = ball_handler_coords and _point_in_zone(ball_handler_coords, zone_coords_for_check, False)
                
                # ✅ IMPORTANT: assign_all_zone_defenders returns coords in HOME orientation
                # (assign_bh_defender_coords now returns home orientation when away team has ball)
                # (assign_non_bh_defender_coords returns home orientation directly)
                # When away team is on offense, we need to flip ALL defensive coords to away orientation
                # to match the offensive coords (which are also in away orientation)
                # This ensures all players (offense and defense) are positioned on the away side of the court
                if is_away_offense:
                    def_coords_before_flip = def_coords.copy()
                    def_coords = get_away_player_coords(def_coords)
                
                # Get timestamp
                if step_index < len(skeleton_steps):
                    timestamp = skeleton_steps[step_index].get("timestamp", step_index * 800)
                else:
                    timestamp = (len(skeleton_steps) - 1) * 800 if skeleton_steps else step_index * 800
                
                if step_index == 0:
                    def_start = def_coords
                
                def_end = def_coords
                
                # Determine action (guard_ball if ball handler in zone, otherwise guard_offball)
                zone_coords = zone_boundaries.get(def_pos, [])
                action = "guard_offball"
                if ball_handler_coords and _point_in_zone(ball_handler_coords, zone_coords, is_away_offense):
                    action = "guard_ball"
                
                def_movement.append({
                    "timestamp": timestamp,
                    "coords": def_coords,
                    "action": action
                })
            
            if not def_movement:
                continue
            
            # All defenders have ball at no steps (defensive players never have ball)
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

    def _position_standard_defenders(self, offensive_animations, def_lineup, skeleton_steps):
        """
        Position defensive players for standard HCO scenarios.
        
        Strategy:
        - Each defender guards the offensive player at their position
        - Use standard defensive positioning logic from shared_defense
        - Track offensive players dynamically through the play
        
        Args:
            offensive_animations: Dict mapping position → offensive player animation
            def_lineup: Dict of defensive players by position
            skeleton_steps: List of skeleton steps for timing
            
        Returns:
            List of defensive player animations
        """
        from BackEnd.utils.shared_defense import get_defender_coords
        
        defensive_animations = []
        
        # Determine court orientation
        is_away_offense = self.game.offense_team.team_id == self.game.away_team.team_id
        aggression = self.game.defense_team.strategy_calls.get("aggression_call", "normal")
        
        # Build offensive player positions by step for tracking
        # PHASE 6: get_defender_coords handles coordinate orientation automatically
        # Store coords as-is (away orientation if away offense, home orientation if home offense)
        # The wrapper will handle orientation transformation internally
        offensive_positions_by_step = {}
        for pos, off_anim in offensive_animations.items():
            offensive_positions_by_step[pos] = []
            for step in off_anim.get("movement", []):
                coords = step.get("coords", {"x": 50, "y": 25})
                offensive_positions_by_step[pos].append(coords)
        
        # Find ball handler position (player with ball at step 0)
        ball_handler_pos = None
        for pos, off_anim in offensive_animations.items():
            if off_anim.get("hasBallAtStep", [False])[0]:  # Has ball at first step
                ball_handler_pos = pos
                break
        
        if not ball_handler_pos:
            # Fallback: assume PG is ball handler
            ball_handler_pos = "PG"
        
        
        # Create defensive animations for each position
        for def_pos in ['PG', 'SG', 'SF', 'PF', 'C']:
            def_player = def_lineup.get(def_pos)
            if not def_player:
                continue
            
            def_player_id = getattr(def_player, "player_id", None)
            if not def_player_id:
                continue
            
            
            # Get the offensive player this defender is guarding
            off_pos_to_guard = def_pos  # Man-to-man by position
            off_coords_list = offensive_positions_by_step.get(off_pos_to_guard, [])
            
            def_movement = []
            def_start = None
            def_end = None
            
            # Step 0: Initial defensive position
            if off_coords_list:
                off_coords = off_coords_list[0]
                
                # Calculate initial defensive position
                if off_pos_to_guard == ball_handler_pos:
                    # Ball handler defender - extract ball handler's spot from first skeleton step
                    first_step = skeleton_steps[0] if skeleton_steps else {}
                    bh_action = first_step.get("pos_actions", {}).get(ball_handler_pos, {})
                    bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                    
                    # PHASE 3: Use new unified defender coordinate system
                    # get_defender_coords handles coordinate orientation automatically
                    def_coords = get_defender_coords(
                        off_coords,
                        is_away_offense,
                        aggression,
                        bh_spot,
                        None,
                        is_ball_handler=True
                    )
                else:
                    # Non-ball handler defender
                    bh_coords = offensive_positions_by_step.get(ball_handler_pos, [{}])[0] if ball_handler_pos in offensive_positions_by_step else {"x": 50, "y": 25}
                    
                    # Extract spots from first skeleton step
                    first_step = skeleton_steps[0] if skeleton_steps else {}
                    bh_action = first_step.get("pos_actions", {}).get(ball_handler_pos, {})
                    bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                    
                    o_action = first_step.get("pos_actions", {}).get(off_pos_to_guard, {})
                    o_spot = o_action.get("location") or o_action.get("spot") or "key"
                    
                    # PHASE 4: Use new unified defender coordinate system
                    # get_defender_coords handles coordinate orientation automatically
                    # Pass ball_spot for non-BH defenders (required for complex positioning logic)
                    def_coords = get_defender_coords(
                        off_coords,
                        is_away_offense,
                        aggression,
                        o_spot,
                        bh_coords,
                        is_ball_handler=False,
                        ball_spot=bh_spot  # Pass ball handler's spot for non-BH defender logic
                    )
                
                # get_defender_coords returns coords in same orientation as input
                # No need to flip - wrapper handles orientation automatically
                
                def_start = def_coords
                def_movement.append({
                    "timestamp": 0,
                    "coords": def_coords,
                    "action": "guard_ball" if off_pos_to_guard == ball_handler_pos else "guard_offball"
                })
            
            # Subsequent steps: Track offensive player
            for step_idx, skeleton_step in enumerate(skeleton_steps[1:], start=1):
                timestamp = skeleton_step.get("timestamp", step_idx * 800)
                
                if step_idx < len(off_coords_list):
                    off_coords = off_coords_list[step_idx]
                    
                    # Dynamically determine who has ball at THIS step
                    current_ball_handler_pos = None
                    for pos, off_anim in offensive_animations.items():
                        if off_anim.get("hasBallAtStep", [])[step_idx] if step_idx < len(off_anim.get("hasBallAtStep", [])) else False:
                            current_ball_handler_pos = pos
                            break
                    
                    # If no one has ball at this step, use previous ball handler
                    if not current_ball_handler_pos:
                        current_ball_handler_pos = ball_handler_pos
                    
                    # Calculate defensive position for this step
                    if off_pos_to_guard == current_ball_handler_pos:
                        # Ball handler defender - extract CURRENT ball handler's spot from skeleton step
                        bh_action = skeleton_step.get("pos_actions", {}).get(current_ball_handler_pos, {})
                        bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                        
                        # PHASE 3: Use new unified defender coordinate system
                        # get_defender_coords handles coordinate orientation automatically
                        def_coords = get_defender_coords(
                            off_coords,
                            is_away_offense,
                            aggression,
                            bh_spot,
                            None,
                            is_ball_handler=True
                        )
                    else:
                        # Non-ball handler defender - need CURRENT ball handler position for this step
                        bh_coords_list = offensive_positions_by_step.get(current_ball_handler_pos, [])
                        bh_coords = bh_coords_list[step_idx] if step_idx < len(bh_coords_list) else {"x": 50, "y": 25}
                        
                        # Extract spots from current skeleton step using CURRENT ball handler
                        bh_action = skeleton_step.get("pos_actions", {}).get(current_ball_handler_pos, {})
                        bh_spot = bh_action.get("location") or bh_action.get("spot") or "key"
                        
                        o_action = skeleton_step.get("pos_actions", {}).get(off_pos_to_guard, {})
                        o_spot = o_action.get("location") or o_action.get("spot") or "key"
                        
                        # PHASE 4: Use new unified defender coordinate system
                        # get_defender_coords handles coordinate orientation automatically
                        # Pass ball_spot for non-BH defenders (required for complex positioning logic)
                        def_coords = get_defender_coords(
                            off_coords,
                            is_away_offense,
                            aggression,
                            o_spot,
                            bh_coords,
                            is_ball_handler=False,
                            ball_spot=bh_spot  # Pass ball handler's spot for non-BH defender logic
                        )
                    # For BH defenders, get_defender_coords already returns correct orientation
                    
                    def_end = def_coords
                    def_movement.append({
                        "timestamp": timestamp,
                        "coords": def_coords,
                        "action": "guard_ball" if off_pos_to_guard == current_ball_handler_pos else "guard_offball"
                    })
                else:
                    # No more offensive movement - stay at last position
                    if def_movement:
                        last_coords = def_movement[-1]["coords"]
                        def_movement.append({
                            "timestamp": timestamp,
                            "coords": last_coords,
                            "action": "guard_offball"
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

    def get_latest_animation_packet(self):
        return self.latest_packet
