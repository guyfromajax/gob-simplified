## Energy System ✅ **COMPLETE** (January 2025; re-verified June 2026)

> **Note:** Inline line-number citations below have drifted from the live files (the logic/values are verified current). Search by function name rather than line number.

**Base Constants**

1. **Energy Attribute**: `NG` (Natural Growth/Nerve/Game)
2. **Energy Range**: 0.0 to 1.0 (clamped)
3. **Energy Minimum**: 0.1 (prevents zero energy during gameplay)
4. **Energy Maximum**: 1.0 (100% energy)
5. **Recharge Types**:
   - **Quarter Break (Non-Halftime)**: Random from `[0.07, 0.08, 0.09, 0.1, 0.11, 0.12]`
   - **Halftime Break**: Random from `[0.15, 0.16, 0.17, 0.18, 0.19, 0.2]`
   - **Timeout Break**: Random from `[0.03, 0.04, 0.05, 0.06]`
   - **Bench Recharge**: 20% chance 0, 70% chance +0.01, 10% chance +0.02 (per HCO turn only)
6. **Depletion System**: ND (Natural Durability) attribute-based via `get_fatigue_decay_amount()`
7. **Depletion Turn Types**: HCO, Fast Break, FCP, HCT
8. **Key Files**:
   - `BackEnd/models/player.py` - `get_fatigue_decay_amount()`, `decay_energy()`, `recharge_energy()` (lines 124-169)
   - `BackEnd/utils/energy_system.py` - `recharge_all_players()` (lines 26-42)
   - `BackEnd/api/api.py` - Quarter break recharge (lines 2198-2214)
   - `BackEnd/models/game_manager.py` - Timeout recharge (lines 225-233)
   - `BackEnd/engine/phase_resolution.py` - `apply_energy_decay()` (lines 60-87), `apply_bench_energy_recharge()` (lines 80-113)

**System Flow (6 Steps)**

1. **Energy Depletion (During Active Play)**: Applied to all 10 active lineup players at the start of HCO, Fast Break, FCP, and HCT turns
2. **Fatigue Calculation**: Each player's ND attribute determines their fatigue decay amount via `get_fatigue_decay_amount()`
3. **Attribute Rescaling**: After energy changes, all malleable attributes are rescaled based on NG value
4. **Bench Recharge (HCO Turns Only)**: Bench players receive small random recharge during HCO turns (not Fast Break, FCP, or HCT)
5. **Break Recharge**: Quarter breaks, halftime, and timeouts recharge all players (lineup + bench) with different amounts
6. **Energy Clamping**: All energy values clamped to valid range (0.1 minimum during gameplay, 1.0 maximum)

**Long Form Documentation**

### Overview

The Energy System manages player energy (NG attribute) depletion during active gameplay and energy restoration during breaks. Energy directly affects player performance by scaling all malleable attributes (the 10 `MALLEABLE_ATTRS`: SC, SH, ID, OD, PS, BH, RB, ST, AG, FT). Higher energy means better performance, while depleted energy reduces attribute effectiveness. **ND and IQ are deliberately NOT scaled** (ND drives fatigue resistance, so scaling it would create a death-spiral).

**Key Features:**
- Energy depletes during active gameplay (HCO, Fast Break, FCP, HCT turns)
- Energy recharges during breaks (quarter breaks, halftime, timeouts)
- Bench players recharge slightly during HCO turns
- Energy affects all player attributes through rescaling
- ND (Natural Durability) attribute determines fatigue resistance

### Energy Replenishment

#### 1. Quarter Break Recharge (Non-Halftime)

**When:** Between Q1→Q2, Q3→Q4, or before any overtime quarters

**Who:** All players (active lineup + bench players) on both teams

**Amount:** Random per player from `[0.07, 0.08, 0.09, 0.1, 0.11, 0.12]`

**Code Location:** `BackEnd/api/api.py` - `simulate_turn_endpoint()` (lines 2198-2214)

