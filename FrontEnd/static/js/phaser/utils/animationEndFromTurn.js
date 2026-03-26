/**
 * Read per-player end coordinates from turn.animations (sim animator output, HOME grid).
 * Used by fast break (and similar) so the client tweens to the same spot the backend chose.
 */

function clampGridX(x) {
  return Math.max(4, Math.min(97, x));
}

function clampGridY(y) {
  return Math.max(1, Math.min(49, y));
}

/**
 * @param {object} turnData - Turn payload with optional animations[]
 * @param {string|number} playerId
 * @returns {{ x: number, y: number } | null}
 */
export function getAnimationEndGridForPlayer(turnData, playerId) {
  if (playerId == null || !turnData?.animations?.length) return null;
  const want = String(playerId);
  for (const anim of turnData.animations) {
    const pid = anim?.playerId != null ? String(anim.playerId) : null;
    if (pid !== want) continue;
    const end = anim.end;
    if (end && typeof end.x === "number" && typeof end.y === "number") {
      return { x: clampGridX(end.x), y: clampGridY(end.y) };
    }
    const mov = anim.movement;
    if (Array.isArray(mov) && mov.length) {
      const last = mov[mov.length - 1]?.coords;
      if (last && typeof last.x === "number" && typeof last.y === "number") {
        return { x: clampGridX(last.x), y: clampGridY(last.y) };
      }
    }
    return null;
  }
  return null;
}
