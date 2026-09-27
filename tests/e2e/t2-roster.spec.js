const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-t2';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/t2-roster');

function cc(week) {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: week,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: week, counts: {}, events: [] },
    user_conference: 1,
    user_region: 'A',
    team_record: '10-2',
    office_digest: {
      state: 'season',
      todos: [],
      result: null,
      next_game: null,
      team_snapshot: null,
      conference_standings: null,
      recruiting_wire: { events: [] },
      what_moved: {
        national_rank: { now: 18, prev: 18, delta: 0 },
        conference_standing: { now: 3, prev: 3, delta: 0 },
        record: { wins: 10, losses: 2 },
        streak: null,
        attribute_changes: [
          { player_id: 'p0', name: 'Ada Keeper', attribute: 'BH', from: 3, to: 5 },
          { player_id: 'p0', name: 'Ada Keeper', attribute: 'ND', from: 8, to: 7 },
          { player_id: 'p1', name: 'Cal Ives', attribute: 'ID', from: 2, to: 4 },
          { player_id: 'p2', name: 'Dee Ortiz', attribute: 'OD', from: 5, to: 6 },
          { player_id: 'p3', name: 'Eve Park', attribute: 'PS', from: 6, to: 8 },
          { player_id: 'p3', name: 'Eve Park', attribute: 'AG', from: 4, to: 3 },
        ],
      },
    },
  };
}

function roster(week) {
  const players = [];
  for (let i = 0; i < 30; i += 1) {
    const starter = i < 5;
    players.push({
      _id: 'p' + i,
      name: i === 0 ? (week === 1 ? 'Ada Keeper' : 'Ada Advanced') : ('Player ' + i),
      year: 'JR',
      height: 76,
      weight: 210,
      position: 'SG',
      rt: i === 0 ? 85 : 70,
      potential_rt_ratcheted: i === 0 ? 96 : 80,
      starter: starter,
      lineup_order: starter ? i : null,
      attributes: i === 0
        ? { SC: 30, SH: 50, ID: 70, OD: 90, PS: 120, BH: 40, RB: 55, AG: 80, ST: 65, ND: 75, IQ: 95, FT: 45 }
        : { SC: 60, SH: 60, ID: 60, OD: 60, PS: 60, BH: 60, RB: 60, AG: 60, ST: 60, ND: 60, IQ: 60, FT: 60 },
      resolved_training_focus: 'offensive',
      training_focus: 'offensive',
    });
  }
  return {
    team: 'Lancaster',
    is_user_team: true,
    players: players,
    training_squad: [{
      name: 'No Portrait',
      year: 'FR',
      height: 74,
      weight: 180,
      position: 'SF',
      rt: 72,
      potential_rt_ratcheted: 88,
      starter: false,
      lineup_order: null,
      attributes: { SC: 40 },
    }],
    practice_squad_recruits: [],
    projected_starting_five: players.slice(0, 5).map(function (player) {
      return { player_id: player._id };
    }),
  };
}

