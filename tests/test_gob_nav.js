const test = require('node:test');
const assert = require('node:assert/strict');
const { install } = require('../FrontEnd/static/js/shared/gobNav.js');

function fakeWindow(start, seed) {
  const store = new Map();
  if (seed) Object.keys(seed).forEach((key) => store.set(key, seed[key]));
  const listeners = {};
  const win = {
    scrollY: 0,
    pageYOffset: 0,
    scrollTo(x, y) { win.scrollY = y; },
    location: {
      origin: 'http://localhost:8000',
      pathname: start.pathname,
      search: start.search || '',
      hash: '',
      assign(url) { win.navigations.push(['assign', url]); },
      replace(url) { win.navigations.push(['replace', url]); },
      reload() { win.navigations.push(['reload']); },
    },
    history: {
      scrollRestoration: 'auto',
      state: null,
      back() { win.navigations.push(['back']); },
      go(delta) { win.navigations.push(['go', delta]); },
      replaceState(state, _t, url) {
        win.navigations.push(['replaceState', url]);
        win.history.state = state;
        if (typeof url === 'string') {
          const q = url.indexOf('?');
          win.location.pathname = q === -1 ? url : url.slice(0, q);
          win.location.search = q === -1 ? '' : url.slice(q);
        }
      },
      pushState(state, _t, url) {
        win.navigations.push(['pushState', url, state && state.gobIdx]);
        win.history.state = state;
        if (typeof url === 'string') {
          const hash = url.indexOf('#');
          const bare = hash === -1 ? url : url.slice(0, hash);
          const q = bare.indexOf('?');
          win.location.pathname = q === -1 ? bare : bare.slice(0, q);
          win.location.search = q === -1 ? '' : bare.slice(q);
          win.location.hash = hash === -1 ? '' : url.slice(hash);
        }
      },
    },
    sessionStorage: {
      getItem(k) { return store.has(k) ? store.get(k) : null; },
      setItem(k, v) { store.set(k, v); },
      removeItem(k) { store.delete(k); },
    },
    document: {
      referrer: '',
      addEventListener(type, fn, capture) { listeners['document:' + type] = fn; },
      querySelector() { return null; },
      querySelectorAll() { return []; },
    },
    addEventListener(type, fn) { listeners[type] = fn; },
    navigations: [],
    listeners,
  };
  win.GOBNav = install(win);
  return win;
}

test('in-app back uses history.back when the previous entry is the parent', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=standings-tab' });
  win.GOBNav.go('/team-roster-view.html?franchise_id=f1&team_id=t1');
  win.location.pathname = '/team-roster-view.html';
  win.location.search = '?franchise_id=f1&team_id=t1';
  win.listeners.pageshow({ persisted: false });
  win.GOBNav.back('/franchise-command-center.html?franchise_id=f1&tab=standings-tab');
  assert.deepEqual(win.navigations.at(-1), ['back']);
});

test('in-app back replaces when the previous entry is not the parent', () => {
  const win = fakeWindow({ pathname: '/player-detail.html', search: '?id=p1' });
  win.GOBNav.back('/team-roster-view.html?team_id=t1');
  const last = win.navigations.at(-1);
  assert.equal(last[0], 'replace');
  assert.match(last[1], /team-roster-view\.html/);
});

test('replace keeps a single stack slot so back skips the flow', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1' });
  win.GOBNav.go('/set-lineup.html?franchise_id=f1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1';
  win.listeners.pageshow({ persisted: false });
  win.GOBNav.replace('/court.html?franchise_id=f1');
  win.location.pathname = '/court.html';
  win.location.search = '?franchise_id=f1';
  win.GOBNav.replace('/franchise-command-center.html?franchise_id=f1');
  win.location.pathname = '/franchise-command-center.html';
  win.location.search = '?franchise_id=f1';
  win.listeners.pageshow({ persisted: false });
  win.navigations.length = 0;
  win.GOBNav.back('/franchise-command-center.html?franchise_id=f1');
  assert.deepEqual(win.navigations.at(-1), ['back']);
});

test('browser back is not used when there is no matching parent', () => {
  const win = fakeWindow({ pathname: '/alpha-feedback.html', search: '' });
  win.GOBNav.back('/mode-select.html');
  assert.equal(win.navigations.some((row) => row[0] === 'back'), false);
  assert.equal(win.navigations.at(-1)[0], 'replace');
});

