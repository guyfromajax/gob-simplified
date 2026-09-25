/**
 * One UI / music / ambience / gameplay-sfx volume bus.
 *
 * Effective gain for a channel is master × channel, or 0 when either is muted.
 * Levels are 0–100. Persisted in localStorage under AUDIO_STORAGE_KEY so the
 * same settings work online and in the offline desktop build.
 *
 * Named constants stay the call-site vocabulary. This module changes volume,
 * not which file a caller asked for.
 */

export const SFX_ADVANCE = 'confirm-1-lowervol.wav';
export const SFX_SELECT = 'click-tiny.wav';
export const SFX_COMMIT = 'click-beep.wav';

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

export function playSfx(filename, baseVolume = 0.7) {
  try {
    if (!filename || typeof Audio === 'undefined') return;
    const a = new Audio(soundBase() + encodeURIComponent(filename));
    a.volume = outputVolume(baseVolume, 'sfx');
    const played = a.play();
    if (played && typeof played.catch === 'function') played.catch(() => {});
  } catch (_err) { /* non-fatal */ }
}

export function playAdvance() { playSfx(SFX_ADVANCE, 0.7); }
export function playSelect() { playSfx(SFX_SELECT, 0.7); }
export function playCommit() { playSfx(SFX_COMMIT, 0.7); }

const api = {
  playSfx,
  playAdvance,
  playSelect,
  playCommit,
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
