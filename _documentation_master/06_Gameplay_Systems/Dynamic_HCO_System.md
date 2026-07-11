## Dynamic HCO System ✅ **SHIPPING (flagged)** (June 2026)

**Feature gates (independent):**
- `GOB_DYNAMIC_HCO_MOTION` (`1`/`true`/`yes`/`on`) — motion plays
- `GOB_DYNAMIC_HCO_SETPLAY` — set plays (overlay on the variant skeleton; see **§ Set plays**)
- `GOB_DYNAMIC_HCO_DEFENSE` — **ON by default**; per-turn defender posture placement + (planned) two-gate intercept. In development — see **§ Dynamic Defense**.

Off → legacy HCO path (up-front outcome tables + static skeleton). This doc describes the ON path for **both**.

**Scope:** half-court **offense — motion plays and set plays, man + zone defense**. Set plays **reuse motion's machinery**; only the deltas in **§ Set plays** are new. Archived build briefs: [Dynamic_HCO_Motion_Brief.md](../projects/Z-Completed/Dynamic_HCO_Motion_Brief.md), [Dynamic_HCO_SP_Brief.md](../projects/Z-Completed/Dynamic_HCO_SP_Brief.md). This file is authoritative for runtime.

---

## Tunable Constants

Shot-timing dials, all in [`BackEnd/engine/motion_step_decision.py`](../../BackEnd/engine/motion_step_decision.py) and wired by `_resolve_motion_offense_shot_dynamic` in `phase_resolution.py`. These govern *when* within a motion turn the ball handler shoots, dishes, or works the ball.

### Shot-clock tiers (`_shot_clock_tier`)
Shared by the random-% grid and the SM-precedence grid.

| Tier | Shot clock |
|---|---|
| Early | ≥ 23s |
| Mid | 15–22s |
| Late | 6–14s |
| Very late | 1–5s |
| Forced | < 1s (forced shot, handled upstream) |

### Optimal-look bar (`_shoot_threshold`)
A look's 0–100 mismatch quality must clear the bar to be **optimal**. Continuous:
`bar = clock × OPTIMAL_BAR_STEEPNESS × OPTIMAL_BAR_TEMPO_MULT[tempo]`
- `OPTIMAL_BAR_STEEPNESS = 2.0` — self-shot and hot-read dish share it.
- `OPTIMAL_BAR_TEMPO_MULT = {slow: 1.2, normal: 1.0, fast: 0.8}`

Higher bar = fewer/later shots; slow tempo demands a better look (work the ball), fast shoots sooner. Self stays slightly favored over the dish via the self-only openness bonus + self-wins-ties tiebreaker (not the bar). Illustrative values (normal tempo): 30s → 60, 22s → 44, 15s → 30, 8s → 16.

### Random-tier shoot % (`RANDOM_TIER_SHOOT_PCT`)
Non-strategic ("random") read tier: `randint(1,100) ≤ %` → shoot (self only). Low early, high late.

| Tier | slow | normal | fast |
|---|---|---|---|
| Early | 30 | 40 | 50 |
| Mid | 45 | 60 | 75 |
| Late | 95 | 95 | 95 |
| Very late | 95 | 95 | 95 |

### Subtle-movement precedence (`SM_PRECEDENCE_TEMPOS`)
When the turn's `offense_reads` (alterations) roll is on, these tempos make **subtle movement take precedence over the shoot decision** — the BH works the ball and defers his shot/hot-read. Reuses the per-turn alterations roll (NOT a second roll). Precedence retreats as the clock drains and tempo speeds up.

| Tier | slow | normal | fast |
|---|---|---|---|
| Early | ✓ | ✓ | ✓ |
| Mid | ✓ | ✓ | ✗ |
| Late | ✓ | ✗ | ✗ |
| Very late | ✗ | ✗ | ✗ |

### Read tiers (`_shoot_read_tier`)
`(player_read_raw + discipline) × d6`: `> SHOOT_READ_RIGHT (300)` → right (take the best optimal look, self or dish); `> SHOOT_READ_SAFE (100)` → safe (always progress); else random (use the % grid above). SM-precedence is evaluated **before** this — when it fires, the read tier is bypassed for that step.

---

### Overview

Legacy HCO predetermined a motion turn's outcome up front (flat percentile tables for foul / steal / turnover, checked before the skeleton renders). Dynamic HCO replaces that with **per-step resolution**: the offense walks its motion skeleton making attribute-driven reads (move / shoot / pass) while the defense contests **each step** (steal / foul / turnover), exactly mirroring how HCT (half-court trap) and FCP (full-court press) already resolve. Nothing is predetermined; everything is reproducible from attributes + seeded RNG (SS&S), and the **FE is a pure renderer** — all logic is backend-side, all motion is emitted as normal UESS skeleton steps + flourishes (no FE decisions, no coord mutation on the client).

