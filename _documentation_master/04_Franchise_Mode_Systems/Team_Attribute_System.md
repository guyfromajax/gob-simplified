# Team Attribute Management System (**verified 2026-06-13**)

> Verified vs code — **substance accurate**. `init_team_attributes` mode ranges match `team_manager.py` exactly (franchise **creation**: attr `(-2,0)`, `team_chemistry` 8-11, `rebound_modifier` 0.5 fixed, `shot_threshold` 65-75; single/tournament-fallback: attr `(-10,10)`, chemistry 7-25, rebound 0.0-0.4, shot_threshold from `TEAM_ATTR_RANGES`). **Season rollover** (new season in an existing franchise) does NOT carry team_attributes: non-core fields re-init like creation and the 8 core attrs re-roll on a carryover-scaled range — see § Season Rollover Re-Roll. All franchise games now use the full turn-by-turn engine and the normal usage/scouting-driven EOG rules. **Note:** Single Game & Tournament mode ranges are documented for completeness but those modes are **(sunset)**; franchise is the live path.

## Base Constants

1. **Core Team Attributes**:
   - `shot_threshold` - Shot attempt threshold (range: −30 to 170; see [Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md))
   - `discipline` - Turnover modifier (formerly `turnover_modifier`)
   - `fight` - Foul modifier (formerly `foul_modifier`)
   - `rebound_modifier` - Rebound effectiveness modifier (range: 0.0-1.0)
   - `offensive_efficiency` - Offensive efficiency rating
   - `team_chemistry` - Team chemistry rating
   - `defensive_efficiency` - Defensive efficiency rating
   - `fb_efficiency` - Fast break efficiency rating
   - `pt_efficiency` - Press/Trap efficiency rating
   - `fb_opp_modifier` - Fast break opponent modifier
   - `pt_opp_modifier` - Press/Trap opponent modifier

2. **Mode-Specific Attribute Ranges**:
   - **Single Game & Tournament**: Most attributes use `random.randint(-10, 10)`, `team_chemistry=random(7-25)`, `rebound_modifier=random(0.0-0.4)` (sunset modes keep the original narrow rebound spread)
   - **Franchise (creation)**: Most attributes use `random.randint(-2, 0)`, `team_chemistry=random(8-11)`, `rebound_modifier=0.5` (fixed)
   - **Franchise (season rollover)**: team_attributes do not carry over; the 8 core attrs re-roll on a carryover-scaled range (§ Season Rollover Re-Roll), other fields re-init like creation

3. **Initialization Source**: Universal `teams` collection in MongoDB → Team objects → Fallback to `TeamManager.init_team_attributes()`

4. **Attribute clamp ranges**: See **Attribute_Clamp_System.md** for absolute min/max clamp values for all player and team attributes.

## System Flow

1. **Team Object Creation**: Attributes copied from universal `teams` collection
2. **Missing Attributes**: Initialized from universal collection or generated randomly
3. **Attribute Updates**: Training updates these team measures in Franchise/Tournament. In **franchise** mode, **end-of-game (EOG)** also adjusts the same FTD team fields from game output via `update_team_attributes_after_game` (see `End_Of_Game_System.md`).
4. **Persistence**: Changes saved to the appropriate document for the game mode.
5. **Play CMD (franchise):** The scalar list in this doc is not play effectiveness. That same EOG hook applies FTD **offensive** `plays.*.effectiveness` decay when **`4 * usage_int < success_rate_pct`** (`usage_int` from `times_run` share vs team total, `success_rate_pct` from `game_stats.successes` / `times_run`; see `End_Of_Game_System.md`), and FTD **`scouting_data.defense.*.effectiveness`** decay from each game’s defensive playcall **`used`** share (integer percent of team defensive calls). Training no longer applies random pre-training defense decay (`Training_System.md`).

## Long Form Documentation

### Overview

The Team Attribute Management System handles the initialization, storage, and updates of team attributes across all game modes. Team attributes control various aspects of team performance, including shooting tendencies, defensive capabilities, fast break efficiency, and team chemistry.

**Location:** `BackEnd/models/team_manager.py`, `BackEnd/api/gameplan_routes.py`  
**Status:** ✅ Fully implemented for all game modes  
**Key Function:** `TeamManager.init_team_attributes(mode)`

### Attribute List

All team attributes are stored in team objects across all game modes:

**Core Attributes:**
- `shot_threshold` - Shot attempt threshold (range: −30 to 170, center at 70 for pill display; see [Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md))
- `discipline` - Turnover modifier (formerly `turnover_modifier`)
- `fight` - Foul modifier (formerly `foul_modifier`)
- `rebound_modifier` - Rebound effectiveness modifier (range: 0.0-1.0, center at 0.5 for pill display)
- `offensive_efficiency` - Offensive efficiency rating
- `team_chemistry` - Team chemistry rating

**Additional Attributes (January 2025):**
- `defensive_efficiency` - Defensive efficiency rating
- `fb_efficiency` - Fast break efficiency rating
- `pt_efficiency` - Press/Trap efficiency rating
- `fb_opp_modifier` - Fast break opponent modifier
- `pt_opp_modifier` - Press/Trap opponent modifier

**Note:** `momentum_score` is not set in `TeamManager.init_team_attributes()` for single/tournament mode. In **franchise mode**, season init sets it to **0** via `franchise_manager.py`; the deferred compatibility update after full CPU games is described in § Momentum below.

### Default Values

