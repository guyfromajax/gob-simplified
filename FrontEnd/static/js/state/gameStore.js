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
    state.gameId = id || null;
  },
  getGameId() {
    return state.gameId;
  },

  reset() {
    state.teams = { home: null, away: null };
    state.colors = { home: {}, away: {} };
    state.rosters = { home: null, away: null };
    state.gameId = null;
  },
};
