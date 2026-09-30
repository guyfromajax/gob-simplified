function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

// Training Report Page JavaScript

function playSound(filename) {
  import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(filename, 0.7); }).catch(function () {});
}

let root = null;
let mode = '';
let franchiseId = '';
let teamId = '';
let week = NaN;
let reportFrom = 'training';
let reportData = null;
let currentView = 'changes';
let projectedLineupView = 'attributes';
let lastSignature = '';
let togglesWired = false;
let backClickWired = false;
let loadSeq = 0;

const TOOLTIP_ID = 'training-report-attr-tooltip';

function byId(id) {
  if (!root) return null;
  if (root.id === id) return root;
  return root.querySelector('#' + id);
}

function qsa(sel) {
  return root ? root.querySelectorAll(sel) : [];
}

function inAppShell() {
  if (document.documentElement.classList.contains('gob-focus')) return true;
  return !!(root && (root.id === 'training-report-view' || (root.closest && root.closest('#training-report-view'))));
}

function readOptions(options) {
  options = options || {};
  let bag;
  try { bag = liveParams(); }
  catch (err) { bag = window.FranchiseContext && window.FranchiseContext.createParams ? window.FranchiseContext.createParams() : { get: function () { return ''; } }; }
  function pick(name, alt) {
    if (options[name] != null && options[name] !== '') return String(options[name]);
    return bag.get(name) || bag.get(alt) || '';
  }
  mode = pick('mode') || 'franchise';
  franchiseId = pick('franchiseId', 'franchise_id');
  teamId = pick('teamId', 'team_id');
  const weekRaw = pick('week');
  week = parseInt(weekRaw, 10);
  if (!Number.isFinite(week)) {
    try {
      const fromCtx = parseInt(franchiseCtx().get('week') || '', 10);
      if (Number.isFinite(fromCtx)) week = fromCtx;
    } catch (err) { /* keep NaN */ }
  }
  const fromRaw = pick('from');
  const originRaw = pick('origin');
  reportFrom = (fromRaw === 'news' || fromRaw === 'inbox')
    ? 'news'
    : (fromRaw === 'office' || originRaw === 'office') ? 'office' : 'training';
}

function shellHtml() {
  return (
    '<div class="training-report-container resource-page-container fcc-brand-page-shell training-report-resource-shell">'
    + '<header class="report-header"><div class="header-left">'
    + '<h1 class="page-title">Training Report</h1>'
    + '<div class="header-meta-row"><div class="header-meta-line">'
    + '<span><span id="week-label">Week:</span> <span id="week-number">--</span></span>'
    + '<span class="meta-sep">·</span>'
    + '<span>Upcoming Opponent: <span id="upcoming-opponent">--</span></span>'
    + '<span class="meta-sep">·</span>'
    + '<span>Training Focus: <span id="training-focus">--</span></span>'
    + '</div></div></div>'
    + '<a href="#" role="button" id="locker-room-btn" class="locker-room-button">Go To Locker Room</a>'
    + '</header>'
    + '<section class="training-notes-section"><div class="training-notes-header"><div class="training-notes-header-main">'
    + '<div class="training-notes-header-accent" aria-hidden="true"></div>'
    + '<div class="training-notes-header-copy"><h2>Notes</h2>'
    + '<div id="training-notes-brief" class="training-notes-brief">Week -- Training Brief · For Coaching Staff Only</div>'
    + '</div></div></div>'
    + '<div class="training-notes-rule" aria-hidden="true"></div>'
    + '<div class="training-notes-container" id="training-notes-container"></div></section>'
    + '<section class="team-section"><h2>Team Report</h2>'
    + '<div class="team-attributes-grid" id="team-attributes-grid"></div></section>'
    + '<section class="players-section"><div class="section-header"><h2>Player Report</h2>'
    + '<div class="view-toggle">'
    + '<button type="button" class="toggle-btn" data-view="attributes">Attributes</button>'
    + '<button type="button" class="toggle-btn active" data-view="changes">Training Changes</button>'
    + '</div></div><div class="scroll-x"><table class="players-table" id="players-table">'
    + '<thead id="players-thead"></thead><tbody id="players-tbody"></tbody></table></div></section>'
    + '<section class="projected-lineup-section"><div class="section-header projected-lineup-header">'
    + '<h2>Projected Starting 5</h2>'
    + '<div class="view-toggle projected-lineup-toggle" role="group" aria-label="Projected lineup columns">'
    + '<button type="button" class="toggle-btn active" data-projected-view="attributes">Attributes</button>'
    + '<button type="button" class="toggle-btn" data-projected-view="stats">Stats</button>'
    + '</div></div><div class="scroll-x">'
    + '<div id="training-projected-lineup" class="training-projected-lineup-wrap"></div></div></section>'
    + '<section class="playbook-summary-section"><h2>Playbook Summary</h2>'
    + '<div class="playbook-summary-container" id="playbook-summary-container"></div></section>'
    + '</div>'
  );
}

function ensureShell() {
  if (!root) return;
  if (!root.querySelector('.training-report-container')) {
    root.insertAdjacentHTML('beforeend', shellHtml());
  }
}

function reportSignature(data) {
  try { return JSON.stringify(data); }
  catch (err) { return ''; }
}

function startTrainingReport() {
  ensureShell();
  setupViewToggle();
  setupProjectedLineupToggle();
  paintBack();
  return loadTrainingReport();
}

