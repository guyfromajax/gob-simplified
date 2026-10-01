const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * Player rows are one height (44px at 1280) whatever the avatar holds: a headshot, a
 * monogram, or a headshot that fails late. Before `a.gob-team.gob-player { vertical-align: middle }`
 * an image-only avatar lifted the line by 2px, so a roster mixed 46px and 44px rows and a
 * row changed height when its headshot failed.
 *
 * PLAYER_ROW_SHOTS=before writes before-*.png and skips the guards: run it on develop for
 * the BEFORE set. The default run writes after-*.png and asserts.
 */
test.describe.configure({ timeout: 120000 });

const BEFORE = process.env.PLAYER_ROW_SHOTS === 'before';
const OUT = path.join(__dirname, '../../reports/player-row-44');
const FID = 'f-e2e-player-row';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const PLAYERS_DIR = path.join(__dirname, '../../FrontEnd/static/images/players');
// Any real headshot on disk; the guard only needs an image that loads.
const HEADSHOT = fs.readFileSync(path.join(PLAYERS_DIR, fs.readdirSync(PLAYERS_DIR).filter((f) => /^[0-9a-f-]{36}\.png$/.test(f)).sort()[0]));
const LATE_MS = 600;

// p1, p3, p5: headshot loads. p2, p4: 404 at once. p6: 404 after LATE_MS.
const SQUAD = [
  ['p1', 'Ada Ace', 'PG', 'SR', 4],
  ['p2', 'Bo Low', 'SG', 'JR', 11],
  ['p3', 'Cy Zero', 'SF', 'SO', 23],
  ['p4', 'Dee Marsh', 'PF', 'FR', 32],
  ['p5', 'Eli Stone', 'C', 'SR', 50],
  ['p6', 'Finn Late', 'SG', 'JR', 7],
];

function cc() {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week: 8, rank: 14, season: 1,
    current_season: 1, training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: 8, counts: {}, events: [] },
    user_conference: 1, user_region: 'A', team_record: '10-2',
  };
}

function counting(gp, totals) {
  const keys = ['MIN', 'PTS', 'FGM', 'FGA', '3PTM', '3PTA', 'FTM', 'FTA', 'OREB', 'DREB', 'REB', 'AST', 'TO', 'STL', 'BLK', 'F'];
  const per = { GP: gp };
  const sum = { GP: gp };
  keys.forEach(function (key) {
    const total = totals[key] == null ? 0 : totals[key];
    sum[key] = total;
    per[key] = gp > 0 ? total / gp : null;
  });
  return { per_game: per, totals: sum };
}


function rosterBody() {
  return {
    team: 'Lancaster',
    is_user_team: true,
    players: SQUAD.map(function (p, i) {
      return {
        _id: p[0], name: p[1], position: p[2], year: p[3], jersey: p[4], height: 72 + i, weight: 180 + i * 6,
        rt: 45 + i * 9, starter: i < 5, lineup_order: i,
        attributes: { SC: 60, SH: 55, ID: 50, OD: 62, PS: 48, BH: 57, RB: 44, AG: 66, ST: 52, ND: 58, IQ: 61, FT: 70 },
      };
    }),
    training_squad: [],
    practice_squad_recruits: [],
  };
}

function statsBody() {
  return {
    team_id: TID,
    players: SQUAD.map(function (p, i) {
      const line = counting(2, { MIN: 40 - i * 4, PTS: 22 - i * 3, FGM: 6, FGA: 12, FTM: 2, FTA: 4, OREB: 1, DREB: 4, REB: 5, AST: 3, TO: 1, STL: 1, BLK: 0, F: 2 });
      line.rates = { fg_pct: 50, tp_pct: null, ft_pct: 50, def_pct: 25 };
      return Object.assign({ player_id: p[0], name: p[1], position: p[2], year: p[3], jersey: p[4] }, line);
    }),
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}


async function installApi(page) {
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/') || pathname.startsWith('/recruit/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
    if (pathname.startsWith('/franchise/command-center/data')) return fulfillJson(route, cc());
    if (pathname.startsWith('/roster/')) return fulfillJson(route, rosterBody());
    if (pathname.startsWith('/franchise/player-stats')) return fulfillJson(route, statsBody());
    return fulfillJson(route, {});
  });
  // Registered after the catch-all, so it answers the headshot requests.
  await page.route(/\/images\/players\/(p[1-6])\.png/, async (route) => {
    const id = route.request().url().match(/\/(p[1-6])\.png/)[1];
    if (id === 'p1' || id === 'p3' || id === 'p5') {
      await route.fulfill({ status: 200, contentType: 'image/png', body: HEADSHOT });
      return;
    }
    if (id === 'p6') await new Promise((resolve) => setTimeout(resolve, LATE_MS));
    await route.fulfill({ status: 404, body: '' });
  });
}

async function openFcc(page, search) {
  await stubAuth(page);
  const qs = search || ('?franchise_id=' + FID + '&team_id=' + TID);
  await page.goto('/franchise-command-center.html' + qs);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}


