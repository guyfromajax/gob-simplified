const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * Team Builder on the gob tokens + colour law (computed-style guards).
 *
 * TB_SHOTS=before writes before-*.png and skips the guards: run it on develop
 * for the BEFORE set. The default run writes after-*.png and asserts.
 */
const BEFORE = process.env.TB_SHOTS === 'before';
const OUT = path.join(__dirname, '../../reports/team-builder-tokens');

const REPLACED = 'cccccccccccccccccccccc01';
const GREEN_RGB = 'rgb(52, 236, 39)';
const ORANGE_RGB = 'rgb(247, 148, 32)';
const NAVY_RGB = 'rgb(39, 64, 142)';
const TIER_BLUE_RGB = 'rgb(107, 164, 224)';

// Names are stored strings: nothing here may be title-cased or hyphen-stripped.
const TEAMS = [
  ['cccccccccccccccccccccc01', 'Bentley-Truman', 'BTR', 62, 9100],
  ['cccccccccccccccccccccc02', 'IDA', 'IDA', 88, 9900],
  ['cccccccccccccccccccccc03', 'Seattle AAA', 'SEA', 80, 9700],
  ['cccccccccccccccccccccc04', 'Lancaster', 'LAN', 74, 9500],
  ['cccccccccccccccccccccc05', 'Four Corners', 'FCO', 70, 9400],
  ['cccccccccccccccccccccc06', 'Morristown', 'MOR', 66, 9300],
  ['cccccccccccccccccccccc07', 'Port Allen', 'PAL', 58, 9000],
  ['cccccccccccccccccccccc08', 'Kettle Falls', 'KFA', 50, 8800],
].map(function (row) {
  return {
    object_id: row[0],
    _id: row[0],
    name: row[1],
    abbreviation: row[2],
    conference: 3,
    region: 'B',
    prestige: row[3],
    total_player_attrs: row[4],
    primary_color: '#124e78',
    secondary_color: '#a8c6df',
  };
});

const IDENTITY = { name: 'Cascade Valley', mascot: 'Timberwolves', abbreviation: 'CVT' };

const ATTR_CODES = ['SC', 'SH', 'ID', 'OD', 'PS', 'BH', 'RB', 'ST', 'AG', 'ND', 'IQ', 'FT'];
const CLASS_CYCLE = ['SR', 'JR', 'SO', 'FR'];
const CLASS_RANK = { FR: 1, SO: 2, JR: 3, SR: 4 };
const NAMES = [
  'Jalen Carter', 'Omar Lane', 'Theo Marsh', 'Dev Okafor', 'Sam Whitlock', 'Rui Tanaka',
  'Cole Brandt', 'Nico Ferrand', 'Eli Sato', 'Marcus Hale', 'Finn Aldous', 'Kofi Mensah',
  'Wes Tully', 'Ari Lund', 'Bo Kessler',
];

// Spread across every band of the 5–99 scale so each ramp colour is on screen.
function attrsFor(i) {
  const out = {};
  ATTR_CODES.forEach(function (code, j) {
    out[code] = Math.max(5, Math.min(99, 30 + ((i * 17 + j * 13) % 66)));
  });
  if (i === 0) {
    out.SC = 99;
    out.SH = 86;
    out.ID = 72;
    out.OD = 55;
    out.PS = 22;
  }
  return out;
}

function playerRow(i, walkOn) {
  const parts = NAMES[i].split(' ');
  return {
    id: 'tb-e2e-p' + (i + 1),
    first_name: parts[0],
    last_name: parts[1],
    jersey: i + 1,
    class_year: CLASS_CYCLE[i % 4],
    height_in: 72 + (i % 9),
    weight_lb: 185 + i * 3,
    attributes: attrsFor(i),
    walk_on: !!walkOn,
  };
}

const CORE = NAMES.slice(0, 12).map(function (_n, i) { return playerRow(i, false); });
const WALK_ONS = NAMES.slice(12).map(function (_n, i) { return playerRow(12 + i, true); });
const ALL = CORE.concat(WALK_ONS);
const HEIGHT_BUDGET = ALL.reduce(function (s, p) { return s + p.height_in; }, 0) + 4;
const CLASS_BUDGET = ALL.reduce(function (s, p) { return s + CLASS_RANK[p.class_year]; }, 0);

const POSITIONS = ['PG', 'SG', 'SF', 'PF', 'C'];

// Best slot rotates by player so every position shows on the board.
function ratingsFor(i) {
  const base = 58 + ((i * 7) % 30);
  const out = {};
  POSITIONS.forEach(function (pos, j) {
    out[pos] = base - 3 * ((j - (i % 5) + 5) % 5);
  });
  return out;
}

