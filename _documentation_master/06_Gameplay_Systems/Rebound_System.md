A unified system that handles rebound logic for all missed shot instances.

-HCO Shots
-Fast Break Shots
-OREB Putback Shots
-Free Throw Shots

## Post-shot placement authority (single source of truth)

Post-shot player destinations are authored into four overlay maps on the turn result dict, then absorbed into schema steps / `player.coords`:

- `offense_rebounder_coords` — non-get-back offensive players, clustered near the rim of the basket just attacked.
- `defense_rebounder_coords` — non-release defensive players, clustered near the rim of the basket just attacked.
- `offense_getback_coords` — offensive get-back retreaters (HCO only; HCT / FCP / Fast Break skip the get-back mechanic). The shot shooter is never a get-back retreater; backend selection excludes the shooter by both role position and `player_id` so stale position derivation cannot make the shooter eligible.
- `defense_release_coords` — defensive release players running for the outlet on a Covert Release fast break.

**Who stamps the maps**

- **HCO** — `shot_manager.resolve_shot` authors the maps (paint-cluster randoms for rebounders; get-back / release as applicable).
- **FAST_BREAK / HCT / FCP** — when those maps are empty (or missing a player) at schema post-shot time, `maybe_stamp_transition_shot_board_crash_overlays()` in `BackEnd/utils/transition_shot_board_crash.py` stamps rebounder overlays from the terminal shoot / finish step. It is invoked inside `skeleton_step_emitter._build_post_shot_sub_steps` (after shot-micro injection). Rules:
  - Eligible: offense and defense on `current_turn` ∈ {`FAST_BREAK`, `HCT`, `FCP`} for MAKE / MISS / BLOCK.
  - Always hold: shooter and shot defender (`shot_defender_id` / `defender_id` / `fb_drive_resolution` stopper / shot-defender keys).
  - Already moving on the shoot step → keep that destination in the overlay so `[ball_flight]` / `[bounce]` continue it.
  - Idle and already within `CONTEST_EUCLIDEAN_RADIUS` (11) of the attacked basket → leave in place.
  - Idle and farther than 11 → random destination within 11 Euclidean of the basket.
  - **Fast Break NEUTRAL** — hold all five defenders (matchup + help + shot/BH defender) and the two lead offenders; trailers may crash. Rim-finish / non-NEUTRAL FB uses the general hold set (shooter + shot defender only).
  - Existing overlay entries from `shot_manager` are left intact (not overwritten).
- **OREB putback** — does **not** re-stamp during-putback board crash; players hold post-MISS coords through putback flight. Failed-attemptor near-bounce collapse still runs on the OREB **capture** step (same helper as DREB).

Schema emitters apply overlays via `_apply_overlay_motion_to_shoot_step` and continue them through `_build_ball_motion_sub_step` (`[ball_flight]` / `[bounce]`). `sync_lineup_coords_from_turn` writes final coords to `player.coords`. Overlay precedence is set in `TURN_COORDS_OVERLAY_KEYS` (rebounder maps applied first, get-back / release applied last — get-back / release win for the specific role-players they designate).

### DREB animates rebound capture only (backend step); outlet is a separate client beat

**Backend discrete `DREB` turn** (`result_type` / `current_turn` **`DREB`**, `animation_steps` from `dreb_step_emitter.py`): animates the rebounder moving to the ball at the bounce spot. Non-captor players normally hold their post-shot coordinates, except for backend-stamped failed rebound attemptors (see below), who collapse toward randomized near-bounce spots.

**Half-court outlet** (rebounder dribble / pass to outlet receiver per `dreb_outlet_pass`, teammates moving toward the new offense end — unit **`hco.lead_in.from_dreb_outlet`** in `turnAnimation.js` → `runDefensiveReboundSetup`) **is not** emitted as part of `dreb_step_emitter` steps. For discrete **DREB → HCO/HCT/FCP**, the client runs that setup **after** `AnimationEngine` finishes **`playTurn`** for the DREB row, using the **previous** MISS/BLOCK turn for **`dreb_outlet_pass`** and **`offense_getback`**. Skip when `DREB.next_play_type` is **FAST_BREAK** (fast break owns outlet) or when the shot turn has **`force_foul_after_dreb`**.

