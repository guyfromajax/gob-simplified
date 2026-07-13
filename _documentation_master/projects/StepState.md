# StepState — Dynamic HCO Turn Engine (working doc)

**Status:** aligning (agent ↔ human). This is a shared scratchpad to agree on the architecture before building — **not** finished documentation. Keep it terse.

---

## ▶ RESUME HERE (checkpoint 2026-07-13)

> **Numbering:** formal "Staged plan" (Stage 0–3) below. **Stages 1, 2, 3 ALL DONE + committed on develop.** The core refactor (one resolver, one walk, moment fused, grid shared, legacy gone) is complete. What remains is **residuals + cleanup**, not new stages — see NEXT.

### ✅ Committed since 07-12c
- **Moment fusion** (`b729eab34` "streamlined spine of HCO steps") — Path A, details below.
- **HCO batted-OOB double-send fix** (`8ccedff56` "fiixed OOB animation bug")** — the bat-OOB fired TWO ball trajectories (step-based emitter trajectory + the HCT-era FE imperative `_runHctBatOobBallSend`), so the ball went OOB then flew back to the defender and OOB again. Fix: **imperative-only** (matches HCT/FCP) — removed the step-based `bat_reach` override + `bat_oob` step event from `_finalize_hco_pass_bat_oob` (ball stays with the passer, imperative flies it), and made the FE read the backend's `bat_oob_target` instead of recomputing (`oobGrid = turnData.bat_oob_target ?? resolveNearestOutOfBoundsGrid(...)`). Live-confirmed single clean animation. UESS-compliant (exit point engine-owned).
- **Pass-contest tunable** — promoted the inline INTERCEPT-vs-BAT_OOB split literal to a named constant `PASS_DEFLECT_KIND_D=200` (`pass_contest.py`); corrected the stale `TIER_HI` (retired) rows + added the split to `Tunable_Constants.md` + `Dynamic_HCO_System.md`. (Uncommitted as of this checkpoint.) Sim: BAT_OOB ≈ 46% of deflections — not rare; ratio is CH+IQ-driven.

