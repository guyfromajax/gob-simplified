from BackEnd.utils.shared import (
    get_player_by_pos,
    get_player_position,
    get_away_player_coords,
    calc_ag_segment_seconds,
)
from BackEnd.utils.shared_defense import (
    get_defender_coords
)
from collections import defaultdict
from BackEnd.constants import (
    HCO_STRING_SPOTS,
    OFFSET_SPOTS,
    ACTIONS,
    RIM_COORDS,
    TOP_KEY_COORDS,
    HOME_RIM_COORDS,
    AWAY_RIM_COORDS,
    HOME_TOP_KEY,
    AWAY_TOP_KEY,
    MADE_SHOT_SWEET_SPOT_HOME_RIM,
    MADE_SHOT_SWEET_SPOT_AWAY_RIM,
)
import random
import logging
from BackEnd.constants.fast_break_constants import (
    BALL_HANDLER_MOVE_X_MIN,
    BALL_HANDLER_MOVE_X_MAX,
    BALL_HANDLER_MOVE_Y_RANGE,
    STOPPER_OFFSET_MIN,
    STOPPER_OFFSET_MAX,
    FB_SHOT_SPOT_X_MIN,
    FB_SHOT_SPOT_X_MAX,
    FB_SHOT_SPOT_Y_RANGE,
    fast_break_shot_defender_end_coords,
    fast_break_secondary_shot_defender_end_coords,
    REBOUNDER_X_MIN,
    REBOUNDER_X_MAX,
    REBOUNDER_Y_RANGE,
    SHOT_ATTEMPT_REBOUNDER_Y_RANGE,
    OUTLET_PASSER_MOVE_X,
)

