const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-prep-modules-report';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/prep-modules-report');
const TOKENS_OUT = path.join(__dirname, '../../reports/prep-training-tokens');

function alsoTokenShot(srcName, destName) {
  fs.mkdirSync(TOKENS_OUT, { recursive: true });
  const src = path.join(OUT, srcName);
  if (fs.existsSync(src)) fs.copyFileSync(src, path.join(TOKENS_OUT, destName || srcName));
}

async function resetReportScroll(page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const view = document.getElementById('training-report-view');
    if (view) view.scrollTop = 0;
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = 0;
    document.querySelectorAll('.main, .main.scroll').forEach((el) => { el.scrollTop = 0; });
  });
}
const HEADSHOT = fs.readFileSync(path.join(__dirname, '../../FrontEnd/static/images/players/generic_headshot.png'));
const BEFORE = JSON.parse(fs.readFileSync(path.join(OUT, 'before-metrics.json'), 'utf8'));

function parseRgba(value) {
  const m = String(value).match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (!m) return null;
  return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] == null ? 1 : Number(m[4]) };
}

function samePaint(actual, expected) {
  if (actual === expected) return true;
  if (actual === 'transparent' || actual === 'rgba(0, 0, 0, 0)') {
    const exp = parseRgba(expected);
    return exp && exp.a <= 0.02;
  }
  const a = parseRgba(actual);
  const b = parseRgba(expected);
  if (!a || !b) return false;
  return Math.abs(a.r - b.r) <= 2 && Math.abs(a.g - b.g) <= 2
    && Math.abs(a.b - b.b) <= 2 && Math.abs(a.a - b.a) <= 0.02;
}

const REPORT = {
  week: 12,
  upcoming_opponent: 'Four Corners',
  coaching_focus: {
    archetype: 'systems-coach',
    sub_option: 'systems-coach-offense',
    leaf_display_name: 'Offense',
  },
  players: [
    {
      player_id: 'p-roger',
      id: 'p-roger',
      name: 'Roger Henrich',
      jersey: 33,
      year: 'JR',
      pos: 'C',
      position: 'C',
      position_ratings: { PG: 20, SG: 30, SF: 45, PF: 70, C: 82 },
      attributes: { SC: 40, SH: 40, ID: 60, OD: 70, PS: 30, BH: 30, RB: 80, ST: 80, AG: 40, ND: 50, IQ: 50, FT: 40 },
      attrs: { SC: 40, SH: 40, ID: 60, OD: 70, PS: 30, BH: 30, RB: 80, ST: 80, AG: 40, ND: 50, IQ: 50, FT: 40 },
      season_stats: { PTS: 14.2, FGM: 5, FGA: 11, '3PTM': 1, '3PTA': 3, FTM: 3, FTA: 4, DREB: 6, OREB: 2, AST: 2, STL: 1, BLK: 2, F: 2, MIN: 28, TO: 1 },
    },
  ],
  player_changes: { 'p-roger': { SC: 1.2, RB: 0.8 } },
  player_attribute_display_movements: {},
  exceptional_gains: [],
  team_attributes: {
    offensive_efficiency: 4,
    defensive_efficiency: 2,
    fb_efficiency: 1,
    fb_opp_modifier: -2,
    pt_efficiency: 6,
    pt_opp_modifier: -1,
    discipline: 3,
    fight: 2,
    shot_threshold: 0,
    rebound_modifier: 1,
    team_chemistry: 8,
    momentum_score: 5,
  },
  team_changes: { offensive_efficiency: 1, pt_efficiency: 2 },
  plays_data: {},
  scouting_data: {},
  plays_effectiveness_changes: {},
  defenses_effectiveness_changes: {},
  projected_starting_five: [
    { player_id: 'p-roger', name: 'Roger Henrich', jersey: 33, position: 'C' },
  ],
  training_notes: [
    { title: 'Practice Player Of The Week', body: 'Roger Henrich' },
    { title: 'Biggest Regression', body: 'No Significant Updates' },
    { title: 'Most Positive Locker Room Influence', body: 'Roger Henrich' },
    { title: 'Strong Cumulative Increase', body: 'Inside Defense' },
    { title: 'Strongest Defensive Set', body: 'Man' },
    { title: 'Strongest Offensive Plays', body: 'Horn' },
    { title: 'Fast Break Readiness', body: 'Ready' },
    { title: 'Press/Trap Readiness', body: 'Improving' },
    { title: 'Player Energy Levels', body: 'No Significant Updates' },
  ],
};

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page) {
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
      || pathname === '/teams'
      || pathname === '/app-config';
    if (pathname.startsWith('/images/players/')) {
      return route.fulfill({ status: 200, contentType: 'image/png', body: HEADSHOT });
    }
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    }
    if (pathname === '/app-config') {
      return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    }
    if (pathname === '/teams') {
      return fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      return fulfillJson(route, {
        franchise_id: FID,
        team_id: TID,
        user_team_id: TID,
        team: 'Lancaster',
        week: 12,
        rank: 14,
        season: 1,
        current_season: 1,
        training_completed: true,
        session_type: 'in-season',
        cut_required: false,
        rankings: [],
      });
    }
    if (pathname.startsWith('/franchise/training-report')) return fulfillJson(route, REPORT);
    return fulfillJson(route, {});
  });
}

