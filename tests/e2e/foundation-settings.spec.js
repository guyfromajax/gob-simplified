const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

async function stubMe(page, body) {
  await page.route('**/api/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  }));
  await page.route('**/api/auth/logout', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: '{}',
  }));
}

const ME = {
  user_id: 'e2e-user',
  email: 'e2e@example.com',
  username: 'e2e',
  role: 'user',
  record: { wins: 12, losses: 5 },
  championships_total: { conf_rs: 1, conf_t: 0, region: 0, national: 2 },
};

// Home Base carries its own top bar, so mode-select has no site auth bar and
// no gear. Settings opens from the utility row under the program slots, and
// that control toggles the panel exactly as the gear did.
const SETTINGS_TRIGGER = '[data-hb-settings]';

// Three ways, not four. This used to close the panel a fourth way by clicking
// the trigger again, which worked while the trigger was the auth bar's gear in
// the top-right corner. Home Base has no site auth bar and puts Settings in
// the utility row under the slots, which the left drawer covers while it is
// open. The close button, Escape and the scrim are the ways out from here.
test('settings panel opens and closes three ways', async ({ page }) => {
  await stubAuth(page);
  await stubMe(page, ME);
  await page.goto('/mode-select.html');
  const gear = page.locator(SETTINGS_TRIGGER);
  await expect(gear).toBeVisible();
  await gear.click();
  const panel = page.locator('#gob-settings-host .settings');
  await expect(panel).toBeVisible();
  await expect(panel.locator('h2')).toHaveText('Settings');
  await page.locator('[data-settings-close]').click();
  await expect(page.locator('#gob-settings-host')).toBeHidden();

  await gear.click();
  await expect(panel).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#gob-settings-host')).toBeHidden();

  await gear.click();
  await expect(panel).toBeVisible();
  await page.locator('[data-settings-scrim]').click();
  await expect(page.locator('#gob-settings-host')).toBeHidden();

  // The drawer sits over the utility row, so the trigger is not clickable
  // again while the panel is open. Guard that, so a later layout change that
  // frees the trigger makes someone revisit the fourth way.
  await gear.click();
  await expect(panel).toBeVisible();
  const covered = await page.locator(SETTINGS_TRIGGER).evaluate((el) => {
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return !(top === el || el.contains(top));
  });
  expect(covered, 'the open panel covers Home Base’s Settings trigger').toBe(true);
});

test('sliders change uiSfx live and persist across reload', async ({ page }) => {
  await stubAuth(page);
  await stubMe(page, ME);
  await page.goto('/mode-select.html');
  await page.locator(SETTINGS_TRIGGER).click();
  const music = page.locator('.slider[data-channel="music"]');
  await music.focus();
  await page.keyboard.press('Home');
  const level = await page.evaluate(() => window.GOBUiSfx.getAudioState().music.level);
  expect(level).toBe(0);
  await page.reload();
  const kept = await page.evaluate(async () => {
    const mod = await import('/js/shared/uiSfx.js');
    return mod.getAudioState().music.level;
  });
  expect(kept).toBe(0);
});

test('offline profile hides Account and shows the offline note', async ({ page }) => {
  await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await page.goto('/mode-select.html');
  await page.evaluate(async () => {
    const mod = await import('/js/shared/gobSettings.js');
    mod.openSettings();
  });
  await expect(page.locator('.set-note')).toHaveText("Playing offline. Account settings return when you're back online.");
  await expect(page.locator('[data-settings-logout]')).toHaveCount(0);
  await expect(page.locator('[data-conn-label]')).toHaveText('Offline');
});

