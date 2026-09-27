const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');
const { assertOneVerticalScroll } = require('./helpers/oneVerticalScroll');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-t3';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 3,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 3, counts: {}, events: [] },
    user_conference: 1,
    user_region: 'A',
    team_record: '10-2',
  };
}

function rosterBody(focus) {
  const players = [];
  for (let i = 0; i < 12; i += 1) {
    players.push({
      _id: 'p' + i,
      name: i === 0 ? 'Cedric Buckles' : (i === 1 ? 'Montgomery Worthington-Blake' : ('Player ' + i)),
      year: 'JR',
      height: 76,
      weight: 210,
      position: 'SG',
      rt: 80,
      potential_rt_ratcheted: 90,
      starter: i < 5,
      lineup_order: i < 5 ? i : null,
      attributes: { SC: 70, SH: 60, ID: 50, OD: 40, PS: 80, BH: 55, RB: 65, AG: 75, ST: 85, ND: 45, IQ: 90, FT: 35 },
      resolved_training_focus: i === 0 ? (focus || 'offensive') : 'standard',
      training_focus: i === 0 ? (focus || 'offensive') : 'standard',
    });
  }
  return { team: 'Lancaster', is_user_team: true, players: players, training_squad: [], practice_squad_recruits: [] };
}

function groups() {
  return [
    { id: 'offense', label: 'Offense', attrs: [{ attr: 'SC', raw: 70, display: 7 }, { attr: 'SH', raw: 60, display: 6 }] },
    { id: 'defense', label: 'Defense', attrs: [{ attr: 'ID', raw: 50, display: 5 }, { attr: 'OD', raw: 40, display: 4 }] },
    { id: 'mind', label: 'Mind', attrs: [{ attr: 'IQ', raw: 99, display: 12 }] },
  ];
}

function playerDetail(id, opts) {
  const mine = id === 'p0' || (opts && opts.user);
  const detail = {
    player_id: id,
    name: id === 'p0' ? 'Cedric Buckles' : (id === 'cpu' ? 'Riley Quinn' : ('Player ' + id.replace('p', ''))),
    team_id: mine ? TID : OPP,
    team_name: mine ? 'Lancaster' : 'York',
    team_primary_color: mine ? '#27408E' : null,
    position: 'SG',
    year: 'JR',
    height_in: 76,
    weight: 210,
    jersey: '12',
    is_user_team: !!mine,
    rt: 80,
    potential: 92,
    attributes: groups(),
    season: { gp: 10, min_per_game: 28.2, pts_per_game: 14.2, reb_per_game: 4, ast_per_game: 3.1, stl_per_game: 1, blk_per_game: 0.4, fg_pct: 48.2, tp_pct: 36.5, ft_pct: 80, def_pct: null },
    career: { gp: 40, min_per_game: 22, pts_per_game: 11, reb_per_game: 3.5, ast_per_game: 2, stl_per_game: 0.8, blk_per_game: 0.2, fg_pct: 45, tp_pct: 33, ft_pct: 78, def_pct: 12.5 },
    recent_changes: [
      { week: 3, session_type: 'in-season', changes: [{ attr: 'SC', from: 4, to: 5 }] },
      { week: 2, session_type: 'in-season', changes: [{ attr: 'ZZ', delta: 1 }] },
    ],
    development: {
      focus: opts && opts.focus ? opts.focus : 'offensive',
      focus_label: opts && opts.focus === 'rebounding' ? 'Rebounding' : 'Offensive',
      emphasises: ['SC', 'SH', 'ID'],
      editable: !!mine,
    },
  };
  if (opts && opts.nullRates) {
    detail.season = Object.assign({}, detail.season, { tp_pct: null });
    detail.career = Object.assign({}, detail.career, { tp_pct: null, ft_pct: 0 });
  }
  return detail;
}

