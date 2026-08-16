## End of Game System ✅ **COMPLETE** (January 2025; re-verified June 2026)

**Base Constants**

1. **Game Completion Trigger**: Backend marks a completed Q4 or overtime quarter as final when the score is not tied
2. **Completion Detection**: Backend response field `is_final === true`; the frontend must not recompute final-vs-overtime from scores
3. **Navigation Parameters**:
   - `gameId` - Game document ID
   - `mode` - Game mode: 'single', 'tournament', or 'franchise'
   - `tournamentId` - Tournament ID (for tournament mode only)
   - `franchiseId` - Franchise ID (for franchise mode only)
   - `teamId` - Team ID (ObjectId) for navigation anchor
   - `finalScore` - Final score object with homeTeam, awayTeam, homeScore, awayScore
4. **Command Center URLs**:
   - Tournament Mode: `/static/tournament.html?tournament_id={id}&team_id={id}`
   - Franchise Mode: `/static/franchise-command-center.html?franchise_id={id}&team_id={id}`
   - Single Game Mode: `/static/mode-select.html`
5. **Key Files**:
   - `FrontEnd/static/js/phaser/gameScene.js` - Renders backend final/quarter-break responses and calls completion popup when `is_final === true`
   - `FrontEnd/static/js/phaser/finalizeGame.js` - Tournament save-result; franchise **phase-a** at EOG (see split API below)
   - `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` - Creates completion popup; franchise phase B pending: starts **phase-b** in background when popup shows; PGPC vs locker CTA via **`FRANCHISE_PGPC_AT_EOG_ENABLED`** (`franchisePhaseBClient.js`); see `Press_Conference_System.md`
   - `FrontEnd/static/box-score.js` - Locker room navigation; franchise **phase-b** when week finish is pending
   - `FrontEnd/static/js/shared/pageLoadOverlay.js` - Full-page pulse overlay during **phase-b** (banner + copy/stat feed + green bar)
   - `BackEnd/api/franchise_routes.py` - `complete_week_phase_a`, `complete_week_phase_b`, monolithic `complete_week`
   - `BackEnd/api/api.py` - ObjectId serialization for tournament/franchise endpoints

**End of Game System Flow (6 Steps)**

1. **Game Completion Detection**: Game completes only when the backend returns `is_final === true` after Q4 or any overtime quarter
2. **Backend Game Finalization** (Franchise Mode — **split API**, April 2026): 
   - **Phase A (automatic at EOG):** `POST /franchise/complete-week/phase-a` with the same body as the historical monolith (`franchise_id`, `week`, `game_id`, `result`, optional `game_document`). Persists the **user** game: `games` / EOG / inbox / `franchise.results[week]` user row, sets `post_game_status.phase_a_user_week`. Idempotent if phase A already completed for that week.
   - **Phase B (user-triggered):** `POST /franchise/complete-week/phase-b` with **`{ franchise_id, week }` only**. Runs CPU games for the rest of the week, recruiting / rank-prestige / EOS side effects, week advance, and clears `post_game_status.phase_a_user_week`. Requires phase A done and non-empty `results[week]`; idempotent if franchise `week` already advanced past the request.
   - **Monolith (fallback / legacy):** `POST /franchise/complete-week` still runs user block + CPU + advance in one call; if phase A already persisted the week row, the user block is skipped (see `franchise_routes.py`).
   - Team id normalization, `stat_updater.finalize_game()`, and **team attribute updates** follow the same rules as before; see **Franchise post-game split (phase A / phase B)** below.
   - **Side effect (2026-06):** `finalize_game()` also commits the franchise owner's **career record** — W/L and the per-quarter **coaching archetypes** — to the `users` doc (`commit_user_game_record`), reading the game doc's archetypes before week cleanup deletes it. See [`00_General_Systems/Coaching_Archetype_System.md`](../00_General_Systems/Coaching_Archetype_System.md).
3. **Completion Popup Display**: Shows final score, "Box Score" button, and "Go To Locker Room" button with all navigation parameters
4. **Navigation Anchor Preservation**: Preserves complete navigation anchor set (mode, doc_id, team_id) for seamless return to command center
5. **Box Score Navigation**: User can navigate to Box Score page with all context parameters preserved (box score reflects updated team attributes)
6. **Command Center Navigation**: User can navigate to appropriate Command Center (Tournament, Franchise, or Mode Select) with complete navigation context

### Final-Turn Resolution Guardrail (February 2026)

EOQ clock-driven possession chains (Final Shot, FLSS, terminal DREB) are documented in [`EOQ_System.md`](EOQ_System.md).

- At `0:00`, EOG resolution now follows one consistent rule:
  - If free throws are pending, run the free throws first, then resolve to End of Game or Overtime based on the post-FT score.
  - If free throws are not pending, resolve directly to End of Game or Overtime (skip other in-turn interruption flows).
- This prevents final-turn edge cases from skipping score-impacting free throws and keeps quarter/final scoring consistent.

### Final vs Overtime Authority (May 2026)

The backend is the only authority for whether a completed period enters End of Game or advances to overtime. This follows the UESS migration rule that the frontend is a renderer, not a game-logic owner.

**Backend contract:**
- At quarter completion, `/api/simulate-turn` returns:
  - `quarter_complete: true`
  - `quarter`: the backend-ready next quarter number
  - `next_quarter`: same next-quarter value for explicit navigation
  - `is_final`: `true` only when Q4 or an overtime quarter completed with `home_score != away_score`
  - `home_score` / `away_score`: display/debug fields only for this decision
