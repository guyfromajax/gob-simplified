// @ts-check
/**
 * Shared .mm template for every MILESTONE-tier kind in moments_for_this_visit.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 90000 });

const FID = 'f-e2e-mm';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const SHOTS = path.join(__dirname, '../../reports/milestone-modal');

function digest() {
  return {
    state: 'regular',
    what_moved: {
      national_rank: { now: 18, prev: 22, delta: 4 },
      conference_standing: { now: 3, prev: 5, delta: 2 },
      record: { wins: 16, losses: 5 },
      streak: 'W4',
      attribute_changes: [],
    },
    team_snapshot: { state: 'ready', chemistry: { value: 18, max: 25 }, attitude: { player_count: 12, buckets: [] }, moved_most: [] },
    result: {
      week: 21, user_won: true, site: 'home', home_score: 71, away_score: 64,
      home_team_name: 'Lancaster', away_team_name: 'Crickstown',
      opponent_team_name: 'Crickstown', opponent_rank: 9,
      leader_role: 'potg', leader: { name: 'Jalen Carter', stats: { pts: 24 } },
      box_score: { path: '/box-score.html', params: {} },
    },
    next_game: { week: 22, site: 'away', opponent: 'Morristown', rank: 21, record: { wins: 11, losses: 8 }, conference: 2 },
    conference_standings: { conference: 2, region: 'A', rows: [] },
    todos: [],
    recruiting_wire: { status: '', events: [], pending_count: 0, urgent: false, unseen_count: 0 },
    signing_day: null,
    season_preview: null,
    weekly_card_items: [],
  };
}

function cc(flags) {
  return Object.assign({
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 22,
    season: 2,
    current_season: 2,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 22, counts: {} },
    office_digest: digest(),
    pending_championship_moments: [],
    moments: [],
    moments_for_this_visit: [],
    weekly_card_items: [],
    team_name_map: { [TID]: 'Lancaster', [OPP]: 'Kingsport' },
  }, flags || {});
}

function item(kind, extra) {
  const meta = {
    signed_class: {
      priority: 40, payload_ref: 'signed_class', seen_key: 'recruiting_results_modal_seen_season',
      duration: 'long', title: 'Signing class', line: '2 recruits signed with your program.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    walk_on_welcome: {
      priority: 50, payload_ref: 'walk_on_welcome_modal', seen_key: 'walk_on_welcome_modal_seen_season',
      duration: 'long', title: 'Walk-on welcome', line: '1 walk-on joined the roster.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    bracket_reveal: {
      priority: 30, payload_ref: 'bracket_reveal_modal', seen_key: 'bracket_reveal',
      duration: 'long', title: 'Bracket reveal', line: 'The bracket is set.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    region_bye: {
      priority: 60, payload_ref: 'region_bye_modal_eligible', seen_key: 'region_bye_modal_seen_season',
      duration: 'short', title: 'Region tournament bye', line: 'Bye.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    conference_rs_region: {
      priority: 65, payload_ref: 'conference_rs_region_modal', seen_key: 'conference_rs_region_modal_seen_season',
      duration: 'short', title: 'Region tournament qualified', line: 'Qualified.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    first_archetype: {
      priority: 70, payload_ref: 'first_archetype', seen_key: 'archetype_reveal_seen',
      duration: 'short', title: 'Your first archetype', line: 'How you win, written on the staff.',
      style: 'gold', sting: 'STING_MILESTONE',
    },
    elimination: {
      priority: 20, payload_ref: 'elimination', seen_key: 'elimination_seen_season',
      duration: 'short', title: 'Season over',
      line: 'Your season ended in the Region Tourney Championship.',
      style: 'quiet', sting: null,
    },
  };
  return Object.assign({ id: kind, kind: kind, tier: 'MILESTONE' }, meta[kind], extra || {});
}

function signedClassPayload() {
  return {
    eligible: true, count: 2,
    recruits: [
      { name: 'Dee Prospect', position: 'PG', home_region: 'B', rt_now: 71, rt_potential: 84 },
      { name: 'Marcus Vane', position: 'C', rt_now: 64 },
    ],
  };
}

function walkOnPayload() {
  return {
    eligible: true, season: 2, count: 1,
    walk_ons: [{ name: 'Ellis Clemons', pos: 'PF', rt: 72, potential_rt: 88 }],
  };
}

function bracketPayload() {
  return {
    eligible: true, tier: 'conference',
    eyebrow: 'Conference Tournament · Weeks 27–29',
    layout: 'full', reveal_key: 'conference:2', display_week: 27,
    seeds: { [TID]: 2, [OPP]: 7 },
    bracket: {
      round1: [{ home_team: TID, away_team: OPP }],
      final: [{ home_team: TID, away_team: '' }],
    },
  };
}

function visitKind(kind, extras) {
  const moments = [item(kind)];
  const flags = {
    moments,
    moments_for_this_visit: moments,
  };
  if (kind === 'signed_class') flags.signed_class = signedClassPayload();
  if (kind === 'walk_on_welcome') flags.walk_on_welcome_modal = walkOnPayload();
  if (kind === 'bracket_reveal') flags.bracket_reveal_modal = bracketPayload();
  if (kind === 'region_bye') flags.region_bye_modal_eligible = true;
  if (kind === 'conference_rs_region') flags.conference_rs_region_modal = { eligible: true, lost_round: 'round1' };
  if (kind === 'first_archetype') flags.first_archetype = { eligible: true, archetype: 'pure_offense' };
  if (kind === 'elimination') {
    flags.elimination = {
      eligible: true, season: 3, tier: 'region', round_key: 'final',
      round_name: 'Region Tourney Championship',
      opponent_team_id: OPP, opponent_team_name: 'Kingsport',
      score: { user: 58, opponent: 66 }, game_id: 'g-region',
      record: { wins: 24, losses: 9 },
      conference_place: 2, national_rank: 11,
    };
  }
  return cc(Object.assign(flags, extras || {}));
}

function visitSignedThenWalk() {
  const moments = [item('signed_class'), item('walk_on_welcome')];
  return cc({
    signed_class: signedClassPayload(),
    walk_on_welcome_modal: walkOnPayload(),
    moments,
    moments_for_this_visit: moments,
  });
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page, data, seen) {
  await page.unrouteAll({ behavior: 'ignoreErrors' }).catch(function () {});
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/')
      || pathname.startsWith('/recruit/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
    if (request.method() === 'PATCH' && seen) {
      seen.push({ path: pathname, method: request.method() });
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, {
        user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com',
        lead_archetype: 'pure_offense', archetype_reveal_seen: false,
      });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, data);
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openOffice(page, data, seen) {
  await stubAuth(page);
  await installApi(page, data, seen);
  await page.addInitScript(() => { window.__gobMilestoneSfx = []; });
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    const root = document.getElementById('office-root');
    return (!overlay || getComputedStyle(overlay).display === 'none')
      && root && root.getAttribute('aria-busy') === 'false';
  });
}

async function waitOpen(page, kind) {
  const modal = page.locator('.mm-scrim.is-open');
  await expect(modal).toBeVisible({ timeout: 15000 });
  if (kind) await expect(modal).toHaveAttribute('data-kind', kind);
  return modal;
}

function rgbOf(hex) {
  const n = hex.replace('#', '');
  const r = parseInt(n.slice(0, 2), 16);
  const g = parseInt(n.slice(2, 4), 16);
  const b = parseInt(n.slice(4, 6), 16);
  return 'rgb(' + r + ', ' + g + ', ' + b + ')';
}

test.describe('milestone modal variants', () => {
  test.beforeAll(() => {
    fs.mkdirSync(SHOTS, { recursive: true });
  });

  test('signed_class renders the calm recap as 1 of 2', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitSignedThenWalk());
    const modal = await waitOpen(page, 'signed_class');
    await expect(modal.locator('.mm-eye')).toContainText('Signing class');
    await expect(modal.locator('.mq i')).toHaveCount(2);
    await expect(modal.locator('.mq i.on')).toHaveCount(1);
    await expect(modal.getByText('Dee Prospect')).toBeVisible();
    await expect(modal.getByText('Marcus Vane')).toBeVisible();
    await expect(modal.getByText('PG · B')).toBeVisible();
    await expect(modal.getByText('2 signed.')).toBeVisible();
    await expect(modal.locator('.mm-up')).toContainText('Up next');
    await expect(modal.locator('.mm-go')).toHaveText('Next');
    await expect(modal.locator('.mm.is-gold')).toHaveCount(1);
    await expect(page.locator('[class*="confetti"]')).toHaveCount(0);
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(SHOTS, 'signed-class.png') });
  });

  test('signed_class at 1920', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await openOffice(page, visitSignedThenWalk());
    await waitOpen(page, 'signed_class');
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(SHOTS, 'signed-class-1920.png') });
  });

  test('bracket_reveal uses seed and path, navy on yours, no confetti', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitKind('bracket_reveal'));
    const modal = await waitOpen(page, 'bracket_reveal');
    await expect(modal.locator('.seed')).toContainText('2');
    await expect(modal.getByText('Lancaster', { exact: true })).toHaveCount(1);
    await expect(modal.getByText('Kingsport', { exact: true })).toHaveCount(1);
    await expect(modal.locator('.mm-go')).toHaveText('Done');
    await expect(page.locator('[class*="confetti"]')).toHaveCount(0);
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(SHOTS, 'bracket-reveal.png') });
  });

  test('walk_on_welcome renders the walk-ons', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitKind('walk_on_welcome'));
    const modal = await waitOpen(page, 'walk_on_welcome');
    await expect(modal.getByText('Ellis Clemons')).toBeVisible();
    await expect(modal.getByText('1 walk-on.')).toBeVisible();
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(SHOTS, 'walk-ons.png') });
  });

  test('first_archetype uses the manifest name and copy', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitKind('first_archetype'));
    const modal = await waitOpen(page, 'first_archetype');
    await expect(modal.locator('#mm-ttl')).toContainText('Pure Offense');
    await expect(modal.locator('.arch')).toBeVisible();
    await expect(modal.locator('.mm-link')).toHaveAttribute('href', '/coaching-archetypes.html');
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(SHOTS, 'first-archetype.png') });
  });

  test('region_bye uses the existing copy', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitKind('region_bye'));
    const modal = await waitOpen(page, 'region_bye');
    await expect(modal.getByText(/earned a bye in the Region Tournament/)).toBeVisible();
    await page.waitForTimeout(450);
    await page.screenshot({ path: path.join(SHOTS, 'region-bye.png') });
  });

  test('elimination is quiet: no gold, no rise, no sound, omitted seeds', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openOffice(page, visitKind('elimination'));
    const modal = await waitOpen(page, 'elimination');
    await expect(modal.locator('.mm.is-quiet')).toHaveCount(1);
    await expect(modal.locator('.mm-dia')).toHaveCount(0);
    await expect(modal.locator('.mm-med')).toHaveCount(0);
    await expect(modal.getByText('58–66')).toBeVisible();
    await expect(modal.locator('.fin')).toContainText('Region Tourney Championship');
    await expect(modal.getByText('24–9')).toBeVisible();
    await expect(modal.getByText(/Seed/)).toHaveCount(0);
    await expect(modal.locator('.mm-go')).toHaveText('Done');
    await page.waitForTimeout(350);
    const sfx = await page.evaluate(() => window.__gobMilestoneSfx || []);
    expect(sfx).toEqual([]);
    await page.screenshot({ path: path.join(SHOTS, 'elimination.png') });
  });
});

test('gold accents only on the rule, diamond and medallion', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitKind('region_bye'));
  await waitOpen(page, 'region_bye');
  await page.waitForTimeout(450);
  const colors = await page.evaluate(() => {
    const goldProbe = document.createElement('span');
    goldProbe.style.color = 'var(--reward-gold)';
    document.body.appendChild(goldProbe);
    const gold = getComputedStyle(goldProbe).color;
    goldProbe.remove();
    const mm = document.querySelector('.mm.is-gold');
    const rule = mm ? getComputedStyle(mm, '::before').backgroundColor : '';
    const dia = document.querySelector('.mm-dia');
    const med = document.querySelector('.mm-med');
    const btn = document.querySelector('.mm-go');
    const dek = document.querySelector('.mm-dek');
    function rgb(el, prop) {
      return el ? getComputedStyle(el)[prop] : '';
    }
    return {
      gold,
      rule,
      dia: rgb(dia, 'backgroundColor'),
      medBorder: med ? getComputedStyle(med).borderTopColor : '',
      btnBg: rgb(btn, 'backgroundColor'),
      btnColor: rgb(btn, 'color'),
      dekColor: rgb(dek, 'color'),
    };
  });
  expect(colors.rule).toBe(colors.gold);
  expect(colors.dia).toBe(colors.gold);
  expect(colors.medBorder).toBe(colors.gold);
  expect(colors.btnBg).not.toBe(colors.gold);
  expect(colors.btnColor).not.toBe(colors.gold);
  expect(colors.dekColor).not.toBe(colors.gold);
});

test('elimination computed styles carry no reward gold', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitKind('elimination'));
  await waitOpen(page, 'elimination');
  const info = await page.evaluate(() => {
    const goldProbe = document.createElement('span');
    goldProbe.style.color = 'var(--reward-gold)';
    document.body.appendChild(goldProbe);
    const gold = getComputedStyle(goldProbe).color;
    goldProbe.remove();
    const mm = document.querySelector('.mm.is-quiet');
    const before = mm ? getComputedStyle(mm, '::before') : null;
    return {
      gold,
      beforeContent: before ? before.content : '',
      beforeBg: before ? before.backgroundColor : '',
      hasDia: !!document.querySelector('.mm-dia'),
      hasMed: !!document.querySelector('.mm-med'),
    };
  });
  expect(info.hasDia).toBe(false);
  expect(info.hasMed).toBe(false);
  expect(info.beforeBg).not.toBe(info.gold);
});

test('Next steps, Done closes, Esc leaves the rest for the next visit', async ({ page }) => {
  const seen = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitSignedThenWalk(), seen);
  await waitOpen(page, 'signed_class');
  await page.locator('.mm-go').click();
  await waitOpen(page, 'walk_on_welcome');
  await expect(page.locator('.mm-go')).toHaveText('Done');
  await page.locator('.mm-go').click();
  await expect(page.locator('.mm-scrim.is-open')).toHaveCount(0);
  const shown = seen.filter((s) => s.path.indexOf('seen') !== -1);
  expect(shown.some((s) => s.path.indexOf('recruiting-results-modal-seen') !== -1)).toBe(true);
  expect(shown.some((s) => s.path.indexOf('walk-on-welcome-modal-seen') !== -1)).toBe(true);

  const seen2 = [];
  await openOffice(page, visitSignedThenWalk(), seen2);
  await waitOpen(page, 'signed_class');
  await page.keyboard.press('Escape');
  await expect(page.locator('.mm-scrim.is-open')).toHaveCount(0);
  const escSeen = seen2.filter((s) => s.path.indexOf('seen') !== -1);
  expect(escSeen.some((s) => s.path.indexOf('recruiting-results-modal-seen') !== -1)).toBe(true);
  expect(escSeen.some((s) => s.path.indexOf('walk-on-welcome-modal-seen') !== -1)).toBe(false);
});

test('× closes the current moment and does not play the rest', async ({ page }) => {
  const seen = [];
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitSignedThenWalk(), seen);
  await waitOpen(page, 'signed_class');
  await page.locator('.mm-x').click();
  await expect(page.locator('.mm-scrim.is-open')).toHaveCount(0);
  expect(seen.some((s) => s.path.indexOf('walk-on-welcome-modal-seen') !== -1)).toBe(false);
});

test('STING_MILESTONE is requested once per gold moment and never for elimination', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitKind('region_bye'));
  await waitOpen(page, 'region_bye');
  await page.waitForTimeout(350);
  const gold = await page.evaluate(() => window.__gobMilestoneSfx || []);
  expect(gold.filter((n) => n === 'STING_MILESTONE')).toHaveLength(1);

  await openOffice(page, visitKind('elimination'));
  await waitOpen(page, 'elimination');
  await page.waitForTimeout(350);
  const quiet = await page.evaluate(() => window.__gobMilestoneSfx || []);
  expect(quiet.filter((n) => n === 'STING_MILESTONE')).toHaveLength(0);
});

test('focus is trapped and returns to the page on close', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitKind('region_bye'));
  await waitOpen(page, 'region_bye');
  await expect(page.locator('.mm-go')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('.mm-x')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.locator('.mm-go')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('.mm-scrim.is-open')).toHaveCount(0);
  const back = await page.evaluate(() => {
    const el = document.activeElement;
    return !!(el && !el.closest('.mm-scrim'));
  });
  expect(back).toBe(true);
});

test('reduced motion lands on the final state and still plays the sting', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitKind('region_bye'));
  await waitOpen(page, 'region_bye');
  const motion = await page.evaluate(() => {
    const mm = document.querySelector('.mm.is-gold');
    const scrim = document.querySelector('.mm-scrim.is-open');
    const before = mm ? getComputedStyle(mm, '::before') : null;
    return {
      open: !!(scrim && scrim.classList.contains('is-open')),
      opacity: mm ? getComputedStyle(mm).opacity : '',
      transform: mm ? getComputedStyle(mm).transform : '',
      rule: before ? before.transform : '',
    };
  });
  expect(motion.open).toBe(true);
  expect(motion.opacity).toBe('1');
  expect(motion.transform === 'none' || motion.transform === 'matrix(1, 0, 0, 1, 0, 0)').toBe(true);
  await page.waitForTimeout(50);
  const sfx = await page.evaluate(() => window.__gobMilestoneSfx || []);
  expect(sfx.filter((n) => n === 'STING_MILESTONE')).toHaveLength(1);
});

test('conference_rs_region uses the existing lost-round copy', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openOffice(page, visitKind('conference_rs_region'));
  const modal = await waitOpen(page, 'conference_rs_region');
  await expect(modal.getByText(/still qualify for the Region Tournament/)).toBeVisible();
  await expect(modal.getByText(/sim the rest of the Conference Tourney/)).toBeVisible();
});