function teamDetail(id) {
  const mine = id === TID;
  return {
    team_id: id,
    name: mine ? 'Lancaster' : 'York',
    primary_color: mine ? '#27408E' : null,
    conference: 'A2',
    region: 'A',
    record: { wins: 10, losses: 2 },
    natl_rank: mine ? 14 : 6,
    conference_place: '1st of 8',
    streak: 'W4',
    next_game: mine
      ? { week: 25, site: 'away', opponent_id: OPP, opponent_name: 'York', opponent_primary_color: null, opponent_natl_rank: 6 }
      : { week: 25, site: 'home', opponent_id: TID, opponent_name: 'Lancaster', opponent_primary_color: '#27408E', opponent_natl_rank: 14 },
    results: [
      { week: 3, site: 'home', team_score: 70, opp_score: 60, result: 'W', opponent_id: OPP, opponent_name: 'York', opponent_primary_color: null, opponent_natl_rank: 6 },
    ],
    upcoming: [
      { week: 26, site: 'away', opponent_id: 'cccccccccccccccccccccccc', opponent_name: 'Dover', opponent_primary_color: '#333333', opponent_natl_rank: 20 },
    ],
  };
}

function standings() {
  const rows = [];
  for (let i = 0; i < 4; i += 1) {
    const id = i === 0 ? TID : (OPP.slice(0, 23) + i);
    rows.push({
      team_id: id,
      name: i === 0 ? 'Lancaster' : ('York ' + i),
      display_name: i === 0 ? 'Lancaster' : ('York ' + i),
      primary_color: i === 1 ? null : '#27408E',
      W: 10 - i,
      L: i,
      pct: 0.8,
      PF: 70,
      PA: 60,
      differential: 10,
      streak: 'W1',
      conference: 2,
      region: 'A',
    });
  }
  return { standings: rows, user_team_id: TID };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
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
      if (/\.(png|jpe?g|webp|gif|svg)$/i.test(pathname)) {
        await route.fulfill({ status: 404, body: '' });
        return;
      }
      await route.continue();
      return;
    }
    if (request.method() === 'POST' && pathname.indexOf('/franchise/player/development-focus') !== -1) {
      const body = request.postDataJSON() || {};
      state.focus = body.training_focus || state.focus;
      state.posted = body;
      await fulfillJson(route, { ok: true });
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
      await fulfillJson(route, cc());
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      await fulfillJson(route, standings());
      return;
    }
    if (pathname.startsWith('/franchise/player-detail')) {
      if (state.failPlayer) {
        await fulfillJson(route, { detail: 'no' }, 500);
        return;
      }
      if (state.holdPlayer && state.gate) await state.gate;
      const id = new URL(request.url()).searchParams.get('player_id') || 'p0';
      await fulfillJson(route, playerDetail(id, { user: id === 'p0', focus: state.focus, nullRates: state.nullRates }));
      return;
    }
    if (pathname.startsWith('/franchise/leaders')) {
      await fulfillJson(route, {
        'FG%': [{ player_id: 'fg0', name: 'Null Shooter', team: 'Lancaster', team_id: TID, value: null }],
        PTS: [{ player_id: 'pt0', name: 'Ada Keeper', team: 'Lancaster', team_id: TID, value: 18.2 }],
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-stats')) {
      await fulfillJson(route, {
        teams: [{
          team: 'Lancaster',
          team_id: TID,
          natl_rank: 14,
          primary_color: '#27408E',
          stats: { W: 10, L: 2, FG_PCT: 0, TP_PCT: null, FT_PCT: 75 },
        }],
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-data')) {
      await fulfillJson(route, {
        measures: [{
          key: 'chemistry', label: 'Chemistry', family: 'Team',
          value: 18, max: 25, tied: true, rank: 61, rank_of: 128, percentile: 50,
        }],
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-detail')) {
      if (state.failTeam) {
        await fulfillJson(route, { detail: 'no' }, 500);
        return;
      }
      const id = new URL(request.url()).searchParams.get('team_id') || TID;
      await fulfillJson(route, teamDetail(id));
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, rosterBody(state.focus));
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page, state, search) {
  await stubAuth(page);
  await installApi(page, state);
  await page.goto('/franchise-command-center.html' + (search || ('?franchise_id=' + FID + '&team_id=' + TID)));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}

async function mouseClick(page, target) {
  const loc = typeof target === 'string' ? page.locator(target).first() : target;
  const box = await loc.boundingBox();
  if (!box) throw new Error('missing target');
  await page.mouse.click(box.x + box.width / 2, box.y + Math.min(box.height / 2, 20));
}

test('roster push opens a player and Back restores the roster scroll', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await page.waitForSelector('#roster-view a.gob-player');
  await page.evaluate(() => { document.querySelector('html.gob-shell .main').scrollTop = 320; });
  const saved = await page.evaluate(() => document.querySelector('html.gob-shell .main').scrollTop);
  expect(saved).toBeGreaterThan(80);
  const before = await page.evaluate(() => history.state && history.state.gobIdx);
  await page.locator('#roster-view a.gob-player').first().evaluate((anchor) => anchor.click());
  await page.waitForURL(/tab=player-view/);
  await expect(page.locator('#player-view')).toContainText('Cedric Buckles');
  expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(before + 1);
  await expect(page.locator('[data-gob-section="team"].on')).toHaveCount(1);
  await page.goBack();
  await page.waitForURL(/tab=roster-view/);
  await page.waitForFunction((top) => {
    const main = document.querySelector('html.gob-shell .main');
    return main && Math.abs(main.scrollTop - top) <= 2;
  }, saved, { timeout: 8000 });
});

test('the player pager replaces and stops at the ends', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=roster-view');
  await page.waitForSelector('#roster-view a.gob-player');
  await page.locator('#roster-view a.gob-player').first().evaluate((anchor) => anchor.click());
  await page.waitForSelector('#player-view .gob-pager');
  const idx = await page.evaluate(() => history.state && history.state.gobIdx);
  await expect(page.locator('#player-view .gob-pager button[aria-label="Previous"]')).toBeDisabled();
  await page.locator('#player-view .gob-pager button[aria-label="Next"]').evaluate((button) => button.click());
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Player 1');
  expect(page.url()).toContain('player_id=p1');
  expect(await page.evaluate(() => history.state && history.state.gobIdx)).toBe(idx);
  await page.locator('#player-view .gob-pager button[aria-label="Previous"]').evaluate((button) => button.click());
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Cedric Buckles');
  await expect(page.locator('#player-view .gob-pager button[aria-label="Previous"]')).toBeDisabled();
});

test('standings opens a team with a conference pager and the league rail', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state);
  await mouseClick(page, '[data-gob-section="league"]');
  await page.waitForSelector('#standings-view a.gob-team');
  await page.locator('#standings-view a.gob-team').nth(1).evaluate((anchor) => anchor.click());
  await page.waitForURL(/tab=team-view/);
  await expect(page.locator('#team-view .gob-hero-n')).toBeVisible();
  await expect(page.locator('#team-view .gob-pager')).toContainText('of 4');
  await expect(page.locator('[data-gob-section="league"].on')).toHaveCount(1);
  const owner = new URL(page.url()).searchParams.get('team_id');
  expect(owner).toBe(TID);
  expect(new URL(page.url()).searchParams.get('view_team_id')).not.toBe(TID);
});

test('old player and other-team links redirect into the views', async ({ page }) => {
  const state = { focus: 'offensive' };
  await stubAuth(page);
  await installApi(page, state);
  await page.goto('/player-detail.html?id=p0&mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&return_tab=roster-view');
  await page.waitForURL(/tab=player-view/);
  expect(new URL(page.url()).searchParams.get('player_id')).toBe('p0');
  expect(new URL(page.url()).searchParams.get('team_id')).toBe(TID);
  await page.goto('/player-detail.html?recruit_id=r1&franchise_id=' + FID);
  await page.waitForURL(/player-detail\.html/);
  expect(page.url()).toContain('recruit_id=r1');
  await page.goto('/team-roster-view.html?mode=franchise&franchise_id=' + FID + '&team_id=' + TID + '&roster_team_id=' + OPP + '&return_tab=standings-view');
  await page.waitForURL(/tab=team-view/);
  expect(new URL(page.url()).searchParams.get('team_id')).toBe(TID);
  expect(new URL(page.url()).searchParams.get('view_team_id')).toBe(OPP);
});

test('recent changes skip delta-only entries and a cpu player is read-only', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team');
  await expect(page.locator('#player-view')).toContainText('SC');
  await expect(page.locator('#player-view')).toContainText('4');
  await expect(page.locator('#player-view')).toContainText('5');
  await expect(page.locator('#player-view')).not.toContainText('ZZ');
  await expect(page.locator('#player-view .gob-focus')).toBeVisible();
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=cpu&origin=league');
  await expect(page.locator('#player-view .gob-focus-read')).toContainText('Offensive');
  await expect(page.locator('#player-view .gob-focus-read')).toContainText('Emphasises SC · SH · ID');
  await expect(page.locator('#player-view .gob-focus')).toHaveCount(0);
  await expect(page.locator('[data-gob-section="league"].on')).toHaveCount(1);
});

