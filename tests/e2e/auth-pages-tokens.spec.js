const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// Auth / entry pages (login, signup + alpha access code, reset password) on
// gob tokens + colour law. Visual only: every API call here is stubbed.
// AUTH_PAGES_BEFORE=1 writes before-*.png (run on origin/develop CSS) and skips the guards.

test.describe.configure({ timeout: 120000 });

const OUT = path.join(__dirname, '../../reports/auth-pages-tokens');
const CAPTURE_BEFORE = process.env.AUTH_PAGES_BEFORE === '1';
const PREFIX = CAPTURE_BEFORE ? 'before' : 'after';
const SIZES = [
  { w: 1280, h: 720 },
  { w: 1920, h: 1080 },
];

// Computed colours arrive as rgb()/rgba(), or as color(srgb r g b / a) when
// the source is color-mix(); both are parsed to 0–255 channels.
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
function isBlue(rgb) {
  const p = parseRgba(rgb);
  return !!p && p.a >= 0.05 && p.b > p.r + 40 && p.b > 100;
}
function isRed(rgb) {
  const p = parseRgba(rgb);
  return !!p && p.a >= 0.1 && p.r > 200 && p.g < 170 && p.b < 170 && p.r - p.g > 60;
}
const hasOrange = (v) => paints(v).some(isOrange);
const hasGreen = (v) => paints(v).some(isGreen);
const hasBlue = (v) => paints(v).some(isBlue);

async function installApi(page, opts) {
  const o = opts || {};
  await page.route('**/*', async (route) => {
    const req = route.request();
    let pathname = '';
    try { pathname = new URL(req.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (/googletagmanager|sentry|google-analytics/.test(req.url())) {
      await route.fulfill({ status: 204, body: '' });
      return;
    }
    if (pathname === '/app-config') return json(200, { isAlpha: !!o.alpha, alphaDisclaimer: null, version: '1.0', sentryDsn: null, teamBuilderEnabled: true });
    if (pathname === '/api/auth/login') return json(401, { detail: 'Invalid email or password' });
    if (pathname === '/api/auth/check-access-code') return json(200, o.codeValid ? { valid: true } : { valid: false, reason: 'invalid' });
    if (pathname === '/api/auth/reset-request') return json(200, { message: 'If that email exists, a reset link is on its way.' });
    if (pathname === '/api/auth/me') return json(401, { detail: 'Not authenticated' });
    if (pathname.startsWith('/api/')) return json(200, {});
    await route.continue();
  });
}

async function open(page, url, size, opts) {
  await page.setViewportSize({ width: size.w, height: size.h });
  await page.addInitScript((base) => {
    if (base) window.API_BASE_URL = base;
    try { localStorage.removeItem('auth_token'); localStorage.removeItem('auth_user'); } catch (_) {}
  }, process.env.BASE_URL || '');
  await installApi(page, opts);
  await page.goto(url, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts && document.fonts.ready);
  await page.waitForTimeout(250);
}

async function shot(page, name, size) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT, `${PREFIX}-${name}-${size.w}.png`) });
}

async function loginError(page) {
  await page.fill('#email', 'coach@example.com');
  await page.fill('#password', 'wrong-password1');
  await page.locator('#login-form button[type="submit"]').click();
  await page.locator('#error-message').filter({ hasText: /Invalid/ }).waitFor();
}

async function codeError(page) {
  await page.fill('#otp-code', 'BADCODE');
  await page.locator('#continue-code-btn').click();
  await page.locator('#code-error').filter({ hasText: /./ }).waitFor();
}

async function codeAccepted(page) {
  await page.fill('#otp-code', 'GOODCODE');
  await page.locator('#continue-code-btn').click();
  await page.locator('#code-accepted-msg').waitFor({ state: 'visible' });
}

