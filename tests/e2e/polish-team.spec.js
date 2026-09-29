// @ts-check
/**
 * UX polish batch A — Team. Jamie's design review items 3–6.
 *
 * Square headshots, the roster's column rhythm, the twelve-measure Team
 * Attributes grid with its radar, and the top-25-only rank prefix on the
 * Team Schedule. Screenshots land in reports/polish-team.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 180000 });

const FID = 'f-e2e-polish-team';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OUT = path.join(__dirname, '../../reports/polish-team');
const SIZES = [[1280, 720, '1280'], [1920, 1080, '1920']];

const STATS = ['PTS', '3PTM', 'AST', 'BLK', 'FG%', 'REB', 'STL', 'DEF%'];

// The eight measures documented at −20…+20. Only these carry the ± pill.
const SIGNED_KEYS = [
  'fight', 'discipline', 'offensive_efficiency', 'defensive_efficiency',
  'pt_opp_modifier', 'pt_efficiency', 'fb_efficiency', 'fb_opp_modifier',
];
const UNSIGNED_KEYS = ['team_chemistry', 'shot_threshold', 'rebound_modifier'];

const MEASURES = [
  ['team_chemistry', 'Chemistry', 19, 25, null, 12, 80, 1],
  ['fight', 'Fight', 8, null, 20, 21, 84, 3],
  ['discipline', 'Discipline', -4, null, 20, 88, 31, -2],
  ['offensive_efficiency', 'Offense', 11, null, 20, 9, 93, 4],
  ['defensive_efficiency', 'Defense', -7, null, 20, 101, 21, -6],
  ['pt_opp_modifier', 'P/T Offense', 5, null, 20, 33, 74, null],
  ['pt_efficiency', 'P/T Defense', -2, null, 20, 70, 45, 1],
  ['fb_efficiency', 'Fast Break', 14, null, 20, 4, 97, 2],
  ['fb_opp_modifier', 'Fast Break Defense', 0, null, 20, 64, 50, null],
  ['shot_threshold', 'Shooting', 88, null, null, 17, 87, -1],
  ['rebound_modifier', 'Rebounding', 0.6, null, null, 52, 59, null],
];

const CHARACTER = ['team_chemistry', 'fight', 'discipline'];

function teamData() {
  const attrs = {};
  const measures = MEASURES.map(([key, label, value, scaleMax, signed, rank, pct, delta]) => {
    attrs[key] = value;
    return {
      family: CHARACTER.indexOf(key) !== -1 ? 'character' : 'floor',
      family_label: CHARACTER.indexOf(key) !== -1 ? 'Character' : 'On the floor',
      key: key,
      label: label,
      value: value,
      scale_max: scaleMax,
      signed_scale: signed,
      meter_pct: key === 'team_chemistry' ? 76 : null,
      delta: null,
      description: null,
      direction: key === 'shot_threshold' ? 'lower_better' : 'higher_better',
      rank: rank,
      rank_of: 128,
      percentile: pct,
      rank_delta: delta,
      tied: false,
    };
  });
  return { team_attributes: attrs, measures: measures, updated_after_week: 12 };
}

function roster() {
  const players = [];
  const names = ['Ada Keeper', 'Cal Ives', 'Dee Ortiz', 'Eve Park', 'Ford Nakamura',
    'Gil Abernathy', 'Hank Osei', 'Ivo Salazar', 'Jem Whitfield', 'Kip Brannigan',
    'Lou Fitzwilliam', 'Moe Castellanos'];
  for (let i = 0; i < names.length; i += 1) {
    const starter = i < 5;
    players.push({
      _id: 'p' + i,
      name: names[i],
      year: ['FR', 'SO', 'JR', 'SR'][i % 4],
      height: 70 + (i % 12),
      weight: 178 + (i * 7) % 60,
      position: ['PG', 'SG', 'SF', 'PF', 'C'][i % 5],
      rt: 58 + (i * 4) % 40,
      potential_rt_ratcheted: 72 + (i * 3) % 28,
      starter: starter,
      lineup_order: starter ? i : null,
      attributes: {
        SC: 20 + (i * 13) % 100, SH: 30 + (i * 7) % 90, ID: 40 + (i * 11) % 80,
        OD: 50 + (i * 5) % 70, PS: 60 + (i * 3) % 60, BH: 25 + (i * 17) % 95,
        RB: 35 + (i * 9) % 85, AG: 45 + (i * 19) % 75, ST: 55 + (i * 23) % 65,
        ND: 65 + (i * 2) % 55, IQ: 75 + (i * 29) % 45, FT: 85 + (i * 31) % 35,
      },
      resolved_training_focus: 'offensive',
      training_focus: 'offensive',
    });
  }
  return {
    team: 'Lancaster',
    is_user_team: true,
    players: players,
    training_squad: [],
    practice_squad_recruits: [],
    projected_starting_five: players.slice(0, 5).map((p) => ({ player_id: p._id })),
  };
}

const OPPONENTS = [
  ['York', 3], ['Four-Corners', 25], ['Bentley-Truman', 26], ['Morristown', 64],
  ['Fairview', 1], ['Kingsport Valley', 118], ['Ashford', 12], ['St. Brendan', 999],
  ['Harbor City', 41], ['Millbrook', 7], ['Crestwood Prep', 88], ['Oak Ridge', 19],
  ['Northgate', 51],
];

function opponentFor(week) {
  const i = (week * 5) % OPPONENTS.length;
  return {
    opponent_id: String(i + 1).padStart(24, 'b'),
    opponent_name: OPPONENTS[i][0],
    opponent_primary_color: '#3a5f8a',
    opponent_natl_rank: OPPONENTS[i][1],
    opponent_wins: (week * 3) % 12,
    opponent_losses: (week * 7) % 9,
  };
}

function teamDetail() {
  const results = [];
  const upcoming = [];
  for (let week = 1; week <= 26; week += 1) {
    const base = Object.assign({ week: week, site: week % 2 ? 'home' : 'away' }, opponentFor(week));
    if (week < 14) {
      const win = (week * 7) % 5 !== 0;
      const a = 58 + ((week * 13) % 24);
      const b = a - 3 - ((week * 5) % 12);
      results.push(Object.assign({}, base, {
        team_score: win ? a : b, opp_score: win ? b : a,
        result: win ? 'W' : 'L', game_id: 'g-' + week,
      }));
    } else {
      upcoming.push(base);
    }
  }
  results.sort((x, y) => y.week - x.week);
  return {
    team_id: TID, name: 'Lancaster', primary_color: '#112233',
    record: { wins: 9, losses: 4 }, natl_rank: 14, conference_place: '2nd of 8', streak: 'W3',
    results: results, next_game: upcoming.shift(), upcoming: upcoming,
    tournament_by_phase: {},
  };
}

function leaders(limit) {
  const count = limit >= 50 ? 30 : 5;
  const body = {};
  STATS.forEach((stat) => {
    const rows = [];
    for (let i = 0; i < count; i += 1) {
      rows.push({
        player_id: stat + '-p' + i,
        name: 'Leader ' + stat + ' ' + (i + 1),
        team: i === 2 ? 'Lancaster' : ('Club ' + (i + 1)),
        team_id: i === 2 ? TID : ('bbbbbbbbbbbbbbbbbbbbbbb' + (i % 10)),
        position: 'G', year: 'JR',
        value: /%$/.test(stat) ? 70 - i : 20 - i,
      });
    }
    body[stat] = rows;
  });
  return body;
}

function cc() {
  return {
    franchise_id: FID, team_id: TID, user_team_id: TID, team: 'Lancaster',
    week: 14, rank: 14, season: 1, current_season: 1,
    training_completed: true, session_type: 'in-season', cut_required: false,
    recruiting_wire: { board_saved_week: 14, counts: {}, events: [] },
    user_conference: 1, user_region: 'A', team_record: '9-4',
    office_digest: {
      state: 'season', todos: [], result: null, next_game: null,
      team_snapshot: null, conference_standings: null,
      recruiting_wire: { events: [] },
      what_moved: {
        national_rank: { now: 14, prev: 16, delta: 2 },
        conference_standing: { now: 2, prev: 2, delta: 0 },
        record: { wins: 9, losses: 4 }, streak: null, attribute_changes: [],
      },
    },
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function installApi(page) {
  await page.route('**/*', async (route) => {
    const request = route.request();
    let url;
    try { url = new URL(request.url()); } catch (err) { await route.continue(); return; }
    const pathname = url.pathname;
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname.startsWith('/player/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) { await route.continue(); return; }
    if (pathname === '/api/auth/me') {
      await fulfillJson(route, { user_id: 'e2e-user', username: 'e2e', email: 'e2e@example.com' });
      return;
    }
    if (pathname === '/app-config') {
      await fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
      return;
    }
    if (pathname === '/teams') {
      await fulfillJson(route, [{ name: 'Lancaster', display_name: 'Lancaster', object_id: TID, _id: TID }]);
      return;
    }
    if (pathname.startsWith('/franchise/command-center/data')) { await fulfillJson(route, cc()); return; }
    if (pathname.startsWith('/franchise/team-data')) { await fulfillJson(route, teamData()); return; }
    if (pathname.startsWith('/franchise/team-detail')) { await fulfillJson(route, teamDetail()); return; }
    if (pathname.startsWith('/franchise/leaders')) {
      await fulfillJson(route, leaders(Number(url.searchParams.get('limit') || '5')));
      return;
    }
    if (pathname.startsWith('/roster/')) { await fulfillJson(route, roster()); return; }
    await fulfillJson(route, {});
  });
}

