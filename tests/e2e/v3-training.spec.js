// @ts-check
/**
 * v3 training polish (Jamie, 2026-10-03).
 *
 *  1. Coaching Focus tooltips: the focus name is the title; no coaching archetype name.
 *  2. Training Report, Readiness: six bars on a -40..40 scale, the word in parentheses;
 *     Fast Break = Fast Break + Fast Break Defense, Press/Traps = P/T Defense + P/T Offense.
 *  3. Training Report, Standouts: the locker room second, the regression third.
 *  4. The Training playbook choice is a saved setting: Custom Playbook and its plays stay
 *     the default for every later training, camp and next season included, until the
 *     user switches back to Current Playbooks.
 *
 *   V3T_SHOTS=before|after   shots to reports/v3-training/
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const report = require('./helpers/trainingReportFixture');
const fx = require('./helpers/v3TrainingFixture');

const OUT = path.join(__dirname, '../../reports/v3-training');
const PHASE = process.env.V3T_SHOTS || '';
const SIZES = [[1280, 720], [1920, 1080]];
const ARCHETYPES = ['Culture Builder', 'Authoritarian', 'Systems Coach', 'Player Maximizer'];

test.describe.configure({ timeout: 120000 });

// [low, high, bars, word]: Jamie's scale.
const BANDS = [
  [-40, -30, 0, 'Awful'],
  [-29, -20, 1, 'Very Weak'],
  [-19, -10, 2, 'Weak'],
  [-9, 9, 3, 'Neutral'],
  [10, 19, 4, 'Strong'],
  [20, 29, 5, 'Very Strong'],
  [30, 40, 6, 'Elite'],
];

async function openReport(page, data) {
  await stubAuth(page);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await report.installReportApi(page, data);
  await page.goto(report.reportUrl(data));
  await expect(page.locator('#training-report-view')).not.toHaveClass(/is-loading/, { timeout: 30000 });
  await expect(page.locator('.tr-card--readiness')).toBeVisible();
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

/** The busy week with its two readiness notes replaced. `undefined` drops the note's number. */
function withReadiness(fastBreak, pressTraps, attrs) {
  const data = report.busy();
  data.training_notes = data.training_notes.map((note) => {
    if (note.title === 'Fast Break Readiness') return Object.assign({ title: note.title, body: 'Very Strong' }, fastBreak === undefined ? {} : { value: fastBreak });
    if (note.title === 'Press/Trap Readiness') return Object.assign({ title: note.title, body: 'Very Weak' }, pressTraps === undefined ? {} : { value: pressTraps });
    return note;
  });
  if (attrs) Object.assign(data.team_attributes, attrs);
  return data;
}

function readReadiness(page) {
  return page.locator('.tr-card--readiness .tr-readiness').evaluateAll((pairs) => pairs.map((pair) => {
    const meter = pair.querySelector('.tr-meter');
    const steps = meter ? [...meter.querySelectorAll('i')] : [];
    return {
      key: pair.dataset.ready,
      label: pair.querySelector('.tr-label').textContent.trim(),
      word: pair.querySelector('.tr-ready-word').textContent.trim(),
      meter: !!meter,
      steps: steps.length,
      // Lit bars are the first N: a filled meter never has a gap.
      lit: steps.map((el) => (el.classList.contains('on') ? '1' : '0')).join(''),
      aria: meter ? meter.getAttribute('aria-label') : null,
      value: pair.dataset.value || null,
    };
  }));
}

function bars(n) {
  return '1'.repeat(n) + '0'.repeat(6 - n);
}

// ---------------------------------------------------------------------------
// 1. Coaching Focus tooltips
// ---------------------------------------------------------------------------
// The focus each option trains, as its tooltip titles it.
const FOCUS_TITLES = {
  'authoritarian-discipline': 'Discipline',
  'authoritarian-rebounding': 'Rebounding',
  'authoritarian-execution': 'Execution',
  'authoritarian-teamwork': 'Teamwork',
  'systems-coach-offense': 'Offense',
  'systems-coach-defense': 'Defense',
  'systems-coach-fast-breaks': 'Fast Breaks',
  'systems-coach-press-trap': 'Press / Trap',
  'player-maximizer-top-3': 'Top 3 Attributes',
  'player-maximizer-attributes-4-6': 'Attributes 4\u20136',
  'player-maximizer-positional-focus': 'Positional Focus',
  'player-maximizer-custom': 'Custom',
  'culture-builder-inspire': 'Inspire',
  'culture-builder-confidence': 'Confidence',
  'culture-builder-community': 'Community Engagement',
  'culture-builder-teamwork': 'Team Building',
};