function revalidate(options) {
  readOptions(options);
  paintBack();
  return loadTrainingReport();
}

function teardown() {
  const tip = document.getElementById(TOOLTIP_ID);
  if (tip) tip.remove();
}

function init(host, options) {
  root = host || document.body;
  if (root.classList) root.classList.add('training-report-page');
  togglesWired = false;
  backClickWired = false;
  lastSignature = '';
  reportData = null;
  currentView = 'changes';
  projectedLineupView = 'attributes';
  readOptions(options);
  if (!mode || !teamId) {
    console.error('Missing required URL parameters: mode and team_id are required');
    return Promise.resolve({ revalidate: revalidate, unmount: teardown });
  }
  if (mode === 'franchise' && !week) {
    console.error('Missing required URL parameter: week is required for franchise mode');
  }
  return startTrainingReport().then(function () {
    return { revalidate: revalidate, unmount: teardown };
  });
}

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
  'fb_efficiency': 'Fast Break',
  'pt_efficiency': 'P/T Defense',
  'fight': 'Fight',
  'discipline': 'Discipline',
  'momentum_score': 'Momentum',
  'team_chemistry': 'Team Chemistry',
  'fb_opp_modifier': 'Fast Break Defense',
  'pt_opp_modifier': 'P/T Offense'
};

const NOTE_ATTRIBUTE_LABELS = {
  SC: 'Scoring (SC)',
  SH: 'Shooting (SH)',
  ID: 'Inside Defense (ID)',
  OD: 'Outside Defense (OD)',
  PS: 'Passing (PS)',
  BH: 'Ball Handling (BH)',
  RB: 'Rebounding (RB)',
  ST: 'Strength (ST)',
  AG: 'Agility (AG)',
  FT: 'Free Throws (FT)',
  ND: 'Endurance (ND)',
  IQ: 'Basketball IQ (IQ)',
  NG: 'Energy (NG)',
  EM: 'Emotion (EM)',
};

const NOTES_HERO_CONFIG = [
  {
    key: 'practice',
    titles: ['Practice Player Of The Week', 'Practice Players Of The Week'],
    label: 'Practice Player Of The Week',
    accent: 'var(--text-100)',
    accentBorder: 'var(--line-strong)',
    accentTint: 'var(--white-6)',
  },
  {
    key: 'regression',
    titles: ['Biggest Regression'],
    label: 'Biggest Regression',
    accent: 'var(--red)',
    accentBorder: 'color-mix(in srgb, var(--red) 35%, transparent)',
    accentTint: 'color-mix(in srgb, var(--red) 12%, transparent)',
  },
  {
    key: 'locker',
    titles: ['Most Positive Locker Room Influence'],
    label: 'Most Positive Locker Room Influence',
    accent: 'var(--text-100)',
    accentBorder: 'var(--line-strong)',
    accentTint: 'var(--white-6)',
  }
];

/** In-season tactical row title; camp week uses Concerning Progression (see training_notes.py). */
const NOTES_TACTICAL_ORDER_BASE = [
  'Strong Cumulative Increase',
  'Strongest Defensive Set',
  'Strongest Offensive Plays',
  'Fast Break Readiness',
  'Press/Trap Readiness',
];

/**
 * These titles are the lookup keys the server writes into the stored report, so they can't
 * be renamed without rewriting history. The shown name comes from here instead, which means
 * a report generated last season reads with today's vocabulary.
 */
const NOTES_TACTICAL_DISPLAY_TITLES = {
  'Press/Trap Readiness': 'P/T Defense Readiness',
};

function notesTacticalDisplayTitle(title) {
  return NOTES_TACTICAL_DISPLAY_TITLES[title] || title;
}

function getConcerningTeamAttrNoteTitle(sectionMap) {
  if (sectionMap.has('Concerning Progression')) return 'Concerning Progression';
  return 'Concerning Regression';
}

function isTrainingCampReportNotes(sectionMap) {
  return (
    sectionMap.has('Concerning Progression') ||
    sectionMap.has('Training Camp MVP') ||
    sectionMap.has('Training Camp Co-MVPs')
  );
}

function resolveHeroNoteSection(config, sectionMap) {
  const isCamp = isTrainingCampReportNotes(sectionMap);
  let order;
  if (config.key === 'practice') {
    order = isCamp
      ? [
          'Training Camp MVP',
          'Training Camp Co-MVPs',
          'Practice Player Of The Week',
          'Practice Players Of The Week',
        ]
      : [
          'Practice Player Of The Week',
          'Practice Players Of The Week',
          'Training Camp MVP',
          'Training Camp Co-MVPs',
        ];
  } else if (config.key === 'regression') {
    order = isCamp
      ? ['Biggest Concern', 'Biggest Concerns', 'Biggest Regression']
      : ['Biggest Regression', 'Biggest Concern', 'Biggest Concerns'];
  } else {
    order = config.titles;
  }
  const section =
    order.map((t) => sectionMap.get(t)).find(Boolean) || {
      title: order[0],
      body: 'No Significant Updates',
    };
  return { section, order };
}

function buildNotesTacticalOrder(sectionMap) {
  const concerning = getConcerningTeamAttrNoteTitle(sectionMap);
  return [NOTES_TACTICAL_ORDER_BASE[0], concerning, ...NOTES_TACTICAL_ORDER_BASE.slice(1)];
}

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


