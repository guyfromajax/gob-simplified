# Zone sink escape — the empty-area defender may leave his zone

**Yes, he sits closer to the basket.** The perimeter-class defender — the one in Jamie's complaint —
goes from **16.31 to 14.60** grid units from the rim on the mean (p50 15.94 → 13.88, p90 22.04 →
18.32) and now stands outside his own polygon **83.5 %** of the time.

**What is still holding him out is the reach cap, not the clamp.** 58.2 % of perimeter placements are
still capped by `reach_perimeter`, and lifting it — measured, **not shipped** — would take him a
further **1.69** closer, to 12.92. The escape and the reach constant are almost exactly the same size
of lever.

Behind `GOB_ZONE_SINK_ESCAPE`, **default `"0"`. Not flipped, not re-cut, not merged.** No reach
constant and no sink weight was touched. `GOB_BOXOUT_CONTEST` still `"0"`, `crash_destination.py`
untouched.

---

## 1. The change

When `_clamp_into` would pull him back, he keeps the part of the movement that **reduces his distance
to the rim**. Movement that is not rim-ward is still clamped and the old behaviour stands. Only the
empty-area sink path; a zone defender with a man in his area is untouched.

### The two guardrails, derived from measured geometry

| guardrail | value | derivation |
|---|---|---|
| **`RIM_FLOOR`** | **4.0** | the rim→`basketSpot` distance — the nearest **named** on-court spot an offensive player can occupy. `HCO_STRING_SPOTS["basketSpot"]` (87,25) vs `HOME_RIM_COORDS` (91,25) = **exactly 4.00**. A defender should never stand closer to the basket than a man standing at the basket. The sink's own observed minimum today is **4.03** over 235k placements, so it does not bind on anything the sink does now — it only bounds the new, deeper positions. |
| **`MIN_SEPARATION`** | **2.0** | the **5th percentile** of today's nearest-other-defender distance on zone turns (p5 = 1.41 home offense / 2.00 away, 235k placements). It permits essentially everything the current geometry already does and only stops the escape from creating a tighter overlap than the game already tolerates. |

**A guardrail that binds is itself a clamp and is counted as one.** Per game, sim SD=1:

| counter | /game | note |
|---|---|---|
| `clamp_would_bind` | 3,660 | the polygon clamp had something to pull back |
| `escaped` | **2,551** (69.7 %) | he ended up outside his polygon |
| `not_rim_ward` | 1,109 (30.3 %) | the discarded movement was not rim-ward → still clamped |
| `rim_floor_bound` | **11** | guardrail 1 stopped him |
| `separation_bound` | **37** | guardrail 2 stopped him |
| `escape_nulled` | 0 | a guardrail never walked him all the way back |

**The guardrails bind on 48 of 2,551 escapes — 1.9 %.** They are bounds, not shapers. The minimum rim
distance actually reached is **4.00**, exactly the floor.

### Plumbing note

The separation guardrail needs the defenders already placed at that step, which the per-defender
`assign_zone_defender_coords` cannot see. `placed_defenders` is threaded from both callers —
`assign_all_zone_defenders` (`assignments`) and `position_zone_defenders` (`step_coords`, unflipped to
the HOME contract). The render path's existing collision pass only splits **exact** (x, y) ties, so it
does not subsume a minimum separation. **This was caught by the flag on its first run**, as a
`NameError` — the sink call lives in the per-defender function, not the orchestrator I first assumed.

## 2. Gates

| gate | result |
|---|---|
| **flag OFF vs `equiv_v3_reference_5cc98ee3e_freeze.json`** | **40/40 fingerprint AND draws in all four cells**, every escape counter **0**, 0 errors |
| **freeze-miss** | see §3 — **not resolvably changed** |
| **same-moment gate** | **100.000 %** identical both ways (71,325 / 70,735 pairs) |
| **§8.1 coord-continuity corrections** | **0** both ways (182.2 / 179.7 guard calls/game) |
| **suite** | **3151 passed, 20 skipped, 112 xfailed, 0 failed, 0 XPASS** — flag OFF *and* ON |
| errors | **0** across 720 games |

### Freeze-miss — stated precisely rather than waved through

The brief set "must not rise (2.20/game sim SD=1)". It reads **2.48** with the flag on. Paired per
seed it is **+0.275 ± 0.530 — within CI**, and the played arm moves the same distance the other way
(**1.85 → 1.57, −0.275 ± 0.525**). Equal and opposite is the signature of noise, not a regression, and
**no new consumer or reason category appears** (still `shot_contest_defender_selection` +
`_hco_step_def_xy`, still `stamped_empty` + `appended_after_last_stamp`). I am reporting it as
unchanged-within-noise, not as "did not rise".

