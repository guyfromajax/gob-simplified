import * as Phaser from 'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.esm.js';
import animationConfig from "./animation_config.js";

const BALL_DEPTH = 1000;
export const PASS_DEBUG = false;

/**
 * Position the ball sprite on top of a player's sprite and optionally adjust depth.
 * Any active tweens on the ball are killed before attaching.
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Image} ballSprite
 * @param {Phaser.GameObjects.Sprite} playerSprite
 * @param {{depth?: number}} opts
 */
export function attachBallToPlayer(scene, ballSprite, playerSprite, opts = {}) {
  if (!scene || !ballSprite || !playerSprite) return;
  scene.ballDetached = false;
  const depth = opts.depth ?? (playerSprite.depth != null ? playerSprite.depth + 1 : BALL_DEPTH);
  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  ballSprite.setPosition(playerSprite.x, playerSprite.y);
  ballSprite.setVisible(true);
  ballSprite.setDepth(depth);
  if (typeof playerSprite.playerId !== 'undefined') {
    scene.ballAttachedToPlayerId = playerSprite.playerId;
    scene.ballLastKnownOwnerId = playerSprite.playerId;
  } else if (scene.playerSprites) {
    for (const [pid, sprite] of Object.entries(scene.playerSprites)) {
      if (sprite === playerSprite) {
        scene.ballAttachedToPlayerId = pid;
        scene.ballLastKnownOwnerId = pid;
        break;
      }
    }
  }
}

/**
 * Detach ball from any player and optionally hide it.
 * Currently just clears active tweens and ownership reference.
 */
export function detachBall(scene, ballSprite) {
  if (!scene || !ballSprite) return;
  scene.ballDetached = true;
  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  if (typeof scene.ballAttachedToPlayerId !== 'undefined') {
    scene.ballAttachedToPlayerId = null;
  }
}

/**
 * Tween the ball to a specific position. Returns a promise that resolves when tween completes.
 * Supports optional arc motion via quadratic bezier.
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Image} ballSprite
 * @param {{x:number, y:number}} target
 * @param {{duration?:number, easing?:string, arc?:{height?:number}|boolean}} opts
 */
export function tweenBallTo(scene, ballSprite, target, opts = {}) {
  if (!scene || !ballSprite || !target) return Promise.resolve();
  const { duration = 300, easing = 'Linear', arc } = opts;
  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  ballSprite.setDepth(BALL_DEPTH);
  ballSprite.setVisible(true);

  return new Promise((resolve, reject) => {
    if (arc) {
      const startX = ballSprite.x;
      const startY = ballSprite.y;
      const controlX = (startX + target.x) / 2;
      const height = typeof arc === 'object' && arc.height ? arc.height : 50;
      const controlY = Math.min(startY, target.y) - height;
      const curve = new Phaser.Curves.QuadraticBezier(
        new Phaser.Math.Vector2(startX, startY),
        new Phaser.Math.Vector2(controlX, controlY),
        new Phaser.Math.Vector2(target.x, target.y)
      );
      const progress = { t: 0 };
      const tween = scene.tweens.add({
        targets: progress,
        t: 1,
        duration,
        ease: easing,
        onUpdate: () => {
          const p = curve.getPoint(progress.t);
          ballSprite.setPosition(p.x, p.y);
        },
        onComplete: resolve
      });
      tween?.once?.('stop', () => reject(new Error('tween stopped')));
    } else {
      const tween = scene.tweens.add({
        targets: ballSprite,
        x: target.x,
        y: target.y,
        duration,
        ease: easing,
        onComplete: resolve
      });
      tween?.once?.('stop', () => reject(new Error('tween stopped')));
    }
  });
}

/**
 * Execute a full pass animation between players or coordinates.
 * Uses scene.ballSprite and scene.playerSprites to resolve sprites by id.
 * @param {Phaser.Scene} scene
 * @param {{fromId?:string|number, toId?:string|number, startCoords?:{x:number,y:number}, endCoords?:{x:number,y:number}, duration?:number, easing?:string}} cfg
 */
