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
import { playStealReachInSfx } from "../utils/gameSfx.js";
import { isPassInterception } from "../utils/announcements.js";
import { pixelsToGrid } from "../utils/gridToPixels.js";

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
function runReachIn(scene, sprite, flourish, ballSprite, turnData = null) {
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

  // Never stack reach-ins on the same sprite. Consecutive HCT contest moments can
  // re-fire on the same on-ball defender; overlapping yoyo tweens on the same
  // targets corrupt the "rest" position and leave the marker permanently offset.
  if (sprite.__reachInTween && sprite.__reachInTween.isPlaying?.()) return;

  const resolved = resolveRenderTarget(sprite);
  if (!resolved) return;

  // Steal cue: two quick clicks back-to-back, starting the instant the reach-in
  // begins. Skipped flourishes (overlap guard above) intentionally don't re-fire it.
  // On a pass-INTERCEPTION turn the only steal-family SFX is the "INTERCEPTION!"
  // announce voice — suppress the reach-in steal click so the two don't overlap.
  if (!isPassInterception(turnData)) {
    playStealReachInSfx(scene);
  }

  // Snapshot the base positions so we ALWAYS restore to them on complete OR stop
  // (a killed/interrupted relative tween otherwise leaves a residual offset — the
  // "stuck ghost" bug). Absolute restore is the safety net.
  let restore;
  let tweenProps;
  if (resolved.mode === "origin") {
    const baseOX = Number(sprite.displayOriginX);
    const baseOY = Number(sprite.displayOriginY);
    // displayOrigin offset is inverted: to move the sprite toward +x/+y, DECREASE
    // the origin.
    tweenProps = { displayOriginX: baseOX - dx, displayOriginY: baseOY - dy };
    restore = () => {
      sprite.displayOriginX = baseOX;
      sprite.displayOriginY = baseOY;
      sprite.__reachInTween = null;
    };
  } else {
    // child_local: translate every child by the same local delta toward the ball.
    // The masked photo's clip follows it (createHeadshotMarkerV2 syncs the mask to
    // photoChild), so the whole marker lunges coherently.
    const bases = resolved.targets.map((c) => ({ c, x: c.x, y: c.y }));
    tweenProps = { x: `+=${dx}`, y: `+=${dy}` };
    restore = () => {
      for (const b of bases) {
        b.c.x = b.x;
        b.c.y = b.y;
      }
      sprite.__reachInTween = null;
    };
  }

  const tween = scene.tweens.add({
    targets: resolved.targets,
    ...tweenProps,
    duration: halfMs,
    ease,
    yoyo: true,
    repeat: 0,
    onComplete: restore,
    onStop: restore,
  });
  // Belt-and-suspenders: never let this gate the turn boundary (child tweens are
  // already invisible to the boundary collector, which only inspects containers).
  if (tween) {
    tween.__uessBoundaryIgnore = true;
    sprite.__reachInTween = tween;
  } else {
    restore();
  }
  return tween;
}

/**
 * Awaitable reach-in flourish (for Quick Foul commit timing).
 */
