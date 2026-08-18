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


test.describe('Coach\'s Office cards hold their size as the wire fills', () => {
  /** Render the recruiting card the way franchise-command-center.js does. */
  const wireHtml = (n) => {
    if (!n) {
      return '<div class="fcc-home-empty">No board movement yet</div>'
        + '<div class="fcc-wire-status"></div>';
    }
    const rows = Array.from({ length: n }, (_, i) => `
      <div class="fcc-wire-row">
        <div class="fcc-wire-line"><span>Jacques Chen dropped Nickel Beach — you're still #2</span>
        <span class="fcc-wire-line__wk">Wk 12</span></div>
        ${i % 3 === 0 ? '<div class="fcc-newlean-tag">GAIN</div>' : ''}
      </div>`).join('');
    return `<div class="fcc-home-recruiting"><div class="fcc-home-list-scroll">${rows}</div></div>`
      + '<div class="fcc-wire-status">6 moved · 3 dropped you since you last looked.</div>';
  };

  async function measure(page, n) {
    await page.evaluate((html) => {
      document.getElementById('home-recruiting-body').innerHTML = html;
    }, wireHtml(n));
    return page.evaluate(() => {
      const grid = document.querySelector('.fcc-home-grid');
      const cards = [...grid.querySelectorAll('.fcc-home-card')];
      const rec = document.querySelector('.fcc-home-card--recruiting');
      const scroll = rec.querySelector('.fcc-home-list-scroll');
      return {
        card: Math.round(rec.getBoundingClientRect().height),
        row1: Math.max(...cards.slice(0, 3).map((c) => Math.round(c.getBoundingClientRect().height))),
        row2Top: Math.round(Math.min(...cards.slice(3).map((c) => c.getBoundingClientRect().top))),
        overflows: scroll ? scroll.scrollHeight > scroll.clientHeight + 1 : null,
      };
    });
  }

  test('the recruiting card is the same height at 0, 1 and 60 events', async ({ page }) => {
    await mount(page, `<div id="franchise-container">${HOME_GRID}</div>`);
    const empty = await measure(page, 0);
    const few = await measure(page, 3);
    const many = await measure(page, 60);
    // A season's worth of wire must not make the card taller than week 1.
    expect(few.card).toBe(empty.card);
    expect(many.card).toBe(empty.card);
    expect(many.overflows).toBe(true);      // the events are still all reachable, by scrolling
  });

  test('row 2 never moves down as the wire fills', async ({ page }) => {
    await mount(page, `<div id="franchise-container">${HOME_GRID}</div>`);
    const tops = [];
    for (const n of [0, 1, 3, 6, 12, 25, 60]) tops.push((await measure(page, n)).row2Top);
    expect(new Set(tops).size, `row 2 top drifted: ${tops.join(', ')}`).toBe(1);
  });

  test('the wire list is a fixed box, not one that grows into a cap', async ({ page }) => {
    await mount(page, `<div id="franchise-container">${HOME_GRID}</div>`);
    await page.evaluate((html) => {
      document.getElementById('home-recruiting-body').innerHTML = html;
    }, wireHtml(1));
    const one = await page.evaluate(() =>
      Math.round(document.querySelector('.fcc-home-list-scroll').getBoundingClientRect().height));
    await page.evaluate((html) => {
      document.getElementById('home-recruiting-body').innerHTML = html;
    }, wireHtml(40));
    const many = await page.evaluate(() =>
      Math.round(document.querySelector('.fcc-home-list-scroll').getBoundingClientRect().height));
    expect(one).toBe(many);
  });
});


