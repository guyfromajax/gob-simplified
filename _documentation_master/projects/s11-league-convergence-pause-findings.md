# League convergence — pause export (seed 202608061)

**Paused:** 6 August 2026 ~16:33 local  
**Scratch DB:** `gob-s11-league-convergence` — **not deleted**  
**Exports:** `tmp/s11_league_convergence/seed_202608061/` (+ `pause_export/`)  
**Master seed:** `202608061`

## 1. Where the run reached

| | |
|---|---|
| Franchise | `6a747ba896aec901cbcc87a0` (Couer d'Alene user slot) |
| At SIGTERM | **season 3, week 4** (mid regular season) |
| Season-1 `develop_rollover` | **Completed** (`rollover done (205.6 min)`) |
| Season-2 `develop_rollover` | **Completed** (`rollover done (261.2 min)`) |
| Season-3 offseason | **Not reached** |

Process killed with SIGTERM. Scratch franchise + reference data left intact. No re-init.

**Gap:** post-season-1 FPD was never written to disk and was overwritten by later rollovers. True one-offseason same-player σ is not directly in the DB. Numbers below use survivors after **two** develops and derive one-step as √R₂ under the established proportional-compounding assumption.

## 2. Files written (all verified JSON-readable)

Pre-existing:

- `t0_fpd_raw.json`, `t0_metrics.json`, `meta.json`, `franchise_id.json`
- `ceiling_partial.json`, `s1_signed_pre_rollover.json`, `s2_signed_pre_rollover.json`
- `seed_202608061_run.log`

Pause export (`pause_export/`):

- `REACHED.json`
- `current_fpd_raw.json` (1920 players at pause)
- `current_frd_raw.json` (400 recruits)
- `franchise_doc_slim.json`
- `ceilings.json`
- `runtime_split.json`
- `within_cohort_retention_same_set.json` ← **use this** for retention
- `VERIFY_READABLE.json`
- Superseded: `within_cohort_retention.json`, `within_cohort_retention_corrected.json` (wrong set / wrong z-score)

## 3. Within-cohort retention (primary)

**Method (final):** same survivor player_ids at t0 and now; group by **t0 `training_position`**; within-position sample σ per attribute; average across positions (n-weighted) and attributes. Modes: raw, and z-score with **frozen t0 league mean/std** on both snapshots. FR/SO survivors have **2** `develop_rollover` events. One-step \(\hat{r}=\sqrt{R_2}\); career \(\hat{r}^3\).

### Seed 202608061 — frozen t0 z (preferred combining scale)

| Cohort (year at t0) | n survivors | σ(t0) | σ(after 2 develops) | R₂ | \(\hat{r}\) (1-step) | \(\hat{r}^3\) (career) |
|---|---:|---:|---:|---:|---:|---:|
| FR | 407 | 0.801 | 0.915 | **1.141** | **1.068** | **1.219** |
| SO | 342 | 0.884 | 0.843 | **0.954** | **0.977** | **0.932** |
| JR | 0 | — | — | graduated after 1 develop | — | — |
| SR | 0 | — | — | never developed / gone | — | — |

**Aggregate (mean of FR+SO \(\hat{r}\)):** \(\hat{r} = 1.023\) → **career projection \(\hat{r}^3 = 1.069\)**

Against the 0.4 / 0.7 rule: **≥ 0.7** → blend is **not** dominating league-wide within-position spread in practice; this reads as a **tuning question** (or no question), not a structural model rewrite — **with the caveat that one-step is derived from two develops, not measured after one.**

Raw-attr mode agrees (career projection **1.067**).

Per-attribute one-step \(\hat{r}\) (frozen z, mean of FR/SO √R₂): all attrs in ~0.95–1.10; none near the §11 shape-collapse regime.

### How this sits next to §11

§11 measured **distance to `position_profile`** (shape toward the mean) — ~15% retained.  
This metric measures **dispersion among players inside a position**. Those can diverge: shapes can crowd the profile while magnitudes still fan out via peaks / `potential_factor` / ladder level-close. The pause result says **within-position σ is not collapsing**; it does not reopen §11’s shape finding.

## 4. Ceilings (generation vs signed)

| Label | n | mean attr σ |
|---|---:|---:|
| Generation pre-sign (t0 FRD) | 300 | **15.717** |
| Signed pre-rollover (end s1) | 750 | **11.736** |
| Generation pre-sign (FRD after s1 rollover) | 400 | **11.575** |
| Signed pre-rollover (end s2) | 481 | **11.462** |

**Gap (signing vs generation):**

- s1 signed / t0 generation = **0.747** (signed ~25% tighter than the init recruit pool σ)
- s2 signed / s1 post-rollover generation = **0.990** (essentially flat)

s1 shows a real narrowing at signing vs the init FRD; s2 does not repeat it against the post-rollover generated class. Signing selection as a second convergence source is **plausible in s1, not confirmed as systematic** from two cycles.

## 5. Runtime split (from log)

| Block | Seconds (approx) | Share of logged |
|---|---:|---:|
| Regular + EOS weeks (train + sim + finalize + complete_week) | 29,150 | **51%** |
| `finish_season` / rollover (2×) | 28,008 | **49%** |

- Mean regular week ≈ **428 s**; two full seasons of weeks dominate wall time together with rollover.
- Rollover itself is huge (~3.4h and ~4.4h) — develop for ~1920 players + schedule/recruit regen, not “instant.”
- **Games are a large share of week time**, and with `f ≡ 1.0` they do not change development. A future league-scale experiment could skip sims **only if** week-35 signing inputs are otherwise supplied; recruiting today depends on the season having been played. Cheaper harness = possible for pure develop+recruit experiments if signings are fed explicitly — not claimed implemented.

## 6. Do not resume this franchise

Mid-season-3 state is not a valid t+3. Any re-run: **clean scratch**, **one season** first (revised design), export post-rollover FPD before anything else.

## 7. Decision status

| Question | From this pause |
|---|---|
| Within-position σ retention (derived 1-step → career³) | **~1.07 ≥ 0.7** → not structural by that rule |
| Caveat | One-step not directly measured; no post-s1 FPD file |
| Signing ceiling gap | Present in s1 (~0.75), absent in s2 (~0.99) |
| Re-run needed? | Only if you want a **direct** one-offseason same-set σ, or multi-cycle team-distance at true t+3 |

`OFFSEASON_ATTRACTOR_ALPHA` stays flagged under review — this informs, it is not the decision.