**Embedded DREB** (MISS/BLOCK turn still owns rebound, no separate `DREB` row — e.g. many **FREE_THROW** misses, unmigrated FCP / FB variants): outlet still runs from **`ShotAnimationSystem.handleDefensiveRebound`** → **`runDefensiveReboundSetup`** when `next_play_type` is **HCO/HCT/FCP** on that same shot turn. **Rebound!** headline rules (including idempotency with discrete rows): **`Announcement_System.md`**.

This replaces the earlier two-authorities-via-player-id-matching design, where the DREB step ran its own frontcourt-filter / random-near-bounce placement logic and tried to honor shot_manager's get-back / release maps via an exempt list. That coupling was brittle — any mismatch in the exempt set yanked role-players to the rim cluster. See [`UESS_System.md`](../00_General_Systems/UESS_System.md) and [`UESS_Backlog.md`](../projects/UESS_Backlog.md) for DREB emitter scoping.

### Near-bounce failed rebound attemptors

Missed **Fast Break** shots, missed **After-Steal Fast Break** shots, missed **OREB putback** attempts, and clean-miss **Dynamic HCT** shot attempts stamp a backend-authored failed-attemptor list for the rebound-capture step.

- **Helper:** `collect_near_bounce_rebound_attemptors()` in `BackEnd/utils/shared.py`.
- **Rule:** after the authoritative `bounce_spot` and actual `rebounderId` are known, scan both current lineups and include every non-captor player near the bounce spot. Default radius is **≤ 20** Euclidean grid units; Fast Break paths use **≤ 25** via `FAST_BREAK_REBOUND_GEO_DISTANCE`.
- **MISS/BLOCK turn contract (schema path):** when a migrated shot turn carries `ball_bounce_x/y` for the schema `[bounce]` step, it must also carry `rebounderId` and `rebound_type` on the same turn row so `game_manager` can promote a discrete **DREB** turn. `simulate_macro_turn` runs `_repair_miss_bounce_rebound_contract()` before append to restore those fields from `game_state.last_rebounder` / `last_rebound` when they were stripped in error (skipped for intentional `quarter_ends_after` terminal shots).
- **Orientation:** the helper uses display-oriented rebound math for away-offense cases, matching `determine_rebounder` bounce calculations.
- **Fast Break / After-Steal FB:** `shot_manager.py` and `after_steal_fast_break.py` apply shot-end coords while selecting the rebounder and collecting failed attemptors. They apply the pre-winner candidate filter at **25** Euclidean grid units so only players near the bounce are eligible unless both teams filter empty.
- **OREB putback miss:** `resolve_offensive_rebound()` applies the pre-winner candidate filter before resolving the second rebound, while preserving the existing putback-shooter 20% distance penalty.
- **Dynamic HCT:** `dynamic_hct_shot.py` applies the HCT shot-moment seed coords only while filtering candidates, selecting the rebounder, and collecting failed attemptors, then restores runtime `player.coords`. This keeps rebound winner selection and failed-attemptor animation in the same coordinate frame without changing global rebound helpers.
- **Payload:** the prior miss turn carries `offense_rebounders` and `defense_rebounders` as player IDs. `dreb_step_emitter.py` / `oreb_step_emitter.py` pass those through `rebound_attemptor_ids()`.
- **Animation:** the actual rebounder moves to the exact bounce spot. Failed attemptors move to backend-randomized nearby targets via `sample_rebound_collapse_target()` / `stamp_rebound_capture_player_motion()`, not to the exact ball spot.
- **Frontend contract:** the frontend does not choose rebound attemptors. It renders the backend `animation_steps` payload.

