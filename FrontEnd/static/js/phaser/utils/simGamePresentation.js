/**
 * Sim Game Presentation — Act 2 broadcast overlay (Sim Broadcast Overlay slice 1).
 *
 * Zone contract (below the live scoreboard): away board · stage (worm + slot) · home board,
 * then bench chips · Highlights/Team Stats control · bench chips. All variability for later
 * slices (cards / clutch) stays in the stage slot; boards never restructure.
 *
 * Input: `{ teams, frames }` from simTimelineAssembler.js. Pure renderer — no game state.
 *
 * Slice 1: shell + boards + time-based worm + Team Stats hold mode. Cards / clutch / Context
 * deferred. Skip control removed. Quarter-break card kept at full-overlay scope.
 */

import { fadeOutPregameBed } from './gameSfx.js';
import { REG_Q_SEC } from './simWormTime.js';
import { loadMomentCopy } from './simMomentCopy.js';
import { CardCadence } from './simCardCadence.js';

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

/** Auto Team Stats on lulls — shipped behind flag, default off (brief §6). */
const AUTO_TEAM_STATS_ON_LULLS = false;

/**
 * Scale-to-fit for the content box (fix 1). The composition is authored once at the
 * 1280x720 floor and scaled uniformly; it is never stretched, because stretching grows
 * the stat-bar tracks while the 84px rows stay put and still leaves vertical dead space.
 * Capped so portraits and type stay broadcast-scale on very large displays, floored at
 * 1.0 because 720p is the minimum supported size, not a target to shrink past.
 */
/**
 * Worm vertical floor, converging across the game (±18 at tip → ±6 at final).
 *
 * The x-domain is the whole game from tip, so early on the worm has almost no width to
 * travel and any y-move renders near-vertical. The lever is NOT a growing x-domain: that
 * would make the same run occupy different widths at different times and destroy
 * "remaining game is remaining space", which clutch depends on. A converging y-floor
 * flattens the early game instead, and says something true while it does it — a two-point
 * swing in Q1 matters less than a two-point swing at the final horn.
 *
 * Auto-fit still overrides: a game wider than the floor is always fitted to its extremes.
 */
const WORM_FLOOR_TIP = 18;
const WORM_FLOOR_FINAL = 6;

function wormScaleFloor(progress) {
  const t = Math.max(0, Math.min(1, Number(progress) || 0));
  return WORM_FLOOR_TIP + (WORM_FLOOR_FINAL - WORM_FLOOR_TIP) * t;
}

const FIT_W = 1228;
const FIT_H = 572;
const FIT_MAX_SCALE = 1.6;
const FIT_MIN_SCALE = 1;

function fitScale(availW, availH) {
  if (!(availW > 0) || !(availH > 0)) return FIT_MIN_SCALE;
  const raw = Math.min(availW / FIT_W, availH / FIT_H);
  return Math.max(FIT_MIN_SCALE, Math.min(FIT_MAX_SCALE, raw));
}

const SIL = `<svg viewBox="0 0 100 100"><circle cx="50" cy="34" r="19" fill="rgba(255,255,255,0.15)"/><path d="M12 100c0-22 17-36 38-36s38 14 38 36" fill="rgba(255,255,255,0.15)"/></svg>`;
const FLAME = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c1 3-1 4.5-2.5 6.5C8 10.7 7 12.4 7 14.5 7 18 9.2 21 12 21s5-3 5-6.5c0-2.4-1.3-4-2.4-5.6.2 1.6-.4 2.7-1.3 3.3.5-2.6-.9-6.4-1.3-10.2z"/></svg>`;
const SNOW = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1M12 5.5l2 2M12 5.5l-2 2M12 18.5l2-2M12 18.5l-2-2M5.5 12l2 2M5.5 12l2-2M18.5 12l-2 2M18.5 12l-2-2"/></svg>`;

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function rtColor(rt) {
  if (rt == null) return null;
  return (typeof window !== 'undefined' && window.getRtColor) ? window.getRtColor(rt) : null;
}

function rtDisplay(rt) {
  if (typeof window !== 'undefined' && typeof window.formatRtDisplay === 'function') return window.formatRtDisplay(rt);
  return '--';
}

function portraitSrc(id) {
  if (id && typeof window !== 'undefined' && window.API_CONFIG && window.API_CONFIG.getPlayerImageUrl) {
    return window.API_CONFIG.getPlayerImageUrl(id, { size: 'card' });
  }
  return '';
}

