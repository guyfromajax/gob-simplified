const reportParams = new URLSearchParams(window.location.search);

const reportState = {
  mode: reportParams.get('mode') || 'single',
  teamId: reportParams.get('team_id') || reportParams.get('user_team_id') || '',
  franchiseId: reportParams.get('franchise_id') || '',
  tournamentId: reportParams.get('tournament_id') || '',
  gameId: reportParams.get('game_id') || '',
  homeTeam: reportParams.get('home') || '',
  awayTeam: reportParams.get('away') || '',
  myTeamSide: reportParams.get('my_team') || '',
  returnUrl: getSafeReturnUrl(reportParams.get('return_url')),
};

function reportFetchJson(url) {
  return fetch(url, { headers: API_CONFIG.getAuthHeaders() })
    .then((response) => {
      if (typeof AccessDenied !== 'undefined' && AccessDenied.checkAccessDenied) {
        if (AccessDenied.checkAccessDenied(response)) return null;
      }
      if (!response.ok) throw new Error(`Request failed: ${response.status}`);
      return response.json();
    })
    .catch((error) => {
      console.error('[PLAYBOOK REPORT] Request failed:', url, error);
      return null;
    });
}

function reportPostJson(url, body) {
  return fetch(url, {
    method: 'POST',
    headers: {
      ...API_CONFIG.getAuthHeaders(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body || {}),
  })
    .then((response) => {
      if (typeof AccessDenied !== 'undefined' && AccessDenied.checkAccessDenied) {
        if (AccessDenied.checkAccessDenied(response)) return null;
      }
      if (!response.ok) throw new Error(`Request failed: ${response.status}`);
      return response.json();
    })
    .catch((error) => {
      console.error('[PLAYBOOK REPORT] Request failed:', url, error);
      return null;
    });
}

function formatPct(rawValue) {
  const numericValue = Number(rawValue || 0);
  return `${Math.round(numericValue)}%`;
}

function ensureArray(value) {
  return Array.isArray(value) ? value : [];
}

function buildRow(label, value, options = {}) {
  const row = document.createElement('div');
  row.className = 'report-row';
  if (options.highlight) row.classList.add('is-highlight');

  const main = document.createElement('div');
  main.className = 'report-row-main';

  const labelEl = document.createElement('span');
  labelEl.className = 'report-row-label';
  labelEl.textContent = label;
  main.appendChild(labelEl);

  const valueEl = document.createElement('span');
  valueEl.className = 'report-row-value';
  valueEl.textContent = value;
  main.appendChild(valueEl);

  row.appendChild(main);

  if (options.meta) {
    const meta = document.createElement('div');
    meta.className = 'report-row-meta';
    meta.textContent = options.meta;
    row.appendChild(meta);
  }

  return row;
}

function buildOrderedRow(index, label, meta, options = {}) {
  const row = document.createElement('div');
  row.className = 'report-row';
  if (options.highlight) row.classList.add('is-highlight');

  const order = document.createElement('span');
  order.className = 'report-order-num';
  order.textContent = String(index + 1);
  row.appendChild(order);

  const content = document.createElement('div');
  content.className = 'report-row-content';

  const labelEl = document.createElement('div');
  labelEl.className = 'report-row-label';
  labelEl.textContent = label;
  content.appendChild(labelEl);

  if (meta) {
    const metaEl = document.createElement('div');
    metaEl.className = 'report-row-meta';
    metaEl.textContent = meta;
    content.appendChild(metaEl);
  }

  row.appendChild(content);
  return row;
}

function renderList(containerId, rows) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  if (!rows.length) {
    const empty = document.createElement('div');
    empty.className = 'report-empty';
    empty.textContent = 'No saved settings yet.';
    container.appendChild(empty);
    return;
  }

  rows.forEach((row) => container.appendChild(row));
}

function getPlaybookUrl() {
  const params = new URLSearchParams();
  params.set('mode', reportState.mode);
  if (reportState.teamId) params.set('team_id', reportState.teamId);
  if (reportState.franchiseId) params.set('franchise_id', reportState.franchiseId);
  if (reportState.tournamentId) params.set('tournament_id', reportState.tournamentId);
  if (reportState.gameId) params.set('game_id', reportState.gameId);
  return `${API_CONFIG.buildUrl('/api/playbooks')}?${params.toString()}`;
}

function buildOffenseRows(data) {
  const percentages = data.simple_playbook_percentages || {};
  const offensePcIds = new Set(ensureArray((data.pc_order || {}).offense).map(String));

  const motionRows = ensureArray(data.motion)
    .map((play) => ({
      label: play.name,
      value: Number((percentages.motion || {})[String(play.play_id)] || 0),
      highlight: offensePcIds.has(String(play.play_id)),
    }))
    .filter((play) => play.value > 0 || play.highlight)
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
    .map((play) => buildRow(play.label, formatPct(play.value), { highlight: play.highlight }));

  const setRows = ensureArray(data.set_plays)
    .map((play) => ({
      label: play.name,
      value: Number((percentages.set_plays || {})[String(play.play_id)] || 0),
      highlight: offensePcIds.has(String(play.play_id)),
    }))
    .filter((play) => play.value > 0 || play.highlight)
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
    .map((play) => buildRow(play.label, formatPct(play.value), { highlight: play.highlight }));

  renderList('offense-motion-list', motionRows);
  renderList('offense-set-list', setRows);
}

