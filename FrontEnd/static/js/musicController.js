/**
 * Background music controller.
 *
 * Two independent music contexts:
 *
 * 1. FRANCHISE — a single track loops across the entire franchise-mode UX
 *    (FCC + standings + rankings + rosters + game plan + box score + recruiting
 *    + reports, etc.). Persistence across hard page navigations is implemented
 *    via localStorage; each opt-in page resumes from `{track, currentTime}`
 *    state on load and writes it back on unload. Brief audible gap (50–300ms)
 *    during navigations is expected.
 *
 * 2. GAMEPLAY — a separate short track loops only on court.html. Scoped to
 *    that single page; dies with page unload.
 *
 * Spec: _documentation_master/07_Design_Systems/Soundtrack_System.md
 */

const FCC_TRACKS = ["scouting-track-1.mp3", "scouting-track-2.mp3"];
const GAMEPLAY_TRACK = "pixel-pulse-1.mp3";
const DEFAULT_VOLUME = 0.4;
const STATE_KEY = "franchise_music_state";

let franchiseAudio = null;
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

function readState() {
  try {
    const raw = localStorage.getItem(STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.track || typeof parsed.currentTime !== "number") return null;
    return parsed;
  } catch (_err) {
    return null;
  }
}

function writeState(audio) {
  if (!audio || audio.dataset.musicKilled === "1") return;
  const track = audio.dataset?.musicTrack;
  if (!track) return;
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify({
      track,
      currentTime: audio.currentTime || 0,
    }));
  } catch (_err) {
    /* localStorage unavailable / over quota — ignore */
  }
}

function buildAudio(filename) {
  const audio = new Audio();
  audio.src = `${soundsBasePath()}${encodeURIComponent(filename)}`;
  audio.preload = "none";
  audio.loop = true;
  audio.volume = DEFAULT_VOLUME;
  audio.dataset.musicTrack = filename;
  audio.dataset.musicKilled = "0";
  return audio;
}

function attachFranchiseStatePersistence(audio) {
  // timeupdate fires every ~250ms during playback; cheap source of fresh
  // currentTime so a fast navigation doesn't resume from a stale checkpoint.
  audio.addEventListener("timeupdate", () => writeState(audio));
  // beforeunload as the final-pass write right before the page tears down.
  window.addEventListener("beforeunload", () => writeState(audio));
}

function playAudio(audio, label) {
  const playPromise = audio.play();
  debugLog("play", { label, file: audio.dataset.musicTrack, t: audio.currentTime });
  if (playPromise?.catch) {
    playPromise.catch((err) => {
      debugLog("play_blocked", { label, reason: err?.message || String(err) });
    });
  }
}

/**
 * Start the franchise music loop with a fresh random pick. Used by the FCC
 * page on every visit (always re-rolls, ignores existing state). Writes new
 * state so downstream franchise pages can resume.
 */
export function playFccTrack() {
  if (franchiseAudio && !franchiseAudio.paused) {
    debugLog("fcc_already_playing", { file: franchiseAudio.dataset.musicTrack });
    return;
  }
  const pick = FCC_TRACKS[Math.floor(Math.random() * FCC_TRACKS.length)];
  franchiseAudio = buildAudio(pick);
  attachFranchiseStatePersistence(franchiseAudio);
  franchiseAudio.currentTime = 0;
  writeState(franchiseAudio);
  debugLog("fcc_pick", { file: pick });
  playAudio(franchiseAudio, "fcc");
}

/**
 * Resume the franchise music on opt-in pages (standings, rankings, rosters,
 * game-plan, box-score, recruiting, recruiting-results, training-report).
 * No-op when state is empty — that's the "silent" branch of every crossover
 * page (e.g. box-score reached from EOG modal, training-report from training.js).
 */
export function resumeFranchiseTrack() {
  if (franchiseAudio && !franchiseAudio.paused) return;
  const state = readState();
  if (!state) {
    debugLog("resume_no_state");
    return;
  }
  franchiseAudio = buildAudio(state.track);
  attachFranchiseStatePersistence(franchiseAudio);
  franchiseAudio.currentTime = state.currentTime || 0;
  debugLog("resume", { file: state.track, t: state.currentTime });
  playAudio(franchiseAudio, "resume");
}

/**
 * Hard stop on the franchise loop and wipe persisted state. Called by:
 *   - Boundary pages on load (set-lineup.html, court.html)
 *   - Kill-point click handlers (FCC Play Game / Run Training / Run Recruiting / Exit Franchise)
 *
 * The `musicKilled` flag prevents any in-flight timeupdate/beforeunload listener
 * from re-writing state after the kill.
 */
export function clearFranchiseMusicState() {
  if (franchiseAudio) {
    franchiseAudio.dataset.musicKilled = "1";
    franchiseAudio.pause();
    franchiseAudio.currentTime = 0;
    franchiseAudio = null;
  }
  try {
    localStorage.removeItem(STATE_KEY);
  } catch (_err) {
    /* ignore */
  }
  debugLog("franchise_state_cleared");
}

/**
 * Start the gameplay background loop on court.html. Each fresh start plays
 * from the beginning; calls during ongoing playback are no-ops so mid-game
 * inbound events don't yank the track back to zero.
 */
export function playGameplayTrack() {
  if (gameplayAudio && !gameplayAudio.paused) {
    debugLog("gameplay_already_playing");
    return;
  }
  if (!gameplayAudio) {
    gameplayAudio = buildAudio(GAMEPLAY_TRACK);
  }
  gameplayAudio.currentTime = 0;
  playAudio(gameplayAudio, "gameplay");
}

export function stopGameplayTrack() {
  if (!gameplayAudio) return;
  gameplayAudio.pause();
  gameplayAudio.currentTime = 0;
  debugLog("gameplay_stop");
}