test('a pushed lineup peek comes back with history.back', () => {
  const lineup = '/set-lineup.html?franchise_id=f1&game_id=g1&quarter=2';
  const win = fakeWindow({ pathname: '/set-lineup.html', search: '?franchise_id=f1&game_id=g1&quarter=2' });
  win.GOBNav.go('/player-detail.html?id=p1&return_url=' + encodeURIComponent(lineup));
  win.location.pathname = '/player-detail.html';
  win.location.search = '?id=p1&return_url=' + encodeURIComponent(lineup);
  win.listeners.pageshow({ persisted: false });
  win.navigations.length = 0;
  win.GOBNav.back(lineup);
  assert.deepEqual(win.navigations.at(-1), ['back']);
});

test('closed-game guard uses one resume-state read while the game is live', async () => {
  const win = fakeWindow({ pathname: '/set-lineup.html', search: '?franchise_id=f1&game_id=g1' });
  const urls = [];
  win.API_CONFIG = {
    buildUrl(path) { return 'http://localhost:8000' + path; },
    getAuthHeaders() { return {}; },
  };
  win.fetch = (url) => {
    urls.push(String(url));
    return Promise.resolve({ ok: true, json: async () => ({ status: 'quarter_break' }) });
  };
  const redirected = await win.GOBNav.guardClosedFranchiseGame();
  assert.equal(redirected, false);
  assert.deepEqual(urls, ['http://localhost:8000/api/game/g1/resume-state']);
});

test('closed-game guard reads command center only after the game is final', async () => {
  const win = fakeWindow({ pathname: '/court.html', search: '?franchise_id=f1&game_id=g1' });
  const urls = [];
  win.API_CONFIG = {
    buildUrl(path) { return 'http://localhost:8000' + path; },
    getAuthHeaders() { return {}; },
  };
  win.fetch = (url) => {
    urls.push(String(url));
    if (String(url).includes('resume-state')) {
      return Promise.resolve({ ok: true, json: async () => ({ status: 'final' }) });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ week: 4, last_game_summary: { game_id: 'g1', week: 3 } }),
    });
  };
  const redirected = await win.GOBNav.guardClosedFranchiseGame();
  assert.equal(redirected, true);
  assert.equal(urls.length, 2);
  assert.match(urls[0], /resume-state/);
  assert.match(urls[1], /command-center\/data/);
  assert.equal(win.navigations.at(-1)[0], 'replace');
  assert.match(win.navigations.at(-1)[1], /franchise-command-center\.html/);
});

test('fcc bfcache peek return does not reload or call phase-b', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1' });
  win.fetch = () => { throw new Error('phase-b must not be fetched from pageshow'); };
  win.listeners.pageshow({ persisted: true });
  assert.equal(win.navigations.some((row) => row[0] === 'reload' || row[0] === 'replace'), false);
});

test('a repeat drill-down keeps the locker room that launched it', () => {
  const team = '/team-roster-view.html?team_id=t1';
  const fcc = '/franchise-command-center.html?franchise_id=f1&tab=standings-tab';
  const win = fakeWindow({ pathname: '/team-roster-view.html', search: '?team_id=t1' });
  win.GOBNav.go(fcc);
  win.location.pathname = '/franchise-command-center.html';
  win.location.search = '?franchise_id=f1&tab=standings-tab';
  win.listeners.pageshow({ persisted: false });
  win.GOBNav.go(team);
  win.location.pathname = '/team-roster-view.html';
  win.location.search = '?team_id=t1';
  win.listeners.pageshow({ persisted: false });
  win.navigations.length = 0;
  win.GOBNav.back(fcc);
  assert.deepEqual(win.navigations.at(-1), ['back']);
});

test('in-app back uses the browser referrer when the stack lost the locker room', () => {
  const win = fakeWindow({ pathname: '/team-roster-view.html', search: '?team_id=t1&return_tab=standings-tab' });
  win.document.referrer = 'http://localhost:8000/franchise-command-center.html?franchise_id=f1&tab=standings-tab';
  win.navigations.length = 0;
  win.GOBNav.back('/franchise-command-center.html?franchise_id=f1');
  assert.deepEqual(win.navigations.at(-1), ['back']);
});

test('replace fallback keeps return_tab when return_url has no tab', () => {
  const win = fakeWindow({ pathname: '/team-roster-view.html', search: '?team_id=t1&return_tab=roster-tab' });
  win.GOBNav.back('/franchise-command-center.html?franchise_id=f1');
  const last = win.navigations.at(-1);
  assert.equal(last[0], 'replace');
  assert.match(last[1], /tab=roster-tab/);
});

