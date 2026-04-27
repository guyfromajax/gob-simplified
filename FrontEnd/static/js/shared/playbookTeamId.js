/**
 * SS&S: Single resolution for which team_id to send to GET /api/playbooks.
 * Matches set-lineup / bootGame: explicit ids first, then my_team + home_id/away_id.
 * Never prefers home_id over away_id when both exist without my_team (returns null).
 */
(function (g) {
  'use strict';

  /**
   * @param {URLSearchParams|string} source - query string (with or without '?') or URLSearchParams
   * @returns {string|null}
   */
  function resolvePlaybookTeamIdFromSearch(source) {
    var params =
      source instanceof URLSearchParams
        ? source
        : new URLSearchParams(
            typeof source === 'string' && source.charAt(0) === '?'
              ? source.slice(1)
              : source || ''
          );

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

  g.resolvePlaybookTeamIdFromSearch = resolvePlaybookTeamIdFromSearch;
})(typeof globalThis !== 'undefined' ? globalThis : window);
