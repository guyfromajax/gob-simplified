function playSound(filename) {
  try {
    var a = new Audio('/sounds/' + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function () {});
  } catch (e) {}
}

const ALPHA_DISMISS_STORAGE_KEY = 'alpha_disclaimer_dismissed_version';
const ALPHA_DISCLAIMER_VERSION = '2026-07-22-recruiting-defenses-alpha-box';

const franchiseHomeSlots = document.getElementById('franchise-home-slots');
const alphaDisclaimer = document.getElementById('alpha-disclaimer');
const alphaDisclaimerDismiss = document.getElementById('alpha-disclaimer-dismiss');
const leaderboardHost = document.getElementById('community-leaderboard');
const communityHighlightsBody = document.querySelector('.community-highlights-body');
const aroundTheLeagueGrid = document.getElementById('around-the-league-grid');
const leaderboardGeekPointsToggle = document.getElementById('leaderboard-view-geek-points');
const leaderboardTitlesToggle = document.getElementById('leaderboard-view-titles');

// Primary/secondary from scripts/align_core8_team_colors.py (Mongo teams.primary_color / secondary_color)
const A1_CONFERENCE_TEAMS = [
  { id: 'bentley_truman', name: 'Bentley-Truman', primary: '#4066b2', secondary: '#ffffff' },
  { id: 'lancaster', name: 'Lancaster', primary: '#d24a1b', secondary: '#000000' },
  { id: 'four_corners', name: 'Four Corners', primary: '#c0976a', secondary: '#00954b' },
  { id: 'ocean_city', name: 'Ocean City', primary: '#2a2168', secondary: '#00a89d' },
  { id: 'morristown', name: 'Morristown', primary: '#ec1d28', secondary: '#cccccc' },
  { id: 'little_york', name: 'Little York', primary: '#65308e', secondary: '#f6af38' },
  { id: 'xavien', name: 'Xavien', primary: '#016837', secondary: '#999999' },
  { id: 'south_lancaster', name: 'South Lancaster', primary: '#7c2b24', secondary: '#e39649' },
];

/** Up to MAX_FRANCHISE_SLOTS franchise summaries from GET /franchise/list (newest first). */
let franchisesList = [];
let maxFranchiseSlots = 2;
/** Per franchise_id: { franchise, activeGameResume, cpuSimResume } */
const slotRuntimeById = {};
/** Pending delete confirmation target */
let pendingDeleteFranchise = null;
let currentLeaderboardData = null;
let currentLeaderboardView = 'geek_points';

// Team name → square logo filename prefix (from images/square-logos/{code}_square.png)
const TEAM_LOGO_CODE = {
  'Bentley-Truman': 'bt',
  'Four Corners': 'fc',
  'Four-Corners': 'fc',
  'Lancaster': 'lan',
  'Little York': 'ly',
  'Little-York': 'ly',
  'Morristown': 'mor',
  'Ocean City': 'oc',
  'Ocean-City': 'oc',
  'South Lancaster': 'sl',
  'South-Lancaster': 'sl',
  'Xavien': 'xav'
};

function getSquareLogoPath(teamName) {
  if (typeof getTeamAssetPath === 'function') return getTeamAssetPath(teamName, 'banner_primary');
  return '/images/teams/general/general_banner_primary.jpg';
}

function clearFranchiseLocalStorage() {
  if (window.FranchiseLS && typeof window.FranchiseLS.clearOnFranchiseExit === 'function') {
    window.FranchiseLS.clearOnFranchiseExit();
    return;
  }
  if (typeof localStorage === 'undefined') return;
  const toRemove = [
    'franchiseId',
    'franchise_id',
    'franchise_week',
    'franchise_user_team',
    'franchise_user_team_id',
    'franchise_user_team_primary_color',
    'franchise_complete_week_pending',
    'franchise_eog_pgpc_snapshot',
  ];
  toRemove.forEach((k) => localStorage.removeItem(k));
  Object.keys(localStorage).forEach((k) => {
    if (k.startsWith('playbooks_position_filters_franchise_')) localStorage.removeItem(k);
    if (k.startsWith('franchise:')) localStorage.removeItem(k);
  });
  localStorage.removeItem('last_game_id');
  localStorage.removeItem('last_box_score_gameId');
  localStorage.removeItem('last_box_score_url');
  localStorage.removeItem('last_game_user_team_side');
  localStorage.removeItem('game_home');
  localStorage.removeItem('game_away');
}

function getAuthHeaders() {
  try {
    return API_CONFIG.getAuthHeaders();
  } catch (e) {
    return {};
  }
}

function redirectToLogin() {
  try {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
  } catch (e) {}
  const redirectParam = encodeURIComponent('/mode-select.html');
  window.location.replace('/login.html?redirect=' + redirectParam);
}

function revealModeSelect() {
  if (document.body) document.body.classList.remove('mode-select-loading');
}

function safeJsonFetch(url, options) {
  return fetch(url, options)
    .then(function (response) {
      if (!response.ok) return null;
      return response.json();
    })
    .catch(function () {
      return null;
    });
}

