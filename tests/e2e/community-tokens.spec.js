const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

// Community surfaces (archetype leaderboard, coaching archetypes, account /
// geek points) on gob tokens + colour law. Visual only: all data is stubbed.
// COMMUNITY_BEFORE=1 writes before-*.png (run on origin/develop CSS) and skips the guards.

test.describe.configure({ timeout: 120000 });

const OUT = path.join(__dirname, '../../reports/community-tokens');
const CAPTURE_BEFORE = process.env.COMMUNITY_BEFORE === '1';
const PREFIX = CAPTURE_BEFORE ? 'before' : 'after';
const SIZES = [
  { w: 1280, h: 720 },
  { w: 1920, h: 1080 },
];

const ME = {
  user_id: 'e2e-user',
  username: 'CoachE2E',
  email: 'e2e@example.com',
  subscription: 'alpha',
  fte_v2_complete: true,
  geek_points: 1240,
  geek_points_teams: [
    { team_id: 't1', display_name: 'Lancaster', points: 900 },
    { team_id: 't2', display_name: 'Xavien', points: 340 },
  ],
  championships_total: { national: 1, region: 2, conf_t: 0, conf_rs: 3 },
  archetypes: { total: 20, pure_offense: 9, od_balance: 6, the_intimidator: 5 },
  lead_archetype: 'pure_offense',
};

const BOARDS = {
  od_balance: [
    { rank: 1, username: 'HoopsMind', pct: 52 },
    { rank: 2, username: 'CoachE2E', pct: 30, is_current_user: true },
    { rank: 3, username: 'ZoneKing', pct: 21 },
  ],
  pure_offense: [
    { rank: 1, username: 'CoachE2E', pct: 45, is_current_user: true },
    { rank: 2, username: 'RunAndGun', pct: 38 },
  ],
  pure_defense: [{ rank: 1, username: 'LockDown', pct: 61 }],
  the_intimidator: [{ rank: 1, username: 'BigFella', pct: 40 }],
};

// Computed colours arrive as rgb()/rgba(), or color(srgb …) from color-mix().
function parseRgba(value) {
  const v = String(value);
  let m = v.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (m) return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] == null ? 1 : Number(m[4]) };
  m = v.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*\)/i);
  if (m) return { r: Number(m[1]) * 255, g: Number(m[2]) * 255, b: Number(m[3]) * 255, a: m[4] == null ? 1 : Number(m[4]) };
  return null;
}
const paints = (v) => String(v).match(/rgba?\([^)]*\)|color\(srgb[^)]*\)/gi) || [];
function isOrange(rgb) {
  const p = parseRgba(rgb);
  return !!p && p.a >= 0.1 && p.r > 200 && p.g > 100 && p.g < 190 && p.b < 80;
}
function isGreen(rgb) {
  const p = parseRgba(rgb);
  return !!p && p.a >= 0.1 && p.g > 180 && p.r < 150 && p.b < 150;
}
// Navy-family: blue clearly dominant, but darker than the RT tier blue.
function isNavy(rgb) {
  const p = parseRgba(rgb);
  return !!p && p.a >= 0.1 && p.b > p.r + 30 && p.b > p.g + 15;
}
// A coloured (non-grey) tint of any hue: what a "wash" is.
function isTinted(rgb) {
  const p = parseRgba(rgb);
  if (!p || p.a < 0.05) return false;
  return Math.max(p.r, p.g, p.b) - Math.min(p.r, p.g, p.b) > 24;
}
const hasOrange = (v) => paints(v).some(isOrange);
const hasGreen = (v) => paints(v).some(isGreen);
const hasNavy = (v) => paints(v).some(isNavy);
const hasTint = (v) => paints(v).some(isTinted);

