import random
import os

# Debug flag - set DISABLE_DEBUG=1 environment variable to suppress verbose output
# Defaults to True (debug enabled) unless DISABLE_DEBUG is set
DEBUG = os.environ.get("DISABLE_DEBUG", "").lower() not in ["1", "true", "yes"]

ALL_ATTRS = [
    "SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT",  # malleable
    "ND", "IQ", "CH", "EM", "MO"  # static or macro-adjusted
    ]

BOX_SCORE_KEYS = [
    "FGA", "FGM", "3PTA", "3PTM", "FTA", "FTM",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "MIN", "PTS", "PIP", "FB_PTS", "POT",
    "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S",
    # Fast Break stats
    "Outlet_A", "Outlet_S", "Outlet_Score", "Outlet_Score_List", "Outlet_Score_Cum",
    "FB_A", "FB_S",
    "FB_A_D", "FB_S_D", "FB_F_D",
    # FCP/HCT stats
    "HCT_A", "HCT_S", "HCT_A_D", "HCT_S_D",
    "FCP_A", "FCP_S", "FCP_A_D", "FCP_S_D"
]


PLAYCALL_ATTRIBUTE_WEIGHTS = {
    "Base": {"SH": 2, "SC": 2, "AG": 2, "ST": 2, "IQ": 1, "CH": 1},
    "Freelance": {"SH": 2, "SC": 2, "AG": 1, "ST": 1, "IQ": 3, "CH": 1},
    "Inside": {"SC": 6, "ST": 2, "IQ": 1, "CH": 1},
    "Attack": {"SC": 5, "AG": 2, "ST": 1, "IQ": 1, "CH": 1},
    "Outside": {"SH": 8, "IQ": 1, "CH": 1},
    "Set": "Same as Attack"
}

THREE_POINT_PROBABILITY = {
    "Outside": 0.8,
    "Base": 0.4,
    "Freelance": 0.2
    # All others default to 0.0
}

# Spots that are three-point shots (outside the arc) - case insensitive
THREE_POINT_SPOTS = {
    "key",
    "deep key",
    "upper wing",
    "deep upper wing",
    "lower wing",
    "deep lower wing",
    "upper midwing",
    "lower midwing",
    "lower midcorner",
    "upper midcorner",
    "upper corner",
    "lower corner",
    "deep upper baseline",
    "deep lower baseline",
}

# Spots that are points in the paint (PIP) - case insensitive
PAINT_SPOTS = {
    "lower lowpost",
    "lower midpost",
    "upper lowpost",
    "upper midpost",
    "midlane",
    "basketspot",
}

# Inside paint area — canonical spot names and bounding rectangle (home orientation,
# basket at x=91). Use is_inside_paint_grid() for arbitrary grid coords; away offense
# mirrors x before the rect check.
INSIDE_PAINT_SPOT_NAMES = (
    "basketSpot",
    "lower lowPost",
    "lower midPost",
    "midLane",
    "upper midPost",
    "upper lowPost",
)

INSIDE_PAINT_RECT_HOME = {
    "x_min": 80,
    "x_max": 87,
    "y_min": 19,
    "y_max": 32,
}

# FLSS (Forced Last Second Shot) x-band thresholds — home orientation; mirror for away.
FLSS_DEEP_KEY_X_HOME = 57
FLSS_NORMAL_SHOT_MIN_X_HOME = 64
FLSS_HEAVE_MAX_X_HOME = 50


def is_inside_paint_grid(x, y, *, home_basket: bool = True) -> bool:
    """True when display grid (x, y) lies inside INSIDE_PAINT_RECT_HOME (mirrored for away)."""
    rect = INSIDE_PAINT_RECT_HOME
    gx = float(x)
    if not home_basket:
        gx = 100.0 - gx
    gy = float(y)
    return rect["x_min"] <= gx <= rect["x_max"] and rect["y_min"] <= gy <= rect["y_max"]

