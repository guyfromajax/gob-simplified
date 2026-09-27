// @ts-check
/**
 * The invite step in updatePlayButton — weeks 20-26 open with recruiting.
 *
 * The green button runs Recruit Invites -> Training -> Play Game. Invites come first
 * because they are ASSIGNED during run-training, so a board sent afterwards misses its
 * own week. The step's branch order relative to cut_required is the reason the whole
 * thing works, so it is asserted here too.
 *
 * Calls the REAL GOBAdvance.updatePlayButton (the Office and the FCC both delegate
 * to it) against a stub #play-now, so the test tracks the shipped branch order
 * rather than a copy of it.
 *
 * Run: npx playwright test tests/e2e/fcc-invite-step.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const path = require('path');

const ADVANCE = path.join(__dirname, '../../FrontEnd/static/js/shared/gobAdvance.js');

/** Call the real advance button with synthetic command-center data; report the button. */
async function runWith(page, data, recover) {
  await page.setContent('<button id="play-now">Run Training</button>');
  await page.addScriptTag({ path: ADVANCE });
  return page.evaluate(({ data, recover }) => {
    window.GOBAdvance.updatePlayButton(data, {
      userTeamId: 'user-team',
      fccCpuSimNeedsRecovery: () => !!recover,
    });
    const btn = document.getElementById('play-now');
    return { text: btn.textContent.trim(), mode: btn.dataset.mode || null };
  }, { data, recover: !!recover });
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

  test('week 36 shows results until they are seen, then the season transition', async ({ page }) => {
    const unseen = await runWith(page, { week: 36, ...NEVER_SENT });
    expect(unseen.mode).toBe('view-recruiting-results');
    const seen = await runWith(page, { week: 36, recruiting_wire: { week_36_results_seen: true } });
    expect(seen.mode).toBe('new-season');
  });

  test('cpu-sim recovery still preempts everything', async ({ page }) => {
    const r = await runWith(page, {
      week: 20, cut_required: true, recruiting_wire: { has_saved_board: false },
    }, true);
    expect(r.mode).toBe('finish-cpu-sims');
  });
});
