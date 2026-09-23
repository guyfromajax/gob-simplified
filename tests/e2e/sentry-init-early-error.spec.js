// @ts-check
/**
 * sentryInit must capture a throw from a later classic <script> that runs
 * before DOMContentLoaded. The SDK loads async; errors in that window are
 * queued and flushed after Sentry.init.
 */
const { test, expect } = require('@playwright/test');

test('Sentry captures an error thrown before DOMContentLoaded', async ({ page }) => {
  await page.route('**/app-config', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sentryDsn: 'https://key@example.ingest.sentry.io/1' }),
    }));
  await page.route('**/browser.sentry-cdn.com/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/javascript',
      body: [
        'window.Sentry = {',
        '  init: function () { window.__sentryInited = true; },',
        '  setUser: function () {},',
        '  captureException: function (err) {',
        '    window.__sentryCaptured = window.__sentryCaptured || [];',
        '    window.__sentryCaptured.push(String(err && err.message || err));',
        '  }',
        '};',
      ].join('\n'),
    }));

  await page.goto('/?sentry-early=1');
  await page.setContent(`<!doctype html>
<html><head>
<script src="/js/shared/sentryInit.js"></script>
<script>throw new Error('early-boot-boom');</script>
<script src="/js/config/api-config.js"></script>
</head><body></body></html>`, { waitUntil: 'load' });

  await expect.poll(() => page.evaluate(() => window.__sentryInited === true)).toBe(true);
  const captured = await page.evaluate(() => window.__sentryCaptured || []);
  expect(captured.some((m) => String(m).includes('early-boot-boom'))).toBe(true);
});
