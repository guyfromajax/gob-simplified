/**
 * AG → movement speed (px/s) for player tweens. Pure helpers + agility lookup.
 * See docs/docs_1_systems/05_Animation_System/AG_Implementation.md.
 */

/** Linear intercept: speed at AG 0 before global game-speed scale */
export const MOVEMENT_SPEED_BASE = 400;

/** Linear slope: +1 px/s per AG point (AG 50 → 450 px/s before BH / global scale) */
export const MOVEMENT_SPEED_SLOPE = 1;

export const DEFAULT_AG_WHEN_MISSING = 50;

/** v1 ball-handler movement penalty */
export const BALL_HANDLER_SPEED_MULTIPLIER = 0.95;

function normId(id) {
  return id != null ? String(id) : null;
}

/**
 * Map agility to pixels/second (before multiplying by global game speed).
 * @param {number} ag - Effective in-game AG (anchor × NG on backend).
 * @param {{ isBallHandler?: boolean }} [opts]
 */
export function agToSpeedPxPerSec(ag, opts = {}) {
  const n = Number(ag);
  const safeAg = Number.isFinite(n) ? n : DEFAULT_AG_WHEN_MISSING;
  let v = MOVEMENT_SPEED_BASE + MOVEMENT_SPEED_SLOPE * safeAg;
  if (opts.isBallHandler) {
    v *= BALL_HANDLER_SPEED_MULTIPLIER;
  }
  return Math.max(1, v);
}

/**
 * Effective AG from sprite and/or scene roster (post-rescale attributes.AG).
 * @param {object} sprite - Phaser container with optional .attributes.AG, .playerId
 * @param {object} [scene] - Phaser scene with simData.players; defaults to sprite.scene
 */
export function getEffectiveAgilityForMovement(sprite, scene) {
  const sc = scene ?? sprite?.scene;
  if (sprite?.attributes && sprite.attributes.AG != null) {
    const v = Number(sprite.attributes.AG);
    if (Number.isFinite(v)) return v;
  }
  const sid = normId(sprite?.playerId ?? sprite?.player_id);
  const players = sc?.simData?.players;
  if (sid && Array.isArray(players)) {
    for (const p of players) {
      const pid = normId(p.playerId ?? p.player_id);
      if (pid !== sid) continue;
      const raw = p.attributes?.AG ?? p.AG;
      if (raw != null) {
        const v = Number(raw);
        if (Number.isFinite(v)) return v;
      }
      break;
    }
  }
  return DEFAULT_AG_WHEN_MISSING;
}

/**
 * Base px/s for this sprite (AG + BH rule only; multiply by global game speed in caller).
 */
export function resolvePlayerBaseSpeedPxPerSec(sprite, opts = {}) {
  const ag = getEffectiveAgilityForMovement(sprite, opts.scene);
  return agToSpeedPxPerSec(ag, { isBallHandler: opts.isBallHandler });
}
