import * as Phaser from "https://cdn.jsdelivr.net/npm/phaser@3.70.0/dist/phaser.esm.js";
import { animateStep } from "./animateStep.js";
import { gridToPixels } from "../utils/gridToPixels.js";
import {
  STEAL_HCO_SETUP_MOVE_X_MIN,
  STEAL_HCO_SETUP_MOVE_X_MAX,
  STEAL_HCO_SETUP_MOVE_Y_RANGE,
  STEAL_HCO_SETUP_Y_MIN,
  STEAL_HCO_SETUP_Y_MAX,
} from "../constants/fastBreakConstants.js";
import {
  shootBall,
  SHOT_DEBUG,
  animateRebound,
  animateKickoutReset
} from "./ballManager.js";
import { attachBallToPlayer } from "./BallControllerAdapter.js";
import { runPass, PASS_DEBUG, tweenPlayerTo } from "./ballTween.js";
import animationConfig from "./animation_config.js";
import { HOME_RIM_COORDS, AWAY_RIM_COORDS } from "./courtConstants.js";
import { deriveOffenseContext, computeFastBreakOutletTarget } from "./outletUtils.js";
import { clampGridCoords } from "./courtClamp.js";
import { getAnimationEndGridForPlayer } from "../utils/animationEndFromTurn.js";
import * as unitCompletionContract from "./unitCompletionContract.js";
import { resolveDrebOutletReceiverTarget } from "./drebOutletTargetResolver.js";
import { DEBUG } from "../utils/debug.js";
import {
  DebugFlags,
  animationDebugLog,
  animationDebugWarn,
  isAnimationDebugEnabled,
} from "../utils/debugFlags.js";
import {
  States,
  getDebugTransitions,
  safeTransition,
  createTransitionGuard,
  transitionWithDebug,
} from "../state/gameStateMachine.js";
import {
  ENABLE_TIMEOUT_BUTTON,
  initTimeoutButton,
  resetTimeoutQueue,
  checkTimeoutEligibility,
} from "../utils/timeoutButtonManager.js";
import {
  getPendingOwner,
  clearPendingOwner,
  setPendingOwner,
  setCurrentOwner,
  getCurrentOwner
} from "./BallControllerAdapter.js";
// ✅ NEW (Step 1): Import simple ball holder state functions
// ✅ STEP 3 MIGRATION: Import new ball animation function
import {
  initializeBallHolderState,
  setBallHolderId,
  clearBallHolder,
  animateBallToPosition,
} from "./ballAnimationSimple.js";
import {
  resolveMovementSpeedPxPerSec,
  getPlayerMovementDurationMs,
} from "../utils/playerMovementDuration.js";

const { enforceUnitCompletionContract } = unitCompletionContract;
const advanceDynamicEventBoundary =
  unitCompletionContract.advanceDynamicEventBoundary ??
  (async function fallbackAdvanceDynamicEventBoundary({
    requiredPromises = [],
    scene,
    nonRequiredSprites = [],
    onAdvance,
    onStopSprite,
  }) {
    await Promise.all(requiredPromises);
    if (typeof onAdvance === "function") {
      await onAdvance();
    }
    const seen = new Set();
    for (const sprite of nonRequiredSprites) {
      if (!sprite || seen.has(sprite)) continue;
      seen.add(sprite);
      if (typeof onStopSprite === "function") {
        onStopSprite(sprite);
      }
      scene?.tweens?.killTweensOf?.(sprite);
    }
  });

const DEFAULT_BALL_SPEED = 450; // Default speed (Normal preset) — ball uses same preset as players

/**
 * Get current ball speed (can be changed dynamically)
 * @returns {number} Speed in pixels per second
 */
function getBallSpeed() {
  if (typeof window !== "undefined" && window.__GAME_SPEED) {
    return window.__GAME_SPEED;
  }
  return DEFAULT_BALL_SPEED;
}

function resolveSpriteById(playerSprites, rawId) {
  if (!playerSprites || rawId == null) return { id: null, sprite: null };
  const sid = String(rawId);
  if (playerSprites[sid]) return { id: sid, sprite: playerSprites[sid] };
  if (playerSprites[rawId]) return { id: rawId, sprite: playerSprites[rawId] };
  const n = Number(rawId);
  if (Number.isFinite(n) && playerSprites[n]) return { id: n, sprite: playerSprites[n] };
  return { id: sid, sprite: null };
}

function getDrebTelemetryScope() {
  return (
    (typeof window !== "undefined" && window) ||
    (typeof globalThis !== "undefined" && globalThis) ||
    null
  );
}

function resolveDrebStrictMode() {
  const scope = getDrebTelemetryScope();
  const raw = scope?.DREB_STRICT_CONTRACT;
  if (raw === "throw") return "throw";
  if (raw === "warn" || raw === true) return "warn";
  if (raw === "off" || raw === false) return "off";
  return "throw";
}

function resolveInboundContractMode() {
  const scope = getDrebTelemetryScope();
  const raw = String(scope?.UESS_INBOUND_CONTRACT_MODE ?? "warn")
    .trim()
    .toLowerCase();
  if (raw === "off" || raw === "observe" || raw === "warn" || raw === "throw") {
    return raw;
  }
  return "warn";
}

function getInboundBudgetGameSeconds(kind = "pass", resultType = "SIDE_INBOUND") {
  const scope = getDrebTelemetryScope();
  const normalizedKind = kind === "setup" ? "setup" : "pass";
  const normalizedResultType = String(resultType || "SIDE_INBOUND").toUpperCase();
  const isBaseline = normalizedResultType === "BASELINE_INBOUND";
  const specificKey =
    normalizedKind === "setup"
      ? isBaseline
        ? "UESS_BASELINE_INBOUND_SETUP_MAX_GAME_SECONDS"
        : "UESS_SIDE_INBOUND_SETUP_MAX_GAME_SECONDS"
      : isBaseline
      ? "UESS_BASELINE_INBOUND_PASS_MAX_GAME_SECONDS"
      : "UESS_SIDE_INBOUND_PASS_MAX_GAME_SECONDS";
  const genericKey =
    normalizedKind === "setup"
      ? "UESS_INBOUND_SETUP_MAX_GAME_SECONDS"
      : "UESS_INBOUND_PASS_MAX_GAME_SECONDS";
  const defaultValue = normalizedKind === "setup" ? 4 : 2;
  const specific = Number(scope?.[specificKey]);
  if (Number.isFinite(specific) && specific >= 0) return specific;
  const generic = Number(scope?.[genericKey]);
  if (Number.isFinite(generic) && generic >= 0) return generic;
  return defaultValue;
}

function hasPlayerSpriteForId(playerSprites, rawId) {
  if (rawId == null || !playerSprites) return false;
  if (playerSprites?.[rawId]) return true;
  const want = String(rawId);
  for (const [id, sprite] of Object.entries(playerSprites || {})) {
    if (String(id) === want) return true;
    if (String(sprite?.playerId ?? "") === want) return true;
  }
  return false;
}

function emitInboundContractTelemetry(scene, turnData, event, payload = {}) {
  scene?.events?.emit?.("animTelemetry", {
    event,
    branchKind: "inbound_unit_contract",
    turnId: turnData?.turn_count ?? turnData?.id ?? null,
    turnIndex: scene?.currentTurn ?? null,
    resultType: turnData?.result_type ?? null,
    gameClock: scene?.simData?.clock ?? null,
    quarter: turnData?.quarter ?? scene?.quarter ?? null,
    timestampMs: Date.now(),
    ...payload,
  });
}

function validateInboundUnitCompletionContract({
  scene,
  turnData,
  playerSprites,
  unitId,
  advanceTrigger,
  visualSettleTrigger,
  unitStartMs,
  maxWaitGameSeconds,
  authorizingEventReceived,
  requireOwner = false,
  requirePassNotInFlight = false,
  context = {},
}) {
  const mode = resolveInboundContractMode();
  if (mode === "off") {
    return { ok: true, mode, skipped: true };
  }

  const emitTelemetry = (event, payload = {}) =>
    emitInboundContractTelemetry(scene, turnData, event, payload);

  const currentOwnerId = getCurrentOwner(scene);
  const pendingOwnerId = getPendingOwner(scene);
  const hasCurrentOwner = currentOwnerId != null && String(currentOwnerId).length > 0;
  const hasPendingOwner = pendingOwnerId != null && String(pendingOwnerId).length > 0;
  const ownerMissing = requireOwner && !hasCurrentOwner && !hasPendingOwner;
  const ownerInvalid =
    requireOwner &&
    ((hasCurrentOwner && !hasPlayerSpriteForId(playerSprites, currentOwnerId)) ||
      (hasPendingOwner && !hasPlayerSpriteForId(playerSprites, pendingOwnerId)));
  const passInFlightAtBoundary = requirePassNotInFlight && scene?.passInFlight === true;
  const elapsedMs = Math.max(0, Date.now() - Number(unitStartMs || Date.now()));
  const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 350;
  const elapsedGameSeconds = elapsedMs / clockSecondMs;
  const overrun =
    Number.isFinite(maxWaitGameSeconds) &&
    maxWaitGameSeconds >= 0 &&
    elapsedGameSeconds > maxWaitGameSeconds;
  const visualSettled =
    !ownerMissing && !ownerInvalid && !passInFlightAtBoundary && !overrun;

  const summaryContext = {
    unitId,
    currentOwnerId: currentOwnerId ?? null,
    pendingOwnerId: pendingOwnerId ?? null,
    ownerMissing,
    ownerInvalid,
    passInFlightAtBoundary,
    elapsedMs,
    elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
    maxWaitGameSeconds,
    ...context,
  };

  if (ownerMissing) emitTelemetry("inbound_contract_owner_missing", summaryContext);
  if (ownerInvalid) emitTelemetry("inbound_contract_owner_invalid", summaryContext);
  if (passInFlightAtBoundary) emitTelemetry("inbound_contract_pass_in_flight", summaryContext);
  if (overrun) emitTelemetry("inbound_contract_clock_overrun", summaryContext);

  const logger =
    mode === "observe"
      ? {
          warn: () => {},
        }
      : console;
  enforceUnitCompletionContract({
    contract: {
      unit_id: unitId,
      execution_mode: "dynamic_event",
      advance_trigger: advanceTrigger,
      visual_settle_trigger: visualSettleTrigger,
      failure_policy: mode === "throw" ? "throw" : "warn",
    },
    observed: {
      authorizingEventReceived: authorizingEventReceived === true,
      visualSettled,
    },
    context: summaryContext,
    emitTelemetry,
    logger,
  });

  if (mode === "throw") {
    if (ownerMissing) {
      throw new Error(
        `[inbound contract] missing owner at unit boundary (unit=${unitId}, result=${turnData?.result_type ?? "?"})`
      );
    }
    if (ownerInvalid) {
      throw new Error(
        `[inbound contract] invalid owner at unit boundary (unit=${unitId}, result=${turnData?.result_type ?? "?"})`
      );
    }
    if (passInFlightAtBoundary) {
      throw new Error(
        `[inbound contract] pass still in flight at unit boundary (unit=${unitId}, result=${turnData?.result_type ?? "?"})`
      );
    }
    if (overrun) {
      throw new Error(
        `[inbound contract] clock overrun (unit=${unitId}, result=${turnData?.result_type ?? "?"}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${Number(maxWaitGameSeconds)})`
      );
    }
  }

  return { ok: visualSettled, mode, visualSettled };
}

/**
 * Grid X distance (0–100 court scale) covered in durationMs at AG-based px/s when
 * 100 grid units span `width` pixels (matches gridToPixels).
 */
export function horizontalGridUnitsForDurationMs(sprite, durationMs, width, opts = {}) {
  if (!sprite || !Number.isFinite(width) || width <= 0 || !Number.isFinite(durationMs) || durationMs <= 0) {
    return 0;
  }
  const scene = opts.scene ?? sprite?.scene;
  const speed = resolveMovementSpeedPxPerSec(sprite, { ...opts, scene });
  const distPx = speed * (durationMs / 1000);
  return (distPx * 100) / width;
}

/** Ball-only: distance / speed (game speed preset). Player moves use playerMovementDuration.js */
function getDurationFromDistance(currentX, currentY, targetX, targetY, speed) {
  const distance = Phaser.Math.Distance.Between(currentX, currentY, targetX, targetY);
  const duration = (distance / speed) * 1000;
  return Math.max(50, duration);
}

function pixelsToGrid(pixelX, pixelY, width, height) {
  return {
    x: (pixelX / width) * 100,
    y: 50 - (pixelY / height) * 50,
  };
}

function captureLiveSpriteGrid(sprite, width, height) {
  if (!sprite || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return;
  }
  const liveGrid = pixelsToGrid(sprite.x, sprite.y, width, height);
  sprite.gridX = liveGrid.x;
  sprite.gridY = liveGrid.y;
}

/**
 * Calculate player movement duration based on distance from current sprite position to target
 * Uses the sprite's actual current position (sprite.x, sprite.y) as the starting point,
 * which ensures smooth transitions between turns without requiring setup tweens.
 * 
 * @param {Phaser.GameObjects.Sprite} sprite - The player sprite
 * @param {number} targetX - Target X position in pixels
 * @param {number} targetY - Target Y position in pixels
 * @param {boolean} isTransition - If true, use MAX_TRANSITION_DURATION instead of MAX_STEP_DURATION
 * @returns {number} Duration in milliseconds
 */
/**
 * Steal HCO Setup Animation
 * Moves the stealer (ball handler) back away from basket before HCO skeleton starts
 */
async function animateStealHCOSetup(scene, turnData, playerSprites, ballSprite) {
  const ballHandlerId = turnData.roles?.ball_handler_id;
  const ballHandlerSprite = ballHandlerId ? playerSprites[ballHandlerId] : null;
  
  if (!ballHandlerSprite) {
    console.warn("Steal HCO Setup: Ball handler sprite not found", { 
      ballHandlerId,
      roles: turnData.roles
    });
    return;
  }
  
  // Ball should already be attached to stealer from the steal turn
  // Verify attachment
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  
  if (!ballController?.isAttached || ballController.currentOwner !== ballHandlerSprite) {
    // Attach ball to stealer if not already attached
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite, {
      reason: 'steal_hco_setup_verify'
    });
  }
  
  // Get stealer's current position
  const currentGrid = {
    x: ballHandlerSprite.gridX || 50,
    y: ballHandlerSprite.gridY || 25
  };
  
  // ✅ DETAILED LOGGING: Track frontend HCO Setup calculation
  console.warn("🏀 [FRONTEND STEAL HCO SETUP] Entry:", {
    ballHandlerId,
    currentSpritePosition: { x: ballHandlerSprite.gridX, y: ballHandlerSprite.gridY },
    roles: turnData.roles,
    backendFinalX: turnData.roles?.ball_handler_hco_setup_x,
    backendFinalY: turnData.roles?.ball_handler_hco_setup_y,
    backendMoveX: turnData.roles?.ball_handler_hco_setup_move_x,
    backendMoveY: turnData.roles?.ball_handler_hco_setup_move_y
  });
  
  // Determine offense team and direction (away from basket)
  const isHomeOffense = ballHandlerSprite.team === "home";
  const direction = isHomeOffense ? -1 : 1; // -1 for home (away from x=90), +1 for away (away from x=10)
  
  // Calculate steal HCO setup movement (matches backend calculation)
  const moveX = turnData.roles?.ball_handler_hco_setup_move_x || 
                Phaser.Math.Between(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX);
  const moveY = turnData.roles?.ball_handler_hco_setup_move_y || 
                Phaser.Math.Between(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE);
  
  // ✅ FIX: Use backend-provided final coordinates if available (more accurate)
  // Otherwise, calculate from current position
  let targetGrid;
  if (turnData.roles?.ball_handler_hco_setup_x !== undefined && turnData.roles?.ball_handler_hco_setup_y !== undefined) {
    // Use backend-calculated final position
    targetGrid = {
      x: turnData.roles.ball_handler_hco_setup_x,
      y: turnData.roles.ball_handler_hco_setup_y
    };
    console.warn("🏀 [FRONTEND STEAL HCO SETUP] Using backend final coordinates:", targetGrid);
  } else {
    // Fallback: Calculate from current position (shouldn't happen if backend is correct)
    targetGrid = {
      x: currentGrid.x + (direction * moveX),
      y: Phaser.Math.Clamp(
        currentGrid.y + moveY,
        STEAL_HCO_SETUP_Y_MIN,
        STEAL_HCO_SETUP_Y_MAX
      )
    };
    console.warn("⚠️ [FRONTEND STEAL HCO SETUP] Calculated target (backend coords missing):", targetGrid);
  }
  
  console.warn("🏀 [FRONTEND STEAL HCO SETUP] Movement Details:", {
    startingPosition: currentGrid,
    direction,
    moveX,
    moveY,
    targetPosition: targetGrid,
    calculation: `${currentGrid.x} + (${direction} * ${moveX}) = ${targetGrid.x}`
  });
  
  // Convert to pixel coordinates
  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
  
  // Get animation duration
  const playerDuration = getPlayerDuration(ballHandlerSprite, targetPx.x, targetPx.y, true);
  
  // Animate stealer movement
  await tweenPlayerTo(scene, ballHandlerSprite, targetPx, {
    duration: playerDuration,
    easing: "Linear"
  });
  
  // Update sprite grid coordinates
  ballHandlerSprite.gridX = targetGrid.x;
  ballHandlerSprite.gridY = targetGrid.y;
  
  // Verify ball remains attached after movement
  if (ballController && (!ballController.isAttached || ballController.currentOwner !== ballHandlerSprite)) {
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite, {
      reason: 'steal_hco_setup_post_movement'
    });
  }
  
  // Animate all 9 other players (toward the new offense basket)
  const otherPlayersMovements = turnData.roles?.other_players_hco_setup_movements || [];
  if (otherPlayersMovements.length > 0) {
    console.warn(`🏀 [FRONTEND STEAL HCO SETUP] Animating ${otherPlayersMovements.length} other players toward new offense basket`);
    
    const promises = [];
    for (const movement of otherPlayersMovements) {
      const playerSprite = playerSprites[movement.player_id];
      if (!playerSprite) {
        console.warn(`⚠️ [FRONTEND STEAL HCO SETUP] Player sprite not found: ${movement.player_id}`);
        continue;
      }
      
      // Get current position
      const currentGrid = {
        x: playerSprite.gridX || movement.start_x,
        y: playerSprite.gridY || movement.start_y
      };
      
      // Use backend-calculated final position
      const targetGrid = {
        x: movement.final_x,
        y: movement.final_y
      };
      
      // Convert to pixel coordinates
      const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
      
      // Get animation duration
      const duration = getPlayerDuration(playerSprite, targetPx.x, targetPx.y, true);
      
      // Animate player movement
      promises.push(
        tweenPlayerTo(scene, playerSprite, targetPx, {
          duration: duration,
          easing: "Linear"
        }).then(() => {
          // Update sprite grid coordinates
          playerSprite.gridX = targetGrid.x;
          playerSprite.gridY = targetGrid.y;
        })
      );
    }
    
    // Wait for all other players to finish animating
    await Promise.all(promises);
    console.warn(`🏀 [FRONTEND STEAL HCO SETUP] All ${otherPlayersMovements.length} other players finished animating`);
  }
}

function getPlayerDuration(sprite, targetX, targetY, _isTransition = false, opts = {}) {
  return getPlayerMovementDurationMs(sprite, targetX, targetY, {
    ...opts,
    scene: opts.scene ?? sprite?.scene,
  });
}

/**
 * Calculate ball movement duration based on distance from current sprite position to target
 * 
 * @param {Phaser.GameObjects.Sprite} ballSprite - The ball sprite
 * @param {number} targetX - Target X position in pixels
 * @param {number} targetY - Target Y position in pixels
 * @returns {number} Duration in milliseconds
 */
function getBallDuration(ballSprite, targetX, targetY) {
  if (!ballSprite) return 300; // Default fallback if ball sprite doesn't exist
  const currentX = ballSprite.x;
  const currentY = ballSprite.y;
  const speed = getBallSpeed();
  return getDurationFromDistance(currentX, currentY, targetX, targetY, speed);
}

function delayMs(scene, ms) {
  const safe = Math.max(0, Math.floor(Number(ms) || 0));
  if (!safe) return Promise.resolve();
  if (scene?.time?.delayedCall) {
    return new Promise((resolve) => scene.time.delayedCall(safe, resolve));
  }
  return new Promise((resolve) => setTimeout(resolve, safe));
}

function getStepBallHandlerId(animations, stepIndex) {
  if (!Array.isArray(animations)) return null;
  for (const anim of animations) {
    if (anim?.hasBallAtStep?.[stepIndex]) return anim.playerId;
  }
  for (const anim of animations) {
    const step = anim?.movement?.[stepIndex];
    const action = step?.action;
    if (action === "handle_ball" || action === "receive" || action === "pass" || action === "shoot" || action === "drive") {
      return anim.playerId;
    }
  }
  return null;
}


/**
 * Centralized ball ownership logic
 * Assigns the ball to the correct player for the current stepIndex
 */
/**
 * Update ball ownership (step-index based)
 * Delegates to unified updateBallOwnership function
 * @param {Object} options
 * @param {Phaser.Scene} options.scene
 * @param {Phaser.GameObjects.Sprite} options.ballSprite
 * @param {Array} options.animations
 * @param {Object} options.playerSprites
 * @param {number} options.stepIndex
 * @param {string} [options.offenseTeamId]
 * @param {Object} [options.currentBallOwnerRef]
 */
async function updateBallOwnership({ scene, ballSprite, animations, playerSprites, stepIndex, offenseTeamId, currentBallOwnerRef }) {
  const { updateBallOwnership: unifiedUpdate } = await import('./BallControllerAdapter.js');
  return unifiedUpdate({
    scene,
    ballSprite,
    animations,
    playerSprites,
    stepIndex,
    offenseTeamId,
    currentBallOwnerRef
  });
}

/**
 * Smoothly move all players to their step 0 positions before possession begins.
 * Locks the ball to the player with hasBallAtStep[0] during this setup tween.
 */

async function runSetupTween({ scene, ballSprite, animations, playerSprites, currentBallOwnerRef, turnData = null, stepDurationMs = null }) {
  if (scene.skipToEnd) return;
  const stepIndex = 0;
  const promises = [];
  for (const anim of animations) {
    if (scene.skipToEnd) break;
    const sprite = playerSprites[anim.playerId];
    const firstStep = anim.movement?.[stepIndex];
    if (!sprite || !firstStep) continue;

    const isInboundSpot = firstStep.coords.x <= 5 || firstStep.coords.x >= 95;
    const shouldClampXToRims =
      !isInboundSpot &&
      turnData?.result_type !== "SIDE_INBOUND" &&
      turnData?.result_type !== "BASELINE_INBOUND";
    const targetGridX = shouldClampXToRims
      ? Phaser.Math.Clamp(firstStep.coords.x, 9, 91)
      : firstStep.coords.x;

    const { x, y } = gridToPixels(
      targetGridX,
      firstStep.coords.y,
      scene.game.config.width,
      scene.game.config.height
    );

    // ✅ FIX: Use distance-based duration for consistent speed (matches step animations)
    // This ensures smooth transitions between turns and consistent speeds
    const duration = getPlayerDuration(sprite, x, y);

    promises.push(new Promise((resolve) => {
      const tween = scene.tweens.add({
        targets: [sprite],
        x,
        y,
        duration,
        ease: "Linear",
        onUpdate: () => {
          if (currentBallOwnerRef?.value === sprite && ballSprite?.setPosition) {
            ballSprite.setPosition(sprite.x, sprite.y);
            ballSprite.setVisible(true);
          }
        },
        onComplete: resolve,
        onStop: resolve
      });
      if (scene.skipToEnd) {
        tween.stop();
      }
    }));
  }

  await Promise.all(promises);
}

async function runStep0EntryPassIfNeeded({
  scene,
  ballSprite,
  playerSprites,
  currentBallOwnerRef,
  liveOwnerId,
  step0OwnerId,
}) {
  if (!scene || !ballSprite || !playerSprites) return false;
  if (liveOwnerId == null || step0OwnerId == null) return false;
  const fromRef = resolveSpriteById(playerSprites, liveOwnerId);
  const toRef = resolveSpriteById(playerSprites, step0OwnerId);
  const fromId = fromRef.id != null ? String(fromRef.id) : "";
  const toId = toRef.id != null ? String(toRef.id) : "";
  const fromSprite = fromRef.sprite;
  const toSprite = toRef.sprite;
  if (!fromId || !toId || fromId === toId || !fromSprite || !toSprite) return false;

  attachBallToPlayer(scene, ballSprite, fromSprite, { reason: "step0_entry_pass_start" });
  currentBallOwnerRef.value = fromSprite;
  setBallHolderId(scene, fromId);
  setCurrentOwner(scene, fromId);
  clearPendingOwner(scene);

  await runPass(scene, {
    fromId,
    toId,
    endCoords: { x: toSprite.x, y: toSprite.y },
    easing: "Sine.easeInOut",
  });

  attachBallToPlayer(scene, ballSprite, toSprite, { reason: "step0_entry_pass_complete" });
  currentBallOwnerRef.value = toSprite;
  setBallHolderId(scene, toId);
  setCurrentOwner(scene, toId);
  clearPendingOwner(scene);
  return true;
}

/**
 * HCO step 0 after Rim Runner hold-up: everyone except ball handler tweens to step 0; when PG arrives,
 * pass from ball handler (still at hold-up end) to PG; then finish remaining setup tweens; then BH → step 0.
 */
