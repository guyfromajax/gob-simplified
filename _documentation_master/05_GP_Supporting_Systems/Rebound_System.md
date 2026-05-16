A unified system that handles rebound logic for all missed shot instances.

-HCO Shots
-Fast Break Shots
-OREB Putback Shots
-Free Throw Shots

## Post-shot placement authority (single source of truth)

`shot_manager` is the **sole authority** for where every player ends up after a missed shot. On any MISS turn it populates four overlay maps on the turn result dict:

- `offense_rebounder_coords` — non-get-back offensive players, clustered near the rim of the basket just attacked.
- `defense_rebounder_coords` — non-release defensive players, clustered near the rim of the basket just attacked.
- `offense_getback_coords` — offensive get-back retreaters (HCO only; HCT / FCP / Fast Break skip the get-back mechanic).
- `defense_release_coords` — defensive release players running for the outlet on a Covert Release fast break.

The MISS turn emitter absorbs these into the final step's `end.coords` via its `_apply_post_shot_overlay` helper. `sync_lineup_coords_from_turn` then writes them to `player.coords`. Overlay precedence is set in `TURN_COORDS_OVERLAY_KEYS` (rebounder maps applied first, get-back / release applied last — get-back / release win for the specific role-players they designate).

### DREB animates rebound capture only (backend step); outlet is a separate client beat

**Backend discrete `DREB` turn** (`result_type` / `current_turn` **`DREB`**, `animation_steps` from `dreb_step_emitter.py`): animates **only** the rebounder moving to the ball at the bounce spot. **It does not re-place the other nine players** — they stay where `shot_manager` put them on the prior **MISS/BLOCK** turn (placement authority above).

**Half-court outlet** (rebounder dribble / pass to outlet receiver per `dreb_outlet_pass`, teammates moving toward the new offense end — unit **`hco.lead_in.from_dreb_outlet`** in `turnAnimation.js` → `runDefensiveReboundSetup`) **is not** emitted as part of `dreb_step_emitter` steps. For discrete **DREB → HCO/HCT/FCP**, the client runs that setup **after** `AnimationEngine` finishes **`playTurn`** for the DREB row, using the **previous** MISS/BLOCK turn for **`dreb_outlet_pass`** and **`offense_getback`**. Skip when `DREB.next_play_type` is **FAST_BREAK** (fast break owns outlet) or when the shot turn has **`force_foul_after_dreb`**.

**Embedded DREB** (MISS/BLOCK turn still owns rebound, no separate `DREB` row — e.g. many **FREE_THROW** misses, unmigrated FCP / FB variants): outlet still runs from **`ShotAnimationSystem.handleDefensiveRebound`** → **`runDefensiveReboundSetup`** when `next_play_type` is **HCO/HCT/FCP** on that same shot turn. **Rebound!** headline rules (including idempotency with discrete rows): **`Announcement_System.md`**.

This replaces the earlier two-authorities-via-player-id-matching design, where the DREB step ran its own frontcourt-filter / random-near-bounce placement logic and tried to honor shot_manager's get-back / release maps via an exempt list. That coupling was brittle — any mismatch in the exempt set yanked role-players to the rim cluster. See [`Animation_System_Updated.md`](../projects/Animation_System_Updated.md) "DREB emitter — scoping" for the current model.

## Free Throw Miss Rebounds

When the **last** free throw is missed, rebound selection runs in `resolve_free_throw_logic` (`BackEnd/engine/phase_resolution.py`) after **`apply_coords_from_animations_list`** updates player `coords` from the FT lane / setup animation. Rebounding uses **`determine_rebounder`** in `BackEnd/utils/shared.py` with the same bounce spot as today (`calculate_bounce_spot` from the attacked basket).

### X-distance eligibility (FT only)

- **Constant:** `FREE_THROW_REBOUND_MAX_X_DELTA = 20` (x grid units) in `BackEnd/utils/shared.py`.
- **Rule:** Before choosing the closest player to the bounce on each team, the pool is filtered to players with **|coords.x − bounce_x| ≤ 20**. Players farther than **20** x-spots from the bounce (using coords at FT attempt time) are **not** eligible to be that team’s rebound candidate.
- **Y:** The gate uses **x only**; y is unchanged from existing closest-to-bounce logic.
- **Fallback:** If no one on **either** team passes the filter, the engine logs a warning and runs **`determine_rebounder`** again on **full lineups** (no x gate) so a rebound is always assigned.
- **Scope:** Only **missed last FT** passes `max_x_delta_from_bounce` into `determine_rebounder`. HCO, fast break, and OREB putback-miss rebounds do **not** use this gate unless called with the same keyword explicitly in the future.

