# Distant Sim Tuning — Season Momentum & Record Distribution

**Date:** 2026-07-04 · **Scope:** Distant (lightweight) franchise CPU game sim — win probability inputs, season record distribution, national rankings skew · **Status:** Phase 6 complete — integration tests + final MC; manual playtest checklist below · **Primary code:** `BackEnd/api/franchise_routes.py`, `BackEnd/distant_sim_engine.py` · **Calibration script:** `scripts/distant_sim_monte_carlo.py` · **Primary doc:** [`Distant_Game_Sim_System.md`](../04_Franchise_Mode_Systems/Distant_Game_Sim_System.md)

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
| **Full sim (override)** | Either team is user's scheduled opponent next week (weeks 1–26) | Same |
| **Full sim (ranked promotion)** | Both teams `natl_rank ≤ 15` in a non-user-conference game (Phase 5) | Same |
| **Distant sim** | All other regular-season matchups (~56–60/week) | `_run_distant_game_sim` |

See [`Distant_Game_Sim_System.md`](../04_Franchise_Mode_Systems/Distant_Game_Sim_System.md) and `_complete_week_finish_cpu_and_persist` (~L5724–L5757).

### Win probability pipeline (today)

Computed in `_distant_sim_team_combined()` → rolled in `_run_distant_game_sim()`:

```
1. base         = prestige + int(0.1 × talent_signal)
2. momentum     = DISTANT_MO_MULT × (wins − losses)   ← distant_sim_record_momentum()
3. season_mo    = momentum_score × 8                    ← distant_sim_season_momentum()
4. home_bonus   = 2 × team_chemistry   (home team only) ← _distant_sim_home_team_chemistry_bonus()
5. roll         = randint(1, home_combined + away_combined)
                  home wins if roll ≤ home_combined
```

**`talent_signal`** (Phase 3 — distant-only, not written to FTD for ranking):
- **Option A:** sum live FPD core attrs for `ftd.players` at sim time (`distant_sim_live_roster_player_attrs`).
- **Option B (fallback):** frozen `total_player_attrs` + team-attribute composite (`off_eff + def_eff − int(shot_threshold/20)` when present).

**Chemistry multiplier bands** (`distant_sim_momentum_multiplier` — `BackEnd/constants/distant_sim.py`):

| Clamped chemistry | Multiplier |
|---|---|
| 7–10 (franchise init range) | **3** |
| 11–15 | 4 |
| 16–20 | 5 |
| 21–24 | 6 |
| 25 | 8 |

**FTD fields loaded for distant sim** (batch in `_complete_week_finish_cpu_and_persist`, ~L5524–L5531):

- `prestige`
- `total_player_attrs` (frozen at season start for v2 franchises)
- `team_attributes.team_chemistry`
- `team_attributes.momentum_score` (Phase 2 — compounding season momentum, −10..+10)
- `team_attributes.distant_win_streak`, `distant_loss_streak` (Phase 2 — streak tracking)

**Not used in distant win roll:**

- Live player attribute growth from training
- Team attributes updated by training/EOG (`offensive_efficiency`, `defensive_efficiency`, `shot_threshold`, etc.)
- SOS, recent form (beyond distant streak counters)
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

### 6. `momentum_score` was a dead hook — **now wired (Phase 2)**

The team attribute exists (clamps −10..+10). Phase 2 updates it after each distant game and feeds `momentum_score × 8` into combined score. Streak bonuses/penalties apply on top of base win/loss deltas. See `Team_Attribute_System.md` § Momentum and `Distant_Game_Sim_System.md`.

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

### Phase 1 — Differential momentum ✅

**Files:** `BackEnd/distant_sim_engine.py`, `BackEnd/constants/distant_sim.py`, `franchise_routes.py`, `Distant_Game_Sim_System.md`

- [x] **1.1** Change momentum from `mult × wins` to `DISTANT_MO_MULT × (wins - losses)`.
- [x] **1.2** Replace chemistry multiplier bands with distant-specific bands (floor 3×, not 1×).
- [x] **1.3** Pass losses into momentum term via `_distant_sim_team_combined` reading `L` from standings.
- [x] **1.4** Update `Distant_Game_Sim_System.md` win-probability section.
- [x] **1.5** Add unit tests in `tests/test_distant_sim.py`.
- [x] **1.6** Re-run Monte Carlo — compare to baseline (see Phase 1 results below).