function ensureStyles() {
  if (document.getElementById('sim-game-pres-styles')) return;
  const style = document.createElement('style');
  style.id = 'sim-game-pres-styles';
  style.textContent = `
    .sgp-root{position:fixed;left:0;right:0;bottom:0;top:0;z-index:2000;overflow:hidden;display:flex;align-items:stretch;
      font-family:Inter,system-ui,sans-serif;color:rgba(255,255,255,.90);-webkit-font-smoothing:antialiased;
      --w90:rgba(255,255,255,.90);--w70:rgba(255,255,255,.70);--w55:rgba(255,255,255,.55);--w40:rgba(255,255,255,.40);--w25:rgba(255,255,255,.25);
      --hair:rgba(255,255,255,.08);--boardw:398px;--stagew:400px}
    .sgp-root .overlay{position:relative;flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;padding:16px 26px 12px;gap:14px;isolation:isolate;
      background:radial-gradient(120% 78% at 50% 30%,rgba(39,64,142,.13),transparent 62%),radial-gradient(90% 70% at 50% 120%,rgba(247,148,32,.045),transparent 60%),#0b0d14}
    .sgp-root .overlay::before{content:'';position:absolute;left:50%;bottom:-54%;width:94%;aspect-ratio:1/1;transform:translateX(-50%);border-radius:50%;border:1px solid rgba(255,255,255,.04);pointer-events:none}
    .sgp-root.fade-in{animation:sgpFade .45s ease}
    @keyframes sgpFade{from{opacity:0}to{opacity:1}}
    .sgp-root.dissolving{opacity:0;transition:opacity .45s ease}

    /* Fixed-aspect content box: 398+400+398 + 2x16 gaps = 1228 wide, 512+14+46 = 572 tall.
       One transform scales the whole composition; nothing inside re-flows, so the density
       relationships tuned at the 1280x720 floor survive at every viewport size. */
    .sgp-root .fit{width:1228px;height:572px;flex-shrink:0;display:flex;flex-direction:column;gap:14px;
      transform-origin:top center;will-change:transform}
    .sgp-root .zones{height:512px;display:grid;grid-template-columns:minmax(260px,var(--boardw)) var(--stagew) minmax(260px,var(--boardw));gap:16px;justify-content:center;position:relative;z-index:1;min-height:0}
    .sgp-root .footer{height:46px;display:grid;grid-template-columns:minmax(260px,var(--boardw)) var(--stagew) minmax(260px,var(--boardw));gap:16px;align-items:center;justify-content:center;position:relative;z-index:1}

    .sgp-root .board{display:flex;flex-direction:column;gap:11px;justify-content:center;min-height:0;overflow:hidden}
    .sgp-root .bhead{height:16px;display:flex;align-items:center;gap:7px;font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.16em;color:var(--w40);text-transform:uppercase}
    .sgp-root .board.home .bhead{flex-direction:row-reverse}
    .sgp-root .bhead .dot{width:6px;height:6px;border-radius:2px;flex-shrink:0}
    .sgp-root .prow{height:84px;display:flex;align-items:center;gap:12px;padding:0 8px;border-radius:12px;position:relative;transition:filter .3s}
    .sgp-root .board.home .prow{flex-direction:row-reverse}
    .sgp-root .prow.isout{filter:saturate(.5) brightness(.82)}
    .sgp-root .prow.spot{background:radial-gradient(120% 150% at 50% 50%,rgba(247,148,32,.11),transparent 72%)}
    .sgp-root .prow.spot::before{content:'';position:absolute;inset:0;border-radius:12px;box-shadow:inset 0 0 0 1px rgba(247,148,32,.38),0 0 20px rgba(247,148,32,.14);animation:sgpSpot 2.6s ease-in-out infinite}
    @keyframes sgpSpot{0%,100%{box-shadow:inset 0 0 0 1px rgba(247,148,32,.32),0 0 14px rgba(247,148,32,.09)}50%{box-shadow:inset 0 0 0 1px rgba(247,148,32,.54),0 0 26px rgba(247,148,32,.2)}}

    .sgp-root .head{position:relative;flex-shrink:0;width:62px;height:62px;border-radius:12px;overflow:hidden;background:linear-gradient(180deg,#1b2130,#10141d);border:2px solid rgba(255,255,255,.16);box-shadow:0 5px 14px rgba(0,0,0,.4)}
    .sgp-root .head img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
    .sgp-root .head .sil{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center}
    .sgp-root .head .sil svg{width:80%;height:90%}
    .sgp-root .rtb{position:absolute;top:3px;left:3px;z-index:2;font-family:'Bebas Neue',sans-serif;font-size:12px;line-height:1;padding:2px 4px 1px;border-radius:4px;color:#0b0d14;box-shadow:0 1px 4px rgba(0,0,0,.45)}

    .sgp-root .pbody{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}
    .sgp-root .pname{display:flex;align-items:center;gap:6px;line-height:1;height:13px}
    .sgp-root .board.home .pname{flex-direction:row-reverse}
    .sgp-root .pname .pos{font-family:'Bebas Neue',sans-serif;font-size:12px;line-height:1;letter-spacing:.04em;flex-shrink:0}
    .sgp-root .pname .nm{font-size:13px;line-height:1;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .sgp-root .pname .jn{font-size:10.5px;line-height:1;font-weight:600;color:var(--w40);flex-shrink:0}
    .sgp-root .spotmark{font-family:'Bebas Neue',sans-serif;font-size:11px;letter-spacing:.1em;color:${ORANGE};flex-shrink:0}
    .sgp-root .tag-in{font-family:'Bebas Neue',sans-serif;font-size:10px;line-height:1;padding:2px 4px 1px;border-radius:3px;background:${GREEN};color:#06210a;letter-spacing:.04em}

    .sgp-root .status{display:flex;align-items:center;gap:8px;height:12px}
    .sgp-root .board.home .status{flex-direction:row-reverse}
    .sgp-root .mo{width:12px;height:12px;display:flex;flex-shrink:0}.sgp-root .mo svg{width:100%;height:100%}
    .sgp-root .flame{animation:sgpFlick 1.1s ease-in-out infinite}
    @keyframes sgpFlick{0%,100%{transform:scale(1) rotate(-1deg);opacity:.92}50%{transform:scale(1.13) rotate(2deg);opacity:1}}
    .sgp-root .pips{display:flex;gap:2.5px}.sgp-root .board.home .pips{flex-direction:row-reverse}
    .sgp-root .pip{width:10px;height:3.5px;border-radius:2px}
    .sgp-root .tag-out,.sgp-root .tag-ft{font-family:'Bebas Neue',sans-serif;font-size:9.5px;line-height:1;letter-spacing:.06em;padding:2px 4px 1px;border-radius:3px;white-space:nowrap}
    .sgp-root .tag-out{background:${RED};color:#2a0606}.sgp-root .tag-ft{color:${GOLD};border:1px solid rgba(255,215,0,.4)}

    .sgp-root .bars{display:flex;flex-direction:column;gap:4px}
    .sgp-root .barrow{display:grid;grid-template-columns:25px 1fr 28px;align-items:center;gap:7px;height:9px}
    .sgp-root .board.home .barrow{grid-template-columns:28px 1fr 25px}
    .sgp-root .bl{font-family:ui-monospace,Menlo,monospace;font-size:8px;line-height:1;letter-spacing:.08em;color:var(--w40)}
    .sgp-root .board.away .bl{text-align:left}.sgp-root .board.home .bl{text-align:right}
    .sgp-root .bv{font-size:11px;line-height:1;font-weight:700;color:var(--w90);font-variant-numeric:tabular-nums}
    .sgp-root .board.away .bv{text-align:right}.sgp-root .board.home .bv{text-align:left}
    .sgp-root .track{position:relative;height:8px;border-radius:4px;background:rgba(255,255,255,.07);overflow:hidden;display:flex}
    .sgp-root .board.home .track{justify-content:flex-end}
    .sgp-root .fill{height:100%;border-radius:4px;transition:width .5s cubic-bezier(.2,.7,.2,1)}
    .sgp-root .fill.maxed{box-shadow:0 0 8px 0 currentColor}

    .sgp-root .stage{display:flex;flex-direction:column;gap:14px;min-height:0;padding:10px 12px 12px;border-radius:14px;
      background:linear-gradient(180deg,rgba(255,255,255,.028),rgba(255,255,255,.008));box-shadow:inset 0 0 0 1px rgba(255,255,255,.045)}
    /* At rest the worm claims the stage (276 tall at the floor, chart area 246). The slot
       below stays reserved at 200 whatever fills it, so the stage never changes size across
       resting worm / team panel / card. */
    .sgp-root .wormblock{display:flex;flex-direction:column;flex:1;min-height:0}
    .sgp-root .wormfill{position:relative;flex:1;min-height:0;overflow:hidden;margin-top:4px}
    .sgp-root .wormfill .wormsvg{position:absolute;inset:0;width:100%;height:100%;margin:0}
    .sgp-root .wl-head{display:flex;align-items:baseline;justify-content:space-between;height:14px}
    .sgp-root .wl-cap{font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.16em;color:var(--w40)}
    .sgp-root .wl-team{font-family:'Bebas Neue',sans-serif;font-size:19px;letter-spacing:.04em;line-height:1}
    .sgp-root .wl-axis{display:flex;justify-content:space-between;margin-top:3px;font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.06em;color:var(--w25)}
    .sgp-root .wormdot{filter:drop-shadow(0 0 4px currentColor)}
    .sgp-root .slot{position:relative;flex-shrink:0;height:200px;display:flex;flex-direction:column;justify-content:center}
    /* ---- Cards in the directed slot. The slot is already reserved at 200, so a card
       arriving changes nothing about the stage's size — only what fills the lower band. ---- */
    .sgp-root .card{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;gap:8px;
      padding:14px 15px;border-radius:11px;z-index:3;
      background:linear-gradient(180deg,rgba(255,255,255,.055),rgba(255,255,255,.012));
      box-shadow:inset 0 0 0 1px var(--cc),0 12px 30px rgba(0,0,0,.5);
      opacity:1;transform:none;
      transition:opacity .18s cubic-bezier(.2,.7,.2,1),transform .18s cubic-bezier(.2,.7,.2,1)}
    /* Entry only: the settled card carries no transform, so text never sits on a scaled layer. */
    .sgp-root .card.enter{opacity:0;transform:scale(.985) translateY(5px)}
    .sgp-root .card.leaving{opacity:0}
    .sgp-root .ctag{align-self:flex-start;font-family:'Bebas Neue',sans-serif;font-size:12px;line-height:1;letter-spacing:.16em;padding:3px 7px 2px;border-radius:4px;border:1px solid}
    .sgp-root .cline{font-family:'Bebas Neue',sans-serif;font-size:31px;line-height:1.02;letter-spacing:.02em;color:#fff;text-wrap:balance}
    .sgp-root .csub{font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.1em;color:var(--w40)}
    .sgp-root .cmargin{display:flex;flex-direction:column;gap:6px}
    .sgp-root .cmrow{display:flex;align-items:baseline;justify-content:space-between}
    .sgp-root .cmval{font-family:'Bebas Neue',sans-serif;font-size:34px;line-height:1;letter-spacing:.02em}
    .sgp-root .cmtug{position:relative;height:13px;border-radius:7px;background:rgba(255,255,255,.07)}
    .sgp-root .cmtug::before{content:'';position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:rgba(255,255,255,.22)}
    .sgp-root .cmtug .pull{position:absolute;top:0;bottom:0;border-radius:7px}
    .sgp-root .cset{display:inline-flex;align-items:center;gap:6px;align-self:flex-start;font-family:'Bebas Neue',sans-serif;font-size:15px;letter-spacing:.14em;color:var(--w70);border:1px solid rgba(255,255,255,.16);border-radius:5px;padding:3px 8px 2px}
    .sgp-root .cset b{color:${GOLD};font-weight:400}
    .sgp-root .cbig{display:flex;align-items:baseline;gap:9px}
    .sgp-root .cbig .n{font-family:'Bebas Neue',sans-serif;font-size:40px;line-height:1;color:#fff}
    .sgp-root .cbig .l{font-family:'Bebas Neue',sans-serif;font-size:15px;letter-spacing:.14em;color:var(--w55)}
    /* Dim, never the quarter-break blur: on a 2.6s card a blur reads as a modal you must
       wait out, and it destroys whatever the coach was mid-read on. */
    .sgp-root .zones .board{transition:filter .18s}
    .sgp-root .zones.is-carddim .board{filter:brightness(.72)}

    .sgp-root .pretip-lbl{position:absolute;inset:0;display:none;align-items:center;justify-content:center;font-family:'Bebas Neue',sans-serif;font-size:16px;letter-spacing:.28em;color:rgba(255,255,255,.40);pointer-events:none;z-index:2}
    .sgp-root.is-pretip .pretip-lbl{display:flex}

    .sgp-root .tsp{display:flex;flex-direction:column;gap:6px;padding:4px 2px}
    .sgp-root .tsp-head{display:flex;align-items:center;justify-content:space-between;height:12px;margin-bottom:2px}
    .sgp-root .tsp-cap{font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.16em;color:var(--w40)}
    .sgp-root .tsr{display:grid;grid-template-columns:60px 26px 1fr 26px;align-items:center;gap:7px;height:18px}
    .sgp-root .tsr .lb{font-family:ui-monospace,Menlo,monospace;font-size:8.5px;letter-spacing:.05em;color:var(--w55);white-space:nowrap}
    .sgp-root .tsr .va,.sgp-root .tsr .vh{font-size:12px;line-height:1;font-weight:700;font-variant-numeric:tabular-nums;color:var(--w40)}
    .sgp-root .tsr .va{text-align:right}.sgp-root .tsr .vh{text-align:left}
    .sgp-root .tsr .va.lead,.sgp-root .tsr .vh.lead{color:#fff}
    .sgp-root .tug{position:relative;height:7px;border-radius:4px;background:rgba(255,255,255,.06)}
    .sgp-root .tug::before{content:'';position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:rgba(255,255,255,.18)}
    .sgp-root .tug .pull{position:absolute;top:0;bottom:0;border-radius:4px;transition:width .5s cubic-bezier(.2,.7,.2,1)}
    .sgp-root .pivot{position:relative;height:7px}
    .sgp-root .pivot::before{content:'';position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(255,255,255,.13)}

    .sgp-root .bench{display:flex;align-items:center;gap:7px;overflow:hidden;flex-wrap:nowrap;min-width:0}
    .sgp-root .bench.home{flex-direction:row-reverse}
    .sgp-root .bench-lbl{font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.14em;color:var(--w25);flex-shrink:0}
    /* Chips never shrink: rail density must not change with roster events. The room comes
       from the content instead — the chip's job is identity, so the name is the payload
       and the rebound count was the part that could go. */
    .sgp-root .bchip{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.045);border:1px solid var(--hair);border-radius:20px;padding:3px 9px;font-size:10.5px;white-space:nowrap;flex:0 0 auto}
    .sgp-root .bchip .bstat{color:var(--w40);font-variant-numeric:tabular-nums}
    .sgp-root .bchip.out{opacity:.7}
    .sgp-root .bout{font-family:'Bebas Neue',sans-serif;font-size:9.5px;color:#2a0606;background:${RED};border-radius:3px;padding:1px 4px 0;letter-spacing:.04em}
    .sgp-root .ctl{display:flex;align-items:center;gap:8px;justify-content:center}
    .sgp-root .ctlseg{display:flex;border:1px solid rgba(255,255,255,.09);border-radius:6px;overflow:hidden}
    .sgp-root .ctlseg button{font-family:'Bebas Neue',sans-serif;font-size:11.5px;letter-spacing:.09em;padding:5px 9px 4px;background:transparent;border:0;color:var(--w40);cursor:pointer;transition:color .2s,background .2s}
    .sgp-root .ctlseg button.on{color:var(--w90);background:rgba(255,255,255,.07)}
    .sgp-root .ctlseg button:hover{color:var(--w70)}

    .sgp-root.is-break .zones,.sgp-root.is-break .footer{filter:blur(3px) brightness(.42);opacity:.5}
    .sgp-root .breakcard{position:absolute;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center;gap:8px;z-index:5;background:radial-gradient(60% 60% at 50% 50%,rgba(11,13,20,.62),rgba(11,13,20,.9))}
    .sgp-root.is-break .breakcard{display:flex}
    .sgp-root .bc-eyebrow{font-size:12px;font-weight:800;letter-spacing:.34em;color:rgba(255,255,255,.40)}
    .sgp-root .bc-title{font-family:'Bebas Neue',sans-serif;font-size:78px;line-height:.9;letter-spacing:.02em;color:#fff}
    .sgp-root .bc-score{font-family:'Bebas Neue',sans-serif;font-size:40px;letter-spacing:.03em;display:flex;gap:16px;align-items:baseline}
    .sgp-root .bc-dash{color:rgba(255,255,255,.40)}
    .sgp-root .bc-note{font-size:13px;color:rgba(255,255,255,.55);margin-top:6px}
    .sgp-root .finalstamp{position:absolute;top:16px;left:50%;transform:translateX(-50%);z-index:6;display:none;font-family:'Bebas Neue',sans-serif;font-size:28px;letter-spacing:.28em;color:#fff;background:rgba(11,13,20,.6);border:1px solid rgba(255,255,255,.16);border-radius:8px;padding:5px 20px 3px}
    .sgp-root.is-final .finalstamp{display:block}

    /* ---- cadence debug panel (?debug_cards=1) -----------------------------------------
       Off by default and position:fixed, so it never participates in the composition's
       layout or its measurements. This is the panel the weights get tuned against. */
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
      .sgp-root .card,.sgp-root .zones .board{transition:none}
      .sgp-root .fill,.sgp-root .tug .pull{transition:none}
      .sgp-root .prow.spot::before,.sgp-root .flame{animation:none}
      .sgp-root.fade-in{animation:none}
    }
  `;
  document.head.appendChild(style);
}

