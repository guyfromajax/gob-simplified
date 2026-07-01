import animationConfig from "./animation_config.js";

const HEARTBEAT_STORE_KEY = "__arrivalHeartbeatStore";

// Deterministic PRNG (mulberry32) — a backend-provided `seed` reproduces the exact
// same idle-wander path on every render (SS&S-reproducible), even though the motion
// is cosmetic. Used by applyIdleWander below.
function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

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

function resolveHeartbeatBpm(ng, cfg) {
  const minBpm = Number.isFinite(cfg?.minBpm) ? cfg.minBpm : 75;
  const maxBpm = Number.isFinite(cfg?.maxBpm) ? cfg.maxBpm : 750;
  const clampedMin = Math.max(1, minBpm);
  const clampedMax = Math.max(clampedMin, maxBpm);
  const normalizedNg = (ng - 0.01) / 0.99; // 0 at NG=0.01, 1 at NG=1.0
  return clampedMax + (clampedMin - clampedMax) * normalizedNg;
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

function isWritableProperty(target, prop) {
  if (!target) return false;
  let current = target;
  while (current) {
    const descriptor = Object.getOwnPropertyDescriptor(current, prop);
    if (descriptor) {
      if (descriptor.set) return true;
      if (descriptor.writable === true) return true;
      return false;
    }
    current = Object.getPrototypeOf(current);
  }
  return prop in target;
}

function resolveHeartbeatTarget(sprite) {
  // Sprite-like objects: use display origin when writable.
  if (
    isWritableProperty(sprite, "displayOriginX") &&
    isWritableProperty(sprite, "displayOriginY")
  ) {
    return {
      target: sprite,
      mode: "origin",
      xProp: "displayOriginX",
      yProp: "displayOriginY",
      baseX: Number(sprite.displayOriginX),
      baseY: Number(sprite.displayOriginY),
    };
  }

  // Container-like objects: use the first render child's local x/y.
  const firstChild =
    Array.isArray(sprite?.list) && sprite.list.length > 0 ? sprite.list[0] : null;
  if (
    firstChild &&
    isWritableProperty(firstChild, "x") &&
    isWritableProperty(firstChild, "y")
  ) {
    return {
      target: firstChild,
      mode: "child_local",
      xProp: "x",
      yProp: "y",
      baseX: Number(firstChild.x),
      baseY: Number(firstChild.y),
    };
  }

  // Last-resort fallback (non-movement visual pulse).
  if (
    isWritableProperty(sprite, "scaleX") &&
    isWritableProperty(sprite, "scaleY")
  ) {
    return {
      target: sprite,
      mode: "scale",
      xProp: "scaleX",
      yProp: "scaleY",
      baseX: Number(sprite.scaleX),
      baseY: Number(sprite.scaleY),
    };
  }
  return null;
}

function restoreTargetState(entry) {
  const target = entry?.target;
  const state = entry?.baseState;
  if (!target || !state) return;
  if (Number.isFinite(state.x)) target[entry.xProp] = state.x;
  if (Number.isFinite(state.y)) target[entry.yProp] = state.y;
}

function isEntryLive(entry, sprite) {
  const tween = entry?.tween;
  if (!entry || entry.sprite !== sprite || !tween) return false;
  if (typeof tween.isPlaying === "function") return !!tween.isPlaying();
  if (typeof tween.isPlaying === "boolean") return tween.isPlaying;
  return true;
}

// Create (or replace) the persistent NG-driven heartbeat tween for one sprite and
// register it in the store. Extracted so applyIdleWander can re-establish the normal
// heartbeat from true rest after a wander completes.
function startHeartbeatForSprite(scene, sprite) {
  const cfg = animationConfig.heartbeat || {};
  if (cfg.enabled === false) return null;
  if (!scene?.tweens || !sprite || sprite.active === false || sprite.destroyed) return null;
  const store = getStore(scene);
  const key = getSpriteKey(sprite);
  if (!key) return null;

  const amplitudePx = Number.isFinite(cfg.amplitudePx) ? cfg.amplitudePx : 1.2;
  const jitterPx = Number.isFinite(cfg.jitterPx) ? cfg.jitterPx : 0.2;
  const ng = resolveNg(scene, sprite);
  const bpm = resolveHeartbeatBpm(ng, cfg);
  const halfCycleMs = Math.max(20, Math.round(30000 / bpm));
  const role = resolveRole(scene, sprite);
  const dir = role === "defense" ? { x: -1, y: 1 } : { x: 1, y: 1 };
  const jitter = (Math.random() * jitterPx * 2) - jitterPx;
  const delta = amplitudePx + jitter;
  const dx = delta * dir.x;
  const dy = delta * dir.y;

  const resolved = resolveHeartbeatTarget(sprite);
  if (!resolved) return null;

  const baseState = { x: resolved.baseX, y: resolved.baseY };

  const tweenProps = {};
  if (resolved.mode === "scale") {
    // Keep fallback subtle and centered around current shape.
    tweenProps[resolved.xProp] = baseState.x * (1 + (delta * 0.015));
    tweenProps[resolved.yProp] = baseState.y * (1 - (delta * 0.015));
  } else {
    tweenProps[resolved.xProp] = baseState.x + dx;
    tweenProps[resolved.yProp] = baseState.y + dy;
  }

  const tween = scene.tweens.add({
    targets: resolved.target,
    ...tweenProps,
    duration: halfCycleMs,
    ease: "Sine.easeInOut",
    yoyo: true,
    repeat: -1,
  });
  if (tween) tween.__uessBoundaryIgnore = true;

  const entry = {
    sprite,
    target: resolved.target,
    mode: resolved.mode,
    xProp: resolved.xProp,
    yProp: resolved.yProp,
    tween,
    baseState,
  };
  store.set(key, entry);
  return entry;
}

export function ensureConsistentHeartbeat(scene, sprites = null) {
  try {
    if (!scene?.tweens) return;

    const cfg = animationConfig.heartbeat || {};
    if (cfg.enabled === false) return;

    const spriteMap = sprites || scene.playerSprites;
    if (!spriteMap) return;

    const store = getStore(scene);

    const liveKeys = new Set();
    for (const sprite of Object.values(spriteMap)) {
      if (!sprite || sprite.active === false || sprite.destroyed) continue;
      const key = getSpriteKey(sprite);
      if (!key) continue;
      liveKeys.add(key);

      const existing = store.get(key);
      // A live entry — normal heartbeat OR an active idle-wander (which owns the
      // sprite's render offset for the beat) — is left untouched.
      if (isEntryLive(existing, sprite)) continue;
      if (existing) {
        safeStopTween(existing.tween);
        restoreTargetState(existing);
        store.delete(key);
      }

      startHeartbeatForSprite(scene, sprite);
    }

    // Cleanup entries for sprites no longer present.
    for (const [key, entry] of store.entries()) {
      if (liveKeys.has(key)) continue;
      safeStopTween(entry?.tween);
      restoreTargetState(entry);
      store.delete(key);
    }
  } catch (_) {
    // Visual-only; never throw.
  }
}

// Resolve a WHOLE-marker render-space mover (unlike resolveHeartbeatTarget, which moves
// only one child): displayOrigin when sprite-like, else every movable child translated
// together so the marker never splits. Bases are captured at call time — the caller must
// ensure the sprite is at true rest first. Direction is irrelevant for organic drift, so
// offsets are applied as base + offset uniformly.
function resolveWanderTargets(sprite) {
  if (
    isWritableProperty(sprite, "displayOriginX") &&
    isWritableProperty(sprite, "displayOriginY")
  ) {
    const baseOX = Number(sprite.displayOriginX);
    const baseOY = Number(sprite.displayOriginY);
    return {
      apply: (ox, oy) => {
        sprite.displayOriginX = baseOX + ox;
        sprite.displayOriginY = baseOY + oy;
      },
      restore: () => {
        sprite.displayOriginX = baseOX;
        sprite.displayOriginY = baseOY;
      },
    };
  }
  if (Array.isArray(sprite?.list) && sprite.list.length > 0) {
    const movable = sprite.list.filter(
      (c) => c && isWritableProperty(c, "x") && isWritableProperty(c, "y"),
    );
    if (movable.length) {
      const bases = movable.map((c) => ({ c, x: c.x, y: c.y }));
      return {
        apply: (ox, oy) => {
          for (const b of bases) {
            b.c.x = b.x + ox;
            b.c.y = b.y + oy;
          }
        },
        restore: () => {
          for (const b of bases) {
            b.c.x = b.x;
            b.c.y = b.y;
          }
        },
      };
    }
  }
  return null;
}

/**
 * Idle wander — a slow, organic render-space drift within a small radius, spanning the
 * beat, that RIDES THE HEARTBEAT SYSTEM instead of competing with it. It takes ownership
 * of the sprite's idle render offset for `durationMs` (stopping the normal heartbeat and
 * snapping to true rest first, so there is exactly one writer), then re-establishes the
 * normal heartbeat from that same rest. Single-owner ⇒ no residual "ghost" offset. Fully
 * determined by `opts.seed` (SS&S-reproducible). Cosmetic only — never touches gameplay
 * coords or the turn boundary. Universal: any "pause with real motion" step can call it.
 *
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Container} sprite
 * @param {{ seed?: number, radiusGrid?: number, durationMs?: number }} opts
 */
export function applyIdleWander(scene, sprite, opts = {}) {
  try {
    if (!scene?.tweens || !sprite || sprite.active === false || sprite.destroyed) return;
    if ((animationConfig.heartbeat || {}).enabled === false) return; // rides the heartbeat system
    const cfg = animationConfig.flourish?.idleWander || {};
    const store = getStore(scene);
    const key = getSpriteKey(sprite);
    if (!key) return;

    const existing = store.get(key);
    // Don't stack: if a wander already owns this sprite, let it finish (beats are sequential).
    if (existing && existing.__wander && isEntryLive(existing, sprite)) return;

    // Take ownership from the normal heartbeat: stop it and snap its target back to the
    // authoritative rest, so EVERY child is at true rest before we capture wander bases.
    if (existing) {
      safeStopTween(existing.tween);
      restoreTargetState(existing);
      store.delete(key);
    }

    const bail = () => { startHeartbeatForSprite(scene, sprite); };

    const targets = resolveWanderTargets(sprite);
    if (!targets) { bail(); return; }

    const width = scene.game?.config?.width;
    const height = scene.game?.config?.height;
    if (!Number.isFinite(width) || !Number.isFinite(height)) { bail(); return; }
    const pxPerGrid = (width / 100 + height / 50) / 2;
    const radiusGrid = Number.isFinite(opts.radiusGrid)
      ? opts.radiusGrid
      : (Number.isFinite(cfg.radiusGrid) ? cfg.radiusGrid : 1.0);
    const radiusPx = Math.max(0, radiusGrid * pxPerGrid);
    if (radiusPx < 1e-3) { bail(); return; }
    const totalMs = Number.isFinite(opts.durationMs) && opts.durationMs > 0
      ? opts.durationMs
      : (Number.isFinite(cfg.durationMs) ? cfg.durationMs : 900);

    // Seeded, per-axis two-component drift → smooth non-repeating organic motion.
    const rand = mulberry32((opts.seed | 0) || 1);
    const fx1 = 0.4 + rand() * 0.5, fx2 = 0.8 + rand() * 0.8;
    const fy1 = 0.4 + rand() * 0.5, fy2 = 0.8 + rand() * 0.8;
    const phx1 = rand() * Math.PI * 2, phx2 = rand() * Math.PI * 2;
    const phy1 = rand() * Math.PI * 2, phy2 = rand() * Math.PI * 2;
    const wx = 0.55 + rand() * 0.35, wy = 0.55 + rand() * 0.35;

    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      targets.restore();
      // Re-pin the photo clip to the restored position in this same frame (see below).
      if (typeof sprite.__syncMask === "function") sprite.__syncMask();
      // Re-establish the normal heartbeat from true rest (replaces the wander store entry).
      if (sprite.active !== false && !sprite.destroyed) startHeartbeatForSprite(scene, sprite);
      else store.delete(key);
    };

    const tween = scene.tweens.addCounter({
      from: 0,
      to: 1,
      duration: Math.max(1, totalMs),
      onUpdate: (tw) => {
        const s = (tw.elapsed || 0) / 1000;
        const p = Math.min(1, (tw.elapsed || 0) / Math.max(1, totalMs));
        const env = Math.sin(Math.PI * p); // 0 at both ends, 1 at mid-beat — no snap
        const ox = radiusPx * env * (
          wx * Math.sin(2 * Math.PI * fx1 * s + phx1) +
          (1 - wx) * Math.sin(2 * Math.PI * fx2 * s + phx2)
        );
        const oy = radiusPx * env * (
          wy * Math.sin(2 * Math.PI * fy1 * s + phy1) +
          (1 - wy) * Math.sin(2 * Math.PI * fy2 * s + phy2)
        );
        targets.apply(ox, oy);
        // Re-pin the masked photo's clip circle to the photo IN THIS FRAME. The marker's
        // scene-`update` mask sync can lag a sustained per-frame render-space move enough to
        // leave a faint detached "ghost" of the headshot; syncing in lockstep prevents it.
        if (typeof sprite.__syncMask === "function") sprite.__syncMask();
      },
      onComplete: finish,
      onStop: finish,
    });
    if (!tween) { finish(); return; }
    tween.__uessBoundaryIgnore = true;
    // Register as the sprite's live entry so ensureConsistentHeartbeat won't double-manage
    // it mid-beat. baseState:null makes restoreTargetState a safe no-op (finish() owns restore).
    store.set(key, {
      sprite,
      tween,
      __wander: true,
      target: sprite,
      mode: "wander",
      xProp: "x",
      yProp: "y",
      baseState: null,
    });
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
      restoreTargetState(entry);
    }
    store.clear();
  } catch (_) {
    // Visual-only; never throw.
  }
}