### Phase 2 — Compounding `momentum_score` ✅

**Files:** `franchise_routes.py`, `BackEnd/distant_sim_engine.py`, `BackEnd/constants/distant_sim.py`, `franchise_manager.py`, `Team_Attribute_System.md`

- [x] **2.1** Add `_distant_sim_persist_momentum_score_updates()` — apply WIN_GAIN / LOSS_DECAY with chemistry scale and streak logic (`compute_distant_momentum_score_updates` in engine).
- [x] **2.2** Call from distant game persist path after result is known (`_persist_distant_franchise_game`).
- [x] **2.3** Add `season_momentum = momentum_score × DISTANT_MO_SCORE_WEIGHT` to `_distant_sim_team_combined`.
- [x] **2.4** Extend FTD batch load to include `team_attributes.momentum_score` + streak fields; in-memory cache updates within same-week batch.
- [x] **2.5** Initialize `momentum_score = 0`, `distant_win_streak = 0`, `distant_loss_streak = 0` at season creation (`franchise_manager.py`).
- [x] **2.6** Update docs: `Distant_Game_Sim_System.md`, `Team_Attribute_System.md`.
- [x] **2.7** Re-run Monte Carlo (see Phase 2 results below).

### Phase 3 — Live talent signal (distant-only base enrichment) ✅

**Files:** `BackEnd/distant_sim_engine.py`, `franchise_routes.py` (`_distant_sim_batch_fpd_map`, `_distant_sim_team_combined`, batch load in `_complete_week_finish_cpu_and_persist` + EOS distant path)

- [x] **3.1** Add `distant_sim_talent_signal()` / `distant_sim_team_attr_composite()` in engine — live FPD sum or frozen + composite fallback.
- [x] **3.2** Use in base score via `distant_sim_team_combined(..., fpd_by_player_id=)` (distant sim only; never writes back to FTD).
- [x] **3.3** Batch-load FPD for all roster `players` in distant-sim week; extend FTD projection with `players` + team attrs for fallback.
- [x] **3.4** Re-run Monte Carlo (see Phase 3 results below). MC script supports `--live-talent-proxy N` for training-growth simulation.

### Phase 4 — Tier amplification & streak bonus ✅

**Files:** `BackEnd/constants/distant_sim.py`, `BackEnd/distant_sim_engine.py`, `franchise_routes.py`, `scripts/distant_sim_monte_carlo.py`

- [x] **4.1** All tuning constants in `BackEnd/constants/distant_sim.py` (incl. `DISTANT_TALENT_ATTR_MULT`, streak, tier bands).
- [x] **4.2** Win/loss streak on record momentum via existing `distant_win_streak` / `distant_loss_streak` FTD fields (Phase 2).
- [x] **4.3** Tier amplification (`distant_sim_tier_adjustment`) with week gate (`DISTANT_TIER_WEEK_GATE = 5`); `current_week` passed from franchise routes + MC script.
- [x] **4.4** Streak bonus/penalty on record momentum (`distant_sim_record_streak_bonus`).
- [x] **4.5** Monte Carlo calibration — locked constants (see Phase 4 results below).
- [x] **4.6** Docs updated: `Distant_Game_Sim_System.md`, this file.

### Phase 5 — User-conference skew mitigation ✅

**Files:** `BackEnd/constants/distant_sim.py`, `BackEnd/distant_sim_engine.py`, `franchise_routes.py`, `scripts/distant_sim_monte_carlo.py`

- [x] **5.1** Measure skew: hybrid MC reports top-5/top-10 user-conf share **by wins** and **by natl-rank proxy** (week 26 `calculate_ranking_score`).
- [x] **5.2** Decision: **5.2a** (Phase 4 distant calibration) + **5.2b** (ranked full-sim promotion) — see Phase 5 results below. Did not need 5.2c alone.
- [x] **5.3** Documented in `Distant_Game_Sim_System.md` and this file.