**Three subsystems, in execution order on a motion turn:**
1. **Turn gate** — two independent rolls decide whether the offense makes reads and whether the defense pressures this turn.
2. **Per-step Moment** — the defender contests the ball each step; a hard outcome (steal/foul/turnover) pre-empts the shot. Migrated from HCT's D8 model.
3. **Per-step offense walk** — subtle movement beats, defender freeze reaction, and the Universal Shoot Decision (`should_shoot`) that decides when/what to shoot.

---

### Where it hooks in

`resolve_half_court_offense_logic` (BackEnd/engine/phase_resolution.py):

```
resolve_hco_outcome(game, skeleton)            # motion+flag ON → skips up-front event tables (skip_upfront_events)
  ↓ result == "SHOT"
_resolve_hco_moment_walk(...)                  # per-step contest; hard outcome → overrides result
  ↓ (collects reach_in_tags for non-terminal contests — option B)
skeleton = deepcopy(skeleton)                  # cached skeleton never mutated
final_skeleton = skeleton                      # motion branch; reach_in_tags applied HERE (post-deepcopy)
  ↓
result == "SHOT":  resolve_motion_offense_shot → _resolve_motion_offense_shot_dynamic   # the offense walk
result != "SHOT":  existing non-shot resolution + apply_stopper_system_to_skeleton      # steal/foul/turnover
  ↓
skeleton_step_emitter.build_skeleton_animation_steps(...)   # UESS render: steps, SFX, reach_in flourishes
```

The dynamic resolver appends the **base step dicts verbatim** (`output_steps.append(steps[i])`), so custom step keys (`_subtle_movement`, `_hot_read_sfx`, `reach_in_def_id`) survive untouched into the emitted skeleton.

---

### 1. Turn gate

Two decoupled per-turn rolls in `_resolve_motion_offense_shot_dynamic`:

| Roll | Formula | Effect |
|---|---|---|
| `offense_reads` | `randint(0,4) <= alterations` | offense executes reads (subtle movement / hot reads) this turn |
| `defense_pressure` | `randint(0,4) <= aggression` | defense applies step pressure (feeds the freeze reaction) |

`alterations` and `aggression` are integer `strategy_settings` sliders (0–4). Neither true → the turn walks straight to a shot with no reads/pressure. **The per-step Moment has its OWN, separate engagement roll** inside `_resolve_hco_moment_walk` — a percentage curve (`MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION`, see §2), *not* this flat `randint(0,4) <= aggression`. So aggression gates the freeze-reaction pressure (here) and the moment frequency (there) independently.

---

### 2. Per-step Moment (foul / steal / turnover)

`_resolve_hco_moment_walk(skeleton, game, off_lineup, def_lineup, reach_in_tags)` — runs **before** shot resolution:

1. **Engagement:** per-turn, by defense aggression → % of possessions with any contest (`MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION` = `{0:5, 1:20, 2:35, 3:50, 4:75}`), else None (no moment this turn). Same gate for man and zone.
2. **Walk steps 1..n:** for each, resolve the on-ball defender — **man:** the ball-handler's matchup defender (`off_to_def[bh_pos]`); **zone:** the defender whose zone polygon covers the BH's spot (`_zone_bh_defender` → `_zone_boundaries_for_spot` + `_defender_for_zone_point`, nearest-zone centroid fallback, then position-on-position). Fire `_resolve_hco_moment` → `_resolve_moment` (shared HCT D8 contest in dynamic_hct.py), scaled by `HCO_MOMENT_SCALAR` (man) or `HCO_ZONE_MOMENT_SCALAR` (zone).
3. **First hard outcome wins:** `STEAL` / `DEAD_BALL_TURNOVER` / `O_FOUL` / `D_FOUL` → returned; the caller sets `result`, and the **existing** non-shot resolution + `apply_stopper_system_to_skeleton` route/render it (no new emission path). `NEUTRAL` (defender won, no event) / `POS_O` (offense beat defender) → continue.
4. **Credited defender stash:** on a hard outcome the walk stashes the contesting defender's id in `game_state["_hco_moment_defender_id"]`; the non-shot block consumes it so the steal credit (`stealer_id`) + terminal reach-in land on the **actual** defender (critical for zone, where the position-on-position fallback would pick the wrong one). Man path: the stash equals the matchup defender, so behavior is unchanged.

The contest math (steal vs dead-ball vs charge weighting, defender-vs-BH attribute gaps, team modifiers) lives in `_resolve_moment` and is shared with HCT — see [HCT_System.md](HCT_System.md). HCO scales the whole event probability by `HCO_MOMENT_SCALAR` (HCT/FCP pass the default 1.0, so they are mathematically unchanged).

#### Reach-in micro-movement (the "pressure moment" visual — option B)

HCO has a single on-ball defender, so it does **not** use FCP/HCT's multi-defender *converge*. Instead the on-ball defender lunges at the ball via the render-space **`reach_in` flourish** (`flourishes.js` → `runReachIn` + `playStealReachInSfx` / `click-steal.wav`). It fires on **every contested step of an engaged turn** (option B — so the coach sees an aggressive defense constantly poking, successes and whiffs alike):