## Frontend — "Rebound!" headline (primary overlay)

When the rebounder **secures** the ball in animation, the client shows the primary **Rebound!** headline (portrait + team styling). Implementation details:

- **Helper:** `announceReboundHeadlineIfNeeded(scene, turnData, rebounderSprite, rebounderId)` in `FrontEnd/static/js/phaser/utils/announcements.js`.
- **Idempotency:** When callers pass the authoritative turn object (`turnData`), the helper sets `turnData._reboundHeadlineShown` after display so `ballManager.animateRebound`, embedded `ShotAnimationSystem.handleEmbeddedRebound`, final-FT `animateRebound`, `ReboundAnimationSystem`, and `announceGameEvent('REBOUND', ...)` cannot double-fire for the same turn.
- **Call sites:** `ballManager.js`, **`ShotAnimationSystem.js`** (embedded MISS/BLOCK rebound secure), **`FreeThrowAnimationSystem.js`**, `ReboundAnimationSystem.js`, `gameAnnouncements.js` (`REBOUND`). **Discrete `DREB` turn:** rebound headline may still fire on the embedded MISS path; **outlet** runs after **`AnimationEngine`** `playTurn` for the **`DREB`** row (`_maybeRunDiscreteDrebOutletLeadIn` → `runDefensiveReboundSetup`).

See `Announcement_System.md` for tiering, Block → Rebound ordering, and related flags (`_blockAnnounced`).

## OREB Putback Shot Defender

OREB putbacks now use a proximity-qualified shot defender system instead of the old weighted-by-position shortcut.

### Defender Qualification
1. Only defenders within `10` Euclidean distance of the OREB shooter are initially eligible.
2. Among those eligible defenders, first look for players whose `x` position is at least as close to the basket as the shooter:
   - home offense attacking right basket: `defender_x >= shooter_x`
   - away offense attacking left basket: `defender_x <= shooter_x`
3. If exactly one qualifies, he is the shot defender.
4. If more than one qualifies, choose the one closest to the shooter. Ties are broken randomly.
5. If none qualify on the x-axis, take the closest initially eligible defender and run an IQ read:
   - `x = random.randint(1, 100)`
   - if `x <= defender.IQ`, move the defender to one x-grid closer to the basket than the shooter and within `-1` to `+1` y of the shooter, and he becomes the shot defender
   - if `x > defender.IQ`, the putback is uncontested

### Putback Resolution
- Contested putback:
  - use the same `inside` shot logic as a standard inside shot with no passer
  - this includes standard make/miss thresholding, defensive foul checks, and and-1 / 2 FT outcomes
- Uncontested putback:
  - `y = random.randint(1, 100)`
  - if `y < 100`, shot is good
  - else the putback is missed and rebound resolution proceeds normally

## Rebound Stat Recording

### Standard Flow (HCO, Fast Break, Free Throw)
- Rebound stat (DREB/OREB) is recorded immediately after determining the rebounder
- Stat is recorded in the same function that creates the turn result
- Example: `shot_manager.py` records stat on line 900-901, then computes deltas using the same player object

### OREB Putback Miss Flow (Special Case)
**Problem:** When a putback misses and results in another rebound, the stat recording flow is split across two functions:
1. `resolve_offensive_rebound()` in `shared.py` (line 229) records the stat on the rebounder object returned by `determine_rebounder()`
2. `resolve_offensive_rebound_turn()` in `turn_manager.py` looks up the player again by ID (line 2454) for delta computation

**Solution:** After looking up the rebounder by ID in `turn_manager.py`, re-record the rebound stat on that player object to ensure it's on the same instance used for delta computation. This matches the pattern used in HCO misses and guarantees stat consistency.

**Implementation:**
- Location: `BackEnd/models/turn_manager.py` line ~2464
- After finding `new_rebounder` by ID lookup, call `new_rebounder.record_stat(rebound_type)`
- This ensures the stat is recorded on the correct object instance, even if the lookup returns a different reference than the one used in `shared.py`

**Why This Matters:**
- Supports consecutive OREB scenarios: HCO miss => OREB => Putback Miss => OREB => Putback Miss => OREB => Putback Miss => DREB
- Each OREB is a separate turn, and each rebounder must have their stat properly recorded
- Stat deltas are computed by comparing current stats to `pre_stats` snapshot, so the stat must be on the same object instance used for delta computation

