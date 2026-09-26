const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'aabbccddeeff001122334455';
const TID = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const OFFICE = '/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID;

function freshState() {
  return {
    rev: 0,
    season: 1,
    week: 3,
    build: 'storebuild',
    headline: 'Week three headline',
    tempo: 0,
    playName: 'Baseline',
    focus: 'standard',
    players: ['Ada Keeper', 'Bea Cutter'],
    wireEvents: [],
  };
}

function etagFor(state, pathname, search) {
  const sig = pathname + (search || '');
  return 'W/"' + FID + ':' + state.season + ':' + state.week + ':' + state.rev + ':' + state.build + ':' + sig + '"';
}

function player(name, focus) {
  const parts = name.split(' ');
  return {
    _id: name.replace(/\s/g, '-').toLowerCase(),
    first_name: parts[0],
    last_name: parts[1],
    year: 'junior',
    height: 76,
    weight: 200,
    jersey: 4,
    attributes: { SC: 5, SH: 5, ID: 5, OD: 5, PS: 5, BH: 5, RB: 5, AG: 5, ST: 5, ND: 5, IQ: 5, FT: 5 },
    position_ratings: { PG: 70 },
    stats: { season: { PTS: 20, GP: 2, REB: 4 } },
    training_focus: focus,
    resolved_training_focus: focus,
    training_position: 'PG',
    resolved_training_position: 'PG',
  };
}

function commandCenter(state) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    user_team_object_id: TID,
    team: 'Lancaster',
    week: state.week,
    rank: 18,
    current_season: state.season,
    training_completed: false,
    session_type: 'in-season',
    cut_required: false,
    primary_color: '#27408E',
    user_conference: 1,
    user_region: 'A',
    recruiting_wire: { counts: {}, board_saved_week: 0, has_saved_board: false },
    rankings: [],
    news_headlines: [],
    office_digest: {
      state: 'regular',
      todos: [
        { id: 'run_training', label_key: 'run_training', required: true, done: false, gates_advance: false, is_advance_action: false, route: '/training.html' },
        { id: 'play_next_game', label_key: 'play_next_game', required: true, done: false, gates_advance: false, is_advance_action: true, route: '/set-lineup.html' },
      ],
      result: {
        week: 2,
        home_team_id: TID,
        away_team_id: 'cccccccccccccccccccccccc',
        home_team_name: 'Lancaster',
        away_team_name: 'Morristown',
        home_score: 70,
        away_score: 60,
        user_is_home: true,
        site: 'home',
        user_won: true,
        opponent_team_id: 'cccccccccccccccccccccccc',
        opponent_team_name: 'Morristown',
        headline: state.headline,
        leader: null,
      },
      what_moved: {
        national_rank: { now: 18, prev: 18, delta: 0 },
        conference_standing: { now: 4, prev: 4, delta: 0 },
        record: { wins: 1, losses: 1 },
        streak: null,
        attribute_changes: [],
      },
      next_game: {
        week: state.week,
        opponent: 'Morristown',
        opponent_team_id: 'cccccccccccccccccccccccc',
        site: 'home',
        record: { wins: 8, losses: 4 },
        conference: 1,
      },
      team_snapshot: {
        record: { wins: 1, losses: 1 },
        chemistry: 12,
        attitude: { buckets: [] },
      },
      recruiting_wire: { status: '', events: state.wireEvents, pending_count: 0, urgent: false },
      signing_day: null,
      season_preview: null,
    },
  };
}

