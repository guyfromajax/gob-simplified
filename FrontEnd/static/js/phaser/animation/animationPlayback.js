/**
 * Animation Playback Engine — pure renderer for the unified animation
 * step schema. See:
 *   - Schema (Python):  BackEnd/utils/animation_step_schema.py
 *   - Schema (JSDoc):   FrontEnd/static/js/phaser/animation/animationStepSchema.js
 *   - Design rationale: _documentation_master/projects/Animation_System_Updated.md
 *
 * Backend is the source of truth — it pre-computes start coords, end coords
 * (interrupted positions when applicable), and the step duration. This engine
 * just renders the linear tween from start → end at the prescribed duration.
 * No advance-trigger detection, no destination math, no per-player rate
 * calculation.
 *
 * SCOPE (this iteration): player tweens only. Ball-state-diff rendering and
 * action-specific side effects (shot animation, pass animation, foul flash,
 * etc.) are layered in subsequent iterations.
 */

import { gridToPixels } from "../utils/gridToPixels.js";
import { logEoqStep, logEoqSchemaStep, isEoqTraceEnabled } from "../utils/eoqDebugLog.js";
import { BALL_ATTACH_OFFSET } from "../setup/markerConfig.js";
import { attachBallToPlayer } from "./ballManager.js";
// IMPORTANT: import `detachBall` from BallControllerAdapter — not from
// ballManager / ballTween — because the latter only cancels tweens, while
// the BallController's per-frame `followCallback` keeps the ball snapped
// to the passer until properly detached via `ballController.detachFromPlayer`.
// Without this, schema-driven ball tweens get overwritten every frame by
// the follow callback and the pass renders as a teleport at step end.
import { detachBall } from "./BallControllerAdapter.js";
import { createBallTrail } from "./createBallTrail.js";
import { playGameSfx } from "../utils/gameSfx.js";
import {
  waitMsRespectingPause,
  waitWhileUserPaused,
  shouldFastForwardPlayback,
} from "./playbackPause.js";

// --- Ball-state helpers ----------------------------------------------------

function isBallAttached(ballState) {
  return Boolean(
    ballState &&
      Object.prototype.hasOwnProperty.call(ballState, "owner_player_id"),
  );
}

/**
 * Resolve the ball's grid coord from its state at a given step boundary:
 *   - attached(A) → that player's coord at the same boundary
 *   - in_flight   → ball.current_coords
 *   - loose       → ball.coords
 *
 * @param {import("./animationStepSchema.js").BallState} ballState
 * @param {Object<string, import("./animationStepSchema.js").GridCoord>} playerCoords
 * @returns {import("./animationStepSchema.js").GridCoord | null}
 */
function ballCoordFromState(ballState, playerCoords) {
  if (!ballState) return null;
  if (isBallAttached(ballState)) {
    return playerCoords[ballState.owner_player_id] || null;
  }
  // BallInFlight uses `current_coords`; BallLoose uses `coords`.
  return ballState.current_coords || ballState.coords || null;
}

/** Mirrors `BackEnd.constants.SHOT_BALL_GRID_PER_GAME_SECOND`. */
const SHOT_BALL_GRID_PER_GAME_SEC = 27;
/** Mirrors `BackEnd.constants.FREE_THROW_SHOT_GRID_PER_GAME_SECOND` (UESS §11.1). */
const FREE_THROW_BALL_GRID_PER_GAME_SEC = 12;
/** Minimum step-playback wait for a shot [ball_flight] step (FE only).
 * Keeps the camera on the rim long enough for short shots to read.
 * Main-branch parity. Does not change backend T. */
const SHOT_BALL_MIN_WALL_CLOCK_MS = 400;
/** Minimum ball-tween wall-clock duration for a shot (FE only).
 * Keeping the tween
 * floor equal to the step floor prevents the ball/SFX from reaching the rim
 * early, then idling before result/bounce handling begins. */
const SHOT_BALL_MIN_TWEEN_MS = SHOT_BALL_MIN_WALL_CLOCK_MS;
/** Mirrors `BackEnd.constants.PASS_GRID_SPOTS_PER_GAME_SECOND`. */
const PASS_BALL_GRID_PER_GAME_SEC = 24;

function shouldTracePlayback(scene = null) {
  const flag = typeof window !== "undefined" ? window.UESS_TRACE_PLAYBACK : undefined;
  if (flag === false) return false;
  if (flag === true) return true;
  return Boolean(scene?.__uessTracePlayback);
}

function tracePlayback(scene, label, payload = {}) {
  return;
}

function isShotBallMotionStep(step) {
  return step?.start?.ball_motion_style === "shot";
}

function shotReleasePlayerId(step) {
  const actions = step?.start?.action || {};
  for (const [playerId, action] of Object.entries(actions)) {
    if (action === "shoot") return String(playerId);
  }
  return null;
}

function shouldAdvanceToShotFlightOnShooterSettle(step, steps = null) {
  const shooterId = shotReleasePlayerId(step);
  const next = step?.end?.next;
  if (!shooterId || next?.kind !== "next_step") {
    return { shouldAdvance: false, shooterId: null };
  }
  const nextStep = Array.isArray(steps) ? steps[next.index] : null;
  return {
    shouldAdvance: isShotBallMotionStep(nextStep),
    shooterId,
  };
}

/** Backend stamps `advance_trigger.metadata.free_throw_shot` on FT [ball_flight]. */
function isFreeThrowShotStep(step) {
  const meta = step?.start?.advance_trigger?.metadata;
  if (!meta) return false;
  if (meta.free_throw_shot === true) return true;
  const rate = Number(meta.ball_grid_per_game_second);
  return Number.isFinite(rate) && rate === FREE_THROW_BALL_GRID_PER_GAME_SEC;
}

/** Rare FT-only: mid-sequence ball snap bounce → shooter (attached). */
function isFtReturnTeleportStep(step) {
  return step?.start?.advance_trigger?.metadata?.kind === "ft_return_teleport";
}

function shotBallGridRate(step) {
  return isFreeThrowShotStep(step)
    ? FREE_THROW_BALL_GRID_PER_GAME_SEC
    : SHOT_BALL_GRID_PER_GAME_SEC;
}

function shotBallTweenDurationMs(gridDist, clockSecondMs, step = null) {
  const dist = Math.max(0, Number(gridDist) || 0);
  const rate = shotBallGridRate(step);
  const fromRate = Math.round((dist / rate) * clockSecondMs);
  if (step && isFreeThrowShotStep(step)) {
    return Math.max(50, fromRate);
  }
  return Math.max(SHOT_BALL_MIN_TWEEN_MS, fromRate);
}

/** Skewed parabola height factor 0→1→0; peaks at `apexPos` (backend-authored). */
function shotBallArcShape(p, apexPos) {
  const pos = Math.max(1e-6, Math.min(1 - 1e-6, Number(apexPos) || 0.54));
  const t = Math.max(0, Math.min(1, Number(p) || 0));
  if (t < pos) {
    const u = (pos - t) / pos;
    return 1 - u * u;
  }
  const u = (t - pos) / (1 - pos);
  return 1 - u * u;
}