test('development focus posts and the roster shows the saved label', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team&return_tab=roster-view');
  await page.waitForSelector('#player-view .gob-focus');
  await expect(page.locator('#player-view select')).toHaveCount(0);
  await expect(page.locator('#player-view .gob-focus-note')).toHaveText('Emphasises SC · SH · ID');
  await expect(page.locator('#player-view .gob-save')).toBeDisabled();
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.waitForTimeout(50);
    const rows = await page.locator('#player-view .gob-focus button').evaluateAll((buttons) => {
      const byTop = {};
      buttons.forEach((button) => {
        const top = Math.round(button.getBoundingClientRect().top);
        byTop[top] = (byTop[top] || 0) + 1;
      });
      return {
        counts: Object.values(byTop),
        fits: buttons.every((button) => button.scrollWidth <= button.clientWidth + 1),
      };
    });
    expect(rows.counts).toEqual([3, 3]);
    expect(rows.fits).toBe(true);
  }
  await page.evaluate(() => {
    const orig = window.GOBStore.mutate.bind(window.GOBStore);
    window.__gobMutations = 0;
    window.GOBStore.mutate = function () {
      window.__gobMutations += 1;
      return orig.apply(window.GOBStore, arguments);
    };
  });
  await page.locator('#player-view .gob-focus [data-value="rebounding"]').click();
  await expect(page.locator('#player-view .gob-save')).toBeEnabled();
  const saveColor = await page.locator('#player-view .gob-save').evaluate((button) => getComputedStyle(button).backgroundColor);
  expect(saveColor).toBe('rgb(247, 148, 32)');
  await page.locator('#player-view .gob-save').click();
  await expect.poll(() => state.posted && state.posted.training_focus).toBe('rebounding');
  await expect.poll(() => page.evaluate(() => window.__gobMutations)).toBe(1);
  await expect(page.locator('#player-view .gob-save')).toHaveText('Saved');
  await expect(page.locator('#player-view .gob-save')).toBeDisabled();
  await page.locator('#player-view .gob-dt-up').click();
  await page.waitForURL(/tab=roster-view/);
  await expect(page.locator('#roster-view')).toContainText('Rebounding');
});

