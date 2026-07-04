# Distant Sim Tuning — Season Momentum & Record Distribution

**Date:** 2026-07-04 · **Scope:** Distant (lightweight) franchise CPU game sim — win probability inputs, season record distribution, national rankings skew · **Status:** Phase 0 complete — baseline measured · **Primary code:** `BackEnd/api/franchise_routes.py` (`_distant_sim_*`, `_run_distant_game_sim`, `_complete_week_finish_cpu_and_persist`) · **Calibration script:** `scripts/distant_sim_monte_carlo.py` · **Primary doc:** [`Distant_Game_Sim_System.md`](../04_Franchise_Mode_Systems/Distant_Game_Sim_System.md)

---

## ⭐ TL;DR (human topline — read this first)

**Problem:** Distant sim produces too many teams clustered around .500–.650 win rates. Full sim seasons routinely produce a handful of 22+ win teams; distant sim rarely does. Additionally, 3–4 of the top 5–10 nationally ranked teams often come from the **user's conference** because that conference runs full sim while everyone else runs distant.

**Root cause:** The current "momentum" term (`chemistry_multiplier × season_wins`) is ratio-neutral, gated behind chemistry bands that are almost always **1×** in franchise mode, and doesn't use persistent compounding state. Base talent inputs are frozen at season start. The full-sim/distant-sim split by conference amplifies the skew.

**Fix direction:** Replace linear win bonus with **win-loss differential momentum**, wire up **compounding `momentum_score`** on FTD, enrich distant-only base inputs with live talent signal, add **tier amplification** for hot teams, and calibrate with Monte Carlo sims against full-sim distributions.

**Target outcome:** ~3–5 teams nationally finish 22+ wins (26-game regular season); ~8–12 teams finish 18–21 wins; median ~13 wins; no more than 1–2 user-conference teams in top 5 unless genuinely elite by talent.

---

## Current System (verified trace)

### Scope & partition

| Path | When | Engine |
|---|---|---|
| **Full sim** | Either team in user's conference | `run_simulation` + `finalize_game` |
| **Full sim (override)** | Either team is user's next-week opponent (weeks 1–26) | Same |
| **Distant sim** | All other regular-season matchups (~56–60/week) | `_run_distant_game_sim` |

See [`Distant_Game_Sim_System.md`](../04_Franchise_Mode_Systems/Distant_Game_Sim_System.md) and `_complete_week_finish_cpu_and_persist` (~L5724–L5757).

### Win probability pipeline (today)

Computed in `_distant_sim_team_combined()` → rolled in `_run_distant_game_sim()`:

```
1. base         = prestige + int(0.1 × total_player_attrs)
2. momentum     = chemistry_multiplier × season_wins        ← _distant_sim_momentum_term()
3. home_bonus   = 2 × team_chemistry   (home team only)     ← _distant_sim_home_team_chemistry_bonus()
4. roll         = randint(1, home_combined + away_combined)
                  home wins if roll ≤ home_combined
```

**Chemistry multiplier bands** (`_distant_sim_momentum_multiplier`):

| Clamped chemistry | Multiplier |
|---|---|
| 7–10 (franchise init range) | **1** |
| 11–15 | 2 |
| 16–20 | 3 |
| 21–24 | 4 |
| 25 | 6 |

**FTD fields loaded for distant sim** (batch in `_complete_week_finish_cpu_and_persist`, ~L5524–L5531):

- `prestige`
- `total_player_attrs` (frozen at season start for v2 franchises)
- `team_attributes.team_chemistry`

**Not used in distant win roll:**

- Live player attribute growth from training
- Team attributes updated by training/EOG (`offensive_efficiency`, `defensive_efficiency`, `shot_threshold`, etc.)
- `momentum_score` FTD field (exists, clamp −10..+10, always 0, never updated)
- SOS, win streaks, recent form
- In-game Player MO / Team Momentum (`Player_Momentum_System.md` — per-possession, zeroed at game end)

### Margin & scores (unchanged by this plan)

`_run_distant_game_sim` maps roll dominance → margin buckets → Gaussian total points → clamped final scores. This layer is fine; tuning targets **win probability inputs only**.

---

## Why Records Compress Toward the Middle

### 1. User-conference full-sim skew

