"""Player Momentum (MO) system tunables — single source of truth.

Keep in sync with _documentation_master/projects/Player_Momentum_System.md:
the doc documents these names/values so they can be tuned in one place and the
code reads them directly. Player MO is clamped to [MO_MIN, MO_MAX] via
``player.clamp_mo``.
"""

# --- Per-player MO scale (mirrors player.clamp_mo) ---
MO_MIN = -10
MO_MAX = 10

# --- Event deltas ---
MO_BLOCK_DELTA = 1            # blocker +, blocked shooter −
MO_STEAL_DELTA = 1            # stealer +, victim −
MO_AND_ONE_DELTA = 1          # made shot + shooting foul → shooter +
MO_DUNK_DELTA = 1            # DEFERRED — dunks not wired yet (hook only)
MO_CHARGE_DELTA = 1          # charge drawer +, charging player −
MO_OREB_DELTA = 1
MO_OREB_THRESHOLD = 3        # +MO_OREB_DELTA on a player's 3rd OREB and each after

# --- Free throws: miss the whole trip → penalty ---
MO_FT_MISS_MIN_ATTEMPTS = 2  # only trips with >1 FT attempted qualify
MO_FT_ALL_MISS_DELTA = -1    # flat, once per trip, when ALL attempted FTs miss

# --- Set play: target shooter makes the shot in a successful skeleton ---
MO_SET_PLAY_DELTA = 1

# --- Consecutive shots (read from per-game Shot_Result_List) ---
MO_CONSECUTIVE_THRESHOLD = 3  # 3rd make/miss in a row, and each one after
MO_CONSECUTIVE_DELTA = 1      # + per consecutive make / − per consecutive miss

# --- Shot-attempt impact (shooter base roll + putback roll) ---
MO_SHOT_ROLL_BASE = (1, 6)        # default roll
MO_SHOT_ROLL_POSITIVE = (2, 6)    # when MO > 0 and the chance hits
MO_SHOT_ROLL_NEGATIVE = (1, 5)    # when MO < 0 and the chance hits
MO_SHOT_IMPACT_PCT_PER_LEVEL = 10  # P(modified roll) = |MO| × this (%)

# --- Shot-clock violation (per active player, independent roll) ---
MO_SHOTCLOCK_BASE_PCT = 40
MO_SHOTCLOCK_OFFENSE_DELTA = -1   # P = clamp(BASE − offenseTeamMO, 0, 100)%
MO_SHOTCLOCK_DEFENSE_DELTA = 1    # P = clamp(BASE + defenseTeamMO, 0, 100)%

# --- Resets ---
# Move each active player toward 0 by a randint(MIN, MAX), never crossing 0.
# Bench → 0. Never on foul-out. Quarter breaks (Q1→Q2, Q3→Q4) and OT breaks use
# the larger range; timeouts use the smaller range.
MO_RESET_REDUCTION_MIN = 4         # quarter + OT breaks
MO_RESET_REDUCTION_MAX = 7
MO_TIMEOUT_REDUCTION_MIN = 2       # timeouts
MO_TIMEOUT_REDUCTION_MAX = 4
# Halftime (Q2→Q3): everyone → 0, except the rails:
MO_HALFTIME_HIGH_RESET = (1, 3)    # MO == +MO_MAX → randint(1, 3)
MO_HALFTIME_LOW_RESET = (-3, -1)   # MO == −MO_MAX (−10) → randint(−3, −1)
MO_FINAL_SHOT_BONUS = 1            # made the quarter's Final Shot → + after reset

# --- Team momentum (DERIVED = sum of a team's 5 active players' MO) ---
MO_TEAM_MIN = -50   # = 5 × MO_MIN
MO_TEAM_MAX = 50    # = 5 × MO_MAX
