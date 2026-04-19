// Training Report Page JavaScript

function playSound(filename) {
  try {
    const base = (typeof window.API_CONFIG !== 'undefined' && window.API_CONFIG.buildStaticPath) ? window.API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
    const a = new Audio(base + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(() => {});
  } catch (e) {}
}

const urlParams = new URLSearchParams(window.location.search);
const mode = urlParams.get('mode');
const franchiseId = urlParams.get('franchise_id');
const tournamentId = urlParams.get('tournament_id');
const teamId = urlParams.get('team_id');
const week = parseInt(urlParams.get('week'), 10);
const round = parseInt(urlParams.get('round'), 10); // For tournament mode (optional - backend will determine if not provided)

let reportData = null;
let currentView = 'changes'; // 'attributes' or 'changes'
/** Projected Starting 5 sub-toggle: 'attributes' | 'stats' */
let projectedLineupView = 'attributes';

// Season stat columns (aligned with franchise command center roster stats table)
const TRAINING_PROJECTED_STATS_COLUMNS = [
  'PTS',
  'FGM',
  'FGA',
  'FG%',
  '3PTM',
  '3PTA',
  '3PT%',
  'FTM',
  'FTA',
  'FT%',
  'DREB',
  'OREB',
  'TREB',
  'AST',
  'STL',
  'BLK',
  'F',
  'MIN',
  'TO',
];

// Attribute abbreviations mapping
// NOTE: Order is critical - this is the exact order attributes should be displayed horizontally
// MO (Momentum) is excluded from Training Report display
const ATTRIBUTE_ORDER = [
  'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT', 'NG', 'EM'
];
const STATIC_COLUMNS = ['RT'];

const ATTRIBUTE_NAMES = {
  'SC': 'SC',
  'SH': 'SH',
  'ID': 'ID',
  'OD': 'OD',
  'PS': 'PS',
  'BH': 'BH',
  'RB': 'RB',
  'AG': 'AG',
  'ST': 'ST',
  'ND': 'ND',
  'IQ': 'IQ',
  'FT': 'FT',
  'NG': 'NG',
  'EM': 'EM',
  'MO': 'MO'
};

// Team attribute display names
const TEAM_ATTR_NAMES = {
  'shot_threshold': 'Shooting',
  'rebound_modifier': 'Rebounding',
  'offensive_efficiency': 'Offense',
  'defensive_efficiency': 'Defense',
  'fb_efficiency': 'Fast Breaks',
  'pt_efficiency': 'Press/Trap',
  'fight': 'Fight',
  'discipline': 'Discipline',
  'momentum_score': 'Momentum',
  'team_chemistry': 'Team Chemistry',
  'fb_opp_modifier': 'Fast Break Defense',
  'pt_opp_modifier': 'Press/Trap Breaks'
};

// Coaching focus display names
const FOCUS_DISPLAY = {
  'authoritarian': {
    'discipline': 'Authoritarian - Discipline',
    'rebounding': 'Authoritarian - Rebounding',
    'teamwork': 'Authoritarian - Teamwork',
    'execution': 'Authoritarian - Execution'
  },
  'systems-coach': {
    'offense': 'Systems Coach - Offense',
    'defense': 'Systems Coach - Defense',
    'fast-breaks': 'Systems Coach - Fast Breaks',
    'presses-traps': 'Systems Coach - Presses/Traps'
  },
  'player-maximizer': {
    'top-3': 'Player Maximizer - Top 3 Attributes',
    'attributes-4-6': 'Player Maximizer - Attributes 4-6',
    'positional-focus': 'Player Maximizer - Positional Focus',
    'custom': 'Player Maximizer - Custom',
    'choose-attributes': 'Player Maximizer - Choose Attributes'
  },
  'culture-builder': {
    'inspire': 'Culture Builder - Inspire',
    'community': 'Culture Builder - Community Engagement',
    'teamwork': 'Culture Builder - Team Building',
    'build-confidence': 'Culture Builder - Build Confidence'
  }
};

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
  // SS&S: For tournament mode, round is optional (backend will determine from state)
  // For franchise mode, week is required
  if (!mode || !teamId) {
    console.error('Missing required URL parameters: mode and team_id are required');
    return;
  }
  
  if (mode === 'franchise' && !week) {
    console.error('Missing required URL parameter: week is required for franchise mode');
    return;
  }
  
  // Tournament mode: round is optional - backend will determine from training_status

  // Set up view toggle
  setupViewToggle();

  setupProjectedLineupToggle();
  
  // Set up locker room button
  setupLockerRoomButton();
  
  // Load training report data
  loadTrainingReport();
});

function setupProjectedLineupToggle() {
  const buttons = document.querySelectorAll('.projected-lineup-toggle .toggle-btn');
  if (!buttons.length) return;
  buttons.forEach((b) => {
    if (b.getAttribute('data-projected-view') === projectedLineupView) b.classList.add('active');
    else b.classList.remove('active');
  });
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      playSound('click-tiny.wav');
      buttons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      projectedLineupView = btn.getAttribute('data-projected-view') || 'attributes';
      renderProjectedStartingFiveSection();
    });
  });
}

