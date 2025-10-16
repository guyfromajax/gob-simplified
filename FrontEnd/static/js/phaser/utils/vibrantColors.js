/**
 * Vibrant color mappings for GOB teams
 * These are boosted versions of team primary colors for UI accents
 * Original colors remain in team JSON files - these are display-only
 */

export const VIBRANT_COLORS = {
  "Bentley-Truman": "#5080ff",      // Boosted blue: #4066b2 → #5080ff
  "Four Corners": "#ffcc66",        // Boosted gold/tan: #c0976a → #ffcc66
  "Lancaster": "#ff6200",           // Boosted orange: #d24a1b → #ff6200
  "Little York": "#9945ff",         // Boosted purple: #65308e → #9945ff
  "Morristown": "#ff2233",          // Boosted red: #ec1d28 → #ff2233
  "Ocean City": "#4444ff",          // Boosted dark blue: #2a2168 → #4444ff
  "South Lancaster": "#cc3322",     // Boosted maroon: #7c2b24 → #cc3322
  "Xavien": "#00cc44"               // Boosted green: #016837 → #00cc44
};

/**
 * Get vibrant color for a team name
 * @param {string} teamName - Team name (e.g., "Lancaster", "Four Corners")
 * @returns {string} Vibrant hex color
 */
export function getVibrantColor(teamName) {
  return VIBRANT_COLORS[teamName] || "#ff6200"; // Default to GOB orange
}

/**
 * Apply vibrant colors to court UI elements based on home/away teams
 * @param {string} homeTeam - Home team name
 * @param {string} awayTeam - Away team name
 */
export function applyVibrantColors(homeTeam, awayTeam) {
  const homeColor = getVibrantColor(homeTeam);
  const awayColor = getVibrantColor(awayTeam);
  
  // Apply home team color to borders and home-specific UI
  document.documentElement.style.setProperty('--home-vibrant-color', homeColor);
  document.documentElement.style.setProperty('--away-vibrant-color', awayColor);
  
  console.log('🎨 Applied vibrant colors:', {
    homeTeam,
    homeColor,
    awayTeam,
    awayColor
  });
}

