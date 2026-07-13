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

function fccCpuSimNeedsRecovery(data) {
  const resume = data && data.cpu_sim_resume;
  return !!(resume && resume.phase_b_required && resume.can_resume_phase_b);
}

function fccCpuSimProgressCopy(resume) {
  const week = Number(resume && resume.week) || 1;
  const completed = Number(resume && resume.completed_matchups) || 0;
  const expected = Number(resume && resume.expected_matchups) || 0;
  if (expected > 0) {
    return `Week ${week} · ${completed}/${expected} computer games complete`;
  }
  return `Week ${week} · finishing computer games`;
}

async function recoverCpuSimsBeforeFccRender(topData) {
  if (!fccCpuSimNeedsRecovery(topData)) return topData;
  const resume = topData.cpu_sim_resume || {};
  const week = Number(resume.week || topData.week || 0);
  if (!franchiseId || !week) return topData;

  if (window.PageLoadOverlay && window.PageLoadOverlay.show) {
    window.PageLoadOverlay.show({
      variant: 'pulse',
      label: 'Simulating Computer Games',
      title: 'Finishing Week',
      subtitle: fccCpuSimProgressCopy(resume),
      teamName: topData.team || '',
      assetKey: 'banner_primary',
    });
  }

  try {
    const mod = await import('/js/phaser/utils/franchisePhaseBClient.js');
    const res = await mod.getOrStartFranchisePhaseB({ franchise_id: franchiseId, week });
    if (!res || !res.ok) {
      let detail = '';
      try {
        detail = res ? await res.text() : '';
      } catch (_) {}
      throw new Error(`phase-b failed (${res ? res.status : 'no response'}) ${detail}`);
    }
    try {
      localStorage.removeItem('franchise_complete_week_pending');
      localStorage.removeItem('franchise_eog_pgpc_snapshot');
    } catch (_) {}
    const refreshed = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
    return refreshed || topData;
  } catch (err) {
    console.error('[FCC CPU SIM RESUME] Could not finish computer games:', err);
    alert('Could not finish computer games. Please try again.');
    return topData;
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
let currentWeekInviteRecruitCache = null;
let newLeanRecruitIdsCache = [];
let fccTeamStatsSummaryCache = null;
let commandCenterTopDataCache = null;
let playbooksWeekSavedCache = null;
let fccPlaybooksSummaryCache = null;
let userRosterPlayersCache = [];
let userScheduleDataCache = null;
let homeLastGameDataCache = null;
let fccNewsListCache = null;
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
const GENERIC_GAMEPLAN_SCALE = {
  0: 'Never',
  1: 'Less',
  2: 'Normal',
  3: 'More',
  4: 'Most'
};
const GAMEPLAN_LABELS = {
  offense: 'Offense',
  inside: 'Inside',
  attack: 'Attack',
  outside: 'Outside',
  tempo: 'Offense Tempo',
  alterations: 'Play Alteration',
  fast_breaks: 'Fast Breaks',
  defense: 'Defense',
  aggression: 'Aggression',
  hc_trap: 'Half-Court Trap',
  fc_press: 'Full-Court Press',
  rebounding: 'Rebounding'
};
// Row-major pairs for the 2-column FCC grid — must match game-plan.html columns:
// Left: offense, inside, attack, outside, tempo, alterations
// Right: defense, aggression, hc_trap, fc_press, fast_breaks, rebounding
const GAMEPLAN_DISPLAY_ORDER = [
  'offense',
  'defense',
  'inside',
  'aggression',
  'attack',
  'hc_trap',
  'outside',
  'fc_press',
  'tempo',
  'fast_breaks',
  'alterations',
  'rebounding'
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
  return `${FCC_SESSION_CACHE_PREFIX}:${franchiseId || ''}:${userTeamId || 'unknown'}`;
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
      teamId: userTeamId || null,
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
  if (cached.teamId && userTeamId && String(cached.teamId) !== String(userTeamId)) {
    return false;
  }
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

function invalidateFccTeamScopedCaches() {
  standingsDataCache = null;
  teamData = null;
  fccPlaybooksSummaryCache = null;
  userRosterPlayersCache = [];
  homeOpponentRosterCache.clear();
  invalidateHomeWeekSensitiveCaches();
}

function adoptAuthoritativeFccTeamId(topData) {
  const authoritativeTeamId = topData?.team_id ? String(topData.team_id) : '';
  if (!authoritativeTeamId) return false;

  const previousTeamId = userTeamId ? String(userTeamId) : '';
  if (previousTeamId && previousTeamId !== authoritativeTeamId) {
    console.warn('[FCC] Replacing stale team_id with authoritative command-center team_id', {
      previousTeamId,
      authoritativeTeamId
    });
    invalidateFccTeamScopedCaches();
  }

  if (previousTeamId !== authoritativeTeamId) {
    userTeamId = authoritativeTeamId;
    localStorage.setItem('franchise_user_team_id', userTeamId);
    emitDisplayContextUpdate();
    return true;
  }

  return false;
}

function invalidateHomeWeekSensitiveCaches() {
  userScheduleDataCache = null;
  homeLastGameDataCache = null;
  fccNewsListCache = null;
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
  const rankLabelEl = document.getElementById('fcc-rank-label');
  if (seasonLabelEl) {
    const seasonNumber = Number(data.current_season || 1);
    const weekNumber = Number(data.week || 1);
    seasonLabelEl.textContent = `Season ${seasonNumber} / Week ${weekNumber}`;
  }
  if (rankLabelEl) {
    rankLabelEl.textContent = `National Rank: ${data.rank || '--'}`;
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
  applyScheduleTabMode(Number(data.week || 1));
  const wk = Number(data.week || 1);
  if (Number.isFinite(wk) && wk >= 27 && document.getElementById('schedule-tab')?.classList.contains('active')) {
    void renderTournamentBracket();
  }
}

/**
 * Week 27+: tab label "Tournament", show bracket mount + footer links; else regular-season schedule.
 * Uses franchise command-center `week` (same source as header season/week label).
 */
function applyScheduleTabMode(weekArg) {
  const w = weekArg !== undefined && weekArg !== null
    ? Number(weekArg)
    : Number(commandCenterTopDataCache?.week || 1);
  const tabBtn = document.querySelector('.tab-buttons button[data-tab="schedule-tab"]');
  const regularView = document.getElementById('fcc-regular-schedule-view');
  const regularFooter = document.getElementById('fcc-regular-schedule-footer');
  const tournamentView = document.getElementById('fcc-tournament-view');
  const tournamentFooter = document.getElementById('fcc-tournament-footer');
  const isTournament = Number.isFinite(w) && w >= 27;

  if (tabBtn) tabBtn.textContent = isTournament ? 'Tournament' : 'Schedule';
  if (regularView) regularView.style.display = isTournament ? 'none' : '';
  if (regularFooter) regularFooter.style.display = isTournament ? 'none' : '';
  if (tournamentView) tournamentView.style.display = isTournament ? '' : 'none';
  if (tournamentFooter) tournamentFooter.style.display = isTournament ? 'flex' : 'none';
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

function persistFranchiseDisplayColorContext(topData) {
  if (typeof localStorage === 'undefined') return;
  try {
    const teamName = String(topData?.team || '').trim();
    const teamPrimaryColor = normalizeHexColor(topData?.primary_color);
    if (teamName) localStorage.setItem('franchise_user_team', teamName);
    if (teamPrimaryColor) {
      localStorage.setItem('franchise_user_team_primary_color', teamPrimaryColor);
    } else {
      localStorage.removeItem('franchise_user_team_primary_color');
    }
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

// Render the logged-in user's handle + lead-archetype badge in the header top-left.
// Username comes from the page's existing /api/auth/me data (window.__gobAuthMeData);
// the badge reuses the shared GOBArchetype utility (graceful no-badge when no archetype).
function renderFccUserIdentity(meData) {
  const nameEl = document.getElementById('fcc-username');
  const badgeHost = document.getElementById('fcc-username-badge');
  if (!nameEl || !badgeHost) return;
  const username = meData && meData.username ? String(meData.username) : '';
  nameEl.textContent = username;
  nameEl.title = username;
  badgeHost.innerHTML = '';
  const lead = window.GOBArchetype ? window.GOBArchetype.leadFrom(meData) : '';
  if (lead && window.GOBArchetype) {
    const badge = window.GOBArchetype.createBadge(lead, 26);
    if (badge) badgeHost.appendChild(badge);
  }
}

if (window.__gobAuthMeData) {
  renderFccUserIdentity(window.__gobAuthMeData);
}

window.addEventListener('gob:auth-me-loaded', (event) => {
  syncFccDisplayColorFromAccountSettings(event.detail || {});
  renderFccUserIdentity(event.detail || window.__gobAuthMeData);
});

window.addEventListener('gob:account-settings-updated', (event) => {
  syncFccDisplayColorFromAccountSettings(event.detail || {});
  renderFccUserIdentity(event.detail || window.__gobAuthMeData);
});

let standingsDataCache = null;

function buildFranchiseTeamPageUrl(teamId, teamName, returnTab) {
  const returnUrl = encodeURIComponent(getCurrentRelativeUrl());
  return `/team-roster-view.html?mode=franchise&franchise_id=${franchiseId}&team_id=${encodeURIComponent(teamId)}&team_name=${encodeURIComponent(teamName)}&return_tab=${returnTab}&return_url=${returnUrl}`;
}

function buildTeamLink(t) {
  const teamLink = document.createElement('a');
  teamLink.href = buildFranchiseTeamPageUrl(t.team_id, t.name, 'standings-tab');
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

function getStandingsTeamEntry(teamId) {
  return (standingsDataCache?.standings || []).find((entry) => String(entry.team_id || '') === String(teamId)) || null;
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
  params.set('user_team_only', '1');
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

function getScheduleGameForWeek(weekNumber) {
  return getUserScheduleGames().find((game) => Number(game.week || 0) === Number(weekNumber)) || null;
}

function getScheduleRowMarkup(label, detail, detailClass = '') {
  return `
    <div class="fcc-schedule-row">
      <span class="fcc-schedule-week">${escapeHomeHtml(label)}</span>
      <span class="fcc-schedule-detail ${detailClass}">${escapeHomeHtml(detail)}</span>
    </div>
  `;
}

function formatScheduleGameDetail(game) {
  if (!game) {
    return { text: 'Open', className: '' };
  }
  const opponentId = getOpponentIdFromGame(game);
  const opponentName = getScheduleDisplayName(opponentId) || 'TBD';
  const matchupLabel = getMatchupLabelForGame(game);
  const baseText = `${matchupLabel} ${opponentName}`;
  const awayScore = Number(game.away_score ?? 0);
  const homeScore = Number(game.home_score ?? 0);
  const isComplete = game.status === 'complete' || (Number.isFinite(awayScore) && Number.isFinite(homeScore) && (awayScore > 0 || homeScore > 0));
  if (!isComplete) {
    return { text: baseText, className: 'is-pending' };
  }
  const userIsHome = String(game.home_team_id) === String(userTeamId);
  const userScore = userIsHome ? homeScore : awayScore;
  const oppScore = userIsHome ? awayScore : homeScore;
  let className = 'is-complete-tie';
  if (userScore > oppScore) className = 'is-complete-win';
  else if (userScore < oppScore) className = 'is-complete-loss';
  return {
    text: `${baseText} ${userScore}-${oppScore}`,
    className
  };
}

function buildScheduleColumnMarkup(title, weeks, extraRows = []) {
  const rows = weeks.map((weekNumber) => {
    const game = getScheduleGameForWeek(weekNumber);
    const detail = formatScheduleGameDetail(game);
    return getScheduleRowMarkup(`Wk ${weekNumber}`, detail.text, detail.className);
  });
  extraRows.forEach((rowText) => {
    rows.push(getScheduleRowMarkup('', rowText, 'is-tournament'));
  });
  return `
    <section class="fcc-schedule-column">
      <div class="fcc-schedule-column-head">${escapeHomeHtml(title)}</div>
      <div class="fcc-schedule-column-body">${rows.join('')}</div>
    </section>
  `;
}

async function renderScheduleTab() {
  applyScheduleTabMode();
  const weekNum = Number(commandCenterTopDataCache?.week || 0);
  if (Number.isFinite(weekNum) && weekNum >= 27) {
    await renderTournamentBracket();
    return;
  }
  const host = document.getElementById('fcc-schedule-grid');
  if (!host) return;
  if (!franchiseId) {
    host.innerHTML = '<div class="fcc-game-plan-empty">Schedule unavailable.</div>';
    return;
  }
  if (!userScheduleDataCache) {
    host.innerHTML = '<div class="fcc-game-plan-empty">Loading schedule...</div>';
  }
  await ensureHomeScheduleData();
  if (!userScheduleDataCache) {
    host.innerHTML = '<div class="fcc-game-plan-empty">Schedule unavailable.</div>';
    return;
  }
  host.innerHTML = [
    buildScheduleColumnMarkup('Weeks 1-7', [1, 2, 3, 4, 5, 6, 7]),
    buildScheduleColumnMarkup('Weeks 8-14', [8, 9, 10, 11, 12, 13, 14]),
    buildScheduleColumnMarkup('Weeks 15-21', [15, 16, 17, 18, 19, 20, 21]),
    buildScheduleColumnMarkup('Weeks 22-26', [22, 23, 24, 25, 26], [
      'Conference Tournaments',
      'Region Tournaments',
      'National Tournament'
    ])
  ].join('');
}

function renderHomeMatchupCard(bodyId, summary, options = {}) {
  const body = document.getElementById(bodyId);
  if (!body) return;
  if (!summary) {
    const emptyLabel = options.emptyMessage != null ? options.emptyMessage : 'N/A';
    body.innerHTML = createEmptyHomeState(emptyLabel);
    return;
  }
  const opponentName = summary.opponent_team_name || 'Opponent';
  const opponentMascot = String(summary.opponent_team_mascot || '').trim();
  const opponentRegion = String(summary.opponent_team_region || '').trim().toUpperCase();
  const opponentConference = summary.opponent_team_conference;
  const opponentRegionConference = opponentRegion && opponentConference != null && opponentConference !== ''
    ? `${opponentRegion}${opponentConference}`
    : '';
  const opponentBaseDisplayName = opponentMascot ? `${opponentName} ${opponentMascot}` : opponentName;
  const opponentDisplayName = opponentRegionConference
    ? `${opponentBaseDisplayName} (${opponentRegionConference})`
    : opponentBaseDisplayName;
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
          <div class="fcc-home-opponent-name">${escapeHomeHtml(opponentDisplayName)}</div>
          <div class="fcc-home-detail-line fcc-home-meta-row">
            <span>Record: ${escapeHomeHtml(`${summary.record?.wins || 0}-${summary.record?.losses || 0}`)}</span>
            <span>Rank: ${escapeHomeHtml(summary.rank || 'N/A')}</span>
          </div>
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

function getNewLeanRecruitIdSet() {
  return new Set((newLeanRecruitIdsCache || []).map((id) => String(id)));
}

function isNewLeanRecruit(recruit) {
  if (!recruit) return false;
  const recruitId = recruit.recruitId != null ? recruit.recruitId : recruit.recruit_id;
  return getNewLeanRecruitIdSet().has(String(recruitId));
}

function partitionRecruitsWithNewLeans(recruits, sortFn, sortState) {
  const newLeanIds = getNewLeanRecruitIdSet();
  if (!newLeanIds.size) {
    return sortFn ? sortFn(recruits, sortState) : recruits.slice();
  }
  const newOnes = [];
  const rest = [];
  recruits.forEach((recruit) => {
    if (newLeanIds.has(String(recruit.recruitId))) newOnes.push(recruit);
    else rest.push(recruit);
  });
  if (!sortFn) return newOnes.concat(rest);
  return sortFn(newOnes, sortState).concat(sortFn(rest, sortState));
}

function buildHomeRecruitRowHtml(recruit) {
  const rowHtml = `
    <div class="fcc-home-recruit-row">
      <span class="fcc-home-recruit-name">${escapeHomeHtml(recruit.name || '--')}</span>
      <span class="fcc-home-recruit-arch">${escapeHomeHtml(recruit.archetype || '--')}</span>
      <span class="fcc-home-recruit-stat">${escapeHomeHtml(recruit.height || '--')}</span>
      <span class="fcc-home-recruit-stat">${escapeHomeHtml(recruit.weight ?? '--')}</span>
      <span class="fcc-home-recruit-stat ${typeof window.getRecruitRtBucketClassForYear === 'function' ? window.getRecruitRtBucketClassForYear(recruit.rt, recruit.year) : ''}">${escapeHomeHtml(recruit.rt ?? '--')}</span>
    </div>
  `;
  if (!isNewLeanRecruit(recruit)) return rowHtml;
  return `
    <div class="fcc-newlean-row">
      ${rowHtml}
      <div class="fcc-newlean-tag"><span class="fcc-newlean-badge">New</span></div>
    </div>
  `;
}

function buildFccInviteBlockHtml(recruit, week, wide) {
  if (!recruit) return '';
  const isAssigned = recruit.status === 'assigned';
  const rtClass = typeof window.getRecruitRtBucketClassForYear === 'function'
    ? window.getRecruitRtBucketClassForYear(recruit.rt, recruit.year)
    : '';
  const weightDisplay = recruit.weight != null ? recruit.weight : '--';
  const meta = `${recruit.archetype || '--'} · ${recruit.height || '--'} / ${weightDisplay}`;
  const rtDisplay = recruit.rt != null ? recruit.rt : '--';
  const eyebrow = isAssigned ? 'Recruiting Visit' : `Week ${Number(week)} Invite`;
  const statusHtml = isAssigned
    ? ''
    : '<span class="fcc-invite__status"><span class="fcc-invite__dot" aria-hidden="true"></span>Visit Pending</span>';
  const topHtml = `
    <div class="fcc-invite__top">
      <span class="fcc-invite__eyebrow">${escapeHomeHtml(eyebrow)}</span>
      ${statusHtml}
    </div>
  `;
  const idHtml = `
    <div class="fcc-invite__id">
      <span class="fcc-invite__name">${escapeHomeHtml(recruit.name || '--')}</span>
      <span class="fcc-invite__meta">${escapeHomeHtml(meta)}</span>
    </div>
  `;
  const rtHtml = `
    <div class="fcc-invite__rt">
      <span class="fcc-invite__rtnum ${rtClass}">${escapeHomeHtml(rtDisplay)}</span>
      <span class="fcc-invite__rtlabel">RT</span>
    </div>
  `;
  if (wide) {
    return `<div class="fcc-invite fcc-invite--wide">${topHtml}${idHtml}${rtHtml}</div>`;
  }
  return `<div class="fcc-invite">${topHtml}<div class="fcc-invite__body">${idHtml}${rtHtml}</div></div>`;
}

function renderFccRecruitsInviteBanner() {
  const host = document.getElementById('fcc-recruits-invite');
  if (!host) return;
  const week = Number(document.body.dataset.fccWeek || commandCenterTopDataCache?.week || 1);
  const invite = currentWeekInviteRecruitCache;
  if (week < 20 || week > 26 || !invite) {
    host.innerHTML = '';
    host.hidden = true;
    return;
  }
  host.innerHTML = buildFccInviteBlockHtml(invite, week, true);
  host.hidden = false;
}

function renderHomeRecruitingCard() {
  const body = document.getElementById('home-recruiting-body');
  if (!body) return;
  const week = Number(commandCenterTopDataCache?.week || document.body.dataset.fccWeek || 1);
  const inviteBlock = (week >= 20 && week <= 26 && currentWeekInviteRecruitCache)
    ? buildFccInviteBlockHtml(currentWeekInviteRecruitCache, week, false)
    : '';
  const recruits = partitionRecruitsWithNewLeans(
    [...leanRecruitsDataCache].sort((a, b) => Number(b.rt || 0) - Number(a.rt || 0)),
    null,
    null
  );
  body.innerHTML = `
    ${inviteBlock}
    <div class="fcc-home-recruiting">
      <div class="fcc-home-list-scroll">
        <div class="fcc-home-recruit-header">
          <span>Recruit</span>
          <span>Arch.</span>
          <span>HT</span>
          <span>WT</span>
          <span>RT</span>
        </div>
        ${recruits.map((recruit) => buildHomeRecruitRowHtml(recruit)).join('')}
      </div>
    </div>
  `;
}

function renderHomeNewsCard() {
  const body = document.getElementById('home-news-body');
  if (!body) return;
  const seeAllLink = document.getElementById('home-news-see-all-link');
  if (seeAllLink) seeAllLink.href = buildStandaloneNewsUrl(null);
  const headlines = (commandCenterTopDataCache?.news_headlines || []).slice(0, 5);
  if (!headlines.length) {
    body.innerHTML = createEmptyHomeState('No News To Report');
    return;
  }
  body.innerHTML = `
    <div class="fcc-home-list-scroll">
      ${headlines.map((item) => `
        <a class="fcc-home-news-row" href="${buildStandaloneNewsUrl(item.story_id)}">
          <span class="fcc-home-news-headline">${escapeHomeHtml(item.headline || '--')}</span>
          <span class="fcc-home-list-meta">Wk ${escapeHomeHtml(item.week ?? '--')}</span>
        </a>
      `).join('')}
    </div>
  `;
}

function buildStandaloneNewsUrl(storyId) {
  const q = new URLSearchParams();
  if (franchiseId) q.set('franchise_id', franchiseId);
  if (userTeamId) q.set('team_id', userTeamId);
  if (storyId) q.set('story', storyId);
  const qs = q.toString();
  return `/news.html${qs ? `?${qs}` : ''}`;
}

async function renderNewsTab() {
  const host = document.getElementById('fcc-news-list');
  if (!host) return;
  if (!fccNewsListCache) {
    const data = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/news')}?franchise_id=${franchiseId}`);
    if (!data) {
      host.innerHTML = '<div class="fcc-news-tab-empty">Failed to load news.</div>';
      return;
    }
    fccNewsListCache = Array.isArray(data.news) ? data.news : [];
  }
  const news = fccNewsListCache;
  if (!news.length) {
    host.innerHTML = '<div class="fcc-news-tab-empty">No News To Report</div>';
    return;
  }
  // Group stories by release week, newest week first (season_news is newest first).
  const byWeek = new Map();
  news.forEach((story) => {
    const week = Number(story.week || 0);
    if (!byWeek.has(week)) byWeek.set(week, []);
    byWeek.get(week).push(story);
  });
  const weeks = [...byWeek.keys()].sort((a, b) => b - a);
  host.innerHTML = weeks.map((week) => `
    <section class="fcc-data-card fcc-news-tab-week">
      <div class="fcc-news-tab-week-title">Week ${week}</div>
      <div class="fcc-news-tab-week-body">
        ${byWeek.get(week).map((story) => `
          <a class="fcc-news-tab-headline" href="${buildStandaloneNewsUrl(story.story_id)}">${escapeHomeHtml(story.headline || '--')}</a>
        `).join('')}
      </div>
    </section>
  `).join('');
}

async function renderHomeTab() {
  renderHomeStandingsCard();
  renderHomeRankingsCard();
  renderHomeLockerRoomCard();
  renderHomeTeamStatsCard();
  renderHomeRecruitingCard();
  renderHomeNewsCard();
  renderHomeMatchupCard('home-next-game-body', commandCenterTopDataCache?.next_game_summary || null, {
    emptyMessage: commandCenterTopDataCache?.next_game_is_bye ? 'Bye' : 'N/A'
  });
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
  const scheduleFullLink = document.getElementById('schedule-full-link');
  if (scheduleFullLink) scheduleFullLink.href = `/schedule.html${q()}`;
  const tournamentScheduleLink = document.getElementById('tournament-schedule-link');
  if (tournamentScheduleLink) tournamentScheduleLink.href = `/schedule.html${q()}`;
  const statsNavBtn = document.getElementById('stats-nav-btn');
  if (statsNavBtn) statsNavBtn.dataset.route = '';
  const teamStatsFullLink = document.getElementById('team-stats-full-link');
  if (teamStatsFullLink) teamStatsFullLink.href = `/team-stats.html${q()}`;
  const leadersFullLink = document.getElementById('leaders-full-link');
  if (leadersFullLink) leadersFullLink.href = `/leaders.html${q()}`;
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
  if (rAwards) rAwards.href = `/leaders.html${q()}`;
}

function formatTeamStatsPercent(numerator, denominator) {
  return denominator > 0 ? (((numerator || 0) / denominator) * 100).toFixed(1) + '%' : '0.0%';
}

const FCC_LEADER_CATEGORY_ORDER = ['PTS', '3PTM', 'AST', 'BLK', 'FG%', 'REB', 'STL', 'DEF%'];
const FCC_LEADER_CATEGORY_LABELS = {
  PTS: 'Points',
  '3PTM': '3 PT Made',
  AST: 'Assists',
  BLK: 'Blocks',
  'FG%': 'FG%',
  REB: 'Rebounds',
  STL: 'Steals',
  'DEF%': 'DEF%',
};

function formatLeaderValue(category, value) {
  if (value == null || value === '') return '--';
  if (category === 'FG%' || category === 'DEF%') {
    const numeric = Number(value);
    return `${Number.isFinite(numeric) ? numeric.toFixed(1) : '0.0'}%`;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(1).replace(/\.0$/, '') : String(value);
}

function escapeFccLeaderHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

async function ensureConferenceLeaders() {
  if (leadersDataCache || !franchiseId) return leadersDataCache;
  leadersDataCache = await fetchJSON(
    `${API_CONFIG.buildUrl('/franchise/leaders')}?franchise_id=${encodeURIComponent(franchiseId)}&scope=season&view_scope=conference&limit=5`
  );
  return leadersDataCache;
}

async function renderFccLeadersSummary() {
  const grid = document.getElementById('fcc-leaders-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="fcc-leader-card"><div class="fcc-leader-card-empty">Loading leaders...</div></div>';
  const data = await ensureConferenceLeaders();
  if (!data) {
    grid.innerHTML = '<div class="fcc-leader-card"><div class="fcc-leader-card-empty">Failed to load leaders.</div></div>';
    return;
  }
  grid.innerHTML = '';
  FCC_LEADER_CATEGORY_ORDER.forEach((category) => {
    const card = document.createElement('section');
    card.className = 'fcc-leader-card';
    const header = document.createElement('div');
    header.className = 'fcc-leader-card-header';
    header.textContent = FCC_LEADER_CATEGORY_LABELS[category] || category;
    card.appendChild(header);
    const list = document.createElement('div');
    list.className = 'fcc-leader-card-list';
    const leaders = Array.isArray(data[category]) ? data[category].slice(0, 5) : [];
    if (!leaders.length) {
      list.innerHTML = '<div class="fcc-leader-card-empty">No leaders available.</div>';
    } else {
      leaders.forEach((leader, index) => {
        const row = document.createElement('div');
        row.className = 'fcc-leader-row';
        row.innerHTML = `
          <div class="fcc-leader-rank">${index + 1}.</div>
          <div class="fcc-leader-meta">
            <div class="fcc-leader-name">${escapeFccLeaderHtml(leader.name || '--')}</div>
            <div class="fcc-leader-team">${escapeFccLeaderHtml(leader.team || '--')}</div>
          </div>
          <div class="fcc-leader-value">${escapeFccLeaderHtml(formatLeaderValue(category, leader.value))}</div>
        `;
        list.appendChild(row);
      });
    }
    card.appendChild(list);
    grid.appendChild(card);
  });
}

async function ensureFccTeamStatsSummary() {
  if (fccTeamStatsSummaryCache || !franchiseId) return fccTeamStatsSummaryCache;
  fccTeamStatsSummaryCache = await fetchJSON(
    `${API_CONFIG.buildUrl('/franchise/team-stats')}?franchise_id=${encodeURIComponent(franchiseId)}&scope=conference`
  );
  return fccTeamStatsSummaryCache;
}

async function ensureFccPlaybooksSummary() {
  if (fccPlaybooksSummaryCache || !franchiseId || !userTeamId) return fccPlaybooksSummaryCache;
  const params = new URLSearchParams();
  params.set('mode', 'franchise');
  params.set('team_id', userTeamId);
  params.set('franchise_id', franchiseId);
  fccPlaybooksSummaryCache = await fetchJSON(`${API_CONFIG.buildUrl('/api/playbooks')}?${params.toString()}`);
  return fccPlaybooksSummaryCache;
}

async function renderFccTeamStatsSummary() {
  const tbody = document.getElementById('fcc-team-stats-summary-body');
  if (!tbody) return;
  if (!fccTeamStatsSummaryCache) {
    tbody.innerHTML = '<tr><td colspan="27">Loading team stats...</td></tr>';
  }
  const payload = await ensureFccTeamStatsSummary();
  const teams = payload?.teams || [];
  if (!teams.length) {
    tbody.innerHTML = '<tr><td colspan="27">Failed to load team stats.</td></tr>';
    return;
  }
  const rows = teams.map((team) => {
    const stats = team.stats || {};
    const rank = Number(team?.natl_rank);
    return `
      <tr>
        <td class="col-group-start">${escapeHomeHtml(team.team || '')}</td>
        <td>${Number.isFinite(rank) && rank > 0 ? rank : '--'}</td>
        <td class="col-w">${escapeHomeHtml(stats.W ?? 0)}</td>
        <td class="col-l">${escapeHomeHtml(stats.L ?? 0)}</td>
        <td>${escapeHomeHtml(stats.PF ?? 0)}</td>
        <td>${escapeHomeHtml(stats.PA ?? 0)}</td>
        <td class="col-group-start">${escapeHomeHtml(stats.FGM ?? 0)}</td>
        <td>${escapeHomeHtml(stats.FGA ?? 0)}</td>
        <td>${escapeHomeHtml(formatTeamStatsPercent(stats.FGM, stats.FGA))}</td>
        <td class="col-group-start">${escapeHomeHtml(stats['3PTM'] ?? 0)}</td>
        <td>${escapeHomeHtml(stats['3PTA'] ?? 0)}</td>
        <td>${escapeHomeHtml(formatTeamStatsPercent(stats['3PTM'], stats['3PTA']))}</td>
        <td class="col-group-start">${escapeHomeHtml(stats.FTM ?? 0)}</td>
        <td>${escapeHomeHtml(stats.FTA ?? 0)}</td>
        <td>${escapeHomeHtml(formatTeamStatsPercent(stats.FTM, stats.FTA))}</td>
        <td class="col-group-start">${escapeHomeHtml(stats.DREB ?? 0)}</td>
        <td>${escapeHomeHtml(stats.OREB ?? 0)}</td>
        <td>${escapeHomeHtml(stats.TREB ?? 0)}</td>
        <td class="col-group-start">${escapeHomeHtml(stats.AST ?? 0)}</td>
        <td>${escapeHomeHtml(stats.F ?? 0)}</td>
        <td>${escapeHomeHtml(stats.TO ?? 0)}</td>
        <td>${escapeHomeHtml(stats.SCR_A ?? 0)}</td>
        <td>${escapeHomeHtml(formatTeamStatsPercent(stats.SCR_S, stats.SCR_A))}</td>
        <td class="col-group-start">${escapeHomeHtml(stats.STL ?? 0)}</td>
        <td>${escapeHomeHtml(stats.BLK ?? 0)}</td>
        <td>${escapeHomeHtml(stats.DEF_A ?? 0)}</td>
        <td>${escapeHomeHtml(formatTeamStatsPercent(stats.DEF_S, stats.DEF_A))}</td>
      </tr>
    `;
  }).join('');
  tbody.innerHTML = rows;
}

const FCC_PLAYBOOK_SECTION_ORDER = [
  { key: 'motion', label: 'Motion Plays' },
  { key: 'set_plays', label: 'Set Plays' },
  { key: 'man_defense', label: 'Man Defense' },
  { key: 'zone_defense', label: 'Zone Defense' },
  { key: 'fast_breaks', label: 'Fast Breaks' },
  { key: 'hc_traps', label: 'HC Traps' }
];

function escapePlaybookHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildFccPlaybooksItems(data, key) {
  const percentages = data?.simple_playbook_percentages || data?.playbook_percentages || {};
  let items = [];

  if (key === 'motion') {
    items = (data?.motion || []).map((play) => ({
      id: String(play?.play_id || ''),
      name: play?.name || 'Unknown',
      percentage: Number(percentages.motion?.[play?.play_id] || 0),
      effectiveness: Number(play?.effectiveness || 0),
      top_scorer: play?.top_scorer || '',
      motion_focus: play?.motion_focus || ''
    }));
  } else if (key === 'set_plays') {
    items = (data?.set_plays || []).map((play) => ({
      id: String(play?.play_id || ''),
      name: play?.name || 'Unknown',
      percentage: Number(percentages.set_plays?.[play?.play_id] || 0),
      effectiveness: Number(play?.effectiveness || 0),
      top_scorer: play?.top_scorer || '',
      target_shooter: play?.target_shooter || ''
    }));
  } else if (key === 'man_defense') {
    items = (data?.man_defense_rows || [])
      .filter((row) => row?.is_active !== false)
      .map((row) => ({
        id: String(row?.id || ''),
        name: row?.name || 'Unknown',
        percentage: Number(percentages.man_defense?.[row?.id] || 0),
        effectiveness: Number(row?.effectiveness || 0),
        top_scorer: row?.top_scorer || ''
      }));
  } else if (key === 'zone_defense') {
    items = (data?.zone_defense_rows || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: Number(percentages.zone_defense?.[row?.id] || 0),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || ''
    }));
  } else if (key === 'fast_breaks') {
    items = (data?.fast_breaks || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: Number(percentages.fast_breaks?.[row?.id] || 0),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || ''
    }));
  } else if (key === 'hc_traps') {
    items = (data?.hc_traps || []).map((row) => ({
      id: String(row?.id || ''),
      name: row?.name || 'Unknown',
      percentage: Number(percentages.hc_traps?.[row?.id] || 0),
      effectiveness: Number(row?.effectiveness || 0),
      top_scorer: row?.top_scorer || ''
    }));
  }

  return items
    .filter((item) => Number(item.percentage || 0) > 0)
    .sort((a, b) => Number(b.percentage || 0) - Number(a.percentage || 0) || String(a.name).localeCompare(String(b.name)));
}

function getFccPlaybookEffClass(value) {
  const numeric = Number(value || 0);
  if (numeric >= 70) return 'is-good';
  if (numeric >= 40) return 'is-mid';
  return 'is-low';
}

function getFccMotionFocusLabel(value) {
  if (value === 'inside') return 'Inside';
  if (value === 'attack') return 'Attack';
  if (value === 'outside') return 'Outside';
  return 'Balanced';
}

function buildFccPlaycallCenterMaps(data) {
  const offense = new Map();
  const defense = new Map();

  (data?.motion || []).forEach((play) => {
    offense.set(String(play?.play_id || ''), {
      name: play?.name || 'Unknown',
      detail: getFccMotionFocusLabel(play?.motion_focus || '')
    });
  });
  (data?.set_plays || []).forEach((play) => {
    offense.set(String(play?.play_id || ''), {
      name: play?.name || 'Unknown',
      detail: play?.target_shooter || ''
    });
  });
  (data?.man_defense_rows || []).filter((row) => row?.is_active !== false).forEach((row) => {
    defense.set(String(row?.id || ''), {
      name: row?.name || 'Unknown',
      detail: ''
    });
  });
  (data?.zone_defense_rows || []).forEach((row) => {
    defense.set(String(row?.id || ''), {
      name: row?.name || 'Unknown',
      detail: ''
    });
  });

  return { offense, defense };
}

function buildFccPlaycallCenterListMarkup(label, entries, lookup) {
  const rows = Array.from({ length: 8 }, (_, index) => {
    const id = String(entries?.[index] || '');
    const item = id ? lookup.get(id) : null;
    return `
      <article class="fcc-playcall-slot-card">
        <div class="fcc-playcall-slot-line">
          <span class="fcc-playcall-slot-number">${index + 1}.</span>
          ${item
            ? `<span class="fcc-playcall-slot-name">${escapePlaybookHtml(item.name)}</span>${item.detail ? ` <span class="fcc-playcall-slot-detail">&mdash; ${escapePlaybookHtml(item.detail)}</span>` : ''}`
            : '<span class="fcc-playcall-slot-empty">Empty</span>'}
        </div>
      </article>
    `;
  }).join('');

  return `
    <div class="fcc-playcall-column">
      <div class="fcc-playcall-column-head">${escapePlaybookHtml(label)}</div>
      <div class="fcc-playcall-slots">${rows}</div>
    </div>
  `;
}

function buildFccPlaycallCenterSectionMarkup(data) {
  const editLinkMarkup = `
    <button id="fcc-edit-playcall-center-link" class="fcc-playbooks-inline-link" type="button">Edit in Playbooks</button>
  `;
  const pcOrder = data?.pc_order || { offense: [], defense: [] };
  const lookup = buildFccPlaycallCenterMaps(data);

  return `
    <section class="fcc-playbooks-section fcc-playcall-section">
      <div class="fcc-playbooks-section-head-wrap">
        <div class="fcc-playbooks-section-head">Playcall Center</div>
        ${editLinkMarkup}
      </div>
      <div class="fcc-playbooks-section-body">
        <div class="fcc-playcall-grid">
          ${buildFccPlaycallCenterListMarkup('Offense', pcOrder.offense || [], lookup.offense)}
          ${buildFccPlaycallCenterListMarkup('Defense', pcOrder.defense || [], lookup.defense)}
        </div>
      </div>
    </section>
  `;
}

function buildFccPlaybooksSectionMarkup(data, section) {
  const editButtonMarkup = section.key === 'motion'
    ? '<button id="fcc-edit-playbooks-btn" class="fcc-game-plan-edit-btn" type="button">Edit Playbooks</button>'
    : '';

  const items = buildFccPlaybooksItems(data, section.key);
  const bodyMarkup = items.length
    ? `<div class="fcc-playbooks-items">${items.map((item) => `
        <article class="fcc-playbooks-item-card">
          <div class="fcc-playbooks-item-top">
            <div class="fcc-playbooks-item-name">${escapePlaybookHtml(
              section.key === 'set_plays' && item.target_shooter
                ? `${item.name} (${item.target_shooter})`
                : item.name
            )}</div>
            <div class="fcc-playbooks-item-percent">${escapePlaybookHtml(`${Number(item.percentage || 0)}%`)}</div>
          </div>
          <div class="fcc-playbooks-item-meta">
            <div class="fcc-playbooks-item-eff ${getFccPlaybookEffClass(item.effectiveness)}">${escapePlaybookHtml(`CMD: ${Number(item.effectiveness || 0)}`)}</div>
            ${item.top_scorer && item.top_scorer !== 'N/A' ? `<div class="fcc-playbooks-item-top-scorer">${escapePlaybookHtml(`TOP: ${item.top_scorer}`)}</div>` : ''}
          </div>
        </article>
      `).join('')}</div>`
    : '<div class="fcc-playbooks-empty">No plays assigned.</div>';

  return `
    <section class="fcc-playbooks-section">
      <div class="fcc-playbooks-section-head-wrap">
        <div class="fcc-playbooks-section-head">${escapePlaybookHtml(section.label)}</div>
        ${editButtonMarkup}
      </div>
      <div class="fcc-playbooks-section-body">
        ${bodyMarkup}
      </div>
    </section>
  `;
}

async function renderFccPlaybooksSummary() {
  const host = document.getElementById('fcc-playbooks-sections');
  if (!host) return;

  host.innerHTML = '<div class="fcc-playbooks-empty">Loading playbook settings...</div>';
  const data = await ensureFccPlaybooksSummary();
  if (!data) {
    host.innerHTML = '<div class="fcc-playbooks-empty">Failed to load playbook settings.</div>';
    return;
  }

  host.innerHTML = `${FCC_PLAYBOOK_SECTION_ORDER.map((section) => buildFccPlaybooksSectionMarkup(data, section)).join('')}${buildFccPlaycallCenterSectionMarkup(data)}`;

  // TODO: confirm position_shot_weights is present in FCC playbook API response
  const shotWeights = data?.position_shot_weights || null;
  const playbooksCardBody = host.closest('.fcc-playbooks-card-body');
  if (playbooksCardBody) {
    playbooksCardBody.querySelectorAll(':scope > .fcc-psw-strip').forEach((el) => el.remove());
  }
  if (shotWeights && typeof renderShotWeights === 'function') {
    if (playbooksCardBody) {
      const pswStrip = document.createElement('div');
      pswStrip.className = 'fcc-psw-strip';
      pswStrip.style.marginTop = '18px';
      renderShotWeights(pswStrip, shotWeights, true);
      playbooksCardBody.appendChild(pswStrip);
    }
  }

  const editBtn = document.getElementById('fcc-edit-playbooks-btn');
  if (editBtn && !editBtn.dataset.bound) {
    editBtn.dataset.bound = '1';
    editBtn.addEventListener('click', () => {
      if (!franchiseId || !userTeamId) return;
      const params = new URLSearchParams();
      params.set('mode', 'franchise');
      params.set('team_id', userTeamId);
      params.set('franchise_id', franchiseId);
      params.set('return_url', getCurrentRelativeUrl());
      window.location.href = `/playbooks.html?${params.toString()}`;
    });
  }

  const playcallEditLink = document.getElementById('fcc-edit-playcall-center-link');
  if (playcallEditLink && !playcallEditLink.dataset.bound) {
    playcallEditLink.dataset.bound = '1';
    playcallEditLink.addEventListener('click', () => {
      if (!franchiseId || !userTeamId) return;
      const params = new URLSearchParams();
      params.set('mode', 'franchise');
      params.set('team_id', userTeamId);
      params.set('franchise_id', franchiseId);
      params.set('return_url', getCurrentRelativeUrl());
      window.location.href = `/playbooks.html?${params.toString()}`;
    });
  }
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
  const fullListLink = document.getElementById('fcc-recruits-full-link');
  if (!tbody || !table || typeof RecruitingCommon === 'undefined') return;

  renderFccRecruitsInviteBanner();

  const useSignedRecruits = Number(document.body.dataset.fccWeek || 1) >= 36;
  if (heading) heading.textContent = useSignedRecruits ? 'Signed Recruits' : 'Recruits Leaning Your Way';
  if (fullListLink) {
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('return_url', getCurrentRelativeUrl());
    fullListLink.href = `/recruiting.html?${params.toString()}`;
  }
  const psLink = document.getElementById('fcc-ps-season-link');
  if (psLink) {
    const psParams = new URLSearchParams();
    psParams.set('franchise_id', franchiseId);
    psParams.set('team_id', userTeamId);
    psLink.href = `/practice-squad-standings.html?${psParams.toString()}`;
  }
  if (lastCol) {
    lastCol.textContent = 'Current Lean';
    lastCol.dataset.sortKey = 'lean';
    lastCol.style.display = useSignedRecruits ? 'none' : '';
  }

  if (useSignedRecruits) {
    if (!signedRecruitsDataCache.length) {
      tbody.innerHTML = '<tr><td colspan="20">No recruits or walk-ons joined your team.</td></tr>';
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
        '<td>' + (recruit.yearDisplay || '--') + '</td>',
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
        '<td class="' + (typeof window.getRecruitRtBucketClassForYear === 'function' ? window.getRecruitRtBucketClassForYear(recruit.rt, recruit.year) : '') + '">' + (recruit.rt != null ? recruit.rt : '--') + '</td>'
      ].join('');
      tbody.appendChild(tr);
    });
    return;
  }

  if (!leanRecruitsDataCache.length) {
    tbody.innerHTML = '<tr><td colspan="21">No recruits currently have your team on their lean list.</td></tr>';
    return;
  }
  RecruitingCommon.renderRecruitTableRows(
    tbody,
    partitionRecruitsWithNewLeans(
      leanRecruitsDataCache,
      RecruitingCommon.sortRecruits.bind(RecruitingCommon),
      recruitSortState
    ),
    { newLeanIds: getNewLeanRecruitIdSet() }
  );
}

function initFccRecruits(topData) {
  if (typeof RecruitingCommon === 'undefined') return;
  document.body.dataset.fccWeek = String(Number(topData?.week || 1));
  currentWeekInviteRecruitCache = topData?.current_week_invite_recruit || null;
  newLeanRecruitIdsCache = Array.isArray(topData?.new_lean_recruit_ids) ? topData.new_lean_recruit_ids : [];
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
      year: player.year || 'JH',
      yearDisplay: RecruitingCommon.formatYearAbbrev(player.year || 'JH'),
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
  
  // Initialize tooltips for table cells (and headers)
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody.closest('table') || tbody, ['td', 'th']);
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

// Practice Squad section (the 3 cut players). After Week 35 Recruiting Day
// the team's recruits join the list under the same "Practice Squad" header.
// Renders an attributes table and a stats table (fed by ps_season_stats), mirroring
// the team roster pages.
function renderPracticeSquad(data) {
  const section = document.getElementById('training-squad-section');
  const tbody = document.getElementById('training-squad-body');
  // The stats table lives in a separate section at the bottom of the Player Stats tab.
  const statsBody = document.getElementById('ps-stats-body');
  const statsSection = document.getElementById('ps-stats-section');
  const titleEl = document.getElementById('ps-section-title');
  const statsTitleEl = document.getElementById('ps-stats-title');
  if (!section || !tbody) return;
  // Neither field provided on this render (e.g. cache restore) => leave as-is.
  if (!Array.isArray(data.training_squad) && !Array.isArray(data.practice_squad_recruits)) return;

  const psPlayers = Array.isArray(data.training_squad) ? data.training_squad : [];
  const recruits = Array.isArray(data.practice_squad_recruits) ? data.practice_squad_recruits : [];
  const combined = psPlayers.concat(recruits);

  if (!combined.length) {
    section.style.display = 'none';
    tbody.innerHTML = '';
    if (statsBody) statsBody.innerHTML = '';
    if (statsSection) statsSection.style.display = 'none';
    return;
  }

  const psTitle = 'Practice Squad';
  if (titleEl) titleEl.textContent = psTitle;
  if (statsTitleEl) statsTitleEl.textContent = psTitle;

  // Attributes table
  tbody.innerHTML = '';
  combined.forEach(p => {
    try {
      const best = getBestPosition(p.position_ratings || {});
      const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
      const attrs = p.attributes || {};
      const tr = document.createElement('tr');

      const nameTd = document.createElement('td');
      if (p.is_recruit) {
        // Recruits have no player-detail page until the season transition.
        nameTd.textContent = fullName;
      } else {
        const nameLink = document.createElement('a');
        nameLink.href = buildPlayerDetailUrl(p._id);
        nameLink.textContent = typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, fullName) : fullName;
        nameLink.style.color = 'inherit';
        nameLink.style.textDecoration = 'none';
        nameTd.appendChild(nameLink);
      }
      tr.appendChild(nameTd);

      const addCell = (content, extraClass) => {
        const td = document.createElement('td');
        td.textContent = content;
        if (extraClass) td.className = extraClass;
        tr.appendChild(td);
      };
      addCell(best.pos || '--');
      addCell(yearMap[(p.year || '').toLowerCase()] || p.year || '--');
      addCell(formatHeight(p.height));
      addCell(p.weight ?? '--');
      ATTR_HEADERS.forEach(h => {
        const rawVal = attrs[`anchor_${h}`] ?? attrs[h];
        const displayVal = h === 'NG'
          ? (rawVal != null ? rawVal.toFixed(2) : '--')
          : (rawVal != null ? Math.floor(rawVal / 10) : '--');
        addCell(displayVal);
      });
      const rt = best.rating;
      addCell(rt ?? '-', typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(rt) : '');
      tbody.appendChild(tr);
    } catch (e) {
      console.error('Error rendering practice squad player:', p, e);
    }
  });

  // Stats table (ps_season_stats — regional Practice Squad games)
  if (statsBody) {
    statsBody.innerHTML = '';
    combined.forEach(p => {
      try {
        const stats = p.ps_stats || {};
        const fullName = `${p.first_name || ''} ${p.last_name || ''}`.trim() || p.name || '';
        const tr = document.createElement('tr');

        const nameTd = document.createElement('td');
        if (p.is_recruit) {
          nameTd.textContent = fullName;
        } else {
          const nameLink = document.createElement('a');
          nameLink.href = buildPlayerDetailUrl(p._id);
          nameLink.textContent = typeof formatNameWithJersey === 'function' ? formatNameWithJersey(p.jersey, fullName) : fullName;
          nameLink.style.color = 'inherit';
          nameLink.style.textDecoration = 'none';
          nameTd.appendChild(nameLink);
        }
        tr.appendChild(nameTd);

        const addCell = (content) => {
          const td = document.createElement('td');
          td.textContent = content;
          tr.appendChild(td);
        };

        const tpm = stats['3PTM'] || 0;
        const tpa = stats['3PTA'] || 0;
        const fgm = stats.FGM || 0;
        const fga = stats.FGA || 0;
        const ftm = stats.FTM || 0;
        const fta = stats.FTA || 0;
        const defa = stats.DEF_A || 0;
        const defs = stats.DEF_S || 0;
        const scra = stats.SCR_A || 0;
        const scrs = stats.SCR_S || 0;

        addCell(stats.PTS || 0);
        addCell(fgm);
        addCell(fga);
        addCell(fga > 0 ? ((fgm / fga) * 100).toFixed(1) : '0.0');
        addCell(tpm);
        addCell(tpa);
        addCell(tpa > 0 ? ((tpm / tpa) * 100).toFixed(1) : '0.0');
        addCell(ftm);
        addCell(fta);
        addCell(fta > 0 ? ((ftm / fta) * 100).toFixed(1) : '0.0');
        addCell(stats.DREB || 0);
        addCell(stats.OREB || 0);
        addCell(stats.TREB || stats.REB || 0);
        addCell(stats.AST || 0);
        addCell(stats.STL || 0);
        addCell(stats.BLK || 0);
        addCell(stats.F || 0);
        addCell(stats.TO || 0);
        addCell(defa);
        addCell(defa > 0 ? ((defs / defa) * 100).toFixed(1) : '0.0');
        addCell(scra);
        addCell(scra > 0 ? ((scrs / scra) * 100).toFixed(1) : '0.0');
        statsBody.appendChild(tr);
      } catch (e) {
        console.error('Error rendering practice squad stats row:', p, e);
      }
    });
  }

  section.style.display = '';
  if (statsSection) statsSection.style.display = '';
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody.closest('table') || tbody, ['td', 'th']);
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
        walk_on: !!p.walk_on,
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
    if (p.walk_on) {
      const wo = document.createElement('span');
      wo.textContent = ' (walk on)';
      wo.style.color = '#8a93a6';
      wo.style.fontWeight = '700';
      nameTd.appendChild(wo);
    }
    tr.appendChild(nameTd);

    // Add other columns directly as DOM elements
    const addCell = (content, extraClass) => {
      const td = document.createElement('td');
      td.textContent = content;
      if (extraClass) td.className = extraClass;
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
    // RT colored per canonical Attribute Bar Scale (see /css/rt-buckets.css).
    addCell(
      p.rt ?? '-',
      typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(p.rt) : ''
    );

    tbody.appendChild(tr);
  });

  // Initialize tooltips. Scope to the parent table so the SC/SH/ID/… column
  // headers also get tooltips, not only the cells under them.
  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody.closest('table') || tbody, ['td', 'th']);
  }

  // Practice Squad (+ Recruits after Week 35) rendered below the active roster.
  renderPracticeSquad(data);

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
        '<td><a href="' + buildPlayerDetailUrl(entry.raw._id) + '" style="color:inherit;text-decoration:none;">' + getDisplayPlayerNameForStats(entry.raw) + '</a></td>' +
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
    if (p.walk_on) {
      const wo = document.createElement('span');
      wo.textContent = ' (walk on)';
      wo.style.color = '#8a93a6';
      wo.style.fontWeight = '700';
      nameTd.appendChild(wo);
    }
    tr.appendChild(nameTd);

    const addCell = (content, extraClass) => {
      const td = document.createElement('td');
      td.textContent = content;
      if (extraClass) td.className = extraClass;
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
    // RT colored per canonical Attribute Bar Scale (see /css/rt-buckets.css).
    addCell(
      p.rt ?? '-',
      typeof window.getRtBucketClass === 'function' ? window.getRtBucketClass(p.rt) : ''
    );

    tbody.appendChild(tr);
  });

  if (typeof initAttributeTooltips !== 'undefined') {
    initAttributeTooltips(tbody.closest('table') || tbody, ['td', 'th']);
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
    persistFranchiseDisplayColorContext(commandCenterTopDataCache);
    emitDisplayContextUpdate();
    adoptAuthoritativeFccTeamId(commandCenterTopDataCache);
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
    // Keep the full-page overlay visible until authoritative command-center
    // data returns. Cached rendering is only a behind-the-overlay warm paint;
    // showing it directly causes a stale-data flash on FCC entry.
  }
  const topDataStartTime = performance.now();
  let topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
  const topDataEndTime = performance.now();
  console.log(`⏱️ [PERF] /franchise/command-center/data: ${(topDataEndTime - topDataStartTime).toFixed(2)}ms`);
  if (!topData) return; // Access denied or error - redirect already triggered for 401/403; finally block will hide page-load-overlay
  topData = await recoverCpuSimsBeforeFccRender(topData);
  if (!topData) return;
  const previousWeek = Number(commandCenterTopDataCache?.week || 0);
  const nextWeek = Number(topData?.week || 0);
  if (previousWeek && nextWeek && previousWeek !== nextWeek) {
    console.warn('[FCC CACHE] Invalidating week-sensitive Home caches after week change', { previousWeek, nextWeek });
    invalidateHomeWeekSensitiveCaches();
  }
  commandCenterTopDataCache = topData;
  persistFranchiseDisplayColorContext(topData);
  // Command-center data is the source of truth; URL/localStorage can be stale after team changes.
  adoptAuthoritativeFccTeamId(topData);
  persistFccSessionCache();
  emitDisplayContextUpdate();
  
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
  const playbooksTab = document.getElementById('playbooks-tab');
  if (playbooksTab && playbooksTab.classList.contains('active')) {
    void renderFccPlaybooksSummary();
  }
  renderFccInbox(topData);
  // Championship Announce moments take precedence over the legacy
  // championship_summary modal: when the new system has anything queued, render
  // those overlays instead of the older one for the same game.
  const pendingMoments = Array.isArray(topData?.pending_championship_moments)
    ? topData.pending_championship_moments
    : [];
  let championshipMomentsDone = Promise.resolve();
  if (pendingMoments.length && typeof window.ChampionshipMoments !== 'undefined') {
    championshipMomentsDone = window.ChampionshipMoments.processPendingMoments(
      franchiseId,
      pendingMoments,
      {
        boxScoreUrlBuilder: (moment) => buildFccBoxScoreUrlForMoment(moment),
      }
    );
  } else {
    maybeShowChampionshipCompleteModal(topData);
  }
  championshipMomentsDone.then(() => {
    if (window.RegionByeModal) window.RegionByeModal.maybeShow(topData);
    if (window.BigNewsModals) {
      window.BigNewsModals.maybeShow(topData, {
        userTeamId,
        teamIdToNameMap: topData?.team_name_map || {},
        teamIdMetaMap,
      });
    }
  });
  if (topData?.cut_required && Number(topData.cut_count || 0) > 0) {
    const showTs = () => showCutPlayersRequiredModal(Number(topData.cut_count || 0));
    // Sequence behind tutorial alerts: on the season-1 week-1 return the Team
    // Attributes tutorial must come first. whenReturnAlertsSettled fires once that
    // alert is dismissed (or immediately if no tutorial alert is showing). Fallback
    // to showing directly if the tutorial-alert module isn't present.
    const ta = window.GOBTutorialAlerts;
    if (ta && typeof ta.whenReturnAlertsSettled === 'function') {
      let shown = false;
      const fire = () => { if (shown) return; shown = true; showTs(); };
      ta.whenReturnAlertsSettled(fire);
      setTimeout(fire, 8000); // safety net if the settle signal never arrives
    } else {
      showTs();
    }
  }

  // Lowest-priority coaching-archetype "you have evolved" modal. Runs only after
  // the rest of the modal sequence has settled (championship moments resolved +
  // tutorial-return alerts settled + a short delay so any synchronous reveal /
  // feedback / region-bye / big-news overlay has rendered). On a clean visit it
  // shows; if anything else claimed the visit it's skipped permanently. The
  // pending flag is consumed either way (inside ArchetypeEvolutionModal.run).
  if (window.ArchetypeEvolutionModal) {
    const runEvo = () => setTimeout(() => {
      window.ArchetypeEvolutionModal.run(fccHasCompetingModal(topData));
    }, 1200);
    const settleThenEvo = () => {
      const taEvo = window.GOBTutorialAlerts;
      if (taEvo && typeof taEvo.whenReturnAlertsSettled === 'function') {
        taEvo.whenReturnAlertsSettled(runEvo);
      } else {
        runEvo();
      }
    };
    championshipMomentsDone.then(settleThenEvo, settleThenEvo);
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
      renderTeam(result);
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
    // Start the FCC background music loop. Random pick (50/50) between the two
    // scouting tracks per visit. Page unload (Green Action Button → nav) tears
    // down the audio naturally — no explicit stop hooks needed.
    try {
      const { playFccTrack } = await import('/js/musicController.js');
      playFccTrack();
    } catch (musicErr) {
      console.warn('[fcc] background music init failed', musicErr);
    }
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

/**
 * SS&S: Same box-score query hints as post-game completion (gameCompletionPopup) so
 * `/api/game/{id}` plus URL stay aligned; game doc `user_team_side` remains primary when present.
 */
function appendFranchiseBoxScoreUserHints(params, homeTeamName, awayTeamName) {
  if (!params || typeof params.set !== 'function') return;
  const tid =
    (userTeamId && String(userTeamId).trim()) ||
    (typeof localStorage !== 'undefined' && (localStorage.getItem('franchise_user_team_id') || '').trim()) ||
    '';
  const teamNameRaw =
    (typeof localStorage !== 'undefined' && (localStorage.getItem('franchise_user_team') || '').trim()) ||
    (userTeamName || '').trim();
  if (tid) params.set('team_id', tid);
  const hn = (homeTeamName || '').trim();
  const an = (awayTeamName || '').trim();
  if (teamNameRaw && hn && teamNameRaw.toLowerCase() === hn.toLowerCase()) {
    params.set('my_team', 'home');
  } else if (teamNameRaw && an && teamNameRaw.toLowerCase() === an.toLowerCase()) {
    params.set('my_team', 'away');
  }
  if (teamNameRaw) params.set('banner_team', teamNameRaw);
}

function getChampionshipSeenKey(franchiseIdValue, gameId) {
  if (!franchiseIdValue || !gameId) return null;
  return `fcc_championship_seen_${franchiseIdValue}_${gameId}`;
}

// True if any higher-priority FCC modal/prompt claims this visit, so the
// lowest-priority archetype-evolution modal must yield. Combines a DOM check
// (same overlay selectors RegionByeModal.blockerVisible uses, for modals already
// rendered) with a data check from topData/me (for modals eligible this visit
// that may not have rendered yet — avoids a render-timing race). Conservative:
// when in doubt it returns true, so the evolution modal over-yields rather than
// stacking on another modal.
function fccHasCompetingModal(topData) {
  if (typeof document !== 'undefined' && document.querySelector(
      '.cm-overlay.is-visible,.arch-reveal-overlay.is-visible,.afm-overlay.is-visible,'
      + '.gob-talert-overlay,.sammy-modal-backdrop.open,.fcc-modal-overlay,.bn-overlay.show')) {
    return true;
  }
  if (Array.isArray(topData?.pending_championship_moments) && topData.pending_championship_moments.length) return true;
  const summary = topData?.championship_summary;
  if (summary && summary.game_id) {
    const seenKey = getChampionshipSeenKey(franchiseId, summary.game_id);
    const seen = seenKey && typeof localStorage !== 'undefined' && localStorage.getItem(seenKey) === '1';
    if (!seen) return true;
  }
  if (topData?.region_bye_modal_eligible) return true;
  if (topData?.bracket_reveal_modal?.eligible || topData?.bracket_update_modal?.eligible || topData?.recruiting_results_modal?.eligible) return true;
  if (topData?.cut_required && Number(topData.cut_count || 0) > 0) return true;
  const me = window.__gobAuthMeData;
  if (me) {
    if (me.archetype_reveal_seen === false) return true; // first-archetype reveal still pending
    if (!me.alpha_feedback_submitted && me.archetype_reveal_seen !== false) {
      const games = parseInt(me.alpha_feedback_games, 10) || 0;
      const level = parseInt(me.alpha_feedback_prompt_level, 10) || 0;
      if ((games >= 8 && level < 8) || (games >= 4 && level < 4)) return true;
    }
  }
  return false;
}

function buildFccBoxScoreUrlForMoment(moment) {
  if (!moment || !moment.game_id || !franchiseId) return '';
  const params = new URLSearchParams();
  params.set('mode', 'franchise');
  params.set('franchise_id', franchiseId);
  params.set('game_id', moment.game_id);
  if (moment.winner_team_name) params.set('home', moment.winner_team_name);
  if (moment.loser_team_name) params.set('away', moment.loser_team_name);
  appendFranchiseBoxScoreUserHints(params, moment.winner_team_name, moment.loser_team_name);
  return `/box-score.html?${params.toString()}`;
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
    appendFranchiseBoxScoreUserHints(params, homeName, awayName);
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
  overlay.className = 'gob-modal-overlay fcc-new-season-modal is-visible';
  overlay.setAttribute('aria-hidden', 'false');
  overlay.innerHTML = `
    <div class="gob-modal-backdrop"></div>
    <div class="gob-modal-box" role="dialog" aria-modal="true" aria-labelledby="fcc-new-season-title" aria-describedby="fcc-new-season-copy">
      <div class="gob-modal-accent is-green"></div>
      <div class="gob-modal-body">
        <h3 id="fcc-new-season-title" class="gob-modal-title">Go To Next Season?</h3>
        <p id="fcc-new-season-copy" class="gob-modal-subtitle">This will create the next season for this franchise instance. Your current season cannot be reopened after you proceed.</p>
      </div>
      <div class="gob-modal-actions">
        <button type="button" class="gob-modal-btn-secondary" id="fcc-new-season-cancel">Cancel</button>
        <button type="button" class="gob-modal-btn-primary is-green" id="fcc-new-season-proceed">Start Next Season</button>
      </div>
    </div>
  `;
  const close = () => {
    document.removeEventListener('keydown', onKeydown);
    overlay.remove();
  };
  const onKeydown = (event) => {
    if (event.key === 'Escape') close();
  };
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay || event.target.classList.contains('gob-modal-backdrop')) close();
  });
  document.addEventListener('keydown', onKeydown);
  overlay.closeGobModal = close;
  document.body.appendChild(overlay);
  overlay.querySelector('#fcc-new-season-cancel')?.focus();
  return overlay;
}