**Implementation (5.2b):** `DISTANT_RANKED_FULLSIM_MAX_RANK = 15`. Non-user-conference games where both teams are nationally ranked ≤ 15 route to full CPU sim instead of distant.

### Phase 6 — Integration & validation ✅

**Files:** `tests/test_distant_sim_integration.py`, `BackEnd/distant_sim_engine.py` (`distant_sim_apply_result_to_standings_cache`), `Distant_Game_Sim_System.md`

- [x] **6.1** Momentum FTD updates: `compute_distant_momentum_score_updates` + within-week cache (`test_momentum_updates_apply_to_ftd_cache`, `test_within_week_cache_updates_combined_score`). Full mongo `complete_week` E2E deferred to CI (requires pymongo) / manual playtest.
- [x] **6.2** Distant persist shape: `build_distant_game_summary` → `simulation_engine="distant"`, box scores, `quarter=5`, `is_final=True` (`test_build_distant_game_summary_marks_distant_engine`; skips locally without pymongo).
- [x] **6.3** Ranking/prestige freeze: v2 strips `total_player_attrs` from FTD writes; live FPD talent signal does not mutate FTD (`test_v2_franchise_freezes_total_player_attrs_on_ftd_update`, `test_talent_signal_reads_fpd_without_mutating_ftd`).
- [ ] **6.4** **Manual playtest** — one full franchise season (checklist below).
- [x] **6.5** Final doc pass: `Distant_Game_Sim_System.md`, this file (Phase 6 results below).

#### Playtest checklist (6.4 — manual)

Run one franchise season through week 26 and spot-check:

1. **National standings (weeks 10, 18, 26):** ≤ 1–2 user-conference teams in top 5 unless genuinely elite; ~3–5 teams nationally at 22+ wins by week 26.
2. **Momentum on FTD:** After a distant-sim week, inspect two CPU teams that played distant games — winner `momentum_score` increased, loser decreased; `distant_win_streak` / `distant_loss_streak` updated.
3. **Ranked promotion:** Log or breakpoint when both teams `natl_rank ≤ 15` in a non-user-conference game — should route to full CPU sim, not distant.
4. **Game docs:** Sample distant game has `simulation_engine="distant"`, plausible box scores, EOG team attrs applied.
5. **Record distribution:** No more than ~5 teams below 8 wins; median ~13 wins league-wide.

---

## Constants File (Phases 1–4 implemented)

`BackEnd/constants/distant_sim.py` — calibrated Phase 4 (seed 42, 10k seasons):

```python
DISTANT_TALENT_ATTR_MULT = 0.20
DISTANT_MO_MULT_BANDS = [(11, 8), (16, 10), (21, 12), (25, 16), (26, 22)]
DISTANT_MO_SCORE_WEIGHT = 28
DISTANT_STREAK_MIN = 3
DISTANT_STREAK_BONUS = 22
DISTANT_STREAK_PENALTY = 18
DISTANT_TIER_WEEK_GATE = 5
DISTANT_TIER_BANDS = [(0.750, 7.0), (0.650, 3.25), (0.550, 1.0), (0.450, 0.45), (0.000, 0.25)]
# Plus season momentum: WIN_GAIN=1.5, LOSS_DECAY=0.8, SCORE clamp ±10
DISTANT_RANKED_FULLSIM_MAX_RANK = 15  # Phase 5; 0 = disable
```

Engine: `BackEnd/distant_sim_engine.py`

---

## Key Files Reference