BLOCK_PROBABILITY = {
    "Inside": 0.2,
    "Attack": 0.1,
    "Base": 0.1,
    "Freelance": 0.1
    # All others default to 0.0
}

# Block reconciliation (blocks on shot attempts): diff = shot_score_pre_defense - defense_block_score
# If diff > BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD → shooting foul; if diff < BLOCK_RECONCILIATION_BLOCK_THRESHOLD → block; else → standard shot
# Thresholds are independent: adjust either without affecting the other.
BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD = 150
BLOCK_RECONCILIATION_BLOCK_THRESHOLD = -150
# Block attempt roll: y = random.randint(BLOCK_Y_ROLL_MIN, BLOCK_Y_ROLL_MAX); attempt when y <= aggression
BLOCK_Y_ROLL_MIN = 0
BLOCK_Y_ROLL_MAX = 4
# Secondary block attempt roll: z = random.randint(BLOCK_FIGHT_RANGE_MIN, BLOCK_FIGHT_RANGE_MAX); attempt when z <= defense fight
BLOCK_FIGHT_RANGE_MIN = 0
BLOCK_FIGHT_RANGE_MAX = 10
# Third block attempt roll (individual rim protector): z = random.randint(BLOCK_PLAYER_ROLL_MIN,
# BLOCK_PLAYER_ROLL_MAX); attempt when z <= shot_defender ID + (defense defensive_efficiency × defender height-rating 0-10)
BLOCK_PLAYER_ROLL_MIN = 1
BLOCK_PLAYER_ROLL_MAX = 300

MALLEABLE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT"]

PLAYCALLS = ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]

# Token in STRATEGY_CALL_DICTS["defense"] lists → expand via weighted zone picker (`defense_id` slugs).
STRATEGY_DEFENSE_ZONE_SENTINEL = "__strategy_zone__"

STRATEGY_CALL_DICTS = {
    "defense": {
        0: ["man"],
        1: ["man", "man", STRATEGY_DEFENSE_ZONE_SENTINEL],
        2: ["man", STRATEGY_DEFENSE_ZONE_SENTINEL],
        3: ["man", STRATEGY_DEFENSE_ZONE_SENTINEL, STRATEGY_DEFENSE_ZONE_SENTINEL],
        4: [STRATEGY_DEFENSE_ZONE_SENTINEL],
    },
    "tempo": {
        0: ["slow"],
        1: ["slow", "normal"],
        2: ["normal"],
        3: ["normal", "fast"],
        4: ["fast"],
    },
    "aggression": {
        0: ["passive"],
        1: ["passive", "normal"],
        2: ["normal"],
        3: ["normal", "aggressive"],
        4: ["aggressive"],
    },
}

TEMPO_PASS_DICT = {
    "slow": random.randint(1,6),
    "normal": random.randint(2,4),
    "fast": random.randint(1,3)
}

TURNOVER_CALC_DICT = {
    0: ["PG"],
    1: ["PG", "SG"],
    2: ["PG", "SG", "PG"],
    3: ["PG", "SG", "SF", "PG"],
    4: ["PG", "SG", "SF", "PF", "PG"],
    5: ["PG", "SG", "SF", "PF", "C", "PG"],
    6: ["PG", "SG", "SF", "PF", "C", "PG", "PG"]
}

POSITION_LIST = ["PG", "SG", "SF", "PF", "C"]

# Ball rest position after a make (grid coords, one step toward center from each hoop).
# Must stay in sync with FrontEnd/static/js/phaser/animation/courtConstants.js
MADE_SHOT_SWEET_SPOT_HOME_RIM = {"x": 90, "y": 25}  # hoop at HOME_RIM_COORDS (91)
MADE_SHOT_SWEET_SPOT_AWAY_RIM = {"x": 10, "y": 25}  # hoop at AWAY_RIM_COORDS (9)