test('a missing portrait and a missing logo fall back to letters', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=cpu&origin=league');
  await expect(page.locator('#player-view .gob-portrait')).toContainText('RQ');
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-view&view_team_id=' + OPP + '&origin=league');
  await expect(page.locator('#team-view .gob-hero-logo .gob-mark')).toContainText('Y');
  await expect(page.locator('#team-view')).toContainText('Scout them');
});

test('first open shows a skeleton and a failed detail retries', async ({ page }) => {
  let release = function () {};
  const state = {
    focus: 'offensive',
    holdPlayer: true,
    gate: new Promise(function (resolve) { release = resolve; }),
  };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team');
  await expect(page.locator('#player-view .gob-view-skel')).toBeVisible();
  await expect(page.locator('#player-view .spinner, #player-view [class*="spinner"]')).toHaveCount(0);
  state.holdPlayer = false;
  release();
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Cedric Buckles');
  state.failPlayer = true;
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p1&origin=team');
  await expect(page.locator('#player-view .gob-view-error')).toBeVisible();
  await expect(page.locator('#player-view .gob-view-retry')).toBeVisible();
  state.failPlayer = false;
  await page.locator('#player-view .gob-view-retry').click();
  await expect(page.locator('#player-view .gob-hero-n')).toContainText('Player 1');
});

