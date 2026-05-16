import { getPlayerImageUrl } from "../utils/announcements.js";

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

  const players = Array.isArray(allPlayers) ? allPlayers : [];
  const queued = [];

  for (const player of players) {
    const id = player?.playerId ?? player?.player_id ?? player?._id;
    if (!id || id === "ball" || id === "Ball") continue;
    const key = headshotTextureKey(id);
    if (scene.textures && scene.textures.exists(key)) continue;
    const url = getPlayerImageUrl(player.photo, id);
    scene.load.image(key, url);
    queued.push(key);
  }

  if (!scene.textures || !scene.textures.exists(HEADSHOT_FALLBACK_KEY)) {
    const fallbackUrl = getPlayerImageUrl(null, null);
    scene.load.image(HEADSHOT_FALLBACK_KEY, fallbackUrl);
    queued.push(HEADSHOT_FALLBACK_KEY);
  }

  if (queued.length === 0) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const onComplete = () => {
      scene.load.off("loaderror", onLoadError);
      resolve();
    };
    const onLoadError = (file) => {
      if (file && file.key) {
        console.warn(`[headshots] failed to load texture "${file.key}" — marker will use initials fallback`);
      }
    };
    scene.load.once("complete", onComplete);
    scene.load.on("loaderror", onLoadError);
    scene.load.start();
  });
}
