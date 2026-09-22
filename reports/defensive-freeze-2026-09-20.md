# The defensive freeze: measured

**Verdict: the hypothesis is half right in the control flow and dead on magnitude.** The deferral at
`turnAnimation.js:4833/4851/5046` is exactly as described. But the reading missed **line 4801**, and
that line changes the mechanism completely: **defenders are never frozen.** What the deferral
actually creates is a *second, duplicate* tween. Its worst case is **~50 ms**, on **0.69 %** of turns.

It is not what Jamie is seeing. §6 has a candidate that is, measured on the renderer that actually
draws 98 % of the game.

Measurement only. **No engine code, no frontend code, and no flags were changed.** `GOB_BOXOUT_CONTEST`
stays `"0"`. `git diff` at `a4c691c9c` is **0 lines**; the only new file is this report.

---

## 1. What line 4801 does to the hypothesis

```js
4801   const promise = animateStep({ ... });   // ← EVERY player. Unconditional. Before the branch.
4815   const playerRole = playerClassifications[anim.playerId] || 'defense';
4818   if (isOffensivePlayer) { offensivePromises.push(promise); ... }
4831   } else {
4833     defensiveStarters.push(() => animateStep({ ...same args... }));   // ← a SECOND call
4844   }
```

`animateStep` (`animateStep.js:37`) returns a Promise whose **executor runs synchronously** and reaches
`scene.tweens.add(tweenConfig)` at line 434, which auto-starts. There is no `killTweensOf(sprite)`
anywhere on this path — the two `killTweensOf` calls (104, 624) take `tween`, not `sprite`.

So on every step, for every defender:

| | what happens |
|---|---|
| **tween A** | started at 4801, immediately, in parallel with the offense. Its promise is **discarded** for defenders. |
| **tween B** | a *second* `animateStep`, fired at 4852 (no pass) or 5047 (after `await passerPromise`). |

**The defenders move on time, every step.** The deferral defers a duplicate, not the motion.

> The brief asked to be told if the instrumentation contradicted the reading. It does — but by code
> inspection, not by instrumentation. The falsifier is one line above the block that was quoted, and
> reading it is cheaper and more certain than measuring it.

## 2. The duration formula

```js
4763   const waypointGameSeconds = Number(curr?.game_seconds);
4765   if (Number.isFinite(waypointGameSeconds) && waypointGameSeconds >= 0) {
4766     duration = Math.max(50, Math.round(waypointGameSeconds * clockSecondMs));   // primary
4767   } else {
4774     duration = distanceDuration;                                                // fallback
```

- `clockSecondMs` = `scene.gameClock.getState().tickMs || 350`.
- `distanceDuration` = `getPlayerDuration` → `getPlayerMovementDurationMs`:
  `max(50, hypot(Δpx) / speed × 1000)`, `speed = (400 + AG) × (window.__GAME_SPEED ?? 450)/450`,
  ball-handler multiplier `1.0`. `distance < 1 px` → `50`.
- `gridToPixels`: `px = (gx/100)×1229`, `py = ((50−gy)/50)×768` — anisotropic, 12.29 px/grid-x vs 15.36 px/grid-y.

**On this path the primary branch is dead.** Across n=40 games, **0 of 22,206** legacy waypoints carry
`game_seconds`. So `turnAnimation.js` is always distance-based — the brief's reading of the formula was
right, even though the `method: 'distance-based'` string at 4780 is **hard-coded** and is logged
unconditionally, including when the `game_seconds` branch *is* taken. That string is what makes the
formula look settled; it is not evidence either way.

## 3. Magnitude on the legacy path

Tween B starts at `t = D_passer`. A defender who has already arrived hits the `distance < 1` early
return (`animateStep.js:258`) and B is inert. A defender still in flight gets a fresh tween of the
**same** `duration` (computed once at 4763), so its arrival moves from `D_def` to `D_passer + D_def`.
Extra delay = `D_passer`.

n=40, seeds 8000–8039, sim arm, `SEED_DEFENSES=1`; 119 legacy-only turns, 1,255 defender-instances on pass steps:

| | mean | p50 | p90 | max |
|---|---|---|---|---|
| `D_passer` (the "freeze") | 51 ms | **50** | 50 | **148** |
| `D_def` | 81 ms | 50 | 157 | 641 |

| | |
|---|---|
| defender already arrived → **B inert** | **83.6 %** |
| defender in flight → extra delay `D_passer` | 16.4 % (p50 **50 ms**, max **50 ms**) |
| that delay as a fraction of the defender's own tween | p50 0.24, p90 0.73 |

**`D_passer` is 50 ms at the p50 and 148 ms at the max because it is the floor.** The passer barely
moves on a pass step — he stands and passes, so his distance is sub-pixel and the `MIN_DURATION_MS`
clamp takes over. There is no 600 ms freeze here to be a fraction of anything.

## 4. Routing — how often this code runs at all

| turn population (n=40, 17,143 turns) | count | share |
|---|---|---|
| `animation_steps` present → **schema renderer** (`animationPlayback.js`) | 14,105 | **82.3 %** |
| legacy `animations` **and** `animation_steps` → still schema | 3,583 | 20.9 % |
| legacy `animations` **without** `animation_steps` → **can reach `playTurnAnimation`** | **119** | **0.69 %** |
| neither (FREE_THROW, TIMEOUT, …) | 2,919 | 17.0 % |

The other legacy routes are all shut:

| route | guard | fires |
|---|---|---|
| `AnimationEngine.js:804` HCO-family fallback | `isHcoFamily && !hasAnimationSteps` | the 119 above |
| `animateGameTurns.js:1026` FCP/HCT shot | `fcp_shot === true \|\| hct_shot === true` | **0 / 17,143** |
| `AnimationEngine.js:1894` STEAL skeleton | `turnData.animations.length > 0` — *unguarded by steps* | **0 / 17,143** (no STEAL turn carries `animations`) |
| `1811 / 2070 / 2100 / 2124 / 2149` | behind `runSchemaPlaybackTurn()` or a missing subsystem | not in prod |

The 119 are `MAKE→BASELINE_INBOUND` (60), `OPENING_TIP` (40), `MISS→DREB` (14), `MISS→OREB` (5).
**No HCO turn is among them.** Jamie reports the symptom on HCO entry steps; this code cannot draw them.

## 5. Part 3 — scope, and every site with this shape

**All five defenders, not a subset.** `playerClassifications` (4521–4542) is whole-team:
`String(sprite.team_id) === String(offenseTeamId)`. Line 4815 defaults to `'defense'`, so a player
missing from the map is deferred too.

| file | `defensiveStarters` / `passerPromise` refs | does it defer? |
|---|---|---|
| `turnAnimation.js` | 10 | **Yes** — the only site |
| `ShotAnimationSystem.js` | 4 | **No.** One `animateStep` at 719 *before* the branch; the else-branch (743–754) pushes the **already-running** promise. No closure, no second call. |
| `animationPlayback.js` (schema) | 0 | No branch at all — one loop over `start.coords` (1391–1431) starts offense and defense alike. |

`animateStep` has exactly three callers: its own module, these two files. `ShotAnimationSystem` is the
corrected version of the same code — its comment at **761** (`"ShotAnimationSystem always starts
defenders in Phase 2"`) is stale; they start in the loop, as its own comment at 717 says.

### One real defect, small and confined

The duplicate is **not** inert even when the tween is. The `distance < 1` early return calls
`onAction` (`animateStep.js:262–264`) — so B re-fires it. And defenders carry a non-null action on
**100 %** of legacy pass steps: `guard_offball` 1,120, `guard_ball` 130, `steal_miss` 5.
**`onAction` fires twice per defender per pass step** on this path. Confined to 0.69 % of turns; not
investigated further, because it is not the reported symptom.

## 6. What does match the symptom — on the renderer that draws 98 %

The schema path has no deferral, so the question becomes whether the *backend* authors defender motion.
Measured from `animation_steps` `start.coords` vs `end.coords` — the same test the repo's own shipped
detector uses (`deadAirLedger.js:171 detectDefenseFrozen`):