// FAQs sits in the panel footer, outside the Account section the offline profile
// replaces. It opens in a new tab; the game page stays put.
async function checkFaqs(page, shot) {
  const faqs = page.locator('#gob-settings-host .set-f a[data-settings-faqs]');
  await expect(faqs).toBeVisible();
  const hit = await faqs.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return { ok: top === el || el.contains(top), bottom: r.bottom, vh: innerHeight };
  });
  expect(hit.ok, JSON.stringify(hit)).toBe(true);
  expect(hit.bottom).toBeLessThanOrEqual(hit.vh);
  await expect(faqs).toHaveText('FAQs');
  await expect(faqs).toHaveClass(/\blnk\b/);
  await expect(faqs).toHaveAttribute('href', '/faqs.html');
  await expect(faqs).toHaveAttribute('target', '_blank');
  await expect(faqs).toHaveAttribute('rel', /\bnoopener\b/);

  let focused = false;
  for (let i = 0; i < 30 && !focused; i++) {
    await page.keyboard.press('Tab');
    focused = await faqs.evaluate((el) => document.activeElement === el);
  }
  expect(focused, 'FAQs reachable with Tab').toBe(true);
  const ring = await faqs.evaluate((el) => {
    const cs = getComputedStyle(el);
    return { style: cs.outlineStyle, width: parseFloat(cs.outlineWidth), visible: el.matches(':focus-visible') };
  });
  expect(ring.visible).toBe(true);
  expect(ring.style).toBe('solid');
  expect(ring.width).toBeGreaterThanOrEqual(2);
  await page.locator('#gob-settings-host .settings').evaluate((el) => Promise.all(el.getAnimations().map((a) => a.finished)));
  await page.screenshot({ path: shot });

  const before = page.url();
  const [popup] = await Promise.all([page.waitForEvent('popup'), faqs.click()]);
  await popup.waitForLoadState('domcontentloaded');
  expect(new URL(popup.url()).pathname).toMatch(/\/faqs\.html$/);
  await expect(popup.locator('h1').first()).toBeVisible();
  expect(page.url()).toBe(before);
  await popup.close();
}

test('settings footer links FAQs in a new tab online', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await stubAuth(page);
  await stubMe(page, ME);
  await page.goto('/mode-select.html');
  await page.locator(SETTINGS_TRIGGER).click();
  await expect(page.locator('#gob-settings-host [data-settings-logout]')).toBeVisible();
  await expect(page.locator('[data-conn-label]')).toHaveText('Online');
  await checkFaqs(page, 'reports/settings-faqs/settings-online-1280x720.png');
});

test('settings footer links FAQs in a new tab offline', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await page.goto('/mode-select.html');
  await page.evaluate(async () => {
    const mod = await import('/js/shared/gobSettings.js');
    mod.openSettings();
  });
  await expect(page.locator('.set-note')).toBeVisible();
  await expect(page.locator('[data-conn-label]')).toHaveText('Offline');
  await checkFaqs(page, 'reports/settings-faqs/settings-offline-1280x720.png');
});

// The body (.set-b) is the panel's own scroll area; the header and the footer
// (FAQs, Online/Offline) stay pinned while it scrolls.
function panelMetrics(page) {
  return page.evaluate(() => {
    const panel = document.querySelector('#gob-settings-host .settings');
    const head = panel.querySelector('.set-h');
    const body = panel.querySelector('.set-b');
    const foot = panel.querySelector('.set-f');
    const faqs = foot.querySelector('a[data-settings-faqs]');
    const box = (el) => { const r = el.getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height) }; };
    const hits = (el) => {
      const r = el.getBoundingClientRect();
      const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return top === el || el.contains(top);
    };
    return {
      panel: box(panel),
      head: box(head),
      body: box(body),
      foot: box(foot),
      overflow: body.scrollHeight - body.clientHeight,
      scrollTop: Math.round(body.scrollTop),
      gutter: body.offsetWidth - body.clientWidth,
      overflowY: getComputedStyle(body).overflowY,
      faqsHit: hits(faqs),
      faqsInFoot: faqs.getBoundingClientRect().bottom <= foot.getBoundingClientRect().bottom + 0.5,
      sections: [...body.children].filter((s) => !s.hidden).map((s) => {
        const r = s.getBoundingClientRect();
        return [Math.round(r.top), Math.round(r.height)];
      }),
    };
  });
}

async function openPanel(page, offline) {
  if (offline) await page.addInitScript(() => { window.GOB_BUILD_PROFILE = 'desktop'; });
  await stubAuth(page);
  await stubMe(page, ME);
  await page.goto('/mode-select.html');
  await page.evaluate(async () => {
    const mod = await import('/js/shared/gobSettings.js');
    mod.openSettings();
  });
  const panel = page.locator('#gob-settings-host .settings');
  await expect(panel).toBeVisible();
  await expect(page.locator(offline ? '#gob-settings-host .set-note' : '#gob-settings-host [data-settings-logout]')).toBeVisible();
  await panel.evaluate((el) => Promise.all(el.getAnimations().map((a) => a.finished)));
}