function safeText(value, fallback) {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

function safeNumber(value, fallback) {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function deriveCurrentSeason(commandCenterData) {
  return safeNumber(commandCenterData && commandCenterData.current_season, 1);
}

function deriveRank(teamDoc, commandCenterData) {
  if (teamDoc) {
    const teamRank = teamDoc.natl_rank || teamDoc.rank || teamDoc.national_rank;
    if (teamRank !== undefined && teamRank !== null && String(teamRank).trim() !== '') {
      return String(teamRank);
    }
  }
  if (commandCenterData && commandCenterData.rank !== undefined && commandCenterData.rank !== null && commandCenterData.rank !== '-') {
    return String(commandCenterData.rank);
  }
  return '-';
}

function derivePrestige(teamDoc, commandCenterData) {
  if (commandCenterData && commandCenterData.prestige !== undefined && commandCenterData.prestige !== null && String(commandCenterData.prestige).trim() !== '') {
    return String(commandCenterData.prestige);
  }
  if (teamDoc && teamDoc.prestige !== undefined && teamDoc.prestige !== null && String(teamDoc.prestige).trim() !== '') {
    return String(teamDoc.prestige);
  }
  return '-';
}

function deriveRecord(commandCenterData, teamName) {
  const rankings = (commandCenterData && Array.isArray(commandCenterData.rankings)) ? commandCenterData.rankings : [];
  const teamEntry = rankings.find(function (entry) {
    return entry && entry.team_name === teamName;
  });
  if (!teamEntry) return '0-0';
  const wins = Number.isFinite(teamEntry.W) ? teamEntry.W : parseInt(teamEntry.W || 0, 10) || 0;
  const losses = Number.isFinite(teamEntry.L) ? teamEntry.L : parseInt(teamEntry.L || 0, 10) || 0;
  return wins + '-' + losses;
}

function deriveNextOpponent(commandCenterData, teamName) {
  const rankings = (commandCenterData && Array.isArray(commandCenterData.rankings)) ? commandCenterData.rankings : [];
  const teamEntry = rankings.find(function (entry) {
    return entry && entry.team_name === teamName;
  });
  if (!teamEntry) return 'TBD';
  return safeText(teamEntry.next, 'TBD');
}

function deriveSeasonProgress(commandCenterData, franchiseData) {
  const currentSeason = deriveCurrentSeason(commandCenterData);
  const week = safeNumber(franchiseData && franchiseData.week, 1);
  return 'Season ' + currentSeason + ' · Week ' + week + ' of 26';
}

function displayCommunityLeaderboardPoints(geekPoints) {
  var n = parseInt(geekPoints, 10);
  return (Number.isFinite(n) && n > 0) ? n : '--';
}

function escapeHtmlMs(text) {
  if (text == null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function setLeaderboardView(view) {
  currentLeaderboardView = view === 'titles' ? 'titles' : 'geek_points';
  if (leaderboardGeekPointsToggle) leaderboardGeekPointsToggle.classList.toggle('active', currentLeaderboardView === 'geek_points');
  if (leaderboardTitlesToggle) leaderboardTitlesToggle.classList.toggle('active', currentLeaderboardView === 'titles');
  var subtitle = document.querySelector('.ms-leaderboard-subtitle');
  if (subtitle) {
    subtitle.textContent = currentLeaderboardView === 'titles'
      ? 'Total Titles (National Titles)'
      : 'Earn Geek Points after each game based on your coaching performance.';
  }
}

// Title-count display: total titles with national titles in parens, e.g. "7 (0)".
function displayTitlesValue(entry) {
  var total = parseInt(entry && entry.total_titles, 10);
  var natl = parseInt(entry && entry.national_titles, 10);
  if (!Number.isFinite(total)) total = 0;
  if (!Number.isFinite(natl)) natl = 0;
  return total + ' (' + natl + ')';
}

function renderGeekPointsLeaderboard(leaderboardData, currentUsername) {
  if (!leaderboardHost) return;
  const currentUserNormalized = safeText(currentUsername, '').toLowerCase();
  const topFive = Array.isArray(leaderboardData && leaderboardData.top) ? leaderboardData.top.slice(0, 5) : [];
  const currentTopEntry = currentUserNormalized
    ? topFive.find(function (entry) { return safeText(entry && entry.username, '').toLowerCase() === currentUserNormalized; })
    : null;
  const currentPinnedEntry = (!currentTopEntry && leaderboardData && leaderboardData.current_user)
    ? leaderboardData.current_user
    : null;
  const rows = topFive.map(function (entry) {
    const isCurrent = entry.is_current_user || (currentUserNormalized && safeText(entry.username, '').toLowerCase() === currentUserNormalized);
    const displayPoints = displayCommunityLeaderboardPoints(entry.geek_points);
    return `
      <div class="community-leaderboard-row${isCurrent ? ' is-current-user' : ''}">
        <div class="community-rank">${entry.rank}.</div>
        <div class="community-username">${entry.username}${coachArchetypeBadge(entry, 22)}</div>
        <div class="community-score">${displayPoints}</div>
      </div>
    `;
  }).join('');
  const pinned = currentPinnedEntry ? `
    <div class="community-leaderboard-separator"></div>
    <div class="community-leaderboard-row is-current-user">
      <div class="community-rank">${currentPinnedEntry.rank}.</div>
      <div class="community-username">${currentPinnedEntry.username}${coachArchetypeBadge(currentPinnedEntry, 22)}</div>
      <div class="community-score">${displayCommunityLeaderboardPoints(currentPinnedEntry.geek_points)}</div>
    </div>
  ` : '';
  leaderboardHost.innerHTML = (rows + pinned) || '<div class="community-leaderboard-empty">No alpha leaderboard data yet</div>';
}

// Coaching-archetype badge markup for a leaderboard entry (reads entry.lead_archetype).
function coachArchetypeBadge(entry, size) {
  try {
    if (!window.GOBArchetype) return '';
    var lead = window.GOBArchetype.leadFrom(entry);
    if (!lead) return '';
    return '<span class="lb-archetype-badge" style="display:inline-flex;align-items:center;vertical-align:middle;margin-left:6px;">'
      + window.GOBArchetype.badgeHtml(lead, size || 22) + '</span>';
  } catch (e) { return ''; }
}

function renderTitlesLeaderboard(leaderboardData, currentUsername) {
  if (!leaderboardHost) return;
  const currentUserNormalized = safeText(currentUsername, '').toLowerCase();
  const topFive = Array.isArray(leaderboardData && leaderboardData.titles_top) ? leaderboardData.titles_top.slice(0, 5) : [];
  const currentTopEntry = currentUserNormalized
    ? topFive.find(function (entry) { return safeText(entry && entry.username, '').toLowerCase() === currentUserNormalized; })
    : null;
  const currentPinnedEntry = (!currentTopEntry && leaderboardData && leaderboardData.titles_current_user)
    ? leaderboardData.titles_current_user
    : null;
  const rows = topFive.map(function (entry) {
    const isCurrent = entry.is_current_user || (currentUserNormalized && safeText(entry.username, '').toLowerCase() === currentUserNormalized);
    return `
      <div class="community-leaderboard-row${isCurrent ? ' is-current-user' : ''}">
        <div class="community-rank">${entry.rank}.</div>
        <div class="community-username">${escapeHtmlMs(entry.username)}${coachArchetypeBadge(entry, 22)}</div>
        <div class="community-score">${displayTitlesValue(entry)}</div>
      </div>
    `;
  }).join('');
  const pinned = currentPinnedEntry ? `
    <div class="community-leaderboard-separator"></div>
    <div class="community-leaderboard-row is-current-user">
      <div class="community-rank">${currentPinnedEntry.rank}.</div>
      <div class="community-username">${escapeHtmlMs(currentPinnedEntry.username)}${coachArchetypeBadge(currentPinnedEntry, 22)}</div>
      <div class="community-score">${displayTitlesValue(currentPinnedEntry)}</div>
    </div>
  ` : '';
  leaderboardHost.innerHTML = (rows + pinned) || '<div class="community-leaderboard-empty">No titles won yet</div>';
}

function renderCommunityLeaderboard(leaderboardData, currentUsername) {
  if (currentLeaderboardView === 'titles') {
    renderTitlesLeaderboard(leaderboardData, currentUsername);
    return;
  }
  renderGeekPointsLeaderboard(leaderboardData, currentUsername);
}

async function loadCommunityLeaderboard(currentUsername) {
  if (!leaderboardHost) return;
  const leaderboardData = await safeJsonFetch(API_CONFIG.buildUrl('/api/auth/leaderboard'), {
    headers: getAuthHeaders()
  });
  currentLeaderboardData = leaderboardData;
  renderCommunityLeaderboard(leaderboardData, currentUsername);
}

function formatHighlightGpLabel(gpDelta) {
  var n = parseInt(gpDelta, 10);
  if (!Number.isFinite(n) || n === 0) return '0 GP';
  if (n > 0) return '+' + n + ' GP';
  return String(n) + ' GP';
}

function chGpBlock(entry) {
  var gpLabel = formatHighlightGpLabel(entry.gp_delta);
  var gpNum = parseInt(entry.gp_delta, 10);
  var gpClass = 'community-highlight-gp' + ((Number.isFinite(gpNum) && gpNum < 0) ? ' is-neg' : ' is-pos');
  return (
    '<div class="' +
    gpClass +
    '">' +
    escapeHtmlMs(gpLabel) +
    '</div>'
  );
}

function chRowChromeStyle(entry) {
  var primary = escapeHtmlMs(entry.primary_color || '#27408E');
  var secondary = escapeHtmlMs(entry.secondary_color || '#15181f');
  return '--ch-primary:' + primary + ';--ch-secondary:' + secondary;
}

function chUsernameHtml(entry) {
  var uname = escapeHtmlMs((entry && (entry.username || entry.user_name)) || 'Coach');
  return '<strong class="ch-username">' + uname + '</strong>' + coachArchetypeBadge(entry || {}, 18);
}

function chStandardCopyHtml(entry) {
  var ut = escapeHtmlMs(entry.user_team_name || '?');
  var opp = escapeHtmlMs(entry.opponent_name || '?');
  var beatLost = entry.user_won ? 'beat' : 'lost to';
  var rankLabel = escapeHtmlMs(entry.rank_label || '#--');
  var recRaw = entry.user_team_record != null && String(entry.user_team_record).trim() !== '' ? String(entry.user_team_record).trim() : '';
  var rec = recRaw ? escapeHtmlMs(recRaw) : '';
  var userStrong = chUsernameHtml(entry);
  var usc = entry.user_score;
  var osc = entry.opponent_score;
  var hasScores =
    usc != null &&
    osc != null &&
    !Number.isNaN(Number(usc)) &&
    !Number.isNaN(Number(osc));
  var tailRanked = rec
    ? ut + ' is now ' + rec + ' & ranked ' + rankLabel + ' in the nation.'
    : ut + ' is now ranked ' + rankLabel + ' in the nation.';
  if (hasScores) {
    return (
      userStrong +
      ', coaching ' +
      ut +
      ', ' +
      beatLost +
      ' ' +
      opp +
      ' ' +
      Number(usc) +
      '-' +
      Number(osc) +
      '. ' +
      tailRanked
    );
  }
  return userStrong + ', coaching ' + ut + ', ' + beatLost + ' ' + opp + '. ' + tailRanked;
}

// FTE v2 debut entry — copy locked by Coach (Q8):
//   "Username (bold) has completed his onboarding game. Coaching
//    {team} he defeated/lost to {opp} by a score of {us}-{them}."
function chDebutCopyHtml(entry) {
  var ut = escapeHtmlMs(entry.user_team_name || '?');
  var opp = escapeHtmlMs(entry.opponent_name || '?');
  var verb = entry.user_won ? 'defeated' : 'lost to';
  var userStrong = chUsernameHtml(entry);
  var usc = entry.user_score;
  var osc = entry.opponent_score;
  var hasScores =
    usc != null &&
    osc != null &&
    !Number.isNaN(Number(usc)) &&
    !Number.isNaN(Number(osc));
  var scoreSuffix = hasScores
    ? ' by a score of ' + Number(usc) + '-' + Number(osc)
    : '';
  return (
    userStrong +
    ' has completed his onboarding game. Coaching ' +
    ut +
    ' he ' +
    verb +
    ' ' +
    opp +
    scoreSuffix +
    '.'
  );
}

// Archetype-evolution entry: badge sits right after the bold username (our
// standard), then the established/evolved copy. Name resolves from the manifest.
function chArchetypeCopyHtml(entry) {
  var userStrong = chUsernameHtml(entry);
  var name = (window.GOBArchetype && window.GOBArchetype.nameFor)
    ? window.GOBArchetype.nameFor(entry.lead_archetype)
    : entry.lead_archetype;
  var nameEsc = escapeHtmlMs(name || '');
  if (entry.is_first) {
    return userStrong + ' has established his coaching archetype as ' + nameEsc + '.';
  }
  return userStrong + ' has evolved his coaching archetype to ' + nameEsc + '.';
}

function chAnnouncementHtml(entry) {
  var u = String(entry.username || entry.user_name || 'Coach');
  var raw = String(entry.announcement_line || '');
  if (raw.indexOf(u + ',') === 0) {
    var rest = raw.slice(u.length);
    return chUsernameHtml(entry) + escapeHtmlMs(rest);
  }
  return escapeHtmlMs(raw);
}

function renderCommunityHighlights(data) {
  if (!communityHighlightsBody) return;
  var entries = data && Array.isArray(data.entries) ? data.entries : [];
  if (!entries.length) {
    communityHighlightsBody.innerHTML =
      '<div class="community-highlights-empty">No highlights yet — finish a franchise week to show up here.</div>';
    return;
  }
  communityHighlightsBody.innerHTML = entries.map(function (entry) {
    var type = entry.entry_type || 'standard';
    var variant = entry.variant || 'standard_row';
    var rowExtra = variant === 'national_gold' ? ' community-highlight-row--national-gold' : '';

    // FTE v2 debut: gold metallic border, no clickable behavior, no GP block.
    if (type === 'debut') {
      var debutCopy = chDebutCopyHtml(entry);
      return (
        '<div class="community-highlight-row community-highlight-row--debut" style="' +
        chRowChromeStyle(entry) +
        '">' +
        '<div class="community-highlight-row-inner">' +
        '<div class="community-highlight-copy">' +
        debutCopy +
        '</div>' +
        '</div>' +
        '</div>'
      );
    }

    // Archetype evolution: standard row chrome, no GP block (no game).
    if (type === 'archetype_evolution') {
      return (
        '<div class="community-highlight-row" style="' +
        chRowChromeStyle(entry) +
        '">' +
        '<div class="community-highlight-row-inner">' +
        '<div class="community-highlight-copy">' +
        chArchetypeCopyHtml(entry) +
        '</div>' +
        '</div>' +
        '</div>'
      );
    }

    if (type === 'conference_rs_title' || type === 'championship') {
      var ann = chAnnouncementHtml(entry);
      var details = escapeHtmlMs(entry.details_line || '');
      return (
        '<div class="community-highlight-row community-highlight-row--stacked' +
        rowExtra +
        '" style="' +
        chRowChromeStyle(entry) +
        '">' +
        '<div class="community-highlight-row-inner community-highlight-row-inner--stacked">' +
        '<div class="community-highlight-copy-wrap">' +
        '<div class="community-highlight-announcement">' +
        ann +
        '</div>' +
        '<div class="community-highlight-details">' +
        details +
        '</div>' +
        '</div>' +
        chGpBlock(entry) +
        '</div>' +
        '</div>'
      );
    }

    var copy = chStandardCopyHtml(entry);
    return (
      '<div class="community-highlight-row" style="' +
      chRowChromeStyle(entry) +
      '">' +
      '<div class="community-highlight-row-inner">' +
      '<div class="community-highlight-copy">' +
      copy +
      '</div>' +
      chGpBlock(entry) +
      '</div>' +
      '</div>'
    );
  }).join('');
}

async function loadCommunityHighlights() {
  if (!communityHighlightsBody) return;
  communityHighlightsBody.innerHTML = '<div class="community-highlights-loading">Loading…</div>';
  var data = await safeJsonFetch(API_CONFIG.buildUrl('/api/community/highlights'), {
    headers: getAuthHeaders()
  });
  if (!data) {
    communityHighlightsBody.innerHTML =
      '<div class="community-highlights-empty">Sign in to see community highlights.</div>';
    return;
  }
  // Ensure the archetype name/badge manifest is loaded so archetype-evolution rows
  // render the proper display name (not a humanized key).
  try {
    if (window.GOBArchetype && window.GOBArchetype.ensureManifest) {
      await window.GOBArchetype.ensureManifest();
    }
  } catch (e) {}
  renderCommunityHighlights(data);
}

const ATL_LAST_VISIT_KEY = 'gob_atl_last_visit';
const ATL_ANIMATE_SELF_KEY = 'gob_atl_animate_self';
const ATL_POLL_MS = 20000;
const ATL_SLOT_COUNT = 8;

let atlSlots = [];
let atlBoardSignature = '';
let atlInitialLoadDone = false;
let atlPollTimer = null;
let atlAnimateQueue = [];
let atlAnimating = false;
let atlCurrentUserId = '';

function atlPrefersReducedMotion() {
  try {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (e) {
    return false;
  }
}

function atlBoardSig(slots) {
  return (slots || []).map(function (s) {
    if (!s) return '_';
    return String(s.user_id || '') + '@' + String(s.completed_at || '');
  }).join('|');
}

function atlParseLastVisit() {
  try {
    var raw = localStorage.getItem(ATL_LAST_VISIT_KEY);
    if (!raw) return null;
    var t = Date.parse(raw);
    return Number.isFinite(t) ? t : null;
  } catch (e) {
    return null;
  }
}

function atlPersistLastVisit() {
  try {
    localStorage.setItem(ATL_LAST_VISIT_KEY, new Date().toISOString());
  } catch (e) {}
}

function atlIsNewSinceLastVisit(completedAt) {
  var lastVisit = atlParseLastVisit();
  if (!lastVisit || !completedAt) return false;
  var t = Date.parse(completedAt);
  return Number.isFinite(t) && t > lastVisit;
}

function atlTeamAccentStyle(primary) {
  var p = escapeHtmlMs(primary || '#27408e');
  return '--atl-accent: color-mix(in srgb, ' + p + ' 72%, white);';
}

function atlCardHtml(entry, options) {
  options = options || {};
  var showNew = !!options.showNew;
  var primary = escapeHtmlMs(entry.primary_color || '#27408e');
  var secondary = escapeHtmlMs(entry.secondary_color || '#15181f');
  var rankVal = entry.national_rank != null && entry.national_rank !== ''
    ? '#' + escapeHtmlMs(entry.national_rank)
    : '#--';
  var last = entry.last_game || {};
  var lastWin = !!last.won;
  var lastClass = lastWin ? 'is-win' : 'is-loss';
  var lastPrefix = last.is_away ? '@ ' : 'vs ';
  var nextHtml;
  if (entry.next_opponent && entry.next_opponent.team_name) {
    var n = entry.next_opponent;
    var nPrefix = n.is_away ? '@ ' : 'vs ';
    nextHtml = '<div class="atl-next">Next: <span class="atl-next-opp">' + nPrefix + escapeHtmlMs(n.team_name) + '</span></div>';
  } else {
    nextHtml = '<div class="atl-next is-na">Next: <span class="atl-next-opp">N/A</span></div>';
  }
  var statusClass = entry.is_tournament_week ? 'atl-status is-tourney' : 'atl-status';
  var weekText = escapeHtmlMs(entry.week_label || ('Week ' + (entry.week || '?')));
  var badge = coachArchetypeBadge(entry, 18);
  var newMarker = showNew ? '<span class="atl-new-marker" aria-label="New since last visit"></span>' : '';
  return (
    '<article class="atl-card" data-user-id="' + escapeHtmlMs(entry.user_id) + '" style="--atl-primary:' + primary + ';--atl-secondary:' + secondary + ';' + atlTeamAccentStyle(entry.primary_color) + '">' +
    newMarker +
    '<div class="atl-card-inner">' +
    '<div class="atl-card-head">' +
    '<div class="atl-user-row"><div class="atl-user">' + escapeHtmlMs(entry.username || 'Coach') + '</div>' + badge + '</div>' +
    '<div class="atl-team">' + escapeHtmlMs(entry.team_name || '') + '</div>' +
    '</div>' +
    '<div class="atl-chips">' +
    '<div class="atl-chip"><div class="atl-chip-label">Record</div><div class="atl-chip-value">' + Number(entry.wins || 0) + '-' + Number(entry.losses || 0) + '</div></div>' +
    '<div class="atl-chip"><div class="atl-chip-label">Nat\'l Rank</div><div class="atl-chip-value">' + rankVal + '</div></div>' +
    '</div>' +
    '<div class="' + statusClass + '"><span class="atl-status-dot"></span><span class="atl-status-text">' + weekText + '</span></div>' +
    nextHtml +
    '<div class="atl-last ' + lastClass + '">' +
    '<div class="atl-result">' + (lastWin ? 'W' : 'L') + '</div>' +
    '<div class="atl-last-detail">' + lastPrefix + escapeHtmlMs(last.opponent || '?') + '</div>' +
    '<div class="atl-last-score">' + Number(last.user_score || 0) + '&ndash;' + Number(last.opp_score || 0) + '</div>' +
    '</div>' +
    '</div>' +
    '</article>'
  );
}

function atlEmptyHtml() {
  return (
    '<div class="atl-empty">' +
    '<div class="atl-empty-mark"><span></span></div>' +
    '<div class="atl-empty-text">Waiting for<br>next result</div>' +
    '</div>'
  );
}

function atlRenderGrid(slots, options) {
  if (!aroundTheLeagueGrid) return;
  options = options || {};
  var lastVisitMode = !!options.lastVisitMode;
  var list = Array.isArray(slots) ? slots.slice(0, ATL_SLOT_COUNT) : [];
  while (list.length < ATL_SLOT_COUNT) list.push(null);
  var html = list.map(function (entry) {
    if (!entry) return atlEmptyHtml();
    return atlCardHtml(entry, {
      showNew: lastVisitMode && atlIsNewSinceLastVisit(entry.completed_at),
    });
  }).join('');
  aroundTheLeagueGrid.innerHTML = html;
}

function atlSnapshotRects() {
  var map = new Map();
  if (!aroundTheLeagueGrid) return map;
  aroundTheLeagueGrid.querySelectorAll('.atl-card[data-user-id]').forEach(function (el) {
    map.set(el.getAttribute('data-user-id'), el.getBoundingClientRect());
  });
  return map;
}

function atlPlayFlip(prevRects, freshUserId, done) {
  if (!aroundTheLeagueGrid || atlPrefersReducedMotion()) {
    if (typeof done === 'function') done();
    return;
  }
  var cards = aroundTheLeagueGrid.querySelectorAll('.atl-card[data-user-id]');
  var pending = 0;
  function finishOne() {
    pending -= 1;
    if (pending <= 0 && typeof done === 'function') done();
  }
  if (!cards.length) {
    if (typeof done === 'function') done();
    return;
  }
  cards.forEach(function (el) {
    var uid = el.getAttribute('data-user-id');
    if (prevRects.has(uid)) {
      var oldR = prevRects.get(uid);
      var newR = el.getBoundingClientRect();
      var dx = oldR.left - newR.left;
      var dy = oldR.top - newR.top;
      if (dx || dy) {
        pending += 1;
        el.style.transition = 'none';
        el.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            el.style.transition = 'transform 500ms cubic-bezier(.22,.61,.36,1)';
            el.style.transform = '';
            window.setTimeout(finishOne, 520);
          });
        });
      }
    } else {
      pending += 1;
      el.classList.add('atl-card--enter');
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          el.style.transition = 'opacity 480ms ease, transform 480ms cubic-bezier(.22,.61,.36,1)';
          el.classList.remove('atl-card--enter');
          window.setTimeout(finishOne, 500);
        });
      });
    }
    if (freshUserId && uid === freshUserId) {
      el.classList.add('is-fresh-pulse');
      window.setTimeout(function () {
        el.classList.remove('is-fresh-pulse');
      }, 1500);
    }
  });
  if (pending === 0 && typeof done === 'function') done();
}

