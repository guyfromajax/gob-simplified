// @ts-check
/**
 * The FCC's recruiting buttons: the green #play-now and the ghost beneath it.
 *
 * The ghost is the way BACK into recruiting, and it appears exactly when this week's
 * recruiting step is done and the green button has moved on — invites in weeks 20-26,
 * orders on Signing Day. Any earlier and it would only restate where the green button
 * already goes.
 *
 * Signing Day also splits the green button: once orders are saved it RUNS the day;
 * before that it is still the way IN to the board.
 *
 * Calls the REAL GOBAdvance button writers — same technique as
 * fcc-invite-step.spec.js — so the test tracks the shipped branch order rather than a
 * copy of it.
 *
 * Run: npx playwright test tests/e2e/fcc-recruiting-buttons.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const ADVANCE_SRC = fs.readFileSync(path.join(S, 'js/shared/gobAdvance.js'), 'utf8');
const CSS = fs.readFileSync(path.join(S, 'franchise-command-center.css'), 'utf8');
const HTML = fs.readFileSync(path.join(S, 'franchise-command-center.html'), 'utf8');

/** The real hero button group, lifted out of the shipped template. */
const HERO_GROUP = (() => {
  const open = HTML.indexOf('<div class="hero-buttons-group">');
  if (open === -1) throw new Error('hero-buttons-group not found');
  const close = HTML.indexOf('</div>', HTML.indexOf('id="fcc-edit-recruiting"'));
  if (close === -1) throw new Error('hero-buttons-group not closed');
  return HTML.slice(open, close + 6);
})();

async function runWith(page, data) {
  await page.setContent(`<!doctype html><style>${CSS}</style><div id="franchise-container"><div class="right-controls">${HERO_GROUP}</div></div>`);
  await page.addScriptTag({ path: path.join(S, 'js/shared/gobAdvance.js') });
  return page.evaluate((data) => {
    const env = { userTeamId: 'user-team', fccCpuSimNeedsRecovery: () => false };
    window.GOBAdvance.updatePlayButton(data, env);
    window.GOBAdvance.updateEditRecruitingButton(data, env);
    const play = document.getElementById('play-now');
    const edit = document.getElementById('fcc-edit-recruiting');
    const pr = play.getBoundingClientRect();
    const er = edit.getBoundingClientRect();
    return {
      text: play.textContent.trim(),
      mode: play.dataset.mode || null,
      editText: edit.textContent.trim(),
      editShown: getComputedStyle(edit).display !== 'none',
      editBelow: er.top >= pr.bottom - 1,
      sameWidth: Math.round(er.width) === Math.round(pr.width),
      sameHeight: Math.round(er.height) === Math.round(pr.height),
      // Colour law: green is the gating action. The ghost button must not be green.
      editBg: getComputedStyle(edit).backgroundColor,
      playBg: getComputedStyle(play).backgroundImage,
    };
  }, data);
}

const SUBMITTED = { recruiting_wire: { week_35_orders_submitted: true } };
const NOT_SUBMITTED = { recruiting_wire: { week_35_orders_submitted: false } };
/** Invites submitted in week `w` — the marker the invite step reads. */
const sentIn = (w) => ({ recruiting_wire: { board_saved_week: w, has_saved_board: true } });

test.describe('week 35 — orders submitted', () => {
  test('the green button runs the day', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...SUBMITTED });
    expect(r.text).toBe('Run Recruiting Day');
    expect(r.mode).toBe('week35-run');
  });

  test('a ghost button below it goes back to edit', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...SUBMITTED });
    expect(r.editShown).toBe(true);
    expect(r.editText).toBe('Edit Recruiting Orders');
    expect(r.editBelow).toBe(true);
  });

  test('the ghost button is the same size as the green one', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...SUBMITTED });
    expect(r.sameWidth).toBe(true);
    expect(r.sameHeight).toBe(true);
  });

  test('and is not green — green is reserved for the gating action', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...SUBMITTED });
    expect(r.playBg).toContain('gradient');
    expect(r.editBg).toBe('rgba(0, 0, 0, 0)');
  });
});

test.describe('week 35 — before orders exist', () => {
  test('the green button opens the board', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...NOT_SUBMITTED });
    expect(r.text).toBe('Run Signing Day');
    expect(r.mode).toBe('week35-recruiting');
  });

  test('the entry goes directly to recruiting without an optional cut step', () => {
    const start = ADVANCE_SRC.indexOf("if (mode === 'week35-recruiting')");
    const end = ADVANCE_SRC.indexOf("if (mode === 'cut-players')", start);
    const branch = ADVANCE_SRC.slice(start, end);
    expect(branch).toContain("'/recruiting.html?'");
    expect(branch).not.toContain('/cut-players.html');
    expect(branch).not.toContain('Cut Players?');
  });

  test('no ghost button — it would point where the green one already goes', async ({ page }) => {
    const r = await runWith(page, { week: 35, ...NOT_SUBMITTED });
    expect(r.editShown).toBe(false);
  });
});

test.describe('the pair is week 35 only', () => {
  for (const week of [26, 34, 36]) {
    test(`week ${week} shows no ghost button even with orders on file`, async ({ page }) => {
      const r = await runWith(page, { week, ...SUBMITTED });
      expect(r.editShown).toBe(false);
      expect(r.mode).not.toBe('week35-run');
    });
  }

  test('an illegal roster still outranks the run', async ({ page }) => {
    // cut_required is checked before the week-35 branch and must stay there: signing
    // over a roster that is not legal yet would commit points against the wrong size.
    const r = await runWith(page, { week: 35, cut_required: true, ...SUBMITTED });
    expect(r.mode).toBe('cut-players');
  });
});

test.describe('weeks 20-26 — the ghost follows the invite step', () => {
  test('it appears once invites are submitted THIS week', async ({ page }) => {
    for (const week of [20, 23, 26]) {
      const r = await runWith(page, { week, ...sentIn(week) });
      expect(r.editShown, `week ${week}`).toBe(true);
      expect(r.editText, `week ${week}`).toBe('Edit Recruit Invites');
      expect(r.editBelow, `week ${week}`).toBe(true);
    }
  });

  test('and not before — the green button is still the way in', async ({ page }) => {
    const r = await runWith(page, { week: 23, ...sentIn(22) });
    // Green is still steering to the board; a second button pointing there is noise.
    expect(r.mode).toBe('recruit-invites');
    expect(r.editShown).toBe(false);
  });

  test('it is the same size as the green button here too', async ({ page }) => {
    const r = await runWith(page, { week: 22, ...sentIn(22) });
    expect(r.sameWidth).toBe(true);
    expect(r.sameHeight).toBe(true);
    expect(r.editBg).toBe('rgba(0, 0, 0, 0)');
  });

  test('outside the invite window a sent board does not summon it', async ({ page }) => {
    for (const week of [19, 27]) {
      const r = await runWith(page, { week, ...sentIn(week) });
      expect(r.editShown, `week ${week}`).toBe(false);
    }
  });

  test('the label is the week\'s own — invites here, orders on Signing Day', async ({ page }) => {
    const invite = await runWith(page, { week: 24, ...sentIn(24) });
    const signing = await runWith(page, { week: 35, ...SUBMITTED });
    expect(invite.editText).toBe('Edit Recruit Invites');
    expect(signing.editText).toBe('Edit Recruiting Orders');
  });
});
