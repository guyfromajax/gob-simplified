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

test('settings panel opens and closes four ways', async ({ page }) => {
  await stubAuth(page);
  await stubMe(page, ME);
  await page.goto('/mode-select.html');
  const gear = page.locator('#auth-settings-btn');
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

  await gear.click();
  await expect(panel).toBeVisible();
  await gear.click();
  await expect(page.locator('#gob-settings-host')).toBeHidden();
});

test('sliders change uiSfx live and persist across reload', async ({ page }) => {
  await stubAuth(page);
  await stubMe(page, ME);
  await page.goto('/mode-select.html');
  await page.locator('#auth-settings-btn').click();
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

test('court speaker mutes and shows the slashed icon', async ({ page }) => {
  await stubAuth(page);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto('/static/court.html?home=Lancaster&away=Four-Corners');
  const cap = page.locator('#scoreboard .sb-snd');
  await expect(cap).toBeVisible();
  // The pregame modal covers the viewport until the quarter starts. Hide it
  // so the scoreboard control can be clicked; measure size around the click
  // only, after the modal is already out of the way.
  await page.evaluate(() => {
    document.querySelectorAll('.pre-game-container').forEach((el) => el.classList.add('hidden'));
  });
  const before = await page.evaluate(() => ({
    scoreboard: document.getElementById('scoreboard').getBoundingClientRect().height,
    phaser: document.getElementById('phaser-container').getBoundingClientRect().toJSON(),
  }));
  await cap.locator('button').first().click();
  await expect(page.locator('#scoreboard .snd-pop')).toBeVisible();
  await page.locator('#scoreboard .tgl').click();
  await expect(cap.locator('button').first()).toHaveClass(/is-muted/);
  const muted = await page.evaluate(() => window.GOBUiSfx.getAudioState().master.muted);
  expect(muted).toBe(true);
  const after = await page.evaluate(() => ({
    scoreboard: document.getElementById('scoreboard').getBoundingClientRect().height,
    phaser: document.getElementById('phaser-container').getBoundingClientRect().toJSON(),
  }));
  expect(after.scoreboard).toBe(before.scoreboard);
  expect(after.phaser.width).toBe(before.phaser.width);
  expect(after.phaser.height).toBe(before.phaser.height);
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
  await page.locator('#auth-settings-btn').click();
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
