# Advance Triggers

Per-step advance triggers for each turn type in the unified animation system. The advance trigger is the condition that ends a step; backend pre-computes its time `T` (game-seconds) and the frontend playback engine awaits exactly that duration before rendering step end.

See [Animation_System_Updated.md](../projects/Animation_System_Updated.md) for the schema and architecture.

**Trigger conditions (closed vocab):**
- `fixed_duration` — step ends after a backend-computed duration. T = the duration.
- `ball_reaches_player` — step ends when the ball arrives at a target player. T = pass distance ÷ pass speed.
- `player_reaches_position` — step ends when a target player arrives at a target coord. T = traversal time at the player's archetype rate.
- `shot_resolved` — step ends when shot outcome is determined.
- `stopper_action` — step ends on backend-rolled foul / steal / dead-ball turnover event.

---

## HCT

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Setup | `player_reaches_position` | slowest setup mover (max start→end distance) | `step_clock_seconds[0]` |
| 1 | BH advance | `player_reaches_position` | BH | `step_clock_seconds[1]` |
| 2 | PG converge | `player_reaches_position` | PG defender (defender on BH) | `step_clock_seconds[2]` |
| 3 | Outcome | `player_reaches_position` | BH | `step_clock_seconds[3]` |

## DREB

| # | Step | Trigger | T |
|---|---|---|---|
| 0 | Rebound capture | `player_reaches_position` (rebounder → ball bounce coords) | rebounder traversal time at `sprint` archetype |

---

## Not yet migrated

Sections below are placeholders. Populated as each turn type migrates to the new system.

## HCO

HCO is skeleton-driven. The emitter walks `skeleton.steps[i]` + `step_clock_seconds[i]` and emits one AnimationStep per skeleton step. The number of steps varies by playcall / variant — typically 4–10 after inbound trim.

Per-step trigger uniformly = `player_reaches_position`. T = `step_clock_seconds[i]`. Faster movers reach their destinations earlier and idle until T.

Gating player:
- Steps `0..N−2`: **slowest mover** (player with the largest start→end distance).
- Step `N−1` (final): **shooter** (offense player with `shoot` in pos_actions); falls back to slowest mover if the final step has no shoot action (e.g., non-shot outcomes like steals or dead-ball turnovers).

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0..N−2 | Skeleton step i | `player_reaches_position` | slowest mover for step i | `step_clock_seconds[i]` |
| N−1 | Final step (outcome) | `player_reaches_position` | shooter on shot outcomes; slowest mover otherwise | `step_clock_seconds[N−1]` |

Final step branches on `result_type` (same outcome map as HCT step 3):
- `MAKE`/`MISS`/`BLOCK` → `turn_stop: SHOT_ATTEMPT`
- `D_FOUL`/`O_FOUL`/`FOUL` → `turn_stop: FOUL`
- `STEAL` → `turn_stop: STEAL`
- `DEAD_BALL` / `DEAD_BALL_TURNOVER` / `TURNOVER` → `turn_stop: DEAD_BALL_TURNOVER`
- `SHOT_CLOCK_EXPIRED` → `turn_stop: SHOT_CLOCK_EXPIRED`

After HCO MISS with defensive rebound, a discrete DREB turn is generated (parallel to OREB). See DREB section above.

## FCP

_TBD_

## Fast Break

Phase 2 rows (shot motion / shot resolution / defensive stop) below are **best-effort** mappings against the existing `fastBreak.js` orchestration. Where the current code doesn't expose a clean per-step gate (defensive stop, hold-up lead-in, outlet-denied beat), the row is marked _TBD_ to be scoped during the FB migration.

After Steal sub-variant is intentionally out of scope here.

### Covert Release

Step 0 = outlet pass + parallel transition movement. Step 1 = outcome (shot motion / defensive stop motion / foul / steal / DBT). DEFENSIVE_STOP adds a step 2 = step-back / HCO setup. Other outcomes terminate at step 1 via the appropriate `turn_stop` event.