| Case | Tag source | Step |
|---|---|---|
| Terminal (`STEAL`/`DEAD_BALL_TURNOVER`/`D_FOUL`) | non-shot block sets `reach_in_def_id` on the **stopper step** | the stop |
| Non-terminal (`NEUTRAL`/`POS_O`) | walk appends `(step_index, defender_id)` to `reach_in_tags`; caller applies to `final_skeleton` **post-deepcopy** | each contested step |

`O_FOUL` (offensive charge) is excluded. `skeleton_step_emitter` turns any `reach_in_def_id` on a step into `step.start.flourish[id] = {kind:"reach_in", target:"ball"}`. **Pure render-space — never mutates gameplay coords (UESS-safe).** Non-engaged turns show no reach-ins, so reach-in *presence* reads as defensive aggression.

---

### 3. Per-step offense walk

`_resolve_motion_offense_shot_dynamic` walks the skeleton accumulating an output step stream (base steps woven with inserted subtle-movement beats). Per step it calls `decide_step_action` (motion_step_decision.py):

- **SUBTLE_MOVEMENT** — insert a `build_subtle_beat` (motion_subtle.py): the BH nudges off-pattern; each non-BH teammate makes his own read (`(player_read_raw + off_eff) * d6 > MOTION_READ_THRESHOLD`) to relocate or hold; the next skeleton step pulls everyone back ("pop back"). Movers render at the `cruise` archetype.
- **Defender freeze reaction** — per-defender read (`_roll_subtle_defender_reads`); a defender whose man moved but whose read FAILED freezes instead of following (`_subtle_defender_should_freeze`, applied geometrically in the animator).
- **Universal Shoot Decision** (`should_shoot`) — see below.
- **SHOOT / KICKOUT_SHOOT / HOT_READ_SHOOT** terminate and append shot steps via `_execute_motion_decision`. If no shot fires by the last step, force one (with a `SUBTLE_FORCED_SHOT_PENALTY` if the clock forced it).

#### Universal Shoot Decision (`should_shoot`)
Two-stage: **(1) is this an optimal look?** — shot-type mismatch score from the read map + openness vs the `_shoot_threshold` bar (`SHOOT_THRESHOLD_BASE` lowered by clock drain + tempo). **(2) read tier** — `(player_read_raw + discipline) × d6`: `> SHOOT_READ_RIGHT` shoot if optimal else progress; `> SHOOT_READ_SAFE` progress; else non-strategic ("random"). Shot type (attack vs outside) is a team-biased weighted pick (`_weighted_attack_or_outside`).

##### Random-tier shoot progression
The non-strategic ("random") tier no longer shoots a flat 50/50 each step — it rolls `randint(1,100) ≤ _random_tier_shoot_pct(shot_clock, tempo)`, a clock+tempo progression (low early, high late) that stops undisciplined possessions from dumping early shots. Buckets (`RANDOM_TIER_SHOOT_PCT` in `motion_step_decision.py`):

| Shot-clock bucket | slow | normal | fast |
|---|---|---|---|
| Early (23–30s) | 30% | 40% | 50% |
| Mid (15–22s) | 45% | 60% | 75% |
| Late (6–14s) | 95% | 95% | 95% |
| Very late (1–3s) | 95% | 95% | 95% |
| Forced (<1s) | 100% (existing `<1s` forced-shot backstop) |

Very-late is flat 95% for all tempos (clock pressure dominates). The "right" and "safe" tiers are unchanged.

---

### Dynamic Defense 🚧 **IN DEVELOPMENT** (ON by default, July 2026)

**Gate:** `GOB_DYNAMIC_HCO_DEFENSE` (independent; **default ON**, kill switch = falsy). Off → legacy glued-to-man defender placement. Design/working doc: [Dynamic_MM_Brief.md](../projects/Dynamic_MM_Brief.md). Phased build (P1–P7); this section documents what is **live**.

**Goal:** make HCO defenders dynamic instead of pinned to their man — a per-turn team **posture** shifts placement, and (planned) an interception model reads pass lanes. Legacy steal/turnover mechanics (per-step moment + hot-read/kickout pass contest) are **unchanged** and run alongside.

#### Live now — P1: posture placement (man defense)

Each HCO turn rolls a team-wide **posture** (`_roll_defense_posture`, phase_resolution.py) — interim `random(loose/normal/tight)`; later the chosen tight/loose **playcall variant** (P6). It is stashed on `game_state["_hco_defense_posture"]`; the animator (`_position_standard_defenders`) reads it and passes it to `get_defender_coords`, which shades the baseline man position (`_apply_defender_posture`, shared_defense.py). **Purely positional** — no new steals yet.

