# Emitter As God — single position authority (handoff)

**Purpose:** knowledge-transfer for a new thread. This is the overarching fix the whole UESS turn-audit sweep pointed at. Read §0 to get up to speed, then this doc top-to-bottom, then the audit docs it references.

---

## 0. Read this first (onboarding — do NOT skip)

Read in tiers. **Tier 0 fully** (the contract + how the emitter/steps work — this whole effort is enforcing that contract). **Tier 1-2** for the subsystem you're touching. **Tier 3** as needed for context.

**Tier 0 — the spec + the emitter/step machinery (read fully):**
- [`05_UESS_System/UESS_System.md`](../05_UESS_System/UESS_System.md) — THE contract. §1 single-coord-source, **§9.5 destinations-are-intent + "logic reads the interrupted end"** (the rule this whole doc enforces), §12.1/§12.2 known gaps.
- [`05_UESS_System/Step_By_Step_System.md`](../05_UESS_System/Step_By_Step_System.md) — the emitted step schema (`start`/`end`, `coords`, `gate`, `action`, `ball`) — i.e. what "read `end.coords`" means concretely.
- [`05_UESS_System/Core_Animation_System.md`](../05_UESS_System/Core_Animation_System.md) — how the FE renders steps (the "God" side).
- [`05_UESS_System/Animation_Routing_Reference.md`](../05_UESS_System/Animation_Routing_Reference.md) — how each turn type routes to its emitter/renderer (which turns are migrated).

**Tier 1 — the position/coord machinery (where render coords come from):**
- [`05_UESS_System/Transition_Systems.md`](../05_UESS_System/Transition_Systems.md) — `build_walk_up_step` / gate / interrupted-coord / inbound seams (the §9.5 mechanic in code).
- [`05_UESS_System/Position_Checkpoints_and_Snapshot_Schema.md`](../05_UESS_System/Position_Checkpoints_and_Snapshot_Schema.md) — position snapshots / `final_coords` / seam handoffs.
- [`05_UESS_System/Defense_Coords_System.md`](../05_UESS_System/Defense_Coords_System.md) — defender placement (directly relevant to the contest bug).
- [`06_Gameplay_Systems/Shot_Micro_Movements_System.md`](../06_Gameplay_Systems/Shot_Micro_Movements_System.md) — the shot-step micro movements (part of the render coord).
- [`10_Players_Systems/Player_Attribute_System.md`](../10_Players_Systems/Player_Attribute_System.md) — **AG → speed archetypes (sprint/standard rate)** — the crux of the FB rate divergence + the reachability model.

**Tier 2 — the game logic being fixed (the re-derivers):**
- [`06_Gameplay_Systems/Shot_System.md`](../06_Gameplay_Systems/Shot_System.md) — shot resolution + **contest** (the boolean this whole thing feeds).
- [`06_Gameplay_Systems/Fast_Break_System.md`](../06_Gameplay_Systems/Fast_Break_System.md) — FB families + drive resolution (the **48% no-defender** bug lives here).
- [`06_Gameplay_Systems/Rebound_System.md`](../06_Gameplay_Systems/Rebound_System.md) — rebounder selection (same divergent frame).
- [`06_Gameplay_Systems/Motion_Offense_Shot_System.md`](../06_Gameplay_Systems/Motion_Offense_Shot_System.md) — motion/HCO shot classification (already-fixed reference case).
- [`06_Gameplay_Systems/HCT_System.md`](../06_Gameplay_Systems/HCT_System.md) + [`FCP_System.md`](../06_Gameplay_Systems/FCP_System.md) — trap/press (positioning divergence + over-and-back).
- [`06_Gameplay_Systems/Block_System.md`](../06_Gameplay_Systems/Block_System.md), [`Steal_System.md`](../06_Gameplay_Systems/Steal_System.md), [`Stopper_System.md`](../06_Gameplay_Systems/Stopper_System.md) — all gated by the contest/positions.
- [`06_Gameplay_Systems/Defense_Matchups_System.md`](../06_Gameplay_Systems/Defense_Matchups_System.md) — matchup assignment (zone contest path).
- [`06_Gameplay_Systems/HCO_Turn_Resolution_System.md`](../06_Gameplay_Systems/HCO_Turn_Resolution_System.md), [`Turn_by_Turn_System.md`](../06_Gameplay_Systems/Turn_by_Turn_System.md), [`Shot_Clock_System.md`](../06_Gameplay_Systems/Shot_Clock_System.md) — turn lifecycle + clock (§5).

