# Attribute Calibration — Measurement Spec

**Purpose:** establish what the attribute scale and progression actually look like, in numbers, so future tuning argues against measurements rather than impressions.

**Not a tuning exercise.** This is a read of the world as it stands after the pass-2 fixes. Do not change any constant in response to what it shows.

## Ground rules

- **Percentiles, not standard deviations.** Almost every distribution here is deliberately skewed — the tier ladder is 7/20/40/20/11/2, and offseason gains are multi-modal because a peak year and a non-peak year are different populations. Report **p10 / p25 / p50 / p75 / p90**, plus min and max. Where a distribution genuinely looks symmetric, an SD is a useful addition, not a replacement.
- **Measure `anchor_` attributes**, never live/fatigued values.
- **Prefer starter-weighted to whole-roster means.** Bench composition diluted the signal badly in the four-season run. Where a roster-wide figure is reported, report the starter figure beside it.
- **Report progression in display units as well as raw points.** Attributes display on the 1-10 scale, so a +3 raw gain reads as +0.3 on screen. Both numbers, always — the question "would a user notice this?" is only answerable in what they see.
- **Read-only.** No writes, no code changes. Use the migrated pool and the Phase 4 run's existing boundary snapshots wherever possible rather than generating new runs.

---

## 1. Franchise start — what a new user's league looks like

Measured on a fresh franchise initialized off the migrated pool.

**Team strength, per team (128 teams):**

| Metric | Definition |
|---|---|
| Starter strength | mean RT of the projected starting five, at each player's best position |
| Depth | mean RT of the 6th-10th players |
| Top-end | best player's RT |

For each of those three: p10 / p25 / p50 / p75 / p90, min, max. Name the actual best and worst team.

**The gap that matters:** how far apart are the p90 and p10 teams in starter strength, in RT and as a percentage? That is the answer to "how much better is a good team than a bad one at franchise start."

**Roster composition of the median team:** RT of each of the 15 players, sorted. This shows the drop from starter to bench in one line.

**League-wide player distribution:** RT percentiles across all 1,920 players, plus the same split by class year and by entry tier.

---

## 2. Offseason progression

From the Phase 4 boundary snapshots — the same players tracked across rollovers.

**Per-player RT gain per offseason**, at p10 / p25 / p50 / p75 / p90, min, max — **split by peak count (0 / 1 / 2 / 3) and aggregated.** Splitting matters: peaks are the largest variance driver, and a lumped distribution describes nobody.

Also split by class-year rung (JH→FR, FR→SO, SO→JR, JR→SR), since rung increments differ.

**Per-attribute gain per offseason**, same percentiles, for the position's signature attributes and its non-signature attributes separately. In raw points and display units.

**Height and weight gain per offseason**, same percentiles, split by class-year rung. This is also the longitudinal check that the HT curve fires — the same players across boundaries, not the class-year cross-section.

**The headline question:** what does a median player's RT gain feel like on the 1-10 display, and what does a 3-peak player's look like? If both round to the same displayed number, progression is invisible regardless of what the data says.

---

## 3. Recruits — measured relative to rosters, not in isolation

Absolute values first: RT at p10 / p25 / p50 / p75 / p90, min, max, and the same by entry tier.

**Then the question that actually matters:** where does a recruit land on the roster he joins?

- What percentile of an existing roster is the median recruit? The p90 recruit? The p10?
- What share of recruits would crack the starting five immediately? The top ten? Neither?
- How does a signed recruit's RT compare to the player whose graduation opened the spot?

That last one is the direct read on whether recruiting replaces what a team loses.

---

## 4. Walk-ons

Same absolute percentiles, and the same roster-relative framing.

**The specific question:** is a walk-on a warm body or a contributor? What share ever reach the top ten of their roster, and how does the best walk-on in the league compare to a median recruit?

Walk-ons are ~20% of the league by design, so if they are pure filler that is a large share of the league doing nothing.

---

## 5. In-season training

From the Phase 4 per-week movement capture.

**Per-player RT change across a season**, percentiles, split by allocation policy where the data allows — CPU reference versus the harness's user-team policy.

**Per-attribute weekly movement**: mean net and mean absolute change, for signature and non-signature attributes separately. In raw points and display units.

**The perceptibility question, which is the point of this section:** how many weeks of training does it take for a single attribute to move one full display unit — a 1-10 step? If the answer is more than a few weeks, the training report shows nothing happening whatever the underlying data says.

---

## 6. Season-over-season team strength

Not in the original list, and the most important section.

For each team, across each boundary: change in starter strength, in RT and as a percentage. Percentiles across the 128 teams.

- What does the median team gain or lose per season?
- What does the p90 team do — and is it the same team each year, or does strength rotate?
- How much of a team's change is graduation, how much development, how much recruiting?

This is the original question that started the project ("anecdotal steep team-talent dropoff from season 1 to season 2"), and it is the most direct read on whether progression feels like anything from the user's chair.

---

## Deliverable

One report, tables throughout, minimal prose. Every figure in raw units with the display-scale equivalent beside it wherever a user would see it.

Flag anything that looks wrong, but **do not fix it in this pass.** The point is to establish the baseline; tuning decisions come after, argued against these numbers.