function formatTrainingSeasonStat(stats, col) {
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

function buildSeasonStatsByPlayerId() {
  const map = new Map();
  (reportData.players || []).forEach((p) => {
    const pid = p.player_id || p.id;
    if (pid != null && pid !== '') map.set(String(pid), p.season_stats || {});
  });
  return map;
}

function renderProjectedStartingFiveStats(rows) {
  const el = document.getElementById('training-projected-lineup');
  if (!el) return;
  el.innerHTML = '';
  if (!rows || rows.length === 0) {
    el.innerHTML =
      '<p class="training-projected-empty">No projected lineup (missing position ratings or roster data).</p>';
    return;
  }
  const statsMap = buildSeasonStatsByPlayerId();
  const table = document.createElement('table');
  table.className = 'training-projected-table';
  const thead = document.createElement('thead');
  const hrow = document.createElement('tr');
  const headers = ['Pos', 'Player'].concat(TRAINING_PROJECTED_STATS_COLUMNS);
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
    const stats = statsMap.get(pid) || {};
    const playerLabel =
      typeof formatNameWithJersey === 'function'
        ? formatNameWithJersey(r.jersey, r.name || '')
        : r.name || '—';
    const cells = [r.position || '—', playerLabel];
    TRAINING_PROJECTED_STATS_COLUMNS.forEach((col) => {
      cells.push(formatTrainingSeasonStat(stats, col));
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
  enhanceProjectedStartingFiveTable();
}

function renderProjectedStartingFiveSection() {
  if (!reportData) return;
  const rows = reportData.projected_starting_five || [];
  if (projectedLineupView === 'stats') {
    renderProjectedStartingFiveStats(rows);
    return;
  }
  if (typeof renderProjectedStartingFive === 'function') {
    renderProjectedStartingFive(rows, {
      containerId: 'training-projected-lineup',
      tableClass: 'training-projected-table',
      emptyClass: 'training-projected-empty',
    });
    enhanceProjectedStartingFiveTable();
  }
}

function setupViewToggle() {
  const toggleButtons = document.querySelectorAll('.players-section .toggle-btn');
  // Enforce initial active button from currentView
  toggleButtons.forEach(b => {
    if (b.dataset.view === currentView) b.classList.add('active');
    else b.classList.remove('active');
  });
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      playSound('click-tiny.wav');
      toggleButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentView = btn.dataset.view;
      renderPlayersTable();
    });
  });
}

function setupLockerRoomButton() {
  const btn = document.getElementById('locker-room-btn');
  if (!btn) return;
  
  btn.addEventListener('click', () => {
    playSound('click-strong.wav');
    if (mode === 'franchise') {
      const lockerRoomUrl = (typeof resolveFranchiseLockerRoomUrl === 'function')
        ? resolveFranchiseLockerRoomUrl({
            franchiseId: franchiseId,
            teamId: teamId
          })
        : `/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}`;
      window.location.href = lockerRoomUrl;
    } else if (mode === 'tournament') {
      // Use same pattern as franchise mode - tournament.html is the command center
      window.location.href = `/tournament.html?tournament_id=${tournamentId}&team_id=${teamId}`;
    }
  });
}

async function loadTrainingReport() {
  try {
    const params = new URLSearchParams({
      mode: mode,
      team_id: teamId
    });
    
    if (franchiseId) {
      params.set('franchise_id', franchiseId);
      params.set('week', week);
    }
    if (tournamentId) {
      params.set('tournament_id', tournamentId);
      // SS&S: Only send round/week if provided - backend will determine from state if not provided
      if (round) {
        params.set('round', round);
      } else if (week) {
        params.set('week', week); // Backward compatibility
      }
      // If neither round nor week provided, backend will determine from training_status
    }
    
    const response = await fetch(`${API_CONFIG.buildUrl('/franchise/training-report')}?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to load training report: ${response.statusText}`);
    }
    
    reportData = await response.json();
    renderPage();
  } catch (error) {
    console.error('Error loading training report:', error);
    alert('Failed to load training report. Please try again.');
  }
}

function renderPage() {
  if (!reportData) return;
  
  // Render header
  renderHeader();
  
  // Render players table
  renderPlayersTable();
  
  // Render team attributes
  renderTeamAttributes();
  
  // Render playbook summary
  renderPlaybookSummary();

  renderProjectedStartingFiveSection();
  
  // Render training notes
  renderTrainingNotes();
}

function renderHeader() {
  // For tournament mode, display "Round X"; for franchise mode, display "Week X"
  const periodLabel = mode === 'tournament' ? 'Round' : 'Week';
  const periodValue = mode === 'tournament' ? (reportData.round || round) : reportData.week;
  document.getElementById('week-number').textContent = periodValue || '--';
  
  // Update label
  const weekLabel = document.getElementById('week-label');
  if (weekLabel) {
    weekLabel.textContent = periodLabel + ':';
  }
  
  document.getElementById('upcoming-opponent').textContent = reportData.upcoming_opponent || '--';
  
  const focus = reportData.coaching_focus || {};
  const archetype = focus.archetype || '';
  const subOption = focus.sub_option || '';
  
  let focusText = '--';
  if (archetype && subOption) {
    // Map archetype to full name
    const archetypeMap = {
      'authoritarian': 'Authoritarian',
      'systems-coach': 'Systems Coach',
      'player-maximizer': 'Player Maximizer',
      'culture': 'Culture Builder',
      'culture-builder': 'Culture Builder'
    };
    
    // Get archetype display name
    let archetypeDisplay = archetypeMap[archetype] || archetype.split('-').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');

    // Backend may send explicit leaf label (e.g. Team Building vs Teamwork—which share no API token ambiguity once labeled)
    const leafFromApi = focus.leaf_display_name;
    if (leafFromApi) {
      focusText = `${leafFromApi} (${archetypeDisplay})`;
    } else {
    // Remove archetype prefix from sub_option (e.g., "systems-coach-offense" -> "offense")
    let subOptionClean = subOption;
    if (subOption.startsWith(archetype + '-')) {
      subOptionClean = subOption.substring(archetype.length + 1);
    } else if (archetype === 'culture' && subOption.startsWith('builder-')) {
      subOptionClean = subOption.substring('builder-'.length);
    }
    
    // Special handling for systems-coach: remove "coach-" prefix if present
    if (archetype === 'systems-coach' && subOptionClean.startsWith('coach-')) {
      subOptionClean = subOptionClean.substring('coach-'.length);
    }

    // Player Maximizer: keep "4–6" and short labels (split('-') breaks "attributes-4-6")
    const PM_SUBOPTION_LABEL = {
      'top-3': 'Top 3',
      'attributes-4-6': 'Attributes 4–6',
      'positional-focus': 'Positional Focus',
      'custom': 'Custom',
      'choose-attributes': 'Choose Attributes'
    };
    let formatSubOption;
    if (archetype === 'player-maximizer' && PM_SUBOPTION_LABEL[subOptionClean]) {
      formatSubOption = PM_SUBOPTION_LABEL[subOptionClean];
    } else {
      formatSubOption = subOptionClean.split('-').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ');
    }
    
    // Format: focus (archetype) - focus outside, archetype inside parentheses
    focusText = `${formatSubOption} (${archetypeDisplay})`;
    }
  }
  
  document.getElementById('training-focus').textContent = focusText;
}

function getReportWeekNumber() {
  return Number(reportData?.week || week || 0);
}

