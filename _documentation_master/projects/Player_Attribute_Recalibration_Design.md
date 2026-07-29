# Player Attribute Recalibration — Design

**Status:** Draft for review, 2026-07-29
**Scope:** New franchises only. In-flight alpha saves are not migrated.
**Repo path:** `_documentation_master/projects/Player_Attribute_Recalibration_Design.md`
**Companion to:** the project brief at `_documentation_master/projects/Player_Attribute_Recalibration.md` and the audit at `_documentation_master/projects/rt_sanity_audit/`

---

## 1. What this project actually is

The original framing was "recalibrate the numbers." The code says otherwise: **there is no player progression model to recalibrate.**

What exists today is three forces fighting with no designed outcome —

- a weekly decay treadmill applied to every trainable attribute (`apply_pre_training_conditions`, FR `randint(-5,-2)` down to SR `(-2,0)`),
- a concentrated weekly training spend (24 points, with untrained attributes taking a further `(-2,-1)`),
- a Week 1 Training Camp bonus (30 points, CH-tiered bonus, year-bonus roll, HT/WT growth for FR/SO only),

and **no offseason step at all** — `complete_season_transition` copies `attributes` and `position_ratings` forward verbatim and bumps `meta.year`.

Career growth is an emergent side effect of that collision. This document specifies a growth model to replace it.

---

## 2. Measured baseline

From the RT sanity audit (`_documentation_master/projects/rt_sanity_audit/`), 1,920 rostered players, ratings freshly recomputed.

**Median top RT by class year:**

| | FR | SO | JR | SR |
|---|---|---|---|---|
| p50 | 24 | 50 | 54 | 54 |
| p90 | 73 | 76 | 79 | 80 |

All growth happens in one transition. FR→SO is +26; SO→JR is +4; **JR→SR is zero.** Development stops after sophomore year.

**Class sizes:** SR 621, FR 479, JR 456, SO 364 (even would be ~480 each). Seniors are 32% of the league.

**Freshman distribution is bimodal:** p10 16, p25 19, p50 24, p75 57, p90 73.

**Argmax position distribution:** SG 27.1%, PG 23.6%, PF 23.0%, SF 15.4%, C 10.9%. Median height by argmax: PG 70, SG 71, SF 71, PF 73, C 79.

**Position identity is weak:** 32.2% of players have an RT margin under 3; 47.3% under 5; 8.0% have exact top-rating ties.

**League RT:** p10 18, p50 50, p90 78, max 100. Exactly one player has any RT ≥ 100.

### 2.1 What the baseline tells us

- **The season-1-to-season-2 dropoff is structural, not a tuning problem.** A third of the league graduates each year and is replaced by freshmen at a median RT of 24. No progression curve fixes that; class balance has to be fixed in roster generation.
- **The freshman bimodality is a generation artifact**, the same shape as the already-flagged SH spike at 88-105. Two populations are being stapled together.
- **Centers are undersupplied** at 1.6 per roster, while PF is overstuffed with wings.

---

## 3. Prerequisite: the RT formula fix

RT is the calibration metric for everything below, so it has to mean something stable before any anchor is committed.

### 3.1 What the audit confirmed

- **H2 confirmed.** `_pf_height_to_rating` returns 75 for every height ≥ 76 inches, at a weight of 0.10. Height contributes between 0 and 7.5 points to a PF rating across the entire human range. A 6'4" wing and a 7'0" center receive identical PF height credit. Correlation between height and PF RT among 76-84 inch players is r = 0.14.
- **H3 confirmed.** Recruit and player weight tables differ at PF and C. Median absolute C change is 7 RT, p90 is 15 RT, and 15.7% of recruits change argmax position between profiles. Rollover copies recruit-profile ratings into the signed player's FPD record, so the discontinuity lands at the next recomputation.
- **H1 refined.** The mush is not PF vs C — the 40% C height weight separates centers cleanly (C p10 77 inches vs PF median 73). The mush is **PF vs SF**, two inches apart with near-total overlap.

### 3.2 The structural problem

**Additive weights cannot gate a requirement.** In a weighted mean of positive terms, failing a criterion means forgoing its points; it can never disqualify. Height at 10% of PF means a short player with strong RB/ST/ID still rates 87 there.

### 3.3 Specification

**Make height a multiplier for the big positions, not a weighted term.**

```
RT_PF = attribute_weighted_mean × pf_height_fitness(height)
RT_C  = attribute_weighted_mean × c_height_fitness(height)
```

