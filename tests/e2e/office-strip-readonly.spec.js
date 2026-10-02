// @ts-check
/**
 * The Office progress strip is status, not controls (Jamie, 2026-10-02).
 *
 * A quiet stepper: a list of steps with a state mark and plain text, joined by a thin
 * line. Nothing in it can be clicked, focused or activated. The action button in the top
 * bar is the only control that advances the week.
 *
 * STRIP_SHOT_TAG=before names the shots when the spec runs against old code.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const O = require('./helpers/officeFixtures');

test.describe.configure({ timeout: 90000 });

const SHOTS = path.join(__dirname, '../../reports/office-week-1');
const TAG = process.env.STRIP_SHOT_TAG || 'after';
const SIZES = [[1280, 720], [1920, 1080]];

test.beforeAll(() => { fs.mkdirSync(SHOTS, { recursive: true }); });

const clone = (value) => JSON.parse(JSON.stringify(value));
const todo = (id, extra) => Object.assign({ id, label_key: id, required: true, done: false, gates_advance: false, is_advance_action: false, route: '/training.html' }, extra || {});

/** Every week shape the strip has to carry. */
const STATES = {
  // A regular week: training done, the game is next.
  regular: () => {
    const data = clone(O.STATES.win);
    data.week = 12;
    data.office_digest.todos = [
      todo('run_training', { done: true }),
      todo('play_next_game', { is_advance_action: true, route: '/set-lineup.html' }),
    ];
    return data;
  },
  // An invite week: the recruit invites block the advance.
  invite: () => clone(O.STATES.win),
  // Week 1: training camp.
  camp: () => clone(O.STATES.first_week),
  tournament: () => clone(O.STATES.tournament),
  signing_day: () => clone(O.STATES.signing_day),
  // Week 36: the season is over.
  offseason: () => {
    const data = clone(O.STATES.regular);
    data.week = 36;
    data.office_digest.next_game = null;
    data.office_digest.todos = [
      todo('view_recruiting_results', { done: true, route: '/recruiting.html' }),
      todo('finish_season', { is_advance_action: true, route: '' }),
    ];
    return data;
  },
};

/** What the strip is made of, and how each step is painted. */
function stripFacts(page) {
  return page.evaluate(() => {
    const strip = document.querySelector('#office-root .week-strip');
    const track = strip.querySelector('.week-track');
    const neutral = (value) => {
      const colours = String(value).match(/rgba?\([^)]*\)/g) || [];
      return colours.every((c) => {
        const p = c.match(/[\d.]+/g).map(Number);
        const alpha = p.length > 3 ? p[3] : 1;
        return alpha === 0 || (Math.abs(p[0] - p[1]) <= 2 && Math.abs(p[1] - p[2]) <= 2);
      });
    };
    return {
      trackTag: track.tagName,
      controls: strip.querySelectorAll('button, a, input, select, textarea, summary, [tabindex], [role="button"], [role="link"], [onclick], [href]').length,
      steps: [...track.children].map((step) => {
        const cs = getComputedStyle(step);
        const label = step.querySelector('.td-l');
        const dot = step.querySelector('.wk-dot');
        return {
          tag: step.tagName,
          state: step.dataset.stepState,
          current: step.getAttribute('aria-current'),
          text: label.textContent.trim(),
          check: !!dot.querySelector('svg'),
          cursor: cs.cursor,
          outline: cs.boxShadow,
          fill: cs.backgroundColor,
          border: cs.borderTopWidth,
          labelColor: getComputedStyle(label).color,
          labelWeight: Number(getComputedStyle(label).fontWeight),
          tabIndex: step.tabIndex,
          // What is painted: the label, the mark and its ring.
          neutral: neutral([getComputedStyle(label).color, getComputedStyle(dot).color,
            getComputedStyle(dot).boxShadow, getComputedStyle(dot).backgroundImage].join(' ')),
          joined: step.previousElementSibling ? getComputedStyle(step, '::before').height : null,
        };
      }),
      overflow: strip.scrollWidth - strip.clientWidth,
    };
  });
}

/** The listeners attached to the strip and each of its steps (Chrome's own answer). */
async function stripListeners(page) {
  const client = await page.context().newCDPSession(page);
  const { result } = await client.send('Runtime.evaluate', {
    expression: '[...document.querySelectorAll("#office-root .week-strip, #office-root .week-strip *")]',
  });
  const { result: props } = await client.send('Runtime.getProperties', { objectId: result.objectId, ownProperties: true });
  const found = [];
  for (const prop of props) {
    if (!/^\d+$/.test(prop.name) || !prop.value || !prop.value.objectId) continue;
    const { listeners } = await client.send('DOMDebugger.getEventListeners', { objectId: prop.value.objectId });
    listeners.forEach((listener) => found.push(listener.type));
  }
  await client.detach();
  return found;
}

