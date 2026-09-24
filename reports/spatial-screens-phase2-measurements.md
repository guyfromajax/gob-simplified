# Collision Phase 2 — the three missing measurements, and the proximity cap

Completes `reports/spatial-screens-phase2.md`; does not redo it. Branch
`feature/animation-reward`. Stage A `98a9f5a79`, Stage B `7fc0948f0`, both still default OFF
and unchanged here. New: `GOB_SCREEN_PROXIMITY_CAP`, **default OFF**, on its own flag.

**Rule 6e footing** (every number): worker `scratch_equiv3_fbdedupe.py`, Lancaster vs
Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one
game per process, `SEED_DEFENSES=1`, `GOB_DEFENDER_AG_SPREAD` unset (ON),
`GOB_COLLISION_SEPARATION` unset (OFF), `GOB_STRICT_EXCEPTIONS=1` on all flag-on runs,
CI = 1.96 × SEM. Probes are the **existing** `bcensus.py` and `ovcensus.py`, imported
byte-identical from the directories that produced the Stage 2, flip, overlap-audit and
Phase 1 numbers; `stats()` is copied verbatim from the cell that produced the Phase 1 n=120
baseline. No measurement machinery was rebuilt.

---

## Gate — re-run because the cap adds code

| | result |
|---|---|
| all three flags off, 240 cells | **240/240**, fingerprint AND draws, 480/480 checks, **0 mismatches** |
| seed 8000 played SD=1 | fp `0c3389cd41d0bbef`, draws `75363` ✓ |
| cap ON, targeting OFF (80 cells, both arms) | **80/80 byte-identical to all-flags-off**, and divergence identical to the baseline at 147/666,385 |
| suite | **3,632 passed** / 20 skipped / 110 xfailed / **0 failed** |

The cap is unreachable with Stage A off — the applier returns before the cap is consulted.
Confirmed by measurement, not only by the unit test.

---

# PART 1

## 1A. Exact-coincidence stacks — **the stack did not collapse. It barely moved, and the coincidence relocated.**

Footing identical to the overlap audit: n=40 seeds 8000–8039, **both arms**, SD=1.

### Total exact coincidences

| state | total | vs off | off-off | def-def | def-off |
|---|---|---|---|---|---|
| all off | 28,377 | — | 13,757 | 7,932 | 6,688 |
| targeting | 28,225 | **−0.5%** | 13,958 | 8,019 | 6,248 |
| targeting + contest | 28,130 | **−0.9%** | 14,193 | 7,815 | 6,122 |
| targeting + cap | 28,223 | **−0.5%** | 13,565 | 8,062 | 6,596 |

### The stacks themselves, ranked by the all-off baseline

| pair | all off | targeting | +contest | +cap | targeting vs off |
|---|---|---|---|---|---|
| **off-off O-C / O-PF** | **3,501** | **3,489** | 3,430 | 3,523 | **−0.3%** |
| def-def D-PG / D-SG | 2,661 | 2,559 | 2,605 | 2,670 | −3.8% |
| def-off D-PG / O-PG | 2,628 | 2,466 | 2,384 | 2,544 | −6.2% |
| **off-off O-PF / O-SF** | **2,241** | **2,601** | **2,854** | 2,469 | **+16.1%** |
| off-off O-C / O-SG | 2,209 | 2,248 | 2,149 | 2,168 | +1.8% |
| off-off O-PG / O-SF | 1,938 | 1,953 | 2,169 | 1,950 | +0.8% |
| def-def D-C / D-PF | 1,652 | 1,721 | 1,733 | 1,635 | +4.2% |
| def-def D-PG / D-SF | 1,615 | 1,700 | 1,606 | 1,720 | +5.3% |
| off-off O-C / O-SF | 1,141 | 1,144 | 1,125 | 1,091 | +0.3% |
| off-off O-C / O-PG | 1,071 | 1,078 | 1,105 | 981 | +0.7% |
| off-off O-PG / O-SG | 943 | 982 | 1,035 | 952 | +4.1% |
| def-off D-PF / O-PF | 865 | 852 | 703 | 879 | −1.5% |

### Stated plainly

**It did not collapse. It did not meaningfully shrink. It relocated.**

- O-C/O-PF moves **−0.3%** with targeting on. That is nothing.
- Total exact coincidence moves **−0.5%**.
- **off-off coincidence goes UP** — 13,757 → 13,958 with targeting, → 14,193 with contest.
- The relocation is concrete and large: **O-PF/O-SF +16.1%** with targeting and **+27.4%**
  with contest. Stage A moved coincidence from one offensive pair onto another.
