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
    .sgp-root .overlay{position:relative;flex:1;min-width:0;display:flex;flex-direction:column;padding:16px 26px 12px;gap:14px;isolation:isolate;
      background:radial-gradient(120% 78% at 50% 30%,rgba(39,64,142,.13),transparent 62%),radial-gradient(90% 70% at 50% 120%,rgba(247,148,32,.045),transparent 60%),#0b0d14}
    .sgp-root .overlay::before{content:'';position:absolute;left:50%;bottom:-54%;width:94%;aspect-ratio:1/1;transform:translateX(-50%);border-radius:50%;border:1px solid rgba(255,255,255,.04);pointer-events:none}
    .sgp-root.fade-in{animation:sgpFade .45s ease}
    @keyframes sgpFade{from{opacity:0}to{opacity:1}}
    .sgp-root.dissolving{opacity:0;transition:opacity .45s ease}

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
    .sgp-root .wormblock{display:flex;flex-direction:column;flex-shrink:0;height:246px}
    .sgp-root .wormfill{position:relative;flex:1;min-height:0;overflow:hidden;margin-top:4px}
    .sgp-root .wormfill .wormsvg{position:absolute;inset:0;width:100%;height:100%;margin:0}
    .sgp-root .wl-head{display:flex;align-items:baseline;justify-content:space-between;height:14px}
    .sgp-root .wl-cap{font-family:ui-monospace,Menlo,monospace;font-size:9px;letter-spacing:.16em;color:var(--w40)}
    .sgp-root .wl-team{font-family:'Bebas Neue',sans-serif;font-size:19px;letter-spacing:.04em;line-height:1}
    .sgp-root .wl-axis{display:flex;justify-content:space-between;margin-top:3px;font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.06em;color:var(--w25)}
    .sgp-root .wormdot{filter:drop-shadow(0 0 4px currentColor)}
    .sgp-root .slot{position:relative;flex-shrink:0;height:200px;display:flex;flex-direction:column;justify-content:center}
    .sgp-root .slot.framed{border-radius:10px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.05)}
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

    .sgp-root .bench{display:flex;align-items:center;gap:7px;overflow:hidden}
    .sgp-root .bench.home{flex-direction:row-reverse}
    .sgp-root .bench-lbl{font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.14em;color:var(--w25);flex-shrink:0}
    .sgp-root .bchip{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.045);border:1px solid var(--hair);border-radius:20px;padding:3px 9px;font-size:10.5px;white-space:nowrap}
    .sgp-root .bchip b{font-weight:700;color:var(--w70)}
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

    @media (prefers-reduced-motion: reduce){
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
          <div class="slot framed" data-slot>
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
  const maxAbs = Math.max(6, ...margins.map((m) => Math.abs(m)));
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

function benchHtml(chips) {
  if (!chips || !chips.length) return '<span class="bench-lbl">BENCH</span>';
  const items = chips.map((c) =>
    `<span class="bchip${c.out ? ' out' : ''}"><b>${esc(c.name)}</b>${c.out ? '<span class="bout">OUT</span>' : ''}<span class="bstat">${c.pts}p · ${c.reb}r</span></span>`
  ).join('');
  return `<span class="bench-lbl">BENCH</span>${items}`;
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
    { key: 'fouls', a: a.fouls, h: h.fouls, lowBetter: true, format: (v) => String(Math.round(v)) },
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
    if (edge === 0) {
      pull.style.width = '0';
      pull.style.left = '50%';
      pull.style.right = 'auto';
      pull.style.background = 'transparent';
    } else if (aLead) {
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

  const positionBelowScoreboard = () => {
    const sbEl = document.getElementById('scoreboard');
    const top = sbEl ? Math.max(0, Math.round(sbEl.getBoundingClientRect().bottom)) : 0;
    root.style.top = `${top}px`;
  };
  positionBelowScoreboard();
  window.addEventListener('resize', positionBelowScoreboard);

  let restMode = 'worm';
  setRestMode(root, restMode);
  root.querySelector('.ctlseg')?.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-v]');
    if (!btn) return;
    restMode = btn.getAttribute('data-v') === 'team' ? 'team' : 'worm';
    setRestMode(root, restMode);
  });

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

  return new Promise((resolve) => {
    const timers = [];
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      fadeOutPregameBed();
      timers.forEach(clearTimeout);
      window.removeEventListener('resize', positionBelowScoreboard);
      root.classList.add('dissolving');
      const t = setTimeout(() => { root.remove(); resolve(); }, prefersReduced ? 0 : 450);
      timers.push(t);
    };

    let i = 0;
    const step = () => {
      if (done) return;
      if (i >= frames.length) { finish(); return; }
      renderFrame(frames[i]);
      const hold = holdFor(frames[i]);
      i += 1;
      timers.push(setTimeout(step, hold));
    };

    // Skip control removed for v1 simplify — no click-to-skip.
    step();
  });
}
