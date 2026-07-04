// Dunk micro-beat playback — render-space rise + ball slam + camera rim rattle.
// Backend stamps `advance_trigger.metadata.micro_beat_kind === "dunk"`.

import { gridToPixels } from "../utils/gridToPixels.js";
import { animationConfig } from "./animation_config.js";
import { playGameSfx } from "../utils/gameSfx.js";
import {
  waitMsRespectingPause,
  waitWhileUserPaused,
  shouldFastForwardPlayback,
} from "./playbackPause.js";

function easeOut(t) {
  const x = Math.max(0, Math.min(1, t));
  return 1 - (1 - x) * (1 - x);
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

function resolveRenderTarget(sprite) {
  if (
    isWritable(sprite, "displayOriginX") &&
    isWritable(sprite, "displayOriginY")
  ) {
    return { mode: "origin", targets: [sprite] };
  }
  if (Array.isArray(sprite?.list) && sprite.list.length > 0) {
    const movable = sprite.list.filter(
      (c) => c && isWritable(c, "x") && isWritable(c, "y"),
    );
    if (movable.length) return { mode: "child_local", targets: movable };
  }
  return null;
}

function playerDisplayHeight(sprite) {
  if (!sprite) return 48;
  if (Number.isFinite(sprite.displayHeight) && sprite.displayHeight > 0) {
    return sprite.displayHeight;
  }
  const bounds = sprite.getBounds?.();
  if (bounds && Number.isFinite(bounds.height) && bounds.height > 0) {
    return bounds.height;
  }
  return 48;
}

function spriteTopY(sprite) {
  const h = playerDisplayHeight(sprite);
  const originY = Number.isFinite(sprite.originY) ? sprite.originY : 0.5;
  return sprite.y - h * originY;
}

function resolveShooterId(step) {
  const actions = step?.start?.action || {};
  for (const [playerId, action] of Object.entries(actions)) {
    if (action === "shoot") return String(playerId);
  }
  return null;
}

function readDunkConfig(meta) {
  const cfg = animationConfig.dunk || {};
  return {
    risePx: Number.isFinite(meta?.dunk_rise_px) ? meta.dunk_rise_px : (cfg.risePx ?? 22),
    rattleMagPx: Number.isFinite(meta?.dunk_rattle_mag_px)
      ? meta.dunk_rattle_mag_px
      : (cfg.rattleMagPx ?? 6),
    rattleMs: Number.isFinite(meta?.dunk_rattle_ms)
      ? meta.dunk_rattle_ms
      : (cfg.rattleMs ?? 280),
    ballRaise: Number.isFinite(meta?.dunk_ball_raise)
      ? meta.dunk_ball_raise
      : (cfg.ballRaise ?? 0.35),
  };
}

function triggerDunkRimRattle(scene, magPx, durationMs) {
  const cam = scene?.cameras?.main;
  if (!cam || !Number.isFinite(magPx) || magPx <= 0) return;

  const baseScrollX = cam.scrollX;
  const baseScrollY = cam.scrollY;
  const startedAt = scene.time?.now ?? performance.now();
  const totalMs = Math.max(1, durationMs);

  const cleanup = () => {
    cam.setScroll(baseScrollX, baseScrollY);
    scene.events?.off?.("update", onUpdate);
  };

  const onUpdate = () => {
    const now = scene.time?.now ?? performance.now();
    const elapsed = now - startedAt;
    if (elapsed >= totalMs) {
      cleanup();
      return;
    }
    const remaining = totalMs - elapsed;
    const shakeMag = magPx * Math.max(0, remaining / totalMs);
    cam.setScroll(
      baseScrollX + (Math.random() * 2 - 1) * shakeMag,
      baseScrollY + (Math.random() * 2 - 1) * shakeMag,
    );
  };

  scene.events?.on?.("update", onUpdate);
}

function applyRenderOffset(resolved, offsetX, offsetY, bases) {
  if (!resolved) return;
  if (resolved.mode === "origin") {
    const sprite = resolved.targets[0];
    sprite.displayOriginX = bases.originX - offsetX;
    sprite.displayOriginY = bases.originY + offsetY;
    return;
  }
  for (const b of bases.childBases) {
    b.c.x = b.x + offsetX;
    b.c.y = b.y + offsetY;
  }
}

function captureRenderBases(resolved, sprite) {
  if (!resolved) return null;
  if (resolved.mode === "origin") {
    return {
      mode: "origin",
      originX: Number(sprite.displayOriginX),
      originY: Number(sprite.displayOriginY),
    };
  }
  return {
    mode: "child_local",
    childBases: resolved.targets.map((c) => ({ c, x: c.x, y: c.y })),
  };
}

function restoreRenderBases(resolved, bases) {
  if (!resolved || !bases) return;
  if (bases.mode === "origin") {
    resolved.targets[0].displayOriginX = bases.originX;
    resolved.targets[0].displayOriginY = bases.originY;
    return;
  }
  for (const b of bases.childBases) {
    b.c.x = b.x;
    b.c.y = b.y;
  }
}

export function isDunkMicroBeatStep(step) {
  return step?.start?.advance_trigger?.metadata?.micro_beat_kind === "dunk";
}

export async function playDunkMicroBeat(scene, step, sprites, ballSprite, options = {}) {
  const meta = step?.start?.advance_trigger?.metadata || {};
  const width = scene.game?.config?.width;
  const height = scene.game?.config?.height;
  const shooterId = resolveShooterId(step);
  const shooterSprite = shooterId ? sprites[shooterId] : null;

  if (!scene || !step || !shooterSprite || !width || !height) {
    return step?.end?.next ?? null;
  }

  await waitWhileUserPaused(scene);
  if (shouldFastForwardPlayback(scene)) {
    return step.end?.next ?? null;
  }

  const durationMs = Math.max(
    50,
    Math.round(
      meta.wall_clock_hold_ms
      ?? step.end?.time_elapsed * (scene?.gameClock?.getState?.().tickMs || 350)
      ?? 640,
    ),
  );
  const yieldBeforeSlam = meta.yield_before_slam === true;
  const effectiveDurationMs = yieldBeforeSlam ? Math.round(durationMs * 0.5) : durationMs;

  const startCoord = step.start?.coords?.[shooterId];
  const approachCoord = meta.approach_coord || step.end?.coords?.[shooterId];
  const resolveCoord = meta.resolve_coord || approachCoord;
  if (!startCoord || !approachCoord) {
    return step.end?.next ?? null;
  }

  const startPx = gridToPixels(startCoord.x, startCoord.y, width, height);
  const approachPx = gridToPixels(approachCoord.x, approachCoord.y, width, height);
  const resolvePx = resolveCoord
    ? gridToPixels(resolveCoord.x, resolveCoord.y, width, height)
    : approachPx;

  const dunkCfg = readDunkConfig(meta);
  const resolved = resolveRenderTarget(shooterSprite);
  const renderBases = captureRenderBases(resolved, shooterSprite);

  const flourishMap = step.start?.flourish;
  if (flourishMap && typeof flourishMap === "object") {
    import("./flourishes.js")
      .then(({ runFlourish }) => {
        for (const [playerId, flourish] of Object.entries(flourishMap)) {
          const sprite = sprites[playerId];
          if (!sprite || !flourish) continue;
          runFlourish(scene, sprite, flourish, {
            ballSprite,
            turnData: options.turnData,
            stepDurationMs: effectiveDurationMs,
          });
        }
      })
      .catch(() => {});
  }

  let rattleTriggered = false;
  let arrivalSfxPlayed = false;
  const arrivalSfx = step.start?.sfx_on_ball_arrival;
  const startedAt = performance.now();

  const stepFrame = async () => {
    await waitWhileUserPaused(scene);
    if (shouldFastForwardPlayback(scene)) return false;

    const elapsed = performance.now() - startedAt;
    const p = Math.min(1, elapsed / effectiveDurationMs);

    const approachT = Math.min(1, p / 0.55);
    const px = startPx.x + (approachPx.x - startPx.x) * approachT;
    const py = startPx.y + (approachPx.y - startPx.y) * approachT;
    shooterSprite.setPosition(px, py);

    const displayH = playerDisplayHeight(shooterSprite);
    const cockedBallY = spriteTopY(shooterSprite) - dunkCfg.ballRaise * displayH;

    let risePx = 0;
    let ballX = px;
    let ballY = cockedBallY;

    if (p < 0.5) {
      risePx = -dunkCfg.risePx * easeOut(p / 0.5);
    } else if (!yieldBeforeSlam) {
      const dp = (p - 0.5) / 0.5;
      risePx = -dunkCfg.risePx * (1 - easeOut(dp));
      ballX = approachPx.x + (resolvePx.x - approachPx.x) * easeOut(dp);
      ballY = cockedBallY + (resolvePx.y - cockedBallY) * easeOut(dp);
      if (!rattleTriggered) {
        rattleTriggered = true;
        triggerDunkRimRattle(scene, dunkCfg.rattleMagPx, dunkCfg.rattleMs);
        if (arrivalSfx?.file && !arrivalSfxPlayed) {
          arrivalSfxPlayed = true;
          playGameSfx(
            scene,
            arrivalSfx.file,
            typeof arrivalSfx.volume === "number" ? arrivalSfx.volume : 0.7,
            { event: arrivalSfx.event || "ball_arrival" },
          );
        }
      }
    }

    applyRenderOffset(resolved, 0, risePx, renderBases);

    if (ballSprite) {
      ballSprite.setVisible(true);
      ballSprite.setPosition(ballX, ballY);
    }

    if (p >= 1) return false;
    return true;
  };

  while (await stepFrame()) {
    await new Promise((resolve) => {
      scene.time?.delayedCall?.(16, resolve) ?? setTimeout(resolve, 16);
    });
  }

  restoreRenderBases(resolved, renderBases);

  const endCoord = step.end?.coords?.[shooterId] || approachCoord;
  const endPx = gridToPixels(endCoord.x, endCoord.y, width, height);
  shooterSprite.setPosition(endPx.x, endPx.y);
  shooterSprite.gridX = endCoord.x;
  shooterSprite.gridY = endCoord.y;

  if (ballSprite) {
    const endBall = step.end?.ball;
    if (endBall?.coords) {
      const bpx = gridToPixels(endBall.coords.x, endBall.coords.y, width, height);
      ballSprite.setPosition(bpx.x, bpx.y);
    } else if (endBall?.owner_player_id) {
      ballSprite.setPosition(endPx.x, endPx.y);
    }
  }

  const remainingMs = Math.max(0, effectiveDurationMs - (performance.now() - startedAt));
  if (remainingMs > 0) {
    await waitMsRespectingPause(scene, remainingMs);
  }

  return step.end?.next ?? null;
}
