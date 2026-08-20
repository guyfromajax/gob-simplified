// @ts-check
/**
 * The seeded-board Sammy note on the Recruiting Hub.
 *
 * "Hey Coach, your Invite Board is pre-populated with your current leans, but you can
 * add other players too." — shown once a season, on the Hub rather than the FCC,
 * because it explains something the player is looking at.
 *
 * Gated on the seed HAVING HAPPENED, not merely on the week: a player with no leans and
 * no watchlist seeds nothing, and the note would then describe an empty board.
 *
 * Real recruiting-hub.js and the real shared sammyModal / teamCoachAsset modules, with
 * only the network stubbed.
 *
 * Run: npx playwright test tests/e2e/invite-seed-modal.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');
const CSS = read('recruiting-spine.css') + read('css/attr-tiles.css');
const SCRIPTS = ['common.js', 'js/shared/attrTiles.js', 'js/shared/rtBucket.js', 'js/shared/playerYear.js',
  'recruiting-common.js', 'recruiting-spine.js'].map(read);
const HUB = read('recruiting-hub.js');

const ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];
const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const USER = 'user-team-id';

function fixture(o = {}) {
  const recruits = [];
  for (let i = 0; i < 12; i++) {
    const attributes = {};
    ATTRS.forEach((k, j) => { attributes[k] = ((i * 7 + j * 11) % 91) + 5; });
    const leansToUser = !o.noLeans && i % 3 === 0;
    recruits.push({
      recruit_id: `r-${i}`, name: `Recruit ${String(i).padStart(2, '0')}`,
      image_id: `img-${i}`, archetype: 'Slasher', 'Home Region': 'C',
      year: 'JH', height: 72, weight: 190, attributes,
      position_ratings: { [POS[i % POS.length]]: 80 - i },
      Lean: leansToUser ? { 1: USER, 2: 'rival-1', 3: null } : { 1: 'rival-1', 2: null, 3: null },
    });
  }
  const savedOrders = {};
  (o.board || []).forEach((id, i) => { savedOrders[String(i + 1)] = id; });
  return {
    team: o.team || 'Kettle Falls', team_id: USER, team_region: 'C',
    week: o.week ?? 20, recruits,
    team_name_map: { [USER]: o.team || 'Kettle Falls', 'rival-1': 'Fairview' },
    saved_orders: savedOrders, watchlist: o.watchlist || [], new_lean_recruit_ids: [],
    week_35_recruiting_results: {}, week_35_recruiting_ran: false,
    invite_seed_modal_seen: !!o.seen,
    visit_history: [20, 21, 22, 23, 24, 25, 26].map((w) => ({ week: w, recruit_id: null, name: null, lean: null })),
    recruiting_wire: {
      week: o.week ?? 20, seen_week: 0, unseen_count: 0, counts: {},
      events: [], events_this_week: [], visited_recruit_ids: [],
      board_saved_week: 0, has_saved_board: !!(o.board || []).length,
    },
  };
}

async function mount(page, o = {}) {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.setContent(`
    <style>${CSS}</style><style>body{margin:0}.doc{max-width:1360px;margin:0 auto;padding:20px}</style>
    <div class="doc"><a id="back-btn" href="#"></a><div id="hub-root" class="spine"></div></div>`);
  for (const src of SCRIPTS) await page.addScriptTag({ content: src });
  await page.evaluate(({ data }) => {
    window.__writes = [];
    window.API_CONFIG = {
      buildUrl: (p) => `https://stub.local${p}`,
      buildStaticPath: (p) => p,          // the real modules load from the dev server
      getAuthHeaders: () => ({}),
      getRecruitImageUrl: (id) => `https://stub.local/${id}.png`,
      ensureRecruitImage: () => Promise.resolve({ status: 'skip' }),
    };
    window.RecruitingCommon.fetchJSON = function (url, options) {
      const u = String(url);
      if (u.includes('/franchise/recruiting-data')) return Promise.resolve(data);
      window.__writes.push({ url: u, body: (options || {}).body });
      return Promise.resolve({ status: 'success' });
    };
  }, { data: fixture(o) });
  await page.addScriptTag({ content: HUB });
  await page.waitForSelector('#hub-board .bpanel', { timeout: 10000 });
}

const modal = (page) => page.locator('.sammy-modal');

test('it explains the seeded board, in Sammy\'s voice', async ({ page }) => {
  await mount(page, { week: 20 });
  await expect(modal(page)).toBeVisible({ timeout: 5000 });
  const txt = await page.evaluate(() =>
    document.querySelector('.sammy-modal-body').textContent.trim());
  expect(txt).toBe('Hey Coach, your Invite Board is pre-populated with your current leans, '
    + 'but you can add other players too.');
  expect(await page.evaluate(() =>
    document.querySelector('.sammy-modal-actions button').textContent.trim())).toBe('Got It');
});

test('a conference-1 team gets its own Sammy; everyone else gets the white one', async ({ page }) => {
  await mount(page, { week: 20, team: 'South Lancaster' });
  await expect(modal(page)).toBeVisible({ timeout: 5000 });
  expect(await page.evaluate(() =>
    document.querySelector('.sammy-modal-image').getAttribute('src'))).toContain('/coaches/SL/');

  await mount(page, { week: 20, team: 'Kettle Falls' });
  await expect(modal(page)).toBeVisible({ timeout: 5000 });
  expect(await page.evaluate(() =>
    document.querySelector('.sammy-modal-image').getAttribute('src'))).toBe('/images/sammy_tutorial.png');
});

test('showing it stamps it seen, so a refresh does not replay it', async ({ page }) => {
  await mount(page, { week: 20 });
  await expect(modal(page)).toBeVisible({ timeout: 5000 });
  await page.waitForFunction(() =>
    window.__writes.some((w) => String(w.url).includes('invite-seed-modal-seen')));

  // Second landing, with the server reporting it stamped.
  await mount(page, { week: 20, seen: true });
  await page.waitForTimeout(600);
  await expect(modal(page)).toHaveCount(0);
});

test('no seed, no note — it must not describe an empty board', async ({ page }) => {
  await mount(page, { week: 20, noLeans: true, watchlist: [] });
  await page.waitForTimeout(600);
  await expect(modal(page)).toHaveCount(0);
  // Control: the same mount WITH something to seed from does show it.
  await mount(page, { week: 20 });
  await expect(modal(page)).toBeVisible({ timeout: 5000 });
});

test('a saved board is not a seeded one, so it gets no note', async ({ page }) => {
  await mount(page, { week: 20, board: ['r-5', 'r-2'] });
  await page.waitForTimeout(600);
  await expect(modal(page)).toHaveCount(0);
});

test('later invite weeks carry the board forward and stay quiet', async ({ page }) => {
  await mount(page, { week: 22, board: ['r-5', 'r-2'] });
  await page.waitForTimeout(600);
  await expect(modal(page)).toHaveCount(0);
});
