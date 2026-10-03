// @ts-check
/** The legacy white "FAQs" footer (authBarInit.js) never shows inside the shell. */
const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-site-footer';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';

function recruit(i) {
  return {
    recruit_id: 'r-' + i,
    name: 'Recruit ' + i,
    archetype: 'Slasher',
    'Home Region': 'C',
    year: 'Junior',
    height: 76,
    weight: 190,
    attributes: { SC: 70, SH: 60, ID: 55, OD: 50, PS: 48, BH: 44, RB: 40, AG: 62, ST: 58, ND: 52, IQ: 66, FT: 71 },
    position_ratings: { PG: 80 },
    Lean: i % 2 ? { 1: TID, 2: null, 3: null } : { 1: 'rival-1', 2: null, 3: null },
  };
}

function recruitingData() {
  return {
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week: 21,
    recruits: Array.from({ length: 30 }, (_, i) => recruit(i)),
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
    invite_seed_modal_seen: true,
    visit_history: [],
    conferences: { order: [], by_team_id: {} },
  };
}

function cc(week, boardSavedWeek) {
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
    recruiting_wire: { board_saved_week: boardSavedWeek, counts: {} },
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 4, losses: 1 },
  };
}

async function installApi(page, week, boardSavedWeek) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const json = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (pathname.startsWith('/franchise/recruiting-data')) return json(recruitingData());
    if (pathname.startsWith('/franchise/command-center/data')) return json(cc(week, boardSavedWeek));
    if (pathname === '/api/auth/me') return json({ user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
    if (pathname === '/app-config') return json({ isAlpha: false, version: '1.0' });
    if (pathname === '/teams') return json([{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
    if (pathname.startsWith('/franchise/standings')) {
      return json({ standings: [{ team_id: TID, name: 'Lancaster', W: 4, L: 1, conference: 1, region: 'C' }] });
    }
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')) return json({});
    return route.continue();
  });
}

// Put a footer in <body> before the shell mounts, so adoptMain meets it whatever
// the script timing is. authBarInit.js skips its own inject when one exists.
async function footerFirst(page) {
  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      if (document.getElementById('site-footer')) return;
      const footer = document.createElement('footer');
      footer.id = 'site-footer';
      footer.className = 'site-footer';
      footer.innerHTML = '<a href="/faqs.html">FAQs</a>';
      document.body.appendChild(footer);
    }, { once: true });
  });
}

function footerState(page) {
  return page.evaluate(() => {
    const el = document.getElementById('site-footer');
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = main.scrollHeight;
    if (!el) return { present: false, display: 'none', inMain: false, visiblePx: 0 };
    const r = el.getBoundingClientRect();
    return {
      present: true,
      display: getComputedStyle(el).display,
      inMain: !!(main && main.contains(el)),
      visiblePx: Math.max(0, Math.round(Math.min(r.bottom, innerHeight) - Math.max(r.top, 0))),
    };
  });
}

async function expectHidden(page, label) {
  await page.waitForTimeout(500);
  const state = await footerState(page);
  expect(state.inMain, label + ' ' + JSON.stringify(state)).toBe(false);
  expect(state.display, label + ' ' + JSON.stringify(state)).toBe('none');
  expect(state.visiblePx, label + ' ' + JSON.stringify(state)).toBe(0);
  await expect(page.locator('#site-footer')).toBeHidden();
  await expect(page.getByRole('link', { name: 'FAQs', exact: true })).toBeHidden();
}

const SHELL_PAGES = [
  {
    name: 'recruiting focus flow, week 21',
    week: 21,
    saved: 0,
    url: '/recruiting.html?franchise_id=' + FID + '&team_id=' + TID + '&from=fcc',
    ready: async (page) => {
      await page.waitForSelector('#hub-pool tbody tr.rec');
      await expect(page.locator('html.gob-shell.gob-focus')).toHaveCount(1);
    },
  },
  {
    name: 'office',
    week: 21,
    saved: 21,
    url: '/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID,
    ready: async (page) => {
      await page.waitForSelector('#office-root');
      await expect(page.locator('html.gob-shell.gob-office')).toHaveCount(1);
    },
  },
  {
    name: 'league standings (browse)',
    week: 21,
    saved: 21,
    url: '/standings.html?franchise_id=' + FID + '&team_id=' + TID,
    ready: async (page) => {
      await page.waitForSelector('#gob-main');
      await expect(page.locator('html.gob-shell:not(.gob-focus)')).toHaveCount(1);
    },
  },
];

for (const spec of SHELL_PAGES) {
  test('no site footer inside the shell: ' + spec.name, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await installApi(page, spec.week, spec.saved);
    await page.goto(spec.url);
    await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
    await spec.ready(page);
    await expectHidden(page, spec.name);
  });

  test('footer already in the body before mount stays out of #gob-main: ' + spec.name, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await footerFirst(page);
    await installApi(page, spec.week, spec.saved);
    await page.goto(spec.url);
    await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
    await spec.ready(page);
    const state = await footerState(page);
    expect(state.present, JSON.stringify(state)).toBe(true);
    await expectHidden(page, spec.name + ' (footer first)');
  });
}

// Public pages (homepage, login, signup, faqs, ...) return from authGuard.js before it loads
// authBarInit.js, so they never get the injected footer. The homepage has its own.
test('outside the shell the homepage keeps its own footer', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/homepage.html');
  await expect(page.locator('html.gob-shell')).toHaveCount(0);
  await expect(page.locator('#site-footer')).toHaveCount(0);
  const footer = page.locator('footer.footer');
  await expect(footer).toHaveCount(1);
  await footer.scrollIntoViewIfNeeded();
  await expect(footer).toBeVisible();
});

for (const url of ['/faqs.html', '/account.html']) {
  test('outside the shell the footer still shows: ' + url, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    if (url === '/account.html') await installApi(page, 21, 21);
    await page.goto(url);
    const footer = page.locator('#site-footer');
    await expect(footer).toHaveCount(1);
    await expect(page.locator('html.gob-shell')).toHaveCount(0);
    await footer.scrollIntoViewIfNeeded();
    await expect(footer).toBeVisible();
    await expect(footer.getByRole('link', { name: 'FAQs' })).toHaveAttribute('href', '/faqs.html');
    const style = await footer.evaluate((el) => ({ bg: getComputedStyle(el).backgroundColor, display: getComputedStyle(el).display }));
    expect(style.display).not.toBe('none');
    expect(style.bg).toBe('rgb(255, 255, 255)');
  });
}
