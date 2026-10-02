// @ts-check
/**
 * polish/chrome-audio (2026-10-02): Jamie's walk-through, chrome and audio.
 *
 * B1 week strip has no "Blocks Advance" tag        B6 unsaved-changes modal
 * B2 tournament badge sits right of the week       B7 Settings stats tiles
 * B3 title overlay copy, "Season N" eyebrow        B8 audio: two Settings switches
 * B4 Office lists the signed class (week 36)       B9 Sim Game Sound switch
 * B5 Home Base career strip
 *
 * CHROME_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const O = require('./helpers/officeFixtures');
const H = require('./helpers/homeBaseFixtures');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/polish-chrome-audio');
const TAG = process.env.CHROME_SHOT_TAG || 'after';
const shot = (page, name, opts) => page.screenshot(Object.assign(
  { path: path.join(SHOTS, name + '-' + TAG + '-1280.png') }, opts || {}));

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });
test.beforeEach(async ({ page }) => { await page.setViewportSize({ width: 1280, height: 720 }); });

const clone = (value) => JSON.parse(JSON.stringify(value));
const ORANGE = (rgb) => { const m = /rgba?\((\d+), (\d+), (\d+)/.exec(rgb); return !!m && +m[1] > 200 && +m[2] > 110 && +m[2] < 190 && +m[3] < 90; };

/* ------------------------------------------------------------------ B1 --- */

test('B1: the week strip has no Blocks Advance tag; the blocking step keeps its outline', async ({ page }) => {
  await O.openOffice(page, O.STATES.win);
  await shot(page, 'b1-week-strip');
  const steps = page.locator('#office-root .wk-step');
  await expect(steps).toHaveCount(5);
  await expect(page.locator('#office-root .td-gate')).toHaveCount(0);
  await expect(page.locator('#office-root .week-strip')).not.toContainText(/blocks advance/i);
  const blocking = page.locator('#office-root .wk-step[data-step-state="blocking"]');
  await expect(blocking).toHaveCount(1);
  await expect(blocking).toHaveClass(/gated/);
  await expect(blocking).toHaveText('Review recruit invites');
});

/* ------------------------------------------------------------------ B2 --- */

async function topBar(page) {
  return page.evaluate(() => {
    const box = (el) => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, mid: (r.top + r.bottom) / 2, width: r.width }; };
    const shown = (el) => !!el && !el.hidden && el.getBoundingClientRect().width > 0 && getComputedStyle(el).display !== 'none';
    const value = document.getElementById('gob-week-value');
    const round = document.getElementById('gob-week-phase');
    const emblem = document.querySelector('#fcc-header-emblem svg');
    const rank = document.getElementById('gob-rank-stat');
    return {
      text: document.querySelector('.top-stats').innerText.replace(/\s+/g, ' ').trim(),
      value: value.textContent.trim(), valueBox: box(value),
      round: shown(round) ? round.textContent.trim() : null, roundBox: shown(round) ? box(round) : null,
      emblem: shown(emblem) ? box(emblem) : null,
      rank: box(rank), top: box(document.querySelector('html.gob-shell .top')),
      advance: box(document.querySelector('.adv-wrap')), stats: box(document.querySelector('.top-stats')),
      lockupWords: document.querySelectorAll('#fcc-header-emblem .gob-lk-txt').length,
    };
  });
}

function tournamentWeek(week) {
  const data = clone(O.STATES.tournament);
  data.week = week;
  return data;
}

test('B2: a regular-season week still shows "Week N" and no tournament descriptor', async ({ page }) => {
  await O.openOffice(page, O.STATES.win);
  await shot(page, 'b2-top-strip-week-22', { clip: { x: 0, y: 0, width: 1280, height: 120 } });
  const g = await topBar(page);
  expect(g.value).toBe('Week 22');
  expect(g.round).toBe(null);
  expect(g.emblem).toBe(null);
  await expect(page.locator('html.gob-shell .top')).not.toHaveClass(/is-tier/);
});