const CATALOG = {
  total: 24,
  entries: Array.from({ length: 24 }, function (_v, i) {
    return {
      image_id: 'tb-e2e-img-' + i,
      skin: ['white-pale', 'white-normal', 'asian', 'black-normal', 'black-dark'][i % 5],
      frame: ['Slight', 'Lean', 'Normal', 'Broad', 'Doughy'][i % 5],
      definition: ['Cut', 'Toned', 'Soft'][i % 3],
    };
  }),
};

// Flat 8x8 PNG so portrait tiles never reach the CDN.
const PIXEL = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEUlEQVR4nGOoyojBihiGlgQAGBlPge5XMiEAAAAASUVORK5CYII=',
  'base64'
);

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApis(page) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    if (request.resourceType() === 'image' && /recruits|headshot|players?\//i.test(request.url())) {
      await route.fulfill({ status: 200, contentType: 'image/png', body: PIXEL });
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname === '/app-config'
      || pathname === '/teams';
    if (!api) {
      await route.continue();
      return;
    }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0', teamBuilderEnabled: true });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, TEAMS);
      return;
    }
    if (pathname === '/franchise/team-builder/drafts') {
      if (request.method() === 'GET') {
        // No stored draft: the identity is typed in through the page instead.
        await fulfillJson(route, { drafts: [] });
      } else {
        await fulfillJson(route, { draft: { draft_id: 'tb-e2e-draft', replaced_object_id: REPLACED } });
      }
      return;
    }
    if (pathname === '/franchise/team-builder/wizard-walk-ons') {
      await fulfillJson(route, {
        walk_ons: WALK_ONS,
        height_budget: HEIGHT_BUDGET,
        class_budget: CLASS_BUDGET,
        class_rank: CLASS_RANK,
        height_min_in: 66,
        height_max_in: 84,
      });
      return;
    }
    if (pathname === '/franchise/team-builder/slot-roster') {
      await fulfillJson(route, { players: CORE });
      return;
    }
    if (pathname === '/franchise/team-builder/portraits/assign') {
      await fulfillJson(route, {
        portraits: ALL.map(function (p, i) {
          return { player_id: 'tb-e2e-minted-' + i, image_id: 'tb-e2e-img-' + i, source: 'auto' };
        }),
      });
      return;
    }
    if (pathname === '/franchise/team-builder/position-ratings') {
      const body = request.postDataJSON() || {};
      await fulfillJson(route, {
        players: (body.players || []).map(function (p) {
          const idx = ALL.findIndex(function (row) { return row.id === p.player_id; });
          return { player_id: p.player_id, position_ratings: ratingsFor(Math.max(0, idx)) };
        }),
      });
      return;
    }
    if (pathname === '/franchise/team-builder/portraits/catalog') {
      await fulfillJson(route, CATALOG);
      return;
    }
    if (pathname === '/franchise/team-builder/apply') {
      await fulfillJson(route, { franchise_id: 'f-e2e-team-builder' });
      return;
    }
    await fulfillJson(route, {});
  });
}

/** Open Identity and type the program in, so Continue is enabled. */
async function openIdentity(page) {
  await page.goto('/team-builder.html?replaced_object_id=' + REPLACED + '&chapter=identity');
  await page.waitForSelector('#tb-id-name', { timeout: 30000 });
  await page.locator('#tb-id-name').fill(IDENTITY.name);
  await page.locator('#tb-id-mascot').fill(IDENTITY.mascot);
  await page.locator('#tb-id-abbr').fill(IDENTITY.abbreviation);
  await page.waitForSelector('#tb-sb-continue:not([disabled])');
  await page.waitForSelector('.pals .pal');
  await page.locator('#tb-id-abbr').blur();
  await page.mouse.move(2, 2);
}

async function openGate(page) {
  await openIdentity(page);
  await page.locator('#tb-sb-continue').click();
  await page.waitForSelector('.gate .mode');
  await page.mouse.move(2, 2);
}

async function openRoster(page) {
  await openGate(page);
  await page.locator('.mode[data-mode="capped"]').click();
  await page.waitForSelector('#tb-sb-continue:not([disabled])');
  await page.locator('#tb-sb-continue').click();
  await page.waitForSelector('#tb-board .bd-row.sel', { timeout: 30000 });
  await page.waitForSelector('#tb-board .bd-grade:not(.pending)');
  await page.waitForSelector('#tb-sb-roster-next:not([disabled])');
  await page.mouse.move(2, 2);
}

