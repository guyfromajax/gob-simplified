/**
 * Client store for franchise browse GETs.
 *
 * One module. Caches server responses only. It does not compute game data.
 * A resolved entry in this document is shared (no second request). A new
 * document revalidates with If-None-Match. A newer season, week, browse_rev,
 * or BUILD drops every cached body for that franchise.
 */
(function (root) {
  'use strict';

  var nativeFetch = typeof root.fetch === 'function' ? root.fetch.bind(root) : null;
  var memory = new Map();
  var inflight = new Map();
  var generation = new Map();
  var PERSIST_PREFIX = 'gob-store:';
  var MAX_PERSIST_CHARS = 1500000;

  var BROWSE_PREFIXES = [
    '/franchise/command-center/data',
    '/franchise/standings',
    '/franchise/schedule',
    '/franchise/leaders',
    '/franchise/team-stats',
    '/franchise/team-player-stats',
    '/franchise/team-data',
    '/franchise/state',
    '/franchise/news',
    '/franchise/recruiting-data',
    '/franchise/recruiting-results',
    '/franchise/practice-squad',
    '/franchise/awards',
    '/franchise/scouting-report',
    '/api/gameplan',
    '/api/playbooks',
    '/teams',
    '/roster/',
    '/player/',
    '/recruit/'
  ];

  function storage() {
    try {
      return root.sessionStorage;
    } catch (err) {
      return null;
    }
  }

  function requestUrl(input) {
    if (typeof input === 'string') return input;
    if (input && typeof input.url === 'string') return input.url;
    return '';
  }

  function requestMethod(input, init) {
    if (init && init.method) return init.method;
    if (input && typeof input.method === 'string') return input.method;
    return 'GET';
  }

  function canonical(url) {
    try {
      var base = (root.location && root.location.href) || 'http://localhost/';
      var parsed = new URL(url, base);
      var keys = [];
      parsed.searchParams.forEach(function (_value, key) {
        if (keys.indexOf(key) === -1) keys.push(key);
      });
      keys.sort();
      var params = new URLSearchParams();
      keys.forEach(function (key) {
        parsed.searchParams.getAll(key).slice().sort().forEach(function (value) {
          params.append(key, value);
        });
      });
      var search = params.toString();
      return parsed.pathname + (search ? '?' + search : '');
    } catch (err) {
      return String(url || '');
    }
  }

  function pathnameOf(url) {
    try {
      var base = (root.location && root.location.href) || 'http://localhost/';
      return new URL(url, base).pathname;
    } catch (err) {
      return String(url || '');
    }
  }

  function neverCache(url) {
    var path = pathnameOf(url);
    var query = '';
    try {
      var base = (root.location && root.location.href) || 'http://localhost/';
      query = new URL(url, base).search;
    } catch (err) {
      query = String(url || '');
    }
    if (/[?&]profile=1(?:&|$)/.test(query)) return true;
    if (path.indexOf('/api/simulate-quarter') !== -1) return true;
    if (path.indexOf('/api/auth') !== -1 || path.indexOf('/auth/') === 0) return true;
    if (/^\/api\/game\/[^/]+/.test(path)) return true;
    return false;
  }

  function isBrowseGet(url) {
    if (neverCache(url)) return false;
    var path = pathnameOf(url);
    for (var i = 0; i < BROWSE_PREFIXES.length; i += 1) {
      var prefix = BROWSE_PREFIXES[i];
      if (path === prefix || path.indexOf(prefix) === 0) return true;
    }
    return false;
  }

  function parseEtag(etag) {
    if (!etag) return null;
    var raw = String(etag).trim();
    if (raw.slice(0, 2) === 'W/') raw = raw.slice(2).trim();
    if (raw.charAt(0) === '"') raw = raw.slice(1);
    if (raw.charAt(raw.length - 1) === '"') raw = raw.slice(0, -1);
    var parts = raw.split(':');
    if (parts.length < 6) return null;
    var season = Number(parts[1]);
    var week = Number(parts[2]);
    var rev = Number(parts[3]);
    if (!parts[0] || !isFinite(season) || !isFinite(week) || !isFinite(rev)) return null;
    return {
      franchiseId: parts[0],
      season: season,
      week: week,
      rev: rev,
      build: parts[4]
    };
  }

  function generationMoved(prev, next) {
    if (!prev || !next) return false;
    if (next.season !== prev.season) return next.season > prev.season;
    if (next.week !== prev.week) return next.week > prev.week;
    if (next.rev !== prev.rev) return next.rev > prev.rev;
    if (String(next.build) !== String(prev.build)) return true;
    return false;
  }

  function readBlob(franchiseId) {
    var store = storage();
    if (!store || !franchiseId) return null;
    try {
      var raw = store.getItem(PERSIST_PREFIX + franchiseId);
      if (!raw) return null;
      var blob = JSON.parse(raw);
      if (!blob || typeof blob !== 'object') return null;
      return blob;
    } catch (err) {
      return null;
    }
  }

  function writeBlob(franchiseId, blob) {
    var store = storage();
    if (!store || !franchiseId) return;
    try {
      store.setItem(PERSIST_PREFIX + franchiseId, JSON.stringify(blob));
    } catch (err) {
      // Quota, private mode, or a test that makes sessionStorage throw.
    }
  }

  function dropFranchise(franchiseId) {
    if (!franchiseId) return;
    var memoryKeys = [];
    memory.forEach(function (entry, key) {
      var parsed = parseEtag(entry && entry.etag);
      if (parsed && parsed.franchiseId === franchiseId) memoryKeys.push(key);
    });
    memoryKeys.forEach(function (key) { memory.delete(key); });
    generation.delete(franchiseId);
    var store = storage();
    if (!store) return;
    try {
      var names = [];
      for (var i = 0; i < store.length; i += 1) names.push(store.key(i));
      names.forEach(function (key) {
        if (!key) return;
        if (key === PERSIST_PREFIX + franchiseId || key.indexOf('fcc-shell:' + franchiseId) === 0) {
          store.removeItem(key);
        }
      });
    } catch (err) {}
  }

  function currentGeneration(franchiseId) {
    if (generation.has(franchiseId)) return generation.get(franchiseId);
    var blob = readBlob(franchiseId);
    if (blob && blob.generation) return blob.generation;
    return null;
  }

  function noteGeneration(parsed) {
    if (!parsed) return;
    var prev = currentGeneration(parsed.franchiseId);
    if (generationMoved(prev, parsed)) dropFranchise(parsed.franchiseId);
    generation.set(parsed.franchiseId, {
      season: parsed.season,
      week: parsed.week,
      rev: parsed.rev,
      build: parsed.build
    });
  }

  function persistEntry(franchiseId, urlKey, entry) {
    if (!franchiseId || !entry) return;
    var bodyText = '';
    try {
      bodyText = JSON.stringify(entry.body);
    } catch (err) {
      return;
    }
    if (bodyText.length > MAX_PERSIST_CHARS) return;
    var blob = readBlob(franchiseId) || {};
    blob.generation = generation.get(franchiseId) || blob.generation || null;
    blob.entries = blob.entries && typeof blob.entries === 'object' ? blob.entries : {};
    blob.entries[urlKey] = { etag: entry.etag, body: entry.body };
    writeBlob(franchiseId, blob);
  }

  function readPersisted(franchiseId, urlKey) {
    var blob = readBlob(franchiseId);
    if (!blob || !blob.entries) return null;
    return blob.entries[urlKey] || null;
  }

  function franchiseIdFromUrl(url) {
    try {
      var base = (root.location && root.location.href) || 'http://localhost/';
      return new URL(url, base).searchParams.get('franchise_id') || '';
    } catch (err) {
      return '';
    }
  }

  function franchiseIdFromBody(init) {
    if (!init || typeof init.body !== 'string') return '';
    try {
      var parsed = JSON.parse(init.body);
      if (parsed && parsed.franchise_id) return String(parsed.franchise_id);
    } catch (err) {}
    return '';
  }

  function copyHeaders(target, source) {
    if (!source) return;
    if (typeof source.forEach === 'function') {
      source.forEach(function (value, key) { target[key] = value; });
      return;
    }
    Object.keys(source).forEach(function (key) { target[key] = source[key]; });
  }

  function authHeaders(init) {
    var headers = {};
    if (root.API_CONFIG && typeof root.API_CONFIG.getAuthHeaders === 'function') {
      copyHeaders(headers, root.API_CONFIG.getAuthHeaders() || {});
    }
    if (init && init.headers) copyHeaders(headers, init.headers);
    return headers;
  }

  function jsonResponse(body, status, etag) {
    var headers = { 'Content-Type': 'application/json' };
    if (etag) headers.ETag = etag;
    var text;
    try {
      text = body == null ? 'null' : JSON.stringify(body);
    } catch (err) {
      text = 'null';
    }
    return new Response(text, { status: status || 200, headers: headers });
  }

  function remember(key, entry, parsed) {
    memory.set(key, entry);
    if (parsed) persistEntry(parsed.franchiseId, key, entry);
  }

  function fetchRevalidate(url, key, init) {
    var fid = franchiseIdFromUrl(url);
    var stored = memory.get(key) || null;
    if (!stored && fid) {
      var persisted = readPersisted(fid, key);
      if (persisted && persisted.body != null && persisted.etag) stored = persisted;
    }
    var headers = authHeaders(init);
    if (stored && stored.etag) headers['If-None-Match'] = stored.etag;
    var nextInit = {};
    if (init) {
      Object.keys(init).forEach(function (name) {
        if (name !== 'headers') nextInit[name] = init[name];
      });
    }
    nextInit.method = 'GET';
    nextInit.headers = headers;
    return nativeFetch(url, nextInit).then(function (res) {
      var etag = res.headers.get('ETag') || (stored && stored.etag) || '';
      if (res.status === 304 && stored && stored.body != null) {
        var parsed304 = parseEtag(etag || stored.etag);
        noteGeneration(parsed304);
        var entry304 = { body: stored.body, etag: etag || stored.etag, status: 200 };
        remember(key, entry304, parsed304);
        return entry304;
      }
      return res.text().then(function (text) {
        var body = null;
        if (text) {
          try { body = JSON.parse(text); } catch (err) { body = null; }
        }
        if (!res.ok) {
          return { body: body, raw: text, etag: etag, status: res.status, passthrough: true };
        }
        var parsed = parseEtag(etag);
        noteGeneration(parsed);
        var entry = { body: body, etag: etag, status: res.status };
        if (parsed) remember(key, entry, parsed);
        else memory.set(key, entry);
        return entry;
      }, function () {
        return { body: null, raw: '', etag: etag, status: res.status, passthrough: true };
      });
    });
  }

  function entryToResponse(entry) {
    if (entry && entry.passthrough) {
      return new Response(entry.raw || '', {
        status: entry.status || 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    return jsonResponse(entry.body, entry.status || 200, entry.etag);
  }

  function get(url, init) {
    if (!nativeFetch) return Promise.reject(new Error('fetch unavailable'));
    if (neverCache(url) || !isBrowseGet(url)) return nativeFetch(url, init);
    var key = canonical(url);
    if (inflight.has(key)) {
      return inflight.get(key).then(entryToResponse);
    }
    if (memory.has(key)) {
      return Promise.resolve(entryToResponse(memory.get(key)));
    }
    var pending = fetchRevalidate(url, key, init).then(function (entry) {
      inflight.delete(key);
      return entry;
    }, function (err) {
      inflight.delete(key);
      throw err;
    });
    inflight.set(key, pending);
    return pending.then(entryToResponse);
  }

  function clearFranchiseFromWrite(url, init) {
    var fid = franchiseIdFromUrl(url) || franchiseIdFromBody(init);
    if (!fid && root.location) fid = franchiseIdFromUrl(root.location.href);
    if (fid) dropFranchise(fid);
  }

  function isWrite(method) {
    var name = String(method || 'GET').toUpperCase();
    return name === 'POST' || name === 'PUT' || name === 'PATCH' || name === 'DELETE';
  }

  function isFranchiseWrite(url, method) {
    if (!isWrite(method)) return false;
    var path = pathnameOf(url);
    if (path.indexOf('/api/simulate-quarter') !== -1) return false;
    if (/^\/api\/game\//.test(path)) return false;
    return path.indexOf('/franchise/') !== -1
      || path.indexOf('/api/gameplan') !== -1
      || path.indexOf('/api/playbooks') !== -1;
  }

  function mutate(url, options) {
    var opts = options || {};
    return nativeFetch(url, opts).then(function (res) {
      if (res && res.ok) clearFranchiseFromWrite(url, opts);
      return res;
    });
  }

  function install() {
    if (!nativeFetch || root.__gobStoreInstalled) return;
    root.__gobStoreInstalled = true;
    root.fetch = function (input, init) {
      var url = requestUrl(input);
      var method = requestMethod(input, init);
      if (String(method).toUpperCase() === 'GET' && isBrowseGet(url) && !neverCache(url)) {
        return get(url, init);
      }
      if (isFranchiseWrite(url, method)) {
        if (!init && input && typeof input !== 'string') {
          return nativeFetch(input).then(function (res) {
            if (res && res.ok) clearFranchiseFromWrite(url, null);
            return res;
          });
        }
        return mutate(url, init || { method: method });
      }
      return nativeFetch(input, init);
    };
  }

  install();

  root.GOBStore = {
    get: function (url, init) {
      return get(url, init).then(function (res) {
        if (!res.ok) {
          var err = new Error('Request failed');
          err.status = res.status;
          throw err;
        }
        return res.json();
      });
    },
    mutate: mutate,
    clearFranchise: dropFranchise
  };
})(typeof window !== 'undefined' ? window : this);
