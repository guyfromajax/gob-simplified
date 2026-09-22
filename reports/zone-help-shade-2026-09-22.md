# Zone help shade — the weak-side defender now sags to the basket

**Yes. The weak-side zone defender guarding a man in his area goes from 13.83 to 11.74 grid units from
the rim — 2.09 closer — and moves rim-ward on 91.4 % of his placements.** The strong-side defender is
barely touched (−0.60) and a defender with the ball in the middle is not touched at all, which is the
point: the shade is scaled by how weak-side he is.

Behind `GOB_ZONE_HELP_SHADE`, **default `"0"`. Not flipped, not re-cut, not merged.** No new constant
was invented — it reuses `HELP_BASKET_SHADE` and the zone sink's own strong/weak ramp.

---

## 0. Sync and verification

`develop` merged (fast-forward to **`9a307eb11`**). Its 7 commits touch only `BackEnd/persistence/` —
nothing on the sim path. **`equiv_v3_reference_5ea94694f_sinkescape.json` still reproduces 40/40 on
fingerprint AND draws in all four cells**, 0 errors.

## 1. Part A — the path, confirmed

`shared_defense.py` `calculate_defender_coords`: `ball_spot` is `None` on **100 %** of these calls, so
the `"key"` branch always runs, and that branch has **no basket term at all**. The only basket shade
in the codebase is in `_apply_defender_posture`, which the zone path never calls.

Measured at the current tree, sim SD=1, n=20 games, **8,690 zone-with-a-man placements per game**:

| side | share | to MAN (mean/p50/p90) | to BALL | to RIM |
|---|---|---|---|---|
| **weak** | **53.7 %** | **11.14** / 11.00 / 15.13 | 16.97 / 16.14 / 24.52 | 14.02 / 14.14 / 24.04 |
| middle | 29.7 % | 6.82 / 7.07 / 10.00 | 19.45 / 20.40 / 29.15 | 12.67 / 12.00 / 21.54 |
| strong | 16.6 % | 5.31 / 4.47 / 9.22 | 14.92 / 15.00 / 22.36 | 13.66 / 15.03 / 18.68 |

*Side is read from the midline: strong = his man is on the ball's side of `y=25`; middle = the ball is
within 3 of the midline.*

**The weak-side defender is the problem, and the strong-side one is fine.** He sits **more than twice
as far from his man** (11.14 vs 5.31) and no closer to the rim for it (14.02 vs 13.66) — he is drifting
laterally, not helping.

### The two counterfactuals, and why the brief's simpler one still over-applies

RNG-isolated (CF-A draws the posture jitter; CF-B draws nothing), unclamped:

| side | CF-A **full man-normal help**: rim / man | CF-B **flat basket shade**: rim / man | moves rim-ward, A vs B |
|---|---|---|---|
| weak | 14.02 → 12.44 (−1.58) / 11.14 → **9.46** | 14.02 → 11.08 (−2.94) / 11.14 → 14.10 | 60.5 % vs **91.0 %** |
| middle | 12.67 → 12.03 (−0.64) / 6.82 → 6.21 | 12.67 → 9.71 (−2.96) / 6.82 → 9.33 | 46.2 % vs 97.4 % |
| strong | 13.66 → 12.60 (−1.06) / 5.31 → 4.93 | 13.66 → 10.61 (−3.04) / 5.31 → **7.86** | 58.6 % vs 98.7 % |

**CF-A is the wrong tool.** It pulls him *closer to his man* (11.14 → 9.46) and only moves him rim-ward
about half the time, because `HELP_ANCHOR_FLOOR` exists precisely to hold a man-defender to his
assignment. Its movement also has a 36.06 tail.

**CF-B does the job but over-applies**: it drags the strong-side defender 3.04 units off his area too,
and in a zone the strong-side defender should pressure his area rather than sag off it. **The brief
invited the scoping** — "if the strong-side defender is already fine… scope the fix to the weak side
only" — so the shipped form is CF-B **scaled by how weak-side he is**, using the sink's own ramp. A
hard on/off at the midline was rejected because it would teleport a man drifting across the middle.

## 2. What was built

```python
strongness = 1 - min(1, |ball_y - man_y| / SIDE_SPAN)      # the zone sink's own measure
strongness += (1 - strongness) * ball_centrality(ball_y)    # ball in the middle -> no weak side
coords += HELP_BASKET_SHADE * (1 - strongness) * (rim - man)
```

