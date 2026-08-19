// @ts-check
/**
 * The invite step in updatePlayButton — weeks 20-26 open with recruiting.
 *
 * The green button runs Recruit Invites -> Training -> Play Game. Invites come first
 * because they are ASSIGNED during run-training, so a board sent afterwards misses its
 * own week. The step's branch order relative to cut_required is the reason the whole
 * thing works, so it is asserted here too.
 *
 * Extracts the REAL updatePlayButton source out of franchise-command-center.js and
 * evaluates it against a stub #play-now, so the test tracks the shipped branch order
 * rather than a copy of it.
 *
 * Run: npx playwright test tests/e2e/fcc-invite-step.spec.js --project=chromium
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

/** Pulled from source, so a moved week boundary moves these tests with it. */
function extractConst(source, name) {
  const m = source.match(new RegExp(`^const ${name} = \\d+;$`, 'm'));
  if (!m) throw new Error(`${name} not found`);
  return m[0];
}

const UPDATE_PLAY_BUTTON = extractFunction(JS, 'updatePlayButton');
const CONSTS = ['SIGNING_DAY_WEEK', 'INVITE_FIRST_WEEK', 'INVITE_LAST_WEEK']
  .map((n) => extractConst(JS, n)).join('\n');

/** Call the real function with synthetic command-center data; report the button. */
async function runWith(page, data) {
  return page.evaluate(({ src, consts, data }) => {
    document.body.innerHTML = '<button id="play-now">Run Training</button>';
    window.fccCpuSimNeedsRecovery = () => false;
    window.userTeamId = 'user-team';
    // Label lookups only; no test here asserts postseason copy.
    window.EOS_PLAY_CTA_BY_WEEK = {};
    window.EOS_SIM_CTA_BY_WEEK = {};
    // eslint-disable-next-line no-eval
    eval(`${consts}\n${src}\nwindow.__updatePlayButton = updatePlayButton;`);
    window.__updatePlayButton(data);
    const btn = document.getElementById('play-now');
    return { text: btn.textContent.trim(), mode: btn.dataset.mode || null };
  }, { src: UPDATE_PLAY_BUTTON, consts: CONSTS, data });
}

/** Board sent in week `w` — the marker the step reads. */
const sentIn = (w) => ({ recruiting_wire: { board_saved_week: w, has_saved_board: true } });
const NEVER_SENT = { recruiting_wire: { board_saved_week: 0, has_saved_board: false } };

test.describe('the invite step comes first', () => {
  test('week 20 asks you to SET invites', async ({ page }) => {
    const r = await runWith(page, { week: 20, ...NEVER_SENT });
    expect(r.text).toBe('Set Recruit Invites');
    expect(r.mode).toBe('recruit-invites');
  });

  test('weeks 21-26 ask you to REVIEW them', async ({ page }) => {
    for (const week of [21, 23, 26]) {
      const r = await runWith(page, { week, ...sentIn(week - 1) });
      expect(r.text, `week ${week}`).toBe('Review Recruit Invites');
      expect(r.mode, `week ${week}`).toBe('recruit-invites');
    }
  });

  test('a board sent in an EARLIER week does not satisfy this week', async ({ page }) => {
    // The board persists week to week, so "has a board" cannot be the marker — it never
    // clears once set and would gate week 20 only. Sending it THIS week is the step.
    const r = await runWith(page, { week: 24, ...sentIn(20) });
    expect(r.mode).toBe('recruit-invites');
  });

  test('sending it THIS week clears the step', async ({ page }) => {
    for (const week of [20, 24, 26]) {
      const r = await runWith(page, { week, ...sentIn(week) });
      expect(r.mode, `week ${week}`).not.toBe('recruit-invites');
    }
  });

  test('outside weeks 20-26 there is no invite step', async ({ page }) => {
    for (const week of [19, 27, 34]) {
      const r = await runWith(page, { week, ...NEVER_SENT });
      expect(r.mode, `week ${week}`).not.toBe('recruit-invites');
    }
  });

  test('a missing recruiting_wire payload counts as unsent', async ({ page }) => {
    // Defensive: an older payload shape must still steer rather than silently pass.
    const r = await runWith(page, { week: 20 });
    expect(r.mode).toBe('recruit-invites');
  });
});

test.describe('Recruit Invites -> Training -> Play Game', () => {
  test('the three steps run in that order within one invite week', async ({ page }) => {
    const pending = await runWith(page, { week: 22, ...sentIn(21) });
    const sent = await runWith(page, { week: 22, ...sentIn(22), training_completed: false });
    const trained = await runWith(page, { week: 22, ...sentIn(22), training_completed: true });
    expect(pending.mode).toBe('recruit-invites');
    expect(sent.mode).toBe('training');
    expect(trained.mode).toBe('play');
  });
});

test.describe('branch order', () => {
  test('cut_required outranks the invite step', async ({ page }) => {
    const r = await runWith(page, { week: 20, cut_required: true, ...NEVER_SENT });
    expect(r.text).toBe('Assign Practice Squad');
    expect(r.mode).toBe('cut-players');
  });

  test('week 35 still routes to recruiting, not the invite step', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...NEVER_SENT });
    expect(r.mode).toBe('week35-recruiting');
  });

  test('week 36 still offers the season transition', async ({ page }) => {
    const r = await runWith(page, { week: 36, ...NEVER_SENT });
    expect(r.mode).toBe('new-season');
  });

  test('cpu-sim recovery still preempts everything', async ({ page }) => {
    const r = await page.evaluate(({ src, consts }) => {
      document.body.innerHTML = '<button id="play-now"></button>';
      window.fccCpuSimNeedsRecovery = () => true;
      window.userTeamId = 'user-team';
      // eslint-disable-next-line no-eval
      eval(`${consts}\n${src}\nwindow.__u = updatePlayButton;`);
      window.__u({ week: 20, cut_required: true, recruiting_wire: { has_saved_board: false } });
      const btn = document.getElementById('play-now');
      return { text: btn.textContent.trim(), mode: btn.dataset.mode };
    }, { src: UPDATE_PLAY_BUTTON, consts: CONSTS });
    expect(r.mode).toBe('finish-cpu-sims');
  });
});