test('the detail pages do not scroll sideways', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team');
  await page.waitForSelector('#player-view .gob-hero-n');
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.waitForTimeout(100);
    const overflow = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      return main.scrollWidth - main.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(1);
    await assertOneVerticalScroll(page);
    const elite = await page.locator('#player-view .attr-tile.is-elite s').evaluate((el) => {
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
      const tile = el.parentElement;
      const tileBox = getComputedStyle(tile);
      return {
        color: getComputedStyle(el).color,
        ratio: (hi + 0.05) / (lo + 0.05),
        size: parseFloat(getComputedStyle(el).fontSize),
        weight: getComputedStyle(el).fontWeight,
        family: getComputedStyle(el).fontFamily,
        width: parseFloat(tileBox.width),
        height: parseFloat(tileBox.height),
      };
    });
    expect(elite.color).toBe('rgb(107, 164, 224)');
    expect(elite.ratio).toBeGreaterThanOrEqual(4.5);
    expect(elite.size).toBe(size[0] === 1280 ? 20 : 23.5);
    expect(Number(elite.weight)).toBeGreaterThanOrEqual(700);
    expect(elite.family).toContain('Bebas');
    expect(elite.width).toBe(size[0] === 1280 ? 30 : 35.5);
    expect(elite.height).toBe(size[0] === 1280 ? 26 : 30.5);
  }
});

test('a null percentage renders an em dash and a real zero stays 0.0', async ({ page }) => {
  const state = { focus: 'offensive', nullRates: true };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=player-view&player_id=p0&origin=team');
  await page.waitForSelector('#player-view .gob-hs');
  const hero = (label) => page.locator('#player-view .gob-hs div').filter({ has: page.locator('span', { hasText: new RegExp('^' + label + '$') }) });
  await expect(hero('3PT%').locator('b')).toHaveText('—');
  await expect(hero('DEF%').locator('b')).toHaveText('—');
  await expect(hero('3PT%').locator('b')).not.toHaveText('0.0');
  const season = page.locator('#player-view table tbody tr').nth(0);
  const career = page.locator('#player-view table tbody tr').nth(1);
  await expect(season.locator('td').nth(9)).toHaveText('—');
  await expect(career.locator('td').nth(9)).toHaveText('—');
  await expect(career.locator('td').nth(10)).toHaveText('0.0');
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=leaders-view');
  await page.waitForSelector('#leaders-view .gob-ldb');
  const fg = page.locator('#leaders-view .gob-ldb', { hasText: 'FG%' });
  await expect(fg.locator('.ldb-v')).toContainText('—');
  await expect(fg.locator('.ldb-v')).not.toContainText('0.0');
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-stats-view');
  await page.waitForSelector('#team-stats-view td');
  const row = page.locator('#team-stats-view tbody tr').first();
  await expect(row).toContainText('0.0');
  await expect(row).toContainText('—');
});

async function assertCompactRoster(page) {
  const table = page.locator('#team-view .gob-roster.is-compact table');
  await expect(table.locator('tr').first().locator('th').first()).toHaveText('Player');
  const shape = await table.evaluate((node) => {
    const first = node.rows[0];
    const bodyFirst = node.tBodies[0] && node.tBodies[0].rows[0];
    function rects(cell) {
      const bits = cell.querySelectorAll('.rtl, .gob-player span:last-child, .attr-tile');
      if (bits.length) return [...bits].map((bit) => bit.getBoundingClientRect());
      const range = document.createRange();
      range.selectNodeContents(cell);
      return [...range.getClientRects()].filter((box) => box.width > 1 && box.height > 1);
    }
    function hits(a, b) {
      return a.left < b.right - 0.5 && a.right > b.left + 0.5 && a.top < b.bottom - 0.5 && a.bottom > b.top + 0.5;
    }
    const problems = [];
    [...node.rows].forEach((row) => {
      const cells = [...row.cells].map((cell) => ({ rects: rects(cell), text: cell.innerText.trim() }));
      for (let i = 0; i < cells.length; i += 1) {
        for (let j = i + 1; j < cells.length; j += 1) {
          cells[i].rects.forEach((a) => {
            cells[j].rects.forEach((b) => {
              if (hits(a, b)) problems.push(cells[i].text + ' | ' + cells[j].text);
            });
          });
        }
      }
    });
    const rt = node.querySelector('tbody td.rt');
    const rtBox = rt ? rt.getBoundingClientRect() : null;
    const rtText = rt ? rt.querySelector('.rtl').getBoundingClientRect() : null;
    const rtInside = !!(rtBox && rtText
      && rtText.left >= rtBox.left - 0.5
      && rtText.right <= rtBox.right + 0.5
      && rtText.top >= rtBox.top - 0.5
      && rtText.bottom <= rtBox.bottom + 0.5
      && rtText.width > 0);
    return {
      headerFirst: first.parentElement.tagName === 'THEAD' && first.cells[0].tagName === 'TH',
      bodyStarts: bodyFirst ? bodyFirst.innerText.trim() : '',
      repeats: node.querySelectorAll('tbody tr.gob-rep').length,
      problems: problems,
      rtInside: rtInside,
    };
  });
  expect(shape.headerFirst).toBe(true);
  expect(shape.bodyStarts.toLowerCase()).toBe('starters');
  expect(shape.repeats).toBe(0);
  expect(shape.problems).toEqual([]);
  expect(shape.rtInside).toBe(true);
}

