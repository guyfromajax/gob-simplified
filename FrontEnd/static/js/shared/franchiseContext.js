/**
 * FranchiseContext — one door for screen state.
 *
 * URL-as-identity is an invariant, not sprawl. The web build keeps reading the
 * query string; screens must do it through this door. Deleting URL state would
 * break the MPA (80 HTML pages, 133 hard navigations) and multi-tab /
 * multi-franchise on the web build we are keeping.
 *
 * Two backends, selected at boot by window.GOB_BUILD_PROFILE:
 *   UrlContextProvider      — web. Query-string. Bit-identical to today's reads.
 *   SessionContextProvider  — desktop. localStorage singleton (one franchise
 *                             per window). Persisted, not in-memory: Electron
 *                             performs the same 133 hard navigations.
 *
 * `runtime` ('local' | 'hosted') travels with franchise_id. api-config.js
 * peeks FranchiseContext.runtime when a call supplies routing context.
 *
 * Classic script (IIFE). Screens read and commit through this door.
 * `createParams` builds an outbound query bag; `commitParams` writes in place
 * (replaceState on web). A caller that navigates must assign location.href
 * itself — never convert that into commitParams.
 */
(function (global) {
  'use strict';

  var SESSION_STORAGE_KEY = 'gob:franchise_context';

  function isRuntime(value) {
    return value === 'local' || value === 'hosted';
  }

  function defaultRuntime() {
    // Desktop first play is a local franchise. Web stays hosted unless the
    // query string (Url) or session (Session) says otherwise.
    if (typeof window !== 'undefined' && window.GOB_BUILD_PROFILE === 'desktop') {
      return 'local';
    }
    return 'hosted';
  }

  function liveSearch(loc) {
    if (!loc) return '';
    return loc.search == null ? '' : String(loc.search);
  }

  function paramsFromSearch(search) {
    return new URLSearchParams(search || '');
  }

  function applySearchToLocation(loc, history, search) {
    var qs = search ? (search.charAt(0) === '?' ? search : '?' + search) : '';
    var pathname = (loc && loc.pathname) || '';
    var hash = (loc && loc.hash) || '';
    var next = pathname + qs + hash;
    var usedReplace = false;
    if (history && typeof history.replaceState === 'function') {
      try {
        history.replaceState(history.state, '', next);
        usedReplace = true;
      } catch (e) { /* jsdom / about:blank stubs */ }
    }
    // Assigning window.location.search navigates (reload). After a successful
    // replaceState the live Location is already updated. Only write loc.search
    // on stubs (unit tests) or when replaceState is unavailable.
    var isLiveLocation = typeof window !== 'undefined' && loc === window.location;
    if (loc && (!usedReplace || !isLiveLocation)) {
      loc.search = qs;
    }
  }

  function UrlContextProvider(opts) {
    opts = opts || {};
    this._loc = opts.location || (typeof window !== 'undefined' ? window.location : { search: '' });
    this._history = opts.history || (typeof window !== 'undefined' ? window.history : null);
  }

  UrlContextProvider.prototype._params = function () {
    return paramsFromSearch(liveSearch(this._loc));
  };

  UrlContextProvider.prototype.get = function (key) {
    if (key === 'runtime') {
      var fromUrl = this._params().get('runtime');
      return isRuntime(fromUrl) ? fromUrl : defaultRuntime();
    }
    var value = this._params().get(key);
    return value == null ? null : value;
  };

  UrlContextProvider.prototype.getAll = function () {
    var out = {};
    this._params().forEach(function (value, key) {
      out[key] = value;
    });
    if (!isRuntime(out.runtime)) out.runtime = defaultRuntime();
    return out;
  };

  UrlContextProvider.prototype.set = function (key, value) {
    var params = this._params();
    if (value == null || value === '') params.delete(key);
    else params.set(key, String(value));
    applySearchToLocation(this._loc, this._history, params.toString());
  };

  UrlContextProvider.prototype.setMany = function (values) {
    var params = this._params();
    Object.keys(values || {}).forEach(function (key) {
      var value = values[key];
      if (value == null || value === '') params.delete(key);
      else params.set(key, String(value));
    });
    applySearchToLocation(this._loc, this._history, params.toString());
  };

  UrlContextProvider.prototype.toSearchParams = function () {
    return paramsFromSearch(liveSearch(this._loc));
  };

  UrlContextProvider.prototype.commitParams = function (params) {
    applySearchToLocation(
      this._loc,
      this._history,
      params && typeof params.toString === 'function' ? params.toString() : ''
    );
  };

  function SessionContextProvider(opts) {
    opts = opts || {};
    this._storage = opts.storage || (typeof localStorage !== 'undefined' ? localStorage : null);
    this._loc = opts.location || (typeof window !== 'undefined' ? window.location : { search: '' });
    this._state = this._load();
    this._save();
  }

  SessionContextProvider.prototype._load = function () {
    var fallback = { runtime: defaultRuntime() };
    var stored = fallback;
    if (this._storage && typeof this._storage.getItem === 'function') {
      try {
        var raw = this._storage.getItem(SESSION_STORAGE_KEY);
        if (raw) {
          var parsed = JSON.parse(raw);
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) stored = parsed;
        }
      } catch (e) { /* keep fallback */ }
    }
    // Screens still navigate with ?franchise_id= on the href (133 hard
    // navigations). Session is the store, but an inbound query is how this
    // navigation names the franchise — absorb it, then persist.
    var fromUrl = {};
    try {
      paramsFromSearch(liveSearch(this._loc)).forEach(function (value, key) {
        if (value != null && value !== '') fromUrl[key] = String(value);
      });
    } catch (e) { /* ignore */ }
    var merged = Object.assign({}, stored, fromUrl);
    if (!isRuntime(merged.runtime)) merged.runtime = defaultRuntime();
    return merged;
  };

  SessionContextProvider.prototype._save = function () {
    if (!this._storage || typeof this._storage.setItem !== 'function') return;
    this._storage.setItem(SESSION_STORAGE_KEY, JSON.stringify(this._state));
  };

  SessionContextProvider.prototype.get = function (key) {
    if (key === 'runtime') {
      return isRuntime(this._state.runtime) ? this._state.runtime : defaultRuntime();
    }
    if (!Object.prototype.hasOwnProperty.call(this._state, key)) return null;
    var value = this._state[key];
    return value == null ? null : String(value);
  };

  SessionContextProvider.prototype.getAll = function () {
    var out = {};
    Object.keys(this._state).forEach(function (key) {
      if (this._state[key] != null) out[key] = String(this._state[key]);
    }, this);
    if (!isRuntime(out.runtime)) out.runtime = defaultRuntime();
    return out;
  };

  SessionContextProvider.prototype.set = function (key, value) {
    if (value == null || value === '') delete this._state[key];
    else this._state[key] = String(value);
    if (key === 'runtime' && !isRuntime(this._state.runtime)) {
      this._state.runtime = defaultRuntime();
    }
    this._save();
  };

  SessionContextProvider.prototype.setMany = function (values) {
    Object.keys(values || {}).forEach(function (key) {
      var value = values[key];
      if (value == null || value === '') delete this._state[key];
      else this._state[key] = String(value);
    }, this);
    if (!isRuntime(this._state.runtime)) this._state.runtime = defaultRuntime();
    this._save();
  };

  SessionContextProvider.prototype.toSearchParams = function () {
    var params = new URLSearchParams();
    Object.keys(this._state).forEach(function (key) {
      if (this._state[key] != null && this._state[key] !== '') {
        params.set(key, String(this._state[key]));
      }
    }, this);
    return params;
  };

  SessionContextProvider.prototype.commitParams = function (params) {
    var next = {};
    if (params && typeof params.forEach === 'function') {
      params.forEach(function (value, key) {
        next[key] = value;
      });
    }
    if (!isRuntime(next.runtime)) next.runtime = this.get('runtime') || defaultRuntime();
    this._state = next;
    this._save();
  };

  function FranchiseContext(provider) {
    this._provider = provider;
  }

  Object.defineProperty(FranchiseContext.prototype, 'runtime', {
    get: function () {
      return this._provider.get('runtime') || defaultRuntime();
    },
  });

  Object.defineProperty(FranchiseContext.prototype, 'franchiseId', {
    get: function () {
      return this._provider.get('franchise_id');
    },
  });

  FranchiseContext.prototype.get = function (key) {
    return this._provider.get(key);
  };

  FranchiseContext.prototype.getAll = function () {
    return this._provider.getAll();
  };

  FranchiseContext.prototype.set = function (key, value) {
    return this._provider.set(key, value);
  };

  FranchiseContext.prototype.setMany = function (values) {
    return this._provider.setMany(values);
  };

  FranchiseContext.prototype.toSearchParams = function () {
    return this._provider.toSearchParams();
  };

  FranchiseContext.prototype.commitParams = function (params) {
    return this._provider.commitParams(params);
  };

  FranchiseContext.prototype.createParams = function () {
    return new URLSearchParams();
  };

  FranchiseContext.prototype.parseSearch = function (search) {
    return paramsFromSearch(search);
  };

  function resolveBuildProfile(opts) {
    if (opts && opts.buildProfile) return opts.buildProfile;
    if (typeof window !== 'undefined' && window.GOB_BUILD_PROFILE === 'desktop') {
      return 'desktop';
    }
    return 'web';
  }

  function createFranchiseContext(opts) {
    opts = opts || {};
    var profile = resolveBuildProfile(opts);
    var Provider = profile === 'desktop' ? SessionContextProvider : UrlContextProvider;
    return new FranchiseContext(new Provider(opts));
  }

  var api = {
    SESSION_STORAGE_KEY: SESSION_STORAGE_KEY,
    UrlContextProvider: UrlContextProvider,
    SessionContextProvider: SessionContextProvider,
    FranchiseContext: FranchiseContext,
    createFranchiseContext: createFranchiseContext,
    createParams: function () { return new URLSearchParams(); },
    parseSearch: function (search) { return paramsFromSearch(search); },
  };

  global.FranchiseContextLib = api;
  global.FranchiseContext = createFranchiseContext();

  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
