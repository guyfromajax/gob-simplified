const test = require('node:test');
const assert = require('node:assert/strict');
const { install } = require('../FrontEnd/static/js/shared/gobNav.js');

function fakeWindow(start) {
  const store = new Map();
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
      replaceState(_s, _t, url) { win.navigations.push(['replaceState', url]); },
    },
    sessionStorage: {
      getItem(k) { return store.has(k) ? store.get(k) : null; },
      setItem(k, v) { store.set(k, v); },
    },
    document: {
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

test('fcc bfcache restore reloads and does not call phase-b', () => {
  const win = fakeWindow({ pathname: '/franchise-command-center.html', search: '?franchise_id=f1' });
  win.fetch = () => { throw new Error('phase-b must not be fetched from pageshow'); };
  win.listeners.pageshow({ persisted: true });
  assert.deepEqual(win.navigations.at(-1), ['reload']);
});