**Rebound Resolution Flow (8 Steps)**
1. Calculdate the mised shot bounce spot
    -bounce spot has wider variance on longer shots
        shot: x range 2-6, y range +-6
        medium x range 2-8, y range +- 8
        high x range 2-10, y rane +- 10
2. Filter Eligible players
    -Remove fast break get back players from both teams
3. Discount shooter / putback attempt player
    -Increase their distance score +20% (this makes them 20% less likely to be chosen, lowest distance score from each team is chosen)
4. Find closest player to bounce spot from each team
5. Handle edge cases (no rebounders available, use player who is closest to the bounce spot)
6. Calculate rebound scores for the two closest players -- uses function calculdate_rebound_score()
7. Apply team bias, modifiers, and zone penalty
    -bias = def_mod - off_mod
    -def_prob = min(0.95, max(0.55, 0.75 + bias))  
    -zone penelty, def_weight *= 0.9 (if defense playing zone)
8. Weighted random selection between the two closest players
    -o_score, d_score calculated using calculate_rebound_score()
    **(need to account for distance here)**
    -total_score = d_score + o_score 
    -d_weight = (d_score / total_score)
    -d_weight += (def_prob - 0.5)
    -d_weight = min(0.95, max(0.05, d_weight)) 
    -radom_value = random.random()
    -if random_value < d_weight:
        rebound_team = DEFENSE
        rebounder = d_rebounder
    -else:
        rebound_team = OFFENSE
        rebounder = o_rebounder


**Over The Back Fouls**
On each rebound attempt we will calculate the possibility of over teh back fouls via the following logic

-Identify one potential fouling player from each team. 
    -use the rebounder from teh reboudnging team, and the player on the non-rebounding team who is cloest to the rebounder using Euclidian distance
-If the closest player from the non-rebounding team is farther than 4 Euclidian distance from the rebounder, there is no Over The Back foul in play for either team
-Offense Threahsold = 90 + offense team discipline value
-Defense Threshold = 10 - defense team discipline value
otb_foul = random.randint(1,100)
-if otb_foul > Offense Threshold, o foul is in play, elif otb_foul < Defense Threshold, d foul in play, else no foul

-if o foul or d foul in play
    - second_roll = random.randint(1,100)
    - if second_roll > potential fouling player's IQ from the in play foul team (offenssive potential fouler for o foul in play or defensive potential fouler for d foul in play), then foul_still_in_play = True, else foul_in_play = False
    -if foul_still_in_play = True, final_roll = random.randint(1,2), 1 = foul, 2 = no foul

-if there is an over the back foul called on the offense or the defense, it will end the turn there and negate any Putback attempt or kickout pass that would have been executed. We will process each like a standard non shooting d foul or non shooting o foul.
-Announcement copy: "Over The Back!" with the fouling player's image through the announcement system

---

## Rebounder selection per turn type (target state)

Source-of-truth grid for which prefilter and rebounder-selection function each turn type uses. Updated as part of the SS&S animation refactor (see `_documentation_master/projects/Animation_System_Updated.md`).

| Turn type | Prefilter | Rebounder selection |
|---|---|---|
| **HCO MISS** | Existing (`offense_rebounders` + `defense_rebounders` — excludes get-back / release) | `choose_rebounder` |
| **HCT MISS** | Frontcourt-half x-eligibility filter (home offense → x ≥ 50, away offense → x ≤ 50) | `choose_rebounder` |
| **FCP MISS** | Frontcourt-half x-eligibility filter (home offense → x ≥ 50, away offense → x ≤ 50) | `choose_rebounder` |
| **Fast Break MISS** | Frontcourt-half x-eligibility filter (home offense → x ≥ 50, away offense → x ≤ 50) | `choose_rebounder` |
| **Free Throw MISS** | `max_x_delta_from_bounce` (FREE_THROW_REBOUND_MAX_X_DELTA) | `determine_rebounder` |
| **OREB chained rebound** | `max_x_delta_from_bounce` (note: previously attempted but had stale-coord issues; revisited as part of this refactor) | `determine_rebounder` |
| **defender_count == 0 edge case** | None (existing behavior preserved) | `determine_rebounder` |

Notes:
- HCT / FCP previously inherited HCO mechanics (get-back / release). The refactor drops those for HCT / FCP / Fast Break and aligns them on the frontcourt-half x-eligibility filter.
- HCO retains its existing prefilter — the get-back / release mechanic is HCO-specific.
- `choose_rebounder` is the per-team primitive. `determine_rebounder` is the whole-game wrapper that calls `choose_rebounder` once per team and then runs the weighted off-vs-def selection. See section above for algorithmic detail.



