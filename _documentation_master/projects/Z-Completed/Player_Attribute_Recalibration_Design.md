# Player Attribute Recalibration — Design

**Status:** Passes 1 and 2 shipped and merged; live-validated over four seasons. Two defects open — height generation (§11.2) and the pending re-migration. 2026-07-30
**Scope:** New franchises only. In-flight alpha saves are not migrated.
**Repo path:** `_documentation_master/projects/Player_Attribute_Recalibration_Design.md`
**Companion to:** the project brief at `_documentation_master/projects/Player_Attribute_Recalibration_Brief.md` and the audit at `_documentation_master/projects/rt_sanity_audit/`

---

## 1. What this project actually is

The original framing was "recalibrate the numbers." The code says otherwise: **there is no player progression model to recalibrate.**

What exists today is three forces fighting with no designed outcome —

- a weekly decay treadmill applied to every trainable attribute (`apply_pre_training_conditions`, FR `randint(-5,-2)` down to SR `(-2,0)`),
- a concentrated weekly training spend (24 points, with untrained attributes taking a further `(-2,-1)`),
- a Week 1 Training Camp bonus (30 points, CH-tiered bonus, year-bonus roll, HT/WT growth for FR/SO only),

and **no offseason step at all** — `finish_season` (`franchise_routes.py:14713`) copies `attributes` and `position_ratings` forward verbatim and bumps `meta.year`. Note the function is `finish_season`, not `complete_season_transition`; earlier drafts of this document used the wrong name.

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

### 3.5 Stored rating drift — DIAGNOSED

Freshly computed ratings disagreed with **stored** ratings for 1,794 of 1,920 players and 163 of 300 recruits. The cause is now confirmed: **multi-vintage formula-drift staleness, confined to PF and C. It is not fatigue.**

Live attributes equal anchor attributes everywhere in the data (NG = 1.0, no fatigue persisted), so the "RT drifts with energy" hypothesis originally recorded here finds nothing — `_update_position_ratings` is called only at game init, before scaling, and `recalculate_energy_scaled_attributes` has no live callers. That branch of the diagnostic is closed.

What is actually there is three vintages:

- **390 FPD docs** carry the recruit-profile RT verbatim — the signing/rollover copy flagged by H3, which nothing recomputes under the player profile.
- **~1,404 FPD and all 163 FRD docs** match no current formula at all. They were written under older PF/C weight tables and height functions and never backfilled. PG, SG and SF weights never changed historically, which is exactly why those three positions mostly still match — 1,581 of the 1,794 mismatches are confined to PF and C.

Stored RT is only refreshed by `GameManager._update_position_ratings` (universal collection, non-franchise games) and the training write paths (FPD), so any player who has not trained or played under the current formula keeps a stale value.

**Architectural consequence, and it is load-bearing.** In-game RT for franchise games is recomputed fresh at `GameManager.__init__`, so a formula change bites in-sim immediately. But **lineup autoset, CPU roster and conversion logic, scouting, recruiting, and every UI surface read the stored `position_ratings`.** The formula change alone therefore does not move lineups, CPU behaviour or the interface. The bulk recompute in §11.3 is not cleanup — without it the new model is live in the simulation and invisible everywhere else.

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

Multiplicative, piecewise-linear, floor 0.50, cap 1.15. Penalty per inch away from ideal, asymmetric. **The apex is 1.0, not 1.15** — fitness is `1.0 − penalty`, so the cap never binds and exists only as a guard; a 1.15 apex does not reproduce §3.6.4:

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

#### 3.6.5 As-landed values (implementation pass 1)

Implemented on branch `player-attr-recalibration-pass1`. Final tuned constants: `ATTR_NOISE_SD = 0.13`, `IDENTITY_STRENGTH = 0.15`, `PROFILE_FILLER = 0.45` (unchanged).

| Metric | Fresh generator | Pool remap (as migrated) | Walk-ons |
|---|---|---|---|
| argmax PG/SG/SF/PF/C | 19.7 / 22.8 / 18.1 / 20.6 / 18.8 | 22.0 / 22.8 / 16.1 / 17.9 / 21.2 | 18.5 / 24.2 / 16.4 / 21.5 / 19.4 |
| median height by argmax | 73 / 76 / 79 / 80 / 83 | 74 / 76 / 79 / 80 / 83 | — |
| margin < 3 | 8.0% | 5.3% | — |
| exact ties | 1.9% | 1.4% | — |
| argmax matches intent | 95.9% | 97.7% (high by construction) | — |
| class p50 RT | 35 / 43 / 54 / 60 | 35 / 43 / 54 / 60 | 20 / 23 / 29 / 36 (Poor) |
| any attribute ≥ 100 | 5.7% | 6.2% | 0.0% |

The remap column reflects the final attribute-fit intent assignment of §11.3, not the earlier height-banding version.

League height lands at mean 78.2, sd 3.80. Centre supply moves from 10.9% to 19.9%. Class sizes balance at 384 each.

**Two deltas from §3.6.4, both deliberate.** `margin<3` lands near 8% rather than 11.2% — the 11.2% figure was a measurement from the fit, not a target, and §14's decision to sharpen position identity makes fewer tweeners the goal. Raising `PROFILE_FILLER` to recover them was explicitly rejected. And the remap's 6.4% above-100 sits 0.9pp over the accepted 5.5%, which is the price of keeping `IDENTITY_STRENGTH` at 0.15 rather than driving it to zero.

**Walk-ons run through the same generator at Poor tier** with a drawn position intent, rather than the old uniform draw. They are 3 of 15 per roster — 384 players, 20% of everyone on a court — so leaving them off the ladder would have put a fifth of the league on the old scale. Their CH cap of `randint(1,90)` was removed in favour of the flat 1-100 in §8; the cap would otherwise have structurally foreclosed the high-CH walk-on who develops into a star.

**Elite seniors land at p50 105 before peaks are applied.** With peak stacking to 2.6x on top, this confirms the §4.3 compression above RT 95 is required rather than optional.

#### 3.6.6 Migration record

Migrated to `gob-staging` on 2026-07-29 and verified by read-back. Merged to `develop` (`1eb31ddc5` … `e1ab95839`).

| | |
|---|---|
| Universal pool | 1,536 docs remapped — `attributes`, `height`, `weight`, `year`, `position_ratings`, `entry_tier`, `position_intent` |
| Franchise player docs | 30,718 — `position_ratings` only |
| Franchise recruit docs | 7,900 — `position_ratings` only |
| Pool median height | 72 → 78 |
| Centre supply | 10.9% → 21.2% |
| Spearman(old height, new height) | **0.9370** |

