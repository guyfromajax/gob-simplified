// ✅ PHASE 1.3: Import state telemetry
import { logGameStoreRead, logGameStoreWrite, setContext } from '../shared/stateTelemetry.js';

// Set context for telemetry
setContext('gameStore');

const state = {
  teams: { home: null, away: null },
  colors: { home: {}, away: {} },
  rosters: { home: null, away: null },
  gameId: null,
};

export default {
  // Teams
  setTeams({ home, away }) {
    state.teams.home = home || null;
    state.teams.away = away || null;
  },
  getTeams() {
    return { ...state.teams };
  },
  getHomeTeam() {
    return state.teams.home;
  },
  getAwayTeam() {
    return state.teams.away;
  },

  // Colors
  setColors({ home, away }) {
    state.colors.home = home ? { ...home } : {};
    state.colors.away = away ? { ...away } : {};
  },
  getColors() {
    return { ...state.colors };
  },
  getHomeColors() {
    return { ...state.colors.home };
  },
  getAwayColors() {
    return { ...state.colors.away };
  },

  // Rosters
  setRosters({ home, away }) {
    state.rosters.home = home || null;
    state.rosters.away = away || null;
  },
  getRosters() {
    return { ...state.rosters };
  },
  getHomeRoster() {
    return state.rosters.home;
  },
  getAwayRoster() {
    return state.rosters.away;
  },

  // Game ID
  setGameId(id) {
    // ✅ PHASE 1.3: Log state write
    logGameStoreWrite('game_id', id);
    state.gameId = id || null;
  },
  getGameId() {
    // ✅ PHASE 1.3: Log state read
    const value = state.gameId;
    logGameStoreRead('game_id', value);
    return value;
  },

  reset() {
    state.teams = { home: null, away: null };
    state.colors = { home: {}, away: {} };
    state.rosters = { home: null, away: null };
    state.gameId = null;
  },
};
