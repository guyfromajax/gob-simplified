const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * Shared chrome on the gob tokens + colour law: auth bar (and the account modal,
 * toast and footer that ship in the same sheet), account / FAQ / legal pages, the
 * page-load overlay, the error screens and the Home Base alpha banner.
 *
 * SC_SHOTS=before writes before-*.png and skips the guards: run it on develop for
 * the BEFORE set. The default run writes after-*.png and asserts computed styles.
 */
const BEFORE = process.env.SC_SHOTS === 'before';
const OUT = path.join(__dirname, '../../reports/shared-chrome-tokens');

const FID = 'f-e2e-shared-chrome';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const REPLACED = 'cccccccccccccccccccccc01';
const CHROME_RGB = 'rgb(13, 16, 24)'; // --bg-chrome
const BG_RGB = 'rgb(11, 13, 20)'; // --bg
const SIZES = [[1280, 720, '1280'], [1920, 1080, '1920']];

const ME = {
  user_id: 'e2e-user',
  username: 'e2e',
  email: 'e2e@example.com',
  subscription: 'alpha',
  geek_points: 1240,
  geek_points_teams: [
    { team_id: 't1', display_name: 'Bentley-Truman', points: 900 },
    { team_id: 't2', display_name: 'Seattle AAA', points: 340 },
  ],
  championships_total: { national: 1, region: 0, conf_t: 2, conf_rs: 3 },
  archetypes: { total: 10, tactician: 6, recruiter: 3, motivator: 1 },
  lead_archetype: 'tactician',
};

function cc() {
  return {
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
    recruiting_wire: {},
    user_conference: 1,
    user_region: 'C',
    team_record: { wins: 8, losses: 4 },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApis(page, opts) {
  const options = opts || {};
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname === '/app-config'
      || pathname === '/teams';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, ME);
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: !!options.alpha, alphaDisclaimer: null, version: '1.0', teamBuilderEnabled: true });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, [{
        object_id: REPLACED, _id: REPLACED, name: 'Bentley-Truman', abbreviation: 'BTR', conference: 3,
        region: 'B', prestige: 62, total_player_attrs: 9100, primary_color: '#124e78', secondary_color: '#a8c6df',
      }]);
      return;
    }
    if (pathname === '/franchise/team-builder/drafts') {
      await fulfillJson(route, request.method() === 'GET'
        ? { drafts: [] }
        : { draft: { draft_id: 'sc-e2e-draft', replaced_object_id: REPLACED } });
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    await fulfillJson(route, {});
  });
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = 0;
  });
  await page.mouse.move(2, 400);
  await page.screenshot({ path: path.join(OUT, (BEFORE ? 'before-' : 'after-') + name) });
}

// Chrome reports a color-mix() result as "color(srgb r g b / a)" with 0–1 channels.
function parseRgb(color) {
  const text = String(color || '');
  const srgb = text.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)/);
  if (srgb) {
    return [
      Math.round(Number(srgb[1]) * 255), Math.round(Number(srgb[2]) * 255), Math.round(Number(srgb[3]) * 255),
      srgb[4] === undefined ? 1 : Number(srgb[4]),
    ];
  }
  const m = text.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  return m[1].split(',').map((part) => Number(String(part).trim()));
}

function isGreenish(color) {
  const p = parseRgb(color);
  if (!p || p.length < 3 || p[3] === 0) return false;
  return p[1] > 150 && p[1] > p[0] + 40 && p[1] > p[2] + 40;
}

function isOrangeish(color) {
  const p = parseRgb(color);
  if (!p || p.length < 3 || p[3] === 0) return false;
  return p[0] > 200 && p[1] > 80 && p[1] < 200 && p[2] < 110 && p[0] > p[1] + 40;
}

function neutral(color) {
  return !isGreenish(color) && !isOrangeish(color);
}

async function paint(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el);
    return {
      color: s.color,
      bg: s.backgroundColor,
      bgImage: s.backgroundImage,
      border: s.borderTopColor,
      borderLeft: s.borderLeftColor,
      shadow: s.boxShadow,
      filter: s.filter,
      display: s.display,
      text: (el.textContent || '').trim(),
    };
  }, selector);
}

