## Half Court Trap (HCT) System ✅ **COMPLETE** (Dynamic HCT — March 2026; placement sections verified July 2026)

> **Canonical reference (Bible):** This document is the **single source of truth** for the live **dynamic** Half Court Trap system — activation, loop logic, trap plays, outcomes, animation, stats, and file touchpoints. The archived design brief lives in [`Dynamic_HCT_Brief.md`](../projects/Z-Completed/Dynamic_HCT_Brief.md). If something conflicts, **treat this file as authoritative** for runtime behavior.

**Legacy note:** HCT no longer uses MongoDB skeletons + the stopper system when `USE_DYNAMIC_HCT = True` (default). The skeleton/stopper path remains in `resolve_half_court_trap_logic()` only as a fallback when the flag is `False`.

---

**Base Constants**

1. **Trap/pressure detect radius:** `TRAP_MOMENT_RANGE = 5` euclidean grid spots (`dynamic_hct.py`) — pressure (1 ahead defender in range) / trap (2+ in range with ≥1 ahead on x). Tighter than vicinity so a "trap" means genuine converge, not nearby help. **No traps in the center horizontal band** (BH y ∈ [20, 30]) — shared `_detect_moment` gate for every HCT play.
2. **Vicinity radius:** `MOMENT_RANGE = 11` — pass-contest on-ball exclusion, Diamond wing trap-in-range checks, and other non-detect uses (not the pressure/trap classifier).
3. **Attack Basket Area (ABA):** x past half court toward basket, **y ∈ [10, 40]** (`ATTACK_BASKET_Y_MIN/MAX`). Trap-break / goal resolution runs only when the BH enters this band.
4. **10-second rule:** `HCT_TEN_SECOND_LIMIT = 10.0` game-seconds from possession start; disabled when &lt;10s remain in the quarter at possession start. Checked with shot-clock each loop iteration.
5. **Walk-up engage point:** BH targets **(44, y ∈ [21, 29])** after BIP (flipped for away offense).
6. **BH advance beat (beat pressure/trap):** `+random(6, 12)` x toward basket, `+random(-6, 6)` y.
7. **Drive / cutoff pace:** `ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND = 12`; AG-scaled via `ag_to_grid_per_game_sec`.
8. **Off-ball drift (cutoff + FB drive):** `HCT_DRIFT_PROBABILITY = 0.5` — each off-ball player (both teams) rolls 50% to drift toward rim at `DRIFT_GRID_PER_GAME_SEC = 8`, else hold.
9. **Pass contest lane width:** `PASS_LANE_DIST = 8` (`pass_contest.py`); safety gate base `PASS_SAFETY_BASE = 200`; intercept tiers `250` / `200` → STEAL / bat-OOB.
10. **Trap play weights (user default):** `standard_trap` 34 / `straight_pressure` 33 / `standard_diamond` 33 (`hct_trap_play_types.DEFAULT_HCT_TRAP_WEIGHTS`). CPU teams use Standard Diamond at 0% unless projected starting SG AG &gt; 50 (see `cpu_playbook_customization.py`).
11. **Shift bands (Standard Trap):** BH y &lt; 20 → lower; y &gt; 30 → upper; else normal (`SHIFT_LOWER_Y` / `SHIFT_UPPER_Y`).

---

**HCT Resolution Flow (high level)**

1. **Apply energy decay** — active players via `apply_energy_decay(..., omit_zeros_for_defense=True)`.
2. **Track attempt** — `def_scouting["defense"]["HCT"]["used"] += 1`.
3. **Resolve trap play** — `game_state["hct_trap_play"]` (stashed at BIP by `TurnManager.determine_defensive_pressure_type`) or `play_key_for_hct_trap(def_team.playbook_settings)`.
4. **Run engine** — `get_hct_trap_play(play_key).run(game)` → `compute_dynamic_hct_turn(game, play)` returns intermediate dict (`loop_segments`, `result_type`, roles, seeds).
5. **Branch on terminal result:**
   - **FAST_BREAK_SHOT** → `resolve_hct_fast_break_shot` (broken-trap FB; reuses `compute_fb_shot_geometry`).
   - **ATTACK_BASKET_SHOT / ATTACK_BASKET_DRIVE** → `resolve_hct_attack_basket_shot` / `resolve_hct_attack_basket_drive`.
   - **HCO / DEAD BALL / STEAL / FOUL** → wrapper in `_resolve_half_court_trap_dynamic_first_cut` sets possession, `next_play_type`, stats, foul/steal side effects.
   - **Bat-OOB pass** → `result_type = DEAD BALL` + `bat_oob = True` — offense **retains** (side inbound, no TO, no possession flip).
