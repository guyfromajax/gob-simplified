# FCP (Full Court Press) — UESS Compliance Audit

**Verdict: cleaner than HCT on clock/§1, but the §8.3 press-positioning divergence is WORSE.** Two low-risk entry-seam fixes (FCP never got the HCT-Task 2/3 parity), plus the HCT #6/#7 "engine reads full-snap, emitter renders interrupted" divergence — amplified because FCP skips the walk-up. (2026-07-05, 4-dimension parallel trace; deltas-from-HCT only.)

> **Shared with HCT (not re-covered):** FCP = dynamic press via `compute_dynamic_hct_turn(turn_mode="fcp")` + the shared emitter (`skip_walk_up=True`). HCT-shared findings (post-steal clock, interception freeze) are in [`HCT_UESS_Audit.md`](HCT_UESS_Audit.md) / [`../FCPHCT_UESS_Audit.md`](../FCPHCT_UESS_Audit.md). The HCT-Task 1 **backfill fix covers FCP** (runs before the `skip_walk_up` branch — verified).

## Topline
- **§5 clock:** ✅ **Compliant** — and *free* of HCT's walk-up-blindness (HIGH #1): FCP's `fcp_engagement` is a real committed loop segment, decremented from the engine shot clock. New-possession shot clock correctly reset upstream.
- **§1 coord-source:** ✅ **Compliant** — cleaner than HCT (engagement + off-ball routes pre-apply the emitter's interrupted clamp). Dynamic FCP resolves shots via the shared render-exact `dynamic_hct_shot`. Legacy FCP shot branch is **dead code** (dormant behind `USE_DYNAMIC_FCP=True`).
- **§8.1 / §8.2:** ✅ **Compliant** — backfill covers the `skip_walk_up` entry; step + exit seams clean.
- **§8.4 ball-seam:** ⚠️ **Entry teleport + no detector** — FCP never got the HCT-Task 2/3 parity.
- **§8.3 positioning:** ⚠️ **The main FCP exposure — worse than HCT.**

## Findings (ranked)

| # | Sev | Dim | Finding | Location |
|---|---|---|---|---|
| 1 | **HIGH** | §8.3 | **Initial press never renders to the logical formation.** The sole formation beat (`hct_converge`, FCP has no walk-up to pre-position) snaps all 5 defenders onto the full-court press via `_position_defense`, but sizes `converge_seconds` by the PG's move only. The emitter re-interpolates each defender at **standard** rate over that tiny window → SG/SF/PF/C fall far short; the engine reads the **full-snap** `def_coords` for moment/contest while the render shows defenders mid-court. Lag persists the whole turn. HCT #6 amplified by `skip_walk_up`. | dynamic_hct.py:2453 vs dynamic_hct_step_emitter.py:280 |
| 2 | **MED-HIGH** | §8.4 | **Entry ball teleport.** FCP's `skip_walk_up` branch never seeds the ball from `prior_turn["final_ball_coords"]` — the HCT-Task 2 fix is in the walk-up `else` branch only. Step-0 ball attaches to the BH → teleports when the prior rendered rest diverges (in-flight/loose/different-BH). | dynamic_hct_step_emitter.py:756-767 (vs :807-821) |
| 3 | MED | §8.3 | **Terminal steal/foul from a defender not visibly on the ball.** Terminal `_emit_stopper` full-snaps the press onto the BH then appends a fixed 0.5s; the emitter renders interrupted-standard → defenders never reach the BH, but `_resolve_attack` credits STEAL/FOUL from the full-snap `def_coords`. | dynamic_hct.py:2752 vs :280 |
| 4 | MED | §8.4 | **No `[UESS SEAM]` detector at the FCP callsite.** HCT-Task 3's detector is in the `state=="HCT"` branch; FCP is a separate `state=="FCP"` callsite (turn_manager.py:1642/1654) → #2 is silent. FCP is the only migrated entry-emitter turn with no detector. | turn_manager.py:1642-1687 |
| 5 | MED | §8.3 | **PF/C sprint-vs-standard, amplified.** `_move_defense` runs PF/C (+ recovered) at **sprint**; emitter renders off-ball at **standard**. FCP's full-court `fcp_pf_c_zone` drops are large → bigger rendered lag than HCT. (Off-ball *offense* is clean — both use sprint.) | dynamic_hct.py:1875 vs :270 |
| 6 | LOW→consequential | §1/§8.3 | **`_advance` BH drive rate mismatch → over-and-back / violation reads.** Engine jumps the BH the full distance at **AG-drive rate**; emitter renders interrupted at **standard**. For a fast handler the engine BH ends **ahead** of the rendered BH, and the FCP-load-bearing reads run off the engine's forward pos: `frontcourt_established`, 10-second violation, **`is_over_and_back_pass`**. → engine thinks BH is in the frontcourt while the FE renders him crossing back → **over-and-back violation doesn't fire.** Shared `_advance` (hits HCT + FCP). **Likely the over-and-back bug reported in the other thread.** | dynamic_hct.py:2511-2521, :3185 |
| 7 | LOW | §8.2 | Coordless-player seed divergence (FCP seed path): engine `_seed_lineup_coords_from_prior` defaults a no-coord player to (50,25) + generates moves; emitter's backfill skips coordless players → frozen/invisible. Degenerate case, FCP seed path only. | dynamic_hct.py:2128 vs skeleton_step_emitter.py:204 |

## Clean (verified, FCP-specific)
- Shot terminals (FB / attack-basket) render-exact via shared `dynamic_hct_shot` (contest + 2/3 from emitted `defender_end_coords`/`shot_spot`); FCP assemblers don't override.
- `fcp_engagement` + `fcp_offball` are render-exact (engine pre-applies the interrupted/sprint clamp the emitter uses).
- No live FCP decision reads `player.coords`. Legacy `player.coords` shot branch confirmed dead (USE_DYNAMIC_FCP=True early-return, phase_resolution.py:7765).

## Work plan
**Group A — entry-seam parity (low-risk, localized) — ✅ DONE (2026-07-05):**
- ✅ **FCP-Task 1 (MED-HIGH #2):** step-0 ball seeded from `prior_turn["final_ball_coords"]` in the emitter, guarded on `skip_walk_up` + divergence from the step-0 ball owner's coord (mirrors HCT-Task 2). Since FCP's step-0 is the first loop segment (no walk-up step), the override is applied to `steps[0]["start"]["ball"]` after the loop builds. Preserves the common-case attached dribble; only fixes the real teleport.
- ✅ **FCP-Task 2 (MED #4):** `[UESS SEAM]` detector added at the FCP callsite (`state=="FCP"`, turn_manager.py:1642); detection-only, mirrors HCT-Task 3.

Regression-neutral (dynamic FCP/HCT suite is broadly flaky — MagicMock config + RNG order-dependence; no deterministic break from these changes, isolated via git-stash). Parity-verified (mirrors the SIP/HCT/OREB patterns); full-sim FCP trigger not achieved in the mock.

**Group C — press-positioning divergence (design call, FCP-PRIORITY):**
- **FCP-Task 3 (HIGH #1 + MED #3/#5):** the HCT-Task 7 reconciliation (engine reads the interrupted/**rendered** positions for contest + steal/foul eligibility) is **more urgent for FCP** — the press visibly never closes, yet steals/fouls fire from the snapped formation. Same design question: should the press *behave* from where it's *shown*?
- **#6 over-and-back:** shared `_advance` rate mismatch — hand to the separate over-and-back thread; same fix family (logic reads rendered BH pos).

**Deferred/shared:** post-steal clock (HCT-doc'd), #7 coordless degenerate seed.

## Cross-turn note
FCP inherits SIP/HCT's entry-seam defects (#2/#4) — same low-risk parity fix. Its distinctive issue is #1: `skip_walk_up` makes the §8.3 press-positioning divergence materially worse than HCT. And #6 is the concrete coord-source mechanism behind the reported over-and-back bug.
