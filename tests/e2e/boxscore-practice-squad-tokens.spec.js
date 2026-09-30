const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

const FID = 'f-e2e-box-ps-tokens';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const OUT = path.join(__dirname, '../../reports/boxscore-practice-squad-tokens');

const GREEN_RGB = 'rgb(52, 236, 39)';

function ccData(overrides) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 12,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: true,
    cut_count: 2,
    team_record: { wins: 8, losses: 4 },
    recruiting_wire: {},
    user_conference: 1,
    user_region: 'A',
  }, overrides || {});
}

const ROSTER = [
  {
    _id: '111111111111111111111101',
    name: 'Ada Keeper',
    position_ratings: { PG: 72, SG: 60, SF: 50, PF: 40, C: 30 },
    attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
    height: 74,
    weight: 190,
    year: 'FR',
  },
  {
    _id: '111111111111111111111102',
    name: 'Bea Reserve',
    position_ratings: { PG: 68, SG: 58, SF: 48, PF: 38, C: 28 },
    attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
    height: 76,
    weight: 205,
    year: 'SO',
  },
  {
    _id: '111111111111111111111103',
    name: 'Cy Bench',
    position_ratings: { PG: 65, SG: 55, SF: 45, PF: 35, C: 25 },
    attributes: { SC: 50, SH: 50, ID: 50, OD: 50, PS: 50, BH: 50, RB: 50, ST: 50, AG: 50, ND: 50, IQ: 50, FT: 50 },
    height: 78,
    weight: 210,
    year: 'JR',
  },
];

const BOX_PLAYERS = [
  { name: 'Jalen Carter', playerId: 'p1', team: 'home', position: 'PG', jersey: 1, stats: { pts: 22, reb: 5, ast: 4, min: 32 } },
  { name: 'Omar Lane', playerId: 'p2', team: 'away', position: 'SG', jersey: 2, stats: { pts: 18, reb: 3, ast: 2, min: 30 } },
];

async function fulfillJson(route, body) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function routeApiOnly(route) {
  const request = route.request();
  let pathname = '';
  try { pathname = new URL(request.url()).pathname; } catch (err) {
    await route.continue();
    return false;
  }
  const api = pathname.startsWith('/api/')
    || pathname.startsWith('/franchise/')
    || pathname.startsWith('/roster/')
    || pathname === '/app-config'
    || pathname === '/teams';
  if (!api) {
    await route.continue();
    return false;
  }
  return pathname;
}

