/* ============================================================================
 * GOB Tournament Tier Emblem — shared renderer
 * ----------------------------------------------------------------------------
 * One resolver, consumed by every surface (FCC franchise header, FCC Next/Last
 * Game card headers, court scoreboard). Do NOT re-draw the marks per surface —
 * call renderEmblem / renderLockup here.
 *
 * Geometry, metal tokens, and per-surface sizing are extracted VERBATIM from the
 * Claude Design source of truth (_documentation_master/projects/emblem_example.js,
 * itself lifted from "Tournament In-Situ (FCC + Court).html"). Do not hand-tune
 * the coordinates — change the mock, re-extract.
 *
 * The mark is a tier FRAME (crest / hexagon badge / ringed medallion) + a CENTER
 * (the conference number or region letter for Conference/Region, or a star
 * cluster). Two-tone (metal frame + dark field) at >=~28px; single-color "mono"
 * stamp at <=20px. All coordinates live in a 0 0 100 120 viewBox; the rendered
 * box is size wide by size*1.2 tall.
 *
 * Gold is a fixed tier constant. NATIONAL uses #D4A848 to match the existing
 * bracket token (--gold / .fcc-tb-*). Metals never inherit team color.
 *
 * Exposed as window.GOBTierEmblem (same pattern as window.GOBArchetype) so both
 * the classic-script FCC and the module-based court can consume it.
 * ==========================================================================*/
