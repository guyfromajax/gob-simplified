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

// Returns { data, status }. status is the HTTP status, or 0 when the request never
// got a response. Callers that need to tell "this franchise is gone" (404) apart
// from "the network hiccuped" (0) use this; fetchJSON keeps the old null contract
// for the ~40 call sites that only care whether they got a payload. A shared
// module-level status would race — init fires several un-awaited loads.
async function fetchJSONWithStatus(url) {
  try {
    const res = await fetch(url, { headers: API_CONFIG.getAuthHeaders() });
    if (res.status === 401 || res.status === 403) {
      if (typeof AccessDenied !== 'undefined' && AccessDenied.checkAccessDenied) {
        AccessDenied.checkAccessDenied(res);
      }
      return { data: null, status: res.status };
    }
    if (!res.ok) {
      console.error('Failed loading', url, res.status);
      return { data: null, status: res.status };
    }
    return { data: await res.json(), status: res.status };
  } catch (err) {
    console.error('Failed loading', url, err);
    return { data: null, status: 0 };
  }
}

async function fetchJSON(url) {
  return (await fetchJSONWithStatus(url)).data;
}

// The read right after a week advance lands on a busy server (or a deploy
// cutover). Advance stays off until it succeeds, so ride out a transient miss.
const FCC_DATA_RETRY_DELAYS_MS = [1000, 2000, 4000];

async function fetchCommandCenterData() {
  let result = await fetchJSONWithStatus(fccCommandCenterDataUrl(franchiseId));
  for (const delay of FCC_DATA_RETRY_DELAYS_MS) {
    if (result.data || [401, 403, 404].includes(result.status)) break;
    await new Promise((resolve) => setTimeout(resolve, delay));
    result = await fetchJSONWithStatus(fccCommandCenterDataUrl(franchiseId));
  }
  return result;
}

// Profiling stays available as ?cc_profile=1. The Office load itself does not request it.
function fccProfileSuffix() {
  try {
    return new URLSearchParams(window.location.search).get('cc_profile') === '1' ? '&profile=1' : '';
  } catch (error) {
    return '';
  }
}

function fccCommandCenterDataUrl(franchiseId) {
  return `${API_CONFIG.buildUrl('/franchise/command-center/data')}?franchise_id=${franchiseId}${fccProfileSuffix()}`;
}

function fccTeamDataUrl() {
  return `${API_CONFIG.buildUrl('/franchise/team-data')}?franchise_id=${encodeURIComponent(franchiseId)}&team_id=${encodeURIComponent(userTeamId)}`;
}

function fccRosterUrl() {
  return `${API_CONFIG.buildUrl(`/roster/${encodeURIComponent(userTeamId)}`)}?franchise_id=${encodeURIComponent(franchiseId)}${fccProfileSuffix()}`;
}

function fccPlaybooksUrl() {
  const params = emptyParams();
  params.set('mode', 'franchise');
  params.set('franchise_id', franchiseId);
  params.set('team_id', userTeamId);
  return `${API_CONFIG.buildUrl('/api/playbooks')}?${params.toString()}`;
}

// A franchise_id that 404s is a franchise that no longer exists — almost always one
// the user just deleted, where the delete landed server-side but the client did not
// see the confirmation. Without this the FCC silently bailed out of init and left
// the empty shell (header "--", every card stuck on "In Development") with no
// explanation. Rendered above #page-load-overlay (z-index 999999) so it survives
// the overlay hide in init's finally block.
function showFranchiseGoneNotice() {
  if (document.getElementById('fcc-franchise-gone')) return;
  const panel = document.createElement('div');
  panel.id = 'fcc-franchise-gone';
  panel.setAttribute('role', 'alert');
  // Tokens resolve here because the page is html.gob. The button is a neutral plate:
  // leaving a dead franchise is not Advance, so it is not green.
  panel.style.cssText =
    'position:fixed;inset:0;z-index:1000000;background:var(--bg);' +
    'display:flex;flex-direction:column;align-items:center;justify-content:center;' +
    'gap:var(--space-18);padding:var(--space-24);text-align:center;';
  panel.innerHTML =
    '<div style="font-family:var(--font-display);' +
    'font-size:var(--fs-36);letter-spacing:var(--tracking-3);color:var(--text-100);">This Franchise No Longer Exists</div>' +
    '<div style="font-family:var(--font-body);font-size:var(--fs-15);line-height:1.5;' +
    'color:var(--white-72);max-width:440px;">It was deleted, so there is nothing left to load. ' +
    'Your other program slot is untouched.</div>' +
    '<button type="button" id="fcc-franchise-gone-back" style="min-width:138px;min-height:42px;' +
    'padding:var(--space-10) var(--space-18);border:1px solid var(--white-28);border-radius:var(--radius-10);' +
    'background:var(--white-10);color:var(--text-100);cursor:pointer;' +
    'font-family:var(--font-display);font-size:var(--fs-14);font-weight:var(--fw-bold);' +
    'letter-spacing:var(--tracking-2);">Back To Home Base</button>';
  document.body.appendChild(panel);
  const backBtn = document.getElementById('fcc-franchise-gone-back');
  if (backBtn) {
    backBtn.addEventListener('click', () => {
      window.location.href = '/mode-select.html';
    });
  }
  // Stale local keys for a franchise that is provably gone are safe to drop, and
  // leaving them lets a later screen re-adopt a dead id.
  if (window.FranchiseLS && typeof window.FranchiseLS.clearAllForFranchise === 'function') {
    try { window.FranchiseLS.clearAllForFranchise(franchiseId); } catch (e) {}
  }
}

// --- Season-load failure state -------------------------------------------------
// When fetchCommandCenterData() exhausts its retries on a transient failure
// (network/offline -> status 0, a 5xx, or a 429 that never cleared) the Office
// used to be left blank with a dead, disabled Advance and no explanation. Instead
// we render the shared design-system error card (.gob-view-error / .gob-view-retry
// in css/gob-views.css — no new styling, nothing added to the frozen
// franchise-command-center.css) in the Office main area, and tell Advance why it
// is disabled. Retry re-runs the full load (init) with the same retry policy.
let fccSeasonRetrying = false;
const FCC_ADVANCE_LOAD_FAILED_LABEL = "Season didn't load: retry above";

function seasonLoadCauseLine(status) {
  if (status === 0) return 'Connection lost.';
  if (status === 429) return 'The server is busy.';
  if (typeof status === 'number' && status >= 500) return 'Server error.';
  return '';
}

// Advance stays disabled, LOOKS disabled (inline opacity/cursor — .hero-btn has no
// :disabled rule and its stylesheet is frozen), plays no sound (a disabled button
// never dispatches click, so its data-sfx hook can't fire), and says why.
function markAdvanceSeasonLoadFailed() {
  const btn = document.getElementById('play-now');
  if (!btn) return;
  btn.disabled = true;
  btn.setAttribute('aria-disabled', 'true');
  btn.setAttribute('aria-label', FCC_ADVANCE_LOAD_FAILED_LABEL);
  btn.setAttribute('title', FCC_ADVANCE_LOAD_FAILED_LABEL);
  btn.style.opacity = '0.4';
  btn.style.cursor = 'not-allowed';
}

function clearAdvanceSeasonLoadFailed() {
  const btn = document.getElementById('play-now');
  if (!btn) return;
  btn.removeAttribute('aria-disabled');
  btn.removeAttribute('aria-label');
  btn.removeAttribute('title');
  btn.style.opacity = '';
  btn.style.cursor = '';
}

