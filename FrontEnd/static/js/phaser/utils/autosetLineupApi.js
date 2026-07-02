/**
 * Unified lineup autoset via POST /api/autoset-lineup (same rules as set-lineup screen / sim).
 */

const REQUIRED_LINEUP_POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];

function getPlayerId(player) {
  if (!player || typeof player !== 'object') return null;
  return player.player_id || player.playerId || player._id || player.id || null;
}

function validateLineup(lineup, label) {
  const missing = REQUIRED_LINEUP_POSITIONS.filter((pos) => !lineup || !lineup[pos]);
  if (missing.length) {
    throw new Error(`${label} autoset-lineup returned incomplete lineup; missing ${missing.join(', ')}`);
  }
}

function buildAutosetPlayersPayload(players) {
  return (players || []).map((p) => {
    const raw = p.stats || {};
    const gameStats = raw.game || raw;
    const playerId = getPlayerId(p);
    return {
      _id: playerId,
      player_id: playerId,
      first_name: p.first_name || '',
      last_name: p.last_name || '',
      attributes: p.attributes || {},
      position_ratings: p.position_ratings || {},
      stats: Object.keys(gameStats).length ? { game: gameStats } : {},
    };
  });
}

/**
 * @param {object} rosterJson - Response from GET /roster/{team} (must include .players)
 * @param {{ quarter: number, time_remaining: number }} gameState
 * @returns {Promise<Record<string, string>>}
 */
export async function fetchAutosetLineupFromRosterApi(rosterJson, gameState) {
  const API_CONFIG = typeof window !== 'undefined' ? window.API_CONFIG : null;
  if (!API_CONFIG || !API_CONFIG.buildUrl) {
    throw new Error('API_CONFIG.buildUrl not available');
  }
  let tc = rosterJson.team_chemistry != null && rosterJson.team_chemistry !== ''
    ? Number(rosterJson.team_chemistry)
    : 15;
  if (!Number.isFinite(tc)) tc = 15;

  const headers = { 'Content-Type': 'application/json' };
  if (typeof API_CONFIG.getAuthHeaders === 'function') {
    Object.assign(headers, API_CONFIG.getAuthHeaders());
  }

  const res = await fetch(API_CONFIG.buildUrl('/api/autoset-lineup'), {
    method: 'POST',
    headers,
    body: JSON.stringify({
      players: buildAutosetPlayersPayload(rosterJson.players),
      game_state: gameState,
      team_chemistry: tc,
    }),
  });
  if (!res.ok) {
    let msg = `autoset-lineup failed (${res.status})`;
    try {
      const err = await res.json();
      if (err.detail) {
        msg = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      }
    } catch (_) { /* ignore */ }
    throw new Error(msg);
  }
  const data = await res.json();
  const lineup = data.lineup || {};
  validateLineup(lineup, rosterJson.team_name || rosterJson.name || 'team');
  return lineup;
}

/**
 * @param {object} homeRoster
 * @param {object} awayRoster
 * @param {{ quarter: number, time_remaining: number }} gameState
 */
export async function generateBothLineupsFromApi(homeRoster, awayRoster, gameState) {
  const [home_lineup, away_lineup] = await Promise.all([
    fetchAutosetLineupFromRosterApi(homeRoster, gameState),
    fetchAutosetLineupFromRosterApi(awayRoster, gameState),
  ]);
  return { home_lineup, away_lineup };
}
