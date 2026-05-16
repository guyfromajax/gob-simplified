import { getPlayerImageUrl } from "../utils/announcements.js";

export const HEADSHOT_TEXTURE_PREFIX = "headshot_";
export const HEADSHOT_FALLBACK_KEY = "headshot_fallback";

export function headshotTextureKey(playerId) {
  return `${HEADSHOT_TEXTURE_PREFIX}${playerId}`;
}

// Normalize image paths the same way bootGame.js does for play-by-play headshots:
// on localhost (Flask static), keep /static/ prefix; on any other host, strip it
// so the path resolves against the deployed asset root (no /static/ on netlify).
function normalizeHeadshotUrl(url) {
  if (!url || typeof url !== "string") return url;
  const isLocalhost =
    typeof window !== "undefined" &&
    (window.location?.hostname === "localhost" ||
      window.location?.hostname === "127.0.0.1");
  if (!isLocalhost && url.startsWith("/static/")) {
    return url.replace("/static", "");
  }
  if (isLocalhost && !url.startsWith("/static/") && url.startsWith("/images/")) {
    return "/static" + url;
  }
  return url;
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

  for (const player of players) {
    const id = player?.playerId ?? player?.player_id ?? player?._id;
    if (!id || id === "ball" || id === "Ball") continue;
    const key = headshotTextureKey(id);
    if (scene.textures && scene.textures.exists(key)) continue;
    const url = normalizeHeadshotUrl(getPlayerImageUrl(player.photo, id));
    scene.load.image(key, url);
    queued.push(key);
    queuedUrls.push({ key, url, playerName: player.name });
  }

  if (!scene.textures || !scene.textures.exists(HEADSHOT_FALLBACK_KEY)) {
    const fallbackUrl = normalizeHeadshotUrl(getPlayerImageUrl(null, null));
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

  return new Promise((resolve) => {
    const failed = [];
    const onComplete = () => {
      scene.load.off("loaderror", onLoadError);
      if (debug) {
        const loaded = queued.filter((k) => scene.textures.exists(k));
        console.log("[headshots] preload complete", {
          loadedCount: loaded.length,
          loadedKeys: loaded,
          failedCount: failed.length,
          failedKeys: failed,
        });
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
