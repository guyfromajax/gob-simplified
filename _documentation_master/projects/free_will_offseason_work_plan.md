# Free-Will Offseason — Work Plan

**Goal.** Make in-season training decisions (user **and** CPU) have permanent, career-long impact on how a player develops — shift the offseason from **predestination** (rescale every player onto his tier-anchored ladder RT, which *absorbs* in-season) to **free will** (add a *reduced* offseason increment on top of where in-season left him, so coaching **persists**).

**Core change.** `develop_rollover` (`BackEnd/utils/player_development.py`): absolute-target rescale → additive increment, with the post-season rungs reduced so a *reference-coached* league still anchors.

**Status.** Design agreed in principle; nothing implemented. This plan sequences the work. Do **not** start code before Phase 0 is locked.

---

## The change in one line

`RT_new = jh_anchor × ladder(year) × potential × f`  →  `RT_new = RT_current + reduced_rung(+ peaks/potential)`

## Agreed starting reductions (post-season rungs)

The rung a player takes at the *end* of a played season is reduced, so his in-season gain isn't erased. JH→FR is untouched (JH plays no season → nothing to persist).

| End-of-year rollover | today (avg RT) | reduction | target |
|---|--:|--:|--:|
| FR→SO ("Freshman") | +9.1 | −50% | ~+4.6 |
| SO→JR ("Sophomore") | +8.0 | −75% | ~+2.0 |
| JR→SR ("Junior") | +2.7 | −50% | ~+1.4 |
| JH→FR (entry, no season) | +5.5 | none | +5.5 |

*These are cohort-average RT targets. The actual knob is a per-rung retention multiplier; the exact mapping from these RT targets to the constant is a Phase-0 calibration item (the "YoY untrained" figure includes peaks + potential, not just `STD_RUNG_INCREMENT`).*

## In-season tuning folded in (in-flight this session, uncommitted)

`IN_SEASON_GAIN_SCALE 0.18→0.32` · SO decay `−2..0→−1..0` (already live) · JR class `80→95` · SR class `71→100`. These set how big the *persisting* in-season contribution is, so they ship **with** this change, not before it.

---

## Phase 0 — Design decisions (LOCKED 2026-08)

| # | Decision | Resolution |
|---|---|---|
| 0.1 | Additive formula | ✅ `RT_new = RT_current + reduced_rung`, with full peaks and potential-scaled rung added on top |
| 0.2 | Peaks | ✅ **keep full** — the diamond-in-the-rough variability, unshrunk |
| 0.3 | `potential_factor` | ✅ re-point to scale the **rung increment** — a ±15% career-**growth-rate** knob (not a ceiling knob) |
| 0.4 | Reference arc | ✅ **ARC RISES (growth-boosting)** — reference players end stronger; league RT inflates over seasons, so **Phase 3 must prove no runaway** and the soft cap holds |
| 0.5 | Coaching-`f` | ✅ **RETIRE** — additive in-season *is* the "coaching matters" mechanism; one lever |
| 0.6 | `entry_tier` contract | ✅ starting RT **+ standard (reference-coached) career growth rate** — no longer a ceiling; coaching pushes a player above/below it (see below) |
| 0.7 | RT ceiling | ✅ keep `RT_SOFT_CAP = 130`; prove it bounds a well-coached elite over 4 years in Phase 3 (higher stakes now that the arc rises) |
| 0.8 | Save migration | ✅ **roll onto new logic** — mid-career players additive-develop from where they are next offseason; no migration pass |

**Option D calibration parameters (LOCKED 2026-08).** The offseason splits each year's growth budget with the two training phases (Camp + in-season), peaks preserved at full scale:
- **Offseason base retention = 25%** — offseason auto-delivers 25% of standard growth; 75% is earned through persisting Camp + in-season training (a neglected player still creeps up via the 25% floor).
- **Peak split = 50% offseason / 50% training** — a peak year keeps full magnitude: half fires at the rollover, half as amplified Camp + in-season gains during the peak year.
- **Camp vs in-season = proportional** — the training share (and peak amplification) hits Camp and in-season in proportion to the gains they already produce.

**New `entry_tier` contract (0.6).** Tier sets (a) the player's **starting RT** at generation and (b) his **standard career growth rate** (the reduced rung he takes under reference coaching). It is **not a ceiling**: good in-season coaching (user or CPU) compounds a player **above** his tier's standard arc, neglect leaves him **below** it. "Elite" now means "starts high and grows fast under good coaching," not "caps at 100."

## Phase 1 — Implementation
- `develop_rollover`: absolute rescale → additive increment; add per-rung retention constants (e.g. `OFFSEASON_RUNG_RETENTION`), keep shape floors unchanged (only the *level* math changes).
- Apply the in-flight in-season tuning (0.32, JR 95 / SR 100; SO decay already done).

## Phase 2 — Test-suite REWRITE (not just re-green)
| test | fate |
|---|---|
| `test_developed_seniors_land_on_tier_anchors` | **rewrite** — assert the new additive arc, not anchor-landing |
| `test_in_season_invariants` (flat / no-claw-back) | **retire/rewrite** — in-season now persists; "flat" is obsolete by design |
| `test_offseason_attractor` | revisit / likely retire |
| **new** | reference-coached career arc; well-coached > reference > neglected across a career; RT stays under cap; no runaway |

## Phase 3 — Multi-season league validation (the real gate)
- Sim N seasons on a full league (`scripts/season_advance_harness.py`).
- Measure: RT distribution drift, tier→final-RT correlation (should loosen, intentionally), CPU program persistence, top-end (no elite runaway), user-vs-CPU coaching spread.
- Accept when: reference league stays anchored, coaching produces the intended above/below, no runaway.

## Phase 4 — Docs
- `Player_Development_System.md` — **thesis rewrite** (predestination→free-will; offseason additive; in-season persists). Core rewrite, not a line edit.
- `player-development-framework.md`, `Tunable_Constants.md` (new retention knobs; fix the stale "+4.76 RT/season" line), `Training_System.md`.
- Add the per-year × channel chart with live numbers once landed.

## Phase 4b — Capstone infographic (requested)
Once the system is final, produce a holistic **player-development infographic** (hand-off prompt for the design tool *or* built directly): player init (tier/anchor, RT, position intent, potential_factor, CH, peaks + family timing frozen at gen), the load-bearing fields (`entry_tier`, `position_intent`, `potential_factor`, `development` subdoc, `training_position`), and the full growth map — Camp / in-season / offseason by class year (JH→SR) with peaks riding across the training phases. For the user to study the whole system at a glance.

## Phase 5 — Rollout
- Stage on gob-staging → validate a live season → commit + deploy as one coherent unit.

---

## Prerequisite cleanup (uncommitted this session — fold in)
SO decay fix (live) · training-report retune (`training_notes.py` + tests + doc) · doc-drift fixes · `scripts/in_season_training_net_effect.py` · `training_gain_percentages_baseline.md`.

## Top risks
- **RT runaway / tier meaning erodes** → mitigated by Phase 3 validation + soft cap.
- **CPU compounding unbalances programs** → validate program persistence in Phase 3.
- **Save migration surprises** for mid-career players → Phase 0.8.
