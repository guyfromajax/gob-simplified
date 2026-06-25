## Dynamic HCO Motion System ✅ **SHIPPING (flagged)** (June 2026)

**Feature gate:** env var `GOB_DYNAMIC_HCO_MOTION` (`1`/`true`/`yes`/`on`). Off → legacy HCO motion path (up-front outcome tables + static skeleton). This doc describes the ON path.

**Scope today:** half-court **offense, motion plays, man + zone defense**. Set plays are deferred (see [Deferred / Roadmap](#deferred--roadmap)). The companion working brief is [projects/Dynamic_HCO_Motion_Brief.md](../projects/Dynamic_HCO_Motion_Brief.md) — this file is the authoritative system doc; the brief holds build-phase scratch + rationale.

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
Two-stage: **(1) is this an optimal look?** — shot-type mismatch score from the read map + openness vs the `_shoot_threshold` bar (`SHOOT_THRESHOLD_BASE` lowered by clock drain + tempo). **(2) read tier** — `(player_read_raw + discipline) × d6`: `> SHOOT_READ_RIGHT` shoot if optimal else progress; `> SHOOT_READ_SAFE` progress; else random. Shot type (attack vs outside) is a team-biased weighted pick (`_weighted_attack_or_outside`).

---

### 4. Passing lanes & hot-read openness (SPEC — building)

A defender sitting in a passing lane can disrupt an HCO **hot-read dish or kickout** (skeleton motion/reversal passes are NOT contested). Reuses the shared HCT pass model `resolve_pass_contest` (spatial lane gate → skill/anticipation → `complete` / `BAT_OOB` / `INTERCEPT`). **Hybrid** design:

- **Decision gate ("truly open"):** when `should_shoot` evaluates a teammate as a hot-read **dish** target, that teammate is only "open" if the BH→teammate lane is clear — no eligible defender within the perpendicular lane distance. A covered lane removes him from the dish candidates (the offense won't force it).
- **Contest (interception):** when a dish/kickout **is** thrown, run `resolve_pass_contest`; `INTERCEPT`/`BAT_OOB` converts the would-be shot into a turnover, routed through the existing non-shot resolution + stopper system (same path as the per-step Moment). `complete` → the shot resolves as today.

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
| `PASS_LANE_DIST` | pass_contest.py | `8.0` | HCT lane distance (and the param default). Shared pure model. |
| `FCP_PASS_LANE_DIST` | *(planned)* | `8.0` | FCP lane distance once FCP pass contests are wired (Roadmap). |
| `HCT_D8_GLOBAL_SCALAR` | dynamic_hct.py | `1.0` | Global per-moment frequency (affects HCT/FCP/HCO). |
| `HCT_D8_DEF_WIN_BASE` | dynamic_hct.py | `0.45` | Base P(any event) when defense fully wins the contest. |
| `HCT_D8_P_EVENT_MAX` | dynamic_hct.py | `0.60` | Cap on per-moment event probability. |
| `HCT_D8_AGG_MULT` | dynamic_hct.py | `{passive:0.7, normal:1.0, aggressive:1.3}` | Aggression multiplier on event prob (uses `aggression_call` string). |
| `HCT_D8_DFOUL_BASE` / `HCT_D8_P_DFOUL_MAX` | dynamic_hct.py | `0.12` / `0.25` | Base / cap for D_FOUL on a decisive blow-by. |
| `HCT_D8_S_SENS` / `HCT_D8_DB_SENS` / `HCT_D8_O_SENS_IQ` | dynamic_hct.py | `1.2` / `1.0` / `0.8` | Steal / dead-ball / charge sensitivity to attribute gaps. |
| `HCT_D8_W_PTEFF` / `W_PTOPP` / `W_FIGHT` / `W_DISC_REACH` | dynamic_hct.py | `0.04` each | Team-modifier weights (pt_efficiency, pt_opp, fight, discipline). |

> **Two-factor steal rate:** effective rate ≈ *engagement %* (`MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION`) × *conversion* (`HCO_*_MOMENT_SCALAR` × D8 × `HCT_D8_AGG_MULT`). Aggression raises both. To thin steals globally, lower the engagement %; to thin them on one defense type, lower that type's scalar.

#### Subtle movement
| Constant | File | Default | Effect |
|---|---|---|---|
| `MOTION_READ_THRESHOLD` | motion_step_decision.py | `110` | Per-teammate read bar `(player_read_raw + off_eff) × d6` to relocate on a subtle beat. ↑ = fewer teammates move. Also the defender-follow bar. |
| `SUBTLE_STEP_ELAPSED_BY_TEMPO` | motion_step_decision.py | `{slow:(3,4), normal:(2,4), fast:(2,3)}` | Steps elapsed before a subtle beat can pause (tempo floors). |
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
| **Passing lanes & hot-read openness** | 🔨 Building (see §4). ✅ Decision gate ("truly open") shipped for **man + zone** (`_hco_blocked_dish_targets` + `defenders_in_lane`); ⏳ interception contest on thrown dishes/kickouts is the next stage. Hot-read/kickout dishes only. |
| **FCP pass contests @ 8** | 🔨 Planned (§4 stage 3). FCP has **no** pass-disruption today — needs a pass-beat audit (inbound / press-break / advance) before wiring `resolve_pass_contest` with `FCP_PASS_LANE_DIST = 8.0`. (NB: interceptions seen on "FCP" today are the post-steal **rim-runner fast break** mechanic, labeled `FAST_BREAK`, not FCP.) |
| **Set-play moments** | Deferred — motion only for now. |
| **True per-step shoot↔moment interleaving** | The moment walk currently runs fully **before** the shot resolver, so a moment pre-empts the would-be shot. True interleaving needs the late shot resolver (after shot-clock truncation). |
| **Pass interceptions** | HCT's `pass_contest` not yet ported to HCO. |
| **Reach-in option A** | We ship **B** (every contested step). A (defender-wins-only: terminal + `NEUTRAL`, skip `POS_O` blow-bys) is the documented alternative if B reads too busy. |

---

### Key Files

| File | Role |
|---|---|
| BackEnd/engine/phase_resolution.py | `_dynamic_hco_motion_enabled` (gate), `resolve_hco_outcome` (skip up-front tables), `_resolve_hco_moment_walk` + `_resolve_hco_moment` + `HCO_MOMENT_SCALAR`, `_resolve_motion_offense_shot_dynamic` (offense walk), `_execute_motion_decision`, `_roll_subtle_defender_reads`, reach-in tag application |
| BackEnd/engine/motion_step_decision.py | `decide_step_action`, `should_shoot`, shoot/read/tempo constants |
| BackEnd/engine/motion_subtle.py | `build_subtle_beat` + subtle constants |
| BackEnd/engine/motion_read_map.py | `build_motion_read_map`, `read_flag`, `READ_THRESHOLD` |
| BackEnd/engine/dynamic_hct.py | `_resolve_moment` (shared contest) + `HCT_D8_*` constants |
| BackEnd/engine/skeleton_step_emitter.py | UESS render; `reach_in_def_id` → `reach_in` flourish stamping |
| BackEnd/models/animator.py | `_subtle_defender_should_freeze` (defender freeze geometry) |
| FrontEnd/static/js/phaser/animation/flourishes.js | `runReachIn` + steal SFX (FE render) |
| tests/test_motion_*.py | moment walk, subtle, defender freeze, should_shoot, read map, shot-spot classification |

---

### How to test / tune

1. Set `GOB_DYNAMIC_HCO_MOTION=1`. Run man-defense motion possessions.
2. Watch logs: `🎲 [DYNAMIC MOTION] turn gate ...`, `🔹 ... SUBTLE_MOVEMENT`, `🎯 ... SHOOT ...`, `⚔️ [HCO MOMENT] <TYPE> at step N`.
3. To see more moments/reach-ins, raise the defense `aggression` setting (engagement) and/or `HCO_MOMENT_SCALAR` (event prob). Revert after.
4. Unit tests: `MONGO_URI="" MONGO_DB_NAME="gob-test" python3 -m pytest tests/test_motion_*.py -q -o addopts=""`.

---

### Related Documentation
- [projects/Dynamic_HCO_Motion_Brief.md](../projects/Dynamic_HCO_Motion_Brief.md) — build-phase brief (rationale, phase log, condition matrix)
- [HCO_Turn_Resolution_System.md](HCO_Turn_Resolution_System.md) · [Motion_Offense_Shot_System.md](Motion_Offense_Shot_System.md) · [HCT_System.md](HCT_System.md) · [FCP_System.md](FCP_System.md) · [Stopper_System.md](Stopper_System.md) · [Steal_System.md](Steal_System.md) · [SFX_System.md](../11_Design_Systems/SFX_System.md)