function playerRowSkeleton(side) {
  const bars = ['PTS', 'REB', 'AST', 'DEF'].map((label) => `
    <div class="barrow" data-bar="${label}">
      ${side === 'home'
        ? `<span class="bv"></span><div class="track"><div class="fill"></div></div><span class="bl">${label}</span>`
        : `<span class="bl">${label}</span><div class="track"><div class="fill"></div></div><span class="bv"></span>`}
    </div>`).join('');
  const head = `<div class="head"><span class="rtb" style="display:none"></span><img alt="" style="display:none"><div class="sil">${SIL}</div></div>`;
  const body = `<div class="pbody">
      <div class="pname"></div>
      <div class="status"></div>
      <div class="bars">${bars}</div>
    </div>`;
  return `<div class="prow" data-side="${side}" data-pos="">${side === 'home' ? body + head : head + body}</div>`;
}

function teamPanelSkeleton() {
  const rows = [
    ['reb', 'REBOUNDS', 'tug'],
    ['to', 'TURNOVERS', 'tug'],
    ['fb', 'FAST BREAK', 'tug'],
    ['paint', 'PTS IN PAINT', 'tug'],
    ['fg', 'FG%', 'rate'],
    ['tpm', '3PM', 'rate'],
    ['fouls', 'TEAM FOULS', 'tug'],
  ];
  return rows.map(([key, label, kind]) => `
    <div class="tsr" data-stat="${key}" data-kind="${kind}">
      <span class="lb">${label}</span>
      <span class="va">0</span>
      <div class="${kind === 'tug' ? 'tug' : 'pivot'}">${kind === 'tug' ? '<div class="pull"></div>' : ''}</div>
      <span class="vh">0</span>
    </div>`).join('');
}