**Implementation:**
- Triggered when `quarter_complete = True` in `simulate_turn_endpoint()`
- Uses `recharge_all_players()` from `BackEnd/utils/energy_system.py`
- Happens BEFORE game state is saved, ensuring updated NG values are visible on lineup screen
- Each player gets a random amount from the recharge list
- Energy is clamped to maximum of 1.0

**Note:** Quarter break recharge was moved from `BackEnd/main.py` to `BackEnd/api/api.py` to ensure recharge happens before game state persistence, allowing users to see updated energy values on the lineup screen.

#### 2. Halftime Break Recharge

**When:** Between Q2→Q3 (halftime break)

**Who:** All players (active lineup + bench players) on both teams

**Amount:** Random per player from `[0.15, 0.16, 0.17, 0.18, 0.19, 0.2]`

**Code Location:** `BackEnd/api/api.py` - `simulate_turn_endpoint()` (lines 2207-2209)

**Implementation:**
- Detected when `current_quarter == 2` (quarter that just completed)
- Uses larger recharge amounts than regular quarter breaks
- Same implementation pattern as quarter break recharge
- Energy is clamped to maximum of 1.0

**Note:** Halftime provides significantly more energy restoration than regular quarter breaks, representing the longer break period.

#### 3. Timeout Break Recharge

**When:** At the start of any timeout (user-initiated, computer-initiated, or foul out)

**Who:** All players (active lineup + bench players) on both teams

**Amount:** Random per player from `[0.03, 0.04, 0.05, 0.06]`

**Code Location:** `BackEnd/models/game_manager.py` - `call_timeout()` (lines 225-233)

**Implementation:**
- Happens immediately when timeout is called
- Uses `team.get_all_players()` to include bench players
- Small recharge amounts (much less than quarter breaks)
- Happens BEFORE lineup selection screen, so user sees updated energy values
- Energy is clamped to maximum of 1.0

**Note:** Timeout recharge provides minimal energy restoration compared to quarter breaks, representing the shorter break period. The recharge happens before the lineup screen to ensure users can make informed lineup decisions based on updated energy levels.

#### 4. Bench Recharge (HCO Turns Only)

**When:** During HCO (Half Court Offense) turns only

**Who:** All bench players (players not in active lineup) on both teams

**Amount:** Per turn, per bench player:
- 20% chance: no recharge (0)
- 70% chance: +0.01 energy
- 10% chance: +0.02 energy

**Code Location:** `BackEnd/engine/phase_resolution.py` - `apply_bench_energy_recharge()` (lines 80-113), called from `resolve_half_court_offense_logic()` (line 3630)

**Implementation:**
- Only called during HCO turns (not Fast Break, FCP, or HCT)
- Identifies bench players by comparing `player_id` against lineup player IDs
- Uses random roll to determine recharge amount
- Small incremental recharge (0.01 or 0.02 per turn)
- Energy is clamped to maximum of 1.0

**⚠️ IMPORTANT:** Bench recharge does NOT happen during Fast Break, FCP, or HCT turns - only during HCO turns. This ensures bench players only recharge during slower-paced half court situations, not during high-intensity fast break or press scenarios.

### Energy Depletion

#### Overview

Energy depletion occurs during active gameplay when players are actively participating in turns. All 10 active lineup players (5 per team) lose energy based on their ND (Natural Durability) attribute.

**Turn Types with Energy Depletion:**
- **HCO** (Half Court Offense) turns
- **Fast Break** turns
- **FCP** (Full Court Press) turns
- **HCT** (Half Court Trap) turns

**Code Location:** `BackEnd/engine/phase_resolution.py` - `apply_energy_decay()` (lines 60-87)

**Called From:**
- `resolve_half_court_offense_logic()` (line 3742)
- `resolve_fast_break_logic()` (line 689)
- `resolve_full_court_press_logic()` (line 4394) - with `omit_zeros_for_defense=True`
- `resolve_half_court_trap_logic()` (line 5469) - with `omit_zeros_for_defense=True`