test.describe('1. Coaching Focus tooltips', () => {
  test('the focus name is the title and no archetype is named, on every focus option', async ({ page }) => {
    await fx.openTraining(page, fx.newState());
    const options = page.locator('.archetype-option:has(input[name="coaching-focus"])');
    await expect(options).toHaveCount(16);
    const seen = {};
    for (let i = 0; i < 16; i += 1) {
      const option = options.nth(i);
      const value = await option.locator('input[name="coaching-focus"]').getAttribute('value');
      await option.scrollIntoViewIfNeeded();
      await option.hover();
      const tip = page.locator('.training-tooltip');
      await expect(tip).toHaveClass(/is-visible/);
      // The shared tooltip element is refilled on each hover: wait for this option's copy.
      await expect(tip.locator('.tt-name')).toHaveText(FOCUS_TITLES[value]);
      const read = await tip.evaluate((el) => ({
        text: el.textContent.replace(/\s+/g, ' ').trim(),
        first: el.firstElementChild.className,
        title: el.firstElementChild.textContent.trim(),
        eyebrow: el.querySelectorAll('.tt-eyebrow').length,
        desc: el.querySelector('.tt-desc').textContent.trim().length,
      }));
      // The first thing in the tooltip is the focus name; nothing sits above it.
      expect(read.first, value).toBe('tt-name');
      expect(read.title, value).toBe(FOCUS_TITLES[value]);
      expect(read.eyebrow, value).toBe(0);
      expect(read.desc, value).toBeGreaterThan(10);
      for (const archetype of ARCHETYPES) expect(read.text, value).not.toContain(archetype);
      seen[value] = read.title;
      await page.mouse.move(0, 0);
      await expect(tip).not.toHaveClass(/is-visible/);
    }
    expect(seen).toEqual(FOCUS_TITLES);
  });
});

