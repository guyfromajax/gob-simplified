/**
 * State Telemetry Utility
 * Phase 1.3: Track all state read/write operations for debugging and contract enforcement
 * 
 * Logs:
 * - State reads (which variable, which source)
 * - State writes (which variable, which source)
 * - Contract violations (reading from wrong source)
 * - Cache hits/misses
 * 
 * Works as both ES6 module and regular script (global window.StateTelemetry)
 */

(function() {
'use strict';

// Configuration
const TELEMETRY_CONFIG = {
  enabled: false, // Set to false to disable all telemetry (disabled by default - was for Phase 1.3 work)
  logLevel: 'info', // 'debug', 'info', 'warn', 'error'
  logReads: false, // Log state reads
  logWrites: false, // Log state writes
  logViolations: false, // Log contract violations
  logCache: false, // Log cache hits/misses
  groupByPage: true, // Group logs by page/component
};

// State contract rules (what source should be used for each variable)
const STATE_CONTRACT = {
  game_id: {
    sources: ['url'], // Only URL is allowed
    description: 'Game identifier - must come from URL params only'
  },
  franchise_id: {
    sources: ['url'], // Only URL is allowed
    description: 'Franchise identifier - must come from URL params only'
  },
  tournament_id: {
    sources: ['url'], // Only URL is allowed
    description: 'Tournament identifier - must come from URL params only'
  },
  playbook_settings: {
    sources: ['backend', 'gameStore'], // Backend is source of truth, gameStore is cache
    description: 'Playbook settings - backend is source of truth, gameStore is cache'
  },
  strategy_settings: {
    sources: ['backend', 'gameStore'], // Backend is source of truth, gameStore is cache
    description: 'Strategy settings (game plan) - backend is source of truth, gameStore is cache'
  },
  user_team_id: {
    sources: ['url', 'localStorage'], // URL preferred, localStorage for resume feature
    description: 'User team identifier - URL preferred, localStorage for resume only'
  },
  team_id: {
    sources: ['url'], // Only URL is allowed
    description: 'Team identifier - must come from URL params only'
  }
};

// Source types
const SOURCE_TYPES = {
  URL: 'url',
  LOCAL_STORAGE: 'localStorage',
  GAME_STORE: 'gameStore',
  BACKEND: 'backend',
  UNKNOWN: 'unknown'
};

// Current page/component context
let currentContext = 'unknown';

/**
 * Set current context (page/component name) for grouping logs
 */
function setContext(context) {
  currentContext = context;
}

/**
 * Get current context
 */
function getContext() {
  return currentContext;
}

/**
 * Check if telemetry is enabled
 */
function isEnabled() {
  return TELEMETRY_CONFIG.enabled;
}

/**
 * Check if should log based on log level
 */
function shouldLog(level) {
  if (!isEnabled()) return false;
  
  const levels = ['debug', 'info', 'warn', 'error'];
  const currentLevel = levels.indexOf(TELEMETRY_CONFIG.logLevel);
  const messageLevel = levels.indexOf(level);
  return messageLevel >= currentLevel;
}

/**
 * Format log message with context
 */
function formatMessage(prefix, message, data = {}) {
  const context = getContext();
  const contextStr = context !== 'unknown' ? `[${context}]` : '';
  return `${prefix} ${contextStr} ${message}`;
}

/**
 * Log state read operation
 * @param {string} variable - Variable name (e.g., 'game_id')
 * @param {string} source - Source type (e.g., 'url', 'localStorage')
 * @param {any} value - Value read (optional, for debugging)
 * @param {string} location - Code location (file:line, optional)
 */
function logStateRead(variable, source, value = null, location = '') {
  if (!TELEMETRY_CONFIG.logReads || !shouldLog('info')) return;
  
  const contract = STATE_CONTRACT[variable];
  const isViolation = contract && !contract.sources.includes(source);
  
  const logData = {
    variable,
    source,
    value: value !== null ? (typeof value === 'object' ? '[object]' : String(value)) : null,
    location,
    timestamp: new Date().toISOString(),
    isViolation
  };
  
  if (isViolation && TELEMETRY_CONFIG.logViolations) {
    console.warn(
      formatMessage('🔴 [STATE-VIOLATION]', `Read ${variable} from ${source} (should be: ${contract.sources.join(', ')})`),
      logData
    );
  } else {
    console.log(
      formatMessage('🔵 [STATE-READ]', `${variable} from ${source}`),
      logData
    );
  }
}

/**
 * Log state write operation
 * @param {string} variable - Variable name (e.g., 'game_id')
 * @param {string} source - Source type (e.g., 'url', 'localStorage')
 * @param {any} value - Value written (optional, for debugging)
 * @param {string} location - Code location (file:line, optional)
 */
function logStateWrite(variable, source, value = null, location = '') {
  if (!TELEMETRY_CONFIG.logWrites || !shouldLog('info')) return;
  
  const contract = STATE_CONTRACT[variable];
  const isViolation = contract && !contract.sources.includes(source);
  
  const logData = {
    variable,
    source,
    value: value !== null ? (typeof value === 'object' ? '[object]' : String(value)) : null,
    location,
    timestamp: new Date().toISOString(),
    isViolation
  };
  
  if (isViolation && TELEMETRY_CONFIG.logViolations) {
    console.warn(
      formatMessage('🔴 [STATE-VIOLATION]', `Write ${variable} to ${source} (should be: ${contract.sources.join(', ')})`),
      logData
    );
  } else {
    console.log(
      formatMessage('🟢 [STATE-WRITE]', `${variable} to ${source}`),
      logData
    );
  }
}

/**
 * Log cache hit
 * @param {string} variable - Variable name
 * @param {string} cacheType - Cache type (e.g., 'gameStore')
 */
function logCacheHit(variable, cacheType) {
  if (!TELEMETRY_CONFIG.logCache || !shouldLog('debug')) return;
  
  console.log(
    formatMessage('✅ [CACHE-HIT]', `${variable} from ${cacheType}`),
    { variable, cacheType, timestamp: new Date().toISOString() }
  );
}

/**
 * Log cache miss
 * @param {string} variable - Variable name
 * @param {string} cacheType - Cache type (e.g., 'gameStore')
 * @param {string} fallbackSource - Where it was read from instead
 */
function logCacheMiss(variable, cacheType, fallbackSource) {
  if (!TELEMETRY_CONFIG.logCache || !shouldLog('debug')) return;
  
  console.log(
    formatMessage('⚠️ [CACHE-MISS]', `${variable} not in ${cacheType}, using ${fallbackSource}`),
    { variable, cacheType, fallbackSource, timestamp: new Date().toISOString() }
  );
}

/**
 * Log cache invalidation
 * @param {string} variable - Variable name
 * @param {string} cacheType - Cache type (e.g., 'gameStore')
 * @param {string} reason - Reason for invalidation
 */
function logCacheInvalidation(variable, cacheType, reason) {
  if (!TELEMETRY_CONFIG.logCache || !shouldLog('debug')) return;
  
  console.log(
    formatMessage('🔄 [CACHE-INVALIDATE]', `${variable} in ${cacheType} (reason: ${reason})`),
    { variable, cacheType, reason, timestamp: new Date().toISOString() }
  );
}

/**
 * Helper: Get code location (file:line) from stack trace
 */
function getCodeLocation() {
  try {
    const stack = new Error().stack;
    const lines = stack.split('\n');
    // Skip first 3 lines (Error, getCodeLocation, calling function)
    if (lines.length > 3) {
      const callerLine = lines[3];
      // Extract file and line number
      const match = callerLine.match(/([^/]+\.js):(\d+):(\d+)/);
      if (match) {
        return `${match[1]}:${match[2]}`;
      }
    }
  } catch (e) {
    // Ignore errors in location detection
  }
  return '';
}

/**
 * Wrapper for URL parameter reads
 */
function logUrlRead(variable, value, urlParams = null) {
  const location = getCodeLocation();
  logStateRead(variable, SOURCE_TYPES.URL, value, location);
  return value;
}

/**
 * Wrapper for localStorage reads
 */
function logLocalStorageRead(variable, value) {
  const location = getCodeLocation();
  logStateRead(variable, SOURCE_TYPES.LOCAL_STORAGE, value, location);
  return value;
}

/**
 * Wrapper for localStorage writes
 */
function logLocalStorageWrite(variable, value) {
  const location = getCodeLocation();
  logStateWrite(variable, SOURCE_TYPES.LOCAL_STORAGE, value, location);
}

/**
 * Wrapper for gameStore reads
 */
function logGameStoreRead(variable, value) {
  const location = getCodeLocation();
  logStateRead(variable, SOURCE_TYPES.GAME_STORE, value, location);
  return value;
}

/**
 * Wrapper for gameStore writes
 */
function logGameStoreWrite(variable, value) {
  const location = getCodeLocation();
  logStateWrite(variable, SOURCE_TYPES.GAME_STORE, value, location);
}

/**
 * Wrapper for backend/API reads
 */
function logBackendRead(variable, value, endpoint = '') {
  const location = getCodeLocation();
  logStateRead(variable, SOURCE_TYPES.BACKEND, value, `${location}${endpoint ? ` (${endpoint})` : ''}`);
  return value;
}

/**
 * Wrapper for backend/API writes
 */
function logBackendWrite(variable, value, endpoint = '') {
  const location = getCodeLocation();
  logStateWrite(variable, SOURCE_TYPES.BACKEND, value, `${location}${endpoint ? ` (${endpoint})` : ''}`);
}

/**
 * Configure telemetry (runtime modification, e.g., disable in production)
 */
function configureTelemetry(config) {
  Object.assign(TELEMETRY_CONFIG, config);
}

/**
 * Get current telemetry configuration
 */
function getTelemetryConfig() {
  return { ...TELEMETRY_CONFIG };
}

// ✅ PHASE 1.3: Expose API globally for non-module scripts
if (typeof window !== 'undefined') {
  window.StateTelemetry = {
    setContext,
    logStateRead,
    logStateWrite,
    logCacheHit,
    logCacheMiss,
    logCacheInvalidation,
    logUrlRead,
    logLocalStorageRead,
    logLocalStorageWrite,
    logGameStoreRead,
    logGameStoreWrite,
    logBackendRead,
    logBackendWrite,
    configureTelemetry,
    getTelemetryConfig,
    SOURCE_TYPES
  };
}

// ✅ PHASE 1.3: Also export as ES6 module for module scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    setContext,
    logStateRead,
    logStateWrite,
    logCacheHit,
    logCacheMiss,
    logCacheInvalidation,
    logUrlRead,
    logLocalStorageRead,
    logLocalStorageWrite,
    logGameStoreRead,
    logGameStoreWrite,
    logBackendRead,
    logBackendWrite,
    configureTelemetry,
    getTelemetryConfig,
    SOURCE_TYPES
  };
}

})(); // End IIFE

