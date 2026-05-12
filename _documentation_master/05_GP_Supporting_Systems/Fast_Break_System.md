## Fast Break System ✅ **COMPLETE** (January 2025; Rim Runner March 2025; FB shot contest grid unification March 2026)

> **Canonical reference (Bible):** This document is the **single source of truth** for sustained Fast Break knowledge—selection logic, coordinates, defensive stops, shot attempts, constants, and file touchpoints. In-flight implementation checklists may live in `docs/To Do/FB_Playcall_Update.md`; SS&S process notes for FB shot routing live in `docs/To Do/Archive/fast_break_shot_spot_process_review.md`. If something conflicts, **treat this file as authoritative** unless the team explicitly updates both.

**Base Constants**

1. **Defensive Stop Y-Range**: `DEFENSIVE_STOP_Y_RANGE = 6` for **steal → fast break** (defender must be within ±6 y of outlet receiver to force stop). **`DEFENSIVE_STOP_Y_RANGE_DREB_OUTLET = 8`** for **DREB → outlet** fast breaks (Covert Release; wider band than steals).
2. **Ball Handler Movement (Defensive Stop/Shot)**: X: 5-10 spots toward basket, Y: ±3 spots
3. **Stopper Positioning (defensive stop only)**: 1–3 spots in front of ball handler end, same **Y** (confrontation — not the rim shot spot)
4. **Shot contest defender (all fast break shot attempts)**: Grid vs the shooter’s **final** spot (`_bh_final_x/y`, exposed as `shot_spot`). Shooter shot spot is now a tighter rim band: **x = basket.x ± uniform integer in [1, 4]** and **y = basket.y + uniform integer in [−3, +3]** (`FB_SHOT_SPOT_X_MIN/MAX`, `FB_SHOT_SPOT_Y_RANGE` in `BackEnd/constants/fast_break_constants.py`). Primary defender uses **x = shooter_x - 2** for home offense or **x = shooter_x + 2** for away offense, and **y = shooter_y + uniform integer in [−2, +2]** (`SHOT_DEFENDER_X_OFFSET`, `SHOT_DEFENDER_Y_RANGE`). In beat-stopper cases, the **second** contest defender uses the same **x** and **y = primary_y ± 3** based on his starting row (`SECONDARY_SHOT_DEFENDER_Y_OFFSET`). **Helpers:** `fast_break_shot_defender_end_coords(...)` and `fast_break_secondary_shot_defender_end_coords(...)`. **JS mirrors:** `fastBreakShotDefenderGridVsShooter()` and `fastBreakSecondaryShotDefenderGrid()` in `FrontEnd/static/js/phaser/constants/fastBreakConstants.js` for fallbacks; `animateFastBreakShotWithStopper` prefers `turnData.shot_spot` / `defender_spot` from the backend when present.
5. **Steal Entry Movement**: X: 5-10 spots toward basket, Y: ±4 spots (clamped 3-47)
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
   - **Steal Entry**:
     - Ball handler = stealer (from `game_state["last_stealer"]`)
     - No outlet pass (no outlet passer/receiver)

4. **Calculate Ball Handler Position After Entry**
   - **DREB Entry (Covert / generic)**: Ball handler receives outlet pass at starting position (no movement during outlet pass)
     - Priority 1: `defense_release_coords` from most recent MISS/MAKE turn
     - Priority 2: `offense_getback_coords` from most recent MISS/MAKE turn
     - Fallback: `player.coords`
   - **DREB Entry (Rim Runner / Triangle)**: After a **successful** outlet contest, sim coords for the rim runner and outlet ball handler are set from **`rim_runner_burst_phase`** (`rr_to`, `receiver_to`); `roles["ball_handler_outlet_x/y"]` match **`receiver_to`** for stop/shot geography and animation. **Denied** outlet: coords are **not** advanced (only the burst payload is present for the client).
   - **Steal Entry**: Ball handler moves 5-10 x spots toward basket, ±4 y spots (clamped 3-47)
     - Uses `last_stealer_coords` from game_state if available