// ---------------------------------------------------------------------------
// 2. Readiness
// ---------------------------------------------------------------------------
test.describe('2. Training Report, Readiness', () => {
  test('two rows: Fast Break and Press/Traps, six bars each, the word in parentheses', async ({ page }) => {
    await openReport(page, report.busy());
    const rows = await readReadiness(page);
    expect(rows.map((row) => [row.key, row.label])).toEqual([['fast-break', 'Fast Break'], ['press-traps', 'Press/Traps']]);
    expect(rows.map((row) => row.steps)).toEqual([6, 6]);
    expect(rows.map((row) => row.word)).toEqual(['(Strong)', '(Weak)']);
    await expect(page.locator('.tr-card--readiness')).not.toContainText('P/T Defense');
    // The word sits beside the bars, on their line.
    const beside = await page.locator('[data-ready="press-traps"] .tr-ready').evaluate((el) => {
      const meter = el.querySelector('.tr-meter').getBoundingClientRect();
      const word = el.querySelector('.tr-ready-word').getBoundingClientRect();
      return { gap: word.left - meter.right, drift: Math.abs((word.top + word.bottom) / 2 - (meter.top + meter.bottom) / 2) };
    });
    expect(beside.gap).toBeGreaterThan(0);
    expect(beside.gap).toBeLessThanOrEqual(16);
    expect(beside.drift).toBeLessThanOrEqual(3);
  });

  for (const [low, high, lit, word] of BANDS) {
    test(word + ': ' + low + ' to ' + high + ' is ' + lit + ' of six bars', async ({ page }) => {
      // Both edges of the band, one on each row.
      await openReport(page, withReadiness(low, high));
      let rows = await readReadiness(page);
      expect(rows.map((row) => [row.value, row.lit, row.word, row.aria])).toEqual([
        [String(low), bars(lit), '(' + word + ')', word],
        [String(high), bars(lit), '(' + word + ')', word],
      ]);
      // And a value inside it.
      const mid = Math.round((low + high) / 2);
      await openReport(page, withReadiness(mid, mid));
      rows = await readReadiness(page);
      expect(rows.map((row) => [row.lit, row.word])).toEqual([[bars(lit), '(' + word + ')'], [bars(lit), '(' + word + ')']]);
    });
  }

  test('every whole number from -40 to 40 lands in exactly one band', async ({ page }) => {
    test.setTimeout(300000);
    const expected = [];
    for (const [low, high, lit, word] of BANDS) for (let v = low; v <= high; v += 1) expected.push([v, lit, word]);
    expect(expected.map((row) => row[0])).toEqual(Array.from({ length: 81 }, (_, i) => i - 40));
    // Two values a load, one on each row.
    for (let i = 0; i < expected.length; i += 2) {
      const a = expected[i];
      const b = expected[Math.min(i + 1, expected.length - 1)];
      await openReport(page, withReadiness(a[0], b[0]));
      const rows = await readReadiness(page);
      expect(rows.map((row) => [Number(row.value), row.lit, row.word]), a[0] + ',' + b[0]).toEqual([
        [a[0], bars(a[1]), '(' + a[2] + ')'], [b[0], bars(b[1]), '(' + b[2] + ')'],
      ]);
    }
  });

  test('Awful is six empty bars, still drawn', async ({ page }) => {
    await openReport(page, withReadiness(-40, -30));
    const rows = await readReadiness(page);
    expect(rows.map((row) => [row.meter, row.steps, row.lit, row.word])).toEqual([
      [true, 6, '000000', '(Awful)'], [true, 6, '000000', '(Awful)'],
    ]);
    const colors = await page.locator('[data-ready="fast-break"] .tr-meter i').evaluateAll((els) => [...new Set(els.map((el) => getComputedStyle(el).backgroundColor))]);
    expect(colors).toEqual(['rgba(255, 255, 255, 0.12)']);
  });

  test('the bars come from the number the note stores, not from the old word', async ({ page }) => {
    // The stored words say Very Strong / Very Weak; the numbers say otherwise, and win.
    await openReport(page, withReadiness(-12, 33));
    const rows = await readReadiness(page);
    expect(rows.map((row) => [row.lit, row.word])).toEqual([[bars(2), '(Weak)'], [bars(6), '(Elite)']]);
  });

  test('a report stored before the note carried its number: the two team attributes, combined', async ({ page }) => {
    // Fast Break 15 + Fast Break Defense 16 = 31; P/T Defense -12 + P/T Offense -19 = -31.
    await openReport(page, withReadiness(undefined, undefined, {
      fb_efficiency: 15, fb_opp_modifier: 16, pt_efficiency: -12, pt_opp_modifier: -19,
    }));
    let rows = await readReadiness(page);
    expect(rows.map((row) => [row.value, row.lit, row.word])).toEqual([['31', bars(6), '(Elite)'], ['-31', bars(0), '(Awful)']]);

    await openReport(page, withReadiness(undefined, undefined, {
      fb_efficiency: -20, fb_opp_modifier: -20, pt_efficiency: 20, pt_opp_modifier: 20,
    }));
    rows = await readReadiness(page);
    expect(rows.map((row) => [row.value, row.word])).toEqual([['-40', '(Awful)'], ['40', '(Elite)']]);
  });

  test('a fraction or a value off the scale has no band: a dash, no bars', async ({ page }) => {
    for (const [fastBreak, pressTraps] of [[12.5, 41], [null, -41], ['12', 0.5]]) {
      await openReport(page, withReadiness(fastBreak, pressTraps));
      const rows = await readReadiness(page);
      expect(rows.map((row) => [row.meter, row.word, row.value]), String(fastBreak)).toEqual([[false, '—', null], [false, '—', null]]);
    }
    // The same for the attribute fallback.
    await openReport(page, withReadiness(undefined, undefined, { fb_efficiency: 4.5, fb_opp_modifier: 5, pt_efficiency: 30, pt_opp_modifier: 11 }));
    const rows = await readReadiness(page);
    expect(rows.map((row) => [row.meter, row.word])).toEqual([[false, '—'], [false, '—']]);
  });
});

// ---------------------------------------------------------------------------
// 3. Standouts
// ---------------------------------------------------------------------------
test.describe('3. Training Report, Standouts', () => {
  test('order: the first item as before, the locker room second, the regression third', async ({ page }) => {
    const data = report.busy();
    await openReport(page, data);
    const rows = await page.locator('.tr-card--standouts .tr-standout').evaluateAll((els) => els.map((el) => ({
      key: el.dataset.standout,
      label: el.querySelector('.tr-label').textContent.trim(),
      name: el.querySelector('.training-notes-hero-name').textContent.trim(),
      top: Math.round(el.getBoundingClientRect().top),
    })));
    expect(rows.map((row) => row.key)).toEqual(['practice', 'locker', 'regression']);
    expect(rows.map((row) => row.label)).toEqual([
      'Practice Player Of The Week', 'Most Positive Locker Room Influence', 'Biggest Regression',
    ]);
    expect(rows.map((row) => row.name)).toEqual([data.players[11].name, data.players[2].name, data.players[8].name]);
    // Read top to bottom in that order.
    expect(rows[0].top).toBeLessThan(rows[1].top);
    expect(rows[1].top).toBeLessThan(rows[2].top);
  });

  test('training camp keeps the same order with its own titles', async ({ page }) => {
    await openReport(page, report.camp());
    const labels = await page.locator('.tr-card--standouts .tr-standout .tr-label').allTextContents();
    expect(labels.map((text) => text.trim())).toEqual(['Training Camp MVP', 'Most Positive Locker Room Influence', 'Biggest Concern']);
  });
});

