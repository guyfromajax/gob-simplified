# ==================== ZONE DEFENSE CODE - PRESERVE THIS FILE ====================
# This file contains ONLY the zone defense strategy call dictionary from constants.py
# Download this file and preserve it before reverting to commit fc4573e3
# 
# Original location: BackEnd/constants.py
# Contains: STRATEGY_CALL_DICTS["defense"] dictionary with zone defense weights
# 
# To restore: 
# Update STRATEGY_CALL_DICTS["defense"] in BackEnd/constants.py with the dictionary below
# 
# Note: This file does NOT contain the full constants.py - only the defense strategy dictionary

# ==================== DEFENSE STRATEGY CALL DICTIONARY ====================
# Location: Around line 75 in constants.py
# Part of STRATEGY_CALL_DICTS dictionary

STRATEGY_CALL_DICTS_DEFENSE_ONLY = {
    "defense": {
        0: ["Man"],
        1: ["Man", "Man", "Zone"],
        2: ["Man", "Zone"],
        3: ["Man", "Zone", "Zone"],
        4: ["Zone"]
    }
}

# Full context (for reference):
# STRATEGY_CALL_DICTS = {
#     "defense": {
#         0: ["Man"],
#         1: ["Man", "Man", "Zone"],
#         2: ["Man", "Zone"],
#         3: ["Man", "Zone", "Zone"],
#         4: ["Zone"]
#     },
#     "tempo": {
#         0: ["slow"],
#         1: ["slow", "normal"],
#         2: ["normal"],
#         3: ["normal", "fast"],
#         4: ["fast"],
#     },
#     "aggression": {
#         0: ["passive"],
#         1: ["passive", "normal"],
#         2: ["normal"],
#         3: ["normal", "aggressive"],
#         4: ["aggressive"],
#     },
# }

