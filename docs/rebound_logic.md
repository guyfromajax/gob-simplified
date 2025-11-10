# Rebound Logic System

## Overview

This document describes the rebound calculation system used when a shot is missed. The system incorporates strategy settings (offensive rebounding vs getting back on defense, defensive tempo for fast break releases), player attributes, team modifiers, and defensive scheme penalties.

---

## Phase 1: Player Positioning (During Shot Animation)

When a shot is attempted in an HCO instance, players position themselves based on their team's strategy settings.

### Defense Tempo Setting (Fast Break Release)

The defensive team's **Tempo** setting determines the probability that one defender will release early for a potential fast break opportunity:

| Tempo | All 5 Stay | 1 Releases | Released Player |
|-------|------------|------------|-----------------|
| 0     | 100%       | 0%         | N/A             |
| 1     | 75%        | 25%        | PG (or SG if PG guards shooter) |
| 2     | 50%        | 50%        | PG (or SG if PG guards shooter) |
| 3     | 25%        | 75%        | PG (or SG if PG guards shooter) |
| 4     | 0%         | 100%       | PG (or SG if PG guards shooter) |

**Animation:** Released defender animates to:
- **Y coords:** Random 15-35
- **X coords:** Random 45-55

---

### Offense Rebounding Setting (Crash Boards vs Get Back)

The offensive team's **Rebounding** setting determines how many players crash the offensive boards vs get back on defense:

| Rebounding | All 5 Crash | 1 Gets Back | 2 Get Back | Players Getting Back |
|------------|-------------|-------------|------------|----------------------|
| 0          | 100%        | 0%          | 0%         | N/A                  |
| 1          | 50%         | 50%         | 0%         | PG (or SG if PG is shooter) |
| 2          | 25%         | 75%         | 0%         | PG (or SG if PG is shooter) |
| 3          | 10%         | 80%         | 10%        | PG + SG (or SF if one is shooter) |
| 4          | 0%          | 50%         | 50%        | PG + SG (or SF if one is shooter) |

**Animation:** Players getting back animate to:
- **Y coords:** Random 14-36
- **X coords:** 
  - If **away team** shooting: Random 50-60
  - If **home team** shooting: Random 40-50

---

## Phase 2: Rebound Calculation

After determining which players are involved in the rebound battle, the system calculates who wins the rebound.

### Step 1: Base Defensive Probability

Start with a base defensive rebound probability:

```
def_prob = 0.7  (70% base DREB chance)
```

---

### Step 2: Player Advantage Modifier

Adjust based on the number of players attempting the rebound:

```
player_advantage = num_defense_rebounders - num_offense_rebounders
def_prob += (player_advantage * 0.05)
```

**Examples:**
- 5 defenders vs 3 offensive rebounders → +0.10 (80% DREB)
- 4 defenders vs 5 offensive rebounders → -0.05 (65% DREB)
- 4 vs 4 → +0.00 (70% DREB)

---

### Step 3: Calculate Player Rebound Scores

For **all players** attempting the rebound (both teams), calculate their rebound score:

```python
base_score = (RB * 0.5) + (ST * 0.3) + (IQ * 0.2)
die_roll = random.randint(1, 6)
rebound_score = base_score * die_roll
```

**Attribute Weights:**
- **RB (Rebounding):** 50%
- **ST (Strength):** 30%
- **IQ (Basketball IQ):** 20%

**Die Roll:** Adds variance (1-6x multiplier)

---

### Step 4: Select Best Rebounders

From all players attempting the rebound:

```
o_rebounder = offensive player with HIGHEST rebound_score
d_rebounder = defensive player with HIGHEST rebound_score
```

**Note:** This replaced the old weighted random selection. Now the best rebounder from each side competes head-to-head.

---

### Step 5: Apply Team Bias

Teams have a `rebound_modifier` attribute (values: 0.8, 0.9, 1.0, 1.1, 1.2):

```
bias = def_rebound_modifier - off_rebound_modifier
new_prob = min(0.95, max(0.35, def_prob + bias))
```

**Examples:**
- Def Mod 1.2, Off Mod 0.8 → Bias = +0.4 → new_prob = 0.7 + 0.4 = 0.95 (capped)
- Def Mod 0.8, Off Mod 1.2 → Bias = -0.4 → new_prob = 0.7 - 0.4 = 0.35 (capped)

