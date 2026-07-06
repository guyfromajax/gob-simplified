# Emitter As God — single position authority (handoff)

**Purpose:** knowledge-transfer for a new thread. This is the overarching fix the whole UESS turn-audit sweep pointed at. Read this first, then the per-turn audit docs it references.

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
| **Fast Break contest** | logic clamps defenders at BH **sprint**-T toward `basketSpot`; render tweens at **standard**-T toward `author_transition` matchup spots | **48% of FB shots register "no defender"** (should be ~10%); also feeds rebounder + gates block/defense → **inflates FB FG%** | ⏳ SCOPED/DEFERRED | `Fast_Break_UESS_Audit.md` #2/#7/#8 |
| **HCT trap** positioning | engine snaps all 5 defenders to full trap; render interrupts them | steal/foul fire from a defender not visibly on the ball | ⏳ DEFERRED (design settled) | `Trap_Press_Positioning_Decision.md` |
| **FCP press** positioning | same, amplified (`skip_walk_up` → sole converge beat can't render the full close) | worse than HCT | ⏳ DEFERRED | `Trap_Press_Positioning_Decision.md` |
| **Over-and-back / BH advance** | `_advance` jumps BH at **AG-drive** rate in logic; render tweens at **standard** → engine BH ahead of screen | over-and-back / frontcourt / 10-sec violations fire from an unrendered BH position (reported bug) | ⏳ separate thread | `Fast_Break_UESS_Audit.md` #6, `dynamic_hct.py:2511/3185` |

(A distinct, non-coord §1 issue: Timeout's *eligibility rule* lives in the FE — `Timeout_UESS_Audit.md` #1. Same "logic must be backend" spirit, different mechanism. Decision pending.)

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

1. Start with **Fast Break contest** — it's the reported bug (48%), has a concrete before/after metric, and directly affects FG% tuning. Fix H2 (logic reads rendered defender position / matched rate); re-measure; then treat H1 as a tuning knob.
2. **Over-and-back** (`_advance`) — same `_advance` root, small, and a reported bug.
3. **HCT/FCP trap/press** (`Trap_Press_Positioning_Decision.md`) — the settled design; needs prototype verification.
4. Consider the **shared position-service** refactor (decision #2) once 1-3 confirm the pattern.