function setupProjectedLineupToggle() {
  const buttons = qsa('.projected-lineup-toggle .toggle-btn');
  if (!buttons.length || buttons[0].dataset.wired === '1') return;
  buttons[0].dataset.wired = '1';
  buttons.forEach((b) => {
    if (b.getAttribute('data-projected-view') === projectedLineupView) b.classList.add('active');
    else b.classList.remove('active');
  });
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      playSound('SFX_SELECT');
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
    case 'MIN':
      return String(Math.round(num(s.MIN)));
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
  const el = byId('training-projected-lineup');
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
  const toggleButtons = qsa('.players-section .view-toggle .toggle-btn');
  if (!toggleButtons.length) return;
  toggleButtons.forEach(b => {
    if (b.dataset.view === currentView) b.classList.add('active');
    else b.classList.remove('active');
  });
  if (toggleButtons[0].dataset.wired === '1') return;
  toggleButtons[0].dataset.wired = '1';
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      playSound('SFX_SELECT');
      toggleButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentView = btn.dataset.view;
      renderPlayersTable();
    });
  });
}

function newsHref() {
  const bag = emptyParams();
  if (franchiseId) bag.set('franchise_id', franchiseId);
  if (teamId) bag.set('team_id', teamId);
  if (mode) bag.set('mode', mode);
  bag.set('tab', 'news-view');
  bag.delete('story');
  return '/franchise-command-center.html?' + bag.toString();
}

function ensureNewsUpLink() {
  const feed = newsHref();
  let link = byId('back-button');
  if (link) {
    link.hidden = false;
    link.href = feed;
    link.setAttribute('data-gob-up', feed);
    return;
  }
  const notes = root.querySelector('.training-notes-section');
  if (!notes || !notes.parentNode) return;
  link = document.createElement('a');
  link.className = 'gob-dt-up';
  link.id = 'back-button';
  link.href = feed;
  link.setAttribute('data-gob-up', feed);
  link.textContent = '← News';
  notes.parentNode.insertBefore(link, notes);
}

function paintBack() {
  const btn = byId('locker-room-btn');
  if (!btn) return;

  const news = byId('back-button');
  if (news) news.hidden = true;
  btn.hidden = false;
  btn.style.display = '';
  btn.textContent = reportFrom === 'training' ? 'Continue to Office' : 'Back to Locker Room';
  btn.className = 'gob-btn gob-btn--ghost';

  btn.dataset.exitWired = '1';
  if (backClickWired) return;
  backClickWired = true;
  btn.addEventListener('click', (ev) => {
    if (ev && typeof ev.preventDefault === 'function') ev.preventDefault();
    playSound('SFX_SELECT');
    if (mode === 'franchise') {
      if (reportFrom === 'news') {
        const lockerRoomUrl = (typeof buildFranchiseLockerRoomUrl === 'function')
          ? buildFranchiseLockerRoomUrl(franchiseId, teamId, { tab: 'news-view' })
          : `/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}&tab=news-view`;
        if (window.GOBNav && window.GOBNav.exitFlow) window.GOBNav.exitFlow(lockerRoomUrl);
        else if (window.GOBNav) window.GOBNav.replace(lockerRoomUrl);
        else window.location.replace(lockerRoomUrl);
        return;
      }
      const lockerRoomUrl = (typeof resolveFranchiseLockerRoomUrl === 'function')
        ? resolveFranchiseLockerRoomUrl({
            franchiseId: franchiseId,
            teamId: teamId,
            extraParams: reportFrom === 'training' ? { tut_alert: 'training_return' } : {}
          })
        : `/franchise-command-center.html?mode=franchise&franchise_id=${franchiseId}&team_id=${teamId}`
          + (reportFrom === 'training' ? '&tut_alert=training_return' : '');
      if (reportFrom !== 'training' && window.GOBNav && typeof window.GOBNav.back === 'function') {
        window.GOBNav.back(lockerRoomUrl);
        return;
      }
      if (window.GOBNav && window.GOBNav.exitFlow) window.GOBNav.exitFlow(lockerRoomUrl);
      else if (window.GOBNav) window.GOBNav.replace(lockerRoomUrl);
      else window.location.replace(lockerRoomUrl);
    }
  });
}

async function loadTrainingReport() {
  try {
    const params = emptyParams();
    params.set('mode', mode);
    params.set('team_id', teamId);
    
    if (franchiseId) {
      params.set('franchise_id', franchiseId);
    }
    if (Number.isFinite(week)) {
      params.set('week', String(week));
    }
    
    const response = await fetch(`${API_CONFIG.buildUrl('/franchise/training-report')}?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to load training report: ${response.statusText}`);
    }
    
    const next = await response.json();
    const sig = reportSignature(next);
    if (sig && sig === lastSignature && reportData) return;
    reportData = next;
    lastSignature = sig;
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
  const periodLabel = 'Week';
  const periodValue = reportData.week;
  const weekNumber = byId('week-number');
  if (weekNumber) weekNumber.textContent = periodValue || '--';
  
  // Update label
  const weekLabel = byId('week-label');
  if (weekLabel) {
    weekLabel.textContent = periodLabel + ':';
  }
  
  const upcoming = byId('upcoming-opponent');
  if (upcoming) upcoming.textContent = reportData.upcoming_opponent || '--';
  
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
  
  const focusEl = byId('training-focus');
  if (focusEl) focusEl.textContent = focusText;

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
    if (
      !/Practice Player(?:s)? Of The Week/i.test(title) &&
      !/Training Camp (?:Co-)?MVPs?/i.test(title)
    ) {
      return;
    }
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
  if (window.API_CONFIG && typeof window.API_CONFIG.getPlayerImageUrl === 'function') {
    return window.API_CONFIG.getPlayerImageUrl(playerId, { size: 'card' });
  }
  return playerId ? `/images/players/${playerId}.png` : '/images/players/generic_headshot.png';
}

