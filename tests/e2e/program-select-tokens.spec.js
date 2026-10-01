const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

// Program select (franchise-select-team.html) on gob tokens + colour law,
// matching Team Builder: Enter Franchise / Take This Slot = green Advance,
// selection = navy, chips / filters / tiers / links neutral, team colour only
// in the team's own art. Visual only: teams come from the e2e server; drafts
// and app-config are stubbed; nothing is claimed.
// PROGRAM_SELECT_BEFORE=1 writes before-*.png (develop CSS) and skips the guards.

test.describe.configure({ timeout: 120000 });

const OUT = path.join(__dirname, '../../reports/program-select-tokens');
const CAPTURE_BEFORE = process.env.PROGRAM_SELECT_BEFORE === '1';
const PREFIX = CAPTURE_BEFORE ? 'before' : 'after';
const SIZES = [
  { w: 1280, h: 720 },
  { w: 1920, h: 1080 },
];

function parseRgba(value) {
  const v = String(value);
  let m = v.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (m) return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] == null ? 1 : Number(m[4]) };
  m = v.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*\)/i);
  if (m) return { r: Number(m[1]) * 255, g: Number(m[2]) * 255, b: Number(m[3]) * 255, a: m[4] == null ? 1 : Number(m[4]) };
  return null;
}
const paints = (v) => String(v).match(/rgba?\([^)]*\)|color\(srgb[^)]*\)/gi) || [];
const isOrange = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.08 && p.r > 200 && p.g > 100 && p.g < 200 && p.b < 110; };
const isGreen = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.g > 180 && p.r < 150 && p.b < 150; };
const isYellow = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.r > 200 && p.g > 180 && p.b < 100; };
const isNavy = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.b > p.r + 30 && p.b > p.g + 15; };
const isRed = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.r > 200 && p.g < 190 && p.b < 190 && p.r - p.g > 50; };
const hasOrange = (v) => paints(v).some(isOrange);
const hasGreen = (v) => paints(v).some(isGreen);
const hasYellow = (v) => paints(v).some(isYellow);
const hasNavy = (v) => paints(v).some(isNavy);

// 128 synthetic programs (16 conferences x 8), named after real art folders so
// the banner cards load. The e2e seed has no teams.
const ART = fs.readdirSync(path.join(__dirname, '../../FrontEnd/static/images/teams'))
  .filter((d) => d !== 'general' && /^[a-z]/.test(d)).sort().slice(0, 128);
const TEAMS = ART.map((slug, i) => ({
  object_id: 'e2e-team-' + i,
  team_id: 'e2e-team-' + i,
  name: slug.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
  mascot: 'Program ' + (i + 1),
  conference: Math.floor(i / 8) + 1,
  total_player_attrs: 5000 + ((i * 37) % 128) * 11,
  prestige: ((i * 53) % 100) + 1,
  height_band: (i % 5) + 1,
  class_band: ((i * 3) % 5) + 1,
}));

async function installApi(page, opts) {
  const o = opts || {};
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
    if (pathname === '/app-config') return json({ isAlpha: true, alphaDisclaimer: null, version: '1.0', sentryDsn: null, teamBuilderEnabled: true });
    if (pathname === '/franchise/team-builder/drafts' && req.method() === 'GET') return json({ drafts: o.drafts || [] });
    if (pathname === '/teams') return json(TEAMS);
    if (pathname === '/api/auth/me') return json({ user_id: 'e2e-user', username: 'e2e', fte_v2_complete: true });
    await route.continue();
  });
}

