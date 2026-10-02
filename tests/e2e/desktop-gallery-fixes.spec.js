/**
 * Gallery fixes (reports/screen-gallery-2026-10-01.md #2 #4 #5 #6 #8 #10) on the
 * desktop SQLite server: a real Week-1 franchise, the same state the gallery shot.
 * Run with playwright.desktop.config.js (desktop-*.spec.js).
 * GALLERY_FIXES_BEFORE=1 writes before-*.png + before-metrics.json and skips the guards.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || process.env.GOB_LOOPBACK_PORT || '8767';
const OUT = path.join(__dirname, '../../reports/gallery-fixes');
const BEFORE = process.env.GALLERY_FIXES_BEFORE === '1';
const PREFIX = BEFORE ? 'before' : 'after';

test.describe.configure({ mode: 'serial', timeout: 180000 });

function parseRgba(value) {
  const v = String(value);
  let m = v.match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (m) return { r: +m[1], g: +m[2], b: +m[3], a: m[4] == null ? 1 : +m[4] };
  m = v.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\s*\)/i);
  if (m) return { r: m[1] * 255, g: m[2] * 255, b: m[3] * 255, a: m[4] == null ? 1 : +m[4] };
  return null;
}
const isOrange = (c) => { const p = parseRgba(c); return !!p && p.a >= 0.1 && p.r > 200 && p.g > 100 && p.g < 200 && p.b < 110; };

let ctx = null;

async function prime(page) {
  await page.addInitScript((port) => {
    window.GOB_BUILD_PROFILE = 'desktop';
    window.GOB_LOOPBACK_PORT = Number(port);
    window.alert = () => {};
  }, PORT);
}

async function open(page, url, w, waitFor) {
  await page.setViewportSize({ width: w, height: w === 1280 ? 720 : 1080 });
  await prime(page);
  await page.goto(url);
  if (waitFor) await page.locator(waitFor).first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(2500);
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

async function shot(page, name, w) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(0, 0);
  await page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('.main').forEach((m) => { m.scrollTop = 0; }); });
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-${w}.png`) });
}

test.beforeAll(async ({ request }) => {
  const create = await request.post('/franchise/select-team', { data: { team_name: 'Lancaster' } });
  expect(create.ok(), await create.text()).toBeTruthy();
  const fid = (await create.json()).franchise_id;
  const next = await request.post('/franchise/play-next-game', { data: { franchise_id: fid } });
  const m = await next.json();
  const tid = String(m.home === 'Lancaster' ? m.home_id : m.away_id);
  const q = (extra) => new URLSearchParams(Object.assign({ franchise_id: fid, team_id: tid, user_team_id: tid }, extra || {})).toString();
  ctx = {
    fid, tid, q,
    fcc: (tab) => `/franchise-command-center.html?${q({ tab })}`,
    lineup: `/set-lineup.html?${q({ mode: 'franchise', week: String(m.week || 1), home: m.home, away: m.away, home_id: String(m.home_id), away_id: String(m.away_id), my_team: m.home === 'Lancaster' ? 'home' : 'away' })}`,
  };
});

const metrics = {};
test.afterAll(async ({ request }) => {
  // Leave the shared desktop e2e sqlite as we found it (two-franchise cap).
  if (ctx && ctx.fid) await request.delete('/franchise/' + ctx.fid).catch(() => {});
  if (BEFORE) {
    fs.mkdirSync(OUT, { recursive: true });
    fs.writeFileSync(path.join(OUT, 'before-metrics.json'), JSON.stringify(metrics, null, 2) + '\n');
  }
});

test('#4 box score back link', async ({ page }) => {
  await open(page, `/box-score.html?${ctx.q({ mode: 'franchise' })}`, 1280, '#locker-room-button');
  const m = await page.evaluate(() => {
    const b = document.getElementById('locker-room-button');
    const s = getComputedStyle(b);
    const card = document.querySelector('#box-score-container .box-score-header, #box-score-container > :not(#locker-room-button)');
    const br = b.getBoundingClientRect();
    const cr = card ? card.getBoundingClientRect() : null;
    return { bg: s.backgroundColor, border: s.borderTopStyle + ' ' + s.borderTopColor, color: s.color, font: s.fontFamily,
      className: b.className, overlapsCard: !!cr && br.bottom > cr.top && br.top < cr.bottom && br.right > cr.left && br.left < cr.right };
  });
  metrics.box = m;
  await shot(page, 'box-score', 1280);
  if (BEFORE) return;
  expect(m.className).toMatch(/brand-back-link/);
  const bg = parseRgba(m.bg);
  expect(!bg || bg.a < 0.05, `transparent ghost link, got ${m.bg}`).toBe(true);
  expect(m.overlapsCard, 'back link does not overlap the first card').toBe(false);
  expect(isOrange(m.color)).toBe(false);
});

test('#5 cut players', async ({ page }) => {
  await open(page, `/cut-players.html?${ctx.q({ mode: 'franchise' })}`, 1280, '#cut-players-body tr');
  await page.waitForTimeout(1000);
  const m = await page.evaluate(() => {
    const s = (el) => (el ? getComputedStyle(el) : null);
    const back = s(document.getElementById('back-btn'));
    const submit = document.getElementById('submit-btn');
    const ss = s(submit);
    const h1 = s(document.querySelector('.cut-players-header h1'));
    const modalBtn = document.querySelector('#cut-modal-actions button');
    const accent = document.getElementById('cut-modal-accent');
    return {
      back: back.color + ' ' + back.backgroundColor,
      submitDisabled: submit.disabled || submit.classList.contains('is-dead'),
      submitBg: ss.backgroundColor,
      h1Font: h1.fontFamily,
      modalOpen: !!document.querySelector('#cut-modal-backdrop.is-visible, #cut-modal-backdrop[aria-hidden="false"]'),
      modalBtnText: modalBtn ? modalBtn.textContent : '',
      modalBtnBg: modalBtn ? s(modalBtn).backgroundColor : '',
      accentBg: accent ? s(accent).backgroundColor : '',
    };
  });
  metrics.cut = m;
  await shot(page, 'cut-players', 1280);
  if (BEFORE) return;
  expect(isOrange(m.back)).toBe(false);
  expect(m.h1Font).toMatch(/Bebas Neue/);
  if (m.submitDisabled) expect(isOrange(m.submitBg), `disabled Assign is dead, got ${m.submitBg}`).toBe(false);
  if (/Locker Room/i.test(m.modalBtnText)) {
    expect(isOrange(m.modalBtnBg), `navigation button in the modal is not orange, got ${m.modalBtnBg}`).toBe(false);
    expect(isOrange(m.accentBg) || /255, 109, 109/.test(m.accentBg), `no-error modal has a neutral accent, got ${m.accentBg}`).toBe(false);
  }
});

test('#8 player stats fits or cues at 1280', async ({ page }) => {
  await open(page, ctx.fcc('player-stats-view'), 1280, '#player-stats-view .gob-tbl tbody tr');
  const m = await page.evaluate(() => {
    const sc = document.querySelector('#player-stats-view .gob-scroll');
    const tbl = sc.querySelector('.gob-tbl');
    const main = document.querySelector('.main') || document.body;
    const mr = main.getBoundingClientRect();
    const tr = tbl.getBoundingClientRect();
    const cs = getComputedStyle(sc);
    return {
      scrollW: sc.scrollWidth, clientW: sc.clientWidth, overflowX: cs.overflowX,
      tableRight: Math.round(tr.right), mainRight: Math.round(mr.right),
      cueClass: sc.className, cueShadow: cs.boxShadow,
      lastHeaderRight: Math.round(Array.from(tbl.querySelectorAll('thead tr:last-child th')).pop().getBoundingClientRect().right),
      lastHeaderTextRight: (() => {
        const th = Array.from(tbl.querySelectorAll('thead tr:last-child th')).pop();
        const r = document.createRange(); r.selectNodeContents(th);
        return Math.round(r.getBoundingClientRect().right);
      })(),
      cardRight: Math.round(document.querySelector('#player-stats-view .gob-tcard').getBoundingClientRect().right),
      lastPadRight: parseFloat(getComputedStyle(Array.from(tbl.querySelectorAll('thead tr:last-child th')).pop()).paddingRight),
      lastCellPadRight: parseFloat(getComputedStyle(tbl.querySelector('tbody tr td:last-child')).paddingRight),
      viewport: window.innerWidth,
    };
  });
  metrics.playerStats = m;
  await shot(page, 'player-stats', 1280);
  if (BEFORE) return;
  // Gallery: the last column sat on the card's rounded edge and read as clipped.
  expect(m.cardRight - m.lastHeaderTextRight, `last header clears the card edge: ${JSON.stringify(m)}`).toBeGreaterThanOrEqual(8);
  // Not an overflow (the table fits; see the gallery-fixes report): the last column
  // just had no breathing room against the card's rounded edge.
  expect(m.lastPadRight, 'last header has right padding').toBeGreaterThanOrEqual(12);
  expect(m.lastCellPadRight, 'last cell has right padding').toBeGreaterThanOrEqual(12);
  const fits = m.lastHeaderRight <= m.viewport && m.scrollW <= m.clientW + 1;
  const cued = m.scrollW > m.clientW + 1 && /can-r/.test(m.cueClass) && m.cueShadow !== 'none';
  expect(fits || cued, `fits (${m.lastHeaderRight}<=${m.viewport}) or shows a right scroll cue: ${JSON.stringify(m)}`).toBe(true);
});

for (const w of [1280, 1920]) {
  test(`#2 set lineup banner ${w}`, async ({ page }) => {
    await open(page, ctx.lineup, w, '.roster-table tbody tr');
    const m = await page.evaluate(() => {
      const img = document.querySelector('.team-banner-image');
      if (!img) return { img: false };
      const s = getComputedStyle(img);
      const strip = img.closest('.lineup-banner-strip').getBoundingClientRect();
      return { img: true, fit: s.objectFit, natural: [img.naturalWidth, img.naturalHeight], box: [Math.round(strip.width), Math.round(strip.height)] };
    });
    metrics['lineup' + w] = m;
    await shot(page, 'set-lineup', w);
    if (BEFORE || !m.img) return;
    expect(m.fit, 'banner shows the whole lockup (no crop)').toBe('contain');
  });
}

test('#10 roster toggle spacing', async ({ page }) => {
  await open(page, ctx.fcc('roster-view'), 1280, '.stats-toggle button em');
  const m = await page.evaluate(() => Array.from(document.querySelectorAll('.stats-toggle button')).map((b) => {
    const em = b.querySelector('em');
    const range = document.createRange();
    range.selectNodeContents(b.firstChild);
    return { label: b.textContent, gap: Math.round(em.getBoundingClientRect().left - range.getBoundingClientRect().right) };
  }));
  metrics.rosterToggle = m;
  await shot(page, 'roster', 1280);
  if (BEFORE) return;
  for (const b of m) expect(b.gap, `space between label and count: ${b.label}`).toBeGreaterThanOrEqual(5);
});

test('#10 office moved-most placeholder', async ({ page }) => {
  // Week 1 no longer shows the Team snapshot card (2026-10-02): before camp it could only
  // say "Set after camp". So the placeholder is not there at all, let alone twice.
  await open(page, ctx.fcc('home-tab'), 1280, '#office-root .office-col .card');
  const m = await page.evaluate(() => Array.from(document.querySelectorAll('.msr')).filter((r) => /Set after camp/.test(r.textContent)).length);
  metrics.officeSetAfterCamp = m;
  await shot(page, 'office', 1280);
  if (BEFORE) return;
  expect(m, 'no "Set after camp" line in week 1').toBe(0);
  expect(await page.locator('#office-root .office-snap').count(), 'no Team snapshot card in week 1').toBe(0);
});

// Awards is not an empty state in week 1 any more: since the All-American projection
// it shows "Projected All-Americans · Preseason", three teams of five by position.
test('#10/#6 awards: the week-1 preseason projection, not an empty card', async ({ page }) => {
  await open(page, ctx.fcc('awards-view'), 1280, '#awards-view');
  await page.waitForTimeout(1500);
  const view = page.locator('#awards-view');
  const m = await view.evaluate((host) => {
    const shown = (el) => !!el.offsetParent;
    const tables = Array.from(host.querySelectorAll('table.gob-awards-tbl')).filter(shown);
    return {
      empties: Array.from(host.querySelectorAll('.gob-empty')).filter(shown).length,
      heading: (host.querySelector('.gob-awards-head h2') || {}).textContent || '',
      status: (host.querySelector('.gob-awards-head p') || {}).textContent || '',
      teams: Array.from(host.querySelectorAll('.gob-awards > section > h3')).map((el) => el.textContent.trim()),
      rows: tables.map((table) => table.querySelectorAll('tbody tr').length),
      positions: tables.map((table) => Array.from(table.querySelectorAll('tbody td.gob-awards-pos')).map((el) => el.textContent.trim()).join(' ')),
      heads: tables[0] ? Array.from(tables[0].querySelectorAll('thead th')).map((el) => el.textContent.trim()) : [],
      colours: Array.from(host.querySelectorAll('.gob-awards-head *, .gob-awards h3')).map((el) => getComputedStyle(el).color),
    };
  });
  metrics['awards-week-1'] = m;
  await shot(page, 'awards', 1280);
  if (BEFORE) return;
  expect(m.empties, 'no empty card: the projection is there in week 1').toBe(0);
  expect(m.heading).toBe('Projected All-Americans');
  expect(m.status).toContain('Preseason');
  expect(m.teams).toEqual(['1st Team All-American', '2nd Team All-American', '3rd Team All-American']);
  // One player per position on each team; nobody has played, so there are no stat columns.
  expect(m.rows).toEqual([5, 5, 5]);
  expect(m.positions).toEqual(['PG SG SF PF C', 'PG SG SF PF C', 'PG SG SF PF C']);
  // No stat columns in the preseason, and how the teams are picked is never shown.
  expect(m.heads).toEqual(['Pos', 'Player', 'Yr', 'Team', 'RT']);
  expect(m.status.trim()).toBe('Preseason');
  m.colours.forEach((colour) => expect(isOrange(colour)).toBe(false));
});

for (const [name, tab, sel] of [
  ['practice-squad', 'practice-squad-view', '#practice-squad-view'],
  ['leaders', 'leaders-view', '#leaders-view .gob-ldr, #leaders-view'],
]) {
  test(`#10/#6 empty state: ${name}`, async ({ page }) => {
    await open(page, ctx.fcc(tab), 1280, sel);
    await page.waitForTimeout(1500);
    const m = await page.evaluate((root) => {
      const host = document.querySelector(root.split(',')[0].trim()) || document.querySelector(root);
      const empties = Array.from((host || document).querySelectorAll('.gob-empty')).filter((e) => e.offsetParent);
      const first = empties[0];
      const s = first ? getComputedStyle(first) : null;
      return { count: empties.length, bg: s ? s.backgroundColor : '', border: s ? s.borderTopStyle + ' ' + s.borderTopColor : '', radius: s ? s.borderTopLeftRadius : '', color: s ? s.color : '', text: first ? first.textContent.trim() : '' };
    }, sel);
    metrics['empty-' + name] = m;
    await shot(page, name, 1280);
    if (BEFORE) return;
    expect(m.count, `${name}: shared .gob-empty card present`).toBeGreaterThan(0);
    expect(m.border).toMatch(/^solid/);
    expect(parseFloat(m.radius)).toBeGreaterThan(0);
    expect(isOrange(m.color) || isOrange(m.bg)).toBe(false);
  });
}