- The only real reductions are on pairs Stage A never touches: def-off D-PG/O-PG (−6.2%) and
  def-def D-PG/D-SG (−3.8%), both downstream ripples.

### Why — the mechanism, measured

Screens, by the role pair they actually involve (36,779 derived screens, same footing):

| screen pair | n | share |
|---|---|---|
| O-PF / O-SF | 8,085 | **22.0%** |
| O-PG / O-SF | 5,530 | 15.0% |
| O-C / O-SG | 5,175 | 14.1% |
| **O-C / O-PF** | 4,906 | **13.3%** |
| O-PG / O-SG | 3,900 | 10.6% |

**O-C/O-PF is only the fourth most common screen pair**, yet it is the largest coincidence
stack. The most-screened pair, O-PF/O-SF, has a far smaller baseline stack — and is the one
that got *worse*. So the overlap audit's inference that the O-C/O-PF stack is *created by the
screen script* (audit line 542) is **not supported**: retargeting 54% of screens moves that
stack by 0.3%. The two bigs are standing in the same cell for reasons other than screening.

**This contradicts the premise Phase 2 was built on.** Stage A does not solve the overlap
problem, and the cap does not either.

### One discrepancy against the audit

My all-flags-off baseline is **3,501**, not the audit's 3,367 (+4.0%), on 222,188 steps /
10,040,944 pairs vs the audit's 221,037 / 9,988,199. The audit was cut at a different code
state (before the `GOB_DEFENDER_AG_SPREAD` default flip, `f600628a4`). **3,501 is the right
number for this HEAD**, and every comparison above is internal to this run, so the conclusion
does not depend on which baseline is used.

---

## 1B. Screen-vs-game divergence — **it rose for targeting + contest**

Same metric and same code (`bcensus.py`). Per the brief this leads, so it is diagnosed below
rather than just reported.

| state | checked | over tolerance | share | worst |
|---|---|---|---|---|
| all off | 666,385 | 147 | **0.0221%** | 16.84 |
| targeting | 666,453 | 148 | **0.0222%** | 19.40 |
| **targeting + contest** | 666,437 | **180** | **0.0270%** | **20.92** |
| targeting + contest, detour disabled | 665,883 | 170 | 0.0255% | 20.92 |
| targeting + cap | 667,635 | 144 | **0.0216%** | **16.84** |
| cap on, targeting off | 666,385 | 147 | 0.0221% | 16.84 |

The all-off row reproduces the established baseline **exactly** (147 / 666,385 / 0.0221%),
which validates the harness before anything is concluded from it.

### It is NOT something writing after the freeze stamp

The brief's hypothesis does not survive the evidence:

- **Stage A alone is flat** (148 vs 147, one placement in 666,385). Stage A moves the screener
  a median 9.5 grid in the same post-pass. If that pass wrote after the freeze stamp, Stage A
  alone would have produced an enormous divergence. It produces one extra placement.
- **Cap on, targeting off is byte-identical** to the baseline on every figure.
- **Targeting + cap is BELOW baseline** (0.0216%) with the worst case back to exactly 16.84.

### What it actually is

I isolated it by replacing Stage B's GO AROUND displacement with a no-op in the harness
(`_detour` draws no RNG, so the arms stay comparable). Divergence fell only **180 → 170**, and
the worst case did not move at all.

So roughly **one third** of the rise is the GO AROUND detour and **two thirds is the SWITCH**,
and the worst single divergence is entirely a switch effect. Both are the same class: a
defender is asked to reach a point further away than `rate × step_t` allows. A switch genuinely
reassigns him to a different man mid-possession, and the next placement puts that man's
position in front of him without giving him time to get there.

That is a real Stage B finding — **the reachability class, feeding the planned
no-teleport capstone** — not a write-ordering bug. Scale: **+33 placements in 666,437**
(0.0049%). Not retuned, per the brief.

---

## 1C. Outcomes at n=120 — seed-paired

Played arm, SD=1, seeds 8000–8119, CI = 1.96 × SEM **of the per-seed difference**.

**The all-flags-off n=120 baseline was reused, not re-run** — `out120` from the Phase 1 report.
Validity was not assumed: a fresh all-flags-off run at this HEAD is **byte-identical on
fingerprint AND draws for 120/120 seeds**.

