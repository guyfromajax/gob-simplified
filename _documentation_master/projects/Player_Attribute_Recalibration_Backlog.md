# Player Attribute Recalibration — Deferred Backlog

**Repo path:** `_documentation_master/projects/Player_Attribute_Recalibration_Backlog.md`
**Companion to:** [`Player_Attribute_Recalibration_Design.md`](Player_Attribute_Recalibration_Design.md) (working doc) and [`Player_Attribute_Recalibration_Brief.md`](Player_Attribute_Recalibration_Brief.md)
**Last updated:** 2026-07-30

Items deferred from the recalibration, each with a **trigger** rather than a date. Several outlive the project — this file is intended to survive the design doc's move to `Z-Completed/`.

Status key: **OPEN** · **ACCEPTED** (a known consequence, deliberately not fixed) · **DONE**

---

## Blocks the coaching-quality system going live

**CPU auto-train must allocate the reference.** *Trigger: pillar 3 (CPU training).* **OPEN — hard requirement, not optional.**
Measured in-season net: reference coaching +4.76 RT/season, CPU-actual −9.13. CPU uses `generate_random_training_allocations` + `generate_random_coaching_focus`. The coaching-quality normalisation assumes CPU ≈ reference so CPU scores 1.0 and the league sits on the ladder; with random allocation CPU scores well below 1.0 and the whole league drifts under it. CPU must train the frozen reference, or archetype-modulated variants distributed around it.

**Transitional competitive imbalance.** *Trigger: resolved by the item above.* **OPEN.**
Until CPU allocation is fixed, a sensibly-coached user gains ~+5 RT/season while CPU teams sag ~−10 — a ~15 RT per-season swing in the user's favour, live on `develop` today. Does not compound across seasons (the offseason re-anchors), but alpha difficulty feedback gathered before the fix is measuring the artifact rather than the game.

**Per-player allocation capture.** *Trigger: pillar 3.* **OPEN.**
`_coaching_accumulator_for_player` returns `None`, so `f` = 1.0 for everyone and the coaching multiplier is dormant. User and CPU training share one `execute_training` engine with no internal user/CPU flag, so recording must be gated at the calling endpoint (user persist block `franchise_routes.py:13573`, never the CPU block `:2408`).

**`training_position` UI and CPU season-start assignment.** *Trigger: pillar 3.* **OPEN.**
The field exists, is persisted, defaults to `position_intent`, and is forward-copied at rollover. Nothing sets it. Needs the user interface (showing projected RT impact of a conversion) and the CPU rules — depth-chart holes over two seasons, height permitting, adjacent positions preferred, never convert a senior.

---

## Validation still owed

**Multi-season validation harness.** *Trigger: after CPU allocation is fixed.* **OPEN.**
No create-and-advance-four-seasons driver exists. `eog_measurement_season.py` runs regular weeks 1-26 only. Building one needs postseason weeks 27-34 driven headless (never exercised), a `run_week_35_recruiting` auth workaround (that route has `Depends(get_current_user)`), and a rollover loop. Held deliberately: running it while CPU teams decay ~10 RT/season would measure the artifact. Cost is ~8 hours locally; running co-located with the DB would cut it several-fold, since `finalize_game` persistence latency dominates and the engine does not.

**Mid-season training-position switch penalty (§9.4).** *Trigger: after `training_position` UI exists.* **OPEN.**
Structurally unmeasurable in the Monte Carlo — under a no-user-focus policy the accumulator collapses to the position weights. Needs a live season with a real user-focus policy.

**Weekly movement visibility (§7.2), live.** *Trigger: live season with a user-focus policy.* **OPEN.**
Confirmed in memory over 1,920 players: under reference coaching, net per-attribute change ≈ 0.000 with mean |Δ| 0.52/week — attributes move visibly while RT stays flat. Not yet confirmed against a real played season.

**JH→FR rung, live.** *Trigger: first real rollover with signed recruits.* **OPEN.**
The Step B dry run loaded FPD only, so the JH→FR transition was never exercised — the franchise has no JH players and pool freshmen roll to SO. That rung fires only for signed recruits and remains validated by Monte Carlo alone.

