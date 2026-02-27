/**
 * Negative Action Effects - Visual feedback for fouls and turnovers
 *
 * Red tint / pulse / overlay effects were sunset. Announcements (e.g. "Shooting Foul!", "CHARGE!")
 * provide the visual feedback. These exports remain as no-ops so call sites need not change.
 */

export function triggerNegativeAction(scene, playerId, actionType = 'foul', skipScreenFlash = false) {
  // No-op: red tint and related effects removed by design
}

/**
 * Trigger foul effect for a player (no-op; announcements provide feedback)
 */
export function triggerFoulEffect(scene, playerId) {
  triggerNegativeAction(scene, playerId, 'foul');
}

/**
 * Clear red foul tint for a player (e.g. when they foul out and we show the foul-out popup).
 * No-op when tint is not used; kept for API compatibility with foul-out flow.
 */
export function clearFoulTintForPlayer(scene, playerId) {
  if (!playerId || !scene?.playerSprites) return;
  const sprite = scene.playerSprites[playerId];
  if (!sprite) return;
  if (sprite.type === 'Container') {
    sprite.list.forEach(child => {
      if (child.clearTint) child.clearTint();
    });
  } else if (sprite.clearTint) {
    sprite.clearTint();
  }
}

/**
 * Trigger turnover effect for a player (no-op; announcements provide feedback)
 */
export function triggerTurnoverEffect(scene, playerId) {
  triggerNegativeAction(scene, playerId, 'turnover');
}

/**
 * Trigger green flash for made shots (no-op; announcement containers provide feedback)
 * @param {boolean} hasAndOne - Unused (kept for API compatibility)
 */
export function triggerMadeShotFlash(scene, hasAndOne = false) {
  return;
}
