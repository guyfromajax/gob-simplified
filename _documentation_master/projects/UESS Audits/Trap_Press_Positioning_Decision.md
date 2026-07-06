# Group C — Trap / Press Positioning: single-coord-source fix (DECISION SETTLED, needs impl + verify)

**Status: framing settled (2026-07-05) — it's a correctness fix, not a gameplay-feel choice.** Consolidates the deferred "Group C" items from [HCT_UESS_Audit.md](HCT_UESS_Audit.md) (HCT-Task 7) and [FCP_UESS_Audit.md](FCP_UESS_Audit.md) (FCP-Task 3 + #6), the **same root** and the cause of the reported **over-and-back** bug.

> **Implementation update (2026-07-06, code-verified):** the **BH-advance / over-and-back** half is **already implemented**. The emitter renders the BH `hct_advance` at the AG-drive rate (`dynamic_hct_step_emitter.py:279-287`, `ag_to_grid_per_game_sec(AG)`) — the *same* rate + `_interrupted_coord` as the engine's `_advance` (`dynamic_hct.py:2218`) → engine `bh_xy` == rendered BH coord, so `frontcourt_established` / 10-sec / `is_over_and_back_pass` read what's shown. The **defender-collapse** half (§ table row 1) is **still open**. Possible residual: the emitter starts the advance from the rendered chain (`prev_end_coords[bh]`) vs logic's `bh_xy`, so earlier-step clamp drift could still diverge — chase only if over-and-back is still reported live.

> **Implementation update #2 (2026-07-06) — DEFENDER MOVE-BEAT archetype carry SHIPPED (branch `hct-fcp-archetype-carry`):** the **PF/C recovery** row (§ table row 2) is fixed. The engine authored PF/C (+ recovered guards) at `sprint` on advance/hold beats but the emitter re-derived `standard` and rendered them short. Now the engine carries the per-defender archetype on the segment (`move_archetype`, `dynamic_hct.py` `_move_defense`→`_segment`) and the emitter READS it (`dynamic_hct_step_emitter.py` `_build_loop_step`), so advance/hold defenders render at the rate the engine decided from. **This is the single-motion-spec convention for the rate dimension** (archetype authored once, carried, never re-derived). RNG/outcome byte-identical; +22 HCT move-steps now render a defender at sprint. **NOTE — this does NOT touch the CONVERGE/STOPPER snap** (§ table row 1): the first-contest steal/foul is credited from the `_position_defense` teleport (no archetype used), so it needs the separate beat-sizing fix (size the converge beat by the slowest mover → visible slowdown) — **still deferred, design call pending**. The archetype-carry is its foundation.

## Principle (user, 2026-07-05)
Backend logic is authoritative; the FE renders backend decisions and **NEVER overrides** them (UESS §1). If the backend logic determines an over-and-back (or a steal, foul, contest), it must be **both called and rendered** — consistently, every time. So "make the logic read the render" is **rejected** — it inverts the authority.

## The real root (two backend coord representations disagree)
This is NOT the FE overriding the backend. The **engine** (decision logic) and the **emitter** (which produces the render) are *both backend*, but compute positions differently:
- Engine **snaps** the BH/defenders to their full target (BH at AG-drive rate).
- Emitter **interpolates** them at standard rate → renders them short/behind.

So the game logic decides from one backend coord and the FE shows another. Fixing it = **single-coord-source**: one position per player per step, used by both the decision and the render.

## The §8 nuance (why "just render the snap" is wrong too)
The engine's snapped position often **isn't physically reachable in the beat's time** (defenders can't cross the court in a PG-sized window). Rendering the snap verbatim = a **teleport** (violates §8). So the single coord must also be **physically valid** — the beats must be **sized by real travel time** so the intended position *is* reachable. Then engine == emitter == render, and every decision is shown exactly as decided.

