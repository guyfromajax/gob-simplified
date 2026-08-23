// @ts-check
/**
 * Recruit Visit modal (weeks 20-26) + potential RT on the Walk-On Welcome table.
 *
 * Both run the REAL shared modules with only the network stubbed.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');

const ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

function player(over = {}) {
  const attributes = {};
  ATTRS.forEach((k, i) => { attributes[k] = 30 + i * 5; });
  return {
    name: 'Ellis Clemons', pos: 'PF', year: 'Junior', height: 78, weight: 210,
    attributes, rt: 72, potential_rt: 88, ...over,
  };
}

async function mount(page, payloadKey, payload) {
  await page.goto('/');
  await page.setContent('<div id="franchise-container"></div>');
  for (const f of ['js/shared/rtBucket.js', 'js/shared/playerYear.js', 'common.js']) {
    await page.addScriptTag({ content: read(f) });
  }
  await page.addScriptTag({ content: 'window.franchiseId = "f1";' });
  await page.route('**/franchise/*modal-seen*', (r) => r.fulfill({ status: 200, body: '{}' }));
  await page.addScriptTag({
    content: read(payloadKey === 'recruit_visit_modal'
      ? 'js/shared/recruitVisitModal.js' : 'js/shared/walkOnWelcomeModal.js'),
  });
  await page.evaluate(({ key, data }) => {
    const mod = key === 'recruit_visit_modal' ? window.RecruitVisitModal : window.WalkOnWelcomeModal;
    mod.maybeShow({ team: 'Lancaster', [key]: data });
  }, { key: payloadKey, data: payload });
}

/** The modal mounts after a dynamic import of sammyModal.js — wait for the table. */
async function mountAndWait(page, key, payload) {
  await mount(page, key, payload);
  await page.waitForSelector('.wow-roster', { timeout: 5000 });
}

const table = (page) => page.evaluate(() => {
  const t = document.querySelector('.wow-roster');
  if (!t) return null;
  return {
    heads: [...t.querySelectorAll('thead th')].map((h) => h.textContent.trim()),
    rows: [...t.querySelectorAll('tbody tr')].map((r) =>
      [...r.querySelectorAll('td')].map((d) => d.textContent.trim())),
    headline: (document.querySelector('.wow-headline') || {}).textContent,
    sub: (document.querySelector('.wow-sub') || {}).textContent,
    sammy: (document.querySelector('.sammy-modal img, .sammy-figure img, img[src*="ammy"]') || {}).getAttribute?.('src'),
  };
});