// Setup sideline inbound play
async function runSideInboundSetup({ scene, ballSprite, playerSprites, turnData, context = null }) {
  if (!turnData || scene?.skipToEnd || scene?.stateMachine?.is(States.FreeThrow)) return;
  const sideInboundSetupStartMs = Date.now();
  const sideInboundLeadInStartMs = Date.now();

  scene.isInboundSetup = true;
  
  // Allow transition from HalfCourt (after fouls) or other states
  // Only transition if not already in Inbound state
  if (!scene.stateMachine?.is(States.Inbound)) {
    // If coming from HalfCourt (e.g., after a foul), transition through Turnover first
    if (scene.stateMachine?.is(States.HalfCourt)) {
      safeTransition(
        scene.stateMachine,
        States.Turnover,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    }
    
    safeTransition(
      scene.stateMachine,
      States.Inbound,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }

  const { ball_spot, oDestinations = {}, dDestinations = {}, possession_team_id } = turnData;
  const offenseTeamId = scene.offenseTeamId ?? possession_team_id;

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  const cfg = globalThis?.animation_config?.sideInbound || {};
  const ease = cfg.ease ?? "Linear"; // Use Linear to match HCO step movements

  const offenseSprites = {};
  const defenseSprites = {};
  const offenseIds = {};

  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  if (!scene.ballSprite) scene.ballSprite = ballSprite;

  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (!info) continue;
    if (String(sprite.team_id) === String(offenseTeamId)) {
      offenseSprites[info.pos] = sprite;
      offenseIds[info.pos] = id;
    } else {
      defenseSprites[info.pos] = sprite;
    }
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
  }

  // ✅ Move ball to inbound spot immediately (matching BIP behavior)
  if (ball_spot && ballSprite?.setPosition) {
    const spotPx = gridToPixels(ball_spot.x, ball_spot.y, width, height);
    ballSprite.setPosition(spotPx.x, spotPx.y);
    ballSprite.setVisible(true);
    // Kill any existing ball tweens to ensure it stays at the spot
    if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  }

  // ✅ Move ball to inbound spot immediately (matching BIP behavior)
  if (ball_spot && ballSprite?.setPosition) {
    const spotPx = gridToPixels(ball_spot.x, ball_spot.y, width, height);
    ballSprite.setPosition(spotPx.x, spotPx.y);
    ballSprite.setVisible(true);
    // Kill any existing ball tweens to ensure it stays at the spot
    if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  }

  const promises = [];
  const sfSprite = offenseSprites["SF"];
  const sfId = offenseIds["SF"];
  validateInboundUnitCompletionContract({
    scene,
    turnData,
    playerSprites,
    unitId: "sip.lead_in.entry",
    advanceTrigger: "SIP route committed + inbounder resolved",
    visualSettleTrigger: "setup settled",
    unitStartMs: sideInboundLeadInStartMs,
    maxWaitGameSeconds: getInboundBudgetGameSeconds("setup", "SIDE_INBOUND"),
    authorizingEventReceived: true,
    requireOwner: false,
    requirePassNotInFlight: false,
    context: {
      inboundType: "SIDE_INBOUND",
      phase: "lead_in_entry",
      inbounderId: sfId ?? null,
      inbounderResolved: Boolean(sfSprite),
    },
  });
  
  const addTween = (sprite, coords, pos) => {
    if (!sprite || !coords) return;
    const { x, y } = gridToPixels(coords.x, coords.y, width, height);
    // Use distance-based duration for consistent speed
    const duration = getPlayerDuration(sprite, x, y);
    promises.push(
      new Promise((resolve) => {
        scene.tweens.add({
          targets: sprite,
          x,
          y,
          duration,
          ease,
          onStart: () => animationDebugLog(`tweenStart:${pos}`),
            onComplete: async () => {
            animationDebugLog(`tweenEnd:${pos}`);
            // ✅ Attach ball to SF when SF reaches the inbound spot (matching BIP behavior)
            if (pos === "SF" && sfSprite && ballSprite && ball_spot) {
              attachBallToPlayer(scene, ballSprite, sfSprite);
              animationDebugLog(`[sideInbound][ballAttach][SF] sf:${sfId}`);
              const holdMs = animationConfig.inbound?.holdAfterPlaceMs ?? 200;
              await new Promise(resolve => setTimeout(resolve, holdMs));
            }
            resolve();
          },
          onStop: async () => {
            animationDebugLog(`tweenEnd:${pos}`);
            // ✅ Also attach on stop (in case tween is interrupted)
            if (pos === "SF" && sfSprite && ballSprite && ball_spot) {
              attachBallToPlayer(scene, ballSprite, sfSprite);
              animationDebugLog(`[sideInbound][ballAttach][SF] sf:${sfId}`);
              const holdMs = animationConfig.inbound?.holdAfterPlaceMs ?? 200;
              await new Promise(resolve => setTimeout(resolve, holdMs));
            }
            resolve();
          }
        });
      })
    );
  };

  Object.entries(oDestinations).forEach(([pos, coords]) => addTween(offenseSprites[pos], coords, pos));
  Object.entries(dDestinations).forEach(([pos, coords]) => addTween(defenseSprites[pos], coords, pos));

  await Promise.all(promises);
  validateInboundUnitCompletionContract({
    scene,
    turnData,
    playerSprites,
    unitId: "sip.phase.setup_positions",
    advanceTrigger: "all ten players reach SIP setup destinations",
    visualSettleTrigger: "setup tweens settled",
    unitStartMs: sideInboundSetupStartMs,
    maxWaitGameSeconds: getInboundBudgetGameSeconds("setup", "SIDE_INBOUND"),
    authorizingEventReceived: true,
    requireOwner: false,
    requirePassNotInFlight: false,
    context: {
      inboundType: "SIDE_INBOUND",
      phase: "setup_positions",
      requiredMovers: ["all_10_players"],
    },
  });
  
  // ✅ TIMEOUT: Removed 2-second pause - timeout button is now always live

  const pgSprite = offenseSprites["PG"];
  const pgId = offenseIds["PG"];

  // ✅ REFACTOR: Use passDetection.js for dynamic passes, with resilient fallback
  // resolution before dropping to hardcoded SF→PG.
  const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
  
  // Check if turnData has animations with pass actions
  let passInfo = null;
  if (turnData.animations && Array.isArray(turnData.animations) && turnData.animations.length > 0) {
    // Find the step index where the pass happens (typically the last step after positioning)
    const maxSteps = Math.max(...turnData.animations.map(anim => anim.movement?.length || 0));
    if (maxSteps > 0) {
      // First try legacy expected boundary.
      passInfo = detectPassAtStep(turnData.animations, maxSteps - 1);
      // If not found, scan backward to pick up pass actions one step earlier.
      if (!passInfo) {
        for (let si = maxSteps - 2; si >= 0; si -= 1) {
          passInfo = detectPassAtStep(turnData.animations, si);
          if (passInfo) break;
        }
      }
    }
  }
  if (!passInfo && Array.isArray(turnData?.events)) {
    // Fallback to backend events payload when animation step pass markers are missing.
    const passEvt = turnData.events.find((evt) => String(evt?.type || evt?.event_type || "").toLowerCase() === "pass");
    const evtBy = String(passEvt?.by || passEvt?.from || "").trim().toUpperCase();
    const evtTo = String(passEvt?.to || "").trim().toUpperCase();
    const passerId =
      (evtBy && offenseIds[evtBy]) || (sfId ? String(sfId) : null);
    const receiverId =
      (evtTo && offenseIds[evtTo]) || (pgId ? String(pgId) : null);
    if (passerId && receiverId && passerId !== receiverId) {
      passInfo = {
        passerId,
        receiverId,
        stepIndex: 0,
        timestamp: Date.now(),
      };
    }
  }
  if (
    passInfo &&
    (!playerSprites?.[passInfo.passerId] || !playerSprites?.[passInfo.receiverId])
  ) {
    // Invalid dynamic pass payload; clear so fallback runPass is used.
    passInfo = null;
  }
  if (!passInfo && sfId && pgId && String(sfId) !== String(pgId)) {
    // Structured synthetic pass for cases where backend omitted explicit pass marker.
    passInfo = {
      passerId: String(sfId),
      receiverId: String(pgId),
      stepIndex: 0,
      timestamp: Date.now(),
      synthetic: true,
      reason: "sip_pass_marker_missing",
    };
  }
  if (passInfo?.synthetic) {
    console.log('🏀 [SIDE_INBOUND] Using synthetic passInfo fallback', passInfo);
  } else if (passInfo) {
    console.log('🏀 [SIDE_INBOUND] Using dynamic pass from animation/events', passInfo);
  } else {
    console.warn('🏀 [SIDE_INBOUND] Falling back to hardcoded SF→PG pass');
  }
  if (
    passInfo &&
    Number.isFinite(Number(passInfo.stepIndex)) &&
    Number(passInfo.stepIndex) < 0
  ) {
    passInfo = null;
  }
  if (
    passInfo &&
    !Number.isFinite(Number(passInfo.timestamp))
  ) {
    passInfo.timestamp = Date.now();
  }
  if (
    passInfo &&
    (typeof passInfo.passerId !== "string" || typeof passInfo.receiverId !== "string")
  ) {
    passInfo = null;
  }
  if (
    passInfo &&
    passInfo.passerId === passInfo.receiverId
  ) {
    passInfo = null;
  }
  if (
    passInfo &&
    (!playerSprites?.[passInfo.passerId] || !playerSprites?.[passInfo.receiverId])
  ) {
    passInfo = null;
  }
  if (!passInfo) {
    // Last-resort branch preserves existing behavior.
    console.log('🏀 [SIDE_INBOUND] Using fallback hardcoded SF→PG pass');
  }
  
  // Fallback to hardcoded SF→PG if no pass detected in animation data
  // ✅ Note: Ball is already attached to SF when SF reached the inbound spot (above)
  
  const sideInboundPassStartMs = Date.now();
  let sideInboundPassDelivered = false;
  if (sfSprite) {
    // ✅ Ball attachment already happened when SF reached the spot (in tween onComplete)
    // Only attach here as a safety fallback if attachment didn't happen
    const ballController = scene.ballController || (scene.ballSprite?.ballController);
    if (!ballController?.isAttached || ballController?.currentOwner !== sfSprite) {
      attachBallToPlayer(scene, ballSprite, sfSprite);
      animationDebugLog("ballAttach(SF) - fallback");
    }

    animationDebugLog(`[sideInbound][holdStart] sf:${sfId} pg:${pgId}`);
    // Removed 1000ms pause for smoother transitions

    scene.events?.once('passStart', () => animationDebugLog('passStart'));
    scene.events?.once('tweenStart', () => animationDebugLog('tweenStart'));
    scene.events?.once('tweenEnd', () => animationDebugLog('tweenEnd'));
    scene.events?.once('passEnd', () => animationDebugLog('passEnd'));

    animationDebugLog(`[sideInbound][passStart] sf:${sfId} pg:${pgId}`);
    
    // ✅ TIMEOUT: Removed markInboundPassStarted - button is always live now
    
    if (!scene.stateMachine?.is(States.FastBreak)) {
      // ✅ Force Foul: when next turn is Quick Foul, animate defender to receiver in same step as the pass
      const nextTurn = context?.nextTurn;
      const isQuickFoulNext = nextTurn?.quick_foul && nextTurn?.result_type === 'FOUL';
      const passPromise = passInfo
        ? handlePassAnimation({ scene, passInfo, playerSprites })
        : pgSprite
          ? runPass(scene, { fromId: sfId, toId: pgId, easing: ease })
          : Promise.resolve();

      let defenderPromise = Promise.resolve();
      if (isQuickFoulNext) {
        const receiverId = passInfo?.receiverId ?? pgId;
        const receiverSprite = playerSprites[receiverId];
        const defenderSprite = nextTurn.foul_player_id ? playerSprites[nextTurn.foul_player_id] : null;
        if (receiverSprite && defenderSprite) {
          defenderPromise = animateQuickFoulDefenderToReceiver(scene, defenderSprite, receiverSprite);
          nextTurn._quickFoulAnimatedDuringInbound = true;
        }
      }
      await Promise.all([passPromise, defenderPromise]);
      sideInboundPassDelivered = true;
    }

    validateInboundUnitCompletionContract({
      scene,
      turnData,
      playerSprites,
      unitId: "sip.phase.pass",
      advanceTrigger: "pass received",
      visualSettleTrigger: "ball flight + receiver settle",
      unitStartMs: sideInboundPassStartMs,
      maxWaitGameSeconds: getInboundBudgetGameSeconds("pass", "SIDE_INBOUND"),
      authorizingEventReceived: sideInboundPassDelivered,
      requireOwner: true,
      requirePassNotInFlight: true,
      context: {
        inboundType: "SIDE_INBOUND",
        phase: "pass",
      },
    });

    animationDebugLog(`[sideInbound][passEnd] sf:${sfId} pg:${pgId}`);
    if (pgSprite) {
      animationDebugLog(`[sideInbound][pgAttach] sf:${sfId} pg:${pgId}`);
    }
    if (scene.stateMachine?.is(States.Inbound))
      safeTransition(
        scene.stateMachine,
        States.HalfCourt,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    validateInboundUnitCompletionContract({
      scene,
      turnData,
      playerSprites,
      unitId: "sip.out.to_*",
      advanceTrigger: "route committed",
      visualSettleTrigger: "SIP final settle complete",
      unitStartMs: sideInboundPassStartMs,
      maxWaitGameSeconds: getInboundBudgetGameSeconds("pass", "SIDE_INBOUND"),
      authorizingEventReceived: true,
      requireOwner: false,
      requirePassNotInFlight: false,
      context: {
        inboundType: "SIDE_INBOUND",
        phase: "transition_out",
        route: String(turnData?.next_play_type || context?.nextTurn?.current_turn || "HCO"),
        stateIsHalfCourt: scene.stateMachine?.is(States.HalfCourt) === true,
      },
    });
  }
  if (!sfSprite) {
    validateInboundUnitCompletionContract({
      scene,
      turnData,
      playerSprites,
      unitId: "sip.phase.pass",
      advanceTrigger: "pass received",
      visualSettleTrigger: "ball flight + receiver settle",
      unitStartMs: sideInboundPassStartMs,
      maxWaitGameSeconds: getInboundBudgetGameSeconds("pass", "SIDE_INBOUND"),
      authorizingEventReceived: false,
      requireOwner: true,
      requirePassNotInFlight: true,
      context: {
        inboundType: "SIDE_INBOUND",
        phase: "pass",
        reason: "missing_sf_inbounder",
      },
    });
  }
  scene.isInboundSetup = false;
  scene.passInFlight = false;
  // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
}

// Setup positions after a defensive rebound before new half-court offense or fast break
async function runDefensiveReboundSetup({
  scene,
  ballSprite,
  playerSprites,
  rebounderId,
  nextPlayType = "HCO",
  turnData = null,
  authorityTurnData = null,
  suppressFastBreakReceiverAuthority = false,
}) {
  // Split contexts:
  // - authorityTurn: contract/role/result source for strict DREB outlet enforcement
  // - turnData: movement/get-back source (kept for backward compatibility)
  const currentIndex = scene?.currentTurn || 0;
  const authorityTurn =
    authorityTurnData ||
    turnData ||
    scene?.simData?.turns?.[currentIndex] ||
    null;

  // Get the offense_getback list from the MISS turn that led to this DREB
  // For Fast Break MISS → DREB, the offense_getback is from the previous HCO MISS turn
  // For regular HCO MISS → DREB, the offense_getback is from the current MISS turn
  // The turnData parameter is the current turn (for animations), but we may need to look
  // at the previous turn for offense_getback if this is a Fast Break MISS
  let missTurnForGetback = turnData;
  if (!missTurnForGetback || !missTurnForGetback.offense_getback) {
    // Try previous turn if current turn doesn't have offense_getback (Fast Break case)
    const previousTurn = scene.simData?.turns?.[currentIndex - 1];
    if ((previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") && previousTurn.offense_getback) {
      missTurnForGetback = previousTurn;
    } else if (!missTurnForGetback) {
      // Fallback: try current turn
      const currentTurn = scene.simData?.turns?.[currentIndex];
      if (currentTurn?.result_type === "MISS" || currentTurn?.result_type === "BLOCK") {
        missTurnForGetback = currentTurn;
      }
    }
  }
  
  const getBackList = missTurnForGetback?.offense_getback || [];
  const getBackSet = new Set(getBackList.map((id) => String(id)));
  const isFastBreakMissDrebToHco =
    Boolean(
      suppressFastBreakReceiverAuthority ||
      (turnData?.fast_break &&
        String(turnData?.rebound_type || "").toUpperCase() === "DREB" &&
        nextPlayType === "HCO")
    );
  const logDrebHandoff = (label, payload = {}) => {
    console.log(`[DREB HANDOFF][${label}]`, {
      turnId: authorityTurn?.turn_count ?? authorityTurn?.id ?? null,
      turnIndex: scene?.currentTurn ?? null,
      authorityResultType: authorityTurn?.result_type ?? null,
      authorityReboundType: authorityTurn?.rebound_type ?? null,
      authorityFastBreak: !!authorityTurn?.fast_break,
      nextPlayType,
      isFastBreakMissDrebToHco,
      suppressFastBreakReceiverAuthority,
      ...payload,
    });
  };
  
  // runDefensiveReboundSetup called
  
  animationDebugLog('runDefensiveReboundSetup called with:', { rebounderId, nextPlayType });
  if (!scene || !playerSprites || rebounderId == null) return;

  const rebounderRef = resolveSpriteById(playerSprites, rebounderId);
  const rebounderSprite = rebounderRef.sprite;
  rebounderId = rebounderRef.id;
  if (!rebounderSprite) return;
  const drebTelemetry = {
    branchKind: "dreb_hco_setup",
    turnId: authorityTurn?.turn_count ?? authorityTurn?.id ?? null,
    turnIndex: scene?.currentTurn ?? null,
    resultType: authorityTurn?.result_type ?? null,
    gameClock: scene?.simData?.clock ?? null,
    quarter: authorityTurn?.quarter ?? scene?.quarter ?? null,
    required: 0,
    fallback: 0,
    strictWarnings: 0,
    strictThrows: 0,
  };
  const emitDrebTelemetry = (event, payload = {}) => {
    scene?.events?.emit?.("animTelemetry", {
      event,
      branchKind: drebTelemetry.branchKind,
      turnId: drebTelemetry.turnId,
      turnIndex: drebTelemetry.turnIndex,
      resultType: drebTelemetry.resultType,
      gameClock: drebTelemetry.gameClock,
      quarter: drebTelemetry.quarter,
      timestampMs: Date.now(),
      ...payload,
    });
  };
  const enforceDrebStrict = ({ playerId, role, reason, allowThrow = true }) => {
    const mode = resolveDrebStrictMode();
    if (mode === "off") return;
    const msg = `[DREB contract] missing required endpoint (branch=dreb_hco_setup, playerId=${playerId ?? "?"}, role=${role ?? "?"}, reason=${reason ?? "unknown"})`;
    if (mode === "throw" && allowThrow) {
      drebTelemetry.strictThrows += 1;
      throw new Error(msg);
    }
    drebTelemetry.strictWarnings += 1;
    console.warn(msg, {
      playerId,
      role,
      reason,
      turnId: drebTelemetry.turnId,
      turnIndex: drebTelemetry.turnIndex,
      downgradedFromThrow: mode === "throw" && !allowThrow,
    });
  };
  const drebOutletCompletionContract = {
    unit_id: "hco.lead_in.from_dreb_outlet",
    execution_mode: "dynamic_event",
    advance_trigger: "outlet pass received",
    visual_settle_trigger: "outlet movement + pass settled",
    failure_policy: "throw",
  };
  const unitStartMs = Date.now();
  const drebUnitId = "hco.lead_in.from_dreb_outlet";
  const destinationSettleTolerancePx = 12;
  const getDrebUndeclaredHoldBudgetMs = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_DREB_OUTLET_UNDECLARED_HOLD_BUDGET_MS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 900;
  };
  const requiredMoverTargetsPx = new Map();
  const requiredMoverBestDeltaPx = new Map();
  const activeInterrupts = new Set(["rebound_secure"]);
  let strictBranchForWatchdog = false;
  let lastDestinationProgressAtMs = Date.now();
  let undeclaredHoldViolationEmitted = false;
  const registerRequiredMoverTarget = (playerId, targetPx) => {
    if (playerId == null || !targetPx) return;
    const moverId = String(playerId);
    requiredMoverTargetsPx.set(moverId, {
      x: Number(targetPx.x),
      y: Number(targetPx.y),
    });
    const moverRef = resolveSpriteById(playerSprites, moverId);
    const moverSprite = moverRef?.sprite;
    if (moverSprite) {
      const deltaPx = Phaser.Math.Distance.Between(
        Number(moverSprite.x),
        Number(moverSprite.y),
        Number(targetPx.x),
        Number(targetPx.y)
      );
      requiredMoverBestDeltaPx.set(moverId, deltaPx);
    } else {
      requiredMoverBestDeltaPx.delete(moverId);
    }
    lastDestinationProgressAtMs = Date.now();
  };
  const sampleRequiredMoverProgress = () => {
    const movers = [];
    let progressed = false;
    let allSettled = true;
    for (const [moverId, target] of requiredMoverTargetsPx.entries()) {
      const moverRef = resolveSpriteById(playerSprites, moverId);
      const moverSprite = moverRef?.sprite;
      if (!moverSprite) continue;
      const deltaPx = Phaser.Math.Distance.Between(
        Number(moverSprite.x),
        Number(moverSprite.y),
        Number(target.x),
        Number(target.y)
      );
      const bestDelta = Number(requiredMoverBestDeltaPx.get(moverId));
      if (!Number.isFinite(bestDelta) || deltaPx + 0.5 < bestDelta) {
        requiredMoverBestDeltaPx.set(moverId, deltaPx);
        progressed = true;
      }
      const settled = deltaPx <= destinationSettleTolerancePx;
      if (!settled) allSettled = false;
      movers.push({
        playerId: moverId,
        deltaPx: Number(deltaPx.toFixed(2)),
        settled,
      });
    }
    return {
      requiredMoverCount: movers.length,
      unsettled: movers.filter((row) => !row.settled),
      allSettled,
      progressed,
    };
  };
  const destinationProgressWatchdog = () => {
    if (activeInterrupts.size > 0 || undeclaredHoldViolationEmitted) return;
    const sample = sampleRequiredMoverProgress();
    if (sample.requiredMoverCount === 0) return;
    if (sample.progressed || sample.allSettled) {
      lastDestinationProgressAtMs = Date.now();
      return;
    }
    const nowMs = Date.now();
    const idleMs = nowMs - lastDestinationProgressAtMs;
    const stallBudgetMs = getDrebUndeclaredHoldBudgetMs();
    if (idleMs <= stallBudgetMs) return;
    undeclaredHoldViolationEmitted = true;
    emitDrebTelemetry("dreb_undeclared_hold_violation", {
      unitId: drebUnitId,
      violationType: "destination_progress_stalled_without_interrupt",
      allowedInterrupts: [
        "pass_in_flight",
        "rebound_secure",
        "dead_ball_or_whistle_stop",
        "period_end",
      ],
      activeInterrupts: Array.from(activeInterrupts),
      idleMs: Number(idleMs.toFixed(1)),
      stallBudgetMs,
      requiredMoverCount: sample.requiredMoverCount,
      unsettledMoverCount: sample.unsettled.length,
      unsettledMovers: sample.unsettled.slice(0, 8),
      strictBranch: strictBranchForWatchdog,
    });
  };
  scene?.events?.on?.("update", destinationProgressWatchdog);
  const drebOutletObserved = {
    authorizingEventReceived: false,
    visualSettled: false,
    finalOffensiveMoverSettled: false,
    shotTerminated: false,
  };

  scene.possessionFlipInProgress = true;
  try {
  // CRITICAL: Don't attach ball if a putback is in progress
  // The putback shot animation is still running, and attaching the ball here
  // causes a flash before the shot animation completes
  // ✅ PHASE 4: Check BallController state instead of old _putbackInProgress flag
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  const isPutbackInProgress = ballController && (ballController.reason === 'putback_shot' || ballController.state === 'PUTBACK_ATTEMPT');
  if (!isPutbackInProgress && ballSprite) {
    attachBallToPlayer(scene, ballSprite, rebounderSprite, {
      allowDuringPossessionFlip: true,
      debugInfo: { reason: "dreb_outlet_setup" },
    });
  }

  if (scene.stateMachine?.is(States.Rebound)) {
    if (DebugFlags?.FSM) animationDebugLog('FSM: Rebound -> OutletSetup');
    safeTransition(
      scene.stateMachine,
      States.OutletSetup,
      {
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      }
    );
  }

  const rebounderTeamKey = rebounderSprite.team;
  const { newOffenseTeam, newOffenseBasket } = deriveOffenseContext(rebounderTeamKey);
  const width = scene.game.config.width;
  const height = scene.game.config.height;

  const rebGridX = (rebounderSprite.x / width) * 100;
  const rebGridY = 50 - (rebounderSprite.y / height) * 50;
  const getFallbackOutletTarget = () => {
    const sign = newOffenseBasket.x > rebGridX ? 1 : -1;
    return {
      x: Phaser.Math.Clamp(
        rebGridX + sign * Phaser.Math.Between(3, 6),
        4,
        97
      ),
      y: Phaser.Math.Clamp(
        rebGridY + Phaser.Math.Between(-6, 6),
        1,
        50
      ),
    };
  };

  // Find the outlet pass receiver
  // For fast breaks that came from a previous turn (not a separate fast break turn),
  // we don't have outlet_receiver data, so we find the PG
  let outletReceiverId = null;
  let outletReceiverSprite = null;
  const isValidOutletReceiverRef = (ref) =>
    !!ref?.id &&
    !!ref?.sprite &&
    String(ref.id) !== String(rebounderId) &&
    String(ref.sprite.team) === String(rebounderSprite.team);

  // Prefer backend authority for outlet receiver when present.
  const receiverCandidates = isFastBreakMissDrebToHco
    ? []
    : [
        authorityTurn?.outlet_receiver_id,
        authorityTurn?.outletReceiverId,
        authorityTurn?.outlet_receiver,
        authorityTurn?.roles?.outlet_receiver,
        authorityTurn?.roles?.ball_handler_id,
        authorityTurn?.roles?.ball_handler?.player_id,
        authorityTurn?.ball_handler,
      ];
  for (const cid of receiverCandidates) {
    const ref = resolveSpriteById(playerSprites, cid);
    if (isValidOutletReceiverRef(ref)) {
      outletReceiverId = ref.id;
      outletReceiverSprite = ref.sprite;
      break;
    }
  }
  const drebOutletPassContract =
    !isFastBreakMissDrebToHco &&
    authorityTurn?.dreb_outlet_pass &&
    typeof authorityTurn.dreb_outlet_pass === "object"
      ? authorityTurn.dreb_outlet_pass
      : null;
  const contractPasserId =
    drebOutletPassContract?.passer_id ?? drebOutletPassContract?.passerId ?? null;
  const contractReceiverId =
    drebOutletPassContract?.receiver_id ?? drebOutletPassContract?.receiverId ?? null;
  const contractReceiverTarget = drebOutletPassContract?.receiver_target ?? drebOutletPassContract?.receiverTarget ?? null;
  logDrebHandoff("AUTHORITY", {
    rebounderId,
    receiverCandidates,
    hasDrebOutletPassContract: !!drebOutletPassContract,
    contractPasserId,
    contractReceiverId,
    contractReceiverTarget,
  });
  if (contractReceiverId != null) {
    const contractReceiverRef = resolveSpriteById(playerSprites, contractReceiverId);
    if (isValidOutletReceiverRef(contractReceiverRef)) {
      outletReceiverId = contractReceiverRef.id;
      outletReceiverSprite = contractReceiverRef.sprite;
      logDrebHandoff("CONTRACT RECEIVER APPLIED", {
        contractReceiverId,
        contractReceiverTeam: contractReceiverRef?.sprite?.team ?? null,
      });
    } else {
      logDrebHandoff("CONTRACT RECEIVER REJECTED", {
        contractReceiverId,
        rebounderTeam: rebounderSprite.team,
        contractReceiverTeam: contractReceiverRef?.sprite?.team ?? null,
      });
      emitDrebTelemetry("dreb_contract_missing_endpoint", {
        playerId: rebounderId,
        role: "outlet_receiver",
        requiredEndpointType: "dreb_outlet_pass",
        reason: "contract_receiver_invalid_or_wrong_team",
        contractReceiverId,
        rebounderTeam: rebounderSprite.team,
        contractReceiverTeam: contractReceiverRef?.sprite?.team ?? null,
      });
    }
  }
  
  // For HCO, always find the PG
  // CRITICAL: This must find the PG for the outlet pass to execute
  // First try scene.playerInfo (preferred, has position data)
  for (const [id, info] of Object.entries(scene.playerInfo || {})) {
    if (outletReceiverId) break;
    if (info.pos === "PG" && info.team === rebounderSprite.team) {
      const pgRef = resolveSpriteById(playerSprites, id);
      if (isValidOutletReceiverRef(pgRef)) {
        outletReceiverId = pgRef.id ?? id;
        outletReceiverSprite = pgRef.sprite;
        break;
      }
    }
  }
  
  // ✅ FALLBACK: If scene.playerInfo lookup failed, try finding PG from playerSprites
  // This can happen when runDefensiveReboundSetup() is called before scene.playerInfo is fully populated
  if (!outletReceiverId) {
    console.warn('🏀 [DREB OUTLET] PG not found in scene.playerInfo, trying fallback lookup from playerSprites', {
      rebounderTeam: rebounderSprite.team,
      playerInfoCount: Object.keys(scene.playerInfo || {}).length,
      playerSpritesCount: Object.keys(playerSprites).length
    });
    
    // Try to find PG by checking sprite properties or by position
    // Look for a sprite on the rebounder's team that might be the PG
    // We'll use the first player on the rebounder's team as a fallback
    for (const [id, sprite] of Object.entries(playerSprites)) {
      if (sprite.team === rebounderSprite.team && String(id) !== String(rebounderId)) {
        // Check if sprite has position info
        if (sprite.pos === "PG" || sprite.position === "PG") {
          const pgRef = resolveSpriteById(playerSprites, id);
          if (isValidOutletReceiverRef(pgRef)) {
            outletReceiverId = pgRef.id ?? id;
            outletReceiverSprite = pgRef.sprite;
            console.log('🏀 [DREB OUTLET] Found PG via fallback lookup', { outletReceiverId: id });
            break;
          }
        }
      }
    }
    
    // If still not found, use the first non-rebounder player on the rebounder's team as a last resort
    if (!outletReceiverId) {
      for (const [id, sprite] of Object.entries(playerSprites)) {
        if (sprite.team === rebounderSprite.team && String(id) !== String(rebounderId)) {
          const fallbackRef = resolveSpriteById(playerSprites, id);
          if (isValidOutletReceiverRef(fallbackRef)) {
            outletReceiverId = fallbackRef.id ?? id;
            outletReceiverSprite = fallbackRef.sprite;
            console.warn('🏀 [DREB OUTLET] Using fallback: first non-rebounder player as outlet receiver', { outletReceiverId: id });
            break;
          }
        }
      }
    }
  }
  
  // Always log outlet receiver lookup (not just when DebugFlags?.OUTLET is enabled)
  console.log('🏀 runDefensiveReboundSetup: Outlet receiver lookup', {
    rebounderId,
    rebounderTeam: rebounderSprite.team,
    nextPlayType,
    isFastBreakMissDrebToHco,
    outletReceiverId,
    hasOutletReceiverSprite: !!outletReceiverSprite,
    playerInfoCount: Object.keys(scene.playerInfo || {}).length,
    playerInfoKeys: Object.keys(scene.playerInfo || {}),
    playerInfoEntries: Object.entries(scene.playerInfo || {}).map(([id, info]) => ({
      id,
      pos: info.pos,
      team: info.team
    }))
  });
  logDrebHandoff("RECEIVER LOOKUP", {
    rebounderId,
    outletReceiverId,
    outletReceiverTeam: outletReceiverSprite?.team ?? null,
    rebounderTeam: rebounderSprite.team,
  });
  
  // Debug logging for outlet pass setup
  if (DebugFlags?.OUTLET) {
    animationDebugLog('Outlet setup debug:', {
      rebounderId,
      nextPlayType,
      outletReceiverId,
      rebounderSprite: rebounderSprite ? {
        team: rebounderSprite.team
      } : null,
      playerInfo: scene.playerInfo,
      allPlayerIds: Object.keys(scene.playerInfo || {})
    });
  }

  const promises = [];
  const isHalfCourtSetup =
    nextPlayType === "HCO" || nextPlayType === "HCT" || nextPlayType === "FCP";
  const requiresDrebOutletPassContract =
    !isFastBreakMissDrebToHco &&
    isHalfCourtSetup &&
    (authorityTurn?.result_type === "MISS" || authorityTurn?.result_type === "BLOCK") &&
    String(authorityTurn?.rebound_type || "").toUpperCase() === "DREB";
  strictBranchForWatchdog = requiresDrebOutletPassContract;
  const drebOutletBudgetGameSeconds = (() => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_DREB_OUTLET_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 8;
  })();
  const handoffTolerancePx = (() => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_DREB_OUTLET_HANDOFF_TOLERANCE_PX);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 12;
  })();
  const receiverTargetAuthorityMode = requiresDrebOutletPassContract
    ? "contract_receiver_target_only"
    : isFastBreakMissDrebToHco
      ? "transition_policy_only"
      : "mixed_legacy";
  const transitionTargetAuthorityMode = (requiresDrebOutletPassContract || isFastBreakMissDrebToHco)
    ? "transition_policy_only"
    : "animations_end_then_fallback";
  const applyGetBackExclusion = !requiresDrebOutletPassContract;
  const rebounderInfo = scene.playerInfo?.[String(rebounderId)] || null;
  const rebounderPos =
    rebounderInfo?.pos ||
    rebounderSprite?.pos ||
    rebounderSprite?.position ||
    null;
  const suppressHalfCourtOutletPass =
    requiresDrebOutletPassContract &&
    isHalfCourtSetup &&
    rebounderPos === "PG";
  console.log("🏀 [DREB OUTLET DEBUG] authority mode", {
    turnId: authorityTurn?.turn_count ?? authorityTurn?.id ?? null,
    resultType: authorityTurn?.result_type ?? null,
    reboundType: authorityTurn?.rebound_type ?? null,
    nextPlayType,
    strictBranch: requiresDrebOutletPassContract,
    receiverTargetAuthorityMode,
    transitionTargetAuthorityMode,
    applyGetBackExclusion,
    rebounderPos,
    suppressHalfCourtOutletPass,
  });
  let outletTarget = null;
  let outletTargetSource = "unset";
  let outletContext = null;

  if (suppressHalfCourtOutletPass) {
    outletReceiverId = null;
    outletReceiverSprite = null;
    console.log("🏀 [DREB OUTLET DEBUG] PG rebounder half-court exception applied", {
      rebounderId,
      rebounderPos,
      nextPlayType,
    });
  }

  // Set up outlet receiver movement and outlet pass for HCO ONLY
  // FAST_BREAK has its own outlet pass in the fast break sequence (animateOutletPhase in fastBreak.js)
  // These two outlet steps are MUTUALLY EXCLUSIVE - never run together
  if (!suppressHalfCourtOutletPass && outletReceiverId && String(outletReceiverId) !== String(rebounderId) && outletReceiverSprite && isHalfCourtSetup) {
    
    // SS&S: prefer backend animation end for receiver when available.
    drebTelemetry.required += 1;
    const sign = newOffenseBasket.x > rebGridX ? 1 : -1;
    const receiverAnimEndFromAuthority = isFastBreakMissDrebToHco
      ? null
      : getAnimationEndGridForPlayer(authorityTurn, outletReceiverId);
    const receiverAnimEndFromTurnData = getAnimationEndGridForPlayer(turnData, outletReceiverId);
    const currentReceiverGrid = {
      x: (outletReceiverSprite.x / width) * 100,
      y: 50 - (outletReceiverSprite.y / height) * 50,
    };
    const receiverTargetResolution = resolveDrebOutletReceiverTarget({
      requiresDrebOutletPassContract,
      contractReceiverTarget,
      authorityAnimEnd: receiverAnimEndFromAuthority,
      turnDataAnimEnd: receiverAnimEndFromTurnData,
      currentReceiverGrid,
      meaningfulDeltaThreshold: 1,
    });
    if (receiverTargetResolution.target) {
      outletTarget = receiverTargetResolution.target;
      outletTargetSource = receiverTargetResolution.source || "unknown";
      logDrebHandoff("RECEIVER TARGET RESOLVED", {
        outletReceiverId,
        outletTarget,
        outletTargetSource,
        resolutionReason: receiverTargetResolution.reason ?? null,
        currentReceiverGrid,
        receiverAnimEndFromAuthority,
        receiverAnimEndFromTurnData,
        contractReceiverTarget,
      });
      if (
        requiresDrebOutletPassContract &&
        receiverTargetResolution.reason === "contract_receiver_target_no_op"
      ) {
        emitDrebTelemetry("dreb_contract_receiver_target_no_op", {
          playerId: outletReceiverId,
          role: "outlet_receiver",
          requiredEndpointType: "dreb_outlet_pass.receiver_target",
          reason: receiverTargetResolution.reason,
        });
      }
    } else {
      drebTelemetry.fallback += 1;
      const resolutionReason =
        receiverTargetResolution.reason || "missing_outlet_receiver_animation_end";
      emitDrebTelemetry("dreb_fallback_used", {
        playerId: outletReceiverId,
        role: "outlet_receiver",
        fallbackPolicy: "receiver_near_rebounder",
        reason: resolutionReason,
      });
      emitDrebTelemetry("dreb_contract_missing_endpoint", {
        playerId: outletReceiverId,
        role: "outlet_receiver",
        requiredEndpointType: requiresDrebOutletPassContract
          ? "dreb_outlet_pass.receiver_target"
          : "animations_end",
        reason: resolutionReason,
      });
      enforceDrebStrict({
        playerId: outletReceiverId,
        role: "outlet_receiver",
        reason: resolutionReason,
        allowThrow: false,
      });
      if (requiresDrebOutletPassContract) {
        throw new Error(
          `[DREB contract] strict outlet receiver target required (branch=dreb_hco_setup, reason=${resolutionReason}, receiverId=${outletReceiverId ?? "?"})`
        );
      }
      outletTarget = getFallbackOutletTarget();
      outletTargetSource = "fallback.receiver_near_rebounder";
      logDrebHandoff("RECEIVER TARGET FALLBACK", {
        outletReceiverId,
        outletTarget,
        outletTargetSource,
        fallbackReason: resolutionReason,
        currentReceiverGrid,
        receiverAnimEndFromAuthority,
        receiverAnimEndFromTurnData,
        contractReceiverTarget,
      });
    }
    outletContext = {
      newOffenseTeam,
      newOffenseBasket,
      direction: sign,
    };

    const outletPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
    registerRequiredMoverTarget(outletReceiverId, outletPx);
    // Use distance-based duration for consistent speed (same as HCO step movements)
    // isTransition=true allows longer durations for transition movements
    const outletDuration = getPlayerDuration(outletReceiverSprite, outletPx.x, outletPx.y, true);
    const outletDeltaGrid = Phaser.Math.Distance.Between(
      currentReceiverGrid.x,
      currentReceiverGrid.y,
      outletTarget.x,
      outletTarget.y
    );
    const pickBounceGrid = (t) =>
      t && typeof t.ball_bounce_x === "number" && typeof t.ball_bounce_y === "number"
        ? { x: t.ball_bounce_x, y: t.ball_bounce_y }
        : null;
    const rebounderToOutletDeltaGrid = Phaser.Math.Distance.Between(
      rebGridX,
      rebGridY,
      outletTarget.x,
      outletTarget.y
    );
    const receiverToRebounderDeltaGrid = Phaser.Math.Distance.Between(
      currentReceiverGrid.x,
      currentReceiverGrid.y,
      rebGridX,
      rebGridY
    );
    console.log("🏀 [DREB OUTLET DEBUG] receiver movement plan", {
      turnId: authorityTurn?.turn_count ?? authorityTurn?.id ?? null,
      resultType: authorityTurn?.result_type ?? null,
      reboundType: authorityTurn?.rebound_type ?? null,
      nextPlayType,
      strictBranch: requiresDrebOutletPassContract,
      rebounderId,
      outletReceiverId,
      source: outletTargetSource,
      receiverStartGrid: {
        x: Number(currentReceiverGrid.x.toFixed(2)),
        y: Number(currentReceiverGrid.y.toFixed(2)),
      },
      outletTargetGrid: {
        x: Number(outletTarget.x.toFixed(2)),
        y: Number(outletTarget.y.toFixed(2)),
      },
      rebounderGridFromSprite: {
        x: Number(rebGridX.toFixed(2)),
        y: Number(rebGridY.toFixed(2)),
      },
      bounceGridAuthority: pickBounceGrid(authorityTurn),
      bounceGridTurnData: pickBounceGrid(turnData),
      bounceGridMissTurn: pickBounceGrid(missTurnForGetback),
      outletDeltaGrid: Number(outletDeltaGrid.toFixed(2)),
      rebounderToOutletTargetDeltaGrid: Number(rebounderToOutletDeltaGrid.toFixed(2)),
      receiverToRebounderDeltaGrid: Number(receiverToRebounderDeltaGrid.toFixed(2)),
      outletDurationMs: Math.round(outletDuration),
      contractReceiverId: contractReceiverId ?? null,
      contractPasserId: contractPasserId ?? null,
      contractReceiverTarget: contractReceiverTarget ?? null,
      newOffenseBasket: newOffenseBasket ?? null,
    });
    logDrebHandoff("PASS PLAN", {
      rebounderId,
      outletReceiverId,
      outletTarget,
      outletTargetSource,
      contractPasserId,
      contractReceiverId,
      contractReceiverTarget,
      receiverTargetAuthorityMode,
    });
    promises.push(
      tweenPlayerTo(scene, outletReceiverSprite, outletPx, {
        duration: outletDuration,
        easing: 'Linear', // Match HCO step movements for consistent feel
      })
    );
    
    if (DebugFlags?.BALL) {
      animationDebugLog('outletTarget', {
        outletReceiverId,
        outletTarget,
        nextPlayType,
        newOffenseTeam,
        rebounderTeam: rebounderSprite.team,
        attackRimX: newOffenseBasket.x,
        bounds: outletContext?.bounds,
      });
    }
    if (DebugFlags?.OUTLET) animationDebugLog(`${nextPlayType} outlet receiver movement queued`);
  } else if (isHalfCourtSetup) {
    // Log why outlet receiver movement was skipped (for debugging)
    console.warn('🏀 runDefensiveReboundSetup: Outlet receiver movement skipped', {
      outletReceiverId,
      rebounderId,
      hasOutletReceiverSprite: !!outletReceiverSprite,
      nextPlayType,
      reason: !outletReceiverId ? 'No outlet receiver found' : 
              outletReceiverId === rebounderId ? 'Outlet receiver is rebounder' :
              !outletReceiverSprite ? 'Outlet receiver sprite not found' :
              'Unknown reason'
    });
  }

  // For HCO and FAST_BREAK scenarios, move all other players toward the new offense basket
  // The difference is: HCO executes outlet pass here, FAST_BREAK handles outlet pass in its own sequence
  // But BOTH need players to animate into position during the outlet step
  if (isHalfCourtSetup || nextPlayType === "FAST_BREAK") {
    animationDebugLog('HCO scenario detected, moving other players toward new offense basket');
    // Determine the new offense basket
    // In defensive rebound: rebounder's team becomes the new offense team
    animationDebugLog('New offense basket:', newOffenseBasket, 'Rebounder team:', rebounderSprite.team, 'New offense team:', newOffenseTeam);
    
    // Debug: Check for extra sprites without playerInfo
    animationDebugLog('Player sprites keys:', Object.keys(playerSprites));
    animationDebugLog('Scene playerInfo keys:', Object.keys(scene.playerInfo || {}));
    const extraSprites = Object.keys(playerSprites).filter(id => !scene.playerInfo?.[id]);
    if (extraSprites.length > 0) {
      animationDebugWarn('EXTRA SPRITES DETECTED (no playerInfo):', extraSprites);
      // Hide these extra sprites
      extraSprites.forEach(id => {
        const sprite = playerSprites[id];
        if (sprite) {
          animationDebugLog(`Hiding extra sprite: ${id}`, { team: sprite.team, position: { x: sprite.x, y: sprite.y } });
          sprite.setVisible(false);
        }
      });
    }
    
    let playersMoved = 0;
    let playersSkipped = 0;
    let transitionPlayersFromAnimEnd = 0;
    let transitionPlayersFromFallback = 0;
    let playersSkippedReasons = {
      noInfo: 0,
      isRebounder: 0,
      isOutletReceiver: 0,
      isGetBackPlayer: 0
    };
    
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const isGetBackPlayer = applyGetBackExclusion && getBackSet.has(String(id));
      
      // Collect skip reasons for debugging
      let skipReason = null;
      if (String(id) === String(rebounderId)) {
        skipReason = 'isRebounder';
        playersSkippedReasons.isRebounder++;
      } else if (String(id) === String(outletReceiverId)) {
        skipReason = 'isOutletReceiver';
        playersSkippedReasons.isOutletReceiver++;
      } else if (isGetBackPlayer) {
        skipReason = 'isGetBackPlayer';
        playersSkippedReasons.isGetBackPlayer++;
      }
      
      // CRITICAL: Exclude get-back players from DREB animation
      // These players already animated back during the shot attempt, so animating them again
      // causes the extra animation step bug. They should already be in position.
      // 
      // BUG CHECK: If only get-back player animates, it means ALL OTHER players have a skipReason.
      // This suggests a condition might be inverted or all players are being incorrectly skipped.
      if (skipReason) {
        playersSkipped++;
        continue;
      }
      
      // SS&S: prefer backend animation end for this transition player.
      drebTelemetry.required += 1;
      const animEnd =
        transitionTargetAuthorityMode === "animations_end_then_fallback"
          ? getAnimationEndGridForPlayer(turnData, id)
          : null;
      const currentGridX = (sprite.x / width) * 100;
      const currentGridY = 50 - (sprite.y / height) * 50;
      
      // Move 20-30 grid spots toward new offense basket
      const distance = Phaser.Math.Between(20, 30);
      // Determine direction based on new offense team:
      // In defensive rebound: rebounder's team becomes the new offense team
      // If new offense team is home (basket at x=89), all players move right (increase x)
      // If new offense team is away (basket at x=11), all players move left (decrease x)
      const direction = newOffenseTeam === "home" ? 1 : -1;
      
      const targetGrid = animEnd || {
        x: Phaser.Math.Clamp(
          currentGridX + direction * distance,
          9,  // Stay between rims
          91
        ),
        y: Phaser.Math.Clamp(
          currentGridY + Phaser.Math.Between(-10, 10),
          10,  // Keep players well inside court
          40   // Keep players well inside court
        ),
      };
      if (!animEnd) {
        transitionPlayersFromFallback += 1;
        drebTelemetry.fallback += 1;
        emitDrebTelemetry("dreb_fallback_used", {
          playerId: id,
          role: "transition_player",
          fallbackPolicy: "advance_toward_new_offense_basket",
          reason:
            transitionTargetAuthorityMode === "transition_policy_only"
              ? "transition_policy_only_mode"
              : "missing_transition_player_animation_end",
        });
      } else {
        transitionPlayersFromAnimEnd += 1;
      }
      
      const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);
      registerRequiredMoverTarget(id, targetPx);
      // Use distance-based duration for consistent speed (same as HCO step movements)
      // isTransition=true allows longer durations for transition movements
      const playerDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y, true);
      
      // Animate player in DREB outlet step
      
      promises.push(
        tweenPlayerTo(scene, sprite, targetPx, {
          duration: playerDuration,
          easing: 'Linear', // Match HCO step movements for consistent feel
        }).then(() => {
          playersMoved++;
        })
      );
      
      animationDebugLog(`HCO player movement: ${id} from (${currentGridX.toFixed(1)}, ${currentGridY.toFixed(1)}) to (${targetGrid.x}, ${targetGrid.y}) [direction: ${direction}, newOffenseTeam: ${newOffenseTeam}]`);
    }
    
    const scheduledPlayers = promises.length;
    if (scheduledPlayers <= 1 && Object.keys(playerSprites).length > 2) {
      console.warn('⚠️ [OUTLET STEP] Few players animated:', {
        totalPlayers: Object.keys(playerSprites).length,
        playersAnimated: scheduledPlayers,
        playersSkipped,
        playersSkippedReasons
      });
    }
    console.log("🏀 [DREB OUTLET DEBUG] transition movement summary", {
      turnId: authorityTurn?.turn_count ?? authorityTurn?.id ?? null,
      strictBranch: requiresDrebOutletPassContract,
      transitionTargetAuthorityMode,
      applyGetBackExclusion,
      scheduledPlayers,
      transitionPlayersFromAnimEnd,
      transitionPlayersFromFallback,
      playersSkipped,
      playersSkippedReasons,
    });
    animationDebugLog(`Total players moved for HCO: ${scheduledPlayers}`);
  } else {
    animationDebugLog('Not HCO or FAST_BREAK scenario, nextPlayType:', nextPlayType);
  }

  await Promise.all(promises);
  activeInterrupts.delete("rebound_secure");
  drebOutletObserved.visualSettled = true;

  // Do outlet pass for HCO ONLY
  // FAST_BREAK outlet pass is handled separately in fastBreak.js (animateOutletPhase)
  // These two outlet steps are MUTUALLY EXCLUSIVE - never run together
  // For FCP/HCT: No outlet pass - players go directly to press positions
  // CRITICAL: This outlet pass step is required for smooth DREB -> HCO transitions
  // The outlet pass MUST execute if we have an outletReceiverId, even if receiver movement was skipped
  if (!suppressHalfCourtOutletPass && isHalfCourtSetup && outletReceiverId && String(outletReceiverId) !== String(rebounderId)) {
    // If outletReceiverSprite is missing, re-resolve with string/number-safe lookup.
    if (!outletReceiverSprite && outletReceiverId) {
      const receiverRef = resolveSpriteById(playerSprites, outletReceiverId);
      outletReceiverId = receiverRef.id ?? outletReceiverId;
      outletReceiverSprite = receiverRef.sprite;
      console.log('🏀 runDefensiveReboundSetup: Re-fetched outlet receiver sprite', {
        outletReceiverId,
        hasSprite: !!outletReceiverSprite
      });
    }
    
    // If outletTarget wasn't set (receiver movement was skipped), use receiver's current position
    if (!outletTarget && outletReceiverSprite) {
      outletTarget = {
        x: (outletReceiverSprite.x / width) * 100,
        y: 50 - (outletReceiverSprite.y / height) * 50
      };
      outletTargetSource = "receiver.current_position";
      console.log('🏀 runDefensiveReboundSetup: Using receiver current position as outlet target', outletTarget);
      const outletTargetPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
      registerRequiredMoverTarget(outletReceiverId, outletTargetPx);
    } else if (!outletTarget) {
      // If we still don't have outletTarget and no sprite, log a warning but proceed anyway
      // runPass will use the receiver's current position from playerSprites
      console.warn('🏀 runDefensiveReboundSetup: No outletTarget and no sprite, but proceeding with outlet pass', {
        outletReceiverId,
        outletTarget,
        hasOutletReceiverSprite: !!outletReceiverSprite
      });
    }
    const outletLog = {
      event: 'OUTLET_PASS',
      from: rebounderId,
      to: outletReceiverId,
      outletTarget,
      nextPlayType,
      startedAt: Date.now(),
    };
    if (outletContext) {
      outletLog.newOffenseTeam = outletContext.newOffenseTeam;
      outletLog.attackRim = outletContext.newOffenseBasket;
    } else {
      outletLog.newOffenseTeam = newOffenseTeam;
      outletLog.attackRim = newOffenseBasket;
    }
    // Always log outlet pass execution (not just when DebugFlags?.OUTLET is enabled)
    console.log('🏀 runDefensiveReboundSetup: Executing outlet pass', {
      from: rebounderId,
      to: outletReceiverId,
      nextPlayType,
      outletTarget: outletTarget ? `(${outletTarget.x}, ${outletTarget.y})` : 'null (will use receiver current position)',
      outletTargetSource,
      strictBranch: requiresDrebOutletPassContract,
      authorityTurnId: authorityTurn?.turn_count ?? authorityTurn?.id ?? null,
      authorityResultType: authorityTurn?.result_type ?? null,
    });
    logDrebHandoff("PASS START", {
      fromId: rebounderId,
      toId: outletReceiverId,
      outletTarget,
      outletTargetSource,
      strictBranch: requiresDrebOutletPassContract,
    });
    if (DebugFlags?.OUTLET) animationDebugLog(outletLog);
    if (DebugFlags?.OUTLET) animationDebugLog('Starting outlet pass animation...');
    
    // ✅ REFACTOR: Use centralized passDetection.js system for consistency.
    // For HCO MISS/BLOCK -> DREB -> half-court transitions, require backend outlet contract (no synthetic fallback).
    const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
    let passInfo = null;
    if (requiresDrebOutletPassContract) {
      const missingPasser = !contractPasserId;
      const missingReceiver = !contractReceiverId;
      const missingReceiverTarget =
        !contractReceiverTarget ||
        !Number.isFinite(Number(contractReceiverTarget?.x)) ||
        !Number.isFinite(Number(contractReceiverTarget?.y));
      const contractPasserMismatch =
        contractPasserId != null && String(contractPasserId) !== String(rebounderId);
      const contractReceiverRef = resolveSpriteById(playerSprites, contractReceiverId);
      const missingReceiverSprite = !contractReceiverRef.sprite;
      const contractReceiverWrongTeam =
        !!contractReceiverRef.sprite &&
        String(contractReceiverRef.sprite.team) !== String(rebounderSprite.team);
      if (missingPasser || missingReceiver || missingReceiverTarget || contractPasserMismatch || missingReceiverSprite || contractReceiverWrongTeam) {
        const reason = missingPasser
          ? "missing_contract_passer"
          : missingReceiver
            ? "missing_contract_receiver"
            : missingReceiverTarget
              ? "missing_contract_receiver_target"
            : contractPasserMismatch
              ? "contract_passer_mismatch_rebounder"
              : missingReceiverSprite
                ? "missing_contract_receiver_sprite"
                : "contract_receiver_wrong_team";
        emitDrebTelemetry("dreb_contract_missing_endpoint", {
          playerId: rebounderId,
          role: "outlet_pass",
          requiredEndpointType: "dreb_outlet_pass",
          reason,
          contractPasserId: contractPasserId ?? null,
          contractReceiverId: contractReceiverId ?? null,
          rebounderId,
        });
        throw new Error(
          `[DREB contract] missing required outlet pass contract (branch=dreb_hco_setup, reason=${reason}, rebounderId=${rebounderId ?? "?"})`
        );
      }
      passInfo = {
        passerId: contractPasserId,
        receiverId: contractReceiverRef.id ?? contractReceiverId,
        stepIndex: 0,
        timestamp: Date.now(),
      };
      console.log('🏀 [DREB OUTLET] Using backend outlet pass contract', passInfo);
    } else {
      if (authorityTurn?.animations && Array.isArray(authorityTurn.animations) && authorityTurn.animations.length > 0) {
        // Check if there's a pass action in the animation data
        const maxSteps = Math.max(...authorityTurn.animations.map(anim => anim.movement?.length || 0));
        if (maxSteps > 0) {
          passInfo = detectPassAtStep(authorityTurn.animations, maxSteps - 1);
        }
      }
      if (passInfo) {
        console.log('🏀 [DREB OUTLET] Using dynamic pass from animation data', passInfo);
      } else {
        // Fallback remains for non-strict branches only.
        passInfo = {
          passerId: rebounderId,
          receiverId: outletReceiverId,
          stepIndex: 0,
          timestamp: Date.now()
        };
        console.log('🏀 [DREB OUTLET] Using synthetic passInfo for non-strict branch', passInfo);
      }
    }
    scene.__drebOutletWindowActive = true;
    activeInterrupts.add("pass_in_flight");
    try {
      await handlePassAnimation({
        scene,
        passInfo,
        playerSprites
      });
      drebOutletObserved.authorizingEventReceived = true;
    } finally {
      activeInterrupts.delete("pass_in_flight");
      scene.__drebOutletWindowActive = false;
    }
    
    // Update ball ownership after pass completes
    if (requiresDrebOutletPassContract && outletReceiverSprite && outletTarget) {
      const outletTargetPx = gridToPixels(outletTarget.x, outletTarget.y, width, height);
      const handoffDeltaPx = Phaser.Math.Distance.Between(
        outletReceiverSprite.x,
        outletReceiverSprite.y,
        outletTargetPx.x,
        outletTargetPx.y
      );
      if (handoffDeltaPx > handoffTolerancePx) {
        emitDrebTelemetry("dreb_handoff_tolerance_breach", {
          playerId: outletReceiverId,
          tolerancePx: handoffTolerancePx,
          handoffDeltaPx: Number(handoffDeltaPx.toFixed(2)),
          outletTargetSource,
        });
        throw new Error(
          `[DREB contract] handoff tolerance breach (branch=dreb_hco_setup, playerId=${outletReceiverId ?? "?"}, deltaPx=${handoffDeltaPx.toFixed(2)}, tolerancePx=${handoffTolerancePx})`
        );
      }
    }
    setPendingOwner(scene, outletReceiverId);
    setCurrentOwner(scene, outletReceiverId);
    outletLog.completedAt = Date.now();
    console.log('🏀 runDefensiveReboundSetup: Outlet pass completed', {
      from: rebounderId,
      to: outletReceiverId
    });
    logDrebHandoff("PASS END", {
      fromId: rebounderId,
      toId: outletReceiverId,
      ballOwner: getCurrentOwner(scene),
      outletTarget,
      outletTargetSource,
      receiverLiveGrid: outletReceiverSprite
        ? {
            x: Number((((outletReceiverSprite.x / width) * 100)).toFixed(2)),
            y: Number(((50 - (outletReceiverSprite.y / height) * 50)).toFixed(2)),
          }
        : null,
    });
    if (DebugFlags?.OUTLET) animationDebugLog(outletLog);
    if (DebugFlags?.OUTLET) animationDebugLog('Outlet pass completed!');
  } else {
    // Always log when outlet pass is skipped (not just when DebugFlags?.OUTLET is enabled)
    console.warn('🏀 runDefensiveReboundSetup: Outlet pass skipped', { 
      outletReceiverId, 
      rebounderId,
      nextPlayType,
      reason: !outletReceiverId ? 'No outlet receiver found' : 
              outletReceiverId === rebounderId ? 'Outlet receiver is rebounder' : 
              nextPlayType === "FAST_BREAK" ? 'FAST_BREAK - outlet pass handled in fast break sequence (fastBreak.js)' :
              !isHalfCourtSetup ? `nextPlayType is "${nextPlayType}" (only half-court transitions execute outlet pass here)` :
              'Unknown reason'
    });
    if (DebugFlags?.OUTLET) {
      animationDebugLog('Outlet pass skipped:', { 
        outletReceiverId, 
        rebounderId,
        nextPlayType,
        reason: !outletReceiverId ? 'No outlet receiver found' : 
                outletReceiverId === rebounderId ? 'Outlet receiver is rebounder' : 
                nextPlayType === "FAST_BREAK" ? 'FAST_BREAK - outlet pass handled in fast break sequence' :
                !isHalfCourtSetup ? `nextPlayType is "${nextPlayType}"` : 
                'Unknown reason'
      });
    }
  }

  if (requiresDrebOutletPassContract) {
    const elapsedMs = Date.now() - unitStartMs;
    const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 350;
    const elapsedGameSeconds = elapsedMs / clockSecondMs;
    if (elapsedGameSeconds > drebOutletBudgetGameSeconds) {
      emitDrebTelemetry("dreb_clock_overrun", {
        elapsedMs,
        elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
        maxWaitGameSeconds: drebOutletBudgetGameSeconds,
      });
      throw new Error(
        `[DREB contract] transition budget overrun (branch=dreb_hco_setup, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${drebOutletBudgetGameSeconds})`
      );
    }
    enforceUnitCompletionContract({
      contract: drebOutletCompletionContract,
      observed: drebOutletObserved,
      context: {
        branchKind: drebTelemetry.branchKind,
        turnId: drebTelemetry.turnId,
        turnIndex: drebTelemetry.turnIndex,
        resultType: drebTelemetry.resultType,
      },
      emitTelemetry: emitDrebTelemetry,
      logger: console,
    });
  }

  if (scene.stateMachine?.is(States.OutletSetup)) {
    if (DebugFlags?.FSM) animationDebugLog('FSM: OutletSetup -> HalfCourt');
    safeTransition(
      scene.stateMachine,
      States.HalfCourt,
      {
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      }
    );
  }

  if (typeof scene.startNextHalfCourtOffense === "function") {
    scene.startNextHalfCourtOffense();
  }
  } finally {
    scene?.events?.off?.("update", destinationProgressWatchdog);
    scene.__drebOutletWindowActive = false;
    scene.possessionFlipInProgress = false;
    emitDrebTelemetry("dreb_telemetry_summary", {
      fbFallbackCount: drebTelemetry.fallback,
      fbRequiredRoleCount: drebTelemetry.required,
      fbFallbackRate: drebTelemetry.required > 0 ? drebTelemetry.fallback / drebTelemetry.required : 0,
      fbClampCount: 0,
      fbSnapCount: 0,
      drebStrictWarnings: drebTelemetry.strictWarnings,
      drebStrictThrows: drebTelemetry.strictThrows,
    });
  }
}