// 1280x600, not 720. On Home Base the panel runs the full viewport height —
// there is no site auth bar above it any more — and at 720 the online content
// clears the body with room to spare, so there is nothing to scroll. 600 is
// the smallest supported height and the one where scrolling still has to work.
test('the settings body scrolls so Log Out is reachable at 1280x600, footer pinned', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 600 });
  await openPanel(page, false);
  const before = await panelMetrics(page);
  expect(before.overflowY).toBe('auto');
  expect(before.overflow, 'content taller than the body at 1280x600 online').toBeGreaterThan(0);
  expect(before.head.top).toBe(before.panel.top);
  expect(before.foot.bottom).toBe(before.panel.bottom);
  expect(before.foot.height).toBe(44);
  expect(before.faqsHit).toBe(true);

  const logout = page.locator('#gob-settings-host [data-settings-logout]');
  await logout.scrollIntoViewIfNeeded();
  await page.locator('#gob-settings-host .set-b').evaluate((el) => { el.scrollTop = el.scrollHeight; });
  const after = await panelMetrics(page);
  const target = await logout.evaluate((el) => {
    const r = el.getBoundingClientRect();
    const foot = document.querySelector('#gob-settings-host .set-f').getBoundingClientRect();
    const body = document.querySelector('#gob-settings-host .set-b').getBoundingClientRect();
    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return { hit: top === el || el.contains(top), top: r.top, bottom: r.bottom, footTop: foot.top, bodyTop: body.top, height: r.height };
  });
  expect(target.hit, JSON.stringify(target)).toBe(true);
  expect(target.bottom, JSON.stringify(target)).toBeLessThanOrEqual(target.footTop);
  expect(target.top).toBeGreaterThanOrEqual(target.bodyTop);
  expect(target.height).toBeGreaterThanOrEqual(24);
  expect(after.scrollTop).toBe(before.overflow);
  // Header and footer do not move while the body scrolls.
  expect(after.head).toEqual(before.head);
  expect(after.foot).toEqual(before.foot);
  expect(after.faqsHit).toBe(true);
  expect(after.faqsInFoot).toBe(true);
  await page.mouse.move(900, 400);
  await page.screenshot({ path: 'reports/settings-scroll/settings-online-1280x600-scrolled.png' });

  const [req] = await Promise.all([
    page.waitForRequest((r) => r.url().includes('/api/auth/logout') && r.method() === 'POST'),
    logout.click(),
  ]);
  expect(req).toBeTruthy();
  await page.waitForLoadState('load');
  await expect(page).toHaveURL(/mode-select\.html/);
});

test('the settings panel keeps its frame online and offline at three sizes', async ({ browser }) => {
  const fs = require('fs');
  const out = {};
  for (const offline of [false, true]) {
    for (const size of [[1280, 720], [1920, 1080], [1280, 600]]) {
      const page = await browser.newPage({ viewport: { width: size[0], height: size[1] } });
      await openPanel(page, offline);
      const m = await panelMetrics(page);
      const label = (offline ? 'offline-' : 'online-') + size.join('x');
      out[label] = m;
      if (process.env.SETTINGS_PHASE === 'before') { await page.close(); continue; }
      expect(m.head.top, label).toBe(m.panel.top);
      expect(m.foot.bottom, label).toBe(m.panel.bottom);
      expect(m.body.top, label).toBe(m.head.bottom);
      expect(m.body.bottom, label).toBe(m.foot.top);
      expect(m.head.height, label).toBe(56);
      expect(m.foot.height, label).toBe(44);
      expect(m.faqsHit, label).toBe(true);
      if (m.overflow <= 0) expect(m.gutter, label + ' no scrollbar when it fits').toBe(0);
      const body = page.locator('#gob-settings-host .set-b');
      await body.evaluate((el) => { el.scrollTop = el.scrollHeight; });
      const last = await body.evaluate((el) => {
        const kids = [...el.querySelectorAll('.set-s:not([hidden]) > *')];
        const r = kids[kids.length - 1].getBoundingClientRect();
        return { bottom: r.bottom, limit: el.getBoundingClientRect().bottom };
      });
      expect(last.bottom, label + ' last item inside the body').toBeLessThanOrEqual(last.limit + 0.5);
      if (size[1] === 600) {
        await page.mouse.move(900, 300);
        await page.screenshot({ path: 'reports/settings-scroll/settings-' + label + '-bottom.png' });
      }
      await page.close();
    }
  }
  fs.writeFileSync('reports/settings-scroll/' + (process.env.SETTINGS_PHASE || 'after') + '-metrics.json', JSON.stringify(out, null, 2));
});

