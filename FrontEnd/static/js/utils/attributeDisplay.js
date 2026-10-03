/**
 * First-digit attribute display.
 *
 * Attributes are stored raw (hard minimum 1, no upper cap). Every surface shows
 * the first digit: Math.floor(raw / 10). Raw 1–9 → 0, 77 → 7, 99 → 9, 105 → 10,
 * 160 → 16. 0 is a valid display. There is no upper cap.
 *
 * Tier is the displayed value: 0–4 low, 5–6 mid, 7–8 high, 9+ elite.
 *
 * Read precedence matches the tile builder: anchor_<KEY>, then <KEY>.
 * null, undefined, and '' fall through; 0 is a real value.
 *
 * Classic script: window.GOB_AttributeDisplay. Also module.exports for node tests.
 * Load this before attrTiles.js and before any page script that formats attributes.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (root) root.GOB_AttributeDisplay = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';

  function rawAttr(attrs, key) {
    var bag = attrs || {};
    var raw = bag['anchor_' + key];
    if (raw == null || raw === '') raw = bag[key];
    if (raw == null || raw === '') return null;
    return raw;
  }

  function displayAttr(raw) {
    if (raw == null || raw === '') return null;
    var n = Number(raw);
    if (!isFinite(n)) return null;
    return Math.floor(n / 10);
  }

  function attrTier(display) {
    if (display == null || display === '') return null;
    var d = Number(display);
    if (!isFinite(d)) return null;
    if (d >= 9) return 'elite';
    if (d >= 7) return 'high';
    if (d >= 5) return 'mid';
    return 'low';
  }

  return {
    rawAttr: rawAttr,
    displayAttr: displayAttr,
    attrTier: attrTier,
  };
});