async function open(page, tab, ready) {
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID + '&tab=' + tab);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector(ready);
  await page.mouse.move(600, 300);
}

/** Every headshot box and its image, as the browser resolves them. */
function headshotRadii(page, scope) {
  return page.locator(scope + ' .av').evaluateAll((nodes) => nodes.map((node) => {
    const img = node.querySelector('img');
    const box = node.getBoundingClientRect();
    return {
      radius: getComputedStyle(node).borderTopLeftRadius,
      imgRadius: img ? getComputedStyle(img).borderTopLeftRadius : null,
      width: Math.round(box.width),
      height: Math.round(box.height),
    };
  }));
}

/**
 * A square headshot: equal sides, and a corner small enough to still read as a
 * corner. A radius at half the side is a circle, and anything past a quarter is
 * already closer to one than to a square.
 */
function assertSquare(shot) {
  expect(shot.radius).not.toBe('50%');
  expect(shot.width).toBe(shot.height);
  expect(parseFloat(shot.radius) / shot.width).toBeLessThanOrEqual(0.25);
  if (shot.imgRadius != null) {
    expect(shot.imgRadius).not.toBe('50%');
    expect(parseFloat(shot.imgRadius) / shot.width).toBeLessThanOrEqual(0.25);
  }
}

test.beforeAll(() => { fs.mkdirSync(OUT, { recursive: true }); });

