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
  "shot-standard.wav",
  "swish.wav",
  "clank.wav",
  "back-of-rim.wav",
  "rattle-leather.wav",
  "bb-swish.wav",
  "bb-rim-swish.wav",
  "bb-clank.wav",
  "bb-clank-2.wav",
  "airball.wav",
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
  "sammy-steal.wav",
  "braddock-steal.wav",
  "butler-steal.wav",
  "click-steal.wav",
  "braddock-three.mp3",
  "duke-three.mp3",
  "sammy-three.mp3",
  "block1.wav",
  "airball-emotion.wav",
  "duke-its-blocked.wav",
  "duke-charging.wav",
  "duke-great-stop.wav",
  "duke-denied.wav",
  "duke-hold-up.wav",
  // Dynamic HCO Motion — hot-read coach VO (one chosen at random by the backend).
  "braddock-greatread.wav",
  "sammy-niceread.mp3",
]);

// Heavy rattle fires 8 hops at 40 ms each — needs a big enough pool to hold
// overlapping plays without truncating earlier ones.
const POOL_SIZE_OVERRIDES = Object.freeze({
  "rattle-leather.wav": 8,
});

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

  const effectiveSize = POOL_SIZE_OVERRIDES[filename] ?? poolSize;
  const audios = Array.from({ length: effectiveSize }, () => createAudio(filename));
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
  if (!filename) {
    console.warn("[SFX] playGameSfx called with no filename", meta);
    return;
  }
  if (!scene) {
    console.warn("[SFX] playGameSfx called with no scene", { filename, ...meta });
  }
  const pool = ensurePool(filename);
  const audio = nextAudioFromPool(pool);
  if (!audio) {
    console.warn("[SFX] no audio available in pool (not preloaded or pool exhausted)", { filename, ...meta });
    return;
  }

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
  return audio;
}

/**
 * Steal reach-in cue: plays `click-steal.wav` once. Fired by the reach-in
 * flourish at the start of the steal micro-movement (see flourishes.js). Audio
 * is non-critical.
 */
