// @ts-check
/**
 * Chapter 8 SFX sweep: the controls this branch wired play exactly one
 * named sound, and none when the sfx channel is muted.
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const SEASON_PEAK = path.join(__dirname, '../../FrontEnd/static/js/shared/seasonPeak.js');
const MILESTONE = path.join(__dirname, '../../FrontEnd/static/js/shared/milestoneModal.js');
const LEAVE = path.join(__dirname, '../../FrontEnd/static/js/shared/gobLeaveConfirm.js');

async function armSpy(page) {
  await page.evaluate(async () => {
    const m = await import('/js/shared/uiSfx.js');
    m.setChannelMuted('master', false);
    m.setChannelMuted('sfx', false);
    m.setChannelLevel('master', 100);
    m.setChannelLevel('sfx', 100);
    window.__gobSfxCalls = [];
  });
}

test.describe('ch8 sfx hooks', () => {
  test('fixed controls play one named sound, and none when muted', async ({ page }) => {
    await stubAuth(page);
    await page.goto('/mode-select.html');
    await page.addScriptTag({ path: SEASON_PEAK });
    await page.addScriptTag({ path: MILESTONE });
    await page.addScriptTag({ path: LEAVE });
    await armSpy(page);

    await page.evaluate(async () => {
      await import('/js/shared/gobSettings.js');
      window.GOBSettings.open();
    });
    await page.locator('[data-settings-close]').click();
    let calls = await page.evaluate(() => window.__gobSfxCalls.slice());
    expect(calls).toEqual(['SFX_SELECT']);

    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.evaluate(() => {
      window.SeasonPeak.showTitle({
        moments: [{
          type: 'national_championship',
          season: 2,
          winner_team_name: 'Lancaster',
          loser_team_name: 'Harbor City',
          score: { winner: 72, loser: 66 },
        }],
      });
    });
    await expect(page.locator('.pk-go')).toBeVisible();
    await page.waitForTimeout(700);
    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.locator('.pk-go').click();
    calls = await page.evaluate(() => window.__gobSfxCalls.slice());
    expect(calls).toEqual(['SFX_SELECT']);

    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.evaluate(() => {
      window.MilestoneModal.show({
        item: { kind: 'walk_on_welcome', style: 'gold', sting: 'STING_MILESTONE' },
        payload: { walk_ons: [{ name: 'Jordan Price' }] },
        index: 1,
        total: 1,
        isLast: true,
      });
    });
    await expect(page.locator('.mm-go')).toBeVisible();
    await page.waitForTimeout(300);
    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.locator('.mm-go').click();
    calls = await page.evaluate(() => window.__gobSfxCalls.slice());
    expect(calls).toEqual(['SFX_SELECT']);

    await page.evaluate(() => { window.__gobSfxCalls = []; });
    await page.evaluate(() => {
      window.GOBLeaveConfirm.open({ title: 'Unsaved', copy: 'Leave?' });
    });
    await page.locator('[data-leave="stay"]').click();
    calls = await page.evaluate(() => window.__gobSfxCalls.slice());
    expect(calls).toEqual(['SFX_SELECT']);

    await page.evaluate(async () => {
      const m = await import('/js/shared/uiSfx.js');
      m.setChannelMuted('sfx', true);
      window.__gobSfxCalls = [];
      window.GOBSettings.open();
    });
    await page.locator('[data-settings-close]').click();
    calls = await page.evaluate(() => window.__gobSfxCalls.slice());
    expect(calls).toEqual([]);
  });
});