test('exitFlow backs into the locker room that launched the flow', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=game-plan-tab' });
  win.GOBNav.go('/set-lineup.html?franchise_id=f1&game_id=g1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.listeners.pageshow({ persisted: false });
  win.GOBNav.replace('/court.html?franchise_id=f1&game_id=g1');
  win.location.pathname = '/court.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.navigations.length = 0;
  win.fetch = () => { throw new Error('exitFlow must not fetch'); };
  win.GOBNav.exitFlow('/franchise-command-center.html?franchise_id=f1', { tab: 'home-tab' });
  assert.deepEqual(win.navigations.at(-1), ['go', -1]);
  const landing = JSON.parse(win.sessionStorage.getItem('gob_nav_exit'));
  assert.equal(landing.tab, 'home-tab');
  assert.equal(landing.fresh, true);
});

test('exitFlow keeps the tab the flow started from', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=training-tab' });
  win.GOBNav.go('/training.html?franchise_id=f1');
  win.location.pathname = '/training.html';
  win.location.search = '?franchise_id=f1';
  win.listeners.pageshow({ persisted: false });
  win.navigations.length = 0;
  win.GOBNav.exitFlow('/franchise-command-center.html?franchise_id=f1');
  assert.deepEqual(win.navigations.at(-1), ['go', -1]);
  const landing = JSON.parse(win.sessionStorage.getItem('gob_nav_exit'));
  assert.equal(landing.tab, 'training-tab');
});

test('exitFlow replaces when the locker room is not the previous entry', () => {
  const win = fakeWindow({ pathname: '/court.html', search: '?franchise_id=f1' });
  win.fetch = () => { throw new Error('exitFlow must not fetch'); };
  win.GOBNav.exitFlow('/franchise-command-center.html?franchise_id=f1', { tab: 'home-tab' });
  const last = win.navigations.at(-1);
  assert.equal(last[0], 'replace');
  assert.match(last[1], /tab=home-tab/);
});

test('locker room load applies a pending exit tab', () => {
  const win = fakeWindow(
    { pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=game-plan-tab' },
    { gob_nav_exit: JSON.stringify({ tab: 'home-tab', fresh: true }) }
  );
  const replaced = win.navigations.find((row) => row[0] === 'replaceState' && /home-tab/.test(row[1]));
  assert.ok(replaced);
  assert.match(replaced[1], /tab=home-tab/);
  assert.equal(win.sessionStorage.getItem('gob_nav_exit'), null);
});

test('bfcache locker room with a pending exit reloads instead of showing stale data', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=game-plan-tab' });
  win.sessionStorage.setItem('gob_nav_exit', JSON.stringify({ tab: 'home-tab', fresh: true }));
  win.fetch = () => { throw new Error('exit landing must not fetch phase-b'); };
  win.navigations.length = 0;
  win.listeners.pageshow({ persisted: true });
  assert.equal(win.navigations.at(-1)[0], 'replace');
  assert.match(win.navigations.at(-1)[1], /home-tab/);
  assert.ok(win.navigations.some((row) => row[0] === 'replaceState' && /home-tab/.test(row[1])));
});

test('push advances gobIdx and replace keeps it', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1' });
  assert.equal(win.history.state.gobIdx, 0);
  win.GOBNav.go('/set-lineup.html?franchise_id=f1&game_id=g1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.listeners.pageshow({ persisted: false });
  assert.equal(win.history.state.gobIdx, 1);
  win.GOBNav.replace('/court.html?franchise_id=f1&game_id=g1');
  win.location.pathname = '/court.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.listeners.pageshow({ persisted: false });
  assert.equal(win.history.state.gobIdx, 1);
});