// Mute buttons and the close × must never pick up the browser's default button face.
// Outside the shell the host is `.gob.gob-settings-host` with no .gob ancestor.
const SHELL_FID = 'f-e2e-settings-icons';
const SHELL_TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const ICON_PAGES = [
  { name: 'mode-select', url: '/mode-select.html', shell: false },
  { name: 'office', url: '/franchise-command-center.html?franchise_id=' + SHELL_FID + '&team_id=' + SHELL_TID, shell: true },
  { name: 'standings (browse)', url: '/standings.html?franchise_id=' + SHELL_FID + '&team_id=' + SHELL_TID, shell: true },
  { name: 'recruiting (focus)', url: '/recruiting.html?franchise_id=' + SHELL_FID + '&team_id=' + SHELL_TID + '&from=fcc', shell: true },
];

async function installShellApi(page) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (_err) { return route.continue(); }
    const json = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (pathname.startsWith('/franchise/command-center/data')) {
      return json({
        franchise_id: SHELL_FID, team_id: SHELL_TID, user_team_id: SHELL_TID, team: 'Lancaster', week: 21, rank: 14,
        season: 1, current_season: 1, training_completed: true, session_type: 'in-season',
        recruiting_wire: { board_saved_week: 21, counts: {} }, user_conference: 1, user_region: 'C',
        team_record: { wins: 4, losses: 1 },
      });
    }
    if (pathname === '/api/auth/me') return json(ME);
    if (pathname === '/app-config') return json({ isAlpha: false, version: '1.0' });
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')) return json({});
    return route.continue();
  });
}

async function openOn(page, spec) {
  await page.setViewportSize({ width: 1280, height: 720 });
  if (spec.shell) await installShellApi(page);
  else { await stubAuth(page); await stubMe(page, ME); }
  await page.goto(spec.url);
  await page.waitForFunction(() => !document.documentElement.classList.contains('gob-pending'));
  if (spec.shell) await expect(page.locator('html.gob-shell')).toHaveCount(1);
  await page.evaluate(async () => {
    const mod = await import('/js/shared/gobSettings.js');
    mod.openSettings();
  });
  const panel = page.locator('#gob-settings-host .settings');
  await expect(panel).toBeVisible();
  await panel.evaluate((el) => Promise.all(el.getAnimations().map((a) => a.finished)));
}

function iconState(page, selector) {
  return page.evaluate((sel) => {
    const host = document.getElementById('gob-settings-host');
    const token = (name) => {
      const probe = document.createElement('span');
      probe.style.color = 'var(' + name + ')';
      host.appendChild(probe);
      const value = getComputedStyle(probe).color;
      probe.remove();
      return value;
    };
    const el = host.querySelector(sel);
    const cs = getComputedStyle(el);
    const svg = el.querySelector('svg');
    const out = {
      bg: cs.backgroundColor,
      bgImage: cs.backgroundImage,
      borderWidth: cs.borderTopWidth,
      appearance: cs.appearance,
      color: cs.color,
      text60: token('--text-60'),
      text100: token('--text-100'),
      red: token('--red'),
      on: el.classList.contains('on'),
      pressed: el.getAttribute('aria-pressed'),
    };
    if (svg) {
      const r = svg.getBoundingClientRect();
      const paths = [...svg.querySelectorAll('path')];
      const pcs = getComputedStyle(paths[0]);
      out.svg = { w: r.width, h: r.height, stroke: pcs.stroke, fill: pcs.fill, strokeWidth: pcs.strokeWidth, d: paths.map((p) => p.getAttribute('d')).join(' ') };
    }
    return out;
  }, selector);
}