// ---------------------------------------------------------------------------
// 4. The Training playbook choice carries forward
// ---------------------------------------------------------------------------
test.describe('4. Training playbook choice', () => {
  const FOCUS = { offense: [fx.PLAYS.motion[0], fx.PLAYS.sets[1]], defense: [fx.PLAYS.man[0], fx.PLAYS.zone[0]] };

  test('nothing saved: Current Playbooks, and that is what trains', async ({ page }) => {
    const state = fx.newState();
    await fx.openTraining(page, state);
    const mode = await fx.readMode(page);
    expect(mode.selected).toBe('current-playbooks');
    expect(mode.banner).toBe('');
    expect(mode.sessionMode).toBeNull();
    const sent = await fx.submitTraining(page, state);
    expect(sent.playbook_training_mode).toBe('current-playbooks');
    expect(sent.training_playbook_focus).toBeNull();
    expect(state.patches).toEqual([]);
  });

  test('a saved Custom Playbook is the default the next week, with its plays, and trains', async ({ page }) => {
    const state = fx.newState({ choice: { mode: 'custom', focus: fx.clone(FOCUS) } });
    await fx.openTraining(page, state);
    const mode = await fx.readMode(page);
    expect(mode.selected).toBe('custom');
    expect(mode.pressed).toEqual({ current: 'false', custom: 'true' });
    expect(mode.banner).toContain('stays your default until you switch back to Current Playbooks');
    expect(mode.focus).toEqual(FOCUS);
    const sent = await fx.submitTraining(page, state);
    expect(sent.playbook_training_mode).toBe('custom');
    expect(sent.training_playbook_focus).toEqual(FOCUS);
    // Opening the page and training did not rewrite the setting.
    expect(state.patches).toEqual([]);
  });

  test('it carries through every later training: next week, training camp, the next season', async ({ page }) => {
    const state = fx.newState({ week: 12, season: 1, choice: { mode: 'custom', focus: fx.clone(FOCUS) } });
    for (const [week, season] of [[12, 1], [13, 1], [26, 1], [1, 2], [2, 2], [1, 3]]) {
      state.week = week;
      state.season = season;
      await fx.openTraining(page, state);
      // A submit clears the page's working copy; the saved choice refills it on the next load.
      const mode = await fx.readMode(page);
      expect([week, season, mode.selected, mode.focus]).toEqual([week, season, 'custom', FOCUS]);
      const sent = await fx.submitTraining(page, state);
      expect([week, season, sent.playbook_training_mode, sent.training_playbook_focus]).toEqual([week, season, 'custom', FOCUS]);
      expect(await page.evaluate(() => sessionStorage.getItem('gob_playbook_training_mode'))).toBeNull();
    }
    expect(state.submits).toHaveLength(6);
    expect(state.patches).toEqual([]);
    expect(state.choice).toEqual({ mode: 'custom', focus: FOCUS });
  });

  test('switching back to Current Playbooks is saved, and holds from then on', async ({ page }) => {
    const state = fx.newState({ choice: { mode: 'custom', focus: fx.clone(FOCUS) } });
    await fx.openTraining(page, state);
    expect((await fx.readMode(page)).selected).toBe('custom');
    await page.locator('#playbook-mode-current-btn').click();
    await expect.poll(() => state.patches.length).toBe(1);
    expect(state.patches[0]).toEqual({ franchise_id: fx.FID, mode: 'current-playbooks' });
    let mode = await fx.readMode(page);
    expect([mode.selected, mode.banner, mode.sessionMode]).toEqual(['current-playbooks', '', null]);

    for (const [week, season] of [[12, 1], [1, 2]]) {
      state.week = week;
      state.season = season;
      await fx.openTraining(page, state);
      mode = await fx.readMode(page);
      expect([week, mode.selected, mode.focus]).toEqual([week, 'current-playbooks', null]);
      const sent = await fx.submitTraining(page, state);
      expect([sent.playbook_training_mode, sent.training_playbook_focus]).toEqual(['current-playbooks', null]);
    }
  });

  test('choosing a Custom Playbook saves it with its plays; the saved plays are pre-selected next time', async ({ page }) => {
    const state = fx.newState();
    await fx.openTraining(page, state);
    await page.locator('#playbook-mode-custom-btn').click();
    await page.waitForURL(/training-playbooks\.html/);
    await expect(page.locator('#tp-offense-grid .tp-card').first()).toBeVisible();
    await expect(page.locator('#tp-save')).toBeDisabled();
    for (const id of FOCUS.offense) await page.locator('#tp-offense-grid .tp-card[data-id="' + id + '"]').click();
    for (const id of FOCUS.defense) await page.locator('#tp-defense-grid .tp-card[data-id="' + id + '"]').click();
    // Two of each: an even split, 50% a play.
    await expect(page.locator('#tp-dock-off-pct')).toHaveText('50%');
    await expect(page.locator('#tp-dock-def-pct')).toHaveText('50%');
    await page.locator('#tp-save').click();
    await page.waitForURL(/training\.html/);
    // Saved before the page left.
    expect(state.patches).toHaveLength(1);
    expect(state.patches[0].mode).toBe('custom');
    expect(state.patches[0].franchise_id).toBe(fx.FID);
    expect(state.patches[0].focus.offense.slice().sort()).toEqual(FOCUS.offense.slice().sort());
    expect(state.patches[0].focus.defense.slice().sort()).toEqual(FOCUS.defense.slice().sort());
    await fx.waitOverlay(page);
    await expect(page.locator('#playbook-mode-custom-btn')).toHaveClass(/is-selected/);

    // Next season's camp, a new browser session: nothing in sessionStorage but the saved choice.
    await fx.submitTraining(page, state);
    await page.evaluate(() => sessionStorage.clear());
    state.week = 1;
    state.season = 2;
    await fx.openTraining(page, state);
    expect((await fx.readMode(page)).selected).toBe('custom');
    await page.locator('#playbook-mode-custom-btn').click();
    await page.waitForURL(/training-playbooks\.html/);
    await expect(page.locator('#tp-offense-grid .tp-card').first()).toBeVisible();
    const picked = await page.evaluate(() => ({
      offense: [...document.querySelectorAll('#tp-offense-grid .tp-card.is-selected[aria-pressed="true"]')].map((el) => el.dataset.id).sort(),
      defense: [...document.querySelectorAll('#tp-defense-grid .tp-card.is-selected[aria-pressed="true"]')].map((el) => el.dataset.id).sort(),
    }));
    expect(picked).toEqual({ offense: FOCUS.offense.slice().sort(), defense: FOCUS.defense.slice().sort() });
    await expect(page.locator('#tp-dock-off-pct')).toHaveText('50%');
    await expect(page.locator('#tp-dock-def-pct')).toHaveText('50%');
  });

  test('a saved play that no longer exists is dropped from the Custom Playbook page', async ({ page }) => {
    const state = fx.newState({ choice: { mode: 'custom', focus: { offense: [fx.PLAYS.motion[0], 'a-play-that-is-gone'], defense: [fx.PLAYS.man[0]] } } });
    await fx.openTraining(page, state);
    await page.locator('#playbook-mode-custom-btn').click();
    await page.waitForURL(/training-playbooks\.html/);
    await expect(page.locator('#tp-offense-grid .tp-card').first()).toBeVisible();
    await expect(page.locator('#tp-dock-off-pct')).toHaveText('100%');
    await expect(page.locator('#tp-dock-off-meta')).toContainText('1 of ');
    await page.locator('#tp-save').click();
    await page.waitForURL(/training\.html/);
    expect(state.patches[0].focus).toEqual({ offense: [fx.PLAYS.motion[0]], defense: [fx.PLAYS.man[0]] });
  });

  test('a failed save does not block this training', async ({ page }) => {
    const state = fx.newState();
    await fx.openTraining(page, state);
    await page.route('**/franchise/training-playbook-choice', (route) => route.abort());
    await page.locator('#playbook-mode-custom-btn').click();
    await page.waitForURL(/training-playbooks\.html/);
    await page.locator('#tp-offense-grid .tp-card[data-id="' + FOCUS.offense[0] + '"]').click();
    await page.locator('#tp-defense-grid .tp-card[data-id="' + FOCUS.defense[0] + '"]').click();
    await page.locator('#tp-save').click();
    await page.waitForURL(/training\.html/);
    await fx.waitOverlay(page);
    await expect(page.locator('#playbook-mode-custom-btn')).toHaveClass(/is-selected/);
    const sent = await fx.submitTraining(page, state);
    expect(sent.playbook_training_mode).toBe('custom');
    expect(sent.training_playbook_focus).toEqual({ offense: [FOCUS.offense[0]], defense: [FOCUS.defense[0]] });
  });

  test('the save is a franchise route: it follows a local franchise onto the desktop engine', async ({ page }) => {
    const state = fx.newState();
    await fx.openTraining(page, state);
    const routed = await page.evaluate(() => ({
      category: window.API_CONFIG.classifyEndpoint('/franchise/training-playbook-choice'),
      same: window.API_CONFIG.classifyEndpoint('/franchise/training-points'),
    }));
    expect(routed).toEqual({ category: 'franchise', same: 'franchise' });
  });
});