**Special Case - FCP/HCT Defensive Players:**
- For defensive players on FCP and HCT turns only, zero values are omitted from the depletion list
- This ensures defensive players always lose some energy when applying pressure defense
- Offensive players always use normal depletion (with zeros included)
- Implemented via `omit_zeros_for_defense=True` parameter in `apply_energy_decay()`

#### Depletion Calculation

**Method:** `BackEnd/models/player.py` - `get_fatigue_decay_amount()` (ND tiers in the module-level `_ND_DECAY_TIERS` list)

**Formula:** Based on player's ND (Natural Durability) attribute, returns a random amount from a weighted list. Optionally omits zero values for defensive players on FCP/HCT turns. A positive-MO player may decay from one tier higher (see *Momentum bonus* below).

**Parameters:**
- `omit_zeros` (default: False): If True, removes all zero values from the depletion list before selection. Used for defensive players on FCP/HCT turns to ensure they always lose some energy.

- **ND ≥ 89**: `random.choice([0, 0.01])` (very low depletion)
- **ND ≥ 79**: `random.choice([0, 0.01, 0.01])` (low depletion)
- **ND ≥ 69**: `random.choice([0, 0, 0.01, 0.01, 0.01])` (low-medium depletion)
- **ND ≥ 59**: `random.choice([0, 0, 0.01, 0.01, 0.02])` (medium depletion)
- **ND ≥ 49**: `random.choice([0, 0.01, 0.01, 0.01, 0.02])` (medium-high depletion)
- **ND ≥ 39**: `random.choice([0, 0.01, 0.01, 0.02, 0.02])` (high depletion)
- **ND ≥ 29**: `random.choice([0, 0.01, 0.01, 0.02, 0.03])` (very high depletion)
- **ND ≥ 19**: `random.choice([0, 0.01, 0.02, 0.02, 0.03])` (extreme depletion)
- **ND ≥ 9**: `random.choice([0, 0.01, 0.02, 0.02, 0.02, 0.03])` (maximum depletion)
- **ND < 9**: `random.choice([0, 0.01, 0.02, 0.02, 0.03, 0.03])` (maximum depletion)

**Momentum bonus (MO):** a player with **MO > 0** has a chance to take the turn's decay from **one ND tier higher** (less fatigue) — e.g. a 35 ND (tier `ND ≥ 29`) can pull from the `ND ≥ 39` list. The chance is **|MO| × `MO_NG_DECAY_BONUS_PCT_PER_LEVEL`** (= 20) %, capped at 100; each player rolls independently each turn:

| MO | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| chance | 20% | 40% | 60% | 80% | 100% |

