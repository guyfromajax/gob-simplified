function playSound(filename) {
  try {
    var a = new Audio('/sounds/' + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function () {});
  } catch (e) {}
}

const ALPHA_DISMISS_STORAGE_KEY = 'alpha_disclaimer_dismissed_version';
const ALPHA_DISCLAIMER_VERSION = '2026-06-14-alpha-box';

const franchisePlayNowBtn = document.getElementById('franchise-play-now-btn');
const franchiseNewBtn = document.getElementById('franchise-new-btn');
const franchiseDeleteLink = document.getElementById('franchise-delete-link');
const franchiseDeleteRow = document.getElementById('franchise-delete-row');
const franchiseEmptyCard = document.getElementById('franchise-empty-card');
const franchiseCardBanner = document.getElementById('franchise-card-banner');
const franchiseCardTeamName = document.getElementById('franchise-card-team-name');
const franchiseCardSeasonProgress = document.getElementById('franchise-card-season-progress');
const franchiseCardRecord = document.getElementById('franchise-card-record');
const franchiseCardRank = document.getElementById('franchise-card-rank');
const franchiseCardPrestige = document.getElementById('franchise-card-prestige');
const franchiseCardNext = document.getElementById('franchise-card-next');
const franchiseCardCareerSummary = document.getElementById('franchise-card-career-summary');
const franchiseEnterBtn = document.getElementById('franchise-enter-btn');
const alphaDisclaimer = document.getElementById('alpha-disclaimer');
const alphaDisclaimerDismiss = document.getElementById('alpha-disclaimer-dismiss');
const leaderboardHost = document.getElementById('community-leaderboard');
const communityHighlightsBody = document.querySelector('.community-highlights-body');
const leaderboardGeekPointsToggle = document.getElementById('leaderboard-view-geek-points');
const leaderboardRankToggle = document.getElementById('leaderboard-view-rank');

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