async function shot(page, name) {
  fs.mkdirSync(OUT, { recursive: true });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(OUT, (BEFORE ? 'before-' : 'after-') + name) });
}

function parseRgb(color) {
  const m = String(color || '').match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  return m[1].split(',').map((part) => Number(String(part).trim()));
}

function isGreenish(color) {
  const p = parseRgb(color);
  if (!p || p.length < 3 || p[3] === 0) return false;
  return p[1] > 150 && p[1] > p[0] + 40 && p[1] > p[2] + 40;
}

function isOrangeish(color) {
  const p = parseRgb(color);
  if (!p || p.length < 3 || p[3] === 0) return false;
  return p[0] > 200 && p[1] > 90 && p[1] < 200 && p[2] < 110 && p[0] > p[1] + 40;
}

// The RT blue (#4A90D9 / --tier-blue), as opposed to navy.
function isRtBlue(color) {
  const p = parseRgb(color);
  if (!p || p.length < 3 || p[3] === 0) return false;
  return p[2] > 190 && p[2] > p[0] + 60 && p[1] > 120;
}

function neutral(color) {
  return !isGreenish(color) && !isOrangeish(color) && !isRtBlue(color);
}

function px(value) {
  const m = String(value || '').match(/^([\d.]+)px$/);
  return m ? parseFloat(m[1]) : NaN;
}

/** Computed paint of the first match: every colour-bearing property the law covers. */
async function paint(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const s = getComputedStyle(el);
    return {
      color: s.color,
      bg: s.backgroundColor,
      bgImage: s.backgroundImage,
      border: s.borderTopColor,
      borderLeft: s.borderLeftColor,
      shadow: s.boxShadow,
      radius: s.borderTopLeftRadius,
      width: el.getBoundingClientRect().width,
      text: (el.textContent || '').trim(),
    };
  }, selector);
}

function expectNeutral(p, label) {
  expect(p, label + ' missing').not.toBeNull();
  ['color', 'bg', 'border', 'borderLeft'].forEach(function (key) {
    expect(neutral(p[key]), label + ' ' + key + ' = ' + p[key]).toBe(true);
  });
  expect(/52,\s*236,\s*39|247,\s*148,\s*32|74,\s*144,\s*217/.test(p.bgImage + ' ' + p.shadow),
    label + ' gradient/shadow = ' + p.bgImage + ' ' + p.shadow).toBe(false);
}

const SIZES = [[1280, 720, '1280'], [1920, 1080, '1920']];