async function openReport(page, extra) {
  await stubAuth(page);
  await installApi(page);
  const bag = new URLSearchParams({
    franchise_id: FID,
    team_id: TID,
    mode: 'franchise',
    week: '12',
    tab: 'training-report-view',
  });
  Object.keys(extra || {}).forEach((key) => bag.set(key, extra[key]));
  await page.goto('/franchise-command-center.html?' + bag.toString());
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#training-report-view.tab-content.active', { timeout: 20000 });
  await expect(page.locator('#training-report-view #week-number')).toHaveText('12', { timeout: 15000 });
}

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test('the view does not fetch the old embed HTML', async ({ page }) => {
  const embeds = [];
  const loaders = [];
  const bridges = [];
  page.on('request', (req) => {
    const url = req.url();
    if (url.includes('training-report.html')) embeds.push(url);
    if (url.includes('viewLoader.js')) loaders.push(url);
    if (url.includes('prepEmbed.js')) bridges.push(url);
  });
  await page.setViewportSize({ width: 1280, height: 720 });
  await openReport(page, { from: 'office', origin: 'office' });
  expect(embeds).toEqual([]);
  expect(bridges).toEqual([]);
  expect(loaders.length).toBeGreaterThan(0);
  const clash = await page.evaluate(() => {
    const host = document.getElementById('training-report-view');
    const dupes = [];
    if (!host) return ['missing-host'];
    host.querySelectorAll('[id]').forEach((el) => {
      const id = el.id;
      if (!id) return;
      if (document.querySelectorAll('[id="' + CSS.escape(id) + '"]').length > 1) dupes.push(id);
    });
    if (document.getElementById('attribute-tooltip')) dupes.push('attribute-tooltip');
    if (document.querySelectorAll('[id="toast"]').length > 1) dupes.push('toast');
    return dupes;
  });
  expect(clash).toEqual([]);
});