(function (global) {
  'use strict';

  /* ---- Metal + shape tokens per tier -------------------------------------- */
  var TIER_TOKENS = {
    conference: { shape: 'crest',     stars: 1, metal: '#C79A5B', metalHi: '#EAC488', fieldA: '#F6DFAE', fieldB: '#9c7434', glow: 'rgba(199,154,91,0.5)',  word: 'CONFERENCE' },
    region:     { shape: 'badge',     stars: 2, metal: '#B9C1CD', metalHi: '#F0F4FA', fieldA: '#FFFFFF', fieldB: '#8b929e', glow: 'rgba(200,212,228,0.5)', word: 'REGION' },
    national:   { shape: 'medallion', stars: 3, metal: '#D4A848', metalHi: '#F0C560', fieldA: '#F7E3A0', fieldB: '#9c7a1e', glow: 'rgba(212,168,72,0.55)', word: 'NATIONAL' }
  };

  /* Per-surface sizing used in the approved mock. Match these. */
  var EMBLEM_SIZING = {
    fccFranchiseHeader: { emblem: 52, labelL1: 19, labelL2: 11 },       // logo+emblem object, 2-line lockup
    fccGameCardHeader:  { emblem: 27, labelL1: 14, labelL2: 8.5, gap: 8 }, // Next/Last Game header, right-justified
    courtScoreboard:    { emblem: 16, mode: 'mono' },                    // round-label strip, monochrome
    minColorSize: 28,   // below this, use mode:'mono'
    monoMaxSize: 20
  };

  var _uid = 0;

  /* ---- primitives --------------------------------------------------------- */
  function starPath(cx, cy, r) {
    var ri = r * 0.42, p = '';
    for (var i = 0; i < 10; i++) {
      var rad = i % 2 === 0 ? r : ri;
      var a = -Math.PI / 2 + i * Math.PI / 5;
      p += (i ? 'L' : 'M') + (cx + rad * Math.cos(a)).toFixed(2) + ' ' + (cy + rad * Math.sin(a)).toFixed(2);
    }
    return p + 'Z';
  }
  function starCluster(n, cx, cy, R) {
    var s = function (x, y, r) { return '<path d="' + starPath(x, y, r) + '" fill="var(--st)"/>'; };
    if (n === 1) return s(cx, cy, R);
    if (n === 2) return s(cx - R * 0.82, cy, R * 0.74) + s(cx + R * 0.82, cy, R * 0.74);
    return s(cx, cy - R * 0.30, R * 0.92) + s(cx - R * 1.02, cy + R * 0.52, R * 0.60) + s(cx + R * 1.02, cy + R * 0.52, R * 0.60);
  }
  function glyphSVG(ch, cy) {
    return '<text x="50" y="' + (cy + 1) + '" text-anchor="middle" dominant-baseline="central" ' +
      'font-family="\'Bebas Neue Pro\',\'Bebas Neue\',sans-serif" font-weight="700" font-size="58" fill="var(--st)">' + ch + '</text>';
  }
  function frameShape(shape) {
    if (shape === 'crest')
      return '<path d="M14 12 H86 V60 C86 96 66 108 50 112 C34 108 14 96 14 60 Z" fill="var(--field)" stroke="var(--fr)" stroke-width="4" stroke-linejoin="round"/>';
    if (shape === 'badge')
      return '<path d="M27 13 H73 L91 60 L73 107 H27 L9 60 Z" fill="var(--field)" stroke="var(--fr)" stroke-width="4" stroke-linejoin="round"/>';
    // medallion: sunburst rays + double ring
    var rays = '';
    for (var i = 0; i < 28; i++) {
      var a = i / 28 * Math.PI * 2;
      rays += '<line x1="' + (50 + 50 * Math.cos(a)).toFixed(2) + '" y1="' + (60 + 50 * Math.sin(a)).toFixed(2) +
        '" x2="' + (50 + 55.5 * Math.cos(a)).toFixed(2) + '" y2="' + (60 + 55.5 * Math.sin(a)).toFixed(2) +
        '" stroke="var(--fr)" stroke-width="2.2"/>';
    }
    return rays +
      '<circle cx="50" cy="60" r="46" fill="var(--field)" stroke="var(--fr)" stroke-width="4"/>' +
      '<circle cx="50" cy="60" r="40" fill="none" stroke="var(--fr)" stroke-width="1.4" opacity="0.7"/>';
  }

  /* ---- public: render one emblem ------------------------------------------
   * opts:
   *   tier   'conference' | 'region' | 'national'   (required)
   *   value  conference number / region letter as a string. Ignored for national.
   *          If omitted for conference/region, the star cluster is shown instead.
   *   size   rendered width in px (height = size*1.2). Default 52.
   *   mode   'color' (two-tone, default) | 'mono' (single-color stamp for <=20px)
   * ------------------------------------------------------------------------- */
  function renderEmblem(opts) {
    opts = opts || {};
    var tier = opts.tier;
    var value = opts.value == null ? null : opts.value;
    var size = opts.size == null ? 52 : opts.size;
    var mode = opts.mode || 'color';
    var T = TIER_TOKENS[tier];
    if (!T) throw new Error('Unknown tier: ' + tier);
    var id = 'e' + (_uid++);
    var cy = T.shape === 'crest' ? 56 : 60;
    var useGlyph = tier !== 'national' && value != null && value !== '';
    var vars, defs = '';
    if (mode === 'mono') {
      vars = '--fr:' + T.metal + ';--st:' + T.metal + ';--field:transparent';
    } else {
      vars = '--fr:url(#fr' + id + ');--st:' + T.metalHi + ';--field:url(#fd' + id + ')';
      defs = '<defs>' +
        '<linearGradient id="fr' + id + '" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + T.fieldA + '"/><stop offset="1" stop-color="' + T.fieldB + '"/></linearGradient>' +
        '<radialGradient id="fd' + id + '" cx="0.5" cy="0.4" r="0.7"><stop offset="0" stop-color="#16161f"/><stop offset="1" stop-color="#07070d"/></radialGradient>' +
        '</defs>';
    }
    var center = useGlyph ? glyphSVG(String(value), cy) : starCluster(T.stars, 50, cy, T.shape === 'crest' ? 22 : 21);
    return '<svg width="' + size + '" height="' + (size * 1.2).toFixed(1) + '" viewBox="0 0 100 120" style="' + vars + '" fill="none">' +
      defs + frameShape(T.shape) + center + '</svg>';
  }

  /* ---- public: render an emblem + wordmark lockup -------------------------
   * The wordmark is always "<TIER> TOURNAMENT" and NEVER repeats the value —
   * the number/letter lives only inside the emblem.
   * opts:
   *   tier, value, size, mode  — as renderEmblem
   *   variant  'stack' (2-line: TIER / TOURNAMENT, default) | 'inline' (one line)
   *   l1, l2   optional font-size overrides in px for the two label lines
   * Returns an inline-flex span; pair with EMBLEM_CSS.
   * ------------------------------------------------------------------------- */
  function renderLockup(opts) {
    opts = opts || {};
    var tier = opts.tier;
    var value = opts.value == null ? null : opts.value;
    var size = opts.size == null ? 52 : opts.size;
    var variant = opts.variant || 'stack';
    var l1 = opts.l1 == null ? null : opts.l1;
    var l2 = opts.l2 == null ? null : opts.l2;
    var mode = opts.mode || 'color';
    var T = TIER_TOKENS[tier];
    if (!T) throw new Error('Unknown tier: ' + tier);
    var emb = renderEmblem({ tier: tier, value: value, size: size, mode: mode });
    var s1 = l1 ? ' style="font-size:' + l1 + 'px"' : '';
    var s2 = l2 ? ' style="font-size:' + l2 + 'px;letter-spacing:0.18em"' : '';
    if (variant === 'inline') {
      return '<span class="gob-lockup gob-lockup--inline" style="--m-hi:' + T.metalHi + '">' + emb +
        '<span class="gob-lk-one"' + s1 + '>' + T.word + ' TOURNAMENT</span></span>';
    }
    return '<span class="gob-lockup" style="--m-hi:' + T.metalHi + '">' + emb +
      '<span class="gob-lk-txt"><span class="gob-lk-l1"' + s1 + '>' + T.word + '</span>' +
      '<span class="gob-lk-l2"' + s2 + '>TOURNAMENT</span></span></span>';
  }

  /* ---- companion CSS ------------------------------------------------------
   * Fonts assumed present in the host page (Bebas Neue Pro / Bebas Neue).
   * ------------------------------------------------------------------------- */
  var EMBLEM_CSS = '' +
    '.gob-lockup{display:inline-flex;align-items:center;gap:11px}' +
    '.gob-lockup--inline{gap:8px}' +
    '.gob-lk-txt{display:flex;flex-direction:column;line-height:0.94}' +
    ".gob-lk-l1{font-family:'Bebas Neue Pro','Bebas Neue',sans-serif;font-weight:700;font-size:20px;letter-spacing:0.5px;color:#fff}" +
    ".gob-lk-l2{font-family:'Bebas Neue Pro','Bebas Neue',sans-serif;font-size:11px;letter-spacing:0.28em;color:var(--m-hi);margin-top:3px}" +
    ".gob-lk-one{font-family:'Bebas Neue Pro','Bebas Neue',sans-serif;font-size:14px;letter-spacing:0.1em;color:#fff;white-space:nowrap}";

  var _cssInjected = false;
  function injectCss() {
    if (_cssInjected || typeof document === 'undefined') return;
    _cssInjected = true;
    var style = document.createElement('style');
    style.id = 'gob-tier-emblem-css';
    style.textContent = EMBLEM_CSS;
    document.head.appendChild(style);
  }

  /* ---- tier derivation (canonical frontend mapping) -----------------------
   * Mirrors franchise-tournament-brackets-render.js activeTierForWeek():
   *   w>=32 -> national, w>=30 -> region, w>=27 -> conference, else null.
   * Regular season ends at week 26, so a non-null tier here means an EOS week.
   * ------------------------------------------------------------------------- */
  function tierForWeek(week) {
    var w = parseInt(week, 10);
    if (isNaN(w)) return null;
    // EOS window is weeks 27-34 (ft.EOS_WEEKS). Bound the upper end so the
    // offseason (week 35+ recruiting/awards) does not read as "national".
    if (w < 27 || w > 34) return null;
    if (w >= 32) return 'national';
    if (w >= 30) return 'region';
    return 'conference';
  }

  /* ---- round label (structurally normalized) ------------------------------
   * Per PM decision: every 8-team round 1 reads QUARTERFINAL.
   *   Conference (27,28,29): QUARTERFINAL / SEMIFINAL / CHAMPIONSHIP
   *   Region     (30,   31): SEMIFINAL / CHAMPIONSHIP   (4-team bracket)
   *   National   (32,33,34): QUARTERFINAL / SEMIFINAL / CHAMPIONSHIP
   * Round name only — no tier word (the emblem carries the tier).
   * ------------------------------------------------------------------------- */
  var ROUND_LABEL_BY_WEEK = {
    27: 'QUARTERFINAL', 28: 'SEMIFINAL', 29: 'CHAMPIONSHIP',
    30: 'SEMIFINAL',    31: 'CHAMPIONSHIP',
    32: 'QUARTERFINAL', 33: 'SEMIFINAL', 34: 'CHAMPIONSHIP'
  };
  function roundLabelForWeek(week) {
    return ROUND_LABEL_BY_WEEK[parseInt(week, 10)] || null;
  }

  global.GOBTierEmblem = {
    TIER_TOKENS: TIER_TOKENS,
    EMBLEM_SIZING: EMBLEM_SIZING,
    EMBLEM_CSS: EMBLEM_CSS,
    renderEmblem: renderEmblem,
    renderLockup: renderLockup,
    injectCss: injectCss,
    tierForWeek: tierForWeek,
    roundLabelForWeek: roundLabelForWeek
  };
})(typeof window !== 'undefined' ? window : this);