test.describe('auth pages tokens', () => {
  for (const size of SIZES) {
    test(`shots ${size.w}`, async ({ page }) => {
      await open(page, '/login.html', size);
      await shot(page, 'login', size);
      await loginError(page);
      await shot(page, 'login-error', size);

      await open(page, '/signup.html', size, { alpha: true });
      await page.locator('#otp-code').waitFor();
      await shot(page, 'signup-code', size);
      await codeError(page);
      await shot(page, 'signup-code-error', size);

      await open(page, '/signup.html', size, { alpha: true, codeValid: true });
      await codeAccepted(page);
      await shot(page, 'signup-account', size);

      await open(page, '/signup.html', size, { alpha: true });
      await page.locator('#request-access-link').click();
      await page.locator('.access-request-modal-backdrop.open').waitFor();
      await shot(page, 'signup-request-access', size);

      await open(page, '/reset-password.html', size);
      await shot(page, 'reset-request', size);
      await page.fill('#email', 'coach@example.com');
      await page.locator('#request-form button[type="submit"]').click();
      await page.locator('#success-message:visible').waitFor();
      await shot(page, 'reset-sent', size);

      await open(page, '/reset-password.html?token=e2e-token', size);
      await page.locator('#set-section').waitFor({ state: 'visible' });
      await shot(page, 'reset-set', size);
    });
  }

  test('colour law guards', async ({ page }) => {
    test.skip(CAPTURE_BEFORE, 'before capture');
    const size = SIZES[0];

    for (const url of ['/login.html', '/signup.html', '/reset-password.html']) {
      await open(page, url, size);
      const t = await page.evaluate(() => {
        const root = getComputedStyle(document.documentElement);
        const body = getComputedStyle(document.body);
        const before = getComputedStyle(document.body, '::before');
        const title = document.querySelector('.auth-title');
        return {
          gob: document.documentElement.classList.contains('gob'),
          text100: root.getPropertyValue('--text-100').trim(),
          bodyFont: body.fontFamily,
          bodyBg: body.backgroundColor,
          atmosphere: before.backgroundImage,
          titleFont: title ? getComputedStyle(title).fontFamily : '',
          footerLink: document.querySelector('.auth-footer a') ? getComputedStyle(document.querySelector('.auth-footer a')).color : '',
        };
      });
      expect(t.gob, `${url} html.gob`).toBe(true);
      expect(t.text100, `${url} --text-100`).not.toBe('');
      expect(t.bodyFont, `${url} body Inter`).toMatch(/Inter/);
      expect(t.titleFont, `${url} title Bebas`).toMatch(/Bebas Neue/);
      expect(hasBlue(t.atmosphere), `${url} no blue atmosphere ${t.atmosphere}`).toBe(false);
      expect(hasBlue(t.bodyBg) || hasOrange(t.bodyBg), `${url} body bg ${t.bodyBg}`).toBe(false);
      if (t.footerLink) expect(hasOrange(t.footerLink), `${url} footer link ${t.footerLink}`).toBe(false);
    }

    // Login: LOG IN enters the game -> green gate, Bebas. Focus ring and links neutral. Error red.
    await open(page, '/login.html', size);
    await page.locator('#email').focus();
    const login = await page.evaluate(() => {
      const b = getComputedStyle(document.querySelector('#login-form button[type="submit"]'));
      const f = getComputedStyle(document.getElementById('email'));
      return { bg: b.backgroundColor, ink: b.color, font: b.fontFamily, focus: f.borderTopColor, ring: f.boxShadow };
    });
    expect(isGreen(login.bg), `LOG IN green ${login.bg}`).toBe(true);
    expect(login.font).toMatch(/Bebas Neue/);
    const ink = parseRgba(login.ink);
    expect(ink && ink.r < 60 && ink.g < 60 && ink.b < 60, `LOG IN dark ink ${login.ink}`).toBe(true);
    expect(hasOrange(login.focus) || hasOrange(login.ring), `focus ${login.focus} ${login.ring}`).toBe(false);
    await page.locator('.forgot-password-link').hover();
    const forgot = await page.locator('.forgot-password-link').evaluate((el) => getComputedStyle(el).color);
    expect(hasOrange(forgot), `forgot hover ${forgot}`).toBe(false);
    await loginError(page);
    const err = await page.locator('#error-message').evaluate((el) => {
      const s = getComputedStyle(el);
      return { color: s.color, border: s.borderTopColor };
    });
    expect(isRed(err.color), `error text red ${err.color}`).toBe(true);
    expect(isRed(err.border), `error border red ${err.border}`).toBe(true);

    // Signup code step: Continue is neutral; hint link neutral; code error red.
    await open(page, '/signup.html', size, { alpha: true });
    await page.locator('#otp-code').waitFor();
    const code = await page.evaluate(() => ({
      cont: getComputedStyle(document.getElementById('continue-code-btn')).backgroundColor,
      hint: getComputedStyle(document.getElementById('request-access-link')).color,
    }));
    expect(hasOrange(code.cont) || hasGreen(code.cont), `code Continue ${code.cont}`).toBe(false);
    expect(hasOrange(code.hint), `request access link ${code.hint}`).toBe(false);
    await codeError(page);
    const codeErr = await page.locator('#code-error').evaluate((el) => getComputedStyle(el).color);
    expect(isRed(codeErr), `code error red ${codeErr}`).toBe(true);

    // Accepted code: status label neutral, change link neutral; SIGN UP enters the game -> green.
    await open(page, '/signup.html', size, { alpha: true, codeValid: true });
    await codeAccepted(page);
    const acc = await page.evaluate(() => ({
      accepted: getComputedStyle(document.getElementById('code-accepted-msg')).color,
      change: getComputedStyle(document.getElementById('change-code-link')).color,
      submit: getComputedStyle(document.querySelector('#signup-form button[type="submit"], form button[type="submit"]:not(#request-access-submit)')).backgroundColor,
    }));
    expect(hasGreen(acc.accepted), `code accepted ${acc.accepted}`).toBe(false);
    expect(hasOrange(acc.change), `change link ${acc.change}`).toBe(false);
    expect(isGreen(acc.submit), `SIGN UP green ${acc.submit}`).toBe(true);

    // Request-access modal: submit neutral, accent bar neutral.
    await open(page, '/signup.html', size, { alpha: true });
    await page.locator('#request-access-link').click();
    await page.locator('.access-request-modal-backdrop.open').waitFor();
    const modal = await page.evaluate(() => ({
      submit: getComputedStyle(document.getElementById('request-access-submit')).backgroundColor,
      bar: getComputedStyle(document.querySelector('.access-request-modal'), '::before').backgroundColor,
    }));
    expect(hasOrange(modal.submit) || hasGreen(modal.submit), `request submit ${modal.submit}`).toBe(false);
    expect(hasOrange(modal.bar), `modal bar ${modal.bar}`).toBe(false);

    // Reset: submits neutral (they do not enter the game); success message not green.
    await open(page, '/reset-password.html', size);
    const reset = await page.locator('#request-form button[type="submit"]').evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(hasOrange(reset) || hasGreen(reset), `reset submit ${reset}`).toBe(false);
    await page.fill('#email', 'coach@example.com');
    await page.locator('#request-form button[type="submit"]').click();
    await page.locator('#success-message:visible').waitFor();
    const ok = await page.locator('#success-message').evaluate((el) => {
      const s = getComputedStyle(el);
      return { color: s.color, border: s.borderTopColor, bg: s.backgroundColor };
    });
    for (const [k, v] of Object.entries(ok)) expect(hasGreen(v), `success ${k} ${v}`).toBe(false);
  });
});
