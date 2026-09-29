// @ts-check
/** Team › Schedule as four week columns; League › Schedule left as it was. */
const { test, expect } = require('@playwright/test');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-sched-cols';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/team-schedule-columns');

const OPPONENTS = [
  ['York', '#778899'], ['Four-Corners', '#445566'], ['Bentley-Truman', '#7a2230'], ['Morristown', '#2f5d3a'],
  ['Fairview', '#5b3d7a'], ['Kingsport Valley', '#8a6d1f'], ['Ashford', '#264a73'], ['St. Brendan', '#6b2b2b'],
  ['Harbor City', '#1f5f63'], ['Millbrook', '#4d4d4d'], ['Crestwood Prep', '#703a1c'], ['Oak Ridge', '#35602d'],
  ['Northgate', '#3a3f7a'],
];

function opponentFor(week) {
  const i = (week * 5) % OPPONENTS.length;
  return {
    opponent_id: String(i + 1).padStart(24, 'b'),
    opponent_name: OPPONENTS[i][0],
    opponent_primary_color: OPPONENTS[i][1],
    opponent_natl_rank: week % 4 === 0 ? 999 : 3 + ((week * 11) % 90),
    opponent_wins: (week * 3) % 12,
    opponent_losses: (week * 7) % 9,
  };
}

function scheduled(week) {
  return Object.assign({ week: week, site: week % 2 ? 'home' : 'away' }, opponentFor(week));
}

function played(week) {
  const win = (week * 7) % 5 !== 0;
  const a = 58 + ((week * 13) % 24);
  const b = a - 3 - ((week * 5) % 12);
  return Object.assign(scheduled(week), {
    team_score: win ? a : b,
    opp_score: win ? b : a,
    result: win ? 'W' : 'L',
    game_id: 'g-' + week,
  });
}

// Week 9 is a bye in this fixture, so an Open row is covered.
const BYE = 9;

function teamDetail(currentWeek) {
  const results = [];
  const remaining = [];
  for (let week = 1; week <= 26; week++) {
    if (week === BYE) continue;
    if (week < currentWeek) results.push(played(week));
    else remaining.push(scheduled(week));
  }
  results.sort((x, y) => y.week - x.week);
  const tournament_by_phase = currentWeek >= 28
    ? {
      conference: [Object.assign(played(27), {
        week: 27,
        phase: 'conference',
        round_label: 'Quarterfinal',
        kind: 'played',
      })],
      region: [],
      national: [],
    }
    : { conference: [], region: [], national: [] };
  return {
    team_id: TID,
    name: 'Lancaster',
    next_game: remaining[0] || null,
    results: results,
    upcoming: remaining.slice(1),
    tournament_by_phase: tournament_by_phase,
  };
}

function cc(week) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: week,
    rank: 4,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: week >= 27 ? 'post-season' : 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: week, counts: {}, events: [] },
    user_conference: 1,
    user_region: 'A',
    team_record: '15-5',
  };
}

function side(id, name, rank, color) {
  return { team_id: id, name: name, primary_color: color, natl_rank: rank, wins: 3, losses: 1 };
}