function buildDefenseRows(data) {
  const percentages = data.simple_playbook_percentages || {};
  const defensePcIds = new Set(ensureArray((data.pc_order || {}).defense).map(String));

  const manRows = ensureArray(data.man_defense_rows)
    .map((defense) => {
      const value = Number((percentages.man_defense || {})[defense.id] || 0);
      return {
        label: defense.name,
        value,
        highlight: defensePcIds.has(String(defense.id)),
      };
    })
    .filter((defense) => defense.value > 0 || defense.highlight)
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
    .map((defense) => buildRow(defense.label, formatPct(defense.value), { highlight: defense.highlight }));

  const zoneRows = ensureArray(data.zone_defense_rows)
    .map((defense) => {
      const value = Number((percentages.zone_defense || {})[defense.id] || 0);
      return {
        label: defense.name,
        value,
        highlight: defensePcIds.has(String(defense.id)),
      };
    })
    .filter((defense) => defense.value > 0 || defense.highlight)
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
    .map((defense) => buildRow(defense.label, formatPct(defense.value), { highlight: defense.highlight }));

  renderList('defense-man-list', manRows);
  renderList('defense-zone-list', zoneRows);
}

function buildFastBreakRows(data) {
  const percentages = ((data || {}).simple_playbook_percentages || {}).fast_breaks || {};
  const rows = ensureArray(data.fast_breaks)
    .map((item) => ({
      label: item.name,
      value: Number(percentages[item.id] || 0),
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label))
    .map((item) => buildRow(item.label, formatPct(item.value)));

  renderList('fast-break-list', rows);
}

function buildPlayMap(data) {
  const byId = new Map();
  ensureArray(data.motion).forEach((play) => byId.set(String(play.play_id), { ...play, category: 'motion' }));
  ensureArray(data.set_plays).forEach((play) => byId.set(String(play.play_id), { ...play, category: 'set_play' }));
  return byId;
}

function buildPcMeta(play) {
  if (!play) return '';
  if (play.category === 'motion') {
    return `Focus: ${play.motion_focus || 'None'}`;
  }
  if (play.category === 'set_play') {
    return `Target Shooter: ${play.target_shooter || 'None'}`;
  }
  return '';
}

function buildPcRows(data) {
  const playMap = buildPlayMap(data);
  const defenseNameMap = new Map();
  ensureArray(data.man_defense_rows).forEach((item) => defenseNameMap.set(String(item.id), item.name));
  ensureArray(data.zone_defense_rows).forEach((item) => defenseNameMap.set(String(item.id), item.name));

  const offenseRows = ensureArray((data.pc_order || {}).offense)
    .map((playId, index) => {
      const play = playMap.get(String(playId));
      if (!play) return null;
      return buildOrderedRow(index, play.name, buildPcMeta(play), { highlight: true });
    })
    .filter(Boolean);

  const defenseRows = ensureArray((data.pc_order || {}).defense)
    .map((defenseId, index) => {
      const defenseName = defenseNameMap.get(String(defenseId)) || String(defenseId);
      return buildOrderedRow(index, defenseName, null, { highlight: true });
    });

  renderList('pc-offense-list', offenseRows);
  renderList('pc-defense-list', defenseRows);
}

function getGameplayOpponentName() {
  if (!reportState.homeTeam || !reportState.awayTeam) return null;
  if (reportState.myTeamSide === 'home') return formatTeamName(reportState.awayTeam);
  if (reportState.myTeamSide === 'away') return formatTeamName(reportState.homeTeam);
  return null;
}

async function resolveOpponentName() {
  const gameplayOpponent = getGameplayOpponentName();
  if (gameplayOpponent) return gameplayOpponent;

  if (reportState.mode === 'franchise' && reportState.franchiseId) {
    const data = await reportPostJson(API_CONFIG.buildUrl('/franchise/play-next-game'), {
      franchise_id: reportState.franchiseId,
    });
    if (data) {
      const myTeamName = formatTeamName(localStorage.getItem('franchise_user_team') || '');
      const myTeamId = reportState.teamId;
      const home = formatTeamName(data.home || '');
      const away = formatTeamName(data.away || '');
      if (myTeamId && data.home_id && String(data.home_id) === String(myTeamId)) return away;
      if (myTeamId && data.away_id && String(data.away_id) === String(myTeamId)) return home;
      if (myTeamName && home === myTeamName) return away;
      if (myTeamName && away === myTeamName) return home;
      return away || home || 'Opponent';
    }
  }

  return 'Opponent';
}

function configureButtons() {
  const backBtn = document.getElementById('back-btn');
  const editBtn = document.getElementById('edit-btn');

  backBtn?.addEventListener('click', () => {
    const fallback = reportState.mode === 'franchise'
      ? resolveFranchiseLockerRoomUrl({
          franchiseId: reportState.franchiseId,
          teamId: reportState.teamId,
        })
      : '/mode-select.html';
    window.location.href = reportState.returnUrl || fallback;
  });

  if (!editBtn) return;
  if (reportState.gameId) {
    editBtn.style.display = 'none';
    return;
  }

  editBtn.addEventListener('click', () => {
    const params = new URLSearchParams();
    params.set('mode', reportState.mode);
    if (reportState.teamId) params.set('team_id', reportState.teamId);
    if (reportState.franchiseId) params.set('franchise_id', reportState.franchiseId);
    if (reportState.tournamentId) params.set('tournament_id', reportState.tournamentId);
    params.set('return_url', getCurrentRelativeUrl());
    window.location.href = `/playbooks.html?${params.toString()}`;
  });
}

async function initPlaybookReport() {
  configureButtons();

  const opponentName = await resolveOpponentName();
  const subhead = document.getElementById('report-subhead');
  if (subhead) subhead.textContent = `vs ${opponentName}`;

  const data = await reportFetchJson(getPlaybookUrl());
  if (!data) return;

  buildOffenseRows(data);
  buildDefenseRows(data);
  buildFastBreakRows(data);
  buildPcRows(data);
}

window.addEventListener('DOMContentLoaded', initPlaybookReport);