test.beforeEach(async ({ page }) => {
  await stubAuth(page);
  await installApi(page);
});

for (const [width, height, tag] of SIZES) {
  test('roster reads as three column groups at ' + tag, async ({ page }) => {
    await page.setViewportSize({ width: width, height: height });
    await open(page, 'roster-view', '#roster-view .gob-tbl tbody tr');

    const align = await page.evaluate(() => {
      const read = (sel) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el).textAlign : null;
      };
      return {
        rt: read('#roster-view tbody td.rt'),
        rtHead: read('#roster-view thead th.rt'),
        pos: read('#roster-view tbody td.code'),
        wt: read('#roster-view tbody td.wt'),
        attr: read('#roster-view tbody td.gstart'),
        attrHead: read('#roster-view thead th.gstart'),
        dev: read('#roster-view tbody td.dev'),
      };
    });
    // Current → Pot starts at the column edge; Dev focus keeps its right edge.
    expect(align.rt).toBe('left');
    expect(align.rtHead).toBe('left');
    expect(align.dev).toBe('right');
    // Attribute values centre under their headers.
    expect(align.attr).toBe('center');
    expect(align.attrHead).toBe('center');
    expect(align.pos).toBe('center');
    expect(align.wt).toBe('right');

    // No highlight square: the tier lives in the digit's colour alone.
    const tiles = await page.locator('#roster-view tbody .attr-tile').evaluateAll((nodes) =>
      nodes.slice(0, 24).map((node) => ({
        cls: node.className,
        fill: getComputedStyle(node).backgroundColor,
        ring: getComputedStyle(node).boxShadow,
      })));
    expect(tiles.length).toBeGreaterThan(11);
    expect(tiles.some((tile) => /is-elite|is-hi/.test(tile.cls))).toBe(true);
    tiles.forEach((tile) => {
      expect(tile.fill).toBe('rgba(0, 0, 0, 0)');
      expect(tile.ring).toBe('none');
    });

    // A pair is tight, pairs are spaced. Adjacent table cells touch, so the rhythm
    // lives in the padding: measure between the ink, not between the cell boxes.
    const rhythm = await page.evaluate(() => {
      const row = document.querySelector('#roster-view tbody tr:not(.gob-sep):not(.gob-rep)');
      const cells = Array.from(row.querySelectorAll('td'));
      const ink = (cell) => {
        if (cell.firstElementChild) return cell.firstElementChild.getBoundingClientRect();
        const range = document.createRange();
        range.selectNodeContents(cell);
        return range.getBoundingClientRect();
      };
      const starts = cells.filter((c) => c.classList.contains('gstart'));
      const ends = cells.filter((c) => c.classList.contains('gend'));
      const within = [];
      const between = [];
      starts.forEach((start, i) => {
        const end = ends[i];
        if (!end) return;
        within.push(ink(end).left - ink(start).right);
        if (starts[i + 1]) between.push(ink(starts[i + 1]).left - ink(end).right);
      });
      return {
        pairs: starts.length,
        within: Math.max.apply(null, within),
        between: Math.min.apply(null, between),
        wtGutter: ink(starts[0]).left - ink(cells.find((c) => c.classList.contains('wt'))).right,
      };
    });
    expect(rhythm.pairs).toBe(6);
    // Six pairs, each read as a unit: the gutter between pairs is the wider gap.
    expect(rhythm.between).toBeGreaterThan(rhythm.within);
    // WT no longer crowds SC: the identity block closes wider than a pair is tight.
    expect(rhythm.wtGutter).toBeGreaterThan(rhythm.within);

    // The declared rhythm behind that geometry, read off the cells themselves.
    const pads = await page.evaluate(() => {
      const pad = (sel, side) => {
        const el = document.querySelector('#roster-view tbody ' + sel);
        return parseFloat(getComputedStyle(el)['padding' + side]);
      };
      return {
        wtRight: pad('td.wt', 'Right'),
        pairInner: pad('td.gstart', 'Right'),
        pairOuter: pad('td.gend', 'Right'),
        devLeft: pad('td.dev', 'Left'),
      };
    });
    expect(pads.pairOuter).toBeGreaterThan(pads.pairInner);
    expect(pads.wtRight).toBeGreaterThanOrEqual(pads.pairOuter);
    expect(pads.devLeft).toBeGreaterThanOrEqual(pads.pairOuter);

    const overflow = await page.evaluate(() => {
      const main = document.querySelector('html.gob-shell .main');
      return { main: main.scrollWidth - main.clientWidth, page: document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth };
    });
    expect(overflow.page).toBeLessThanOrEqual(1);
    expect(overflow.main).toBeLessThanOrEqual(1);
    await page.screenshot({ path: path.join(OUT, 'roster-' + tag + '.png') });
  });

  test('team attributes shows twelve measures over the radar at ' + tag, async ({ page }) => {
    await page.setViewportSize({ width: width, height: height });
    await open(page, 'team-attributes-view', '#team-attributes-view .mcell');

    await expect(page.locator('#team-attributes-view .mcell')).toHaveCount(11);
    await expect(page.locator('#team-attributes-view .tm-radar-svg')).toHaveCount(1);

    // One name per measure: the chart's axes read the same as the cells below it.
    const axes = await page.locator('#team-attributes-view .tm-radar-axis-label')
      .evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()).sort());
    const cellNames = await page.locator('#team-attributes-view .mcell .nm')
      .evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()));
    axes.forEach((axis) => { expect(cellNames).toContain(axis); });

    // The radar is neutral. Blue belongs to RT A, attribute 9+ and elite glyphs.
    const radarPaint = await page.locator('#team-attributes-view .tm-radar-svg *')
      .evaluateAll((nodes) => nodes.map((node) => {
        const style = getComputedStyle(node);
        return [style.fill, style.stroke, style.filter].join(' | ');
      }));
    const channels = (text) => (text.match(/rgba?\([^)]*\)/g) || []).map((colour) => {
      const [r, g, b] = (colour.match(/[\d.]+/g) || []).map(Number);
      return Math.max(Math.abs(r - g), Math.abs(g - b), Math.abs(r - b));
    });
    radarPaint.forEach((paint) => {
      channels(paint).forEach((spread) => { expect(spread).toBeLessThanOrEqual(12); });
    });

    // The chart is drawn at its real size, not shrunk to fit its wrapper.
    const chart = await page.locator('#team-attributes-view .tm-radar-svg')
      .evaluate((el) => Math.round(el.getBoundingClientRect().width));
    expect(chart).toBeGreaterThan(300);
    const grid = await page.locator('#team-attributes-view .mgrid').evaluate((el) => ({
      columns: getComputedStyle(el).gridTemplateColumns.split(' ').length,
      rows: getComputedStyle(el).gridTemplateRows.split(' ').length,
    }));
    expect(grid.columns).toBe(4);
    expect(grid.rows).toBe(3);

    // Eleven cells in twelve slots: the bottom right is empty, not a placeholder.
    const bottomRow = await page.locator('#team-attributes-view .mcell').evaluateAll((nodes) => {
      const lowest = Math.max.apply(null, nodes.map((n) => Math.round(n.getBoundingClientRect().top)));
      return nodes.filter((n) => Math.round(n.getBoundingClientRect().top) === lowest)
        .map((n) => n.getAttribute('data-measure'));
    });
    expect(bottomRow).toEqual(['team_chemistry', 'fight', 'discipline']);
    const grid4 = await page.locator('#team-attributes-view .mgrid').evaluate((el) => {
      const cells = Array.from(el.querySelectorAll('.mcell'));
      const lowest = Math.max.apply(null, cells.map((c) => Math.round(c.getBoundingClientRect().top)));
      const last = cells.filter((c) => Math.round(c.getBoundingClientRect().top) === lowest).pop();
      // Nothing is rendered to the right of Discipline in the bottom row.
      return { right: Math.round(last.getBoundingClientRect().right), gridRight: Math.round(el.getBoundingClientRect().right) };
    });
    expect(grid4.gridRight - grid4.right).toBeGreaterThan(80);

    // Pairs share a column: each measure sits above or below its partner.
    const centres = await page.locator('#team-attributes-view .mcell').evaluateAll((nodes) => {
      const out = {};
      nodes.forEach((node) => {
        const box = node.getBoundingClientRect();
        out[node.getAttribute('data-measure')] = Math.round(box.left + box.width / 2);
      });
      return out;
    });
    for (const [a, b] of [
      ['offensive_efficiency', 'defensive_efficiency'],
      ['pt_opp_modifier', 'pt_efficiency'],
      ['fb_efficiency', 'fb_opp_modifier'],
      ['shot_threshold', 'rebound_modifier'],
    ]) {
      expect(Math.abs(centres[a] - centres[b])).toBeLessThanOrEqual(1);
    }

    for (const key of SIGNED_KEYS) {
      await expect(page.locator('#team-attributes-view .mcell[data-measure="' + key + '"] .dv')).toHaveCount(1);
    }
    for (const key of UNSIGNED_KEYS) {
      await expect(page.locator('#team-attributes-view .mcell[data-measure="' + key + '"] .dv')).toHaveCount(0);
      await expect(page.locator('#team-attributes-view .mcell[data-measure="' + key + '"] .gob-meter')).toHaveCount(1);
    }

    // Zero sits in the centre and a negative measure fills to its left.
    const pills = await page.locator('#team-attributes-view .dv').evaluateAll((nodes) => nodes.map((node) => {
      const track = node.getBoundingClientRect();
      const fill = node.querySelector('i').getBoundingClientRect();
      return {
        key: node.closest('.mcell').getAttribute('data-measure'),
        neg: node.classList.contains('neg'),
        centre: Math.round(track.left + track.width / 2),
        left: Math.round(fill.left),
        right: Math.round(fill.right),
      };
    }));
    pills.forEach((pill) => {
      if (pill.neg) expect(Math.abs(pill.right - pill.centre)).toBeLessThanOrEqual(1);
      else expect(Math.abs(pill.left - pill.centre)).toBeLessThanOrEqual(1);
    });
    expect(pills.find((p) => p.key === 'defensive_efficiency').neg).toBe(true);
    expect(pills.find((p) => p.key === 'offensive_efficiency').neg).toBe(false);

    // Movement is neutral. No green or red anywhere in the grid.
    const hues = await page.locator('#team-attributes-view .mgrid *').evaluateAll((nodes) =>
      nodes.map((node) => getComputedStyle(node).color));
    hues.forEach((hue) => {
      const parts = (hue.match(/[\d.]+/g) || []).map(Number);
      const [r, g, b] = parts;
      expect(Math.abs(r - g) < 12 && Math.abs(g - b) < 12).toBe(true);
    });

    // Radar plus all twelve cells inside one screen at both sizes, card edge included.
    const fit = await page.evaluate(() => ({
      sideways: document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth,
      gridBottom: Math.ceil(document.querySelector('#team-attributes-view .mgrid').getBoundingClientRect().bottom),
      viewport: window.innerHeight,
    }));
    expect(fit.sideways).toBeLessThanOrEqual(1);
    expect(fit.gridBottom).toBeLessThanOrEqual(fit.viewport);
    await page.screenshot({ path: path.join(OUT, 'team-attributes-' + tag + '.png') });
  });

  test('team schedule prefixes only the top 25 at ' + tag, async ({ page }) => {
    await page.setViewportSize({ width: width, height: height });
    await open(page, 'team-schedule-view', '#team-schedule-view tr[data-week="1"]');

    const rows = await page.locator('#team-schedule-view tr[data-week] td.team .gob-id > span:first-child')
      .evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()));
    const prefixed = rows.filter((text) => text.charAt(0) === '#');
    expect(prefixed.length).toBeGreaterThan(0);
    prefixed.forEach((text) => {
      const rank = Number(text.slice(1).split(' ')[0]);
      expect(rank).toBeGreaterThanOrEqual(1);
      expect(rank).toBeLessThanOrEqual(25);
    });
    // The fixture carries 26th, 64th, 118th and unranked opponents; none is prefixed.
    for (const name of ['Bentley-Truman', 'Morristown', 'Kingsport Valley', 'St. Brendan']) {
      expect(rows.some((text) => text === name)).toBe(true);
    }
    await page.screenshot({ path: path.join(OUT, 'team-schedule-' + tag + '.png') });
  });

  test('headshots are square on leaders and the roster at ' + tag, async ({ page }) => {
    await page.setViewportSize({ width: width, height: height });
    await open(page, 'leaders-view', '#leaders-view .gob-ldb .av');
    const leaderShots = await headshotRadii(page, '#leaders-view');
    expect(leaderShots.length).toBeGreaterThan(0);
    leaderShots.forEach(assertSquare);
    await page.screenshot({ path: path.join(OUT, 'leaders-' + tag + '.png') });

    await open(page, 'roster-view', '#roster-view .av');
    const rosterShots = await headshotRadii(page, '#roster-view');
    expect(rosterShots.length).toBeGreaterThan(0);
    rosterShots.forEach(assertSquare);
  });
}