test.describe('team builder token + colour-law guards', () => {
  test('identity and gate: one green Advance, neutral choice controls', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApis(page);

    for (const size of SIZES) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await openIdentity(page);
      await page.waitForTimeout(600);
      if (captureShots) await shot(page, 'identity-' + size[2] + '.png');

      if (!BEFORE) {
        const tokens = await page.evaluate(() => ({
          gob: document.documentElement.classList.contains('gob'),
          green: getComputedStyle(document.documentElement).getPropertyValue('--green').trim(),
        }));
        expect(tokens.gob).toBe(true);
        expect(tokens.green).not.toBe('');

        // Team names render as stored.
        expect((await paint(page, '#tb-sb-claim .sb-v')).text).toContain('Bentley-Truman');

        const advance = await paint(page, '#tb-sb-continue');
        expect(advance.bg).toBe(GREEN_RGB);
        expectNeutral(await paint(page, '.sb-cell.chap'), 'chapter cell');
        expectNeutral(await paint(page, '.sb-cell.chap .sb-v'), 'chapter label');
        expectNeutral(await paint(page, '.pal.on'), 'selected palette');
        expectNeutral(await paint(page, '.chip.on'), 'selected chip');
        expectNeutral(await paint(page, '.stbtn.on'), 'selected style button');
        expectNeutral(await paint(page, '.dot.d-ok'), 'status dot');
        const greens = await page.evaluate(() => {
          return [].slice.call(document.querySelectorAll('#tb-app button')).filter(function (b) {
            return getComputedStyle(b).backgroundColor === 'rgb(52, 236, 39)';
          }).map(function (b) { return b.id || b.className; });
        });
        expect(greens).toEqual(['tb-sb-continue']);
      }

      await page.locator('#tb-sb-continue').click();
      await page.waitForSelector('.gate .mode');
      await page.mouse.move(2, 2);
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'gate-unchosen-' + size[2] + '.png');
      if (!BEFORE) {
        await expect(page.locator('#tb-sb-continue')).toBeDisabled();
        expect(neutral((await paint(page, '#tb-sb-continue')).bg)).toBe(true);
      }

      await page.locator('.mode[data-mode="capped"]').click();
      await page.waitForSelector('.mode.on');
      await page.waitForSelector('#tb-sb-continue:not([disabled])');
      await page.mouse.move(2, 2);
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'gate-capped-' + size[2] + '.png');
      if (!BEFORE) {
        expect((await paint(page, '#tb-sb-continue')).bg).toBe(GREEN_RGB);
        expectNeutral(await paint(page, '.mode.on'), 'chosen mode card');
        expectNeutral(await paint(page, '.m-elig.ok'), 'eligible status label');
        expectNeutral(await paint(page, '.mode.on .m-tick'), 'chosen tick');
      }
    }
  });

  test('roster: navy selection, neutral status, square headshots, 99 cap', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApis(page);

    for (const size of SIZES) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await openRoster(page);
      await page.waitForTimeout(400);
      if (captureShots) await shot(page, 'roster-legal-' + size[2] + '.png');

      if (!BEFORE) {
        expect((await paint(page, '#tb-sb-roster-next')).bg).toBe(GREEN_RGB);

        const sel = await paint(page, '#tb-board .bd-row.sel');
        expect(isRtBlue(sel.bg), 'selected row bg ' + sel.bg).toBe(false);
        expect(sel.shadow).toContain(NAVY_RGB);

        expectNeutral(await paint(page, '.verdict.ok'), 'legal verdict');
        expectNeutral(await paint(page, '.verdict.ok .vd-k'), 'legal verdict label');
        expectNeutral(await paint(page, '.meter .mt-note .ok'), 'meter note');
        expectNeutral(await paint(page, '.meter.exact'), 'exact meter');
        expectNeutral(await paint(page, '.meter.exact .mt-fill'), 'exact meter fill');
        expectNeutral(await paint(page, '.pool.ok'), 'attribute pool');
        expectNeutral(await paint(page, '.pool.ok .pool-r .n'), 'attribute pool number');
        expectNeutral(await paint(page, '.tally.ok'), 'budget tally');
        expectNeutral(await paint(page, '.tally.ok em'), 'budget tally note');
        expectNeutral(await paint(page, '#tb-board .pos'), 'position chip');
        expectNeutral(await paint(page, '.gcard .gp'), 'grade card position');
        expectNeutral(await paint(page, '.catrow span'), 'attribute category label');
        expectNeutral(await paint(page, '.alegend b'), 'attribute legend code');
        expectNeutral(await paint(page, '.seg button.on'), 'view toggle');
        expectNeutral(await paint(page, '.cseg button.on'), 'year control');

        // Headshots are square: --radius-6 on the board badge, --radius-10 on the portrait.
        const thumb = await paint(page, '#tb-board .bd-row .pt');
        expect(px(thumb.radius)).toBe(6);
        expect(px(thumb.radius)).toBeLessThanOrEqual(thumb.width / 4);
        const portrait = await paint(page, '#tb-insp .pt-lg');
        expect(px(portrait.radius)).toBe(10);
        expect(px(portrait.radius)).toBeLessThanOrEqual(portrait.width / 4);

        // The attribute ramp is the one sanctioned green/blue: positive data and elite.
        const ramp = await page.evaluate(() => {
          const out = {};
          ['SC', 'ID', 'PS'].forEach(function (code) {
            const row = document.querySelector('#tb-insp .attr[data-code="' + code + '"]');
            out[code] = {
              fill: getComputedStyle(row.querySelector('.fill')).backgroundColor,
              num: row.querySelector('.num').textContent.trim(),
              max: row.querySelector('input[data-attr]').max,
            };
          });
          return out;
        });
        expect(ramp.SC.num).toBe('99');
        expect(ramp.SC.max).toBe('99');
        expect(ramp.SC.fill).toBe(TIER_BLUE_RGB);
        expect(ramp.ID.fill).toBe(GREEN_RGB);
        expect(isGreenish(ramp.PS.fill) || isRtBlue(ramp.PS.fill)).toBe(false);
      }

      // Year budget must match exactly: one change makes the roster illegal.
      await page.locator('#tb-insp .cseg button:not(.on)').first().click();
      await page.waitForSelector('.verdict.bad');
      await page.waitForSelector('#tb-board .bd-grade:not(.pending)');
      await page.mouse.move(2, 2);
      await page.waitForTimeout(400);
      if (captureShots) await shot(page, 'roster-not-legal-' + size[2] + '.png');
      if (!BEFORE) {
        await expect(page.locator('#tb-sb-roster-next')).toBeDisabled();
        expect(neutral((await paint(page, '#tb-sb-roster-next')).bg)).toBe(true);
        expectNeutral(await paint(page, '#tb-board .mk.edit'), 'changed marker');
        expectNeutral(await paint(page, '#tb-board .cls.chg'), 'changed class chip');
        expectNeutral(await paint(page, '.bd-foot i'), 'changed legend dot');
      }

      await page.locator('#tb-board [data-view="grid"]').click();
      await page.waitForSelector('#tb-board table.gr tr.sel');
      await page.mouse.move(2, 2);
      await page.waitForTimeout(300);
      if (captureShots) await shot(page, 'roster-grid-' + size[2] + '.png');
      if (!BEFORE) {
        const gridSel = await paint(page, '#tb-board table.gr tr.sel td');
        expect(isRtBlue(gridSel.bg), 'grid selected row bg ' + gridSel.bg).toBe(false);
        expectNeutral(await paint(page, '#tb-board table.gr .pos'), 'grid position chip');
      }

      await page.locator('#tb-board [data-view="sig"]').click();
      await page.waitForSelector('#tb-insp .pt-lg');
      await page.locator('#tb-insp .pt-ov [data-open-picker]').click({ force: true });
      await page.waitForSelector('.pk-grid .pk-i');
      await page.mouse.move(2, 2);
      await page.waitForTimeout(400);
      if (captureShots) await shot(page, 'roster-portrait-picker-' + size[2] + '.png');
      if (!BEFORE) {
        expectNeutral(await paint(page, '.mdl-acc'), 'picker accent');
        expectNeutral(await paint(page, '.tones button.on'), 'tone filter');
        const tile = await paint(page, '.pk-grid .pk-i');
        expect(px(tile.radius)).toBe(10);
        expect(px(tile.radius)).toBeLessThanOrEqual(tile.width / 4);
      }
    }
  });

  test('review and establish: orange commit, then the green Enter', async ({ page }, testInfo) => {
    const captureShots = testInfo.repeatEachIndex === 0;
    await stubAuth(page);
    await installApis(page);

    for (const size of SIZES) {
      await page.setViewportSize({ width: size[0], height: size[1] });
      await openRoster(page);
      await page.locator('#tb-sb-roster-next').click();
      await page.waitForSelector('.rv .fifteen .pl');
      await page.waitForSelector('#tb-sb-establish');
      await page.mouse.move(2, 2);
      await page.waitForTimeout(500);
      if (captureShots) await shot(page, 'review-' + size[2] + '.png');

      if (!BEFORE) {
        // Establish writes the program: a commit, so orange. Nothing here is green.
        expect((await paint(page, '#tb-sb-establish')).bg).toBe(ORANGE_RGB);
        expectNeutral(await paint(page, '.rv .elig'), 'eligibility card');
        expectNeutral(await paint(page, '.rv .elig-v'), 'eligibility label');
        expectNeutral(await paint(page, '.rv-eb'), 'review eyebrow');
        expectNeutral(await paint(page, '.ms-v em.ok'), 'measure note');
        expectNeutral(await paint(page, '.fifteen .pos-b'), 'review position chip');
        const thumb = await paint(page, '.fifteen .pt');
        expect(px(thumb.radius)).toBe(6);
        expect(px(thumb.radius)).toBeLessThanOrEqual(thumb.width / 4);

        const names = await page.evaluate(() => {
          return [].slice.call(document.querySelectorAll('.rv .tbl td.nm')).map(function (td) {
            return (td.textContent || '').replace(/^\d+/, '').trim();
          });
        });
        expect(names).toEqual(expect.arrayContaining(['IDA', 'Seattle AAA', 'Four Corners']));
      }

      await page.locator('#tb-sb-establish').click();
      await page.waitForSelector('#tb-est-root.p3 #tb-est-enter:not([disabled])', { timeout: 20000 });
      await page.mouse.move(2, 2);
      await page.waitForTimeout(900);
      if (captureShots) await shot(page, 'establish-' + size[2] + '.png');

      if (!BEFORE) {
        expect((await paint(page, '#tb-est-enter')).bg).toBe(GREEN_RGB);
        expectNeutral(await paint(page, '.w-pulse span'), 'wait pulse');
        expectNeutral(await paint(page, '.sw-t tr.slot.now td'), 'swapped seat row');
        expectNeutral(await paint(page, '.ch-v .yes'), 'charter eligibility note');
        expect((await paint(page, '.sw-t tr.slot.now td.n')).text).toBe('Cascade Valley');
      }
    }
  });
});