### ✅ Moment fusion — DONE (Path A, 2026-07-12c, committed `b729eab34`)
Chose **Path A** (invert spine, reuse the existing `[4]` non-shot machinery — B would have duplicated ~300 lines of turnover+foul finalize). Executed the low-risk **hoist+cache** variant (didn't physically relocate `[2]`–`[4]`):
- **Moment fused into `_resolve_hco_offense_shot_dynamic`** — per-turn engagement rolled ONCE; per REACHED step it rolls the on-ball moment moment-FIRST (before the scripted-pass/shot/dish resolves). A hard outcome returns a `{"moment_result", "skeleton"(reached), "moment_stop_index", "moment_defender_id"}` dict; near-misses append reach-in tags. Gated by a new `roll_moment` param (default False) so ONLY the authoritative up-front walk rolls it.
- **Spine**: the resolver runs ONCE up front (both motion + set play), after `final_skeleton` is chosen. Moment → set `result` + truncate `final_skeleton` → existing stopper/`[4]` finalize it (unchanged). Shot → cache `_hco_precomputed_shot_info`; the reached walk drives the shot-clock check `[2]`. `[5]` consumes the cache instead of re-walking (a 2nd RNG walk would desync moment↔shot). Both `_resolve_hco_moment_walk` call sites + the post-hoc reach-in stamping removed.
- **`roll_moment` fix**: the `[5]` fallback re-walks (setplay try + motion fresh) must NOT fire a moment (the shot path can't route a moment dict, and `[4]` already ran). `roll_moment=False` on all callers except the up-front spine call. (First run KeyError:'shooter' → this.)
- **`_resolve_hco_moment_walk` kept but RETIRED from the spine** — still the unit-tested reference spec (`tests/test_motion_moment.py`, couldn't run: pytest blocked on gob-staging). Keep it in sync with the fused copy, or repoint the tests + delete later.
- **Baseline-10 verified (20 games):** distribution shifted **as predicted** — Shot 69.0%→**77.0%** (+7.9pp); moment-outcomes 31.0%→23.0% (O_FOUL 2.3→1.1, D_FOUL 8.9→5.7, DBTO 11.4→9.2, STEAL 8.4→7.0). No crash, no new outcome types. The −7.9pp is exactly the moments that used to pre-empt shots on unreached steps.

**✅ Walk-time contest consolidation — INVESTIGATED 2026-07-13, already resolved / coverage patch is load-bearing (measured).** The doc previously listed "consolidate the walk-time contest → retire `_hco_contest_final_skeleton`" as the one meaty residual. Empirical audit (real sims, non-invasive wrappers) found BOTH halves stale:
- **Walk-time grid seam is already closed** (`b83f1ec51`): the resolver stamps `compute_defender_grid` at ~5743 **before** the walk; `_hco_step_def_xy` prefers the stamp (~4936). So `_hco_contest_skeleton_pass` + `_apply_dish_contest` during the walk already read the rendered grid — no reconstruction-fallback seam. Nothing to consolidate.
- **The coverage patch is LOAD-BEARING, not redundant.** Measured ≈ **1.5 picks/game ≈ 18% of all HCO interceptions**, on **dish steps** (`passer→receiver`, receiver=shooter) that the per-step `_apply_dish_contest` didn't tag (NOT recalibration — 0/9 after recalib). It's effectively the single *final-skeleton* contest sweep. **Retiring it would silently drop the steal rate ~18%** — so it stays. Decision (human, 07-13): keep it; not a residual.

**NEXT (all that remains — small cleanups + follow-ups, no architectural work):**
1. **Trivial cleanup** (low-risk housekeeping): delete the neutered `_dynamic_hco_motion_enabled`; collapse the 3 resolver wrapper names (`resolve_motion_offense_shot` / `_resolve_motion_offense_shot_dynamic` / `_resolve_setplay_offense_shot_dynamic`) → 1; prune the retired flag's gate tests.
2. **Bat-OOB follow-ups** (from `8ccedff56`, recorded in bugs.md): remove the now-**inert** `bat_reach`/step-`bat_oob` handling in `skeleton_step_emitter.py` (~1634–1671, ~1992–1999) — no writer remains; and close the **HCT UESS gap** (HCT's exit point is still FE-derived — send a `nearest_oob_point` target from `dynamic_hct.py`).
3. **Stage-2 residual — verify render adoption** (bookkeeping): confirm no redundant/second defender-grid draw remains.
4. *(Optional, deferred)* true single-site consolidation — make the walk's non-standard dish paths self-contest, then retire the coverage patch. Real steal-rate regression risk; net simplicity debatable. Not worth it now.

### Shipped since the 07-11b checkpoint (all on develop)
- **Moment-teleport pin (`eb0408de6`)** — moment fired foul/steal/turnover at a known step `i` but discarded it → `apply_stopper` used a random blast-radius step (ball snap-back). Now stashes `_hco_moment_stop_index=i`; apply_stopper consumes it. Fixes the DB-turnover-after-pass teleport.
- **Walk-time interception seam / Option B (`b83f1ec51`)** — extracted `_stamp_contest_defender_grid`, now called BEFORE the offense walk too. ALL HCO interception contesting (skeleton passes, dishes, hot-reads, coverage) reads the render grid, man+zone. No residual.
- **Resolver unification (`7b578cb36`)** — motion+setplay dynamic resolvers were ~255-line near-duplicates (one diff: setplay `_setplay_recovery_roll`). Merged into `_resolve_hco_offense_shot_dynamic(..., is_setplay=False)`. Deleted the 257-line dup; kept thin delegates.
- **BAT_OOB reachable + zone exclusion + Batted-OOB UESS Layer B (`8d86c6abd`, side-quest off the pass-contest thread):** the old INTERCEPT/BAT_OOB two-tier band was narrower than the score's quantization step → BAT_OOB never fired. Replaced with a single deflect threshold (tier_mid) + `rand(1,200)<CH+IQ` INTERCEPT-vs-BAT split (all callers). Zone now excludes the on-ball zone defender (`_zone_bh_defender`) from picking his own passer's pass. HCO batted-OOB now emits a proper UESS animation via `nearest_oob_point`. Live-confirmed getting both. **⚠️ SUPERSEDED (`8ccedff56`, 07-13):** the step-based `bat_reach`/`bat_oob`-event trajectory this shipped was later removed — it double-fired with the FE imperative send. Now imperative-only (see the 07-13 committed list up top).
- **✅ Stage 3 (MOTION) — legacy removed (`5c5aad53c`):** the 219-line legacy random-step body of `resolve_motion_offense_shot` was still LIVE via recalibration (Second Chance `forced_shot_step_index` skipped the dynamic resolver) + the `GOB_DYNAMIC_HCO_MOTION` kill switch. Removed: (1) `_resolve_hco_offense_shot_dynamic` gained a `forced_shot_step_index` mode; (2) `resolve_motion_offense_shot` is now a thin wrapper → dynamic (recalibration passes through); (3) legacy body deleted; (4) motion flag retired (gates unconditional, `_dynamic_hco_motion_enabled()` neutered to always-True). Baseline-10 holds. **Simplifies the spine ahead of the fusion.**

### ✅ Moment fusion — DONE 2026-07-12c (formal Stage 1). See the DONE block up top. Design record kept below:
Goal (ACHIEVED): fold the on-ball moment into the unified per-step walk per Decision #1 (moment EVERY step, moment-first, first-terminal-in-step-order wins) → the moment stops pre-empting a shot on a step the offense never reached. **Executed as Path A (hoist+cache), verified +7.9pp shot shift.**

**The spine order BEFORE the fusion (historical — this is the problem Path A solved; the moment walk `[1]` and the two `_resolve_hco_moment_walk` call sites no longer exist):**
```
[1] moment walk (motion ~6583 + setplay ~6849)  → sets result = STEAL/DBTO/O_FOUL/D_FOUL if it fires
[2] shot-clock check + recalibration (~6867)     → may set result = SHOT_CLOCK_VIOLATION
[3] apply_stopper(final_skeleton, result) (~6906) → truncates for non-shot results
[4] non-shot machinery (~6924→7285→7311→7360…)   → defender-override → event_type → foul/turnover finalize (ALSO serves shot-clock violations + general fouls; ~450 interleaved lines)
[5] shot resolution (the resolver) (~7647)        → runs LAST, gated event_type=="SHOT"; then coverage contest + _finalize_hco_pass_interception / _finalize_hco_pass_bat_oob
```
**Path A = INVERT the spine:** run the resolver `[5]` FIRST (with the moment fused into its loop), derive `result` from its output (shot / interception / **moment**), then run `[2]`+`[3]`+`[4]` on that. It's NOT a block-move — the stopper + non-shot machinery consume `result` and currently run BEFORE `[5]`. **Entanglement to handle:** `[2]` shot-clock/recalibration sits between and keys on `result=="SHOT"` + skeleton timing; moving the resolver first means the shot-clock check runs on the resolver's OUTPUT (where the offense actually shot — arguably more correct, but restructures recalibration too, not just moves it).

**Verdict:** Stage 3 helped (ONE shot path now, not two) so the reorder is cleaner than when deferred — but it's still a genuine spine restructuring (resolver + shot-clock + stopper + non-shot machinery re-keyed on the resolver's output). Highest-blast-radius change of the project. **Path B** (a standalone multi-outcome moment finalizer, mirroring `_finalize_hco_pass_interception`) is the alternative but re-implements the foul/turnover finalize for 4 types. **START HERE next session:** decide A vs B, then for A do the reorder in behavior-preserving steps (e.g. first thread the resolver's output into a unified `result`, then move `[2]`–`[4]` after `[5]`).

### 🔎 Objective audit (2026-07-12b) — "one resolver for motion + set play; simplify execution"
**Core objective ✅ MET:** one shot resolver `_resolve_hco_offense_shot_dynamic(…, is_setplay)` serves both; the ~255-line dup is gone. **Full "simplify execution" 🟡 PARTIAL** — the orchestration around the resolver is still branchy + ASYMMETRIC between motion and set play:

| Concern | Motion | Set play | Unified? |
|---|---|---|---|
| Shot resolver | dynamic via `resolve_motion_offense_shot` wrapper | dynamic, called direct (7472) | ✅ same resolver, **2 invocation styles** |
| Legacy fallback | removed (Stage 3) | **"standard set-play shot path" STILL LIVE** (7474/7476 when dynamic → None/error/flag-off) | ❌ |
| Flag | retired | `_dynamic_hco_setplay_enabled()` still gates | ❌ |
| Moment walk | called 6581 (on `skeleton`) | called AGAIN 6654 (on `final_skeleton`, flag-gated) + duplicated reach-in stamping | ❌ shared fn, **dup call sites** |
| Skeleton | base_loop | variant-selected (`get_hco_skeleton(lean_score)`) | inherent to set plays (variants are real, keep) |
| Up-front event tables | skipped (unconditional) | `resolve_hco_outcome` still the setplay/flag-off legacy | ❌ |

**Gaps vs the plan:** setplay legacy + flag → **Stage 3 (setplay)** [in plan]. Moment dup → **the fusion** collapses BOTH call sites at once [in plan]. **NOT in plan:** (a) the wrapper cleanup (3 names → 1), (b) explicitly scoping `resolve_hco_outcome` + the "standard set-play path" under Stage 3 setplay.

**⚖️ ORDER QUESTION — RESOLVED 2026-07-12b:** did **Stage 3 setplay FIRST** (`6e04d15df`) — it was the direct completion of the symmetry objective and low-risk. ✅ Symmetry achieved. **Remaining:** the moment fusion (correctness capstone) + trivial flag/wrapper cleanup.

> **Also open:** trivial — delete the neutered `_dynamic_hco_motion_enabled` + prune its gate tests; collapse the 3 resolver wrapper names.
> **Historical note:** earlier this block called Stage-2 work "Stage 1 man/zone" — a mislabel; it is **Stage 2**. Formal **Stage 1** = the moment fusion (resolvers unified ✅; moment-into-loop deferred).

**✅ Stage 2 (defender-grid sharing) COMPLETE + verified on live turns (develop).** The interception contest now judges against the render's ACTUAL defender positions for BOTH man and zone, in one unified display frame. `🔬 STEPSTATE GAP` (canonical vs contest) measured **0% for man AND zone** on live play (was man 22–64%, zone up to 100%/96px mirror). The zone+away contact_point mirror is fixed.

**Shipped + pushed (develop) — commit chain `c3929ef4b`→`14befe175`:**
- `compute_defender_grid` **extracted** from `skeleton_to_animations` (split into `_build_all_animations` + thin wrapper); pure + sim-safe (bypasses the `_is_full_simulation` early-return). Made **pure** (deep-copies skeleton — the build mutates BH coords in place).
- **RNG discovery (load-bearing):** defender placement uses `random` (~2px shade; proven deterministic-under-fixed-seed). So contest and render as *two separate draws* can NEVER agree → recomputation is *incorrect*, not just wasteful. This is the concrete reason for "resolve once → freeze → draw."
- **Option A (share the one draw):** the HCO emit stashes its exact per-player `animations` on the game (`game._hco_render_animations`, transient, NOT in payload); `build_step_states` extracts `StepState.defense` from those via `Animator.defender_grid_from_animations`. Contest == render by construction. Sims fall back to `compute_defender_grid`'s own single draw (no render to match).
- **Stage 2 Step A (man):** `_hco_contest_final_skeleton` stamps `compute_defender_grid` on each step pre-contest (the emit's exact stash isn't available yet — contest runs pre-emit + truncates the skeleton the emit draws → circular; compute_defender_grid is the same code, ~2px RNG, immaterial vs the lane band). `_hco_step_def_xy` MAN branch reads the stamp.
- **Stage 2 Step B (zone):** hoisted the stamped-read above the man/zone split — when stamped, BOTH modes use the grid with **identity `_pt`** (one display frame). Kills the zone HOME-frame path (`assign_all_zone_defenders` + HOME-flipping `_pt`) that produced the mirrored contact_point. Legacy per-mode fallback preserved for the unstamped path.

**Next concrete steps (in the formal scheme):**
1. ~~**Stage 2 residual — consolidate the walk-time contest.**~~ **✅ RESOLVED 2026-07-13 (see RESUME HERE):** the walk-time grid seam was already closed by `b83f1ec51` (resolver stamps before the walk; `_hco_step_def_xy` reads the stamp). And the coverage patch `_hco_contest_final_skeleton` is **load-bearing** (measured ≈18% of interceptions — dishes the per-step paths don't tag), so it stays, not retired.
2. **Stage 2 residual — verify render adoption.** The render already computes the same grid via the extract, so contest+render share one value today; confirm no redundant/second draw remains. (This is the last bookkeeping bit of Stage 2, NOT a new stage.)
3. **Stage 1 (walk unification) — ✅ moment fusion DONE (2026-07-12c).** Moment + offense now walk in ONE resolver loop (moment-first, reached steps only); both `_resolve_hco_moment_walk` call sites removed. Interception already runs inside the resolver. *The coverage patch (`_hco_contest_final_skeleton`) STAYS — measured load-bearing (≈18% of interceptions, dishes the per-step paths miss); it's the single final-skeleton contest sweep, not a residual (audit 2026-07-13).* The DB-turnover-after-pass teleport was already pinned tactically (`eb0408de6`); the fusion makes the pin structural.
4. **Stage 3 — ✅ DONE (motion `5c5aad53c` + setplay `6e04d15df`).** Legacy + recalibration bypass paths removed.

**Hard constraint (still true):** the contest's grid must be a pure resolution-time computation (interception = OUTCOME, identical animated/sim'd). Satisfied: `compute_defender_grid` runs pre-emit for the contest; the emit's exact stash feeds `StepState.defense` for rendered turns.

---

## ✅ Decisions locked (feed the eventual Dynamic HCO System doc overhaul)
Stable *contracts* settled with the human during this refactor — they won't change based on how we implement. Captured here as we go; the Dynamic HCO System doc gets ONE comprehensive overhaul at the end (mid-flight rewrites would describe a half-migrated state → "wires crossed"). Each entry: the rule + when locked.

1. **Per-step event order (single-walk model), locked 2026-07-11.** At each step, run in order and STOP at the first terminal (possession-ending) event; **the first terminal in STEP order wins across the walk**. (Walk runs step 1..N; step 0 is starting positions, no decision.)
   1. **Offense decides its action** — a mini-sequence, in this order:
      - **1a. Scripted pass?** — a ball-reversal baked into the skeleton at this step.
      - **1b. SM-precedence** — "work the ball instead of shooting?" → *the **FIRST** subtle-movement read*; runs BEFORE the shoot decision and can pre-empt it (`sm_takes_precedence`, gated by clock/tempo + `offense_reads`).
      - **1c. Shoot decision** (`should_shoot`) — shoot, or dish to an open man → *the **HOT READ** lives here* (a dish; `_hco_blocked_dish_targets` first drops covered lanes).
      - **1d. Movement matrix** (`decide_step_action`) — if no shot/dish, pick a move; subtle can also be chosen here (the 2nd subtle read).
   2. **On-ball moment — EVERY step (incl. pass & shot steps).** The ball-handler's defender rolls strip/steal/foul. Fires → possession ends here, pinned to this step. **Moment-FIRST**: it gets its crack at the handler BEFORE the pass/shot he chose resolves.
   3. **If the action was a pass** (and ② didn't fire) → interception check in the lane (vs. the rendered defender grid). Pick/bat → STEAL/turnover ends the possession here.
   4. **If the action was a shot** (and ② didn't fire) → resolve the shot (make/miss/foul).
   5. **No terminal → advance to the next step.**
   - Notes: moments fire on ALL steps and are NOT mutually exclusive with the pass/shot — the moment simply gets first crack, and the offense's chosen pass/shot resolves only if the handler survived it. Supersedes the old model where the moment ran as a SEPARATE full pass before shot resolution (and could pre-empt an earlier-step shot). **②'s placement (moment-first) is the human's current choice and may be revisited** — if flipped to offense-first, ② moves below ③/④.

---

## Governing law — where game logic lives
**Resolve once → freeze into `StepState` → project to the emitter → draw.** All game logic lives in the resolution engine, *upstream of both* StepState and the emitter.

- **Engine** — 100% of game logic: every decision, RNG draw, and geometry/timing calc that can affect an outcome, stat, contest, position, or clock.
- **`StepState`** — the **frozen result**. A value, not a computation. **No logic.**
- **Emitter** — a **pure projection**: formats `StepState` → AnimationStep JSON. No decisions, no RNG, no re-derivation of anything game-relevant.
- **FE** — draws the JSON. No logic.

This makes backend↔FE alignment a **property of the data flow, not a discipline**: with exactly one computation (the engine) and one frozen value read everywhere downstream, the FE cannot render something the backend didn't resolve.

**Classification test** — for any value: *could computing it differently change an outcome, stat, contest, position, or clock?*
- **Yes → engine / `StepState`** (game logic).
- **No, it only changes how something looks → emitter** (cosmetic).
- Even for cosmetics, the **trigger** is `StepState`, only the **styling** is the emitter — e.g. "a steal occurred here, by this defender, at this contact point" = `StepState`; "play `click-steal.wav` + lunge animation" = emitter.

*Today this is violated* (emitter/animator re-derive coords, meet-points, timing, interrupts — some game-relevant). That smearing **is** the fragmentation; the refactor's job is to pull every game-relevant computation back into the engine.

---

## Problem (why we're doing this)
One dynamic HCO turn walks the same `steps` **~16 times** and re-derives the same per-step facts over and over:

| Fact | Re-derived |
|---|---|
| ball-handler-at-step | ~8× |
| pass/receive detection | ~6× |
| defender coords per step | ~4× |
| ball-owner-by-step | ~4× |
| step timing | ~3× (two parallel systems) |

No per-step record is the source of truth, so the moment walk, the shot walk, the interception coverage patch, the animator, and timing all recompute independently. Worst part: **contest and render recompute defender positions separately and can disagree** (subtle-freeze, flip seams) → a latent correctness bug.

---

## Core idea
One per-step object — **`StepState`** — computed **once** per step, **stamped on the emitted step**, read by everyone (contest + render). This just extends the pattern that already works today (`_attack_drive.defender_overrides` are stamped-and-read) to **all** per-step state.

`StepState` per step (complete, UESS-complete shape — every emitted game-relevant field has a home here):
```
players: {                       # offense + defense, keyed by player_id
  <pid>: { start_coord, target_dest, end_coord(actual, post-interrupt), archetype, action }
}
ball:    { from_owner, to_owner, from_coord, arrival_coord, motion_style, contact_point?, resolved_by? }
timing:  { step_t, game_clock_start/end, shot_clock_start/end }
advance_gate: { condition, target_player, target_coord }   # player_reaches_position | ball_reaches_player | fixed_duration
outcome: none | { kind: moment | interception | bat_oob | shot, ... }   # terminal step
cosmetics: { flourishes: {pid → trigger}, sfx_triggers: [...] }   # TRIGGERS only; styling is the emitter's
```

### Ball model — first-class trajectory (aligned)
A pass is a **mid-step event** (ball in flight), but today the data only records the step-*end* owner (the receiver); the passer is implicit and mid-flight events (interception, bat-OOB) are retrofitted (`uncatch` + `stealer_id`). So the ball becomes a per-step trajectory:

```
ball: { from_owner, to_owner, from_coord, arrival_coord, contact_point?, resolved_by? }
```
- **held** step: from == to.
- **pass** step: from = passer, to = receiver, arrival = meet-point.
- **interception / bat-OOB**: to = defender, arrival = contact_point (trajectory truncates mid-flight).

**Good news (traced 2026-07-11):** HCO already renders via the UESS step-emitter (`skeleton_step_emitter.build_skeleton_animation_steps`), whose emitted ball schema is **already this shape** — per-step `start.ball`/`end.ball` = `{owner_player_id}` + `ball_motion_style:"pass"` + `ball_arrival_coord` + `ball_reaches_player` trigger. So first-class trajectory is a **~1:1 map onto the existing emitter**, not a shim/FE-rewrite. `StepState.ball` *is* the emitter's ball schema, computed by the engine instead of re-derived.

### Field ownership — "the emitter's only input is StepState"
Enumerated the full emitted `AnimationStep` (2026-07-11). **Headline: the emitter currently *computes*, at emit time, essentially the entire movement / timing / clock / ball layer** — not copies it from a resolved skeleton. All of it is **game-relevant** and most is **double-derived** (the engine's contest/clock derive the same values independently → the divergence bug). Reframed test: **the emitter's only input should be `StepState`** — if a field needs game state *other than* StepState (positions, rates, RNG, attributes), that computation belongs in the engine.

| Emitted field(s) | Owner | Note |
|---|---|---|
| `start.coords` / `end.coords`(actual, interrupts) / `destination` | **StepState** | positions — contest + reads use them; **today derived at emit time** |
| `action`, `archetype` | **StepState** | archetype drives contest rate + timing |
| `ball` owner (start/end), `ball_motion_style`, `ball_arrival_coord` | **StepState** | interception geometry |
| `advance_trigger` (gate selection + target/meet-point) | **StepState** | gate = timing; **derived at emit today** |
| `end.time_elapsed` / step T, `start.clock`/`end.clock` | **StepState** | step timing + game/shot clock |
| `next` (next_step / turn_stop + payload) | **StepState** | outcome linkage |
| reach_in / idle_wander **whether+who**, SFX **whether+when** | **StepState** (`cosmetics` triggers) | the *decision* to cue |
| `tween_durations` (= `min(dist/rate, T)`) | **Emitter** | pure function of frozen StepState inputs → can't diverge |
| flourish **styling** (lunge, wander seed/amplitude), shot-arc keyframes | **Emitter** | render interpolation between resolved endpoints |
| SFX **file/tier** selection | **Emitter** *(open — see below)* | reads player attrs today; cosmetic, but breaks "only input is StepState" |

**Reassurance:** the emit-time computations are **deterministic** (no new RNG/decisions) — so the refactor **relocates** them (compute once in the engine, freeze in StepState) rather than rewriting the math. Same functions, moved call site, single frozen result. *But it means Stage 2 is bigger than "stamp the defender grid" — it's "move the whole movement/timing/clock derivation into the engine."*

**Cosmetic strictness — DECIDED (pragmatic):** SFX file/tier stays in the emitter (reads player attrs, as today — zero work). This is the **single named carve-out** to "emitter's only input is StepState": SFX tier/file selection is the *only* value the emitter may derive from game state, and only because it is provably outcome-inert. Everything else must come from StepState.

### One canonical coordinate frame (hard requirement)
Every coord in `StepState` (defender grid, ball trajectory incl. `contact_point`, all positions) is in **ONE frame — display orientation — flipped for away offense exactly once, at the source.** No consumer re-flips.

**Motivating bug (2026-07-11 — zone interception, away offense):** `pass_contact_point` is computed in **HOME** frame (zone contest: `assign_all_zone_defenders` always returns HOME + `_pt = get_away_player_coords` flips offense to home), but the render is in the **away-display** frame. That contact point is used verbatim as both the `steal_reach` override coord *and* `ball_arrival_coord`, so it lands **mirrored across half-court** → the pass animates to the opposite side, then the possession-boundary transition snaps it back ("teleport"). MAN / home offense are unaffected (contest already in display frame). The animator compounds it by using override coords **verbatim** — skipping the away-flip normal zone defenders get (`animator.py:1912` vs `:1949`).

**StepState fix (folded in — not spot-patched):** the defender grid + ball trajectory are stamped in the single display frame at build time; contest and render read the **same value**, so this mirror-bug class is impossible by construction. *Interim:* until this lands, zone + away-offense interceptions render mis-sided (a pre-existing frame bug the teleport fix now makes the ball follow rather than hide behind an instant snap).

---

## The engine — step by step
One engine, shared by motion + set play. Walk the scripted skeleton **once**. At each step `i`:

1. **Positions** → `StepState.positions`: offense from the skeleton; defenders from the *single* reconstruction.
2. **Ball owner / handler** (carried forward).
3. **Offense decides** — call the existing `motion_step_decision` library: shoot / dish / subtle / freelance / advance.
4. **Defense reacts** vs the *stamped* grid, in order — **first terminal wins**:
   1. Moment (steal / foul / turnover)
   2. Pass interception (if a pass this step)
   3. *(future: reactive defender actions — Dynamic-MM P2–P5)*
5. **Terminal?** (moment / interception / shot) → finalize + stop. Else stamp **timing** and advance.
6. **Stamp `StepState`** onto the emitted step.

Result: the emitted skeleton is **fully self-describing**. The animator becomes a **pure renderer** that reads `StepState` (no recompute). The contest already read `StepState`'s grid → **emitter-as-god by construction**, and contest/render can no longer disagree.

---

## What we delete
- the standalone **moment walk** (folds into step 4.1)
- **`_hco_contest_final_skeleton` + `_hco_contested` tagging** (one walk sees every pass — coverage patch no longer needed)
- the **running-estimate timing** (`_estimate_step_game_seconds`) — one authoritative contract
- the **legacy random-step resolver + shot-clock recalibration** bypass paths (the engine is the only path)
- **animator / turn_manager re-derivations** of ball-owner, defender coords, BH → read the stamped state instead

## What we keep as-is
- **`motion_step_decision`** library — the offense "brain" is already clean
- **sub-resolvers as called units**: `build_subtle_beat`, `_resolve_freelance`, `_execute_motion_decision`, attack drives
- **scripted skeleton** (base_loop / set-play variant) — the engine overlays decisions on it, doesn't generate steps

---

## Staged plan (each flag-guarded + parity-gated)
- **Stage 0** — define `StepState` + the single per-step reconstruction; stamp positions / BH / owner / timing. **No behavior change** — centralize what's already computed. (De-risks everything after it.) *Status: partially done — `StepState.defense` is stamped/consumed; BH / owner / timing not yet centralized.*
- **Stage 1 — ✅ moment fusion DONE (2026-07-12c, Path A hoist+cache)** — moment + offense in one resolver loop (moment-first, reached steps only); both `_resolve_hco_moment_walk` call sites removed; interception already in-loop. Baseline-10: shot 69→77% (+7.9pp), moments 31→23%. *Residual: coverage patch still present (retire with the walk-time-contest consolidation).*
- **Stage 2 — ✅ COMPLETE (2026-07-11, develop)** — **smaller than first thought.** HCO already renders off the emitter (`skeleton_step_emitter`), which builds coords internally via `skeleton_to_animations` → `get_defender_coords`. The gap: that render-side defender reconstruction was *independent* from the contest's (`_hco_step_def_xy` → `get_defender_coords`) — same formula, separate computation, confirmed divergence (man 22–64%, zone+away 100% mirror). Stage 2 = the engine **stamps the defender grid** so both the emitter and the contest read one value (emitter-as-god), instead of the animator re-deriving it. Not a renderer rewrite. **Shipped** via `compute_defender_grid` extract + Option A (share the emit's one draw) + Step A (man) / Step B (zone) contest routing; live GAP = 0% man+zone. *Residual (low pri): consolidate the walk-time contest; verify no redundant render draw. See RESUME HERE.*
- **Stage 3 — ✅ DONE (motion `5c5aad53c` + setplay `6e04d15df`)** — legacy + bypass paths removed. Motion: 219-line legacy body deleted, recalibration migrated to the dynamic resolver's `forced_shot_step_index` mode, motion flag retired. Set play: flag retired, gates always-dynamic (no separate legacy body — its "standard path" was just the shared `resolve_shot`, kept as a 1-line try/except safety net; variant selection kept). Both flags neutered to always-True (delete when gate tests pruned).

**Parity gate each stage:** moment / shot / foul / interception rates unchanged; `walk-saw == census` (coverage closed).

---

## Open decisions (need human ✅/❌)
1. Renderer collapse (Stage 2) is **in scope** — *agent: yes, it's the correctness fix. Confirmed smaller than feared: HCO already renders off the emitter; Stage 2 = stamp the defender grid so contest + render share one value, not a renderer rewrite.* **[✅ DONE 2026-07-11 — shipped, live GAP=0 man+zone]**
2. **Scripted skeleton stays** (engine overlays, doesn't generate) — *agent: yes.* [ ]
3. **Kill the legacy + recalibration bypasses** entirely — *agent: yes.* [ ]
4. **One timing system** (drop the running estimate) — *agent: yes.* [ ]
5. **Precedence:** when a moment and an interception are both possible, the **earlier step wins** (first-terminal-in-the-walk) — *agent: yes.* [ ]

---

## Bug family subsumed by Stage 1 — "ball snap-back on a non-shot outcome"
Any non-shot terminal (moment steal / **dead-ball turnover** / foul) that lands at/after a pass step makes the ball complete to the receiver, then teleport back to the stopper's ball-handler for the micro-animation + announce. Root: the outcome isn't **pinned to its actual step** (only interceptions/bat-OOB pin today), so `apply_stopper` truncates at a random blast-radius step. Stage 1 kills the whole family: one walk, every terminal pinned to its step, first-class ball trajectory (turnover mid-pass = truncated trajectory, ball never completes to the receiver). *Confirmed instances: interception teleport (fixed tactically), DB-turnover-after-pass teleport (2026-07-11, still live).*

## Convergence note
This isn't a side-refactor — it's the capstone of three tracked threads: **emitter-as-god** (one position source), **Dynamic-MM P2–P5** (offense-acts→defense-reacts step loop), and **UESS no-teleport** (one authoritative per-step position record).
