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
 * Set the session Team Builder visual. FranchiseLS is an optional warm cache only.
 */
function setActiveTeamBuilderVisual(visual) {
  _activeTeamBuilderVisual = visual || null;
}

/**
 * Active Team Builder visual overlay for the franchise in the URL (or null).
 * Prefers in-memory hydrate from franchise payload; localStorage is cache only.
 * Pass-through no-op when absent — same property as the §3.2 name resolver.
 */
function getActiveTeamBuilderVisual() {
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
 * @param {object} data - FCC /me, mode-select card, Apply response, etc.
 * @param {string} [franchiseId]
 * @returns {object|null} visual or null when not a custom program
 */
function hydrateTeamBuilderVisualFromFranchisePayload(data, franchiseId) {
  if (!data) {
    setActiveTeamBuilderVisual(null);
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
    return null;
  }
  var name = data.team || data.user_team_id || data.name || '';
  var jerseyPreset = Number(data.jersey_preset);
  if (jerseyPreset !== 2) jerseyPreset = 1;
  var visual = {
    name: name,
    abbreviation: data.abbreviation,
    mascot: data.mascot || '',
    primary_color: data.primary_color || data.primary,
    secondary_color: data.secondary_color || data.secondary,
    jersey_preset: jerseyPreset,
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
  return visual;
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
 *  - court → always filesystem ``general_court.jpg`` for custom programs until
 *    Team Builder §6.3 ships a real court generator (3333×2083 + marking geometry).
 *    Phaser's loader rejects data URIs; the Colors-step SVG is a preview swatch
 *    only and must not become the gameplay surface.
 *
 * Non-overlay franchises / other teams: filesystem path (mandatory no-op).
 *
 * @param {string} teamNameOrSlug
 * @param {string} assetKey - court | logo_square | background | banner_primary | banner_card
 * @param {object} [visualOverride] - optional overlay (e.g. mode-select multi-slot cards)
 */
function getTeamAssetPath(teamNameOrSlug, assetKey, visualOverride) {
  var visual = visualOverride || getActiveTeamBuilderVisual();
  if (teamBuilderVisualMatchesName(visual, teamNameOrSlug)) {
    // Temporary: §6.3 court generator replaces this — its canvas output can
    // feed Phaser directly. Until then, never hand a data URI to load.image.
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
