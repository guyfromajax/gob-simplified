import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import os from 'node:os';
import path from 'node:path';

// uiSfx.js is browser ESM. The repo package.json is not "type": "module"
// (a nested one would make gobNav.js un-requireable). Load a .mjs copy.
const dest = path.join(os.tmpdir(), 'gob-uiSfx-under-test.mjs');
writeFileSync(dest, readFileSync(new URL('../FrontEnd/static/js/shared/uiSfx.js', import.meta.url)));
const {
  AUDIO_STORAGE_KEY,
  LEGACY_AMBIENCE_KEY,
  channelGain,
  defaultAudioState,
  normalizeAudioState,
  outputVolume,
  resetAudioStateForTests,
  setChannelLevel,
  setChannelMuted,
  getAudioState,
} = await import(pathToFileURL(dest).href);

test('effective volume is master times channel', () => {
  const state = defaultAudioState();
  state.master.level = 50;
  state.sfx.level = 40;
  assert.equal(channelGain(state, 'sfx'), 0.2);
  assert.equal(channelGain(state, 'music'), 0.5);
});

test('mute on either side zeroes the gain and keeps the level', () => {
  const state = defaultAudioState();
  state.sfx.level = 80;
  state.sfx.muted = true;
  assert.equal(channelGain(state, 'sfx'), 0);
  assert.equal(state.sfx.level, 80);
  state.sfx.muted = false;
  state.master.muted = true;
  assert.equal(channelGain(state, 'sfx'), 0);
  assert.equal(state.sfx.level, 80);
});

test('legacy ambience opt-out mutes ambience and keeps level 100', () => {
  const migrated = normalizeAudioState(null, 'false');
  assert.equal(migrated.ambience.muted, true);
  assert.equal(migrated.ambience.level, 100);
  assert.equal(channelGain(migrated, 'ambience'), 0);
  assert.equal(channelGain(migrated, 'music'), 1);
});

test('a saved record wins over the legacy flag', () => {
  const saved = normalizeAudioState({
    master: { level: 90, muted: false },
    music: { level: 10, muted: false },
    sfx: { level: 100, muted: true },
    ambience: { level: 70, muted: false },
  }, 'false');
  assert.equal(saved.ambience.muted, false);
  assert.equal(saved.ambience.level, 70);
  assert.equal(saved.music.level, 10);
  assert.equal(saved.sfx.muted, true);
});

test('output volume multiplies the per-sound base by the channel gain', () => {
  resetAudioStateForTests({
    master: { level: 100, muted: false },
    music: { level: 100, muted: false },
    sfx: { level: 50, muted: false },
    ambience: { level: 100, muted: false },
  });
  assert.equal(outputVolume(0.7, 'sfx'), 0.35);
  assert.equal(outputVolume(0.5, 'sfx'), 0.25);
  assert.equal(outputVolume(0.4, 'music'), 0.4);
});

test('setters persist under one key and round-trip', () => {
  const mem = new Map();
  global.localStorage = {
    getItem(k) { return mem.has(k) ? mem.get(k) : null; },
    setItem(k, v) { mem.set(k, v); },
    removeItem(k) { mem.delete(k); },
  };
  resetAudioStateForTests(null);
  mem.set(LEGACY_AMBIENCE_KEY, 'false');
  const first = getAudioState();
  assert.equal(first.ambience.muted, true);
  assert.equal(mem.get(AUDIO_STORAGE_KEY) != null, true);
  setChannelMuted('ambience', false);
  setChannelLevel('music', 25);
  resetAudioStateForTests(null);
  const again = getAudioState();
  assert.equal(again.ambience.muted, false);
  assert.equal(again.music.level, 25);
  assert.equal(again.master.level, 100);
  delete global.localStorage;
  resetAudioStateForTests(null);
});
