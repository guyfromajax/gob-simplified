# Attribute Clamp System

Single reference for **absolute clamp ranges** applied to player and team attributes (e.g. in training, init, distant-team templates). Values outside these ranges are clamped before persistence.

**Code:** `BackEnd/models/training_execution_v2.py` (`PLAYER_ATTR_CLAMP`, `TEAM_ATTR_CLAMPS`); team init uses `BackEnd/constants/__init__.py` (`TEAM_ATTR_RANGES`) for `shot_threshold` and `rebound_modifier`.

---

## Player attributes

| Clamp | Value |
|-------|--------|
| **Min** | 1 |
| **Max** | None |

Applies to all trainable player attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, CH). EM and NG are not clamped by this system.

**MO (Momentum)** has its own hard bound, **−10 to +10**, enforced canonically on every `Player` load (`Player._extract_attributes` via `clamp_mo`, `BackEnd/models/player.py`) and at its write sites (init resets to 0; the Culture-Builder training bump clamps to the same range). So no persisted or legacy MO value can reach the engine/UI outside scale.

---

## Team attributes

### shot_threshold

| Clamp | Value |
|-------|--------|
| **Min** | 10 |
| **Max** | 210 |

### rebound_modifier

| Clamp | Value |
|-------|--------|
| **Min** | 0 |
| **Max** | 0.4 |

### team_chemistry

| Clamp | Value |
|-------|--------|
| **Min** | 7 |
| **Max** | 25 |

### Other nine (range -10 to 10)

| Clamp | Value |
|-------|--------|
| **Min** | -10 |
| **Max** | 10 |

Attributes in this group:

- `offensive_efficiency`
- `defensive_efficiency`
- `pt_efficiency`
- `fb_efficiency`
- `pt_opp_modifier`
- `fb_opp_modifier`
- `momentum_score`
- `fight`
- `discipline`