function getTrainingReportPlayerYear(player) {
  const raw = player?.year || player?.class_year || '';
  if (typeof GOB_PlayerYear !== 'undefined' && GOB_PlayerYear.formatDisplay) {
    return GOB_PlayerYear.formatDisplay(raw);
  }
  if (typeof yearMap !== 'undefined' && raw) {
    const abbr = yearMap[String(raw).toLowerCase()];
    if (abbr) return abbr;
  }
  const s = String(raw).trim();
  if (!s) return '';
  return s.toUpperCase();
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
    'Training Camp MVP',
    'Training Camp Co-MVPs',
    'Biggest Regression',
    'Biggest Concern',
    'Biggest Concerns',
    'Most Positive Locker Room Influence',
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

function formatNoteAttributeToken(token) {
  const trimmed = String(token || '').trim();
  if (!trimmed) return '';
  return NOTE_ATTRIBUTE_LABELS[trimmed] || trimmed;
}

function formatNoteAttributeList(text) {
  const normalized = String(text || '').trim();
  if (!normalized || isMutedTrainingNote(normalized)) return normalized || 'No Significant Updates';
  return normalized
    .split(',')
    .map((token) => formatNoteAttributeToken(token))
    .filter(Boolean)
    .join(', ');
}

function getTrainingNoteValueTone(title, body) {
  const text = String(body || '').trim();
  if (isMutedTrainingNote(text) || /^none$/i.test(text)) return 'muted';
  if (title === 'Strong Cumulative Increase') return 'positive';
  if (title === 'Concerning Regression' || title === 'Concerning Progression') return 'negative';
  return 'default';
}

function formatTrainingNoteValue(title, body) {
  if (
    title === 'Strong Cumulative Increase' ||
    title === 'Concerning Regression' ||
    title === 'Concerning Progression'
  ) {
    return formatNoteAttributeList(body);
  }
  return String(body || '').trim() || 'No Significant Updates';
}

function createNotesHeroPortrait(player, displayName, accentConfig, isMuted) {
  const wrap = document.createElement('div');
  wrap.className = 'training-notes-hero-portrait';

  if (player) {
    const img = document.createElement('img');
    img.className = 'training-notes-hero-portrait-img';
    img.src = getTrainingReportPlayerPortraitUrl(player);
    img.alt = displayName;
    img.addEventListener('error', () => {
      wrap.innerHTML = '';
      wrap.appendChild(createNotesHeroInitials(displayName, accentConfig, isMuted));
    }, { once: true });
    wrap.appendChild(img);
    return wrap;
  }

  wrap.appendChild(createNotesHeroInitials(displayName, accentConfig, isMuted));
  return wrap;
}

function createNotesHeroInitials(displayName, accentConfig, isMuted) {
  const fallback = document.createElement('div');
  fallback.className = 'training-notes-hero-portrait-fallback';
  fallback.textContent = isMuted ? 'NS' : getTrainingReportPlayerInitials(displayName);
  if (isMuted) fallback.classList.add('is-muted');
  fallback.style.setProperty('--notes-accent', accentConfig.accent);
  fallback.style.setProperty('--notes-accent-border', accentConfig.accentBorder);
  fallback.style.setProperty('--notes-accent-tint', accentConfig.accentTint);
  return fallback;
}

function displayMovementsForPlayer(player) {
  const all = (reportData && reportData.player_attribute_display_movements) || {};
  const id = player && (player.id != null ? String(player.id) : '');
  return all[id] || all[player && player.name] || {};
}

function displayMovementValue(cell) {
  if (cell && typeof cell === 'object') {
    const from = Number(cell.from);
    const to = Number(cell.to);
    if (!Number.isFinite(from) || !Number.isFinite(to) || to === from) return 0;
    return to > from ? 1 : -1;
  }
  return Number(cell) || 0;
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
  
  const thead = byId('players-thead');
  const tbody = byId('players-tbody');
  
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
        let value;
        if (attr === 'NG' || attr === 'EM' || attr === 'MO') {
          value = player.attributes[attr] || (attr === 'NG' ? 1.0 : attr === 'EM' ? 50 : 0);
        } else {
          value = window.GOB_AttributeDisplay.rawAttr(player.attributes, attr);
          if (value == null) value = 0;
        }
        const changes = reportData.player_changes[player.name] || {};
        const change = changes[attr] || 0;
        const displayMovements = displayMovementsForPlayer(player);
        const displayMovement = displayMovementValue(displayMovements[attr]);
        row.appendChild(createAttributeCell(attr, value, change, displayMovement));
      });
    } else {
      // Show changes for this player (0 if no change)
      attributeList.forEach(attr => {
        const changes = reportData.player_changes[player.name] || {};
        const change = changes[attr] || 0;
        row.appendChild(createChangeCell(change));
      });
    }

    const rt = getPlayerHighestRt(player);
    const rtCell = document.createElement('td');
    rtCell.textContent = formatRtDisplay(rt);
    if (typeof getRtBucketClass === 'function') {
      rtCell.className = getRtBucketClass(rt);
    }
    row.appendChild(rtCell);
    
    tbody.appendChild(row);
  });
  
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