function buildSkeleton(teams) {
  const awayRows = POSITIONS.map((pos) => playerRowSkeleton('away').replace('data-pos=""', `data-pos="${pos}"`)).join('');
  const homeRows = POSITIONS.map((pos) => playerRowSkeleton('home').replace('data-pos=""', `data-pos="${pos}"`)).join('');

  const root = document.createElement('div');
  root.className = 'sgp-root fade-in';
  root.innerHTML = `
    <div class="overlay">
      <div class="fit" data-fit>
      <div class="zones">
        <div class="board away" data-side="away">
          <div class="bhead"><span class="dot" style="background:${esc(teams.away.color)}"></span><span>${esc(teams.away.name)} · AWAY</span></div>
          ${awayRows}
        </div>
        <div class="stage">
          <div class="wormblock">
            <div class="wl-head"><span class="wl-cap">LEAD MARGIN</span><span class="wl-team"></span></div>
            <div class="wormfill"></div>
            <div class="wl-axis"><span>TIP</span><span>Q1</span><span>HALF</span><span>Q3</span><span>FINAL</span></div>
          </div>
          <div class="slot" data-slot>
            <div class="pretip-lbl">STARTING LINEUPS · TIP-OFF</div>
            <div class="tsp" data-team-panel style="display:none">
              <div class="tsp-head"><span class="tsp-cap">TEAM STATS</span></div>
              ${teamPanelSkeleton()}
            </div>
          </div>
        </div>
        <div class="board home" data-side="home">
          <div class="bhead"><span class="dot" style="background:${esc(teams.home.color)}"></span><span>${esc(teams.home.name)} · HOME</span></div>
          ${homeRows}
        </div>
      </div>
      <div class="footer">
        <div class="bench away" data-bench="away"></div>
        <div class="ctl">
          <div class="ctlseg" data-rest>
            <button type="button" data-v="worm" class="on">HIGHLIGHTS</button>
            <button type="button" data-v="team">TEAM STATS</button>
          </div>
        </div>
        <div class="bench home" data-bench="home"></div>
      </div>
      </div>
      <div class="breakcard">
        <div class="bc-eyebrow">QUARTER BREAK</div>
        <div class="bc-title"></div>
        <div class="bc-score"></div>
        <div class="bc-note"></div>
      </div>
      <div class="finalstamp">FINAL</div>
    </div>`;
  return root;
}

