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

function playSound(filename) {
  import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(filename, 0.7); }).catch(function () {});
}

const MODE_SELECT_MUSIC_VOLUME = 0.4;
const MODE_SELECT_MUSIC_FADE_MS = 600;
let modeSelectMusic = null;
let modeSelectMusicIsFading = false;

function leaveModeSelect(url) {
  if (window.GOBNav && typeof window.GOBNav.go === 'function') window.GOBNav.go(url);
  else window.location.href = url;
}

function navigateFromModeSelect(url) {
  if (modeSelectMusicIsFading) return;
  if (!modeSelectMusic || modeSelectMusic.paused) {
    leaveModeSelect(url);
    return;
  }

  modeSelectMusicIsFading = true;
  const startingVolume = modeSelectMusic.volume;
  const startedAt = performance.now();

  function fadeFrame(now) {
    const progress = Math.min((now - startedAt) / MODE_SELECT_MUSIC_FADE_MS, 1);
    modeSelectMusic.volume = startingVolume * (1 - progress);
    if (progress < 1) {
      window.requestAnimationFrame(fadeFrame);
      return;
    }
    modeSelectMusic.pause();
    leaveModeSelect(url);
  }

  window.requestAnimationFrame(fadeFrame);
}

const ALPHA_DISMISS_STORAGE_KEY = 'alpha_disclaimer_dismissed_version';
const ALPHA_DISCLAIMER_VERSION = '2026-08-12-player-attributes-alpha-box';

const homeBaseRoot = document.getElementById('home-base');
const alphaDisclaimer = document.getElementById('alpha-disclaimer');
const alphaDisclaimerDismiss = document.getElementById('alpha-disclaimer-dismiss');

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
/** Top-level hint from GET /franchise/list: the program that gets the green. */
let mostRecentFranchiseId = '';
/** The last view model handed to homeBase.js, so partial updates can reuse it. */
let hbView = null;
let hbUsername = '';
/** Career numerals from GET /franchise/coach-career (the left-zone strip, online). */
let hbCareer = null;
/** The offline "Your Career" right zone, from the same coach-career payload. */
let hbCareerZone = null;
/** PR 5 owns the Trophy Case route; the entry stays off until it lands. */
const HB_TROPHY_CASE_HREF = '/trophy-case.html';
/** How long the loader will wait on the right zone's first view before giving up. */
const COMMUNITY_FIRST_VIEW_TIMEOUT_MS = 6000;

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