**Mode-Specific Initialization:**

**Single Game & Tournament Mode:**
- Attribute range: `random.randint(-10, 10)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `shot_threshold`: `random.randint(0, 200)` (from `TEAM_ATTR_RANGES`; see [Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md))
- `team_chemistry`: `random.randint(7, 25)`
- `rebound_modifier`: `random.randint(0, 40) / 100.0` (random 0.0-0.4 in 0.01 increments)

**Franchise Mode (creation):**
- Attribute range: `random.randint(-2, 0)` for:
  - `discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`
- `shot_threshold`: `random.randint(65, 75)` (MID ± 5; see [Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md))
- `team_chemistry`: `random.randint(8, 11)` — **8, not 7**: the clamp FLOOR is 7, so a team rolled at 7 starts pinned and cannot register a loss until it first wins. 21% of the league began on the floor before this change.
- `rebound_modifier`: `0.5` (fixed — the MIDPOINT of the 0.0-1.0 clamp, giving symmetric headroom. At 0.2 with the old EOG ladder, 93 of 128 teams hit 0.0 by week 3.)

**Franchise Mode (season rollover):** see § Season Rollover Re-Roll — team_attributes do **not** carry over; the 8 core attrs re-roll on a carryover-scaled range, other fields re-init like creation.

**New Attributes**: All default to `0` if not present in the universal collection.

### Season Rollover Re-Roll

When an existing franchise advances to a new season, `finish_season` (`BackEnd/api/franchise_routes.py`) **re-rolls** each team's `team_attributes` — nothing carries over. Implemented by `TeamManager.init_franchise_rollover_team_attributes(carryover_count)` (`team_manager.py`).

- **Non-core fields** re-init exactly like franchise creation: `shot_threshold` `randint(65,75)`, `rebound_modifier` `0.5`, `team_chemistry` `randint(8,11)`, `momentum_score`/`distant_win_streak`/`distant_loss_streak` `0`.
- **The 8 core attrs** (`discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`) re-roll with `randint(lo, hi)` where `(lo,hi)` is scaled by **carryover count**.

**Carryover count** = returning players from the prior season (active roster **+** training/practice squad, graduating seniors excluded), counted **before** this season's signed recruits are added. Source: `len(returning_players_by_team[team_id])`.

| Carryover players | Core-attr range | Bias |
|-------------------|-----------------|------|
| **≥ 10**          | `-1 to 2`       | strong continuity |
| **7 – 9**         | `-2 to 1`       | moderate turnover |
| **< 7**           | `-3 to 0`       | heavy turnover |

Boundary: exactly **10 → top bucket** (`>= 10`). Range logic lives in `TeamManager.rollover_core_attr_range()`.

### Attribute Initialization

**Initialization Flow:**

1. **First Access**: Team attributes are copied from the **universal `teams` collection** in MongoDB (the core/master team data)
2. **Missing Attributes**: If attributes don't exist in team object, they're initialized from the **universal `teams` collection**
3. **Fallback**: If the **universal `teams` collection** doesn't have attributes, `TeamManager.init_team_attributes(mode)` generates random values based on the game mode

**Implementation:**
- **Location**: `BackEnd/models/team_manager.py` - `init_team_attributes()` (~L463)
- **Method**: Static method that accepts `mode` parameter ("single", "tournament", or "franchise")
- **Returns**: Dictionary of team attributes with mode-specific randomization

### Universal Teams Collection

The **universal `teams` collection** in MongoDB (`db.teams`) is the source of truth for initial team attribute values. This collection contains the master/base team data that is copied when team objects are first created in any game mode. It stores:

- Team metadata (name, colors, mascot, team_id)
- Base team attributes (`shot_threshold`, `discipline`, `fight`, `rebound_modifier`, `offensive_efficiency`, `team_chemistry`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`)
- Coaching attributes object (effectiveness, training focus list, archetype scores and momentum)
- Initial playbook and strategy settings (if any)

When team objects are created in Single Game, Tournament, or Franchise modes, they copy attribute values from this universal collection. If attributes don't exist in the universal collection, they default to `0` (for new attributes) or are generated randomly (for core attributes via `init_team_attributes()`).

### Attribute Updates

**Training System:**
- **Franchise Mode**: Team attributes can be updated through training
  - **Location**: `BackEnd/api/franchise_routes.py` - `run_franchise_training()` (~L10536)
  - **Process**: Training changes are saved to `franchises.{franchise_id}.franchise_teams.{team_id}.{attribute_name}`
  - **Example**: `franchises.{franchise_id}.franchise_teams.{team_id}.defensive_efficiency = new_value`
- **Tournament Mode**: Team attributes can be updated through training (future implementation)
- **Single Game Mode**: Team attributes are not updated during gameplay (training not implemented)

**Gameplay:**
- Team attributes are read-only during gameplay (not modified by game events)
- Attributes are used in calculations but remain constant throughout a game

**Persistence:**
- Changes persist to the appropriate document based on game mode:
  - **Single Game**: `games.{game_id}.teams.{team_id}`
  - **Tournament**: `tournaments.{tournament_id}.teams.{team_id}`
  - **Franchise**: `franchises.{franchise_id}.franchise_teams.{team_id}`

### EOG / Training Changes

Franchise FTD team attributes update in two places: **EOG** (`update_team_attributes_after_game` in `franchise_routes.py`) and **training** (`training_execution_v2.apply_training_points`). Below, **up / down** mean the signed change added to the stored value (then clamped). Exception: **`shot_threshold` is a golf score** — **down** is *better* shooting discipline, **up** is *worse*.