/** Mid-skeleton HCO pass: ownership transfers, ball uses pass motion rate. */
function isSchemaPassStep(step) {
  const startOwner = isBallAttached(step?.start?.ball)
    ? step.start.ball.owner_player_id
    : null;
  const endOwner = isBallAttached(step?.end?.ball)
    ? step.end.ball.owner_player_id
    : null;
  return (
    step?.start?.ball_motion_style === "pass" &&
    Boolean(startOwner) &&
    Boolean(endOwner) &&
    String(startOwner) !== String(endOwner)
  );
}

function schemaPassStartOwnerId(step) {
  return isBallAttached(step?.start?.ball)
    ? String(step.start.ball.owner_player_id)
    : null;
}

function schemaPassEndOwnerId(step) {
  return isBallAttached(step?.end?.ball)
    ? String(step.end.ball.owner_player_id)
    : null;
}

function withExpectedDuration(promise, expectedDurationMs = 0) {
  if (promise && typeof promise === "object") {
    promise.expectedDurationMs = Math.max(0, Math.round(Number(expectedDurationMs) || 0));
  }
  return promise;
}

async function awaitTweenOrDuration(scene, tweenPromise, expectedDurationMs, fallbackResult = undefined) {
  if (!tweenPromise || typeof tweenPromise.then !== "function") {
    return fallbackResult;
  }
  const fallbackMs = Math.max(0, Math.round(Number(expectedDurationMs) || 0));
  if (fallbackMs <= 0) {
    return tweenPromise;
  }
  return Promise.race([
    tweenPromise,
    waitMsRespectingPause(scene, fallbackMs).then(() => fallbackResult),
  ]);
}

/**
 * Schedule `timed_sfx` cues relative to a base moment (ball arrival by default).
 * @param {Phaser.Scene} scene
 * @param {import("./animationStepSchema.js").TimedSfx[]} timedSfx
 * @param {number} [baseDelayMs=0]
 */
function scheduleTimedSfxCues(scene, timedSfx, baseDelayMs = 0) {
  if (!scene || !Array.isArray(timedSfx)) return;
  for (const cue of timedSfx) {
    if (!cue || !cue.file) continue;
    const delay = baseDelayMs + Math.max(0, Number(cue.delay_ms) || 0);
    const playCue = () => playGameSfx(
      scene,
      cue.file,
      typeof cue.volume === "number" ? cue.volume : 0.7,
      { event: cue.event || "timed_sfx" },
    );
    if (delay === 0) {
      playCue();
    } else if (scene.time?.delayedCall) {
      scene.time.delayedCall(delay, playCue);
    } else {
      setTimeout(playCue, delay);
    }
  }
}

/**
 * Spawn the ball's own linear tween from its computed start coord to its
 * computed end coord over the step duration. This single dispatch handles
 * every diff case from the schema:
 *   - attached(A) → attached(A): tween parallel to A's player tween (same path).
 *   - attached(A) → attached(B): pass A→B over duration T.
 *   - attached(A) → in_flight: pass started, ends at interrupted position.
 *   - in_flight → attached(B): in-flight ball lands on B.
 *   - in_flight → in_flight: ball continues toward receiver, doesn't complete.
 *
 * Ownership state changes are applied at step end via snapBallToEndState.
 */
