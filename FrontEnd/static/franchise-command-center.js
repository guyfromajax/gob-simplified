async function fetchJSON(url) {
  try {
    const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
    if (res.status === 401 || res.status === 403) {
      if (typeof AccessDenied !== 'undefined' && AccessDenied.checkAccessDenied) {
        AccessDenied.checkAccessDenied(res);
      }
      return null;
    }
    if (!res.ok) throw new Error('Request failed');
    return await res.json();
  } catch (err) {
    console.error('Failed loading', url, err);
    return null;
  }
}

let franchiseId = null;
const userTeamName = localStorage.getItem('franchise_user_team') || '';
// ✅ SS&S: Store team ObjectId for consistent navigation
let userTeamId = null; // Will be resolved from command center data or URL params
let userTeamNameForLeaders = null; // Store user team name for leaderboard highlighting
let userConference = null; // User team's conference (for Stats/Traits scope)
let userRegion = null;    // User team's region (for Stats/Traits scope)
let teamColorCache = null; // Cache for team primary colors
let teamMetaByNameCache = null;
let leadersDataCache = null;
let teamStatsDataCache = null;
let teamTraitsDataCache = null;
let leanRecruitsDataCache = [];
let signedRecruitsDataCache = [];
let commandCenterTopDataCache = null;
let playbooksWeekSavedCache = null;
let userRosterPlayersCache = [];
let userScheduleDataCache = null;
let homeLastGameDataCache = null;
const homeOpponentRosterCache = new Map();
const FCC_SESSION_CACHE_PREFIX = 'fcc-shell';
let statsScope = 'conference';   // 'conference' | 'region' | 'national'
let traitsScope = 'conference';
const FCC_DEFAULT_PRIMARY = '#27408E';
const FCC_DEFAULT_TOP = '#3551A5';
const FCC_DEFAULT_DEEP = '#1C2D60';
const ATTR_HEADERS = ["SC","SH","ID","OD","PS","BH","RB","AG","ST","ND","IQ","FT"];
const recruitSortState = { key: 'rt', direction: 'desc' };
const HOME_EMOJI_BUCKETS = [
  { emoji: '😡', min: 0, maxExclusive: 20 },
  { emoji: '😕', min: 20, maxExclusive: 40 },
  { emoji: '😐', min: 40, maxExclusive: 60 },
  { emoji: '😊', min: 60, maxExclusive: 80 },
  { emoji: '😎', min: 80, maxExclusive: Infinity }
];

function hideFccLoadingOverlay() {
  if (window.PageLoadOverlay && window.PageLoadOverlay.hide) window.PageLoadOverlay.hide();
  if (typeof AccessDenied !== 'undefined' && AccessDenied.hideLoadingOverlay) AccessDenied.hideLoadingOverlay();
}

window.addEventListener('pageshow', () => {
  maybeRefreshPlaybooksButtonState();
});

window.addEventListener('focus', () => {
  maybeRefreshPlaybooksButtonState();
});

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') {
    maybeRefreshPlaybooksButtonState();
  }
});

function getFccSessionCacheKey() {
  return `${FCC_SESSION_CACHE_PREFIX}:${franchiseId || ''}`;
}

function readFccSessionCache() {
  if (!franchiseId || typeof sessionStorage === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(getFccSessionCacheKey());
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    console.warn('Failed to read FCC session cache:', error);
    return null;
  }
}

function persistFccSessionCache() {
  if (!franchiseId || typeof sessionStorage === 'undefined') return;
  try {
    const payload = {
      topData: commandCenterTopDataCache || null,
      standingsData: standingsDataCache || null,
      rosterPlayers: Array.isArray(userRosterPlayersCache) ? userRosterPlayersCache : [],
      teamData: teamData || null,
      scheduleData: userScheduleDataCache || null,
      lastGameDataCache: homeLastGameDataCache || null,
      opponentRosters: Array.from(homeOpponentRosterCache.entries())
    };
    sessionStorage.setItem(getFccSessionCacheKey(), JSON.stringify(payload));
  } catch (error) {
    console.warn('Failed to persist FCC session cache:', error);
  }
}

function restoreFccSessionCache() {
  const cached = readFccSessionCache();
  if (!cached) return false;
  commandCenterTopDataCache = cached.topData || null;
  standingsDataCache = cached.standingsData || null;
  userRosterPlayersCache = Array.isArray(cached.rosterPlayers) ? cached.rosterPlayers : [];
  teamData = cached.teamData || null;
  userScheduleDataCache = cached.scheduleData || null;
  homeLastGameDataCache = cached.lastGameDataCache || null;
  homeOpponentRosterCache.clear();
  (cached.opponentRosters || []).forEach(([teamId, players]) => {
    if (teamId) homeOpponentRosterCache.set(String(teamId), players || []);
  });
  return !!(commandCenterTopDataCache || standingsDataCache || userRosterPlayersCache.length || teamData || userScheduleDataCache);
}

function invalidateHomeWeekSensitiveCaches() {
  userScheduleDataCache = null;
  homeLastGameDataCache = null;
  homeOpponentRosterCache.clear();
}

function buildPlayerDetailUrl(playerId) {
  const qs = new URLSearchParams();
  qs.set('id', playerId);
  if (franchiseId) qs.set('mode', 'franchise');
  if (franchiseId) qs.set('franchise_id', franchiseId);
  qs.set('return_url', getCurrentRelativeUrl());
  return `/player-detail.html?${qs.toString()}`;
}

const teamMap = {
  "Four Corners": "FC",
  "Bentley-Truman": "BT",
  "Lancaster": "Lan",
  "Little York": "LY",
  "Morristown": "Mor",
  "Ocean City": "OC",
  "South Lancaster": "SL",
  "Xavien": "Xav",
};

const teamIdNameMap = {};
const teamIdMetaMap = {};

function formatConferenceTooltipLabel(conference) {
  const numericConference = Number(conference);
  if (!Number.isInteger(numericConference) || numericConference < 1 || numericConference > 16) {
    return String(conference || '');
  }
  const regionLetter = String.fromCharCode(65 + Math.floor((numericConference - 1) / 2));
  const conferenceNumber = ((numericConference - 1) % 2) + 1;
  return `${conferenceNumber}${regionLetter}`;
}

