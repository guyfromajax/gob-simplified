# RR/Triangle Emit-Then-Resolve Migration — executable plan

**Status: SHIPPED 2026-07-07** (branch `fb-migration-rr`). Steps 1–3 done + verified; guard baseline 20→18. Step-4 clamp removal **deferred** (see below). The first turn migrated to the "logic reads emitter coords" objective ([Emitter_As_God.md](Emitter_As_God.md), [Coord_Source_Registry.md](../05_UESS_System/Coord_Source_Registry.md)).

**Verified:** stash reaches emitter 5/5 RR drive turns; `build_rr_drive_preamble` called ~1×/drive (no rebuild) → single-source by construction; RR/Triangle cutoff now fires (~53% has-stopper vs. prior ~44%; `NO_MEET` ~47% vs. ~56%); no crash.

**Step-4 clamp finding:** the `_no_retreat_end` clamp is **NOT** removable yet — it still fires ~85% of calls because it patches `def_start_coords` inside `author_defense_end_coords`, which is the **After-Steal** seed path (`after_steal_drive_integration.py:758/760`), not the RR resolver seed this migration fixed. Remove it only when After-Steal migrates.

## Context / the bug this fixes

On an RR/Triangle fast break, after the lane pass the receiver drives to the rim and **a defender near the basket just stands there — no attempt to cut off the drive** (measured: ~56% of RR drives resolve `NO_MEET`). Root: the resolver seeds defender start positions from **stale `player.coords`** (start-of-break; RR/Triangle skip `apply_coords`) — [`def_starts = _lineup_starts_by_pos(def_lineup)`, rim_runner_drive_integration.py:184](../../BackEnd/engine/rim_runner_drive_integration.py#L184). The defender who — on screen — sprinted back near the basket is, to the resolver, still far behind → `best_cutoff_on_drive` finds no cutoff → `NO_MEET` → no attempt. The emitter, meanwhile, renders those defenders from the **burst→outlet→lane-pass get-back chain**. Two coord sources → the §1 violation.

**Fix:** seed the resolver from the emitter's **rendered drive-start positions** (the lane-pass `end.coords`) instead of `player.coords`. Then the resolver sees the near-basket defender where he actually is → the cutoff fires → the defender steps out to meet the drive.

## The hard constraint (why stash-and-reuse, not a pre-pass)

`resolve_fb_drive_step` **draws RNG between** the resolver's preamble build and the emitter's preamble build. So RNG-isolation or a deterministic get-back do **not** make the two builds match. The only construction that guarantees `resolver def_starts == emitter rendered positions` is: **build the preamble once (in the resolver), stash it, and have the emitter reuse the stash** — no rebuild, no double-draw. This is mechanism (A) emit-then-resolve.

## Coord-boundary map (settled; from the registry)

| Decision | Reads |
|---|---|
| Cutoff/meet race, `t_drive`/`t_meet` | drive-step **start** = lane-pass `end.coords` |
| NEUTRAL receiver pick + pass contest | **meet-moment** (meet sub-step end) |
| Pass-ahead contester | **ball-detach** (pass-flight step start) |
| Shot contest + shooting foul | drive-step **end** |
| Rebounder | post-shot **end** |

## Implementation (staged, verify each gate)

### Step 1 — extract `build_rr_drive_preamble()` (behavior-preserving)
In [rim_runner_step_emitter.py](../../BackEnd/engine/rim_runner_step_emitter.py): extract setup + burst + outlet + lane-pass (the **drive path only** — no terminal branches) into `build_rr_drive_preamble(turn_result, game) -> Optional[(steps, lane_pass_end_coords)]`. Seams:
- setup: `build_rim_runner_animation_steps` lines **2179-2214**
- burst: **2216-2231** (`_build_burst_step`)
- outlet (unless `skip_outlet_pass`): **2254-2271** (`_build_outlet_pass_step`)
- lane pass + end coords: `append_lane_pass_to_rr_resolution_steps` **2094-2112** (`_build_lane_pass_step`; end = `coords` at **:2112**)
- **do NOT include** the drive build (**:2116**) or the terminal branches (outlet_failed **:2238**, interception/bat_oob/no_lane_pass **:2049-2092**).
Refactor `build_rim_runner_animation_steps` so the drive path calls `build_rr_drive_preamble` (single preamble build path). **Verify: emitted steps byte-identical vs before** (no behavior change).

### Step 2 — resolver builds preamble, seeds, stashes
In [`resolve_attack_drive_finisher_turn`, rim_runner_drive_integration.py:154](../../BackEnd/engine/rim_runner_drive_integration.py#L154): **before** `resolve_fb_drive_step` (**:187**):
- call `build_rr_drive_preamble(turn_result, game)` → `(preamble_steps, lane_end)`.
- seed `def_starts` / `off_starts` from `lane_end` (replace `_lineup_starts_by_pos` at **:184/:193**). `bh_start` stays `rr_to` (already emitter-consistent — [:172](../../BackEnd/engine/rim_runner_drive_integration.py#L172)). Annotate the kept `rr_to` seed `# coord-source-ok: rr_to converges with the emitter's lane-pass BH end by construction`.
- stash `turn_result["rr_preamble_steps"] = preamble_steps` (and the end coords) for the emitter to reuse.

### Step 3 — emitter reuses the stashed preamble
In `build_rim_runner_animation_steps`: if `turn_result.get("rr_preamble_steps")` is present (drive case), **use them** as the preamble and build the drive from the stashed lane-pass end — skip the rebuild. Terminal branches (no stash) build as today.

### Step 4 — guard + cleanup
- Lower the `check_coord_source.py` `BASELINE` by the RR sites removed (from 20).
- The **no-retreat clamp** (`after_steal_transition_positioning.py` `_no_retreat_end`) becomes **removable** once seeds are rendered-consistent — it was the symptom patch this replaces. Remove it and re-verify no topLane regression.

## RNG note
The preamble RNG (lane-pass d6 [:822](../../BackEnd/engine/rim_runner_step_emitter.py#L822), get-back tiebreak [:852](../../BackEnd/engine/rim_runner_step_emitter.py#L852)) is now drawn **once** in the resolver's preamble build (before the drive rolls) and the emitter reuses the result → **one-time chronological reorder** of the RNG stream (aggregate-neutral, not byte-identical replay; same tradeoff accepted for Phase-2 FB convergence). Verify **structurally**, not by byte-identity.

## Verification
1. **Step-1 byte-identical** preamble steps (refactor is behavior-preserving).
2. **Structural single-source:** assert `resolver def_starts == emitter lane-pass end.coords` (RNG-independent).
3. **Gameplay:** RR/Triangle `NO_MEET` rate drops; a defender rendered near the basket now produces a cutoff/meet → **steps out to meet the drive**. Measure via `scripts/rr_drive_outcomes.py` (scratchpad) or an equivalent.
4. **Guard baseline** drops from 20.
5. **Prototype:** the near-basket defender attempts the cutoff; no topLane regression after removing the no-retreat clamp.

## Then: CR + After-Steal
- **Covert Release** = same shape (outlet preamble → drive); apply the same extract/seed/reuse. Lower baseline further.
- **After-Steal** = drive is the first step (little preamble); its `def_starts`/`off_starts` (**:758/:760**) still need rendered seeds — smaller change.
Drive `check_coord_source.py` baseline toward **0** across all three, then move to the next turn family.