function createAttributeCell(attr, value, change, displayMovement = 0) {
  const td = document.createElement('td');
  td.className = 'attribute-value-cell';

  const attachChangeTooltip = () => {
    if (!change) return;
    const arrow = describeTrainingChange(change);
    td.setAttribute('data-tooltip', arrow.text);
    td.setAttribute('data-tooltip-class', arrow.className);
    td.style.cursor = 'help';
    td.addEventListener('mouseenter', showAttributeTooltip);
    td.addEventListener('mouseleave', hideAttributeTooltip);
    td.addEventListener('mousemove', positionAttributeTooltip);
  };
  
  // Special handling for NG, EM, MO
  if (attr === 'NG') {
    // Display with 2 decimal places
    td.textContent = typeof value === 'number' ? value.toFixed(2) : '1.00';
    attachChangeTooltip();
  } else if (attr === 'EM') {
    // Display with emoji
    const emoji = getEmotionEmoji(value);
    td.innerHTML = emoji;
    td.style.fontSize = 'var(--fs-24)';
    td.style.textAlign = 'center';
    attachChangeTooltip();
  } else if (attr === 'MO') {
    // Display with red/green pill (no integer on top)
    const pillContainer = createMomentumPill(value);
    td.appendChild(pillContainer);
    td.style.padding = 'var(--spacing-xs)';
    attachChangeTooltip();
  } else {
    const displayValue = window.GOB_AttributeDisplay.displayAttr(value);
    td.textContent = String(displayValue == null ? 0 : displayValue);
    if (displayMovement > 0) {
      td.classList.add('attribute-display-increase');
    } else if (displayMovement < 0) {
      td.classList.add('attribute-display-decrease');
    }
    attachChangeTooltip();
  }

  markTrainingDelta(td, change);
  return td;
}

function markTrainingDelta(td, change) {
  const n = Number(change);
  if (!Number.isFinite(n) || n === 0) return;
  const arrow = describeTrainingChange(n);
  if (!arrow.text || arrow.text === '–') return;
  td.classList.add('is-delta');
  const mark = document.createElement('span');
  mark.className = 'delta-mark ' + arrow.className;
  mark.textContent = arrow.text;
  td.appendChild(mark);
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
  container.style.background = 'var(--black-25)';
  container.style.borderRadius = 'var(--radius-14)';
  container.style.overflow = 'hidden';
  
  // Center line
  const centerLine = document.createElement('div');
  centerLine.style.position = 'absolute';
  centerLine.style.left = '50%';
  centerLine.style.top = '0';
  centerLine.style.bottom = '0';
  centerLine.style.width = '2px';
  centerLine.style.background = 'var(--text-60)';
  centerLine.style.transform = 'translateX(-50%)';
  centerLine.style.zIndex = '2';
  container.appendChild(centerLine);
  
  const moValue = typeof mo === 'number' ? mo : 0;
  const maxValue = 5; // MO ranges from -5 to +5 (BackEnd MO_MAX; Player_Momentum_System.md)
  
  // Fill based on value
  if (moValue > 0) {
    const fill = document.createElement('div');
    fill.style.position = 'absolute';
    fill.style.left = '50%';
    fill.style.top = '0';
    fill.style.bottom = '0';
    fill.style.background = 'var(--green)'; /* colour-law: positive-data */
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
    fill.style.background = 'var(--red)';
    fill.style.transition = 'width 0.3s ease';
    fill.style.zIndex = '1';
    const absValue = Math.abs(moValue);
    const percentage = Math.min((absValue / maxValue) * 50, 50); // Max 50% to the left
    fill.style.width = `${percentage}%`;
    container.appendChild(fill);
  }
  
  return container;
}

/**
 * Map a training delta to arrow glyphs. Two regimes by report week (2026-08):
 *
 * CAMP (week 1) — symmetric bands, keeps the grey dash at exactly 0:
 *   0 → dash · 0<|n|<2 → 1 · 2≤|n|≤5 → 2 · |n|>5 → 3
 *
 * IN-SEASON (weeks 2–26) — asymmetric, NO dash. In-season decay makes tiny
 * negatives normal, so the "up" band absorbs small dips (down to −0.5) and reads
 * them as holding, keeping the report from screaming red on an unlucky −0.4 week:
 *   n ≥ 3          → ▲▲▲ blue
 *   1.0 ≤ n < 3    → ▲▲ green
 *   −0.5 ≤ n < 1.0 → ▲ green   (absorbs 0 and small dips)
 *   −1.5 < n < −0.5 → ▼ red    (−0.51 … −1.49)
 *   −2.5 < n ≤ −1.5 → ▼▼ red   (−1.5 … −2.49)
 *   n ≤ −2.5       → ▼▼▼ red
 * Triple-UP uses RT-elite blue; all other ups green; all downs red.
 */
