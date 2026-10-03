/**
 * Box-score MIN. The stat is seconds; the table shows whole minutes.
 */
(function (global) {
  'use strict';

  function formatMinutes(seconds) {
    if (!seconds) return '0';
    return Math.floor(Number(seconds) / 60).toString();
  }

  global.formatMinutes = formatMinutes;
})(typeof window !== 'undefined' ? window : this);