6. **Emit animation** — `build_dynamic_hct_animation_steps()` → `animation_steps[]` on turn result (UESS schema playback). Post-step hook: `_runHctBatOobBallSend` / `_runSchemaBatOobBallSend` for batted-ball ball flight (`batOobAnimation.js`).
7. **Record stats** — `_record_hct_stats` + per-play `scouting_data["defense"]["hct_trap_plays"][play_key]`.

---

### Overview

**Half Court Trap** is defensive pressure after a made basket when `offensive_state = "HCT"`. One HCT API turn = **one full trap-break possession**: the engine runs an internal **read → detect → resolve → move** loop until a terminal outcome (HCO transition, turnover, foul, steal, shot, clock violation, or bat-OOB pass).

**Architecture (three layers)**

| Layer | Module | Role |
|-------|--------|------|
| Wrapper | `phase_resolution._resolve_half_court_trap_dynamic_first_cut` | Stats, possession flips, foul bonus routing, steal→FB chance, merges engine output into turn dict |
| Engine | `BackEnd/engine/dynamic_hct.py` | Loop, moments, passes, ABA reads, cutoff race, pass contests |
| Plays | `BackEnd/engine/hct_trap_plays.py` | `HCTPlay` seams: `detect_moment`, `defense_targets`, `select_trappers`, `begin_possession` |
| Emitter | `BackEnd/engine/dynamic_hct_step_emitter.py` | Engine intermediate → `animation_steps[]` |
| Shots | `BackEnd/engine/dynamic_hct_shot.py` | ABA shot/drive + broken-HCT FB shot resolution |
| Pass contests | `BackEnd/engine/pass_contest.py` | Universal COMPLETE / INTERCEPT / BAT_OOB primitive |
| Cutoff geometry | `BackEnd/engine/cutoff_resolution.py` | Shared D21 drive cutoff (HCT broken trap + Covert Release FB stops) |

**Feature flag:** `USE_DYNAMIC_HCT = True` in `phase_resolution.py` (set `False` to revert to legacy skeleton + BSM/DST math).

---

### When HCT Activates

- After **made shots** when defense applies half court trap (`TurnManager.determine_defensive_pressure_type()` → `offensive_state = "HCT"`).
- Preceded by **BASELINE_INBOUND** with `next_defensive_setup = "HCT"` (see **BIP entry** below).
- Play key chosen once at the SS&S choke point and stored as `game_state["hct_trap_play"]`.

---

### BIP → HCT Entry

Documented in detail in [`BIP_System.md`](./BIP_System.md) § "BASELINE_INBOUND → HCT". Summary (HOME orientation; away flips x):

**Offense** — static `HCT_SETUP_POSITIONS` → `HCO_STRING_SPOTS` (not skeleton step 0):

| Pos | Spot key | Home coords |
|-----|----------|-------------|
| SF | `inbound_left` | (3, 25) — inbounder |
| PG | `hct_inbound_pg` | (10, 25) — usual BIP receiver / first-cut BH |
| SG | `hct_inbound_sg` | (15, 35) |
| PF | `deep upper wing` | (57, 35) |
| C | `deep lower wing` | (57, 15) |

**Defense** — `hct_initial_defender_coords(is_away_offense)` (shared by BIP-end and HCT loop start so step 0 does not read stale `player.coords`):

| Pos | Rule | Typical home centroid |
|-----|------|------------------------|
| PG | `DEFENSIVE_PG_STEP_1_TARGET` = center court | (50, 25) |
| SG / SF / PF / C | centroid of `HCT_STANDARD_NORMAL` polygon spots | ~SG (63, 39), SF (63, 11), PF (76, 25), C (83, 25) |

**Standard Diamond override:** at `begin_possession`, `_diamond_start_formation` snaps all five defenders into the 1-4 diamond (center_bc_defender x∈[44,50] y∈[23,27]; pos1 midLane±5y; pos2/pos3 deep wings ±3; pos4 key). BIP still plants the Standard Normal centroids; Diamond walk-up then converges to the diamond.