function showSeasonLoadError(status) {
  markAdvanceSeasonLoadFailed();
  const host = document.getElementById('office-root');
  if (!host) return;
  host.setAttribute('data-office-state', 'error');
  host.setAttribute('aria-busy', 'false');

  const card = document.createElement('div');
  card.className = 'gob-view-error';
  card.setAttribute('role', 'alert');

  const title = document.createElement('p');
  const strong = document.createElement('strong');
  strong.textContent = "Couldn't load your season";
  title.appendChild(strong);
  card.appendChild(title);

  const cause = seasonLoadCauseLine(status);
  if (cause) {
    const line = document.createElement('p');
    line.textContent = cause;
    card.appendChild(line);
  }

  const retry = document.createElement('button');
  retry.type = 'button';
  retry.className = 'gob-view-retry';
  retry.textContent = 'Retry';
  retry.setAttribute('data-sfx', 'SFX_SELECT'); // neutral select tick; not Advance
  retry.addEventListener('click', () => {
    if (fccSeasonRetrying) return; // no double-submit
    fccSeasonRetrying = true;
    retry.disabled = true;
    retry.textContent = 'Retrying…';
    host.setAttribute('aria-busy', 'true');
    Promise.resolve()
      .then(() => init()) // re-run the full load; same retry policy
      .catch((err) => { console.error('[fcc] season retry failed', err); })
      .finally(() => { fccSeasonRetrying = false; });
  });
  card.appendChild(retry);

  host.replaceChildren(card);
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
      if (window.FranchiseLS) {
        window.FranchiseLS.clearPendingAndEog(franchiseId);
      } else {
        localStorage.removeItem('franchise_complete_week_pending');
        localStorage.removeItem('franchise_eog_pgpc_snapshot');
      }
    } catch (_) {}
    const refreshed = await fetchJSON(fccCommandCenterDataUrl(franchiseId));
    return refreshed || topData;
  } catch (err) {
    console.error('[FCC CPU SIM RESUME] Could not finish computer games:', err);
    alert('Could not finish computer games. Please try again.');
    return topData;
  }
}

let franchiseId = null;
const _urlFidEarly = franchiseCtx() ? franchiseCtx().get('franchise_id') : null;
const userTeamName = (_urlFidEarly && window.FranchiseLS)
  ? (window.FranchiseLS.get(_urlFidEarly, 'user_team') || '')
  : '';
// ✅ SS&S: Store team ObjectId for consistent navigation
let userTeamId = null; // Will be resolved from command center data or URL params
let userTeamNameForLeaders = null; // Store user team name for leaderboard highlighting
let userConference = null; // User team's conference (for Stats/Traits scope)
let userRegion = null;    // User team's region (for Stats/Traits scope)
let teamColorCache = null; // Cache for team primary colors
let teamMetaByNameCache = null;
const leadersDataCache = new Map();
let teamStatsDataCache = null;
let teamTraitsDataCache = null;
let leanRecruitsDataCache = [];
let signedRecruitsDataCache = [];
let currentWeekInviteRecruitCache = null;
let newLeanRecruitIdsCache = [];
let recruitTeamNameMapCache = {};
let fccTeamStatsSummaryCache = null;
let commandCenterTopDataCache = null;
// One page-lifecycle promise shared by restored tabs. URL tab restoration is
// synchronous, while FCC identity/top-data hydration is asynchronous; renderers
// that require that state must await this instead of racing init() or polling.
let fccInitializationPromise = null;
let playbooksWeekSavedCache = null;
let fccPlaybooksSummaryCache = null;
let userRosterPlayersCache = [];
let userRosterDataCache = null;
let homeTeamLeaderCategory = 'PTS';
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

window.addEventListener('pageshow', (event) => {
  maybeRefreshPlaybooksButtonState();
  if (event && event.persisted) void revalidateRestoredFcc();
});

// The fields the Advance step and the week header are computed from.
function fccAdvanceKey(data) {
  if (!data) return '';
  const wire = data.recruiting_wire || {};
  const resume = data.cpu_sim_resume || {};
  return JSON.stringify([
    data.current_season, data.week, data.session_type, !!data.training_completed,
    !!data.cut_required, wire.board_saved_week, !!wire.week_35_orders_submitted,
    resume.status || null, !!data.season_complete,
  ]);
}

// A back-forward-cache restore is the old document. gobNav reloads the returns it
// has markers for; any other restore checks the server before Advance is live, so
// the FCC never offers a step from a week that has already moved on.
async function revalidateRestoredFcc() {
  if (window.GOBNav && typeof window.GOBNav.isReloading === 'function' && window.GOBNav.isReloading()) return;
  const shown = window.__gobCommandCenterData;
  if (!franchiseId || !shown) return;
  const wasDisabled = playNowBtn.disabled;
  playNowBtn.disabled = true;
  const url = fccCommandCenterDataUrl(franchiseId);
  let fresh = null;
  try {
    fresh = window.GOBStore && typeof window.GOBStore.revalidate === 'function'
      ? await window.GOBStore.revalidate(url, { headers: API_CONFIG.getAuthHeaders() })
      : await fetchJSON(url);
  } catch (err) {
    fresh = null;
  }
  if (!fresh || fccAdvanceKey(fresh) !== fccAdvanceKey(shown)) {
    if (window.PageLoadOverlay && window.PageLoadOverlay.show) window.PageLoadOverlay.show();
    window.location.replace(window.location.href);
    return;
  }
  playNowBtn.disabled = wasDisabled;
}

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
      rosterData: userRosterDataCache || null,
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
  userRosterDataCache = window.FccRosterData.fromSessionCache(cached);
  userRosterPlayersCache = userRosterDataCache.players;
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
  userRosterDataCache = null;
  homeOpponentRosterCache.clear();
  invalidateHomeWeekSensitiveCaches();
}

function publishFccUserTeam(teamId) {
  if (!franchiseId || !window.GOBViews || typeof window.GOBViews.noteUserTeam !== 'function') return;
  window.GOBViews.noteUserTeam(franchiseId, teamId || '');
}

function teamIdFromCommandCenter(topData) {
  if (!topData) return '';
  const digest = topData.office_digest;
  return String(
    topData.team_id
    || topData.user_team_id
    || topData.user_team_object_id
    || (digest && (digest.user_team_id || digest.team_id))
    || ''
  );
}

function adoptAuthoritativeFccTeamId(topData) {
  const authoritativeTeamId = teamIdFromCommandCenter(topData);
  publishFccUserTeam(authoritativeTeamId);
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
    if (franchiseId && window.FranchiseLS) {
      window.FranchiseLS.set(franchiseId, 'user_team_id', userTeamId);
    }
    emitDisplayContextUpdate();
    return true;
  }

  return false;
}

function invalidateHomeWeekSensitiveCaches() {
  userScheduleDataCache = null;
  homeLastGameDataCache = null;
  homeOpponentRosterCache.clear();
}

