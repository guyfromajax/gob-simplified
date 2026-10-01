const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

// Tutorials / FTE on gob tokens + colour law.
// TUTORIALS_FTE_BEFORE=1 writes before-*.png (run on origin/develop CSS) and skips the guards.

test.describe.configure({ timeout: 120000 });

const OUT = path.join(__dirname, '../../reports/tutorials-fte-tokens');
const CAPTURE_BEFORE = process.env.TUTORIALS_FTE_BEFORE === '1';
const PREFIX = CAPTURE_BEFORE ? 'before' : 'after';
const SIZES = [
  { w: 1280, h: 720 },
  { w: 1920, h: 1080 },
];

const ME = {
  user_id: 'e2e-user',
  username: 'e2e',
  email: 'e2e@example.com',
  fte_v2_complete: true,
  tutorial_state: { team_pick: 'Lancaster' },
};

const OPPONENTS = {
  user_team: 'Lancaster',
  conference: 3,
  default_opponent: 'Bentley-Truman',
  opponents: [
    { name: 'Bentley-Truman', rank: 1, mascot: 'Bulldogs', primary_color: '#7a1f2b' },
    { name: 'Ocean City', rank: 2, mascot: 'Red Raiders', primary_color: '#1f4f7a' },
    { name: 'Morristown', rank: 3, mascot: 'Colonials', primary_color: '#2f6b3a' },
    { name: 'Xavien', rank: 4, mascot: 'Knights', primary_color: '#5a3f8c' },
  ],
};

function parseRgba(value) {
  const m = String(value).match(/rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)/i);
  if (!m) return null;
  return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a: m[4] == null ? 1 : Number(m[4]) };
}

function allPaints(value) {
  return String(value).match(/rgba?\([^)]*\)/gi) || [];
}

function isOrange(rgb) {
  const p = parseRgba(rgb);
  if (!p || p.a < 0.1) return false;
  return p.r > 200 && p.g > 100 && p.g < 190 && p.b < 80;
}

function isGreen(rgb) {
  const p = parseRgba(rgb);
  if (!p || p.a < 0.1) return false;
  return p.g > 180 && p.r < 120 && p.b < 120;
}

function hasOrange(value) { return allPaints(value).some(isOrange); }
function hasGreen(value) { return allPaints(value).some(isGreen); }

async function installApi(page) {
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ME) });
      return;
    }
    if (pathname === '/api/auth/tutorial-opponents') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(OPPONENTS) });
      return;
    }
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return;
    }
    if (/googletagmanager|sentry/.test(route.request().url())) {
      await route.fulfill({ status: 204, body: '' });
      return;
    }
    await route.continue();
  });
}

