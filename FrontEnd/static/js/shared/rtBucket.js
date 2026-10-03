/**
 * Canonical, reversible RT display experiment.
 *
 * RT stays numeric in data and logic. Only final display formatting changes.
 * This file owns the canonical bands and the letter/number switch. The colours are
 * gob tokens (`token`); `color` is the same value as a literal, for scripts that need
 * a concrete colour (canvas, inline bars) and for pages with no gob tokens.
 * tests/test_token_mirrors.py keeps the two equal.
 *
 * Loaded as a classic script (no module export) for ES modules and IIFE pages.
 */
(function (global) {
  global.RT_DISPLAY_MODE = 'letter';
  var RT_BANDS = Object.freeze([
    Object.freeze({ minimum: 100, grade: 'A++', className: 'rt-elite', color: '#4A90D9', token: '--blue' }),
    Object.freeze({ minimum: 90, grade: 'A+', className: 'rt-elite', color: '#4A90D9', token: '--blue' }),
    Object.freeze({ minimum: 80, grade: 'A', className: 'rt-elite', color: '#4A90D9', token: '--blue' }),
    Object.freeze({ minimum: 70, grade: 'B+', className: 'rt-high', color: '#34EC27', token: '--tier-green' }),
    Object.freeze({ minimum: 60, grade: 'B', className: 'rt-high', color: '#34EC27', token: '--tier-green' }),
    Object.freeze({ minimum: 50, grade: 'C+', className: 'rt-mid', color: '#FFD700', token: '--tier-yellow' }),
    Object.freeze({ minimum: 40, grade: 'C', className: 'rt-mid', color: '#FFD700', token: '--tier-yellow' }),
    Object.freeze({ minimum: 30, grade: 'D', className: 'rt-low', color: '#ff6d6d', token: '--tier-red' }),
    Object.freeze({ minimum: -Infinity, grade: 'F', className: 'rt-low', color: '#ff6d6d', token: '--tier-red' })
  ]);

  if (global.document && global.document.documentElement) {
    RT_BANDS.forEach(function (band) {
      // The .rt-* classes read the token; the literal is the fallback on a page without gob tokens.
      global.document.documentElement.style.setProperty(
        '--' + band.className + '-color',
        'var(' + band.token + ', ' + band.color + ')'
      );
    });
  }

  function numericRt(rt) {
    if (rt === null || rt === undefined || rt === '') return null;
    var v = Number(rt);
    return isFinite(v) ? v : null;
  }

  function getRtPresentation(rt) {
    var v = numericRt(rt);
    if (v === null) {
      return { grade: '--', className: 'rt-unknown', color: 'rgba(255, 255, 255, 0.4)' };
    }
    return RT_BANDS.find(function (band) { return v >= band.minimum; });
  }

  function getRtLetterGrade(rt) {
    return getRtPresentation(rt).grade;
  }

  function formatRtDisplay(rt) {
    var v = numericRt(rt);
    if (v === null) return '--';
    return global.RT_DISPLAY_MODE === 'letter' ? getRtLetterGrade(v) : String(rt);
  }

  /**
   * Format the display-only current/potential pair through the same canonical
   * RT mapping. Potential is an already-ratcheted ceiling supplied by the
   * backend; missing potential deliberately falls back to current alone.
   */
  function formatRtWithPotentialDisplay(rt, potentialRt) {
    var current = numericRt(rt);
    if (current === null) return '--';
    var potential = numericRt(potentialRt);
    return potential === null
      ? formatRtDisplay(rt)
      : formatRtDisplay(rt) + '/' + formatRtDisplay(potentialRt);
  }

  function getRtBucketClass(rt) {
    return getRtPresentation(rt).className;
  }

  function getRecruitRtBucketClass(rt) {
    return getRtBucketClass(rt);
  }

  function getRecruitRtBucketClassForYear(rt, year) {
    return getRtBucketClass(rt);
  }

  function getRtColor(rt) {
    return getRtPresentation(rt).color;
  }

  global.getRtPresentation = getRtPresentation;
  global.getRtLetterGrade = getRtLetterGrade;
  global.formatRtDisplay = formatRtDisplay;
  global.formatRtWithPotentialDisplay = formatRtWithPotentialDisplay;
  global.getRtBucketClass = getRtBucketClass;
  global.getRecruitRtBucketClass = getRecruitRtBucketClass;
  global.getRecruitRtBucketClassForYear = getRecruitRtBucketClassForYear;
  global.getRtColor = getRtColor;
})(typeof window !== 'undefined' ? window : this);