function wormSvg(wormState, w, h, home, away) {
  const pad = 6;
  const mid = h / 2;
  const samples = (wormState && wormState.samples) || [];
  const domain = Math.max(1, (wormState && wormState.domain) || 4 * REG_Q_SEC);
  const elapsed = (wormState && wormState.elapsed) != null
    ? wormState.elapsed
    : (samples.length ? samples[samples.length - 1].elapsed : 0);
  const margins = samples.length ? samples.map((s) => s.margin) : [0];
  const maxAbs = Math.max(wormScaleFloor(elapsed / domain), ...margins.map((m) => Math.abs(m)));
  const xAt = (sec) => pad + (Math.min(sec, domain) / domain) * (w - pad * 2);
  const y = (m) => Math.max(pad, Math.min(h - pad, mid - (m / maxAbs) * (mid - pad)));

  let line = '';
  let area = `M ${xAt(0)} ${mid} `;
  if (!samples.length) {
    line = `M ${xAt(0)} ${mid}`;
    area += `L ${xAt(0)} ${mid} Z`;
  } else {
    samples.forEach((s, i) => {
      const xx = xAt(s.elapsed);
      const yy = y(s.margin);
      line += `${i ? 'L' : 'M'} ${xx.toFixed(1)} ${yy.toFixed(1)} `;
      area += `L ${xx.toFixed(1)} ${yy.toFixed(1)} `;
    });
    area += `L ${xAt(samples[samples.length - 1].elapsed)} ${mid} Z`;
  }

  const cur = margins[margins.length - 1] || 0;
  const cx = xAt(elapsed);
  const cy = y(cur);
  const tickStroke = 'rgba(255,255,255,0.10)';
  const ticks = [0, REG_Q_SEC, 2 * REG_Q_SEC, 3 * REG_Q_SEC]
    .filter((t) => t < domain)
    .map((t) => `<line x1="${xAt(t).toFixed(1)}" y1="0" x2="${xAt(t).toFixed(1)}" y2="${h}" stroke="${tickStroke}" stroke-width="1"/>`)
    .join('');
  const nowRule = `<line x1="${cx.toFixed(1)}" y1="0" x2="${cx.toFixed(1)}" y2="${h}" stroke="rgba(255,255,255,0.18)" stroke-width="1"/>`;
  const zeroLine = `<line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="rgba(255,255,255,0.16)" stroke-width="1" stroke-dasharray="3 4"/>`;

  return `<svg class="wormsvg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs>
      <linearGradient id="sgpwg-up" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${home}" stop-opacity="0.42"/><stop offset="1" stop-color="${home}" stop-opacity="0"/></linearGradient>
      <linearGradient id="sgpwg-dn" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${away}" stop-opacity="0.42"/><stop offset="1" stop-color="${away}" stop-opacity="0"/></linearGradient>
      <clipPath id="sgpclip-up"><rect x="0" y="0" width="${w}" height="${mid}"/></clipPath>
      <clipPath id="sgpclip-dn"><rect x="0" y="${mid}" width="${w}" height="${mid}"/></clipPath>
    </defs>
    ${zeroLine}
    ${ticks}
    ${nowRule}
    <path d="${area}" fill="url(#sgpwg-up)" clip-path="url(#sgpclip-up)"/>
    <path d="${area}" fill="url(#sgpwg-dn)" clip-path="url(#sgpclip-dn)"/>
    <path d="${line}" fill="none" stroke="${cur >= 0 ? home : away}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#sgpclip-up)"/>
    <path d="${line}" fill="none" stroke="${away}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#sgpclip-dn)"/>
    <circle class="wormdot" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.4" fill="${cur >= 0 ? home : away}" style="color:${cur >= 0 ? home : away}"/>
  </svg>`;
}

/** Chips that fit beside a board at this width before they start clipping mid-word. */
const BENCH_MAX_CHIPS = 3;

/**
 * The rail is empty until someone leaves the floor, and with no rotation subs the only
 * route onto it is a foul-out. Empty means the whole rail is gone — a lone BENCH label
 * over nothing reads as a component that failed to load. Chips arrive most-recent-exit
 * first, and the overflow collapses to one +N rather than clipping the last chip.
 */
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

