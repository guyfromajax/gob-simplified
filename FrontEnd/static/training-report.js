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

/**
 * The loading state. While `.is-loading` is on the host, every section is hidden and this
 * quiet skeleton stands in: the report never shows headings over empty space.
 */
const REPORT_SKELETON_HTML = '<div class="report-skeleton" aria-hidden="true">' + '<div class="rsk-col"><i class="rsk rsk-h"></i><i class="rsk rsk-line"></i><i class="rsk rsk-line"></i><i class="rsk rsk-line"></i></div>'.repeat(3) + '<i class="rsk rsk-grid"></i></div><p class="report-load-status" role="status" aria-live="polite"></p>';

function setReportLoading(loading) {
  if (!root || !root.classList) return;
  root.classList.toggle('is-loading', !!loading);
  if (loading) root.classList.remove('is-load-failed');
  root.setAttribute('aria-busy', loading ? 'true' : 'false');
}

function showReportLoadFailed() {
  if (!root || !root.classList) return;
  root.classList.remove('is-loading');
  root.classList.add('is-load-failed');
  root.setAttribute('aria-busy', 'false');
  const status = root.querySelector('.report-load-status');
  if (status) status.textContent = 'The training report did not load.';
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
    + REPORT_SKELETON_HTML
    + '<section class="training-notes-section"><h2>Notes</h2>'
    + '<div class="training-notes-container" id="training-notes-container"></div></section>'
    + '<section class="team-section"><h2>Team Report</h2>'
    + '<div class="team-attributes-grid card" id="team-attributes-grid"></div></section>'
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
  // A host page written before the skeleton existed still gets one.
  const header = root.querySelector('.report-header');
  if (header && !root.querySelector('.report-skeleton')) {
    header.insertAdjacentHTML('afterend', REPORT_SKELETON_HTML);
  }
}

function reportSignature(data) {
  try { return JSON.stringify(data); }
  catch (err) { return ''; }
}