- **Frontend:** `runInboundSetup(..., pressureType="HCT")` animates SF→PG inbound; HCT turn uses schema step 0 walk-up from `prior_turn.final_coords` (no redundant `runSetupTween` when `fromInbound && isFCPHCT`).
- **Clocks** start when the inbound receiver has the ball (same contract as HCO BIP).

---

### Trap Play Selection (`hc_traps`)

Mirrors Fast Break play selection on the **defending** team's playbook:

| Key | Label | Summary |
|-----|-------|---------|
| `standard_trap` | Standard Trap | Zone-style normal formation; universal band-based primary/trapper on trap moments |
| `straight_pressure` | Straight Pressure | Man-to-man backcourt locks at converge; trap only when **rover** reaches BH |
| `standard_diamond` | Standard Diamond | 1-4 diamond (`center_bc_defender` default PG); band→role trapper map; dynamic D_FOUL backcourt/frontcourt split |

Registry: `HCT_TRAP_PLAYS` in `hct_trap_plays.py`. Weights: `playbook_settings["hc_traps"]`. Per-play scouting: `scouting_data["defense"]["hct_trap_plays"][key]["A"|"S"]`.

---

### The Possession Loop

Each loop iteration (after step 0 walk-up):

1. **Time terminals** — shot clock ≤ 0 → `DEAD BALL` + `turnover_type = SHOT_CLOCK`; elapsed ≥ 10s and BH not past half → `TEN_SECOND` violation.
2. **Zone precedence** — BH in ABA → §7 goal achievement (HCO vs FB read, or in-ABA shot tree). x &gt; half court but outside ABA y-band → trap persists (keep looping).
3. **Moment detection** — `play.detect_moment(bh_xy, def_coords)` → `none` | `pressure` | `trap` (+ in-range defender list). Defenders must be within **`TRAP_MOMENT_RANGE` (5)** and on the basket-side of the BH (x gate). **Center-band gate (all HCT plays):** while BH y ∈ [20, 30], never return `"trap"` — downgrade to `"pressure"` (matches Standard Trap formation, which only builds trap spots on upper/lower shifts). Straight Pressure further requires the **rover** in range before a trap is allowed.
4. **BH read** — `player_read`-style score → **attack / pass / hold** (thresholds dynamic on `BH + AG`; see [`Dynamic_HCT_Brief.md`](../projects/Z-Completed/Dynamic_HCT_Brief.md) for the full table). Strong-handler sum: `BH + AG > 80` (`READ_STRONG_HANDLER_SUM`).
5. **Resolve branch:**
   - **attack + none (broken HCT)** → cutoff race to y-keyed ABA spot (`topLane` / upper or lower apex); meet → D8 contest (`resolve_cutoff_contest`, steal excluded): **POS_O** → continue to ABA then HCO/FB read; **NEUTRAL/D_STOP** → `STOP_HCO`; foul/TO → terminal. No meet → ABA arrival → HCO/FB read.
   - **attack + pressure/trap** → D8 moment at contact.
   - **hold** → defenders converge; if a defender reaches BH → same D8 contest.
   - **pass** → vertical-half or central pass movement; **`resolve_pass_contest`** on flight (on-ball trappers excluded from intercept pool).
6. **Emit segment** — append to `loop_segments`; decrement shot clock by segment duration.
7. **Advance** (non-terminal) — BH random advance; defenders move via interrupted AG rates toward `play.defense_targets()` (overlay: mid-court recovery — see below); off-ball offense tracks actual coords.

**Pass receipt (off-ball re-key):** When the pass completes and a new teammate becomes BH (e.g. PG→SG), `_refresh_hct_off_targets_for_bh` rebuilds alias-map spacing for **SG-as-handler** — fresh pos1..pos4 range targets for the other four; the new BH keeps their **catch spot** (no x=44 snap). Teammates sprint toward those targets during pass flight and on subsequent hold/advance beats.

**Broken-cutoff consumption** (shared with FCP via `turn_mode="fcp"`): see [`attack_contest_unification.md`](../projects/attack_contest_unification.md). No dribble-dead RETAIN on meet — stop resets to HCO; beat-the-man continues the drive.

