import { animateMovementSequence } from "./animateMovementSequence.js";

/**
 * Plays a single possession (turn) by animating all players in parallel.
 * Resolves only after all animations finish.
 *
 * @param {object} scene - Phaser scene
 * @param {object} simData - Full simData including players
 * @param {object} playerSprites - Map of playerId → sprite
 * @param {object} turnData - One turn from simData.turns
 * @param {Phaser.GameObjects.Sprite} ballSprite - The shared ball sprite
 * @param {Function} onAction - Action callback (pass, shoot, etc.)
 */
export async function playTurnAnimation({ scene, simData, playerSprites, turnData, ballSprite, onAction }) {
  const promises = [];
  const currentBallOwnerRef = { value: null }; // ✅ shared mutable ref for frame-accurate ball tracking

  for (const anim of turnData.animations) {
    const sprite = playerSprites[anim.playerId];

    if (!sprite || !anim.movement || !anim.hasBallAtStep) {
      console.warn("⚠️ Skipping animation for missing sprite or data:", anim.playerId);
      continue;
    }

    const positionName =
      simData.players.find(p => p.playerId === anim.playerId)?.pos || "[unknown]";

      if (!ballSprite) {
        console.error("🚫 ballSprite not passed to animateMovementSequence");
      }      
    
      const promise = animateMovementSequence({
      scene,
      sprite,
      movement: anim.movement,
      hasBallAtStep: anim.hasBallAtStep,
      ballSprite,
      position: positionName,
      currentBallOwnerRef,
      onAction: (action, sprite, timestamp) => {
        if (onAction) onAction(action, sprite, timestamp);
      }
    });

    promises.push(promise);
  }

  await Promise.all(promises);
}