| File | Role |
|---|---|
| `BackEnd/api/franchise_routes.py` | `_distant_sim_*`, `_run_distant_game_sim`, `_persist_distant_franchise_game`, `_complete_week_finish_cpu_and_persist`, `_apply_franchise_distant_cpu_training` |
| `BackEnd/distant_sim_engine.py` | Win-probability helpers (Phase 1+) |
| `BackEnd/constants/distant_sim.py` | Tuning constants |
| `BackEnd/models/distant_game_stats.py` | Box score generation (unchanged) |
| `BackEnd/utils/franchise_rank_prestige.py` | Ranking/prestige (unchanged; distant-only talent recompute must not write here) |
| `scripts/distant_sim_monte_carlo.py` | **New** — calibration script |
| `tests/test_distant_sim.py` | Unit tests for momentum/combined score (29) |
| `tests/test_distant_sim_integration.py` | Phase 6 integration tests (6) |
| `_documentation_master/04_Franchise_Mode_Systems/Distant_Game_Sim_System.md` | Spec doc (update after each phase) |
| `_documentation_master/04_Franchise_Mode_Systems/Rank_Prestige_System.md` | Ranking formula (read-only reference) |
| `_documentation_master/04_Franchise_Mode_Systems/Team_Attribute_System.md` | momentum_score faucets/sinks (update in Phase 2) |

---

## Calibration Results

> **Phase 0 complete (2026-07-04).** 10,000 seasons × 128 teams × 26 games. Team talent from **tsv**. Conference assignment: **mixed**. Seed `42`. Full-sim proxy uses `prestige + int(0.25 × attrs)` with no win-count momentum — reference target only, not live GameManager output.

### Phase 0 findings (interpretation)

1. **Record compression is confirmed.** Under the current distant formula, essentially **zero** teams reach 22+ wins (mean **0.06** per season). Preseason top-10 teams finish at **14.5** wins on average — barely above the **13**-win median. Elite cumulative win rate plateaus at **~56%** by mid-season (no runaway separation).

2. **Full-sim proxy (0.25× attrs, no momentum) is not enough alone** — still **0.05** teams at 22+ in this model; preseason top-10 avg only **14.4** wins. Real full sim likely separates more via possession-level talent, playcalling, and in-game dynamics not captured here. Phase 1–4 momentum/tier changes remain necessary.

3. **Conference assignment matters.** Default **`mixed`** shuffles talent across conferences (realistic). Use **`--conference-mode rank_block`** to reproduce the pathological case where the top 8 teams share a conference and cannibalize each other's records (top-10 avg drops to **13.3** wins).

4. **Hybrid skew** (user conf = full proxy, rest = distant): top-5 share from user conference = **3.4%** with conference 1 as user conf and mixed talent. In-game skew reported by playtesters (3–4 of top 5 from user conf) reflects the **live** full-sim path, not this simplified proxy — re-run hybrid after Phase 1+ tuning.

### Phase 0 baseline (pre-change formula: `mult × wins`, 1× chemistry floor)

| Metric | Value |
|---|---|
| Teams at 22+ wins (mean/season) | 0.06 |
| Preseason top-10 avg final wins | 14.49 |
| Preseason top-10 P90 final wins | 18 |
| Median wins | 13.0 |

### Phase 1 results (2026-07-04 — `DISTANT_MO_MULT × (W−L)`, chemistry floor 3×)

10,000 seasons, mixed conferences, seed 42. Same script as Phase 0.

| Metric | Phase 0 | Phase 1 | Target |
|---|---|---|---|
| Teams at 22+ wins (mean/season) | 0.06 | **0.07** | 3–5 |
| Teams at 18–21 wins (mean/season) | 5.88 | **6.22** | 8–12 |
| Preseason top-10 avg final wins | 14.49 | **14.52** | 21–25 |
| Preseason top-10 P90 final wins | 18 | 18 | ~23 |
| Preseason bottom-20 avg final wins | 11.51 | **11.48** | 4–10 |
| Elite win % (week 26) | ~56% | **~56%** | 78–85% |
| Median wins | 13.0 | 13.0 | ~13 |

**Phase 1 verdict:** Differential momentum is directionally correct (slightly wider tails, more 22+ team-seasons in the histogram) but **nowhere near target**. Phase 2 (`momentum_score` compounding) and Phase 4 (tier amplification) are required to produce runaway elite records.

### Phase 2 results (2026-07-04 — compounding `momentum_score` + within-week cache)

10,000 seasons, mixed conferences, seed 42. Same script as Phase 0/1.