for (const [week, tier, round] of [
  [27, 'Conference', 'First Round'], [28, 'Conference', 'Semifinals'], [29, 'Conference', 'Championship'],
  [30, 'Region', 'First Round'], [31, 'Region', 'Championship'],
  [32, 'National', 'First Round'], [33, 'National', 'Semifinals'], [34, 'National', 'Championship'],
]) {
  test('B2: week ' + week + ' shows no week number, only "' + tier + ' Tournament / ' + round + '"', async ({ page }) => {
    await O.openOffice(page, tournamentWeek(week));
    await expect(page.locator('#fcc-header-emblem svg')).toBeVisible();
    if (week === 27 || week === 31 || week === 34) {
      await shot(page, 'b2-top-strip-week-' + week, { clip: { x: 0, y: 0, width: 1280, height: 120 } });
    }
    const g = await topBar(page);
    // No week number anywhere in the strip.
    expect(g.text).not.toMatch(/week/i);
    expect(g.text).not.toMatch(new RegExp('\\b' + week + '\\b'));
    // The round descriptor sits where the week sits: the stat after National Rank.
    expect(g.value).toBe(tier + ' Tournament');
    expect(g.round).toBe(round);
    expect(g.valueBox.left).toBeGreaterThan(g.rank.right);
    expect(g.roundBox.top).toBeGreaterThanOrEqual(g.valueBox.bottom - 1);
    // The emblem is beside the words, not over them, and everything is inside the bar.
    expect(g.emblem.right).toBeLessThanOrEqual(g.valueBox.left);
    expect(g.lockupWords, 'the emblem carries no second wordmark').toBe(0);
    for (const part of [g.emblem, g.valueBox, g.roundBox]) {
      expect(part.top).toBeGreaterThanOrEqual(g.top.top);
      expect(part.bottom).toBeLessThanOrEqual(g.top.bottom);
    }
    // The space beside the action button stays empty.
    expect(g.advance.left - g.stats.right).toBeGreaterThan(120);
    // The round is named in the same words as the Advance button.
    await expect(page.locator('#play-now')).toContainText(round.replace(/s$/, ''));
  });
}

// Follow-up (2026-10-02): after the tournament the week is named, not numbered.
for (const [week, label] of [[35, 'Signing Day'], [36, 'Offseason']]) {
  test('B2: week ' + week + ' shows no week number, only "' + label + '"', async ({ page }) => {
    const data = clone(week === 35 ? O.STATES.signing_day : O.STATES.regular);
    data.week = week;
    if (week === 36) data.office_digest.next_game = null;
    await O.openOffice(page, data);
    const g = await topBar(page);
    expect(g.value).toBe(label);
    expect(g.text).not.toMatch(/week/i);
    expect(g.text).not.toMatch(new RegExp('\\b' + week + '\\b'));
    // Not a tournament round: no emblem, no round line, and it sits in the week's place.
    expect(g.round).toBe(null);
    expect(g.emblem).toBe(null);
    expect(g.valueBox.left).toBeGreaterThan(g.rank.right);
    expect(g.valueBox.top).toBeGreaterThanOrEqual(g.top.top);
    expect(g.valueBox.bottom).toBeLessThanOrEqual(g.top.bottom);
    await expect(page.locator('html.gob-shell .top')).not.toHaveClass(/is-tier/);
  });
}

test('B2: a browse page paints the same descriptor (recruiting, week 31)', async ({ page }) => {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { await route.continue(); return; }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname.startsWith('/franchise/command-center/data')) { await O.fulfillJson(route, tournamentWeek(31)); return; }
    if (pathname.startsWith('/franchise/recruiting-data')) {
      await O.fulfillJson(route, { week: 31, team_id: O.TID, team: 'Lancaster', team_region: 'A', recruits: [], team_name_map: {} });
      return;
    }
    await O.fulfillJson(route, {});
  });
  await page.goto('/recruiting.html?franchise_id=' + O.FID + '&team_id=' + O.TID + '&from=fcc');
  await expect(page.locator('#gob-week-value')).toHaveText('Region Tournament', { timeout: 15000 });
  await expect(page.locator('#gob-week-phase')).toHaveText('Championship');
  await expect(page.locator('#fcc-header-emblem svg')).toBeVisible();
  await expect(page.locator('.top-stats')).not.toContainText(/week/i);
});

/* ------------------------------------------------------------------ B3 --- */