**Displacement** — the honest identity metric for an attribute-derived assignment: 95.8% of pool players received their best-fit position, 3.4% their second, 0.8% their third, none worse. The assignment reached 99.8% of the unconstrained objective ceiling, so the soft capacity bands cost almost nothing.

**Supply per bucket:** PG 338 (22.0%), SG 318 (20.7%), SF 276 (18.0%), PF 276 (18.0%), C 328 (21.4%). SF and PF sit exactly at the 18% floor — the in-between positions are rarely anyone's top fit, since they overlap with neighbours on both sides.

**Height by assigned intent** (p10 / median / p90): PG 71/74/76, SG 73/76/79, SF 76/78/81, PF 78/80/83, C 80/82/85. Monotonic, with C's p10 above SF's median.

**Rollback.** The migration is **non-idempotent** — rank-mapping an already-remapped pool produces garbage. Restore before any re-tune; never re-run against migrated data.

```
db["players_backup_prerecal_20260729"].aggregate([{"$match": {}}, {"$out": "players"}])
```

The pre-migration snapshot `players_backup_prerecal_20260729` (1,536 docs, whole-document verified, restore rehearsed into a scratch collection) is retained, as is the older `players_backup` from 2026-07-08 as a second recovery point. FPD and FRD `position_ratings` need no backup — they are derived and recomputable from attributes and height, which the migration never modifies on those documents.

#### 3.6.7 Known consequences for existing saves

Existing franchises are deliberately not remapped (§14). Two effects follow, both accepted:

- **Distorted RT for bigs.** Old-scale rosters keep short players while gaining height-gated PF and C ratings, so their interior players' RTs collapse.
- **Shot-blocking effectively disappears.** `height_to_block_score` returns 0 at or below the league median of 78, and an old-scale roster's p90 height *is* 78. This is a gameplay change rather than a cosmetic one, and it is written into `Tunable_Constants.md` so that a "nobody blocks shots on my save" report is not misdiagnosed as a bug.

**The 2026-07-20 reference anchor is not comparable to the post-recalibration one.** Roughly eighteen sim-touching commits landed between them, several explicit shot, block and foul recalibrations, so the large aggregate deltas belong to that tuning rather than to this project. The recalibration's own sim-outcome effect is unmeasured by design and will come from pass 2's four-season validation franchise, the first one initialised off the regenerated pool. A warning to this effect is recorded in `scripts/sim_verify/README.md`.

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

**There is no magnitude split.** An earlier draft specified 70% of career growth from the offseason and 30% in-season. That is architecturally impossible against an absolute-target offseason — see §17.1 — and was replaced.

In-season carries two other jobs instead: moving attributes within the season, and feeding the coaching-quality score that modulates the offseason (§17).

**Every in-season RT figure must be labelled by allocation policy.** An unlabelled "in-season nets X" is meaningless, and the omission has already caused one contradiction — a "reference coaching" figure was quoted against the frozen reference when it came from a much better allocation. At `IN_SEASON_GAIN_SCALE` 0.18, over a 26-week season:

| Allocation policy | coaching quality | in-season RT/season |
|---|---|---|
| Random | ~0.5-0.8 | −9.78 |
| **Frozen reference** (what CPU trains) | **1.00** | **−1.23** |
| Proportional / good coaching | ~1.20 | +4.76 |

The frozen reference nets slightly negative *by design* — it is a deliberately mediocre baseline (§17.3), and the absolute-target offseason re-anchors it onto the ladder regardless. Good coaching nets positive but stays below the smallest per-rung increment (~+6 RT), so a well-coached player can never outrun his own offseason target and be pulled back at rollover.

The gap between the bottom and top rows is the user's coaching edge: roughly **6 RT per season** against a correctly-trained CPU league. That residual is the designed reward for out-coaching the baseline, not an artifact.

Under good coaching the *per-attribute* net is ≈ 0.000 with a mean absolute movement of 0.52 per week — attributes visibly shift toward the focus while RT, their weighted mean, stays nearly flat. **§7.2's visibility requirement is about attributes, not RT.** Measuring RT delta is the wrong instrument for it.

### 7.3 The accumulator

In-season allocation *aims* the offseason budget. Attributes trained most across the season receive the largest share of the offseason distribution.

**This is additive on top of §7.2, not a replacement for it.** In-season training does two jobs:

1. **Distribution** — what was trained determines where the offseason budget lands.
2. **Quality** — the same allocation is scored to produce the coaching multiplier of §17.

These are two independent signals computed from one input, and they are kept separate in code so neither can silently stop working. A season spent hammering SH points the offseason bump at SH *and* scores as focused coaching; switching focus in week 20 scrambles the aim without erasing the attribute movement already banked.

This is load-bearing — it is also the mid-season switch penalty (§9.4).

---

## 8. CH — the hidden driver

- **`ch_seed`** — frozen at generation, immutable, drives peak-count distribution. Never displayed.
- **Live `CH`** — remains trainable and fatigue-relevant for whatever the sim reads.

CH is **always hidden and never revealed.** It is deliberately the one attribute users feel but never see.

**This constrains the UI beyond CH itself.** Peaks are CH-driven, so anything exposing peak count or remaining peaks leaks CH by inference. The offseason report may say a player broke out; it may never say he has two peaks remaining.

**Hiddenness needs observable correlates or it reads as noise rather than magic.** A user must be able to develop instincts.

**The ATTITUDE indicator is driven by `EM`, not CH**, so it is not currently a CH proxy. That leaves CH with nothing observable correlated to it at all. A hook is needed before alpha — training report flavor text is the cheapest option and requires no change to what ATTITUDE means.

**Known conflict to resolve.** A CH tooltip already exists in the frontend at `attributeTooltips.js:7`, labelled "Clutch", which means CH is surfaced somewhere today. Either that surface is found and removed as part of the display sweep, or this section is aspirational rather than true. Resolve before the display task is scoped.

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
entry_tier            // top-level, written by pass 1
position_intent       // top-level, written by pass 1