- `pf_height_fitness` is **non-monotonic** — peaks around 78-81 inches, falls off below (too small) and above (that's a center).
- `c_height_fitness` is **monotonic** — rises to ~84 and plateaus.

That asymmetry separates the two positions structurally instead of by fighting over shared attributes.

**Attribute-side differentiation:**

- **Give PF meaningful AG weight; keep C at zero.** AG is currently 0.00 for both, which is the largest missed differentiator in the table. PF = the athletic big who runs and faces up. C = the immobile anchor.
- **Split ID and RB.** Push C toward ID (rim protection), PF toward RB. Both currently carry ID at 0.15, so neither owns interior defense.

**Rebuild the SF vector.** SF is currently the *athlete* position, not the versatile wing: `AG .25 + ST .25` is half the rating, and SF needs six attributes to cover 80% of its weight — the widest of the five vectors (PG, SG and C need four; PF needs five). A skilled wing with modest strength forfeits a quarter of his rating before anything else is counted, which is why SF is only 15.4% of argmax and why athletic-but-unskilled players cluster at SF and PF while skilled wings have nowhere to land.

Rebuild SF around SH, SC, ID and OD carrying the weight, with AG as the athletic requirement and **ST dropped substantially**. Raw physicality belongs at PF. This narrows the vector, sharpens identity per §14, and creates real separation from PF.

**Unify the recruit and player weight tables.** Delete `RECRUIT_POSITION_WEIGHTS`, `RECRUIT_PF_WEIGHTS_SHORT`, `RECRUIT_C_WEIGHTS_SHORT`, and the `profile` parameter. A player's RT must not change at signing without development having occurred — the entire ladder below depends on RT continuity from JH to SR.

### 3.4 Acceptance criteria

**These are evaluated against the regenerated population from §11.2, not the current one.** Prototyping showed the current height distribution cannot support them under any weight table; the formula and the generator have to be fitted together.

- Argmax distribution within roughly 5 points of even across all five positions (target ~20% each; C currently 10.9%).
- PF-argmax and SF-argmax height distributions visibly separated — at least 3 inches of median difference with reduced p10-p90 overlap.
- Correlation of height with PF RT materially above the current r = 0.14 in the 76-84 inch band.
- Zero RT change for any recruit when computed under the unified table versus the player table.
- Exact-tie rate materially below 8.0%.

### 3.5 Related, needs its own diagnostic

Freshly computed ratings disagree with **stored** ratings for 1,794 of 1,920 players and 163 of 300 recruits. Stored RT is what the UI shows, what lineups read, what `primary_position_from_position_ratings` uses to select training-camp core attributes, and what CPU roster logic keys off.

Diagnostic: for the mismatched set, recompute three ways — player weights on anchor attributes, player weights on live (NG-scaled) attributes, recruit weights on anchor attributes — and see which matches the stored value. If it's the live-attribute variant, RT drifts with fatigue and that must be fixed before RT can anchor a four-season calibration.

### 3.6 Fitted values

Fitted jointly with the §11.2 generator against a synthesized 1,920-player population. Six iterations; the breakthrough was §3.6.3.

#### 3.6.1 Weight vectors

| | PG | SG | SF | PF | C |
|---|---|---|---|---|---|
| SC | — | .11 | .18 | .08 | .18 |
| SH | .05 | **.42** | .14 | .14 | — |
| ID | — | — | .16 | — | **.32** |
| OD | .10 | .25 | .20 | — | — |
| PS | .15 | .05 | — | — | — |
| BH | **.30** | — | — | — | — |
| RB | — | — | .05 | **.30** | .22 |
| ST | — | — | — | .22 | .20 |
| AG | .10 | .07 | **.22** | .16 | — |
| IQ | .25 | .05 | — | .05 | .04 |
| FT | .05 | .05 | .05 | .05 | .04 |

#### 3.6.2 Height fitness

Multiplicative, piecewise-linear, floor 0.50, cap 1.15. Penalty per inch away from ideal, asymmetric:

| | ideal | short penalty /in | tall penalty /in |
|---|---|---|---|
| PG | 73.5 | .020 | .050 |
| SG | 76.0 | .030 | .045 |
| SF | 78.5 | .035 | .035 |
| PF | 80.5 | .050 | .025 |
| C | 82.5 | .060 | .010 |

Every position carries a curve, not just the bigs. Applying fitness only to PF and C leaves guards ungated at every height, which was what collapsed centre supply in the earlier iterations.

#### 3.6.3 The PF/C separation

**PF and C previously shared four of their five weighted attributes** (RB, ST, ID, SC). No weight tuning separates positions that measure the same things — this is why the height cap looked like the only available lever.

The fix is signature attributes each position's neighbour ignores:

- **PF = the mobile, stretch big.** AG .16 and SH .14 — a four who runs and shoots. Carries no ID.
- **C = the rim-protecting anchor.** ID .32, the largest single weight at any position. Carries no AG and no SH.

C's intent match went from 77.6% to 100% on this change alone.

#### 3.6.4 Measured results

| Criterion | Current | Fitted | Target |
|---|---|---|---|
| argmax PG / SG / SF / PF / C | 23.6 / 27.1 / 15.3 / 23.0 / **10.9** | 19.9 / 21.9 / 18.2 / 18.6 / **21.5** | within 5 of 20 |
| median height by argmax | 70 / 71 / 71 / 73 / 79 | 73 / 76 / 79 / 80 / 83 | monotonic |
| margin < 3 | 32.3% | **11.2%** | materially lower |
| margin < 5 | 47.3% | 22.5% | materially lower |
| exact ties | 8.1% | **2.5%** | well below 8% |
| argmax matches intent | n/a | 95.3% | — |

Ladder alignment on the same population:

| | FR | SO | JR | SR |
|---|---|---|---|---|
| fitted p50 | 35 | 43 | 53 | 61 |
| designed | 35 | 43 | 54 | 60 |

Senior RT by tier — fitted vs designed: Poor 39/40, Below Average 49/50, Average 61/60, Good 70/70, Great 79/80, Elite 105/100.

**Above-100 rate accepted at 5.5%.** Players with any attribute ≥ 100 come out at 5.5% rather than the original 3% target. Accepted as-is — no recalibration of the spike constants required. The 3% figure in §12 is superseded by this measurement.

**Elite seniors land at p50 105 before peaks are applied.** With peak stacking to 2.6x on top, this confirms the §4.3 compression above RT 95 is required rather than optional.

---

## 4. The class-year ladder

### 4.1 Entry tiers

**JH RT is drawn from a single right-skewed distribution. Tiers are labels on bands of it, not separate generation paths.** The 2x is anchored to the **JH rung of the ladder**, not to an individual's entry value — recruits who enter as FR, SO, or JR are slotted into the scale at their year and walk the remaining rungs.

| Tier | JH RT | SR RT (1 peak) | Share of generated players |
|---|---|---|---|
| Poor | ~20 | 40 | 7% |
| Below Average | ~25 | 50 | 20% |
| Average | 30 | 60 | 40% |
| Good | 35 | 70 | 20% |
| Great | 40 | 80 | 11% |
| Elite | 50 | 100 | 2% |

The distribution is deliberately right-skewed: Elite sits +20 above Average while Poor sits only −10 below. There is no mirrored Elite at the bottom — walk-ons and low-tier signees occupy Poor, and the floor is around RT 18-20.

Tier is a **label**, not a mechanic. The rung multipliers in §4.2 are tier-independent; they multiply whatever JH anchor was drawn. Nothing in the growth model branches on tier.

### 4.2 Rung multipliers

Expressed as multipliers of the JH anchor. This is the **one-peak** path, with the peak at SO→JR:

| Rung | Multiplier | Average tier | Good | Great | Elite |
|---|---|---|---|---|---|
| JH | 1.00 | 30 | 35 | 40 | 50 |
| FR | 1.17 | 35 | 41 | 47 | 58 |
| SO | 1.43 | 43 | 50 | 57 | 72 |
| JR (peak) | 1.80 | 54 | 63 | 72 | 90 |
| SR | 2.00 | 60 | 70 | 80 | 100 |

Rung spacing is deliberately middle-bulged rather than even. Front-loading makes freshmen immediately good and removes the reason to retain upperclassmen; back-loading makes the first two seasons feel dead.

### 4.3 Ceiling behavior

RT compresses as it approaches **130** — gains run at reduced efficiency above ~95. Elite entry with three peaks lands at approximately 130, which is the practical maximum.

Individual attributes are **not** capped at 130. A few reaching 140-150 is intended, and arises from specialization: because RT is a weighted mean, concentrating growth into two attributes spikes those attributes while RT stays moderate.

---

## 5. Growth profile

Two independent systems, rolled at generation, stored on the player, never exposed.

### 5.1 Peak rungs — how much total growth

Peak counts **stack**. More peaks means more total career growth, not redistribution of a fixed budget.

| Peaks | Share | Career multiple | Average tier ends at | Elite ends at |
|---|---|---|---|---|
| 0 | 20% | 1.7x | ~50 | ~85 |
| 1 | 55% | 2.0x | 60 | 100 |
| 2 | 22% | 2.3x | ~70 | ~115 |
| 3 | 3% | 2.6x | ~78 | ~130 |

This is the mechanism behind the original brief's "some miss 2x, some exceed it."

**Which rung peaks** is a second roll. Weighting for a single peak: SO→JR most likely, then FR→SO, then JR→SR, then JH→FR rarest. A JH→FR peak is the freshman phenom; a JR→SR peak is the classic late bloomer.

**Peaks apply identically at every tier.** A Poor entrant rolls 0-3 peaks on the same distribution as an Elite one; because peaks are multipliers, the outcomes scale automatically. This produces a bounded but real crossover:

| | ends at |
|---|---|
| Poor + 3 peaks | ~52 |
| Average + 0 peaks | ~51 |
| Great + 3 peaks | ~104 |
| Elite + 0 peaks | ~85 |

**Development can beat recruiting by roughly one tier, but not more.** Recruiting remains the dominant lever; development is a real but bounded modifier.

**CH drives the peak-count distribution, not a flat bonus.** High career-CH shifts the distribution up; low CH shifts it down. It stays probabilistic — a high-CH recruit must still be able to roll zero peaks, because that is the bust, and it is what makes recruiting a gamble rather than a purchase.

**`ch_seed` is independent of entry tier.** This is what creates the diamond in the rough — a Poor entrant with high CH and three peaks — and it gives recruiting two genuinely separate axes: visible talent, roughly scoutable through RT, and hidden character. If the two correlate, recruiting collapses into a single axis.

### 5.2 Family timing — when each family arrives

The family curves in §6 are the **foundation, not an absolute.** High school players are unpredictable; maturation timing varies per player per family. Three independent rolls at generation:

| Family | Early | Standard | Late |
|---|---|---|---|
| Physical | 30% | 55% | 15% |
| Skill | 25% | 50% | 25% |
| Mental | 20% | 50% | 30% |

Late physical bloomers exist but are the exception. The two systems do different jobs and must stay orthogonal in code: **peaks control how much, timing controls when.**

Twenty-seven timing combinations on top of four peak counts produce genuinely different players from identical entry ratings. `physical: early, mental: late` is the athlete who arrives ready and doesn't understand the game until he's a junior — a recognizable archetype falling out of two dice rolls.

---

## 6. Attribute families

| Family | Attributes | Curve |
|---|---|---|
| **Physical** | ST, AG, + HT, WT | Front-loaded; essentially complete by end of SO |
| **Skill** | SC, SH, ID, OD, PS, BH, RB, FT | Steady across all four rungs |
| **Mental** | IQ, ND | Back-loaded |

`CH` is not in a family — it is the hidden driver (§8).

This is what makes a player *read* differently at FR than at SR rather than merely larger. A freshman is a raw athlete with a body and no feel; a senior is polished. No uniform curve produces that.

**Note:** the existing malleable/static split (`SC SH ID OD PS BH RB ST AG FT` vs `ND IQ CH EM MO`) governs **fatigue rescaling**, not development. Family assignment is an independent axis and the two must not be conflated in implementation.

---

## 7. Growth mechanics

### 7.1 Offseason development event — the primary growth

Fires at season rollover, before Training Camp:

1. Look up the player's rung on the ladder → base growth budget.
2. Apply the CH-seeded peak check for this rung → peak or standard.
3. Apply family timing modifiers → per-family share of the budget.
4. Distribute across attributes by training-position weights × family curve.
5. Roll HT/WT in the same event.
6. Recompute all five RTs.
7. Emit an offseason development report.

Non-core attributes still grow. Every attribute carries a positional growth multiplier that is **low but never zero** — a center's PS is a trickle, not a drain.

### 7.2 In-season training — shaping, not earning

Weekly decay shrinks substantially and per-point gains shrink to match; net stays slightly positive. Weekly numbers still move, because the Training Report exists and killing visible movement would gut it. They simply stop being where careers are made.

**Because non-core attributes are not allowed to rot, specialization is expressed as rate, not direction.** Everything grows; focused attributes grow much faster. The trade-off becomes opportunity cost (gains not taken) rather than loss (ground lost). This is a deliberate departure from the team-attribute philosophy, where bleed-without-investment was the goal.

**Split: 70% of total career growth from the offseason, 30% in-season.**

### 7.3 The accumulator

In-season allocation *aims* the offseason budget. Attributes trained most across the season receive the largest share of the offseason distribution.

**This is additive on top of §7.2, not a replacement for it.** In-season training does two jobs:

1. **Direct** — trained attributes rise now, at the reduced in-season rate.
2. **Aiming** — what was trained determines where the offseason's 70% lands.

A season spent hammering SH yields some SH immediately and points the large offseason bump at SH. Switching focus in week 20 does not erase the direct gains already banked; it scrambles the aim.

This is load-bearing — it is also the mid-season switch penalty (§9.4).

---

## 8. CH — the hidden driver

- **`ch_seed`** — frozen at generation, immutable, drives peak-count distribution. Never displayed.
- **Live `CH`** — remains trainable and fatigue-relevant for whatever the sim reads.

CH is **always hidden and never revealed.** It is deliberately the one attribute users feel but never see.

**This constrains the UI beyond CH itself.** Peaks are CH-driven, so anything exposing peak count or remaining peaks leaks CH by inference. The offseason report may say a player broke out; it may never say he has two peaks remaining.

**Hiddenness needs observable correlates or it reads as noise rather than magic.** A user must be able to develop instincts.

**The ATTITUDE indicator is driven by `EM`, not CH**, so it is not currently a CH proxy. That leaves CH with nothing observable correlated to it at all. A hook is needed before alpha — training report flavor text is the cheapest option and requires no change to what ATTITUDE means.

**CH distribution — DECIDED: flat.** CH stays `randint(1,100)` (measured mean 49.4, sd 28.4).

The peak-count target is reachable under any distribution, because only the composition of distribution and mapping is observable — 3% at three peaks is `CH > 97` under flat and `CH > 78` under Normal(50,15), with identical outcomes. The decision therefore rests on tuning ergonomics and blast radius, and both favour flat:

- **Flat gives uniform tuning sensitivity.** A one-point threshold shift always moves 1% of the league. Under Normal(50,15) the boundaries governing most players sit near the mode at 2.66% per point while the three-peak boundary sits in a tail at 0.08% per point — a hair trigger on the common case and a dead knob on the rare one.
- **Flat preserves existing consumers.** The training-camp bonus bands (>80 / >60 / >40 / >20) are absolute thresholds that split a flat league into fifths. Under a bell they would become 2.3% / 23% / 49.5% / 23% / 2.3%, collapsing the top and bottom bands. CH is also wired into a number of other gameplay components, all of which assume the current shape.
- **Hiddenness makes the shape unobservable.** CH is never displayed, so users experience only the outcome distribution, which is identical either way.

**Revisit if CH is ever exposed indirectly** — a scouting range, a character grade. At that point the distribution becomes visible and a bell would earn its keep.

Note that CH is re-rolled at every franchise init unless `preserve_character`, so the same universal player develops differently in different saves. Recommend keeping this — it is free replayability, and it is only coherent because CH is hidden.

---

## 9. Training position architecture

### 9.1 Concepts

- **`training_position`** — development pointer *and* measurement anchor for the ladder. Set by user or CPU at season start.
- **Display position** — equals the training position. `OVERALL` becomes the training position's RT rather than max RT.
- **Lineup position** — unrelated. Teams play players anywhere, independent of training position. Training position must never leak into lineup eligibility.

The ladder is measured against `training_position` because it is stable by intent, changes for visible reasons, and is semantically correct: "is he developing well toward what he is being developed toward."

### 9.2 Conversion cost is free

The weight tables already price it. Developing a PG toward SG means pouring into SH, which is 40% of SG RT and 5% of PG RT — his SG RT climbs, his PG RT barely moves. Height gates big-man conversions absolutely under §3.3.

**No additional efficiency haircut.** Adding one double-charges the user and makes an interesting decision punitive.

### 9.3 CPU logic at season start

Rules-based, no learning:

- Identify depth-chart holes over the next two seasons (who graduates).
- Find the best conversion candidate for the hole.
- Constraints: height must permit it; prefer adjacent positions on the PG→SG→SF→PF→C chain; never convert a senior (no payoff window).
- Team archetype biases the choice — a press-heavy program favors conversions toward AG/ND-leaning positions.

Same lever the CPU archetype project is already building; not a separate subsystem.

### 9.4 Mid-season switch penalty

If §7.3 is adopted, the accumulator *is* the penalty. Switch in week 4 and little is lost; switch in week 20 and most of a season's aiming is discarded, with the offseason budget landing split across two weight vectors. No special-case code, scales naturally with lateness, explains itself in one sentence.

Optional sharpener if playtesting says it's too soft: a few weeks of reduced training gain after a switch. Ship without it first.

### 9.5 Fixes a live bug

`_pick_top_rt_position` breaks ties **randomly**, and 8.0% of players have exact top-RT ties. Roughly 150 players per league currently get a randomly selected primary position each season, determining which attributes receive the training-camp core bonus. They are being developed toward a coin flip that re-flips annually. An explicit `training_position` field removes this.

---

## 10. Data model

One nested subdocument on the player rather than scattered fields:

```
development: {
  entry_tier,           // average | good | great | elite
  peak_count,           // 0-3, rolled at generation
  peak_rungs,           // e.g. ["SO_JR", "JR_SR"]
  family_timing: {
    physical,           // early | standard | late
    skill,
    mental
  },
  ch_seed,              // frozen career CH, hidden
  training_position,
  focus_accumulator     // in-season aiming → offseason budget
}
```

**Two implementation notes that matter more than they look:**

1. It must be written at **both** generation points — the universal pool and recruit generation — or half the league develops and half does not.
2. **Season rollover copies a fixed field list forward.** If `development` is not added to that list, every profile silently vanishes at the first rollover and everyone reverts to the default curve. That failure presents as a tuning problem for weeks.

---

## 11. Roster generation requirements

These are not progression concerns, but the progression model cannot hit its targets without them.

- **Balanced class sizes.** ~480 per class. Current SR 621 / SO 364 skew guarantees a talent cliff at every rollover regardless of progression tuning.
- **Unimodal freshman distribution.** The current p50 24 / p75 57 gap is two populations stapled together.
- **Position supply.** Roughly even natural-position distribution; C is currently 10.9%, or 1.6 per roster.
- **Regenerate the universal pool from a parameterized generator** driven by the tier table in §4.1, rather than patching it further. The pool has been hand-edited repeatedly (`decap_player_attr_hundreds_*`, `apply_tsv_attrs_*`). Regeneration is the only way it stays reproducible when tiers are re-tuned, and it removes the SH bimodality at the source instead of decapping after the fact.

### 11.1 Regenerating the universal players pool

Every new franchise init draws its entire 128-team league from the universal players collection. If that pool still holds old-scale players, a new franchise opens on the old distribution and only converts as recruits arrive — a four-season crossfade before the ladder means anything. Regeneration is mandatory, not cleanup.

**The pool holds players at all four class years, not just entrants.** Assigning entry tiers and rolling attributes is not sufficient. A pool senior must look like a senior *who walked the ladder*: RT at his tier's SR rung, attribute mix consistent with his family timing, physical attributes already matured while mental ones are not.

**Approach: generate every pool player as a JH and simulate him forward to his class year using the real offseason development event.** Not a parallel "make a senior" routine — literally the same function, run one to four times. Internal consistency is then structural rather than maintained by hand.

This also serves as a live test of the progression model before anything ships. If simulating ~1,920 careers forward produces a league that looks right, the model works. If it produces something odd, that surfaces during pool generation rather than four seasons into a validation run.

**What is fixed in the pool versus rolled per save:**

| Fixed on the universal player | Rolled fresh at franchise init |
|---|---|
| `entry_tier` | `ch_seed` |
| `family_timing` | Peak assignment for *remaining* rungs only |
| Accumulated attribute state, HT/WT | |

Past is fixed, future varies. A pool junior's already-accumulated attributes came from a known history that is identical in every save; whether his one remaining offseason is a peak is rolled per franchise. This preserves the replayability of per-save CH re-rolling without the incoherence of a player's history being governed by a profile he no longer has.

**Class-size balance (§11, first bullet) is enforced here**, in the same generation step — not corrected downstream.

**Sequencing:** the pool generator consumes the ladder constants from §12, so it cannot be written until the Monte Carlo has fit them.

### 11.2 Height distribution and position-intent generation

**This section is a prerequisite for §3.4, not a follow-on.** Prototyping the §3.3 vectors against the current 1,920-player population showed that no weight table or height curve can hit the acceptance criteria, because the height distribution cannot support five height-differentiated positions.

**Measured current heights:** p10 68 · p25 69 · p50 72 · p75 75 · p90 78 · max 87. Only 20.9% of the league is 76 inches or taller; 11.1% is 78+; 5.1% is 80+. The median player is 6'0".

Three prototype iterations against that population:

| | argmax PG / SG / SF / PF / C | PF−SF height gap |
|---|---|---|
| Current formula | 23.6 / 27.1 / 15.3 / 23.0 / **10.9** | +2.0 in |
| New vectors, PF/C height fitness | 30.1 / 32.0 / 16.5 / 16.7 / **4.7** | +5.0 in |
| Height fitness on all five positions | 35.2 / 31.0 / 8.5 / 20.2 / **5.1** | +1.0 in |

The vector work does what it should — the PF/SF gap widens from 2 inches to 5 — but centre supply collapses, because every gate correctly identifies that 89% of the league is under 6'6" and pushes those players to the perimeter. Holding heights fixed and fitting curves to compensate would bake the distortion permanently into the formula.

Redrawing heights from Normal(77, 3.6) with attributes untouched and rerunning the same candidate formula gives PG 14.7 / SG 26.7 / SF 18.2 / PF 27.2 / **C 13.3** — dramatically better supply from the height distribution alone.

#### Generate position intent first

The generator currently draws height and attributes independently and lets RT sort players into positions afterward, which leaves supply at the mercy of whatever distribution falls out. Invert it:

1. Assign **position intent** — roughly 20% per position.
2. Draw **height** from that position's distribution.
3. Draw **attributes** from that position's profile, at the tier drawn per §4.1.

Argmax balance then follows by construction. The weight vectors only need to be *consistent* with positional intent rather than manufacturing balance out of an unbalanced population. This also attacks the 32% tweener rate at its source — players generated with coherent positional profiles have identities, which is what gives the training-position mechanic stakes.

Target per-position height distributions (inches, approximate): PG 73.5, SG 76, SF 78.5, PF 80.5, C 82.5, each with sd ≈ 2.0-2.2, giving a league aggregate near mean 78, sd 3.6.

#### Consequence: absolute height thresholds elsewhere must be re-banded

Shifting the median from 72 to 78 re-sorts every system that reads height against fixed inch values. Known consumers:

- **`height_to_block_score`** (`utils/shared.py`) — `≤72 → 0`, then `h − 72`, `≥82 → 10`. Under the current distribution the league mean is **1.68** and **59% of players score zero**. Under the proposed distribution the mean becomes **5.08** with only 11% at zero. Block rates would move sharply.
- **`opening_tip`** — banded on absolute inches from 73 up through 83+.
- `franchise_manager` and `position_ratings` also carry absolute height comparisons.

This is the same failure pattern as the `cum_nd` 200/350 cutoffs: absolutes placed against an assumed distribution. Every one of them needs re-banding in the same pass, and a sweep should confirm the list above is complete.

### 11.3 Migrating the existing universal pool

**Principle: preserve identity and relative standing; regenerate values.**

Tall players should stay relatively tall on the new scale, and a player's talent level should classify to the same tier where possible. Where the current distribution is overabundant at a tier, tiering down is acceptable — some current elites becoming great or good is expected and fine. The same tolerance applies to height.

The mechanism is a **rank-preserving remap** rather than a value transform:

1. **Position intent** — sort the pool by height and assign intent in bands matching the target supply (tallest ~20% become centre intent, and so on), splitting the guard band by ball-handling and passing versus shooting and perimeter defence. This respects relative height while filling the centre shortage by construction.
2. **Height** — rank-map each player within his new position cohort onto that position's target height distribution. A player at the 80th percentile of height stays at the 80th percentile.
3. **Talent** — rank-map overall RT percentile onto the new tier bands from §4.1. Because the mapping is by rank, tier frequencies match the target **exactly**, which is what makes overabundance resolve itself automatically.
4. **Attributes** — preserve each player's relative attribute ordering (a shooter stays a shooter) while redrawing magnitudes to hit his new tier's target RT at his class year.

**One deliberate exception.** Raw attribute *values* are not preserved, because the current pool carries known generation artifacts — the SH bimodality at 88-105 being the clearest. Preserving shape at the level of "who is a shooter" keeps player identity; preserving exact values would carry the artifacts forward. Names, portraits, heights and tiers are what a returning user would recognise; a specific SH value is not.

---

## 12. Constants

All of the following belong in `_documentation_master/11_Design_Systems/Tunable_Constants.md` as part of this project, along with an audit of the training constants already there.

| Constant | Starting value | Notes |
|---|---|---|
| `JH_ANCHOR_BY_TIER` | 30 / 35 / 40 / 50 | Average / Good / Great / Elite |
| `TIER_FREQUENCY` | .62 / .25 / .115 / .015 | Sums to 1.0 |
| `RUNG_MULTIPLIERS` | 1.00 / 1.17 / 1.43 / 1.80 / 2.00 | JH → SR, one-peak path |
| `PEAK_COUNT_DISTRIBUTION` | .20 / .55 / .22 / .03 | 0-3 peaks, before CH weighting |
| `PEAK_RUNG_WEIGHTS` | SO_JR > FR_SO > JR_SR > JH_FR | Where a single peak lands |
| `PEAK_MULTIPLIER` | ~1.9x a standard rung | Tune against career-multiple targets |
| `CH_PEAK_WEIGHTING` | TBD | How ch_seed shifts peak distribution |
| `FAMILY_TIMING_WEIGHTS` | See §5.2 | Per family, early/standard/late |
| `FAMILY_CURVES` | See §6 | Per-family share of each rung's budget |
| `RT_COMPRESSION_THRESHOLD` | 95 | Where gains start compressing |
| `RT_SOFT_CAP` | 130 | Practical ceiling |
| `NON_CORE_GROWTH_MULTIPLIER` | Low, non-zero | Per position per attribute |
| `WEEKLY_DECAY_BY_YEAR` | Much reduced from current | Currently FR (-5,-2) … SR (-2,0) |
| `OFFSEASON_INSEASON_SPLIT` | ~70/30 | Share of total career growth |
| `ACCUMULATOR_WEIGHT` | TBD | How strongly in-season aims the offseason |
| `PF_HEIGHT_FITNESS` | Peak 78-81, non-monotonic | §3.3 |
| `C_HEIGHT_FITNESS` | Monotonic to ~84 | §3.3 |
| `SF_WEIGHTS` | ST dropped, SH/SC/ID/OD raised | §3.3 rebuild |
| `CAMP_BONUS_CH_BANDS` | >80 / >60 / >40 / >20 | Unchanged — flat CH preserves the fifths these assume |
| `CH_DISTRIBUTION` | flat `randint(1,100)` | §8 |
| `ABOVE_100_TARGET` | 5.5% of all players | Any attribute ≥ 100; measured and accepted, see §3.6.4 |

---

## 13. Display

- **Attributes:** bucketed in tens, extending past 10 — 110-119 shows as 11, 120-129 as 12, and so on.
- **Position RTs:** precise, all five listed. Training position highlighted in orange.
- **`OVERALL`:** the training position's RT.
- **`MOMENTUM` field:** replaced with `POSITION`, showing the training position. Momentum needs a new home if the profile is currently its only surface.
- **All bars:** scale to 1-100 and pin at full above 100; the numeral carries the information above that. Pinned state should be visually deliberate so it does not read as a rendering bug.
- **Recommended:** a quiet secondary marker on the highest RT when it is not the training position, so a user converting a player can see what the conversion is costing him.

### 13.1 Display sweep — confirmed scope

All attributes display on the 1-10 scale. RT displays on 1-100. **Remove every scaling toggle** for player attribute displays; the full 1-100 attribute scale becomes a dev-only concern.

Attribute progress bars fill on the 1-100 scale while the value shown beside them is the 1-10 figure.

This is a broad sweep and every frontend surface must be audited for alignment — the training report, roster displays, the set-lineup screen, recruiting pages, the player profile, and others. Expect the surface list to be longer than it first appears.

---

## 14. Decisions

**Resolved:**

1. **Accumulator model** — adopted as specified in §7.3, additive on top of in-season gains.
2. **The 1-100 toggle** — removed. See §13.1.
3. **ATTITUDE** — driven by `EM`, not CH. May be revisited later; unchanged for now.
4. **Offseason/in-season split** — 70/30. Exact figure still fitted in the Monte Carlo.
5. **RT formula fix applies to existing saves** — yes, kept distinct from the recalibration, which stays new-franchises-only.
6. **Position identities** — sharper. Drives the SF rebuild in §3.3.
7. **Archetype weight vectors** — rejected. Testing against the audit data showed specialization is already rewarded: among players at the same mean attribute level, the spiky third out-rates the balanced third at four of five positions (SG +5.5, SF +5.1, PF +2.4, C +2.1, PG −1.7). The SF problem was vector composition, not architecture, and is addressed in §3.3. If the Monte Carlo later shows in-position specialists lagging, a single convexity exponent on the weighted mean fixes it with one constant and no new tables — documented here as a fallback, not built.

8. **CH distribution** — flat. See §8 for the reasoning and the condition under which it should be revisited.

**Still open:** none. The design is decision-complete; remaining unknowns are constants to be fitted in the Monte Carlo (§15), not choices to be made.

---

## 15. Validation plan

**Offline Monte Carlo first.** None of this needs possessions — generation → camp → weekly decay and allocation → rollover is pure arithmetic over importable functions. Run ~10k synthetic careers and fit the constants there. A live 26-week measurement season is roughly two hours; four seasons is a working day per iteration, far too slow to fit tables against.

**Targets to hit in the Monte Carlo:**

- Median career multiple ≈ 2.0x, with 0-peak careers near 1.7x and 3-peak near 2.6x.
- ~3% of all players with at least one attribute ≥ 100.
- RT ceiling near 130; no player materially above it.
- Class-year p50 RT tracking the §4.2 ladder within a few points.
- Tier outcomes landing where §4.1 says they should.

**Then one live four-season validation run**, after the distant-sunset branch merges. Running it against a moving codebase produces a dataset that cannot be trusted.

**Sequencing note:** the distant sunset and the RT formula fix are both behavior-changing. Land both, then re-cut the reference anchor once. Cutting between them wastes the run.