async function installBoxApis(page) {
  await page.route('**/*', async (route) => {
    const pathname = await routeApiOnly(route);
    if (!pathname) return;
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, ccData());
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, { players: ROSTER, conference: 1, region: 'A', team_chemistry: 15 });
      return;
    }
    if (pathname.indexOf('/api/game/') === 0 && pathname.indexOf('resume-state') === -1) {
      const homeBox = {};
      const awayBox = {};
      BOX_PLAYERS.forEach(function (player) {
        const slot = Object.assign({ name: player.name, playerId: player.playerId }, player.stats);
        if (player.team === 'away') awayBox[player.position + player.jersey] = slot;
        else homeBox[player.position + player.jersey] = slot;
      });
      const boxScore = {};
      boxScore.Lancaster = homeBox;
      boxScore['Four Corners'] = awayBox;
      await fulfillJson(route, {
        home_team_id: TID,
        away_team_id: OPP,
        teams: { [TID]: { name: 'Lancaster' }, [OPP]: { name: 'Four Corners' } },
        home_team: { name: 'Lancaster' },
        away_team: { name: 'Four Corners' },
        score: { Lancaster: 78, 'Four Corners': 71 },
        points_by_quarter: { Lancaster: [20, 18, 22, 18], 'Four Corners': [19, 17, 18, 17] },
        clock: '0:00',
        quarter: 4,
        is_final: true,
        players: BOX_PLAYERS,
        box_score: boxScore,
        player_of_the_game: {
          playerId: 'p1',
          name: 'Jalen Carter',
          stats: { pts: 22, reb: 5, ast: 4, stl: 1, blk: 0, defPct: '42%' },
        },
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function installCutApis(page) {
  await page.route('**/*', async (route) => {
    const pathname = await routeApiOnly(route);
    if (!pathname) return;
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, ccData());
      return;
    }
    if (pathname.startsWith('/roster/')) {
      await fulfillJson(route, { players: ROSTER, conference: 1, region: 'A', team_chemistry: 15 });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function scrollTop(page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    const main = document.getElementById('gob-main');
    if (main) main.scrollTop = 0;
  });
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await scrollTop(page);
  await page.screenshot({ path: path.join(OUT, name) });
}

function parseRgb(color) {
  const m = String(color || '').match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  return m[1].split(',').map((part) => Number(String(part).trim()));
}

function isGreenish(color) {
  const parts = parseRgb(color);
  if (!parts || parts.length < 3) return false;
  const g = parts[1];
  const r = parts[0];
  const b = parts[2];
  return g > 180 && g > r + 40 && g > b + 40;
}

test.describe('box score + practice squad token guards', () => {
  test('box score browse and focus: W/L plate, no illegal green, square POTG', async ({ page }) => {
    await stubAuth(page);
    await installBoxApis(page);

    const browseQs =
      '?mode=franchise&franchise_id=' + FID + '&team_id=' + TID +
      '&game_id=g-box&home=Lancaster&away=Four%20Corners&my_team=home' +
      '&return_url=' + encodeURIComponent('/schedule.html');

    for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.goto('/box-score.html' + browseQs);
      await page.waitForSelector('#home-player-stats-body tr', { timeout: 30000 });
      await expect(page.locator('html.gob-shell')).toHaveCount(1);
      const wl = await page.evaluate(() => {
        const plate = document.getElementById('user-game-wl-plate');
        const s = plate ? getComputedStyle(plate) : null;
        return {
          text: plate ? (plate.textContent || '').trim() : '',
          hidden: plate ? plate.hidden : true,
          color: s ? s.color : '',
          borderColor: s ? s.borderColor : '',
          bg: s ? s.backgroundColor : '',
        };
      });
      expect(wl.hidden, JSON.stringify(wl)).toBe(false);
      expect(wl.text).toBe('W');
      expect(isGreenish(wl.color)).toBe(false);
      expect(isGreenish(wl.borderColor)).toBe(false);
      expect(isGreenish(wl.bg)).toBe(false);

      const styles = await page.evaluate((greenRgb) => {
        const potg = document.getElementById('potg-portrait');
        const potgStyle = potg ? getComputedStyle(potg) : null;
        const nameCell = document.querySelector('#home-player-stats-body td:first-child');
        const nameColor = nameCell ? getComputedStyle(nameCell).color : '';
        return {
          potgRadius: potgStyle ? potgStyle.borderRadius : '',
          nameColor,
          greenRgb,
        };
      }, GREEN_RGB);
      expect(styles.potgRadius).toBe('0px');
      expect(styles.nameColor).not.toBe(GREEN_RGB);

      await shot(page, 'after-box-score-browse-' + size[2] + '.png');
    }

    const focusQs =
      '?mode=franchise&franchise_id=' + FID + '&team_id=' + TID +
      '&game_id=g-box&home=Lancaster&away=Four%20Corners&my_team=home&from=lineup';

    for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await page.goto('/box-score.html' + focusQs);
      await page.waitForSelector('#home-player-stats-body tr', { timeout: 30000 });
      await expect(page.locator('html.gob-focus')).toHaveCount(1);
      await shot(page, 'after-box-score-focus-' + size[2] + '.png');
    }
  });

  test('practice squad: submit is committed orange when enabled', async ({ page }) => {
    await stubAuth(page);
    await installCutApis(page);

    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/cut-players.html?franchise_id=' + FID + '&team_id=' + TID + '&from=fcc');
    await page.waitForSelector('#cut-players-table .cut-player-checkbox', { timeout: 30000 });
    await shot(page, 'after-cut-wrong-count-1280.png');

    const boxes = page.locator('#cut-players-table .cut-player-checkbox');
    await boxes.nth(0).check();
    await boxes.nth(1).check();
    await expect(page.locator('#submit-btn')).toBeEnabled();
    const btnStyle = await page.evaluate(() => {
      const btn = document.getElementById('submit-btn');
      const s = getComputedStyle(btn);
      return { bg: s.backgroundColor, color: s.color };
    });
    expect(isGreenish(btnStyle.bg)).toBe(false);
    expect(isGreenish(btnStyle.color)).toBe(false);
    await shot(page, 'after-cut-exact-count-1280.png');

    await page.locator('#submit-btn').click();
    await expect(page.locator('#cut-modal-backdrop.is-visible')).toBeVisible();
    await shot(page, 'after-cut-confirm-modal-1280.png');

    await page.setViewportSize({ width: 1920, height: 1080 });
    await shot(page, 'after-cut-confirm-modal-1920.png');
  });
});