User's conference (~4–8 games/week) runs full sim for **all** intra-conference matchups. Every other conference runs distant sim. Full sim expresses player talent, team attributes, plays, and in-game dynamics. Distant sim uses a 3-number formula. This alone explains 3–4 of the top 5–10 nationally being from the user's conference.

### 2. Current momentum is mathematically weak

**Ratio-neutral:** Both teams add `mult × wins` to combined score. As the season progresses, everyone's combined total inflates, so the percentage gap between teams barely moves.

Example (mid-season, mult = 1 for both):

| Team | Base | Wins | Momentum | Combined |
|---|---|---|---|---|
| Elite (20–6) | 840 | 20 | +20 | 860 |
| Mid (10–16) | 650 | 10 | +10 | 660 |
| **Win prob (neutral)** | | | | **860 / 1520 = 56.6%** |

The 10-win gap in record only adds 10 net points on a ~1500 combined total.

**Chemistry multiplier stuck at 1×:** Franchise init sets `team_chemistry` to 7–10. That maps to multiplier **1** for nearly the entire season unless EOG/training pushes a team above 11. Momentum adds only ~5–15 points of separation — noise on a ~1200–1600 combined total.

### 3. Base talent gap is too small for 22+ wins

Quick math for preseason elite vs weak (no momentum):

| Team | Prestige | Attrs | Base | vs each other (neutral) |
|---|---|---|---|---|
| Elite | 700 | 1400 | 840 | **840 / 1250 = 67.2%** |
| Weak | 320 | 900 | 410 | |

67% win rate over 26 games ≈ **17–18 wins**, not 22+. Current momentum doesn't close this gap.

To reach 22–4 (.846), a team needs ~**85% average win probability**. That requires a combined-score ratio of roughly **5.5:1** against average opponents by late season — far beyond what today's formula produces.

### 4. Frozen `total_player_attrs` (v2)

Training improves player attrs on FPD and team attrs on FTD, but v2 franchises freeze `total_player_attrs` on FTD (`_should_freeze_total_player_attrs`). Full sim picks up training-driven improvement; distant sim does not.

### 5. Prestige dampeners

Floor (200), ceiling (800), and proximity dampeners (`Rank_Prestige_System.md`) keep prestige drift modest over 26 weeks. Good for recruiting integrity, but it means distant sim's primary input doesn't widen much in-season.

### 6. `momentum_score` is a dead hook

The team attribute exists (clamps −10..+10), distant training templates zero it out, and EOG/training never touch it (`Team_Attribute_System.md` § Momentum). Natural place for compounding season momentum — just not wired.

---

## Calibration Targets

These are the distribution goals for a 26-game regular season across 128 teams, calibrated to approximate what full sim produces:

| Metric | Target |
|---|---|
| Teams at 22+ wins | **3–5** |
| Teams at 18–21 wins | **8–12** |
| Median wins | **~13** (matching .500 baseline) |
| Teams below 8 wins | **3–5** (basement dwellers) |
| User-conf teams in top 5 nationally | **≤ 1–2** unless genuinely elite by talent |
| Preseason top-10 team final record | **21–25 wins** (mode ~23) |
| Preseason bottom-20 team final record | **4–10 wins** (mode ~7) |

### Win-probability benchmarks (late season, vs average opponent)

| Team tier | Target P(win) mid-season | Target P(win) late season (week 20+) |
|---|---|---|
| Preseason top-5 | 72–78% | **82–88%** |
| Preseason top-10 | 68–74% | **78–85%** |
| Average (rank ~64) | 48–52% | 48–52% |
| Preseason bottom-20 | 25–32% | **15–22%** |

---

## Proposed Formula (v2 distant sim combined score)

### Layer 1 — Base (talent anchor)

```
base = prestige + int(0.1 × talent_signal)
```

**`talent_signal`** — distant-only, not written to FTD for ranking:

```
Option A (preferred): recompute live total_player_attrs from FPD at sim time
Option B (fallback):  total_player_attrs + team_attr_composite

team_attr_composite = (
    offensive_efficiency
  + defensive_efficiency
  - int(shot_threshold / 20)       # lower threshold = better (golf score)
)
```

Use Option A where FPD is available in the sim batch; fall back to Option B using FTD `team_attributes` already loaded. This closes the training-improvement gap without touching the ranking system's frozen attrs.