/** Count anything a step could set off: a navigation, or a press of the action button. */
async function watch(page) {
  await page.evaluate(() => {
    window.__strip = { nav: [], advance: 0 };
    if (window.GOBNav) window.GOBNav.go = (url) => { window.__strip.nav.push(String(url)); };
    const play = document.getElementById('play-now');
    if (play) play.addEventListener('click', () => { window.__strip.advance += 1; }, true);
  });
}

for (const name of Object.keys(STATES)) {
  test('the strip is a read-only stepper: ' + name, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await O.openOffice(page, STATES[name]());
    const facts = await stripFacts(page);

    // A list of steps, and nothing in it that can be operated.
    expect(facts.trackTag).toBe('OL');
    expect(facts.steps.length).toBeGreaterThan(0);
    expect(facts.controls).toBe(0);
    facts.steps.forEach((step) => {
      expect(step.tag, step.text).toBe('LI');
      expect(step.tabIndex, step.text).toBe(-1);
      expect(step.cursor, step.text).toBe('default');
      // It does not look like a control either: no pill outline, no fill, no border.
      expect(step.outline, step.text).toBe('none');
      expect(step.fill, step.text).toBe('rgba(0, 0, 0, 0)');
      expect(step.border, step.text).toBe('0px');
      // Neutral only: no green, orange or navy.
      expect(step.neutral, step.text).toBe(true);
      if (step.joined !== null) expect(step.joined, step.text).toBe('1px');
    });
    expect(await stripListeners(page)).toEqual([]);

    // Status: at most one current step, marked for a reader; done steps carry the check.
    const current = facts.steps.filter((step) => step.current === 'step');
    expect(current.length).toBeLessThanOrEqual(1);
    facts.steps.forEach((step) => {
      expect(step.check, step.text).toBe(step.state === 'done');
      if (step.current === 'step') {
        expect(step.labelColor, step.text).toBe('rgb(255, 255, 255)');
        expect(step.labelWeight, step.text).toBeGreaterThanOrEqual(700);
      } else {
        expect(step.labelColor, step.text).not.toBe('rgb(255, 255, 255)');
        expect(step.labelWeight, step.text).toBeLessThan(600);
      }
    });
    expect(facts.overflow).toBeLessThanOrEqual(1);

    // A click, a double click or a key on any step does nothing.
    await watch(page);
    const url = page.url();
    const steps = page.locator('#office-root .wk-step');
    for (let i = 0; i < await steps.count(); i += 1) {
      const box = await steps.nth(i).boundingBox();
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.dblclick(box.x + box.width / 2, box.y + box.height / 2);
      await page.keyboard.press('Enter');
      await page.keyboard.press('Space');
    }
    await page.waitForTimeout(400);
    expect(await page.evaluate(() => window.__strip)).toEqual({ nav: [], advance: 0 });
    expect(page.url()).toBe(url);

    // Not in the tab order: tabbing through the page never lands in the strip.
    await page.locator('body').click({ position: { x: 2, y: 2 } });
    let landed = 0;
    for (let i = 0; i < 40; i += 1) {
      await page.keyboard.press('Tab');
      if (await page.evaluate(() => !!(document.activeElement && document.activeElement.closest('.week-strip')))) landed += 1;
    }
    expect(landed).toBe(0);
  });
}

test('the action button in the top bar is the one control that advances', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await O.openOffice(page, STATES.regular());
  await watch(page);
  // The step that mirrors the button names the same action, and does nothing.
  const mirror = page.locator('#office-root [data-advance-mirror="1"]');
  await expect(mirror.locator('.td-l')).toHaveText(((await page.locator('#play-now').textContent()) || '').trim());
  await mirror.click();
  await page.waitForTimeout(400);
  expect(await page.evaluate(() => window.__strip)).toEqual({ nav: [], advance: 0 });
  // The button does.
  await page.locator('#play-now').click();
  await expect.poll(() => page.evaluate(() => window.__strip.advance)).toBe(1);
  await expect.poll(() => page.evaluate(() => window.__strip.nav.length)).toBeGreaterThan(0);
  expect(new URL(await page.evaluate(() => window.__strip.nav[0]), 'http://local').pathname).toBe('/set-lineup.html');
});

for (const [width, height] of SIZES) {
  test('shots of the stepper at ' + width, async ({ page }) => {
    for (const name of ['regular', 'invite']) {
      await page.setViewportSize({ width, height });
      await O.openOffice(page, STATES[name]());
      await page.waitForTimeout(2500); // the arrival
      await page.mouse.move(0, 0);
      await page.screenshot({ path: path.join(SHOTS, 'strip-' + name + '-week-' + TAG + '-' + width + '.png') });
      const strip = await page.locator('#office-root .week-strip').boundingBox();
      await page.screenshot({
        path: path.join(SHOTS, 'strip-' + name + '-week-close-' + TAG + '-' + width + '.png'),
        clip: { x: 0, y: 0, width, height: Math.ceil(strip.y + strip.height + 12) },
      });
    }
  });
}