function bodyFor(state, pathname, search) {
  const params = new URLSearchParams(search || '');
  if (pathname.indexOf('/franchise/command-center/data') !== -1) return commandCenter(state);
  if (pathname.indexOf('/franchise/team-data') !== -1) {
    return { team_attributes: { team_chemistry: 12, shot_threshold: 1, rebound_modifier: 1 }, plays_data: {}, scouting_data: {} };
  }
  if (pathname.indexOf('/franchise/standings') !== -1) {
    return { standings: [{ team_id: TID, name: 'Lancaster', W: 1, L: 1, differential: 4, conference: 1, region: params.get('region') || 'A' }] };
  }
  if (pathname.indexOf('/franchise/leaders') !== -1) {
    return { PTS: [{ name: 'Ada Keeper', team: 'Lancaster', value: 10 }] };
  }
  if (pathname.indexOf('/franchise/team-stats') !== -1) {
    return { teams: [{ team_id: TID, team: 'Lancaster', natl_rank: 18, stats: { W: 1, L: 1 } }] };
  }
  if (pathname.indexOf('/franchise/news') !== -1) {
    return { news: [{ headline: 'Lancaster holds on', week: state.week, story_id: 's1', body: 'A short story.' }] };
  }
  if (pathname.indexOf('/franchise/recruiting-data') !== -1) {
    return {
      week: state.week,
      team_id: TID,
      team: 'Lancaster',
      recruits: [],
      saved_orders: {},
      watchlist: [],
      recruiting_wire: { status: state.headline, events: state.wireEvents },
    };
  }
  if (pathname.indexOf('/franchise/schedule') !== -1) {
    return { schedule: [], team_name_map: {}, team_display_name_map: {} };
  }
  if (pathname.indexOf('/api/playbooks') !== -1) {
    return {
      playbook_meta: { saved_for_week: state.week },
      motion: [{ play_id: 'm1', name: state.playName, effectiveness: 1 }],
      simple_playbook_percentages: { motion: { m1: 100 } },
      set_plays: [],
      man_defense: [],
      zone_defense: [],
      fast_breaks: [],
      hc_traps: [],
    };
  }
  if (pathname.indexOf('/api/gameplan') !== -1) {
    return { strategy_settings: { tempo: state.tempo, offense: 2, defense: 2 } };
  }
  if (pathname.indexOf('/roster/') !== -1) {
    return {
      team: 'Lancaster',
      team_name: 'Lancaster',
      is_user_team: true,
      players: state.players.map(function (name) { return player(name, state.focus); }),
      training_squad: [],
      practice_squad_recruits: [],
    };
  }
  if (pathname === '/teams') return [{ name: 'Lancaster', display_name: 'Lancaster', primary_color: '#27408E', _id: TID }];
  if (pathname === '/api/auth/me') return { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' };
  if (pathname === '/app-config') return { isAlpha: false, alphaDisclaimer: null, version: '1.0' };
  return {};
}

function isWrite(method, pathname) {
  const m = method.toUpperCase();
  if (m !== 'POST' && m !== 'PUT' && m !== 'PATCH' && m !== 'DELETE') return false;
  return pathname.indexOf('/franchise/') !== -1 || pathname.indexOf('/api/gameplan') !== -1 || pathname.indexOf('/api/playbooks') !== -1;
}

async function installStoreServer(page, state) {
  const requests = [];
  page.on('request', function (request) {
    requests.push(request);
  });
  await page.route('**/*', async function (route) {
    const request = route.request();
    let url;
    try { url = new URL(request.url()); } catch (err) {
      await route.continue();
      return;
    }
    const pathname = url.pathname;
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/')
      || pathname.startsWith('/recruit/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (isWrite(request.method(), pathname)) {
      state.rev += 1;
      const raw = request.postData() || '';
      if (pathname.indexOf('/run-training/user') !== -1) state.headline = 'Training filed';
      if (pathname.indexOf('/recruiting-orders') !== -1) {
        state.wireEvents = [{ recruit: 'Miles Hart', event_text: 'Invites saved', direction: 'up' }];
      }
      if (pathname.indexOf('/recruiting-watchlist') !== -1) {
        state.wireEvents = [{ recruit: 'Ada Keeper', event_text: 'Added to the watchlist', direction: 'up' }];
      }
      if (pathname.indexOf('/api/gameplan') !== -1) state.tempo = 4;
      if (pathname.indexOf('/api/playbooks') !== -1) state.playName = 'Horns';
      if (pathname.indexOf('/development-focus') !== -1) state.focus = 'rebounding';
      if (pathname.indexOf('/cut-players') !== -1) state.players = ['Ada Keeper'];
      if (pathname.indexOf('/complete-week') !== -1) {
        state.week += 1;
        state.headline = 'Week advanced';
      }
      if (pathname.indexOf('-seen') !== -1 || pathname.indexOf('modal-seen') !== -1) {
        state.wireEvents = [{ recruit: 'Sam Quinn', event_text: 'Flag dismissed', direction: 'flat' }];
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: raw && raw.charAt(0) === '{' ? raw : '{"ok":true}',
      });
      return;
    }
    const payload = bodyFor(state, pathname, url.search);
    const text = JSON.stringify(payload);
    const tag = etagFor(state, pathname, url.search);
    const inm = request.headers()['if-none-match'];
    if (inm && inm === tag) {
      await route.fulfill({ status: 304, headers: { ETag: tag }, body: '' });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: { ETag: tag },
      body: text,
    });
  });
  return requests;
}