**Caps:** new_prob is capped between 0.35 (35% DREB min) and 0.95 (95% DREB max)

---

### Step 6: Calculate Final Defensive Weight

Combine player skill and team bias:

```python
total_score = d_rebounder_score + o_rebounder_score
d_weight = d_rebounder_score / total_score  # Player skill component (0.0-1.0)
d_weight += (new_prob - 0.5)  # Team/situation bias adjustment
d_weight = min(0.95, d_weight)  # Cap at 95%
```

**Example:**
- Player scores: D=300, O=200 → d_weight = 0.60
- new_prob = 0.75 → Add (0.75 - 0.5) = +0.25
- Final d_weight = 0.60 + 0.25 = 0.85 (85% DREB chance)

---

### Step 7: Zone Defense Penalty

If the defensive team is playing **Zone** defense:

```python
if defense_call == "Zone":
    d_weight *= 0.9  # 10% penalty
```

Zone defenses give up more offensive rebounds due to worse boxing out.

---

### Step 8: Determine Rebound Winner

Roll a random number and compare to d_weight:

```python
roll = random.random()  # 0.0 to 1.0
rebound_team = defense if roll < d_weight else offense
rebounder = d_rebounder if rebound_team == defense else o_rebounder
stat = "DREB" if rebound_team == defense else "OREB"
```

---

## Phase 3: Post-Rebound Actions

### Defensive Rebound (DREB)
- Possession flips to defense
- Determine next play type:
  - **Fast Break:** Based on offensive team's tempo (higher tempo = higher FB chance)
  - **Half-Court Offense (HCO):** Standard setup

### Offensive Rebound (OREB)
- Possession stays with offense
- Creates a separate `OREB` turn with options:
  - **Putback attempt:** Rebounder shoots immediately
  - **Kickout:** Pass to perimeter for new shot attempt

---

## Animation System

### During Shot Animation:

**1. Defenders Releasing for Fast Break:**
- Animate to y: 15-35, x: 45-55
- Timing: During shot flight

**2. Offensive Players Getting Back:**
- If away team shooting: y: 14-36, x: 50-60
- If home team shooting: y: 14-36, x: 40-50
- Timing: During shot flight

### After Shot Misses:

**1. Rebounder:**
- Animates to **exact ball bounce location**

**2. All Other Players:**
- Animate to ±6y, ±4x from ball bounce location
- Can stack on top of each other (realistic scrum)
- Stay in bounds

---

## Expected Results

Based on 100-simulation testing with randomized parameters:

### Strong Defensive Team (Lancaster):
- **Overall:** 78% DREB, 22% OREB
- **5v5:** 81% DREB, 19% OREB
- **4v4:** 80% DREB, 20% OREB

### Weak Defensive Team (South Lancaster):
- **Overall:** 59% DREB, 41% OREB
- **5v5:** 52% DREB, 48% OREB
- **4v4:** 62% DREB, 38% OREB

### NBA Comparison:
- **NBA League Average:** 72-78% DREB, 22-28% OREB
- **Our System:** Ranges from 59-78% DREB based on team quality ✅

---

## Code Locations

- **Rebound Calculation:** `BackEnd/models/shot_manager.py` (lines 259-315)
- **Player Score Formula:** `BackEnd/utils/shared.py` - `calculate_rebound_score()`
- **Animation Logic:** `FrontEnd/static/js/phaser/animation/turnAnimation.js`
- **Shot Animation System:** `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`

---

## Formula Summary

```
Final DREB% = min(0.95, 
    (d_score / (d_score + o_score))           # Player skill (50/50 baseline)
    + ((0.7 + player_advantage + team_bias) - 0.5)  # Situational adjustment
    * (0.9 if Zone else 1.0)                  # Zone penalty
)
```

**Components:**
1. **Base:** 70% DREB
2. **Player Advantage:** ±5% per extra player
3. **Team Bias:** ±(def_mod - off_mod), capped 0.35-0.95
4. **Player Skill:** Die-rolled scores determine head-to-head matchup
5. **Zone Penalty:** -10% if defense plays Zone
6. **Final Cap:** 95% maximum DREB probability

---

## Testing

See `tests/simulate_new_rebound_logic.py` for simulation script.

**Last Updated:** November 10, 2025