- Only **one** tier up (the magnitude of the bonus doesn't grow with MO — only the *chance* does), capped at the top tier (`ND ≥ 89`).
- **MO ≤ 0 → no effect** (normal decay). Composes with `omit_zeros` (the higher tier's list still drops zeros for FCP/HCT defenders).
- Wired in `get_fatigue_decay_amount()` (`player.py`); constant in `BackEnd/constants/momentum.py`. See [Player_Momentum_System.md](Player_Momentum_System.md).

**Key Points:**
- Higher ND = less energy depletion per turn
- Lower ND = more energy depletion per turn
- Depletion amounts range from 0 (no depletion) to 0.03 (maximum depletion)
- Random selection adds variance to fatigue progression
- Default ND value is 50 if not set
- **FCP/HCT Defensive Players**: When `omit_zeros=True`, all zero values are filtered out before selection, ensuring defensive players always lose at least 0.01 energy per turn

#### Depletion Application

**Method:** `BackEnd/models/player.py` - `decay_energy()` (lines 148-150)

**Process:**
1. Subtract depletion amount from current NG value
2. Clamp NG to minimum of 0.1 (prevents zero energy)
3. Round to 3 decimal places
4. Call `_rescale_attributes()` to update all malleable attributes

**Attribute Rescaling:**
After energy changes, all malleable attributes are rescaled based on the new NG value:
```python
for k in MALLEABLE_ATTRS:
    self.attributes[k] = int(self.attributes[f"anchor_{k}"] * ng)
```
This ensures that as energy depletes, the 10 malleable attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, FT) are reduced proportionally. **ND and IQ are not in `MALLEABLE_ATTRS` and are not rescaled.**

### Energy System Summary

| Situation | Who | Amount | Frequency |
|-----------|-----|--------|-----------|
| Quarter Break (non-halftime) | All players | Random: [0.07, 0.08, 0.09, 0.1, 0.11, 0.12] | Per quarter break (Q1→Q2, Q3→Q4, before OT) |
| Halftime Break | All players | Random: [0.15, 0.16, 0.17, 0.18, 0.19, 0.2] | Once per game (Q2→Q3) |
| Timeout | All players | Random: [0.03, 0.04, 0.05, 0.06] | Per timeout (user/computer/foul out) |
| Bench Recharge | Bench players only | 20%: 0, 70%: +0.01, 10%: +0.02 | Per HCO turn only |
| Energy Depletion | Active lineup only | ND-based (0 to 0.03) | Per HCO/Fast Break/FCP/HCT turn |

### Key Files

**Backend:**
- `BackEnd/models/player.py` - Core energy methods:
  - `get_fatigue_decay_amount()` (lines 124-169) - Calculates depletion based on ND
    - Accepts `omit_zeros` parameter for FCP/HCT defensive players
  - `decay_energy()` (lines 148-150) - Applies depletion and rescales attributes
  - `recharge_energy()` (lines 153-155) - Applies recharge and rescales attributes
  - `reset_energy()` (lines 157-159) - Resets NG to 1.0
  - `_rescale_attributes()` (lines 167-170) - Rescales all malleable attributes based on NG
- `BackEnd/utils/energy_system.py` - Recharge utilities:
  - `recharge_all_players()` (lines 26-42) - Recharges all players (lineup + bench)
  - `recharge_lineups()` (lines 7-24) - Deprecated: only recharges lineup players
- `BackEnd/api/api.py` - Quarter break recharge:
  - `simulate_turn_endpoint()` (lines 2198-2214) - Handles quarter/halftime recharge
- `BackEnd/models/game_manager.py` - Timeout recharge:
  - `call_timeout()` (lines 225-233) - Handles timeout recharge
- `BackEnd/engine/phase_resolution.py` - Gameplay energy management:
  - `apply_energy_decay()` (lines 60-87) - Applies depletion to active lineup players
    - Accepts `omit_zeros_for_defense` parameter for FCP/HCT defensive players
    - Called with `omit_zeros_for_defense=True` in `resolve_full_court_press_logic()` and `resolve_half_court_trap_logic()`
  - `apply_bench_energy_recharge()` (lines 80-113) - Recharges bench players during HCO

### Energy and Attribute Scaling

**Malleable Attributes (`MALLEABLE_ATTRS` in `BackEnd/constants/__init__.py`):**
The following 10 attributes are scaled by NG. Everything else — including NG itself, EM (Emotion), MO (Momentum), CH (Chemistry), **ND (Natural Durability)**, and **IQ (Intelligence)** — is **not** scaled.
- SC (Scoring)
- SH (Shooting)
- ID (Inside Defense)
- OD (Outside Defense)
- PS (Passing)
- BH (Ball Handling)
- RB (Rebounding)
- ST (Stealing)
- AG (Agility)
- FT (Free Throw)

> **Note:** ND is intentionally excluded so a fatigued player's durability (which governs how fast they deplete) does not itself decay; IQ is likewise excluded.

**Scaling Formula:**
```
effective_attribute = anchor_attribute * NG
```

**Example:**
- Player has anchor_SC = 80, NG = 0.75
- Effective SC = 80 * 0.75 = 60
- Player performs at 60 SC instead of 80 due to reduced energy

**Benefits:**
- Creates realistic fatigue progression
- Encourages strategic lineup management
- Makes ND attribute valuable for endurance
- Adds depth to game strategy

