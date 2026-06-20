/**
 * Merge state doc's players[id].season into roster data (no fetch).
 * @param {Object} rosterData - { players: Array }
 * @param {Object} stateDoc - { players: { [id]: { season: {...} } } }
 * @returns {{ players: Array }}
 */
function mergeRosterWithStateDoc(rosterData, stateDoc) {
  var statePlayers = (stateDoc && stateDoc.players) ? stateDoc.players : {};
  var players = (rosterData.players || []).map(function (p) {
    var id = p._id;
    var statePlayer = statePlayers[id];
    var season = (statePlayer && statePlayer.season) ? statePlayer.season : {};
    var out = {};
    for (var k in p) {
      if (Object.prototype.hasOwnProperty.call(p, k)) out[k] = p[k];
    }
    out.stats = { season: season };
    return out;
  });
  // Preserve other top-level roster fields (e.g. training_squad,
  // practice_squad_recruits) so callers can render them alongside the roster.
  var result = {};
  for (var key in rosterData) {
    if (Object.prototype.hasOwnProperty.call(rosterData, key)) result[key] = rosterData[key];
  }
  result.players = players;
  return result;
}

/**
 * Fetch roster + state and merge season stats (Phase 4.1).
 * Callers build rosterUrl and stateUrl (e.g. with API_CONFIG.buildUrl).
 *
 * @param {string} rosterUrl - Full URL for GET roster
 * @param {string} stateUrl - Full URL for GET state doc
 * @returns {Promise<{ players: Array }>}
 */
function loadRosterWithStats(rosterUrl, stateUrl) {
  var headers = (typeof window !== 'undefined' && window.API_CONFIG && window.API_CONFIG.getAuthHeaders) ? window.API_CONFIG.getAuthHeaders() : {};
  return fetch(rosterUrl, { headers: headers })
    .then(function (rosterRes) {
      if (!rosterRes.ok) {
        var err = new Error('Roster fetch failed: ' + rosterRes.status);
        err.status = rosterRes.status;
        throw err;
      }
      return rosterRes.json();
    })
    .then(function (rosterData) {
      return fetch(stateUrl, { headers: headers })
        .then(function (stateRes) {
          if (!stateRes.ok) {
            rosterData.players = rosterData.players || [];
            return rosterData;
          }
          return stateRes.json().then(function (stateDoc) {
            return mergeRosterWithStateDoc(rosterData, stateDoc);
          });
        });
    });
}

(function (global) {
  'use strict';
  var api = {
    loadRosterWithStats: loadRosterWithStats,
    mergeRosterWithStateDoc: mergeRosterWithStateDoc
  };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.RosterLoader = api;
  }
})(typeof window !== 'undefined' ? window : this);
