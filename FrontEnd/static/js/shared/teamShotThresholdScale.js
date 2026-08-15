/**
 * Team shot_threshold attribute scale — keep in sync with
 * BackEnd/constants/shot_threshold_scale.py (change MIN there and here).
 *
 * Lower raw = better shooting. Pills center at MID; fill right when raw decreases.
 */
(function (global) {
  // Mirror of BackEnd/constants/shot_threshold_scale.py. Change MIN there first, then
  // restate MAX and MID here as LITERALS — tests/test_shot_threshold_scale.py greps for
  // `const MAX = <n>` so the values stay eyeballable against the Python side.
  const SPAN = 200;
  const HALF_SPAN = SPAN / 2;
  const MIN = -10;
  const MAX = 190;
  const MID = 90;

  function pillDeviation(raw) {
    return MID - Number(raw);
  }

  function pillFillFromRaw(raw) {
    return {
      maxValue: HALF_SPAN,
      value: pillDeviation(raw),
    };
  }

  function pillFillPercent(raw) {
    return Math.min((Math.abs(pillDeviation(raw)) / HALF_SPAN) * 50, 50);
  }

  /** Normalized −10..+10 score for FCC card tone (positive = better shooting). */
  function normalizedScore(raw) {
    return (pillDeviation(raw) / HALF_SPAN) * 10;
  }

  function invertDelta(rawDelta) {
    return -Number(rawDelta);
  }

  function shouldPulse(raw, threshold) {
    return Math.abs(pillDeviation(raw)) >= (threshold == null ? 30 : threshold);
  }

  global.TeamShotThresholdScale = {
    SPAN,
    HALF_SPAN,
    MIN,
    MAX,
    MID,
    pillDeviation,
    pillFillFromRaw,
    pillFillPercent,
    normalizedScore,
    invertDelta,
    shouldPulse,
  };
})(typeof window !== 'undefined' ? window : globalThis);
