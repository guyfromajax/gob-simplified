import animationConfig from "./animation_config.js";

const HEARTBEAT_STORE_KEY = "__arrivalHeartbeatTweens";

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

function getSpriteKey(sprite) {
  return String(
    sprite?.playerId ??
      sprite?.name ??
      sprite?.texture?.key ??
      sprite?.id ??
      ""
  );
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

function canHeartbeat(scene, sprite, turnData, forceEnable) {
  if (!scene || !sprite || !scene.tweens) return false;
  if (scene.skipToEnd || sprite.active === false || sprite.destroyed) return false;

  const cfg = animationConfig.heartbeat || {};
  if (cfg.enabled === false) return false;
  if (forceEnable === true) return true;

  const resultType = resolveResultType(scene, turnData);
  return !EXEMPT_RESULT_TYPES.has(resultType);
}

function safeStopTween(tween) {
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
    // Visual-only feature; never propagate heartbeat cleanup errors.
  }
}

function restoreSpriteVisualState(sprite, state) {
  if (!sprite || sprite.active === false || sprite.destroyed || !state) return;
  if (Number.isFinite(state.scaleX)) sprite.scaleX = state.scaleX;
  if (Number.isFinite(state.scaleY)) sprite.scaleY = state.scaleY;
  if (Number.isFinite(state.angle)) sprite.angle = state.angle;
}

export function stopArrivalHeartbeat(scene, sprite) {
  try {
    const store = getStore(scene);
    if (!store || !sprite) return;

    const key = getSpriteKey(sprite);
    if (!key) return;

    const active = store.get(key);
    if (!active) return;

    safeStopTween(active.tween);
    restoreSpriteVisualState(sprite, active.baseState);
    store.delete(key);
  } catch (_) {
    // Visual-only feature; never propagate heartbeat cleanup errors.
  }
}

export function stopAllArrivalHeartbeats(scene) {
  try {
    const store = getStore(scene);
    if (!store) return;

    for (const active of store.values()) {
      safeStopTween(active?.tween);
      restoreSpriteVisualState(active?.sprite, active?.baseState);
    }

    store.clear();
  } catch (_) {
    // Visual-only feature; never propagate heartbeat cleanup errors.
  }
}

export function startArrivalHeartbeat(
  scene,
  sprite,
  { turnData = null, forceEnable = false } = {}
) {
  try {
    if (!canHeartbeat(scene, sprite, turnData, forceEnable)) return null;

    stopArrivalHeartbeat(scene, sprite);

    const cfg = animationConfig.heartbeat || {};
    const ng = resolveNg(scene, sprite);
    const minHalfMs = Number.isFinite(cfg.minHalfCycleMs) ? cfg.minHalfCycleMs : 170;
    const maxHalfMs = Number.isFinite(cfg.maxHalfCycleMs) ? cfg.maxHalfCycleMs : 520;
    const scaleDelta = Number.isFinite(cfg.scaleDelta) ? cfg.scaleDelta : 0.02;
    const angleDeltaDeg = Number.isFinite(cfg.angleDeltaDeg) ? cfg.angleDeltaDeg : 1.2;

    const halfCycleMs = Math.round(minHalfMs + (maxHalfMs - minHalfMs) * ng);
    const baseState = {
      scaleX: Number(sprite.scaleX),
      scaleY: Number(sprite.scaleY),
      angle: Number(sprite.angle),
    };

    const tween = scene.tweens.add({
      targets: sprite,
      scaleX: baseState.scaleX * (1 + scaleDelta),
      scaleY: baseState.scaleY * (1 - scaleDelta),
      angle: baseState.angle + angleDeltaDeg,
      duration: halfCycleMs,
      ease: "Sine.easeInOut",
      yoyo: true,
      repeat: -1,
    });

    const key = getSpriteKey(sprite);
    if (!key) return tween;
    getStore(scene)?.set(key, { tween, sprite, baseState });
    return tween;
  } catch (_) {
    // Visual-only feature; fail closed.
    return null;
  }
}