# constants/strategy_factors.py
AGGRESSION_FOUL_MULTIPLIER = {
    0: 0.8,
    1: 0.9,
    2: 1,
    3: 1.1,
    4: 1.2,
}

# Shooting Foul System constants
HARD_SHOOTING_FOUL_THRESHOLD = 50
SOFT_SHOOTING_FOUL_THRESHOLD = 110
HARD_PROB = 0.7  # When defense_score < hard_threshold, call shooting foul with this probability (reduces automatic fouls)
SOFT_PROB = 0.16

# Shooting Foul Calibration constants (chance that a defensive shooting foul forces a miss)
THREE_POINTER_FOUL_MISS_CHANCE = 0.4  # 40% chance foul forces miss on 3-pointers
TWO_POINTER_FOUL_MISS_CHANCE = 0.2    # 20% chance foul forces miss on 2-pointers
# After primary FT roll (1–100 vs ft_shot_score), if miss: this probability upgrades miss → make (baseline;
# home crowd / other systems can substitute an adjusted value at call site).
FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.40
# Three-point shot threshold modifier: shot_threshold += (THREE_POINT_SHOT_THRESHOLD_INCREASE - (random(1,5)*momentum))
THREE_POINT_SHOT_THRESHOLD_INCREASE = 55

# HCO Resolution System constants
# Target averages per game:
# - 60 field goal attempts per team per game
# - Average target FG% of 45%
STANDARD_D_FOUL = 96 #changed from 95 to accommodate over the back fouls
STANDARD_O_FOUL = 4 #changed from 5 to accommodate over the back fouls
HARD_STEAL = -135
SOFT_STEAL = -35
HARD_FOUL = 250
SOFT_FOUL = 150
STEAL_ATTEMPT = 30
DEAD_BALL_TURNOVER = 10

# Charge/Blocking Foul (drive reconciliation thresholds)
# reconciliation = offense_score - defense_score
# < CHARGE_THRESHOLD → charge (offensive foul); > BLOCKING_FOUL_THRESHOLD → blocking foul (defensive foul)
CHARGE_THRESHOLD = -240
BLOCKING_FOUL_THRESHOLD = 220

# Situational Logic (Q4/OT): time-band table (see docs/.../Situational_Logic_System.md)
# Each entry: (min_sec, max_sec, config). Time remaining in quarter (seconds). Bands: 2:01-3:00, 1:01-2:00, 0:31-1:00, 0:01-0:30.
SITUATIONAL_TIME_BANDS = (
    (121, 180, {"slow_min": 12, "quick_lo": -24, "quick_hi": -12, "outside": 0.60, "attack": 0.20, "inside": 0.20, "force_foul": False}),
    (61, 120, {"slow_min": 9, "quick_lo": -18, "quick_hi": -9, "outside": 0.70, "attack": 0.20, "inside": 0.10, "force_foul": False}),
    (31, 60, {"slow_min": 3, "quick_lo": -12, "quick_hi": -3, "outside": 0.80, "attack": 0.15, "inside": 0.05, "force_foul_lo": 3, "force_foul_hi": 12}),
    # Last 30s Force Foul: True if 0 < Score Delta < 9 (see Situational_Logic_System.md); force_lo=0 + strict < gives delta 1..8
    # Quick Shot applies only when trailing by more than 3 (delta <= -4). Down exactly 3 stays eligible for Final Shot.
    (0, 30, {"slow_min": 1, "quick_lo": -9, "quick_hi": -3, "last_30_quick": True, "outside_if_delta_below": -3, "force_foul_lo": 0, "force_foul_hi": 9}),
)
# Legacy: used only if a caller expects single ratio; bands above define explicit outside/attack/inside
SITUATIONAL_QUICK_SHOT_ATTACK_RATIO = 0.75
SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MIN = 1
SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MAX = 3
# Inbound pass receiver position for Force Foul (BIP/SIP)
SITUATIONAL_BIP_RECEIVER_POS = "SG"
SITUATIONAL_SIP_RECEIVER_POS = "SG"

