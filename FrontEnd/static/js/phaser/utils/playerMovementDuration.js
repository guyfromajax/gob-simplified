/**
 * Universal player movement duration: distance ÷ (AG-based px/s × game speed preset).
 * Single source of truth for run speed — use from tweenPlayerTo and turnAnimation.getPlayerDuration.
 * See _documentation_master/00_General_Systems/UESS_System.md §9.3
 */
import { getEffectiveAgilityForMovement, agToSpeedPxPerSec } from "./playerMovementSpeed.js";
import { getCurrentOwner } from "../animation/BallControllerAdapter.js";

const DEFAULT_GAME_SPEED_PX = 450;
const MIN_DURATION_MS = 50;

export function getGameSpeedPxPerSec() {
  if (typeof window !== "undefined" && window.__GAME_SPEED != null) {
    const v = Number(window.__GAME_SPEED);
    if (Number.isFinite(v) && v > 0) return v;
  }
  return DEFAULT_GAME_SPEED_PX;
}

function resolveIsBallHandler(sprite, opts = {}) {
  if (opts.isBallHandler === true || opts.isBallHandler === false) {
    return opts.isBallHandler;
  }
  const scene = sprite?.scene;
  const pid = sprite?.playerId ?? sprite?.player_id;
  if (!scene || pid == null) return false;
  const owner = getCurrentOwner(scene);
  return owner != null && String(owner) === String(pid);
}

/**
 * Per-player px/s from AG + ball-handler rule, scaled by global game speed (Slow/Normal/Fast).
 */
export function resolveMovementSpeedPxPerSec(sprite, opts = {}) {
  const isBH = resolveIsBallHandler(sprite, opts);
  const ag = getEffectiveAgilityForMovement(sprite, opts.scene ?? sprite?.scene);
  const base = agToSpeedPxPerSec(ag, { isBallHandler: isBH });
  return base * (getGameSpeedPxPerSec() / DEFAULT_GAME_SPEED_PX);
}

/**
 * Milliseconds to move from sprite's current position to target at AG-based speed.
 * @param {object} sprite - Phaser game object with x, y
 * @param {number} targetX
 * @param {number} targetY
 * @param {object} [opts]
 * @param {boolean} [opts.isBallHandler] - override BH detection
 * @param {import("phaser").Scene} [opts.scene]
 */
export function getPlayerMovementDurationMs(sprite, targetX, targetY, opts = {}) {
  if (!sprite || !Number.isFinite(targetX) || !Number.isFinite(targetY)) {
    return MIN_DURATION_MS;
  }
  const cx = Number(sprite.x);
  const cy = Number(sprite.y);
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return MIN_DURATION_MS;
  const speed = resolveMovementSpeedPxPerSec(sprite, opts);
  if (!speed || speed <= 0) return MIN_DURATION_MS;
  const distance = Math.hypot(targetX - cx, targetY - cy);
  if (distance < 1) return MIN_DURATION_MS;
  const duration = (distance / speed) * 1000;
  return Math.max(MIN_DURATION_MS, duration);
}