Two existing constants, no new ones: **`HELP_BASKET_SHADE` = 0.20** for the magnitude, **`SIDE_SPAN`**
and **`ball_centrality`** from `zone_sink` for the weighting. Applied at the two non-ball-handler
return sites in `assign_zone_defender_coords`. The empty-area sink, man defense and the on-ball
defender are untouched.

### The clamp the brief asked for does not exist, and adding it would work against the fix

The brief said "he stays clamped to his own zone polygon… count how often the clamp binds". **There is
no clamp on this path today** — the clamp lives only in the sink. Measured:

| | |
|---|---|
| placements already **outside** his own polygon today | **58.9 %** |
| their mean rim distance | **11.66** |
| mean rim distance of the ones **inside** | **16.29** |
| movement a clamp alone would cause, with zero shade | **2.54** units on that 58.9 % |

**The defenders already outside their zone are the ones already nearest the rim.** Introducing a clamp
would push exactly the right defenders back out, and would move 58.9 % of placements before any shade
was applied. **Not built. Reported.** After the shade he is outside his polygon 70.3 % of the time —
that is the shade working, not a regression.

## 3. Gates

| gate | result |
|---|---|
| **flag OFF vs `equiv_v3_reference_5ea94694f_sinkescape.json`** | **40/40 fingerprint AND draws, all four cells**, 0 errors |
| same-moment gate | **100.000 %** identical both ways (85,085 / 83,365 pairs) |
| §8.1 corrections | **0** both ways |
| suite | **3166 passed, 0 failed, 0 XPASS** — flag OFF *and* ON |
| errors | **0** across 800 games |

### Freeze-miss — one arm's delta resolves, and I am not hiding it

| cell | OFF | ON | paired Δ |
|---|---|---|---|
| sim SD=1 | 2.48 | **2.02** | −0.450 ± 0.620 (within CI) |
| **played SD=1** | 1.57 | **2.27** | **+0.700 ± 0.571 — RESOLVED** |
| sim / played SD=0 | 0.38 / 0.28 | unchanged | **exactly 0.000 ± 0.000** |

The brief's bar was "within noise of ~2.2–2.5/game sim SD=1"; sim SD=1 reads **2.02**, slightly *below*
the band. The played arm rises 0.70 and that delta **does** resolve at n=40 — it lands at 2.27, still
inside the stated band, and no new consumer or reason category appears. **Worth Jamie's eye before a
flip**, and not something I would call a pass without saying so.

## 4. The shade, measured inside one run

Hooked on the shade itself, so before and after are the same placement rather than two diverged games.
n=20 games, **8,277 calls/game**:

| side | share | mean strongness | distance to RIM | moves rim-ward | to MAN | movement (mean / p90) |
|---|---|---|---|---|---|---|
| **weak** | 53.4 % | 0.274 | **13.83 → 11.74 (−2.09)** | **91.4 %** | 11.06 → 13.19 | 2.81 / 4.69 |
| middle | 29.5 % | 1.000 | 12.51 → 12.51 (0.00) | 0.3 % | 6.75 → 6.75 | **0.00** |
| strong | 17.1 % | 0.807 | 13.77 → 13.17 (−0.60) | 95.4 % | 5.32 → 5.81 | 0.64 / 1.19 |

Overall movement mean **1.61**, p90 3.85, **max 5.10** — bounded, because the shade is 20 % of the
man→rim vector. **30.0 % of calls are untouched** (the ball is central, so by the sink's own rule there
is no weak side).

This matches the Part A prediction for the shipped form almost exactly (**predicted −2.11, measured
−2.09** on the weak side), which is the cross-check that the implementation is the thing that was
designed.

**A measurement error I caught before reporting:** my first attempt hooked `get_defender_coords`, which
returns *before* the shade is applied. It showed the weak side moving −0.19 and would have said "the
shade does nothing". It was reading the pre-shade value.

## 5. Blast radius

| | |
|---|---|
| placements the shade moved | 115,867 = **70.0 %** |
| of those, crossing the 11-unit contest radius vs the ball | 5,968 = **5.15 %** |
| as a share of all zone-with-man placements | **3.61 %** |

Proxy stated: distance to the ball handler, as in the two prior reports. The interception/bat geometry
reads the same stamped rows, so it moves with this.

## 6. Outcomes

**`SEED_DEFENSES=0` is exactly inert** — every metric Δ is **0.00 ± 0.00** on both arms. Zone does not
exist there.

**n=40, both arms, SD=1**: everything within CI except **interceptions on the sim arm, +0.93 ± 0.83
(RESOLVED)**.

**n=120, sim SD=1, seeds 8000–8119, seed-paired — that does not hold, and nothing else resolves:**

