/**
 * Unified Timeout Navigation Helper
 * 
 * Single Source & System (SS&S) for all game navigation parameter building.
 * Handles ALL navigation scenarios:
 * - Game Start (Q1, new game)
 * - Overtime Start (OT1+, existing game)
 * - Quarter Breaks (Q2-Q4, existing game)
 * - Timeout Resume (any quarter, existing game)
 * - Foul Out Resume (any quarter, existing game)
 * - Back Navigation (preserve all params)
 * 
 * @module timeoutNavigationHelper
 */

// ✅ SS&S: Use IIFE pattern to work as both regular script and ES6 module
(function(global) {
  'use strict';
  
  /**
   * Builds URL parameters for game navigation with consistent SS&S logic
   * 
   * @param {Object} options
   * @param {URLSearchParams} options.sourceParams - Current page URL params
   * @param {number} options.targetQuarter - Quarter to navigate to
   * @param {string|null} options.gameId - Game ID (from URL or localStorage)
   * @param {boolean} options.resumeFromTimeout - Whether resuming from timeout/foul out
   * @param {Object} [options.lineup={}] - Lineup object {PG, SG, SF, PF, C}
   * @param {string|null} options.myTeamSide - 'home' or 'away'
   * @param {string|null} [options.clock] - Clock time to preserve
   * @param {Object} [options.overrides={}] - Optional param overrides
   * @returns {URLSearchParams} Built parameters ready for navigation
   */
  function buildGameNavigationParams({
    sourceParams,
    targetQuarter,
    gameId = null,
    resumeFromTimeout = false,
    lineup = {},
    myTeamSide = null,
    clock = null,
    computerTimeout = false,
    computerTeamName = null,
    overrides = {}
  }) {
    const params = new URLSearchParams();
    
    // ============================================
    // 1. CORE GAME PARAMS (Always needed)
    // ============================================
    params.set('quarter', String(targetQuarter));
    params.set('period', targetQuarter <= 4 ? `Q${targetQuarter}` : `OT${targetQuarter - 4}`);
    
    // ============================================
    // 2. TEAM INFORMATION
    // ============================================
    const home = overrides.home || sourceParams.get('home');
    const away = overrides.away || sourceParams.get('away');
    const homeId = overrides.home_id || sourceParams.get('home_id');
    const awayId = overrides.away_id || sourceParams.get('away_id');
    const myTeam = overrides.my_team || sourceParams.get('my_team');
    const userTeamId = overrides.user_team_id || sourceParams.get('user_team_id');
    
    if (home) params.set('home', home);
    if (away) params.set('away', away);
    if (homeId) params.set('home_id', homeId);
    if (awayId) params.set('away_id', awayId);
    if (myTeam) params.set('my_team', myTeam);
    if (userTeamId) params.set('user_team_id', userTeamId);
    
    // ============================================
    // 3. GAME ID LOGIC (SS&S Rules)
    // ============================================
    // Rule: Pass game_id if:
    //   - Quarter > 1 (quarter breaks, overtime)
    //   - OR resumeFromTimeout is true (timeout/foul out resume, any quarter)
    //   - NOT for new Q1 game start
    const shouldPassGameId = gameId && (
      targetQuarter > 1 ||  // Quarter breaks, overtime
      resumeFromTimeout     // Timeout/foul out resume (any quarter)
    );
    
    if (shouldPassGameId) {
      params.set('game_id', gameId);
    }
    
    // ============================================
    // 4. RESUME FROM TIMEOUT/FOUL OUT (SS&S Rules)
    // ============================================
    // Rule: Set resume_from_timeout if:
    //   - resumeFromTimeout is true (any quarter - backend supports this)
    //   - AND gameId exists (not a new game)
    //   - NOT for quarter breaks (Q2-Q4 without timeout)
    //   - NOT for new game start
    if (resumeFromTimeout && gameId) {
      params.set('resume_from_timeout', 'true');
    }
    
    // ============================================
    // 5. CLOCK PRESERVATION
    // ============================================
    const clockTime = clock || sourceParams.get('clock');
    if (clockTime) {
      params.set('clock', clockTime);
    }
    
    // ============================================
    // 6. LINEUP PARAMS
    // ============================================
    if (myTeamSide && lineup) {
      ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
        const id = lineup[pos];
        if (id) {
          params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
        }
      });
    }
    
    // ============================================
    // 7. SPECIAL PARAMS
    // ============================================
    const startWithInbound = sourceParams.get('start_with_inbound');
    const startingPossession = sourceParams.get('starting_possession');
    if (startWithInbound) params.set('start_with_inbound', startWithInbound);
    if (startingPossession) params.set('starting_possession', startingPossession);
    
    // ============================================
    // 8. MODE/TOURNAMENT/FRANCHISE PARAMS
    // ============================================
    const mode = overrides.mode || sourceParams.get('mode');
    const tournamentId = overrides.tournament_id || sourceParams.get('tournament_id');
    const franchiseId = overrides.franchise_id || sourceParams.get('franchise_id');
    const week = overrides.week || sourceParams.get('week');
    
    if (mode) params.set('mode', mode);
    if (tournamentId) params.set('tournament_id', tournamentId);
    if (franchiseId) params.set('franchise_id', franchiseId);
    if (week) params.set('week', week);
    
    // ============================================
    // 9. COMPUTER TIMEOUT PARAMS
    // ============================================
    // ✅ COMPUTER TIMEOUT: Add params to indicate computer timeout for lineup screen display
    if (computerTimeout && computerTeamName) {
      params.set('computer_timeout', 'true');
      params.set('computer_team_name', computerTeamName);
      console.log('✅ COMPUTER TIMEOUT: Added URL params', {
        computer_timeout: 'true',
        computer_team_name: computerTeamName
      });
    } else {
      console.warn('⚠️ COMPUTER TIMEOUT: Missing params', {
        computerTimeout: computerTimeout,
        computerTeamName: computerTeamName
      });
    }
    
    // ============================================
    // 10. DEBUG PARAMS
    // ============================================
    if (sourceParams.get('debug') === '1') {
      params.set('debug', '1');
    }
    
    return params;
  }

  /**
   * Helper to extract resume_from_timeout from URL params
   * 
   * @param {URLSearchParams} urlParams - URL parameters
   * @returns {boolean} Whether resuming from timeout/foul out
   */
  function getResumeFromTimeout(urlParams) {
    return urlParams.get('resume_from_timeout') === 'true';
  }

  /**
   * Helper to get game ID from URL or localStorage
   * 
   * @param {URLSearchParams} urlParams - URL parameters
   * @returns {string|null} Game ID or null
   */
  function getGameId(urlParams) {
    return urlParams.get('game_id') ||
      (typeof localStorage !== 'undefined' ? localStorage.getItem('game_id') : null);
  }

  // ✅ SS&S: Make available as global (for script tag loading)
  // This allows non-module scripts to use the helper
  if (typeof window !== 'undefined') {
    window.TimeoutNavigationHelper = {
      buildGameNavigationParams,
      getResumeFromTimeout,
      getGameId
    };
  }

  // ✅ SS&S: Also export for ES6 module usage (if in module context)
  // This allows module scripts to import the helper
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      buildGameNavigationParams,
      getResumeFromTimeout,
      getGameId
    };
  }

  // ES6 module exports (for import statements) - only if not in strict script mode
  if (typeof globalThis !== 'undefined') {
    try {
      // Try to export if we're in a module context
      if (typeof exports !== 'undefined') {
        exports.buildGameNavigationParams = buildGameNavigationParams;
        exports.getResumeFromTimeout = getResumeFromTimeout;
        exports.getGameId = getGameId;
      }
    } catch (e) {
      // Not in module context, that's fine
    }
  }

})(typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : this);

// Note: For ES6 module usage, create a separate wrapper file that imports and re-exports
// This file works as a regular script (attaches to window.TimeoutNavigationHelper)
// For ES6 imports, use: import { buildGameNavigationParams, getResumeFromTimeout, getGameId } from './timeoutNavigationHelper.mjs'
