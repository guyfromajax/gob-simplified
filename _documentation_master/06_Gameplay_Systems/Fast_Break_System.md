## Fast Break System ✅ **COMPLETE** (January 2025; Rim Runner March 2025; FB shot contest grid unification March 2026)

> **Canonical reference (Bible):** This document is the **single source of truth** for sustained Fast Break knowledge—selection logic, coordinates, defensive stops, shot attempts, constants, and file touchpoints. In-flight implementation checklists may live in `docs/To Do/FB_Playcall_Update.md`; SS&S process notes for FB shot routing live in `docs/To Do/Archive/fast_break_shot_spot_process_review.md`. If something conflicts, **treat this file as authoritative** unless the team explicitly updates both.
>
> **Planned overhaul (June 2026):** **FB Drive Cutoff & Stop Decision** (below) is the approved design for a geo-based drive resolver across all FB play keys. It **supersedes** the CR outlet-phase cutoff (Steps 5–8 in *Fast Break Resolution Flow*), the get-back-only shot-defender gates, and the point-race **`compute_fb_shot_geometry`** helper. A full doc reconciliation will follow implementation; until then, treat the new section as authoritative where it conflicts with older subsections.

**Base Constants**

1. **Defensive Stop (Covert Release)**: Legacy **`DEFENSIVE_STOP_Y_RANGE`** (±6 steal) and **`DEFENSIVE_STOP_Y_RANGE_DREB_OUTLET = 8`** (±8 ahead/y band) are **superseded** for Covert Release DREB stops. Stops now use the shared **drive-cutoff** primitive in `BackEnd/engine/cutoff_resolution.py` (same D21 arrival-time race as HCT broken-trap drives). FB tuning: **`FB_CUTOFF_PATH_CORRIDOR_DREB = 14`**, **`FB_CUTOFF_PATH_CORRIDOR_STEAL = 11`**, **`FB_CUTOFF_DEFENDER_TIME_SLACK_DREB = 1.15`**, **`FB_CUTOFF_DEFENDER_TIME_SLACK_STEAL = 1.0`** (`BackEnd/constants/fast_break_constants.py`). Steal → FB on the legacy `resolve_fast_break_logic` steal-entry path still uses the FB corridor; primary steal → FB uses **`after_steal`** (separate resolver).
2. **Ball Handler Movement (Defensive Stop/Shot)**: X: 5-10 spots toward basket, Y: ±3 spots
3. **Stopper Positioning (defensive stop only)**: 1–3 spots in front of ball handler end, same **Y** (confrontation — not the rim shot spot)
4. **Shot contest defender (all fast break shot attempts)**: Grid vs the shooter’s **final** spot (`_bh_final_x/y`, exposed as `shot_spot`). Shooter shot spot is now a tighter rim band: **x = basket.x ± uniform integer in [1, 4]** and **y = basket.y + uniform integer in [−3, +3]** (`FB_SHOT_SPOT_X_MIN/MAX`, `FB_SHOT_SPOT_Y_RANGE` in `BackEnd/constants/fast_break_constants.py`). Primary defender uses **x = shooter_x - 2** for home offense or **x = shooter_x + 2** for away offense, and **y = shooter_y + uniform integer in [−2, +2]** (`SHOT_DEFENDER_X_OFFSET`, `SHOT_DEFENDER_Y_RANGE`). In beat-stopper cases, the **second** contest defender uses the same **x** and **y = primary_y ± 3** based on his starting row (`SECONDARY_SHOT_DEFENDER_Y_OFFSET`). **Helpers:** `fast_break_shot_defender_end_coords(...)` and `fast_break_secondary_shot_defender_end_coords(...)`. **JS mirrors:** `fastBreakShotDefenderGridVsShooter()` and `fastBreakSecondaryShotDefenderGrid()` in `FrontEnd/static/js/phaser/constants/fastBreakConstants.js` for fallbacks; `animateFastBreakShotWithStopper` prefers `turnData.shot_spot` / `defender_spot` from the backend when present.
5. **Steal Entry Movement** *(legacy — superseded by `after_steal`)*: X: 5-10 spots toward basket, Y: ±4 spots (clamped 3-47). The steal → Fast Break path no longer uses this; see **After Steal (`after_steal`)** below and `after_steal_fast_break.py`. The `STEAL_ENTRY_*` constants are retained but unused on the rendered path.
6. **Outlet Pass Score Formula (Covert Release / default DREB path)**: `(PS * 0.6 + ST * 0.2 + IQ * 0.2) * random(1-6)`, scaled to 1-100 range. **Rim Runner** uses a different outlet base for the outlet contest (see **Rim Runner** under *Fast break plays* below).
7. **Fast break initiation (single roll)**: Slider **0–4** maps to probability **`{0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}`** via `fast_break_probability_from_slider()` in `BackEnd/utils/shared.py` (`SLIDER_TO_FAST_BREAK_PROB`). **Missed shot → DREB (HCO or FT):** one roll on the **rebounding team’s** `strategy_settings["fast_breaks"]` only — no second roll for Covert release. **Steal:** one roll on the **stealing team’s** `strategy_settings["aggression"]` only (that team is `def_team` at steal resolution before possession flips in `game_manager`). User playbook settings now also seed **`playbook_settings.fast_break`** with `covert_release = 50`, `rim_runner = 50`, and `triangle = 0`.

**Fast Break Resolution Flow (8 Steps)**

1. **Apply Energy Decay**
   - Apply energy decay to all active players (offense and defense) via `apply_energy_decay()`
   - **Note**: Bench recharge does NOT happen during Fast Break turns (only during HCO turns)

2. **Track Defensive Attempt**
   - Increment `off_scouting["offense"]["Fast_Break_Entries"]`
   - Increment `def_scouting["defense"]["vs_Fast_Break"]["used"]`

3. **Determine Entry Type and Set Roles**
   - **DREB Entry (shot turn, `shot_manager`)**: On the shot attempt, **one** roll: `random.random() < fast_break_probability_from_slider(def_team["fast_breaks"])` (with situational override to 0 when applicable). **No second roll** for Covert. If eligible, **`play_key_for_fast_break_entry(True)`** runs **once** (**50/50** `rim_runner` vs `covert_release` for now; `triangle` remains seeded at 0 in mode-init until enabled in playbook settings). **Covert Release only**: if eligible and key is `covert_release`, **`select_covert_release_position`** assigns the release defender (no extra probability roll). **Rim Runner / `triangle`**: all defenders crash; no release list. Key stored as **`game_state["pending_dreb_fb_play_key"]`** when miss → DREB and **`next_play_type == "FAST_BREAK"`** (consumed in resolver). **Missed FT → DREB** (`resolve_free_throw_logic`): same **single** roll using rebounding team’s **`fast_breaks`** for `FAST_BREAK` vs `HCO`.
   - **`resolve_fast_break_logic()`**: For DREB, **`fb_play_key = game_state.pop("pending_dreb_fb_play_key", None)`**; if missing (legacy/tests), fallback **`play_key_for_fast_break_entry(True)`**. Branches: **`rim_runner`** or **`triangle`** → `resolve_rim_runner_fast_break(game, fb_play_key)`; **`covert_release`** → existing Covert flow below.
   - **DREB Entry (Covert Release path only)**: 
     - Outlet passer = rebounder (from `game_state["last_rebounder"]`)
     - Outlet receiver = release player (from `game_state["last_release_player"]`) or fallback to random PG/SG/SF. **Release selection** runs **only when the pending play key is `covert_release`**: on the **prior shot turn**, `select_covert_release_position` chose the releaser (defender **farthest from the rim in x** among those **not** guarding the shooter — no second `fast_breaks` roll). **IQ reads**: roll `the_read` 1–100 → **good_release** if `the_read <` release player IQ; roll `d_read` 1–100 once → each get-back player gets **good_d_release** if `d_read <` that player’s IQ. **AG**: outlet and get-back **x-band floors** use each player’s **AG** (see **Covert Release** below). Final coords sampled in `covert_release.py` (HOME orientation; mirror **x** when the future FB offense team is away).
     - Calculate outlet pass score: `(PS * 0.6 + ST * 0.2 + IQ * 0.2) * random(1-6)`, scaled to 1-100
   - **Steal Entry** *(legacy path — superseded; steal → FB now resolves in `after_steal_fast_break.py`, see **After Steal** below)*:
     - Ball handler = stealer (from `game_state["last_stealer"]`)
     - No outlet pass (no outlet passer/receiver)

4. **Calculate Ball Handler Position After Entry**
   - **DREB Entry (Covert / generic)**: Ball handler receives outlet pass at starting position (no movement during outlet pass)
     - Priority 1: `defense_release_coords` from most recent MISS/MAKE turn
     - Priority 2: `offense_getback_coords` from most recent MISS/MAKE turn
     - Fallback: `player.coords`
   - **DREB Entry (Rim Runner / Triangle)**: After a **successful** outlet contest, sim coords for the rim runner and outlet ball handler are set from **`rim_runner_burst_phase`** (`rr_to`, `receiver_to`); `roles["ball_handler_outlet_x/y"]` match **`receiver_to`** for stop/shot geography and animation. **Denied** outlet: coords are **not** advanced (only the burst payload is present for the client).
   - **Steal Entry** *(legacy — not used by `after_steal`)*: Ball handler moves 5-10 x spots toward basket, ±4 y spots (clamped 3-47), using `last_stealer_coords` if available. Superseded — the after-steal resolver drives the stealer to a rim band instead (see **After Steal** below).

5. **Check All Defenders for Drive Cutoff**
   - Loop through **all defenders in `def_lineup`** (not just `fb_roles["defense"]`)
   - Get defender coordinates:
     - Priority: `offense_getback_coords` from most recent MISS/MAKE turn (if defender was a get-back player)
     - Fallback: `defender.coords`
   - Pre-roll BH drive target: **x** 5–10 toward basket, **y** ±3 (`ball_handler_drive_roll_x/y` in `fb_roles`; animator consumes same rolls)
   - **`best_cutoff_on_drive()`** (`cutoff_resolution.py`): walk BH straight-line drive; each defender within **`path_corridor`** (14 DREB / 11 steal-entry) gets a D21 meet point with optional **`defender_time_slack`** (1.15 DREB / 1.0 steal). Earliest intercept along the path wins (tie → closer to meet point).
   - **Aggression gate** (unchanged): `strategy_calls["aggression_call"]` → per-defender stop-attempt probability (passive 0% / normal 50% / aggressive 100%). Failed rolls skip that defender for this drive.
   - Track **closest defender overall among get-back players only** (Euclidean distance; shot-defender pool when 1–2 get-back)

6. **Determine Event Type**
   - **0 Defenders**: Always `SHOT`
   - **Cutoff meet found** (after aggression gate): **`resolve_cutoff_contest()`** → D8 moment (`_resolve_moment`, steal excluded)
     - **`POS_O`** → `SHOT` + `ball_handler_beats_defender = True` (BH reaches meet, beats stopper; animates to rim shot spot)
     - **`NEUTRAL`** → `DEFENSIVE_STOP` (BH stalled at meet — hold-up to HCO)
     - **`D_FOUL` / `O_FOUL`** → `FOUL` (non-shooting foul path; defensive stop scouting on O_FOUL)
     - **`DEAD BALL`** → turnover (lost handle at meet)
     - Meet coords stored as **`cutoff_meet_x/y`** for animator (stopper + BH end at collision point)
   - **No meet**: `SHOT`. **Shot defender only when 1 or 2 get-back players**: closest get-back by Euclidean distance; if 0 or 3+ get-back, no shot defender (defender_count = 0)

7. **Handle DEFENSIVE_STOP Result**
   - Set `offensive_state = "HCO"`
   - Build animation packet (outlet pass + defensive stop)
   - Track Fast Break stats (release player: `FB_A`, get-back players: `FB_A_D`, `FB_S_D`)
   - Track team stats (`def_scouting["defense"]["vs_Fast_Break"]["success"] += 1`)
   - Return result with `next_play_type = "HCO"`

