# League convergence — shape vs level (correction)

**Date:** 6 August 2026  
**Seed:** `202608061`  
**Inputs:** existing exports only (`t0_fpd_raw.json`, `pause_export/current_fpd_raw.json`) — no re-sim  
**Raw numbers:** `tmp/s11_league_convergence/seed_202608061/pause_export/shape_vs_level_retention.json`  
**Prior pause note:** `s11-league-convergence-pause-findings.md` (per-attribute σ verdict **withdrawn**)

## Verdict status

**Hold / reverse the “not structural” reading.** Per-attribute σ was level-contaminated. On **shape** retention the career projection lands **≤ 0.4** → structural by the stated rule. No clean one-season re-run required for the boundary case.

`OFFSEASON_ATTRACTOR_ALPHA` stays under review. Nothing changed in code.

---

## Why per-attribute σ was blind

The attractor is RT-neutral: it redistributes shape while preserving level. Level still fans out via tier / `potential_factor` / peaks. End state §11 predicts: one shape per position at many magnitudes. Per-attribute σ stays large (magnitude spread) while kind-diversity is gone.

FR “retention” **1.141** on that metric was the tell — an inward attractor cannot increase dispersion; level fan-out can. Same RT-masking pattern again; the metric in the brief was the miss.

---

## Correction — shape vs level (same survivor sets, 2 develops)

For each player, \(v\) = core-12; **level** = mean(\(v\)); **shape** = \(v\) / mean(\(v\)).  
Group by **t0 `training_position`**. Same survivors at t0 and pause.  
One-step \(\hat{r}=\sqrt{R_2}\); career \(=\hat{r}^3\). Decision rule on **shape only**.

### Aggregate (mean of FR + SO)

| Metric | \(\hat{r}\) (1-step) | Career \(\hat{r}^3\) | Rule |
|---|---:|---:|---|
| **Shape — mean pairwise cosine distance (primary)** | **0.625** | **0.245** | **≤ 0.4 → structural** |
| Shape — per-component σ of shape vectors (second view) | 0.724 | **0.379** | **≤ 0.4 → structural** |
| Level σ (context) | — | R₂ **1.315** (grew) | not for verdict |

### Per cohort (shape cosine)

| Cohort | n | cosine t0 | cosine after 2 | R₂ | \(\hat{r}\) | \(\hat{r}^3\) |
|---|---:|---:|---:|---:|---:|---:|
| FR | 407 | 0.110 | 0.050 | 0.456 | 0.675 | 0.308 |
| SO | 342 | 0.139 | 0.046 | 0.331 | 0.576 | 0.191 |

### Level fan-out (expected)

| Cohort | level σ t0 | level σ after 2 | R₂ |
|---|---:|---:|---:|
| FR | 14.58 | 20.04 | **1.374** |
| SO | 14.55 | 18.28 | **1.256** |

### PC1 share of shape variance (collapse toward one axis)

| Cohort | PC1 t0 | PC1 after 2 | Δ |
|---|---:|---:|---:|
| FR | 0.341 | 0.546 | **+0.205** |
| SO | 0.317 | 0.556 | **+0.238** |

### Per-position shape cosine (career \(\hat{r}^3\)) — do not hide in aggregate

**FR survivors**

| Pos | n | \(\hat{r}\) | career \(\hat{r}^3\) | PC1 t0→after | level R₂ |
|---|---:|---:|---:|---|---:|
| PG | 63 | 0.535 | **0.153** | 0.37→0.71 | 1.54 |
| SG | 90 | 0.450 | **0.091** | 0.26→0.42 | 1.38 |
| SF | 51 | 0.645 | **0.269** | 0.30→0.55 | 1.19 |
| PF | 82 | 0.700 | **0.343** | 0.42→0.52 | 1.56 |
| C | 121 | 0.843 | **0.599** | 0.35→0.57 | 1.23 |

**SO survivors**

| Pos | n | \(\hat{r}\) | career \(\hat{r}^3\) | PC1 t0→after | level R₂ |
|---|---:|---:|---:|---|---:|
| PG | 55 | 0.455 | **0.094** | 0.31→0.67 | 1.24 |
| SG | 83 | 0.374 | **0.052** | 0.23→0.48 | 1.31 |
| SF | 42 | 0.559 | **0.175** | 0.27→0.67 | 0.98 |
| PF | 56 | 0.616 | **0.234** | 0.37→0.46 | 1.32 |
| C | 106 | 0.733 | **0.393** | 0.38→0.56 | 1.34 |

Guards collapse hardest (SG career shape retention ~5–9%). Centres retain the most shape (~39–60%) but still sit at or under the 0.4 line on SO, and FR-C’s 0.599 is the softest cell — still well below 0.7.

---

## Generation-path discrepancy (ceilings)

| Row | n | mean attr σ | Path |
|---|---:|---:|---|
| t0 FRD (init) | **300** | **15.717** | Pre-built **`recruit_sets` set** (`set_0001`) via `load_unused_set_or_generate` |
| FRD after s1 rollover | **400** | **11.575** | **Dynamic** `generate_recruits_list(count=400)` — set already in `used_recruit_set_ids` |

Both are generation / pre-sign. Difference is **not** signing selection.

**Code:** `BackEnd/models/recruit_sets.py` → `load_unused_set_or_generate`.  
- Init: unused sets available → load frozen set (scratch DB has one set, **300** recruits).  
- First `finish_season`: that `set_id` is recorded on the franchise → no unused set left → fallback dynamic generation at **count=400**.

Same entry helper both times; **different branch** after the only set is consumed. The variety drop (~26% mean attr σ) is a side effect of portrait-set vs live `generate_player` populations — not an intentional “season-2+ ceiling” design knob. Unintentional as a permanent league variety ratchet unless someone chose the set’s tighter attribute distribution on purpose when building `set_0001`.

That also explains the signing gaps: s1 signed vs **wide init set** → 0.747; s2 signed vs **like-for-like dynamic class** → 0.990.

Nothing changed; report only.

---

## Rollover cost (note only)

Rollover wall times **205.6 min** and **261.2 min** for ~1920 players ≈ **6–8 s/player** for develop arithmetic over twelve numbers. Strongly implies per-player DB round trips in the develop / persist path — same family as the 443 in-loop writes. Noted; not chased.

---

## Sequence status

1. Shape vs level recomputed from exports — **done**.  
2. Generation-path discrepancy — **done** (set vs dynamic fallback).  
3. Clean one-season re-run — **not required** for the 0.4/0.7 gate (primary shape cosine career **0.245 ≤ 0.4**). Direct one-offseason measure remains optional hygiene, not blocking.
