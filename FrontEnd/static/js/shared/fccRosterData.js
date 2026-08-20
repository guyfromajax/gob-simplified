/** Pure data contract for the FCC Roster tab and its session-cache restore path. */
(function (global) {
  'use strict';

  function normalize(payload) {
    var data = payload && typeof payload === 'object' ? payload : {};
    var out = {};
    Object.keys(data).forEach(function (key) { out[key] = data[key]; });
    out.players = Array.isArray(data.players) ? data.players : [];
    out.training_squad = Array.isArray(data.training_squad) ? data.training_squad : [];
    out.practice_squad_recruits = Array.isArray(data.practice_squad_recruits)
      ? data.practice_squad_recruits : [];
    return out;
  }

  function fromSessionCache(cache) {
    if (cache && cache.rosterData && typeof cache.rosterData === 'object') {
      return normalize(cache.rosterData);
    }
    // Backward compatibility for caches written before the full roster payload
    // was persisted. These can warm-paint Varsity; the authoritative fetch will
    // subsequently populate Practice Squad data.
    return normalize({ players: cache && cache.rosterPlayers });
  }

  function practiceSquadPlayers(payload) {
    var data = normalize(payload);
    return data.training_squad.concat(data.practice_squad_recruits);
  }

  var api = {
    normalize: normalize,
    fromSessionCache: fromSessionCache,
    practiceSquadPlayers: practiceSquadPlayers,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else global.FccRosterData = api;
})(typeof window !== 'undefined' ? window : this);