function getExceptionalGainThreshold() {
  return getReportWeekNumber() === 1 ? 10 : 5;
}

function getPlayerDisplayPosition(player) {
  const validPositions = ['PG', 'SG', 'SF', 'PF', 'C'];
  const direct = String(player?.position || '').toUpperCase().trim();
  if (validPositions.includes(direct)) return direct;

  const ratings = player?.position_ratings || {};
  let bestPos = 'PG';
  let bestVal = -Infinity;
  validPositions.forEach((pos) => {
    const value = Number(ratings[pos]) || 0;
    if (value > bestVal) {
      bestVal = value;
      bestPos = pos;
    }
  });
  return bestPos;
}

function getPracticePlayerOfWeekNames() {
  const names = new Set();
  const players = (reportData?.players || []).map((p) => String(p?.name || '').trim()).filter(Boolean);
  const notes = reportData?.training_notes || [];
  notes.forEach((section) => {
    const title = typeof section === 'object' ? String(section.title || '') : '';
    if (!/Practice Player(?:s)? Of The Week/i.test(title)) return;
    const body = typeof section === 'object' ? String(section.body || '') : String(section || '');
    const bodyLower = body.toLowerCase();
    players.forEach((name) => {
      if (bodyLower.includes(name.toLowerCase())) names.add(name);
    });
  });
  return names;
}

function isMutedTrainingNote(text) {
  const normalized = String(text || '').trim().toLowerCase();
  return (
    !normalized ||
    normalized === 'neutral' ||
    /no significant updates/.test(normalized) ||
    /no significant update/.test(normalized) ||
    /no significant changes/.test(normalized) ||
    /no significant change/.test(normalized) ||
    /no notable updates/.test(normalized) ||
    /no notable changes/.test(normalized)
  );
}

function getTrainingReportPlayerName(player) {
  return String(
    player?.name ||
    player?.player_name ||
    player?.full_name ||
    `${player?.first_name || ''} ${player?.last_name || ''}`
  ).trim();
}

function getTrainingReportPlayerInitials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '—';
  return parts.slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join('');
}

function getTrainingReportPlayerPortraitUrl(player) {
  const playerId = player?.player_id || player?._id || player?.id || '';
  if (player?.photo) return player.photo;
  if (window.API_CONFIG && typeof window.API_CONFIG.buildStaticPath === 'function') {
    return playerId
      ? window.API_CONFIG.buildStaticPath(`/images/players/${playerId}.png`)
      : window.API_CONFIG.buildStaticPath('/images/players/generic_headshot.png');
  }
  return playerId ? `/images/players/${playerId}.png` : '/images/players/generic_headshot.png';
}