function updatePlayerRow(rowEl, p, teamColor) {
  const head = rowEl.querySelector('.head');
  const img = head.querySelector('img');
  const rtb = head.querySelector('.rtb');
  const sil = head.querySelector('.sil');

  if (head.dataset.pid !== String(p.id || '')) {
    head.dataset.pid = String(p.id || '');
    const src = portraitSrc(p.id);
    if (src) {
      img.style.display = 'block';
      sil.style.display = 'none';
      img.onerror = () => { img.style.display = 'none'; sil.style.display = 'flex'; };
      img.src = src;
    } else {
      img.style.display = 'none';
      sil.style.display = 'flex';
    }
  }
  head.style.borderColor = p.out ? RED : teamColor;

  const rc = rtColor(p.rt);
  if (p.rt != null && rc) {
    rtb.style.display = '';
    rtb.style.background = rc;
    rtb.textContent = rtDisplay(p.rt);
  } else {
    rtb.style.display = 'none';
    rtb.textContent = '';
  }

  const nameEl = rowEl.querySelector('.pname');
  nameEl.innerHTML =
    `<span class="pos" style="color:${POSC[p.pos] || BLUE}">${esc(p.pos)}</span>` +
    `<span class="nm">${esc(p.name)}</span><span class="jn">#${esc(p.jersey)}</span>` +
    `${p.spot ? '<span class="spotmark">◆ TOP</span>' : ''}` +
    `${p.sub ? '<span class="tag-in">IN</span>' : ''}`;

  const status = [];
  if (p.hot) status.push(`<span class="mo flame" style="color:${ORANGE}">${FLAME}</span>`);
  if (p.cold) status.push(`<span class="mo snow" style="color:${BLUE}">${SNOW}</span>`);
  if (p.out) status.push('<span class="tag-out">FOULED OUT</span>');
  else if (p.fouls >= 4) status.push('<span class="tag-ft">FOUL TROUBLE</span>');
  let pips = '';
  for (let i = 0; i < 5; i++) {
    const on = i < p.fouls;
    const c = p.out ? RED : (p.fouls >= 4 ? GOLD : 'rgba(255,255,255,0.7)');
    pips += `<span class="pip" style="background:${on ? c : 'rgba(255,255,255,0.14)'}"></span>`;
  }
  status.push(`<span class="pips">${pips}</span>`);
  rowEl.querySelector('.status').innerHTML = status.join('');

  [
    ['PTS', p.pts, 20, false],
    ['REB', p.reb, 10, false],
    ['AST', p.ast, 10, false],
    ['DEF', p.def, 100, true],
  ].forEach(([label, v, max, pct]) => {
    const br = rowEl.querySelector(`.barrow[data-bar="${label}"]`);
    if (!br) return;
    const fillPct = Math.min(v / max, 1) * 100;
    const maxed = pct ? v >= 80 : v >= max;
    const color = pct ? (v >= 80 ? BLUE : GREEN) : (v >= max ? BLUE : GREEN);
    const fill = br.querySelector('.fill');
    fill.style.width = `${fillPct}%`;
    fill.style.background = color;
    fill.style.color = color;
    fill.classList.toggle('maxed', maxed);
    br.querySelector('.bv').textContent = pct ? `${v}%` : v;
  });

  rowEl.classList.toggle('spot', !!p.spot);
  rowEl.classList.toggle('isout', !!p.out);
}

function updateTeamPanel(panelEl, teamPanel, awayColor, homeColor) {
  if (!panelEl || !teamPanel) return;
  const a = teamPanel.away || {};
  const h = teamPanel.home || {};
  const specs = [
    { key: 'reb', a: a.reb, h: h.reb, lowBetter: false, format: (v) => String(Math.round(v)) },
    { key: 'to', a: a.to, h: h.to, lowBetter: true, format: (v) => String(Math.round(v)) },
    { key: 'fb', a: a.fb, h: h.fb, lowBetter: false, format: (v) => String(Math.round(v)) },
    { key: 'paint', a: a.paint, h: h.paint, lowBetter: false, format: (v) => String(Math.round(v)) },
    { key: 'fg', a: a.fgPct, h: h.fgPct, lowBetter: false, rate: true, format: (v) => (Number(v) || 0).toFixed(1) },
    { key: 'tpm', a: a.tpm, h: h.tpm, lowBetter: false, rate: true, format: (v) => String(Math.round(v)) },
    // Fouls read as accumulating trouble, so the bar grows toward the team in it, in that
    // team's colour. `lowBetter` still governs the white value highlight — fewer fouls is
    // still the better number — so only the pill is inverted, not the judgement.
    { key: 'fouls', a: a.fouls, h: h.fouls, lowBetter: true, pullToHigh: true, format: (v) => String(Math.round(v)) },
  ];
  specs.forEach((spec) => {
    const row = panelEl.querySelector(`.tsr[data-stat="${spec.key}"]`);
    if (!row) return;
    const av = Number(spec.a) || 0;
    const hv = Number(spec.h) || 0;
    const va = row.querySelector('.va');
    const vh = row.querySelector('.vh');
    va.textContent = spec.format(av);
    vh.textContent = spec.format(hv);
    const aLead = spec.lowBetter ? av < hv : av > hv;
    const hLead = spec.lowBetter ? hv < av : hv > av;
    va.classList.toggle('lead', aLead);
    vh.classList.toggle('lead', hLead);
    if (spec.rate) return;
    const pull = row.querySelector('.pull');
    if (!pull) return;
    const edge = Math.abs(av - hv);
    const widthPct = edge === 0 ? 0 : Math.min(46, 8 + edge * 2.5);
    const pullsAway = spec.pullToHigh ? av > hv : aLead;
    if (edge === 0) {
      pull.style.width = '0';
      pull.style.left = '50%';
      pull.style.right = 'auto';
      pull.style.background = 'transparent';
    } else if (pullsAway) {
      pull.style.right = '50%';
      pull.style.left = 'auto';
      pull.style.width = `${widthPct}%`;
      pull.style.background = awayColor;
    } else {
      pull.style.left = '50%';
      pull.style.right = 'auto';
      pull.style.width = `${widthPct}%`;
      pull.style.background = homeColor;
    }
  });
}

/* ===================== CARDS (brief §8) =====================
 * One at a time, in the already-reserved 200px slot. Four types share one component: a tag,
 * a body, and a mono sub-line. Copy never lives here — every string arrives on the card model
 * from the moment pack (see simMomentCopy.js).
 */

/** Hold is the same for every type, clutch included. */
const CARD_HOLD_MS = 2600;
/** Entry transition; exit is a plain fade of the same length. */
const CARD_ENTER_MS = 180;

const CARD_COLORS = { green: GREEN, blue: BLUE, orange: ORANGE, red: RED, gold: GOLD };

/** Copy packs name colours; resolve to the palette, never to a raw value from data. */
function cardColor(name) {
  return CARD_COLORS[String(name || '').toLowerCase()] || GREEN;
}

/**
 * Margin is NOT a separate component — it is the §7 tug at higher emphasis, and it must be
 * whichever tug currently has the widest edge. Rates (FG%, 3PM) are excluded: they are pivot
 * rows, not tugs, so they have no edge to promote.
 */
function widestMarginStat(teamPanel, stats) {
  const a = (teamPanel && teamPanel.away) || {};
  const h = (teamPanel && teamPanel.home) || {};
  let best = null;
  (stats || []).forEach((spec) => {
    const av = Number(a[spec.key]) || 0;
    const hv = Number(h[spec.key]) || 0;
    const edge = Math.abs(av - hv);
    if (edge <= 0) return;
    if (!best || edge > best.edge) best = { key: spec.key, label: spec.label, away: av, home: hv, edge };
  });
  return best;
}

