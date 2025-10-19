/**
 * Update strategy bars (tempo and aggression) on the scoreboard
 * Called at the start of each turn to reflect current team settings
 */

/**
 * Convert strategy setting (0-4) to bar fill percentage
 * 0 -> 20%, 1 -> 40%, 2 -> 60%, 3 -> 80%, 4 -> 100%
 */
function settingToPercentage(value) {
  return ((value + 1) * 20);
}

/**
 * Update strategy bars for both teams
 * @param {Object} turnData - Turn data containing strategy settings
 * @param {string} homeTeamId - Home team ID for determining which team is which
 */
export function updateStrategyBars(turnData, homeTeamId) {
  // Get tempo and aggression values from turn data
  // These come from the offensive and defensive teams' strategy settings
  
  console.log('📊 updateStrategyBars called:', {
    turnData_keys: Object.keys(turnData),
    offense_tempo: turnData.offense_tempo,
    offense_aggression: turnData.offense_aggression,
    defense_tempo: turnData.defense_tempo,
    defense_aggression: turnData.defense_aggression
  });
  
  const offenseTeamId = turnData.possession_team_id || turnData.starting_possession_team_id;
  const isHomeOnOffense = homeTeamId && String(offenseTeamId) === String(homeTeamId);
  
  // Determine which team is offense/defense
  let homeTempo, homeAggression, awayTempo, awayAggression;
  
  if (turnData.offense_tempo !== undefined && turnData.defense_aggression !== undefined) {
    // Use offense tempo and defense aggression from turn data
    if (isHomeOnOffense) {
      homeTempo = turnData.offense_tempo;
      homeAggression = turnData.offense_aggression || 2; // Default to normal
      awayTempo = turnData.defense_tempo || 2; // Default to normal
      awayAggression = turnData.defense_aggression;
    } else {
      awayTempo = turnData.offense_tempo;
      awayAggression = turnData.offense_aggression || 2;
      homeTempo = turnData.defense_tempo || 2;
      homeAggression = turnData.defense_aggression;
    }
    
    console.log('✅ Using turn data strategy values');
  } else {
    // Fallback: use default values
    console.warn('⚠️ No strategy data in turn, using defaults');
    homeTempo = 2;
    homeAggression = 2;
    awayTempo = 2;
    awayAggression = 2;
  }
  
  // Update home bars
  const homeTempBar = document.querySelector('#home-tempo-bar .strategy-bar-fill');
  const homeAggrBar = document.querySelector('#home-aggression-bar .strategy-bar-fill');
  if (homeTempBar) homeTempBar.style.height = `${settingToPercentage(homeTempo)}%`;
  if (homeAggrBar) homeAggrBar.style.height = `${settingToPercentage(homeAggression)}%`;
  
  // Update away bars
  const awayTempoBar = document.querySelector('#away-tempo-bar .strategy-bar-fill');
  const awayAggrBar = document.querySelector('#away-aggression-bar .strategy-bar-fill');
  if (awayTempoBar) awayTempoBar.style.height = `${settingToPercentage(awayTempo)}%`;
  if (awayAggrBar) awayAggrBar.style.height = `${settingToPercentage(awayAggression)}%`;
  
  console.log('📊 Strategy bars updated:', {
    home: { tempo: homeTempo, aggression: homeAggression },
    away: { tempo: awayTempo, aggression: awayAggression }
  });
}