function resolveFranchiseSlotBanner(franchiseData) {
  const teamName = safeText(franchiseData && franchiseData.user_team_id, 'Program');
  if (franchiseData && (franchiseData.asset_strategy === 'generated' || franchiseData.is_custom_team)) {
    return getTeamAssetPath(teamName, 'banner_card', {
      name: franchiseData.user_team_id,
      abbreviation: franchiseData.abbreviation,
      primary_color: franchiseData.primary_color,
      secondary_color: franchiseData.secondary_color,
      jersey_preset: franchiseData.jersey_preset,
      asset_strategy: 'generated',
      is_custom: true,
      replaced_name: franchiseData.team_builder_replaced_name,
    });
  }
  return getSquareLogoPath(teamName);
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

/**
 * Drops the shared branded loader. Only called once Home Base has painted real
 * content: the session check is done and the slots have rendered.
 */
function revealModeSelect() {
  if (window.PageLoadOverlay && typeof window.PageLoadOverlay.hide === 'function') {
    window.PageLoadOverlay.hide();
    return;
  }
  const overlay = document.getElementById('page-load-overlay');
  if (overlay) overlay.style.display = 'none';
}

/**
 * Resolves when `promise` settles or `ms` elapses, whichever comes first.
 * The community payloads gate the loader so the right zone is not blank behind
 * it, but a stalled community fetch must never strand the page on the loader —
 * that bug shipped once already.
 */
function settledOrAfter(promise, ms) {
  return Promise.race([
    Promise.resolve(promise).catch(function () {}),
    new Promise(function (resolve) { window.setTimeout(resolve, ms); }),
  ]);
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

function findRankingsEntry(commandCenterData, franchiseData, teamName) {
  const rankings = (commandCenterData && Array.isArray(commandCenterData.rankings)) ? commandCenterData.rankings : [];
  const objectId = franchiseData && franchiseData.user_team_object_id
    ? String(franchiseData.user_team_object_id)
    : '';
  if (objectId) {
    const byId = rankings.find(function (entry) {
      return entry && String(entry.team_id) === objectId;
    });
    if (byId) return byId;
  }
  return rankings.find(function (entry) {
    return entry && entry.team_name === teamName;
  }) || null;
}

function deriveRecord(commandCenterData, teamName, franchiseData) {
  const teamEntry = findRankingsEntry(commandCenterData, franchiseData, teamName);
  if (!teamEntry) return '0-0';
  const wins = Number.isFinite(teamEntry.W) ? teamEntry.W : parseInt(teamEntry.W || 0, 10) || 0;
  const losses = Number.isFinite(teamEntry.L) ? teamEntry.L : parseInt(teamEntry.L || 0, 10) || 0;
  return wins + '-' + losses;
}

function deriveNextOpponent(commandCenterData, teamName, franchiseData) {
  const teamEntry = findRankingsEntry(commandCenterData, franchiseData, teamName);
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

function setLeaderboardView(view) {
  currentLeaderboardView = view === 'titles' ? 'titles' : 'geek_points';
}

// Title-count display: total titles with national titles in parens, e.g. "7 (0)".
function displayTitlesValue(entry) {
  var total = parseInt(entry && entry.total_titles, 10);
  var natl = parseInt(entry && entry.national_titles, 10);
  if (!Number.isFinite(total)) total = 0;
  if (!Number.isFinite(natl)) natl = 0;
  return total + ' (' + natl + ')';
}

/**
 * Flattens /api/auth/leaderboard into the shape Home Base draws: ranked rows
 * (top three become tiles) plus the current user, pinned separately only when
 * the server put them outside the returned page.
 */
function hbLeaderboardModel(leaderboardData, currentUsername) {
  const titles = currentLeaderboardView === 'titles';
  const normalized = safeText(currentUsername, '').toLowerCase();
  const source = titles
    ? (leaderboardData && leaderboardData.titles_top)
    : (leaderboardData && leaderboardData.top);
  const pinnedEntry = titles
    ? (leaderboardData && leaderboardData.titles_current_user)
    : (leaderboardData && leaderboardData.current_user);

  function isMe(entry) {
    if (!entry) return false;
    if (entry.is_current_user) return true;
    return !!normalized && safeText(entry.username, '').toLowerCase() === normalized;
  }
  function valueOf(entry) {
    return titles ? displayTitlesValue(entry) : displayCommunityLeaderboardPoints(entry.geek_points);
  }
  function rowOf(entry) {
    return {
      rank: entry.rank,
      name: safeText(entry.username, 'Coach'),
      value: valueOf(entry),
      isMe: isMe(entry),
    };
  }

  const rows = (Array.isArray(source) ? source : []).map(rowOf);
  return {
    view: titles ? 'titles' : 'geek_points',
    unit: titles ? 'TITLES' : 'GP',
    rows: rows,
    meInTop: rows.some(function (row) { return row.isMe; }),
    me: pinnedEntry ? rowOf(pinnedEntry) : null,
  };
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

function renderCommunityLeaderboard(leaderboardData, currentUsername) {
  const model = hbLeaderboardModel(leaderboardData, currentUsername);
  if (hbView) hbView.leaderboard = model;
  if (window.GOBHomeBase) window.GOBHomeBase.renderLeaderboard(model);
}

/**
 * GET /franchise/coach-career -> the four career numerals. The server owns every
 * number here: win % arrives pre-formatted as `win_pct_display` (never derived
 * from record.win_rate), and a field the payload omits drops its cell.
 *
 * The client does no arithmetic: `titles_total` arrives pre-summed from the
 * server (Ch7 PR2), win % arrives as `win_pct_display`, and a field the payload
 * omits drops its cell.
 */
function hbCareerModel(data) {
  if (!data) return null;
  const model = {};
  const record = data.record;
  if (record && (record.wins != null || record.losses != null)) {
    const wins = safeNumber(record.wins, 0);
    const losses = safeNumber(record.losses, 0);
    model.record = wins + '\u2013' + losses;
    model.recordEmpty = (wins + losses) === 0;
    // Shown only when the server sends it; the client does not compute a rate.
    if (data.win_pct_display) model.winPct = String(data.win_pct_display);
  }
  if (data.titles_total != null) model.titles = safeNumber(data.titles_total, 0);
  if (data.seasons_completed != null) model.seasons = safeNumber(data.seasons_completed, 0);
  if (data.geek_points != null) {
    const gp = safeNumber(data.geek_points, 0);
    model.geekPointsRaw = gp;
    model.geekPoints = gp.toLocaleString('en-US');
  }
  return Object.keys(model).length ? model : null;
}

/**
 * A program's own banner art from a slug (+ optional generated visual), the same
 * name→slug producer the doors use. Team Builder / custom programs render their
 * generated art when the caller carries `assetStrategy: 'generated'` (and colours);
 * core programs resolve `<slug>_banner_card.webp`.
 */
function hbResolveBanner(spec) {
  spec = spec || {};
  if (typeof getTeamAssetPath !== 'function') return '';
  const nameOrSlug = spec.slug || spec.name || '';
  if (!nameOrSlug) return '';
  if (spec.assetStrategy === 'generated' || spec.isCustom) {
    return getTeamAssetPath(spec.name || spec.slug, 'banner_card', {
      name: spec.name,
      abbreviation: spec.abbreviation,
      mascot: spec.mascot,
      primary_color: spec.primaryColor,
      secondary_color: spec.secondaryColor,
      jersey_preset: spec.jerseyPreset,
      asset_strategy: 'generated',
      is_custom: true,
      replaced_name: spec.replacedName,
    });
  }
  return getTeamAssetPath(spec.slug || spec.name, 'banner_card');
}

// Trophy kinds → medallion (server owns the counts; the client only maps a kind
// to its letter, gold flag and display label, the way the frame does).
const HB_TITLE_MEDALLIONS = {
  national: { letter: 'N', label: 'National Champions' },
  region: { letter: 'R', label: 'Region Champions' },
  conf_t: { letter: 'C', label: 'Conference Tournament Champions' },
  conf_rs: { letter: 'C', label: 'Regular Season Conference Champions' },
};
const HB_MILESTONE_MEDALLIONS = {
  milestone_first_signing_class: { letter: 'S', label: 'First signing class' },
  milestone_first_bracket: { letter: 'B', label: 'First bracket' },
  milestone_first_archetype: { letter: 'A', label: 'First coach archetype' },
};

function hbTrophyMedallion(trophy) {
  const kind = String((trophy && trophy.kind) || '');
  const title = HB_TITLE_MEDALLIONS[kind];
  const milestone = HB_MILESTONE_MEDALLIONS[kind];
  const spec = title || milestone;
  if (!spec) return null; // All-Americans and season records are not shelf medallions.
  const team = safeText(trophy.team_name, '');
  const season = trophy.season != null ? 'Season ' + trophy.season : '';
  const sub = [team, season].filter(Boolean).join(' · ');
  return { gold: !!title, letter: spec.letter, title: spec.label, sub: sub };
}

/** One server top_seasons row -> one .tsn row. Server order is preserved. */
function hbTopSeasonRow(row) {
  const wins = safeNumber(row.wins, 0);
  const losses = safeNumber(row.losses, 0);
  const gp = safeNumber(row.season_gp, 0);
  return {
    bannerUrl: hbResolveBanner({ slug: row.team_slug, name: row.team_name }),
    name: safeText(row.team_name, 'Program'),
    season: row.season != null ? row.season : '',
    record: wins + '–' + losses,
    finish: safeText(row.finish, ''),
    finishIsTitle: !!row.finish_is_title,
    inProgress: !!row.in_progress,
    week: row.week != null ? row.week : '',
    geekPoints: gp.toLocaleString('en-US'),
  };
}

/**
 * The offline "Your Career" zone (Ch7 PR2). Every numeral is a server value; the
 * trophies and Top Seasons come pre-ranked. Titles are grouped before milestones
 * on the shelf so the count line ("3 titles · 2 milestones") reads in the same
 * order. Nothing here derives a number or a ranking.
 */
function hbCareerZoneModel(data) {
  if (!data) return null;
  const record = data.record || {};
  const wins = safeNumber(record.wins, 0);
  const losses = safeNumber(record.losses, 0);
  const titles = safeNumber(data.titles_total, 0);
  const seasons = safeNumber(data.seasons_completed, 0);
  const gp = safeNumber(data.geek_points, 0);
  const recordHollow = (wins + losses) === 0;

  const rawTrophies = Array.isArray(data.trophies) ? data.trophies : [];
  const medallions = rawTrophies.map(hbTrophyMedallion).filter(Boolean);
  const titleMeds = medallions.filter(function (m) { return m.gold; });
  const milestoneMeds = medallions.filter(function (m) { return !m.gold; });

  const topSeasons = (Array.isArray(data.top_seasons) ? data.top_seasons : []).map(hbTopSeasonRow);

  return {
    record: wins + '–' + losses,
    recordHollow: recordHollow,
    winPct: data.win_pct_display ? String(data.win_pct_display) : '',
    titles: String(titles),
    titlesHollow: titles === 0,
    seasons: String(seasons),
    seasonsHollow: seasons === 0,
    geekPoints: gp.toLocaleString('en-US'),
    geekPointsHollow: gp === 0,
    // The caption reads as an invitation; it only fits a truly fresh coach.
    zeroState: recordHollow && titles === 0 && seasons === 0 && gp === 0,
    trophies: titleMeds.concat(milestoneMeds),
    trophyCounts: { titles: titleMeds.length, milestones: milestoneMeds.length },
    topSeasons: topSeasons,
  };
}

async function loadCoachCareer() {
  // Loopback serves this on desktop (a /franchise route, never a community host),
  // so it runs offline too and feeds the "Your Career" zone. No remote call.
  const data = await safeJsonFetch(API_CONFIG.buildUrl('/franchise/coach-career'), {
    headers: getAuthHeaders(),
  });
  hbCareer = hbCareerModel(data);
  hbCareerZone = hbCareerZoneModel(data);
  if (hbView) {
    hbView.career = hbCareer;
    hbView.careerZone = hbCareerZone;
    if (window.GOBHomeBase) window.GOBHomeBase.render(hbView);
  }
}

// Around GOB and the leaderboards are always-remote community routes. The
// desktop profile has no community backend: no requests, and the right zone
// stays empty until "Your Career" fills it.
function msCommunityOffline() {
  if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.getBuildProfile === 'function') {
    return API_CONFIG.getBuildProfile() === 'desktop';
  }
  return typeof window !== 'undefined' && window.GOB_BUILD_PROFILE === 'desktop';
}

async function loadCommunityLeaderboard(currentUsername) {
  if (msCommunityOffline()) return;
  const leaderboardData = await safeJsonFetch(API_CONFIG.buildUrl('/api/auth/leaderboard'), {
    headers: getAuthHeaders()
  });
  currentLeaderboardData = leaderboardData;
  renderCommunityLeaderboard(leaderboardData, currentUsername);
}

const ATL_LAST_VISIT_KEY = 'gob_atl_last_visit';
const ATL_POLL_MS = 20000;
const ATL_SLOT_COUNT = 8;

let atlSlots = [];
let atlBoardSignature = '';
let atlInitialLoadDone = false;
let atlPollTimer = null;
let atlCurrentUserId = '';

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

/**
 * One Around GOB slot -> one .agc card. Anything the payload does not carry is
 * omitted rather than derived; see reports/home-base-online-2026-09-29.md.
 */
function hbAroundCard(entry, showNew) {
  var last = entry.last_game || {};
  var teamName = safeText(entry.team_name, '');
  var wins = Number(entry.wins || 0);
  var losses = Number(entry.losses || 0);
  var haveScores = last.user_score != null && last.opp_score != null;
  return {
    userId: String(entry.user_id || ''),
    coach: safeText(entry.username, 'Coach'),
    isMe: !!(atlCurrentUserId && String(entry.user_id || '') === String(atlCurrentUserId)),
    isNew: !!showNew,
    // The slot now carries team_slug + asset_strategy, so a program (including a
    // Team Builder / custom one) loads its own banner art instead of falling back
    // to general art off the display name.
    bannerUrl: hbResolveBanner({
      slug: entry.team_slug,
      name: teamName,
      assetStrategy: entry.asset_strategy,
      primaryColor: entry.primary_color,
      secondaryColor: entry.secondary_color,
    }),
    team: teamName,
    record: wins + '-' + losses,
    rank: (entry.national_rank != null && entry.national_rank !== '') ? '#' + entry.national_rank : '',
    season: entry.current_season != null ? entry.current_season : null,
    week: entry.week != null ? entry.week : null,
    won: !!last.won,
    score: haveScores ? (Number(last.user_score) + '\u2013' + Number(last.opp_score)) : '',
    opponent: safeText(last.opponent, ''),
  };
}

/** Yours leads the grid; the rest keep the server's recency order. */
function hbAroundModel(slots, lastVisitMode) {
  var list = (Array.isArray(slots) ? slots : []).filter(Boolean);
  var cards = list.map(function (entry) {
    return hbAroundCard(entry, lastVisitMode && atlIsNewSinceLastVisit(entry.completed_at));
  });
  var mine = cards.filter(function (c) { return c.isMe; });
  var others = cards.filter(function (c) { return !c.isMe; });
  return mine.concat(others);
}

function hbAroundNewCount(slots) {
  return (Array.isArray(slots) ? slots : []).filter(function (entry) {
    return entry && !(atlCurrentUserId && String(entry.user_id || '') === String(atlCurrentUserId))
      && atlIsNewSinceLastVisit(entry.completed_at);
  }).length;
}

function atlRenderGrid(slots, options) {
  options = options || {};
  if (!window.GOBHomeBase) return;
  var cards = hbAroundModel(slots, !!options.lastVisitMode);
  var newCount = options.lastVisitMode ? hbAroundNewCount(slots) : 0;
  if (hbView) { hbView.around = cards; hbView.newCount = newCount; }
  window.GOBHomeBase.renderAround(cards, newCount);
}

function atlApplyBoardUpdate(nextSlots, opts) {
  opts = opts || {};
  var sig = atlBoardSig(nextSlots);
  if (sig === atlBoardSignature && !opts.force) return;
  atlSlots = nextSlots.slice();
  atlBoardSignature = sig;
  atlRenderGrid(atlSlots, { lastVisitMode: !!opts.lastVisitMode });
}

async function loadAroundTheLeague(options) {
  if (msCommunityOffline()) return;
  options = options || {};
  var data = await safeJsonFetch(API_CONFIG.buildUrl('/api/community/around-the-league'), {
    headers: getAuthHeaders(),
  });
  if (!data || !Array.isArray(data.slots)) return;

  var nextSlots = data.slots.slice(0, ATL_SLOT_COUNT);

  if (!atlInitialLoadDone) {
    atlInitialLoadDone = true;
    atlApplyBoardUpdate(nextSlots, { lastVisitMode: atlParseLastVisit() !== null });
    return;
  }
  if (options.poll) atlApplyBoardUpdate(nextSlots, { lastVisitMode: true });
}

function wireAroundTheLeaguePolling() {
  if (atlPollTimer || msCommunityOffline()) return;
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
  if (!grid || msCommunityOffline()) return;

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

// The Home Base leaderboard footer opens this; it has no button of its own.
function openLeadersByTeamModal() {
  var leadersByTeamModal = document.getElementById('leaders-by-team-modal');
  if (!leadersByTeamModal) return;
  leadersByTeamModal.classList.add('is-visible');
  leadersByTeamModal.setAttribute('aria-hidden', 'false');
  loadLeadersByTeam();
}

function wireLeadersByTeamModal() {
  var leadersByTeamModal = document.getElementById('leaders-by-team-modal');
  var leadersByTeamClose = document.getElementById('leaders-by-team-close');
  var leadersByTeamBackdrop = document.getElementById('leaders-by-team-backdrop');

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
  const params = emptyParams();
  params.set('mode', 'franchise');
  params.set('active_resume', 'true');
  params.set('franchise_id', franchiseData.franchise_id);
  params.set('game_id', resume.game_id);
  // home/away = core identity names from the game doc; display params are chrome-only.
  params.set('home', resume.home_team_name || 'Home');
  params.set('away', resume.away_team_name || 'Away');
  if (resume.home_display_name) params.set('home_display', resume.home_display_name);
  if (resume.away_display_name) params.set('away_display', resume.away_display_name);
  params.set('home_id', resume.home_team_id || resume.home_team_name || 'Home');
  params.set('away_id', resume.away_team_id || resume.away_team_name || 'Away');
  params.set('team_id', franchiseData.user_team_object_id || franchiseData.user_team_id || '');
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
/**
 * Green rule (Ch7 decision 1): exactly one primary forward action on screen.
 * A program with a game in progress takes it as "Resume Game"; otherwise the
 * most recently played program takes it as "Enter". No programs, nothing green.
 */
function hbGreenFranchiseId(bySlot) {
  const present = Object.keys(bySlot)
    .map(function (k) { return bySlot[k]; })
    .filter(Boolean);
  if (!present.length) return '';

  const live = present.find(function (franchiseData) {
    const runtime = slotRuntimeById[String(franchiseData.franchise_id)];
    return !!(runtime && runtime.activeGameResume);
  });
  if (live) return String(live.franchise_id);

  const recent = present.find(function (franchiseData) {
    return mostRecentFranchiseId && String(franchiseData.franchise_id) === mostRecentFranchiseId;
  });
  if (recent) return String(recent.franchise_id);

  // No server hint (older deploy): /franchise/list is newest-first.
  const byListOrder = franchisesList.find(function (franchiseData) {
    return present.some(function (p) {
      return String(p.franchise_id) === String(franchiseData && franchiseData.franchise_id);
    });
  });
  return byListOrder ? String(byListOrder.franchise_id) : String(present[0].franchise_id);
}

/** One occupied slot -> one .door. Records the runtime the click handlers read. */
function hbDoorModel(franchiseData, teamDoc, commandCenterData, greenId) {
  const franchiseId = String(franchiseData.franchise_id || '');
  const teamName = safeText(franchiseData.user_team_id, 'Program');

  const activeGameResume = commandCenterData && commandCenterData.active_game_resume
    && commandCenterData.active_game_resume.status === 'stoppage_anchor'
    ? commandCenterData.active_game_resume
    : null;
  const cpuSimResume = commandCenterData && cpuSimNeedsResume(commandCenterData.cpu_sim_resume)
    ? commandCenterData.cpu_sim_resume
    : null;

  slotRuntimeById[franchiseId] = {
    franchise: franchiseData,
    commandCenter: commandCenterData || null,
    activeGameResume: activeGameResume,
    cpuSimResume: cpuSimResume,
  };

  const week = safeNumber(franchiseData.week, 1);
  const nextOpponent = deriveNextOpponent(commandCenterData, teamName, franchiseData);
  let nextLabel = nextOpponent === 'TBD' ? '' : nextOpponent;
  if (activeGameResume) {
    const away = String(activeGameResume.user_team_side || 'home').toLowerCase() === 'away';
    // Core *_team_name stays for URL keys; chrome uses *_display_name.
    nextLabel = (away ? '@ ' : 'vs ')
      + (away
        ? (activeGameResume.home_display_name || activeGameResume.home_team_name || 'Opponent')
        : (activeGameResume.away_display_name || activeGameResume.away_team_name || 'Opponent'));
  }

  const rank = deriveRank(teamDoc, commandCenterData);
  return {
    franchiseId: franchiseId,
    name: teamName,
    bannerUrl: resolveFranchiseSlotBanner(franchiseData),
    season: deriveCurrentSeason(commandCenterData),
    week: week,
    nextOpponent: nextLabel,
    record: deriveRecord(commandCenterData, teamName, franchiseData),
    rank: rank && rank !== '-' ? '#' + rank : '',
    gameInProgress: !!activeGameResume,
    isGreen: franchiseId === greenId,
    isLastPlayed: franchiseId === greenId,
  };
}

function assignFranchisesToSlots(franchises) {
  const maxSlots = maxFranchiseSlots || 2;
  const bySlot = {};
  for (let s = 1; s <= maxSlots; s++) bySlot[s] = null;

  const list = Array.isArray(franchises) ? franchises.slice() : [];
  const unassigned = [];
  list.forEach(function (franchiseData) {
    const slot = Number(franchiseData && franchiseData.home_slot);
    if (slot >= 1 && slot <= maxSlots && !bySlot[slot]) {
      bySlot[slot] = franchiseData;
    } else {
      unassigned.push(franchiseData);
    }
  });
  unassigned.forEach(function (franchiseData) {
    for (let s = 1; s <= maxSlots; s++) {
      if (!bySlot[s]) {
        bySlot[s] = franchiseData;
        return;
      }
    }
  });
  return bySlot;
}

function renderFranchiseSlots(franchises, teamsById, teamsByName, commandCenterById) {
  Object.keys(slotRuntimeById).forEach(function (k) { delete slotRuntimeById[k]; });

  const bySlot = assignFranchisesToSlots(franchises);

  // Two passes: the doors need every runtime recorded before the green rule can
  // ask which program has a game in progress.
  const doorInputs = {};
  for (let slot = 1; slot <= maxFranchiseSlots; slot++) {
    const franchiseData = bySlot[slot];
    if (!franchiseData) continue;
    // Join by ObjectId first (Team Builder: user_team_id is display name, not core).
    const objectId = franchiseData.user_team_object_id ? String(franchiseData.user_team_object_id) : '';
    const teamName = safeText(franchiseData.user_team_id, '');
    const replacedName = safeText(franchiseData.team_builder_replaced_name, '');
    doorInputs[slot] = {
      franchiseData: franchiseData,
      teamDoc: (objectId && teamsById[objectId]) || teamsByName[replacedName] || teamsByName[teamName] || null,
      commandCenterData: commandCenterById[String(franchiseData.franchise_id)] || null,
    };
    hbDoorModel(franchiseData, doorInputs[slot].teamDoc, doorInputs[slot].commandCenterData, '');
  }

  const greenId = hbGreenFranchiseId(bySlot);
  const slots = [];
  for (let slot = 1; slot <= maxFranchiseSlots; slot++) {
    const input = doorInputs[slot];
    slots.push(input
      ? hbDoorModel(input.franchiseData, input.teamDoc, input.commandCenterData, greenId)
      : null);
  }

  hbView = {
    online: !msCommunityOffline(),
    accountName: hbUsername || 'Coach',
    slots: slots,
    career: hbCareer,
    careerZone: hbCareerZone,
    trophyCaseHref: HB_TROPHY_CASE_HREF,
    around: (hbView && hbView.around) || [],
    newCount: (hbView && hbView.newCount) || 0,
    leaderboard: (hbView && hbView.leaderboard) || { rows: [], view: currentLeaderboardView, unit: 'GP' },
  };
  if (window.GOBHomeBase) window.GOBHomeBase.render(hbView);
}

function goToFranchiseCommandCenter(franchiseId) {
  const runtime = franchiseId ? slotRuntimeById[String(franchiseId)] : null;
  const franchiseData = runtime && runtime.franchise;
  if (franchiseData && franchiseData.franchise_id) {
    const resumeUrl = buildActiveGameCourtUrl(franchiseData, runtime.activeGameResume);
    if (resumeUrl) {
      // Same hydrate producer as FCC — before court reconstructs chrome from URL/sim.
      try {
        if (typeof hydrateTeamBuilderVisualFromFranchisePayload === 'function') {
          hydrateTeamBuilderVisualFromFranchisePayload(
            runtime.commandCenter || franchiseData,
            franchiseData.franchise_id
          );
        }
      } catch (e) { /* court will re-fetch */ }
      console.warn('[MODE-RESUME-CLIENT] route resume', {
        franchise_id: franchiseData.franchise_id,
        game_id: runtime.activeGameResume && runtime.activeGameResume.game_id,
        url: resumeUrl,
      });
      navigateFromModeSelect(resumeUrl);
      return;
    }
    if (runtime.cpuSimResume) {
      const params = emptyParams();
      params.set('franchise_id', franchiseData.franchise_id);
      params.set('finish_cpu_sims', '1');
      if (runtime.cpuSimResume.week) params.set('week', String(runtime.cpuSimResume.week));
      console.warn('[MODE-RESUME-CLIENT] route cpu sim recovery', {
        franchise_id: franchiseData.franchise_id,
        week: runtime.cpuSimResume.week,
      });
      navigateFromModeSelect('./franchise-command-center.html?' + params.toString());
      return;
    }
    console.warn('[MODE-RESUME-CLIENT] route fcc', {
      franchise_id: franchiseData.franchise_id,
    });
    navigateFromModeSelect('./franchise-command-center.html?franchise_id=' + encodeURIComponent(franchiseData.franchise_id));
    return;
  }
  console.warn('[MODE-RESUME-CLIENT] route franchise select', { franchiseId: franchiseId });
  navigateFromModeSelect('./franchise-select-team.html');
}

/** Tutorial alert "I'll do this later" for Player Attributes → FCC when a franchise exists. */
function getFranchiseCommandCenterUrlForLater() {
  const sorted = franchisesList.slice().sort(function (a, b) {
    const sa = Number(a && a.home_slot) || 99;
    const sb = Number(b && b.home_slot) || 99;
    return sa - sb;
  });
  const currentFranchise = sorted[0] || null;
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

function closeAllSlotMenus() {
  if (window.GOBHomeBase) window.GOBHomeBase.closeConfirm();
}

/**
 * Ch7 decision 7: delete is a red-outline confirm, never a red button in the
 * slot. The copy is explicit that trophies and season history survive.
 */
function openDeleteFranchiseModal(franchiseData) {
  pendingDeleteFranchise = franchiseData || null;
  if (!pendingDeleteFranchise || !window.GOBHomeBase) return;
  const teamName = safeText(pendingDeleteFranchise.user_team_id, 'this program');
  const slot = safeNumber(pendingDeleteFranchise.home_slot, 1);
  const week = pendingDeleteFranchise.week != null ? pendingDeleteFranchise.week : '?';
  const season = pendingDeleteFranchise.current_season != null ? pendingDeleteFranchise.current_season : '?';
  window.GOBHomeBase.openConfirm({
    title: 'Delete ' + teamName + '?',
    bodyHtml: 'Slot ' + escapeHtml(String(slot).padStart(2, '0'))
      + ' <em>· Season ' + escapeHtml(season) + ', Week ' + escapeHtml(week) + '</em>. '
      + 'This deletes the program and every save in this slot, and cannot be undone. '
      + 'Your trophies and season history stay in your Trophy Case.',
    cancelLabel: 'Cancel',
    confirmLabel: 'Delete Program',
  });
}

function closeDeleteFranchiseModal() {
  pendingDeleteFranchise = null;
  if (window.GOBHomeBase) window.GOBHomeBase.closeConfirm();
}

function openSlotsFullModal() {
  if (!window.GOBHomeBase) return;
  window.GOBHomeBase.openConfirm({
    title: 'Both slots are full',
    bodyHtml: 'You already coach two programs. Delete one to start another.',
    cancelLabel: 'OK',
  });
}

function closeSlotsFullModal() {
  if (window.GOBHomeBase) window.GOBHomeBase.closeConfirm();
}

function goToNewFranchise(homeSlot) {
  const slot = Number(homeSlot);
  const q = (slot === 1 || slot === 2) ? ('?home_slot=' + encodeURIComponent(String(slot))) : '';
  navigateFromModeSelect('./franchise-select-team.html' + q);
}

function startNewFranchiseFlow(homeSlot) {
  playSound('click-beep.wav');
  if (franchisesList.length >= maxFranchiseSlots) {
    openSlotsFullModal();
    return;
  }
  // Fill the chosen empty slot — do not delete any existing franchise.
  goToNewFranchise(homeSlot);
}

async function confirmDeleteFranchise() {
  const target = pendingDeleteFranchise;
  if (!target || !target.franchise_id) {
    closeDeleteFranchiseModal();
    return;
  }
  const franchiseId = String(target.franchise_id);
  // Same click as the slot "Delete Franchise" control.
  playSound('click-beep.wav');
  closeDeleteFranchiseModal();
  if (window.PageLoadOverlay && typeof window.PageLoadOverlay.show === 'function') {
    window.PageLoadOverlay.show('Deleting franchise…');
  }
  try {
    const res = await fetch(
      API_CONFIG.buildUrl('/franchise/' + encodeURIComponent(franchiseId)),
      { method: 'DELETE', headers: getAuthHeaders() }
    );
    // 404 = already gone. The server is idempotent now, but a client running a
    // cached bundle against an older deploy can still see one, and "not found"
    // on a delete means the delete succeeded — treat it as success, not failure.
    if (!res.ok && res.status !== 404) {
      // Indeterminate, NOT known-failed: the request may have been abandoned by an
      // edge timeout while the server completed the wipe. Reload so the slot list
      // is re-read from the source of truth instead of leaving a stale card that
      // navigates into a dead franchise_id. Local franchise keys are deliberately
      // NOT cleared here — complete_week_pending / eog_pgpc_snapshot are resume
      // state, and dropping them on a franchise that survived would lose a week.
      console.warn('[mode-select] delete franchise unconfirmed:', res.status);
      alert('That delete did not confirm. Reloading — if the franchise is still listed, try again.');
      window.location.reload();
      return;
    }
    if (window.FranchiseLS && typeof window.FranchiseLS.clearAllForFranchise === 'function') {
      window.FranchiseLS.clearAllForFranchise(franchiseId);
    }
    // Reload lands on mode select; initial loading panel covers the refresh.
    window.location.reload();
  } catch (e) {
    // Network error or a fetch aborted by the user refreshing mid-delete. The
    // server does not cancel with the client, so the wipe may well have landed —
    // same indeterminate handling as above.
    console.warn('[mode-select] delete franchise error:', e);
    alert('That delete did not confirm. Reloading — if the franchise is still listed, try again.');
    window.location.reload();
  }
}

/** homeBase.js owns the DOM and the keyboard; these are the data-side answers. */
function wireHomeBase() {
  if (!window.GOBHomeBase || !homeBaseRoot) return;
  window.GOBHomeBase.init(homeBaseRoot, {
    onEnter: function (franchiseId) {
      playSound('click-strong.wav');
      goToFranchiseCommandCenter(franchiseId);
    },
    onNewFranchise: function (slotIndex) {
      startNewFranchiseFlow(slotIndex);
    },
    onRequestDelete: function (slotIndex) {
      playSound('click-beep.wav');
      const slot = hbView && hbView.slots ? hbView.slots[Number(slotIndex) - 1] : null;
      const runtime = slot ? slotRuntimeById[String(slot.franchiseId)] : null;
      if (runtime && runtime.franchise) openDeleteFranchiseModal(runtime.franchise);
    },
    onConfirmDelete: confirmDeleteFranchise,
    onTabChange: function (tab) {
      // Opening Around GOB clears the badge: the results have now been seen.
      if (tab === 'ag') atlPersistLastVisit();
    },
    onLeaderboardView: function (view) {
      setLeaderboardView(view);
      renderCommunityLeaderboard(currentLeaderboardData, hbUsername);
    },
    onLeadersByTeam: openLeadersByTeamModal,
    onSettings: function () {
      import('/js/shared/gobSettings.js')
        .then(function (mod) { mod.toggle(); })
        .catch(function () {});
    },
    onLogout: logOutOfGob,
  });
}

async function logOutOfGob() {
  // Shared helper attaches the bearer token before clearing it, so the server
  // actually revokes the session. It clears the local token and never throws.
  try { await API_CONFIG.logout(); } catch (e) {}
  navigateFromModeSelect('/login.html');
}

document.addEventListener('DOMContentLoaded', async function () {
  const isDesktop = typeof window !== 'undefined' && window.GOB_BUILD_PROFILE === 'desktop';
  const authToken = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const authUser = typeof localStorage !== 'undefined' ? localStorage.getItem('auth_user') : null;
  let currentUsername = '';

  if (!isDesktop && (!authToken || !authUser)) {
    redirectToLogin();
    return;
  }

  try {
    if (isDesktop) {
      currentUsername = 'Coach';
      atlCurrentUserId = 'local-desktop-user';
    } else {
      const user = JSON.parse(authUser);
      currentUsername = user.username || user.email || '';

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
        const stored = JSON.parse(authUser);
        stored.username = meData.username;
        localStorage.setItem('auth_user', JSON.stringify(stored));
      }
    }
  } catch (e) {
    // Leaving the page aborts this fetch. A restored snapshot must not be
    // sent to login, and must not stay on the session check.
    if (e && e.name === 'AbortError') return;
    console.error('[AUTH] Mode select auth validation failed:', e);
    redirectToLogin();
    return;
  }

  hbUsername = currentUsername;
  wireAlphaBanner();
  wireHomeBase();
  // Nothing is on screen yet; paint the frame so the two zones exist before the
  // slot and community payloads land.
  renderFranchiseSlots([], {}, {}, {});

  try {
    modeSelectMusic = new Audio('/sounds/Championship_Gridlock.mp4');
    modeSelectMusic.loop = true;
    modeSelectMusic.volume = MODE_SELECT_MUSIC_VOLUME;
    import('/js/shared/uiSfx.js').then(function (m) {
      var apply = function () {
        if (modeSelectMusic) modeSelectMusic.volume = m.outputVolume(MODE_SELECT_MUSIC_VOLUME, 'music');
      };
      apply();
      m.subscribeAudio(apply);
    }).catch(function () {});
    modeSelectMusic.play().catch(function () {});
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

  // Desktop has no community backend: no community requests. The right zone is
  // "Your Career", fed only by GET /franchise/coach-career over loopback, and the
  // loader waits on it. Online, the loader waits on the first community view (never
  // on the 20 s poll) plus the career strip.
  let rightZoneFirstView;
  if (msCommunityOffline()) {
    rightZoneFirstView = loadCoachCareer();
  } else {
    setLeaderboardView('geek_points');
    rightZoneFirstView = Promise.all([
      loadCommunityLeaderboard(currentUsername),
      loadAroundTheLeague(),
      loadCoachCareer(),
    ]);
    wireAroundTheLeaguePolling();
    wireLeadersByTeamModal();
  }

  const headers = getAuthHeaders();
  const listData = await safeJsonFetch(API_CONFIG.buildUrl('/franchise/list'), { headers: headers });
  franchisesList = (listData && Array.isArray(listData.franchises)) ? listData.franchises : [];
  maxFranchiseSlots = (listData && listData.max) ? Number(listData.max) || 2 : 2;
  mostRecentFranchiseId = safeText(listData && listData.most_recent_franchise_id, '');

  const teamsData = await safeJsonFetch(API_CONFIG.buildUrl('/teams'), { headers: headers }) || [];
  const teamsByName = {};
  const teamsById = {};
  teamsData.forEach(function (team) {
    if (!team) return;
    if (team.name) teamsByName[team.name] = team;
    const tid = team.object_id || team._id || team.id || team.team_object_id;
    if (tid) teamsById[String(tid)] = team;
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

  renderFranchiseSlots(franchisesList, teamsById, teamsByName, commandCenterById);
  await settledOrAfter(rightZoneFirstView, COMMUNITY_FIRST_VIEW_TIMEOUT_MS);
  revealModeSelect();
});

window.addEventListener('pageshow', function (event) {
  // A bfcache restore re-runs no script, so nothing would ever drop the loader.
  if (event.persisted) revealModeSelect();
});
