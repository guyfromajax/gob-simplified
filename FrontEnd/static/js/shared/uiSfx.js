/**
 * One UI / music / ambience / gameplay-sfx volume bus.
 *
 * Effective gain for a channel is master × channel, or 0 when either is muted.
 * Levels are 0–100. Persisted in localStorage under AUDIO_STORAGE_KEY so the
 * same settings work online and in the offline desktop build.
 *
 * Named constants stay the call-site vocabulary. playSfx(name) maps those
 * names (and legacy filenames) onto files, respects the sfx channel, and
 * installs one data-sfx click hook per document.
 */

const SFX_FILES = {
  SFX_ADVANCE: 'confirm-1-lowervol.wav',
  SFX_SELECT: 'click-tiny.wav',
  SFX_COMMIT: 'click-beep.wav',
  STING_WIN: 'sting-win.wav',
  STING_MILESTONE: 'sting-milestone.wav',
  STING_SEASON_PEAK: 'sting-season-peak.wav',
};

export const SFX_ADVANCE = SFX_FILES.SFX_ADVANCE;
export const SFX_SELECT = SFX_FILES.SFX_SELECT;
export const SFX_COMMIT = SFX_FILES.SFX_COMMIT;
export const STING_WIN = SFX_FILES.STING_WIN;
export const STING_MILESTONE = SFX_FILES.STING_MILESTONE;
export const STING_SEASON_PEAK = SFX_FILES.STING_SEASON_PEAK;

export const AUDIO_STORAGE_KEY = 'gob_audio_v1';
export const LEGACY_AMBIENCE_KEY = 'gob_scouting_ambience_enabled';
export const AUDIO_CHANNELS = ['master', 'music', 'sfx', 'ambience'];

const listeners = new Set();

function clampLevel(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 100;
  return Math.max(0, Math.min(100, Math.round(n)));
}

function channelSlot(raw, fallback) {
  const src = raw && typeof raw === 'object' ? raw : {};
  return {
    level: clampLevel(src.level == null ? fallback.level : src.level),
    muted: src.muted == null ? !!fallback.muted : !!src.muted,
  };
}

export function defaultAudioState() {
  return {
    master: { level: 100, muted: false },
    music: { level: 100, muted: false },
    sfx: { level: 100, muted: false },
    ambience: { level: 100, muted: false },
  };
}

/**
 * Build a state object from stored JSON and the legacy ambience flag.
 * An existing gob_audio_v1 record wins. Otherwise a legacy "false" opt-out
 * mutes ambience and keeps its level.
 */
export function normalizeAudioState(raw, legacyValue) {
  const base = defaultAudioState();
  const src = raw && typeof raw === 'object' ? raw : null;
  if (src) {
    AUDIO_CHANNELS.forEach((name) => {
      base[name] = channelSlot(src[name], base[name]);
    });
    return base;
  }
  if (legacyValue === 'false') base.ambience.muted = true;
  return base;
}

export function channelGain(state, channel) {
  if (!state || !state.master || !state[channel]) return 0;
  if (state.master.muted || state[channel].muted) return 0;
  return (state.master.level / 100) * (state[channel].level / 100);
}

function storage() {
  try {
    if (typeof localStorage === 'undefined') return null;
    return localStorage;
  } catch (_err) {
    return null;
  }
}

let state = null;

function ensureState() {
  if (state) return state;
  const store = storage();
  let raw = null;
  let legacy = null;
  if (store) {
    try { raw = JSON.parse(store.getItem(AUDIO_STORAGE_KEY) || 'null'); } catch (_err) { raw = null; }
    try { legacy = store.getItem(LEGACY_AMBIENCE_KEY); } catch (_err) { legacy = null; }
  }
  const hadRecord = !!(raw && typeof raw === 'object');
  state = normalizeAudioState(raw, legacy);
  if (store && !hadRecord && legacy === 'false') writeState();
  return state;
}

function writeState() {
  const store = storage();
  if (!store || !state) return;
  try { store.setItem(AUDIO_STORAGE_KEY, JSON.stringify(state)); } catch (_err) { /* quota */ }
}

function emit() {
  const snapshot = getAudioState();
  listeners.forEach((fn) => {
    try { fn(snapshot); } catch (_err) { /* listener */ }
  });
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new CustomEvent('gob-audio-change', { detail: snapshot }));
  }
}

export function getAudioState() {
  const current = ensureState();
  const copy = {};
  AUDIO_CHANNELS.forEach((name) => {
    copy[name] = { level: current[name].level, muted: current[name].muted };
  });
  return copy;
}

export function subscribeAudio(fn) {
  if (typeof fn !== 'function') return function () {};
  listeners.add(fn);
  return function () { listeners.delete(fn); };
}

export function setChannelLevel(channel, level) {
  if (!AUDIO_CHANNELS.includes(channel)) return getAudioState();
  ensureState();
  state[channel].level = clampLevel(level);
  writeState();
  emit();
  return getAudioState();
}

export function setChannelMuted(channel, muted) {
  if (!AUDIO_CHANNELS.includes(channel)) return getAudioState();
  ensureState();
  state[channel].muted = !!muted;
  writeState();
  if (channel === 'ambience') {
    const store = storage();
    if (store) {
      try { store.setItem(LEGACY_AMBIENCE_KEY, state.ambience.muted ? 'false' : 'true'); } catch (_err) { /* ignore */ }
    }
  }
  emit();
  return getAudioState();
}

export function resetAudioStateForTests(next) {
  state = next ? normalizeAudioState(next, null) : null;
}

function soundBase() {
  if (typeof window !== 'undefined'
    && window.API_CONFIG
    && typeof window.API_CONFIG.buildStaticPath === 'function') {
    return window.API_CONFIG.buildStaticPath('/sounds/');
  }
  return '/sounds/';
}