# Movement rates. Per-archetype absolute rates at AG=50; the AG curve scales
# them proportionally for other AG values via
# ``ag_to_grid_per_game_sec(ag) / STANDARD_GRID_PER_GAME_SEC``.
# Pass speeds are independent constants — ball physics, not player AG.
PASS_GRID_SPOTS_PER_GAME_SECOND = 24  # Pass (ball in air): Euclidean — HCO / clock-burn accounting.
# Fast-break-specific pass rate (schema-based emitters: CR FB). Used by
# `calc_fb_pass_segment_seconds`. Drives both the visible wall-clock animation
# duration (game-sec × 350 ms) and the clock-burn for the pass step — these
# stay 1:1 synced via the schema playback engine (no wall-clock cap). Tune
# this value to control how fast FB passes feel.
FB_PASS_GRID_SPOTS_PER_GAME_SECOND = 40
FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY = 30  # FB outlet pass when outlet_score < threshold
FB_OUTLET_QUALITY_THRESHOLD = 50                # sharp/sloppy split on fb_roles["outlet_score"]
FB_PASS_MIN_GAME_SECONDS = 0.5                  # T floor for FB pass steps (short passes still register)

# Universal Fast Break shot geometry feature flags. When True, the FB
# resolver replaces its legacy shot location + shot defender selection +
# contested decision with the universal helper in
# BackEnd/utils/fast_break_shot_geometry.py. Flip to False to revert to
# legacy on a per-FB basis. Steal-FB always uses the helper; Triangle is
# intentionally untouched. See:
#   _documentation_master/00_General_Systems/Step_By_Step_System.md
#   _documentation_master/05_GP_Supporting_Systems/Fast_Break_System.md
USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR = True
USE_UNIVERSAL_FB_SHOT_GEOMETRY_CR = True
RESET_INBOUND_PASS_GRID_PER_GAME_SECOND = 24    # Reset step inbound pass (BH → PG)
INBOUND_PASS_GRID_PER_GAME_SECOND = 24          # Inbound pass (SF → PG) for BIP / SIP
HCO_STEP_T_FLOOR_GAME_SECONDS = 0.5             # Min step T for HCO skeleton steps (short-distance steps still visibly play)

# ---- Per-archetype absolute rates (grid/game-sec at AG=50) ----------------
# Add a new archetype: define an absolute rate here, list it in
# ``PlayerArchetype`` Literal, and add a branch in ``_ag_grid_per_game_sec``.
DRIFT_GRID_PER_GAME_SEC       = 8   # archetype "drift"       — slow off-ball relocation (HCT drive/FB off-ball drift)
CRUISE_GRID_PER_GAME_SEC      = 13  # archetype "cruise"      — BH bring-up / settle / transition pace
SHOT_MOTION_GRID_PER_GAME_SEC = 14  # archetype "shot_motion" — shooter during shot
STANDARD_GRID_PER_GAME_SEC    = 14  # archetype "standard"    — base / unaccelerated (AG curve anchor @ AG=50)
SPRINT_GRID_PER_GAME_SEC      = 18  # archetype "sprint"      — max-effort movement (walk-up non-BH, converge)
BURST_GRID_PER_GAME_SEC       = 32  # archetype "burst"       — peak explosive start (FB outlet)

# Per stationary player, the chance to drift toward the offensive rim (vs. hold)
# during the HCT broken-HCT drive step and the ABA Fast Break drive step.
HCT_DRIFT_PROBABILITY = 0.5

# Geometry-based shot contest: defender within this many Euclidean grid spots of
# the shooter counts as contested (non-HCO resolve_shot, motion attack drive,
# dynamic HCT Attack-Basket). Normal HCO set-play shots stay role-based.
CONTEST_EUCLIDEAN_RADIUS = 11