test('exitFlow jumps to the recorded locker-room index after a quarter break, a timeout, and a peek', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=game-plan-tab' });
  win.GOBNav.go('/set-lineup.html?franchise_id=f1&game_id=g1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.listeners.pageshow({ persisted: false });

  win.GOBNav.replace('/court.html?franchise_id=f1&game_id=g1&court_start=play');
  win.location.pathname = '/court.html';
  win.location.search = '?franchise_id=f1&game_id=g1&court_start=play';
  win.listeners.pageshow({ persisted: false });

  win.history.replaceState(win.history.state, '', '/court.html?franchise_id=f1&game_id=g1');
  assert.equal(win.history.state.gobIdx, 1);

  win.GOBNav.replace('/set-lineup.html?franchise_id=f1&game_id=g1&quarter_break_from=1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1&quarter_break_from=1';
  win.listeners.pageshow({ persisted: false });

  win.GOBNav.replace('/set-lineup.html?franchise_id=f1&game_id=g1&timeout=1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1&timeout=1';
  win.listeners.pageshow({ persisted: false });

  win.GOBNav.go('/player-detail.html?player_id=p1');
  win.location.pathname = '/player-detail.html';
  win.location.search = '?player_id=p1';
  win.listeners.pageshow({ persisted: false });
  assert.equal(win.history.state.gobIdx, 2);

  win.navigations.length = 0;
  win.GOBNav.back('/set-lineup.html?franchise_id=f1&game_id=g1&timeout=1');
  assert.deepEqual(win.navigations.at(-1), ['back']);
  win.history.state = { gobIdx: 1 };
  win.listeners.popstate({ state: { gobIdx: 1 } });

  win.fetch = () => { throw new Error('exitFlow must not fetch'); };
  win.GOBNav.exitFlow('/franchise-command-center.html?franchise_id=f1', { tab: 'home-tab' });
  assert.deepEqual(win.navigations.at(-1), ['go', -1]);
  const landing = JSON.parse(win.sessionStorage.getItem('gob_nav_exit'));
  assert.equal(landing.tab, 'home-tab');
  assert.equal(landing.fresh, true);
  assert.equal(win.navigations.some((row) => row[0] === 'replace'), false);
});

test('a lineup peek return does not reload while a game flow is open', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1' });
  win.GOBNav.go('/set-lineup.html?franchise_id=f1&game_id=g1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.listeners.pageshow({ persisted: false });
  win.GOBNav.go('/player-detail.html?player_id=p1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.history.state = { gobIdx: 1 };
  win.fetch = () => { throw new Error('peek return must not fetch'); };
  win.navigations.length = 0;
  win.listeners.pageshow({ persisted: true });
  assert.equal(win.navigations.some((row) => row[0] === 'reload' || row[0] === 'replace'), false);
});

test('returning to the flow start replaces the page and does not call phase-b', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=training-tab' });
  win.GOBNav.go('/training.html?franchise_id=f1');
  win.location.pathname = '/franchise-command-center.html';
  win.location.search = '?franchise_id=f1&tab=training-tab';
  win.history.state = { gobIdx: 0 };
  win.fetch = () => { throw new Error('phase-b must not be fetched from pageshow'); };
  win.navigations.length = 0;
  win.listeners.pageshow({ persisted: true });
  assert.equal(win.navigations.at(-1)[0], 'replace');
  assert.equal(win.sessionStorage.getItem('gob_nav_flow_start'), null);
});

test('pagehide covers the flow start and leaves a peek snapshot alone', () => {
  const flow = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=training-tab' });
  let flowShown = 0;
  flow.PageLoadOverlay = { show() { flowShown += 1; } };
  flow.GOBNav.go('/training.html?franchise_id=f1');
  flow.listeners.pagehide();
  assert.equal(flowShown, 1);

  const peek = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=standings-tab' });
  let peekShown = 0;
  peek.PageLoadOverlay = { show() { peekShown += 1; } };
  peek.GOBNav.go('/team-roster-view.html?team_id=t1');
  peek.listeners.pagehide();
  assert.equal(peekShown, 0);

  const lineup = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1' });
  lineup.GOBNav.go('/set-lineup.html?franchise_id=f1&game_id=g1');
  lineup.location.pathname = '/set-lineup.html';
  lineup.location.search = '?franchise_id=f1&game_id=g1';
  lineup.listeners.pageshow({ persisted: false });
  let lineupShown = 0;
  lineup.PageLoadOverlay = { show() { lineupShown += 1; } };
  lineup.GOBNav.go('/player-detail.html?player_id=p1');
  lineup.listeners.pagehide();
  assert.equal(lineupShown, 0);
});

test('isHubUrl matches the locker room pathname and ignores the query string', () => {
  const win = fakeWindow({ pathname: '/training.html', search: '?franchise_id=f1' });
  const report = '/training-report.html?return_url=' + encodeURIComponent('/franchise-command-center.html?franchise_id=f1&tab=training-tab');
  assert.equal(win.GOBNav.isHubUrl(report), false);
  assert.equal(win.GOBNav.isHubUrl('/franchise-command-center.html?franchise_id=f1'), true);
  assert.equal(win.GOBNav.isHubUrl('http://localhost:8000/franchise-command-center.html?return_url=/franchise-command-center.html'), true);
});

function clickAnchor(win, href, options) {
  options = options || {};
  const link = {
    getAttribute(name) {
      if (name === 'href') return href;
      if (name === 'data-gob-up') return options['data-gob-up'] || null;
      return null;
    },
    hasAttribute(name) { return Object.prototype.hasOwnProperty.call(options, name); },
    setAttribute() {},
    target: '',
  };
  const event = {
    defaultPrevented: !!options.defaultPrevented,
    target: { closest(sel) { return sel === 'a[href]' ? link : null; } },
    metaKey: false,
    ctrlKey: false,
    shiftKey: false,
    altKey: false,
    button: 0,
    preventDefault() { event.defaultPrevented = true; },
  };
  win.listeners.click(event);
  return event;
}

test('a prevented anchor click does not advance the index', () => {
  const win = fakeWindow({ pathname: '/court.html', search: '?franchise_id=f1&game_id=g1' });
  const before = win.history.state.gobIdx;
  clickAnchor(win, '/franchise-command-center.html?franchise_id=f1', { defaultPrevented: true });
  assert.equal(win.history.state.gobIdx, before);
  assert.equal(win.sessionStorage.getItem('gob_nav_pending_idx'), null);
  assert.equal(win.sessionStorage.getItem('gob_nav_idx'), String(before));
});

test('a same-origin anchor click records the next index once', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1' });
  clickAnchor(win, '/team-roster-view.html?team_id=t1');
  assert.equal(win.sessionStorage.getItem('gob_nav_pending_idx'), '1');
  assert.equal(win.history.state.gobIdx, 0);
});

test('exitFlow uses the stamped entry index when sessionStorage is ahead', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=game-plan-tab' });
  win.GOBNav.go('/set-lineup.html?franchise_id=f1&game_id=g1');
  win.location.pathname = '/set-lineup.html';
  win.location.search = '?franchise_id=f1&game_id=g1';
  win.listeners.pageshow({ persisted: false });
  win.sessionStorage.setItem('gob_nav_idx', '9');
  assert.equal(win.history.state.gobIdx, 1);
  win.navigations.length = 0;
  win.GOBNav.exitFlow('/franchise-command-center.html?franchise_id=f1', { tab: 'home-tab' });
  assert.deepEqual(win.navigations.at(-1), ['go', -1]);
  const landing = JSON.parse(win.sessionStorage.getItem('gob_nav_exit'));
  assert.equal(landing.tab, 'home-tab');
  assert.match(landing.url, /franchise-command-center\.html/);
  assert.match(landing.url, /tab=home-tab/);
});