| metric | OFF | ON | paired Δ |
|---|---|---|---|
| **interceptions** | 3.43 | 3.55 | **+0.117 ± 0.520** |
| pts/team | 74.45 | 75.30 | +0.842 ± 1.900 |
| FG% | 40.12 | 40.91 | +0.790 ± 1.197 |
| possessions | 40.46 | 40.68 | +0.225 ± 1.457 |
| shots INSIDE (paint) | 30.02 | 29.38 | −0.633 ± 1.261 |
| shots ATTACK (drive) | 34.75 | 34.12 | −0.625 ± 1.274 |
| shots OUTSIDE | 35.70 | 36.74 | +1.042 ± 1.164 |
| inside share % | 29.90 | 29.31 | −0.589 ± 1.161 |

**Plainly: nothing resolves at n=120.** The shot mix drifts in the direction you would expect from
defenders sagging off the perimeter — fewer paint and drive attempts, more outside — but every one of
those is inside its interval and I am not going to call it.

## 7. CPU

`GOB_SIM_PROFILE=1`, sim SD=1, seeds 8000–8019, interleaved per seed, run sequentially.

| | wall / game | placement self |
|---|---|---|
| shade OFF | 5.292 ± 0.530 s | 1.005 s/game |
| shade ON | 5.087 ± 0.326 s | 0.988 s/game |
| paired Δ | −0.205 ± 0.563 s = **−3.87 % (within CI)** | −0.016 ± 0.078 s (within CI) |

**Free.** Neither measure resolves; the shade is a handful of arithmetic per placement.

## 8. Pictures

| file | what |
|---|---|
| `zone-help-shade-weakside-2026-09-22.png` | the weak side — the case that was broken |
| `zone-help-shade-strongside-2026-09-22.png` | the strong side — scaled almost to nothing, by design |

Hollow red = OFF, green = ON, green arrow = the shade; the bold blue ring is **the man he is
guarding** with a dotted line to him; grey = the other four defenders; zones shaded; black = ball; the
dotted horizontal line is the midline the side is read from.

**Both positions come from one run** (the shade's own input and return), so the step is identical.
Home offense only, where the zone frame and the home frame coincide. Steps are ranked by closeness to
the **median** shade distance, then filtered so no two panels share a zone-shell + rim-distance +
strongness signature — **without that filter all four panels came out as clones of the modal case**,
which is what the first render produced. All three shells appear.

## 9. Footing

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
CI = 1.96 × SEM. **Catalogue-seeded state: `SEED_DEFENSES=1` for every geometry measurement — zone only
exists there**; the SD=0 cells are the inertness check. 800 games: 160 post-merge verification, 160
gate, 160 flag-on, 160 n=120 extension, 40 geometry, 40 CPU, 24 same-moment, 24 §8.1. **0 errors.**

All probes read frame locals under `sys.monitoring`; CF-A ran on an isolated `random.Random` with
`shared_defense.random` swapped and restored, and CF-B and the shade itself draw nothing.

## 10. Not done

- **Not flipped, not re-cut, not merged.**
- **No clamp introduced** (§2) — it would work against the fix. Reported with its measured size.
- **No constant retuned.** If zone wants a different shade strength than man's 0.20, that is Jamie's
  tuning pass; it ships with the existing value.
- **No test added** — the shipped default is `"0"`, so there is no new default to guard; that belongs
  with the flip.
- **The played-arm freeze-miss rise** (§3) is measured and flagged, not explained.
- **The played arm was not run at n=120.**

## 11. Tunable constants

**Nothing was retuned.**

| constant | where | value | role |
|---|---|---|---|
| `GOB_ZONE_HELP_SHADE` | `shared_defense.py` | **`"0"`** | this stage |
| `HELP_BASKET_SHADE` | `shared_defense.py:1939` | `0.20` | **reused** — the shade magnitude |
| `SIDE_SPAN` | `zone_sink.py:64` | `30.0` | **reused** — the strong/weak ramp |
| `CENTRALITY_PLATEAU` / `CENTRALITY_OUTER` | `zone_sink.py:71–72` | `(23,28)` / `(18,33)` | **reused** — "ball in the middle, no weak side" |
| `HELP_SAG` / `HELP_ANCHOR_FLOOR` | `shared_defense.py:1937,1940` | `0.30` / `0.30` | **not used** — they are what made CF-A wrong |
| `CONTEST_EUCLIDEAN_RADIUS` | `constants/__init__.py:364` | `11` | §5 |