export function outputVolume(baseVolume, channel) {
  const base = typeof baseVolume === 'number' ? baseVolume : 0.7;
  const gain = channelGain(ensureState(), channel || 'sfx');
  return Math.max(0, Math.min(1, base * gain));
}

const missingLogged = new Set();
const knownMissing = new Set();
const preloadCache = Object.create(null);
let activeSting = null;
const hookedDocs = typeof WeakSet === 'function' ? new WeakSet() : null;
let hookedFallback = false;

function resolveNamed(name) {
  if (!name || typeof name !== 'string') return null;
  const key = name.trim();
  if (!key) return null;
  if (SFX_FILES[key]) {
    return { key, file: SFX_FILES[key], sting: key.indexOf('STING_') === 0 };
  }
  const keys = Object.keys(SFX_FILES);
  for (let i = 0; i < keys.length; i += 1) {
    const k = keys[i];
    if (SFX_FILES[k] === key) {
      return { key: k, file: key, sting: k.indexOf('STING_') === 0 };
    }
  }
  if (key.indexOf('.') !== -1) {
    return { key, file: key, sting: false };
  }
  return null;
}

function logMissingOnce(key) {
  if (missingLogged.has(key)) return;
  missingLogged.add(key);
  if (typeof console !== 'undefined' && typeof console.debug === 'function') {
    console.debug('[uiSfx] missing sound', key);
  }
}

function stopActiveSting() {
  if (!activeSting) return;
  try {
    activeSting.pause();
    activeSting.currentTime = 0;
  } catch (_err) { /* non-fatal */ }
  activeSting = null;
}

function markMissing(file, key, audio) {
  knownMissing.add(file);
  preloadCache[file] = false;
  logMissingOnce(key);
  if (activeSting === audio) activeSting = null;
}

function preloadFile(file, key) {
  if (typeof Audio === 'undefined') return;
  if (preloadCache[file] || knownMissing.has(file)) return;
  try {
    const probe = new Audio();
    probe.preload = 'auto';
    probe.addEventListener('canplaythrough', function () {
      preloadCache[file] = probe;
    }, { once: true });
    probe.addEventListener('error', function () {
      markMissing(file, key, probe);
    }, { once: true });
    probe.src = soundBase() + encodeURIComponent(file);
    preloadCache[file] = probe;
  } catch (_err) { /* non-fatal */ }
}

export function playSfx(name, baseVolume = 0.7) {
  try {
    const resolved = resolveNamed(name);
    if (!resolved || typeof Audio === 'undefined') return;
    if (knownMissing.has(resolved.file) || preloadCache[resolved.file] === false) return;
    const vol = outputVolume(baseVolume, 'sfx');
    if (vol <= 0) return;
    if (typeof window !== 'undefined' && Array.isArray(window.__gobSfxCalls)) {
      try { window.__gobSfxCalls.push(resolved.key); } catch (_err) { /* spy */ }
    }

    preloadFile(resolved.file, resolved.key);

    const a = new Audio(soundBase() + encodeURIComponent(resolved.file));
    a.volume = vol;
    a.addEventListener('error', function onErr() {
      a.removeEventListener('error', onErr);
      markMissing(resolved.file, resolved.key, a);
    }, { once: true });

    if (resolved.sting) {
      stopActiveSting();
      activeSting = a;
      a.addEventListener('ended', function () {
        if (activeSting === a) activeSting = null;
      }, { once: true });
    }

    const played = a.play();
    if (played && typeof played.catch === 'function') {
      played.catch(function () {
        if (activeSting === a) activeSting = null;
      });
    }
  } catch (_err) { /* non-fatal */ }
}

function onSfxClick(ev) {
  const t = ev && ev.target;
  if (!t || typeof t.closest !== 'function') return;
  const el = t.closest('[data-sfx]');
  if (!el || typeof el.matches !== 'function') return;
  if (!el.matches('button, a, [role="tab"]')) return;
  const hookName = el.getAttribute('data-sfx');
  if (!hookName || !SFX_FILES[hookName.trim()]) return;
  playSfx(hookName.trim());
}

export function installSfxHooks(doc) {
  const root = doc || (typeof document !== 'undefined' ? document : null);
  if (!root || typeof root.addEventListener !== 'function') return;
  if (hookedDocs) {
    if (hookedDocs.has(root)) return;
    hookedDocs.add(root);
  } else {
    if (hookedFallback) return;
    hookedFallback = true;
  }
  root.addEventListener('click', onSfxClick);
  preloadFile(SFX_FILES.SFX_ADVANCE, 'SFX_ADVANCE');
  preloadFile(SFX_FILES.SFX_SELECT, 'SFX_SELECT');
  preloadFile(SFX_FILES.SFX_COMMIT, 'SFX_COMMIT');
}

export function playAdvance() { playSfx(SFX_ADVANCE, 0.7); }
export function playSelect() { playSfx(SFX_SELECT, 0.7); }
export function playCommit() { playSfx(SFX_COMMIT, 0.7); }

const api = {
  playSfx,
  playAdvance,
  playSelect,
  playCommit,
  installSfxHooks,
  SFX_ADVANCE,
  SFX_SELECT,
  SFX_COMMIT,
  STING_WIN,
  STING_MILESTONE,
  STING_SEASON_PEAK,
  getAudioState,
  setChannelLevel,
  setChannelMuted,
  subscribeAudio,
  channelGain,
  outputVolume,
  AUDIO_STORAGE_KEY,
  LEGACY_AMBIENCE_KEY,
};

if (typeof window !== 'undefined') window.GOBUiSfx = api;
if (typeof document !== 'undefined') installSfxHooks(document);