function isBrowseUrl(url) {
  let pathname = '';
  try { pathname = new URL(url).pathname; } catch (err) { return false; }
  return pathname.startsWith('/franchise/')
    || pathname.startsWith('/roster/')
    || pathname.startsWith('/api/playbooks')
    || pathname.startsWith('/api/gameplan')
    || pathname === '/teams';
}

function browseGets(requests) {
  return requests.filter(function (request) {
    return request.method() === 'GET' && isBrowseUrl(request.url());
  });
}

async function openTab(page, section, tab) {
  await page.locator('.rail [data-gob-section="' + section + '"]').click();
  await page.locator('#gob-subtabs [data-tab="' + tab + '"]').click();
}

async function openOffice(page) {
  const started = Date.now();
  await page.goto(OFFICE);
  await page.waitForFunction(function () {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
  return Date.now() - started;
}

async function boot(page, state) {
  await stubAuth(page);
  const requests = await installStoreServer(page, state);
  const ms = await openOffice(page);
  return { requests: requests, ms: ms };
}

test('office first load skips state, duplicates, and the 300 KB budget', async ({ page }) => {
  const state = freshState();
  const started = [];
  page.on('response', function (response) {
    started.push(response);
  });
  const bootInfo = await boot(page, state);
  const gets = browseGets(bootInfo.requests);
  const keys = gets.map(function (request) {
    const url = new URL(request.url());
    return url.pathname + url.search;
  });
  const dupes = keys.filter(function (key, index) { return keys.indexOf(key) !== index; });
  expect(keys.some(function (key) { return key.indexOf('/franchise/state') !== -1; })).toBe(false);
  expect(keys.some(function (key) { return key.indexOf('profile=1') !== -1; })).toBe(false);
  expect(dupes).toEqual([]);
  let bytes = 0;
  for (const response of started) {
    const url = response.url();
    if (!isBrowseUrl(url) && new URL(url).pathname !== '/api/auth/me') continue;
    const buf = await response.body().catch(function () { return Buffer.alloc(0); });
    bytes += buf.length;
  }
  expect(bytes).toBeLessThan(300 * 1024);
  console.log('STORE_OFFICE ' + JSON.stringify({ bytes: bytes, requests: keys.length, ms: bootInfo.ms, urls: keys }));
  await expect(page.locator('#office-root .res-hl')).toHaveText('Week three headline');
});

test('session walk revalidates with 304 on the second visit', async ({ page }) => {
  const state = freshState();
  const responses = [];
  page.on('response', function (response) { responses.push(response); });
  await boot(page, state);
  const officeBytes = responses.length;
  async function visit(path, marker) {
    const target = path + '?franchise_id=' + FID + '&team_id=' + TID;
    const seen = page.waitForResponse(function (response) {
      return response.url().indexOf(marker) !== -1;
    }, { timeout: 20000 }).catch(function () { return null; });
    await page.goto(target, { waitUntil: 'domcontentloaded' });
    await seen;
  }
  await openTab(page, 'team', 'roster-tab');
  await openTab(page, 'team', 'player-stats-tab');
  await openTab(page, 'team', 'team-stats-tab');
  await openTab(page, 'team', 'schedule-tab');
  await visit('/standings.html', '/franchise/standings');
  await visit('/leaders.html', '/franchise/leaders');
  await visit('/team-stats.html', '/franchise/team-stats');
  await visit('/recruiting.html', '/franchise/recruiting-data');
  await visit('/news.html', '/franchise/news');
  const beforeReturn = responses.length;
  await page.goto(OFFICE);
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  const returnResponses = responses.slice(beforeReturn);
  const cc = returnResponses.filter(function (response) {
    return response.url().indexOf('/franchise/command-center/data') !== -1;
  });
  expect(cc.length).toBeGreaterThan(0);
  expect(cc.every(function (response) { return response.status() === 304; })).toBe(true);
  expect(cc.every(function (response) {
    return response.request().headers()['if-none-match'];
  })).toBe(true);

  const standingsStart = responses.length;
  const secondStandings = page.waitForResponse(function (response) {
    return response.url().indexOf('/franchise/standings') !== -1;
  });
  await page.goto('/standings.html?franchise_id=' + FID + '&team_id=' + TID, { waitUntil: 'domcontentloaded' });
  await secondStandings;
  const standings = responses.slice(standingsStart).filter(function (response) {
    return response.url().indexOf('/franchise/standings') !== -1;
  });
  expect(standings.length).toBeGreaterThan(0);
  expect(standings.every(function (response) { return response.status() === 304; })).toBe(true);

  let bytes = 0;
  let browseResponses = 0;
  for (const response of responses) {
    if (!isBrowseUrl(response.url())) continue;
    browseResponses += 1;
    const buf = await response.body().catch(function () { return Buffer.alloc(0); });
    bytes += buf.length;
  }
  console.log('STORE_WALK ' + JSON.stringify({ bytes: bytes, browseResponses: browseResponses, responses: responses.length, officeMarks: officeBytes }));
});

async function writeThenOffice(page, url, method, assertText) {
  const state = freshState();
  await boot(page, state);
  await expect(page.locator('#office-root .res-hl')).toHaveText('Week three headline');
  const status = await page.evaluate(async function (args) {
    const res = await fetch(args.url, {
      method: args.method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: args.fid, team_id: args.tid }),
    });
    return res.status;
  }, { url: url, method: method, fid: FID, tid: TID });
  expect(status).toBe(200);
  await page.reload();
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  await expect(page.locator(assertText.selector)).toContainText(assertText.text);
}