test.describe('Recruit Visit modal', () => {
  test('shows the visiting recruit with the walk-on columns plus Region', async ({ page }) => {
    await mountAndWait(page, 'recruit_visit_modal',
      { eligible: true, week: 22, recruit: player({ region: 'E' }) });
    const m = await table(page);
    expect(m.heads).toEqual(['Name', 'Pos', 'Yr', 'Ht', 'Wt', 'Rgn', ...ATTRS, 'RT']);
    const row = m.rows[0];
    expect(row[0]).toBe('Ellis Clemons');
    expect(row[1]).toBe('PF');
    expect(row[3]).toBe("6'6\"");
    expect(row[4]).toBe('210');
    expect(row[5]).toBe('E');                      // the one added column
    expect(row.length).toBe(6 + ATTRS.length + 1);
  });

  test('carries the copy verbatim', async ({ page }) => {
    await mountAndWait(page, 'recruit_visit_modal',
      { eligible: true, week: 21, recruit: player({ region: 'A' }) });
    const m = await table(page);
    expect(m.headline).toBe('Hey Coach, here is this week’s invite!');
    expect(m.sub).toBeUndefined();                 // one line, not the walk-on pair
  });

  test('the CTA dismisses to the locker room, it does not jump to Recruits', async ({ page }) => {
    await mountAndWait(page, 'recruit_visit_modal',
      { eligible: true, week: 21, recruit: player({ region: 'A' }) });
    const m = await page.evaluate(() => {
      const btn = document.querySelector('.sammy-modal-actions button, .sammy-modal-cta');
      return { label: btn ? btn.textContent.trim() : null };
    });
    // It used to read "Go To Recruiting" and click the Recruits tab — sending the
    // player somewhere they had not asked to go. This modal is news; the player is
    // already standing in the locker room.
    expect(m.label).toBe('Go To Locker Room');
  });

  test('pressing it closes the modal and leaves the tab alone', async ({ page }) => {
    await mountAndWait(page, 'recruit_visit_modal',
      { eligible: true, week: 21, recruit: player({ region: 'A' }) });
    await page.evaluate(() => {
      // The harness page has no FCC tabs, so a listener over whatever happens to exist
      // proves nothing — the old onCta looked up [data-tab="recruits-tab"] and silently
      // did nothing when absent. Plant the real target it used to click.
      window.__tabClicks = 0;
      const tab = document.createElement('button');
      tab.setAttribute('data-tab', 'recruits-tab');
      tab.addEventListener('click', () => { window.__tabClicks += 1; });
      document.body.appendChild(tab);
      document.querySelector('.sammy-modal-actions button, .sammy-modal-cta').click();
    });
    const m = await page.evaluate(() => ({
      open: document.querySelectorAll('.sammy-modal-backdrop.open').length,
      tabClicks: window.__tabClicks,
    }));
    expect(m.open).toBe(0);
    expect(m.tabClicks).toBe(0);
  });

  test('RT reads current/potential as letter grades', async ({ page }) => {
    await mountAndWait(page, 'recruit_visit_modal',
      { eligible: true, week: 22, recruit: player({ rt: 72, potential_rt: 88, region: 'E' }) });
    const m = await table(page);
    const rt = m.rows[0][m.rows[0].length - 1];
    expect(rt).toContain('/');
    expect(rt).toMatch(/^[A-F][+]{0,2}\/[A-F][+]{0,2}$/);
  });

  test('attributes render on the 0-10 scale', async ({ page }) => {
    await mountAndWait(page, 'recruit_visit_modal',
      { eligible: true, week: 22, recruit: player({ region: 'E' }) });
    const m = await table(page);
    const attrs = m.rows[0].slice(6, 6 + ATTRS.length).map(Number);
    for (const v of attrs) { expect(v).toBeGreaterThanOrEqual(0); expect(v).toBeLessThanOrEqual(10); }
  });

  test('no visit means no modal at all', async ({ page }) => {
    // Assert on the modal ROOT, not the table: a table missing because rendering threw
    // looks identical to the guard working, and only one of those is correct.
    for (const payload of [null, { eligible: false }, { eligible: true, recruit: null }]) {
      await mount(page, 'recruit_visit_modal', payload);
      await page.waitForTimeout(250);
      const m = await page.evaluate(() => ({
        backdrop: document.querySelectorAll('.sammy-modal-backdrop').length,
        modal: document.querySelectorAll('.sammy-modal').length,
      }));
      expect(m, JSON.stringify(payload)).toEqual({ backdrop: 0, modal: 0 });
    }
  });

  test('...and the control: a real visit DOES open the modal root', async ({ page }) => {
    await mountAndWait(page, 'recruit_visit_modal',
      { eligible: true, week: 22, recruit: player({ region: 'E' }) });
    const m = await page.evaluate(() => ({
      backdrop: document.querySelectorAll('.sammy-modal-backdrop').length,
      modal: document.querySelectorAll('.sammy-modal').length,
    }));
    expect(m).toEqual({ backdrop: 1, modal: 1 });
  });
});

test.describe('Walk-On Welcome now shows potential RT', () => {
  test('RT is the current/potential pair, not a single grade', async ({ page }) => {
    await mountAndWait(page, 'walk_on_welcome_modal',
      { eligible: true, season: 2, walk_ons: [player({ rt: 41, potential_rt: 63 })] });
    const m = await table(page);
    const rt = m.rows[0][m.rows[0].length - 1];
    expect(rt).toContain('/');
    expect(m.heads).toEqual(['Name', 'Pos', 'Yr', 'Ht', 'Wt', ...ATTRS, 'RT']);
    expect(m.heads).not.toContain('Rgn');          // region is the visit modal's alone
  });

  test('a walk-on with no potential still renders a single grade, not a broken pair', async ({ page }) => {
    await mountAndWait(page, 'walk_on_welcome_modal',
      { eligible: true, season: 2, walk_ons: [player({ rt: 41, potential_rt: null })] });
    const m = await table(page);
    const rt = m.rows[0][m.rows[0].length - 1];
    expect(rt).not.toContain('/');
    expect(rt).not.toBe('--');
  });
});
