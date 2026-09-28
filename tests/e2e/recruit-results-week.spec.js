// @ts-check
/** Week 36 signing results — browse-template layout. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');
const OUT = path.join(__dirname, '../../reports/recruit-results-week');

const CSS = read('css/gob-tokens.css') + read('css/gob-tables.css') + read('recruiting-spine.css')
  + read('recruiting-signing.css') + read('recruiting-results-hub.css') + read('css/attr-tiles.css');
const SCRIPTS = [
  'js/shared/franchiseContext.js',
  'common.js',
  'js/utils/attributeDisplay.js',
  'js/shared/attrTiles.js', 'js/shared/rtBucket.js',
  'js/shared/playerYear.js',
  'recruiting-common.js',
  'recruiting-spine.js',
].map(read);
const HUB = read('recruiting-hub.js');

const USER = 'user-team-id';
const regionOf = (c) => String.fromCharCode(65 + Math.floor((Number(c) - 1) / 2));

function withRegions(conferences, userTeamId) {
  const byTeam = conferences.by_team_id || {};
  const regionByTeam = {};
  Object.keys(byTeam).forEach((tid) => { regionByTeam[tid] = regionOf(byTeam[tid]); });
  const userRegion = regionByTeam[String(userTeamId)] || null;
  return Object.assign({}, conferences, {
    user_region: userRegion,
    region_by_team_id: regionByTeam,
    region_team_ids: Object.keys(regionByTeam).filter((tid) => regionByTeam[tid] === userRegion).sort(),
  });
}

/** Six conferences with signings for screenshot + order checks. */
function fixtureLeague() {
  const byTeam = { [USER]: 9 };
  for (let i = 1; i <= 7; i += 1) byTeam[`c9-${i}`] = 9;
  for (let i = 1; i <= 4; i += 1) byTeam[`c10-${i}`] = 10;
  for (let c of [1, 2, 3, 4, 5, 6]) {
    byTeam[`c${c}-a`] = c;
    byTeam[`c${c}-b`] = c;
  }
  const teamNames = { [USER]: 'South Lancaster' };
  Object.keys(byTeam).forEach((tid) => {
    if (!teamNames[tid]) teamNames[tid] = 'Team ' + tid;
  });
  const signed = [];
  const YEARS = ['JH', 'Freshman', 'Sophomore', 'Junior'];
  let rt = 92;
  for (let i = 0; i < 5; i += 1) {
    signed.push({
      player_id: `p-u${i}`, image_id: `img-u${i}`, recruit_id: `r-u${i}`,
      name: `Lancaster ${i}`, pos: 'SF', rt: rt--, potential_rt_ratcheted: rt + 2,
      year: YEARS[i % 4], team_id: USER, team_name: 'South Lancaster',
    });
  }
  Object.keys(byTeam).forEach((tid, idx) => {
    if (tid === USER) return;
    signed.push({
      player_id: `p-${idx}`, recruit_id: `r-${idx}`, name: `Sign ${idx}`, pos: 'PG',
      rt: 70 + (idx % 20), potential_rt_ratcheted: 80 + (idx % 15), year: 'Junior',
      team_id: tid, team_name: teamNames[tid],
    });
  });
  const conferences = withRegions({
    user_conference: 9,
    sister_conference: 10,
    order: [9, 10, 1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16],
    by_team_id: byTeam,
  }, USER);
  return { signed, conferences, teamNames };
}

function fixturePayload(opts) {
  const { signed, conferences, teamNames } = fixtureLeague();
  return {
    team: 'South Lancaster', team_id: USER, team_region: 'A', week: 36, season: 3,
    recruits: [],
    team_name_map: teamNames,
    saved_orders: {}, watchlist: [], saved_order_entries_week_35: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: { signed_players: signed },
    week_35_recruiting_ran: true,
    week_35_reveal_seen: true,
    conferences,
  };
}

async function mountResults(page) {
  await page.route('**/', (route) => (route.request().resourceType() === 'document'
    ? route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>o</title>' })
    : route.continue()));
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.setContent(`
    <style>${CSS}</style>
    <style>body{margin:0;background:var(--bg,#0b0d14)}.doc{max-width:1180px;margin:0 auto;padding:20px}</style>
    <div class="doc"><div id="hub-root" class="spine"></div></div>
  `);
  for (const src of SCRIPTS) await page.addScriptTag({ content: src });
  await page.evaluate((data) => {
    window.__seen = [];
    window.API_CONFIG = {
      buildUrl: (p) => `https://stub.local${p}`,
      getAuthHeaders: () => ({}),
      getRecruitImageUrl: (id) => `https://stub.local/img/${id}.png`,
    };
    window.__fixture = data;
    const realFetchJSON = window.RecruitingCommon.fetchJSON;
    window.RecruitingCommon.fetchJSON = function (url, options) {
      window.__seen.push(String(url));
      if (String(url).includes('/franchise/recruiting-data')) {
        return Promise.resolve(window.__fixture);
      }
      if (String(url).includes('week-36-results-seen')) {
        return Promise.resolve({});
      }
      return realFetchJSON.call(this, url, options);
    };
  }, fixturePayload());
  await page.addScriptTag({ content: HUB });
  await page.waitForSelector('.gob-rec-results', { timeout: 10000 });
}

test.describe('week 36 signing results browse layout', () => {
  test('your class first, conference order, navy rows, seen PATCH once', async ({ page }) => {
    await mountResults(page);
    const layout = await page.evaluate(() => {
      const root = document.querySelector('#hub-signings .gob-rec-results');
      const kids = [...root.children].map((el) => el.className);
      const confTitles = [...document.querySelectorAll('#hub-signings .gob-rec-conf h2')].map((h) => h.textContent.trim());
      const navy = document.querySelectorAll('#hub-signings .gob-rec-league tr.me').length;
      return { kids, confTitles, navy, seen: (window.__seen || []).filter((u) => u.includes('week-36-results-seen')).length };
    });
    expect(layout.kids[0]).toContain('gob-rec-lead');
    expect(layout.kids.some((c) => c.includes('gob-rec-your-class'))).toBe(true);
    const classIdx = layout.kids.findIndex((c) => c.includes('gob-rec-your-class'));
    const gridIdx = layout.kids.findIndex((c) => c.includes('gob-rec-conf-grid'));
    expect(classIdx).toBeGreaterThan(-1);
    expect(gridIdx).toBeGreaterThan(classIdx);
    expect(layout.confTitles[0]).toBe('Conference E9');
    expect(layout.confTitles[1]).toBe('Conference E10');
    expect(layout.confTitles[2]).toBe('Conference A1');
    expect(layout.navy).toBeGreaterThan(0);
    expect(layout.seen).toBe(1);
    await expect(page.locator('#hub-signings .gob-rec-player-link').first()).toHaveAttribute('href', /player-view/);
  });

  test('screenshots at 1280 and 1920', async ({ page }) => {
    fs.mkdirSync(OUT, { recursive: true });
    for (const size of [[1280, 720, '1280'], [1920, 1080, '1920']]) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await mountResults(page);
      await page.screenshot({ path: path.join(OUT, `results-w36-${size[2]}.png`) });
    }
  });
});
