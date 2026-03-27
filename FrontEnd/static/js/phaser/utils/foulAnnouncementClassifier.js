/**
 * Shared foul announcement classification helpers.
 *
 * Intent:
 * - Bonus fouls are FOUL turns that can route to FREE_THROW, but still announce as FOUL.
 * - True "Shooting Foul!" announcements belong to shot-result turns (MISS path).
 */

function hasFreeThrowContinuation(turnData) {
  if (!turnData) return false;
  const hasFreeThrowsRemaining = (turnData.free_throws_remaining ?? 0) > 0;
  const nextPlayTypeIsFreeThrow = turnData.next_play_type === 'FREE_THROW';
  return hasFreeThrowsRemaining || nextPlayTypeIsFreeThrow;
}

export function isBonusFreeThrowFoulTurn(turnData) {
  return turnData?.result_type === 'FOUL' && hasFreeThrowContinuation(turnData);
}

export function isShotResultShootingFoulTurn(turnData) {
  return turnData?.result_type === 'MISS' && hasFreeThrowContinuation(turnData);
}

