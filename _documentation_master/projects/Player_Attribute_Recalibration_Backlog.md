# Player Attribute Recalibration — Deferred Backlog

**Status:** Active follow-on backlog. The recalibration itself is complete and archived in
[`Player_Attribute_Recalibration_Design.md`](Z-Completed/Player_Attribute_Recalibration_Design.md).
Canonical behavior lives in the player, position-rating, development, and training system docs.

This file contains only unresolved or deliberately accepted follow-ons. Completed work is removed
rather than retained as a second history; Git and the archived design preserve that record.

## Coaching-quality activation

### Per-player allocation capture — open

`_coaching_accumulator_for_player` still returns `None`, so offseason coaching factor `f` is `1.0`
for every player. User and CPU training share `execute_training`; capture must be gated at the
calling endpoint so user allocations are attributed correctly without treating CPU execution as a
user decision.

CPU reference auto-training is already shipped and tested. The old random-CPU allocation defect
and its projected ~15 RT user advantage are resolved; do not reopen them from older project notes.

### Training-position control — open

`training_position` exists, persists, defaults to `position_intent`, and is carried through
rollover, but it has no user write surface or CPU season-start assignment policy. The future UI
should show the projected RT/conversion cost. CPU rules still need product agreement; the prior
proposal was to prefer adjacent positions for persistent depth-chart needs, respect height, and
avoid converting seniors.

### Mid-season switch penalty — blocked by training-position control

Measure and decide the switch penalty only after the live write path and a real per-player focus
policy exist. The prior Monte Carlo could not express this decision.

## Validation still owed

- **Weekly movement in a played season:** in-memory validation proved attributes move while
  reference-coached RT stays broadly flat, but the user-facing weekly feel still needs live play.
- **JH→FR live rollover:** unit/Monte Carlo coverage exists; confirm the first real rollover of
  signed recruits.
- **Practice Squad parity fixture:** the exact-diff harness needs a self-created durable PS fixture
  instead of a shared staging franchise that can disappear.

The reusable full-season/multi-season driver now exists as `scripts/season_advance_harness.py` and
the four-season validation has been completed. “No multi-season harness” is no longer an open item.

## Display and profile consolidation

- **Attribute display sweep:** converge player attributes on the intended 1–10 presentation while
  RT remains a letter/1–100-derived grade; remove duplicated transforms and stale scale toggles.
- **`attributeDisplay.js`:** the canonical helper still has no broad importer adoption; duplicated
  formatting remains across frontend surfaces.
- **CH visibility:** `attributeTooltips.js` still defines CH as “Clutch,” while the recalibration
  design treated CH as hidden. Decide whether the display is intentional before removing either
  the tooltip or the hidden-field claim.
- **Player profile:** decide whether OVERALL follows `training_position`, how a higher alternate
  position is signaled, and whether MOMENTUM remains on the profile. This depends on the
  training-position product decision above.

Potential Rating itself is shipped and is not part of this display debt. Its canonical formula and
surface contract live in `Player_Development_System.md`.

## Gameplay and progression tuning

- **Above-100 frequency — accepted pending play:** approximately 7.5% of the pool and 19% of
  seniors have at least one attribute ≥100. Judge in play; do not tune solely to an old 5.5% lock.
- **In-season RT swing — accepted pending play:** the calibrated distribution is intentionally
  broad. Re-measure against the current post-framework gain path before changing it.
- **Backfilled peak skew:** inherited mid-career players can only place peaks on remaining rungs,
  temporarily skewing early franchise seasons toward one-peak careers. Revisit only if development
  feels muted before generated cohorts replace the inherited pool.
- **Blanket-versus-custom training tax:** measure when per-player training-position/focus controls
  are live; it is roster-composition dependent.
- **Recency weighting:** rejected for four-year careers. Reopen only if JUCO/redshirt support makes
  careers materially longer.
- **Shot calibration:** remains a separate gameplay calibration effort, not a player-recalibration
  fix.
- **Recruit archetype labels:** optionally restore richer cosmetic labels derived from current
  shape if recruiting presentation feels too uniform.
- **Recruit generation variety:** init `recruit_sets` measured wider than dynamic post-rollover
  generation (mean attribute σ roughly 15.7 vs 11.6). Determine whether that branch difference is
  intentional before changing either generator.

## Existing-save consequences — accepted

- Old-scale saves are not migrated onto the recalibrated physical/RT distribution; new cohorts
  replace them over time.
- Legacy players missing `entry_tier` derive it from current RT, which can misclassify distorted
  old-scale bigs. This is accepted rather than guessed backward from incomplete history.
- Player block-height behavior follows the current `LEAGUE_MEDIAN_HEIGHT_IN` constant (75); older
  notes based on 77/78 are historical.

## Downstream systems

- **Archetype thresholds:** re-derive team-identity thresholds against recalibrated distributions
  when that system is next tuned.
- **EOG attributes:** the EOG band retune remains open and has its own measurement runbook.
- **Program persistence:** four-season validation found recruiting has more influence on roster
  strength than development and elite programs rotate quickly. If durable program quality is the
  goal, tune prestige→recruiting outcomes rather than widening initial rosters.

## Adjacent documentation debt

Some tournament, Practice Squad, rank/prestige, and championship documentation still uses
“distant” terminology after the distant simulation/training engines were retired. Audit those
documents before using their old route descriptions as implementation guidance.