let currentFranchise = null;
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
  if (typeof localStorage === 'undefined') return;
  const toRemove = [
    'franchiseId',
    'franchise_id',
    'franchise_week',
    'franchise_user_team',
    'franchise_user_team_id',
    'franchise_user_team_primary_color',
  ];
  toRemove.forEach((k) => localStorage.removeItem(k));
  Object.keys(localStorage).forEach((k) => {
    if (k.startsWith('playbooks_position_filters_franchise_')) localStorage.removeItem(k);
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

function renderCareerSummary(commandCenterData) {
  if (!franchiseCardCareerSummary) return;
  const careerBestRankRaw = commandCenterData && commandCenterData.career_best_rank;
  const careerBestRank = (careerBestRankRaw !== undefined && careerBestRankRaw !== null && String(careerBestRankRaw).trim() !== '')
    ? String(careerBestRankRaw)
    : '--';
  const bestRankSeasonsRaw =
    (commandCenterData && commandCenterData.career_best_rank_seasons) ||
    (commandCenterData && commandCenterData.best_rank_seasons) ||
    (commandCenterData && commandCenterData.career_best_seasons) ||
    (commandCenterData && commandCenterData.career_best_rank_season);

  let seasons = [];
  if (Array.isArray(bestRankSeasonsRaw)) {
    seasons = bestRankSeasonsRaw
      .map(function (value) { return safeNumber(value, null); })
      .filter(function (value) { return Number.isFinite(value); });
  } else {
    const singleSeason = safeNumber(bestRankSeasonsRaw, null);
    if (Number.isFinite(singleSeason)) seasons = [singleSeason];
  }

  let dedupedSortedSeasons = Array.from(new Set(seasons)).sort(function (a, b) { return a - b; });
  if (!dedupedSortedSeasons.length) {
    const currentSeason = deriveCurrentSeason(commandCenterData);
    if (careerBestRank !== '--' && Number.isFinite(currentSeason)) dedupedSortedSeasons = [currentSeason];
  }

  if (!dedupedSortedSeasons.length) {
    franchiseCardCareerSummary.textContent = 'Career Best Ranking: #' + careerBestRank;
    return;
  }

  const seasonLabel = dedupedSortedSeasons.length === 1 ? 'Season ' : 'Seasons ';
  franchiseCardCareerSummary.textContent =
    'Career Best Ranking: #' + careerBestRank + ' (' + seasonLabel + dedupedSortedSeasons.join(', ') + ')';
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
  currentLeaderboardView = view === 'rank' ? 'rank' : 'geek_points';
  if (leaderboardGeekPointsToggle) leaderboardGeekPointsToggle.classList.toggle('active', currentLeaderboardView === 'geek_points');
  if (leaderboardRankToggle) leaderboardRankToggle.classList.toggle('active', currentLeaderboardView === 'rank');
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

function renderRankLeaderboard(leaderboardData, currentUsername) {
  if (!leaderboardHost) return;
  const currentUserNormalized = safeText(currentUsername, '').toLowerCase();
  const topFive = Array.isArray(leaderboardData && leaderboardData.rank_top) ? leaderboardData.rank_top.slice(0, 5) : [];
  const rows = topFive.map(function (entry) {
    const isCurrent = entry.is_current_user || (currentUserNormalized && safeText(entry.username, '').toLowerCase() === currentUserNormalized);
    const natlRank = parseInt(entry.natl_rank, 10);
    const displayRank = Number.isFinite(natlRank) ? natlRank : '--';
    const teamColor = safeText(entry.team_primary_color, '#27408E');
    return `
      <div class="community-leaderboard-row${isCurrent ? ' is-current-user' : ''}">
        <div class="community-rank">${entry.rank}.</div>
        <div class="community-username">
          <span class="community-username-fragment">${escapeHtmlMs(entry.username)}</span>${coachArchetypeBadge(entry, 22)}
          <span class="community-username-fragment"> (</span><span class="community-team-name" style="color: ${escapeHtmlMs(teamColor)};">${escapeHtmlMs(entry.team_name)}</span><span class="community-username-fragment">):</span>
        </div>
        <div class="community-score">${displayRank}</div>
      </div>
    `;
  }).join('');
  leaderboardHost.innerHTML = rows || '<div class="community-leaderboard-empty">No franchise rank data yet</div>';
}

function renderCommunityLeaderboard(leaderboardData, currentUsername) {
  if (currentLeaderboardView === 'rank') {
    renderRankLeaderboard(leaderboardData, currentUsername);
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

function chStandardCopyHtml(entry) {
  var uname = escapeHtmlMs(entry.username || entry.user_name || 'Coach');
  var ut = escapeHtmlMs(entry.user_team_name || '?');
  var opp = escapeHtmlMs(entry.opponent_name || '?');
  var beatLost = entry.user_won ? 'beat' : 'lost to';
  var rankLabel = escapeHtmlMs(entry.rank_label || '#--');
  var recRaw = entry.user_team_record != null && String(entry.user_team_record).trim() !== '' ? String(entry.user_team_record).trim() : '';
  var rec = recRaw ? escapeHtmlMs(recRaw) : '';
  var userStrong = '<strong class="ch-username">' + uname + '</strong>';
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
  var uname = escapeHtmlMs(entry.username || entry.user_name || 'Coach');
  var ut = escapeHtmlMs(entry.user_team_name || '?');
  var opp = escapeHtmlMs(entry.opponent_name || '?');
  var verb = entry.user_won ? 'defeated' : 'lost to';
  var userStrong = '<strong class="ch-username">' + uname + '</strong>';
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
  var uname = escapeHtmlMs(entry.username || entry.user_name || 'Coach');
  var userStrong = '<strong class="ch-username">' + uname + '</strong>';
  var badge = coachArchetypeBadge(entry, 22); // reads entry.lead_archetype
  var name = (window.GOBArchetype && window.GOBArchetype.nameFor)
    ? window.GOBArchetype.nameFor(entry.lead_archetype)
    : entry.lead_archetype;
  var nameEsc = escapeHtmlMs(name || '');
  if (entry.is_first) {
    return userStrong + badge + ' has established his coaching archetype as ' + nameEsc + '.';
  }
  return userStrong + badge + ' has evolved his coaching archetype to ' + nameEsc + '.';
}

function chAnnouncementHtml(entry) {
  var u = String(entry.username || entry.user_name || 'Coach');
  var raw = String(entry.announcement_line || '');
  if (raw.indexOf(u + ',') === 0) {
    var rest = raw.slice(u.length);
    return '<strong class="ch-username">' + escapeHtmlMs(u) + '</strong>' + escapeHtmlMs(rest);
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

function wireLeaderboardViewToggles(currentUsername) {
  if (leaderboardGeekPointsToggle) {
    leaderboardGeekPointsToggle.addEventListener('click', function () {
      setLeaderboardView('geek_points');
      renderCommunityLeaderboard(currentLeaderboardData, currentUsername);
    });
  }
  if (leaderboardRankToggle) {
    leaderboardRankToggle.addEventListener('click', function () {
      setLeaderboardView('rank');
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

  var leaderboardView = currentLeaderboardView === 'rank' ? 'rank' : 'geek_points';
  if (title) {
    title.textContent = leaderboardView === 'rank'
      ? 'Leaders By Team (Rank)'
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
            var value = leaderboardView === 'rank'
              ? (Number.isFinite(parseInt(entry.natl_rank, 10)) ? String(parseInt(entry.natl_rank, 10)) : '--')
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

function renderFranchiseEmptyState() {
  if (franchiseEmptyCard) franchiseEmptyCard.style.display = 'block';
  if (franchisePlayNowBtn) franchisePlayNowBtn.style.display = 'none';
  if (franchiseDeleteRow) franchiseDeleteRow.style.display = 'none';
}

function renderFranchiseActiveState(franchiseData, teamDoc, commandCenterData) {
  if (!franchisePlayNowBtn) return;

  const teamName = safeText(franchiseData.user_team_id, 'Program');
  if (franchiseCardTeamName) franchiseCardTeamName.textContent = teamName;
  const bannerUrl = getSquareLogoPath(teamName);
  if (franchiseCardBanner) {
    franchiseCardBanner.src = bannerUrl;
    franchiseCardBanner.alt = teamName;
    franchiseCardBanner.style.display = 'none';
  }
  if (franchisePlayNowBtn) {
    franchisePlayNowBtn.style.backgroundImage = "url('" + bannerUrl + "')";
    franchisePlayNowBtn.style.backgroundSize = 'cover';
    franchisePlayNowBtn.style.backgroundPosition = 'center';
  }
  if (franchiseCardSeasonProgress) franchiseCardSeasonProgress.textContent = deriveSeasonProgress(commandCenterData, franchiseData);
  if (franchiseCardRecord) franchiseCardRecord.textContent = deriveRecord(commandCenterData, teamName);
  if (franchiseCardRank) {
    const rank = deriveRank(teamDoc, commandCenterData);
    franchiseCardRank.textContent = rank === '-' ? '-' : '#' + rank;
  }
  if (franchiseCardPrestige) franchiseCardPrestige.textContent = derivePrestige(teamDoc, commandCenterData);
  if (franchiseCardNext) franchiseCardNext.textContent = deriveNextOpponent(commandCenterData, teamName);
  renderCareerSummary(commandCenterData);

  if (franchiseEmptyCard) franchiseEmptyCard.style.display = 'none';
  franchisePlayNowBtn.style.display = 'block';
  if (franchiseDeleteRow) franchiseDeleteRow.style.display = 'block';
}

function goToFranchiseCommandCenter() {
  if (currentFranchise && currentFranchise.franchise_id) {
    window.location.href = './franchise-command-center.html?franchise_id=' + encodeURIComponent(currentFranchise.franchise_id);
  } else {
    window.location.href = './franchise-select-team.html';
  }
}

/** Tutorial alert "I'll do this later" for Player Attributes → FCC when a franchise exists. */
function getFranchiseCommandCenterUrlForLater() {
  if (!currentFranchise || !currentFranchise.franchise_id) return null;
  var fid = currentFranchise.franchise_id;
  var tid = currentFranchise.user_team_id || (typeof localStorage !== 'undefined' ? localStorage.getItem('franchise_user_team_id') : null);
  if (typeof buildFranchiseLockerRoomUrl === 'function') {
    return buildFranchiseLockerRoomUrl(fid, tid);
  }
  return './franchise-command-center.html?mode=franchise&franchise_id=' + encodeURIComponent(fid) +
    (tid ? '&team_id=' + encodeURIComponent(tid) : '');
}

window.GOBModeSelect = window.GOBModeSelect || {};
window.GOBModeSelect.getFranchiseCommandCenterUrlForLater = getFranchiseCommandCenterUrlForLater;

const newFranchiseModal = document.getElementById('new-franchise-modal');
const newFranchiseDontShowAgain = document.getElementById('new-franchise-dont-show-again');
const newFranchiseModalCancel = document.getElementById('new-franchise-modal-cancel');
const newFranchiseModalConfirm = document.getElementById('new-franchise-modal-confirm');
const DONT_SHOW_NEW_FRANCHISE_WARNING_KEY = 'gob_dont_show_new_franchise_warning';

function openNewFranchiseModal() {
  if (newFranchiseModal) newFranchiseModal.style.display = 'flex';
}

function closeNewFranchiseModal() {
  if (newFranchiseModal) newFranchiseModal.style.display = 'none';
}

function goToNewFranchise() {
  window.location.href = './franchise-select-team.html';
}

async function startNewFranchiseFlow() {
  playSound('click-beep.wav');
  const dontShow = typeof localStorage !== 'undefined' && localStorage.getItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY) === '1';
  const hasExistingFranchise = !!currentFranchise;
  if (hasExistingFranchise && !dontShow) {
    openNewFranchiseModal();
    return;
  }
  if (hasExistingFranchise && dontShow) {
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/delete-current'), {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (res.ok) clearFranchiseLocalStorage();
    } catch (e) {
      console.warn('[mode-select] delete-current franchise (dontShow path):', e);
    }
  }
  goToNewFranchise();
}

if (franchisePlayNowBtn) {
  franchisePlayNowBtn.addEventListener('click', function () {
    playSound('click-strong.wav');
    goToFranchiseCommandCenter();
  });
  franchisePlayNowBtn.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      playSound('click-strong.wav');
      goToFranchiseCommandCenter();
    }
  });
}

if (franchiseEnterBtn) {
  franchiseEnterBtn.addEventListener('click', function (event) {
    event.stopPropagation();
    playSound('click-strong.wav');
    goToFranchiseCommandCenter();
  });
}

if (franchiseNewBtn) {
  franchiseNewBtn.addEventListener('click', startNewFranchiseFlow);
}

if (franchiseDeleteLink) {
  franchiseDeleteLink.addEventListener('click', function (event) {
    event.stopPropagation();
    startNewFranchiseFlow();
  });
}

if (newFranchiseModalCancel) {
  newFranchiseModalCancel.addEventListener('click', closeNewFranchiseModal);
}

if (newFranchiseModalConfirm) {
  newFranchiseModalConfirm.addEventListener('click', async function () {
    if (newFranchiseDontShowAgain && newFranchiseDontShowAgain.checked && typeof localStorage !== 'undefined') {
      localStorage.setItem(DONT_SHOW_NEW_FRANCHISE_WARNING_KEY, '1');
    }
    closeNewFranchiseModal();
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/delete-current'), {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        console.warn('[mode-select] delete-current franchise failed:', res.status);
      } else {
        clearFranchiseLocalStorage();
      }
    } catch (e) {
      console.warn('[mode-select] delete-current franchise error:', e);
    }
    goToNewFranchise();
  });
}

document.addEventListener('DOMContentLoaded', async function () {
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

  const authLoggedOut = document.getElementById('auth-logged-out');
  const authLoggedIn = document.getElementById('auth-logged-in');
  const authUserEmail = document.getElementById('auth-user-email');
  const logoutBtn = document.getElementById('logout-btn');
  const authToken = localStorage.getItem('auth_token');
  const authUser = localStorage.getItem('auth_user');
  let currentUsername = '';

  wireAlphaBanner();

  if (authToken && authUser) {
    try {
      const user = JSON.parse(authUser);
      currentUsername = user.username || user.email || '';
      if (authLoggedOut) authLoggedOut.style.display = 'none';
      if (authLoggedIn) authLoggedIn.style.display = 'flex';
      if (authUserEmail) authUserEmail.textContent = user.username || user.email;

      const meRes = await fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: getAuthHeaders() });
      if (meRes.ok) {
        const meData = await meRes.json();
        if (meData.username && meData.username.trim()) {
          currentUsername = meData.username;
          if (authUserEmail) authUserEmail.textContent = meData.username;
          const stored = JSON.parse(authUser);
          stored.username = meData.username;
          localStorage.setItem('auth_user', JSON.stringify(stored));
        }
      } else if (meRes.status === 401) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        if (authLoggedOut) authLoggedOut.style.display = 'flex';
        if (authLoggedIn) authLoggedIn.style.display = 'none';
      }
    } catch (e) {
      console.error('[AUTH] Failed to parse user:', e);
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      if (authLoggedOut) authLoggedOut.style.display = 'flex';
      if (authLoggedIn) authLoggedIn.style.display = 'none';
    }
  }

  setLeaderboardView('geek_points');
  wireLeaderboardViewToggles(currentUsername);
  await loadCommunityLeaderboard(currentUsername);
  await loadCommunityHighlights();
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
  const currentFranchiseData = await safeJsonFetch(API_CONFIG.buildUrl('/franchise/current'), { headers: headers });
  currentFranchise = currentFranchiseData;

  const teamsData = await safeJsonFetch(API_CONFIG.buildUrl('/teams'), { headers: headers }) || [];
  const teamsByName = {};
  teamsData.forEach(function (team) {
    if (team && team.name) teamsByName[team.name] = team;
  });

  if (!currentFranchise) {
    renderFranchiseEmptyState();
    return;
  }

  const commandCenterData = await safeJsonFetch(
    API_CONFIG.buildUrl('/franchise/command-center/data?franchise_id=' + encodeURIComponent(currentFranchise.franchise_id)),
    { headers: headers }
  );

  const teamName = safeText(currentFranchise.user_team_id, '');
  const teamDoc = teamsByName[teamName] || null;
  renderFranchiseActiveState(currentFranchise, teamDoc, commandCenterData);
});
