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
const GAMEPLAY_DEFAULT_TRACK = "arcade-pulse-1.mp3";
const GAMEPLAY_CRUNCH_TRACK = "pixel-pulse-1.mp3";
// Q4 crunch-time gate: less than 121 seconds remaining AND score difference of 6 or fewer.
const CRUNCH_TIME_SECONDS = 121;
const CRUNCH_SCORE_DIFF = 6;
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
 * Start the franchise music loop on FCC entry. Symmetric with the rest of the
 * franchise pages: if persisted state exists, resume from it (so a round-trip
 * Standings → FCC carries through the same track). If state is empty (first
 * visit of a session, after a kill point, or after a boundary page wiped it),
 * roll a fresh random pick and start from the beginning.
 */
export function playFccTrack() {
  if (franchiseAudio && !franchiseAudio.paused) {
    debugLog("fcc_already_playing", { file: franchiseAudio.dataset.musicTrack });
    return;
  }
  const state = readState();
  if (state) {
    franchiseAudio = buildAudio(state.track);
    attachFranchiseStatePersistence(franchiseAudio);
    franchiseAudio.currentTime = state.currentTime || 0;
    debugLog("fcc_resume", { file: state.track, t: state.currentTime });
    playAudio(franchiseAudio, "fcc_resume");
    return;
  }
  const pick = FCC_TRACKS[Math.floor(Math.random() * FCC_TRACKS.length)];
  franchiseAudio = buildAudio(pick);
  attachFranchiseStatePersistence(franchiseAudio);
  franchiseAudio.currentTime = 0;
  writeState(franchiseAudio);
  debugLog("fcc_fresh_pick", { file: pick });
  playAudio(franchiseAudio, "fcc_fresh");
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
 * Start the default gameplay track if nothing is currently loaded. No-op when
 * any track (default or crunch) is already in the element — that way the
 * legacy inbound / FT-shooter / opening-tip hooks can't accidentally
 * "downgrade" the crunch track back to the default. Use
 * `evaluateGameplayTrack()` for state-driven switching.
 */
export function playGameplayTrack(filename = GAMEPLAY_DEFAULT_TRACK) {
  if (gameplayAudio) {
    debugLog("gameplay_already_loaded", { current: gameplayAudio.dataset.musicTrack });
    return;
  }
  gameplayAudio = buildAudio(filename);
  gameplayAudio.currentTime = 0;
  playAudio(gameplayAudio, "gameplay_start");
}

/**
 * Reactive gameplay-track selector. Picks the right track for the current
 * game state (quarter, clock, score) and hard-cuts to it if the desired
 * track differs from what's currently loaded. Idempotent: same-track calls
 * are no-ops (don't restart, don't disturb a user pause).
 *
 * Reversible: every call re-evaluates from scratch, so a Q4 score swing that
 * pushes the diff back above 6 flips the music back to the default track.
 *
 * @param {object} ctx
 * @param {number} ctx.quarter           current quarter (5+ = OT)
 * @param {number|string} [ctx.clock]    seconds remaining (number) or "M:SS" string
 * @param {number} [ctx.homeScore]
 * @param {number} [ctx.awayScore]
 */
export function evaluateGameplayTrack(ctx = {}) {
  const desired = chooseGameplayTrack(ctx);
  if (gameplayAudio && gameplayAudio.dataset.musicTrack === desired) {
    return; // already on the right track; respect any paused state
  }
  const wasPaused = gameplayAudio?.paused ?? false;
  if (gameplayAudio) {
    gameplayAudio.pause();
  }
  gameplayAudio = buildAudio(desired);
  gameplayAudio.currentTime = 0;
  debugLog("gameplay_track_set", { file: desired, autoplay: !wasPaused, ctx });
  if (!wasPaused) {
    playAudio(gameplayAudio, "gameplay_switch");
  }
}

function chooseGameplayTrack({ quarter, clock, homeScore, awayScore } = {}) {
  const q = Number(quarter);
  if (Number.isFinite(q) && q > 4) return GAMEPLAY_CRUNCH_TRACK;
  if (Number.isFinite(q) && q === 4) {
    const sec = parseSecondsRemaining(clock);
    const diff = Math.abs((Number(homeScore) || 0) - (Number(awayScore) || 0));
    if (sec < CRUNCH_TIME_SECONDS && diff <= CRUNCH_SCORE_DIFF) {
      return GAMEPLAY_CRUNCH_TRACK;
    }
  }
  return GAMEPLAY_DEFAULT_TRACK;
}

function parseSecondsRemaining(clock) {
  if (typeof clock === "number" && Number.isFinite(clock)) return Math.max(0, clock);
  if (typeof clock !== "string") return Infinity;
  if (clock.includes(":")) {
    const [m, s] = clock.split(":").map(Number);
    if (Number.isFinite(m) && Number.isFinite(s)) return Math.max(0, m * 60 + s);
    return Infinity;
  }
  const n = Number(clock);
  return Number.isFinite(n) ? Math.max(0, n) : Infinity;
}

export function stopGameplayTrack() {
  if (!gameplayAudio) return;
  gameplayAudio.pause();
  gameplayAudio.currentTime = 0;
  debugLog("gameplay_stop");
}

/** Pause the gameplay loop without resetting position. Wired to the Pause button. */
export function pauseGameplayTrack() {
  if (!gameplayAudio || gameplayAudio.paused) return;
  gameplayAudio.pause();
  debugLog("gameplay_pause", { t: gameplayAudio.currentTime });
}

/** Resume the gameplay loop from its current position. Wired to the Resume button. */
export function resumeGameplayTrack() {
  if (!gameplayAudio || !gameplayAudio.paused) return;
  playAudio(gameplayAudio, "gameplay_resume");
}