function expectFlatButton(state, label) {
  expect(state.bg, label + ' background').toBe('rgba(0, 0, 0, 0)');
  expect(state.bgImage, label).toBe('none');
  expect(state.borderWidth, label + ' border').toBe('0px');
  expect(state.appearance, label).toBe('none');
}

for (const spec of ICON_PAGES) {
  test('settings mute icons and close render flat on ' + spec.name, async ({ page }) => {
    await openOn(page, spec);
    const MUTE = '[data-mute="music"]';

    const rest = await iconState(page, MUTE);
    expectFlatButton(rest, spec.name + ' mute');
    expect(rest.color).toBe(rest.text60);
    expect(rest.svg.w).toBeGreaterThan(0);
    expect(rest.svg.h).toBeGreaterThan(0);
    expect(rest.svg.fill).toBe('none');
    expect(rest.svg.stroke).toBe(rest.text60);
    expect(parseFloat(rest.svg.strokeWidth)).toBeGreaterThan(0);
    expect(rest.svg.d).toContain('M15.5 9a4 4 0 0 1 0 6');
    expect(rest.pressed).toBe('false');

    const close = await iconState(page, '.set-x');
    expectFlatButton(close, spec.name + ' close');
    expect(close.color).toBe(close.text60);

    await page.hover('#gob-settings-host ' + MUTE);
    await expect.poll(async () => (await iconState(page, MUTE)).color).toBe(rest.text100);

    await page.click('#gob-settings-host ' + MUTE);
    await page.mouse.move(900, 400);
    await expect.poll(async () => (await iconState(page, MUTE)).on).toBe(true);
    await expect.poll(async () => (await iconState(page, MUTE)).color).toBe(rest.red);
    const muted = await iconState(page, MUTE);
    expect(muted.pressed).toBe('true');
    expect(muted.svg.d).toContain('M16 9.5l5 5');
    expect(muted.svg.stroke).toBe(rest.red);
    expect(muted.svg.w).toBeGreaterThan(0);

    const others = await page.evaluate(() => [...document.querySelectorAll('#gob-settings-host [data-mute]')]
      .map((b) => ({ id: b.dataset.mute, bg: getComputedStyle(b).backgroundColor, on: b.classList.contains('on') })));
    for (const other of others.filter((o) => o.id !== 'music')) {
      expect(other.on, other.id).toBe(false);
      expect(other.bg, other.id).toBe('rgba(0, 0, 0, 0)');
    }

    if (spec.name === 'mode-select' || spec.name === 'office') {
      await page.screenshot({ path: 'reports/settings-mute-icons/settings-' + spec.name + '-1280x720-music-muted.png' });
    }

    await page.click('#gob-settings-host ' + MUTE);
    await page.mouse.move(900, 400);
    await expect.poll(async () => (await iconState(page, MUTE)).on).toBe(false);
    const back = await iconState(page, MUTE);
    expect(back.pressed).toBe('false');
    expect(back.svg.d).toContain('M15.5 9a4 4 0 0 1 0 6');
    await expect.poll(async () => (await iconState(page, MUTE)).color).toBe(rest.text60);
  });
}

const COURT_RECTS = {
  '1280x720': {
    scoreboard: { x: 0, y: 0, w: 1280, h: 120 },
    phaser: { x: 280, y: 120, w: 720, h: 456 },
    playcall: { x: 280, y: 576, w: 720, h: 144 },
    pauseH: 48,
    timeoutH: 48,
    gap: 6,
  },
  '1920x1080': {
    scoreboard: { x: 0, y: 0, w: 1920, h: 120 },
    phaser: { x: 280, y: 120, w: 1360, h: 744 },
    playcall: { x: 280, y: 864, w: 1360, h: 216 },
    pauseH: 75,
    timeoutH: 75,
    gap: 8,
  },
};

function roundRect(box) {
  return {
    x: Math.round(box.x),
    y: Math.round(box.y),
    w: Math.round(box.width),
    h: Math.round(box.height),
  };
}

async function revealCourt(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.pre-game-container, #page-load-overlay, .pgxp-root').forEach((el) => {
      el.style.display = 'none';
    });
  });
}

async function mouseClick(page, locator) {
  const box = await locator.boundingBox();
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.click(x, y);
  return { x, y };
}

