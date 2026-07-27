/**
 * Namespaced franchise localStorage (multi_franchises_brief Phase 3 hybrid).
 *
 * Identity: URL `?franchise_id=` only — never store a bare "current" franchise id.
 * Context cache: `franchise:{id}:week|user_team|user_team_id|user_team_primary_color|
 *   team_builder_visual|complete_week_pending|eog_pgpc_snapshot|last_game_id|last_game_user_team_side`
 *
 * Classic script (IIFE). Loaded before authBarInit via authGuard; also include
 * explicitly on court / FCC / mode-select / box-score / team-select pages.
 */
(function (global) {
  var PREFIX = 'franchise:';
  var BARE_KEYS = [
    'franchiseId',
    'franchise_id',
    'franchise_week',
    'franchise_user_team',
    'franchise_user_team_id',
    'franchise_user_team_primary_color',
    'franchise_complete_week_pending',
    'franchise_eog_pgpc_snapshot',
  ];
  var BARE_LAST_GAME_KEYS = [
    'last_game_id',
    'last_game_user_team_side',
    'last_box_score_gameId',
    'last_box_score_url',
    'game_home',
    'game_away',
  ];

  function hasLs() {
    return typeof localStorage !== 'undefined';
  }

  function resolveFranchiseIdFromUrl(search) {
    try {
      var q = new URLSearchParams(
        search != null ? search : (typeof window !== 'undefined' ? window.location.search : '')
      );
      return q.get('franchise_id') || null;
    } catch (e) {
      return null;
    }
  }

  function key(franchiseId, field) {
    if (!franchiseId || !field) return null;
    return PREFIX + String(franchiseId) + ':' + String(field);
  }

  function get(franchiseId, field) {
    if (!hasLs()) return null;
    var k = key(franchiseId, field);
    if (!k) return null;
    try {
      return localStorage.getItem(k);
    } catch (e) {
      return null;
    }
  }

  function set(franchiseId, field, value) {
    if (!hasLs() || value == null) return;
    var k = key(franchiseId, field);
    if (!k) return;
    try {
      localStorage.setItem(k, String(value));
    } catch (e) {}
  }

  function remove(franchiseId, field) {
    if (!hasLs()) return;
    var k = key(franchiseId, field);
    if (!k) return;
    try {
      localStorage.removeItem(k);
    } catch (e) {}
  }

  function getJson(franchiseId, field) {
    var raw = get(franchiseId, field);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function setJson(franchiseId, field, obj) {
    if (obj == null) {
      remove(franchiseId, field);
      return;
    }
    try {
      set(franchiseId, field, JSON.stringify(obj));
    } catch (e) {}
  }

  function setTeamContext(franchiseId, opts) {
    opts = opts || {};
    if (opts.teamName != null && opts.teamName !== '') set(franchiseId, 'user_team', opts.teamName);
    if (opts.teamId != null && opts.teamId !== '') set(franchiseId, 'user_team_id', opts.teamId);
    if (opts.primaryColor != null && opts.primaryColor !== '') {
      set(franchiseId, 'user_team_primary_color', opts.primaryColor);
    } else if (opts.clearPrimaryColor) {
      remove(franchiseId, 'user_team_primary_color');
    }
    if (opts.teamBuilderVisual != null) {
      setJson(franchiseId, 'team_builder_visual', opts.teamBuilderVisual);
    } else if (opts.clearTeamBuilderVisual) {
      remove(franchiseId, 'team_builder_visual');
    }
  }

  function getTeamContext(franchiseId) {
    return {
      teamName: get(franchiseId, 'user_team') || '',
      teamId: get(franchiseId, 'user_team_id') || '',
      primaryColor: get(franchiseId, 'user_team_primary_color') || '',
      teamBuilderVisual: getJson(franchiseId, 'team_builder_visual'),
    };
  }

  function setTeamBuilderVisual(franchiseId, visual) {
    if (!franchiseId) return;
    if (visual == null) {
      remove(franchiseId, 'team_builder_visual');
      if (typeof setActiveTeamBuilderVisual === 'function') {
        try {
          // Only clear session visual when this franchise is the URL franchise.
          var activeId = resolveFranchiseIdFromUrl();
          if (!activeId || String(activeId) === String(franchiseId)) {
            setActiveTeamBuilderVisual(null);
          }
        } catch (e) {}
      }
      return;
    }
    setJson(franchiseId, 'team_builder_visual', visual);
    if (typeof setActiveTeamBuilderVisual === 'function') {
      try {
        var activeId2 = resolveFranchiseIdFromUrl();
        if (!activeId2 || String(activeId2) === String(franchiseId)) {
          setActiveTeamBuilderVisual(visual);
        }
      } catch (e2) {}
    }
  }

  function getTeamBuilderVisual(franchiseId) {
    if (!franchiseId) {
      franchiseId = resolveFranchiseIdFromUrl();
    }
    if (!franchiseId) return null;
    return getJson(franchiseId, 'team_builder_visual');
  }

  function setWeek(franchiseId, week) {
    if (week == null || week === '') return;
    set(franchiseId, 'week', String(week));
  }

  function getWeek(franchiseId) {
    var raw = get(franchiseId, 'week');
    if (raw == null || raw === '') return null;
    var n = parseInt(raw, 10);
    return Number.isFinite(n) ? n : null;
  }

  function setPendingCompleteWeek(franchiseId, payload) {
    setJson(franchiseId, 'complete_week_pending', payload);
  }

  function getPendingCompleteWeek(franchiseId) {
    var namespaced = getJson(franchiseId, 'complete_week_pending');
    if (namespaced) return namespaced;
    // One-shot migrate from bare global if id matches
    if (!hasLs() || !franchiseId) return null;
    try {
      var bare = localStorage.getItem('franchise_complete_week_pending');
      if (!bare) return null;
      var parsed = JSON.parse(bare);
      if (parsed && String(parsed.franchise_id) === String(franchiseId)) {
        setPendingCompleteWeek(franchiseId, parsed);
        localStorage.removeItem('franchise_complete_week_pending');
        return parsed;
      }
    } catch (e) {}
    return null;
  }

  function clearPendingCompleteWeek(franchiseId) {
    remove(franchiseId, 'complete_week_pending');
    if (hasLs()) {
      try {
        localStorage.removeItem('franchise_complete_week_pending');
      } catch (e) {}
    }
  }

  function setEogSnapshot(franchiseId, payload) {
    setJson(franchiseId, 'eog_pgpc_snapshot', payload);
  }

  function getEogSnapshot(franchiseId) {
    var namespaced = getJson(franchiseId, 'eog_pgpc_snapshot');
    if (namespaced) return namespaced;
    if (!hasLs() || !franchiseId) return null;
    try {
      var bare = localStorage.getItem('franchise_eog_pgpc_snapshot');
      if (!bare) return null;
      var parsed = JSON.parse(bare);
      var snapFid = parsed && (parsed.franchiseId || parsed.franchise_id);
      if (parsed && snapFid != null && String(snapFid) === String(franchiseId)) {
        setEogSnapshot(franchiseId, parsed);
        localStorage.removeItem('franchise_eog_pgpc_snapshot');
        return parsed;
      }
    } catch (e) {}
    return null;
  }

  function clearEogSnapshot(franchiseId) {
    remove(franchiseId, 'eog_pgpc_snapshot');
    if (hasLs()) {
      try {
        localStorage.removeItem('franchise_eog_pgpc_snapshot');
      } catch (e) {}
    }
  }

  function clearPendingAndEog(franchiseId) {
    clearPendingCompleteWeek(franchiseId);
    clearEogSnapshot(franchiseId);
  }

  function setLastGame(franchiseId, gameId, userTeamSide) {
    if (gameId != null) set(franchiseId, 'last_game_id', gameId);
    if (userTeamSide != null) set(franchiseId, 'last_game_user_team_side', userTeamSide);
  }

  function getLastGameUserTeamSide(franchiseId) {
    var side = get(franchiseId, 'last_game_user_team_side');
    if (side) return side;
    // Migrate bare only when URL franchise is known (caller passes id)
    if (!hasLs()) return null;
    try {
      return localStorage.getItem('last_game_user_team_side');
    } catch (e) {
      return null;
    }
  }

  function clearBareKeys() {
    if (!hasLs()) return;
    BARE_KEYS.forEach(function (k) {
      try {
        localStorage.removeItem(k);
      } catch (e) {}
    });
  }

  function clearBareLastGameKeys() {
    if (!hasLs()) return;
    BARE_LAST_GAME_KEYS.forEach(function (k) {
      try {
        localStorage.removeItem(k);
      } catch (e) {}
    });
  }

  function clearAllForFranchise(franchiseId) {
    if (!franchiseId || !hasLs()) return;
    var fields = [
      'week',
      'user_team',
      'user_team_id',
      'user_team_primary_color',
      'team_builder_visual',
      'complete_week_pending',
      'eog_pgpc_snapshot',
      'last_game_id',
      'last_game_user_team_side',
    ];
    fields.forEach(function (f) {
      remove(franchiseId, f);
    });
  }

  function clearAllNamespaces() {
    if (!hasLs()) return;
    try {
      Object.keys(localStorage).forEach(function (k) {
        if (k.indexOf(PREFIX) === 0) localStorage.removeItem(k);
      });
    } catch (e) {}
  }

  /** Full exit / delete / New Franchise wipe — bare + all franchise namespaces + last-game globals. */
  function clearOnFranchiseExit() {
    clearBareKeys();
    clearBareLastGameKeys();
    clearAllNamespaces();
    if (!hasLs()) return;
    try {
      Object.keys(localStorage).forEach(function (k) {
        if (k.indexOf('playbooks_position_filters_franchise_') === 0) {
          localStorage.removeItem(k);
        }
      });
    } catch (e) {}
  }

  global.FranchiseLS = {
    PREFIX: PREFIX,
    key: key,
    resolveFranchiseIdFromUrl: resolveFranchiseIdFromUrl,
    get: get,
    set: set,
    remove: remove,
    getJson: getJson,
    setJson: setJson,
    setTeamContext: setTeamContext,
    getTeamContext: getTeamContext,
    setTeamBuilderVisual: setTeamBuilderVisual,
    getTeamBuilderVisual: getTeamBuilderVisual,
    setWeek: setWeek,
    getWeek: getWeek,
    setPendingCompleteWeek: setPendingCompleteWeek,
    getPendingCompleteWeek: getPendingCompleteWeek,
    clearPendingCompleteWeek: clearPendingCompleteWeek,
    setEogSnapshot: setEogSnapshot,
    getEogSnapshot: getEogSnapshot,
    clearEogSnapshot: clearEogSnapshot,
    clearPendingAndEog: clearPendingAndEog,
    setLastGame: setLastGame,
    getLastGameUserTeamSide: getLastGameUserTeamSide,
    clearBareKeys: clearBareKeys,
    clearBareLastGameKeys: clearBareLastGameKeys,
    clearAllForFranchise: clearAllForFranchise,
    clearAllNamespaces: clearAllNamespaces,
    clearOnFranchiseExit: clearOnFranchiseExit,
  };
})(typeof window !== 'undefined' ? window : this);