- The zero-clock early-return path returns the same final-navigation contract (`is_final`, `quarter`, `next_quarter`, scores), so edge responses do not fall back to frontend scoring logic.
- Full-quarter simulation uses the persisted game summary from `summarize_game_state()`, where `is_final` is true only when `game.quarter > 4` and the score is not tied.

**Frontend contract:**
- `gameScene.js` must finalize only when `lastTurnData.is_final === true`.
- If `quarter_complete === true` and `is_final !== true`, the frontend renders the next quarter/OT lineup break using backend `next_quarter` / `quarter`.
- The frontend must not decide End of Game vs OT by comparing `home_score` and `away_score`, checking `quarter === 4`, or deriving tie state locally.
- `bootGame.js` full-quarter flows must continue using `lastSummary.is_final === true` as the only game-complete signal.

**Desired period-completion behavior:**
- End of Q1-Q3: `is_final: false`, next quarter is Q2-Q4.
- End of Q4 with tied score: `is_final: false`, next quarter is OT1 (`quarter: 5`).
- End of Q4 with non-tied score: `is_final: true`, enter End of Game flow.
- End of any OT with tied score: `is_final: false`, next quarter is the next OT.
- End of any OT with non-tied score: `is_final: true`, enter End of Game flow.

**Team Attributes Update System**
Team attributes will adjust at the end of game based on the notes below. Note this will replace the team attribute decay we had coded into the Training System. For a side-by-side comparison with Training, see `docs/To Do/team_attributes_eog_vs_training_comparison.md`.
- Values are clamped to `TEAM_ATTR_CLAMPS` (`BackEnd/models/training_execution_v2.py`):
  - `shot_threshold`: −10 to 190 · `rebound_modifier`: 0.0 to 1.0 · `team_chemistry`: 7 to 25 · `momentum_score`: -10 to 10
  - core 8 (`discipline`, `fight`, `offensive_efficiency`, `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`, `fb_opp_modifier`, `pt_opp_modifier`): **-20 to 20** (widened from ±10 in the Structural Pass)