function populateTop(data) {
  if (!data) return;
  const formattedTeam = formatTeamName(data.team);
  const logoSrc = typeof getTeamAssetPath === 'function' ? getTeamAssetPath(data.team, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg';
  document.getElementById('team-logo').src = logoSrc;
  const seasonLabelEl = document.getElementById('fcc-season-label');
  if (seasonLabelEl) {
    const seasonNumber = Number(data.current_season || 1);
    const weekNumber = Number(data.week || 1);
    seasonLabelEl.textContent = `Season ${seasonNumber} / Week ${weekNumber}`;
  }
  updateTopRecordLabel();
  console.log('Team logo URL:', logoSrc);

  const abbr = teamMap[formattedTeam];
  const sammyEl = document.getElementById('coach-sammy');
  const dukeEl = document.getElementById('coach-duke');
  if (abbr) {
    if (sammyEl) {
      sammyEl.src = `/images/coaches/${abbr}/Sammy-${abbr}.png`;
      console.log('Coach Sammy URL:', sammyEl.src);
    }
    if (dukeEl) {
      dukeEl.src = `/images/coaches/${abbr}/Duke-${abbr}.png`;
      console.log('Coach Duke URL:', dukeEl.src);
    }
  } else {
    if (sammyEl) sammyEl.removeAttribute('src');
    if (dukeEl) dukeEl.removeAttribute('src');
  }

  // Update chemistry bar with proportional fill
  const chemistryBar = document.querySelector('.chemistry-bar');
  if (chemistryBar) {
    const chemistryValue = data.team_chemistry || 0;
    const fillElement = chemistryBar.querySelector('.chemistry-bar-fill');
    const textElement = chemistryBar.querySelector('.chemistry-bar-text');
    
    if (fillElement) {
      const percentage = (chemistryValue / 25) * 100;
      fillElement.style.transform = `scaleX(${Math.max(0, Math.min(percentage / 100, 1))})`;
    }
    
    if (textElement) {
      textElement.textContent = `${chemistryValue} / 25`;
    }
  }
  const prestigeEl = document.getElementById('stat-prestige');
  const rankEl = document.getElementById('stat-rank');
  if (prestigeEl) prestigeEl.textContent = `Prestige: ${data.prestige || '--'}`;
  if (rankEl) rankEl.textContent = `Nat'l Rank: ${data.rank || '--'}`;
}

function updateTopRecordLabel() {
  const recordLabelEl = document.getElementById('fcc-record-label');
  if (!recordLabelEl) return;
  let wins = 0;
  let losses = 0;
  if (standingsDataCache?.standings?.length && userTeamId) {
    const teamEntry = standingsDataCache.standings.find((team) => String(team.team_id || '') === String(userTeamId));
    wins = Number(teamEntry?.W || 0);
    losses = Number(teamEntry?.L || 0);
  }
  recordLabelEl.textContent = `Record: ${wins}-${losses}`;
}

function normalizeHexColor(value) {
  const raw = String(value || '').trim();
  if (!/^#?[0-9a-fA-F]{6}$/.test(raw)) return null;
  return raw.startsWith('#') ? raw.toUpperCase() : ('#' + raw.toUpperCase());
}

function blendHexColors(baseHex, targetHex, ratio) {
  const base = normalizeHexColor(baseHex);
  const target = normalizeHexColor(targetHex);
  if (!base || !target) return null;
  const clamped = Math.max(0, Math.min(1, Number(ratio) || 0));
  const baseInt = parseInt(base.slice(1), 16);
  const targetInt = parseInt(target.slice(1), 16);
  const r = Math.round(((baseInt >> 16) & 255) * (1 - clamped) + ((targetInt >> 16) & 255) * clamped);
  const g = Math.round(((baseInt >> 8) & 255) * (1 - clamped) + ((targetInt >> 8) & 255) * clamped);
  const b = Math.round((baseInt & 255) * (1 - clamped) + (targetInt & 255) * clamped);
  return '#' + [r, g, b].map((part) => part.toString(16).padStart(2, '0')).join('').toUpperCase();
}

function applyFccDisplayColor(displayColor, teamPrimaryColor) {
  const root = document.documentElement;
  const useTeamColor = displayColor === 'team_colors' && normalizeHexColor(teamPrimaryColor);
  if (!root) return;
  if (!useTeamColor) {
    root.style.setProperty('--fcc-primary', FCC_DEFAULT_PRIMARY);
    root.style.setProperty('--fcc-primary-top', FCC_DEFAULT_TOP);
    root.style.setProperty('--fcc-primary-deep', FCC_DEFAULT_DEEP);
    return;
  }
  const primary = normalizeHexColor(teamPrimaryColor);
  const top = blendHexColors(primary, '#FFFFFF', 0.18) || FCC_DEFAULT_TOP;
  const deep = blendHexColors(primary, '#000000', 0.34) || FCC_DEFAULT_DEEP;
  root.style.setProperty('--fcc-primary', primary);
  root.style.setProperty('--fcc-primary-top', top);
  root.style.setProperty('--fcc-primary-deep', deep);
}

function getGobDisplayColorContext() {
  const teamPrimaryColor = normalizeHexColor(commandCenterTopDataCache?.primary_color);
  return {
    mode: 'franchise',
    hasActiveFranchiseTeam: !!(franchiseId && (userTeamId || commandCenterTopDataCache?.team_id) && teamPrimaryColor),
    teamPrimaryColor: teamPrimaryColor
  };
}

window.getGobDisplayColorContext = getGobDisplayColorContext;

function emitDisplayContextUpdate() {
  try {
    window.__gobDisplayColorContext = getGobDisplayColorContext();
    window.dispatchEvent(new CustomEvent('gob:display-context-updated', {
      detail: window.__gobDisplayColorContext
    }));
  } catch (error) {}
}

function syncFccDisplayColorFromAccountSettings(meData) {
  const displayColor = meData?.account_settings?.display_color === 'team_colors' ? 'team_colors' : 'default';
  applyFccDisplayColor(displayColor, commandCenterTopDataCache?.primary_color);
}

async function hydrateFccDisplayColorPreference() {
  if (window.__gobAuthMeData) {
    syncFccDisplayColorFromAccountSettings(window.__gobAuthMeData);
    return;
  }
  if (typeof API_CONFIG === 'undefined' || !API_CONFIG.buildUrl || !API_CONFIG.getAuthHeaders) {
    applyFccDisplayColor('default');
    return;
  }
  try {
    const response = await fetch(API_CONFIG.buildUrl('/api/auth/me'), { headers: API_CONFIG.getAuthHeaders() });
    if (!response.ok) {
      applyFccDisplayColor('default');
      return;
    }
    const meData = await response.json();
    syncFccDisplayColorFromAccountSettings(meData);
  } catch (error) {
    applyFccDisplayColor('default');
  }
}

window.addEventListener('gob:auth-me-loaded', (event) => {
  syncFccDisplayColorFromAccountSettings(event.detail || {});
});

window.addEventListener('gob:account-settings-updated', (event) => {
  syncFccDisplayColorFromAccountSettings(event.detail || {});
});

let standingsDataCache = null;

function buildTeamLink(t) {
  const returnUrl = encodeURIComponent(getCurrentRelativeUrl());
  const teamLink = document.createElement('a');
  teamLink.href = `/team-roster-view.html?mode=franchise&franchise_id=${franchiseId}&team_id=${encodeURIComponent(t.team_id)}&team_name=${encodeURIComponent(t.name)}&return_tab=standings-tab&return_url=${returnUrl}`;
  const rank = Number(t?.natl_rank);
  const rankPrefix = Number.isFinite(rank) && rank >= 1 && rank <= 25 ? `#${rank} ` : '';
  teamLink.textContent = `${rankPrefix}${t.name}`;
  teamLink.style.color = '#4a90e2';
  teamLink.style.textDecoration = 'none';
  teamLink.style.cursor = 'pointer';
  teamLink.addEventListener('mouseenter', () => { teamLink.style.textDecoration = 'underline'; });
  teamLink.addEventListener('mouseleave', () => { teamLink.style.textDecoration = 'none'; });
  return teamLink;
}

function buildStandingsCard(titleText, teams) {
  const card = document.createElement('section');
  card.className = 'fcc-standings-card';

  const title = document.createElement('div');
  title.className = 'fcc-standings-card-title';
  title.textContent = titleText;
  card.appendChild(title);

  const headerRow = document.createElement('div');
  headerRow.className = 'fcc-standings-row fcc-standings-row-header';
  headerRow.innerHTML = [
    '<span class="fcc-standings-col-team">Team</span>',
    '<span class="fcc-standings-col-stat">W</span>',
    '<span class="fcc-standings-col-stat">L</span>',
    '<span class="fcc-standings-col-stat">PF</span>',
    '<span class="fcc-standings-col-stat">PA</span>',
    '<span class="fcc-standings-col-next">Next</span>'
  ].join('');
  card.appendChild(headerRow);

  const body = document.createElement('div');
  body.className = 'fcc-standings-card-body';

  teams.forEach((t) => {
    const row = document.createElement('div');
    row.className = 'fcc-standings-row';

    const teamCell = document.createElement('span');
    teamCell.className = 'fcc-standings-col-team';
    teamCell.appendChild(buildTeamLink(t));
    row.appendChild(teamCell);

    const wCell = document.createElement('span');
    wCell.className = 'fcc-standings-col-stat';
    wCell.textContent = t.W;
    row.appendChild(wCell);

    const lCell = document.createElement('span');
    lCell.className = 'fcc-standings-col-stat';
    lCell.textContent = t.L;
    row.appendChild(lCell);

    const pfCell = document.createElement('span');
    pfCell.className = 'fcc-standings-col-stat';
    pfCell.textContent = t.PF;
    row.appendChild(pfCell);

    const paCell = document.createElement('span');
    paCell.className = 'fcc-standings-col-stat';
    paCell.textContent = t.PA;
    row.appendChild(paCell);

    const nextCell = document.createElement('span');
    nextCell.className = 'fcc-standings-col-next';
    nextCell.textContent = t.next || '';
    row.appendChild(nextCell);

    body.appendChild(row);
  });

  card.appendChild(body);
  return card;
}

function renderStandings(data, selectedRegion) {
  if (!data) return;
  const list = data.standings || [];
  updateTopRecordLabel();
  list.forEach(t => { teamIdNameMap[t.team_id] = t.name; });

  const container = document.getElementById('standings-by-region');
  if (!container) return;
  container.innerHTML = '';

  // FCC slim view: two blocks (user conference, sister conference) when API returned user_conference/sister_conference
  const userConf = data.user_conference;
  const sisterConf = data.sister_conference;
  if (userConf != null && sisterConf != null && list.length > 0) {
    const regionLabels = { 1: 'A1', 2: 'A2', 3: 'B1', 4: 'B2', 5: 'C1', 6: 'C2', 7: 'D1', 8: 'D2', 9: 'E1', 10: 'E2', 11: 'F1', 12: 'F2', 13: 'G1', 14: 'G2', 15: 'H1', 16: 'H2' };
    [userConf, sisterConf].forEach((confNum) => {
      const teams = list.filter(t => t.conference === confNum);
      if (teams.length === 0) return;
      const label = regionLabels[confNum] ? `Conference ${regionLabels[confNum]}` : `Conference ${confNum}`;
      container.appendChild(buildStandingsCard(label, teams));
    });
    return;
  }

  // Fallback: full standings by region (e.g. from standalone standings page)
  selectedRegion = selectedRegion || 'A';
  const byRegion = list.filter(t => (t.region || '').toString().toUpperCase() === selectedRegion);
  const byConference = {};
  byRegion.forEach(t => {
    const c = t.conference != null ? t.conference : 0;
    if (!byConference[c]) byConference[c] = [];
    byConference[c].push(t);
  });
  const confNumbers = Object.keys(byConference).map(Number).sort((a, b) => a - b);

  confNumbers.forEach(confNum => {
    const teams = byConference[confNum];
    teams.sort((a, b) => (b.W - a.W) || (b.differential - a.differential));
    container.appendChild(buildStandingsCard(`Conference ${selectedRegion}${confNum}`, teams));
  });

  document.querySelectorAll('.standings-region-btn').forEach(btn => {
    if (btn) btn.classList.toggle('active', btn.getAttribute('data-region') === selectedRegion);
  });
}

function escapeHomeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function getPlayerSeasonStats(player) {
  return player?.stats?.season || {};
}

function getGamesPlayed(player) {
  const stats = getPlayerSeasonStats(player);
  return Number(stats.GP || 0) || 0;
}

function formatPerGame(total, gamesPlayed) {
  if (!gamesPlayed) return '0.0';
  return (Number(total || 0) / gamesPlayed).toFixed(1);
}

function getPlayerDisplayName(player) {
  return `${player?.first_name || ''} ${player?.last_name || ''}`.trim() || player?.name || 'Unknown';
}

function getPlayerTotalRebounds(player) {
  const stats = getPlayerSeasonStats(player);
  return Number(stats.TREB || ((stats.OREB || 0) + (stats.DREB || 0)) || 0);
}

function getDisplayPlayerNameForStats(player) {
  const base = `${player?.first_name || ''} ${player?.last_name || ''}`.trim() || player?.name || '';
  return typeof formatNameWithJersey === 'function' ? formatNameWithJersey(player?.jersey, base) : base;
}

function getTopPlayerByAverage(players, totalResolver) {
  let best = null;
  let bestAvg = -1;
  (players || []).forEach((player) => {
    const gp = getGamesPlayed(player);
    if (!gp) return;
    const average = Number(totalResolver(player) || 0) / gp;
    if (average > bestAvg) {
      best = player;
      bestAvg = average;
    }
  });
  return { player: best, average: bestAvg > -1 ? bestAvg : 0 };
}

function getPlayerPpg(player) {
  return Number(formatPerGame(getPlayerSeasonStats(player).PTS || 0, getGamesPlayed(player)));
}

function getPlayerRt(player) {
  if (player?.rt != null) return Number(player.rt) || 0;
  if (player?.position_ratings && typeof getBestPosition === 'function') {
    try {
      return Number(getBestPosition(player.position_ratings || {}).rating || 0);
    } catch (error) {
      return 0;
    }
  }
  return 0;
}

function getScheduleDisplayName(teamId) {
  if (!userScheduleDataCache) return '';
  const display = userScheduleDataCache.team_display_name_map?.[teamId];
  const fallback = userScheduleDataCache.team_name_map?.[teamId];
  return display || fallback || '';
}

function formatConferenceShortLabel(conference) {
  const numericConference = Number(conference);
  if (!Number.isInteger(numericConference) || numericConference < 1 || numericConference > 16) return '';
  const regionLetter = String.fromCharCode(65 + Math.floor((numericConference - 1) / 2));
  const conferenceNumber = ((numericConference - 1) % 2) + 1;
  return `${regionLetter}${conferenceNumber}`;
}

function getTeamTooltipText(teamName) {
  if (!teamName) return '';
  const meta = teamMetaByNameCache?.[teamName] || null;
  const mascot = String(meta?.mascot || '').trim();
  return mascot ? `${teamName} ${mascot}` : String(teamName);
}

function getTeamRankingEntry(teamId) {
  return (commandCenterTopDataCache?.rankings || []).find((entry) => String(entry.team_id) === String(teamId)) || null;
}

function getUserScheduleGames() {
  const weeks = userScheduleDataCache?.schedule || [];
  return weeks.flat().filter((game) => game && game.is_user_team);
}

function getOpponentIdFromGame(game) {
  if (!game || !userTeamId) return null;
  return String(game.home_team_id) === String(userTeamId) ? String(game.away_team_id) : String(game.home_team_id);
}

function getMatchupLabelForGame(game) {
  if (!game || !userTeamId) return '';
  return String(game.home_team_id) === String(userTeamId) ? 'vs' : '@';
}

function getNextUserGame() {
  const currentWeek = Number(commandCenterTopDataCache?.week || 1);
  return getUserScheduleGames().find((game) => Number(game.week || 0) >= currentWeek && game.status !== 'complete') || null;
}

function getLastCompletedUserGame() {
  const currentWeek = Number(commandCenterTopDataCache?.week || 1);
  const games = getUserScheduleGames()
    .filter((game) => {
      const week = Number(game.week || 0);
      const awayScore = game.away_score;
      const homeScore = game.home_score;
      const hasRecordedScore =
        awayScore !== null &&
        awayScore !== undefined &&
        homeScore !== null &&
        homeScore !== undefined;
      const hasRealFinalScore =
        hasRecordedScore &&
        (Number(awayScore) > 0 || Number(homeScore) > 0);
      const looksComplete = game.status === 'complete' || hasRealFinalScore;
      return looksComplete && week <= currentWeek;
    })
    .sort((a, b) => Number(b.week || 0) - Number(a.week || 0));
  return games[0] || null;
}

async function fetchRosterWithStatsForTeam(teamId) {
  if (!franchiseId || !teamId) return [];
  if (homeOpponentRosterCache.has(teamId)) return homeOpponentRosterCache.get(teamId);
  const rosterUrl = `${API_CONFIG.buildUrl(`/roster/${encodeURIComponent(teamId)}`)}?franchise_id=${encodeURIComponent(franchiseId)}`;
  const stateUrl = `${API_CONFIG.buildUrl('/franchise/state')}?franchise_id=${encodeURIComponent(franchiseId)}`;
  try {
    const result = await RosterLoader.loadRosterWithStats(rosterUrl, stateUrl);
    const players = result?.players || [];
    homeOpponentRosterCache.set(teamId, players);
    persistFccSessionCache();
    return players;
  } catch (error) {
    console.warn('Failed to load opponent roster for Home tab:', teamId, error);
    return [];
  }
}

async function ensureHomeScheduleData() {
  if (userScheduleDataCache || !franchiseId) return userScheduleDataCache;
  const params = new URLSearchParams();
  params.set('franchise_id', franchiseId);
  if (userConference != null) params.set('conference', String(userConference));
  userScheduleDataCache = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/schedule')}?${params.toString()}`);
  persistFccSessionCache();
  return userScheduleDataCache;
}

async function ensureHomeLastGameData(game) {
  if (!game?.game_id) return null;
  if (homeLastGameDataCache && homeLastGameDataCache.game_id === game.game_id) return homeLastGameDataCache.data;
  const data = await fetchJSON(`${API_CONFIG.buildUrl(`/api/game/${encodeURIComponent(game.game_id)}`)}`);
  if (data) {
    homeLastGameDataCache = { game_id: game.game_id, data };
    persistFccSessionCache();
  }
  return data;
}

function createEmptyHomeState(message = 'N/A') {
  return `<div class="fcc-home-empty">${escapeHomeHtml(message)}</div>`;
}

function renderHomeStandingsCard() {
  const body = document.getElementById('home-standings-body');
  if (!body) return;
  if (!standingsDataCache?.standings || userConference == null) {
    body.innerHTML = createEmptyHomeState('Loading...');
    return;
  }
  const teams = standingsDataCache.standings
    .filter((team) => Number(team.conference) === Number(userConference))
    .sort((a, b) => (Number(b.W || 0) - Number(a.W || 0)) || (Number(b.differential || 0) - Number(a.differential || 0)));
  if (!teams.length) {
    body.innerHTML = createEmptyHomeState();
    return;
  }

  const rows = teams.map((team) => `
    <div class="fcc-home-standings-row">
      <span class="fcc-home-standings-team">${escapeHomeHtml(team.name || '')}</span>
      <span class="fcc-home-standings-stat">${escapeHomeHtml(team.W ?? 0)}</span>
      <span class="fcc-home-standings-stat">${escapeHomeHtml(team.L ?? 0)}</span>
      <span class="fcc-home-standings-stat">${escapeHomeHtml(team.PF ?? 0)}</span>
      <span class="fcc-home-standings-stat">${escapeHomeHtml(team.PA ?? 0)}</span>
    </div>
  `).join('');

  body.innerHTML = `
    <div class="fcc-home-standings">
      <div class="fcc-home-standings-row fcc-home-standings-row-header">
        <span class="fcc-home-standings-team">Team</span>
        <span class="fcc-home-standings-stat">W</span>
        <span class="fcc-home-standings-stat">L</span>
        <span class="fcc-home-standings-stat">PF</span>
        <span class="fcc-home-standings-stat">PA</span>
      </div>
      <div class="fcc-home-list-scroll">${rows}</div>
    </div>
  `;
}

function renderHomeRankingsCard() {
  const body = document.getElementById('home-rankings-body');
  if (!body) return;
  const rankings = (commandCenterTopDataCache?.rankings || []).slice(0, 10);
  if (!rankings.length) {
    body.innerHTML = createEmptyHomeState('Loading...');
    return;
  }
  body.innerHTML = `
    <div class="fcc-home-list-scroll">
      ${rankings.map((team) => `
        <div class="fcc-home-list-row">
          <span class="fcc-home-list-rank">${escapeHomeHtml(team.natl_rank)}</span>
          <span class="fcc-home-list-main">${escapeHomeHtml(`${team.team_name || ''}${formatConferenceShortLabel(team.conference) ? ` (${formatConferenceShortLabel(team.conference)})` : ''}`)}</span>
          <span class="fcc-home-list-meta">${escapeHomeHtml(`${team.W || 0}-${team.L || 0}`)}</span>
        </div>
      `).join('')}
    </div>
  `;
}

function renderHomeMatchupCard(bodyId, summary) {
  const body = document.getElementById(bodyId);
  if (!body) return;
  if (!summary) {
    body.innerHTML = createEmptyHomeState('N/A');
    return;
  }
  const opponentName = summary.opponent_team_name || 'Opponent';
  const matchupLabel = summary.matchup_label || '';
  const logoSrc = typeof getTeamAssetPath === 'function'
    ? getTeamAssetPath(opponentName, 'banner_primary')
    : '/images/teams/general/general_banner_primary.jpg';
  const tooltipText = getTeamTooltipText(opponentName);

  if (bodyId === 'home-next-game-body') {
    body.innerHTML = `
      <div class="fcc-home-matchup-card">
        <div class="fcc-home-matchup-top">
          <span class="fcc-home-matchup-label">${escapeHomeHtml(matchupLabel)}</span>
          <span class="team-tooltip-host" data-team-tooltip="${escapeHomeHtml(tooltipText)}" aria-label="${escapeHomeHtml(tooltipText)}">
            <img class="fcc-home-matchup-logo" src="${escapeHomeHtml(logoSrc)}" alt="${escapeHomeHtml(opponentName)} banner">
          </span>
        </div>
        <div class="fcc-home-matchup-bottom">
          <div class="fcc-home-detail-line">Record: ${escapeHomeHtml(`${summary.record?.wins || 0}-${summary.record?.losses || 0}`)}</div>
          <div class="fcc-home-detail-line">Rank: ${escapeHomeHtml(summary.rank || 'N/A')}</div>
          <div class="fcc-home-detail-line">Top Scorer: ${escapeHomeHtml(summary.top_scorer ? `${summary.top_scorer.name}, ${Number(summary.top_scorer.average || 0).toFixed(1)}` : 'N/A')}</div>
          <div class="fcc-home-detail-line">Top Rebounder: ${escapeHomeHtml(summary.top_rebounder ? `${summary.top_rebounder.name}, ${Number(summary.top_rebounder.average || 0).toFixed(1)}` : 'N/A')}</div>
        </div>
      </div>
    `;
    return;
  }

  const awayName = summary.away_team_name || 'Away';
  const homeName = summary.home_team_name || 'Home';
  const awayScore = Number(summary.away_score || 0);
  const homeScore = Number(summary.home_score || 0);
  const awayBold = awayScore > homeScore ? 'fcc-home-score-strong' : '';
  const homeBold = homeScore > awayScore ? 'fcc-home-score-strong' : '';

  body.innerHTML = `
    <div class="fcc-home-matchup-card">
      <div class="fcc-home-matchup-top">
        <span class="fcc-home-matchup-label">${escapeHomeHtml(matchupLabel)}</span>
        <span class="team-tooltip-host" data-team-tooltip="${escapeHomeHtml(tooltipText)}" aria-label="${escapeHomeHtml(tooltipText)}">
          <img class="fcc-home-matchup-logo" src="${escapeHomeHtml(logoSrc)}" alt="${escapeHomeHtml(opponentName)} banner">
        </span>
      </div>
      <div class="fcc-home-matchup-bottom">
        <div class="fcc-home-final-score">
          <span class="${awayBold}">${escapeHomeHtml(`${awayName} (${awayScore})`)}</span>
          <span class="fcc-home-final-score-at">at</span>
          <span class="${homeBold}">${escapeHomeHtml(`${homeName} (${homeScore})`)}</span>
        </div>
        <div class="fcc-home-detail-line">Player of The Game: ${escapeHomeHtml(summary.potg?.name || 'N/A')}</div>
        <div class="fcc-home-detail-line fcc-home-potg-line">
          ${escapeHomeHtml(summary.potg ? `${summary.potg.stats.pts} PTS  ${summary.potg.stats.reb} REB  ${summary.potg.stats.ast} AST  ${summary.potg.stats.stl} STL  ${summary.potg.stats.blk} BLK  ${summary.potg.stats.defPct} DEF%` : 'N/A')}
        </div>
      </div>
    </div>
  `;
}

function renderHomeLockerRoomCard() {
  const body = document.getElementById('home-locker-room-body');
  if (!body) return;
  if (!teamData?.team_attributes || !userRosterPlayersCache.length) {
    body.innerHTML = createEmptyHomeState('Loading...');
    return;
  }

  const chemistry = Number(teamData.team_attributes.team_chemistry || 0);
  const chemistryPercent = Math.max(0, Math.min(100, (chemistry / 25) * 100));
  const attitudeCounts = HOME_EMOJI_BUCKETS.map((bucket) => {
    const count = userRosterPlayersCache.filter((player) => {
      const em = Number(player?.attributes?.EM || 0);
      return em >= bucket.min && em < bucket.maxExclusive;
    }).length;
    return { ...bucket, count };
  });

  body.innerHTML = `
    <div class="fcc-home-locker-room">
      <div class="fcc-home-locker-label">Team Chemistry</div>
      <div class="fcc-home-chemistry-bar">
        <div class="fcc-home-chemistry-fill" style="width:${chemistryPercent}%"></div>
        <div class="fcc-home-chemistry-text">${escapeHomeHtml(`${chemistry} / 25`)}</div>
      </div>
      <div class="fcc-home-locker-label">Player Attitudes</div>
      <div class="fcc-home-attitude-scale">
        <div class="fcc-home-attitude-emojis">
          ${attitudeCounts.map((bucket) => `<span>${bucket.emoji}</span>`).join('')}
        </div>
        <div class="fcc-home-attitude-rail">
          ${attitudeCounts.map(() => '<span class="fcc-home-attitude-tick"></span>').join('')}
        </div>
        <div class="fcc-home-attitude-counts">
          ${attitudeCounts.map((bucket) => `<span>${bucket.count}</span>`).join('')}
        </div>
      </div>
    </div>
  `;
}

function renderHomeTeamStatsCard() {
  const body = document.getElementById('home-team-stats-body');
  if (!body) return;
  if (!userRosterPlayersCache.length) {
    body.innerHTML = createEmptyHomeState('Loading...');
    return;
  }
  const players = [...userRosterPlayersCache]
    .sort((a, b) => {
      const bGp = getGamesPlayed(b);
      const aGp = getGamesPlayed(a);
      const bPpg = getPlayerPpg(b);
      const aPpg = getPlayerPpg(a);
      if (bGp === 0 && aGp === 0) {
        return getPlayerRt(b) - getPlayerRt(a);
      }
      if (bPpg !== aPpg) return bPpg - aPpg;
      return getPlayerRt(b) - getPlayerRt(a);
    })
    .slice(0, 12);
  body.innerHTML = `
    <div class="fcc-home-team-stats">
      <div class="fcc-home-team-stats-header">
        <span>Player</span>
        <span>PPG</span>
      </div>
      <div class="fcc-home-list-scroll">
        ${players.map((player, index) => `
          <div class="fcc-home-team-stats-row">
            <span class="fcc-home-team-stats-name">${escapeHomeHtml(`${index + 1}. ${getPlayerDisplayName(player)}`)}</span>
            <span class="fcc-home-team-stats-value">${escapeHomeHtml(formatPerGame(getPlayerSeasonStats(player).PTS || 0, getGamesPlayed(player)))}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderHomeRecruitingCard() {
  const body = document.getElementById('home-recruiting-body');
  if (!body) return;
  const natlRank = commandCenterTopDataCache?.rank ?? '--';
  const prestige = commandCenterTopDataCache?.prestige ?? '--';
  const recruits = [...leanRecruitsDataCache].sort((a, b) => Number(b.rt || 0) - Number(a.rt || 0));
  body.innerHTML = `
    <div class="fcc-home-recruiting">
      <div class="fcc-home-recruiting-topline">
        <span class="fcc-home-recruiting-rank">${escapeHomeHtml(`National Rank: ${natlRank}`)}</span>
        <span class="fcc-home-recruiting-prestige">${escapeHomeHtml(`Prestige: ${prestige}`)}</span>
      </div>
      <div class="fcc-home-list-scroll">
        <div class="fcc-home-recruit-header">
          <span>Recruit</span>
          <span>Arch.</span>
          <span>HT</span>
          <span>WT</span>
          <span>RT</span>
        </div>
        ${recruits.map((recruit) => `
          <div class="fcc-home-recruit-row">
            <span class="fcc-home-recruit-name">${escapeHomeHtml(recruit.name || '--')}</span>
            <span class="fcc-home-recruit-arch">${escapeHomeHtml(recruit.archetype || '--')}</span>
            <span class="fcc-home-recruit-stat">${escapeHomeHtml(recruit.height || '--')}</span>
            <span class="fcc-home-recruit-stat">${escapeHomeHtml(recruit.weight ?? '--')}</span>
            <span class="fcc-home-recruit-stat">${escapeHomeHtml(recruit.rt ?? '--')}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderHomeNewsCard() {
  const body = document.getElementById('home-news-body');
  if (!body) return;
  body.innerHTML = createEmptyHomeState('In Development');
}

async function renderHomeTab() {
  renderHomeStandingsCard();
  renderHomeRankingsCard();
  renderHomeLockerRoomCard();
  renderHomeTeamStatsCard();
  renderHomeRecruitingCard();
  renderHomeNewsCard();
  renderHomeMatchupCard('home-next-game-body', commandCenterTopDataCache?.next_game_summary || null);
  renderHomeMatchupCard('home-last-game-body', commandCenterTopDataCache?.last_game_summary || null);
}

async function loadHomeTabData() {
  await renderHomeTab();
}

function bindStandingsRegionButtons() {
  document.querySelectorAll('.standings-region-btn').forEach(btn => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => {
      const region = btn.getAttribute('data-region');
      if (standingsDataCache) renderStandings(standingsDataCache, region);
    });
  });
}

function buildResourceUrl(page, extraParams) {
  if (!franchiseId || !userTeamId) return '#';
  const params = new URLSearchParams();
  params.set('franchise_id', franchiseId);
  params.set('team_id', userTeamId);
  params.set('return_url', getCurrentRelativeUrl());
  if (extraParams) Object.keys(extraParams).forEach(k => params.set(k, extraParams[k]));
  return `/${page}?${params.toString()}`;
}

async function updatePlaybooksButtonState(topData) {
  const playbooksBtn = document.getElementById('playbooks-franchise');
  if (!playbooksBtn || !franchiseId || !userTeamId) return;
  const currentWeek = Number(topData?.week || 1);
  const data = await fetchJSON(
    `${API_CONFIG.buildUrl('/api/playbooks')}?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`
  );
  const savedForWeek = Number(data?.playbook_meta?.saved_for_week || 0);
  playbooksWeekSavedCache = savedForWeek;
  const needsSave = savedForWeek !== currentWeek;
  playbooksBtn.classList.toggle('needs-playbook-save', needsSave);
  if (needsSave) {
    playbooksBtn.title = "Playbooks have not been set for this week's game.";
    playbooksBtn.setAttribute('aria-label', "Playbooks have not been set for this week's game.");
  } else {
    playbooksBtn.removeAttribute('title');
    playbooksBtn.removeAttribute('aria-label');
  }
}

async function maybeRefreshPlaybooksButtonState() {
  if (!commandCenterTopDataCache || !franchiseId || !userTeamId) return;
  const storageKey = `playbooks_saved_refresh:${franchiseId}:${userTeamId}`;
  let shouldRefresh = false;
  try {
    shouldRefresh = window.sessionStorage.getItem(storageKey) === '1';
  } catch (error) {
    shouldRefresh = false;
  }
  if (!shouldRefresh) return;
  await updatePlaybooksButtonState(commandCenterTopDataCache);
  try {
    window.sessionStorage.removeItem(storageKey);
  } catch (error) {
    // ignore storage cleanup failures
  }
}

function bindResourcesLinks() {
  const q = () => {
    if (!franchiseId || !userTeamId) return '';
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('return_url', getCurrentRelativeUrl());
    return `?${params.toString()}`;
  };
  const standingsLink = document.getElementById('standings-resources-link');
  if (standingsLink) standingsLink.href = `/standings.html${q()}`;
  const standingsFullLink = document.getElementById('standings-full-link');
  if (standingsFullLink) standingsFullLink.href = `/standings.html${q()}`;
  const statsNavBtn = document.getElementById('stats-nav-btn');
  if (statsNavBtn) statsNavBtn.dataset.route = `/team-stats.html${q()}`;
  const rStandings = document.getElementById('resources-standings');
  if (rStandings) rStandings.href = `/standings.html${q()}`;
  const rStats = document.getElementById('resources-stats');
  if (rStats) rStats.href = `/stats.html${q()}`;
  const rSchedule = document.getElementById('resources-schedule');
  if (rSchedule) rSchedule.href = `/schedule.html${q()}`;
  const rTraits = document.getElementById('resources-team-traits');
  if (rTraits) rTraits.href = `/team-traits.html${q()}`;
  const rRankings = document.getElementById('resources-rankings');
  if (rRankings) rRankings.href = `/rankings.html${q()}`;
  const homeRankingsFullLink = document.getElementById('home-rankings-full-link');
  if (homeRankingsFullLink) homeRankingsFullLink.href = `/rankings.html${q()}`;
  const rRecruits = document.getElementById('resources-recruits');
  if (rRecruits) rRecruits.href = `/recruiting.html${q()}${q() ? '&from=fcc' : '?from=fcc'}`;
  const rAwards = document.getElementById('resources-awards');
  if (rAwards) rAwards.href = `/awards.html${q()}${q() ? '&from=fcc' : '?from=fcc'}`;
}

function bindStatsAndTraitsScopeButtons() {
  document.querySelectorAll('.stats-scope-btn').forEach(btn => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => {
      statsScope = btn.getAttribute('data-scope') || 'conference';
      document.querySelectorAll('.stats-scope-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-scope') === statsScope));
      if (leadersDataCache) renderLeaders(leadersDataCache, statsScope);
      if (teamStatsDataCache) renderTeamStats(teamStatsDataCache, statsScope);
    });
  });
  document.querySelectorAll('.traits-scope-btn').forEach(btn => {
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('click', () => {
      traitsScope = btn.getAttribute('data-scope') || 'conference';
      document.querySelectorAll('.traits-scope-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-scope') === traitsScope));
      if (teamTraitsDataCache) renderTeamTraits(teamTraitsDataCache, traitsScope);
    });
  });
}