# Shot ball motion: ball flight rate during the [ball_flight] HCO sub-step.
# FE mirrors this in animationPlayback.js (grid-distance / rate × tickMs).
# ~27 grid/game-sec at tickMs=350 is main-branch-equivalent (~333 px/s horizontal).
# Slower than passes by design — shooters are deliberate, passes are quick-twitch.
SHOT_BALL_GRID_PER_GAME_SECOND = 27
FREE_THROW_SHOT_GRID_PER_GAME_SECOND = 12  # FT shot ball motion (grid/game-sec)
# Bounce sub-step T: fixed 300ms wall-clock at tickMs=350. Ball rate during
# bounce therefore varies with distance (rim → bounce_coords) — that spread is
# intentional, a "settle" feels different per bounce length.
BOUNCE_STEP_GAME_SECONDS = 300.0 / 350.0

# OREB putback minimum game-clock burn (game-sec). Putbacks are self-contained
# shot attempts whose UESS schema burn is only ~1-2s (the make [hold] beat is
# clock-paused and the putback flight is short), so the master clock is floored
# here to the designed rebound-capture+putback cost. OREB_KICKOUT is NOT floored
# — its reset time is burned by the following HCO turn's entry orchestrator.
# See Rebound_System.md §OREB clock burn.
OREB_PUTBACK_MIN_TIME_ELAPSED = 2

# Offensive-rebound score discount. Offensive rebounders' final rebound value is
# multiplied by this in select_rebounder_by_score, modeling the defense's box-out /
# positioning advantage on a miss (which the scoring otherwise ignores — offense and
# defense were scored equally). Lower = fewer offensive rebounds. Tune against the
# week-aggregate OREB% (D1 target ~30%); 1.0 = no discount (legacy behavior).
OREB_REBOUND_SCORE_DISCOUNT = 0.8

# Post-shot variant animation timings (SFX_System.md §Ball Resolve
# Animations). Expressed in game-seconds at the default 350 ms/game-sec
# clock so FE wall-clock matches the legacy reference timings.
RATTLE_HOP_GAME_SECONDS = 40.0 / 350.0            # Per-hop wall-clock for RATTLE
RATTLE_MAKE_SETTLE_GAME_SECONDS = 150.0 / 350.0   # RATTLE make: settle into MSSS
BANK_MAKE_SETTLE_GAME_SECONDS = 250.0 / 350.0     # BANK_MAKE: bank → MSSS
BANK_MISS_GRAZE_GAME_SECONDS = 200.0 / 350.0      # BANK_MISS: bank → rim-graze
BOR_MAKE_FOLLOWUP_SWISH_DELAY_MS = 150.0          # BACK_OF_RIM make swish offset
BANK_MAKE_FOLLOWUP_SWISH_DELAY_MS = 100.0         # BANK_MAKE swish offset

# AIRBALL OOB resting points (SFX_System.md: ball continues from
# 2-short-of-MSSS to the OOB sideline). Animation only; backend resolution
# still routes the rebound until the resolution-step 3 cleanup lands.
AIRBALL_OOB_HOME_COORDS = {"x": 97.0, "y": 25.0}
AIRBALL_OOB_AWAY_COORDS = {"x": 3.0, "y": 25.0}
AIRBALL_OOB_GAME_SECONDS = 400.0 / 350.0          # 2-short → OOB resting tween

