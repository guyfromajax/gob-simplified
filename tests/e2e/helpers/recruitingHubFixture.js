// @ts-check
/** Recruiting hub fixture for the pinned-header tests: forty recruits, Pool / Leans / Visits. */
const { expect } = require('@playwright/test');
const { stubAuth } = require('./auth');

const FID = 'f-e2e-sticky-header';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const REGIONS = ['A', 'B', 'C', 'D', 'E'];
const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];

/** Forty recruits: enough rows to scroll under the header at 1920x1080. */
function pool() {
  const out = [];
  for (let i = 0; i < 40; i += 1) {
    const leansToUser = i % 3 === 0;
    const attrs = {};
    ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'].forEach((key, k) => {
      attrs[key] = 40 + ((i * 7 + k * 11) % 55);
    });
    out.push({
      recruit_id: 'r-' + i,
      image_id: 'r-' + i,
      name: ['Ada', 'Bea', 'Cal', 'Dev', 'Eli', 'Fay', 'Gus', 'Hal'][i % 8] + ' ' + ['Lean', 'Other', 'Stone', 'Wright', 'Park'][i % 5] + ' ' + (i + 1),
      archetype: 'Slasher',
      'Home Region': REGIONS[i % REGIONS.length],
      year: ['Junior', 'Senior', 'Sophomore'][i % 3],
      height: 72 + (i % 10),
      weight: 170 + (i % 40),
      attributes: attrs,
      position_ratings: { [POSITIONS[i % 5]]: 60 + (i % 35) },
      // Every third recruit has no lean to the user, so the table has plain rows too.
      Lean: i % 3 === 2 ? { 1: 'rival-1', 2: 'rival-2', 3: null }
        : leansToUser ? { 1: TID, 2: 'rival-1', 3: null } : { 1: 'rival-1', 2: TID, 3: null },
    });
  }
  return out;
}

function history() {
  return [20, 21, 22, 23, 24, 25, 26].map((week) => ({ week, recruit_id: null, name: null, lean: null }));
}

function dataFor(week) {
  return {
    team: 'Lancaster',
    team_id: TID,
    team_region: 'C',
    week,
    recruits: pool(),
    team_name_map: { [TID]: 'Lancaster', 'rival-1': 'Fairview', 'rival-2': 'Great Falls' },
    saved_orders: {},
    watchlist: [],
    new_lean_recruit_ids: [],
    week_35_recruiting_results: {},
    week_35_recruiting_ran: false,
    invite_seed_modal_seen: true,
    visit_history: history(),
    current_results_week: null,
    conferences: { order: [], by_team_id: {} },
  };
}

function cc(week) {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster', week, rank: 14, season: 1, current_season: 1,
    training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: week, counts: {}, week_35_orders_submitted: false },
    user_conference: 1, user_region: 'C', team_record: { wins: 4, losses: 1 },
  };
}

async function openHub(page, hub, week) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) { return route.continue(); }
    const json = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (pathname.startsWith('/franchise/recruiting-data')) return json(dataFor(week));
    if (pathname.startsWith('/franchise/command-center/data')) return json(cc(week));
    if (pathname.startsWith('/franchise/recruiting-results')) return json({ regions: [] });
    if (pathname === '/app-config') return json({ isAlpha: false, version: '1.0' });
    if (pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/teams') return json({});
    return route.continue();
  });
  await page.goto('/recruiting.html?franchise_id=' + FID + '&team_id=' + TID + '&hub=' + hub);
  await page.waitForSelector('#hub-phase .pstrip');
  await page.waitForFunction(() => {
    const cls = document.documentElement.classList;
    return cls.contains('gob-shell') && !cls.contains('gob-pending');
  });
  await page.evaluate(() => document.fonts && document.fonts.ready);
}

/** Scroll the shell's main pane by `px` and let the sticky header settle. */
async function scrollMain(page, px) {
  await page.evaluate((y) => {
    const main = document.querySelector('html.gob-shell .main');
    main.scrollTop = y;
  }, px);
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.waitForTimeout(150);
}

