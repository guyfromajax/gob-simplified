function formatTeamName(name) {
  return (name || '')
    .toLowerCase()
    .replace(/_/g, ' ')
    .split(' ')
    .map(w => w.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join('-'))
    .join(' ');
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