from BackEnd.engine.defender_placement import (
    build_all_animations,
    defender_grid_from_animations,
)
# Re-exported for existing importers: scripts/s1_openness_monte_carlo.py and
# tests/test_motion_subtle_defense.py import these FROM animator, and this commit is not
# allowed to move an outcome or a test. The definitions now live in defender_placement.
from BackEnd.engine.defender_placement import (  # noqa: F401
    _attack_drive_defender_override,
    _defender_lag_fraction,
    _subtle_defender_should_freeze,
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
        # ✅ PERFORMANCE: Skip animation generation for full simulations
        if self.game.game_state.get("_is_full_simulation", False):
            self.latest_packet = []
            return []

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

        def build_movement(player, end_coords, has_ball=False, action=ACTIONS["DRIFT"], archetype="standard"):
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
            
            # Debug logs removed to declutter output
            
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

            # Per-player game_seconds for the start→end segment, AG-driven via the
            # Movement Rate Refactor helper. Stamped on the end waypoint (HCT
            # pattern). Frontend authority shift comes in Phase 3c — until then
            # this is a payload-only addition; legacy `getPlayerDuration` still
            # drives visual durations on the frontend.
            game_seconds = calc_ag_segment_seconds(start, end, player, archetype=archetype)

            movement = [
                {"timestamp": 0, "coords": start, "action": action if not has_ball else ACTIONS["HANDLE"]},
                {"timestamp": duration, "coords": end, "action": action if not has_ball else ACTIONS["HANDLE"], "game_seconds": game_seconds},
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

        def is_player_animated(player_id):
            if player_id is None:
                return False
            want = str(player_id)
            return any(str(pid) == want for pid in animated_player_ids if pid is not None)

        def mark_player_animated(player_id):
            if player_id is not None:
                animated_player_ids.add(player_id)
        
        # ✅ Get get-back player IDs (used in both defensive stop and shot attempt paths)
        getback_player_ids = fb_roles.get("getback_player_ids", [])
        # Normalize IDs so int/string mixed payloads still map consistently.
        getback_player_ids_set = (
            {str(pid) for pid in getback_player_ids if pid is not None}
            if getback_player_ids
            else set()
        )
        # Shared player pools used by contract guardrails and rebounder routing.
        all_offensive_players = list(offense_team.lineup.values())
        all_defensive_players = list(defense_team.lineup.values())

        # Ball handler path
        # ✅ NEW LOGIC: Calculate ball handler's final position (used for both defensive stop and shot)
        import random
        ball_handler_outlet_x = fb_roles.get("ball_handler_outlet_x")
        ball_handler_outlet_y = fb_roles.get("ball_handler_outlet_y")
        ball_handler_move_x = fb_roles.get("ball_handler_move_x", 7)  # Default 7 if not set
        
        # Calculate additional movement from outlet position (pre-rolled by backend
        # when drive-cutoff resolution ran, so animation matches the contest geometry).
        if fb_roles.get("ball_handler_drive_roll_x") is not None:
            additional_move_x = int(fb_roles["ball_handler_drive_roll_x"])
            additional_move_y = int(fb_roles.get("ball_handler_drive_roll_y") or 0)
        else:
            move_distance = random.randint(BALL_HANDLER_MOVE_X_MIN, BALL_HANDLER_MOVE_X_MAX)
            x_direction = -1 if is_away_offense else 1
            additional_move_x = x_direction * move_distance
            additional_move_y = random.randint(-BALL_HANDLER_MOVE_Y_RANGE, BALL_HANDLER_MOVE_Y_RANGE)
        
        # Calculate ball handler's final position (coordinates already in correct orientation)
        # When ball handler beats defender (hold_up but shot attempt), use shot spot near rim
        # so the shooter doesn't take the shot from the confrontation/stop spot.
        ball_handler_beats_defender = hold_up and fb_roles.get("ball_handler_beats_defender")
        cutoff_meet_x = fb_roles.get("cutoff_meet_x")
        cutoff_meet_y = fb_roles.get("cutoff_meet_y")
        if (
            hold_up
            and cutoff_meet_x is not None
            and cutoff_meet_y is not None
            and not ball_handler_beats_defender
        ):
            # Drive-cutoff collision: BH ends at the meet point (shared with HCT cutoff).
            bh_end = {
                "x": max(4, min(97, int(cutoff_meet_x))),
                "y": max(1, min(49, int(cutoff_meet_y))),
            }
        elif ball_handler_beats_defender:
            # Ball handler beat defender: shot spot near rim (same as no defensive stop attempt)
            rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
            shot_distance = random.randint(FB_SHOT_SPOT_X_MIN, FB_SHOT_SPOT_X_MAX)
            if is_away_offense:
                bh_end_x = min(97, rim["x"] + shot_distance)
            else:
                bh_end_x = max(4, rim["x"] - shot_distance)
            bh_end_y = max(1, min(49, rim["y"] + random.randint(-FB_SHOT_SPOT_Y_RANGE, FB_SHOT_SPOT_Y_RANGE)))
            bh_end = {"x": bh_end_x, "y": bh_end_y}
        elif hold_up and ball_handler_outlet_x is not None and ball_handler_outlet_y is not None:
            # Defensive stop: ball handler ends at confrontation spot (outlet + short run)
            bh_end_x = max(4, min(97, ball_handler_outlet_x + additional_move_x))
            bh_end_y = max(1, min(49, ball_handler_outlet_y + additional_move_y))
            bh_end = {"x": bh_end_x, "y": bh_end_y}
        elif not hold_up and ball_handler_outlet_x is not None and ball_handler_outlet_y is not None:
            # Shot attempt with outlet (no defensive stop): shot spot near rim, same as beats_defender
            rim = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
            shot_distance = random.randint(FB_SHOT_SPOT_X_MIN, FB_SHOT_SPOT_X_MAX)
            if is_away_offense:
                bh_end_x = min(97, rim["x"] + shot_distance)
            else:
                bh_end_x = max(4, rim["x"] - shot_distance)
            bh_end_y = max(1, min(49, rim["y"] + random.randint(-FB_SHOT_SPOT_Y_RANGE, FB_SHOT_SPOT_Y_RANGE)))
            bh_end = {"x": bh_end_x, "y": bh_end_y}
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
            
        # Debug log removed to declutter output
        
        # Store final position for defender calculations (in HOME orientation)
        fb_roles["_bh_final_x"] = bh_end["x"]
        fb_roles["_bh_final_y"] = bh_end["y"]
        fb_roles["_bh_additional_move_x"] = abs(additional_move_x)  # Store absolute value for calculations
        
        if ball_handler:
            build_movement(ball_handler, bh_end, has_ball=True)
            mark_player_animated(getattr(ball_handler, "player_id", None))

        # Identify stopper
        stopper = None
        if hold_up and stopper_id:
            for d in defenders:
                if getattr(d, "player_id", None) == stopper_id:
                    stopper = d
                    break
        
        if hold_up:
            bh_stop_x = fb_roles.get("_bh_final_x", HOME_TOP_KEY["x"])
            bh_stop_y = fb_roles.get("_bh_final_y", HOME_TOP_KEY["y"])
            shot_defender = fb_roles.get("defender")

            if ball_handler_beats_defender:
                # FB shot after beating stopper: primary defender uses the unified shooter-relative
                # shot contest spot; secondary defender shares x and gets a +/-3 y offset.
                primary_defender_end = None
                if stopper:
                    end = fast_break_shot_defender_end_coords(
                        bh_stop_x, bh_stop_y, is_away_offense
                    )
                    build_movement(stopper, end, action=ACTIONS["GUARD_BALL"])
                    mark_player_animated(getattr(stopper, "player_id", None))
                    primary_defender_end = end
                sd_pid = getattr(shot_defender, "player_id", None) if shot_defender else None
                if shot_defender and sd_pid and sd_pid != stopper_id:
                    if primary_defender_end is None:
                        end_sd = fast_break_shot_defender_end_coords(
                            bh_stop_x, bh_stop_y, is_away_offense
                        )
                    else:
                        shot_defender_source_y = (
                            (getattr(shot_defender, "coords", {}) or {}).get("y", 25)
                        )
                        end_sd = fast_break_secondary_shot_defender_end_coords(
                            primary_defender_end["x"],
                            primary_defender_end["y"],
                            shot_defender_source_y,
                        )
                    build_movement(shot_defender, end_sd, action=ACTIONS["GUARD_BALL"])
                    mark_player_animated(sd_pid)

                for d in defenders:
                    if d is stopper or d is shot_defender:
                        continue
                    player_id = getattr(d, "player_id", None)
                    if player_id is not None and str(player_id) in getback_player_ids_set:
                        build_movement(d, between_key_and_rim(), action=ACTIONS["GUARD_OFFBALL"])
                        mark_player_animated(player_id)
            else:
                # Defensive stop (no shot): stopper at meet point or 1–3 x toward basket from BH end
                if stopper:
                    if cutoff_meet_x is not None and cutoff_meet_y is not None:
                        end = {
                            "x": max(4, min(97, int(cutoff_meet_x))),
                            "y": max(1, min(49, int(cutoff_meet_y))),
                        }
                    else:
                        stopper_offset = random.randint(STOPPER_OFFSET_MIN, STOPPER_OFFSET_MAX)
                        if is_away_offense:
                            stopper_x = max(4, bh_stop_x - stopper_offset)
                        else:
                            stopper_x = min(97, bh_stop_x + stopper_offset)
                        end = {"x": stopper_x, "y": bh_stop_y}
                    build_movement(stopper, end, action=ACTIONS["GUARD_BALL"])
                    mark_player_animated(getattr(stopper, "player_id", None))

                for d in defenders:
                    if d is stopper:
                        continue
                    player_id = getattr(d, "player_id", None)
                    if player_id is not None and str(player_id) in getback_player_ids_set:
                        build_movement(d, between_key_and_rim(), action=ACTIONS["GUARD_OFFBALL"])
                        mark_player_animated(player_id)
        else:
            shot_defender = fb_roles.get("defender")
            if shot_defender:
                bh_shot_x = fb_roles.get("_bh_final_x", bh_end["x"])
                bh_shot_y = fb_roles.get("_bh_final_y", bh_end["y"])
                defender_end = fast_break_shot_defender_end_coords(
                    bh_shot_x, bh_shot_y, is_away_offense
                )
                build_movement(shot_defender, defender_end, action=ACTIONS["GUARD_BALL"])
                mark_player_animated(getattr(shot_defender, "player_id", None))

            for d in defenders:
                if d is shot_defender:
                    continue
                player_id = getattr(d, "player_id", None)
                if player_id is not None and str(player_id) in getback_player_ids_set:
                    build_movement(d, between_key_and_rim(), action=ACTIONS["GUARD_OFFBALL"])
                    mark_player_animated(player_id)

        # Contract completeness guardrail:
        # ensure every get-back player has an animation endpoint, even when they were
        # not included in `defenders` above (role-filter mismatch or branch variance).
        for player in all_offensive_players + all_defensive_players:
            player_id = getattr(player, "player_id", None)
            if player_id is None:
                continue
            if str(player_id) not in getback_player_ids_set:
                continue
            if is_player_animated(player_id):
                continue
            build_movement(player, between_key_and_rim(), action=ACTIONS["GUARD_OFFBALL"])
            mark_player_animated(player_id)
        
        # ✅ Animate rebounders (players who stayed near rim, not get-back, not release)
        # Get outlet passer ID - they move forward 7 x-coords toward basket
        outlet_passer_id = fb_roles.get("outlet_passer")
        outlet_passer_id_set = {outlet_passer_id} if outlet_passer_id else set()
        
        # Get release player IDs (they're already animated as ball handler)
        release_player_ids = set()
        if self.game.turns and len(self.game.turns) > 0:
            for turn in reversed(self.game.turns[-10:]):
                if turn.get("result_type") in ["MISS", "MAKE", "BLOCK"]:
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
        #
        # Contract completeness guardrail: even when we intentionally skip outlet passer locomotion,
        # emit a no-op animation endpoint so frontend authority lookup can stay on animations[].end.
        if outlet_passer_id:
            outlet_passer = None
            for player in all_offensive_players + all_defensive_players:
                if getattr(player, "player_id", None) == outlet_passer_id:
                    outlet_passer = player
                    break
            if outlet_passer:
                passer_coords = getattr(outlet_passer, "coords", {}) or {}
                outlet_passer_spot = {
                    "x": float(passer_coords.get("x", 50)),
                    "y": float(passer_coords.get("y", 25)),
                }
                build_movement(outlet_passer, outlet_passer_spot, has_ball=False, action=ACTIONS["DRIFT"])
                mark_player_animated(outlet_passer_id)
        
        for player in all_offensive_players + all_defensive_players:
            player_id = getattr(player, "player_id", None)
            if not player_id or is_player_animated(player_id):
                continue
            
            # Skip outlet passer - already animated above
            if player_id in outlet_passer_id_set:
                continue
            
            # Skip release players (already animated as ball handler)
            if player_id in release_player_ids:
                continue
            
            # Skip get-back players (already animated as defenders)
            if str(player_id) in getback_player_ids_set:
                continue
            
            # This is a rebounder (stayed near rim for shot attempt)
            player_start_y = getattr(player, "coords", {}).get("y", 25)
            
            if hold_up:
                # ✅ Defensive Stop: x=40-60, y=starting_y ± 6 (clamped 1-49)
                # ✅ CLAMP: Clamp x to rim coordinates (10-90)
                target_y = max(1, min(49, player_start_y + random.randint(-REBOUNDER_Y_RANGE, REBOUNDER_Y_RANGE)))
                target_x = random.randint(REBOUNDER_X_MIN, REBOUNDER_X_MAX)
                # Clamp x between rim coordinates
                target_x = max(AWAY_RIM_COORDS["x"], min(HOME_RIM_COORDS["x"], target_x))
                target_spot = {
                    "x": target_x,
                    "y": target_y
                }
            else:
                # ✅ Shot Attempt: x=rim_x, y=rim_y ± 10 (clamped 1-49)
                # ✅ CLAMP: Clamp x to rim coordinates (10-90)
                rim_coords = AWAY_RIM_COORDS if is_away_offense else HOME_RIM_COORDS
                target_y = max(1, min(49, rim_coords["y"] + random.randint(-SHOT_ATTEMPT_REBOUNDER_Y_RANGE, SHOT_ATTEMPT_REBOUNDER_Y_RANGE)))
                target_x = rim_coords["x"]
                # Clamp x between rim coordinates (should already be within range, but ensure it)
                target_x = max(AWAY_RIM_COORDS["x"], min(HOME_RIM_COORDS["x"], target_x))
                target_spot = {
                    "x": target_x,
                    "y": target_y
                }
            
            build_movement(player, target_spot, has_ball=False, action=ACTIONS["DRIFT"])
            mark_player_animated(player_id)

        # Strict contract fill-in for role IDs that frontend expects in FB shot paths.
        players_by_id = {}
        for player in all_offensive_players + all_defensive_players + defenders:
            pid = getattr(player, "player_id", None)
            if pid is None:
                continue
            players_by_id[str(pid)] = player
        for candidate in [ball_handler, fb_roles.get("defender"), fb_roles.get("shot_defender")]:
            pid = getattr(candidate, "player_id", None) if candidate is not None else None
            if pid is not None:
                players_by_id[str(pid)] = candidate

        required_role_ids = []
        if stopper_id:
            required_role_ids.append(str(stopper_id))
        defender_obj = fb_roles.get("defender")
        defender_pid = getattr(defender_obj, "player_id", None) if defender_obj is not None else None
        if defender_pid:
            required_role_ids.append(str(defender_pid))

        for role_pid in required_role_ids:
            if is_player_animated(role_pid):
                continue
            role_player = players_by_id.get(str(role_pid))
            if role_player is None:
                logging.warning(
                    "capture_fast_break_animation missing required role player for endpoint fill-in (player_id=%s)",
                    role_pid,
                )
                continue
            role_coords = getattr(role_player, "coords", {}) or {}
            role_end = {
                "x": float(role_coords.get("x", 50)),
                "y": float(role_coords.get("y", 25)),
            }
            build_movement(role_player, role_end, has_ball=False, action=ACTIONS["DRIFT"])
            mark_player_animated(role_pid)
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
        # ✅ PERFORMANCE: Skip animation generation for full simulations
        if game.game_state.get("_is_full_simulation", False):
            self.latest_packet = []
            return []

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
            
            # Made shots: unified sweet spot (same as field goals); misses hit rim first
            if outcome == "MAKE":
                ball_coords = (
                    dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)
                    if rim["x"] == HOME_RIM_COORDS["x"]
                    else dict(MADE_SHOT_SWEET_SPOT_AWAY_RIM)
                )
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
        # ✅ PERFORMANCE: Skip animation generation for full simulations
        if self.game.game_state.get("_is_full_simulation", False):
            self.latest_packet = []
            return []
        
        offense_team = self.game.offense_team
        defense_team = self.game.defense_team
        off_lineup = offense_team.lineup
        def_lineup = defense_team.lineup
        aggression_call = defense_team.strategy_calls.get("aggression_call", "normal")
        is_away_offense = offense_team.team_id == self.game.away_team.team_id
        
        # Check if next play will be FCP/HCT (set after made shots)
        next_defensive_setup = roles.get("next_defensive_setup")

        # ✅ FIX: Handle missing "steps" or "action_timeline" keys gracefully
        # This can happen when serializable_roles is created without these fields
        steps = roles.get("steps", [])
        action_timeline = roles.get("action_timeline", {})
        logging.debug("action_timeline: %s", action_timeline)
        shooter = roles.get("shooter")
        ball_handler = roles.get("ball_handler")

        # If required fields are missing, return empty animations
        if not steps or shooter is None or ball_handler is None:
            logging.warning(f"capture_halfcourt_animation: missing required fields (steps={bool(steps)}, shooter={shooter is not None}, ball_handler={ball_handler is not None})")
            self.latest_packet = []
            return []

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
                    elif event.get("type") == "steal" and event.get("stealer_id"):
                        # A stealer (defender) named on the step owns the ball there → the ball
                        # tweens to him (HCO interception ball-attach; defenders are in players_by_id).
                        owner = players_by_id.get(event.get("stealer_id"))
                        if owner:
                            break
            ball_owner_by_step.append(owner)

        # Extend ball ownership to cover any additional timeline steps
        # ✅ FIX: Handle missing action_timeline (not serializable, so may be absent)
        timeline_lengths = [len(tl) for tl in action_timeline.values()] if action_timeline else []
        max_timeline_len = max(
            timeline_lengths + [len(ball_owner_by_step)]
        ) if timeline_lengths or ball_owner_by_step else 0
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

        # ✅ FIX: Extract ball handler timeline spots BEFORE the loop
        # This ensures bh_first_spot and bh_last_spot are available for all defenders
        bh_timeline = action_timeline.get(ball_handler, []) if action_timeline else []
        bh_first_spot = bh_timeline[0][2] if bh_timeline else None
        bh_last_spot = bh_timeline[-1][2] if bh_timeline else None
        
        # ✅ FIX: Extract ball_handler_end_coords from steps if action_timeline is missing
        # This handles the case where serializable_roles doesn't have action_timeline
        if ball_handler_end_coords is None and steps:
            # Try to extract from steps - find last step where ball handler has the ball
            for step in reversed(steps):
                pos_actions = step.get("pos_actions", {})
                if bh_pos in pos_actions:
                    action_info = pos_actions[bh_pos]
                    location_key = action_info.get("location") or action_info.get("spot", "key")
                    ball_handler_end_coords = HCO_STRING_SPOTS.get(location_key, HCO_STRING_SPOTS["key"])
                    if not bh_last_spot:
                        bh_last_spot = location_key
                    if not bh_first_spot:
                        bh_first_spot = location_key
                    break
        
        # ✅ FIX: Ensure ball_handler_end_coords has a default value
        if ball_handler_end_coords is None:
            ball_handler_end_coords = HCO_STRING_SPOTS["key"]

        for pos, defender in def_lineup.items():
            def_coords = None
            action_type = ACTIONS["GUARD_OFFBALL"]

            hasBallAtStep = [ball_owner_by_step[i] is defender for i in range(len(ball_owner_by_step))]

            if pos == bh_pos:
                # ✅ FIX: Ensure final_coords and first_coords always have valid values
                first_coords = HCO_STRING_SPOTS.get(bh_first_spot, ball_handler_end_coords) if bh_first_spot else ball_handler_end_coords
                final_coords = HCO_STRING_SPOTS.get(bh_last_spot, ball_handler_end_coords) if bh_last_spot else ball_handler_end_coords
                
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
        # ✅ PERFORMANCE: Skip animation generation for full simulations
        if self.game.game_state.get("_is_full_simulation", False):
            return []
        
        if not skeleton or "steps" not in skeleton:
            return []
        return self._build_all_animations(
            skeleton, off_lineup, def_lineup, add_defenders=add_defenders, is_fcp=is_fcp, is_hct=is_hct)

    def _build_all_animations(self, skeleton, off_lineup, def_lineup, add_defenders=True, is_fcp=False, is_hct=False):
        """Adapter onto the engine-owned producer in ``BackEnd.engine.defender_placement``.

        The body moved there verbatim (commit 1 of 2: pure relocation). This wrapper exists only
        to keep ``self.game`` plumbing and to PUBLISH the zone guard map the producer now returns
        instead of writing through ``game`` from inside its placement loop.

        The publish is conditional because the attribute's ABSENCE is load-bearing:
        ``phase_resolution.py:5314`` tests it with ``hasattr`` and ``:5336`` ``delattr``s it, so
        creating it on man-defense turns would change behaviour. Commit 2 removes the publish
        when the producer's outputs are consumed directly.
        """
        animations, zone_assignments = build_all_animations(
            self.game, skeleton, off_lineup, def_lineup,
            add_defenders=add_defenders, is_fcp=is_fcp, is_hct=is_hct,
        )
        if zone_assignments is not None:
            self.game.zone_defender_assignments_by_step = zone_assignments
        return animations
    
    def compute_defender_grid(self, skeleton, off_lineup, def_lineup, is_fcp=False, is_hct=False):
        """PURE, sim-safe per-step defender grid — runs the SAME offense-build + defender-placement
        as the render (via ``_build_all_animations``) but WITHOUT the full-sim early-return, so the
        interception contest and the render compute defender positions from ONE identical
        computation. Returns ``{step_idx: {def_pos: {x, y}}}``.

        An interception is an OUTCOME, so its defender geometry must be identical for animated and
        sim'd games — hence this bypasses the ``_is_full_simulation`` skip. (Perf: it builds the full
        animation to reuse the exact code; a grid-only fast path can follow if it ever matters.)

        PURE: ``_build_all_animations`` mutates the skeleton in place (ball-handler coord nudging,
        coord-flip), so we build on a deep copy — the shared skeleton the emitter/render also draw
        from is left untouched. Without this, calling the render code twice on one object is not
        idempotent and the two draws diverge.

        The build itself now lives in ``BackEnd.engine.defender_placement``; ``_build_all_animations``
        below is the adapter. NOTE (pre-existing, NOT caused by the relocation): the "ONE identical
        computation" claim above is aspirational — the contest's grid and the render's animations are
        still two separate computations that both draw from ``sim_rng``. That is what commit 2 fixes;
        this commit only moved the code."""
        import copy as _copy
        if not skeleton or "steps" not in skeleton:
            return {}
        try:
            anims = self._build_all_animations(
                _copy.deepcopy(skeleton), off_lineup, def_lineup, add_defenders=True, is_fcp=is_fcp, is_hct=is_hct)
        except Exception:
            return {}
        return self.defender_grid_from_animations(anims, def_lineup, len((skeleton.get("steps") or [])))

    @staticmethod
    def defender_grid_from_animations(anims, def_lineup, num_steps):
        """Moved to ``BackEnd.engine.defender_placement``; kept as a delegating alias because
        callers reach it through ``Animator``."""
        return defender_grid_from_animations(anims, def_lineup, num_steps)

    def get_latest_animation_packet(self):
        return self.latest_packet