function atlDetectFreshUserId(prevSlots, nextSlots) {
  var prevHead = prevSlots && prevSlots[0] ? String(prevSlots[0].user_id || '') : '';
  var nextHead = nextSlots && nextSlots[0] ? String(nextSlots[0].user_id || '') : '';
  if (!nextHead) return '';
  if (nextHead !== prevHead) return nextHead;
  var prevAt = prevSlots && prevSlots[0] ? String(prevSlots[0].completed_at || '') : '';
  var nextAt = nextSlots && nextSlots[0] ? String(nextSlots[0].completed_at || '') : '';
  if (nextAt && nextAt !== prevAt) return nextHead;
  return '';
}

function atlEnqueueAnimation(job) {
  atlAnimateQueue.push(job);
  atlDrainAnimateQueue();
}

function atlDrainAnimateQueue() {
  if (atlAnimating || !atlAnimateQueue.length) return;
  atlAnimating = true;
  var job = atlAnimateQueue.shift();
  var prevRects = job.prevRects;
  var freshUserId = job.freshUserId || '';
  atlRenderGrid(job.slots, { lastVisitMode: false });
  atlPlayFlip(prevRects, freshUserId, function () {
    atlAnimating = false;
    atlDrainAnimateQueue();
  });
}

function atlConsumeSelfAnimateFlag() {
  try {
    var v = sessionStorage.getItem(ATL_ANIMATE_SELF_KEY);
    sessionStorage.removeItem(ATL_ANIMATE_SELF_KEY);
    return v === '1';
  } catch (e) {
    return false;
  }
}