| schema path, n=40 | |
|---|---|
| steps | 93,209 |
| steps involving a ball pass | **23,343 (25.0 %)** |
| steps with offense moving | 67,562 |
| **offense moves / defence entirely static** | **8,680 (12.8 %)** |

Cause, on all 8,680: **backend authoring, never rendering.**

| `detectDefenseFrozen` verdict | count | share |
|---|---|---|
| `destination == start` (emitter authored a no-op) | 6,071 | 69.9 % |
| `no destination authored` | 2,609 | 30.1 % |
| `destination differs from start` → **FRONTEND** | **0** | **0 %** |

By step reason — HCO entry called out as the brief asked (`advance_trigger.metadata.reason`;
tween ms = `max(50, round(tween_durations × 350))`):

| reason | steps | def-static | tween p50 | p90 | max |
|---|---|---|---|---|---|
| **`hco_entry_walkup`** | **4,070** | **22.6 %** | **548** | **1249** | **1716** |
| `hco_entry_handoff_hold` | 2,328 | 0.0 % | 350 | 350 | 350 |
| `hco_entry_handoff_converge` | 1,680 | 0.0 % | 180 | 481 | 1499 |
| `hco_entry_handoff_pass` | 1,680 | 0.8 % | 175 | 175 | 175 |
| `hco_entry_kickout_pass` | 405 | 20.5 % | 175 | 288 | 372 |
| `hco_entry_kickout_positioning` | 405 | 0.0 % | 357 | 631 | 1299 |
| `hct_dead_ball` | 41 | 97.6 % | 50 | 175 | — |
| `final_turn_handoff_converge` | 54 | 88.9 % | 280 | 754 | — |
| `hct_foul` | 682 | 29.3 % | 50 | 175 | — |
| `hct_steal` | 193 | 21.2 % | 50 | 175 | — |
| `hct_entry_walkup` | 1,065 | 12.2 % | 802 | 852 | — |

**`hco_entry_walkup` is the one to look at.** 4,070 steps, 22.6 % of them draw a completely motionless
defence, and it is a *long* beat — half a second at the median, 1.25 s at p90, 1.7 s at the worst. That
is a real freeze, it is on HCO entry, and it is long enough to see. The three
`hco_entry_handoff_*` reasons the brief named are **clean** (0.0 / 0.0 / 0.8 %).

**This is a hypothesis, not a finding.** I have shown the backend authors no defender movement on those
steps; I have *not* shown that this is what Jamie is looking at. It needs an eye test against a
`hco_entry_walkup` step, and it is a backend authoring question, not a frontend one.

On the brief's 5 %-or-40 % test: **25.0 %** of schema steps involve a pass, so a per-pass-step effect
*could* account for "many steps" — it just isn't happening on this renderer.

## 7. Part 2 — NOT RUN

No browser in this environment, so the in-page timing capture was not done. **I added no
instrumentation, so there is nothing to revert** — §0 records the tracked diff as 0 lines.

It should not need new code when it is run. The instrumentation already ships and is **on by default**:

| already in the repo | what it gives |
|---|---|
| `deadAirLedger.js:171 detectDefenseFrozen` | fires `[DEF-FROZEN]` on the symptom itself, with a BACKEND/FRONTEND verdict. Silences on `window.DEF_FROZEN_TRACE = false`. |
| `window.UESS_TRACE_PLAYBACK = true` | `pass:release` with per-mover tween durations (`stepMoverDurations`, 1390) |
| `recordArrivalTails` / `recordStillness` | movers that arrive early then stand — the "defenders stop animating" signature |

Recipe: load a game, leave `DEF_FROZEN_TRACE` alone, set `UESS_TRACE_PLAYBACK = true`, and filter the
console on `[DEF-FROZEN]`. §6 predicts it fires on ~12.8 % of offense-moving steps, and that **every**
one says `BACKEND`. If any says `FRONTEND`, §6 is wrong and the frontend is back in scope.

## 8. If you wanted to fix the deferral anyway