### Layer 2 — Differential momentum (replaces raw wins)

```
record_momentum = DISTANT_MO_MULT × (wins - losses)
```

Where `DISTANT_MO_MULT` uses a **distant-specific chemistry scale** (not the current franchise-init-suppressed bands):

| Clamped chemistry | `DISTANT_MO_MULT` |
|---|---|
| 7–10 | **3** |
| 11–15 | **4** |
| 16–20 | **5** |
| 21–24 | **6** |
| 25 | **8** |

Rationale: franchise init chemistry 7–10 should still produce meaningful momentum (3×), not 1×.

**Optional streak bonus** (additive on top of record momentum):

```
if win_streak >= 3:  record_momentum += DISTANT_STREAK_BONUS × (win_streak - 2)
if loss_streak >= 3:  record_momentum -= DISTANT_STREAK_PENALTY × (loss_streak - 2)
```

Constants (initial proposal — tune via Monte Carlo):

| Constant | Proposed value |
|---|---|
| `DISTANT_STREAK_BONUS` | 4 |
| `DISTANT_STREAK_PENALTY` | 3 |

Win/loss streaks computed from last N results in `franchise.results` (regular season only), or maintained as FTD fields updated on persist.

### Layer 3 — Compounding season momentum (`momentum_score`)

Persistent FTD field, updated after each distant game result:

```
On WIN:  momentum_score += WIN_GAIN    × chemistry_scale
On LOSS: momentum_score -= LOSS_DECAY  × chemistry_scale   (asymmetric: LOSS_DECAY < WIN_GAIN)

chemistry_scale = max(1.0, team_chemistry / 10.0)

Clamp momentum_score to [-10, 10]  (existing Attribute_Clamp_System range)
```

Constants (initial proposal):

| Constant | Proposed value | Rationale |
|---|---|---|
| `DISTANT_MO_WIN_GAIN` | 1.5 | Builds momentum over ~8–10 win streak to near ceiling |
| `DISTANT_MO_LOSS_DECAY` | 0.8 | Asymmetric — hot teams persist through occasional losses |
| `DISTANT_MO_SCORE_WEIGHT` | 8 | Each momentum_score point → 8 combined-score points |

Contribution to combined score:

```
season_momentum = momentum_score × DISTANT_MO_SCORE_WEIGHT
```

Example: a team at `momentum_score = 8` gets +64 combined points — meaningful but not overwhelming.

**Streak interaction with `momentum_score`:**

```
On WIN with win_streak >= 3:  WIN_GAIN += 0.5 × (win_streak - 2)
On LOSS with win_streak >= 3:  momentum_score -= 2.0  (partial streak reset)
```

### Layer 4 — Tier amplification (late-season separation)

Applied only after week 10 (enough games for stable win pct):

```
win_pct = wins / (wins + losses)

if win_pct >= 0.750:   tier_mult = 1.50
elif win_pct >= 0.650: tier_mult = 1.25
elif win_pct >= 0.550: tier_mult = 1.00
elif win_pct >= 0.450: tier_mult = 0.90
else:                  tier_mult = 0.75

tier_adjustment = int((record_momentum + season_momentum) × (tier_mult - 1.0))
```

This amplifies teams already pulling away (.750+) without affecting early-season variance.

### Layer 5 — Home edge (unchanged)

```
home_bonus = 2 × team_chemistry   (home team only)
```

### Full combined score (v2)

```
combined = (
    base
  + record_momentum
  + season_momentum
  + tier_adjustment
  + home_bonus                          # home only
)
```

Roll unchanged: `randint(1, home_combined + away_combined)`.

### Worked example (late season, week 22)

Preseason #3 team (20–2) at home vs average team (11–11):

| Component | Elite (home) | Average (away) |
|---|---|---|
| base | 840 | 620 |
| record_momentum (18 × 5) | +90 | 0 |
| season_momentum (mo=7 × 8) | +56 | +8 (mo=1) |
| tier_adj (.909 → 1.50×) | +73 | 0 |
| home_bonus (2 × 18) | +36 | 0 |
| **Combined** | **1095** | **628** |

**P(elite wins)** = 1095 / 1723 = **63.6%**