## 3. By role class (brief item 1)

sim SD=1, n=20 games, 135,922 empty-area placements with the flag on.

| class | share | **distance to RIM** OFF → ON (mean / p50 / p90) | to BALL | **leaves polygon** | outside by (mean/p50/p90/max) | reach still binding |
|---|---|---|---|---|---|---|
| **perimeter** | 8.9 % | **16.31 → 14.60** / 15.94 → 13.88 / 22.04 → **18.32** | 13.35 → 12.84 | **83.5 %** | 2.36 / 2.28 / 5.76 / 7.47 | **58.2 %** (was 57.0 %) |
| spanning | 62.5 % | 13.51 → 12.77 / 13.48 → 13.07 / 17.04 → 16.49 | 16.52 → 15.66 | 45.5 % | 1.78 / 1.69 / 2.89 / 4.13 | 40.5 % (was 43.0 %) |
| interior | 28.6 % | 8.64 → 8.49 / 8.76 → 8.71 / 11.14 → 11.14 | 15.97 → 16.00 | 11.2 % | 0.44 / 0.30 / 0.99 / 1.54 | 16.9 % (was 14.2 %) |
| **all** | | **12.37 → 11.71** (0.66 closer) | | **39.1 %** | 1.78 / 1.68 / 3.22 / **7.47** | |

## 4. Does it answer #1? (brief item 2)

**Yes for the perimeter class, and the effect is real rather than cosmetic** — 1.71 units on the mean,
2.06 at the median, **3.72 at p90**, with 83.5 % of those defenders now standing outside their zone,
which is exactly the licence Jamie granted.

**But reach is now the binding constraint.** It bound on 57.0 % of perimeter placements before and
**58.2 % after** — the escape removed the clamp and handed the job straight to the cap. Measured with
the cap lifted (**reported, not shipped**; `sink_position` draws no randomness, so this recompute
needs no RNG isolation and consumes none):

| class | escape (shipped) | + reach cap lifted | a further… |
|---|---|---|---|
| **perimeter** | 14.60 | **12.92** | **1.69 closer** |
| spanning | 12.77 | 11.58 | 1.19 closer |
| interior | 8.49 | 8.45 | 0.04 closer |
| all | 11.71 | 10.80 | 0.91 closer |

**The chain for the perimeter defender:** 16.31 clamped in his zone → **14.60** with the escape →
**12.92** with the reach cap lifted. The two levers are the same size. `reach_perimeter` is Jamie's
tuning pass; it was not touched.

## 5. Blast radius (brief item 3)

| | |
|---|---|
| empty-area placements the escape moved | 53,554 = **39.4 %** |
| of those, crossing the 11-unit contest radius vs the ball | 2,566 = **4.79 %** |
| …of which **into** contest range | 2,368 (92.3 %) |
| as a share of **all** empty-area placements | **1.89 %** |
| movement when it moves | mean 2.19, p50 2.17, p90 3.30, max 7.47 |

Proxy stated: distance to the **ball handler**, the same proxy as
`reports/offball-ball-read-2026-09-21.md` §5. The interception/bat geometry reads the same stamped
rows, so it moves with this.

## 6. Outcomes (brief item 4)

**`SEED_DEFENSES=0` is provably inert** — every metric Δ is **exactly 0.00 ± 0.00** on both arms.
Zone does not exist there, so the escape cannot fire; a good structural check that the flag touches
only what it claims.

**n=40, both arms, SD=1, paired per seed.** Everything within CI except interceptions, which
"resolves" in **opposite directions on the two arms**: sim **−0.62 ± 0.62**, played **+0.75 ± 0.64**.
Two boundary crossings with opposite signs out of ~40 comparisons is noise, and the n=120 run below
confirms it.

**n=120, sim arm SD=1, seeds 8000–8119, seed-paired. Nothing resolves:**

| metric | OFF | ON | paired Δ |
|---|---|---|---|
| pts/team | 73.72 | 74.45 | +0.738 ± 1.494 |
| FG% | 40.15 | 40.12 | −0.026 ± 0.954 |
| possessions | 40.53 | 40.46 | −0.075 ± 1.194 |
| interceptions | 3.75 | 3.43 | −0.317 ± 0.375 |
| **shots INSIDE (paint)** | 30.31 | 30.02 | **−0.292 ± 1.142** |
| shots ATTACK (drive) | 34.15 | 34.75 | +0.600 ± 1.151 |
| shots OUTSIDE | 35.90 | 35.70 | −0.200 ± 1.024 |
| **inside share %** | 30.21 | 29.90 | −0.313 ± 1.030 |