function startTrainingReport() {
  ensureShell();
  setReportLoading(true);
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
  // Nothing outside the host to clean up.
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
  'team_chemistry': 'Chemistry',
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

/**
 * The top of the report is three cards, one kind of information each (Jamie, 2026-10-02):
 * Standouts (people), Trends (attributes and schemes), Readiness (two meters). The titles
 * below are the lookup keys the server writes into the stored report, so they can't be
 * renamed without rewriting history; the shown label comes from here instead, which means
 * a report generated last season reads with today's vocabulary.
 */
const NOTES_RISING_TITLE = 'Strong Cumulative Increase';
// In season the second list is what the team lost ground in. Camp skips decay, so nothing
// falls: that list is what camp under-developed, and it says so.
const NOTES_FALLING_LABEL = 'Falling';
const NOTES_CAMP_FALLING_LABEL = 'Lagging';
const NOTES_SCHEME_ROWS = [
  { title: 'Strongest Defensive Set', label: 'Strongest Defensive Set' },
  { title: 'Strongest Offensive Plays', label: 'Strongest Offensive Plays' },
];
const NOTES_READINESS_ROWS = [
  { key: 'fast-break', title: 'Fast Break Readiness', label: 'Fast Break' },
  // The measure is "P/T Defense" everywhere (Styleguide, display text); the stored key is older.
  { key: 'press-traps', title: 'Press/Trap Readiness', label: 'P/T Defense' },
];
// The server's five words on a three-step meter: the word beside it carries "Very".
const READINESS_STEPS = 3;
const READINESS_LEVEL = { 'very weak': 1, 'weak': 1, 'neutral': 2, 'strong': 3, 'very strong': 3 };
// CH is a hidden attribute: it is never named on the report, whatever a stored note says.
const NOTES_HIDDEN_ATTRIBUTES = ['CH'];

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

// Leaving the page cancels the report's fetch. That is the player moving on, not
// a failure, so it shows nothing. beforeunload comes first (the fetch is cancelled
// after it); the timer clears the flag if the page was not left after all.
let reportPageLeaving = false;
let reportLeaveWatchInstalled = false;
function watchReportPageLeave() {
  if (reportLeaveWatchInstalled || typeof window === 'undefined') return;
  reportLeaveWatchInstalled = true;
  window.addEventListener('beforeunload', () => {
    reportPageLeaving = true;
    setTimeout(() => { reportPageLeaving = false; }, 3000);
  });
  window.addEventListener('pagehide', () => { reportPageLeaving = true; });
  window.addEventListener('pageshow', () => { reportPageLeaving = false; });
}

async function loadTrainingReport() {
  watchReportPageLeave();
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
    setReportLoading(false);
  } catch (error) {
    if (reportPageLeaving || (error && error.name === 'AbortError')) return;
    console.error('Error loading training report:', error);
    // A real failure is the inline card, never a browser alert. A report that is
    // already on screen stays: a failed refresh does not take it away.
    if (!reportData) showReportLoadFailed();
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

/**
 * The attributes a Rising / Falling note names, as display labels. A muted note ("No
 * Significant Updates") is an empty list. Hidden attributes are dropped here, so an old
 * stored report cannot put one on the page.
 */
function noteAttributeLabels(text) {
  const normalized = String(text || '').trim();
  if (!normalized || isMutedTrainingNote(normalized) || /^none$/i.test(normalized)) return [];
  return normalized
    .split(',')
    .map((token) => String(token || '').trim())
    .filter((token) => token && !NOTES_HIDDEN_ATTRIBUTES.includes(token.toUpperCase()))
    .map((token) => formatNoteAttributeToken(token))
    .filter(Boolean);
}

/** A note's text, or '' when it has nothing to say. */
function noteText(section) {
  const text = String((section && section.body) || '').trim();
  return (isMutedTrainingNote(text) || /^none$/i.test(text)) ? '' : text;
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
      // Current attribute values only; movement lives on Training Changes.
      attributeList.forEach(attr => {
        let value;
        if (attr === 'NG' || attr === 'EM' || attr === 'MO') {
          value = player.attributes[attr] || (attr === 'NG' ? 1.0 : attr === 'EM' ? 50 : 0);
        } else {
          value = window.GOB_AttributeDisplay.rawAttr(player.attributes, attr);
          if (value == null) value = 0;
        }
        row.appendChild(createAttributeCell(attr, value));
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

function createAttributeCell(attr, value) {
  const td = document.createElement('td');
  td.className = 'attribute-value-cell';

  // Special handling for NG, EM, MO
  if (attr === 'NG') {
    // Display with 2 decimal places
    td.textContent = typeof value === 'number' ? value.toFixed(2) : '1.00';
  } else if (attr === 'EM') {
    // Display with emoji
    const emoji = getEmotionEmoji(value);
    td.innerHTML = emoji;
    td.style.fontSize = 'var(--fs-24)';
    td.style.textAlign = 'center';
  } else if (attr === 'MO') {
    // Display with red/green pill (no integer on top)
    const pillContainer = createMomentumPill(value);
    td.appendChild(pillContainer);
    td.style.padding = 'var(--spacing-xs)';
  } else {
    const displayValue = window.GOB_AttributeDisplay.displayAttr(value);
    td.textContent = String(displayValue == null ? 0 : displayValue);
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
 * Map a training delta to a mark. Exactly 0 is a dash in every week. Otherwise two
 * scales by report week, and they differ:
 *
 * CAMP (week 1) — symmetric bands:
 *   0<|n|<2 → 1 · 2≤|n|≤5 → 2 · |n|>5 → 3
 *
 * IN-SEASON (weeks 2–26) — a single arrow follows the sign; the two- and three-arrow
 * bands are asymmetric (in-season decay makes small negatives normal):
 *   n ≥ 3           → 3 up
 *   1.0 ≤ n < 3     → 2 up
 *   0 < n < 1.0     → 1 up
 *   −1.5 < n < 0    → 1 down
 *   −2.5 < n ≤ −1.5 → 2 down
 *   n ≤ −2.5        → 3 down
 *
 * Tone (Jamie, 2026-10-02; Styleguide "Training movement marks"):
 *   in season: one up faint green · one down faint red · two up green · three up blue ·
 *   two or three down red.
 *   camp: one up neutral · two up green · three up blue · any down red.
 *
 * `text` is the arrow form (Team Report, Training Changes, Playbook Summary).
 */
function describeTrainingChange(change) {
  const n = Number(change);
  if (!Number.isFinite(n)) {
    return { text: '–', className: 'change-zero', tone: 'flat', direction: 0, count: 0 };
  }
  const camp = getReportWeekNumber() === 1;
  const mark = (direction, count) => {
    let tone;
    if (direction > 0) tone = count >= 3 ? 'elite' : count === 2 ? 'up' : (camp ? 'neutral' : 'up-faint');
    else tone = (!camp && count === 1) ? 'down-faint' : 'down';
    return {
      text: (direction > 0 ? '▲' : '▼').repeat(count),
      className: (direction > 0 ? 'change-delta' : 'change-negative') + ' tr-tone-' + tone,
      tone: tone,
      direction: direction,
      count: count,
    };
  };

  // Exactly 0 is a grey dash, camp or in season.
  if (n === 0) return { text: '–', className: 'change-zero', tone: 'flat', direction: 0, count: 0 };

  // Camp (week 1): symmetric 0/2/5 bands.
  if (camp) {
    const abs = Math.abs(n);
    return mark(n > 0 ? 1 : -1, abs > 5 ? 3 : abs >= 2 ? 2 : 1);
  }

  // In-season (weeks 2–26): the arrow's direction is the sign of the change.
  if (n > 0) return mark(1, n >= 3 ? 3 : n >= 1 ? 2 : 1);
  return mark(-1, n <= -2.5 ? 3 : n <= -1.5 ? 2 : 1);
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

function createChangeCell(change) {
  const td = document.createElement('td');
  const arrow = describeTrainingChange(change);
  td.textContent = arrow.text;
  td.className = arrow.className;
  if (Number(change) !== 0) td.classList.add('is-delta');
  td.setAttribute('aria-label', `Training change ${change > 0 ? '+' : ''}${change}`);
  return td;
}

/**
 * Team Report: the eleven team attributes in the four columns of Team > Team Attributes,
 * read down: Shooting, Rebounding, Chemistry; Offense, Defense, Discipline; Fast Break,
 * Fast Break Defense, Fight; P/T Offense, P/T Defense. Emitted row-major, so a four-column
 * grid puts each list in one column. Momentum is not a Team Report measure.
 */
const TEAM_REPORT_GRID_ROWS = [
  ['shot_threshold', 'offensive_efficiency', 'fb_efficiency', 'pt_opp_modifier'],
  ['rebound_modifier', 'defensive_efficiency', 'fb_opp_modifier', 'pt_efficiency'],
  ['team_chemistry', 'discipline', 'fight'],
];

function renderTeamAttributes() {
  if (!reportData) return;
  
  const grid = byId('team-attributes-grid');
  grid.innerHTML = '';
  
  const teamAttrs = reportData.team_attributes || {};
  const teamChanges = reportData.team_changes || {};

  TEAM_REPORT_GRID_ROWS.forEach((row, rowIndex) => {
    row.forEach((attrKey, colIndex) => {
      const item = createTeamAttrItem(attrKey, teamAttrs[attrKey], teamChanges[attrKey]);
      if (!item) return;
      item.dataset.attr = attrKey;
      item.style.gridRow = String(rowIndex + 1);
      item.style.gridColumn = String(colIndex + 1);
      grid.appendChild(item);
    });
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
    changeSpan.setAttribute('aria-label', (arrow.direction > 0 ? 'Up ' : 'Down ') + arrow.count);
    item.classList.add('is-delta');
  } else {
    // No movement is a quiet dash, never the words: what moved is what stands out.
    changeSpan.textContent = '–';
    changeSpan.className += ' change-zero';
    changeSpan.setAttribute('aria-label', 'No change');
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
  
  // Offense sub-sections: Motion, then set plays by where the shot comes from.
  const motion_plays = [];
  const set_by_focus = { inside: [], attack: [], outside: [], other: [] };

  for (const [play_name, play_data] of Object.entries(plays_data)) {
    if (typeof play_data === 'object' && play_data !== null) {
      const play_type = play_data.play_type || '';
      if (play_type === 'motion') {
        motion_plays.push(buildTrainingReportPlayEntry(play_name, play_data));
      } else if (play_type === 'set_play') {
        // A set play with no recognised focus is still listed, in its own column.
        const focus = String(play_data.play_focus || '').toLowerCase();
        const bucket = (focus === 'inside' || focus === 'attack' || focus === 'outside') ? focus : 'other';
        set_by_focus[bucket].push(buildTrainingReportPlayEntry(play_name, play_data));
      }
    }
  }

  const byName = (a, b) => a.name.localeCompare(b.name);
  motion_plays.sort(byName);
  Object.keys(set_by_focus).forEach((focus) => set_by_focus[focus].sort(byName));

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
  
  const playChange = (item) => getTrainingReportPlayChange(plays_changes, item);
  const defenseChange = (item) => getTrainingReportDefenseChange(defenses_changes, item);
  const panels = document.createElement('div');
  panels.className = 'pbs-panels';
  const offenseGroups = [
    { title: 'Motion', items: motion_plays, change: playChange },
    { title: 'Inside Set Plays', items: set_by_focus.inside, change: playChange },
    { title: 'Attack Set Plays', items: set_by_focus.attack, change: playChange },
    { title: 'Outside Set Plays', items: set_by_focus.outside, change: playChange },
  ];
  if (set_by_focus.other.length) {
    offenseGroups.push({ title: 'Other Set Plays', items: set_by_focus.other, change: playChange });
  }
  panels.appendChild(createPlaybookSummaryPanel('Offense', 'offense', offenseGroups));
  panels.appendChild(createPlaybookSummaryPanel('Defense', 'defense', [
    { title: 'Man', items: man_defenses, change: defenseChange },
    { title: 'Zone', items: zone_defenses, change: defenseChange },
  ]));
  container.appendChild(panels);
}

/** One side of the playbook: a titled panel whose sub-sections sit side by side. */
function createPlaybookSummaryPanel(title, key, groups) {
  const panel = document.createElement('section');
  panel.className = 'pbs-panel pbs-panel--' + key;
  panel.setAttribute('aria-label', title);
  const heading = document.createElement('h3');
  heading.className = 'pbs-panel-title';
  heading.textContent = title;
  panel.appendChild(heading);
  const cols = document.createElement('div');
  cols.className = 'pbs-cols';
  groups.forEach(function (group) {
    cols.appendChild(createPlaybookSummaryGroup(group));
  });
  panel.appendChild(cols);
  return panel;
}

/** One sub-section: name, CMD and this week's movement for each play. */
function createPlaybookSummaryGroup(group) {
  const col = document.createElement('div');
  col.className = 'pbs-group';
  const head = document.createElement('div');
  head.className = 'pbs-group-head';
  const name = document.createElement('h4');
  name.textContent = group.title;
  const cmdHead = document.createElement('span');
  cmdHead.textContent = 'CMD';
  head.appendChild(name);
  head.appendChild(cmdHead);
  col.appendChild(head);

  const items = group.items || [];
  if (!items.length) {
    const empty = document.createElement('p');
    empty.className = 'pbs-empty';
    empty.textContent = 'None in the playbook.';
    col.appendChild(empty);
    return col;
  }
  const list = document.createElement('ul');
  list.className = 'pbs-list';
  items.forEach(function (item) {
    const change = group.change(item);
    const row = document.createElement('li');
    row.className = 'pbs-row';
    const label = document.createElement('span');
    label.className = 'pbs-name';
    label.textContent = item.display_name || item.name || '';
    const cmd = document.createElement('span');
    cmd.className = 'pbs-cmd';
    const effectiveness = item && typeof item.effectiveness === 'number' ? item.effectiveness : null;
    cmd.textContent = effectiveness == null ? '—' : String(effectiveness);
    const delta = document.createElement('span');
    const described = describeTrainingChange(change);
    delta.className = 'pbs-delta ' + described.className;
    delta.textContent = described.text;
    delta.setAttribute('aria-label', 'Training change ' + (change > 0 ? '+' : '') + change);
    row.appendChild(label);
    row.appendChild(cmd);
    row.appendChild(delta);
    list.appendChild(row);
  });
  col.appendChild(list);
  return col;
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

/** A shared card (`.card`, gob-components.css) with its title. */
function createNotesCard(key, title) {
  const card = document.createElement('article');
  card.className = 'card tr-card tr-card--' + key;
  card.dataset.card = key;
  const head = document.createElement('div');
  head.className = 'card-h';
  const heading = document.createElement('h3');
  heading.textContent = title;
  head.appendChild(heading);
  card.appendChild(head);
  return card;
}

/** One label with its value directly under it. `value` is text or a node. */
function createNotesPair(labelText, value, extraClass) {
  const pair = document.createElement('div');
  pair.className = 'tr-pair' + (extraClass ? ' ' + extraClass : '');
  const label = document.createElement('div');
  label.className = 'tr-label';
  label.textContent = labelText;
  const body = document.createElement('div');
  body.className = 'tr-value';
  if (value && value.nodeType) body.appendChild(value);
  else body.textContent = String(value == null ? '' : value);
  pair.appendChild(label);
  pair.appendChild(body);
  return pair;
}

/** Standouts: the three people, headshot beside the label and the name under it. */
function buildStandoutsCard(sectionMap) {
  const card = createNotesCard('standouts', 'Standouts');
  const list = document.createElement('div');
  list.className = 'tr-standouts';

  NOTES_HERO_CONFIG.forEach((config) => {
    const { section } = resolveHeroNoteSection(config, sectionMap);
    const text = section.body != null ? String(section.body).trim() : '';
    const muted = isMutedTrainingNote(text) || /^none$/i.test(text);
    const player = muted ? null : getTrainingNotePortraitPlayer(section, text);
    const displayName = muted ? 'No Significant Updates' : (getTrainingReportPlayerName(player) || text || 'No Significant Updates');

    const row = document.createElement('div');
    row.className = 'training-notes-hero-card tr-standout';
    row.dataset.standout = config.key;
    if (muted) row.classList.add('is-muted');

    row.appendChild(createNotesHeroPortrait(player, displayName, config, muted));

    const copy = document.createElement('div');
    copy.className = 'training-notes-hero-copy tr-pair';
    const label = document.createElement('div');
    label.className = 'training-notes-hero-label tr-label';
    label.textContent = config.key === 'locker' ? config.label : section.title || config.label;
    copy.appendChild(label);

    const value = document.createElement('div');
    value.className = 'tr-value tr-standout-value';
    const name = document.createElement('span');
    name.className = 'training-notes-hero-name';
    name.textContent = displayName;
    value.appendChild(name);
    if (!muted && player) {
      const meta = document.createElement('span');
      meta.className = 'training-notes-hero-meta';
      const position = getPlayerDisplayPosition(player);
      const year = getTrainingReportPlayerYear(player);
      meta.textContent = year ? `${position} · ${year}` : position;
      value.appendChild(meta);
    }
    copy.appendChild(value);
    row.appendChild(copy);
    list.appendChild(row);
  });

  card.appendChild(list);
  return card;
}

/** Rising / Falling: short tagged attributes, each behind the faint arrow of its direction. */
function createTrendTags(labels, direction) {
  if (!labels.length) {
    const none = document.createElement('span');
    none.className = 'tr-none';
    none.textContent = 'No Significant Updates';
    return none;
  }
  const tags = document.createElement('span');
  tags.className = 'tr-tags';
  labels.forEach((text) => {
    const tag = document.createElement('span');
    tag.className = 'tr-tag';
    const arrow = document.createElement('i');
    arrow.className = direction > 0 ? 'tr-tone-up-faint' : 'tr-tone-down-faint';
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = direction > 0 ? '▲' : '▼';
    tag.appendChild(arrow);
    tag.appendChild(document.createTextNode(text));
    tags.appendChild(tag);
  });
  return tags;
}

/** Trends: what the team's attributes did, then its strongest schemes. */
function buildTrendsCard(sectionMap) {
  const card = createNotesCard('trends', 'Trends');
  const camp = isTrainingCampReportNotes(sectionMap);

  // Rising and Falling share one small grid, so their tags start on the same line.
  const trends = document.createElement('div');
  trends.className = 'tr-trend-list';
  card.appendChild(trends);

  const rising = noteAttributeLabels((sectionMap.get(NOTES_RISING_TITLE) || {}).body);
  const risingPair = createNotesPair('Rising', createTrendTags(rising, 1), 'tr-trend');
  risingPair.dataset.trend = 'rising';
  trends.appendChild(risingPair);

  const falling = noteAttributeLabels((sectionMap.get(getConcerningTeamAttrNoteTitle(sectionMap)) || {}).body);
  const fallingPair = createNotesPair(
    camp ? NOTES_CAMP_FALLING_LABEL : NOTES_FALLING_LABEL, createTrendTags(falling, -1), 'tr-trend'
  );
  fallingPair.dataset.trend = 'falling';
  trends.appendChild(fallingPair);

  NOTES_SCHEME_ROWS.forEach((row) => {
    const text = noteText(sectionMap.get(row.title));
    let value = text;
    if (!text) {
      value = document.createElement('span');
      value.className = 'tr-none';
      value.textContent = 'No Significant Updates';
    }
    const pair = createNotesPair(row.label, value, 'tr-scheme');
    pair.dataset.scheme = row.title;
    card.appendChild(pair);
  });
  return card;
}

/** A small stepped meter: `level` of `steps` lit. Neutral colours; the word says the rest. */
function createReadinessMeter(level, steps, word) {
  const meter = document.createElement('span');
  meter.className = 'tr-meter';
  meter.dataset.level = String(level);
  meter.dataset.steps = String(steps);
  meter.setAttribute('role', 'img');
  meter.setAttribute('aria-label', word);
  for (let i = 1; i <= steps; i += 1) {
    const step = document.createElement('i');
    if (i <= level) step.className = 'on';
    meter.appendChild(step);
  }
  return meter;
}

/** Readiness: Fast Break and P/T Defense, a meter with the word beside it. */
function buildReadinessCard(sectionMap) {
  const card = createNotesCard('readiness', 'Readiness');
  NOTES_READINESS_ROWS.forEach((row) => {
    const word = String((sectionMap.get(row.title) || {}).body || '').trim() || 'Neutral';
    const level = READINESS_LEVEL[word.toLowerCase()] || 0;
    const value = document.createElement('span');
    value.className = 'tr-ready';
    if (level) value.appendChild(createReadinessMeter(level, READINESS_STEPS, word));
    const text = document.createElement('span');
    text.className = 'tr-ready-word';
    text.textContent = word;
    value.appendChild(text);
    const pair = createNotesPair(row.label, value, 'tr-readiness');
    pair.dataset.ready = row.key;
    pair.dataset.word = word;
    card.appendChild(pair);
  });
  return card;
}

function renderTrainingNotes() {
  if (!reportData) return;
  
  const container = byId('training-notes-container');
  if (!container) return;
  container.innerHTML = '';
  
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

    const cards = document.createElement('div');
    cards.className = 'tr-cards';
    cards.appendChild(buildStandoutsCard(sectionMap));
    cards.appendChild(buildTrendsCard(sectionMap));
    cards.appendChild(buildReadinessCard(sectionMap));
    container.appendChild(cards);

    // Misc carries the week's energy notes. With nothing to say there is no row.
    const miscText = noteText(sectionMap.get('Player Energy Levels'));
    if (miscText) {
      const misc = createNotesPair('Misc', miscText, 'training-notes-misc-row tr-misc');
      container.appendChild(misc);
    }
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