test('a missed exit replaces mode-select with the locker room', () => {
  const hub = '/franchise-command-center.html?franchise_id=f1&tab=home-tab';
  const win = fakeWindow(
    { pathname: '/mode-select.html', search: '' },
    { gob_nav_exit: JSON.stringify({ url: hub, tab: 'home-tab', fresh: true }) }
  );
  const replaced = win.navigations.find((row) => row[0] === 'replace');
  assert.ok(replaced);
  assert.equal(replaced[1], hub);
});

test('pushSection stamps gobIdx on the new entry and does not arm a pending idx', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1&tab=home-tab' });
  assert.equal(win.history.state.gobIdx, 0);
  win.GOBNav.pushSection('/franchise-command-center.html?franchise_id=f1&tab=roster-tab');
  assert.equal(win.history.state.gobIdx, 1);
  assert.equal(win.location.search, '?franchise_id=f1&tab=roster-tab');
  assert.equal(win.sessionStorage.getItem('gob_nav_pending_idx'), null);
  win.GOBNav.pushSection('/franchise-command-center.html?franchise_id=f1&tab=standings-tab');
  assert.equal(win.history.state.gobIdx, 2);
  assert.equal(win.sessionStorage.getItem('gob_nav_pending_idx'), null);
});

test('a short jump still replaces an in-game page with the locker room', () => {
  const hub = '/franchise-command-center.html?franchise_id=f1&tab=training-tab';
  const win = fakeWindow({ pathname: '/court.html', search: '?franchise_id=f1&game_id=g1' });
  win.sessionStorage.setItem('gob_nav_exit', JSON.stringify({ url: hub, tab: 'training-tab', fresh: true }));
  win.navigations.length = 0;
  win.listeners.pageshow({ persisted: true });
  assert.equal(win.navigations[0][0], 'replace');
  assert.equal(win.navigations[0][1], hub);
});
