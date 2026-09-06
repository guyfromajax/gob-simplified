/**
 * Sim Game Presentation — Act 2 broadcast overlay (Mockup 4 · wide worm).
 *
 * Layout (1228×572 fit box, scale 1.0–1.6 top-anchored):
 *   worm 242 · gap 14 · band 256 (away | team stats | home) · gap 14 · footer 46
 *
 * Worm: full-width time-domain x, fixed nonlinear y (compressMargin). Callouts pin
 * to the worm tip. Cards / three-zone stage / Highlights↔Team Stats switch removed.
 *
 * Input: `{ teams, frames }` from simTimelineAssembler.js. Pure renderer — no game state.
 */

import { fadeOutPregameBed } from './gameSfx.js';
import { REG_Q_SEC, clockToSeconds } from './simWormTime.js';
import { loadCalloutCopy } from './simCalloutCopy.js';
import { CalloutCadence, CALLOUT_HOLD_S, GAME_WINNER_HOLD_S, GAME_WINNER_TIER } from './simCalloutCadence.js';

const POSC = { PG: '#4A90D9', SG: '#7B5EA7', SF: '#3A8C4A', PF: '#C0392B', C: '#D4A017' };
const GREEN = '#34EC27', BLUE = '#4A90D9', ORANGE = '#F79420', RED = '#ff6d6d', GOLD = '#FFD700';
const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];

const QUARTER_MS = 18000;
const FRAME_MIN_MS = 130;
const FRAME_MAX_MS = 900;
const PRETIP_MS = 2200;
const BREAK_MS = 2800;
const FINAL_MS = 2600;
const LINEUP_CHANGE_MS = 1000;

const FIT_W = 1228;
const FIT_H = 572;
const FIT_MAX_SCALE = 1.6;
const FIT_MIN_SCALE = 1;

const WORM_PLOT_H = 208;
const WORM_KNEE = 10;
const WORM_BEYOND = 0.20;
const WORM_DOMAIN_M = 45;
const WORM_PAD_X = 4;
const WORM_PAD_Y = 10;

const CALLOUT_HOLD_MS = Math.round(CALLOUT_HOLD_S * 1000); // 2600
/** The game-winner holds longer; the cadence engine owns both numbers. */
const GAME_WINNER_HOLD_MS = Math.round(GAME_WINNER_HOLD_S * 1000); // 6000
const CALLOUT_ENTER_MS = 200;

const BENCH_MAX_CHIPS = 3;

const CALLOUT_COLORS = {
  green: GREEN, blue: BLUE, orange: ORANGE, red: RED, gold: GOLD,
};

const SIL = `<svg viewBox="0 0 100 100"><circle cx="50" cy="34" r="19" fill="rgba(255,255,255,0.15)"/><path d="M12 100c0-22 17-36 38-36s38 14 38 36" fill="rgba(255,255,255,0.15)"/></svg>`;
const FLAME = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c1 3-1 4.5-2.5 6.5C8 10.7 7 12.4 7 14.5 7 18 9.2 21 12 21s5-3 5-6.5c0-2.4-1.3-4-2.4-5.6.2 1.6-.4 2.7-1.3 3.3.5-2.6-.9-6.4-1.3-10.2z"/></svg>`;
const SNOW = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1M12 5.5l2 2M12 5.5l-2 2M12 18.5l2-2M12 18.5l-2-2M5.5 12l2 2M5.5 12l2-2M18.5 12l-2 2M18.5 12l-2-2"/></svg>`;

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/**
 * Fixed nonlinear margin compression — full resolution inside ±10, 20% beyond.
 * Same margin always maps to the same height (never auto-fit).
 */
export function compressMargin(m, knee = WORM_KNEE, beyond = WORM_BEYOND) {
  const a = Math.abs(Number(m) || 0);
  const c = Math.min(a, knee) + Math.max(0, a - knee) * beyond;
  return (Number(m) || 0) < 0 ? -c : c;
}

function fitScale(availW, availH) {
  if (!(availW > 0) || !(availH > 0)) return FIT_MIN_SCALE;
  const raw = Math.min(availW / FIT_W, availH / FIT_H);
  return Math.max(FIT_MIN_SCALE, Math.min(FIT_MAX_SCALE, raw));
}

function rtColor(rt) {
  if (rt == null) return null;
  return (typeof window !== 'undefined' && window.getRtColor) ? window.getRtColor(rt) : null;
}

function rtDisplay(rt) {
  if (typeof window !== 'undefined' && typeof window.formatRtDisplay === 'function') {
    return window.formatRtDisplay(rt);
  }
  return '--';
}

function portraitSrc(id) {
  if (id && typeof window !== 'undefined' && window.API_CONFIG && window.API_CONFIG.getPlayerImageUrl) {
    return window.API_CONFIG.getPlayerImageUrl(id, { size: 'card' });
  }
  return '';
}

function calloutColor(name) {
  return CALLOUT_COLORS[String(name || '').toLowerCase()] || GREEN;
}

/** *asterisks* → <b>…</b>; everything else HTML-escaped. */
function formatCalloutLine(line) {
  return String(line || '').split(/(\*[^*]+\*)/g).map((part) => {
    if (part.length >= 2 && part.startsWith('*') && part.endsWith('*')) {
      return `<b>${esc(part.slice(1, -1))}</b>`;
    }
    return esc(part);
  }).join('');
}

/**
 * Compute worm tip geometry for a frame without building SVG.
 * @returns {{ cx, cy, rising, cur, elapsed, domain, w, h, padX, padY, mid }}
 */
export function wormSvgMeta(wormState, w, h) {
  const padX = WORM_PAD_X;
  const padY = WORM_PAD_Y;
  const mid = h / 2;
  const samples = (wormState && wormState.samples) || [];
  const domain = Math.max(1, (wormState && wormState.domain) || 4 * REG_Q_SEC);
  const elapsed = (wormState && wormState.elapsed) != null
    ? wormState.elapsed
    : (samples.length ? samples[samples.length - 1].elapsed : 0);
  const yDenom = compressMargin(WORM_DOMAIN_M) || 1;
  const xAt = (sec) => padX + (Math.min(Math.max(0, sec), domain) / domain) * (w - padX * 2);
  const yAt = (m) => {
    const v = compressMargin(m) / yDenom;
    return Math.max(padY, Math.min(h - padY, mid - v * (mid - padY)));
  };
  const cur = samples.length ? samples[samples.length - 1].margin : 0;
  const cx = xAt(elapsed);
  const cy = yAt(cur);
  const prevM = samples.length > 1 ? samples[samples.length - 2].margin : cur;
  const prevY = yAt(prevM);
  return {
    cx, cy, rising: cy < prevY, cur, elapsed, domain, w, h, padX, padY, mid, xAt, yAt,
  };
}

