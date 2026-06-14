/**
 * Canonical player class year formatting (JH, FR, SO, JR, SR, GR).
 * Attach as global GOB_PlayerYear.
 */
(function (global) {
  'use strict';

  var YEAR_SORT_ORDER = { JH: 0, Freshman: 1, Sophomore: 2, Junior: 3, Senior: 4, Graduate: 5 };
  var YEAR_ABBREV = { JH: 'JH', Freshman: 'FR', Sophomore: 'SO', Junior: 'JR', Senior: 'SR', Graduate: 'GR' };
  var ALIASES = {
    jh: 'JH',
    freshman: 'Freshman',
    fr: 'Freshman',
    sophomore: 'Sophomore',
    so: 'Sophomore',
    junior: 'Junior',
    jr: 'Junior',
    senior: 'Senior',
    sr: 'Senior',
    graduate: 'Graduate',
    grad: 'Graduate'
  };

  function normalizeYear(year) {
    if (year == null || year === '') return null;
    var raw = String(year).trim();
    if (!raw || raw === '--') return null;
    if (ALIASES[raw.toLowerCase()]) return ALIASES[raw.toLowerCase()];
    if (/^[a-zA-Z]+$/.test(raw)) {
      return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
    }
    return raw;
  }

  function formatAbbrev(year) {
    var normalized = normalizeYear(year);
    if (!normalized) return '--';
    return YEAR_ABBREV[normalized] || normalized;
  }

  function formatDisplay(year) {
    return formatAbbrev(year);
  }

  function getSortValue(year) {
    var normalized = normalizeYear(year);
    return normalized != null && YEAR_SORT_ORDER[normalized] != null
      ? YEAR_SORT_ORDER[normalized]
      : -1;
  }

  global.GOB_PlayerYear = {
    normalizeYear: normalizeYear,
    formatDisplay: formatDisplay,
    formatAbbrev: formatAbbrev,
    getSortValue: getSortValue
  };
})(typeof window !== 'undefined' ? window : globalThis);
