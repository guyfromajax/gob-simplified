# Original Thresholds (Jamie's CC / God Mode)

Reference values for all configurable thresholds on the **jamies-cc** (God mode) page. Use these to restore defaults if you change values and want to revert.

Source: `BackEnd/utils/config_overrides.py` (DEFAULTS) and `BackEnd/constants/__init__.py` / `BackEnd/utils/shared.py`.

---

## Turn Results

| Key | Original value | Notes |
|-----|----------------|--------|
| STANDARD_D_FOUL | 95 | Base defensive foul threshold (HCO resolution). Calibrated with fight. |
| STANDARD_O_FOUL | 5 | Base offensive foul threshold. |
| HARD_STEAL | -200 | Steal threshold (calibrated with discipline). |
| SOFT_STEAL | -100 | Soft steal threshold. |
| HARD_FOUL | 200 | Foul threshold on steal attempts (calibrated with fight). |
| SOFT_FOUL | 100 | Soft foul threshold on steal attempts. |
| STEAL_ATTEMPT | 25 | Steal attempt rate. |
| DEAD_BALL_TURNOVER | 7 | Dead ball turnover threshold (calibrated with discipline). |

---

## Charges

| Key | Original value | Notes |
|-----|----------------|--------|
| CHARGE_THRESHOLD | -240 | reconciliation < this → charge (offensive foul). |
| BLOCKING_FOUL_THRESHOLD | 220 | reconciliation > this → blocking foul (defensive foul). |

---

## Blocks

| Key | Original value | Notes |
|-----|----------------|--------|
| BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD | 200 | diff > this → shooting foul from block. |
| BLOCK_RECONCILIATION_BLOCK_THRESHOLD | -200 | diff < this → block. (Thresholds are independent.) |
| BLOCK_Y_ROLL_MIN (Y Random Range Min) | 1 | Block attempt roll: random.randint(min, max). |
| BLOCK_Y_ROLL_MAX (Y Random Range Max) | 6 | Block attempted when roll < aggression. |

---

## Aggression Foul Multiplier

| Key (display) | Original value | Notes |
|---------------|----------------|--------|
| 1 | 0.8 | AGGRESSION_FOUL_MULTIPLIER index 0. |
| 2 | 0.9 | Index 1. |
| 3 | 1.0 | Index 2. |
| 4 | 1.1 | Index 3. |
| 5 | 1.2 | Index 4. |

---

## Shooting Thresholds

| Key | Original value | Notes |
|-----|----------------|--------|
| HARD_SHOOTING_FOUL_THRESHOLD | 50 | defense_score < hard_threshold → foul (inside base). |
| SOFT_SHOOTING_FOUL_THRESHOLD | 110 | defense_score < soft_threshold → SOFT_PROB chance of foul. |
| SOFT_PROB | 0.16 | 16% chance soft contact is called a foul. |
| THREE_POINTER_FOUL_MISS_CHANCE | 0.4 | 40% chance a foul forces a miss on 3-pointers. |
| TWO_POINTER_FOUL_MISS_CHANCE | 0.2 | 20% chance a foul forces a miss on 2-pointers. |
| THREE_POINT_SHOT_THRESHOLD_INCREASE | 40 | shot_threshold += (40 - (random(1,5) * momentum)) for 3-pointers. |

---

## Team Attribute Ranges

| Key | Original value | Notes |
|-----|----------------|--------|
| shot_threshold_min | -10 | Min for team shot_threshold (TEAM_ATTR_CLAMPS, init, balancing). |
| shot_threshold_max | 190 | Max for team shot_threshold. |
| rebound_modifier_min | 0.0 | Min for team rebound_modifier. |
| rebound_modifier_max | 0.4 | Max for team rebound_modifier. |

---

## Tempo Time Elapsed Ranges

Used by `get_time_elapsed(tempo_call)`: `int(max(min, min(max, random.gauss(mean, std))))`.

### Slow

| Key | Original value |
|-----|----------------|
| tempo_slow_mean | 24 |
| tempo_slow_std | 6 |
| tempo_slow_min | 5 |
| tempo_slow_max | 35 |

### Normal

| Key | Original value |
|-----|----------------|
| tempo_normal_mean | 18 |
| tempo_normal_std | 6 |
| tempo_normal_min | 5 |
| tempo_normal_max | 35 |

### Fast

| Key | Original value |
|-----|----------------|
| tempo_fast_mean | 12 |
| tempo_fast_std | 4 |
| tempo_fast_min | 4 |
| tempo_fast_max | 15 |

---

*Last updated to match defaults in code as of creation. Overrides are stored in `config_overrides.json` when changed via Jamie's CC.*
