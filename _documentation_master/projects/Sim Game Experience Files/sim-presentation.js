/* GOB — Sim Game Presentation overlay. Data-driven renderer for all states. */
(function () {
  const GREEN = '#34EC27', BLUE = '#4A90D9', ORANGE = '#F79420', RED = '#ff6d6d', YELLOW = '#FFD700';
  const POSC = { PG:'#4A90D9', SG:'#7B5EA7', SF:'#3A8C4A', PF:'#C0392B', C:'#D4A017' };
  // Canonical ROSTER PLAYER RT bands (rtBucket.js / rt-buckets.css / Attribute Bar Scale).
  // 81+ blue · 61-80 green · 41-60 yellow · 0-40 red. NOT the recruit JH scale.
  const RTC = rt => rt >= 81 ? BLUE : rt >= 61 ? GREEN : rt >= 41 ? YELLOW : RED;
  const SIL = `<svg viewBox="0 0 100 100"><circle cx="50" cy="34" r="19" fill="rgba(255,255,255,0.15)"/><path d="M12 100c0-22 17-36 38-36s38 14 38 36" fill="rgba(255,255,255,0.15)"/></svg>`;
  const FLAME = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c1 3-1 4.5-2.5 6.5C8 10.7 7 12.4 7 14.5 7 18 9.2 21 12 21s5-3 5-6.5c0-2.4-1.3-4-2.4-5.6.2 1.6-.4 2.7-1.3 3.3.5-2.6-.9-6.4-1.3-10.2z"/></svg>`;
  const SNOW = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M12 2v20M2 12h20M4.9 4.9l14.2 14.2M19.1 4.9L4.9 19.1M12 5.5l2 2M12 5.5l-2 2M12 18.5l2-2M12 18.5l-2-2M5.5 12l2 2M5.5 12l2-2M18.5 12l-2 2M18.5 12l-2-2"/></svg>`;

  const abbrev = n => n; // names supplied already short

  function statBar(label, v, max, pct, side) {
    const fill = Math.min(v / max, 1) * 100;
    const color = pct ? (v >= 80 ? BLUE : GREEN) : (v >= max ? BLUE : GREEN);
    const maxed = pct ? v >= 80 : v >= max;
    const val = pct ? v + '%' : v;
    const track = `<div class="track ${side}"><div class="fill${maxed ? ' maxed' : ''}" style="width:${fill}%;background:${color}"></div></div>`;
    const lab = `<span class="bl">${label}</span>`, value = `<span class="bv">${val}</span>`;
    return `<div class="barrow ${side}">${side === 'home' ? value + track + lab : lab + track + value}</div>`;
  }

  function foulPips(f, out) {
    let pips = '';
    for (let i = 0; i < 5; i++) {
      const on = i < f;
      const c = out ? RED : (f >= 4 ? YELLOW : 'rgba(255,255,255,0.7)');
      pips += `<span class="pip" style="background:${on ? c : 'rgba(255,255,255,0.14)'}"></span>`;
    }
    return `<span class="pips" title="${f} fouls">${pips}</span>`;
  }

  function playerRow(p, side, teamColor) {
    const pc = POSC[p.pos] || '#fff';
    const status = [];
    if (p.hot) status.push(`<span class="mo flame" style="color:${ORANGE}">${FLAME}</span>`);
    if (p.cold) status.push(`<span class="mo snow" style="color:${BLUE}">${SNOW}</span>`);
    if (p.out) status.push(`<span class="tag-out">FOULED OUT</span>`);
    else if (p.fouls >= 4) status.push(`<span class="tag-ft">FOUL TROUBLE</span>`);
    const statusHtml = `<span class="status">${status.join('')}${foulPips(p.fouls || 0, p.out)}</span>`;
    const rtb = p.rt == null ? '' : `<span class="rtb" style="background:${RTC(p.rt)}">${p.rt}</span>`;
    const head = `<div class="head" style="border-color:${p.out ? RED : teamColor}">${rtb}<div class="sil">${SIL}</div></div>`;
    const name = `<div class="pname">${p.spot ? `<span class="spotmark" style="color:${ORANGE}">◆ TOP</span>` : ''}<span class="nm">${abbrev(p.name)}</span><span class="jn">#${p.jersey}</span>${p.sub ? '<span class="tag-in">IN</span>' : ''}</div>`;
    const bars = `<div class="bars">${statBar('PTS', p.pts, 20, false, side)}${statBar('REB', p.reb, 10, false, side)}${statBar('AST', p.ast, 10, false, side)}${statBar('DEF', p.def, 100, true, side)}</div>`;
    const body = `<div class="pbody">${name}${statusHtml}${bars}</div>`;
    return `<div class="prow ${side}${p.spot ? ' spot' : ''}${p.out ? ' isout' : ''}" style="--tc:${teamColor}">${side === 'home' ? body + head : head + body}</div>`;
  }

  function benchRail(chips, side, teamColor) {
    if (!chips || !chips.length) return '';
    const items = chips.map(c => `<span class="bchip${c.out ? ' out' : ''}"><b>${c.name}</b>${c.out ? '<span class="bout">OUT</span>' : ''}<span class="bstat">${c.pts}p · ${c.reb}r</span></span>`).join('');
    return `<div class="bench ${side}"><span class="bench-lbl">BENCH</span>${items}</div>`;
  }

  function worm(margins, w, h, home, away) {
    const pad = 6, mid = h / 2, n = margins.length;
    const maxAbs = Math.max(6, ...margins.map(m => Math.abs(m)));
    const x = i => pad + (n <= 1 ? 0 : i * (w - pad * 2) / (n - 1));
    const y = m => mid - (m / maxAbs) * (mid - pad);
    let up = `M ${x(0)} ${mid}`, dn = `M ${x(0)} ${mid}`, line = '';
    margins.forEach((m, i) => { line += (i ? 'L' : 'M') + ` ${x(i).toFixed(1)} ${y(m).toFixed(1)} `; });
    // area split: build a top clip (home lead) and bottom clip (away lead)
    let area = `M ${x(0)} ${mid} `;
    margins.forEach((m, i) => { area += `L ${x(i).toFixed(1)} ${y(m).toFixed(1)} `; });
    area += `L ${x(n - 1)} ${mid} Z`;
    const cur = margins[n - 1];
    const cx = x(n - 1), cy = y(cur);
    return `<svg class="wormsvg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <defs>
        <linearGradient id="wg-up" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${home}" stop-opacity="0.42"/><stop offset="1" stop-color="${home}" stop-opacity="0"/></linearGradient>
        <linearGradient id="wg-dn" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="${away}" stop-opacity="0.42"/><stop offset="1" stop-color="${away}" stop-opacity="0"/></linearGradient>
        <clipPath id="clip-up"><rect x="0" y="0" width="${w}" height="${mid}"/></clipPath>
        <clipPath id="clip-dn"><rect x="0" y="${mid}" width="${w}" height="${mid}"/></clipPath>
      </defs>
      <line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="rgba(255,255,255,0.16)" stroke-width="1" stroke-dasharray="3 4"/>
      <path d="${area}" fill="url(#wg-up)" clip-path="url(#clip-up)"/>
      <path d="${area}" fill="url(#wg-dn)" clip-path="url(#clip-dn)"/>
      <path d="${line}" fill="none" stroke="${cur >= 0 ? home : away}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#clip-up)"/>
      <path d="${line}" fill="none" stroke="${away}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#clip-dn)"/>
      <circle class="wormdot" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.4" fill="${cur >= 0 ? home : away}"/>
    </svg>`;
  }

  function scoreboard(s, T) {
    const q = s.clock === 'FINAL' ? '' : s.quarter;
    return `<div class="sb">
      <div class="sb-side left">
        <div class="sb-logo" style="background:linear-gradient(135deg,${T.away.color},#0b0d14)">${T.away.abbr}</div>
        <div class="sb-meta"><span class="sb-rank">#${T.away.rank}</span><span class="sb-rec">${T.away.rec}</span></div>
        <div class="sb-score">${s.away}</div>
        <div class="sb-tf"><span>TOL ${s.atol}</span><span>F ${s.afoul}</span></div>
      </div>
      <div class="sb-center">
        <div class="sb-clock">${s.clock}</div>
        <div class="sb-per"><span class="sb-q">${q}</span>${s.clock === 'FINAL' ? '' : `<span class="sb-shot">${s.shot}</span>`}</div>
      </div>
      <div class="sb-side right">
        <div class="sb-tf right"><span>TOL ${s.htol}</span><span>F ${s.hfoul}</span></div>
        <div class="sb-score">${s.home}</div>
        <div class="sb-meta right"><span class="sb-rank">#${T.home.rank}</span><span class="sb-rec">${T.home.rec}</span></div>
        <div class="sb-logo" style="background:linear-gradient(225deg,${T.home.color},#0b0d14)">${T.home.abbr}</div>
      </div>
      <div class="sb-edge" style="--al:${T.away.color};--hl:${T.home.color}"></div>
    </div>`;
  }

  function sidePanel(side) {
    const rows = Array.from({ length: 7 }, () => `<div class="gp-row"><span class="gp-a"></span><span class="gp-b"></span></div>`).join('');
    return `<div class="sidepanel ${side}"><div class="gp-head">${side === 'left' ? 'BOX SCORE' : 'GAME FLOW'}</div>${rows}<div class="gp-note">existing side panel · not redesigned</div></div>`;
  }

  function overlay(st, T) {
    const w = worm(st.worm, 1173, 66, T.home.color, T.away.color);
    const curMargin = st.worm[st.worm.length - 1];
    const leader = curMargin === 0 ? null : (curMargin > 0 ? T.home : T.away);
    const wormLabel = leader ? `<span class="wl-team" style="color:${leader.color}">${leader.abbr} +${Math.abs(curMargin)}</span>` : `<span class="wl-team" style="color:rgba(255,255,255,0.5)">TIED</span>`;

    const pairs = [0, 1, 2, 3, 4].map(i => {
      const a = st.away[i], h = st.home[i];
      const pos = a.pos;
      return `<div class="pair">
        ${playerRow(a, 'away', T.away.color)}
        <div class="poscol"><span class="posmark" style="color:${POSC[pos]}">${pos}</span></div>
        ${playerRow(h, 'home', T.home.color)}
      </div>`;
    }).join('');

    const benches = `<div class="bench-wrap">${benchRail(st.benchAway, 'away', T.away.color)}${benchRail(st.benchHome, 'home', T.home.color)}</div>`;

    let ticker = '';
    if (st.ticker) {
      const tagColor = { RUN: ORANGE, HEAT: '#ff7a3c', FOUL: RED, LEAD: BLUE, TIP: 'rgba(255,255,255,0.55)', FINAL: GREEN }[st.ticker.tag] || ORANGE;
      ticker = `<div class="ticker"><div class="tk-item"><span class="tk-tag" style="color:${tagColor};border-color:${tagColor}">${st.ticker.tag}</span><span class="tk-txt">${st.ticker.txt}</span></div></div>`;
    }

    let breakCard = '';
    if (st.phase === 'break') {
      breakCard = `<div class="breakcard"><div class="bc-eyebrow">QUARTER BREAK</div><div class="bc-title">END ${st.summaryQ}</div><div class="bc-score"><span style="color:${T.away.color}">${T.away.abbr} ${st.summaryAway}</span><span class="bc-dash">–</span><span style="color:${T.home.color}">${T.home.abbr} ${st.summaryHome}</span></div><div class="bc-note">${st.summaryNote}</div></div>`;
    }

    let finalStamp = '', popup = '';
    if (st.phase === 'final') {
      finalStamp = `<div class="finalstamp">FINAL</div>`;
      const winner = st.home_won ? T.home : T.away;
      popup = `<div class="popup"><div class="pu-badge">${st.home_won ? 'W' : 'L'}</div><div class="pu-banner" style="background:linear-gradient(120deg,${winner.color},#0b0d14)"></div><div class="pu-inner"><div class="pu-team">${winner.name.toUpperCase()} WIN</div><div class="pu-score">${T.away.abbr} ${st.summaryAway} <span class="bc-dash">–</span> ${T.home.abbr} ${st.summaryHome}</div><div class="pu-note">existing game-completion popup · overlay hands off here</div></div></div>`;
    }

    let eyebrow = '';
    if (st.phase === 'pretip') eyebrow = `<div class="pretip-lbl">STARTING LINEUPS · TIP-OFF</div>`;

    return `<div class="overlay ${st.phase === 'break' ? 'breaking' : ''}">
      <div class="ov-worm">
        <div class="wl-head"><span class="wl-cap">LEAD MARGIN</span>${wormLabel}</div>
        ${w}
        <div class="wl-axis"><span>TIP</span><span>Q1</span><span>Q2</span><span>HALF</span><span>Q3</span><span>Q4</span></div>
      </div>
      ${eyebrow}
      <div class="rows">${pairs}</div>
      ${benches}
      ${ticker}
      ${breakCard}
      ${finalStamp}
      ${popup}
    </div>`;
  }

  function frame(st, T, size) {
    const dim = size || { w: 1920, h: 1080 };
    return `<div class="screen" style="width:${dim.w}px;height:${dim.h}px">
      ${scoreboard(st.score, T)}
      <div class="stage-row">
        ${sidePanel('left')}
        <div class="ovhost">${overlay(st, T)}</div>
        ${sidePanel('right')}
      </div>
    </div>`;
  }

  window.SimPres = { frame, overlay, scoreboard };
})();
