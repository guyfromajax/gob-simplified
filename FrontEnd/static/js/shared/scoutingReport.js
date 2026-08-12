/**
 * Shared scouting report functionality for both Franchise and Tournament modes.
 * Provides rendering functions for team attributes and play usage data.
 */

/** Core 12 display columns (matches BackEnd roster_builder ATTR_KEYS order for ST/AG). */
const SCOUTING_PROJECTED_ATTR_COLS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

/** Season stat columns for scouting modal Stats toggle (matches command center roster stats). */
const SCOUTING_PROJECTED_STATS_COLUMNS = [
  'PTS', 'FGM', 'FGA', 'FG%', '3PTM', '3PTA', '3PT%', 'FTM', 'FTA', 'FT%',
  'DREB', 'OREB', 'TREB', 'AST', 'STL', 'BLK', 'F', 'MIN', 'TO',
];

var scoutingProjectedRowsCache = [];
var scoutingPlayerSeasonStatsCache = {};
var scoutingProjectedViewMode = 'attributes';
var scoutingProjectedToggleWired = false;

function scoutingFormatHeight(raw) {
  if (typeof formatHeight === 'function') return formatHeight(raw);
  const inches = parseInt(raw, 10);
  if (Number.isNaN(inches)) return raw == null || raw === '' ? '--' : String(raw);
  const ft = Math.floor(inches / 12);
  const inch = inches % 12;
  return `${ft}'${inch}"`;
}

/**
 * Render projected starting five (from API `projected_starting_five` array).
 * @param {Array<{position:string,name:string,jersey:number,year:string,height:number,weight:number,rt:number,attributes:Object}>} rows
 * @param {string|{containerId?:string,tableClass?:string,emptyClass?:string}} [containerOrOpts] - optional container id or options (default: scouting modal)
 */