async function open(page, url, size, opts) {
  await page.setViewportSize({ width: size.w, height: size.h });
  await stubAuth(page);
  await installApi(page, opts);
  await page.goto(url, { waitUntil: 'load' });
  await page.locator('.pg').first().waitFor();
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

async function shot(page, name, size) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(0, 0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-${size.w}.png`) });
}

async function firstTeamId(page) {
  return page.evaluate(async () => {
    const teams = await window.TeamPicker.fetchTeams();
    const t = (teams || [])[0] || {};
    return { id: String(t.object_id || t._id || t.team_id || ''), name: t.name || 'Program' };
  });
}

async function selectFirst(page) {
  await page.locator('.pg:not(.out)').first().click();
  await page.locator('#action-bar.up #ab-primary').waitFor();
}

async function setFilter(page) {
  const sel = page.locator('#filter-talent');
  const values = await sel.locator('option').evaluateAll((os) => os.map((o) => o.value).filter((v) => v && v !== '0'));
  await sel.selectOption(values[0]);
  await page.locator('.fsel.on').first().waitFor();
}

test.describe('program select tokens', () => {
  for (const size of SIZES) {
    test(`shots ${size.w}`, async ({ page }) => {
      await open(page, '/franchise-select-team.html', size);
      await shot(page, 'browse', size);
      await selectFirst(page);
      await shot(page, 'selected', size);
      await page.locator('#ab-clear').click();
      await setFilter(page);
      await shot(page, 'filtered', size);

      await open(page, '/franchise-select-team.html?builder=1', size);
      await page.locator('#mode-banner:not([hidden])').waitFor();
      await selectFirst(page);
      await shot(page, 'builder-selected', size);

      await open(page, '/franchise-select-team.html', size);
      const team = await firstTeamId(page);
      await open(page, '/franchise-select-team.html', size, {
        drafts: [{ replaced_object_id: team.id, identity: { name: 'Riverside Owls' }, build_mode: 'replace' }],
      });
      await page.locator('#unfinished-draft:not([hidden])').waitFor();
      await shot(page, 'draft', size);
    });
  }

  test('colour law guards', async ({ page }) => {
    test.skip(CAPTURE_BEFORE, 'before capture');
    const size = SIZES[0];

    await open(page, '/franchise-select-team.html', size);
    const base = await page.evaluate(() => {
      const s = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el) : null; };
      const tiers = Array.from(document.querySelectorAll('.pg .top1 span, .pg .top1t span')).slice(0, 6).map((el) => getComputedStyle(el).color);
      return {
        gob: document.documentElement.classList.contains('gob'),
        text100: getComputedStyle(document.documentElement).getPropertyValue('--text-100').trim(),
        tbe: s('.tbe').backgroundImage + ' ' + s('.tbe').borderTopColor,
        openTb: s('#open-team-builder').backgroundColor,
        back: s('#team-select-back-link').color,
        tiers,
        title: s('#page-title').fontFamily,
      };
    });
    expect(base.gob, 'html.gob').toBe(true);
    expect(base.text100).not.toBe('');
    expect(base.title).toMatch(/Bebas Neue/);
    expect(hasOrange(base.tbe), `Team Builder entry not orange ${base.tbe}`).toBe(false);
    expect(hasOrange(base.openTb) || hasGreen(base.openTb), `Open Team Builder neutral ${base.openTb}`).toBe(false);
    expect(hasOrange(base.back), `back link ${base.back}`).toBe(false);
    expect(base.tiers.length, 'top-tier markers rendered').toBeGreaterThan(0);
    for (const c of base.tiers) expect(hasOrange(c) || hasYellow(c), `tier marker neutral ${c}`).toBe(false);

    // Search focus + active filter (choice controls) neutral.
    await page.locator('#filter-search').focus();
    const focus = await page.locator('#filter-search').evaluate((el) => getComputedStyle(el).borderTopColor);
    expect(hasOrange(focus), `search focus ${focus}`).toBe(false);
    await setFilter(page);
    const fil = await page.evaluate(() => {
      const s = getComputedStyle(document.querySelector('.fsel.on select'));
      const c = document.getElementById('filter-clear');
      return { on: s.borderTopColor + ' ' + s.backgroundColor, clear: c ? getComputedStyle(c).color : '' };
    });
    expect(hasOrange(fil.on), `active filter ${fil.on}`).toBe(false);
    expect(hasOrange(fil.clear), `Clear ${fil.clear}`).toBe(false);

    // Selection is navy; Enter Franchise is the green Advance; Scout/Clear ghost.
    await page.locator('#filter-clear').click();
    await selectFirst(page);
    const sel = await page.evaluate(() => {
      const card = getComputedStyle(document.querySelector('.pg.sel'));
      const check = document.querySelector('.pg.sel .pg-check');
      const cta = getComputedStyle(document.getElementById('ab-primary'));
      return {
        border: card.borderTopColor,
        shadow: card.boxShadow,
        check: check ? getComputedStyle(check).backgroundColor : '',
        cta: cta.backgroundColor,
        ctaInk: cta.color,
        scout: getComputedStyle(document.getElementById('ab-scout')).backgroundColor,
      };
    });
    expect(hasOrange(sel.border) || hasOrange(sel.shadow), `selected card not orange ${sel.border} ${sel.shadow}`).toBe(false);
    expect(hasNavy(sel.border) || hasNavy(sel.shadow), `selected card navy ${sel.border} ${sel.shadow}`).toBe(true);
    if (sel.check) expect(hasOrange(sel.check), `check ${sel.check}`).toBe(false);
    expect(isGreen(sel.cta), `Enter Franchise green ${sel.cta}`).toBe(true);
    const ink = parseRgba(sel.ctaInk);
    expect(ink && ink.r < 60 && ink.g < 60 && ink.b < 60, `Enter Franchise dark ink ${sel.ctaInk}`).toBe(true);
    expect(hasOrange(sel.scout) || hasGreen(sel.scout), `Scout ghost ${sel.scout}`).toBe(false);
    // Hovering a card is a choice affordance: neutral border.
    await page.locator('.pg:not(.sel):not(.out)').nth(1).hover();
    const hover = await page.locator('.pg:not(.sel):not(.out)').nth(1).evaluate((el) => getComputedStyle(el).borderTopColor);
    expect(hasOrange(hover), `card hover ${hover}`).toBe(false);

    // Builder mode: banner neutral, Take This Slot is Team Builder's Continue (green).
    await open(page, '/franchise-select-team.html?builder=1', size);
    await page.locator('#mode-banner:not([hidden])').waitFor();
    const banner = await page.evaluate(() => {
      const b = getComputedStyle(document.getElementById('mode-banner'));
      return {
        bg: b.backgroundImage + ' ' + b.backgroundColor + ' ' + b.borderBottomColor,
        k: getComputedStyle(document.querySelector('.mb-k')).color,
        h1: getComputedStyle(document.getElementById('page-title')).color,
      };
    });
    for (const [k, v] of Object.entries(banner)) expect(hasOrange(v), `builder ${k} ${v}`).toBe(false);
    await selectFirst(page);
    const slot = await page.locator('#ab-primary').evaluate((el) => ({ text: el.textContent, bg: getComputedStyle(el).backgroundColor }));
    expect(slot.text).toMatch(/Take This Slot/);
    expect(isGreen(slot.bg), `Take This Slot green ${slot.bg}`).toBe(true);

    // Unfinished draft card: no blue wash; Continue neutral.
    await open(page, '/franchise-select-team.html', size);
    const team = await firstTeamId(page);
    await open(page, '/franchise-select-team.html', size, {
      drafts: [{ replaced_object_id: team.id, identity: { name: 'Riverside Owls' }, build_mode: 'replace' }],
    });
    await page.locator('#unfinished-draft:not([hidden])').waitFor();
    const draft = await page.evaluate(() => ({
      card: getComputedStyle(document.getElementById('unfinished-draft')).backgroundColor + ' ' + getComputedStyle(document.getElementById('unfinished-draft')).borderTopColor,
      cont: getComputedStyle(document.getElementById('draft-continue')).backgroundColor,
    }));
    expect(hasNavy(draft.card), `draft card not blue ${draft.card}`).toBe(false);
    expect(hasOrange(draft.cont) || hasGreen(draft.cont), `draft Continue neutral ${draft.cont}`).toBe(false);

    // Error red; loading indicator neutral.
    const misc = await page.evaluate(() => {
      const err = document.getElementById('team-select-error');
      err.hidden = false;
      err.textContent = 'Could not claim that program.';
      const load = document.getElementById('team-select-loading');
      load.hidden = false;
      const dot = load.querySelector('.team-select-loading-indicator span');
      return {
        err: getComputedStyle(err).color,
        errBorder: getComputedStyle(err).borderTopColor,
        dot: dot ? getComputedStyle(dot).backgroundColor : '',
      };
    });
    expect(isRed(misc.err), `error text ${misc.err}`).toBe(true);
    expect(isRed(misc.errBorder), `error border ${misc.errBorder}`).toBe(true);
    if (misc.dot) expect(hasOrange(misc.dot), `loading dot ${misc.dot}`).toBe(false);
  });
});