test('court sound control sits with pause and timeout', async ({ page }) => {
  await stubAuth(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
  const sound = page.locator('#sound-btn');
  await expect(sound).toBeVisible();
  await expect(page.locator('#scoreboard .sb-snd')).toHaveCount(0);
  await revealCourt(page);

  const hit = await page.evaluate(() => {
    const btn = document.getElementById('sound-btn');
    const box = btn.getBoundingClientRect();
    const el = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return el && el.id;
  });
  expect(hit).toBe('sound-btn');

  const rects = await page.evaluate(() => ({
    scoreboard: document.getElementById('scoreboard').getBoundingClientRect().toJSON(),
    phaser: document.getElementById('phaser-container').getBoundingClientRect().toJSON(),
    playcall: document.getElementById('playcall-center').getBoundingClientRect().toJSON(),
  }));
  expect(roundRect(rects.scoreboard)).toEqual(COURT_RECTS['1280x720'].scoreboard);
  expect(roundRect(rects.phaser)).toEqual(COURT_RECTS['1280x720'].phaser);
  expect(roundRect(rects.playcall)).toEqual(COURT_RECTS['1280x720'].playcall);
  await expect(sound).not.toContainText('SOUND');
  await expect(sound).toHaveAttribute('title', 'Sound');
  await expect(sound).toHaveAttribute('aria-label', 'Sound');

  const beforePause = await page.locator('.pcc-pause-text').innerText();
  expect(beforePause).toBe('PAUSE');
  await mouseClick(page, sound);
  const pop = page.locator('.gob-snd-pop');
  await expect(pop).toBeVisible();
  await expect(page.locator('#pause-btn')).not.toHaveClass(/paused/);
  await expect(page.locator('.pcc-pause-text')).toHaveText('PAUSE');

  const stacked = await page.evaluate(() => {
    const btn = document.getElementById('sound-btn').getBoundingClientRect();
    const panel = document.querySelector('.gob-snd-pop').getBoundingClientRect();
    const pause = document.getElementById('pause-btn').getBoundingClientRect();
    const timeout = document.getElementById('timeout-btn').getBoundingClientRect();
    return {
      panelBottom: panel.bottom,
      panelRight: panel.right,
      buttonTop: btn.top,
      buttonRight: btn.right,
      panelTop: panel.top,
      soundW: btn.width,
      soundH: btn.height,
      pauseH: pause.height,
      timeoutH: timeout.height,
      gap: btn.left - pause.right,
    };
  });
  expect(stacked.panelBottom).toBeLessThanOrEqual(stacked.buttonTop + 1);
  expect(stacked.panelTop).toBeGreaterThanOrEqual(0);
  expect(Math.abs(stacked.panelRight - stacked.buttonRight)).toBeLessThanOrEqual(1);
  expect(Math.round(stacked.pauseH)).toBe(COURT_RECTS['1280x720'].pauseH);
  expect(Math.round(stacked.timeoutH)).toBe(COURT_RECTS['1280x720'].timeoutH);
  expect(Math.round(stacked.soundW)).toBe(COURT_RECTS['1280x720'].pauseH);
  expect(Math.round(stacked.soundH)).toBe(COURT_RECTS['1280x720'].pauseH);
  expect(Math.round(stacked.gap)).toBe(COURT_RECTS['1280x720'].gap);

  await mouseClick(page, pop.locator('.tgl'));
  await expect(sound).toHaveClass(/is-muted/);
  await expect(sound).toHaveAttribute('aria-label', 'Sound (muted)');
  await expect(sound).toHaveAttribute('title', 'Sound');
  const music = pop.locator('.slider[data-channel="music"]');
  const track = await music.boundingBox();
  await page.mouse.move(track.x + track.width - 2, track.y + track.height / 2);
  await page.mouse.down();
  await page.mouse.move(track.x, track.y + track.height / 2, { steps: 12 });
  await page.mouse.up();
  const dragged = await page.evaluate(() => window.GOBUiSfx.getAudioState().music.level);
  expect(dragged).toBe(0);
  await pop.locator('.slider[data-channel="sfx"]').focus();
  await page.keyboard.press('ArrowLeft');
  const stepped = await page.evaluate(() => window.GOBUiSfx.getAudioState().sfx.level);
  expect(stepped).toBe(95);

  await page.reload();
  await expect(sound).toBeVisible();
  await revealCourt(page);
  await expect(sound).toHaveClass(/is-muted/);
  await expect(sound).toHaveAttribute('aria-label', 'Sound (muted)');
  await expect(sound).toHaveAttribute('title', 'Sound');
  const kept = await page.evaluate(() => ({
    muted: window.GOBUiSfx.getAudioState().master.muted,
    music: window.GOBUiSfx.getAudioState().music.level,
  }));
  expect(kept.muted).toBe(true);
  expect(kept.music).toBe(0);

  await mouseClick(page, sound);
  await expect(pop).toBeVisible();
  await page.screenshot({ path: 'reports/court-sound/popover-1280x720.png' });

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.evaluate(() => window.dispatchEvent(new Event('resize')));
  await expect(pop).toBeVisible();
  const wide = await page.evaluate(() => ({
    scoreboard: document.getElementById('scoreboard').getBoundingClientRect().toJSON(),
    phaser: document.getElementById('phaser-container').getBoundingClientRect().toJSON(),
    playcall: document.getElementById('playcall-center').getBoundingClientRect().toJSON(),
    pauseH: document.getElementById('pause-btn').getBoundingClientRect().height,
    timeoutH: document.getElementById('timeout-btn').getBoundingClientRect().height,
    sound: document.getElementById('sound-btn').getBoundingClientRect().toJSON(),
    pauseRight: document.getElementById('pause-btn').getBoundingClientRect().right,
    panelRight: document.querySelector('.gob-snd-pop').getBoundingClientRect().right,
    soundRight: document.getElementById('sound-btn').getBoundingClientRect().right,
  }));
  expect(roundRect(wide.scoreboard)).toEqual(COURT_RECTS['1920x1080'].scoreboard);
  expect(roundRect(wide.phaser)).toEqual(COURT_RECTS['1920x1080'].phaser);
  expect(roundRect(wide.playcall)).toEqual(COURT_RECTS['1920x1080'].playcall);
  expect(Math.round(wide.pauseH)).toBe(COURT_RECTS['1920x1080'].pauseH);
  expect(Math.round(wide.timeoutH)).toBe(COURT_RECTS['1920x1080'].timeoutH);
  expect(Math.round(wide.sound.width)).toBe(COURT_RECTS['1920x1080'].pauseH);
  expect(Math.round(wide.sound.height)).toBe(COURT_RECTS['1920x1080'].pauseH);
  expect(Math.round(wide.sound.x - wide.pauseRight)).toBe(COURT_RECTS['1920x1080'].gap);
  expect(Math.abs(wide.panelRight - wide.soundRight)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: 'reports/court-sound/popover-1920x1080.png' });

  await page.keyboard.press('Escape');
  await expect(pop).toBeHidden();
  await mouseClick(page, sound);
  await expect(pop).toBeVisible();
  await mouseClick(page, sound);
  await expect(pop).toBeHidden();
});

test('a mode-select click still asks for its original file', async ({ page }) => {
  await stubAuth(page);
  await stubMe(page, ME);
  const played = [];
  await page.addInitScript(() => {
    const Orig = window.Audio;
    window.Audio = function (src) {
      const audio = new Orig(src);
      const realPlay = audio.play.bind(audio);
      audio.play = () => {
        window.__played = window.__played || [];
        window.__played.push(String(src || audio.src || ''));
        return realPlay().catch(() => {});
      };
      return audio;
    };
  });
  await page.goto('/mode-select.html');
  await page.evaluate(() => { window.__played = []; });
  await page.locator(SETTINGS_TRIGGER).click();
  // The gear itself does not play a file. A tutorials click in the bar does, when present.
  const tutorials = page.locator('#tutorials-btn, [data-tutorials], a[href*="tutorial"]').first();
  if (await tutorials.count()) {
    await tutorials.click({ timeout: 2000 }).catch(() => {});
  }
  await page.evaluate(async () => {
    const mod = await import('/js/shared/uiSfx.js');
    mod.playSfx('click-tiny.wav', 0.7);
  });
  const files = await page.evaluate(() => window.__played || []);
  expect(files.some((src) => src.includes('click-tiny.wav'))).toBe(true);
});