| Posture | On-ball (BH) defender | Off-ball defender |
|---|---|---|
| **tight** | 1 grid tighter (toward the man) | **deny** — hugs the man on the ball side, in his passing lane (`POSTURE_DENY_DISTANCE` off the man) |
| **normal** | baseline (`get_spacing`) | baseline man position |
| **loose** | 2 grid more cushion (sag) | **help** — sags toward mid-floor (fraction `POSTURE_HELP_SHADE` toward the ball→basket line) |

- **Inside-man lock:** a defender guarding an **inside** man (lowPost/midPost/midLane/basketSpot) always plays **normal** post D, regardless of posture.
- **Scope:** **man defense render only** (zone placement not yet shaded). Read-side / offense reaction not wired.
- **Orientation-safe:** posture shade runs in the caller's orientation (verified home + away); `posture=None`/`"normal"` is a strict no-op, so every non-HCO caller (fast break, HCT, quarter-start, attack-drives) is untouched. Coords flow through the shared reconstruction (render + future read agree — emitter-as-god façade).

#### Tunable Constants (P1)

| Constant | File | Default | Effect |
|---|---|---|---|
| `POSTURE_ONBALL_CUSHION_DELTA` | shared_defense.py | `{tight:-1, loose:+2}` | On-ball cushion shift along man→basket (+ = more cushion/sag). |
| `POSTURE_DENY_DISTANCE` | shared_defense.py | `2.0` | Off-ball tight: grid off the man, ball-side (in his passing lane). |
| `POSTURE_HELP_ANCHOR_FRAC` | shared_defense.py | `0.5` | Help anchor = this far along the ball→basket line (mid-floor). |
| `POSTURE_HELP_SHADE` | shared_defense.py | `{loose:0.55}` | Off-ball loose: fraction from baseline toward the help anchor. |
| `_HCO_DEFENSE_POSTURES` | phase_resolution.py | `(loose,normal,tight)` | Interim random posture pool (→ playcall variants in P6). |

#### Roadmap (planned)

| Phase | Item |
|---|---|
| **P2** | Two-gate intercept — Gate 1 geometry (defender in a pass lane, reusing the posture-shaded reconstruction) → Gate 2 `aggression_call` (aggressive 80 / normal 40 / passive 0) → Gate 3 `resolve_pass_contest`. Posture gates *viability by distance*: tight can jump his man's pass, loose can't (only help lanes). **Interceptable passes (all types):** hot-read dishes + kickouts (P2a), **freelance passes**, and **skeleton motion/reversal passes** (P2b — walk hook `_hco_contest_skeleton_pass`, both walks). All reuse `_hco_resolve_dish_contest`; an intercept → STEAL via `pass_intercepted`. Loose/help defenders pick swing passes in help lanes. |
| **P3** | Reactive resolution + graded openness (generalize the SM freeze to every step type). |
| **P4–P5** | Offense reads the commitment → `attack` / relocate / step-in / new `backdoor`; dish-receiver agency on the catch. |
| **P6** | Real tight/loose **playcall variants** replace the interim random pick. |
| **P7** | Zone-defense posture parity; tuning; tests. |

---

### Set plays (overlay)

**Gate:** `GOB_DYNAMIC_HCO_SETPLAY` (independent of motion). Off → legacy set-play path (up-front outcome tables + static variant skeleton).

#### Model: OVERLAY

The up-front **variant roll** (`successful` / `mid_play_change` / `contested` / `broken`) **still** selects the skeleton. The dynamic per-step layer overlays on the chosen variant skeleton. `get_hco_skeleton` runs `_apply_set_play_runtime_position_mapping`, so the variant skeleton arrives **position-keyed** (PG/SG/…) just like motion's `base_loop` — the motion helpers walk it directly, no slot mapping.

**Scope:** half-court offense, set plays, **man + zone** defense.

#### Where it hooks in

```
resolve_hco_outcome(game, skeleton)              # set_play + flag → skips up-front event tables; variant STILL chosen
  ↓ result == "SHOT"
final_skeleton = get_hco_skeleton(variant)       # executed variant skeleton, then deepcopy
_resolve_hco_moment_walk(final_skeleton, …)      # per-step steal/foul/TO (man+zone); hard outcome → overrides result
  ↓ result still "SHOT"
_resolve_setplay_offense_shot_dynamic(…)         # per-step offense walk (shared motion block routing)
  ↓ result != "SHOT": existing non-shot resolution + apply_stopper_system_to_skeleton
skeleton_step_emitter.build_skeleton_animation_steps(…)
```

The moment walk runs **after** the variant skeleton is chosen + deep-copied (so it reads the actual play and reach-in indices align) and **before** the shot-clock block (so a hard outcome correctly pre-empts the would-be shot). Routing reuses the motion roles-update block: the set-play result has the same contract (`roles["shooter"/"motion_shot_type"/"motion_playcall"]` + passer re-derivation + dish-interception finalize).

#### The three differences from motion