/**
 * Scroll the main pane until `rows` body rows of the table have passed under its pinned
 * header, wherever the table sits on the page.
 */
async function scrollTableUnder(page, tableSelector, rows) {
  const px = await page.evaluate(([selector, n]) => {
    const main = document.querySelector('html.gob-shell .main');
    const table = document.querySelector(selector);
    const row = table.querySelector('tbody tr');
    const stickTop = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--gob-stick-top')) || 0;
    const edge = main.getBoundingClientRect().top + stickTop;
    return main.scrollTop + (table.getBoundingClientRect().top - edge) + n * row.getBoundingClientRect().height;
  }, [tableSelector, rows]);
  await scrollMain(page, px);
  return px;
}

/** The header's box on screen: the union of its cells' boxes, in whole pixels, inset by one. */
function headerBox(page, tableSelector) {
  return page.evaluate((selector) => {
    const rects = [...document.querySelector(selector).querySelectorAll('thead th')].map((th) => th.getBoundingClientRect());
    const top = Math.ceil(Math.min(...rects.map((r) => r.top))) + 1;
    const left = Math.ceil(Math.min(...rects.map((r) => r.left))) + 1;
    const bottom = Math.floor(Math.max(...rects.map((r) => r.bottom))) - 1;
    const right = Math.floor(Math.max(...rects.map((r) => r.right))) - 1;
    return { x: left, y: top, width: right - left, height: bottom - top };
  }, tableSelector);
}

/**
 * The header's pixels as the viewer sees them: a clip screenshot, decoded in the page.
 * `size` (a previous capture's clip) keeps two captures the same size whatever the
 * sub-pixel phase of each position.
 */
async function headerPixels(page, tableSelector, size) {
  const clip = await headerBox(page, tableSelector);
  if (size) { clip.width = size.width; clip.height = size.height; }
  const png = await page.screenshot({ clip, animations: 'disabled' });
  const data = await page.evaluate((b64) => new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      resolve({ width: canvas.width, height: canvas.height, data: Array.from(ctx.getImageData(0, 0, canvas.width, canvas.height).data) });
    };
    img.src = 'data:image/png;base64,' + b64;
  }), png.toString('base64'));
  return Object.assign(data, { clip });
}

/**
 * Pixels of the pinned header that are not in the header at rest: each scrolled pixel is
 * compared with the rest pixel at the same place and one row up and down (text snaps a
 * pixel differently when the header is pinned at another sub-pixel phase), and counts
 * when it differs from all three by more than `tolerance` in a channel. The bottom
 * `skipRows` rows are ignored (the hairline that is meant to appear). If the header is
 * opaque, what it shows while rows pass under it is what it shows at rest.
 */
function pixelDiff(rest, scrolled, skipRows, tolerance) {
  const out = { count: 0, first: [] };
  if (rest.width !== scrolled.width || rest.height !== scrolled.height) {
    return Object.assign(out, { count: -1, sizes: [rest.width + 'x' + rest.height, scrolled.width + 'x' + scrolled.height] });
  }
  const w = rest.width;
  const rows = rest.height - (skipRows || 0);
  const gap = (i, j) => Math.max(Math.abs(rest.data[i] - scrolled.data[j]), Math.abs(rest.data[i + 1] - scrolled.data[j + 1]), Math.abs(rest.data[i + 2] - scrolled.data[j + 2]));
  for (let y = 0; y < rows; y += 1) {
    for (let x = 0; x < w; x += 1) {
      const j = (y * w + x) * 4;
      let d = gap(j, j);
      if (y > 0) d = Math.min(d, gap(j - w * 4, j));
      if (y < rest.height - 1) d = Math.min(d, gap(j + w * 4, j));
      if (d > tolerance) {
        out.count += 1;
        if (out.first.length < 8) out.first.push({ x, y, rest: rest.data.slice(j, j + 3), scrolled: scrolled.data.slice(j, j + 3) });
      }
    }
  }
  return out;
}