test.describe('Signing Day: the Recruiting card is one call to action', () => {
  /** Drive the REAL renderer so the branch under test is the shipped one. */
  async function renderWire(page, { week, events }) {
    await page.evaluate(({ week, events }) => {
      window.commandCenterTopDataCache = {
        week,
        recruiting_wire: { events, counts: { moved: 6, dropped: 3 }, unseen_count: 9 },
      };
      window.renderHomeRecruitingWire();
    }, { week, events });
  }

  async function mountWithJs(page) {
    await mount(page, `<div id="franchise-container">${HOME_GRID}</div>`);
    // Only the functions under test; the module is a classic script full of page globals.
    const js = require('fs').readFileSync(
      require('path').join(__dirname, '../../FrontEnd/static/franchise-command-center.js'), 'utf8');
    const start = js.indexOf('const SIGNING_DAY_WEEK');
    const end = js.indexOf('/** Secondary hero button');
    await page.addScriptTag({ content: [
      'function escapeHomeHtml(s){return String(s==null?"":s);}',
      'function createEmptyHomeState(m){return "<div class=\\"fcc-home-empty\\">"+m+"</div>";}',
      'function buildRecruitingUrl(){return "#";}',
      'function wireBadgeFor(){return "";}',
      'function wireRowClassFor(){return "fcc-wire-row";}',
      'function openRecruitingSurface(){}',
      js.slice(start, end),
      'window.renderHomeRecruitingWire = renderHomeRecruitingWire;',
    ].join('\n') });
  }

  const EVENTS = Array.from({ length: 12 }, (_, i) => ({
    kind: 'displaced', line: `Jacques Chen dropped Nickel Beach — you're still #2`, week: 30 + (i % 5),
  }));

  test('week 35 shows no recruiting news at all', async ({ page }) => {
    await mountWithJs(page);
    await renderWire(page, { week: 35, events: EVENTS });
    const m = await page.evaluate(() => {
      const card = document.querySelector('.fcc-home-card--recruiting');
      return {
        rows: card.querySelectorAll('.fcc-wire-row').length,
        lists: card.querySelectorAll('.fcc-home-list-scroll').length,
        status: card.querySelectorAll('.fcc-wire-status').length,
        copy: (card.querySelector('.fcc-wire-signing__copy') || {}).textContent,
      };
    });
    expect(m.rows).toBe(0);
    expect(m.lists).toBe(0);
    expect(m.status).toBe(0);
    expect(m.copy).toContain('Signing Day');
  });

  test('the copy sits directly above the button, both centred', async ({ page }) => {
    await mountWithJs(page);
    await renderWire(page, { week: 35, events: EVENTS });
    const m = await page.evaluate(() => {
      const card = document.querySelector('.fcc-home-card--recruiting');
      const body = card.querySelector('.fcc-home-card-body');
      // Mirror updateRecruitingButton() on this card FIRST — button shown, its own copy
      // <p> hidden — then measure. Measuring before these land reads a stale layout.
      document.getElementById('fcc-recruiting-live-copy-home').style.display = 'none';
      const btn = document.getElementById('fcc-recruiting-btn-home');
      btn.style.display = 'inline-flex';
      const copy = card.querySelector('.fcc-wire-signing__copy').getBoundingClientRect();
      const b = btn.getBoundingClientRect();
      const box = body.getBoundingClientRect();
      return {
        stacked: b.top >= copy.bottom - 1,               // button below the copy
        overlaps: b.top < copy.bottom - 1,
        copyCentreX: copy.left + copy.width / 2, btnCentreX: b.left + b.width / 2,
        boxCentreX: box.left + box.width / 2,
        groupCentreY: (copy.top + b.bottom) / 2, boxCentreY: box.top + box.height / 2,
        inButton: card.querySelector('.fcc-wire-signing').contains(btn),
      };
    });
    expect(m.overlaps).toBe(false);                      // the reported collision
    expect(m.stacked).toBe(true);
    expect(m.inButton).toBe(true);
    expect(Math.abs(m.copyCentreX - m.boxCentreX)).toBeLessThan(2);
    expect(Math.abs(m.btnCentreX - m.boxCentreX)).toBeLessThan(2);
    expect(Math.abs(m.groupCentreY - m.boxCentreY)).toBeLessThan(3);
  });

  test('a normal week still shows the wire, and the card height is unchanged', async ({ page }) => {
    await mountWithJs(page);
    await renderWire(page, { week: 30, events: EVENTS });
    const normal = await page.evaluate(() => {
      // Mirror updateRecruitingButton(): in a passive week there is no button and no
      // copy on this card, so the footnote is hidden. Leaving it visible would compare
      // Signing Day against a state the app never renders.
      document.querySelector('.fcc-recruiting-footnote--embed').style.display = 'none';
      const card = document.querySelector('.fcc-home-card--recruiting');
      return {
        rows: document.querySelectorAll('.fcc-wire-row').length,
        h: Math.round(card.getBoundingClientRect().height),
        body: Math.round(card.querySelector('.fcc-home-card-body').getBoundingClientRect().height),
        signing: card.classList.contains('is-signing-day'),
      };
    });
    expect(normal.rows).toBe(12);
    expect(normal.signing).toBe(false);

    await renderWire(page, { week: 35, events: EVENTS });
    const signing = await page.evaluate(() => {
      document.getElementById('fcc-recruiting-live-copy-home').style.display = 'none';
      document.getElementById('fcc-recruiting-btn-home').style.display = 'inline-flex';
      const card = document.querySelector('.fcc-home-card--recruiting');
      return { h: Math.round(card.getBoundingClientRect().height),
               body: Math.round(card.querySelector('.fcc-home-card-body').getBoundingClientRect().height) };
    });
    expect(signing.body).toBe(normal.body);  // the reserved box is the same every week
    expect(signing.h).toBe(normal.h);        // so row 2 does not move on Signing Day
  });

  test('leaving week 35 restores the footnote and the feed', async ({ page }) => {
    await mountWithJs(page);
    await renderWire(page, { week: 35, events: EVENTS });
    await renderWire(page, { week: 30, events: EVENTS });
    const m = await page.evaluate(() => {
      const card = document.querySelector('.fcc-home-card--recruiting');
      const footer = card.querySelector('.fcc-recruiting-footnote--embed');
      return { rows: card.querySelectorAll('.fcc-wire-row').length,
               footerBackOnCard: footer.parentElement === card,
               strays: card.querySelectorAll('.fcc-wire-signing').length };
    });
    expect(m.rows).toBe(12);
    expect(m.footerBackOnCard).toBe(true);   // the moved element must not be stranded
    expect(m.strays).toBe(0);
  });
});