function renderBallTransition(scene, step, sprites, ballSprite, durationMs, width, height, clockSecondMs, options = {}) {
  if (!ballSprite) return withExpectedDuration(Promise.resolve({ tweenStarted: false }), 0);
  const startCoord = options.ballStartCoordOverride
    ?? ballCoordFromState(step.start.ball, step.start.coords);
  // ball_arrival_coord override: when the ball's tween should terminate at a
  // backend-computed meet-point rather than the end-state owner's step-end
  // coord. Used by HCO pass steps where the receiver may still be moving
  // when the ball arrives — the meet-point is the receiver's interpolated
  // position at ball-arrival time. Backend pre-resolves; FE consumes.
  const endCoord = options.ballEndCoordOverride
    ?? step.start?.ball_arrival_coord
    ?? ballCoordFromState(step.end.ball, step.end.coords);

  if (!startCoord || !endCoord) return withExpectedDuration(Promise.resolve({ tweenStarted: false }), 0);

  // When the ball is attached to a player, its visual anchor is the player's
  // hip (sprite + BALL_ATTACH_OFFSET); when in flight or loose, it tracks the
  // raw ball coordinate. Compose the offset conditionally so both modes work.
  const startAttachOffset = isBallAttached(step.start.ball) ? BALL_ATTACH_OFFSET : { x: 0, y: 0 };
  const endAttachOffset = isBallAttached(step.end.ball) ? BALL_ATTACH_OFFSET : { x: 0, y: 0 };

  // Snap-to-start. If previous step ended at the same coord, this is a no-op.
  const startPx = gridToPixels(startCoord.x, startCoord.y, width, height);
  startPx.x += startAttachOffset.x;
  startPx.y += startAttachOffset.y;
  ballSprite.setPosition(startPx.x, startPx.y);

  if (
    Math.abs(startCoord.x - endCoord.x) < 1e-6 &&
    Math.abs(startCoord.y - endCoord.y) < 1e-6
  ) {
    return withExpectedDuration(Promise.resolve({ tweenStarted: false }), 0);
  }

  // Ownership-change handling. When the ball changes owners between steps
  // (e.g., a pass from passer A to receiver B), the ball sprite is still
  // parented to A from the prior step's attach. A bare `scene.tweens.add`
  // would tween world coords on a sprite whose render position is dictated
  // by A's parent transform — so the ball appears glued to A for the whole
  // step and then snaps to B at step end (visible teleport).
  // Detaching here releases the parent transform so the world-coord tween
  // renders correctly. `snapBallToEndState` re-attaches to the end owner.
  const startOwner = isBallAttached(step.start.ball)
    ? step.start.ball.owner_player_id
    : null;
  const endOwner = isBallAttached(step.end.ball)
    ? step.end.ball.owner_player_id
    : null;

  // Pass steps: release at step start in parallel with all player tweens
  // (passer, receivers, defenders). Re-attach to the passer first so
  // `detachBall` is not a no-op when the prior sub-step left the controller
  // detached (common after shot / loose-ball hops).
  if (isSchemaPassStep(step)) {
    const passerSprite = sprites?.[startOwner];
    if (passerSprite) {
      attachBallToPlayer(scene, ballSprite, passerSprite, {
        debugInfo: { reason: "schema_pass_step_start" },
      });
    }
  }

  // Detach when ownership changes (existing case) OR when start is unattached
  // (BallLoose / BallInFlight) — the schema says the ball isn't parented to a
  // player at step start, so we must release any lingering BallController
  // follow callback from a prior turn before tweening (otherwise the per-frame
  // follow overrides our tween and the ball appears to follow the prior owner).
  const startIsAttached = startOwner !== null;
  const needsDetach = startIsAttached
    ? startOwner !== endOwner
    : true;
  if (needsDetach) {
    detachBall(scene, ballSprite);
    // `BallController.detachFromPlayer` calls `ballSprite.setVisible(false)`
    // when the ball isn't flagged as in-flight — which is the case here since
    // we're managing the flight via this tween, not via the controller's
    // startFlight/endFlight primitives. Force visibility back on so the
    // tween renders. `snapBallToEndState` will re-attach (and re-show) at
    // step end via `attachBallToPlayer`.
    ballSprite.setVisible(true);
    // startPx already includes startAttachOffset above; this is the same starting hip position.
    ballSprite.setPosition(startPx.x, startPx.y);

    // Outlet-pass SFX. Fires at the moment of detach (ball leaves passer's
    // hand). Quality gate uses the same `outlet_score` metadata the trail
    // effect reads, so the audio + visual stay in sync.
    //
    const outletScoreForSfx = step.start?.advance_trigger?.metadata?.outlet_score;
    if (typeof outletScoreForSfx === "number") {
      const sfxFile = outletScoreForSfx >= 50
        ? "outlet-pass-great.wav"
        : "outlet-pass-bad.wav";
      playGameSfx(scene, sfxFile, 0.7, { event: "outlet_pass_release" });
    }

    // Generic ball-release SFX cue (SFX_System.md). Backend stamps
    // the resolved filename / tier; FE just plays. Used by HCO mid-skeleton
    // pass steps (pass-{strong|medium|weak}.wav) AND the [ball_flight]
    // sub-step (tiered shot launch from `shot_score_pre_defense`) AND each
    // RATTLE hop (`rattle-leather.wav`). All FE-side variant decisions for
    // shots now flow through this backend-resolved cue — see
    // `_build_post_shot_sub_steps` in `BackEnd/engine/skeleton_step_emitter.py`.
    const releaseSfx = step.start?.sfx_on_ball_release;
    console.warn('[SHOT-SFX] ball_release | file=', releaseSfx?.file, '| event=', releaseSfx?.event);
    if (releaseSfx?.file) {
      playGameSfx(
        scene,
        releaseSfx.file,
        typeof releaseSfx.volume === "number" ? releaseSfx.volume : 0.7,
        { event: releaseSfx.event || "ball_release" },
      );
    }
    if (options.turnData?.flss_vo) {
      import("../utils/gameSfx.js").then(({ playFlssVoSfx }) => {
        playFlssVoSfx(scene, options.turnData);
      });
    }
  }

  const endPx = gridToPixels(endCoord.x, endCoord.y, width, height);
  endPx.x += endAttachOffset.x;
  endPx.y += endAttachOffset.y;

  // Sharp-outlet ball trail: emitted by the backend in
  // `_build_outlet_pass_step` (covert_release_step_emitter.py) as
  // `step.start.advance_trigger.metadata.outlet_score`. Trail fires when the
  // outlet pass is high-quality (>= 50). Self-cleans after `durationMs`.
  // The same threshold gates the `outlet-pass-great.wav` SFX in the
  // ownership-change branch above, so audio + visual stay in sync.
  const outletScore = step.start?.advance_trigger?.metadata?.outlet_score;
  if (typeof outletScore === "number" && outletScore >= 50) {
    createBallTrail(scene, ballSprite, durationMs);
  }

  // Ball motion style override. Default: tween over step T. When
  // step.start.ball_motion_style is set, the ball moves at a fixed
  // grid/game-sec rate that mirrors the backend constant — so the FE
  // wall-clock duration matches the backend's `ball_pass_t` (or shot T)
  // exactly. Critical: distance must be in GRID units, not pixels.
  // `gridToPixels` uses anisotropic scaling (court is 100×50 grid but
  // canvas is 1229×768 → 12.29 px/grid for X, 15.36 px/grid for Y), so a
  // pixel-distance approach over-counts Y-heavy moves and the ball arrives
  // after step T ends.
  //   "shot" — 27 grid/game-sec (HCO) or 12 (FT via metadata), min 400 ms for HCO only
  //   "pass" — PASS_GRID_SPOTS_PER_GAME_SECOND (24)
  let ballDurationMs = durationMs;
  if (isShotBallMotionStep(step)) {
    const dxGrid = endCoord.x - startCoord.x;
    const dyGrid = endCoord.y - startCoord.y;
    ballDurationMs = shotBallTweenDurationMs(
      Math.hypot(dxGrid, dyGrid),
      clockSecondMs,
      step,
    );
  } else if (step.start?.ball_motion_style === "pass") {
    const dxGrid = endCoord.x - startCoord.x;
    const dyGrid = endCoord.y - startCoord.y;
    const gridDist = Math.hypot(dxGrid, dyGrid);
    const passRate =
      step.start?.pass_grid_per_game_second
      ?? step.start?.advance_trigger?.metadata?.pass_grid_per_game_second
      ?? PASS_BALL_GRID_PER_GAME_SEC;
    ballDurationMs = Math.max(
      50,
      Math.round((gridDist / passRate) * clockSecondMs),
    );
  }

  // Hot-shot flame trail: backend stamps ``advance_trigger.metadata.hot_shot_trail``
  // on schema [ball_flight] when shot_score_pre_defense > 210 (strong tier).
  // Same threshold as three-strong.wav / legacy ShotAnimationSystem.
  if (
    isShotBallMotionStep(step)
    && !isFreeThrowShotStep(step)
    && step.start?.advance_trigger?.metadata?.hot_shot_trail
  ) {
    createBallTrail(scene, ballSprite, ballDurationMs);
  }

  // When ball_motion_style="pass" and the step ends with ownership on a
  // sprite, attach the ball to that sprite on tween completion (not at
  // step end). The ball then follows the receiver via the BallController
  // parent transform for the remainder of step T — matches the
  // "ball lands and travels with the receiver" intent for HCO passes.
  let attachOnCompleteSprite = null;
  if (step.start?.ball_motion_style === "pass") {
    const endBall = step.end?.ball;
    if (endBall && Object.prototype.hasOwnProperty.call(endBall, "owner_player_id")) {
      attachOnCompleteSprite = sprites?.[endBall.owner_player_id] || null;
    }
  }

  const shotBallArc = step.start?.advance_trigger?.metadata?.shot_ball_arc;
  const arcApexPx = Number(shotBallArc?.apex_px);
  const arcApexPos = Number(shotBallArc?.apex_pos);
  const useSkewedArc = (
    isShotBallMotionStep(step)
    && Number.isFinite(arcApexPx)
    && arcApexPx > 0
    && Number.isFinite(arcApexPos)
  );

  const onBallTweenComplete = (resolve) => {
    if (attachOnCompleteSprite) {
      attachBallToPlayer(scene, ballSprite, attachOnCompleteSprite);
    }
    const arrivalSfx = step.start?.sfx_on_ball_arrival;
    if (arrivalSfx?.file) {
      playGameSfx(
        scene,
        arrivalSfx.file,
        typeof arrivalSfx.volume === "number" ? arrivalSfx.volume : 0.7,
        { event: arrivalSfx.event || "ball_arrival" },
      );
    }
    const timedSfx = step.start?.timed_sfx;
    if (Array.isArray(timedSfx) && timedSfx.length > 0) {
      scheduleTimedSfxCues(scene, timedSfx);
    }
    resolve({ tweenStarted: true });
  };

  const tweenPromise = new Promise((resolve) => {
    if (useSkewedArc) {
      const progress = { t: 0 };
      scene.tweens.add({
        targets: progress,
        t: 1,
        duration: ballDurationMs,
        ease: "Linear",
        onUpdate: () => {
          const p = progress.t;
          const lift = arcApexPx * shotBallArcShape(p, arcApexPos);
          ballSprite.setPosition(
            startPx.x + (endPx.x - startPx.x) * p,
            startPx.y + (endPx.y - startPx.y) * p - lift,
          );
        },
        onComplete: () => onBallTweenComplete(resolve),
        onStop: () => resolve({ tweenStarted: true }),
      });
      return;
    }
    scene.tweens.add({
      targets: ballSprite,
      x: endPx.x,
      y: endPx.y,
      duration: ballDurationMs,
      ease: "Linear",
      onComplete: () => onBallTweenComplete(resolve),
      onStop: () => resolve({ tweenStarted: true }),
    });
  });
  return withExpectedDuration(tweenPromise, ballDurationMs);
}