| metric | baseline | targeting only | targeting + contest | targeting + cap |
|---|---|---|---|---|
| points/team | 73.37 | +0.48 ± 1.10 | +1.68 ± 1.98 | +0.71 ± 1.00 |
| FG% | 40.58 | +0.16 ± 0.64 | **+1.66 ± 1.37** | −0.07 ± 0.65 |
| fouls | 31.70 | +0.09 ± 0.80 | +0.32 ± 1.36 | +0.43 ± 0.77 |
| OREB | 14.76 | +0.04 ± 0.53 | −0.30 ± 0.87 | +0.06 ± 0.49 |
| DREB | 43.09 | −0.26 ± 0.75 | −0.78 ± 1.29 | +0.01 ± 0.69 |
| blocks | 10.06 | −0.11 ± 0.44 | **−0.68 ± 0.68** | +0.09 ± 0.38 |
| steals | 16.55 | +0.05 ± 0.50 | −0.51 ± 0.98 | +0.12 ± 0.38 |
| possessions | 39.70 | −0.43 ± 0.77 | −0.88 ± 1.28 | +0.01 ± 0.72 |

**CI excludes zero in two places, both for targeting + contest: FG% +1.66 and blocks −0.68.**
Directionally coherent — screens create cleaner looks, so the offence shoots better and gets
blocked less. Nothing else moves, in any state. **Not retuned.**

Honest caveat: two flagged metrics out of eight at 95% is close to what multiple comparisons
alone would produce (expected ≈ 0.4). FG% is a 2.4σ effect and is the one I would believe;
blocks at 2.0σ is marginal.

### This corrects `spatial-screens-phase2.md`

That report said *"Every delta is inside CI. Neither stage moves scoring."* At n=120 that is
**wrong for Stage B**. The cause is sample size, not method: the same seed-paired test on the
same 40 seeds gives FG% **+0.64 ± 2.08** — the effect was there and the run was underpowered.
**The n=120 figures above are the right ones.**

(The report's own n=40 comparison also used independent CIs of two means rather than paired
differences, which is strictly less sensitive; the paired form is used throughout here.)

Strict mode changed nothing: the targeting+contest run with `GOB_STRICT_EXCEPTIONS=1`
reproduces the report's run (strict unset) **40/40** on fingerprint and draws.

---

# PART 2 — the proximity cap

`GOB_SCREEN_PROXIMITY_CAP`, **default OFF**, its own flag, additive, not folded into Stage A.

Distance is the house's existing derived gate, `pass_contest.PASS_LANE_DIST = 8.0` — the same
"close enough to contest" radius `boxout_contest` already reused after deriving the identical
number independently. Resolved at call time through the module, never inlined (a test fails if
it is). **No new tuning number, and this one is not tuned.**

**It refuses, it does not clamp.** A targeted point further than the gate from the receiver
falls back to today's `OFFSET_SPOTS` placement and is counted. A clamped point would sit on
neither the defender (so it screens nobody) nor near the receiver (so it is not his screen) —
a third position that is not a screen at all. Declining beats inventing one.

## 2A. Screener → receiver

| state | p25 | p50 | p75 | p90 | max |
|---|---|---|---|---|---|
| all off | 3.0 | 4.0 | 4.0 | 4.0 | 4.0 |
| targeting (uncapped) | 4.0 | 6.0 | 14.0 | **17.0** | **23.5** |
| **targeting + cap** | 3.0 | **4.0** | **4.0** | **6.0** | **8.0** |

The cap does exactly what it is for: **max 8.0, the gate itself**. No screen is ever further
from its receiver than the house's contest radius. The uncapped tail — p90 17.0, max 23.5 —
is gone.

## 2B. Screener → receiver's defender — **the number that decides the trade**

| state | p25 | p50 | p75 | p90 |
|---|---|---|---|---|
| all off | 6.0 | 8.0 | 12.0 | 13.0 |
| targeting (uncapped) | 2.5 | **2.5** | 3.0 | 8.0 |
| targeting + cap | **2.5** | 7.0 | 12.0 | 13.5 |

**Read this carefully — the p50 of 7.0 is not a degraded screen.** These distributions cover
*every* screen including the ones that fall back, and the cap halves how many are placed. On
the screens the cap **accepts**, the screener lands on the **identical point** as uncapped —
the contact distance, 2.62 — which is why p25 stays at 2.5 and is pinned by a test
(`test_a_nearby_defender_is_unaffected_by_the_cap`). The median rises because the untouched
fallbacks now dominate the sample, not because any screen got worse.

**The cap does not destroy the benefit. It reduces how often the benefit is delivered.**

