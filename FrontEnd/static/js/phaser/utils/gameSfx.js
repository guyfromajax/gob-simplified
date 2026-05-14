const DEFAULT_VOLUME = 0.7;
const DEFAULT_POOL_SIZE = 4;
const PRELOAD_TIMEOUT_MS = 2500;

export const GAMEPLAY_SFX_FILES = Object.freeze([
  "pass-weak.wav",
  "pass-medium.wav",
  "pass-strong.wav",
  "receive-weak.wav",
  "receive-medium.wav",
  "receive-strong.wav",
  "three-weak.wav",
  "three-medium.wav",
  "three-strong.wav",
  "inside-shot-weak.wav",
  "inside-shot-medium.wav",
  "inside-shot-strong.wav",
  "attack-shot-medium.wav",
  "attack-shot-strong.wav",
  "swish.wav",
  "clank.wav",
  "free-throw-swish.wav",
  "free-throw-miss.wav",
  "outlet-pass-great.wav",
  "outlet-pass-bad.wav",
  "defense-sammy.mp3",
  "fast-break-braddock.mp3",
  "trap-braddock.mp3",
  "sammy-press.mp3",
  "press-braddock.mp3",
  "quick-shot-braddock.mp3",
  "slow-it-down-braddock.mp3",
  "sammy-final-shot.mp3",
  "final-shot-braddock.mp3",
]);

const sfxPools = new Map();
let preloadPromise = null;

function soundBasePath() {
  if (typeof window !== "undefined" && window.API_CONFIG?.buildStaticPath) {
    return window.API_CONFIG.buildStaticPath("/sounds/");
  }
  return "/sounds/";
}

function debugEnabled() {
  if (typeof window === "undefined") return false;
  if (window.DEBUG_GAME_SFX === true) return true;
  try {
    const value = new URLSearchParams(window.location.search).get("debug_sfx");
    return ["1", "true", "yes"].includes(String(value || "").toLowerCase());
  } catch (_err) {
    return false;
  }
}

function debugSfx(eventName, payload = {}) {
  if (!debugEnabled()) return;
  console.debug("[gameSfx]", eventName, payload);
}

function createAudio(filename) {
  const audio = new Audio(`${soundBasePath()}${encodeURIComponent(filename)}`);
  audio.preload = "auto";
  audio.volume = DEFAULT_VOLUME;
  audio.dataset.gameSfxFile = filename;
  audio.dataset.gameSfxBusy = "0";
  return audio;
}

function ensurePool(filename, poolSize = DEFAULT_POOL_SIZE) {
  if (!filename) return null;
  let pool = sfxPools.get(filename);
  if (pool) return pool;

  const audios = Array.from({ length: poolSize }, () => createAudio(filename));
  pool = { filename, audios, cursor: 0, preloadStarted: false };
  sfxPools.set(filename, pool);
  return pool;
}

function waitForAudioReady(audio) {
  if (!audio) return Promise.resolve({ status: "missing" });
  if (audio.readyState >= 3) return Promise.resolve({ status: "ready" });

  return new Promise((resolve) => {
    let settled = false;
    const done = (status) => {
      if (settled) return;
      settled = true;
      audio.removeEventListener("canplaythrough", onReady);
      audio.removeEventListener("canplay", onReady);
      audio.removeEventListener("error", onError);
      clearTimeout(timer);
      resolve({ status });
    };
    const onReady = () => done("ready");
    const onError = () => done("error");
    const timer = setTimeout(() => done("timeout"), PRELOAD_TIMEOUT_MS);

    audio.addEventListener("canplaythrough", onReady, { once: true });
    audio.addEventListener("canplay", onReady, { once: true });
    audio.addEventListener("error", onError, { once: true });
    try {
      audio.load();
    } catch (_err) {
      done("load_error");
    }
  });
}

function retainActiveSfx(scene, audio) {
  if (!scene || !audio) return () => {};
  if (!scene._activeSfx) scene._activeSfx = new Set();
  scene._activeSfx.add(audio);
  return () => scene._activeSfx?.delete(audio);
}

function nextAudioFromPool(pool) {
  if (!pool?.audios?.length) return null;
  const available = pool.audios.find(audio => audio.paused || audio.ended || audio.dataset.gameSfxBusy !== "1");
  if (available) return available;

  const audio = pool.audios[pool.cursor % pool.audios.length];
  pool.cursor += 1;
  return audio;
}

