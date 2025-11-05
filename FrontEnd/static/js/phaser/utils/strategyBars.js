/**
 * Update strategy bars (tempo and aggression) on the scoreboard
 * Called at the start of each turn to reflect current team settings
 */

/**
 * Convert tempo call to bar fill percentage
 * slow -> 20%, normal -> 60%, fast -> 100%
 */
function tempoToPercentage(tempoCall) {
  if (tempoCall === 'slow') return 20;
  if (tempoCall === 'fast') return 100;
  return 60; // normal or default
}

/**
 * Convert aggression call to bar fill percentage
 * passive -> 20%, normal -> 60%, aggressive -> 100%
 */
function aggressionToPercentage(aggressionCall) {
  if (aggressionCall === 'passive') return 20;
  if (aggressionCall === 'aggressive') return 100;
  return 60; // normal or default
}

/**
 * Update strategy bars for both teams
 * @param {Object} turnData - Turn data containing strategy settings
 * @param {string} homeTeamId - Home team ID for determining which team is which
 */
export function updateStrategyBars(turnData, homeTeamId) {
  // Get tempo and aggression values from turn data
  // These come from the offensive and defensive teams' strategy settings
  
  const offenseTeamId = turnData.possession_team_id || turnData.starting_possession_team_id;
  const isHomeOnOffense = homeTeamId && String(offenseTeamId) === String(homeTeamId);
  
  // Determine which team is offense/defense using actual calls (slow/normal/fast, passive/normal/aggressive)
  let homeTempoCall, homeAggrCall, awayTempoCall, awayAggrCall;
  
  if (turnData.offense_tempo_call && turnData.offense_aggression_call && turnData.defense_tempo_call && turnData.defense_aggression_call) {
    // Use actual tempo and aggression calls from turn data
    if (isHomeOnOffense) {
      homeTempoCall = turnData.offense_tempo_call;
      homeAggrCall = turnData.offense_aggression_call || 'normal';
      awayTempoCall = turnData.defense_tempo_call || 'normal';
      awayAggrCall = turnData.defense_aggression_call;
    } else {
      awayTempoCall = turnData.offense_tempo_call;
      awayAggrCall = turnData.offense_aggression_call || 'normal';
      homeTempoCall = turnData.defense_tempo_call || 'normal';
      homeAggrCall = turnData.defense_aggression_call;
    }
  } else {
    // Fallback: use normal for everything
    homeTempoCall = 'normal';
    homeAggrCall = 'normal';
    awayTempoCall = 'normal';
    awayAggrCall = 'normal';
  }
  
  // Update home bars
  const homeTempBar = document.querySelector('#home-tempo-bar .strategy-bar-fill');
  const homeAggrBar = document.querySelector('#home-aggression-bar .strategy-bar-fill');
  if (homeTempBar) homeTempBar.style.height = `${tempoToPercentage(homeTempoCall)}%`;
  if (homeAggrBar) homeAggrBar.style.height = `${aggressionToPercentage(homeAggrCall)}%`;
  
  // Update away bars
  const awayTempoBar = document.querySelector('#away-tempo-bar .strategy-bar-fill');
  const awayAggrBar = document.querySelector('#away-aggression-bar .strategy-bar-fill');
  if (awayTempoBar) awayTempoBar.style.height = `${tempoToPercentage(awayTempoCall)}%`;
  if (awayAggrBar) awayAggrBar.style.height = `${aggressionToPercentage(awayAggrCall)}%`;
}