function title(type, extra) {
  return Object.assign({
    id: 'cm-' + type, type, season: 3, conference: 2, region: 'A',
    winner_team_id: O.TID, winner_team_name: 'Lancaster', winner_primary_color: '#27408E',
    loser_team_name: 'Four Corners', winner_record: { W: 24, L: 2 }, winner_seed: 1, user_is_winner: true,
  }, extra || {});
}

function withTitle(moment) {
  const item = {
    id: 'championship', kind: 'championship', tier: 'SEASON_PEAK', priority: 10,
    payload_ref: 'pending_championship_moments', seen_key: 'pending_championship_moments',
    title: 'Championship moment', line: '', style: 'gold', sting: 'STING_SEASON_PEAK', duration: 'long',
  };
  return Object.assign(clone(O.STATES.regular), {
    pending_championship_moments: [moment], moments: [item], moments_for_this_visit: [item],
  });
}

for (const [name, moment, headline] of [
  ['regular-season', title('trophy_spotlight'), 'Regular Season Conference Champions'],
  ['conference-tournament', title('conference_championship', { score: { winner: 78, loser: 71 } }), 'Conference Tournament Champions'],
  ['region', title('region_championship', { score: { winner: 80, loser: 70 } }), 'Region Champions'],
  ['national', title('national_championship', { score: { winner: 66, loser: 60 } }), 'National Champions'],
]) {
  test('B3: ' + name + ' overlay reads "' + headline + '" under a "Season N" eyebrow', async ({ page }) => {
    await O.openOffice(page, withTitle(moment));
    const pk = page.locator('.pk.is-open');
    await expect(pk).toBeVisible({ timeout: 15000 });
    await expect(pk.locator('.pk-t')).toHaveText(headline);
    await expect(pk.locator('.pk-k')).toHaveText('Season 3');
    if (name === 'regular-season' || name === 'conference-tournament') {
      await page.waitForTimeout(3200);
      await shot(page, 'b3-overlay-' + name);
    }
  });
}

/* ------------------------------------------------------------------ B4 --- */

const CLASS = [
  { name: 'Miles Hart', position: 'SG', rt_now: 82, rt_potential: 93, home_region: 'A' },
  { name: 'Owen Blake', position: 'PF', rt_now: 71, rt_potential: 80, home_region: 'C' },
  { name: 'Dante Okafor', position: 'C', rt_now: 64, rt_potential: 77, home_region: 'A' },
  { name: 'Terrence Villanueva-Washington', position: 'PG', rt_now: 58, rt_potential: 58, home_region: 'F' },
];

/** Week 36: running Signing Day in week 35 moves the franchise on. */
function week36(recruits) {
  const data = clone(O.STATES.regular);
  data.week = 36;
  data.week_35_recruiting_ran = true;
  data.recruiting_wire = { board_saved_week: 0, counts: {}, week_35_orders_submitted: true, week_36_results_seen: true };
  data.office_digest.next_game = null;
  data.office_digest.recruiting_wire = { status: '', events: [], pending_count: 0, urgent: false, unseen_count: 0 };
  data.office_digest.signed_class = recruits ? { recruits } : null;
  data.office_digest.todos = [{ id: 'go_to_next_season', label_key: 'go_to_next_season', required: true, done: false,
    gates_advance: false, is_advance_action: true, route: '' }];
  return data;
}

test('B4: after Signing Day has run, the Recruiting column lists every signed recruit', async ({ page }) => {
  await O.openOffice(page, week36(CLASS));
  await shot(page, 'b4-signed-class');
  const card = page.locator('#office-root .office-class');
  await expect(card).toBeVisible();
  await expect(card.locator('.card-h')).toContainText('Signing class');
  await expect(card.locator('.card-h')).toContainText('4 signed');
  const rows = card.locator('.wr');
  await expect(rows).toHaveCount(CLASS.length);
  for (let i = 0; i < CLASS.length; i += 1) {
    await expect(rows.nth(i)).toContainText(CLASS[i].name);
    await expect(rows.nth(i)).toContainText(CLASS[i].position);
  }
  // Grade now -> ceiling, as RT letters; one letter when they are the same.
  await expect(rows.nth(0).locator('.sg-rt b')).toHaveText(['A', 'A+']);
  await expect(rows.nth(3).locator('.sg-rt b')).toHaveText(['C+']);
  // Nothing is cut off, however long the name.
  const overflow = await rows.evaluateAll((nodes) => nodes.filter((n) => n.scrollWidth > n.clientWidth + 1).length);
  expect(overflow).toBe(0);
  await expect(page.locator('#office-root .office-wire')).toHaveCount(0);
});

