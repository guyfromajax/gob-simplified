# Coord-Source Registry (UESS §1 enforcement)

**The rule:** game *decision* logic reads player positions from the emitter's rendered step coords — never from `player.coords`, `_lineup_starts_by_pos()`, `_coord_of()`, a named spot, or an archetype re-derivation. One producer of "where everyone is," consumed by both render and logic.

## Which emitted coord a decision reads

Every decision reads **some emitted step's `end.coords`** — the only question is *which* step boundary its event sits at:

| Decision kind | Reads | = |
|---|---|---|
| **Race / process during a step** (cutoff, meet, drive, interception, loose ball) | that step's **start** | the **prior** step's `end.coords` |
| **State at a step's conclusion** (shot contest, foul, rebound, classification, a violation checked at the landing) | **that** step's `end.coords` | — |

When a step is single-purpose the boundary is obvious. When a step is **multi-phase** (moves players *and* has a mid-step event), or the event-time isn't clearly a boundary — **stop and ask**; do not guess.

## Decision → coord-boundary map (expand as turns migrate)

### Fast Break — RR / Triangle drive (settled 2026-07-07)
| Decision | Reads (emitted boundary) |
|---|---|
| Cutoff / meet race, `t_drive`/`t_meet` timing | drive-step **start** = lane-pass `end.coords` |
| NEUTRAL receiver pick + pass contest | **meet-moment** (meet sub-step `end`) |
| Pass-ahead contester | **ball-detach** (pass-flight step start) |
| Shot contest + shooting foul | drive-step **end** |
| Rebounder | post-shot **end** |

## Enforcement

**Guard:** [`scripts/check_coord_source.py`](../../scripts/check_coord_source.py) — greps the scoped decision modules for `_lineup_starts_by_pos(` / `_coord_of(` call sites and fails if the count exceeds the recorded `BASELINE` (a ratchet). Run: `python scripts/check_coord_source.py`. A legitimate render-consistent seed or infra line can be exempted inline with `# coord-source-ok: <reason>`.

**Migration:** convert each site to read the rendered coord (via the *emit-then-resolve* pattern — emit a step's movement, seed the next decision from its `end.coords`), annotate/remove the call, then **lower `BASELINE`** to lock the win.

**Status (2026-07-07): COMPLETE — baseline = 0.** Every FB decision now reads the emitter's coordinates: drive-start cutoff/meet seeds (RR/CR/AS), the NEUTRAL kick-out receiver (RR/CR/AS), the After-Steal pass-ahead decision, and the triangle-three contest (`apply_triangle_unified_contest` — seeded from the rendered setup-end defender positions `rr_defender_to`/`bh_defender_to`; the setup moves those two defenders, so their old `player.coords` seed drifted). Render-authoring and degenerate fallbacks are annotated `# coord-source-ok:` with precise reasons. The guard now fails CI on any NEW stale `player.coords`/`_lineup_starts_by_pos` seed in the scoped modules. **Behavior-shifting fixes to verify live (aggregated sims / prototype):** RR & CR drive-starts (defenders attempt cutoffs; one-time RNG reorder), NEUTRAL-receiver and triangle-three contests (rare). After-Steal drive-start + pass-ahead are proven zero-change.

**History (pre-completion): baseline was 7.** RR/Triangle, Covert Release, After-Steal **drive-start seeds** migrated, **the NEUTRAL-receiver pick in all three** (RR/CR/AS), **and the After-Steal pass-ahead decision** (`_find_open_pass_ahead` — the open-teammate/lane-interception check now reads the emitter's rendered drive-start snapshot; proven byte-identical to `player.coords` → zero behavior change, single-source by construction). Remaining 7 sites are **render-authoring** (After-Steal `_build_offense_end_coords`, transition-planner start coords) + degenerate **fallbacks** (bh_start, RR shooter/defender-end) + the `_lineup_starts_by_pos` helper body. The NEUTRAL-receiver pick now reads the receiver's **rendered meet-moment position** (`end_coords[recv_id]`, built at `t_meet`) — the same frame as the defenders in that contest — instead of his stale start-of-break `player.coords`. Verified: forced NEUTRAL→pass exercises the branch 15/15 with the receiver resolving in `end_coords`, no crash; naturally rare (0 in 22q) so low behavior-change risk. Remaining 9 sites: After-Steal render-authoring + pass-ahead + bh_start-fallback, RR/CR shooter/defender-end fallbacks, and the `_lineup_starts_by_pos` helper body (still imported by RR/CR annotated fallbacks). After-Steal was already divergence-0 at the drive-start (its `player.coords` seed happened to equal the emitter's `prior_turn.final_coords`); the migration makes that **structural** — the resolver now seeds `def_starts`/`off_starts` from `game.turns[-1].final_coords` (the exact source the emitter reads; at resolve time the after-steal turn isn't appended yet, so `turns[-1]` is the steal turn for both). Proven byte-identical to the old seed (0 mismatches → zero behavior change), now un-driftable. Remaining After-Steal sites are **separate concerns**: render-authoring (`_build_offense_end_coords`, transition-planner start coords), the pass-ahead open-teammate decision (`_find_open_pass_ahead`), and the NEUTRAL-receiver pick. RR/Triangle **and** Covert Release drives **migrated** (emit-then-resolve). Each: resolver builds the preamble once (RR: burst→outlet→lane-pass; CR: outlet), seeds `off_starts`/`def_starts`/`bh_start` from the rendered drive-start `end.coords`, stashes it in `roles["*_preamble_steps"]`; the emitter reuses the stash — single-source by construction. CR verified: def_starts vs rendered drive-start **0.000 (100% exact)**, stash 19/19, 1 build/drive, cutoff fires 68% vs prior 50%. RR verified: 5/5 stash, ~53% stopper vs ~44%. Next: **After-Steal** (`after_steal_drive_integration.py:758/760`) + each turn's NEUTRAL-receiver pick (`recv_coord = _lineup_starts_by_pos`). Target 0.

**Note — no-retreat clamp stays:** `after_steal_transition_positioning._no_retreat_end` is still load-bearing (fires ~85% of calls) — it patches `def_start_coords` inside `author_defense_end_coords`, which belongs to the **After-Steal** seed path, not the RR one. Remove it only when After-Steal migrates.

**Why this exists:** the whole "emitter as god" effort ([Emitter_As_God.md](../projects/Emitter_As_God.md)) is enforcing the rule above. We drifted because nothing flagged a stale `player.coords` seed. This registry + guard make the contract *explicit and checked*, per decision, so it can't silently drift again.
