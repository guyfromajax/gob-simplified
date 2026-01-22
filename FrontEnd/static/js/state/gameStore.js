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
  // ✅ PHASE 1.3: Optional cache for settings (disposable, rebuild from truth)
  playbook_settings: null, // Cached playbook settings (backend is source of truth)
  strategy_settings: null, // Cached strategy settings (backend is source of truth)
};

const gameStore = {
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

  // ✅ PHASE 1.3: Playbook settings cache (optional, disposable)
  setPlaybookSettings(settings) {
    if (StateTelemetry) {
      StateTelemetry.logGameStoreWrite('playbook_settings', settings);
    }
    state.playbook_settings = settings ? JSON.parse(JSON.stringify(settings)) : null; // Deep copy
  },
  getPlaybookSettings() {
    const value = state.playbook_settings;
    if (StateTelemetry) {
      StateTelemetry.logGameStoreRead('playbook_settings', value);
      if (value) {
        StateTelemetry.logCacheHit('playbook_settings', 'gameStore');
      } else {
        StateTelemetry.logCacheMiss('playbook_settings', 'gameStore', 'backend');
      }
    }
    return value ? JSON.parse(JSON.stringify(value)) : null; // Return deep copy
  },
  invalidatePlaybookSettings(reason = '') {
    if (StateTelemetry && state.playbook_settings) {
      StateTelemetry.logCacheInvalidation('playbook_settings', 'gameStore', reason || 'manual');
    }
    state.playbook_settings = null;
  },

  // ✅ PHASE 1.3: Strategy settings cache (optional, disposable)
  setStrategySettings(settings) {
    if (StateTelemetry) {
      StateTelemetry.logGameStoreWrite('strategy_settings', settings);
    }
    state.strategy_settings = settings ? JSON.parse(JSON.stringify(settings)) : null; // Deep copy
  },
  getStrategySettings() {
    const value = state.strategy_settings;
    if (StateTelemetry) {
      StateTelemetry.logGameStoreRead('strategy_settings', value);
      if (value) {
        StateTelemetry.logCacheHit('strategy_settings', 'gameStore');
      } else {
        StateTelemetry.logCacheMiss('strategy_settings', 'gameStore', 'backend');
      }
    }
    return value ? JSON.parse(JSON.stringify(value)) : null; // Return deep copy
  },
  invalidateStrategySettings(reason = '') {
    if (StateTelemetry && state.strategy_settings) {
      StateTelemetry.logCacheInvalidation('strategy_settings', 'gameStore', reason || 'manual');
    }
    state.strategy_settings = null;
  },

  reset() {
    state.teams = { home: null, away: null };
    state.colors = { home: {}, away: {} };
    state.rosters = { home: null, away: null };
    state.gameId = null;
    // ✅ PHASE 1.3: Clear settings cache on reset
    state.playbook_settings = null;
    state.strategy_settings = null;
  },
};

// ✅ PHASE 1.3: Expose gameStore globally for non-module scripts (like playbooks.js, game-plan.js)
if (typeof window !== 'undefined') {
  window.gameStore = gameStore;
}

export default gameStore;