test('B4: an empty class says so; no class payload keeps the recruiting wire', async ({ page }) => {
  await O.openOffice(page, week36([]));
  await expect(page.locator('#office-root .office-class')).toContainText('No recruits signed with your program.');
  await O.openOffice(page, week36(null));
  await expect(page.locator('#office-root .office-class')).toHaveCount(0);
  await expect(page.locator('#office-root .office-wire')).toBeVisible();
});

/* ------------------------------------------------------------------ B5 --- */

const BIG_CAREER = {
  user_id: 'e2e-user', username: 'e2e',
  record: { wins: 271, losses: 168, total_games: 439, win_rate: 62 },
  championships_total: { conf_rs: 4, conf_t: 3, region: 2, national: 1 },
  titles_total: 10, win_pct_display: '.617', geek_points: 14060, seasons_completed: 16, programs: 2,
};

test('B5: the career strip gives each numeral room; Trophy Case sits with the utility links', async ({ page }) => {
  await H.openHomeBase(page, { careerBody: BIG_CAREER });
  await page.waitForTimeout(400);
  await shot(page, 'b5-mode-select');
  const strip = page.locator('[data-hb-career]');
  await expect(strip.locator('.cr-n > div')).toHaveCount(4);
  const g = await strip.evaluate((el) => {
    const column = el.closest('.hb-l').getBoundingClientRect();
    const grid = el.querySelector('.cr-n').getBoundingClientRect();
    const cells = Array.from(el.querySelectorAll('.cr-n > div')).map((cell) => {
      const r = cell.getBoundingClientRect();
      const inner = Array.from(cell.querySelectorAll('b, em, span')).map((n) => n.getBoundingClientRect());
      return {
        left: r.left, right: r.right,
        contentRight: Math.max.apply(null, inner.map((n) => n.right)),
        clipped: Array.from(cell.querySelectorAll('b, span')).some((n) => n.scrollWidth > n.clientWidth + 1),
        divider: parseFloat(getComputedStyle(cell).borderLeftWidth) || 0,
      };
    });
    return { column: { left: column.left, right: column.right }, grid: { left: grid.left, right: grid.right }, cells };
  });
  // The numerals own the whole column (the Trophy Case link used to take the right 105px).
  expect(g.grid.right - g.grid.left).toBeGreaterThanOrEqual(g.column.right - g.column.left - 2);
  for (let i = 0; i < g.cells.length; i += 1) {
    expect(g.cells[i].clipped, 'cell ' + i + ' is not truncated').toBe(false);
    expect(g.cells[i].divider, 'no divider hard against the numeral').toBe(0);
    if (i > 0) {
      const air = g.cells[i].left - g.cells[i - 1].contentRight;
      expect(air, 'air between numeral ' + (i - 1) + ' and ' + i).toBeGreaterThanOrEqual(24);
    }
  }
  await expect(strip.locator('[data-hb-trophy-case]')).toHaveCount(0);
  await expect(page.locator('.hb-util [data-hb-trophy-case]')).toBeVisible();
  await expect(page.locator('.door-tag')).toHaveText('Last played');
  // Still nothing below the fold.
  const fold = await page.evaluate(() => Array.from(document.querySelectorAll('.hb-career, .hb-util'))
    .every((el) => el.getBoundingClientRect().bottom <= window.innerHeight + 1));
  expect(fold).toBe(true);
});

/* ------------------------------------------------------------------ B6 --- */