function normalizeTrainingReportText(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getTrainingReportPlayerNameCandidates(player) {
  const candidates = new Set();
  const fullName = getTrainingReportPlayerName(player);
  const firstName = String(player?.first_name || '').trim();
  const lastName = String(player?.last_name || '').trim();
  if (fullName) candidates.add(fullName);
  if (firstName && lastName) {
    candidates.add(`${firstName} ${lastName}`);
    candidates.add(`${lastName}, ${firstName}`);
  }
  if (lastName) candidates.add(lastName);
  return Array.from(candidates)
    .map(normalizeTrainingReportText)
    .filter(Boolean);
}

function getTrainingNotePortraitPlayer(sectionOrTitle, text) {
  const section = (sectionOrTitle && typeof sectionOrTitle === 'object') ? sectionOrTitle : null;
  const title = section ? String(section.title || '') : String(sectionOrTitle || '');
  const eligibleTitles = new Set([
    'Practice Player Of The Week',
    'Practice Players Of The Week',
    'Biggest Regression',
    'Most Positive Locker Room Influence'
  ]);
  if (!eligibleTitles.has(title)) return null;
  const players = Array.isArray(reportData?.players) ? reportData.players : [];
  const playerIds = section
    ? [
        ...(section.player_id ? [String(section.player_id)] : []),
        ...((Array.isArray(section.player_ids) ? section.player_ids : []).map((id) => String(id)))
      ]
    : [];
  console.log('[TRAINING REPORT][NOTES] portrait lookup start', {
    title,
    body: String(text || ''),
    player_id: section?.player_id || null,
    player_ids: section?.player_ids || [],
    report_player_count: players.length,
  });
  if (playerIds.length) {
    const byId = new Map(players.map((player) => [
      String(player?.player_id || player?._id || player?.id || ''),
      player
    ]));
    const directMatch = playerIds.map((id) => byId.get(id)).find(Boolean);
    if (directMatch) {
      console.log('[TRAINING REPORT][NOTES] portrait direct id match', {
        title,
        matched_player: getTrainingReportPlayerName(directMatch),
        matched_player_id: String(directMatch?.player_id || directMatch?._id || directMatch?.id || ''),
      });
      return directMatch;
    }
    console.warn('[TRAINING REPORT][NOTES] portrait id match failed', {
      title,
      requested_ids: playerIds,
      available_ids_sample: players.slice(0, 12).map((player) => String(player?.player_id || player?._id || player?.id || '')),
    });
  }
  const haystack = ` ${normalizeTrainingReportText(text)} `;
  let bestMatch = null;
  players.forEach((player) => {
    const candidates = getTrainingReportPlayerNameCandidates(player);
    if (!candidates.length) return;
    const matchedCandidate = candidates.find((candidate) => haystack.includes(` ${candidate} `) || haystack.includes(candidate));
    if (!matchedCandidate) return;
    if (!bestMatch || matchedCandidate.length > normalizeTrainingReportText(getTrainingReportPlayerName(bestMatch)).length) {
      bestMatch = player;
    }
  });
  console.log('[TRAINING REPORT][NOTES] portrait text fallback result', {
    title,
    matched_player: bestMatch ? getTrainingReportPlayerName(bestMatch) : null,
    matched_player_id: bestMatch ? String(bestMatch?.player_id || bestMatch?._id || bestMatch?.id || '') : null,
  });
  return bestMatch;
}

function createTrainingNotePortrait(player, text) {
  const normalizedText = normalizeTrainingReportText(text);
  if (!player && (
    !normalizedText ||
    normalizedText === 'no significant updates' ||
    normalizedText === 'none'
  )) {
    return null;
  }
  const playerName = getTrainingReportPlayerName(player) || String(text || '').trim();
  const initials = getTrainingReportPlayerInitials(playerName);
  const wrap = document.createElement('div');
  wrap.className = 'training-note-portrait-wrap';

  const fallback = document.createElement('div');
  fallback.className = 'training-note-portrait-fallback';
  fallback.textContent = initials;
  fallback.setAttribute('aria-label', `${playerName || 'Player'} portrait placeholder`);

  if (!player) {
    wrap.appendChild(fallback);
    return wrap;
  }

  const img = document.createElement('img');
  img.className = 'training-note-portrait';
  img.alt = playerName ? `${playerName} headshot` : 'Player headshot';
  const portraitUrl = getTrainingReportPlayerPortraitUrl(player);
  console.log('[TRAINING REPORT][NOTES] portrait render attempt', {
    player_name: playerName,
    player_id: String(player?.player_id || player?._id || player?.id || ''),
    player_photo: player?.photo || null,
    portrait_url: portraitUrl,
  });
  img.src = portraitUrl;
  img.onerror = function () {
    console.warn('[TRAINING REPORT][NOTES] portrait image failed', {
      player_name: playerName,
      player_id: String(player?.player_id || player?._id || player?.id || ''),
      attempted_url: portraitUrl,
    });
    wrap.innerHTML = '';
    wrap.appendChild(fallback);
  };
  wrap.appendChild(img);
  return wrap;
}

function createPlayerNameCell(player) {
  const td = document.createElement('td');
  td.className = 'player-name-cell';

  const badge = document.createElement('span');
  badge.className = 'position-badge';
  badge.textContent = getPlayerDisplayPosition(player);

  const name = document.createElement('span');
  name.className = 'player-name-text';
  name.textContent = player.name || '—';

  td.appendChild(badge);
  td.appendChild(name);
  return td;
}

function renderPlayersTable() {
  if (!reportData || !reportData.players) return;
  
  const thead = document.getElementById('players-thead');
  const tbody = document.getElementById('players-tbody');
  
  // Clear existing content
  thead.innerHTML = '';
  tbody.innerHTML = '';
  
  // Build header
  const headerRow = document.createElement('tr');
  headerRow.appendChild(createHeaderCell('Name'));
  
  let attributeList = [];
  if (currentView === 'attributes') {
    // Attributes view: show all player attributes in exact order
    attributeList = ATTRIBUTE_ORDER.filter(attr => ATTRIBUTE_NAMES[attr]);
    attributeList.forEach(attr => {
      headerRow.appendChild(createHeaderCell(attr));
    });
  } else {
    // Changes view: show only attributes that changed, but maintain order
    const changedAttrs = new Set();
    Object.values(reportData.player_changes || {}).forEach(changes => {
      Object.keys(changes).forEach(attr => changedAttrs.add(attr));
    });
    
    // Filter to only changed attrs, but maintain ATTRIBUTE_ORDER
    attributeList = ATTRIBUTE_ORDER.filter(attr => changedAttrs.has(attr));
    attributeList.forEach(attr => {
      headerRow.appendChild(createHeaderCell(attr));
    });
  }

  STATIC_COLUMNS.forEach(col => {
    headerRow.appendChild(createHeaderCell(col));
  });
  
  thead.appendChild(headerRow);
  
  // Build rows
  const practicePlayers = getPracticePlayerOfWeekNames();
  getSortedPlayersForReport().forEach(player => {
    const row = document.createElement('tr');
    if (practicePlayers.has(player.name)) {
      row.classList.add('practice-player-highlight');
    }
    row.appendChild(createPlayerNameCell(player));
    
    if (currentView === 'attributes') {
      // Show current attribute values with tooltips
      attributeList.forEach(attr => {
        const value = player.attributes[attr] || (attr === 'NG' ? 1.0 : attr === 'EM' ? 50 : attr === 'MO' ? 0 : 0);
        const changes = reportData.player_changes[player.name] || {};
        const change = changes[attr] || 0;
        row.appendChild(createAttributeCell(attr, value, change));
      });
    } else {
      // Show changes for this player (0 if no change)
      attributeList.forEach(attr => {
        const changes = reportData.player_changes[player.name] || {};
        const change = changes[attr] || 0;
        row.appendChild(createChangeCell(change));
      });
    }

    row.appendChild(createCell(getPlayerHighestRt(player)));
    
    tbody.appendChild(row);
  });
  
  // Add aggregated row for Training Changes view
  if (currentView === 'changes' && attributeList.length > 0) {
    const totalRow = document.createElement('tr');
    totalRow.className = 'total-row';
    totalRow.appendChild(createCell('Total'));
    
    // Calculate totals for each attribute
    attributeList.forEach(attr => {
      let total = 0;
      reportData.players.forEach(player => {
        const changes = reportData.player_changes[player.name] || {};
        total += changes[attr] || 0;
      });
      totalRow.appendChild(createChangeCell(total));
    });

    totalRow.appendChild(createCell('—'));
    
    tbody.appendChild(totalRow);
  }
}

function getPlayerHighestRt(player) {
  const ratings = player && player.position_ratings ? player.position_ratings : {};
  const values = Object.values(ratings).map(v => Number(v) || 0);
  if (!values.length) return 0;
  return Math.max(...values);
}

function getSortedPlayersForReport() {
  return (reportData.players || [])
    .map((player, index) => ({ player, index }))
    .sort((a, b) => {
      const rtDiff = getPlayerHighestRt(b.player) - getPlayerHighestRt(a.player);
      if (rtDiff !== 0) return rtDiff;
      return a.index - b.index;
    })
    .map(entry => entry.player);
}

function createHeaderCell(text) {
  const th = document.createElement('th');
  th.textContent = text;
  return th;
}

function createCell(text) {
  const td = document.createElement('td');
  td.textContent = text;
  return td;
}

function createAttributeCell(attr, value, change) {
  const td = document.createElement('td');
  td.className = 'attribute-value-cell';
  
  // Special handling for NG, EM, MO
  if (attr === 'NG') {
    // Display with 2 decimal places
    td.textContent = typeof value === 'number' ? value.toFixed(2) : '1.00';
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  } else if (attr === 'EM') {
    // Display with emoji
    const emoji = getEmotionEmoji(value);
    td.innerHTML = emoji;
    td.style.fontSize = '1.5rem';
    td.style.textAlign = 'center';
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  } else if (attr === 'MO') {
    // Display with red/green pill (no integer on top)
    const pillContainer = createMomentumPill(value);
    td.appendChild(pillContainer);
    td.style.padding = 'var(--spacing-xs)';
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  } else {
    // Standard integer display with tooltip - show full value (no rounding)
    // Ensure we display the full integer value, not a rounded version
    const displayValue = typeof value === 'number' ? Math.floor(value) : (typeof value === 'string' ? parseInt(value, 10) || 0 : 0);
    td.textContent = displayValue.toString();
    if (change !== 0) {
      td.setAttribute('data-tooltip', formatChangeForTooltip(change));
      td.style.cursor = 'help';
      td.addEventListener('mouseenter', showAttributeTooltip);
      td.addEventListener('mouseleave', hideAttributeTooltip);
      td.addEventListener('mousemove', positionAttributeTooltip);
    }
  }
  
  return td;
}

function getEmotionEmoji(em) {
  const emValue = typeof em === 'number' ? em : 50;
  if (emValue >= 80) return '😎';        // Sunglasses
  else if (emValue >= 60) return '😊';   // Big smile
  else if (emValue >= 40) return '😐';   // Straight face
  else if (emValue >= 20) return '😕';   // Slight frown
  else return '😡';                      // Angry face
}

function createMomentumPill(mo) {
  const container = document.createElement('div');
  container.className = 'momentum-pill-container';
  container.style.position = 'relative';
  container.style.width = '100%';
  container.style.height = '30px';
  container.style.background = 'rgba(0, 0, 0, 0.3)';
  container.style.borderRadius = '15px';
  container.style.overflow = 'hidden';
  
  // Center line
  const centerLine = document.createElement('div');
  centerLine.style.position = 'absolute';
  centerLine.style.left = '50%';
  centerLine.style.top = '0';
  centerLine.style.bottom = '0';
  centerLine.style.width = '2px';
  centerLine.style.background = 'var(--color-warning)';
  centerLine.style.transform = 'translateX(-50%)';
  centerLine.style.zIndex = '2';
  container.appendChild(centerLine);
  
  const moValue = typeof mo === 'number' ? mo : 0;
  const maxValue = 10; // MO ranges from -10 to +10
  
  // Fill based on value
  if (moValue > 0) {
    const fill = document.createElement('div');
    fill.style.position = 'absolute';
    fill.style.left = '50%';
    fill.style.top = '0';
    fill.style.bottom = '0';
    fill.style.background = 'var(--color-success)';
    fill.style.transition = 'width 0.3s ease';
    fill.style.zIndex = '1';
    const percentage = Math.min((moValue / maxValue) * 50, 50); // Max 50% to the right
    fill.style.width = `${percentage}%`;
    container.appendChild(fill);
  } else if (moValue < 0) {
    const fill = document.createElement('div');
    fill.style.position = 'absolute';
    fill.style.right = '50%';
    fill.style.top = '0';
    fill.style.bottom = '0';
    fill.style.background = 'var(--color-error)';
    fill.style.transition = 'width 0.3s ease';
    fill.style.zIndex = '1';
    const absValue = Math.abs(moValue);
    const percentage = Math.min((absValue / maxValue) * 50, 50); // Max 50% to the left
    fill.style.width = `${percentage}%`;
    container.appendChild(fill);
  }
  
  return container;
}

function formatChangeForTooltip(change, attrKey = null) {
  // ✅ FIX: Format rebound_modifier changes to 2 decimal places
  const formattedChange = attrKey === 'rebound_modifier' 
    ? (change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2))
    : (change > 0 ? `+${change}` : change.toString());
  
  if (change > 0) {
    return formattedChange;
  } else if (change < 0) {
    return formattedChange;
  } else {
    return '0';
  }
}