- **Band selection lives in `BackEnd/eog_attr_rules.py`** — the SINGLE implementation `calculate_attr_changes` calls. All thresholds, band ranges, and label strings are named constants in **`BackEnd/constants/eog_attr_bands.py`**.

  **LEVELING PASS (2026-08-11) — these values are MEASURED, not provisional.** Thresholds were re-cut at the measured p33/p67 of each input over 3,328 team-games so the reward band means something again, and midpoints were tuned so combined drift (EOG + training) lands slightly positive. Verify any change with `scripts/eog_band_tuner.py` — it recomputes expected drift offline from a season log in seconds. **Do not re-run a 2-hour season to evaluate a band change.**

  End-of-game adjustments (each team, from the finished-game snapshot):
  - `shot_threshold` (golf score, lower better; band IDs still say 50/45 — they are instrumentation labels, not thresholds): FG% > **45** → `-6..-2`; FG% > **40** winner `-1..0` / loser `0..+1`; FG% ≤ **40** → `+2..+6`. ⚠️ **INTERIM, AND SCALE-COUPLED** — these cuts are valid only for the current window (-10..190, init 85-95). **Every `MIN` change requires a band re-cut**. **Re-cut 2026-08-15 from 22/37** against a measured league FG% of **45.16**: the old cuts sat at the 18th and **0.2nd** percentiles, so the penalty branch caught 8 team-games out of 4,220 and was dead. Shipped alongside the training hold-rung fix — see `04_Franchise_Mode_Systems/Team_Attribute_System.md` § The 1-point rung. Procedure: `00_Operations/Shot_Threshold_Scale_Tuning.md` § Re-cutting the EOG bands.
  - `discipline`: team `(F+TO)` vs opponent `(F+TO)+8` → below `+1..+2` / above `-3..-1` / equal `-1..0`.
  - `fight`: winner `0..+2` / loser `-2..0`. **Structurally nets zero** across the league — every game has exactly one winner — so `fight`'s season drift is entirely training-driven.
  - `rebound_modifier` (**5-band ladder**, deltas in cents /100; asymmetric on purpose — rebound differential is zero-sum, so symmetric bands net zero drift). **NARROWED 2026-08-14** — the old ranges reached ±0.14 in a single game against training's ~0.04 per WEEK, so EOG dominated and a short rebounding run crossed half the 0.0-1.0 scale; measured across two seasons, **28-31 teams sat at exactly 1.0 and 17-30 at exactly 0.0** (~40% of the league railed, after which the attribute carries no information). Max single-game swing is now **0.10**.

    | differential | band | delta |
    |---|---|---|
    | ≥ **+14** | `reb_dominant` | `+0.05 .. +0.10` |
    | **+7 .. +13** | `reb_strong` | `+0.01 .. +0.05` |
    | **-3 .. +6** | `reb_even` | `-0.03 .. +0.03` |
    | **-13 .. -4** | `reb_weak` | `-0.08 .. -0.04` |
    | ≤ **-14** | `reb_dominated` | `-0.12 .. -0.08` |

    Margins (`REBOUND_BIG/MID/EVEN_MARGIN` = 14/7/3) were widened from 8/4/3 because **65.5% of team-games landed in the two extreme bands**, so the tails dominated the drift.

    **Labels are deliberately threshold-free.** The previous set (`outrebound_gt_8`, `outrebound_4_7` …) baked margins into the names and then went stale — `outrebound_gt_8` was firing at a differential of **14**, not 8. Same failure as `fg_gt_50` firing at 40% FG. The margins are meant to be re-tuned; the names must survive it. `scripts/eog_band_tuner.py` carries `REBOUND_LABEL_ALIASES` so pre-rename season logs still parse.

    ⚠️ **The ladder now leans NEGATIVE.** The penalty bands widened downward while the reward bands narrowed, moving expected drift from `-0.004`/game (`-0.12`/season) to `-0.0136`/game (`-0.355`/season) at measured band frequencies. Training contributes roughly `+0.40`/season, so net is about `+0.04`/season from a 0.5 init — close to neutral, but the docstring's "asymmetric so it does not net zero" now leans the other way. Re-check after a season.

    ⚠️ **The training side is calibrated around a bug — do not "fix" it casually.** `_apply_rebound_modifier_training` is called TWICE per week, once from `technical_drills.rebounding` and once from `scrimmages`. **80% of team-weeks have `scrimmages = 0`**, and that path still fires with 0 effective points, hitting the `<1` band for **-0.04 every week**. That phantom penalty is currently load-bearing: summing the two sources into one application (the apparent fix) *raises* season drift by **+0.61**, taking the league to ~1.15 on a 1.0 scale. If that is ever corrected, the training bands must be re-cut in the same pass.
  - `offensive_efficiency` (**concentration** = largest play's share of offensive possessions): `≤0.23` → `0..+2`; `≤0.30` → `-1..+1`; `>0.30` → `-2..-1`. Zero possessions = **data-integrity** (log, no change) — every game has offense, so zero means broken data, not a choice. ⚠️ **INTERIM** — cut against a distribution the playbook generator caps (20% ceiling per set play at 4+ plays); lifting that cap invalidates these.
  - `defensive_efficiency` (max share of HCO defense `used`): `≤0.42` → `0..+2`; `≤0.57` → `-1..+1`; `>0.57` → `-2..-1`. Zero defensive possessions = **data-integrity**.
  - `fb_efficiency` (**concentration** over CR / RR / Triangle — `after_steal` excluded as a forced, non-strategic event): `≤0.44` → `0..+2`; `≤0.53` → `-1..+1`; `>0.53` → `-2..-1`. Zero fast-break volume → **atrophy** `-1..0` (a coaching choice).
  - `pt_efficiency` (**concentration** over the 4 press/trap plays = 3 HCT variant `A` counts + `fcp_used`): `≤0.50` → `0..+2`; `≤0.70` → `-1..+1`; `>0.70` → `-2..-1`. Zero P/T volume → **atrophy** `-1..0`. NOTE: `fcp_press_plays[*].A` is a **dead counter** (never incremented); `fcp_used` stands in for the single live FCP variant — revisit when FCP variants expand.
  - `fb_opp_modifier` (opponent fast-break **volume**, `after_steal` excluded; healthy **7-13**): `0` → atrophy `-1..0`; `<7` under `-1..0`; `7-13` healthy `0..+1`; `>13` over `-1..0`.
  - `pt_opp_modifier` (opponent press/trap **volume** = `hct_used + fcp_used`; healthy **9-20**): `0` → atrophy `-1..0`; `<9` under `-1..0`; `9-20` healthy `0..+1`; `>20` over `-1..0`.
    **Why 9-20 and not 7-14:** with CPU identity live, opponent pressure volume is strongly **BIMODAL** — press-vision teams generate a median of **15** pressure possessions, everyone else **4-6**, a 3.0x separation with press p10 = 9. The old 7-14 band sat in the valley *between* the two modes and scored **53.7% of press games as overuse**, penalising commitment. 9-20 makes the healthy band mean "you faced a real press", which is what an opponent-pressure modifier should reward.
  - `team_chemistry` (**rank-driven** — lower `natl_rank` int is better. `winner_score` / `loser_score` are **DEAD parameters**, a fossil of the old score-margin design; margin is NOT used):
    - winner: opponent worse-ranked → `0..+2`; opponent top-10 → `+2..+5`; else → `+1..+3`.
    - loser: lost to better-ranked top-10 → `0..+1`; lost to better-ranked non-top-10 → `-1..+1`; lost to rank 100-128 → `-4..-2`; else → `-2..-1`.
    - Lifted across the board because **all 128 teams hit the 7 floor by week 2** on an 18-point range. Losing to a stronger team no longer costs chemistry outright; only losing to a much weaker one does.

  **⚠️ `shot_threshold` is the one attribute whose band INPUT it also DETERMINES.** It is the bar a shot must clear, so it sets team FG%, and FG% selects the band that moves it. **That loop is intended** — it is the compounding effect of game performance — so the band is not a defect and must not be removed or inverted. The fault it originally had was magnitude: at ±85/season on a 200-point range it saturated inside a season (**123 of 128 teams railed at the ceiling**). It is therefore tuned to a **VARIANCE target**, not a mean one: near-neutral centre, spread that grows, few teams railing. For the current **-10..190** scale from init 85-95, 1,000 modeled seasons using the measured 3,330-row FG% residual distribution and actual integer band rolls produced mean 90.0, sd 20.5, drift **-0.05**, and **zero rails across 128,000 team-seasons**. ⚠️ **That model did not survive contact with a real season.** Measured on prod: the league ended at mean **59.5**, not 90 — EOG **−87.7**/team-season against training **+57.2**, net −30.5. Both halves are now read from persisted records rather than modeled; see `04_Franchise_Mode_Systems/Team_Attribute_System.md` § The 1-point rung.
    **The equilibrium FG% is SEASON-SPECIFIC — re-derive before re-cutting and never reuse a previous fit.** Per-season slopes of `FG% = a + b*shot_threshold` measured **-0.1125 / -0.0691 / -0.1413** with non-overlapping 95% CIs, and the LEVEL shifts too (mean cross-season spread 6.42pp). Pooling seasons produces a chord between clouds at different equilibria, not a response curve. See `00_Operations/Shot_Threshold_Scale_Tuning.md`.

  - All games use the scouting/usage-driven efficiency rules; the former lightweight-sim override has been removed.
  - `team_chemistry` (**rank-driven** — lower `natl_rank` int is better. `winner_score` / `loser_score` are **DEAD parameters**, a fossil of the old score-margin design; margin is NOT used):
    - winner: opponent worse-ranked → `0..+1`; opponent top-10 → `+2..+4`; else → `+1..+2`.
    - loser: lost to better-ranked top-10 → `-1..0`; lost to better-ranked non-top-10 → `-2..0`; lost to rank 100-128 → `-5..-3`; else → `-3..-2`.
- **Offensive play CMD (effectiveness) decay — franchise FTD only:**
  - After the team-attribute `calculate_attr_changes` pass, `update_team_attributes_after_game()` applies **separate** updates to **`franchise_team_data.plays.<storage_key>.effectiveness`** for each team (same EOG entry point as FTD `team_attributes`).
  - For each offensive play row in the finished-game snapshot (`iter_team_plays` over `teams[team_id].plays`), let `times_run` be that play’s `game_stats.times_run`, `successes` that play’s `game_stats.successes`, and `T` the sum of `times_run` over all those plays for that team in that game.
  - Let **`usage_int` = `int(100.0 * times_run / T)`** when **`T > 0`** and **`times_run > 0`**, else **0**. Let **`success_rate_pct` = `(successes / times_run) * 100`** when **`times_run > 0`**, else **0**.
  - Decay points = **`usage_int`** only when **`4 * usage_int < success_rate_pct`**; otherwise decay is **0**. If **`T == 0`** or a play has **`times_run == 0`**, that play’s decay is **0**.
  - New effectiveness = **`max(0, current_ftd_effectiveness - decay)`**; only keys that change are `$set` on FTD.
  - **Implementation:** `build_eog_offensive_play_effectiveness_decay_ftd_updates()` in `BackEnd/models/training_execution_v2.py`; persistence in `BackEnd/api/franchise_routes.py` immediately after home/away attribute changes are computed.
  - **Not** applied when postseason EOG freezes team-attribute updates (weeks 27–34): that early return skips the whole `update_team_attributes_after_game` body, including this decay.
  - **Training:** Offensive play effectiveness is **no longer** reduced by random 5–15 at the start of training; see `Training_System.md`.
- **Defensive scouting effectiveness decay — franchise FTD only (same EOG pass):**
  - `update_team_attributes_after_game()` also applies updates to **`franchise_team_data.scouting_data.defense.<row>.effectiveness`** using each finished-game defense row’s **`game_stats.used`** (and **`T`** = sum of `used` over `teams[team_id].scouting.defense` for that team). Decay = **`int(100.0 * used / T)`** when **`T > 0`**, else **0**; new effectiveness = **`max(0, current - decay)`**.
  - **Implementation:** `build_eog_defensive_effectiveness_decay_ftd_updates()` in `BackEnd/models/training_execution_v2.py`; persistence in `BackEnd/api/franchise_routes.py` alongside offensive play decay. Pre-training random defense decay was removed from `execute_training`.
- **Data Sources:**
  - Team totals (F, TO, FG%, TREB) come from the canonical finished-game snapshot built for EOG and box score display.
  - Offensive play decay reads `teams[team_id].plays[*].game_stats.times_run` and **`successes`** (same snapshot as usage totals).
  - Defensive play usage reads the completed game's `teams[team_id].scouting.defense` usage counts.
  - Fast break play usage reads the completed game's `teams[team_id].scouting.offense.fast_break_plays[*].A`.
  - Press/trap totals read the same HCT/FCP usage fields shown in the box score's Special Situations section.


**Long Form Documentation**

### Overview

The End of Game System handles game completion, displays final scores, and provides navigation to the Box Score page and appropriate Command Center (Tournament, Franchise, or Mode Select for Single Game).

### Player Momentum Reset (June 2026)

When a game is detected final, **every player's MO (momentum) is reset to 0** on both teams (active + bench) before the final save, so no in-game momentum persists past the game. Fires at the live `is_final` detection in `BackEnd/api/api.py` (both the quarter-complete turn path and the already-over early-return). Code: `reset_all_player_momentum()` in `BackEnd/utils/player_momentum.py`. See `Player_Momentum_System.md` for the full momentum system.

### Game Completion Flow

**Trigger:**
- Game completes when the backend returns `is_final === true` after a completed Q4 or overtime quarter.
- Tied completed Q4/OT periods are not final; the backend returns `is_final: false` and the next quarter/OT number.
- `gameScene.js` renders that response; it does not compare scores or derive overtime locally.

**Completion Popup:**
- **Location:** `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`
- **Display:** Shows final score; franchise + phase B pending: **no Box Score on this popup**, CTA **Post-Game Press Conference** (opens PGPC modal; **phase-b** already started when this popup appeared, then FCC). Otherwise **Box Score** + **Go To Locker Room** (or tournament/single variants).
- **Parameters Passed:**
  - `gameId` - Game document ID
  - `mode` - Game mode: 'single', 'tournament', or 'franchise'
  - `tournamentId` - Tournament ID (for tournament mode only)
  - `franchiseId` - Franchise ID (for franchise mode only)
  - `teamId` - Team ID (ObjectId) for navigation anchor
  - `finalScore` - Final score object with homeTeam, awayTeam, homeScore, awayScore

### Navigation Anchor Preservation (SS&S - January 2025)

**✅ Complete Navigation Anchor Set:** When a game completes, the completion popup preserves all three navigation parameters:
1. **`mode`** (franchise/tournament/single) - Which collection/endpoints to use
2. **`doc_id`** (franchise_id/tournament_id) - Which document within that collection
3. **`team_id`** (ObjectId string) - Which team within that document (user's team)

**Implementation Flow:**
- **`bootGame.js`:** Reads `team_id` from URL params (or `home_id`/`away_id` fallback), passes to game scene via `sceneData`
- **`gameScene.js`:** Stores `teamId` from scene data, passes it to completion popup when game ends
- **`gameCompletionPopup.js`:** Constructs command center URLs with complete navigation anchor set:
  ```javascript
  // Tournament mode example
  const params = new URLSearchParams();
  if (tournamentId) params.set('tournament_id', tournamentId);
  if (teamId) params.set('team_id', teamId);  // ✅ Preserve navigation anchor
  lockerRoomUrl = `/static/tournament.html?${params.toString()}`;
  ```

**Benefits:**
- **No Fallback Needed:** Prevents fallback to `/tournament/active?user_team_id=...` which requires ObjectId serialization
- **Complete Context:** All three navigation parameters preserved for seamless return to command center
- **Consistent Pattern:** Matches navigation anchor preservation pattern used throughout the application

### Box Score Navigation

**Box Score URL Construction:**
- **Location:** `gameCompletionPopup.js` (lines 59-64)
- **Parameters Included:**
  - `game_id` - Game document ID
  - `home` - Home team name
  - `away` - Away team name
  - **✅ SS&S (January 2025):** Also includes `mode`, `tournament_id`, `franchise_id`, and `team_id` for proper navigation from Box Score page

**Box Score primary action (Back to Locker Room / Go To Locker Room when phase B pending from EOG):**
- **Location:** `FrontEnd/static/box-score.js` - `setupLockerRoomButton()` function
- **Navigation Logic (Priority Order):**
  1. **Mode Parameter (Highest Priority):** If `mode` is set in URL params, use it directly
  2. **ID Parameters:** Check for `tournament_id` or `franchise_id` in URL params
  3. **LocalStorage (Last Resort):** Only check localStorage if URL params are not available (for backward compatibility)
- **Command Center URLs:**
  - **Tournament Mode:** `/static/tournament.html?tournament_id={id}&team_id={id}`
  - **Franchise Mode:** `/static/franchise-command-center.html?franchise_id={id}&team_id={id}`
  - **Single Game Mode:** `/static/mode-select.html`

**Key Fix (January 2025):**
- Box Score page now receives `mode`, `tournament_id`, `franchise_id`, and `team_id` in URL params
- Navigation logic prioritizes URL parameters over localStorage to prevent stale data issues
- Franchise mode uses correct path: `/static/franchise-command-center.html` (not `/franchise/command-center`)

### Franchise post-game split (phase A / phase B) — April 2026

Canonical franchise week completion is a **two-step HTTP flow** so the user’s game and box score are safe before CPU games run. Deeper design notes and inventory live in `docs/To Do/Post_Game_Split.md`.

**Phase A — `POST /franchise/complete-week/phase-a`**

- **Body:** Same as `CompleteWeekRequest`: `franchise_id`, `week`, `result` (`team1_id`, `team2_id`, `team1_score`, `team2_score`), optional `game_id`, optional `game_document`.
- **Behavior:** Runs the shared user-game pipeline (`_complete_week_process_user_game_block`), merges the user row into `franchise.results[str(week)]`, persists `season_inbox`, sets `post_game_status.phase_a_user_week` to `week`.
- **Game doc + stat rollup (Jun 2026):** When `game_document` is supplied, phase A persists it through **`_persist_franchise_user_game_snapshot`** — canonical games `_id` via `resolve_game_write_id`, purge of string/ObjectId duplicate docs, and deletion of other week/matchup game rows for that franchise. Then **`stat_updater.finalize_game()`** rolls box-score stats into FPD `season`/`career`. Idempotency uses **`franchises.applied_games`** (per game `_id`) **and** **`franchises.applied_matchups`** (per franchise-week matchup) so the same played game cannot inflate season stats twice. See **`Box_Score_System.md` §5** for the box-score vs FCC Player/Team Stats display split.
  - **Perf — batched FPD writes (2026-07-22):** `finalize_game`'s per-player FPD stat updates are issued as a **single `bulk_write(ordered=False)`** over disjoint `(franchise_id, player_id)` docs (identical `$inc`/`$set` semantics to the old per-player `update_one` loop). This collapses ~24 sequential acknowledged writes/game to one — it was the dominant cost of a full turn-by-turn **CPU week** (`finalize_game` ~1.3 s/game × 63 ≈ 82 s, ~89% of per-game persistence). The same `finalize_game` runs for the user game (phase A) and every CPU game (phase B / week loop), so both benefit. Full analysis + remaining parallelization work: **`../projects/Sim_Perf_Capstone.md` § CPU-week EOG persistence** (and the Tier-3 plan doc).
- **Response (success):** `{ status, phase: "a", idempotent, week, results_count }`. If phase A already completed for that week, returns **`idempotent: true`** without re-running side effects.
- **Frontend:** `finalizeGame.js` shows **“Saving game…”**, POSTs phase-a when `canCompleteWeek` (franchise, no tournament, valid `week`). On success, writes `localStorage.franchise_complete_week_pending` as `JSON.stringify({ franchise_id, week })` and passes `franchisePhaseBPending` / `franchisePhaseAOk` into `finalScore` for the EOG popup.

**Start CPU sims — `POST /franchise/complete-week/start-cpu-sims`** (May 2026)

- **Body:** `{ franchise_id, week }`.
- **Behavior:** Sims **non-user** week games only; persists **`results[week]`** (and EOS tournament blobs on EOS weeks). Does **not** advance franchise `week` or run week-closure aggregates. **409** if phase A already completed for that week (use phase B).
- **Frontend:** `bootGame.js` calls **`getOrStartFranchiseStartCpuSims`** (`franchiseStartCpuSimsClient.js`, single-flight, non-fatal errors) when franchise **pre-game (`quarter === 0`)** starts via **Play Quarter**, **Sim Quarter**, or **Sim Full Game**, so CPU games can run in parallel while the user plays.

**Phase B — `POST /franchise/complete-week/phase-b`**

- **Body:** `CompleteWeekPhaseBRequest`: **`franchise_id`**, **`week`** only.
- **Preconditions:** Let `current_week` be the franchise doc’s `week`. If **`current_week > req.week`**, the week already advanced — returns **200** with **`idempotent: true`** (no-op). If **`current_week < req.week`**, **400**. If **`current_week == req.week`**, phase A must be done and `results[week]` must be a non-empty list; otherwise **409** (run phase-a or use the monolith).
- **Behavior:** Loads saved week results from DB, runs `_complete_week_finish_cpu_and_persist` (CPU sims, recruiting, rank/prestige, EOS, week advance). Full turn-based CPU games (`run_simulation`) may run **in parallel** inside one phase-b request (`ThreadPoolExecutor`; optional env **`FRANCHISE_CPU_SIM_MAX_WORKERS`**, default **4**). Clears `post_game_status.phase_a_user_week` on successful persist.
- **Response:** Extends the usual complete-week payload with `status`, `phase: "b"`, `idempotent`.
- **Frontend triggers:**
  - EOG popup: **`getOrStartFranchisePhaseB`** runs when the franchise completion modal is shown (`gameCompletionPopup.js`). **Franchise EOG primary CTA:** controlled by **`FRANCHISE_PGPC_AT_EOG_ENABLED`** in `gameCompletionPopup.js`. When **`false`** (current default), the popup shows **Box Score** + **Go To Locker Room**; **Go To Locker Room** dismisses the modal, shows the same **`PageLoadOverlay`** pulse as box-score (“Simulating Computer Games”), **awaits** the same phase-b Promise, then clears pending `localStorage` and navigates to the FCC (no extra click). The phase-b pulse may include a rotating completed-game player-stat feed below the team banner, sourced from the completed game's `box_score`. When **`true`**, the legacy **Post-Game Press Conference** button is shown and **`postGamePressConference.js`** attaches to the same phase-b Promise (PGPC code paths remain in the repo). Box-score entry with `post_game_phase_b=1` uses the **Go To Locker Room** label for the phase-b finish action (see below).
  - Box score: **Back to Locker Room** or **Go To Locker Room** (phase-b pending from EOG; see below) — same POST and overlay when pending matches URL `franchise_id`. Legacy pending shape `{ body: full CompleteWeekRequest }` still POSTs monolithic **`/franchise/complete-week`**.

**Monolith — `POST /franchise/complete-week`**

- **Body:** Same as phase A. Runs user block then `_complete_week_finish_cpu_and_persist` unless phase A already persisted `results[week]` (user block skipped to avoid double finalize / GP).
- **Use:** Escape hatch for old clients or the box-score legacy pending `{ body }` path.

**Box score URL flag (`post_game_phase_b=1`)**

- When the EOG popup builds the **Box Score** link and phase B is pending, it appends **`post_game_phase_b=1`**.
- `box-score.js` shows **Go To Locker Room** (same phase-b + overlay behavior as the historical “Sim Computer Games” control) only if that flag is present **and** `localStorage.franchise_complete_week_pending` exists **and** `franchise_id` matches the URL. All other entry paths keep **Back to Locker Room**; phase-b wiring when pending is unchanged.

**Phase-B pulse player-stat feed**

- Scope: franchise **phase-b pulse only**. It is not used by tournament result saving, generic page loading, or normal “Saving game…” statuses.
- Sources:
  - EOG popup path: `gameScene.js` passes the resolved final game snapshot into `showGameCompletionPopup()`; `gameCompletionPopup.js` uses that resolved doc for the pulse feed.
  - Box Score path: `box-score.js` uses the already-loaded `gameData`.
- Feed builder: `PageLoadOverlay.buildPostgameStatFeed(gameDoc, { userTeamSide })`. Feed entries include the stat line and the player's team context.
- Ordering: user team first, opponent second; within each team, players are sorted by points scored descending, then minutes played descending when points are tied.
- Eligibility: only players with more than 0 displayed minutes are included (`MIN` seconds floored to whole minutes).
- Line format: `{Player Name} (#{jersey}): {points} points, {non-zero TREB/AST/STL/BLK}, {minutes} minutes played, DEF: {defPct}%`.
- Rebounds use **TREB = DREB + OREB**. Points are always shown, including `0 points`; all other zero stats are omitted.
- DEF uses `DEF_S / DEF_A * 100`, rounded to a whole percent; players with no defensive attempts show `DEF: -`.
- Rotation: one player line is shown at a time for 8 seconds while phase B is pending.
- Banner behavior: the team banner follows the currently displayed player. User-team player lines show the user team banner; opponent player lines show the opponent team banner; when the feed loops, the banner switches back with the line.

### Franchise complete-week team id resolution (February 2026)

- **Endpoints:** Team ids in `result` apply to **phase-a** and the **monolith** the same way. **Phase-b** does not send `result`; the server uses the saved week row and schedule.
- **Frontend week resolution:** `finalizeGame()` resolves `week` in this order **before posting phase-a**:
  1. `window.location.search`
  2. `localStorage.franchise_week`
  3. `simData.week`
  4. `simData.final_game_document.week`
  5. backend franchise state fallback via `/franchise/command-center/data`, then `/franchise/state`
- **Reason for backend fallback:** Prevent intermittent franchise EOG failures where command-center navigation context is incomplete at game end; if local/frontend week sources are missing, the finalizer recovers the authoritative current franchise week instead of silently skipping franchise completion.
- **Team ids:** Backend normalizes `result.team1_id` and `result.team2_id` via `_normalize_team_id()` in `BackEnd/api/franchise_routes.py`:
  1. If the value is a valid ObjectId string, it is returned.
  2. Else lookup in universal `teams` by `_id`, `name`, or `code`; if found, return that document’s `_id`.
  3. **Canonical fallback:** If still not found and the value contains an underscore (e.g. `FOUR_CORNERS`), convert to a name by replacing `_` with space and title-casing (e.g. `"Four Corners"`), then lookup by `name`; if found, return that document’s `_id`.
- This allows the frontend to send either ObjectIds (e.g. from URL params) or canonical keys from the game doc (e.g. when Play Quarter completes and URL params are missing). Sim Quarter, Sim Full Game, and Play Quarter all use the same flow; only the value sent for team ids can differ.

### Backend ObjectId Serialization

- **`/tournament/active` endpoint:** Now serializes all ObjectIds in nested structures using `jsonable_encoder(doc, custom_encoder={ObjectId: str})`
- **Consistent with `/tournament/state`:** Both endpoints use the same serialization pattern
- **Prevents 500 Errors:** Ensures nested ObjectIds (e.g., in `teams` collection) are properly serialized for JSON response

### Games Collection Structure

**Game Document Storage:**
- Game documents are stored in the `games` collection (standalone documents, not nested in franchise/tournament documents)
- **Team Identification Fields:** Game documents use `home_team_id` and `away_team_id` fields (team_id strings like "XAVIEN"), NOT `team1_id` / `team2_id`
- **Teams Object:** The `teams` object is keyed by `team_id` strings (e.g., `teams["XAVIEN"]`), matching the `home_team_id` / `away_team_id` values
- **Plays Data:** Plays data with `game_stats` (times_run, successes) is stored in `teams[team_id]["plays"]`

**Key Fix (January 2025):**
- Scouting report queries were updated to use `home_team_id` / `away_team_id` fields instead of non-existent `team1_id` / `team2_id` fields
- Queries now match against `team_id` strings (like "XAVIEN") instead of ObjectId strings

**Reference:** See `../00_Data_Systems/Games_Collection.md` for complete games collection documentation.

### Key Files

- **`FrontEnd/static/js/phaser/gameScene.js`** - Renders backend final/quarter-break responses and calls completion popup when `is_final === true`
- **`FrontEnd/static/js/phaser/finalizeGame.js`** - Franchise EOG: **phase-a**; builds `finalScore` with phase B pending for popup
- **`FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`** - Completion popup; kicks off **`getOrStartFranchisePhaseB`** when franchise + phase B pending; **`FRANCHISE_PGPC_AT_EOG_ENABLED`** toggles PGPC vs Box Score + locker on franchise EOG; `post_game_phase_b` on box-score link when pending
- **`FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js`** - Single-flight `POST …/phase-b` Promise per franchise week (EOG + PGPC share)
- **`FrontEnd/static/js/phaser/utils/postGamePressConference.js`** - PGPC modal; attaches to shared phase-b Promise + `press_conference_sessions` API
- **`FrontEnd/static/box-score.js`** - **phase-b** when `franchise_complete_week_pending` matches; label branching per `post_game_phase_b`
- **`FrontEnd/static/js/shared/pageLoadOverlay.js`** - Pulse overlay during phase-b, including optional rotating player-stat feed
- **`BackEnd/api/franchise_routes.py`** - `complete_week_phase_a`, `complete_week_phase_b`, `complete_week`, `_complete_week_finish_cpu_and_persist`
- **`BackEnd/api/api.py`** - ObjectId serialization for tournament/franchise endpoints

### EOG Data Source & Access Method

- **Design goal:** EOG team-attribute calculations must read from one frozen per-game snapshot.
- **Canonical snapshot field:** `games.eog_inputs`
- **Built from:**
  - `teams[team_id].scouting` for FB/HCT/FCP rates and attempts
  - `team_totals` for box-score totals (`FGM/FGA`, `TO/STL`, `DREB/OREB`)
  - fallback to aggregated `box_score` only if `team_totals` is missing
- **CPU games:** Full CPU games persist the same engine-derived totals and scouting inputs used by the normal EOG formulas.
- **Backend access point:** `BackEnd/api/franchise_routes.py` → `update_team_attributes_after_game()` (FTD `team_attributes` deltas, FTD offensive **`plays.*.effectiveness`** decay when **`4 * usage_int < success_rate_pct`** (see **Offensive play CMD** above), and FTD **`scouting_data.defense.*.effectiveness`** decay from defensive `used` share; see **Defensive scouting effectiveness** above).
- **Processing rule:** Build and persist `eog_inputs` once, then compute all EOG attribute changes from `eog_inputs` only.
- **Postgame display rule:** Box Score "Special Situations" (Fast Breaks, HC Traps, FC Presses) should read from `eog_inputs.*.scouting` so displayed rates match EOG calculations exactly.
- **Why this method:** Prevents source drift between `team_stats`, `teams.scouting`, and totals; keeps EOG deltas deterministic and aligned to final game state.

### Postseason Team Attribute Freeze

- **Franchise weeks 27-34:** EOG team attribute changes are frozen for EOS tournament games.
- **Persistence rule:** The game doc still receives `team_attribute_changes: {}` for box score compatibility, but franchise team-data attributes are not mutated.
- **Scope:** Game results, stats, inbox entries, and tournament bracket advancement still persist normally. In-game NG effects may still change live game state during play; the frozen values are the postgame anchor team attributes.
- **Reversibility:** The freeze is controlled by a centralized postseason policy in `BackEnd/api/franchise_routes.py` so future postseason EOG team attribute changes can be re-enabled without rewriting the EOG formulas.

### EOG Persistence Guardrails (February 2026)

- **Issue observed:** EOG logs showed `totals_source=none` and zero team totals/scouting during `complete-week`, causing incorrect deltas (for example PT/FB opponent modifiers and discipline).
- **Root cause:** Mixed game `_id` handling in franchise flow could create/read two docs for the same game:
  - canonical gameplay doc with `_id` as **string** (full teams/totals/scouting),
  - partial metadata doc with `_id` as **ObjectId** (missing totals).
- **Fix implemented:**
  - `complete_week()` now persists the provided `game_document` snapshot before EOG runs.
  - `_save_game_result()` now prefers string `_id` to avoid creating new ObjectId clone docs.
  - `update_team_attributes_after_game()` now evaluates both `_id` variants and selects the richer doc for EOG (`[EOG-GAME-DOC-SELECT]` log).
- **Expected log health:**
  - `🧪 [EOG-SNAPSHOT-SOURCES]` should report `teams.totals` or `teams.box_score` (not `none`) for completed games.
  - `🧭 [EOG-GAME-DOC-SELECT]` should show which candidate doc was used and its richness score.

### Player Of The Game (POTG)

**Canonical implementation** is `FrontEnd/static/js/shared/potg.js` (`calculatePlayerOfTheGame(gameData, options)`). It is used by the EOG completion popup (`gameCompletionPopup.js`) and Box Score page (`box-score.js`). The FCC Last Game backend summary mirrors this exact contract in `_calculate_potg_summary()`; `tests/test_potg_surface_parity.py` passes one game document through both languages and requires identical player and stat output.

**POTG point scale (per player, both teams):**
1. **2 POTG points** for each point scored, assist, rebound (TREB = OREB + DREB), block, and steal.
2. Defensive bonus, only when `DEF_A > 10`:
   - DEF% `> 80%` → +15
   - else DEF% `> 60%` → +10
   - else DEF% `> 40%` → +5
   - (DEF% = `round(DEF_S / DEF_A × 100)`)

**Winner selection:**
- Players are scored and sorted descending.
- If the top player's POTG points are **≥ 16 more** than the second player → top player is POTG outright.
- Otherwise, randomly choose among the **contenders** (all players whose score ≥ the second-place score):
  - If contenders span both winning and losing teams: winning-team share **0.67**, losing-team share **0.33** (split evenly within each group).
  - Otherwise (same team, or no clear winner): **equal weight** across contenders.
  - The random pick is **deterministic per game** — seeded from `gameId` (`"{gameId}:potg"`) so the same game always yields the same POTG.

**Candidate sourcing:** merges `gameData.players` and `gameData.box_score` (team inferred from box-score key); later box-score fields merge over an existing player candidate rather than being discarded. Stats read from `stats.game` / `stats`; rebounds use `REB`, falling back to `OREB + DREB`.

**Snapshot contract:** for franchise games, the completion modal fetches and prefers the finalized persisted game document after phase A, falling back to the supplied live snapshot only if that read is unavailable. FCC Last Game reads the same persisted document. This prevents the same algorithm from receiving two different stat snapshots.

**EOG completion popup layout** (`gameCompletionPopup.js`):
- Header: "Game Complete!"
- Row 1 (Final Score): left team+score vs right team+score
- Row 2: POTG image (horizontally centered)
- Row 3: "XX PTS  XX Reb  XX Ast" (Reb = TREB)
- Row 4: "XX STL  XX BLK  XX Def%"
- Row 5: two CTA buttons (mode-specific, see above)

**Box Score POTG section** (`box-score.js`/`.html`): below Team Quarterly Scoring, above the two team tabs.
- Header (centered): "Player Of The Game"
- Row 1 (centered): "{Player Name} - {Player Team}"
- Row 2 (stats): "XX PTS  XX REB  XX AST  XX STL  XX BLK  XX DEF%"