HCO_STRING_SPOTS = {
    "key": {"x": 64, "y": 25},
    "upper midWing": {"x": 68, "y": 36}, 
    "lower midWing": {"x": 68, "y": 14},
    "upper wing": {"x": 73, "y": 40}, 
    "lower wing": {"x": 73, "y": 10},
    "upper midCorner": {"x": 81, "y": 43}, 
    "lower midCorner": {"x": 81, "y": 7},
    "upper corner": {"x": 88, "y": 44}, 
    "lower corner": {"x": 88, "y": 6},
    "upper highPost": {"x": 74, "y": 32}, 
    "lower highPost": {"x": 74, "y": 19},
    "upper midPost": {"x": 80, "y": 32}, 
    "lower midPost": {"x": 80, "y": 19},
    "upper lowPost": {"x": 86, "y": 32}, 
    "lower lowPost": {"x": 86, "y": 19}, 
    "topLane": {"x": 74, "y": 25},
    "midLane": {"x": 80, "y": 25}, 
    "basketSpot": {"x": 87, "y": 25},
    "upper apex": {"x": 80, "y": 36}, 
    "lower apex": {"x": 80, "y": 15},
    "upper bird": {"x": 85, "y": 36},
    "lower bird": {"x": 85, "y": 15},
    "upper midBaseline": {"x": 89, "y": 36}, 
    "lower midBaseline": {"x": 89, "y": 15},
    "deep key": {"x": 57, "y": 25},
    "deep lower wing": {"x": 57, "y": 15},
    "deep lower baseline": {"x": 57, "y": 5},
    "deep upper wing": {"x": 57, "y": 35},
    "deep upper baseline": {"x": 57, "y": 45},
    "center court": {"x": 50, "y": 25},
    "upper center court wing": {"x": 50, "y": 35},
    "upper center court baseline": {"x": 50, "y": 45},
    "lower center court wing": {"x": 50, "y": 15},
    "lower center court baseline": {"x": 50, "y": 5},
    # Inbound positions (for FCP/HCT skeletons after made baskets)
    "inbound_left": {"x": 3, "y": 25},    # Left of center baseline
    "inbound_right": {"x": 97, "y": 25},   # Right of center baseline
    # HCT inbound-side setup spots for PG/SG (home orientation). Sit near the
    # inbounder so dynamic-HCT step 1 always advances forward from a consistent
    # low-x starting point (see HCT_System.md).
    "hct_inbound_pg": {"x": 10, "y": 25},
    "hct_inbound_sg": {"x": 15, "y": 35},
    # FCP inbound-side setup spots (home orientation). Pre-flipped equivalents
    # of the FCP skeleton's step-0 opp:True spots so BIP can place offense
    # directly without re-applying opp logic downstream.
    "fcp_inbound_pg": {"x": 15, "y": 15},
    "fcp_inbound_sg": {"x": 11, "y": 36},
    "fcp_outlet_pf": {"x": 43, "y": 25},
}

# ---- HCO Setup Positions ---------------------------------------------------
# Used by Fast Break Defensive Stop step-back step (and any future pre-HCO
# transition setup). See:
#   _documentation_master/00_General_Systems/Step_By_Step_System.md
#   (Covert Release → CR Defensive Stop sub-step logic).
#
# Convention: BH(s) excluded from pos slots via the standard alias mapping
# (`_alias_map` in dynamic_hct.py / `_build_set_play_alias_map` in
# playbook_weights_utils.py).
#
#   - Single-BH case (FB BH == HCO BH): the BH goes to a randomly chosen
#     deep frontcourt spot (HCO_SETUP_OFFENSE_BH_DEEP_SPOTS); the other 4
#     supporting players fill pos1..pos4.
#   - Two-BHs case (FB BH != HCO BH): the FB BH goes to a deep frontcourt
#     spot; the HCO BH goes within HCO_SETUP_HCO_BH_RADIUS grid units of
#     the FB BH AND on the same horizontal half (home offense → x ≥ 50;
#     away offense → x ≤ 50, to avoid an over-and-back violation). The
#     remaining 3 supporting players fill pos1..pos3 (pos4 is dropped).
#
# Defenders mirror the offensive setup with same-lineup-position matchup
# (def_PG → off_PG's spot, etc.). The 5 spots form a 2-3 zone footprint
# by construction.
HCO_SETUP_OFFENSE_BH_DEEP_SPOTS = ("deep key", "deep upper wing", "deep lower wing")
HCO_SETUP_OFFENSE_POS_SPOTS = {
    "pos1": "upper wing",
    "pos2": "lower wing",
    "pos3": "upper lowPost",
    "pos4": "lower lowPost",  # dropped when FB BH != HCO BH
}
HCO_SETUP_HCO_BH_RADIUS = 10  # max grid units from FB BH for HCO BH placement


