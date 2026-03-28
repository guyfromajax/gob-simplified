import animationConfig from "./animation_config.js";

const HEARTBEAT_STORE_KEY = "__arrivalHeartbeatStore";

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

function resolveRole(scene, sprite) {
  const offenseTeamId = scene?.offenseTeamId;
  if (offenseTeamId != null && sprite?.team_id != null) {
    return String(sprite.team_id) === String(offenseTeamId) ? "offense" : "defense";
  }
  if (sprite?.team === "away") return "defense";
  return "offense";
}

function safeStopTween(tween) {
  try {
    if (!tween) return;
    if (typeof tween.stop === "function") tween.stop();
    else if (typeof tween.remove === "function") tween.remove();
  } catch (_) {
    // Visual-only; never throw.
  }
}

function restoreOrigin(sprite, state) {
  if (!sprite || sprite.active === false || sprite.destroyed || !state) return;
  if (Number.isFinite(state.displayOriginX)) sprite.displayOriginX = state.displayOriginX;
  if (Number.isFinite(state.displayOriginY)) sprite.displayOriginY = state.displayOriginY;
}

function isEntryLive(entry, sprite) {
  const tween = entry?.tween;
  if (!entry || entry.sprite !== sprite || !tween) return false;
  if (typeof tween.isPlaying === "function") return !!tween.isPlaying();
  if (typeof tween.isPlaying === "boolean") return tween.isPlaying;
  return true;
}

export function ensureConsistentHeartbeat(scene, sprites = null) {
  try {
    if (!scene?.tweens) return;

    const cfg = animationConfig.heartbeat || {};
    if (cfg.enabled === false) return;

    const spriteMap = sprites || scene.playerSprites;
    if (!spriteMap) return;

    const store = getStore(scene);
    const amplitudePx = Number.isFinite(cfg.amplitudePx) ? cfg.amplitudePx : 1.2;
    const minHalfMs = Number.isFinite(cfg.minHalfCycleMs) ? cfg.minHalfCycleMs : 170;
    const maxHalfMs = Number.isFinite(cfg.maxHalfCycleMs) ? cfg.maxHalfCycleMs : 520;
    const jitterPx = Number.isFinite(cfg.jitterPx) ? cfg.jitterPx : 0.2;

    const liveKeys = new Set();
    for (const sprite of Object.values(spriteMap)) {
      if (!sprite || sprite.active === false || sprite.destroyed) continue;
      const key = getSpriteKey(sprite);
      if (!key) continue;
      liveKeys.add(key);

      const existing = store.get(key);
      if (isEntryLive(existing, sprite)) continue;
      if (existing) {
        safeStopTween(existing.tween);
        restoreOrigin(existing.sprite, existing.baseState);
        store.delete(key);
      }

      const ng = resolveNg(scene, sprite);
      const halfCycleMs = Math.round(minHalfMs + (maxHalfMs - minHalfMs) * ng);
      const role = resolveRole(scene, sprite);
      const dir = role === "defense" ? { x: -1, y: 1 } : { x: 1, y: 1 };
      const jitter = (Math.random() * jitterPx * 2) - jitterPx;
      const delta = amplitudePx + jitter;
      const dx = delta * dir.x;
      const dy = delta * dir.y;

      const baseState = {
        displayOriginX: Number(sprite.displayOriginX),
        displayOriginY: Number(sprite.displayOriginY),
      };

      const tween = scene.tweens.add({
        targets: sprite,
        displayOriginX: baseState.displayOriginX + dx,
        displayOriginY: baseState.displayOriginY + dy,
        duration: halfCycleMs,
        ease: "Sine.easeInOut",
        yoyo: true,
        repeat: -1,
      });

      store.set(key, { sprite, tween, baseState });
    }

    // Cleanup entries for sprites no longer present.
    for (const [key, entry] of store.entries()) {
      if (liveKeys.has(key)) continue;
      safeStopTween(entry?.tween);
      restoreOrigin(entry?.sprite, entry?.baseState);
      store.delete(key);
    }
  } catch (_) {
    // Visual-only; never throw.
  }
}

export function stopAllArrivalHeartbeats(scene) {
  try {
    const store = getStore(scene);
    if (!store) return;
    for (const entry of store.values()) {
      safeStopTween(entry?.tween);
      restoreOrigin(entry?.sprite, entry?.baseState);
    }
    store.clear();
  } catch (_) {
    // Visual-only; never throw.
  }
}