test('B6: the unsaved-changes modal keeps three actions, uncramped, with Save the only orange', async ({ page }) => {
  await O.openOffice(page, O.STATES.win);
  await page.addScriptTag({ url: '/js/shared/gobLeaveConfirm.js' });
  const result = await page.evaluate(() => new Promise((resolve) => {
    window.__leave = [];
    window.GOBLeaveConfirm.open({
      title: 'Unsaved Game Plan', copy: 'Save your game plan changes before you leave?', saveLabel: 'Save Game Plan',
      onSave: () => { window.__leave.push('save'); return true; },
      onDiscard: () => { window.__leave.push('discard'); },
      proceed: () => { window.__leave.push('proceed'); },
    });
    requestAnimationFrame(() => resolve(true));
  }));
  expect(result).toBe(true);
  const modal = page.locator('.gob-leave-confirm');
  await expect(modal).toBeVisible();
  await page.waitForTimeout(300);
  await shot(page, 'b6-unsaved-modal');

  const save = modal.locator('[data-leave="save"]');
  const discard = modal.locator('[data-leave="discard"]');
  const stay = modal.locator('[data-leave="stay"]');
  await expect(save).toHaveText('Save Game Plan');
  await expect(discard).toBeVisible();
  await expect(stay).toHaveText('Keep Editing');
  await expect(stay).toBeFocused();

  const g = await modal.evaluate((el) => {
    const read = (sel) => {
      const node = el.querySelector(sel);
      const r = node.getBoundingClientRect();
      const cs = getComputedStyle(node);
      const lines = Math.round(node.scrollHeight / parseFloat(cs.lineHeight || '18'));
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height,
        bg: cs.backgroundColor, wraps: node.scrollWidth > node.clientWidth + 1 || r.height > 60, lines };
    };
    return { save: read('[data-leave="save"]'), discard: read('[data-leave="discard"]'), stay: read('[data-leave="stay"]') };
  });
  // One label, one line, per button (Keep Editing used to wrap).
  for (const key of ['save', 'discard', 'stay']) {
    expect(g[key].wraps, key + ' label fits on one line').toBe(false);
    expect(g[key].height).toBeGreaterThanOrEqual(40);
    expect(g[key].height).toBeLessThanOrEqual(52);
  }
  // Save spans the modal; the two ways out share the row beneath it.
  expect(g.save.bottom).toBeLessThanOrEqual(g.discard.top - 8);
  expect(Math.abs(g.discard.top - g.stay.top)).toBeLessThanOrEqual(1);
  expect(Math.abs(g.discard.width - g.stay.width)).toBeLessThanOrEqual(1);
  expect(g.save.width).toBeGreaterThanOrEqual(g.discard.width + g.stay.width);
  expect(g.stay.left - g.discard.right).toBeGreaterThanOrEqual(8);
  // Colour law: Save is the only orange.
  expect(ORANGE(g.save.bg), 'save is orange: ' + g.save.bg).toBe(true);
  expect(ORANGE(g.discard.bg)).toBe(false);
  expect(ORANGE(g.stay.bg)).toBe(false);

  // Behaviour is unchanged.
  await stay.click();
  await expect(modal).toHaveCount(0);
  expect(await page.evaluate(() => window.__leave)).toEqual([]);
});

/* ------------------------------------------------------------- B7 + B8 --- */

const ME = {
  user_id: 'e2e-user', username: 'CoachJamie', email: 'jamie@example.com',
  record: { wins: 271, losses: 168 },
  championships_total: { conf_rs: 4, conf_t: 3, region: 2, national: 1 },
};

async function openSettings(page, me) {
  await O.openOffice(page, O.STATES.win);
  await page.route('**/api/auth/me', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(me || ME) }));
  await page.locator('#gob-rail-settings').click();
  const panel = page.locator('#gob-settings-host .settings');
  await expect(panel).toBeVisible();
  await expect(panel.locator('[data-coach]')).toBeVisible();
  return panel;
}