function renderProjectedStartingFive(rows, containerOrOpts) {
  let containerId = 'scouting-projected-lineup';
  let tableClass = 'scouting-projected-table';
  let emptyClass = 'scouting-projected-empty';
  if (typeof containerOrOpts === 'string') {
    containerId = containerOrOpts;
  } else if (containerOrOpts && typeof containerOrOpts === 'object') {
    if (containerOrOpts.containerId) containerId = containerOrOpts.containerId;
    if (containerOrOpts.tableClass) tableClass = containerOrOpts.tableClass;
    if (containerOrOpts.emptyClass) emptyClass = containerOrOpts.emptyClass;
  }
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  if (!rows || rows.length === 0) {
    el.innerHTML =
      '<p class="' + emptyClass + '">No projected lineup (missing position ratings or roster data).</p>';
    return;
  }

  const table = document.createElement('table');
  table.className = tableClass;
  const thead = document.createElement('thead');
  const hrow = document.createElement('tr');
  const headers = ['Pos', 'Player', 'Year', 'Ht', 'Wt'].concat(SCOUTING_PROJECTED_ATTR_COLS).concat(['RT']);
  headers.forEach((h) => {
    const th = document.createElement('th');
    th.textContent = h;
    hrow.appendChild(th);
  });
  thead.appendChild(hrow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  rows.forEach((r) => {
    const tr = document.createElement('tr');
    const playerLabel =
      typeof formatNameWithJersey === 'function'
        ? formatNameWithJersey(r.jersey, r.name || '')
        : r.name || '—';
    const cells = [
      r.position || '—',
      playerLabel,
      (typeof GOB_PlayerYear !== 'undefined'
        ? GOB_PlayerYear.formatDisplay(r.year)
        : (typeof yearMap !== 'undefined' && r.year
          ? (yearMap[String(r.year).toLowerCase()] || String(r.year).toUpperCase())
          : (r.year != null && r.year !== '' ? String(r.year) : '—'))),
      scoutingFormatHeight(r.height),
      r.weight != null && r.weight !== '' ? String(r.weight) : '—',
    ];
    SCOUTING_PROJECTED_ATTR_COLS.forEach((k) => {
      const raw = r.attributes && r.attributes[k] != null ? Number(r.attributes[k]) : NaN;
      // Display scale 0–10 (team-page parity): floor(raw / 10).
      cells.push(Number.isFinite(raw) ? String(Math.floor(raw / 10)) : '—');
    });
    cells.push(typeof formatRtDisplay === 'function' ? formatRtDisplay(r.rt) : (r.rt != null ? String(r.rt) : '—'));
    cells.forEach((text) => {
      const td = document.createElement('td');
      td.textContent = text;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  el.appendChild(table);
}

function scoutingEscapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function scoutingFormatYearLabel(year) {
  if (typeof GOB_PlayerYear !== 'undefined') return GOB_PlayerYear.formatDisplay(year);
  if (typeof yearMap !== 'undefined' && year) {
    return yearMap[String(year).toLowerCase()] || String(year).toUpperCase();
  }
  return year != null && year !== '' ? String(year) : '—';
}

function scoutingFormatOneDecimal(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(1) : '0.0';
}

function scoutingFormatWholeDefPct(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '0%';
  return `${Math.round(n)}%`;
}

/**
 * Shared projected-five image cards (FCC Scouting + team roster Starting 5).
 * Expects rows enriched with ppg/rpg/apg/def_pct from the server.
 * @param {Array} rows
 * @param {{containerId?: string, emptyClass?: string}} [opts]
 */
function renderProjectedStartingFiveCards(rows, opts) {
  const containerId = (opts && opts.containerId) || 'fcc-scouting-projected-lineup';
  const emptyClass = (opts && opts.emptyClass) || 'scouting-projected-empty';
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  if (!rows || rows.length === 0) {
    el.innerHTML =
      '<p class="' + emptyClass + '">No projected lineup (missing position ratings or roster data).</p>';
    return;
  }

  const genericUrl =
    window.API_CONFIG && typeof window.API_CONFIG.getGenericHeadshotUrl === 'function'
      ? window.API_CONFIG.getGenericHeadshotUrl({ size: 'card' })
      : '/static/images/players/generic_headshot.png';

  const row = document.createElement('div');
  row.className = 'p5-row';
  rows.forEach((r) => {
    const pid = r.player_id != null ? String(r.player_id) : '';
    const imageId = r.image_id != null ? String(r.image_id) : '';
    const isRecruitPortrait = r.portrait_source === 'recruit' && imageId;
    const name = r.name || '—';
    const imgSrc =
      isRecruitPortrait && window.API_CONFIG && typeof window.API_CONFIG.getRecruitImageUrl === 'function'
        ? window.API_CONFIG.getRecruitImageUrl(imageId, { size: 'card' })
        : pid && window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function'
          ? window.API_CONFIG.getPlayerImageUrl(pid, { size: 'card' })
        : genericUrl;
    // Starting-five cards show the CURRENT rating only; the current/potential pair
    // stays in the attribute grid (roster + scouting tables).
    const rt = typeof formatRtDisplay === 'function'
      ? formatRtDisplay(r.rt)
      : (r.rt != null ? r.rt : '—');
    const rtClass =
      typeof getRtBucketClass === 'function' ? getRtBucketClass(r.rt) : 'rt-unknown';
    const jersey =
      r.jersey != null && r.jersey !== '' ? `#${r.jersey}` : '#—';
    const bio = [
      scoutingFormatYearLabel(r.year),
      scoutingFormatHeight(r.height),
      r.weight != null && r.weight !== '' ? `${r.weight} lb` : '—',
    ].join(' · ');

    const article = document.createElement('article');
    article.className = 'p5-card';
    article.innerHTML = `
      <div class="p5-photo">
        <span class="p5-pos">${scoutingEscapeHtml(r.position || '—')}</span>
        <span class="p5-rt-badge ${scoutingEscapeHtml(rtClass)}">${scoutingEscapeHtml(rt)}</span>
        <img loading="lazy" width="240" height="240" src="${scoutingEscapeHtml(imgSrc)}" alt="${scoutingEscapeHtml(name)}">
      </div>
      <div class="p5-body">
        <div class="p5-namerow">
          <div class="p5-ident">
            <div class="p5-name">${scoutingEscapeHtml(name)}</div>
            <div class="p5-bio">${scoutingEscapeHtml(bio)}</div>
          </div>
          <span class="p5-jersey">${scoutingEscapeHtml(jersey)}</span>
        </div>
        <div class="p5-stats">
          <div class="p5-stat"><span class="sv">${scoutingEscapeHtml(scoutingFormatOneDecimal(r.ppg))}</span><span class="sl">PPG</span></div>
          <div class="p5-stat"><span class="sv">${scoutingEscapeHtml(scoutingFormatOneDecimal(r.rpg))}</span><span class="sl">RPG</span></div>
          <div class="p5-stat"><span class="sv">${scoutingEscapeHtml(scoutingFormatOneDecimal(r.apg))}</span><span class="sl">APG</span></div>
          <div class="p5-stat"><span class="sv">${scoutingEscapeHtml(scoutingFormatWholeDefPct(r.def_pct))}</span><span class="sl">DEF</span></div>
        </div>
      </div>
    `;
    const img = article.querySelector('img');
    if (img) {
      img.addEventListener('error', function onImgError() {
        img.removeEventListener('error', onImgError);
        const api = window.API_CONFIG;
        const ensure =
          isRecruitPortrait && typeof api?.ensureRecruitImage === 'function'
            ? api.ensureRecruitImage(imageId)
            : r.portrait_source === 'player' && imageId && pid && typeof api?.ensurePlayerImage === 'function'
              ? api.ensurePlayerImage(api.currentFranchiseId?.(), pid)
              : Promise.resolve({ status: 'skip' });
        Promise.resolve(ensure).then(() => {
          img.addEventListener('error', function onRetryError() {
            img.removeEventListener('error', onRetryError);
            img.src = genericUrl;
          });
          const retryUrl =
            isRecruitPortrait && typeof api?.getRecruitImageUrl === 'function'
              ? api.getRecruitImageUrl(imageId, { size: 'card' })
              : pid && typeof api?.getPlayerImageUrl === 'function'
                ? api.getPlayerImageUrl(pid, { size: 'card' })
                : genericUrl;
          img.src = `${retryUrl}${retryUrl.includes('?') ? '&' : '?'}r=1`;
        });
      });
    }
    row.appendChild(article);
  });
  el.appendChild(row);
  if (typeof window.initAttributeTooltips === 'function') {
    window.initAttributeTooltips(el, ['[data-tooltip]']);
  }
}

/** @deprecated Alias — prefer renderProjectedStartingFiveCards */
function renderFccProjectedStartingFiveCards(rows, opts) {
  return renderProjectedStartingFiveCards(rows, opts);
}

function formatScoutingSeasonStat(stats, col) {
  const s = stats || {};
  const num = (x) => {
    const n = Number(x);
    return Number.isFinite(n) ? n : 0;
  };
  switch (col) {
    case 'FG%': {
      const fga = num(s.FGA);
      const fgm = num(s.FGM);
      return fga > 0 ? ((fgm / fga) * 100).toFixed(1) : '0.0';
    }
    case '3PT%': {
      const tpa = num(s['3PTA'] != null ? s['3PTA'] : s.TPA);
      const tpm = num(s['3PTM'] != null ? s['3PTM'] : s.TPM);
      return tpa > 0 ? ((tpm / tpa) * 100).toFixed(1) : '0.0';
    }
    case 'FT%': {
      const fta = num(s.FTA);
      const ftm = num(s.FTM);
      return fta > 0 ? ((ftm / fta) * 100).toFixed(1) : '0.0';
    }
    case 'TREB': {
      if (s.TREB != null && s.TREB !== '') return String(s.TREB);
      return String(num(s.OREB) + num(s.DREB));
    }
    default: {
      const v = s[col];
      if (v == null || v === '') return '0';
      return String(v);
    }
  }
}

/**
 * Stats view for projected starting five (scouting modal).
 * @param {string} containerId
 * @param {Array} rows - projected_starting_five from API
 * @param {Object<string, Object>} statsByPlayerId - player_season_stats from API
 */
function renderProjectedStartingFiveStatsInto(containerId, rows, statsByPlayerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = '';
  const map = statsByPlayerId && typeof statsByPlayerId === 'object' ? statsByPlayerId : {};
  if (!rows || rows.length === 0) {
    el.innerHTML =
      '<p class="scouting-projected-empty">No projected lineup (missing position ratings or roster data).</p>';
    return;
  }
  const table = document.createElement('table');
  table.className = 'scouting-projected-table';
  const thead = document.createElement('thead');
  const hrow = document.createElement('tr');
  const headers = ['Pos', 'Player'].concat(SCOUTING_PROJECTED_STATS_COLUMNS);
  headers.forEach((h) => {
    const th = document.createElement('th');
    th.textContent = h;
    hrow.appendChild(th);
  });
  thead.appendChild(hrow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  rows.forEach((r) => {
    const tr = document.createElement('tr');
    const pid = r.player_id != null ? String(r.player_id) : '';
    const stats = map[pid] || {};
    const playerLabel =
      typeof formatNameWithJersey === 'function'
        ? formatNameWithJersey(r.jersey, r.name || '')
        : r.name || '—';
    const cells = [r.position || '—', playerLabel];
    SCOUTING_PROJECTED_STATS_COLUMNS.forEach((col) => {
      cells.push(formatScoutingSeasonStat(stats, col));
    });
    cells.forEach((text) => {
      const td = document.createElement('td');
      td.textContent = text;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  el.appendChild(table);
}

function renderScoutingProjectedLineupTable() {
  if (scoutingProjectedViewMode === 'stats') {
    renderProjectedStartingFiveStatsInto(
      'scouting-projected-lineup',
      scoutingProjectedRowsCache,
      scoutingPlayerSeasonStatsCache
    );
    return;
  }
  renderProjectedStartingFive(scoutingProjectedRowsCache, {
    containerId: 'scouting-projected-lineup',
    tableClass: 'scouting-projected-table',
    emptyClass: 'scouting-projected-empty',
  });
}

/**
 * Cache scouting projected rows + season stats and render (Attributes view by default).
 * Call after fetching /franchise/scouting-report or /tournament/scouting-report.
 * @param {Array} rows
 * @param {Object<string, Object>} [playerSeasonStats]
 */
function setScoutingProjectedLineupData(rows, playerSeasonStats) {
  scoutingProjectedRowsCache = rows || [];
  scoutingPlayerSeasonStatsCache =
    playerSeasonStats && typeof playerSeasonStats === 'object' ? playerSeasonStats : {};
  scoutingProjectedViewMode = 'attributes';
  const wrap = document.querySelector('.scouting-projected-toggle');
  if (wrap) {
    wrap.querySelectorAll('.toggle-btn').forEach((b) => {
      const v = b.getAttribute('data-scouting-projected');
      if (v === 'attributes') b.classList.add('active');
      else b.classList.remove('active');
    });
  }
  ensureScoutingProjectedToggleWired();
  renderScoutingProjectedLineupTable();
}

function ensureScoutingProjectedToggleWired() {
  if (scoutingProjectedToggleWired) return;
  const wrap = document.querySelector('.scouting-projected-toggle');
  if (!wrap) return;
  scoutingProjectedToggleWired = true;
  wrap.querySelectorAll('.toggle-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      scoutingProjectedViewMode = btn.getAttribute('data-scouting-projected') || 'attributes';
      wrap.querySelectorAll('.toggle-btn').forEach((b) => {
        b.classList.toggle('active', b === btn);
      });
      renderScoutingProjectedLineupTable();
    });
  });
}

/**
 * Render team attributes in the scouting report grid.
 * @param {Object} teamAttrs - Team attributes object
 * @param {Function} createTeamAttrItem - Function to create team attribute items (must be provided by caller)
 */
function renderScoutingTeamReport(teamAttrs, createTeamAttrItem, gridId) {
  const grid = document.getElementById(gridId || 'scouting-team-attributes-grid');
  if (!grid) return;
  
  if (typeof createTeamAttrItem !== 'function') {
    console.error('renderScoutingTeamReport: createTeamAttrItem function is required');
    return;
  }
  
  grid.innerHTML = '';
  
  const attrOrder = [
    'shot_threshold',
    'rebound_modifier',
    'offensive_efficiency',
    'defensive_efficiency',
    'fb_efficiency',
    'pt_efficiency',
    'fight',
    'discipline',
    'momentum_score',
    'team_chemistry',
    'fb_opp_modifier',
    'pt_opp_modifier'
  ];
  
  attrOrder.forEach(attrKey => {
    const item = createTeamAttrItem(attrKey, teamAttrs[attrKey], 0);
    if (item) grid.appendChild(item);
  });
}

/**
 * Render play usage data in the scouting report table.
 * @param {Array} plays - Array of play objects with name, times_run, successes, total_playcalls; optional topScorer for box score
 * @param {string} emptyMessage - Message to display when no plays are available (optional)
 * @param {string} tbodyId - tbody element id
 * @param {{ showTopScorer?: boolean }} [options] - When showTopScorer, expects each play.topScorer (string) for the Top Scorer column
 */
function renderPlayUsage(plays, emptyMessage = 'No previous game data available. Opponent has not played a game yet.', tbodyId = 'play-usage-body', options = {}) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;

  const showTopScorer = Boolean(options && options.showTopScorer);
  const colspan = showTopScorer ? 5 : 4;

  tbody.innerHTML = '';

  if (!plays || plays.length === 0) {
    tbody.innerHTML = `<tr><td colspan="${colspan}" style="text-align: center; padding: 20px; color: #666;">${emptyMessage}</td></tr>`;
    return;
  }

  // Calculate total playcalls for usage %
  const totalPlaycalls = plays.reduce((sum, p) => sum + (p.times_run || 0), 0);

  // Sort by times_run descending
  plays.sort((a, b) => (b.times_run || 0) - (a.times_run || 0));

  plays.forEach((play) => {
    const timesRun = play.times_run || 0;
    const successes = play.successes || 0;
    const successRate = timesRun > 0 ? ((successes / timesRun) * 100).toFixed(1) : '0.0';
    const usagePct = totalPlaycalls > 0 ? ((timesRun / totalPlaycalls) * 100).toFixed(1) : '0.0';
    const topCell = showTopScorer
      ? `<td>${play.topScorer != null && play.topScorer !== '' ? String(play.topScorer) : '—'}</td>`
      : '';

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${play.name || 'Unknown'}</td>
      <td>${timesRun}</td>
      <td>${successRate}%</td>
      <td>${usagePct}%</td>
      ${topCell}
    `;
    tbody.appendChild(tr);
  });
}

/**
 * Setup scouting report button and modal event handlers.
 * Call this function after DOM is ready to initialize click handlers.
 */
function setupScoutingReport(loadScoutingReportCallback) {
  const scoutingBtn = document.getElementById('scouting-report-btn');
  const modal = document.getElementById('scouting-report-modal');
  const closeBtn = document.querySelector('.scouting-modal-close');
  
  if (scoutingBtn && typeof loadScoutingReportCallback === 'function') {
    scoutingBtn.addEventListener('click', loadScoutingReportCallback);
  }
  
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      try {
        var a = new Audio('/sounds/' + encodeURIComponent('x-back.mp3'));
        a.volume = 0.7;
        a.play().catch(function () {});
      } catch (e) {}
      if (modal) modal.style.display = 'none';
    });
  }
  
  // Close modal when clicking outside
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.style.display = 'none';
      }
    });
  }

  ensureScoutingProjectedToggleWired();
}