---

### Moment Resolution (D8)

`_resolve_moment(off_team, def_team, bh, primary_def, trapper, exclude_steal=...)` — attribute-driven regions:

- Defense wins → `STEAL`, `DEAD BALL`, or `O_FOUL` (charge).
- Offense wins → BH advances, or `D_FOUL` (reach-in, 60/30/10 fouler spread). Broken-cutoff `POS_O` continues the drive (separate path).
- Neutral → hold / stall (trap loop continues).

Aggression multiplier on defense-wins rates; offense `fight` suppresses. **Steal excluded** on full-speed drive cutoff collisions.

#### Aggression for designers (D8)

1. **What the dial is:** Per-turn defense `aggression_call` (passive / normal / aggressive) scales **event volume after a defender engages** — it does **not** change who wins the encounter (`d_score` vs `o_score`); it only amplifies outcomes once that winner is decided.

2. **Defense wins the encounter:** `p_event = DEF_WIN_BASE (**0.25**) × margin × agg (0.7 / 1.0 / 1.3) × …`, capped at **60%** — then a weighted roll for steal / dead-ball TO / charge; tune **`HCT_D8_DEF_WIN_BASE`**, **`HCT_D8_P_EVENT_MAX`**, **`HCT_D8_AGG_MULT`** for overall trap chaos.

3. **Offense wins the encounter:** `p_dfoul = DFOUL_BASE (**0.25**) × margin × agg × discipline & AG-gap terms` (no artificial cap; clamped to valid probability 0–100%) — tune **`HCT_D8_DFOUL_BASE`**, **`HCT_D8_W_DISC_REACH`**, and **`HCT_D8_W_AG_BEATEN`** for reach-in frequency on blow-bys.

4. **Asymmetry to know when tuning:** Same **0.25** base and agg multiplier on both branches, but a **60% cap on defense-wins events only** still makes aggressive **reward-heavy when the trap is winning checks**; steals get **extra** agg via `steal_factor` (only knob that double-dips). Reach-ins on blow-bys scale with agg but have no separate cap.

5. **Out of scope for this dial:** Pass interceptions (§14 `pass_contest`), steal→fast-break odds (0–4 strategy slider), and HCO moment rate (`event_scalar = 0.5`, separate engagement % table) — don't touch D8 expecting those to move.

---

### Primary / Trapper Selection (trap moments)

**Universal geometric rule** (`_select_trappers` — Standard Trap + Straight Pressure when a trap is allowed): Among in-range defenders, **primary** = first in-range defender whose **own y** sits in the ball's vertical band (`_diamond_band`: upper y&gt;30 / center 20–30 / lower y&lt;20); ties → nearest to BH; none in-band → nearest to BH. **Trapper** = next-closest remaining in-range defender (not a hardcoded PG).

**Standard Diamond override** (`_diamond_select_trappers`): on-ball **primary** is the band's *assigned* role — center → `center_bc_defender` (default PG); upper → pos2 (SF); lower → pos3 (PF); fall back to nearest in-range if assigned is out of range. **Trapper** = `center_bc_defender` when he is in range and not already primary; else next-closest. D_FOUL backcourt/frontcourt split uses `_diamond_court_split`.

---

### In-possession defender placement (`defense_targets`)

Each beat, `_move_defense` asks the active play for targets, then applies mid-court recovery, then interrupts travel at AG rates (PF/C + recovered defenders **sprint**; other defenders **standard**).

| Play | Seam | Placement model |
|------|------|-----------------|
| **Standard Trap** | `_defense_targets` | Upper/lower shift → `compute_hct_trap_formation` (two trappers at BH±1–4 x toward basket, BH_y±2) + remaining backcourt guard at BH_x+4, y=25. Normal shift → PG converges on BH; wings hold. **PF/C** always use D22 `_pf_c_targets` (ball-reactive; C upper-half / PF lower-half) when `off_coords` present. |
| **Straight Pressure** | `_straight_pressure_targets` | PG/SG/SF man-lock at converge (deny fraction 0.6 ball-side). Man who enters ABA is released → fills next open role: **rover** (on BH) → **key** (key/wing toggle by BH y) → **wings**. Trap only when rover is in range. PF/C inherit Standard D22 `_pf_c_targets`. |
| **Standard Diamond** | `_diamond_targets` | 1-4: `center_bc_defender` always on BH; pos1 deep rim triangle / deny ABA; pos2/pos3 mirrored wings; pos4 key safety + pass disruptor. **Does not** use PF/C D22 zone. Formation snaps at `begin_possession` via `_diamond_start_formation`. |