| | Motion | Set play |
|---|---|---|
| **offense_reads** | rolled per turn from `alterations` | **forced `False`** — offense never proactively subtle-moves; only the defense can force one |
| **post-forced-subtle** | resume skeleton silently | BH reads shoot / hot-read pass / **hold** → `_setplay_recovery_roll` |
| **events** | per-step moment (§2) | same per-step moment, replacing the set-play up-front tables |

With `offense_reads=False`, `decide_step_action` only acts under defense pressure (Condition 3, ball-handling battle): defense wins → `_disruption_branch` (subtle / freelance / advance); else advance. The **universal `should_shoot`** hot read still runs every step (not only after a subtle).

**Forced-subtle progression:** defense forces a subtle → `build_subtle_beat` (BH + non-BH reads) → shot-clock-expiry backstop → post-subtle `should_shoot` (shoot **or** hot-read dish). If no shot, the BH holds and rolls recovery:

```
offense_score = (team_chemistry + offensive_efficiency) × randint(1,6)   # offense team
defense_score = (team_chemistry + defensive_efficiency) × randint(1,6)   # defense team
offense_score > defense_score → re-enter skeleton at next defined step (players pop back to spots)
                         else → forced freelance (_resolve_freelance)
```

A direct `FREELANCE_FORCED` from the disruption branch (no subtle) goes straight to freelance.

#### Reused from motion (no rebuild)

`should_shoot` + truly-open gate (`_hco_blocked_dish_targets`) + dish interception · `decide_step_action`/`_disruption_branch` · `build_subtle_beat` · `_execute_motion_decision` · `_resolve_freelance` · `_resolve_hco_moment_walk` (man + zone). New code is only `_resolve_setplay_offense_shot_dynamic`, `_setplay_recovery_roll`, the flag gate, and the routing branches.

#### Set-play tests + prototype

- `tests/test_setplay_dynamic_gate.py` — flag gate + recovery-roll formula
- `tests/test_setplay_dynamic_resolver.py` — walk: offense_reads forced False, universal hot read, forced-subtle → re-enter vs freelance, FREELANCE_FORCED, shot-clock backstop
- `dynamic_setplay_prototype.py` — seeded Monte-Carlo recovery-roll grid + walk path distribution. Run: `MONGO_URI="" MONGO_DB_NAME="gob-test" python3 dynamic_setplay_prototype.py`
- Unit tests: `MONGO_URI="" MONGO_DB_NAME="gob-test" python3 -m pytest tests/test_setplay_dynamic_*.py -q -o addopts=""`

---

### 4. Passing lanes & hot-read openness (SPEC — building)

A defender sitting in a passing lane can disrupt an HCO **hot-read dish or kickout** (skeleton motion/reversal passes are NOT contested). Reuses the shared HCT pass model `resolve_pass_contest` (spatial lane gate → skill/anticipation → `complete` / `BAT_OOB` / `INTERCEPT`). **Hybrid** design:

