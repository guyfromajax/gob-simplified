const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 360000 });

const FID = 'f-e2e-shell2';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/shell-2');

const BROWSE = [
  'recruiting.html',
  'rankings.html',
  'schedule.html',
  'practice-squad-standings.html',
  'practice-squad-bracket.html',
  'brackets.html',
  'awards.html',
  'news.html',
  'leaders.html',
  'player-detail.html',
  'team-roster-view.html',
  'standings.html',
  'team-stats.html',
  'stats.html',
];

const FOCUS = [
  'set-lineup.html',
  'training.html',
  'training-report.html',
  'training-squad-report.html',
  'training-playbooks.html',
  'cut-players.html',
  'game-plan.html',
  'playbooks.html',
  'playbook-report.html',
];

function cc(overrides) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 1,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 1, counts: {} },
    user_conference: 1,
    user_region: 'A',
    team_record: { wins: 16, losses: 5 },
  }, overrides || {});
}

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function midSeason() {
  const opp = 'bbbbbbbbbbbbbbbbbbbbbbbb';
  const rankings = [];
  for (let i = 0; i < 128; i += 1) {
    const name = i === 0 ? 'Lancaster' : ('Program ' + (i + 1));
    rankings.push({
      rank: i + 1,
      natl_rank: i + 1,
      team_id: i === 0 ? TID : opp.slice(0, 23) + String(i % 10),
      name: name,
      team_name: name,
      display_name: name,
      PF: 80,
      PA: 70,
      differential: 10,
      W: 10 - (i % 4),
      L: i % 4,
      conference: (i % 16) + 1,
      region: 'ABCDEFGH'[i % 8],
      last_week: 'W vs Program 2',
      last_week_result: 'W',
      next: 'vs Program 3',
      primary_color: '#c4a35a',
    });
  }
  const standings = rankings.slice(0, 8).map(function (row) {
    return Object.assign({}, row, { conference: 1, region: 'A' });
  });
  const schedule = [];
  for (let w = 0; w < 12; w += 1) {
    schedule.push([{
      away_team_id: TID,
      home_team_id: opp,
      away_conference: 1,
      home_conference: 1,
      away_score: w < 11 ? 72 : null,
      home_score: w < 11 ? 66 : null,
    }]);
  }
  const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
  const years = ['Freshman', 'Sophomore', 'Junior', 'Senior'];
  const recruits = [];
  for (let i = 0; i < 48; i += 1) {
    const pos = positions[i % 5];
    const ratings = { PG: 40, SG: 40, SF: 40, PF: 40, C: 40 };
    ratings[pos] = 70 + (i % 20);
    recruits.push({
      recruit_id: 'r' + i,
      name: 'Recruit ' + (i + 1),
      'Home Region': 'A',
      archetype: 'Scorer',
      height: 72 + (i % 10),
      weight: 170 + i,
      year: years[i % 4],
      position_ratings: ratings,
      potential_rt_ratcheted: 82,
      Lean: {},
      attributes: { SC: 70, SH: 60, ID: 55, OD: 50, PS: 48, BH: 52, RB: 40, AG: 60, ST: 58, ND: 44, IQ: 62, FT: 66 },
    });
  }
  const players = [];
  for (let i = 0; i < 24; i += 1) {
    const pos = positions[i % 5];
    const ratings = { PG: 50, SG: 50, SF: 50, PF: 50, C: 50 };
    ratings[pos] = 78;
    players.push({
      id: 'p' + i,
      player_id: 'p' + i,
      name: 'Player ' + (i + 1),
      jersey: String(i + 1),
      position: pos,
      position_ratings: ratings,
      attributes: {},
    });
  }
  const news = [8, 9, 10, 11, 12].map(function (week) {
    return {
      story_id: 'story-' + week,
      week: week,
      headline: 'Week ' + week + ' — Lancaster stays in the regional race',
      body: 'Lancaster won its week ' + week + ' game.',
    };
  });
  const teamStats = {
    teams: rankings.map(function (row, i) {
      return {
        team: row.team_name,
        team_id: row.team_id,
        natl_rank: row.natl_rank,
        stats: {
          W: row.W, L: row.L, PF: 70 + (i % 20), PA: 64,
          FGM: 28, FGA: 60, '3PTM': 8, '3PTA': 22, FTM: 12, FTA: 16,
          DREB: 24, OREB: 10, TREB: 34, AST: 14, F: 16, TO: 11,
          STL: 7, BLK: 3, DEF_A: 40, DEF_S: 22, SCR_A: 12, SCR_S: 6,
        },
      };
    }),
  };
  const boxPlayers = [];
  for (let side = 0; side < 2; side += 1) {
    const teamKey = side === 0 ? 'home' : 'away';
    const teamId = side === 0 ? TID : opp;
    for (let i = 0; i < 12; i += 1) {
      boxPlayers.push({
        playerId: teamKey + '-p' + i,
        _id: teamKey + '-p' + i,
        name: (side === 0 ? 'Home ' : 'Away ') + (i + 1),
        team: teamKey,
        team_id: teamId,
        jersey: i,
        year: 'SR',
        position: positions[i % 5],
        stats: { PTS: 8 + i, MIN: 1200, FGM: 3, FGA: 7, '3PTM': 1, '3PTA': 3, FTM: 2, FTA: 2, DREB: 3, OREB: 1, AST: 2, STL: 1, BLK: 0, TO: 1, F: 2 },
      });
    }
  }
  const data = cc({
    week: 12,
    rank: 8,
    rankings: rankings,
    standings: standings,
    user_team_object_id: TID,
    team_record: { wins: 9, losses: 2 },
  });
  return {
    data: data,
    standings: standings,
    schedule: schedule,
    recruits: recruits,
    players: players,
    news: news,
    opp: opp,
    teamStats: teamStats,
    boxPlayers: boxPlayers,
  };
}

