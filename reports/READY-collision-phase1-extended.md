# READY — extension works on its metric, but the metric still is not what you see

Report: `reports/collision-phase1-extended.md`. `GOB_COLLISION_SEPARATION_ALL`, default OFF,
requires the base flag. Verified against the brief by Claude. Not merged.

## Gate — clean

240/240 both collision flags off, fp AND draws, 480/480 checks, 0 mismatches. Seed 8000 played
SD=1 = fp `0c3389cd41d0bbef` / draws `75363`. All three flag-on states produce DIFFERENT
fingerprints (so the code fired). **ALL=1 with base OFF is 8/8 byte-identical to flags-off**,
`enabled_calls=0`, warning logged once — not half-applied. Suite 3,646 passed / 0 failed.
Rule 6e footing throughout.

## ITEM 22 — CLEAN, proved by invariant not argument

**The shooter is exempt outright at every step**, identified from the authored `shoot` action in
the skeleton — play intent, not outcome, so clairvoyance holds.

```
SHOOTER VIOLATIONS: 0     (all four flag states, 80 games each)
```

If the shooter's coordinate is never written, no shot can be reclassified. And the aggregate
backs it: seed-paired at n=120, **3PA share +0.502 ± 1.073** and **3PT% +0.454 ± 2.010**, both
spanning zero. Worth noting the already-shipped base flag moves 3PA share MORE than the extension
does — what movement exists is the known consequence of moving defenders, not of touching offence.

## The headline, and the caveat that matters more

| | within 2.0 | vs flags-off |
|---|---|---|
| flags off | 1.5559% | — |
| base only (def-def) | 1.3670% | −12.1% |
| **base + ALL (ten players)** | **1.1050%** | **−29.0%** |
| base + ALL, authored pin off | 1.0144% | **−34.8%** |

**But within 5.25 — actual sprite width — moved 0.7%.** Steps containing any sub-3.0 overlap:
74.21% -> 73.69%.

The reason is arithmetic, not a bug: the separation target is
`COLLISION_OVERLAP_TOLERANCE x (r_a + r_b)` = ~2.62 grid, and a sprite is ~5.25 grid wide. **Two
players pushed to exactly the threshold are still overlapping by half a sprite.**

**This is the third metric in this arc, and it is still not the one Jamie sees.** Exact-cell was
2.7% of the visible problem. Within-2.0 is measurably better but still separates only to
half-sprite. The visible metric is sprite-width, and the only lever that reaches it is
`COLLISION_OVERLAP_TOLERANCE` raised toward 1.0 — a balance constant, deliberately out of scope,
and now clearly identified as **the actual decision**.

## Divergence ROSE against a must-not-rise condition

| | share | worst |
|---|---|---|
| flags off | 0.0221% | 16.84 |
| base only | 0.0207% | 16.76 |
| **base + ALL** | **0.0264%** | **19.56** |
| ALL, no authored pin | 0.0250% | 15.40 |

+32 placements in 677,585. The base flag alone still goes DOWN, so this is specifically the
ten-player extension. **Not write-ordering** — same insertion point as the base pass, which
measures clean through the same probe. Shape matches the reachability class already documented for
the Stage B switch: a player moved to a point he cannot reach within `rate x step_t`. The agent
did NOT attribute the 32 placements and says so plainly rather than guessing.

## A real defect it found in its own pass, mid-audit

Defender movement is **step-indexed**; offensive entries are matched by **timestamp** — and
**26.8% of defender movement lists repeat a timestamp** (sub-steps). The same offensive entry
could be selected at more than one index and written twice, applying the displacement cap twice:
**measured at 4.0 against a 2.0 cap.** Fixed with a one-write-per-entry guard, covered by a test,
and **every number in the report re-measured afterwards** (max displacement now 2.0). It was NOT
the cause of the divergence rise — 0.0266% before the fix, 0.0264% after.

## Residual worse, as predicted — and where the crowding actually lives

49.14% (base) -> **66.55%** (ten players). Three times the overlapping pairs in one capped
relaxation. Caps NOT tuned, per the brief.

**def-off is 60% of the residual** — 93,282 of 155,446. That is the class the base flag could not
touch at all, and it is where the crowding is.

## Recommendation: DROP the authored-location pin

Measured both ways, and it is better on **every** axis:

| | within 2.0 | off placements moved | residual | divergence |
|---|---|---|---|---|
| pin ON | −29.0% | 27,632 | 66.55% | 0.0264% |
| **pin OFF** | **−34.8%** | 90,536 | **58.49%** | **0.0250%** |

The reasoning is sound: a defender on his man is executing coverage against an opponent; an
offensive player on his authored spot is sitting at a **static table coordinate the coincidence
audit already showed is shared by design** (73.9% of the O-C/O-PF stack is one named spot).
Pinning it protects exactly the coordinate that causes the crowding — and it is the largest pin
at 49%.

The agent left the default at `True` (conservative) rather than changing behaviour on its own
recommendation. Correct call. Flipping is one line with the measurement already in hand.

## Exemptions chosen

Shooter (17% of pins, Item 22). Ball handler on any ball action — handle/receive/pass/drive/shoot
— because the brief required proof of inertness and the agent could not show it, so pinned (19%).
Existing defender pin kept (6%). Offensive players with no writable entry at that timestamp are
treated as obstacles rather than written to the wrong beat (7%).

## Outcomes — nothing clears

n=120 seed-paired, both states. Closest is OREB at −0.82 ± 0.89, which does not cross. Nothing
retuned.

## Claude's read

Agree with the agent: **do not flip yet.** Two measured reasons — divergence rose against an
explicit condition, and the visible overlap barely moved.

But the arc has produced a clear answer: **the visible overlap problem is governed by one
constant.** At `COLLISION_OVERLAP_TOLERANCE = 0.5` the pass separates to half-sprite, which is
invisible. Reaching what a viewer sees means moving it toward 1.0. That is a balance decision and
it is Jamie's tuning call — everything up to here has been measurement to find it.

No merge by Claude. Jamie merges.
