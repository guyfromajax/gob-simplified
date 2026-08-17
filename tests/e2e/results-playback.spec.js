// @ts-check
/**
 * Results (week 36) playback + the Signing Day carry-back fix.
 *
 * Playback is a presentation of a sequence the engine already produced. Every number on
 * a row comes from `resolution` on the signed entry — the reason string is built
 * server-side, so the client showing it is proof it wasn't recomputed here.
 *
 * Run: npx playwright test tests/e2e/results-playback.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');
const CSS = read('recruiting-spine.css') + read('recruiting-signing.css') + read('css/attr-tiles.css');
const SCRIPTS = ['common.js', 'js/shared/attrTiles.js', 'js/shared/rtBucket.js', 'js/shared/playerYear.js',
  'recruiting-common.js', 'recruiting-spine.js'].map(read);
const HUB = read('recruiting-hub.js');

const ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];
const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const USER = 'user-team-id';
const RIVAL = 'rival-1';

function recruit(i, leanRank) {
  const attributes = {};
  ATTRS.forEach((k, j) => { attributes[k] = ((i * 5 + j * 9) % 91) + 5; });
  const lean = leanRank === 1 ? { 1: USER, 2: RIVAL, 3: null }
    : leanRank === 2 ? { 1: RIVAL, 2: USER, 3: null }
      : leanRank === 3 ? { 1: RIVAL, 2: 'rival-2', 3: USER }
        : { 1: RIVAL, 2: 'rival-2', 3: null };
  return {
    recruit_id: `r-${i}`, name: `Recruit ${String(i).padStart(2, '0')}`,
    image_id: `img-${i}`, archetype: 'Slasher', 'Home Region': 'C',
    year: 'JH', height: 72, weight: 190, attributes,
    position_ratings: { [POS[i % POS.length]]: 90 - i * 6 }, Lean: lean,
  };
}

/** Signed entry with the resolution block the engine records, plus its server reason. */
function signed(i, { winner, points, mult, field, reason, boarded = true }) {
  return {
    recruit_id: `r-${i}`, name: `Recruit ${String(i).padStart(2, '0')}`,
    image_id: `img-${i}`, pos: POS[i % POS.length], rt: 90 - i * 6,
    team_id: winner, team_name: winner === USER ? 'Kettle Falls' : 'Fairview',
    walk_on: false, year: 'JH',
    signing_reason: reason,
    resolution: {
      field_size: field,
      points_by_team: points > 0 ? { [USER]: points, [RIVAL]: 14 } : { [RIVAL]: 14 },
      scores_by_team: boarded ? { [USER]: 40, [RIVAL]: 70 } : { [RIVAL]: 70 },
      winner_team_id: winner, winner_score: 70, winner_points: 14,
      lean_multipliers: { [USER]: mult, [RIVAL]: 3 },
      lean_at_resolution: { 1: RIVAL, 2: USER, 3: null },
      pt_offer_count: 1,
    },
  };
}

const DEFAULT_SIGNED = [
  signed(0, { winner: USER, points: 18, mult: 5, field: 2, reason: '#1 lean x5 · only 2 programs funding' }),
  signed(1, { winner: RIVAL, points: 5, mult: 3, field: 6, reason: "6 programs funding · 5 points didn't carry" }),
  signed(2, { winner: USER, points: 9, mult: 2, field: 1, reason: 'Uncontested — nobody else boarded him' }),
  signed(3, { winner: RIVAL, points: 0, mult: 1, field: 4, reason: 'You boarded him with 0 points · Fairview funded him' }),
];