function showCutPlayersRequiredModal(cutCount) {
  const overlay = document.createElement('div');
  overlay.className = 'gob-modal-overlay fcc-cut-required-modal is-visible';
  overlay.setAttribute('aria-hidden', 'false');
  overlay.innerHTML = `
    <div class="gob-modal-backdrop"></div>
    <div class="gob-modal-box" role="dialog" aria-modal="true" aria-labelledby="fcc-cut-required-title" aria-describedby="fcc-cut-required-copy">
      <div class="gob-modal-accent"></div>
      <div class="gob-modal-body">
        <h3 id="fcc-cut-required-title" class="gob-modal-title">Trim Your Roster to Size</h3>
        <p id="fcc-cut-required-copy" class="gob-modal-subtitle">Assign ${cutCount} player${cutCount === 1 ? '' : 's'} to your practice squad. They'll sit out this season, but they'll keep developing and return eligible next year.</p>
      </div>
      <div class="gob-modal-actions">
        <button type="button" class="gob-modal-btn-dismiss" id="fcc-cut-required-close">Close</button>
      </div>
    </div>
  `;
  const close = () => {
    document.removeEventListener('keydown', onKeydown);
    overlay.remove();
  };
  const onKeydown = (event) => {
    if (event.key === 'Escape') close();
  };
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay || event.target.classList.contains('gob-modal-backdrop')) close();
  });
  document.addEventListener('keydown', onKeydown);
  overlay.querySelector('#fcc-cut-required-close')?.addEventListener('click', () => {
    close();
  });
  document.body.appendChild(overlay);
  overlay.querySelector('#fcc-cut-required-close')?.focus();
}