async function installApi(page, data, rich) {
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
    if (pathname.startsWith('/franchise/standings')) {
      await fulfillJson(route, {
        standings: (rich && rich.standings) || [{ team_id: TID, name: 'Lancaster', W: 16, L: 5, conference: 1, region: 'A' }],
      });
      return;
    }
    if (rich && pathname.startsWith('/franchise/recruiting-data')) {
      await fulfillJson(route, {
        week: data.week,
        team_id: TID,
        team: 'Lancaster',
        team_region: 'A',
        season: 1,
        recruits: rich.recruits,
        recruiting_wire: data.recruiting_wire,
        roster_capacity: { used: 12, max: 15 },
        competition_counts: {},
      });
      return;
    }
    if (rich && pathname.startsWith('/franchise/schedule/national')) {
      const names = {};
      names[TID] = 'Lancaster';
      names[rich.opp] = 'Four Corners';
      await fulfillJson(route, {
        schedule: rich.schedule,
        tournament_schedule: {},
        team_name_map: names,
        team_display_name_map: names,
      });
      return;
    }
    if (rich && pathname.startsWith('/franchise/news')) {
      await fulfillJson(route, { news: rich.news });
      return;
    }
    if (rich && pathname.startsWith('/franchise/team-stats')) {
      await fulfillJson(route, rich.teamStats);
      return;
    }
    if (rich && pathname.startsWith('/roster/')) {
      await fulfillJson(route, {
        players: rich.players,
        conference: 1,
        region: 'A',
        team_chemistry: 18,
        name: 'Lancaster',
        team_record: data.team_record || null,
      });
      return;
    }
    if (rich && pathname.indexOf('/api/game/') === 0 && pathname.indexOf('resume-state') === -1) {
      const homeBox = {};
      const awayBox = {};
      (rich.boxPlayers || []).forEach(function (player) {
        const slot = Object.assign({ name: player.name, playerId: player.playerId }, player.stats);
        if (player.team === 'away') awayBox[player.position + player.jersey] = slot;
        else homeBox[player.position + player.jersey] = slot;
      });
      const teams = {};
      teams[TID] = { name: 'Lancaster' };
      teams[rich.opp] = { name: 'Four Corners' };
      const boxScore = {};
      boxScore[TID] = homeBox;
      boxScore[rich.opp] = awayBox;
      await fulfillJson(route, {
        home_team_id: TID,
        away_team_id: rich.opp,
        teams: teams,
        home_team: { name: 'Lancaster' },
        away_team: { name: 'Four Corners' },
        score: { Lancaster: 78, 'Four Corners': 71 },
        clock: '0:00',
        quarter: 4,
        players: rich.boxPlayers || [],
        box_score: boxScore,
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function mouseClick(page, target) {
  const loc = typeof target === 'string' ? page.locator(target).first() : target;
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing target');
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 20));
}

function stab(page, label) {
  return page.locator('#gob-subtabs .stab').filter({ hasText: new RegExp('^' + label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$') });
}

async function assertNoHorizontalOverflow(page) {
  const offenders = await page.evaluate(() => {
    const out = [];
    function check(el, name) {
      if (!el) return;
      if (el.scrollWidth > el.clientWidth + 1) out.push(name + ' ' + el.scrollWidth + '>' + el.clientWidth);
    }
    const main = document.querySelector('html.gob-shell .main');
    check(main, '.main');
    check(document.scrollingElement, 'scrollingElement');
    if (!main) return out;
    const limit = main.getBoundingClientRect().right + 1;
    function visibleRight(el) {
      let edge = el.getBoundingClientRect().right;
      let node = el.parentElement;
      while (node && node !== main) {
        const ox = getComputedStyle(node).overflowX;
        if (ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') {
          edge = Math.min(edge, node.getBoundingClientRect().right);
        }
        node = node.parentElement;
      }
      return edge;
    }
    main.querySelectorAll('table, .fcc-data-card, .team-stats-page-card, .gob-wide-wrap').forEach(function (el) {
      if (el.getBoundingClientRect().width < 1) return;
      if (visibleRight(el) > limit) {
        const id = el.id || String(el.className || '').slice(0, 60);
        out.push(id + ' right ' + Math.round(visibleRight(el)) + '>' + Math.round(limit));
      }
    });
    return out;
  });
  expect(offenders, offenders.join('; ')).toEqual([]);
}

async function wideTables(page) {
  return page.evaluate(() => {
    if (window.GOBShell && typeof window.GOBShell.classifyTables === 'function') window.GOBShell.classifyTables();
    return (window.__gobWideTables || []).map(function (row) {
      return row.id + ' table=' + row.table + ' wrap=' + row.wrap + ' main=' + row.main;
    });
  });
}

async function stickyGeometry(page, headerSel, rowSel) {
  return page.evaluate(({ headerSel, rowSel }) => {
    const head = document.querySelector('html.gob-shell .pg-head');
    const headers = Array.from(document.querySelectorAll(headerSel));
    const rows = Array.from(document.querySelectorAll(rowSel));
    const headBox = head.getBoundingClientRect();
    let stackTop = Infinity;
    let stackBottom = -Infinity;
    headers.forEach((el) => {
      const b = el.getBoundingClientRect();
      if (b.height < 1) return;
      stackTop = Math.min(stackTop, b.top);
      stackBottom = Math.max(stackBottom, b.bottom);
    });
    const rowBox = rows[0].getBoundingClientRect();
    const gapRows = rows.filter((el) => {
      const b = el.getBoundingClientRect();
      return stackTop - headBox.bottom > 1 && b.bottom > headBox.bottom + 1 && b.top < stackTop - 1;
    }).length;
    return {
      headerToRow: Math.abs(stackBottom - rowBox.top),
      headToHeader: Math.abs(stackTop - headBox.bottom),
      gapRows: gapRows,
    };
  }, { headerSel, rowSel });
}

async function railIconTops(page) {
  return page.evaluate(() => {
    const rail = document.querySelector('html.gob-shell .app > nav.rail');
    const face = rail && rail.querySelector('.rail-face');
    if (!face) return [];
    const box = face.getBoundingClientRect();
    return Array.from(face.querySelectorAll(':scope > .rail-i')).map(function (el) {
      const b = el.getBoundingClientRect();
      return Math.round(b.top - box.top);
    });
  });
}

async function openPage(page, file, data, extra, rich) {
  await stubAuth(page);
  await installApi(page, data, rich);
  const q = 'franchise_id=' + FID + '&team_id=' + TID + (extra || '');
  await page.goto('/' + file + '?' + q);
  await page.waitForSelector('html.gob-shell .app');
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('browse and focus pages, screenshots, and one vertical scroll', async ({ page }) => {
  const loads = [];
  const wideLog = [];
  const season = midSeason();
  const pages = BROWSE.concat(FOCUS).concat(['box-score.html']);
  for (const file of pages) {
    let extra = '';
    if (file === 'box-score.html') {
      extra = '&return_url=' + encodeURIComponent('/schedule.html') + '&game_id=g-box&home=Lancaster&away=Four%20Corners';
    }
    if (file === 'set-lineup.html') {
      extra = '&home=Lancaster&away=Four%20Corners&home_display=Lancaster&away_display=Four%20Corners&my_team=home&game_id=g-mid&week=12';
    }
    await openPage(page, file, season.data, extra, season);
    const focus = FOCUS.indexOf(file) !== -1;
    if (focus) {
      await expect(page.locator('html.gob-focus')).toHaveCount(1);
      await expect(page.locator('nav.rail')).toHaveCount(0);
      await expect(page.locator('#play-now.advance')).toHaveCount(0);
      await expect(page.locator('#gob-focus-settings')).toBeVisible();
    } else {
      await expect(page.locator('nav.rail')).toHaveCount(1);
      await expect(page.locator('#play-now.advance')).toHaveCount(1);
    }
    if (file === 'set-lineup.html') {
      await page.waitForSelector('#team-banner:not([hidden]), #team-banner-fallback:not([hidden])');
    }
    if (file === 'team-stats.html') await page.waitForSelector('#teamstats-body tr');
    if (file === 'box-score.html' && extra.indexOf('return_url') !== -1) {
      await page.waitForSelector('#home-player-stats-body tr');
      await page.waitForSelector('#away-player-stats-body tr', { state: 'attached' });
    }
    if (!focus) {
      await page.waitForFunction(() => {
        const el = document.getElementById('gob-record-value');
        return !!(el && el.textContent.trim());
      });
      const record = (await page.locator('#gob-record-value').textContent()) || '';
      expect(record.trim(), file + ' record').not.toEqual('');
    }
    const meta = await page.evaluate(() => ({
      ms: window.__gobAdvanceLoadMs,
      reused: !!window.__gobAdvanceLoadReused,
    }));
    loads.push(file + ' ' + (meta.reused ? 'reused' : 'fetched') + ' ' + Math.round(meta.ms || 0) + 'ms');
    for (const size of [[1280, 720, '1280'], [1440, 900, '1440'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.waitForTimeout(200);
      await assertOneVerticalScroll(page);
      await assertNoHorizontalOverflow(page);
      const wide = await wideTables(page);
      wide.forEach(function (row) {
        wideLog.push(file + ' ' + size[2] + ' ' + row);
      });
      if (size[2] !== '1440') {
        const browseShot = file === 'box-score.html';
        const name = file.replace('.html', '') + (browseShot ? '-browse' : '') + '-' + size[2] + '.png';
        await page.screenshot({ path: path.join(OUT, name) });
      }
    }
  }
  await openPage(page, 'box-score.html', season.data, '&from=lineup&game_id=g-box&home=Lancaster&away=Four%20Corners', season);
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await page.waitForSelector('#home-player-stats-body tr');
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.waitForTimeout(200);
    await assertOneVerticalScroll(page);
    await assertNoHorizontalOverflow(page);
    await page.screenshot({ path: path.join(OUT, 'box-score-flow-' + size[2] + '.png') });
  }
  fs.writeFileSync(path.join(OUT, 'load-times.txt'), loads.join('\n') + '\n');
  fs.writeFileSync(path.join(OUT, 'wide-tables.txt'), (wideLog.length ? wideLog.join('\n') : 'none') + '\n');
});

test('tournament stays locked on standalone league pages at week 1', async ({ page }) => {
  for (const file of ['rankings.html', 'schedule.html']) {
    await openPage(page, file, cc());
    const tab = stab(page, 'Tournament');
    await expect(tab).toHaveClass(/is-locked/);
    await expect(tab).toHaveAttribute('aria-disabled', 'true');
    await expect(tab).toHaveAttribute('title', /Opens Week \d+/);
  }
});

async function pinTable(page, tableSel) {
  await page.evaluate((tableSel) => {
    const main = document.querySelector('html.gob-shell .main');
    const head = document.querySelector('html.gob-shell .pg-head');
    const table = document.querySelector(tableSel);
    main.scrollTop = 0;
    const headBottom = head.getBoundingClientRect().bottom;
    const tableBox = table.getBoundingClientRect();
    const delta = tableBox.top - headBottom;
    const room = Math.max(0, tableBox.bottom - headBottom - 80);
    main.scrollTop = Math.min(Math.max(24, delta + 36), room);
  }, tableSel);
}

test('sticky table headers sit on the first row, then pin under the page head', async ({ page }) => {
  const season = midSeason();
  const cases = [
    ['rankings.html', '#rankings-table', '#rankings-table thead th', '#rankings-table tbody tr', ''],
    ['recruiting.html', 'table.pool', 'table.pool thead th', 'table.pool tbody tr', ''],
    ['team-roster-view.html', '#roster-table', '#roster-table thead th', '#roster-table tbody tr', ''],
    ['box-score.html', '#quarter-scoring-table', '#quarter-scoring-table thead th', '#quarter-scoring-table tbody tr', '&return_url=' + encodeURIComponent('/schedule.html') + '&game_id=g-box&home=Lancaster&away=Four%20Corners'],
    ['box-score.html', '#home-player-stats-table', '#home-player-stats-table thead th', '#home-player-stats-body tr', '&return_url=' + encodeURIComponent('/schedule.html') + '&game_id=g-box&home=Lancaster&away=Four%20Corners'],
  ];
  for (const size of [[1280, 720], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    for (const item of cases) {
      await openPage(page, item[0], season.data, item[4], season);
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.waitForSelector(item[3]);
      await page.waitForFunction(() => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--gob-stick-top')) > 20);
      const wide = await page.evaluate((tableSel) => {
        const table = document.querySelector(tableSel);
        return !!(table && table.closest('.gob-wide-wrap'));
      }, item[1]);
      if (wide) {
        const contained = await page.evaluate((tableSel) => {
          const main = document.querySelector('html.gob-shell .main');
          const wrap = document.querySelector(tableSel).closest('.gob-wide-wrap');
          const header = document.querySelector(tableSel + ' thead th');
          return wrap.getBoundingClientRect().right <= main.getBoundingClientRect().right + 1
            && getComputedStyle(header).position !== 'sticky';
        }, item[1]);
        expect(contained, item[0] + ' ' + item[1] + ' wide ' + size[0]).toBe(true);
        continue;
      }
      await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
      const atTop = await stickyGeometry(page, item[2], item[3]);
      expect(atTop.headerToRow, item[0] + ' ' + item[1] + ' ' + size[0] + ' scroll 0').toBeLessThanOrEqual(1);
      await pinTable(page, item[1]);
      const stuck = await stickyGeometry(page, item[2], item[3]);
      expect(stuck.headToHeader, item[0] + ' ' + item[1] + ' ' + size[0] + ' scrolled').toBeLessThanOrEqual(1);
      expect(stuck.gapRows, item[0] + ' ' + item[1] + ' ' + size[0] + ' gap').toEqual(0);
      if (item[1] === '#quarter-scoring-table') {
        const leftWithTable = await page.evaluate(() => {
          const main = document.querySelector('html.gob-shell .main');
          const head = document.querySelector('html.gob-shell .pg-head').getBoundingClientRect();
          const table = document.querySelector('#quarter-scoring-table').getBoundingClientRect();
          main.scrollTop += table.bottom - head.bottom + 12;
          const header = document.querySelector('#quarter-scoring-table thead th').getBoundingClientRect();
          const headAfter = document.querySelector('html.gob-shell .pg-head').getBoundingClientRect();
          return header.bottom <= headAfter.bottom + 1;
        });
        expect(leftWithTable, 'quarter header leaves with its table ' + size[0]).toBe(true);
      }
    }
    await openPage(page, 'schedule.html', season.data, '', season);
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.waitForSelector('.schedule-game-row');
    expect(await page.locator('.main thead').count()).toBe(0);
    const scheduleGap = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      function gap() {
        const card = document.querySelector('.schedule-week-card');
        const title = card.querySelector('.schedule-week-title').getBoundingClientRect();
        const row = card.querySelector('.schedule-game-row').getBoundingClientRect();
        return Math.abs(title.bottom - row.top);
      }
      main.scrollTop = 0;
      const atTop = gap();
      main.scrollTop = 600;
      return { atTop: atTop, scrolled: gap() };
    });
    expect(Math.abs(scheduleGap.atTop - scheduleGap.scrolled), 'schedule ' + size[0]).toBeLessThanOrEqual(1);
  }
});

test('rail icon positions match across shell pages', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const files = ['franchise-command-center.html', 'rankings.html', 'recruiting.html', 'player-detail.html'];
  const tops = [];
  for (const file of files) {
    await openPage(page, file, cc());
    await page.setViewportSize({ width: 1280, height: 720 });
    const rects = await railIconTops(page);
    expect(rects.length).toBeGreaterThan(3);
    tops.push(rects);
  }
  for (let i = 1; i < tops.length; i += 1) {
    expect(tops[i]).toEqual(tops[0]);
  }
});

test('advance label matches the office on three weeks', async ({ page }) => {
  const weeks = [
    cc({ week: 4, training_completed: false, session_type: 'in-season' }),
    cc({ week: 8, training_completed: true }),
    cc({ week: 20, training_completed: true, recruiting_wire: { board_saved_week: 0, counts: {} } }),
  ];
  const surfaces = ['franchise-command-center.html', 'rankings.html', 'schedule.html', 'awards.html'];
  for (const data of weeks) {
    let office = null;
    for (const file of surfaces) {
      await openPage(page, file, data);
      await page.waitForFunction(() => {
        const btn = document.getElementById('play-now');
        return btn && btn.dataset.mode && btn.textContent && btn.textContent !== 'STARTING…';
      });
      const read = await page.evaluate(() => ({
        label: document.getElementById('play-now').textContent,
        mode: document.getElementById('play-now').dataset.mode,
      }));
      if (!office) office = read;
      expect(read).toEqual(office);
    }
  }
});

test('rankings sub-tab replace then back returns to League', async ({ page }) => {
  await openPage(page, 'franchise-command-center.html', cc());
  await page.waitForSelector('#play-now.advance');
  await mouseClick(page, '.rail [data-gob-section="league"]');
  await expect(page.locator('#gob-subtabs .stab.on')).toHaveText('Standings');
  await mouseClick(page, stab(page, 'Rankings'));
  await page.waitForURL(/rankings\.html/);
  await expect(page.locator('#gob-subtabs .stab.on')).toHaveText('Rankings');
  const mid = await page.evaluate(() => (history.state && history.state.gobIdx));
  await mouseClick(page, stab(page, 'Standings'));
  await page.waitForURL(/franchise-command-center\.html/);
  await expect(page.locator('#gob-subtabs .stab.on')).toHaveText('Standings');
  const after = await page.evaluate(() => (history.state && history.state.gobIdx));
  expect(after).toBe(mid);
  await page.goBack();
  await page.waitForURL(/franchise-command-center\.html\?.*tab=standings-tab/);
  await expect(page.locator('.rail [data-gob-section="league"].on')).toHaveCount(1);
});

test('flow pages keep their own exit and the court has no shell', async ({ page }) => {
  await openPage(page, 'training.html', cc({ training_completed: false }));
  await expect(page.locator('#back-btn')).toHaveCount(1);
  await expect(page.locator('.rail')).toHaveCount(0);
  await openPage(page, 'recruiting.html', cc(), '&action=run');
  await expect(page.locator('html.gob-focus')).toHaveCount(1);
  await stubAuth(page);
  await installApi(page, cc());
  await page.goto('/court.html?mode=franchise&franchise_id=' + FID);
  await page.waitForTimeout(400);
  await expect(page.locator('html.gob-shell')).toHaveCount(0);
  await expect(page.locator('.rail')).toHaveCount(0);
});

const OUT2 = path.join(__dirname, '../../reports/shell-2b');

async function chromeRects(page) {
  return page.evaluate(() => {
    function box(sel) {
      const el = document.querySelector(sel);
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
    }
    return { top: box('.top'), rail: box('nav.rail') };
  });
}

test('record comes from rankings when team_record is absent', async ({ page }) => {
  const season = midSeason();
  const data = Object.assign({}, season.data, { team_record: null });
  const rich = Object.assign({}, season, { data: data });
  const files = BROWSE.concat(['box-score.html']);
  for (const file of files) {
    let extra = '';
    if (file === 'box-score.html') {
      extra = '&return_url=' + encodeURIComponent('/schedule.html') + '&game_id=g-box&home=Lancaster&away=Four%20Corners';
    }
    await openPage(page, file, data, extra, rich);
    await page.waitForFunction(() => {
      const el = document.getElementById('gob-record-value');
      return !!(el && el.textContent.trim());
    });
    const record = ((await page.locator('#gob-record-value').textContent()) || '').trim();
    expect(record, file).toBe('10-0');
  }
});

test('top bar and rail stay put from Rankings to Schedule to Office', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openPage(page, 'rankings.html', cc());
  await page.waitForSelector('#gob-subtabs .stab');
  const names = await page.evaluate(() => ({
    top: getComputedStyle(document.querySelector('.top')).viewTransitionName,
    rail: getComputedStyle(document.querySelector('nav.rail')).viewTransitionName,
    main: getComputedStyle(document.querySelector('.main')).viewTransitionName,
  }));
  expect(names.top).toBe('gob-chrome-top');
  expect(names.rail).toBe('gob-chrome-rail');
  expect(names.main).toBe('none');
  const before = await chromeRects(page);
  await mouseClick(page, stab(page, 'Schedule'));
  await page.waitForURL(/schedule\.html/);
  fs.mkdirSync(OUT2, { recursive: true });
  await page.screenshot({ path: path.join(OUT2, 'transition-rankings-schedule.png') });
  expect(await chromeRects(page)).toEqual(before);
  await mouseClick(page, '.rail [data-gob-section="office"]');
  await page.waitForURL(/franchise-command-center\.html/);
  expect(await chromeRects(page)).toEqual(before);
  await page.goBack();
  await page.waitForURL(/schedule\.html/);
  expect(await chromeRects(page)).toEqual(before);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.reload();
  await page.waitForSelector('nav.rail');
  const reduced = await page.evaluate(() => getComputedStyle(document.querySelector('.top')).viewTransitionName);
  expect(reduced).toBe('none');
});

test('box score and team stats screenshots at three sizes', async ({ page }) => {
  fs.mkdirSync(OUT2, { recursive: true });
  const season = midSeason();
  const shots = [
    ['box-score.html', '&return_url=' + encodeURIComponent('/schedule.html') + '&game_id=g-box&home=Lancaster&away=Four%20Corners', 'box-score-browse', '#home-player-stats-body tr'],
    ['box-score.html', '&from=lineup&game_id=g-box&home=Lancaster&away=Four%20Corners', 'box-score-flow', '#home-player-stats-body tr'],
    ['team-stats.html', '', 'team-stats', '#teamstats-body tr'],
  ];
  const wideLog = [];
  for (const shot of shots) {
    await openPage(page, shot[0], season.data, shot[1], season);
    await page.waitForSelector(shot[3]);
    for (const size of [[1280, 720, '1280'], [1440, 900, '1440'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.waitForTimeout(250);
      await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 0; });
      await assertNoHorizontalOverflow(page);
      const wide = await wideTables(page);
      wide.forEach(function (row) { wideLog.push(shot[2] + ' ' + size[2] + ' ' + row); });
      await page.screenshot({ path: path.join(OUT2, shot[2] + '-' + size[2] + '.png') });
    }
  }
  fs.writeFileSync(path.join(OUT2, 'wide-tables.txt'), (wideLog.length ? wideLog.join('\n') : 'none') + '\n');
});

test('office home has one vertical scroller', async ({ page }) => {
  await openPage(page, 'franchise-command-center.html', cc());
  await page.setViewportSize({ width: 1280, height: 720 });
  await assertOneVerticalScroll(page);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await assertOneVerticalScroll(page);
});