## Free Throw Miss Rebounds

When the **last** free throw is missed, rebound selection runs in `resolve_free_throw_logic` (`BackEnd/engine/phase_resolution.py`) after **`apply_coords_from_animations_list`** updates player `coords` from the FT lane / setup animation. Rebounding uses **`determine_rebounder`** in `BackEnd/utils/shared.py` with the same bounce spot as today (`calculate_bounce_spot` from the attacked basket).

### X-distance eligibility (FT only)

- **Constant:** `FREE_THROW_REBOUND_MAX_X_DELTA = 20` (x grid units) in `BackEnd/utils/shared.py`.
- **Rule:** Before scoring rebound candidates, the pool is filtered to players with **|coords.x − bounce_x| ≤ 20**. Players farther than **20** x-spots from the bounce (using coords at FT attempt time) are not in the first-pass candidate pool.
- **Y:** The gate uses **x only** for first-pass eligibility; final scoring still uses Euclidean distance to decide upper-half vs lower-half discount.
- **Fallback:** If no one on **either** team passes the filter, the engine logs a warning and runs **`determine_rebounder`** again on **full lineups** (no x gate) so a rebound is always assigned.
- **Scope:** Only **missed last FT** passes `max_x_delta_from_bounce` into `determine_rebounder`. HCO, fast break, and OREB putback-miss rebounds do **not** use this gate unless called with the same keyword explicitly in the future.

## Frontend — "Rebound!" headline (primary overlay)

When the rebounder **secures** the ball in animation, the client shows the primary **Rebound!** headline (portrait + team styling). Implementation details:

- **Helper:** `announceReboundHeadlineIfNeeded(scene, turnData, rebounderSprite, rebounderId)` in `FrontEnd/static/js/phaser/utils/announcements.js`.
- **Idempotency:** When callers pass the authoritative turn object (`turnData`), the helper sets `turnData._reboundHeadlineShown` after display so `ballManager.animateRebound`, embedded `ShotAnimationSystem.handleEmbeddedRebound`, final-FT `animateRebound`, `ReboundAnimationSystem`, and `announceGameEvent('REBOUND', ...)` cannot double-fire for the same turn.
- **Call sites:** `ballManager.js`, **`ShotAnimationSystem.js`** (embedded MISS/BLOCK rebound secure), **`FreeThrowAnimationSystem.js`**, `ReboundAnimationSystem.js`, `gameAnnouncements.js` (`REBOUND`). **Discrete `DREB` turn:** rebound headline may still fire on the embedded MISS path; **outlet** runs after **`AnimationEngine`** `playTurn` for the **`DREB`** row (`_maybeRunDiscreteDrebOutletLeadIn` → `runDefensiveReboundSetup`).

See `Announcement_System.md` for tiering, Block → Rebound ordering, and related flags (`_blockAnnounced`).

## OREB Putback Shot Defender

