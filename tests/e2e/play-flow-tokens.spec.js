const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

// Play-flow leftovers on gob tokens + colour law, each peeled off
// resource-pages.css: training-playbooks (custom training playbook),
// playbook-report (Playbook Settings), recruit player-detail.
// Visual only: all data stubbed. PLAY_FLOW_BEFORE=1 writes before-*.png
// (develop CSS) and skips the guards.

test.describe.configure({ timeout: 120000 });

const FIXTURE = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/prep-plan.json'), 'utf8'));
const FID = FIXTURE.franchise_id;
const TID = FIXTURE.cc.team_id;
const OUT = path.join(__dirname, '../../reports/play-flow-tokens');
const CAPTURE_BEFORE = process.env.PLAY_FLOW_BEFORE === '1';
const PREFIX = CAPTURE_BEFORE ? 'before' : 'after';
const BEFORE_METRICS = path.join(__dirname, 'fixtures/play-flow-before-metrics.json');
const SIZES = [
  { w: 1280, h: 720 },
  { w: 1920, h: 1080 },
];

const RECRUIT = {
  _id: 'e2e-recruit-1',
  is_recruit: true,
  first_name: 'Marcus',
  last_name: 'Hale',
  name: 'Marcus Hale',
  position: 'SG',
  year: 'Jr',
  height_in: 76,
  weight: 190,
  archetype: 'Shooter',
  lean_display: 'Leaning you',
  signed_display: 'Unsigned',
  attributes: { SC: 72, SH: 81, ID: 55, OD: 63, PS: 70, BH: 78, RB: 44, ST: 52, AG: 74, ND: 61, IQ: 66, FT: 79 },
  position_ratings: { PG: 6.8, SG: 7.9, SF: 6.1, PF: 4.5, C: 3.2 },
};

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
const isGreen = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.g > 150 && p.r < 150 && p.b < 150; };
const isNavy = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.b > p.r + 30 && p.b > p.g + 15; };
const isRed = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.r > 200 && p.g < 190 && p.b < 190 && p.r - p.g > 50; };
const isTinted = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.05 && Math.max(p.r, p.g, p.b) - Math.min(p.r, p.g, p.b) > 24; };
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
    if (pathname === '/api/playbooks' && req.method() === 'GET') return json(FIXTURE.playbooks);
    if (pathname === '/api/playbooks') return json({ success: true });
    if (pathname === '/franchise/play-next-game') return json({ opponent: 'Bentley-Truman', user_team: 'Lancaster', home_team: 'Lancaster', away_team: 'Bentley-Truman' });
    if (pathname.startsWith('/recruit/')) return json(RECRUIT);
    if (pathname === '/api/auth/me') return json({ user_id: 'e2e-user', username: 'e2e', fte_v2_complete: true });
    if (pathname === '/app-config') return json({ isAlpha: false, alphaDisclaimer: null, version: '1.0', sentryDsn: null, teamBuilderEnabled: true });
    await route.continue();
  });
}

const URLS = {
  training: `/training-playbooks.html?franchise_id=${FID}&team_id=${TID}&mode=franchise`,
  report: `/playbook-report.html?franchise_id=${FID}&team_id=${TID}&mode=franchise`,
  recruit: `/player-detail.html?recruit_id=${RECRUIT._id}&franchise_id=${FID}`,
};

