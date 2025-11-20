# ==================== ZONE DEFENSE CODE - PRESERVE THIS FILE ====================
# This file contains ONLY the zone defense integration code from turn_manager.py
# Download this file and preserve it before reverting to commit fc4573e3
# 
# Original location: BackEnd/models/turn_manager.py
# Contains: Zone defense logic in set_playcalls, assign_roles, and calculate_foul_turnover
# 
# To restore:
# 1. Uncomment zone defense sections in set_playcalls() method (around line 608)
# 2. Uncomment zone defense sections in assign_roles() method (around line 1232)
# 3. Uncomment zone defense sections in calculate_foul_turnover() method (around line 1358)
# 
# Note: This file does NOT contain the full TurnManager class - only zone defense sections

import random
import logging
from BackEnd.constants import STRATEGY_CALL_DICTS

# ==================== ZONE DEFENSE IN set_playcalls() METHOD ====================
# Location: Around line 608 in set_playcalls()
# Currently commented out with: # ✅ TEMPORARY: Force MAN defense for all turns

# UNCOMMENTED VERSION (to restore):
# Defense setting - use override if set, otherwise choose normally
# if chosen_defense is None:  # Not set by user override
#     defense_setting = self.game.defense_team.strategy_settings.get("defense", 2)
#     chosen_defense = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])
#     logging.info(f"🛡️ Defense call from strategy_settings: defense={defense_setting}, chosen={chosen_defense}, defense_team={self.game.defense_team.name}")

# CURRENTLY COMMENTED OUT VERSION (for reference):
# ✅ TEMPORARY: Force MAN defense for all turns (zone defense disabled for debugging)
# Defense setting - use override if set, otherwise force MAN
# if chosen_defense is None:  # Not set by user override
#     # defense_setting = self.game.defense_team.strategy_settings.get("defense", 2)
#     # chosen_defense = random.choice(STRATEGY_CALL_DICTS["defense"][defense_setting])
#     # logging.info(f"🛡️ Defense call from strategy_settings: defense={defense_setting}, chosen={chosen_defense}, defense_team={self.game.defense_team.name}")
#     chosen_defense = "Man"  # Force MAN defense for debugging
#     logging.info(f"🛡️ Defense call FORCED to MAN (zone defense disabled for debugging), defense_team={self.game.defense_team.name}")


# ==================== ZONE DEFENSE IN assign_roles() METHOD ====================
# Location: Around line 1232 in assign_roles()
# Currently commented out with: # ✅ TEMPORARY: Zone defense disabled for debugging

# UNCOMMENTED VERSION (to restore):
# if game_state["defense_playcall"] == "Zone":
#     # Use zone defense logic to determine which defender's zone contains the shooter
#     from BackEnd.utils.shared_defense import _get_23_zone_boundaries, _point_in_zone
#     from BackEnd.constants import HCO_STRING_SPOTS
#     
#     # Get shooter's spot from final step (where they shoot)
#     shooter_spot = "key"  # Default
#     if steps:
#         final_step = steps[-1]
#         shooter_action = final_step.get("pos_actions", {}).get(shooter_pos, {})
#         shooter_spot = shooter_action.get("location") or shooter_action.get("spot") or "key"
#     
#     # Get ball handler's spot for zone shift logic (use first step or final step's ball handler)
#     ball_handler_spot = "key"  # Default
#     if steps:
#         first_step = steps[0]
#         # Find ball handler position from first step
#         ball_handler_pos_first = None
#         for pos, action_info in first_step.get("pos_actions", {}).items():
#             if action_info.get("action") in ["handle_ball", "receive"]:
#                 ball_handler_pos_first = pos
#                 break
#         if ball_handler_pos_first:
#             bh_action = first_step.get("pos_actions", {}).get(ball_handler_pos_first, {})
#             ball_handler_spot = bh_action.get("location") or bh_action.get("spot") or "key"
#     
#     # Determine if away team is on offense
#     is_away_offense = off_team.team_id == game.away_team.team_id
#     
#     # Get zone boundaries based on ball handler location (applies shifts)
#     zone_boundaries = _get_23_zone_boundaries(ball_handler_spot, is_away_offense)
#     
#     # Get shooter's coordinates
#     shooter_coords = HCO_STRING_SPOTS.get(shooter_spot, {"x": 50, "y": 25})
#     
#     # Find which defender's zone contains the shooter
#     defenders_in_zone = []
#     for def_pos in ["PG", "SG", "SF", "PF", "C"]:
#         if def_pos not in def_lineup:
#             continue
#         zone_coords = zone_boundaries.get(def_pos, [])
#         if _point_in_zone(shooter_coords, zone_coords, is_away_offense):
#             defenders_in_zone.append(def_pos)
#     
#     if defenders_in_zone:
#         # If shooter is in multiple zones (overlap), pick based on zone logic:
#         # If one defender has the shooter as the only player in their zone, use that defender
#         # Otherwise, prefer defender closest to basket (C, then PF/SF, then PG/SG)
#         if len(defenders_in_zone) == 1:
#             defender_pos = defenders_in_zone[0]
#         else:
#             # Overlap: prefer center, then forwards, then guards (by zone responsibility)
#             priority_order = ["C", "PF", "SF", "PG", "SG"]
#             for pos in priority_order:
#                 if pos in defenders_in_zone:
#                     defender_pos = pos
#                     break
#             else:
#                 # Fallback: use first defender
#                 defender_pos = defenders_in_zone[0]
#     else:
#         # Shooter not in any zone (shouldn't happen, but fallback)
#         logging.warning(f"⚠️ Zone defense: Shooter at {shooter_spot} not in any zone, using random defender")
#         defender_pos = random.choice(list(def_lineup))
# else:
#     # Always use MAN defense (position-to-position matching)
#     defender_pos = shooter_pos

# CURRENTLY COMMENTED OUT VERSION (for reference):
# ✅ TEMPORARY: Zone defense disabled for debugging - always use MAN defense
# if game_state["defense_playcall"] == "Zone":
#     # ... (all the code above is commented out) ...
# # Always use MAN defense (position-to-position matching)
# defender_pos = shooter_pos


# ==================== ZONE DEFENSE IN calculate_foul_turnover() METHOD ====================
# Location: Around line 1358 in calculate_foul_turnover()
# Currently commented out with: # ✅ TEMPORARY: Always use MAN defense

# UNCOMMENTED VERSION (to restore):
# defender = def_lineup.get(def_pos) if defense_call != "Zone" else random.choice(list(def_lineup.values()))
# ...
# if defense_call == "Zone":
#     pressure *= 0.9
# ...
# defender = def_lineup[pos] if defense_call != "Zone" else random.choice(list(def_lineup.values()))

# CURRENTLY COMMENTED OUT VERSION (for reference):
# ✅ TEMPORARY: Always use MAN defense (zone defense disabled for debugging)
# defender = def_lineup.get(def_pos)  # Always MAN defense
# ...
# ✅ TEMPORARY: Zone defense disabled for debugging
# if defense_call == "Zone":
#     pressure *= 0.9
# ...
# ✅ TEMPORARY: Always use MAN defense (zone defense disabled for debugging)
# defender = def_lineup[pos]  # Always MAN defense