## 2C. How much the cap refuses

| | screens | Stage A applied | refused by the cap |
|---|---|---|---|
| targeting | 41,731 | 22,574 (**54.1%**) | — |
| targeting + cap | 41,296 | 11,234 (**27.2%**) | **11,116** |

The cap refuses **49.7%** of the screens Stage A would otherwise place, halving Stage A's reach
from 54.1% to **27.2%** of all screens. Full fallback breakdown with the cap on:

| reason | n |
|---|---|
| cap: too far from the receiver | 11,116 |
| zone: no defender assigned to the receiver | 8,441 |
| receiver not heading anywhere next | 5,693 |
| no teammate on the screener's spot | 4,812 |

## 2D. Screener displacement

| state | p25 | p50 | p75 | p90 | max |
|---|---|---|---|---|---|
| targeting (uncapped) | 5.0 | 9.5 | 12.0 | 14.5 | **19.5** |
| **targeting + cap** | 3.0 | **5.5** | 8.0 | **9.5** | **11.0** |

The teleport tail is cut hard: max 19.5 → **11.0**. This is the same concern as the planned
no-teleport capstone, and the cap is the only thing in Phase 2 that improves it.

---

## Recommendation

**Cap ON — but do not flip Stage A yet.**

The cap is strictly better than no cap, on every axis measured, with no offsetting cost:

- caps screener → receiver at exactly the house gate (max 8.0 vs 23.5);
- cuts the teleport tail (displacement max 19.5 → 11.0);
- returns worst-case divergence to the baseline 16.84 and drives the share **below** baseline
  (0.0216% vs 0.0221%);
- every n=120 outcome flat, nothing excluding zero;
- accepted screens are **bit-identical** to uncapped — it only ever refuses.

The cost is reach: 54.1% → 27.2%. That is a real cost and it is why "cap on" is not the same
as "ship it".

**Neither state is good enough to flip Stage A, because the phase's stated goal is not met.**
Phase 2 was motivated by the overlap audit and the 3,367 O-C/O-PF stack. Measured: that stack
moves **−0.3%**, total coincidence **−0.5%**, and off-off coincidence **rises**. The screen
script is not what creates that stack — O-C/O-PF is only 13.3% of screens. Flipping Stage A
would buy a large geometric change, a measurable FG% shift once Stage B is on, and a small
divergence rise, in exchange for none of the thing it was built to fix.

What I would do next, in order:

1. **Find what actually creates the O-C/O-PF stack.** It is not screens. Until that is known,
   Phase 2 cannot be judged against its own goal.
2. **Take the Stage B switch reachability item** (+23 placements beyond `rate × step_t`) into
   the no-teleport capstone rather than patching it here.
3. Keep all three flags off meanwhile. Nothing here is a regression; it is simply not yet a win.

---

## Anything that did not behave as expected

- **Divergence rose for targeting + contest** (0.0221% → 0.0270%). Diagnosed above: switch
  reassignment, not write ordering. This was the brief's STOP condition; it is reported ahead
  of everything else and the ordering hypothesis is refuted with evidence, not asserted.
- **The headline stack did not collapse.** I expected the screen retarget to cut O-C/O-PF
  substantially. It moved 0.3%.
- **Coincidence relocated upward** onto O-PF/O-SF (+16.1% / +27.4%), which is the *most*
  screened pair. I do not have a mechanism for the direction of that and am not going to invent
  one; it is measured, reproducible across both arms, and worth its own look.
- **Stage B moves FG%**, which the n=40 report concluded it did not. n=120 is the right answer.
- The census probe did not propagate `cap_refused` into its accumulator, so 2C's refusal count
  is read from the `cap_too_far_from_receiver` fallback counter, which is authoritative and
  unaffected. The probe has been fixed for future runs; **no number in this report changes.**

## Tunable Constants

| Constant | Value | Effect |
|---|---|---|
| `GOB_SCREEN_PROXIMITY_CAP` | **off** | Refuse a targeted screen further than the gate from its receiver. Unreachable when `GOB_SCREEN_TARGETING` is off. |
| cap distance | *derived* | `pass_contest.PASS_LANE_DIST` = 8.0, resolved at call time. Not a knob, and out of scope to tune. |
| `GOB_SCREEN_TARGETING` | off | Stage A, unchanged. |
| `GOB_SCREEN_CONTEST` | off | Stage B, unchanged. |

Nothing was tuned. Jamie tunes once, at the end. Nothing merged.