function expectNeutral(p, label) {
  expect(p, label + ' missing').not.toBeNull();
  ['color', 'bg', 'border', 'borderLeft'].forEach(function (key) {
    expect(neutral(p[key]), label + ' ' + key + ' = ' + p[key]).toBe(true);
  });
  expect(/52,\s*236,\s*39|247,\s*148,\s*32|255,\s*98,\s*0|255,\s*122,\s*0/.test(p.bgImage + ' ' + p.shadow + ' ' + p.filter),
    label + ' gradient/shadow/filter = ' + p.bgImage + ' ' + p.shadow + ' ' + p.filter).toBe(false);
}

async function barReady(page, opts) {
  // Legal and FAQ pages carry an empty bar; only the filled bars have a right cluster.
  if (!(opts && opts.empty)) await page.waitForSelector('#auth-bar .auth-bar-right', { timeout: 30000 });
  await page.waitForFunction(() => {
    const bar = document.getElementById('auth-bar');
    return !!bar && getComputedStyle(bar).position === 'fixed';
  });
}

test.describe('shared chrome token + colour-law guards', () => {
  test('auth bar: tutorial, Team Builder, homepage, and hidden under the FCC shell', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApis(page);

    for (const size of SIZES) {
      await page.setViewportSize({ width: size[0], height: size[1] });

      await page.goto('/tutorial.html');
      await barReady(page);
      await page.waitForTimeout(400);
      if (captureShots) await shot(page, 'bar-tutorial-' + size[2] + '.png');
      if (!BEFORE) {
        const bar = await paint(page, '#auth-bar');
        expect(bar.bg).toBe(CHROME_RGB);
        expectNeutral(bar, 'auth bar');
        expectNeutral(await paint(page, '#auth-bar .nav-tutorials-link'), 'tutorials link');
        expectNeutral(await paint(page, '#auth-bar .auth-logout-btn'), 'log out');
        expectNeutral(await paint(page, '#auth-bar .auth-settings-btn'), 'settings gear');
      }

      // The tutorials alert state: forced here, the product sets it for an unread tutorial.
      await page.evaluate(() => {
        const link = document.querySelector('#auth-bar .nav-tutorials-link');
        if (!link) return;
        link.classList.add('is-alert-glow');
        if (!link.querySelector('.nav-tutorials-callout')) {
          const callout = document.createElement('span');
          callout.className = 'nav-tutorials-callout';
          callout.textContent = 'New tutorial';
          link.appendChild(callout);
        }
      });
      if (captureShots && size[2] === '1280') await shot(page, 'bar-tutorial-callout-1280.png');
      if (!BEFORE) {
        expectNeutral(await paint(page, '#auth-bar .nav-tutorials-callout'), 'tutorials callout');
        expectNeutral(await paint(page, '#auth-bar .nav-tutorials-link.is-alert-glow'), 'tutorials alert glow');
      }

      await page.goto('/team-builder.html?replaced_object_id=' + REPLACED + '&chapter=identity');
      await page.waitForSelector('#tb-id-name', { timeout: 30000 });
      await barReady(page);
      await page.waitForTimeout(400);
      if (captureShots) await shot(page, 'bar-team-builder-' + size[2] + '.png');
      if (!BEFORE) {
        expect((await paint(page, '#auth-bar')).bg).toBe(CHROME_RGB);
        const footer = await paint(page, '#site-footer a');
        expectNeutral(footer, 'footer link');
      }

      // Not a gob page and not editable in this batch: the bar must still resolve its tokens.
      await page.goto('/homepage.html');
      await page.waitForSelector('#auth-bar .auth-bar-right');
      await page.waitForTimeout(400);
      if (captureShots) await shot(page, 'bar-homepage-' + size[2] + '.png');
      if (!BEFORE) {
        const hpBar = await paint(page, '#auth-bar');
        expect(hpBar.bg).toBe(CHROME_RGB);
        const hpLink = await paint(page, '#auth-bar .nav-tutorials-link');
        expect(parseRgb(hpLink.color)[0], 'homepage tutorials link ' + hpLink.color).toBeGreaterThan(150);
      }

      await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
      await page.waitForSelector('html.gob-shell .top', { timeout: 30000 });
      await page.waitForTimeout(600);
      if (captureShots) await shot(page, 'fcc-' + size[2] + '.png');
      const fccBar = await paint(page, '#auth-bar');
      if (fccBar) expect(fccBar.display).toBe('none');
      const fccFooter = await paint(page, '#site-footer');
      if (fccFooter) expect(fccFooter.display).toBe('none');
    }
  });

  test('account modal and toast: neutral switch, accent and save feedback', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApis(page);
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/tutorial.html');
    await barReady(page);
    await page.waitForSelector('#account-settings-overlay', { state: 'attached' });

    // Nothing opens this modal today (the gear opens the Settings panel), but the bar
    // still builds it and its styles ship in auth-bar.css. Opened by hand here.
    await page.evaluate(() => {
      document.getElementById('account-settings-overlay').classList.add('is-visible');
      document.querySelector('#account-settings-overlay .account-modal-box').classList.add('is-entered');
      document.getElementById('account-settings-username').textContent = 'e2e';
      document.getElementById('account-avatar').textContent = 'E';
    });
    await page.waitForTimeout(350);
    if (captureShots) await shot(page, 'account-modal-1280.png');
    if (!BEFORE) {
      await expect(page.locator('#account-ambience-switch')).toHaveAttribute('aria-checked', 'true');
      expectNeutral(await paint(page, '#account-ambience-switch'), 'ambience switch on');
      expectNeutral(await paint(page, '#account-settings-overlay .gob-modal-accent'), 'account modal accent');
      expectNeutral(await paint(page, '#account-settings-overlay .gob-modal-box'), 'account modal box');
    }

    await page.locator('#account-ambience-switch').click();
    await page.waitForSelector('#account-toast.is-visible');
    await page.waitForTimeout(350);
    if (captureShots) await shot(page, 'account-toast-1280.png');
    if (!BEFORE) {
      expectNeutral(await paint(page, '#account-toast'), 'account toast');
      expectNeutral(await paint(page, '#account-toast .account-toast-icon'), 'account toast icon');
    }
  });

  test('FAQ and legal pages, and the shared switch on the account page', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApis(page);

    for (const size of SIZES) {
      await page.setViewportSize({ width: size[0], height: size[1] });

      // account.html is owned by the community pass. It reuses .account-switch and the
      // bar and footer from auth-bar.css, so only check that those still paint there.
      await page.goto('/account.html');
      await page.waitForSelector('#acct-ambience-switch', { timeout: 30000 });
      if (!BEFORE) {
        expect((await paint(page, '#auth-bar')).bg).toBe(CHROME_RGB);
        const sw = await paint(page, '#acct-ambience-switch');
        expectNeutral(sw, 'account page switch');
        expect(parseRgb(sw.bg)[3], 'switch background ' + sw.bg).toBeGreaterThan(0);
        expect(parseRgb(sw.border)[3], 'switch border ' + sw.border).toBeGreaterThan(0);
        expectNeutral(await paint(page, '#site-footer a'), 'footer link');
      }

      await page.goto('/faqs.html');
      await page.waitForSelector('.faqs-container h1');
      await barReady(page, { empty: true });
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'faqs-' + size[2] + '.png');
      if (!BEFORE) {
        expect((await paint(page, 'body')).bg).toBe(BG_RGB);
        expectNeutral(await paint(page, '.back-link'), 'FAQ back link');
        expectNeutral(await paint(page, '.faq-item a'), 'FAQ inline link');
      }

      await page.goto('/privacy.html');
      await page.waitForSelector('.legal-document h1');
      await barReady(page, { empty: true });
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'privacy-' + size[2] + '.png');
      if (!BEFORE) {
        expect((await paint(page, 'body')).bg).toBe(BG_RGB);
        expectNeutral(await paint(page, '.legal-back-link'), 'legal back link');
        expectNeutral(await paint(page, '.legal-document a'), 'legal inline link');
      }

      if (size[2] === '1280') {
        await page.goto('/terms.html');
        await page.waitForSelector('.legal-document h1');
        await barReady(page, { empty: true });
        await page.waitForTimeout(300);
        if (captureShots) await shot(page, 'terms-1280.png');
        if (!BEFORE) expectNeutral(await paint(page, '.legal-back-link'), 'terms back link');
      }
    }
  });

  test('Home Base alpha banner, page-load overlay and error screens', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApis(page, { alpha: true });

    for (const size of SIZES) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.goto('/mode-select.html');
      await page.waitForSelector('#alpha-disclaimer.visible', { timeout: 30000, state: 'attached' });
      // Trailer mode (css/trailer-mode.css, imported by fonts.css) hides the banner
      // app-wide. Un-hide it here so the shot and the guards see what ships when
      // trailer mode comes off.
      await page.addStyleTag({ content: 'body.mode-select-page #alpha-disclaimer.alpha-disclaimer.visible{display:flex !important}' });
      await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
      await page.waitForTimeout(400);
      if (captureShots) await shot(page, 'home-base-alpha-' + size[2] + '.png');
      if (!BEFORE) {
        expect((await paint(page, 'body')).bg).toBe(BG_RGB);
        expectNeutral(await paint(page, '#alpha-disclaimer'), 'alpha banner');
        expectNeutral(await paint(page, '.alpha-disclaimer-title'), 'alpha banner title');
      }

      await page.evaluate(() => window.PageLoadOverlay.show('Loading your season'));
      await page.waitForSelector('#page-load-overlay .page-load-overlay-message');
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'overlay-spinner-' + size[2] + '.png');

      await page.evaluate(() => window.PageLoadOverlay.show({
        variant: 'pulse',
        title: 'Simulating Week 12',
        subtitle: 'Lancaster at Four Corners',
        showBanner: false,
      }));
      await page.waitForFunction(() => {
        const pulse = document.querySelector('#page-load-overlay .page-load-overlay-pulse');
        return !!pulse && getComputedStyle(pulse).display !== 'none';
      });
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'overlay-pulse-' + size[2] + '.png');
      if (!BEFORE) {
        expectNeutral(await paint(page, '#page-load-overlay .page-load-overlay-pulse-indicator span'), 'overlay pulse bar');
        expectNeutral(await paint(page, '#page-load-overlay .page-load-overlay-pulse-title'), 'overlay title');
        const overlay = await paint(page, '#page-load-overlay');
        expect(parseRgb(overlay.bg), 'overlay bg ' + overlay.bg).toEqual([0, 0, 0, 0.92]);
      }
      await page.evaluate(() => window.PageLoadOverlay.hide());
    }

    const screens = [
      ['missing-pointer', () => window.ErrorHandler.showMissingPointerError({
        missingPointer: 'game_id',
        message: 'This page needs a game to load. Go back to the lineup and start again.',
        mode: 'franchise',
        recoveryOptions: { redirectTo: 'mode-select', redirectLabel: 'Back to Home Base' },
      })],
      ['missing-truth', () => window.ErrorHandler.showMissingTruthError({
        pointerType: 'game_id',
        pointerValue: 'g-123',
        message: 'Game g-123 was not found.',
        mode: 'franchise',
        recoveryOptions: { redirectTo: 'mode-select', redirectLabel: 'Back to Home Base' },
      })],
      ['version-mismatch', () => window.ErrorHandler.showVersionMismatchError({
        cacheType: 'lineup',
        expectedVersion: 3,
        actualVersion: 2,
        message: 'Your saved lineup is from an older version.',
        recoveryOptions: { redirectTo: 'reload', redirectLabel: 'Reload' },
      })],
    ];
    await page.setViewportSize({ width: 1280, height: 720 });
    for (const screen of screens) {
      await page.goto('/playbooks.html?mode=tutorial&franchise_id=' + FID + '&team_id=' + TID);
      await page.waitForFunction(() => !!window.ErrorHandler);
      await page.waitForLoadState('load');
      await page.evaluate(screen[1]);
      await page.waitForSelector('.error-screen .error-content');
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'error-' + screen[0] + '-1280.png');
      if (!BEFORE) {
        expect((await paint(page, '.error-screen')).bg).toBe(BG_RGB);
        expectNeutral(await paint(page, '.error-screen h1'), screen[0] + ' heading');
        expectNeutral(await paint(page, '.error-screen button'), screen[0] + ' primary button');
        expectNeutral(await paint(page, '.error-screen .error-content'), screen[0] + ' card');
      }
    }
  });
});