# FCP setup positions — randomized per position range at BIP time. Replaces
# the legacy static `FCP_SETUP_POSITIONS` mapping. SF is NOT in these maps;
# SF uses the dynamic chemistry-aware inbound logic (see HCO BIP / FCP setup
# helper in `turn_manager.py`). All ranges expressed in HOME orientation
# (x≈0..50 = backcourt for home offense). For away offense, the build
# function flips via ``getAwayTeamCoords``.
# See FCP_HCT_System.md → "FCP Starting Alignment" (FCP only; HCT → HCT_System.md).
FCP_OFFENSE_SETUP_RANGES = {
    "PG": {"x": (12, 18)},  # y: SF y + randint(-6, 6) in turn_manager
    "SG": {"x": (25, 32), "y": (20, 30)},
    "PF": {"x": (45, 55), "y": (20, 30)},
    "C":  {"x": (60, 70), "y": (20, 30)},
}
FCP_DEFENSE_SETUP_RANGES = {
    "PG": {"x": (20, 25), "y": (23, 27)},
    "SG": {"x": (26, 31), "y": (30, 36)},
    "SF": {"x": (26, 31), "y": (14, 20)},
    "PF": {"x": (50, 55), "y": (23, 27)},
    "C":  {"x": (71, 76), "y": (23, 27)},
}
# Final separation required between any two players when their random rolls
# land on the same exact (x, y). The chosen player is offset by this many
# grid spots in a random direction — final separation = this constant,
# moved player's new location is exactly this far from his original (so it
# satisfies both the "within N of original" and "≥ N from other" rules).
FCP_SETUP_COLLISION_OFFSET_GRID = 2

# All HCT variants use the same starting positions.
# PG/SG sit on the inbound side near the inbounder so dynamic-HCT step 1
# always advances forward from a consistent low-x starting point. See
# Dynamic HCT step 1 always advances forward from a consistent
# low-x starting point (see HCT_System.md).
HCT_SETUP_POSITIONS = {
    "PG": "hct_inbound_pg",
    "SG": "hct_inbound_sg",
    "SF": "inbound_left",
    "PF": "deep upper wing",
    "C": "deep lower wing"
}

# Offset positions for collision handling (when two players at same spot)
OFFSET_SPOTS = {
    # Center spots: x + 3, y same
    "deep key": {"x": 60, "y": 25},
    "key": {"x": 67, "y": 25},
    "topLane": {"x": 77, "y": 25},
    "midLane": {"x": 83, "y": 25},
    
    # Upper wing/apex spots: x + 3, y - 3
    "deep upper wing": {"x": 60, "y": 32},
    "upper midWing": {"x": 71, "y": 33},
    "upper wing": {"x": 76, "y": 37},
    "upper apex": {"x": 83, "y": 33},
    
    # Upper corner/baseline spots: x same, y - 3
    "upper corner": {"x": 88, "y": 41},
    "upper midCorner": {"x": 81, "y": 40},
    "deep upper baseline": {"x": 57, "y": 42},
    "upper midBaseline": {"x": 89, "y": 33},
    
    # Lower wing/apex spots: x + 3, y + 3
    "deep lower wing": {"x": 60, "y": 18},
    "lower midWing": {"x": 71, "y": 17},
    "lower wing": {"x": 76, "y": 13},
    "lower apex": {"x": 83, "y": 18},
    
    # Lower corner/baseline spots: x same, y + 3
    "lower corner": {"x": 88, "y": 9},
    "lower midCorner": {"x": 81, "y": 10},
    "deep lower baseline": {"x": 57, "y": 8},
    "lower midBaseline": {"x": 89, "y": 18},
    
    # Upper post spots: x - 3, y + 3
    "upper lowPost": {"x": 83, "y": 35},
    "upper midPost": {"x": 77, "y": 35},
    "upper highPost": {"x": 71, "y": 35},
    
    # Lower post spots: x + 3, y - 3
    "lower lowPost": {"x": 89, "y": 16},
    "lower midPost": {"x": 83, "y": 16},
    "lower highPost": {"x": 77, "y": 16}
}

