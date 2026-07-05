# Fast Break (FB) — UESS Compliance Audit

**Verdict: the richest audit in the sweep — issues on 3 of 4 dimensions across 4 families (Steal/RR/CR/Triangle + universal drive-step).** The render is reachability-safe by construction (the good pattern), but: the **clock exit seam** isn't reconciled (every family), the **ball entry seam** never got the SIP/HCT/FCP parity (×4), and the **contest/rebounder read a different coord frame than the render** on the drive step. (2026-07-05, 4-dimension parallel trace, deltas beyond the coord-consumer / three-pointer / interception docs.)

> **Sim-verifiable (unlike HCT/FCP):** FB fires from DREB + steal, which the mock produces → fixes here can be validated in the mock. Trigger sources: `resolve_fast_break_logic` (phase_resolution.py:1154), DREB `rebound` branch + `AFTER_STEAL`. **No made-shot FB path exists.**

## Topline
- **§8.1-8.3 player-coord:** ✅ **Render is reachability-safe by construction** (interrupted-coord clamp + BH-traversal T-floor → the length-of-court sprint never teleports). Step + turn seams hold. One §8.3 rate-mismatch (capstone).
- **§5 clock:** ⚠️ **Exit seam broken (HIGH, all families)** — `time_elapsed` is a hand-rolled approximation, never reconciled with the schema per-step deltas. Entry seam + shot-clock reset ✅.
- **§8.4 ball-seam:** ⚠️ **Entry seam unguarded ×4** — no `final_ball_coords` seed, no `[UESS SEAM]` detector; + the `final_ball_coords` snapshot is itself wrong for STEAL. Within-turn (outlet/drive/shot) + exit ✅.
- **§1 coord-source:** ⚠️ **Contest/rebounder read a different frame than render** on the drive step (partly overturns the coord-consumer "render-synced by construction" claim).

## Findings (ranked)