function showAttributeTooltip(event) {
  const cell = event.target;
  const changeText = cell.getAttribute('data-tooltip');
  if (!changeText) return;
  
  // Create tooltip element if it doesn't exist
  let tooltip = document.getElementById('attribute-tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'attribute-tooltip';
    tooltip.className = 'attribute-tooltip';
    document.body.appendChild(tooltip);
  }
  
  // Determine color based on change value
  const change = parseInt(changeText.replace('+', ''), 10);
  if (change > 0) {
    tooltip.className = 'attribute-tooltip attribute-tooltip-positive';
  } else if (change < 0) {
    tooltip.className = 'attribute-tooltip attribute-tooltip-negative';
  } else {
    tooltip.className = 'attribute-tooltip attribute-tooltip-zero';
  }
  
  tooltip.textContent = changeText;
  tooltip.style.display = 'block';
  positionAttributeTooltip(event);
}

function hideAttributeTooltip() {
  const tooltip = document.getElementById('attribute-tooltip');
  if (tooltip) {
    tooltip.style.display = 'none';
  }
}

function positionAttributeTooltip(event) {
  const tooltip = document.getElementById('attribute-tooltip');
  if (!tooltip || tooltip.style.display === 'none') return;
  
  const cell = event.target;
  const rect = cell.getBoundingClientRect();
  
  // Position tooltip above the cell
  tooltip.style.left = `${rect.left + rect.width / 2}px`;
  tooltip.style.top = `${rect.top - 10}px`;
  tooltip.style.transform = 'translate(-50%, -100%)';
}

function createChangeCell(change) {
  const td = document.createElement('td');
  const exceptionalThreshold = getExceptionalGainThreshold();
  
  if (change >= exceptionalThreshold) {
    td.textContent = `+${change}`;
    td.className = 'change-gold';
  } else if (change > 0) {
    td.textContent = `+${change}`;
    td.className = 'change-positive';
  } else if (change < 0) {
    td.textContent = change.toString();
    td.className = 'change-negative';
  } else {
    td.textContent = '0';
    td.className = 'change-zero';
  }
  
  return td;
}

function renderTeamAttributes() {
  if (!reportData) return;
  
  const grid = document.getElementById('team-attributes-grid');
  grid.innerHTML = '';
  
  const teamAttrs = reportData.team_attributes || {};
  const teamChanges = reportData.team_changes || {};
  
  // Define order of attributes
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
    const item = createTeamAttrItem(attrKey, teamAttrs[attrKey], teamChanges[attrKey]);
    if (item) grid.appendChild(item);
  });
}