# Shared court coordinates
HOME_RIM_COORDS = {"x": 91, "y": 25}
AWAY_RIM_COORDS = {"x": 9, "y": 25}
HOME_TOP_KEY = {"x": 64, "y": 25}
AWAY_TOP_KEY = {"x": 36, "y": 25}
HOME_INBOUND_LEFT = {"x": 97, "y": 20}  # Home team inbounding from left side (under away basket)
AWAY_INBOUND_LEFT = {"x": 3, "y": 20}   # Away team inbounding from left side (under home basket)

RIM_COORDS = HOME_RIM_COORDS
TOP_KEY_COORDS = HOME_TOP_KEY

ACTIONS = {
    "HANDLE": "handle_ball",
    "PASS": "pass",
    "RECEIVE": "receive",
    "POST_UP": "post_up",
    "SHOOT": "shoot",
    "DRIVE": "drive",
    "SCREEN": "screen",
    "CUT": "cut",
    "GET_OPEN": "get_open",
    "DRIFT": "drift",
    "HOLD": "stationary",
    # 🛡️ Defensive actions
    "GUARD_BALL": "guard_ball",
    "GUARD_OFFBALL": "guard_offball"
}

# Import fast break constants
from BackEnd.constants.fast_break_constants import (
    BALL_HANDLER_MOVE_X_MIN,
    BALL_HANDLER_MOVE_X_MAX,
    BALL_HANDLER_MOVE_Y_RANGE,
    STOPPER_OFFSET_MIN,
    STOPPER_OFFSET_MAX,
    SHOT_DEFENDER_X_OFFSET,
    SHOT_DEFENDER_Y_RANGE,
    fast_break_shot_defender_end_coords,
    REBOUNDER_X_MIN,
    REBOUNDER_X_MAX,
    REBOUNDER_Y_RANGE,
    SHOT_ATTEMPT_REBOUNDER_Y_RANGE,
    OUTLET_PASSER_MOVE_X,
    DEFENSIVE_STOP_Y_RANGE,
    STEAL_ENTRY_MOVE_X_MIN,
    STEAL_ENTRY_MOVE_X_MAX,
    STEAL_ENTRY_MOVE_Y_RANGE,
    STEAL_ENTRY_Y_MIN,
    STEAL_ENTRY_Y_MAX,
    STEAL_HCO_SETUP_MOVE_X_MIN,
    STEAL_HCO_SETUP_MOVE_X_MAX,
    STEAL_HCO_SETUP_MOVE_Y_RANGE,
    STEAL_HCO_SETUP_Y_MIN,
    STEAL_HCO_SETUP_Y_MAX,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX,
)

# Tempo time elapsed: get_time_elapsed(tempo_call) uses these (mean, std, min, max → gauss then clamp).
# Values previously in jamies-cc; now canonical here. See docs Constants_System.md.
TEMPO_PARAMS = {
    "slow": {"mean": 20, "std": 6, "min": 5, "max": 30},
    "normal": {"mean": 15, "std": 6, "min": 5, "max": 30},
    "fast": {"mean": 10, "std": 4, "min": 4, "max": 15},
}

# Team attribute clamps (min, max) for shot_threshold and rebound_modifier. Used by team init and training.
from BackEnd.constants.shot_threshold_scale import team_attr_range as _shot_threshold_team_attr_range

TEAM_ATTR_RANGES = {
    "shot_threshold": _shot_threshold_team_attr_range(),
    "rebound_modifier": (0.0, 0.4),
}