**Tier 3 — context as needed:**
- Turn specifics: [`BIP_System.md`](../06_Gameplay_Systems/BIP_System.md), [`SIP_System.md`](../06_Gameplay_Systems/SIP_System.md), [`Free_Throw_System.md`](../06_Gameplay_Systems/Free_Throw_System.md), [`Timeout_System.md`](../06_Gameplay_Systems/Timeout_System.md), [`Dynamic_HCO_System.md`](../06_Gameplay_Systems/Dynamic_HCO_System.md), [`EOQ_System.md`](../06_Gameplay_Systems/EOQ_System.md).
- Tuning (this fix shifts FG%): [`04_Franchise_Mode_Systems/Shot_Threshold_Scale_Tuning.md`](../04_Franchise_Mode_Systems/Shot_Threshold_Scale_Tuning.md), [`06_Gameplay_Systems/Aggression_System.md`](../06_Gameplay_Systems/Aggression_System.md), [`Player_Momentum_System.md`](../06_Gameplay_Systems/Player_Momentum_System.md).
- Downstream of outcomes: [`11_Design_Systems/SFX_System.md`](../11_Design_Systems/SFX_System.md), [`06_Gameplay_Systems/Announcement_System.md`](../06_Gameplay_Systems/Announcement_System.md).

**Then read the UESS Audit docs** (§9 below lists them) — they have the per-turn detail behind the inventory in §3.

> ⚠️ **Docs may lag code.** These specs are the design intent; verify file:line claims against current code before acting (the working tree has a large uncommitted shot-tuning stack). When a doc and the code disagree, the code is truth — and note the drift.

---

## 1. The principle (one line)

**The step emitter is the single source of truth for where every player and the ball is at each step. Game logic MUST read the emitted `end.coords[player_id]` (and ball coord); it must NEVER re-derive a position from a destination, an archetype/rate, `player.coords`, or a named spot.**

Corollary (already added to `UESS_System.md` §9.5): a destination is *intent*; when the advance trigger fires (gate reaches destination / step T elapses), each player ends at the interrupted coord the emitter renders. Logic reads that interrupted end — the reachable, on-screen position — not the destination.

## 2. The architecture problem (why it's fragile — the user's instinct is correct)

The game currently has **two independent coordinate/motion producers**:
1. the **decision engine** (game logic — contest, steal, foul, rebound, classification, violations), and
2. the **render emitter** (`*_step_emitter.py` — produces `animation_steps[].end.coords`).

Each computes player positions AND speeds/timing **separately**, with its own archetype/rate/destination choices, and **nothing forces them to agree** — so they drift. There is no single authority that answers "where is every player at step end." Every subsystem re-derives it. That fragmentation is the root defect; the per-turn sweep was an inventory of where it surfaces.

**The fix is universal:** make the emitter the authority. Logic reads `end.coords`. Delete every parallel re-derivation.

## 3. The recurring symptom (same root, every turn)

Logic decides from a coord the frontend never rendered. Confirmed instances (severity + status):