**Mid-court recovery (all plays):** once `frontcourt_established`, any defender whose play target is still in the backcourt is redirected to the nearest unguarded offender (deny 0.6) or the key help spot — shared `_recover_defense_targets` (same overlay as FCP; see [`FCP_System.md`](./FCP_System.md) § Defensive mid-court recovery).

---

### Pass Contests (§14 — built)

On each HCT pass, `_resolve_hct_pass_contest` → `resolve_pass_contest()`:

1. **Geometry gate** — in lane (perp distance ≤ 8) + D21 reachable-in-time with IQ anticipation head-start.
2. **Passer safety gate** — `(PS·0.6 + CH·0.2 + IQ·0.2) × d6` vs `200 − pt_opp_modifier` (HCT offense modifier).
3. **Intercept band** — defender composite vs tiers → **COMPLETE**, **INTERCEPT** (→ `STEAL` terminal), or **BAT_OOB** (→ dead ball, offense keeps).

On-ball defenders within moment range of the passer are **excluded** from the intercept pool (trappers can't peel to steal their own trap outlet).

**Frontend bat-OOB:** `turnData.bat_oob` + `bat_oob_contact` / `bat_oob_deflector_id`; schema steps animate players; imperative overlay flies ball passer → contact → deflected OOB (`FrontEnd/static/js/phaser/animation/batOobAnimation.js`).

---

### Attack Basket Area — Goal Achievement

When BH enters ABA (y 10–40, past half court):

- **Head-count read:** defenders vs offenders in ABA → optimal HCO vs Fast Break.
- **IQ read** (see [`Dynamic_HCT_Brief.md`](../projects/Z-Completed/Dynamic_HCT_Brief.md)): &gt;200 optimal; 125–200 HCO unless offense aggressive; ≤125 50/50.
- **HCO branch:** `result_type = HCO`, `next_play_type = HCO`, possession unchanged; stamps `final_ball_handler_id` for HCO entry orchestrator (non-PG initiator supported — suppress PG override on HCT path).
- **Fast Break branch:** broken-HCT cutoff win or numbers edge → `FAST_BREAK_SHOT` via `resolve_hct_fast_break_shot` (steal-FB geometry + full shot turn).
- **In-ABA shot tree:** `ATTACK_BASKET_SHOT` / `ATTACK_BASKET_DRIVE` → rim collapse (D5) + shot defender at release (D6) → `resolve_shot` path; emitter appends post-shot sub-steps.

---

### Terminal Outcomes & Routing

| `result_type` | Possession flip? | Typical `next_play_type` | Notes |
|---------------|------------------|--------------------------|-------|
| `HCO` | No | `HCO` | Successful trap break |
| `DEAD BALL` | Yes* | `SIDE_INBOUND` | *No flip if `bat_oob` |
| `STEAL` | Yes | `FAST_BREAK` or `HCO` | Steal→FB roll on **stealing** team's aggression slider |
| `FOUL` | If O_FOUL | `FREE_THROW` or `SIDE_INBOUND` | D_FOUL bonus routing; reach-in stats |
| `MAKE` / `MISS` | Shot rules | Rebound / BIP / FT | Via `dynamic_hct_shot` wrappers |
| Clock violations | Yes | `SIDE_INBOUND` | `turnover_type` SHOT_CLOCK / TEN_SECOND |

Announcements: `"TRAP!"` base text; `"Batted Ball Out Of Bounds!"` for bat-OOB; `"INTERCEPTION!"` for pass picks; violation strings for clock terminals.

---

### Stats & Scouting

**Player stats:** `HCT_A`, `HCT_S` (offense); `HCT_A_D`, `HCT_S_D` (defense) — same success/failure conventions as legacy HCT (see below). Recorded via `_record_hct_stats`.

**Team scouting:** `def_scouting["defense"]["HCT"]["used"]` on entry; `["success"]` on defensive stops (MISS, O_FOUL, DEAD BALL except bat-OOB, STEAL).

**Per-play defense scouting:** `hct_trap_plays[play_key].A` / `.S` on attempt / offensive success events.

---

### Animation (UESS)

- Turn carries **`animation_steps[]`** built by `build_dynamic_hct_animation_steps()`.
- **Step 0:** `build_walk_up_step` — BH cruise to engage point; off-ball sprint to setup; defenders to formation.
- **Steps 1..N:** one step per `loop_segment` (converge, advance, hold, pass flight, cutoff drive, etc.).
- **Turn-stop events:** `DEAD_BALL_TURNOVER`, `STEAL`, `FOUL`, shot handoff — consumed by `animationPlayback.dispatchTurnStop`.
- **Post-shot:** `_build_post_shot_sub_steps` appended for ABA / FB shot branches.
- **Legacy path:** if no `animation_steps`, fall back to skeleton + stopper (deprecated for HCT when dynamic flag is on). See `Stopper_System.md`.

Frontend dispatch: `AnimationEngine.runSchemaPlaybackTurn` for HCT turns with steps; HCT bat-OOB post-hook after schema settles.

---

### Key Files

**Backend**
- `BackEnd/engine/phase_resolution.py` — `resolve_half_court_trap_logic`, `_resolve_half_court_trap_dynamic_first_cut`, `USE_DYNAMIC_HCT`
- `BackEnd/engine/dynamic_hct.py` — `compute_dynamic_hct_turn`, loop, moments, cutoff, pass wiring
- `BackEnd/engine/dynamic_hct_step_emitter.py` — schema step assembly
- `BackEnd/engine/dynamic_hct_shot.py` — ABA + broken-HCT shot resolution
- `BackEnd/engine/hct_trap_plays.py` — `HCTPlay` + three registered plays
- `BackEnd/constants/hct_trap_play_types.py` — keys, weights, selection
- `BackEnd/engine/pass_contest.py` — pass contest primitive
- `BackEnd/engine/cutoff_resolution.py` — shared drive cutoff geometry
- `BackEnd/models/turn_manager.py` — pressure type + `hct_trap_play` stash at BIP
- `BackEnd/utils/shared_defense.py` — HCT zone centroids, trap formation helpers

**Frontend**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` — schema playback + HCT bat-OOB hooks
- `FrontEnd/static/js/phaser/animation/batOobAnimation.js` — bat collision + deflected OOB ball path
- `FrontEnd/static/js/phaser/animation/animationPlayback.js` — step renderer + turn-stop dispatch
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` — BIP inbound for HCT

**Tests (representative)**
- `tests/test_fcp_hct_stopper_system.py` — includes dynamic HCT paths when flag on
- `tests/test_dynamic_hct_shot_rebound_attemptors.py` — HCT FB miss rebound seeding

---

### Legacy Fallback (`USE_DYNAMIC_HCT = False`)

Reverts to pre-2026 behavior documented historically in the legacy FCP sections of [`FCP_System.md`](./FCP_System.md): single-roll **BSM/DST** score math, MongoDB **`hct_skeletons`** `"base"` / `"shot"` variants, and **stopper system** truncation for non-SHOT results. Not used in production with the default flag. Kept for regression tests and emergency rollback.

**Legacy HCT success math (reference only):**
- BSM = `200 + 10×fight` + chemistry/`pt_opp_modifier` adjustments
- DST = `800` + discipline/chemistry
- Success: `(offenseScore + BSM) > defenseScore`; dominant → weighted D_FOUL/HCO/SHOT; failure → O_FOUL/DEAD BALL/STEAL weights

---

### Related Documentation

- [`Dynamic_HCT_Brief.md`](../projects/Z-Completed/Dynamic_HCT_Brief.md) — archived design brief + deep specs (pass contest, play specs)
- [`FCP_System.md`](./FCP_System.md) — Full Court Press (shares loop; BIP setup + Straight Pressure FCP placement differ)
- [`BIP_System.md`](./BIP_System.md) — BIP→HCT setup coords
- [`Stopper_System.md`](./Stopper_System.md) — stopper truncation (FCP + legacy HCT)
- [`Fast_Break_System.md`](./Fast_Break_System.md) — FB executor for broken-HCT branch; shared `cutoff_resolution` with Covert Release stops
