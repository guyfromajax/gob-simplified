import random
import logging
from BackEnd.constants import (
    THREE_POINT_PROBABILITY, 
    THREE_POINT_SPOTS,
    PAINT_SPOTS,
    PLAYCALL_ATTRIBUTE_WEIGHTS, 
    BLOCK_PROBABILITY,
    AGGRESSION_FOUL_MULTIPLIER,
    HARD_SHOOTING_FOUL_THRESHOLD,
    SOFT_SHOOTING_FOUL_THRESHOLD,
    SOFT_PROB
)
from BackEnd.utils.shared import (
    apply_help_defense_if_triggered,
    apply_scoring,
    get_time_elapsed,
    resolve_offensive_rebound,
    get_player_position,
    calculate_screen_score,
    choose_rebounder,
    calculate_rebound_score,
    get_name_safe,
    calculate_gravity_score,
    unpack_game_context,
    calculate_ball_handling_score,
    calculate_defender_pressure_score,
)
from BackEnd.constants.fast_break_constants import DEFENSIVE_STOP_Y_RANGE


class ShotManager:
    def __init__(self, game):
        self.game = game
        self.game_state = game.game_state  # still accessible
        # Add defense score tracking
        self.defense_scores = []
    
    def _calculate_getback_coordinates(self, getback_player, off_team, def_team):
        """
        Calculate get-back player coordinates matching frontend logic.
        
        Args:
            getback_player: Player object getting back
            off_team: Offensive team (shooting team)
            def_team: Defensive team (will be offense on fast break)
        
        Returns:
            dict with "x" and "y" coordinates
        """
        # Determine which team will be on offense for the fast break
        # If home team is shooting, away team is on defense and will be offense on fast break
        # If away team is shooting, home team is on defense and will be offense on fast break
        will_be_home_offense_on_fast_break = def_team.team_id == self.game.home_team.team_id
        
        # Get player IQ attribute
        player_iq = getattr(getback_player, "attributes", {}).get("IQ", 0)
        has_high_iq = player_iq > 50
        
        # Calculate X range based on fast break offense team and IQ
        if will_be_home_offense_on_fast_break:
            # Home team will be offense on fast break (away team is shooting)
            # Offense get-back (becomes defense): 45-60 if home will be offense, 50-60 if IQ > 50
            target_x_min = 50 if has_high_iq else 45
            target_x_max = 60
        else:
            # Away team will be offense on fast break (home team is shooting)
            # Offense get-back (becomes defense): 40-55 if away will be offense, 40-50 if IQ > 50
            target_x_min = 40
            target_x_max = 50 if has_high_iq else 55
        
        # Y range is always 14-36
        target_y_min = 14
        target_y_max = 36
        
        # Randomize within ranges
        target_x = random.randint(target_x_min, target_x_max)
        target_y = random.randint(target_y_min, target_y_max)
        
        return {"x": target_x, "y": target_y}
    
    def _calculate_release_coordinates(self, release_player, off_team, def_team):
        """
        Calculate defensive release player coordinates matching frontend logic.
        
        Args:
            release_player: Player object releasing for fast break
            off_team: Offensive team (shooting team)
            def_team: Defensive team (will be offense on fast break)
        
        Returns:
            dict with "x" and "y" coordinates
        """
        # Determine which team will be on offense for the fast break
        # The defensive team (def_team) will be offense on fast break
        will_be_home_offense_on_fast_break = def_team.team_id == self.game.home_team.team_id
        
        # Get player IQ attribute
        player_iq = getattr(release_player, "attributes", {}).get("IQ", 0)
        has_high_iq = player_iq > 50
        
        # Calculate X range based on fast break offense team and IQ
        if will_be_home_offense_on_fast_break:
            # Home team will be offense on fast break (away team is shooting)
            # Defense release (becomes offense): 40-55 if home will be offense, 45-55 if IQ > 50
            target_x_min = 45 if has_high_iq else 40
            target_x_max = 55
        else:
            # Away team will be offense on fast break (home team is shooting)
            # Defense release (becomes offense): 45-60 if away will be offense, 50-60 if IQ > 50
            target_x_min = 50 if has_high_iq else 45
            target_x_max = 60
        
        # Calculate Y range based on IQ
        if has_high_iq:
            target_y_min = 20
            target_y_max = 30
        else:
            target_y_min = 14
            target_y_max = 36
        
        # Randomize within ranges
        target_x = random.randint(target_x_min, target_x_max)
        target_y = random.randint(target_y_min, target_y_max)
        
        return {"x": target_x, "y": target_y}
    
    def _get_shooter_position_and_spot(self, shooter, roles):
        """
        Helper method to extract shooter's position and spot from roles.
        Eliminates duplicate lookup logic between is_three_point_shot and is_paint_shot.
        
        Args:
            shooter: The player taking the shot
            roles: The roles dict containing steps/skeleton data
            
        Returns:
            tuple: (shooter_pos, spot) or (None, None) if not found
        """
        # Get the shooter's position
        shooter_pos = None
        for pos, player in self.game.offense_team.lineup.items():
            if player == shooter:
                shooter_pos = pos
                break
        
        if not shooter_pos:
            logging.warning(f"🔍 [SHOT LOCATION] Shooter {get_name_safe(shooter)} not found in lineup")
            return (None, None)
        
        # Find the shooter's spot from the final step (where they shoot)
        steps = roles.get("steps", [])
        if not steps:
            logging.warning(f"🔍 [SHOT LOCATION] No steps in roles")
            return (None, None)
        
        # Check the last step for the shooter's spot
        # ✅ FIX: Only check the FINAL step (last step in list) for the shooter's spot
        # This ensures we get the actual shot location, not an earlier step
        if steps:
            final_step = steps[-1]
            pos_actions = final_step.get("pos_actions", {})
            shooter_action = pos_actions.get(shooter_pos)
            if shooter_action and shooter_action.get("action") == "shoot":
                # MongoDB skeletons use "location", old skeletons use "spot"
                location_key = shooter_action.get("location") or shooter_action.get("spot", "")
                spot = location_key.lower() if location_key else ""
                logging.debug(f"🔍 [SHOT LOCATION] Shooter {get_name_safe(shooter)} (pos: {shooter_pos}) shooting from: '{spot}' (raw: '{location_key}')")
                return (shooter_pos, spot)
            else:
                # Fallback: search all steps in reverse (for backwards compatibility)
                logging.debug(f"🔍 [SHOT LOCATION] No shoot action in final step for {shooter_pos}, searching all steps...")
                for step in reversed(steps):
                    pos_actions = step.get("pos_actions", {})
                    shooter_action = pos_actions.get(shooter_pos)
                    if shooter_action and shooter_action.get("action") == "shoot":
                        location_key = shooter_action.get("location") or shooter_action.get("spot", "")
                        spot = location_key.lower() if location_key else ""
                        logging.debug(f"🔍 [SHOT LOCATION] Found shoot action in earlier step: '{spot}' (raw: '{location_key}')")
                        return (shooter_pos, spot)
        
        logging.debug(f"🔍 [SHOT LOCATION] No shoot action found for {shooter_pos} in any step")
        return (None, None)

    def is_three_point_shot(self, shooter, roles):
        """
        Determine if a shot is a three-pointer based on the shooter's spot.
        
        Args:
            shooter: The player taking the shot
            roles: The roles dict containing steps/skeleton data
            
        Returns:
            bool: True if three-pointer, False if two-pointer
        """
        shooter_pos, spot = self._get_shooter_position_and_spot(shooter, roles)
        if not spot:
            return False
        
        # Check if spot is a three-point spot (case insensitive)
        return spot in THREE_POINT_SPOTS

    def is_paint_shot(self, shooter, roles):
        """
        Determine if a shot is from the paint (PIP) based on the shooter's spot.
        
        Args:
            shooter: The player taking the shot
            roles: The roles dict containing steps/skeleton data
            
        Returns:
            bool: True if paint shot, False otherwise
        """
        shooter_pos, spot = self._get_shooter_position_and_spot(shooter, roles)
        if not spot:
            return False
        
        # Check if spot is a paint spot (case insensitive)
        return spot in PAINT_SPOTS
    
    def _calculate_getback_coordinates(self, getback_player, off_team, def_team):
        """
        Calculate get-back player coordinates matching frontend logic.
        
        Args:
            getback_player: Player object getting back
            off_team: Offensive team (shooting team)
            def_team: Defensive team (will be offense on fast break)
        
        Returns:
            dict with "x" and "y" coordinates
        """
        # Determine which team will be on offense for the fast break
        # If home team is shooting, away team is on defense and will be offense on fast break
        # If away team is shooting, home team is on defense and will be offense on fast break
        will_be_home_offense_on_fast_break = def_team.team_id == self.game.home_team.team_id
        
        # Get player IQ attribute
        player_iq = getattr(getback_player, "attributes", {}).get("IQ", 0)
        has_high_iq = player_iq > 50
        
        # Calculate X range based on fast break offense team and IQ
        if will_be_home_offense_on_fast_break:
            # Home team will be offense on fast break (away team is shooting)
            # Offense get-back (becomes defense): 45-60 if home will be offense, 50-60 if IQ > 50
            target_x_min = 50 if has_high_iq else 45
            target_x_max = 60
        else:
            # Away team will be offense on fast break (home team is shooting)
            # Offense get-back (becomes defense): 40-55 if away will be offense, 40-50 if IQ > 50
            target_x_min = 40
            target_x_max = 50 if has_high_iq else 55
        
        # Y range is always 14-36
        target_y_min = 14
        target_y_max = 36
        
        # Randomize within ranges
        target_x = random.randint(target_x_min, target_x_max)
        target_y = random.randint(target_y_min, target_y_max)
        
        return {"x": target_x, "y": target_y}

    def resolve_shot(self, roles):
        
        game_state, off_team, def_team, off_lineup, def_lineup = unpack_game_context(self.game)
        
        time_elapsed = 0
        events = []
        result = {}

        shooter = roles["shooter"]
        passer = roles.get("passer")  # Can be None if no passer found
        screener = roles.get("screener", "")
        defender = roles.get("defender", "")
        second_defender = roles.get("second_defender")  # Second defender if shooter has two defenders in zone
        
        # Check actual defender assignments at the shot step (not just zone boundaries at turn start)
        # Find the shot step (last step where shooter has "shoot" action)
        steps = roles.get("steps", [])
        shooter_id = getattr(shooter, "player_id", None)
        shot_step_index = None
        
        if steps and shooter_id:
            # Find the last step with a shot action
            for step_idx in range(len(steps) - 1, -1, -1):
                step = steps[step_idx]
                pos_actions = step.get("pos_actions", {})
                shooter_pos = get_player_position(off_lineup, shooter)
                if shooter_pos:
                    shooter_action = pos_actions.get(shooter_pos, {})
                    if shooter_action.get("action") == "shoot":
                        shot_step_index = step_idx
                        break
        
        # Check if shooter has two defenders at the actual shot step
        has_double_team_at_shot = False
        second_defender_id_at_shot = None
        
        if shot_step_index is not None and hasattr(self.game, 'zone_defender_assignments_by_step'):
            assignments_by_step = getattr(self.game, 'zone_defender_assignments_by_step', {})
            shot_step_assignments = assignments_by_step.get(shot_step_index, {})
            
            # Count how many defenders are assigned to the shooter at the shot step
            defenders_on_shooter = [
                def_pos for def_pos, guarded_player_id in shot_step_assignments.items()
                if guarded_player_id == shooter_id
            ]
            
            if len(defenders_on_shooter) >= 2:
                has_double_team_at_shot = True
                # Get the second defender's player_id
                if len(defenders_on_shooter) >= 2:
                    second_def_pos = defenders_on_shooter[1]
                    second_defender_obj = def_lineup.get(second_def_pos)
                    if second_defender_obj:
                        second_defender_id_at_shot = getattr(second_defender_obj, "player_id", None)
        
        # Add second_defender_id to result for frontend announcement (only if actually double-teamed at shot step)
        if has_double_team_at_shot and second_defender_id_at_shot:
            result["second_defender_id"] = second_defender_id_at_shot
            result["has_double_team"] = True

        # Debug: Print shooter information with object ID
        # from BackEnd.constants import DEBUG
        # if DEBUG:
        #     print(f"🎯 SHOT DEBUG: shooter={get_name_safe(shooter)}, shooter_pos={get_player_position(off_lineup, shooter)}, shooter_id={id(shooter)}")
        #     print(f"🎯 SHOT DEBUG: shooter object: {shooter}")

        # ✅ MOTION OFFENSE: Use motion_playcall if available (from Motion shot resolution)
        playcall = roles.get("motion_playcall") or self.game_state["current_playcall"]
        defense_call = self.game_state["defense_playcall"]
        
        # Determine if shot is three-pointer based on shooter's spot
        is_three = self.is_three_point_shot(shooter, roles)
        
        # Determine if shot is from the paint (PIP)
        is_paint = self.is_paint_shot(shooter, roles)
        
        # ✅ BALANCING SYSTEM: Check for balancing override first
        if "balancing_shot_threshold_override" in game_state:
            shot_threshold = game_state["balancing_shot_threshold_override"]
            # Clear override after use (one-time per turn)
            game_state.pop("balancing_shot_threshold_override", None)
        else:
            shot_threshold = off_team.team_attributes["shot_threshold"]
        
        if is_three:
            shot_threshold += 100
        if playcall == "Set":
            playcall = "Attack"

        # Apply variant-based modifier (temporary for this turn only)
        variant_modifier = 0
        skeleton = roles.get("skeleton", {})
        variant = skeleton.get("_variant")
        if variant:
            # Variant modifiers based on defensive effectiveness
            variant_modifiers = {
                "successful": -50,      # Play worked perfectly, easier shot
                "mid_play_change": 0,   # Play adjusted, neutral
                "contested": 25,        # Defense engaged, harder shot
                "broken": 100           # Defense disrupted, very difficult shot
            }
            variant_modifier = variant_modifiers.get(variant, 0)
            shot_threshold += variant_modifier
            # Debug logging removed - was cluttering logs
            # logging.debug(f"🎯 Variant modifier: {variant} → {variant_modifier:+d} (threshold: {shot_threshold})")

        # Get shooter location for debug logs
        shooter_pos, shooter_location = self._get_shooter_position_and_spot(shooter, roles)
        shooter_location_str = shooter_location if shooter_location else "unknown"
        
        # ✅ New: returns shot_score, help defender, and foul info
        shot_score, help_defender, d_foul, foul_player = self.calculate_shot_score(
            shooter, passer, screener, defender, playcall, defense_call, is_three, is_paint, second_defender, shooter_location_str
        )
        
        # ✅ MOTION OFFENSE: Apply attack penalty if applicable
        motion_attack_penalty = roles.get("motion_attack_penalty", 0) or game_state.get("motion_attack_penalty", 0)
        if motion_attack_penalty > 0:
            shot_score -= motion_attack_penalty
            # Clear penalty after use
            game_state.pop("motion_attack_penalty", None)

        made = shot_score >= shot_threshold

        # ✅ SHOOTING FOUL CALIBRATION: If there's a shooting foul, check if it forces a miss
        # Fouls are significant outliers that can force missed shots
        if d_foul:
            from BackEnd.constants import THREE_POINTER_FOUL_MISS_CHANCE, TWO_POINTER_FOUL_MISS_CHANCE
            
            foul_calibration_roll = random.random()
            original_made = made
            if is_three:
                # 3-pointers: 40% chance foul forces a miss
                threshold = THREE_POINTER_FOUL_MISS_CHANCE
                miss_chance_pct = int(THREE_POINTER_FOUL_MISS_CHANCE * 100)
                # logging.warning(f"🔍 [SHOOTING FOUL CALIBRATION] 3-pointer foul check:")
                # logging.warning(f"   Original shot result: {'MADE' if made else 'MISS'}")
                # logging.warning(f"   Calibration roll: {foul_calibration_roll:.3f}")
                # logging.warning(f"   Threshold: < {threshold} ({miss_chance_pct}% chance to force miss)")
                if foul_calibration_roll < threshold:
                    made = False
                    # logging.warning(f"   ✅ Foul forces MISS (roll {foul_calibration_roll:.3f} < {threshold})")
                else:
                    # ✅ BUG FIX: Explicitly preserve original result when calibration doesn't force miss
                    # The original 'made' value is already correct, but we log it for clarity
                    # logging.warning(f"   ➡️  Standard shot result holds (roll {foul_calibration_roll:.3f} >= {threshold}) - Result: {'MADE' if made else 'MISS'}")
                    pass
            else:
                # 2-pointers: 20% chance foul forces a miss
                threshold = TWO_POINTER_FOUL_MISS_CHANCE
                miss_chance_pct = int(TWO_POINTER_FOUL_MISS_CHANCE * 100)
                # logging.warning(f"🔍 [SHOOTING FOUL CALIBRATION] 2-pointer foul check:")
                # logging.warning(f"   Original shot result: {'MADE' if made else 'MISS'}")
                # logging.warning(f"   Calibration roll: {foul_calibration_roll:.3f}")
                logging.warning(f"   Threshold: < {threshold} ({miss_chance_pct}% chance to force miss)")
                if foul_calibration_roll < threshold:
                    made = False
                    logging.warning(f"   ✅ Foul forces MISS (roll {foul_calibration_roll:.3f} < {threshold})")
                else:
                    # ✅ BUG FIX: Explicitly preserve original result when calibration doesn't force miss
                    # The original 'made' value is already correct, but we log it for clarity
                    logging.warning(f"   ➡️  Standard shot result holds (roll {foul_calibration_roll:.3f} >= {threshold}) - Result: {'MADE' if made else 'MISS'}")
            
            if original_made != made:
                logging.warning(f"   📊 Shot result changed: {('MADE' if original_made else 'MISS')} → {('MADE' if made else 'MISS')}")
            else:
                logging.warning(f"   📊 Shot result unchanged: {'MADE' if made else 'MISS'} (calibration did not force change)")

        # Stat tracking (attempts)
        shooter.record_stat("FGA")
        if is_three:
            shooter.record_stat("3PTA")

        # ==================== PLAYER POSITIONING (FOR ALL SHOTS) ====================
        # Players release for fast break / get back on defense when shot is TAKEN,
        # not when it's made/missed. They don't know the outcome yet!
        shooter_pos = get_player_position(off_lineup, shooter)
        
        # Get strategy settings directly as numeric values (0-4)
        # No need for string conversion - we just need the numbers for probability calculations
        offense_reb_value = off_team.strategy_settings.get("rebounding", 2)  # Crash boards vs get back
        defense_fast_breaks_value = def_team.strategy_settings.get("fast_breaks", 2)  # Stay vs release for FB
        
        # Import for debug logging (logging already imported at top of file)
        from BackEnd.utils.shared import get_name_safe
        shooter_name = get_name_safe(shooter)
        
        # Determine defensive players releasing for fast break
        from BackEnd.engine.fast_break_trigger import FastBreakTrigger
        
        defense_releases, defense_release_list, defense_rebounders = FastBreakTrigger.can_trigger_from_dreb(
            defense_tempo_value=defense_fast_breaks_value,  # Note: parameter name kept as defense_tempo_value for backward compatibility
            shooter_pos=shooter_pos,
            def_team_lineup=def_team.lineup
        )
        
        # Get names for debug logging
        release_pos = defense_release_list[0] if defense_release_list else None
        release_player = def_team.lineup.get(release_pos) if release_pos else None
        release_player_name = get_name_safe(release_player) if release_player else "NONE"
        
        # Determine offensive players getting back on defense
        offense_getback_chances = {
            0: {"none": 1.0, "one": 0.0, "two": 0.0},
            1: {"none": 0.5, "one": 0.5, "two": 0.0},
            2: {"none": 0.25, "one": 0.75, "two": 0.0},
            3: {"none": 0.1, "one": 0.8, "two": 0.1},
            4: {"none": 0.0, "one": 0.5, "two": 0.5}
        }
        
        chances = offense_getback_chances[offense_reb_value]
        rand = random.random()
        
        if rand < chances["none"]:
            num_getback = 0
        elif rand < chances["none"] + chances["one"]:
            num_getback = 1
        else:
            num_getback = 2
        
        # Note: 0 get-back defenders with a release player is still a valid Fast Break
        # It's just an easy layup opportunity for the outlet receiver
        # No minimum enforcement needed
        
        offense_getback_list = []
        if num_getback >= 1:
            if shooter_pos != "PG":
                offense_getback_list.append("PG")
            else:
                offense_getback_list.append("SG")
        
        if num_getback >= 2:
            if shooter_pos != "SG" and "SG" not in offense_getback_list:
                offense_getback_list.append("SG")
            else:
                offense_getback_list.append("SF")
        
        offense_rebounders = [pos for pos in off_team.lineup.keys() if pos not in offense_getback_list]
        
        # Get names for debug logging
        getback_player_names = [get_name_safe(off_team.lineup.get(pos)) for pos in offense_getback_list if off_team.lineup.get(pos)]
        getback_names_str = ", ".join(getback_player_names) if getback_player_names else "NONE"
        
        # Debug logging for release player logic with all player/team names
        # Reduced to debug level - was cluttering logs
        # offense_tempo_value = off_team.strategy_settings.get("tempo", 2)
        # logging.debug(f"🏃 RELEASE PLAYER DEBUG - shooter={shooter_name}, offense_team={off_team.name}, defense_team={def_team.name}, offense_tempo={offense_tempo_value}, defense_tempo={defense_tempo_value}, release_player={release_player_name}, getback_players={getback_names_str}, defense_releases={defense_releases}")
        
        # ==================== STAT TRACKING ====================
        # Track release/get back instances for both teams
        # Defense team: Increment release_instances (every shot calculates this)
        if not hasattr(def_team, 'team_stats'):
            def_team.team_stats = {}
        def_team.team_stats['release_instances'] = def_team.team_stats.get('release_instances', 0) + 1
        
        # Offense team: Increment get_back_instances (every shot calculates this)
        if not hasattr(off_team, 'team_stats'):
            off_team.team_stats = {}
        off_team.team_stats['get_back_instances'] = off_team.team_stats.get('get_back_instances', 0) + 1
        
        # Defense team: If actually sending a release player, increment actual_releases
        if defense_release_list:
            def_team.team_stats['actual_releases'] = def_team.team_stats.get('actual_releases', 0) + 1
        # ==================== END STAT TRACKING ====================
        
        # ==================== END PLAYER POSITIONING ====================

        # ------------------------
        # 🎯 Shot is Made
        # ------------------------
        if made:
            # Debug logging for assist tracking
            if passer:
                passer.record_stat("AST")
                # ✅ COMMENTED OUT: Assist logs (cluttering transition debugging)
                # logging.info(f"🎯 ASSIST: {get_name_safe(passer)} credited with AST for assist to {get_name_safe(shooter)} (HCO shot)")
            else:
                # logging.info(f"🎯 ASSIST: No passer found for shooter {get_name_safe(shooter)}, no assist awarded")
                pass  # Debug logging commented out
            stats = ["FGM", "3PTM"] if is_three else ["FGM"]
            points = 3 if is_three else 2
            
            # Debug: Print shooter info right before scoring
            # from BackEnd.constants import DEBUG
            # if DEBUG:
            #     print(f"🎯 PRE-SCORING DEBUG: shooter={get_name_safe(shooter)}, shooter_pos={get_player_position(off_lineup, shooter)}, shooter_id={id(shooter)}")
            #     print(f"🎯 PRE-SCORING DEBUG: shooter object: {shooter}")
            
            apply_scoring(self.game, off_team, shooter, points, stats)
            
            # Track PIP if shot was from the paint
            if is_paint:
                shooter.record_stat("PIP", amount=points)
                # print(f"🎯 PIP DEBUG: Recorded {points} PIP for {get_name_safe(shooter)}")
            
            # print(f"🎯 SCORING DEBUG: Awarded {points} points to {get_name_safe(shooter)} (position: {get_player_position(off_lineup, shooter)})")

            possession_flips = True
            if screener:
                screener.record_stat("SCR_S")

            if d_foul:
                possession_flips = False
                # AND-1 situation
                self.game_state["shooter"] = shooter 
                foul_player.record_stat("F")
                
                # Check if player fouled out (5th foul)
                from BackEnd.engine.phase_resolution import check_and_handle_foul_out
                foul_out_info = check_and_handle_foul_out(foul_player, self.game_state, def_team)
                
                def_team.team_fouls += 1  # Increment team fouls for shooting foul
                self.game_state["foul_team"] = "DEFENSE"
                self.game_state["offensive_state"] = "FREE_THROW"
                self.game_state["free_throws"] = 1
                self.game_state["free_throws_remaining"] = 1
                # ✅ FIX: Set next_play_type for AND-1 situations
                result["next_play_type"] = "FREE_THROW"
                text = f"{get_name_safe(shooter)} makes the shot. {get_name_safe(foul_player)} fouls him! AND-1 opportunity!"
                
                # Add foul out info to result if applicable
                if foul_out_info["fouled_out"]:
                    result["fouled_out"] = True
                    result["foul_out_player"] = {
                        "player_id": foul_out_info["foul_player_id"],
                        "name": foul_out_info["foul_player_name"],
                        "photo": foul_out_info["foul_player_photo"],
                        "team": foul_out_info["foul_player_team"]
                    }
                    result["foul_count"] = foul_out_info["foul_count"]
            else:
                # Check for defensive pressure opportunity (FCP/HCT)
                pressure_type = self.game.turn_manager.determine_defensive_pressure_type()
                # print(f"🏀 MADE SHOT: Setting offensive_state to {pressure_type} (defense team: {self.game.defense_team.name})")
                self.game_state["offensive_state"] = pressure_type
                # Store pressure type for animator to use
                result["next_defensive_setup"] = pressure_type
                # ✅ FIX: Set next_play_type for made shots without fouls
                # After a made shot, possession flips and the other team gets a baseline inbound
                result["next_play_type"] = "BASELINE_INBOUND"
                text = f"{get_name_safe(shooter)} drains a 3!" if is_three else f"{get_name_safe(shooter)} makes the shot."
            
            # Add player positioning data for frontend animation (MAKE shots)
            result["offense_getback"] = [off_team.lineup[pos].player_id for pos in offense_getback_list]
            result["defense_release"] = [def_team.lineup[pos].player_id for pos in defense_release_list]
            result["offense_rebounders"] = [off_team.lineup[pos].player_id for pos in offense_rebounders]
            result["defense_rebounders"] = [def_team.lineup[pos].player_id for pos in defense_rebounders]
            
            # ✅ SS&S: Calculate and store get-back player coordinates (backend as source of truth)
            offense_getback_coords = {}
            for pos in offense_getback_list:
                getback_player = off_team.lineup.get(pos)
                if getback_player:
                    coords = self._calculate_getback_coordinates(getback_player, off_team, def_team)
                    offense_getback_coords[getback_player.player_id] = coords
                    # Update player.coords so fast break logic uses correct starting position
                    getback_player.coords = coords.copy()
            result["offense_getback_coords"] = offense_getback_coords
            
            # ✅ FIX: Update coordinates for non-get-back players (rebounders) to prevent stale coordinates
            # These players should be near the basket they were attacking (where the shot was taken)
            # off_team was on offense during shot, so they were attacking their target basket
            # For home team shooting: attacking away basket (x=10)
            # For away team shooting: attacking home basket (x=90)
            # ✅ CLAMP: Clamp all rebound positions to rim coordinates (x between 10 and 90)
            from BackEnd.constants import AWAY_RIM_COORDS, HOME_RIM_COORDS
            min_x = AWAY_RIM_COORDS["x"]  # 10 (left side)
            max_x = HOME_RIM_COORDS["x"]  # 90 (right side)
            
            is_home_team_shooting = off_team.team_id == self.game.home_team.team_id
            for pos in offense_rebounders:
                rebounder_player = off_team.lineup.get(pos)
                if rebounder_player:
                    # Non-get-back players are near the basket after shot attempt
                    if is_home_team_shooting:
                        # Home team was shooting, so rebounders near away basket (x=10)
                        rebounder_x = random.randint(8, 15)
                    else:
                        # Away team was shooting, so rebounders near home basket (x=90)
                        rebounder_x = random.randint(85, 92)
                    # ✅ CLAMP: Ensure x is between rim coordinates
                    rebounder_x = max(min_x, min(max_x, rebounder_x))
                    rebounder_coords = {"x": rebounder_x, "y": random.randint(20, 30)}
                    rebounder_player.coords = rebounder_coords.copy()
            
            # ✅ SS&S: Calculate and store release player coordinates (backend as source of truth)
            defense_release_coords = {}
            for pos in defense_release_list:
                release_player = def_team.lineup.get(pos)
                if release_player:
                    coords = self._calculate_release_coordinates(release_player, off_team, def_team)
                    defense_release_coords[release_player.player_id] = coords
                    # Update player.coords so fast break logic uses correct starting position
                    release_player.coords = coords.copy()
            result["defense_release_coords"] = defense_release_coords

        # ------------------------
        # ❌ Shot is Missed
        # ------------------------
        else:
            text = f"{get_name_safe(shooter)} misses the {'3' if is_three else 'shot'}."
            if defender:
                defender.record_stat("DEF_S")

            if d_foul:
                # Shooting foul → free throws
                self.game_state["shooter"] = shooter 
                foul_player.record_stat("F")
                
                # Check if player fouled out (5th foul)
                from BackEnd.engine.phase_resolution import check_and_handle_foul_out
                foul_out_info = check_and_handle_foul_out(foul_player, self.game_state, def_team)
                
                def_team.team_fouls += 1  # Increment team fouls for shooting foul
                self.game_state["foul_team"] = "DEFENSE"
                self.game_state["offensive_state"] = "FREE_THROW"
                self.game_state["free_throws"] = 3 if is_three else 2
                self.game_state["free_throws_remaining"] = self.game_state["free_throws"]
                text = f"{get_name_safe(foul_player)} fouls {get_name_safe(shooter)} on the shot."
                possession_flips = False
                
                # Add foul out info to result if applicable
                if foul_out_info["fouled_out"]:
                    result["fouled_out"] = True
                    result["foul_out_player"] = {
                        "player_id": foul_out_info["foul_player_id"],
                        "name": foul_out_info["foul_player_name"],
                        "photo": foul_out_info["foul_player_photo"],
                        "team": foul_out_info["foul_player_team"]
                    }
                    result["foul_count"] = foul_out_info["foul_count"]
                    
                    # ✅ FOUL OUT: Store foul context for timeout creation
                    self.game_state["foul_out_context"] = {
                        "foul_type": "DEFENSIVE",
                        "is_shooting_foul": True,
                        "is_bonus": False,  # Shooting fouls are always free throws regardless of bonus
                        "next_play_type": "FREE_THROW",
                        "shooter": shooter  # Store shooter for free throw resume
                    }
                    logging.info(f"✅ FOUL OUT: Stored shooting foul context (miss) - shooter={get_name_safe(shooter)}")
                
                # ✅ Add player positioning data for frontend animation (defensive foul on miss)
                # Players still released/got back when shot was taken, so include this data
                result["offense_getback"] = [off_team.lineup[pos].player_id for pos in offense_getback_list]
                result["defense_release"] = [def_team.lineup[pos].player_id for pos in defense_release_list]
                result["offense_rebounders"] = [off_team.lineup[pos].player_id for pos in offense_rebounders]
                result["defense_rebounders"] = [def_team.lineup[pos].player_id for pos in defense_rebounders]
                
                # ✅ SS&S: Calculate and store get-back player coordinates (backend as source of truth)
                offense_getback_coords = {}
                for pos in offense_getback_list:
                    getback_player = off_team.lineup.get(pos)
                    if getback_player:
                        coords = self._calculate_getback_coordinates(getback_player, off_team, def_team)
                        offense_getback_coords[getback_player.player_id] = coords
                        # Update player.coords so fast break logic uses correct starting position
                        getback_player.coords = coords.copy()
                result["offense_getback_coords"] = offense_getback_coords
                
                # ✅ FIX: Update coordinates for non-get-back players (rebounders) to prevent stale coordinates
                # These players should be near the basket they were attacking (where the shot was taken)
                # off_team was on offense during shot, so they were attacking their target basket
                # For home team shooting: attacking away basket (x=10)
                # For away team shooting: attacking home basket (x=90)
                is_home_team_shooting = off_team.team_id == self.game.home_team.team_id
                for pos in offense_rebounders:
                    rebounder_player = off_team.lineup.get(pos)
                    if rebounder_player:
                        # Non-get-back players are near the basket after shot attempt
                        if is_home_team_shooting:
                            # Home team was shooting, so rebounders near away basket (x=10)
                            rebounder_coords = {"x": random.randint(8, 15), "y": random.randint(20, 30)}
                        else:
                            # Away team was shooting, so rebounders near home basket (x=90)
                            rebounder_coords = {"x": random.randint(85, 92), "y": random.randint(20, 30)}
                        rebounder_player.coords = rebounder_coords.copy()
                
                # ✅ SS&S: Calculate and store release player coordinates (backend as source of truth)
                defense_release_coords = {}
                for pos in defense_release_list:
                    release_player = def_team.lineup.get(pos)
                    if release_player:
                        coords = self._calculate_release_coordinates(release_player, off_team, def_team)
                        defense_release_coords[release_player.player_id] = coords
                        # Update player.coords so fast break logic uses correct starting position
                        release_player.coords = coords.copy()
                result["defense_release_coords"] = defense_release_coords
            else:
                # Regular miss → rebound logic
                defense_attrs = defender.attributes if defender else {"ID": 0}
                base_block_prob = BLOCK_PROBABILITY.get(playcall, 0.0)
                block_skill = defense_attrs["ID"] / 100
                final_block_chance = base_block_prob * (0.5 + block_skill)
                is_block = random.random() < final_block_chance
                if is_block:
                    text += f" {get_name_safe(defender)} blocks the shot! Great block!"
                    defender.record_stat("BLK")

                # ==================== NEW REBOUND SYSTEM ====================
                # Step 1: Player positioning already calculated above (lines 177-233)
                # Using offense_rebounders, defense_rebounders, offense_getback_list, defense_release_list
                
                # Step 2: Calculate base def_prob with player advantage
                def_prob = 0.7
                player_advantage = len(defense_rebounders) - len(offense_rebounders)
                def_prob += (player_advantage * 0.05)
                
                # Step 3: Calculate rebound scores for ALL players attempting rebound
                o_scores = {}
                for pos in offense_rebounders:
                    player = off_team.lineup[pos]
                    if player is None:
                        raise ValueError(f"Offensive player at position {pos} is None in lineup: {off_team.lineup}")
                    o_scores[pos] = calculate_rebound_score(player)
                
                d_scores = {}
                for pos in defense_rebounders:
                    player = def_team.lineup[pos]
                    if player is None:
                        raise ValueError(f"Defensive player at position {pos} is None in lineup: {def_team.lineup}")
                    d_scores[pos] = calculate_rebound_score(player)
                
                # Handle edge cases (all players released/got back)
                if not o_scores:
                    # All offensive players got back - automatic DREB
                    d_pos = max(d_scores, key=d_scores.get) if d_scores else "C"
                    d_rebounder = def_team.lineup[d_pos]
                    stat = "DREB"
                    rebound_team = def_team
                    rebounder = d_rebounder
                elif not d_scores:
                    # All defensive players released - automatic OREB
                    o_pos = max(o_scores, key=o_scores.get) if o_scores else "C"
                    o_rebounder = off_team.lineup[o_pos]
                    stat = "OREB"
                    rebound_team = off_team
                    rebounder = o_rebounder
                else:
                    # Normal rebound selection: pick best rebounder from each side, then use weighted random
                    o_best_pos = max(o_scores, key=o_scores.get) if o_scores else None
                    d_best_pos = max(d_scores, key=d_scores.get) if d_scores else None
                    
                    if o_best_pos is None or d_best_pos is None:
                        raise ValueError("Missing rebounders: o_best_pos={}, d_best_pos={}".format(o_best_pos, d_best_pos))
                    
                    o_rebounder = off_team.lineup[o_best_pos]
                    d_rebounder = def_team.lineup[d_best_pos]
                    
                    if o_rebounder is None or d_rebounder is None:
                        raise ValueError("Rebounder is None: o_rebounder={}, d_rebounder={}".format(o_rebounder, d_rebounder))
                    
                    # Get rebound scores for best rebounders
                    o_rebounder_score = o_scores[o_best_pos]
                    d_rebounder_score = d_scores[d_best_pos]
                    
                    # Apply team bias
                    off_mod = off_team.team_attributes["rebound_modifier"]
                    def_mod = def_team.team_attributes["rebound_modifier"]
                    bias = def_mod - off_mod
                    new_prob = min(0.95, max(0.35, def_prob + bias))
                    
                    # Calculate final weights
                    total_score = d_rebounder_score + o_rebounder_score
                    d_weight = (d_rebounder_score / total_score) if total_score > 0 else 0.5
                    d_weight += (new_prob - 0.5)
                    d_weight = min(0.95, max(0.05, d_weight))
                    
                    # Zone defense penalty
                    defense_call = game_state.get("defense_call", "Man")
                    if defense_call == "Zone":
                        d_weight *= 0.9
                    
                    # Weighted random selection
                    o_weight = 1 - d_weight
                    rebound_team = def_team if random.random() < d_weight else off_team
                    rebounder = d_rebounder if rebound_team == def_team else o_rebounder
                    stat = "DREB" if rebound_team == def_team else "OREB"
                
                # Record rebound stat and update game state
                self.game_state["last_rebound"] = stat
                rebounder.record_stat(stat)
                # Debug: Log when initial rebound stat is recorded
                # ✅ COMMENTED OUT: Initial rebound log (cluttering transition debugging)
                # logging.info(f"🏀 Initial Rebound: {get_name_safe(rebounder)} credited with {stat} (initial shot miss)")
                text += f"...{get_name_safe(rebounder)} grabs the rebound."
                result["rebounderId"] = getattr(rebounder, "player_id", None)
                result["rebound_type"] = stat
                
                # Add player positioning data for frontend animation (already added at top for MAKE shots)
                result["offense_getback"] = [off_team.lineup[pos].player_id for pos in offense_getback_list]
                result["defense_release"] = [def_team.lineup[pos].player_id for pos in defense_release_list]
                result["offense_rebounders"] = [off_team.lineup[pos].player_id for pos in offense_rebounders]
                result["defense_rebounders"] = [def_team.lineup[pos].player_id for pos in defense_rebounders]
                
                # ✅ SS&S: Calculate and store get-back player coordinates (backend as source of truth)
                offense_getback_coords = {}
                for pos in offense_getback_list:
                    getback_player = off_team.lineup.get(pos)
                    if getback_player:
                        coords = self._calculate_getback_coordinates(getback_player, off_team, def_team)
                        offense_getback_coords[getback_player.player_id] = coords
                        # Update player.coords so fast break logic uses correct starting position
                        getback_player.coords = coords.copy()
                result["offense_getback_coords"] = offense_getback_coords
                
                # ✅ SS&S: Calculate and store release player coordinates (backend as source of truth)
                defense_release_coords = {}
                for pos in defense_release_list:
                    release_player = def_team.lineup.get(pos)
                    if release_player:
                        coords = self._calculate_release_coordinates(release_player, off_team, def_team)
                        defense_release_coords[release_player.player_id] = coords
                        # Update player.coords so fast break logic uses correct starting position
                        release_player.coords = coords.copy()
                result["defense_release_coords"] = defense_release_coords
                
                # ✅ FIX: Update coordinates for non-get-back players (rebounders) to prevent stale coordinates
                # These players should be near the basket they were attacking (where the shot was taken)
                # off_team was on offense during shot, so they were attacking their target basket
                # For home team shooting: attacking away basket (x=10)
                # For away team shooting: attacking home basket (x=90)
                is_home_team_shooting = off_team.team_id == self.game.home_team.team_id
                for pos in offense_rebounders:
                    rebounder_player = off_team.lineup.get(pos)
                    if rebounder_player:
                        # Non-get-back players are near the basket after shot attempt
                        if is_home_team_shooting:
                            # Home team was shooting, so rebounders near away basket (x=10)
                            rebounder_coords = {"x": random.randint(8, 15), "y": random.randint(20, 30)}
                        else:
                            # Away team was shooting, so rebounders near home basket (x=90)
                            rebounder_coords = {"x": random.randint(85, 92), "y": random.randint(20, 30)}
                        rebounder_player.coords = rebounder_coords.copy()
                
                # Debug log to verify offense_getback is populated
                # print(f"🔍 [BACKEND GET BACK DEBUG] MISS shot - offense_getback populated:", {
                #     "offense_getback_positions": offense_getback_list,
                #     "offense_getback_player_ids": result["offense_getback"],
                #     "count": len(result["offense_getback"]),
                #     "shooter_pos": shooter_pos,
                #     "offense_reb_value": offense_reb_value,
                #     "note": "This should match frontend logs"
                # })
                
                # ==================== OLD REBOUND SYSTEM (COMMENTED OUT) ====================
                # rebounder_dict = {
                #     "offense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3},
                #     "defense": {"PG": 0.1, "SG": 0.1, "SF": 0.2, "PF": 0.3, "C": 0.3}
                # }
                # o_pos = choose_rebounder(rebounder_dict, "offense")
                # d_pos = choose_rebounder(rebounder_dict, "defense")
                # o_rebounder = off_team.lineup[o_pos]
                # d_rebounder = def_team.lineup[d_pos]
                # o_score = calculate_rebound_score(o_rebounder)
                # d_score = calculate_rebound_score(d_rebounder)
                # off_mod = off_team.team_attributes["rebound_modifier"]
                # def_mod = def_team.team_attributes["rebound_modifier"]
                # bias = def_mod - off_mod
                # def_prob = min(0.95, max(0.55, 0.75 + bias))
                # total_score = d_score + o_score
                # d_weight = (d_score / total_score) if total_score else 0.5
                # d_weight += (def_prob - 0.5)
                # d_weight = min(0.95, max(0.05, d_weight))
                # if defense_call == "Zone":
                #     d_weight *= 0.9
                # o_weight = 1 - d_weight
                # rebound_team = def_team if random.random() < d_weight else off_team
                # rebounder = d_rebounder if rebound_team == def_team else o_rebounder
                # stat = "DREB" if rebound_team == def_team else "OREB"
                # self.game_state["last_rebound"] = stat
                # rebounder.record_stat(stat)
                # text += f"...{get_name_safe(rebounder)} grabs the rebound."
                # result["rebounderId"] = getattr(rebounder, "player_id", None)
                # result["rebound_type"] = stat
                # ==================== END OLD REBOUND SYSTEM ====================
                
                if stat == "OREB":
                    possession_flips = False
                    # Store OREB info for game_manager to create a separate OREB turn
                    self.game_state["pending_oreb"] = {
                        "rebounder": rebounder,
                        "rebounder_id": getattr(rebounder, "player_id", None),
                    }
                    # OREB will be handled as a separate turn
                    # Don't process putback here - let next turn handle it
                else:
                    # DREB - determine next play type
                    possession_flips = True
                    events.append({
                        "event_type": "defReb",
                        "rebounderId": getattr(rebounder, "player_id", None),
                    })
                    self.game.turn_manager.logger.log("defReb")
                    self.game_state["last_rebounder"] = rebounder
                    
                    # NEW FAST BREAK LOGIC:
                    # Fast Break is determined DURING the shot (by defense tempo), not after DREB
                    # If a defender released for fast break during shot → auto-trigger fast break
                    # If no defender released → regular HCO
                    next_play_type = "FAST_BREAK" if defense_release_list else "HCO"
                    if defense_release_list:
                        # next_play_type = "FAST_BREAK"
                        # Log fast break determination with release player info
                        release_player_ids = [def_team.lineup[pos].player_id for pos in defense_release_list]
                        # ✅ Store release player in game_state for use in resolve_fast_break_logic
                        # The outlet pass should go to the release player, not a randomly chosen ball handler
                        release_pos = defense_release_list[0]  # Get first release position (usually only one)
                        release_player = def_team.lineup.get(release_pos)
                        if release_player:
                            self.game_state["last_release_player"] = release_player
                            # ✅ COMMENTED OUT: Fast break debug logs (cluttering transition debugging)
                            # logging.info(f"🏀 FAST_BREAK determined during shot: defense_release_list={defense_release_list}, release_player_ids={release_player_ids}, release_player_stored={getattr(release_player, 'player_id', None)}, shooter={get_name_safe(shooter)}")
                        else:
                            # logging.warning(f"⚠️ FAST_BREAK determined but release_player not found at position {release_pos}")
                            pass  # Debug logging commented out
                    else:
                        next_play_type = "HCO"
                        # Clear release player if not doing fast break
                        self.game_state["last_release_player"] = None
                        # logging.info(f"🏀 HCO determined during shot: no defense_release_list, shooter={get_name_safe(shooter)}")
                    
                    self.game_state["offensive_state"] = next_play_type
                    result["next_play_type"] = next_play_type

        # ⏱️ Add tempo-based time to turn
        # If HCO came after FCP/HCT, adjust time based on pressure phase time
        pressure_phase_time = game_state.get("pressure_phase_time", 0)
        
        if pressure_phase_time > 0:
            # Adjust HCO time: random.randint(15 - pressure_phase_time, min(35, 35 - pressure_phase_time))
            min_time = max(1, 15 - pressure_phase_time)  # Ensure min_time doesn't go below 1
            max_time = min(35, 35 - pressure_phase_time)
            hco_time = random.randint(min_time, max_time)
            time_elapsed += hco_time + pressure_phase_time  # Total = FCP/HCT time + HCO time
            # Clear pressure_phase_time after use
            game_state["pressure_phase_time"] = 0
        else:
            # Normal HCO without pressure phase
            tempo = off_team.strategy_calls["tempo_call"]
            time_elapsed += get_time_elapsed(tempo)

        shooter_pos = get_player_position(off_lineup, shooter)
        
        # Get intended shooter (from successful variant) for audible/hot read popup
        intended_shooter_pos = roles.get("intended_shooter_pos")
        intended_shooter = off_lineup.get(intended_shooter_pos) if intended_shooter_pos else None
        intended_shooter_id = intended_shooter.player_id if intended_shooter else None

        result.update({
            "result_type": "MAKE" if made else "MISS",
            "ball_handler": shooter,
            "shooter": shooter,
            "shooter_id": shooter.player_id,
            "shooter_pos": shooter_pos,
            "intended_shooter_pos": intended_shooter_pos,  # For audible/hot read popup
            "intended_shooter_id": intended_shooter_id,    # For playcall HUD headshot
            "screener": screener,
            "passer": passer,
            "defender": defender,
            "text": text,
            "possession_flips": possession_flips,
            "time_elapsed": time_elapsed,
            "events": events,
            "foul_player_id": getattr(foul_player, "player_id", None) if d_foul and foul_player else None,
            "foul_team": self.game_state.get("foul_team") if d_foul else None,
        })

        if made:
            result["points"] = points
            result["scoring_team"] = off_team.name
            # next_defensive_setup is already in result from line 95
            
            # For AND-1 situations, include free throw info so frontend knows not to inbound
            if d_foul and self.game_state.get("free_throws_remaining", 0) > 0:
                result["free_throws_remaining"] = self.game_state["free_throws_remaining"]
                result["has_and_one"] = True

        return result

    
    def calculate_shot_score(self, shooter, passer, screener, defender, playcall, defense_call, is_three, is_paint=False, second_defender=None, shooter_location=None):
        """
        Calculate shot score based on attributes, playcall, defense, gravity, etc.
        Also returns:
            - help_defender: if one triggered
            - d_foul: whether a defensive foul occurred
            - foul_player: who committed the foul
        """

        shot_score = 0
        attrs = shooter.attributes
        weights = PLAYCALL_ATTRIBUTE_WEIGHTS.get(playcall, {})

        # Base shot score based on shooter attributes and playcall weights
        shot_score += sum(attrs[attr] * (weight / 10) for attr, weight in weights.items()) * random.randint(1, 6)

        # Passing or dribbling bonus
        if passer:
            passer_attrs = passer.attributes
            passer_score = (passer_attrs["PS"] * 0.8 + passer_attrs["IQ"] * 0.2) * random.randint(1, 6)
            shot_score += passer_score * 0.2
        else:
            dribble_score = (attrs["AG"] * 0.8 + attrs["IQ"] * 0.2) * random.randint(1, 6)
            shot_score += dribble_score * 0.2

        # Defensive impact - varies by shot type
        # Calculate defense score for primary defender
        defense_attrs = defender.attributes if defender else {"OD": 0, "ID": 0, "AG": 0, "ST": 0, "IQ": 0, "CH": 0}
        
        if is_paint:
            # Paint shots: ID-focused defense
            defense_score = (
                defense_attrs["ID"] * 0.6 +
                defense_attrs["ST"] * 0.2 +
                defense_attrs["IQ"] * 0.1 +
                defense_attrs["CH"] * 0.1
            ) * random.randint(1, 6)
        elif is_three:
            # Three-point shots: OD-focused defense
            defense_score = (
                defense_attrs["OD"] * 0.8 +
                defense_attrs["IQ"] * 0.1 +
                defense_attrs["CH"] * 0.1
            ) * random.randint(1, 6)
        else:
            # Mid-range shots: balanced defense
            defense_score = (
                defense_attrs["OD"] * 0.3 +
                defense_attrs["ID"] * 0.3 +
                defense_attrs["AG"] * 0.1 +
                defense_attrs["ST"] * 0.1 +
                defense_attrs["IQ"] * 0.1 +
                defense_attrs["CH"] * 0.1
            ) * random.randint(1, 6)
        
        # Track defense score for statistics
        self.defense_scores.append(defense_score)

        d_foul, foul_player = self.check_defensive_foul_on_shot(defender, defense_score, is_three, shooter, shooter_location)

        # Apply primary defender's defense score
        if second_defender:
            # Two defenders: apply both with 30% discount (0.2 * 0.7 = 0.14 each)
            shot_score -= defense_score * 0.14
            
            # Calculate defense score for second defender
            second_defense_attrs = second_defender.attributes if second_defender else {"OD": 0, "ID": 0, "AG": 0, "ST": 0, "IQ": 0, "CH": 0}
            
            if is_paint:
                second_defense_score = (
                    second_defense_attrs["ID"] * 0.6 +
                    second_defense_attrs["ST"] * 0.2 +
                    second_defense_attrs["IQ"] * 0.1 +
                    second_defense_attrs["CH"] * 0.1
                ) * random.randint(1, 6)
            elif is_three:
                second_defense_score = (
                    second_defense_attrs["OD"] * 0.8 +
                    second_defense_attrs["IQ"] * 0.1 +
                    second_defense_attrs["CH"] * 0.1
                ) * random.randint(1, 6)
            else:
                second_defense_score = (
                    second_defense_attrs["OD"] * 0.3 +
                    second_defense_attrs["ID"] * 0.3 +
                    second_defense_attrs["AG"] * 0.1 +
                    second_defense_attrs["ST"] * 0.1 +
                    second_defense_attrs["IQ"] * 0.1 +
                    second_defense_attrs["CH"] * 0.1
                ) * random.randint(1, 6)
            
            # Track second defender's defense score
            self.defense_scores.append(second_defense_score)
            
            # Apply second defender's defense score with 30% discount
            shot_score -= second_defense_score * 0.14
            
            # Record defensive attempts for both defenders
            if second_defender:
                second_defender.record_stat("DEF_A")
        else:
            # Single defender: apply normal 20% impact
            shot_score -= defense_score * 0.2
        
        if defender:
            defender.record_stat("DEF_A")

        # Defense scheme multiplier
        if (defense_call == "Zone" and is_three) or (defense_call == "Man" and not is_three):
            shot_score *= 0.9
        else:
            shot_score *= 1.1

        # Help defense
        help_defender = None
        if defender:
            shot_score, help_defender, help_penalty = apply_help_defense_if_triggered(
                self.game, playcall, is_three, defender, shot_score
            )

        # Screener bonus
        if screener and screener != shooter:
            screen_attrs = screener.attributes
            screen_score = calculate_screen_score(screen_attrs)
            shot_score += screen_score * 0.15
            screener.record_stat("SCR_A")

        # Gravity contribution from off-ball players
        off_lineup = self.game.offense_team.lineup
        shooter_pos = get_player_position(off_lineup, shooter)
        passer_pos = get_player_position(off_lineup, passer) if passer else None
        screener_pos = get_player_position(off_lineup, screener) if screener else None

        gravity_contributors = [
            pos for pos in off_lineup
            if pos not in [shooter_pos, passer_pos, screener_pos]
        ]

        total_gravity = sum(
            calculate_gravity_score(off_lineup[pos].attributes)
            for pos in gravity_contributors
        )

        gravity_boost = total_gravity * 0.02
        shot_score += gravity_boost

        # print(f"Off-ball gravity boost: +{round(gravity_boost, 2)} from {gravity_contributors}")
        # print(f"offense call: {playcall} // defense call: {defense_call}")
        # print(f"shooter: {get_name_safe(shooter)} | passer: {get_name_safe(passer)}")
        # print(f"shot score = {round(shot_score, 2)} | (defense penalty: {round(defense_score * 0.2, 2)})")

        return shot_score, help_defender, d_foul, foul_player

    
    def check_defensive_foul_on_shot(self, defender, defense_score, is_three=False, shooter=None, shooter_location=None):
        """
        Determines if a defensive foul occurs based on defender skill and team fight.
        Uses hard and soft thresholds with universal constants.
        Returns (bool, player) → (was_foul_committed, fouling_defender)
        """
        if not defender:
            return False, None

        defense_team = self.game.defense_team
        fight = defense_team.team_attributes.get("fight", 0)

        # Calculate thresholds with fight adjustment
        hard_threshold = HARD_SHOOTING_FOUL_THRESHOLD + fight
        soft_threshold = SOFT_SHOOTING_FOUL_THRESHOLD + fight

        # 🔍 DEBUG: Shooting Foul Calculation
        from BackEnd.utils.shared import get_name_safe
        logging.debug(f"🔍 [SHOOTING FOUL] Calculation:")
        shooter_name = get_name_safe(shooter) if shooter else "Unknown"
        shooter_loc_str = shooter_location if shooter_location else "unknown"
        logging.debug(f"   Shooter: {shooter_name}")
        logging.debug(f"   Shooter location: {shooter_loc_str}")
        logging.debug(f"   Defender: {get_name_safe(defender)}")
        logging.debug(f"   Defense score: {defense_score}")
        logging.debug(f"   Is 3-pointer: {is_three}")
        logging.debug(f"   Defense team fight: {fight}")
        logging.debug(f"   Base HARD threshold: {HARD_SHOOTING_FOUL_THRESHOLD}")
        logging.debug(f"   Base SOFT threshold: {SOFT_SHOOTING_FOUL_THRESHOLD}")
        logging.debug(f"   Calibrated HARD threshold: {HARD_SHOOTING_FOUL_THRESHOLD} + {fight} = {hard_threshold}")
        logging.debug(f"   Calibrated SOFT threshold: {SOFT_SHOOTING_FOUL_THRESHOLD} + {fight} = {soft_threshold}")

        # Determine if foul occurs
        if defense_score < hard_threshold:
            d_foul = True
            logging.warning(f"   ✅ RESULT: HARD FOUL (defense_score {defense_score} < hard_threshold {hard_threshold})")
        elif defense_score < soft_threshold:
            # Soft foul: random chance based on SOFT_PROB
            soft_roll = random.random()
            d_foul = soft_roll < SOFT_PROB
            # logging.warning(f"   Soft foul check: defense_score {defense_score} < soft_threshold {soft_threshold}")
            # logging.warning(f"   Soft roll: {soft_roll:.3f} < SOFT_PROB {SOFT_PROB} = {d_foul}")
            if d_foul:
                # logging.warning(f"   ✅ RESULT: SOFT FOUL (roll {soft_roll:.3f} < {SOFT_PROB})")
                pass
            else:
                # logging.warning(f"   ➡️  No foul (roll {soft_roll:.3f} >= {SOFT_PROB})")
                pass
        else:
            d_foul = False
            # logging.warning(f"   ➡️  No foul (defense_score {defense_score} >= soft_threshold {soft_threshold})")
            pass
        
        return d_foul, defender if d_foul else None


    def resolve_fast_break_shot(self, fb_roles):
        off_team = self.game.offense_team
        def_team = self.game.defense_team
        off_lineup = off_team.lineup
        def_lineup = def_team.lineup
        result = {}
        
        shooter = fb_roles["shooter"]
        passer = fb_roles.get("passer", "")
        if shooter == passer:
            passer = None
        
        attrs = shooter.attributes
        
        # ✅ RECALIBRATE DEFENDER COUNT: After outlet pass is received, only count defenders ahead of ball handler
        # Get ball handler outlet position (after receiving outlet pass)
        ball_handler = fb_roles.get("ball_handler", shooter)  # Ball handler is typically the outlet receiver
        ball_handler_outlet_x = fb_roles.get("ball_handler_outlet_x")
        ball_handler_outlet_y = fb_roles.get("ball_handler_outlet_y")
        
        # Determine if away offense or home offense (for x-coord comparison)
        is_away_offense = off_team.team_id == self.game.away_team.team_id
        
        # Filter defenders to only those ahead of ball handler (via x-coords check)
        # Also check for defensive stop challenges (±6 y-coords and ahead)
        valid_defenders = []
        defense_call = self.game_state.get("defense_playcall", "Man")
        
        if ball_handler_outlet_x is not None and ball_handler_outlet_y is not None:
            for defender in fb_roles.get("defense", []):
                # Get defender outlet position (stored in defender.outlet_coords)
                defender_outlet_coords = getattr(defender, "outlet_coords", {})
                defender_outlet_x = defender_outlet_coords.get("x")
                defender_outlet_y = defender_outlet_coords.get("y")
                
                # Fallback to current coords if outlet_coords not available
                if defender_outlet_x is None or defender_outlet_y is None:
                    defender_coords = getattr(defender, "coords", {})
                    defender_outlet_x = defender_coords.get("x", 50)
                    defender_outlet_y = defender_coords.get("y", 25)
                
                # Check if defender is ahead of ball handler (x-coords check)
                if is_away_offense:
                    # Away offense: basket at x=10 in HOME orientation, smaller x is closer
                    # Defender ahead if defender_x <= ball_handler_x
                    is_ahead = defender_outlet_x <= ball_handler_outlet_x
                else:
                    # Home offense: basket at x=90 in HOME orientation, larger x is closer
                    # Defender ahead if defender_x >= ball_handler_x
                    is_ahead = defender_outlet_x >= ball_handler_outlet_x
                
                if not is_ahead:
                    # Defender is not ahead, skip them
                    continue
                
                # Check if defender is within ±6 y-coords (defensive stop position)
                y_diff = abs(defender_outlet_y - ball_handler_outlet_y)
                is_within_y_range = y_diff <= DEFENSIVE_STOP_Y_RANGE
                
                if is_within_y_range:
                    # Defender is in position to attempt defensive stop - run challenge
                    defender_score = calculate_defender_pressure_score(defender, defense_call)
                    offender_score = calculate_ball_handling_score(ball_handler)
                    
                    # If offender wins (offender_score > defender_score), they pass the defender
                    # Remove defender from count (they won't defend the shot)
                    if offender_score > defender_score:
                        # Offender wins - defender is passed, don't include in count
                        logging.debug(f"🏀 [FAST BREAK CHALLENGE] {get_name_safe(ball_handler)} (BH={offender_score}) beats {get_name_safe(defender)} (Pressure={defender_score}) - defender passed, continuing to shot")
                        continue
                    else:
                        # Defender wins - this should have been a defensive stop
                        # If we're here, it means we're in shot resolution, so log warning but include them
                        # (This shouldn't happen if phase_resolution.py logic is correct)
                        logging.warning(f"⚠️ [FAST BREAK CHALLENGE] {get_name_safe(defender)} (Pressure={defender_score}) should have stopped {get_name_safe(ball_handler)} (BH={offender_score}) but reached shot resolution - including in count")
                
                # Defender is ahead and either not in stop position or lost challenge - include in count
                valid_defenders.append(defender)
        else:
            # Fallback: use original defender list if outlet positions not available
            valid_defenders = fb_roles.get("defense", [])
            logging.warning(f"⚠️ [FAST BREAK] Ball handler outlet position not available, using original defender count")
        
        # Update fb_roles["defense"] with filtered list
        fb_roles["defense"] = valid_defenders
        defender_count = len(valid_defenders)
        
        shot_score = (attrs["SC"] * 0.6 + attrs["AG"] * 0.2 + attrs["IQ"] * 0.2) * random.randint(1, 6)
        text = f"fast break shot_score: {shot_score}"
        
        # ✅ Defender assignment: Respect already-set defender (e.g., from phase_resolution.py)
        # If defender already set (e.g., closest_defender_overall for shot attempts), use it
        if fb_roles.get("defender"):
            defender = fb_roles["defender"]
            # Defender already set, no need to reassign
        else:
            # Defender not set: assign based on defender count (fallback logic)
            if defender_count == 0:
                # 0 defenders: No defender assigned
                defender = None
                fb_roles["defender"] = None
            elif defender_count == 1:
                # 1 defender: Assign the single defender
                defender = fb_roles["defense"][0] if fb_roles["defense"] else None
                fb_roles["defender"] = defender
            else:  # defender_count >= 2
                # 2+ defenders: Randomly select one as primary shot defender
                defender = random.choice(fb_roles["defense"])
                fb_roles["defender"] = defender
                # Store all defenders for animation (other defenders position around basket)
                fb_roles["all_defenders"] = fb_roles["defense"]
        
        # Calculate defense score and apply to shot
        if defender:
            defense_attrs = defender.attributes
            defense_score = (
                defense_attrs.get("ID", 0) * 0.8 +
                defense_attrs.get("IQ", 0) * 0.1 +
                defense_attrs.get("CH", 0) * 0.1
            ) * random.randint(1, 6)
            # Track defense score for statistics (fast break)
            self.defense_scores.append(defense_score)
            shot_score -= (defense_score * 0.2)
            text += f" - defense score: {defense_score}"
            defender.record_stat("DEF_A")
        
        # Adjust shot threshold based on defender count
        shot_threshold = off_team.team_attributes["shot_threshold"]
        
        if defender_count == 0:
            # 0 defenders: 99% make chance (threshold = 1)
            shot_threshold = 1
            # Debug print removed to declutter output
        elif defender_count >= 2:
            # 2+ defenders: +300 shot threshold (much harder shot)
            shot_threshold += 100
            # Debug print removed to declutter output

        made = shot_score >= shot_threshold
        text += f"shot threshold: {off_team.team_attributes['shot_threshold']}"
        shooter.record_stat("FGA")

        if made:
            if passer:
                passer.record_stat("AST")
            points = 2
            # If this fast break was triggered by a steal (no outlet pass), track Points Off Turnovers (POT)
            # and allow for 3-point makes if the shot was from deep (if the flag is present).
            if fb_roles.get("is_steal_entry"):
                pot_points = 3 if fb_roles.get("is_three_point_shot") else points
                shooter.record_stat("POT", amount=pot_points)
            apply_scoring(self.game, off_team, shooter, points, ["FGM"])  # Record FGM
            shooter.record_stat("FB_PTS", amount=points)  # Track fast break points - increment by points scored (2 or 3)
            text += f"{shooter} converts the fast break shot!"
            possession_flips = True
            # Check for defensive pressure opportunity (FCP/HCT) after fast break make
            pressure_type = self.game.turn_manager.determine_defensive_pressure_type()
            self.game_state["offensive_state"] = pressure_type
            result["next_defensive_setup"] = pressure_type
            # ✅ FIX: Set next_play_type for made fast break shots (matches HCO makes pattern)
            # After a made shot, possession flips and the other team gets a baseline inbound
            result["next_play_type"] = "BASELINE_INBOUND"
        else:
            # Fast break shot missed
            if defender:
                defender.record_stat("DEF_S")
            
            if defender_count == 0:
                # 0 defenders: Find closest player to ball (excluding shooter)
                # Ball bounces to a random spot near the basket
                # Determine which basket based on offense team
                is_away_team = off_team.team_id == self.game.away_team.team_id
                
                # Basket coordinates: Home basket x=9, Away basket x=91
                basket_x = 91 if is_away_team else 9
                basket_y = 25
                
                # Ball bounces ±8 y, ±5 x from basket
                bounce_x = basket_x + random.randint(-5, 5)
                bounce_y = basket_y + random.randint(-8, 8)
                
                # Find closest player (excluding shooter)
                shooter_id = getattr(shooter, "player_id", None)
                all_players = list(off_lineup.values()) + list(def_lineup.values())
                closest_player = None
                closest_distance = float("inf")
                
                for player in all_players:
                    player_id = getattr(player, "player_id", None)
                    if player_id == shooter_id:
                        continue  # Skip shooter
                    
                    # Get player's current position (or default position)
                    player_coords = getattr(player, "coords", {"x": 50, "y": 25})
                    player_x = player_coords.get("x", 50)
                    player_y = player_coords.get("y", 25)
                    
                    # Calculate distance to ball bounce spot
                    distance = ((player_x - bounce_x) ** 2 + (player_y - bounce_y) ** 2) ** 0.5
                    
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_player = player
                
                rebounder = closest_player
                
                # Determine if OREB or DREB based on rebounder's team
                rebounder_team_id = getattr(rebounder, "team_id", None)
                is_oreb = rebounder_team_id == off_team.team_id
                
                if is_oreb:
                    # OREB: Use standard OREB system
                    rebounder.record_stat("OREB")
                    text += f"{shooter} misses the layup -- {get_name_safe(rebounder)} grabs the offensive rebound!"
                    result["rebounderId"] = getattr(rebounder, "player_id", None)
                    result["rebound_type"] = "OREB"
                    possession_flips = False
                    # Store OREB info for game_manager to create a separate OREB turn
                    self.game_state["pending_oreb"] = {
                        "rebounder": rebounder,
                        "rebounder_id": getattr(rebounder, "player_id", None),
                    }
                else:
                    # DREB: Transition to HCO with outlet step
                    rebounder.record_stat("DREB")
                    text += f"{shooter} misses the layup -- {get_name_safe(rebounder)} grabs the defensive rebound."
                    result["rebounderId"] = getattr(rebounder, "player_id", None)
                    result["rebound_type"] = "DREB"
                    possession_flips = True
                    text += " -- entering half court."
                    self.game_state["offensive_state"] = "HCO"
                    self.game_state["last_rebounder"] = rebounder
                    self.game_state["last_rebound"] = "DREB"
                    result["next_play_type"] = "HCO"
                
                # Store bounce spot for animation
                result["ball_bounce_x"] = bounce_x
                result["ball_bounce_y"] = bounce_y
            else:
                # 1+ defenders: Defender grabs rebound (original logic)
                rebounder = random.choice(fb_roles["defense"]) if fb_roles["defense"] else self.game.defense_team.lineup["PG"]
                text += f"{shooter} misses the fast break shot -- {get_name_safe(rebounder)} grabs the rebound."
                rebounder.record_stat("DREB")
                result["rebounderId"] = getattr(rebounder, "player_id", None)
                result["rebound_type"] = "DREB"
                possession_flips = True
                # Force HCO after defensive rebound from missed fast break shot
                text += " -- entering half court."
                self.game_state["offensive_state"] = "HCO"
                result["next_play_type"] = "HCO"  # ✅ FIX: Set next_play_type so game_manager can detect DREB→HCO transition
                self.game_state["last_rebounder"] = rebounder
                self.game_state["last_rebound"] = "DREB"

        time_elapsed = random.randint(5, 10)

        shooter_pos = get_player_position(off_lineup, shooter)

        result.update({
            "result_type": "MAKE" if made else "MISS",
            "ball_handler": shooter,
            "shooter": shooter,
            "shot_score": shot_score,
            "screener": None,
            "passer": passer,
            "defender": defender,
            "defenderId": getattr(defender, "player_id", None) if defender else None,
            "text": text,
            "possession_flips": possession_flips,
            "time_elapsed": time_elapsed,
            "defender_count": defender_count,  # For frontend animation logic
            "outlet_passer_id": fb_roles.get("outlet_passer"),  # Outlet passer stays stationary for 0 defenders
        })

        if made:
            result["points"] = points
            result["scoring_team"] = off_team.name

        return result

    def print_defense_score_stats(self):
        """Print defense score statistics for the game."""
        if not self.defense_scores:
            print("No defense scores recorded in this game.")
            return
            
        import statistics
        
        count = len(self.defense_scores)
        avg = statistics.mean(self.defense_scores)
        median = statistics.median(self.defense_scores)
        stdev = statistics.stdev(self.defense_scores) if count > 1 else 0
        
        print("\n" + "="*50)
        print("DEFENSE SCORE STATISTICS")
        print("="*50)
        print(f"Total calculations: {count}")
        print(f"Average: {avg:.2f}")
        print(f"Median: {median:.2f}")
        print(f"Standard Deviation: {stdev:.2f}")
        print(f"1st Standard Deviation Range: {avg - stdev:.2f} to {avg + stdev:.2f}")
        print(f"2nd Standard Deviation Range: {avg - 2*stdev:.2f} to {avg + 2*stdev:.2f}")
        print(f"Min: {min(self.defense_scores):.2f}")
        print(f"Max: {max(self.defense_scores):.2f}")
        print("="*50)