export async function runPass(scene, cfg = {}) {
  if (!scene) return;
  const { fromId, toId, startCoords, endCoords, duration, easing } = cfg;
  const usedDuration = duration ?? 300;
  const usedEasing = easing ?? 'Linear';
  const ballSprite = scene.ballSprite;
  if (!ballSprite) return;
  const fromSprite = fromId != null ? scene.playerSprites?.[fromId] : null;
  const toSprite = toId != null ? scene.playerSprites?.[toId] : null;

  const frame = scene.game?.loop?.frame ?? 0;
  const key = `${fromId ?? ''}-${toId ?? ''}`;

  if (scene.__activePass && scene.__activePass.key === key && scene.__activePass.frame === frame) {
    if (PASS_DEBUG) console.log('duplicate runPass ignored', { fromId, toId, frame });
    return Promise.resolve();
  }

  if (scene.__activePass) {
    if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
    const lastId = scene.ballLastKnownOwnerId;
    const lastSprite = lastId != null ? scene.playerSprites?.[lastId] : null;
    if (lastSprite) {
      attachBallToPlayer(scene, ballSprite, lastSprite);
    }
    scene.__activePass.reject?.(new Error('pass cancelled'));
    scene.__activePass = null;
  }

  if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
  if (scene.ballDetached && scene.ballLastKnownOwnerId != null) {
    const owner = scene.playerSprites?.[scene.ballLastKnownOwnerId];
    if (owner) attachBallToPlayer(scene, ballSprite, owner);
  }

  let resolveFn, rejectFn;
  const promise = new Promise((resolve, reject) => {
    resolveFn = resolve;
    rejectFn = reject;
  });
  scene.__activePass = { key, frame, promise, reject: rejectFn };

  scene.passInFlight = true;
  scene.pendingBallOwnerId = toId;

  (async () => {
    try {
      scene.events?.emit('passStart', { fromId, toId, duration: usedDuration, easing: usedEasing });
      if (PASS_DEBUG) console.log('passStart', { fromId, toId, duration: usedDuration, easing: usedEasing });

      if (fromSprite) {
        attachBallToPlayer(scene, ballSprite, fromSprite);
        if (startCoords) {
          ballSprite.setPosition(startCoords.x, startCoords.y);
        }
      } else if (startCoords) {
        if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
        ballSprite.setPosition(startCoords.x, startCoords.y);
        ballSprite.setVisible(true);
        ballSprite.setDepth(BALL_DEPTH);
      }

      detachBall(scene, ballSprite);
      scene.ballDetached = true;
      scene.events?.emit('ballDetached');
      if (PASS_DEBUG) console.log('detach(A)', { fromId });

      const end = endCoords || (toSprite ? { x: toSprite.x, y: toSprite.y } : null);
      if (!end) {
        resolveFn();
        return;
      }

      const doTween = animationConfig.enableBallTween !== false;
      if (doTween) {
        scene.events?.emit('tweenStart', { fromId, toId, duration: usedDuration, easing: usedEasing });
        if (PASS_DEBUG) console.log('tweenStart', { fromId, toId, duration: usedDuration, easing: usedEasing });
        await tweenBallTo(scene, ballSprite, end, { duration: usedDuration, easing: usedEasing });
        scene.events?.emit('tweenEnd', { toId });
        if (PASS_DEBUG) console.log('tweenEnd', { toId });
      } else {
        scene.events?.emit('tweenStart', { fromId, toId, skipped: true });
        if (PASS_DEBUG) console.log('tweenStart', { fromId, toId, skipped: true });
        if (scene.tweens) scene.tweens.killTweensOf(ballSprite);
        ballSprite.setPosition(end.x, end.y);
        ballSprite.setVisible(true);
        ballSprite.setDepth(BALL_DEPTH);
        scene.events?.emit('tweenEnd', { toId, skipped: true });
        if (PASS_DEBUG) console.log('tweenEnd', { toId, skipped: true });
      }
      if (toSprite) {
        attachBallToPlayer(scene, ballSprite, toSprite);
        scene.ballDetached = false;
        scene.events?.emit('ballAttached', { toId });
        if (PASS_DEBUG) console.log('attach(B)', { toId });
      }

      scene.events?.emit('passEnd', { toId });
      if (PASS_DEBUG) console.log('passEnd', { toId });
      resolveFn();
    } catch (err) {
      const lastId = scene.ballLastKnownOwnerId;
      const lastSprite = lastId != null ? scene.playerSprites?.[lastId] : null;
      if (lastSprite) {
        attachBallToPlayer(scene, ballSprite, lastSprite);
      }
      rejectFn(err);
    } finally {
      if (scene.__activePass && scene.__activePass.key === key && scene.__activePass.frame === frame) {
        scene.__activePass = null;
        scene.passInFlight = false;
        scene.pendingBallOwnerId = null;
      }
    }
  })();

  return promise;
}

export default {
  attachBallToPlayer,
  detachBall,
  tweenBallTo,
  runPass
};