function describeTrainingChange(change) {
  const n = Number(change);
  if (!Number.isFinite(n)) {
    return { text: '–', className: 'change-zero' };
  }
  const up = (count) => ({
    text: '▲'.repeat(count),
    className: 'change-delta',
  });
  const down = (count) => ({ text: '▼'.repeat(count), className: 'change-negative' });

  // Camp (week 1): symmetric 0/2/5 bands with a grey dash at exactly 0.
  if (getReportWeekNumber() === 1) {
    if (n === 0) return { text: '–', className: 'change-zero' };
    const abs = Math.abs(n);
    const count = abs > 5 ? 3 : abs >= 2 ? 2 : 1;
    return n > 0 ? up(count) : down(count);
  }

  // In-season (weeks 2–26): no dash; the up band absorbs dips down to −0.5.
  if (n >= -0.5) {
    return up(n >= 3 ? 3 : n >= 1 ? 2 : 1);
  }
  return down(n <= -2.5 ? 3 : n <= -1.5 ? 2 : 1);
}

function formatChangeForTooltip(change, attrKey = null) {
  // Team attribute tooltips still use numeric labels; player attrs use arrows.
  if (attrKey === 'rebound_modifier') {
    return change > 0 ? `+${change.toFixed(2)}` : change.toFixed(2);
  }
  if (attrKey) {
    return change > 0 ? `+${change}` : String(change);
  }
  return describeTrainingChange(change).text;
}

function showAttributeTooltip(event) {
  const cell = event.currentTarget || event.target;
  const changeText = cell.getAttribute('data-tooltip');
  if (!changeText) return;
  
  // Create tooltip element if it doesn't exist
  let tooltip = document.getElementById(TOOLTIP_ID);
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = TOOLTIP_ID;
    tooltip.className = 'attribute-tooltip';
    document.body.appendChild(tooltip);
  }

  const tone = cell.getAttribute('data-tooltip-class') || '';
  tooltip.className = 'attribute-tooltip';
  if (tone.includes('change-elite')) {
    tooltip.classList.add('attribute-tooltip-elite');
  } else if (tone.includes('change-positive')) {
    tooltip.classList.add('attribute-tooltip-positive');
  } else if (tone.includes('change-negative')) {
    tooltip.classList.add('attribute-tooltip-negative');
  } else {
    tooltip.classList.add('attribute-tooltip-zero');
  }
  
  tooltip.textContent = changeText;
  tooltip.style.display = 'block';
  positionAttributeTooltip(event);
}

function hideAttributeTooltip() {
  const tooltip = document.getElementById(TOOLTIP_ID);
  if (tooltip) {
    tooltip.style.display = 'none';
  }
}

function positionAttributeTooltip(event) {
  const tooltip = document.getElementById(TOOLTIP_ID);
  if (!tooltip || tooltip.style.display === 'none') return;
  
  const cell = event.currentTarget || event.target;
  const rect = cell.getBoundingClientRect();
  
  // Position tooltip above the cell
  tooltip.style.left = `${rect.left + rect.width / 2}px`;
  tooltip.style.top = `${rect.top - 10}px`;
  tooltip.style.transform = 'translate(-50%, -100%)';
}

function createChangeCell(change) {
  const td = document.createElement('td');
  const arrow = describeTrainingChange(change);
  td.textContent = arrow.text;
  td.className = arrow.className;
  if (Number(change) !== 0) td.classList.add('is-delta');
  td.setAttribute('aria-label', `Training change ${change > 0 ? '+' : ''}${change}`);
  return td;
}

function renderTeamAttributes() {
  if (!reportData) return;
  
  const grid = byId('team-attributes-grid');
  grid.innerHTML = '';
  
  const teamAttrs = reportData.team_attributes || {};
  const teamChanges = reportData.team_changes || {};
  
  // Team Report display list. Momentum is omitted (Jamie: same 11 as Team Attributes).
  const attrOrder = [
    'shot_threshold',
    'rebound_modifier',
    'offensive_efficiency',
    'defensive_efficiency',
    'fb_efficiency',
    'pt_efficiency',
    'fight',
    'discipline',
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
    // Shot threshold is a golf score: a lower raw value is the better direction.
    const displayDelta = attrKey === 'shot_threshold' ? -change : change;
    const arrow = describeTrainingChange(displayDelta);
    changeSpan.textContent = arrow.text;
    changeSpan.className = 'attr-change ' + arrow.className;
    item.classList.add('is-delta');
  } else {
    changeSpan.textContent = 'No change';
    changeSpan.className += ' change-zero';
  }
  
  label.appendChild(nameSpan);
  label.appendChild(changeSpan);
  item.appendChild(label);

  if (inAppShell()) return item;
  
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
    ({ maxValue, value } = window.TeamShotThresholdScale.pillFillFromRaw(originalValue));
  } else if (attrKey === 'rebound_modifier') {
    // Rebound modifier is 0.0-1.0; center = neutral = init = 0.2 (NOT the midpoint).
    // Asymmetric span: 0.2 of room below, 0.8 above. is-extreme (value/maxValue >= 0.7)
    // then triggers at 70% of whichever half-span the value is on.
    value = originalValue - 0.2;
    maxValue = value < 0 ? 0.2 : 0.8;
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
  
  const container = byId('playbook-summary-container');
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
  
  let man_defenses = [];
  let zone_defenses = [];
  if (scouting_data.defense && typeof window !== 'undefined' && window.GOBDefenseDisplay) {
    const split = window.GOBDefenseDisplay.buildPlaybookStyleDefenseRows(scouting_data.defense);
    man_defenses = split.man_defenses;
    zone_defenses = split.zone_defenses;
  } else if (scouting_data.defense) {
    for (const [defense_name, defense_data] of Object.entries(scouting_data.defense)) {
      if (typeof defense_data === 'object' && defense_data !== null) {
        const rowKey = trainingReportCanonicalDefenseRowKey(defense_name) || defense_name;
        if (defense_name === 'Man' || defense_name === 'man') {
          man_defenses.push({
            ...defense_data,
            name: defense_name === 'man' ? 'Man' : defense_name,
            defense_row_key: rowKey,
          });
        } else if (defense_name.includes('Zone') || defense_name.includes('zone')) {
          zone_defenses.push({
            ...defense_data,
            name: defense_name,
            defense_row_key: rowKey,
          });
        }
      }
    }
  }
  
  // Sort defenses by name
  man_defenses.sort((a, b) => a.name.localeCompare(b.name));
  zone_defenses.sort((a, b) => a.name.localeCompare(b.name));
  
  container.appendChild(createPlaybookSummaryTable([
    { title: 'Offense', items: motion_plays.concat(set_plays), changes: plays_changes },
    { title: 'Defense', items: man_defenses.concat(zone_defenses), changes: defenses_changes },
  ]));
}