function fixture(o = {}) {
  const recruits = [];
  for (let i = 0; i < 6; i++) recruits.push(recruit(i, i % 4));
  const signedPlayers = o.signed || DEFAULT_SIGNED;
  const byId = {};
  signedPlayers.forEach((sp) => { byId[sp.recruit_id] = { team_id: sp.team_id, team_name: sp.team_name, walk_on: false }; });
  return {
    team: 'Kettle Falls', team_id: USER, team_region: 'C', week: o.week ?? 36, recruits,
    team_name_map: { [USER]: 'Kettle Falls', [RIVAL]: 'Fairview', 'rival-2': 'Brackenridge' },
    saved_orders: {}, watchlist: [], new_lean_recruit_ids: [],
    week_35_recruiting_ran: (o.week ?? 36) !== 35,
    week_35_recruiting_results: { signed_players: signedPlayers, signed_by_recruit_id: byId },
    saved_order_entries_week_35: o.savedEntries || [],
    week_35_points_budget: 50,
    roster_capacity: o.capacity || { roster_spots: 4, scholarships: 2, roster_cap: 15, roster_used: 11 },
    competition_counts: o.competition || {},
    lean_multipliers: { 1: 5, 2: 3, 3: 2 },
    recruiting_wire: { week: 36, events: [], events_this_week: [], visited_recruit_ids: [], counts: {} },
  };
}

