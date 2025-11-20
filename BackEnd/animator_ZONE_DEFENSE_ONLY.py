# ==================== ZONE DEFENSE CODE - PRESERVE THIS FILE ====================
# This file contains ONLY the zone defense integration code from animator.py
# Download this file and preserve it before reverting to commit fc4573e3
# 
# Original location: BackEnd/models/animator.py
# Contains: _position_zone_defenders method and integration in skeleton_to_animations
# 
# To restore: 
# 1. Copy _position_zone_defenders method into BackEnd/models/animator.py
# 2. Uncomment the zone defense integration block in skeleton_to_animations method
# 
# Note: This file does NOT contain the full Animator class - only zone defense methods

from BackEnd.utils.shared import get_away_player_coords

# ==================== ZONE DEFENSE METHOD ====================

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
            # Get ball handler coords for this step
            bh_coords_list = offensive_positions_by_step.get(ball_handler_pos, [])
            ball_handler_coords = bh_coords_list[step_index] if step_index < len(bh_coords_list) else (
                bh_coords_list[-1] if bh_coords_list else {"x": 50, "y": 25}
            )
            
            # Get ball handler's spot for this step
            if step_index < len(skeleton_steps):
                step = skeleton_steps[step_index]
                bh_action = step.get("pos_actions", {}).get(ball_handler_pos, {})
                current_ball_spot = bh_action.get("location") or bh_action.get("spot") or ball_spot
            else:
                current_ball_spot = ball_spot
            
            # Update zone boundaries if ball spot changed (shift logic)
            # ✅ Zone boundaries should be in SAME orientation as offensive coords
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
                    "is_ball_handler": off_pos == ball_handler_pos,
                    "spot": spot
                })
            
            # Assign defensive coordinates for this defender at this step
            # Use assign_all_zone_defenders which handles overlaps and priorities
            # ✅ Pass is_away_offense as-is - zone functions expect coords in original flipped state
            # They will unflip internally, calculate in home orientation, and return home orientation coords
            defender_coords_dict = assign_all_zone_defenders(
                zone_boundaries,
                offensive_players,
                ball_handler_coords,
                current_ball_spot,
                aggression,
                is_away_offense
            )
            
            def_coords = defender_coords_dict.get(def_pos)
            if not def_coords:
                # Fallback: use center of zone
                zone_coords_list = zone_boundaries.get(def_pos, [])
                if zone_coords_list:
                    # Average of zone coordinates
                    avg_x = sum(c[0] for c in zone_coords_list) / len(zone_coords_list)
                    avg_y = sum(c[1] for c in zone_coords_list) / len(zone_coords_list)
                    def_coords = {"x": int(avg_x), "y": int(avg_y)}
                else:
                    def_coords = {"x": 50, "y": 25}
            
            # ✅ Flip defensive coordinates if away team is on offense
            # When away team has the ball, ALL players (both offense and defense) 
            # are positioned on the away side of the court (left side of screen)
            # This matches how offensive coords are flipped in skeleton_to_animations
            if is_away_offense:
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


# ==================== INTEGRATION CODE FOR skeleton_to_animations ====================
# This block should be uncommented in skeleton_to_animations method around line 867
# 
# elif defense_playcall == "Zone":
#     # Use zone defense positioning (2-3 zone)
#     defensive_anims = self._position_zone_defenders(
#         offensive_animations,
#         def_lineup,
#         steps
#     )
#     animations.extend(defensive_anims)

