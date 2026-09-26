const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-office';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/office-frontend');
const V2 = path.join(__dirname, '../../reports/office-v2');
const V3 = path.join(__dirname, '../../reports/office-v3');
const V3B = path.join(__dirname, '../../reports/office-v3b');
const FRAMES = path.join(__dirname, '../../_documentation_master/projects/design_handoff_office_shell/frames');

const FRAME_SHOTS = [
  ['office-win-1280.html', 1280, 720],
  ['office-win-1920.html', 1920, 1080],
  ['office-loss-1280.html', 1280, 720],
  ['office-first-week-1280.html', 1280, 720],
  ['office-tournament-1280.html', 1280, 720],
  ['office-tournament-1920.html', 1920, 1080],
  ['office-signing-day-1280.html', 1280, 720],
];

function resultBlock(overrides) {
  return Object.assign({
    week: 21,
    home_team_id: TID,
    away_team_id: 'bbbbbbbbbbbbbbbbbbbbbbbb',
    home_team_name: 'Amariabi International',
    away_team_name: 'Long Island Methodist',
    home_score: 71,
    away_score: 64,
    user_is_home: true,
    site: 'home',
    neutral: null,
    opponent_team_id: 'bbbbbbbbbbbbbbbbbbbbbbbb',
    opponent_team_name: 'Long Island Methodist',
    opponent_rank: 9,
    round_name: null,
    user_won: true,
    leader_role: 'potg',
    leader: {
      player_id: 'p-jalen',
      name: 'Jalen Carter',
      stats: { pts: 24, reb: 6, ast: 4, fgm: 9, fga: 16, fg3m: 3, fg3a: 7, min: 2040 },
    },
    headline: 'Carter closes it late',
    box_score: {
      path: '/box-score.html',
      params: { mode: 'franchise', franchise_id: FID, game_id: 'g1', home: 'Lancaster', away: 'Four Corners' },
    },
  }, overrides || {});
}

function nextBlock(overrides) {
  return Object.assign({
    week: 22,
    date: null,
    site: 'away',
    neutral: null,
    opponent_team_id: 'cccccccccccccccccccccccc',
    opponent: 'Crickstown',
    rank: 21,
    record: { wins: 11, losses: 8 },
    conference: 2,
    conference_position: 2,
    conference_size: 8,
    top_scorer: { name: 'Avery Cole', average: 18.4 },
    top_rebounder: { name: 'Noah Peck', average: 9.1 },
    projected_starting_five: null,
    round_name: null,
    seeds: null,
    stakes: null,
    team_rt: null,
  }, overrides || {});
}

function wireBlock(overrides) {
  return Object.assign({
    status: 'Two leans moved',
    events: [
      {
        recruit_id: 'r1',
        recruit: 'Miles Hart',
        position: 'SG',
        stars: null,
        filmed_grade: null,
        event_type: 'gained',
        event_text: 'Miles Hart moved you to #2',
        list_position: 2,
        direction: 'up',
      },
      {
        recruit_id: 'r2',
        recruit: 'Owen Blake',
        position: 'PF',
        stars: null,
        filmed_grade: null,
        event_type: 'lost',
        event_text: 'Owen Blake dropped you to #4',
        list_position: 4,
        direction: 'down',
      },
    ],
    pending_count: 1,
    urgent: true,
    unseen_count: 3,
  }, overrides || {});
}

function snapshotBlock(overrides) {
  return Object.assign({
    state: 'ready',
    chemistry: { value: 18, max: 25 },
    attitude: {
      player_count: 12,
      buckets: [
        { id: 'em_0_19', min: 0, max: 19, count: 1 },
        { id: 'em_20_39', min: 20, max: 39, count: 2 },
        { id: 'em_40_59', min: 40, max: 59, count: 4 },
        { id: 'em_60_79', min: 60, max: 79, count: 3 },
        { id: 'em_80_plus', min: 80, max: null, count: 2 },
      ],
    },
    moved_most: [
      { measure: 'fight', value: 1.4, delta: 0.3 },
      { measure: 'discipline', value: 0.9, delta: -0.2 },
    ],
  }, overrides || {});
}

function standingsBlock() {
  const names = ['Alpha', 'Crickstown', 'Gamma', 'Amariabi International', 'Delta', 'Echo', 'Foxtrot', 'Golf'];
  return {
    conference: 2,
    region: 'A',
    rows: names.map(function (name, index) {
      return {
        team_id: index === 3 ? TID : ('team-' + index),
        team_name: name,
        wins: 14 - index,
        losses: index,
        differential: 24 - index * 4,
        position: index + 1,
        is_user: index === 3,
      };
    }),
  };
}

function digest(state, patch) {
  const body = {
    state: state,
    what_moved: {
      national_rank: { now: 18, prev: 22, delta: 4 },
      conference_standing: { now: 3, prev: 5, delta: 2 },
      record: { wins: 16, losses: 5 },
      streak: 'W4',
      attribute_changes: [
        { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'SH', from: 6, to: 7 },
        { player_id: 'p-jalen', name: 'Jalen Carter', attribute: 'ND', from: 7, to: 6 },
        { player_id: 'p-marcus', name: 'Marcus Ruiz', attribute: 'BH', from: 4, to: 5 },
      ],
    },
    team_snapshot: snapshotBlock(),
    result: resultBlock(),
    next_game: nextBlock(),
    conference_standings: standingsBlock(),
    todos: [
      { id: 'run_training', label_key: 'run_training', required: true, done: true, gates_advance: false, is_advance_action: false, route: '/training.html' },
      { id: 'review_recruit_invites', label_key: 'review_recruit_invites', required: true, done: false, gates_advance: true, is_advance_action: false, route: '/recruiting.html' },
      { id: 'play_next_game', label_key: 'play_next_game', required: true, done: false, gates_advance: false, is_advance_action: true, route: '/set-lineup.html' },
      { id: 'resume_training', label_key: 'resume_training', required: true, done: false, gates_advance: false, is_advance_action: false, route: '/training.html' },
      { id: 'run_training_camp', label_key: 'run_training_camp', required: true, done: false, gates_advance: false, is_advance_action: false, route: '/training.html' },
    ],
    recruiting_wire: wireBlock(),
    signing_day: null,
    season_preview: null,
  };
  return Object.assign(body, patch || {});
}