/**
 * Run offensive rebound kickout outlet setup animation
 * Similar to runDefensiveReboundSetup but for OREB kickout scenarios
 * 
 * @param {Object} params
 * @param {Object} params.scene - Phaser scene
 * @param {Object} params.ballSprite - Ball sprite
 * @param {Object} params.playerSprites - Player sprites dict
 * @param {string} params.rebounderId - Rebounder player ID
 * @param {string} params.pgId - Point guard player ID
 * @param {Object} [params.turnData] - Turn data (optional, for determining offense team)
 */
async function runOffensiveReboundKickoutSetup({ scene, ballSprite, playerSprites, rebounderId, pgId, turnData }) {
  animationDebugLog('runOffensiveReboundKickoutSetup called with:', { rebounderId, pgId });
  if (!scene || !playerSprites || rebounderId == null || pgId == null) return;

  const rebounderSprite = playerSprites[rebounderId];
  const pgSprite = playerSprites[pgId];
  if (!rebounderSprite || !pgSprite) {
    animationDebugWarn('runOffensiveReboundKickoutSetup: Missing sprites', {
      rebounderId,
      pgId,
      hasRebounder: !!rebounderSprite,
      hasPG: !!pgSprite
    });
    return;
  }

  // Attach ball to rebounder
  if (ballSprite) {
    attachBallToPlayer(scene, ballSprite, rebounderSprite);
  }

  // ✅ Determine if away team is on offense
  const offenseTeamId = turnData?.offense_team_id || turnData?.possession_team_id || scene.offenseTeamId;
  const homeTeamId = scene.simData?.home_team_id;
  const isAwayOffense = offenseTeamId && homeTeamId && offenseTeamId !== homeTeamId;

  // ✅ Helper function to flip coordinates for away team offense
  const flipCoords = (coords) => {
    return { x: 101 - coords.x, y: coords.y };
  };

  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const { HCO_STRING_SPOTS } = await import('../../utils/courtPositions.js');

  // PG moves to one of: key, deep key, upper midWing, deep upper wing, lower midWing, deep lower wing (randomized)
  const pgSpotOptions = [
    "key",
    "deep key",
    "upper midWing",
    "deep upper wing",
    "lower midWing",
    "deep lower wing"
  ];
  const selectedPGSpot = pgSpotOptions[Math.floor(Math.random() * pgSpotOptions.length)];
  let pgSpot = HCO_STRING_SPOTS[selectedPGSpot];
  
  if (!pgSpot) {
    animationDebugWarn('runOffensiveReboundKickoutSetup: Invalid PG spot selected', { selectedPGSpot });
    return;
  }

  // ✅ Apply coordinate flipping for away team offense
  if (isAwayOffense) {
    pgSpot = flipCoords(pgSpot);
  }

  // Determine PG's vertical half for rebounder constraint (based on original spot name, not flipped coords)
  const isPGUpperHalf = selectedPGSpot.includes("upper");
  const isPGLowerHalf = selectedPGSpot.includes("lower");
  const isPGCentral = selectedPGSpot === "key" || selectedPGSpot === "deep key";

  // Rebounder moves to: topLane, upper apex, lower apex, or key (if PG not at key)
  // Constraint: Rebounder must be on same vertical half as PG (or central)
  let rebounderSpotOptions = [];
  
  // Always allow topLane and key (vertically central)
  rebounderSpotOptions.push("topLane");
  if (selectedPGSpot !== "key") {
    rebounderSpotOptions.push("key");
  }

  // Add vertical half options based on PG position
  // If PG is central (key/deep key), rebounder can go to any vertical spot
  // If PG is upper half, rebounder can't go to lower apex
  // If PG is lower half, rebounder can't go to upper apex
  if (isPGCentral || isPGUpperHalf) {
    rebounderSpotOptions.push("upper apex");
  }
  if (isPGCentral || isPGLowerHalf) {
    rebounderSpotOptions.push("lower apex");
  }

  // Select random rebounder spot from valid options
  const selectedRebounderSpot = rebounderSpotOptions[Math.floor(Math.random() * rebounderSpotOptions.length)];
  let rebounderSpot = HCO_STRING_SPOTS[selectedRebounderSpot];
  
  if (!rebounderSpot) {
    animationDebugWarn('runOffensiveReboundKickoutSetup: Invalid rebounder spot selected', { selectedRebounderSpot });
    return;
  }

  // ✅ Apply coordinate flipping for away team offense
  if (isAwayOffense) {
    rebounderSpot = flipCoords(rebounderSpot);
  }

  animationDebugLog('runOffensiveReboundKickoutSetup: Selected spots', {
    pgSpot: selectedPGSpot,
    pgCoords: pgSpot,
    rebounderSpot: selectedRebounderSpot,
    rebounderCoords: rebounderSpot,
    isAwayOffense,
    offenseTeamId,
    homeTeamId
  });

  // Animate both players to their spots
  const promises = [];
  
  // Animate PG to outlet position
  const pgPx = gridToPixels(pgSpot.x, pgSpot.y, width, height);
  const pgDuration = getPlayerDuration(pgSprite, pgPx.x, pgPx.y, true);
  promises.push(
    tweenPlayerTo(scene, pgSprite, pgPx, {
      duration: pgDuration,
      easing: 'Linear',
    })
  );

  // Animate rebounder to outlet position
  const rebounderPx = gridToPixels(rebounderSpot.x, rebounderSpot.y, width, height);
  const rebounderDuration = getPlayerDuration(rebounderSprite, rebounderPx.x, rebounderPx.y, true);
  promises.push(
    tweenPlayerTo(scene, rebounderSprite, rebounderPx, {
      duration: rebounderDuration,
      easing: 'Linear',
    })
  );

  // Wait for both animations to complete
  await Promise.all(promises);

  animationDebugLog('runOffensiveReboundKickoutSetup: Outlet positioning complete');
}