export function playStealReachInSfx(scene) {
  playGameSfx(scene, "click-steal.wav", DEFAULT_VOLUME, { event: "steal_reach_in" });
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
  // Blocked shots: the block cue is the shot-attempt SFX and takes precedence
  // over the shot_score-scaled tiers below (SFX_System.md "Blocked Shot
  // Attempt"). result_type is already known at release time — the backend
  // resolves the full turn before animation.
  if (String(turnData?.result_type || "").toUpperCase() === "BLOCK") {
    playGameSfx(scene, "block1.wav", DEFAULT_VOLUME, { event: "shot_block" });
    return;
  }

  const preDefense = toNumber(turnData?.sfx?.shot_score_pre_defense ?? turnData?.shot_score_pre_defense);
  if (preDefense == null) return;

  const filename =
    preDefense < 101
      ? "three-weak.wav"
      : preDefense > 210
        ? "three-strong.wav"
        : "shot-standard.wav";
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

// Variants whose SFX is driven by the animation itself (rattle hops), so the
// flight-onComplete hook stays silent for them.
const SHOT_RESULT_SFX_DRIVEN_BY_ANIMATION = new Set([
  "LITTLE_RATTLE",
  "NORMAL_RATTLE",
  "HEAVY_RATTLE",
]);

function pickShotResultSfxFilename(variant, normalizedResult) {
  switch (variant) {
    case "SWISH":
      return "swish.wav";
    case "CLANK":
      return "clank.wav";
    case "BACK_OF_RIM":
      return "back-of-rim.wav";
    case "BANK_MAKE":
      return "bb-rim-swish.wav";
    case "BANK_MISS":
      return Math.random() < 0.5 ? "bb-clank.wav" : "bb-clank-2.wav";
    case "AIRBALL":
      return "airball.wav";
    default:
      // Legacy / unknown variant — fall back to outcome-based SFX.
      if (normalizedResult === "MAKE") return "swish.wav";
      if (normalizedResult === "MISS") return "clank.wav";
      return null;
  }
}

// BOR make follows the rim contact with a swish ~150 ms later — long enough
// to read as "rim → through the net," short enough to feel like one event.
const BOR_MAKE_SWISH_DELAY_MS = 150;
// BANK_MAKE plays bb-rim-swish.wav (bank → rim) and follows with a swish
// almost immediately, since the original recording had the swish trimmed off.
const BANK_MAKE_SWISH_DELAY_MS = 100;

export function playShotResultSfx(scene, turnData, result) {
  const normalizedResult = normalizeShotResult(result);
  const variant = turnData?.shot_variant || null;

  if (SHOT_RESULT_SFX_DRIVEN_BY_ANIMATION.has(variant)) return;

  const filename = pickShotResultSfxFilename(variant, normalizedResult);
  if (!filename) return;
  playGameSfx(scene, filename, DEFAULT_VOLUME, {
    event: "shot_result",
    result: normalizedResult,
    variant,
  });

  if (variant === "BACK_OF_RIM" && normalizedResult === "MAKE") {
    setTimeout(() => {
      playGameSfx(scene, "swish.wav", DEFAULT_VOLUME, {
        event: "shot_result",
        result: normalizedResult,
        variant,
        followup: "bor_swish",
      });
    }, BOR_MAKE_SWISH_DELAY_MS);
  }

  if (variant === "BANK_MAKE" && normalizedResult === "MAKE") {
    setTimeout(() => {
      playGameSfx(scene, "swish.wav", DEFAULT_VOLUME, {
        event: "shot_result",
        result: normalizedResult,
        variant,
        followup: "bank_swish",
      });
    }, BANK_MAKE_SWISH_DELAY_MS);
  }
}

// Weighted 33/33/34 across three voice options. Tied to the "STEAL!"
// announcement appearance (SFX_System.md "Steal Announce"); callers
// resolve a filename here and pass it via `meta.sfx` on the announcement
// payload so `court.html` plays the cue at overlay mount.
const STEAL_SFX_FILES = Object.freeze([
  { file: "sammy-steal.wav", weight: 33 },
  { file: "braddock-steal.wav", weight: 33 },
  { file: "butler-steal.wav", weight: 34 },
]);

export function resolveStealSfxFile() {
  const total = STEAL_SFX_FILES.reduce((sum, entry) => sum + entry.weight, 0);
  let roll = Math.random() * total;
  for (const entry of STEAL_SFX_FILES) {
    roll -= entry.weight;
    if (roll <= 0) return entry.file;
  }
  return STEAL_SFX_FILES[STEAL_SFX_FILES.length - 1].file;
}

// Weighted 33/33/34 across three voice options. Tied to the "INTERCEPTION!"
// announcement appearance (SFX_System.md "Interception Announce") — fired for
// PASS interceptions (RR lane pass, HCT/HCO/FCP pass contests) instead of the
// reach-in steal cue. Callers resolve a filename here and pass it via `meta.sfx`
// so `court.html` plays the cue at overlay mount.
const INTERCEPTION_SFX_FILES = Object.freeze([
  { file: "braddock-interception.mp3", weight: 33 },
  { file: "duke-interception.mp3", weight: 33 },
  { file: "sammy-interception.mp3", weight: 34 },
]);

export function resolveInterceptionSfxFile() {
  const total = INTERCEPTION_SFX_FILES.reduce((sum, entry) => sum + entry.weight, 0);
  let roll = Math.random() * total;
  for (const entry of INTERCEPTION_SFX_FILES) {
    roll -= entry.weight;
    if (roll <= 0) return entry.file;
  }
  return INTERCEPTION_SFX_FILES[INTERCEPTION_SFX_FILES.length - 1].file;
}

// One of three announcer-voice calls played at random when a made 3-pointer's
// "It's Good!" announcement mounts (SFX_System.md "Made Three Announce"). Even
// 33/33/34 split, mirroring the steal/interception cues. Callers resolve a file
// here (via the "three_make" key) and pass it through meta.sfx so court.html
// plays it at overlay mount, synced to the visual.
const THREE_POINTER_SFX_FILES = Object.freeze([
  { file: "braddock-three.mp3", weight: 33 },
  { file: "duke-three.mp3", weight: 33 },
  { file: "sammy-three.mp3", weight: 34 },
]);

export function resolveThreePointerSfxFile() {
  const total = THREE_POINTER_SFX_FILES.reduce((sum, entry) => sum + entry.weight, 0);
  let roll = Math.random() * total;
  for (const entry of THREE_POINTER_SFX_FILES) {
    roll -= entry.weight;
    if (roll <= 0) return entry.file;
  }
  return THREE_POINTER_SFX_FILES[THREE_POINTER_SFX_FILES.length - 1].file;
}

// Fires at the moment the ball attaches to the rebounder sprite. DREB → defense
// strong; OREB → inside strong.
export function playReboundSfx(scene, reboundType) {
  if (reboundType === "DREB") {
    playGameSfx(scene, "attack-shot-strong.wav", DEFAULT_VOLUME, { event: "rebound", rebound_type: "DREB" });
    return;
  }
  if (reboundType === "OREB") {
    playGameSfx(scene, "inside-shot-strong.wav", DEFAULT_VOLUME, { event: "rebound", rebound_type: "OREB" });
  }
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

const ONCE_PER_TURN_SECONDARY_HEADLINES = new Set(["Press!", "Trap!", "Fast Break!"]);
let secondaryCourtEventSfxPlayedThisTurn = new Set();

/** Reset Press / Trap / Fast Break secondary stingers for a new turn. */
export function resetSecondaryAnnounceCourtSfxDedup() {
  secondaryCourtEventSfxPlayedThisTurn = new Set();
}

/**
 * Headline → secondary-tier SFX filename, with once-per-turn dedupe for
 * Press / Trap / Fast Break. Returns null when no headline match or the
 * once-per-turn gate has already consumed this turn's stinger.
 *
 * Mirrors ``playSecondaryAnnounceCourtSfx`` but does not play — callers put
 * the returned filename on the announcement payload (``data.sfx``) so the
 * actual play happens at overlay mount time in ``court.html``, synced to
 * the visual entry per SFX_System.md.
 */
export function resolveSecondaryAnnounceCourtSfxFile(headline) {
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
    case "No Fast Break":
      filename = "duke-hold-up.wav";
      break;
    default:
      return null;
  }
  if (ONCE_PER_TURN_SECONDARY_HEADLINES.has(text)) {
    if (secondaryCourtEventSfxPlayedThisTurn.has(text)) return null;
    secondaryCourtEventSfxPlayedThisTurn.add(text);
  }
  return filename;
}

/**
 * Legacy ``meta.sfx`` KEY → filename (or null when no mapping).
 *
 * Supports both:
 *   - Secondary-tier keys backend stamps on schema announcements:
 *     ``"steal"`` / ``"block_announce"`` / ``"charge_announce"`` /
 *     ``"fb_defensive_stop"`` / ``"fb_outlet_denied_court"`` /
 *     ``"no_fast_break"``. Mirrors ``playAnnouncementMetaCourtSfx``'s switch.
 *   - Primary-tier legacy kinds historically passed to ``playAnnouncementSfx``:
 *     ``"foul"`` / ``"shot_clock_violation"``. Lets callers keep the legacy
 *     ``meta.sfx`` contract while the actual play moves to court.html mount.
 *
 * Callers put the returned filename on ``data.sfx``; court.html plays at
 * overlay mount, synced to the visual entry per SFX_System.md.
 */
export function resolveAnnounceMetaCourtSfxFile(key) {
  switch (String(key || "").trim()) {
    case "steal": return resolveStealSfxFile();
    case "interception": return resolveInterceptionSfxFile();
    case "three_make": return resolveThreePointerSfxFile();
    case "block_announce": return "duke-its-blocked.wav";
    case "charge_announce": return "duke-charging.wav";
    case "fb_defensive_stop": return "duke-great-stop.wav";
    case "fb_outlet_denied_court": return "duke-denied.wav";
    case "no_fast_break": return "duke-hold-up.wav";
    case "foul": return "whistle-1-lowervol.wav";
    case "shot_clock_violation": return "whistle-3.mp3";
    default: return null;
  }
}

/**
 * Secondary-announcement court stingers (SFX_System.md — Court Event SFX).
 * Press!, Trap!, and Fast Break! play at most once per turn; other mapped headlines
 * still fire on every matching showSecondaryAnnouncement call.
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
    case "No Fast Break":
      filename = "duke-hold-up.wav";
      break;
    default:
      console.warn("[SFX] playSecondaryAnnounceCourtSfx: no headline match", { headline: text });
      return;
  }
  if (ONCE_PER_TURN_SECONDARY_HEADLINES.has(text)) {
    if (secondaryCourtEventSfxPlayedThisTurn.has(text)) return;
    secondaryCourtEventSfxPlayedThisTurn.add(text);
  }
  playGameSfx(scene, filename, DEFAULT_VOLUME, { event: "court_event_sfx", headline: text });
}

/** Defense Matchups modal open stinger (modal open only). */
export function playDefenseMatchupModalCourtSfx(scene) {
  playGameSfx(scene, "defense-sammy.mp3", DEFAULT_VOLUME, { event: "defense_matchup_modal_open" });
}

/** Primary BLOCK! announcement stinger (normal block card only). */
export function playBlockAnnounceCourtSfx(scene) {
  playGameSfx(scene, "duke-its-blocked.wav", DEFAULT_VOLUME, { event: "block_announce" });
}

/** CHARGE! announcement stinger. */
export function playChargeAnnounceCourtSfx(scene) {
  playGameSfx(scene, "duke-charging.wav", DEFAULT_VOLUME, { event: "charge_announce" });
}

/** Fast Break "Great Stop!" announcement stinger. */
export function playFBDefensiveStopCourtSfx(scene) {
  playGameSfx(scene, "duke-great-stop.wav", DEFAULT_VOLUME, { event: "fb_defensive_stop" });
}

/** Fast Break "FB Outlet Pass Denied!" announcement stinger. */
export function playFBOutletDeniedCourtSfx(scene) {
  playGameSfx(scene, "duke-denied.wav", DEFAULT_VOLUME, { event: "fb_outlet_denied" });
}

/**
 * Backend-emitted announcement metadata (`announcement.meta.sfx`) is the
 * schema path for court-event stingers that are not covered by headline-only
 * secondary mappings. Returns true when the key was recognized.
 */
export function playAnnouncementMetaCourtSfx(scene, key, headline = "") {
  switch (String(key || "").trim()) {
    case "steal":
      playGameSfx(scene, resolveStealSfxFile(), DEFAULT_VOLUME, { event: "steal" });
      return true;
    case "interception":
      playGameSfx(scene, resolveInterceptionSfxFile(), DEFAULT_VOLUME, { event: "interception" });
      return true;
    case "three_make":
      playGameSfx(scene, resolveThreePointerSfxFile(), DEFAULT_VOLUME, { event: "three_make" });
      return true;
    case "block_announce":
      playBlockAnnounceCourtSfx(scene);
      return true;
    case "charge_announce":
      playChargeAnnounceCourtSfx(scene);
      return true;
    case "fb_defensive_stop":
      playFBDefensiveStopCourtSfx(scene);
      return true;
    case "fb_outlet_denied_court":
      playFBOutletDeniedCourtSfx(scene);
      return true;
    case "no_fast_break":
      playGameSfx(scene, "duke-hold-up.wav", DEFAULT_VOLUME, {
        event: "no_fast_break",
        headline,
      });
      return true;
    default:
      console.warn("[SFX] playAnnouncementMetaCourtSfx: unknown meta.sfx key", { key, headline });
      return false;
  }
}

if (typeof window !== "undefined") {
  // `court.html`'s announcement-overlay mount functions read `data.sfx`
  // (filename) and call this to play the cue at the moment the overlay
  // appears — fixes BLOCK SFX timing per SFX_System.md "Block
  // Announce: Trigger: immediately when the Block announce appears."
  // Scene is null because pool retention keeps the audio element alive.
  window.playGameSfx = (filename, volume) =>
    playGameSfx(null, filename, typeof volume === "number" ? volume : DEFAULT_VOLUME, {
      event: "announcement_mount_sfx",
    });
  window.getGameSfxDebugState = getGameSfxDebugState;
}
