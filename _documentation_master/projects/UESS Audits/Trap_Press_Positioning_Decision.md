# Group C — Trap / Press Positioning: single-coord-source fix (DECISION SETTLED, needs impl + verify)

**Status: framing settled (2026-07-05) — it's a correctness fix, not a gameplay-feel choice.** Consolidates the deferred "Group C" items from [HCT_UESS_Audit.md](HCT_UESS_Audit.md) (HCT-Task 7) and [FCP_UESS_Audit.md](FCP_UESS_Audit.md) (FCP-Task 3 + #6), the **same root** and the cause of the reported **over-and-back** bug.

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
- **Over-and-back (`_advance`, #6):** render the BH advance at the AG-drive rate so his rendered position matches the engine's `frontcourt_established` / `is_over_and_back_pass` read → the violation is called whenever it's shown. Coordinate with the separate over-and-back thread.
- **Verify in prototype** — HCT/FCP can't be sim-verified in the mock; watch that (a) no defender/BH teleports (beats long enough) and (b) over-and-back fires exactly when the ball is shown crossing back.

## Remaining (not a fork — just confirmations)
- [ ] Confirm the *real-speed* trap/press close (slightly slower than the current instant-snap) is acceptable — it's the correct physics, but it's a visible timing change.
- [ ] Sequencing: bundle HCT-Task 7 + FCP-Task 3 + the over-and-back fix into one coordinated pass (shared `_advance` / `_position_defense` / beat-sizing), verified in prototype.
