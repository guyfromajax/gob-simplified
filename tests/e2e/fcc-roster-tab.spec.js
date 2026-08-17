// @ts-check
/** FCC Roster tab redesign — grouped tiles, key-based sort, scope toggle, RT lockup. */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const S = path.join(__dirname, '../../FrontEnd/static');
const read = (p) => fs.readFileSync(path.join(S, p), 'utf8');

const HTML = read('franchise-command-center.html');
const CSS = read('franchise-command-center.css') + read('css/attr-tiles.css') + read('css/rt-buckets.css');

function extractById(html, id) {
  const anchor = html.indexOf(`id="${id}"`);
  const open = html.lastIndexOf('<', anchor);
  const tag = html.slice(open + 1).match(/^[a-zA-Z0-9-]+/)[0];
  let i = open, depth = 0;
  const openRe = new RegExp(`<${tag}[\\s>]`, 'g'), closeRe = new RegExp(`</${tag}>`, 'g');
  while (i < html.length) {
    openRe.lastIndex = i; closeRe.lastIndex = i;
    const o = openRe.exec(html), c = closeRe.exec(html);
    if (!c) throw new Error('unbalanced');
    if (o && o.index < c.index) { depth++; i = o.index + 1; }
    else { depth--; i = c.index + 1; if (depth === 0) return html.slice(open, c.index + `</${tag}>`.length); }
  }
}
const ROSTER_TAB = extractById(HTML, 'roster-tab');

async function mount(page) {
  await page.setViewportSize({ width: 1500, height: 900 });
  await page.setContent(`<style>${CSS}</style>
    <style>body{margin:0;background:#0b0d14}.tab-content{display:block!important}</style>
    <div id="franchise-container"><div id="tournament-tabs">${ROSTER_TAB}</div></div>`);
  await page.addScriptTag({ content: read('js/shared/rtBucket.js') });
  await page.addScriptTag({ content: read('js/shared/attrTiles.js') });
  await page.evaluate(() => {
    const A = ['SC','SH','ID','OD','PS','BH','RB','AG','ST','ND','IQ','FT'];
    const mk = (i) => { const a={}; A.forEach((k,j)=>a[k]=((i*7+j*13)%95+5)*1); return a; };
    document.getElementById('fcc-roster-attr-head').innerHTML =
      window.GOB_AttrTiles.groupedHeaderHtml({ key: 'RT', dir: 'desc' });
    const tb = document.getElementById('team-body');
    tb.innerHTML = [0,1,2].map((i) =>
      '<tr><td class="c-ident"><div class="ident"><span class="ident-jersey">' + (i+2) +
      '</span><span class="ident-body"><span class="ident-name"><a href="#">Player ' + i + '</a></span></span></div></td>' +
      '<td class="c-rt"><span class="rt-lockup"><b class="rt-high">B+</b><i class="rt-elite">A</i></span></td>' +
      '<td><span class="pos-chip">PF</span></td><td>JR</td><td>6\'7"</td><td>228</td>' +
      '<td class="attr-tiles-cell">' + window.GOB_AttrTiles.groupedTilesHtml(mk(i)) + '</td></tr>').join('');
  });
}

test('column order is Player RT POS YR HT WT Attributes', async ({ page }) => {
  await mount(page);
  const labels = await page.evaluate(() =>
    [...document.querySelectorAll('#roster-tab thead th')].map((t) => t.textContent.replace(/cur.*pot/i,'').trim()));
  expect(labels.slice(0, 6)).toEqual(['Player', 'RT', 'POS', 'YR', 'HT', 'WT']);
  expect(labels).toHaveLength(7);
});

test('every header carries a sort key except the grouped attribute cell', async ({ page }) => {
  await mount(page);
  const m = await page.evaluate(() => ({
    withKey: [...document.querySelectorAll('#roster-tab thead th[data-sort-col]')].map((t) => t.dataset.sortCol),
    attrControls: document.querySelectorAll('#roster-tab [data-attr-sort]').length,
  }));
  expect(m.withKey).toEqual(['Name', 'RT', 'POS', 'Year', 'Height', 'Weight']);
  expect(m.attrControls).toBe(12);   // all 12 attributes sortable
});

test('tiles are grouped into 6 labelled pairs with no in-tile labels', async ({ page }) => {
  await mount(page);
  const m = await page.evaluate(() => ({
    groups: [...document.querySelectorAll('#roster-tab thead .attr-grp')].map((g) => g.textContent.trim()),
    pairs: document.querySelectorAll('#roster-tab tbody tr:first-child .attr-pair').length,
    tiles: document.querySelectorAll('#roster-tab tbody tr:first-child .attr-tile').length,
    inTileLabels: document.querySelectorAll('#roster-tab tbody .attr-tile u').length,
  }));
  expect(m.groups).toEqual(['OFFENSE', 'DEFENSE', 'SKILLS', 'GRIT', 'BODY', 'MIND']);
  expect(m.pairs).toBe(6);
  expect(m.tiles).toBe(12);
  expect(m.inTileLabels).toBe(0);
});