const EOS_PLAY_CTA_BY_WEEK = Object.freeze({
  27: 'Play Conference Tourney First Round',
  28: 'Play Conference Tourney Semifinals',
  29: 'Play Conference Tourney Championship',
  30: 'Play Region Tourney First Round',
  31: 'Play Region Tourney Championship',
  32: 'Play National Tourney First Round',
  33: 'Play National Tourney Semifinals',
  34: 'Play National Championship!',
});

const EOS_SIM_CTA_BY_WEEK = Object.freeze({
  28: 'Sim Conference Tourney Semifinals',
  29: 'Sim Conference Tourney Championship',
  30: 'Sim Region Tourney First Round',
  31: 'Sim Region Tourney Championship',
  32: 'Sim National Tourney First Round',
  33: 'Sim National Tourney Semifinals',
  34: 'Sim National Championship',
});

function updatePlayButton(data) {
  const playNowBtn = document.getElementById('play-now');
  if (!data) return;
  
  const eosTournamentActive = data.eos_tournament_active || false;
  const eosTournament = data.eos_tournament;
  const week = Number(data.week || 1);
  const trainingDisabledForEos = !!data.training_disabled_for_eos;
  const trainingDisabledForPostseason = !!data.training_disabled_for_postseason || (week >= 27 && week <= 34);
  const userEliminated = data.user_eliminated != null ? !!data.user_eliminated : null;
  const offerSimRest = data.offer_sim_rest != null ? !!data.offer_sim_rest : null;
  const regionQualified = !!data.region_qualified;
  const hasEosGameThisWeek = !!data.has_eos_game_this_week;
  
  if (fccCpuSimNeedsRecovery(data)) {
    playNowBtn.textContent = 'Finish Computer Games';
    playNowBtn.dataset.mode = 'finish-cpu-sims';
    return;
  }

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
    playNowBtn.textContent = 'Assign Practice Squad';
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
    playNowBtn.textContent = EOS_SIM_CTA_BY_WEEK[week] || 'Sim Next Round';
    playNowBtn.dataset.mode = 'sim-rest-tournament';
  } else if (
    trainingDisabledForPostseason
    && !eliminated
    && regionQualified
    && week >= 27
    && week <= 29
    && !hasEosGameThisWeek
  ) {
    playNowBtn.textContent = EOS_SIM_CTA_BY_WEEK[week] || 'Sim Next Round';
    playNowBtn.dataset.mode = 'sim-rest-tournament';
  } else if (trainingDisabledForPostseason && !eliminated) {
    playNowBtn.textContent = EOS_PLAY_CTA_BY_WEEK[week] || 'Play Next Game';
    playNowBtn.dataset.mode = 'play';
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
  const week = Number(data?.week || 1);
  const resultsWeek = Number(data?.current_recruiting_results_week || 0);
  let text = 'Recruiting Invites Begin Week 20';
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
    text = 'Recruiting Is Complete';
  } else if (week > 26) {
    text = 'Recruiting Runs After National Tourney';
  }

  const slots = [
    ['fcc-recruiting-live-copy-home', 'fcc-recruiting-btn-home'],
    ['fcc-recruiting-live-copy-tab', 'fcc-recruiting-btn-tab'],
  ];
  for (const [copyId, btnId] of slots) {
    const recruitingBtn = document.getElementById(btnId);
    const liveCopy = document.getElementById(copyId);
    if (!recruitingBtn || !liveCopy) continue;
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

const FCC_CONFIRM_NAV_DELAY_MS = 200;
function waitForConfirmSfx() {
  return new Promise(resolve => setTimeout(resolve, FCC_CONFIRM_NAV_DELAY_MS));
}

const playNowBtn = document.getElementById('play-now');
playNowBtn.disabled = true;
playNowBtn.addEventListener('click', async () => {
  playSound('confirm-1-lowervol.wav');
  const confirmSfxReady = waitForConfirmSfx();
  const mode = playNowBtn.dataset.mode || 'play';

  if (mode === 'finish-cpu-sims') {
    const topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
    const recovered = await recoverCpuSimsBeforeFccRender(topData);
    if (recovered && !fccCpuSimNeedsRecovery(recovered)) {
      window.location.href = `/franchise-command-center.html?franchise_id=${encodeURIComponent(franchiseId)}`;
    } else {
      updatePlayButton(recovered || topData);
    }
    return;
  }
  
  if (mode === 'training') {
    const topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
    if (topData?.training_disabled_for_eos || topData?.training_disabled_for_postseason) {
      return;
    }
    const sessionType = topData?.session_type || 'in-season';
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('mode', 'franchise');
    params.set('session_type', sessionType);
    params.set('return_url', getCurrentRelativeUrl());
    if (userTeamId) params.set('team_id', userTeamId);
    const trainingReturnUrl = `/training.html?${params.toString()}`;
    const navigateToTraining = async () => {
      await confirmSfxReady;
      try {
        const { clearFranchiseMusicState } = await import('/js/musicController.js');
        clearFranchiseMusicState();
      } catch {}
      window.location.href = trainingReturnUrl;
    };
    if (window.GOBTutorialAlerts) {
      const blocked = await window.GOBTutorialAlerts.interceptTraining(franchiseId, navigateToTraining, trainingReturnUrl);
      if (blocked) return;
    } else {
      await navigateToTraining();
    }
    return;
  }

  if (mode === 'week35-recruiting') {
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('return_url', getCurrentRelativeUrl());
    const recruitingUrl = `/recruiting-orders.html?${params.toString()}`;
    const goRecruiting = async () => {
      await confirmSfxReady;
      try {
        const { clearFranchiseMusicState } = await import('/js/musicController.js');
        clearFranchiseMusicState();
      } catch {}
      window.location.href = recruitingUrl;
    };
    // Offer optional pre-recruiting cuts (real cuts — players lost forever).
    const cutParams = new URLSearchParams();
    cutParams.set('franchise_id', franchiseId);
    cutParams.set('team_id', userTeamId);
    cutParams.set('mode', 'cut');
    cutParams.set('from', 'week35');
    cutParams.set('next_url', recruitingUrl);
    const cutUrl = `/cut-players.html?${cutParams.toString()}`;

    const overlay = document.createElement('div');
    overlay.className = 'gob-modal-overlay fcc-cut-required-modal is-visible';
    overlay.setAttribute('aria-hidden', 'false');
    overlay.innerHTML = `
      <div class="gob-modal-backdrop"></div>
      <div class="gob-modal-box" role="dialog" aria-modal="true" aria-labelledby="fcc-wk35-cut-title" aria-describedby="fcc-wk35-cut-copy">
        <div class="gob-modal-accent"></div>
        <div class="gob-modal-body">
          <h3 id="fcc-wk35-cut-title" class="gob-modal-title">Cut Players?</h3>
          <p id="fcc-wk35-cut-copy" class="gob-modal-subtitle">Would you like to cut any players ahead of recruiting? Note any players cut will be lost forever, but you will open additional slots for recruiting.</p>
        </div>
        <div class="gob-modal-actions">
          <button type="button" class="gob-modal-btn-secondary" id="fcc-wk35-cut-yes">Cut Players</button>
          <button type="button" class="gob-modal-btn-primary" id="fcc-wk35-cut-no">No Cuts</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector('#fcc-wk35-cut-yes')?.addEventListener('click', () => { window.location.href = cutUrl; });
    overlay.querySelector('#fcc-wk35-cut-no')?.addEventListener('click', () => { overlay.remove(); goRecruiting(); });
    return;
  }

  if (mode === 'cut-players') {
    const params = new URLSearchParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('return_url', getCurrentRelativeUrl());
    await confirmSfxReady;
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
      await confirmSfxReady;
      location.reload();
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
    const closeModal = () => {
      if (typeof modal.closeGobModal === 'function') modal.closeGobModal();
      else modal.remove();
    };
    modal.querySelector('#fcc-new-season-cancel')?.addEventListener('click', () => {
      closeModal();
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
        closeModal();
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
    if (userTeamId) url += `&team_id=${encodeURIComponent(userTeamId)}&user_team_id=${encodeURIComponent(userTeamId)}`;
    if (resolvedSide) url += `&my_team=${resolvedSide}`;
    console.log('Navigating to', url);
    const navigateToLineup = async () => {
      await confirmSfxReady;
      try {
        const { clearFranchiseMusicState } = await import('/js/musicController.js');
        clearFranchiseMusicState();
      } catch {}
      window.location.href = url;
    };
    if (window.GOBTutorialAlerts) {
      const blocked = await window.GOBTutorialAlerts.interceptPlayNextGame(franchiseId, url, navigateToLineup);
      if (blocked) {
        playNowBtn.disabled = false;
        playNowBtn.textContent = originalText;
        return;
      }
    } else {
      await navigateToLineup();
    }
  } catch (err) {
    console.error(err);
    alert('Unable to play next game');
    playNowBtn.disabled = false;
    playNowBtn.textContent = originalText;
  }
});

function navigateToGamePlan() {
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
}

// Legacy route buttons were removed from the FCC tab bar in favor of local placeholder tabs.
function wireFccNavButtons() {
  const setGameplanBtn = document.getElementById('set-gameplan-franchise');
  if (setGameplanBtn) {
    setGameplanBtn.addEventListener('click', navigateToGamePlan);
  }
  const fccEditGamePlanBtn = document.getElementById('fcc-edit-game-plan-btn');
  if (fccEditGamePlanBtn) {
    fccEditGamePlanBtn.addEventListener('click', navigateToGamePlan);
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
    exitFranchiseBtn.addEventListener('click', async () => {
      playSound('x-back.mp3');
      try {
        const { clearFranchiseMusicState } = await import('/js/musicController.js');
        clearFranchiseMusicState();
      } catch {}
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
        if (tabName === 'press-tab') {
          void renderNewsTab();
        }
        if (tabName === 'game-plan-tab') {
          renderGamePlanSummary();
        }
        if (tabName === 'playbooks-tab') {
          void renderFccPlaybooksSummary();
        }
        if (tabName === 'coaches-tab') {
          void renderScoutingTab();
        }
        if (tabName === 'schedule-tab') {
          void renderScheduleTab();
        }
        if (tabName === 'fcc-team-stats-summary-tab') {
          void renderFccTeamStatsSummary();
        }
        if (tabName === 'awards-tab') {
          void renderFccLeadersSummary();
        }
        if (tabName === 'team-stats-tab') {
          renderTeamReport();
        }
        if (tabName === 'tutorials-tab' && commandCenterTopDataCache) {
          renderFccInbox(commandCenterTopDataCache);
        }
      }
    });
  }
});

function renderFccInbox(topData) {
  const el = document.getElementById('fcc-inbox-body');
  if (!el) return;
  el.innerHTML = '';
  const inboxItems = Array.isArray(topData?.season_inbox) ? topData.season_inbox : [];
  const w = topData && topData.last_training_report_week;
  const tid = (topData && topData.team_id) || userTeamId;

  if (w != null && w !== '' && franchiseId && tid) {
    const weekNum = Number(w);
    if (Number.isFinite(weekNum) && weekNum >= 1) {
      const reportParams = new URLSearchParams({
        mode: 'franchise',
        franchise_id: String(franchiseId),
        team_id: String(tid),
        week: String(weekNum),
        from: 'inbox',
      });
      const href = `/training-report.html?${reportParams.toString()}`;
      const p = document.createElement('p');
      p.className = 'fcc-inbox-message';
      p.appendChild(document.createTextNode(`Week ${weekNum} training report `));
      const a = document.createElement('a');
      a.href = href;
      a.className = 'fcc-inbox-link';
      a.textContent = 'here';
      p.appendChild(a);
      p.appendChild(document.createTextNode('.'));
      el.appendChild(p);
    }
  }

  inboxItems.forEach((item) => {
    if (!item) return;
    if (item.type === 'training_squad_report') {
      const tsParams = new URLSearchParams({
        franchise_id: String(franchiseId || ''),
        team_id: String(tid || ''),
        from: 'inbox',
      });
      const p = document.createElement('p');
      p.className = 'fcc-inbox-message';
      p.appendChild(document.createTextNode(`Week #${Number(item.week)} Practice Squad Development report `));
      const a = document.createElement('a');
      a.href = `/training-squad-report.html?${tsParams.toString()}`;
      a.className = 'fcc-inbox-link';
      a.textContent = 'here';
      p.appendChild(a);
      p.appendChild(document.createTextNode('.'));
      el.appendChild(p);
      return;
    }
    if (item.type !== 'game_result') return;
    const itemWeek = Number(item.week);
    const verb = item.result === 'win' ? 'defeated' : 'lost to';
    const text = Number.isFinite(itemWeek) && item.user_team_name && item.opponent_team_name
      ? `Week #${itemWeek}: ${item.user_team_name} ${verb} ${item.opponent_team_name} ${item.user_score}-${item.opponent_score}`
      : item.copy;
    if (!text) return;
    const p = document.createElement('p');
    p.className = 'fcc-inbox-message';
    p.appendChild(document.createTextNode(`${text} `));
    if (item.box_score_url) {
      const a = document.createElement('a');
      a.href = item.box_score_url;
      a.className = 'fcc-inbox-link';
      a.textContent = 'box score';
      p.appendChild(a);
    }
    el.appendChild(p);
  });

  if (!el.childElementCount) {
    el.innerHTML = '<p class="fcc-inbox-empty">Inbox is empty.</p>';
  }
}