One paragraph, as asked. **Do not build this.** The fix is to delete the closure at 4833–4843 and push
the promise from 4801 (`defensivePromises.push(promise)`) — i.e. make `turnAnimation.js` match
`ShotAnimationSystem.js`, which already does exactly that and is the same code one refactor later. It
removes the duplicate tween, the double `onAction`, and the ≤148 ms lag. **Cost: it is not worth doing
on its own** — 0.69 % of turns, 50 ms, and no HCO turn in the population. **Risk:** the comment says the
deferral exists "so we can sync them with the pass", and whatever that was protecting is protected by
*tween B*, not tween A — so anything downstream that depends on defenders settling *after* the pass
release would change. Line 5246 (`passInfo && offensivePromises.length > 0`) and the receiver-settle
contract at 5166–5192 are the places to check first. It should ride along with other work in this file,
behind that check, not as a standalone flip.

## 9. Tunable Constants

| constant | where | value | effect |
|---|---|---|---|
| `MIN_DURATION_MS` | `playerMovementDuration.js:10` | `50` | the floor that *is* `D_passer` at p50 (§3). Raising it lengthens the duplicate-tween lag 1:1. |
| `DEFAULT_GAME_SPEED_PX` | `playerMovementDuration.js:9` | `450` | denominator of the global speed scale |
| `MOVEMENT_SPEED_BASE` | `playerMovementSpeed.js:8` | `400` | px/s at AG 0 |
| `MOVEMENT_SPEED_SLOPE` | `playerMovementSpeed.js:11` | `1` | +1 px/s per AG point → AG 5–98 spans 405–498 px/s, a 23 % spread |
| `BALL_HANDLER_SPEED_MULTIPLIER` | `playerMovementSpeed.js:21` | `1.0` | inert today; plumbing kept |
| `DEFAULT_AG_WHEN_MISSING` | `playerMovementSpeed.js:13` | `50` | |
| `clockSecondMs` (`tickMs`) | `turnAnimation.js:3287` | `350` | game-second → ms for every schema tween (§6) |
| canvas `width` / `height` | `bootGame.js:2338` | `1229` / `768` | grid→px scale; anisotropic |
| `window.DEF_FROZEN_TRACE` | `deadAirLedger.js:174` | unset (= on) | the §7 detector |

## 10. Footing and caveats

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
n=40 seeds 8000–8039, `SEED_DEFENSES=1`, **sim arm**. **0 errors across 40 games.**

**The probes consume no RNG.** They patch nothing and call nothing back into the engine — they walk
`gm.turns` *after* all four quarters have run. No reference cut and none needed: no sim code was touched.

Caveats, stated rather than buried:

- §3 models the sprite's start position as `movement[i-1].coords`. The real tween starts from
  `sprite.x/y`, which can differ — the `[HCT-FE-DIAG]` block at `turnAnimation.js:4730` exists because
  of exactly that. Where they diverge, `D_def` is wrong; `D_passer` is not, because it is on the floor.
- §3 assumes `tickMs = 350` and `window.__GAME_SPEED` unset. A non-default game speed scales §6's tween
  columns linearly.
- §6's def-static test is authored intent (`start.coords` vs `end.coords`), not pixels. It shows the
  emitter authored no movement. It does not prove the sprite stood still, and it does not prove this is
  the symptom Jamie reported.
- The 25.0 % pass-step figure is the union of `ball_motion_style == "pass"`, an owner change, and
  `advance_trigger.metadata.kind == "ball_reaches_player"`. A narrower definition gives 8.4 %. My first
  pass used a stricter test that required a non-null start owner and reported 9.1 %; that under-counted,
  because a ball already in flight at step start has `sowner: null` — `hco_entry_handoff_pass` scored
  0 % passes under it, which is how the error surfaced.

## 11. Not covered

- **Part 2 not run** (§7). No browser here.
- The double `onAction` (§5) is reported, not fixed and not traced into its handlers.
- `hco_entry_walkup` (§6) is not diagnosed — where the emitter drops the defender destinations is a
  separate pass.
- Nothing retuned, nothing flipped, no flag added.
