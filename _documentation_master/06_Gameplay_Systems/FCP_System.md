## Full Court Press (FCP) System

> **Doc status (July 2026):** Placement / BIP setup / in-possession defense targets verified against code. The **legacy** skeleton + BSM/DST resolution flow (sections through *Overview*) still describes the old path when `USE_DYNAMIC_FCP=False`. The **dynamic** spatial loop (`USE_DYNAMIC_FCP=True`, default) is documented in [**Dynamic FCP Engine — BH Read Logic**](#dynamic-fcp-engine--bh-read-logic-current) below and in the archived [`Dynamic_FCP_Brief.md`](../projects/Z-Completed/Dynamic_FCP_Brief.md). A full rewrite collapsing legacy content is still planned once FCP press-play PR3 lands.

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
- The inbound pass runs during BASELINE_INBOUND; FCP animates SF→PG inbound via UESS `animation_steps` (legacy: `runInboundSetup()`).
- **FCP BIP step 2** advances when 4 of 5 offense reach press-break setup **and** SF reaches the baseline inbound spot (mandatory passer gate — see `BIP_System.md`).
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

Moment detection for pressure/trap uses `TRAP_MOMENT_RANGE = 5` (same as HCT). `MOMENT_RANGE = 11` is still used for pass-contest on-ball exclusion and other non-detect checks.

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

#### Aggression for designers (D8 — shared with HCT)

1. **What the dial is:** Per-turn defense `aggression_call` (passive / normal / aggressive) scales **event volume after a defender engages** — it does **not** change who wins the encounter (`d_score` vs `o_score`); it only amplifies outcomes once that winner is decided.

2. **Defense wins the encounter:** `p_event = DEF_WIN_BASE (**0.25**) × margin × agg (0.7 / 1.0 / 1.3) × …`, capped at **60%** — then a weighted roll for steal / dead-ball TO / charge; tune **`HCT_D8_DEF_WIN_BASE`**, **`HCT_D8_P_EVENT_MAX`**, **`HCT_D8_AGG_MULT`** for overall press chaos.

3. **Offense wins the encounter:** `p_dfoul = DFOUL_BASE (**0.25**) × margin × agg × discipline & AG-gap terms` (no artificial cap; clamped to valid probability 0–100%) — tune **`HCT_D8_DFOUL_BASE`**, **`HCT_D8_W_DISC_REACH`**, and **`HCT_D8_W_AG_BEATEN`** for reach-in frequency on blow-bys.

4. **Asymmetry to know when tuning:** Same **0.25** base and agg multiplier on both branches, but a **60% cap on defense-wins events only** still makes aggressive **reward-heavy when the press is winning checks**; steals get **extra** agg via `steal_factor` (only knob that double-dips). Reach-ins on blow-bys scale with agg but have no separate cap.

5. **Out of scope for this dial:** Pass interceptions (§14 `pass_contest`), FCP engagement geometry (who closes first), steal→fast-break odds (0–4 strategy slider), and HCO moment rate (`event_scalar = 0.5`, separate engagement % table) — don't touch D8 expecting those to move.

#### SF inbound release (current)

After BIP, SF sprints off the baseline **starting on the first FCP segment** (engagement / converge / hold — not waiting for a BH advance beat).

| Rule | Detail |
|------|--------|
| **Movement target** | **x = 34** (home; mirrored away) on an **open vertical tier** |
| **Tier anchors (home y)** | upper **35**, center **25**, lower **15** |
| **Tier occupancy** | PG + SG (excluding BH) each claim upper (y>30), center (20–30), or lower (y<20); SF picks **randomly among open tiers** (always ≥1 with 3 tiers / 2 players) |
| **Pass eligibility** | SF excluded from press-break pass targets until **offense-progress x ≥ clear_x**, where `clear_x = randint(14, 20)` per possession (halfway from baseline ~3 → staging 34). Away: `x ≤ 100 − clear_x`. |
| **After staging** | On **`hct_advance`**, SF joins PG/SG on the normal backcourt release lane **x∈[46,53]** |

Module: `fcp_inbound_release.py` (target + pass gate); wired in `compute_dynamic_hct_turn` via `off_targets["SF"]` + `FcpOffballAttackState.set_sf_inbound_release`.

#### Over-and-back awareness (FCP + HCT)

Before a pass that **would** be over-and-back (`frontcourt_established` + receiver in backcourt), the passer may **read the violation and hold** instead of throwing the pass.

| Rule | Detail |
|------|--------|
| **Threshold** | `0.8 × PS + 0.2 × CH` (passer attributes) |
| **Roll** | `randint(1, 100)` — pass **only if** `roll > threshold` |
| **Grace beat** | The **first BH** to establish frontcourt (dribble, advance, or pass receipt) gets **one beat** where any backward outlet is **always** a hold — teammates sprint toward **x∈[51,57]** if still in backcourt |
| **On hold** | Normal §5 hold beat (grace label vs over-and-back read label) |
| **On pass** | Pass resolves as usual; post-pass violation still fires if the ball lands backcourt |
| **Off-ball urgency** | Once `frontcourt_established`, non-BH offenders still in backcourt override targets to the cross-half band (HCT `off_targets`; FCP `FcpOffballAttackState`) |
| **Back-movement gate** | Once `frontcourt_established`, any **off-ball** offender who has crossed half court is **ratcheted at x=50** — his x cannot re-enter the backcourt on any later beat this possession (he may sit on the line). Applied at each segment snapshot via `gate_offense_backcourt_reentry`; the live BH and an in-flight pass receiver are never gated (so over-and-back stays detectable at the true catch spot) |
| **Scope** | FCP + HCT dynamic loop; primitives in `over_and_back.py` |

#### Off-ball attack routing (current)

During **`hct_advance`**, **`hct_hold`**, and **`hct_pass`** beats, non-BH offenders route via `fcp_offball_attack.py` (sprint toward press-break destinations keyed to the live ball handler). **Engagement** and **converge** still use static BIP **`off_targets`** until the first pass or advance activates incremental routing.

**Ball-progress tiers** (BH **x**, home orientation; away mirrored). Half-open partition — PF and C share the same boundary operators:

| Tier | BH progress x (home) | PG / SG / SF | PF | C |
|------|----------------------|--------------|----|---|
| **T1** | **x ≤ 34** | Release **x∈[46,53]**, **y ± 6** | Hold | Hold |
| **T2** | **34 < x ≤ 50** | Release (same) | Deep key (6 eu of x=47) | BH-half mid spots |
| **T3** | **50 < x ≤ 64** | Release (same) | key / midWings / wings | midLane + front half spots |
| **T4** | **x > 64** | Release until terminal | Same as T3 | Same as T3 |

Constants: `FCP_TIER1_MAX = 34`, `FCP_TIER2_MAX = 50`, `FCP_TIER3_MAX = 64`. Broken-trap drives flood all non-BH to ABA spots until a cutoff **STOP_HCO** (or other terminal) exits ABA mode back to incremental tiers.

#### FCP Straight Pressure — PF/C zone & man release (current)

**Def PF/C** use a compressing front-court zone (not HCT `_pf_c_targets`):

| BH x (home) | Zone x | Zone y |
|-------------|--------|--------|
| < 36 | [50, 64] | 1–50 |
| 36–50 | [ball_x, min(ball_x+14, 64)] | 10–40 |
| 50–64 | [50, 64] | 10–40 |

Anchor ladder: midcourt → key → midLane → basketSpot by progress. Help/denial counts offenders inside the zone.

**Def SG/SF release:** when **BH x ≥ 64** (not when their man enters ABA). PG stays on ball. Module: `fcp_pf_c_zone.py`.

#### Defensive mid-court recovery (FCP + HCT)

Companion to the offensive back-movement gate. Once `frontcourt_established`, any defender the active play leaves **holding in the backcourt** (Standard Trap normal-shift guards; FCP Straight Pressure men released "to help" after the press break) is pulled across mid-court so the defense doesn't get stranded when the offense clears the backcourt.

| Rule | Detail |
|------|--------|
| **Trigger** | `frontcourt_established` (ball crossed half this possession) — same trigger as the offense gate |
| **Who** | Any defender whose play-computed target is still in the **backcourt** (behind x=50). Ball/trap/zone/man-following defenders already resolve frontcourt targets and are untouched |
| **Where** | Nearest **unguarded** offender, denying ball-side (`interpolate(BH → man, 0.6)`); "guarded" is inferred from the non-stranded defenders' targets (within `8`). Falls back to the **key** help spot if every offender is already covered |
| **Trailing man** | Self-correcting — a legit unguarded backcourt offender is the nearest unguarded man, so his defender stays with him instead of abandoning him |
| **Speed** | Recovering defenders **sprint** (they catch up rather than trail a beat behind) |
| **Where applied** | Overlay on the play's `defense_targets` inside `_move_defense`; primitive `_recover_defense_targets` — shared by all HCT/FCP plays |

#### Post-read overrides (shared)

- **D21 — no live dribble:** any `attack` result collapses to `pass`.
- **Broken + attack:** runs the open-floor cutoff race (`_do_broken_hct_cutoff`) instead of a normal on-ball contest. Geometry, shared D8 outcomes, and transition consumption are canonical in [`HCT_System.md`](HCT_System.md#the-possession-loop): `POS_O` continues to ABA; `NEUTRAL`/`D_STOP` reset to HCO; contact is terminal at the meet.
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
- `tests/test_fcp_inbound_release.py` — SF x=34 tier pick, pass-clear x (14–20), off-ball handoff.
- `tests/test_fcp_offball_attack.py` — tier boundaries at 34 / 50 / 51 and backcourt release lane.
- `tests/test_fcp_pf_c_zone.py` — zone geometry, anchor ladder, BH x≥64 man release.
- `tests/test_defense_recovery.py` — stranded backcourt defenders recover across mid-court; trailing-man and all-covered fallbacks.

#### Related docs

- [`Dynamic_FCP_Brief.md`](../projects/Z-Completed/Dynamic_FCP_Brief.md) — archived full dynamic FCP spec (engagement, off-ball routing, play architecture).
- [`HCT_System.md`](./HCT_System.md) — shared loop primitives; HCT keeps `READ_STRONG_HANDLER_SUM = 80`.

---

### FCP Starting Alignment (BIP-end positions)

Set during BASELINE_INBOUND when `next_defensive_setup="FCP"` (`TurnManager._build_fcp_setup_positions`). HOME orientation; away offense flips x via `getAwayTeamCoords`.

**Offense** — SF is chemistry-aware (not in the ranges map). PG/SG/PF/C from `FCP_OFFENSE_SETUP_RANGES` in `BackEnd/constants/__init__.py`:

| Pos | x range | y range / rule | Notes |
|---|---|---|---|
| SF | 3 (fixed) | chemistry-aware (see below) | Inbounder |
| PG | (12, 18) | `SF.y + randint(-6, 6)`, clamped to [1, 49] | Receive near inbounder |
| SG | (25, 32) | (20, 30) | Mid-backcourt outlet |
| PF | (45, 55) | (20, 30) | Mid-court outlet |
| C  | (60, 70) | (20, 30) | Frontcourt anchor |

**SF y (chemistry-aware, mirrors HCO BIP):**
- Chemistry > 15 → biased toward PG side: `(25, 35)` if `current_pg_y > 24`, else `(15, 25)`
- Otherwise → `(15, 35)`

**Defense ranges** (`FCP_DEFENSE_SETUP_RANGES` — all five positions; replaces the legacy `get_defender_coords` layout for FCP only):

| Pos | x range | y range |
|---|---|---|
| PG | (20, 25) | (23, 27) |
| SG | (26, 31) | (30, 36) |
| SF | (26, 31) | (14, 20) |
| PF | (50, 55) | (23, 27) |
| C  | (71, 76) | (23, 27) |

**Collision rule** (`FCP_SETUP_COLLISION_OFFSET_GRID = 2`): exact (x,y) collisions (offense + defense together) broken by moving one randomly chosen player 2 grid spots in a random direction, up to 10 rounds.

Also documented in [`BIP_System.md`](./BIP_System.md) § "BASELINE_INBOUND → FCP".

---

### Press Play Selection (`fc_presses`)

Mirrors HCT trap selection on the **defending** team's playbook, but **PR1 implements only Straight Pressure**:

| Key | Label | Status |
|-----|-------|--------|
| `fcp_straight_pressure` | Straight Pressure | **Live** — only registered play |
| `fcp_standard_trap` | Standard Trap | Reserved (PR3) |
| `fcp_standard_diamond` | Standard Diamond | Reserved (PR3) |

- Chosen once at `TurnManager.determine_defensive_pressure_type()` → `game_state["fcp_press_play"]`.
- `play_key_for_fcp_press()` always resolves to `fcp_straight_pressure` until PR3 (weights for other keys ignored).
- Registry: `FCP_PRESS_PLAYS` in `fcp_press_plays.py`. Per-play scouting: `scouting_data["defense"]["fcp_press_plays"][key]`.

**Live placement model (Straight Pressure FCP):** man-glue on PG/SG/SF (`_straight_pressure_targets` with `fcp_man_glue=True`); trap moments downgrade to single-defender `"pressure"`; PF/C use `fcp_pf_c_zone.py` (see above). Release off-ball men when **BH progress x ≥ 64** (not when their man enters ABA).

---

### When FCP Activates

- After made shots when `offensive_state = "FCP"`
- Set via `turn_manager.determine_defensive_pressure_type()` (also stashes `fcp_press_play`)

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

**Legacy skeleton path:** ball handler from skeleton steps (`handle_ball`, `receive`, `shoot`); defender position-matched to BH.

**Dynamic path (default):** live BH from the shared HCT/FCP loop; Straight Pressure FCP locks man assignments at converge (`_straight_pressure_begin(..., fcp=True)`); primary/trapper via universal band-based `_select_trappers` (trap moments still downgrade to pressure under `fcp_man_glue`).

---

### FCP Stat Tracking

**Offense:** `FCP_A` (all lineup), `FCP_S` on MAKE / HCO / defensive foul  
**Defense:** `FCP_A_D` (all lineup), `FCP_S_D` on MISS / TO / STEAL / offensive foul  
**Team scouting:** `def_scouting["defense"]["FCP"]["used"]` / `["success"]`

Recorded via `_record_fcp_stats()` in `phase_resolution.py`.

---

### Animation and UESS

- **Dynamic path (default):** FCP wraps the shared dynamic HCT loop and emits
  through `dynamic_fcp_step_emitter` / `dynamic_hct_step_emitter`.
- **Central orchestration:** `TurnManager._emit_pressure_animation_steps`
  chooses the dynamic wrapper, derives elapsed time from schema clock burn, and
  freezes/projects the result through the shared PressureStepState bridge.
- **Schema-owned terminal motion:** pass interception renders flight to the
  interceptor; batted-OOB renders contact and drift to the OOB target. Frontend
  STEAL/FOUL/dead-ball terminal handlers perform cleanup only.
- **Legacy fallback:** non-dynamic FCP payloads may still use MongoDB
  `fcp_skeletons` and `build_skeleton_animation_steps(..., turn_type="FCP")`.
  The builder UI remains `FrontEnd/static/fcp-skeletons.html`.
- **Open architecture work:** pressure builders still build schema before the
  StepState freeze/project bridge. Direct upstream `PressureStepState` builders
  remain deferred until parity and prototype coverage are retained.

---

### Key Files

**Backend**
- `BackEnd/engine/dynamic_fcp.py` — `compute_dynamic_fcp_turn()` wrapper
- `BackEnd/engine/fcp_pf_c_zone.py` — FCP Straight Pressure PF/C zone + anchor ladder
- `BackEnd/engine/fcp_offball_attack.py` — off-ball attack routing on advance beats
- `BackEnd/engine/dynamic_hct.py` — shared §4 loop, FCP read constants, engagement, Straight Pressure wiring
- `BackEnd/engine/dynamic_fcp_step_emitter.py` — dynamic FCP schema wrapper
- `BackEnd/engine/dynamic_hct_step_emitter.py` — shared pressure schema assembly
- `BackEnd/engine/pressure_step_state.py` — shared pressure freeze/projection bridge
- `BackEnd/engine/fcp_press_plays.py` — FCP play registry (`StraightPressureFCP`; PR1 only)
- `BackEnd/constants/fcp_press_play_types.py` — keys, `play_key_for_fcp_press()`
- `BackEnd/engine/fcp_inbound_release.py` — SF staging + pass-clear gate
- `BackEnd/engine/phase_resolution.py` — `resolve_full_court_press_logic()`, `USE_DYNAMIC_FCP`, legacy skeleton getters, stopper integration
- `BackEnd/models/turn_manager.py` — setup/play selection and centralized pressure emission
- `BackEnd/engine/skeleton_step_emitter.py` — legacy/non-dynamic FCP fallback and shared post-steal transition
- `BackEnd/models/animator.py` — legacy skeleton → animations

**Frontend**
- `FrontEnd/static/fcp-skeletons.html` — skeleton builder
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — BIP + FCP setup

**Related**
- [`Dynamic_FCP_Brief.md`](../projects/Z-Completed/Dynamic_FCP_Brief.md) — archived dynamic FCP design brief
- [`HCT_System.md`](./HCT_System.md) — Half Court Trap (dynamic; separate system)
- [`Stopper_System.md`](./Stopper_System.md) — truncation architecture (FCP + legacy HCT fallback)
- [`BIP_System.md`](./BIP_System.md) — baseline inbound → FCP setup

---

### Future Enhancements

- Enhanced stopper step selection using player attributes
- Additional FCP skeleton variants for situational press breaks

## Tunable Constants — Pass Contest (interceptions & batted balls)

Press/trap pass contests resolve through the shared
[`BackEnd/engine/pass_contest.py`](../../BackEnd/engine/pass_contest.py)
`resolve_pass_contest`, wired from `dynamic_hct._resolve_hct_pass_contest`.
HCT and FCP share this path; `turn_mode` selects the turn type so each modifier
is looked up correctly rather than by coincidence.

### Team-attribute modifiers

| Side | Attribute | Resolver | Effect |
|---|---|---|---|
| Offense | `pt_opp_modifier` | `resolve_offense_pass_modifier` | Higher = passer clears the safety bar more easily = fewer deflections |
| Defense | `pt_efficiency` | `resolve_defense_pass_modifier` | Higher = lower deflection tier = more deflections |

Both are `core8_gameplay()`-normalised (±10). The `_g` suffix on
`offense_modifier_g` / `defense_modifier_g` marks that contract — never pass a
raw ±20 team attribute.

### Calibration bases

| Constant | Value | Effect |
|---|---|---|
| `HCT_PASS_SAFETY_BASE` | 175.0 | Passer-safety bar. ↑ = harder to evade = more deflections |
| `HCT_PASS_INTERCEPT_TIER_MID` | 170.0 | Deflection threshold. ↓ = more deflections |
| `HCT_PASS_INTERCEPT_TIER_HI` | 200.0 | **Dead** — carried for signature parity only (see below) |
| `PASS_DEFLECT_KIND_D` | 200 | INTERCEPT vs BAT_OOB ratio. **Shared with HCO** |

Seeded at HCO parity (175 / 170) and deliberately separate from the
`HCO_PASS_*` constants so the two families can be calibrated independently.

### Formulas (`efficiency_in_composite=True`, matching HCO)

```
pass_score = ((PS·0.6 + CH·0.2 + IQ·0.2) + pt_opp_modifier) × rand(1,6)
bar        = HCT_PASS_SAFETY_BASE − pt_opp_modifier
intercept  = ((OD·0.6 + CH·0.2 + IQ·0.2) + pt_efficiency)  × rand(1,6)
tier_mid   = HCT_PASS_INTERCEPT_TIER_MID − pt_efficiency
kind       = rand(1, PASS_DEFLECT_KIND_D) < (CH + IQ) ? INTERCEPT : BAT_OOB
```

Team efficiency folds into **both** the composite and the bar — which is why the
bases sit below the shared 200/200 defaults.

### Which dial does what

- **How often passes are deflected** → `HCT_PASS_SAFETY_BASE` + `HCT_PASS_INTERCEPT_TIER_MID`
- **INTERCEPT vs BAT_OOB split** → `PASS_DEFLECT_KIND_D` only. ↑ D = more BAT_OOB, ↓ D = more clean steals. High CH+IQ defenders skew toward INTERCEPT.
- **Lane eligibility** → `PASS_LANE_DIST = 8.0` (HCT/FCP; HCO is tighter at 5–6)

### Two traps

`PASS_INTERCEPT_TIER_HI` / `HCT_PASS_INTERCEPT_TIER_HI` are **dead**. The old
hi/mid split made BAT_OOB effectively unreachable — the band was narrower than
the score's quantization step (`composite × randint(1,6)`, step ≈ 50–100), so
consecutive scores straddled it. Tuning them has no effect.

`PASS_DEFLECT_KIND_D` is **shared across HCO, HCT and FCP**. Changing the
intercept/bat ratio moves it for all three; splitting them needs a new constant
plumbed the way `HCT_PASS_SAFETY_BASE` already is.

### History

Before 2026-08-28, HCT/FCP passed **no** `defense_modifier_g` at all — the
defending team's press/trap quality had zero effect on interceptions — and ran
with `efficiency_in_composite=False` against the shared 200/200 bases. FCP also
had no entry in `OFFENSE_PASS_MODIFIER_KEYS`, so an explicit `"FCP"` turn type
would have fallen back to `offensive_efficiency`.