8. **Handle SHOT Result**
   - Assign shooter (random from `[ball_handler] + offense`)
   - Assign passer:
     - If shooter is outlet receiver: passer = outlet passer (rebounder)
     - Else if shooter != ball_handler: passer = ball_handler
     - Else: passer = None
   - **Shot threshold**: Uses effective defender count. If a defender attempted a stop and failed (`ball_handler_beats_defender`), effective count = defender_count − 1 (min 0). Threshold: 0 def → 1; 1 def → base; 2+ def → base + 100 + def_chem − off_fight. Stats and animation still use actual defender_count.
   - **Shot defender pool**: Only **get-back players** (from `offense_getback` on the most recent shot) are eligible. **Only when there are 1 or 2 get-back players** is a shot defender assigned; 0 or 3+ get-back → no shot defender (defender_count = 0). If a get-back defender attempted a stop and failed (`ball_handler_beats_defender`), that defender is **excluded** from being the shot defender (closest remaining get-back is used, or none if he was the only get-back).
   - **Special Case - Ball Handler Beats Defender**:
     - If `ball_handler_beats_defender = True` (from Step 6 skill check):
       - **Stopper** uses the primary FB shot-defender spot from **`shot_spot`**; the **trail shot defender** (if any) uses the same **x** plus a **±3 y** offset based on his starting row so the sprites do not stack
       - Ball handler animates to shot spot near rim (same rim-band logic as other FB shots)
       - Client: `animateFastBreakShotWithStopper()` (uses `shot_spot` / `defender_spot` when on the turn)
       - Shot defender = closest get-back **excluding the failed stopper** (or none if no other get-back)
   - **Charge/Blocking Foul**: Only checked when there is a shot defender (defender present and defender_count ≥ 1). If 0 defenders back, no charge/block check; shot proceeds normally. When applicable, uses same attack-shot logic as half-court (`calculate_charge()`); CHARGE → possession to defense, BLOCKING_FOUL → foul on defender (SIP or free throws if bonus). Shooter and defender are animated to the shot spot; no shot-to-rim.
   - Call `shot_manager.resolve_shot()` (attack adapter) for shot resolution
   - Build animation packet (outlet pass + shot attempt)
   - Track Fast Break stats and team stats
   - If MISS → DREB: Route to `runDefensiveReboundSetup()` with current Fast Break turn data

**Long Form Documentation**

### Overview

The **Fast Break** system handles transition offense situations that occur after defensive rebounds or steals. The system determines whether a fast break results in a defensive stop or a shot attempt based on defender positioning relative to the ball handler after the outlet pass.

**Key Functions:**
- **DREB outlet**: On the **HCO shot** turn, `shot_manager` rolls FB eligibility once via **`fast_break_probability_from_slider`** on the **defensive (rebounding) team’s `fast_breaks`**, then play key; **Covert** runs `select_covert_release_position` + coords (no second roll). **Rim Runner / Triangle** skip release. `FastBreakTrigger.DEFENSE_RELEASE_CHANCES` aliases the same **`SLIDER_TO_FAST_BREAK_PROB`** table (legacy `can_trigger_from_dreb()` helper). **Rim Runner / Triangle** DREB possessions resolve in `BackEnd/engine/rim_runner_fast_break.py` after **`pending_dreb_fb_play_key`** is consumed.
- `resolve_fast_break_logic()` - Handles fast break outcome determination in `BackEnd/engine/phase_resolution.py` (delegates to Rim Runner module when DREB + play key is **`rim_runner`** or **`triangle`**)
- `capture_fast_break_animation()` - Builds animation packet in `BackEnd/models/animator.py`
- `runFastBreakSequence()` - Orchestrates fast break animation in `FrontEnd/static/js/phaser/animation/fastBreak.js`

### Fast break plays (per-play reference)

Use this subsection for **behavior and formulas by play key** (`covert_release`, `rim_runner`, `triangle`, `after_steal`). The **8-step flow** above describes the **Covert Release** DREB path in full; Rim Runner replaces that path when selected.

#### Covert Release (`covert_release`)

- **When**: DREB → `FAST_BREAK` and **`pending_dreb_fb_play_key`** (from the prior miss shot turn) is **`covert_release`** (50/50 vs Rim Runner until settings ship).
- **What**: Release defender selection, IQ/AG bands, outlet receiver coords, then **defensive stop vs shot** per Steps 4–8 (unified drive cutoff + D8 contest, shot via `resolve_shot`).
- **Code**: `BackEnd/engine/covert_release.py`, `resolve_fast_break_logic()` (Covert branch), `shot_manager` for Covert-only release/get-back coords on the prior shot turn.

##### Get-back defender read on outlet pass (step 0)

On the outlet pass step (CR FB step 0), how each get-back defender positions themselves depends on the outlet pass quality:

- **Sloppy outlet (`outlet_score < 50`)** — legacy/default behavior. Get-back defender 1 takes the cut-off spot near the receiver; get-back defender 2 (if present) takes the same-side `lowPost` spot from `HCO_STRING_SPOTS`. No read required.

- **Sharp outlet (`outlet_score >= 50`)** — defenders must make a read to attempt the stop. Only **one** defender can take the cut-off; the other defends the basket.

**Eligibility filter.** A defender is eligible to attempt the stop only if their x is at or past the receiver's x in the attacking direction:
- Home offense (attacks `HOME_RIM` at x=91): eligible iff `defender.x >= receiver.x`.
- Away offense (attacks `AWAY_RIM` at x=9):  eligible iff `defender.x <= receiver.x`.

Defenders behind the receiver (in the attacking direction) are ineligible and **auto-retreat to basket defense** without attempting a read.

**Order of attempts.** Among eligible defenders, the **closest to the receiver** (Euclidean) attempts the read first. Exact ties → random choice.

**The read.** `player_read(defender)` (from `BackEnd/utils/shared.py`):
```
score = ((IQ * 0.8) + (CH * 0.2)) * random.randint(1, 6)
```
Threshold: **`outlet_score * 3`**. Pass iff `score >= threshold`.

**Outcomes:**
1. **First defender's read passes** → they take the cut-off stop position; the second defender (if any) **skips their read** and retreats to basket defense.
2. **First defender's read fails** → they retreat to basket defense; the second eligible defender (if any) attempts their own read. If passes → cut-off; if fails → basket defense.

**Cut-off stop position** (unchanged): `(receiver.x ± 2 toward attacking basket, receiver.y)`.

**Basket defense spot**: random within a box near the rim being attacked.
- Home offense: x ∈ [87, 91], y ∈ [20, 30].
- Away offense: x ∈ [9, 13], y ∈ [20, 30].

When two defenders both retreat to basket defense, the second defender's spot is enforced to be **≥2 grid units offset on both axes** from the first so they don't stack at the same point. Up to 5 random retries; deterministic offset fallback if the box can't accommodate.

**Implemented in**: `_build_outlet_pass_step` in `BackEnd/engine/covert_release_step_emitter.py`, with helpers `_order_defenders_for_stop` and `_basket_defense_spot` in the same file.

#### Rim Runner (`rim_runner`)

