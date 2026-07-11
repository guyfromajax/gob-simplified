# StepState — Dynamic HCO Turn Engine (working doc)

**Status:** aligning (agent ↔ human). This is a shared scratchpad to agree on the architecture before building — **not** finished documentation. Keep it terse.

---

## ▶ RESUME HERE (checkpoint 2026-07-11)

**Shipped + pushed (develop):** interception teleport fix (`skeleton_step_emitter`); Stage 0 diagnostics; Stage 1a (canonical grid concept); Stage 1b (`step_state.py` — pure man primitive + `🔬 STEPSTATE FIDELITY`/`GAP` diagnostics). All **inert** — nothing reads `StepState.defense` yet, zero behavior change.

**Proven (the whole point):** contest (`_hco_step_def_xy`) vs render (`skeleton_to_animations`) disagree — **man ~30–57%** (Δ up to 20), **zone+away 100%** (half-court mirror, Δ up to 98). So interceptions are judged against defender positions the player doesn't see. Rock-solid, measured many times.

**Where we stopped:** the pure man primitive (`_compute_man_defender_grid`) is a **hand-replication** of the render's defender math and stays ~40% off (Y-dominant, pass steps). `off-coord-also-diverged` is LOW → it's a defender-*logic* mismatch, not offense coords. Root: `skeleton_to_animations`' movement/`hasBallAtStep` arrays **skip steps that omit a player** → misalign when read by skeleton-step index; plus BH tie-break quirks. Hand-copying that ~350-line intertwined function exactly is the trap.

**Decision:** STOP hand-replicating. **Extract** the render's actual offense-position + defender-placement computation out of `skeleton_to_animations` into a **pure function callable for sims** (no full-animation cost, no `_is_full_simulation` early-return dependency). Then fidelity = 0 by construction (same code, not a lookalike).

**Next concrete steps:**
1. **Extract** `skeleton_to_animations`' core (offense build + `_position_standard/zone_defenders`) into a shared, sim-safe `compute_defender_grid(skeleton, off_lineup, def_lineup, …)`. Render calls it (behavior-preserving); it returns just the grid for the contest.
2. Point `StepState.defense` at it; confirm `🔬 STEPSTATE FIDELITY ≈ 0` and `🔬 STEPSTATE GAP` = the man/zone divergence.
3. **Stage 1:** route the interception contest to read `StepState.defense` (run post-resolution against the canonical grid — extend `_hco_contest_final_skeleton`). Retire the walk-time `_hco_step_def_xy` hooks.
4. **Stage 2:** render adopts the same function (already does, via the extract). Then contest == render == one computation, animated or sim'd.

**Hard constraint:** the canonical grid must be a **pure resolution-time computation** — an interception is an OUTCOME and must be identical for animated and sim'd games (sims return `[]` from `skeleton_to_animations`). This is *why* the extract (not "read the render output") is required.

**Also open (folded into this refactor):** DB-turnover-after-pass teleport (same "ball snap-back on non-shot outcome" family — see below); zone extract (man first); the zone/away frame mirror (dies when the contest reads the canonical grid).

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
- **Stage 0** — define `StepState` + the single per-step reconstruction; stamp positions / BH / owner / timing. **No behavior change** — centralize what's already computed. (De-risks everything after it.)
- **Stage 1** — unify the walks onto `StepState` (moment + interception + offense in one loop); delete moment walk + coverage patch.
- **Stage 2** — **smaller than first thought.** HCO already renders off the emitter (`skeleton_step_emitter`), which builds coords internally via `skeleton_to_animations` → `get_defender_coords`. The gap: that render-side defender reconstruction is *independent* from the contest's (`_hco_step_def_xy` → `get_defender_coords`) — **same formula, separate computation, confirmed divergence points** (subtle-freeze, orientation flip seams, BH detection). Stage 2 = make the engine **stamp the defender grid** so both the emitter and the contest read one value (emitter-as-god), instead of the animator re-deriving it. Not a renderer rewrite.
- **Stage 3** — remove the legacy + recalibration bypass paths.

**Parity gate each stage:** moment / shot / foul / interception rates unchanged; `walk-saw == census` (coverage closed).

---

## Open decisions (need human ✅/❌)
1. Renderer collapse (Stage 2) is **in scope** — *agent: yes, it's the correctness fix. Confirmed smaller than feared: HCO already renders off the emitter; Stage 2 = stamp the defender grid so contest + render share one value, not a renderer rewrite.* [ ]
2. **Scripted skeleton stays** (engine overlays, doesn't generate) — *agent: yes.* [ ]
3. **Kill the legacy + recalibration bypasses** entirely — *agent: yes.* [ ]
4. **One timing system** (drop the running estimate) — *agent: yes.* [ ]
5. **Precedence:** when a moment and an interception are both possible, the **earlier step wins** (first-terminal-in-the-walk) — *agent: yes.* [ ]

---

## Bug family subsumed by Stage 1 — "ball snap-back on a non-shot outcome"
Any non-shot terminal (moment steal / **dead-ball turnover** / foul) that lands at/after a pass step makes the ball complete to the receiver, then teleport back to the stopper's ball-handler for the micro-animation + announce. Root: the outcome isn't **pinned to its actual step** (only interceptions/bat-OOB pin today), so `apply_stopper` truncates at a random blast-radius step. Stage 1 kills the whole family: one walk, every terminal pinned to its step, first-class ball trajectory (turnover mid-pass = truncated trajectory, ball never completes to the receiver). *Confirmed instances: interception teleport (fixed tactically), DB-turnover-after-pass teleport (2026-07-11, still live).*

## Convergence note
This isn't a side-refactor — it's the capstone of three tracked threads: **emitter-as-god** (one position source), **Dynamic-MM P2–P5** (offense-acts→defense-reacts step loop), and **UESS no-teleport** (one authoritative per-step position record).