function commandCenter(office, flags) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 22,
    rank: 18,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 22, counts: {} },
    user_conference: 1,
    user_region: 'A',
    office_digest: office,
  }, flags || {});
}

const STATES = {
  win: commandCenter(digest('win')),
  loss: commandCenter(digest('loss', {
    result: resultBlock({
      user_won: false,
      home_score: 58,
      away_score: 71,
      leader_role: 'team_leader',
      leader: { player_id: 'p-jalen', name: 'Jalen Carter', stats: { pts: 19, reb: 4, ast: 3 } },
      headline: null,
    }),
    what_moved: {
      national_rank: { now: 24, prev: 18, delta: -6 },
      conference_standing: { now: 6, prev: 3, delta: -3 },
      record: { wins: 15, losses: 6 },
      streak: 'L1',
      attribute_changes: [],
    },
  })),
  regular: commandCenter(digest('regular', {
    result: resultBlock({ user_won: null, home_score: 70, away_score: 70, headline: null, leader_role: null, leader: null }),
    what_moved: {
      national_rank: { now: 20, prev: 20, delta: 0 },
      conference_standing: { now: 4, prev: 4, delta: 0 },
      record: { wins: 8, losses: 8 },
      streak: null,
      attribute_changes: [],
    },
  })),
  first_week: commandCenter(digest('first_week', {
    result: null,
    what_moved: {
      national_rank: { now: 40, prev: null, delta: null },
      conference_standing: { now: null, prev: null, delta: null },
      record: { wins: 0, losses: 0 },
      streak: null,
      attribute_changes: [],
    },
    team_snapshot: snapshotBlock({ state: 'set_after_camp', moved_most: [] }),
    season_preview: {
      preseason_rank: 40,
      conference_projection: null,
      team_rt: null,
      national_rank: 40,
      returning_starters: null,
      top_returner: null,
      newcomers: null,
      opener: nextBlock({ week: 1 }),
    },
    next_game: nextBlock({ week: 1, site: 'home' }),
    recruiting_wire: wireBlock({ status: 'Opens with the invite period', events: [], pending_count: 0, urgent: false }),
    todos: [
      { id: 'run_training_camp', label_key: 'run_training_camp', required: true, done: false, gates_advance: true, is_advance_action: true, route: '/training.html' },
    ],
  }), { week: 1, training_completed: false, session_type: 'preseason' }),
  tournament: commandCenter(digest('tournament', {
    result: resultBlock({ week: 30, round_name: 'Region Tourney First Round', headline: null }),
    next_game: nextBlock({
      week: 31,
      site: 'home',
      round_name: 'Region Tourney Championship',
      seeds: null,
      stakes: null,
      team_rt: null,
      date: null,
      neutral: null,
      projected_starting_five: null,
    }),
  }), { week: 31, eos_tournament_active: true, training_completed: true, training_disabled_for_postseason: true }),
  signing_day: commandCenter(digest('signing_day', {
    result: resultBlock({ week: 34, round_name: 'National Championship', user_won: true, headline: null }),
    next_game: null,
    recruiting_wire: wireBlock({ status: 'Signing Day', pending_count: 1, urgent: true }),
    signing_day: {
      points_remaining: 12,
      points_total: 50,
      promises_made: 1,
      open_roster_spots: 3,
      targets: [
        { recruit_id: 'r1', name: 'Miles Hart', position: 'SG', stars: null, rt: 'A', lean_rank: 1, direction: 'up' },
        { recruit_id: 'r2', name: 'Owen Blake', position: 'PF', stars: null, rt: 'B+', lean_rank: 2, direction: null },
      ],
    },
    todos: [
      { id: 'run_signing_day', label_key: 'run_signing_day', required: true, done: false, gates_advance: true, is_advance_action: true, route: '/recruiting.html' },
    ],
  }), { week: 35 }),
};

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, data) {
  await page.unrouteAll({ behavior: 'ignoreErrors' }).catch(function () {});
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
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
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, data);
      return;
    }
    if (pathname.startsWith('/franchise/play-next-game')) {
      await fulfillJson(route, {
        home: 'Lancaster', away: 'Morristown', week: 22,
        home_id: TID, away_id: 'cccccccccccccccccccccccc',
        home_display: 'Lancaster', away_display: 'Morristown',
      });
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      var table = (data.office_digest && data.office_digest.conference_standings) || standingsBlock();
      await fulfillJson(route, {
        standings: (table.rows || []).map(function (row) {
          return {
            team_id: row.team_id,
            name: row.team_name,
            display_name: row.team_name,
            W: row.wins,
            L: row.losses,
            differential: row.differential,
            conference: table.conference,
            region: table.region,
          };
        }),
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openOffice(page, data) {
  await stubAuth(page);
  await installApi(page, data);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
  await page.waitForFunction(() => {
    const root = document.documentElement;
    return root.classList.contains('gob-1280') || root.classList.contains('gob-1920');
  });
  await page.waitForTimeout(900);
}

const OFFICE_BAD_TEXT = /\[object Object\]|\bNaN\b|\bnull\b|\bundefined\b|N\/A|\{["']?\w+["']?\s*:/;

async function assertOfficeText(page) {
  const text = await page.locator('#office-root').innerText();
  expect(text).not.toMatch(OFFICE_BAD_TEXT);
  return text;
}

async function assertMonograms(page) {
  expect(await page.locator('#office-root .office-res .logo, #office-root .office-next .logo').count()).toBe(0);
}

async function assertLabelsFit(page) {
  const clipped = await page.evaluate(() => {
    return [...document.querySelectorAll('#office-root .rs-n, #office-root .wk-step .td-l')]
      .filter((node) => node.scrollWidth > node.clientWidth + 1)
      .map((node) => node.textContent.trim());
  });
  expect(clipped, 'ellipsis on team names or strip labels').toEqual([]);
}

async function assertChipSize(page) {
  const sizes = await page.evaluate(() => {
    const row = document.querySelector('#office-root .mv-p');
    if (!row) return null;
    const name = row.querySelector('.nm');
    const code = row.querySelector('.attr-code');
    if (!name || !code) return null;
    return {
      name: parseFloat(getComputedStyle(name).fontSize),
      chip: parseFloat(getComputedStyle(code).fontSize),
    };
  });
  if (!sizes) return;
  expect(sizes.chip).toBeGreaterThanOrEqual(sizes.name);
}

async function assertWireFitsContent(page) {
  const over = await page.evaluate(() => {
    const wire = document.querySelector('#office-root .office-wire');
    if (!wire) return 0;
    const style = getComputedStyle(wire);
    const pad = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const gap = parseFloat(style.rowGap || style.gap) || 0;
    const kids = [...wire.children];
    const content = kids.reduce((sum, el) => sum + el.getBoundingClientRect().height, 0);
    const gaps = Math.max(0, kids.length - 1) * gap;
    return wire.getBoundingClientRect().height - (content + pad + gaps);
  });
  expect(over, 'wire taller than its content').toBeLessThanOrEqual(2);
}

async function assertHeadersClear(page) {
  const overlap = await page.evaluate(() => {
    return [...document.querySelectorAll('#office-root .office-col')].map((col) => {
      const head = col.querySelector('.office-h');
      const card = col.querySelector('.card');
      if (!head || !card) return null;
      const gap = card.getBoundingClientRect().top - head.getBoundingClientRect().bottom;
      return Math.round(gap * 10) / 10;
    });
  });
  overlap.forEach((gap, index) => {
    expect(gap, 'column ' + (index + 1) + ' header clearance').not.toBeNull();
    expect(gap, 'column ' + (index + 1) + ' header overlaps its card').toBeGreaterThanOrEqual(0);
  });
}

async function mouseClick(page, selector) {
  const loc = page.locator(selector).first();
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing ' + selector);
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 24));
}

function measure(page) {
  return page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const mainBox = main.getBoundingClientRect();
    const office = document.getElementById('office-root');
    const officeBox = office.getBoundingClientRect();
    const pad = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--page-pad'));
    const gaps = [...document.querySelectorAll('#office-root .office-col')].map((col) => {
      const kids = [...col.children].filter((el) => el.getBoundingClientRect().height > 1);
      const last = kids[kids.length - 1] || col;
      return Math.round(mainBox.bottom - last.getBoundingClientRect().bottom);
    });
    const clip = [...document.querySelectorAll('#office-root .office-col')].map((col) => {
      return Math.max(0, col.scrollHeight - col.clientHeight);
    });
    return {
      mainScroll: main.scrollHeight - main.clientHeight,
      mainWide: main.scrollWidth - main.clientWidth,
      pageWide: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      gaps: gaps,
      clip: clip,
      pad: pad,
      standings: (function () {
        const card = document.querySelector('#office-root .office-st');
        if (!card) return null;
        const cols = [...document.querySelectorAll('#office-root .office-col')];
        return {
          mode: card.dataset.standingsMode || '',
          shown: Number(card.dataset.standingsShown) || 0,
          total: Number(card.dataset.standingsTotal) || 0,
          column: cols.findIndex((col) => col.contains(card)) + 1,
        };
      })(),
      left: Math.round((officeBox.left - mainBox.left) * 10) / 10,
      right: Math.round((mainBox.right - officeBox.right) * 10) / 10,
    };
  });
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
  fs.mkdirSync(V2, { recursive: true });
  fs.mkdirSync(V3, { recursive: true });
  fs.mkdirSync(V3B, { recursive: true });
});

