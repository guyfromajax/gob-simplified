// ✅ PHASE 1.3: Use window.StateTelemetry (loaded as script before this module)
// stateTelemetry.js is loaded as a regular script, so we access it via window
const StateTelemetry = typeof window !== 'undefined' && window.StateTelemetry;

// Set context for telemetry
if (StateTelemetry) {
  StateTelemetry.setContext('gameStore');
}

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
    if (StateTelemetry) {
      StateTelemetry.logGameStoreWrite('game_id', id);
    }
    state.gameId = id || null;
  },
  getGameId() {
    // ✅ PHASE 1.3: Log state read
    const value = state.gameId;
    if (StateTelemetry) {
      StateTelemetry.logGameStoreRead('game_id', value);
    }
    return value;
  },

  reset() {
    state.teams = { home: null, away: null };
    state.colors = { home: {}, away: {} };
    state.rosters = { home: null, away: null };
    state.gameId = null;
  },
};