test('B7: Stats tiles fit the record, and National Titles follows Titles', async ({ page }) => {
  const panel = await openSettings(page);
  await page.waitForTimeout(500);
  await shot(page, 'b7-b8-settings');
  await expect(panel.locator('[data-coach] h3')).toHaveText('Stats');
  const tiles = panel.locator('.cs-grid .cs');
  await expect(tiles.locator('span')).toHaveText(['Career record', 'Titles', 'National Titles']);
  await expect(tiles.nth(0).locator('b')).toHaveText('271–168');
  await expect(tiles.nth(1).locator('b')).toHaveText('10');
  await expect(tiles.nth(2).locator('b')).toHaveText('1');
  const spill = await tiles.evaluateAll((nodes) => nodes.map((tile) => {
    const box = tile.getBoundingClientRect();
    const grid = tile.parentElement.getBoundingClientRect();
    const inner = Array.from(tile.querySelectorAll('b, span, em')).map((n) => n.getBoundingClientRect().right);
    return { text: Math.max.apply(null, inner) - box.right, grid: box.right - grid.right };
  }));
  spill.forEach((s, i) => {
    expect(s.text, 'tile ' + i + ' text stays inside its container').toBeLessThanOrEqual(0);
    expect(s.grid, 'tile ' + i + ' stays inside the panel').toBeLessThanOrEqual(1);
  });
});

test('B7: a four-digit record still fits its tile', async ({ page }) => {
  const panel = await openSettings(page, Object.assign({}, ME, { record: { wins: 1271, losses: 1168 } }));
  const tile = panel.locator('.cs-rec');
  await expect(tile.locator('b')).toHaveText('1271–1168');
  // Measure the digits themselves: the <b> box stays inside a tile its content overflows.
  const spill = await tile.evaluate((el) => {
    const digits = Array.from(el.querySelectorAll('b em')).map((n) => n.getBoundingClientRect().right);
    return Math.max.apply(null, digits) - el.getBoundingClientRect().right;
  });
  expect(spill).toBeLessThan(0);
});

test('B8: Settings audio is two switches, Music and Sound, and nothing else', async ({ page }) => {
  const panel = await openSettings(page);
  const switches = panel.locator('[data-audio-switch]');
  await expect(switches).toHaveCount(2);
  await expect(panel.locator('.aud .aud-l')).toHaveText(['Music', 'Sound']);
  await expect(panel.locator('.slider')).toHaveCount(0);
  await expect(panel.locator('[data-mute]')).toHaveCount(0);
  await expect(panel).not.toContainText(/Master|Ambience|Sound Effects/);
  for (const id of ['music', 'sound']) {
    const sw = panel.locator('[data-audio-switch="' + id + '"]');
    await expect(sw).toHaveAttribute('role', 'switch');
    await expect(sw).toHaveAttribute('aria-checked', 'true');
  }

  // Sound off: no interface sound plays anywhere. (The spy only records a sound that will be heard.)
  await page.evaluate(() => { window.__gobSfxCalls = []; });
  await panel.locator('[data-audio-switch="sound"]').click();
  await expect(panel.locator('[data-audio-switch="sound"]')).toHaveAttribute('aria-checked', 'false');
  await page.evaluate(() => { window.__gobSfxCalls = []; window.GOBUiSfx.playSfx('SFX_SELECT'); window.GOBUiSfx.playSfx('STING_WIN'); });
  expect(await page.evaluate(() => window.__gobSfxCalls)).toEqual([]);
  // Music is its own switch: still on, and it is what the franchise track and the lobby music ask for.
  expect(await page.evaluate(() => window.GOBUiSfx.getAppAudio())).toEqual({ music: true, sound: false });
  expect(await page.evaluate(() => [window.GOBUiSfx.outputVolume(0.4, 'music'), window.GOBUiSfx.outputVolume(0.4, 'ambience')])).toEqual([0.4, 0.4]);
  await panel.locator('[data-audio-switch="music"]').click();
  expect(await page.evaluate(() => [window.GOBUiSfx.outputVolume(0.4, 'music'), window.GOBUiSfx.outputVolume(0.4, 'ambience')])).toEqual([0, 0]);

  // The switches do not touch gameplay audio, which belongs to the court.
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('gob_audio_v1')));
  expect(stored.app).toEqual({ music: false, sound: false });
  expect(stored.master).toEqual({ level: 100, muted: false });
  expect(stored.music).toEqual({ level: 100, muted: false });
  expect(stored.sfx).toEqual({ level: 100, muted: false });

  // Survives a reload.
  await page.reload();
  await page.locator('#gob-rail-settings').click();
  await expect(page.locator('[data-audio-switch="music"]')).toHaveAttribute('aria-checked', 'false');
  await expect(page.locator('[data-audio-switch="sound"]')).toHaveAttribute('aria-checked', 'false');
  await page.locator('[data-audio-switch="sound"]').click();
  await page.evaluate(() => { window.__gobSfxCalls = []; window.GOBUiSfx.playSfx('SFX_SELECT'); });
  expect(await page.evaluate(() => window.__gobSfxCalls)).toEqual(['SFX_SELECT']);
});