test('Office drill-in: real data, Back, no Player Training highlight', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openReport(page, { from: 'office', origin: 'office' });
  await expect(page.locator('#training-report-view')).toContainText('Four Corners');
  await expect(page.locator('#training-report-view')).toContainText('Roger Henrich');
  await expect(page.locator('#training-report-view')).toContainText('P/T Defense Readiness');
  await expect(page.locator('#training-report-view #team-attributes-grid')).not.toContainText('Momentum');
  const tokenLook = await page.evaluate(() => {
    const host = document.getElementById('training-report-view');
    const green = (v) => /rgb\(\s*52\s*,\s*236\s*,\s*39/i.test(v);
    const orange = (v) => /rgb\(\s*247\s*,\s*148\s*,\s*32/i.test(v);
    const bad = [];
    host.querySelectorAll('.toggle-btn, .seg button, [role="radio"]').forEach((el) => {
      const s = getComputedStyle(el);
      if (green(s.backgroundColor) || green(s.color) || orange(s.backgroundColor) || orange(s.color)) {
        bad.push({ cls: el.className, bg: s.backgroundColor, color: s.color });
      }
    });
    const shot = host.querySelector('.training-notes-hero-portrait-img, .pdg-av img, .av img, .player-portrait img');
    return { bad, radius: shot ? getComputedStyle(shot).borderRadius : '' };
  });
  expect(tokenLook.bad).toEqual([]);
  if (tokenLook.radius) {
    expect(tokenLook.radius.includes('%')).toBe(false);
    expect(parseFloat(tokenLook.radius)).toBeLessThanOrEqual(8);
  }
  const nitShots = path.join(__dirname, '../../reports/training-report-no-momentum');
  fs.mkdirSync(nitShots, { recursive: true });
  await expect(page.getByRole('button', { name: '← Back', exact: true })).toBeVisible();
  await expect(page.locator('#gob-subtabs .tb[data-tab="training-view"][aria-selected="true"]')).toHaveCount(0);
  await expect(page.locator('html')).not.toHaveClass(/gob-office/);
  await resetReportScroll(page);
  await page.screenshot({ path: path.join(OUT, 'training-report-office-1280.png') });
  await page.screenshot({ path: path.join(OUT, 'training-report-after-1280.png') });
  alsoTokenShot('training-report-after-1280.png', 'after-report-1280.png');
  const notes = page.locator('#training-report-view .training-notes-section');
  if (await notes.count()) {
    await notes.first().screenshot({ path: path.join(TOKENS_OUT, 'after-report-notes-1280.png') });
  }
  const team = page.locator('#training-report-view .team-section, #training-report-view #team-attributes-grid');
  if (await team.count()) {
    await team.first().screenshot({ path: path.join(TOKENS_OUT, 'after-report-team-1280.png') });
  }
  await page.locator('#training-report-view .team-section').screenshot({
    path: path.join(nitShots, 'team-report-after-1280.png'),
  });

  await page.setViewportSize({ width: 1920, height: 1080 });
  await expect(page.locator('#training-report-view #week-number')).toHaveText('12');
  await resetReportScroll(page);
  await page.screenshot({ path: path.join(OUT, 'training-report-office-1920.png') });
  await page.screenshot({ path: path.join(OUT, 'training-report-after-1920.png') });
  alsoTokenShot('training-report-after-1920.png', 'after-report-1920.png');
});

test('News drill-in keeps ← News', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openReport(page, { from: 'news', origin: 'news' });
  await expect(page.getByRole('link', { name: '← News', exact: true })).toBeVisible();
  await expect(page.locator('#training-report-view')).toContainText('Four Corners');
  await page.screenshot({ path: path.join(OUT, 'training-report-news-1280.png') });
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.screenshot({ path: path.join(OUT, 'training-report-news-1920.png') });
});

test('reopening keeps the panel and does not rebuild the shell', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openReport(page, { from: 'office', origin: 'office' });
  const token = await page.evaluate(() => {
    const host = document.getElementById('training-report-view');
    host.dataset.keep = '1';
    return host.querySelector('.training-report-container') ? 'ok' : '';
  });
  expect(token).toBe('ok');
  await page.evaluate(() => {
    if (window.GOBViews && window.GOBViews.show) window.GOBViews.show('training-report-view');
  });
  await expect(page.locator('#training-report-view')).toHaveAttribute('data-keep', '1');
  await expect(page.locator('#training-report-view .training-report-container')).toHaveCount(1);
  await expect(page.locator('#training-report-view #week-number')).toHaveText('12');
});