function wormSvgHtml(wormState, w, h, home, away, clutch) {
  const meta = wormSvgMeta(wormState, w, h);
  const samples = (wormState && wormState.samples) || [];
  const { xAt, yAt, mid, cx, cy, cur, domain } = meta;

  let line = '';
  let area = `M ${xAt(0)} ${mid} `;
  if (!samples.length) {
    line = `M ${xAt(0)} ${mid}`;
    area += `L ${xAt(0)} ${mid} Z`;
  } else {
    samples.forEach((s, i) => {
      const xx = xAt(s.elapsed);
      const yy = yAt(s.margin);
      line += `${i ? 'L' : 'M'} ${xx.toFixed(1)} ${yy.toFixed(1)} `;
      area += `L ${xx.toFixed(1)} ${yy.toFixed(1)} `;
    });
    area += `L ${xAt(samples[samples.length - 1].elapsed)} ${mid} Z`;
  }

  const tickStroke = (f) => `rgba(255,255,255,${f === 0.5 ? '.08' : '.045'})`;
  const ticks = [0.25, 0.5, 0.75].map((f) => {
    const tx = (WORM_PAD_X + f * (w - WORM_PAD_X * 2)).toFixed(1);
    return `<line x1="${tx}" y1="0" x2="${tx}" y2="${h}" stroke="${tickStroke(f)}" stroke-width="1"/>`;
  }).join('');

  // Absolute quarter boundaries when they fall inside the domain (OT extends domain).
  const qTicks = [REG_Q_SEC, 2 * REG_Q_SEC, 3 * REG_Q_SEC]
    .filter((t) => t < domain)
    .map((t) => {
      const tx = xAt(t).toFixed(1);
      return `<line x1="${tx}" y1="0" x2="${tx}" y2="${h}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;
    })
    .join('');

  const kneeY = [yAt(WORM_KNEE), yAt(-WORM_KNEE)]
    .map((v) => `<line x1="0" y1="${v.toFixed(1)}" x2="${w}" y2="${v.toFixed(1)}" stroke="rgba(255,255,255,.055)" stroke-width="1" stroke-dasharray="2 6"/>`)
    .join('');

  const wallOp = clutch ? '.3' : '.12';
  const wallW = clutch ? 1.5 : 1;
  const wallX = xAt(domain).toFixed(1);
  const wall = `<line x1="${wallX}" y1="0" x2="${wallX}" y2="${h}" stroke="rgba(255,255,255,${wallOp})" stroke-width="${wallW}"/>`;
  const nowRule = `<line x1="${cx.toFixed(1)}" y1="0" x2="${cx.toFixed(1)}" y2="${h}" stroke="rgba(255,255,255,.13)" stroke-width="1"/>`;
  const zeroLine = `<line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="rgba(255,255,255,.16)" stroke-width="1" stroke-dasharray="3 4"/>`;
  const tipFill = cur >= 0 ? home : away;

  const svg = `<svg class="wormsvg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs>
      <linearGradient id="sgpwg-up" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${home}" stop-opacity="0.42"/><stop offset="1" stop-color="${home}" stop-opacity="0"/></linearGradient>
      <linearGradient id="sgpwg-dn" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${away}" stop-opacity="0.42"/><stop offset="1" stop-color="${away}" stop-opacity="0"/></linearGradient>
      <clipPath id="sgpclip-up"><rect x="0" y="0" width="${w}" height="${mid}"/></clipPath>
      <clipPath id="sgpclip-dn"><rect x="0" y="${mid}" width="${w}" height="${mid}"/></clipPath>
    </defs>
    ${ticks}${qTicks}${kneeY}${wall}${zeroLine}${nowRule}
    <path d="${area}" fill="url(#sgpwg-up)" clip-path="url(#sgpclip-up)"/>
    <path d="${area}" fill="url(#sgpwg-dn)" clip-path="url(#sgpclip-dn)"/>
    <path d="${line}" fill="none" stroke="${home}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#sgpclip-up)"/>
    <path d="${line}" fill="none" stroke="${away}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#sgpclip-dn)"/>
    <circle class="wormdot" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="4" fill="${tipFill}" style="color:${tipFill}"/>
  </svg>`;

  return { svg, meta };
}

function isClutchFrame(frame) {
  const q = Number(frame && frame.quarter) || 1;
  if (q < 4) return false;
  const clock = (frame.score && frame.score.clock) || '';
  if (clockToSeconds(clock) > 120) return false;
  const a = Number((frame.score && frame.score.away) || 0);
  const h = Number((frame.score && frame.score.home) || 0);
  return Math.abs(h - a) <= 6;
}

function ensureStyles() {
  if (document.getElementById('sim-game-pres-styles')) return;
  const style = document.createElement('style');
  style.id = 'sim-game-pres-styles';
  style.textContent = `
    .sgp-root{position:fixed;left:0;right:0;bottom:0;top:0;z-index:2000;overflow:hidden;display:flex;align-items:stretch;
      font-family:Inter,system-ui,sans-serif;color:rgba(255,255,255,.90);-webkit-font-smoothing:antialiased;
      --w90:rgba(255,255,255,.90);--w70:rgba(255,255,255,.70);--w55:rgba(255,255,255,.55);--w40:rgba(255,255,255,.40);--w25:rgba(255,255,255,.25);
      --hair:rgba(255,255,255,.08);--green:${GREEN};--orange:${ORANGE}}
    .sgp-root .overlay{position:relative;flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;padding:16px 26px 12px;gap:14px;isolation:isolate;overflow:hidden;
      background:radial-gradient(120% 78% at 50% 26%,rgba(39,64,142,.13),transparent 62%),radial-gradient(90% 70% at 50% 120%,rgba(247,148,32,.045),transparent 60%),#0b0d14}
    .sgp-root .overlay::before{content:'';position:absolute;left:50%;bottom:-54%;width:94%;aspect-ratio:1/1;transform:translateX(-50%);border-radius:50%;border:1px solid rgba(255,255,255,.04);pointer-events:none}
    .sgp-root.fade-in{animation:sgpFade .45s ease}
    @keyframes sgpFade{from{opacity:0}to{opacity:1}}
    .sgp-root.dissolving{opacity:0;transition:opacity .45s ease}

    .sgp-root .fit{width:1228px;height:572px;flex-shrink:0;display:flex;flex-direction:column;gap:14px;
      transform-origin:top center;will-change:transform;position:relative;z-index:1}

    /* ── wide worm 242 = 14 + 4 + 208 + 4 + 12 ── */
    .sgp-root .w4{height:242px;flex:none;display:flex;flex-direction:column;position:relative}
    .sgp-root .w4-head{height:14px;display:flex;align-items:center;justify-content:space-between}
    .sgp-root .w4-cap{font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.18em;color:var(--w40)}
    .sgp-root .w4-cap.poss{color:var(--orange)}
    .sgp-root .w4-team{font-family:'Bebas Neue',sans-serif;font-size:20px;line-height:1;letter-spacing:.04em}
    .sgp-root .w4-plot{position:relative;height:208px;margin:4px 0;overflow:hidden}
    .sgp-root .w4-plot svg.wormsvg{display:block;position:absolute;inset:0;width:100%;height:100%;margin:0}
    .sgp-root .w4-axis{height:12px;display:flex;justify-content:space-between;font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.06em;color:var(--w25)}
    .sgp-root .w4-axis.endgame span{color:rgba(255,255,255,.12);transition:color .4s}
    .sgp-root .w4-axis.endgame span:last-child{color:var(--w70);font-weight:700}
    .sgp-root .wormdot{filter:drop-shadow(0 0 5px currentColor)}

    /* ── callout pill (sibling overlay in plot — not wiped with SVG) ── */
    .sgp-root .co{position:absolute;z-index:4;display:flex;align-items:center;gap:9px;padding:6px 12px 6px 6px;border-radius:24px;pointer-events:none;
      background:rgba(10,13,20,.93);box-shadow:0 0 0 1px var(--coc),0 8px 24px rgba(0,0,0,.6);
      opacity:1;transform:none;transition:opacity .2s cubic-bezier(.2,.7,.2,1),transform .2s cubic-bezier(.2,.7,.2,1);
      font-family:Inter,system-ui,sans-serif}
    .sgp-root .co.enter{opacity:0;transform:scale(.94)}
    .sgp-root .co-av{width:30px;height:30px;border-radius:9px;flex:none;overflow:hidden;position:relative;background:linear-gradient(180deg,#1b2130,#10141d);box-shadow:inset 0 0 0 1.5px var(--coc)}
    .sgp-root .co-av img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
    .sgp-root .co-av .sil{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center}
    .sgp-root .co-av .sil svg{width:80%;height:90%}
    .sgp-root .co-av.logo{width:38px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-family:'Bebas Neue',sans-serif;font-size:16px;line-height:1;letter-spacing:.04em;color:#fff;padding-top:1px}
    .sgp-root .co-txt{font-size:13.5px;font-weight:600;line-height:1.15;color:#fff;white-space:nowrap;letter-spacing:-.005em}
    .sgp-root .co-txt b{font-weight:800}
    .sgp-root .co-leader{position:absolute;z-index:3;pointer-events:none;background:var(--coc);border-radius:1px;opacity:.5;height:1px}

    /* ── band: 433 / 330 / 433 ── */
    .sgp-root .band{height:256px;flex:none;display:grid;grid-template-columns:433px 330px 433px;gap:16px;position:relative}
    .sgp-root .pane{padding:10px;border-radius:12px;background:linear-gradient(180deg,rgba(255,255,255,.026),rgba(255,255,255,.008));box-shadow:inset 0 0 0 1px rgba(255,255,255,.045);display:flex;flex-direction:column;min-height:0;overflow:hidden}
    .sgp-root .pane-head{height:14px;display:flex;align-items:center;gap:8px;font-family:ui-monospace,Menlo,monospace;font-size:8.5px;letter-spacing:.15em;color:var(--w40);text-transform:uppercase;margin-bottom:6px}
    .sgp-root .pane-head .dot{width:6px;height:6px;border-radius:2px;flex:none}
    .sgp-root .pane-head .sp{flex:1}
    .sgp-root .pane-head .cols{display:grid;grid-template-columns:repeat(4,52px);gap:0;text-align:center;font-size:8px;letter-spacing:.1em;color:var(--w25)}
    .sgp-root .lineup{flex:1;display:flex;flex-direction:column;gap:4px;min-height:0}

    .sgp-root .r4{height:40px;display:grid;grid-template-columns:34px 1fr repeat(4,52px);align-items:center;gap:8px;padding:0 4px;border-radius:9px;position:relative;transition:filter .3s}
    .sgp-root .r4.isout{filter:saturate(.5) brightness(.8)}
    .sgp-root .r4.spot{background:radial-gradient(120% 160% at 50% 50%,rgba(247,148,32,.1),transparent 72%);box-shadow:inset 0 0 0 1px rgba(247,148,32,.32)}
    .sgp-root .r4.ft{box-shadow:inset 0 0 0 1px rgba(255,215,0,.28)}
    .sgp-root .r4.spot.ft{box-shadow:inset 0 0 0 1px rgba(247,148,32,.32),inset 0 0 0 1px rgba(255,215,0,.28)}

    .sgp-root .h4{position:relative;width:34px;height:34px;border-radius:9px;overflow:hidden;background:linear-gradient(180deg,#1b2130,#10141d);border:1.5px solid rgba(255,255,255,.16);box-shadow:0 3px 9px rgba(0,0,0,.4)}
    .sgp-root .h4 img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
    .sgp-root .h4 .sil{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center}
    .sgp-root .h4 .sil svg{width:80%;height:90%}
    .sgp-root .rt4{position:absolute;top:1px;left:1px;z-index:2;font-family:'Bebas Neue',sans-serif;font-size:10px;line-height:1;padding:1px 3px 0;border-radius:3px;color:#0b0d14}

    .sgp-root .id4{min-width:0;display:flex;flex-direction:column;gap:3px}
    .sgp-root .n4{display:flex;align-items:center;gap:5px;height:12px}
    .sgp-root .n4 .pos{font-family:'Bebas Neue',sans-serif;font-size:11px;line-height:1;flex:none}
    .sgp-root .n4 .nm{font-size:12.5px;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1}
    .sgp-root .n4 .jn{font-size:9.5px;font-weight:600;color:var(--w40);flex:none;line-height:1}
    .sgp-root .spotmark{font-family:'Bebas Neue',sans-serif;font-size:10px;letter-spacing:.08em;color:${ORANGE};flex:none}
    .sgp-root .s4{display:flex;align-items:center;gap:6px;height:10px}
    .sgp-root .s4 .mo{width:10px;height:10px;flex:none;display:flex}.sgp-root .s4 .mo svg{width:100%;height:100%}
    .sgp-root .flame{animation:sgpFlick 1.1s ease-in-out infinite}
    @keyframes sgpFlick{0%,100%{transform:scale(1) rotate(-1deg);opacity:.92}50%{transform:scale(1.13) rotate(2deg);opacity:1}}
    .sgp-root .pips{display:flex;gap:2px}
    .sgp-root .pip{width:8px;height:3px;border-radius:1.5px}
    .sgp-root .tag4{font-family:'Bebas Neue',sans-serif;font-size:9px;line-height:1;letter-spacing:.05em;padding:1px 4px 0;border-radius:3px;white-space:nowrap}

    .sgp-root .c4{display:flex;flex-direction:column;align-items:center;gap:3px}
    .sgp-root .c4 .v{font-size:13px;font-weight:700;line-height:1;color:var(--w90);font-variant-numeric:tabular-nums}
    .sgp-root .c4 .t{width:40px;height:3px;border-radius:2px;background:rgba(255,255,255,.09);overflow:hidden}
    .sgp-root .c4 .f{height:100%;border-radius:2px;transition:width .5s cubic-bezier(.2,.7,.2,1)}

    /* team stats */
    .sgp-root .tsp4{flex:1;display:flex;flex-direction:column;justify-content:space-between}
    .sgp-root .tsr4{display:grid;grid-template-columns:66px 26px 1fr 26px;align-items:center;gap:7px;height:26px}
    .sgp-root .tsr4 .lb{font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.04em;color:var(--w55);white-space:nowrap}
    .sgp-root .tsr4 .va,.sgp-root .tsr4 .vh{font-size:12.5px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums;color:var(--w40)}
    .sgp-root .tsr4 .va{text-align:right}.sgp-root .tsr4 .vh{text-align:left}
    .sgp-root .tsr4 .va.lead,.sgp-root .tsr4 .vh.lead{color:#fff}
    .sgp-root .tug4{position:relative;height:8px;border-radius:4px;background:rgba(255,255,255,.06)}
    .sgp-root .tug4::before{content:'';position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:rgba(255,255,255,.18)}
    .sgp-root .tug4 .pull{position:absolute;top:0;bottom:0;border-radius:4px;transition:width .5s cubic-bezier(.2,.7,.2,1)}

    /* footer */
    .sgp-root .f4{height:46px;flex:none;display:flex;align-items:center;justify-content:space-between;gap:16px}
    .sgp-root .f4 .bench{flex:1;min-width:0;display:flex;align-items:center;gap:7px;overflow:hidden;flex-wrap:nowrap}
    .sgp-root .f4 .bench.home{flex-direction:row-reverse;justify-content:flex-start}
    .sgp-root .bench-lbl{font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.14em;color:var(--w25);flex-shrink:0}
    .sgp-root .bchip{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.045);border:1px solid var(--hair);border-radius:20px;padding:3px 9px;font-size:10.5px;white-space:nowrap;flex:0 0 auto}
    .sgp-root .bchip .bstat{color:var(--w40);font-variant-numeric:tabular-nums}
    .sgp-root .bchip.out{opacity:.7}
    .sgp-root .bout{font-family:'Bebas Neue',sans-serif;font-size:9.5px;color:#2a0606;background:${RED};border-radius:3px;padding:1px 4px 0;letter-spacing:.04em}
    .sgp-root .tgl{display:flex;align-items:center;gap:8px;flex:none}
    .sgp-root .tgl-lbl{font-family:ui-monospace,Menlo,monospace;font-size:8.5px;letter-spacing:.14em;color:var(--w40)}
    .sgp-root .tgl-sw{width:38px;height:20px;border-radius:11px;background:rgba(255,255,255,.09);box-shadow:inset 0 0 0 1px rgba(255,255,255,.1);position:relative;cursor:pointer;transition:background .2s;border:0;padding:0}
    .sgp-root .tgl-sw::after{content:'';position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:var(--w55);transition:transform .2s,background .2s}
    .sgp-root .tgl-sw.on{background:rgba(52,236,39,.2)}
    .sgp-root .tgl-sw.on::after{transform:translateX(18px);background:var(--green)}

    .sgp-root .pretip-lbl{position:absolute;left:50%;top:25%;transform:translate(-50%,-50%);display:none;
      font-family:'Bebas Neue',sans-serif;font-size:16px;letter-spacing:.28em;color:rgba(255,255,255,.40);
      pointer-events:none;z-index:2;white-space:nowrap}
    .sgp-root.is-pretip .pretip-lbl{display:block}

    .sgp-root.is-break .fit{filter:blur(3px) brightness(.42);opacity:.5}
    .sgp-root .breakcard{position:absolute;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center;gap:8px;z-index:5;background:radial-gradient(60% 60% at 50% 50%,rgba(11,13,20,.62),rgba(11,13,20,.9))}
    .sgp-root.is-break .breakcard{display:flex}
    .sgp-root .bc-eyebrow{font-size:12px;font-weight:800;letter-spacing:.34em;color:rgba(255,255,255,.40)}
    .sgp-root .bc-title{font-family:'Bebas Neue',sans-serif;font-size:78px;line-height:.9;letter-spacing:.02em;color:#fff}
    .sgp-root .bc-score{font-family:'Bebas Neue',sans-serif;font-size:40px;letter-spacing:.03em;display:flex;gap:16px;align-items:baseline}
    .sgp-root .bc-dash{color:rgba(255,255,255,.40)}
    .sgp-root .bc-perf{display:flex;flex-direction:column;align-items:center;gap:8px;margin-top:6px}
    .sgp-root .bc-av{width:72px;height:72px;border-radius:14px;overflow:hidden;position:relative;background:linear-gradient(180deg,#1b2130,#10141d);border:2px solid rgba(255,255,255,.18);box-shadow:0 8px 22px rgba(0,0,0,.45);display:none}
    .sgp-root .bc-av.show{display:block}
    .sgp-root .bc-av img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
    .sgp-root .bc-av .sil{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center}
    .sgp-root .bc-av .sil svg{width:80%;height:90%}
    .sgp-root .bc-note{font-size:13px;color:rgba(255,255,255,.55)}
    .sgp-root .finalstamp{position:absolute;top:16px;left:50%;transform:translateX(-50%);z-index:6;display:none;font-family:'Bebas Neue',sans-serif;font-size:28px;letter-spacing:.28em;color:#fff;background:rgba(11,13,20,.6);border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:5px 20px 3px}
    .sgp-root.is-final .finalstamp{display:block}

    .sgp-dbg{position:fixed;top:8px;right:8px;width:322px;max-height:calc(100vh - 16px);z-index:2100;
      display:flex;flex-direction:column;gap:6px;padding:10px 11px;border-radius:10px;
      background:rgba(8,10,15,.94);border:1px solid rgba(255,255,255,.14);
      font-family:ui-monospace,Menlo,monospace;font-size:10px;color:rgba(255,255,255,.72)}
    .sgp-dbg h4{font-size:9px;letter-spacing:.16em;color:rgba(255,255,255,.42);margin:0;text-transform:uppercase}
    .sgp-dbg .row{display:flex;justify-content:space-between;gap:8px}
    .sgp-dbg .row b{color:#fff;font-weight:600;font-variant-numeric:tabular-nums}
    .sgp-dbg .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:4px;text-align:center}
    .sgp-dbg .grid div{background:rgba(255,255,255,.05);border-radius:4px;padding:3px 2px}
    .sgp-dbg .grid i{display:block;font-style:normal;color:rgba(255,255,255,.4);font-size:8px}
    .sgp-dbg .log{display:flex;flex-direction:column;gap:1px;overflow:auto;max-height:230px}
    .sgp-dbg .lg{display:grid;grid-template-columns:30px 62px 1fr;gap:5px;padding:2px 0;
      border-bottom:1px dashed rgba(255,255,255,.07);color:rgba(255,255,255,.38)}
    .sgp-dbg .lg.f{color:rgba(255,255,255,.92)}
    .sgp-dbg .lg .x{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .sgp-dbg .hr{height:1px;background:rgba(255,255,255,.1);margin:2px 0}

    @media (prefers-reduced-motion: reduce){
      .sgp-root .co{transition:none}
      .sgp-root .c4 .f,.sgp-root .tug4 .pull{transition:none}
      .sgp-root .flame{animation:none}
      .sgp-root.fade-in{animation:none}
    }
  `;
  document.head.appendChild(style);
}

function playerRowSkeleton() {
  const cells = ['PTS', 'REB', 'AST', 'DEF'].map((label) => `
    <div class="c4" data-bar="${label}">
      <span class="v">0</span>
      <div class="t"><div class="f"></div></div>
    </div>`).join('');
  return `<div class="r4" data-pos="">
    <div class="h4">
      <span class="rt4" style="display:none"></span>
      <img alt="" style="display:none">
      <div class="sil">${SIL}</div>
    </div>
    <div class="id4">
      <div class="n4"></div>
      <div class="s4"></div>
    </div>
    ${cells}
  </div>`;
}

function teamPanelSkeleton() {
  const rows = [
    ['fg', 'FG%'],
    ['tpm', '3PT'],
    ['paint', 'PTS IN PAINT'],
    ['fb', 'FAST BREAK'],
    ['reb', 'REBOUNDS'],
    ['to', 'TURNOVERS'],
    ['fouls', 'TEAM FOULS'],
  ];
  return rows.map(([key, label]) => `
    <div class="tsr4" data-stat="${key}">
      <span class="lb">${label}</span>
      <span class="va">0</span>
      <div class="tug4"><div class="pull"></div></div>
      <span class="vh">0</span>
    </div>`).join('');
}

function buildSkeleton(teams) {
  const awayRows = POSITIONS.map((pos) => playerRowSkeleton().replace('data-pos=""', `data-pos="${pos}"`)).join('');
  const homeRows = POSITIONS.map((pos) => playerRowSkeleton().replace('data-pos=""', `data-pos="${pos}"`)).join('');

  const root = document.createElement('div');
  root.className = 'sgp-root fade-in';
  root.innerHTML = `
    <div class="overlay">
      <div class="fit" data-fit>
        <div class="w4">
          <div class="w4-head">
            <span class="w4-cap" data-wcap>LEAD MARGIN</span>
            <span class="w4-team" data-wteam></span>
          </div>
          <div class="w4-plot" data-plot>
            <div class="pretip-lbl">TIP OFF</div>
          </div>
          <div class="w4-axis" data-waxis><span>TIP</span><span>Q1</span><span>HALF</span><span>Q3</span><span>FINAL</span></div>
        </div>
        <div class="band" data-band>
          <div class="pane" data-side="away">
            <div class="pane-head">
              <span class="dot" style="background:${esc(teams.away.color)}"></span>
              <span>${esc(teams.away.name)} · AWAY</span>
              <span class="sp"></span>
              <span class="cols"><span>PTS</span><span>REB</span><span>AST</span><span>DEF</span></span>
            </div>
            <div class="lineup" data-lineup="away">${awayRows}</div>
          </div>
          <div class="pane">
            <div class="pane-head">
              <span>TEAM STATS</span>
              <span class="sp"></span>
              <span style="font-size:8px;color:rgba(255,255,255,.25)">bar shows the edge</span>
            </div>
            <div class="tsp4" data-team-panel>${teamPanelSkeleton()}</div>
          </div>
          <div class="pane" data-side="home">
            <div class="pane-head">
              <span class="dot" style="background:${esc(teams.home.color)}"></span>
              <span>${esc(teams.home.name)} · HOME</span>
              <span class="sp"></span>
              <span class="cols"><span>PTS</span><span>REB</span><span>AST</span><span>DEF</span></span>
            </div>
            <div class="lineup" data-lineup="home">${homeRows}</div>
          </div>
        </div>
        <div class="f4">
          <div class="bench away" data-bench="away"></div>
          <div class="tgl">
            <span class="tgl-lbl">HIGHLIGHTS</span>
            <button type="button" class="tgl-sw on" data-highlights aria-pressed="true" aria-label="Toggle highlights"></button>
          </div>
          <div class="bench home" data-bench="home"></div>
        </div>
      </div>
      <div class="breakcard">
        <div class="bc-eyebrow">QUARTER BREAK</div>
        <div class="bc-title"></div>
        <div class="bc-score"></div>
        <div class="bc-perf">
          <div class="bc-av" data-break-av>
            <img alt="">
            <div class="sil">${SIL}</div>
          </div>
          <div class="bc-note"></div>
        </div>
      </div>
      <div class="finalstamp">FINAL</div>
    </div>`;
  return root;
}

function benchHtml(chips) {
  if (!chips || !chips.length) return '';
  const shown = chips.slice(0, BENCH_MAX_CHIPS);
  const extra = chips.length - shown.length;
  const items = shown.map((c) =>
    `<span class="bchip${c.out ? ' out' : ''}"><b>${esc(c.name)}</b>${c.out ? '<span class="bout">OUT</span>' : ''}<span class="bstat">${c.pts}p</span></span>`
  ).join('');
  const more = extra > 0 ? `<span class="bchip"><b>+${extra}</b></span>` : '';
  return `<span class="bench-lbl">BENCH</span>${items}${more}`;
}

function setPortrait(headEl, playerId, borderColor) {
  if (!headEl) return;
  const img = headEl.querySelector('img');
  const sil = headEl.querySelector('.sil');
  if (!img || !sil) return;

  if (headEl.dataset.pid !== String(playerId || '')) {
    headEl.dataset.pid = String(playerId || '');
    const src = portraitSrc(playerId);
    img.onload = null;
    img.onerror = null;
    if (src) {
      img.style.display = 'block';
      sil.style.display = 'none';
      img.onerror = () => {
        img.style.display = 'none';
        sil.style.display = 'flex';
      };
      img.src = src;
    } else {
      img.removeAttribute('src');
      img.style.display = 'none';
      sil.style.display = 'flex';
    }
  }
  if (borderColor) headEl.style.borderColor = borderColor;
}

function updatePlayerRow(rowEl, p, teamColor) {
  if (!rowEl || !p) return;
  const head = rowEl.querySelector('.h4');
  setPortrait(head, p.id, p.out ? RED : teamColor);

  const rtb = head && head.querySelector('.rt4');
  if (rtb) {
    const rc = rtColor(p.rt);
    if (p.rt != null && rc) {
      rtb.style.display = '';
      rtb.style.background = rc;
      rtb.textContent = rtDisplay(p.rt);
    } else {
      rtb.style.display = 'none';
      rtb.textContent = '';
    }
  }

  const nameEl = rowEl.querySelector('.n4');
  if (nameEl) {
    nameEl.innerHTML =
      `<span class="pos" style="color:${POSC[p.pos] || BLUE}">${esc(p.pos)}</span>` +
      `<span class="nm">${esc(p.name)}</span><span class="jn">#${esc(p.jersey)}</span>` +
      `${p.spot ? '<span class="spotmark">◆ TOP</span>' : ''}`;
  }

  const status = [];
  if (p.hot) status.push(`<span class="mo flame" style="color:${ORANGE}">${FLAME}</span>`);
  if (p.cold) status.push(`<span class="mo" style="color:${BLUE}">${SNOW}</span>`);
  let pips = '';
  for (let i = 0; i < 5; i += 1) {
    const on = i < p.fouls;
    const c = p.out ? RED : (p.fouls >= 3 ? GOLD : 'rgba(255,255,255,0.7)');
    pips += `<span class="pip" style="background:${on ? c : 'rgba(255,255,255,0.14)'}"></span>`;
  }
  status.push(`<span class="pips">${pips}</span>`);
  if (p.out) status.push(`<span class="tag4" style="background:${RED};color:#2a0606">OUT</span>`);
  else if (p.fouls >= 3) {
    status.push(`<span class="tag4" style="color:${GOLD};box-shadow:inset 0 0 0 1px rgba(255,215,0,.4)">FOUL TROUBLE</span>`);
  }
  if (p.sub) status.push(`<span class="tag4" style="background:${GREEN};color:#06210a">IN</span>`);
  const s4 = rowEl.querySelector('.s4');
  if (s4) s4.innerHTML = status.join('');

  [
    ['PTS', p.pts, 20, false],
    ['REB', p.reb, 10, false],
    ['AST', p.ast, 10, false],
    ['DEF', p.def, 100, true],
  ].forEach(([label, v, max, pct]) => {
    const cell = rowEl.querySelector(`.c4[data-bar="${label}"]`);
    if (!cell) return;
    const n = Number(v) || 0;
    const fillPct = Math.min(n / max, 1) * 100;
    const maxed = pct ? n >= 80 : n >= max;
    const color = maxed ? BLUE : GREEN;
    const fill = cell.querySelector('.f');
    if (fill) {
      fill.style.width = `${fillPct}%`;
      fill.style.background = color;
    }
    const val = cell.querySelector('.v');
    if (val) val.textContent = pct ? `${n}%` : String(n);
  });

  rowEl.classList.toggle('spot', !!p.spot);
  rowEl.classList.toggle('isout', !!p.out);
  rowEl.classList.toggle('ft', !p.out && p.fouls >= 3);
}

function updateTeamPanel(panelEl, teamPanel, awayColor, homeColor) {
  if (!panelEl || !teamPanel) return;
  const a = teamPanel.away || {};
  const h = teamPanel.home || {};
  const specs = [
    { key: 'fg', a: a.fgPct, h: h.fgPct, lowBetter: false, format: (v) => (Number(v) || 0).toFixed(1) },
    { key: 'tpm', a: a.tpm, h: h.tpm, lowBetter: false, format: (v) => String(Math.round(v)) },
    { key: 'paint', a: a.paint, h: h.paint, lowBetter: false, format: (v) => String(Math.round(v)) },
    { key: 'fb', a: a.fb, h: h.fb, lowBetter: false, format: (v) => String(Math.round(v)) },
    { key: 'reb', a: a.reb, h: h.reb, lowBetter: false, format: (v) => String(Math.round(v)) },
    { key: 'to', a: a.to, h: h.to, lowBetter: true, pullToHigh: true, opponentColor: true, format: (v) => String(Math.round(v)) },
    { key: 'fouls', a: a.fouls, h: h.fouls, lowBetter: true, pullToHigh: true, opponentColor: true, format: (v) => String(Math.round(v)) },
  ];
  specs.forEach((spec) => {
    const row = panelEl.querySelector(`.tsr4[data-stat="${spec.key}"]`);
    if (!row) return;
    const av = Number(spec.a) || 0;
    const hv = Number(spec.h) || 0;
    const va = row.querySelector('.va');
    const vh = row.querySelector('.vh');
    if (va) va.textContent = spec.format(av);
    if (vh) vh.textContent = spec.format(hv);
    const aLead = spec.lowBetter ? av < hv : av > hv;
    const hLead = spec.lowBetter ? hv < av : hv > av;
    if (va) va.classList.toggle('lead', aLead);
    if (vh) vh.classList.toggle('lead', hLead);
    const pull = row.querySelector('.pull');
    if (!pull) return;
    const edge = Math.abs(av - hv);
    const widthPct = edge === 0 ? 0 : Math.min(46, 8 + edge * 2.5);
    const pullsAway = spec.pullToHigh ? av > hv : aLead;
    // TO/fouls: bar still grows toward the higher total, but in the opponent's colour
    // (the team benefiting from the trouble).
    const fill = spec.opponentColor
      ? (pullsAway ? homeColor : awayColor)
      : (pullsAway ? awayColor : homeColor);
    if (edge === 0) {
      pull.style.width = '0';
      pull.style.left = '50%';
      pull.style.right = 'auto';
      pull.style.background = 'transparent';
    } else if (pullsAway) {
      pull.style.right = '50%';
      pull.style.left = 'auto';
      pull.style.width = `${widthPct}%`;
      pull.style.background = fill;
    } else {
      pull.style.left = '50%';
      pull.style.right = 'auto';
      pull.style.width = `${widthPct}%`;
      pull.style.background = fill;
    }
  });
}

function setBreakAvatar(avEl, playerId) {
  if (!avEl) return;
  const img = avEl.querySelector('img');
  const sil = avEl.querySelector('.sil');
  if (!playerId) {
    avEl.classList.remove('show');
    avEl.dataset.pid = '';
    if (img) {
      img.onerror = null;
      img.removeAttribute('src');
      img.style.display = 'none';
    }
    if (sil) sil.style.display = 'flex';
    return;
  }
  avEl.classList.add('show');
  if (avEl.dataset.pid === String(playerId)) return;
  avEl.dataset.pid = String(playerId);
  if (!img || !sil) return;
  const src = portraitSrc(playerId);
  img.onerror = null;
  if (src) {
    img.style.display = 'block';
    sil.style.display = 'none';
    img.onerror = () => {
      img.style.display = 'none';
      sil.style.display = 'flex';
    };
    img.src = src;
  } else {
    img.removeAttribute('src');
    img.style.display = 'none';
    sil.style.display = 'flex';
  }
}

function calloutsDebugEnabled() {
  try {
    if (typeof window === 'undefined') return false;
    if (window.DEBUG_CARDS || window.DEBUG_CALLOUTS) return true;
    const q = new URLSearchParams(window.location.search);
    return q.has('debug_cards') || q.has('debug_callouts');
  } catch (e) {
    return false;
  }
}

function renderCalloutsDebug(el, cadence) {
  if (!el) return;
  if (!cadence) {
    el.innerHTML = '<h4>callouts</h4><div class="row"><span>waiting for copy…</span></div>';
    return;
  }
  const st = cadence.stats();
  const prof = cadence.profile();
  const target = 8;
  const rows = st.byQuarter.map((q) => `<div><b>${q.fired}</b><i>Q${q.q}</i></div>`).join('');
  const reasons = Object.entries(st.suppressedByReason)
    .sort((a, b) => b[1] - a[1])
    .map(([r, n]) => `<div class="row"><span>${esc(r)}</span><b>${n}</b></div>`).join('');
  const counts = st.counts || {};
  const countBits = Object.keys(counts).sort()
    .map((k) => `${k[0].toUpperCase()}${counts[k]}`)
    .join(' ') || '—';
  const log = cadence.log.slice(-40).reverse().map((e) => `
    <div class="lg${e.fired ? ' f' : ''}">
      <span>${e.t.toFixed(0)}s</span>
      <span>${esc(String(e.tag || '').slice(0, 9))}</span>
      <span class="x">${esc(e.fired ? (e.detail || '') : e.reason)}</span>
    </div>`).join('');
  el.innerHTML = `
    <h4>callouts · Q${cadence.quarter}${cadence.suspended ? ' · OFF' : ''}</h4>
    <div class="row"><span>playback</span><b>${st.t.toFixed(1)}s</b></div>
    <div class="row"><span>fired</span><b>${st.total} / ~${target}</b></div>
    <div class="row"><span>share on screen</span><b>${st.share}%</b></div>
    <div class="row"><span>suppressed</span><b>${st.suppressed}</b></div>
    <div class="hr"></div>
    <h4>fired by quarter</h4>
    <div class="grid">${rows}</div>
    <div class="hr"></div>
    <h4>gates now</h4>
    <div class="row"><span>gap / rest</span><b>${prof.gap}s / ${prof.restFloor}s</b></div>
    <div class="row"><span>player cool</span><b>${prof.playerCool}s</b></div>
    <div class="row"><span>by tier</span><b>${esc(countBits)}</b></div>
    <div class="hr"></div>
    <h4>held, by reason</h4>
    <div>${reasons || '<div class="row"><span>none yet</span></div>'}</div>
    <div class="hr"></div>
    <h4>candidates (newest first)</h4>
    <div class="log">${log}</div>`;
}

/**
 * @param {{teams, frames}} timeline
 * @param {object} opts
 * @returns {Promise<void>}
 */
export function showSimGamePresentation(timeline, opts = {}) {
  const { teams, frames, meta } = timeline || {};
  ensureStyles();
  document.querySelectorAll('.sgp-root').forEach((n) => n.remove());

  if (!frames || !frames.length) {
    console.warn('⚠️ [SIM-PRES] No frames to play — skipping presentation.');
    return Promise.resolve();
  }

  const mount = opts.mount || document.body;
  const driveScoreboard = opts.driveScoreboard !== false;
  const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const root = buildSkeleton(teams);
  mount.appendChild(root);

  const fitEl = root.querySelector('[data-fit]');
  const overlayEl = root.querySelector('.overlay');
  const plotEl = root.querySelector('[data-plot]');
  const wCap = root.querySelector('[data-wcap]');
  const wTeam = root.querySelector('[data-wteam]');
  const wAxis = root.querySelector('[data-waxis]');
  const teamPanelEl = root.querySelector('[data-team-panel]');
  const highlightsBtn = root.querySelector('[data-highlights]');
  const breakAvEl = root.querySelector('[data-break-av]');

  const applyFit = () => {
    if (!fitEl || !overlayEl) return;
    const cs = getComputedStyle(overlayEl);
    const availW = overlayEl.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const availH = overlayEl.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    fitEl.style.transform = `scale(${fitScale(availW, availH)})`;
  };

  const positionBelowScoreboard = () => {
    const sbEl = document.getElementById('scoreboard');
    const top = sbEl ? Math.max(0, Math.round(sbEl.getBoundingClientRect().bottom)) : 0;
    root.style.top = `${top}px`;
    applyFit();
  };
  positionBelowScoreboard();
  window.addEventListener('resize', positionBelowScoreboard);

  let highlightsOn = true;
  let cadence = null;
  let lastRenderedFrame = null;
  let tipMeta = { cx: FIT_W / 2, cy: WORM_PLOT_H / 2, rising: true, w: FIT_W, h: WORM_PLOT_H };

  const dbgEl = calloutsDebugEnabled() ? document.createElement('div') : null;
  if (dbgEl) {
    dbgEl.className = 'sgp-dbg';
    root.appendChild(dbgEl);
    renderCalloutsDebug(dbgEl, null);
  }

  /* ---- callout presenter: DOM siblings in the plot, never wiped with SVG ---- */
  const calloutTimers = [];
  let calloutBusy = false;
  let calloutEl = null;
  let leaderEl = null;
  let activeCallout = null;
  let frozenCallout = null; // set once at appearance — pill never tracks the worm

  const clearCalloutTimers = () => { calloutTimers.splice(0).forEach(clearTimeout); };

  const clearCallout = () => {
    clearCalloutTimers();
    if (calloutEl) { calloutEl.remove(); calloutEl = null; }
    if (leaderEl) { leaderEl.remove(); leaderEl = null; }
    activeCallout = null;
    frozenCallout = null;
    calloutBusy = false;
  };

  /**
   * Place once at appearance and freeze. Vertical: above mid if tip is below mid,
   * below mid if tip is above, or halfway top→mid when tied. Horizontal: right edge
   * on tip x. Leader freezes to that same tip.
   */
  const placeCallout = () => {
    if (!calloutEl || !plotEl || !activeCallout) return;
    if (frozenCallout) {
      calloutEl.style.left = `${frozenCallout.left}px`;
      calloutEl.style.top = `${frozenCallout.top}px`;
      if (leaderEl) {
        leaderEl.style.left = `${frozenCallout.leaderLeft}px`;
        leaderEl.style.top = `${frozenCallout.leaderTop}px`;
        leaderEl.style.width = `${frozenCallout.leaderW}px`;
      }
      return;
    }

    const d = tipMeta || { cx: FIT_W / 2, cy: WORM_PLOT_H / 2, cur: 0 };
    const plotW = tipMeta.w || plotEl.clientWidth || FIT_W;
    const plotH = tipMeta.h || plotEl.clientHeight || WORM_PLOT_H;
    const mid = plotH / 2;
    const pw = calloutEl.offsetWidth || 220;
    const ph = calloutEl.offsetHeight || 42;
    const gap = 12;

    let top;
    if (!d.cur) {
      // Tied — halfway between plot top and the zero mid-line.
      top = (mid / 2) - (ph / 2);
    } else if (d.cy > mid) {
      // Tip below mid → pill just above mid.
      top = mid - gap - ph;
    } else {
      // Tip above mid → pill just below mid.
      top = mid + gap;
    }

    // Right-justified to the tip x at appearance.
    let left = d.cx - pw;
    top = Math.max(2, Math.min(plotH - ph - 2, top));
    left = Math.max(2, Math.min(plotW - pw - 2, left));

    calloutEl.style.left = `${left}px`;
    calloutEl.style.top = `${top}px`;

    if (!leaderEl) {
      leaderEl = document.createElement('div');
      leaderEl.className = 'co-leader';
      plotEl.appendChild(leaderEl);
    }
    leaderEl.style.setProperty('--coc', activeCallout.col);
    // Leader from pill's right edge to the frozen tip (same x as right-justify target).
    const tipX = d.cx;
    const tipY = d.cy;
    const attachX = left + pw;
    const leaderLeft = Math.min(attachX, tipX);
    const leaderW = Math.max(6, Math.abs(tipX - attachX));
    const leaderTop = tipY - 0.5;
    leaderEl.style.left = `${leaderLeft}px`;
    leaderEl.style.top = `${leaderTop}px`;
    leaderEl.style.width = `${leaderW}px`;

    frozenCallout = { left, top, leaderLeft, leaderTop, leaderW };
  };

  const buildCalloutAvatar = (model, col) => {
    const side = model.side === 'home' ? 'home' : 'away';
    const team = teams[side] || {};
    if (model.avatar === 'abbr') {
      const av = document.createElement('div');
      av.className = 'co-av logo';
      av.style.setProperty('--coc', col);
      av.style.background = `linear-gradient(135deg,${team.color || col},#0b0d14)`;
      av.textContent = model.teamAbbr || team.abbr || '';
      return av;
    }
    const av = document.createElement('div');
    av.className = 'co-av';
    av.style.setProperty('--coc', col);
    av.innerHTML = `<img alt="" style="display:none"><div class="sil">${SIL}</div>`;
    setPortrait(av, model.playerId, null);
    return av;
  };

  const showCallout = (model) => {
    if (!plotEl || !model || !highlightsOn) return false;
    // A callout mid-hold normally wins. The game-winner is the exception: there is no
    // later chance to show it, so it replaces whatever is up.
    if (calloutBusy && model.tier !== GAME_WINNER_TIER) return false;
    calloutBusy = true;
    const col = calloutColor(model.color);
    activeCallout = { col, model };

    clearCalloutTimers();
    if (calloutEl) calloutEl.remove();
    if (leaderEl) { leaderEl.remove(); leaderEl = null; }
    frozenCallout = null;

    calloutEl = document.createElement('div');
    calloutEl.className = prefersReduced ? 'co' : 'co enter';
    calloutEl.style.setProperty('--coc', col);
    calloutEl.appendChild(buildCalloutAvatar(model, col));
    const txt = document.createElement('div');
    txt.className = 'co-txt';
    txt.innerHTML = formatCalloutLine(model.line);
    calloutEl.appendChild(txt);
    plotEl.appendChild(calloutEl);

    const settleAndFreeze = () => {
      placeCallout(); // first layout pass freezes position
      if (calloutEl) calloutEl.classList.remove('enter');
    };
    if (prefersReduced) settleAndFreeze();
    else if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => requestAnimationFrame(settleAndFreeze));
    } else {
      calloutTimers.push(setTimeout(settleAndFreeze, 16));
    }

    // The game-winner holds for 6s; every other tier for 2.6s.
    const holdMs = model.tier === GAME_WINNER_TIER ? GAME_WINNER_HOLD_MS : CALLOUT_HOLD_MS;
    calloutTimers.push(setTimeout(() => {
      if (calloutEl) {
        calloutEl.style.opacity = '0';
        if (leaderEl) leaderEl.style.opacity = '0';
      }
      calloutTimers.push(setTimeout(clearCallout, prefersReduced ? 0 : CALLOUT_ENTER_MS));
    }, holdMs));

    return true;
  };

  highlightsBtn?.addEventListener('click', () => {
    highlightsOn = !highlightsOn;
    highlightsBtn.classList.toggle('on', highlightsOn);
    highlightsBtn.setAttribute('aria-pressed', highlightsOn ? 'true' : 'false');
    if (cadence) cadence.suspend(!highlightsOn);
    if (!highlightsOn) clearCallout();
    if (dbgEl) renderCalloutsDebug(dbgEl, cadence);
  });

  const replaceWormSvg = (html) => {
    if (!plotEl) return;
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const next = tmp.firstElementChild;
    if (!next) return;
    const prev = plotEl.querySelector('svg.wormsvg');
    if (prev) prev.replaceWith(next);
    else plotEl.insertBefore(next, plotEl.firstChild);
  };

  const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  const updateScoreboard = (frame) => {
    if (!driveScoreboard) return;
    const s = frame.score || {};
    setText('away-score', s.away);
    setText('home-score', s.home);
    setText('game-clock', s.clock);
    setText('quarter', s.quarter);
    if (s.shot != null) setText('shot-clock', s.shot);
    setText('away-fouls', `F: ${s.afoul}`);
    setText('home-fouls', `F: ${s.hfoul}`);
    if (s.atol != null) setText('away-tol', `TOL: ${s.atol}`);
    if (s.htol != null) setText('home-tol', `TOL: ${s.htol}`);
  };

  const renderFrame = (frame) => {
    lastRenderedFrame = frame;
    const wormState = frame.worm && frame.worm.samples
      ? frame.worm
      : { samples: [{ elapsed: 0, margin: 0 }], elapsed: 0, domain: 4 * REG_Q_SEC };
    const clutch = isClutchFrame(frame);
    const w = Math.max(200, Math.round(plotEl.clientWidth || FIT_W));
    const h = Math.max(80, Math.round(plotEl.clientHeight || WORM_PLOT_H));
    const drawn = wormSvgHtml(wormState, w, h, teams.home.color, teams.away.color, clutch);
    tipMeta = drawn.meta;
    replaceWormSvg(drawn.svg);
    // Callouts stay frozen at appearance — do not re-place with the worm.

    const cur = tipMeta.cur || 0;
    if (wCap) {
      wCap.className = 'w4-cap' + (clutch ? ' poss' : '');
      if (clutch) {
        wCap.textContent = Math.abs(cur) <= 3 ? 'ONE POSSESSION' : 'TWO POSSESSIONS';
      } else {
        wCap.textContent = 'LEAD MARGIN';
      }
    }
    if (wTeam) {
      if (cur === 0) {
        wTeam.textContent = 'TIED';
        wTeam.style.color = 'rgba(255,255,255,0.5)';
      } else {
        const lead = cur > 0 ? teams.home : teams.away;
        wTeam.textContent = `${lead.abbr} +${Math.abs(cur)}`;
        wTeam.style.color = lead.color;
      }
    }
    if (wAxis) wAxis.className = 'w4-axis' + (clutch ? ' endgame' : '');

    POSITIONS.forEach((pos) => {
      const ai = POSITIONS.indexOf(pos);
      const awayRow = root.querySelector(`[data-lineup="away"] .r4[data-pos="${pos}"]`);
      const homeRow = root.querySelector(`[data-lineup="home"] .r4[data-pos="${pos}"]`);
      if (awayRow && frame.away && frame.away[ai]) updatePlayerRow(awayRow, frame.away[ai], teams.away.color);
      if (homeRow && frame.home && frame.home[ai]) updatePlayerRow(homeRow, frame.home[ai], teams.home.color);
    });

    root.querySelector('[data-bench="away"]').innerHTML = benchHtml(frame.benchAway);
    root.querySelector('[data-bench="home"]').innerHTML = benchHtml(frame.benchHome);
    updateTeamPanel(teamPanelEl, frame.teamPanel, teams.away.color, teams.home.color);

    root.classList.toggle('is-pretip', frame.phase === 'pretip');
    root.classList.toggle('is-break', frame.phase === 'break' || !!frame.breakSummary);
    root.classList.toggle('is-final', frame.phase === 'final');

    if (frame.breakSummary) {
      const b = frame.breakSummary;
      root.querySelector('.bc-title').textContent = `END ${b.summaryQ}`;
      root.querySelector('.bc-score').innerHTML =
        `<span style="color:${teams.away.color}">${esc(teams.away.abbr)} ${b.summaryAway}</span>` +
        `<span class="bc-dash">–</span>` +
        `<span style="color:${teams.home.color}">${esc(teams.home.abbr)} ${b.summaryHome}</span>`;
      root.querySelector('.bc-note').textContent = b.summaryNote || '';
      setBreakAvatar(breakAvEl, b.summarySpotId || null);
    } else {
      setBreakAvatar(breakAvEl, null);
    }

    updateScoreboard(frame);
  };

  const quarterCounts = {};
  frames.forEach((f) => {
    if (f.phase === 'live' && !f.breakSummary) {
      quarterCounts[f.quarter] = (quarterCounts[f.quarter] || 0) + 1;
    }
  });
  const hasLineupChange = (frame) =>
    [...(frame.away || []), ...(frame.home || [])].some((p) => p && (p.sub || p.out));
  const holdFor = (frame) => {
    if (prefersReduced) return frame.breakSummary || frame.phase !== 'live' ? 400 : 40;
    if (frame.phase === 'pretip') return PRETIP_MS;
    if (frame.phase === 'final') return FINAL_MS;
    if (frame.breakSummary) return BREAK_MS;
    if (hasLineupChange(frame)) return LINEUP_CHANGE_MS;
    const c = quarterCounts[frame.quarter] || 1;
    return Math.min(FRAME_MAX_MS, Math.max(FRAME_MIN_MS, Math.round(QUARTER_MS / c)));
  };

  loadCalloutCopy().then((pack) => {
    cadence = new CalloutCadence({
      pack,
      teams,
      seed: (frames && frames.length) || 7,
      onCallout: (model) => showCallout(model),
    });
    // Copy loads asynchronously. Prime from what is actually on screen if playback
    // has moved; otherwise use the assembler's exact Sim Rest quarter-boundary score.
    cadence.primeScore((lastRenderedFrame && lastRenderedFrame.score) || (meta && meta.startScore));
    cadence.suspend(!highlightsOn);
    root.__cadence = cadence;
    if (dbgEl) renderCalloutsDebug(dbgEl, cadence);
  });

  root.__callouts = {
    showCallout,
    endCallout: clearCallout,
    isBusy: () => calloutBusy,
  };

  return new Promise((resolve) => {
    const timers = [];
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      fadeOutPregameBed();
      timers.forEach(clearTimeout);
      clearCalloutTimers();
      window.removeEventListener('resize', positionBelowScoreboard);
      root.classList.add('dissolving');
      const t = setTimeout(() => { root.remove(); resolve(); }, prefersReduced ? 0 : 450);
      timers.push(t);
    };

    let i = 0;
    const step = () => {
      if (done) return;
      if (i >= frames.length) { finish(); return; }
      const frame = frames[i];
      renderFrame(frame);
      const hold = holdFor(frame);
      if (cadence) cadence.step(frame, hold / 1000);
      if (dbgEl) renderCalloutsDebug(dbgEl, cadence);
      i += 1;
      timers.push(setTimeout(step, hold));
    };

    step();
  });
}