async function installApi(page) {
  await page.route('**/*', async (route) => {
    const req = route.request();
    let pathname = '';
    try { pathname = new URL(req.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const json = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (/googletagmanager|sentry|google-analytics/.test(req.url())) {
      await route.fulfill({ status: 204, body: '' });
      return;
    }
    if (pathname === '/api/auth/me') return json(ME);
    if (pathname === '/api/leaderboard/by-archetype') return json(BOARDS);
    if (pathname === '/teams') return json([]);
    if (pathname === '/app-config') return json({ isAlpha: true, alphaDisclaimer: null, version: '1.0', sentryDsn: null, teamBuilderEnabled: true });
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) return json({});
    await route.continue();
  });
}

async function open(page, url, size) {
  await page.setViewportSize({ width: size.w, height: size.h });
  await stubAuth(page);
  await page.addInitScript((me) => { window.__gobAuthMeData = me; }, ME);
  await installApi(page);
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

async function shot(page, name, size) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(350);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-${size.w}.png`) });
}

const ready = {
  leaderboard: (page) => page.locator('.alb-row').first().waitFor(),
  archetypes: (page) => page.locator('.ca-card').first().waitFor(),
  account: (page) => page.locator('.arch-cell').first().waitFor(),
};

test.describe('community tokens', () => {
  for (const size of SIZES) {
    test(`shots ${size.w}`, async ({ page }) => {
      await open(page, '/coaching-archetypes-leaderboard.html', size);
      await ready.leaderboard(page);
      await shot(page, 'leaderboard', size);
      await page.locator('.alb-card-head.has-tip').first().hover();
      await page.waitForTimeout(200);
      await shot(page, 'leaderboard-tip', size);

      await open(page, '/coaching-archetypes.html', size);
      await ready.archetypes(page);
      await shot(page, 'archetypes', size);

      await open(page, '/account.html', size);
      await ready.account(page);
      await shot(page, 'account', size);
    });
  }

  test('colour law guards', async ({ page }) => {
    test.skip(CAPTURE_BEFORE, 'before capture');
    const size = SIZES[0];

    for (const url of ['/coaching-archetypes-leaderboard.html', '/coaching-archetypes.html', '/account.html']) {
      await open(page, url, size);
      const t = await page.evaluate(() => {
        const root = getComputedStyle(document.documentElement);
        const body = getComputedStyle(document.body);
        const h = document.querySelector('h1, .acct-name');
        return {
          gob: document.documentElement.classList.contains('gob'),
          text100: root.getPropertyValue('--text-100').trim(),
          bg: body.backgroundImage + ' ' + body.backgroundColor,
          font: body.fontFamily,
          head: h ? getComputedStyle(h).fontFamily : '',
          sheet: !!document.querySelector('link[href*="community.css"]'),
          padTop: body.paddingTop,
        };
      });
      expect(t.gob, `${url} html.gob`).toBe(true);
      expect(t.text100, `${url} --text-100`).not.toBe('');
      expect(t.sheet, `${url} loads css/community.css`).toBe(true);
      expect(hasNavy(t.bg) || hasTint(t.bg), `${url} no navy/colour wash on the page ${t.bg}`).toBe(false);
      expect(t.padTop, `${url} auth bar keeps owning padding-top (layout unchanged)`).toBe('72px');
      expect(t.font).toMatch(/Inter/);
      expect(t.head).toMatch(/Bebas Neue/);
    }

    // Leaderboard: your row is navy ("yours"); other rows untinted; % neutral; tip focus neutral.
    await open(page, '/coaching-archetypes-leaderboard.html', size);
    await ready.leaderboard(page);
    const lb = await page.evaluate(() => {
      const mine = document.querySelector('.alb-row.is-current');
      const other = document.querySelector('.alb-row:not(.is-current)');
      return {
        mine: getComputedStyle(mine).backgroundColor + ' ' + getComputedStyle(mine).boxShadow,
        other: getComputedStyle(other).backgroundColor,
        pct: Array.from(document.querySelectorAll('.alb-pct')).map((el) => getComputedStyle(el).color),
        tip: getComputedStyle(document.querySelector('.alb-tip')).backgroundColor,
      };
    });
    expect(hasNavy(lb.mine), `your row navy ${lb.mine}`).toBe(true);
    expect(hasOrange(lb.mine), `your row not orange ${lb.mine}`).toBe(false);
    expect(hasTint(lb.other), `other rows untinted ${lb.other}`).toBe(false);
    for (const c of lb.pct) expect(hasOrange(c) || hasGreen(c), `pct ${c}`).toBe(false);
    expect(hasNavy(lb.tip), `tooltip surface neutral ${lb.tip}`).toBe(false);
    await page.locator('.alb-card-head.has-tip').first().focus();
    const ring = await page.locator('.alb-card-head.has-tip').first().evaluate((el) => getComputedStyle(el).outlineColor);
    expect(hasOrange(ring), `focus ring ${ring}`).toBe(false);

    // Coaching archetypes: your archetype card is navy, not orange.
    await open(page, '/coaching-archetypes.html', size);
    await ready.archetypes(page);
    const ca = await page.evaluate(() => {
      const lead = document.querySelector('.ca-card.is-lead');
      const s = lead ? getComputedStyle(lead) : null;
      return lead ? { border: s.borderTopColor, shadow: s.boxShadow } : null;
    });
    expect(ca, 'lead archetype card rendered').not.toBeNull();
    expect(hasOrange(ca.border) || hasOrange(ca.shadow), `lead card not orange ${ca.border} ${ca.shadow}`).toBe(false);
    expect(hasNavy(ca.border) || hasNavy(ca.shadow), `lead card navy ${ca.border} ${ca.shadow}`).toBe(true);

    // Account: points, % and status pill neutral; segmented "on" (choice) neutral.
    await open(page, '/account.html', size);
    await ready.account(page);
    const acct = await page.evaluate(() => {
      const s = (sel) => getComputedStyle(document.querySelector(sel));
      return {
        total: s('.gp-total').color,
        status: s('.acct-status').color + ' ' + s('.acct-status').backgroundColor + ' ' + s('.acct-status').borderTopColor,
        pct: s('.arch-pct').color,
        segOn: s('.seg span.on').backgroundColor + ' ' + s('.seg span.on').color,
        avatar: s('.acct-avatar').backgroundImage,
      };
    });
    for (const [k, v] of Object.entries(acct)) {
      expect(hasOrange(v) || hasGreen(v), `account ${k} ${v}`).toBe(false);
    }
    expect(hasNavy(acct.avatar) || hasTint(acct.avatar), `avatar not a colour wash ${acct.avatar}`).toBe(false);
  });
});