test('B8: Music off stops the franchise track where it is playing; on starts it again', async ({ page }) => {
  // A recording Audio, so the test sees what would be heard without a sound card.
  await page.addInitScript(() => {
    window.__audios = [];
    window.Audio = class {
      constructor(src) { this.src = src || ''; this.volume = 1; this.paused = true; this.currentTime = 0; this.loop = false; this.dataset = {}; window.__audios.push(this); }
      play() { this.paused = false; return Promise.resolve(); }
      pause() { this.paused = true; }
      addEventListener() {}
      removeEventListener() {}
    };
  });
  const playing = () => page.evaluate(() => window.__audios
    .filter((a) => /scouting-track/.test(a.src) && !a.paused && a.volume > 0).length);
  const panel = await openSettings(page);
  await expect.poll(playing, { message: 'the franchise track plays in the Office' }).toBe(1);

  await panel.locator('[data-audio-switch="music"]').click();
  await expect.poll(playing, { message: 'Music off: nothing is playing' }).toBe(0);
  // Sound is untouched by the Music switch.
  expect(await page.evaluate(() => window.GOBUiSfx.outputVolume(0.7, 'sfx'))).toBe(0.7);

  await panel.locator('[data-audio-switch="music"]').click();
  await expect.poll(playing, { message: 'Music on: the track starts again on this page' }).toBe(1);
});

test('B8: the Account page has no audio control', async ({ page }) => {
  await stubAuth(page);
  await page.route('**/api/auth/me', (r) => r.fulfill({ status: 200, contentType: 'application/json',
    body: JSON.stringify({ user_id: 'e2e-user', username: 'CoachJamie', email: 'jamie@example.com' }) }));
  await page.goto('/account.html');
  await expect(page.locator('.card-label', { hasText: 'Settings' })).toBeVisible();
  await page.waitForTimeout(600);
  await shot(page, 'b8-account', { fullPage: true });
  await expect(page.locator('#acct-ambience-switch')).toHaveCount(0);
  await expect(page.locator('body')).not.toContainText(/ambience/i);
  await expect(page.locator('[role="switch"]')).toHaveCount(0);
});

/* ------------------------------------------------------------------ B9 --- */

const POS = ['PG', 'SG', 'SF', 'PF', 'C'];
const TEAMS = {
  home: { teamName: 'Lancaster', name: 'Lancaster', abbr: 'LAN', color: '#1F8A5B', rank: 12, rec: '3–1' },
  away: { teamName: 'Xavier', name: 'Xavier', abbr: 'XAV', color: '#9E1B32', rank: 20, rec: '2–2' },
};
function simFrame() {
  const player = (side, i) => ({ id: side + i, pos: POS[i], name: (side === 'home' ? 'Home ' : 'Away ') + i, jersey: 10 + i,
    rt: 70, pts: 4, reb: 2, ast: 1, def: 50, fouls: 0, hot: false, cold: false, out: false, sub: false, spot: false });
  return { phase: 'play', quarter: 1, score: { away: 2, home: 4, clock: '3:06', quarter: 'Q1', shot: 21, afoul: 1, hfoul: 2 },
    worm: { samples: [{ elapsed: 0, margin: 0 }, { elapsed: 174, margin: 2 }], elapsed: 174, domain: 1920, progress: 0.09 },
    teamPanel: null, away: POS.map((_, i) => player('away', i)), home: POS.map((_, i) => player('home', i)),
    benchAway: [], benchHome: [], ticker: null };
}