function teamData() {
  return {
    team_attributes: { team_chemistry: 18 },
    measures: [
      {
        family: 'character', family_label: 'Character', key: 'team_chemistry', label: 'Chemistry',
        value: 18, scale_max: 25, meter_pct: 72, delta: 1, description: null,
        direction: 'higher_better', rank: 12, rank_of: 128, percentile: 80, rank_delta: null, tied: false,
      },
      {
        family: 'character', family_label: 'Character', key: 'fight', label: 'Fight',
        value: 3, scale_max: null, meter_pct: null, delta: 0, description: null,
        direction: 'higher_better', rank: 34, rank_of: 128, percentile: 70, rank_delta: 2, tied: true,
      },
      {
        family: 'floor', family_label: 'On the floor', key: 'shot_threshold', label: 'Shooting',
        value: 90, scale_max: null, meter_pct: null, delta: null, description: null,
        direction: 'lower_better', rank: 8, rank_of: 128, percentile: 94, rank_delta: -1, tied: false,
      },
      {
        family: 'character', family_label: 'Character', key: 'discipline', label: 'Discipline',
        value: null, scale_max: null, meter_pct: null, delta: null, description: null,
        direction: 'higher_better', rank: null, rank_of: null, percentile: null, rank_delta: 0, tied: false,
      },
    ],
    updated_after_week: 3,
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, state) {
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
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (request.method() === 'POST' && pathname.indexOf('/franchise/complete-week') !== -1) {
      state.week += 1;
      await fulfillJson(route, { ok: true, week: state.week });
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
      await fulfillJson(route, cc(state.week));
      return;
    }
    if (pathname.startsWith('/franchise/team-data')) {
      await fulfillJson(route, teamData());
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, roster(state.week));
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page, state, search) {
  await stubAuth(page);
  await installApi(page, state);
  const qs = search || ('?franchise_id=' + FID + '&team_id=' + TID);
  await page.goto('/franchise-command-center.html' + qs);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
  await page.evaluate(() => {
    sessionStorage.removeItem('gob-view-roster-scope');
    sessionStorage.removeItem('gob-view-roster-order');
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

async function assertNoMainOverflow(page) {
  const overflow = await page.evaluate(() => {
    const main = document.querySelector('html.gob-shell .main');
    const se = document.scrollingElement;
    return {
      main: main.scrollWidth - main.clientWidth,
      page: se.scrollWidth - se.clientWidth,
    };
  });
  expect(overflow.main).toBeLessThanOrEqual(1);
  expect(overflow.page).toBeLessThanOrEqual(1);
  await assertOneVerticalScroll(page);
}

async function park(page) {
  await page.mouse.move(480, 240);
}

test.beforeAll(() => {
  fs.mkdirSync(OUT, { recursive: true });
});

test('roster and team attributes navigate, restore scroll, and redirect', async ({ page }) => {
  const state = { week: 1 };
  await openFcc(page, state);
  await mouseClick(page, '[data-gob-section="team"]');
  await page.waitForSelector('#roster-view .gob-tbl tbody tr');
  await expect(page.locator('#roster-view.tab-content.active')).toBeVisible();
  await expect(stab(page, 'Roster')).toHaveClass(/on/);
  await expect(page.locator('#gob-subtabs .stab', { hasText: 'Development' })).toHaveCount(0);
  const teamIdx = await page.evaluate(() => history.state && history.state.gobIdx);
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 420; });
  const saved = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  expect(saved).toBeGreaterThan(200);
  await mouseClick(page, stab(page, 'Player Stats'));
  await expect(page.locator('#player-stats-tab.tab-content.active')).toBeVisible();
  expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(teamIdx);
  await page.goBack();
  await expect(page.locator('#home-tab.tab-content.active')).toBeVisible();
  await page.goForward();
  await page.waitForURL(/tab=player-stats-tab/);
  await page.goBack();
  await mouseClick(page, '[data-gob-section="team"]');
  await page.waitForSelector('#roster-view a.gob-player');
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 360; });
  const scrolled = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  await page.locator('#roster-view a.gob-player').first().evaluate((anchor) => anchor.click());
  await page.waitForURL(/tab=player-view/);
  const order = await page.evaluate(() => JSON.parse(sessionStorage.getItem('gob-view-roster-order') || '[]'));
  expect(order[0]).toBe('p0');
  expect(order.length).toBe(30);
  await page.goBack();
  await page.waitForURL(/tab=roster-view/);
  await page.waitForFunction((top) => {
    const main = document.querySelector('html.gob-shell .main');
    return main && Math.abs(main.scrollTop - top) <= 2;
  }, scrolled, { timeout: 8000 });

  await page.goto('/team-roster-view.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&return_url=' + encodeURIComponent('/rankings.html?franchise_id=' + FID + '&team_id=' + TID));
  await page.waitForURL(/tab=roster-view/);
  const landed = new URL(page.url());
  expect(landed.searchParams.get('franchise_id')).toBe(FID);
  expect(landed.searchParams.get('team_id')).toBe(TID);
  expect(landed.searchParams.get('return_url')).toContain('/rankings.html');
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-tab');
  await expect(page.locator('#roster-view.tab-content.active')).toBeVisible();
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-stats-tab');
  await expect(page.locator('#team-attributes-view.tab-content.active')).toBeVisible();
  await expect(page.locator('#team-attributes-view')).toContainText('Chemistry');
  await expect(page.locator('#team-attributes-view')).toContainText('/25');
  await expect(page.locator('#team-attributes-view')).toContainText('Updated after Week 3');
});

