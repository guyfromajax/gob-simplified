# READY — Phase 2 measurements: the premise was wrong. Stack did not collapse.

Report: `reports/spatial-screens-phase2-measurements.md`. Verified against the follow-up brief by
Claude. New flag `GOB_SCREEN_PROXIMITY_CAP`, default OFF. Stage A `98a9f5a79` / Stage B
`7fc0948f0` unchanged.

## Gate — clean, re-run because the cap adds code

240/240 all three flags off, fingerprint AND draws, 480/480 checks, 0 mismatches. Seed 8000
played SD=1 = fp `0c3389cd41d0bbef`, draws `75363`. Cap ON with targeting OFF is **80/80
byte-identical** to all-flags-off, confirmed by measurement not just by unit test. Suite 3,632
passed / 0 failed. Rule 6e footing throughout; probes imported byte-identical from the
directories that produced the earlier numbers — no measurement machinery rebuilt.

## 1A — THE HEADLINE: it did not collapse, it RELOCATED

| | all off | targeting | +contest |
|---|---|---|---|
| **O-C/O-PF stack** | 3,501 | 3,489 (**-0.3%**) | 3,430 |
| total exact coincidences | 28,377 | 28,225 (-0.5%) | 28,130 (-0.9%) |
| **off-off coincidences** | 13,757 | 13,958 (**UP**) | 14,193 (**UP**) |
| **O-PF/O-SF stack** | 2,241 | 2,601 (**+16.1%**) | 2,854 (**+27.4%**) |

**The premise Phase 2 was built on is contradicted.** The overlap audit inferred the O-C/O-PF
stack was CREATED by the screen script sending the screener to the receiver's own named
`location`. Measured: **O-C/O-PF is only the FOURTH most common screen pair (13.3%)**, and
retargeting 54% of screens moves that stack by 0.3%. The most-screened pair is O-PF/O-SF (22.0%)
— and that is the one that got WORSE.

The two bigs are standing in the same cell for reasons other than screening. Claude carried the
audit's causal inference forward as established fact in several briefs and readouts; it is wrong,
and it shaped this whole phase.

Only real reductions are on pairs Stage A never touches — def-off D-PG/O-PG -6.2%, def-def
D-PG/D-SG -3.8% — downstream ripples.

**Baseline discrepancy, correctly flagged:** all-off baseline here is **3,501**, not the audit's
3,367 (+4.0%), because the audit was cut before the AG-spread default flip (`f600628a4`). 3,501
is right for this HEAD; all comparisons are internal to this run so the conclusion holds either
way.

## 1B — divergence ROSE, but NOT from write ordering

| state | share | worst |
|---|---|---|
| all off | 0.0221% (147/666,385) | 16.84 |
| targeting | 0.0222% (148) | 19.40 |
| **targeting + contest** | **0.0270% (180)** | **20.92** |
| targeting + cap | **0.0216% (144)** | 16.84 |
| cap on, targeting off | 0.0221% (147) | 16.84 |

The all-off row reproduces the established baseline exactly, validating the harness first.

**The brief's STOP hypothesis is refuted with evidence, not asserted.** Stage A alone moves
screeners a median 9.5 grid units in the same post-pass and produces ONE extra diverging
placement — if that pass wrote after the freeze stamp, Stage A alone would have exploded.
Cap-on/targeting-off is byte-identical. Targeting+cap is BELOW baseline.

Isolated by replacing Stage B's GO AROUND displacement with a no-op (`_detour` draws no RNG, so
arms stay comparable): divergence fell only 180 -> 170 and the worst case did not move. So ~1/3
detour, **~2/3 SWITCH**, and the worst single case is entirely a switch effect.

Cause: a switched defender is reassigned mid-possession and the next placement puts his new man's
position in front of him without time to get there — `rate x step_t` exceeded. **Reachability
class, feeds the no-teleport capstone.** Scale +33 placements in 666,437 (0.0049%). Not retuned.

## 1C — n=120 CORRECTS the earlier report

All-flags-off n=120 baseline reused from Phase 1, and validity PROVEN not assumed: a fresh
all-flags-off run at this HEAD is byte-identical on fingerprint AND draws for 120/120 seeds.

**Two metrics exclude zero, both for targeting + contest:**
- **FG% +1.66 ± 1.37** (2.4 sigma)
- **blocks -0.68 ± 0.68** (2.0 sigma, marginal)

Directionally coherent — real screens create cleaner looks, so the offence shoots better and gets
blocked less. Everything else flat in every state.

**This corrects `spatial-screens-phase2.md`, which said "neither stage moves scoring."** At n=40
the same paired test gives FG% +0.64 ± 2.08 — the effect was there and the run was underpowered.
The earlier report also used independent CIs of two means rather than paired differences, which is
strictly less sensitive. **The n=120 figures are the right ones.**

Agent's own caveat kept: 2 of 8 flagged at 95% against ~0.4 expected from multiplicity alone; it
believes FG% and calls blocks marginal.

## 2 — the cap is strictly better, and only ever refuses

Uses the existing derived `pass_contest.PASS_LANE_DIST = 8.0`, resolved at call time, test-pinned
against inlining. **It REFUSES rather than clamps** — a clamped point would sit on neither the
defender nor the receiver, which is not a screen at all.

| | uncapped | capped |
|---|---|---|
| screener -> receiver p90 / max | 17.0 / 23.5 | **6.0 / 8.0** |
| screener displacement p50 / max | 9.5 / 19.5 | **5.5 / 11.0** |
| divergence | 0.0222% | **0.0216%** (below baseline) |
| outcomes at n=120 | — | all flat, nothing excludes zero |
| Stage A reach | 54.1% | **27.2%** (refuses 49.7%) |

**The 2B p50 of 7.0 is not a degraded screen** — the distribution includes fallbacks, and the cap
halves how many screens are placed. On screens the cap ACCEPTS the screener lands on the
identical point as uncapped (contact distance 2.62), which is why p25 stays 2.5 and is pinned by
`test_a_nearby_defender_is_unaffected_by_the_cap`. The cap does not destroy the benefit; it
reduces how often it is delivered.

## Recommendation — Claude agrees with the agent

**Cap ON. Do NOT flip Stage A yet.**

The cap is better on every measured axis with no offsetting cost, and accepted screens are
bit-identical to uncapped. But flipping Stage A would buy a large geometric change, a real FG%
shift once Stage B is on, and a small divergence rise — in exchange for **none of the thing the
phase was built to fix**.

Next, in order:
1. **Find what actually creates the O-C/O-PF stack.** It is not screens. Until that is known,
   Phase 2 cannot be judged against its own goal.
2. Take the Stage B switch reachability item into the no-teleport capstone rather than patching
   it here.
3. Keep all three flags off meanwhile. Nothing here is a regression — it is simply not yet a win.

Separately, for the tuning pass: Stage B making the offence shoot +1.66% better is arguably
correct basketball (a real screen should help the offence), but it is a balance decision, not a
bug, and it is Jamie's call.

## Honest housekeeping from the agent

The census probe did not propagate `cap_refused` into its accumulator, so 2C's refusal count is
read from the authoritative `cap_too_far_from_receiver` fallback counter. Probe fixed for future
runs; **no number in the report changes.** It also has no mechanism for WHY coincidence relocated
upward onto O-PF/O-SF and declined to invent one — measured, reproducible across both arms,
flagged for its own look.

Nothing tuned. Nothing merged. Stage 3 defects, Phase 1 constants, SCRA/SCRS,
`calculate_screen_score` all untouched. No illegal-screen foul built. No offensive separation. No
frontend change.

No merge by Claude. Jamie merges.