#### End of game (EOG)

| Attribute | Direction | Rule (after clamp) |
|-----------|-----------|---------------------|
| **Offensive efficiency** | Concentration | Largest play's share of offensive possessions: `≤0.23` → **+0…+2**; `≤0.30` → **−1…+1**; `>0.30` → **−2…−1**. Zero possessions = data-integrity (log, no change). |
| **Defensive efficiency** | Concentration | Max HCO-defense usage share: `≤0.42` → **+0…+2**; `≤0.57` → **−1…+1**; `>0.57` → **−2…−1**. |
| **Fast break efficiency** | Concentration | Over CR / RR / Triangle (`after_steal` excluded): `≤0.44` → **+0…+2**; `≤0.53` → **−1…+1**; `>0.53` → **−2…−1**. Zero FB volume → atrophy **−1…0**. |
| **Press/trap efficiency** | Concentration | Over the 4 P/T plays: `≤0.50` → **+0…+2**; `≤0.70` → **−1…+1**; `>0.70` → **−2…−1**. Zero P/T volume → atrophy **−1…0**. |
| **Fast break opp. modifier** | Volume ladder | Opponent FB volume, healthy **7–13**: `0` atrophy **−1…0**; `<7` **−1…0**; `7–13` **0…+1**; `>13` **−1…0**. |
| **PT opp. modifier** | Volume ladder | Opponent P/T volume, healthy **9–20** (bimodal — press teams median 15, others 4–6). Same ladder shape. |
| **Fight** | **Up** if win (**0…+2**); **down** if lose (**−2…0**) | Margin does not change fight; only W/L. **Nets structurally zero league-wide** — one winner per game — so fight's season drift is entirely training-driven. |
| **Discipline** | Buffered comparison | **+1…+2** if your **F + TO** < opponent **F + TO + 8**; **−3…−1** if higher; **−1…0** if equal. |
| **Team chemistry** | Rank-relative | Beat lower-ranked **0…+2**; beat higher non-top-10 **+1…+3**; beat top-10 **+2…+5**. Lose to top-10 **0…+1**; lose to higher non-top-10 **−1…+1**; lose to rank 100-128 **−4…−2**; lose to other lower **−2…−1**. Lifted across the board — the old ladder floored **all 128 teams by week 2**. |
| **Shot threshold** | Golf score | **FG% > 40** → **−6…−2** both. **FG% > 26 and ≤ 40** → winner **−1…0**, loser **0…+1**. **FG% ≤ 26** → **+2…+6** both. ⚠️ **SCALE-COUPLED** — valid only for the current −30…170 window; every `MIN` change requires a re-cut. |
| **Rebound modifier** | 5-band ladder (cents /100) | Outrebound by **≥14** → **+0.04…+0.14**; **7–13** → **0.00…+0.06**; **−3…+6** → **−0.03…+0.03**; outrebounded **4–13** → **−0.08…−0.02**; **≥14** → **−0.12…−0.04**. Asymmetric on purpose: rebound differential is zero-sum, so symmetric bands net zero drift. |

Full band definitions, thresholds and the reasoning behind each re-cut live in
[End_Of_Game_System.md](../06_Gameplay_Systems/End_Of_Game_System.md). All values are named
constants in `BackEnd/constants/eog_attr_bands.py` — **never inline a threshold in a branch**.

**Evaluate band changes with `scripts/eog_band_tuner.py`, not a season.** It recomputes expected
drift offline from a season log in seconds and validates itself against the log (must be 100%).

#### Training

