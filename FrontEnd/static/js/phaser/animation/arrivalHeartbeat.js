import animationConfig from "./animation_config.js";

const HEARTBEAT_STORE_KEY = "__arrivalHeartbeatStore";

const EXEMPT_RESULT_TYPES = new Set([
  "SIDE_INBOUND",
  "BASELINE_INBOUND",
  "FREE_THROW",
  "TIMEOUT",
]);

function getStore(scene) {
  if (!scene) return null;
  if (!scene[HEARTBEAT_STORE_KEY]) {
    scene[HEARTBEAT_STORE_KEY] = new Map();
  }
  return scene[HEARTBEAT_STORE_KEY];
}

function isTweenPlaying(tween) {
  if (!tween) return false;
  if (typeof tween.isPlaying === "function") return !!tween.isPlaying();
  return !!tween.isPlaying;
}

function normalizeNg(rawNg) {
  const value = Number(rawNg);
  if (!Number.isFinite(value)) return 1;
  return Math.max(0.01, Math.min(1, value));
}

function resolveNg(scene, sprite) {
  const fromSprite = sprite?.attributes?.NG;
  if (fromSprite != null) return normalizeNg(fromSprite);
  const fromScene = scene?.playerInfo?.[sprite?.playerId]?.attributes?.NG;
  return normalizeNg(fromScene);
}

function resolveResultType(scene, turnData) {
  return turnData?.result_type ?? scene?.currentTurnData?.result_type ?? null;
}

function resolveRole(scene, sprite, explicitRole = null) {
  if (explicitRole === "offense" || explicitRole === "defense") return explicitRole;
  const offenseTeamId = scene?.offenseTeamId;
  if (offenseTeamId != null && sprite?.team_id != null) {
    return String(sprite.team_id) === String(offenseTeamId) ? "offense" : "defense";
  }
  if (sprite?.team === "away") return "defense";
  return "offense";
}

function getSpriteKey(sprite) {
  return String(
    sprite?.playerId ??
      sprite?.name ??
      sprite?.texture?.key ??
      sprite?.id ??
      ""
  );
}

function canHeartbeat(scene, sprite, turnData, forceEnable) {
  if (!scene || !sprite || !scene.tweens) return false;
  if (scene.skipToEnd || sprite.active === false || sprite.destroyed) return false;

  const cfg = animationConfig.heartbeat || {};
  if (cfg.enabled === false) return false;
  if (forceEnable === true) return true;

  const resultType = resolveResultType(scene, turnData);
  return !EXEMPT_RESULT_TYPES.has(resultType);
}

function safelyStopTween(tween) {
  try {
    if (!tween) return;
    if (isTweenPlaying(tween) && typeof tween.stop === "function") {
      tween.stop();
      return;
    }
    if (typeof tween.remove === "function") {
      tween.remove();
      return;
    }
    if (typeof tween.stop === "function") {
      tween.stop();
    }
  } catch (_) {
    // Never allow visual-only heartbeat cleanup to disrupt gameplay.
  }
}

export function stopArrivalHeartbeat(scene, sprite) {
  try {
    const store = getStore(scene);
    if (!store || !sprite) return;

    const key = getSpriteKey(sprite);
    if (!key) return;

    const active = store.get(key);
    if (!active) return;

    safelyStopTween(active.tween);

    if (
      sprite.active !== false &&
      !sprite.destroyed &&
      Number.isFinite(active.anchorX) &&
      Number.isFinite(active.anchorY)
    ) {
      sprite.x = active.anchorX;
      sprite.y = active.anchorY;
    }

    store.delete(key);
  } catch (_) {
    // Never throw from heartbeat path.
  }
}

export function stopAllArrivalHeartbeats(scene) {
  try {
    const store = getStore(scene);
    if (!store) return;

    for (const active of store.values()) {
      const sprite = active?.sprite;
      safelyStopTween(active?.tween);

      if (
        sprite &&
        sprite.active !== false &&
        !sprite.destroyed &&
        Number.isFinite(active.anchorX) &&
        Number.isFinite(active.anchorY)
      ) {
        sprite.x = active.anchorX;
        sprite.y = active.anchorY;
      }
    }

    store.clear();
  } catch (_) {
    // Never throw from heartbeat path.
  }
}

export function startArrivalHeartbeat(
  scene,
  sprite,
  { turnData = null, role = null, forceEnable = false } = {}
) {
  try {
    if (!canHeartbeat(scene, sprite, turnData, forceEnable)) return null;

    stopArrivalHeartbeat(scene, sprite);

    const cfg = animationConfig.heartbeat || {};
    const ng = resolveNg(scene, sprite);
    const minHalfMs = Number.isFinite(cfg.minHalfCycleMs) ? cfg.minHalfCycleMs : 160;
    const maxHalfMs = Number.isFinite(cfg.maxHalfCycleMs) ? cfg.maxHalfCycleMs : 520;
    const amplitudePx = Number.isFinite(cfg.amplitudePx) ? cfg.amplitudePx : 2.1;
    const jitterPx = Number.isFinite(cfg.jitterPx) ? cfg.jitterPx : 0.2;

    const halfCycleMs = Math.round(minHalfMs + (maxHalfMs - minHalfMs) * ng);
    const jitter = (Math.random() * jitterPx * 2) - jitterPx;

    const roleResolved = resolveRole(scene, sprite, role);
    const dir = roleResolved === "defense" ? { x: -1, y: 1 } : { x: 1, y: 1 };
    const dx = (amplitudePx + jitter) * dir.x;
    const dy = (amplitudePx + jitter) * dir.y;

    const anchorX = sprite.x;
    const anchorY = sprite.y;

    const tween = scene.tweens.add({
      targets: sprite,
      x: anchorX + dx,
      y: anchorY + dy,
      duration: halfCycleMs,
      ease: "Sine.easeInOut",
      yoyo: true,
      repeat: -1,
    });

    const key = getSpriteKey(sprite);
    if (!key) return tween;

    const store = getStore(scene);
    store?.set(key, { tween, anchorX, anchorY, sprite });
    return tween;
  } catch (_) {
    // Visual effect is optional; fail closed and continue gameplay.
    return null;
  }
}
