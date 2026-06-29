# Computer Team Game Plan System (In-Game Situational Adjustments)

**Status:** Implemented (June 2026) · **Code:** `BackEnd/utils/db_utils.py`

Situational, score-aware overrides a computer team applies on top of its normal logic as a game gets out of hand. Models a coach scaling back in **tiers**: dial back aggressive strategy first (smaller lead), then rest the starters later (bigger lead). The two overrides are **independent** — each on its own thresholds; a team can be in one, both, or neither.

Both are re-evaluated at every computer-team lineup/strategy set — **quarter break** (`simulate_quarter`), **timeout** (`call_timeout`), **foul-out** (`call_timeout` FOUL_OUT) — and auto-revert when the margin drops back. **Computer teams only.** "Margin" / "lead" = the computer team's own (its score − opponent's), from `game_state["score"]`. Thresholds are strict (`>`).

---

## 1. Conservative Strategy Adjustments (scale back first)

When leading, re-roll these **eight** strategy settings low (sit on the lead). Weights in `_CONSERVATIVE_STRATEGY_ROLLS`:

| Settings | Weighted likelihoods |
|---|---|
| `offense`, `aggression` | 0: **60%** · 1: **30%** · 2: **10%** |
| `hc_trap`, `fc_press` | 0: **90%** · 1: **10%** |
| `tempo`, `alterations` | 0: **90%** · 1: **10%** |
| `fast_breaks`, `rebounding` | 0: **90%** · 1: **10%** |

**Unchanged:** `inside`, `attack`, `outside`, `play_calling`, `defense` keep their normal `_compute_strategic_strategy_settings` values — only the eight above are overridden.

**Conditions (lead):**

| Quarter | Trigger |
|---|---|
| Q1 / Q2 / Q3 | lead **> 20** |
| Q4+ (incl. OT), `time_remaining` > 239s | lead **> 20** |
| Q4+ (incl. OT), `time_remaining` ≤ 239s | lead **> 15** |

**Code:** `_conservative_strategy_active()` → `_apply_conservative_strategy_override()`, called from `autoset_strategy_settings()` right after `_compute_strategic_strategy_settings()`.

---

## 2. Blowout Lineup Adjustments (rest starters later)

When the lead becomes a true blowout, build the lineup with the **same autobuild logic and eligibility waterfall**, but **invert the ranking** — seat the **lowest-RT** players (garbage time). A player's **RT = his highest slot rating across the five positions** (`_player_rt_max`). Forced-include players (e.g. a locked FT shooter) still play. Same team-chemistry pools, so there's still variety among the benched-tier players.

**Conditions (margin of victory):**

| Situation | Trigger |
|---|---|
| Q1 / Q2 / Overtime | **never** |
| Q3 | margin **> 50** |
| Q4, `time_remaining` > 239s | margin **> 35** |
| Q4, `time_remaining` > 59s | margin **> 25** |
| Q4, `time_remaining` > 0s | margin **> 20** |

**Code:** `_blowout_lineup_active()` gates `build_lineup_from_mongo()`, which passes `prefer_lowest_rt=True` into `build_unified_autoset_lineup_from_eligible()` (ranks by `_player_rt_max`, ascending).

---

See `Timeout_System.md` (underlying `autoset_strategy_settings` lineup + strategy re-set) and `Game_Init_System.md` (`_compute_strategic_strategy_settings`, the normal non-situational computation).
