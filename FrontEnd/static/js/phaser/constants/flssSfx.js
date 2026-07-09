/**
 * FLSS coach VO and Final Shot SFX exclusion contract (mirrors BackEnd/constants/flss_sfx.py).
 *
 * FLSS turns may play launch/heave coach VO only. Final Shot stingers and
 * braddock-finalshot are explicitly excluded on FLSS shot attempts.
 */

export const FLSS_COACH_VO_LAUNCH_FILE = 'sammy-launch.mp3';
export const FLSS_COACH_VO_HEAVE_FILE = 'duke-heave.mp3';

/** Court stingers + Final Shot coach clip — never valid on FLSS turns. */
export const FINAL_SHOT_SFX_FILES = Object.freeze([
  'sammy-final-shot.mp3',
  'final-shot-braddock.mp3',
  'braddock-finalshot.mp3',
]);

const FINAL_SHOT_SFX_FILE_SET = new Set(FINAL_SHOT_SFX_FILES);

/** @param {boolean} flssHeaveSfx */
export function flssCoachVoPool(flssHeaveSfx) {
  const pool = [FLSS_COACH_VO_LAUNCH_FILE];
  if (flssHeaveSfx) {
    pool.push(FLSS_COACH_VO_HEAVE_FILE);
  }
  return pool;
}

/** @param {{ flssHeaveSfx?: boolean }} [options] */
export function resolveFlssCoachVoFile(options = {}) {
  const pool = flssCoachVoPool(Boolean(options.flssHeaveSfx));
  return pool[Math.floor(Math.random() * pool.length)];
}

/** @param {string} filename */
export function isFinalShotSfxExcludedOnFlss(filename) {
  return FINAL_SHOT_SFX_FILE_SET.has(String(filename || ''));
}

/** @param {object|null|undefined} turnData */
export function isFlssTurnContext(turnData) {
  return turnData?.flss === true;
}

/**
 * On FLSS turns, block Final Shot SFX and substitute an allowed coach VO file.
 * @param {string} filename
 * @param {{ turnData?: object, event?: string }} [meta]
 * @returns {string}
 */
export function coerceFlssSfxFilename(filename, meta = {}) {
  const turnData = meta.turnData;
  const isFlss = isFlssTurnContext(turnData) || meta.event === 'flss_vo';
  if (!isFlss || !isFinalShotSfxExcludedOnFlss(filename)) {
    return filename;
  }
  return resolveFlssCoachVoFile({
    flssHeaveSfx: Boolean(turnData?.flss_heave_sfx),
  });
}
