// Flourishes — in-place "micro-movements" rendered in RENDER SPACE only.
//
// A flourish is a quick, character-level motion (a defender's reach-in steal
// attempt, a pump fake, a post-up rattle, ...) that the backend stamps onto a
// step (`step.start.flourish[playerId]`) and the FE renders WITHOUT ever
// touching the player's gameplay grid coords. The decision (steal / foul /
// nothing) lives entirely on the backend; this module only animates.
//
// Render-space contract (mirrors the arrival-heartbeat system):
//   - Player sprites are Phaser CONTAINERS. We move them visually by tweening
//     either the container's displayOrigin (when writable) or its child render
//     objects' local x/y — NEVER the container's gameplay x/y. So a flourish
//     can never leak into possession/boundary logic.
//   - The tween is tagged `__uessBoundaryIgnore = true` and (for the child case)
//     targets children the turn-boundary collector never inspects — so it never
//     gates step T or the turn boundary (see AnimationRouter._collectActiveBoundaryTweens).
//   - Fire-and-forget: callers do NOT await it.

import { animationConfig } from "./animation_config.js";

/**
 * Resolve a render-space move target for a sprite/container, mirroring
 * arrivalHeartbeat.resolveHeartbeatTarget but returning enough to translate the
 * WHOLE visual (origin mode moves the sprite; child mode moves every child).
 */
function resolveRenderTarget(sprite) {
  // Sprite-like: displayOrigin moves the whole rendered image.
  if (
    isWritable(sprite, "displayOriginX") &&
    isWritable(sprite, "displayOriginY")
  ) {
    return { mode: "origin", targets: [sprite] };
  }
  // Container-like: translate every child by the same local delta so the whole
  // marker (base, headshot, ring, name strip) lunges together.
  if (Array.isArray(sprite?.list) && sprite.list.length > 0) {
    const movable = sprite.list.filter(
      (c) => c && isWritable(c, "x") && isWritable(c, "y"),
    );
    if (movable.length) return { mode: "child_local", targets: movable };
  }
  return null;
}

function isWritable(target, prop) {
  if (!target) return false;
  let current = target;
  while (current) {
    const descriptor = Object.getOwnPropertyDescriptor(current, prop);
    if (descriptor) return Boolean(descriptor.set) || descriptor.writable === true;
    current = Object.getPrototypeOf(current);
  }
  return prop in target;
}

/** Pixel coords of the motion's target ("ball" only for now). */
function resolveTargetPoint(flourish, sprite, ballSprite) {
  const which = flourish?.target || "ball";
  if (which === "ball" && ballSprite) {
    return { x: ballSprite.x, y: ballSprite.y };
  }
  // Unsupported targets (rim/x/y) — no directional anchor yet; caller no-ops.
  return null;
}

/**
 * Render the reach_in flourish: a quick lunge of `sprite` toward the ball, then
 * a recover (yoyo). Render-space only.
 */
function runReachIn(scene, sprite, flourish, ballSprite) {
  const cfg = animationConfig.flourish?.reachIn || {};
  const targetPt = resolveTargetPoint(flourish, sprite, ballSprite);
  if (!targetPt) return;

  // Direction from the defender to the ball, in pixel space.
  const dxBall = targetPt.x - sprite.x;
  const dyBall = targetPt.y - sprite.y;
  const len = Math.hypot(dxBall, dyBall);
  if (!Number.isFinite(len) || len < 1e-3) return;
  const ux = dxBall / len;
  const uy = dyBall / len;

  // Amplitude: backend grid units (converted to px) override the FE default px.
  let ampPx = Number.isFinite(cfg.amplitudePx) ? cfg.amplitudePx : 11;
  if (Number.isFinite(flourish?.amplitude_grid)) {
    const width = scene.game?.config?.width;
    const height = scene.game?.config?.height;
    if (Number.isFinite(width) && Number.isFinite(height)) {
      const pxPerGrid = (width / 100 + height / 50) / 2;
      ampPx = flourish.amplitude_grid * pxPerGrid;
    }
  }

  const dx = ux * ampPx;
  const dy = uy * ampPx;
  const totalMs = Number.isFinite(flourish?.duration_ms)
    ? flourish.duration_ms
    : (Number.isFinite(cfg.durationMs) ? cfg.durationMs : 450);
  const ease = flourish?.ease || cfg.ease || "Back.easeOut";
  const halfMs = Math.max(1, totalMs / 2);

  const resolved = resolveRenderTarget(sprite);
  if (!resolved) return;

  let tweenProps;
  if (resolved.mode === "origin") {
    // displayOrigin offset is inverted: to move the sprite toward +x/+y,
    // DECREASE the origin. Relative tween yoyos back to the base origin.
    tweenProps = { displayOriginX: `-=${dx}`, displayOriginY: `-=${dy}` };
  } else {
    // child_local: translate every child by the same local delta toward the ball.
    tweenProps = { x: `+=${dx}`, y: `+=${dy}` };
  }

  const tween = scene.tweens.add({
    targets: resolved.targets,
    ...tweenProps,
    duration: halfMs,
    ease,
    yoyo: true,
    repeat: 0,
  });
  // Belt-and-suspenders: never let this gate the turn boundary (child tweens are
  // already invisible to the boundary collector, which only inspects containers).
  if (tween) tween.__uessBoundaryIgnore = true;
}

/**
 * Render a flourish. Dispatches by `flourish.kind`. Unknown / not-yet-rendered
 * kinds are accepted no-ops (placeholders). Visual-only — never throws.
 *
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Container} sprite   The player's sprite/container.
 * @param {import("./animationStepSchema.js").Flourish} flourish
 * @param {{ ballSprite?: Phaser.GameObjects.GameObject }} [opts]
 */
export function runFlourish(scene, sprite, flourish, opts = {}) {
  try {
    if (!scene?.tweens || !sprite || !flourish?.kind) return;
    if (sprite.active === false || sprite.destroyed) return;
    switch (flourish.kind) {
      case "reach_in":
        runReachIn(scene, sprite, flourish, opts.ballSprite);
        return;
      // pump_fake / bite / gather / rattle / shot_dip / dribble / pickup / dunk:
      // accepted-but-unrendered placeholders for now.
      default:
        return;
    }
  } catch (_) {
    // Visual-only; never throw into the playback loop.
  }
}