test('the grouped header lays out SIX ACROSS, not one tall column', async ({ page }) => {
  await mount(page);
  const m = await page.evaluate(() => {
    const groups = [...document.querySelectorAll('#roster-tab thead .attr-grp')];
    const boxes = groups.map((g) => g.getBoundingClientRect());
    const rows = [...new Set(boxes.map((b) => Math.round(b.y)))];
    const xs = boxes.map((b) => Math.round(b.x));
    const head = document.querySelector('#roster-tab thead').getBoundingClientRect();
    return { rows: rows.length, xs, ascending: xs.every((x, i) => i === 0 || x > xs[i - 1]), headHeight: head.height };
  });
  // All six group labels share one row and march left-to-right.
  expect(m.rows).toBe(1);
  expect(m.ascending).toBe(true);
  // A stacked header ran ~400px tall; two text rows plus padding is far less.
  expect(m.headHeight).toBeLessThan(120);
});

test('each pair is 2 tiles wide and pairs are separated by the group gap', async ({ page }) => {
  await mount(page);
  const m = await page.evaluate(() => {
    const pairs = [...document.querySelectorAll('#roster-tab tbody tr:first-child .attr-pair')];
    const boxes = pairs.map((p) => p.getBoundingClientRect());
    const innerGaps = pairs.map((p) => {
      const t = [...p.querySelectorAll('.attr-tile')].map((x) => x.getBoundingClientRect());
      return Math.round(t[1].left - t[0].right);
    });
    const groupGaps = boxes.slice(1).map((b, i) => Math.round(b.left - boxes[i].right));
    return { rows: [...new Set(boxes.map((b) => Math.round(b.y)))].length, innerGaps, groupGaps };
  });
  expect(m.rows).toBe(1);
  // Within a pair: 2.5px. Between pairs: the responsive clamp, always wider.
  for (const g of m.innerGaps) expect(g).toBeLessThanOrEqual(3);
  for (const g of m.groupGaps) expect(g).toBeGreaterThan(5);
});

test('RT is a current-to-potential lockup with the CUR/POT caption', async ({ page }) => {
  await mount(page);
  const m = await page.evaluate(() => {
    const th = document.querySelector('#roster-tab thead th.c-rt');
    const lock = document.querySelector('#roster-tab tbody .rt-lockup');
    return {
      caption: th.querySelector('.rt-caption').textContent.trim(),
      cur: lock.querySelector('b').textContent.trim(),
      pot: lock.querySelector('i').textContent.trim(),
      arrow: getComputedStyle(lock.querySelector('i'), '::before').content,
      curColored: getComputedStyle(lock.querySelector('b')).color,
    };
  });
  expect(m.caption).toMatch(/cur\s*→\s*pot/i);
  expect(m.cur).toBe('B+');
  expect(m.pot).toBe('A');
  expect(m.arrow).toContain('→');
  expect(m.curColored).not.toBe('rgb(0, 0, 0)');
});

test('the identity column is sticky and opaque in every row state', async ({ page }) => {
  await mount(page);
  const m = await page.evaluate(() => {
    const cells = [...document.querySelectorAll('#roster-tab td.c-ident')];
    return cells.map((c) => ({
      pos: getComputedStyle(c).position,
      bg: getComputedStyle(c).backgroundColor,
    }));
  });
  for (const c of m) {
    expect(c.pos).toBe('sticky');
    expect(c.bg).not.toContain('rgba');        // must be solid, not translucent
    expect(c.bg).not.toBe('transparent');
  }
});

test('POS chip is neutral — no position colour tokens', async ({ page }) => {
  await mount(page);
  const bg = await page.evaluate(() =>
    getComputedStyle(document.querySelector('#roster-tab .pos-chip')).backgroundColor);
  expect(bg).toBe('rgba(255, 255, 255, 0.07)');
  expect(CSS_HAS_POS_COLORS).toBe(false);
}, );

test('scope toggle exists with counts and aria-pressed', async ({ page }) => {
  await mount(page);
  const m = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('#roster-tab [data-roster-scope]')];
    return btns.map((b) => ({
      scope: b.dataset.rosterScope,
      pressed: b.getAttribute('aria-pressed'),
      hasCount: !!b.querySelector('[data-scope-count]'),
      text: b.textContent.replace(/\s+/g, ' ').trim(),
    }));
  });
  expect(m).toHaveLength(2);
  expect(m[0]).toMatchObject({ scope: 'varsity', pressed: 'true', hasCount: true });
  expect(m[1]).toMatchObject({ scope: 'practice', pressed: 'false', hasCount: true });
});

test('no stacked practice-squad table remains in the Roster tab', async () => {
  expect(HTML).not.toContain('training-squad-section');
  expect(HTML).not.toContain('training-squad-body');
});

const CSS_HAS_POS_COLORS = /--pos-(pg|sg|sf|pf|c)\b/i.test(CSS);