Still not 85% — this example shows tier + momentum need tuning upward, or the elite team's base/talent signal needs to be higher. Monte Carlo script will iterate constants until distribution targets are met. Likely adjustments:

- Raise `DISTANT_MO_SCORE_WEIGHT` to 10–12
- Raise tier mult for .750+ to 1.75–2.0
- Raise `DISTANT_MO_MULT` top band to 10

The Monte Carlo calibrator (Phase 4) exists precisely to find these values empirically rather than guessing.

---

## What We Will NOT Do

| Avoid | Reason |
|---|---|
| Reuse in-game Player MO / Team Momentum | Per-possession, zeroed at game end — wrong abstraction |
| Multiplicative momentum on base score (without testing) | Can explode for high-prestige teams; breaks margin logic |
| Random momentum updates | Keep deterministic from W/L for explainability (consistent with prestige design) |
| Change margin/score generation | Win-prob inputs are the problem, not box score output |
| Touch ranking system's frozen `total_player_attrs` | Distant-only live recompute preserves ranking integrity |

---

## Work Plan

### Phase 0 — Baseline measurement (prerequisite) ✅

- [x] **0.1** Build `scripts/distant_sim_monte_carlo.py` — simulate N seasons (start with N=10,000) using current formula against a representative talent/prestige distribution pulled from staging data or hardcoded tiers.
- [x] **0.2** Record baseline distribution: wins histogram, top-10 team origins (conf), elite team win rates by week.
- [x] **0.3** Run same script against a sample of **full sim** seasons (or historical franchise data if available) to establish the target distribution empirically.
- [x] **0.4** Document baseline numbers in this file under **Calibration Results** (section below).

### Phase 1 — Differential momentum (highest leverage, smallest diff)

**Files:** `franchise_routes.py` (`_distant_sim_momentum_term`, `_distant_sim_momentum_multiplier`), `Distant_Game_Sim_System.md`

- [ ] **1.1** Change `_distant_sim_momentum_term` from `mult × wins` to `DISTANT_MO_MULT × (wins - losses)`.
- [ ] **1.2** Replace chemistry multiplier bands with distant-specific bands (floor 3×, not 1×).
- [ ] **1.3** Pass losses into momentum term (extend `_distant_sim_team_combined` to read `L` from standings).
- [ ] **1.4** Update `Distant_Game_Sim_System.md` win-probability section.
- [ ] **1.5** Add unit tests in `tests/test_distant_sim.py` for momentum term edge cases (0–0, undefeated, winless, mid-season).
- [ ] **1.6** Re-run Monte Carlo — compare to baseline.

### Phase 2 — Compounding `momentum_score`

**Files:** `franchise_routes.py` (`_persist_distant_franchise_game` or post-result hook, `_distant_sim_team_combined`), `Team_Attribute_System.md`

- [ ] **2.1** Add `_distant_sim_update_momentum_score(winner_ftd, loser_ftd, margin)` — apply WIN_GAIN / LOSS_DECAY with chemistry scale and streak logic.
- [ ] **2.2** Call from distant game persist path after result is known.
- [ ] **2.3** Add `season_momentum = momentum_score × DISTANT_MO_SCORE_WEIGHT` to `_distant_sim_team_combined`.
- [ ] **2.4** Extend FTD batch load to include `team_attributes.momentum_score`.
- [ ] **2.5** Initialize `momentum_score = 0` at season creation (verify existing behavior).
- [ ] **2.6** Update docs: `Distant_Game_Sim_System.md`, `Team_Attribute_System.md` (add distant-sim faucets/sinks for momentum_score).
- [ ] **2.7** Re-run Monte Carlo.

### Phase 3 — Live talent signal (distant-only base enrichment)

**Files:** `franchise_routes.py` (`_distant_sim_team_combined`, batch load in `_complete_week_finish_cpu_and_persist`)

- [ ] **3.1** Add `_distant_sim_talent_signal(ftd_doc, fpd_by_player_id)` — recompute live attrs or team_attr composite.
- [ ] **3.2** Use in base score instead of frozen `total_player_attrs` (distant sim only; do not write back to FTD).
- [ ] **3.3** Ensure batch load includes needed FPD data (or team_attributes for fallback).
- [ ] **3.4** Re-run Monte Carlo.

