// @ts-check
/**
 * FCC recruiting layout — measured, not eyeballed.
 *
 * Extracts the real #franchise-container markup from franchise-command-center.html
 * and loads the real franchise-command-center.css, so the geometry under test is the
 * shipped geometry. No server, no season, no login.
 *
 * Run: npx playwright test tests/e2e/fcc-recruiting-layout.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const STATIC_DIR = path.join(__dirname, '../../FrontEnd/static');
const HTML = fs.readFileSync(path.join(STATIC_DIR, 'franchise-command-center.html'), 'utf8');
const CSS = fs.readFileSync(path.join(STATIC_DIR, 'franchise-command-center.css'), 'utf8');
// The shipped page is html.gob with gob-tokens.css, and the sheet reads tokens (--badge).
const TOKENS = fs.readFileSync(path.join(STATIC_DIR, 'css/gob-tokens.css'), 'utf8');

/** Pull one balanced element out of the real page by id, so the test can't drift from it. */
function extractById(html, id) {
  const anchor = html.indexOf(`id="${id}"`);
  if (anchor === -1) throw new Error(`#${id} not found in franchise-command-center.html`);
  const open = html.lastIndexOf('<', anchor);
  const tag = html.slice(open + 1).match(/^[a-zA-Z0-9-]+/)[0];
  let i = open, depth = 0;
  const openRe = new RegExp(`<${tag}[\\s>]`, 'g');
  const closeRe = new RegExp(`</${tag}>`, 'g');
  while (i < html.length) {
    openRe.lastIndex = i; closeRe.lastIndex = i;
    const nextOpen = openRe.exec(html);
    const nextClose = closeRe.exec(html);
    if (!nextClose) throw new Error(`unbalanced <${tag}>`);
    if (nextOpen && nextOpen.index < nextClose.index) { depth++; i = nextOpen.index + 1; }
    else {
      depth--; i = nextClose.index + 1;
      if (depth === 0) return html.slice(open, nextClose.index + `</${tag}>`.length);
    }
  }
  throw new Error(`could not close <${tag}>`);
}

const HERO_GROUP = (() => {
  const open = HTML.indexOf('<div class="hero-buttons-group">');
  if (open === -1) throw new Error('hero-buttons-group not found');
  const close = HTML.indexOf('</div>', HTML.indexOf('id="fcc-edit-recruiting"'));
  if (close === -1) throw new Error('hero-buttons-group not closed');
  return HTML.slice(open, close + 6);
})();

const HOME_GRID = extractById(HTML, 'home-tab');

async function mount(page, innerHtml, opts = {}) {
  await page.setViewportSize({ width: opts.width || 1440, height: 900 });
  await page.setContent(`
    <script>document.documentElement.classList.add('gob');</script>
    <style>${TOKENS}</style>
    <style>${CSS}</style>
    <style>
      body { margin: 0; background: #0b0d14; }
      /* The real page constrains #franchise-container; mirror that, nothing more. */
      #franchise-container { width: ${opts.width || 1440}px; }
      .tab-content { display: none; }
      .tab-content.active { display: block; }
    </style>
    <div id="franchise-container">${innerHtml}</div>
  `);
}

// RETIRED: the 'hero buttons' block.
//
// It measured the amber #fcc-recruiting-secondary button — width parity with #play-now,
// its shared right edge, the two-line label, the is-dead state, and the amber-not-green
// colour law. That button was REMOVED: every week's recruiting news already lives in the
// Coach's Office recruiting card, and a second notice under the green action bar was
// repeating it. The only thing left below #play-now is week 35's ghost
// "Edit Recruiting Orders", whose size and colour are measured in
// week35-signing-pair.spec.js against this same extracted markup.

test.describe('Coach\'s Office grid', () => {
  test.beforeEach(async ({ page }) => {
    await mount(page, HOME_GRID);
  });

  test('home tab is the office grid, not the old card row', async ({ page }) => {
    const info = await page.evaluate(() => ({
      columns: document.querySelectorAll('#home-tab .office-col').length,
      oldCards: document.querySelectorAll('#home-tab .fcc-home-card').length,
      title: document.querySelector('#home-tab h1') === null,
    }));
    expect(info.columns).toBe(3);
    expect(info.oldCards).toBe(0);
    expect(info.title).toBe(true);
  });
});

// RETIRED: leftover Office wire-card geometry.
// Those rows lived on the remapped #recruits-tab / old home recruiting card.
// Live Office is GOBOffice; the FCC.css rules for .fcc-newlean-* / .fcc-drop-*
// were peeled with the leftover HTML/JS. Tab-badge coverage below still runs.

test.describe('tab badge', () => {
  test('.inbox-badge renders on the Recruiting tab and the tab is renamed', async ({ page }) => {
    const start = HTML.indexOf('<div class="tab-buttons">');
    const end = HTML.indexOf('</div>', HTML.indexOf('data-tab="news-view"'));
    const tabBar = HTML.slice(start, end + 6);
    await mount(page, `<div id="tournament-tabs">${tabBar}</div>`);
    const result = await page.evaluate(() => {
      const tab = document.querySelector('[data-tab="recruits-tab"]');
      const label = tab.textContent.trim();
      tab.style.position = 'relative';
      const badge = document.createElement('span');
      badge.className = 'inbox-badge';
      tab.appendChild(badge);
      const b = badge.getBoundingClientRect();
      const t = tab.getBoundingClientRect();
      return {
        label,
        w: b.width, h: b.height,
        insideTab: b.right <= t.right + 1 && b.top >= t.top - 1,
        bg: getComputedStyle(badge).backgroundColor,
      };
    });
    expect(result.label).toBe('Recruiting');
    expect(result.w).toBe(8);
    expect(result.h).toBe(8);
    expect(result.insideTab).toBe(true);
    // Ruling 2026-10-01 (#7): the presence dot is neutral, not orange and not green.
    expect(result.bg).toBe('rgb(255, 255, 255)');
  });
});

// The home-tab recruiting card, its footnote, and the seven-card grid are gone.
// The Office renders office_digest. Those geometry checks are retired with the card.