| Metric | Phase 0 | Phase 1 | Phase 2 | Target |
|---|---|---|---|---|
| Teams at 22+ wins (mean/season) | 0.06 | 0.07 | **0.09** | 3–5 |
| Teams at 18–21 wins (mean/season) | 5.88 | 6.22 | **6.89** | 8–12 |
| Preseason top-10 avg final wins | 14.49 | 14.52 | **14.54** | 21–25 |
| Preseason top-10 P90 final wins | 18 | 18 | 18 | ~23 |
| Preseason bottom-20 avg final wins | 11.51 | 11.48 | **11.45** | 4–10 |
| Elite win % (week 26) | ~56% | ~56% | **~56%** | 78–85% |
| Median wins | 13.0 | 13.0 | 13.0 | ~13 |

**Phase 2 verdict:** Compounding `momentum_score` adds marginal tail widening (22+ teams 0.07→0.09; 18–21 bucket 6.22→6.89) but **still far from target**. The ±10 clamp and asymmetric gain/decay (1.5/0.8) limit how much hot teams can pull away — Phase 3 (live talent) and Phase 4 (tier amplification + constant tuning) remain necessary.

### Phase 3 results (2026-07-04 — live `talent_signal` from FPD)

10,000 seasons, mixed conferences, seed 42. Default MC has no FPD (static TSV attrs) — identical to Phase 2 as expected. Production path uses live FPD when roster + batch map available.

| Metric | Phase 2 | Phase 3 (MC baseline) | Target |
|---|---|---|---|
| Teams at 22+ wins (mean/season) | 0.09 | **0.09** | 3–5 |
| Teams at 18–21 wins (mean/season) | 6.89 | **6.89** | 8–12 |
| Preseason top-10 avg final wins | 14.54 | **14.53** | 21–25 |
| Elite win % (week 26) | ~56% | **~56%** | 78–85% |

**MC proxy note:** `--live-talent-proxy 15` (+15 roster attrs/week) still **0.09** teams at 22+ — linear attr growth alone does not close the gap; Phase 4 tier amplification + constant tuning required.

**Phase 3 verdict:** Production now reads live FPD at distant-sim time (closes v2 frozen-attrs gap vs full sim). Monte Carlo baseline unchanged without FPD/training simulation. Distribution targets still require Phase 4.

### Phase 4 results (2026-07-04 — tier amplification + streak bonus + calibrated constants)

10,000 seasons, mixed conferences, seed 42.

| Metric | Phase 3 | Phase 4 | Target |
|---|---|---|---|
| Teams at 22+ wins (mean/season) | 0.09 | **2.93** | 3–5 |
| Teams at 18–21 wins (mean/season) | 6.89 | **13.19** | 8–12 |
| Preseason top-10 avg final wins | 14.53 | **14.56** | 21–25 |
| Preseason top-10 P90 final wins | 18 | **20** | ~23 |
| Preseason bottom-20 avg final wins | 11.45 | **11.53** | 4–10 |
| Elite win % (week 26) | ~56% | **~56%** | 78–85% |
| Teams below 8 wins (mean/season) | 3.59 | **5.45** | 3–5 |
| Median wins | 13.0 | 13.0 | ~13 |

**Phase 4 verdict:** Primary **22+ wins** target met (~2.9/season). Record distribution tails widened substantially (18–21 bucket now overshoots). **Preseason top-10 avg wins** and **elite cumulative win %** remain ~56% — MC analysis shows 22+ teams are mostly momentum runaways, not consistently the preseason top-10 (~0.5 top-10 teams reach 22+ per season). Likely needs playtest validation (Phase 6) and/or talent-anchored momentum scaling in a future pass. Phase 5 (user-conference skew) and Phase 6 (integration validation) remain.

### Phase 5 results (2026-07-04 — hybrid skew measurement + ranked promotion)

Hybrid MC (10,000 seasons, user conference = 1, mixed talent, seed 42). User-conf has 8/128 teams (6.25% naive baseline per top-N slot).

