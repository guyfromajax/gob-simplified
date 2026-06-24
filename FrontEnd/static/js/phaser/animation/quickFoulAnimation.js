/**
 * Quick Foul (situational Force Foul) animation helpers.
 * BIP/SIP: fouler setup near receiver → pass → reach_in + SFX → announce.
 * DREB / Final Turn: sprint to victim → reach_in + SFX → announce (clock runs via turn contract).
 */

import { gridToPixels } from '../utils/gridToPixels.js';
import { tweenPlayerTo } from './ballTween.js';
import animationConfig from './animation_config.js';
import { getPlayerMovementDurationMs } from '../utils/playerMovementDuration.js';
import { awaitReachInFlourish } from './flourishes.js';

const DEFAULT_MAX_GRID_RADIUS = 2;

function pixelsToGrid(pixelX, pixelY, width, height) {
  return {
    x: (pixelX / width) * 100,
    y: (pixelY / height) * 50,
  };
}

function getSprintSpeedMultiplier() {
  return (
    animationConfig?.quickFoul?.sprintSpeedMultiplier
    ?? animationConfig?.fastBreak?.sprintSpeed
    ?? 1.5
  );
}

function getSprintDurationMs(sprite, targetX, targetY, opts = {}) {
  const base = getPlayerMovementDurationMs(sprite, targetX, targetY, opts);
  const mult = getSprintSpeedMultiplier();
  return Math.max(50, base / mult);
}

/**
 * Pick a pixel target within ``maxGridRadius`` Euclidean grid units of the victim,
 * biased toward the defender's current position.
 */
export function pickQuickFoulApproachPixels(scene, defenderSprite, victimSprite, maxGridRadius = DEFAULT_MAX_GRID_RADIUS) {
  if (!scene || !defenderSprite || !victimSprite) return null;
  const w = scene.game.config?.width ?? 1229;
  const h = scene.game.config?.height ?? 768;
  const vGrid = pixelsToGrid(victimSprite.x, victimSprite.y, w, h);
  const dGrid = pixelsToGrid(defenderSprite.x, defenderSprite.y, w, h);
  const dx = dGrid.x - vGrid.x;
  const dy = dGrid.y - vGrid.y;
  const dist = Math.hypot(dx, dy);
  if (dist <= maxGridRadius) {
    return { x: defenderSprite.x, y: defenderSprite.y };
  }
  const r = Math.min(maxGridRadius * 0.875, Math.max(0.5, maxGridRadius - 0.01));
  const gx = vGrid.x + (dx / (dist || 1)) * r;
  const gy = vGrid.y + (dy / (dist || 1)) * r;
  return gridToPixels(gx, gy, w, h);
}

export function resolveQuickFoulInboundPair(turnData, nextTurn, playerSprites, passInfo) {
  const pending = Boolean(turnData?.force_foul_pending);
  const fromNext = nextTurn?.quick_foul && nextTurn?.result_type === 'FOUL';
  if (!pending && !fromNext) return null;

  const foulerId = String(
    turnData?.force_foul_fouler_id ?? nextTurn?.foul_player_id ?? ''
  );
  const receiverId = String(
    turnData?.force_foul_receiver_id
    ?? passInfo?.receiverId
    ?? nextTurn?.ball_handler
    ?? nextTurn?.shooter
    ?? ''
  );
  if (!foulerId || !receiverId) return null;

  const defenderSprite = playerSprites?.[foulerId];
  const victimSprite = playerSprites?.[receiverId];
  if (!defenderSprite || !victimSprite) return null;

  return {
    foulerId,
    receiverId,
    defenderSprite,
    victimSprite,
    foulTurnData: nextTurn ?? null,
  };
}

export async function announceQuickFoul(scene, turnData) {
  if (!scene || !turnData) return;
  const { announceGameEvent } = await import('../utils/gameAnnouncements.js');
  announceGameEvent('FOUL_DEFENSIVE', turnData, scene, {
    foulerId: turnData.foul_player_id,
  });
}

/**
 * Reach-in micro-move toward the ball, then announce Quick Foul.
 */
export async function commitQuickFoulReachInAndAnnounce(scene, {
  defenderSprite,
  victimSprite,
  ballSprite,
  turnDataForAnnounce,
  markTurnDone,
}) {
  if (!defenderSprite || !victimSprite || !turnDataForAnnounce) return;

  await awaitReachInFlourish(scene, defenderSprite, ballSprite, turnDataForAnnounce);
  await announceQuickFoul(scene, turnDataForAnnounce);

  if (markTurnDone) {
    markTurnDone._quickFoulAnnounceDone = true;
  }
}

/**
 * Sprint to within 2 grid of victim, reach_in, announce. Total wall time follows
 * the turn clock contract when ``clockBudgetMs`` is provided.
 */
export async function runQuickFoulSprintSequence(scene, {
  defenderSprite,
  victimSprite,
  ballSprite,
  turnData,
  clockBudgetMs,
}) {
  if (!scene?.tweens || !defenderSprite || !victimSprite || !turnData) return;

  const target = pickQuickFoulApproachPixels(scene, defenderSprite, victimSprite);
  if (!target) return;

  const reachMs = Number(animationConfig?.flourish?.reachIn?.durationMs) || 450;
  const totalMs = Math.max(
    reachMs + 50,
    Number(clockBudgetMs)
      || Number(turnData?.real_time_elapsed_ms ?? turnData?.realTimeElapsedMs)
      || Number(scene?._clockInterpolationDurationMs)
      || 1050,
  );
  const sprintMs = Math.max(50, totalMs - reachMs);
  let sprintDuration = getSprintDurationMs(defenderSprite, target.x, target.y, { scene });
  sprintDuration = Math.min(sprintDuration, sprintMs);

  await tweenPlayerTo(scene, defenderSprite, target, {
    duration: sprintDuration,
    easing: 'Linear',
  });

  const remainingMs = Math.max(0, totalMs - sprintDuration);
  if (remainingMs > 0) {
    await new Promise((resolve) => {
      if (scene.time?.delayedCall) {
        scene.time.delayedCall(remainingMs, resolve);
      } else {
        setTimeout(resolve, remainingMs);
      }
    });
  }

  turnData._deferQuickFoulAnnounce = true;
  await commitQuickFoulReachInAndAnnounce(scene, {
    defenderSprite,
    victimSprite,
    ballSprite,
    turnDataForAnnounce: turnData,
    markTurnDone: turnData,
  });
}

/** @deprecated Use pickQuickFoulApproachPixels + commitQuickFoulReachInAndAnnounce */
export async function animateQuickFoulDefenderToReceiver(scene, defenderSprite, receiverSprite) {
  const target = pickQuickFoulApproachPixels(scene, defenderSprite, receiverSprite);
  if (!target) return;
  return tweenPlayerTo(scene, defenderSprite, target, { duration: 400, easing: 'Linear' });
}