/**
 * Animate the fouling defender moving to within 1-2 x spots and ±1 y spots of the receiver (Quick Foul after BIP/SIP).
 * Used in the same turn as the inbound pass so ball and defender move together.
 */
function animateQuickFoulDefenderToReceiver(scene, defenderSprite, receiverSprite) {
  if (!scene?.tweens || !defenderSprite || !receiverSprite) return Promise.resolve();
  const w = scene.game.config?.width ?? 1229;
  const h = scene.game.config?.height ?? 768;
  const spotW = w / 100;
  const spotH = h / 50;
  const offsetX = spotW * (Math.random() < 0.5 ? 1 : 2);
  const offsetY = spotH * (Math.random() * 2 - 1); // -1 to 1
  const target = { x: receiverSprite.x + offsetX, y: receiverSprite.y + offsetY };
  return tweenPlayerTo(scene, defenderSprite, target, { duration: 400, easing: 'Linear' });
}

// Setup baseline inbound play after a made basket
async function runInboundSetup({
  scene,
  ballSprite,
  playerSprites,
  newOffenseSide,
  homeTeamId,
  awayTeamId,
  skipRetreat = false,  // Allow skipping retreat for FCP/HCT
  pressureType = null,   // "FCP" or "HCT" to determine defensive positioning
  turnData = null,       // ✅ NEW: Optional turnData for dynamic pass detection
  context = null        // ✅ Force Foul: nextTurn so we can animate defender move in same turn
}) {
  const baselineInboundSetupStartMs = Date.now();
  const baselineInboundLeadInStartMs = Date.now();
  // ✅ CRITICAL: ALWAYS set scene.offenseTeamId to match newOffenseSide BEFORE doing anything else
  // This ensures that any code that reads scene.offenseTeamId will get the correct value
  const expectedOffenseTeamId = newOffenseSide === "home" ? homeTeamId : awayTeamId;
  if (!expectedOffenseTeamId) {
    console.error('❌ [INBOUND SETUP] Cannot determine expectedOffenseTeamId!', {
      newOffenseSide,
      homeTeamId,
      awayTeamId
    });
  }
  
  // ✅ SS&S: Possession flip removed from frontend (Fix 2 - Pattern A)
  // Backend now flips possession before creating BASELINE_INBOUND turn
  // Frontend just reads offense_team_id from turnData (handled by universal transition in turnPreparation.js)
  // This defensive check is no longer needed - backend is authoritative
  
  // ✅ SS&S: Set FCP/HCT state when pressureType is provided (called inline from ShotAnimationSystem)
  // This ensures state is set even when runInboundSetup is called directly, not from a BASELINE_INBOUND turn
  if (pressureType === "FCP" || pressureType === "HCT") {
    scene.currentPressureType = pressureType;
    scene.pressureSequenceActive = true;
  } else if (pressureType === null) {
    // Clear state if no pressure (normal inbound)
    scene.currentPressureType = null;
    scene.pressureSequenceActive = false;
  }
  
  if (scene?.stateMachine?.is(States.FreeThrow)) {
    animationDebugLog('runInboundSetup blocked - FreeThrow state');
    return;
  }
  
  animationDebugLog('runInboundSetup proceeding - not blocked by FreeThrow state');
  scene.isInboundSetup = true;
  if (!scene.stateMachine?.is(States.Inbound)) {
    // ✅ FIX: If coming from HalfCourt (e.g., after a made shot), transition through Turnover first
    // This matches the pattern in runSideInboundSetup() and prevents "Invalid transition: HalfCourt -> Inbound" warning
    if (scene.stateMachine?.is(States.HalfCourt)) {
      safeTransition(
        scene.stateMachine,
        States.Turnover,
        {
          stepIndex: 0,
          currentOwnerId: getCurrentOwner(scene),
          pendingOwnerId: getPendingOwner(scene),
        },
        ["stepIndex"]
      );
    }
    
    safeTransition(
      scene.stateMachine,
      States.Inbound,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  }
  if (!scene.ballSprite) scene.ballSprite = ballSprite;
  const isAwayOffense = newOffenseSide === "away";

  // Derive missing team IDs from sprite metadata
  if (!homeTeamId || !awayTeamId) {
    const sprites = Object.values(playerSprites);
    if (!homeTeamId) {
      homeTeamId = sprites.find(s => s.team === "home")?.team_id;
    }
    if (!awayTeamId) {
      awayTeamId = sprites.find(s => s.team === "away")?.team_id;
    }
  }

  const inboundTeamKey = isAwayOffense ? "away" : "home";
  const scoringTeamKey = isAwayOffense ? "home" : "away";
  const inboundTeamId = isAwayOffense ? awayTeamId : homeTeamId;
  const scoringTeamId = isAwayOffense ? homeTeamId : awayTeamId;
  const defaultBallSpot = isAwayOffense ? { x: 98, y: 16 } : { x: 3, y: 16 };
  const ballSpot = turnData?.ball_spot ?? defaultBallSpot;

  const homeOffsetRanges = {
    PG: { x: [8, 12], y: [-2, 2] },
    SG: { x: [12, 16], y: [-4, 4] },
    PF: { x: [10, 14], y: [6, 10] },
    C: { x: [10, 14], y: [-10, -6] }
  };
  const awayOffsetRanges = {
    PG: { x: [-12, -8], y: [-2, 2] },
    SG: { x: [-16, -12], y: [-4, 4] },
    PF: { x: [-14, -10], y: [6, 10] },
    C: { x: [-14, -10], y: [-10, -6] }
  };
  const ranges = isAwayOffense ? awayOffsetRanges : homeOffsetRanges;
  const inboundDest = {};
  for (const pos of ["PG", "SG", "PF", "C"]) {
    if (pos === "PF" || pos === "C") {
      // PF and C go to half court area
      inboundDest[pos] = {
        x: Phaser.Math.Between(40, 60),
        y: Phaser.Math.Between(15, 35)
      };
    } else {
      // PG and SG use offset-based positioning
      inboundDest[pos] = {
        x: ballSpot.x + Phaser.Math.Between(ranges[pos].x[0], ranges[pos].x[1]),
        y: ballSpot.y + Phaser.Math.Between(ranges[pos].y[0], ranges[pos].y[1])
      };
    }
  }

  const width = scene.game.config.width;
  const height = scene.game.config.height;

  // If FCP/HCT is next, position defenders in press formation
  const fcpDefensiveSetup = {};
  if (skipRetreat) {
    // Define defensive positions based on pressure type
    // FCP (Full Court Press): Aggressive full court pressure
    // HCT (Half Court Trap): Trap at half court line
    
    let basePositions;
    if (pressureType === "HCT") {
      // HCT: Half court trap positions (defenders closer to midcourt)
      basePositions = {
        PG: { x: 60, y: 25 },   // Just past midcourt
        SG: { x: 55, y: 35 },   // Upper side of half court
        SF: { x: 55, y: 15 },   // Lower side of half court
        PF: { x: 45, y: 30 },   // Opposite side upper
        C: { x: 45, y: 20 }     // Opposite side lower
      };
    } else {
      // FCP: Full court press positions (defenders spread across court)
      basePositions = {
        PG: { x: 80, y: 25 },   // Deep in offensive zone
        SG: { x: 73, y: 40 },   // Upper wing
        SF: { x: 73, y: 10 },   // Lower wing
        PF: { x: 37, y: 36 },   // Protecting opposite end
        C: { x: 35, y: 15 }     // Protecting opposite end
      };
    }

    // Apply positioning logic based on which team is defending
    // Midcourt is X=50
    // Left basket (away) is X=9, Right basket (home) is X=91
    for (const pos of ['PG', 'SG', 'SF', 'PF', 'C']) {
      let coords = basePositions[pos];
      
      if (isAwayOffense) {
        // AWAY on offense (attacking LEFT basket X=9), HOME defending LEFT basket
        // No flip needed - positions are already oriented correctly
        fcpDefensiveSetup[pos] = coords;
      } else {
        // HOME on offense (attacking RIGHT basket X=91), AWAY defending RIGHT basket
        // Flip X coordinates: 101 - x
        fcpDefensiveSetup[pos] = { x: 101 - coords.x, y: coords.y };
      }
    }
  }

  // Retreat scoring team toward midcourt (unless FCP is next)
  const usePayloadHcoSetup =
    !skipRetreat &&
    !pressureType &&
    turnData?.next_play_type === "HCO" &&
    turnData?.oDestinations &&
    turnData?.dDestinations;

  const retreatPromises = [];
  const retreatSprites = [];
  if (usePayloadHcoSetup) {
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      if (!info) continue;
      const targetPos = turnData.dDestinations?.[info.pos];
      if (
        !targetPos ||
        !(
          sprite.team_id === scoringTeamId ||
          (!scoringTeamId && sprite.team === scoringTeamKey)
        )
      ) {
        continue;
      }
      const targetPx = gridToPixels(targetPos.x, targetPos.y, width, height);
      const duration = getPlayerDuration(sprite, targetPx.x, targetPx.y, false);
      retreatSprites.push(sprite);
      retreatPromises.push(
        new Promise((resolve) => {
          let timeoutId;
          const tween = scene.tweens.add({
            targets: sprite,
            x: targetPx.x,
            y: targetPx.y,
            duration,
            ease: "Linear",
            onComplete: () => {
              if (timeoutId) clearTimeout(timeoutId);
              resolve();
            },
            onStop: () => {
              if (timeoutId) clearTimeout(timeoutId);
              resolve();
            }
          });
          const timeoutMs = Math.max(duration * 2, 1000);
          timeoutId = setTimeout(() => {
            if (tween && tween.isPlaying && tween.isPlaying()) {
              scene.tweens.killTweensOf(sprite);
            }
            resolve();
          }, timeoutMs);
        })
      );
    }
  } else if (!skipRetreat) {
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      if (!info) continue;
      if (
        sprite.team_id === scoringTeamId ||
        (!scoringTeamId && sprite.team === scoringTeamKey)
      ) {
        // Base x-coord for midcourt retreat (uniform for all defensive players)
        const baseX = isAwayOffense ? 45 : 55;
        // Randomize x-coord by ±10 from base for more organic feel
        const xOffset = Phaser.Math.Between(-10, 10);
        const targetXGrid = baseX + xOffset;
        const clampedTarget = clampGridCoords(
          { x: targetXGrid, y: 25 },
          turnData,
          { action: "retreat_to_midcourt", playerId: id }
        );
        const targetX = gridToPixels(
          clampedTarget.x,
          clampedTarget.y,
          width,
          height
        ).x;
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for retreat - should match inbound setup speed
        const retreatDuration = getPlayerDuration(sprite, targetX, sprite.y, false);
        retreatSprites.push(sprite);
        retreatPromises.push(
          new Promise((resolve) => {
            let timeoutId;
            const tween = scene.tweens.add({
              targets: sprite,
              x: targetX,
              y: sprite.y,
              duration: retreatDuration,
              ease: "Linear", // Match HCO step movements for consistent feel
              onComplete: () => {
                if (timeoutId) clearTimeout(timeoutId);
                resolve();
              },
              onStop: () => {
                if (timeoutId) clearTimeout(timeoutId);
                resolve();
              }
            });
            
            // Timeout safety: force resolve after 2x duration + buffer
            const timeoutMs = Math.max(retreatDuration * 2, 1000);
            timeoutId = setTimeout(() => {
              if (tween && tween.isPlaying && tween.isPlaying()) {
                scene.tweens.killTweensOf(sprite);
              }
              resolve();
            }, timeoutMs);
          })
        );
      }
    }
  } else if (Object.keys(fcpDefensiveSetup).length > 0) {
    // Move defending players to FCP press positions
    for (const [id, sprite] of Object.entries(playerSprites)) {
      const info = scene.playerInfo?.[id];
      if (!info) continue;
      
      // Check if this is a defending player
      if (
        sprite.team_id === scoringTeamId ||
        (!scoringTeamId && sprite.team === scoringTeamKey)
      ) {
        const targetPos = fcpDefensiveSetup[info.pos];
        if (targetPos) {
          const targetPx = gridToPixels(targetPos.x, targetPos.y, width, height);
          // Use distance-based duration for consistent speed (same as HCO step movements)
          // isTransition=true allows longer durations for transition movements
          const fcpDuration = getPlayerDuration(sprite, targetPx.x, targetPx.y, true);
          retreatSprites.push(sprite);
          retreatPromises.push(
            new Promise((resolve) => {
              let timeoutId;
              const tween = scene.tweens.add({
                targets: sprite,
                x: targetPx.x,
                y: targetPx.y,
                duration: fcpDuration,
                ease: "Linear", // Match HCO step movements for consistent feel
                onComplete: () => {
                  if (timeoutId) clearTimeout(timeoutId);
                  resolve();
                },
                onStop: () => {
                  if (timeoutId) clearTimeout(timeoutId);
                  resolve();
                }
              });
              
              // Timeout safety: force resolve after 2x duration + buffer
              const timeoutMs = Math.max(fcpDuration * 2, 1000);
              timeoutId = setTimeout(() => {
                if (tween && tween.isPlaying && tween.isPlaying()) {
                  scene.tweens.killTweensOf(sprite);
                }
                resolve();
              }, timeoutMs);
            })
          );
        }
      }
    }
  }

  // Identify SF/PG/SG/PF/C and freeze other inbound players
  let sfSprite = null;
  let pgSprite = null;
  let sgSprite = null;
  let pfSprite = null;
  let cSprite = null;
  let sfId = null;
  let pgId = null;
  let sgId = null;
  let pfId = null;
  let cId = null;
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (
      !info ||
      (sprite.team_id !== inboundTeamId &&
        !(inboundTeamId === undefined && sprite.team === inboundTeamKey))
    )
      continue;
    if (info.pos === "SF") {
      sfSprite = sprite;
      sfId = id;
    } else if (info.pos === "PG") {
      pgSprite = sprite;
      pgId = id;
    } else if (info.pos === "SG") {
      sgSprite = sprite;
      sgId = id;
    } else if (info.pos === "PF") {
      pfSprite = sprite;
      pfId = id;
    } else if (info.pos === "C") {
      cSprite = sprite;
      cId = id;
    }
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
  }

  if (!sfSprite || !pgSprite) {
    validateInboundUnitCompletionContract({
      scene,
      turnData,
      playerSprites,
      unitId: "bip.lead_in.entry",
      advanceTrigger: "BIP route committed + inbounder resolved",
      visualSettleTrigger: "baseline setup settled",
      unitStartMs: baselineInboundLeadInStartMs,
      maxWaitGameSeconds: getInboundBudgetGameSeconds("setup", "BASELINE_INBOUND"),
      authorizingEventReceived: false,
      requireOwner: false,
      requirePassNotInFlight: false,
      context: {
        inboundType: "BASELINE_INBOUND",
        phase: "lead_in_entry",
        inbounderResolved: false,
      },
    });
    scene.isInboundSetup = false;
    return;
  }
  validateInboundUnitCompletionContract({
    scene,
    turnData,
    playerSprites,
    unitId: "bip.lead_in.entry",
    advanceTrigger: "BIP route committed + inbounder resolved",
    visualSettleTrigger: "baseline setup settled",
    unitStartMs: baselineInboundLeadInStartMs,
    maxWaitGameSeconds: getInboundBudgetGameSeconds("setup", "BASELINE_INBOUND"),
    authorizingEventReceived: true,
    requireOwner: false,
    requirePassNotInFlight: false,
    context: {
      inboundType: "BASELINE_INBOUND",
      phase: "lead_in_entry",
      inbounderId: sfId ?? null,
      inbounderResolved: true,
    },
  });
  animationDebugLog(
    `[inbound][score][${newOffenseSide}] sf:${sfId} pg:${pgId} sg:${sgId} pf:${pfId} c:${cId}`
  );

  const spotPx = gridToPixels(ballSpot.x, ballSpot.y, width, height);

  // ✅ SS&S: For FCP/HCT, use step 0 positions from backend-provided skeleton data
  // Backend includes offense_setup_positions in BASELINE_INBOUND turn when next_defensive_setup is FCP/HCT
  // This positions offensive players in their press-break formation from the start
  let useSkeletonPositions = false;
  let skeletonPositions = {};
  
  if (skipRetreat && pressureType && turnData?.offense_setup_positions) {
    // Backend provided skeleton step 0 positions - convert to coords format
    const posActions = turnData.offense_setup_positions;
    
    // ✅ FIX: Helper function to flip coordinates for away team offense
    const flipCoords = (coords) => {
      return { x: 101 - coords.x, y: coords.y };
    };
    
    for (const [pos, actionData] of Object.entries(posActions)) {
      // ✅ FIX: Check coords first (has opp logic applied by backend), then fall back to location
      if (actionData.coords) {
        // Backend already applied opp logic and coordinate flipping - use as-is
        skeletonPositions[pos] = actionData.coords;
      } else if (actionData.location) {
        // Convert location string to coords (using HCO_STRING_SPOTS)
        const { HCO_STRING_SPOTS } = await import('../../utils/courtPositions.js');
        let coords = HCO_STRING_SPOTS[actionData.location];
        if (coords) {
          // ✅ FIX: Apply opp logic if opp field is set
          const hasOpp = actionData.opp === true;
          if (hasOpp) {
            // Player with opp=True should be on opposite side (defensive side)
            if (!isAwayOffense) {
              // Home team offense - ball handlers go to away side (defensive side)
              coords = flipCoords(coords);
            }
            // Away team offense - ball handlers stay on home side (no flip needed)
          } else {
            // Player without opp field stays on same side as normal offense
            if (isAwayOffense) {
              // Away team offense - outlet players go to away side (offensive side)
              coords = flipCoords(coords);
            }
            // Home team offense - outlet players stay on home side (no flip needed)
          }
          skeletonPositions[pos] = coords;
        }
      }
    }
    
    // Only use skeleton positions if we have positions for key players (SF and PG at minimum)
    if (skeletonPositions.SF && skeletonPositions.PG) {
      useSkeletonPositions = true;
    }
  }
  
  // ✅ NEW APPROACH: Don't skip inbound pass for FCP/HCT anymore
  // Players are positioned at skeleton step 0 locations (from backend setup positions)
  // We'll animate the inbound pass here, then skeleton starts from old step 1

  // Use skeleton positions if available, otherwise fall back to baseline inbound positions
  const payloadOffenseTargets = usePayloadHcoSetup ? turnData.oDestinations : null;
  const pgDest = useSkeletonPositions && skeletonPositions.PG
    ? skeletonPositions.PG
    : payloadOffenseTargets?.PG ?? inboundDest.PG;
  const sgDest = useSkeletonPositions && skeletonPositions.SG
    ? skeletonPositions.SG
    : payloadOffenseTargets?.SG ?? inboundDest.SG;
  const pfDest = useSkeletonPositions && skeletonPositions.PF
    ? skeletonPositions.PF
    : payloadOffenseTargets?.PF ?? inboundDest.PF;
  const cDest = useSkeletonPositions && skeletonPositions.C
    ? skeletonPositions.C
    : payloadOffenseTargets?.C ?? inboundDest.C;
  const sfDest = useSkeletonPositions && skeletonPositions.SF
    ? skeletonPositions.SF
    : payloadOffenseTargets?.SF ?? ballSpot;

  // 🔍 DEBUG: Log offensive player destinations (HCO only now - FCP/HCT returns above)
  // COMMENTED OUT: Verbose log - uncomment if needed for debugging
  // console.log('🔍 [HCO INBOUND] Offensive player destinations:', {
  //   newOffenseSide,
  //   positions: {
  //     PG: { grid: pgDest, source: 'baseline' },
  //     SG: { grid: sgDest, source: 'baseline' },
  //     SF: { grid: sfDest, source: 'baseline' },
  //     PF: { grid: pfDest, source: 'baseline' },
  //     C: { grid: cDest, source: 'baseline' }
  //   }
  // });

  const pgDestPx = gridToPixels(pgDest.x, pgDest.y, width, height);
  animationDebugLog(`inboundDest assigned for PG: (${pgDestPx.x},${pgDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const sgDestPx = gridToPixels(sgDest.x, sgDest.y, width, height);
  animationDebugLog(`inboundDest assigned for SG: (${sgDestPx.x},${sgDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const pfDestPx = gridToPixels(pfDest.x, pfDest.y, width, height);
  animationDebugLog(`inboundDest assigned for PF: (${pfDestPx.x},${pfDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const cDestPx = gridToPixels(cDest.x, cDest.y, width, height);
  animationDebugLog(`inboundDest assigned for C: (${cDestPx.x},${cDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);
  const sfDestPx = gridToPixels(sfDest.x, sfDest.y, width, height);
  animationDebugLog(`inboundDest assigned for SF: (${sfDestPx.x},${sfDestPx.y}) ${useSkeletonPositions ? '[SKELETON]' : '[BASELINE]'}`);

  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    scene.tweens.killTweensOf(sfSprite);
    scene.tweens.killTweensOf(pgSprite);
    if (sgSprite) scene.tweens.killTweensOf(sgSprite);
    if (pfSprite) scene.tweens.killTweensOf(pfSprite);
    if (cSprite) scene.tweens.killTweensOf(cSprite);
  }

  ballSprite.setVisible(true);
  animationDebugLog(`[inbound][rimHoldEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  const ballPickupPx = {
    x: Number.isFinite(Number(ballSprite?.x)) ? Number(ballSprite.x) : spotPx.x,
    y: Number.isFinite(Number(ballSprite?.y)) ? Number(ballSprite.y) : spotPx.y,
  };

  const sfTween = new Promise((resolve) => {
    const sfPickupDuration = getPlayerDuration(sfSprite, ballPickupPx.x, ballPickupPx.y, false);
    scene.tweens.add({
      targets: sfSprite,
      x: ballPickupPx.x,
      y: ballPickupPx.y,
      duration: sfPickupDuration,
      ease: "Linear",
      onComplete: () => {
        attachBallToPlayer(scene, ballSprite, sfSprite);
        const sfCarryDuration = getPlayerDuration(sfSprite, sfDestPx.x, sfDestPx.y, false);
        scene.tweens.add({
          targets: sfSprite,
          x: sfDestPx.x,
          y: sfDestPx.y,
          duration: sfCarryDuration,
          ease: "Linear",
          onUpdate: () => {
            if (ballSprite?.setPosition) {
              ballSprite.setPosition(sfSprite.x, sfSprite.y);
            }
          },
          onComplete: () => {
            animationDebugLog(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
            resolve();
          },
          onStop: () => {
            animationDebugLog(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
            resolve();
          }
        });
      },
      onStop: () => {
        attachBallToPlayer(scene, ballSprite, sfSprite);
        const sfCarryDuration = getPlayerDuration(sfSprite, sfDestPx.x, sfDestPx.y, false);
        scene.tweens.add({
          targets: sfSprite,
          x: sfDestPx.x,
          y: sfDestPx.y,
          duration: sfCarryDuration,
          ease: "Linear",
          onUpdate: () => {
            if (ballSprite?.setPosition) {
              ballSprite.setPosition(sfSprite.x, sfSprite.y);
            }
          },
          onComplete: () => {
            animationDebugLog(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
            resolve();
          },
          onStop: () => {
            animationDebugLog(`[inbound][sfTweenEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
            resolve();
          }
        });
      }
    });
  });

  const pgTween = new Promise((resolve) => {
    animationDebugLog("pgTween start");
    // Use distance-based duration for consistent speed (same as HCO step movements)
    // Use regular speed (not transition) for inbound setup - should be faster
    const pgDuration = getPlayerDuration(pgSprite, pgDestPx.x, pgDestPx.y, false);
    scene.tweens.add({
      targets: pgSprite,
      x: pgDestPx.x,
      y: pgDestPx.y,
      duration: pgDuration,
      ease: "Linear", // Match HCO step movements for consistent feel
      onComplete: () => {
        animationDebugLog("pgTween end");
        resolve();
      },
      onStop: () => {
        animationDebugLog("pgTween end");
        resolve();
      }
    });
  });

  const sgTween = sgSprite
    ? new Promise((resolve) => {
        animationDebugLog("sgTween start");
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for inbound setup - should be faster
        const sgDuration = getPlayerDuration(sgSprite, sgDestPx.x, sgDestPx.y, false);
        scene.tweens.add({
          targets: sgSprite,
          x: sgDestPx.x,
          y: sgDestPx.y,
          duration: sgDuration,
          ease: "Linear", // Match HCO step movements for consistent feel
          onComplete: () => {
            animationDebugLog("sgTween end");
            resolve();
          },
          onStop: () => {
            animationDebugLog("sgTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  const pfTween = pfSprite
    ? new Promise((resolve) => {
        animationDebugLog("pfTween start");
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for inbound setup - should be faster
        const pfDuration = getPlayerDuration(pfSprite, pfDestPx.x, pfDestPx.y, false);
        scene.tweens.add({
          targets: pfSprite,
          x: pfDestPx.x,
          y: pfDestPx.y,
          duration: pfDuration,
          ease: "Linear", // Match HCO step movements for consistent feel
          onComplete: () => {
            animationDebugLog("pfTween end");
            resolve();
          },
          onStop: () => {
            animationDebugLog("pfTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  const cTween = cSprite
    ? new Promise((resolve) => {
        animationDebugLog("cTween start");
        // Use distance-based duration for consistent speed (same as HCO step movements)
        // Use regular speed (not transition) for inbound setup - should be faster
        const cDuration = getPlayerDuration(cSprite, cDestPx.x, cDestPx.y, false);
        scene.tweens.add({
          targets: cSprite,
          x: cDestPx.x,
          y: cDestPx.y,
          duration: cDuration,
          ease: "Linear", // Match HCO step movements for consistent feel
          onComplete: () => {
            animationDebugLog("cTween end");
            resolve();
          },
          onStop: () => {
            animationDebugLog("cTween end");
            resolve();
          }
        });
      })
    : Promise.resolve();

  await advanceDynamicEventBoundary({
    requiredPromises: [sfTween, pgTween],
    scene,
    nonRequiredSprites: [
      ...retreatSprites,
      sgSprite,
      pfSprite,
      cSprite,
    ].filter(Boolean),
    settlePromises: [...retreatPromises, sgTween, pfTween, cTween],
    onAdvance: () =>
      validateInboundUnitCompletionContract({
        scene,
        turnData,
        playerSprites,
        unitId: "bip.phase.setup_positions",
        advanceTrigger: "SF and PG reached setup destinations",
        visualSettleTrigger: "SF and PG setup tweens settled",
        unitStartMs: baselineInboundSetupStartMs,
        maxWaitGameSeconds: getInboundBudgetGameSeconds("setup", "BASELINE_INBOUND"),
        authorizingEventReceived: true,
        requireOwner: false,
        requirePassNotInFlight: false,
        context: {
          inboundType: "BASELINE_INBOUND",
          phase: "setup_positions",
          requiredMovers: ["SF", "PG"],
        },
      }),
    onStopSprite: (sprite) => captureLiveSpriteGrid(sprite, width, height),
  });
  
  // ✅ TIMEOUT: Removed 2-second pause - timeout button is now always live

  animationDebugLog(`[inbound][ballAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  attachBallToPlayer(scene, ballSprite, sfSprite);
  
  const inboundHoldMs = animationConfig.inbound?.holdAfterPlaceMs ?? 200;
  await new Promise(resolve => setTimeout(resolve, inboundHoldMs));
  await new Promise(resolve => setTimeout(resolve, inboundHoldMs));

  animationDebugLog(`[inbound][holdStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  // Removed 1000ms pause for smoother transitions
  
  // ✅ TIMEOUT: Removed markInboundPassStarted - button is always live now

  // ✅ BIP → FCP/HCT: Execute inbound pass here (same as HCO). FCP/HCT turn will start at step 1 (step 0 done in BIP).
  // SIP (side inbound) always uses runSideInboundSetup() and never calls this function, so SIP is unaffected.

  if (scene.tweens) {
    scene.tweens.killTweensOf(ballSprite);
    scene.tweens.killTweensOf(pgSprite);
  }

  scene.events?.once('passStart', () => animationDebugLog('passStart'));
  scene.events?.once('tweenStart', () => animationDebugLog('tweenStart'));
  scene.events?.once('tweenEnd', () => animationDebugLog('tweenEnd'));
  scene.events?.once('passEnd', () => animationDebugLog('passEnd'));

  animationDebugLog(`[inbound][passStart][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  animationDebugLog(`[inbound][stateCheck] current state: ${scene.stateMachine?.state}, isFastBreak: ${scene.stateMachine?.is(States.FastBreak)}`);
  
  // ✅ REFACTOR: Use passDetection.js for dynamic passes, fallback to hardcoded SF→PG
  const { detectPassAtStep, handlePassAnimation } = await import('./passDetection.js');
  
  // Check if turnData has animations with pass actions
  let passInfo = null;
  if (turnData?.animations && Array.isArray(turnData.animations) && turnData.animations.length > 0) {
    // Find the step index where the pass happens (typically the last step after positioning)
    const maxSteps = Math.max(...turnData.animations.map(anim => anim.movement?.length || 0));
    // Check the last step for pass actions
    if (maxSteps > 0) {
      passInfo = detectPassAtStep(turnData.animations, maxSteps - 1);
    }
  }
  
  // Allow inbound pass regardless of current state (including FastBreak)
  // ✅ Force Foul: when next turn is Quick Foul, animate defender to receiver in same step as the pass
  const nextTurn = context?.nextTurn;
  const isQuickFoulNext = nextTurn?.quick_foul && nextTurn?.result_type === 'FOUL';
  const baselineInboundPassStartMs = Date.now();
  const passPromise = passInfo
    ? (console.log('🏀 [BASELINE_INBOUND] Using dynamic pass from animation data', passInfo),
       handlePassAnimation({ scene, passInfo, playerSprites }))
    : runPass(scene, { fromId: sfId, toId: pgId, duration: 500, easing: "Sine.easeInOut" });

  let defenderPromise = Promise.resolve();
  if (isQuickFoulNext) {
    const receiverId = passInfo?.receiverId ?? pgId;
    const receiverSprite = playerSprites[receiverId];
    const defenderSprite = nextTurn.foul_player_id ? playerSprites[nextTurn.foul_player_id] : null;
    if (receiverSprite && defenderSprite) {
      defenderPromise = animateQuickFoulDefenderToReceiver(scene, defenderSprite, receiverSprite);
      nextTurn._quickFoulAnimatedDuringInbound = true;
    }
  }
  await Promise.all([passPromise, defenderPromise]);
  validateInboundUnitCompletionContract({
    scene,
    turnData,
    playerSprites,
    unitId: "bip.phase.pass",
    advanceTrigger: "pass received",
    visualSettleTrigger: "ball flight + receiver settle",
    unitStartMs: baselineInboundPassStartMs,
    maxWaitGameSeconds: getInboundBudgetGameSeconds("pass", "BASELINE_INBOUND"),
    authorizingEventReceived: true,
    requireOwner: true,
    requirePassNotInFlight: true,
    context: {
      inboundType: "BASELINE_INBOUND",
      phase: "pass",
      skipRetreat: !!skipRetreat,
      pressureType: pressureType ?? null,
    },
  });

  animationDebugLog(`[inbound][passEnd][${newOffenseSide}] sf:${sfId} pg:${pgId}`);
  animationDebugLog(`[inbound][pgAttach][${newOffenseSide}] sf:${sfId} pg:${pgId}`);

  if (scene.stateMachine?.is(States.Inbound))
    safeTransition(
      scene.stateMachine,
      States.HalfCourt,
      {
        stepIndex: 0,
        currentOwnerId: getCurrentOwner(scene),
        pendingOwnerId: getPendingOwner(scene),
      },
      ["stepIndex"]
    );
  validateInboundUnitCompletionContract({
    scene,
    turnData,
    playerSprites,
    unitId: "bip.out.to_*",
    advanceTrigger: "route committed",
    visualSettleTrigger: "BIP final settle complete",
    unitStartMs: baselineInboundPassStartMs,
    maxWaitGameSeconds: getInboundBudgetGameSeconds("pass", "BASELINE_INBOUND"),
    authorizingEventReceived: true,
    requireOwner: false,
    requirePassNotInFlight: false,
    context: {
      inboundType: "BASELINE_INBOUND",
      phase: "transition_out",
      route: String(turnData?.next_play_type || context?.nextTurn?.current_turn || "HCO"),
      stateIsHalfCourt: scene.stateMachine?.is(States.HalfCourt) === true,
    },
  });

  scene.isInboundSetup = false;
  scene.passInFlight = false;
  
  // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
}


/**
 * Step-synchronized possession animation.
 * Each stepIndex is animated across all players, then the next step begins.
 * 
 * @param {Object} params - Animation parameters
 * @param {Object} params.scene - Phaser scene
 * @param {Object} params.simData - Simulation data
 * @param {Object} params.playerSprites - Player sprite map
 * @param {Object} params.turnData - Turn data object
 * @param {Object} params.ballSprite - Ball sprite
 * @param {Function} params.onAction - Action callback (optional)
 * @param {number} params.turnIndex - Turn index (optional, uses scene.currentTurn if not provided)
 * @param {Function} params.onUpdate - Update callback (optional, for future use)
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction, turnIndex, onUpdate }) {
  
  // ✅ SS&S: Use current_turn to detect FCP/HCT (replaces fragmented flags)
  const isFCPHCT = turnData?.current_turn === 'FCP' || turnData?.current_turn === 'HCT';
  const isHcoTurn = turnData?.current_turn === 'HCO';
  
  // ✅ REMOVED: Step-by-step animation logging (cluttering console)
  
  // Guard: Skip if this is an opening tip, putback, or if animations is missing
  // Putback turns are handled by handleOrebTurn in animateGameTurns.js
  if (turnData.result_type === "OPENING_TIP" || 
      turnData.result_type === "PUTBACK_MAKE" || 
      turnData.result_type === "PUTBACK_MISS" ||
      !turnData.animations) {
    if (turnData.result_type === "PUTBACK_MAKE" || turnData.result_type === "PUTBACK_MISS") {
      console.warn('⚠️ playTurnAnimation called for putback turn - this should be handled by handleOrebTurn:', turnData.result_type);
    } else {
    console.warn('⚠️ playTurnAnimation called for turn without animations:', turnData.result_type);
    }
    return;
  }

  // ✅ NEW (Step 1): Initialize simple ball holder state (WIP_GOB approach)
  initializeBallHolderState(scene);

  const fromInbound = scene._previousTurnWasInbound === true;
  const inboundLeadInSource = fromInbound
    ? String(scene._previousInboundTurnType || "").toUpperCase()
    : "";
  const fromOpeningTip = scene._previousTurnWasOpeningTip === true;

  scene.passInFlight = false;
  scene.rebounderId = null;
  // Only clear ball attachment/ownership when NOT coming directly from an inbound or opening tip,
  // so the ball can carry over with the inbound receiver or tip winner into HCO.
  if (!fromInbound && !fromOpeningTip) {
    // ✅ PHASE 4: Removed old ballDetached flag - BallController manages state internally
    clearPendingOwner(scene);
    // ✅ NEW (Step 1): Also clear simple ball holder state
    clearBallHolder(scene);
  }

  const currentBallOwnerRef = { value: null };
  // Store a reference on the scene so other modules (e.g., runPass)
  // can update ball ownership consistently.
  scene.currentBallOwnerRef = currentBallOwnerRef;
  const maxSteps = turnData.animations && turnData.animations.length > 0
    ? Math.max(
        ...turnData.animations
          .filter(anim => anim.movement && Array.isArray(anim.movement))
          .map(anim => anim.movement.length)
      )
    : 0;
  

  // ✅ Allow HCO turns even if state is FastBreak (can happen after defensive stop transition fails)
  // Check if this is an HCO turn (not fast_break and has animations) - if so, allow it
  const isHCOAfterFastBreak = !turnData.fast_break && 
                               (turnData.result_type === "MAKE" || turnData.result_type === "MISS" || turnData.result_type === "BLOCK") &&
                               turnData.animations?.length > 0 &&
                               scene.stateMachine?.is(States.FastBreak);
  
  // ✅ REMOVED: Special FCP/HCT FastBreak check - FCP/HCT now routes through AnimationRouter (same as HCO)
  if (scene.stateMachine?.is(States.FastBreak) && !isHCOAfterFastBreak) {
    return;
  }
  
  // If we're allowing HCO after FastBreak, force transition to HalfCourt
  if (isHCOAfterFastBreak) {
    console.log("🔄 playTurnAnimation: Forcing transition from FastBreak to HalfCourt for HCO turn");
    const { safeTransition, States: StateMachineStates } = await import('../state/gameStateMachine.js');
    safeTransition(scene.stateMachine, StateMachineStates.HalfCourt);
  }

  if (ballSprite && scene?.tweens) {
    // Always clear any stray tweens, but don't hide the ball if we're carrying over from inbound or opening tip
    scene.tweens.killTweensOf(ballSprite);
    if (!fromInbound && !fromOpeningTip) {
      ballSprite.setVisible(false);
    }
  }

  const homeTeamId = simData.home_team_id;
  let awayTeamId = simData.away_team_id;
  if (!awayTeamId) {
    const awaySprite = Object.values(playerSprites).find(s => s.team === "away");
    awayTeamId = awaySprite?.team_id;
    if (awayTeamId) simData.away_team_id = awayTeamId;
  }

  // Determine which player owns the ball at step 0
  // BUT: Skip this if the previous turn was a shot (MAKE or MISS)
  // EXCEPT: For FCP/HCT, we NEED step 0 ball attachment (SF holds ball at inbound spot)
  // isFCPHCT already declared above
  const previousTurnWasShot = scene._previousTurnWasShot === true;
  if (previousTurnWasShot && !isFCPHCT) {
    console.log('🏀 playTurnAnimation: Skipping step 0 ball attachment - previous turn was a shot (HCO only)');
    scene._previousTurnWasShot = false; // Clear the flag
  } else if (previousTurnWasShot && isFCPHCT) {
    console.log('🏀 playTurnAnimation: NOT skipping step 0 for FCP/HCT - need to attach ball to inbounder');
    scene._previousTurnWasShot = false; // Clear the flag
  }
  
  let step0OwnerSprite = null;
  let step0OwnerId = null;
  let requiresStep0EntryPass = false;
  let step0EntryPassFromId = null;
  for (const anim of turnData.animations) {
    if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) break;
    if (anim.hasBallAtStep?.[0]) {
      step0OwnerSprite = playerSprites[anim.playerId];
      break;
    }
  }

  if (step0OwnerSprite) {
    step0OwnerId = step0OwnerSprite.playerId;
    const liveOwnerId = getCurrentOwner(scene) ?? getPendingOwner(scene) ?? null;
    if (
      isHcoTurn &&
      liveOwnerId != null &&
      String(liveOwnerId) !== String(step0OwnerId)
    ) {
      requiresStep0EntryPass = true;
      step0EntryPassFromId = String(liveOwnerId);
    }
  }

  // If we are coming directly from an inbound or opening tip, the ball should already be attached
  // to the inbound receiver or tip winner, so we don't re-derive or re-attach at step 0.
  if (!previousTurnWasShot && !fromInbound && !fromOpeningTip && step0OwnerSprite) {
    const isPutbackTurn = turnData.result_type === "PUTBACK_MAKE" || turnData.result_type === "PUTBACK_MISS";

    if (isPutbackTurn) {
      // ✅ PHASE 4: Check BallController state instead of old _shotInProgress flag
      const { getBallController } = await import('./BallControllerAdapter.js');
      const ballController = getBallController();
      // CRITICAL: Don't attach ball for putback turns - handleOrebTurn handles it
      // This prevents the brief attachment flash before the putback shot
    } else if (!requiresStep0EntryPass) {
      attachBallToPlayer(scene, ballSprite, step0OwnerSprite);
      currentBallOwnerRef.value = step0OwnerSprite;

      // ✅ NEW (Step 1): Also set simple ball holder ID (WIP_GOB approach)
      // This enables the new simple ball animation system to track ball holder
      setBallHolderId(scene, step0OwnerId);
    }
  }

  // ✅ REMOVED: Special FCP/HCT FastBreak check - FCP/HCT now routes through AnimationRouter (same as HCO)
  // AnimationRouter handles routing, so no special state checks needed here
  if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) {
    return;
  }

  // ✅ NEW: Lock ball ownership to correct player at step
  animationDebugLog("🟡 inside playTurnAnimation → ");
  //print turnData here in the console logs
  animationDebugLog("turnData", turnData);
  // animationDebugLog("turnData.animations", turnData.animations);
  // animationDebugLog("turnData.possession_team_id", turnData.possession_team_id);
  // animationDebugLog("turnData.animations[0].hasBallAtStep", turnData.animations[0].hasBallAtStep);
  // animationDebugLog("turnData.animations[0].playerId", turnData.animations[0].playerId);
  // animationDebugLog("turnData.animations[0].movement", turnData.animations[0].movement);
  if (!requiresStep0EntryPass) {
    updateBallOwnership({
      scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      stepIndex: 0,
      offenseTeamId: scene.offenseTeamId ?? turnData.possession_team_id,
      currentBallOwnerRef,
    });
  }

  // Initial active player display update
  if (!scene.skipToEnd) {
    const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
    const ballHandlerId = getBallHandlerIdFromTurn(turnData, 0);
    const defenderId = getDefenderIdFromTurn(turnData);
    const homeTeamId = scene.simData?.home_team_id || null;
    if (ballHandlerId && homeTeamId) {
      updateActivePlayers(ballHandlerId, defenderId, homeTeamId, playerSprites);
    }
  }

  // Clear inbound and opening tip flags after applying pre-step setup
  if (scene._previousTurnWasInbound) {
    scene._previousTurnWasInbound = false;
    scene._previousInboundTurnType = null;
  }
  if (scene._previousTurnWasOpeningTip) {
    scene._previousTurnWasOpeningTip = false;
  }

  // ✅ REMOVED: Special FCP/HCT setup tween - FCP/HCT now routes through ShotAnimationSystem (same as HCO)
  // ShotAnimationSystem.runSetupTween() handles setup for all skeleton animations, including FCP/HCT

  let eventsProcessed = false;
  const clockSecondMs = scene?.gameClock?.getState?.().tickMs || 350;
  const stepClockSeconds = Array.isArray(turnData?.step_clock_seconds)
    ? turnData.step_clock_seconds
    : null;
  const getContractStepDurationMs = (stepIndex, fallbackDurationMs) => {
    const stepSeconds = stepClockSeconds?.[stepIndex];
    if (Number.isFinite(stepSeconds) && stepSeconds > 0) {
      return Math.max(50, Math.round(stepSeconds * clockSecondMs));
    }
    return fallbackDurationMs;
  };
  const currentTurnType = String(turnData?.current_turn || "").toUpperCase();
  const isPressureSkeletonTurn = currentTurnType === "FCP" || currentTurnType === "HCT";
  const emitHcoStepTelemetry = (event, payload = {}) => {
    const eventName = isPressureSkeletonTurn
      ? String(event || "").replace(/^hco_/, "pressure_")
      : event;
    scene?.events?.emit?.("animTelemetry", {
      event: eventName,
      branchKind: isPressureSkeletonTurn ? "pressure_step_movement" : "hco_step_movement",
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      currentTurn: currentTurnType || null,
      gameClock: scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? scene?.quarter ?? null,
      timestampMs: Date.now(),
      ...payload,
    });
  };
  const resolveHcoStepStrictMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = scope?.HCO_STEP_MOVEMENT_STRICT_CONTRACT;
    if (raw === "throw") return "throw";
    if (raw === "off" || raw === false) return "off";
    return "throw";
  };
  const hcoStepStrictMode = resolveHcoStepStrictMode();
  const resolvePressureStepContractMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = String(scope?.UESS_PRESSURE_STEP_CONTRACT_MODE ?? "warn")
      .trim()
      .toLowerCase();
    if (raw === "off" || raw === "warn" || raw === "throw") return raw;
    return "warn";
  };
  const pressureStepContractMode = resolvePressureStepContractMode();
  const getHcoStepTolerancePx = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_HCO_STEP_MOVEMENT_TOLERANCE_PX);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 18;
  };
  const getHcoStepFallbackBudgetGameSeconds = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_HCO_STEP_MOVEMENT_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 8;
  };
  const getHcoStepClockJitterSlackSeconds = (budgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_HCO_STEP_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_HCO_STEP_CLOCK_JITTER_RATIO);
    const absSlack = Number.isFinite(rawAbs) && rawAbs >= 0 ? rawAbs : 0.4;
    const ratioSlack =
      Number.isFinite(rawRatio) && rawRatio >= 0
        ? budgetSeconds * rawRatio
        : budgetSeconds * 0.35;
    return Math.max(absSlack, ratioSlack);
  };
  const getHcoStepPassClockJitterSlackSeconds = (budgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_HCO_STEP_PASS_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_HCO_STEP_PASS_CLOCK_JITTER_RATIO);
    const absSlack = Number.isFinite(rawAbs) && rawAbs >= 0 ? rawAbs : 1.0;
    const ratioSlack =
      Number.isFinite(rawRatio) && rawRatio >= 0
        ? budgetSeconds * rawRatio
        : budgetSeconds * 1.0;
    return Math.max(absSlack, ratioSlack);
  };
  const getPressureStepTolerancePx = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_PRESSURE_STEP_MOVEMENT_TOLERANCE_PX);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 18;
  };
  const getPressureStepFallbackBudgetGameSeconds = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_PRESSURE_STEP_MOVEMENT_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 8;
  };
  const getPressureStepClockJitterSlackSeconds = (budgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_PRESSURE_STEP_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_PRESSURE_STEP_CLOCK_JITTER_RATIO);
    const absSlack = Number.isFinite(rawAbs) && rawAbs >= 0 ? rawAbs : 0.4;
    const ratioSlack =
      Number.isFinite(rawRatio) && rawRatio >= 0
        ? budgetSeconds * rawRatio
        : budgetSeconds * 0.35;
    return Math.max(absSlack, ratioSlack);
  };
  const getPressureStepPassClockJitterSlackSeconds = (budgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_PRESSURE_STEP_PASS_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_PRESSURE_STEP_PASS_CLOCK_JITTER_RATIO);
    const absSlack = Number.isFinite(rawAbs) && rawAbs >= 0 ? rawAbs : 1.0;
    const ratioSlack =
      Number.isFinite(rawRatio) && rawRatio >= 0
        ? budgetSeconds * rawRatio
        : budgetSeconds * 1.0;
    return Math.max(absSlack, ratioSlack);
  };
  const isHCOSkeletonTurn =
    currentTurnType === "HCO" ||
    (!isFCPHCT &&
      !turnData?.fast_break &&
      (turnData?.result_type === "MAKE" ||
        turnData?.result_type === "MISS" ||
        turnData?.result_type === "BLOCK"));
  const isContractSkeletonTurn = isHCOSkeletonTurn || isPressureSkeletonTurn;
  const contractUnitPrefix = isPressureSkeletonTurn
    ? currentTurnType === "HCT"
      ? "hct"
      : "fcp"
    : "hco";
  const contractLabel = contractUnitPrefix.toUpperCase();
  const resolvePressureReworkPhase = () => {
    const scope = getDrebTelemetryScope();
    const raw = String(scope?.UESS_PRESSURE_REWORK_PHASE ?? "off")
      .trim()
      .toLowerCase();
    if (raw === "phase1_scaffold") return "phase1_scaffold";
    if (raw === "phase2_split") return "phase2_split";
    if (raw === "phase3_lead_in") return "phase3_lead_in";
    return "off";
  };
  const pressureReworkPhase = resolvePressureReworkPhase();
  const isPressureReworkPhase2Enabled =
    isPressureSkeletonTurn && pressureReworkPhase === "phase2_split";
  const isPressureReworkPhase3LeadInEnabled =
    isPressureSkeletonTurn && pressureReworkPhase === "phase3_lead_in";
  const resolvePressureReworkStepContractMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = String(scope?.UESS_PRESSURE_REWORK_STEP_CONTRACT_MODE ?? "")
      .trim()
      .toLowerCase();
    if (raw === "off" || raw === "warn" || raw === "throw") return raw;
    return null;
  };
  const pressureReworkStepContractMode = resolvePressureReworkStepContractMode();
  const resolvePressureReworkResolutionContractMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = String(scope?.UESS_PRESSURE_REWORK_RESOLUTION_CONTRACT_MODE ?? "")
      .trim()
      .toLowerCase();
    if (raw === "off" || raw === "warn" || raw === "throw") return raw;
    return null;
  };
  const resolvePressureReworkOutContractMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = String(scope?.UESS_PRESSURE_REWORK_OUT_CONTRACT_MODE ?? "")
      .trim()
      .toLowerCase();
    if (raw === "off" || raw === "warn" || raw === "throw") return raw;
    return null;
  };
  const pressureReworkResolutionContractMode =
    resolvePressureReworkResolutionContractMode();
  const pressureReworkOutContractMode = resolvePressureReworkOutContractMode();
  const activePressureStepStrictMode =
    isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled
      ? pressureReworkStepContractMode ?? pressureStepContractMode
      : pressureStepContractMode;
  const pressureReworkMovementDefaults = {
    tolerancePx: 22,
    passReceiverTolerancePx: 24,
    maxGameSeconds: 9,
    movementJitterAbsSeconds: 0.6,
    movementJitterRatio: 0.45,
    passJitterAbsSeconds: 1.2,
    passJitterRatio: 1.1,
  };
  const activeStepStrictMode = isPressureSkeletonTurn
    ? activePressureStepStrictMode
    : hcoStepStrictMode;
  const activePressureResolutionStrictMode =
    isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled
      ? pressureReworkResolutionContractMode ?? activePressureStepStrictMode
      : activePressureStepStrictMode;
  const activePressureOutStrictMode =
    isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled
      ? pressureReworkOutContractMode ?? activePressureStepStrictMode
      : activePressureStepStrictMode;
  const emitPressureReworkTelemetry = (event, payload = {}) => {
    if (!isPressureSkeletonTurn || pressureReworkPhase === "off") return;
    const row = {
      event,
      branchKind: "pressure_rework",
      phase: pressureReworkPhase,
      contractFamily: contractUnitPrefix,
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      gameClock: scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? scene?.quarter ?? null,
      timestampMs: Date.now(),
      ...payload,
    };
    scene?.events?.emit?.("animTelemetry", row);
    const scope = (typeof window !== "undefined" && window) || globalThis;
    try {
      scope.__PRESSURE_REWORK_LAST__ = row;
      if (!Array.isArray(scope.__PRESSURE_REWORK_BUFFER__)) {
        scope.__PRESSURE_REWORK_BUFFER__ = [];
      }
      scope.__PRESSURE_REWORK_BUFFER__.push(row);
      if (scope.__PRESSURE_REWORK_BUFFER__.length > 100) {
        scope.__PRESSURE_REWORK_BUFFER__.splice(
          0,
          scope.__PRESSURE_REWORK_BUFFER__.length - 100
        );
      }

      if (!scope.__PRESSURE_REWORK_SESSION__) {
        scope.__PRESSURE_REWORK_SESSION__ = {
          rows: 0,
          warnRows: 0,
          byFamily: {},
          leadInEvalRows: 0,
          movementPolicyRows: 0,
          passPolicyRows: 0,
          resolutionWarnRows: 0,
          outWarnRows: 0,
        };
      }
      const session = scope.__PRESSURE_REWORK_SESSION__;
      const eventKey = String(event || "");
      const familyKey = String(row.contractFamily || "unknown");
      session.byFamily[familyKey] = (session.byFamily[familyKey] || 0) + 1;
      if (eventKey === "pressure_rework_phase_active") session.rows += 1;
      if (eventKey === "pressure_lead_in_contract_eval") session.leadInEvalRows += 1;
      if (eventKey === "pressure_step_movement_policy_applied") session.movementPolicyRows += 1;
      if (eventKey === "pressure_step_pass_policy_applied") session.passPolicyRows += 1;
      if (eventKey === "pressure_resolution_contract_warn") session.resolutionWarnRows += 1;
      if (eventKey === "pressure_out_contract_warn") session.outWarnRows += 1;
      if (eventKey.endsWith("_warn")) session.warnRows += 1;

      const summaryEvery = Math.max(
        1,
        Math.floor(Number(scope.UESS_PRESSURE_REWORK_SUMMARY_EVERY ?? 5) || 5)
      );
      if (eventKey === "pressure_rework_phase_active" && session.rows % summaryEvery === 0) {
        const thresholds = {
          minRows: Math.max(
            1,
            Math.floor(Number(scope.UESS_PRESSURE_REWORK_WARN_MIN_ROWS ?? 10) || 10)
          ),
          warnRowsMax: Math.max(
            0,
            Math.floor(Number(scope.UESS_PRESSURE_REWORK_WARN_ROWS_MAX ?? 0) || 0)
          ),
          warnRateMax: Math.max(
            0,
            Number(scope.UESS_PRESSURE_REWORK_WARN_RATE_MAX ?? 0.02) || 0.02
          ),
        };
        const warnRate = session.rows > 0 ? Number((session.warnRows / session.rows).toFixed(4)) : 0;
        const hasEnoughRows = session.rows >= thresholds.minRows;
        const meetsWarnPromotionGate =
          hasEnoughRows &&
          session.warnRows <= thresholds.warnRowsMax &&
          warnRate <= thresholds.warnRateMax;
        const summary = {
          event: "pressure_rework_summary",
          phase: pressureReworkPhase,
          rows: session.rows,
          warnRows: session.warnRows,
          warnRate,
          leadInEvalRows: session.leadInEvalRows,
          movementPolicyRows: session.movementPolicyRows,
          passPolicyRows: session.passPolicyRows,
          resolutionWarnRows: session.resolutionWarnRows,
          outWarnRows: session.outWarnRows,
          byFamily: { ...session.byFamily },
          thresholds,
          hasEnoughRows,
          meetsWarnPromotionGate,
          timestampMs: Date.now(),
        };
        scope.__PRESSURE_REWORK_SUMMARY_LAST__ = summary;
        if (!Array.isArray(scope.__PRESSURE_REWORK_SUMMARY_BUFFER__)) {
          scope.__PRESSURE_REWORK_SUMMARY_BUFFER__ = [];
        }
        scope.__PRESSURE_REWORK_SUMMARY_BUFFER__.push(summary);
        if (scope.__PRESSURE_REWORK_SUMMARY_BUFFER__.length > 50) {
          scope.__PRESSURE_REWORK_SUMMARY_BUFFER__.splice(
            0,
            scope.__PRESSURE_REWORK_SUMMARY_BUFFER__.length - 50
          );
        }
        scene?.events?.emit?.("animTelemetry", summary);
      }
    } catch (_) {
      // Pressure rework debug mirror should never impact gameplay.
    }
  };
  const resolvePressureLeadInContractMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = String(scope?.UESS_PRESSURE_LEAD_IN_CONTRACT_MODE ?? "off")
      .trim()
      .toLowerCase();
    if (raw === "warn" || raw === "true" || raw === "on") return "warn";
    return "off";
  };
  const pressureLeadInContractMode = resolvePressureLeadInContractMode();
  const getPressureReworkStepTolerancePx = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_PRESSURE_REWORK_STEP_MOVEMENT_TOLERANCE_PX);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return pressureReworkMovementDefaults.tolerancePx;
  };
  const getPressureReworkStepFallbackBudgetGameSeconds = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_PRESSURE_REWORK_STEP_MOVEMENT_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return pressureReworkMovementDefaults.maxGameSeconds;
  };
  const getPressureReworkStepClockJitterSlackSeconds = (budgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_PRESSURE_REWORK_STEP_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_PRESSURE_REWORK_STEP_CLOCK_JITTER_RATIO);
    const absSlack =
      Number.isFinite(rawAbs) && rawAbs >= 0
        ? rawAbs
        : pressureReworkMovementDefaults.movementJitterAbsSeconds;
    if (Number.isFinite(rawRatio) && rawRatio >= 0) {
      return Math.max(absSlack, budgetSeconds * rawRatio);
    }
    return Math.max(absSlack, budgetSeconds * pressureReworkMovementDefaults.movementJitterRatio);
  };
  const getPressureReworkStepPassClockJitterSlackSeconds = (budgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_PRESSURE_REWORK_STEP_PASS_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_PRESSURE_REWORK_STEP_PASS_CLOCK_JITTER_RATIO);
    const absSlack =
      Number.isFinite(rawAbs) && rawAbs >= 0
        ? rawAbs
        : pressureReworkMovementDefaults.passJitterAbsSeconds;
    if (Number.isFinite(rawRatio) && rawRatio >= 0) {
      return Math.max(absSlack, budgetSeconds * rawRatio);
    }
    return Math.max(absSlack, budgetSeconds * pressureReworkMovementDefaults.passJitterRatio);
  };
  const getPressureReworkStepPassReceiverTolerancePx = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_PRESSURE_REWORK_STEP_PASS_RECEIVER_TOLERANCE_PX);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return pressureReworkMovementDefaults.passReceiverTolerancePx;
  };
  const getPressureReworkStepMinBudgetGameSeconds = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_PRESSURE_REWORK_STEP_MIN_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 2;
  };
  const getActivePressureStepTolerancePx = () =>
    isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled
      ? getPressureReworkStepTolerancePx()
      : getPressureStepTolerancePx();
  const getActivePressureStepFallbackBudgetGameSeconds = () =>
    isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled
      ? getPressureReworkStepFallbackBudgetGameSeconds()
      : getPressureStepFallbackBudgetGameSeconds();
  const getActivePressureStepClockJitterSlackSeconds = (budgetSeconds) =>
    isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled
      ? getPressureReworkStepClockJitterSlackSeconds(budgetSeconds)
      : getPressureStepClockJitterSlackSeconds(budgetSeconds);
  const getActivePressureStepPassClockJitterSlackSeconds = (budgetSeconds) =>
    isPressureReworkPhase2Enabled
      ? getPressureReworkStepPassClockJitterSlackSeconds(budgetSeconds)
      : getPressureStepPassClockJitterSlackSeconds(budgetSeconds);
  const getActivePressureStepPassReceiverTolerancePx = () =>
    isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled
      ? getPressureReworkStepPassReceiverTolerancePx()
      : getPressureStepTolerancePx();
  if (isPressureSkeletonTurn && pressureReworkPhase !== "off") {
    emitPressureReworkTelemetry("pressure_rework_phase_active", {
      phase2PolicySplitEnabled: isPressureReworkPhase2Enabled,
      phase3LeadInScaffoldEnabled: isPressureReworkPhase3LeadInEnabled,
      legacyPressureStepContractMode: pressureStepContractMode,
      pressureReworkStepContractMode:
        pressureReworkStepContractMode ?? "inherit_legacy",
      activePressureStepStrictMode,
      pressureReworkResolutionContractMode:
        pressureReworkResolutionContractMode ?? "inherit_step_mode",
      pressureReworkOutContractMode:
        pressureReworkOutContractMode ?? "inherit_step_mode",
      activePressureResolutionStrictMode,
      activePressureOutStrictMode,
    });
  }
  if (isPressureReworkPhase3LeadInEnabled) {
    const leadInSource = fromInbound
      ? inboundLeadInSource || "UNKNOWN_INBOUND"
      : "NON_INBOUND_ENTRY";
    const leadInUnitId = `${contractUnitPrefix}.lead_in.entry`;
    const leadInContractDraft = {
      unit_id: leadInUnitId,
      execution_mode: "dynamic_event",
      advance_trigger: `${contractLabel} route committed + entry owner resolved`,
      visual_settle_trigger:
        contractUnitPrefix === "hct"
          ? "trap entry handoff settled"
          : "press entry handoff settled",
      failure_policy: "warn",
    };
    emitPressureReworkTelemetry("pressure_lead_in_contract_active", {
      leadInSource,
      leadInContractDraft,
    });
  }
  const pressureUnitContractsDraft =
    isPressureSkeletonTurn && pressureReworkPhase !== "off"
      ? {
          stepMovement: {
            advance_trigger: "required movers reach step-n targets",
            visual_settle_trigger: "required step-n tweens complete",
          },
          stepPass: {
            advance_trigger: "pass received",
            visual_settle_trigger: "ball flight + receiver settle",
          },
          resolution: {
            advance_trigger: "result committed",
            visual_settle_trigger: "resolution visuals settled",
          },
          transitionOut: {
            advance_trigger: "route committed",
            visual_settle_trigger: `${contractLabel} boundary settle complete`,
          },
        }
      : null;
  const isHcoLeadInFromInbound =
    isHCOSkeletonTurn &&
    fromInbound &&
    (inboundLeadInSource === "BASELINE_INBOUND" || inboundLeadInSource === "SIDE_INBOUND");
  const hcoStepMovementContract = {
    unit_id: `${contractUnitPrefix}.step[n].movement`,
    execution_mode: "skeleton",
    advance_trigger:
      pressureUnitContractsDraft?.stepMovement?.advance_trigger ??
      "required movers reach step-n targets",
    visual_settle_trigger:
      pressureUnitContractsDraft?.stepMovement?.visual_settle_trigger ??
      "required step-n tweens complete",
    failure_policy: activeStepStrictMode === "throw" ? "throw" : "warn",
  };
  const hcoStepPassContract = {
    unit_id: `${contractUnitPrefix}.step[n].pass`,
    execution_mode: "skeleton",
    advance_trigger:
      pressureUnitContractsDraft?.stepPass?.advance_trigger ?? "pass received",
    visual_settle_trigger:
      pressureUnitContractsDraft?.stepPass?.visual_settle_trigger ??
      "ball flight + receiver settle",
    failure_policy: activeStepStrictMode === "throw" ? "throw" : "warn",
  };
  const resolveHcoLeadInInboundStrictMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = scope?.HCO_LEAD_IN_FROM_INBOUND_STRICT_CONTRACT;
    if (raw === "throw") return "throw";
    if (raw === "warn" || raw === true) return "warn";
    if (raw === "off" || raw === false) return "off";
    // Rollout default for this unit: warn before throw.
    return "warn";
  };
  const hcoLeadInInboundStrictMode = resolveHcoLeadInInboundStrictMode();
  const getHcoLeadInInboundBudgetGameSeconds = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_HCO_LEAD_IN_FROM_INBOUND_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw > 0) return raw;
    return 8;
  };
  const hcoLeadInFromInboundContract = {
    unit_id: "hco.lead_in.from_sip_or_bip",
    execution_mode: "dynamic_event",
    advance_trigger: "inbound pass received",
    visual_settle_trigger: "inbound setup + pass settled",
    failure_policy: hcoLeadInInboundStrictMode === "throw" ? "throw" : "warn",
  };
  const hcoResolutionContract = {
    unit_id: `${contractUnitPrefix}.resolution`,
    execution_mode: "dynamic_event",
    advance_trigger:
      pressureUnitContractsDraft?.resolution?.advance_trigger ??
      "result committed",
    visual_settle_trigger:
      pressureUnitContractsDraft?.resolution?.visual_settle_trigger ??
      "resolution visuals settled",
    failure_policy:
      (isPressureSkeletonTurn
        ? activePressureResolutionStrictMode
        : activeStepStrictMode) === "throw"
        ? "throw"
        : "warn",
  };
  const hcoOutContract = {
    unit_id: `${contractUnitPrefix}.out.to_*`,
    execution_mode: "dynamic_event",
    advance_trigger:
      pressureUnitContractsDraft?.transitionOut?.advance_trigger ??
      "route committed",
    visual_settle_trigger:
      contractUnitPrefix === "hco"
        ? "end-of-turn visuals settled"
        : pressureUnitContractsDraft?.transitionOut?.visual_settle_trigger ??
          `${contractLabel} boundary settle complete`,
    failure_policy:
      (isPressureSkeletonTurn
        ? activePressureOutStrictMode
        : activeStepStrictMode) === "throw"
        ? "throw"
        : "warn",
  };
  const resolutionResultType = String(turnData?.result_type || "").toUpperCase();
  const skeletonContractResultTypes = new Set([
    "MAKE",
    "MISS",
    "BLOCK",
    "FOUL",
    "STEAL",
  ]);
  const isStepContractTurn =
    isContractSkeletonTurn && skeletonContractResultTypes.has(resolutionResultType);
  const turnStartMs = Date.now();
  const getTurnContractElapsedMs = () => {
    const raw = Number(turnData?.real_time_elapsed_ms ?? turnData?.realTimeElapsedMs);
    if (Number.isFinite(raw) && raw >= 0) return raw;
    return null;
  };
  const getHcoTurnElapsedGuardSlackMs = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_HCO_TURN_ELAPSED_GUARD_SLACK_MS);
    if (Number.isFinite(raw) && raw >= 0) return raw;
    return 1500;
  };
  const getGuardedTurnElapsedMs = () => {
    const wallElapsedMs = Math.max(0, Date.now() - turnStartMs);
    const contractElapsedMs = getTurnContractElapsedMs();
    if (contractElapsedMs == null) {
      return {
        elapsedMs: wallElapsedMs,
        wallElapsedMs,
        contractElapsedMs: null,
        elapsedCapMs: null,
        elapsedClamped: false,
      };
    }
    const elapsedCapMs = contractElapsedMs + getHcoTurnElapsedGuardSlackMs();
    const elapsedMs = Math.min(wallElapsedMs, elapsedCapMs);
    return {
      elapsedMs,
      wallElapsedMs,
      contractElapsedMs,
      elapsedCapMs,
      elapsedClamped: wallElapsedMs > elapsedCapMs,
    };
  };
  const resolveHcoElapsedAuthorityMode = () => {
    const scope = getDrebTelemetryScope();
    const raw = String(scope?.UESS_HCO_ELAPSED_AUTHORITY ?? "observe")
      .trim()
      .toLowerCase();
    if (raw === "off") return "off";
    if (raw === "observe") return "observe";
    // Forward-compatible: unknown values currently degrade to observe.
    return "observe";
  };
  const hcoElapsedAuthorityMode = resolveHcoElapsedAuthorityMode();
  const shouldTrackHcoElapsed =
    isHCOSkeletonTurn && hcoElapsedAuthorityMode !== "off";
  const hcoElapsedUnitsMs = {
    lead_in: 0,
    step_movement: 0,
    step_pass: 0,
    resolution: 0,
    transition_out: 0,
  };
  let hcoElapsedLastCheckpointMs = shouldTrackHcoElapsed
    ? getGuardedTurnElapsedMs().elapsedMs
    : 0;
  const captureHcoUnitElapsed = (unitKey) => {
    if (
      !shouldTrackHcoElapsed ||
      !Object.prototype.hasOwnProperty.call(hcoElapsedUnitsMs, unitKey)
    ) {
      return 0;
    }
    const checkpoint = getGuardedTurnElapsedMs();
    const deltaMs = Math.max(
      0,
      Number(checkpoint.elapsedMs) - Number(hcoElapsedLastCheckpointMs)
    );
    hcoElapsedLastCheckpointMs = Number(checkpoint.elapsedMs);
    hcoElapsedUnitsMs[unitKey] += deltaMs;
    return deltaMs;
  };
  const emitHcoElapsedObserveTelemetry = (meta = {}) => {
    if (!shouldTrackHcoElapsed || hcoElapsedAuthorityMode !== "observe") return;
    const totalMs = Object.values(hcoElapsedUnitsMs).reduce(
      (sum, ms) => sum + (Number(ms) || 0),
      0
    );
    const toGameSeconds = (ms) => Number((ms / clockSecondMs).toFixed(3));
    const unitElapsedGameSeconds = {
      lead_in: toGameSeconds(hcoElapsedUnitsMs.lead_in),
      step_movement: toGameSeconds(hcoElapsedUnitsMs.step_movement),
      step_pass: toGameSeconds(hcoElapsedUnitsMs.step_pass),
      resolution: toGameSeconds(hcoElapsedUnitsMs.resolution),
      transition_out: toGameSeconds(hcoElapsedUnitsMs.transition_out),
    };
    const totalGameSeconds = toGameSeconds(totalMs);
    turnData.hco_uess_elapsed_game_seconds = totalGameSeconds;
    scene?.events?.emit?.("animTelemetry", {
      event: "hco_uess_elapsed_observe",
      branchKind: "hco_turn_elapsed",
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: scene?.currentTurn ?? null,
      resultType: turnData?.result_type ?? null,
      gameClock: scene?.simData?.clock ?? null,
      quarter: turnData?.quarter ?? scene?.quarter ?? null,
      timestampMs: Date.now(),
      authorityMode: hcoElapsedAuthorityMode,
      hco_uess_elapsed_game_seconds: totalGameSeconds,
      hco_uess_elapsed_ms: Math.round(totalMs),
      hco_uess_elapsed_unit_breakdown_game_seconds: unitElapsedGameSeconds,
      hco_uess_elapsed_unit_breakdown_ms: {
        lead_in: Math.round(hcoElapsedUnitsMs.lead_in),
        step_movement: Math.round(hcoElapsedUnitsMs.step_movement),
        step_pass: Math.round(hcoElapsedUnitsMs.step_pass),
        resolution: Math.round(hcoElapsedUnitsMs.resolution),
        transition_out: Math.round(hcoElapsedUnitsMs.transition_out),
      },
      ...meta,
    });
  };
  const hasPlayerSpriteForId = (rawId) => {
    if (rawId == null) return false;
    if (playerSprites?.[rawId]) return true;
    const want = String(rawId);
    for (const [id, sprite] of Object.entries(playerSprites || {})) {
      if (String(id) === want) return true;
      if (String(sprite?.playerId ?? "") === want) return true;
    }
    return false;
  };
  let pressureLeadInValidated = false;
  const validatePressureLeadInContract = (context = {}) => {
    if (
      !isPressureSkeletonTurn ||
      !isPressureReworkPhase3LeadInEnabled ||
      pressureLeadInContractMode === "off" ||
      pressureLeadInValidated
    ) {
      return;
    }
    const currentOwnerId = getCurrentOwner(scene);
    const pendingOwnerId = getPendingOwner(scene);
    const hasCurrentOwner = currentOwnerId != null && String(currentOwnerId).length > 0;
    const hasPendingOwner = pendingOwnerId != null && String(pendingOwnerId).length > 0;
    const ownerMissing = !hasCurrentOwner && !hasPendingOwner;
    const ownerInvalid =
      (hasCurrentOwner && !hasPlayerSpriteForId(currentOwnerId)) ||
      (hasPendingOwner && !hasPlayerSpriteForId(pendingOwnerId));
    const passInFlightAtLeadIn = scene?.passInFlight === true;
    const elapsedMs = Math.max(0, Date.now() - turnStartMs);
    const elapsedGameSeconds = elapsedMs / clockSecondMs;
    const leadInSource = fromInbound
      ? inboundLeadInSource || "UNKNOWN_INBOUND"
      : "NON_INBOUND_ENTRY";
    const routeCommitted =
      String(turnData?.current_turn || "").toUpperCase() === "FCP" ||
      String(turnData?.current_turn || "").toUpperCase() === "HCT" ||
      Boolean(turnData?.next_play_type || turnData?.next_turn);
    const leadInContext = {
      contractFamily: contractUnitPrefix,
      leadInSource,
      routeCommitted,
      currentOwnerId: currentOwnerId ?? null,
      pendingOwnerId: pendingOwnerId ?? null,
      ownerMissing,
      ownerInvalid,
      passInFlightAtLeadIn,
      elapsedMs,
      elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
      ...context,
    };
    emitPressureReworkTelemetry("pressure_lead_in_contract_eval", leadInContext);
    enforceUnitCompletionContract({
      contract: {
        unit_id: `${contractUnitPrefix}.lead_in.entry`,
        execution_mode: "dynamic_event",
        advance_trigger: `${contractLabel} route committed + entry owner resolved`,
        visual_settle_trigger:
          contractUnitPrefix === "hct"
            ? "trap entry handoff settled"
            : "press entry handoff settled",
        failure_policy: "warn",
      },
      observed: {
        authorizingEventReceived: routeCommitted,
        visualSettled: !ownerMissing && !ownerInvalid && !passInFlightAtLeadIn,
      },
      context: leadInContext,
      emitTelemetry: (event, payload = {}) => {
        emitPressureReworkTelemetry(event, {
          ...leadInContext,
          ...payload,
        });
      },
      logger: console,
    });
    pressureLeadInValidated = true;
  };
  let hcoLeadInFromInboundValidated = false;
  const validateHcoLeadInFromInbound = (context = {}) => {
    if (!isHcoLeadInFromInbound || hcoLeadInInboundStrictMode === "off" || hcoLeadInFromInboundValidated) {
      return;
    }
    const emitHcoLeadInTelemetry = (event, payload = {}) => {
      scene?.events?.emit?.("animTelemetry", {
        event,
        branchKind: "hco_lead_in_from_sip_or_bip",
        turnId: turnData?.turn_count ?? turnData?.id ?? null,
        turnIndex: scene?.currentTurn ?? null,
        resultType: turnData?.result_type ?? null,
        gameClock: scene?.simData?.clock ?? null,
        quarter: turnData?.quarter ?? scene?.quarter ?? null,
        timestampMs: Date.now(),
        ...payload,
      });
    };
    const currentOwnerId = getCurrentOwner(scene);
    const pendingOwnerId = getPendingOwner(scene);
    const hasCurrentOwner = currentOwnerId != null && String(currentOwnerId).length > 0;
    const hasPendingOwner = pendingOwnerId != null && String(pendingOwnerId).length > 0;
    const ownerMissing = !hasCurrentOwner && !hasPendingOwner;
    const ownerInvalid =
      (hasCurrentOwner && !hasPlayerSpriteForId(currentOwnerId)) ||
      (hasPendingOwner && !hasPlayerSpriteForId(pendingOwnerId));
    const passInFlightAtLeadIn = scene?.passInFlight === true;
    const elapsedTiming = getGuardedTurnElapsedMs();
    const elapsedMs = elapsedTiming.elapsedMs;
    const elapsedGameSeconds = elapsedMs / clockSecondMs;
    const maxWaitGameSeconds = getHcoLeadInInboundBudgetGameSeconds();
    const overrun = elapsedGameSeconds > maxWaitGameSeconds;
    const leadInContext = {
      inboundSource: inboundLeadInSource || null,
      currentOwnerId: currentOwnerId ?? null,
      pendingOwnerId: pendingOwnerId ?? null,
      ownerMissing,
      ownerInvalid,
      passInFlightAtLeadIn,
      elapsedMs,
      wallElapsedMs: elapsedTiming.wallElapsedMs,
      contractElapsedMs: elapsedTiming.contractElapsedMs,
      elapsedCapMs: elapsedTiming.elapsedCapMs,
      elapsedClamped: elapsedTiming.elapsedClamped,
      elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
      maxWaitGameSeconds,
      ...context,
    };
    if (ownerMissing) emitHcoLeadInTelemetry("hco_lead_in_inbound_owner_missing", leadInContext);
    if (ownerInvalid) emitHcoLeadInTelemetry("hco_lead_in_inbound_owner_invalid", leadInContext);
    if (passInFlightAtLeadIn) {
      emitHcoLeadInTelemetry("hco_lead_in_inbound_pass_in_flight", leadInContext);
    }
    if (overrun) emitHcoLeadInTelemetry("hco_lead_in_inbound_clock_overrun", leadInContext);
    enforceUnitCompletionContract({
      contract: hcoLeadInFromInboundContract,
      observed: {
        authorizingEventReceived: fromInbound,
        visualSettled: !ownerMissing && !ownerInvalid && !passInFlightAtLeadIn,
      },
      context: leadInContext,
      emitTelemetry: emitHcoLeadInTelemetry,
      logger: console,
    });
    if (hcoLeadInInboundStrictMode === "throw") {
      if (ownerMissing) {
        throw new Error(
          `[HCO lead-in inbound contract] missing owner after inbound handoff (source=${inboundLeadInSource || "unknown"})`
        );
      }
      if (ownerInvalid) {
        throw new Error(
          `[HCO lead-in inbound contract] invalid owner reference after inbound handoff (source=${inboundLeadInSource || "unknown"})`
        );
      }
      if (passInFlightAtLeadIn) {
        throw new Error(
          `[HCO lead-in inbound contract] pass still in flight at HCO lead-in boundary (source=${inboundLeadInSource || "unknown"})`
        );
      }
      if (overrun) {
        throw new Error(
          `[HCO lead-in inbound contract] lead-in budget overrun (source=${inboundLeadInSource || "unknown"}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${maxWaitGameSeconds})`
        );
      }
    }
    hcoLeadInFromInboundValidated = true;
  };
  const getHcoResolutionExtraBudgetSeconds = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_HCO_RESOLUTION_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw >= 0) return raw;
    return 2;
  };
  const getHcoResolutionClockSlackSeconds = (declaredBudgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_HCO_RESOLUTION_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_HCO_RESOLUTION_CLOCK_JITTER_RATIO);
    const absSlack = Number.isFinite(rawAbs) && rawAbs >= 0 ? rawAbs : 1.5;
    const ratioSlack =
      Number.isFinite(rawRatio) && rawRatio >= 0
        ? declaredBudgetSeconds * rawRatio
        : declaredBudgetSeconds * 0.5;
    return Math.max(absSlack, ratioSlack);
  };
  const getHcoOutExtraBudgetSeconds = () => {
    const scope = getDrebTelemetryScope();
    const raw = Number(scope?.UESS_HCO_OUT_MAX_GAME_SECONDS);
    if (Number.isFinite(raw) && raw >= 0) return raw;
    return 2;
  };
  const getHcoOutClockSlackSeconds = (declaredBudgetSeconds) => {
    const scope = getDrebTelemetryScope();
    const rawAbs = Number(scope?.UESS_HCO_OUT_CLOCK_JITTER_ABS_SECONDS);
    const rawRatio = Number(scope?.UESS_HCO_OUT_CLOCK_JITTER_RATIO);
    const absSlack = Number.isFinite(rawAbs) && rawAbs >= 0 ? rawAbs : 1.5;
    const ratioSlack =
      Number.isFinite(rawRatio) && rawRatio >= 0
        ? declaredBudgetSeconds * rawRatio
        : declaredBudgetSeconds * 0.5;
    return Math.max(absSlack, ratioSlack);
  };
  const isResolutionContractTurn = isStepContractTurn;
  const hasCanonicalTurnBatchContext =
    Array.isArray(simData?.turns) && simData.turns.length > 0;
  const isSyntheticPutbackExecution =
    String(turnData?.shot_type || "").toLowerCase() === "putback";
  const shouldValidateHcoOut =
    isResolutionContractTurn &&
    hasCanonicalTurnBatchContext &&
    !isSyntheticPutbackExecution;
  let hcoResolutionValidated = false;
  const validateHcoResolution = (context = {}) => {
    const resolutionStrictMode = isPressureSkeletonTurn
      ? activePressureResolutionStrictMode
      : activeStepStrictMode;
    if (!isResolutionContractTurn || resolutionStrictMode === "off" || hcoResolutionValidated) return;
    const currentOwnerId = getCurrentOwner(scene);
    const pendingOwnerId = getPendingOwner(scene);
    const hasCurrentOwner = currentOwnerId != null && String(currentOwnerId).length > 0;
    const hasPendingOwner = pendingOwnerId != null && String(pendingOwnerId).length > 0;
    const rebounderId =
      turnData?.rebounder_player_id ??
      turnData?.rebounderId ??
      turnData?.rebounder_id ??
      null;
    const shouldHaveOwnerAtResolution =
      ["MISS", "BLOCK", "STEAL", "OREB", "PUTBACK_MISS", "PUTBACK_MAKE"].includes(
        resolutionResultType
      ) || rebounderId != null;
    const ownerMissing = shouldHaveOwnerAtResolution && !hasCurrentOwner && !hasPendingOwner;
    const ownerInvalid =
      (hasCurrentOwner && !hasPlayerSpriteForId(currentOwnerId)) ||
      (hasPendingOwner && !hasPlayerSpriteForId(pendingOwnerId));
    const passInFlightAtResolution = scene?.passInFlight === true;
    const elapsedTiming = getGuardedTurnElapsedMs();
    const elapsedMs = elapsedTiming.elapsedMs;
    const elapsedGameSeconds = elapsedMs / clockSecondMs;
    const declaredTurnBudgetSeconds = Array.isArray(stepClockSeconds)
      ? stepClockSeconds.reduce((sum, sec) => sum + (Number(sec) || 0), 0)
      : null;
    const extraBudgetSeconds = getHcoResolutionExtraBudgetSeconds();
    const hardFailThresholdSeconds =
      declaredTurnBudgetSeconds == null
        ? null
        : declaredTurnBudgetSeconds +
          extraBudgetSeconds +
          getHcoResolutionClockSlackSeconds(declaredTurnBudgetSeconds);
    const resolutionContext = {
      resultType: turnData?.result_type ?? null,
      turnId: turnData?.turn_count ?? turnData?.id ?? null,
      turnIndex: scene?.currentTurn ?? null,
      currentOwnerId: currentOwnerId ?? null,
      pendingOwnerId: pendingOwnerId ?? null,
      shouldHaveOwnerAtResolution,
      ownerMissing,
      ownerInvalid,
      passInFlightAtResolution,
      elapsedMs,
      wallElapsedMs: elapsedTiming.wallElapsedMs,
      contractElapsedMs: elapsedTiming.contractElapsedMs,
      elapsedCapMs: elapsedTiming.elapsedCapMs,
      elapsedClamped: elapsedTiming.elapsedClamped,
      elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
      declaredTurnBudgetSeconds,
      resolutionExtraBudgetSeconds: extraBudgetSeconds,
      hardFailThresholdSeconds:
        hardFailThresholdSeconds == null
          ? null
          : Number(hardFailThresholdSeconds.toFixed(2)),
      ...context,
    };
    if (ownerMissing) {
      emitHcoStepTelemetry("hco_resolution_owner_missing", resolutionContext);
      const message = `[${contractLabel} resolution contract] missing owner at resolution (result=${resolutionResultType}, turn=${turnData?.turn_count ?? "?"})`;
      if (!isPressureSkeletonTurn || resolutionStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_resolution_contract_warn", {
        ...resolutionContext,
        violation: "owner_missing",
        message,
        resolutionStrictMode,
      });
    }
    if (ownerInvalid) {
      emitHcoStepTelemetry("hco_resolution_owner_invalid", resolutionContext);
      const message = `[${contractLabel} resolution contract] invalid owner reference at resolution (result=${resolutionResultType}, owner=${currentOwnerId ?? "null"}, pending=${pendingOwnerId ?? "null"})`;
      if (!isPressureSkeletonTurn || resolutionStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_resolution_contract_warn", {
        ...resolutionContext,
        violation: "owner_invalid",
        message,
        resolutionStrictMode,
      });
    }
    if (passInFlightAtResolution) {
      emitHcoStepTelemetry("hco_resolution_pass_in_flight", resolutionContext);
      const message = `[${contractLabel} resolution contract] pass still in flight at resolution (result=${resolutionResultType}, turn=${turnData?.turn_count ?? "?"})`;
      if (!isPressureSkeletonTurn || resolutionStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_resolution_contract_warn", {
        ...resolutionContext,
        violation: "pass_in_flight",
        message,
        resolutionStrictMode,
      });
    }
    if (hardFailThresholdSeconds != null && elapsedGameSeconds > hardFailThresholdSeconds) {
      emitHcoStepTelemetry("hco_resolution_clock_overrun", resolutionContext);
      const message = `[${contractLabel} resolution contract] clock overrun (result=${resolutionResultType}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, hardFailThresholdSeconds=${hardFailThresholdSeconds.toFixed(2)})`;
      if (!isPressureSkeletonTurn || resolutionStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_resolution_contract_warn", {
        ...resolutionContext,
        violation: "clock_overrun",
        message,
        resolutionStrictMode,
      });
    }
    if (declaredTurnBudgetSeconds != null && elapsedGameSeconds > declaredTurnBudgetSeconds) {
      emitHcoStepTelemetry("hco_resolution_clock_soft_overrun", resolutionContext);
    }
    enforceUnitCompletionContract({
      contract: hcoResolutionContract,
      observed: {
        authorizingEventReceived: true,
        visualSettled: true,
      },
      context: resolutionContext,
      emitTelemetry: emitHcoStepTelemetry,
      logger: console,
    });
    captureHcoUnitElapsed("resolution");
    hcoResolutionValidated = true;
  };
  let hcoOutValidated = false;
  const validateHcoTransitionOut = (context = {}) => {
    const outStrictMode = isPressureSkeletonTurn
      ? activePressureOutStrictMode
      : activeStepStrictMode;
    if (!shouldValidateHcoOut || outStrictMode === "off" || hcoOutValidated) return;
    const route = String(turnData?.next_play_type || turnData?.next_turn || "").toUpperCase();
    const quarterEndsAfter = turnData?.quarter_ends_after === true;
    const routeMissing = !quarterEndsAfter && !route;
    const currentOwnerId = getCurrentOwner(scene);
    const pendingOwnerId = getPendingOwner(scene);
    const hasCurrentOwner = currentOwnerId != null && String(currentOwnerId).length > 0;
    const hasPendingOwner = pendingOwnerId != null && String(pendingOwnerId).length > 0;
    const liveBallRoutes = new Set(["HCO", "HCT", "FCP", "FAST_BREAK", "OREB"]);
    const requiresOwnerAtHandoff = liveBallRoutes.has(route);
    const ownerMissing = requiresOwnerAtHandoff && !hasCurrentOwner && !hasPendingOwner;
    const ownerInvalid =
      (hasCurrentOwner && !hasPlayerSpriteForId(currentOwnerId)) ||
      (hasPendingOwner && !hasPlayerSpriteForId(pendingOwnerId));
    const elapsedTiming = getGuardedTurnElapsedMs();
    const elapsedMs = elapsedTiming.elapsedMs;
    const elapsedGameSeconds = elapsedMs / clockSecondMs;
    const declaredTurnBudgetSeconds = Array.isArray(stepClockSeconds)
      ? stepClockSeconds.reduce((sum, sec) => sum + (Number(sec) || 0), 0)
      : null;
    const extraBudgetSeconds = getHcoOutExtraBudgetSeconds();
    const hardFailThresholdSeconds =
      declaredTurnBudgetSeconds == null
        ? null
        : declaredTurnBudgetSeconds +
          extraBudgetSeconds +
          getHcoOutClockSlackSeconds(declaredTurnBudgetSeconds);
    const outContext = {
      route: route || null,
      quarterEndsAfter,
      routeMissing,
      currentOwnerId: currentOwnerId ?? null,
      pendingOwnerId: pendingOwnerId ?? null,
      requiresOwnerAtHandoff,
      ownerMissing,
      ownerInvalid,
      elapsedMs,
      wallElapsedMs: elapsedTiming.wallElapsedMs,
      contractElapsedMs: elapsedTiming.contractElapsedMs,
      elapsedCapMs: elapsedTiming.elapsedCapMs,
      elapsedClamped: elapsedTiming.elapsedClamped,
      elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
      declaredTurnBudgetSeconds,
      outExtraBudgetSeconds: extraBudgetSeconds,
      hardFailThresholdSeconds:
        hardFailThresholdSeconds == null
          ? null
          : Number(hardFailThresholdSeconds.toFixed(2)),
      ...context,
    };
    if (routeMissing) {
      emitHcoStepTelemetry("hco_out_route_missing", outContext);
      const message = `[${contractLabel} out contract] missing committed route (result=${resolutionResultType}, turn=${turnData?.turn_count ?? "?"})`;
      if (!isPressureSkeletonTurn || outStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_out_contract_warn", {
        ...outContext,
        violation: "route_missing",
        message,
        outStrictMode,
      });
    }
    if (ownerMissing) {
      emitHcoStepTelemetry("hco_out_owner_missing", outContext);
      const message = `[${contractLabel} out contract] missing owner for live-ball handoff (route=${route}, turn=${turnData?.turn_count ?? "?"})`;
      if (!isPressureSkeletonTurn || outStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_out_contract_warn", {
        ...outContext,
        violation: "owner_missing",
        message,
        outStrictMode,
      });
    }
    if (ownerInvalid) {
      emitHcoStepTelemetry("hco_out_owner_invalid", outContext);
      const message = `[${contractLabel} out contract] invalid owner reference at handoff (route=${route}, owner=${currentOwnerId ?? "null"}, pending=${pendingOwnerId ?? "null"})`;
      if (!isPressureSkeletonTurn || outStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_out_contract_warn", {
        ...outContext,
        violation: "owner_invalid",
        message,
        outStrictMode,
      });
    }
    if (hardFailThresholdSeconds != null && elapsedGameSeconds > hardFailThresholdSeconds) {
      emitHcoStepTelemetry("hco_out_clock_overrun", outContext);
      const message = `[${contractLabel} out contract] clock overrun (route=${route || "quarter_end"}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, hardFailThresholdSeconds=${hardFailThresholdSeconds.toFixed(2)})`;
      if (!isPressureSkeletonTurn || outStrictMode === "throw") {
        throw new Error(message);
      }
      emitPressureReworkTelemetry("pressure_out_contract_warn", {
        ...outContext,
        violation: "clock_overrun",
        message,
        outStrictMode,
      });
    }
    if (declaredTurnBudgetSeconds != null && elapsedGameSeconds > declaredTurnBudgetSeconds) {
      emitHcoStepTelemetry("hco_out_clock_soft_overrun", outContext);
    }
    enforceUnitCompletionContract({
      contract: hcoOutContract,
      observed: {
        authorizingEventReceived: !routeMissing || quarterEndsAfter,
        visualSettled: true,
      },
      context: outContext,
      emitTelemetry: emitHcoStepTelemetry,
      logger: console,
    });
    captureHcoUnitElapsed("transition_out");
    hcoOutValidated = true;
  };

  // ✅ CRITICAL FIX: Kill all ball tweens before starting step loop
  // Lingering ball tweens from previous shots/passes can block the tween manager
  // This is especially important for FCP/HCT turns that come after shots
  if (ballSprite && scene.tweens) {
    const ballActiveTweens = scene.tweens.getTweensOf ? scene.tweens.getTweensOf(ballSprite) : [];
    if (ballActiveTweens.length > 0) {
      scene.tweens.killTweensOf(ballSprite);
      // Also kill ball shadow tweens if they exist
      if (scene.ballShadowSprite) {
        scene.tweens.killTweensOf(scene.ballShadowSprite);
      }
    }
  }

  // ✅ REMOVED: Special FCP/HCT tween cleanup - FCP/HCT now uses exact same path as HCO
  // ShotAnimationSystem handles all skeleton animations identically

  if (isPressureSkeletonTurn) {
    validatePressureLeadInContract({ phase: "turn_entry" });
  }

  // ✅ SS&S FIX: Resolve offenseTeamId once at turn start and classify all players
  // This ensures consistent player classification throughout the turn
  const { resolveOffenseTeamId } = await import('../utils/offenseTeamIdResolver.js');
  const offenseTeamId = resolveOffenseTeamId({
    scene,
    turnData,
    playerSprites,
    passInfo: null // No passInfo at turn start, will be detected per step
  });
  
  // ✅ SS&S: Classify all players once at turn start
  const playerClassifications = {}; // Map: playerId -> 'offense' | 'defense'
  let offensiveCount = 0;
  let defensiveCount = 0;
  
  // 🔍 DEBUG: Log team_id format mismatch detection
  // Classify players as offense or defense
  
  for (const anim of turnData.animations) {
    const sprite = playerSprites[anim.playerId];
    if (!sprite) {
      continue;
    }
    
    const isOffensivePlayer = offenseTeamId ? String(sprite.team_id) === String(offenseTeamId) : false;
    playerClassifications[anim.playerId] = isOffensivePlayer ? 'offense' : 'defense';
    
    if (isOffensivePlayer) {
      offensiveCount++;
    } else {
      defensiveCount++;
    }
  }
  
  // ✅ VALIDATION: Ensure we have exactly 5 offensive and 5 defensive players
  // only on full-roster skeleton turns (partial/synthetic turns like helper putbacks
  // do not carry all 10 players and should not emit false warnings).
  const expectedFullRosterClassification =
    Array.isArray(turnData?.animations) && turnData.animations.length >= 10;
  if (expectedFullRosterClassification && (offensiveCount !== 5 || defensiveCount !== 5)) {
    console.warn('⚠️ [PLAYER CLASSIFICATION] Expected 5 offensive and 5 defensive players, but got:', {
      resultType: turnData?.result_type ?? null,
      animationCount: turnData?.animations?.length ?? 0,
      offensiveCount,
      defensiveCount
    });
  }

  // ============================================================================
  // STEAL HCO SETUP: Animate stealer moving back before HCO skeleton starts
  // ============================================================================
  if (turnData.roles?.is_steal_hco_setup) {
    await animateStealHCOSetup(scene, turnData, playerSprites, ballSprite);
  }

  // ✅ CRITICAL FIX: Run setup tween to move players to step 0 positions before skeleton animation
  // This ensures players are correctly positioned before step 1 (first pass) starts
  // Without this, truncated skeletons (o foul, d foul, dead ball turnover, steal) start
  // the step loop before players reach step 0 positions, causing slow/fast first pass animations
  // Shot attempts work correctly because ShotAnimationSystem calls runSetupTween() before animatePlayerMovement()
  // ✅ SS&S FIX: Skip setup tween if coming from BIP for FCP/HCT - players are already at step 0 positions
  // BIP (BASELINE_INBOUND) already positioned players at skeleton step 0 positions, so this is redundant
  // and can cause timing conflicts if the inbound pass animation is still completing
  if (!fromInbound || !isFCPHCT) {
    await runSetupTween({
      scene,
      ballSprite,
      animations: turnData.animations,
      playerSprites,
      currentBallOwnerRef,
      turnData,
      stepDurationMs: getContractStepDurationMs(0, null),
    });
  } else {
    console.log('⏭️ [FCP/HCT] Skipping runSetupTween() - players already positioned at step 0 from BIP');
  }
  if (requiresStep0EntryPass) {
    await runStep0EntryPassIfNeeded({
      scene,
      ballSprite,
      playerSprites,
      currentBallOwnerRef,
      liveOwnerId: step0EntryPassFromId,
      step0OwnerId,
    });
  }
  if (isPressureSkeletonTurn) {
    validatePressureLeadInContract({ phase: "post_setup_tween" });
  }
  validateHcoLeadInFromInbound({ phase: "post_setup_tween" });
  captureHcoUnitElapsed("lead_in");

  // Step loop animates transitions using (prev -> curr), so it must start at 1.
  // Starting at 0 makes prev undefined and can short-circuit skeleton playback.
  const stepLoopStartIndex = 1;
  for (let stepIndex = stepLoopStartIndex; stepIndex < maxSteps; stepIndex++) {
    
    // ✅ REMOVED: Special FCP/HCT FastBreak check - FCP/HCT now routes through AnimationRouter (same as HCO)
    const willEarlyExit = scene.skipToEnd || scene.stateMachine?.is(States.FastBreak);
    
    // ✅ CRITICAL FIX: Kill ball tweens at the start of EACH step iteration
    // Passes within the step loop can leave lingering ball tweens that block subsequent steps
    if (ballSprite && scene.tweens && !willEarlyExit) {
      const ballActiveTweens = scene.tweens.getTweensOf ? scene.tweens.getTweensOf(ballSprite) : [];
      if (ballActiveTweens.length > 0) {
        scene.tweens.killTweensOf(ballSprite);
        if (scene.ballShadowSprite) {
          scene.tweens.killTweensOf(scene.ballShadowSprite);
        }
      }
    }
    
    if (willEarlyExit) {
      break;
    }

    // ✅ FIX: Skip updateBallOwnership if a pass is happening at this step OR
    // if a pass just completed (passInFlight is still true from previous step)
    // We'll handle the pass explicitly after movements complete (like shots)
    // ✅ REFACTOR: Use unified passDetection.js for consistency
    // ✅ FIX: Detect pass early to determine animation sequence (reused below)
    const { detectPassAtStep } = await import('./passDetection.js');
    
    const passInfo = detectPassAtStep(turnData.animations, stepIndex);
    const passHappeningAtThisStep = !!passInfo;
    const stepStartMs = Date.now();
    
    // 🔍 DEBUG: Log step processing for step 16 (3-2 Motion bug)
    if (stepIndex === 16) {
      const step = turnData.animations?.[0]?.movement?.[stepIndex];
      console.log('📋 [STEP PROCESSING] Step 16', {
        timestamp: step?.timestamp,
        passHappening: passHappeningAtThisStep,
        passInfo: passInfo ? {
          passerId: passInfo.passerId?.substring(0, 8),
          receiverId: passInfo.receiverId?.substring(0, 8)
        } : null,
        allPlayerPositions: Object.keys(playerSprites).map(playerId => {
          const sprite = playerSprites[playerId];
          const anim = turnData.animations?.find(a => a.playerId === playerId);
          const stepData = anim?.movement?.[stepIndex];
          return {
            playerId: playerId?.substring(0, 8),
            x: sprite.x,
            y: sprite.y,
            action: stepData?.action,
            location: stepData?.location
          };
        })
      });
    }
    
    // ✅ OLD CODE (commented out - replaced with unified passDetection.js):
    // const passHappeningAtThisStep = turnData.animations.some(
    //   anim => anim.movement?.[stepIndex]?.action === "pass"
    // );
    
    // ✅ CRITICAL FIX: Also skip if passInFlight is true (pass just completed)
    // This prevents updateBallOwnership from teleporting the ball immediately after runPass() completes
    // The passInFlight flag will be cleared by runPass()'s finally block, but we keep it true
    // for one more step to ensure the ball is properly attached before updateBallOwnership runs
    if (!passHappeningAtThisStep && !scene.passInFlight) {
      updateBallOwnership({
        scene,
        ballSprite,
        animations: turnData.animations,
        playerSprites,
        stepIndex,
        offenseTeamId: scene.offenseTeamId ?? turnData.possession_team_id,
        currentBallOwnerRef
      });
    } else if (scene.passInFlight && !passHappeningAtThisStep) {
      // Pass just completed, clear the flag now that we've skipped updateBallOwnership
      // This allows updateBallOwnership to run normally for subsequent steps
      scene.passInFlight = false;
      console.log('🏀 [PASS ANIMATION] Cleared passInFlight after skipping updateBallOwnership');
    }

    // Update active player displays in scoreboard
    if (!scene.skipToEnd) {
      const { getBallHandlerIdFromTurn, getDefenderIdFromTurn, updateActivePlayers } = await import('../utils/activePlayerDisplay.js');
      const ballHandlerId = getBallHandlerIdFromTurn(turnData, stepIndex);
      const defenderId = getDefenderIdFromTurn(turnData);
      const homeTeamId = scene.simData?.home_team_id || null;
      if (ballHandlerId && homeTeamId) {
        updateActivePlayers(ballHandlerId, defenderId, homeTeamId, playerSprites);
      }
    }

    // ✅ SS&S: Use pre-classified player roles (determined at turn start)
    // No need to re-resolve offenseTeamId or re-classify players per step
    const offensivePromises = [];
    const requiredOffensiveMoverIds = [];
    const requiredOffensiveMoverTargetPx = new Map();
    const defensiveStarters = []; // defer starting defensive tweens when a pass exists
    let passerPromise = null;
    let shotInfo = null;

    // Separate offensive and defensive players using pre-classified roles
    for (const anim of turnData.animations) {
      if (scene.skipToEnd) break;
      const sprite = playerSprites[anim.playerId];
      const movement = anim.movement;

      if (!sprite || stepIndex >= movement.length) continue;

      const prev = movement[stepIndex - 1];
      const curr = movement[stepIndex];
      const step = prev;
      const nextStep = curr;
      
      // Calculate target position in pixels
      const { x: targetX, y: targetY } = gridToPixels(
        nextStep.coords.x,
        nextStep.coords.y,
        scene.game.config.width,
        scene.game.config.height
      );
      
      // Use distance-based duration calculation (from current sprite position to target)
      // This ensures smooth transitions between turns and consistent speeds
      // The sprite's current position (sprite.x, sprite.y) is where it actually is,
      // which may be from the end of the previous turn or from a previous step
      const distanceDuration = getPlayerDuration(sprite, targetX, targetY);
      // For HCT/FCP, respect waypoint timestamp deltas as a duration floor only
      // for zero-distance "hold" frames (e.g. dynamic-HCT BH 3s hold at step-1
      // start). Non-zero-distance steps must keep distance-based duration so
      // movers run at the frontend's normal pace, not stretched to the hold's
      // game-second window.
      const tsDelta = Number(curr?.timestamp) - Number(prev?.timestamp);
      const gridDx = Number(curr?.coords?.x) - Number(prev?.coords?.x);
      const gridDy = Number(curr?.coords?.y) - Number(prev?.coords?.y);
      const isHoldFrame = Number.isFinite(gridDx) && Number.isFinite(gridDy)
        && Math.hypot(gridDx, gridDy) < 1;
      const duration = (isPressureSkeletonTurn && isHoldFrame && Number.isFinite(tsDelta) && tsDelta > 0)
        ? Math.max(distanceDuration, tsDelta)
        : distanceDuration;
      

      DEBUG && animationDebugLog('[turn]', turnData?.id, step.timestamp, nextStep.timestamp, duration, {
        currentPos: { x: sprite.x, y: sprite.y },
        targetPos: { x: targetX, y: targetY },
        distance: Phaser.Math.Distance.Between(sprite.x, sprite.y, targetX, targetY),
        method: 'distance-based'
      });
      if (duration <= 0) {
        animationDebugWarn('[turn] Non-positive duration', { turnId: turnData?.id, step, nextStep });
        if (typeof window !== 'undefined') {
          window.__badStepPayloads = window.__badStepPayloads || [];
          window.__badStepPayloads.push({ turnId: turnData?.id, step, nextStep });
        }
      }

      if (nextStep.action === "shoot") {
        // Option A: Don't animate shot attempt for Charge or Blocking Foul — keep ball on ball handler
        const isChargeOrBlockingFoul = turnData.result_type === 'CHARGE' ||
          (turnData.result_type === 'FOUL' && turnData.text?.toLowerCase().includes('blocking foul'));
        if (!isChargeOrBlockingFoul) {
          shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
        }
      }

      const promise = animateStep({
        scene,
        sprite,
        step: prev,  // Previous step (for position calculation)
        nextStep: curr,  // Current step (for action checking)
        duration,
        ballSprite,
        currentBallOwnerRef,
        onAction,
        stepIndex  // Pass stepIndex to identify first step
      });

      // ✅ SS&S: Use pre-classified player role (determined at turn start)
      // This ensures consistent classification throughout the turn
      const playerRole = playerClassifications[anim.playerId] || 'defense'; // Default to defense if not found
      const isOffensivePlayer = playerRole === 'offense';
      
      if (isOffensivePlayer) {
        offensivePromises.push(promise);
        requiredOffensiveMoverIds.push(anim.playerId);
        requiredOffensiveMoverTargetPx.set(String(anim.playerId), {
          x: targetX,
          y: targetY,
          targetGridX: nextStep.coords?.x ?? null,
          targetGridY: nextStep.coords?.y ?? null,
        });
        // Track passer's promise separately so we can wait for it before starting pass
        if (passInfo && anim.playerId === passInfo.passerId) {
          passerPromise = promise;
        }
      } else {
        // Defer starting defensive tweens when a pass exists so we can sync them with the pass
        defensiveStarters.push(() => animateStep({
          scene,
          sprite,
          step: prev,
          nextStep: curr,
          duration,
          ballSprite,
          currentBallOwnerRef,
          onAction,
          stepIndex
        }));
      }
    }

    // Start defensive tweens immediately only when there is no pass; when there is a pass,
    // we'll start them alongside the pass to keep them in sync.
    let defensivePromiseArray = [];

    if (!passInfo && defensiveStarters.length > 0) {
      defensivePromiseArray = defensiveStarters.map((start) => start());
    }

    // Phase 1 — Offense-gated: passer hits spot before pass; no-pass step advances when all
    // offense reach their spots. Defensive tweens run in parallel and do not gate the step.
    let requiredOffensiveMoverCount = 0;
    let finalOffensiveMoverSettled = false;
    let requiredMoverIdsForGate = [];
    if (passInfo && passerPromise) {
      await passerPromise;
      requiredOffensiveMoverCount = 1;
      finalOffensiveMoverSettled = true;
      requiredMoverIdsForGate = passInfo?.passerId ? [passInfo.passerId] : [];
    } else if (offensivePromises.length > 0) {
      await Promise.all(offensivePromises);
      requiredOffensiveMoverCount = offensivePromises.length;
      finalOffensiveMoverSettled = true;
      requiredMoverIdsForGate = [...new Set(requiredOffensiveMoverIds)];
    } else {
      requiredOffensiveMoverCount = 0;
      finalOffensiveMoverSettled = false;
      requiredMoverIdsForGate = [];
    }

    if (isStepContractTurn && activeStepStrictMode !== "off") {
      const tolerancePx = isPressureSkeletonTurn
        ? getActivePressureStepTolerancePx()
        : getHcoStepTolerancePx();
      let maxRequiredMoverDeltaPx = 0;
      const requiredMoverDeltaRows = [];
      for (const moverId of requiredMoverIdsForGate) {
        const target = requiredOffensiveMoverTargetPx.get(String(moverId));
        const sprite = playerSprites?.[moverId];
        if (!target || !sprite) continue;
        const deltaPx = Phaser.Math.Distance.Between(
          sprite.x,
          sprite.y,
          target.x,
          target.y
        );
        maxRequiredMoverDeltaPx = Math.max(maxRequiredMoverDeltaPx, deltaPx);
        requiredMoverDeltaRows.push({
          playerId: moverId,
          deltaPx: Number(deltaPx.toFixed(2)),
          targetGridX: target.targetGridX,
          targetGridY: target.targetGridY,
        });
      }
      const stepBudgetSecondsRaw = Number(stepClockSeconds?.[stepIndex]);
      const pressureMinStepBudgetGameSeconds = getPressureReworkStepMinBudgetGameSeconds();
      let stepBudgetGameSeconds =
        Number.isFinite(stepBudgetSecondsRaw) && stepBudgetSecondsRaw > 0
          ? stepBudgetSecondsRaw
          : isPressureSkeletonTurn
          ? getActivePressureStepFallbackBudgetGameSeconds()
          : getHcoStepFallbackBudgetGameSeconds();
      let pressureStepBudgetFloored = false;
      if (
        isPressureSkeletonTurn &&
        (isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled) &&
        stepBudgetGameSeconds < pressureMinStepBudgetGameSeconds
      ) {
        pressureStepBudgetFloored = true;
        stepBudgetGameSeconds = pressureMinStepBudgetGameSeconds;
      }
      const elapsedMs = Date.now() - stepStartMs;
      const elapsedGameSeconds = elapsedMs / clockSecondMs;
      const jitterSlackSeconds = isPressureSkeletonTurn
        ? getActivePressureStepClockJitterSlackSeconds(stepBudgetGameSeconds)
        : getHcoStepClockJitterSlackSeconds(stepBudgetGameSeconds);
      const hardFailThresholdSeconds = stepBudgetGameSeconds + jitterSlackSeconds;
      const budgetOverrunSeconds = elapsedGameSeconds - stepBudgetGameSeconds;
      const observed = {
        finalOffensiveMoverSettled,
        visualSettled: finalOffensiveMoverSettled,
        shotTerminated: false,
      };
      const context = {
        contractFamily: contractUnitPrefix,
        stepIndex,
        hasPassAtStep: Boolean(passInfo),
        requiredOffensiveMoverCount,
        offensivePromiseCount: offensivePromises.length,
        passerId: passInfo?.passerId ?? null,
        requiredMoverIdsForGate,
        tolerancePx,
        maxRequiredMoverDeltaPx: Number(maxRequiredMoverDeltaPx.toFixed(2)),
        elapsedMs,
        elapsedGameSeconds: Number(elapsedGameSeconds.toFixed(2)),
        maxWaitGameSeconds: stepBudgetGameSeconds,
        jitterSlackSeconds: Number(jitterSlackSeconds.toFixed(3)),
        hardFailThresholdSeconds: Number(hardFailThresholdSeconds.toFixed(3)),
        budgetOverrunSeconds: Number(Math.max(0, budgetOverrunSeconds).toFixed(3)),
      };
      if (pressureStepBudgetFloored) {
        context.pressureStepBudgetFloored = true;
        context.pressureStepBudgetFloorFrom = Number.isFinite(stepBudgetSecondsRaw)
          ? Number(stepBudgetSecondsRaw.toFixed(3))
          : null;
        context.pressureStepBudgetFloorTo = Number(stepBudgetGameSeconds.toFixed(3));
        emitPressureReworkTelemetry("pressure_step_budget_floor_applied", {
          stepIndex,
          fromBudgetGameSeconds: Number.isFinite(stepBudgetSecondsRaw)
            ? Number(stepBudgetSecondsRaw.toFixed(3))
            : null,
          toBudgetGameSeconds: Number(stepBudgetGameSeconds.toFixed(3)),
          minBudgetGameSeconds: Number(pressureMinStepBudgetGameSeconds.toFixed(3)),
        });
      }
      if (isPressureSkeletonTurn && (isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled)) {
        emitPressureReworkTelemetry("pressure_step_movement_policy_applied", {
          stepIndex,
          activePressureStepStrictMode,
          tolerancePx,
          maxWaitGameSeconds: stepBudgetGameSeconds,
          jitterSlackSeconds: Number(jitterSlackSeconds.toFixed(3)),
          hardFailThresholdSeconds: Number(hardFailThresholdSeconds.toFixed(3)),
        });
      }
      if (requiredOffensiveMoverCount === 0) {
        emitHcoStepTelemetry("hco_step_movement_no_required_movers", context);
      }
      if (requiredMoverIdsForGate.length > 0 && maxRequiredMoverDeltaPx > tolerancePx) {
        emitHcoStepTelemetry("hco_step_movement_tolerance_breach", {
          ...context,
          requiredMoverDeltaRows,
        });
        const message = `[${contractLabel} step contract] tolerance breach (step=${stepIndex}, maxDeltaPx=${maxRequiredMoverDeltaPx.toFixed(2)}, tolerancePx=${tolerancePx})`;
        if (!isPressureSkeletonTurn || activePressureStepStrictMode === "throw") {
          throw new Error(message);
        }
        emitPressureReworkTelemetry("pressure_step_contract_warn", {
          ...context,
          violation: "tolerance_breach",
          message,
          activePressureStepStrictMode,
        });
      }
      if (elapsedGameSeconds > stepBudgetGameSeconds) {
        emitHcoStepTelemetry("hco_step_movement_clock_soft_overrun", {
          ...context,
          requiredMoverDeltaRows,
        });
      }
      const deferClockHardFailToPassUnit = Boolean(passInfo);
      if (elapsedGameSeconds > hardFailThresholdSeconds && !deferClockHardFailToPassUnit) {
        emitHcoStepTelemetry("hco_step_movement_clock_overrun", {
          ...context,
          requiredMoverDeltaRows,
        });
        const message = `[${contractLabel} step contract] clock overrun (step=${stepIndex}, elapsedGameSeconds=${elapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${stepBudgetGameSeconds}, hardFailThresholdSeconds=${hardFailThresholdSeconds.toFixed(2)})`;
        if (!isPressureSkeletonTurn || activePressureStepStrictMode === "throw") {
          throw new Error(message);
        }
        emitPressureReworkTelemetry("pressure_step_contract_warn", {
          ...context,
          violation: "clock_overrun",
          message,
          activePressureStepStrictMode,
        });
      }
      enforceUnitCompletionContract({
        contract: hcoStepMovementContract,
        observed,
        context,
        emitTelemetry: emitHcoStepTelemetry,
        logger: console,
      });
    }
    captureHcoUnitElapsed("step_movement");

    // Phase 2 — Pass animation only (defense may run alongside; we do not await defense).
    if (passInfo) {
      const { handlePassAnimation } = await import("./passDetection.js");
      const passStartMs = Date.now();
      if (defensiveStarters.length > 0) {
        defensivePromiseArray = defensiveStarters.map((start) => start());
      }
      const passPromise = handlePassAnimation({
        scene,
        passInfo,
        playerSprites,
      });
      await passPromise;
      if (isStepContractTurn && activeStepStrictMode !== "off") {
        const receiverId = String(passInfo?.receiverId ?? "");
        const receiverSprite = receiverId ? playerSprites?.[receiverId] : null;
        const receiverTarget = receiverId
          ? requiredOffensiveMoverTargetPx.get(receiverId)
          : null;
        const tolerancePx = isPressureSkeletonTurn
          ? getActivePressureStepPassReceiverTolerancePx()
          : getHcoStepTolerancePx();
        const stepBudgetSecondsRaw = Number(stepClockSeconds?.[stepIndex]);
        const pressureMinStepBudgetGameSeconds = getPressureReworkStepMinBudgetGameSeconds();
        let stepBudgetGameSeconds =
          Number.isFinite(stepBudgetSecondsRaw) && stepBudgetSecondsRaw > 0
            ? stepBudgetSecondsRaw
            : isPressureSkeletonTurn
            ? getActivePressureStepFallbackBudgetGameSeconds()
            : getHcoStepFallbackBudgetGameSeconds();
        let pressureStepBudgetFloored = false;
        if (
          isPressureSkeletonTurn &&
          (isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled) &&
          stepBudgetGameSeconds < pressureMinStepBudgetGameSeconds
        ) {
          pressureStepBudgetFloored = true;
          stepBudgetGameSeconds = pressureMinStepBudgetGameSeconds;
        }
        const jitterSlackSeconds = isPressureSkeletonTurn
          ? getActivePressureStepPassClockJitterSlackSeconds(stepBudgetGameSeconds)
          : getHcoStepPassClockJitterSlackSeconds(stepBudgetGameSeconds);
        const hardFailThresholdSeconds = stepBudgetGameSeconds + jitterSlackSeconds;
        const stepElapsedMs = Date.now() - stepStartMs;
        const stepElapsedGameSeconds = stepElapsedMs / clockSecondMs;
        const passElapsedMs = Date.now() - passStartMs;
        const passElapsedGameSeconds = passElapsedMs / clockSecondMs;
        const receiverDeltaPx =
          receiverSprite && receiverTarget
            ? Phaser.Math.Distance.Between(
                receiverSprite.x,
                receiverSprite.y,
                receiverTarget.x,
                receiverTarget.y
              )
            : null;
        const receiverSettled =
          receiverDeltaPx != null && Number.isFinite(receiverDeltaPx)
            ? receiverDeltaPx <= tolerancePx
            : false;
        const ownerAtEnd = getCurrentOwner(scene);
        const pendingOwnerAtEnd = getPendingOwner(scene);
        const ownerMatchesReceiver =
          receiverId.length > 0 &&
          (String(ownerAtEnd ?? "") === receiverId ||
            String(pendingOwnerAtEnd ?? "") === receiverId);
        const passContext = {
          contractFamily: contractUnitPrefix,
          stepIndex,
          passStep: true,
          passerId: passInfo?.passerId ?? null,
          receiverId: passInfo?.receiverId ?? null,
          ownerAtEnd: ownerAtEnd ?? null,
          pendingOwnerAtEnd: pendingOwnerAtEnd ?? null,
          ownerMatchesReceiver,
          receiverDeltaPx:
            receiverDeltaPx == null ? null : Number(receiverDeltaPx.toFixed(2)),
          tolerancePx,
          passElapsedMs,
          passElapsedGameSeconds: Number(passElapsedGameSeconds.toFixed(2)),
          elapsedMs: stepElapsedMs,
          elapsedGameSeconds: Number(stepElapsedGameSeconds.toFixed(2)),
          maxWaitGameSeconds: stepBudgetGameSeconds,
          jitterSlackSeconds: Number(jitterSlackSeconds.toFixed(3)),
          hardFailThresholdSeconds: Number(hardFailThresholdSeconds.toFixed(3)),
        };
        if (pressureStepBudgetFloored) {
          passContext.pressureStepBudgetFloored = true;
          passContext.pressureStepBudgetFloorFrom = Number.isFinite(stepBudgetSecondsRaw)
            ? Number(stepBudgetSecondsRaw.toFixed(3))
            : null;
          passContext.pressureStepBudgetFloorTo = Number(stepBudgetGameSeconds.toFixed(3));
          emitPressureReworkTelemetry("pressure_step_budget_floor_applied", {
            stepIndex,
            fromBudgetGameSeconds: Number.isFinite(stepBudgetSecondsRaw)
              ? Number(stepBudgetSecondsRaw.toFixed(3))
              : null,
            toBudgetGameSeconds: Number(stepBudgetGameSeconds.toFixed(3)),
            minBudgetGameSeconds: Number(pressureMinStepBudgetGameSeconds.toFixed(3)),
            passStep: true,
          });
        }
        if (isPressureSkeletonTurn && (isPressureReworkPhase2Enabled || isPressureReworkPhase3LeadInEnabled)) {
          emitPressureReworkTelemetry("pressure_step_pass_policy_applied", {
            stepIndex,
            activePressureStepStrictMode,
            passReceiverTolerancePx: tolerancePx,
            maxWaitGameSeconds: stepBudgetGameSeconds,
            jitterSlackSeconds: Number(jitterSlackSeconds.toFixed(3)),
            hardFailThresholdSeconds: Number(hardFailThresholdSeconds.toFixed(3)),
          });
        }
        if (!receiverSprite || !receiverTarget) {
          emitHcoStepTelemetry("hco_step_pass_missing_receiver_target", passContext);
          const message = `[${contractLabel} step pass contract] missing receiver settle target (step=${stepIndex}, receiverId=${passInfo?.receiverId ?? "?"})`;
          if (!isPressureSkeletonTurn || activePressureStepStrictMode === "throw") {
            throw new Error(message);
          }
          emitPressureReworkTelemetry("pressure_step_contract_warn", {
            ...passContext,
            violation: "missing_receiver_target",
            message,
            activePressureStepStrictMode,
          });
        }
        if (!receiverSettled) {
          emitHcoStepTelemetry("hco_step_pass_receiver_settle_breach", passContext);
          const message = `[${contractLabel} step pass contract] receiver settle breach (step=${stepIndex}, receiverId=${passInfo?.receiverId ?? "?"}, deltaPx=${receiverDeltaPx.toFixed(2)}, tolerancePx=${tolerancePx})`;
          if (!isPressureSkeletonTurn || activePressureStepStrictMode === "throw") {
            throw new Error(message);
          }
          emitPressureReworkTelemetry("pressure_step_contract_warn", {
            ...passContext,
            violation: "receiver_settle_breach",
            message,
            activePressureStepStrictMode,
          });
        }
        if (!ownerMatchesReceiver) {
          emitHcoStepTelemetry("hco_step_pass_owner_mismatch", passContext);
          const message = `[${contractLabel} step pass contract] owner mismatch at pass end (step=${stepIndex}, receiverId=${passInfo?.receiverId ?? "?"}, owner=${ownerAtEnd ?? "null"}, pendingOwner=${pendingOwnerAtEnd ?? "null"})`;
          if (!isPressureSkeletonTurn || activePressureStepStrictMode === "throw") {
            throw new Error(message);
          }
          emitPressureReworkTelemetry("pressure_step_contract_warn", {
            ...passContext,
            violation: "owner_mismatch",
            message,
            activePressureStepStrictMode,
          });
        }
        if (stepElapsedGameSeconds > stepBudgetGameSeconds) {
          emitHcoStepTelemetry("hco_step_pass_clock_soft_overrun", passContext);
        }
        if (stepElapsedGameSeconds > hardFailThresholdSeconds) {
          emitHcoStepTelemetry("hco_step_pass_clock_overrun", passContext);
          const message = `[${contractLabel} step pass contract] clock overrun (step=${stepIndex}, elapsedGameSeconds=${stepElapsedGameSeconds.toFixed(2)}, maxWaitGameSeconds=${stepBudgetGameSeconds}, hardFailThresholdSeconds=${hardFailThresholdSeconds.toFixed(2)})`;
          if (!isPressureSkeletonTurn || activePressureStepStrictMode === "throw") {
            throw new Error(message);
          }
          emitPressureReworkTelemetry("pressure_step_contract_warn", {
            ...passContext,
            violation: "clock_overrun",
            message,
            activePressureStepStrictMode,
          });
        }
        enforceUnitCompletionContract({
          contract: hcoStepPassContract,
          observed: {
            finalOffensiveMoverSettled: receiverSettled,
            visualSettled: receiverSettled,
            shotTerminated: false,
          },
          context: passContext,
          emitTelemetry: emitHcoStepTelemetry,
          logger: console,
        });
      }
      captureHcoUnitElapsed("step_pass");
    }

    // Phase 3 — After a pass, ensure every offensive player (including passer) reached this step.
    // No-pass: already satisfied in phase 1.
    if (passInfo && offensivePromises.length > 0) {
      await Promise.all(offensivePromises);
    }

    if (shotInfo) {
      currentBallOwnerRef.value = null;
      const shooterPos = scene.playerInfo?.[shotInfo.playerId]?.pos;
      const shooterTeamId = playerSprites[shotInfo.playerId]?.team_id;
      const shootParams = {
        scene,
        ballSprite,
        fromCoords: shotInfo.step.coords,
        startTimestamp: shotInfo.step.timestamp,
        // Map rebound result types to "MISS" so shootBall returns a landing spot
        result: ["DREB", "OREB"].includes(
          turnData.rebound_type || turnData.result_type
        )
          ? "MISS"
          : turnData.result_type,
        shooterPos,
        shooterId: shotInfo.playerId,
        shooterTeamId,
        homeTeamId,
        stepIndex: shotInfo.stepIndex,
        turnIndex: scene.currentTurn,
        turnData: turnData
      };
      if (SHOT_DEBUG) {
        animationDebugLog("shootParams", {
          stepIndex: shootParams.stepIndex,
          turnIndex: shootParams.turnIndex,
          shooterId: shootParams.shooterId,
          result: shootParams.result,
        });
      }
      // console.log("🏀 HCO SHOT - About to call shootBall", {
      //   currentState: scene.stateMachine?.state,
      //   shooterId: shootParams.shooterId,
      //   result: shootParams.result,
      //   fromCoords: shootParams.fromCoords
      // });
      
      // Check if this is an audible/hot read (shooter different from intended)
      let isAudible = false;
      if (turnData.shooter_pos && 
          turnData.intended_shooter_pos && 
          turnData.shooter_pos !== turnData.intended_shooter_pos) {
        
        console.log('🔥 AUDIBLE DETECTED:', {
          shooter_pos: turnData.shooter_pos,
          intended_shooter_pos: turnData.intended_shooter_pos,
          shooter_id: shotInfo.playerId
        });
        
        // Get shooter info
        const shooterInfo = scene.playerInfo?.[shotInfo.playerId];
        const shooterMO = shooterInfo?.attributes?.MO || 5;
        
        console.log('🔥 Shooter MO:', shooterMO, 'Info:', shooterInfo);
        
        // Determine audible text based on MO attribute
        const audibleText = shooterMO >= 7 ? "HOT READ!" : "AUDIBLE!";
        
        console.log('🔥 Audible text:', audibleText);
        
        // Update scoreboard with audible text next to ball icon (stays visible until shot completes)
        const { getBallHandlerIdFromTurn, getDefenderIdFromTurn } = await import('../utils/activePlayerDisplay.js');
        const defenderId = getDefenderIdFromTurn(turnData);
        const homeTeamId = scene.simData?.home_team_id || null;
        
        if (typeof window.updateActivePlayersDisplay === 'function') {
          console.log('🔥 Calling updateActivePlayersDisplay with audibleText:', audibleText);
          window.updateActivePlayersDisplay(shotInfo.playerId, defenderId, homeTeamId, playerSprites, audibleText);
        } else {
          console.warn('⚠️ window.updateActivePlayersDisplay not found');
        }
        
        isAudible = true;
      }
      
      const shotResult = await shootBall(shootParams);
      
      // Clear audible text after shot animation completes
      if (isAudible && typeof window.updateActivePlayersDisplay === 'function') {
        const { getBallHandlerIdFromTurn, getDefenderIdFromTurn } = await import('../utils/activePlayerDisplay.js');
        const ballHandlerId = getBallHandlerIdFromTurn(turnData, 0);
        const defenderId = getDefenderIdFromTurn(turnData);
        const homeTeamId = scene.simData?.home_team_id || null;
        // Call without audibleText to clear it
        window.updateActivePlayersDisplay(ballHandlerId, defenderId, homeTeamId, playerSprites, null);
      }
      
      // console.log("🏀 HCO SHOT - shootBall returned", shotResult);
      const ballSpot = shotResult?.grid;
      // console.log("result_type", turnData.result_type);
      
      // Check if this MAKE is from a putback
      // With new OREB turn architecture, putbacks are separate turns, not events
      // But keep this check for backward compatibility
      const hasPutbackMake = turnData.events?.some(evt => 
        evt.event_type === "PUTBACK_ATTEMPT" && evt.result === "MAKE"
      );
      
      if (turnData.result_type === "MAKE") {
        // Visual effects for AND-1 now handled in ballManager.js when "And 1!" is announced
        
        // ✅ OPTION 1 FIX: Ensure onShotEnd() is called before transitioning to next operation
        // This ensures ball state is cleared before free throw or inbound pass
        const { getBallController } = await import('./BallControllerAdapter.js');
        const ballController = getBallController();
        if (ballController && ballController.isInFlight) {
          ballController.onShotEnd();
        }
        
        // ✅ FIX: Match HCO's approach - call runInboundSetup() if next_play_type is BASELINE_INBOUND
        // This works for both HCO shots and FCP/HCT shots
        // For AND-1 situations (next_play_type === "FREE_THROW"), let the free throw system handle the transition
        const nextTurn = simData?.turns?.[scene.currentTurn + 1];
        const hasPendingFreeThrow =
          nextTurn?.result_type === "FREE_THROW" ||
          (turnData.free_throws_remaining && turnData.free_throws_remaining > 0);
        
        // ✅ FIX: Don't call runInboundSetup() here if next_play_type === "BASELINE_INBOUND"
        // The BASELINE_INBOUND turn will handle the inbound setup via AnimationEngine.handleBaselineInbound()
        // Calling it here causes double inbound passes and double setup animations
        if (!hasPendingFreeThrow && !hasPutbackMake && turnData.next_play_type === "BASELINE_INBOUND") {
          // ✅ REMOVED: runInboundSetup() call - BASELINE_INBOUND turn handles it
          // This prevents double inbound passes and double setup animations
        }
        
        // ✅ REMOVED: Special FCP/HCT handling - FCP/HCT now routes through AnimationRouter (same as HCO)
        // AnimationRouter handles announcements and updates via finalizeTurnAfterAnimation
      } else if (ballSpot) {
        if (turnData.result_type === 'BLOCK' || turnData.rebound_type === 'OREB') {
          console.log('🟡🟡🟡 [BLOCK/OREB BALL] playTurnAnimation calling animateRebound', {
            result_type: turnData.result_type,
            rebound_type: turnData.rebound_type,
            ballSpot,
          });
        }
        const rebounderId =
          turnData.rebounder_player_id ||
          turnData.rebounderId ||
          turnData.rebounder_id ||
          null;
        if (rebounderId) {
          // Use the unified animateRebound function for all rebounds
          await animateRebound({
            scene,
            ballSprite,
            playerSprites,
            animations: turnData.animations || [],
            rebounderId,
            ballSpot,
            shooterId: shotInfo?.playerId ?? null,
            upcomingFastBreak: turnData.fast_break || false,
            turnData: turnData // Pass turnData so get-back players can be excluded
          });
          
          const rebounderSprite = playerSprites[rebounderId];
          // ✅ FIX: Use offense_team_id (SS&S possession system)
          const isDreb = turnData.rebound_type
            ? turnData.rebound_type === "DREB"
            : rebounderSprite?.team_id !== turnData.offense_team_id;
          // ✅ Skip DREB setup if next play is Fast Break - player advancement happens in outlet phase
          if (isDreb && !turnData.fast_break && turnData.next_play_type !== "FAST_BREAK") {
            // Find the MISS/BLOCK turn that led to this DREB
            // In playTurnAnimation, turnData should be the MISS/BLOCK turn itself
            // Check if this turnData is a MISS or BLOCK turn first, otherwise look for it
            const isMissOrBlock = turnData?.result_type === "MISS" || turnData?.result_type === "BLOCK";
            let missTurn = isMissOrBlock ? turnData : null;
            if (!missTurn) {
              // If not, look for it in previous turn or current turn
              const currentIndex = scene.currentTurn || 0;
              const previousTurn = scene.simData?.turns?.[currentIndex - 1];
              const currentTurn = scene.simData?.turns?.[currentIndex];
              
              if (previousTurn?.result_type === "MISS" || previousTurn?.result_type === "BLOCK") {
                missTurn = previousTurn;
              } else if (currentTurn?.result_type === "MISS" || currentTurn?.result_type === "BLOCK") {
                missTurn = currentTurn;
              }
              
              console.log('🔍 [GET BACK DEBUG] Searching for MISS turn', {
                turnDataResultType: turnData?.result_type,
                currentTurnIndex: currentIndex,
                previousTurnResultType: previousTurn?.result_type,
                currentTurnResultType: currentTurn?.result_type,
                foundMissTurn: !!missTurn,
                missTurnHasGetBack: !!missTurn?.offense_getback
              });
            } else {
              console.log('🔍 [GET BACK DEBUG] Using current turnData as MISS turn', {
                turnDataResultType: turnData?.result_type,
                hasOffenseGetBack: !!turnData?.offense_getback,
                offenseGetBackCount: turnData?.offense_getback?.length || 0
              });
            }
            
            await runDefensiveReboundSetup({
              scene,
              ballSprite,
              playerSprites,
              rebounderId,
              nextPlayType: turnData.next_play_type || "HCO",
              turnData: missTurn, // get-back source
              authorityTurnData: turnData, // strict outlet contract source
            });
          } else {
            const pauseCap = Math.max(
              0,
              Number(
                (typeof window !== "undefined"
                  ? window.UESS_OFFENSIVE_REBOUND_PAUSE_CAP_MS
                  : globalThis?.UESS_OFFENSIVE_REBOUND_PAUSE_CAP_MS) ?? 300
              ) || 300
            );
            const pause = Math.min(
              Math.max(0, Number(animationConfig.offensiveRebound.pauseMs) || 0),
              pauseCap
            );
            await new Promise((res) =>
              scene.time?.delayedCall
                ? scene.time.delayedCall(pause, res)
                : setTimeout(res, pause)
            );
            if (!scene.skipToEnd && Array.isArray(turnData.events)) {
              eventsProcessed = true;
              for (const evt of turnData.events) {
                if (scene.skipToEnd) break;
                if (evt.event_type === "PUTBACK_ATTEMPT") {
                  // SKIP: Putback attempts are handled by handleOrebTurn() in animateGameTurns.js
                  // This event processing happens during step-by-step animation, but putbacks
                  // should be handled as a separate turn type, not as an event in the animation sequence.
                  // Attaching the ball here causes it to briefly attach before the shot animation.
                  // The handleOrebTurn function already properly handles ball attachment and shot animation.
                  continue;
                  if (evt.result === "MISS" && evt.rebound) {
                    const reboundData = evt.rebound;
                    const rebounderId =
                      reboundData.rebounder_player_id || reboundData.rebounderId;
                    await animateRebound({
                      scene,
                      ballSprite,
                      playerSprites,
                      animations: reboundData.animations || turnData.animations,
                      rebounderId,
                      ballSpot: putbackResult?.grid || reboundData.ballSpot,
                      shooterId: evt.shooterId,
                      turnData: turnData // Pass turnData so get-back players can be excluded
                    });
                    if (
                      reboundData.rebound_type === "DREB" &&
                      !turnData.fast_break
                    ) {
                      // For putback events, find the MISS/BLOCK turn with offense_getback
                      const isMissOrBlockEvt = turnData?.result_type === "MISS" || turnData?.result_type === "BLOCK";
                      let missTurn = isMissOrBlockEvt ? turnData : null;
                      if (!missTurn) {
                        const currentIndex = scene.currentTurn || 0;
                        missTurn = scene.simData?.turns?.[currentIndex - 1];
                      }
                      
                      await runDefensiveReboundSetup({
                        scene,
                        ballSprite,
                        playerSprites,
                        rebounderId,
                        nextPlayType: turnData.next_play_type || "HCO",
                        turnData: missTurn,
                        authorityTurnData: turnData,
                      });
                    }
                  }
                } else if (evt.event_type === "KICKOUT_RESET") {
                  await animateKickoutReset(
                    scene,
                    ballSprite,
                    evt.rebounder_player_id || evt.rebounderId,
                    evt.pgId,
                    evt.pass
                  );
                  if (typeof scene.startNextHalfCourtOffense === "function") {
                    scene.startNextHalfCourtOffense();
                  }
                }
              }
            }
          }
        }
      }
      validateHcoResolution({
        stepIndex: shotInfo?.stepIndex ?? stepIndex,
        branch: "shot_resolution",
      });
      break;
    }
  }

  if (!eventsProcessed && !scene.skipToEnd && Array.isArray(turnData.events)) {
    for (const evt of turnData.events) {
      if (scene.skipToEnd) break;
                if (evt.event_type === "PUTBACK_ATTEMPT") {
                  const shooterId = evt.shooterId;
                  const rebounderSprite = playerSprites[shooterId];
                  if (!rebounderSprite) continue;
                  attachBallToPlayer(scene, ballSprite, rebounderSprite, {
                    debugInfo: { shooterId, reboundSpot: evt.rebound?.ballSpot || null }
                  });
                  const rimCoords =
                    rebounderSprite.team === "home" ? HOME_RIM_COORDS : AWAY_RIM_COORDS;
                  const putbackResult = await animatePutbackAttempt(
                    scene,
                    ballSprite,
                    shooterId,
                    rimCoords,
                    evt.duration || 500,
                    evt.result
                  );
                  
                  // Handle made putbacks
                  if (evt.result === "MAKE") {
                    // Possession flips after made putback
                    const shooterTeamId = rebounderSprite.team_id;
                    const shooterTeamIsHome = String(shooterTeamId) === String(homeTeamId);
                    const newOffenseSide = shooterTeamIsHome ? "away" : "home";
                    
                    // Check for defensive pressure
                    const skipRetreat = turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT";
                    const pressureType = skipRetreat ? turnData.next_defensive_setup : null;
                    if (skipRetreat) {
                      // Skip defensive retreat for FCP/HCT after putback
                    }
                    
                    await runInboundSetup({
                      scene,
                      ballSprite,
                      playerSprites,
                      newOffenseSide,
                      homeTeamId,
                      awayTeamId,
                      skipRetreat,
                      pressureType,
                    });
                  }
                  // Handle missed putbacks
                  else if (evt.result === "MISS" && evt.rebound) {
                    const reboundData = evt.rebound;
                    const rebounderId =
                      reboundData.rebounder_player_id || reboundData.rebounderId;
                    const putbackMissBallSpot = putbackResult?.grid || reboundData.ballSpot;
                    console.log('🟡🟡🟡 [BLOCK/OREB BALL] putback-miss path calling animateRebound', {
                      ballSpot: putbackMissBallSpot,
                      from_putbackResult: !!putbackResult?.grid,
                      from_reboundData: !!reboundData.ballSpot,
                    });
                    await animateRebound({
                      scene,
                      ballSprite,
                      playerSprites,
                      animations: reboundData.animations || turnData.animations,
                      rebounderId,
                      ballSpot: putbackMissBallSpot,
                      shooterId: evt.shooterId,
                      turnData: turnData // Pass turnData so get-back players can be excluded
                    });
                    if (
                      reboundData.rebound_type === "DREB" &&
                      !turnData.fast_break
                    ) {
                      // For putback events, find the MISS/BLOCK turn with offense_getback
                      const isMissOrBlockPutback = turnData?.result_type === "MISS" || turnData?.result_type === "BLOCK";
                      let missTurn = isMissOrBlockPutback ? turnData : null;
                      if (!missTurn) {
                        const currentIndex = scene.currentTurn || 0;
                        missTurn = scene.simData?.turns?.[currentIndex - 1];
                      }
                      
                      await runDefensiveReboundSetup({
                        scene,
                        ballSprite,
                        playerSprites,
                        rebounderId,
                        nextPlayType: turnData.next_play_type || "HCO",
                        turnData: missTurn,
                        authorityTurnData: turnData,
                      });
                    }
                  }
                } else if (evt.event_type === "KICKOUT_RESET") {
        await animateKickoutReset(
          scene,
          ballSprite,
          evt.rebounder_player_id || evt.rebounderId,
          evt.pgId,
          evt.pass
        );
        if (typeof scene.startNextHalfCourtOffense === "function") {
          scene.startNextHalfCourtOffense();
        }
      }
    }

  }
  validateHcoResolution({
    branch: "turn_end",
  });
  validateHcoTransitionOut({
    branch: "turn_end",
    resultType: turnData?.result_type ?? null,
    turnId: turnData?.turn_count ?? turnData?.id ?? null,
    turnIndex: scene?.currentTurn ?? null,
  });
  emitHcoElapsedObserveTelemetry({
    branch: "turn_end",
    strictMode: hcoStepStrictMode,
  });
}

/**
 * Phase 4: Final Turn alignment — tween offense and defense to oDestinations/dDestinations.
 * When away team is on offense, flip both offense and defense coords so the whole setup is on the
 * away (attacking) half; backend sends home-side coords. If the live owner differs from the step-0
 * handler, preserve the live owner so ShotAnimationSystem can animate the step-0 entry pass.
 */
export async function runFinalTurnAlignment({ scene, playerSprites, ballSprite, turnData }) {
  if (scene?.skipToEnd || !turnData) return;
  const oDestinations = turnData.oDestinations || turnData.o_destinations || {};
  const dDestinations = turnData.dDestinations || turnData.d_destinations || {};
  const { resolveOffenseTeamId } = await import('../utils/offenseTeamIdResolver.js');
  const offenseTeamId = resolveOffenseTeamId({ scene, turnData, playerSprites });
  const homeTeamId = scene.simData?.home_team_id;
  const isAwayOffense = offenseTeamId && homeTeamId && String(offenseTeamId) !== String(homeTeamId);
  const flipCoords = (coords) => ({ x: 101 - coords.x, y: coords.y });

  const width = scene.game.config.width;
  const height = scene.game.config.height;
  const cfg = animationConfig?.finalTurn?.alignment || {};
  const ease = cfg.ease ?? "Linear";

  const offenseSprites = {};
  const defenseSprites = {};
  let ballHandlerSprite = null;

  if (scene.tweens && ballSprite) scene.tweens.killTweensOf(ballSprite);
  for (const [id, sprite] of Object.entries(playerSprites)) {
    const info = scene.playerInfo?.[id];
    if (!info) continue;
    if (scene.tweens) scene.tweens.killTweensOf(sprite);
    if (String(sprite.team_id) === String(offenseTeamId)) {
      offenseSprites[info.pos] = sprite;
    } else {
      defenseSprites[info.pos] = sprite;
    }
  }

  const addTween = (sprite, coords, pos) => {
    if (!sprite || !coords) return Promise.resolve();
    const { x, y } = gridToPixels(coords.x, coords.y, width, height);
    const duration = getPlayerDuration(sprite, x, y);
    return new Promise((resolve) => {
      scene.tweens.add({
        targets: sprite,
        x, y, duration, ease,
        onComplete: resolve,
        onStop: resolve
      });
    });
  };

  const promises = [];
  Object.entries(oDestinations).forEach(([pos, coords]) => {
    const c = isAwayOffense ? flipCoords(coords) : coords;
    promises.push(addTween(offenseSprites[pos], c, pos));
  });
  Object.entries(dDestinations).forEach(([pos, coords]) => {
    const c = isAwayOffense ? flipCoords(coords) : coords;
    promises.push(addTween(defenseSprites[pos], c, pos));
  });

  await Promise.all(promises);

  const ballHandlerId = turnData.ball_handler_id ?? turnData.roles?.ball_handler_id ?? turnData.ball_handler?.player_id;
  if (!ballHandlerId && turnData.animations?.length) {
    const animWithBall = turnData.animations.find(a => a.hasBallAtStep?.[0]);
    if (animWithBall) ballHandlerSprite = playerSprites[animWithBall.playerId];
  } else if (ballHandlerId) {
    ballHandlerSprite = playerSprites[ballHandlerId];
  }
  const liveOwnerId = getCurrentOwner(scene) ?? getPendingOwner(scene) ?? null;
  const preserveLiveOwner =
    ballHandlerSprite &&
    liveOwnerId != null &&
    String(liveOwnerId) !== String(ballHandlerSprite.playerId);
  if (ballSprite && ballHandlerSprite && !preserveLiveOwner) {
    attachBallToPlayer(scene, ballSprite, ballHandlerSprite);
  }
}

export { runInboundSetup, runSideInboundSetup, runDefensiveReboundSetup, runOffensiveReboundKickoutSetup, getPlayerDuration, animateQuickFoulDefenderToReceiver };
// Provide an uncapped duration helper for long transitions (e.g., inbound -> HCO)
export function getPlayerDurationUncapped(sprite, targetX, targetY, opts = {}) {
  return getPlayerMovementDurationMs(sprite, targetX, targetY, {
    ...opts,
    scene: opts.scene ?? sprite?.scene,
  });
}

// Animate a short defensive stop resolution and transition to HalfCourt
export async function runDefensiveStopTransition({ scene, playerSprites, ballSprite }) {
  try {
    const width = scene.game.config.width;
    const height = scene.game.config.height;
    const isHomeOffense = (scene.offenseTeamId && scene.simData?.home_team_id === scene.offenseTeamId) || false;
    // Choose a generic "top of key" on offense side
    const targetGrid = isHomeOffense ? { x: 86, y: 25 } : { x: 14, y: 25 };
    const targetPx = gridToPixels(targetGrid.x, targetGrid.y, width, height);

    const currentOwnerId = getCurrentOwner(scene);
    const handlerSprite = currentOwnerId ? playerSprites[currentOwnerId] : null;

    const promises = [];
    if (handlerSprite) {
      const handlerDuration = getPlayerDuration(handlerSprite, targetPx.x, targetPx.y, true);
      promises.push(
        tweenPlayerTo(scene, handlerSprite, targetPx, { duration: handlerDuration, easing: 'Linear' })
      );
      // Attach ball if not attached so it follows visually
      if (ballSprite) attachBallToPlayer(scene, ballSprite, handlerSprite);
    }

    // Move nearest defender to contest
    let nearestDefender = null;
    let nearestDist = Infinity;
    for (const [id, sprite] of Object.entries(playerSprites)) {
      if (!sprite || !scene.playerInfo?.[id]) continue;
      const info = scene.playerInfo[id];
      // Opposite team of offense
      const isDefender = info.team !== (isHomeOffense ? 'home' : 'away');
      if (!isDefender) continue;
      const d = Phaser.Math.Distance.Between(sprite.x, sprite.y, targetPx.x, targetPx.y);
      if (d < nearestDist) {
        nearestDist = d;
        nearestDefender = sprite;
      }
    }
    if (nearestDefender) {
      // Slight offset to indicate contest
      const contestPx = { x: targetPx.x + (isHomeOffense ? -18 : 18), y: targetPx.y };
      const defDuration = getPlayerDuration(nearestDefender, contestPx.x, contestPx.y, true);
      promises.push(
        tweenPlayerTo(scene, nearestDefender, contestPx, { duration: defDuration, easing: 'Linear' })
      );
    }

    if (promises.length) await Promise.all(promises);

    // Transition to HalfCourt for next possession
    if (scene.stateMachine) {
      safeTransition(scene.stateMachine, States.HalfCourt, 'defensive_stop_to_halfcourt');
    }
  } catch (err) {
    console.warn('runDefensiveStopTransition failed', err);
  }
}

if (typeof window !== "undefined") {
  window.playTurnAnimation = playTurnAnimation;
}
