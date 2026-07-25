/**
 * Sim Game Presentation — Act 2 overlay + playback (Chunks 2 & 3).
 *
 * A center-court DOM overlay (mirrors Act 1's preGameExperience.js pattern) that
 * plays a simmed game back as a broadcast. It does NOT re-render the real
 * scoreboard or side panels — it DRIVES the real scoreboard from playback frames
 * and occupies the center court region only.
 *
 * Input: the assembler's `{ teams, frames }` (simTimelineAssembler.js). Frames are
 * consumed as-is; this module renders and eases — it derives no game state.
 *
 * UESS: pure renderer. Bars ease between two emitted stat points (§3-sanctioned,
 * same contract as sprite tweening). MO is a binary threshold read per frame —
 * never interpolated. Score/clock/lineups are sampled from emitted values.
 *
 * Design values locked in Prompt 2 §5. Moments are tabled (§2): the ~44px ticker
 * slot is rendered empty and never filled or reflowed away.
 */

const POSC = { PG: '#4A90D9', SG: '#7B5EA7', SF: '#3A8C4A', PF: '#C0392B', C: '#D4A017' };
const RT_HEX = { 'rt-elite': '#4A90D9', 'rt-high': '#34EC27', 'rt-mid': '#FFD700', 'rt-low': '#ff6d6d' };
const GREEN = '#34EC27', BLUE = '#4A90D9', ORANGE = '#F79420', RED = '#ff6d6d';
const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];

// Pacing (§5: each quarter across 15–30s of playback).
const QUARTER_MS = 18000;
const FRAME_MIN_MS = 130;
const FRAME_MAX_MS = 900;
const PRETIP_MS = 2200;
const BREAK_MS = 2800;
const FINAL_MS = 2600;

const SIL = `<svg viewBox="0 0 100 100"><circle cx="50" cy="34" r="19" fill="rgba(255,255,255,0.15)"/><path d="M12 100c0-22 17-36 38-36s38 14 38 36" fill="rgba(255,255,255,0.15)"/></svg>`;
const FLAME = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c1 3-1 4.5-2.5 6.5C8 10.7 7 12.4 7 14.5 7 18 9.2 21 12 21s5-3 5-6.5c0-2.4-1.3-4-2.4-5.6.2 1.6-.4 2.7-1.3 3.3.5-2.6-.9-6.4-1.3-10.2z"/></svg>`;
const SNOW = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1M12 5.5l2 2M12 5.5l-2 2M12 18.5l2-2M12 18.5l-2-2M5.5 12l2 2M5.5 12l2-2M18.5 12l-2 2M18.5 12l-2-2"/></svg>`;

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/** RT → hex via the canonical 4-band rtBucket.js (reuse, don't fork). null → no badge. */
function rtColor(rt) {
  if (rt == null) return null;
  const cls = (typeof window !== 'undefined' && window.getRtBucketClass) ? window.getRtBucketClass(rt) : null;
  return (cls && RT_HEX[cls]) || null;
}