**PS-parity anchor (`--mode both`).** *Trigger: when a durable PS fixture exists.* **OPEN.**
The current anchor is CPU-only because the PS reference franchise `6a5e1f0e517ebcc58d981675` was deleted from shared staging. A single-arm anchor gives *false* confidence: a refactor breaking PS-only code returns a clean exact-diff. Preferred fix is a harness that creates its own fixture rather than pointing at a franchise anyone can delete.

---

## Display sweep

**Attribute and RT display consolidation.** *Trigger: independent — can run any time.* **OPEN.**
All attributes on the 1-10 scale (extending to 11, 12, 13+ past 100), RT on 1-100, every scaling toggle removed. Attribute bars fill on the 1-100 scale with the 1-10 value beside them; all bars scale to 100 and pin above it. Roughly 25 frontend surfaces: training report, roster displays, set-lineup, recruiting pages, player profile, and 16 static team-roster demo pages.

**CH tooltip conflict.** *Trigger: with the display sweep.* **OPEN — design conflict.**
`attributeTooltips.js:7` carries a CH tooltip labelled "Clutch", which means CH is surfaced somewhere today. §8 states CH is never displayed. Either the surface is found and removed, or §8 is aspirational.

**`attributeDisplay.js` consolidation.** *Trigger: with the display sweep.* **OPEN.**
A canonical helper already exists with no importers, while the ÷10 transform is duplicated across ~15 files. Two surfaces show raw 1-100 instead: `training-report.js:1121` and `scoutingReport.js:85`. The tutorial's "Attribute Scale" legend still documents 0-100 bands.

**Player profile changes.** *Trigger: with the display sweep.* **OPEN.**
`OVERALL` becomes the training position's RT rather than max RT; the training position is highlighted in orange in the position list; `MOMENTUM` is replaced by `POSITION`. Momentum needs a new home if the profile is currently its only surface. Recommended addition: a quiet secondary marker on the highest RT when it is not the training position, so a user converting a player can see the cost.

---

## Tuning to revisit in gameplay

