// @ts-check
/**
 * Week-20 invite-board gate in updatePlayButton — including its branch ORDER
 * relative to cut_required, which is the reason the gate works at all.
 *
 * Extracts the REAL updatePlayButton source out of franchise-command-center.js and
 * evaluates it against a stub #play-now, so the test tracks the shipped branch order
 * rather than a copy of it. Only two dependencies need stubbing
 * (fccCpuSimNeedsRecovery, userTeamId).
 *
 * Run: npx playwright test tests/e2e/fcc-week20-gate.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const JS = fs.readFileSync(
  path.join(__dirname, '../../FrontEnd/static/franchise-command-center.js'), 'utf8');

function extractFunction(source, name) {
  const lines = source.split('\n');
  const start = lines.findIndex((l) => l.startsWith(`function ${name}(`));
  if (start === -1) throw new Error(`${name} not found`);
  const end = lines.findIndex((l, i) => i > start && l === '}');
  return lines.slice(start, end + 1).join('\n');
}

const UPDATE_PLAY_BUTTON = extractFunction(JS, 'updatePlayButton');

/** Call the real function with synthetic command-center data; report the button. */
async function runWith(page, data) {
  return page.evaluate(({ src, data }) => {
    document.body.innerHTML = '<button id="play-now">Run Training</button>';
    // The only two dependencies of updatePlayButton beyond its argument.
    window.fccCpuSimNeedsRecovery = () => false;
    window.userTeamId = 'user-team';
    // eslint-disable-next-line no-eval
    eval(`${src}; window.__updatePlayButton = updatePlayButton;`);
    window.__updatePlayButton(data);
    const btn = document.getElementById('play-now');
    return { text: btn.textContent.trim(), mode: btn.dataset.mode || null };
  }, { src: UPDATE_PLAY_BUTTON, data });
}

const NO_BOARD = { recruiting_wire: { has_saved_board: false } };
const HAS_BOARD = { recruiting_wire: { has_saved_board: true } };

test.describe('week-20 gate', () => {
  test('week 20 with no saved board becomes Build Invite Board', async ({ page }) => {
    const r = await runWith(page, { week: 20, ...NO_BOARD });
    expect(r.text).toBe('Build Invite Board');
    expect(r.mode).toBe('build-invite-board');
  });

  test('week 20 WITH a saved board does not gate', async ({ page }) => {
    const r = await runWith(page, { week: 20, ...HAS_BOARD });
    expect(r.mode).not.toBe('build-invite-board');
  });

  test('adjacent weeks never gate, even with no board', async ({ page }) => {
    for (const week of [19, 21, 26]) {
      const r = await runWith(page, { week, ...NO_BOARD });
      expect(r.mode, `week ${week}`).not.toBe('build-invite-board');
    }
  });

  test('a missing recruiting_wire payload is treated as no board', async ({ page }) => {
    // Defensive: an older payload shape must still gate rather than silently pass.
    const r = await runWith(page, { week: 20 });
    expect(r.mode).toBe('build-invite-board');
  });
});

test.describe('branch order', () => {
  test('cut_required outranks the week-20 gate', async ({ page }) => {
    const r = await runWith(page, { week: 20, cut_required: true, ...NO_BOARD });
    expect(r.text).toBe('Assign Practice Squad');
    expect(r.mode).toBe('cut-players');
  });

  test('the week-20 gate outranks the normal week action', async ({ page }) => {
    const plain = await runWith(page, { week: 20, ...HAS_BOARD });
    const gated = await runWith(page, { week: 20, ...NO_BOARD });
    expect(gated.mode).toBe('build-invite-board');
    expect(gated.mode).not.toBe(plain.mode);
  });

  test('week 35 still routes to recruiting, not the board gate', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...NO_BOARD });
    expect(r.mode).toBe('week35-recruiting');
  });

  test('week 36 still offers the season transition', async ({ page }) => {
    const r = await runWith(page, { week: 36, ...NO_BOARD });
    expect(r.mode).toBe('new-season');
  });

  test('cpu-sim recovery still preempts everything', async ({ page }) => {
    const r = await page.evaluate(({ src }) => {
      document.body.innerHTML = '<button id="play-now"></button>';
      window.fccCpuSimNeedsRecovery = () => true;
      window.userTeamId = 'user-team';
      // eslint-disable-next-line no-eval
      eval(`${src}; window.__u = updatePlayButton;`);
      window.__u({ week: 20, cut_required: true, recruiting_wire: { has_saved_board: false } });
      const btn = document.getElementById('play-now');
      return { text: btn.textContent.trim(), mode: btn.dataset.mode };
    }, { src: UPDATE_PLAY_BUTTON });
    expect(r.mode).toBe('finish-cpu-sims');
  });
});