- **Decision gate ("truly open"):** when `should_shoot` evaluates a teammate as a hot-read **dish** target, that teammate is only "open" if the BH→teammate lane is clear — no eligible defender within the perpendicular lane distance. A covered lane removes him from the dish candidates (the offense won't force it).
- **Contest (interception):** when a dish/kickout **is** thrown, run `resolve_pass_contest`; `INTERCEPT`/`BAT_OOB` converts the would-be shot into a turnover, routed through the existing non-shot resolution + stopper system (same path as the per-step Moment). `complete` → the shot resolves as today. `INTERCEPT` → STEAL via `_finalize_hco_pass_interception`; `BAT_OOB` → offense retains (side inbound, no stats) via `_finalize_hco_pass_bat_oob`.
- **Result-payload gotcha (serialization):** an HCO non-shot finalize must **not** return the raw motion `roles` — its `action_timeline` / `touch_counts` are keyed by **Player objects**, and `JSONResponse` rejects non-str dict keys (`convert_players` coerces values, not keys). Strip both before returning (every HCO *shot* path already does). A key-coercion safety net in `convert_players` backstops any that slip through. (Fixed: BAT_OOB was returning raw roles → `TypeError: keys must be str… not Player`.)

**Defender coords at decision time** (the skeleton carries no defender positions) are reconstructed from the offensive coords — the same math the animator renders with, so the contest matches the picture: **man** → `get_defender_coords(off_coords, is_away_offense, aggression_call, spot, …)` per matchup; **zone** → `assign_all_zone_defenders(zone_boundaries, offensive_players, bh_coords, ball_spot, aggression, is_away_offense)`.

**Lane distance** (perpendicular, passed as a param to `resolve_pass_contest` so HCT's `8.0` is untouched):

| Turn / defense | Lane dist | Source |
|---|---|---|
| HCO, defense passive | `6.0` | `HCO_PASS_LANE_DIST_BY_AGGRESSION` |
| HCO, defense normal | `randint(5,6)` **once per game** | rolled + cached in `game_state` |
| HCO, defense aggressive | `5.0` | `HCO_PASS_LANE_DIST_BY_AGGRESSION` |
| HCT | `8.0` | `PASS_LANE_DIST` (unchanged) |
| FCP | `8.0` | `FCP_PASS_LANE_DIST` (new — see Roadmap) |

Tighter HCO lanes (5–6 vs 8) reflect closer spacing + faster half-court passes. The normal-tempo roll is taken once and cached for the whole game (no per-pass roll).

**Build stages:** (1) decision gate — reconstruct def coords, exclude covered-lane dish targets in `should_shoot`; (2) interception contest on thrown dish/kickout → turnover routing; (3) FCP @ 8 (needs a pass-beat audit — FCP's inbound/press-break/advance passes have no contest today).

**Calibration diagnostic** (`_track_hco_pass_lanes`, called from `turn_manager.resolve_half_court_offense`, behind the flag): for every pass step in a resolved HCO turn it logs the closest non-BH defender's perpendicular distance to the pass lane in two bands — **mid-lane help** (t 0.1–0.9, the gate band) and **full-eligible** (t 0.1–1.0, the contest band incl. the receiver's man) — and accumulates game totals in `game_state`, logging the running average each turn (`📏 [HCO PASS LANES] … GAME: passes=N mid_avg=… full_avg=…`). The last HCO turn's line is the game summary. Use it to judge whether `HCO_PASS_LANE_DIST_*` (5–6) is too high/low. Pure observability — wrapped so it can never break a turn.

---

### Tunable Constants

Per agents.md best-practice #3, every knob is a named constant. To retune frequency/feel, change these and re-run — no logic edits.

#### Moment frequency (steal / foul / turnover)
| Constant | File | Default | Effect |
|---|---|---|---|
| `HCO_MOMENT_SCALAR` | phase_resolution.py | `0.5` | **HCO man-defense** dial; multiplies the whole per-moment event probability. ↑ = more steals/fouls/TOs vs man. HCT/FCP unaffected. |
| `HCO_ZONE_MOMENT_SCALAR` | phase_resolution.py | `0.5` | **HCO zone-defense** dial (defaults equal to man). Tune zone independently — zones strip less, deflect/help more. |
| `MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION` | phase_resolution.py | `{0:5, 1:20, 2:35, 3:50, 4:75}` | Per-turn % of possessions the defense attempts **any** moment, by aggression (man + zone). The frequency knob *before* conversion. ↓ = fewer possessions with a steal/foul/TO at every aggression level. |
| `HCO_PASS_LANE_DIST_BY_AGGRESSION` | phase_resolution.py | `{passive:6.0, aggressive:5.0}` (normal = `randint(5,6)`/game) | Perpendicular lane distance for HCO hot-read/kickout pass disruption. ↑ = defenders contest from farther = more interceptions. Tighter than HCT/FCP (8.0). |
| `INTERCEPT_ATTEMPT_PCT_BY_CALL` | phase_resolution.py | `{aggressive:80, normal:40, passive:0}` | **Gate 2** — % chance an in-lane defender (Gate 1) actually *attempts* the pick, by `aggression_call`. The volume throttle *before* the Gate 3 attribute contest. ↑ = more attempts feed the contest = more interceptions. Passive never gambles. |
| `PASS_LANE_DIST` | pass_contest.py | `8.0` | HCT lane distance (and the param default). Shared pure model. |
| `FCP_PASS_LANE_DIST` | *(planned)* | `8.0` | FCP lane distance once FCP pass contests are wired (Roadmap). |
| `HCT_D8_GLOBAL_SCALAR` | dynamic_hct.py | `1.0` | Global per-moment frequency (affects HCT/FCP/HCO). |
| `HCT_D8_DEF_WIN_BASE` | dynamic_hct.py | `0.25` | Base P(any event) when defense fully wins the contest. |
| `HCT_D8_P_EVENT_MAX` | dynamic_hct.py | `0.60` | Cap on per-moment event probability. |
| `HCT_D8_AGG_MULT` | dynamic_hct.py | `{passive:0.7, normal:1.0, aggressive:1.3}` | Aggression multiplier on event prob (uses `aggression_call` string). |
| `HCT_D8_DFOUL_BASE` | dynamic_hct.py | `0.25` | Base P(D_FOUL) on a decisive blow-by (no separate cap). |
| `HCT_D8_S_SENS` / `HCT_D8_DB_SENS` / `HCT_D8_O_SENS_IQ` | dynamic_hct.py | `1.2` / `1.0` / `0.8` | Steal / dead-ball / charge sensitivity to attribute gaps. |
| `HCT_D8_W_PTEFF` / `W_PTOPP` / `W_FIGHT` / `W_DISC_REACH` | dynamic_hct.py | `0.04` each | Team-modifier weights (pt_efficiency, pt_opp, fight, discipline). |

> **Two-factor steal rate:** effective rate ≈ *engagement %* (`MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION`) × *conversion* (`HCO_*_MOMENT_SCALAR` × D8 × `HCT_D8_AGG_MULT`). Aggression raises both. To thin steals globally, lower the engagement %; to thin them on one defense type, lower that type's scalar.

#### Subtle movement
| Constant | File | Default | Effect |
|---|---|---|---|
| `MOTION_READ_THRESHOLD` | motion_step_decision.py | `110` | Per-teammate read bar `(player_read_raw + off_eff) × d6` to relocate on a subtle beat. ↑ = fewer teammates move. Also the defender-follow bar. |
| `SUBTLE_STEP_ELAPSED_BY_TEMPO` | motion_step_decision.py | `{slow:(2,4), normal:(2,3), fast:(1,3)}` | Steps elapsed before a subtle beat can pause (tempo floors). |
| `SUBTLE_FORCED_SHOT_PENALTY` | motion_step_decision.py | `50` | Shot-score penalty when the clock forces a shot off a subtle hold. |
| `SUBTLE_ARCHETYPE` | motion_subtle.py | `"cruise"` | Movement speed archetype for subtle movers + BH dribble. |
| `BH_SUBTLE_MOVES` | motion_subtle.py | `("in_place","back","in")` | BH radial move menu (+`"side"` when at a perimeter spot with a free neighbor). |
| `_X_MIN/_X_MAX`, `_Y_MIN/_Y_MAX` | motion_subtle.py | `2/98`, `2/48` | Off-pattern coord clamps (display space). |

#### Shoot decision
| Constant | File | Default | Effect |
|---|---|---|---|
| `SHOOT_THRESHOLD_BASE` | motion_step_decision.py | `30` | "Optimal look" bar at full clock, normal tempo (mismatch-score scale). |
| `SHOOT_TEMPO_ADJ` | motion_step_decision.py | `{slow:-8, normal:0, fast:8}` | Fast lowers the bar (shoot sooner). |
| `SHOOT_READ_RIGHT` / `SHOOT_READ_SAFE` | motion_step_decision.py | `200` / `125` | Read tiers: right = optimal decision, safe = progress. |
| `READ_THRESHOLD` | motion_read_map.py | `15` | Mismatch score above which a shot-type read is an "edge". |
| `TEMPO_MOD` | motion_step_decision.py | `{slow:-25, normal:0, fast:25}` | Tempo shift on the desperation offense-score pre-check. |
| `KICKOUT_MAX_DIST` | motion_step_decision.py | `10` | Grid distance for the 25% desperation kick-out. |

---

### Stats, SFX & UESS

- **Steal SFX:** the `reach_in` flourish fires `click-steal.wav` (`playStealReachInSfx`) FE-side on render. See [SFX_System.md](../11_Design_Systems/SFX_System.md). (Hot-read VO is currently disabled — `HOT_READ_VO_ENABLED = False`.)
- **Stopper:** terminal outcomes route through `apply_stopper_system_to_skeleton` (shared with FCP) — see [Stopper_System.md](Stopper_System.md).
- **UESS:** every beat is a coord-based skeleton step; the emitter (`skeleton_step_emitter.build_skeleton_animation_steps`) stamps all required fields. Flourishes are render-space only. See [05_UESS_System](../05_UESS_System/).

---

### Deferred / Roadmap

| Item | Status / notes |
|---|---|
| **Zone-defense moments** | ✅ Shipped (June 2026). On-ball defender resolved by zone polygon (`_zone_bh_defender`); `HCO_ZONE_MOMENT_SCALAR` dial; contest uses the **same D8 weights** as man for v1 (reweighting toward deflections/help is a future tuning pass). |
| **Zone contest reweighting** | Deferred — v1 reuses man's D8 steal/dead-ball/charge weights. Zones realistically strip less and force more deflections/help; revisit `HCT_D8_*` weights (or a zone-specific set) + `HCO_ZONE_MOMENT_SCALAR` after live observation. |
| **Passing lanes & hot-read openness** | ✅ Shipped — needs prototype tuning (see §4). Decision gate ("truly open") + interception contest, **man + zone**, hot-read/kickout dishes only. Gate clears the 0.1–0.9 lane band, so the contest's net-new interceptions are the **receiver's man jumping the entry pass** (t→1.0), gated by passer skill — frequency tunable via `HCO_PASS_LANE_DIST_*` / `PASS_SAFETY_BASE`. Intercept → STEAL (`is_interception`) via `_finalize_hco_pass_interception` (resolve_turnover_logic + stopper). |
| **FCP pass contests @ 8** | 🔨 Planned (§4 stage 3). FCP has **no** pass-disruption today — needs a pass-beat audit (inbound / press-break / advance) before wiring `resolve_pass_contest` with `FCP_PASS_LANE_DIST = 8.0`. (NB: interceptions seen on "FCP" today are the post-steal **rim-runner fast break** mechanic, labeled `FAST_BREAK`, not FCP.) |
| **Set-play overlay** | ✅ Shipped — `GOB_DYNAMIC_HCO_SETPLAY`; variant skeleton + motion helpers; recovery roll after forced subtle (see **§ Set plays**). |
| **True per-step shoot↔moment interleaving** | The moment walk currently runs fully **before** the shot resolver, so a moment pre-empts the would-be shot. True interleaving needs the late shot resolver (after shot-clock truncation). |
| **Pass interceptions** | HCT's `pass_contest` not yet ported to HCO. |
| **Reach-in option A** | We ship **B** (every contested step). A (defender-wins-only: terminal + `NEUTRAL`, skip `POS_O` blow-bys) is the documented alternative if B reads too busy. |

---

### Key Files

| File | Role |
|---|---|
| BackEnd/engine/phase_resolution.py | `_dynamic_hco_motion_enabled` / `_dynamic_hco_setplay_enabled` (gates), `resolve_hco_outcome` (skip up-front tables), `_resolve_hco_moment_walk` + `_resolve_hco_moment` + `HCO_MOMENT_SCALAR`, `_resolve_motion_offense_shot_dynamic` / `_resolve_setplay_offense_shot_dynamic` / `_setplay_recovery_roll`, `_execute_motion_decision`, `_roll_subtle_defender_reads`, reach-in tag application |
| BackEnd/engine/motion_step_decision.py | `decide_step_action`, `should_shoot`, shoot/read/tempo constants |
| BackEnd/engine/motion_subtle.py | `build_subtle_beat` + subtle constants |
| BackEnd/engine/motion_read_map.py | `build_motion_read_map`, `read_flag`, `READ_THRESHOLD` |
| BackEnd/engine/dynamic_hct.py | `_resolve_moment` (shared contest) + `HCT_D8_*` constants |
| BackEnd/engine/skeleton_step_emitter.py | UESS render; `reach_in_def_id` → `reach_in` flourish stamping |
| BackEnd/models/animator.py | `_subtle_defender_should_freeze` (defender freeze geometry) |
| FrontEnd/static/js/phaser/animation/flourishes.js | `runReachIn` + steal SFX (FE render) |
| tests/test_motion_*.py | motion: moment walk, subtle, defender freeze, should_shoot, read map |
| tests/test_setplay_dynamic_*.py | set-play: flag gate, recovery roll, walk |
| dynamic_hco_prototype.py / dynamic_setplay_prototype.py | Seeded Monte-Carlo prototypes (standalone; no Mongo) |

---

### How to test / tune

1. Set `GOB_DYNAMIC_HCO_MOTION=1` and/or `GOB_DYNAMIC_HCO_SETPLAY=1`. Run man-defense possessions of each type.
2. Watch logs: `🎲 [DYNAMIC MOTION] turn gate ...`, `🔹 ... SUBTLE_MOVEMENT`, `🎯 ... SHOOT ...`, `⚔️ [HCO MOMENT] <TYPE> at step N` (set-play: recovery re-enter vs freelance after forced subtle).
3. To see more moments/reach-ins, raise the defense `aggression` setting (engagement) and/or `HCO_MOMENT_SCALAR` (event prob). Revert after.
4. Unit tests + prototypes:

```bash
MONGO_URI="" MONGO_DB_NAME="gob-test" python3 -m pytest \
  tests/test_motion_*.py tests/test_setplay_dynamic_*.py -q -o addopts=""
MONGO_URI="" MONGO_DB_NAME="gob-test" python3 dynamic_hco_prototype.py
MONGO_URI="" MONGO_DB_NAME="gob-test" python3 dynamic_setplay_prototype.py
```

---

### Related Documentation
- [projects/Z-Completed/Dynamic_HCO_Motion_Brief.md](../projects/Z-Completed/Dynamic_HCO_Motion_Brief.md) — archived motion build brief
- [projects/Z-Completed/Dynamic_HCO_SP_Brief.md](../projects/Z-Completed/Dynamic_HCO_SP_Brief.md) — archived set-play build brief
- [ENV_VARIABLES.md](../ENV_VARIABLES.md) — `GOB_DYNAMIC_HCO_MOTION` / `GOB_DYNAMIC_HCO_SETPLAY`
- [Shot_Micro_Movements_System.md](Shot_Micro_Movements_System.md) — shot-time micros (pump fake, dunk, etc.) — separate from mid-HCO subtle movement
- [HCO_Turn_Resolution_System.md](HCO_Turn_Resolution_System.md) · [Motion_Offense_Shot_System.md](Motion_Offense_Shot_System.md) · [HCT_System.md](HCT_System.md) · [FCP_System.md](FCP_System.md) · [Stopper_System.md](Stopper_System.md) · [Steal_System.md](Steal_System.md) · [SFX_System.md](../11_Design_Systems/SFX_System.md)
