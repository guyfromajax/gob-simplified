const { test, expect } = require('@playwright/test');
const { stubAuth } = require('./helpers/auth');

test('cold in-app back stays inside the app', async ({ page }) => {
  await stubAuth(page);
  await page.goto('/alpha-feedback.html');
  await page.evaluate(() => {
    window.__gobHistoryBacks = 0;
    const orig = history.back.bind(history);
    history.back = function () {
      window.__gobHistoryBacks += 1;
      return orig();
    };
  });
  await page.locator('#af-back').click();
  await expect(page).toHaveURL(/\/(mode-select|franchise-command-center)\.html/);
  const backs = await page.evaluate(() => window.__gobHistoryBacks || 0);
  expect(backs).toBe(0);
});

test('in-progress lineup peeks push and flow steps replace', async ({ request }) => {
  const lineup = await (await request.get('/set-lineup.js')).text();
  const box = await (await request.get('/box-score.js')).text();
  const nav = await (await request.get('/js/shared/gobNav.js')).text();
  expect(lineup).toContain('window.GOBNav.go(next)');
  expect(lineup).toContain('window.GOBNav.go(boxUrl)');
  expect(lineup).toContain("window.GOBNav.replace(`/game-plan.html?");
  expect(box).toContain('window.GOBNav.back(backUrl)');
  expect(box).toContain('window.GOBNav.back(lineupUrl)');
  expect(nav).toContain("'/api/game/' + encodeURIComponent(gameId) + '/resume-state'");
  expect(nav).toContain('function exitFlow(');
  expect(nav).not.toContain('encodeURIComponent(gameId));');
  const timeout = await (await request.get('/js/phaser/utils/timeoutButtonManager.js')).text();
  const foul = await (await request.get('/js/phaser/utils/foulOutPopup.js')).text();
  const popup = await (await request.get('/js/phaser/utils/gameCompletionPopup.js')).text();
  expect(timeout).toContain('window.GOBNav.replace(lineupUrl)');
  expect(timeout).not.toContain('window.location.href = `/set-lineup.html');
  expect(foul).toContain('data-gob-replace');
  expect(popup).toContain('data-gob-replace');
  expect(popup).toContain("window.GOBNav.exitFlow(lockerRoomUrl, { tab: 'home-tab' })");
});

test('section tab clicks do not add history entries', async ({ page }) => {
  await stubAuth(page);
  await page.goto('/coaching-archetypes.html');
  await page.evaluate(() => {
    document.body.insertAdjacentHTML('beforeend', [
      '<div class="tab-buttons">',
      '<button type="button" data-tab="home-tab">Home</button>',
      '<button type="button" data-tab="standings-tab">Standings</button>',
      '<button type="button" data-tab="schedule-tab">Schedule</button>',
      '<button type="button" data-tab="recruits-tab">Recruits</button>',
      '</div>',
      '<div id="home-tab" class="tab-content"></div>',
      '<div id="standings-tab" class="tab-content"></div>',
      '<div id="schedule-tab" class="tab-content"></div>',
      '<div id="recruits-tab" class="tab-content"></div>',
    ].join(''));
  });
  await page.addScriptTag({ url: '/js/shared/commandCenterTabs.js' });
  await page.evaluate(() => {
    window.CommandCenterTabs.initCommandCenterTabs({ defaultTab: 'home-tab' });
  });
  const before = await page.evaluate(() => history.length);
  await page.locator('[data-tab="standings-tab"]').click();
  await page.locator('[data-tab="schedule-tab"]').click();
  await page.locator('[data-tab="recruits-tab"]').click();
  await page.locator('[data-tab="home-tab"]').click();
  const after = await page.evaluate(() => history.length);
  expect(after).toBe(before);
  await expect(page).toHaveURL(/tab=home-tab/);
  await page.goBack();
  await expect(page).not.toHaveURL(/coaching-archetypes\.html/);
});
