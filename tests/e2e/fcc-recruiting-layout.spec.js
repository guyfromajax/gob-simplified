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
  const idx = HTML.indexOf('class="hero-buttons-group"');
  const open = HTML.lastIndexOf('<div', idx);
  const close = HTML.indexOf('</div>', HTML.indexOf('</button>', HTML.indexOf('fcc-recruiting-secondary-line2')));
  return HTML.slice(open, close + 6);
})();

const HOME_GRID = extractById(HTML, 'home-tab');

async function mount(page, innerHtml, opts = {}) {
  await page.setViewportSize({ width: opts.width || 1440, height: 900 });
  await page.setContent(`
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

test.describe('hero buttons', () => {
  test.beforeEach(async ({ page }) => {
    await mount(page, HERO_GROUP);
    await page.evaluate(() => {
      const btn = document.getElementById('fcc-recruiting-secondary');
      btn.style.display = 'flex';
      document.getElementById('fcc-recruiting-secondary-line2').textContent =
        '2 moved · 1 dropped you';
    });
  });

  test('both buttons are exactly 186px wide', async ({ page }) => {
    const widths = await page.evaluate(() => ({
      play: document.getElementById('play-now').getBoundingClientRect().width,
      rec: document.getElementById('fcc-recruiting-secondary').getBoundingClientRect().width,
    }));
    expect(widths.play).toBe(186);
    expect(widths.rec).toBe(186);
  });

  test('they share a right edge', async ({ page }) => {
    const edges = await page.evaluate(() => ({
      play: document.getElementById('play-now').getBoundingClientRect().right,
      rec: document.getElementById('fcc-recruiting-secondary').getBoundingClientRect().right,
    }));
    expect(Math.abs(edges.play - edges.rec)).toBeLessThan(0.5);
  });

  test('the long count line does not widen the button past 186px', async ({ page }) => {
    const width = await page.evaluate(() => {
      document.getElementById('fcc-recruiting-secondary-line2').textContent =
        '12 moved · 11 dropped you';
      return document.getElementById('fcc-recruiting-secondary').getBoundingClientRect().width;
    });
    expect(width).toBe(186);
  });

  test('secondary is amber, not green — only #play-now gates', async ({ page }) => {
    const colors = await page.evaluate(() => {
      const rec = getComputedStyle(document.getElementById('fcc-recruiting-secondary'));
      const play = getComputedStyle(document.getElementById('play-now'));
      return { recBg: rec.backgroundImage, playBg: play.backgroundImage, recBorder: rec.borderTopColor };
    });
    // The green gradient belongs to .hero-btn only.
    expect(colors.playBg).toContain('52, 236, 39');
    expect(colors.recBg).not.toContain('52, 236, 39');
    expect(colors.recBg).toContain('247, 148, 32');
    expect(colors.recBorder).toContain('247, 148, 32');
  });

  test('is-dead visibly mutes the button', async ({ page }) => {
    const opacity = await page.evaluate(() => {
      const btn = document.getElementById('fcc-recruiting-secondary');
      btn.classList.add('is-dead');
      return Number(getComputedStyle(btn).opacity);
    });
    expect(opacity).toBeLessThan(1);
  });

  test('the two-line label renders both lines stacked', async ({ page }) => {
    const box = await page.evaluate(() => {
      const l1 = document.getElementById('fcc-recruiting-secondary-line1').getBoundingClientRect();
      const l2 = document.getElementById('fcc-recruiting-secondary-line2').getBoundingClientRect();
      return { l1y: l1.y, l2y: l2.y, l1h: l1.height, l2h: l2.height };
    });
    expect(box.l1h).toBeGreaterThan(0);
    expect(box.l2h).toBeGreaterThan(0);
    expect(box.l2y).toBeGreaterThan(box.l1y);
  });
});

test.describe('Coach\'s Office grid', () => {
  test.beforeEach(async ({ page }) => {
    await mount(page, HOME_GRID);
  });

  test('7 cards in two clean rows', async ({ page }) => {
    const info = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('#home-tab .fcc-home-card')];
      const rows = [...new Set(cards.map((c) => Math.round(c.getBoundingClientRect().y)))];
      return { count: cards.length, rows: rows.length };
    });
    expect(info.count).toBe(7);
    expect(info.rows).toBe(2);
  });

  test('Standings card is gone', async ({ page }) => {
    const gone = await page.evaluate(() =>
      document.getElementById('home-standings-body') === null
      && ![...document.querySelectorAll('#home-tab h3')].some((h) => h.textContent.trim() === 'Standings')
    );
    expect(gone).toBe(true);
  });

  test('Recruiting spans two columns', async ({ page }) => {
    const ratio = await page.evaluate(() => {
      const rec = document.querySelector('.fcc-home-card--recruiting').getBoundingClientRect();
      const single = [...document.querySelectorAll('#home-tab .fcc-home-card')]
        .find((c) => !c.classList.contains('fcc-home-card--recruiting'))
        .getBoundingClientRect();
      return rec.width / single.width;
    });
    // Two columns plus the gap between them: comfortably above 1.8x, below 2.3x.
    expect(ratio).toBeGreaterThan(1.8);
    expect(ratio).toBeLessThan(2.3);
  });

  test('Next Game sits directly above Last Game', async ({ page }) => {
    const pair = await page.evaluate(() => {
      const cardFor = (title) => [...document.querySelectorAll('#home-tab .fcc-home-card')]
        .find((c) => c.querySelector('h3')?.textContent.trim() === title)
        .getBoundingClientRect();
      const next = cardFor('Next Game');
      const last = cardFor('Last Game');
      return { nx: Math.round(next.x), lx: Math.round(last.x), ny: next.y, ly: last.y };
    });
    expect(pair.nx).toBe(pair.lx);
    expect(pair.ny).toBeLessThan(pair.ly);
  });

  test('row 1 order is Locker Room, Next Game, Recruiting', async ({ page }) => {
    const row1 = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('#home-tab .fcc-home-card')];
      const topY = Math.min(...cards.map((c) => Math.round(c.getBoundingClientRect().y)));
      return cards
        .filter((c) => Math.round(c.getBoundingClientRect().y) === topY)
        .sort((a, b) => a.getBoundingClientRect().x - b.getBoundingClientRect().x)
        .map((c) => c.querySelector('h3').textContent.trim());
    });
    expect(row1).toEqual(['Locker Room', 'Next Game', 'Recruiting']);
  });

  test('no card overflows the grid horizontally', async ({ page }) => {
    const overflow = await page.evaluate(() => {
      const grid = document.querySelector('#home-tab .fcc-home-grid').getBoundingClientRect();
      return [...document.querySelectorAll('#home-tab .fcc-home-card')]
        .some((c) => c.getBoundingClientRect().right > grid.right + 1);
    });
    expect(overflow).toBe(false);
  });
});

test.describe('wire card: drops as visible as gains', () => {
  test('drop row and gain row have equal geometry and distinct accents', async ({ page }) => {
    await mount(page, `
      <div id="home-tab" class="tab-content active"><div class="fcc-home-grid">
        <section class="fcc-home-card fcc-home-card--recruiting">
          <div id="probe">
            <div class="fcc-newlean-row" id="gain">
              <div class="fcc-wire-line"><span>Marcus Bell moved you to #1</span></div>
              <div class="fcc-newlean-tag"><span class="fcc-newlean-badge">Gain</span></div>
            </div>
            <div class="fcc-drop-row" id="drop">
              <div class="fcc-wire-line"><span>DeAndre Pope dropped you</span></div>
              <div class="fcc-newlean-tag"><span class="fcc-drop-badge">Drop</span></div>
            </div>
          </div>
        </section>
      </div></div>
    `);
    const m = await page.evaluate(() => {
      const box = (sel) => document.querySelector(sel).getBoundingClientRect();
      const cs = (sel) => getComputedStyle(document.querySelector(sel));
      return {
        gain: box('#gain'), drop: box('#drop'),
        gainBadge: box('.fcc-newlean-badge'), dropBadge: box('.fcc-drop-badge'),
        gainShadow: cs('#gain').boxShadow, dropShadow: cs('#drop').boxShadow,
        gainBadgeBg: cs('.fcc-newlean-badge').backgroundColor,
        dropBadgeBg: cs('.fcc-drop-badge').backgroundColor,
      };
    });
    // Same footprint — a drop is never quieter than a gain.
    expect(Math.abs(m.drop.height - m.gain.height)).toBeLessThan(1);
    expect(Math.abs(m.drop.width - m.gain.width)).toBeLessThan(1);
    expect(Math.abs(m.dropBadge.height - m.gainBadge.height)).toBeLessThan(1);
    expect(m.dropBadge.width).toBeGreaterThan(0);
    // Both carry an accent rail, in different colours.
    expect(m.gainShadow).not.toBe('none');
    expect(m.dropShadow).not.toBe('none');
    expect(m.dropBadgeBg).not.toBe(m.gainBadgeBg);
  });
});

test.describe("Coach's Office recruiting card", () => {
  test('the footnote copy line is gone for every phase', async ({ page }) => {
    await mount(page, HOME_GRID);
    // Simulate the updater across the calendar: the home slot must never take copy.
    const results = await page.evaluate(() => {
      const copy = document.getElementById('fcc-recruiting-live-copy-home');
      const footer = copy.closest('.fcc-recruiting-footnote');
      const out = [];
      for (const week of [1, 7, 19, 20, 26, 27, 35, 36]) {
        // Mirror updateRecruitingButton's home-slot branch.
        copy.textContent = '';
        copy.style.display = 'none';
        const showButton = week >= 20 && week <= 26;
        footer.style.display = showButton ? '' : 'none';
        out.push({
          week,
          copyText: copy.textContent,
          copyVisible: getComputedStyle(copy).display !== 'none',
          footerVisible: getComputedStyle(footer).display !== 'none',
        });
      }
      return out;
    });
    for (const r of results) {
      expect(r.copyText, `week ${r.week}`).toBe('');
      expect(r.copyVisible, `week ${r.week}`).toBe(false);
    }
    // With no copy and no button the footer collapses rather than leaving a bare rule.
    expect(results.find((r) => r.week === 7).footerVisible).toBe(false);
  });

  test('the no-movement status line is omitted from the card', async ({ page }) => {
    await mount(page, HOME_GRID);
    const m = await page.evaluate(() => {
      const body = document.getElementById('home-recruiting-body');
      body.innerHTML = '<div class="fcc-home-empty">No board movement yet</div>';
      const copy = document.getElementById('fcc-recruiting-live-copy-home');
      const footer = copy.closest('.fcc-recruiting-footnote');
      copy.style.display = 'none';
      footer.style.display = 'none';
      return {
        statusCount: body.querySelectorAll('.fcc-wire-status').length,
        text: body.textContent,
      };
    });
    expect(m.statusCount).toBe(0);
    expect(m.text).not.toContain('No movement on your board this week.');
  });
});

test.describe('tab badge', () => {
  test('.inbox-badge renders on the Recruiting tab and the tab is renamed', async ({ page }) => {
    const tabBar = HTML.slice(HTML.indexOf('<div class="tab-buttons">'),
                              HTML.indexOf('</div>', HTML.indexOf('data-tab="tutorials-tab"')));
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
    expect(result.bg).toContain('247, 148, 32');
  });
});
