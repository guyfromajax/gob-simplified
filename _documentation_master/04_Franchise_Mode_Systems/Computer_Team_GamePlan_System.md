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

**Code:** `_conservative_strategy_active()` → `_apply_conservative_strategy_override()`, called from `autoset_strategy_settings()`.

> **UPDATED August 2026 — two changes to how this composes.**
>
> **1. `autoset_strategy_settings` is now IDEMPOTENT ON THE DERIVATION.** A CPU team's game plan
> is derived ONCE (at `TeamManager.__init__`) and persists as `team.strategy_settings_base` for
> the rest of the game. It used to recompute from the CURRENT five at every quarter break,
> timeout and foul-out, so a team's identity shifted several times a game as players tired —
> and no per-team slider configuration was reachable at all, because anything a caller set was
> overwritten by the next rebuild. Measured: **52-84% of team-games had every slider changed
> between tip and final buzzer.** What still happens every call is the situational override,
> re-evaluated against live `game_state` and applied **on top of the persisted base** — so a
> team reverts to its real game plan when the situation clears.
>
> **2. There is now a SECOND situational override on the same seam:** foul-trouble / fatigue
> self-regulation. **Conservative wins** — if sit-on-the-lead is active, self-regulation is
> skipped entirely, since both target `aggression` / `hc_trap` / `fc_press` and conservative
> damps harder. See
> [`06_Gameplay_Systems/CPU_Team_Identity_System.md`](../../06_Gameplay_Systems/CPU_Team_Identity_System.md) § Self-regulation override.
>
> **3. The base itself is no longer `_compute_strategic_strategy_settings()` for franchise CPU
> teams** — it is the identity-derived slider draw persisted on `ftd.identity`. The old
> per-slider `_strategy_roll_*` thresholds were dead in practice (`cum_nd > 350` matched 0 of
> 128 teams). Same document.

---

## 2. Blowout Lineup Adjustments (rest starters later)

> **WHO THIS APPLIES TO (changed PR0.5, 2026-08-15).** Both margin systems — this one and the
> conservative strategy override in §1 — used to skip a **user** team entirely, so they had never
> once been applied to the team doing the blowing out. They now apply to a user team **in full
> simulation**. **Turn-by-turn (Play Quarter) is unchanged and still exempt:** there the user owns
> substitutions and playcalls, and overriding them would take away a decision they are actively
> making. See [`../projects/Blowout_Governor_Spec.md`](../projects/Blowout_Governor_Spec.md) §9.

When the lead becomes a true blowout, build the lineup with the **same autobuild logic and eligibility waterfall**, but **invert the ranking** — seat the **lowest-RT** players (garbage time). A player's **RT = his highest slot rating across the five positions** (`_player_rt_max`). Forced-include players (e.g. a locked FT shooter) still play. Same team-chemistry pools, so there's still variety among the benched-tier players.

**Conditions (margin of victory):**

| Situation | Trigger |
|---|---|
| Q1 / Q2 / Overtime | **never** |
| Q3 | margin **> 40** |
| Q4, `time_remaining` > 239s | margin **> 35** |
| Q4, `time_remaining` > 59s | margin **> 25** |
| Q4, `time_remaining` > 0s | margin **> 20** |

**Code:** `_blowout_lineup_active()` gates `build_lineup_from_mongo()`, which passes `prefer_lowest_rt=True` into `build_unified_autoset_lineup_from_eligible()` (ranks by `_player_rt_max`, ascending).

---

---

## Tunable Constants

All dials live in [`BackEnd/utils/db_utils.py`](../../BackEnd/utils/db_utils.py). The code is the source of truth; values below are the current settings.

### Conservative strategy — trigger thresholds

| Constant | Value | Effect |
|---|---|---|
| `CONSERVATIVE_LEAD_THRESHOLD` | 20 | Lead needed in Q1–Q3 (and Q4+ before the late split). Higher → triggers in fewer games. |
| `CONSERVATIVE_LATE_Q4_LEAD_THRESHOLD` | 15 | Lead needed in late Q4+ (≤ time split). Lower → sits on smaller late leads. |
| `CONSERVATIVE_LATE_Q4_SECONDS` | 239 | Q4+ boundary where the lead requirement drops from 20 → 15. |

### Conservative strategy — re-roll weights (`_CONSERVATIVE_STRATEGY_ROLLS`)

Lower-skewed weights = more aggressively scaled-back play when leading. Eight settings; the other five keep normal values.

| Settings | `(values, weights)` |
|---|---|
| `offense`, `aggression` | `([0,1,2], [60,30,10])` |
| `hc_trap`, `fc_press` | `([0,1], [90,10])` |
| `tempo`, `alterations` | `([0,1], [90,10])` |
| `fast_breaks`, `rebounding` | `([0,1], [90,10])` |

### Blowout lineup — trigger thresholds

| Constant | Value | Effect |
|---|---|---|
| `BLOWOUT_Q3_MARGIN` | 40 | Margin to rest starters in Q3. Was 50 — an unexplained outlier against the Q4 ladder, which steps 35/25/20 as time runs down. A Q3 lead needs *more* margin to be safe than a Q4 lead, not 15 more than the tier right after it. |
| `BLOWOUT_Q4_MARGIN_EARLY` | 35 | Q4 margin, > early time split remaining. |
| `BLOWOUT_Q4_MARGIN_MID` | 25 | Q4 margin, > mid time split remaining. |
| `BLOWOUT_Q4_MARGIN_LATE` | 20 | Q4 margin, any time remaining. |
| `BLOWOUT_Q4_EARLY_SECONDS` | 239 | Q4 boundary: early (35) → mid (25) margin tier. |
| `BLOWOUT_Q4_MID_SECONDS` | 59 | Q4 boundary: mid (25) → late (20) margin tier. |

Lower margins → starters pulled sooner. All blowout thresholds are above the conservative ones by design (scale back strategy first, rest starters later).

---

See `Timeout_System.md` (underlying `autoset_strategy_settings` lineup + strategy re-set) and `Game_Init_System.md` (`_compute_strategic_strategy_settings`, the normal non-situational computation).