test('training submit shows the new office', async ({ page }) => {
  await writeThenOffice(page, '/franchise/run-training/user', 'POST', {
    selector: '#office-root .res-hl',
    text: 'Training filed',
  });
});

test('recruit invites show the new wire', async ({ page }) => {
  await writeThenOffice(page, '/franchise/recruiting-orders', 'POST', {
    selector: '#office-root .office-wire',
    text: 'Invites saved',
  });
});

test('watchlist toggle shows the new wire', async ({ page }) => {
  await writeThenOffice(page, '/franchise/recruiting-watchlist', 'PATCH', {
    selector: '#office-root .office-wire',
    text: 'Ada Keeper',
  });
});

test('game plan save shows the new tempo', async ({ page }) => {
  const state = freshState();
  await boot(page, state);
  await openTab(page, 'prep', 'game-plan-tab');
  await expect(page.locator('.fcc-game-plan-item', { hasText: 'Offense Tempo' })).toContainText('Slow');
  await page.evaluate(async function (fid) {
    await fetch('/api/gameplan?mode=franchise&franchise_id=' + fid, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid, strategy_settings: { tempo: 4 } }),
    });
  }, FID);
  await page.reload();
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  await openTab(page, 'prep', 'game-plan-tab');
  await expect(page.locator('.fcc-game-plan-item', { hasText: 'Offense Tempo' })).toContainText('Fast');
});

test('playbooks save shows the new play', async ({ page }) => {
  const state = freshState();
  await boot(page, state);
  await openTab(page, 'prep', 'playbooks-tab');
  await expect(page.locator('#fcc-playbooks-sections')).toContainText('Baseline');
  await page.evaluate(async function (fid) {
    await fetch('/api/playbooks?mode=franchise&franchise_id=' + fid, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid }),
    });
  }, FID);
  await page.reload();
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  await openTab(page, 'prep', 'playbooks-tab');
  await expect(page.locator('#fcc-playbooks-sections')).toContainText('Horns');
});

test('development focus shows the new focus', async ({ page }) => {
  const state = freshState();
  await boot(page, state);
  await openTab(page, 'team', 'roster-tab');
  await expect(page.locator('#team-body')).toContainText('Standard');
  await page.evaluate(async function (fid) {
    await fetch('/franchise/player/development-focus', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid, training_focus: 'rebounding' }),
    });
  }, FID);
  await page.reload();
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  await openTab(page, 'team', 'roster-tab');
  await expect(page.locator('#team-body')).toContainText('Rebounding');
});

