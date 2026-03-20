/**
 * Shared scouting report functionality for both Franchise and Tournament modes.
 * Provides rendering functions for team attributes and play usage data.
 */

/** Core 12 display columns (matches BackEnd roster_builder ATTR_KEYS order for ST/AG). */
const SCOUTING_PROJECTED_ATTR_COLS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

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
 */
function renderProjectedStartingFive(rows) {
  const el = document.getElementById('scouting-projected-lineup');
  if (!el) return;
  el.innerHTML = '';
  if (!rows || rows.length === 0) {
    el.innerHTML =
      '<p class="scouting-projected-empty">No projected lineup (missing position ratings or roster data).</p>';
    return;
  }

  const table = document.createElement('table');
  table.className = 'scouting-projected-table';
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
      r.year != null && r.year !== '' ? String(r.year) : '—',
      scoutingFormatHeight(r.height),
      r.weight != null && r.weight !== '' ? String(r.weight) : '—',
    ];
    SCOUTING_PROJECTED_ATTR_COLS.forEach((k) => {
      const av = r.attributes && r.attributes[k] != null ? r.attributes[k] : '—';
      cells.push(String(av));
    });
    cells.push(r.rt != null ? String(r.rt) : '—');
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

/**
 * Render team attributes in the scouting report grid.
 * @param {Object} teamAttrs - Team attributes object
 * @param {Function} createTeamAttrItem - Function to create team attribute items (must be provided by caller)
 */
function renderScoutingTeamReport(teamAttrs, createTeamAttrItem) {
  const grid = document.getElementById('scouting-team-attributes-grid');
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
 * @param {Array} plays - Array of play objects with name, times_run, successes, total_playcalls
 * @param {string} emptyMessage - Message to display when no plays are available (optional)
 */
function renderPlayUsage(plays, emptyMessage = 'No previous game data available. Opponent has not played a game yet.') {
  const tbody = document.getElementById('play-usage-body');
  if (!tbody) return;
  
  tbody.innerHTML = '';
  
  if (!plays || plays.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; padding: 20px; color: #666;">${emptyMessage}</td></tr>`;
    return;
  }
  
  // Calculate total playcalls for usage %
  const totalPlaycalls = plays.reduce((sum, p) => sum + (p.times_run || 0), 0);
  
  // Sort by times_run descending
  plays.sort((a, b) => (b.times_run || 0) - (a.times_run || 0));
  
  plays.forEach(play => {
    const timesRun = play.times_run || 0;
    const successes = play.successes || 0;
    const successRate = timesRun > 0 ? ((successes / timesRun) * 100).toFixed(1) : '0.0';
    const usagePct = totalPlaycalls > 0 ? ((timesRun / totalPlaycalls) * 100).toFixed(1) : '0.0';
    
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${play.name || 'Unknown'}</td>
      <td>${timesRun}</td>
      <td>${successRate}%</td>
      <td>${usagePct}%</td>
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
}