- **When**: DREB → `FAST_BREAK` and **`pending_dreb_fb_play_key`** is **`rim_runner`**.
- **Designation**: Optional per team — `game_state["rim_runner_by_team_id"][str(team_id)]` = player id (set from lineup / `simulate-quarter` payload). If omitted, finisher = offensive player **closest to the attacking basket** at DREB (with transfer rule when the designated player is the rebounder; see implementation). Lineup UI: optional Rim Runner select on **Set Lineup**; URL params `home_rim_runner_player_id` / `away_rim_runner_player_id` → game payload.
- **Outlet chain (sim + animation)**: Offensive **outlet target** `(tx, ty)` uses fixed outlet x by side (`45` home offense, `55` away offense) and the opposite vertical lane from the rim runner: `ty = 15` when RR starts in the upper half (`rr.y > 24`), else `ty = 35`. The **outlet receiver** is the offensive player (not the rim runner) closest to that target. If that player is the **rebounder**, there is **no outlet pass** (`roles["outlet_passer"] = null`); the rebounder dribbles to `(tx, ty)` in parallel with the burst-phase animation. Otherwise **`outlet_passer`** = rebounder and **`outlet_receiver`** = that closest player. `roles["rim_runner_sequence"]` is **true** only for **`rim_runner`**, not **`triangle`**.
- **RR destination (`rr_to`)**: RR targets the offense `basketSpot` (`HCO_STRING_SPOTS`, mirrored for away offense). Roll `movement_factor = random.randint(1, 100)` vs **`0.6*AG + 0.2*IQ + 0.2*CH`**. **Success**: RR uses the `burst` archetype. **Fail**: RR uses the `sprint` archetype. The old same-side-wing clamp and x-delta cap are sunset; RR movement is now controlled by backend UESS step timing and AG-scaled archetype rates.
- **RR Step 0 advance**: Step 0 is a fixed **1.0 game-second** advance toward `rr_to`. Backend interruption math computes the RR end coord as `archetype_rate × AG_scale × 1.0` along the path to `basketSpot`; RR is not forced to the final target unless his rate/distance allows it. The outlet-pass step then continues RR toward the same `basketSpot` using the same `burst` / `sprint` archetype chosen in Step 0.
- **Dynamic RR x base**: Retained only as diagnostic metadata (`dynamic_rr_x_base`) when the prior shot has `ball_bounce_x` in the mid-court band (**home** `25 < x < 50`; **away** `50 < x < 75`). It no longer changes `rr_to`, because `rr_to` is always `basketSpot`.
- **`roles["rim_runner_burst_phase"]`**: Structured payload for the client: `rr_id`, `rr_from` / `rr_to`, `burst_success`, `burst_delta`, `movement_factor`, `burst_threshold`, `dynamic_rr_x_base`, `skip_outlet_pass`, `outlet_passer_id`, `outlet_receiver_id`, `receiver_to` `{x,y}`, `outlet_defender_id`, `outlet_defender_to` (closest outlet contest defender tweens to **passer x ± 2** same **y** as passer; home **+2**, away **−2`), `other_players` (everyone not passer, that defender, rim runner, or outlet receiver). **Offense (rebounding team):** **x** toward basket **`random.randint(1, 4)`**, **y** unchanged. **Defense — get-back** (from prior shot's `offense_getback`, excluding outlet contest defender): **x** **15** spots toward the attacking basket, clamped so they do not cross the rim **x**; **y** up to **6** toward the rim runner's burst **y** (`rr_to.y`), without crossing past the RR in either vertical direction. Present on **both** successful and **denied** outlet turns so the sprint/setup can still animate when **`rim_runner_outlet_failed`** is true.
- **Resolution (high level)**: Dedicated module **`resolve_rim_runner_fast_break()`** — build **`rim_runner_burst_phase`** + outlet roles → outlet contest → on success, apply rim runner + ball handler **coords** to burst targets → sim **burst** (`fb_open`) → ball-handler IQ read → pass vs hold → if pass: open lane → fast break shot; if not open → intercept tiers / bat OOB (`rim_runner_bat_oob`, SIP) / completion to shot. Uses team attrs **`fb_efficiency`** / **`fb_opp_modifier`** (clamped **−10…+10**) and `random.randint(1,6)` where applicable.
- **Outlet contest (step A)**: Offense: `(PS*0.5 + ST*0.3 + IQ*0.2) * d6` vs defense: `(IQ*0.5 + OD*0.3 + ST*0.2) * d6`; offense adds **`+3 × fb_efficiency`**, defense adds **`+2 × fb_opp_modifier`**; if offense **≤** defense, settle to HCO — turn is still `DEFENSIVE_STOP` with **`rim_runner_outlet_failed: true`**, `defender` = outlet contest defender, text *“Outlet denied — settling…”* (see **client** below: this path does **not** use the generic fast-break defensive-stop animation or **`Great Stop!`**).
- **Burst**: Offense `(AG*0.7 + IQ*0.3) * d6` vs primary defender — get-back pool: `(IQ*1.0 + AG*0.5) * d6`; else `(IQ*0.5 + AG*0.5) * d6`. **`fb_open`** if offense score **>** defense score.
- **Read**: `IQ * d6` vs threshold **`200 - 5×fb_efficiency`** (offense team). **Aggression** (offense `strategy_settings`, ≥3 = aggressive) weights wrong-read pass vs hold.
- **Pass / shot / events**: Open lane → FB shot (Rim Runner shooter, existing `resolve_shot` attack path). Forced pass when not open: intercept roll vs **`250 - fb_opp_modifier`** / **`200 - fb_opp_modifier`** tiers; bat OOB announces **“Batted Ball Out Of Bounds!”** (`RIM_RUNNER_BATTED_OOB`). Full detail matches `rim_runner_fast_break.py`.
- **Universal FB interception / bat contact point (client)**: All FB pass interceptions and batted-pass-out-of-bounds branches use the same contact-point helper keyed off the **intended receiver pass target** when present, falling back to the receiver’s live grid if not. The passer uses the same priority (intended pass source/target if present, otherwise live grid at pass time). Contact point:
  - `interceptor.x = receiver.x + 3` if `passer.x > receiver.x`, else `receiver.x - 3`
  - `interceptor.y = receiver.y + 3` if `passer.y >= receiver.y + 3`
  - `interceptor.y = receiver.y - 3` if `passer.y <= receiver.y - 3`
  - otherwise `interceptor.y = receiver.y`
  - Interceptions attach the ball at that contact point; batted passes hit that point and then continue to the **nearest sideline/baseline** based on the interceptor location.
- **Client — outlet denied (`rim_runner_outlet_failed`)**: After **`animateRimRunnerBurstPhase`**, the outlet pass is skipped. **`animateRimRunnerOutletDeniedBeat`** (in `fastBreak.js`): ball remains on the **outlet passer**; any burst tween on the **outlet defender** is cleared so they move to **`outlet_defender_to`** (**passer x ± 2** toward the pass, same **y** as passer — HOME grid); announcement **“FB Outlet Pass Denied!”** with the defender’s headshot; after the standard FB hold, **all players except** outlet passer, outlet receiver, and outlet defender run a **long horizontal drift** toward the offense basket (same idea as hold-up) while the **receiver** tweens to the catch spot; drift stops when the receiver arrives; burst tweens stopped for those players use **`Promise.allSettled`** in **`animateRimRunnerBurstPhase`** so the sequence does not reject. Then **`runPass`** to the receiver (if passer ≠ receiver; dribble-outlet / **`skip_outlet_pass`** keeps one player with the ball). **Phase 2** calls **`finalizeRimRunnerNonShotTurn`** only — **no** **`animateDefensiveStop`**, **no** **`Great Stop!`**. Next HCO follows normal half-court entry (**`startNextHalfCourtOffense`**).
- **Client — hold-up (no lane pass after successful outlet)**: **`animateRimRunnerHoldUpLeadIn`** — ball handler (outlet receiver): **+6** grid **x** toward the basket, **+8 y** if **`y < 25`** else **−8 y**. **Everyone else** tweens in a **straight horizontal** line toward the offense basket (**y** fixed at current grid row, **x** up to **40** grid toward the rim on a long easing duration). Those horizontal tweens are **stopped** when the ball handler **finishes** his move; then grid coords are synced from pixels. **No** **`animateDefensiveStop`** / top-of-key. Phase 2 **`finalizeRimRunnerHoldUpToHco`** sets **`scene._rimRunnerHoldUpInboundPass`** when ball handler ≠ offensive **PG**, then **`finalizeRimRunnerNonShotTurn`**. On the **next HCO** turn, **`playTurnAnimation`** runs **`runRimRunnerHoldUpSetupTween`**: all players except the ball handler tween to skeleton **step 0**; when **PG** reaches step 0, **`runPass`** from the ball handler’s hold-up spot to **PG**; then remaining setup completes and the ball handler tweens to step 0 (ball stays with **PG**). If ball handler **is** PG, normal **`runSetupTween`** only. **`Great Stop!`** remains for **Covert** / **`stopper_id`** stops only, not RR hold-up. **Lineup invariant:** both teams always field **PG, SG, SF, PF, C** (one each), so offensive **PG** exists for the hold-up → HCO inbound pass path.
- **Rim-runner sprint barrier (dead-air fix, client)**: In the burst phase (`animateRimRunnerBurstPhase`) and the triangle setup phase (`animateTriangleSetupPhase`), the RR's long downcourt sprint is **not awaited** when a downstream stage will re-drive the RR from its live position — the lane pass (`animateRimRunnerLanePass`) or the triangle setup / shot decision lead-in, all of which spawn a fresh RR tween. The phase stops the RR sprint (avoids a double-tween) and awaits only the other movers, eliminating the dead air between the outlet-receive and the pass-to-RR. The dispatcher computes this up front as `rrReDrivenAfterBurst` / `rrReDrivenAfterTriangleSetup` (from `phase2Kind` + `triangleSetupRequired`) and passes it in. Endings that require the RR to settle (hold-up, defensive stop) keep the full barrier. Independent of the global `isCriticalEventPatternEnabled()` flag (left off).
- **Code**: `BackEnd/engine/rim_runner_fast_break.py`; entry from `resolve_fast_break_logic()` when DREB + `RIM_RUNNER`.

#### Triangle (`triangle`)

- **Status**: UESS-migrated for burst, outlet, denied-outlet, **lane-pass quick shot**, and full setup/decision branches. Backend emitter: `BackEnd/engine/triangle_step_emitter.py` (setup tree) plus shared `append_lane_pass_to_rr_resolution_steps` in `rim_runner_step_emitter.py` (open-lane pass-ahead). *(Originally specced in the now-retired `FB_Triangle_Play_Spec.md`, folded into this Bible June 2026.)*
- **Phase architecture (design framing)**: Triangle is a Fast Break play *family* inside the universal FB system, not a bespoke stack — it reuses shared FB routing, UESS contract rules, carry-forward snapshots, and shot-resolution handoff, but defines its own phase graph: `entry` (RR-style DREB entry, outlet receiver placement, outlet contest, result fork) → `rr_read` (post-outlet RR lane-pass read) → `setup` (Triangle target movement after the lane pass is declined) → `decision` (BH decision tree) → `finish` (pass/shot/HCO handoff). The denied-outlet branch stays owned by the shared RR denied path. Once a phase hands off, prior phases must not re-apply old destinations; live carried-forward positions remain authoritative. Triangle uses existing `HCO_STRING_SPOTS` labels (corners, wings, low/mid/high posts, `topLane`/`midLane`/`basketSpot`, `apex`/`bird`). This per-play-phase-map approach is the recommended long-term FB architecture.
- **Entry**: Triangle drafts off the Rim Runner DREB entry. It uses the same RR burst, outlet receiver placement, outlet contest, and denied-outlet branch. If the outlet is denied, Triangle uses the same denied-outlet comeback branch and then enters `HCO` exactly as RR does.
- **RR archetype in the outlet pass step (Triangle-only)**: In the burst step the RR uses its rolled `burst` / `sprint` archetype (same as RR). In the **outlet pass step**, Triangle forces the RR to **`sprint`** regardless of the burst-step roll, so the RR settles out of the burst once the outlet pass goes (Rim Runner instead carries the burst-step archetype forward). Implemented via the `rr_archetype_override="sprint"` argument to the shared `_build_outlet_pass_step` in `triangle_step_emitter.py`.
- **RR read gate**: After a successful outlet, Triangle still performs the RR lane-pass read first. It uses the same `burst_offense_score`, `burst_defense_score`, `correct_read`, and `pass_attempted` logic as RR, except the open-lane threshold is stricter: `fb_open = (burst_offense_score * 0.8) > burst_defense_score`.
  - **`pass_attempted = True`**: Resolution matches Rim Runner (outlet receiver → RR lane pass → attack shot). **`animation_steps`** are built via **`append_lane_pass_to_rr_resolution_steps`** (burst → optional outlet → lane pass → `_build_shot_motion_step` → skeleton post-shot sub-steps). Turn has **`rim_runner_pass_attempted`** and **no** `triangle_setup_phase`. Frontend must use schema playback (`NEW_PLAYBACK_ENGINE`); legacy `fastBreak.js` `animateRebound` on the MISS turn causes double rebound animation if steps are missing.
  - **`pass_attempted = False`**: Triangle enters its own setup/decision flow below (`triangle_setup_phase` on roles).
- **Triangle setup**:
  - Two remaining offensive players become corner players and sprint to `upper corner` / `lower corner` (`HCO_STRING_SPOTS` labels).
  - Ball handler sprints to `upper wing` if `y > 25`, else `lower wing`.
  - Rim runner sprints to same-side `upper lowPost` / `lower lowPost`.
  - Trailer (rebounder / outlet passer) sprints to the opposite wing.
  - Defenders: closest-by-x defender to the offensive basket tracks the rim runner via skeleton HCO man-matchup placement; second-closest-by-x tracks the ball handler the same way; the other three target random lane spots from `lower/upper lowPost`, `lower/upper midPost`, `lower/upper highPost`, `basketSpot`, `midLane`, `topLane`, `lower/upper bird`, and `lower/upper apex`.
  - RR defender, BH defender, and helper defenders all sprint to their setup targets.
- **Triangle setup advance trigger**: BH reaches his setup spot; T is BH traversal at `sprint` rate, AG-scaled.
- **Triangle decision tree**:
  - `decision = random.randint(1, 8)`
  - `1-2`: pass to RR at lowPost -> RR inside shot
  - `3`: wait for same-side corner arrival -> pass to corner -> corner 3
  - `4`: BH wing 3
  - `5-6`: BH drives to same-side lowPost; RR moves to `midLane`; drive branch then resolves:
    - `drive_decision 1-2`: BH attack shot
    - `drive_decision 3-4`: BH -> RR at `midLane` -> RR inside shot
    - `drive_decision 5`: BH -> same-side corner -> corner 3
  - `7-8`: enter `HCO`
- **Decision branch carry-forward**:
  - For all non-drive branches, RR remains at lowPost.
  - Trailer remains at opposite wing unless interrupted by the HCO handoff.
  - The two matched defenders keep tracking RR/BH assignments; all other defenders either continue to their assigned location or hold if already there.
- **Shot-defender rule for Triangle corner 3s**: only calculate a shot defender if a defender is within Euclidean distance `6` of the shooter.
- **No-defender corner-3 override**: if no shot defender is present on a Triangle corner 3, calculate shot score as normal but use a Triangle-specific make threshold: make if `shot_score > (190 - offense_team.fb_efficiency)`, else miss. If a shot defender is present, use normal shot resolution logic.
- **HCO handoff rule**: if Triangle enters `HCO`, all players carry forward from their live positions at the HCO decision boundary. If the current ball handler is not the PG, once the PG reaches HCO step-0 location, animate a pass from the current ball handler to the PG before normal HCO setup completes.

#### After Steal (`after_steal`) — UESS migrated (May 2026)

- **When**: Fast break entered from **steal** (not DREB outlet). `play_key_for_fast_break_entry(False)` → **`after_steal`**.
- **What (current resolver — replaces the legacy steal-entry/stopper path):** No outlet; ball handler = stealer. Resolution is in `BackEnd/engine/after_steal_fast_break.py` (`resolve_after_steal_fast_break`), **not** the legacy steal-entry movement + ±6 defensive-stop skill check in Steps 4–8:
  - **BH (stealer) target:** drives to a rim band — `x = basket.x ± random(2,3)`, `y ∈ [19, 31]` (AWAY basket x=9 → x∈[11,12]; HOME x=91 → x∈[88,89]).
  - **Defenders:** **all five** sprint to a single target = `BH_target_x ± 2` toward basket, same y. Per-defender traversal time = `euclid(start, target) / AG-sprint-rate` (`_ag_grid_per_game_sec`); smallest time = **first arriver**. If `t_first < t_shooter`, the other defenders **freeze** at their interpolated positions (clamped no closer than `DEFENDER_FREEZE_CLAMP_GRID_SPOTS = 6` from basket, never pulled backward from start).
  - **Contested check** (at `t_shooter`): the defender whose x is closest to basket; if past the shooter's x → **CONTESTED** (that defender is the shot defender), else **UNCONTESTED**.
  - **Shot type:** **`attack`** (drive-to-the-rim finish — the stealer sprints and finishes himself). Scores with **Attack** attribute weights (`SC·5, AG·2, ST·1, IQ·1, CH·1` — agility-based rim finishing) and the **attack** defensive-foul thresholds, **not** Inside (`SC·6, ST·2, …` post weights). `is_paint` stays **True** (the finish is physically in the paint → the rim contest is ID-focused paint defense), matching `resolve_shot`'s FB attack path. *(Changed from `inside` — June 2026; a steal-and-go is a drive, not a post-up.)*
  - **Shot resolution:** CONTESTED → `shot_manager.calculate_shot_score(apply_defense=True)`, made if `shot_score ≥ shot_threshold`; UNCONTESTED → `apply_defense=False`, **automatic MAKE** (OREB-putback uncontested rule). **Outcome is MAKE or MISS only — there is no `DEFENSIVE_STOP` on this path.**
  - **Other 4 offensive players:** sample 4 unique spots (no collisions) from the 11-name `AFTER_STEAL_OFFENSE_SPOT_NAMES` HCO setup list (mirrored for away).
- **UESS schema**: After-steal FB is fully migrated to the unified animation step schema. **No frontend choreography logic** — all positions, transitions, announcements, and SFX are backend-emitted. FE is a pure renderer (`runSchemaPlaybackTurn`).
- **Emitter**: `BackEnd/engine/after_steal_fast_break_step_emitter.py::build_after_steal_fast_break_animation_steps`. Routed via `resolve_fast_break_logic` (`phase_resolution.py`) — same pattern as `covert_release` schema emission, in the same block.
- **FE gate**: `MIGRATED_FB_PLAYS` in `AnimationEngine.js` includes `"after_steal"` (alongside `covert_release`, `rim_runner`, `triangle`); the FE step dispatcher consumes the schema steps directly.
- **Legacy code removed**: `animateStealEntry()` in `fastBreak.js`, the `is_steal_entry` routing branch, and the `STEAL_ENTRY_*` constant imports were deleted during migration. The FE constants in `fastBreakConstants.js` remain for reference but are no longer consumed.

**Step schema (MAKE / MISS / BLOCK — the only outcomes):** built by `after_steal_fast_break_step_emitter.build_after_steal_fast_break_animation_steps`.

| Step | Purpose | Key fields |
|---|---|---|
| 0 — drive (single step) | Stealer sprints to his shot spot **ending in shot motion**; all defenders sprint to the single defender target (first-arrival freeze); the other 4 offensive players sprint to their sampled HCO setup spots; "Fast Break!" secondary announcement on `start` | `action[stealer] = "shoot"`, `archetype[stealer] = "sprint"`, others `action/archetype = "sprint"`, `end.coords` = resolver `after_steal_end_coords`, `ball.owner_player_id = stealer`, `advance_trigger` gates on stealer reaching `bh_target`, `start.announcement = "Fast Break!"` (`_build_drive_step`) |
| 1 — ball flight | Variant-aware flight to rim; launch SFX on release | post-shot sub-step; `sfx_on_ball_release = shot_launch_sfx(...)`; `sfx_on_ball_arrival = shot_result_sfx(variant, result)` (omitted for RATTLE) |
| 2+ — variant sub-steps | RATTLE hops / BANK_MAKE settle / BANK_MISS graze / AIRBALL OOB | Emitted by skeleton's `_build_post_shot_sub_steps`; per-hop `rattle-leather.wav` for RATTLE |
| N — hold (MAKE) | "Fast Break Score!" announcement (or "...And 1!") at the ball's settle point | `start.announcement.text` overridden in-place by `_override_fb_make_announcement` from skeleton's default "It's Good!" |
| N — bounce (MISS) | Ball bounces from rim to backend-stamped bounce spot; "Shooting Foul!" stamped on `end.announcement` if miss + defensive shooting foul | `_stamp_shooting_foul_on_miss_end` (shared helper) |

> **No defensive-stop branch.** The after-steal resolver returns only MAKE/MISS (BLOCK rendered as a miss outcome); there is no `DEFENSIVE_STOP`, no step-back-to-top-of-key step, and no "Great Stop!" announcement on this path (unlike Covert Release / Rim Runner DREB breaks, which can stop). The emitter (`build_after_steal_fast_break_animation_steps`) only handles `("MAKE", "MISS", "BLOCK")`.

**Make announcement text:** Per design, steal-FB makes read as "Fast Break Score!" not "It's Good!" (overrides skeleton's default). The emitter post-processes the make-hold step's `start.announcement.text` from "It's Good!" → "Fast Break Score!" (and the and-1 variant). Helper: `_override_fb_make_announcement` in the after_steal emitter.

**Stat tracking:** unchanged. Each after_steal FB increments `scouting_data.offense.fast_break_plays["after_steal"]` (`A` on attempt, `S` on success) and the team-level `Fast_Break_Entries` aggregate; the four play keys (CR, RR, Triangle, AFTER_STEAL) all roll up into the team's overall Fast Break stats.

**DREB miss chaining:** If a migrated Fast Break shot (`covert_release`, `rim_runner`, `triangle`, or `after_steal`) misses or is blocked and the defense secures the rebound, `GameManager.simulate_macro_turn()` promotes the defensive rebound into a discrete `DREB` turn before routing to the original next play (`HCO` or `FAST_BREAK`). The Fast Break shot turn ends at the schema post-shot bounce / `SHOT_ATTEMPT` stop; the separate `DREB` turn is the authority for rebound capture and ball ownership.

### When Fast Break Activates

**Trigger Conditions:**
- After **DREB** on a miss when the **single** `fast_breaks` roll succeeded on the **shot attempt** (or FT miss path); **`pending_dreb_fb_play_key`** selects **Covert** (requires successful Covert release position) or **Rim Runner** / **Triangle** (no release). **`next_play_type = "FAST_BREAK"`** no longer requires a non-empty defense release list.
- After steals with fast break chance (`FastBreakTrigger.can_trigger_from_steal()`)
- Set via `next_play_type = "FAST_BREAK"` in turn result

**State Flow:**
1. DREB or STEAL → Fast break chance determined
2. FAST_BREAK turn generated with `fast_break = true` flag
3. Backend determines outcome (DEFENSIVE_STOP or SHOT) based on defender positioning
4. Frontend animates outlet pass, then defensive stop or shot attempt

### Possible Outcomes

Fast breaks can result in:

1. **Defensive Stop (DEFENSIVE_STOP)**
   - Defender is ahead of ball handler after outlet pass AND within y-range (**±8** DREB/outlet; the **±6** "steal" band is legacy — see **After Steal**)
   - Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
   - Closest defender ahead becomes "stopper" and is placed 1-3 spots in front of ball handler
   - Routes to: HCO (half court offense)

2. **Shot Attempt (SHOT)**
   - No defender ahead of ball handler after outlet pass OR defender not within the applicable y-range (±6 vs ±8)
   - Ball handler moves to **rim shot spot** (see `capture_fast_break_animation`); not the old “outlet + 5–10 only” path for contested shots
   - **Shot defender (if any)**: Only when there are **1 or 2 get-back players**; pool is **get-back players only**. Closest get-back by Euclidean distance becomes shot defender, or—if the ball handler **beat** a stopper—the closest **remaining** get-back after excluding the failed stopper. If 0 or 3+ get-back, or the only get-back was the failed stopper, no shot defender. **Animation end coords** for the primary shot defender always come from the shooter-relative FB shot-defender rule (see **Shot contest grid** under *Animation Sequence* below); beat-stopper path adds a second defender at the same **x** and **±3 y** from the primary defender.
   - Routes to: Standard shot resolution flow (MAKE, MISS, or **BLOCK** — block reconciliation can run on attack shots; see Block System)

### Charge and Blocking Foul (Fast Break Shot Only)

- **When checked**: Only when there is a shot defender defending the attempt: defender is assigned and `defender_count ≥ 1`. If **0 defenders back**, the charge/block check is **skipped** and the shot is resolved normally (make/miss/block).
- **How**: Same as attack shots in half-court. Before make/miss, `calculate_charge(shooter, defender, off_team, def_team)` runs. It uses shooter/defender attributes and team chemistry/discipline; thresholds determine the call.
- **CHARGE** (foul on offense): Possession flips to defense; next play is side inbound. No shot attempt.
- **BLOCKING_FOUL** (foul on defense): Foul recorded on defender; next play is SIP or FREE_THROW if bonus. No shot attempt.
- **Animation**: For either call, shooter and defender are animated to the shot spot near the basket; no ball-to-rim. Announcement ("Charge!" / "Blocking foul on X!") runs in finalizeTurnAfterAnimation.

### Blocks on Fast Break Shots

When a Fast Break shot is **blocked** (block reconciliation in `shot_manager.resolve_shot()` returns BLOCK), the turn has `result_type === "BLOCK"` and is treated as a **shot attempt** for animation, not a defensive stop.

**Routing (frontend):**
- In `runFastBreakSequence()` (fastBreak.js), Phase 2 branches on `result_type`. BLOCK is grouped with MAKE and MISS: `if (result === "MAKE" || result === "MISS" || result === "BLOCK")` → shot path (`animateFastBreakShot` or `animateFastBreakShotWithStopper`). Previously BLOCK fell through to the `else` and ran `animateDefensiveStop()`, so the fast break shot (run to rim + shot) never played.
- **Fix**: BLOCK now follows the same shot-attempt flow as MAKE/MISS so the run to the basket and shot motion always animate; then outcome handling runs for block (bounce from block spot, block announcement, rebound).

**Animation (shot target and outcome):**
- **Shot target**: When `result_type === "BLOCK"` and the backend provides `ball_bounce_x` / `ball_bounce_y` (block spot in grid), the ball is animated to that block spot instead of the rim. Otherwise the rim is used.
- **After the shot**: Block announcement (`announceGameEvent('BLOCK', ...)`), transition to Rebound, then `bounceFromRim(scene, ballSprite, blockSpotGrid, ...)` using the block spot (or basket if block spot missing). Rebound and DREB setup then match the MISS path (`animateRebound`, `runDefensiveReboundSetup` when `rebound_type === "DREB"`).
- **With-stopper path**: `animateFastBreakShotWithStopper()` uses the same logic: block spot as shot target when present, block announcement and bounce from block spot, then same rebound/DREB handling.

**Backend:**
- Block reconciliation runs for inside/attack shots (see Block System). On BLOCK, the turn result includes `result_type: "BLOCK"`, `ball_bounce_x` / `ball_bounce_y` (from the block spot), `rebounderId`, `rebound_type`, and other rebound fields. The frontend uses `ball_bounce_x`/`ball_bounce_y` for both the shot target and the bounce origin so the ball does not snap to the wrong side.

### Shot Threshold When Defender Attempts Stop and Fails

- For **shot difficulty only**, defender count is reduced by 1 when a defender **attempted a stop and failed** (`ball_handler_beats_defender = True`). Effective count = max(0, defender_count − 1).
- **Example**: 1 defender back, they attempt stop and lose → effective count = 0 → shot threshold = 1 (same as no defenders). Stats and animation still use actual defender_count = 1.

### Coordinate System and Player Positioning

**Coordinate Orientation:**
- All coordinates stored in **HOME orientation** (basket at x=90 for home, x=10 for away)
- Frontend flips coordinates for away team display
- Backend calculations always use HOME orientation for consistency

### Covert Release (DREB → outlet only)

Steal-initiated fast breaks **do not** use Covert Release. Play-type naming (e.g. “Covert Release”) applies only to **DREB → outlet** paths.

**Selection (summary)**  
1. Defender guarding the shooter cannot release.  
2. Among other defenders, choose the one **farthest from the basket being attacked** in x (HOME): home team shooting → lowest x on defense; away team shooting → highest x on defense; ties → random.  
3. **`the_read`**, **`d_read`**, **`good_release`**, **`good_d_release` per get-back** — see Step 3 in **Fast Break Resolution Flow** above.

**AG → x floors (HOME, when the fast-break offense team is home)**  
These set the **lower** end of random x; upper bounds and y come from the IQ bands below.

| Role | AG | Floor label | Value |
|------|-----|-------------|--------|
| **Outlet / release player** | AG ≥ 80 | `x_min` | 50 |
| | 60 ≤ AG < 80 | `x_min` | 47 |
| | AG < 60 | `x_min` | 45 |
| **Each get-back player** | AG ≥ 80 | `def_x_min` | 55 |
| | 60 ≤ AG < 80 | `def_x_min` | 53 |
| | AG < 60 | `def_x_min` | 50 |

**IQ → random bands (after floors)**  
Random integer coords; **x** is mirrored with `100 - x` when the **future** fast-break **offense** team is **away** (same as before); **y** is not mirrored.

| Player | Condition | x range (HOME, home FB offense) | y range |
|--------|-----------|----------------------------------|---------|
| Release (outlet receiver) | `good_release` | `x_min` – 55 | 18 – 32 |
| Release | not `good_release` | `(x_min - 5)` – 50 | 22 – 30 |
| Get-back | `good_d_release` | `def_x_min` – 60 | 22 – 30 |
| Get-back | not `good_d_release` | `(def_x_min - 5)` – 60 | 18 – 32 |

Implementation: `BackEnd/engine/covert_release.py` — `release_x_min_from_ag`, `getback_def_x_min_from_ag`, `sample_release_coords`, `sample_getback_coords`, `player_ag`.

**Outlet Receiver (Ball Handler) Starting Coordinates:**
- **Priority 1**: `defense_release_coords` from most recent MISS/MAKE turn (outlet receiver is typically a release player). Sampled via **`covert_release.sample_release_coords(good_release, will_be_home_fb_offense, ag)`** with **release player’s AG**.
- **Priority 2**: `offense_getback_coords` from most recent MISS/MAKE turn (if ball handler was a get-back player)
- **Fallback**: `player.coords` (current position on court)

**Get-Back Defender Coordinates:**
- **Priority**: `offense_getback_coords` from **most recent** MISS/MAKE turn only — **`covert_release.sample_getback_coords(good_d, will_be_home_fb_offense, ag)`** per get-back player (**that player’s AG**)
- Only defenders who were actually get-back players in the turn that triggered the fast break
- **Fallback**: `defender.coords` (current position on court)

**Example from Logs:**
```
Outlet Receiver: x=55, y=23 (from defense_release_coords)
Get-Back Defender: x=57, y=34 (from offense_getback_coords)
Y Difference: |34 - 23| = 11 (exceeds ±6 steal band and ±8 DREB/outlet band)
Result: SHOT (defender is ahead in x but NOT within y-range)
Note: Even though defender at x=57 is ahead of ball handler at x=55, they are 11 y-coords 
away, so it becomes a shot attempt instead of defensive stop.

Another Example:
Outlet Receiver: x=55, y=23 (from defense_release_coords)
Get-Back Defender: x=57, y=25 (from offense_getback_coords)
Y Difference: |25 - 23| = 2 (within ±6 and ±8 y-bands)
Result: DEFENSIVE_STOP (defender at x=57 is ahead AND within y-range, distance: 2)
```

### Defensive Stop vs. Shot Attempt Determination

> **Legacy (pre–June 2026 overhaul):** The outlet-phase drive cutoff below is **removed** by the approved **FB Drive Cutoff & Stop Decision** section. Kept for reference until implementation lands.

**Logic (HOME Orientation):**

**Home / Away orientation:** Drive target is always toward the attacking basket (home +x, away −x). Cutoff geometry is orientation-agnostic — it uses the BH start→target segment, not a fixed “ahead in x” gate.

**Drive Cutoff (Covert Release — legacy outlet-phase; superseded):**

Shared module: `BackEnd/engine/cutoff_resolution.py` (also used by HCT `_do_broken_hct_cutoff`).

1. BH drive from outlet position toward pre-rolled target (5–10 x toward basket, ±3 y).
2. Each defender in `def_lineup` with coords (get-back priority) is evaluated if within **`path_corridor`** perpendicular distance of the drive segment.
3. **Aggression gate**: each candidate rolls `stop_attempt_prob` from `strategy_calls["aggression_call"]` (passive 0 / normal 0.5 / aggressive 1.0).
4. **`cutoff_meet_point()`**: D21 arrival-time race along the segment; defender wins a step if `t_def <= t_mover × defender_time_slack`.
5. **`best_cutoff_on_drive()`**: earliest meet progress wins; tie-break closer defender-to-meet distance.
6. On meet → **`resolve_cutoff_contest()`** (D8 `_resolve_moment`, steal excluded) → **`map_cutoff_outcome_to_fb()`**:
   - `POS_O` → SHOT + `ball_handler_beats_defender`
   - `NEUTRAL` → DEFENSIVE_STOP
   - `D_FOUL` / `O_FOUL` → FOUL
   - `DEAD BALL` → turnover

**FB vs HCT tuning:** FB uses wider corridor (14 vs ~11 implicit) and 15% defender time slack on DREB (`FB_CUTOFF_*` constants). HCT uses standard AG rates; FB sprint rates for BH and cutoff defenders.

**Animation when ball handler beats stopper (`POS_O`):**
- Stopper at **`cutoff_meet_x/y`**; BH continues to rim **`shot_spot`**
- Trail shot defender uses unified FB shot-contest grid (see **Shot contest grid**)
- Failed stopper excluded from shot-defender pool

**Multiple defenders on the drive lane:** Any defender with a valid meet is considered; the earliest intercept along the path wins (not merely closest-to-BH at outlet).

**Critical Implementation Detail - Defender Assignment (Get-Back Only, 1 or 2):**
- **Backend Calculation**: In `phase_resolution.py`, `closest_defender_overall` is tracked **only among defenders in `getback_player_ids`** (get-back players from the most recent shot). A shot defender is assigned only when `len(getback_player_ids) in (1, 2)`; otherwise `fb_roles["defender"] = None` and `fb_roles["defender_count"] = 0`. When `ball_handler_beats_defender` is True, the stopper is excluded and the closest remaining get-back is chosen (or none).
- **Shot Resolution**: `resolve_shot()` in `shot_manager.py` **respects** the already-set `fb_roles["defender"]` from phase resolution.
- **Why This Matters**: Only get-back players can contest the shot; the failed stopper cannot also be the shot defender; 0 or 3+ get-back means no charge/block and no shot defender for animation.

**Critical Implementation Detail:**
- **All defenders checked**: The system checks **all defenders in `def_lineup`**, not just those initially in `fb_roles["defense"]`
- **Why**: `get_in_play_defenders()` (called earlier) uses stale `ball_handler.coords` to filter defenders, which might exclude get-back players who are actually ahead of the outlet receiver position
- **Fix**: Loop through all defenders when comparing against outlet receiver position (`ball_handler_outlet_x/y`)
- **Result**: Get-back players who are ahead are correctly detected, even if they weren't initially included in `fb_roles["defense"]`
- **Animation**: If an ahead defender wasn't in the initial list, they're added to `fb_roles["defense"]` for animation purposes

**Implementation (simplified):**
```python
from BackEnd.engine.cutoff_resolution import (
    best_cutoff_on_drive, resolve_cutoff_contest, map_cutoff_outcome_to_fb,
)

# Build def_coords_cutoff from all def_lineup positions (get-back coords priority)
cutoff_pos, cutoff_meet = best_cutoff_on_drive(
    bh_start, drive_target, bh_drive_rate, def_coords_cutoff, def_lineup,
    get_defender_rate=lambda d: ag_sprint_rate(d),
    path_corridor=FB_CUTOFF_PATH_CORRIDOR_DREB,
    defender_time_slack=FB_CUTOFF_DEFENDER_TIME_SLACK_DREB,
    stop_attempt_prob=aggression_stop_prob,
)
if cutoff_meet and cutoff_pos:
    outcome, _, credited = resolve_cutoff_contest(off_team, def_team, bh, def_lineup[cutoff_pos])
    event_type, flags = map_cutoff_outcome_to_fb(outcome)
    fb_roles["cutoff_meet_x/y"] = cutoff_meet
else:
    event_type = "SHOT"  # no geometric cutoff
```

### Animation Sequence

**Phase 1: Outlet Pass (DREB Entry Only)**

- **Covert Release / default DREB path (no `rim_runner_burst_phase`)**: Outlet passer (rebounder) stays at rebound spot; outlet receiver (ball handler) receives pass at current position (no movement); defenders and other players stay put (`animateOutletPhase()` in `fastBreak.js`).
- **Rim Runner / Triangle (`rim_runner_burst_phase` present)**: `animateRimRunnerBurstPhase()` runs first. **All** burst-phase tweens (rim runner sprint, outlet contest defender, `other_players`, outlet receiver run to `receiver_to`) **start together**. The **outlet pass** tween runs **only after** the **outlet receiver’s** move completes; rim runner, defender, and other players **may still be moving** during the pass. If **`skip_outlet_pass`**, the ball stays on the rebounder and moves with them to `receiver_to` (no pass). If **`rim_runner_outlet_failed`**, setup tweens play as usual; the scripted outlet pass is skipped and **`animateRimRunnerOutletDeniedBeat`** runs inside Phase 1 (see **Rim Runner** → *Client — outlet denied* above). Phase 2 for outlet denied is **HCO finalize only** — not the generic defensive-stop block below.

**Phase 2: Defensive Stop or Shot Attempt**

**Defensive Stop:**
- *(Excludes Rim Runner **outlet denied** and **hold-up**; those paths finalize HCO without this block.)*
- Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
- Stopper (closest defender ahead) moves to position 1-3 spots in front of ball handler
- Get-back defenders chase toward basket
- Rebounders move to random x=40-60, y=starting_y ± 6 (clamped)
- **Early Termination**: Rebounder animations stop when ball handler and stopper both reach their spots

**Shot Attempt:**
- Ball handler (shooter) moves to **shot spot near rim** (basket ± 2-6, ±6 Y in `capture_fast_break_animation`; exposed as `turn_result["shot_spot"]`). See **Shot spot (ball handler end position)** below.
- **Shot contest defender(s)** animate from the shooter final. Primary defender: **x = shooter_x - 2** for home offense or **x = shooter_x + 2** for away offense; **y = shooter_y + random(-2, 2)**. In beat-stopper cases, the second defender uses the same **x** and **y = primary_y ± 3** based on his starting row. `turn_result["defender_spot"]` is the primary defender row’s **`end`** in the animation packet (`phase_resolution`).
- **Client timing**: `animateFastBreakShot` / `animateFastBreakShotWithStopper` **`await` only the shooter** reaching the shot spot before `animateShotToRim`. The shot defender’s tween **may still be in progress** when the ball is released (defender and rebounders are not awaited at the shoot cue).
- Get-back defenders (non–shot-defender) chase toward basket per `moveOtherPlayersToStandardPositions`
- Rebounders move to random x=5-20 spots from basket, y=rim_y ± 10 (clamped)
- **Ball flight**: MAKE/MISS → ball to rim (or adjusted rim for make). **BLOCK** → ball to **block spot** when `ball_bounce_x`/`ball_bounce_y` are present; then bounce from that spot, "Block!" announcement, and rebound/DREB same as miss.
- **Early Termination**: 
  - Made shot: Rebounder animations stop when ball hits rim
  - Missed or blocked shot: Rebounder animations stop when rebounder grabs ball

**Shot spot (ball handler end position) – backend**

In `capture_fast_break_animation()` (BackEnd/models/animator.py), the ball handler's end position determines where the shot is taken and is exposed as `turn_result["shot_spot"]` for the frontend. It is set as follows:

1. **Ball handler beats defender** (`hold_up` and `ball_handler_beats_defender`): Shot spot **near the rim** (same as below). Frontend uses `animateFastBreakShotWithStopper()` and may use local shot spot; backend still provides rim spot for consistency.
2. **Defensive stop** (`hold_up` True, outlet set): Ball handler ends at **confrontation spot** (outlet position + 5–10 x toward basket, ±3 y). No shot; this is the stop position.
3. **Shot attempt with outlet, no defensive stop** (`hold_up` False, outlet set): Shot spot **near the rim** (same logic as case 1). Previously this used "outlet + 5–10", which caused the shot to animate from the top-of-key area; the fix ensures all shot attempts get a rim shot spot so the animation shows the shot from near the basket.
4. **Fallback** (no outlet): Defensive stop → top of key; shot attempt → near rim.

The frontend uses `turnData.shot_spot` when present (FAST_BREAK handler) so the shot animates from the correct position. **`animateFastBreakShotWithStopper`** also consumes **`shot_spot`** when present so stopper/trail defender targets match the sim.

### Shot contest grid vs shooter final (authoritative)

**Rule (all FB shot attempts in `capture_fast_break_animation`):**

- Let **`(sx, sy)`** = ball handler end = **`_bh_final_x/y`** (same as `shot_spot` on the turn for shots).
- **Single contest defender** (`hold_up` is false, or only one animated defender): end = primary shooter-relative FB shot-defender spot:
  - home offense: **`x = sx - 2`**
  - away offense: **`x = sx + 2`**
  - **`y = sy + random(-2, 2)`**
- **Handler beats stopper** (`hold_up` + `ball_handler_beats_defender`): failed **stopper** gets that same primary defender spot. **Trail shot defender** (different player, from `fb_roles["defender"]`) gets the same **x** and **`y = primary_y + 3`** when his starting **y** is greater than the primary defender’s **y**; otherwise **`y = primary_y - 3`**.
- **True defensive stop** (no shot): unchanged — stopper remains **1–3** X toward basket from ball handler **confrontation** end, same **Y**; other get-backs use *between key and rim* sampling (not the shot contest helper).

**Constants / code:** `SHOT_DEFENDER_X_OFFSET`, `SHOT_DEFENDER_Y_RANGE`, `SECONDARY_SHOT_DEFENDER_Y_OFFSET`, **`fast_break_shot_defender_end_coords`**, **`fast_break_secondary_shot_defender_end_coords`** — `BackEnd/constants/fast_break_constants.py`. Animator: `BackEnd/models/animator.py` (`capture_fast_break_animation`). Client fallback / parity: **`fastBreakShotDefenderGridVsShooter`** and **`fastBreakSecondaryShotDefenderGrid`** — `FrontEnd/static/js/phaser/constants/fastBreakConstants.js`; `fastBreak.js` (`animateFastBreakShot`, `animateFastBreakShotWithStopper`).

### Fast Break MISS → DREB Transition

**Flow:**
1. Fast Break shot attempt results in MISS
2. Defensive rebound occurs (DREB)
3. Transition to HCO (half court offense) via `runDefensiveReboundSetup()`

**Rebound-capture attemptors:** missed Fast Break shots use the shared backend near-bounce attemptor contract from `Rebound_System.md`. After the backend resolves the bounce spot and actual `rebounderId`, `shot_manager.py` / migrated FB resolvers stamp `offense_rebounders` / `defense_rebounders` with every non-captor player within **20 Euclidean grid units** of the bounce. The promoted discrete `DREB` turn animates the winner to the ball and those failed attemptors to randomized near-bounce spots. The frontend does not calculate these candidates.

**Critical Implementation Detail - turnData Handling:**
- **Current Fast Break MISS turn** must be passed as `turnData` to `runDefensiveReboundSetup()`
- **Why**: `runDefensiveReboundSetup()` uses `turnData.animations` to detect pass actions for the outlet pass animation
- **offense_getback lookup**: If current turn doesn't have `offense_getback`, `runDefensiveReboundSetup()` automatically looks up the previous HCO MISS turn (the one that triggered the Fast Break)
- **Why this matters**: The previous HCO MISS turn has the `offense_getback` list needed for get-back player positioning, but the current Fast Break MISS turn has the correct animation data

**Implementation:**
```javascript
// In fastBreak.js - animateFastBreakShot()
// Pass current Fast Break MISS turnData (has animations)
await runDefensiveReboundSetup({
  scene,
  ballSprite,
  playerSprites,
  rebounderId,
  nextPlayType: turnData.next_play_type || "HCO",
  turnData: turnData // ✅ Current Fast Break MISS turn (for animations)
  // runDefensiveReboundSetup will find offense_getback from previous turn if needed
});
```

```javascript
// In turnAnimation.js - runDefensiveReboundSetup()
// Lookup offense_getback from previous turn if current turn doesn't have it
let missTurnForGetback = turnData;
if (!missTurnForGetback || !missTurnForGetback.offense_getback) {
  // Try previous turn if current turn doesn't have offense_getback (Fast Break case)
  const previousTurn = scene.simData?.turns?.[currentIndex - 1];
  if (previousTurn?.result_type === "MISS" && previousTurn.offense_getback) {
    missTurnForGetback = previousTurn;
  }
}
const getBackList = missTurnForGetback?.offense_getback || [];
```

**Why This Fix Was Critical:**
- **Previous Bug**: Passing the previous HCO MISS turn caused `runDefensiveReboundSetup()` to look for pass animations in the wrong turn data
- **Result**: Animation freeze when trying to execute outlet pass after Fast Break MISS → DREB
- **Fix**: Pass current Fast Break MISS turn (correct animations) while still allowing lookup of `offense_getback` from previous turn

### Fast Break Stat Tracking

The Fast Break system tracks comprehensive statistics for both offensive and defensive players involved in fast break situations.

**Stat Tracking Function:**
- `_record_fast_break_stats()` in `BackEnd/engine/phase_resolution.py` - Records stats after Fast Break turn completes

**Offensive Stats (Release Player / Outlet Receiver):**

The release player (outlet receiver) tracks:
- **`FB_A`** (Fast Break Attempts): Always incremented when player is the outlet receiver on a Fast Break
- **`FB_S`** (Fast Break Success): Incremented when Fast Break results in:
  - Shot Make
  - Defensive Foul (non-shooting)
  - **Note**: Shot Miss (without defensive foul) does NOT count as success (matches team-level criteria)
- **`FB_F` / `FB_N`**: Retired — not tracked; use **S / A / %** from **`FB_S`** / **`FB_A`**.

**Defensive Stats (Get-Back Players):**

All get-back players (defenders who got back on defense) track:
- **`FB_A_D`** (Fast Break Attempts Defense): Always incremented when player is a get-back defender on a Fast Break
- **`FB_S_D`** (Fast Break Success Defense): Incremented when Fast Break results in:
  - DEFENSIVE_STOP
- **`FB_F_D`** (Fast Break Failure Defense): Incremented when Fast Break results in:
  - Shot Make
  - Shot Make + Foul
  - Shot Miss + Foul
  - Defensive Foul (non-shooting)

**Outlet Pass Stats (Outlet Passer):**

The outlet passer tracks:
- **`Outlet_A`** (Outlet Pass Attempts): Always incremented when player makes an outlet pass
- **`Outlet_S`** (Outlet Pass Successes): Incremented when outlet pass leads to a shot attempt (not a defensive stop)
- **`Outlet_Score`** (Average Outlet Pass Score): Average of all outlet pass scores (1-100 scale)
- **`Outlet_Score_List`** (Outlet Pass Score List): Array of individual outlet pass scores
- **`Outlet_Score_Cum`** (Cumulative Outlet Pass Score): Sum of all outlet pass scores

**Outlet Pass Score Calculation:**
- **Formula**: `(PS * 0.6 + ST * 0.2 + IQ * 0.2) * random.randint(1, 6)`
- **Scaling**: Raw score (1-600 range, midpoint 175) is scaled to 1-100 range (midpoint 50)
- **Function**: `calculate_outlet_pass_score()` in `BackEnd/utils/shared.py`
- **Scaling Function**: `scale_score_to_100()` in `BackEnd/utils/shared.py` (universal helper for all attribute-based scores)

**Stat Initialization:**
- All Fast Break stats initialized to `0` (except `Outlet_Score_List` which is initialized as empty array `[]`)
- Initialized in:
  - `Player._init_stats()` - For all stat levels (game, season, career)
  - `_init_game_stats_dict()` in `BackEnd/main.py` - For single game mode
  - Tournament and Franchise mode initialization functions

**Stat Tracking Timing:**
- **Outlet Pass Stats**: Tracked immediately after outlet pass score is calculated (in `resolve_fast_break_logic()`)
- **Fast Break Stats**: Tracked after Fast Break turn result is finalized (both DEFENSIVE_STOP and SHOT paths)
- Stats are recorded in both `run_micro_turn()` and `resolve_offensive_rebound_turn()` paths

**Team Stats (Scouting Data):**
- **`Fast_Break_Entries`** (Offense): Incremented each time a team runs a Fast Break (in parallel with per-play **`A`** below)
- **`Fast_Break_Success`** (Offense): Incremented only when Fast Break result_type is:
  - `MAKE`, or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul on the break)
  - **Note**: `MISS` or `TURNOVER` do NOT count as team success (they count as defensive success)
- **`fast_break_plays`** (Offense): Per-play **`A`** / **`S`** for `covert_release`, `rim_runner`, `triangle`, `after_steal` (see `BackEnd/constants/fast_break_play_types.py`). **DREB outlet**: play key is chosen on the **miss shot** turn and stored in **`pending_dreb_fb_play_key`**; the resolver pops it and increments the matching bucket (**50/50** `rim_runner` vs `covert_release` if not pre-set). **Steal entry** → **`after_steal`**. **`triangle`** now uses the shared Rim Runner entry/denied-outlet path, then its own setup / decision / finish branch family. Same success rules as **`Fast_Break_Success`**, applied to the active play bucket.
- Turn payloads include **`fast_break_play`** for the active bucket.
- **`vs_Fast_Break.used`** (Defense): Incremented each time defending a Fast Break
- **`vs_Fast_Break.success`** (Defense): Incremented when Fast Break result_type is:
  - `DEFENSIVE_STOP`, or
  - `MISS`, or
  - `TURNOVER`, or
  - `FOUL` where `foul_team == "OFFENSE"`
- **Alignment with player stats:** Player **`FB_S`** matches team **`Fast_Break_Success`** (only `MAKE` or defensive foul). A `MISS` without defensive foul is not a success for the team or player **`FB_S`**.

**Special Handling:**
- **`Outlet_Score_List`**: Excluded from stat delta calculations (it's a list, not numeric)
- **Team Stats Aggregation**: `Outlet_Score_List` is concatenated (not summed) when aggregating team stats
- **Stat Deltas**: `Outlet_Score_List` and `REB` are excluded from delta calculations in `turn_manager.py`

**Box Score Display:**
- Fast Break stats are available in the Box Score page
- Clicking a player's name opens a popup showing:
  - Fast Breaks: Offense and Defense as **S / A / %** (with hint row); Outlet Passes: Att / Score
- **Scouting Notes** (per team): **Fast Breaks** appears after **Defense Play Calls**, styled like a defense subsection: **`h4`** line **`Fast Breaks: S / A (%)`** (aggregate), then **`scouting-item`** rows for **Covert Release**, **Rim Runner**, **Triangle**, **After Steal** from **`offense.fast_break_plays`** (EOG snapshot override when present).

### Key Files

- `BackEnd/utils/shared.py` — `SLIDER_TO_FAST_BREAK_PROB`, `fast_break_probability_from_slider()` (DREB: rebounding `fast_breaks`; steal: stealing team `aggression`)
- `BackEnd/engine/fast_break_trigger.py`
  - `FastBreakTrigger.DEFENSE_RELEASE_CHANCES` — same table as `SLIDER_TO_FAST_BREAK_PROB` (legacy helpers)
  - `can_trigger_from_dreb()` - Legacy PG/SG release tuple (live DREB uses Covert in `shot_manager`)
  - `can_trigger_from_steal()` - Legacy steal helper
- `BackEnd/engine/covert_release.py`
  - Covert Release: defender farthest from rim (excluding shooter’s matchup); **AG**-based x floors + **IQ** (`good_release` / `good_d_release`) y/x bands; HOME orientation + **x** mirror for away FB offense
- `BackEnd/constants/fast_break_constants.py` — Movement bands, **`fast_break_shot_defender_end_coords()`** / **`fast_break_secondary_shot_defender_end_coords()`** (single source for FB shot defender geometry vs shooter final)
- `BackEnd/constants/fast_break_play_types.py` — Play keys, `default_fast_break_plays()`, `ensure_fast_break_plays()`, `play_key_for_fast_break_entry()` (DREB: **50/50** when called; live path uses **`pending_dreb_fb_play_key`** from `shot_manager`)
- `BackEnd/engine/rim_runner_fast_break.py` — **`resolve_rim_runner_fast_break()`** — Rim Runner / Triangle DREB outlet play (outlet contest, burst, read, pass/intercept/bat/shot or Triangle setup tree)
- `BackEnd/engine/rim_runner_step_emitter.py` — **`build_rim_runner_animation_steps()`**; shared **`append_lane_pass_to_rr_resolution_steps()`** (outlet receiver → RR lane pass + shot, hold-up, intercept, bat OOB) used by Rim Runner and Triangle lane-pass quick shot
- `BackEnd/engine/triangle_step_emitter.py` — **`build_triangle_animation_steps()`** — burst/outlet/denied + lane-pass delegate + Triangle setup/decision branches
- `BackEnd/engine/phase_resolution.py`
  - `resolve_free_throw_logic()` — missed FT + DREB: `fast_break_probability_from_slider(def_team["fast_breaks"])` for FAST_BREAK vs HCO
  - `resolve_turnover_logic()` / FCP / HCT steal branches — `fast_break_probability_from_slider(def_team["aggression"])` (**stealing** team)
  - `resolve_fast_break_logic()` - Determines defensive stop vs. shot attempt; increments **`fast_break_plays`** and sets **`fast_break_play`**; **early return** to Rim Runner resolver when DREB + **`rim_runner`** or **`triangle`**
  - `GameManager.simulate_macro_turn()` promotes migrated Fast Break MISS/BLOCK + `DREB` outcomes (`covert_release`, `rim_runner`, `triangle`, `after_steal`) into a discrete `DREB` turn before `HCO` / next Fast Break routing.
  - Uses coordinate comparison in HOME orientation
  - Stores `ball_handler_outlet_x/y`, `is_away_offense`, `getback_player_ids` in `fb_roles`
- `BackEnd/models/shot_manager.py`
  - **DREB FB (HCO shots)**: one `fast_breaks` roll → play key → Covert (`select_covert_release_position`) or all-defenders-crash for RR/Triangle; sets **`_shot_dreb_fb_play_key`** → **`pending_dreb_fb_play_key`** on DREB → FAST_BREAK
  - `_calculate_getback_coordinates(..., good_d=)` / `_calculate_release_coordinates(..., good_release=)` — Covert outlet positioning only when play key is **`covert_release`**
  - Stores `offense_getback_coords` and `defense_release_coords` in turn results (release coords empty for RR/Triangle)
- `BackEnd/models/animator.py`
  - `capture_fast_break_animation()` - Builds animation packet; primary shot defender end coords via **`fast_break_shot_defender_end_coords`** and beat-stopper secondary defender coords via **`fast_break_secondary_shot_defender_end_coords`** for every FB **shot** path; defensive stop path keeps legacy stopper 1–3 + between-key-and-rim for other get-backs
  - Uses `fb_roles` for ball handler outlet position and `is_away_offense`
  - **Ball handler end position (shot spot)**: Defensive stop → confrontation spot (outlet + 5–10); shot attempt (with or without outlet) → shot spot near rim (so the shot always animates from near the basket, not from top-of-key). Exposed as `turn_result["shot_spot"]` in phase_resolution for frontend use.
- `FrontEnd/static/js/phaser/constants/fastBreakConstants.js` — **`fastBreakShotDefenderGridVsShooter()`**, **`fastBreakSecondaryShotDefenderGrid()`**, `SHOT_DEFENDER_X_OFFSET`, `SHOT_DEFENDER_Y_RANGE`, `SECONDARY_SHOT_DEFENDER_Y_OFFSET` (mirror backend contest grid for client fallbacks)
- `FrontEnd/static/js/phaser/animation/fastBreak.js`
  - `runFastBreakSequence()` - Orchestrates fast break animation; routes MAKE, MISS, and **BLOCK** to shot path (not defensive stop); if `roles.rim_runner_burst_phase` is set, runs **`animateRimRunnerBurstPhase()`** before Phase 2 instead of the static Covert-style **`animateOutletPhase()`**. **Rim Runner HCO settle** (`rim_runner_hco_settle`): if **`rim_runner_outlet_failed`**, Phase 2 is **`finalizeRimRunnerNonShotTurn()`** only; else (hold-up) **`animateRimRunnerHoldUpLeadIn()`** then **`finalizeRimRunnerHoldUpToHco()`** (no **`animateDefensiveStop`**).
  - `animateRimRunnerBurstPhase()` - Rim Runner burst + simultaneous role-player moves; pass gated on outlet receiver tween completion (and skipped when outlet denied or dribble-outlet); outlet denied delegates to **`animateRimRunnerOutletDeniedBeat()`**
  - `animateRimRunnerOutletDeniedBeat()` - Outlet-denied sequence: defender press coords, **“FB Outlet Pass Denied!”** + defender headshot, receiver cut, pass (or dribble-outlet), then burst tweens finish
  - `animateOutletPhase()` - Covert-style outlet pass (no player movement)
  - `animateDefensiveStop()` - Handles defensive stop animation
  - `animateFastBreakShot()` - Handles shot attempt (MAKE/MISS/BLOCK): shot spot move, ball to rim or block spot, then make/miss/block outcome (BLOCK: block announcement, bounce from block spot, rebound/DREB)
  - `animateFastBreakShotWithStopper()` - Same outcome handling for BLOCK (block spot target, block announcement, bounce from block spot, rebound/DREB)
  - `moveOtherPlayersToStandardPositions()` - Positions outlet passer and get-back defenders
    - **Get-back retreat (client)**: Non-shooter get-back defenders tween toward an x-band toward the **rim the fast-break offense is attacking** — same HOME-grid convention as `animateFastBreakShot` (`HOME_RIM` when home has the ball, `AWAY_RIM` when away has the ball). **Do not** hardcode only the home rim in this path: that made away-FB get-backs sprint the wrong direction. Resolve offense from the ball-handler sprite’s `team` when possible, with `turnData.offense_team_id` / `possession_team_id` (+ `scene.simData.home_team_id`) as fallback. If get-backs ever look reversed after future refactors, check that `ballHandlerId` and possession fields still refer to the **FB offense** at this call site (possible second-order bugs).
  - `animateRebounders()` - Handles rebounder animation (extracted for maintainability)
    - Defensive Stop: x=40-60, y=starting_y ± 6 (clamped 1-49)
    - Shot Attempt: x=random 5-20 spots out from basket, y=rim_y ± 10 (clamped 1-49)
    - Returns tween references for early termination
  - Early termination logic for rebounder animations
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`
  - `runRimRunnerHoldUpSetupTween()` - After RR hold-up, HCO step 0 with optional **BH → PG** pass when PG reaches step 0 ( **`_rimRunnerHoldUpInboundPass`** )
  - `runDefensiveReboundSetup()` - Handles DREB → HCO transition, including Fast Break MISS → DREB cases
  - Automatically looks up `offense_getback` from previous turn if current turn doesn't have it (Fast Break case)

### Future Enhancements

- **User FB play settings**: Replace **50/50** DREB play selection with user-configured weights (Rim Runner vs Covert Release vs **Triangle**). (`playbook_settings.fast_break` is seeded `covert_release=50 / rim_runner=50 / triangle=0`, but live DREB selection is still the hardcoded 50/50 RR-vs-CR until the settings are wired into selection.)
- **Fast Break Fouls**: Add foul handling during fast break sequences
- **Fast Break Turnovers**: Add turnover handling during fast break sequences

> **Note (2026-06):** Triangle is **already implemented** (UESS-migrated burst/outlet/denied/lane-pass + setup/decision branches — see the *Triangle (`triangle`)* subsection above). The former "implement Triangle engine path" enhancement has been removed as completed.


**Rim Runner Fast Break Step Schema Details**
##Step 0: Burst
  -Advance Trigger (AT): player_reaches_position (PRT)
    -Outlet Receiver reaches destination (sprint rate)
  -Movement speeds
    -RR: Burst 
    -Outlet Receiver: sprint
    -Get Back Defenders: sprint
    -Outlet Passer: stationary
    -Other players: drift


##Step 1 Branches
  -Step 1: Outlet Pass (see below for Step 2 branches)
    -Step 1: Outlet pass
      -AT: ball_reaches_destination (BRD)
      -Movement Speeds:
        -RR, Get Back Defenders, Other: sprint
        -Outlet Passer / Receiver: stationary
  -Step 1: Outlet Denied
    -Step 1: Defender Close Out
    -Step 2: Paralle Movement
    -Step 3: Reset Step


##Step 2: Lane Pass or Hold Up
  -Lane Pass Branches (Shot, Interception, or OOB)
    -Step 2: Lane Pass
      -Movement:
        -RR continues toward `basketSpot` from his carried-forward coord
        -If Primary Defender & (Interceopt or Batted Ball): contact_grid spot
        -All other players: stationary
      -Movmeent Speeds: RR uses the same `burst` / `sprint` archetype selected in Step 0; primary defender uses `sprint`
      -AT: ball_reaches_player
        -Shot: RR
        -Steal or Batted Ball OOB: Primary Defender
    -Step 3: Shot Motion
      -Movement:
        -RR: Shot Spot
        -Shot Defender: guard ball
      -Movmeent Speeds: 
        -RR & Shot Defender: sprint
        -All other moving players: drive
      -AT: PRD, RR reaches Shot Spot

  -Hold Up Branch
    -Step 2: Hold Up Step
    -Step 3: Lead In


---

## FB Drive Cutoff & Stop Decision *(approved design — implementation pending, June 2026)*

> **Work plan:** [`projects/FB_Drive_Cutoff_Work_Plan.md`](../projects/FB_Drive_Cutoff_Work_Plan.md)

Unified geo-based resolver for **all FB play keys** (`covert_release`, `rim_runner`, `triangle`, `after_steal`). Replaces the split between (a) CR outlet-phase cutoff + universal HCO stop and (b) the point-race **`compute_fb_shot_geometry`** model.

**Planned modules:** `BackEnd/engine/fb_drive_resolution.py` (`resolve_fb_drive_step`), `BackEnd/engine/fb_stop_decision.py`, `BackEnd/utils/fb_geo_helpers.py`. Emitters remain pure renderers; resolver stamps `fb_drive_resolution` on the turn.

### Scope

| Applies to | Rule |
|---|---|
| **Drive cutoff / stop** | **`shot_type = attack`** drives only (rim band, Triangle BH drive to lowPost, RR finisher drives, etc.) |
| **Shot-defender proximity** | **All FB shot types** — `CONTEST_EUCLIDEAN_RADIUS` (11) **and** `FB_CONTEST_MAX_X_TRAIL` (3); FB-only (HCO keeps its own contest rules) |
| **Spot-up shots** (Triangle wing/corner 3, etc.) | No drive cutoff; contest via 11 + x-trail only |
| **RR hold-up** (OR declines lane pass, no cutoff) | Still auto-**HCO**; dynamic stop tree does not run |

**Outlet-phase cutoff removed:** CR (and any path using `resolve_fast_break_logic` Steps 5–6) no longer stops at outlet. Outlet pass completes → **one shot-drive step** runs this resolver.

**After-steal:** Model 2 stops enabled (not MAKE/MISS-only). Steal-specific meet filter below.

### Drive geometry

- **BH path:** straight segment **drive-step start → pre-rolled `shot_spot`** (rim band: `basket_x ± randint(2,4)`, `y ∈ [19,31]`).
- **Rates / animation:** **`sprint`** for BH and cutoff defenders; logic rates = animation archetype rates (`_ag_grid_per_game_sec`).
- **Defender pool:** all five defenders; **geo-gated** only (no hard-coded get-back / outlet exclusions). Outlet contest defenders are organically excluded when **`drift`** on the drive step prevents a timely meet.
- **Path corridor:** `FB_CUTOFF_PATH_CORRIDOR = 14` (perpendicular distance to segment); **`defender_time_slack = 1.0`**. No aggression re-roll.
- **Selection:** `best_cutoff_on_drive()` — **earliest meet** on path (farthest-from-rim intercept); tie → closer defender to meet. One winner; others continue toward **`basketSpot`** for rebound position.
- **Failed prior stopper:** permanently excluded from a second cutoff attempt; **`drift`** on drive step, then sprint on later steps.
- **Committed cutoff / outlet-denial defenders:** **`drift`** archetype on the **drive step only** (`DRIFT_GRID_PER_GAME_SEC`).

**No geometric meet:** BH clean path to `shot_spot`; all defenders sprint to **`basketSpot`** (or interpolated chase); contest evaluated at shot time.

#### After-steal meet filter *(steal entry only)*

General corridor + race excludes hopeless trailing stops, but does **not** require the intercept to sit **ahead** of the BH on x. For **`after_steal`**, a meet is valid only if meet **`x` is ≥ 1 grid spot toward the basket from the BH’s drive-step start `x`** (HOME: `meet_x ≥ bh_start_x + 1`; AWAY: `meet_x ≤ bh_start_x - 1`). Invalid → defender treated as no cutoff (→ `basketSpot` / contest path). DREB FB paths omit this filter.

### Meet resolution order *(never double foul)*

1. Arrival race → **`cutoff_meet_x/y`**
2. **`resolve_cutoff_contest`** (D8, steal excluded) → terminal on `DEAD BALL` / `O_FOUL` / `D_FOUL`
3. **`calculate_charge`** → terminal on `CHARGE` / `BLOCKING_FOUL` (non-shooting charge moment at meet)
4. **`POS_O`** → BH beats stopper; single drive step to rim (see **POS_O shimmy**)
5. **`NEUTRAL`** → dynamic stop decision (see below); **two schema steps**
6. If BH later **shoots** from stop: **shooting foul only** via `calculate_shot_score` (no second D8/charge). Pass → new shooter gets full foul stack on their action.

### Dynamic stop decision (`NEUTRAL` only)

**Geo gates**

| Action | Eligibility |
|---|---|
| **Shoot** | BH Euclidean ≤ **24** to attacking basket **OR** nearest `HCO_STRING_SPOTS` label ∈ **`key`**, **`upper midWing`**, **`lower midWing`** (label proximity — no extra distance cap on the label) |
| **Pass** | Closest teammate to basket; same **≤ 24 Euclidean** **or** nearest label ∈ **`key`**, **midWings**, **wings**, **midCorners**, **corners**; teammate **`SH > 49`** |

**Optimal priority**

1. **Pass** if pass geo + SH gate pass  
2. Else **shoot** if `calculate_shot_score(...) >= shot_threshold` with stop defender contesting (`apply_defense=True`) — same make gate as `resolve_shot`; **no separate heuristic**  
3. Else **HCO**

**Stop-and-shoot shot type** (at meet coord): motion rule — Euclidean to basket ≤ **`ATTACK_DRIVE_INSIDE_RADIUS` (15)** → **`inside`**; else **`outside`** pull-up (not `attack`).

**Read gate** (`_player_read`, same thresholds as HCT ABA: **200 / 125**)

- **> 200** → take optimal action  
- **> 125** → **HCO** (safe)  
- **≤ 125** → random among **geo-valid** options: shoot + HCO always in pool; pass only when pass geo valid  

**HCO entry:** existing orchestrator (`skeleton_step_emitter` + `transition_bridge`) — backcourt **handoff** (x &lt; 71 home / &gt; 29 away); frontcourt BH ≠ PG **kickout**; else **walk-up**.

Stop defender **auto-contests** any pull-up (no re-pick).

### Animation / advance triggers

| Outcome | Steps | Advance trigger |
|---|---|---|
| **`POS_O`** | **1** — start → meet → shimmy knot → `shot_spot` | BH reaches **`shot_spot`** |
| **`NEUTRAL`** | **2** — (1) drive to meet; (2) shoot / pass / HCO | Step 1: **slower of BH + stopper** at meet. Step 2: pass = ball reaches receiver; shoot = **immediate** post-shot sub-steps (no gather beat); HCO = handoff/kickout/walk-up gates |
| **No meet** | **1** — BH to `shot_spot` | BH reaches **`shot_spot`** |

#### POS_O shimmy *(single step — not a second schema step)*

When BH beats the stopper, path is **three knots in one step**: `start → meet → shimmy_point → shot_spot`. Magnitude **2 grid spots** dodge **away from stopper** (pick larger lateral separation at meet).

**Shimmy axis from drive approach** (segment into meet, or meet → `shot_spot`):

| Approach | Dominance | Shimmy offset |
|---|---|---|
| **Key / top-of-key** (mostly ±x toward rim) | `\|dx\| ≥ \|dy\|` | **±2 y** |
| **Baseline / side** (mostly ±y toward lane) | `\|dy\| > \|dx\|` | **±2 x** |
| **Arc / diagonal** | neither dominates | **Combined x+y** — unit vector **perpendicular** to drive direction, scaled to **2** grid Euclidean (typically splits both axes) |

Sign: side that increases distance from stopper at meet. Clamp to court bounds.

### Stats *(gameplay geo; stats by player id)*

- **Gameplay roles:** geo only — remove `num_getback in (1,2)` shot-defender gate.
- **`offense_getback` IDs:** retained on prior shot turn for scouting (“designated get-back”).
- **`FB_A_D`:** designated get-back **plus** any defender who geo-participated (cutoff attempt, stopper, shot defender). Failed cutoff attempt counts **`FB_A_D`**, not **`FB_S_D`**.
- **Team `zero/one/two_defenders_back`:** geo count of defenders who attempted cutoff or finished in contest range.

### Supersedes *(post-implementation cleanup)*

- CR **Steps 5–6** outlet cutoff + `map_cutoff_outcome_to_fb` → universal HCO stop  
- **`compute_fb_shot_geometry`** point-race + first-arriver freeze  
- Get-back-only **`fb_roles["defender"]`** assignment  
- CR outlet-pass step **sharp-outlet IQ read** cutoff positioning (replaced by drive-step geo)  
- Triangle corner-3 **6-spot** defender radius → **11 + x-trail**  
- After-steal **MAKE/MISS-only** (no stop branch)

---

# Universal Fast Break Shot Geometry Helper *(legacy — superseded by FB Drive Cutoff & Stop Decision above; retained until migration complete)*

Shared backend module that computes shooter target, defender race
outcome, and contested decision for FB shot attempts across Rim Runner,
Covert Release, and Steal-FB. Triangle is intentionally untouched.

**Module:** `BackEnd/utils/fast_break_shot_geometry.py`
**Public function:** `compute_fb_shot_geometry(...)`
**Spec source:** discussion 2026-05-27 — same logic originally implemented
inline in `after_steal_fast_break.py`, refactored into a reusable helper.

## Geometry rules

| Component | Rule |
|---|---|
| **Shooter target x** | `basket_x ± random.randint(2, 4)` toward center. AWAY basket=9 → x ∈ {11, 12, 13}. HOME basket=91 → x ∈ {87, 88, 89}. |
| **Shooter target y** | `random.randint(19, 31)` (uniform random integer in that range). |
| **Defender single target x** | `shooter_x ± 2` toward basket (same y as shooter). |
| **Defender single target y** | Same as shooter's y. |

## Race + freeze

| Step | Rule |
|---|---|
| Per-defender traversal time | `euclidean(start, defender_target) / sprint_rate`. Sprint rate via `_ag_grid_per_game_sec(player, "sprint")` (AG-based). |
| First arriver | Defender with smallest traversal time. Occupies `defender_target`. |
| Other available defenders (t_first < t_shooter) | Freeze at their interpolated position at `t_first`. Clamped no closer than 6 grid spots from basket (with **no-pull-backward** edge case: defenders starting inside the 6-spot zone stay at start). |
| All defenders (t_first ≥ t_shooter) | At interpolated positions at `t_shooter`. No clamp (freeze never fired). |

## Contested decision

At `t_shooter`, evaluate each racing defender's end position. A defender
**contests** when **both** are true:

1. **Euclidean distance** to the shooter ≤ `CONTEST_EUCLIDEAN_RADIUS` (11 grid spots)
2. **X trail** ≤ `FB_CONTEST_MAX_X_TRAIL` (3 grid spots) — the defender may
   trail the shooter by 1, 2, or 3 x spots (or be even/ahead on x) and
   still qualify; more than 3 spots behind on x does not contest even if
   within 11 Euclidean.

The **nearest** qualifying defender is the shot defender. If none qualify →
**uncontested**.

| Direction | "Trailing" on x |
|---|---|
| HOME offense (basket x=91) | Defender x < shooter x; trail = `shooter_x − defender_x` |
| AWAY offense (basket x=9) | Defender x > shooter x; trail = `defender_x − shooter_x` |

| Case | Shot resolution |
|---|---|
| Contested | `calculate_shot_score(apply_defense=True)`; normal `shot_threshold` check decides MAKE / MISS / BLOCK. |
| Uncontested | `apply_defense=False` + `fast_break_shot_threshold_override = 1` → automatic MAKE (matches OREB-putback uncontested rule). |

## Race-pool definitions per FB type

| FB type | Excluded from race | Race pool |
|---|---|---|
| **Rim Runner** | Stopper + Outlet defender | Trail + Get-back defenders |
| **Covert Release** | Stopper (no outlet defender concept in CR) | Trail + Get-back defenders |
| **Steal-FB** | None | All 5 defenders |
| **Triangle** | n/a — helper is NOT applied to Triangle | n/a |

The Stopper and Outlet defender stay at their end-of-preceding-step
positions (no movement during the shot step).

## Feature flags (per-FB revert)

`BackEnd/constants/__init__.py`:

```python
USE_UNIVERSAL_FB_SHOT_GEOMETRY_RR = True   # set False to revert RR to legacy
USE_UNIVERSAL_FB_SHOT_GEOMETRY_CR = True   # set False to revert CR to legacy
```

Steal-FB always uses the helper; Triangle is intentionally untouched.

## Function signature

```python
def compute_fb_shot_geometry(
    *,
    shooter,                  # player object
    shooter_start,            # GridCoord — end coord of preceding step
    available_defenders,      # list of player objects (race pool)
    defender_starts,          # dict {pid: GridCoord} — end-of-preceding-step
    is_away_offense,          # bool
) -> dict
```

Returns:

| Key | Type | Meaning |
|---|---|---|
| `shooter_target` | GridCoord | Where the shooter ends up |
| `defender_target` | GridCoord | The single point defenders race to |
| `defender_end_coords` | dict[pid, GridCoord] | End positions for the race pool only |
| `first_arriver_id` | str \| None | Defender who reached the target before `t_shooter`, or None |
| `contested` | bool | True if a defender is within 11 Euclidean of the shooter and trails on x by ≤ 3 at t_shooter |
| `shot_defender_id` | str \| None | Nearest qualifying defender for `calculate_shot_score` (None if uncontested) |
| `t_shooter_game_seconds` | float | Shooter's traversal time — drives the shot step's advance trigger |

## UESS compliance

Pure function. No side effects on game state. Caller:

1. Calls `compute_fb_shot_geometry(...)` with the right inputs.
2. Uses returned `shot_defender_id` + `contested` to call
   `calculate_shot_score` (or `resolve_shot` via roles override).
3. Stamps `defender_end_coords` + `shooter_target` onto the schema
   step's end coords for the schema emitter to render.

Schema emitters remain pure renderers.

## Caller integration sites

| FB | File | Site(s) |
|---|---|---|
| Steal-FB | `BackEnd/engine/after_steal_fast_break.py` | Inline (helper IS the geometry source) |
| Rim Runner | `BackEnd/engine/rim_runner_fast_break.py` | 3 sites, via private adapter `_apply_universal_geometry_for_rr_shot` |
| Covert Release | `BackEnd/engine/phase_resolution.py:1823` area | Inline at the SHOT branch of `resolve_fast_break_logic` |

## Animation and UESS

| Topic | Doc |
|---|---|
| Schema contract, migration table, known gaps | [`UESS_System.md`](../00_General_Systems/UESS_System.md) |
| Per-turn steps (HCO, FB, OREB, etc.) | [`Step_By_Step_System.md`](../00_General_Systems/Step_By_Step_System.md) |
| Advance triggers | [`Step_By_Step_System.md`](../00_General_Systems/Step_By_Step_System.md) (Advance_Triggers.md merged in, June 2026) |
| Legacy `fastBreak.js` timing / trigger backlog | [`projects/bugs.md`](../projects/bugs.md) § Fast Break animation backlog · archived map in [`projects/Z-Completed/Fast_Break_Refactor.md`](../projects/Z-Completed/Fast_Break_Refactor.md) |

All four FB play keys (`covert_release`, `rim_runner`, `triangle`, `after_steal`) use backend `animation_steps` when present; FE `AnimationEngine` `MIGRATED_FB_PLAYS` gates schema playback. Legacy `runFastBreakSequence` runs only without steps.

Missed FB rebound-capture detail is backend-authored: the shot turn carries the rebound winner, bounce spot, and near-bounce failed-attemptor IDs; the discrete DREB/OREB schema turn renders those players. No frontend rebound-attemptor selection is allowed.

---

## Known limitations / scope notes

- **Triangle** is intentionally not migrated. Its existing shot
  location and defender selection logic remains.
- **Backward compatibility:** legacy paths in RR/CR are preserved
  in-file behind the feature flags. Set either flag to `False` to
  revert that FB type without affecting the other.
- **Gameplay-feel impact:** uncontested = auto-make introduces a higher
  FB scoring rate compared to legacy. Tunable via the flag.