/**
 * At step end: snap ball to exact end coord and reconcile ownership state
 * with `step.end.ball`. Called after the wall-clock wait, alongside the
 * player snap.
 */
function snapBallToStartState(scene, step, sprites, ballSprite, width, height) {
  if (!ballSprite || !step?.start?.ball) return;
  const startBall = step.start.ball;
  const startCoord = ballCoordFromState(startBall, step.start.coords);
  if (!startCoord) return;

  const startPx = gridToPixels(startCoord.x, startCoord.y, width, height);
  const startAttachOffset = isBallAttached(startBall) ? BALL_ATTACH_OFFSET : { x: 0, y: 0 };
  ballSprite.setPosition(startPx.x + startAttachOffset.x, startPx.y + startAttachOffset.y);

  if (isBallAttached(startBall)) {
    const ownerSprite = sprites[startBall.owner_player_id];
    if (ownerSprite) {
      attachBallToPlayer(scene, ballSprite, ownerSprite);
    }
  } else {
    detachBall(scene, ballSprite);
  }
}

function snapSpritesToStepStart(scene, step, sprites, ballSprite) {
  if (!scene || !step?.start?.coords || !sprites) return;
  const width = scene.game?.config?.width;
  const height = scene.game?.config?.height;
  for (const [playerId, startCoord] of Object.entries(step.start.coords)) {
    const sprite = sprites[playerId];
    if (!sprite || !startCoord) continue;
    const startPx = gridToPixels(startCoord.x, startCoord.y, width, height);
    sprite.setPosition(startPx.x, startPx.y);
    sprite.gridX = startCoord.x;
    sprite.gridY = startCoord.y;
  }
  snapBallToStartState(scene, step, sprites, ballSprite, width, height);
}

function snapBallToEndState(scene, step, sprites, ballSprite, width, height) {
  if (!ballSprite) return;
  const endBall = step.end.ball;
  if (!endBall) return;
  const endCoord = ballCoordFromState(endBall, step.end.coords);
  if (!endCoord) return;

  const endPx = gridToPixels(endCoord.x, endCoord.y, width, height);
  // Compose ball-attach offset when ball ends attached to a player (anchor at hip).
  const endAttachOffset = isBallAttached(endBall) ? BALL_ATTACH_OFFSET : { x: 0, y: 0 };
  ballSprite.setPosition(endPx.x + endAttachOffset.x, endPx.y + endAttachOffset.y);

  if (isBallAttached(endBall)) {
    const ownerSprite = sprites[endBall.owner_player_id];
    if (ownerSprite) {
      attachBallToPlayer(scene, ballSprite, ownerSprite);
    }
  } else {
    detachBall(scene, ballSprite);
  }
}

function resolveScenePlayerRef(scene, rawId, sprites = null) {
  if (!scene || rawId == null) return { id: null, sprite: null, info: null };
  const sid = String(rawId);
  const playerSprites = sprites || scene.playerSprites || {};
  const playerInfo = scene.playerInfo || {};

  if (playerSprites[sid] || playerInfo[sid]) {
    return { id: sid, sprite: playerSprites[sid] || null, info: playerInfo[sid] || null };
  }

  for (const [playerId, sprite] of Object.entries(playerSprites)) {
    if (!sprite) continue;
    if (String(sprite.playerId ?? sprite.id ?? "") === sid) {
      return { id: String(playerId), sprite, info: playerInfo[playerId] || null };
    }
  }

  return { id: sid, sprite: null, info: null };
}

function normalizeAnnouncementPlayerData(playerData) {
  if (!playerData) return null;
  const playerId =
    playerData.playerId ??
    playerData.player_id ??
    playerData.id ??
    playerData._id ??
    null;
  return playerId ? { ...playerData, playerId: String(playerId) } : playerData;
}

function inferStepAnnouncementPlayerData(announcement, step, turnData = null) {
  const directPlayerData = normalizeAnnouncementPlayerData(
    announcement?.player_data || announcement?.playerData || null,
  );
  return directPlayerData?.playerId ? directPlayerData : (directPlayerData || null);
}

function enrichStepAnnouncementPlayerData(scene, playerData, sprites = null) {
  if (!playerData?.playerId) return playerData || null;
  const ref = resolveScenePlayerRef(scene, playerData.playerId, sprites);
  const resolvedId = ref.id || String(playerData.playerId);
  return {
    ...playerData,
    playerId: resolvedId,
    photo: playerData.photo || ref.sprite?.photo || ref.info?.photo || null,
    name: playerData.name || ref.info?.name || ref.sprite?.name || "",
    jersey:
      playerData.jersey ??
      ref.info?.jersey ??
      ref.info?.jerseyNumber ??
      ref.info?.jersey_number ??
      ref.sprite?.jersey ??
      "",
    position:
      playerData.position ||
      ref.info?.position ||
      ref.info?.primary_position ||
      ref.info?.pos ||
      ref.sprite?.position ||
      "",
  };
}

function startSchemaPlayerTween(scene, sprite, endCoord, durationMs, width, height) {
  if (!scene || !sprite || !endCoord) {
    return Promise.resolve();
  }
  const endPx = gridToPixels(endCoord.x, endCoord.y, width, height);
  return new Promise((resolve) => {
    scene.tweens.add({
      targets: sprite,
      x: endPx.x,
      y: endPx.y,
      duration: Math.max(50, Math.round(durationMs)),
      ease: "Linear",
      onComplete: resolve,
      onStop: resolve,
    });
  });
}


/**
 * Run an in-step announcement: pause clocks, show announcement, await hold,
 * resume clocks. Used by both `step.start.announcement` and
 * `step.end.announcement` hooks.
 *
 * @param {Phaser.Scene} scene
 * @param {import("./animationStepSchema.js").Announcement} announcement
 */