test('six states fit at 1280 and 1920', async ({ page }) => {
  const fit = {};
  for (const name of Object.keys(STATES)) {
    fit[name] = {};
    for (const size of [[1280, 720, '1280'], [1440, 900, '1440'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await openOffice(page, STATES[name]);
      await assertOfficeText(page);
      await assertHeadersClear(page);
      await assertLabelsFit(page);
      await assertMonograms(page);
      await assertChipSize(page);
      await assertWireFitsContent(page);
      expect(await page.locator('#office-root .office-col').count()).toBe(3);
      expect(await page.locator('#office-root .week-strip').count()).toBe(1);
      expect(await page.locator('#gob-main h1')).toHaveText('');
      if (name === 'signing_day') {
        expect(await page.locator('#office-root .office-wire').count()).toBe(0);
        expect(await page.locator('#office-root').getByText('stars', { exact: false }).count()).toBe(0);
      }
      if (name === 'loss') {
        expect(await page.locator('#office-root .office-res.is-loss').count()).toBe(1);
        expect(await page.locator('#office-root .res-hl').count()).toBe(0);
      }
      if (name === 'win') {
        expect(await page.locator('#office-root .res-hl').count()).toBe(1);
        expect(await page.locator('#office-root').getByText('Team RT').count()).toBe(0);
        expect(await page.locator('#office-root .five').count()).toBe(0);
      }
      if (name === 'first_week') {
        expect(await page.locator('#office-root .sp-card').count()).toBe(1);
        expect(await page.locator('#office-root').getByText('Set after camp').count()).toBe(2);
        expect(await page.locator('#office-root .td-gate').count()).toBe(0);
        expect(await page.locator('#office-root .td-adv').count()).toBe(0);
        expect(await page.locator('#office-root .week-k').count()).toBe(0);
        await expect(page.locator('#office-root .wr-empty')).toHaveText('Opens with the invite period');
      }
      if (name !== 'first_week') {
        await expect(page.locator('#office-root .rs-n').first()).toContainText('Amariabi International');
        await expect(page.locator('#office-root .rs-n').nth(1)).toContainText('Long Island Methodist');
      }
      if (name === 'regular') {
        expect(await page.locator('#office-root .mv-cell .chip').count()).toBe(0);
      }
      const numbers = await measure(page);
      fit[name][size[2]] = numbers;
      expect(Math.abs(numbers.left - numbers.pad), name + ' left pad').toBeLessThan(1.5);
      expect(Math.abs(numbers.right - numbers.pad), name + ' right pad').toBeLessThan(1.5);
      expect(numbers.mainScroll, name + ' ' + size[2] + ' vertical').toBeLessThanOrEqual(1);
      if (numbers.standings && numbers.standings.mode === 'window') {
        expect(numbers.standings.shown, name + ' ' + size[2] + ' window').toBeLessThan(numbers.standings.total);
        expect(numbers.standings.shown, name + ' ' + size[2] + ' window').toBeGreaterThanOrEqual(size[2] === '1280' ? 3 : 5);
      } else if (numbers.standings) {
        expect(numbers.standings.mode, name + ' ' + size[2] + ' full table').toBe('all');
        expect(numbers.standings.shown, name + ' ' + size[2] + ' rows').toBe(numbers.standings.total);
      }
      if (size[2] === '1280') {
        expect(numbers.pageWide, name + ' horizontal').toBeLessThanOrEqual(1);
        numbers.clip.forEach(function (px, index) {
          expect(px, name + ' column ' + (index + 1) + ' clipped').toBeLessThanOrEqual(1);
        });
        await assertOneVerticalScroll(page);
      }
      if (size[2] === '1920' && numbers.standings && numbers.standings.mode === 'all') {
        numbers.clip.forEach(function (px, index) {
          expect(px, name + ' 1920 column ' + (index + 1) + ' clipped').toBeLessThanOrEqual(1);
        });
      }
      expect(numbers.standings && numbers.standings.column, name + ' standings column').toBe(2);
      await page.screenshot({ path: path.join(V3B, name + '-' + size[2] + '.png') });
    }
  }
  fs.writeFileSync(path.join(V3B, 'fit.json'), JSON.stringify(fit, null, 2));
});

test('frames at their design sizes', async ({ page }) => {
  for (const row of FRAME_SHOTS) {
    await page.setViewportSize({ width: row[1], height: row[2] });
    await page.goto('file://' + path.join(FRAMES, row[0]));
    await page.screenshot({ path: path.join(OUT, 'frame-' + row[0].replace('.html', '.png')) });
  }
});

test('advance mirror matches the top bar', async ({ page }) => {
  const cases = [
    ['training', commandCenter(digest('win', {
      todos: [
        { id: 'run_training', label_key: 'run_training', required: true, done: false, gates_advance: true, is_advance_action: true, route: '/training.html' },
        { id: 'play_next_game', label_key: 'play_next_game', required: true, done: false, gates_advance: false, is_advance_action: false, route: '/set-lineup.html' },
      ],
    }), { week: 10, training_completed: false }), '/training.html'],
    ['game', commandCenter(digest('win'), { week: 12, training_completed: true }), '/set-lineup.html'],
    ['cut', commandCenter(digest('regular', {
      todos: [
        { id: 'assign_practice_squad', label_key: 'assign_practice_squad', required: true, done: false, gates_advance: true, is_advance_action: true, route: '/cut-players.html' },
      ],
    }), { week: 8, cut_required: true, training_completed: true }), '/cut-players.html'],
  ];
  const log = [];
  for (const row of cases) {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, row[1]);
    await page.evaluate(() => {
      window.__officeNav = [];
      const nav = window.GOBNav;
      if (!nav || !nav.go) return;
      const real = nav.go.bind(nav);
      nav.go = function (url) {
        window.__officeNav.push(String(url));
        void real;
      };
    });
    await expect(page.locator('#play-now')).toBeVisible();
    await expect(page.locator('[data-advance-mirror="1"] .td-l')).toHaveText(
      ((await page.locator('#play-now').textContent()) || '').trim()
    );
    const todoUrl = await captureNav(page, '[data-advance-mirror="1"]');
    await openOffice(page, row[1]);
    await page.evaluate(() => {
      window.__officeNav = [];
      const nav = window.GOBNav;
      nav.go = function (url) { window.__officeNav.push(String(url)); };
    });
    const barUrl = await captureNav(page, '#play-now');
    expect(new URL(todoUrl, 'http://local').pathname).toBe(row[2]);
    expect(new URL(barUrl, 'http://local').pathname).toBe(new URL(todoUrl, 'http://local').pathname);
    log.push(row[0] + ' ' + new URL(todoUrl, 'http://local').pathname);
  }
  fs.writeFileSync(path.join(OUT, 'advance.txt'), log.join('\n') + '\n');
});

async function captureNav(page, selector) {
  await mouseClick(page, selector);
  await page.waitForFunction(() => window.__officeNav && window.__officeNav.length > 0, null, { timeout: 8000 });
  return page.evaluate(() => window.__officeNav[0]);
}

test('live mid-season digest', async ({ page }) => {
  const file = path.join(OUT, 'live-digest.json');
  test.skip(!fs.existsSync(file), 'no live digest dump');
  const dumped = JSON.parse(fs.readFileSync(file, 'utf8'));
  const data = commandCenter(dumped.office_digest, {
    week: dumped.week,
    team: dumped.team || 'Lancaster',
    rank: dumped.rank,
    training_completed: dumped.training_completed !== false,
  });
  for (const size of [[1280, 720, '1280'], [1440, 900, '1440'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await openOffice(page, data);
    await assertOfficeText(page);
    await assertHeadersClear(page);
    await assertLabelsFit(page);
    await assertMonograms(page);
    await assertWireFitsContent(page);
    expect(await page.locator('#office-root .td-gate').count()).toBe(0);
    expect(await page.locator('#office-root .td-adv').count()).toBe(0);
    expect(await page.locator('#office-root .week-k').count()).toBe(0);
    await expect(page.locator('#office-root .wr-empty')).toHaveText('No recruiting movement this week');
    await expect(page.locator('#office-root .nx-sub')).toContainText('7–7');
    await expect(page.locator('#office-root .nx-sub')).toContainText('A1');
    await expect(page.locator('[data-advance-mirror="1"] .td-l')).toHaveText(
      ((await page.locator('#play-now').textContent()) || '').trim()
    );
    if (size[2] === '1920') {
      await expect(page.locator('#office-root .pg-extra')).toContainText('20');
      await expect(page.locator('#office-root .pg-extra')).not.toContainText('1237');
    }
    const numbers = await measure(page);
    expect(numbers.mainScroll, 'live ' + size[2] + ' vertical').toBeLessThanOrEqual(1);
    if (size[2] === '1280') {
      await assertOneVerticalScroll(page);
    }
    await page.screenshot({ path: path.join(V3B, 'live-' + size[2] + '.png') });
  }
});

test('week strip states and clicks', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, STATES.win);
  const steps = await page.locator('#office-root .wk-step').evaluateAll((nodes) => nodes.map((node) => ({
    state: node.dataset.stepState,
    next: node.classList.contains('is-next'),
    text: node.innerText.replace(/\s+/g, ' ').trim(),
  })));
  expect(steps.map((step) => step.state)).toEqual(['done', 'blocking', 'upcoming', 'upcoming', 'upcoming']);
  expect(steps[1].next).toBe(true);
  expect(steps[1].text).toContain('BLOCKS ADVANCE');
  expect(await page.locator('#office-root .td-adv').count()).toBe(0);
  expect(await page.locator('#office-root .week-k').count()).toBe(0);
  expect(await page.locator('#office-root .wk-step.gated .td-adv').count()).toBe(0);
  const inset = await page.locator('#office-root .wk-step.is-next').evaluate((node) => {
    const dot = node.querySelector('.wk-dot');
    const pad = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dsp-8'));
    const pads = [...document.querySelectorAll('#office-root .wk-step')].map((step) => getComputedStyle(step).padding);
    return {
      inset: dot.getBoundingClientRect().left - node.getBoundingClientRect().left,
      pad: pad,
      pads: pads,
    };
  });
  expect(inset.inset).toBeGreaterThanOrEqual(inset.pad - 0.5);
  expect(new Set(inset.pads).size).toBe(1);
  const doneOpacity = await page.locator('#office-root .wk-step.done').evaluate((node) => getComputedStyle(node).opacity);
  expect(doneOpacity).toBe('0.38');
  const strip = await page.locator('#office-root .week-strip').evaluate((node) => ({
    h: node.getBoundingClientRect().height,
    wide: node.scrollWidth - node.clientWidth,
  }));
  expect(strip.h).toBeGreaterThan(50);
  expect(strip.h).toBeLessThan(60);
  expect(strip.wide).toBeLessThanOrEqual(1);
  await page.evaluate(() => {
    window.__officeNav = [];
    window.GOBNav.go = function (url) { window.__officeNav.push(String(url)); };
  });
  await mouseClick(page, '#office-root .wk-step.done');
  await page.waitForFunction(() => window.__officeNav && window.__officeNav.length > 0);
  expect(new URL((await page.evaluate(() => window.__officeNav[0])), 'http://local').pathname).toBe('/training.html');
});

test('attribute chips group, order, and cap', async ({ page }) => {
  const changes = [
    { player_id: 'p-zoe', name: 'Zoe Ng', attribute: 'SH', from: 1, to: 2 },
    { player_id: 'p-amy', name: 'Amy Cole', attribute: 'BH', from: 3, to: 5 },
    { player_id: 'p-amy', name: 'Amy Cole', attribute: 'ND', from: 8, to: 7 },
    { player_id: 'p-bob', name: 'Bob Hale', attribute: 'SC', from: 4, to: 5 },
    { player_id: 'p-cal', name: 'Cal Ives', attribute: 'ID', from: 2, to: 4 },
    { player_id: 'p-dee', name: 'Dee Ortiz', attribute: 'OD', from: 5, to: 6 },
    { player_id: 'p-eve', name: 'Eve Park', attribute: 'PS', from: 6, to: 8 },
    { player_id: 'p-eve', name: 'Eve Park', attribute: 'AG', from: 4, to: 3 },
  ];
  const data = commandCenter(digest('win', {
    what_moved: {
      national_rank: { now: 18, prev: 18, delta: 0 },
      conference_standing: { now: 3, prev: 3, delta: 0 },
      record: { wins: 16, losses: 5 },
      streak: null,
      attribute_changes: changes,
    },
  }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, data);
  await assertOfficeText(page);
  expect(await page.locator('#office-root .mv-cell .chip').count()).toBe(0);
  const rows = await page.locator('#office-root .mv-p').evaluateAll((nodes) => nodes.map((node) => ({
    id: node.dataset.playerId,
    chips: [...node.querySelectorAll('.attr-chip')].map((chip) => ({
      code: chip.querySelector('.attr-code').textContent,
      value: chip.querySelector('.tdig').textContent,
      title: chip.getAttribute('title'),
      dir: chip.querySelector('.arr').classList.contains('up') ? 'up' : 'down',
      text: chip.textContent,
    })),
  })));
  expect(rows.map((row) => row.id)).toEqual(['p-amy', 'p-eve', 'p-cal', 'p-bob', 'p-dee']);
  expect(rows[0].chips.map((chip) => chip.code + chip.dir + chip.value)).toEqual(['BHup5', 'NDdown7']);
  expect(rows[0].chips[0].title).toBe('Ball Handling');
  expect(rows[0].chips[0].text).not.toContain('3');
  expect(rows[1].chips.map((chip) => chip.dir)).toEqual(['up', 'down']);
  await expect(page.locator('#office-root .office-mv .lnk')).toHaveText(/All changes/);
  const href = await page.locator('#office-root .office-mv .lnk').getAttribute('href');
  expect(href).toContain('/training-report.html');
  expect(href).toContain('week=21');
  const nameHref = await page.locator('#office-root .mv-p[data-player-id="p-amy"] .nm').getAttribute('href');
  expect(nameHref).toContain('/player-detail.html');
  expect(nameHref).toContain('id=p-amy');
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openOffice(page, data);
  expect(await page.locator('#office-root .mv-p').count()).toBe(6);
  expect(await page.locator('#office-root .office-mv .lnk').count()).toBe(0);
  const edge = await page.evaluate(() => {
    const row = document.querySelector('#office-root .mv-p');
    const card = row.closest('.card');
    const chips = row.querySelectorAll('.attr-chip');
    const chip = chips[chips.length - 1];
    const style = getComputedStyle(card);
    const contentRight = card.getBoundingClientRect().right - parseFloat(style.paddingRight);
    return Math.abs(contentRight - chip.getBoundingClientRect().right);
  });
  expect(edge).toBeLessThanOrEqual(1);
});

test('next game, standings, chemistry, and attitude', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, STATES.win);
  await assertOfficeText(page);
  const rankStyle = await page.locator('#office-root .nx-rank').evaluate((node) => ({
    style: getComputedStyle(node).fontStyle,
    family: getComputedStyle(node).fontFamily,
    text: node.parentElement.textContent.replace(/\s+/g, ' ').trim(),
  }));
  expect(rankStyle.style).toBe('normal');
  expect(rankStyle.family).toMatch(/Bebas/i);
  expect(rankStyle.text).toBe('21. Crickstown');
  await expect(page.locator('#office-root .nx-sub')).toContainText('Conference A2 (2 of 8)');
  await expect(page.locator('#office-root .nx-sub')).not.toContainText('Week');
  await expect(page.locator('#office-root .rs-n').first()).toContainText('#18');
  await expect(page.locator('#office-root .office-h').nth(1)).toHaveText(/This Week/);
  const heading = page.locator('#office-root .office-col').nth(2).locator('.col-link');
  await expect(heading).toHaveAttribute('href', /recruiting\.html/);
  expect(await page.locator('#office-root .office-wire h3').count()).toBe(0);
  const col2 = page.locator('#office-root .office-col').nth(1);
  await expect(col2.locator('.office-st h3')).toHaveText('Conference A2 standings');
  await expect(page.locator('#office-root .office-col').nth(2).locator('.office-st')).toHaveCount(0);
  const shown = await page.locator('#office-root .office-st .st-r:not(.st-hd)').evaluateAll((nodes) => {
    return nodes.map((node) => ({
      me: node.classList.contains('me'),
      name: node.querySelector('.st-n').textContent,
      pos: node.firstElementChild.textContent,
    }));
  });
  const mode = await page.locator('#office-root .office-st').getAttribute('data-standings-mode');
  const order = standingsBlock().rows.map((row) => row.team_name);
  const visible = shown.map((row) => row.name);
  expect(shown.some((row) => row.me && row.name === 'Amariabi International')).toBe(true);
  const start = order.indexOf(visible[0]);
  expect(order.slice(start, start + visible.length)).toEqual(visible);
  if (mode === 'all') {
    expect(visible).toEqual(order);
    expect(await page.locator('#office-root .st-more').count()).toBe(0);
  } else {
    expect(mode).toBe('window');
    expect(visible.length).toBeGreaterThanOrEqual(3);
    expect(visible.length).toBeLessThan(order.length);
    await expect(page.locator('#office-root .st-more')).toHaveAttribute('href', /tab=standings-tab/);
  }
  const rowMetrics = await page.evaluate(() => {
    const watch = document.querySelector('#office-root .ptw');
    const row = document.querySelector('#office-root .office-st .st-r:not(.st-hd):not(.me)');
    const watchStyle = getComputedStyle(watch);
    const rowStyle = getComputedStyle(row);
    const name = getComputedStyle(row.querySelector('.st-n'));
    const watchName = getComputedStyle(watch.querySelector('.nm'));
    const record = getComputedStyle(row.querySelector('.st-wl'));
    const watchNum = getComputedStyle(watch.querySelector('b'));
    const place = getComputedStyle(row.querySelector('.st-pos'));
    const me = getComputedStyle(document.querySelector('#office-root .office-st .st-r.me'));
    const px = (style, prop) => parseFloat(style[prop]);
    return {
      font: Math.abs(px(watchStyle, 'fontSize') - px(rowStyle, 'fontSize')),
      lineMatch: watchStyle.lineHeight === rowStyle.lineHeight,
      lineWatch: watchStyle.lineHeight,
      lineRow: rowStyle.lineHeight,
      padTop: Math.abs(px(watchStyle, 'paddingTop') - px(rowStyle, 'paddingTop')),
      padBottom: Math.abs(px(watchStyle, 'paddingBottom') - px(rowStyle, 'paddingBottom')),
      nameSize: Math.abs(px(name, 'fontSize') - px(watchName, 'fontSize')),
      nameWeight: name.fontWeight === watchName.fontWeight,
      nameTrack: name.letterSpacing,
      recordFamily: record.fontFamily,
      watchFamily: watchNum.fontFamily,
      recordSize: Math.abs(px(record, 'fontSize') - px(watchNum, 'fontSize')),
      placeTrack: place.letterSpacing,
      mePadLeft: px(me, 'paddingLeft'),
      mePadTop: px(me, 'paddingTop'),
    };
  });
  expect(rowMetrics.font).toBeLessThanOrEqual(1);
  expect(rowMetrics.lineMatch, rowMetrics.lineWatch + ' vs ' + rowMetrics.lineRow).toBe(true);
  expect(rowMetrics.padTop).toBeLessThanOrEqual(1);
  expect(rowMetrics.padBottom).toBeLessThanOrEqual(1);
  expect(rowMetrics.nameSize).toBeLessThanOrEqual(1);
  expect(rowMetrics.nameWeight).toBe(true);
  expect(rowMetrics.nameTrack === 'normal' || rowMetrics.nameTrack === '0px').toBe(true);
  expect(rowMetrics.placeTrack === 'normal' || rowMetrics.placeTrack === '0px').toBe(true);
  expect(rowMetrics.recordFamily).toMatch(/Bebas/i);
  expect(rowMetrics.watchFamily).toMatch(/Bebas/i);
  expect(rowMetrics.recordSize).toBeLessThanOrEqual(1);
  expect(rowMetrics.mePadLeft).toBeGreaterThanOrEqual(6);
  expect(rowMetrics.mePadTop).toBeGreaterThanOrEqual(4);
  const headerAlign = await page.evaluate(() => {
    const head = document.querySelector('#office-root .office-st .st-hd .st-wl');
    const value = document.querySelector('#office-root .office-st .st-r:not(.st-hd) .st-wl');
    const title = document.querySelector('#office-root .office-st .card-h');
    const headerRow = document.querySelector('#office-root .office-st .st-hd');
    const snap = document.querySelector('#office-root .office-snap');
    const snapTitle = snap.querySelector('.card-h');
    const snapNext = snapTitle.nextElementSibling;
    const gap = headerRow.getBoundingClientRect().top - title.getBoundingClientRect().bottom;
    const snapGap = snapNext.getBoundingClientRect().top - snapTitle.getBoundingClientRect().bottom;
    return {
      edge: Math.abs(head.getBoundingClientRect().right - value.getBoundingClientRect().right),
      gap: gap,
      snapGap: snapGap,
    };
  });
  expect(headerAlign.edge).toBeLessThanOrEqual(1);
  expect(Math.abs(headerAlign.gap - headerAlign.snapGap)).toBeLessThanOrEqual(1);
  await page.setViewportSize({ width: 1440, height: 900 });
  await openOffice(page, STATES.win);
  await expect(page.locator('#office-root .office-st')).toHaveAttribute('data-standings-mode', 'all');
  expect(await page.locator('#office-root .office-st .st-r:not(.st-hd)').count()).toBe(8);
  expect(await page.locator('#office-root .st-more').count()).toBe(0);
  const typeStep = await page.evaluate(() => {
    const title = document.querySelector('#office-root .office-mv h3');
    const body = document.querySelector('#office-root .sn-l');
    const heading = document.querySelector('#office-root .office-h h2');
    const emoji = document.querySelector('#office-root .att-emoji');
    const meter = document.querySelector('#office-root .meter.chem');
    const step = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--fs-15'));
    return {
      title: parseFloat(getComputedStyle(title).fontSize),
      step: step,
      body: parseFloat(getComputedStyle(body).fontSize),
      heading: parseFloat(getComputedStyle(heading).fontSize),
      emoji: parseFloat(getComputedStyle(emoji).fontSize),
      meter: meter.getBoundingClientRect().height,
    };
  });
  expect(typeStep.title).toBeCloseTo(typeStep.step, 0);
  expect(typeStep.title).toBeGreaterThan(typeStep.body);
  expect(typeStep.title).toBeLessThan(typeStep.heading);
  expect(typeStep.emoji).toBe(16);
  expect(typeStep.meter).toBeGreaterThanOrEqual(6);
  const attitude = await page.locator('#office-root .att-col').evaluateAll((nodes) => {
    const widths = nodes.map((node) => node.getBoundingClientRect().width);
    const centers = nodes.map((node) => {
      const emoji = node.querySelector('.att-emoji').getBoundingClientRect();
      const bar = node.querySelector('.att-bar').getBoundingClientRect();
      return Math.abs((emoji.left + emoji.width / 2) - (bar.left + bar.width / 2));
    });
    return { widths: widths, centers: centers, count: nodes.length };
  });
  expect(attitude.count).toBe(5);
  expect(Math.max(...attitude.widths) - Math.min(...attitude.widths)).toBeLessThanOrEqual(1);
  attitude.centers.forEach((delta) => expect(delta).toBeLessThanOrEqual(1));

  for (const band of [[5, 'red'], [13, 'yellow'], [20, 'green']]) {
    const data = commandCenter(digest('win', {
      team_snapshot: snapshotBlock({ chemistry: { value: band[0], max: 25 } }),
    }));
    await openOffice(page, data);
    await expect(page.locator('#office-root .meter.chem')).toHaveAttribute('data-chem-band', band[1]);
    const paint = await page.locator('#office-root .meter.chem i').evaluate((node) => getComputedStyle(node).backgroundImage);
    expect(paint).toContain('gradient');
    expect(paint.toLowerCase()).not.toContain('74, 144, 217');
  }
});