Edge case: when rebounder == release player (no distinct outlet passer), step 0 is skipped.

#### Branch: Outlet → Shot Attempt

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Outlet pass | `ball_reaches_player` | outlet receiver | distance ÷ pass rate (sharp = `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` = 30; sloppy = 22 hardcoded); floored at 0.5 game-sec |
| 1 | Shot motion (→ `turn_stop: SHOT_ATTEMPT`) | `player_reaches_position` | shooter (BH; reaches shot spot) | BH traversal time at `sprint` archetype |

#### Branch: Outlet → Defensive Stop

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Outlet pass | `ball_reaches_player` | outlet receiver | distance ÷ pass rate (sharp = `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` = 30; sloppy = 22 hardcoded); floored at 0.5 game-sec |
| 1 | Defensive stop motion | `player_reaches_position` | **slower of {BH, defensive stopper}** reaching their stop spot | slower mover's traversal time at `sprint` archetype (BH) / `drive` archetype (stopper) |
| 2 | Step-back / HCO setup (→ implicit end-of-turn) | `player_reaches_position` | slowest mover (max traversal at drive) | slowest mover's traversal time at `drive` archetype |

**Step 0 (outlet pass) per-player movement:**
- **Outlet passer** (rebounder): stationary.
- **Outlet receiver**: stationary at receive spot.
- **Get-back defenders** (from prior shot's `offense_getback`, if any). Behavior gated on outlet quality:
  - **Sharp outlet** (`outlet_score >= 50`, 1–2 get-back defenders): **read-to-stop**. Defenders are first split by eligibility — a defender is eligible to attempt the stop only if their x is at-or-past the receiver's x in the attacking direction (home offense: `defender.x >= receiver.x`; away offense: `defender.x <= receiver.x`). Ineligible defenders (behind the receiver in the attacking direction) auto-retreat to defend the basket without rolling. Among eligible defenders, the **closest to the receiver** (Euclidean; exact ties → random) attempts first — their `player_read` score is rolled against threshold `outlet_score × 3`. **Pass** → that defender claims the cut-off stop at `(receiver.x ± 2 toward attacking basket, receiver.y)` and any other get-back defender retreats to basket defense. **Fail** → that defender retreats and the next eligible defender (if any) attempts the read.
  - **Sloppy outlet** (`outlet_score < 50` or unset, or 0 / 3+ get-back defenders): legacy deterministic behavior — player 1 (in `getback_player_ids` order) takes the cut-off at `(receiver.x ± 2 toward attacking basket, receiver.y)`; player 2 (if present) takes the same-side `lowPost` from `HCO_STRING_SPOTS` (`upper lowPost` if `receiver.y > 24`, else `lower lowPost`).
  - **Basket-defense retreat spot** (used by any defender who retreats): random spot in the defender box near the attacking rim — home offense: `(87–91, 20–30)`; away offense: `(9–13, 20–30)`. When two defenders both retreat, the second is placed with ≥2 grid offset on both axes from the first to avoid stacking.
  - Archetype = `sprint` (14 grid/sec at AG=50; aggressive cut-off pace) for all get-back defenders, both branches.
- **All other players** (non-passer, non-receiver, non-getback — typically 5–7 of them): drift a random **1–6 grid spots toward the attacking basket along x** (y held). Archetype = `cruise` (casual transition pace, not full sprint). They sprint with the play on step 1+; the small drift on step 0 keeps the outlet pass visually focused on the ball + receiver instead of crowding the BH with 6+ sprinters.

**Step 1 end announcement:** `step.end.announcement = "Nice Stop!"` (team: defense, headshot: defensive stopper). Playback engine pauses clocks, shows announcement for `hold_ms = 1000`, resumes, then proceeds to step 2.

**Step 2 (step-back) per-player movement:**
- **FB BH**: tweens to a random one of `{deep key, deep upper wing, deep lower wing}` (`HCO_SETUP_OFFENSE_BH_DEEP_SPOTS`).
- **HCO step-0 BH** (default = team's PG; only moves if different from FB BH): tweens to a position within `HCO_SETUP_HCO_BH_RADIUS = 10` grid units of FB BH AND on the same horizontal half (home offense → x ≥ 50; away → x ≤ 50, to avoid over-and-back).
- **Supporting offensive players (3 if FB BH != HCO BH; 4 if same)**: tween to `HCO_SETUP_OFFENSE_POS_SPOTS[posN]` per the standard `_alias_map` excluding both BH positions:
  - pos1 → `upper wing`
  - pos2 → `lower wing`
  - pos3 → `upper lowPost`
  - pos4 → `lower lowPost` (dropped when 2 BHs)
- **All 5 defenders**: mirror with same-lineup-position matchup (def_PG → off_PG's spot, def_SG → off_SG's spot, etc.). The 5 spots form a 2-3 zone footprint by construction.

Notes:
- Step 0 T is **distance-driven**, with pass rate gated on outlet quality. **Sharp outlets** (`fb_roles["outlet_score"] >= 50`) fly at `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` (= 30 grid/game-sec; FB-specific so HCO's canonical `PASS_GRID_SPOTS_PER_GAME_SECOND = 36` is unaffected). **Sloppy outlets** (`outlet_score < 50` or unset) fly at a hardcoded 22 grid/game-sec — the ball hangs in the air longer and the play reads as less crisp. Floored at 0.5 game-sec so very short passes still register visually. Replaces the earlier `outlet_score`-gated **fixed-T** (1.0 / 2.0 second) branches; outlet-quality gating now lives on the *rate* instead.
- DEFENSIVE_STOP has no schema-vocab `turn_stop` event for "defensive stop" — step 2 ends with `next: next_step` past the array (implicit end of turn). Caller transitions to HCO.
- Other outcome variants (FOUL / STEAL / DEAD_BALL_TURNOVER) reuse step 1 with `gating_player = BH` and the appropriate `turn_stop` event on `next` — no step 2.
- HCO BH default = PG. Set-play-specific BH detection (e.g., for plays where the BH is SG or SF) is a future enhancement.

### Rim Runner

Five terminal branches. Steps 0–1 (Burst, Outlet pass) are shared across 4 of the 5 branches; outlet-denied forks at step 1. T column = step duration in game-seconds.

#### Common lead-in (steps 0–1, shared by all branches except outlet-denied)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver (reaches `receiver_to`) | receiver traversal at default archetype |

- **Rim Runner**: 9–14 or 20–25 x spots toward basket (skill check: roll d100 < `0.6×AG + 0.2×IQ + 0.2×CH` → 20–25, else 9–14); y to a wing band on the same side as start (15–20 or 30–35).
- **Outlet Receiver**: ~8 x spots toward basket (or `rebound_x ± 12` in dynamic-placement mode); y snaps to the opposite wing band from RR (15 or 35).
- **Outlet Passer (rebounder)**: stationary at rebound spot; ball attaches to them at burst start.
- **Outlet Defender**: tweens to passer.x ± 2 (toward basket), same y as passer.
- **Get Back Players** (defenders flagged in prior shot's `offense_getback`):
  - Defender 1: targets 2 x spots ahead of RR's burst-end position (`RR.x + 2` home offense, `RR.x − 2` away offense), same y as RR.
  - Defender 2 (if present): targets the same-side `lowPost` near the basket — `upper lowPost` if RR's burst-end y > 24, else `lower lowPost` (coords from `HCO_STRING_SPOTS`).
- **Other O players** (2 non-RR, non-receiver): drift forward 1–4 x spots toward the offense's attacking basket; y unchanged.
- **Other D players** (non-getback): drift forward 1–4 x spots in the same direction as the offense (i.e., toward the offense's attacking basket, trailing the play); y unchanged.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 1 | Outlet pass | `ball_reaches_player` | outlet receiver | passer→receiver distance ÷ pass speed |

- **Rim Runner**: continues sprinting toward `rr_to` (tween started in step 0).
- **Outlet Receiver**: stationary at `receiver_to`, awaits ball.
- **Outlet Passer**: stationary, releases ball at step start.
- **Outlet Defender**: continues toward contest spot.
- **Get Back Players**: continue retreating toward own basket.
- **Other O players**: continue drifting forward.
- **Other D players**: continue retreating per their step 0 destinations.

(All non-passer/non-receiver tweens keep running through step 1 by default. The opt-in `UESS_FB_CRITICAL_EVENT_PATTERN` flag would freeze them at the step 0 boundary instead.)

#### Branch: Burst → Outlet → Lane Pass → Shot

Steps 0–1: see Common lead-in.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 2 | Lane pass | `ball_reaches_player` | rim runner (ball + RR co-arrive at catch grid) | RR traversal at sprint |

- **Rim Runner**: tweens 6 x spots further toward basket from `rr_to`, same y; arrives at catch grid same instant ball arrives.
- **Outlet Receiver / Ball Handler**: stationary, releases lane pass.
- **Outlet Passer (rebounder)**: stationary.
- **Outlet Defender**: stationary at contest spot.
- **Get Back / Other O / Other D**: stationary at their step 0 endpoints.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | Shot motion | `player_reaches_position` | shooter (reaches shot spot) | shooter traversal time |

- **Rim Runner / Shooter**: tweens from catch grid to FB shot spot near rim.
- **Shot Defender**: tweens to `defender_spot` (between shooter and basket, contest position).
- **Outlet Receiver / Outlet Passer**: stationary.
- **Other 6 players**: reposition to standard FB shot positions in parallel (`moveOtherPlayersToStandardPositions`).

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 4 | Shot resolution | `shot_resolved` | — | instantaneous |

- All players: stationary. Ball + shooter renders the shot release; result already pre-resolved by backend.

#### Branch: Burst → Outlet Denied → Defensive Stop

Step 0: see Common lead-in. (This branch forks at step 1 — no outlet pass fires.)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
*Note we need to add a gate to this, the outlet defender must be within 10 euclidin grid spots of the outlet passer, otherwsie there is not denied outlet pass
| 1 | Outlet denied beat |`player_reaches_position` | outlet pass defender reaches outlet pass defense spot | oulet pass defender sprints to location|
| 2 | Defensive stop | _TBD_ — see Covert Release defensive stop | _TBD_ | _TBD_ | **Do we need this step? I think we enter the pass to offense PG step after this, right?**

#### Branch: Burst → Outlet → Lane Pass Intercepted (STEAL)

Steps 0–1: see Common lead-in.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 2 | Lane pass intercepted | `ball_reaches_player` | interceptor (ball reaches interception contact grid) | partial pass flight |

- **Rim Runner**: tweens to a partial position (`rr_to.x + 3` toward basket, same y) — not the full catch spot, halfway in.
- **Stealer / Interceptor**: tweens to interception contact grid at sprint pace.
- **Outlet Receiver / Ball Handler**: stationary, released lane pass.
- **Outlet Passer**: stationary.
- **Outlet Defender / Get Back / Other O / Other D**: stationary at step 0 endpoints.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | `turn_stop: STEAL` | — | — | — |

#### Branch: Burst → Outlet → Lane Pass Batted OOB

Steps 0–1: see Common lead-in.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 2 | Lane pass batted OOB | `ball_reaches_player` | OOB destination (ball reaches OOB grid post-deflection) | partial pass flight + OOB drift |

- **Rim Runner**: tweens to `rr_to.x + 4` toward basket, same y (less far than the full catch spot).
- **Defender (batter)**: tweens to interception contact grid; deflects ball after ball arrives there.
- **Ball**: flies from BH to contact grid, then drifts to nearest OOB grid spot.
- **Outlet Receiver / Ball Handler**: stationary, released lane pass.
- **Outlet Passer / Get Back / Other O / Other D**: stationary at step 0 endpoints.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | `turn_stop: DEAD_BALL_TURNOVER` | — | — | — |

#### Branch: Burst → Outlet → Hold-up → HCO Settle

Steps 0–1: see Common lead-in.

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 2 | Hold-up lead-in | _TBD_ — `animateRimRunnerHoldUpLeadIn` has no exposed per-step gate | _TBD_ | _TBD_ |
| 3 | HCO settle | _TBD_ — `finalizeRimRunnerNonShotTurn` | _TBD_ | _TBD_ |

### Triangle

Drafts off the Rim Runner burst (steps 0–1). Adds Triangle setup (step 2), then a branch-specific decision lead-in (step 3+) per `triangle_branch`. If the outlet is denied (`rim_runner_outlet_failed`), Triangle setup is skipped and the path falls through to the Rim Runner outlet-denied branch above.

Common lead-in (steps 0–2, shared by all branches below):

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 0 | Burst | `player_reaches_position` | outlet receiver | receiver traversal at sprint |
| 1 | Outlet pass | `ball_reaches_player` | outlet receiver | pass flight time |
| 2 | Triangle setup | `player_reaches_position` | slowest of {BH, RR, trailer, corner players, defenders} reaching setup target | slowest mover traversal |

#### Branch: triangle_rr_post (BH → RR pass → RR shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH→RR pass | `ball_reaches_player` | RR | pass flight time |
| 4 | Shot motion | `player_reaches_position` | RR (reaches shot spot) | RR traversal time |
| 5 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_corner_three (BH → corner pass → corner shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH→corner pass | `ball_reaches_player` | same-side corner | pass flight time |
| 4 | Shot motion | `player_reaches_position` | corner shooter (reaches shot spot) | corner traversal time |
| 5 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_bh_wing_three (BH wing shot, no pass)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | Shot motion | `player_reaches_position` | BH (reaches shot spot) | BH traversal time |
| 4 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_bh_drive (BH + RR drive, BH shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH + RR drive | `player_reaches_position` | slower of {BH (`triangle_drive_to`), RR (`triangle_rr_drive_to`)} | slower mover traversal |
| 4 | Shot motion | `player_reaches_position` | BH (reaches shot spot) | BH traversal time |
| 5 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_drive_rr_feed (BH + RR drive → BH→RR pass → RR shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH + RR drive | `player_reaches_position` | slower of {BH, RR} reaching their drive targets | slower mover traversal |
| 4 | BH→RR pass | `ball_reaches_player` | RR | pass flight time |
| 5 | Shot motion | `player_reaches_position` | RR (reaches shot spot) | RR traversal time |
| 6 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_drive_corner_kick (BH + RR drive → BH→corner pass → corner shot)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | BH + RR drive | `player_reaches_position` | slower of {BH, RR} reaching their drive targets | slower mover traversal |
| 4 | BH→corner pass | `ball_reaches_player` | same-side corner | pass flight time |
| 5 | Shot motion | `player_reaches_position` | corner shooter (reaches shot spot) | corner traversal time |
| 6 | Shot resolution | `shot_resolved` | — | instantaneous |

#### Branch: triangle_hco_settle (no shot, settle to HCO)

| # | Step | Trigger | Gating player | T |
|---|---|---|---|---|
| 3 | HCO settle | _TBD_ — `animateTriangleHcoSettle` calls `finalizeRimRunnerNonShotTurn`; no per-step gate exposed | _TBD_ | _TBD_ |

## OREB

_TBD_

## BIP

_TBD_

## SIP

_TBD_

## Free Throw

_TBD_

## Opening Tip

_TBD_

## Timeout

_TBD_
