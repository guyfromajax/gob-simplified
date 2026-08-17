// @ts-check
/**
 * Attribute tiles — shared builder, shared hover, four surfaces.
 *
 * In scope: Recruits screen (Hub pool), FCC Roster tab, FCC Recruits tab,
 * team-roster-view.html. Everything else that shows attributes is deliberately
 * untouched, and the last describe block guards that.
 *
 * Run: npx playwright test tests/e2e/attr-tiles.spec.js --project=chromium
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');
const TILES_JS = read('js/shared/attrTiles.js');
const TOOLTIP_JS = read('js/shared/attributeTooltips.js');
const TILES_CSS = read('css/attr-tiles.css');

const ATTRS = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT'];

/** Raw (0-100+) attributes, so the builder does its own scaling. */
function rawAttrs(values) {
  const out = {};
  ATTRS.forEach((k, i) => { out[k] = values[i] * 10; });
  return out;
}

async function mount(page, attrs) {
  await page.setViewportSize({ width: 1200, height: 700 });
  await page.setContent(`<style>${TILES_CSS}</style><body style="margin:0;background:#0b0d14">
    <table><thead><tr><th class="attr-tiles-head">Attributes</th></tr></thead>
    <tbody><tr id="row"></tr></tbody></table></body>`);
  await page.addScriptTag({ content: TILES_JS });
  await page.addScriptTag({ content: TOOLTIP_JS });
  await page.evaluate((a) => {
    document.getElementById('row').innerHTML =
      window.GOB_AttrTiles.tilesCellHtml(a);
    window.initAttributeTooltips(document, ['.attr-tile']);
  }, attrs);
}

test.describe('builder', () => {
  test('renders 12 tiles in roster column order', async ({ page }) => {
    await mount(page, rawAttrs([7, 16, 4, 8, 6, 5, 5, 6, 4, 6, 5, 5]));
    const keys = await page.evaluate(() =>
      [...document.querySelectorAll('.attr-tile')].map((t) => t.dataset.attr));
    expect(keys).toEqual(['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT']);
  });

  test('values render on the 0-10 scale', async ({ page }) => {
    await mount(page, rawAttrs([7, 16, 4, 8, 6, 5, 5, 6, 4, 6, 5, 5]));
    const vals = await page.evaluate(() =>
      [...document.querySelectorAll('.attr-tile s')].map((s) => s.textContent));
    expect(vals).toEqual(['7', '16', '4', '8', '6', '5', '5', '6', '4', '6', '5', '5']);
  });

  test('prefers the anchor value', async ({ page }) => {
    await mount(page, { SC: 50, anchor_SC: 90 });
    const v = await page.evaluate(() =>
      document.querySelector('.attr-tile[data-attr="SC"] s').textContent);
    expect(v).toBe('9');
  });

  test('a missing attribute renders -- rather than 0', async ({ page }) => {
    await mount(page, { SC: 70 });
    const m = await page.evaluate(() => ({
      sc: document.querySelector('.attr-tile[data-attr="SC"] s').textContent,
      rb: document.querySelector('.attr-tile[data-attr="RB"] s').textContent,
      rbTip: document.querySelector('.attr-tile[data-attr="RB"]').dataset.tooltip,
    }));
    expect(m.sc).toBe('7');
    expect(m.rb).toBe('--');
    expect(m.rbTip).toBe('Rebounding: --');
  });
});

test.describe('hover copy', () => {
  test('shows the full attribute name and the 10-scale value', async ({ page }) => {
    await mount(page, rawAttrs([7, 16, 4, 8, 1, 5, 6, 6, 4, 6, 5, 5]));
    const tips = await page.evaluate(() =>
      Object.fromEntries([...document.querySelectorAll('.attr-tile')]
        .map((t) => [t.dataset.attr, t.dataset.tooltip])));
    expect(tips.RB).toBe('Rebounding: 6');
    expect(tips.PS).toBe('Passing: 1');
    expect(tips.SH).toBe('Shooting: 16');
    expect(tips.IQ).toBe('Basketball IQ: 5');
    expect(tips.ND).toBe('Endurance: 6');
    expect(tips.FT).toBe('Free Throws: 5');
  });

  test('every one of the 12 gets a name, not an abbreviation', async ({ page }) => {
    await mount(page, rawAttrs(ATTRS.map(() => 5)));
    const tips = await page.evaluate(() =>
      [...document.querySelectorAll('.attr-tile')].map((t) => t.dataset.tooltip));
    for (const [i, tip] of tips.entries()) {
      expect(tip, ATTRS[i]).toMatch(/^[A-Z][A-Za-z ]+: 5$/);
      expect(tip.split(':')[0].length, ATTRS[i]).toBeGreaterThan(2);
    }
  });

  test('hovering a tile shows the bubble with that copy', async ({ page }) => {
    await mount(page, rawAttrs([7, 16, 4, 8, 6, 5, 6, 6, 4, 6, 5, 5]));
    await page.hover('.attr-tile[data-attr="RB"]');
    const bubble = await page.evaluate(() => {
      const b = document.getElementById('attribute-tooltip-bubble');
      return { text: b && b.textContent, visible: b && b.style.visibility };
    });
    expect(bubble.text).toBe('Rebounding: 6');
    expect(bubble.visible).toBe('visible');
  });

  test('the tile advertises itself as hoverable', async ({ page }) => {
    await mount(page, rawAttrs(ATTRS.map(() => 5)));
    const cursor = await page.evaluate(() =>
      getComputedStyle(document.querySelector('.attr-tile')).cursor);
    expect(cursor).toBe('help');
  });
});