/** The Sim Game broadcast, mounted from the shipped module on a court-shaped URL. */
async function mountSim(page) {
  // The bus scopes by page: gameplay audio is court.html. Serve a bare page at that path.
  await page.route('**/court.html*', (r) => r.fulfill({ status: 200, contentType: 'text/html',
    body: '<!doctype html><meta charset="utf-8"><div id="scoreboard" style="height:120px;background:#111"></div>' }));
  await page.goto('/court.html?e2e=sim');
  await page.evaluate(async ({ teams, frames }) => {
    // Load a second copy of the bus first, as the court page has (shell from /js, Phaser from /static).
    await import('/static/js/shared/uiSfx.js');
    const mod = await import('/js/phaser/utils/simGamePresentation.js');
    window.__bus = await import('/js/shared/uiSfx.js');
    mod.showSimGamePresentation({ teams, frames }, { driveScoreboard: false });
  }, { teams: TEAMS, frames: Array.from({ length: 400 }, simFrame) });
  await page.waitForSelector('.sgp-root [data-fit]');
  await page.waitForTimeout(300);
}

test('B9: Sim Game has a Sound switch, not a Highlights toggle, and it persists', async ({ page }) => {
  await mountSim(page);
  await shot(page, 'b9-sim-game');
  await page.locator('.sgp-root .tgl').screenshot({ path: path.join(SHOTS, 'b9-sim-toggle-' + TAG + '.png') });
  await expect(page.locator('.sgp-root [data-highlights]')).toHaveCount(0);
  await expect(page.locator('.sgp-root')).not.toContainText(/highlights/i);
  const sound = page.locator('.sgp-root [data-sound]');
  await expect(sound).toHaveCount(1);
  await expect(page.locator('.sgp-root .tgl-lbl')).toHaveText('SOUND');
  await expect(sound).toHaveAttribute('role', 'switch');
  await expect(sound).toHaveAttribute('aria-checked', 'true');
  expect(await page.evaluate(() => window.__bus.audioScope())).toBe('game');
  expect(await page.evaluate(() => [window.__bus.outputVolume(1, 'sfx'), window.__bus.outputVolume(1, 'music')])).toEqual([1, 1]);

  // Off: all gameplay audio is silent, and the choice is stored.
  await sound.click();
  await expect(sound).toHaveAttribute('aria-checked', 'false');
  await expect(sound).not.toHaveClass(/\bon\b/);
  expect(await page.evaluate(() => [window.__bus.outputVolume(1, 'sfx'), window.__bus.outputVolume(1, 'music')])).toEqual([0, 0]);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('gob_audio_v1')).master.muted)).toBe(true);
  // Every copy of the bus on the page hears it (localhost serves the Phaser tree from /static).
  expect(await page.evaluate(async () => {
    const copies = await Promise.all([import('/js/shared/uiSfx.js'), import('/static/js/shared/uiSfx.js')]);
    return copies.map((bus) => [bus.outputVolume(1, 'sfx'), bus.outputVolume(1, 'music')]);
  })).toEqual([[0, 0], [0, 0]]);
  // Highlights carry on with the sound off: the callout cadence is never suspended.
  expect(await page.evaluate(() => {
    const cadence = document.querySelector('.sgp-root').__cadence;
    return cadence ? !!cadence.suspended : false;
  })).toBe(false);

  // The next game starts as the player left it.
  await mountSim(page);
  await expect(page.locator('.sgp-root [data-sound]')).toHaveAttribute('aria-checked', 'false');
  await page.locator('.sgp-root [data-sound]').click();
  await expect(page.locator('.sgp-root [data-sound]')).toHaveAttribute('aria-checked', 'true');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('gob_audio_v1')).master.muted)).toBe(false);
});

test('B8/B9: the Sim Game switch and the Settings switches are separate', async ({ page }) => {
  await mountSim(page);
  await page.locator('.sgp-root [data-sound]').click();
  // Off the court, interface sound and music are untouched by the game's switch.
  await O.openOffice(page, O.STATES.win);
  await page.waitForFunction(() => !!window.GOBUiSfx);
  expect(await page.evaluate(() => window.GOBUiSfx.audioScope())).toBe('app');
  expect(await page.evaluate(() => window.GOBUiSfx.getAppAudio())).toEqual({ music: true, sound: true });
  expect(await page.evaluate(() => [window.GOBUiSfx.outputVolume(0.7, 'sfx'), window.GOBUiSfx.outputVolume(0.4, 'music')])).toEqual([0.7, 0.4]);
});