// Team Report and Playbook Summary functions (adapted from training-report.js)
const TEAM_ATTR_NAMES = {
  'shot_threshold': 'Shooting',
  'rebound_modifier': 'Rebounding',
  'offensive_efficiency': 'Offense',
  'defensive_efficiency': 'Defense',
  'fb_efficiency': 'Fast Breaks',
  'pt_efficiency': 'Press/Traps',
  'fight': 'Fight',
  'discipline': 'Discipline',
  'momentum_score': 'Momentum',
  'team_chemistry': 'Team Chemistry',
  'fb_opp_modifier': 'Fast Break Defense',
  'pt_opp_modifier': 'P/T Offense'
};

let teamData = null;

async function loadTeamData() {
  if (!franchiseId || !userTeamId) return;
  
  const loadTeamDataStartTime = performance.now();
  console.log('⏱️ [PERF] loadTeamData() function START');
  
  try {
    // First, ensure team objects exist (this will create them if missing)
    let gamePlanData = null;
    try {
      // ✅ SS&S: Use ObjectId directly - backend accepts it
      const gameplanStartTime = performance.now();
      console.log('⏱️ [PERF] loadTeamData() calling /api/gameplan START');
      const gameplanResponse = await fetch(`${API_CONFIG.buildUrl('/api/gameplan')}?mode=franchise&franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`, { headers: API_CONFIG.getAuthHeaders() });
      const gameplanEndTime = performance.now();
      console.log(`⏱️ [PERF] loadTeamData() /api/gameplan: ${(gameplanEndTime - gameplanStartTime).toFixed(2)}ms`);
      if (gameplanResponse.ok) {
        gamePlanData = await gameplanResponse.json();
      }
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
      players: players,
      game_plan: gamePlanData || { strategy_settings: {} }
    };
    persistFccSessionCache();
    
    // Log all team attribute values on page load
    console.log('📊 [TEAM ATTRIBUTES] All team attribute values:', teamData.team_attributes);
    
    // Render if Team Measures tab is active
    const teamMeasuresTab = document.getElementById('team-stats-tab');
    if (teamMeasuresTab && teamMeasuresTab.classList.contains('active')) {
      renderTeamReport();
    }
    const gamePlanTab = document.getElementById('game-plan-tab');
    if (gamePlanTab && gamePlanTab.classList.contains('active')) {
      renderGamePlanSummary();
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
  const teamAttrs = teamData.team_attributes || {};
  const radarHost = document.getElementById('team-measures-radar');
  const shootingHost = document.getElementById('team-measure-shooting');
  const reboundingHost = document.getElementById('team-measure-rebounding');
  const chemistryHost = document.getElementById('team-measure-chemistry');
  if (!radarHost || !shootingHost || !reboundingHost || !chemistryHost) return;

  radarHost.innerHTML = buildTeamMeasuresRadarMarkup(teamAttrs);
  shootingHost.innerHTML = buildTeamMeasuresLinearCardMarkup('Shooting', 'shot_threshold', Number(teamAttrs.shot_threshold || 0));
  reboundingHost.innerHTML = buildTeamMeasuresLinearCardMarkup('Rebounding', 'rebound_modifier', Number(teamAttrs.rebound_modifier || 0));
  chemistryHost.innerHTML = buildTeamMeasuresLinearCardMarkup('Team Chemistry', 'team_chemistry', Number(teamAttrs.team_chemistry || 0));
}

function mapGamePlanValue(key, rawValue) {
  const value = Math.max(0, Math.min(4, Number(rawValue ?? 2)));
  switch (key) {
    case 'offense':
      return {
        0: '100% Motion',
        1: '75% Motion / 25% Set Plays',
        2: '50% Motion / 50% Set Plays',
        3: '75% Set Plays / 25% Motion',
        4: '100% Set Plays'
      }[value];
    case 'defense':
      return {
        0: '100% Man',
        1: '75% Man / 25% Zone',
        2: '50% Man / 50% Zone',
        3: '75% Zone / 25% Man',
        4: '100% Zone'
      }[value];
    case 'fast_breaks':
      return {
        0: '100% Half Court Sets',
        1: '75% Half Court Sets / 25% Fast Breaks',
        2: '50% Half Court Sets / 50% Fast Breaks',
        3: '75% Fast Breaks / 25% Half Court Sets',
        4: '100% Fast Breaks'
      }[value];
    case 'tempo':
      return {
        0: 'Slow',
        1: 'Slow / Normal',
        2: 'Normal',
        3: 'Normal / Fast',
        4: 'Fast'
      }[value];
    case 'alterations':
      return {
        0: 'Least',
        1: 'Less',
        2: 'Normal',
        3: 'More',
        4: 'Most'
      }[value];
    case 'aggression':
      return {
        0: 'Passive',
        1: 'Normal / Passive',
        2: 'Normal',
        3: 'Normal / Aggressive',
        4: 'Aggressive'
      }[value];
    case 'rebounding':
      return {
        0: '100% Crash The Boards',
        1: '75% Crash The Boards / 25% Get Back on D',
        2: '50% Crash The Boards / 50% Get Back on D',
        3: '75% Get Back on D / 25% Crash The Boards',
        4: '100% Get Back on D'
      }[value];
    default:
      return GENERIC_GAMEPLAN_SCALE[value] || 'Normal';
  }
}

function buildGamePlanSummaryMarkup(strategySettings = {}) {
  const items = GAMEPLAN_DISPLAY_ORDER.map((key) => {
    const label = GAMEPLAN_LABELS[key];
    const valueText = mapGamePlanValue(key, strategySettings?.[key]);
    return `
      <div class="fcc-game-plan-item">
        <div class="fcc-game-plan-label">${label}</div>
        <div class="fcc-game-plan-value">${valueText}</div>
      </div>
    `;
  });
  return items.join('');
}

function renderGamePlanSummary() {
  const host = document.getElementById('fcc-game-plan-grid');
  if (!host) return;
  const strategySettings = teamData?.game_plan?.strategy_settings;
  if (!strategySettings || typeof strategySettings !== 'object') {
    host.innerHTML = '<div class="fcc-game-plan-empty">Game plan settings are not available yet.</div>';
    return;
  }
  host.innerHTML = buildGamePlanSummaryMarkup(strategySettings);
}

const TEAM_MEASURES_RADAR_AXES = [
  { key: 'offensive_efficiency', label: 'Offense', angle: -90 },
  { key: 'fb_efficiency', label: 'Fast Breaks', angle: -45 },
  { key: 'discipline', label: 'Discipline', angle: 0 },
  { key: 'pt_efficiency', label: 'Press/Traps', angle: 45 },
  { key: 'defensive_efficiency', label: 'Defense', angle: 90 },
  { key: 'fb_opp_modifier', label: 'Fast Break Defense', angle: 135 },
  { key: 'fight', label: 'Fight', angle: 180 },
  { key: 'pt_opp_modifier', label: 'P/T Offense', angle: 225 }
];

function buildTeamMeasuresRadarMarkup(teamAttrs) {
  const center = 250;
  const radius = 164;
  const labelRadius = 204;
  const pointLabelRadius = 18;
  const ringValues = [10, 6.7, 3.3, 0, -3.3, -6.7, -10];

  const values = TEAM_MEASURES_RADAR_AXES.map((axis) => Number(teamAttrs?.[axis.key] || 0));
  const clampedValues = values.map((value) => Math.max(-10, Math.min(10, value)));
  const dominantCount = values.filter((value) => Number(value) >= 7).length;

  function radiusForValue(value) {
    const clamped = Math.max(-10, Math.min(10, Number(value) || 0));
    return ((clamped + 10) / 20) * radius;
  }

  function pointFor(angleDeg, value, extra = 0) {
    const radians = (angleDeg * Math.PI) / 180;
    const scaledRadius = radiusForValue(value) + extra;
    return {
      x: center + Math.cos(radians) * scaledRadius,
      y: center + Math.sin(radians) * scaledRadius
    };
  }

  const ringPolygons = ringValues.map((ringValue) => {
    const points = TEAM_MEASURES_RADAR_AXES.map((axis) => {
      const point = pointFor(axis.angle, ringValue);
      return `${point.x.toFixed(2)},${point.y.toFixed(2)}`;
    }).join(' ');
    const ringClass = ringValue === 10
      ? ' tm-radar-ring-outer'
      : ringValue === 0
        ? ' tm-radar-ring-zero'
        : ringValue === -10
          ? ' tm-radar-ring-inner'
          : '';
    return `<polygon class="tm-radar-ring${ringClass}" points="${points}" />`;
  }).join('');

  const axisLines = TEAM_MEASURES_RADAR_AXES.map((axis) => {
    const point = pointFor(axis.angle, 10);
    return `<line class="tm-radar-axis" x1="${center}" y1="${center}" x2="${point.x.toFixed(2)}" y2="${point.y.toFixed(2)}" />`;
  }).join('');

  const shapePoints = TEAM_MEASURES_RADAR_AXES.map((axis, index) => {
    const point = pointFor(axis.angle, clampedValues[index]);
    return `${point.x.toFixed(2)},${point.y.toFixed(2)}`;
  }).join(' ');

  const labels = TEAM_MEASURES_RADAR_AXES.map((axis) => {
    const point = pointFor(axis.angle, 10, labelRadius - radius);
    return `<text class="tm-radar-axis-label" x="${point.x.toFixed(2)}" y="${point.y.toFixed(2)}" text-anchor="middle" dominant-baseline="middle">${axis.label}</text>`;
  }).join('');

  const valueLabels = TEAM_MEASURES_RADAR_AXES.map((axis, index) => {
    return '';
  }).join('');

  return `
    <div class="tm-radar-wrap">
      <svg class="tm-radar-svg" viewBox="0 0 500 500" role="img" aria-label="Team Measures radar chart">
        <defs>
          <filter id="tm-radar-outline-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="tm-radar-point-glow" x="-200%" y="-200%" width="400%" height="400%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <g class="tm-radar-grid">
          ${ringPolygons}
          ${axisLines}
        </g>
        <polygon class="tm-radar-shape-fill" points="${shapePoints}" />
        <polygon class="tm-radar-shape-outline${dominantCount >= 3 ? ' is-pulsing' : ''}" points="${shapePoints}" />
        ${labels}
        ${valueLabels}
      </svg>
    </div>
  `;
}

function buildTeamMeasuresLinearCardMarkup(title, attrKey, value) {
  const visual = getTeamAttrVisualConfig(attrKey, value);
  if (attrKey === 'team_chemistry') {
    const percentage = Math.max(0, Math.min((Number(value) / 25) * 100, 100));
    const pulseClass = visual.pulse ? ' is-pulsing' : '';
    return `
      <div class="tm-side-card-content tm-side-card-content-chemistry">
        <div class="tm-side-card-label">${title}</div>
        <div class="tm-chemistry-bar${pulseClass}">
          <div class="tm-chemistry-fill" style="width:${percentage}%; opacity:${0.2 + (percentage / 100) * 0.8};"></div>
          <div class="tm-chemistry-text">${visual.displayValue}</div>
        </div>
      </div>
    `;
  }

  const pulseClass = visual.pulse ? ' is-pulsing' : '';
  const fillMarkup = visual.direction === 'positive'
    ? `<div class="tm-linear-fill tm-linear-fill-positive" style="width:${visual.fillPercent}%"></div>`
    : (visual.direction === 'negative'
      ? `<div class="tm-linear-fill tm-linear-fill-negative" style="width:${visual.fillPercent}%"></div>`
      : '');

  return `
    <div class="tm-side-card-content">
      <div class="tm-side-card-label">${title}</div>
      <div class="tm-linear-bar${pulseClass}">
        ${fillMarkup}
        <div class="tm-linear-center"></div>
      </div>
    </div>
  `;
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
  const visual = getTeamAttrVisualConfig(attrKey, Number(currentValue) || 0);
  if (visual.cardTone) item.dataset.tone = visual.cardTone;
  
  const label = document.createElement('div');
  label.className = 'attr-label';
  
  const nameSpan = document.createElement('span');
  nameSpan.textContent = displayName;
  
  label.appendChild(nameSpan);
  item.appendChild(label);
  
  if (attrKey === 'team_chemistry') {
    const barContainer = document.createElement('div');
    barContainer.className = 'fcc-chemistry-bar-container';
    if (visual.pulse) barContainer.classList.add('is-pulsing');
    
    const barFill = document.createElement('div');
    barFill.className = 'fcc-chemistry-bar-fill';
    const percentage = Math.max(0, Math.min((Number(currentValue) / 25) * 100, 100));
    barFill.style.width = `${percentage}%`;
    barFill.style.opacity = String(0.2 + (percentage / 100) * 0.8);
    
    const barText = document.createElement('div');
    barText.className = 'fcc-chemistry-bar-text';
    barText.textContent = `${currentValue} / 25`;
    
    barContainer.appendChild(barFill);
    barContainer.appendChild(barText);
    item.appendChild(barContainer);
  } else {
    const pill = createPill(currentValue, attrKey);
    item.appendChild(pill);
  }
  
  return item;
}

function createPill(originalValue, attrKey) {
  const pill = document.createElement('div');
  pill.className = 'attr-pill';
  const visual = getTeamAttrVisualConfig(attrKey, Number(originalValue) || 0);
  if (visual.direction !== 'zero') {
    pill.classList.add(`pill-${visual.direction}`);
  }
  if (visual.pulse) {
    pill.classList.add('is-pulsing');
  }
  
  const centerLine = document.createElement('div');
  centerLine.className = 'pill-center-line';
  pill.appendChild(centerLine);

  if (visual.direction === 'positive') {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-positive';
    fill.style.width = `${visual.fillPercent}%`;
    pill.insertBefore(fill, centerLine);
  } else if (visual.direction === 'negative') {
    const fill = document.createElement('div');
    fill.className = 'pill-fill-negative';
    fill.style.width = `${visual.fillPercent}%`;
    pill.insertBefore(fill, centerLine);
  }

  const valueLabel = document.createElement('div');
  valueLabel.className = 'pill-value show';
  valueLabel.textContent = visual.displayValue;
  pill.appendChild(valueLabel);
  
  return pill;
}

function formatTeamAttrDisplayValue(attrKey, value) {
  const numericValue = Number(value) || 0;
  if (attrKey === 'rebound_modifier') return numericValue.toFixed(2);
  return Number.isInteger(numericValue) ? String(numericValue) : numericValue.toFixed(1);
}

function getTeamAttrVisualConfig(attrKey, value) {
  if (attrKey === 'team_chemistry') {
    return {
      direction: value > 0 ? 'positive' : 'zero',
      fillPercent: Math.max(0, Math.min((value / 25) * 100, 100)),
      displayValue: `${value} / 25`,
      pulse: value <= 5 || value >= 22,
      cardTone: value < 8 ? 'warning-negative' : (value > 20 ? 'warning-elite' : '')
    };
  }

  let normalized = value;
  let fillPercent = 0;
  let pulse = false;

  if (attrKey === 'shot_threshold') {
    const st = window.TeamShotThresholdScale;
    normalized = st.normalizedScore(value);
    fillPercent = st.pillFillPercent(value);
    pulse = st.shouldPulse(value);
  } else if (attrKey === 'rebound_modifier') {
    const deviation = value - 0.2;
    normalized = (deviation / 0.2) * 10;
    fillPercent = Math.min((Math.abs(deviation) / 0.2) * 50, 50);
    pulse = Math.abs(deviation) >= 0.06;
  } else {
    fillPercent = Math.min((Math.abs(normalized) / 10) * 50, 50);
    pulse = Math.abs(normalized) >= 7;
  }

  let cardTone = '';
  if (normalized <= -6) cardTone = 'negative';
  else if (normalized >= 6) cardTone = 'positive';

  return {
    direction: normalized > 0 ? 'positive' : (normalized < 0 ? 'negative' : 'zero'),
    fillPercent,
    displayValue: formatTeamAttrDisplayValue(attrKey, value),
    pulse,
    cardTone
  };
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
  
  let man_defenses = [];
  let zone_defenses = [];
  if (scouting_data.defense && typeof window !== 'undefined' && window.GOBDefenseDisplay) {
    const split = window.GOBDefenseDisplay.buildPlaybookStyleDefenseRows(scouting_data.defense);
    man_defenses = split.man_defenses;
    zone_defenses = split.zone_defenses;
  } else if (scouting_data.defense) {
    for (const [defense_name, defense_data] of Object.entries(scouting_data.defense)) {
      if (typeof defense_data === 'object' && defense_data !== null) {
        if (defense_name === 'Man' || defense_name === 'man') {
          man_defenses.push({ name: defense_name === 'man' ? 'Man' : defense_name, ...defense_data });
        } else if (defense_name.includes('Zone') || defense_name.includes('zone')) {
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
  
  // Command metric - Blue, 0-100 scale
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
  
  // Change indicator (only for Command)
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

// ✅ EOS TOURNAMENT: Render tournament bracket (shared renderer: franchise-tournament-brackets-render.js)
async function renderTournamentBracket() {
  const container =
    document.getElementById('fcc-tournament-bracket') || document.getElementById('tournament-bracket-container');
  const titleEl = document.getElementById('fcc-tournament-title');
  if (!container || !franchiseId) return;

  let topData = commandCenterTopDataCache;
  try {
    topData = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}&profile=1`);
    commandCenterTopDataCache = topData;
  } catch (e) {
    console.warn('[FCC] Could not refresh command-center data for bracket:', e);
    if (!topData) {
      container.innerHTML = '<p class="fcc-tournament-empty-msg">Tournament bracket not available.</p>';
      return;
    }
  }

  let teamIdToNameMap = {};
  try {
    const teamStatsRes = await fetchJSON(`${API_CONFIG.buildUrl('/franchise/team-stats')}?franchise_id=${franchiseId}`);
    const teams = teamStatsRes?.teams || [];
    teams.forEach(function (t) {
      if (t.team_id != null && t.team != null) {
        teamIdToNameMap[String(t.team_id)] = t.team;
        const st = t.stats || {};
        teamIdMetaMap[String(t.team_id)] = {
          team: t.team,
          mascot: t.mascot || '',
          conference: t.conference,
          region: t.region != null && t.region !== '' ? String(t.region).toUpperCase() : '',
          natl_rank: t.natl_rank != null && Number.isFinite(Number(t.natl_rank)) ? Number(t.natl_rank) : null,
          W: Number.isFinite(Number(st.W)) ? Number(st.W) : 0,
          L: Number.isFinite(Number(st.L)) ? Number(st.L) : 0,
        };
      }
    });
  } catch (e) {
    console.warn('[FCC] Could not load team-stats for bracket names:', e);
  }

  if (typeof FranchiseTournamentBrackets !== 'undefined' && FranchiseTournamentBrackets.appendFranchiseBracketSections) {
    FranchiseTournamentBrackets.appendFranchiseBracketSections(container, topData, {
      userTeamId,
      teamIdToNameMap,
      teamIdMetaMap,
      mode: 'fcc',
      titleEl,
      allTournamentsHref: buildResourceUrl('brackets.html'),
    });
  } else {
    container.innerHTML = '<p class="fcc-tournament-empty-msg">Bracket UI not loaded.</p>';
  }
}

// Scouting Report functionality
let upcomingOpponent = null;
let upcomingOpponentId = null;
let scoutingTabDataCache = null;
let fccScoutingProjectedViewMode = 'attributes';

function disableLegacyFccScoutingModal() {
  const legacyModal = document.getElementById('scouting-report-modal');
  if (legacyModal) legacyModal.remove();

  const legacyScoutingButton = document.getElementById('scouting-report-btn');
  if (legacyScoutingButton) {
    legacyScoutingButton.style.display = 'none';
    legacyScoutingButton.setAttribute('aria-hidden', 'true');
  }
}

disableLegacyFccScoutingModal();

async function resolveUpcomingOpponentFromMatchup(data) {
  const resolvedUserTeamName = data?.team || userTeamNameForLeaders || userTeamName || '';
  const week = data?.week || data?.training_status?.current_week || 0;
  const eosTournamentActive = data?.eos_tournament_active || false;
  const eosTournament = data?.eos_tournament;

  let userTeamEliminated = false;
  if (eosTournamentActive && eosTournament && userTeamId && week >= 27) {
    const bracket = eosTournament.bracket || {};
    const allMatchups = [...(bracket.round1 || []), ...(bracket.round2 || []), ...(bracket.final || [])];
    userTeamEliminated = !allMatchups.some((m) =>
      String(m.home_team) === String(userTeamId) || String(m.away_team) === String(userTeamId)
    );
  }

  const scoutingAvailable = data && ((week >= 0 && week <= 26) || (week >= 27 && week <= 34 && !userTeamEliminated));
  if (!scoutingAvailable || !franchiseId) {
    upcomingOpponent = null;
    upcomingOpponentId = null;
    return null;
  }

  try {
    const res = await fetch(API_CONFIG.buildUrl('/franchise/play-next-game'), {
      method: 'POST',
      headers: { ...API_CONFIG.getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: franchiseId })
    });
    if (!res.ok) throw new Error('Failed to resolve next game');
    const matchup = await res.json();
    upcomingOpponent = null;
    upcomingOpponentId = null;
    if (matchup && matchup.home && matchup.away) {
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
    }
    return upcomingOpponent ? { name: upcomingOpponent, id: upcomingOpponentId } : null;
  } catch (err) {
    console.warn('Could not determine upcoming opponent:', err);
    upcomingOpponent = null;
    upcomingOpponentId = null;
    return null;
  }
}

function updateScoutingButton(data) {
  const scoutingBtn = document.getElementById('scouting-report-btn');
  if (!scoutingBtn) return;
  resolveUpcomingOpponentFromMatchup(data).then((result) => {
    scoutingBtn.style.display = result ? 'block' : 'none';
  });
}

function renderFccScoutingProjectedLineup() {
  if (!scoutingTabDataCache) return;
  if (typeof renderProjectedStartingFive === 'function') {
    renderProjectedStartingFive(scoutingTabDataCache.projected_starting_five || [], {
      containerId: 'fcc-scouting-projected-lineup',
      tableClass: 'scouting-projected-table',
      emptyClass: 'scouting-projected-empty',
    });
  }
}

function renderFccScoutingMeasures(teamAttrs) {
  const radarHost = document.getElementById('fcc-scouting-radar-host');
  const shootingCard = document.getElementById('fcc-scouting-shooting-card');
  const reboundingCard = document.getElementById('fcc-scouting-rebounding-card');
  const chemistryCard = document.getElementById('fcc-scouting-chemistry-card');
  if (!radarHost || !shootingCard || !reboundingCard || !chemistryCard) return;

  const attrs = teamAttrs || {};
  radarHost.innerHTML = buildTeamMeasuresRadarMarkup(attrs);
  shootingCard.innerHTML = buildTeamMeasuresLinearCardMarkup('Shooting', 'shot_threshold', Number(attrs.shot_threshold || 0));
  reboundingCard.innerHTML = buildTeamMeasuresLinearCardMarkup('Rebounding', 'rebound_modifier', Number(attrs.rebound_modifier || 0));
  chemistryCard.innerHTML = buildTeamMeasuresLinearCardMarkup('Team Chemistry', 'team_chemistry', Number(attrs.team_chemistry || 0));
}

async function renderScoutingTab() {
  const status = document.getElementById('fcc-scouting-status');
  const content = document.getElementById('fcc-scouting-content');
  const opponentName = document.getElementById('fcc-scouting-opponent-name');
  const opponentRecord = document.getElementById('fcc-scouting-opponent-record');
  const opponentRank = document.getElementById('fcc-scouting-opponent-rank');
  if (!status || !content || !opponentName || !opponentRecord || !opponentRank) return;

  status.style.display = 'block';
  content.style.display = 'none';
  status.textContent = 'Loading scouting report...';

  const opponent = await resolveUpcomingOpponentFromMatchup(commandCenterTopDataCache);
  if (!opponent) {
    status.textContent = 'No upcoming opponent available for scouting.';
    return;
  }

  const opponentTeamName = opponent.name || '--';
  const standingsEntry = getStandingsTeamEntry(opponent.id);
  const rankingEntry = getTeamRankingEntry(opponent.id);
  const wins = Number(standingsEntry?.W ?? rankingEntry?.W ?? 0);
  const losses = Number(standingsEntry?.L ?? rankingEntry?.L ?? 0);
  const rank = Number(rankingEntry?.natl_rank || 0);

  opponentName.textContent = opponentTeamName;
  opponentRecord.textContent = `${wins}-${losses}`;
  opponentRank.textContent = Number.isFinite(rank) && rank > 0 ? String(rank) : '--';

  const teamPageLink = document.getElementById('fcc-scouting-team-page-link');
  if (teamPageLink) {
    if (opponent.id && franchiseId) {
      teamPageLink.href = buildFranchiseTeamPageUrl(opponent.id, opponentTeamName, 'coaches-tab');
    } else {
      // TODO: wire team page URL when opponent team id is unavailable in matchup context
      teamPageLink.href = '#';
    }
  }

  try {
    const authHeaders = API_CONFIG.getAuthHeaders();
    const [teamDataRes, playUsageRes] = await Promise.all([
      fetch(`${API_CONFIG.buildUrl('/franchise/team-data')}?franchise_id=${encodeURIComponent(franchiseId)}&team_name=${encodeURIComponent(opponent.name)}`, { headers: authHeaders }),
      fetch(`${API_CONFIG.buildUrl('/franchise/scouting-report')}?franchise_id=${encodeURIComponent(franchiseId)}&team_name=${encodeURIComponent(opponent.name)}`, { headers: authHeaders })
    ]);

    if (!teamDataRes.ok) throw new Error('Failed to load team report');
    if (!playUsageRes.ok) throw new Error('Failed to load play usage');

    const teamData = await teamDataRes.json();
    const playUsage = await playUsageRes.json();
    scoutingTabDataCache = playUsage || {};
    renderFccScoutingProjectedLineup();
    renderFccScoutingMeasures(teamData.team_attributes || {});
    if (typeof renderPlayUsage === 'function') {
      // Play Usage is gated on the user running this week's training with Film
      // Study (backend sets the *_unlocked flags). HCO unlocks at Film Study > 0;
      // Fast Breaks + Half-Court Traps unlock at > 1. Until then each panel shows
      // N/A with a hint. Absent HCO flag → treat as unlocked (back-compat).
      const playUsageUnlocked = playUsage.play_usage_unlocked !== false;
      renderPlayUsage(
        playUsageUnlocked ? (playUsage.plays || []) : [],
        playUsageUnlocked
          ? 'No previous game data available. Opponent has not played a game yet this season.'
          : "N/A — Run Film Study in training this week to scout this opponent's play usage.",
        'fcc-play-usage-body'
      );

      const extendedUnlocked = playUsage.fast_break_usage_unlocked === true;
      const extendedHint = "N/A — Set Film Study above 1 in training this week to scout this opponent's play usage.";
      renderPlayUsage(
        extendedUnlocked ? (playUsage.fast_break_plays || []) : [],
        extendedUnlocked
          ? 'No fast break data available from the opponent\'s last game.'
          : extendedHint,
        'fcc-fast-break-usage-body'
      );
      renderPlayUsage(
        (playUsage.hct_usage_unlocked === true) ? (playUsage.hct_trap_plays || []) : [],
        (playUsage.hct_usage_unlocked === true)
          ? 'No half-court trap data available from the opponent\'s last game.'
          : extendedHint,
        'fcc-hct-usage-body'
      );
    }
    status.style.display = 'none';
    content.style.display = 'flex';
  } catch (error) {
    console.error('Error loading scouting report tab:', error);
    status.textContent = `Error loading scouting report: ${error.message}`;
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
