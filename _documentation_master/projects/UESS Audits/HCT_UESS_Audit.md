# HCT (Half-Court Trap) — UESS Compliance Audit

**Verdict: the messiest turn in the sweep — 2 HIGH, 1 MED-HIGH, 5 MED.** Shot logic is exemplary (§1 reference pattern); the problems are the **entry seam** (backfill + ball + detector, some SIP-parity), a **dual clock authority** that diverges, and **trap positioning logic-vs-render** divergence. (2026-07-05, 4-dimension parallel trace; builds on the interception audit below.)

> **Scope note:** the pass-**interception / steal** freeze bug (no pass-flight segment, ball teleport passer→stealer, `runSteal` FE stub) is separately documented in [`../FCPHCT_UESS_Audit.md`](../FCPHCT_UESS_Audit.md) (2026-07-04) — NOT re-covered here.

## Topline (human-scannable)
- **§1 coord-source:** ✅ **Compliant — reference pattern.** HCT shot decides contest + 2/3 classification from the *exact* `defender_end_coords`/`shot_spot` the emitter renders (no `player.coords`, no re-interpolation) — stronger than the HCO/FCP pre-pass fix. Trouble is trap *defender positioning* (see §8.3), not the shot.
- **§5 clock:** ⚠️ **Dual authority diverges.** Engine shot-clock is blind to the entry walk-up (HIGH); post-steal exit seam doesn't reset the shot clock and drops 0.5s of game clock.
- **§8.1-8.3 player-coord:** ⚠️ **HIGH backfill gap** (dropped player frozen whole turn) + **MED trap logic-vs-render** divergence.
- **§8.4 ball-seam:** ⚠️ Entry ball teleport + no detector — **the same two defects just fixed for SIP.**

HCT = dynamic trap (shared `compute_dynamic_hct_turn` loop with FCP) → multi-outcome: shot / steal-interception / reset. Two emitters: `dynamic_hct_step_emitter` (live), legacy `hct_step_emitter` (flag-disabled).

## Findings (ranked)