test('the team page roster is the compact five-attribute grid', async ({ page }) => {
  const state = { focus: 'offensive' };
  await openFcc(page, state, '?franchise_id=' + FID + '&team_id=' + TID + '&tab=team-view&view_team_id=' + OPP + '&origin=league');
  await page.waitForSelector('#team-view .gob-roster.is-compact');
  const headers = await page.locator('#team-view .gob-roster thead th').allTextContents();
  expect(headers.map((text) => text.trim())).toEqual(['Player', 'RT', 'POS', 'YR', 'HT', 'SC', 'SH', 'ID', 'OD', 'RB']);
  await expect(page.locator('#team-view .gob-roster')).toContainText('Starters');
  await expect(page.locator('#team-view .gob-roster')).toContainText('Bench');
  await expect(page.locator('#team-view .gob-roster')).toContainText('Montgomery Worthington-Blake');
  await expect(page.locator('#team-view .gob-roster thead')).not.toContainText('Dev focus');
  await expect(page.locator('#team-view .gob-roster thead')).not.toContainText('PS');
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.waitForTimeout(100);
    await assertCompactRoster(page);
    const fit = await page.locator('#team-view .gob-roster.is-compact').evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(fit).toBeLessThanOrEqual(1);
    const overflow = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      return main.scrollWidth - main.clientWidth;
    });
    expect(overflow).toBeLessThanOrEqual(1);
  }
});

test('each view opens when the URL has no team_id', async ({ page }) => {
  const state = { focus: 'offensive' };
  const hits = [];
  page.on('request', (req) => hits.push(req.url()));
  await openFcc(page, state, '?franchise_id=' + FID + '&tab=roster-view');
  expect(new URL(page.url()).searchParams.has('team_id')).toBe(false);
  await page.waitForSelector('#roster-view a.gob-player');
  await expect(page.locator('#roster-view')).toContainText('Cedric Buckles');
  await expect(page.locator('#roster-view')).not.toContainText('could not be opened');
  await expect(page.locator('#gob-subtabs [data-value="varsity"] em')).toHaveText('12');
  expect(hits.some((url) => url.includes('/roster/' + TID))).toBe(true);
  const views = [
    { search: 'tab=rankings-view', ready: '#rankings-view', text: 'National Rankings' },
    { search: 'tab=standings-view', ready: '#standings-view', text: 'Lancaster' },
    { search: 'tab=leaders-view', ready: '#leaders-view .gob-ldb', text: 'Null Shooter', filtered: true },
    { search: 'tab=team-stats-view', ready: '#team-stats-view', text: 'Lancaster' },
    { search: 'tab=team-attributes-view', ready: '#team-attributes-view', text: '61st of 128' },
    { search: 'tab=player-view&player_id=p0', ready: '#player-view .gob-hero-n', text: 'Cedric Buckles' },
    { search: 'tab=team-view', ready: '#team-view .gob-hero-n', text: 'Lancaster' },
  ];
  for (const view of views) {
    hits.length = 0;
    await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&' + view.search);
    expect(new URL(page.url()).searchParams.has('team_id')).toBe(false);
    await page.waitForSelector(view.ready);
    const ready = view.filtered
      ? page.locator(view.ready).filter({ hasText: view.text })
      : page.locator(view.ready);
    await expect(ready).toContainText(view.text);
    await expect(page.locator('.main')).not.toContainText('could not be opened');
    if (view.search.indexOf('team-attributes') !== -1) {
      await expect(page.locator('#team-attributes-view')).not.toContainText('T-');
    }
  }
});