function buildPlayerDetailUrl(playerId) {
  if (window.GOBTables) return window.GOBTables.viewHref({ tab: 'player-view', player_id: playerId });
  const qs = emptyParams();
  qs.set('id', playerId);
  if (franchiseId) qs.set('mode', 'franchise');
  if (franchiseId) qs.set('franchise_id', franchiseId);
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

/**
 * Tournament tier emblem value derivation (shared by Surface A + B).
 * Conference crest carries the conference number (user_conference, 1-16);
 * Region badge carries the region letter (user_region, A-H); National takes none.
 * Centralized here so the exact representation is one place to change.
 */
function conferenceEmblemValue(data) {
  const c = data ? data.user_conference : null;
  return (c === 0 || c) ? String(c) : '';
}
function regionEmblemValue(data) {
  const r = data ? data.user_region : null;
  if (r) return String(r).toUpperCase();
  // Fallback: derive the region letter from the conference (mirrors backend
  // ft._conference_to_region: conf 1-16 -> A-H via (conf-1)//2) so the Region
  // badge is never blank when the team doc lacks an explicit region field.
  const c = Number(data ? data.user_conference : NaN);
  if (Number.isInteger(c) && c >= 1 && c <= 16) {
    return String.fromCharCode(65 + Math.floor((c - 1) / 2));
  }
  return '';
}
function emblemValueForTier(tier, data) {
  if (tier === 'conference') return conferenceEmblemValue(data);
  if (tier === 'region') return regionEmblemValue(data);
  return null; // national: always 3 stars, no value
}

/**
 * Surface A — render the tier emblem lockup to the right of the team logo.
 * Only during an EOS week (tierForWeek 27-34); cleared otherwise so the logo
 * sits centered alone exactly as in the base layout.
 */
function renderFccHeaderEmblem(data) {
  const slot = document.getElementById('fcc-header-emblem');
  if (!slot || !window.GOBTierEmblem) return;
  const tier = window.GOBTierEmblem.tierForWeek(data && data.week);
  if (!tier) { slot.innerHTML = ''; return; }
  window.GOBTierEmblem.injectCss();
  const sz = window.GOBTierEmblem.EMBLEM_SIZING.fccFranchiseHeader;
  // The emblem alone: the top bar spells out the tournament and the round beside it.
  slot.innerHTML = window.GOBTierEmblem.renderEmblem({
    tier,
    value: emblemValueForTier(tier, data),
    size: sz.emblem,
  });
}

/**
 * Surface B — right-justified compact tier lockup in the Next/Last Game card
 * headers. Each card's emblem is derived from THAT game's own week, not the
 * current franchise week: a finished conference game keeps its conference emblem
 * through region week, and a regular-season game (week <= 26) shows no emblem.
 * The value inside the emblem is always the logged-in franchise's conf/region.
 */
function renderFccGameCardLockups() {
  if (!window.GOBTierEmblem) return;
  const data = commandCenterTopDataCache || {};
  renderOneGameCardLockup('home-next-game-lockup', data, data.next_game_summary);
  renderOneGameCardLockup('home-last-game-lockup', data, data.last_game_summary);
}

function renderOneGameCardLockup(slotId, data, gameSummary) {
  const el = document.getElementById(slotId);
  if (!el) return;
  const tier = window.GOBTierEmblem.tierForWeek(gameSummary ? gameSummary.week : null);
  if (!tier) { el.innerHTML = ''; return; }
  window.GOBTierEmblem.injectCss();
  const sz = window.GOBTierEmblem.EMBLEM_SIZING.fccGameCardHeader;
  el.innerHTML = window.GOBTierEmblem.renderLockup({
    tier,
    value: emblemValueForTier(tier, data),
    size: sz.emblem,
    l1: sz.labelL1,
    l2: sz.labelL2,
    variant: 'stack'
  });
}

function resolveFccTeamBanner(data) {
  if (!data) return '/images/teams/general/general_banner_primary.jpg';
  // Visual must already be hydrated from the franchise payload (memory), not LS.
  if (typeof getTeamAssetPath === 'function') {
    return getTeamAssetPath(data.team, 'banner_primary');
  }
  return '/images/teams/general/general_banner_primary.jpg';
}

// `warm` is the session-cache paint behind the overlay. That copy can be from an
// older week (a late write after the week advanced), so it never reaches the
// shared command-center data or the shell's week: Advance reads those.
function populateTop(data, { warm = false } = {}) {
  if (!data) return;
  const formattedTeam = formatTeamName(data.team);
  const logoEl = document.getElementById('team-logo');
  if (logoEl) {
    logoEl.alt = formattedTeam;
    logoEl.title = formattedTeam;
  }
  const topId = document.getElementById('gob-top-id');
  if (topId) topId.setAttribute('aria-label', formattedTeam);
  // Hydrate from franchise payload — FranchiseLS is cache only.
  const visual =
    typeof hydrateTeamBuilderVisualFromFranchisePayload === 'function'
      ? hydrateTeamBuilderVisualFromFranchisePayload(
          data,
          typeof franchiseId !== 'undefined' ? franchiseId : null
        )
      : null;
  if (window.FranchiseLS && typeof franchiseId !== 'undefined' && franchiseId) {
    window.FranchiseLS.setTeamContext(franchiseId, {
      teamName: data.team,
      primaryColor: data.primary_color,
    });
  }
  const logoSrc = resolveFccTeamBanner(data);
  document.getElementById('team-logo').src = logoSrc;
  renderFccHeaderEmblem(data);
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
  if (!warm) {
    window.__gobCommandCenterData = data;
    if (window.GOBShell && typeof window.GOBShell.syncTop === 'function') window.GOBShell.syncTop(data);
  }
  console.log('Team logo URL:', logoSrc);

  const abbr = teamMap[formattedTeam];
  const sammyEl = document.getElementById('coach-sammy');
  const dukeEl = document.getElementById('coach-duke');
  if (typeof getTeamCoachAssetPath === 'function') {
    const sammySrc = getTeamCoachAssetPath(data.team, 'Sammy', visual || undefined);
    const dukeSrc = getTeamCoachAssetPath(data.team, 'Duke', visual || undefined);
    if (sammyEl) {
      if (sammySrc) sammyEl.src = sammySrc;
      else sammyEl.removeAttribute('src');
    }
    if (dukeEl) {
      if (dukeSrc) dukeEl.src = dukeSrc;
      else dukeEl.removeAttribute('src');
    }
  } else if (abbr) {
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
  if (!standingsDataCache?.standings?.length || !userTeamId) return;
  const teamEntry = standingsDataCache.standings.find((team) => String(team.team_id || '') === String(userTeamId));
  if (!teamEntry) return;
  const wins = Number(teamEntry.W || 0);
  const losses = Number(teamEntry.L || 0);
  recordLabelEl.textContent = `Record: ${wins}-${losses}`;
  if (window.GOBShell && typeof window.GOBShell.syncRecord === 'function') window.GOBShell.syncRecord();
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
  if (!franchiseId || !window.FranchiseLS) return;
  try {
    const teamName = String(topData?.team || '').trim();
    const teamPrimaryColor = normalizeHexColor(topData?.primary_color);
    window.FranchiseLS.setTeamContext(franchiseId, {
      teamName: teamName || undefined,
      primaryColor: teamPrimaryColor || undefined,
      clearPrimaryColor: !teamPrimaryColor,
    });
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
  if (window.GOB_BUILD_PROFILE === 'desktop') {
    applyFccDisplayColor('default');
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

function standingsTeamLabel(t) {
  // Render chrome; identity stays on t.name / t.team_id.
  return (t && (t.display_name || t.name)) || '';
}

function buildFranchiseTeamPageUrl(teamId, teamName, returnTab) {
  if (window.GOBTables) return window.GOBTables.rosterHref(franchiseId, teamId, teamName, returnTab);
  const owner = new URLSearchParams(window.location.search).get('team_id') || teamId;
  const params = new URLSearchParams();
  params.set('mode', 'franchise');
  if (franchiseId) params.set('franchise_id', franchiseId);
  params.set('team_id', owner);
  if (teamId) params.set('roster_team_id', teamId);
  if (teamName) params.set('team_name', teamName);
  if (returnTab) params.set('return_tab', returnTab);
  params.set('origin', 'league');
  return '/team-roster-view.html?' + params.toString();
}

// The League › Standings view draws the table. This keeps the top-bar record and the
// team id → name map current.
function renderStandings(data) {
  if (!data) return;
  const list = data.standings || [];
  updateTopRecordLabel();
  list.forEach(t => { teamIdNameMap[t.team_id] = standingsTeamLabel(t); });
}

function escapeHomeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatConferenceShortLabel(conference) {
  const numericConference = Number(conference);
  if (!Number.isInteger(numericConference) || numericConference < 1 || numericConference > 16) return '';
  const regionLetter = String.fromCharCode(65 + Math.floor((numericConference - 1) / 2));
  return `${regionLetter}${numericConference}`;
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

function buildRecruitingUrl() {
  const params = emptyParams();
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (userTeamId) params.set('team_id', userTeamId);
  params.set('from', 'fcc');
  params.set('return_url', getCurrentRelativeUrl());
  return `/recruiting.html?${params.toString()}`;
}

/**
 * Open the Recruiting surface and stamp the wire as read.
 *
 * Mark-seen belongs HERE and nowhere else: not on hover (reading the button's
 * tooltip must not clear the badge) and not on FCC render (that would clear it
 * before the player has seen anything).
 */
async function openRecruitingSurface() {
  const url = buildRecruitingUrl();
  try {
    if (franchiseId && typeof API_CONFIG !== 'undefined') {
      await fetch(API_CONFIG.buildUrl('/franchise/recruiting-wire-seen'), {
        method: 'PATCH',
        headers: Object.assign(
          { 'Content-Type': 'application/json' },
          API_CONFIG.getAuthHeaders ? API_CONFIG.getAuthHeaders() : {}
        ),
        body: JSON.stringify({ franchise_id: franchiseId }),
      });
    }
  } catch (err) {
    // Never block navigation on the read marker.
    console.warn('[WIRE] could not persist seen state:', err);
  }
  if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(url);
  else window.location.assign(url);
}

function renderRecruitingTabBadge() {
  const api = window.GOB_RecruitingButtonState;
  if (!api) return;

  const wire = commandCenterTopDataCache?.recruiting_wire || {};
  const week = Number(commandCenterTopDataCache?.week || document.body.dataset.fccWeek || 1);

  // Tab badge — prompted only. Hovering does not clear it; only opening the surface
  // does, via the mark-seen PATCH.
  const prompted = api.recruitingIsPrompted({
    week,
    counts: wire.counts || {},
    boardSavedWeek: Number(wire.board_saved_week || 0),
    hasSavedBoard: !!wire.has_saved_board,
  });
  const tabBtn = document.querySelector('#franchise-container [data-tab="recruits-tab"]')
    || document.querySelector('[data-tab="recruits-tab"]');
  if (tabBtn) {
    let badge = tabBtn.querySelector('.inbox-badge');
    if (prompted && !badge) {
      badge = document.createElement('span');
      badge.className = 'inbox-badge';
      tabBtn.appendChild(badge);
    } else if (!prompted && badge) {
      badge.remove();
    }
    if (getComputedStyle(tabBtn).position === 'static') tabBtn.style.position = 'relative';
  }
}

async function renderHomeTab() {
  if (window.GOBOffice && typeof window.GOBOffice.render === 'function') {
    window.GOBOffice.render(commandCenterTopDataCache && commandCenterTopDataCache.office_digest);
  }
  renderRecruitingTabBadge();
}

async function loadHomeTabData() {
  await renderHomeTab();
}

function buildResourceUrl(page, extraParams) {
  if (!franchiseId || !userTeamId) return '#';
  const params = emptyParams();
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
  const data = await fetchJSON(fccPlaybooksUrl());
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
    const params = emptyParams();
    params.set('franchise_id', franchiseId);
    params.set('team_id', userTeamId);
    params.set('return_url', getCurrentRelativeUrl());
    return `?${params.toString()}`;
  };
  const standingsLink = document.getElementById('standings-resources-link');
  if (standingsLink) standingsLink.href = `/standings.html${q()}`;
  const scheduleFullLink = document.getElementById('schedule-full-link');
  const leagueScheduleHref = q()
    ? `/franchise-command-center.html${q()}&tab=league-schedule-view`
    : '/franchise-command-center.html?tab=league-schedule-view';
  if (scheduleFullLink) scheduleFullLink.href = leagueScheduleHref;
  const tournamentScheduleLink = document.getElementById('tournament-schedule-link');
  if (tournamentScheduleLink) tournamentScheduleLink.href = leagueScheduleHref;
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
  if (rSchedule) rSchedule.href = q()
    ? `/franchise-command-center.html${q()}&tab=league-schedule-view`
    : '/franchise-command-center.html?tab=league-schedule-view';
  const rTraits = document.getElementById('resources-team-traits');
  if (rTraits) rTraits.href = `/team-traits.html${q()}`;
  const rRankings = document.getElementById('resources-rankings');
  if (rRankings) rRankings.href = `/rankings.html${q()}`;
  const homeRankingsFullLink = document.getElementById('home-rankings-full-link');
  if (homeRankingsFullLink) homeRankingsFullLink.href = `/rankings.html${q()}`;
  const psLink = document.getElementById('fcc-ps-season-link');
  if (psLink && franchiseId && userTeamId) {
    const psParams = emptyParams();
    psParams.set('franchise_id', franchiseId);
    psParams.set('team_id', userTeamId);
    psParams.set('tab', 'practice-squad-view');
    psLink.href = `/franchise-command-center.html?${psParams.toString()}`;
  }
  const rRecruits = document.getElementById('resources-recruits');
  if (rRecruits) rRecruits.href = `/recruiting.html${q()}${q() ? '&from=fcc' : '?from=fcc'}`;
  const rAwards = document.getElementById('resources-awards');
  if (rAwards) rAwards.href = `/leaders.html${q()}`;
}

function formatTeamStatsPercent(numerator, denominator) {
  return denominator > 0 ? (((numerator || 0) / denominator) * 100).toFixed(1) + '%' : '0.0%';
}

function formatWholeDefPercent(numerator, denominator) {
  return denominator > 0 ? Math.round(((numerator || 0) / denominator) * 100) + '%' : '0%';
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
  if (category === 'DEF%') {
    const numeric = Number(value);
    return `${Number.isFinite(numeric) ? Math.round(numeric) : 0}%`;
  }
  if (category === 'FG%') {
    const numeric = Number(value);
    return `${Number.isFinite(numeric) ? numeric.toFixed(1) : '0.0'}%`;
  }
  const numeric = Number(value);
  if (category === 'PTS' || category === 'REB' || category === 'AST') {
    return Number.isFinite(numeric) ? numeric.toFixed(1) : '0.0';
  }
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

async function ensureLeaders(scope = 'conference', limit = 10) {
  if (!franchiseId) return null;
  const cacheKey = `${scope}:${limit}`;
  if (leadersDataCache.has(cacheKey)) return leadersDataCache.get(cacheKey);
  const data = await fetchJSON(
    `${API_CONFIG.buildUrl('/franchise/leaders')}?franchise_id=${encodeURIComponent(franchiseId)}&scope=season&view_scope=${encodeURIComponent(scope)}&limit=${limit}`
  );
  if (data) leadersDataCache.set(cacheKey, data);
  return data;
}

async function renderFccLeadersSummary() {
  const grid = document.getElementById('fcc-leaders-grid');
  if (!grid) return;
  grid.innerHTML = '<div class="fcc-leader-card"><div class="fcc-leader-card-empty">Loading leaders...</div></div>';
  const data = await ensureLeaders('conference', 5);
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
        <td>${escapeHomeHtml(formatWholeDefPercent(stats.DEF_S, stats.DEF_A))}</td>
      </tr>
    `;
  }).join('');
  tbody.innerHTML = rows;
}

function initFccRecruits(topData) {
  document.body.dataset.fccWeek = String(Number(topData?.week || 1));
  void renderHomeTab();
}

async function initializeTeamColorCache() {
  if (teamColorCache) return; // Already initialized
  
  try {
    const fid =
      (typeof franchiseId !== 'undefined' && franchiseId) ||
      liveParams().get('franchise_id') ||
      '';
    const teamsUrl = fid
      ? `${API_CONFIG.buildUrl('/teams')}?franchise_id=${encodeURIComponent(fid)}`
      : API_CONFIG.buildUrl('/teams');
    const res = await fetch(teamsUrl);
    const teamData = await res.json();
    teamColorCache = {};
    teamMetaByNameCache = {};
    teamData.forEach(t => {
      const color = t.primary_color;
      if (t.name) {
        teamColorCache[t.name] = color;
        teamMetaByNameCache[t.name] = {
          mascot: t.mascot || '',
          primary_color: color || null,
        };
      }
      // TB overlay: also index by display_name so custom program lookups hit overlay colors.
      if (t.display_name && t.display_name !== t.name) {
        teamColorCache[t.display_name] = color;
        teamMetaByNameCache[t.display_name] = {
          mascot: t.mascot || '',
          primary_color: color || null,
        };
      }
    });
    if (typeof getActiveTeamBuilderVisual === 'function') {
      const visual = getActiveTeamBuilderVisual();
      if (visual && visual.primary_color) {
        if (visual.name) teamColorCache[visual.name] = visual.primary_color;
        if (visual.replaced_name) teamColorCache[visual.replaced_name] = visual.primary_color;
      }
    }
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

function renderTeam(data) {
  if (!data) return;
  userRosterDataCache = window.FccRosterData.normalize(data);
  userRosterPlayersCache = userRosterDataCache.players;
  persistFccSessionCache();
  void renderHomeTab();
}

async function init() {
  if (window.GOB_Analytics) window.GOB_Analytics.franchiseEntered();
  // ✅ ALPHA: Initialize alpha banner (shows badge if IS_ALPHA=true)
  if (typeof AlphaBanner !== 'undefined') {
    await AlphaBanner.init();
  }
  
  // ✅ SS&S: Check URL params first for team_id (ObjectId) - allows seamless navigation
  const urlParams = liveParams();
  const urlTeamId = urlParams.get('team_id');
  if (urlTeamId) {
    userTeamId = urlTeamId;
    if (franchiseId && window.FranchiseLS) {
      window.FranchiseLS.set(franchiseId, 'user_team_id', userTeamId);
    }
  } else if (franchiseId && window.FranchiseLS) {
    userTeamId = window.FranchiseLS.get(franchiseId, 'user_team_id') || null;
  } else {
    userTeamId = null;
  }
  
  const initStartTime = performance.now();
  console.log('⏱️ [PERF] FCC init() START');
  const restoredFromSession = restoreFccSessionCache();
  try {
  if (restoredFromSession && commandCenterTopDataCache) {
    persistFranchiseDisplayColorContext(commandCenterTopDataCache);
    emitDisplayContextUpdate();
    adoptAuthoritativeFccTeamId(commandCenterTopDataCache);
    populateTop(commandCenterTopDataCache, { warm: true });
    void hydrateFccDisplayColorPreference();
    initFccRecruits(commandCenterTopDataCache);
    if (commandCenterTopDataCache.team) {
      userTeamNameForLeaders = commandCenterTopDataCache.team;
    }
    userConference = commandCenterTopDataCache.user_conference != null ? commandCenterTopDataCache.user_conference : null;
    userRegion = commandCenterTopDataCache.user_region != null && commandCenterTopDataCache.user_region !== '' ? commandCenterTopDataCache.user_region : null;
    void initializeTeamColorCache();
    // Advance and its ghost wait for the authoritative read below: the cached week
    // can be the one the player just finished.
    updateScoutingButton(commandCenterTopDataCache);
    updateRecruitingButton(commandCenterTopDataCache);
    updateAwardsButton(commandCenterTopDataCache);
    void updatePlaybooksButtonState(commandCenterTopDataCache);
    bindResourcesLinks();
    if (standingsDataCache) renderStandings(standingsDataCache);
    if (userRosterPlayersCache.length) renderTeam(userRosterDataCache);
    void renderHomeTab();
    // Keep the full-page overlay visible until authoritative command-center
    // data returns. Cached rendering is only a behind-the-overlay warm paint;
    // showing it directly causes a stale-data flash on FCC entry.
  }
  const topDataStartTime = performance.now();
  const topDataResult = await fetchCommandCenterData();
  let topData = topDataResult.data;
  const topDataEndTime = performance.now();
  console.log(`⏱️ [PERF] /franchise/command-center/data: ${(topDataEndTime - topDataStartTime).toFixed(2)}ms`);
  if (!topData && topDataResult.status === 404) {
    showFranchiseGoneNotice();
    publishFccUserTeam('');
    return;
  }
  if (!topData) {
    publishFccUserTeam('');
    // 404 (franchise gone) handled above; 401/403 already triggered an AccessDenied
    // redirect. Anything else — network (status 0), 5xx, or a 429 that never cleared
    // after the retry loop — is a real load failure. Show the retryable error card
    // instead of a silent dead page (Advance stuck disabled with no reason).
    if (topDataResult.status !== 401 && topDataResult.status !== 403) {
      showSeasonLoadError(topDataResult.status);
    }
    return; // finally block hides page-load-overlay, revealing the card
  }
  topData = await recoverCpuSimsBeforeFccRender(topData);
  if (!topData) {
    publishFccUserTeam('');
    return;
  }
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
  
  // One team-data read. loadTeamData reuses this body. Chemistry for the header
  // comes from the same payload the Team tab renders.
  if (franchiseId && userTeamId) {
    try {
      const teamDataStartTime = performance.now();
      const teamPayload = await fetchJSON(fccTeamDataUrl());
      const teamDataEndTime = performance.now();
      console.log(`⏱️ [PERF] /franchise/team-data: ${(teamDataEndTime - teamDataStartTime).toFixed(2)}ms`);
      if (teamPayload) {
        fccTeamDataPayload = teamPayload;
        if (teamPayload.team_attributes && teamPayload.team_attributes.team_chemistry !== undefined) {
          topData.team_chemistry = teamPayload.team_attributes.team_chemistry;
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
  playNowBtn.disabled = false;
  clearAdvanceSeasonLoadFailed(); // a prior failed load may have marked it; the load succeeded
  updateScoutingButton(topData);
  updateRecruitingButton(topData);
  updateEditRecruitingButton(topData);
  updateAwardsButton(topData);
  await updatePlaybooksButtonState(topData);
  // Your team's dispatches render inside News now; nothing to paint on load.
  const startMomentQueue = () => {
    if (fccBrowseTournamentTabActive()) return Promise.resolve();
    if (!window.MomentQueue || typeof window.MomentQueue.play !== 'function') return Promise.resolve();
    return window.MomentQueue.play(topData, {
      maps: {
        userTeamId,
        teamIdToNameMap: topData?.team_name_map || {},
        teamIdMetaMap,
      },
      boxScoreUrlBuilder: (moment) => buildFccBoxScoreUrlForMoment(moment),
    });
  };
  const afterTutorial = (fn) => {
    const ta = window.GOBTutorialAlerts;
    if (ta && typeof ta.whenReturnAlertsSettled === 'function') ta.whenReturnAlertsSettled(fn);
    else fn();
  };
  afterTutorial(() => {
    const queueDone = startMomentQueue();
    if (topData?.cut_required && Number(topData.cut_count || 0) > 0) {
      let shown = false;
      const overlayUp = () => !!(typeof document !== 'undefined' && document.querySelector(
        '.cm-overlay.is-visible,.arch-reveal-overlay.is-visible,.afm-overlay.is-visible,'
        + '.gob-talert-overlay,.sammy-modal-backdrop.open,.bn-overlay.show,.mm-scrim.is-open,.pk.is-open,.rv.is-open'
      ));
      const showTs = () => {
        if (shown) return;
        shown = true;
        showCutPlayersRequiredModal(Number(topData.cut_count || 0));
      };
      Promise.resolve(queueDone).then(showTs, showTs);
      setTimeout(() => {
        if (shown) return;
        if (overlayUp()) {
          Promise.resolve(queueDone).then(showTs, showTs);
          return;
        }
        showTs();
      }, 8000);
    }
  });

  if (topData && (topData.team_id || topData.team) && userTeamId) {
    console.log('Loading franchise roster for team_id:', userTeamId, 'franchiseId:', franchiseId);
    if (!franchiseId) {
      console.error('No franchiseId found - cannot load roster');
      return;
    }
    try {
      const rosterStartTime = performance.now();
      const result = await RosterLoader.loadRosterWithStats(fccRosterUrl(), '');
      const rosterEndTime = performance.now();
      console.log(`⏱️ [PERF] roster (franchise): ${(rosterEndTime - rosterStartTime).toFixed(2)}ms`);
      renderTeam(result);
    } catch (error) {
      console.error('Failed to load franchise roster:', error);
    }
  }
  const standingsStartTime = performance.now();
  const standingsUrl = userTeamId
    ? `${API_CONFIG.buildUrl('/franchise/standings')}?franchise_id=${franchiseId}&scope=user_region&team_id=${encodeURIComponent(userTeamId)}${fccProfileSuffix()}`
    : `${API_CONFIG.buildUrl('/franchise/standings')}?franchise_id=${franchiseId}${fccProfileSuffix()}`;
  const standingsData = await fetchJSON(standingsUrl);
  const standingsEndTime = performance.now();
  console.log(`⏱️ [PERF] /franchise/standings: ${(standingsEndTime - standingsStartTime).toFixed(2)}ms`);
  standingsDataCache = standingsData;
  persistFccSessionCache();
  renderStandings(standingsData);
  bindResourcesLinks();
  const homeTabDataPromise = loadHomeTabData();
    
    // Load team data for header chemistry / session cache
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

/**
 * SS&S: Same box-score query hints as post-game completion (gameCompletionPopup) so
 * `/api/game/{id}` plus URL stay aligned; game doc `user_team_side` remains primary when present.
 */
function appendFranchiseBoxScoreUserHints(params, homeTeamName, awayTeamName) {
  if (!params || typeof params.set !== 'function') return;
  const ctx = (franchiseId && window.FranchiseLS)
    ? window.FranchiseLS.getTeamContext(franchiseId)
    : { teamId: '', teamName: '' };
  const tid =
    (userTeamId && String(userTeamId).trim()) ||
    (ctx.teamId || '').trim() ||
    '';
  const teamNameRaw =
    (ctx.teamName || '').trim() ||
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

// True if any higher-priority FCC modal/prompt claims this visit, so the
// lowest-priority archetype-evolution modal must yield. Combines a DOM check
// (same overlay selectors RegionByeModal.blockerVisible uses, for modals already
// rendered) with a data check from topData/me (for modals eligible this visit
// that may not have rendered yet — avoids a render-timing race). Conservative:
// when in doubt it returns true, so the evolution modal over-yields rather than
// stacking on another modal.
function fccBrowseTournamentTabActive() {
  try {
    return new URLSearchParams(window.location.search).get('tab') === 'tournament-view';
  } catch (_) {
    return false;
  }
}

function fccHasCompetingModal(topData) {
  if (typeof document !== 'undefined' && document.querySelector(
      '.cm-overlay.is-visible,.arch-reveal-overlay.is-visible,.afm-overlay.is-visible,'
      + '.gob-talert-overlay,.sammy-modal-backdrop.open,.bn-overlay.show,.mm-scrim.is-open,.pk.is-open,.rv.is-open')) {
    return true;
  }
  if (Array.isArray(topData?.moments_for_this_visit) && topData.moments_for_this_visit.length) return true;
  if (Array.isArray(topData?.pending_championship_moments) && topData.pending_championship_moments.length) return true;
  if (topData?.region_bye_modal_eligible) return true;
  if (topData?.conference_rs_region_modal?.eligible) return true;
  if (topData?.bracket_reveal_modal?.eligible || topData?.bracket_update_modal?.eligible) return true;
  if (topData?.walk_on_welcome_modal?.eligible) return true;
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
  const params = emptyParams();
  params.set('mode', 'franchise');
  params.set('franchise_id', franchiseId);
  params.set('game_id', moment.game_id);
  if (moment.winner_team_name) params.set('home', moment.winner_team_name);
  if (moment.loser_team_name) params.set('away', moment.loser_team_name);
  appendFranchiseBoxScoreUserHints(params, moment.winner_team_name, moment.loser_team_name);
  return `/box-score.html?${params.toString()}`;
}

function flashSeasonAdvanceScreen() {
  const existing = document.querySelector('.fcc-season-advance-flash');
  if (existing) existing.remove();
  const flash = document.createElement('div');
  flash.className = 'fcc-season-advance-flash';
  flash.setAttribute('aria-hidden', 'true');
  document.body.appendChild(flash);
  const cleanup = () => flash.remove();
  flash.addEventListener('animationend', cleanup, { once: true });
  // Fallback if animationend is skipped (e.g. tab backgrounded).
  window.setTimeout(cleanup, 500);
}

/**
 * Full-screen "Advancing To Season N" cover.
 *
 * Rollover is a multi-second server job. Without a cover the confirm modal stayed up
 * with a re-armed button, which reads as "nothing happened — press it again". This
 * takes the screen instead: the team's own logo, the destination season, and a pulse
 * bar that says work is happening without pretending to know how much is left.
 */
function showSeasonAdvanceOverlay(nextSeason) {
  document.querySelector('.fcc-season-advance')?.remove();
  const logo = document.getElementById('team-logo');
  const src = logo?.src || '/images/teams/general/general_banner_primary.jpg';
  const overlay = document.createElement('div');
  overlay.className = 'fcc-season-advance';
  overlay.setAttribute('role', 'status');
  overlay.setAttribute('aria-live', 'polite');
  overlay.innerHTML = `
    <div class="fcc-season-advance__stack">
      <img class="fcc-season-advance__logo" src="${escapeHomeHtml(src)}" alt="">
      <div class="fcc-season-advance__copy">Advancing To Season ${escapeHomeHtml(nextSeason)}</div>
      <div class="fcc-season-advance__bar"><i></i></div>
    </div>
  `;
  document.body.appendChild(overlay);
  return overlay;
}

/** The season the franchise is moving INTO. */
function nextSeasonNumber() {
  const current = Number(commandCenterTopDataCache?.current_season || 1);
  return (Number.isFinite(current) ? current : 1) + 1;
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

// Practice-squad assignment screen URL. Shared by the required-cuts modal CTA and
// the Green Action Button's 'cut-players' mode so both land on the same screen
// with the same return path.
function buildAssignPracticeSquadUrl() {
  const params = emptyParams();
  params.set('franchise_id', franchiseId);
  params.set('team_id', userTeamId);
  params.set('from', 'fcc');
  params.set('return_url', getCurrentRelativeUrl());
  return `/cut-players.html?${params.toString()}`;
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
        <button type="button" class="gob-modal-btn-primary is-green" id="fcc-cut-required-close">Assign Practice Squad</button>
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
  // Straight to the assignment screen — no extra Green Action Button hop.
  overlay.querySelector('#fcc-cut-required-close')?.addEventListener('click', async () => {
    playSound('confirm-1-lowervol.wav');
    const sfxReady = waitForConfirmSfx();
    close();
    await sfxReady;
    if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(buildAssignPracticeSquadUrl());
    else window.location.assign(buildAssignPracticeSquadUrl());
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

const EOS_SIM_OVERLAY_BY_WEEK = Object.freeze({
  28: 'Simming Conference Semifinals',
  29: 'Simming Conference Finals',
  30: 'Simming Region Semifinals',
  31: 'Simming Region Finals',
  32: 'Simming National First Round',
  33: 'Simming National Semifinals',
  34: 'Simming National Finals',
});

function fccEosSimOverlayCopy(week) {
  const n = Number(week || 0);
  return EOS_SIM_OVERLAY_BY_WEEK[n] || 'Simming Tournament Games';
}

function advanceEnv() {
  return {
    franchiseId: franchiseId,
    userTeamId: userTeamId,
    userTeamName: userTeamNameForLeaders,
    topData: commandCenterTopDataCache,
    fetchJSON: fetchJSON,
    fccCpuSimNeedsRecovery: fccCpuSimNeedsRecovery,
    recoverCpuSimsBeforeFccRender: recoverCpuSimsBeforeFccRender,
    emptyParams: emptyParams,
    getCurrentRelativeUrl: getCurrentRelativeUrl,
    openRecruitingSurface: openRecruitingSurface,
    buildAssignPracticeSquadUrl: buildAssignPracticeSquadUrl,
    fccEosSimOverlayCopy: fccEosSimOverlayCopy,
    showNewSeasonConfirmModal: showNewSeasonConfirmModal,
    flashSeasonAdvanceScreen: flashSeasonAdvanceScreen,
    showSeasonAdvanceOverlay: showSeasonAdvanceOverlay,
    normalizeHexColor: normalizeHexColor,
    nextSeasonNumber: nextSeasonNumber,
  };
}

function updatePlayButton(data) {
  if (window.GOBAdvance) window.GOBAdvance.updatePlayButton(data, advanceEnv());
}


/**
 * The ghost button under #play-now — the way BACK into recruiting.
 *
 * It appears exactly when this week's recruiting step is done and the green button has
 * moved on, which is the only time a second button is not just restating where the
 * green one already goes:
 *
 *   weeks 20-26, invites submitted this week -> "Edit Recruit Invites"
 *   week 35, orders submitted                -> "Edit Recruiting Orders"
 *
 * Both land on the Recruiting Hub, and both are safe: unsubmitted edits made there are
 * preserved by the sessionStorage draft, and re-submitting simply overwrites.
 */
function updateEditRecruitingButton(data) {
  if (window.GOBAdvance) window.GOBAdvance.updateEditRecruitingButton(data, advanceEnv());
}


function updateRecruitingButton(data) {
  const week = Number(data?.week || 1);
  const resultsWeek = Number(data?.current_recruiting_results_week || 0);
  // Phase-aware footnote that speaks the hub phase strip's language (calendar-driven).
  const phase = (window.RecruitingSpine && window.RecruitingSpine.Phase)
    ? window.RecruitingSpine.Phase.forWeek(week)
    : (week >= 20 && week <= 26 ? 'invite' : week === 35 ? 'day' : week === 36 ? 'results' : 'passive');
  const resultsReady = week >= 20 && week <= 26 && resultsWeek === week;

  let text, btnLabel = null, showButton = false;
  if (phase === 'invite') {
    const sent = Math.max(0, Math.min(7, week - 20)); // matches the phase strip's "N/7 sent"
    text = `Invite Season · Wk ${week} · ${sent} of 7 sent`;
    showButton = true;
    btnLabel = resultsReady ? `View Week ${week} Results` : 'Open Invite Board';
  } else if (phase === 'day') {
    text = 'Signing Day · 50 points';
    showButton = true;
    btnLabel = 'Open Signing Board';
  } else if (phase === 'results') {
    text = 'Signings are final';
    // While #play-now reads "View Recruiting Results" it goes to this exact page, so a
    // second button beneath it would only restate where green already goes — the same
    // rule the ghost Edit button follows. It comes back once green flips to Go To Next
    // Season. Scoped to week 36: from week 37 green is the rollover, so this is the only
    // way back to the signing list.
    const greenOwnsResults = week === 36 && !(data?.recruiting_wire || {}).week_36_results_seen;
    showButton = !greenOwnsResults;
    btnLabel = showButton ? 'View Signings' : null;
  } else { // passive
    text = week >= 27 ? `Passive · Wk ${week} — postseason. Signing Day is Week 35.`
      : week === 19 ? 'Passive · Wk 19 — Invite Season begins next week.'
        : 'Passive — leans come to you. Invite Season opens Week 20.';
  }

  // The Recruiting Hub (recruiting.html) now owns invites / signing / results.
  let href = null;
  if (showButton) {
    const params = emptyParams();
    params.set('franchise_id', franchiseId);
    if (userTeamId) params.set('team_id', userTeamId);
    params.set('from', 'fcc');
    params.set('return_url', getCurrentRelativeUrl());
    href = `/recruiting.html?${params.toString()}`;
  }

  // showCopy=false on the Coach's Office card: the Wire renders its own phase-aware
  // status line inside the card body, and this footnote sat on top of it. The Recruiting
  // tab keeps its footnote copy.
  const slots = [
    ['fcc-recruiting-live-copy-home', 'fcc-recruiting-btn-home', false],
    ['fcc-recruiting-live-copy-tab', 'fcc-recruiting-btn-tab', true],
  ];
  for (const [copyId, btnId, showCopy] of slots) {
    const recruitingBtn = document.getElementById(btnId);
    const liveCopy = document.getElementById(copyId);
    if (!recruitingBtn || !liveCopy) continue;
    liveCopy.textContent = showCopy ? text : '';
    liveCopy.style.display = showCopy ? 'block' : 'none';
    // With no copy and no button the footer would render as a bare rule; hide it.
    const footer = liveCopy.closest('.fcc-recruiting-footnote');
    if (footer) footer.style.display = (showCopy || showButton) ? '' : 'none';
    recruitingBtn.style.display = showButton ? 'inline-flex' : 'none';
    recruitingBtn.textContent = btnLabel || '';
    recruitingBtn.disabled = !showButton;
    recruitingBtn.classList.toggle('is-dead', !showButton);
    recruitingBtn.onclick = null;
    if (showButton && href) {
      recruitingBtn.onclick = () => {
        if (window.GOBNav && window.GOBNav.go) window.GOBNav.go(href);
        else window.location.assign(href);
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
  import('/js/shared/uiSfx.js').then(function (m) { m.playSfx(filename, 0.7); }).catch(function () {});
}

const FCC_CONFIRM_NAV_DELAY_MS = 200;
function waitForConfirmSfx() {
  return new Promise(resolve => setTimeout(resolve, FCC_CONFIRM_NAV_DELAY_MS));
}

const playNowBtn = document.getElementById('play-now');
playNowBtn.disabled = true;
if (window.GOBAdvance && playNowBtn) window.GOBAdvance.bind(playNowBtn, advanceEnv);


function navigateToGamePlan() {
  playSound('click-tiny.wav');
  if (!franchiseId || !userTeamId) {
    alert('Franchise or user team not loaded');
    return;
  }
  const params = emptyParams();
  params.set('mode', 'franchise');
  params.set('franchise_id', franchiseId);
  params.set('team_id', userTeamId);
  params.set('from', 'command_center');
  params.set('return_url', getCurrentRelativeUrl());
  if (window.GOBNav) window.GOBNav.go(`/game-plan.html?${params.toString()}`);
  else window.location.assign(`/game-plan.html?${params.toString()}`);
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
      const params = emptyParams();
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
  const urlParams = liveParams();
  franchiseId = urlParams.get('franchise_id');
  if (!franchiseId) {
    console.error('❌ [FCC] franchise_id is required but missing from URL. Redirecting to franchise select.');
    window.location.href = '/franchise-select-team.html';
    return;
  }
  // #play-now stays disabled until authoritative command-center data sets it
  // (init below, or GOBAdvance.load). The static label is not a real step.

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

  fccInitializationPromise = init();

  // ✅ Phase 4.4: Shared tab management (commandCenterTabs.js)
  if (typeof CommandCenterTabs !== 'undefined') {
    CommandCenterTabs.initCommandCenterTabs({
      defaultTab: 'home-tab',
      onTabShow: (tabName) => {
        bindResourcesLinks();
        if (commandCenterTopDataCache) {
          updateRecruitingButton(commandCenterTopDataCache);
        }
        if (tabName === 'fcc-team-stats-summary-tab') {
          void renderFccTeamStatsSummary();
        }
        if (tabName === 'awards-tab') {
          void renderFccLeadersSummary();
        }
        if (window.GOBNav && typeof window.GOBNav.restoreScroll === 'function') {
          window.GOBNav.restoreScroll();
        }
      }
    });
  }
});

let teamData = null;
let fccTeamDataPayload = null;

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
    
    // The Office init already loaded this body. Fetch only if that read did not run.
    let data = fccTeamDataPayload;
    if (!data) {
      const teamDataStartTime = performance.now();
      console.log('⏱️ [PERF] loadTeamData() calling /franchise/team-data START');
      data = await fetchJSON(fccTeamDataUrl());
      fccTeamDataPayload = data;
      const teamDataEndTime = performance.now();
      console.log(`⏱️ [PERF] loadTeamData() /franchise/team-data: ${(teamDataEndTime - teamDataStartTime).toFixed(2)}ms`);
    }
    if (!data) {
      console.error('Failed to load team data');
      return;
    }

    const players = userRosterPlayersCache.length ? userRosterPlayersCache.slice() : [];
    
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
    
    void renderHomeTab();
    
    const loadTeamDataEndTime = performance.now();
    console.log(`⏱️ [PERF] loadTeamData() function COMPLETE: ${(loadTeamDataEndTime - loadTeamDataStartTime).toFixed(2)}ms`);
  } catch (error) {
    console.error('Failed to load team data:', error);
  }
}

const TEAM_MEASURES_RADAR_AXES = [
  { key: 'offensive_efficiency', label: 'Offense', angle: -90 },
  { key: 'fb_efficiency', label: 'Fast Break', angle: -45 },
  { key: 'discipline', label: 'Discipline', angle: 0 },
  { key: 'pt_efficiency', label: 'P/T Defense', angle: 45 },
  { key: 'defensive_efficiency', label: 'Defense', angle: 90 },
  { key: 'fb_opp_modifier', label: 'Fast Break Defense', angle: 135 },
  { key: 'fight', label: 'Fight', angle: 180 },
  { key: 'pt_opp_modifier', label: 'P/T Offense', angle: 225 }
];
const TEAM_MEASURES_RADAR_MIN = -20;
const TEAM_MEASURES_RADAR_MAX = 20;
const TEAM_MEASURES_RADAR_SPAN = TEAM_MEASURES_RADAR_MAX - TEAM_MEASURES_RADAR_MIN;
// Preserve the former +7-of-10 visual threshold at the same 70% position.
const TEAM_MEASURES_RADAR_DOMINANT_MIN = 14;

function buildTeamMeasuresRadarMarkup(teamAttrs) {
  const center = 250;
  const radius = 164;
  const labelRadius = 204;
  const pointLabelRadius = 18;
  const ringValues = [20, 13.3, 6.7, 0, -6.7, -13.3, -20];

  const values = TEAM_MEASURES_RADAR_AXES.map((axis) => Number(teamAttrs?.[axis.key] || 0));
  const clampedValues = values.map((value) => Math.max(TEAM_MEASURES_RADAR_MIN, Math.min(TEAM_MEASURES_RADAR_MAX, value)));
  const dominantCount = values.filter((value) => Number(value) >= TEAM_MEASURES_RADAR_DOMINANT_MIN).length;

  function radiusForValue(value) {
    const clamped = Math.max(
      TEAM_MEASURES_RADAR_MIN,
      Math.min(TEAM_MEASURES_RADAR_MAX, Number(value) || 0)
    );
    return ((clamped - TEAM_MEASURES_RADAR_MIN) / TEAM_MEASURES_RADAR_SPAN) * radius;
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
    const ringClass = ringValue === TEAM_MEASURES_RADAR_MAX
      ? ' tm-radar-ring-outer'
      : ringValue === 0
        ? ' tm-radar-ring-zero'
        : ringValue === TEAM_MEASURES_RADAR_MIN
          ? ' tm-radar-ring-inner'
          : '';
    return `<polygon class="tm-radar-ring${ringClass}" points="${points}" />`;
  }).join('');

  const axisLines = TEAM_MEASURES_RADAR_AXES.map((axis) => {
    const point = pointFor(axis.angle, TEAM_MEASURES_RADAR_MAX);
    return `<line class="tm-radar-axis" x1="${center}" y1="${center}" x2="${point.x.toFixed(2)}" y2="${point.y.toFixed(2)}" />`;
  }).join('');

  const shapePoints = TEAM_MEASURES_RADAR_AXES.map((axis, index) => {
    const point = pointFor(axis.angle, clampedValues[index]);
    return `${point.x.toFixed(2)},${point.y.toFixed(2)}`;
  }).join(' ');

  const labels = TEAM_MEASURES_RADAR_AXES.map((axis) => {
    const point = pointFor(axis.angle, TEAM_MEASURES_RADAR_MAX, labelRadius - radius);
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

let upcomingOpponent = null;
let upcomingOpponentId = null;
const upcomingOpponentByKey = Object.create(null);

function upcomingOpponentCacheKey(data) {
  const week = data?.week || data?.training_status?.current_week || 0;
  return String(franchiseId || '') + ':' + String(week);
}

function opponentFromLoadedFcc(data) {
  if (!data) return null;
  const summary = data.next_game_summary;
  if (summary && (summary.opponent_team_name || summary.opponent_team_id)) {
    return {
      name: summary.opponent_team_name || '',
      id: summary.opponent_team_id != null ? String(summary.opponent_team_id) : '',
    };
  }
  const digestGame = data.office_digest && data.office_digest.next_game;
  if (digestGame && (digestGame.opponent || digestGame.opponent_team_name || digestGame.opponent_team_id)) {
    return {
      name: digestGame.opponent || digestGame.opponent_team_name || '',
      id: digestGame.opponent_team_id != null ? String(digestGame.opponent_team_id) : '',
    };
  }
  return null;
}

function rememberUpcomingOpponent(key, resolved) {
  if (!key || !resolved || !resolved.name) return null;
  upcomingOpponentByKey[key] = resolved;
  upcomingOpponent = resolved.name;
  upcomingOpponentId = resolved.id || null;
  return resolved;
}

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

  const key = upcomingOpponentCacheKey(data);
  const hit = upcomingOpponentByKey[key];
  if (hit && hit.name) {
    upcomingOpponent = hit.name;
    upcomingOpponentId = hit.id || null;
    return hit;
  }

  // play-next-game can persist region_tournaments on EOS weeks
  // (_maybe_reconcile_region_for_eos). Scouting reads the opponent already
  // sitting on the FCC payload / Office digest instead of that POST.
  const fromLoaded = opponentFromLoadedFcc(data);
  if (fromLoaded && fromLoaded.name) {
    return rememberUpcomingOpponent(key, fromLoaded);
  }

  upcomingOpponent = null;
  upcomingOpponentId = null;
  return null;
}

function updateScoutingButton(data) {
  const scoutingBtn = document.getElementById('scouting-report-btn');
  if (!scoutingBtn) return;
  resolveUpcomingOpponentFromMatchup(data).then((result) => {
    scoutingBtn.style.display = result ? 'block' : 'none';
  });
}

window.GOBFccPrep = {
  whenReady: () => fccInitializationPromise,
  resolveUpcomingOpponent: () => resolveUpcomingOpponentFromMatchup(commandCenterTopDataCache),
  peekUpcomingOpponent: () => {
    const key = upcomingOpponentCacheKey(commandCenterTopDataCache);
    return upcomingOpponentByKey[key] || opponentFromLoadedFcc(commandCenterTopDataCache);
  },
  rankingEntry: getTeamRankingEntry,
  standingsEntry: getStandingsTeamEntry,
  teamPageUrl: buildFranchiseTeamPageUrl,
};
