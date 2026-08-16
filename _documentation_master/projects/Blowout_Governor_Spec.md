# Blowout Governor — Implementation Spec

**Status:** draft for implementation by the IDE agent
**Source brief:** `_documentation_master/projects/Blowout_Governor_Brief.md`
**Backlog item:** `_documentation_master/projects/bugs.md` → "Full Product Perfection" #4, *Comprehensive Blowout Governor*
**Repo state referenced:** `gob-simplified`, BackEnd @ 2026-08-15
**Citations:** every file:line, constant and function name below was verified against the working tree. `scripts/` and `reports/` references were not machine-verified — treat §8's harness invocations as needing a smoke run.
**Rev 4 (2026-08-15):** Margins measured (§1.5). Cause isolated by matched pair — the user team is excluded from both existing blowout systems, and that exclusion accounts for nearly all of a 13.4-point gap against a talent-matched CPU team. New **PR0.5** ships that one-line fix first and alone. `SAFE_LEAD_A/B` promoted from provisional: they reproduce the existing thresholds where those fire. The ≤10% engagement target is **retracted**.
**Rev 3 (2026-08-15):** §1 rewritten against the **production** season (`925178c53`). The `shot_threshold` mechanism is reframed: not railing, not AutoTrain — the intended EOG compounding loop, with the user at its extreme. §1.2 sizes the attribute contribution at ~20–25 points using the repo's own fitted FG% slope, leaving the bulk of the reported 80–110 unexplained. Two standalone findings in §1.3 (EOG bands cut too low; `discipline` drift disabling the existing brake). New gate **G8** and an EOG-coupling warning in §8. Prior H1 downgraded.

---

## 0. Scope and standing assumptions

Assumptions made where the brief was silent. Overturn any of these and the affected section changes.

| # | Assumption |
|---|---|
| A1 | The governor applies to **both** teams' *style* decisions in Full Sim / Sim Rest of Game. |
| A2 | In **Play Quarter**, the governor never overrides an explicit user Playcall Center call, and never changes the user's lineup — the user owns their subs. It still governs the CPU opponent, and possession-level effects (§4 L5) still apply to both teams. |
| A3 | "Contain the margin" means **compress the tail, preserve the ordering**. A better team must still win, and must still win bigger against a worse team. The governor is judged on both. |
| A4 | No new RNG draws in the common path (§7.3). Determinism is a hard contract in this repo. |

---

## 1. Phase 0 — diagnose before governing

**Do not build the governor first.** Nobody has measured the margin distribution yet. Every threshold in this spec is fitted to a distribution we have not looked at, and there is at least one plausible upstream cause a governor would mask rather than fix.

### 1.1 What the production season settled

Source: `_documentation_master/projects/team_player_attribute_tuning.md` @ `925178c53` — the **production** franchise `6a8073d78294292a794bec4c`, user team HA Rushmore, 26-0 regular season / 33-0 with postseason, 128 teams, 1,524 players, played through the UI.

**`shot_threshold` drift is not railing, and AutoTrain is not the cause.** Mean 59.5, median 56.0, spread 10–124, **zero rails in either direction**. The user's training allocation is identical to the CPU's, and week 26 shows the same `+3` from training that CPU teams get. Couer d'Alene went 26-0 with the same identity pair and no AutoTrain. Two independent seasons now agree.

**But the user still sits at the extreme: `shot_threshold` 10, best in the league, against a CPU mean of 59.5** — and `corr(shot_threshold, wins) = −0.495`, second only to talent at `+0.750`.

**This is the EOG compounding loop, and it is working as designed.** `BackEnd/constants/eog_attr_bands.py:53-56` is explicit:

> *"`shot_threshold` is the only attribute whose band INPUT it also DETERMINES. It is the bar a shot must clear, so it sets team FG%, and FG% selects the band that moves it. That loop is INTENDED — it is the compounding effect of game performance — so the band is not a defect and must not be removed from EOG or inverted. The fault was magnitude only."*

The band is tuned to a **variance** target — *"near-neutral centre, spread that grows meaningfully, few teams reaching either rail"* (`:59-61`). Prod delivered exactly that. Shipping 26-0 and ending up with the league's best shooting attribute is the system doing its job.

### 1.2 How much of the margin the attributes actually explain

The repo carries its own fitted response (`eog_attr_bands.py:79`):

> `FG% = 51.25 − 0.14126 × shot_threshold`, residual sd 7.67pp

Applying it to the prod gap:

| | `shot_threshold` | fitted FG% |
|---|--:|--:|
| HA Rushmore | 10 | **49.8%** |
| CPU mean | 59.5 | **42.8%** |
| **gap** | 49.5 | **≈ 7.0 pp** |

At roughly 60 FGA a game, 7pp is ~4 extra makes — call it **8–10 points of margin**. Add 94th-percentile talent (and note Rushmore is *15th* percentile on `offensive_efficiency`), and the attribute story plausibly accounts for **20–25 points**.

**The brief reports margins of 80–110.** If that holds when measured, **55–85 points are not explained by any attribute gap** — which is the case for building this governor. Caveats, stated plainly: the slope is flagged ⚠️ INTERIM and season-specific (`:47-49`, and the 2026-08-15 block-threshold change invalidates it by construction), residual sd is 7.67pp, and **the 80–110 figure is still anecdotal — nobody has measured margins.** §1.4 step 1 is the gate.

### 1.3 Two live findings worth acting on regardless

