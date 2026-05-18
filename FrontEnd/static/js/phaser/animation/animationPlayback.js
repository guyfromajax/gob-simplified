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
import { playGameSfx, playFBDefensiveStopCourtSfx } from "../utils/gameSfx.js";

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
function renderBallTransition(scene, step, sprites, ballSprite, durationMs, width, height) {
  if (!ballSprite) return;
  const startCoord = ballCoordFromState(step.start.ball, step.start.coords);
  const endCoord = ballCoordFromState(step.end.ball, step.end.coords);
  if (!startCoord || !endCoord) return;

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
    return;
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
  if (startOwner && startOwner !== endOwner) {
    console.log(
      "🐛 [BALL DETACH] firing detach: startOwner=%s endOwner=%s startCoord=%o endCoord=%o duration=%dms",
      startOwner, endOwner, startCoord, endCoord, durationMs,
    );
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
  } else {
    console.log(
      "🐛 [BALL DETACH] skipping detach: startOwner=%s endOwner=%s (same or unattached)",
      startOwner, endOwner,
    );
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

  scene.tweens.add({
    targets: ballSprite,
    x: endPx.x,
    y: endPx.y,
    duration: durationMs,
    ease: "Linear",
  });
}

/**
 * At step end: snap ball to exact end coord and reconcile ownership state
 * with `step.end.ball`. Called after the wall-clock wait, alongside the
 * player snap.
 */
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
  if (directPlayerData?.playerId) return directPlayerData;
  const text = String(announcement?.text || "").trim().toLowerCase();
  if (text !== "nice stop!") return directPlayerData || null;
  const stopperId =
    turnData?.stopper_id
    ?? turnData?.roles?.stopper_id
    ?? turnData?.roles?.stopper?.player_id
    ?? turnData?.roles?.stopper;
  if (stopperId) {
    return { ...(directPlayerData || {}), playerId: String(stopperId) };
  }
  const actions = step?.start?.action || {};
  const guardStopperId = Object.entries(actions).find(([, action]) => action === "guard_ball")?.[0];
  return guardStopperId ? { ...(directPlayerData || {}), playerId: guardStopperId } : (directPlayerData || null);
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

function isCovertReleaseDefensiveStopAnnouncement(announcement, turnData = null) {
  if (turnData?.fast_break_play !== "covert_release") return false;
  return String(announcement?.text || "").trim().toLowerCase() === "nice stop!";
}

function isNoFastBreakAnnouncement(announcement) {
  return String(announcement?.text || "").trim().toLowerCase() === "no fast break";
}

/**
 * Play `duke-hold-up.wav` when the "No Fast Break" announcement fires
 * (RR FB hold-up branch, step 2 start). Stashes the Audio instance on
 * `scene._activeSfx` so the browser doesn't GC the anonymous Audio object
 * mid-clip — same pattern as the outlet-pass SFX in `renderBallTransition`.
 * Fail-silent.
 */
function playNoFastBreakSfx(scene) {
  try {
    const sfx = new Audio(`/sounds/duke-hold-up.wav`);
    if (!scene._activeSfx) scene._activeSfx = new Set();
    scene._activeSfx.add(sfx);
    const release = () => {
      if (scene._activeSfx) scene._activeSfx.delete(sfx);
    };
    sfx.addEventListener("ended", release, { once: true });
    sfx.addEventListener("error", release, { once: true });
    sfx.play().catch(release);
  } catch (_e) {
    // Audio is non-critical.
  }
}

function resolveDefenseTeamSideForTurn(scene, turnData, sprites = null) {
  const playerSprites = sprites || scene?.playerSprites || {};
  const ballHandlerData = turnData?.roles?.ball_handler;
  const ballHandlerId = ballHandlerData?.player_id || ballHandlerData;
  const ballHandlerSprite = ballHandlerId ? playerSprites[ballHandlerId] : null;
  if (ballHandlerSprite?.team === "home") return "away";
  if (ballHandlerSprite?.team === "away") return "home";
  return "away";
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

  // Announcement-tied SFX. Fire alongside the announcement so audio + visual
  // are synced. Once per announcement display (this function runs once per
  // step.start.announcement / step.end.announcement). Add new cases here as
  // additional announcements need accompanying SFX.
  if (isNoFastBreakAnnouncement(announcement)) {
    playNoFastBreakSfx(scene);
  }

  try {
    const { showAnnouncement, showSecondaryAnnouncement, buildSecondaryStopperPlayerData } = await import("../utils/announcements.js");
    const inferredPlayerData = inferStepAnnouncementPlayerData(announcement, step, turnData);
    const playerData = enrichStepAnnouncementPlayerData(scene, inferredPlayerData, sprites);
    if (isCovertReleaseDefensiveStopAnnouncement(announcement, turnData)) {
      // Legacy CR override: rewrite "Nice Stop!" → "Great Stop!", play court SFX,
      // resolve stopper via dedicated builder. Pre-dates the explicit `style`
      // field; kept for backwards compat with CR emitter output.
      const stopperId =
        playerData?.playerId
        ?? turnData?.stopper_id
        ?? turnData?.roles?.stopper_id
        ?? turnData?.roles?.stopper?.player_id
        ?? turnData?.roles?.stopper;
      const stopperRef = stopperId
        ? resolveScenePlayerRef(scene, stopperId, sprites)
        : { id: null, sprite: null, info: null };
      const defenseTeam = stopperRef.sprite?.team === "home"
        ? "home"
        : stopperRef.sprite?.team === "away"
          ? "away"
          : resolveDefenseTeamSideForTurn(scene, turnData, sprites);
      playFBDefensiveStopCourtSfx(scene);
      showSecondaryAnnouncement(
        "Great Stop!",
        defenseTeam,
        buildSecondaryStopperPlayerData(scene, stopperId, sprites),
        { scene },
      );
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
        announcement.meta || null,
      );
    }
  } catch (err) {
    console.warn("runStepAnnouncement: showAnnouncement failed", err);
  }
  const holdMs = Number.isFinite(announcement.hold_ms) && announcement.hold_ms > 0
    ? announcement.hold_ms
    : 1000;
  await new Promise((resolve) => {
    if (scene.time?.delayedCall) {
      scene.time.delayedCall(holdMs, resolve);
    } else {
      setTimeout(resolve, holdMs);
    }
  });
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

  const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 350;
  const durationMs = Math.max(
    50,
    Math.round(step.end.time_elapsed * clockSecondMs),
  );

  const width = scene.game?.config?.width;
  const height = scene.game?.config?.height;

  // step.start.announcement: play before tweens fire.
  if (step.start?.announcement) {
    await runStepAnnouncement(scene, step.start.announcement, sprites, step, options.turnData);
  }

  // Spawn one linear tween per player whose start coord differs from end coord.
  // Backend stamps per-player tween durations on step.start.tween_durations
  // (in game-seconds); convert to ms via clockSecondMs. Players who finish
  // before step T sit idle at their end coord until the wall-clock timer
  // below fires — produces the natural "settle and wait" feel rather than
  // stretching every player's tween across the gating player's duration.
  // When tween_durations is absent (legacy emitters), fall back to step T.
  const perPlayerDurations = step.start.tween_durations || {};
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

    const endPx = gridToPixels(endCoord.x, endCoord.y, width, height);
    scene.tweens.add({
      targets: sprite,
      x: endPx.x,
      y: endPx.y,
      duration: playerDurationMs,
      ease: "Linear",
    });
  }

  // Spawn the ball tween in parallel with player tweens.
  renderBallTransition(scene, step, sprites, ballSprite, durationMs, width, height);

  // Wait the prescribed wall-clock duration. We don't await each tween's
  // completion individually — Phaser drives them in parallel and we trust the
  // wall-clock timer. Avoids the hang patterns we hit when chaining promises
  // through tweenPlayerTo's reject-on-stop wrapper.
  await new Promise((resolve) => {
    if (scene.time?.delayedCall) {
      scene.time.delayedCall(durationMs, resolve);
    } else {
      setTimeout(resolve, durationMs);
    }
  });

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

  let currentIndex = startIndex;
  let stepsExecuted = 0;

  while (currentIndex >= 0 && currentIndex < steps.length) {
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

    const next = await playAnimationStep(scene, step, sprites, ballSprite, options);
    if (!next) return null;

    if (next.kind === "turn_stop") {
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
  const { result, ball_bounce_coords, shooter_id } = payload || {};
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

  // Phase 1: ball arcs to its end position (rim for miss, sweet spot for make).
  const { playShotLaunchSfx, playShotResultSfx } = await import("../utils/gameSfx.js");
  const ballAnim = await import("./ballAnimationSimple.js");
  if (typeof ballAnim.animateShotToRim === "function") {
    await ballAnim.animateShotToRim(scene, shotEndPx, {
      duration: 350,
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
