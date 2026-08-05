/**
 * Team Builder shared constants — Identity + Gate chapters.
 * PROGRAM_NAME_MAX_LEN mirrors BackEnd.constants.team_builder_budget.
 */
(function (global) {
  'use strict';

  var PROGRAM_NAME_MAX_LEN = 23;
  var MASCOT_MAX_LEN = 20;
  var ABBR_LEN = 3;
  var ABBR_CHECK_MS = 480;
  var COURT_RENDER_MS = 140;
  var DRAFT_SAVE_MS = 600;

  /** Fixed court line color — generator COLORS.line; never user-editable. */
  var COURT_LINE_COLOR = '#6e675f';

  /**
   * Custom inside-wood vs COURT_LINE_COLOR must meet WCAG contrast ratio ≥ 3.0
   * (non-text / graphical-object floor). Measured 2026-08-05:
   * grain overlays drop interior median contrast ~0.12–0.18 from the flat swatch
   * (worst single stroke ~0.30 near the boundary). A flat-swatch floor of 3.0
   * lands effective contrast in the same band as shipping medium hardwood
   * (#DBB891 ≈ 2.99 flat), which still reads the 3PT arc at Identity display
   * width (~880px). Do not raise without a failed visual re-check.
   * Applies to custom colours only — stock hardwood style keys are exempt by
   * measurement (already on ~120 courts); extending the validator to keys would
   * make medium illegal league-wide. Client feedback + Apply refusal;
   * teamCourtGenerator.js stays dumb.
   */
  var INSIDE_WOOD_LINE_CONTRAST_MIN = 3.0;

  var CHAPTERS = ['identity', 'gate', 'roster', 'review', 'establish'];

  var BANNER_VARIANTS = [
    { key: 'keel', name: 'Keel' },
    { key: 'baseline', name: 'Baseline' },
    { key: 'plate', name: 'Plate' },
    { key: 'sash', name: 'Sash' },
  ];

  var DEFAULT_BANNER_VARIANT = 'baseline';

  var PALETTES = [
    { name: 'Cascade', p: '#1e5a8c', s: '#f2a83b' },
    { name: 'Ridge', p: '#1f3a2e', s: '#c9a227' },
    { name: 'Foundry', p: '#8c1d26', s: '#e8dcc3' },
    { name: 'Meridian', p: '#2c1b4d', s: '#e0b94a' },
    { name: 'Tidewater', p: '#0f4c4a', s: '#de6b35' },
    { name: 'Sandstone', p: '#a6462c', s: '#1b2733' },
    { name: 'Glacier', p: '#124e78', s: '#a8c6df' },
    { name: 'Ironwood', p: '#2b2b2b', s: '#d9a13b' },
  ];

  var SWATCHES = [
    '#1e5a8c',
    '#124e78',
    '#1f3a2e',
    '#0f4c4a',
    '#2c1b4d',
    '#8c1d26',
    '#a6462c',
    '#2b2b2b',
    '#f2a83b',
    '#c9a227',
    '#de6b35',
    '#e8dcc3',
  ];

  var HARDWOOD_TONES_KEYS = ['light', 'medium', 'dark'];

  /** Core-12 attribute codes — ND is Endurance (display); key stays ND. */
  var CORE_12_ATTRS = [
    { code: 'SC', name: 'Scoring', cat: 'offense' },
    { code: 'SH', name: 'Shooting', cat: 'offense' },
    { code: 'ID', name: 'Inside Defense', cat: 'defense' },
    { code: 'OD', name: 'Outside Defense', cat: 'defense' },
    { code: 'PS', name: 'Passing', cat: 'technical' },
    { code: 'BH', name: 'Ball Handling', cat: 'technical' },
    { code: 'RB', name: 'Rebounding', cat: 'technical' },
    { code: 'ST', name: 'Strength', cat: 'physical' },
    { code: 'AG', name: 'Agility', cat: 'physical' },
    { code: 'ND', name: 'Endurance', cat: 'endurance' },
    { code: 'IQ', name: 'Basketball IQ', cat: 'intangibles' },
    { code: 'FT', name: 'Free Throws', cat: 'intangibles' },
  ];

  /** Eleven RT-weighted keys — ND excluded from position-ratings payload. */
  var RT_ATTR_KEYS = [
    'AG',
    'BH',
    'FT',
    'ID',
    'IQ',
    'OD',
    'PS',
    'RB',
    'SC',
    'SH',
    'ST',
  ];

  var ATTR_CATS = {
    offense: { label: 'Offense', color: '#f79420' },
    defense: { label: 'Defense', color: '#4a90d9' },
    technical: { label: 'Technical', color: '#7b5ea7' },
    physical: { label: 'Physical', color: '#aeb8cc' },
    endurance: { label: 'Endurance', color: '#34ec27' },
    intangibles: { label: 'Intangibles', color: '#d4a017' },
  };

  /**
   * Exact copy for the ND control — do not paraphrase, do not reuse elsewhere.
   * Display term is Endurance; never "Natural Durability".
   */
  var ENDURANCE_COPY =
    "Endurance doesn't raise his position ratings — it protects them. Fatigue drags his other attributes down as a game wears on; this slows that, and makes him less likely to foul on defense.";

  var POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];
  var POS_COLOR = {
    PG: '#4A90D9',
    SG: '#7B5EA7',
    SF: '#3A8C4A',
    PF: '#C0392B',
    C: '#D4A017',
  };
  var CLASSES = ['FR', 'SO', 'JR', 'SR'];

  var ATTR_MIN = 5;
  var ATTR_MAX = 99;
  var TOPUP_FLOOR = 60;
  var HEIGHT_MIN_IN = 66;
  var HEIGHT_MAX_IN = 84;
  var RATINGS_DEBOUNCE_MS = 480;
  var AUTHORED_ROSTER_SIZE = 15;
  var SCHOLARSHIP_SIZE = 12;

  var SURPRISE = [
    ['Cascade Valley', 'Timberwolves', 0],
    ['Ironwood State', 'Prospectors', 7],
    ['Puget Bay', 'Mariners', 6],
    ['Marrow Creek', 'Ravens', 1],
    ['Fort Hollis', 'Sentinels', 3],
    ['Larkspur', 'Cardinals', 2],
    ['Alderton', 'Foundry', 5],
    ['Bell Harbor', 'Anchors', 4],
  ];

  function defaultIdentity() {
    var p = '#1e5a8c';
    var s = '#f2a83b';
    var d =
      global.TeamCourtGenerator && typeof global.TeamCourtGenerator.defaultsFromTeamColors === 'function'
        ? global.TeamCourtGenerator.defaultsFromTeamColors(p, s)
        : {
            oobColor: p,
            laneColor: p,
            outsideWoodColor: '#DBB891',
            halfArcFillColor: s,
          };
    var mid = (global.TeamCourtGenerator && global.TeamCourtGenerator.HARDWOOD_TONES) || {
      light: '#EAD8C6',
      medium: '#DBB891',
      dark: '#CB9D76',
    };
    return {
      name: '',
      mascot: '',
      abbreviation: '',
      abbr_touched: false,
      primary: p,
      secondary: s,
      jersey_preset: 2,
      banner_variant: DEFAULT_BANNER_VARIANT,
      inside: 'medium',
      outside: 'medium',
      oob: 'Primary',
      lane: 'Primary',
      arc: 'Secondary',
      oob_custom: d.oobColor || p,
      lane_custom: p,
      outside_custom: d.outsideWoodColor || mid.medium,
      inside_custom: mid.medium,
      arc_custom: s,
    };
  }

  global.TeamBuilderConstants = {
    PROGRAM_NAME_MAX_LEN: PROGRAM_NAME_MAX_LEN,
    MASCOT_MAX_LEN: MASCOT_MAX_LEN,
    ABBR_LEN: ABBR_LEN,
    ABBR_CHECK_MS: ABBR_CHECK_MS,
    COURT_RENDER_MS: COURT_RENDER_MS,
    DRAFT_SAVE_MS: DRAFT_SAVE_MS,
    COURT_LINE_COLOR: COURT_LINE_COLOR,
    INSIDE_WOOD_LINE_CONTRAST_MIN: INSIDE_WOOD_LINE_CONTRAST_MIN,
    CHAPTERS: CHAPTERS,
    BANNER_VARIANTS: BANNER_VARIANTS,
    DEFAULT_BANNER_VARIANT: DEFAULT_BANNER_VARIANT,
    PALETTES: PALETTES,
    SWATCHES: SWATCHES,
    HARDWOOD_TONES_KEYS: HARDWOOD_TONES_KEYS,
    CORE_12_ATTRS: CORE_12_ATTRS,
    RT_ATTR_KEYS: RT_ATTR_KEYS,
    ATTR_CATS: ATTR_CATS,
    ENDURANCE_COPY: ENDURANCE_COPY,
    POSITIONS: POSITIONS,
    POS_COLOR: POS_COLOR,
    CLASSES: CLASSES,
    ATTR_MIN: ATTR_MIN,
    ATTR_MAX: ATTR_MAX,
    TOPUP_FLOOR: TOPUP_FLOOR,
    HEIGHT_MIN_IN: HEIGHT_MIN_IN,
    HEIGHT_MAX_IN: HEIGHT_MAX_IN,
    RATINGS_DEBOUNCE_MS: RATINGS_DEBOUNCE_MS,
    AUTHORED_ROSTER_SIZE: AUTHORED_ROSTER_SIZE,
    SCHOLARSHIP_SIZE: SCHOLARSHIP_SIZE,
    SURPRISE: SURPRISE,
    defaultIdentity: defaultIdentity,
  };
})(typeof window !== 'undefined' ? window : globalThis);