function atlApplyBoardUpdate(nextSlots, opts) {
  opts = opts || {};
  var prevSlots = atlSlots.slice();
  var sig = atlBoardSig(nextSlots);
  if (sig === atlBoardSignature && !opts.force) return;

  var animate = !!opts.animate;
  var lastVisitMode = !!opts.lastVisitMode;
  var selfAnimate = !!opts.selfAnimate;

  if (!animate || atlPrefersReducedMotion()) {
    atlSlots = nextSlots.slice();
    atlBoardSignature = sig;
    atlRenderGrid(atlSlots, { lastVisitMode: lastVisitMode });
    return;
  }

  var freshUserId = '';
  if (selfAnimate && atlCurrentUserId) {
    var headId = nextSlots[0] ? String(nextSlots[0].user_id || '') : '';
    if (headId && headId === atlCurrentUserId) freshUserId = headId;
  }
  if (!freshUserId) freshUserId = atlDetectFreshUserId(prevSlots, nextSlots);

  atlSlots = nextSlots.slice();
  atlBoardSignature = sig;
  atlEnqueueAnimation({
    prevRects: atlSnapshotRects(),
    slots: atlSlots,
    freshUserId: freshUserId,
  });
}

async function loadAroundTheLeague(options) {
  if (!aroundTheLeagueGrid) return;
  options = options || {};
  if (!atlInitialLoadDone) {
    aroundTheLeagueGrid.innerHTML = '<div class="around-the-league-loading">Loading…</div>';
  }
  var data = await safeJsonFetch(API_CONFIG.buildUrl('/api/community/around-the-league'), {
    headers: getAuthHeaders(),
  });
  if (!data || !Array.isArray(data.slots)) {
    if (!atlInitialLoadDone) {
      aroundTheLeagueGrid.innerHTML = '<div class="around-the-league-error">Could not load Around The League.</div>';
    }
    return;
  }
  try {
    if (window.GOBArchetype && window.GOBArchetype.ensureManifest) {
      await window.GOBArchetype.ensureManifest();
    }
  } catch (e) {}

  var nextSlots = data.slots.slice(0, ATL_SLOT_COUNT);
  while (nextSlots.length < ATL_SLOT_COUNT) nextSlots.push(null);

  if (!atlInitialLoadDone) {
    atlInitialLoadDone = true;
    var hadLastVisit = atlParseLastVisit() !== null;
    var selfFlag = atlConsumeSelfAnimateFlag();
    atlApplyBoardUpdate(nextSlots, {
      animate: selfFlag,
      selfAnimate: selfFlag,
      lastVisitMode: hadLastVisit && !selfFlag,
    });
    return;
  }

  if (options.poll) {
    atlApplyBoardUpdate(nextSlots, { animate: true });
  }
}

