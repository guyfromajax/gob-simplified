# Constants System

This document lists all constants and variables that were previously on the deprecated **jamies-cc** (God mode) page, with their **current values** in one place for reference. The game engine now reads them only from `BackEnd/constants/__init__.py` (no runtime file I/O). This file is the human-readable reference; the code is the source of truth.

---

## Turn Results

| Key | Current value | Notes |
|-----|---------------|--------|
| `STANDARD_D_FOUL` | 95 | |
| `STANDARD_O_FOUL` | 5 | |
| `HARD_STEAL` | -200 | |
| `SOFT_STEAL` | -100 | |
| `HARD_FOUL` | 200 | |
| `SOFT_FOUL` | 100 | |
| `STEAL_ATTEMPT` | 25 | |
| `DEAD_BALL_TURNOVER` | 7 | |

---

## Charges

| Key | Current value | Notes |
|-----|---------------|--------|
| `CHARGE_THRESHOLD` | -240 | reconciliation &lt; this → charge (offensive foul) |
| `BLOCKING_FOUL_THRESHOLD` | 220 | reconciliation &gt; this → blocking foul (defensive foul) |

---

## Blocks

| Key | Current value | Notes |
|-----|---------------|--------|
| `BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD` | 200 | diff above this → shooting foul |
| `BLOCK_RECONCILIATION_BLOCK_THRESHOLD` | -200 | diff below this → block |
| `BLOCK_Y_ROLL_MIN` | 1 | Y random range min (block attempt roll) |
| `BLOCK_Y_ROLL_MAX` | 6 | Y random range max |

---

## Aggression Foul Multiplier

Levels 1–5 map to aggression indices 0–4.

| Key | Current value | Notes |
|-----|---------------|--------|
| `aggression_foul_1` | 0.8 | index 0 |
| `aggression_foul_2` | 0.9 | index 1 |
| `aggression_foul_3` | 1.0 | index 2 |
| `aggression_foul_4` | 1.1 | index 3 |
| `aggression_foul_5` | 1.2 | index 4 |

---

## Shooting Thresholds

| Key | Current value | Notes |
|-----|---------------|--------|
| `HARD_SHOOTING_FOUL_THRESHOLD` | 50 | |
| `SOFT_SHOOTING_FOUL_THRESHOLD` | 110 | |
| `SOFT_PROB` | 0.16 | |
| `THREE_POINTER_FOUL_MISS_CHANCE` | 0.4 | chance defensive shooting foul forces miss on 3PT |
| `TWO_POINTER_FOUL_MISS_CHANCE` | 0.2 | chance defensive shooting foul forces miss on 2PT |
| `THREE_POINT_SHOT_THRESHOLD_INCREASE` | 40 | shot_threshold += (this - (random(1,5)*momentum)) for 3PT |

---

## Team Attribute Ranges

Used for TEAM_ATTR_CLAMPS (e.g. training, team init). Min/max clamp for generated or overridden team attributes.

| Key | Current value | Notes |
|-----|---------------|--------|
| `shot_threshold_min` | -10 | |
| `shot_threshold_max` | 190 | |
| `rebound_modifier_min` | 0.0 | |
| `rebound_modifier_max` | 0.4 | |

---

## Tempo Time Elapsed Ranges

Used by `get_time_elapsed(tempo_call)` in `BackEnd/utils/shared.py`. Each tempo (slow, normal, fast) uses mean, std, min, max; time = `max(min, min(max, gauss(mean, std)))`.

### Slow

| Key | Current value |
|-----|---------------|
| `tempo_slow_mean` | 24 |
| `tempo_slow_std` | 6 |
| `tempo_slow_min` | 5 |
| `tempo_slow_max` | 35 |

### Normal

| Key | Current value |
|-----|---------------|
| `tempo_normal_mean` | 18 |
| `tempo_normal_std` | 6 |
| `tempo_normal_min` | 5 |
| `tempo_normal_max` | 35 |

### Fast

| Key | Current value |
|-----|---------------|
| `tempo_fast_mean` | 12 |
| `tempo_fast_std` | 4 |
| `tempo_fast_min` | 4 |
| `tempo_fast_max` | 15 |

---

## Where these live in code

- **Canonical source:** `BackEnd/constants/__init__.py`. All values above are defined there (module-level constants, `TEMPO_PARAMS`, `TEAM_ATTR_RANGES`). The game engine imports from constants only; no config file or runtime file reads.
- **Tempo:** `get_time_elapsed()` in `BackEnd/utils/shared.py` uses `TEMPO_PARAMS`.
- **Team attribute ranges:** `TeamManager.init_team_attributes()`, `initialize_team_attributes()` in main, and `TEAM_ATTR_CLAMPS` in `training_execution_v2.py` use `TEAM_ATTR_RANGES`.