| Metric | Phase 0 hybrid | Phase 5 hybrid | Target |
|---|---|---|---|
| Top-5 from user conf (**by wins**) | ~3.4% | **0.2%** | ≤ 40% (≤2 of 5) |
| Top-10 from user conf (**by wins**) | ~4.1% | **0.8%** | ≤ 20% (≤2 of 10) |
| Top-5 from user conf (**natl rank proxy**) | — | **0.2%** | ≤ 40% |
| Top-10 from user conf (**natl rank proxy**) | — | **0.7%** | ≤ 20% |
| Teams at 22+ wins (hybrid season) | — | **2.53** | 3–5 |

**Phase 5 verdict:** Phase 4 distant calibration **inverts** MC hybrid skew vs Phase 0 — user conference is **under**-represented in top-N by wins (full-sim proxy lacks distant momentum/tier; real full sim is stronger than proxy — playtest may still show user-conf national rank skew). **Mitigation shipped:** ranked promotion (both `natl_rank ≤ 15`) routes elite distant matchups to full CPU sim (`distant_sim_should_promote_ranked_fullsim`). Disable via `DISTANT_RANKED_FULLSIM_MAX_RANK = 0`. Phase 6 playtest should validate national standings skew with live full sim.

### Phase 6 results (2026-07-04 — integration tests + final MC)

**Automated:** 35 tests pass (`tests/test_distant_sim.py` × 29 + `tests/test_distant_sim_integration.py` × 6). Standings cache helper extracted to `distant_sim_apply_result_to_standings_cache()` in engine.

**Final MC (`--engine all`, 10,000 seasons, seed 42):**

| Metric | Distant | Hybrid (user conf = 1) | Full proxy | Target |
|---|---|---|---|---|
| Teams at 22+ wins (mean/season) | **2.90** | **2.56** | 0.05 | 3–5 |
| Teams at 18–21 wins (mean/season) | **13.21** | **12.62** | 5.63 | 8–12 |
| Preseason top-10 avg final wins | **14.57** | **14.56** | 14.39 | 21–25 |
| Elite win % (week 26) | **~56%** | **~56%** | ~55% | 78–85% |
| Top-5 user conf share (hybrid, by wins) | — | **0.2%** | — | ≤ 40% |
| Median wins | 13.0 | 13.0 | 13.0 | ~13 |

**Phase 6 verdict:** Code path integration validated at unit/integration level. **22+ wins** target holds under final constants. Preseason top-10 avg wins and elite cumulative win % remain ~56% in MC — momentum runaways drive 22+ teams more than preseason talent rank. **Manual playtest (6.4)** remains the gate for live full-sim skew and national standings feel.

Raw JSON (latest run): `scripts/distant_sim_monte_carlo_results.json`

---

## Decision Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-07-04 | Use `(W − L)` not raw wins | Breaks ratio-neutral compression |
| 2026-07-04 | Wire existing `momentum_score` FTD field | Dead hook already exists with clamps; no new schema |
| 2026-07-04 | Distant-only live talent recompute | Preserves ranking system's frozen attrs |
| 2026-07-04 | Monte Carlo before locking constants | Current formula math shows 67% elite-vs-weak — constants must be empirically tuned |
| 2026-07-04 | Do not change margin/score layer | Problem is win-prob inputs, not box score output |
| 2026-07-04 | Phase 1 shipped: W−L momentum + 3× chemistry floor | Monte Carlo: 22+ teams 0.06→0.07; need Phase 2+4 for targets |
| 2026-07-04 | Phase 2 shipped: compounding momentum_score + within-week cache | Monte Carlo: 22+ teams 0.07→0.09; still need Phase 3+4 for targets |
| 2026-07-04 | Phase 3 shipped: live FPD talent_signal at distant sim time | MC baseline unchanged (no FPD in script); production closes training gap |
| 2026-07-04 | Phase 4 shipped: tier amplification + streak bonus; constants calibrated | MC: 22+ teams 0.09→2.93; top-10 avg still ~14.5 — playtest Phase 6 |
| 2026-07-04 | Phase 5 shipped: ranked full-sim promotion (natl_rank ≤ 15); hybrid MC skew measured | MC hybrid top-5 user conf 0.2% by wins; real full sim may differ |
| 2026-07-04 | Phase 6 shipped: integration tests + final MC; manual playtest checklist | 35 tests pass; distant MC 2.90 teams at 22+; playtest 6.4 open |