## Prior mis-framing (superseded)
Earlier this doc framed it as "weaken logic (A) vs speed up render (B) vs hybrid (C)" — a gameplay tradeoff. That was wrong: A inverts §1 authority, and B/C conflate "render faster" with the real fix. The correct fix is one thing: **unify the coord + make it physically valid.**

## The divergence (mechanism)
The dynamic HCT/FCP engine **snaps** players to their full target in one beat; the emitter **interrupts** them at a slower rate over that beat's short duration, so on screen they fall short. The engine then reads the **full/snapped** positions for game decisions. Two shapes:

| Shape | Engine | Emitter renders | Consumer that reads the wrong coord |
|---|---|---|---|
| **Defender collapse** (trap converge / press converge / terminal stopper) | snaps all 5 to full trap/press formation; beat sized by PG-only | interpolates each at **standard** rate → SG/SF/PF/C fall short | steal / foul / contest eligibility (`_position_defense` → `_resolve_attack`) |
| **PF/C recovery** | moves at **sprint** | renders at **standard** → lag | trap/press coverage reads |
| **BH advance** (`_advance`) | jumps BH full distance at **AG-drive rate** | interpolates at **standard** → BH renders behind | `frontcourt_established`, 10-sec violation, **`is_over_and_back_pass`** ← the over-and-back bug |

**Why it's worse for FCP:** `skip_walk_up` removes the walk-up that pre-positions defenders, so the *sole* converge beat must snap defenders across the whole court in a window the standard render can't cover → the press visibly never closes, yet steals/fouls fire from the snapped formation.

**Symptom already reported:** ball animated committing an over-and-back, but the violation doesn't register — the engine's BH is *ahead* of the rendered BH, so `is_over_and_back_pass` sees a frontcourt BH while the FE shows him crossing back.

## The fix (settled direction): unify the coord, make it physically valid
One position per player per step, decided-from and rendered, physically reachable:
- **Size every collapse / advance beat's duration by the *slowest mover* it must move** (currently the trap/press converge is sized PG-only), so the intended target *is* reachable within the beat.
- **Use the same movement rate in the engine and the emitter** per player (PF/C + recovery = sprint in both; BH advance = AG-drive rate in both — the emitter must stop rendering these at standard rate).
- Result: engine end coord == emitter end coord == rendered coord. Steal / foul / contest / over-and-back are decided and rendered from the identical coord → called ⇔ shown, always.

This is **not** a balance change and **not** "render faster for looks" — it's removing a second, physically-impossible coord representation. The trap/press now closes at its *real* speed; the instant-snap was the fiction.

## Scope
- **HCT-Task 7:** size the trap `hct_converge` + terminal-stopper beats by the slowest converging defender's travel; render PF/C (+ recovery) at sprint in the emitter.
- **FCP-Task 3:** same for the press converge + stopper — **higher priority** (`skip_walk_up` makes the single converge beat cover the whole court).
- **Over-and-back (`_advance`, #6): ✅ IMPLEMENTED (2026-07-06, code-verified).** Emitter renders the BH advance at the AG-drive rate (`dynamic_hct_step_emitter.py:279-287`) matching the engine `_advance` (`dynamic_hct.py:2218`) → `frontcourt_established` / `is_over_and_back_pass` read the rendered coord. Not yet prototype-checked; possible seam-drift residual (see top note).
- **Verify in prototype** — HCT/FCP can't be sim-verified in the mock; watch that (a) no defender/BH teleports (beats long enough) and (b) over-and-back fires exactly when the ball is shown crossing back.

## Remaining (not a fork — just confirmations)
- [x] **Over-and-back (`_advance` BH-advance rate) — implemented in code (2026-07-06);** see Scope + top note. Defender-collapse half below still open.
- [ ] Confirm the *real-speed* trap/press close (slightly slower than the current instant-snap) is acceptable — it's the correct physics, but it's a visible timing change.
- [ ] Sequencing: bundle HCT-Task 7 + FCP-Task 3 (**defender collapse/converge** only — over-and-back done) into one coordinated pass (shared `_position_defense` / beat-sizing), verified in prototype.