/**
 * The Training Report needs a whole week's payload to render, so this mounts its two
 * real headshot components against their real stylesheets. The shape is the point.
 */
for (const [width, height, tag] of SIZES) {
  test('training report headshots are square at ' + tag, async ({ page }) => {
    await page.setViewportSize({ width: width, height: height });
    // Served from the origin so the real stylesheets resolve, without the Training
    // Report's own script, which redirects away when there is no franchise loaded.
    await page.unrouteAll({ behavior: 'ignoreErrors' });
    await page.route('**/e2e-headshot-harness.html', (route) => route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: `<!doctype html><html><head><meta charset="utf-8">
      <link rel="stylesheet" href="/training-report.css">
      <link rel="stylesheet" href="/css/training-newswire.css">
      </head><body class="training-report-page" style="background:#0b0d14;padding:40px;display:flex;gap:48px;align-items:center;
        --notes-accent:#4A90D9;--notes-accent-border:rgba(74,144,217,.5);--notes-accent-tint:rgba(74,144,217,.16)">
      <div class="training-notes-hero-portrait">
        <div class="training-notes-hero-portrait-fallback">AK</div>
      </div>
      <div class="training-notes-hero-portrait">
        <img class="training-notes-hero-portrait-img" alt="" src="/images/players/generic_headshot.png">
      </div>
      <div class="wr-row wr-row-plr"><span class="wr-rk">1</span>
        <span class="wr-hs"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 22c0-5 4-8 8-8s8 3 8 8z"/></svg></span>
        <span class="wr-plr"><b>Ada Keeper</b><em>PG &middot; FR</em></span><span class="wr-val">+4</span></div>
      </body></html>`,
    }));
    await page.goto('/e2e-headshot-harness.html');
    await page.waitForFunction(() => document.styleSheets.length >= 2
      && getComputedStyle(document.querySelector('.wr-hs')).borderTopLeftRadius !== '0px');

    const shots = await page.evaluate(() => {
      const sel = ['.training-notes-hero-portrait-fallback', '.training-notes-hero-portrait-img', '.wr-hs'];
      return sel.map((s) => {
        const el = document.querySelector(s);
        const box = el.getBoundingClientRect();
        return {
          selector: s,
          radius: getComputedStyle(el).borderTopLeftRadius,
          width: Math.round(box.width),
          height: Math.round(box.height),
          imgRadius: null,
        };
      });
    });
    expect(shots).toHaveLength(3);
    shots.forEach((shot) => {
      expect(shot.width, shot.selector).toBeGreaterThan(0);
      assertSquare(shot);
    });
    await page.screenshot({ path: path.join(OUT, 'training-report-' + tag + '.png') });
  });
}

test('no player headshot rule in the shell resolves to a circle', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await open(page, 'roster-view', '#roster-view .av');
  const round = await page.evaluate(() => {
    const hits = [];
    Array.from(document.styleSheets).forEach((sheet) => {
      let rules;
      try { rules = sheet.cssRules; } catch (err) { return; }
      Array.from(rules || []).forEach((rule) => {
        if (!rule.selectorText || !rule.style) return;
        const radius = rule.style.getPropertyValue('border-radius');
        if (!radius) return;
        const round = /50%|var\(--radius-round\)/.test(radius);
        const headshot = /\.av\b|headshot|portrait/.test(rule.selectorText);
        if (round && headshot) hits.push(rule.selectorText + ' { border-radius: ' + radius + ' }');
      });
    });
    return hits;
  });
  expect(round).toEqual([]);
});