function renderFccRecruits() {
  const tbody = document.getElementById('fcc-recruits-body');
  const table = document.getElementById('fcc-recruits-table');
  const heading = document.querySelector('#recruits-tab h3');
  const lastCol = document.getElementById('fcc-recruits-last-col');
  const fullListCopy = document.getElementById('fcc-recruits-link-copy');
  const fullListLink = document.getElementById('fcc-recruits-full-link');
  if (!tbody || !table || typeof RecruitingCommon === 'undefined') return;

  const useSignedRecruits = Number(document.body.dataset.fccWeek || 1) >= 36;
  if (heading) heading.textContent = useSignedRecruits ? 'Signed Recruits' : 'Recruits Leaning Your Way';
  if (fullListCopy) fullListCopy.style.display = useSignedRecruits ? 'none' : 'block';
  if (fullListLink) {
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('return_url', getCurrentRelativeUrl());
    fullListLink.href = `/recruiting.html?${params.toString()}`;
  }
  if (lastCol) {
    lastCol.textContent = 'Current Lean';
    lastCol.dataset.sortKey = 'lean';
    lastCol.style.display = useSignedRecruits ? 'none' : '';
  }

  if (useSignedRecruits) {
    if (!signedRecruitsDataCache.length) {
      tbody.innerHTML = '<tr><td colspan="19">No recruits or walk-ons joined your team.</td></tr>';
      return;
    }
    const rows = RecruitingCommon.sortRecruits(signedRecruitsDataCache, recruitSortState);
    tbody.innerHTML = '';
    rows.forEach(function (recruit) {
      const tr = document.createElement('tr');
      tr.innerHTML = [
        '<td>' + recruit.name + '</td>',
        '<td>' + recruit.homeRegion + '</td>',
        '<td>' + recruit.archetype + '</td>',
        '<td>' + recruit.height + '</td>',
        '<td>' + (recruit.weight != null ? recruit.weight : '--') + '</td>',
        '<td>' + recruit.pos + '</td>',
        '<td>' + recruit.attrs.SC + '</td>',
        '<td>' + recruit.attrs.SH + '</td>',
        '<td>' + recruit.attrs.ID + '</td>',
        '<td>' + recruit.attrs.OD + '</td>',
        '<td>' + recruit.attrs.PS + '</td>',
        '<td>' + recruit.attrs.BH + '</td>',
        '<td>' + recruit.attrs.RB + '</td>',
        '<td>' + recruit.attrs.AG + '</td>',
        '<td>' + recruit.attrs.ST + '</td>',
        '<td>' + recruit.attrs.ND + '</td>',
        '<td>' + recruit.attrs.IQ + '</td>',
        '<td>' + recruit.attrs.FT + '</td>',
        '<td>' + (recruit.rt != null ? recruit.rt : '--') + '</td>'
      ].join('');
      tbody.appendChild(tr);
    });
    return;
  }

  if (!leanRecruitsDataCache.length) {
    tbody.innerHTML = '<tr><td colspan="20">No recruits currently have your team on their lean list.</td></tr>';
    return;
  }
  RecruitingCommon.renderRecruitTableRows(
    tbody,
    RecruitingCommon.sortRecruits(leanRecruitsDataCache, recruitSortState),
    {}
  );
}

function initFccRecruits(topData) {
  if (typeof RecruitingCommon === 'undefined') return;
  document.body.dataset.fccWeek = String(Number(topData?.week || 1));
  leanRecruitsDataCache = RecruitingCommon.normalizeRecruits(
    topData?.lean_recruits || [],
    topData?.team_name_map || {}
  );
  signedRecruitsDataCache = (topData?.week_35_user_recruits || []).map((player) => {
    const attrs = player.attributes || {};
    return {
      recruitId: player.recruit_id || player.player_id,
      name: player.walk_on ? player.name + ' (walk on)' : player.name,
      homeRegion: player.home_region || '--',
      archetype: player.archetype || '--',
      height: typeof formatHeight === 'function' ? formatHeight(player.height) : '--',
      heightRaw: Number(player.height) || 0,
      weight: player.weight != null ? Number(player.weight) : null,
      pos: player.pos || '--',
      rt: player.rt != null ? Number(player.rt) : null,
      leanDisplay: '',
      leanSortValue: '',
      attrs: {
        SC: Math.floor((Number(attrs.SC) || 0) / 10),
        SH: Math.floor((Number(attrs.SH) || 0) / 10),
        ID: Math.floor((Number(attrs.ID) || 0) / 10),
        OD: Math.floor((Number(attrs.OD) || 0) / 10),
        PS: Math.floor((Number(attrs.PS) || 0) / 10),
        BH: Math.floor((Number(attrs.BH) || 0) / 10),
        RB: Math.floor((Number(attrs.RB) || 0) / 10),
        AG: Math.floor((Number(attrs.AG) || 0) / 10),
        ST: Math.floor((Number(attrs.ST) || 0) / 10),
        ND: Math.floor((Number(attrs.ND) || 0) / 10),
        IQ: Math.floor((Number(attrs.IQ) || 0) / 10),
        FT: Math.floor((Number(attrs.FT) || 0) / 10)
      },
      raw: player
    };
  });
  RecruitingCommon.bindSortableHeaders(
    document.getElementById('fcc-recruits-table'),
    recruitSortState,
    renderFccRecruits
  );
  renderFccRecruits();
  if (typeof initAttributeTooltips !== 'undefined') {
    const recruitsTable = document.getElementById('fcc-recruits-table');
    if (recruitsTable) initAttributeTooltips(recruitsTable, ['th']);
  }
  void renderHomeTab();
}

let rankingsFullList = [];

function renderRankings(rankings, showAll) {
  const listEl = document.getElementById('rankings-list');
  if (!listEl) return;
  listEl.innerHTML = '';
  if (!rankings || rankings.length === 0) return;
  const toShow = showAll ? rankings : rankings.slice(0, 25);
  toShow.forEach((r) => {
    const li = document.createElement('li');
    li.appendChild(document.createTextNode(`${r.natl_rank}. `));
    const nameSpan = document.createElement('span');
    nameSpan.textContent = r.team_name;
    if (r.conference === 1) {
      nameSpan.className = 'rankings-team conference-1';
      nameSpan.style.color = r.primary_color || '#000';
      nameSpan.style.fontWeight = 'bold';
    }
    li.appendChild(nameSpan);
    listEl.appendChild(li);
  });
}

// Helper function to initialize team color cache
async function initializeTeamColorCache() {
  if (teamColorCache) return; // Already initialized
  
  try {
    const res = await fetch(API_CONFIG.buildUrl('/teams'));
    const teamData = await res.json();
    teamColorCache = {};
    teamMetaByNameCache = {};
    teamData.forEach(t => {
      teamColorCache[t.name] = t.primary_color;
      teamMetaByNameCache[t.name] = {
        mascot: t.mascot || '',
        primary_color: t.primary_color || null,
      };
    });
  } catch (err) {
    console.warn('Failed to load team colors:', err);
    teamColorCache = {};
    teamMetaByNameCache = {};
  }
}

// Helper function to get team primary color (synchronous, uses cache)
function getTeamPrimaryColor(teamName) {
  if (!teamName || !teamColorCache) return null;
  return teamColorCache[teamName] || null;
}

function filterLeadersByScope(data, scope) {
  if (!data || scope === 'national') return data;
  const out = {};
  const confMatch = scope === 'conference' && userConference != null;
  const regionMatch = scope === 'region' && userRegion != null;
  const regionNorm = (v) => (v || '').toString().toUpperCase();
  const userRegionNorm = regionNorm(userRegion);
  Object.keys(data).forEach(cat => {
    const list = data[cat] || [];
    out[cat] = list.filter((p) => {
      if (confMatch) return p.conference === userConference;
      if (regionMatch) return regionNorm(p.region) === userRegionNorm;
      return true;
    });
  });
  return out;
}

function renderLeaders(data, scope) {
  if (!data) return;
  scope = scope || statsScope;
  const filtered = filterLeadersByScope(data, scope);
  const container = document.getElementById('leaders-container');
  container.innerHTML = '';
  const preferredOrderGroups = [
    ['PTS'],
    ['3PTM', 'TPM'],
    ['REB'],
    ['AST'],
    ['BLK'],
    ['STL']
  ];
  const ordered = preferredOrderGroups
    .map(group => group.find(cat => Object.prototype.hasOwnProperty.call(filtered, cat)))
    .filter(Boolean);
  const categories = [
    ...ordered,
    ...Object.keys(filtered).filter(cat => !ordered.includes(cat))
  ];
  const primaryColor = getTeamPrimaryColor(userTeamNameForLeaders);
  
  // Map category names for display (backward compatibility for old keys)
  const categoryNameMap = {
    'PTS': 'Points',
    'TPM': '3PTM',  // Legacy key support
    '3PTM': '3PTM', // ✅ SS&S: Standardized key (backend now uses this)
    'REB': 'Rebound',
    'AST': 'Assists',
    'BLK': 'Blocks',
    'STL': 'Steals'
  };

  const valueHeaderMap = {
    'PTS': 'Points',
    'TPM': '3PT Made',
    '3PTM': '3PT Made',
    'REB': 'Rebounds',
    'AST': 'Assists',
    'BLK': 'Blocks',
    'STL': 'Steals'
  };
  
  categories.forEach(cat => {
    const section = document.createElement('div');
    const h3 = document.createElement('h3');
    h3.textContent = categoryNameMap[cat] || cat;
    section.appendChild(h3);
    const div = document.createElement('div');
    div.className = 'scroll-x';
    const table = document.createElement('table');
    table.className = 'leaders-table';
    const valueHeader = valueHeaderMap[cat] || 'Value';
    table.innerHTML = `<thead><tr><th>Rank</th><th>Player</th><th>Team</th><th>${valueHeader}</th></tr></thead>`;
    const body = document.createElement('tbody');
    (filtered[cat] || []).forEach((p, idx) => {
      const tr = document.createElement('tr');
      const isUserTeam = userTeamNameForLeaders && p.team === userTeamNameForLeaders;
      
      // Create cells individually to apply styling
      const rankCell = document.createElement('td');
      rankCell.textContent = idx + 1;
      const playerCell = document.createElement('td');
      playerCell.textContent = p.name;
      const teamCell = document.createElement('td');
      teamCell.textContent = p.team;
      const valueCell = document.createElement('td');
      valueCell.textContent = p.value;
      
      // Apply bold and color if user team player
      if (isUserTeam && primaryColor) {
        [rankCell, playerCell, teamCell, valueCell].forEach(cell => {
          cell.style.fontWeight = 'bold';
          cell.style.color = primaryColor;
        });
      }
      
      tr.appendChild(rankCell);
      tr.appendChild(playerCell);
      tr.appendChild(teamCell);
      tr.appendChild(valueCell);
      body.appendChild(tr);
    });
    table.appendChild(body);
    div.appendChild(table);
    section.appendChild(div);
    container.appendChild(section);
  });
}

// Store teams data for sorting
let teamsDataForSorting = [];

function filterTeamsByScope(teams, scope) {
  if (!teams || scope === 'national') return teams || [];
  const confMatch = scope === 'conference' && userConference != null;
  const regionMatch = scope === 'region' && userRegion != null;
  const regionNorm = (v) => (v || '').toString().toUpperCase();
  const userRegionNorm = regionNorm(userRegion);
  return teams.filter((t) => {
    if (confMatch) return t.conference === userConference;
    if (regionMatch) return regionNorm(t.region) === userRegionNorm;
    return true;
  });
}

