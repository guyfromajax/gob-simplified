// @ts-check
/**
 * Office weekly card SFX. The "+N more" reveal is not a navigation, so it never
 * routed through go()/clickTiny and played no sound; it now carries
 * data-sfx="SFX_SELECT" and ticks once per click via the delegated hook. The
 * weekly-card links go through go() -> clickTiny (playSelect), which must be exactly
 * one sound per click (not doubled by also matching the data-sfx hook). Spied with
 * window.__gobSfxCalls.
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const OFFICE_HOME = path.join(__dirname, '../../FrontEnd/static/js/shared/officeHome.js');

const DIGEST = {
  state: 'win',
  result: { user_won: true, week: 22, site: 'home' },
  what_moved: {
    national_rank: { now: 18, delta: 4 },
    conference_standing: { now: 3, delta: 2 },
    record: { wins: 16, losses: 5 },
    streak: 'W4',
    attribute_changes: [],
  },
  also: { title: 'Rivalry win', href: '/franchise-command-center.html?tab=news-tab' },
  weekly_card_items: [
    { title: 'Rivalry win', href: '/franchise-command-center.html?tab=news-tab' },
    { title: 'Milestone reached', href: '/franchise-command-center.html?tab=news-tab' },
    { title: 'Streak extended', href: '/franchise-command-center.html?tab=news-tab' },
  ],
};

async function armAndRender(page) {
  await page.evaluate(async (digest) => {
    document.body.innerHTML = '<div id="office-root"></div>';
    const m = await import('/js/shared/uiSfx.js'); // import installs the data-sfx hook on document
    m.setChannelMuted('master', false);
    m.setChannelMuted('sfx', false);
    m.setChannelLevel('master', 100);
    m.setChannelLevel('sfx', 100);
    window.GOBNav = { go() {} }; // swallow link navigation so the page stays put
    window.__gobSfxCalls = [];
    window.GOBOffice.render(digest);
  }, DIGEST);
}

test.describe('office weekly card sfx', () => {
  test('"+N more" ticks once; a weekly link plays exactly one select', async ({ page }) => {
    await stubAuth(page);
    await page.goto('/mode-select.html');
    await page.addScriptTag({ path: OFFICE_HOME });
    await armAndRender(page);

    // The reveal toggle now plays exactly one SFX_SELECT.
    const toggle = page.locator('.wkc-more');
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect.poll(() => page.evaluate(() => window.__gobSfxCalls.slice())).toEqual(['SFX_SELECT']);

    // A weekly-card link (go() -> clickTiny) plays exactly one, not two.
    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.locator('.wkc-also .lnk').first().click();
    await expect.poll(() => page.evaluate(() => window.__gobSfxCalls.slice())).toEqual(['SFX_SELECT']);
  });

  test('"Moved most" never surfaces Momentum or Shooting, even as the top movers', async ({ page }) => {
    await stubAuth(page);
    await page.goto('/mode-select.html');
    await page.addScriptTag({ path: OFFICE_HOME });
    // Team snapshot whose biggest mover is momentum_score, with Shooting in the list too.
    // "Moved most" ranks only the eight signed-scale attributes (2026-10-02): Momentum is
    // never shown, and Shooting is on another scale. The Office shows the eligible mover.
    const digest = Object.assign({}, DIGEST, {
      team_snapshot: {
        state: 'in_season',
        moved_most: [
          { measure: 'momentum_score', value: 9, delta: 6 },
          { measure: 'offensive_efficiency', value: 5, delta: 3 },
          { measure: 'shot_threshold', value: 88, delta: 2 },
        ],
      },
    });
    await page.evaluate((d) => {
      document.body.innerHTML = '<div id="office-root"></div>';
      window.GOBNav = { go() {} };
      window.GOBOffice.render(d);
    }, digest);

    const snap = page.locator('.office-snap');
    await expect(snap).toBeVisible();
    await expect(snap).toContainText('Team Attributes Moved Most');
    await expect(snap).toContainText('Offense');
    await expect(snap).not.toContainText('Shooting');
    await expect(snap).not.toContainText('Momentum');
  });
});