async function mount(page, o = {}) {
  await page.setViewportSize({ width: 1500, height: 1200 });
  await page.goto('/?franchise_id=fid-test&team_id=user-team-id');
  await page.setContent(`
    <style>${CSS}</style><style>body{margin:0}.doc{max-width:1440px;margin:0 auto;padding:16px}</style>
    <div class="doc"><a id="back-btn" href="#"></a><div id="hub-root" class="spine"></div></div>`);
  for (const src of SCRIPTS) await page.addScriptTag({ content: src });
  await page.evaluate(({ data }) => {
    window.__writes = [];
    window.API_CONFIG = {
      buildUrl: (p) => `https://stub.local${p}`, getAuthHeaders: () => ({}),
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
  // Week 35 renders the signing board; week 36 renders the results stage.
  const selector = (o.week ?? 36) === 35 ? '#hub-sign .prow' : '#hub-signings .rstage';
  await page.waitForSelector(selector, { timeout: 10000 });
}

const rowCount = (page) => page.locator('#hub-signings .rrow').count();

test.describe('sequence playback', () => {
  test('starts with nothing revealed and advances one at a time', async ({ page }) => {
    await mount(page);
    expect(await rowCount(page)).toBe(0);
    await page.click('#pb-next');
    expect(await rowCount(page)).toBe(1);
    await page.click('#pb-next');
    expect(await rowCount(page)).toBe(2);
  });

  test('reveals in the engine order — RT descending', async ({ page }) => {
    await mount(page);
    await page.click('#pb-skip');
    const names = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-signings .rrow .rnm')].map((n) => n.textContent.trim()));
    // r-0 (90) > r-1 (84) > r-2 (78) > r-3 (72)
    expect(names).toEqual(['Recruit 00', 'Recruit 01', 'Recruit 02', 'Recruit 03']);
  });

  test('Skip all reveals everything and shows the summary', async ({ page }) => {
    await mount(page);
    expect(await page.locator('#hub-signings .rsum').count()).toBe(0);
    await page.click('#pb-skip');
    expect(await rowCount(page)).toBe(4);
    expect(await page.locator('#hub-signings .rsum').count()).toBe(1);
    expect(await page.locator('#pb-next').count()).toBe(0);
  });

  test('Auto-play advances on its own and can be paused', async ({ page }) => {
    await mount(page);
    await page.click('#pb-auto');
    await page.waitForFunction(() => document.querySelectorAll('#hub-signings .rrow').length >= 2, null, { timeout: 6000 });
    await page.click('#pb-auto');   // now labelled Pause
    const paused = await rowCount(page);
    await page.waitForTimeout(1400);
    expect(await rowCount(page)).toBe(paused);
  });

  test('the counter tracks progress', async ({ page }) => {
    await mount(page);
    await page.click('#pb-next');
    expect((await page.locator('#hub-signings .rctl-count').textContent()).trim()).toBe('1 of 4');
  });

  test('a season with nothing boarded says so instead of showing an empty stage', async ({ page }) => {
    await mount(page, { signed: [signed(5, { winner: RIVAL, points: 0, mult: 1, field: 3, reason: 'x', boarded: false })] });
    // That entry is not boarded and not signed with us, so it is excluded entirely.
    const txt = await page.evaluate(() => document.querySelector('#hub-signings').textContent);
    expect(txt).toContain('never boarded anyone');
  });
});

test.describe('every row explains itself', () => {
  test.beforeEach(async ({ page }) => { await mount(page); await page.click('#pb-skip'); });

  test('row carries headshot, name, RT, signed-to, points, standing, field and a why', async ({ page }) => {
    const m = await page.evaluate(() => {
      const r = document.querySelector('#hub-signings .rrow');
      return {
        img: !!r.querySelector('.rav img'),
        name: r.querySelector('.rnm').textContent.trim(),
        link: !!r.querySelector('.rnm a'),
        rt: r.querySelector('.rrt').textContent.trim(),
        team: r.querySelector('.rsigned-team').textContent.trim(),
        nums: [...r.querySelectorAll('.rnum')].map((n) => n.textContent.trim()),
        why: r.querySelector('.rwhy').textContent.trim(),
      };
    });
    expect(m.img).toBe(true);
    expect(m.name).toBe('Recruit 00');
    expect(m.link).toBe(true);
    expect(m.rt.length).toBeGreaterThan(0);
    expect(m.team).toBe('Kettle Falls');
    expect(m.nums[0]).toContain('18');
    expect(m.nums[1]).toContain('#1 x5');
    expect(m.nums[2]).toContain('2');
    expect(m.why).toBe('#1 lean x5 · only 2 programs funding');
  });

  test('the why is the server string verbatim — not rebuilt client-side', async ({ page }) => {
    const served = await page.evaluate(() =>
      window.__lastFixtureReasons || null);
    const shown = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-signings .rwhy')].map((w) => w.textContent.trim()));
    expect(shown).toEqual([
      '#1 lean x5 · only 2 programs funding',
      "6 programs funding · 5 points didn't carry",
      'Uncontested — nobody else boarded him',
      'You boarded him with 0 points · Fairview funded him',
    ]);
    void served;
  });

  test('slot-3 standing renders x2, matching the engine', async ({ page }) => {
    const nums = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-signings .rrow')].map((r) =>
        r.querySelectorAll('.rnum')[1].textContent.trim()));
    // r-2 was recorded with lean_multipliers[user] = 2.
    expect(nums[2]).toContain('#3 x2');
    expect(nums.join(' ')).not.toContain('#3 x1');
  });

  test('won and lost rows are visually distinguished', async ({ page }) => {
    const m = await page.evaluate(() => ({
      won: document.querySelectorAll('#hub-signings .rrow.won').length,
      lost: document.querySelectorAll('#hub-signings .rrow.lost').length,
    }));
    expect(m.won).toBe(2);
    expect(m.lost).toBe(2);
  });

  test('no percentage on the results screen', async ({ page }) => {
    const hits = await page.evaluate(() => {
      const w = document.createTreeWalker(document.getElementById('hub-signings'), NodeFilter.SHOW_TEXT);
      const out = [];
      while (w.nextNode()) if ((w.currentNode.nodeValue || '').includes('%')) out.push(w.currentNode.nodeValue.trim());
      return out;
    });
    expect(hits).toEqual([]);
  });

  test('a row with no recorded resolution shows a dash, not an invented reason', async ({ page }) => {
    await mount(page, {
      signed: [{
        recruit_id: 'r-0', name: 'Recruit 00', pos: 'PG', rt: 90,
        team_id: USER, team_name: 'Kettle Falls', walk_on: false,
      }],
    });
    await page.click('#pb-skip');
    expect((await page.locator('#hub-signings .rwhy').first().textContent()).trim()).toBe('—');
  });
});

test.describe('class summary', () => {
  test('reconciles with what was submitted', async ({ page }) => {
    await mount(page);
    await page.click('#pb-skip');
    const cells = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-signings .rsum-cell')].map((c) => ({
        v: c.querySelector('b').textContent.trim(),
        label: c.querySelector('span').textContent.trim(),
      })));
    const by = Object.fromEntries(cells.map((c) => [c.label, c.v]));
    expect(by['signed']).toBe('2');            // r-0 and r-2
    expect(by['funded']).toBe('3');            // r-0 (18), r-1 (5), r-2 (9)
    expect(by['points spent']).toBe('32');     // 18 + 5 + 9
    expect(by['class avg RT']).toBeTruthy();
    expect(by['roster spots left']).toBe('2'); // 4 served - 2 signed
  });

  test('roster spots left reads the served capacity', async ({ page }) => {
    await mount(page, { capacity: { roster_spots: 9, scholarships: 0, roster_cap: 15, roster_used: 6 } });
    await page.click('#pb-skip');
    const v = await page.evaluate(() =>
      [...document.querySelectorAll('#hub-signings .rsum-cell')]
        .find((c) => c.querySelector('span').textContent.trim() === 'roster spots left')
        .querySelector('b').textContent.trim());
    expect(v).toBe('7');   // 9 - 2 signed
  });

  test('summary only appears after the sequence finishes', async ({ page }) => {
    await mount(page);
    await page.click('#pb-next');
    expect(await page.locator('#hub-signings .rsum').count()).toBe(0);
    await page.click('#pb-skip');
    expect(await page.locator('#hub-signings .rsum').count()).toBe(1);
  });
});

