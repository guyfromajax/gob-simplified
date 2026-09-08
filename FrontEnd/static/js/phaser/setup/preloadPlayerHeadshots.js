import { getPlayerImageUrl } from "../utils/announcements.js";

// Cap the self-heal so a broken asset zone cannot turn scene start into a stall.
// Above this many misses something systemic is wrong and initials are the right
// answer; below it, a paint round trip (~1-3s each, run in parallel) is worth it.
export const HEAL_MAX = 12;
export const HEAL_TIMEOUT_MS = 8000;

export const HEADSHOT_TEXTURE_PREFIX = "headshot_";
export const HEADSHOT_FALLBACK_KEY = "headshot_fallback";

export function headshotTextureKey(playerId) {
  return `${HEADSHOT_TEXTURE_PREFIX}${playerId}`;
}

// Preload all roster player photos as Phaser textures so the headshot marker
// can render them via scene.add.image(). Resolves once the loader is idle.
// Players whose photo URL fails to load simply won't have a texture registered;
// createHeadshotMarker falls back to the initials tile in that case.
export function preloadPlayerHeadshots(scene, allPlayers) {
  if (!scene || !scene.load) {
    return Promise.resolve();
  }

  const debug = (typeof window !== "undefined") && !!window.DEBUG_HEADSHOT_MARKER;
  const players = Array.isArray(allPlayers) ? allPlayers : [];
  const queued = [];
  const queuedUrls = [];

  // Headshots are served cross-origin from the R2 asset domain in staging/prod.
  // WebGL textures of cross-origin images require CORS (anonymous) loading +
  // an Access-Control-Allow-Origin header on the asset zone. Same-origin (local
  // dev) ignores this, so it is always safe to set. Restored in onComplete.
  const prevCrossOrigin = scene.load.crossOrigin;
  scene.load.crossOrigin = "anonymous";

  const byKey = new Map();   // texture key -> { id, uniformKey } for the heal pass
  for (const player of players) {
    const id = player?.playerId ?? player?.player_id ?? player?._id;
    if (!id || id === "ball" || id === "Ball") continue;
    const key = headshotTextureKey(id);
    if (scene.textures && scene.textures.exists(key)) continue;
    // uniform_key addresses the shared archive object; when the payload carries it
    // the first request hits a painted object instead of 404ing.
    const uniformKey = player?.uniform_key ?? player?.uniformKey ?? null;
    const url = getPlayerImageUrl(player.photo, id, uniformKey);
    scene.load.image(key, url);
    queued.push(key);
    byKey.set(key, { id, uniformKey });
    queuedUrls.push({ key, url, playerName: player.name });
  }

  if (!scene.textures || !scene.textures.exists(HEADSHOT_FALLBACK_KEY)) {
    const fallbackUrl = getPlayerImageUrl(null, null);
    scene.load.image(HEADSHOT_FALLBACK_KEY, fallbackUrl);
    queued.push(HEADSHOT_FALLBACK_KEY);
    queuedUrls.push({ key: HEADSHOT_FALLBACK_KEY, url: fallbackUrl, playerName: null });
  }

  if (debug) {
    console.log("[headshots] queued for preload:", queuedUrls);
  }

  if (queued.length === 0) {
    return Promise.resolve();
  }

  let healed = false;
  return new Promise((resolve) => {
    const failed = [];
    const onComplete = () => {
      scene.load.crossOrigin = prevCrossOrigin;
      scene.load.off("loaderror", onLoadError);
      const loaded = queued.filter((k) => scene.textures.exists(k));
      // Unconditional one-line summary so we can verify load health without a debug flag.
      console.log(`[headshots] preload complete — loaded ${loaded.length}/${queued.length}, failed ${failed.length}`);
      if (debug) {
        console.log("[headshots] detail", {
          loadedKeys: loaded,
          failedKeys: failed,
        });
      }
      // SELF-HEAL. WebGL textures are not <img> elements, so the delegated
      // paint-on-miss handler in api-config.js never sees them — without this a
      // single missed paint means an initials tile for the whole game and every
      // game after, since nothing else ever triggers the paint. A pre-warm should
      // mean this never fires; it exists so one miss is not permanent.
      // Bounded and time-capped: a slow paint must never hold the tip-off.
      if (!healed && failed.length && failed.length <= HEAL_MAX) {
        healed = true;
        healFailures(scene, failed, byKey, prevCrossOrigin).then(resolve, resolve);
        return;
      }
      resolve();
    };
    const onLoadError = (file) => {
      if (file && file.key) {
        failed.push(file.key);
        console.warn(`[headshots] failed to load texture "${file.key}" — marker will use initials fallback`);
      }
    };
    scene.load.once("complete", onComplete);
    scene.load.on("loaderror", onLoadError);
    scene.load.start();
  });
}


/**
 * Paint the misses, then re-queue them once. Resolves either way — a portrait must
 * never be able to block the game from starting.
 */
function healFailures(scene, failedKeys, byKey, prevCrossOrigin) {
  const api = (typeof window !== "undefined") && window.API_CONFIG;
  if (!api || typeof api.ensurePlayerImage !== "function") return Promise.resolve();
  const fid = typeof api.currentFranchiseId === "function" ? api.currentFranchiseId() : null;

  const targets = failedKeys
    .map((k) => ({ key: k, ...(byKey.get(k) || {}) }))
    .filter((t) => t.id);
  if (!targets.length) return Promise.resolve();

  console.warn(`[headshots] self-heal: painting ${targets.length} missing master(s)`);

  const paints = targets.map((t) =>
    api.ensurePlayerImage(fid, t.id).catch(() => null)
  );
  const timeout = new Promise((r) => setTimeout(r, HEAL_TIMEOUT_MS));

  return Promise.race([Promise.all(paints), timeout]).then((results) => {
    const reload = [];
    targets.forEach((t, i) => {
      // Prefer the uniform_key the paint just reported: it addresses the shared
      // archive object, which is what the paint actually wrote.
      const res = Array.isArray(results) ? results[i] : null;
      const uk = (res && res.uniform_key) || t.uniformKey || null;
      const url = getPlayerImageUrl(null, t.id, uk);
      // Cache-buster: the browser has a fresh 404 cached for this URL.
      scene.load.image(t.key, url + (url.indexOf("?") === -1 ? "?" : "&") + "gobr=1");
      reload.push(t.key);
    });
    if (!reload.length) return;

    return new Promise((done) => {
      let settled = false;
      const finish = () => {
        if (settled) return;          // "complete" and the timeout can both fire
        settled = true;
        scene.load.crossOrigin = prevCrossOrigin;
        const ok = reload.filter((k) => scene.textures.exists(k));
        console.log(`[headshots] self-heal complete — recovered ${ok.length}/${reload.length}`);
        done();
      };
      scene.load.once("complete", finish);
      scene.load.crossOrigin = "anonymous";
      scene.load.start();
      setTimeout(finish, HEAL_TIMEOUT_MS);
    });
  }).catch(() => {});
}