test('first open shows a skeleton and a failed roster retries', async ({ page }) => {
  const state = { week: 1 };
  let release;
  const gate = new Promise(function (resolve) { release = resolve; });
  await stubAuth(page);
  await installApi(page, state);
  await page.route('**/js/shared/views/rosterView.js', async (route) => {
    if (route.request().url().indexOf('retry=') !== -1) {
      await route.fallback();
      return;
    }
    await gate;
    await route.fallback();
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await expect(page.locator('#roster-view .gob-view-skel')).toBeVisible();
  await expect(page.locator('#roster-view .spinner, #roster-view [class*="spinner"]')).toHaveCount(0);
  release();
  await page.waitForSelector('#roster-view .gob-tbl tbody tr');
  await page.unroute('**/js/shared/views/rosterView.js');

  let fail = true;
  await page.route('**/roster/**', async (route) => {
    if (fail) {
      await route.abort();
      return;
    }
    await route.fallback();
  });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await expect(page.locator('#roster-view .gob-view-error')).toBeVisible();
  await expect(page.locator('#roster-view .gob-view-retry')).toBeVisible();
  fail = false;
  await mouseClick(page, '#roster-view .gob-view-retry');
  await page.waitForSelector('#roster-view .gob-tbl tbody tr');
});

test('a week advance refreshes the roster', async ({ page }) => {
  const state = { week: 1 };
  await openFcc(page, state);
  await mouseClick(page, '[data-gob-section="team"]');
  await page.waitForSelector('#roster-view .gob-tbl');
  await expect(page.locator('#roster-view')).toContainText('Ada Keeper');
  await page.evaluate(async (fid) => {
    const res = await fetch('/franchise/complete-week', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ franchise_id: fid }),
    });
    if (!res.ok) throw new Error('advance failed');
  }, FID);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await page.waitForSelector('#roster-view .gob-tbl');
  await expect(page.locator('#roster-view')).toContainText('Ada Advanced');
  await expect(page.locator('#roster-view')).not.toContainText('Ada Keeper');
});

