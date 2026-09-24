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
 * Display rules (product-wide, via GOB_AttributeDisplay):
 *   - Values render as the first digit of the raw attribute (floor of raw/10),
 *     preferring anchor_<KEY>. Uncapped: 105 → 10, 160 → 16. 0 is valid.
 *   - Tier colours follow the displayed value: 0–4 low, 5–6 mid, 7–8 high, 9+ elite.
 *   - Hover shows the full attribute name and that displayed value, e.g. "Rebounding: 6".
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

  /**
   * PRESENTATION-ONLY pairing. Twelve identical tiles read as a barcode; six labelled
   * pairs read as chunks.
   *
   * Deliberately separate from ATTR_KEYS, which MUST NOT be reordered: the display
   * pairing needs RB,ST then AG,ND, while ATTR_KEYS has AG before ST to match the
   * backend roster_builder order that SCOUTING_PROJECTED_ATTR_COLS also mirrors.
   * Reordering the shared array to get the pairing would shift those consumers.
   */
  var ATTR_PAIRS = [
    { label: 'OFFENSE', keys: ['SC', 'SH'] },
    { label: 'DEFENSE', keys: ['ID', 'OD'] },
    { label: 'SKILLS', keys: ['PS', 'BH'] },
    { label: 'GRIT', keys: ['RB', 'ST'] },
    { label: 'BODY', keys: ['AG', 'ND'] },
    { label: 'MIND', keys: ['IQ', 'FT'] },
  ];

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /** Displayed attribute, anchor-aware. Null when the attribute is absent. */
  function tileValue(attrs, key) {
    var ad = global.GOB_AttributeDisplay;
    return ad.displayAttr(ad.rawAttr(attrs, key));
  }

  /** Tier class from the displayed value. 9+ is elite blue. */
  function tierClass(value) {
    var tier = global.GOB_AttributeDisplay.attrTier(value);
    if (tier === 'elite') return 'is-elite';
    if (tier === 'high') return 'is-hi';
    if (tier === 'mid') return 'is-mid';
    if (tier === 'low') return 'is-lo';
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

  // ── Grouped variants (Roster / Recruiting / standalone roster) ────────────────
  // Tiles render WITHOUT their inner label here: the abbreviation prints once in the
  // header instead of twelve times per row. Hover identification is unaffected —
  // every tile still carries data-tooltip.

  /** Six labelled pairs of label-less tiles, for one player. */
  function groupedTilesHtml(attrs) {
    return '<div class="attr-grid">' + ATTR_PAIRS.map(function (pair) {
      return '<div class="attr-pair">' + pair.keys.map(function (key) {
        return tileHtml(key, tileValue(attrs, key), false);
      }).join('') + '</div>';
    }).join('') + '</div>';
  }

  function groupedTilesCellHtml(attrs) {
    return '<td class="attr-tiles-cell">' + groupedTilesHtml(attrs) + '</td>';
  }

  /**
   * Two-row grouped header: pair labels above, per-attribute sort controls below.
   * `sort` is { key, dir } so the active control can show its caret.
   */
  function groupedHeaderHtml(sort) {
    var active = (sort && sort.key) || '';
    var dir = (sort && sort.dir) || 'desc';
    // The group label nests INSIDE its pair, so `grid-column: 1 / -1` spans the pair's
    // two columns. As a direct child of .attr-grid it spanned all six and forced its own
    // full-width row, stacking the header into one tall column.
    return '<div class="attr-grid attr-grid--head">' + ATTR_PAIRS.map(function (pair) {
      var labels = '<div class="attr-grp">' + escapeHtml(pair.label) + '</div>';
      var controls = pair.keys.map(function (key) {
        var isSorted = key === active;
        return '<button type="button" class="attr-abbr' + (isSorted ? ' is-sorted' : '') + '"' +
          ' data-attr-sort="' + escapeHtml(key) + '"' +
          (isSorted ? ' data-dir="' + escapeHtml(dir) + '"' : '') +
          ' data-tooltip="' + escapeHtml(ATTR_FULL_NAMES[key] || key) + '"' +
          ' aria-label="Sort by ' + escapeHtml(ATTR_FULL_NAMES[key] || key) + '">' +
          escapeHtml(key) + '</button>';
      }).join('');
      return '<div class="attr-pair">' + labels + controls + '</div>';
    }).join('') + '</div>';
  }

  /** Sort comparator on the DISPLAYED 0-10 value, so ties behave as the user sees them. */
  function compareByAttr(a, b, key, dir) {
    var av = tileValue(a, key);
    var bv = tileValue(b, key);
    if (av == null) av = -1;
    if (bv == null) bv = -1;
    return dir === 'asc' ? av - bv : bv - av;
  }

  var api = {
    ATTR_KEYS: ATTR_KEYS,
    ATTR_PAIRS: ATTR_PAIRS,
    groupedTilesHtml: groupedTilesHtml,
    groupedTilesCellHtml: groupedTilesCellHtml,
    groupedHeaderHtml: groupedHeaderHtml,
    compareByAttr: compareByAttr,
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
