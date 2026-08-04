function formatTeamName(name) {
  return (name || '')
    .toLowerCase()
    .replace(/_/g, ' ')
    .split(' ')
    .map(w => w.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join('-'))
    .join(' ');
}

/**
 * Derive team_slug from a display name for asset paths.
 * Must match BackEnd.utils.team_slug.slug_from_display_name:
 * lowercase, strip apostrophes/periods, hyphens → spaces, spaces → underscores.
 * Not an identity normalizer — ObjectId / teams.team_id stay the keys.
 */
function nameToTeamSlug(teamName) {
  if (!teamName || typeof teamName !== 'string') return 'general';
  let s = teamName.trim().toLowerCase();
  s = s.replace(/['.]/g, '');
  s = s.replace(/-/g, ' ').replace(/\s+/g, ' ').trim();
  s = s.replace(/\s/g, '_');
  return s || 'general';
}

/** Asset key -> { ext, fallbackSlug } */
var TEAM_ASSET_SPEC = {
  court: { ext: 'jpg', fallbackSlug: 'general' },
  logo_square: { ext: 'png', fallbackSlug: 'general' },
  background: { ext: 'png', fallbackSlug: 'general' },
  banner_primary: { ext: 'jpg', fallbackSlug: 'general' },
  // Picker-grid derivative: ~400px wide WebP. Full banners stay banner_primary.
  banner_card: { ext: 'webp', fallbackSlug: 'general' }
};

/** Known on-disk core team asset folders (excl. general). */
var CORE_TEAM_ASSET_SLUGS = {
  'abilene': 1,
  'ada': 1,
  'amariabi_international': 1,
  'amarillo_tech': 1,
  'ann_arbor': 1,
  'appalachia': 1,
  'archbishop_mcclellan': 1,
  'austin': 1,
  'austin_west': 1,
  'barton_lutheran': 1,
  'bayou_district': 1,
  'bentley_truman': 1,
  'berkley': 1,
  'biloxi': 1,
  'boise': 1,
  'border_academy': 1,
  'burroughs': 1,
  'cagers_world': 1,
  'cardinal_conor': 1,
  'casino_row': 1,
  'chambless_global': 1,
  'chapel_hill': 1,
  'circus_circus': 1,
  'cleveland_carlysle': 1,
  'columbus': 1,
  'concord': 1,
  'couer_dalene': 1,
  'crickstown': 1,
  'crimson_county': 1,
  'crofton': 1,
  'cupertino': 1,
  'd1_institute': 1,
  'dade_academy': 1,
  'decatur_dei': 1,
  'deland': 1,
  'desert_regional': 1,
  'dillinger': 1,
  'durham': 1,
  'east_rockies': 1,
  'empire_city': 1,
  'evanston': 1,
  'falls_academy': 1,
  'fielding': 1,
  'four_corners': 1,
  'gainesville': 1,
  'garden_elites': 1,
  'gp_prep_school': 1,
  'grayson_ranch': 1,
  'grizzly_academy': 1,
  'grupenberg': 1,
  'ha_rushmore': 1,
  'hana_road': 1,
  'harding_central': 1,
  'hardwood_fields': 1,
  'hollywood_prep': 1,
  'houston_jesuit': 1,
  'huntington_canyon': 1,
  'hyde_methodist': 1,
  'ida': 1,
  'independence': 1,
  'iowa_academy': 1,
  'ivy_prep': 1,
  'juneau_nome': 1,
  'kenton': 1,
  'keys_high': 1,
  'knoxville': 1,
  'lancaster': 1,
  'lawrence': 1,
  'lewis_catholic': 1,
  'lexington': 1,
  'little_york': 1,
  'long_island_methodist': 1,
  'mahala_alou': 1,
  'melbourne_americas': 1,
  'middletex': 1,
  'minot': 1,
  'mobile': 1,
  'monroe_hayes': 1,
  'montpeiler': 1,
  'morristown': 1,
  'mt_simmons': 1,
  'mynsk': 1,
  'myrtle_private': 1,
  'nickel_beach': 1,
  'norman': 1,
  'north_columbus': 1,
  'ocean_city': 1,
  'ozark_centre': 1,
  'pacific_all_stars': 1,
  'pan_handle_limited': 1,
  'pikes_prep': 1,
  'providence': 1,
  'queens_guard': 1,
  'quigley_catholic': 1,
  'rainier_central': 1,
  'rancho_estrada': 1,
  'reardon_mayes': 1,
  'redwood_high': 1,
  'reyes_santiago': 1,
  'rivers_edge': 1,
  'rodeo_circuit': 1,
  'sacred_heart': 1,
  'salem': 1,
  'san_jose': 1,
  'seattle_aaa': 1,
  'south_lancaster': 1,
  'southwest_miner': 1,
  'st_peters': 1,
  'stormwood': 1,
  'swoosh': 1,
  'syracuse': 1,
  'tallahassee': 1,
  'templeton_wesley': 1,
  'toronto_limited': 1,
  'tower_academy': 1,
  'tri_cities_prep': 1,
  'tucson': 1,
  'two_rivers': 1,
  'upper_peninsula': 1,
  'upstate': 1,
  'valdosta_valley': 1,
  'valley_high': 1,
  'vancouver': 1,
  'wacker_west': 1,
  'wash_u_prep': 1,
  'washington_carver': 1,
  'west_ocean_city': 1,
  'xavien': 1
};

/** Core-8 coach folder abbreviations (Sammy/Duke portraits). */
var TEAM_COACH_ABBR = {
  'Four Corners': 'FC',
  'Bentley-Truman': 'BT',
  'Lancaster': 'Lan',
  'Little York': 'LY',
  'Morristown': 'Mor',
  'Ocean City': 'OC',
  'South Lancaster': 'SL',
  'Xavien': 'Xav',
};

var GENERIC_TEAM_SAMMY = '/images/sammy_tutorial.png';

/** In-memory Team Builder visual for this page session (hydrated from franchise payload). */
var _activeTeamBuilderVisual = null;
/**
 * Payload/network hydrate gate. FranchiseLS warm alone does NOT settle this —
 * chrome apply must await ensureTeamBuilderVisualReady().
 */
var _tbVisualReady = false;
var _tbVisualReadyPromise = null;

/**
 * Set the session Team Builder visual. FranchiseLS is an optional warm cache only.
 */
function setActiveTeamBuilderVisual(visual) {
  _activeTeamBuilderVisual = visual || null;
}

function _franchiseIdFromLocation() {
  try {
    if (typeof window === 'undefined' || !window.location) return null;
    var sp = new URLSearchParams(window.location.search || '');
    return sp.get('franchise_id') || null;
  } catch (e) {
    return null;
  }
}

function isTeamBuilderVisualReady() {
  var fid = _franchiseIdFromLocation();
  if (!fid) return true;
  return !!_tbVisualReady;
}

/**
 * Active Team Builder visual overlay for the franchise in the URL (or null).
 * Prefers in-memory hydrate from franchise payload; localStorage is cache only.
 * Kicks lazy network hydrate when a franchise_id is present (does not await).
 * Pass-through no-op when absent — same property as the §3.2 name resolver.
 */
function getActiveTeamBuilderVisual() {
  if (!_tbVisualReady) {
    try {
      ensureTeamBuilderVisualReady();
    } catch (e) { /* ignore */ }
  }
  if (_activeTeamBuilderVisual) return _activeTeamBuilderVisual;
  if (typeof window === 'undefined' || !window.FranchiseLS) return null;
  try {
    var cached = window.FranchiseLS.getTeamBuilderVisual() || null;
    if (cached) {
      _activeTeamBuilderVisual = cached;
      return cached;
    }
  } catch (e) {}
  return null;
}

/**
 * Build + hydrate Team Builder visual from a franchise API payload.
 * Writes memory (source of truth for this page) and optionally caches to FranchiseLS.
 * Settles the ready gate — this is the hydrate producer (FCC, Apply, ensure-fetch).
 * @param {object} data - FCC /me, mode-select card, Apply response, etc.
 * @param {string} [franchiseId]
 * @returns {object|null} visual or null when not a custom program
 */
function hydrateTeamBuilderVisualFromFranchisePayload(data, franchiseId) {
  clearTeamBuilderChromeSnapshot();
  if (!data) {
    setActiveTeamBuilderVisual(null);
    _tbVisualReady = true;
    return null;
  }
  var isCustom = !!(data.is_custom_team || data.is_custom || data.asset_strategy === 'generated');
  if (!isCustom) {
    setActiveTeamBuilderVisual(null);
    if (franchiseId && typeof window !== 'undefined' && window.FranchiseLS) {
      try {
        window.FranchiseLS.setTeamBuilderVisual(franchiseId, null);
      } catch (e) {}
    }
    _tbVisualReady = true;
    return null;
  }
  var name = data.team || data.user_team_id || data.name || '';
  var jerseyPreset = Number(data.jersey_preset);
  if (jerseyPreset !== 2) jerseyPreset = 1;
  var court =
    data.court ||
    (data.team_builder && data.team_builder.court) ||
    null;
  var visual = {
    name: name,
    abbreviation: data.abbreviation,
    mascot: data.mascot || '',
    primary_color: data.primary_color || data.primary,
    secondary_color: data.secondary_color || data.secondary,
    jersey_preset: jerseyPreset,
    // Server overlay is source of truth; LS only caches after hydrate.
    court: court,
    asset_strategy: 'generated',
    is_custom: true,
    replaced_name: data.team_builder_replaced_name || data.replaced_name,
    replaced_object_id: data.user_team_object_id || data.replaced_object_id || data.team_object_id,
    replaced_primary_color:
      data.team_builder_replaced_primary_color || data.replaced_primary_color || null,
    replaced_secondary_color:
      data.team_builder_replaced_secondary_color || data.replaced_secondary_color || null,
  };
  setActiveTeamBuilderVisual(visual);
  if (franchiseId && typeof window !== 'undefined' && window.FranchiseLS) {
    try {
      window.FranchiseLS.setTeamBuilderVisual(franchiseId, visual);
    } catch (e) {}
  }
  _tbVisualReady = true;
  return visual;
}

/**
 * Ensure session visual is hydrated from the franchise API payload (same producer
 * as FCC populateTop). Warming from FranchiseLS alone is not the hydrate path.
 * @param {string} franchiseId
 * @returns {Promise<object|null>}
 */
async function ensureTeamBuilderVisualHydratedFromFranchise(franchiseId) {
  if (!franchiseId) return getActiveTeamBuilderVisual();
  try {
    var base =
      typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl
        ? API_CONFIG.buildUrl('/franchise/command-center/data')
        : '/franchise/command-center/data';
    var url = base + '?franchise_id=' + encodeURIComponent(franchiseId) + '&profile=1';
    var headers =
      typeof API_CONFIG !== 'undefined' && API_CONFIG.getAuthHeaders
        ? API_CONFIG.getAuthHeaders()
        : {};
    var res = await fetch(url, { headers: headers });
    if (!res.ok) {
      _tbVisualReady = true;
      return getActiveTeamBuilderVisual();
    }
    var data = await res.json();
    return hydrateTeamBuilderVisualFromFranchisePayload(data, franchiseId);
  } catch (e) {
    _tbVisualReady = true;
    return getActiveTeamBuilderVisual();
  }
}

/**
 * Resolver-owned hydrate gate. Lazy-starts the FCC payload fetch when a
 * franchise_id is on the URL. Chrome apply awaits this — callers need not.
 *
 * Sync network hydrate is not feasible (fetch is async); this is the async
 * precondition that makes paint-without-hydrate impossible.
 *
 * @param {string} [franchiseId]
 * @returns {Promise<object|null>}
 */
function ensureTeamBuilderVisualReady(franchiseId) {
  if (_tbVisualReady) {
    return Promise.resolve(_activeTeamBuilderVisual);
  }
  var fid = franchiseId || _franchiseIdFromLocation();
  if (!fid) {
    _tbVisualReady = true;
    return Promise.resolve(null);
  }
  if (_tbVisualReadyPromise) return _tbVisualReadyPromise;
  _tbVisualReadyPromise = ensureTeamBuilderVisualHydratedFromFranchise(fid).then(
    function (v) {
      _tbVisualReady = true;
      return v;
    },
    function () {
      _tbVisualReady = true;
      return _activeTeamBuilderVisual;
    }
  );
  return _tbVisualReadyPromise;
}

/**
 * Display label for a side. Hydrated visual.name is authority; URL/sim fallbacks
 * are not identity sources — only used when the overlay does not match.
 * @param {string} teamNameOrSlug - core identity, display, or slug
 * @param {string} [fallbackDisplay] - URL *_display or sim display_name
 * @returns {string}
 */
function resolveTeamBuilderDisplayName(teamNameOrSlug, fallbackDisplay) {
  if (_tbChromeSnapshotByKey) {
    var chrome = lookupTeamChrome(teamNameOrSlug, { label: fallbackDisplay });
    if (chrome && chrome.label) return chrome.label;
  }
  if (!_tbVisualReady) {
    try {
      ensureTeamBuilderVisualReady();
    } catch (e) { /* ignore */ }
  }
  var visual = _activeTeamBuilderVisual;
  if (!visual && typeof window !== 'undefined' && window.FranchiseLS) {
    try {
      visual = window.FranchiseLS.getTeamBuilderVisual() || null;
    } catch (e2) { /* ignore */ }
  }
  if (visual && teamBuilderVisualMatchesName(visual, teamNameOrSlug)) {
    return String(visual.name || fallbackDisplay || teamNameOrSlug || '');
  }
  if (visual && fallbackDisplay && teamBuilderVisualMatchesName(visual, fallbackDisplay)) {
    return String(visual.name || fallbackDisplay);
  }
  return String(fallbackDisplay || teamNameOrSlug || '');
}

/**
 * UI palette for a side — same hydrated visual the court generator reads.
 * Fallback is roster/sim colors when the side is not the custom program.
 * @param {string} teamNameOrSlug
 * @param {object|string} [fallbackColors]
 * @returns {{ primary_color: string|null, secondary_color: string|null }}
 */
function resolveTeamBuilderPaletteColors(teamNameOrSlug, fallbackColors) {
  var fb = fallbackColors;
  if (typeof fb === 'string') fb = { primary_color: fb };
  fb = fb || {};
  if (_tbChromeSnapshotByKey) {
    var chrome = lookupTeamChrome(teamNameOrSlug, fb);
    return {
      primary_color: chrome.primary_color || fb.primary_color || fb.primary || null,
      secondary_color: chrome.secondary_color || fb.secondary_color || fb.secondary || null,
    };
  }
  if (!_tbVisualReady) {
    try {
      ensureTeamBuilderVisualReady();
    } catch (e) { /* ignore */ }
  }
  var visual = _activeTeamBuilderVisual;
  if (!visual && typeof getActiveTeamBuilderVisual === 'function') {
    visual = getActiveTeamBuilderVisual();
  }
  if (visual && teamBuilderVisualMatchesName(visual, teamNameOrSlug)) {
    return {
      primary_color: visual.primary_color || visual.primary || fb.primary_color || fb.primary || null,
      secondary_color:
        visual.secondary_color || visual.secondary || fb.secondary_color || fb.secondary || null,
    };
  }
  return {
    primary_color: fb.primary_color || fb.primary || null,
    secondary_color: fb.secondary_color || fb.secondary || null,
  };
}

function _tbHexToRgbTriplet(hex) {
  if (!hex || typeof hex !== 'string') return null;
  var h = hex.trim();
  if (h.charAt(0) === '#') h = h.slice(1);
  if (h.length === 3) {
    h = h.split('').map(function (c) { return c + c; }).join('');
  }
  if (h.length !== 6) return null;
  var n = parseInt(h, 16);
  if (!Number.isFinite(n)) return null;
  return ((n >> 16) & 255) + ', ' + ((n >> 8) & 255) + ', ' + (n & 255);
}

function _tbChromeGateIsStrictEnv() {
  try {
    if (typeof API_CONFIG !== 'undefined' && typeof API_CONFIG.isCaptureEnv === 'function') {
      return !!API_CONFIG.isCaptureEnv();
    }
  } catch (e) { /* ignore */ }
  try {
    var host =
      (typeof window !== 'undefined' && window.location && window.location.hostname) || '';
    return host === 'localhost' || host === '127.0.0.1';
  } catch (e2) {
    return false;
  }
}

/**
 * Hydrate gate for chrome paint. Dev/staging: throw so a new entry point fails
 * immediately. Production: log only — same observe-only trade as the server
 * detector; the DOM leak detector reports the cosmetic miss.
 * @returns {boolean} true when paint may proceed
 */
function _assertTeamBuilderVisualReadyForChrome() {
  var fid = _franchiseIdFromLocation();
  if (!fid) return true;
  if (_tbVisualReady) return true;
  var msg =
    '[TB] game chrome applied before Team Builder visual hydration settled ' +
    '(franchise_id present). Await ensureTeamBuilderVisualReady() / applyTeamVibrantDocumentVars().';
  if (_tbChromeGateIsStrictEnv()) {
    throw new Error(msg);
  }
  try {
    console.error(msg);
  } catch (e) { /* ignore */ }
  return false;
}

/**
 * Sync chrome paint — requires hydrate already settled.
 * Dev/staging: throws if the gate is unset. Production: logs and paints best-effort.
 * Prefer applyTeamVibrantDocumentVars() (async) at call sites.
 */
function applyTeamVibrantDocumentVarsNow(homeName, awayName, homeColors, awayColors) {
  _assertTeamBuilderVisualReadyForChrome();
  if (typeof document === 'undefined' || !document.documentElement) return;
  var homePal = resolveTeamBuilderPaletteColors(homeName, homeColors);
  var awayPal = resolveTeamBuilderPaletteColors(awayName, awayColors);
  if (homePal.primary_color) {
    document.documentElement.style.setProperty('--home-vibrant-color', homePal.primary_color);
    var hr = _tbHexToRgbTriplet(homePal.primary_color);
    if (hr) document.documentElement.style.setProperty('--home-vibrant-rgb', hr);
  }
  if (awayPal.primary_color) {
    document.documentElement.style.setProperty('--away-vibrant-color', awayPal.primary_color);
    var ar = _tbHexToRgbTriplet(awayPal.primary_color);
    if (ar) document.documentElement.style.setProperty('--away-vibrant-rgb', ar);
  }
}

/**
 * Apply court chrome CSS vars from the hydrated palette (hex + rgb).
 * Awaits resolver-owned hydration when franchise_id is present, then paints.
 */
async function applyTeamVibrantDocumentVars(homeName, awayName, homeColors, awayColors) {
  await ensureTeamBuilderChromeSnapshot();
  applyTeamVibrantDocumentVarsNow(homeName, awayName, homeColors, awayColors);
}

/**
 * Labels + colours for a matchup — one producer after hydrate settles.
 * @param {{
 *   homeCore: string, awayCore: string,
 *   homeUrlDisplay?: string, awayUrlDisplay?: string,
 *   homeColors?: object, awayColors?: object,
 *   homeLabelEl?: Element|null, awayLabelEl?: Element|null,
 *   franchiseId?: string,
 * }} opts
 */
async function applyTeamBuilderMatchupChrome(opts) {
  opts = opts || {};
  await ensureTeamBuilderChromeSnapshot(opts.franchiseId);
  // Gate settled by await above; assert is a dev/staging belt for regressions.
  _assertTeamBuilderVisualReadyForChrome();
  var homeChrome = lookupTeamChrome(opts.homeCore || opts.homeUrlDisplay, {
    label: opts.homeUrlDisplay,
    primary_color: opts.homeColors && (opts.homeColors.primary_color || opts.homeColors.primary),
    secondary_color: opts.homeColors && (opts.homeColors.secondary_color || opts.homeColors.secondary),
  });
  var awayChrome = lookupTeamChrome(opts.awayCore || opts.awayUrlDisplay, {
    label: opts.awayUrlDisplay,
    primary_color: opts.awayColors && (opts.awayColors.primary_color || opts.awayColors.primary),
    secondary_color: opts.awayColors && (opts.awayColors.secondary_color || opts.awayColors.secondary),
  });
  var homeLabel = homeChrome.label;
  var awayLabel = awayChrome.label;
  if (opts.homeLabelEl) opts.homeLabelEl.textContent = homeLabel || '';
  if (opts.awayLabelEl) opts.awayLabelEl.textContent = awayLabel || '';
  await applyTeamVibrantDocumentVars(homeLabel, awayLabel, homeChrome, awayChrome);
  return { homeLabel: homeLabel, awayLabel: awayLabel, homeChrome: homeChrome, awayChrome: awayChrome };
}

/**
 * Total Team Builder chrome snapshot — every program in the league.
 *
 * Built ONLY after ensureTeamBuilderVisualReady(). Non-overlaid teams map to
 * their own core label/abbr/palette; the replaced slot maps to overlay chrome.
 * Consumers must read through lookupTeamChrome / ensureTeamBuilderChromeSnapshot
 * — never summary.teams[].colors or roster.primary_color directly.
 *
 * Indexed by core name, display label, team_id, object_id, and path slug so any
 * identity form resolves without an if-overlay branch at the call site.
 */
var _tbChromeSnapshot = null;
var _tbChromeSnapshotByKey = null;
var _tbChromeSnapshotFranchiseId = null;
var _tbChromeSnapshotPromise = null;
var _tbChromeSnapshotBuiltAt = 0;

function _tbChromeIndexKey(value) {
  if (value == null || value === '') return '';
  var s = String(value).trim();
  if (!s) return '';
  // ObjectIds and TEAM_ID slugs stay case-folded; names use normalizeTeamNameKey.
  if (/^[a-f0-9]{24}$/i.test(s)) return 'oid:' + s.toLowerCase();
  if (/^[A-Z0-9_]+$/.test(s) && s.indexOf('_') !== -1) return 'tid:' + s.toUpperCase();
  if (/^[A-Z0-9_]{3,}$/.test(s) && s === s.toUpperCase()) return 'tid:' + s;
  return 'name:' + normalizeTeamNameKey(s);
}

function _tbChromeIndexPut(map, key, entry) {
  if (!key || !entry) return;
  map[key] = entry;
}

function _tbChromeEntryFromTeamRow(row, visual) {
  var coreName = String((row && row.name) || '').trim();
  var label = String((row && row.display_name) || coreName).trim() || coreName;
  var isOverlay = !!(row && row.display_name && normalizeTeamNameKey(row.display_name) !== normalizeTeamNameKey(coreName));
  // Prefer overlay visual when this row is the replaced slot (authoritative colours).
  if (
    visual &&
    (teamBuilderVisualMatchesName(visual, coreName) || teamBuilderVisualMatchesName(visual, label))
  ) {
    isOverlay = true;
    label = String(visual.name || label).trim() || label;
  }
  var primary =
    (isOverlay && visual && (visual.primary_color || visual.primary)) ||
    (row && row.primary_color) ||
    null;
  var secondary =
    (isOverlay && visual && (visual.secondary_color || visual.secondary)) ||
    (row && row.secondary_color) ||
    null;
  var abbr =
    (isOverlay && visual && visual.abbreviation) ||
    (row && row.abbreviation) ||
    null;
  if (!abbr) {
    abbr =
      typeof deriveTeamAbbreviationFromName === 'function'
        ? deriveTeamAbbreviationFromName(label || coreName)
        : String(label || coreName || '')
            .replace(/[^A-Za-z0-9]/g, '')
            .slice(0, 3)
            .toUpperCase() || '???';
  }
  return {
    core_name: coreName,
    label: label,
    abbreviation: String(abbr).toUpperCase(),
    primary_color: primary,
    secondary_color: secondary,
    team_id: row && row.team_id ? String(row.team_id) : null,
    object_id: row && row.object_id ? String(row.object_id) : null,
    is_overlay: isOverlay,
  };
}

function _tbChromeBuildIndex(entries) {
  var map = Object.create(null);
  for (var i = 0; i < entries.length; i++) {
    var e = entries[i];
    if (!e) continue;
    _tbChromeIndexPut(map, _tbChromeIndexKey(e.core_name), e);
    _tbChromeIndexPut(map, _tbChromeIndexKey(e.label), e);
    if (e.team_id) _tbChromeIndexPut(map, _tbChromeIndexKey(e.team_id), e);
    if (e.object_id) _tbChromeIndexPut(map, _tbChromeIndexKey(e.object_id), e);
    if (e.abbreviation) _tbChromeIndexPut(map, 'abbr:' + String(e.abbreviation).toUpperCase(), e);
    if (typeof nameToTeamSlug === 'function') {
      if (e.core_name) _tbChromeIndexPut(map, 'slug:' + nameToTeamSlug(e.core_name), e);
      if (e.label) _tbChromeIndexPut(map, 'slug:' + nameToTeamSlug(e.label), e);
    }
  }
  return map;
}

/**
 * Await hydrate, then build (or reuse) the total 128-program chrome map.
 * @param {string} [franchiseId]
 * @returns {Promise<{entries: object[], byKey: object, franchiseId: string|null, builtAt: number}>}
 */
async function ensureTeamBuilderChromeSnapshot(franchiseId) {
  var fid = franchiseId || _franchiseIdFromLocation() || null;
  await ensureTeamBuilderVisualReady(fid);
  if (
    _tbChromeSnapshot &&
    _tbChromeSnapshotByKey &&
    String(_tbChromeSnapshotFranchiseId || '') === String(fid || '')
  ) {
    return {
      entries: _tbChromeSnapshot,
      byKey: _tbChromeSnapshotByKey,
      franchiseId: _tbChromeSnapshotFranchiseId,
      builtAt: _tbChromeSnapshotBuiltAt,
    };
  }
  if (_tbChromeSnapshotPromise) return _tbChromeSnapshotPromise;

  _tbChromeSnapshotPromise = (async function () {
    var t0 =
      typeof performance !== 'undefined' && performance.now
        ? performance.now()
        : Date.now();
    var rows = [];
    try {
      var base =
        typeof API_CONFIG !== 'undefined' && API_CONFIG.buildUrl
          ? API_CONFIG.buildUrl('/teams')
          : '/teams';
      var url = fid ? base + '?franchise_id=' + encodeURIComponent(fid) : base;
      var headers =
        typeof API_CONFIG !== 'undefined' && API_CONFIG.getAuthHeaders
          ? API_CONFIG.getAuthHeaders()
          : {};
      var res = await fetch(url, { headers: headers });
      if (res.ok) {
        var data = await res.json();
        if (Array.isArray(data)) rows = data;
      }
    } catch (e) {
      try {
        console.error('[TB] chrome snapshot /teams fetch failed', e);
      } catch (e2) { /* ignore */ }
    }

    if (!rows.length) {
      _tbChromeSnapshotPromise = null;
      throw new Error('[TB] chrome snapshot refused empty /teams response');
    }

    var visual = getActiveTeamBuilderVisual();
    var entries = [];
    for (var i = 0; i < rows.length; i++) {
      entries.push(_tbChromeEntryFromTeamRow(rows[i], visual));
    }
    // If overlay visual exists but /teams missed the display_name stamp, force it.
    if (visual && visual.replaced_name) {
      var replacedKey = _tbChromeIndexKey(visual.replaced_name);
      var hit = null;
      for (var j = 0; j < entries.length; j++) {
        if (_tbChromeIndexKey(entries[j].core_name) === replacedKey) {
          hit = entries[j];
          break;
        }
      }
      if (hit) {
        hit.is_overlay = true;
        hit.label = String(visual.name || hit.label).trim() || hit.label;
        hit.abbreviation = String(
          visual.abbreviation || hit.abbreviation || ''
        ).toUpperCase();
        hit.primary_color = visual.primary_color || visual.primary || hit.primary_color;
        hit.secondary_color =
          visual.secondary_color || visual.secondary || hit.secondary_color;
      }
    }

    _tbChromeSnapshot = entries;
    _tbChromeSnapshotByKey = _tbChromeBuildIndex(entries);
    _tbChromeSnapshotFranchiseId = fid;
    _tbChromeSnapshotBuiltAt =
      typeof performance !== 'undefined' && performance.now
        ? performance.now()
        : Date.now();
    var dt = _tbChromeSnapshotBuiltAt - t0;
    try {
      console.info(
        '[TB] chrome snapshot ready',
        entries.length,
        'programs',
        Math.round(dt) + 'ms',
        fid ? 'franchise=' + fid : 'no-franchise'
      );
    } catch (e3) { /* ignore */ }
    _tbChromeSnapshotPromise = null;
    return {
      entries: _tbChromeSnapshot,
      byKey: _tbChromeSnapshotByKey,
      franchiseId: _tbChromeSnapshotFranchiseId,
      builtAt: _tbChromeSnapshotBuiltAt,
      buildMs: dt,
    };
  })();

  try {
    return await _tbChromeSnapshotPromise;
  } catch (err) {
    _tbChromeSnapshotPromise = null;
    throw err;
  }
}

function getTeamBuilderChromeSnapshot() {
  if (!_tbChromeSnapshot || !_tbChromeSnapshotByKey) return null;
  return {
    entries: _tbChromeSnapshot,
    byKey: _tbChromeSnapshotByKey,
    franchiseId: _tbChromeSnapshotFranchiseId,
    builtAt: _tbChromeSnapshotBuiltAt,
  };
}

function clearTeamBuilderChromeSnapshot() {
  _tbChromeSnapshot = null;
  _tbChromeSnapshotByKey = null;
  _tbChromeSnapshotFranchiseId = null;
  _tbChromeSnapshotPromise = null;
  _tbChromeSnapshotBuiltAt = 0;
}

/**
 * Sync chrome lookup against the total map. Call only after
 * ensureTeamBuilderChromeSnapshot() has settled (or when no franchise_id).
 * @param {string} teamNameOrId
 * @param {object} [fallback]
 */
function lookupTeamChrome(teamNameOrId, fallback) {
  var fb = fallback || {};
  var fid = _franchiseIdFromLocation();
  if (fid && (!_tbChromeSnapshotByKey || !_tbVisualReady)) {
    _assertTeamBuilderVisualReadyForChrome();
  }
  var needle = teamNameOrId;
  if (needle == null || needle === '') {
    return {
      core_name: fb.core_name || '',
      label: fb.label || fb.name || '',
      abbreviation: fb.abbreviation || '???',
      primary_color: fb.primary_color || fb.primary || null,
      secondary_color: fb.secondary_color || fb.secondary || null,
      team_id: fb.team_id || null,
      object_id: fb.object_id || null,
      is_overlay: false,
    };
  }
  var map = _tbChromeSnapshotByKey;
  if (map) {
    var keys = [
      _tbChromeIndexKey(needle),
      'slug:' + (typeof nameToTeamSlug === 'function' ? nameToTeamSlug(needle) : ''),
      'abbr:' + String(needle).trim().toUpperCase(),
    ];
    for (var i = 0; i < keys.length; i++) {
      if (keys[i] && map[keys[i]]) return map[keys[i]];
    }
  }
  // Unknown needle (should not happen for the 128) — still return a full shape.
  var label = String(fb.label || fb.name || needle).trim();
  return {
    core_name: String(fb.core_name || needle).trim(),
    label: label,
    abbreviation:
      fb.abbreviation ||
      (typeof deriveTeamAbbreviationFromName === 'function'
        ? deriveTeamAbbreviationFromName(label)
        : String(label).replace(/[^A-Za-z0-9]/g, '').slice(0, 3).toUpperCase()) ||
      '???',
    primary_color: fb.primary_color || fb.primary || null,
    secondary_color: fb.secondary_color || fb.secondary || null,
    team_id: fb.team_id || null,
    object_id: fb.object_id || null,
    is_overlay: false,
  };
}

function normalizeTeamNameKey(name) {
  return String(name || '')
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ');
}

/** Shared empty token when a name yields no alnum chars (must match BE ABBR_EMPTY). */
var ABBR_EMPTY = '???';

/**
 * Fallback 3-letter token from a team name (alnum → slice(0,3) upper).
 * Same algorithm as BackEnd abbr_from_name — validation and rendering share this.
 * Prefer resolveTeamAbbreviation when a franchise overlay may apply.
 */
function deriveTeamAbbreviationFromName(name) {
  var clean = String(name || '').replace(/[^A-Za-z0-9]/g, '');
  return (clean.slice(0, 3) || ABBR_EMPTY).toUpperCase();
}

/**
 * Single abbreviation resolver (Team Builder chrome).
 * Overlay abbreviation when the franchise has one for this team; else slice(0,3).
 *
 * @param {string} name - display or core team name
 * @param {string} [teamId] - team ObjectId string when known
 */
function resolveTeamAbbreviation(name, teamId) {
  var visual = typeof getActiveTeamBuilderVisual === 'function' ? getActiveTeamBuilderVisual() : null;
  if (visual && visual.abbreviation) {
    var abbr = String(visual.abbreviation).trim().toUpperCase().slice(0, 3);
    if (abbr) {
      var oid = visual.replaced_object_id || visual.object_id;
      if (teamId != null && oid && String(teamId) === String(oid)) return abbr;
      if (typeof teamBuilderVisualMatchesName === 'function' && teamBuilderVisualMatchesName(visual, name)) {
        return abbr;
      }
    }
  }
  return deriveTeamAbbreviationFromName(name);
}

function teamBuilderVisualMatchesName(visual, teamNameOrSlug) {
  if (!visual || !teamNameOrSlug) return false;
  if (visual.asset_strategy && visual.asset_strategy !== 'generated' && !visual.is_custom) {
    return false;
  }
  if (!(visual.asset_strategy === 'generated' || visual.is_custom)) return false;
  var needle = normalizeTeamNameKey(teamNameOrSlug);
  if (!needle || needle === 'general') return false;
  // Match display name, abbrev, or replaced core name — court URL may pass any for chrome.
  // (short_name removed: never used as a lookup key; callers pass name / replaced_name / slug.)
  var candidates = [visual.name, visual.abbreviation, visual.replaced_name];
  for (var i = 0; i < candidates.length; i++) {
    if (candidates[i] && normalizeTeamNameKey(candidates[i]) === needle) return true;
  }
  // Slug form of the custom name (spaces → underscores)
  if (visual.name && nameToTeamSlug(visual.name) === String(teamNameOrSlug).trim().toLowerCase()) {
    return true;
  }
  if (visual.replaced_name && nameToTeamSlug(visual.replaced_name) === String(teamNameOrSlug).trim().toLowerCase()) {
    return true;
  }
  return false;
}

function generatedTeamAssetDataUrl(visual, assetKey) {
  var jerseyPreset = Number(visual.jersey_preset);
  if (jerseyPreset !== 2) jerseyPreset = 1;
  var opts = {
    name: visual.name || 'Custom Program',
    abbreviation: visual.abbreviation,
    mascot: visual.mascot,
    primary: visual.primary_color || visual.primary || '#27408E',
    secondary: visual.secondary_color || visual.secondary || '#15181f',
    jerseyPreset: jerseyPreset,
    asset_strategy: 'generated',
    is_custom: true,
  };
  // Note: `court` is not generated here for gameplay — see getTeamAssetPath.
  // Wizard Colors preview calls TeamGeneratedArt.courtPreviewDataUrl directly.
  if (typeof window !== 'undefined' && window.TeamGeneratedArt) {
    if (assetKey === 'logo_square' || assetKey === 'mark') return window.TeamGeneratedArt.markDataUrl(opts);
    if (assetKey === 'banner_card') return window.TeamGeneratedArt.bannerCardDataUrl(opts);
    if (assetKey === 'banner_primary' || assetKey === 'background') {
      return window.TeamGeneratedArt.bannerPrimaryDataUrl(opts);
    }
    if (assetKey === 'jersey') return window.TeamGeneratedArt.jerseyPreviewDataUrl(opts);
  }
  // Inline fallback when TeamGeneratedArt is not loaded — flat primary, no gradient bar.
  var initials = opts.abbreviation
    ? String(opts.abbreviation).trim().toUpperCase().slice(0, 3)
    : (typeof resolveTeamAbbreviation === 'function'
        ? resolveTeamAbbreviation(opts.name, opts.teamId || opts.object_id)
        : deriveTeamAbbreviationFromName(opts.name || 'TB'));
  if (!initials || initials === ABBR_EMPTY) initials = 'TB';
  var w = assetKey === 'logo_square' || assetKey === 'mark' ? 128 : 400;
  var h = assetKey === 'logo_square' || assetKey === 'mark' ? 128 : 141;
  var svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="' +
    w +
    '" height="' +
    h +
    '" viewBox="0 0 ' +
    w +
    ' ' +
    h +
    '">' +
    '<rect width="' +
    w +
    '" height="' +
    h +
    '" fill="' +
    opts.primary +
    '"/>' +
    '<text x="' +
    w / 2 +
    '" y="' +
    (h / 2 + 8) +
    '" text-anchor="middle" fill="#ffffff" font-family="Bebas Neue Pro, Bebas Neue, sans-serif" font-size="' +
    (h > 100 ? 42 : 28) +
    '">' +
    (assetKey === 'logo_square' || assetKey === 'mark'
      ? initials
      : String(opts.name || 'Custom Program')
          .toUpperCase()
          .replace(/[<>&]/g, '')) +
    '</text></svg>';
  return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

/**
 * Filesystem team asset path (core programs). Used as the no-op pass-through.
 * Unknown / custom slugs fall back to generic art (§1: never broken).
 */
function filesystemTeamAssetPath(teamNameOrSlug, assetKey) {
  var slug = (teamNameOrSlug && typeof teamNameOrSlug === 'string' && teamNameOrSlug.indexOf(' ') === -1 && teamNameOrSlug.indexOf('-') === -1)
    ? teamNameOrSlug.toLowerCase()
    : nameToTeamSlug(teamNameOrSlug);
  var spec = TEAM_ASSET_SPEC[assetKey];
  if (!spec) return '/images/teams/general/general_logo_square.png';
  var useSlug = slug || spec.fallbackSlug;
  if (!useSlug || useSlug === 'general' || !CORE_TEAM_ASSET_SLUGS[useSlug]) {
    useSlug = spec.fallbackSlug || 'general';
  }
  return '/images/teams/' + useSlug + '/' + useSlug + '_' + assetKey + '.' + spec.ext;
}

/**
 * Build path for a team asset. Franchise-aware shared producer (§3.3 / Task B #8).
 *
 * Asset strategy is **per-key**, not per-team:
 *  - banner / logo / background → generated data URL for the custom program
 *  - court → sync fallback to ``general_court.jpg`` for custom programs.
 *    Authoritative gameplay court is ``resolveCourtImagePath`` in gameScene.js,
 *    which async-generates a blob URL via TeamCourtGenerator / TeamGeneratedArt
 *    (3333×2083 canvas). Phaser's loader rejects data: URIs; use blob: only.
 *
 * Non-overlay franchises / other teams: filesystem path (mandatory no-op).
 *
 * @param {string} teamNameOrSlug
 * @param {string} assetKey - court | logo_square | background | banner_primary | banner_card
 * @param {object} [visualOverride] - optional overlay (e.g. mode-select multi-slot cards)
 */
function getTeamAssetPath(teamNameOrSlug, assetKey, visualOverride) {
  // Prefer total chrome snapshot when ready — overlay entry drives generated art
  // with the display label (agreement with .team-name / Sim Exp).
  if (!visualOverride && _tbChromeSnapshotByKey && teamNameOrSlug) {
    var chrome = lookupTeamChrome(teamNameOrSlug);
    if (chrome && chrome.is_overlay) {
      if (assetKey === 'court') {
        return filesystemTeamAssetPath(null, 'court');
      }
      return generatedTeamAssetDataUrl(
        {
          name: chrome.label,
          abbreviation: chrome.abbreviation,
          primary_color: chrome.primary_color,
          secondary_color: chrome.secondary_color,
          jersey_preset: (_activeTeamBuilderVisual && _activeTeamBuilderVisual.jersey_preset) || 1,
          mascot: (_activeTeamBuilderVisual && _activeTeamBuilderVisual.mascot) || '',
          asset_strategy: 'generated',
          is_custom: true,
        },
        assetKey
      );
    }
  }
  var visual = visualOverride || getActiveTeamBuilderVisual();
  if (teamBuilderVisualMatchesName(visual, teamNameOrSlug)) {
    // Sync fallback only — Phaser loads custom courts via resolveCourtImagePath
    // (async blob URL from TeamCourtGenerator). Never return data: here.
    if (assetKey === 'court') {
      return filesystemTeamAssetPath(null, 'court');
    }
    return generatedTeamAssetDataUrl(visual, assetKey);
  }
  return filesystemTeamAssetPath(teamNameOrSlug, assetKey);
}

/**
 * Coach portrait path. Custom programs inherit the replaced slot's Core-8 coach
 * art when the replaced program is Core-8; otherwise generic Sammy.
 * @param {string} teamName
 * @param {string} [coach] - 'Sammy' | 'Duke' (default Sammy)
 * @param {object} [visualOverride]
 */
function getTeamCoachAssetPath(teamName, coach, visualOverride) {
  var which = coach === 'Duke' ? 'Duke' : 'Sammy';
  var visual = visualOverride || getActiveTeamBuilderVisual();
  var lookupName = teamName;
  if (teamBuilderVisualMatchesName(visual, teamName) && visual.replaced_name) {
    lookupName = visual.replaced_name;
  }
  var formatted = typeof formatTeamName === 'function' ? formatTeamName(lookupName) : lookupName;
  var abbr = TEAM_COACH_ABBR[formatted] || TEAM_COACH_ABBR[lookupName];
  if (!abbr) {
    return which === 'Duke' ? '' : GENERIC_TEAM_SAMMY;
  }
  return '/images/coaches/' + abbr + '/' + which + '-' + abbr + '.png';
}

// Map stored year values to UI abbreviations (JH, FR, SO, JR, SR, GR)
const yearMap = {
  jh: 'JH',
  freshman: 'FR',
  fr: 'FR',
  sophomore: 'SO',
  so: 'SO',
  junior: 'JR',
  jr: 'JR',
  senior: 'SR',
  sr: 'SR',
  graduate: 'GR',
  grad: 'GR',
};

// Convert a numeric height (in inches) to feet-inches format
function formatHeight(raw) {
  const inches = parseInt(raw, 10);
  if (isNaN(inches)) return raw ?? '--';
  const ft = Math.floor(inches / 12);
  const inch = inches % 12;
  return `${ft}'${inch}"`;
}

const positionOrder = ['PG', 'SG', 'SF', 'PF', 'C'];

// Derive the best position and rating from a position_ratings object
function getBestPosition(positionRatings = {}) {
  let bestPos = '-';
  let bestRating = null;
  positionOrder.forEach(pos => {
    const rating = positionRatings[pos];
    if (rating == null) return;
    if (bestRating === null || rating > bestRating) {
      bestRating = rating;
      bestPos = pos;
    }
  });
  return { pos: bestPos, rating: bestRating };
}

/**
 * Display name with jersey prefix e.g. "#32 Ronnie Rozier". Jersey 0 is valid.
 * @param {*} jersey - number or string; null/undefined/'' skips prefix
 * @param {string} rawName - full name without jersey
 */
function formatNameWithJersey(jersey, rawName) {
  const name = rawName != null && rawName !== '' ? String(rawName).trim() : '';
  if (jersey === null || jersey === undefined || jersey === '') {
    return name || '—';
  }
  const n = typeof jersey === 'number' ? jersey : parseInt(String(jersey).trim(), 10);
  if (Number.isNaN(n)) {
    return name || '—';
  }
  const prefix = '#' + n;
  return name ? prefix + ' ' + name : prefix;
}

function getCurrentRelativeUrl() {
  return `${window.location.pathname}${window.location.search}${window.location.hash || ''}`;
}

function getSafeReturnUrl(rawReturnUrl) {
  if (!rawReturnUrl || typeof rawReturnUrl !== 'string') return null;
  try {
    const parsed = new URL(rawReturnUrl, window.location.origin);
    if (parsed.origin !== window.location.origin) return null;
    if (!parsed.pathname || !parsed.pathname.startsWith('/')) return null;
    return `${parsed.pathname}${parsed.search}${parsed.hash || ''}`;
  } catch (e) {
    return null;
  }
}

function buildFranchiseLockerRoomUrl(franchiseId, teamId, extraParams = {}) {
  const params = new URLSearchParams();
  params.set('mode', 'franchise');
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (teamId) params.set('team_id', teamId);
  Object.keys(extraParams || {}).forEach((key) => {
    if (extraParams[key] != null && extraParams[key] !== '') {
      params.set(key, extraParams[key]);
    }
  });
  const query = params.toString();
  return query ? `/franchise-command-center.html?${query}` : '/franchise-command-center.html';
}

function resolveFranchiseLockerRoomUrl(options = {}) {
  const params = options.params instanceof URLSearchParams
    ? options.params
    : new URLSearchParams(window.location.search);
  const extraParams = options.extraParams || {};
  const explicitReturnUrl = options.returnUrl != null ? options.returnUrl : params.get('return_url');
  const safeReturnUrl = getSafeReturnUrl(explicitReturnUrl);

  if (safeReturnUrl) {
    if (!extraParams || !Object.keys(extraParams).length) return safeReturnUrl;
    try {
      const merged = new URL(safeReturnUrl, window.location.origin);
      Object.keys(extraParams).forEach(function (key) {
        if (extraParams[key] != null && extraParams[key] !== '') {
          merged.searchParams.set(key, extraParams[key]);
        }
      });
      return `${merged.pathname}${merged.search}${merged.hash || ''}`;
    } catch (_e) {
      return safeReturnUrl;
    }
  }

  const franchiseId = options.franchiseId != null ? options.franchiseId : params.get('franchise_id');
  const teamId = options.teamId != null ? options.teamId : params.get('team_id');
  return buildFranchiseLockerRoomUrl(franchiseId, teamId, extraParams);
}

// Canonical attribute bar color scale — see Styleguide.md ### Attribute Bar Scale
// Do not add a fifth color tier. All values 81+ including 100+ return light blue.
/**
 * @param {number} scaledValue Bucket from Math.ceil(rawAttribute / 10) for anchor storage on a 0–100+ raw scale (e.g. raw 81 → 9 → light blue). Values above 10 (raw > 100) still map to light blue.
 * @returns {string} Hex fill color for attribute / position-rating bars.
 */
function getAttrColor(scaledValue) {
  const s = Number(scaledValue);
  if (!Number.isFinite(s)) return '#ff6d6d';
  if (s >= 9) return '#4A90D9';
  if (s >= 7) return '#34EC27';
  if (s >= 5) return '#FFD700';
  return '#ff6d6d';
}

// Canonical position shot weights color scale — see Styleguide.md
function getPswColor(pct) {
  if (pct > 35) return '#4A90D9';
  if (pct >= 21) return '#34EC27';
  if (pct >= 11) return '#FFD700';
  return '#ff6d6d';
}

/**
 * Canonical playbook CMD (effectiveness) band class.
 * Thresholds and colors: css/playbook-cmd.css — blue ≥70, green ≥40, yellow <40.
 */
function getPlaybookCmdClass(value) {
  const numeric = Number(value || 0);
  if (numeric >= 70) return 'is-good';
  if (numeric >= 40) return 'is-mid';
  return 'is-low';
}

/** Set Plays focus rank: inside → attack → outside → other. */
function getSetPlayFocusRank(focus) {
  const key = String(focus || '').toLowerCase();
  if (key === 'inside') return 0;
  if (key === 'attack') return 1;
  if (key === 'outside') return 2;
  return 3;
}

/**
 * Shared Set Plays display order (Playbooks editor, FCC, Set Lineup).
 * percentPrimary true (read-only / post-save): % desc → focus → CMD → name → apiIndex
 * percentPrimary false (editor while editing): focus → % desc → CMD → name → apiIndex
 */
function compareSetPlaysForDisplay(a, b, options) {
  const percentPrimary = !options || options.percentPrimary !== false;
  const pctA = Number(a && a.percentage || 0);
  const pctB = Number(b && b.percentage || 0);
  const focusA = getSetPlayFocusRank(a && (a.focus != null ? a.focus : a.play_focus));
  const focusB = getSetPlayFocusRank(b && (b.focus != null ? b.focus : b.play_focus));
  if (percentPrimary) {
    if (pctB !== pctA) return pctB - pctA;
    if (focusA !== focusB) return focusA - focusB;
  } else {
    if (focusA !== focusB) return focusA - focusB;
    if (pctB !== pctA) return pctB - pctA;
  }
  const cmdA = Number((a && (a.effectiveness != null ? a.effectiveness : a.cmd)) || 0);
  const cmdB = Number((b && (b.effectiveness != null ? b.effectiveness : b.cmd)) || 0);
  if (cmdB !== cmdA) return cmdB - cmdA;
  const nameCmp = String((a && a.name) || '').localeCompare(String((b && b.name) || ''));
  if (nameCmp) return nameCmp;
  return Number((a && a._apiIndex) || 0) - Number((b && b._apiIndex) || 0);
}

function renderShotWeights(container, shotWeights, compact = false) {
  if (!container) return;
  container.classList.add('psw-root');
  container.setAttribute('data-compact', compact ? 'true' : 'false');

  if (!shotWeights || (!shotWeights.playbooks && !shotWeights.playcall_center)) {
    container.innerHTML = '<p class="psw-unavailable">Shot weight data unavailable.</p>';
    return;
  }

  const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];

  function renderGroup(label, data) {
    if (!data) return '';
    const values = POSITIONS.map((pos) => ({ pos, pct: data[pos] ?? 0 }));
    const maxPct = Math.max(...values.map((value) => value.pct));

    const pills = values.map(({ pos, pct }) => {
      const color = getPswColor(pct);
      const isDominant = pct === maxPct;
      const pillStyle = `border: 1px solid rgba(255,255,255,0.08);`;
      const valStyle = `color: ${color};`;
      const accentStyle = isDominant
        ? `background: ${color}; opacity: 1;`
        : `opacity: 0;`;
      return `
        <div class="psw-pill" style="${pillStyle}">
          <div class="psw-pill-pos">${pos}</div>
          <div class="psw-pill-val" style="${valStyle}">${pct}%</div>
          <div class="psw-pill-accent" style="${accentStyle}"></div>
        </div>
      `;
    }).join('');

    return `
      <div class="psw-group">
        <div class="psw-group-label">${label}</div>
        <div class="psw-strip">${pills}</div>
      </div>
    `;
  }

  container.innerHTML = `
    ${renderGroup('PLAYBOOKS', shotWeights.playbooks)}
    ${renderGroup('PLAYCALL CENTER', shotWeights.playcall_center)}
  `;
}

// Team Builder replaced-name DOM leak detector (dev/staging). See teamBuilderLeakDetector.js.
(function loadTeamBuilderLeakDetector() {
  if (typeof document === 'undefined') return;
  if (window.TeamBuilderLeakDetector) return;
  var s = document.createElement('script');
  s.src = '/js/shared/teamBuilderLeakDetector.js';
  s.async = true;
  document.head.appendChild(s);
})();