development: {
  peak_count,         // 0-3, rolled at generation
  peak_rungs,         // e.g. ["SO_JR", "JR_SR"]
  family_timing: {
    physical,         // early | standard | late
    skill,
    mental
  },
  ch_seed,            // frozen career CH, hidden
  focus_accumulator   // in-season aiming → offseason budget
}
```

`entry_tier` and `position_intent` sit **top-level, not inside the subdoc** — pass 1's migration put them there. `training_position` is deliberately absent: the growth model uses `position_intent` as its development pointer, which decouples going live from the whole focus-position system (§9).

**Four implementation notes that matter more than they look:**

1. There are **four** creation points, not two: universal pool generation, FPD construction at franchise init, recruit generation, and walk-on generation. Miss any and part of the league does not develop.
2. **`position_intent` currently dies pool→FPD.** `_build_fpd_doc` copies only `meta`, `attributes` and `position_ratings`, so franchise init drops both `entry_tier` and `position_intent`. Since `finish_season` develops FPD players, they must be carried across explicitly.
3. **`finish_season` copies a fixed field list forward** — `franchise_id`, `player_id`, `meta`, `season`, `career`, `attributes`, `position_ratings`. If `development`, `entry_tier` and `position_intent` are not added to it, every profile silently vanishes at the first rollover and the league reverts to the default curve. That failure presents as a tuning problem for weeks. A test must survive a rollover and assert the profile is intact.
4. `develop_one_offseason` needs a `jh_anchor`, which FPD docs do not carry. It is derived from `entry_tier` via `JH_ANCHOR_BY_TIER` — another reason `entry_tier` has to reach FPD.

**Players with no profile (existing saves, never backfilled)** get one rolled on first encounter and **persisted** — a lazy backfill, not an on-the-fly roll, since re-rolling each season would give a player a different profile every year. The roll uses the normal CH-weighted peak mapping, freezes the live CH value as `ch_seed`, and assigns peaks to **remaining rungs only**, per the past-fixed/future-varies rule in §11.3. Caveat to document rather than solve: deriving `entry_tier` from a legacy player's current RT misclassifies those whose RT collapsed under height gating — a distorted big man reads as Poor and then develops on a Poor ladder, compounding the degradation §3.6.7 already accepts.

---

## 11. Roster generation requirements

These are not progression concerns, but the progression model cannot hit its targets without them.

- **Balanced class sizes.** ~480 per class. Current SR 621 / SO 364 skew guarantees a talent cliff at every rollover regardless of progression tuning. This is enforced in *pool* generation (§11.3), not recruit generation — recruits are correctly JH-dominant entrants.
- **Unimodal freshman distribution.** The current p50 24 / p75 57 gap is two populations stapled together.
- **Position supply.** Roughly even natural-position distribution; C is currently 10.9%, or 1.6 per roster.
- **Regenerate the universal pool from a parameterized generator** driven by the tier table in §4.1, rather than patching it further. The pool has been hand-edited repeatedly (`decap_player_attr_hundreds_*`, `apply_tsv_attrs_*`). Regeneration is the only way it stays reproducible when tiers are re-tuned, and it removes the SH bimodality at the source instead of decapping after the fact.

### 11.1 Regenerating the universal players pool

Every new franchise init draws its entire 128-team league from the universal players collection. If that pool still holds old-scale players, a new franchise opens on the old distribution and only converts as recruits arrive — a four-season crossfade before the ladder means anything. Regeneration is mandatory, not cleanup.

**The pool holds players at all four class years, not just entrants.** Assigning entry tiers and rolling attributes is not sufficient. A pool senior must look like a senior *who walked the ladder*: RT at his tier's SR rung, attribute mix consistent with his family timing, physical attributes already matured while mental ones are not.

**Approach: generate every pool player as a JH and simulate him forward to his class year using the real offseason development event.** Not a parallel "make a senior" routine — literally the same function, run one to four times. Internal consistency is then structural rather than maintained by hand.

**Sequencing caveat — an interim form is needed first.** Simulate-forward depends on the offseason development event, which depends on the growth constants fitted in the Monte Carlo (§15). But the RT formula in §3.6 cannot merge without the new height distribution, which requires the generator. To break the cycle, generation splits in two:

- **Interim (unblocks §3.6):** generate players *directly* at their class-year target from the §4.2 ladder, needing only the tier table and rung multipliers. This is exactly what the §3.6 fit was validated against.
- **Final (after the Monte Carlo):** ~~replace it with generate-as-JH-and-simulate-forward~~ — **CLOSED, not needed.** The interim generator already reproduces the ladder exactly (class p50 RT 35/41/54/60, senior p50 by tier 40/50/60/70/80/100), and the 10k-career Monte Carlo in §16 is a far better model check than 1,920 simulated pool careers. Simulate-forward would add coherent development *history*, which nothing reads and nothing plans to, at the cost of a full pool re-migration. Removed from the queue.

**Stored `position_ratings` are recomputed in this same pass**, not as a separate migration — the 1,794 player and 163 recruit mismatches from §3.5 are corrected wherever they live, including the universal players collection, alongside the attribute and HT/WT updates. Note that recomputing fixes the symptom; if the §3.5 diagnostic shows the cause is RT being computed from fatigue-scaled attributes, the drift will recur and the cause needs fixing too.

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

> **⚠️ DEFECT — this section as written produces adult heights for every class year. Open, fix pending.**
>
> Those per-position figures are **mature** heights: they mirror the height-fitness peaks in §3.6.2, the values at which a player's rating is maximised at that position. `player_generation.draw_height()` implements them literally — `gauss(HEIGHT_IDEAL_IN[position], 2.1)` with **no class-year term** — so a JH recruit is generated at the same height as a senior. `weight_from_height` then derives weight from that inflated height, so the weight error is downstream of the same cause.
>
> **Grow-into-frame is missing.** The Monte Carlo model in §16.3 assumes JH height = the adult draw minus expected career gain. The production generator never received it. A JH recruit should be roughly **adult − 3.2 inches** (≈74.8 against a league mean of 78), and pool players should be staggered by class year using the remaining share of the HT curve: JH→FR 40%, FR→SO 30%, SO→JR 20%, JR→SR 10%.
>
> **Measured scope — both generation and the migrated pool.** The pool is flat by class year: FR 78.31 / SO 77.97 / JR 78.08 / SR 78.02, a total spread of **0.34 inches**, every class at a 78-inch median. §11.3's rank-mapping carried no year term. In a live franchise, freshmen sit **above** their own position ideal at every position — PG +1.42, SG +1.46, SF +1.99, PF +1.33, C +1.56 — with 73-87% at or beyond the fitness peak before any college growth, and league mean height climbing roughly +1.4 inches over four seasons as entrants grow past a frame they already occupy.
>
> **Fixing it requires a pool re-migration** — restore `players_backup_prerecal_20260729`, correct the generator, re-run. The migration is non-idempotent, and the re-run invalidates every franchise built from the current pool.
>
> The silver lining is that the fix gives HT growth its intended meaning: young players start undersized, are correctly penalised by height fitness, and grow *into* their position rather than past it.

#### Consequence: absolute height thresholds elsewhere must be re-banded

Shifting the median from 72 to 78 re-sorts every system that reads height against fixed inch values. The completed sweep found the following — the original four-item list in this section was incomplete:

| Location | What | Thresholds |
|---|---|---|
| `utils/shared.py:1445` | `height_to_block_score` | `≤72 → 0`, `h−72`, `≥82 → 10` |
| `utils/opening_tip.py:44-65` | `get_height_scale_value` (live tip) | `>83 → 10`, `≥81 → 9`, `≥79 → 8`, `78 → 7` … `<73 → 1` |
| `utils/opening_tip.py:292-306` | `player_tip_score` height dict | `82 → 11` … `73 → 2`; marked legacy — **delete if confirmed dead rather than re-band** |
| `models/franchise_manager.py:1184-1193` | `_generate_weight`, weight derived from height | bands at `<72` / `72-75` / `76-80` / `>80` |
| `models/franchise_manager.py:1136-1157` | archetype `height_range` per recruit archetype | replaced by §11.2 generation |
| `models/franchise_manager.py:174-179` | `WALK_ON_YEAR_PROFILES` height ranges | JH (66,72) … Junior (68,77) |
| `models/training_execution_v2.py:1149-1160` | training-camp weight-delta gates | `height_after > 75`, `> 72` |
| `models/shot_manager.py:1197-1228` | block reconciliation, `def_h × 10` scaling | downstream of `height_to_block_score` |

Under the current distribution `height_to_block_score` yields a league mean of **1.68** with **59% of players at zero**; under the proposed distribution the same function yields **5.08** with 11% at zero. Re-banding must preserve each system's intended *shape* — roughly the same league mean block score and tip-off distribution — not its literal thresholds.

**Each consumer needs its own shift, not one global offset.** Block score is fed by the whole league, whose median moves 72 → 78, so it shifts +6. The opening tip is contested by centres, whose median moves 79 → 82, so it shifts +3. The feeding population determines the shift.

**Missing-height fallback defaults also need attention.** Several literals sit below the new median: `shot_manager.py` (76), `player.py:62` (75), `quick_foul.py:96` (75), `team_builder_roster.py` (72). These are not bands, but a 72-76 inch default now reads as a guard. Replace all of them with a single named constant set to the new league median rather than re-scattering literals.

This is the same failure pattern as the `cum_nd` 200/350 cutoffs: absolutes placed against an assumed distribution. Every one of them needs re-banding in the same pass.

### 11.3 Migrating the existing universal pool

**Principle: preserve identity and relative standing; regenerate values.**

Tall players should stay relatively tall on the new scale, and a player's talent level should classify to the same tier where possible. Where the current distribution is overabundant at a tier, tiering down is acceptable — some current elites becoming great or good is expected and fine. The same tolerance applies to height.

The mechanism is a **rank-preserving remap** rather than a value transform:

1. **Position intent** — a capacity-constrained assignment, not a height banding. Each player receives a fit score for all five positions, and the assignment maximises total fit subject to per-position capacity.

   - **Fit** is the new weight vector for each position applied to the player's *current attributes*, with no height term. Stored `position_ratings` are deliberately **not** used: they come from the formula being replaced, so they carry the PF height saturation, the PF/C attribute overlap and the athleticism-weighted SF that this pass exists to remove. Using them would faithfully reproduce the 10.9% centre supply.
   - **Normalised per position** before comparison — each raw fit is converted to the player's percentile among all players at that position, since different vectors load on attributes with different league means and would otherwise not be comparable.
   - **Height modulates rather than decides**, via the same fitness curve, so an interior-skilled short player does not become a centre while height still informs the choice.
   - **Soft capacities** of 18-22% per position rather than a hard 20%. Fresh generation still draws evenly, so the league converges to 20% as the pool turns over.
   - Circularity is broken with two passes: fit uses height rank-mapped against the *league-wide* new distribution; once intent is assigned, step 2 rank-maps within cohort.

   **The metric changes with the method.** Once intent is derived from attributes, "argmax matches intent" is high by construction and is no longer an independent check for the remap — it remains meaningful only for fresh generation, where intent is drawn before attributes exist. The honest measure here is **displacement**: what share of players receive their best-fit position.
2. **Height** — rank-map each player within his new position cohort onto that position's target height distribution. A player at the 80th percentile of height stays at the 80th percentile.
3. **Talent** — rank-map overall RT percentile onto the new tier bands from §4.1. Because the mapping is by rank, tier frequencies match the target **exactly**, which is what makes overabundance resolve itself automatically.
4. **Attributes** — preserve each player's relative attribute ordering (a shooter stays a shooter) while redrawing magnitudes to hit his new tier's target RT at his class year.

**Step 4 needs care.** Taken literally — scaling the old raw attribute vector to hit the target at the newly assigned position — it explodes RT for players whose old shape does not match their new position, producing above-100 attributes in over 40% of the pool. It only works as a *blend* of the intended-position profile with the player's relative ordering, implemented as `IDENTITY_STRENGTH`. Higher values preserve more shape and import more of the old artifacts; the workable knee is 0.10-0.15.

**One deliberate exception.** Raw attribute *values* are not preserved, because the current pool carries known generation artifacts — the SH bimodality at 88-105 being the clearest. Preserving shape at the level of "who is a shooter" keeps player identity; preserving exact values would carry the artifacts forward. Names, portraits, heights and tiers are what a returning user would recognise; a specific SH value is not.

---

## 12. Constants

All of the following belong in `_documentation_master/11_Design_Systems/Tunable_Constants.md` as part of this project, along with an audit of the training constants already there.

| Constant | Starting value | Notes |
|---|---|---|
| `JH_ANCHOR_BY_TIER` | 30 / 35 / 40 / 50 | Average / Good / Great / Elite |
| `TIER_FREQUENCY` | .07 / .20 / .40 / .20 / .11 / .02 | Poor → Elite, per the six-tier table in §4.1. An earlier four-value row here was superseded |
| `RUNG_MULTIPLIERS` | 1.00 / 1.17 / 1.43 / 1.80 / 2.00 | JH → SR, one-peak path |
| `PEAK_COUNT_DISTRIBUTION` | .20 / .55 / .22 / .03 | 0-3 peaks, before CH weighting |
| `PEAK_RUNG_WEIGHTS` | SO_JR > FR_SO > JR_SR > JH_FR | Where a single peak lands |
| `PEAK_BONUS` | +0.30 × JH anchor, fixed per peak | Replaces `PEAK_MULTIPLIER`. A rung *multiplier* is unimplementable: it cannot simultaneously reproduce the linear career multiples and the §4.2 one-peak path. A fixed per-peak bonus reproduces both exactly |
| `CH_PEAK_WEIGHTING` | TBD | How ch_seed shifts peak distribution |
| `FAMILY_TIMING_WEIGHTS` | See §5.2 | Per family, early/standard/late |
| `FAMILY_CURVES` | See §6 | Per-family share of each rung's budget |
| `RT_COMPRESSION_THRESHOLD` | 95 | Where gains start compressing |
| `RT_SOFT_CAP` | 130 | Practical ceiling |
| `NON_CORE_GROWTH_MULTIPLIER` | Low, non-zero | Per position per attribute |
| `WEEKLY_DECAY_BY_YEAR` | Much reduced from current | Currently FR (-5,-2) … SR (-2,0) |
| `OFFSEASON_DISTRIBUTION_BLEND` | 0.70 | A distribution blend, **not** a magnitude split — no magnitude split exists (§7.2, §17.1) |
| `QUALITY_CAP` | 4 points per attribute per week | Saturation point of the coaching-quality metric (§17.2) |
| `COACHING_F_MIN` / `COACHING_F_MAX` | 0.85 / 1.20 | Bounds on the coaching multiplier (§17) |
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
- Above-100 rate as measured and accepted, not the ~3% figure earlier drafts carried. See §16.2 — it lands at 7.5% of the pool and 19.0% of seniors, locked.
- RT ceiling near 130; no player materially above it.
- Class-year p50 RT tracking the §4.2 ladder within a few points.
- Tier outcomes landing where §4.1 says they should.

**Then one live four-season validation run**, after the distant-sunset branch merges. Running it against a moving codebase produces a dataset that cannot be trusted.

**Sequencing note:** the distant sunset and the RT formula fix are both behavior-changing. Land both, then re-cut the reference anchor once. Cutting between them wastes the run.

---

## 16. Pass 2 — the fitted growth model

Fitted offline against 10,000 synthetic careers. Module: `BackEnd/utils/player_development.py` — `develop_one_offseason`, `roll_growth_profile`, `simulate_career` — pure and RNG-injectable, reusing `player_generation` for the JH start and `position_ratings` for RT. Driver: `scripts/mc_growth_fit.py`. Branch `attr-recalibration-pass2-growth`.

### 16.1 Fitted constants

| Constant | Value | Expose? |
|---|---|---|
| `STD_RUNG_INCREMENT` (× JH anchor) | FR .17 / SO .20 / JR .15 / SR .18 (Σ .70 → 1.7x at zero peaks) | yes |
| `PEAK_BONUS` | +0.30 × JH anchor, fixed per peak | yes |
| `PEAK_RUNG_WEIGHTS` | JR .42 / SO .28 / SR .20 / FR .10 | — |
| `CH_PEAK_WEIGHTING` | linear interp, low (.38,.52,.10,0) → high (.02,.58,.34,.06) | spread only |
| `FAMILY_CURVES` (weight multipliers per rung, phys/skill/mental) | FR 3.0/1.0/.30 · SO 2.0/1.2/.60 · JR .60/1.3/2.2 · SR .35/1.2/3.2 | yes |
| `HT_CURVE_BY_TIMING` (share of career HT gain) | early 55/30/12/3 · standard 40/30/20/10 · late 15/25/35/25 | yes |
| `HT_TOTAL` | Normal(3.2, 1.9) clamped [0,8]; per-rung cap 2.5 in | yes |
| `FAMILY_TIMING_WEIGHTS` | §5.2 as-is; `FAMILY_TIMING_SHIFT` 0.40 | no |
| `OFFSEASON_DISTRIBUTION_BLEND` | 0.70 | yes |
| `INTRA_FAMILY_GAMMA` | 0.20 | no |
| `NON_CORE_GROWTH_MULTIPLIER` | 0.06 (never zero) | no |
| `RT_COMPRESSION_THRESHOLD` / `RT_SOFT_CAP` | 95 / 130 | no |
| `WEEKLY_DECAY_BY_YEAR` | defaults only — not target-fittable | n/a |
| `QUALITY_CAP` | 4 points/attribute/week | yes |
| `COACHING_F_MIN` / `COACHING_F_MAX` | 0.85 / 1.20 | yes |

`PEAK_BONUS` and `STD_RUNG_INCREMENT` are effectively pinned by the targets rather than free. The `CH_PEAK` endpoint spread is mean-constrained — it does not move the aggregate peak distribution, only how strongly CH predicts peaks, so it is a feel knob for diamond-in-the-rough strength. `HT_TOTAL` and the HT curves set the position-flip rate.

### 16.2 Measured against targets

| Target | Measured | |
|---|---|---|
| peak counts 20 / 55 / 22 / 3 | 20.1 / 54.3 / 22.8 / 2.8 | ✓ |
| career multiples 1.7 / 2.0 / 2.3 / 2.6 | 1.70 / 2.00 / 2.30 / 2.60 | ✓ exact |
| Average ladder 35 / 43 / 54 / 60 | 35 / 41 / 54 / 60 | SO −2, accepted |
| senior p50 by tier 40/50/60/70/80/100 | 40/50/60/70/80/100 | ✓ exact |
| RT ceiling ~130 | max 131, p99 100, none above 132 | ✓ |
| `ch_seed` ⊥ `entry_tier` | −0.010 | ✓ diamond in the rough intact |
| any attribute ≥ 100 | 7.5% of pool, 19.0% of seniors | **locked** |

The SO ladder point moved from 43 to 41 when the rung increments were flattened. That was deliberate: the original JR increment of .07 left roughly 55-60% of players — those with no peak, plus everyone whose peak landed elsewhere — gaining about 2 RT in their junior offseason, invisible on a 1-10 display. After flattening, every non-peak rung yields +5 to +6 RT and a peak lands +14 to +15. No dead rungs in any peak configuration. §4.2's ladder was a measurement from the original fit rather than a design commitment, and it assumed a JR peak that only 42% of single-peak players have.

The above-100 rate is accepted as structural and locked. Reaching Elite senior RT 100 through a weighted mean carrying a concentrated weight — SG's SH at .42 — forces high-tier seniors to hold a 100+ attribute; the pool floors near 7.5% even under fully uniform growth. To be judged in gameplay rather than tuned.

### 16.3 Family shares and height

Share of each rung's growth by family (physical / skill / mental): FR 35/58/7 · SO 26/65/9 · JR 11/66/23 · SR 9/61/30. Physical takes 61% of its career growth in FR and SO; mental climbs from 7% to 30%. Mental share is position-weighted, so a PG gains more RT credit for IQ than an SF does — correct, since a senior wing gains feel without it showing up in his rating.

**HT has its own curve, separate from the physical family.** It is the only attribute whose growth can change a player's best position, and it is already handled in its own block in the training-camp code. ST and AG follow the family curve; WT tracks strength and keeps growing throughout.

Mean HT gain in inches by rung: early timing 1.44 / 0.96 / 0.39 / 0.09, standard 1.23 / 0.97 / 0.65 / 0.33, late 0.49 / 0.81 / 1.10 / 0.81. Career gain p10 0 / p50 3 / p90 5-6 inches; roughly 8% of players gain no height at all.

The earlier guidance that physical growth is "locked to early rungs" was the wrong instrument — it bounded by rung when the real requirement is bounding by **magnitude**. Very few players stop growing after their sophomore year. Everyone keeps gaining height at JR and SR; late bloomers gain most of theirs there.

**HT growth changes a player's best position 5.3% of the time**, and this is timing-independent (early 5.9% / standard 5.1% / late 4.9%). Generation works grow-into-frame — JH height is the adult draw minus career gain — so with equal career totals across timing groups every player converges on the same adult height, and his senior best position is set by that draw rather than by when he grew. Concentrating flips in late bloomers would require late timing to correlate with a *taller* adult outcome, which would erode the position-supply balance §11.2 exists to guarantee. Deliberately not done.

### 16.4 Not fittable offline

`WEEKLY_DECAY_BY_YEAR` and the in-season gain scale cannot be fitted against career-outcome targets. Under a no-user-focus policy only the *net* in-season contribution matters, and that net is specified as roughly flat (§7.2) rather than as a target fraction.

They are mechanism and UX knobs. The two things they govern — the mid-season switch penalty (§9.4) and the requirement that weekly movement stay visibly positive (§7.2) — remain **unvalidated**, and both need a live season with a real user-focus policy. This belongs in the validation run as an explicit item rather than something discovered in alpha.

---

## 17. The coaching-quality multiplier

The offseason event targets `jh_anchor × ladder_value × f(coaching_quality)`. `f` is bounded to **[0.85, 1.20]**, so coaching moves a player meaningfully above or below the designed ladder without displacing recruiting as the dominant lever.

### 17.1 Why not a magnitude split

§7.2 originally specified 70% of career growth from the offseason and 30% in-season. That is incompatible with an absolute-target offseason, and the incompatibility is structural rather than a tuning problem.

The offseason event *solves* an attribute budget so RT lands on a fixed ladder value. Anything in-season therefore either gets erased at the next re-anchor, or ratchets past it and compounds without bound. Measured: at an in-season gain scale of 0.25 career multiples blew out to 3.2x with seniors at 86-117; at 0.05 the model collapsed to the RT floor. There is no stable basin between them, because the weekly treadmill makes the net a large-minus-large.

Three routes were considered. Making the offseason **relative/additive** would deliver a true split, but surrenders the fixed class-year scale — the distributions become emergent rather than designed, and user-versus-CPU divergence compounds across a franchise's lifetime with nothing to correct it. Treating the ladder as a **ceiling** training fills toward makes coaching pure downside avoidance: you train well to avoid falling behind, never to build something exceptional.

The chosen route keeps the offseason absolute and multiplies its target by a bounded coaching factor. The ladder survives as the designed centre, coaching moves players in both directions, and each offseason re-anchors so nothing drifts.

### 17.2 The metric

Coaching quality scores a season's training allocation, expressed in **points per attribute per week**, not shares:

```
contribution_a = weight_a × min(points_a / QUALITY_CAP, 1)
quality        = Σ contribution / Σ contribution(reference)
```

`QUALITY_CAP` is 4 points. Because the cap is high in points, saturation is expensive — spreading a fixed budget thin saturates nothing, and concentrating it saturates the attributes that matter.

**Points rather than shares is deliberate.** Shares sum to 1 regardless of budget size, so a smaller budget would score identically to a larger one with the same proportions. In points, a smaller budget saturates fewer attributes and scores lower automatically. This matters for the planned per-player training focus feature, where customising costs roughly 2 points against blanket team-wide training: that efficiency cost prices itself through the same mechanism with no special-casing.

Achievable range is normalised affinely per position, so headroom is comparable everywhere — an earlier fit gave SF 1.52 and SG 1.07, which made coaching matter twice as much at one position as another for no design reason.

### 17.3 The reference anchor

The allocation that scores exactly 1.0 is a **frozen, named constant**: a deliberately mediocre baseline, weight-proportional across the position's top three attributes and neglecting the tail. Test-asserted at all five positions.

Two properties follow. CPU teams train that baseline, so the league sits exactly on the ladder and nothing calibrated against the scale floats. (This was *false* until commit `14e4baee9` — CPU previously allocated randomly, scoring far below 1.0. See §17.6.) And because the baseline is *mediocre rather than optimal*, good coaching has real upside — which a proportional reference structurally cannot provide, since a concave metric is very nearly maximised by proportional allocation itself.

**Which allocation scores 1.0 is a labelling choice, not a property of the metric.** That is what dissolves the apparent trade-off between holding the league on the ladder and giving coaching upside. The only real constraint is that pillar 3 must keep CPU's baseline aligned to the frozen constant — changing the reference re-scales every player's development.

### 17.4 Strategy shape

| Strategy | quality → f |
|---|---|
| reference (≈ CPU) | 1.00 → 1.00 |
| all-in on the top attribute | 0.79-0.82 → 0.85 |
| off-position | 0.48-0.66 → 0.85 |
| uniform across all 12 | 0.89-0.97 |
| 2-attribute focus | 1.01-1.09 |
| 3-attribute focus | 1.09-1.16 |
| 4-attribute spread | 1.17-1.20 |
| broad / proportional | 1.18-1.20 |

A monotone climb through the sensible strategies with only genuine waste at the floor — deliberately a **plateau, not a peak**. Any scalar quality metric has exactly one optimal allocation, so strategic depth cannot live there; it lives in the distribution half of the accumulator, which has no optimum at all because a shooter and a lockdown defender are both valid outcomes. Quality answers "did you coach this player competently," rewarding a broad range of sensible allocations and punishing only neglect.

The residual gradient is intended: **breadth buys magnitude, focus buys a spike.** A broadly trained player finishes higher overall; a focused one finishes roughly 10 RT lower at Average tier with an attribute above 100. That is the trade the above-100 system is built on.

Uniform-across-twelve sits at 0.89-0.97 rather than the floor. A coverage metric should rate "half-covered everything important" as mediocre rather than as waste, and forcing it lower would require an off-position penalty that fights the points-budget mechanic.

### 17.5 What it is worth

Senior p50 RT at f = 0.85 / 1.00 / 1.20:

| Tier | 0.85 | 1.00 | 1.20 | spread |
|---|---|---|---|---|
| Average | 51 | 60 | 72 | 21 RT (~2.1 buckets) |
| Good | 60 | 70 | 84 | 24 RT |
| Great | 68 | 80 | 96 | 28 RT |
| Elite | 85 | 100 | 120 | 35 RT (~3.5 buckets) |

Senior tier targets sit 10 RT apart, so coaching is worth roughly **±1 tier step**, against a recruiting span of 60 RT from Poor to Elite. Recruiting stays about twice the lever coaching is. The multiplicative form makes coaching matter more at higher tiers, which is intended — elite talent responds most to good coaching.

### 17.6 Current state and the pillar 3 dependency

The mechanic is built and **dormant**. The live path reads coaching quality through a seam that returns `None`, so `f` is 1.0 for every player and the league holds exactly at pass 1.

Activating it requires per-player allocation capture, which is genuinely coupled to the CPU archetype work: user and CPU training run through the same `execute_training` engine with no user/CPU flag inside it, so recording has to be gated at the calling endpoint. It lands with pillar 3 alongside the training-position UI and CPU season-start assignment.

**CPU now trains the reference — this was a live defect, fixed separately.** Until commit `14e4baee9`, CPU auto-train rolled `generate_random_training_allocations` plus `generate_random_coaching_focus`. That produced −9.13 RT/season against a well-coached user's +4.76 — a ~14 RT per-season swing in the user's favour in every franchise — and it would have scored far below 1.0 the moment quality went live, dragging the whole league beneath the ladder.

`auto_train_one_cpu_team` now uses a fixed team-wide reference substrate plus `player-maximizer-custom` focus steering each player to his own position's reference top three. The team-wide/per-position tension is real — one team-wide allocation cannot equal the reference for a point guard and a centre simultaneously — and is resolved by the per-player focus amplifier rather than ignored. Measured per-position quality is 0.984-1.011 with a spread of 0.027; CPU in-season RT moved from −9.13 to −1.23; the user-versus-CPU gap closed from ~13.9 to ~6.0.

`positional-focus` was evaluated and **rejected**: its triple is misaligned with the reference at four of five positions and amplifies off-position attributes at SF (ST) and PF (ID).

**Two coupled calibration constants now exist** — the frozen reference and the CPU base allocation tuned to score 1.0 against it. Neither can be changed alone. `tests/test_cpu_reference_training.py` asserts the relationship so a future change breaks a test rather than silently drifting the league.

Worth recording for future training-side work: training runs on the global `random` module while the engine uses an isolated `sim_random`, so the streams are independent and training changes cannot perturb sim determinism.

**One property is temporary.** Base training points are team-wide, with only the focus amplifier applied per player, so `f` is currently near-identical across a roster — a program-level multiplier rather than per-player coaching. That expires when the planned per-player training focus ships, at which point `f` becomes genuinely per-player. The metric already reads points, so no metric change is needed then — only the capture.

---

## 18. Live validation — what four seasons found

Run on a scratch franchise, five boundaries (season 1 week 1 through season 5 week 1), roughly 2.5 hours per season. The harness (`scripts/season_advance_harness.py`) drives regular weeks 1-26, postseason 27-34 via the bracket driver, week-35 recruiting, and `finish_season`. It is parameterised for N seasons and resumable from the database's current position.

### 18.1 The growth model passed

The failure criterion — compounding erosion of returning players — never triggered. Returning-player attribute nets stayed positive and *grew* every cycle: SC +1.5 → +3.0 → +3.8, SH +0.0 → +1.3 → +2.1. The class-year ladder held, with JR pinned at 54 across all four boundaries. `development` profiles survived the forward copy with writes at 1920/1920, the lazy backfill persisted once per player, and the JH→FR rung executed live for the first time outside Monte Carlo with 326 signed recruits.

### 18.2 The methodology finding

This is the durable output of the run, and it generalises past this project.

| Boundary | Box FG% | Starter SC | Starter SH | Starter FT | Starter RT | Team talent |
|---|---|---|---|---|---|---|
| s1 | 30.4 | 51.9 | 52.0 | 38.5 | 61.5 | 448 |
| s2 | 28.6 | 46.8 | 45.1 | 31.9 | 62.8 | 458 |
| s3 | 23.9 | 38.3 | 37.0 | 22.3 | 63.5 | 455 |
| s4 | 23.0 | 36.1 | 34.9 | 19.5 | 62.3 | 439 |
| s5 | — | 34.0 | 34.9 | 18.8 | 54.7 | 392 |
| total | **−24%** | **−34%** | **−33%** | **−51%** | −11% | −13% |

**RT was the last metric to move, by nearly two seasons.** Box scores degraded from season 1, starter shooting fell steeply from season 2, team talent bent at season 3 — and starter RT held near 62 through four straight boundaries, breaking only once the league had fully turned over. Validating on RT would have read the league as healthy through season 4 while the games had already lost a quarter of their scoring and half their free-throw skill.

The mechanism is structural rather than incidental. **RT is the quantity the growth, ladder and coaching systems all optimise**, so it holds by construction while the attributes that actually produce basketball degrade underneath. It is a weighted mean dominated by core attributes, so the damage sorts by weight: FT, weighted .04-.05 at every position, fell hardest at −51%.

The same failure has a second form one level up. The ladder held perfectly at 35/41/54/60 throughout — because it measures whoever is *labelled* Average, and a mis-tiered player develops correctly on the wrong ladder. **A metric computed against the system's own labels cannot detect the labels being wrong.**

Both are the same rule: **a control variable can never detect its own controller failing.** Every acceptance check therefore needs metrics the system does not optimise — starter or minutes-weighted attribute means and box-score aggregates, never RT, and never whole-roster means, which bench composition dilutes.

### 18.3 What the run isolated

Three defects, none of which unit tests or the Monte Carlo could see:

- **CPU auto-train allocated randomly** (`generate_random_training_allocations` + `generate_random_coaching_focus`), producing −9.13 RT/season against a well-coached user's +4.76 — a ~14 RT per-season swing in every franchise, and a normalisation that would have dragged the league beneath the ladder the moment coaching quality went live. Fixed at `14e4baee9`; see §17.6.
- **In-season attribute rot.** Every attribute trained at base-1 lost 7-9 points per season, and the offseason — being RT-targeted and core-weighted — regrew only the core, so the erosion compounded. Fixed at `af7c784ee`; see §18.4.
- **Recruit supply.** The recruit pool was capped at 300 against ~440 graduations, so walk-ons absorbed the difference every year and climbed toward a ~40% share against a designed 20%. Pool raised to 400. This restores the walk-on floor; it does **not** own the box-score decline, an earlier conclusion that the acceptance run disproved — starters are the top five by rating and are never walk-ons, so bench composition cannot move them.

### 18.4 In-season rot — diagnosis and the invariants

The rot was localised to base-1 allocations rather than global. League-average net per attribute per season by allocation level: base-0 −34.9, base-1 −10.7, base-2 −1.4, base-3 +1.0, base-4 +5.7, base-5 +8.0. Base-2 and base-3 were already flat, so a global decay or gain-scale rebalance would have over-inflated them and reopened the claw-back constraint. The fix was surgical — unify the reference band's gain range at points 1 through 3 — which leaves base-0 declining at −34.9 so the cost of neglect survives.

**The invariant, stated properly, is not "nothing rots."** It is: *a player trained at the reference allocation holds steady across all attributes; deviation from the reference is what causes decline.* Reference holds flat, neglect costs, focus gains.

This was the third in-season retune. The model is now pinned by assertions rather than by tuned constants that drift:

1. reference allocation → each on-position attribute nets ≈ 0 over a season (|Δ| < 3)
2. reference allocation → RT/season stays below the smallest rung increment
3. a base-0 attribute declines (< −5 over a season)
4. **the full cycle** — season plus rollover — holds, with no attribute eroding

Invariant 4 exists because this defect survived a complete validation pass: the season eroded and the offseason failed to restore, while RT held throughout. Any invariant a top-line metric can mask needs its own assertion.

Acceptance was a trained-versus-untrained comparison on the same instrument and seed: FG% 33.1 (broken) → 36.97 (fixed) against 37.5 untrained.

### 18.5 Entry-tier down-classification

The largest defect the run surfaced, and it is a dropped field rather than a model error.

`generate_recruits_list` stamps `entry_tier` correctly (Poor 7 / Average 39 / Great 11). The season FRD write dropped it, along with `position_intent` and `development`. A signed recruit therefore reached FPD with no tier, and `develop_rollover` re-derived one from the recruit's *undeveloped JH* rating of ~31 — reading a JH's low rating as a low tier and shifting every recruit down roughly 1.5 tiers. The derived value then persisted and compounded.

| | Poor | BelowAvg | Average | Good | Great | Elite |
|---|---|---|---|---|---|---|
| True (generated) | 7 | 21 | 39 | 20 | 11 | 2 |
| Derived (the bug) | 27 | 39 | 21 | 11 | 2 | 0 |
| Live freshmen | 26 | 40 | 22 | 9 | 3 | 0 |

The derived and live distributions match almost exactly, which is the proof. It explains why rating held while shooting fell — a level effect with shape preserved — why the recruit-pool increase did nothing for box scores, and why a franchise looks healthy in season 1 and regresses as the correctly-tiered initial pool graduates.

**A second bug lived inside the first.** `_derive_entry_tier_from_rt` was **year-blind**. Tier anchors are JH-scale (Poor 20 … Elite 50) while the ladder multiplies by rung, up to 2.0× at senior, so mapping a raw rating to a tier without dividing by the rung multiplier misclassifies *every non-senior*: an Average freshman at 35 reads Poor, an Average junior at 54 reads Below Average. Only seniors derived correctly, by coincidence — which also means the legacy-backfill path described in §10 had been down-classifying far more broadly than the RT-collapsed bigs noted there.

Fixed at `ae98d9a59` and `f3f02bab4` in three parts: persist the three fields on the FRD write; make the derivation year-aware via a shared `entry_tier_at_year(ratings, current_year)` helper; and make the fallback log loudly, with a test asserting a generated recruit round-trips FRD → FPD → rollover with its tier unchanged. Two further paths that dropped the fields — the roster-editor builder and the `stat_updater` safety-net — now carry them explicitly rather than relying on the derive.

**Why explicit carry rather than trusting the derive:** derive-from-rating is correct today only because the coaching multiplier is dormant at `f` = 1.0. Once §17 activates, ratings diverge from the ladder by up to ±20% — a well-coached Average senior at 72, a neglected one at 51 — against senior tier bands 10 apart. That is more than a full tier step, so the derive would silently misclassify again.

**Existing saves are not repairable.** The true tier is gone from every source: the FRD document is overwritten and never stored it, the frozen recruit set carries no tier, and rolled documents hold only the wrong derived value with no link back. Consistent with §14, they degrade and partially self-heal over roughly four seasons as mis-developed players graduate; new franchises are correct from creation.

### 18.6 Process notes

- The run's per-boundary snapshots were written to a local temporary directory and not retained, so the height trend could not be reconstructed afterwards from ten hours of runtime. Measurement output belongs somewhere durable.
- The postseason weeks require the bracket driver rather than the weekly advance, which returns a conflict once the user's team is eliminated.
- Season 1 of every fresh franchise seeds from a frozen 300-recruit set rather than the dynamic count, so a new franchise carries a one-time supply gap of ~130 spots. `set_0001` is a designed first class and expanding it to 400 requires bespoke imagery for the additional recruits.
