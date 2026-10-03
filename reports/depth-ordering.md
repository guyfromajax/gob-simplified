# Player sprite depth ordering — making merged sprites legible

`USE_DEPTH_ORDERING`, **default FALSE**. Front end only. Branch `feature/animation-reward`.
Not merged. No coordinate, posture, tolerance, cap or pass-count change; nothing retuned.

---

## 1. Are merged pairs actually legible now? Yes — and here are the frames

Two merges were staged inside the band the separation pass refuses to touch
(`pinned_coverage_distance()` = 2.5 grid): a **teammate merge at 1.10 grid apart** and a
**defender-on-his-man merge at 1.20 grid apart**. Two median sprites clear each other only at
5.2482 grid, so both pairs are fully merged on screen.

| | frame |
|---|---|
| flag OFF | [`reports/depth-frames/merge-01-flag-off.png`](depth-frames/merge-01-flag-off.png) |
| sub-mode (i) tie-break | [`reports/depth-frames/merge-02-tie-break.png`](depth-frames/merge-02-tie-break.png) |
| sub-mode (ii) hard promotion | [`reports/depth-frames/merge-03-hard-promotion.png`](depth-frames/merge-03-hard-promotion.png) |

**What changes in the frames**, verified by eye and by the measured depths below:

- **Teammate merge (right of frame).** Flag off, `OP` (the power forward) is in front and the
  centre's name strip is half-buried — which of the two wins is decided by insertion order, not
  by the play. Ordering on, **`OC` is in front** with its strip fully readable, because the
  centre is the nearer of the two (grid y 32.0 vs 33.1).
- **Defender-on-his-man merge (bottom right).** Flag off, `DG` (defender) is in front. Ordering
  on, **`OG` is in front** — the offensive guard is nearer the viewer (y 14.0 vs 15.2).
- **The top pair does NOT flip**, and that is the control: there the defender genuinely is the
  nearer man (y 44.8 vs 46.0), so he stays in front in both states. The rule is "nearest the
  viewer wins", not "offence wins".

### The measured depths behind those frames

| player | grid y | flag OFF | (i) tie-break | (ii) hard promotion |
|---|---|---|---|---|
| o_SF | 8.0 | 1 | **523** | 523 |
| o_SG | 14.0 | 1 | **463** | 463 |
| d_SG | 15.2 | 1 | 448 | 448 |
| d_C | 20.0 | 1 | 400 | 400 |
| d_SF | 25.0 | 1 | 350 | 350 |
| d_PF | 30.0 | 1 | 300 | 300 |
| o_C | 32.0 | 1 | **283** | 283 |
| o_PF | 33.1 | 1 | 272 | 272 |
| d_PG | 44.8 | 1 | 152 | 152 |
| o_PG (ball) | 46.0 | 1 | 148 | **652** |

Flag off, **all ten are identical** — which is the defect: ten players at one depth means the
renderer has nothing to order them by.

---

## 2. Coverage — read this before believing the section above

**There is no single per-step funnel, and I did not find one.** Eight paths each run their own
step loop over `playerSprites`, so a per-step hook would have to be written eight times:

| path | moves players | covered by this change |
|---|---|---|
| `turnAnimation.js` | yes (2 `animateStep` sites, 11 tweens) | ✅ per-frame |
| `animateGameTurns.js` | yes | ✅ per-frame |
| `AnimationEngine.js` | yes | ✅ per-frame |
| `HCOAnimationSystem.js` | yes (3 tweens) | ✅ per-frame |
| `PassAnimationSystem.js` | yes (4 tweens) | ✅ per-frame |
| `ShotAnimationSystem.js` | yes (2 `animateStep`, 12 tweens) | ✅ per-frame |
| `ReboundAnimationSystem.js` | yes (1 tween) | ✅ per-frame |
| `FreeThrowAnimationSystem.js` | yes (3 tweens) | ✅ per-frame |
| FCP / HCT | via the above | ✅ per-frame |

The funnel that *does* exist is **`scene.events.on("update")`** — it runs every frame whatever
is driving, and it is the same mechanism `createHeadshotMarkerV2.__syncMask` already uses. The
ordering pass installs there, so all nine rows above are covered by **one** hook rather than
eight, and nothing added later can silently miss it.

**What I have NOT proven:** that the hook fires inside a live game turn. See §7 — the frames come
from a standalone harness that loads the real marker factory and the real applier, not from a
booted `court.html` session. The coverage claim above is traced from the call graph plus the
fact that the update loop is unconditional; it is not measured in a live turn.

---