**The box score does carry shot location** — `turn_payload["shot_type"]` is `inside` / `attack` /
`outside`, covering ~100 of ~105 shots a game — so rim/paint shots are reported rather than skipped.
They do not move.

**Plainly: the change is geometrically real and outcome-neutral at n=120.** A defender sitting 1.7
units deeper does not, on this evidence, change what the box score says.

## 7. CPU (brief item 5)

`GOB_SIM_PROFILE=1`, sim SD=1, seeds 8000–8019, **interleaved per seed and run sequentially**.

| | wall / game | placement self |
|---|---|---|
| escape OFF | 4.969 ± 0.470 s | 0.840 s/game |
| escape ON | 4.706 ± 0.380 s | 0.883 s/game |
| **paired Δ** | **−0.263 ± 0.527 s = −5.30 % (within CI)** | **+0.042 ± 0.041 s — RESOLVED** |

**Negligible, as expected.** The placement cost rises ~5 % of itself — about **0.9 % of a sim** — from
the extra walk-backs and the separation scan. Total wall does not resolve. Nothing here argues against
the flip.

## 8. Pictures (brief item 6 — the main deliverable)

| file | class |
|---|---|
| `zone-escape-perimeter-2026-09-21.png` | perimeter — Jamie's complaint |
| `zone-escape-spanning-2026-09-21.png` | spanning |
| `zone-escape-interior-2026-09-21.png` | interior |

Each panel shows **his own zone** (darker polygon), **the other four zones** (pale), the **RIM_FLOOR**
as a dashed red circle, the other four defenders (grey), offence (blue), the ball (black), and the
move from **OFF (hollow red)** to **ON (green)**.

**Both positions come from one run**, not from two diverged games: `_clamp_into`'s return is the
flag-OFF position and `sink_position`'s return is the escaped one, so the step is identical.
Restricted to **home offense**, where the zone frame and the home frame coincide and nothing in the
drawing needs flipping. Steps picked at the **median escape distance** and forced apart so the four
panels are four different possessions, not four frames of one.

## 9. Footing

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
CI = 1.96 × SEM. **Catalogue-seeded state: `SEED_DEFENSES=1` for every measurement in §3–§8 — zone
only exists there**; the SD=0 cells in §2 and §6 are the inertness check. Gate 160 games, outcomes
320, n=120 extension 240, geometry 40, CPU 40, same-moment 20, §8.1 24. **0 errors throughout.**

All probes read frame locals under `sys.monitoring` and draw no RNG; the reach-lever recompute calls
`sink_position`, which draws none by construction.

## 10. Not done

- **Not flipped, not re-cut, not merged.**
- **No reach constant or sink weight touched** — §4 prices the reach lever, it does not pull it.
- **Out of scope, unchanged:** the zone defender *with* a man in his area still has no basket shade
  (`reports/offball-ball-read-2026-09-21.md` §4 side find). Separate item.
- **No test added** for the escape. The shipped default is `"0"`, so there is no new default to guard
  yet; the guard belongs with the flip.
- **The played arm was not run at n=120**, so its n=40 interception crossing stays formally open —
  though the sim n=120 result and the opposite sign make noise the obvious reading.

## 11. Tunable constants

**Nothing was retuned.** New knobs and the ones §4 prices:

| constant | where | value | note |
|---|---|---|---|
| `GOB_ZONE_SINK_ESCAPE` | `zone_sink.py` | **`"0"`** | this stage |
| `RIM_FLOOR` | `zone_sink.py` | `4.0` | derived (§1); binds 11×/game |
| `MIN_SEPARATION` | `zone_sink.py` | `2.0` | derived (§1); binds 37×/game |
| `reach_perimeter` / `reach_spanning` / `reach_interior` | `zone_sink.py:102` | `8.0` / `7.0` / `5.0` | **now the binding constraint** (§4) — untouched |
| `basket_weak` / `basket_strong` | `zone_sink.py:102` | `0.75` / `0.15` | already rim-hungry — untouched |
| `CONTEST_EUCLIDEAN_RADIUS` | `constants/__init__.py:364` | `11` | §5 |