OREB putbacks assign the nearest defender using Euclidean distance from the rendered putback origin (the prior miss's bounce spot). Distance then scales that defender's actual shot impact through the shared HCO/OREB proximity curve.

### Defender Qualification
1. Measure every defender from the putback origin and assign the nearest defender.
2. At `≤3` grid units, apply the defender at full strength (`1.0`).
3. From `3–9`, linearly reduce defensive impact from `1.0` to `0.15`.
4. From `9–11`, retain the `0.15` residual contest.
5. Beyond `CONTEST_EUCLIDEAN_RADIUS=11`, retain the nearest-defender attribution but treat the shot as uncontested (`apply_defense=False`, factor `0.0`).

### Putback Resolution
- Contested putback (`≤11`):
  - use the same `inside` shot logic as a standard inside shot with no passer
  - the proximity factor scales defense at its source, so it also flows into contest classification, make probability, and defensive-foul evaluation
  - this includes standard make/miss thresholding and and-1 / 2 FT outcomes
- Uncontested putback:
  - Uses the **universal uncontested inside/attack make helper** (`BackEnd/utils/uncontested_shot.py`): `make_threshold = 99 + offense discipline − defense fight`; `roll = random.randint(1, 100)` → make if `roll < make_threshold` (geo-gated to distance ≤ 11 from basket; outside shots excluded). Falls back to `shot_score >= shot_threshold` when helper is ineligible.

## Rebound Stat Recording

### Standard Flow (HCO, Fast Break, Free Throw)
- Rebound stat (DREB/OREB) is recorded immediately after determining the rebounder
- Stat is recorded in the same function that creates the turn result
- Example: `shot_manager.py` records stat on line 900-901, then computes deltas using the same player object

### OREB Putback Miss Flow (Special Case)
**Problem:** When a putback misses and results in another rebound, the stat recording flow is split across two functions:
1. `resolve_offensive_rebound()` in `shared.py` (line 229) records the stat on the rebounder object returned by `determine_rebounder()`
2. `resolve_offensive_rebound_turn()` in `turn_manager.py` looks up the player again by ID (line 2454) for delta computation

**Solution:** `resolve_offensive_rebound()` records the rebound stat on the canonical roster player returned by ID lookup, then `resolve_offensive_rebound_turn()` preserves that same rebound data on the `PUTBACK_MISS` result for deltas and follow-on DREB/OREB animation.

**Implementation:**
- Stat recording: `BackEnd/utils/shared.py` (`resolve_offensive_rebound`) records on the canonical player instance.
- Payload preservation: `BackEnd/models/turn_manager.py` copies `rebound_type`, `rebounderId`, `ballSpot`, `offense_rebounders`, and `defense_rebounders` from the putback-miss rebound data onto the `PUTBACK_MISS` turn.
- This ensures stat deltas and the following discrete DREB/chained OREB animation read the same authoritative rebound result.

**Why This Matters:**
- Supports consecutive OREB scenarios: HCO miss => OREB => Putback Miss => OREB => Putback Miss => OREB => Putback Miss => DREB
- Each OREB is a separate turn, and each rebounder must have their stat properly recorded
- Stat deltas are computed by comparing current stats to `pre_stats` snapshot, so the stat must be on the same object instance used for delta computation

### OREB Kickout Animation

`OREB_KICKOUT` is schema-owned. The OREB turn itself only animates the rebound capture: the rebounder/captor moves to the bounce spot at `sprint`, eligible failed rebound attemptors collapse near the bounce spot, and everyone else holds.

The visible kickout setup/pass is prepended to the following HCO turn by `build_kickout_step` in `BackEnd/utils/transition_bridge.py`:

- **Sub-step A — outlet positioning:** current BH / OREB rebounder, the next HCO initiator/receiver, and the other eight players all move at the `cruise` archetype. The step advances when the slower of the BH or receiver reaches his outlet spot; non-gate players are interrupted at the point they can naturally reach.
- **Sub-step B — kickout pass:** passer and receiver are stationary for the pass; the other eight players continue toward setup spots at `cruise`. The step advances when the ball reaches the receiver.

Frontend kickout spot selection and legacy fallback pass behavior have been removed; the frontend renders backend `animation_steps` only.

### OREB clock burn

OREB turns are UESS-compliant (`oreb_step_emitter.py` → `animation_steps[]`). `_stamp_oreb_animation_steps` (`turn_manager.py`) realigns `time_elapsed` to the schema's total game-clock burn — same principle as HCO/FCP. The raw schema burn is small, so the master clock is floored per result type:

| Result type | `time_elapsed` | Why |
|---|---|---|
| `PUTBACK_MAKE` / `PUTBACK_MISS` | `max(OREB_PUTBACK_MIN_TIME_ELAPSED, round(burn))` | Self-contained shot attempt; nothing downstream absorbs the time. Raw burn is only ~1–2s (make `[hold]` beat is clock-paused, putback flight is short), so floor to the designed **2s** rebound-capture+putback cost. |
| `OREB_KICKOUT` | `round(burn)` (no floor) | Just the board-secure beat (~0–1s). The reset/bring-up time is burned by the **following HCO turn's** entry orchestrator (`build_kickout_step` in `transition_bridge.py`). Flooring here would double-count it. |

- **Constant:** `OREB_PUTBACK_MIN_TIME_ELAPSED = 2` (`BackEnd/constants/__init__.py`).
- **Putback vs kickout decision** (`resolve_offensive_rebound` in `shared.py`): scales with the **offense team's `aggression_call`** — aggressive **90/10**, normal **75/25**, passive **60/40** (putback/kickout). Roll `randint(1,100) ≤ putback%` → putback, else kickout. When **`time_remaining < 6`** (`should_force_oreb_putback`), always putback (no kickout) — applies universally, including late-clock OREB chains.
- **History:** putback floor was 3s through early 2026; lowered to **2s** for clock-driven EOQ so putback make/miss can drain the period. Kickout correctly stays at the raw burn.
- The legacy `_oreb_te = 3` assignments remain only because they still feed `oreb_hold_seconds` (consumed by the FE legacy animation path); the `time_elapsed` they set is overwritten by the realignment.

**Rebound Resolution Flow** (`calculate_bounce_spot`, `determine_rebounder`, `select_rebounder_by_score`, `calculate_rebound_score` — all in `BackEnd/utils/shared.py`)

1. **Calculate the missed-shot bounce spot** (`calculate_bounce_spot` → `_bounce_variance_for_shot_distance`). Variance widens with shot distance (Euclidean shooter→basket); x is always outward from the basket into the paint:
   - distance **&lt; 15**: x `randint(2, 6)`, y `±6`
   - **≤ 20**: x `randint(2, 8)`, y `±8`
   - **≤ 30**: x `randint(3, 14)`, y `±10`
   - **≤ 45**: x `randint(5, 22)`, y `±12`
   - **else** (deep heaves): x `randint(8, min(40, int(0.55·d)))`, y `±14`
   - no shooter spot → medium default `(2, 8, ±8)`. Bounce clamped to court bounds (x 0–100, y 0–50). See [Tunable_Constants.md](../11_Design_Systems/Tunable_Constants.md) Promotion Pass `BOUNCE_VAR_*`.
2. **Identify eligible rebounders** (per turn type — see the prefilter grid below). HCO removes get-back / release players; Fast Break paths use the frontcourt-half x filter plus the **25-grid** Euclidean near-bounce candidate filter; Dynamic HCT / OREB putback misses use the **20-grid** Euclidean near-bounce candidate filter; FT uses the `max_x_delta_from_bounce` x-gate.
3. **Identify upper-half rebounders** from that eligible pool:
   - Fast Break: upper half is Euclidean distance to bounce **≤ 12.5** (`0.5 × FAST_BREAK_REBOUND_GEO_DISTANCE`).
   - Dynamic HCT / OREB: upper half is Euclidean distance to bounce **≤ 10** (`0.5 × 20`).
   - HCO / Free Throw: upper half is Euclidean distance to bounce **≤ 12**.
4. **Set the lower-half discount:**
   - If at least **2** eligible players are in the upper half, lower-half discount is **0.7**.
   - Otherwise, lower-half discount is **0.95**.
5. **Score every eligible rebounder**:
   - `rebound_function = (RB×0.5 + ST×0.3 + IQ×0.1 + CH×0.1) × randint(1, 6)`
   - Upper-half player final score: `rebound_function + (team_chemistry × rebound_modifier)`
   - Lower-half player final score: `(rebound_function + (team_chemistry × rebound_modifier)) × lower_half_discount`
   - **Offensive-rebounder discount:** offensive players' final score is multiplied by **`OREB_REBOUND_SCORE_DISCOUNT` (0.8)** — modeling the defense's box-out / positioning edge on a miss (offense and defense were otherwise scored identically). Applied in `select_rebounder_by_score`; defense scores untouched. Tune against the week-aggregate **OREB%** (D1 target ~30%; `1.0` = legacy no-discount). Note: a 0.8 *score* discount is **not** a 20% *rate* reduction — the winner is a max-of-`d6` pick, so the OREB% effect is non-linear and tuned empirically.
   - Shooter / putback shooter penalty: after the score above is calculated, apply the existing **20% discount** (`× 0.8`) to the shooter or putback shooter if he is in the eligible pool.
6. **No eligible rebounder fallback:** if the eligible pool is empty, expand the Euclidean search radius by **5** until at least one rebounder is found. HCO / Free Throw fallback starts at **20**. Geo-gated paths start from their path radius, then expand by 5 from there.
   - Path-specific prefilters may define the first-pass candidate pool, but fallback pools must use the full active lineups for that turn context. Otherwise a strict prefilter (for example the Fast Break frontcourt-half x filter) can leave the expansion step with no players to recover.
7. **Determine the rebounder:** highest final score wins. If only one player is eligible, that player automatically gets the rebound.
8. **Tie breakers:** if multiple players tie for highest final score:
   - team with higher `rebound_modifier`
   - player with higher `MO`
   - team with higher `team_chemistry`
   - random among any remaining tied players


**Over The Back Fouls**
On each rebound attempt we calculate the possibility of Over The Back fouls via the following logic. OREB and DREB now resolve OTB in their own rebound turns, not in the preceding shot-attempt turn.

-Identify one potential fouling player from each team. 
    -use the rebounder from the rebounding team, and the player on the non-rebounding team who is closest to the rebounder using Euclidian distance
-If the closest player from the non-rebounding team is farther than 4 Euclidian distance from the rebounder, there is no Over The Back foul in play for either team
-Offense Threshold = 90 + offense team discipline value
-Defense Threshold = 10 - defense team discipline value
otb_foul = random.randint(1,100)
-if otb_foul > Offense Threshold, o foul is in play, elif otb_foul < Defense Threshold, d foul in play, else no foul

-if o foul or d foul in play
    - second_roll = random.randint(1,100)
    - if second_roll > potential fouling player's IQ from the in play foul team (offenssive potential fouler for o foul in play or defensive potential fouler for d foul in play), then foul_still_in_play = True, else foul_in_play = False
    -if foul_still_in_play = True, final_roll = random.randint(1,2), 1 = foul, 2 = no foul

-If there is an Over The Back foul called on the offense or the defense, it ends the rebound turn there and negates any putback attempt, kickout pass, DREB outlet, or fast-break continuation that would have followed. We process each like a standard non-shooting defensive foul or non-shooting offensive foul.
-DREB OTB visual order: animate the shot miss in the shot turn, animate players already placed for the rebound battle, move/attach the ball to the DREB rebounder in the DREB turn, then announce `"Over The Back!"` from the DREB step-end announcement and emit `turn_stop: FOUL`.
-Announcement copy: `"Over The Back!"` with the fouling player's image through the announcement system.

---

## Rebounder selection per turn type (current state)

Source-of-truth grid for which prefilter and rebounder-selection function each turn type uses. The regular Fast Break frontcourt-half x filter is implemented in `shot_manager.py`; Fast Break near-bounce filtering uses `FAST_BREAK_REBOUND_GEO_DISTANCE = 25`; the FT x-gate (`FREE_THROW_REBOUND_MAX_X_DELTA`) is implemented in `determine_rebounder`; the After-Steal FB pre-winner near-bounce candidate filter is implemented in `after_steal_fast_break.py` via `filter_rebound_candidate_lineups_near_bounce()`. Established as part of the SS&S animation refactor (see [`UESS_System.md`](../00_General_Systems/UESS_System.md)).

| Turn type | Prefilter | Rebounder selection |
|---|---|---|
| **HCO MISS** | Existing (`offense_rebounders` + `defense_rebounders` — excludes get-back / release) | `select_rebounder_by_score` across all eligible players |
| **Dynamic HCT MISS** | Shot-moment active lineups, first-pass filtered to 20 Euclidean grid units with 5-grid expansion fallback | `select_rebounder_by_score` across all eligible players |
| **Legacy HCT MISS** | All five offense + all five defense crash through `shot_manager`; path is being sunset | `select_rebounder_by_score` across all eligible players |
| **FCP MISS** | Same strategy-derived pool as HCO in current code | `select_rebounder_by_score` across all eligible players |
| **Fast Break MISS** | Frontcourt-half x-eligibility filter (home offense → x ≥ 50, away offense → x ≤ 50), then first-pass filtered to 25 Euclidean grid units with 5-grid expansion fallback | `select_rebounder_by_score` across all eligible players |
| **After-Steal Fast Break MISS** | Shot-end active lineups, first-pass filtered to 25 Euclidean grid units with 5-grid expansion fallback | `select_rebounder_by_score` across all eligible players |
| **Free Throw MISS** | `max_x_delta_from_bounce` (`FREE_THROW_REBOUND_MAX_X_DELTA`), then 20-grid Euclidean expansion fallback if no candidate passes | `select_rebounder_by_score` across all eligible players |
| **OREB putback MISS chained rebound** | Active lineups, first-pass filtered to 20 Euclidean grid units with 5-grid expansion fallback | `select_rebounder_by_score` across all eligible players |
| **defender_count == 0 edge case** | None (existing behavior preserved) | `select_rebounder_by_score` across all eligible players |

Notes:
- HCT / FCP do not currently share one unified prefilter. Treat the grid above as current code, not target design.
- HCO retains its existing prefilter — the get-back / release mechanic is HCO-specific.
- The near-bounce candidate filter is gameplay-side and position-key preserving. It is separate from `collect_near_bounce_rebound_attemptors()`, which is post-winner animation support.
- `select_rebounder_by_score` is the winner-selection primitive. It evaluates every eligible player in the caller-supplied pools, applies upper/lower-half scoring, applies the shooter/putback discount, then uses the documented tie breakers.

## Geo-Based Helper Applied

| Turn type | Pre-read | Animation read |
|---|---:|---:|
| HCO | No | No |
| Dynamic HCT | Yes | Yes |
| Steal FB | Yes | Yes |
| RR FB | Yes | Yes |
| CR FB | Yes | Yes |
| Triangle FB | Yes | Yes |
| OREB | Yes | Yes |
| Free Throw | No | No |

Notes:
- Fast Break paths use `FAST_BREAK_REBOUND_GEO_DISTANCE = 25` for both pre-winner candidate filtering and post-winner failed-attemptor animation.
- Dynamic HCT and OREB putback-miss paths use the default `NEAR_BOUNCE_REBOUND_ATTEMPTOR_DISTANCE = 20`.
- Free Throw misses use the FT-specific x-axis gate (`FREE_THROW_REBOUND_MAX_X_DELTA = 20`), not the Euclidean geo helper.
- UESS emitter sanity check: migrated Fast Break miss paths have backend emitters at the shot/miss point before downstream rebound animation. After-Steal FB uses `build_after_steal_fast_break_animation_steps`; RR FB uses `build_rim_runner_animation_steps`; Triangle FB uses `build_triangle_animation_steps`; CR FB uses `build_covert_release_animation_steps`. The rebound helper reads backend-owned shot-end coordinates, and the frontend only renders the emitted payload.
- Near-bounce failed-attemptor collapse (`stamp_rebound_capture_player_motion`) runs on **DREB / OREB capture**, not on the schema `[bounce]` step. Schema bounce continues rebounder overlay destinations from the shot turn.