/** Real headshot via the same resolver Act 1 uses; silhouette is fallback only. */
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
    /* Full-width overlay from just below the scoreboard to the viewport bottom
       (covers the court + both side panels; only the scoreboard stays). The top
       offset is set in JS from the live scoreboard height so no row hides under it. */
    .sgp-root{position:fixed;left:0;right:0;bottom:0;top:0;z-index:2000;overflow:hidden;display:flex;align-items:stretch;
      font-family:Inter,system-ui,sans-serif;color:rgba(255,255,255,.90);-webkit-font-smoothing:antialiased}
    .sgp-root .overlay{position:relative;flex:1;min-width:0;display:flex;flex-direction:column;padding:16px 26px 12px;isolation:isolate;
      background:radial-gradient(120% 80% at 50% 34%,rgba(39,64,142,.14),transparent 60%),radial-gradient(90% 70% at 50% 118%,rgba(247,148,32,.05),transparent 60%),#0b0d14}
    .sgp-root .overlay::before{content:'';position:absolute;left:50%;bottom:-52%;width:96%;aspect-ratio:1/1;transform:translateX(-50%);border-radius:50%;border:1px solid rgba(255,255,255,.045);pointer-events:none}
    .sgp-root.fade-in{animation:sgpFade .45s ease}
    @keyframes sgpFade{from{opacity:0}to{opacity:1}}
    .sgp-root.dissolving{opacity:0;transition:opacity .45s ease}

    .sgp-root .ov-worm{position:relative;flex-shrink:0;margin-bottom:26px}
    .sgp-root .wl-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:3px}
    .sgp-root .wl-cap{font-size:9.5px;font-weight:800;letter-spacing:.22em;color:rgba(255,255,255,.40)}
    .sgp-root .wl-team{font-family:'Bebas Neue',sans-serif;font-size:20px;letter-spacing:.04em}
    .sgp-root .wormsvg{display:block;width:100%;height:60px}
    .sgp-root .wormdot{filter:drop-shadow(0 0 4px currentColor)}
    .sgp-root .wl-axis{display:flex;justify-content:space-between;margin-top:2px;font-family:ui-monospace,Menlo,monospace;font-size:8px;letter-spacing:.06em;color:rgba(255,255,255,.40)}
    .sgp-root .pretip-lbl{position:absolute;top:40px;left:0;right:0;text-align:center;font-family:'Bebas Neue',sans-serif;font-size:16px;letter-spacing:.28em;color:rgba(255,255,255,.40);z-index:2;pointer-events:none;display:none}
    .sgp-root.is-pretip .pretip-lbl{display:block}

    .sgp-root .rows{flex:1;display:flex;flex-direction:column;justify-content:center;gap:8px;min-height:0;position:relative;z-index:1}
    .sgp-root .pair{display:grid;grid-template-columns:1fr 78px 1fr;align-items:center;position:relative}
    .sgp-root .pair:not(:last-child)::after{content:'';position:absolute;left:9%;right:9%;bottom:-4px;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.08) 24%,rgba(255,255,255,.08) 76%,transparent)}
    .sgp-root .poscol{display:flex;align-items:center;justify-content:center}
    .sgp-root .posmark{font-family:'Bebas Neue',sans-serif;font-size:23px;letter-spacing:.04em}

    .sgp-root .prow{display:flex;align-items:center;gap:12px;position:relative;padding:4px 8px;border-radius:12px;transition:transform .3s,filter .3s}
    .sgp-root .prow.home{flex-direction:row-reverse}
    .sgp-root .prow.isout{filter:saturate(.5) brightness(.82)}
    .sgp-root .prow.spot{background:radial-gradient(120% 160% at 50% 50%,rgba(247,148,32,.12),transparent 72%)}
    .sgp-root .prow.spot::before{content:'';position:absolute;inset:0;border-radius:12px;box-shadow:inset 0 0 0 1px rgba(247,148,32,.4),0 0 22px rgba(247,148,32,.16);animation:sgpSpot 2.6s ease-in-out infinite}
    @keyframes sgpSpot{0%,100%{box-shadow:inset 0 0 0 1px rgba(247,148,32,.34),0 0 16px rgba(247,148,32,.1)}50%{box-shadow:inset 0 0 0 1px rgba(247,148,32,.55),0 0 28px rgba(247,148,32,.22)}}

    .sgp-root .head{position:relative;flex-shrink:0;width:62px;height:62px;border-radius:13px;overflow:hidden;background:linear-gradient(180deg,#1b2130,#10141d);border:2px solid rgba(255,255,255,.16);box-shadow:0 6px 16px rgba(0,0,0,.4)}
    .sgp-root .head img{width:100%;height:100%;object-fit:cover;object-position:center top;display:block}
    .sgp-root .head .sil{position:absolute;inset:0;display:flex;align-items:flex-end;justify-content:center}
    .sgp-root .head .sil svg{width:80%;height:90%}
    .sgp-root .rtb{position:absolute;top:4px;left:4px;z-index:2;font-family:'Bebas Neue',sans-serif;font-size:13px;line-height:1;letter-spacing:.02em;padding:2px 5px 1px;border-radius:4px;color:#0b0d14;box-shadow:0 1px 4px rgba(0,0,0,.45)}

    .sgp-root .pbody{flex:1;min-width:0}
    .sgp-root .pname{display:flex;align-items:center;gap:7px;line-height:1;margin-bottom:5px}
    .sgp-root .prow.home .pname{flex-direction:row-reverse}
    .sgp-root .pname .nm{font-size:15px;font-weight:700;color:#fff;white-space:nowrap}
    .sgp-root .pname .jn{font-size:12px;font-weight:600;color:rgba(255,255,255,.40)}
    .sgp-root .spotmark{font-family:'Bebas Neue',sans-serif;font-size:12px;letter-spacing:.08em}
    .sgp-root .tag-in{font-family:'Bebas Neue',sans-serif;font-size:11px;letter-spacing:.06em;color:${GREEN};border:1px solid rgba(52,236,39,.5);border-radius:4px;padding:1px 5px 0}
    .sgp-root .tag-out{font-family:'Bebas Neue',sans-serif;font-size:11px;letter-spacing:.06em;color:#fff;background:${RED};border-radius:4px;padding:2px 6px 1px}
    .sgp-root .tag-ft{font-family:'Bebas Neue',sans-serif;font-size:11px;letter-spacing:.06em;color:#15181f;background:#FFD700;border-radius:4px;padding:2px 6px 1px}

    .sgp-root .status{display:flex;align-items:center;gap:8px;margin-bottom:6px;height:16px}
    .sgp-root .prow.home .status{flex-direction:row-reverse}
    .sgp-root .mo{display:flex;width:15px;height:15px}
    .sgp-root .mo svg{width:100%;height:100%}
    .sgp-root .flame{animation:sgpFlick 1.1s ease-in-out infinite}
    @keyframes sgpFlick{0%,100%{transform:scale(1) rotate(-1deg);opacity:.92}50%{transform:scale(1.14) rotate(2deg);opacity:1}}
    .sgp-root .pips{display:flex;gap:2.5px}
    .sgp-root .prow.home .pips{flex-direction:row-reverse}
    .sgp-root .pip{width:11px;height:4px;border-radius:2px}

    .sgp-root .bars{display:flex;flex-direction:column;gap:4px}
    .sgp-root .barrow{display:grid;grid-template-columns:26px 1fr 30px;align-items:center;gap:8px}
    .sgp-root .barrow.home{grid-template-columns:30px 1fr 26px}
    .sgp-root .bl{font-size:8px;font-weight:800;letter-spacing:.06em;color:rgba(255,255,255,.40);text-transform:uppercase}
    .sgp-root .barrow.away .bl{text-align:left}.sgp-root .barrow.home .bl{text-align:right}
    .sgp-root .bv{font-size:12px;font-weight:700;color:rgba(255,255,255,.90);font-variant-numeric:tabular-nums}
    .sgp-root .barrow.away .bv{text-align:right}.sgp-root .barrow.home .bv{text-align:left}
    .sgp-root .track{position:relative;height:9px;border-radius:5px;background:rgba(255,255,255,.07);overflow:hidden}
    .sgp-root .track.home{display:flex;justify-content:flex-end}
    .sgp-root .fill{height:100%;border-radius:5px;transition:width .5s cubic-bezier(.2,.7,.2,1),background .4s ease}
    .sgp-root .fill.maxed{box-shadow:0 0 8px 0 currentColor}

    .sgp-root .bench-wrap{display:flex;justify-content:space-between;gap:20px;flex-shrink:0;margin:8px 0 2px;min-height:22px}
    .sgp-root .bench{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .sgp-root .bench.home{flex-direction:row-reverse}
    .sgp-root .bench-lbl{font-size:8px;font-weight:800;letter-spacing:.16em;color:rgba(255,255,255,.40)}
    .sgp-root .bchip{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:3px 10px;font-size:11px}
    .sgp-root .bchip b{font-weight:700;color:rgba(255,255,255,.70)}
    .sgp-root .bchip .bstat{color:rgba(255,255,255,.40);font-variant-numeric:tabular-nums}
    .sgp-root .bchip.out{opacity:.7}
    .sgp-root .bout{font-family:'Bebas Neue',sans-serif;font-size:10px;color:#fff;background:${RED};border-radius:3px;padding:1px 4px 0;letter-spacing:.04em}

    /* Moments tabled (§2): slot kept empty at fixed height so nothing reflows. */
    .sgp-root .ticker{flex-shrink:0;height:44px;border:1px solid rgba(255,255,255,.05);border-radius:10px;background:linear-gradient(90deg,rgba(255,255,255,.03),rgba(255,255,255,.01))}

    .sgp-root.is-break .rows,.sgp-root.is-break .bench-wrap,.sgp-root.is-break .ticker{filter:blur(3px) brightness(.42);opacity:.5}
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
      .sgp-root .fill{transition:none}
      .sgp-root .prow.spot::before,.sgp-root .flame{animation:none}
      .sgp-root.fade-in{animation:none}
    }
  `;
  document.head.appendChild(style);
}

// ── Static skeleton (Chunk 2) ────────────────────────────────────────────
function playerRowSkeleton(side) {
  const bars = ['PTS', 'REB', 'AST', 'DEF'].map((label) => `
    <div class="barrow ${side}" data-bar="${label}">
      ${side === 'home'
        ? `<span class="bv"></span><div class="track home"><div class="fill"></div></div><span class="bl">${label}</span>`
        : `<span class="bl">${label}</span><div class="track"><div class="fill"></div></div><span class="bv"></span>`}
    </div>`).join('');
  const head = `<div class="head"><span class="rtb" style="display:none"></span><img alt="" style="display:none"><div class="sil">${SIL}</div></div>`;
  const body = `<div class="pbody">
      <div class="pname"></div>
      <div class="status"></div>
      <div class="bars">${bars}</div>
    </div>`;
  return `<div class="prow ${side}" data-side="${side}">${side === 'home' ? body + head : head + body}</div>`;
}

function buildSkeleton(teams) {
  const rows = POSITIONS.map((pos) => `
    <div class="pair" data-pos="${pos}">
      ${playerRowSkeleton('away')}
      <div class="poscol"><span class="posmark" style="color:${POSC[pos]}">${pos}</span></div>
      ${playerRowSkeleton('home')}
    </div>`).join('');

  const root = document.createElement('div');
  root.className = 'sgp-root fade-in';
  root.innerHTML = `
    <div class="overlay">
      <div class="ov-worm">
        <div class="wl-head"><span class="wl-cap">LEAD MARGIN</span><span class="wl-team"></span></div>
        <div class="worm-host"></div>
        <div class="wl-axis"><span>TIP</span><span>Q1</span><span>Q2</span><span>HALF</span><span>Q3</span><span>Q4</span></div>
      </div>
      <div class="pretip-lbl">STARTING LINEUPS · TIP-OFF</div>
      <div class="rows">${rows}</div>
      <div class="bench-wrap"><div class="bench away"></div><div class="bench home"></div></div>
      <div class="ticker"></div>
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

// ── Worm SVG (ported from prototype) ─────────────────────────────────────
function wormSvg(margins, w, h, home, away) {
  const pad = 6, mid = h / 2, n = margins.length;
  const maxAbs = Math.max(6, ...margins.map((m) => Math.abs(m)));
  const x = (i) => pad + (n <= 1 ? 0 : (i * (w - pad * 2)) / (n - 1));
  const y = (m) => mid - (m / maxAbs) * (mid - pad);
  let line = '', area = `M ${x(0)} ${mid} `;
  margins.forEach((m, i) => {
    line += (i ? 'L' : 'M') + ` ${x(i).toFixed(1)} ${y(m).toFixed(1)} `;
    area += `L ${x(i).toFixed(1)} ${y(m).toFixed(1)} `;
  });
  area += `L ${x(n - 1)} ${mid} Z`;
  const cur = margins[n - 1];
  return `<svg class="wormsvg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs>
      <linearGradient id="sgpwg-up" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${home}" stop-opacity="0.42"/><stop offset="1" stop-color="${home}" stop-opacity="0"/></linearGradient>
      <linearGradient id="sgpwg-dn" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${away}" stop-opacity="0.42"/><stop offset="1" stop-color="${away}" stop-opacity="0"/></linearGradient>
      <clipPath id="sgpclip-up"><rect x="0" y="0" width="${w}" height="${mid}"/></clipPath>
      <clipPath id="sgpclip-dn"><rect x="0" y="${mid}" width="${w}" height="${mid}"/></clipPath>
    </defs>
    <line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="rgba(255,255,255,0.16)" stroke-width="1" stroke-dasharray="3 4"/>
    <path d="${area}" fill="url(#sgpwg-up)" clip-path="url(#sgpclip-up)"/>
    <path d="${area}" fill="url(#sgpwg-dn)" clip-path="url(#sgpclip-dn)"/>
    <path d="${line}" fill="none" stroke="${cur >= 0 ? home : away}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#sgpclip-up)"/>
    <path d="${line}" fill="none" stroke="${away}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#sgpclip-dn)"/>
    <circle class="wormdot" cx="${x(n - 1).toFixed(1)}" cy="${y(cur).toFixed(1)}" r="3.4" fill="${cur >= 0 ? home : away}"/>
  </svg>`;
}

// ── Per-frame update (Chunk 3) ───────────────────────────────────────────
function benchHtml(chips) {
  if (!chips || !chips.length) return '';
  const items = chips.map((c) =>
    `<span class="bchip${c.out ? ' out' : ''}"><b>${esc(c.name)}</b>${c.out ? '<span class="bout">OUT</span>' : ''}<span class="bstat">${c.pts}p · ${c.reb}r</span></span>`
  ).join('');
  return `<span class="bench-lbl">BENCH</span>${items}`;
}

function updatePlayerRow(rowEl, p, side, teamColor) {
  const head = rowEl.querySelector('.head');
  const img = head.querySelector('img');
  const rtb = head.querySelector('.rtb');
  const sil = head.querySelector('.sil');

  // Portrait (only reset src when the occupant changes → avoids reload flicker).
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

  // RT badge — canonical band fill, upper-left both teams; empty if unknown.
  const rc = rtColor(p.rt);
  if (p.rt != null && rc) {
    rtb.style.display = '';
    rtb.style.background = rc;
    rtb.textContent = p.rt;
  } else {
    rtb.style.display = 'none';
    rtb.textContent = '';
  }

  // Name row.
  const nameEl = rowEl.querySelector('.pname');
  nameEl.innerHTML =
    `${p.spot ? `<span class="spotmark" style="color:${ORANGE}">◆ TOP</span>` : ''}` +
    `<span class="nm">${esc(p.name)}</span><span class="jn">#${esc(p.jersey)}</span>` +
    `${p.sub ? '<span class="tag-in">IN</span>' : ''}`;

  // Status strip: hot/cold glyph + foul-trouble/out tag + foul pips.
  const status = [];
  if (p.hot) status.push(`<span class="mo flame" style="color:${ORANGE}">${FLAME}</span>`);
  if (p.cold) status.push(`<span class="mo snow" style="color:${BLUE}">${SNOW}</span>`);
  if (p.out) status.push('<span class="tag-out">FOULED OUT</span>');
  else if (p.fouls >= 4) status.push('<span class="tag-ft">FOUL TROUBLE</span>');
  let pips = '';
  for (let i = 0; i < 5; i++) {
    const on = i < p.fouls;
    const c = p.out ? RED : (p.fouls >= 4 ? '#FFD700' : 'rgba(255,255,255,0.7)');
    pips += `<span class="pip" style="background:${on ? c : 'rgba(255,255,255,0.14)'}"></span>`;
  }
  status.push(`<span class="pips">${pips}</span>`);
  rowEl.querySelector('.status').innerHTML = status.join('');

  // Bars: PTS/20, REB/10, AST/10, DEF% threshold (blue >=80 else green).
  const barSpec = [
    ['PTS', p.pts, 20, false],
    ['REB', p.reb, 10, false],
    ['AST', p.ast, 10, false],
    ['DEF', p.def, 100, true],
  ];
  barSpec.forEach(([label, v, max, pct]) => {
    const br = rowEl.querySelector(`.barrow[data-bar="${label}"]`);
    if (!br) return;
    const fillPct = Math.min(v / max, 1) * 100;
    const maxed = pct ? v >= 80 : v >= max;
    const color = pct ? (v >= 80 ? BLUE : GREEN) : (v >= max ? BLUE : GREEN);
    const fill = br.querySelector('.fill');
    fill.style.width = `${fillPct}%`;
    fill.style.background = color;
    fill.style.color = color; // for the maxed glow (currentColor)
    fill.classList.toggle('maxed', maxed);
    br.querySelector('.bv').textContent = pct ? `${v}%` : v;
  });

  rowEl.classList.toggle('spot', !!p.spot);
  rowEl.classList.toggle('isout', !!p.out);
}

// ── Public entry ─────────────────────────────────────────────────────────
/**
 * Play a simmed game back as a broadcast.
 * @param {{teams, frames}} timeline  from buildSimTimeline
 * @param {object} opts  { mount?: HTMLElement, driveScoreboard?: boolean }
 * @returns {Promise<void>}  resolves after the final beat (caller then shows the completion popup)
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

  // Sit directly beneath the real scoreboard so its top edge never hides a row and
  // the worm reads as attached to the scoreboard (Bug 4). Track on resize.
  const positionBelowScoreboard = () => {
    const sbEl = document.getElementById('scoreboard');
    const top = sbEl ? Math.max(0, Math.round(sbEl.getBoundingClientRect().bottom)) : 0;
    root.style.top = `${top}px`;
  };
  positionBelowScoreboard();
  window.addEventListener('resize', positionBelowScoreboard);

  const overlay = root.querySelector('.overlay');
  const wormHost = root.querySelector('.worm-host');
  const wlTeam = root.querySelector('.wl-team');
  const benchAwayEl = root.querySelector('.bench.away');
  const benchHomeEl = root.querySelector('.bench.home');

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

  const wormWidth = Math.max(400, Math.round((overlay.clientWidth || 1173) - 8));
  const renderFrame = (frame) => {
    // Worm + lead label.
    const margins = frame.worm && frame.worm.length ? frame.worm : [0];
    wormHost.innerHTML = wormSvg(margins, wormWidth, 60, teams.home.color, teams.away.color);
    const cur = margins[margins.length - 1];
    if (cur === 0) {
      wlTeam.textContent = 'TIED';
      wlTeam.style.color = 'rgba(255,255,255,0.5)';
    } else {
      const lead = cur > 0 ? teams.home : teams.away;
      wlTeam.textContent = `${lead.abbr} +${Math.abs(cur)}`;
      wlTeam.style.color = lead.color;
    }

    // Player rows.
    POSITIONS.forEach((pos, i) => {
      const pair = root.querySelector(`.pair[data-pos="${pos}"]`);
      updatePlayerRow(pair.querySelector('.prow.away'), frame.away[i], 'away', teams.away.color);
      updatePlayerRow(pair.querySelector('.prow.home'), frame.home[i], 'home', teams.home.color);
    });

    // Bench rails.
    benchAwayEl.innerHTML = benchHtml(frame.benchAway);
    benchHomeEl.innerHTML = benchHtml(frame.benchHome);

    // Phase flags.
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

  // Pacing: distribute QUARTER_MS across each quarter's live frames.
  const quarterCounts = {};
  frames.forEach((f) => {
    if (f.phase === 'live' && !f.breakSummary) quarterCounts[f.quarter] = (quarterCounts[f.quarter] || 0) + 1;
  });
  const holdFor = (frame) => {
    if (prefersReduced) return frame.breakSummary || frame.phase !== 'live' ? 400 : 40;
    if (frame.phase === 'pretip') return PRETIP_MS;
    if (frame.phase === 'final') return FINAL_MS;
    if (frame.breakSummary) return BREAK_MS;
    const c = quarterCounts[frame.quarter] || 1;
    return Math.min(FRAME_MAX_MS, Math.max(FRAME_MIN_MS, Math.round(QUARTER_MS / c)));
  };

  return new Promise((resolve) => {
    const timers = [];
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
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
      const frame = frames[i];
      renderFrame(frame);
      const hold = holdFor(frame);
      i += 1;
      const t = setTimeout(step, hold);
      timers.push(t);
    };

    // Click to skip straight to the final beat.
    root.addEventListener('click', () => {
      if (done) return;
      timers.forEach(clearTimeout);
      renderFrame(frames[frames.length - 1]);
      const t = setTimeout(finish, prefersReduced ? 0 : FINAL_MS);
      timers.push(t);
    });

    step();
  });
}