test('cut players shows the shorter roster', async ({ page }) => {
  const state = freshState();
  await boot(page, state);
  await openTab(page, 'team', 'roster-tab');
  await expect(page.locator('#team-body')).toContainText('Bea Cutter');
  await page.evaluate(async function (fid) {
    await fetch('/franchise/cut-players', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid }),
    });
  }, FID);
  await page.reload();
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  await openTab(page, 'team', 'roster-tab');
  await expect(page.locator('#team-body')).toContainText('Ada Keeper');
  await expect(page.locator('#team-body')).not.toContainText('Bea Cutter');
});

test('week advance shows the new week', async ({ page }) => {
  const state = freshState();
  await boot(page, state);
  await expect(page.locator('#office-root .week-k')).toHaveText('Week 3');
  await page.evaluate(async function (fid) {
    await fetch('/franchise/complete-week', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid }),
    });
  }, FID);
  await page.reload();
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  await expect(page.locator('#office-root .week-k')).toHaveText('Week 4');
  await expect(page.locator('#office-root .res-hl')).toHaveText('Week advanced');
});

test('seen-flag dismiss shows the new wire', async ({ page }) => {
  await writeThenOffice(page, '/franchise/recruiting-wire-seen', 'PATCH', {
    selector: '#office-root .office-wire',
    text: 'Flag dismissed',
  });
});

test('a different BUILD drops the persisted cache', async ({ page }) => {
  const state = freshState();
  await boot(page, state);
  await page.evaluate(function (fid) {
    const key = 'gob-store:' + fid;
    const blob = JSON.parse(sessionStorage.getItem(key));
    blob.generation.build = 'oldbuild';
    const staleKey = '/franchise/news?franchise_id=' + fid;
    blob.entries[staleKey] = {
      etag: 'W/"' + fid + ':1:3:0:oldbuild:' + staleKey + '"',
      body: { news: [{ headline: 'STALE NEWS', story_id: 'old' }] },
    };
    Object.keys(blob.entries).forEach(function (entryKey) {
      const entry = blob.entries[entryKey];
      if (entry && entry.etag) entry.etag = String(entry.etag).replace(':storebuild:', ':oldbuild:');
    });
    sessionStorage.setItem(key, JSON.stringify(blob));
  }, FID);
  state.build = 'newbuild';
  await page.reload();
  await page.waitForFunction(function () {
    const root = document.getElementById('office-root');
    return root && root.getAttribute('aria-busy') === 'false';
  });
  const gone = await page.evaluate(function (fid) {
    const blob = JSON.parse(sessionStorage.getItem('gob-store:' + fid) || '{}');
    const keys = Object.keys(blob.entries || {});
    return {
      keys: keys,
      stale: keys.some(function (key) { return key.indexOf('/franchise/news') !== -1 && blob.entries[key].body && blob.entries[key].body.news && blob.entries[key].body.news[0].headline === 'STALE NEWS'; }),
    };
  }, FID);
  expect(gone.stale).toBe(false);
  expect(gone.keys.some(function (key) { return key.indexOf('STALE') !== -1; })).toBe(false);
});

test('sessionStorage throwing still paints the office', async ({ page }) => {
  await stubAuth(page);
  await page.addInitScript(function () {
    const deny = function () { throw new Error('sessionStorage denied'); };
    const store = window.sessionStorage;
    store.getItem = deny;
    store.setItem = deny;
    store.removeItem = deny;
  });
  const state = freshState();
  const requests = await installStoreServer(page, state);
  await openOffice(page);
  expect(requests.length).toBeGreaterThan(0);
  await expect(page.locator('#office-root .res-hl')).toHaveText('Week three headline');
});

test('two callers share one in-flight request', async ({ page }) => {
  const state = freshState();
  await boot(page, state);
  let hits = 0;
  page.on('request', function (request) {
    if (request.url().indexOf('/franchise/news') !== -1) hits += 1;
  });
  await page.evaluate(async function (fid) {
    const url = '/franchise/news?franchise_id=' + fid;
    await Promise.all([window.GOBStore.get(url), window.GOBStore.get(url)]);
  }, FID);
  expect(hits).toBe(1);
});