async function open(page, url, size) {
  await page.setViewportSize({ width: size.w, height: size.h });
  await stubAuth(page);
  await page.addInitScript(() => {
    try {
      Object.keys(localStorage)
        .filter((k) => /attribute[-_]?tour|pgpc_sammy/i.test(k))
        .forEach((k) => localStorage.removeItem(k));
    } catch (_) {}
  });
  await installApi(page);
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

async function shot(page, name, size) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(450);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-${size.w}.png`) });
}

async function showSammy(page, opts) {
  await page.evaluate(async (o) => {
    const m = await import('/js/shared/sammyModal.js');
    m.showSammyModal({ body: 'Pick your opponent. Top is toughest.', ctaLabel: 'GOT IT', ...o });
  }, opts || {});
  await page.locator('.sammy-modal-backdrop.open .sammy-modal-btn-primary').last().waitFor();
}

async function showTipAlert(page) {
  await page.waitForFunction(() => window.GOB && typeof window.GOB.showTip === 'function');
  await page.evaluate(() => {
    window.GOB.showTip({
      alertMode: true,
      id: 'e2e-alert',
      topicLabel: 'Game Plans',
      title: 'Game Plans',
      body: 'Your game plan tells the team how to play. Two minutes.',
      href: '/tutorial-game-plans.html',
      lessonIndex: 2,
      lessonTotal: 7,
      portrait: '/images/sammy_tutorial.png',
      cta: 'Start lesson',
      laterLabel: "I'll do this later",
      onGo() {},
      onLater() {},
    });
  });
  await page.locator('.gob-talert').waitFor();
}

async function showTip(page) {
  await page.waitForFunction(() => window.GOB && typeof window.GOB.showTip === 'function');
  await page.evaluate(() => {
    window.GOB.showTip({
      id: 'e2e-tip',
      title: 'Scouting',
      body: 'Read the opponent before you set your plan.',
      portrait: '/images/sammy_tutorial.png',
      cta: 'Open lesson',
      href: '/tutorial-scouting.html',
    });
  });
  await page.locator('.gob-tip-overlay .gob-modal').waitFor();
}

async function showAttributeTour(page) {
  await page.evaluate(async () => {
    const wrap = document.createElement('div');
    wrap.id = 'e2e-tour-host';
    wrap.style.cssText = 'position:fixed;left:40px;right:40px;top:120px;z-index:5;background:#10131c;padding:12px';
    wrap.innerHTML = '<table style="width:100%;color:#fff;font:13px Inter,sans-serif"><thead><tr id="e2e-tour-row">'
      + ['NAME', 'POS', 'SC', 'SH', 'PA', 'BH', 'DE', 'RE', 'AG', 'ST'].map((t) => `<th style="padding:8px">${t}</th>`).join('')
      + '</tr></thead><tbody><tr><td>Player</td><td>PG</td><td>7</td><td>6</td><td>8</td><td>5</td><td>6</td><td>4</td><td>7</td><td>5</td></tr></tbody></table>';
    document.body.appendChild(wrap);
    const m = await import('/js/shared/attributeTour.js');
    m.showAttributeTour({ headerRow: document.getElementById('e2e-tour-row'), persistKey: 'e2e_attribute_tour_' + Date.now() });
  });
  await page.locator('.attribute-tour__sammy.is-visible').waitFor();
}

test.describe('tutorials / FTE tokens', () => {
  for (const size of SIZES) {
    test(`shots ${size.w}`, async ({ page }) => {
      // Tutorial hub and lesson chrome (eyebrow tick, bottom nav, handoff).
      await open(page, '/tutorial.html', size);
      await shot(page, 'hub', size);
      await open(page, '/tutorial-advanced-momentum.html', size);
      await shot(page, 'advanced', size);

      // Overlays on the tutorial host.
      await open(page, '/tutorial.html', size);
      await showTipAlert(page);
      await shot(page, 'alert', size);
      await open(page, '/tutorial.html', size);
      await showTip(page);
      await shot(page, 'tip', size);

      // FTE funnel screens.
      await open(page, '/tutorial-persona-intro.html', size);
      await shot(page, 'persona', size);
      await open(page, '/tutorial-pick-opponent.html', size);
      await page.locator('.sammy-modal-backdrop.open').waitFor();
      await shot(page, 'opponent-sammy', size);
      await page.locator('.sammy-modal-btn-primary').click();
      await page.locator('.opp-card[data-name="Ocean City"]').click();
      await shot(page, 'opponent-selected', size);
      await open(page, '/tutorial-situation.html?away=Bentley-Truman', size);
      await page.locator('#tipoff-moment:not([hidden])').waitFor();
      await shot(page, 'tipoff', size);

      // Shared modals on a tutorial page.
      await open(page, '/tutorial.html', size);
      await page.evaluate(async () => {
        const m = await import('/js/shared/usernameModal.js');
        m.openUsernameModal({ onSuccess() {} });
      });
      await page.locator('#username-modal-cta').waitFor();
      await shot(page, 'username', size);
      await open(page, '/tutorial.html', size);
      await page.evaluate(async () => {
        const m = await import('/js/shared/tutorialLineupModals.js');
        m.showLineupIntroModal({ teamName: 'Lancaster', onDismiss() {} });
      });
      await page.locator('.tutorial-lineup-modal-cta').waitFor();
      await shot(page, 'lineup-intro', size);
      await open(page, '/tutorial.html', size);
      await showAttributeTour(page);
      await shot(page, 'attribute-tour', size);

      // Legacy (non-.gob) host: press-conference reminder and the Sammy modal.
      await open(page, '/privacy.html', size);
      await page.evaluate(async () => {
        const m = await import('/js/phaser/utils/pgpcSammyReminderModal.js');
        m.showPgpcSammyReminderModal({ userTeamName: 'Lancaster', onGotIt() {} });
      });
      await page.locator('#pgpc-sammy-reminder-gotit').waitFor();
      await shot(page, 'pgpc-legacy-host', size);
      await open(page, '/privacy.html', size);
      await showSammy(page, { eyebrow: 'Week 3 · Invite Season', body: 'Head to the locker room.', ctaLabel: 'Go To Locker Room', primaryClass: 'is-orange' });
      await shot(page, 'sammy-legacy-host', size);
    });
  }

  test('colour law guards', async ({ page }) => {
    test.skip(CAPTURE_BEFORE, 'before capture');
    const size = SIZES[0];

    // Tutorial pages are html.gob with the tokens loaded.
    for (const url of ['/tutorial.html', '/tutorial-advanced-momentum.html', '/tutorial-persona-intro.html', '/tutorial-pick-opponent.html', '/tutorial-situation.html?away=Bentley-Truman']) {
      await open(page, url, size);
      const tok = await page.evaluate(() => ({
        gob: document.documentElement.classList.contains('gob'),
        text100: getComputedStyle(document.documentElement).getPropertyValue('--text-100').trim(),
      }));
      expect(tok.gob, `${url} html.gob`).toBe(true);
      expect(tok.text100, `${url} --text-100`).not.toBe('');
    }

    // Hub chrome: eyebrow tick, active nav icon, depth badge, selection are neutral.
    await open(page, '/tutorial.html', size);
    const hub = await page.evaluate(() => {
      const cs = (sel, prop) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el)[prop] : null;
      };
      return {
        tick: cs('.eyebrow .tick', 'backgroundColor'),
        navIco: cs('.gob-navbtn.active .ico', 'color'),
        depth: cs('.depth.foundational', 'color'),
        depthBg: cs('.depth.foundational', 'backgroundColor'),
        action: Array.from(document.querySelectorAll('.gob-btn--action')).length,
      };
    });
    if (hub.tick) expect(hasOrange(hub.tick), `tick ${hub.tick}`).toBe(false);
    if (hub.navIco) expect(hasOrange(hub.navIco), `nav ico ${hub.navIco}`).toBe(false);
    if (hub.depth) {
      expect(hasOrange(hub.depth) || hasOrange(hub.depthBg), `depth ${hub.depth}`).toBe(false);
    }
    expect(hub.action, 'no orange action buttons on the hub').toBe(0);

    // Advanced lesson: callout bar, icon, eyebrow, list bullets, handoff label.
    await open(page, '/tutorial-advanced-momentum.html', size);
    const adv = await page.evaluate(() => {
      const out = [];
      const pick = (sel, props, pseudo) => {
        document.querySelectorAll(sel).forEach((el) => {
          const s = getComputedStyle(el, pseudo || null);
          props.forEach((p) => out.push([sel + (pseudo || '') + ' ' + p, s[p]]));
        });
      };
      pick('.adv-callout', ['backgroundColor'], '::before');
      pick('.adv-callout .ac-ico', ['color', 'backgroundColor', 'borderTopColor']);
      pick('.adv-callout .ac-eyebrow', ['color']);
      pick('.info-list > li', ['backgroundColor'], '::before');
      pick('.handoff .h-l .lbl', ['color']);
      pick('.gob-btn--action', ['backgroundColor']);
      return out;
    });
    expect(adv.length).toBeGreaterThan(0);
    for (const [label, value] of adv) expect(hasOrange(value), `${label} ${value}`).toBe(false);
    // Handoff CTA is the neutral plate with dark ink (an <a> under body.gob-tut).
    const handoff = await page.locator('.handoff .gob-btn--neutral').first().evaluate((el) => {
      const s = getComputedStyle(el);
      return { bg: s.backgroundColor, ink: s.color };
    });
    const hbg = parseRgba(handoff.bg);
    const hink = parseRgba(handoff.ink);
    expect(hbg && hbg.r > 200 && hbg.g > 200 && hbg.b > 200, `handoff plate ${handoff.bg}`).toBe(true);
    expect(hink && hink.r < 60 && hink.g < 60 && hink.b < 60, `handoff ink ${handoff.ink}`).toBe(true);

    // Coach-card tutorial alert: rail, mark, portrait ring, dots, primary.
    await open(page, '/tutorial.html', size);
    await showTipAlert(page);
    const alert = await page.evaluate(() => {
      const s = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el) : null; };
      return {
        rail: s('.gob-talert-rail').backgroundImage,
        mark: s('.gob-talert-mark').color,
        portrait: s('.gob-talert-portrait').boxShadow,
        num: s('.gob-talert-num').color,
        dot: s('.gob-talert-dots i.on') ? s('.gob-talert-dots i.on').backgroundColor : '',
        primaryBg: s('.gob-talert-btn-primary').backgroundImage + ' ' + s('.gob-talert-btn-primary').backgroundColor,
        primaryShadow: s('.gob-talert-btn-primary').boxShadow,
      };
    });
    for (const [k, v] of Object.entries(alert)) expect(hasOrange(v) || hasGreen(v), `alert ${k} ${v}`).toBe(false);
    // The neutral plate keeps dark ink (body.gob-tut a { color: inherit } must not win).
    const ink = parseRgba(await page.locator('.gob-talert-btn-primary').evaluate((el) => getComputedStyle(el).color));
    expect(ink && ink.r < 60 && ink.g < 60 && ink.b < 60, 'Start lesson ink is dark on the white plate').toBe(true);

    // Tip overlay: kicker + primary are neutral.
    await open(page, '/tutorial.html', size);
    await showTip(page);
    const tip = await page.evaluate(() => {
      const s = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el) : null; };
      const k = s('.gob-tip-overlay .gob-modal-kicker');
      const b = s('.gob-tip-overlay .btn-primary');
      return { kicker: k ? k.color : '', bg: b ? b.backgroundColor : '', shadow: b ? b.boxShadow : '' };
    });
    for (const [k, v] of Object.entries(tip)) expect(hasOrange(v), `tip ${k} ${v}`).toBe(false);

    // Persona LET'S GO is a navigation CTA, not a save.
    await open(page, '/tutorial-persona-intro.html', size);
    const persona = await page.locator('#persona-intro-cta').evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(hasOrange(persona) || hasGreen(persona), `persona cta ${persona}`).toBe(false);

    // Pick opponent: Sammy GOT IT neutral; selected card + check neutral; CONTINUE neutral.
    await open(page, '/tutorial-pick-opponent.html', size);
    await page.locator('.sammy-modal-backdrop.open').waitFor();
    const gotIt = await page.locator('.sammy-modal-btn-primary').evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(hasGreen(gotIt) || hasOrange(gotIt), `sammy GOT IT ${gotIt}`).toBe(false);
    await page.locator('.sammy-modal-btn-primary').click();
    await page.locator('.opp-card[data-name="Ocean City"]').click();
    const opp = await page.evaluate(() => {
      const card = getComputedStyle(document.querySelector('.opp-card.is-selected'));
      const rank = getComputedStyle(document.querySelector('.opp-card.is-selected .opp-card__rank'));
      const check = getComputedStyle(document.querySelector('.opp-card.is-selected .opp-card__check'));
      const cta = getComputedStyle(document.getElementById('opp-cta'));
      return {
        border: card.borderTopColor, bg: card.backgroundColor, shadow: card.boxShadow,
        rank: rank.color, check: check.color, cta: cta.backgroundColor,
        rail: card.borderLeftColor,
      };
    });
    for (const k of ['border', 'bg', 'shadow', 'rank', 'check', 'cta']) {
      expect(hasOrange(opp[k]), `opponent ${k} ${opp[k]}`).toBe(false);
    }
    // The team-colour rail stays (team colour, not a law colour).
    expect(opp.rail).toBe('rgb(31, 79, 122)');

    // Tip-off: Sammy ring and eyebrow neutral; SIM GAME is the Advance and stays green.
    await open(page, '/tutorial-situation.html?away=Bentley-Truman', size);
    await page.locator('#tipoff-moment:not([hidden])').waitFor();
    const tipoff = await page.evaluate(() => ({
      ring: getComputedStyle(document.querySelector('.tipoff-moment__portrait')).borderTopColor,
      eyebrow: getComputedStyle(document.querySelector('.tipoff-moment__eyebrow')).color,
      cta: getComputedStyle(document.getElementById('tipoff-cta')).backgroundColor,
    }));
    expect(hasOrange(tipoff.ring), `tipoff ring ${tipoff.ring}`).toBe(false);
    expect(hasOrange(tipoff.eyebrow), `tipoff eyebrow ${tipoff.eyebrow}`).toBe(false);
    expect(hasGreen(tipoff.cta), `SIM GAME stays green ${tipoff.cta}`).toBe(true);

    // Username: ring + focus neutral; CONTINUE is the neutral plate (Jamie, 2026-10-01:
    // orange only for unsaved changes).
    await open(page, '/tutorial.html', size);
    await page.evaluate(async () => {
      const m = await import('/js/shared/usernameModal.js');
      m.openUsernameModal({ onSuccess() {} });
    });
    await page.locator('#username-modal-cta').waitFor();
    await page.locator('.username-modal-input').focus();
    const user = await page.evaluate(() => ({
      ring: getComputedStyle(document.querySelector('.username-modal-portrait')).borderTopColor,
      focus: getComputedStyle(document.querySelector('.username-modal-input')).borderTopColor,
      cta: getComputedStyle(document.getElementById('username-modal-cta')).backgroundColor,
    }));
    expect(hasOrange(user.ring), `username ring ${user.ring}`).toBe(false);
    expect(hasOrange(user.focus), `username focus ${user.focus}`).toBe(false);
    expect(hasOrange(user.cta), `username CONTINUE is not orange ${user.cta}`).toBe(false);

    // Lineup intro: GOT IT neutral, ring neutral.
    await open(page, '/tutorial.html', size);
    await page.evaluate(async () => {
      const m = await import('/js/shared/tutorialLineupModals.js');
      m.showLineupIntroModal({ teamName: 'Lancaster', onDismiss() {} });
    });
    await page.locator('.tutorial-lineup-modal-cta').waitFor();
    const lineup = await page.evaluate(() => ({
      ring: getComputedStyle(document.querySelector('.tutorial-lineup-modal-portrait')).borderTopColor,
      cta: getComputedStyle(document.querySelector('.tutorial-lineup-modal-cta')).backgroundColor,
    }));
    expect(hasOrange(lineup.ring), `lineup ring ${lineup.ring}`).toBe(false);
    expect(hasOrange(lineup.cta) || hasGreen(lineup.cta), `lineup GOT IT ${lineup.cta}`).toBe(false);

    // Attribute tour: lifted band, cue, explored state, eyebrow, ring, GOT IT neutral.
    await open(page, '/tutorial.html', size);
    await showAttributeTour(page);
    const cued = page.locator('th.is-cued').first();
    await cued.hover();
    await page.waitForTimeout(150);
    const tour = await page.evaluate(() => {
      const th = document.querySelector('th.attribute-tour__lifted');
      const cue = document.querySelector('th.is-cued');
      const s = (sel) => getComputedStyle(document.querySelector(sel));
      return {
        band: getComputedStyle(th).boxShadow,
        cue: getComputedStyle(cue, '::after').backgroundImage,
        hover: getComputedStyle(cue).color,
        eyebrow: s('.attribute-tour__sammy-eyebrow').color,
        ring: s('.attribute-tour__sammy-portrait').borderTopColor,
        dismiss: s('.attribute-tour__sammy-dismiss').backgroundColor,
      };
    });
    for (const [k, v] of Object.entries(tour)) expect(hasOrange(v) || hasGreen(v), `tour ${k} ${v}`).toBe(false);
    await page.evaluate(() => {
      document.querySelectorAll('th.is-cued').forEach((th) => th.classList.add('is-explored'));
      const c = document.querySelector('.attribute-tour__sammy-count');
      if (c) c.classList.add('is-complete');
    });
    const explored = await page.evaluate(() => ({
      th: getComputedStyle(document.querySelector('th.is-explored')).color,
      count: document.querySelector('.attribute-tour__sammy-count')
        ? getComputedStyle(document.querySelector('.attribute-tour__sammy-count')).color : '',
    }));
    expect(hasGreen(explored.th), `explored ${explored.th}`).toBe(false);
    expect(hasGreen(explored.count), `complete count ${explored.count}`).toBe(false);

    // Legacy host (no html.gob): restored fte.css styles the press-conference reminder.
    await open(page, '/privacy.html', size);
    expect(await page.evaluate(() => document.documentElement.classList.contains('gob'))).toBe(false);
    await page.evaluate(async () => {
      const m = await import('/js/phaser/utils/pgpcSammyReminderModal.js');
      m.showPgpcSammyReminderModal({ userTeamName: 'Lancaster', onGotIt() {} });
    });
    await page.locator('#pgpc-sammy-reminder-gotit').waitFor();
    const fteRes = await page.evaluate(async () => {
      const link = document.querySelector('link[href*="fte.css"]');
      const r = await fetch(link.href);
      return r.status;
    });
    expect(fteRes, '/css/fte.css is served').toBe(200);
    await page.waitForFunction(() => getComputedStyle(document.getElementById('pgpc-sammy-reminder-backdrop')).position === 'fixed');
    const pgpc = await page.evaluate(() => {
      const s = (sel) => getComputedStyle(document.querySelector(sel));
      return {
        position: s('#pgpc-sammy-reminder-backdrop').position,
        modalBg: s('.fte-modal').backgroundColor,
        btn: s('#pgpc-sammy-reminder-gotit').backgroundColor,
        label: s('.pgpc-sammy-dont-show').color,
        accent: s('#pgpc-sammy-dont-show-again').accentColor,
      };
    });
    expect(pgpc.position).toBe('fixed');
    const bg = parseRgba(pgpc.modalBg);
    expect(bg && bg.a > 0.9 && bg.r < 40 && bg.g < 40 && bg.b < 60, `fte modal is the dark surface ${pgpc.modalBg}`).toBe(true);
    expect(hasOrange(pgpc.btn) || hasGreen(pgpc.btn), `pgpc Got It ${pgpc.btn}`).toBe(false);
    const label = parseRgba(pgpc.label);
    expect(label && label.r > 200 && label.g > 200, `don't-show label readable on dark ${pgpc.label}`).toBe(true);
    expect(hasOrange(pgpc.accent), `checkbox accent ${pgpc.accent}`).toBe(false);

    // Sammy modal on a legacy host: is-orange navigation renders neutral, is-advance is green.
    await open(page, '/privacy.html', size);
    await showSammy(page, { ctaLabel: 'Go To Locker Room', primaryClass: 'is-orange' });
    const nav = await page.evaluate(() => {
      const m = getComputedStyle(document.querySelector('.sammy-modal'));
      const b = getComputedStyle(document.querySelector('.sammy-modal-btn-primary'));
      return { modal: m.backgroundColor, btn: b.backgroundColor, border: b.borderTopColor };
    });
    const mbg = parseRgba(nav.modal);
    expect(mbg && mbg.a > 0.9, `sammy surface resolves without .gob ${nav.modal}`).toBe(true);
    expect(hasOrange(nav.btn) || hasOrange(nav.border), `is-orange nav CTA ${nav.btn}`).toBe(false);
    await open(page, '/privacy.html', size);
    await showSammy(page, { ctaLabel: 'Sim Region First Round', primaryClass: 'is-advance' });
    const adv2 = await page.locator('.sammy-modal-btn-primary').evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(hasGreen(adv2), `is-advance stays green ${adv2}`).toBe(true);
  });
});
