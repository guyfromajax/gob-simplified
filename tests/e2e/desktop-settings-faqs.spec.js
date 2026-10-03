// @ts-check
/**
 * Desktop profile against the real loopback engine: the Settings FAQs link opens
 * /faqs.html from 127.0.0.1 in a second window and the game window stays put.
 * desktop/main.js allows window.open for loopback URLs, so Electron does the same.
 */
const { test, expect } = require('@playwright/test');

const PORT = process.env.PORT || process.env.GOB_LOOPBACK_PORT || '8767';

test('the loopback serves faqs.html and Settings opens it in a new window', async ({ page, request }) => {
  const res = await request.get('/faqs.html');
  expect(res.status()).toBe(200);
  expect(await res.text()).toContain('<h1');

  await page.addInitScript((port) => {
    window.GOB_BUILD_PROFILE = 'desktop';
    window.GOB_LOOPBACK_PORT = Number(port);
  }, PORT);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/mode-select.html');
  await page.evaluate(async () => {
    const mod = await import('/js/shared/gobSettings.js');
    mod.openSettings();
  });
  await expect(page.locator('[data-conn-label]')).toHaveText('Offline');
  const faqs = page.locator('#gob-settings-host a[data-settings-faqs]');
  await expect(faqs).toBeVisible();
  const before = page.url();
  const [popup] = await Promise.all([page.waitForEvent('popup'), faqs.click()]);
  await popup.waitForLoadState('domcontentloaded');
  const url = new URL(popup.url());
  expect(url.hostname).toBe('127.0.0.1');
  expect(url.pathname).toMatch(/\/faqs\.html$/);
  await expect(popup.locator('h1').first()).toBeVisible();
  expect(page.url()).toBe(before);
});