async function runStepAnnouncement(scene, announcement, sprites = null, step = null, turnData = null) {
  if (!scene || !announcement?.text) return;
  const reason = "step_announcement";
  scene.gameClock?.pause?.(reason);
  scene.shotClock?.pause?.(reason);

  // Announcement-tied SFX is carried on the payload (`data.sfx`) and played
  // by court.html at overlay mount — single source of truth, synced to the
  // visual entry per SFX_System.md. Backend-stamped `meta.sfx` keys
  // (e.g. "no_fast_break", "fb_outlet_denied_court", "steal") are resolved
  // to filenames inside `showSecondaryAnnouncement`.

  try {
    const {
      showAnnouncement,
      showSecondaryAnnouncement,
      showAndOneAnnouncement,
    } = await import("../utils/announcements.js");
    const inferredPlayerData = inferStepAnnouncementPlayerData(announcement, step, turnData);
    const playerData = enrichStepAnnouncementPlayerData(scene, inferredPlayerData, sprites);
    if (announcement.style === "and_one") {
      // Backend stamps `style: "and_one"` for the two-portrait foul card
      // (Announcement_System.md). Resolve shooter + fouler from
      // announcement.player_data ({ playerId, foulerId }); fall back to the
      // single-row variant when either resolution fails. SFX comes from
      // `announcement.meta.sfx` (backend-stamped); no FE hardcode.
      const shooterId =
        announcement.player_data?.playerId
        ?? announcement.player_data?.shooterId;
      const foulerId =
        announcement.player_data?.foulerId
        ?? turnData?.foul_player_id
        ?? turnData?.foul_player?.player_id;
      const shooterData = shooterId
        ? enrichStepAnnouncementPlayerData(scene, { playerId: String(shooterId) }, sprites)
        : playerData;
      const foulerData = foulerId
        ? enrichStepAnnouncementPlayerData(scene, { playerId: String(foulerId) }, sprites)
        : null;
      const team = announcement.team || "home";
      const andOneMeta = { ...(announcement.meta || {}), scene };
      if (shooterData?.playerId && foulerData?.playerId) {
        showAndOneAnnouncement(team, shooterData, foulerData, andOneMeta);
      } else {
        showAnnouncement(announcement.text, team, shooterData, andOneMeta);
      }
    } else if (announcement.style === "secondary") {
      showSecondaryAnnouncement(
        announcement.text,
        announcement.team || "neutral",
        playerData,
        { ...(announcement.meta || {}), scene },
      );
    } else {
      showAnnouncement(
        announcement.text,
        announcement.team || "neutral",
        playerData,
        { ...(announcement.meta || {}), scene },
      );
    }
    if (
      turnData
      && String(announcement.text || "").trim().toLowerCase() === "airball!"
    ) {
      turnData._airballAnnounced = true;
    }
    if (
      turnData
      && String(announcement.text || "").trim().toLowerCase() === "block!"
    ) {
      turnData._blockAnnounced = true;
    }
  } catch (err) {
    console.warn("runStepAnnouncement: showAnnouncement failed", err);
  }
  const holdMs = Number.isFinite(announcement.hold_ms) && announcement.hold_ms > 0
    ? announcement.hold_ms
    : 1000;
  await waitMsRespectingPause(scene, holdMs);
  scene.gameClock?.resume?.(reason);
  scene.shotClock?.resume?.(reason);
}


/**
 * Play a single animation step. Spawns linear tweens for each player whose
 * coords change between start and end, waits the prescribed duration, snaps
 * sprites to the exact end coords, and returns the next-step pointer.
 *
 * Contract: caller ensures sprites are at `step.start.coords` when this is
 * invoked. Engine does not snap-to-start; sprite drift between steps is the
 * caller's bug to fix.
 *
 * Announcement hooks: optional `step.start.announcement` plays BEFORE the
 * step's tweens fire. Optional `step.end.announcement` plays AFTER tweens
 * complete and sprites snap, BEFORE returning the `next` pointer. Both pause
 * `gameClock` + `shotClock` for the announcement's `hold_ms`.
 *
 * @param {Phaser.Scene} scene
 * @param {import("./animationStepSchema.js").AnimationStep} step
 * @param {Object<string, Phaser.GameObjects.Sprite>} sprites  Keyed by stringified player_id.
 * @param {Phaser.GameObjects.Sprite} [ballSprite]  Required for ball-state-diff rendering.
 * @returns {Promise<import("./animationStepSchema.js").NextStep>}
 */