test('recruiting keeps the latest event and whole rows', async ({ page }) => {
  const events = [];
  for (let i = 0; i < 10; i += 1) {
    events.push({
      recruit_id: 'r' + i,
      recruit: 'Recruit ' + i,
      position: 'SG',
      event_text: 'Moved ' + i,
      direction: 'up',
    });
  }
  events.push({
    recruit_id: 'r1',
    recruit: 'Recruit 1',
    position: 'SG',
    event_text: 'Latest for 1',
    direction: 'down',
  });
  const data = commandCenter(digest('win', {
    recruiting_wire: wireBlock({ events: events, status: 'Busy' }),
  }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, data);
  const rows = await page.locator('#office-root .office-wire .wr').evaluateAll((nodes) => {
    return nodes.map((node) => node.dataset.recruitKey);
  });
  expect(new Set(rows).size).toBe(rows.length);
  expect(rows).not.toContain('id:r0');
  expect(rows).toContain('id:r1');
  await expect(page.locator('#office-root .office-wire')).toContainText('Latest for 1');
  expect(rows.length).toBeLessThanOrEqual(8);
  expect(rows.length).toBeGreaterThan(0);
  const cut = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const limit = main.getBoundingClientRect().bottom;
    return [...document.querySelectorAll('#office-root .office-wire .wr')].filter((node) => {
      return node.getBoundingClientRect().bottom > limit + 1;
    }).length;
  });
  expect(cut).toBe(0);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await openOffice(page, data);
  expect(await page.locator('#office-root .office-wire .wr').count()).toBeLessThanOrEqual(12);
  const empty = commandCenter(digest('regular', {
    recruiting_wire: wireBlock({ events: [], status: 'No recruiting movement', pending_count: 0, urgent: false }),
  }));
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, empty);
  await expect(page.locator('#office-root .wr-empty')).toHaveText('No recruiting movement this week');
});

