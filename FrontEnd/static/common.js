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