### Phase 4 — Tier amplification & streak bonus

**Files:** `franchise_routes.py`, new constants in `BackEnd/constants/distant_sim.py` (or similar)

- [ ] **4.1** Extract all tuning constants to a named constants file (matching project convention — see `Player_Momentum_System.md` tuning contract).
- [ ] **4.2** Implement win/loss streak tracking (FTD fields or computed from results).
- [ ] **4.3** Implement tier amplification (week 10+ gate).
- [ ] **4.4** Implement streak bonus/penalty on record momentum.
- [ ] **4.5** Run Monte Carlo calibrator — iterate constants until distribution targets (§ Calibration Targets) are met.
- [ ] **4.6** Lock final constants in constants file + docs.

### Phase 5 — User-conference skew mitigation (optional, separate concern)

- [ ] **5.1** Measure skew: % of top-5 / top-10 from user conference before and after Phases 1–4.
- [ ] **5.2** If skew persists, evaluate options:
  - **5.2a** Calibrate distant constants until distant elite teams match full-sim elite win rates (preferred — no arch change).
  - **5.2b** Full-sim promotion for top-N ranked matchups (both teams natl_rank ≤ 15) — ~2–4 extra full sims/week.
  - **5.2c** Accept minor skew if national record distribution is otherwise correct.
- [ ] **5.3** Document chosen approach and results.

### Phase 6 — Integration & validation

- [ ] **6.1** End-to-end test: complete_week with distant games, verify momentum_score updates persist on FTD.
- [ ] **6.2** Verify distant sim results still persist correctly (`simulation_engine="distant"`, box scores, EOG attrs).
- [ ] **6.3** Verify ranking/prestige system unaffected (frozen attrs, weekly rank updates).
- [ ] **6.4** Playtest one full franchise season — spot-check national standings at weeks 10, 18, 26.
- [ ] **6.5** Final doc pass: `Distant_Game_Sim_System.md`, this file (Calibration Results filled in).

---

## Constants File (proposed)

New file: `BackEnd/constants/distant_sim.py`

```python
# Distant sim tuning — change here AND in Distant_Game_Sim_System.md + Distant_Sim_Tuning.md

# Chemistry → record momentum multiplier (distant-specific; floor 3×)
DISTANT_MO_MULT_BANDS = [
    (11, 3),   # chemistry 7–10
    (16, 4),   # 11–15
    (21, 5),   # 16–20
    (25, 6),   # 21–24
    (26, 8),   # 25
]

# Compounding season momentum (momentum_score on FTD)
DISTANT_MO_WIN_GAIN = 1.5
DISTANT_MO_LOSS_DECAY = 0.8
DISTANT_MO_SCORE_WEIGHT = 8          # tune via Monte Carlo
DISTANT_MO_STREAK_WIN_BONUS = 0.5    # per streak level above 2
DISTANT_MO_STREAK_LOSS_RESET = 2.0   # partial reset on loss after 3+ streak

# Streak bonus on record momentum
DISTANT_STREAK_BONUS = 4
DISTANT_STREAK_PENALTY = 3

# Tier amplification (applied after this week)
DISTANT_TIER_MIN_WEEK = 10
DISTANT_TIER_BANDS = [
    (0.750, 1.50),
    (0.650, 1.25),
    (0.550, 1.00),
    (0.450, 0.90),
    (0.000, 0.75),
]
```

All values marked "tune via Monte Carlo" are starting proposals, not final.

---

## Key Files Reference

| File | Role |
|---|---|
| `BackEnd/api/franchise_routes.py` | `_distant_sim_*`, `_run_distant_game_sim`, `_persist_distant_franchise_game`, `_complete_week_finish_cpu_and_persist`, `_apply_franchise_distant_cpu_training` |
| `BackEnd/constants/distant_sim.py` | **New** — tuning constants |
| `BackEnd/models/distant_game_stats.py` | Box score generation (unchanged) |
| `BackEnd/utils/franchise_rank_prestige.py` | Ranking/prestige (unchanged; distant-only talent recompute must not write here) |
| `scripts/distant_sim_monte_carlo.py` | **New** — calibration script |
| `tests/test_distant_sim.py` | **New** — unit tests for momentum/combined score |
| `_documentation_master/04_Franchise_Mode_Systems/Distant_Game_Sim_System.md` | Spec doc (update after each phase) |
| `_documentation_master/04_Franchise_Mode_Systems/Rank_Prestige_System.md` | Ranking formula (read-only reference) |
| `_documentation_master/04_Franchise_Mode_Systems/Team_Attribute_System.md` | momentum_score faucets/sinks (update in Phase 2) |