function renderTeamStats(data, scope) {
  if (!data) return;
  scope = scope || statsScope;
  const allTeams = data.teams || [];
  const filtered = filterTeamsByScope(JSON.parse(JSON.stringify(allTeams)), scope);
  teamsDataForSorting = filtered;
  TeamStatsTable.renderTeamStatsTable(teamsDataForSorting);
  
  // Add click handlers to sortable headers (only once)
  const sortableHeaders = document.querySelectorAll('#stats-tab .sortable');
  sortableHeaders.forEach(header => {
    // Remove existing listeners to avoid duplicates
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => {
      const stat = newHeader.dataset.stat;
      TeamStatsTable.sortTeamStats(stat, teamsDataForSorting);
    });
  });
}

// ✅ SS&S: Team stats table rendering now uses shared module (teamStatsTable.js)
// Removed ~160 lines of duplicate code

function renderRecruits(data) {
  if (!data) return;
  const tbody = document.getElementById('recruits-body');
  tbody.innerHTML = '';
  
  // Process recruits to add position and rating info
  let recruits = (data.recruits || []).map(r => {
    const a = r.attributes || {};
    const ratings = r.position_ratings || {};
    const best = getBestPosition(ratings);
    
    return {
      name: r.name,
      archetype: r.archetype || '--',
      height: formatHeight(r.height),
      weight: r.weight ?? '--',
      pos: best.pos,
      rt: best.rating,
      attributes: a
    };
  });
  
  // Sort by rating (highest to lowest)
  recruits.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  
  // Render sorted recruits
  recruits.forEach(r => {
    const tr = document.createElement('tr');
    const a = r.attributes;
    
    // Format attributes: 0-9 displays 0, 10-19 displays 1, 20-29 displays 2, etc.
    const formatAttr = (attr) => {
      const value = attr ?? 0;
      return Math.floor(value / 10);
    };
    
    tr.innerHTML = `<td>${r.name}</td><td>${r.archetype}</td><td>${r.height}</td><td>${r.weight}</td><td>${r.pos}</td><td>${formatAttr(a.SC)}</td><td>${formatAttr(a.SH)}</td><td>${formatAttr(a.ID)}</td><td>${formatAttr(a.OD)}</td><td>${formatAttr(a.PS)}</td><td>${formatAttr(a.BH)}</td><td>${formatAttr(a.RB)}</td><td>${formatAttr(a.AG)}</td><td>${formatAttr(a.ST)}</td><td>${formatAttr(a.ND)}</td><td>${formatAttr(a.IQ)}</td><td>${formatAttr(a.FT)}</td><td>${r.rt ?? '-'}</td>`;
    tbody.appendChild(tr);
  });
  
  // Initialize tooltips for table cells
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
}

function renderTrainingResults(data) {
  const container = document.getElementById('training-results-container');
  if (!container) return;
  
  if (!data || (!data.player_logs || Object.keys(data.player_logs).length === 0)) {
    container.innerHTML = '<p>No training session completed yet.</p>';
    return;
  }
  
  container.innerHTML = '';
  
  // Add session type header
  const sessionHeader = document.createElement('h4');
  const sessionLabel = data.session_type === 'preseason' ? 'Training Camp' : 'In-Season Training';
  sessionHeader.textContent = sessionLabel + (data.week ? ` (Week ${data.week})` : '');
  sessionHeader.style.marginBottom = '15px';
  container.appendChild(sessionHeader);
  
  // Player Results
  const playerHeader = document.createElement('h5');
  playerHeader.textContent = 'Player Attribute Changes';
  playerHeader.style.marginTop = '10px';
  container.appendChild(playerHeader);
  
  const traitOrder = ['SH','SC','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT'];
  
  if (data.player_logs && typeof data.player_logs === 'object') {
    Object.entries(data.player_logs).forEach(([name, traits]) => {
      const row = document.createElement('p');
      row.style.marginBottom = '5px';
      const bold = document.createElement('strong');
      bold.textContent = name + ': ';
      row.appendChild(bold);

      const parts = traitOrder.map(attr => {
        const val = Object.hasOwnProperty.call(traits, attr) ? traits[attr] : 0;
        if (val === 0) return null;
        const sign = val > 0 ? '+' : '';
        return `${attr} ${sign}${val}`;
      }).filter(p => p !== null);

      row.appendChild(document.createTextNode(parts.join(', ')));
      container.appendChild(row);
    });
  }
  
  // Team Results
  if (data.team_log && typeof data.team_log === 'object' && Object.keys(data.team_log).length > 0) {
    const teamHeader = document.createElement('h5');
    teamHeader.textContent = 'Team Attribute Changes';
    teamHeader.style.marginTop = '20px';
    container.appendChild(teamHeader);

    Object.entries(data.team_log).forEach(([attr, delta]) => {
      const row = document.createElement('p');
      row.style.marginBottom = '5px';
      const sign = delta > 0 ? '+' : '';
      row.textContent = `${attr}: ${sign}${delta}`;
      container.appendChild(row);
    });
  }
}

function renderTeam(data) {
  if (!data) {
    return;
  }
  userRosterPlayersCache = data.players || [];
  persistFccSessionCache();
  const tbody = document.getElementById('team-body');
  if (!tbody) {
    return;
  }
  tbody.innerHTML = '';
  let players = (data.players || []).map(p => {
    try {
      const best = getBestPosition(p.position_ratings || {});
      const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
      const player = {
        _id: p._id, // Add missing _id field for player detail links
        name: fullName,
        jersey: p.jersey,
        pos: best.pos,
        year: yearMap[p.year?.toLowerCase()] || p.year || '--',
        height: formatHeight(p.height),
        weight: p.weight ?? '--',
        attributes: p.attributes || {},
        rt: best.rating,
        has_playing_time_promise: !!p.has_playing_time_promise,
        is_graduating: !!p.is_graduating,
      };
      return player;
    } catch (error) {
      console.error('Error mapping player:', p, error);
      return null;
    }
  }).filter(p => p !== null);
  players.sort((a, b) => (b.rt ?? -1) - (a.rt ?? -1));
  
  // Store for sorting
  rosterTableDataForSorting = JSON.parse(JSON.stringify(players));
  
  players.forEach((p, index) => {
    const tr = document.createElement('tr');
    
    // Create player name as clickable link
    const nameTd = document.createElement("td");
    const nameLink = document.createElement("a");
    nameLink.href = buildPlayerDetailUrl(p._id);
    nameLink.textContent =
      typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
    nameLink.style.color = 'inherit';
    nameLink.style.textDecoration = 'none';
    nameLink.addEventListener('mouseenter', () => {
      nameLink.style.textDecoration = 'underline';
    });
    nameLink.addEventListener('mouseleave', () => {
      nameLink.style.textDecoration = 'none';
    });
    nameTd.appendChild(nameLink);
    if (p.has_playing_time_promise) {
      const ptp = document.createElement('span');
      ptp.textContent = ' (PTP)';
      ptp.style.color = '#bb2f35';
      ptp.style.fontWeight = '700';
      nameTd.appendChild(ptp);
    }
    if (p.is_graduating) {
      const gr = document.createElement('span');
      gr.textContent = ' (GR)';
      gr.style.color = '#2f8f46';
      gr.style.fontWeight = '700';
      nameTd.appendChild(gr);
    }
    tr.appendChild(nameTd);
    
    // Add other columns directly as DOM elements
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    addCell(p.pos);
    addCell(p.year);
    addCell(p.height);
    addCell(p.weight);
    
    ATTR_HEADERS.forEach(h => {
      const attrs = p.attributes || {};
      // Use anchor attribute (base value) as fallback, same as lineup screen
      const rawVal = attrs[`anchor_${h}`] ?? attrs[h];
      // Convert to 0-12 scale, except NG which stays as decimal
      const displayVal = h === 'NG' 
        ? (rawVal != null ? rawVal.toFixed(2) : '--')
        : (rawVal != null ? Math.floor(rawVal / 10) : '--');
      addCell(displayVal);
    });
    addCell(p.rt ?? '-');
    
    tbody.appendChild(tr);
  });
  
  // Initialize tooltips for table cells
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
  
  // Add click handlers to sortable headers
  const sortableHeaders = document.querySelectorAll('#roster-tab .roster-table thead th');
  let rosterSortColumn = 'RT';
  let rosterSortDirection = 'desc';
  
  sortableHeaders.forEach((header, index) => {
    // Remove existing listeners
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => {
      const columnNames = ['Name', 'POS', 'Year', 'Height', 'Weight', 'SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT', 'RT'];
      const columnName = columnNames[index];
      
      // Toggle sort direction if clicking the same column
      if (rosterSortColumn === columnName) {
        rosterSortDirection = rosterSortDirection === 'desc' ? 'asc' : 'desc';
      } else {
        rosterSortColumn = columnName;
        rosterSortDirection = 'desc';
      }
      
      sortRosterTable(columnName, rosterSortDirection);
    });
  });
  renderPlayerStatsTable(data.players || []);
  void renderHomeTab();
}

function renderPlayerStatsTable(players) {
  const tbody = document.getElementById('player-stats-body');
  const statsTable = document.querySelector('#player-stats-tab .stats-table');
  if (!tbody || !statsTable) return;

  const statsRows = (players || []).map((player) => ({
    raw: player,
    stats: getPlayerSeasonStats(player),
    rt: getPlayerRt(player)
  }));

  function statValueForSort(entry, statKey) {
    const stats = entry.stats || {};
    if (statKey === 'name') return `${entry.raw?.last_name || ''} ${entry.raw?.first_name || ''}`.trim() || entry.raw?.name || '';
      if (statKey === 'FG%') return stats.FGA > 0 ? ((stats.FGM || 0) / stats.FGA) : 0;
      if (statKey === '3PT%') {
        const attempts = stats['3PTA'] || stats.TPA || 0;
        return attempts > 0 ? (((stats['3PTM'] || stats.TPM || 0) / attempts)) : 0;
      }
      if (statKey === 'FT%') return stats.FTA > 0 ? ((stats.FTM || 0) / stats.FTA) : 0;
      if (statKey === 'SCR%') return stats.SCR_A > 0 ? ((stats.SCR_S || 0) / stats.SCR_A) : 0;
      if (statKey === 'DEF%') return stats.DEF_A > 0 ? ((stats.DEF_S || 0) / stats.DEF_A) : 0;
      if (statKey === 'TREB') return stats.TREB || ((stats.DREB || 0) + (stats.OREB || 0));
      return Number(stats[statKey] || 0);
    }

  function renderRows(rows) {
    tbody.innerHTML = '';
    rows.forEach((entry) => {
      const stats = entry.stats || {};
      const tpm = stats['3PTM'] || 0;
      const tpa = stats['3PTA'] || stats.TPA || 0;
      const fgPct = stats.FGA > 0 ? (((stats.FGM || 0) / stats.FGA) * 100).toFixed(1) : '0.0';
      const threePct = tpa > 0 ? ((tpm / tpa) * 100).toFixed(1) : '0.0';
      const ftPct = stats.FTA > 0 ? (((stats.FTM || 0) / stats.FTA) * 100).toFixed(1) : '0.0';
      const scrA = stats.SCR_A || 0;
      const scrPct = scrA > 0 ? (((stats.SCR_S || 0) / scrA) * 100).toFixed(1) : '0.0';
      const defA = stats.DEF_A || 0;
      const defPct = defA > 0 ? (((stats.DEF_S || 0) / defA) * 100).toFixed(1) : '0.0';

      const tr = document.createElement('tr');
      tr.innerHTML =
        '<td>' + getDisplayPlayerNameForStats(entry.raw) + '</td>' +
        '<td>' + (stats.PTS || 0) + '</td>' +
        '<td>' + (stats.FGM || 0) + '</td>' +
        '<td>' + (stats.FGA || 0) + '</td>' +
        '<td>' + fgPct + '%</td>' +
        '<td>' + tpm + '</td>' +
        '<td>' + tpa + '</td>' +
        '<td>' + threePct + '%</td>' +
        '<td>' + (stats.FTM || 0) + '</td>' +
        '<td>' + (stats.FTA || 0) + '</td>' +
        '<td>' + ftPct + '%</td>' +
        '<td>' + (stats.DREB || 0) + '</td>' +
        '<td>' + (stats.OREB || 0) + '</td>' +
        '<td>' + (stats.TREB || ((stats.DREB || 0) + (stats.OREB || 0))) + '</td>' +
        '<td>' + (stats.AST || 0) + '</td>' +
        '<td>' + (stats.STL || 0) + '</td>' +
        '<td>' + (stats.BLK || 0) + '</td>' +
        '<td>' + (stats.F || 0) + '</td>' +
        '<td>' + (stats.MIN || 0) + '</td>' +
        '<td>' + (stats.TO || 0) + '</td>' +
        '<td>' + scrA + '</td>' +
        '<td>' + scrPct + '%</td>' +
        '<td>' + defA + '</td>' +
        '<td>' + defPct + '%</td>';
      tbody.appendChild(tr);
    });
  }

  function sortAndRender(statKey, direction) {
    const sorted = [...statsRows].sort((a, b) => {
      if (statKey === 'name') {
        const cmp = statValueForSort(a, statKey).localeCompare(statValueForSort(b, statKey));
        return direction === 'asc' ? cmp : -cmp;
      }
      const aVal = statValueForSort(a, statKey);
      const bVal = statValueForSort(b, statKey);
      if (aVal !== bVal) return direction === 'asc' ? aVal - bVal : bVal - aVal;
      return direction === 'asc' ? a.rt - b.rt : b.rt - a.rt;
    });
    renderRows(sorted);
  }

  let activeSort = 'PTS';
  let activeDirection = 'desc';
  sortAndRender(activeSort, activeDirection);

  statsTable.querySelectorAll('thead .sortable').forEach((header) => {
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => {
      const stat = newHeader.dataset.stat;
      if (activeSort === stat) {
        activeDirection = activeDirection === 'desc' ? 'asc' : 'desc';
      } else {
        activeSort = stat;
        activeDirection = 'desc';
      }
      sortAndRender(activeSort, activeDirection);
    });
  });
}

// Store roster data for sorting
let rosterTableDataForSorting = [];

