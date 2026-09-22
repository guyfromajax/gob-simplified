# Zone Defender Placement vs Man Postures

**Status: TABLED** — logged 2026-09-19 for a later step in the animation work plan. No code changes yet.
**Source:** code read of `BackEnd/utils/shared_defense.py` on develop. Not measured — numbers below are what the code says, not observed frequencies.

## Question (Jamie)
What is standard on-ball and off-ball placement for zone defense compared to man base, man deny and man loose? Suspicion: our normal zone placement looks similar to man deny.

## Standard basketball

| Scheme | On-ball | Off-ball |
|---|---|---|
| Man deny | Tight, pressure the dribble | One pass away: in the passing lane, denying the catch |
| Man base | Arm's length | One foot in the gap, see man and ball |
| Man loose / pack line | Cushion, keep ball in front | Sag to the paint, help first |
| Zone | Pressure the ball when it enters your area | Guard your area, take away gaps, **don't deny**; weak side sinks hard toward the rim |

Zone off-ball belongs at the **loose** end of the spectrum, not the deny end.

## What our code does

Man postures (`get_defender_coords` :1987 → `_apply_defender_posture`, constants :1909–1929):

| Posture | On-ball distance | Off-ball rule |
|---|---|---|
| tight (deny) | 2.5 | 2.0 off man, ball side (`POSTURE_DENY_DISTANCE`) |
| normal (base) | 3.5 | 30% of man→ball + 20% of man→basket (`HELP_SAG` 0.30, `HELP_BASKET_SHADE` 0.20, jitter 0.10) |
| loose | 4.5 | 55% of man→ball + 20% of man→basket |

Zone: the zone path never passes `posture`, so it always gets **legacy placement**:

| | Zone (legacy) |
|---|---|
| On-ball | `get_spacing` (:1579) BH = 2 / 3 / 4 by aggression (aggressive / normal / passive) |
| Off-ball (main case, ~:1800–1908) | `def = man + 0.5 × (ball − man)` → ~50% toward ball, **no basket shade** |
| Off-ball (some cases) | `def_y = oy + randint(3,5)`, `def_x = bx`; post spots `ox ± 2`; corner-ball cases 0.1 sag with fixed y offset 4–5 |
| Off-ball (default fallback) | `get_spacing(aggression, False)` → **1–3 units off the man** (deny-tight) |

## Conclusions
1. **Zone off-ball depth ≈ man loose** (50% vs 55% toward ball) — so mostly not deny. But it stays on the man–ball line instead of dropping toward the lane, because there is no basket shade.
2. **Zone on-ball aggressive (2.0) is tighter than man deny (2.5).** Normal (3.0) sits between deny and base.
3. **The default fallback branch is deny-tight** (1–3 off the man). How often it fires is unknown — if it's common, Jamie's "zone looks like deny" read is correct for those turns.
4. **Inconsistent with the empty-zone sink:** empty-zone defenders get rim pull (weak side rim-hungry, ~0.75 to rim), but zone defenders guarding a man get zero basket pull. Weak-side zone defenders guarding a man should sink harder than they do.

## Proposed fix (when un-tabled)
- Give zone off-ball placement a basket shade like man loose (≥ `HELP_BASKET_SHADE` 0.20), stronger on the weak side.
- Reuse the sink's side logic (defender's side from his anchor; middle band y 23–28; continuous, no teleporting) so zone-with-man and zone-empty behave as one system.
- Keep the zone clamp: placement stays inside the defender's zone polygon.
- Decide on-ball zone distances vs man postures (should aggressive zone be tighter than deny?).

## Measure first
- How often each legacy off-ball branch fires in zone turns (esp. the 1–3 unit fallback), n=40 seeds, rule 6e stamped.
- Mean distance to man / to ball / to rim for zone off-ball defenders vs man-loose, strong vs weak side.
- Interaction with the overlap rung (rung 0, ~38.8% of turns) and the sink.
- Balance impact reported, not retuned (tune once at the end).
