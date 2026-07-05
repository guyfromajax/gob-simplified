# Group C — Trap / Press Positioning: logic-vs-render divergence (DECISION NEEDED)

**Status: OPEN — needs a gameplay-feel decision.** Consolidates the deferred "Group C" items from [HCT_UESS_Audit.md](HCT_UESS_Audit.md) (HCT-Task 7) and [FCP_UESS_Audit.md](FCP_UESS_Audit.md) (FCP-Task 3 + #6), which are the **same root** and the likely cause of the reported **over-and-back** bug. Not a mechanical fix — it changes how the trap/press *feels*.

## The question (one line)
When the game logic decides a steal / foul / contest / over-and-back from a defender or ball-handler position the **frontend never renders** (the trap collapses in logic but not on screen), do we **weaken the logic to match the render**, or **speed up the render to match the logic**?

## The divergence (mechanism)
The dynamic HCT/FCP engine **snaps** players to their full target in one beat; the emitter **interrupts** them at a slower rate over that beat's short duration, so on screen they fall short. The engine then reads the **full/snapped** positions for game decisions. Two shapes:

| Shape | Engine | Emitter renders | Consumer that reads the wrong coord |
|---|---|---|---|
| **Defender collapse** (trap converge / press converge / terminal stopper) | snaps all 5 to full trap/press formation; beat sized by PG-only | interpolates each at **standard** rate → SG/SF/PF/C fall short | steal / foul / contest eligibility (`_position_defense` → `_resolve_attack`) |
| **PF/C recovery** | moves at **sprint** | renders at **standard** → lag | trap/press coverage reads |
| **BH advance** (`_advance`) | jumps BH full distance at **AG-drive rate** | interpolates at **standard** → BH renders behind | `frontcourt_established`, 10-sec violation, **`is_over_and_back_pass`** ← the over-and-back bug |

**Why it's worse for FCP:** `skip_walk_up` removes the walk-up that pre-positions defenders, so the *sole* converge beat must snap defenders across the whole court in a window the standard render can't cover → the press visibly never closes, yet steals/fouls fire from the snapped formation.

**Symptom already reported:** ball animated committing an over-and-back, but the violation doesn't register — the engine's BH is *ahead* of the rendered BH, so `is_over_and_back_pass` sees a frontcourt BH while the FE shows him crossing back.

## Options

| | Option A — **logic reads render** | Option B — **render reaches logic** (recommended) | Option C — hybrid |
|---|---|---|---|
| **Change** | Eligibility (steal/foul/contest/over-and-back) reads the emitted *interrupted* `end.coords` instead of the engine snap | Size each collapse/advance beat's **duration** by the *slowest mover* (not PG-only), and/or render at the engine's rate (sprint / AG-drive), so players actually reach the logical target on screen | Per-consumer: read-render for violations (over-and-back), render-reaches for the trap collapse |
| **UESS** | ✅ logic == render | ✅ render == logic | ✅ both |
| **Gameplay feel** | ⚠️ **Weaker** trap/press — steals/fouls only fire when a defender is *visibly* on the ball; fewer turnovers | ✅ **Preserves** trap/press strength; the collapse just *looks* as aggressive as it plays | ✅ preserves strength; correct violations |
| **Visual** | unchanged | collapse/advance animations are **faster / longer** (defenders sprint to close, BH drives at full speed) | mixed |
| **Effort / risk** | lower (read a different coord) | medium (beat-duration sizing + rate per mover); more visual change | higher (per-consumer) |

## Recommendation
**Option B** — make the render reach the logical positions (size beats by the slowest mover; render the BH advance at the drive rate). It's the only option that keeps the trap/press as strong as designed *and* satisfies UESS (logic == render) *and* fixes over-and-back — the cost is faster/longer collapse + drive animations, which is a visual-pacing tradeoff, not a correctness one. Fall back to **Option A** only if B's faster animations look bad.

Reason to *not* default to A: it silently nerfs the trap/press (a balance change disguised as a bug fix) — that should be a deliberate design choice, not a side effect.

## Scope if approved (Option B)
- **HCT-Task 7:** size the trap `hct_converge` + terminal stopper beats by the slowest defender's travel; render PF/C at sprint.
- **FCP-Task 3:** same for the press converge + stopper (higher priority — `skip_walk_up` amplifies it).
- **Over-and-back (`_advance`):** render the BH at the AG-drive rate (or read the rendered BH for the violation) — coordinate with the separate over-and-back thread.
- **Verify in prototype** (HCT/FCP can't be sim-verified in the mock).

## Open decision
- [ ] **A** (weaken logic to render), **B** (render reaches logic — recommended), or **C** (hybrid)?
- [ ] Is a faster/longer trap-collapse + BH-drive animation acceptable (Option B's cost)?