function sortRosterTable(columnName, direction) {
  const tbody = document.getElementById('team-body');
  if (!tbody || !rosterTableDataForSorting.length) return;
  
  const columnMap = {
    'Name': 'name',
    'POS': 'pos',
    'Year': 'year',
    'Height': 'height',
    'Weight': 'weight',
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
    'RT': 'RT'
  };
  
  const dataKey = columnMap[columnName] || columnName;
  
  rosterTableDataForSorting.sort((a, b) => {
    let val1, val2;
    
    if (dataKey === 'name') {
      val1 = a.name || '';
      val2 = b.name || '';
      return direction === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (dataKey === 'RT') {
      val1 = a.rt ?? -Infinity;
      val2 = b.rt ?? -Infinity;
    } else if (dataKey === 'year') {
      const yearOrder = { 'FR': 1, 'SO': 2, 'JR': 3, 'SR': 4 };
      val1 = yearOrder[a.year] || 0;
      val2 = yearOrder[b.year] || 0;
    } else if (dataKey === 'height') {
      const parseHeight = (h) => {
        if (!h || h === '--') return 0;
        const match = h.match(/(\d+)'(\d+)"/);
        return match ? parseInt(match[1]) * 12 + parseInt(match[2]) : 0;
      };
      val1 = parseHeight(a.height);
      val2 = parseHeight(b.height);
    } else if (dataKey === 'weight') {
      val1 = parseInt(a.weight) || 0;
      val2 = parseInt(b.weight) || 0;
    } else {
      // Attribute columns
      const attrsA = a.attributes || {};
      const attrsB = b.attributes || {};
      const rawValA = attrsA[`anchor_${dataKey}`] ?? attrsA[dataKey] ?? 0;
      const rawValB = attrsB[`anchor_${dataKey}`] ?? attrsB[dataKey] ?? 0;
      val1 = Math.floor(rawValA / 10);
      val2 = Math.floor(rawValB / 10);
    }
    
    if (direction === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  // Re-render the table
  tbody.innerHTML = '';
  rosterTableDataForSorting.forEach((p, index) => {
    const tr = document.createElement('tr');
    
    const nameTd = document.createElement("td");
    const nameLink = document.createElement("a");
    nameLink.href = buildPlayerDetailUrl(p._id);
    nameLink.textContent =
      typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, p.name) : p.name;
    nameLink.style.color = 'inherit';
    nameLink.style.textDecoration = 'none';
    nameLink.addEventListener('mouseenter', () => {
      nameLink.style.textDecoration = 'underline';
    });
    nameLink.addEventListener('mouseleave', () => {
      nameLink.style.textDecoration = 'none';
    });
    nameTd.appendChild(nameLink);
    if (p.has_playing_time_promise) {
      const ptp = document.createElement('span');
      ptp.textContent = ' (PTP)';
      ptp.style.color = '#bb2f35';
      ptp.style.fontWeight = '700';
      nameTd.appendChild(ptp);
    }
    if (p.is_graduating) {
      const gr = document.createElement('span');
      gr.textContent = ' (GR)';
      gr.style.color = '#2f8f46';
      gr.style.fontWeight = '700';
      nameTd.appendChild(gr);
    }
    tr.appendChild(nameTd);
    
    const addCell = (content) => {
      const td = document.createElement('td');
      td.textContent = content;
      tr.appendChild(td);
    };
    
    addCell(p.pos);
    addCell(p.year);
    addCell(p.height);
    addCell(p.weight);
    
    ATTR_HEADERS.forEach(h => {
      const attrs = p.attributes || {};
      const rawVal = attrs[`anchor_${h}`] ?? attrs[h];
      const displayVal = h === 'NG' 
        ? (rawVal != null ? rawVal.toFixed(2) : '--')
        : (rawVal != null ? Math.floor(rawVal / 10) : '--');
      addCell(displayVal);
    });
    addCell(p.rt ?? '-');
    
    tbody.appendChild(tr);
  });
  
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody, ['td']);
  }
}

// Schedule tab removed; full schedule is on schedule.html (Resources).

// Store team traits data for sorting
let teamTraitsDataForSorting = [];
let teamTraitsSortColumn = 'total';
let teamTraitsSortDirection = 'desc';

function renderTeamTraits(data, scope) {
  if (!data || !data.teams) return;
  scope = scope || traitsScope;
  const filtered = filterTeamsByScope(JSON.parse(JSON.stringify(data.teams)), scope);
  teamTraitsDataForSorting = filtered;
  
  // Calculate totals for each team and add to data
  teamTraitsDataForSorting.forEach(team => {
    const attrs = team.attributes || {};
    const attributes = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];
    let total = 0;
    attributes.forEach(attr => {
      total += attrs[attr] || 0;
    });
    team.total = total;
  });
  
  // Render main table
  const tbody = document.getElementById('team-traits-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  
  // Sort by default (total descending)
  sortTeamTraitsTable(teamTraitsSortColumn, teamTraitsSortDirection);
  
  // Setup sortable headers (clone + replace to avoid duplicate listeners when switching scope)
  const headers = document.querySelectorAll('#team-traits-table thead th.sortable');
  headers.forEach(header => {
    const newHeader = header.cloneNode(true);
    header.parentNode.replaceChild(newHeader, header);
    newHeader.style.cursor = 'pointer';
    newHeader.style.userSelect = 'none';
    newHeader.addEventListener('click', () => {
      const attr = newHeader.dataset.attr;
      if (teamTraitsSortColumn === attr) {
        teamTraitsSortDirection = teamTraitsSortDirection === 'desc' ? 'asc' : 'desc';
      } else {
        teamTraitsSortColumn = attr;
        teamTraitsSortDirection = 'desc';
      }
      sortTeamTraitsTable(attr, teamTraitsSortDirection);
    });
  });
  
  // Render Top 10 list (excluding FT)
  renderTeamTraitsTop10(teamTraitsDataForSorting);
}

function sortTeamTraitsTable(columnName, direction) {
  const tbody = document.getElementById('team-traits-body');
  if (!tbody || !teamTraitsDataForSorting.length) return;
  
  // Ensure totals are calculated for all teams
  teamTraitsDataForSorting.forEach(team => {
    if (team.total === undefined) {
      const attrs = team.attributes || {};
      const attributes = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];
      let total = 0;
      attributes.forEach(attr => {
        total += attrs[attr] || 0;
      });
      team.total = total;
    }
  });
  
  teamTraitsDataForSorting.sort((a, b) => {
    let val1, val2;
    
    if (columnName === 'team') {
      val1 = a.team_name || '';
      val2 = b.team_name || '';
      return direction === 'desc' ? val2.localeCompare(val1) : val1.localeCompare(val2);
    } else if (columnName === 'total') {
      // Total column - use calculated total
      val1 = a.total || 0;
      val2 = b.total || 0;
    } else {
      // Attribute columns
      const attrsA = a.attributes || {};
      const attrsB = b.attributes || {};
      val1 = attrsA[columnName] || 0;
      val2 = attrsB[columnName] || 0;
    }
    
    if (direction === 'desc') {
      return val2 - val1;
    } else {
      return val1 - val2;
    }
  });
  
  // Render sorted table
  tbody.innerHTML = '';
  teamTraitsDataForSorting.forEach(team => {
    const tr = document.createElement('tr');
    const attrs = team.attributes || {};
    
    // Create team name cell with primary color and bold styling
    const teamNameCell = document.createElement('td');
    teamNameCell.textContent = team.team_name || '';
    teamNameCell.style.color = team.primary_color || '#000000';
    teamNameCell.style.fontWeight = 'bold';
    tr.appendChild(teamNameCell);
    
    // Add attribute cells individually
    const attributeValues = [
      attrs.SC || 0,
      attrs.SH || 0,
      attrs.ID || 0,
      attrs.OD || 0,
      attrs.PS || 0,
      attrs.BH || 0,
      attrs.RB || 0,
      attrs.AG || 0,
      attrs.ST || 0,
      attrs.ND || 0,
      attrs.IQ || 0,
      attrs.FT || 0
    ];
    
    attributeValues.forEach(value => {
      const td = document.createElement('td');
      td.textContent = value;
      tr.appendChild(td);
    });
    
    // Add Total cell
    const totalCell = document.createElement('td');
    // Calculate total if not already set
    if (team.total === undefined) {
      team.total = attributeValues.reduce((sum, val) => sum + val, 0);
    }
    totalCell.textContent = team.total || 0;
    totalCell.style.fontWeight = 'bold';
    tr.appendChild(totalCell);
    
    tbody.appendChild(tr);
  });
}

function renderTeamTraitsTop10(teams) {
  const container = document.getElementById('team-traits-top10');
  if (!container) return;
  container.innerHTML = '';
  
  // Create list of all (team_name, attribute, value) tuples, excluding FT
  const allValues = [];
  const attributes = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ'];
  
  teams.forEach(team => {
    const attrs = team.attributes || {};
    attributes.forEach(attr => {
      allValues.push({
        team_name: team.team_name,
        team_id: team.team_id,
        primary_color: team.primary_color || '#000000',
        attribute: attr,
        value: attrs[attr] || 0
      });
    });
  });
  
  // Sort by value descending
  allValues.sort((a, b) => b.value - a.value);
  
  // Get Top 10
  const top10 = allValues.slice(0, 10);
  
  // Create list element
  const list = document.createElement('ul');
  list.style.listStyle = 'none';
  list.style.padding = '0';
  list.style.margin = '0';
  
  top10.forEach((item, index) => {
    const li = document.createElement('li');
    li.style.padding = '8px 0';
    li.style.borderBottom = '1px solid #eee';
    
    const span = document.createElement('span');
    span.style.fontWeight = 'bold';
    span.style.color = item.primary_color;
    span.textContent = `${index + 1}. ${item.team_name} ${item.attribute}: ${item.value}`;
    
    li.appendChild(span);
    list.appendChild(li);
  });
  
  container.appendChild(list);
}

async function init() {
  if (window.GOB_Analytics) window.GOB_Analytics.franchiseEntered();
  // ✅ ALPHA: Initialize alpha banner (shows badge if IS_ALPHA=true)
  if (typeof AlphaBanner !== 'undefined') {
    await AlphaBanner.init();
  }
  
  // ✅ SS&S: Check URL params first for team_id (ObjectId) - allows seamless navigation
  const urlParams = new URLSearchParams(window.location.search);
  const urlTeamId = urlParams.get('team_id');
  if (urlTeamId) {
    userTeamId = urlTeamId;
    localStorage.setItem('franchise_user_team_id', userTeamId);
  } else {
    // Fallback to localStorage
    userTeamId = localStorage.getItem('franchise_user_team_id');
  }
  
  const initStartTime = performance.now();
  console.log('⏱️ [PERF] FCC init() START');
  const restoredFromSession = restoreFccSessionCache();
  try {
  if (restoredFromSession && commandCenterTopDataCache) {
    emitDisplayContextUpdate();
    if (commandCenterTopDataCache && commandCenterTopDataCache.team_id && !userTeamId) {
      userTeamId = commandCenterTopDataCache.team_id;
      localStorage.setItem('franchise_user_team_id', userTeamId);
      emitDisplayContextUpdate();
    }
    populateTop(commandCenterTopDataCache);
    void hydrateFccDisplayColorPreference();
    initFccRecruits(commandCenterTopDataCache);
    if (commandCenterTopDataCache.team) {
      userTeamNameForLeaders = commandCenterTopDataCache.team;
    }
    userConference = commandCenterTopDataCache.user_conference != null ? commandCenterTopDataCache.user_conference : null;
    userRegion = commandCenterTopDataCache.user_region != null && commandCenterTopDataCache.user_region !== '' ? commandCenterTopDataCache.user_region : null;
    void initializeTeamColorCache();
    updatePlayButton(commandCenterTopDataCache);
    updateScoutingButton(commandCenterTopDataCache);
    updateRecruitingButton(commandCenterTopDataCache);
    updateAwardsButton(commandCenterTopDataCache);
    void updatePlaybooksButtonState(commandCenterTopDataCache);
    bindResourcesLinks();
    if (standingsDataCache) renderStandings(standingsDataCache, 'A');
    if (userRosterPlayersCache.length) renderTeam({ players: userRosterPlayersCache });
    renderHomeStandingsCard();
    renderHomeRankingsCard();
    renderHomeLockerRoomCard();
    renderHomeTeamStatsCard();
    renderHomeRecruitingCard();
    renderHomeNewsCard();
    if (userScheduleDataCache) {
      void renderHomeTab();
    }
    hideFccLoadingOverlay();
  }
  const topDataStartTime = performance.now();
  const topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
  const topDataEndTime = performance.now();
  console.log(`⏱️ [PERF] /franchise/command-center/data: ${(topDataEndTime - topDataStartTime).toFixed(2)}ms`);
  if (!topData) return; // Access denied or error - redirect already triggered for 401/403; finally block will hide page-load-overlay
  const previousWeek = Number(commandCenterTopDataCache?.week || 0);
  const nextWeek = Number(topData?.week || 0);
  if (previousWeek && nextWeek && previousWeek !== nextWeek) {
    console.warn('[FCC CACHE] Invalidating week-sensitive Home caches after week change', { previousWeek, nextWeek });
    invalidateHomeWeekSensitiveCaches();
  }
  commandCenterTopDataCache = topData;
  persistFccSessionCache();
  emitDisplayContextUpdate();

  // ✅ SS&S: Resolve team_id from command center data if not already set
  if (topData && topData.team_id && !userTeamId) {
    userTeamId = topData.team_id;
    localStorage.setItem('franchise_user_team_id', userTeamId);
    emitDisplayContextUpdate();
  }
  
  // ✅ FIX: Use EXACT same source as Team tab - fetch team_chemistry from /franchise/team-data
  // This ensures 100% consistency between header and Team tab
  if (franchiseId && userTeamId) {
    try {
      const teamDataStartTime = performance.now();
      const teamDataResponse = await fetch(`${API_CONFIG.buildUrl('/franchise/team-data')}?franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`, { headers: API_CONFIG.getAuthHeaders() });
      const teamDataEndTime = performance.now();
      console.log(`⏱️ [PERF] /franchise/team-data: ${(teamDataEndTime - teamDataStartTime).toFixed(2)}ms`);
      if (teamDataResponse.ok) {
        const teamData = await teamDataResponse.json();
        // Override team_chemistry with value from team-data endpoint (same as Team tab uses)
        if (teamData && teamData.team_attributes && teamData.team_attributes.team_chemistry !== undefined) {
          topData.team_chemistry = teamData.team_attributes.team_chemistry;
          console.log('📊 [TEAM CHEMISTRY] Top bar value (from team-data):', topData.team_chemistry);
          persistFccSessionCache();
        }
      }
    } catch (error) {
      console.warn('Could not fetch team_chemistry from team-data endpoint:', error);
    }
  }
  
  populateTop(topData);
  await hydrateFccDisplayColorPreference();
  initFccRecruits(topData);
  
  // Store user team name and scope keys (used by roster/team if needed)
  if (topData && topData.team) {
    userTeamNameForLeaders = topData.team;
  }
  if (topData) {
    userConference = topData.user_conference != null ? topData.user_conference : null;
    userRegion = topData.user_region != null && topData.user_region !== '' ? topData.user_region : null;
  }
  
  // Initialize team color cache for leaderboard highlighting
  await initializeTeamColorCache();
  
  // Update button based on training status
  updatePlayButton(topData);
  updateScoutingButton(topData);
  updateRecruitingButton(topData);
  updateAwardsButton(topData);
  await updatePlaybooksButtonState(topData);
  maybeShowChampionshipCompleteModal(topData);
  if (topData?.cut_required && Number(topData.cut_count || 0) > 0) {
    showCutPlayersRequiredModal(Number(topData.cut_count || 0));
  }
  
  if (topData && (topData.team_id || topData.team) && userTeamId) {
    console.log('Loading franchise roster for team_id:', userTeamId, 'franchiseId:', franchiseId);
    if (!franchiseId) {
      console.error('No franchiseId found - cannot load roster');
      return;
    }
    try {
      const rosterStartTime = performance.now();
      const rosterUrl = `${API_CONFIG.buildUrl(`/roster/${encodeURIComponent(userTeamId)}`)}?franchise_id=${encodeURIComponent(franchiseId)}&profile=1`;
      const stateUrl = `${API_CONFIG.buildUrl('/franchise/state')}?franchise_id=${franchiseId}&profile=1`;
      const result = await RosterLoader.loadRosterWithStats(rosterUrl, stateUrl);
      const rosterEndTime = performance.now();
      console.log(`⏱️ [PERF] roster+state (franchise): ${(rosterEndTime - rosterStartTime).toFixed(2)}ms`);
      renderTeam({ players: result.players });
    } catch (error) {
      console.error('Failed to load franchise roster:', error);
    }
  }
  const standingsStartTime = performance.now();
  const standingsUrl = userTeamId
    ? `${API_CONFIG.buildUrl('/franchise/standings')}?franchise_id=${franchiseId}&scope=user_region&team_id=${encodeURIComponent(userTeamId)}&profile=1`
    : `${API_CONFIG.buildUrl('/franchise/standings')}?franchise_id=${franchiseId}&profile=1`;
  const standingsData = await fetchJSON(standingsUrl);
  const standingsEndTime = performance.now();
  console.log(`⏱️ [PERF] /franchise/standings: ${(standingsEndTime - standingsStartTime).toFixed(2)}ms`);
  standingsDataCache = standingsData;
  persistFccSessionCache();
  renderStandings(standingsData, 'A');
  bindResourcesLinks();
  const homeTabDataPromise = loadHomeTabData();
    
    // ============================================================================
    // 🛠️ DEV MODE: Simulate Entire Regular Season Popup (Temporary Development Feature)
    // ============================================================================
    // ⚠️  DISABLED: Commented out for testing
    // ⚠️  To disable: Comment out the code block below (lines ~785-850)
    // ⚠️  To re-enable: Uncomment the code block
    // ============================================================================
    // const popupStartTime = performance.now();
    // console.log('⏱️ [PERF] showDevSimPopup START', { week: topData?.week, hasResults: !!topData?.results, resultsKeys: topData?.results ? Object.keys(topData.results).length : 0 });
    // showDevSimPopup(topData);
    // const popupEndTime = performance.now();
    // console.log(`⏱️ [PERF] showDevSimPopup COMPLETE: ${(popupEndTime - popupStartTime).toFixed(2)}ms`);
    // ============================================================================
    // 🛠️ END DEV MODE FEATURE
    // ============================================================================
    
    // ✅ Stats, Team Traits, Rankings moved to standalone pages (Resources tab)
    
    // Initialize tooltips for table headers
    if (typeof initAttributeTooltips !== 'undefined') {
      const rosterTable = document.querySelector('#roster-tab .roster-table');
      if (rosterTable) initAttributeTooltips(rosterTable, ['th']);
    }
    
    // Load team data for Team tab
    const loadTeamDataStartTime = performance.now();
    console.log('⏱️ [PERF] loadTeamData() START');
    if (restoredFromSession && teamData) {
      void loadTeamData();
    } else {
      await loadTeamData();
    }
    const loadTeamDataEndTime = performance.now();
    console.log(`⏱️ [PERF] loadTeamData() COMPLETE: ${(loadTeamDataEndTime - loadTeamDataStartTime).toFixed(2)}ms`);
    if (restoredFromSession && userScheduleDataCache) {
      void homeTabDataPromise;
    } else {
      await homeTabDataPromise;
    }
    
    const initEndTime = performance.now();
    console.log(`⏱️ [PERF] FCC init() COMPLETE: ${(initEndTime - initStartTime).toFixed(2)}ms`);
  } finally {
    hideFccLoadingOverlay();
  }
}

function clearFranchiseLocalStorage() {
  if (typeof localStorage === 'undefined') return;
  const toRemove = [
    'franchiseId',
    'franchise_id',
    'franchise_week',
    'franchise_user_team',
    'franchise_user_team_id',
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

function getChampionshipSeenKey(franchiseIdValue, gameId) {
  if (!franchiseIdValue || !gameId) return null;
  return `fcc_championship_seen_${franchiseIdValue}_${gameId}`;
}

function maybeShowChampionshipCompleteModal(topData) {
  const summary = topData?.championship_summary;
  if (!summary || !summary.game_id) return;

  const seenKey = getChampionshipSeenKey(franchiseId, summary.game_id);
  if (seenKey && typeof localStorage !== 'undefined' && localStorage.getItem(seenKey) === '1') {
    return;
  }
  showChampionshipCompleteModal(summary);
}

function showChampionshipCompleteModal(summary) {
  const winner = summary.winner_team_name || 'Champion';
  const homeName = summary.home_team_name || 'Home';
  const awayName = summary.away_team_name || 'Away';
  const homeScore = summary.home_score ?? '--';
  const awayScore = summary.away_score ?? '--';
  const gameId = summary.game_id;

  const overlay = document.createElement('div');
  overlay.className = 'fcc-modal-overlay';
  overlay.innerHTML = `
    <div class="fcc-modal-card" role="dialog" aria-modal="true" aria-label="Season Complete">
      <h3 class="fcc-modal-title">Season Complete</h3>
      <p class="fcc-modal-copy"><strong>${winner}</strong> won the Championship.</p>
      <p class="fcc-modal-copy">${awayName} ${awayScore} at ${homeName} ${homeScore}</p>
      <div class="fcc-modal-actions">
        <button class="fcc-modal-btn fcc-modal-btn-secondary" id="fcc-champ-box-score">Box Score</button>
        <button class="fcc-modal-btn fcc-modal-btn-primary" id="fcc-champ-back">Back To Locker Room</button>
      </div>
    </div>
  `;

  const markSeen = () => {
    const seenKey = getChampionshipSeenKey(franchiseId, gameId);
    if (seenKey && typeof localStorage !== 'undefined') localStorage.setItem(seenKey, '1');
  };

  overlay.querySelector('#fcc-champ-box-score')?.addEventListener('click', () => {
    markSeen();
    const params = new URLSearchParams();
    params.set('mode', 'franchise');
    params.set('franchise_id', franchiseId);
    params.set('game_id', gameId);
    if (homeName) params.set('home', homeName);
    if (awayName) params.set('away', awayName);
    window.location.href = `/box-score.html?${params.toString()}`;
  });

  overlay.querySelector('#fcc-champ-back')?.addEventListener('click', () => {
    markSeen();
    overlay.remove();
    window.location.href = `/franchise-command-center.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}`;
  });

  document.body.appendChild(overlay);
}

function showNewSeasonConfirmModal() {
  const overlay = document.createElement('div');
  overlay.className = 'fcc-modal-overlay';
  overlay.innerHTML = `
    <div class="fcc-modal-card" role="dialog" aria-modal="true" aria-label="New Season">
      <h3 class="fcc-modal-title">Go To Next Season?</h3>
      <p class="fcc-modal-copy">This will create the next season for this franchise instance.</p>
      <p class="fcc-modal-copy">Your current season cannot be reopened after you proceed.</p>
      <div class="fcc-modal-actions">
        <button class="fcc-modal-btn fcc-modal-btn-secondary" id="fcc-new-season-cancel">Cancel</button>
        <button class="fcc-modal-btn fcc-modal-btn-primary" id="fcc-new-season-proceed">Proceed</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  return overlay;
}

function showCutPlayersRequiredModal(cutCount) {
  const overlay = document.createElement('div');
  overlay.className = 'fcc-modal-overlay';
  overlay.innerHTML = `
    <div class="fcc-modal-card" role="dialog" aria-modal="true" aria-label="Cut Players Required">
      <h3 class="fcc-modal-title">Cut Players Required</h3>
      <p class="fcc-modal-copy">You need to cut ${cutCount} player${cutCount === 1 ? '' : 's'}.</p>
      <div class="fcc-modal-actions">
        <button class="fcc-modal-btn fcc-modal-btn-primary" id="fcc-cut-required-close">Close</button>
      </div>
    </div>
  `;
  overlay.querySelector('#fcc-cut-required-close')?.addEventListener('click', () => {
    overlay.remove();
  });
  document.body.appendChild(overlay);
}

function updatePlayButton(data) {
  const playNowBtn = document.getElementById('play-now');
  if (!data) return;
  
  const eosTournamentActive = data.eos_tournament_active || false;
  const eosTournament = data.eos_tournament;
  const week = data.week || 1;
  const trainingDisabledForEos = !!data.training_disabled_for_eos;
  const userEliminated = data.user_eliminated != null ? !!data.user_eliminated : null;
  const offerSimRest = data.offer_sim_rest != null ? !!data.offer_sim_rest : null;
  
  // Fallback: infer eliminated from bracket when API doesn't return user_eliminated/offer_sim_rest
  let userTeamEliminated = false;
  if (eosTournamentActive && eosTournament && userTeamId && userEliminated == null) {
    const bracket = eosTournament.bracket || {};
    const allMatchups = [...(bracket.round1 || []), ...(bracket.round2 || []), ...(bracket.final || [])];
    const userInMatchup = allMatchups.some(m =>
      String(m.home_team) === String(userTeamId) || String(m.away_team) === String(userTeamId)
    );
    userTeamEliminated = !userInMatchup && week >= 27;
  }
  
  const eliminated = userEliminated != null ? userEliminated : userTeamEliminated;
  const showSimRest = offerSimRest != null ? offerSimRest : (eliminated && eosTournamentActive && !eosTournament?.completed);
  const tournamentComplete = eosTournament?.completed || false;
  const cutRequired = !!data.cut_required;
  
  if (cutRequired) {
    playNowBtn.textContent = 'Cut Players';
    playNowBtn.dataset.mode = 'cut-players';
  } else if (week === 35) {
    playNowBtn.textContent = 'Recruiting';
    playNowBtn.dataset.mode = 'week35-recruiting';
  } else if (week === 36) {
    playNowBtn.textContent = 'Go To Next Season';
    playNowBtn.dataset.mode = 'new-season';
  } else if (tournamentComplete && week >= 37) {
    playNowBtn.textContent = 'Go To Next Season';
    playNowBtn.dataset.mode = 'new-season';
  } else if (showSimRest && eosTournamentActive) {
    playNowBtn.textContent = 'Sim Next Round';
    playNowBtn.dataset.mode = 'sim-rest-tournament';
  } else if (trainingDisabledForEos || eliminated) {
    playNowBtn.textContent = 'Go To Next Season';
    playNowBtn.dataset.mode = 'new-season';
  } else {
    const trainingCompleted = data.training_completed || false;
    const sessionType = data.session_type || 'in-season';
    if (!trainingCompleted) {
      playNowBtn.textContent = sessionType === 'preseason' ? 'Run Training Camp' : 'Run Training';
      playNowBtn.dataset.mode = 'training';
    } else {
      playNowBtn.textContent = 'Play Next Game';
      playNowBtn.dataset.mode = 'play';
    }
  }
}

function updateRecruitingButton(data) {
  const recruitingBtn = document.getElementById('fcc-recruiting-btn');
  const liveCopy = document.getElementById('fcc-recruiting-live-copy');
  if (!recruitingBtn || !liveCopy) return;
  const week = Number(data?.week || 1);
  const resultsWeek = Number(data?.current_recruiting_results_week || 0);
  let text = 'Recruiting Begins Week 20';
  let href = null;
  let showButton = false;

  if (week >= 20 && week <= 26 && resultsWeek === week) {
    showButton = true;
    text = `Week ${week} Recruiting Visits`;
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('week', String(week));
    params.set('return_url', getCurrentRelativeUrl());
    href = `/recruiting-results.html?${params.toString()}`;
  } else if (week >= 20 && week <= 26) {
    text = 'Recruiting Invites Active';
  } else if (week === 19) {
    text = 'Recruiting Invites Begin Next Week';
  } else if (week >= 1 && week <= 18) {
    text = 'Recruiting Invites Begin Week 20';
  } else if (week === 35) {
    text = 'Recruiting Is Live';
  } else if (week === 36) {
    text = 'Recruiting Closed';
  } else if (week > 26) {
    text = 'Recruiting Runs After National Tourney';
  }

  liveCopy.textContent = text;
  liveCopy.style.display = showButton ? 'none' : 'block';
  recruitingBtn.style.display = showButton ? 'inline-flex' : 'none';
  recruitingBtn.textContent = text;
  recruitingBtn.disabled = !showButton;
  recruitingBtn.classList.toggle('is-dead', !showButton);
  recruitingBtn.onclick = null;
  if (showButton && href) {
    recruitingBtn.onclick = () => {
      window.location.href = href;
    };
  }
}

function updateAwardsButton(data) {
  const awardsBtn = document.getElementById('resources-awards');
  if (!awardsBtn) return;
  const week = Number(data?.week || 1);
  const active = week >= 35;
  awardsBtn.classList.toggle('is-dead', !active);
  awardsBtn.setAttribute('aria-disabled', active ? 'false' : 'true');
  awardsBtn.onclick = null;
  if (!active) {
    awardsBtn.onclick = function (e) {
      e.preventDefault();
    };
  }
}

function playSound(filename) {
  try {
    const base = (typeof API_CONFIG !== 'undefined' && API_CONFIG.buildStaticPath) ? API_CONFIG.buildStaticPath('/sounds/') : '/sounds/';
    const a = new Audio(base + encodeURIComponent(filename));
    a.volume = 0.7;
    a.play().catch(function() {});
  } catch (e) {}
}

const playNowBtn = document.getElementById('play-now');
playNowBtn.disabled = true;
playNowBtn.addEventListener('click', async () => {
  playSound('confirm-1.mp3');
  const mode = playNowBtn.dataset.mode || 'play';
  
  if (mode === 'training') {
    const topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
    if (topData?.training_disabled_for_eos) {
      return;
    }
    const sessionType = topData?.session_type || 'in-season';
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('mode', 'franchise');
    params.set('session_type', sessionType);
    params.set('return_url', getCurrentRelativeUrl());
    if (userTeamId) params.set('team_id', userTeamId);
    window.location.href = `/training.html?${params.toString()}`;
    return;
  }

  if (mode === 'week35-recruiting') {
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('return_url', getCurrentRelativeUrl());
    window.location.href = `/recruiting-orders.html?${params.toString()}`;
    return;
  }

  if (mode === 'cut-players') {
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('return_url', getCurrentRelativeUrl());
    window.location.href = `/cut-players.html?${params.toString()}`;
    return;
  }
  
  // ✅ EOS TOURNAMENT: Handle sim rest of tournament
  if (mode === 'sim-rest-tournament') {
    const originalText = playNowBtn.textContent;
    playNowBtn.disabled = true;
    playNowBtn.textContent = 'Simulating...';
    
    try {
      const res = await fetch(API_CONFIG.buildUrl('/franchise/sim-rest-of-tournament'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ franchise_id: franchiseId })
      });
      if (!res.ok) throw new Error('Simulation failed');
      const result = await res.json();
      
      // Check if championship needs to be simmed
      const topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
      const eosTournament = topData?.eos_tournament;
      const currentRound = eosTournament?.current_round;
      
      if (currentRound === 2 && eosTournament?.bracket?.round2) {
        // Show popup with results and Sim Championship button
        const popup = document.createElement('div');
        popup.className = 'sim-popup';
        popup.innerHTML = `
          <div class="sim-popup-content">
            <h3>Semifinals Complete</h3>
            <p>Round 2 results have been simulated.</p>
            <button id="sim-championship-btn">Sim Championship Game</button>
            <button id="close-sim-popup">Close</button>
          </div>
        `;
        document.body.appendChild(popup);
        
        document.getElementById('sim-championship-btn').addEventListener('click', async () => {
          try {
            const champRes = await fetch(API_CONFIG.buildUrl('/franchise/sim-championship'), {
              method: 'POST',
              headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
              body: JSON.stringify({ franchise_id: franchiseId })
            });
            if (!champRes.ok) throw new Error('Championship simulation failed');
            const champData = await champRes.json();
            document.body.removeChild(popup);
            showChampionshipCompleteModal({
              game_id: champData.game_id,
              home_team_name: champData.home_team_name,
              away_team_name: champData.away_team_name,
              home_score: champData.home_score,
              away_score: champData.away_score,
              winner_team_name: champData.winner_name,
            });
          } catch (err) {
            console.error(err);
            alert('Unable to simulate championship');
          }
        });
        
        document.getElementById('close-sim-popup').addEventListener('click', () => {
          document.body.removeChild(popup);
          location.reload();
        });
      } else {
        location.reload(); // Reload to show updated bracket
      }
    } catch (err) {
      console.error(err);
      alert('Unable to simulate tournament');
      playNowBtn.disabled = false;
      playNowBtn.textContent = originalText;
    }
    return;
  }
  
  // End-of-season franchise rollover: keep the same franchise instance and build the next season from franchise data
  if (mode === 'new-season') {
    const modal = showNewSeasonConfirmModal();
    modal.querySelector('#fcc-new-season-cancel')?.addEventListener('click', () => {
      modal.remove();
    });
    modal.querySelector('#fcc-new-season-proceed')?.addEventListener('click', async () => {
      const originalText = playNowBtn.textContent;
      playNowBtn.disabled = true;
      playNowBtn.textContent = 'Starting...';
      try {
        const res = await fetch(API_CONFIG.buildUrl('/franchise/finish-season'), {
          method: 'POST',
          headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ franchise_id: franchiseId }),
        });
        if (!res.ok) throw new Error('Finish season failed');
        window.location.href = `/franchise-command-center.html?franchise_id=${encodeURIComponent(franchiseId)}`;
      } catch (err) {
        console.error(err);
        alert('Unable to start new season');
        playNowBtn.disabled = false;
        playNowBtn.textContent = originalText;
      } finally {
        modal.remove();
      }
    });
    return;
  }
  
  // Otherwise, play the game
  console.log('Play Now click search:', window.location.search);
  const originalText = playNowBtn.textContent;
  playNowBtn.disabled = true;
  playNowBtn.textContent = 'Loading...';
  if (!franchiseId) {
    alert('Franchise not loaded');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
    return;
  }
  try {
    const res = await fetch(API_CONFIG.buildUrl('/franchise/play-next-game'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: franchiseId })
    });
    if (!res.ok) throw new Error('Simulation failed');
    const { home, away, week, home_id, away_id } = await res.json();
    if (!home || !away) throw new Error('Matchup not found');
    try {
      localStorage.setItem('franchise_week', week);
    } catch {}
    // Same approach as tournament: prefer API-sourced team name (userTeamNameForLeaders from topData), then derive from userTeamId vs home_id/away_id. Avoids reliance on localStorage franchise_user_team which may be missing or stale.
    let resolvedSide = (userTeamNameForLeaders === home ? 'home' : (userTeamNameForLeaders === away ? 'away' : ''));
    if (!resolvedSide && userTeamId && home_id != null && away_id != null) {
      if (String(userTeamId) === String(home_id)) resolvedSide = 'home';
      else if (String(userTeamId) === String(away_id)) resolvedSide = 'away';
    }
    let url = `/set-lineup.html?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&week=${week}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&home_id=${encodeURIComponent(home_id)}&away_id=${encodeURIComponent(away_id)}`;
    // ✅ SS&S: Use ObjectId for consistent navigation
    if (userTeamId) url += `&team_id=${encodeURIComponent(userTeamId)}`;
    if (resolvedSide) url += `&my_team=${resolvedSide}`;
    console.log('Navigating to', url);
    window.location.href = url;
  } catch (err) {
    console.error(err);
    alert('Unable to play next game');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
  }
});

// Legacy route buttons were removed from the FCC tab bar in favor of local placeholder tabs.
function wireFccNavButtons() {
  const setGameplanBtn = document.getElementById('set-gameplan-franchise');
  if (setGameplanBtn) {
    setGameplanBtn.addEventListener('click', () => {
      playSound('click-tiny.wav');
      if (!franchiseId || !userTeamId) {
        alert('Franchise or user team not loaded');
        return;
      }
      const params = new URLSearchParams();
      params.set('mode', 'franchise');
      params.set('franchise_id', franchiseId);
      params.set('team_id', userTeamId);
      params.set('from', 'command_center');
      params.set('return_url', getCurrentRelativeUrl());
      window.location.href = `/game-plan.html?${params.toString()}`;
    });
  }
  const playbooksBtn = document.getElementById('playbooks-franchise');
  if (playbooksBtn) {
    playbooksBtn.addEventListener('click', () => {
      playSound('click-tiny.wav');
      if (!franchiseId || !userTeamId) {
        alert('Franchise or user team not loaded');
        return;
      }
      const params = new URLSearchParams();
      params.set('mode', 'franchise');
      params.set('franchise_id', franchiseId);
      params.set('team_id', userTeamId);
      params.set('from', 'franchise-command-center');
      params.set('return_url', getCurrentRelativeUrl());
      window.location.href = `/playbook-report.html?${params.toString()}`;
    });
  }
}

window.addEventListener('DOMContentLoaded', () => {
  wireFccNavButtons();
  // ✅ PHASE 2.4: Removed localStorage fallback - franchise_id must come from URL
  const urlParams = new URLSearchParams(window.location.search);
  franchiseId = urlParams.get('franchise_id');
  if (!franchiseId) {
    console.error('❌ [FCC] franchise_id is required but missing from URL. Redirecting to franchise select.');
    window.location.href = '/franchise-select-team.html';
    return;
  }
  if (franchiseId) {
    playNowBtn.disabled = false;
  }

  const exitFranchiseBtn = document.getElementById('exit-franchise');
  if (exitFranchiseBtn) {
    exitFranchiseBtn.addEventListener('click', () => {
      playSound('x-back.mp3');
      window.location.href = '/mode-select.html';
    });
  }

  init();

  // ✅ Phase 4.4: Shared tab management (commandCenterTabs.js)
  if (typeof CommandCenterTabs !== 'undefined') {
    CommandCenterTabs.initCommandCenterTabs({
      defaultTab: 'home-tab',
      onTabShow: (tabName) => {
        bindResourcesLinks();
        if (commandCenterTopDataCache) {
          updateRecruitingButton(commandCenterTopDataCache);
        }
        if (tabName === 'recruits-tab') {
          renderFccRecruits();
        }
      }
    });
  }
});

// Team Report and Playbook Summary functions (adapted from training-report.js)
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

let teamData = null;

async function loadTeamData() {
  if (!franchiseId || !userTeamId) return;
  
  const loadTeamDataStartTime = performance.now();
  console.log('⏱️ [PERF] loadTeamData() function START');
  
  try {
    // First, ensure team objects exist (this will create them if missing)
    try {
      // ✅ SS&S: Use ObjectId directly - backend accepts it
      const gameplanStartTime = performance.now();
      console.log('⏱️ [PERF] loadTeamData() calling /api/gameplan START');
      await fetch(`${API_CONFIG.buildUrl('/api/gameplan')}?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`, { headers: API_CONFIG.getAuthHeaders() });
      const gameplanEndTime = performance.now();
      console.log(`⏱️ [PERF] loadTeamData() /api/gameplan: ${(gameplanEndTime - gameplanStartTime).toFixed(2)}ms`);
    } catch (error) {
      console.warn('Could not ensure team objects exist:', error);
    }
    
    // ✅ SS&S: Use ObjectId directly - backend accepts team_id parameter
    const teamDataStartTime = performance.now();
    console.log('⏱️ [PERF] loadTeamData() calling /franchise/team-data START');
    const response = await fetch(`${API_CONFIG.buildUrl('/franchise/team-data')}?franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`, { headers: API_CONFIG.getAuthHeaders() });
    const teamDataEndTime = performance.now();
    console.log(`⏱️ [PERF] loadTeamData() /franchise/team-data: ${(teamDataEndTime - teamDataStartTime).toFixed(2)}ms`);
    
    if (!response.ok) {
      console.error('Failed to load team data:', response.status, response.statusText);
      return;
    }
    
    const data = await response.json();
    
    // Also load players for top scorer lookup (wire by team_id per Data_Persistence_System / FCC)
    let players = [];
    try {
      const rosterStartTime = performance.now();
      const rosterResponse = await fetch(`${API_CONFIG.buildUrl(`/roster/${encodeURIComponent(userTeamId)}`)}?franchise_id=${encodeURIComponent(franchiseId)}&profile=1`, { headers: API_CONFIG.getAuthHeaders() });
      const rosterEndTime = performance.now();
      console.log(`⏱️ [PERF] loadTeamData() /roster (team_id): ${(rosterEndTime - rosterStartTime).toFixed(2)}ms`);
      if (rosterResponse.ok) {
        const rosterData = await rosterResponse.json();
        players = rosterData.players || [];
      }
    } catch (error) {
      console.warn('Could not load players for team data:', error);
    }
    
    teamData = {
      team_attributes: data.team_attributes || {},
      plays_data: data.plays_data || {},
      scouting_data: data.scouting_data || {},
      players: players
    };
    persistFccSessionCache();
    
    // Log all team attribute values on page load
    console.log('📊 [TEAM ATTRIBUTES] All team attribute values:', teamData.team_attributes);
    
    // Render if Team tab is active
    const teamTab = document.getElementById('team-tab');
    if (teamTab && teamTab.classList.contains('active')) {
      renderTeamReport();
      renderPlaybookSummary();
    }
    void renderHomeTab();
    
    const loadTeamDataEndTime = performance.now();
    console.log(`⏱️ [PERF] loadTeamData() function COMPLETE: ${(loadTeamDataEndTime - loadTeamDataStartTime).toFixed(2)}ms`);
  } catch (error) {
    console.error('Failed to load team data:', error);
  }
}

function renderTeamReport() {
  if (!teamData) return;
  
  const grid = document.getElementById('team-attributes-grid');
  if (!grid) return;
  
  grid.innerHTML = '';
  
  const teamAttrs = teamData.team_attributes || {};
  
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

function createTeamAttrItem(attrKey, currentValue, change) {
  const displayName = TEAM_ATTR_NAMES[attrKey];
  if (!displayName) return null;
  
  if (currentValue === undefined || currentValue === null) {
    currentValue = 0;
  }
  if (change === undefined || change === null) {
    change = 0;
  }
  
  const item = document.createElement('div');
  item.className = 'team-attr-item';
  
  const label = document.createElement('div');
  label.className = 'attr-label';
  
  const nameSpan = document.createElement('span');
  nameSpan.textContent = displayName;
  
  label.appendChild(nameSpan);
  item.appendChild(label);
  
  if (attrKey === 'team_chemistry') {
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
  } else if (attrKey === 'fb_opp_modifier' || attrKey === 'pt_opp_modifier') {
    const indicatorContainer = document.createElement('div');
    indicatorContainer.className = 'plus-minus-container';
    indicatorContainer.style.textAlign = 'center';
    indicatorContainer.style.marginTop = 'var(--spacing-sm)';
    
    const indicator = document.createElement('span');
    indicator.className = 'plus-minus-indicator';
    indicator.style.fontWeight = '700';
    
    if (currentValue >= 10) {
      indicator.textContent = '+++';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue >= 5) {
      indicator.textContent = '++';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue >= 1) {
      indicator.textContent = '+';
      indicator.className += ' plus-minus-positive';
    } else if (currentValue === 0) {
      indicator.textContent = '-';
      indicator.className += ' plus-minus-zero';
    } else if (currentValue >= -4) {
      indicator.textContent = '-';
      indicator.className += ' plus-minus-negative';
    } else if (currentValue >= -9) {
      indicator.textContent = '--';
      indicator.className += ' plus-minus-negative';
    } else {
      indicator.textContent = '---';
      indicator.className += ' plus-minus-negative';
    }
    
    indicatorContainer.appendChild(indicator);
    item.appendChild(indicatorContainer);
  } else {
    const pill = createPill(currentValue, attrKey);
    item.appendChild(pill);
  }
  
  return item;
}

function createPill(originalValue, attrKey) {
  const pill = document.createElement('div');
  pill.className = 'attr-pill';
  
  const centerLine = document.createElement('div');
  centerLine.className = 'pill-center-line';
  pill.appendChild(centerLine);
  
  let maxValue = 10;
  let value = originalValue;
  
  if (attrKey === 'shot_threshold') {
    maxValue = 100; // Range is 10 to 210, center at 110, so max deviation is 100
    value = 110 - originalValue; // Invert: lower is better (positive/green), higher is worse (negative/red)
  } else if (attrKey === 'rebound_modifier') {
    maxValue = 0.2;
    value = originalValue - 0.2; // Center at 0.2 (new range: 0.0-0.4)
  }
  
  if (value > 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-positive';
    const percentage = Math.min((value / maxValue) * 50, 50);
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  } else if (value < 0) {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-negative';
    const absValue = Math.abs(value);
    const percentage = Math.min((absValue / maxValue) * 50, 50);
    fill.style.width = `${percentage}%`;
    pill.insertBefore(fill, centerLine);
  }
  
  return pill;
}

function renderPlaybookSummary() {
  if (!teamData) return;
  
  const container = document.getElementById('playbook-summary-container');
  if (!container) return;
  
  container.innerHTML = '';
  
  const plays_data = teamData.plays_data || {};
  const scouting_data = teamData.scouting_data || {};
  
  const motion_plays = [];
  const set_plays = [];
  
  for (const [play_name, play_data] of Object.entries(plays_data)) {
    if (typeof play_data === 'object' && play_data !== null) {
      const resolvedName = play_data.name || play_name;
      const play_type = play_data.play_type || '';
      if (play_type === 'motion') {
        motion_plays.push({ ...play_data, name: resolvedName, display_name: resolvedName, play_key: play_name });
      } else if (play_type === 'set_play') {
        set_plays.push({ ...play_data, name: resolvedName, display_name: resolvedName, play_key: play_name });
      }
    }
  }
  
  motion_plays.sort((a, b) => a.name.localeCompare(b.name));
  set_plays.sort((a, b) => a.name.localeCompare(b.name));
  
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
  
  man_defenses.sort((a, b) => a.name.localeCompare(b.name));
  zone_defenses.sort((a, b) => a.name.localeCompare(b.name));
  
  const offenseSection = document.createElement('div');
  offenseSection.className = 'playbook-category';
  
  const offenseTitle = document.createElement('h3');
  offenseTitle.textContent = 'Offense';
  offenseSection.appendChild(offenseTitle);
  
  // Get players data for top scorer lookup (only for offensive plays)
  const players = teamData.players || [];
  
  if (motion_plays.length > 0) {
    motion_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking, and season_stats
      const playRow = createPlayRow(play.display_name || play.name, play, null, players);
      offenseSection.appendChild(playRow);
    });
  }
  
  if (set_plays.length > 0) {
    set_plays.forEach(play => {
      // Pass full play object to access effectiveness, momentum, cloaking, and season_stats
      const playRow = createPlayRow(play.display_name || play.name, play, null, players);
      offenseSection.appendChild(playRow);
    });
  }
  
  const emptyRow = document.createElement('div');
  emptyRow.className = 'playbook-empty-row';
  offenseSection.appendChild(emptyRow);
  
  container.appendChild(offenseSection);
  
  const defenseSection = document.createElement('div');
  defenseSection.className = 'playbook-category';
  
  const defenseTitle = document.createElement('h3');
  defenseTitle.textContent = 'Defense';
  defenseSection.appendChild(defenseTitle);
  
  if (man_defenses.length > 0) {
    man_defenses.forEach(defense => {
      // Pass full defense object to access effectiveness, momentum, cloaking
      const defenseRow = createPlayRow(defense.name, defense, null);
      defenseSection.appendChild(defenseRow);
    });
  }
  
  if (zone_defenses.length > 0) {
    zone_defenses.forEach(defense => {
      // Pass full defense object to access effectiveness, momentum, cloaking
      const defenseRow = createPlayRow(defense.name, defense, null);
      defenseSection.appendChild(defenseRow);
    });
  }
  
  container.appendChild(defenseSection);
}

function createPlayRow(playName, playData, change, players = []) {
  // playData can be an object with effectiveness, momentum, cloaking, or just a number (effectiveness)
  // Handle both formats for backward compatibility
  const effectiveness = typeof playData === 'object' ? (playData.effectiveness || 0) : (playData || 0);
  const momentum = typeof playData === 'object' ? (playData.momentum || 0) : 0;
  const cloaking = typeof playData === 'object' ? (playData.cloaking || 0) : 0;
  
  // Check if this is an offensive play (motion or set_play) to show success rate and top scorer
  const isOffensivePlay = typeof playData === 'object' && 
    (playData.play_type === 'motion' || playData.play_type === 'set_play');
  
  const row = document.createElement('div');
  row.className = 'playbook-row';
  if (playData && typeof playData === 'object' && playData.play_id) {
    row.dataset.playId = playData.play_id;
  }
  
  // Play name
  const nameDiv = document.createElement('div');
  nameDiv.className = 'playbook-name';
  nameDiv.textContent = playName;
  row.appendChild(nameDiv);
  
  // Metrics container - holds all three bars
  const metricsContainer = document.createElement('div');
  metricsContainer.className = 'playbook-metrics-container';
  
  // Command (Effectiveness) - Blue, 0-100 scale
  const commandMetric = createMetricBar('Command', effectiveness, 100, '#4a90e2', null);
  metricsContainer.appendChild(commandMetric);
  
  // Momentum - Orange, 0-10 scale
  const momentumMetric = createMetricBar('Momentum', momentum, 10, '#ff9800', null);
  metricsContainer.appendChild(momentumMetric);
  
  // Cloaking - Purple, 0-10 scale
  const cloakingMetric = createMetricBar('Cloaking', cloaking, 10, '#9c27b0', null);
  metricsContainer.appendChild(cloakingMetric);
  
  row.appendChild(metricsContainer);
  
  // Success Rate and Top Scorer column (only for offensive plays)
  if (isOffensivePlay) {
    const statsContainer = document.createElement('div');
    statsContainer.className = 'playbook-stats-container';
    statsContainer.style.display = 'flex';
    statsContainer.style.flexDirection = 'column';
    statsContainer.style.gap = '8px';
    
    // Calculate success rate from season_stats
    const seasonStats = playData.season_stats || {};
    const timesRun = seasonStats.times_run || 0;
    const successes = seasonStats.successes || 0;
    const successRate = timesRun > 0 ? Math.round((successes / timesRun) * 100) : 0;
    
    // Success Rate
    const successRateDiv = document.createElement('div');
    successRateDiv.className = 'playbook-success-rate';
    successRateDiv.textContent = `Success Rate: ${successRate}%`;
    statsContainer.appendChild(successRateDiv);
    
    // Top Scorer
    const topScorerDiv = document.createElement('div');
    topScorerDiv.className = 'playbook-top-scorer';
    
    const playerPoints = seasonStats.player_points || {};
    let topScorerId = null;
    let topScorerPoints = 0;
    
    // Find top scorer
    for (const [playerId, points] of Object.entries(playerPoints)) {
      if (points > topScorerPoints) {
        topScorerPoints = points;
        topScorerId = playerId;
      }
    }
    
    if (topScorerId && topScorerPoints > 0) {
      // Find player name
      const player = players.find(p => p._id === topScorerId || p.id === topScorerId);
      const playerName = player ? (player.name || `${player.first_name || ''} ${player.last_name || ''}`.trim()) : 'Unknown Player';
      topScorerDiv.textContent = `Top Scorer: ${playerName}, ${topScorerPoints} PTS`;
    } else {
      topScorerDiv.textContent = 'Top Scorer: N/A';
    }
    
    statsContainer.appendChild(topScorerDiv);
    row.appendChild(statsContainer);
  }
  
  return row;
}

function createMetricBar(title, value, maxValue, color, change) {
  const metricDiv = document.createElement('div');
  metricDiv.className = 'playbook-metric';
  
  // Title
  const titleDiv = document.createElement('div');
  titleDiv.className = 'playbook-metric-title';
  titleDiv.textContent = title;
  metricDiv.appendChild(titleDiv);
  
  // Progress bar container
  const progressContainer = document.createElement('div');
  progressContainer.className = 'playbook-progress-container';
  
  const progressBar = document.createElement('div');
  progressBar.className = 'playbook-progress-bar';
  
  const progressFill = document.createElement('div');
  progressFill.className = 'playbook-progress-fill';
  progressFill.style.backgroundColor = color;
  const percentage = Math.min(100, (value / maxValue) * 100);
  progressFill.style.width = `${percentage}%`;
  
  progressBar.appendChild(progressFill);
  progressContainer.appendChild(progressBar);
  metricDiv.appendChild(progressContainer);
  
  // Change indicator (only for Command/Effectiveness)
  if (change !== null && change !== undefined) {
    const changeDiv = document.createElement('div');
    changeDiv.className = 'playbook-change';
    
    if (change > 0) {
      changeDiv.textContent = `+${change}`;
      changeDiv.style.color = '#4CAF50'; // Green
    } else if (change < 0) {
      changeDiv.textContent = `-${Math.abs(change)}`;
      changeDiv.style.color = '#f44336'; // Red
    } else {
      changeDiv.textContent = '0';
      changeDiv.style.color = '#ffffff'; // White
    }
    
    metricDiv.appendChild(changeDiv);
  }
  
  return metricDiv;
}

// ✅ Phase 4.2: Roster stats rendering delegated to RosterStatsRenderer (rosterStatsRenderer.js)

// ✅ EOS TOURNAMENT: Render tournament bracket (shared with TCC via bracket.js)
async function renderTournamentBracket() {
  const container = document.getElementById('tournament-bracket-container');
  const titleEl = document.getElementById('fcc-tournament-title');
  if (!container) return;

  const topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
  const eosTournament = topData?.eos_tournament;
  const week = Number(topData?.week || 0);
  const userConference = topData?.user_conference != null ? String(topData.user_conference) : '';
  const userRegion = String(topData?.user_region || '').toUpperCase();
  const conferenceTournament = userConference ? (topData?.conference_tournaments || {})[userConference] : null;
  const regionTournamentRaw = userRegion ? (topData?.region_tournaments || {})[userRegion] : null;
  const regionTournament = regionTournamentRaw ? normalizeRegionBracket(regionTournamentRaw) : null;
  const nationalTournament = topData?.national_tournament || null;

  const hasBracketHistory = Boolean(eosTournament || conferenceTournament || regionTournament || nationalTournament);
  if (!hasBracketHistory) {
    if (titleEl) titleEl.textContent = 'End-of-Season Tournament';
    container.innerHTML = '<p>Tournament bracket not available.</p>';
    return;
  }

  let tournamentTitle = 'End-of-Season Tournament';
  if (week >= 27 && week <= 29) {
    tournamentTitle = 'Conference Tournament';
  } else if (week >= 30 && week <= 31) {
    tournamentTitle = 'Region Tournament';
  } else if (week >= 32 && week <= 36) {
    tournamentTitle = 'National Tournament';
  }
  if (titleEl) titleEl.textContent = tournamentTitle;

  // SS&S: Get team id→name map from franchise/team-stats (same pattern as TCC)
  let teamIdToNameMap = {};
  try {
    const teamStatsRes = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/team-stats')}?franchise_id=${franchiseId}`);
    const teams = teamStatsRes?.teams || [];
    teams.forEach(function (t) {
      if (t.team_id != null && t.team != null) {
        teamIdToNameMap[String(t.team_id)] = t.team;
        teamIdMetaMap[String(t.team_id)] = {
          team: t.team,
          mascot: t.mascot || '',
          conference: t.conference,
        };
      }
    });
  } catch (e) {
    console.warn('[FCC] Could not load team-stats for bracket names:', e);
  }

  function normalizeRegionBracket(rt) {
    if (!rt) return null;
    const finalList = rt.final || [];
    return {
      bracket: {
        round1: rt.round1 || [],
        round2: [],
        final: finalList,
      },
      seeds: {},
    };
  }

  function createBracketSection(sectionTitle, bracketPayload, layout, toneClass) {
    if (!bracketPayload || !bracketPayload.bracket) return null;

    const section = document.createElement('section');
    section.className = `fcc-tournament-section ${toneClass || ''}`.trim();

    const heading = document.createElement('h4');
    heading.className = 'fcc-tournament-section-title';
    heading.textContent = sectionTitle;
    section.appendChild(heading);

    const bracketRoot = document.createElement('div');
    bracketRoot.className = 'bracket';
    section.appendChild(bracketRoot);

    if (typeof renderBracketShared === 'function') {
      renderBracketShared(bracketRoot, bracketPayload.bracket || {}, teamIdToNameMap, {
        seeds: bracketPayload.seeds || {},
        layout: layout || 'full',
        getLogo: function (name) {
          return typeof getTeamAssetPath === 'function' ? getTeamAssetPath(name, 'banner_primary') : '/images/teams/general/general_banner_primary.jpg';
        },
        isUserTeam: function (id) {
          return userTeamId != null && (String(id) === String(userTeamId));
        },
        getTooltip: function (id, name) {
          const meta = teamIdMetaMap[String(id)] || {};
          const teamName = meta.team || name || '';
          const mascot = meta.mascot || '';
          if (!teamName) return '';
          return mascot ? `${teamName} ${mascot}` : teamName;
        },
      });
    } else {
      bracketRoot.innerHTML = '<p>Bracket renderer not loaded.</p>';
    }

    return section;
  }

  container.innerHTML = '';

  const sections = [];
  if (week >= 27 && week <= 29 && conferenceTournament) {
    sections.push(createBracketSection('Conference Tournament', conferenceTournament, 'full', 'fcc-tournament-tone-conference'));
  } else if (week >= 30 && week <= 31) {
    if (regionTournament) sections.push(createBracketSection('Region Tournament', regionTournament, 'compact4', 'fcc-tournament-tone-region'));
    if (conferenceTournament) sections.push(createBracketSection('Conference Tournament', conferenceTournament, 'full', 'fcc-tournament-tone-conference'));
  } else if (week >= 32 && week <= 36) {
    if (nationalTournament) sections.push(createBracketSection('National Tournament', nationalTournament, 'full', 'fcc-tournament-tone-national'));
    if (regionTournament) sections.push(createBracketSection('Region Tournament', regionTournament, 'compact4', 'fcc-tournament-tone-region'));
    if (conferenceTournament) sections.push(createBracketSection('Conference Tournament', conferenceTournament, 'full', 'fcc-tournament-tone-conference'));
  } else if (eosTournament) {
    sections.push(createBracketSection(tournamentTitle, eosTournament, week >= 30 && week <= 31 ? 'compact4' : 'full', 'fcc-tournament-tone-conference'));
  }

  const renderedSections = sections.filter(Boolean);
  if (!renderedSections.length) {
    container.innerHTML = '<p>Tournament bracket not available.</p>';
    return;
  }

  renderedSections.forEach(function (section, index) {
    if (index > 0) {
      const divider = document.createElement('hr');
      divider.className = 'fcc-tournament-divider';
      container.appendChild(divider);
    }
    container.appendChild(section);
  });

}

// Scouting Report functionality
let upcomingOpponent = null;
let upcomingOpponentId = null;

function updateScoutingButton(data) {
  const scoutingBtn = document.getElementById('scouting-report-btn');
  if (!scoutingBtn) return;
  const resolvedUserTeamName = data?.team || userTeamNameForLeaders || userTeamName || '';
  
  // ✅ EOS TOURNAMENT: Show button for regular season (weeks 1-26) and EOS Tournament (weeks 27-34)
  // Also show during preseason (week 0 or undefined) if there's a schedule
  const week = data?.week || data?.training_status?.current_week || 0;
  const eosTournamentActive = data?.eos_tournament_active || false;
  const eosTournament = data?.eos_tournament;
  
  // Check if user team is eliminated from tournament
  let userTeamEliminated = false;
  if (eosTournamentActive && eosTournament && userTeamId && week >= 27) {
    const bracket = eosTournament.bracket || {};
    const round1 = bracket.round1 || [];
    const round2 = bracket.round2 || [];
    const final = bracket.final || [];
    const allMatchups = [...round1, ...round2, ...final];
    const userInMatchup = allMatchups.some(m => 
      m.home_team === userTeamId || m.away_team === userTeamId
    );
    userTeamEliminated = !userInMatchup;
  }
  
  // Show button if: (regular season weeks 0-26) OR (EOS Tournament weeks 27-34 and user not eliminated)
  if (data && ((week >= 0 && week <= 26) || (week >= 27 && week <= 34 && !userTeamEliminated))) {
    // Get upcoming opponent from play-next-game endpoint (now handles both regular season and EOS Tournament)
    fetch(API_CONFIG.buildUrl('/franchise/play-next-game'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: franchiseId })
    })
    .then(res => res.json())
    .then(matchup => {
      upcomingOpponent = null;
      upcomingOpponentId = null;
      if (matchup && matchup.home && matchup.away) {
        // Prefer API-sourced team identity, then fall back to ObjectId match.
        if (resolvedUserTeamName === matchup.home) {
          upcomingOpponent = matchup.away;
          upcomingOpponentId = matchup.away_id;
        } else if (resolvedUserTeamName === matchup.away) {
          upcomingOpponent = matchup.home;
          upcomingOpponentId = matchup.home_id;
        } else if (userTeamId && matchup.home_id != null && matchup.away_id != null) {
          if (String(userTeamId) === String(matchup.home_id)) {
            upcomingOpponent = matchup.away;
            upcomingOpponentId = matchup.away_id;
          } else if (String(userTeamId) === String(matchup.away_id)) {
            upcomingOpponent = matchup.home;
            upcomingOpponentId = matchup.home_id;
          }
        }
        
        if (upcomingOpponent) {
          scoutingBtn.style.display = 'block';
        } else {
          scoutingBtn.style.display = 'none';
        }
      } else {
        scoutingBtn.style.display = 'none';
      }
    })
    .catch(err => {
      console.warn('Could not determine upcoming opponent:', err);
      scoutingBtn.style.display = 'none';
    });
  } else {
    scoutingBtn.style.display = 'none';
  }
}