/**
 * Looks at the pinned header the way the eye does. The header's box is the union of its
 * cells' boxes (a pinned `th` is not where its `thead` is laid out). Every pixel-sample
 * inside that box must land on the header, and every cell must be painted opaque.
 */
function inspectHeader(page, tableSelector) {
  return page.evaluate((selector) => {
    const table = document.querySelector(selector);
    const thead = table.querySelector('thead');
    const cells = [...thead.querySelectorAll('th')];
    const rects = cells.map((th) => th.getBoundingClientRect());
    const box = {
      top: Math.min(...rects.map((r) => r.top)), bottom: Math.max(...rects.map((r) => r.bottom)),
      left: Math.min(...rects.map((r) => r.left)), right: Math.max(...rects.map((r) => r.right)),
    };
    const leaks = [];
    let samples = 0;
    for (let x = box.left + 1; x < box.right - 1; x += 4) {
      for (let y = box.top + 1; y < box.bottom - 1; y += 4) {
        samples += 1;
        const hit = document.elementFromPoint(x, y);
        if (hit && !thead.contains(hit) && table.contains(hit)) {
          leaks.push({ x: Math.round(x), y: Math.round(y), hit: hit.tagName + '.' + String(hit.className).split(' ')[0], text: (hit.textContent || '').trim().slice(0, 16) });
        }
      }
    }
    const alpha = (color) => {
      const m = /rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*(?:,\s*([\d.]+))?\)/.exec(color);
      if (!m) return color === 'transparent' ? 0 : 1;
      return m[1] == null ? 1 : Number(m[1]);
    };
    const paint = cells.map((th) => {
      const cs = getComputedStyle(th);
      return {
        cls: th.className, color: cs.backgroundColor, colorAlpha: alpha(cs.backgroundColor),
        image: cs.backgroundImage, borderBottom: cs.borderBottomWidth + ' ' + cs.borderBottomColor, borderAlpha: alpha(cs.borderBottomColor),
        line: getComputedStyle(th, '::before').backgroundColor, lineAlpha: alpha(getComputedStyle(th, '::before').backgroundColor),
      };
    });
    const rows = [...table.querySelectorAll('tbody tr')];
    return {
      box: { top: Math.round(box.top), bottom: Math.round(box.bottom), left: Math.round(box.left), right: Math.round(box.right) },
      cells: cells.length, samples, leakCount: leaks.length, leaks: leaks.slice(0, 10),
      translucentFill: paint.filter((c) => c.colorAlpha < 1).map((c) => c.cls + ':' + c.color),
      // A border is either transparent (the cell draws the line itself) or opaque; in between it leaks.
      translucentBorder: paint.filter((c) => c.borderBottom.split(' ')[0] !== '0px' && c.borderAlpha > 0 && c.borderAlpha < 1).map((c) => c.cls + ':' + c.borderBottom),
      translucentLine: paint.filter((c) => c.lineAlpha > 0 && c.lineAlpha < 1).map((c) => c.cls + ':' + c.line),
      rowsUnder: rows.filter((tr) => { const r = tr.getBoundingClientRect(); return r.top < box.bottom - 1 && r.bottom > box.top; }).length,
      pinned: table.classList.contains('is-pinned'),
      lastRowLine: [...new Set([...thead.querySelectorAll('tr:last-child th')].map((th) => getComputedStyle(th, '::before').backgroundColor))],
      headHeights: [...thead.querySelectorAll('tr')].map((tr) => Math.round(tr.querySelector('th').getBoundingClientRect().height * 10) / 10),
      bodyHeights: rows.slice(0, 4).map((tr) => Math.round(tr.getBoundingClientRect().height * 10) / 10),
    };
  }, tableSelector);
}


module.exports = { FID, TID, pool, openHub, scrollMain, scrollTableUnder, inspectHeader, headerPixels, pixelDiff };