async function reportGeometry(page) {
  return page.evaluate(() => {
    const host = document.getElementById('training-report-view');
    const cards = [...host.querySelectorAll('.training-notes-hero-card')].map((el) => {
      const r = el.getBoundingClientRect();
      const label = el.querySelector('.training-notes-hero-label');
      const name = el.querySelector('.training-notes-hero-name');
      const widerThanColumn = [label, name].filter(Boolean).some((node) => (
        node.scrollWidth > node.clientWidth + 1
      ));
      return {
        width: Math.round(r.width),
        height: Math.round(r.height),
        labelWidth: label ? Math.round(label.getBoundingClientRect().width) : 0,
        labelHeight: label ? Math.round(label.getBoundingClientRect().height) : 0,
        wrap: label ? (label.scrollHeight > label.clientHeight + 1) : false,
        widerThanColumn,
      };
    });
    const portraits = [...host.querySelectorAll('.training-notes-hero-portrait-img, .training-notes-hero-portrait-fallback')].map((el) => {
      const r = el.getBoundingClientRect();
      return {
        w: Math.round(r.width),
        h: Math.round(r.height),
        natural: el.tagName === 'IMG' ? el.naturalWidth : null,
        radius: getComputedStyle(el).borderRadius,
      };
    });
    const btn = host.querySelector('#locker-room-btn');
    const bs = btn ? getComputedStyle(btn) : null;
    const toggle = host.querySelector('.players-section .toggle-btn.active');
    const ts = toggle ? getComputedStyle(toggle) : null;
    return {
      cards,
      portraits,
      back: btn ? {
        bg: bs.backgroundColor,
        border: bs.borderColor,
        color: bs.color,
        cls: btn.className,
        w: Math.round(btn.getBoundingClientRect().width),
        h: Math.round(btn.getBoundingClientRect().height),
      } : null,
      toggle: toggle ? { bg: ts.backgroundColor, color: ts.color } : null,
      pageClassOnBody: document.body.classList.contains('training-report-page'),
      pageClassOnView: host.classList.contains('training-report-page'),
    };
  });
}

test('Notes columns, headshots, and Back match the develop before', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openReport(page, { from: 'office', origin: 'office' });
  await page.waitForFunction(() => {
    const nodes = document.querySelectorAll('#training-report-view .training-notes-hero-portrait-img, #training-report-view .training-notes-hero-portrait-fallback');
    return nodes.length >= 3;
  });
  await page.waitForFunction(() => {
    const btn = document.querySelector('#training-report-view #locker-room-btn');
    if (!btn) return false;
    const bg = getComputedStyle(btn).backgroundColor;
    return bg === 'rgba(255, 255, 255, 0.06)'
      || bg === 'transparent'
      || bg === 'rgba(0, 0, 0, 0)';
  });
  const after = await reportGeometry(page);
  const before = BEFORE.office;

  expect(after.pageClassOnBody).toBe(false);
  expect(after.pageClassOnView).toBe(true);
  expect(after.cards).toHaveLength(before.cards.length);
  after.cards.forEach((card, i) => {
    expect(Math.abs(card.width - before.cards[i].width)).toBeLessThanOrEqual(16);
    expect(card.widerThanColumn).toBe(false);
  });
  expect(after.portraits).toHaveLength(before.portraits.length);
  after.portraits.forEach((shot) => {
    expect(shot.w).toBe(40);
    expect(shot.h).toBe(40);
    expect(shot.radius.startsWith('6px')).toBe(true);
  });
  const photos = after.portraits.filter((shot) => shot.natural != null);
  photos.forEach((shot) => expect(shot.natural).toBeGreaterThan(0));
  expect(after.back.cls).toContain('gob-btn--ghost');
  expect(after.back.cls).not.toContain('locker-room-button');
  expect(after.back.w).toBe(before.back.w);
  expect(after.back.h).toBe(before.back.h);
  const bgOk = after.back.bg === 'transparent'
    || after.back.bg === 'rgba(0, 0, 0, 0)'
    || samePaint(after.back.bg, before.back.bg);
  expect(bgOk, `Back background ${after.back.bg} vs ${before.back.bg}`).toBe(true);
  expect(samePaint(after.back.border, before.back.border), `Back border ${after.back.border} vs ${before.back.border}`).toBe(true);
  expect(samePaint(after.back.color, before.back.color), `Back color ${after.back.color} vs ${before.back.color}`).toBe(true);
  expect(after.toggle.bg).not.toMatch(/247,\s*148|#f79420/i);
});

test('post-submit Back to Office keeps tut_alert=training_return', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openReport(page, { from: 'training', origin: 'prep' });
  const btn = page.getByRole('button', { name: 'Back to Office', exact: true });
  await expect(btn).toBeVisible();
  const waitNav = page.waitForURL(/tut_alert=training_return/, { timeout: 15000 });
  await btn.click();
  await waitNav;
});