async function loadScoutingReport() {
  playSound('click-tiny.wav');
  if (!upcomingOpponent || !franchiseId) {
    alert('No upcoming opponent found');
    return;
  }
  
  const modal = document.getElementById('scouting-report-modal');
  const loading = document.getElementById('scouting-loading');
  const content = document.getElementById('scouting-content');
  const title = document.getElementById('scouting-report-title');
  
  modal.style.display = 'flex';
  loading.style.display = 'block';
  content.style.display = 'none';
  title.textContent = `Scouting Report: ${upcomingOpponent}`;
  
  try {
    // Load opponent team data and last game play usage
    const authHeaders = API_CONFIG.getAuthHeaders();
    const [teamDataRes, playUsageRes] = await Promise.all([
      fetch(`${API_CONFIG.buildUrl('/franchise/team-data')}?franchise_id=${encodeURIComponent(franchiseId)}&team_name=${encodeURIComponent(upcomingOpponent)}`, { headers: authHeaders }),
      fetch(`${API_CONFIG.buildUrl('/franchise/scouting-report')}?franchise_id=${encodeURIComponent(franchiseId)}&team_name=${encodeURIComponent(upcomingOpponent)}`, { headers: authHeaders })
    ]);
    
    if (!teamDataRes.ok) throw new Error('Failed to load team data');
    if (!playUsageRes.ok) throw new Error('Failed to load play usage');
    
    const teamData = await teamDataRes.json();
    const playUsage = await playUsageRes.json();
    
    // ✅ SS&S: Use shared rendering functions
    if (typeof renderScoutingTeamReport === 'function' && typeof createTeamAttrItem === 'function') {
      renderScoutingTeamReport(teamData.team_attributes || {}, createTeamAttrItem);
    } else {
      console.error('Scouting report rendering functions not available');
    }
    
    if (typeof renderPlayUsage === 'function') {
      renderPlayUsage(playUsage.plays || [], 'No previous game data available. Opponent has not played a game yet this season.');
    } else {
      console.error('Play usage rendering function not available');
    }

    if (typeof setScoutingProjectedLineupData === 'function') {
      setScoutingProjectedLineupData(
        playUsage.projected_starting_five || [],
        playUsage.player_season_stats || {}
      );
    } else if (typeof renderProjectedStartingFive === 'function') {
      renderProjectedStartingFive(playUsage.projected_starting_five || []);
    }
    
    loading.style.display = 'none';
    content.style.display = 'block';
  } catch (error) {
    console.error('Error loading scouting report:', error);
    loading.textContent = `Error loading scouting report: ${error.message}`;
  }
}