function league() {
  const weeks = [];
  for (let week = 1; week <= 34; week++) {
    weeks.push({ week: week, label: week >= 27 ? 'Week ' + week + ': Tourney' : 'Week ' + week, enabled: week <= 21 });
  }
  return {
    week: 21,
    label: 'Week 21',
    current_week: 21,
    user_team_id: TID,
    weeks: weeks,
    games: [
      { away: side('b1', 'York', 80, '#778899'), home: side(TID, 'Lancaster', 4, '#112233'),
        away_score: 60, home_score: 70, status: 'complete', game_id: 'g-box', is_user: true, tournament_context: null },
      { away: side('b2', 'Four-Corners', 21, '#445566'), home: side('b3', 'Morristown', 33, '#2f5d3a'),
        away_score: null, home_score: null, status: 'scheduled', game_id: null, is_user: false, tournament_context: null },
      { away: side('b4', 'Fairview', 12, '#5b3d7a'), home: side('b5', 'Ashford', 55, '#264a73'),
        away_score: 71, home_score: 64, status: 'complete', game_id: 'g-2', is_user: false, tournament_context: null },
    ],
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function open(page, week, tab) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { await route.continue(); return; }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
    if (pathname.startsWith('/franchise/command-center/data')) return fulfillJson(route, cc(week));
    if (pathname.startsWith('/franchise/team-detail')) return fulfillJson(route, teamDetail(week));
    if (pathname.startsWith('/franchise/schedule/week')) return fulfillJson(route, league());
    return fulfillJson(route, {});
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=' + tab);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}

async function park(page) {
  await page.mouse.move(2, 400);
}

async function openTeamSchedule(page, week, size) {
  await page.setViewportSize({ width: size[0], height: size[1] });
  await open(page, week, 'team-schedule-view');
  await expect(page.locator('#team-schedule-view .gob-schcol')).toHaveCount(4);
  await park(page);
}

function grid(page) {
  return page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const cols = [...document.querySelectorAll('#team-schedule-view .gob-schcol')];
    const tops = cols.map((c) => Math.round(c.getBoundingClientRect().top));
    const widths = cols.map((c) => c.getBoundingClientRect().width);
    const heads = cols.map((c) => c.querySelector('thead th').textContent);
    const weeks = cols.map((c) => [...c.querySelectorAll('tbody tr[data-week]')].map((r) => Number(r.dataset.week)));
    const eos = cols.map((c) => [...c.querySelectorAll('tbody tr.is-eos')].map((r) => r.textContent.trim()));
    const lastRow = cols[3].querySelector('tbody tr:last-child').getBoundingClientRect().bottom;
    const tallest = Math.max(...cols.map((c) => c.getBoundingClientRect().bottom));
    return {
      tops, widths, heads, weeks, eos,
      rowTops: [...document.querySelectorAll('#team-schedule-view tr[data-week]')].length,
      bottom: Math.max(lastRow, tallest),
      viewport: window.innerHeight,
      mainScroll: main.scrollHeight - main.clientHeight,
      sideways: main.scrollWidth - main.clientWidth,
      boxHeaders: document.querySelectorAll('#team-schedule-view .gob-box, #team-schedule-view th.box').length,
    };
  });
}

for (const size of [[1280, 720], [1920, 1080]]) {
  test('four equal week columns fit ' + size[0] + ' with nothing below the fold', async ({ page }) => {
    await openTeamSchedule(page, 21, size);
    const g = await grid(page);
    expect(g.heads).toEqual(['Weeks 1–7', 'Weeks 8–14', 'Weeks 15–21', 'Weeks 22–26']);
    expect(g.weeks).toEqual([[1, 2, 3, 4, 5, 6, 7], [8, 9, 10, 11, 12, 13, 14], [15, 16, 17, 18, 19, 20, 21], [22, 23, 24, 25, 26]]);
    expect(g.eos).toEqual([[], [], [], ['Conference Tournaments', 'Region Tournaments', 'National Tournament']]);
    expect(new Set(g.tops).size).toBe(1);
    expect(Math.max(...g.widths) - Math.min(...g.widths)).toBeLessThan(1.5);
    expect(g.bottom).toBeLessThanOrEqual(g.viewport);
    expect(g.mainScroll).toBeLessThanOrEqual(1);
    expect(g.sideways).toBeLessThanOrEqual(0);
    expect(g.boxHeaders).toBe(0);
    await page.screenshot({ path: path.join(OUT, 'team-schedule-w21-' + size[0] + '.png') });
  });

  test('week 27+ keeps the regular season and the tournament rows at ' + size[0], async ({ page }) => {
    await openTeamSchedule(page, 28, size);
    const g = await grid(page);
    expect(g.weeks[3]).toEqual([22, 23, 24, 25, 26, 27]);
    expect(g.eos[3]).toEqual(['Conference Tournaments', 'Region Tournaments', 'National Tournament']);
    expect(g.rowTops).toBe(27);
    await expect(page.locator('#team-schedule-view tr.is-next')).toHaveCount(0);
    await expect(page.locator('#team-schedule-view tr[data-week="26"] .gob-res')).toBeVisible();
    await expect(page.locator('#team-schedule-view tr.is-tourney')).toHaveCount(1);
    await expect(page.locator('#team-schedule-view tr.is-tourney a.gob-res')).toBeVisible();
    expect(g.bottom).toBeLessThanOrEqual(g.viewport);
    await page.screenshot({ path: path.join(OUT, 'team-schedule-w28-' + size[0] + '.png') });
    if (size[0] === 1280) {
      await page.screenshot({ path: path.join(OUT, 'team-schedule-w28-tournament-1280.png') });
    }
  });
}