function wireAroundTheLeaguePolling() {
  if (!aroundTheLeagueGrid || atlPollTimer) return;
  atlPollTimer = window.setInterval(function () {
    loadAroundTheLeague({ poll: true });
  }, ATL_POLL_MS);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') {
      loadAroundTheLeague({ poll: true });
    }
  });
  window.addEventListener('pagehide', atlPersistLastVisit);
  window.addEventListener('beforeunload', atlPersistLastVisit);
}

function wireLeaderboardViewToggles(currentUsername) {
  if (leaderboardGeekPointsToggle) {
    leaderboardGeekPointsToggle.addEventListener('click', function () {
      setLeaderboardView('geek_points');
      renderCommunityLeaderboard(currentLeaderboardData, currentUsername);
    });
  }
  if (leaderboardTitlesToggle) {
    leaderboardTitlesToggle.addEventListener('click', function () {
      setLeaderboardView('titles');
      renderCommunityLeaderboard(currentLeaderboardData, currentUsername);
    });
  }
}

function escapeHtmlLbt(text) {
  if (text == null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function displayLbtPoints(geekPoints) {
  var n = parseInt(geekPoints, 10);
  return (Number.isFinite(n) && n > 0) ? String(n) : '--';
}

async function loadLeadersByTeam() {
  var grid = document.getElementById('leaders-by-team-grid');
  var title = document.querySelector('.leaders-by-team-title');
  if (!grid) return;

  var leaderboardView = currentLeaderboardView === 'titles' ? 'titles' : 'geek_points';
  if (title) {
    title.textContent = leaderboardView === 'titles'
      ? 'Leaders By Team (Titles)'
      : 'Leaders By Team (Geek Points)';
  }
  grid.innerHTML = '<div style="padding:24px;color:rgba(255,255,255,0.3);font-family:Inter,sans-serif;font-size:13px;grid-column:1/-1;text-align:center;">Loading...</div>';

  try {
    var endpoint = API_CONFIG.buildUrl('/api/leaderboard/by-team?view=' + encodeURIComponent(leaderboardView));
    var response = await fetch(endpoint, {
      headers: getAuthHeaders(),
    });
    if (!response.ok) throw new Error('Failed to fetch');
    var data = await response.json();

    grid.innerHTML = '';

    A1_CONFERENCE_TEAMS.forEach(function (team) {
      var leaders = (data[team.id] || []).slice(0, 3);

      var bannerPath = typeof getTeamAssetPath === 'function'
        ? getTeamAssetPath(team.id, 'banner_primary')
        : '/images/teams/' + team.id + '/' + team.id + '_banner_primary.jpg';

      var leadersHtml = leaders.length > 0
        ? leaders.map(function (entry, i) {
            var value = leaderboardView === 'titles'
              ? displayTitlesValue(entry)
              : displayLbtPoints(entry.geek_points);
            return (
              '<div class="lbt-leader-row">' +
              '<span class="lbt-leader-rank">' + (i + 1) + '.</span>' +
              '<span class="lbt-leader-username">' + escapeHtmlLbt(entry.username) + coachArchetypeBadge(entry, 18) + '</span>' +
              '<span class="lbt-leader-points">' + value + '</span>' +
              '</div>'
            );
          }).join('')
        : '<div class="lbt-no-leaders">· · ·</div>';

      var card = document.createElement('div');
      card.className = 'lbt-team-card';
      card.style.cssText =
        '--team-primary: ' + team.primary + '; ' +
        '--team-secondary: ' + team.secondary + '; ' +
        'border-color: ' + team.primary + '66; ' +
        'box-shadow: 0 0 0 1px ' + team.primary + '33, inset 0 0 24px rgba(0,0,0,0.3);';

      // Use unquoted url(...) so inner " does not terminate style="..." (quoted url breaks the attribute).
      var bannerUrlCss = 'url(' + String(bannerPath).replace(/\\/g, '/') + ')';
      card.innerHTML =
        '<div class="lbt-card-banner" style="background-image: ' + bannerUrlCss + ';">' +
        '<div class="lbt-card-banner-overlay"></div>' +
        '<div class="lbt-team-name">' + escapeHtmlLbt(team.name) + '</div>' +
        '</div>' +
        '<div class="lbt-leaders-list">' + leadersHtml + '</div>';

      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = '<div style="padding:24px;color:rgba(255,255,255,0.3);font-family:Inter,sans-serif;font-size:13px;grid-column:1/-1;text-align:center;">Could not load team leaders.</div>';
  }
}

function wireLeadersByTeamModal() {
  var leadersByTeamBtn = document.getElementById('leaders-by-team-btn');
  var leadersByTeamModal = document.getElementById('leaders-by-team-modal');
  var leadersByTeamClose = document.getElementById('leaders-by-team-close');
  var leadersByTeamBackdrop = document.getElementById('leaders-by-team-backdrop');

  if (leadersByTeamBtn && leadersByTeamModal) {
    leadersByTeamBtn.addEventListener('click', function () {
      leadersByTeamModal.classList.add('is-visible');
      leadersByTeamModal.setAttribute('aria-hidden', 'false');
      loadLeadersByTeam();
    });
  }

  if (leadersByTeamClose && leadersByTeamModal) {
    leadersByTeamClose.addEventListener('click', function () {
      leadersByTeamModal.classList.remove('is-visible');
      leadersByTeamModal.setAttribute('aria-hidden', 'true');
    });
  }

  if (leadersByTeamBackdrop && leadersByTeamModal) {
    leadersByTeamBackdrop.addEventListener('click', function () {
      leadersByTeamModal.classList.remove('is-visible');
      leadersByTeamModal.setAttribute('aria-hidden', 'true');
    });
  }
}

function wireAlphaBanner() {
  if (!alphaDisclaimer || !alphaDisclaimerDismiss) return;
  alphaDisclaimerDismiss.addEventListener('click', function () {
    try {
      localStorage.setItem(ALPHA_DISMISS_STORAGE_KEY, ALPHA_DISCLAIMER_VERSION);
    } catch (e) {}
    alphaDisclaimer.classList.add('is-dismissing');
    window.setTimeout(function () {
      alphaDisclaimer.classList.remove('visible', 'is-dismissing');
      alphaDisclaimer.hidden = true;
    }, 180);
  });
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatResumePeriod(resume) {
  const q = Number(resume && resume.quarter) || 1;
  return q <= 4 ? 'Q' + q : 'OT' + (q - 4);
}

function formatResumeClockForModeSelect(resume) {
  const rawClock = resume && resume.clock !== undefined && resume.clock !== null
    ? String(resume.clock).trim()
    : '';
  const normalizedClock = rawClock.replace(/^0(\d):/, '$1:');
  if (normalizedClock === '0:00') {
    return '8:00';
  }
  return rawClock || 'Last stoppage';
}

function cpuSimNeedsResume(cpuSimResume) {
  return !!(
    cpuSimResume &&
    cpuSimResume.phase_b_required &&
    cpuSimResume.can_resume_phase_b
  );
}

function formatCpuSimProgress(cpuSimResume, franchiseData) {
  const completed = Number(cpuSimResume && cpuSimResume.completed_matchups) || 0;
  const expected = Number(cpuSimResume && cpuSimResume.expected_matchups) || 0;
  const failed = Number(cpuSimResume && cpuSimResume.failed_matchups) || 0;
  const week = Number(cpuSimResume && cpuSimResume.week) || Number(franchiseData && franchiseData.week) || 1;
  const base = expected > 0
    ? `Week ${week} · ${completed}/${expected} computer games complete`
    : `Week ${week} · Computer games need to finish`;
  return failed > 0 ? `${base} · ${failed} retrying` : base;
}

function buildActiveGameCourtUrl(franchiseData, resume) {
  if (!franchiseData || !franchiseData.franchise_id || !resume || !resume.game_id) return null;
  const params = new URLSearchParams();
  params.set('mode', 'franchise');
  params.set('active_resume', 'true');
  params.set('franchise_id', franchiseData.franchise_id);
  params.set('game_id', resume.game_id);
  params.set('home', resume.home_team_name || 'Home');
  params.set('away', resume.away_team_name || 'Away');
  params.set('home_id', resume.home_team_id || resume.home_team_name || 'Home');
  params.set('away_id', resume.away_team_id || resume.away_team_name || 'Away');
  params.set('team_id', franchiseData.user_team_id || '');
  params.set('my_team', resume.user_team_side || 'home');
  params.set('quarter', String(Number(resume.quarter) || 1));
  params.set('period', formatResumePeriod(resume));
  params.set('resume_from_timeout', resume.resume_from_timeout ? 'true' : 'false');
  if (resume.anchor_type) params.set('anchor_type', resume.anchor_type);
  if (resume.week) params.set('week', String(resume.week));
  if (resume.clock) params.set('clock', resume.clock);
  if (resume.home_score !== undefined && resume.home_score !== null) params.set('home_score', String(resume.home_score));
  if (resume.away_score !== undefined && resume.away_score !== null) params.set('away_score', String(resume.away_score));
  if (resume.timeout_trace_id) params.set('timeout_trace_id', resume.timeout_trace_id);
  return './court.html?' + params.toString();
}

// Tournament tier emblem on a mode-select franchise card. Tier comes from the
// displayed week; value (conference number / region letter) from command-center
// data — the same sources the FCC uses. Cleared outside an EOS week (27-34).
function renderModeSelectTierEmblem(slotEl, franchiseData, commandCenterData) {
  const emblem = slotEl && slotEl.querySelector('.franchise-card-tier-emblem');
  if (!emblem || !window.GOBTierEmblem) return;
  const week = (franchiseData && franchiseData.week != null)
    ? franchiseData.week
    : (commandCenterData && commandCenterData.week);
  const tier = window.GOBTierEmblem.tierForWeek(week);
  if (!tier) { emblem.innerHTML = ''; return; }
  let value = null;
  if (tier === 'conference') {
    const c = commandCenterData ? commandCenterData.user_conference : null;
    value = (c === 0 || c) ? String(c) : '';
  } else if (tier === 'region') {
    const r = commandCenterData ? commandCenterData.user_region : null;
    if (r) {
      value = String(r).toUpperCase();
    } else {
      const c = Number(commandCenterData ? commandCenterData.user_conference : NaN);
      if (Number.isInteger(c) && c >= 1 && c <= 16) value = String.fromCharCode(65 + Math.floor((c - 1) / 2));
    }
  }
  window.GOBTierEmblem.injectCss();
  emblem.innerHTML = window.GOBTierEmblem.renderLockup({ tier, value, size: 40, variant: 'stack', l1: 16, l2: 9 });
}

function buildEmptySlotHtml(slotIndex) {
  const title = franchisesList.length > 0
    ? 'Start Another Franchise'
    : 'Start Your Coaching Journey';
  const cta = 'Find Your Program';
  return (
    '<div class="franchise-home-slot-cell" data-slot-index="' + slotIndex + '">' +
      '<div class="franchise-home-card franchise-home-card-empty">' +
        '<div class="franchise-empty-state">' +
          '<div class="franchise-empty-icon" aria-hidden="true">' +
            '<img src="/images/buttons/whiteball.svg" alt="">' +
          '</div>' +
          '<h2 class="franchise-empty-title">' + escapeHtml(title) + '</h2>' +
          '<button type="button" class="franchise-empty-cta" data-action="start-franchise">' +
            escapeHtml(cta) +
          '</button>' +
        '</div>' +
      '</div>' +
    '</div>'
  );
}

function buildOccupiedSlotHtml(franchiseData, teamDoc, commandCenterData, slotIndex) {
  const franchiseId = String(franchiseData.franchise_id || '');
  const teamName = safeText(franchiseData.user_team_id, 'Program');
  const bannerUrl = getSquareLogoPath(teamName);
  const seasonProgress = deriveSeasonProgress(commandCenterData, franchiseData);
  const record = deriveRecord(commandCenterData, teamName);
  const rankRaw = deriveRank(teamDoc, commandCenterData);
  const rank = rankRaw === '-' ? '-' : '#' + rankRaw;
  const prestige = derivePrestige(teamDoc, commandCenterData);
  const nextOpponent = deriveNextOpponent(commandCenterData, teamName);

  const activeGameResume = commandCenterData && commandCenterData.active_game_resume
    && commandCenterData.active_game_resume.status === 'stoppage_anchor'
    ? commandCenterData.active_game_resume
    : null;
  const cpuSimResume = commandCenterData && cpuSimNeedsResume(commandCenterData.cpu_sim_resume)
    ? commandCenterData.cpu_sim_resume
    : null;

  slotRuntimeById[franchiseId] = {
    franchise: franchiseData,
    activeGameResume: activeGameResume,
    cpuSimResume: cpuSimResume,
  };

  let resumeHtml = '';
  let enterLabel = 'Enter Franchise →';
  if (activeGameResume) {
    enterLabel = 'Resume Game →';
    resumeHtml =
      '<div class="franchise-resume-card">' +
        '<div>' +
          '<div class="franchise-resume-kicker">Game In Progress</div>' +
          '<div class="franchise-resume-matchup">' +
            escapeHtml((activeGameResume.away_team_name || 'Away') + ' at ' + (activeGameResume.home_team_name || 'Home')) +
          '</div>' +
          '<div class="franchise-resume-detail">' +
            escapeHtml(formatResumePeriod(activeGameResume) + ' · ' + formatResumeClockForModeSelect(activeGameResume)) +
          '</div>' +
        '</div>' +
        '<div class="franchise-resume-score">' +
          escapeHtml(String(activeGameResume.away_score ?? 0) + ' - ' + String(activeGameResume.home_score ?? 0)) +
        '</div>' +
      '</div>';
  } else if (cpuSimResume) {
    enterLabel = 'Finish Week →';
    const completed = Number(cpuSimResume.completed_matchups) || 0;
    const expected = Number(cpuSimResume.expected_matchups) || 0;
    resumeHtml =
      '<div class="franchise-resume-card franchise-resume-card-cpu">' +
        '<div>' +
          '<div class="franchise-resume-kicker">Finishing Week</div>' +
          '<div class="franchise-resume-matchup">Finishing Computer Games</div>' +
          '<div class="franchise-resume-detail">' +
            escapeHtml(formatCpuSimProgress(cpuSimResume, franchiseData)) +
          '</div>' +
        '</div>' +
        '<div class="franchise-resume-score">' +
          escapeHtml(expected > 0 ? (completed + '/' + expected) : '...') +
        '</div>' +
      '</div>';
  }

  return (
    '<div class="franchise-home-slot-cell" data-slot-index="' + slotIndex + '" data-franchise-id="' + escapeHtml(franchiseId) + '">' +
      '<div class="franchise-home-card franchise-home-card-active" role="link" tabindex="0" data-action="enter-franchise" data-franchise-id="' + escapeHtml(franchiseId) + '" style="background-image:url(\'' + escapeHtml(bannerUrl) + '\');background-size:cover;background-position:center;">' +
        '<img class="franchise-card-banner" src="' + escapeHtml(bannerUrl) + '" alt="' + escapeHtml(teamName) + '" style="display:none;">' +
        '<div class="franchise-card-content">' +
          '<div>' +
            '<div class="franchise-card-name-row">' +
              '<div class="franchise-card-team-name">' + escapeHtml(teamName) + '</div>' +
              '<div class="franchise-card-tier-emblem" aria-hidden="true"></div>' +
            '</div>' +
            '<div class="franchise-card-season-line">' + escapeHtml(seasonProgress) + '</div>' +
          '</div>' +
          '<div class="franchise-card-grid">' +
            '<div class="franchise-chip"><div class="franchise-chip-label">Record</div><div class="franchise-chip-value">' + escapeHtml(record) + '</div></div>' +
            '<div class="franchise-chip"><div class="franchise-chip-label">Rank</div><div class="franchise-chip-value">' + escapeHtml(rank) + '</div></div>' +
            '<div class="franchise-chip"><div class="franchise-chip-label">Prestige</div><div class="franchise-chip-value">' + escapeHtml(prestige) + '</div></div>' +
            '<div class="franchise-chip"><div class="franchise-chip-label">Next Opponent</div><div class="franchise-chip-value franchise-chip-value-small">' + escapeHtml(nextOpponent) + '</div></div>' +
          '</div>' +
          resumeHtml +
          '<div class="franchise-card-actions">' +
            '<button type="button" class="franchise-enter-btn" data-action="enter-franchise" data-franchise-id="' + escapeHtml(franchiseId) + '">' + escapeHtml(enterLabel) + '</button>' +
            '<button type="button" class="franchise-slot-delete-btn" data-action="delete-franchise" data-franchise-id="' + escapeHtml(franchiseId) + '">Delete</button>' +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>'
  );
}

function renderFranchiseSlots(franchises, teamsByName, commandCenterById) {
  if (!franchiseHomeSlots) return;
  Object.keys(slotRuntimeById).forEach(function (k) { delete slotRuntimeById[k]; });

  const occupied = Array.isArray(franchises) ? franchises.slice(0, maxFranchiseSlots) : [];
  const emptyCount = Math.max(0, maxFranchiseSlots - occupied.length);
  let html = '';
  occupied.forEach(function (franchiseData, index) {
    const teamName = safeText(franchiseData.user_team_id, '');
    const teamDoc = teamsByName[teamName] || null;
    const commandCenterData = commandCenterById[String(franchiseData.franchise_id)] || null;
    html += buildOccupiedSlotHtml(franchiseData, teamDoc, commandCenterData, index);
  });
  for (let i = 0; i < emptyCount; i++) {
    html += buildEmptySlotHtml(occupied.length + i);
  }
  franchiseHomeSlots.innerHTML = html;

  occupied.forEach(function (franchiseData) {
    const cell = Array.prototype.find.call(
      franchiseHomeSlots.querySelectorAll('.franchise-home-slot-cell[data-franchise-id]'),
      function (el) {
        return String(el.getAttribute('data-franchise-id')) === String(franchiseData.franchise_id);
      }
    );
    if (!cell) return;
    const commandCenterData = commandCenterById[String(franchiseData.franchise_id)] || null;
    renderModeSelectTierEmblem(cell, franchiseData, commandCenterData);
  });
}

function goToFranchiseCommandCenter(franchiseId) {
  const runtime = franchiseId ? slotRuntimeById[String(franchiseId)] : null;
  const franchiseData = runtime && runtime.franchise;
  if (franchiseData && franchiseData.franchise_id) {
    const resumeUrl = buildActiveGameCourtUrl(franchiseData, runtime.activeGameResume);
    if (resumeUrl) {
      console.warn('[MODE-RESUME-CLIENT] route resume', {
        franchise_id: franchiseData.franchise_id,
        game_id: runtime.activeGameResume && runtime.activeGameResume.game_id,
        url: resumeUrl,
      });
      window.location.href = resumeUrl;
      return;
    }
    if (runtime.cpuSimResume) {
      const params = new URLSearchParams();
      params.set('franchise_id', franchiseData.franchise_id);
      params.set('finish_cpu_sims', '1');
      if (runtime.cpuSimResume.week) params.set('week', String(runtime.cpuSimResume.week));
      console.warn('[MODE-RESUME-CLIENT] route cpu sim recovery', {
        franchise_id: franchiseData.franchise_id,
        week: runtime.cpuSimResume.week,
      });
      window.location.href = './franchise-command-center.html?' + params.toString();
      return;
    }
    console.warn('[MODE-RESUME-CLIENT] route fcc', {
      franchise_id: franchiseData.franchise_id,
    });
    window.location.href = './franchise-command-center.html?franchise_id=' + encodeURIComponent(franchiseData.franchise_id);
    return;
  }
  console.warn('[MODE-RESUME-CLIENT] route franchise select', { franchiseId: franchiseId });
  window.location.href = './franchise-select-team.html';
}

/** Tutorial alert "I'll do this later" for Player Attributes → FCC when a franchise exists. */
function getFranchiseCommandCenterUrlForLater() {
  const currentFranchise = franchisesList[0] || null;
  if (!currentFranchise || !currentFranchise.franchise_id) return null;
  var fid = currentFranchise.franchise_id;
  var tid = currentFranchise.user_team_id || null;
  if (!tid && window.FranchiseLS) {
    tid = window.FranchiseLS.get(fid, 'user_team_id') || null;
  }
  if (typeof buildFranchiseLockerRoomUrl === 'function') {
    return buildFranchiseLockerRoomUrl(fid, tid);
  }
  return './franchise-command-center.html?mode=franchise&franchise_id=' + encodeURIComponent(fid) +
    (tid ? '&team_id=' + encodeURIComponent(tid) : '');
}

window.GOBModeSelect = window.GOBModeSelect || {};
window.GOBModeSelect.getFranchiseCommandCenterUrlForLater = getFranchiseCommandCenterUrlForLater;

const deleteFranchiseModal = document.getElementById('delete-franchise-modal');
const deleteFranchiseModalText = document.getElementById('delete-franchise-modal-text');
const deleteFranchiseModalCancel = document.getElementById('delete-franchise-modal-cancel');
const deleteFranchiseModalConfirm = document.getElementById('delete-franchise-modal-confirm');
const slotsFullModal = document.getElementById('slots-full-modal');
const slotsFullModalOk = document.getElementById('slots-full-modal-ok');

function openDeleteFranchiseModal(franchiseData) {
  pendingDeleteFranchise = franchiseData || null;
  if (!pendingDeleteFranchise) return;
  const teamName = safeText(pendingDeleteFranchise.user_team_id, 'this franchise');
  const week = pendingDeleteFranchise.week != null ? pendingDeleteFranchise.week : '?';
  const season = pendingDeleteFranchise.current_season != null ? pendingDeleteFranchise.current_season : '?';
  if (deleteFranchiseModalText) {
    deleteFranchiseModalText.textContent =
      'Delete ' + teamName + ' (Season ' + season + ' · Week ' + week + ')? This cannot be undone.';
  }
  if (deleteFranchiseModal) {
    deleteFranchiseModal.style.display = 'flex';
    deleteFranchiseModal.setAttribute('aria-hidden', 'false');
  }
}

function closeDeleteFranchiseModal() {
  pendingDeleteFranchise = null;
  if (deleteFranchiseModal) {
    deleteFranchiseModal.style.display = 'none';
    deleteFranchiseModal.setAttribute('aria-hidden', 'true');
  }
}

function openSlotsFullModal() {
  if (slotsFullModal) {
    slotsFullModal.style.display = 'flex';
    slotsFullModal.setAttribute('aria-hidden', 'false');
  }
}

function closeSlotsFullModal() {
  if (slotsFullModal) {
    slotsFullModal.style.display = 'none';
    slotsFullModal.setAttribute('aria-hidden', 'true');
  }
}

function goToNewFranchise() {
  window.location.href = './franchise-select-team.html';
}

function startNewFranchiseFlow() {
  playSound('click-beep.wav');
  if (franchisesList.length >= maxFranchiseSlots) {
    openSlotsFullModal();
    return;
  }
  // Fill an empty slot — do not delete any existing franchise.
  goToNewFranchise();
}

async function confirmDeleteFranchise() {
  const target = pendingDeleteFranchise;
  if (!target || !target.franchise_id) {
    closeDeleteFranchiseModal();
    return;
  }
  const franchiseId = String(target.franchise_id);
  if (deleteFranchiseModalConfirm) deleteFranchiseModalConfirm.disabled = true;
  try {
    const res = await fetch(
      API_CONFIG.buildUrl('/franchise/' + encodeURIComponent(franchiseId)),
      { method: 'DELETE', headers: getAuthHeaders() }
    );
    if (!res.ok) {
      console.warn('[mode-select] delete franchise failed:', res.status);
      alert('Could not delete that franchise. Try again.');
      return;
    }
    if (window.FranchiseLS && typeof window.FranchiseLS.clearAllForFranchise === 'function') {
      window.FranchiseLS.clearAllForFranchise(franchiseId);
    }
    closeDeleteFranchiseModal();
    window.location.reload();
  } catch (e) {
    console.warn('[mode-select] delete franchise error:', e);
    alert('Could not delete that franchise. Try again.');
  } finally {
    if (deleteFranchiseModalConfirm) deleteFranchiseModalConfirm.disabled = false;
  }
}

if (franchiseHomeSlots) {
  franchiseHomeSlots.addEventListener('click', function (event) {
    const actionEl = event.target.closest('[data-action]');
    if (!actionEl || !franchiseHomeSlots.contains(actionEl)) return;
    const action = actionEl.getAttribute('data-action');
    const franchiseId = actionEl.getAttribute('data-franchise-id');

    if (action === 'start-franchise') {
      event.preventDefault();
      startNewFranchiseFlow();
      return;
    }
    if (action === 'delete-franchise') {
      event.preventDefault();
      event.stopPropagation();
      playSound('click-beep.wav');
      const runtime = franchiseId ? slotRuntimeById[String(franchiseId)] : null;
      if (runtime && runtime.franchise) openDeleteFranchiseModal(runtime.franchise);
      return;
    }
    if (action === 'enter-franchise') {
      event.preventDefault();
      event.stopPropagation();
      playSound('click-strong.wav');
      goToFranchiseCommandCenter(franchiseId);
    }
  });

  franchiseHomeSlots.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    const card = event.target.closest('[data-action="enter-franchise"].franchise-home-card-active');
    if (!card || !franchiseHomeSlots.contains(card)) return;
    event.preventDefault();
    playSound('click-strong.wav');
    goToFranchiseCommandCenter(card.getAttribute('data-franchise-id'));
  });
}

if (deleteFranchiseModalCancel) {
  deleteFranchiseModalCancel.addEventListener('click', closeDeleteFranchiseModal);
}
if (deleteFranchiseModalConfirm) {
  deleteFranchiseModalConfirm.addEventListener('click', confirmDeleteFranchise);
}
if (slotsFullModalOk) {
  slotsFullModalOk.addEventListener('click', closeSlotsFullModal);
}

document.addEventListener('DOMContentLoaded', async function () {
  const authLoggedOut = document.getElementById('auth-logged-out');
  const authLoggedIn = document.getElementById('auth-logged-in');
  const authUserEmail = document.getElementById('auth-user-email');
  const logoutBtn = document.getElementById('logout-btn');
  const authToken = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const authUser = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_user') : null;
  let currentUsername = '';

  if (!authToken || !authUser) {
    redirectToLogin();
    return;
  }

  try {
    const user = JSON.parse(authUser);
    currentUsername = user.username || user.email || '';
    if (authLoggedOut) authLoggedOut.style.display = 'none';
    if (authLoggedIn) authLoggedIn.style.display = 'flex';
    if (authUserEmail) authUserEmail.textContent = user.username || user.email;

    const meRes = await fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: getAuthHeaders() });
    if (!meRes.ok) {
      if (meRes.status === 401 || meRes.status === 403) {
        redirectToLogin();
        return;
      }
      throw new Error('/api/auth/me failed with status ' + meRes.status);
    }

    const meData = await meRes.json();
    if (meData.user_id) {
      atlCurrentUserId = String(meData.user_id);
    }
    if (meData.username && meData.username.trim()) {
      currentUsername = meData.username;
      if (authUserEmail) authUserEmail.textContent = meData.username;
      const stored = JSON.parse(authUser);
      stored.username = meData.username;
      localStorage.setItem('auth_user', JSON.stringify(stored));
    }
  } catch (e) {
    console.error('[AUTH] Mode select auth validation failed:', e);
    redirectToLogin();
    return;
  }

  wireAlphaBanner();

  try {
    const lobbyMusic = new Audio('/sounds/crossover-21738.mp3');
    lobbyMusic.loop = true;
    lobbyMusic.volume = 0.4;
    lobbyMusic.play().catch(function () {});
  } catch (e) {}

  try {
    const appConfig = await API_CONFIG.loadAppConfig();
    if (appConfig.isAlpha) {
      const alphaBadge = document.getElementById('alpha-badge');
      const isDismissed = typeof localStorage !== 'undefined' && localStorage.getItem(ALPHA_DISMISS_STORAGE_KEY) === ALPHA_DISCLAIMER_VERSION;
      if (alphaBadge) alphaBadge.classList.add('visible');
      if (alphaDisclaimer && !isDismissed) {
        alphaDisclaimer.hidden = false;
        alphaDisclaimer.classList.add('visible');
      }
      console.log('[ALPHA] Alpha mode enabled');
    }
  } catch (error) {
    console.error('[ALPHA] Failed to load app config:', error);
  }

  setLeaderboardView('geek_points');
  wireLeaderboardViewToggles(currentUsername);
  await loadCommunityLeaderboard(currentUsername);
  await loadCommunityHighlights();
  await loadAroundTheLeague();
  wireAroundTheLeaguePolling();
  wireLeadersByTeamModal();

  if (logoutBtn) {
    logoutBtn.addEventListener('click', async function () {
      try {
        await fetch(API_CONFIG.buildUrl('/api/auth/logout'), { method: 'POST' });
      } catch (e) {}
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      if (authLoggedOut) authLoggedOut.style.display = 'flex';
      if (authLoggedIn) authLoggedIn.style.display = 'none';
    });
  }

  const headers = getAuthHeaders();
  const listData = await safeJsonFetch(API_CONFIG.buildUrl('/franchise/list'), { headers: headers });
  franchisesList = (listData && Array.isArray(listData.franchises)) ? listData.franchises : [];
  maxFranchiseSlots = (listData && listData.max) ? Number(listData.max) || 2 : 2;

  const teamsData = await safeJsonFetch(API_CONFIG.buildUrl('/teams'), { headers: headers }) || [];
  const teamsByName = {};
  teamsData.forEach(function (team) {
    if (team && team.name) teamsByName[team.name] = team;
  });

  const commandCenterById = {};
  await Promise.all(franchisesList.map(async function (franchiseData) {
    if (!franchiseData || !franchiseData.franchise_id) return;
    const fid = String(franchiseData.franchise_id);
    const commandCenterData = await safeJsonFetch(
      API_CONFIG.buildUrl('/franchise/command-center/data?franchise_id=' + encodeURIComponent(fid)),
      { headers: headers }
    );
    commandCenterById[fid] = commandCenterData;
    console.warn('[MODE-RESUME-CLIENT] command center data loaded', {
      franchise_id: fid,
      has_data: !!commandCenterData,
      has_active_game_resume: !!(commandCenterData && commandCenterData.active_game_resume),
    });
  }));

  renderFranchiseSlots(franchisesList, teamsByName, commandCenterById);
  revealModeSelect();
});