**Above-100 frequency.** *Trigger: user testing.* **ACCEPTED.**
Lands at 7.5% of the pool and 19.0% of seniors against an originally-accepted 5.5%. Structural — reaching Elite senior RT 100 through a weighted mean with a concentrated weight (SG's SH at .42) forces high-tier seniors to carry a 100+ attribute. Locked; to be judged in play rather than tuned.

**In-season per-season RT swing.** *Trigger: user testing.* **ACCEPTED.**
p10 −14 / p90 +13 RT within a season. Accepted as-is pending feel.

**Backfill peak skew.** *Trigger: if development reads as muted in a franchise's first three seasons.* **OPEN.**
Backfilled mid-career players hold peaks only on remaining rungs, so the league skews toward one peak (20.1/62.1/16.3/1.5 vs 20/55/22/3) until they graduate. Arguably a feature — inherited players are what they are and multi-peak stars come from players you recruited. Fix if needed: roll peaks per remaining rung rather than rolling a career count and truncating.

**Blanket-vs-custom training tax.** *Trigger: when per-player training focus is built (~Sept 2026).* **OPEN.**
The ~2-point tax costs 0.024-0.047 quality (f 0.95-0.98) per position, but that is not the real decision. The real comparison is one blanket allocation across five position types at 24 points versus five tailored allocations at 22 — roster-diversity dependent, and it needs measuring on a real roster. The tax is a feature parameter, not a metric parameter.

**Recency weighting on cumulative coaching quality.** *Trigger: if career length grows (JUCO, redshirt years).* **OPEN.**
Evaluated and rejected: at four seasons with a clamped band it moves `f` by a fraction of a display bucket, not worth the parameter.

**Shot calibration.** *Trigger: a dedicated shot-calibration pass.* **OPEN — pre-existing, not this project's.**
FG% 37.5% and 3PT% 25.3% against real college basketball's ~44% and ~33%. The pre-recalibration anchor was already low at 39.1% and 28.4%, so this predates the recalibration, which moved it slightly further that way.

**Recruit archetype label variety.** *Trigger: if recruiting pages feel flavourless.* **OPEN — cosmetic.**
The 20 archetype display strings collapsed to 5 derived from (intent, tier). Could be restored as a cosmetic descriptor derived from attribute shape.

---

## Accepted consequences for existing saves

**Distorted RT for bigs.** **ACCEPTED.**
Existing franchises keep old-scale short players while gaining height-gated PF and C ratings, so interior players' ratings collapse. Deliberately not migrated; the recalibration is new-franchises-only.

**Shot-blocking effectively gone.** **ACCEPTED — documented so it is not misdiagnosed.**
`height_to_block_score` returns 0 at or below the league median of 78, and an old-scale roster's p90 height *is* 78. A "nobody blocks shots on my save" report is this, not a bug.

**Legacy `entry_tier` derivation.** **ACCEPTED.**
A legacy player with no `entry_tier` has it derived from current RT, which misclassifies players whose RT collapsed under height gating — a distorted big reads as Poor and then develops on a Poor ladder, compounding the degradation above.

---

## Documentation

**Harvest into evergreen system docs.** *Trigger: project close.* **OPEN.**
The design doc is organised by decision narrative and is ~66k characters; it should move to `Z-Completed/` as the record of how decisions were made, not become the evergreen reference. Durable content harvests to:

| Destination | Content |
|---|---|
| `10_Players_Systems/Player_Attribute_System.md` | ladder, tiers, families, growth profile, peaks |
| `10_Players_Systems/Position_Ratings_System.md` | new RT formula, multiplicative height fitness |
| `10_Players_Systems/Player_Development_System.md` *(new)* | the offseason development event |
| `09_Training_Systems/Training_System.md` | coaching quality, in-season model |
| `11_Design_Systems/Tunable_Constants.md` | done |

**Stale-doc audit.** *Trigger: with the harvest.* **OPEN.**
Agents have repeatedly found system docs describing removed behaviour — the distant-sim sections in `balancing_team_attributes.md` and `End_Of_Game_System.md`, wrong function names, half-stale schemas. Worth one sweep listing which docs now lie, since that is what future agents are briefed from.

**Update the brief.** *Trigger: project close.* **OPEN.**
`Player_Attribute_Recalibration_Brief.md` still describes the original suspicion and no longer resembles what the project became. It is the entry point.

---

## Downstream dependencies this project created

**Archetype threshold recalibration.** *Trigger: pillar 3.* **OPEN.**
Team-identity thresholds were explicitly parked pending recalibrated attributes — the existing `cum_nd` 200/350 cutoffs sit essentially on the league median and route 53% of teams into a "weak" branch. They must be re-derived against the new distributions.

**EOG attribute retune.** *Trigger: after pillar 3.* **OPEN.**
Parked behind this project. Note `momentum_score` removal was deliberately deferred out of the distant-sunset cleanup to avoid changing training draw counts mid-flight.

---

## Found during validation (separate from recalibration)

**Recruit-supply / walk-on-floor calibration.** *Trigger: standalone.* **OPEN — HIGH PRIORITY.**
Surfaced by the 4-season live run: the season recruit pool is `count=300` (`load_unused_set_or_generate`), but graduation is **~440/season** (measured: 429, 455), so **~150 spots/season are backfilled by Poor-tier walk-ons**. Walk-on league share climbs **26% → 29% → 33%** (s1–s3) toward a ~40% steady state — vs the designed **~20%** (3 of 15 = the Poor floor). Degrades **every** franchise progressively (≈40% walk-ons by ~season 10). Departure basis (measured, year-normalized): graduation ~429–455/yr; extra departures (128, 43) are young **walk-on cuts**, not a hidden non-walk-on drain — so the pool target is driven by graduation, not inflated by attrition. Fix: size the season pool to **~450–500** (≈400–445 to meet demand + an unsigned surplus so recruiting stays **contested** — do NOT size exactly to demand: that drives walk-ons to zero, deletes the designed floor, and makes recruiting uncontested). **Recruit-generation change only** — does NOT touch the in-season or CPU-training model (both validated). Do not fix mid-run; it would invalidate the trend the current run is measuring.

**Recruit `entry_tier` down-classification (turnover regression).** *Trigger: standalone.* **OPEN — HIGH PRIORITY, root cause confirmed 2026-08-01.**
The box-score decline (found FG% 30→23, 3PT% 21→14 across a turnover; starter SC 54.5→37.7, SH ~33% over a franchise's first four seasons) is a **level/tier collapse**, not walk-on supply and not a growth-model shape problem. Confirmed root cause, proven end-to-end:
- **`generate_recruits_list` is correct** — tiers Poor 7 / BelowAvg 21 / Avg 39 / Good 20 / Great 11 / Elite 2, `entry_tier` stamped on each recruit.
- **The FRD write drops it.** `franchise_routes.py:15169–15187` persists `attributes/year/archetype/...` but **omits `entry_tier`** (also `position_intent`, `development`). So a signed recruit reaches FPD with no `entry_tier`.
- **`develop_rollover` (`player_development.py:533`) then re-derives it** — `entry_tier = fpd.get("entry_tier") or _derive_entry_tier_from_rt(ratings, rung)` — from the recruit's **undeveloped JH RT (~31)**. The derivation back-solves an anchor assuming the player is *at* his final rung, so a JH's low RT reads as a low tier. Every recruit is shifted down ~1.5 tiers, `jh_anchor` is set low, and he develops on the wrong ladder **permanently** (the derived tier is then persisted, so it compounds).
- **Proof** — derive-from-RT applied to freshly generated recruits reproduces the live roster almost exactly:

  |            | Poor | BelowAvg | Avg | Good | Great | Elite |
  |---|---|---|---|---|---|---|
  | TRUE (generated) | 7 | 21 | 39 | 20 | 11 | 2 |
  | DERIVED (the bug) | 27 | 39 | 21 | 11 | 2 | 0 |
  | LIVE non-walk-on freshmen | 26 | 40 | 22 | 9 | 3 | 0 |

This is why RT held while shooting fell (level effect, shape preserved → the generation-vs-development *shape* hypothesis was tested and **refuted**: normalized vectors match, weight↔shape-gap corr +0.69/−0.27/+0.20; `NON_CORE_GROWTH_MULTIPLIER` is not the lever), and why the `400` supply fix did nothing for box scores (more recruits, all still down-classified). The initial franchise pool carries correct `entry_tier` (created directly in FPD), so a franchise looks healthy at s1 and regresses as that pool graduates and down-classified recruits take over.
**Fix:** persist `entry_tier` (and `position_intent`, `development`) in the FRD write so signing carries it to FPD (`franchise_manager.py:537` already forwards it *if present*). New-franchise-facing; needs a fresh multi-season run to confirm box-score/starter recovery. **Secondary, separate:** the generation ladder (`RUNG_MULTIPLIERS`, SR = 2.0×anchor) and the development ladder (`STD_RUNG_INCREMENT` sum = 1.70×anchor + `PEAK_BONUS` 0.3/peak) disagree on level — real but makes development *higher*, so not the regression cause; revisit only after the entry_tier fix.

**Acceptance criterion = walk-on share, NOT box scores.** *(Corrected 2026-08-01.)* The `300→400` fix (shipped `423c320ee`) was validated on a fresh 4-season scratch: live walk-on share fell **42.4% → 27.3%** (trending to ~20% at full saturation), and recruiting counts rose. **That is the fix's real and only criterion.** An earlier version of this item claimed the supply fix would also recover starter SC/SH and box FG%/3PT% — **that was wrong.** The acceptance run's starter SC (34.6) and box FG% (22.9) were superimposable on the pre-fix baseline: the box-score collapse is owned by a *separate* bug (see "Recruit entry_tier down-classification" below), because starters are never walk-ons, so restoring the walk-on floor cannot touch them. Whole-roster attribute means remain the wrong statistic for anything (bench dilution); RT remains a targeting signal, not a health signal.
