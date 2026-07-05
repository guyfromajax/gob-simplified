# Free Throw (FT) — UESS Compliance Audit

**Verdict: largely compliant — the cleanest turn since SIP.** Clock is paused correctly (as clean as SIP), §1 is compliant in effect, and the lane formation is a properly gated/reachable rendered transition. Two parity gaps (backfill all-10 + `[UESS SEAM]` detector) + a couple of LOW nits. (2026-07-05, 4-dimension parallel trace.) **Sim-verifiable** (the mock produces FTs from fouls).

## Topline
- **§5 clock:** ✅ **Compliant — as clean as SIP.** Game clock PAUSED (double-protected: `no_impact_types` + `_pin_ft_clock` freezes every step); shot clock held during the sequence, reset to 30 on possession change at the correct location (UCP, next turn). Multi-FT + seams clean.
- **§1 coord-source:** ✅ **Compliant in effect.** Only real coord decision (missed-last-FT rebounder) measures `player.coords` = byte-identical to the rendered lane coords; bounce spot genuinely shared. Shooter/1-and-1/scoring assignment-based.
- **§8.1-8.3 player-coord:** ✅ Mostly clean — lane move is a gated, reachable, rendered transition; step seams literal; §8.3 clean (emitter lane cfg == legacy cfg == `player.coords`). **One backfill teleport (edge).**
- **§8.4 ball-seam:** ✅ Internal / multi-FT / miss-exit clean. Entry seed gap (mitigated) + no detector.

## Findings (ranked)

| # | Sev | Dim | Finding | Location |
|---|---|---|---|---|
| 1 | **MED-HIGH** | §8.2 | **Backfill gap → center-court teleport.** FT backfills **only the shooter**, not the other 9. A prior-turn-dropped player (None coords) is dropped from every step, then inserted at the default `{50,25}` in the terminal step → teleport. FT never got the standardized `_backfill_missing_active_coords` (HCO/SIP/HCT/FCP have it). Edge-triggered (build_final_coords normally carries all 10) but real + undetected. | ft_step_emitter.py:637-641; terminal :862-868 |
| 2 | MED | §8.4/§8.2 | **No `[UESS SEAM]` entry detector** at the FT callsite. FT is now the only emitter-driven entry turn without one → #1 (+ any regression) is silent. SIP-Task 2 parity. | turn_manager.py:1627-1637 |
| 3 | MED | §8.4 | **Entry ball not seeded from `final_ball_coords`** — step-0 attaches the ball to the shooter's body (no coord seed), so the rim/net→shooter relocation is unrendered. **Mitigated:** a FT legitimately re-spots the ball at the line (ref handoff), so it's semantically valid, just not rendered as a handoff. | ft_step_emitter.py:684-689 |
| 4 | LOW-MED | control-flow | **Made-final FT terminates on a dangling `next` index** (`{"kind":"next_step","index":<out-of-range>}`) instead of `turn_stop`; miss/airball paths correctly use `_implicit_turn_end_next`. Exit *coords* are clean; the terminal *contract* is inconsistent on the common (make) path. | ft_step_emitter.py:743-767 |
| 5 | LOW / latent | §1 | **FT lane config is duplicated, not shared** — `animator.py:598-632` (`HOME/AWAY_CFG`) is byte-identical to `ft_step_emitter.py:61-96` (`_FT_HOME/AWAY_CFG`). Synced today; rebounder-vs-render silently diverges if one is edited without the other. Worth a shared-source guard/test. | animator.py:598 vs ft_step_emitter.py:61 |
| 6 | LOW | §5 | Per-step `end.time_elapsed` non-zero vs pinned zero-delta clock (same as SIP #6). Harmless — turn-level `time_elapsed=0` is authoritative. | ft_step_emitter.py:245/309/384 |
| — | LOW | §8.4 | `ft_return_teleport` (rim→shooter, T=0) between multi-FT attempts — intentional dead-ball ref-retrieval, acceptable by design. | ft_step_emitter.py:389-427 |

## Clean (verified)
- **§5:** game clock zero-burn (no-impact + pin), shot-clock held + reset-30 at correct location, multi-FT + entry/exit seams — mirrors SIP.
- **§1:** rebounder + bounce render-synced (byte-identical tables + shared `_ft_last_bounce_spot`); shooter/scoring assignment-based.
- **§8.1/§8.3:** step seams literal; lane formation gated (all-10) + reachable + rendered (not a raw snap); logic==render (identical cfg); exit seam continuous.
- **§8.4:** per-FT internal seams, multi-FT continuity, missed-final exit (covered by DREB/OREB detectors).

## Work plan (small)
**Group A — parity fixes:**
- ✅ **FT-Task 1 (MED-HIGH #1) — DONE (2026-07-05).** Applied `_backfill_missing_active_coords` to the FT setup `start_coords` (all 10, not just the shooter) — mirrors HCT-Task 1. **Defensive fix:** the dropped-player→`{50,25}` teleport doesn't trigger in normal sim (`build_final_coords` carries all 10), so this guards the edge without changing common-case behavior (verified: FT count + `{50,25}` count unchanged, regression-clean). Closes the standardized-backfill parity gap FT was missing.
- ❌ **FT-Task 2 (MED #2) — determined NOT APPLICABLE to FT.** A `[UESS SEAM]` *ball* detector compares prior `final_ball_coords` vs the emitted step-0 ball. For FT that **always** diverges by design — the ball is legitimately re-spotted from the rim/net to the shooter (ref handoff), so the detector would fire on *every* FT (pure noise) and wouldn't catch the real issue (#1 was a *player* teleport, fixed by FT-Task 1). FT's ball entry is semantically a handoff, not a continuity seam — so the sibling ball-detector pattern doesn't transfer. (If a guard is ever wanted, it'd be a *player*-coord regression check on the backfill, not a ball-seam detector.)

**Lower priority / optional:**
- **#4:** give the made-final FT a proper `turn_stop` terminal (`_implicit_turn_end_next`), matching the miss path. Control-flow tidy.
- **#5:** collapse the duplicated FT lane config to a single shared source (or add a test asserting they're equal) — prevents latent drift.
- **#3** (entry ball-seed): optional — render the ref handoff (seed ball at prior rest → travel to shooter). Cosmetic; low value.

## Capstone flag
#1's dropped-player `{50,25}` teleport is a **reachability** case (a player placed where he can't be) — feeds the no-teleport-by-construction capstone; the FT-Task 1 backfill is the local fix.