async function logoBox(page) {
  return page.evaluate(() => {
    const logo = document.getElementById('team-logo');
    const topH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--top-h'));
    const box = logo.getBoundingClientRect();
    const natural = logo.naturalWidth / logo.naturalHeight;
    return {
      topH: topH,
      logoH: box.height,
      logoW: box.width,
      natural: natural,
      boxRatio: box.width / box.height,
      alt: logo.alt,
      title: logo.title,
      label: document.getElementById('gob-top-id').getAttribute('aria-label'),
    };
  });
}

test('logo fills the top bar on office and standalone pages', async ({ page }) => {
  const pages = [
    '/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID,
    '/rankings.html?franchise_id=' + FID + '&team_id=' + TID,
    '/schedule.html?franchise_id=' + FID + '&team_id=' + TID,
  ];
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    for (const url of pages) {
      await stubAuth(page);
      await installApi(page, STATES.win);
      await page.goto(url);
      await page.waitForSelector('html.gob-shell #team-logo');
      await page.waitForFunction(() => {
        const logo = document.getElementById('team-logo');
        return logo && logo.naturalWidth > 0;
      });
      const box = await logoBox(page);
      expect(Math.abs(box.logoH - box.topH), url).toBeLessThanOrEqual(1);
      expect(box.logoW).toBeGreaterThan(0);
      expect(Math.abs(box.boxRatio - box.natural), url + ' aspect').toBeLessThan(0.08);
      expect(box.alt).toBe('Lancaster');
      expect(box.title).toBe('Lancaster');
      expect(box.label).toBe('Lancaster');
    }
  }
});

test('null wire fields stay out of the dom', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, STATES.win);
  const html = await page.locator('#office-root').innerHTML();
  expect(html).not.toContain('null');
  expect(html).not.toContain('undefined');
  expect(html).not.toContain('N/A');
  expect(html).not.toContain('filmed');
  expect(await page.locator('#gob-rail-recruiting em.office-rail-count.urgent')).toHaveText('1');
});