export function preloadGameSfx(scene, files = GAMEPLAY_SFX_FILES) {
  if (preloadPromise) return preloadPromise;

  const uniqueFiles = [...new Set(files.filter(Boolean))];
  preloadPromise = Promise.all(uniqueFiles.map(async (filename) => {
    const pool = ensurePool(filename);
    if (!pool || pool.preloadStarted) return { filename, status: "skipped" };
    pool.preloadStarted = true;
    const results = await Promise.all(pool.audios.map(waitForAudioReady));
    const status = results.some(result => result.status === "ready") ? "ready" : results[0]?.status || "unknown";
    debugSfx("preload", { filename, status, poolSize: pool.audios.length });
    return { filename, status };
  })).then((results) => {
    if (scene) scene._gameSfxPreloaded = true;
    debugSfx("preload_complete", { results });
    return results;
  });

  return preloadPromise;
}

export function getGameSfxDebugState() {
  return {
    preloaded: !!preloadPromise,
    files: [...sfxPools.keys()],
    pools: [...sfxPools.entries()].map(([filename, pool]) => ({
      filename,
      poolSize: pool.audios.length,
      readyCount: pool.audios.filter(audio => audio.readyState >= 3).length,
      busyCount: pool.audios.filter(audio => audio.dataset.gameSfxBusy === "1").length,
    })),
  };
}

export function playGameSfx(scene, filename, volume = DEFAULT_VOLUME, meta = {}) {
  if (!filename) return;
  const pool = ensurePool(filename);
  const audio = nextAudioFromPool(pool);
  if (!audio) return;

  const releaseSceneRef = retainActiveSfx(scene, audio);
  const release = () => {
    audio.dataset.gameSfxBusy = "0";
    releaseSceneRef();
  };

  try {
    audio.volume = volume;
    audio.currentTime = 0;
    audio.dataset.gameSfxBusy = "1";
    audio.addEventListener("ended", release, { once: true });
    audio.addEventListener("error", release, { once: true });
    const playPromise = audio.play();
    debugSfx("play", { filename, readyState: audio.readyState, ...meta });
    if (playPromise?.catch) {
      playPromise.catch((err) => {
        debugSfx("play_rejected", { filename, reason: err?.message || String(err), ...meta });
        release();
      });
    }
  } catch (_err) {
    debugSfx("play_error", { filename, ...meta });
    release();
    // Audio is non-critical.
  }
}

function toNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function shotTypeForSfx(turnData) {
  return String(turnData?.sfx?.shot_type || turnData?.shot_type || "").toLowerCase();
}

function normalizeShotResult(result) {
  if (result === "MAKE" || result === "PUTBACK_MAKE") return "MAKE";
  if (result === "MISS" || result === "PUTBACK_MISS") return "MISS";
  return result;
}

export function playShotLaunchSfx(scene, turnData) {
  const preDefense = toNumber(turnData?.sfx?.shot_score_pre_defense ?? turnData?.shot_score_pre_defense);
  if (preDefense == null) return;

  const filename =
    preDefense < 101
      ? "three-weak.wav"
      : preDefense > 210
        ? "three-strong.wav"
        : "attack-shot-strong.wav";
  playGameSfx(scene, filename, DEFAULT_VOLUME, {
    event: "shot_release",
    shotType: shotTypeForSfx(turnData) || null,
    tier: preDefense < 101 ? "weak" : preDefense > 210 ? "strong" : "medium",
    shot_score_pre_defense: preDefense,
  });

  // Legacy per-shot-type launch SFX (commented for unified test; may revert).
  // const shotType = shotTypeForSfx(turnData);
  // if (!["outside", "attack", "inside"].includes(shotType)) return;
  // const tier = preDefense < 101 ? "weak" : preDefense > 210 ? "strong" : "medium";
  // if (shotType === "outside") {
  //   playGameSfx(scene, `three-${tier}.wav`, DEFAULT_VOLUME, { event: "shot_release", shotType, tier });
  //   return;
  // }
  // if (shotType === "attack" && tier !== "weak") {
  //   playGameSfx(scene, `attack-shot-${tier}.wav`, DEFAULT_VOLUME, { event: "shot_release", shotType, tier });
  //   return;
  // }
  // playGameSfx(scene, `inside-shot-${tier}.wav`, DEFAULT_VOLUME, { event: "shot_release", shotType, tier });
}