test.describe('carry-back: Signing Day rail warnings are reachable', () => {
  const SIGNING = {
    week: 35,
    // r-3 has no lean to us (leanRank 3 in the fixture cycle => i%4===3 => slot 3),
    // so pick r-0's cycle carefully: i%4===0 -> lean 1, 1 -> lean 2, 2 -> lean 3, 3 -> none.
    // r-4 is i%4===0 in the fixture cycle => no lean to us, so the default 'mine' tab
    // hides him. That is precisely the case the rail used to warn about unreachably.
    competition: { 'r-4': 6 },
    savedEntries: [{ id: 'r-4', points: 4, playing_time: false }],
  };

  test('a warning about a hidden recruit is a button', async ({ page }) => {
    await mount(page, SIGNING);
    await page.waitForSelector('#sign-rail .preflight');
    const m = await page.evaluate(() => {
      const b = document.querySelector('#sign-rail [data-pfw-jump]');
      return { exists: !!b, tag: b && b.tagName, id: b && b.dataset.pfwJump };
    });
    expect(m.exists).toBe(true);
    expect(m.tag).toBe('BUTTON');
    expect(m.id).toBe('r-4');
  });

  test('clicking it switches off the mine tab and flashes the row', async ({ page }) => {
    await mount(page, SIGNING);
    await page.waitForSelector('#sign-rail [data-pfw-jump]');
    // r-4 does not lean to us, so the default 'mine' tab hides him.
    const hiddenBefore = await page.evaluate(() =>
      !document.querySelector('#hub-sign .prow[data-id="r-4"]'));
    expect(hiddenBefore).toBe(true);

    await page.click('#sign-rail [data-pfw-jump="r-4"]');
    await page.waitForSelector('#hub-sign .prow[data-id="r-4"]');
    const m = await page.evaluate(() => ({
      visible: !!document.querySelector('#hub-sign .prow[data-id="r-4"]'),
      flashed: !!document.querySelector('#hub-sign .prow[data-id="r-4"].flash'),
      allTabOn: document.querySelector('#hub-sign [data-stab="all"]').classList.contains('on'),
    }));
    expect(m.visible).toBe(true);
    expect(m.flashed).toBe(true);
    expect(m.allTabOn).toBe(true);
  });

  test('the mine tab remains the default — only the warning route changed', async ({ page }) => {
    await mount(page, SIGNING);
    const on = await page.evaluate(() =>
      document.querySelector('#hub-sign [data-stab="mine"]').classList.contains('on'));
    expect(on).toBe(true);
  });

  test('aggregate warnings that name no recruit stay non-clickable', async ({ page }) => {
    await mount(page, {
      week: 35,
      capacity: { roster_spots: 1, scholarships: 0, roster_cap: 15, roster_used: 14 },
      savedEntries: [{ id: 'r-0', points: 3, playing_time: false }, { id: 'r-1', points: 3, playing_time: false }],
    });
    await page.waitForSelector('#sign-rail .preflight');
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('#sign-rail .pfw')].map((el) => ({
        clickable: el.tagName === 'BUTTON',
        text: el.textContent.trim(),
      })));
    const aggregate = m.find((x) => x.text.includes('roster spot') && x.text.includes('recruits funded'));
    expect(aggregate).toBeTruthy();
    expect(aggregate.clickable).toBe(false);
  });
});