| # | Sev | Dim | Finding | Location |
|---|---|---|---|---|
| 1 | **HIGH** | §5 | **Engine shot-clock blind to entry walk-up.** Engine decrements only its loop segments; the ~1-2s step-0 walk-up (BH bring-up) is emitter-only, never fed back → engine shot-clock runs ~1-2s high → shot-clock (`<=0`) + 10-sec violations under-fire (offense gets ~31-32s). HCT-specific (`skip_walk_up` for FCP). | dynamic_hct.py:2247/2944/2952 vs emitter :765 |
| 2 | **HIGH** | §8.2 | **No `_backfill_missing_active_coords` on HCT entry.** Emitter reads `prior_turn.final_coords` raw; a player `build_final_coords` dropped (None coords) is silently absent the *entire* turn (frozen/invisible) + stale carry. HCO/BIP/SIP backfill at their callsites; the dynamic HCT/FCP callsite does not. | dynamic_hct_step_emitter.py:711-731; turn_manager.py:1651 |
| 3 | MED-HIGH | §5 | **Post-steal transition doesn't reset shot clock.** Post-steal step hands ball to stealer but keeps decrementing the *old* possession's shot clock (no reset to 30); reset lands only on the next turn → forward skip at exit seam. | skeleton_step_emitter.py:3352-3392 |
| 4 | MED | §8.4 | **Entry ball seeded by attachment (BH), not `final_ball_coords`.** `build_walk_up_step` hardcodes ball to `bh_id`; HCT never threads the prior rendered ball rest. Teleports on in-flight/loose prior ends, or `prior_final_bh_id==None` (→ *this* turn's BH). **SIP-Task 1 parity.** | dynamic_hct_step_emitter.py:764-778; transition_bridge.py:350 |
| 5 | MED | §8.4 | **No `[UESS SEAM]` entry detector** (siblings all have one) → #4 is silent. **SIP-Task 2 parity.** | turn_manager.py:1695-1720 |
| 6 | MED | §8.3/§1 | **Trap logic reads full-collapse positions; emitter renders interrupted.** `_position_defense` snaps `def_coords` to full target (engine reads for moment/trap detect, pass-contest eligibility, steal/foul); `_build_loop_step` re-derives each defender's rendered end via `_interrupted_coord(...standard_rate, t)`. On short trap-collapse segments the visible trap never closes to where logic fired → a steal/foul from a defender **not visibly on the ball**. Coord-consumer pattern, applied to trap positioning. | dynamic_hct_step_emitter.py:280 vs dynamic_hct.py _position_defense |
| 7 | MED | §8.3 | **Rate mismatch.** Engine moves PF/C + recovered defenders at **sprint** (`_move_defense`, `_recover_defense_targets`); emitter renders all at **standard** → rendered lag, worst on the mid-court recovery beat. | dynamic_hct_step_emitter.py:268-270 vs dynamic_hct.py:1874-1882 |
| 8 | MED | §5 | **Post-steal 0.5s not committed.** Post-steal step appended *after* `time_elapsed = sum(step_clock_seconds)` finalized → its 0.5s game-clock burn dropped → 0.5s backward jump at exit seam; `executed_step_count`/`resolution_step_index` left stale (off-by-one). | dynamic_hct_step_emitter.py:1037 vs :1063 |
| 9 | LOW | §5 | Per-step shot clock not floored at 0 (`start - t`, no `max(0,…)`) → a segment crossing zero renders a negative shot clock before the top-of-loop check catches it. | dynamic_hct_step_emitter.py:322-325 |
| 10 | LOW | §8.4 | Degenerate-pass fallback (`hct_pass` with passer/receiver missing from `prev_end_coords`) → `_build_loop_step` attaches ball to receiver, no flight → teleport. Only on degenerate input. | dynamic_hct_step_emitter.py:838-853 |
| 11 | LOW | §1 | Off-ball rebounder **attribution** flip: off-ball players stamped at seed positions, emitter drifts them (`HCT_DRIFT_PROBABILITY`) → resolver can't see rendered ends. Possession stable (box-out). Accepted-gap class (Coord_Consumer #3/#4). | dynamic_hct_shot.py:343-372/794-822 |
| 12 | LOW | misc | Collision resolver `resolve_hct_defender_collisions` legacy-only (rare dynamic overlap); post-steal RNG re-pick jitter; `walk_up_bh_id` gate mis-seed; FB race-start from seed not emitter-interrupted (bounded). | shared_defense.py:231; dynamic_hct_step_emitter.py:719 |
| — | DORMANT | §1 | Legacy `resolve_half_court_trap_logic` shot branch reads `player.coords` (classic pre-fix defect) — **unreachable**, `USE_DYNAMIC_HCT=True` forces early return. Risk only if flag flipped. | phase_resolution.py:10019-10044 (gated :9061/:9880) |

## Clean (verified)
- **§1 shot:** contest + classification render-exact (`classify_shot_value`/`is_three_point_shot_from_coords` on rendered `shot_spot`; contest from rendered `defender_end_coords`). Reference pattern.
- **§8.1:** step seams clean (every builder threads `prev_end_coords`).
- **§8.4:** non-intercept pass (flight + catch-transfer), trap loop ownership, trap→shot handoff (ball stays attached), exit seam (universal `final_ball_coords` stamp) — all compliant.
- **§5:** intra-turn `time_elapsed` reconciles; entry seam continuous; steal branch burns trap time.

## Work plan (proposed)
**Group A — SIP-parity + backfill (low-risk, localized, high-value) — ✅ DONE (2026-07-05):**
- ✅ **HCT-Task 1 (HIGH #2):** `_backfill_missing_active_coords` applied in the emitter right after reading `prior_final_coords` (dynamic_hct_step_emitter.py) → walk-up carries all 10.
- ✅ **HCT-Task 2 (MED #4):** step-0 ball seeded from `prior_turn["final_ball_coords"]` — but **only when it diverges (> epsilon) from the BH's start coord**, so the common-case attached dribble is unchanged and only the real teleport (in-flight/loose/None-BH prior end) is fixed. (More conservative than SIP, which is always-loose; HCT's ball is a dribble, not an inbound.)
- ✅ **HCT-Task 3 (MED #5):** `[UESS SEAM]` entry detector added at the callsite (turn_manager.py, mirrors SIP/OREB); detection-only.

Regression-clean (the dynamic HCT/FCP test suite has ~6 pre-existing baseline failures, all isolated via git-stash). Full-sim HCT trigger not achieved in the mock (needs trap-defense playbook config); fixes rest on parity with verified SIP/BIP/OREB patterns + the conservative divergence gate on Task 2.

**Group B — clock authority (medium-risk, engine/emitter):**
- **HCT-Task 4 (HIGH #1):** feed the walk-up duration into the engine shot-clock (so violations evaluate the committed clock).
- **HCT-Task 5 (MED-HIGH #3 + MED #8):** post-steal transition — reset shot clock to 30 for the new possession, and fold its 0.5s into `time_elapsed` (+ fix stale step counts).
- **HCT-Task 6 (LOW #9):** floor per-step shot clock at 0.

**Group C — trap positioning (needs a design call):**
- **HCT-Task 7 (MED #6/#7):** reconcile engine full-collapse/sprint vs emitter interrupted/standard — either the engine reads the interrupted (rendered) positions for steal/foul eligibility, or the emitter renders the full collapse. Decision: should the trap *behave* from where it's *shown*? (Recommend engine reads render, matching the coord-consumer principle.)

All shift trap/steal/clock behavior → coordinate with shot-system tuning ([[project_shot_system_tuning]]).

## Cross-turn note
#4/#5 are the same entry-seam defects just closed for SIP; #2 the same backfill gap. #6 is the coord-consumer principle (logic reads render) applied to trap positioning — the HCT-specific analog of the contest-defender fix.