export async function playAnimationStep(scene, step, sprites, ballSprite, options = {}) {
  if (!scene || !step || !sprites) {
    throw new Error("playAnimationStep: scene, step, and sprites are required");
  }

  await waitWhileUserPaused(scene);
  if (shouldFastForwardPlayback(scene)) {
    return step.end?.next ?? null;
  }

  const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 350;
  const durationMs = Math.max(
    50,
    Math.round(step.end.time_elapsed * clockSecondMs),
  );

  const width = scene.game?.config?.width;
  const height = scene.game?.config?.height;

  // step.start.sfx_on_step_start: play at step-processing start, before any tween / ball motion.
  // Distinct from sfx_on_ball_release (occupied by the shot/pass launch sound). Used by Dynamic
  // HCO Motion to fire the hot-read coach VO as the break begins (SFX_System.md).
  const stepStartSfx = step.start?.sfx_on_step_start;
  if (stepStartSfx?.file) {
    playGameSfx(
      scene,
      stepStartSfx.file,
      typeof stepStartSfx.volume === "number" ? stepStartSfx.volume : 0.7,
      { event: stepStartSfx.event || "step_start" },
    );
  }

  // step.start.announcement: play before tweens fire.
  if (step.start?.announcement) {
    await runStepAnnouncement(scene, step.start.announcement, sprites, step, options.turnData);
  }

  // FT mid-sequence return: instant ball snap to shooter — no tween (schema-only exception).
  if (isFtReturnTeleportStep(step)) {
    const width = scene.game?.config?.width;
    const height = scene.game?.config?.height;
    for (const [playerId, endCoord] of Object.entries(step.end.coords || {})) {
      const sprite = sprites[playerId];
      if (!sprite || !endCoord) continue;
      const endPx = gridToPixels(endCoord.x, endCoord.y, width, height);
      sprite.setPosition(endPx.x, endPx.y);
      sprite.gridX = endCoord.x;
      sprite.gridY = endCoord.y;
    }
    if (ballSprite) {
      ballSprite.setVisible(true);
    }
    snapBallToEndState(scene, step, sprites, ballSprite, width, height);
    if (step.end?.announcement) {
      await runStepAnnouncement(scene, step.end.announcement, sprites, step, options.turnData);
    }
    tracePlayback(scene, "step:ft_return_teleport", {
      turnIndex: options.turnData?.index ?? null,
      targetPlayerId: step.start?.advance_trigger?.metadata?.target_player_id ?? null,
    });
    return step.end?.next ?? null;
  }

  // timed_sfx fires from ball tween onComplete (see renderBallTransition), or
  // from the step-end fallback when the ball tween early-returns.

  // Spawn one linear tween per player whose start coord differs from end coord.
  // Backend stamps per-player tween durations on step.start.tween_durations
  // (in game-seconds); convert to ms via clockSecondMs. Players who finish
  // before step T sit idle at their end coord until the wall-clock timer
  // below fires — produces the natural "settle and wait" feel rather than
  // stretching every player's tween across the gating player's duration.
  // When tween_durations is absent (legacy emitters), fall back to step T.
  const perPlayerDurations = step.start.tween_durations || {};
  const isPassStep = isSchemaPassStep(step);
  const shotReleaseGate = shouldAdvanceToShotFlightOnShooterSettle(step, options.steps);
  const releaseShotOnShooterSettle = shotReleaseGate.shouldAdvance;
  const shotReleaseShooterId = shotReleaseGate.shooterId;
  let shooterTweenPromise = Promise.resolve({ tweenStarted: false });
  let shooterTweenDurationMs = 0;
  let ballTransitionPromise = Promise.resolve({ tweenStarted: false });
  const stepStartedAtMs = performance.now();
  const activeStepTweenSprites = [];
  const passStartOwnerId = isPassStep
    ? schemaPassStartOwnerId(step)
    : null;
  const passEndOwnerId = isPassStep
    ? schemaPassEndOwnerId(step)
    : null;

  const stepWaitMs =
    isShotBallMotionStep(step) && !isFreeThrowShotStep(step)
      ? Math.max(durationMs, SHOT_BALL_MIN_WALL_CLOCK_MS)
      : durationMs;

  if (shouldTracePlayback(scene)) {
    let movers = 0;
    for (const [playerId, startCoord] of Object.entries(step.start.coords || {})) {
      const endCoord = step.end?.coords?.[playerId];
      if (!startCoord || !endCoord) continue;
      if (
        Math.abs(endCoord.x - startCoord.x) >= 1e-6 ||
        Math.abs(endCoord.y - startCoord.y) >= 1e-6
      ) {
        movers += 1;
      }
    }
    tracePlayback(scene, "step:start", {
      turnIndex: options.turnData?.index ?? null,
      resultType: options.turnData?.result_type ?? null,
      currentTurn: options.turnData?.current_turn ?? null,
      stepId: step.id ?? null,
      durationMs,
      stepWaitMs,
      timeElapsed: step.end?.time_elapsed ?? null,
      advanceTrigger: step.start?.advance_trigger?.condition ?? null,
      advanceTriggerReason: step.start?.advance_trigger?.metadata?.reason ?? null,
      advanceTriggerTargetPlayerId: step.start?.advance_trigger?.metadata?.target_player_id ?? null,
      next: step.end?.next ?? null,
      isPassStep,
      releaseShotOnShooterSettle,
      shotReleaseShooterId,
      passStartOwnerId,
      passEndOwnerId,
      movers,
      spriteCount: Object.keys(sprites || {}).length,
      hasBallSprite: Boolean(ballSprite),
      ballVisible: ballSprite?.visible ?? null,
      isPaused: scene?.isPaused ?? null,
      skipToEnd: scene?.skipToEnd ?? null,
    });
  }

  // step.start.flourish: in-place render-space micro-movements (e.g. defender
  // reach-in on a steal contest). Fire-and-forget, in PARALLEL with the player
  // tweens — must NOT block step T. Render-space only; never touches gameplay
  // coords. Mirrors the announcement/sfx hook dispatch pattern.
  const flourishMap = step.start?.flourish;
  if (flourishMap && typeof flourishMap === "object") {
    import("./flourishes.js")
      .then(({ runFlourish }) => {
        for (const [playerId, flourish] of Object.entries(flourishMap)) {
          const sprite = sprites[playerId];
          if (!sprite || !flourish) continue;
          runFlourish(scene, sprite, flourish, { ballSprite, turnData: options.turnData });
        }
      })
      .catch((err) => console.warn("flourish dispatch failed", err));
  }

  for (const [playerId, startCoord] of Object.entries(step.start.coords)) {
    const sprite = sprites[playerId];
    const endCoord = step.end.coords[playerId];
    if (!sprite || !endCoord) continue;

    // No-op when start and end match (within float epsilon).
    const dx = endCoord.x - startCoord.x;
    const dy = endCoord.y - startCoord.y;
    if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) continue;

    const playerGameSec = perPlayerDurations[playerId];
    const playerDurationMs =
      typeof playerGameSec === "number" && playerGameSec > 0
        ? Math.max(50, Math.round(playerGameSec * clockSecondMs))
        : durationMs;

    const tweenPromise = startSchemaPlayerTween(scene, sprite, endCoord, playerDurationMs, width, height);
    activeStepTweenSprites.push(sprite);
    if (releaseShotOnShooterSettle && String(playerId) === shotReleaseShooterId) {
      shooterTweenPromise = tweenPromise;
      shooterTweenDurationMs = playerDurationMs;
    }
  }

  ballTransitionPromise = renderBallTransition(
    scene,
    step,
    sprites,
    ballSprite,
    durationMs,
    width,
    height,
    clockSecondMs,
    options,
  );

  if (isPassStep) {
    tracePlayback(scene, "pass:release", {
      turnIndex: options.turnData?.index ?? null,
      stepId: step.id ?? null,
      elapsedMs: Math.round(performance.now() - stepStartedAtMs),
      passStartOwnerId,
      passEndOwnerId,
      ballArrivalCoord: step.start?.ball_arrival_coord ?? null,
      ballDurationMs: ballTransitionPromise?.expectedDurationMs ?? null,
    });
  }

  if (releaseShotOnShooterSettle) {
    const shotGateResult = await awaitTweenOrDuration(
      scene,
      shooterTweenPromise,
      shooterTweenDurationMs,
      { tweenStarted: false, durationFallback: true },
    );
    if (scene?.tweens?.killTweensOf) {
      for (const sprite of activeStepTweenSprites) {
        scene.tweens.killTweensOf(sprite);
      }
      if (ballSprite) {
        scene.tweens.killTweensOf(ballSprite);
      }
      if (scene.ballShadowSprite) {
        scene.tweens.killTweensOf(scene.ballShadowSprite);
      }
    }
    tracePlayback(scene, "shot:release-on-shooter-settle", {
      turnIndex: options.turnData?.index ?? null,
      stepId: step.id ?? null,
      shooterId: shotReleaseShooterId,
      shooterTweenDurationMs,
      elapsedMs: Math.round(performance.now() - stepStartedAtMs),
      shotGateResult,
      next: step.end?.next ?? null,
    });
    return step.end?.next ?? null;
  }

  // Wait the prescribed wall-clock duration (only while not user-paused).
  // Shot [ball_flight] steps: FE playback floor so short flights are visible
  // (FE playback floor). Backend step T / clocks unchanged.
  const elapsedBeforeWaitMs = performance.now() - stepStartedAtMs;
  await waitMsRespectingPause(scene, Math.max(0, stepWaitMs - elapsedBeforeWaitMs));
  if (shouldFastForwardPlayback(scene)) {
    return step.end?.next ?? null;
  }

  const ballTransitionResult = await awaitTweenOrDuration(
    scene,
    ballTransitionPromise,
    ballTransitionPromise?.expectedDurationMs ?? stepWaitMs,
    { tweenStarted: true, durationFallback: true },
  );
  tracePlayback(scene, "step:post-wait", {
    turnIndex: options.turnData?.index ?? null,
    stepId: step.id ?? null,
    elapsedMs: Math.round(performance.now() - stepStartedAtMs),
    ballTransitionResult,
    isPaused: scene?.isPaused ?? null,
    skipToEnd: scene?.skipToEnd ?? null,
  });

  // Ball-arrival SFX — step-end fallback. Normally fires from the ball
  // tween's onComplete in `renderBallTransition` (HCO mid-skeleton pass).
  // But when the ball doesn't move (startCoord === endCoord), the tween
  // early-returns and onComplete never fires — e.g., DREB where the ball
  // sits at bounce_coords and only the rebounder moves to it. Detect that
  // case here and fire the SFX at step end (= moment of attach via
  // snapBallToEndState below).
  const arrivalSfx = step.start?.sfx_on_ball_arrival;
  if (arrivalSfx?.file && !ballTransitionResult?.tweenStarted) {
    const startBallCoord = step.start?.ball?.owner_player_id
      ? step.start.coords?.[step.start.ball.owner_player_id]
      : step.start?.ball?.coords ?? step.start?.ball?.current_coords;
    const endBallCoord = step.start?.ball_arrival_coord
      ?? (step.end?.ball?.owner_player_id
        ? step.end.coords?.[step.end.ball.owner_player_id]
        : step.end?.ball?.coords ?? step.end?.ball?.current_coords);
    const tweenWouldEarlyReturn =
      startBallCoord && endBallCoord &&
      Math.abs(startBallCoord.x - endBallCoord.x) < 1e-6 &&
      Math.abs(startBallCoord.y - endBallCoord.y) < 1e-6;
    if (tweenWouldEarlyReturn) {
      playGameSfx(
        scene,
        arrivalSfx.file,
        typeof arrivalSfx.volume === "number" ? arrivalSfx.volume : 0.7,
        { event: arrivalSfx.event || "ball_arrival" },
      );
      const timedSfx = step.start?.timed_sfx;
      if (Array.isArray(timedSfx) && timedSfx.length > 0) {
        scheduleTimedSfxCues(scene, timedSfx);
      }
    }
  }

  // Snap sprites to exact end coords. Eliminates float-precision drift from
  // tween interpolation and guarantees the next step's start coords match
  // the rendered positions.
  for (const [playerId, endCoord] of Object.entries(step.end.coords)) {
    const sprite = sprites[playerId];
    if (!sprite) continue;
    const endPx = gridToPixels(endCoord.x, endCoord.y, width, height);
    sprite.setPosition(endPx.x, endPx.y);
    sprite.gridX = endCoord.x;
    sprite.gridY = endCoord.y;
  }

  // Snap ball to its end coord and reconcile ownership state.
  snapBallToEndState(scene, step, sprites, ballSprite, width, height);

  // step.end.announcement: play after tweens + snap, before returning next.
  if (step.end?.announcement) {
    await runStepAnnouncement(scene, step.end.announcement, sprites, step, options.turnData);
  }

  tracePlayback(scene, "step:end", {
    turnIndex: options.turnData?.index ?? null,
    stepId: step.id ?? null,
    elapsedMs: Math.round(performance.now() - stepStartedAtMs),
    advanceTrigger: step.start?.advance_trigger?.condition ?? null,
    advanceTriggerReason: step.start?.advance_trigger?.metadata?.reason ?? null,
    next: step.end?.next ?? null,
  });

  return step.end.next;
}