// ---------------------------------------------------------------------------
// Shots
// ---------------------------------------------------------------------------
test.describe('shots', () => {
  test.skip(!PHASE, 'V3T_SHOTS only');

  async function shot(page, name, width, locator) {
    fs.mkdirSync(OUT, { recursive: true });
    await page.waitForTimeout(300);
    const file = path.join(OUT, PHASE + '-' + name + '-' + width + '.png');
    if (locator) await locator.screenshot({ path: file, animations: 'disabled' });
    else await page.screenshot({ path: file, animations: 'disabled' });
  }

  for (const [width, height] of SIZES) {
    test('1 tooltip at ' + width, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await fx.openTraining(page, fx.newState());
      for (const [name, value] of [['fast-breaks', 'systems-coach-fast-breaks'], ['inspire', 'culture-builder-inspire']]) {
        const option = page.locator('.archetype-option:has(input[value="' + value + '"])');
        await option.scrollIntoViewIfNeeded();
        await option.hover();
        await expect(page.locator('.training-tooltip')).toHaveClass(/is-visible/);
        await shot(page, '1-tooltip-' + name, width);
        await page.mouse.move(0, 0);
      }
    });

    test('2+3 report top at ' + width, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await openReport(page, report.busy());
      await page.mouse.move(0, 0);
      await shot(page, '2-3-report-season', width);
      await openReport(page, report.camp());
      await page.mouse.move(0, 0);
      await shot(page, '2-3-report-camp', width);
    });

    test('2 every readiness band at ' + width, async ({ page }) => {
      test.skip(PHASE === 'before', 'the old meter has no bands to walk');
      await page.setViewportSize({ width, height });
      for (const [low, high, lit, word] of BANDS) {
        await openReport(page, withReadiness(low, high));
        await page.mouse.move(0, 0);
        const name = '2-readiness-' + lit + '-' + word.toLowerCase().replace(/\s+/g, '-');
        await shot(page, name, width, page.locator('#training-report-view .tr-cards'));
      }
    });

    test('4 playbook choice at ' + width, async ({ page }) => {
      await page.setViewportSize({ width, height });
      const focus = { offense: [fx.PLAYS.motion[0], fx.PLAYS.sets[1]], defense: [fx.PLAYS.man[0], fx.PLAYS.zone[0]] };
      const state = fx.newState({ week: 13, choice: { mode: 'custom', focus } });
      // "before" has no saved setting: the page is given the same server state and ignores it.
      await fx.openTraining(page, state);
      const toggle = page.locator('.playbook-mode-selection');
      await toggle.scrollIntoViewIfNeeded();
      await page.mouse.move(0, 0);
      await shot(page, '4-next-week', width);
      state.week = 1;
      state.season = 2;
      await page.evaluate(() => sessionStorage.clear());
      await fx.openTraining(page, state);
      await page.locator('.playbook-mode-selection').scrollIntoViewIfNeeded();
      await page.mouse.move(0, 0);
      await shot(page, '4-next-season-camp', width);
      if (PHASE === 'before') return;
      await page.locator('#playbook-mode-custom-btn').click();
      await page.waitForURL(/training-playbooks\.html/);
      await expect(page.locator('#tp-offense-grid .tp-card').first()).toBeVisible();
      await page.mouse.move(0, 0);
      await shot(page, '4-custom-playbook-plays-carried', width);
    });
  }
});
