/**
 * Canonical, reversible RT display experiment.
 *
 * RT stays numeric in data and logic. Only final display formatting changes.
 * The canonical switch lives in common.js; this fallback covers pages that
 * load the helper first or do not load common.js.
 *
 * Loaded as a classic script (no module export) for ES modules and IIFE pages.
 */
(function (global) {
  if (!global.RT_DISPLAY_MODE) global.RT_DISPLAY_MODE = 'letter';

  function numericRt(rt) {
    if (rt === null || rt === undefined || rt === '') return null;
    var v = Number(rt);
    return isFinite(v) ? v : null;
  }

  function getRtLetterGrade(rt) {
    var v = numericRt(rt);
    if (v === null) return '--';
    if (v >= 100) return 'A++';
    if (v >= 90) return 'A+';
    if (v >= 80) return 'A';
    if (v >= 70) return 'B+';
    if (v >= 60) return 'B';
    if (v >= 50) return 'C+';
    if (v >= 40) return 'C';
    return 'F';
  }

  function formatRtDisplay(rt) {
    var v = numericRt(rt);
    if (v === null) return '--';
    return global.RT_DISPLAY_MODE === 'letter' ? getRtLetterGrade(v) : String(rt);
  }

  function getRtBucketClass(rt) {
    var v = numericRt(rt);
    if (v === null) return 'rt-unknown';
    if (v < 40) return 'rt-low';
    if (v < 60) return 'rt-mid';
    if (v < 80) return 'rt-high';
    return 'rt-elite';
  }

  function getRecruitRtBucketClass(rt) {
    return getRtBucketClass(rt);
  }

  function getRecruitRtBucketClassForYear(rt, year) {
    return getRtBucketClass(rt);
  }

  function getRtColor(rt) {
    var cls = getRtBucketClass(rt);
    if (cls === 'rt-elite') return '#4A90D9';
    if (cls === 'rt-high') return '#34EC27';
    if (cls === 'rt-mid') return '#FFD700';
    if (cls === 'rt-low') return '#ff6d6d';
    return 'rgba(255, 255, 255, 0.4)';
  }

  global.getRtLetterGrade = getRtLetterGrade;
  global.formatRtDisplay = formatRtDisplay;
  global.getRtBucketClass = getRtBucketClass;
  global.getRecruitRtBucketClass = getRecruitRtBucketClass;
  global.getRecruitRtBucketClassForYear = getRecruitRtBucketClassForYear;
  global.getRtColor = getRtColor;
})(typeof window !== 'undefined' ? window : this);