function playSectionLabel(title, item) {
  if (title === 'Offense') {
    const kind = String(item.play_type || '');
    if (kind === 'motion') return 'Motion';
    if (kind === 'set_play' || kind === 'set') return 'Set';
  }
  if (title === 'Defense') {
    const name = String(item.name || item.display_name || '');
    if (/zone/i.test(name)) return 'Zone';
    return 'Man';
  }
  return title;
}

function createPlaybookSummaryTable(groups) {
  const table = document.createElement('table');
  table.className = 'playbook-summary-table';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['Play', 'Section', 'CMD', 'Change'].forEach(function (label) {
    const th = document.createElement('th');
    th.textContent = label;
    headRow.appendChild(th);
  });
  head.appendChild(headRow);
  table.appendChild(head);
  const body = document.createElement('tbody');
  groups.forEach(function (group) {
    (group.items || []).forEach(function (item) {
      const change = group.title === 'Offense'
        ? getTrainingReportPlayChange(group.changes, item)
        : getTrainingReportDefenseChange(group.changes, item);
      const tr = document.createElement('tr');
      const name = document.createElement('td');
      name.textContent = item.display_name || item.name || '';
      const section = document.createElement('td');
      section.textContent = playSectionLabel(group.title, item);
      const cmd = document.createElement('td');
      const effectiveness = item && typeof item.effectiveness === 'number' ? item.effectiveness : null;
      cmd.textContent = effectiveness == null ? '—' : String(effectiveness);
      const delta = document.createElement('td');
      const arrow = describeTrainingChange(change);
      delta.textContent = arrow.text;
      delta.className = arrow.className;
      if (Number(change) !== 0) delta.classList.add('is-delta');
      tr.appendChild(name);
      tr.appendChild(section);
      tr.appendChild(cmd);
      tr.appendChild(delta);
      body.appendChild(tr);
    });
  });
  if (!body.children.length) {
    const empty = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 4;
    cell.textContent = 'No data available.';
    empty.appendChild(cell);
    body.appendChild(empty);
  }
  table.appendChild(body);
  return table;
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

function trainingReportCanonicalDefenseRowKey(scoutingKey) {
  if (scoutingKey == null || scoutingKey === '') return null;
  const k = String(scoutingKey).trim();
  if (k === 'man' || k === 'Man' || k.toLowerCase() === 'base-man') return 'man';
  if (k === '2-3-zone' || k === '2-3 Zone') return '2-3-zone';
  if (k === '3-2-zone' || k === '3-2 Zone') return '3-2-zone';
  if (k === '1-3-1-zone' || k === '1-3-1 Zone') return '1-3-1-zone';
  return k;
}

/** Backend `defenses_effectiveness_changes` uses canonical row keys (`man`, `2-3-zone`); rows use display `name`. */
function getTrainingReportDefenseChange(defensesChanges, defenseItem) {
  if (!defensesChanges || !defenseItem) return 0;

  const candidates = [
    defenseItem.defense_row_key,
    trainingReportCanonicalDefenseRowKey(defenseItem.name),
    defenseItem.name,
    defenseItem.display_name
  ].filter(Boolean);

  for (const key of candidates) {
    if (Object.prototype.hasOwnProperty.call(defensesChanges, key)) {
      return normalizeTrainingReportChangeValue(defensesChanges[key]);
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
        : getTrainingReportDefenseChange(changesLookup, item);
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
  bars.appendChild(createPlaybookMetricCard('Command', effectiveness, 100, ''));
  bars.appendChild(createPlaybookMetricCard('Momentum', momentum, 10, ''));
  bars.appendChild(createPlaybookMetricCard('Cloaking', cloaking, 10, ''));
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
  const percentage = Math.min(100, (value / maxValue) * 100);
  progressFill.style.width = `${percentage}%`;

  progressBar.appendChild(progressFill);
  metricDiv.appendChild(progressBar);
  return metricDiv;
}

function renderTrainingNotes() {
  if (!reportData) return;
  
  const container = byId('training-notes-container');
  if (!container) return;
  container.innerHTML = '';
  const brief = byId('training-notes-brief');
  if (brief) {
    brief.textContent = `Week ${getReportWeekNumber() || '--'} Training Brief · For Coaching Staff Only`;
  }
  
  const training_notes = reportData.training_notes || [];
  
  if (training_notes.length === 0) {
    const placeholder = document.createElement('p');
    placeholder.className = 'notes-placeholder';
    placeholder.textContent = 'No training notes for this session.';
    if (!inAppShell()) {
      placeholder.style.color = 'var(--text-38)';
      placeholder.style.fontStyle = 'italic';
    }
    container.appendChild(placeholder);
    return;
  }

  // Structured sections: { title, body } (Training_System.md → Training Notes Section)
  const first = training_notes[0];
  if (first && typeof first === 'object' && first.title != null) {
    const sectionMap = new Map();
    training_notes.forEach(function (section) {
      sectionMap.set(section.title || '', section);
    });

    const heroGrid = document.createElement('div');
    heroGrid.className = 'training-notes-hero-grid';

    NOTES_HERO_CONFIG.forEach((config) => {
      const { section } = resolveHeroNoteSection(config, sectionMap);
      const text = section.body != null ? String(section.body).trim() : '';
      const muted = isMutedTrainingNote(text) || /^none$/i.test(text);
      const player = muted ? null : getTrainingNotePortraitPlayer(section, text);
      const displayName = muted ? 'No Significant Updates' : (getTrainingReportPlayerName(player) || text || 'No Significant Updates');
      const hero = document.createElement('article');
      hero.className = 'training-notes-hero-card';
      if (muted) hero.classList.add('is-muted');
      if (!inAppShell()) {
        hero.style.setProperty('--notes-accent', config.accent);
        hero.style.setProperty('--notes-accent-border', config.accentBorder);
        hero.style.setProperty('--notes-accent-tint', config.accentTint);
      }

      const label = document.createElement('div');
      label.className = 'training-notes-hero-label';
      label.textContent =
        config.key === 'locker' ? config.label : section.title || config.label;

      const body = document.createElement('div');
      body.className = 'training-notes-hero-body';

      const portrait = createNotesHeroPortrait(player, displayName, config, muted);
      body.appendChild(portrait);

      const copy = document.createElement('div');
      copy.className = 'training-notes-hero-copy';
      const name = document.createElement('div');
      name.className = 'training-notes-hero-name';
      name.textContent = displayName;
      copy.appendChild(name);
      const meta = document.createElement('div');
      meta.className = 'training-notes-hero-meta';
      if (!muted && player) {
        const position = getPlayerDisplayPosition(player);
        const year = getTrainingReportPlayerYear(player);
        meta.textContent = year ? `${position} · ${year}` : position;
      } else {
        meta.textContent = '';
      }
      copy.appendChild(meta);
      body.appendChild(copy);

      hero.appendChild(label);
      hero.appendChild(body);
      heroGrid.appendChild(hero);
    });

    container.appendChild(heroGrid);

    const dividerOne = document.createElement('div');
    dividerOne.className = 'training-notes-subrule';
    container.appendChild(dividerOne);

    const tacticalGrid = document.createElement('div');
    tacticalGrid.className = 'training-notes-tactical-grid';
    buildNotesTacticalOrder(sectionMap).forEach((title) => {
      const section = sectionMap.get(title) || { title, body: 'No Significant Updates' };
      const valueText = formatTrainingNoteValue(title, section.body);
      const tone = getTrainingNoteValueTone(title, section.body);
      const pill = document.createElement('div');
      pill.className = `training-notes-tactical-pill is-${tone}`;

      const label = document.createElement('div');
      label.className = 'training-notes-tactical-label';
      label.textContent = notesTacticalDisplayTitle(title);
      pill.appendChild(label);

      const value = document.createElement('div');
      value.className = 'training-notes-tactical-value';
      value.textContent = valueText;
      pill.appendChild(value);

      tacticalGrid.appendChild(pill);
    });
    container.appendChild(tacticalGrid);

    const dividerTwo = document.createElement('div');
    dividerTwo.className = 'training-notes-subrule';
    container.appendChild(dividerTwo);

    const miscSection = sectionMap.get('Player Energy Levels') || { body: 'No Significant Updates' };
    const miscText = String(miscSection.body || '').trim() || 'No Significant Updates';
    const miscRow = document.createElement('div');
    miscRow.className = 'training-notes-misc-row';
    const miscLabel = document.createElement('div');
    miscLabel.className = 'training-notes-misc-label';
    miscLabel.textContent = 'Misc';
    const miscValue = document.createElement('div');
    miscValue.className = 'training-notes-misc-value';
    miscValue.textContent = miscText;
    miscRow.appendChild(miscLabel);
    miscRow.appendChild(miscValue);
    container.appendChild(miscRow);
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
  const table = root.querySelector('#training-projected-lineup table.training-projected-table');
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

export { init, teardown, revalidate, shellHtml };
if (typeof window !== 'undefined') {
  window.GOBTrainingReport = { init: init, teardown: teardown, revalidate: revalidate, shellHtml: shellHtml };
}
