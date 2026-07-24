/* ============================================================================
 * GOB Tournament Tier Emblem — design source of truth
 * ----------------------------------------------------------------------------
 * Framework-agnostic. Every function returns an SVG/HTML *string*. No deps, no
 * build step. Extracted verbatim (geometry + metal tokens + sizing) from the
 * Claude Design mock "Tournament In-Situ (FCC + Court).html" so the geometry
 * is not guessed. Drop this into the repo and consume renderEmblem / renderLockup.
 *
 * The mark is: a tier FRAME (crest / hexagon badge / ringed medallion) + a
 * CENTER (the conference number or region letter for Conference/Region, or a
 * star cluster). Two-tone (metal frame + dark field) at >=~28px; single-color
 * "mono" stamp at <=20px. All coordinates live in a 0 0 100 120 viewBox; the
 * rendered box is size wide by size*1.2 tall.
 *
 * Gold is a fixed tier constant. NATIONAL uses #D4A848 to match the existing
 * bracket token (.fcc-tb-*) — confirm/alias in code so the two never clash.
 * Metals never inherit team color.
 * ==========================================================================*/

/* ---- Metal + shape tokens per tier ---------------------------------------- */
export const TIER_TOKENS = {
    conference: { shape: 'crest',     stars: 1, metal: '#C79A5B', metalHi: '#EAC488', fieldA: '#F6DFAE', fieldB: '#9c7434', glow: 'rgba(199,154,91,0.5)',  word: 'CONFERENCE' },
    region:     { shape: 'badge',     stars: 2, metal: '#B9C1CD', metalHi: '#F0F4FA', fieldA: '#FFFFFF', fieldB: '#8b929e', glow: 'rgba(200,212,228,0.5)', word: 'REGION' },
    national:   { shape: 'medallion', stars: 3, metal: '#D4A848', metalHi: '#F0C560', fieldA: '#F7E3A0', fieldB: '#9c7a1e', glow: 'rgba(212,168,72,0.55)', word: 'NATIONAL' },
  };
  
  /* Per-surface sizing used in the approved mock. Match these. */
  export const EMBLEM_SIZING = {
    fccFranchiseHeader: { emblem: 52, labelL1: 19, labelL2: 11 }, // logo+emblem object, 2-line lockup
    fccGameCardHeader:  { emblem: 27, labelL1: 14, labelL2: 8.5, gap: 8 }, // Next/Last Game header, right-justified
    courtScoreboard:    { emblem: 16, mode: 'mono' },             // round-label strip, monochrome
    minColorSize: 28,   // below this, use mode:'mono'
    monoMaxSize: 20,
  };
  
  let _uid = 0;
  
  /* ---- primitives ----------------------------------------------------------- */
  function starPath(cx, cy, r) {
    const ri = r * 0.42; let p = '';
    for (let i = 0; i < 10; i++) {
      const rad = i % 2 === 0 ? r : ri;
      const a = -Math.PI / 2 + i * Math.PI / 5;
      p += (i ? 'L' : 'M') + (cx + rad * Math.cos(a)).toFixed(2) + ' ' + (cy + rad * Math.sin(a)).toFixed(2);
    }
    return p + 'Z';
  }
  function starCluster(n, cx, cy, R) {
    const s = (x, y, r) => `<path d="${starPath(x, y, r)}" fill="var(--st)"/>`;
    if (n === 1) return s(cx, cy, R);
    if (n === 2) return s(cx - R * 0.82, cy, R * 0.74) + s(cx + R * 0.82, cy, R * 0.74);
    return s(cx, cy - R * 0.30, R * 0.92) + s(cx - R * 1.02, cy + R * 0.52, R * 0.60) + s(cx + R * 1.02, cy + R * 0.52, R * 0.60);
  }
  function glyphSVG(ch, cy) {
    return `<text x="50" y="${cy + 1}" text-anchor="middle" dominant-baseline="central" font-family="'Bebas Neue Pro','Bebas Neue',sans-serif" font-weight="700" font-size="58" fill="var(--st)">${ch}</text>`;
  }
  function frameShape(shape) {
    if (shape === 'crest')
      return `<path d="M14 12 H86 V60 C86 96 66 108 50 112 C34 108 14 96 14 60 Z" fill="var(--field)" stroke="var(--fr)" stroke-width="4" stroke-linejoin="round"/>`;
    if (shape === 'badge')
      return `<path d="M27 13 H73 L91 60 L73 107 H27 L9 60 Z" fill="var(--field)" stroke="var(--fr)" stroke-width="4" stroke-linejoin="round"/>`;
    // medallion: sunburst rays + double ring
    let rays = '';
    for (let i = 0; i < 28; i++) {
      const a = i / 28 * Math.PI * 2;
      rays += `<line x1="${(50 + 50 * Math.cos(a)).toFixed(2)}" y1="${(60 + 50 * Math.sin(a)).toFixed(2)}" x2="${(50 + 55.5 * Math.cos(a)).toFixed(2)}" y2="${(60 + 55.5 * Math.sin(a)).toFixed(2)}" stroke="var(--fr)" stroke-width="2.2"/>`;
    }
    return `${rays}<circle cx="50" cy="60" r="46" fill="var(--field)" stroke="var(--fr)" stroke-width="4"/><circle cx="50" cy="60" r="40" fill="none" stroke="var(--fr)" stroke-width="1.4" opacity="0.7"/>`;
  }
  
  /* ---- public: render one emblem -------------------------------------------
   * opts:
   *   tier   'conference' | 'region' | 'national'   (required)
   *   value  conference number / region letter as a string. Ignored for national.
   *          If omitted for conference/region, the star cluster is shown instead.
   *   size   rendered width in px (height = size*1.2). Default 52.
   *   mode   'color' (two-tone, default) | 'mono' (single-color stamp for <=20px)
   * ------------------------------------------------------------------------- */
  export function renderEmblem({ tier, value = null, size = 52, mode = 'color' } = {}) {
    const T = TIER_TOKENS[tier];
    if (!T) throw new Error(`Unknown tier: ${tier}`);
    const id = 'e' + (_uid++);
    const cy = T.shape === 'crest' ? 56 : 60;
    const useGlyph = tier !== 'national' && value != null && value !== '';
    let vars, defs = '';
    if (mode === 'mono') {
      vars = `--fr:${T.metal};--st:${T.metal};--field:transparent`;
    } else {
      vars = `--fr:url(#fr${id});--st:${T.metalHi};--field:url(#fd${id})`;
      defs = `<defs>`
        + `<linearGradient id="fr${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${T.fieldA}"/><stop offset="1" stop-color="${T.fieldB}"/></linearGradient>`
        + `<radialGradient id="fd${id}" cx="0.5" cy="0.4" r="0.7"><stop offset="0" stop-color="#16161f"/><stop offset="1" stop-color="#07070d"/></radialGradient>`
        + `</defs>`;
    }
    const center = useGlyph ? glyphSVG(String(value), cy) : starCluster(T.stars, 50, cy, T.shape === 'crest' ? 22 : 21);
    return `<svg width="${size}" height="${(size * 1.2).toFixed(1)}" viewBox="0 0 100 120" style="${vars}" fill="none">${defs}${frameShape(T.shape)}${center}</svg>`;
  }
  
  /* ---- public: render an emblem + wordmark lockup --------------------------
   * The wordmark is always "<TIER> TOURNAMENT" and NEVER repeats the value —
   * the number/letter lives only inside the emblem.
   * opts:
   *   tier, value, size  — as renderEmblem
   *   variant  'stack' (2-line: TIER / TOURNAMENT, default) | 'inline' (one line)
   *   l1, l2   optional font-size overrides in px for the two label lines
   * Returns an inline-flex span; pair with the CSS below.
   * ------------------------------------------------------------------------- */
  export function renderLockup({ tier, value = null, size = 52, variant = 'stack', l1 = null, l2 = null, mode = 'color' } = {}) {
    const T = TIER_TOKENS[tier];
    const emb = renderEmblem({ tier, value, size, mode });
    const s1 = l1 ? ` style="font-size:${l1}px"` : '';
    const s2 = l2 ? ` style="font-size:${l2}px;letter-spacing:0.18em"` : '';
    if (variant === 'inline') {
      return `<span class="gob-lockup gob-lockup--inline" style="--m-hi:${T.metalHi}">${emb}`
        + `<span class="gob-lk-one"${s1}>${T.word} TOURNAMENT</span></span>`;
    }
    return `<span class="gob-lockup" style="--m-hi:${T.metalHi}">${emb}`
      + `<span class="gob-lk-txt"><span class="gob-lk-l1"${s1}>${T.word}</span><span class="gob-lk-l2"${s2}>TOURNAMENT</span></span></span>`;
  }
  
  /* ---- companion CSS (inject once) -----------------------------------------
   * Fonts assumed present in the host page (Bebas Neue Pro / Bebas Neue).
   * ------------------------------------------------------------------------- */
  export const EMBLEM_CSS = `
  .gob-lockup{display:inline-flex;align-items:center;gap:11px}
  .gob-lockup--inline{gap:8px}
  .gob-lk-txt{display:flex;flex-direction:column;line-height:0.94}
  .gob-lk-l1{font-family:'Bebas Neue Pro','Bebas Neue',sans-serif;font-weight:700;font-size:20px;letter-spacing:0.5px;color:#fff}
  .gob-lk-l2{font-family:'Bebas Neue Pro','Bebas Neue',sans-serif;font-size:11px;letter-spacing:0.28em;color:var(--m-hi);margin-top:3px}
  .gob-lk-one{font-family:'Bebas Neue Pro','Bebas Neue',sans-serif;font-size:14px;letter-spacing:0.1em;color:#fff;white-space:nowrap}
  `;
  
  /* ---- usage ----------------------------------------------------------------
   *  import { renderEmblem, renderLockup, EMBLEM_CSS, EMBLEM_SIZING } from './emblem.js';
   *
   *  // FCC franchise header — logo + emblem as one centered row-object:
   *  el.innerHTML = renderLockup({ tier: 'conference', value: '1', size: 52 });   // "1" inside crest, CONFERENCE / TOURNAMENT
   *
   *  // FCC Next/Last Game card header — right-justified lockup, one line:
   *  head.insertAdjacentHTML('beforeend',
   *    renderLockup({ tier: 'region', value: 'C', size: 27, l1: 14, l2: 8.5 }));
   *
   *  // Court scoreboard round-label strip — monochrome emblem + round name:
   *  strip.innerHTML = renderEmblem({ tier: 'national', size: 16, mode: 'mono' })
   *                  + `<b>${roundName}</b>`;   // roundName e.g. "NATIONAL FINAL"
   *
   *  // National takes no value (always 3 stars); conference/region take value:
   *  renderEmblem({ tier: 'national', size: 40 });                 // 3 gold stars
   *  renderEmblem({ tier: 'conference', value: '4', size: 40 });   // "4" in brass crest
   * ------------------------------------------------------------------------- */
  