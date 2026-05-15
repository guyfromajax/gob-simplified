/**
 * Background music controller.
 *
 * Separate from gameSfx.js — the SFX pool preloads 4 Audio elements per file at
 * startup, which is wasteful for multi-minute loop tracks. This controller
 * lazy-builds a single Audio element per track, with `preload="none"` so
 * nothing hits the network until the track actually needs to play.
 *
 * Each page load gets a fresh module state, so the FCC random pick re-rolls
 * naturally on every FCC visit (each is a separate HTML page).
 *
 * Spec: _documentation_master/07_Design_Systems/Soundtrack_System.md
 */

const FCC_TRACKS = ["scouting-track-1.mp3", "scouting-track-2.mp3"];
const GAMEPLAY_TRACK = "pixel-pulse-1.mp3";
const DEFAULT_VOLUME = 0.4;

let fccAudio = null;
let gameplayAudio = null;

function soundsBasePath() {
  if (typeof window !== "undefined" && window.API_CONFIG?.buildStaticPath) {
    return window.API_CONFIG.buildStaticPath("/sounds/");
  }
  return "/sounds/";
}

function debugEnabled() {
  if (typeof window === "undefined") return false;
  if (window.DEBUG_MUSIC === true) return true;
  try {
    const value = new URLSearchParams(window.location.search).get("debug_music");
    return ["1", "true", "yes"].includes(String(value || "").toLowerCase());
  } catch (_err) {
    return false;
  }
}

function debugLog(event, payload = {}) {
  if (!debugEnabled()) return;
  console.debug("[musicController]", event, payload);
}

function buildAudio(filename) {
  const audio = new Audio();
  audio.src = `${soundsBasePath()}${encodeURIComponent(filename)}`;
  audio.preload = "none";
  audio.loop = true;
  audio.volume = DEFAULT_VOLUME;
  audio.dataset.musicTrack = filename;
  return audio;
}

function playAudio(audio, label) {
  const playPromise = audio.play();
  debugLog("play", { label, file: audio.dataset.musicTrack });
  if (playPromise?.catch) {
    playPromise.catch((err) => {
      debugLog("play_blocked", { label, reason: err?.message || String(err) });
    });
  }
}

/**
 * Start the FCC background loop. Picks one of the two scouting tracks 50/50
 * the first time this is called per page load; subsequent calls reuse the
 * same pick. No-op when already playing.
 */
export function playFccTrack() {
  if (fccAudio && !fccAudio.paused) {
    debugLog("fcc_already_playing", { file: fccAudio.dataset.musicTrack });
    return;
  }
  if (!fccAudio) {
    const pick = FCC_TRACKS[Math.floor(Math.random() * FCC_TRACKS.length)];
    fccAudio = buildAudio(pick);
    debugLog("fcc_pick", { file: pick });
  }
  fccAudio.currentTime = 0;
  playAudio(fccAudio, "fcc");
}

/** Hard stop on the FCC loop. Called by Play Game / Run Training / Run Recruiting. */
export function stopFccTrack() {
  if (!fccAudio) return;
  fccAudio.pause();
  fccAudio.currentTime = 0;
  debugLog("fcc_stop", {});
}

/**
 * Start the gameplay background loop on court.html. Each fresh start plays
 * from the beginning (per spec); calls during ongoing playback are no-ops so
 * mid-game inbound events don't yank the track back to zero.
 */
export function playGameplayTrack() {
  if (gameplayAudio && !gameplayAudio.paused) {
    debugLog("gameplay_already_playing", {});
    return;
  }
  if (!gameplayAudio) {
    gameplayAudio = buildAudio(GAMEPLAY_TRACK);
  }
  gameplayAudio.currentTime = 0;
  playAudio(gameplayAudio, "gameplay");
}

/** Hard stop on the gameplay loop. Fires when leaving court.html. */
export function stopGameplayTrack() {
  if (!gameplayAudio) return;
  gameplayAudio.pause();
  gameplayAudio.currentTime = 0;
  debugLog("gameplay_stop", {});
}