## 3. Per-step vs per-frame — decided by the funnel, not by taste

The brief asked for per-step first, then evidence on whether per-frame is justified. **The
coverage inventory decided it before the staleness question did**: per-step means eight hooks,
per-frame means one. I implemented per-frame, and it also removes the staleness limitation for
free — ordering is computed from each container's **live** pixel position (inverted through
`pixelsToGrid`), so two players crossing mid-tween are ordered correctly throughout the tween
rather than at step boundaries only.

Cost: ten containers per frame — read `y`, one multiply-add, one compare, and `setDepth` only
when the value actually changed (`sprite.depth !== depth`). No tween callback is touched.

The per-step context hook still exists at `turnAnimation.js:4686` but only publishes
`scene.__depthContext` (`animations`, `stepIndex`, `offenseTeamId`); it sets no depths.

---

## 4. The ball regression

`BallController.positionBallOnPlayer` did `ballSprite.setDepth(playerSprite.depth + 1)` — safe
only because every player sat at depth 1, so the ball landed at 2, above everyone. With ordering
on, players span 148–675, so a ball pinned one above a **low-depth** carrier would be occluded
by any nearer player. The harness deliberately puts the ball on the **furthest** player on the
floor (o_PG at grid y 46) so this is exercised rather than assumed.

Fixed to `Math.max(BALL_DEPTH, playerSprite.depth + 1)`. Verified in both sub-modes
([`ball-above-players-tie_break.png`](depth-frames/ball-above-players-tie_break.png),
[`ball-above-players-hard_promotion.png`](depth-frames/ball-above-players-hard_promotion.png)) —
the ball is visible above its carrier in every captured frame, including hard promotion where
the carrier is lifted to 652.

### The pre-existing inconsistency, and whether I unified it

Before: `initializeBallSprite` set a literal `1000`; `ballAnimationSimple.js:183` and
`ballTween.js:29` each declared their own `const BALL_DEPTH = 1000`; `positionBallOnPlayer` set
`playerSprite.depth + 1` = 2. Four sites, three values.

**Unified**, into a new zero-import leaf module `animation/ballDepth.js`. A leaf was necessary,
not stylistic: `BallController → ballTween → BallControllerAdapter → BallController` is a real
import cycle, so a constant exported from any of those three could be in the temporal dead zone
for another. A module that imports nothing cannot participate in a cycle.

**Is it a behaviour change with the flag off? No, not in what is drawn.** Every player is at
depth 1, so the old `positionBallOnPlayer` value was 2 and the new one is 1000 — both are above
all ten players and below nothing else, so the stacking is identical. The stored scalar does
change, which is exactly why the flag-off gate asserts the rendered order and the player depths
rather than the ball's number.

---

## 5. The two sub-modes, side by side. No recommendation.

| | (i) tie-break | (ii) hard promotion |
|---|---|---|
| ball owner's depth | 148 (his y position) | **652** |
| does the owner beat everyone? | only on a near-tie | **always** |
| every other player | identical | identical |
| ball still on top | yes | yes |
| frame | [`merge-02-tie-break.png`](depth-frames/merge-02-tie-break.png) | [`merge-03-hard-promotion.png`](depth-frames/merge-03-hard-promotion.png) |

In (i) the y term dominates: a ball owner at the far end stays behind a player at the near end,
so the picture reads purely as depth. In (ii) the owner (and the shooter) are lifted into their
own band above every other player, so the ball is never behind anyone — at the cost of the
carrier sometimes drawing in front of a player who is physically nearer the camera. **Jamie
picks**, in his single tuning pass.

---

## 6. Gates

| gate | result |
|---|---|
| flag OFF, all ten containers | **all at depth 1** — measured via `window.__GOB_DEPTH_REPORT()`, not asserted ([`gate-flag-off.json`](depth-frames/gate-flag-off.json), [`gate-flag-off.png`](depth-frames/gate-flag-off.png)) |
| flag OFF, ball | above every player |
| backend files modified | **0** — `git diff --stat` touches 5 FrontEnd files; 4 new files are FrontEnd; zero `BackEnd/` paths |
| equiv-v3, flags off, `GOB_COLLISION_TOLERANCE` absent | **240/240** on fingerprint AND draws, 480/480 checks, **0 mismatches** |
| seed 8000 played SD=1 | fp `0c3389cd41d0bbef`, draws `75363` ✓ |
| python suite | **3,662 passed / 0 failed** / 9 skipped / 110 xfailed |
| node unit tests (`node --test`) | **16 passed / 0 failed** |
| playwright visual spec | **4 passed / 0 failed** |