---

## Calibration Results

> **Phase 0 complete (2026-07-04).** 10,000 seasons × 128 teams × 26 games. Team talent from **tsv**. Conference assignment: **mixed**. Seed `42`. Full-sim proxy uses `prestige + int(0.25 × attrs)` with no win-count momentum — reference target only, not live GameManager output.

### Baseline (current distant formula — all games distant)

| Metric | Value |
|---|---|
| Teams at 22+ wins (mean/season) | 0.06 |
| Teams at 18–21 wins (mean/season) | 5.88 |
| Teams below 8 wins (mean/season) | 2.63 |
| Median wins (team-season) | 13.0 |
| Mean wins (team-season) | 13.00 |
| Preseason top-10 avg final wins | 14.49 |
| Preseason top-10 P90 final wins | 18 |
| Preseason bottom-20 avg final wins | 11.51 |

**Hybrid skew (user conference = 1, full-sim proxy in-conf / distant out-of-conf):**

| Metric | Value |
|---|---|
| Top-5 from user conference (share) | 3.4% |
| Top-10 from user conference (share) | 3.9% |
| User-conf teams at 22+ (mean/season) | _see JSON_ |

### Full-sim proxy reference (all games — tuning target shape)

| Metric | Target (doc) | Full-sim proxy |
|---|---|---|
| Teams at 22+ wins | 3–5 | 0.05 |
| Teams at 18–21 wins | 8–12 | 5.67 |
| Median wins | ~13 | 13.0 |
| Preseason top-10 avg final wins | 21–25 | 14.39 |

### Phase 0 checklist

- [x] **0.1** `scripts/distant_sim_monte_carlo.py` built
- [x] **0.2** Baseline distribution recorded (see above + `scripts/distant_sim_monte_carlo_results.json`)
- [x] **0.3** Full-sim proxy reference run (same script, `--engine full_proxy`)
- [x] **0.4** Results documented in this section

Raw JSON: `scripts/distant_sim_monte_carlo_results.json`

### Phase 0 findings (interpretation)

1. **Record compression is confirmed.** Under the current distant formula, essentially **zero** teams reach 22+ wins (mean **0.06** per season). Preseason top-10 teams finish at **14.5** wins on average — barely above the **13**-win median. Elite cumulative win rate plateaus at **~56%** by mid-season (no runaway separation).

2. **Full-sim proxy (0.25× attrs, no momentum) is not enough alone** — still **0.05** teams at 22+ in this model; preseason top-10 avg only **14.4** wins. Real full sim likely separates more via possession-level talent, playcalling, and in-game dynamics not captured here. Phase 1–4 momentum/tier changes remain necessary.

3. **Conference assignment matters.** Default **`mixed`** shuffles talent across conferences (realistic). Use **`--conference-mode rank_block`** to reproduce the pathological case where the top 8 teams share a conference and cannibalize each other's records (top-10 avg drops to **13.3** wins).

4. **Hybrid skew** (user conf = full proxy, rest = distant): top-5 share from user conference = **3.4%** with conference 1 as user conf and mixed talent. In-game skew reported by playtesters (3–4 of top 5 from user conf) reflects the **live** full-sim path, not this simplified proxy — re-run hybrid after Phase 1+ tuning.

---

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-04 | Use `(W − L)` not raw wins | Breaks ratio-neutral compression |
| 2026-07-04 | Wire existing `momentum_score` FTD field | Dead hook already exists with clamps; no new schema |
| 2026-07-04 | Distant-only live talent recompute | Preserves ranking system's frozen attrs |
| 2026-07-04 | Monte Carlo before locking constants | Current formula math shows 67% elite-vs-weak — constants must be empirically tuned |
| 2026-07-04 | Do not change margin/score layer | Problem is win-prob inputs, not box score output |
| 2026-07-04 | Tier amplification gated to week 10+ | Avoid early-season runaway before sample size is meaningful |