test('rows: site, logo, rank + name, record line, and the result is the box-score link', async ({ page }) => {
  await openTeamSchedule(page, 21, [1280, 720]);
  const w1 = page.locator('#team-schedule-view tr[data-week="1"]');
  const exp = played(1);
  await expect(w1.locator('td.site')).toHaveText('vs');
  await expect(w1.locator('td.team .gob-id > span').first()).toHaveText('#' + exp.opponent_natl_rank + ' ' + exp.opponent_name);
  await expect(w1.locator('td.team .gob-id .sub')).toHaveText(exp.opponent_wins + '-' + exp.opponent_losses);
  await expect(w1.locator('td.team img, td.team .gob-mark')).toHaveCount(1);
  const res = w1.locator('td.res a.gob-res');
  await expect(res).toHaveText(exp.result + ' ' + exp.team_score + '-' + exp.opp_score);
  await expect(res).toHaveAttribute('href', /\/box-score\.html\?game_id=g-1&mode=franchise&franchise_id=f-e2e-sched-cols&team_id=a{24}$/);
  await expect(res.locator('.gob-wl')).toHaveClass(/\b(up|dn)\b/);
  await expect(page.locator('#team-schedule-view tr[data-week="2"] td.site')).toHaveText('at');
  // Unranked (999) shows the name alone.
  await expect(page.locator('#team-schedule-view tr[data-week="4"] .gob-id > span').first()).toHaveText(opponentFor(4).opponent_name);
  // Bye week.
  await expect(page.locator('#team-schedule-view tr[data-week="9"]')).toHaveClass(/is-open/);
  await expect(page.locator('#team-schedule-view tr[data-week="9"] td.team')).toHaveText('Open');
  // Future games: empty result, no time.
  for (const week of [21, 22, 26]) {
    await expect(page.locator('#team-schedule-view tr[data-week="' + week + '"] td.res')).toHaveText('');
  }
});

test('the current week is a quiet emphasis, not navy, green or orange', async ({ page }) => {
  await openTeamSchedule(page, 21, [1280, 720]);
  const next = page.locator('#team-schedule-view tr.is-next');
  await expect(next).toHaveCount(1);
  await expect(next).toHaveAttribute('data-week', '21');
  const look = await page.evaluate(() => {
    const parse = (c) => (c.match(/[\d.]+/g) || []).map(Number);
    const cells = (sel) => [...document.querySelectorAll(sel + ' td')].map((td) => getComputedStyle(td));
    const next = cells('#team-schedule-view tr.is-next');
    const plain = cells('#team-schedule-view tr[data-week="20"]');
    const neutral = (c) => { const [r, g, b] = parse(c); return Math.max(r, g, b) - Math.min(r, g, b) <= 2; };
    return {
      bgNeutral: next.every((s) => neutral(s.backgroundColor)),
      inkNeutral: next.every((s) => neutral(s.color)),
      marker: next[0].boxShadow,
      nextName: getComputedStyle(document.querySelector('#team-schedule-view tr.is-next .gob-id > span')).color,
      plainName: getComputedStyle(document.querySelector('#team-schedule-view tr[data-week="20"] .gob-id > span')).color,
      plainWk: plain[0].color,
      nextWk: next[0].color,
    };
  });
  expect(look.bgNeutral).toBe(true);
  expect(look.inkNeutral).toBe(true);
  expect(look.marker).not.toBe('none');
  expect(look.nextWk).not.toBe(look.plainWk);
  expect(look.nextName).toBe('rgb(255, 255, 255)');
  expect(look.plainName).not.toBe(look.nextName);
});

