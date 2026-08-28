## Dynamic HCO System ✅ **SHIPPED** (motion + set play, June–July 2026)

**Motion + set play are ALWAYS ON (flags retired, Stage 3 2026-07-12).** The legacy up-front outcome
tables + static-skeleton path were removed for both, so the `GOB_DYNAMIC_HCO_MOTION` /
`GOB_DYNAMIC_HCO_SETPLAY` kill switches had nothing to fall back to and were deleted. The one live gate:
- `GOB_DYNAMIC_HCO_DEFENSE` — **ON by default** (kill switch = falsy); per-turn defender **posture**
  placement + the two-gate pass-intercept model. See **§ Dynamic Defense**.

**Scope:** half-court **offense — motion plays and set plays, man + zone defense**. Set plays **reuse
motion's machinery**; only the deltas in **§ Set plays** are new. This file is authoritative for runtime.

> **Architecture (2026-07 unification):** motion + set play + the on-ball moment + interception all
> resolve inside **one per-step walk** — `_resolve_hco_offense_shot_dynamic(…, is_setplay=)`. The moment
> is **fused** into that walk (was a separate `_resolve_hco_moment_walk` pass); the interception contest
> judges against the **rendered** defender grid (resolve-once → freeze → draw). See **§ StepState: one
> walk, one grid** and the archived refactor history in
> [projects/Z-Completed/StepState.md](../projects/Z-Completed/StepState.md). Remaining upstream
> StepState ownership work is tracked in [UESS System §12.3](../05_UESS_System/UESS_System.md#123-stepstate-upstream-ownership-gap).
> Archived build briefs: [Dynamic_HCO_Motion_Brief.md](../projects/Z-Completed/Dynamic_HCO_Motion_Brief.md),
> [Dynamic_HCO_SP_Brief.md](../projects/Z-Completed/Dynamic_HCO_SP_Brief.md).

---

## Tunable Constants

Shot-timing dials, all in [`BackEnd/engine/motion_step_decision.py`](../../BackEnd/engine/motion_step_decision.py) and wired by `_resolve_hco_offense_shot_dynamic` in `phase_resolution.py`. These govern *when* within a motion turn the ball handler shoots, dishes, or works the ball.

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
- `OPTIMAL_BAR_STEEPNESS = 1.9` — self-shot and hot-read dish share it.
- `OPTIMAL_BAR_TEMPO_MULT = {slow: 1.2, normal: 1.0, fast: 0.8}`

Higher bar = fewer/later shots; slow tempo demands a better look (work the ball), fast shoots sooner. Self stays slightly favored over the dish via the self-only openness bonus + self-wins-ties tiebreaker (not the bar). Illustrative values (normal tempo): 30s → 57, 22s → 41.8, 15s → 28.5, 8s → 15.2.

### Random-tier shoot % (`RANDOM_TIER_SHOOT_PCT`)
Non-strategic ("random") read tier: `randint(1,100) ≤ %` → shoot (self only). Low early, high late.

| Tier | slow | normal | fast |
|---|---|---|---|
| Early | 10 | 20 | 30 |
| Mid | 20 | 35 | 50 |
| Late | 95 | 95 | 95 |
| Very late | 95 | 95 | 95 |

### Outside-shot selection weight (`OUTSIDE_SHOT_SELECTION_MULTIPLIER`)

When an outside/attack location chooses its shot type, the outside score
`SH + outside emphasis × 10` is multiplied by `0.55` before it competes with the attack score.
This redirects some former outside choices into attacks without rejecting a shot or delaying the
skeleton walk. It applies to ball-handler and dish/hot-read candidates through the shared
`_weighted_attack_or_outside` decision. The multiplier applies at every clock tier; because early
and mid account for most HCO attempts, the aggregate reduction is concentrated in those tiers.

`OUTSIDE_SHOT_ACCEPTANCE_PCT_BY_TIER` remains an explicit downstream dial, but is now 100% in every
tier so an outside shot that wins selection is not subsequently discarded.

| Tier | Acceptance |
|---|---:|
| Early | 100% |
| Mid | 100% |
| Late | 100% |
| Very late | 100% |
| Forced | 100% |

### Subtle-movement precedence (`SM_PRECEDENCE_TEMPOS`)
When the turn's `offense_reads` (alterations) roll is on, these tempos make **subtle movement take precedence over the shoot decision** — the BH works the ball and defers his shot/hot-read. Reuses the per-turn alterations roll (NOT a second roll). Precedence retreats as the clock drains and tempo speeds up.

| Tier | slow | normal | fast |
|---|---|---|---|
| Early | ✓ | ✓ | ✓ |
| Mid | ✓ | ✓ | ✗ |
| Late | ✓ | ✗ | ✗ |
| Very late | ✗ | ✗ | ✗ |

### Read tiers (`_shoot_read_tier`)
`(player_read_raw + discipline) × d6`: `> SHOOT_READ_RIGHT (200)` → right (take the best optimal look, self or dish); `> SHOOT_READ_SAFE (125)` → safe (always progress); else random (use the % grid above). SM-precedence is evaluated **before** this — when it fires, the read tier is bypassed for that step.

---

### Overview

Legacy HCO predetermined a motion turn's outcome up front (flat percentile tables for foul / steal / turnover, checked before the skeleton renders). Dynamic HCO replaces that with **per-step resolution**: the offense walks its motion skeleton making attribute-driven reads (move / shoot / pass) while the defense contests **each step** (steal / foul / turnover), exactly mirroring how HCT (half-court trap) and FCP (full-court press) already resolve. Nothing is predetermined; everything is reproducible from attributes + seeded RNG (SS&S), and the **FE is a pure renderer** — all logic is backend-side, all motion is emitted as normal UESS skeleton steps + flourishes (no FE decisions, no coord mutation on the client).

**Three subsystems, all resolved inside the ONE per-step walk (`_resolve_hco_offense_shot_dynamic`):**
1. **Turn gate** — per-turn rolls decide whether the offense makes reads and whether the defense pressures (+ a separate moment-engagement roll).
2. **Per-step Moment** — the on-ball defender contests the ball **moment-first on each REACHED step**, before the offense's chosen shot/dish resolves; a hard outcome (steal/foul/turnover) ends the possession there. Migrated from HCT's D8 model, **fused into the walk** (2026-07-12).
3. **Per-step offense walk** — subtle movement beats, defender freeze reaction, and the Universal Shoot Decision (`should_shoot`) that decides when/what to shoot.

#### Attack-drive contest: shared core, half-court consumption

HCO attack drives share the same `_resolve_moment` contest core used by Fast
Break and broken HCT/FCP cutoffs, but intentionally do not share their
post-contest transition behavior. `_resolve_hco_drive_contest()` calls
`_resolve_moment(..., exclude_steal=True, clean_stop=True,
neutral_band=DRIVE_NEUTRAL_BAND)` with HCO offensive/defensive efficiency
modifiers. Help-cutoff geometry reuses `best_cutoff_on_drive()`; a help collision
is resolved through the same HCO contest helper so its clean-stop band and
tuning remain identical to the primary matchup.

| Shared outcome | HCO tier / behavior |
|----------------|---------------------|
| `POS_O` | Tier A blow-by to the rim, unless a help defender makes a geometric cutoff |
| `D_FOUL` | Tier A plus defensive-foul contact; existing shooting-foul/and-1 routing owns resolution |
| `NEUTRAL` | Tier B contested stop at `DRIVE_NEUTRAL_STOP_FRACTION`; re-read pull-up versus dish |
| `D_STOP` | Tier C early clean stop at the returned ratio; re-enter the half-court read |
| `O_FOUL` / `DEAD BALL` | Tier C terminal contact through existing foul/turnover routing |

The shared boundary is contest math and outcome vocabulary—not a universal
reaction to the outcome. Broken HCT/FCP transition stops reset directly to HCO,
and Fast Break owns its dynamic stop decision; neither should be forced onto the
HCO pull-up/dish read. Canonical transition mapping lives in
[`HCT_System.md`](HCT_System.md#the-possession-loop); Fast Break consumption lives
in [`Fast_Break_System.md`](Fast_Break_System.md#meet-resolution-order-never-double-foul).

---

### Where it hooks in

`resolve_half_court_offense_logic` (BackEnd/engine/phase_resolution.py):

```
resolve_hco_outcome(game, skeleton)             # motion → skips up-front event tables (variant still chosen for set play)
final_skeleton = deepcopy(chosen skeleton)      # cached skeleton never mutated
  ↓ result == "SHOT"
_walk = _resolve_hco_offense_shot_dynamic(final_skeleton, …, is_setplay=, roll_moment=True)
        # ONE walk: per reached step → moment-first, then scripted-pass / shoot / dish / subtle.
        # Returns one of:
        #   • moment dict {moment_result, skeleton(reached steps), moment_stop_index, …}
        #   • shot-info  {skeleton(reached+shot steps), shooter*, shot_type, …}
        #   • interception (pass_intercepted flag) — a picked scripted/dish pass
  ↓
moment  → result = moment_result; final_skeleton = reached walk
          → existing non-shot resolution + apply_stopper_system_to_skeleton  (steal/foul/turnover)
shot    → cache _hco_precomputed_shot_info; shot-clock check [2] runs on the reached walk
          → [5] consumes the cache (NO re-walk — a 2nd RNG walk would desync moment↔shot),
            then _hco_contest_final_skeleton coverage sweep + interception finalize
  ↓
skeleton_step_emitter.build_skeleton_animation_steps(…)   # UESS render: steps, SFX, reach_in flourishes
```

The walk appends the **base step dicts verbatim** (`output_steps.append(steps[i])`), so custom step keys (`_subtle_movement`, `_hot_read_sfx`, `reach_in_def_id`) survive untouched into the emitted skeleton. **Why one walk:** the moment used to run as a separate full-skeleton pass that could fire on a step the offense never reached (it had already shot earlier), pre-empting a shot that should have stood; fusing it into the walk fixed that (baseline: HCO shot rate 69%→77%, the moments that used to steal unreached-step possessions).

---

### 1. Turn gate

Two decoupled per-turn rolls in `_resolve_hco_offense_shot_dynamic`:

| Roll | Formula | Effect |
|---|---|---|
| `offense_reads` | `randint(0,4) <= alterations` | offense executes reads (subtle movement / hot reads) this turn |
| `defense_pressure` | `randint(0,4) <= aggression` | defense applies step pressure (feeds the freeze reaction) |

`alterations` and `aggression` are integer `strategy_settings` sliders (0–4). Neither true → the turn walks straight to a shot with no reads/pressure. **The per-step Moment has its OWN, separate engagement roll** (also in the walk now, rolled once per turn) — a percentage curve (`MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION`, see §2), *not* this flat `randint(0,4) <= aggression`. So aggression gates the freeze-reaction pressure (here) and the moment frequency (there) independently.

---

### 2. Per-step Moment (foul / steal / turnover)

**Fused into the walk** (2026-07-12) — the moment rolls **inside** `_resolve_hco_offense_shot_dynamic`, moment-first on each reached step, gated by `roll_moment=True` (only the one authoritative up-front walk rolls it; recalibration + fallback re-walks pass `False`). The standalone `_resolve_hco_moment_walk` is **retired from the spine** but kept as the unit-tested reference spec — keep the two in sync.

1. **Engagement:** rolled ONCE per turn, by defense aggression → % of possessions with any contest (`MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION` = `{0:5, 1:20, 2:35, 3:50, 4:75}`), else no moment this turn. Same gate for man and zone.
2. **Per REACHED step (moment-first):** before the offense's scripted-pass / shot / dish resolves, resolve the on-ball defender — **man:** the matchup defender (`off_to_def[bh_pos]`); **zone:** prefer the renderer's stamped guard map (`step["_step_state"]["guard"]`) and select the defender explicitly assigned to the current ball-handler ID. If that stamp is unavailable, `_zone_bh_defender` falls back to zone-polygon containment, nearest-zone centroid, then position-on-position. Fire `_resolve_hco_moment` → `_resolve_moment` (shared HCT D8 contest), scaled by `HCO_MOMENT_SCALAR` (man) / `HCO_ZONE_MOMENT_SCALAR` (zone). **The walk only rolls the moment on steps the offense actually reaches — it can no longer fire on a step the offense skipped by shooting earlier** (the fusion's whole point; per Decision #1: moment-first, first terminal in step order wins).
3. **Hard outcome ends the walk here:** `STEAL` / `DEAD_BALL_TURNOVER` / `O_FOUL` / `D_FOUL` → returned as a moment dict with the reached-walk skeleton truncated at this step (`moment_stop_index`); the caller sets `result`, and the **existing** non-shot resolution + `apply_stopper_system_to_skeleton` route/render it (no new emission path). `NEUTRAL` (defender won, no event) / `POS_O` (offense beat defender) → append a reach-in tag, continue the walk.
4. **Credited defender + stop-index stash:** a hard outcome stashes the contesting defender's id (`game_state["_hco_moment_defender_id"]`) + the step it fired at (`_hco_moment_stop_index`); the non-shot block + `apply_stopper` consume them so the steal credit (`stealer_id`), terminal reach-in, and stopper truncation land on the **actual** defender/step (critical for zone; also kills the old "ball snap-back on a non-shot outcome" teleport by pinning the outcome to its step).

The contest math (steal vs dead-ball vs charge weighting, attribute gaps, team modifiers) lives in `_resolve_moment`, shared with HCT — see [HCT_System.md](HCT_System.md). HCO scales the whole event probability by `HCO_MOMENT_SCALAR` (HCT/FCP pass the default 1.0, so they are mathematically unchanged).

#### Reach-in micro-movement (the "pressure moment" visual — option B)

HCO has a single on-ball defender, so it does **not** use FCP/HCT's multi-defender *converge*. Instead the on-ball defender lunges at the ball via the render-space **`reach_in` flourish** (`flourishes.js` → `runReachIn` + `playStealReachInSfx` / `click-steal.wav`). It fires on **every contested step of an engaged turn** (option B — so the coach sees an aggressive defense constantly poking, successes and whiffs alike):

| Case | Tag source | Step |
|---|---|---|
| Terminal (`STEAL`/`DEAD_BALL_TURNOVER`/`D_FOUL`) | non-shot block sets `reach_in_def_id` on the **stopper step** | the stop |
| Non-terminal (`NEUTRAL`/`POS_O`) | walk appends `(step_index, defender_id)` to `reach_in_tags`; caller applies to `final_skeleton` **post-deepcopy** | each contested step |

`O_FOUL` (offensive charge) is excluded. `skeleton_step_emitter` turns any `reach_in_def_id` on a step into `step.start.flourish[id] = {kind:"reach_in", target:"ball"}`. **Pure render-space — never mutates gameplay coords (UESS-safe).** Non-engaged turns show no reach-ins, so reach-in *presence* reads as defensive aggression.

---

### 3. Per-step offense walk

`_resolve_hco_offense_shot_dynamic` walks the skeleton accumulating an output step stream (base steps woven with inserted subtle-movement beats). Per step — **after** the moment-first roll (§2) — it calls `decide_step_action` (motion_step_decision.py):

- **SUBTLE_MOVEMENT** — insert a `build_subtle_beat` (motion_subtle.py): the BH nudges off-pattern; each non-BH teammate makes his own read (`(player_read_raw + off_eff) * d6 > MOTION_READ_THRESHOLD`) to relocate or hold; the next skeleton step pulls everyone back ("pop back"). Movers render at the `cruise` archetype.
- **Defender freeze reaction** — per-defender read (`_roll_subtle_defender_reads`); a defender whose man moved but whose read FAILED freezes instead of following (`_subtle_defender_should_freeze`, applied geometrically in the animator).
- **Universal Shoot Decision** (`should_shoot`) — see below.
- **SHOOT / KICKOUT_SHOOT / HOT_READ_SHOOT** terminate and append shot steps via `_execute_motion_decision`. If no shot fires by the last step, force one (with a `SUBTLE_FORCED_SHOT_PENALTY` if the clock forced it).

#### Universal Shoot Decision (`should_shoot`)
Two-stage: **(1) is this an optimal look?** — shot-type mismatch score from the read map + openness vs the continuous optimal bar `clock × OPTIMAL_BAR_STEEPNESS × OPTIMAL_BAR_TEMPO_MULT` (see § Optimal-look bar above). **(2) read tier** — `(player_read_raw + discipline) × d6`: `> SHOOT_READ_RIGHT` shoot if optimal else progress; `> SHOOT_READ_SAFE` progress; else non-strategic ("random"). Shot type (attack vs outside) is a team-biased weighted pick (`_weighted_attack_or_outside`).

For a teammate selected by a dish/hot read at a non-inside location, that same weighted
attack-versus-outside result controls execution: **outside** emits pass → receive → immediate shot;
**attack** emits pass → receive → the standard attack-drive clearance/contest sequence → finish
(or its normal drive-contact/dish outcome). Thus an attack-labeled receiver never takes an
attack-classified catch-and-shoot from the perimeter.

##### Random-tier shoot progression
The non-strategic ("random") tier no longer shoots a flat 50/50 each step — it rolls `randint(1,100) ≤ _random_tier_shoot_pct(shot_clock, tempo)`, a clock+tempo progression (low early, high late) that stops undisciplined possessions from dumping early shots. Buckets (`RANDOM_TIER_SHOOT_PCT` in `motion_step_decision.py`):

| Shot-clock bucket | slow | normal | fast |
|---|---|---|---|
| Early (23–30s) | 10% | 20% | 30% |
| Mid (15–22s) | 20% | 35% | 50% |
| Late (6–14s) | 95% | 95% | 95% |
| Very late (1–3s) | 95% | 95% | 95% |
| Forced (<1s) | 100% (existing `<1s` forced-shot backstop) |

Very-late is flat 95% for all tempos (clock pressure dominates). The "right" and "safe" tiers are unchanged.

Every outside-vs-attack decision produced by these or the strategic read paths discounts the
outside candidate score with `OUTSIDE_SHOT_SELECTION_MULTIPLIER = 0.55`. The downstream
`OUTSIDE_SHOT_ACCEPTANCE_PCT_BY_TIER` is 100% at every tier, so selection changes shot mix without
rejecting an already-selected shot or pushing the possession later.

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

**Always on** (the `GOB_DYNAMIC_HCO_SETPLAY` flag was retired with the legacy set-play path, Stage 3).

#### Model: OVERLAY

The up-front **variant roll** (`successful` / `mid_play_change` / `contested` / `broken`) **still** selects the skeleton. The dynamic per-step layer overlays on the chosen variant skeleton. `get_hco_skeleton` runs `_apply_set_play_runtime_position_mapping`, so the variant skeleton arrives **position-keyed** (PG/SG/…) just like motion's `base_loop` — the motion helpers walk it directly, no slot mapping.

**Scope:** half-court offense, set plays, **man + zone** defense.

#### Where it hooks in

```
resolve_hco_outcome(game, skeleton)              # set_play → skips up-front event tables; variant STILL chosen
  ↓ result == "SHOT"
final_skeleton = get_hco_skeleton(variant)       # executed variant skeleton, then deepcopy
_resolve_hco_offense_shot_dynamic(final_skeleton, …, is_setplay=True, roll_moment=True)
        # SAME one walk as motion — moment-first per reached step, then the set-play offense walk
  ↓ moment  → result = moment_result → existing non-shot resolution + apply_stopper_system_to_skeleton
    shot    → cached, consumed at [5] (shared motion roles-update + coverage + interception finalize)
skeleton_step_emitter.build_skeleton_animation_steps(…)
```

Set play runs the **identical** unified resolver as motion (the only behavioral fork is `is_setplay=True` → the recovery roll below). It runs after the variant skeleton is chosen + deep-copied (so it reads the actual play and reach-in indices align). Routing reuses the motion roles-update block: the set-play result has the same contract (`roles["shooter"/"motion_shot_type"/"motion_playcall"]` + passer re-derivation + dish-interception finalize).

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

`should_shoot` + truly-open gate (`_hco_blocked_dish_targets`) + dish interception · `decide_step_action`/`_disruption_branch` · `build_subtle_beat` · `_execute_motion_decision` · `_resolve_freelance` · the fused per-step moment (man + zone). Set play is literally the same `_resolve_hco_offense_shot_dynamic(…, is_setplay=True)` call as motion — the only set-play-specific code is `_setplay_recovery_roll` and the recovery fork inside the resolver.

#### Set-play tests + prototype

- `tests/test_setplay_dynamic_gate.py` — recovery-roll formula (the flag-gate tests were pruned when the flag was retired)
- `tests/test_setplay_dynamic_resolver.py` — walk: offense_reads forced False, universal hot read, forced-subtle → re-enter vs freelance, FREELANCE_FORCED, shot-clock backstop
- `dynamic_setplay_prototype.py` — seeded Monte-Carlo recovery-roll grid + walk path distribution. Run: `MONGO_URI="" MONGO_DB_NAME="gob-test" python3 dynamic_setplay_prototype.py`
- Unit tests: `MONGO_URI="" MONGO_DB_NAME="gob-test" python3 -m pytest tests/test_setplay_dynamic_*.py -q -o addopts=""`

---

### 4. Passing lanes & hot-read openness ✅ SHIPPED (man + zone)

A defender sitting in a passing lane can disrupt an HCO pass. **Contestable:** hot-read dishes + kickouts, **skeleton motion/reversal passes** (walk hook `_hco_contest_skeleton_pass`), and freelance passes. Reuses the shared HCT pass model `resolve_pass_contest` (spatial lane gate → skill/anticipation → `complete` / `BAT_OOB` / `INTERCEPT`). **Hybrid** design:

- **Decision gate ("truly open"):** when `should_shoot` evaluates a teammate as a hot-read **dish** target, that teammate is only "open" if the BH→teammate lane is clear — no eligible defender within the perpendicular lane distance. A covered lane removes him from the dish candidates (the offense won't force it).
- **Contest (interception):** when a dish/kickout **is** thrown, run `resolve_pass_contest`; `INTERCEPT`/`BAT_OOB` converts the would-be shot into a turnover, routed through the existing non-shot resolution + stopper system (same path as the per-step Moment). `complete` → the shot resolves as today. `INTERCEPT` → STEAL via `_finalize_hco_pass_interception`; `BAT_OOB` → offense retains (side inbound, no stats) via `_finalize_hco_pass_bat_oob`.
- **Result-payload gotcha (serialization):** an HCO non-shot finalize must **not** return the raw motion `roles` — its `action_timeline` / `touch_counts` are keyed by **Player objects**, and `JSONResponse` rejects non-str dict keys (`convert_players` coerces values, not keys). Strip both before returning (every HCO *shot* path already does). A key-coercion safety net in `convert_players` backstops any that slip through. (Fixed: BAT_OOB was returning raw roles → `TypeError: keys must be str… not Player`.)

**Defender coords and assignments at decision time** — the contest judges against the **rendered** defender grid: the engine stamps `compute_defender_grid` (the animator's own code) on each step *before* the walk (`_stamp_contest_defender_grid`), and `_hco_step_def_xy` reads that stamp (man + zone, one display frame). For zone, the same stamp also carries `assign_all_zone_defenders`'s `{def_pos: guarded_offensive_player_id}` map; moment and pass-contest selection invert that map to identify who the render actually assigned to the BH. So the roll, credit, and animation use one assignment instead of reconstructing it from an idealized spot. (Legacy per-mode reconstruction and polygon selection survive only as unstamped/context fallbacks.)

**Zone guard-map selection status (shipped July 2026):** the prior slot/polygon-only selection made the credited moment defender the raw nearest defender in only about 38% of measurable zone steals. Using the render's guard map raised that diagnostic to about 65% and removed the farthest-defender picks; more importantly, credited defender now matches the rendered guardian by construction. The remaining cases where that guardian is not the physically nearest defender are an intentional consequence of `assign_all_zone_defenders`, not a moment-credit bug. Because changing the selected defender also changes whose attributes resolve the strip, this was a gameplay/draw-moving fix; its recorded distributional multi-seed verification and seeded-reference re-cut remain verification debt.

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

### StepState: one walk, one grid (the 2026-07 unification)

**Governing law — resolve once → freeze → draw.** All game logic (decisions, RNG, geometry that affects
an outcome/stat/contest/position/clock) lives in the engine; the emitter is a pure projection; the FE
only draws. The unification pulled the HCO turn toward this. Fully-met pieces:

- **One resolution spine.** Motion + set play + moment + interception resolve in the single
  `_resolve_hco_offense_shot_dynamic` walk (see Overview). The old stack — a separate moment walk, a
  separate shot walk, and a coverage patch layered on top — collapsed to one authoritative walk whose
  output drives everything downstream.
- **Contest ↔ render share the defender grid.** The interception contest judges against the SAME
  placement the animator draws (man + zone). The engine stamps `compute_defender_grid` pre-emit for the
  contest; the emit stashes its exact per-player animations (`game._hco_render_animations`), and
  `build_step_states` reads that stash for `StepState.defense`. Live `🔬 STEPSTATE GAP` (canonical vs
  contest) measured **0%** man AND zone (was man 22–64%, zone up to 100% / a 96px mirror). The render
  never re-derives — no redundant draw.
- **OOB exit points are engine-owned.** `nearest_oob_point` resolves where a batted/deflected ball
  exits, for **HCO, HCT, and FCP**; the FE reads `bat_oob_target` instead of recomputing.

**Two intentional, measured exceptions (not "one path" in the strict sense):**

- **Coverage patch `_hco_contest_final_skeleton`** — a SECOND contest sweep after the walk, for dish
  passes the per-step paths don't tag (freelance/forced shot paths). **Measured load-bearing: ≈ 1.5
  picks/game ≈ 18% of HCO interceptions** (NOT recalibration). Kept deliberately — retiring it would
  drop the steal rate ~18%. It reads the same stamped grid, so it's not a data-divergence gap, just a
  second contest site.
- **Batted-OOB ball trajectory is flown imperatively by the FE** (`AnimationEngine._runHctBatOobBallSend`),
  not projected from StepState steps — the schema pipeline can't fly a ball off-court. The *positions*
  (contact, exit) are engine-owned; only the bounce *shape* is FE animation (cosmetic). HCO's earlier
  step-based trajectory was removed (it double-fired with the imperative send — "ball → OOB then bounced
  off the defender").

**Remaining actionable UESS work:** StepState is not yet the upstream owner of every game-relevant
per-step value; emitters still derive some meet-points, timing, advance gates, and interrupts. The
canonical scope is [UESS System §12.3](../05_UESS_System/UESS_System.md#123-stepstate-upstream-ownership-gap).
The two-grid ordering constraint and imperative cosmetic bat-OOB shape above are documented behavior,
not active correctness gaps. The blow-by-blow refactor history is archived in
[projects/Z-Completed/StepState.md](../projects/Z-Completed/StepState.md).

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
| `PASS_DEFLECT_KIND_D` | pass_contest.py | `200` | **Gate 3c** — on a deflection, `rand(1, D) < (CH+IQ)` → **INTERCEPT** (steal), else **BAT_OOB** (offense retains). The INTERCEPT/BAT_OOB **ratio** dial (not deflection frequency). **↑ D = more BAT_OOB.** Sim ≈ 46% BAT_OOB of deflections. *Deflection frequency + the Gate 3a/3b tiers (`HCO_PASS_SAFETY_BASE`, `HCO_PASS_INTERCEPT_TIER_MID`; `TIER_HI` is retired) live in the central [Tunable_Constants.md](../11_Design_Systems/Tunable_Constants.md).* |
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
| `OPTIMAL_BAR_STEEPNESS` | motion_step_decision.py | `1.9` | Optimal-look bar = `clock × steepness × tempo mult`. |
| `OPTIMAL_BAR_TEMPO_MULT` | motion_step_decision.py | `{slow:1.2, normal:1.0, fast:0.8}` | Slow raises the bar; fast lowers it. |
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
| **Zone-defense moments** | ✅ Shipped. On-ball defender prefers the rendered per-step guard assignment, with polygon/centroid/position fallback when unstamped; `HCO_ZONE_MOMENT_SCALAR` dial; contest uses the **same D8 weights** as man for v1 (reweighting toward deflections/help is a future tuning pass). |
| **Zone contest reweighting** | Deferred — v1 reuses man's D8 steal/dead-ball/charge weights. Zones realistically strip less and force more deflections/help; revisit `HCT_D8_*` weights (or a zone-specific set) + `HCO_ZONE_MOMENT_SCALAR` after live observation. |
| **Passing lanes & hot-read openness** | ✅ Shipped — needs prototype tuning (see §4). Decision gate ("truly open") + interception contest, **man + zone**, hot-read/kickout dishes only. Gate clears the 0.1–0.9 lane band, so the contest's net-new interceptions are the **receiver's man jumping the entry pass** (t→1.0), gated by passer skill — frequency tunable via `HCO_PASS_LANE_DIST_*` / `HCO_PASS_SAFETY_BASE` / `HCO_PASS_INTERCEPT_TIER_MID`. Intercept → STEAL (`is_interception`) via `_finalize_hco_pass_interception` (resolve_turnover_logic + stopper). |
| **FCP pass contests @ 8** | 🔨 Planned (§4 stage 3). FCP has **no** pass-disruption today — needs a pass-beat audit (inbound / press-break / advance) before wiring `resolve_pass_contest` with `FCP_PASS_LANE_DIST = 8.0`. (NB: interceptions seen on "FCP" today are the post-steal **rim-runner fast break** mechanic, labeled `FAST_BREAK`, not FCP.) |
| **Set-play overlay** | ✅ Shipped (flag retired, always on) — variant skeleton + the unified resolver (`is_setplay=True`); recovery roll after forced subtle (see **§ Set plays**). |
| **True per-step shoot↔moment interleaving** | ✅ **Done (2026-07-12, moment fusion).** The moment now rolls inside the walk, moment-first on each reached step, so it no longer pre-empts a shot the offense never reached. See **§ StepState**. |
| **Pass interceptions** | ✅ **Ported.** HCT's `pass_contest` runs on HCO dishes/kickouts, skeleton reversals (`_hco_contest_skeleton_pass`), and freelance passes; contest judges the rendered grid. See §4 + **§ StepState**. |
| **Reach-in option A** | We ship **B** (every contested step). A (defender-wins-only: terminal + `NEUTRAL`, skip `POS_O` blow-bys) is the documented alternative if B reads too busy. |

---

### Key Files

| File | Role |
|---|---|
| BackEnd/engine/phase_resolution.py | `resolve_hco_outcome` (skip up-front tables), **`_resolve_hco_offense_shot_dynamic`** (the ONE unified walk: motion + set play + fused moment + interception; `is_setplay`/`forced_shot_step_index`/`roll_moment` params), `_resolve_hco_moment` + `HCO_MOMENT_SCALAR`, `_setplay_recovery_roll`, `_execute_motion_decision`, `_roll_subtle_defender_reads`, `_stamp_contest_defender_grid` + `_hco_step_def_xy` (shared grid), `_hco_contest_final_skeleton` (coverage), `_finalize_hco_pass_interception` / `_finalize_hco_pass_bat_oob`, reach-in tag application. *(`_resolve_hco_moment_walk` retired from the spine, kept as the tested reference spec.)* |
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

1. Motion + set play are always on (no flag). Run man-defense possessions of each type. (`GOB_DYNAMIC_HCO_DEFENSE` gates only the defender-posture layer; leave it default-on.)
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
- [ENV_VARIABLES.md](../ENV_VARIABLES.md) — `GOB_DYNAMIC_HCO_DEFENSE` (motion/set-play flags retired)
- [projects/Z-Completed/StepState.md](../projects/Z-Completed/StepState.md) (historical refactor record) · [UESS System §12.3](../05_UESS_System/UESS_System.md#123-stepstate-upstream-ownership-gap) (remaining upstream-ownership work)
- [Shot_Micro_Movements_System.md](Shot_Micro_Movements_System.md) — shot-time micros (pump fake, dunk, etc.) — separate from mid-HCO subtle movement
- [HCO_Turn_Resolution_System.md](HCO_Turn_Resolution_System.md) · [Motion_Offense_Shot_System.md](Motion_Offense_Shot_System.md) · [HCT_System.md](HCT_System.md) · [FCP_System.md](FCP_System.md) · [Stopper_System.md](Stopper_System.md) · [Steal_System.md](Steal_System.md) · [SFX_System.md](../11_Design_Systems/SFX_System.md)


##Altered Actions
**Gated**
- Offensie players can only perform altered actions on steps where the bh executes a subtle movmenet or in freelance situations

**Definitiions**
- Inide locations: basketSpot, midLane, upper/lower: lowPost, midPost
- "Flash To" locations: midLane, topLane, upper/lower: midPost, highPost
- "Good Read": >110
- "Great Read: >200 (not applicable to all actions)

**Actions & Naming Convention**
- Backdoor Cut: "backdoor"
- Jab Step "jab step"
- Flash "flash"
- Post Up "post up"

**Backdoor Cut**
- If an offensie player is in a non-inside location he can perform a backdoor cut targeting an inside location
- Defender reads to binary result:
  - Good read: stick with cutter
  - Poor read: remains stationary

**Jab Step**
- If an offensie player is in a non-inside location he can perform a jab step -- moving in toward the basket at a direct angle toward teh baskeet 4-5 euclidian grid spots then returning to his spot
- Defender reads to binary result: 
  - Good read: sticks with jab stepper
  - Poor read: follow jab stepper inward an remains at the jab step defense location nearest the basket

**Flash**
- If an offensie player is at an inside location he can perform a flash -- moving to a flash location tha tis != his starting location
- Defender reads to binary result: 
  - Great read: sticks with flasher and fronts the pass
  - Good read: sticks with the flasher and stays behind him
  - Poor read: remains stationary

**Post Up**
- If an offensie player is at an inside location he can perform a flash, he can hold his position and actively post up
- Defender does not read, he inside defends:
  - Good defense: he fronts the post up
  - Poor defense: he sits behind the post up


## Tunable Constants — Pass Contest (HCO)

HCO passes resolve through `_hco_resolve_dish_contest` → `pass_contest.resolve_pass_contest`.

### Gate order

| # | Gate | Test | Fail → |
|---|---|---|---|
| 1 | Possession engagement | `rand(1,100) <= MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION[slider]` (5/20/35/50/75) | COMPLETE |
| 2 | In the lane | within `HCO_PASS_LANE_DIST_BY_AGGRESSION` (aggressive 5.0 / passive 6.0 / normal `randint(5,6)`, cached per game) | COMPLETE |
| 3 | Can reach it | `distance / AG_rate − IQ_headstart <= ball_flight_time` (`PASS_IQ_ANTICIPATION_MAX_SEC` = 0.15) | COMPLETE |
| 4 | Gambles | `rand(1,100) <= INTERCEPT_ATTEMPT_PCT_BY_CALL` (aggressive 80 / normal 40 / passive 0) | COMPLETE |
| 5 | Passer evades | `((PS·0.6+CH·0.2+IQ·0.2)+off_eff) × rand(1,6) > HCO_PASS_SAFETY_BASE − off_eff` | (pass) COMPLETE |
| 6 | Deflected | `((OD·0.6+CH·0.2+IQ·0.2)+def_eff) × rand(1,6) > HCO_PASS_INTERCEPT_TIER_MID − def_eff` | COMPLETE |
| 7 | Kind | `rand(1, HCO_PASS_DEFLECT_KIND_D) < (CH+IQ)` | INTERCEPT / BAT_OOB |

Gate 4 fires only when a defensive posture is set; the legacy path contests every eligible defender.

### Constants

| Constant | Value | Effect |
|---|---|---|
| `HCO_PASS_SAFETY_BASE` | 175.0 | Passer bar. ↑ = more deflections |
| `HCO_PASS_INTERCEPT_TIER_MID` | 170.0 | Deflection threshold. ↓ = more deflections |
| `HCO_PASS_DEFLECT_KIND_D` | **250** | INTERCEPT/BAT_OOB split **only**. ↑ = more batted balls |
| `HCO_PASS_INTERCEPT_TIER_HI` | 200.0 | **Dead** — retained for signature parity |

**Completion rate and the kind split are independent dials.** `SAFETY_BASE` +
`TIER_MID` govern how often a pass is deflected; `DEFLECT_KIND_D` governs only
what a deflection becomes. To shift the mix without moving completions, change D
alone.

At CH=50/IQ=50: D=200 → 49.5% INTERCEPT; **D=250 → 39.6% INTERCEPT / 60.4% BAT_OOB**
(set 2026-08-28). HCT/FCP keep the shared `PASS_DEFLECT_KIND_D` = 200.

### Which attribute acts where

| Attribute | Gate |
|---|---|
| AG | 3 only — closing speed (eligibility). Contributes nothing to any score |
| OD | 6 only — 0.6 weight in the deflection composite |
| CH | 6 (0.2 weight) **and** 7 |
| IQ | 3 (anticipation), 6 (0.2 weight) **and** 7 |

`rand(1,6)` is the largest single term in gates 5 and 6 — at average attributes the
composite is ~50, so the score spans 50–300 against a 170 bar. Narrow
`PASS_INTERCEPT_ROLL_MIN/MAX` to make interceptions more skill-driven.

### Missed gamble (2026-08-28)

A defender who clears gate 4 but loses at gate 5 or 6 now still **animates to the
contact point**. `resolve_pass_contest` reports `attempt_deflector` +
`attempt_contact_point` on every outcome after the contester commits, and
`_hco_contest_skeleton_pass` stamps an `_attack_drive.defender_overrides` entry
with action **`steal_miss`**.

`steal_miss`, not `steal_reach`: the skeleton emitter attaches the **ball** to a
`steal_reach` defender (that is the interception render). The animator honours any
override for placement, so a distinct action moves him without transferring
possession. Do not merge the two action names.

Previously a missed gamble was invisible — the defender never moved and an
aggressive defence paid no visible price for gambling.

#### Consequence: the receiver attacks (2026-08-28)

Moving the gambler is only half the price. When the gambler is **the receiver's own
defender**, the receiver catches the ball with nobody in front of him — so the walk
abandons the remaining play skeleton and drives immediately.

| Stage | Where | Behaviour |
|---|---|---|
| Signal | `_hco_contest_skeleton_pass` (`phase_resolution.py`) | On a non-`INTERCEPT`/`BAT_OOB` outcome, stamps `game_state["_hco_gamble_miss_drive"]` — **only** when `off_to_def[receiver] == attempt_deflector`'s position |
| Trigger | `_resolve_hco_offense_shot_dynamic`, immediately after the contest call | Pops the signal, resolves the receiver's location from the step's `pos_actions`, and returns `_execute_motion_decision(..., {"action": "SHOOT", "shooter_pos": receiver, "shot_type": "attack"})` |
| Bypass | `build_attack_drive_sequence` (`attack_drive_clearance.py`) | `primary_beaten` (kwarg **or** `game_state["_hco_primary_beaten"]`) forces the **primary** contest to Tier A / stop 1.0 |

**Unconditional.** Every missed gamble by the receiver's own defender produces the
drive — no second roll. The play skeleton is abandoned from that step; the drive
machinery supplies the rest of the possession.

**The bypass beats the primary, not the defense.** S2c help-cutoff still runs, so a
rotating helper can wall off the blow-by (Tier B/C from the cutoff, S2d path-stop,
S2e pull-up/dish). `_resolve_hco_help_cutoff` already excludes the primary from the
help race, so the stranded gambler is out of **both** roles with no special-casing.

**Flag hygiene.** Both keys are possession-scoped:

- `_hco_primary_beaten` is popped in a `finally` around the drive build.
- `_hco_gamble_miss_drive` is popped by the trigger, popped again at walk entry, and
  discarded by `_hco_contest_final_skeleton` — that coverage patch runs *after* the
  skeleton is final and cannot act on a missed gamble, so a signal it stamps would
  otherwise be inherited by the next possession as a phantom advantage.

`build_attack_drive_sequence` reads `_hco_primary_beaten` off `game_state` rather
than taking a parameter from the walk: threading one through
`_create_attack_drive_shoot_steps` would change a signature with three existing call
sites, which is exactly the shape of the `previous_step` production regression.

Tests: `test_motion_dynamic_resolver.py::test_missed_gamble_*`,
`test_attack_drive_clearance.py::test_beaten_primary_*`.

---

## Loose balls (2026-08-28)

A deflected pass used to have exactly one outcome — out of bounds, offense retains
on a side inbound. Every successful deflection was therefore a dead ball. Half of
them now stay in play and both teams scramble.

```
deflection (BAT_OOB)
  ├─ 50%  out of bounds, offense retains      (unchanged, `_finalize_hco_pass_bat_oob`)
  └─ 50%  loose ball
            ├─ bounce spot lands off the court → treated as out of bounds (above)
            └─ bounce spot in play → scramble
                  ├─ offense recovers → possession continues, shot clock NOT reset
                  └─ defense recovers → turnover (passer) + steal (recoverer)
```

**HCO only.** `BAT_OOB` also fires in HCT and FCP; those remain pure batted-OOB.

### The carom

A uniformly random direction and a uniformly random distance in `[4, 12]` from the
contact point. The result may land off the court — deliberately. That is what makes
a deflection near a sideline usually go out while one at half court never does, with
no second roll. Measured: **100% in play at half court, ~59% two grid spots off the
baseline.**

### Who comes up with it

Modelled on `select_rebounder_by_score`, with different inputs — a scramble rewards
different qualities than boxing out.

```
score = ((0.3·AG + 0.3·IQ + 0.4·CH) + fight) × rand(1, 6)
score × 1 / (1 + distance / LOOSE_BALL_DISTANCE_SCALE)
```

Every player within `LOOSE_BALL_CANDIDATE_RADIUS` of the bounce spot competes; ties
break at random (no rebound-style modifier/MO/chemistry ladder). If nobody is inside
the radius it expands until someone qualifies — a ball on the floor is always
recovered by *someone*.

Three deliberate departures from the rebound formula:

| | Rebounds | Loose balls | Why |
|---|---|---|---|
| team term | `chem × rebound_modifier`, added after the die | `fight`, added **inside** the die | as a flat addend on a composite averaging ~175, ±10 is a ±5.7% nudge — smaller than one pip. Inside the parenthesis it scales with the roll |
| distance scale | 8.0 | **4.0** — twice as steep | makes the random bounce spot, not the die, the main driver |
| offense discount | `OREB_REBOUND_SCORE_DISCOUNT` 0.8 | none | box-out models a rebound; a scramble has no possession bias |

`fight` is core-8, so it reads through `core8_gameplay()` per THE RULE in
`team_attr_scale` (stored ±20 → gameplay ±10).

**Geo is the weaker lever.** Measured over 150k simulated scrambles, the closest
eligible player wins **49.6%** at rebound scale and **54.2%** at 4.0. `rand(1, 6)` is
a 6× swing and dominates either way. If position needs to be more decisive than that,
**narrow the die** (`LOOSE_BALL_ROLL_MIN`/`MAX`) — at 3–6 the closest man wins 63.7%.

Measured over 60 simulated quarters (122 deflections → 55 loose balls): defense
recovers **49.1%**, and the deflector comes up with his own deflection **14.5%** of
the time.

### Coordinates

Offense from the pass step's named `pos_actions` locations, defense from
`step["_step_state"]["defense"]` — the same stamped render grid the pass contest
already judges geometry on, so the scramble is decided on what gets drawn.

**If that grid is absent the loose ball is declined and the ball goes out of bounds.**
Without it the legacy zone reconstruction returns HOME-frame defenders while offense
coords are display-frame, and mixing the two would put the bounce spot on the wrong
end of the floor. `_stamp_contest_defender_grid` runs before both the walk and the
coverage pass, so this is a guard, not a path.

### Turn routing

| Recovered by | Result | Possession | Shot clock | Stats |
|---|---|---|---|---|
| Offense | `DEAD BALL` → `next_turn: HCO` with `kickout_deferred_to_hco_entry` (the OREB handoff; HCO entry emitter builds `hco_entry_kickout`) | continues | **not reset** | none |
| Offense, shot clock < `LOOSE_BALL_FORCED_SHOT_CLOCK` | arms `_loose_ball_forced_shot_pending` → `_execute_forced_shot` next turn | continues | not reset | none |
| Defense | `resolve_turnover_logic(turnover_type="STEAL")` → same FB-vs-HCO determination every steal uses | flips | reset (Rule 1) | **TO to the original passer, STL to the recoverer** |

No shot-clock policy change was needed: `_should_reset_shot_clock` already returns
False for a non-flipping, non-rebound, non-foul result, and True on a possession flip.

`is_interception` stays **False** on a defensive recovery — that flag drives the FE's
INTERCEPTION! headline and SFX, which would misread a ball won on the floor. The next
possession's ball starts at the **bounce spot** (`last_stealer_coords`), not the
deflection contact point.

`_loose_ball_forced_shot_pending` is popped **before** the low-clock `elif` chain, not
at its own branch: inside an `elif`, an earlier match (expiring game clock, shot-clock
violation) would skip the pop and leak a phantom forced shot into a later possession.

### The scramble animation

`append_hco_loose_ball_trajectory` appends three steps at the same single point every
HCO turn passes through (`_emit_hco_animation_steps`), alongside the batted-OOB
trajectory. Mutually exclusive with it — a turn carries `bat_oob` **or** `loose_ball`.

| Step | Reason | Gate | T | What happens |
|---|---|---|---|---|
| A | `hco_loose_ball_contact` | `ball_reaches_player` | ball flight | pass leaves the passer, deflector attacks the lane; the other nine carry their unfinished movement forward |
| B | `hco_loose_ball_bounce` | `fixed_duration` | carom time | ball caroms to its resting spot while **all ten** break for it |
| C | `hco_loose_ball_recover` | `player_reaches_position` | remainder of the winner's run | winner covers the last ground and picks it up |

Total scramble = `max(bounce_t, winner_travel)`. A winner already standing on the spot
gets `recover_t == 0` and **Step C is skipped** — the ball lands in his hands on B.

### Audio

Step A ends when the ball reaches the deflector, so **Step B's `sfx_on_step_start` is
the instant the ball comes loose** — that is where the announcer call fires, before any
tween. One clip is chosen at random per loose ball:

| | |
|---|---|
| Clips | `braddock-loose-ball-v2.mp3`, `sammy-loose-ball-v3.mp3` (`LOOSE_BALL_SFX_FILES`) |
| Chosen by | backend, in `pick_loose_ball_sfx()` — UESS: the FE renders, it does not decide |
| RNG | **`announcement_rng`, not `sim_rng`** |

The presentation stream is mandatory here: sharing `sim_rng` would mean adding or
removing a clip shifts every subsequent basketball outcome. (The older hot-read coach
VO does draw from `sim_rng` — that predates the split and is currently disabled. Do
not copy it.)

It does **not** displace Step A's `block1.wav`, the physical contact thud — the two
layer: thud, then the call.

Both clips must also be listed in `GAMEPLAY_SFX_FILES`
(`FrontEnd/static/js/phaser/utils/gameSfx.js`). `playGameSfx` plays from a preloaded
pool, so a clip added on the backend alone warns to the console and is **silently
inaudible**. `test_clips_are_registered_in_the_frontend_preload_manifest` guards the
pair against drift.

**No frontend changes.** The imperative OOB ball-send is gated on `turnData.bat_oob`,
which a loose ball never sets. The reason strings are deliberately NOT the
`hct_bat_oob_*` pair — those are what `_hasSchemaBatOobTrajectory()` matches to
suppress that send, and borrowing them would make a ball still in play read as one
that left the court.

### Tunable Constants — Loose Balls

All in `BackEnd/engine/loose_ball.py`.

| Constant | Value | Effect |
|---|---|---|
| `LOOSE_BALL_FROM_DEFLECTION_PCT` | `50` | share of deflections that stay in play. ↑ = more scrambles, fewer dead balls. The realised rate is lower — bounces that land off the court revert to OOB |
| `LOOSE_BALL_BOUNCE_MIN_DIST` | `4.0` | closest the ball can come to rest from the contact point |
| `LOOSE_BALL_BOUNCE_MAX_DIST` | `12.0` | farthest. ↑ = wilder caroms, and more of them out of bounds near a sideline |
| `LOOSE_BALL_CANDIDATE_RADIUS` | `12.0` | how far a player can be from the bounce spot and still compete. Expands automatically if it would leave nobody |
| `LOOSE_BALL_DISTANCE_SCALE` | `4.0` | distance discount `1/(1 + d/SCALE)`. **LOWER = distance matters MORE.** Half of `REBOUND_DISTANCE_SCALE` |
| `LOOSE_BALL_AG_WEIGHT` / `IQ` / `CH` | `0.3` / `0.3` / `0.4` | the ability composite. Must sum to 1.0 to keep the scale comparable to rebounding's |
| `LOOSE_BALL_ROLL_MIN` / `MAX` | `1` / `6` | the die. **The dominant variance term** — a 6× swing. Narrowing it is the strongest way to make position and ability decide loose balls |
| `LOOSE_BALL_FORCED_SHOT_CLOCK` | `6.0` | offense recovering under this many seconds takes a forced shot instead of a fresh possession |
| `LOOSE_BALL_BOUNCE_GRID_PER_GAME_SEC` | `= PASS_GRID_SPOTS_PER_GAME_SECOND` (24) | carom speed. Derived, not a copied literal, so it can't silently diverge from the pass rate |
| `LOOSE_BALL_CONVERGE_ARCHETYPE` | `"sprint"` | pace the scramblers converge at |
| `LOOSE_BALL_SFX_FILES` | braddock-v2 / sammy-v3 | announcer clips, one chosen at random per loose ball. Must also be in the FE `GAMEPLAY_SFX_FILES` manifest |
| `LOOSE_BALL_SFX_VOLUME` | `0.7` | announcer call volume |

Tests: `tests/test_loose_ball.py` (32).
