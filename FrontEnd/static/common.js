function formatTeamName(name) {
  return (name || '')
    .toLowerCase()
    .replace(/_/g, ' ')
    .split(' ')
    .map(w => w.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join('-'))
    .join(' ');
}

/**
 * Derive team_slug from team name for asset paths. Matches backend rules:
 * lowercase, spaces → underscores, remove punctuation, hyphens → underscores.
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
  banner_primary: { ext: 'jpg', fallbackSlug: 'general' }
};

/**
 * Build path for a team asset. Uses team_slug if provided, else derives from team name.
 * @param {string} teamNameOrSlug - Team display name or team_slug (from API)
 * @param {string} assetKey - One of: court, logo_square, background, banner_primary
 * @returns {string} Path e.g. /images/teams/bentley_truman/bentley_truman_court.jpg
 */
function getTeamAssetPath(teamNameOrSlug, assetKey) {
  var slug = (teamNameOrSlug && typeof teamNameOrSlug === 'string' && teamNameOrSlug.indexOf(' ') === -1 && teamNameOrSlug.indexOf('-') === -1)
    ? teamNameOrSlug.toLowerCase()
    : nameToTeamSlug(teamNameOrSlug);
  var spec = TEAM_ASSET_SPEC[assetKey];
  if (!spec) return '/images/teams/general/general_logo_square.png';
  var useSlug = slug || spec.fallbackSlug;
  var base = '/images/teams/' + useSlug + '/' + useSlug + '_' + assetKey + '.' + spec.ext;
  return base;
}

// Map full year strings to abbreviations
const yearMap = {
  senior: 'SR',
  junior: 'JR',
  sophomore: 'SO',
  freshman: 'FR',
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
  const explicitReturnUrl = options.returnUrl != null ? options.returnUrl : params.get('return_url');
  const safeReturnUrl = getSafeReturnUrl(explicitReturnUrl);
  if (safeReturnUrl) return safeReturnUrl;

  const franchiseId = options.franchiseId != null ? options.franchiseId : params.get('franchise_id');
  const teamId = options.teamId != null ? options.teamId : params.get('team_id');
  return buildFranchiseLockerRoomUrl(franchiseId, teamId, options.extraParams || {});
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
