/**
 * Attribute tiles — the single builder for the 12-attribute display.
 *
 * One implementation so the surfaces that show attributes as tiles cannot drift:
 *   - Recruits screen (Recruiting Hub pool)
 *   - FCC Roster tab
 *   - FCC Recruits tab
 *   - team-roster-view.html
 *
 * Everything else that displays attributes is deliberately untouched.
 *
 * Display rules (product-wide):
 *   - Values render on the 0-10 scale, preferring the `anchor_<KEY>` value.
 *   - Tier colours: 10+ brand blue (#4A90D9), 7-9 green, <=3 red, otherwise neutral.
 *   - Hover shows the full attribute name and the 10-scale value, e.g. "Rebounding: 6".
 *
 * The tooltip is delivered via `data-tooltip`, which the shared attributeTooltips.js
 * honours verbatim — so a surface only needs to call initAttributeTooltips() over the
 * tiles after rendering.
 *
 * Loaded as a classic script: window.GOB_AttrTiles.
 */
(function (global) {
  'use strict';

  var ATTR_KEYS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

  // Kept in step with ATTRIBUTE_NAMES in attributeTooltips.js, which is the canonical
  // abbreviation map. Only the 12 roster attributes are needed here.
  var ATTR_FULL_NAMES = {
    SC: 'Scoring',
    SH: 'Shooting',
    ID: 'Inside Defense',
    OD: 'Outside Defense',
    PS: 'Passing',
    BH: 'Ball Handling',
    RB: 'Rebounding',
    AG: 'Agility',
    ST: 'Strength',
    ND: 'Endurance',
    IQ: 'Basketball IQ',
    FT: 'Free Throws',
  };

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /** 0-10 display value, anchor-aware. Returns null when the attribute is absent. */
  function tileValue(attrs, key) {
    var raw = (attrs || {})['anchor_' + key];
    if (raw == null || raw === '') raw = (attrs || {})[key];
    if (raw == null || raw === '') return null;
    var num = Number(raw);
    if (isNaN(num)) return null;
    return Math.floor(num / 10);
  }

  /** Tier class. 10+ takes the brand RT display blue. */
  function tierClass(value) {
    if (value == null) return '';
    if (value >= 10) return 'is-elite';
    if (value >= 7) return 'is-hi';
    if (value <= 3) return 'is-lo';
    return '';
  }

  function tooltipFor(key, value) {
    var name = ATTR_FULL_NAMES[key] || key;
    return name + ': ' + (value == null ? '--' : value);
  }

  /** One tile. `showLabel` false renders value-only (unused today; kept for callers). */
  function tileHtml(key, value, showLabel) {
    var display = value == null ? '--' : value;
    var label = showLabel === false ? '' : '<u>' + escapeHtml(key) + '</u>';
    return '<span class="attr-tile ' + tierClass(value) + '"' +
      ' data-attr="' + escapeHtml(key) + '"' +
      ' data-tooltip="' + escapeHtml(tooltipFor(key, value)) + '">' +
      label + '<s>' + escapeHtml(display) + '</s></span>';
  }

  /** The full 12-tile row for one player. */
  function tilesHtml(attrs, opts) {
    var options = opts || {};
    return '<div class="attr-tiles">' + ATTR_KEYS.map(function (key) {
      return tileHtml(key, tileValue(attrs, key), options.showLabel);
    }).join('') + '</div>';
  }

  /** Convenience: a <td> wrapping the tile row, for table surfaces. */
  function tilesCellHtml(attrs, opts) {
    return '<td class="attr-tiles-cell">' + tilesHtml(attrs, opts) + '</td>';
  }

  /** Header cell replacing the 12 individual abbreviation columns. */
  function tilesHeaderHtml(colspan) {
    return '<th class="attr-tiles-head"' + (colspan ? ' colspan="' + colspan + '"' : '') +
      '>Attributes</th>';
  }

  var api = {
    ATTR_KEYS: ATTR_KEYS,
    ATTR_FULL_NAMES: ATTR_FULL_NAMES,
    tileValue: tileValue,
    tierClass: tierClass,
    tooltipFor: tooltipFor,
    tileHtml: tileHtml,
    tilesHtml: tilesHtml,
    tilesCellHtml: tilesCellHtml,
    tilesHeaderHtml: tilesHeaderHtml,
  };

  if (global) global.GOB_AttrTiles = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : null));
