# Attribute Calibration — Measurement Specification

**Status:** Retained measurement backlog, refreshed 2026-08-08. No single completed report covering
all sections was found. The archived four-season validation answered part of the progression and
team-strength work, but roster-relative recruit and walk-on questions remain open.

**Purpose:** establish what the current attribute scale, roster composition, and progression look
like so tuning is argued against measurements rather than impressions.

This is not authority to tune constants or mutate a database. Analysis should be read-only. If a
new longitudinal dataset is required, producing it with `scripts/season_advance_harness.py` is a
separate mutating task that requires an explicitly disposable staging franchise.

## Current model assumptions

Measurements must use the current framework, not the July pass-2 model:

- Offseason development is level-only (`OFFSEASON_ATTRACTOR_ALPHA = 0.0`); camp and in-season
  training own shape.
- `potential_factor` is live and widens outcomes within a tier.
- CPU auto-training uses the fitted reference path, not random allocation.
- Dynamic recruit classes and `set_0001` are currently sized to 450.
- Walk-on roster years are drawn directly as FR/SO/JR/SR = 10/40/40/10; there is no JH advance in
  that path.
- Coaching factor `f` remains dormant at 1.0 until per-player allocation capture ships.

Canonical mechanics: [`Player_Attribute_System.md`](../10_Players_Systems/Player_Attribute_System.md),
[`Player_Development_System.md`](../10_Players_Systems/Player_Development_System.md), and
[`Training_System.md`](../09_Training_Systems/Training_System.md).

## Measurement rules

- Report p10 / p25 / p50 / p75 / p90, min, max, and sample size. Add mean/SD only when useful; do
  not replace percentiles for skewed or multimodal populations.
- Measure persisted `anchor_` attributes where both anchor and live/fatigued values exist.
- Report starter-weighted and roster-wide results side by side. Never infer starter health from a
  whole-roster mean.
- Report raw attribute points and intended display units (`raw / 10`) together where perceptibility
  matters. The frontend display consolidation remains incomplete, so name the actual surface used.
- For longitudinal comparisons, match the same `player_id` across boundaries. Cross-sectional
  class comparisons do not prove development.
- Stratify before interpreting: class year, `entry_tier`, peak count, position/training position,
  and `potential_factor` band can each explain real mixture effects.
- Record database, franchise ID, season/week, Git SHA, dataset path, and extraction timestamp.

## Dataset strategy

Use two explicitly separate datasets:

1. **Current cross-section:** a fresh franchise initialized from the current pool. This supports
   league, roster, recruit, and walk-on comparisons without advancing the save.
2. **Longitudinal boundaries:** durable snapshots from a current multi-season harness run. The old
   Phase 4 boundary files were temporary and were not retained, so do not claim they are available.

Do not combine historical pass-2 snapshots with a current cross-section as if they represent one
model version.

## 1. Franchise-start league

For each of 128 teams calculate:

| Metric | Definition |
|---|---|
| Starter strength | Mean RT of the projected starting five, using the canonical lineup helper |
| Depth | Mean RT of players ranked 6–10 by the same roster-selection basis |
| Top end | Highest player RT |

Report the percentile set for all three, the named best/worst teams, and the p90–p10 starter gap in
RT and percent. For the team nearest median starter strength, list all 15 player RTs in descending
order. Report league player RT by class, entry tier, position, and potential-factor quintile.

## 2. Offseason progression

Match returning players immediately before and after each rollover. Report RT and per-attribute
change by rung (JH→FR, FR→SO, SO→JR, JR→SR), peak count, and potential-factor quintile.

For attributes, split the player's training-position top-three from other core attributes and show
raw/display-unit movement. Report HT/WT longitudinally by rung. Separate the level-only offseason
change from camp/in-season change; combining them would hide which force moved shape.

Headline outputs:

- median and p90 RT gain per rung;
- median signature/non-signature attribute movement;
- zero/one/two/three-peak career curves;
- the share finishing below, at, or above displayed Potential Rating.

## 3. Recruits relative to destination rosters

Report recruit RT percentiles overall and by entry tier/year, then join signed recruits to their
destination team's pre-signing roster:

- recruit percentile within that roster;
- share entering the projected starting five, top ten, or neither;
- signed recruit RT versus the graduating player(s) whose departure created capacity;
- results by prestige/recruiting-strength band so one league-wide mean does not hide allocation.

Keep generated pool, signed subset, and active-roster entrant separate. Selection changes the
distribution.

## 4. Walk-ons relative to rosters

Use the same absolute and destination-relative tables as recruits. Report:

- share entering the top ten at arrival and before graduation;
- best walk-on versus median signed recruit;
- contribution by class year and seasons remaining;
- steady-state roster share after the season-1 cohort clears.

Do not reuse the old “~20% therefore freshman-heavy” premise. Current walk-on years are drawn
directly 10/40/40/10, while the recruit supply is 450; measure the resulting steady state.

## 5. Camp and in-season training

From weekly matched-player snapshots, report season RT change and mean net/absolute per-attribute
movement under CPU reference and representative user policies. Split training-position top-three
from neglected attributes and camp from regular-season weeks.

Perceptibility output: distribution of weeks required to cross one raw point and ten raw points
(one intended 1–10 display unit), plus the actual training-report indicators users see while the
numeric value has not crossed a bucket.

## 6. Season-over-season team strength

For each team and boundary, report starter strength change and decompose it into:

- graduation/removal;
- returning-player development/training;
- recruits and walk-ons entering the roster;
- lineup-selection change.

Track rank persistence: how many p90 teams remain p90 one, two, and three seasons later? Report both
team-level rotation and league-wide percentiles. Attribute/minutes-weighted and box-score measures
must accompany RT because the archived validation proved RT can remain stable while basketball
attributes deteriorate.

## Deliverable and completion gate

Produce one versioned report with tables, provenance, extraction code/query reference, and links to
the underlying machine-readable artifacts. Mark each section complete, unavailable, or blocked;
do not silently omit a requested split.

The measurement is complete only when:

- static and longitudinal datasets are version-compatible;
- every percentile includes `n`;
- starter and roster-wide readings are both present;
- recruits/walk-ons are evaluated relative to destination rosters;
- team-strength change is decomposed rather than merely described;
- findings are copied into the canonical system doc or active backlog before this spec is retired.

Flag anomalies, but make no gameplay or tuning change in the measurement pass.