export function playShotResultSfx(scene, turnData, result) {
  const normalizedResult = normalizeShotResult(result);
  if (normalizedResult === "MAKE") {
    playGameSfx(scene, "swish.wav", DEFAULT_VOLUME, { event: "shot_result", result: normalizedResult });
    return;
  }

  if (normalizedResult !== "MISS") return;
  playGameSfx(scene, "clank.wav", DEFAULT_VOLUME, { event: "shot_result", result: normalizedResult });
}

export function playFreeThrowResultSfx(scene, result) {
  if (result === "MAKE") {
    playGameSfx(scene, "free-throw-swish.wav", DEFAULT_VOLUME, { event: "free_throw_result", result });
    return;
  }
  if (result === "MISS") {
    playGameSfx(scene, "free-throw-miss.wav", DEFAULT_VOLUME, { event: "free_throw_result", result });
  }
}

export function buildGameplayPassSfxContext(scene, passerId, receiverId) {
  const passerSprite = scene?.playerSprites?.[passerId];
  const receiverSprite = scene?.playerSprites?.[receiverId];
  const passerAttrs = passerSprite?.attributes || scene?.playerInfo?.[passerId]?.attributes || {};
  const receiverAttrs = receiverSprite?.attributes || scene?.playerInfo?.[receiverId]?.attributes || {};
  return {
    passSfx: true,
    passerPS: toNumber(passerAttrs.PS),
    receiverIQ: toNumber(receiverAttrs.IQ),
    receiverCH: toNumber(receiverAttrs.CH),
  };
}

export function buildHcoPassSfxContext(scene, passerId, receiverId) {
  return buildGameplayPassSfxContext(scene, passerId, receiverId);
}

export function playHcoPassStartSfx(scene, sfxContext) {
  if (!sfxContext?.passSfx && !sfxContext?.hcoPass) return;
  const ps = toNumber(sfxContext.passerPS);
  const tier = ps != null && ps > 75 ? "strong" : ps != null && ps < 25 ? "weak" : "medium";
  playGameSfx(scene, `pass-${tier}.wav`, DEFAULT_VOLUME, { event: "pass_release", tier });
}

export function playHcoReceiveSfx(scene, sfxContext) {
  if (!sfxContext?.passSfx && !sfxContext?.hcoPass) return;
  const iq = toNumber(sfxContext.receiverIQ);
  const ch = toNumber(sfxContext.receiverCH);
  const receiverScore = (iq ?? 0) + (ch ?? 0);
  const tier = receiverScore > 130 ? "strong" : receiverScore < 50 ? "weak" : "medium";
  playGameSfx(scene, `receive-${tier}.wav`, DEFAULT_VOLUME, { event: "pass_receive", tier });
}

function pickRandomCourtEventFile(files) {
  if (!files?.length) return null;
  return files[Math.floor(Math.random() * files.length)];
}

/**
 * Secondary-announcement court stingers (Sound_Design_Update.md — Court Event SFX).
 * One play per showSecondaryAnnouncement call for mapped headlines only.
 */
export function playSecondaryAnnounceCourtSfx(scene, headline) {
  const text = String(headline || "").trim();
  let filename = null;
  switch (text) {
    case "Press!":
      filename = pickRandomCourtEventFile(["sammy-press.mp3", "press-braddock.mp3"]);
      break;
    case "Trap!":
      filename = "trap-braddock.mp3";
      break;
    case "Fast Break!":
      filename = "fast-break-braddock.mp3";
      break;
    case "Quick Shot":
      filename = "quick-shot-braddock.mp3";
      break;
    case "Slow It Down":
      filename = "slow-it-down-braddock.mp3";
      break;
    case "Final Shot":
      filename = pickRandomCourtEventFile(["sammy-final-shot.mp3", "final-shot-braddock.mp3"]);
      break;
    default:
      return;
  }
  playGameSfx(scene, filename, DEFAULT_VOLUME, { event: "court_event_sfx", headline: text });
}

/** Defense Matchups modal open stinger (modal open only). */
export function playDefenseMatchupModalCourtSfx(scene) {
  playGameSfx(scene, "defense-sammy.mp3", DEFAULT_VOLUME, { event: "defense_matchup_modal_open" });
}

/** Primary BLOCK! announcement stinger (normal block card only). */
export function playBlockAnnounceCourtSfx(scene) {
  playGameSfx(scene, "inside-shot-weak.wav", DEFAULT_VOLUME, { event: "block_announce" });
}

if (typeof window !== "undefined") {
  window.getGameSfxDebugState = getGameSfxDebugState;
}
