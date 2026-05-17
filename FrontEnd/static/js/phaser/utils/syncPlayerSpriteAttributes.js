/**
 * Keep sprite.attributes.AG (and NG) aligned with sim fatigue so AG-based movement matches engine rescaling.
 * Engine: attributes.AG ≈ floor(anchor_AG * NG). We mirror that using anchor from roster payload + per-turn NG from player_energy.
 */

import { USE_MARKER_V2_FEATURES } from "../setup/markerConfig.js";
import { drawStaminaArc } from "../setup/staminaRing.js";

const MOVEMENT_ANCHOR_KEY = "_agMovementAnchor";

/**
 * Call when creating sprites from sim roster player object.
 * @param {object} player - Backend player row (attributes may include anchor_AG, AG, NG)
 * @param {Phaser.GameObjects.Container} sprite - Player container
 */
export function attachMovementAttributeAnchor(player, sprite) {
  if (!player?.attributes || typeof player.attributes !== "object") return;
  const attrs = player.attributes;
  sprite.attributes = sprite.attributes ? { ...attrs } : { ...attrs };

  const anchorRaw = attrs.anchor_AG;
  if (anchorRaw != null) {
    const a = Number(anchorRaw);
    if (Number.isFinite(a)) {
      sprite[MOVEMENT_ANCHOR_KEY] = a;
      return;
    }
  }
  const ag = attrs.AG != null ? Number(attrs.AG) : null;
  const ng = attrs.NG != null ? Number(attrs.NG) : 1;
  if (ag != null && Number.isFinite(ag) && Number.isFinite(ng) && ng > 0) {
    sprite[MOVEMENT_ANCHOR_KEY] = ag / ng;
  }
}

/**
 * After each turn, apply NG from turn.player_energy and rescale AG on sprites (active lineup).
 * Also redraws the v2 marker's stamina ring when v2 features are enabled.
 * @param {Record<string, object>} playerSprites - id -> container
 * @param {Record<string, { NG?: number }>} playerEnergy - from turn.player_energy
 */
export function syncSpriteAttributesFromPlayerEnergy(playerSprites, playerEnergy) {
  if (!playerSprites || !playerEnergy || typeof playerEnergy !== "object") return;

  for (const [playerId, energyData] of Object.entries(playerEnergy)) {
    const sprite = playerSprites[playerId];
    if (!sprite || !energyData) continue;

    const ng = energyData.NG != null ? Number(energyData.NG) : NaN;
    if (!Number.isFinite(ng)) continue;

    const anchor = sprite[MOVEMENT_ANCHOR_KEY];
    if (Number.isFinite(Number(anchor))) {
      const newAg = Math.floor(Number(anchor) * ng);
      if (!sprite.attributes || typeof sprite.attributes !== "object") {
        sprite.attributes = {};
      } else {
        sprite.attributes = { ...sprite.attributes };
      }
      sprite.attributes.AG = newAg;
      sprite.attributes.NG = ng;
    }

    // v2 stamina ring redraw — guarded so v1/legacy markers (no staminaGfx) skip cleanly.
    if (USE_MARKER_V2_FEATURES && sprite.staminaGfx) {
      drawStaminaArc(sprite.staminaGfx, sprite.headR, ng);
    }
  }
}