export function awaitReachInFlourish(scene, sprite, ballSprite, turnData = null, flourish = {}) {
  return new Promise((resolve) => {
    if (!scene?.tweens || !sprite) {
      resolve();
      return;
    }
    const cfg = animationConfig.flourish?.reachIn || {};
    const targetPt = resolveTargetPoint({ target: 'ball', ...flourish }, sprite, ballSprite);
    if (!targetPt) {
      resolve();
      return;
    }
    const dxBall = targetPt.x - sprite.x;
    const dyBall = targetPt.y - sprite.y;
    const len = Math.hypot(dxBall, dyBall);
    if (!Number.isFinite(len) || len < 1e-3) {
      resolve();
      return;
    }
    const ux = dxBall / len;
    const uy = dyBall / len;
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
    const ease = flourish?.ease || cfg.ease || 'Back.easeOut';
    const halfMs = Math.max(1, totalMs / 2);

    if (sprite.__reachInTween && sprite.__reachInTween.isPlaying?.()) {
      resolve();
      return;
    }

    const resolved = resolveRenderTarget(sprite);
    if (!resolved) {
      resolve();
      return;
    }

    if (!isPassInterception(turnData)) {
      playStealReachInSfx(scene);
    }

    let restore;
    let tweenProps;
    if (resolved.mode === 'origin') {
      const baseOX = Number(sprite.displayOriginX);
      const baseOY = Number(sprite.displayOriginY);
      tweenProps = { displayOriginX: baseOX - dx, displayOriginY: baseOY - dy };
      restore = () => {
        sprite.displayOriginX = baseOX;
        sprite.displayOriginY = baseOY;
        sprite.__reachInTween = null;
      };
    } else {
      const bases = resolved.targets.map((c) => ({ c, x: c.x, y: c.y }));
      tweenProps = { x: `+=${dx}`, y: `+=${dy}` };
      restore = () => {
        for (const b of bases) {
          b.c.x = b.x;
          b.c.y = b.y;
        }
        sprite.__reachInTween = null;
      };
    }

    const tween = scene.tweens.add({
      targets: resolved.targets,
      ...tweenProps,
      duration: halfMs,
      ease,
      yoyo: true,
      repeat: 0,
      onComplete: () => {
        restore();
        resolve();
      },
      onStop: () => {
        restore();
        resolve();
      },
    });
    if (tween) {
      tween.__uessBoundaryIgnore = true;
      sprite.__reachInTween = tween;
    } else {
      restore();
      resolve();
    }
  });
}

function runRattle(scene, sprite, flourish) {
  const cfg = animationConfig.flourish?.rattle || {};
  const resolved = resolveRenderTarget(sprite);
  if (!resolved) return;

  const ampPx = Number.isFinite(flourish?.amplitude_grid)
    ? flourish.amplitude_grid * ((scene.game?.config?.width || 800) / 100)
    : (Number.isFinite(cfg.amplitudePx) ? cfg.amplitudePx : 4);
  const cycles = Number.isFinite(flourish?.cycles) ? flourish.cycles : (cfg.cycles || 3);
  const cycleMs = Number.isFinite(cfg.cycleMs) ? cfg.cycleMs : 120;
  const ease = flourish?.ease || cfg.ease || "Sine.easeInOut";

  let restore;
  let tweenProps;
  if (resolved.mode === "origin") {
    const baseOX = Number(sprite.displayOriginX);
    const baseOY = Number(sprite.displayOriginY);
    tweenProps = { displayOriginX: baseOX - ampPx, displayOriginY: baseOY };
    restore = () => {
      sprite.displayOriginX = baseOX;
      sprite.displayOriginY = baseOY;
    };
  } else {
    const bases = resolved.targets.map((c) => ({ c, x: c.x, y: c.y }));
    tweenProps = { x: `+=${ampPx}` };
    restore = () => {
      for (const b of bases) b.c.x = b.x;
    };
  }

  const tween = scene.tweens.add({
    targets: resolved.targets,
    ...tweenProps,
    duration: cycleMs,
    ease,
    yoyo: true,
    repeat: Math.max(0, cycles - 1),
    onComplete: restore,
    onStop: restore,
  });
  if (tween) tween.__uessBoundaryIgnore = true;
}

function runPumpFake(scene, sprite, flourish, ballSprite) {
  if (!ballSprite || !scene?.tweens) return;
  const cfg = animationConfig.flourish?.pumpFake || {};
  const width = scene.game?.config?.width;
  const height = scene.game?.config?.height;
  if (!Number.isFinite(width) || !Number.isFinite(height)) return;

  const amplitudeGrid = Number.isFinite(flourish?.amplitude_grid)
    ? flourish.amplitude_grid
    : (Number.isFinite(cfg.amplitudeGrid) ? cfg.amplitudeGrid : 2);
  const ampPx = amplitudeGrid * (height / 50);

  let shooterGridY = 25;
  if (sprite && Number.isFinite(sprite.x) && Number.isFinite(sprite.y)) {
    shooterGridY = pixelsToGrid(sprite.x, sprite.y, width, height).y;
  }
  const sign = shooterGridY > 25 ? 1 : -1;

  const durationMs = Number.isFinite(flourish?.duration_ms)
    ? flourish.duration_ms
    : (Number.isFinite(cfg.durationMs) ? cfg.durationMs : 380);
  const baseY = ballSprite.y;
  const tween = scene.tweens.add({
    targets: ballSprite,
    y: baseY + sign * ampPx,
    duration: durationMs / 2,
    ease: flourish?.ease || cfg.ease || "Quad.easeOut",
    yoyo: true,
    repeat: 0,
    onComplete: () => { ballSprite.y = baseY; },
    onStop: () => { ballSprite.y = baseY; },
  });
  if (tween) tween.__uessBoundaryIgnore = true;
}

