/**
 * Team shot_threshold attribute scale — keep in sync with
 * BackEnd/constants/shot_threshold_scale.py (change MIN there and here).
 *
 * Lower raw = better shooting. Pills center at MID; fill right when raw decreases.
 */
(function (global) {
  const SPAN = 200;
  const HALF_SPAN = SPAN / 2;
  const MIN = 30;
  const MAX = MIN + SPAN;
  const MID = MIN + HALF_SPAN;

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