function createTeamAttrItem(attrKey, currentValue, change) {
  const displayName = TEAM_ATTR_NAMES[attrKey];
  if (!displayName) return null;
  
  // Handle undefined values
  if (currentValue === undefined || currentValue === null) {
    currentValue = 0;
  }
  if (change === undefined || change === null) {
    change = 0;
  }
  
  const item = document.createElement('div');
  item.className = 'team-attr-item';
  if (change === 0) item.classList.add('is-muted');
  
  const label = document.createElement('div');
  label.className = 'attr-label';
  
  const nameSpan = document.createElement('span');
  nameSpan.className = 'attr-name';
  nameSpan.textContent = displayName;
  
  const changeSpan = document.createElement('span');
  changeSpan.className = 'attr-change';
  
  if (change !== 0) {
    if (attrKey === 'rebound_modifier') {
      // Format rebound_modifier changes to 2 decimal places
      const formattedChange = change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2);
      changeSpan.textContent = formattedChange;
      if (change > 0) {
        changeSpan.className += change >= getExceptionalGainThreshold() ? ' change-gold' : ' change-positive';
      } else {
        changeSpan.className += ' change-negative';
      }
    } else {
      // Standard handling for other attributes
      const formattedChange = change > 0 ? `+${change}` : change.toString();
      changeSpan.textContent = formattedChange;
      if (change > 0) {
        changeSpan.className += change >= getExceptionalGainThreshold() ? ' change-gold' : ' change-positive';
      } else {
        changeSpan.className += ' change-negative';
      }
    }
  } else {
    changeSpan.textContent = 'No change';
    changeSpan.className += ' change-zero';
  }
  
  label.appendChild(nameSpan);
  label.appendChild(changeSpan);
  item.appendChild(label);
  
  // Special handling for different attribute types
  if (attrKey === 'team_chemistry') {
    // Progress bar (0-25)
    const barContainer = document.createElement('div');
    barContainer.className = 'chemistry-bar-container';
    
    const barFill = document.createElement('div');
    barFill.className = 'chemistry-bar-fill';
    const percentage = (currentValue / 25) * 100;
    barFill.style.width = `${percentage}%`;
    
    const barText = document.createElement('div');
    barText.className = 'chemistry-bar-text';
    barText.textContent = `${currentValue} / 25`;
    
    barContainer.appendChild(barFill);
    barContainer.appendChild(barText);
    item.appendChild(barContainer);
  } else {
    // Red/Green Pill Design
    const pill = createPill(currentValue, attrKey);
    item.appendChild(pill);
  }
  
  return item;
}

function createPill(originalValue, attrKey) {
  const pill = document.createElement('div');
  pill.className = 'attr-pill';
  
  // Center line
  const centerLine = document.createElement('div');
  centerLine.className = 'pill-center-line';
  pill.appendChild(centerLine);
  
  // Determine max value for this attribute (for proportional fill)
  let maxValue = 10; // Default for most attributes
  let displayValue = originalValue;
  let value = originalValue;
  
  if (attrKey === 'shot_threshold') {
    maxValue = 100; // Range is 10 to 210, center at 110, so max deviation is 100
    value = 110 - originalValue; // Invert: lower is better (positive/green), higher is worse (negative/red)
  } else if (attrKey === 'rebound_modifier') {
    // Rebound modifier is 0.0-0.4, center at 0.2
    // We'll show deviation from 0.2
    maxValue = 0.2; // Max deviation is 0.2 (from 0.0 to 0.2 or 0.2 to 0.4)
    value = originalValue - 0.2; // Center at 0 for fill calculation
    displayValue = originalValue.toFixed(2); // Show original value with 2 decimals
  }
  
  // Value display - only show for Team Chemistry (handled separately)
  // For other pills, we don't show the value on top
  
  // Fill based on value
  if (value > 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-positive';
    if ((value / maxValue) >= 0.7) fill.classList.add('is-extreme');
    const percentage = Math.min((value / maxValue) * 50, 50); // Max 50% to the right
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  } else if (value < 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-negative';
    if ((Math.abs(value) / maxValue) >= 0.7) fill.classList.add('is-extreme');
    const absValue = Math.abs(value);
    const percentage = Math.min((absValue / maxValue) * 50, 50); // Max 50% to the left
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  }
  
  return pill;
}

function renderPlaybookSummary() {
  if (!reportData) return;
  
  const container = document.getElementById('playbook-summary-container');
  container.innerHTML = '';
  
  const plays_data = reportData.plays_data || {};
  const scouting_data = reportData.scouting_data || {};
  const plays_changes = buildTrainingReportPlayChangesLookup(
    plays_data,
    reportData.plays_effectiveness_changes || {}
  );
  const defenses_changes = reportData.defenses_effectiveness_changes || {};
  
  // Organize plays by type
  const motion_plays = [];
  const set_plays = [];
  
  for (const [play_name, play_data] of Object.entries(plays_data)) {
    if (typeof play_data === 'object' && play_data !== null) {
      const play_type = play_data.play_type || '';
      if (play_type === 'motion') {
        motion_plays.push(buildTrainingReportPlayEntry(play_name, play_data));
      } else if (play_type === 'set_play') {
        set_plays.push(buildTrainingReportPlayEntry(play_name, play_data));
      }
    }
  }
  
  // Sort plays by name
  motion_plays.sort((a, b) => a.name.localeCompare(b.name));
  set_plays.sort((a, b) => a.name.localeCompare(b.name));
  
  // Organize defenses
  const man_defenses = [];
  const zone_defenses = [];
  
  if (scouting_data.defense) {
    for (const [defense_name, defense_data] of Object.entries(scouting_data.defense)) {
      if (typeof defense_data === 'object' && defense_data !== null) {
        if (defense_name === 'Man') {
          man_defenses.push({ name: defense_name, ...defense_data });
        } else if (defense_name.includes('Zone')) {
          zone_defenses.push({ name: defense_name, ...defense_data });
        }
      }
    }
  }
  
  // Sort defenses by name
  man_defenses.sort((a, b) => a.name.localeCompare(b.name));
  zone_defenses.sort((a, b) => a.name.localeCompare(b.name));
  
  container.appendChild(createPlaybookCategorySection('Offense', motion_plays.concat(set_plays), plays_changes));
  container.appendChild(createPlaybookCategorySection('Defense', man_defenses.concat(zone_defenses), defenses_changes));
}

