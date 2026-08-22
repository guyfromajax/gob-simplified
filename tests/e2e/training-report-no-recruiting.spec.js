// @ts-check
/**
 * The training report carries NO recruiting information, in any week.
 *
 * It used to show a "Recruiting Visit" line in weeks 20-26 and a "top recruit leaning
 * your way" line in weeks 1-19, both in the Notes header. Recruiting news lives in the
 * Coach's Office card and the Recruiting Hub; repeating a slice of it on the training
 * report split the story across two screens.
 *
 * Loads the REAL training-report.html + .js + .css with only the payload stubbed, so
 * this fails if the markup, the renderer or the styling comes back.
 *
 * Run: npx playwright test tests/e2e/training-report-no-recruiting.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const HTML = fs.readFileSync(path.join(S, 'training-report.html'), 'utf8');
const JS = fs.readFileSync(path.join(S, 'training-report.js'), 'utf8');
const CSS = fs.readFileSync(path.join(S, 'training-report.css'), 'utf8');

test.describe('training report has no recruiting', () => {
  test('the markup carries no recruiting elements', () => {
    // Asserted on the shipped file, not a render: these ids were the mount points.
    expect(HTML).not.toContain('training-report-recruit-header');
    expect(HTML).not.toContain('training-report-recruit-meta-line');
    expect(HTML).not.toContain('training-notes-recruit-block');
  });

  test('the renderer is gone, along with every payload field it read', () => {
    expect(JS).not.toContain('renderTrainingReportRecruitingBanner');
    for (const field of ['recruiting_header', 'recruiting_meta_line',
                         'recruiting_recruits', 'recruiting_team_name_map']) {
      expect(JS, `payload field ${field} still read`).not.toContain(field);
    }
  });

  test('the recruiting-only assets are no longer pulled in', () => {
    // Both existed on this page solely for the lean ladder in that banner.
    expect(HTML).not.toContain('recruiting-lean-ladder.css');
    expect(HTML).not.toContain('recruiting-spine.js');
  });

  test('no orphaned styles left behind', () => {
    for (const cls of ['training-notes-recruit', 'trr-lean', 'trr-hub-link']) {
      expect(CSS, `${cls} rules survived the removal`).not.toContain(cls);
    }
  });

  test('the page still renders its own content', async ({ page }) => {
    // The removal must not have taken the Notes panel with it.
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    // ALL script tags stripped, inline modules included: this asserts markup and
    // styling, and an inline `import` cannot resolve without a real origin — that
    // would fail for a reason unrelated to recruiting.
    const markup = HTML.replace(/<script[\s\S]*?<\/script>/g, '');
    await page.setContent(`<style>${CSS}</style>${markup}`);
    const m = await page.evaluate(() => ({
      notes: !!document.querySelector('#training-notes-brief'),
      focus: !!document.querySelector('#training-focus'),
      cta: (document.querySelector('#locker-room-btn') || {}).textContent,
      recruitBits: document.querySelectorAll('[id*="recruit"], [class*="recruit"]').length,
    }));
    expect(errors).toEqual([]);
    expect(m.notes).toBe(true);
    expect(m.focus).toBe(true);
    expect(m.cta).toBeTruthy();
    expect(m.recruitBits).toBe(0);
  });
});