function marginBodyHtml(m, awayColor, homeColor) {
  const homeBetter = m.home > m.away;
  const edge = Math.abs(m.home - m.away);
  const pct = Math.min(edge / Math.max(m.home, m.away, 1), 1) * 50;
  const col = homeBetter ? homeColor : awayColor;
  const dim = 'rgba(255,255,255,.45)';
  return '<div class="cmargin">' +
    '<div class="cmrow">' +
      `<span class="cmval" style="color:${homeBetter ? dim : '#fff'}">${esc(m.away)}</span>` +
      `<span class="cmval" style="color:${homeBetter ? '#fff' : dim}">${esc(m.home)}</span>` +
    '</div>' +
    `<div class="cmtug"><div class="pull" style="${homeBetter ? 'left:50%' : 'right:50%'};width:${pct}%;` +
      `background:linear-gradient(${homeBetter ? '90deg' : '270deg'},${col}44,${col})"></div></div>` +
  '</div>';
}

/**
 * Build a card's markup from its model. Every visible string comes from the model.
 * @param {object} c { kind, tag, color, line, sub, margin?, ctx? }
 */
function cardHtml(c, awayColor, homeColor) {
  const color = cardColor(c.color);
  let tag = '';
  let body = '';
  if (c.kind === 'margin' && c.margin) {
    tag = `<span class="ctag" style="color:${color};border-color:${color}66">${esc(c.margin.label)}</span>`;
    body = marginBodyHtml(c.margin, awayColor, homeColor);
  } else if (c.kind === 'context' && c.ctx) {
    // The setting sits beside its outcome and makes no claim. No probability, ever.
    tag = `<div class="cset">${esc(c.ctx.setting)}: <b>${esc(c.ctx.value)}</b></div>`;
    body = `<div class="cbig"><span class="n">${esc(c.ctx.now)}</span><span class="l">${esc(c.ctx.stat)}</span></div>`;
  } else {
    tag = `<span class="ctag" style="color:${color};border-color:${color}66">${esc(c.tag)}</span>`;
    body = `<div class="cline">${esc(c.line)}</div>`;
  }
  const sub = c.sub ? `<div class="csub">${esc(c.sub)}</div>` : '';
  return `<div class="card enter" data-card data-kind="${esc(c.kind || 'moment')}" style="--cc:${color}55">${tag}${body}${sub}</div>`;
}

/**
 * Cadence debug panel (brief §9: "instrument this").
 *
 * Every fired card AND every suppressed candidate with its reason, plus measured per-quarter
 * counts and the share of runtime with a card up. Silent suppression is untunable — the
 * reasons are the whole point, because after Q1 it is the rest floor, the player cooldown and
 * event supply that bind, not the card-to-card gap.
 *
 * Enabled with ?debug_cards=1 (matching the existing debug_pc convention), never by default.
 */
function cardsDebugEnabled() {
  try {
    if (typeof window === 'undefined') return false;
    if (window.DEBUG_CARDS) return true;
    return new URLSearchParams(window.location.search).has('debug_cards');
  } catch (e) {
    return false;
  }
}

function renderCardsDebug(el, cadence) {
  if (!el) return;
  if (!cadence) { el.innerHTML = '<h4>cadence</h4><div class="row"><span>waiting for copy…</span></div>'; return; }
  const st = cadence.stats();
  const prof = cadence.profile();
  const target = 12;   // brief §9: roughly a dozen cards across the broadcast
  const rows = st.byQuarter.map((q) => `<div><b>${q.fired}</b><i>Q${q.q}</i></div>`).join('');
  const reasons = Object.entries(st.suppressedByReason)
    .sort((a, b) => b[1] - a[1])
    .map(([r, n]) => `<div class="row"><span>${esc(r)}</span><b>${n}</b></div>`).join('');
  const log = cadence.log.slice(-40).reverse().map((e) => `
    <div class="lg${e.fired ? ' f' : ''}">
      <span>${e.t.toFixed(0)}s</span>
      <span>${esc(String(e.tag || '').slice(0, 9))}</span>
      <span class="x">${esc(e.fired ? (e.detail || '') : e.reason)}</span>
    </div>`).join('');
  el.innerHTML = `
    <h4>cadence · Q${cadence.quarter}${cadence.suspended ? ' · HELD' : ''}</h4>
    <div class="row"><span>playback</span><b>${st.t.toFixed(1)}s</b></div>
    <div class="row"><span>cards fired</span><b>${st.total} / ~${target}</b></div>
    <div class="row"><span>share on screen</span><b>${st.share}%</b></div>
    <div class="row"><span>suppressed</span><b>${st.suppressed}</b></div>
    <div class="hr"></div>
    <h4>fired by quarter</h4>
    <div class="grid">${rows}</div>
    <div class="hr"></div>
    <h4>gates now</h4>
    <div class="row"><span>gap / rest</span><b>${prof.gap}s / ${prof.restFloor}s</b></div>
    <div class="row"><span>player cool</span><b>${prof.playerCool}s</b></div>
    <div class="row"><span>variety hold</span><b>${Math.round(prof.variety * 100)}%</b></div>
    <div class="row"><span>by type</span><b>M${st.counts.moment} R${st.counts.run} G${st.counts.margin} C${st.counts.context}</b></div>
    <div class="hr"></div>
    <h4>held, by reason</h4>
    <div class="reasons" data-dbg-reasons>${reasons || '<div class="row"><span>none yet</span></div>'}</div>
    <div class="hr"></div>
    <h4>candidates (newest first)</h4>
    <div class="log">${log}</div>`;
}

function setRestMode(root, mode) {
  const wormBtn = root.querySelector('.ctlseg [data-v="worm"]');
  const teamBtn = root.querySelector('.ctlseg [data-v="team"]');
  const panel = root.querySelector('[data-team-panel]');
  const isTeam = mode === 'team';
  if (wormBtn) wormBtn.classList.toggle('on', !isTeam);
  if (teamBtn) teamBtn.classList.toggle('on', isTeam);
  if (panel) panel.style.display = isTeam ? 'flex' : 'none';
  root.dataset.restMode = isTeam ? 'team' : 'worm';
}

/**
 * @param {{teams, frames}} timeline
 * @param {object} opts
 * @returns {Promise<void>}
 */