| Where | Divergence | Impact | Status | Audit doc |
|---|---|---|---|---|
| HCO/FT/FCP **shot classification** | logic used named skeleton spot; render used interrupted shoot coord | ~25% of arc shots mis-scored 2/3 | ✅ FIXED (pre-pass) | `Shot_Classification_UESS_Fix_Scope.md` |
| HCO/FT/FCP **shot contest (defenders)** | contest used animator row-end; render used interrupted coord | over-contest ~98.7%→96.7% | ✅ FIXED (pre-pass, all players) | `Coord_Consumer_UESS_Audit.md` #1 |
| Covert Release **block** | resolve_shot re-derived contest from stale pre-race coords | block never fired on contested CR | ✅ FIXED (flag) | `Coord_Consumer_UESS_Audit.md` #2 |
| **Fast Break contest + drive decisions** | logic clamped defenders at BH **sprint**-T toward `basketSpot` / seeded cutoff/receiver/contest from stale `player.coords`; render tweens toward rendered positions | **48% of FB shots registered "no defender"** (should be ~10%); also fed rebounder + gated block/defense → inflated FB FG% | ✅ **FIXED (2026-07-07)** — Phase-1 contest (pre-pass) + full **emit-then-resolve** sweep: RR/CR/AS/Triangle drive-starts, kick-out receiver, pass-ahead, triangle-three contest all read rendered coords; guard driven **20→0** | `Fast_Break_UESS_Audit.md` #2/#7/#8, `05_UESS_System/Coord_Source_Registry.md` |
| **HCT trap** positioning | engine snaps all 5 defenders to full trap; render interrupts them | steal/foul fire from a defender not visibly on the ball | ⏳ DEFERRED (design settled) | `Trap_Press_Positioning_Decision.md` |
| **FCP press** positioning | same, amplified (`skip_walk_up` → sole converge beat can't render the full close) | worse than HCT | ⏳ DEFERRED | `Trap_Press_Positioning_Decision.md` |
| **Over-and-back / BH advance** | `_advance` jumps BH at **AG-drive** rate in logic; render tweens at **standard** → engine BH ahead of screen | over-and-back / frontcourt / 10-sec violations fire from an unrendered BH position (reported bug) | ✅ FIXED IN CODE (2026-07-06) — emitter renders BH advance at AG-drive rate (`dynamic_hct_step_emitter.py:279-287`), matches engine `_advance`; not prototype-checked (possible seam-drift residual) | `FCP_UESS_Audit.md` #6, `Trap_Press_Positioning_Decision.md`, `dynamic_hct.py:2218` |

(A distinct, non-coord §1 issue: Timeout's *eligibility rule* lives in the FE — `Timeout_UESS_Audit.md` #1. Same "logic must be backend" spirit, different mechanism. Decision pending.)

**Status update (2026-07-07) — what the FB sweep + audit taught us (refines this section's "same root, every turn" framing):**
- **Fast Break is DONE.** Every FB drive decision (RR/CR/AS/Triangle cutoff/meet, kick-out receiver, pass-ahead, triangle-three contest) now reads the emitter's coords via *emit-then-resolve* (resolver builds the preamble once, seeds the decision from the rendered `end.coords`, stashes it for the emitter to reuse). Enforced by the coord-source **guard** (`05_UESS_System/Coord_Source_Registry.md`), driven 20→0 and now **widened to all engine decision modules** as a CI ratchet.
- **The stale-`player.coords` drift is FB-SPECIFIC, not "every turn."** FB uniquely skips `apply_coords` (positions frozen at start-of-break); other turns (HCO/HCT/FCP/DREB/OREB) run `apply_coords` and don't read `player.coords` for decisions (guard scan confirmed ~0). So the "recurring symptom" was concentrated, not universal — and it's now closed + guarded.
- **HCO events are attribute-driven, not coord decisions.** The HCO steal/foul/turnover (dynamic per-step moment walk, now the default — legacy team-attribute tables sunset) rolls on attributes and credits the man-matchup / zone defender; it reads the skeleton spot for *who*, but the outcome isn't proximity-gated. So "a non-guarding defender steals" is a **design** property (steals aren't distance-gated), not an emitter-coord bug. Separate design decision if we want proximity-gating.
- **The one remaining position-authority violation is HCT/FCP trap/press** (rows above, still ⏳) — a *teleport* (engine snaps the full trap), a different mechanism the coord-source guard can't catch. That's the next item (§10 #3).

## 4. The fix pattern

**For logic that runs AFTER the emit** (or can): read `animation_steps[step].end.coords[p]` directly. Trivial.

**For logic that runs BEFORE the emit** (make/miss, contest, classification, rebound — the emitter consumes the shot outcome, so it runs later): you can't read the render yet. Two approaches, both proven/scoped:

- **(A) Emitter pre-pass (shipped for HCO/FT/FCP).** Run the real emitter once on a throwaway turn_result to get the shoot-step `end.coords`, apply them to `player.coords` before `resolve_shot`, then decide. See `_uess_sync_emitted_shot_coords` (`phase_resolution.py`). **RNG-neutral** (getstate/setstate around the emitter) so it never perturbs outcomes. **~98% accurate**, not exact — the throwaway pre-pass can't perfectly reproduce the late render's context (backfill/entry-orchestrator/seam), so it degrades toward the animator row-end. Residual documented in `Shot_Classification_UESS_Fix_Scope.md`.
- **(B) Pin the coord into the emitter (exact, deferred).** Compute the coord once, stamp it, and have the late emitter USE the pinned value (frame + §8.1 continuity care). 0% residual by construction, but touches the shared render path. Deferred as higher-risk.

**Rate/timing must match too, not just frame.** The FB bug is a *timing* divergence: logic budgets defender travel at the BH's **sprint** rate, render at **standard** finisher pace (~29% slower) → defenders placed ~29% farther back in logic than on screen. Aligning the rate is a band-aid (two calcs still drift); the real fix is logic reads the render's `end.coords`.

## 5. Worked example — the FB "48% no defender" bug (concrete)

Two compounding causes (from a live report; both confirmed in code):
- **H2 (the real bug):** `t_drive_game_seconds = _traverse_seconds(bh_start, shot_spot, bh, "sprint")` (`fb_drive_resolution.py:277`), and `_reachable_defender_ends(..., time_budget=t_drive)` (`:307`) clamps defenders to that **sprint** time. The render tweens the drive at the **standard** finisher pace → defenders render ~29% closer than the contest credits (`Fast_Break_UESS_Audit.md` #8). Defenders who visibly contest are placed too far back in logic → "no defender."
- **H1 (compounding limiter, partly by-design):** the FB contest gate is Euclid ≤ `CONTEST_EUCLIDEAN_RADIUS`(11) **AND** x-trail ≤ `FB_CONTEST_MAX_X_TRAIL`(3) (`fb_geo_helpers.py`). On a fast break the D is usually trailing, so the x-trail cut drops beaten defenders; combined with H2 a clamped-short defender is *both* too far and too trailing. Whether 3 is right is a tuning knob, not the root cause.
- **Blast radius:** the same defender frame feeds FB **rebounder** selection (#7) and the contest boolean **gates the block path + defense scoring**, so this also **inflates FB FG%** (relevant to the active FG% tuning).
- **Fix:** contest reads the *rendered* defender `end.coords` (pre-pass or read-after-emit), not the sprint-clamp toward `basketSpot`. Then H1 becomes a tuning knob.

## 6. Open implementation decisions (for the new thread — likely need the user)

1. **How to break the circular dep for pre-emit decisions:** approach (A) pre-pass (~98%, low-risk, shipped) vs (B) pin (exact, touches render path) vs (C) restructure the resolve→emit order so positions are emitted before make/miss. Pick per-subsystem or standardize.
2. **Turn-by-turn vs a shared "position service":** the deepest fix is a single helper the emitter and all logic call for "player positions at step N," eliminating re-derivation everywhere. Bigger refactor; decide scope.
3. **Which archetype/rate is *intended*** for the FB finisher drive (sprint vs standard-gather) — needed to know which side is "right" if not doing full read-render. (Per §9.5 they just have to *match*; design intent decides which.)
4. **Trap/press physical validity** (`Trap_Press_Positioning_Decision.md`, settled framing): size collapse/advance beats by the slowest mover so the intended positions are reachable, and use matched engine/emitter rates — so `end.coords` == logic == render. Confirm the "real-speed (slightly slower) trap close" is acceptable (it's correct physics).

## 7. Verification notes

- **Sim-verifiable in the mock** (fire from DREB/steal/foul): Fast Break, Free Throw, Opening Tip. FB clock fix was measured (gap 2.37s→0.26s). The FB **48% no-defender** IS measurable — but the drive-resolution path (with `defender_end_coords`) is NOT hit by the mock's simpler FB shots; the 48% comes from live game reports. Verify FB Group C in the **prototype**, or first make the mock exercise `resolve_fb_drive_step`.
- **NOT sim-verifiable** (need prototype/trap-defense config): HCT, FCP. Their fixes were parity-based + regression-clean; watch in prototype.
- **RNG isolation for regression:** the dynamic HCT/FCP test suite is broadly flaky (MagicMock + RNG order). Always git-stash-isolate a failure before attributing it.

## 8. Report to watch

End-of-game diagnostics: grep **`END-OF-GAME SHOT DIAGNOSTICS`** (`shot_split_tracker.py:378`). Has FGA by turn type + contested/uncontested. The **48% FB no-defender** shows up here; use it as the before/after metric for the FB contest fix.

## 9. Pointers

- **Per-turn audits:** `_documentation_master/projects/UESS Audits/` — SIP, HCT, FCP, Fast_Break, Free_Throw, Opening_Tip, Timeout + the cross-cutting `Coord_Consumer_UESS_Audit.md`, `Shot_Classification_UESS_Fix_Scope.md`, `Trap_Press_Positioning_Decision.md`.
- **Spec:** `UESS_System.md` §1 (single-coord-source), §9.5 (destinations are intent + the logic-reads-interrupted-end rule), §12.1/§12.2 (known gaps).
- **Memory (persists across threads):** `project_uess_turn_sweep` (sweep status + this capstone), `project_shot_system_tuning` (FG%/3PT% tuning — this fix shifts those, retune after).
- **Shipped fix reference implementation:** `_uess_sync_emitted_shot_coords` in `phase_resolution.py` (the pre-pass pattern to copy).

## 10. Suggested sequence for the new thread

1. ~~Start with **Fast Break contest**~~ — **✅ DONE (2026-07-07).** Full emit-then-resolve sweep (all FB drive decisions read rendered coords) + Phase-1 contest; coord-source guard 20→0, widened to a CI ratchet over all engine decision modules. See the §3 Status update.
2. ~~**Over-and-back** (`_advance`)~~ — **✅ already fixed in code** (2026-07-06 trace): emitter renders BH advance at AG-drive rate (`dynamic_hct_step_emitter.py:279-287`) matching engine `_advance`. Only re-open if it's still reported live (then chase seam-drift: emitter start `prev_end_coords[bh]` vs logic `bh_xy`).
3. **← NEXT: HCT/FCP trap/press** (`Trap_Press_Positioning_Decision.md`) — the last position-authority gap. Engine snaps all 5 defenders to the full trap; render interrupts them → steal/foul fires from a defender not visibly on the ball (a *teleport*, not a `player.coords` read — the guard can't see it). Fix (§6 #4, design settled): size the collapse/converge beat by the **slowest mover** so the trap is reachable, matched engine/emitter rates → `end.coords` == logic == render. **GATE: needs a user design decision** — confirm the *real-speed (slightly slower) trap close* is acceptable (correct physics, but the trap visibly takes an extra beat to snap shut). Then prototype-verify (not fully sim-checkable). Note: the HCT moment engine is shared by the now-default Dynamic HCO system, so this work is adjacent.
4. Consider the **shared position-service** refactor (decision #2) once 1-3 confirm the pattern. (FB proved the *emit-then-resolve* variant of this; #2 is the universal "one position service the emitter + all logic read" version.)