/**
 * Multi-step orchestrator. Walks a sequence of animation steps, following
 * `step.end.next` to determine the next step. Stops at the first `turn_stop`
 * or when `next` points past the array. The caller dispatches turn-stop
 * events (shot resolution, foul flash, etc.) — this engine just reports.
 *
 * @param {Phaser.Scene} scene
 * @param {import("./animationStepSchema.js").AnimationStep[]} steps
 * @param {Object<string, Phaser.GameObjects.Sprite>} sprites
 * @param {Phaser.GameObjects.Sprite} [ballSprite]
 * @param {Object} [options]
 * @param {number} [options.startIndex=0]
 * @param {number} [options.maxStepsGuard=200]  Cycle/loop safety bound.
 * @returns {Promise<{event: import("./animationStepSchema.js").TurnStopEvent, payload: Object} | null>}
 *   Turn-stop event when the turn ends with one; null when steps complete
 *   without one (implicit end of turn).
 */
export async function playTurn(scene, steps, sprites, ballSprite, options = {}) {
  if (!Array.isArray(steps) || steps.length === 0) return null;

  const startIndex = options.startIndex ?? 0;
  const maxStepsGuard = options.maxStepsGuard ?? 200;

  const entryStep = steps[startIndex];
  if (entryStep) {
    snapSpritesToStepStart(scene, entryStep, sprites, ballSprite);
  }

  tracePlayback(scene, "turn:start", {
    turnIndex: options.turnData?.index ?? null,
    resultType: options.turnData?.result_type ?? null,
    currentTurn: options.turnData?.current_turn ?? null,
    steps: steps.length,
    startIndex,
    spriteCount: Object.keys(sprites || {}).length,
    hasBallSprite: Boolean(ballSprite),
    ballVisible: ballSprite?.visible ?? null,
    isPaused: scene?.isPaused ?? null,
    skipToEnd: scene?.skipToEnd ?? null,
  });

  let currentIndex = startIndex;
  let stepsExecuted = 0;

  while (currentIndex >= 0 && currentIndex < steps.length) {
    if (scene?.skipToEnd) return null;
    await waitWhileUserPaused(scene);
    if (scene?.skipToEnd) return null;
    if (stepsExecuted++ >= maxStepsGuard) {
      throw new Error(
        `playTurn: exceeded ${maxStepsGuard} steps — likely a cycle in next pointers`,
      );
    }

    const step = steps[currentIndex];
    if (!step) {
      throw new Error(`playTurn: missing step at index ${currentIndex}`);
    }

    tracePlayback(scene, "turn:step-index", {
      turnIndex: options.turnData?.index ?? null,
      currentIndex,
      stepsExecuted,
      stepId: step.id ?? null,
    });

    const td = options.turnData;
    const eoqFlow = td?.flss
      ? 'FLSS'
      : (td?.final_turn || td?.final_shot_possession || td?.eoq_trace_role === 'FINAL_SHOT')
        ? 'FINAL_SHOT'
        : (td?.eoq_trace_role || (td?.eoq_trace_seq ? 'EOQ' : null));
    if (eoqFlow && isEoqTraceEnabled(scene)) {
      logEoqSchemaStep(
        scene,
        eoqFlow,
        currentIndex,
        "START",
        options.turnData,
        step,
        { playerSprites: sprites },
      );
    }

    const next = await playAnimationStep(scene, step, sprites, ballSprite, {
      ...options,
      steps,
      currentIndex,
    });

    if (eoqFlow && isEoqTraceEnabled(scene)) {
      logEoqSchemaStep(
        scene,
        eoqFlow,
        currentIndex,
        "END",
        options.turnData,
        step,
        { playerSprites: sprites },
      );
    }
    tracePlayback(scene, "turn:next", {
      turnIndex: options.turnData?.index ?? null,
      currentIndex,
      next,
    });
    if (!next) return null;

    if (next.kind === "turn_stop") {
      tracePlayback(scene, "turn:stop", {
        turnIndex: options.turnData?.index ?? null,
        event: next.event,
        payload: next.payload ?? null,
      });
      return { event: next.event, payload: next.payload };
    }
    if (next.kind === "next_step") {
      currentIndex = next.index;
      continue;
    }
    if (next.kind === "branch") {
      currentIndex = next.next_step_index;
      continue;
    }
    throw new Error(`playTurn: unknown next.kind: ${next.kind}`);
  }

  // Index ran past the array — implicit end of turn.
  tracePlayback(scene, "turn:end-implicit", {
    turnIndex: options.turnData?.index ?? null,
    currentIndex,
    stepsExecuted,
  });
  return null;
}

// --- Turn-stop dispatcher --------------------------------------------------

/**
 * Route a turn-stop event (returned from playTurn) to the appropriate side
 * animation. Caller passes the non-null result of playTurn through here.
 *
 * SCOPE NOTE: handler bodies are stubbed. Each turn-type migration fills in
 * the handlers it needs, until every event is implemented. Stubs `console.warn`
 * and resolve with `null` rather than throwing — keeps partial integrations
 * runnable while making missing implementations visible.
 *
 * @param {Phaser.Scene} scene
 * @param {{event: import("./animationStepSchema.js").TurnStopEvent, payload: Object}} turnStop
 * @param {Object} [context]  Passes through anything handlers need (sprites,
 *                            ballSprite, turnData, callbacks). Each handler
 *                            documents the keys it consumes.
 * @returns {Promise<void>}
 */