**F1 — the EOG bands are cut too low for the current engine, and the league is drifting down.** The band re-cut of 2026-08-14 simulated to *"mean 90.0, sd 20.5, drift −0.05, ZERO rails"* (`:92-94`). Prod came in at **mean 59.5** — 30 points below target — and the staging season landed ~32 below MID. Two seasons, same direction. `FG_PCT_HIGH = 37` sits below the league's actual FG%, so most team-games take the reward branch and everyone's threshold falls together. The code predicts this exact failure mode and instructs: *"The equilibrium FG% is SEASON-SPECIFIC. RE-DERIVE IT BEFORE RE-CUTTING AND NEVER REUSE A PREVIOUS SEASON'S FIT."* Re-derive against the prod season. **This is not the governor's job and should not wait for it.** ✅ **RESOLVED 2026-08-15:** re-cut to `FG_PCT_MID=40` / `FG_PCT_HIGH=45` against the prod season (league FG% mean 45.16; the old 22/37 sat at the 18th/0.2nd percentiles and the penalty branch was dead at 8 of 4,220 team-games). Owner chose 40/45 over the drift-neutral 35/40, so the league now leans **upward** (~+35.9/season) rather than downward. Measured decomposition: training **+57.2**/team-season vs EOG **−87.7** (net −30.5, init 90 → 59.5). Training degrades shot_threshold league-wide because `_SCRIMMAGE_BASELINE = 1` sits in the `+0..+5` band — see `eog_attr_bands.py`.

**F2 — attribute drift has silently weakened the one brake you already have.** Prod `discipline` mean **+9.2**, with **55 of 128 teams railed at +20**. The existing balancing system sets the leading team's trigger to `base + core8_gameplay(discipline)`, `core8_gameplay` being value ÷ 2 (`phase_resolution.py:3632`; `utils/team_attr_scale.py:49-53`). A team railed at +20 needs `base + 10` — a **16-to-20-point** lead before the rubber band engages at all, versus 6–10 for a neutral team. Nearly half the league has drifted out of reach of its own anti-blowout system. §4 L5 replaces this mechanism entirely, but the finding stands on its own.

> **Downgraded:** an earlier draft proposed H1, *"offense outruns defense league-wide,"* on staging figures (`off_eff` +11.9 vs `def_eff` +4.5, a 7.4-point tilt). Prod shows **+11.4 vs +8.7 — a 2.7-point gap**. Much weaker. Deprioritise; do not build against it.

### 1.4 The gate

Still outstanding, and cheap while a read-only prod connection is open:

1. **Margin distribution.** Final scores, all games, all 26 weeks of franchise `6a8073d78294292a794bec4c`. Report median / p90 / p99 / max. Split **user-team games vs CPU-vs-CPU games** (Rushmore went 33-0 — the CPU-vs-CPU population is the honest baseline), and split by week band (1–8 / 9–17 / 18–26) to test whether margins genuinely widen across a season or were always this size. That season-progressive shape is the single most diagnostic thing available, and it either confirms the compounding-loop story or kills it.
2. **Regress margin on the talent gap.** Use **sum of the 12 player attributes per team** — already validated at `corr(talent, wins) = +0.750`, and a better quality metric than the `Distant_Sim_Tuning.md:173` composite this spec previously proposed. The residual after talent is what the governor exists to contain, and its size sets the whole scope.
3. **FG% by margin bucket.** Needed to size the §8 G8 coupling risk, and it feeds F1's re-derivation for free.

### 1.5 Measured baseline (prod, franchise `6a8073d78294292a794bec4c`)

| split | n | median | p90 | p99 | max | mean |
|---|--:|--:|--:|--:|--:|--:|
| all | 1,664 | 12 | 28 | 53 | 116 | 14.6 |
| **user games** | 26 | **30** | 83 | 116 | **116** | **35.2** |
| CPU vs CPU | 1,638 | 12 | 28 | 48 | 74 | 14.3 |

Mean margin by week band — **the compounding is real and it is user-only**:

| band | user | CPU vs CPU |
|---|--:|--:|
| 1–8 | 23.9 | 13.0 |
| 9–17 | 26.9 | 14.9 |
| 18–26 | **53.4** | 14.9 |

Two things follow. **The 80–110 figure in the brief is the tail, not the typical game** — user median is 30. And the CPU population is *flat* across the season while the user's more than doubles, so whatever is running away is not league-wide.

**Cause, isolated by matched pair.** Rushmore (user) vs Couer d'Alene (CPU): talent 563.8 vs 564, both 26-0, same Run and Gun / Full-Court Press identity. Cumulative margin:

| | Q1 | half | Q3 | final |
|---|--:|--:|--:|--:|
| Rushmore (user) | 10.7 | 18.2 | 27.2 | **33.3** |
| Couer d'Alene (CPU) | 10.1 | 17.6 | 19.4 | **19.9** |

Identical through halftime (+0.6). Second half: Rushmore **+15.1**, Couer d'Alene **+2.3**. Talent would show in the first half; it does not. The divergence begins as the lead crosses **20** — the conservative-strategy threshold — and the CPU team has that mechanism while the user team is excluded from it by `db_utils.py:326` and `:1158`. **The blowout systems have never once been applied to the team doing the blowing out.** Hence PR0.5.

