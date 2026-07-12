# StepState — Dynamic HCO Turn Engine (working doc)

**Status:** aligning (agent ↔ human). This is a shared scratchpad to agree on the architecture before building — **not** finished documentation. Keep it terse.

---

## ▶ RESUME HERE (checkpoint 2026-07-11b)

> **Numbering:** this block uses the formal "Staged plan" scheme below (Stage 0–3). What shipped is that plan's **Stage 2** (defender-grid sharing — "the correctness fix", Open Decision #1), rolled out as **Step A (man)** then **Step B (zone)**. Earlier notes called this "Stage 1 man/zone" — that was a local mislabel; it is **Stage 2**. The formal **Stage 1 (walk unification)** and **Stage 3 (bypass removal)** remain OPEN.

**✅ Stage 2 (defender-grid sharing) COMPLETE + verified on live turns (develop).** The interception contest now judges against the render's ACTUAL defender positions for BOTH man and zone, in one unified display frame. `🔬 STEPSTATE GAP` (canonical vs contest) measured **0% for man AND zone** on live play (was man 22–64%, zone up to 100%/96px mirror). The zone+away contact_point mirror is fixed.

**Shipped + pushed (develop) — commit chain `c3929ef4b`→`14befe175`:**
- `compute_defender_grid` **extracted** from `skeleton_to_animations` (split into `_build_all_animations` + thin wrapper); pure + sim-safe (bypasses the `_is_full_simulation` early-return). Made **pure** (deep-copies skeleton — the build mutates BH coords in place).
- **RNG discovery (load-bearing):** defender placement uses `random` (~2px shade; proven deterministic-under-fixed-seed). So contest and render as *two separate draws* can NEVER agree → recomputation is *incorrect*, not just wasteful. This is the concrete reason for "resolve once → freeze → draw."
- **Option A (share the one draw):** the HCO emit stashes its exact per-player `animations` on the game (`game._hco_render_animations`, transient, NOT in payload); `build_step_states` extracts `StepState.defense` from those via `Animator.defender_grid_from_animations`. Contest == render by construction. Sims fall back to `compute_defender_grid`'s own single draw (no render to match).
- **Stage 2 Step A (man):** `_hco_contest_final_skeleton` stamps `compute_defender_grid` on each step pre-contest (the emit's exact stash isn't available yet — contest runs pre-emit + truncates the skeleton the emit draws → circular; compute_defender_grid is the same code, ~2px RNG, immaterial vs the lane band). `_hco_step_def_xy` MAN branch reads the stamp.
- **Stage 2 Step B (zone):** hoisted the stamped-read above the man/zone split — when stamped, BOTH modes use the grid with **identity `_pt`** (one display frame). Kills the zone HOME-frame path (`assign_all_zone_defenders` + HOME-flipping `_pt`) that produced the mirrored contact_point. Legacy per-mode fallback preserved for the unstamped path.

**Next concrete steps (in the formal scheme):**
1. **Stage 2 residual — (low priority) consolidate the walk-time contest.** `_hco_contest_skeleton_pass` (called at ~5906/6152 during the walk) runs *before* the pre-coverage stamp, so those picks still use reconstruction (graceful fallback). Coverage (`_hco_contest_final_skeleton`) catches most passes with the real grid. Retire the walk-time hooks / move all contesting to the stamped stage if the mixing shows in numbers or a visual.
2. **Stage 2 residual — verify render adoption.** The render already computes the same grid via the extract, so contest+render share one value today; confirm no redundant/second draw remains. (This is the last bookkeeping bit of Stage 2, NOT a new stage.)
3. **Stage 1 (walk unification) — still OPEN.** Unify moment + interception + offense onto one `StepState` walk; delete the moment walk + coverage patch. This is what subsumes the **"ball snap-back on a non-shot outcome"** family (see below), incl. the **DB-turnover-after-pass teleport (2026-07-11, still live)** — NOT fixed by the Stage 2 defender-grid work.
4. **Stage 3 — still OPEN.** Remove the legacy + recalibration bypass paths.

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
- **Stage 1 — ⬜ OPEN** — unify the walks onto `StepState` (moment + interception + offense in one loop); delete moment walk + coverage patch. *Subsumes the "ball snap-back on a non-shot outcome" family (below), incl. the still-live DB-turnover-after-pass teleport.*
- **Stage 2 — ✅ COMPLETE (2026-07-11, develop)** — **smaller than first thought.** HCO already renders off the emitter (`skeleton_step_emitter`), which builds coords internally via `skeleton_to_animations` → `get_defender_coords`. The gap: that render-side defender reconstruction was *independent* from the contest's (`_hco_step_def_xy` → `get_defender_coords`) — same formula, separate computation, confirmed divergence (man 22–64%, zone+away 100% mirror). Stage 2 = the engine **stamps the defender grid** so both the emitter and the contest read one value (emitter-as-god), instead of the animator re-deriving it. Not a renderer rewrite. **Shipped** via `compute_defender_grid` extract + Option A (share the emit's one draw) + Step A (man) / Step B (zone) contest routing; live GAP = 0% man+zone. *Residual (low pri): consolidate the walk-time contest; verify no redundant render draw. See RESUME HERE.*
- **Stage 3 — ⬜ OPEN** — remove the legacy + recalibration bypass paths.

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
