// @ts-check
/**
 * Ops / desktop-shell surfaces: splash, crash, 404, maintenance.
 * Desktop HTML is opened as file:// (Electron is not driven headless).
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/shell-404-maintenance');
const DESKTOP = path.join(__dirname, '../../desktop');

function fileUrl(rel, query) {
  const full = path.join(DESKTOP, rel);
  let url = 'file://' + full;
  if (query) url += '?' + query;
  return url;
}

async function shot(page, name) {
  await page.evaluate(() => { window.scrollTo(0, 0); });
  await page.screenshot({ path: path.join(SHOTS, name) });
}

test.describe('shell 404 maintenance', () => {
  test.beforeAll(() => {
    fs.mkdirSync(SHOTS, { recursive: true });
  });

  test('desktop splash and crash via file://', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(fileUrl('splash.html'));
    await expect(page.locator('h1')).toContainText('Starting the local engine');
    await expect(page.locator('img.mark')).toBeVisible();
    await shot(page, 'splash-after-1280.png');

    await page.goto(fileUrl('error.html', 'message=' + encodeURIComponent('Sample: the engine exited (code 1). See engine.log.')));
    await expect(page.locator('h1')).toContainText('The game engine stopped');
    await expect(page.locator('#message')).toContainText('Sample: the engine exited');
    await shot(page, 'crash-after-1280.png');
  });

  test('web 404 and maintenance', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    const res = await page.goto('/some-missing-page');
    expect(res && res.status()).toBe(404);
    await expect(page.locator('h1')).toContainText("This page doesn't exist");
    await expect(page.locator('.ops-mark')).toBeVisible();
    await shot(page, '404-web-1280.png');

    await page.goto('/maintenance.html');
    await expect(page.locator('h1')).toContainText("We'll be right back");
    await expect(page.locator('.ops-mark')).toBeVisible();
    await shot(page, 'maintenance-after-1280.png');
  });
});
