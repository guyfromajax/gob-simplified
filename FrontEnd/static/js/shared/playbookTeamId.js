function franchiseCtx() {
  return typeof window !== 'undefined' ? window.FranchiseContext : null;
}
function liveParams() {
  return franchiseCtx().toSearchParams();
}
function emptyParams() {
  return franchiseCtx().createParams();
}
function currentSearch() {
  const s = liveParams().toString();
  return s ? '?' + s : '';
}
function cloneParams(params) {
  const out = emptyParams();
  if (params && typeof params.forEach === 'function') {
    params.forEach((value, key) => out.set(key, value));
  }
  return out;
}

/**
 * SS&S: Single resolution for which team_id to send to GET /api/playbooks.
 * Matches set-lineup / bootGame: explicit ids first, then my_team + home_id/away_id.
 * Never prefers home_id over away_id when both exist without my_team (returns null).
 */
(function (g) {
  'use strict';

  /**
   * @param {Object|string} source - query string or a bag with .get
   * @returns {string|null}
   */
  function resolvePlaybookTeamIdFromSearch(source) {
    var params =
      source && typeof source.get === 'function'
        ? source
        : franchiseCtx().parseSearch(typeof source === 'string' ? source : '');

    var explicit = params.get('team_id') || params.get('user_team_id');
    if (explicit) return explicit;

    var myTeam = (params.get('my_team') || '').toLowerCase();
    var homeId = params.get('home_id');
    var awayId = params.get('away_id');

    if (myTeam === 'home' && homeId) return homeId;
    if (myTeam === 'away' && awayId) return awayId;

    if (homeId && !awayId) return homeId;
    if (awayId && !homeId) return awayId;

    return null;
  }

  /** Match server debug_pc_enabled: 1 / true / yes (case-insensitive). */
  function isDebugPlaycallSearch(source) {
    var params =
      source && typeof source.get === 'function'
        ? source
        : franchiseCtx().parseSearch(typeof source === 'string' ? source : '');
    var v = (params.get('debug_pc') || '').trim().toLowerCase();
    return v === '1' || v === 'true' || v === 'yes';
  }

  g.resolvePlaybookTeamIdFromSearch = resolvePlaybookTeamIdFromSearch;
  g.isDebugPlaycallSearch = isDebugPlaycallSearch;
})(typeof globalThis !== 'undefined' ? globalThis : window);