export async function dispatchTurnStop(scene, turnStop, context = {}) {
  if (!turnStop) return;
  const { event, payload } = turnStop;
  switch (event) {
    case "SHOT_ATTEMPT":         return runShotAttempt(scene, payload, context);
    case "FOUL":                 return runFoul(scene, payload, context);
    case "STEAL":                return runSteal(scene, payload, context);
    case "DEAD_BALL_TURNOVER":   return runDeadBallTurnover(scene, payload, context);
    case "SHOT_CLOCK_EXPIRED":   return runShotClockExpired(scene, payload, context);
    case "GAME_CLOCK_EXPIRED":   return runGameClockExpired(scene, payload, context);
    case "TIMEOUT":              return runTimeout(scene, payload, context);
    case "JUMP_BALL":            return runJumpBall(scene, payload, context);
    default:
      console.warn(`dispatchTurnStop: unknown event "${event}"`, payload);
      return;
  }
}

// Each handler stub takes (scene, payload, context). Migrations replace these
// with real implementations that integrate with the existing helpers
// (ShotAnimationSystem, FreeThrowAnimationSystem, ReboundAnimationSystem,
// announcement utils, etc.). For now they log and no-op.

async function runShotAttempt(scene, payload, context) {
  // Render ball arc to rim, then ball-on-rim bounce for misses. Rebound is
  // a separate turn (DREB or OREB) — this handler does NOT animate the
  // rebound capture itself. See Animation_System_Updated.md.
  const { result, ball_bounce_coords, shooter_id, schema_rendered_arc } = payload || {};

  await waitWhileUserPaused(scene);
  if (shouldFastForwardPlayback(scene)) return;

  // Schema-rendered-arc path (HCO sub-step migration): the [ball_flight]
  // + [bounce] schema steps already rendered the ball motion AND fired
  // both shot-release and shot-result SFX from animationPlayback's
  // step-level cues. Nothing to do here.
  if (schema_rendered_arc) return;

  const { ballSprite, sprites } = context || {};
  if (!scene || !ballSprite) return;

  const width = scene.game?.config?.width;
  const height = scene.game?.config?.height;

  // Determine the basket the shooter was attacking.
  const { HOME_RIM_COORDS, AWAY_RIM_COORDS, getMadeShotSweetSpotGrid } =
    await import("./courtConstants.js");
  const shooterSprite = (sprites || {})[shooter_id] || null;
  const isHomeOffense = shooterSprite?.team === "home";
  const { gridToPixels } = await import("../utils/gridToPixels.js");

  // MAKE: ball settles at the "sweet spot" (slightly in front of the rim
  // center, on the offense's side). MISS / BLOCK: ball hits the rim center
  // first, then bounces to `ball_bounce_coords` in phase 2 below.
  // Matches legacy `shootBall` / `getMadeShotSweetSpotGrid` behavior so the
  // schema engine and legacy renderer terminate makes at the same coord.
  const shotEndGrid = result === "MAKE"
    ? getMadeShotSweetSpotGrid(isHomeOffense)
    : (isHomeOffense ? HOME_RIM_COORDS : AWAY_RIM_COORDS);
  const shotEndPx = gridToPixels(shotEndGrid.x, shotEndGrid.y, width, height);

  const shooterGridX = shooterSprite?.gridX ?? shotEndGrid.x;
  const shooterGridY = shooterSprite?.gridY ?? shotEndGrid.y;
  const gridDist = Math.hypot(
    shotEndGrid.x - shooterGridX,
    shotEndGrid.y - shooterGridY,
  );
  const tickMs = scene?.gameClock?.getState?.().tickMs || 350;
  const legacyShotDurationMs = Math.max(
    SHOT_BALL_MIN_WALL_CLOCK_MS,
    shotBallTweenDurationMs(
      gridDist,
      tickMs,
      { start: { ball_motion_style: "shot" } },
    ),
  );

  // Phase 1: ball arcs to its end position (rim for miss, sweet spot for make).
  const { playShotLaunchSfx, playShotResultSfx } = await import("../utils/gameSfx.js?v=announcement-meta-sfx-1");
  const ballAnim = await import("./ballAnimationSimple.js");
  if (typeof ballAnim.animateShotToRim === "function") {
    await ballAnim.animateShotToRim(scene, shotEndPx, {
      duration: legacyShotDurationMs,
      easing: "Sine.easeInOut",
      arc: { height: 50 },
      onShotRelease: () => playShotLaunchSfx(scene, context?.turnData),
      onShotArrive: () => playShotResultSfx(scene, context?.turnData, result),
    });
  }

  // Phase 2: for MISS / BLOCK, bounce to backend-provided bounce coords.
  // Rebounder pickup happens in the next DREB / OREB turn.
  if (result !== "MAKE" && ball_bounce_coords) {
    const bouncePx = gridToPixels(
      ball_bounce_coords.x,
      ball_bounce_coords.y,
      width,
      height,
    );
    await new Promise((resolve) => {
      scene.tweens.add({
        targets: ballSprite,
        x: bouncePx.x,
        y: bouncePx.y,
        duration: 300,
        ease: "Quad.easeOut",
        onComplete: resolve,
      });
    });
  }

  // Announcement is intentionally skipped for the first HCT cutover — the
  // existing announcement system fires from the legacy turn-completion
  // pipeline, and we want to validate the core animation flow first
  // before wiring announcements through here. Followup task.
}

async function runFoul(_scene, payload, _context) {
  // Wire to: foul flash effect + announcement + (if shooting foul) FT setup.
  console.warn("dispatchTurnStop: FOUL handler not yet implemented", payload);
}

async function runSteal(_scene, payload, _context) {
  // Wire to: steal visual + possession flip (or transition to FAST_BREAK).
  console.warn("dispatchTurnStop: STEAL handler not yet implemented", payload);
}

async function runDeadBallTurnover(_scene, payload, _context) {
  // Wire to: dead-ball animation + SIDE_INBOUND setup.
  console.warn("dispatchTurnStop: DEAD_BALL_TURNOVER handler not yet implemented", payload);
}

async function runShotClockExpired(_scene, payload, _context) {
  // Wire to: buzzer + possession flip + SIDE_INBOUND setup.
  console.warn("dispatchTurnStop: SHOT_CLOCK_EXPIRED handler not yet implemented", payload);
}

async function runGameClockExpired(_scene, payload, _context) {
  // Wire to: end-of-quarter banner + transition to next quarter / end of game.
  console.warn("dispatchTurnStop: GAME_CLOCK_EXPIRED handler not yet implemented", payload);
}

async function runTimeout(_scene, payload, _context) {
  // Wire to: timeout overlay + game-state pause.
  console.warn("dispatchTurnStop: TIMEOUT handler not yet implemented", payload);
}

async function runJumpBall(_scene, payload, _context) {
  // Wire to: jump-ball animation + possession assignment (Opening Tip path).
  console.warn("dispatchTurnStop: JUMP_BALL handler not yet implemented", payload);
}