async function open(page, url, size) {
  await page.setViewportSize({ width: size.w, height: size.h });
  await stubAuth(page);
  await page.addInitScript(() => { window.alert = () => {}; });
  await installApi(page);
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

const ready = {
  training: (page) => page.locator('.tp-card').first().waitFor(),
  report: (page) => page.locator('.report-row').first().waitFor(),
  recruit: (page) => page.locator('.pd-shell').first().waitFor(),
};

async function shot(page, name, size) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(0, 0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(700);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-${size.w}.png`) });
}

// Shell geometry and title type, measured on develop (BEFORE) and held after the peel.
async function shellMetrics(page) {
  return page.evaluate(() => {
    const shell = document.querySelector('.resource-page-container.fcc-brand-page-shell');
    const r = shell.getBoundingClientRect();
    const h1 = shell.querySelector('h1');
    const cs = getComputedStyle(shell);
    return {
      x: Math.round(r.left),
      w: Math.round(r.width),
      pad: [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].join(' '),
      radius: getComputedStyle(shell, '::before').borderTopLeftRadius,
      h1Size: h1 ? getComputedStyle(h1).fontSize : '',
      h1Margin: h1 ? getComputedStyle(h1).marginBottom : '',
    };
  });
}

async function selectTrainingCard(page) {
  const card = page.locator('.tp-card:not(.is-disabled):not(.is-selected)').first();
  await card.click();
  await page.locator('.tp-card.is-selected').first().waitFor();
}

test.describe('play-flow tokens', () => {
  for (const size of SIZES) {
    test(`shots ${size.w}`, async ({ page }) => {
      const metrics = {};
      await open(page, URLS.training, size);
      await ready.training(page);
      metrics.training = await shellMetrics(page);
      await shot(page, 'training-playbooks', size);
      await selectTrainingCard(page);
      await shot(page, 'training-playbooks-selected', size);

      await open(page, URLS.report, size);
      await ready.report(page);
      metrics.report = await shellMetrics(page);
      await shot(page, 'playbook-report', size);

      await open(page, URLS.recruit, size);
      await ready.recruit(page);
      metrics.recruit = await shellMetrics(page);
      await shot(page, 'recruit-detail', size);

      if (CAPTURE_BEFORE) {
        const all = fs.existsSync(BEFORE_METRICS) ? JSON.parse(fs.readFileSync(BEFORE_METRICS, 'utf8')) : {};
        all[size.w] = metrics;
        fs.writeFileSync(BEFORE_METRICS, JSON.stringify(all, null, 2) + '\n');
      } else if (fs.existsSync(BEFORE_METRICS)) {
        const before = JSON.parse(fs.readFileSync(BEFORE_METRICS, 'utf8'))[size.w];
        for (const key of Object.keys(metrics)) {
          expect(metrics[key], `${key} @${size.w}: shell geometry + title type unchanged by the peel`).toEqual(before[key]);
        }
      }
    });
  }

  test('colour law guards', async ({ page }) => {
    test.skip(CAPTURE_BEFORE, 'before capture');
    const size = SIZES[0];

    // All three: html.gob, peeled off resource-pages.css, shell geometry kept.
    for (const [key, url] of Object.entries(URLS)) {
      await open(page, url, size);
      await ready[key](page);
      const t = await page.evaluate(() => {
        const shell = document.querySelector('.resource-page-container.fcc-brand-page-shell');
        const r = shell.getBoundingClientRect();
        const h1 = shell.querySelector('h1');
        return {
          gob: document.documentElement.classList.contains('gob'),
          text100: getComputedStyle(document.documentElement).getPropertyValue('--text-100').trim(),
          resourcePages: !!document.querySelector('link[href*="resource-pages.css"]'),
          shellW: Math.round(r.width),
          shellPadL: getComputedStyle(shell).paddingLeft,
          shellBg: getComputedStyle(shell, '::before').backgroundColor,
          h1Size: h1 ? getComputedStyle(h1).fontSize : '',
          h1Font: h1 ? getComputedStyle(h1).fontFamily : '',
        };
      });
      expect(t.gob, `${key} html.gob`).toBe(true);
      expect(t.text100, `${key} tokens`).not.toBe('');
      expect(t.resourcePages, `${key} no longer loads resource-pages.css`).toBe(false);
      expect(hasTint(t.shellBg), `${key} shell surface neutral ${t.shellBg}`).toBe(false);
      if (t.h1Font) expect(t.h1Font).toMatch(/Bebas Neue/);
    }

    // Training playbook: selection navy, check navy, PCC chip + dock fill neutral,
    // Save & Continue orange (it saves), required-warning red.
    await open(page, URLS.training, size);
    await ready.training(page);
    await selectTrainingCard(page);
    const tp = await page.evaluate(() => {
      const s = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el) : null; };
      const sel = s('.tp-card.is-selected');
      const check = s('.tp-card.is-selected .tp-check');
      const pcc = s('.tp-chip-pcc');
      const fill = s('.tp-dock-bar-fill');
      const save = s('#tp-save');
      const warn = s('.tp-warn');
      return {
        sel: sel.borderTopColor + ' ' + sel.boxShadow,
        check: check ? check.backgroundColor + ' ' + check.borderTopColor : '',
        pcc: pcc ? pcc.color + ' ' + pcc.borderTopColor : '',
        fill: fill ? fill.backgroundColor : '',
        save: save.backgroundColor,
        warn: warn ? warn.color : '',
      };
    });
    expect(hasOrange(tp.sel), `selected card not orange ${tp.sel}`).toBe(false);
    expect(hasNavy(tp.sel), `selected card navy ${tp.sel}`).toBe(true);
    if (tp.check) expect(hasOrange(tp.check), `check ${tp.check}`).toBe(false);
    if (tp.pcc) expect(hasOrange(tp.pcc), `PCC chip ${tp.pcc}`).toBe(false);
    if (tp.fill) expect(hasOrange(tp.fill), `dock fill ${tp.fill}`).toBe(false);
    expect(isOrange(tp.save), `Save & Continue orange (a save) ${tp.save}`).toBe(true);
    if (tp.warn) expect(isRed(tp.warn), `required warning red ${tp.warn}`).toBe(true);

    // Playbook report: Edit Playbooks neutral; section rules + subheads neutral; back link neutral.
    await open(page, URLS.report, size);
    await ready.report(page);
    const rp = await page.evaluate(() => {
      const s = (sel) => getComputedStyle(document.querySelector(sel));
      return {
        edit: s('#edit-btn').backgroundImage + ' ' + s('#edit-btn').backgroundColor,
        h2: s('.report-section-head h2').borderBottomColor,
        h3: s('.report-subsection h3').color + ' ' + s('.report-subsection h3').borderBottomColor,
        back: s('#back-btn').color,
      };
    });
    for (const [k, v] of Object.entries(rp)) expect(hasOrange(v) || hasGreen(v), `report ${k} ${v}`).toBe(false);

    // Recruit detail: overall, primary position value, section headers neutral;
    // position pills carry no per-position colour.
    await open(page, URLS.recruit, size);
    await ready.recruit(page);
    const pd = await page.evaluate(() => {
      const s = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el) : null; };
      const pills = Array.from(document.querySelectorAll('.pd-pos-pill')).map((el) => {
        const c = getComputedStyle(el);
        return c.backgroundColor + ' ' + c.color;
      });
      return {
        overall: s('.pd-overall-value') ? s('.pd-overall-value').color : '',
        primary: s('.pd-pos-rating-value.is-primary') ? s('.pd-pos-rating-value.is-primary').color : '',
        header: s('.pd-section-header') ? s('.pd-section-header').color + ' ' + s('.pd-section-header').borderBottomColor : '',
        pills,
      };
    });
    for (const k of ['overall', 'primary', 'header']) {
      if (pd[k]) expect(hasOrange(pd[k]), `recruit ${k} ${pd[k]}`).toBe(false);
    }
    expect(pd.pills.length, 'position pills rendered').toBeGreaterThan(0);
    for (const v of pd.pills) expect(hasTint(v), `position pill neutral ${v}`).toBe(false);
  });
});