// ✅ SS&S: Removed duplicate functions - now using shared functions from scoutingReport.js
// renderScoutingTeamReport, renderPlayUsage, and setupScoutingReport are now in /js/shared/scoutingReport.js

// ✅ SS&S: Initialize scouting report using shared function
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof setupScoutingReport === 'function') {
      setupScoutingReport(loadScoutingReport);
    }
  });
} else {
  if (typeof setupScoutingReport === 'function') {
    setupScoutingReport(loadScoutingReport);
  }
}

// ============================================================================
// 🛠️ DEV MODE: Simulate Entire Regular Season Popup (Temporary Development Feature)
// ============================================================================
// ⚠️  THIS IS A TEMPORARY DEVELOPMENT FEATURE
// ⚠️  To disable: Comment out the function below (lines ~1985-2090)
// ⚠️  To re-enable: Uncomment the function
// ============================================================================

function showDevSimPopup(topData) {
  const funcStartTime = performance.now();
  console.log('⏱️ [PERF] showDevSimPopup function START', { 
    hasTopData: !!topData,
    week: topData?.week,
    trainingWeek: topData?.training_status?.current_week,
    hasResults: !!topData?.results,
    resultsType: typeof topData?.results,
    resultsKeys: topData?.results ? Object.keys(topData.results).length : 'N/A'
  });
  
  // Only show if week is 1 and no games have been played
  const week = topData?.week || topData?.training_status?.current_week || 1;
  const results = topData?.results || {};
  const hasPlayedGames = Object.keys(results).length > 0;
  
  console.log('⏱️ [PERF] showDevSimPopup check', { week, hasPlayedGames, resultsKeys: Object.keys(results).length });
  
  // Check if games exist in database
  if (week === 1 && !hasPlayedGames) {
    console.log('⏱️ [PERF] showDevSimPopup - Creating popup DOM elements');
    const domStartTime = performance.now();
    // Create popup overlay
    const overlay = document.createElement('div');
    overlay.id = 'dev-sim-popup-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background: rgba(0, 0, 0, 0.7);
      z-index: 10000;
      display: flex;
      justify-content: center;
      align-items: center;
    `;
    
    // Create popup content
    const popup = document.createElement('div');
    popup.style.cssText = `
      background: white;
      padding: 30px;
      border-radius: 10px;
      max-width: 500px;
      text-align: center;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    `;
    
    popup.innerHTML = `
      <h2 style="margin-top: 0; color: #333;">🛠️ Dev Mode: Simulate Regular Season</h2>
      <p style="color: #666; margin-bottom: 20px;">
        This will simulate weeks 1-14 with auto-training and auto-lineups for all teams.
        <br><strong>This will skip directly to the tournament!</strong>
      </p>
      <div style="display: flex; gap: 10px; justify-content: center;">
        <button id="dev-sim-confirm-btn" style="
          padding: 12px 24px;
          background: #4a90e2;
          color: white;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          font-size: 16px;
          font-weight: bold;
        ">Simulate Regular Season</button>
        <button id="dev-sim-cancel-btn" style="
          padding: 12px 24px;
          background: #ccc;
          color: #333;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          font-size: 16px;
        ">Cancel</button>
      </div>
      <p style="color: #999; font-size: 12px; margin-top: 20px;">
        ⚠️ Development feature - can be disabled in code
      </p>
    `;
    
    overlay.appendChild(popup);
    document.body.appendChild(overlay);
    
    // Handle confirm button
    document.getElementById('dev-sim-confirm-btn').addEventListener('click', async () => {
      const btn = document.getElementById('dev-sim-confirm-btn');
      btn.disabled = true;
      btn.style.display = 'none';
      
      // Create progress container
      const progressContainer = document.createElement('div');
      progressContainer.id = 'dev-sim-progress';
      progressContainer.style.cssText = `
        max-height: 400px;
        overflow-y: auto;
        margin: 20px 0;
        padding: 15px;
        background: #f5f5f5;
        border-radius: 5px;
        font-family: monospace;
        font-size: 13px;
        line-height: 1.6;
        text-align: left;
      `;
      
      const progressList = document.createElement('div');
      progressList.id = 'dev-sim-progress-list';
      progressContainer.appendChild(progressList);
      
      // Insert progress container before buttons
      const buttonsContainer = popup.querySelector('div[style*="display: flex"]');
      if (buttonsContainer) {
        popup.insertBefore(progressContainer, buttonsContainer);
      } else {
        // Fallback: append to popup
        popup.appendChild(progressContainer);
      }
      
      function addProgressMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        const timestamp = new Date().toLocaleTimeString();
        const colors = {
          info: '#666',
          success: '#4a90e2',
          error: '#e74c3c',
          warning: '#f39c12'
        };
        messageDiv.style.cssText = `color: ${colors[type] || colors.info}; margin: 4px 0;`;
        messageDiv.textContent = `[${timestamp}] ${message}`;
        progressList.appendChild(messageDiv);
        progressContainer.scrollTop = progressContainer.scrollHeight;
      }
      
      try {
        const response = await fetch(API_CONFIG.buildUrl('/franchise/dev-sim-regular-season'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ franchise_id: franchiseId })
        });
        
        if (!response.ok) {
          throw new Error(`Simulation failed: ${response.status} ${response.statusText}`);
        }
        
        // Check if response is streaming (text/event-stream)
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('text/event-stream')) {
          // Fallback to JSON response (backward compatibility)
          const result = await response.json();
          addProgressMessage(result.message || 'Simulation complete!', 'success');
          setTimeout(() => {
            popup.innerHTML = `
              <h2 style="margin-top: 0; color: #4a90e2;">✅ Simulation Complete!</h2>
              <p style="color: #666; margin-bottom: 20px;">
                ${result.message || 'Regular season simulated successfully.'}
              </p>
              <button id="dev-sim-close-btn" style="
                padding: 12px 24px;
                background: #4a90e2;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
              ">Close & Reload</button>
            `;
            document.getElementById('dev-sim-close-btn').addEventListener('click', () => {
              document.body.removeChild(overlay);
              location.reload();
            });
          }, 1000);
          return;
        }
        
        // Stream SSE events
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        addProgressMessage('Starting simulation...', 'info');
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            break;
          }
          
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6)); // Remove 'data: ' prefix
                
                // Handle different event types
                switch (data.type) {
                  case 'start':
                    addProgressMessage(data.message, 'info');
                    break;
                  case 'week_start':
                    addProgressMessage(`📅 ${data.message}`, 'info');
                    break;
                  case 'training_start':
                    addProgressMessage(`🏋️ ${data.message}`, 'info');
                    break;
                  case 'training_progress':
                    addProgressMessage(`  ✓ ${data.message}`, 'success');
                    break;
                  case 'training_complete':
                    addProgressMessage(`✅ ${data.message}`, 'success');
                    break;
                  case 'training_skip':
                    addProgressMessage(`⏭️ ${data.message}`, 'warning');
                    break;
                  case 'training_error':
                    addProgressMessage(`⚠️ ${data.message}`, 'error');
                    break;
                  case 'game_start':
                    addProgressMessage(`🏀 ${data.message}`, 'info');
                    break;
                  case 'game_simulating':
                    addProgressMessage(`  ⏳ ${data.message}`, 'info');
                    break;
                  case 'game_result':
                    addProgressMessage(`  📊 ${data.message}`, 'success');
                    break;
                  case 'game_finalizing':
                    addProgressMessage(`  💾 ${data.message}`, 'info');
                    break;
                  case 'week_completing':
                    addProgressMessage(`  🔄 ${data.message}`, 'info');
                    break;
                  case 'week_complete':
                    addProgressMessage(`✅ ${data.message}`, 'success');
                    break;
                  case 'week_skip':
                    addProgressMessage(`⏭️ ${data.message}`, 'warning');
                    break;
                  case 'week_error':
                    addProgressMessage(`⚠️ ${data.message}`, 'error');
                    break;
                  case 'complete':
                    addProgressMessage(`🎉 ${data.message}`, 'success');
                    // Show completion UI
                    setTimeout(() => {
                      popup.innerHTML = `
                        <h2 style="margin-top: 0; color: #4a90e2;">✅ Simulation Complete!</h2>
                        <p style="color: #666; margin-bottom: 20px;">
                          ${data.message || 'Regular season simulated successfully.'}
                        </p>
                        <button id="dev-sim-close-btn" style="
                          padding: 12px 24px;
                          background: #4a90e2;
                          color: white;
                          border: none;
                          border-radius: 5px;
                          cursor: pointer;
                          font-size: 16px;
                        ">Close & Reload</button>
                      `;
                      document.getElementById('dev-sim-close-btn').addEventListener('click', () => {
                        document.body.removeChild(overlay);
                        location.reload();
                      });
                    }, 1000);
                    break;
                  case 'error':
                    addProgressMessage(`❌ ${data.message}`, 'error');
                    throw new Error(data.message);
                  default:
                    if (data.message) {
                      addProgressMessage(data.message, 'info');
                    }
                }
              } catch (parseError) {
                console.error('Error parsing SSE data:', parseError, line);
              }
            }
          }
        }
      } catch (error) {
        console.error('Dev sim error:', error);
        addProgressMessage(`❌ Error: ${error.message}`, 'error');
        setTimeout(() => {
          popup.innerHTML = `
            <h2 style="margin-top: 0; color: #e74c3c;">❌ Simulation Failed</h2>
            <p style="color: #666; margin-bottom: 20px;">
              ${error.message || 'An error occurred during simulation.'}
            </p>
            <button id="dev-sim-close-btn" style="
              padding: 12px 24px;
              background: #ccc;
              color: #333;
              border: none;
              border-radius: 5px;
              cursor: pointer;
              font-size: 16px;
            ">Close</button>
          `;
          document.getElementById('dev-sim-close-btn').addEventListener('click', () => {
            document.body.removeChild(overlay);
          });
        }, 2000);
      }
    });
    
    // Handle cancel button
    document.getElementById('dev-sim-cancel-btn').addEventListener('click', () => {
      document.body.removeChild(overlay);
    });
    
    // Close on overlay click (outside popup)
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        document.body.removeChild(overlay);
      }
    });
    
    const domEndTime = performance.now();
    console.log(`⏱️ [PERF] showDevSimPopup - DOM creation: ${(domEndTime - domStartTime).toFixed(2)}ms`);
  } else {
    console.log('⏱️ [PERF] showDevSimPopup - Popup NOT shown (week !== 1 or hasPlayedGames)');
  }
  
  const funcEndTime = performance.now();
  console.log(`⏱️ [PERF] showDevSimPopup function COMPLETE: ${(funcEndTime - funcStartTime).toFixed(2)}ms`);
}

// ============================================================================
// 🛠️ END DEV MODE FEATURE
// ============================================================================
