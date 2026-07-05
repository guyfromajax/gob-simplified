/**
 * End-of-quarter airhorn — unified entry for all quarter-end paths.
 *
 * Eligibility: `quarter_ends_after === true` OR (`clock_end === 0` && `clock_start > 0`).
 * Dedupe: once per turn index (`scene._endOfQuarterAirhornTurnKeys`).
 *
 * Phase:
 *   - `clockTween` — AnimationRouter linear clock interpolation; defers when
 *     `quarter_ends_after` so schema / FT / hold playback can horn at visual end.
 *   - `playbackComplete` — after turn animation finishes (Final Turn, FLSS, FT, hold, run-out).
 */

function resolveTurnKey(scene, turnData) {
  const key = turnData?.index ?? turnData?.turnIndex ?? scene?.currentTurn;
  if (key === undefined || key === null || key === '') {
    return '';
  }
  return String(key);
}

function isQuarterEndEligible(turnData) {
  if (turnData?.quarter_ends_after === true) {
    return true;
  }
  const clockEnd = Number(turnData?.clock_end ?? turnData?.clockEnd);
  const clockStart = Number(turnData?.clock_start ?? turnData?.clockStart);
  return (
    Number.isFinite(clockEnd)
    && clockEnd === 0
    && Number.isFinite(clockStart)
    && clockStart > 0
  );
}

function shouldDeferToPlayback(turnData, phase) {
  return phase === 'clockTween' && turnData?.quarter_ends_after === true;
}

function playAirhornSound() {
  const staticPath = (window.API_CONFIG && typeof window.API_CONFIG.getStaticPath === 'function')
    ? window.API_CONFIG.getStaticPath()
    : '/static';
  const airhorn = new Audio(`${staticPath}/sounds/airhorn-lowervol.wav`);
  airhorn.volume = 0.7;
  airhorn.currentTime = 0;
  airhorn.play().catch(() => {});
}

/**
 * Play the end-of-quarter airhorn when this turn ends the period.
 *
 * @param {object} scene
 * @param {object} turnData
 * @param {{ phase?: 'clockTween'|'playbackComplete' }} [options]
 * @returns {boolean} true when the horn was played
 */
export function signalQuarterEnded(scene, turnData = {}, options = {}) {
  if (typeof window === 'undefined' || scene?.skipToEnd) {
    return false;
  }

  const phase = options.phase === 'clockTween' ? 'clockTween' : 'playbackComplete';

  if (!isQuarterEndEligible(turnData)) {
    return false;
  }
  if (shouldDeferToPlayback(turnData, phase)) {
    return false;
  }

  const turnKey = resolveTurnKey(scene, turnData);
  if (!turnKey) {
    return false;
  }

  if (!scene._endOfQuarterAirhornTurnKeys) {
    scene._endOfQuarterAirhornTurnKeys = new Set();
  }
  if (scene._endOfQuarterAirhornTurnKeys.has(turnKey)) {
    return false;
  }
  scene._endOfQuarterAirhornTurnKeys.add(turnKey);

  try {
    playAirhornSound();
  } catch (e) {
    return false;
  }

  return true;
}

/** @deprecated Prefer `signalQuarterEnded`; kept for existing imports/tests. */
export function playEndOfQuarterAirhorn(scene, turnData = {}) {
  return signalQuarterEnded(scene, turnData, { phase: 'playbackComplete' });
}