**Rule 6e** applies only to the equiv-v3 row: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs
Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game
per process, `SEED_DEFENSES=1` production footing, `GOB_DEFENDER_AG_SPREAD` unset (ON). No other
number in this report is a sim number.

**One suite-count caveat, stated because the number moved:** the python suite was 3,651 passed /
20 skipped last run and is 3,662 / 9 now. The 11 difference is 11 previously-skipped tests that
now execute because I installed `node_modules` (playwright) to capture the frames. It is an
environment change, not a code change — no test changed status from pass to fail or vice versa.

---

## 7. What I could not verify, and what did not work

- **The frames are from a harness, not a live game.** Booting `court.html` end to end needs
  `/api/init-game`, and that endpoint resolves the away team by its real NAME (`Four Corners`)
  while `/roster/` only answers to the hyphenated slug (`Four-Corners`) and 500s on a space.
  Supplying `home_id`/`away_id` does not help — init-game derives the key from the name, and
  with the slug it fails with `documents must have only string keys, key was None`. Bridging the
  two spellings got past the roster load and then hit
  `TypeError: Cannot read properties of null (reading 'replace')` in app code. **That is an
  app/fixture mismatch with nothing to do with depth ordering**, and I stopped rather than
  keep patching around it. The harness (`tests/e2e/fixtures/depth-harness.html`) loads the REAL
  `createPhaserPlayer` → `createHeadshotMarkerV2` and the REAL applier, so the rendering under
  test is genuine; what is synthetic is the ten-player frame and the absence of a sim.
- **Therefore not proven: that the hook fires during a live turn**, and that the ordering looks
  right against real play geometry. That is the eye test, and it is what the window override is
  for.
- **Mid-tween crossings were not captured as a frame sequence.** The per-frame design makes the
  staleness question moot by construction, so I did not build the capture; I have not shown
  frames of a crossing.
- **`getStepBallHandlerId` is now a one-line delegate** to `playerDepth.resolveStepBallOwnerId`,
  which the applier calls every frame — so **the logic is live**. The `turnAnimation.js` wrapper
  itself is still uncalled. I left it rather than delete it: removing dead code there is
  unrelated to this change.
- **A design error I made and corrected**: hard promotion was first an additive `+1000`, which
  put the ball owner at 1508 — **above** `BALL_DEPTH`, so the carrier occluded the ball he was
  holding. It is now a separate bounded band (650–675), provably above every unpromoted player
  (max 608) and below the ball (1000), with a unit test pinning both inequalities.

## How to A/B without a rebuild

In the browser console, at any time:

```js
window.__GOB_DEPTH_ORDERING = true;              // ordering on
window.__GOB_DEPTH_MODE = "hard_promotion";      // or "tie_break"
window.__GOB_DEPTH_ORDERING = false;             // back to today's rendering
window.__GOB_DEPTH_REPORT();                     // read-only: depths, positions, ball depth
```

Both are read at call time. Turning it off live restores every container to depth 1 on the next
frame, so an A/B needs no reload.

## Constants introduced

| constant | value | effect |
|---|---|---|
| `USE_DEPTH_ORDERING` | **false** | Build-time kill switch. Off = today's rendering exactly. |
| `DEPTH_ORDERING_MODE` | `"tie_break"` | Which sub-mode. No value recommended. |
| `DEPTH_BASE` | 100 | Floor of the player band. |
| `DEPTH_PER_GRID_Y` | 10 | Grid-y weight. **The dominant term** — deliberately larger than both biases combined, so a tie-break can never reorder two players a full grid unit apart. |
| `DEPTH_OFFENCE_BIAS` | 3 | Tie-break, offence over defence. |
| `DEPTH_BALL_OWNER_BIAS` | 5 | Tie-break, ball owner over others. |
| `DEPTH_BAND_MAX` | 608 | *Derived*: the highest unpromoted depth. Exists so the next two are assertable. |
| `DEPTH_PROMOTED_BASE` | 650 | Sub-mode (ii) band floor — above 608, below 1000. |
| `DEPTH_PROMOTED_PER_GRID_Y` | 0.5 | Keeps promoted players y-ordered among themselves. |
| `COURT_MAX_Y` | 50 | Mirrors `gridToPixels`. Not a knob. |
| `BALL_DEPTH` | 1000 | Unified from three prior declarations. Unchanged in value. |
| `DEFAULT_PLAYER_DEPTH` | 1 | What the flag-off state restores to. |

Nothing tuned. Jamie tunes once, at the end.
