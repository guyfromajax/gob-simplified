// @ts-check
/**
 * data-sfx plays once and respects mute; a missing sting never throws or
 * blocks a modal; Advance plays SFX_ADVANCE once per click, not twice.
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const ADVANCE = path.join(__dirname, '../../FrontEnd/static/js/shared/gobAdvance.js');
const MOMENTS = path.join(__dirname, '../../FrontEnd/static/js/shared/championshipMoments.js');

async function installFakeAudio(page) {
  await page.addInitScript(() => {
    window.__sfxPlays = [];
    class FakeAudio {
      constructor(src) {
        this.src = src || '';
        this.volume = 1;
        this.currentTime = 0;
        this.paused = true;
      }
      play() {
        window.__sfxPlays.push(this.src);
        return Promise.resolve();
      }
      pause() {}
      addEventListener() {}
      removeEventListener() {}
      cloneNode() { return new FakeAudio(this.src); }
    }
    window.Audio = FakeAudio;
  });
}

async function importBus(page) {
  await page.evaluate(async () => {
    const m = await import('/js/shared/uiSfx.js');
    m.setChannelMuted('master', false);
    m.setChannelMuted('sfx', false);
    m.setChannelLevel('master', 100);
    m.setChannelLevel('sfx', 100);
  });
}

function playsOf(srcs, needle) {
  return (srcs || []).filter((src) => String(src).indexOf(needle) !== -1);
}

test.describe('reward-gold sfx hooks', () => {
  test('data-sfx click plays once and respects mute', async ({ page }) => {
    await installFakeAudio(page);
    await stubAuth(page);
    await page.goto('/mode-select.html');
    await importBus(page);
    await page.evaluate(() => {
      window.__sfxPlays = [];
      const btn = document.createElement('button');
      btn.id = 'sfx-probe';
      btn.setAttribute('data-sfx', 'SFX_SELECT');
      btn.textContent = 'probe';
      document.body.appendChild(btn);
    });

    await page.locator('#sfx-probe').click();
    let srcs = await page.evaluate(() => window.__sfxPlays.slice());
    expect(playsOf(srcs, 'click-tiny.wav')).toHaveLength(1);

    await page.evaluate(async () => {
      window.__sfxPlays = [];
      const m = await import('/js/shared/uiSfx.js');
      m.setChannelMuted('sfx', true);
    });
    await page.locator('#sfx-probe').click();
    srcs = await page.evaluate(() => window.__sfxPlays.slice());
    expect(playsOf(srcs, 'click-tiny.wav')).toHaveLength(0);

    await page.evaluate(async () => {
      const m = await import('/js/shared/uiSfx.js');
      m.setChannelMuted('sfx', false);
      m.setChannelLevel('master', 0);
    });
    await page.locator('#sfx-probe').click();
    srcs = await page.evaluate(() => window.__sfxPlays.slice());
    expect(playsOf(srcs, 'click-tiny.wav')).toHaveLength(0);
  });

  test('missing sting file does not throw or block a modal', async ({ page }) => {
    await stubAuth(page);
    const pageErrors = [];
    page.on('pageerror', (err) => pageErrors.push(String(err && err.message ? err.message : err)));
    await page.goto('/mode-select.html');
    const closed = await page.evaluate(async () => {
      const m = await import('/js/shared/uiSfx.js');
      const dialog = document.createElement('dialog');
      dialog.id = 'sfx-sting-modal';
      dialog.innerHTML = '<p>sting</p><button type="button" id="sfx-sting-close">Close</button>';
      document.body.appendChild(dialog);
      dialog.showModal();
      m.playSfx(m.STING_WIN);
      document.getElementById('sfx-sting-close').click();
      dialog.close();
      return !dialog.open;
    });
    expect(closed).toBe(true);
    expect(pageErrors).toEqual([]);
  });

  test('Advance plays SFX_ADVANCE once per click', async ({ page }) => {
    await installFakeAudio(page);
    await stubAuth(page);
    await page.goto('/mode-select.html');
    await importBus(page);
    await page.addScriptTag({ path: ADVANCE });
    await page.evaluate(() => {
      window.__sfxPlays = [];
      const play = document.createElement('button');
      play.id = 'play-now';
      play.type = 'button';
      play.dataset.mode = 'recruit-invites';
      play.textContent = 'Set Recruit Invites';
      document.body.appendChild(play);
      window.GOBAdvance.bind(play, function () { return {}; });
    });
    await page.locator('#play-now').click();
    await page.waitForFunction(() => (window.__sfxPlays || []).some((src) => String(src).indexOf('confirm-1-lowervol.wav') !== -1));
    const srcs = await page.evaluate(() => window.__sfxPlays.slice());
    expect(playsOf(srcs, 'confirm-1-lowervol.wav')).toHaveLength(1);
  });

  test('championship moment requests STING_SEASON_PEAK when it opens', async ({ page }) => {
    await installFakeAudio(page);
    await stubAuth(page);
    await page.goto('/mode-select.html');
    await importBus(page);
    await page.addScriptTag({ path: MOMENTS });
    await page.evaluate(() => { window.__sfxPlays = []; });
    await page.evaluate(() => {
      window.ChampionshipMoments.showMoment({
        type: 'trophy_spotlight',
        season: 2,
        conference: 'East',
        winner_team_name: 'Lancaster',
        winner_natl_rank: 4,
        winner_seed: 1,
        winner_record: { wins: 28, losses: 4 },
        winner_primary_color: '#224488',
        user_is_winner: true,
      }, {});
    });
    await page.waitForFunction(() => (window.__sfxPlays || []).some((src) => String(src).indexOf('sting-season-peak.wav') !== -1));
    const srcs = await page.evaluate(() => window.__sfxPlays.slice());
    expect(playsOf(srcs, 'sting-season-peak.wav')).toHaveLength(1);
  });

  test('another team\'s championship moment plays no sting', async ({ page }) => {
    await installFakeAudio(page);
    await stubAuth(page);
    await page.goto('/mode-select.html');
    await importBus(page);
    await page.addScriptTag({ path: MOMENTS });
    await page.evaluate(() => { window.__sfxPlays = []; });
    await page.evaluate(() => {
      window.ChampionshipMoments.showMoment({
        type: 'conference_championship',
        season: 2,
        conference: 'East',
        winner_team_name: 'Four Corners',
        loser_team_name: 'Lancaster',
        score: { winner: 70, loser: 61 },
        winner_primary_color: '#224488',
        user_is_winner: false,
      }, {});
    });
    await expect(page.locator('.cm-overlay.is-visible')).toBeVisible();
    await page.waitForTimeout(1200);
    const srcs = await page.evaluate(() => window.__sfxPlays.slice());
    expect(playsOf(srcs, 'sting-season-peak.wav')).toHaveLength(0);
  });
});