test('result and opponent links are tabbable with a visible focus ring; opponent pushes team-view', async ({ page }) => {
  await openTeamSchedule(page, 21, [1280, 720]);
  const links = await page.evaluate(() => [...document.querySelectorAll('#team-schedule-view a')].map((a) => ({
    cls: a.className, tab: a.tabIndex,
  })));
  expect(links.filter((l) => l.cls === 'gob-res').length).toBe(19);
  expect(links.filter((l) => l.cls === 'gob-team').length).toBe(25);
  expect(links.every((l) => l.tab === 0)).toBe(true);

  const res = page.locator('#team-schedule-view tr[data-week="1"] a.gob-res');
  await page.locator('#team-schedule-view tr[data-week="1"] a.gob-team').focus();
  await page.keyboard.press('Tab');
  await expect(res).toBeFocused();
  const ring = await res.evaluate((a) => { const s = getComputedStyle(a); return s.outlineStyle + ' ' + s.outlineWidth; });
  expect(ring).toBe('solid 2px');
  await page.screenshot({ path: path.join(OUT, 'focus-result-1280.png'), clip: { x: 60, y: 120, width: 420, height: 200 } });
  await page.keyboard.press('Shift+Tab');
  const opp = page.locator('#team-schedule-view tr[data-week="1"] a.gob-team');
  await expect(opp).toBeFocused();
  const oppRing = await opp.evaluate((a) => { const s = getComputedStyle(a); return s.outlineStyle + ' ' + s.outlineWidth; });
  expect(oppRing).toBe('solid 2px');
  await page.screenshot({ path: path.join(OUT, 'focus-opponent-1280.png'), clip: { x: 60, y: 120, width: 420, height: 200 } });

  await res.hover();
  const hover = await res.evaluate((a) => getComputedStyle(a).backgroundColor);
  expect(hover).not.toBe('rgba(0, 0, 0, 0)');

  await opp.focus();
  await page.keyboard.press('Enter');
  await page.waitForURL(/tab=team-view/);
  expect(page.url()).toContain('return_tab=team-schedule-view');
});

test('below 1100px the columns drop to two', async ({ page }) => {
  await openTeamSchedule(page, 21, [1024, 720]);
  const g = await grid(page);
  expect(g.tops[0]).toBe(g.tops[1]);
  expect(g.tops[2]).toBeGreaterThan(g.tops[0]);
  expect(g.tops[2]).toBe(g.tops[3]);
  expect(g.sideways).toBeLessThanOrEqual(0);
});

for (const size of [[1280, 720], [1920, 1080]]) {
  test('league schedule reference at ' + size[0], async ({ page }) => {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await open(page, 21, 'league-schedule-view');
    await expect(page.locator('#league-schedule-view .gob-game').first()).toBeVisible();
    await park(page);
    const name = process.env.LEAGUE_SHOT || 'league-schedule-' + size[0] + '.png';
    await page.screenshot({ path: path.join(OUT, name.replace('{w}', String(size[0]))) });
    if (process.env.LEAGUE_STYLES) {
      // Computed style of every league-view node, for a before/after CSS comparison.
      const styles = await page.evaluate(() => {
        const props = ['color', 'background-color', 'font', 'letter-spacing', 'padding', 'margin', 'width', 'height',
          'border', 'text-align', 'text-decoration', 'box-shadow', 'outline', 'display', 'position', 'top', 'white-space'];
        return [...document.querySelectorAll('#league-schedule-view, #league-schedule-view *')].map((el, i) => {
          const s = getComputedStyle(el);
          return [i, el.tagName, String(el.className)].concat(props.map((p) => s.getPropertyValue(p)));
        });
      });
      require('fs').writeFileSync(process.env.LEAGUE_STYLES.replace('{w}', String(size[0])), JSON.stringify(styles));
    }
  });
}