function runGather(scene, sprite, flourish) {
  const cfg = animationConfig.flourish?.gather || {};
  const resolved = resolveRenderTarget(sprite);
  if (!resolved || !scene?.tweens) return;

  const height = scene.game?.config?.height || 768;
  const amplitudeGrid = Number.isFinite(flourish?.amplitude_grid)
    ? flourish.amplitude_grid
    : (Number.isFinite(cfg.amplitudeGrid) ? cfg.amplitudeGrid : 0.6);
  const ampPx = amplitudeGrid * (height / 50);
  const durationMs = Number.isFinite(flourish?.duration_ms)
    ? flourish.duration_ms
    : (Number.isFinite(cfg.durationMs) ? cfg.durationMs : 400);
  const ease = flourish?.ease || cfg.ease || "Quad.easeOut";

  let restore;
  let tweenProps;
  if (resolved.mode === "origin") {
    const baseOY = Number(sprite.displayOriginY);
    tweenProps = { displayOriginY: baseOY + ampPx * 0.35 };
    restore = () => { sprite.displayOriginY = baseOY; };
  } else {
    const bases = resolved.targets.map((c) => ({ c, y: c.y }));
    tweenProps = { y: `+=${ampPx * 0.35}` };
    restore = () => {
      for (const b of bases) b.c.y = b.y;
    };
  }

  const tween = scene.tweens.add({
    targets: resolved.mode === "origin" ? sprite : resolved.targets,
    ...tweenProps,
    duration: durationMs / 2,
    ease,
    yoyo: true,
    repeat: 0,
    onComplete: restore,
    onStop: restore,
  });
  if (tween) tween.__uessBoundaryIgnore = true;
}

function runBite(scene, sprite, flourish, ballSprite) {
  runReachIn(scene, sprite, { ...flourish, kind: "reach_in", target: "ball" }, ballSprite);
}

/**
 * Render a flourish. Dispatches by `flourish.kind`. Unknown / not-yet-rendered
 * kinds are accepted no-ops (placeholders). Visual-only — never throws.
 *
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Container} sprite   The player's sprite/container.
 * @param {import("./animationStepSchema.js").Flourish} flourish
 * @param {{ ballSprite?: Phaser.GameObjects.GameObject, turnData?: object }} [opts]
 *   `turnData` lets a flourish suppress its SFX on certain outcomes (e.g. the
 *   reach-in steal click is muted on a pass-interception turn).
 */
export function runFlourish(scene, sprite, flourish, opts = {}) {
  try {
    if (!scene?.tweens || !sprite || !flourish?.kind) return;
    if (sprite.active === false || sprite.destroyed) return;
    switch (flourish.kind) {
      case "reach_in":
        runReachIn(scene, sprite, flourish, opts.ballSprite, opts.turnData);
        return;
      case "pump_fake":
        runPumpFake(scene, sprite, flourish, opts.ballSprite);
        return;
      case "bite":
        runBite(scene, sprite, flourish, opts.ballSprite);
        return;
      case "rattle":
        runRattle(scene, sprite, flourish);
        return;
      case "gather":
        runGather(scene, sprite, flourish);
        return;
      case "shot_dip":
        runRattle(scene, sprite, { ...flourish, cycles: flourish.cycles || 1 });
        return;
      default:
        return;
    }
  } catch (_) {
    // Visual-only; never throw into the playback loop.
  }
}