test.describe('tiers', () => {
  test('10+ is the brand blue, 7-9 green, <=3 red, rest neutral', async ({ page }) => {
    await mount(page, rawAttrs([10, 16, 3, 1, 7, 9, 5, 6, 4, 2, 8, 5]));
    const m = await page.evaluate(() =>
      [...document.querySelectorAll('.attr-tile')].map((t) => ({
        v: Number(t.querySelector('s').textContent),
        cls: t.className,
        color: getComputedStyle(t.querySelector('s')).color,
      })));
    const BLUE = 'rgb(74, 144, 217)';
    for (const t of m) {
      if (t.v >= 10) { expect(t.cls, `${t.v}`).toContain('is-elite'); expect(t.color).toBe(BLUE); }
      else if (t.v >= 7) { expect(t.cls, `${t.v}`).toContain('is-hi'); expect(t.color).not.toBe(BLUE); }
      else if (t.v <= 3) { expect(t.cls, `${t.v}`).toContain('is-lo'); expect(t.color).not.toBe(BLUE); }
      else { expect(t.cls, `${t.v}`).not.toMatch(/is-(elite|hi|lo)/); }
    }
  });

  test('the 9/10 boundary is exact', async ({ page }) => {
    await mount(page, {});
    const m = await page.evaluate(() => ({
      nine: window.GOB_AttrTiles.tierClass(9),
      ten: window.GOB_AttrTiles.tierClass(10),
      three: window.GOB_AttrTiles.tierClass(3),
      four: window.GOB_AttrTiles.tierClass(4),
      six: window.GOB_AttrTiles.tierClass(6),
      seven: window.GOB_AttrTiles.tierClass(7),
    }));
    expect(m).toEqual({
      nine: 'is-hi', ten: 'is-elite', three: 'is-lo',
      four: '', six: '', seven: 'is-hi',
    });
  });
});

