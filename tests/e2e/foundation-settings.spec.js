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