n = 26 (Rushmore) and 30 (Couer d'Alene), both including postseason, so the band means are the trustworthy figures and the tail percentiles are directional.

**Gate:** publish the margin distribution before PR2. Every constant in §3 (`SAFE_LEAD_A/B`, the tier lines) and every target in §8 is provisional until it exists. If p99 comes back at 38 rather than 80+, this spec is over-built and should shrink to L1 + L4 only.

---

## 2. Design principles

1. **Govern possessions, not competence.** The primary levers reduce the *number of scoring opportunities* (tempo, fast breaks, presses, bench minutes). They do not make the leading team play badly. A team that is +0.4 PPP better still shows it — it just gets fewer possessions to express it. This is what lets the governor compress margins without undermining strong wins.
2. **One margin authority.** There are currently **seven** independent, unrelated margin ladders (§5). Every new lever reads from one function.
3. **Continuous, not banded.** Replace step thresholds with a smooth pressure scalar `G ∈ [0,1]`. Steps produce visible pops in the play-by-play; a ramp does not.
4. **Read-time only.** The governor never mutates `strategy_settings`. This is already the enforced contract in `situational_logic.py:178-180` and the reason `strategy_settings_base` exists (`db_utils.py:1168-1176`). Violating it corrupts the persisted team/FTD doc.
5. **User agency wins.** An explicit Playcall Center call always beats the governor.
6. **Deterministic damping.** No new RNG draws — follow the `_apply_self_regulation_override` precedent (`db_utils.py:1094-1096`).

---

## 3. The margin authority

New module: `BackEnd/utils/game_governor.py`. Constants: `BackEnd/constants/governor.py`.

### 3.1 Time base

Quarters are 480s, OT 240s (`BackEnd/main.py:492`). Regulation total = 1920s.

```python
def seconds_remaining_in_game(game_state) -> float:
    """Total regulation seconds left. OT always returns the OT clock (no future quarters)."""
    q = int(game_state.get("quarter") or 1)
    t = float(game_state.get("time_remaining") or 0)
    if q >= 5:
        return t
    return t + (4 - q) * 480.0
```

### 3.2 Safe lead

Comeback capacity scales with the square root of remaining possessions (variance of a sum of n possessions grows as √n), so the threshold at which a lead is functionally decided is:

```python
SEC_PER_POSSESSION = 15.0        # TEMPO_PARAMS["normal"]["mean"], constants/__init__.py:640
SAFE_LEAD_A = 2.5                # validated against prod anchors — see below
SAFE_LEAD_B = 6.0                # validated against prod anchors — see below

def safe_lead(game_state) -> float:
    poss = max(0.0, seconds_remaining_in_game(game_state)) / (2.0 * SEC_PER_POSSESSION)
    return SAFE_LEAD_A * math.sqrt(poss) + SAFE_LEAD_B
```

Reference values at the provisional constants:

| game clock remaining | poss/team left | safe lead |
|---|---|---|
| 1920s (tip) | 64 | 26.0 |
| 960s (half) | 32 | 20.1 |
| 480s (start Q4) | 16 | 16.0 |
| 240s | 8 | 13.1 |
| 60s | 2 | 9.5 |

### 3.3 Governor pressure `G`

```python
GOV_ENGAGE_RATIO = 1.00          # G starts ramping at margin == safe_lead
GOV_FULL_RATIO   = 2.00          # G == 1.0 at twice safe_lead
GOV_RELEASE_HYSTERESIS = 0.08    # G must fall this far below a tier line to release it

def governor_pressure(team, game_state) -> float:
    margin = team_score_margin(team, game_state)     # reuse db_utils._team_score_margin
    if margin is None or margin <= 0:
        return 0.0
    ratio = margin / safe_lead(game_state)
    return clamp01((ratio - GOV_ENGAGE_RATIO) / (GOV_FULL_RATIO - GOV_ENGAGE_RATIO))
```

`G` is the **leading** team's pressure. The trailing team gets `T` (§6). Both are recomputed every turn, cost is a sqrt and a divide, and both are pure functions of `game_state` — no RNG, no I/O.

**These constants reproduce the existing thresholds where they fire**, which is the reason to keep them rather than invent new ones:

| situation | `safe_lead` | `G` | governor tier | existing system |
|---|--:|--:|---|---|
| 20-point lead at halftime | 20.1 | 0.00 | — | conservative fires at >20 |
| 20-point lead entering Q4 | 16.0 | 0.25 | T1 scale back | conservative (scale back, no benching) |
| 35-point lead entering Q4 | 16.0 | **1.00** | T3 full bench | blowout ladder benches at >35 |

Measured on prod, **28% of CPU-vs-CPU games enter Q4 at ≥20 and 6% at ≥35** — so roughly a quarter of that population is already damped, and its distribution is healthy (max 74 over 1,638 games). An earlier draft proposed fitting A/B so `G` engages in ≤10% of games; **that target was wrong** and is retracted. ~25–30% engagement is the working status quo. Fit against *that*.

The three defects the governor actually fixes are therefore narrower than "the thresholds are wrong": they are **steps instead of ramps**, **lineups cannot engage before Q3**, and **user teams are skipped entirely** (the last of which is PR0.5, not the governor).

### 3.4 Hysteresis and state

Store per-team on `game_state["governor"] = {team_id: {"G": float, "tier": int}}`, refreshed **every turn** in a new `TurnManager._refresh_governor_state()`, called from **both** call sites of the existing `_refresh_situational_team_state()` (`turn_manager.py:3387`): `set_strategy_calls()` at `:3419`, **and** `determine_defensive_pressure_type()` at `:6540`. The second site exists precisely because that choke point is reachable outside the normal `run_micro_turn` path — miss it and the governor state feeding L3 is stale.

A tier, once entered, only releases when `G` drops `GOV_RELEASE_HYSTERESIS` below its entry line. Without this the lineup flips every possession around a boundary.

### 3.5 Why this replaces the current ladders

The existing blowout-lineup gate fires at **>50 in Q3** and **>35 early in Q4** (`db_utils.py:288-293`). Against `safe_lead`, a 50-point Q3 lead is `G = 1.0` several times over — i.e. the bench does not come in until the game is already a 60-point win. That single fact is likely a large share of the reported margins independent of anything else. The documented design intent (`Computer_Team_GamePlan_System.md:113`) is *"scale back strategy first, rest starters later"* — the ordering is right, the magnitudes are not.

---

## 4. Lever ladder

Tiers are `G` bands. Each lever names its exact insertion point.

| Tier | `G` | Name | Levers |
|---|---|---|---|
| 0 | < 0.15 | Normal | none |
| 1 | ≥ 0.15 | Scale back | L1 tempo, L2 fast break, L3 press/trap |
| 2 | ≥ 0.40 | Rest | L4 progressive substitution, L1/L2/L3 deepen |
| 3 | ≥ 0.70 | Shut it down | L5 shot-threshold delta, all above at max |

### L1 — Tempo

**Insert:** `BackEnd/models/turn_manager.py:3487`, inside `set_strategy_calls()`, as a new tier between the situational override and the Playcall Center override.

Precedence becomes: sim roll → situational (Q4/OT) → **governor** → Playcall Center.

```
leading team:  G ≥ 0.15 → tempo_call = "normal" if rolled "fast" else rolled
               G ≥ 0.40 → tempo_call = "slow"
trailing team: T ≥ 0.15 → tempo_call = "fast" if rolled "normal" else rolled
               T ≥ 0.40 → tempo_call = "fast"   (until give-up, §6.2)
```

This is the highest-leverage single lever. `tempo_call` feeds possession length (`TEMPO_PARAMS`, `constants/__init__.py:638`), the optimal-shot bar (`OPTIMAL_BAR_TEMPO_MULT`, `motion_step_decision.py:221`), the undisciplined-shoot rate, and subtle-movement precedence. Slowing the leading team from "fast" (10s mean) to "slow" (20s mean) roughly halves its possession count for the governed stretch — the margin compression follows arithmetically, with no efficiency penalty applied to anyone.

### L2 — Fast breaks

**Insert:** chain into `situational_logic.slow_it_down_defense_setting()` (`BackEnd/utils/situational_logic.py:174`).

That one function is already the read-time gate for `fast_breaks` at `shot_manager.py:1780` (the dominant HCO→DREB path) and `dreb_fast_break_arming.py:301` (FT / OREB / FB-miss paths), and for `aggression` at `steal_fast_break_routing.py:104`. Chaining there covers **all three fast-break origins with zero new call sites**.

⚠️ **Blast radius.** The function has **ten** call sites, not three. Beyond the three above, `aggression` is read through it at `shot_manager.py:1208` (the **block-attempt roll**) and `phase_resolution.py:500, 2881, 3063, 7857` (the passive/normal/aggressive posture map). Damping `aggression` through this chain therefore also suppresses shot blocking and general defensive posture — a much wider change than "fewer transition pushes," and a direct threat to gate G7.

**Therefore: PR3 governs only `fast_breaks`, `hc_trap`, and `fc_press`.** `aggression` is deliberately excluded from `GOVERNED_KEYS` until PR6, and when it is added, the block-attempt path at `shot_manager.py:1208` must be measured separately (BLK in refstats) or explicitly exempted.

Rename it to something honest (`effective_defense_setting`) and give it two stages:

```python
GOVERNED_KEYS = ("fast_breaks", "hc_trap", "fc_press")   # "aggression" deferred to PR6

def effective_defense_setting(game_state, team, key, raw_value):
    if key in SLOW_IT_DOWN_CONSERVATIVE_SETTINGS and is_team_slow_it_down(game_state, team_id):
        return 0                                       # existing, unchanged, wins
    if key in GOVERNED_KEYS:
        return governor_setting(game_state, team, key, raw_value)   # new
    return raw_value
```

Damping schedule (deterministic, integer, damp-only for the leader):

```
fast_breaks:  G ≥ 0.15 → min(raw, 2)
              G ≥ 0.40 → min(raw, 1)
              G ≥ 0.70 → 0
```

Slider→probability is linear (`SLIDER_TO_FAST_BREAK_PROB = {0:0.0, 1:0.25, 2:0.5, 3:0.75, 4:1.0}`, `shared.py:279`), so these are literal probability caps: 50% → 25% → none.

### L3 — Press and trap

**Insert:** `BackEnd/models/turn_manager.py:6600`, inside `_select_defensive_pressure_type()`, immediately after the existing Slow It Down early return. Preserves the established precedence: Quick Shot → user Playcall Center → Slow It Down → **governor** → slider roll.

```
hc_trap / fc_press:  G ≥ 0.15 → min(raw, 1)
                     G ≥ 0.40 → 0   (return "HCO")
```

`aggression` shares the same tuple but is **held back to PR6** for the blast-radius reason in L2. When added: `G ≥ 0.40 → min(raw, 1)`.

### L4 — Progressive substitution

This replaces the binary `prefer_lowest_rt` inversion with a depth dial. **Two changes, both required.**

**(a) Depth, not a flip.** Change `build_unified_autoset_lineup_from_eligible` (`db_utils.py:568`) to take `bench_depth: int` (0–5) plus a `deep_bench: bool` in place of `prefer_lowest_rt: bool`.

Order the eligible pool by `_player_rt_max` descending (respecting `force_include_ids` throughout), then:

- `bench_depth = d`, `deep_bench = False` → **natural rotation.** On-court five = ranks `d+1 … 5+d`. Sit your top `d`, bring the next men up. `d=0` is today's normal path.
- `deep_bench = True` → **walk-on time.** The five **lowest**-RT eligible players, exactly today's `prefer_lowest_rt=True`.

> ⚠️ These are not the same thing at `d=5`, and an earlier draft of this spec got it wrong. Today's `prefer_lowest_rt` sorts the *whole* eligible pool ascending and takes the five worst (`db_utils.py:612-621`); with a 13-man eligible pool that is ranks 9–13. Natural rotation at `d=5` gives ranks 6–10. Both are wanted, at different points on the ramp — hence two parameters.

Keeps the documented contract from `CPU_Team_Rotation_System.md:78` — *invert selection, not seating* — while making it granular.

```
G ≥ 0.40 → bench_depth 1
G ≥ 0.55 → bench_depth 2
G ≥ 0.70 → bench_depth 3
G ≥ 0.85 → bench_depth 5           (second unit)
G ≥ 0.92 → deep_bench = True       (today's behaviour, end of the ramp)
```

Sitting your two best players at a 20-point lead with 6:00 to play is what a real coach does, and it costs the leading team real efficiency without ever making anyone play *badly* — the backups are simply worse. This is the second-highest-leverage lever after tempo.

**(b) Cadence.** Lineups currently rebuild only at quarter breaks, timeouts and foul-outs. `CPU_Team_Identity_System.md:419-421` puts `autoset_strategy_settings` at ~8.9 calls per team-game; lineup rebuilds ride the same stoppages, so treat 8.9 as the order of magnitude, not a measured lineup count — confirm it in PR0 telemetry. Either way, a governor that can only act at a quarter break cannot "enter its backups sooner," which is the brief's explicit ask.

Add a dirty flag: when `_refresh_governor_state()` observes a **tier crossing**, set `game_state["governor_lineup_dirty"] = True`. The turn loop honours it at the next dead ball (made FT, timeout, out-of-bounds, period edge — never mid-possession) by calling the existing `build_lineup_from_mongo` path, then clears it. Cap at `GOV_MAX_EXTRA_REBUILDS = 4` per team-game to bound the cost.

**(c) Bug fix, required.** `fill_unified_lineup_gaps` (`db_utils.py:631-666`) has no blowout parameter, so a foul-out during garbage time seats the **best** available player. Thread `bench_depth` through.

### L5 — Shot threshold (replaces the current balancing system)

`apply_balancing_system` (`phase_resolution.py:3571`) is the "VERY blunt version" the brief refers to, and it is blunter than it looks:

- It fires at a **6–10 point** margin *before team attributes* (`trailing_thresholds` / `leading_thresholds`, Q1/Q2 6, Q3 8, Q4 10). The effective trigger is `base − core8_gameplay(fight)` for the trailing team and `base + core8_gameplay(discipline)` for the leader, clamped to a minimum of **1** — so a high-`fight` team's trailing override can engage at a **1-point** deficit. In practice this fires in essentially every competitive possession of every game.
- It is a **hard replacement**, not a delta: the team's own `shot_threshold` attribute is discarded and replaced with `BALANCING_TRAILING = -30` or `BALANCING_LEADING = 170` (`shot_threshold_scale.py:20-21`) — a 200-point swing on a 200-point scale.
- Consequence: for most of a normal game, **team shooting quality does not affect shot outcomes at all** — the rubber band overwrites it. That is a design problem in its own right, separate from blowouts.

**Replace with a governed additive delta:**

```python
GOV_SHOT_THRESHOLD_MAX_DELTA = 25       # PROVISIONAL — fit in Phase 3

def shot_threshold_delta(G_or_T, is_leader) -> int:
    if G_or_T < 0.70:
        return 0
    scaled = (G_or_T - 0.70) / 0.30
    d = int(round(scaled * GOV_SHOT_THRESHOLD_MAX_DELTA))
    return d if is_leader else -d          # golf score: + is harder
```

Apply as `shot_threshold = off_team.team_attributes["shot_threshold"] + delta`, clamped to `shot_threshold_scale.clamp()`, in the `else` branch at `shot_manager.py:876` — **not** as a first-branch replacement.

**Bug, fix in the same PR:** `balancing_shot_threshold_override` is written to bare `game_state` with **no team ownership** (`phase_resolution.py:3645, 3649`) and popped by the first `resolve_shot` that reads it (`shot_manager.py:868-872`). It is set only in the HCO path but read by *any* shot. `apply_balancing_system` does clear it in its `else` branch at the top of each HCO turn, so the leak is not every possession — it is any shot resolved **without an intervening HCO turn**: fast breaks, putbacks, and `resolve_final_turn_shot_logic` (`phase_resolution.py:7159`). Those shots consume a modifier computed for a different team-state, and because the balancing branch precedes the fast-break branch, a leaked override also **swallows `fast_break_shot_threshold_override` entirely**. The additive-delta design removes the shared-state channel, which is the fix.

---

## 5. Disposition of the seven existing margin systems

| # | System | File | Disposition |
|---|---|---|---|
| 1 | Blowout lineup (50/35/25/20) | `db_utils.py:288-342` | **Replaced** by L4. Delete `BLOWOUT_*`; keep `_team_score_margin` (promote to governor module). |
| 2 | Conservative strategy (20/15 + roll table) | `db_utils.py:984-1020` | **Replaced** by L1/L2/L3. It is stochastic and stoppage-only; the governor is deterministic and per-turn. Removing it also removes the "CONSERVATIVE WINS" mutual-exclusion tangle at `db_utils.py:1180-1189`. |
| 3 | Self-reg desperation (−6 in last 5:00 of Q4; **all of OT**, time gate bypassed) | `db_utils.py:1034-1047` | **Keep**, unchanged. Different concern (foul trouble), and §6 subsumes its intent without conflicting. |
| 4 | Balancing shot threshold (6/8/10) | `phase_resolution.py:3571` | **Replaced** by L5. |
| 5 | Situational Logic Q4/OT bands | `situational_logic.py` | **Keep and outrank the governor.** It models end-of-game clock tactics, which are correct and orthogonal. Governor is subordinate everywhere they meet. |
| 6 | CPU tempo Q4 ratio rules | `team_manager.py:498-538` | **Keep** for now — it sets the identity base once. Revisit in Phase 3 if it fights L1. |
| 7 | Run-out-clock give-up (`delta < -18`) | `situational_logic.py:306` | **Replace** the magic `-18` with the §6.2 give-up condition; keep the behaviour. |

Also fix while in the area: blowout logic never fires in OT (`quarter >= 5` falls through, `db_utils.py:342`) while conservative strategy does. `G` is quarter-agnostic by construction, which resolves the inconsistency.

---

## 6. The trailing team

### 6.1 Dial up

`T` is computed identically to `G` from the trailing team's (negative) margin, using `abs(margin)`. Levers mirror L1–L3, raising rather than damping, capped at 4:

```
tempo:        T ≥ 0.15 → prefer "fast"
fast_breaks:  T ≥ 0.15 → max(raw, 3);  T ≥ 0.40 → 4
fc_press / hc_trap: T ≥ 0.40 → max(raw, 2)
aggression:   T ≥ 0.40 → max(raw, 3)
```

Note this is **new behaviour the codebase has already named and deferred** — `db_utils.py:283-286`: *"raising sliders ABOVE the identity base is new behaviour belonging to the deferred mid-game adjustment layer."* This spec is that layer. Cite it in the PR.

Second-order effect worth stating plainly: a trailing team that presses and runs *increases* variance, which widens some margins further. That is correct and desirable — it is how real comebacks and real 40-point losses both happen — but it means L1–L3 on the leader must carry the compression, and the Phase 3 fit must be done with both sides active.

### 6.2 Give-up

The brief: *"until the point in the game when it is clearly out of hand."*

```
GOV_GIVE_UP = 0.85     # opponent's G
```

When the **opponent's** `G ≥ 0.85`, the trailing team drops all of §6.1 back to its identity base and stops force-fouling. This replaces the inline `delta < -18` at `situational_logic.py:305` with a time-aware condition — down 18 with 6:00 left is not the same game as down 18 with 0:20 left, and the current constant treats them identically.

---

## 7. Hard constraints

### 7.1 Read-time only
Never mutate `strategy_settings` or `team_attributes`. Every governed value is computed at the point of read. Enforced precedent: `situational_logic.py:178-180`, `db_utils.py:1168-1176`.

### 7.2 User precedence
Playcall Center overrides beat the governor, always — `turn_manager.py:3488` (tempo), `:6585-6592` (press/trap), `:2735` (offense call). The governor tier sits *below* the user tier in every ladder. A governor that overrides an explicit user call will be read as a bug, and will be reported as one.

### 7.3 RNG determinism
All damping is deterministic integer clamping — no `random` calls. Measurement harnesses pin `PYTHONHASHSEED` via `BackEnd/utils/repro.py:95` `pin_hash_seed()` (re-execs the process if unset, and fails loudly if the re-exec does not take), and the repo treats draw-count changes as anchor-invalidating (`scripts/sim_verify/README.md`). Adding a roll to the governor would invalidate every reference anchor in `reports/perf/` and make the Phase 3 measurement uninterpretable. If a roll ever becomes necessary, use `sim_rng` and re-cut the anchor deliberately, as a separate PR, with the invalidation documented.

### 7.4 One shared path
Full sim and user-played both run `GameManager.simulate_macro_turn()` → `TurnManager.run_micro_turn()` (`main.py:928`, `api/api.py:5667`). There is no fork. Any lever placed at §4's insertion points is automatically live in both modes — which is what A2 requires, and is also why L4 must respect `is_user_team`.

---

## 8. Acceptance criteria

Measurement runs on the existing rig — no new harness needed for the sim itself:

```
FRANCHISE_CPU_SIM_USE_POOL=0 python3 scripts/perf_sim_baseline.py \
    --franchise 6a28436c98dbd04e902eee09 --week 7 --games 63 --mode cpu
```

Read-only, no Mongo writes, emits `refstats_<ts>.csv` with per-team `final_score`, plus per-game `away_score`/`home_score` in `phase_breakdown_<ts>.json`. Compare arms with `scripts/sim_verify/distcompare.py`.

**New tooling required (PR0):** `scripts/sim_verify/margins.py` — reads one or more `phase_breakdown` JSONs, joins each game to a team-quality metric, and emits the margin distribution overall and by quality-gap bucket. Use the existing composite from `Distant_Sim_Tuning.md:173` (`off_eff + def_eff − int(shot_threshold/20)`) as the quality metric, or `total_player_attrs` — state which.

### Gates

| # | Criterion | Target |
|---|---|---|
| G1 | p99 absolute margin | ≤ 45 |
| G2 | max absolute margin over 63 games | ≤ 60 |
| G3 | median absolute margin | within ±3 of baseline — the governor must not flatten normal games |
| G4 | **Spearman ρ(talent gap, margin)** | **≥ baseline ρ.** This is the "don't undermine strong wins" gate. Compressing the tail must not destroy the relationship between being better and winning bigger. A governor that passes G1 by making every game a coin flip fails here. Use **sum of the 12 player attributes** as the quality metric — validated on prod at `corr(talent, wins) = +0.750`. |
| G5 | Upset rate by quality-gap bucket | no increase beyond noise. The favourite must still win as often. |
| G6 | Ungoverned games byte-identical | In games where `G` never exceeds 0.15, refstats must match baseline **exactly**. Deterministic damping + no new draws makes this achievable, and it is the cleanest possible regression proof. |
| G7 | Leading-team efficiency at `G < 0.15` | unchanged. Verify FG%, TPM, possessions in the sub-threshold sample. When `aggression` joins `GOVERNED_KEYS` in PR6, add **BLK** and **PF** to this check — that key also gates the block-attempt roll at `shot_manager.py:1208`. |

| G8 | **Season-level attribute drift unchanged** | After PR3–PR5, re-run a full measured season and re-cut the `team_player_attribute_tuning.md` tables. `shot_threshold` must still show near-zero rails and comparable spread. See the coupling note below — this gate is not optional. |

G6 is the gate to watch during development. If it fails, something is reading the governor when it should not be, or a draw was added.

### ⚠️ The EOG coupling — the non-obvious consequence of shipping this

`shot_threshold`'s EOG band is keyed on **team FG%** (`FG_PCT_HIGH = 45`, `FG_PCT_MID = 40` as of 2026-08-15; was 37/22), and `eog_attr_bands.py:53-56` states plainly that this attribute *"is the only attribute whose band INPUT it also DETERMINES."* Score margin is **not** an EOG input — `End_Of_Game_System.md:114` confirms `winner_score` / `loser_score` are dead parameters. So the governor does **not** touch EOG through margin.

It touches it through **FG%**, and in both directions:

- **L4 (bench)** puts worse shooters on the floor → leading team's game FG% falls.
- **L5 (threshold delta)** makes the leader's shots harder → FG% falls.
- **L1 (slow tempo)** raises the optimal-shot bar (`OPTIMAL_BAR_TEMPO_MULT["slow"] = 1.2`) → better shot selection → FG% may *rise*.

A dominant team that currently clears 37% nearly every game — taking the reward branch and compounding downward toward better shooting — might, under the governor, dip below the cut in its blowouts. **That would damp the compounding loop as a side effect.** Arguably desirable. But it is a season-long change to a carefully variance-tuned attribute economy, arriving through a feature scoped as in-game containment, and the code explicitly warns that this band *"must not be removed from EOG or inverted."*

Measure it (G8); do not discover it. If the drift moves, the correct response is to re-cut the bands against the post-governor season (per F1), not to weaken the governor.

### Test coverage

There is currently **none** — `grep -rl "blowout\|prefer_lowest_rt\|balancing" BackEnd/tests/` returns nothing. Required in the same PRs:

- `governor_pressure` unit table: margin × clock → expected `G`, including OT and the `margin <= 0` guard.
- Hysteresis: oscillating margin at a tier boundary produces at most one tier change.
- `bench_depth` selection: correct N removed, `force_include_ids` retained, seating still optimal.
- Precedence: user Playcall Center beats the governor at all three ladders.
- Determinism: seeded 20-game run byte-identical with the governor never engaging.

---

## 9. Phasing

Each phase is a separately mergeable PR with its own measurement.

| PR | Content | Exit condition |
|---|---|---|
| **PR0** | `scripts/sim_verify/margins.py`; §1.4 steps 1–3 against the just-finished season. No behaviour change. | Margin distribution published; §1.4 gate answered |
| **PR0.5** | ✅ **SHIPPED 2026-08-15**, two commits. **Task 1** — both `is_user_team` exclusions (`db_utils.py:326`, `:1158`) now fall through when `game_state["_is_full_simulation"]` is set, so the existing conservative-strategy and blowout-lineup systems apply to a leading user team in full sim. Play Quarter unchanged per A2. **Task 2** — `BLOWOUT_Q3_MARGIN` 50 → 40, normalising the ladder. **The spec's read-time `game_state` override was rejected in favour of the existing `strategy_settings_base` seam** — base already IS the pristine-plan / damped-view split the override would have reinvented, so the fix is 2 guard edits + 4 persist-site edits instead of touching 51 read sites of `team.strategy_settings`. The persistence hazard was also overstated: the user's saved gameplan lives in the FTD doc and is never written from `team.strategy_settings`; the four `api.py` sites write a per-game snapshot whose two consumers (Gameplan UI, timeout-resume) both want the plan, so all four now persist `strategy_settings_base`. That closed a latent pre-existing bug — a team leading at save time resumed with damped settings and no base, and autoset promoted the damping to its plan permanently. | ⏳ **Re-measure user-game margins on a NEW season.** The §1.5 figures come from games played under the old code and CANNOT be re-derived from existing data — there is no valid before/after against the finished season and no proxy for one. Watch second-half margin compression and whether the 33-0 win total holds. RNG anchors in `reports/perf/` are invalidated by construction (damping a second team adds draws) — compare distributions, not byte-diffs. |
| **PR1** | Upstream fix *if* the gate says so — H1 (off/def balance) and/or H3 (`discipline` drift neutering the existing balancing trigger). Re-baseline. | New margin distribution published |
| **PR2** | `game_governor.py` + `constants/governor.py` + `_refresh_governor_state`. **Telemetry only** — computes and logs `G`, changes nothing. | G6 passes trivially (byte-identical everywhere) |
| **PR3** | L1 tempo, L2 fast breaks, L3 press/trap (leading team only) | G6, G7 pass; margin p99 moves |
| **PR4** | L4 progressive substitution + dirty-flag cadence + `fill_unified_lineup_gaps` fix; retire systems 1 & 2 | G1–G7 |
| **PR5** | L5 shot-threshold delta; retire `apply_balancing_system`; fix the ownership leak | G1–G7; expect the largest single shift here, and the largest re-tune |
| **PR6** | §6 trailing team + give-up; retire the `-18` magic number | G1–G7 with both sides live |
| **PR7** | Fit `SAFE_LEAD_A/B`, `GOV_*` thresholds, `GOV_SHOT_THRESHOLD_MAX_DELTA` against measured data; update `Tunable_Constants.md`, `Computer_Team_GamePlan_System.md`, `CPU_Team_Rotation_System.md`, `Shot_System.md`; write `Blowout_Governor_System.md` | All gates; docs match code |

Doc debt to clear in PR7: `Shot_System.md` documents the balancing values as −20/180 in **three** places — `:83-84`, `:238`, and `:342`; the code says −30/170. Stale since the scale rescale. Also `shot_threshold_scale.py:27` claims init "95-105" in a comment while `:29-30` sets 85/95 — reconcile.

---

## 10. Open questions

1. **A2 confirmation** — in Play Quarter, should the governor touch the *user's* possession-level outcomes (L5) at all, or only the CPU's? Cleanest answer is "both teams, since it is a physics-of-the-game layer," but it is your call and it changes G6's sample definition.
2. **Should `G` see team quality?** A 30-point lead by a top-5 team over a bottom-100 team is more "earned" than the same lead between equals. The governor could engage later when the quality gap is large. Recommendation: **no** — quality already earned the lead; damping possessions is the neutral response, and coupling `G` to a quality metric makes G4 much harder to reason about. Flagging it because it is the most defensible objection to this design.
3. **Energy knock-on.** Resting starters in blowouts feeds `energy_system.py` and makes the dominant team *fresher* for the next game. The governor therefore has a small compounding upside for the leading team across a season. Accept for now, or budget a follow-up?
4. **Conservative-strategy removal** — system 2 is stochastic and CPU-only; removing it is the right call architecturally but it is currently the only thing that damps a CPU team's aggression at a 20-point lead in Q1/Q2. PR3 must land before PR4 removes it, or there is a window with no early-game damping at all.
5. **Target margin curve.** What *should* a top-1 team beat a bottom-128 team by, in this game's economy? G1/G2 above are my numbers, not yours. If your answer is "35 and it should feel like a beating," the constants move.

---

## Appendix — file-by-file change list

| File | Change |
|---|---|
| `BackEnd/constants/governor.py` | **new** — all `GOV_*`, `SAFE_LEAD_*`, `SEC_PER_POSSESSION` |
| `BackEnd/utils/game_governor.py` | **new** — `seconds_remaining_in_game`, `safe_lead`, `governor_pressure`, `governor_setting`, `governor_tempo`, `bench_depth_for`, `shot_threshold_delta` |
| `BackEnd/utils/situational_logic.py:174` | rename `slow_it_down_defense_setting` → `effective_defense_setting`; chain governor after the SID check (L2) |
| `BackEnd/utils/situational_logic.py:306` | replace `delta < -18` with the §6.2 give-up condition |
| `BackEnd/models/turn_manager.py:3387` | add `_refresh_governor_state()` beside `_refresh_situational_team_state()`; call from **both** `:3419` and `:6540` |
| `BackEnd/models/turn_manager.py:3487` | governor tempo tier (L1) |
| `BackEnd/models/turn_manager.py:6600` | governor press/trap tier (L3) |
| `BackEnd/models/turn_manager.py:2918`, `:3199` | optional Tier-2 set/focus bias — measure before adding |
| `BackEnd/utils/db_utils.py:568` | `prefer_lowest_rt: bool` → `bench_depth: int` + `deep_bench: bool` (L4a) |
| `BackEnd/utils/db_utils.py:631` | thread both into `fill_unified_lineup_gaps` (L4c) |
| `BackEnd/utils/db_utils.py:288-342` | delete `BLOWOUT_*` (all six constants, 288-293) + `_blowout_lineup_active`; move `_team_score_margin` to the governor module |
| `BackEnd/utils/db_utils.py:984-1020` | delete conservative-strategy override (PR4, after PR3) |
| `BackEnd/main.py` (turn loop) | honour `governor_lineup_dirty` at dead balls (L4b) |
| `BackEnd/engine/phase_resolution.py:3571`, `:7506` | delete `apply_balancing_system` and its sole call |
| `BackEnd/models/shot_manager.py:868-876` | remove the override branch; apply the additive governor delta in the base branch (L5) |
| `BackEnd/tests/test_game_governor.py` | **new** — §8 test coverage |
| `scripts/sim_verify/margins.py` | **new** — margin distribution by quality-gap bucket |
| docs | `Blowout_Governor_System.md` **new**; update `Computer_Team_GamePlan_System.md`, `CPU_Team_Rotation_System.md`, `Shot_System.md`, `Tunable_Constants.md`, `Situational_Logic_System.md` |