5. **Check All Defenders for Defensive Stop**
   - Loop through **all defenders in `def_lineup`** (not just `fb_roles["defense"]`)
   - Get defender coordinates:
     - Priority: `offense_getback_coords` from most recent MISS/MAKE turn (if defender was a get-back player)
     - Fallback: `defender.coords`
   - For each defender, check:
     - **X-Coordinate Check (Ahead)**: 
       - Home offense: `defender_x >= ball_handler_x` (basket at x=90)
       - Away offense: `defender_x <= ball_handler_x` (basket at x=10)
     - **Y-Coordinate Check (Within Range)**: `|defender_y - ball_handler_y| <= 6` (steal entry) or `<= 8` (DREB/outlet entry)
   - Track closest stopping defender (x-distance only) and **closest defender overall among get-back players only** (Euclidean distance; only defenders in `offense_getback` from most recent shot are eligible for shot defender)

6. **Determine Event Type**
   - **0 Defenders**: Always `SHOT`
   - **Defender Ahead AND Within Y-Range**: Skill check between ball handler and defender
     - **Geography Check**: Defender must be ahead AND within y-range (**±6** steal, **±8** DREB/outlet) (determines if stop attempt is possible)
     - **Skill Check** (if geography check passes):
       - `break_score = ball_handler.attributes["AG"] + ball_handler.attributes["BH"] * random(1-6)`
       - `stop_score = defender.attributes["AG"] + defender.attributes["OD"] * random(1-6)`
       - If `stop_score >= break_score` → `DEFENSIVE_STOP` (defender wins)
       - If `break_score > stop_score` → `SHOT` (ball handler wins, beats defender)
         - **Animation**: stopper + optional trail defender use the **unified shot contest spots** vs rim **`shot_spot`** (see **Shot contest grid**); not “1–3 from outlet start” on the sim
         - **Shot defender**: Closest get-back (by distance) **excluding the failed stopper**; if no other get-back, no shot defender (defender_count = 0)
   - **Otherwise**: `SHOT`. **Shot defender only when 1 or 2 get-back players**: closest get-back by Euclidean distance; if 0 or 3+ get-back, no shot defender (defender_count = 0)

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
- **What**: Release defender selection, IQ/AG bands, outlet receiver coords, then **defensive stop vs shot** per Steps 4–8 (geography + AG/BH vs AG/OD skill check, shot via `resolve_shot`).
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
- **Outlet chain (sim + animation)**: Offensive **outlet target** `(tx, ty)` is computed from the rim runner’s **post–burst-sprint** vertical half: `ty = 15` if rim runner ends **above** the lane (`y > 24` in HOME grid), else `ty = 35`. Each non–rim-runner offensive player gets a candidate `tx` from **their** current **x** plus **8** grid spots toward the basket, clamped to the backcourt band (**home** offense: `min(start_x + 8, 40)`; **away**: `max(start_x - 8, 60)`). The **outlet receiver** is the offensive player (not the rim runner) **closest** to their own `(tx, ty)` in grid space. If that player is the **rebounder**, there is **no outlet pass** (`roles["outlet_passer"] = null`); the rebounder **dribbles** to `(tx, ty)` in parallel with the burst-phase animation. Otherwise **`outlet_passer`** = rebounder and **`outlet_receiver`** = that closest player. `roles["rim_runner_sequence"]` is **true** only for **`rim_runner`**, not **`triangle`**.
- **Dynamic outlet / burst x (rebound-driven)**: When the prior shot turn has **`ball_bounce_x`** (e.g. block/miss bounce) or rebounder x falls in a “bad” band, **`resolve_rim_runner_fast_break`** may override: **home** offense — `25 < rebound_x < 50` → outlet receiver target **`rebound_x + 12`**; **away** offense — `50 < rebound_x < 75` → **`rebound_x - 12`**. Then rim runner **`rr_to.x`** = that receiver target **plus** the usual burst delta (**20–25** if animation burst success, **9–14** if fail) **toward the basket** from the receiver target (not from RR’s pre-burst x). **Y** logic unchanged. Outside those bands, legacy **+8** outlet candidate + RR sprint from RR’s current x applies.
- **Rim runner sprint (animation geometry only)**: Roll `movement_factor = random.randint(1, 100)` vs organic threshold **`0.6*AG + 0.2*IQ + 0.2*CH`** (no cap at 100). **Success**: move rim runner **x** by **`random.randint(20, 25)`** toward the basket (**+** home offense, **−** away); **fail**: **`random.randint(9, 14)`**; **x** clamped **`[4, 97]`**. **New y** uses rim runner **y before the sprint**: if **`y > 24`** → **`random.randint(30, 35)`**, else **`random.randint(15, 20)`**. (Sim burst open/closed **`fb_open`** below still uses the separate AG/IQ vs defender roll.) *When dynamic placement applies, the x delta is measured from the computed outlet receiver target instead of RR’s start x.*
- **`roles["rim_runner_burst_phase"]`**: Structured payload for the client: `rr_id`, `rr_from` / `rr_to`, `burst_success`, `movement_factor`, `burst_threshold`, `skip_outlet_pass`, `outlet_passer_id`, `outlet_receiver_id`, `receiver_to` `{x,y}`, `outlet_defender_id`, `outlet_defender_to` (closest outlet contest defender tweens to **passer x ± 2** same **y** as passer; home **+2**, away **−2`), `other_players` (everyone not passer, that defender, rim runner, or outlet receiver). **Offense (rebounding team):** **x** toward basket **`random.randint(1, 4)`**, **y** unchanged. **Defense — get-back** (from prior shot’s `offense_getback`, excluding outlet contest defender): **x** **15** spots toward the attacking basket, clamped so they do not cross the rim **x**; **y** up to **6** toward the rim runner’s burst **y** (`rr_to.y`), without crossing past the RR in either vertical direction. **Defense — all other defenders:** roll `x_roll = random.randint(1, 100) −` defending team’s **`fb_opp_modifier`** (clamped **−10…+10**); if **`0.5×IQ + 0.5×AG` > `x_roll`**, move **15–20** x spots toward the basket (same clamp); else **8–12** x spots; **y** still uses **up to 6 toward y = 25** (legacy `_y_toward_25`). Present on **both** successful and **denied** outlet turns so the sprint/setup can still animate when **`rim_runner_outlet_failed`** is true.
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
- **Code**: `BackEnd/engine/rim_runner_fast_break.py`; entry from `resolve_fast_break_logic()` when DREB + `RIM_RUNNER`.

#### Triangle (`triangle`)

- **Status**: Planned dedicated Fast Break play family. It should live inside the universal Fast Break framework, but use its own phase graph rather than the Rim Runner hold-up / lane-pass resolution after the initial RR read.
- **Entry**: Triangle drafts off the Rim Runner DREB entry. It uses the same RR burst, outlet receiver placement, outlet contest, and denied-outlet branch. If the outlet is denied, Triangle uses the same denied-outlet comeback branch and then enters `HCO` exactly as RR does.
- **RR read gate**: After a successful outlet, Triangle still performs the RR lane-pass read first. It uses the same `burst_offense_score`, `burst_defense_score`, `correct_read`, and `pass_attempted` logic as RR, except the open-lane threshold is stricter: `fb_open = (burst_offense_score * 0.6) > burst_defense_score`. If `pass_attempted = True`, Triangle resolves exactly like the RR lane-pass branch. If `pass_attempted = False`, Triangle enters its own setup/decision flow below.
- **Triangle setup**:
  - Two remaining offensive players become corner players and use RR burst movement to `upper corner` / `lower corner` (`HCO_STRING_SPOTS` labels).
  - Ball handler uses non-burst movement to `upper wing` if `y > 25`, else `lower wing`.
  - Rim runner uses non-burst movement to same-side `upper lowPost` / `lower lowPost`.
  - Trailer (rebounder / outlet passer) uses non-burst movement to the opposite wing.
  - Defenders: closest-by-x defender to the offensive basket tracks the rim runner via skeleton HCO man-matchup placement; second-closest-by-x tracks the ball handler the same way; the other three target random lane spots from `lower/upper lowPost`, `lower/upper midPost`, `lower/upper highPost`, `basketSpot`, `midLane`, `topLane`, `lower/upper bird`, and `lower/upper apex`.
  - If defense `fb_opp_modifier > 5`, any non-get-back defenders use RR burst movement during this setup; otherwise defensive movement is non-burst.
- **Triangle setup advance trigger**: rim runner and ball handler both reach their setup spots.
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

#### After Steal (`after_steal`)

- **When**: Fast break entered from **steal** (not DREB outlet). `play_key_for_fast_break_entry(False)` → **`after_steal`**.
- **What**: No Covert Release outlet; ball handler = stealer; steal entry movement; same **defensive stop y-range ±6** and stop vs shot logic as in Steps 4–8 (steal branch). See **Steal Entry** in Step 3 above.

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
   - Defender is ahead of ball handler after outlet pass AND within y-range (**±6** steal, **±8** DREB/outlet)
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

**Logic (HOME Orientation):**

**Home Offense:**
- Basket at x=90 (larger x is closer to basket)
- Defender ahead if: `defender_x >= ball_handler_x`
- **Defender must also be within y-range of outlet receiver** (±6 steal, ±8 DREB/outlet — see `defensive_stop_y_range` in `resolve_fast_break_logic`)
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Away Offense:**
- Basket at x=10 (smaller x is closer to basket)
- Defender ahead if: `defender_x <= ball_handler_x`
- **Same y-range rule** (±6 vs ±8 by entry type)
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Multiple Get-Back Players:**
- If multiple get-back players meet both conditions (ahead AND within y-range), the closest one (by x-distance) forces the defensive stop
- If neither get-back player meets both conditions, and there are **1 or 2 get-back players**, the closest get-back (by Euclidean distance from outlet receiver) becomes the shot defender

**Shot Defender Selection (Get-Back Only, 1 or 2):**
- There is a **potential shot defender only when there are 1 or 2 get-back players** on the defensive team (from `offense_getback` on the most recent shot).
- **Pool**: Only get-back players are eligible. The closest get-back by Euclidean distance from outlet receiver becomes the shot defender.
- **0 or 3+ get-back**: No shot defender is assigned (defender_count = 0); charge/block check is skipped; shot proceeds as uncontested (threshold logic still uses effective count).
- **Ball handler beats defender**: The get-back defender who attempted the stop and lost is **excluded** from being the shot defender. The closest **remaining** get-back (by distance) becomes the shot defender; if there is no other get-back, no shot defender (defender_count = 0).

**Skill Check Implementation:**
- **Two-Step Process**: Geography determines if a stop attempt is possible, then skill check determines the outcome.
  1. **Geography Check**: Defender must be ahead AND within y-range (**±6** steal, **±8** DREB/outlet — determines if stop attempt is possible)
  2. **Skill Check** (if geography check passes):
     - `break_score = ball_handler.attributes["AG"] + ball_handler.attributes["BH"] * random(1-6)`
     - `stop_score = defender.attributes["AG"] + defender.attributes["OD"] * random(1-6)`
     - If `stop_score >= break_score` → `DEFENSIVE_STOP` (defender successfully stops the break)
     - If `break_score > stop_score` → `SHOT` (ball handler beats the defender)
- **Animation Behavior When Ball Handler Wins**:
  - **Stopper** tweens to the primary shooter-relative FB shot-defender spot
  - Ball handler tweens to rim shot spot; **trail shot defender** (if assigned) uses the same **x** and a **±3 y** offset from the stopper so the sprites do not stack
  - Flag `ball_handler_beats_defender = True` triggers `animateFastBreakShotWithStopper` on the client
  - **Shot defender**: The failed stopper is excluded from the *pool*; the closest **other** get-back becomes the shot defender, or none if he was the only get-back

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

**Implementation:**
```python
# getback_player_ids = from most_recent_shot_turn.get("offense_getback", [])
# ✅ Check ALL defenders in def_lineup for stop/shot geography; shot defender pool = get-back only
closest_stopping_defender = None  # Defender who is ahead AND within ±6 y-coords
closest_defender_overall = None   # Closest defender among GET-BACK PLAYERS ONLY (for shot attempts)
closest_distance_overall = float('inf')

for defender in def_lineup.values():
    defender_id = defender.player_id
    defender_outlet_x = get_defender_coords_x(defender, most_recent_shot_turn)
    defender_outlet_y = get_defender_coords_y(defender, most_recent_shot_turn)
    
    x_distance = abs(defender_outlet_x - ball_handler_outlet_x)
    y_distance = abs(defender_outlet_y - ball_handler_outlet_y)
    total_distance = (x_distance ** 2 + y_distance ** 2) ** 0.5
    
    # Track closest defender overall ONLY among get-back players
    if defender_id in getback_player_ids and total_distance < closest_distance_overall:
        closest_distance_overall = total_distance
        closest_defender_overall = defender
    
    # Check if defender is ahead (x-coordinate check) and within ±6 y
    is_ahead = (defender_outlet_x <= ball_handler_outlet_x) if is_away_offense else (defender_outlet_x >= ball_handler_outlet_x)
    is_within_y_range = abs(defender_outlet_y - ball_handler_outlet_y) <= 6
    if is_ahead and is_within_y_range:
        defender_ahead = True
        x_distance_only = abs(defender_outlet_x - ball_handler_outlet_x)
        if x_distance_only < closest_stopping_distance:
            closest_stopping_distance = x_distance_only
            closest_stopping_defender = defender

num_getback = len(getback_player_ids)
# Shot defender only when 1 or 2 get-back; when ball handler beats defender, exclude stopper from pool
if defender_ahead and closest_stopping_defender:
    # skill check...
    if ball_handler_wins:
        # Shot defender = closest get-back by distance EXCLUDING stopper_id (loop def_lineup, filter getback_player_ids and id != stopper_id)
        fb_roles["defender"] = shot_def  # or None if no other get-back
        fb_roles["defender_count"] = 1 if fb_roles["defender"] else 0
else:
    event_type = "SHOT"
    if num_getback in (1, 2) and closest_defender_overall:
        fb_roles["defender"] = closest_defender_overall
        fb_roles["defender_count"] = num_getback
    else:
        fb_roles["defender"] = None
        fb_roles["defender_count"] = 0
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
- `BackEnd/engine/rim_runner_fast_break.py` — **`resolve_rim_runner_fast_break()`** — Rim Runner DREB outlet play (outlet contest, burst, read, pass/intercept/bat/shot)
- `BackEnd/engine/phase_resolution.py`
  - `resolve_free_throw_logic()` — missed FT + DREB: `fast_break_probability_from_slider(def_team["fast_breaks"])` for FAST_BREAK vs HCO
  - `resolve_turnover_logic()` / FCP / HCT steal branches — `fast_break_probability_from_slider(def_team["aggression"])` (**stealing** team)
  - `resolve_fast_break_logic()` - Determines defensive stop vs. shot attempt; increments **`fast_break_plays`** and sets **`fast_break_play`**; **early return** to Rim Runner resolver when DREB + **`rim_runner`** or **`triangle`**
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

- **User FB play settings**: Replace **50/50** DREB play selection with user-configured weights (Rim Runner vs Covert Release vs **Triangle**).
- **Triangle (`triangle`)**: Implement engine path and extend *Fast break plays* subsection above.
- **Fast Break Fouls**: Add foul handling during fast break sequences
- **Fast Break Turnovers**: Add turnover handling during fast break sequences