// Records, every frame from first paint, the row heights of each view and what the
// late player's avatar holds. Only changes are stored.
async function installSampler(page) {
  await page.addInitScript(() => {
    window.__rows = { 'roster-view': [], 'player-stats-view': [] };
    const tick = () => {
      Object.keys(window.__rows).forEach((view) => {
        const rows = Array.from(document.querySelectorAll('#' + view + ' tbody tr')).filter((tr) => tr.querySelector('a.gob-player') && tr.getBoundingClientRect().height > 0);
        if (!rows.length) return;
        const late = rows.find((tr) => /Finn Late/.test(tr.textContent));
        const snap = {
          heights: rows.map((tr) => Math.round(tr.getBoundingClientRect().height * 100) / 100).join(','),
          late: late ? (late.querySelector('.av img') ? 'img' : 'monogram') : 'absent',
        };
        const log = window.__rows[view];
        const last = log[log.length - 1];
        if (!last || last.heights !== snap.heights || last.late !== snap.late) log.push(snap);
      });
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

async function avatarsSettled(page, view) {
  await page.waitForFunction((id) => {
    const imgs = Array.from(document.querySelectorAll('#' + id + ' .av img'));
    return imgs.every((img) => img.complete && img.naturalWidth > 0);
  }, view);
}

async function rowsOf(page, view) {
  return page.evaluate((id) => {
    return Array.from(document.querySelectorAll('#' + id + ' tbody tr')).filter((tr) => tr.querySelector('a.gob-player')).map((tr) => ({
      name: (tr.querySelector('a.gob-player').textContent || '').trim().slice(0, 24),
      height: Math.round(tr.getBoundingClientRect().height * 100) / 100,
      avatar: tr.querySelector('.av img') ? 'img' : 'monogram',
    }));
  }, view);
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.querySelector('html.gob-shell .main');
    if (main) main.scrollTop = 0;
  });
  await page.mouse.move(700, 715);
  await page.waitForTimeout(250);
  await page.screenshot({ path: path.join(OUT, (BEFORE ? 'before-' : 'after-') + name), animations: 'disabled' });
}

async function openRoster(page) {
  await page.setViewportSize({ width: 1280, height: 720 });
  await installSampler(page);
  await installApi(page);
  await openFcc(page, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await page.waitForSelector('#roster-view a.gob-player');
}

async function openStats(page) {
  await page.mouse.move(980, 420);
  await page.locator('#gob-subtabs [data-tab="player-stats-view"]').evaluate((el) => el.click());
  await page.waitForSelector('#player-stats-view a.gob-player');
}

function expectOneHeight(rows, where) {
  expect(rows.length, where).toBe(6);
  expect(rows.filter((r) => r.avatar === 'img').length, where + ': some rows hold a headshot').toBe(3);
  expect(rows.filter((r) => r.avatar === 'monogram').length, where + ': some rows hold a monogram').toBe(3);
  for (const row of rows) expect(row.height, where + ' ' + row.name + ' (' + row.avatar + ')').toBe(44);
}

test.describe('player rows are one height', () => {
  test('Team > Roster: headshot rows and monogram rows are all 44px', async ({ page }, testInfo) => {
    await openRoster(page);
    await page.waitForTimeout(LATE_MS + 300);
    await avatarsSettled(page, 'roster-view');
    if (testInfo.repeatEachIndex === 0) await shot(page, 'roster-1280.png');
    if (BEFORE) return;
    expectOneHeight(await rowsOf(page, 'roster-view'), 'roster');
  });

  test('Team > Player Stats: headshot rows and monogram rows are all 44px', async ({ page }, testInfo) => {
    await openRoster(page);
    await openStats(page);
    await page.waitForTimeout(LATE_MS + 300);
    await avatarsSettled(page, 'player-stats-view');
    if (testInfo.repeatEachIndex === 0) await shot(page, 'player-stats-1280.png');
    if (BEFORE) return;
    expectOneHeight(await rowsOf(page, 'player-stats-view'), 'player stats');
    const align = await page.evaluate(() => {
      const plain = document.createElement('a');
      plain.className = 'gob-player';
      document.querySelector('#player-stats-view td').appendChild(plain);
      const out = {
        avatarLink: getComputedStyle(document.querySelector('#player-stats-view a.gob-team.gob-player')).verticalAlign,
        textLink: getComputedStyle(plain).verticalAlign,
      };
      plain.remove();
      return out;
    });
    expect(align.avatarLink).toBe('middle');
    // A text-only player link (Leaders, Awards) is not touched.
    expect(align.textLink).toBe('baseline');
  });

  test('a headshot that fails late does not change any row height after first paint', async ({ page }) => {
    test.skip(BEFORE, 'guards only');
    await openRoster(page);
    await openStats(page);
    // Until the late 404 has landed and the avatar is the monogram.
    await page.waitForFunction(() => {
      const row = Array.from(document.querySelectorAll('#player-stats-view tbody tr')).find((tr) => /Finn Late/.test(tr.textContent));
      return row && !row.querySelector('.av img');
    }, null, { timeout: 15000 });
    await page.waitForTimeout(400);
    const log = await page.evaluate(() => window.__rows);
    const stats = log['player-stats-view'];
    // The sampler saw the late row with its image in flight and after the fallback.
    expect(stats.map((s) => s.late), JSON.stringify(stats)).toEqual(expect.arrayContaining(['img', 'monogram']));
    for (const view of ['roster-view', 'player-stats-view']) {
      const heights = Array.from(new Set(log[view].map((s) => s.heights)));
      expect(heights, view + ' ' + JSON.stringify(log[view])).toEqual(['44,44,44,44,44,44']);
    }
  });
});