test.describe('team-roster-view header alignment (real markup)', () => {
  const PAGE = read('team-roster-view.html');
  const PAGE_CSS = PAGE.slice(PAGE.indexOf('<style>') + 7, PAGE.indexOf('</style>'));
  // The Player Attributes table's own thead, straight from the page.
  const THEAD = (() => {
    const i = PAGE.indexOf('id="roster-table"');
    const a = PAGE.indexOf('<thead>', i);
    const b = PAGE.indexOf('</thead>', a) + '</thead>'.length;
    return PAGE.slice(a, b);
  })();

  async function mountRoster(page) {
    await page.setViewportSize({ width: 1600, height: 800 });
    await page.setContent(`<style>${PAGE_CSS}</style><style>${TILES_CSS}</style>
      <body style="margin:0;background:#0b0d14">
      <table class="roster-table" id="roster-table">${THEAD}<tbody id="tb"></tbody></table></body>`);
    await page.addScriptTag({ content: TILES_JS });
    await page.evaluate((a) => {
      const tr = document.createElement('tr');
      ['#2 Kermit Prospect', 'C', 'JR', '6\'9"', '242'].forEach((v) => {
        const td = document.createElement('td'); td.textContent = v; tr.appendChild(td);
      });
      const attrTd = document.createElement('td');
      attrTd.className = 'attr-tiles-cell';
      attrTd.innerHTML = window.GOB_AttrTiles.tilesHtml(a);
      tr.appendChild(attrTd);
      const rt = document.createElement('td'); rt.textContent = 'B+/A'; tr.appendChild(rt);
      document.getElementById('tb').appendChild(tr);
    }, rawAttrs([7, 2, 10, 3, 3, 3, 7, 3, 6, 4, 4, 3]));
  }

  test('header count matches body count — no orphaned columns', async ({ page }) => {
    await mountRoster(page);
    const m = await page.evaluate(() => ({
      heads: document.querySelectorAll('#roster-table thead th').length,
      cells: document.querySelectorAll('#roster-table tbody tr td').length,
      labels: [...document.querySelectorAll('#roster-table thead th')].map((t) => t.textContent.trim()),
    }));
    expect(m.heads).toBe(m.cells);
    expect(m.labels).toEqual(['Name', 'POS', 'Year', 'Height', 'Weight', 'Attributes', 'RT']);
  });

  test('no stray single-attribute headers survive', async ({ page }) => {
    await mountRoster(page);
    const labels = await page.evaluate(() =>
      [...document.querySelectorAll('#roster-table thead th')].map((t) => t.textContent.trim()));
    for (const abbr of ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'AG', 'ST', 'ND', 'IQ', 'FT']) {
      expect(labels, abbr).not.toContain(abbr);
    }
  });

  test('"Attributes" is centered over the tile block', async ({ page }) => {
    await mountRoster(page);
    const m = await page.evaluate(() => {
      const th = [...document.querySelectorAll('#roster-table thead th')]
        .find((t) => t.textContent.trim() === 'Attributes');
      const tiles = [...document.querySelectorAll('#roster-table .attr-tile')];
      const h = th.getBoundingClientRect();
      const first = tiles[0].getBoundingClientRect();
      const last = tiles[tiles.length - 1].getBoundingClientRect();
      const cell = document.querySelector('#roster-table .attr-tiles-cell').getBoundingClientRect();
      return {
        headerCenter: h.left + h.width / 2,
        blockCenter: (first.left + last.right) / 2,
        cellCenter: cell.left + cell.width / 2,
        tiles: tiles.length,
      };
    });
    expect(m.tiles).toBe(12);
    expect(Math.abs(m.headerCenter - m.blockCenter)).toBeLessThan(2);
    expect(Math.abs(m.headerCenter - m.cellCenter)).toBeLessThan(2);
  });

  test('the Attributes header is not clickable-looking (it cannot sort)', async ({ page }) => {
    await mountRoster(page);
    await page.addScriptTag({ content: read('team-roster-view.js').includes('setupRosterSorting')
      ? 'window.__hasGuard = true;' : 'window.__hasGuard = false;' });
    // Source-level guard: headers without data-sort get cursor:default and no handler.
    expect(read('team-roster-view.js')).toContain("if (!header.dataset.sort)");
  });
});

test.describe('the four in-scope surfaces all use the shared builder', () => {
  const SURFACES = [
    ['recruiting-hub.js', 'Recruits screen (Hub pool)'],
    ['franchise-command-center.js', 'FCC Roster + Recruits tabs'],
    ['team-roster-view.js', 'team-roster-view'],
  ];

  for (const [file, label] of SURFACES) {
    test(`${label} calls GOB_AttrTiles`, async () => {
      expect(read(file)).toContain('GOB_AttrTiles.tilesHtml');
    });
  }

  test('each in-scope page loads the module and stylesheet', async () => {
    for (const page of ['recruiting.html', 'franchise-command-center.html', 'team-roster-view.html']) {
      const html = read(page);
      expect(html, page).toContain('/js/shared/attrTiles.js');
      expect(html, page).toContain('/css/attr-tiles.css');
    }
  });

  test('no in-scope surface still emits 12 separate attribute columns', async () => {
    for (const page of ['franchise-command-center.html', 'team-roster-view.html']) {
      const html = read(page);
      expect(html, page).not.toContain('<th>SC</th>');
      expect(html, page).not.toContain('data-sort-key="SC"');
      // The grouped header's contents are rendered by attrTiles.js, so assert the
      // host cell exists rather than a literal label.
      expect(html, page).toContain('attr-tiles-head');
    }
  });

  test('out-of-scope surfaces are untouched', async () => {
    // set-lineup still uses its own ATTR_GROUPS card layout; player-detail unchanged.
    expect(read('set-lineup.js')).not.toContain('GOB_AttrTiles');
    expect(read('player-detail.js')).not.toContain('GOB_AttrTiles');
    // The sunset /team-roster/ templates are gone entirely.
    expect(fs.existsSync(path.join(S, 'team-roster'))).toBe(false);
  });
});