| # | Sev | Dim | Finding | Location |
|---|---|---|---|---|
| 1 | **HIGH** | §5 | **Exit-seam clock discontinuity (all 4 families).** Turn-level `time_elapsed` is an independent estimate (`t_shooter+1`, legacy cover-ground, `t_drive+X`, or literal `random`), never reconciled with the emitted per-step clock deltas — unlike FCP (turn_manager.py:1700-1708). FB's last rendered step-end clock ≠ next turn's step-0 start → backward jump / forward skip at **every** FB exit. | turn_manager.py:1638-1641; after_steal_fast_break.py:853; phase_resolution.py:1147 |
| 2 | **HIGH** | §1 | **Contest/rebounder read a different coord frame than render.** Contest y/n + `shot_defender_id` committed from `defender_end_coords` (interrupted toward `basketSpot`), but RR/CR/Triangle pass `author_offball_spread=True` → emitter re-authors defenders toward `author_transition_end_coords` (matchup/help spots). Rendered defender ≠ contest-computed position → contest can flip (gate = Euclid ≤11 AND x-trail ≤3). Coord-consumer "render-synced" holds only for After-Steal (`author_offball_spread=False`). | fb_drive_step_emitter.py:268-280; fb_drive_resolution.py:311/462 |
| 3 | MED-HIGH | §8.4 | **No FB entry-seam parity (×4 families).** Every family seeds step-0 ball from owner-id at live `player.coords`, never `prior_turn["final_ball_coords"]`, and no `[UESS SEAM]` detector at any FB callsite. FB is the only migrated turn family with neither. | rim_runner_step_emitter.py:598; covert_release_step_emitter.py:1487; after_steal_fast_break_step_emitter.py:279; triangle_step_emitter.py:186 |
| 4 | MED-HIGH | §1 | **Triangle spot-up 3PT contest reads `player.coords`** (end-of-DREB) while defenders render at their setup `to` spots (the drive-step interrupt doesn't cover spot-up branches). Classification IS render-synced; contest isn't. | rim_runner_fast_break.py:278-288/332/372; rim_runner_drive_integration.py:77-93 |
| 5 | MED-HIGH | §5 | **DEFENSIVE_STOP clock inconsistent.** Schema meet step burns `t_meet` + ends the turn, but turn-level accounting drops/approximates it (outlet-denied stamps `0`; CR uses `t_drive+1`; `_compute_real_time_elapsed_ms` treats FB stop as 0 game time) → backward jump into the ensuing HCO. | fb_drive_step_emitter.py:332-335; rim_runner_fast_break.py:986/998 |
| 6 | MED | §8.4 | **`final_ball_coords` snapshot is wrong for STEAL.** `build_final_ball_handler_id` special-cases STEAL → stealer, but `build_final_ball_coords` has no STEAL case → coords = victim's spot. The safety net that #3's fix relies on is itself wrong for steal. | animation_step_helpers.py:73-76 vs :148-157 |
| 7 | MED | §1 | RR/CR rebounder selection decides from `_build_offense_end_coords` (sampled arc spots) — a frame the emitter discards for `author_transition_end_coords`. After-Steal is aligned (same planner). | rim_runner_drive_integration.py:470; covert_release_drive_integration.py:452 |
| 8 | MED | §8.3 | **Rate-archetype engine-vs-render mismatch (capstone class).** Resolver budgets defender reachability at BH **sprint** (18 grid/s); render floors step-T to BH **standard** finisher pace (14, ~29% slower) → rendered defenders close ~29% farther than the contest/rebound geometry credited. Same `_advance` class as HCT/FCP. | fb_drive_resolution.py:449-451 vs fb_drive_step_emitter.py:434-454 |
| 9 | MED | §5 | Shot-clock burn rides the approximation; no FB family emits `step_clock_seconds`/`resolution_step_index` → shot-clock detach burns the whole estimate, not schema deltas up to detach. | turn_manager.py:5198-5213 |
| 10 | LOW | §5 | RR bat-OOB dead ball burns `random.randint(2,5)` game clock → nondeterministic seam jump into SIDE_INBOUND. | rim_runner_fast_break.py:1437 |
| 11 | LOW | §1 | NEUTRAL pass-receiver + shooter-location read drive-start `player.coords`; RR lane-pass interception gate + CR release/get-back selection read `player.coords`. | fb_stop_decision.py:42-70; rim_runner_fast_break.py:1349 |
| 12 | LOW | §8.2 | After-Steal seeds step-0 from `final_coords` not synced `player.coords` (RR/CR read `player.coords`); emitter-None → legacy-finals exit fallback (logged); cold-start `coords is None` drop (no FB-entry backfill). | after_steal_fast_break_step_emitter.py:508 |

## Clean (verified)
- **§8.1/§8.2/§8.3 render:** reachability-safe by construction — interrupted-coord clamp (`_interrupted_coord`) + BH T-floor (`floor_step_t_to_traversal`); `_reachable_defender_ends` bounds defenders. No unbounded snap in the rendered path.
- **§8.4 within-turn + exit:** outlet pass = real gated flight w/ seated capture; outlet→lane→drive→shot owner chain continuous; exit ball seam via universal `_append_turn` snapshot.
- **§5 entry + shot-clock reset:** step-0 seeds from committed `game_state`; shot clock reset upstream on the trigger turn (consistent across families).
- **§1 classification:** 2/3 forced-2 (rim) / `roles["shot_spot"]` (outside) render-synced; After-Steal drive path best-aligned.

## Capstone flags (feed the reachability audit)
- **#8** rate mismatch (sprint budget vs standard render) — engine and render must use the *same* archetype rate.
- `after_steal_transition_positioning.py:225-363` (`_chase_behind`/`_lead_defender_spot`/`_assign_help_spots`/`_assign_arc_spots`) are **pure destination snaps** — safe ONLY because `_build_drive_step` re-interrupts them. **Verify** the meet/terminal/DEFENSIVE_STOP branches apply the same clamp — a raw-consume would teleport a get-back defender midcourt→rim.

## Work plan (grouped)
**Group A — clock exit-seam reconciliation:**
- ✅ **FB-Task 1 (HIGH #1/#5) — DONE (2026-07-05).** Applied the FCP treatment to the `state=="FAST_BREAK"` branch (turn_manager.py:1641): recompute `result["time_elapsed"] = int(round(steps[0].start.clock − steps[-1].end.clock))` for ALL FB terminals. **Sim-verified: exit-seam gap avg 2.37s→0.26s, max 6.11s→0.50s** (residual is just int-clock rounding of the fractional schema burn — same as FCP). Fixes DEFENSIVE_STOP (worst offender) + MISS + bat-OOB random uniformly. Regression-clean.
- ⬜ **FB-Task 1b (MED #9):** shot-clock detach — no FB family emits `step_clock_seconds`/`resolution_step_index`, so shot-clock detach burns the whole `time_elapsed` estimate, not the schema deltas up to detach. Needs each FB family to emit those. Largely masked (shot clock resets next possession); lower priority.

**Group B — ball entry-seam parity (MED-HIGH #3 + MED #6):**
- **FB-Task 2:** seed step-0 ball from `prior_turn["final_ball_coords"]` (divergence-gated) + add `[UESS SEAM]` detector — ×4 family emitters (or a shared FB entry helper). **FB-Task 3:** add a STEAL case to `build_final_ball_coords` (return the stealer's coord) so the snapshot the seed relies on is correct.

**Group C — contest-frame divergence (HIGH #2 + MED-HIGH #4 + MED #7):**
- **FB-Task 4:** make the drive-step contest/rebounder read the **rendered** `author_transition_end_coords` frame (not `defender_end_coords`/sampled spots); make Triangle spot-up contest read the rendered setup spots, not `player.coords`. The coord-consumer sibling on the FB drive step — needs care (two frames to unify).

**Capstone / deferred:** #8 rate mismatch + the transition-positioning snap verification → the reachability audit.

## Cross-turn note
FB is the counter-example on reachability (render safe by construction) but the worst on the *clock exit seam* (no reconciliation) and inherits the entry-seam gap ×4. Its #2/#4 contest-frame divergence is the coord-consumer defect resurfacing on the drive step; #8 is capstone-class.
