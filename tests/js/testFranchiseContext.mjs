/**
 * WS-3 slice 1: FranchiseContext door + both providers.
 *
 * Url reads must match URLSearchParams bit-for-bit. Session must survive a
 * new provider instance (hard navigation). Routing peek uses .runtime.
 */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const CTX_SRC = fs.readFileSync(
  path.join(ROOT, 'FrontEnd/static/js/shared/franchiseContext.js'),
  'utf8',
);
const API_SRC = fs.readFileSync(
  path.join(ROOT, 'FrontEnd/static/js/config/api-config.js'),
  'utf8',
);

const RESUME_KEYS = [
  'franchise_id',
  'game_id',
  'team_id',
  'mode',
  'my_team',
  'resume_from_timeout',
  'resume_from_anchor',
  'quarter_break_from',
  'consume_resume_anchor',
  'user_team_id',
  'home_id',
  'away_id',
];

function assertEqual(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function memoryStorage() {
  const data = Object.create(null);
  return {
    getItem(key) {
      return Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null;
    },
    setItem(key, value) {
      data[key] = String(value);
    },
    removeItem(key) {
      delete data[key];
    },
    _data: data,
  };
}

function mutableLocation(search) {
  const loc = {
    pathname: '/static/court.html',
    search: search || '',
    hash: '',
    hostname: 'localhost',
  };
  const history = {
    state: null,
    replaceState(_state, _title, url) {
      const parsed = new URL(url, 'http://localhost');
      loc.pathname = parsed.pathname;
      loc.search = parsed.search;
      loc.hash = parsed.hash;
    },
  };
  return { loc, history };
}

function loadLib(overrides = {}) {
  const { loc, history } = mutableLocation(overrides.search || '');
  const storage = overrides.storage || memoryStorage();
  const windowStub = {
    location: loc,
    history,
    GOB_BUILD_PROFILE: overrides.GOB_BUILD_PROFILE,
    localStorage: storage,
  };
  const sandbox = {
    window: windowStub,
    localStorage: storage,
    URLSearchParams,
    console,
    module: undefined,
  };
  vm.runInNewContext(CTX_SRC, sandbox, { filename: 'franchiseContext.js' });
  return {
    lib: windowStub.FranchiseContextLib,
    auto: windowStub.FranchiseContext,
    loc,
    history,
    storage,
    window: windowStub,
  };
}

function loadApi(windowStub, extra = {}) {
  Object.assign(windowStub, extra);
  const sandbox = {
    window: windowStub,
    console: { log() {}, error() {}, warn() {} },
    document: undefined,
  };
  vm.runInNewContext(API_SRC, sandbox, { filename: 'api-config.js' });
  return windowStub.API_CONFIG;
}

function main() {
  // --- Url get is bit-identical to URLSearchParams ---
  {
    const search =
      '?franchise_id=f1&game_id=g9&team_id=t3&mode=franchise&my_team=home' +
      '&resume_from_timeout=true&resume_from_anchor=true' +
      '&quarter_break_from=2&consume_resume_anchor=true' +
      '&user_team_id=u1&home_id=h1&away_id=a1&clock=5:00';
    const { lib, loc } = loadLib({ search });
    const ctx = lib.createFranchiseContext({
      buildProfile: 'web',
      location: loc,
    });
    const raw = new URLSearchParams(loc.search);
    for (const key of RESUME_KEYS) {
      assertEqual(ctx.get(key), raw.get(key), `Url get(${key})`);
    }
    assertEqual(ctx.get('clock'), '5:00', 'Url get(clock)');
    assertEqual(ctx.get('missing'), null, 'Url get missing');
    assertEqual(ctx.franchiseId, 'f1', 'franchiseId alias');
    assertEqual(ctx.runtime, 'hosted', 'runtime defaults hosted when absent');
    assertEqual(ctx.toSearchParams().toString(), raw.toString(), 'toSearchParams == live query');
  }

  // --- Url runtime from query when present ---
  {
    const { lib, loc } = loadLib({ search: '?franchise_id=f1&runtime=local' });
    const ctx = lib.createFranchiseContext({ buildProfile: 'web', location: loc });
    assertEqual(ctx.runtime, 'local', 'Url runtime=local honored');
  }

  // --- Url set uses replaceState; subsequent get matches ---
  {
    const { lib, loc, history } = loadLib({ search: '?franchise_id=f1' });
    const ctx = lib.createFranchiseContext({
      buildProfile: 'web',
      location: loc,
      history,
    });
    ctx.set('game_id', 'g2');
    ctx.setMany({ quarter: '2', clock: '7:00' });
    assertEqual(ctx.get('franchise_id'), 'f1', 'set preserves other keys');
    assertEqual(ctx.get('game_id'), 'g2', 'set game_id');
    assertEqual(ctx.get('quarter'), '2', 'setMany quarter');
    const raw = new URLSearchParams(loc.search);
    assertEqual(raw.get('game_id'), 'g2', 'query string updated');
    assertEqual(raw.get('franchise_id'), 'f1', 'franchise_id still in query');
  }

  // --- Boot selects provider ---
  {
    const web = loadLib();
    assert(web.auto._provider instanceof web.lib.UrlContextProvider, 'web boot → Url');
    const desk = loadLib({ GOB_BUILD_PROFILE: 'desktop' });
    assert(desk.auto._provider instanceof desk.lib.SessionContextProvider, 'desktop boot → Session');
  }

  // --- Session persists across a new instance (hard navigation) ---
  {
    const storage = memoryStorage();
    const firstPage = loadLib({ GOB_BUILD_PROFILE: 'desktop', storage, search: '?franchise_id=FROM_URL' });
    const ctx1 = firstPage.lib.createFranchiseContext({
      buildProfile: 'desktop',
      storage,
      location: firstPage.loc,
    });
    assertEqual(ctx1.get('franchise_id'), null, 'Session ignores query string');
    ctx1.setMany({
      franchise_id: 'f-desk',
      game_id: 'g-desk',
      resume_from_timeout: 'true',
      runtime: 'local',
    });
    assertEqual(ctx1.runtime, 'local', 'Session runtime set');

    const secondPage = loadLib({
      GOB_BUILD_PROFILE: 'desktop',
      storage,
      search: '',
    });
    const ctx2 = secondPage.lib.createFranchiseContext({
      buildProfile: 'desktop',
      storage,
      location: secondPage.loc,
    });
    assertEqual(ctx2.get('franchise_id'), 'f-desk', 'Session franchise_id survived navigation');
    assertEqual(ctx2.get('game_id'), 'g-desk', 'Session game_id survived navigation');
    assertEqual(ctx2.get('resume_from_timeout'), 'true', 'Session resume flag survived');
    assertEqual(ctx2.runtime, 'local', 'Session runtime survived');
    assertEqual(storage.getItem('franchise_id'), null, 'did not write bare franchise_id');
    assertEqual(storage.getItem('franchiseId'), null, 'did not write bare franchiseId');
    assert(storage.getItem(firstPage.lib.SESSION_STORAGE_KEY), 'wrote the session blob');
  }

  // --- commitParams writes the whole bag in place (no navigation) ---
  {
    const { lib, loc, history } = loadLib({ search: '?franchise_id=f1&resume_from_timeout=true' });
    const ctx = lib.createFranchiseContext({
      buildProfile: 'web',
      location: loc,
      history,
    });
    const bag = ctx.toSearchParams();
    bag.set('resume_from_timeout', 'false');
    bag.delete('active_resume');
    ctx.commitParams(bag);
    assertEqual(ctx.get('franchise_id'), 'f1', 'commitParams keeps franchise_id');
    assertEqual(ctx.get('resume_from_timeout'), 'false', 'commitParams updated flag');
    assertEqual(loc.pathname, '/static/court.html', 'commitParams does not change path');
  }

  // --- commitParams must not assign live location.search (that navigates) ---
  {
    const { lib, window: win } = loadLib({ search: '?franchise_id=f1' });
    let searchAssigns = 0;
    const loc = {
      pathname: '/static/court.html',
      hash: '',
      hostname: 'localhost',
      _search: '?franchise_id=f1&resume_from_timeout=true',
      get search() { return this._search; },
      set search(v) { searchAssigns += 1; this._search = v; },
    };
    win.location = loc;
    const history = {
      state: null,
      replaceState(_state, _title, url) {
        const parsed = new URL(url, 'http://localhost');
        loc.pathname = parsed.pathname;
        loc._search = parsed.search;
        loc.hash = parsed.hash;
      },
    };
    const ctx = lib.createFranchiseContext({
      buildProfile: 'web',
      location: loc,
      history,
    });
    const bag = ctx.toSearchParams();
    bag.set('resume_from_timeout', 'false');
    ctx.commitParams(bag);
    assertEqual(searchAssigns, 0, 'commitParams must not assign live location.search');
    assertEqual(ctx.get('resume_from_timeout'), 'false', 'commitParams still updated query');
    assertEqual(loc.pathname, '/static/court.html', 'path unchanged after commitParams');
  }

  // --- Routing: peek FranchiseContext.runtime; no-args never peeks ---
  {
    const { lib, loc, window: win } = loadLib({ GOB_BUILD_PROFILE: 'desktop' });
    const ctx = lib.createFranchiseContext({
      buildProfile: 'desktop',
      location: loc,
      storage: memoryStorage(),
    });
    ctx.set('runtime', 'local');
    win.FranchiseContext = ctx;
    win.GOB_BUILD_PROFILE = 'desktop';
    const api = loadApi(win);
    const remote = api._resolveBaseUrl('localhost');
    assertEqual(api.getBaseUrl(), remote, 'getBaseUrl() no-args ignores FranchiseContext');
    assertEqual(
      api.getBaseUrl({ category: 'franchise' }),
      'http://127.0.0.1:8000',
      'desktop + context.runtime local + franchise → loopback',
    );
    assertEqual(
      api.getBaseUrl({ category: 'auth' }),
      remote,
      'desktop + local + auth stays remote',
    );
  }

  // --- Web profile: FranchiseContext.runtime local still remote ---
  {
    const { lib, loc, window: win } = loadLib();
    const ctx = lib.createFranchiseContext({ buildProfile: 'web', location: loc });
    ctx.set('runtime', 'local');
    win.FranchiseContext = ctx;
    const api = loadApi(win);
    const remote = api._resolveBaseUrl('localhost');
    assertEqual(api.getBaseUrl(), remote, 'web no-args unchanged');
    assertEqual(
      api.getBaseUrl({ category: 'franchise' }),
      remote,
      'web + FranchiseContext.local still remote',
    );
  }

  console.log(JSON.stringify({ ok: true, resumeKeys: RESUME_KEYS.length }));
}

main();