test('the grid, tiles, lineup, and practice squad match the locked rules', async ({ page }) => {
  const state = { week: 1 };
  await openFcc(page, state);
  for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.evaluate(() => sessionStorage.removeItem('gob-view-roster-scope'));
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
    await page.waitForSelector('#roster-view .gob-tbl tbody tr');
    await assertNoMainOverflow(page);
    const bands = await page.locator('#roster-view tr.gob-groups th').evaluateAll((nodes) => nodes.map((node) => ({
      text: node.textContent.trim(),
      shade: node.classList.contains('gshade'),
    })));
    const named = bands.filter((band) => band.text);
    expect(named.map((band) => band.text)).toEqual(['Offense', 'Defense', 'Skills', 'Grit', 'Body', 'Mind']);
    expect(named.map((band) => band.shade)).toEqual([false, true, false, true, false, true]);
    await expect(page.locator('#gob-subtabs [data-value="varsity"]')).toContainText('30');
    await expect(page.locator('#gob-subtabs [data-value="practice"]')).toContainText('1');
    await expect(page.locator('#roster-view tr.gob-sep').nth(0)).toContainText('Starters');
    await expect(page.locator('#roster-view tr.gob-sep').nth(1)).toContainText('Bench');
    await expect(page.locator('#roster-view .rtl').first()).toContainText('A');
    await expect(page.locator('#roster-view .rtl').first()).toContainText('A+');
    const tiles = await page.locator('#roster-view tbody tr:not(.gob-sep):not(.gob-rep)').first().locator('.attr-tile').evaluateAll((nodes) => nodes.slice(0, 5).map((node) => ({
      value: node.querySelector('s').textContent,
      cls: node.className,
      fill: getComputedStyle(node).backgroundColor,
      ring: getComputedStyle(node).boxShadow,
    })));
    expect(tiles.map((tile) => tile.value)).toEqual(['3', '5', '7', '9', '12']);
    expect(tiles[0].cls).toContain('is-lo');
    expect(tiles[1].cls).toContain('is-mid');
    expect(tiles[2].cls).toContain('is-hi');
    expect(tiles[3].cls).toContain('is-elite');
    expect(tiles[4].cls).toContain('is-elite');
    expect(tiles[0].fill).toBe('rgba(0, 0, 0, 0)');
    expect(tiles[1].fill).not.toBe('rgba(0, 0, 0, 0)');
    expect(tiles[3].ring).not.toBe('none');
    const elite = await page.locator('#roster-view .attr-tile.is-elite s').first().evaluate((el) => {
      function parse(color) {
        const match = String(color).match(/rgba?\(([^)]+)\)/);
        if (!match) return [0, 0, 0, 1];
        const parts = match[1].split(',').map((part) => parseFloat(part));
        return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1];
      }
      function lin(channel) {
        const s = channel / 255;
        return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
      }
      function lum(rgb) {
        return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2]);
      }
      function over(top, bottom) {
        const alpha = top[3] + bottom[3] * (1 - top[3]);
        const mix = (index) => (top[index] * top[3] + bottom[index] * bottom[3] * (1 - top[3])) / (alpha || 1);
        return [mix(0), mix(1), mix(2), alpha];
      }
      let bg = [11, 13, 20, 1];
      const stack = [];
      for (let node = el.parentElement; node; node = node.parentElement) stack.push(node);
      stack.reverse().forEach((node) => {
        const layer = parse(getComputedStyle(node).backgroundColor);
        if (layer[3] > 0) bg = over(layer, bg);
      });
      const fg = parse(getComputedStyle(el).color);
      const hi = Math.max(lum(fg), lum(bg));
      const lo = Math.min(lum(fg), lum(bg));
      const cs = getComputedStyle(el);
      return {
        color: cs.color,
        ratio: (hi + 0.05) / (lo + 0.05),
        size: parseFloat(cs.fontSize),
        weight: cs.fontWeight,
        family: cs.fontFamily,
      };
    });
    expect(elite.color).toBe('rgb(107, 164, 224)');
    expect(elite.ratio).toBeGreaterThanOrEqual(4.5);
    expect(elite.size).toBe(size[0] === 1280 ? 20 : 23.5);
    expect(Number(elite.weight)).toBeGreaterThanOrEqual(700);
    expect(elite.family).toContain('Bebas');
    const sepAlign = await page.locator('#roster-view tr.gob-sep td').first().evaluate((td) => getComputedStyle(td).textAlign);
    expect(sepAlign).toBe('left');
    const tip = await page.locator('#roster-view thead th[data-sort="SC"]').getAttribute('data-tooltip');
    expect(tip).toContain('Scoring');
    expect(tip).toContain("player's ability to put the ball in the hoop");
    await expect(page.locator('#roster-view tbody tr.gob-rep')).toHaveCount(1);
    await park(page);
    await page.screenshot({ path: path.join(OUT, 'roster-varsity-' + size[2] + '.png') });
    await mouseClick(page, '#gob-subtabs [data-value="practice"]');
    await expect(page.locator('#roster-view')).toContainText('No Portrait');
    const letters = await page.locator('#roster-view .av').first().innerText();
    expect(letters.trim()).toBe('NP');
    await expect(page.locator('#roster-view .av img')).toHaveCount(0);
    await park(page);
    await page.screenshot({ path: path.join(OUT, 'roster-practice-' + size[2] + '.png') });
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-attributes-view');
    await page.waitForSelector('#team-attributes-view .gob-mrow');
    await assertNoMainOverflow(page);
    const chemistry = page.locator('#team-attributes-view .gob-mrow', { hasText: 'Chemistry' });
    const fight = page.locator('#team-attributes-view .gob-mrow', { hasText: 'Fight' });
    const shooting = page.locator('#team-attributes-view .gob-mrow', { hasText: 'Shooting' });
    const discipline = page.locator('#team-attributes-view .gob-mrow', { hasText: 'Discipline' });
    await expect(chemistry.locator('.val')).toContainText('18');
    await expect(chemistry.locator('.val')).toContainText('/25');
    await expect(chemistry.locator('.place')).toHaveText('12th of 128');
    await expect(chemistry.locator('.gob-meter i')).toHaveAttribute('style', /--w:\s*80%/);
    await expect(chemistry.locator('.chip')).toHaveCount(0);
    await expect(fight.locator('.val')).toHaveCount(0);
    await expect(fight.locator('.place')).toHaveText('34th of 128');
    await expect(page.locator('#team-attributes-view')).not.toContainText('T-');
    await expect(fight.locator('.chip.up')).toHaveText('▲2');
    await expect(shooting.locator('.val')).toHaveCount(0);
    await expect(shooting.locator('.place')).toHaveText('8th of 128');
    await expect(shooting.locator('.chip.down')).toHaveText('▼1');
    await expect(discipline.locator('.place')).toHaveText('—');
    await expect(discipline.locator('.gob-meter')).toHaveClass(/is-empty/);
    await expect(discipline.locator('.chip')).toHaveCount(0);
    await expect(page.locator('#team-attributes-view .gob-meter')).toHaveCount(4);
    await expect(page.locator('#team-attributes-view')).not.toContainText('/100');
    await park(page);
    await page.screenshot({ path: path.join(OUT, 'team-attributes-' + size[2] + '.png') });
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=home-tab');
    await page.waitForSelector('#office-root .attr-tile');
    const chip = await page.locator('#office-root .attr-chip').first().locator('.attr-tile');
    await expect(chip).toHaveClass(/is-mid/);
    await expect(chip.locator('s')).toHaveText('5');
    const chipType = await page.locator('#office-root .attr-chip').first().evaluate((node) => {
      const code = getComputedStyle(node.querySelector('.attr-code'));
      const digit = getComputedStyle(node.querySelector('.attr-tile s'));
      return {
        code: parseFloat(code.fontSize),
        digit: parseFloat(digit.fontSize),
        weight: digit.fontWeight,
      };
    });
    expect(chipType.digit).toBeGreaterThanOrEqual(chipType.code);
    expect(Number(chipType.weight)).toBeGreaterThanOrEqual(700);
    await park(page);
    await page.screenshot({ path: path.join(OUT, 'office-chips-' + size[2] + '.png') });
  }
});