export function showSimGamePresentation(timeline, opts = {}) {
  const { teams, frames } = timeline || {};
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
    // The overlay's height depends on where the scoreboard ends, so re-fit after moving.
    applyFit();
  };
  positionBelowScoreboard();
  window.addEventListener('resize', positionBelowScoreboard);

  let restMode = 'worm';
  let cadence = null;          // set once the copy pack resolves; see below
  // Declared before the control handler below, which reads it on click.
  const dbgEl = cardsDebugEnabled() ? document.createElement('div') : null;
  if (dbgEl) {
    dbgEl.className = 'sgp-dbg';
    root.appendChild(dbgEl);
    renderCardsDebug(dbgEl, null);
  }
  setRestMode(root, restMode);
  root.querySelector('.ctlseg')?.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-v]');
    if (!btn) return;
    restMode = btn.getAttribute('data-v') === 'team' ? 'team' : 'worm';
    setRestMode(root, restMode);
    // Team Stats is a hold mode: a card already up gives the slot back at once, and the
    // engine stops queueing rather than banking candidates to dump on the way back.
    if (cadence) cadence.suspend(restMode === 'team');
    if (dbgEl) renderCardsDebug(dbgEl, cadence);
    if (restMode === 'team') endCard();
  });

  /* ---- card presenter -------------------------------------------------------------
   * Owns only the showing of a card: entry, hold, exit, and the board dim underneath.
   * WHICH card and WHEN is the cadence engine's job; this deliberately knows neither.
   */
  const slotEl = root.querySelector('[data-slot]');
  const zonesEl = root.querySelector('.zones');
  const cardTimers = [];
  let cardBusy = false;

  const clearCardTimers = () => { cardTimers.splice(0).forEach(clearTimeout); };

  const endCard = () => {
    clearCardTimers();
    if (slotEl) slotEl.querySelectorAll('[data-card]').forEach((n) => n.remove());
    if (zonesEl) zonesEl.classList.remove('is-carddim');
    cardBusy = false;
  };

  /**
   * Present one card. Resolves when the slot is free again.
   * Returns false without rendering when Team Stats is up: the user asked for the numbers,
   * and taking them away is the one thing not to do. Nothing queues while held.
   */
  const showCard = (model) => {
    if (!slotEl || !model) return false;
    if (root.dataset.restMode === 'team') return false;
    if (cardBusy) return false;
    cardBusy = true;
    slotEl.insertAdjacentHTML('beforeend', cardHtml(model, teams.away.color, teams.home.color));
    const el = slotEl.querySelector('[data-card]');
    if (zonesEl) zonesEl.classList.add('is-carddim');
    const settle = () => { if (el) el.classList.remove('enter'); };
    if (prefersReduced) settle();
    else if (typeof requestAnimationFrame === 'function') requestAnimationFrame(() => requestAnimationFrame(settle));
    else cardTimers.push(setTimeout(settle, 16));

    cardTimers.push(setTimeout(() => {
      if (el) el.classList.add('leaving');
      if (zonesEl) zonesEl.classList.remove('is-carddim');
      cardTimers.push(setTimeout(endCard, prefersReduced ? 0 : CARD_ENTER_MS));
    }, CARD_HOLD_MS));
    return true;
  };

  const wormFill = root.querySelector('.wormfill');
  const wlTeam = root.querySelector('.wl-team');
  const teamPanelEl = root.querySelector('[data-team-panel]');

  const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  const updateScoreboard = (frame) => {
    if (!driveScoreboard) return;
    const s = frame.score;
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
    const wormState = frame.worm && frame.worm.samples
      ? frame.worm
      : { samples: [{ elapsed: 0, margin: 0 }], elapsed: 0, domain: 4 * REG_Q_SEC };
    const w = Math.max(200, Math.round(wormFill.clientWidth || 376));
    const h = Math.max(120, Math.round(wormFill.clientHeight || 200));
    wormFill.innerHTML = wormSvg(wormState, w, h, teams.home.color, teams.away.color);

    const samples = wormState.samples || [];
    const cur = samples.length ? samples[samples.length - 1].margin : 0;
    if (cur === 0) {
      wlTeam.textContent = 'TIED';
      wlTeam.style.color = 'rgba(255,255,255,0.5)';
    } else {
      const lead = cur > 0 ? teams.home : teams.away;
      wlTeam.textContent = `${lead.abbr} +${Math.abs(cur)}`;
      wlTeam.style.color = lead.color;
    }

    POSITIONS.forEach((pos) => {
      const awayRow = root.querySelector(`.board.away .prow[data-pos="${pos}"]`);
      const homeRow = root.querySelector(`.board.home .prow[data-pos="${pos}"]`);
      const ai = POSITIONS.indexOf(pos);
      if (awayRow && frame.away[ai]) updatePlayerRow(awayRow, frame.away[ai], teams.away.color);
      if (homeRow && frame.home[ai]) updatePlayerRow(homeRow, frame.home[ai], teams.home.color);
    });

    root.querySelector('[data-bench="away"]').innerHTML = benchHtml(frame.benchAway);
    root.querySelector('[data-bench="home"]').innerHTML = benchHtml(frame.benchHome);
    updateTeamPanel(teamPanelEl, frame.teamPanel, teams.away.color, teams.home.color);

    if (AUTO_TEAM_STATS_ON_LULLS) {
      // reserved — flag default off
    }

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
    }

    updateScoreboard(frame);
  };

  const quarterCounts = {};
  frames.forEach((f) => {
    if (f.phase === 'live' && !f.breakSummary) quarterCounts[f.quarter] = (quarterCounts[f.quarter] || 0) + 1;
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

  /* ---- cadence ----------------------------------------------------------------------
   * Copy loads asynchronously; until it lands the broadcast simply runs without cards
   * rather than blocking the tip-off on a fetch.
   */
  loadMomentCopy().then((pack) => {
    cadence = new CardCadence({
      pack,
      teams,
      seed: (frames && frames.length) || 7,
      onCard: (model) => showCard(model),
    });
    root.__cadence = cadence;
    if (dbgEl) renderCardsDebug(dbgEl, cadence);
  });

  root.__cards = { showCard, endCard, isBusy: () => cardBusy };

  return new Promise((resolve) => {
    const timers = [];
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      fadeOutPregameBed();
      timers.forEach(clearTimeout);
      clearCardTimers();
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
      // The engine measures PLAYBACK seconds — the time the viewer actually experiences —
      // so a frame's own hold is the tick, not game clock.
      if (cadence) cadence.step(frame, hold / 1000);
      if (dbgEl) renderCardsDebug(dbgEl, cadence);
      i += 1;
      timers.push(setTimeout(step, hold));
    };

    // Skip control removed for v1 simplify — no click-to-skip.
    step();
  });
}