function looksLikeTrainingReportObjectId(value) {
  return typeof value === 'string' && /^[a-f0-9]{24}$/i.test(value.trim());
}

function normalizeTrainingReportPlayId(value) {
  if (value == null) return null;

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;

    const objectIdMatch = trimmed.match(/^ObjectId\((['"]?)([a-f0-9]{24})\1\)$/i);
    if (objectIdMatch) {
      return objectIdMatch[2];
    }

    return trimmed;
  }

  if (typeof value === 'object') {
    if (typeof value.$oid === 'string' && value.$oid.trim()) {
      return value.$oid.trim();
    }
    if (typeof value.play_id === 'string' && value.play_id.trim()) {
      return value.play_id.trim();
    }
    if (typeof value.playId === 'string' && value.playId.trim()) {
      return value.playId.trim();
    }
    if (typeof value._id === 'string' && value._id.trim()) {
      return value._id.trim();
    }
    if (typeof value.id === 'string' && value.id.trim()) {
      return value.id.trim();
    }
  }

  const coerced = String(value).trim();
  return coerced && coerced !== '[object Object]' ? coerced : null;
}

function normalizeTrainingReportChangeValue(value) {
  if (value == null) return 0;

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0;
  }

  if (typeof value === 'string') {
    const parsed = Number(value.trim());
    return Number.isFinite(parsed) ? parsed : 0;
  }

  if (typeof value === 'object') {
    const numericKeys = ['$numberInt', '$numberLong', '$numberDouble', '$numberDecimal'];
    for (const key of numericKeys) {
      if (typeof value[key] === 'string') {
        const parsed = Number(value[key]);
        if (Number.isFinite(parsed)) {
          return parsed;
        }
      }
    }
  }

  const fallback = Number(value);
  return Number.isFinite(fallback) ? fallback : 0;
}

function buildTrainingReportPlayEntry(playKey, playData) {
  const resolvedName = playData.name || playKey;
  const resolvedPlayId =
    normalizeTrainingReportPlayId(playData.play_id) ||
    normalizeTrainingReportPlayId(playData.playId) ||
    normalizeTrainingReportPlayId(playData._id) ||
    normalizeTrainingReportPlayId(playData.id) ||
    (looksLikeTrainingReportObjectId(playKey) ? playKey : null);

  return {
    ...playData,
    name: resolvedName,
    display_name: resolvedName,
    play_key: playKey,
    play_id: resolvedPlayId
  };
}

function buildTrainingReportPlayChangesLookup(playsData, rawChanges) {
  const lookup = {};

  if (rawChanges && typeof rawChanges === 'object') {
    Object.entries(rawChanges).forEach(([rawKey, rawValue]) => {
      lookup[rawKey] = normalizeTrainingReportChangeValue(rawValue);

      const normalizedKey = normalizeTrainingReportPlayId(rawKey);
      if (normalizedKey && !(normalizedKey in lookup)) {
        lookup[normalizedKey] = lookup[rawKey];
      }
    });
  }

  Object.entries(playsData || {}).forEach(([playKey, playData]) => {
    if (!playData || typeof playData !== 'object') return;

    const playEntry = buildTrainingReportPlayEntry(playKey, playData);
    const candidateKeys = [
      playEntry.play_id,
      playEntry.name,
      playEntry.display_name,
      playEntry.play_key
    ].filter(Boolean);

    let resolvedChange;
    for (const key of candidateKeys) {
      if (Object.prototype.hasOwnProperty.call(lookup, key)) {
        resolvedChange = lookup[key];
        break;
      }
    }

    if (resolvedChange == null) return;

    candidateKeys.forEach((key) => {
      lookup[key] = resolvedChange;
    });
  });

  return lookup;
}

function getTrainingReportPlayChange(playsChanges, play) {
  if (!playsChanges || !play) return 0;

  const candidates = [
    normalizeTrainingReportPlayId(play.play_id),
    normalizeTrainingReportPlayId(play.playId),
    normalizeTrainingReportPlayId(play._id),
    normalizeTrainingReportPlayId(play.id),
    play.name,
    play.play_key
  ].filter(Boolean);

  for (const key of candidates) {
    if (Object.prototype.hasOwnProperty.call(playsChanges, key)) {
      return normalizeTrainingReportChangeValue(playsChanges[key]);
    }
  }

  return 0;
}

function createPlaybookCategorySection(title, items, changesLookup) {
  const section = document.createElement('div');
  section.className = 'playbook-category';

  const header = document.createElement('div');
  header.className = 'playbook-category-header';
  const heading = document.createElement('h3');
  heading.textContent = title;
  header.appendChild(heading);
  section.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'playbook-card-grid';

  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'playbook-empty-state';
    empty.textContent = 'No data available.';
    grid.appendChild(empty);
  } else {
    items.forEach((item) => {
      const change = title === 'Offense'
        ? getTrainingReportPlayChange(changesLookup, item)
        : normalizeTrainingReportChangeValue(changesLookup[item.name] || 0);
      grid.appendChild(createPlayCard(item.display_name || item.name, item, change));
    });
  }

  section.appendChild(grid);
  return section;
}

function createPlayCard(playName, playData, change) {
  const effectiveness = typeof playData === 'object' ? (playData.effectiveness || 0) : (playData || 0);
  const momentum = typeof playData === 'object' ? (playData.momentum || 0) : 0;
  const cloaking = typeof playData === 'object' ? (playData.cloaking || 0) : 0;

  const row = document.createElement('div');
  row.className = 'playbook-card';
  if (playData && typeof playData === 'object') {
    const normalizedPlayId = normalizeTrainingReportPlayId(playData.play_id || playData.playId || playData._id || playData.id);
    if (normalizedPlayId) {
      row.dataset.playId = normalizedPlayId;
    }
  }

  const top = document.createElement('div');
  top.className = 'playbook-card-top';

  const nameDiv = document.createElement('div');
  nameDiv.className = 'playbook-card-name';
  nameDiv.textContent = playName;

  const delta = document.createElement('div');
  delta.className = 'playbook-card-delta';
  if (change > 0) {
    delta.textContent = `+${change}`;
    delta.classList.add('is-positive');
  } else if (change < 0) {
    delta.textContent = String(change);
    delta.classList.add('is-negative');
  } else {
    delta.textContent = '0';
    delta.classList.add('is-zero');
  }

  top.appendChild(nameDiv);
  top.appendChild(delta);
  row.appendChild(top);

  const bars = document.createElement('div');
  bars.className = 'playbook-card-bars';
  bars.appendChild(createPlaybookMetricCard('Command', effectiveness, 100, '#4065AF'));
  bars.appendChild(createPlaybookMetricCard('Momentum', momentum, 10, '#F79420'));
  bars.appendChild(createPlaybookMetricCard('Cloaking', cloaking, 10, '#7B5EA7'));
  row.appendChild(bars);

  return row;
}

function createPlaybookMetricCard(title, value, maxValue, color) {
  const metricDiv = document.createElement('div');
  metricDiv.className = 'playbook-metric-card';

  const titleDiv = document.createElement('div');
  titleDiv.className = 'playbook-metric-title';
  titleDiv.textContent = title;
  metricDiv.appendChild(titleDiv);

  const progressBar = document.createElement('div');
  progressBar.className = 'playbook-progress-bar';

  const progressFill = document.createElement('div');
  progressFill.className = 'playbook-progress-fill';
  progressFill.style.backgroundColor = color;
  const percentage = Math.min(100, (value / maxValue) * 100);
  progressFill.style.width = `${percentage}%`;

  progressBar.appendChild(progressFill);
  metricDiv.appendChild(progressBar);
  return metricDiv;
}

function renderTrainingNotes() {
  if (!reportData) return;
  
  const container = document.getElementById('training-notes-container');
  if (!container) return;
  container.innerHTML = '';
  
  const training_notes = reportData.training_notes || [];
  
  if (training_notes.length === 0) {
    const placeholder = document.createElement('p');
    placeholder.className = 'notes-placeholder';
    placeholder.textContent = 'No training notes for this session.';
    placeholder.style.color = '#999';
    placeholder.style.fontStyle = 'italic';
    container.appendChild(placeholder);
    return;
  }

  // Structured sections: { title, body } (Training_Notes_System.md)
  const first = training_notes[0];
  if (first && typeof first === 'object' && first.title != null) {
    const sectionMap = new Map();
    training_notes.forEach(function (section) {
      sectionMap.set(section.title || '', section);
    });

    const orderedTitles = [
      'Training Camp MVP',
      'Training Camp Co-MVPs',
      'Practice Player Of The Week',
      'Practice Players Of The Week',
      'Biggest Concern',
      'Biggest Concerns',
      'Biggest Regression',
      'Most Positive Locker Room Influence',
      'Strong Cumulative Increase',
      'Concerning Progression',
      'Concerning Regression',
      'Strongest Offensive Plays',
      'Strongest Defensive Set',
      'Fast Break Readiness',
      'Press/Trap Readiness',
      'Player Energy Levels'
    ];

    orderedTitles.forEach(function (title) {
      const section = sectionMap.get(title);
      if (!section) return;
      console.log('[TRAINING REPORT][NOTES] rendering section', {
        title: section.title || '',
        body: section.body || '',
        player_id: section.player_id || null,
        player_ids: section.player_ids || [],
      });
      const wrap = document.createElement('div');
      wrap.className = 'training-note-section';
      const text = section.body != null ? String(section.body) : '';
      if (isMutedTrainingNote(text)) {
        wrap.classList.add('is-muted');
      }
      if (section.title === 'Player Energy Levels') {
        wrap.classList.add('training-note-section-wide');
      }
      const h3 = document.createElement('h3');
      h3.className = 'training-note-section-title';
      h3.textContent = section.title === 'Player Energy Levels' ? 'Miscellaneous Notes' : (section.title || '');
      const body = document.createElement('div');
      body.className = 'training-note-section-body';
      text.split('\n\n').forEach(function (para, i) {
        const p = document.createElement('p');
        p.className = 'training-note-section-p';
        p.textContent = para.trim();
        if (p.textContent) body.appendChild(p);
      });
      if (!body.children.length) {
        const p = document.createElement('p');
        p.className = 'training-note-section-p';
        p.textContent = text || 'No Significant Updates';
        body.appendChild(p);
      }
      const portraitPlayer = getTrainingNotePortraitPlayer(section, text);
      if (portraitPlayer || (
        section.title === 'Practice Player Of The Week' ||
        section.title === 'Practice Players Of The Week' ||
        section.title === 'Biggest Regression' ||
        section.title === 'Most Positive Locker Room Influence'
      )) {
        wrap.classList.add('training-note-section-with-portrait');
        const media = document.createElement('div');
        media.className = 'training-note-section-media';
        const copy = document.createElement('div');
        copy.className = 'training-note-section-copy';
        copy.appendChild(h3);
        copy.appendChild(body);
        const portrait = createTrainingNotePortrait(portraitPlayer, text);
        if (portrait) {
          media.appendChild(portrait);
        }
        media.appendChild(copy);
        wrap.appendChild(media);
      } else {
        wrap.appendChild(h3);
        wrap.appendChild(body);
      }
      container.appendChild(wrap);
    });
    return;
  }
  
  // Legacy: flat strings
  training_notes.forEach(note => {
    const noteElement = document.createElement('p');
    noteElement.className = 'training-note';
    noteElement.textContent = typeof note === 'string' ? note : JSON.stringify(note);
    container.appendChild(noteElement);
  });
}

function enhanceProjectedStartingFiveTable() {
  const table = document.querySelector('#training-projected-lineup table.training-projected-table');
  if (!table) return;
  const bodyRows = table.querySelectorAll('tbody tr');
  bodyRows.forEach((row) => {
    const posCell = row.children[0];
    const playerCell = row.children[1];
    if (posCell && !posCell.querySelector('.position-badge')) {
      const text = posCell.textContent.trim();
      posCell.textContent = '';
      const badge = document.createElement('span');
      badge.className = 'position-badge';
      badge.textContent = text || '—';
      posCell.appendChild(badge);
    }
    if (playerCell) {
      playerCell.classList.add('projected-player-name-cell');
    }
  });
}
