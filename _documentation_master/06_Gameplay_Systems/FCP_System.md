## Full Court Press (FCP) System

> **Doc status (June 2026):** This file is **mid-overhaul**. The **legacy** skeleton + BSM/DST resolution flow (sections through *Overview*) still describes the old path when `USE_DYNAMIC_FCP=False`. The **dynamic** spatial loop (`USE_DYNAMIC_FCP=True`, default) is documented in [**Dynamic FCP Engine — BH Read Logic**](#dynamic-fcp-engine--bh-read-logic-current) below and in [`Dynamic_FCP_Brief.md`](../projects/Dynamic_FCP_Brief.md). A full rewrite of this document is planned once FCP migration is complete.

> **Half Court Trap (HCT)** is documented separately in [`HCT_System.md`](./HCT_System.md). The live HCT path is **dynamic** (engine loop + UESS schema steps), not the skeleton/stopper system described below for legacy FCP. This file covers **FCP only** plus shared BIP/inbound conventions that apply to both pressure types.

**Legacy path only** — superseded by the dynamic engine when `USE_DYNAMIC_FCP=True`:

1. FCP Success Threshold: `offenseScore + BSM > defenseScore`
2. Dominant Success Threshold: `offenseScore - defenseScore > DST` — DST = **600 (FCP)** plus discipline-based chemistry adjustment (see step 5).
3. Success Result Weights: `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.4, 0.3]`
4. Failure Result Weights: `["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"]` with weights `[0.2, 0.5, 0.3]`
5. Turnover Type Weights: `["TRAVEL", "DOUBLE DRIBBLE", "BAD PASS"]` with weights `[0.6, 0.3, 0.1]`

**FCP Resolution Flow (10 Steps)**

1. **Apply Energy Decay**
   - Apply energy decay to all active players (offense and defense) via `apply_energy_decay()`

2. **Track Defensive Attempt Stat**
   - Increment `def_scouting["defense"]["FCP"]["used"]`

3. **Calculate Offense Score**
   - For each offensive player (PG, SG, SF): Calculate `(BH * 0.6 + AG * 0.2 + IQ * 0.2)`
   - PG gets 3x weight, SG/SF get 1x weight
   - Sum all player contributions, then multiply total by `random.randint(1, 6)`

4. **Calculate Defense Score**
   - For each defensive player (PG, SG, SF): Calculate `(OD * 0.4 + AG * 0.4 + IQ * 0.2)`
   - PG gets 3x weight, SG/SF get 1x weight
   - Sum all player contributions, then multiply total by `random.randint(1, 6)`

5. **Determine Outcome Type**
   - Calculate BSM (Base Success Modifier)
      - Starting FCP BSM = **400** + (10 × offense team's fight attribute value)
      - BSM += random.randint(1, offense team chemistry) × offense pt_opp_modifier if offense pt_opp_modifier > 0, else += random.randint(1, offense team chemistry)
      - BSM -= random.randint(1, defense team chemistry) × defense team pt_efficiency if defense team pt_efficiency > 0 else -= random.randint(1, defense team chemistry)
    - DST (Defense Safety Threshold) = **600** for FCP
      - DST += random.randint(1, defense team chemistry) × defense team discipline if defense team discipline > 0 else += random.randint(1, defense team chemistry)
   - **FCP Success**: `if (offenseScore + BSM) > defenseScore`
     - If `offenseScore - defenseScore > DST`: Weighted random `["D_FOUL", "HCO", "SHOT"]` with weights `[0.3, 0.4, 0.3]`
     - Otherwise: `"HCO"` (press break)
   - **FCP Failure**: Otherwise → Weighted random `["O_FOUL", "DEAD_BALL_TURNOVER", "STEAL"]` with weights `[0.2, 0.5, 0.3]`

6. **Handle SHOT Result (if applicable)**
   - Build shot roles: Passer (PG), Shooter (random PF or C), Defender (defensive PG)
   - Call `shot_manager.resolve_shot()` for full shot resolution
   - If MISS with shooting foul: Route to FREE_THROW
   - If MISS without foul: Route to HCO (track defensive success)
   - If MAKE: Route to BASELINE_INBOUND (pressure may apply again)
   - Get "shot" variant skeleton and generate animations
   - Track FCP stats for all players

7. **Handle Non-SHOT Results**
   - Get "base" variant skeleton (has step 0 with press break positions)
   - Apply stopper system (truncate and add stopper step if not HCO)
   - Determine ball handler from skeleton using `get_ball_handler_from_skeleton()`
   - Determine defender by position-matching to ball handler

8. **Process Specific Result Types**
   - **O_FOUL**: Select foul player using `select_foul_player()` (60% ball handler, 10% each other player), route to SIDE_INBOUND → HCO
   - **D_FOUL**: Bonus / double-bonus → FREE_THROW; else SIDE_INBOUND → HCO
   - **DEAD_BALL_TURNOVER**: Random turnover type, route to SIDE_INBOUND → HCO
   - **STEAL**: Check fast break chance, route to FAST_BREAK or HCO
   - **HCO**: Route to HCO (no possession change)

9. **Generate Animations**
   - Convert skeleton to animations via `animator.skeleton_to_animations()` or UESS `build_skeleton_animation_steps(..., turn_type="FCP")` when migrated

10. **Track Stats and Set Next Play**
    - Record FCP player stats for all players in active lineup
    - Track team-level defensive success (if applicable)
    - Set `next_play_type` and `offensive_state` for transition system

**Stopper System**

The stopper system truncates FCP **"base"** variant skeletons at strategic points to execute non-shot outcomes (fouls, turnovers, steals). Full spec: [`Stopper_System.md`](./Stopper_System.md).

- Applies to: `O_FOUL`, `D_FOUL`, `DEAD_BALL_TURNOVER`, `STEAL`
- Does NOT apply to: `SHOT` (full "shot" variant), `HCO` (full "base" variant)

**Clock start and inbound pass**

- Game and shot clocks start only after the inbound receiver has the ball (same as BIP→HCO and SIP).
- The inbound pass runs during BASELINE_INBOUND; FCP animates SF→PG inbound in `runInboundSetup()`.
- When FCP directly follows BIP, the backend skips leading inbound-equivalent skeleton steps so inbound is not doubled.
- See [`BIP_System.md`](./BIP_System.md) § "BASELINE_INBOUND → FCP".

**Canonical skeleton contract (authoring)**

- BIP owns inbound-pass animation.
- FCP skeletons: **step 0 only** = SF pass → PG receive at inbound spot; step 1+ = post-receive press flow.

---

### Overview

The **Full Court Press (FCP)** system handles full-court defensive pressure after made shots. It uses **skeleton-based** animations (MongoDB `fcp_skeletons`) plus the **stopper system** for non-shot outcomes.

**Key entry point:** `resolve_full_court_press_logic()` in `BackEnd/engine/phase_resolution.py`.

For **Half Court Trap**, see [`HCT_System.md`](./HCT_System.md) — dynamic engine, trap plays, no FCP-style BSM roll.

---

### Dynamic FCP Engine — BH Read Logic (current)

**Status:** Implemented (June 2026). Applies when `USE_DYNAMIC_FCP=True` (default in `BackEnd/engine/phase_resolution.py`).

**Entry points:** `compute_dynamic_fcp_turn()` → shared §4 loop in `compute_dynamic_hct_turn(..., turn_mode="fcp")` (`BackEnd/engine/dynamic_hct.py`). FCP does **not** fork read math into a separate module; it passes `fcp=True` into `_read_decision()`.

#### Read score

Each loop iteration rolls a fresh read for the ball handler:

```python
int(((IQ * 0.8) + (CH * 0.2)) * random.randint(1, 6))
```

(`_player_read()` in `dynamic_hct.py`.)

#### Attack / pass thresholds (shared with HCT)

| Context | High tier (attack gate) | Mid tier (pass gate) | Below mid |
|---------|-------------------------|----------------------|-----------|
| **Normal** — defender in range (`moment` ≠ `"none"`) | read ≥ **200** | read **> 120** | low-tier roll |
| **Broken** — no ahead defender in range (`moment == "none"`) | read ≥ **175** | read **> 110** | low-tier roll |

Moment detection uses `MOMENT_RANGE = 11` (same as HCT).

#### FCP-specific strong-handler gate

Press breaks favor **passing** unless the ball handler is an elite dribbler. FCP raises the bar for who counts as a “strong handler” who may **attack** on a high read:

| Constant | HCT | FCP |
|----------|-----|-----|
| Strong-handler sum | `BH + AG > 80` | `BH + AG > 130` |

**Strong handler** (above the active sum): high read → **attack**, mid read → **pass**.  
**Weak handler** (at or below the sum): mapping is **inverted** — high read → **pass**, mid read → **attack**.

Example: BH+AG = 120 is “strong” in HCT (attacks on read ≥ 200) but still “weak” in FCP (passes on read ≥ 200).

#### FCP-specific low-tier mix

When read ≤ the pass threshold, the BH does not hold automatically — a weighted roll picks the action:

| Mode | Hold | Pass | Attack |
|------|------|------|--------|
| HCT | 50% | 25% | 25% |
| **FCP** | **50%** | **35%** | **15%** |

Constants: `FCP_READ_STRONG_HANDLER_SUM`, `FCP_READ_LOW_TIER_CHOICES` in `dynamic_hct.py`.

#### Off-ball attack routing (current)

During **`hct_advance`** beats (after attack wins pressure), non-BH offenders route via `fcp_offball_attack.py`. Engagement / converge / hold / pass still use BIP setup hustle.

**Ball-progress tiers** (BH **x**, home orientation; away mirrored). Half-open partition — PF and C share the same boundary operators:

| Tier | BH progress x (home) | PG / SG / SF | PF | C |
|------|----------------------|--------------|----|---|
| **T1** | **x ≤ 34** | Release **x∈[46,53]**, **y ± 6** | Hold | Hold |
| **T2** | **34 < x ≤ 50** | Release (same) | Deep key (6 eu of x=47) | BH-half mid spots |
| **T3** | **50 < x ≤ 64** | Release (same) | key / midWings / wings | midLane + front half spots |
| **T4** | **x > 64** | Release until terminal | Same as T3 | Same as T3 |

Constants: `FCP_TIER1_MAX = 34`, `FCP_TIER2_MAX = 50`, `FCP_TIER3_MAX = 64`. Broken-trap drives flood all non-BH to ABA spots until cutoff **RETAIN** reverts to incremental tiers.

#### FCP Straight Pressure — PF/C zone & man release (current)

**Def PF/C** use a compressing front-court zone (not HCT `_pf_c_targets`):

| BH x (home) | Zone x | Zone y |
|-------------|--------|--------|
| < 36 | [50, 64] | 1–50 |
| 36–50 | [ball_x, min(ball_x+14, 64)] | 10–40 |
| 50–64 | [50, 64] | 10–40 |

Anchor ladder: midcourt → key → midLane → basketSpot by progress. Help/denial counts offenders inside the zone.

**Def SG/SF release:** when **BH x ≥ 64** (not when their man enters ABA). PG stays on ball. Module: `fcp_pf_c_zone.py`.

#### Post-read overrides (shared)

- **D21 — no live dribble:** any `attack` result collapses to `pass`.
- **Broken + attack:** runs the open-floor cutoff race (`_do_broken_hct_cutoff`) instead of a normal on-ball contest.
- **Straight Pressure FCP:** trap moments downgrade to single-defender `"pressure"` (man-glue); read thresholds unchanged.

#### Goal achievement at x > 64 (shared with HCT §7)

When the BH enters the Attack Basket Area (trap-break zone — **past x = 64**, y 10–40), a **separate** 3-tier read runs before the normal loop read — unchanged from HCT:

| Read | Result |
|------|--------|
| > 200 | Optimal: HCO if more defenders than offenders in ABA, else Fast Break |
| 125–200 | HCO, unless offense aggression is `"aggressive"` → Fast Break |
| ≤ 125 | 50/50 HCO vs Fast Break |

#### Tests

- `tests/test_fcp_read_decision.py` — FCP strong-handler sum (130) and low-tier weights.
- `tests/test_fcp_offball_attack.py` — tier boundaries at 34 / 50 / 51 and backcourt release lane.
- `tests/test_fcp_pf_c_zone.py` — zone geometry, anchor ladder, BH x≥64 man release.

#### Related docs

- [`Dynamic_FCP_Brief.md`](../projects/Dynamic_FCP_Brief.md) — full dynamic FCP spec (engagement, off-ball routing, play architecture).
- [`HCT_System.md`](./HCT_System.md) — shared loop primitives; HCT keeps `READ_STRONG_HANDLER_SUM = 80`.

---

### FCP Starting Alignment (BIP-end positions)

Set during BASELINE_INBOUND when `next_defensive_setup="FCP"` (`TurnManager._build_fcp_setup_positions`). HOME orientation; away offense flips x via `getAwayTeamCoords`.

**Offense ranges** (`FCP_OFFENSE_SETUP_RANGES` in `BackEnd/constants/__init__.py`):

| Pos | x range | y range | Notes |
|---|---|---|---|
| SF | 3 (fixed) | chemistry-aware | Inbounder |
| PG | random.randint(12, 18) | random.randint(15, 23) | Lower receive option |
| SG | random.randint(12, 18) | random.randint(27, 35) | Upper receive option |
| PF | random.randint(45, 55) | random.randint(20, 30) | Mid-court outlet |
| C  | random.randint(60, 70) | random.randint(20, 30) | Frontcourt anchor |

**Defense ranges** (`FCP_DEFENSE_SETUP_RANGES`):

| Pos | x range | y range |
|---|---|---|
| PG | random.randint(20, 25) | random.randint(23, 27) |
| SG | random.randint(26, 31) | random.randint(30, 36) |
| SF | random.randint(26, 31) | random.randint(14, 20) |
| PF | random.randint(50, 55) | random.randint(23, 27) |
| C  | random.randint(71, 76) | random.randint(23, 27) |

**Collision rule** (`FCP_SETUP_COLLISION_OFFSET_GRID = 2`): exact (x,y) collisions broken by moving one player 2 grid spots in a random direction, up to 10 rounds.

---

### When FCP Activates

- After made shots when `offensive_state = "FCP"`
- Set via `turn_manager.determine_defensive_pressure_type()`

---

### Possible FCP Outcomes

1. **O_FOUL** — possession change → SIDE_INBOUND → HCO
2. **D_FOUL** — bonus routing → FT or SIDE_INBOUND → HCO
3. **STEAL** — FAST_BREAK or HCO
4. **DEAD_BALL_TURNOVER** — SIDE_INBOUND → HCO
5. **HCO** — press break, no possession change
6. **SHOT** — full `resolve_shot()` path with FCP "shot" skeleton

---

### Dynamic Player Assignment

- **Ball handler:** from skeleton steps (`handle_ball`, `receive`, `shoot`) — not hardcoded PG
- **Defender:** position-matched to ball handler
- **Per-step ball handler:** FCP defenders use `guard_ball` when assignment is the live handler (`FCP_HCT_System.md` legacy note retained for FCP animation behavior)

---

### FCP Stat Tracking

**Offense:** `FCP_A` (all lineup), `FCP_S` on MAKE / HCO / defensive foul  
**Defense:** `FCP_A_D` (all lineup), `FCP_S_D` on MISS / TO / STEAL / offensive foul  
**Team scouting:** `def_scouting["defense"]["FCP"]["used"]` / `["success"]`

Recorded via `_record_fcp_stats()` in `phase_resolution.py`.

---

### Skeleton System

- **Source:** MongoDB `fcp_skeletons` (`BackEnd/api/skeleton_routes.py`; legacy fallback `playcall_skeletons/fcp_skeletons.py`)
- **Variants:** `"base"` (non-shot + HCO), `"shot"` (SHOT results)
- **Version selection:** random non-empty version per variant
- **UESS:** `build_skeleton_animation_steps(..., turn_type="FCP")` when `animation_steps` present
- **Builder UI:** `FrontEnd/static/fcp-skeletons.html`

---

### Key Files

**Backend**
- `BackEnd/engine/dynamic_fcp.py` — `compute_dynamic_fcp_turn()` wrapper
- `BackEnd/engine/fcp_pf_c_zone.py` — FCP Straight Pressure PF/C zone + anchor ladder
- `BackEnd/engine/fcp_offball_attack.py` — off-ball attack routing on advance beats
- `BackEnd/engine/dynamic_hct.py` — shared §4 loop, FCP read constants, engagement, Straight Pressure wiring
- `BackEnd/engine/fcp_press_plays.py` — FCP play registry (`StraightPressureFCP`, etc.)
- `BackEnd/engine/phase_resolution.py` — `resolve_full_court_press_logic()`, `USE_DYNAMIC_FCP`, legacy skeleton getters, stopper integration
- `BackEnd/models/turn_manager.py` — `_build_fcp_setup_positions()`, pressure type
- `BackEnd/engine/skeleton_step_emitter.py` — FCP schema steps + stopper step handling
- `BackEnd/models/animator.py` — legacy skeleton → animations

**Frontend**
- `FrontEnd/static/fcp-skeletons.html` — skeleton builder
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — BIP + FCP setup

**Related**
- [`Dynamic_FCP_Brief.md`](../projects/Dynamic_FCP_Brief.md) — dynamic FCP overhaul (in progress)
- [`HCT_System.md`](./HCT_System.md) — Half Court Trap (dynamic; separate system)
- [`Stopper_System.md`](./Stopper_System.md) — truncation architecture (FCP + legacy HCT fallback)
- [`BIP_System.md`](./BIP_System.md) — baseline inbound → FCP setup

---

### Future Enhancements

- Enhanced stopper step selection using player attributes
- Additional FCP skeleton variants for situational press breaks