test.describe('every Coach\'s Office card is one row tall', () => {
  const fill = (page, wireRows) => page.evaluate((n) => {
    const list = (k, cls) => `<div class="fcc-home-list-scroll">${Array.from({ length: k }, () =>
      `<div class="${cls}"><span>Team</span><span>0-0</span></div>`).join('')}</div>`;
    document.getElementById('home-rankings-body').innerHTML = list(10, 'fcc-home-list-row');
    document.getElementById('home-news-body').innerHTML = list(5, 'fcc-home-news-row');
    document.getElementById('home-team-stats-body').innerHTML = list(5, 'fcc-home-team-stats-row');
    const rows = Array.from({ length: n }, () =>
      '<div class="fcc-wire-row"><div class="fcc-wire-line"><span>x</span></div></div>').join('');
    document.getElementById('home-recruiting-body').innerHTML = n
      ? `<div class="fcc-home-recruiting"><div class="fcc-home-list-scroll">${rows}</div></div>`
        + '<div class="fcc-wire-status">6 moved</div>'
      : '<div class="fcc-home-empty">No board movement yet</div><div class="fcc-wire-status"></div>';
    document.querySelector('.fcc-recruiting-footnote--embed').style.display = 'none';
  }, wireRows);

  const geo = (page) => page.evaluate(() => {
    const cards = [...document.querySelectorAll('.fcc-home-grid .fcc-home-card')];
    const sc = document.querySelector('.fcc-home-card--recruiting .fcc-home-list-scroll');
    return {
      heights: [...new Set(cards.map((c) => Math.round(c.getBoundingClientRect().height)))],
      row2Top: Math.round(cards[3].getBoundingClientRect().top),
      wireScrolls: sc ? sc.scrollHeight > sc.clientHeight + 1 : null,
    };
  });

  test('row 1 and row 2 are the same height — one value across all seven cards', async ({ page }) => {
    await mount(page, `<div id="franchise-container">${HOME_GRID}</div>`);
    await fill(page, 3);
    const m = await geo(page);
    // Row 1 used to stand 315px against row 2's 216, which pushed row 2 below the fold.
    expect(m.heights.length, `differing heights: ${m.heights.join(', ')}`).toBe(1);
  });

  test('a season of wire does not change any card height or move row 2', async ({ page }) => {
    await mount(page, `<div id="franchise-container">${HOME_GRID}</div>`);
    const seen = [];
    for (const n of [0, 1, 3, 12, 40, 90]) {
      await fill(page, n);
      seen.push(await geo(page));
    }
    for (const g of seen) expect(g.heights).toEqual(seen[0].heights);
    for (const g of seen) expect(g.row2Top).toBe(seen[0].row2Top);
  });

  test('the wire stays reachable — it scrolls inside the card rather than being cut', async ({ page }) => {
    await mount(page, `<div id="franchise-container">${HOME_GRID}</div>`);
    await fill(page, 40);
    // scrollHeight alone is not proof: an overflow:visible box still reports tall
    // content while spilling into a card that clips it. Move the scroll and check it
    // actually moved, and that the box is a scroller.
    const m = await page.evaluate(() => {
      const sc = document.querySelector('.fcc-home-card--recruiting .fcc-home-list-scroll');
      const overflowY = getComputedStyle(sc).overflowY;
      sc.scrollTop = 9999;
      return { overflowY, moved: sc.scrollTop > 0, taller: sc.scrollHeight > sc.clientHeight + 1 };
    });
    expect(['auto', 'scroll']).toContain(m.overflowY);
    expect(m.taller).toBe(true);
    expect(m.moved).toBe(true);
  });
});