**Install-driven attrs** (`offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `fb_opp_modifier`, `pt_efficiency`, `pt_opp_modifier`): each session uses that line’s **install points** (0–5). Random delta by bucket — **0 → −2…−1**; **1 → 0…+1**; **2 → +1…+3**; **3 → +2…+3**; **4 → +2…+4**; **5 → +2…+5**. Matching **Systems Coach** focus **multiplies positive deltas only** (×1.5–1.8 rounded down).

| Attribute | Direction | Rule |
|-----------|-----------|------|
| **Fight** | **Up, down, or mixed** by bucket | Effective points = **0.5× strength + 0.5× conditioning** (half-up) → bucket **0…5** random delta: **0 → −4…−3**; **1 → −1…+1**; **2 → 0…+2**; **3 → +1…+3**; **4 → +2…+4**; **5 → +3…+5**. **Culture Builder** (Inspire / Confidence / Community Engagement; not **Team Building**): **+1…+2** once. **Authoritarian** except **Rebounding**: **−2…−1** once. **Authoritarian–Discipline** focus: multiplies **positive** fight deltas. **Breaks 3:** fight **−1…0**; **breaks 4:** **−2…−1**; **breaks 5+:** **−3…−1**. |
| **Discipline** | **Up, down, or mixed** by bucket | Effective points = **0.25×** (inside + outside defense + passing + ball handling), half-up → **same bucket table as Fight**. **Authoritarian** (Discipline / Rebounding / Execution; not **Teamwork**): **+1…+2** once. **Culture Builder** except **Confidence**: **−2…−1** once. **Authoritarian–Discipline** focus: multiplies **positive** discipline deltas. **Breaks 3:** discipline **−1…0**; **breaks 4:** **−2…−1**; **breaks 5+:** **−3…−1**. |
| **Team chemistry** | **Down** at 0 pts mix; **up** at 1+ | Chemistry-weighted sum: **free throws ×0.25 + film ×0.25 + scrimmages ×0.25**, rounded half-up → bucket: **0 → −3…−1**; **1 → 0…+1**; **2 → +1…+2**; **3 → +2…+3**; **4 → +2…+4**; **5 → +2…+5**. **Team Building** focus: **+1…+3** once. **Authoritarian–Teamwork** focus: **0…+1** once. **Culture Builder–Inspire:** multiplies **positive** chemistry deltas. **Breaks 3:** **−1…+1**; **breaks 4:** **−2…+1**; **breaks 5+:** **−3…+1**. |
| **Shot threshold** | Scrimmages only | **0 pts → up +5…+15** (worse). **1 → up/flat 0…+5**. **2 → down −3…−8**; **3 → −5…−11**; **4 → −5…−15**; **5+ → −5…−20** (larger scrimmage = more **down** = better golf score). **Breaks** can scale how much of a **session “gain”** sticks (for shot threshold, a **decrease** counts as a gain). |
| **Rebound modifier** | **Up or down** | **Rebounding drill and scrimmages:** half-up(**0.5 × points**) then same bucket table: **<1 effective point → −0.05…−0.03**; **1–2 → −0.03…+0.03**; **3–4 → +0.03…+0.05**; **5+ → +0.03…+0.10**. **Authoritarian–Rebounding** / focus match can **amplify positive** rebound bumps. |

#### ⚠️ Neglect decay is PROBABILITY-GATED (leveling pass, August 2026)

Point-bucket **0** means the coach allocated **nothing** to the categories feeding that
attribute. That still costs something — but it used to cost it **every single week**, at
`−4…−3` for fight/discipline and `−3…−1` for chemistry.

Because the CPU reference plan is a player-development plan, it allocates nothing to the
chemistry and discipline categories, so those attributes decayed **~−3.5/week indefinitely**:
measured **team_chemistry −93.6/season** on an 18-point range and **discipline −91.6** on a
40-point range. Every team floored, and a floored attribute carries no information.

Per-roll intuition is misleading here: these attributes are rolled **~4.7x per week** across
their several source categories, so both penalties and gains multiply. Chemistry's bucket 1 at
`(0,1)` alone was worth **+32/season**.

| constant | value | effect |
|---|---|---|
| bucket-0 range | `(−1, 0)` | was `(−4,−3)` / `(−3,−1)` |
| `NEGLECT_DECAY_CHANCE_CHEMISTRY` | `0.10` | ≈ −3/season |
| `NEGLECT_DECAY_CHANCE_DEFAULT` | `0.25` | ≈ −7/season |
| `FIGHT_GAIN_CHANCE` | `0.45` | gates POSITIVE fight deltas — fight never hits bucket 0, and its gains multiplied to +44/season |
| chemistry bucket 1 | `(−1, 1)` | one point holds station; chemistry must be invested in to grow |

Integer weekly rolls cannot express "−3/season" directly — the smallest ungated penalty is
already −13 — which is why these are probability gates rather than smaller ranges.

**Measured after gating** (12 seeds × 64 teams, all attributes reset to mid-range first):
team_chemistry **−5.3**, discipline **−6.0**, fight **+3.3**, everything else +7.1…+7.9.

**Breaks (training, all attrs above):** **0–2** mostly changes a **multiplier** on **positive** session gains (player attrs + team attrs; for **shot_threshold**, a **decrease** is treated as a positive gain). **3+** adds the **team chemistry** random shifts in the table; **4–5** also applies the **discipline** and **fight** **down** ranges in the Fight/Discipline rows.

### Season drift — the two forces, and what actually happens

Every team attribute is pushed by **two independent forces** each week: **EOG** (game outcomes)
and **TRAINING** (the coach's allocation). What matters is the **combined** figure, and the
design target is **slightly positive** — a default coach drifts up a little, neglect falls,
focus climbs.

**THE THEME: railing stays possible, it just isn't the default.** An attribute that can never
reach its clamp cannot express a great or terrible season. Before the leveling pass the league
railed by construction — 123 of 128 teams pinned `shot_threshold` at the ceiling, all 128
floored `team_chemistry` by week 2. After it, rails are reachable by outliers and unreachable by
accident.

**Verified over a full 26-week season under the new configuration** (128 teams, mean start →
mean end):

| attribute | predicted | **actual** | prior season |
|---|---|---|---|
| fb_opp_modifier | +7.2 | **+7.3** | +5.6 |
| team_chemistry | +5.7 | **+8.0** | +0.5 |
| pt_opp_modifier | +3.7 | **+4.8** | +3.6 |
| fight | +3.3 | **+4.4** | +16.6 |
| offensive_efficiency | +3.5 | **+3.5** | +10.8 |
| discipline | +3.9 | **+3.4** | −12.9 |
| pt_efficiency | +4.7 | **+3.1** | −1.1 |
| fb_efficiency | +1.8 | **+2.9** | −1.3 |
| defensive_efficiency | +3.3 | **+2.7** | −8.3 |
| rebound_modifier | +0.1 | **−0.0** | +0.1 |

**Ten of eleven predictions landed.** Total railed team-attributes fell **457 → 326**, and the
mean clamp rate **15.1% → 6.2%**.

`shot_threshold` is the exception and has its own dynamics — see the golf-score row above and
[Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md).

⚠️ **This season did NOT test forced specialisation.** The CPU reference plan is uniform across
all 127 CPU teams and vision-driven training allocation is still deferred, so team-attribute
drills are identical league-wide. **"Does neglect decay while investment holds" remains
unmeasured** — a flat specialisation result would be expected, not evidence of failure. The
neglect gates above are calibrated for the neglect case only.

### ⚠️ Traps that have already cost days

| trap | what happens |
|---|---|
| **The training column is CENSORED for clamped attributes** | The `[EOG-BAND]` report infers training drift from unclamped week-to-week `pre`→`post` gaps, so for an attribute pressed against a clamp it measures only the SURVIVORS — the teams that have not yet railed, i.e. those with the smallest deltas. Measured gap: team_chemistry **−93.6 true vs −10.2 inferred (9.2x)**; discipline −91.6 vs −48.1. Unconstrained attributes agreed within 10%. **Source training numbers from a direct mid-range dry run of `auto_train_one_cpu_team`, never from the report.** |
| **`shot_threshold` determines its own band input** | It is the bar a shot must clear, so it sets FG%, and FG% picks the band. Its equilibrium is **season- and scale-specific** — re-derive before re-cutting, never reuse a prior fit. |
| **Gain vs position** | **Gain sets SPEED; band position sets WHERE TEAMS SETTLE.** The neutral band must sit BELOW the equilibrium FG% so the negative branch offsets training. |
| **UI-created franchises carry DEPLOYED init values** | A franchise created through the UI is seeded by the deployed backend, then measured by local code. Anything changed since the last deploy seeds wrong, silently, and looks like data rather than an error. Caught once on `rebound_modifier` (0.2 vs 0.5) only because someone was looking for it. |
| **`eog_band_tuner --validate` needs `--config`** | There are now three band generations. Validating a log against the wrong one reports mass "drift" that is really a config mismatch — one log scored 8 of 11 attributes as mismatched against the default, and 11 of 11 clean against its own config. |
| **The rebuild-timeline metric halved star minutes** | Bucketing lineup rebuilds by `(game_id, team_name)` from a module-level context dict produced 40.5% star minutes when the true value was 69.0%, and ~14 players from a 12-man roster. Measure per TURN from the live lineup instead. See [CPU_Team_Rotation_System.md](../06_Gameplay_Systems/CPU_Team_Rotation_System.md). |

### Attribute Name Migration

**Historical Note:**
- `turnover_modifier` was renamed to `discipline` (January 2025)
- `foul_modifier` was renamed to `fight` (January 2025)
- A migration script (`scripts/migrate_foul_turnover_to_aggression_discipline.py`) was used to update existing database documents

### Key Files

- `BackEnd/models/team_manager.py` - `init_team_attributes()` (~L463)
  - Static method for initializing team attributes with mode-specific ranges
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (~L993)
  - Creates team objects and initializes attributes from universal collection
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (~L575)
  - Loads team attributes from mode-specific documents
- `BackEnd/api/franchise_routes.py` - `run_franchise_training()` (~L10536)
  - Updates team attributes through training system
- `BackEnd/models/training_execution_v2.py` - `_apply_team_training_points()` (~L1305)
  - Applies training point allocations to team attributes

**Team Attribute Faucets & Sinks**

**Notes**
- **Initial seed:** Included below for completeness. It sets the franchise starting baseline, but is not a progression faucet/sink after the team already exists.
- **Training amplifiers:** Matching coaching focus can amplify positive training gains. `breaks` can also multiply positive session gains; it directly adds extra changes to `team_chemistry`, `discipline`, and `fight` at 3+ points.
- **CPU teams:** When the user runs training, eligible non-user teams run the shared `execute_training` engine with generated allocations and coaching focus. Per-team retries are guarded by `cpu_autotrain_week`.

### Shooting (`shot_threshold`) (range: −30 to 170)

This is the team's intangible mindset to convert baskets. Their overall belief in their identity as a basketball team who scores points. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

**Scale reference (−30–170, MID 70):** To change the scale, see **[Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md)** (agent workflow + manual checklist).

| Area | Current value |
|------|---------------|
| Team attribute clamp (`TEAM_ATTR_RANGES`) | **−30 – 170** |
| Franchise init | **65 – 75** (MID ± 5) |
| Tournament seeds | 1: **0–100** · 2–4: **0–150** · 5–7: **50–200** · 8: **100–200** |
| Score balancing (one turn) | Trailing **−20**, leading **180** (`MIN−20` / `MAX−20`) |
| Rim-runner corner FB | **180 − fb_efficiency** |
| FTE tutorial | User **0**, computer **100** |
| UI pills | Center **100**, span **0–200** → FCC, training report, tournament, court, box score |

- Initial seed: Franchise creation / missing-FTD creation (`range: 80 to 90`, random). Season rollover re-inits identically (does not carry over).
- Faucet: Training System / Scrimmages.
  Condition: `scrimmages` slider at `0`.
  Range: `0 pts -> +5 to +15` (worse shooting attribute).
- Faucet / slight sink: Training System / Scrimmages.
  Condition: `scrimmages` at `1` pt.
  Range: `+= random.randint(0, 5)` (neutral to slight worsening).
- Sink: Training System / Scrimmages.
  Condition: `scrimmages` at `2+` pts.
  Range: `2 pts -> -3 to -8`, `3 pts -> -5 to -11`, `4 pts -> -5 to -15`, `5+ pts -> -5 to -20`.
- Faucet: End Of Game System.
  Condition: team FG% `<= 45%`.
  Range: **both** teams `+5 to +10`.
- Mixed EOG: End Of Game System.
  Condition: team FG% `> 45%` and `≤ 50%`.
  Range: winner `+= random.randint(-5, 0)`; loser `+= random.randint(0, 5)`.
- Sink: End Of Game System.
  Condition: team FG% `> 50%`.
  Range: **both** teams `+= random.randint(-10, -5)`.

**UI (Shooting pill and deltas):** Raw `shot_threshold` is a golf score (lower is better). Horizontal pills use **100** as center, **0** at the favorable end and **200** at the unfavorable end. Shared helpers: `FrontEnd/static/js/shared/teamShotThresholdScale.js`. **Training report** and **box score attribute-change** copy invert the numeric delta for display: a raw **−10** shows as **+10** in green; a raw **+5** shows as **−5** in red. See **[Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md)**.

### Rebounding (`rebound_modifier`) (range: 0.0 to 1.0)
This is the team's intangible mindset when it comes to rebounding. Their overall belief in their identity as a basketball team who gets more rebounds than their opponent. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Live rebound impact: each eligible player's rebound score receives
  `REBOUND_TEAM_CHEMISTRY_FACTOR (0.5) × team_chemistry × rebound_modifier`
  before geography, offensive-rebound, and shooter/putback discounts. See
  [Rebound_System.md](../06_Gameplay_Systems/Rebound_System.md) for the full winner-selection flow.
- Initial seed: Franchise creation / missing-FTD creation (`0.2` fixed). Season rollover re-inits identically (does not carry over).
- Faucet: Training System / Rebounding drill.
  Condition: `rebounding` slider contributes rounded effective points.
  Range: `<1 effective pt -> -0.05 to -0.03`, `1-2 -> -0.03 to +0.03`, `3-4 -> +0.03 to +0.05`, `5+ -> +0.03 to +0.10`.
- Faucet + Sink: Training System / Scrimmages.
  Condition: scrimmages contributes rounded effective points.
  Range: `<1 effective pt -> -0.05 to -0.03`, `1-2 -> -0.03 to +0.03`, `3-4 -> +0.03 to +0.05`, `5+ -> +0.03 to +0.10`.
- Faucet + Sink: End Of Game System.
  Condition: compare team TREB to opponent TREB.
  <!-- Range: `> opp + 5 -> +0.00 to +0.10`, `< opp - 5 -> -0.10 to +0.00`, otherwise `-0.05 to +0.05`. -->
  Range: `> opp + 8 -> +0.00 to +0.05`, `< opp - 8 -> -0.10 to -0.05`, otherwise `-0.05 to -0.01`.

### Offense Efficiency (`offensive_efficiency`) (range: -20 to 20)
This is how well your team executes the Xs & Os of your offense — running plays, setting screens, making reads, and getting open. This affects how cleanly your offense operates as a unit, independent of raw talent. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through diverse play-calling and offense-focused training activities.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet + Sink: Training System / Offense Install.
  Condition: offense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> 0 to +1`, `2 -> +1 to +3`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`.
- Sink: End Of Game System.
  Condition: every completed franchise game; sum of offensive `times_run` across playbook rows.
  If total > 12: Range: `0 to +1`
  Elif total > 10 (i.e. 11–12): Range: `-1 to 0`
  Else (≤ 10): Range: `-2 to -1`

### Defense Efficiency (`defensive_efficiency`) (range: -20 to 20)
This is how well your team executes the Xs & Os of your defense — rotating on time, closing out, communicating switches, and making life difficult for the offense. Raw athleticism only takes you so far; this is what separates a disciplined unit from a collection of individuals. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through diverse play-calling and defense-focused training activities.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet + Sink: Training System / Defense Install.
  Condition: defense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> 0 to +1`, `2 -> +1 to +3`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`.
- Sink: End Of Game System.
  Condition: every completed franchise game; max HCO defense `used` share among `man` / `2-3-zone` / `3-2-zone` / `1-3-1-zone`.
  If max share ≤ 39%: Range: `0 to +1`
  Elif max share ≤ 49%: Range: `-1 to 0`
  Else (> 49%): Range: `-2 to -1`

### Fast Break Efficiency (`fb_efficiency`) (range: -20 to 20)
This is how well your team executes in transition — pushing the pace, hitting the right moments to run, and converting opportunities before the defense can set up. This affects both how often your team generates fast break chances and how effectively they finish them. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed fast break install, a balanced Fast Break playbook and dedicated fast break training activities.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet + Sink: Training System / Fast Break Offense Install.
  Condition: fast-break offense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> 0 to +1`, `2 -> +1 to +3`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`.
- Sink: End of Game System
  Condition: every completed franchise game
  If any one Fast Break Play > 60% of Fast Break tries: Range: `-2 to -1`
  Elif any one Fast Break Play > 50%: Range: `-1 to 0`
  Else: Range: `0 to +1`

### Press/Trap Break Efficiency (`pt_efficiency`) (range: -20 to 20)
This is how well your team executes full court presses and half court traps — timing the traps, cutting off passing lanes, and turning defensive pressure into live ball turnovers. This affects both how often your team disrupts the opponent's offense and how effectively they convert that pressure into scoring opportunities. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed press/trap install, a disciplined approach to how often you deploy it, and dedicated press/trap training activities.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet + Sink: Training System / P/T Defense Install.
  Condition: press/trap defense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> 0 to +1`, `2 -> +1 to +3`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`.
- Sink: End of Game System
  Condition: every completed franchise game; team HCT + FCP uses.
  If total > 20: Range: `-2 to -1`
  Elif total > 16: Range: `-1 to 0`
  Else: Range: `0 to +1`

### Fight (`fight`) (range: -20 to 20)
Represents your team’s competitive edge. High Fight teams have great resilience, they handle adverse situations well, and perform with urgency when trailing. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet: Training System / Strength + Conditioning.
  Condition: strength and conditioning contribute positive rounded effective points.
  Range (shared fight/discipline bucket table after 0.5× accrual rounds): `0 -> -4 to -3`, `1 -> -1 to +1`, `2 -> 0 to +2`, `3 -> +1 to +3`, `4 -> +2 to +4`, `5+ -> +3 to +5`.
- Sink: Training System / Breaks.
  Condition: `breaks` slider at `3+`.
  Range: `3 pts -> -1 to 0`, `4 pts -> -2 to -1`, `5+ pts -> -3 to -1`.
- Faucet: Training System / Coaching Focus
  If the user chooses **Culture Builder** — **Inspire**, **Confidence**, or **Community Engagement** (not **Team Building**): Range: `+1 to +2`
- Sink: Training System / Coaching Focus
  If the user chooses **Authoritarian** except **Rebounding**: Range: `-2 to -1`
- Faucet: End Of Game System.
  Condition: team won the game.
  Range: `0 to +2`.
- Sink: End Of Game System.
  Condition: team lost the game.
  Range: `-2 to 0`.

### Discipline (`discipline`) (range: -20 to 20)
Reflects polish and control. Disciplined teams commit fewer unnecessary fouls and turnovers, execute aggressive strategies with precision, and maintain composure late in games. It balances Fight very well — aggression without structure becomes chaos. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet: Training System / Inside Defense, Outside Defense, Passing, Ball Handling.
  Condition: those drills contribute positive rounded effective points (0.25× per drill point, summed, half-up).
  Range: same bucket table as **Fight** after rounding: `0 -> -4 to -3`, `1 -> -1 to +1`, `2 -> 0 to +2`, `3 -> +1 to +3`, `4 -> +2 to +4`, `5+ -> +3 to +5`.
- Sink: Training System / Breaks.
  Condition: `breaks` slider at `3+`.
  Range: `3 pts -> -1 to 0`, `4 pts -> -2 to -1`, `5+ pts -> -3 to -1`.
- Faucet: Training System / Coaching Focus
  If the user chooses **Authoritarian** — **Discipline**, **Rebounding**, or **Execution** (not **Teamwork**): Range: `+1 to +2`
- Sink: Training System / Coaching Focus
  If the user chooses **Culture Builder** except **Confidence**: Range: `-2 to -1`
- Faucet: End Of Game System.
  Condition: team `(F + TO)` is lower than opponent `(F + TO)` + 8.
  Range: `+1 to +2`.
- Sink: End Of Game System.
  Condition: team `(F + TO)` is greater than opponent `(F + TO)` + 8.
  Range: `-2 to -1`.
- Else (tie vs buffered opponent total): Range: `-1 to 0`

### Momentum (`momentum_score`) (range: -10 to 10)

- Initial seed: Franchise creation **and** season rollover both set **`0`** (rollover reset now implemented in `finish_season` via `init_franchise_rollover_team_attributes`).
- **Deferred compatibility behavior:** regular-season full CPU games update it through `_persist_legacy_season_momentum_updates()` in `franchise_routes.py`; the unchanged calculation lives in `BackEnd/utils/season_momentum.py`.
  - **Win:** `+1.5 × chemistry_scale` (+ `+0.5 × (win_streak − 2)` when streak ≥ 3 after the win).
  - **Loss:** `−0.8 × chemistry_scale` (+ extra **−2.0** when loss ends a win streak ≥ 3).
  - `chemistry_scale = max(1.0, team_chemistry / 10)`.
- It is output-only and does not affect the full simulation engine.
- Companion legacy fields (not UI attrs): `distant_win_streak`, `distant_loss_streak` on FTD `team_attributes`; reset to **0** at franchise creation and at season rollover. Their removal is deliberately deferred until the EOG attribute retune.
- Training and EOG flows do **not** update `momentum_score`.

### Team Chemistry (`team_chemistry`) (range: 7 to 25)
The connective tissue of your roster. Chemistry influences how well players support one another through mistakes, adversity, and high-pressure moments. Winning strengthens it. Internal friction and extended losing can strain it. You may not see the impact of this attribute directly — but you will definitely feel it. This is a compounding attribute, it compounds both upward and downward, based on the team's in-game performance and training activities.

- Initial seed: Franchise creation / missing-FTD creation (`range: 7 to 10`, random). Season rollover re-inits identically (does not carry over).
- Faucet: Training System / Free Throws, Film Study, Scrimmages.
  Condition: those drills contribute positive rounded effective points.
  Range: chemistry training range after rounding: `0 -> -3 to -1`, `1 -> 0 to +1`, `2 -> +1 to +2`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`.
- Faucet + Sink: Training System / Breaks.
  Condition: `breaks` slider at `3+`.
  Range: `3 pts -> -1 to +1`, `4 pts -> -2 to +1`, `5+ pts -> -3 to +1`.
- Faucet: Training System / Team Building.
  Condition: coaching focus = `culture-builder-teamwork`.
  Range: `+1 to +3`.
- Faucet: Training System / Authoritarian Teamwork.
  Condition: coaching focus = `authoritarian-teamwork`.
  Range: `0 to +1`.
- Faucet + Sink: End Of Game System.
  Condition: rank-relative result using `natl_rank` (lower integer is better; missing rank = 999).
  Range: beat lower-ranked `0 to +1`; beat higher-ranked non-top-10 `+1 to +2`; beat top-10 `+2 to +4`; lose to top-10 `-1 to 0`; lose to higher-ranked non-top-10 `-2 to 0`; lose to lower-ranked 100-128 `-5 to -3`; lose to other lower-ranked `-3 to -2`.

### FB Opp Modifier (`fb_opp_modifier`) (range: -20 to 20)
This is how well your team defends fast breaks and transition offenses. Containing the pace, cutting off passing lanes, and not allowing easy transition buckets. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed Fast Break Defense install and film study of your opponent.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet + Sink: Training System / Fast Break Defense Install.
  Condition: fast-break defense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> 0 to +1`, `2 -> +1 to +3`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`.
- Sink: End of Game System
  Condition: every completed franchise game; opponent fast-break try total.
  If opponent tries > 15: Range: `-2 to -1`
  Elif opponent tries > 10: Range: `-1 to 0`
  Else: Range: `0 to +1`

### P/T Opp Modifier (`pt_opp_modifier`) (range: -20 to 20)
This is how well your team and work through your opponent's presses and traps. Handling the pressure of these disruptive defenses is key to avoiding the many mistakes they can cause. This is a trained attribute. It naturally decays over time as opponents study your game film and adjust to your tendencies, but you can fight that decay — and push it higher — through a committed Press/Trap Offense install and film study of your opponent.

- Initial seed: Franchise creation / missing-FTD creation (`range: -2 to 0`, random). Season rollover re-rolls this on a carryover-scaled range (§ Season Rollover Re-Roll).
- Faucet + Sink: Training System / P/T Offense Install.
  Condition: press/trap offense install slider `0-5`.
  Range: `0 -> -2 to -1`, `1 -> 0 to +1`, `2 -> +1 to +3`, `3 -> +2 to +3`, `4 -> +2 to +4`, `5 -> +2 to +5`.
- Sink: End of Game System
  Condition: every completed franchise game; opponent HCT + FCP uses.
  If opponent uses > 16: Range: `-2 to -1`
  Elif opponent uses > 12: Range: `-1 to 0`
  Else: Range: `0 to +1`


**Team Attribute Impact on Gameplay**

1. Shot Threshold
- Determines the make/miss threshold for standard shot resolution.
- Impacts fast-break shot thresholds during fast-break scoring sequences.
- Impacts special late-game balancing shot-threshold overrides.
- Combines with Home Crowd shot-threshold adjustments.

2. Rebound Modifier
- Impacts offensive-rebound outcomes.
- Impacts defensive-rebound outcomes.
- Impacts rebound resolution after missed standard shots.
- Impacts rebound resolution after missed free throws.

3. Offense Efficiency
- Impacts half-court possession resolution on offense.
- Helps determine offensive execution advantage during standard possession play.

4. Defense Efficiency
- Impacts half-court possession resolution on defense.
- Helps determine defensive execution advantage during standard possession play.

5. Fast Break Efficiency
- Impacts fast-break offensive success.
- Impacts rim-runner fast-break outlet and conversion sequences.
- Impacts fast-break-specific shot-threshold overrides.

6. P/T Efficiency
- Impacts Full-Court Press defensive resolution.
- Impacts Half-Court Trap defensive resolution.
- Impacts defensive pressure success during press/trap gameplay events.

7. Fight
- Impacts offensive foul tendency.
- Impacts defensive foul tendency.
- Impacts turnover/foul calibration during possession resolution.
- Impacts late-game balancing behavior for trailing teams.
- Impacts fast-break shot-threshold adjustments against set defenders.
- Impacts Full-Court Press resolution.
- Impacts Half-Court Trap resolution.
- Impacts block-attempt checks in shot resolution.

8. Discipline
- Impacts steal and turnover calibration during possession resolution.
- Impacts dead-ball turnover calibration.
- Impacts shot-foul likelihood in shot resolution.
- Impacts late-game balancing behavior for leading teams.
- Impacts turnover checks during gameplay resolution.
- Impacts Full-Court Press resolution.
- Impacts Half-Court Trap resolution.
- Impacts violation / recalibration checks tied to offensive organization.
- Impacts charge resolution.

9. Momentum
- No current direct gameplay impact in the working code.

10. Team Chemistry
- Impacts fast-break shot-threshold adjustments against set defenders.
- Impacts Full-Court Press resolution.
- Impacts Half-Court Trap resolution.
- Impacts charge resolution.
- Impacts lineup auto-selection / autoset-lineup pool behavior.
- Impacts Home Crowd strength bands through the Home Crowd system.

11. FB Opp Modifier
- Impacts fast-break defensive success.
- Impacts rim-runner fast-break outlet and conversion defense.

12. P/T Opp Modifier
- Impacts Full-Court Press offensive resistance.
- Impacts Half-Court Trap offensive resistance.
- Impacts offensive resistance to press/trap pressure during gameplay events.
