const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * News › the weekly Recruiting Report story. The lean announcements sit under their two
 * sub-headings with no outer "Recruiting Leans Announced" heading, and under
 * "Conference X Lean Announcements" each team is a sub-heading (mark and name, linking to
 * the team page) over its recruits, one per row, name then RT in the canonical ramp.
 *
 * The rankings: team rows are team links, the user's team is the navy "yours" row (with
 * its own foot row when it is outside the national table), rank movement since last week
 * is a neutral mark beside the rank, one quiet caption says what Score is, and National
 * and Region sit side by side from 1600px. Headings are the app's heading styles.
 *
 * The stories are recorded from a real offline season: `old_shape` (week 4) has the lean
 * section as plain lines, `new_shape` (week 5) as team blocks, and `with_movement`
 * (week 9) also has named tables, stored movement, the foot row and the caption.
 * TPL_SHOTS=1 also writes reports/team-page-links/after-recruiting-report-*.png.
 */
test.describe.configure({ timeout: 120000 });

const SHOTS = process.env.TPL_SHOTS === '1';
const OUT = path.join(__dirname, '../../reports/team-page-links');
const GAME = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/boxscore-real-game.json'), 'utf8'));
const TEAM = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/team-page-real-results.json'), 'utf8'));
const STORIES = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/recruiting-report-real-stories.json'), 'utf8'));
const HUB = '/franchise-command-center.html?franchise_id=' + GAME.franchise_id + '&team_id=' + GAME.team_id;
const OUTER = 'Recruiting Leans Announced';

const json = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

async function openStory(page, story) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let url;
    try { url = new URL(route.request().url()); } catch (err) { return route.continue(); }
    const pathname = url.pathname;
    if (pathname.indexOf('/images/players/') !== -1) return route.fulfill({ status: 404, body: '' });
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/app-config' || pathname === '/teams';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return json(route, []);
    if (pathname.startsWith('/franchise/command-center/data')) return json(route, GAME.command_center);
    if (pathname.startsWith('/franchise/news')) return json(route, { week: 6, news: [story], dispatches: [] });
    if (pathname.startsWith('/franchise/team-detail')) return json(route, TEAM.team_detail_opponent);
    if (pathname.startsWith('/roster/')) return json(route, GAME.roster_opponent);
    return json(route, {});
  });
  await page.goto(HUB + '&tab=news-view&story=' + encodeURIComponent(story.story_id));
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#news-view .gob-news-story .gob-news-body', { timeout: 20000 });
}

async function shots(page, name, focus, sizes) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  for (const size of sizes || [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(size);
    await page.evaluate(() => document.fonts && document.fonts.ready);
    if (focus === 'top') {
      await page.locator('html.gob-shell .main').evaluate((node) => { node.scrollTop = 0; });
    } else {
      await page.locator(focus).first().evaluate((node) => node.scrollIntoView({ block: 'start' }));
    }
    await page.mouse.move(0, 0);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, 'after-' + name + '-' + size.width + '.png'), animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

test('the recorded stories are the two stored shapes', () => {
  const fresh = STORIES.new_shape.rich_lines;
  expect(fresh.some((line) => line.type === 'team_recruits')).toBe(true);
  expect(fresh.some((line) => line.text === OUTER)).toBe(false);
  const old = STORIES.old_shape.rich_lines;
  expect(old.some((line) => line.type === 'team_recruits')).toBe(false);
  expect(old.some((line) => line.type === 'heading' && line.text === OUTER)).toBe(true);
  const moved = STORIES.with_movement.rich_lines.filter((line) => line.type === 'ranking_table');
  expect(moved.map((table) => table.table)).toEqual(['national', 'region']);
  const rows = moved[0].rows;
  // The real week has all four cases in the national table.
  expect(rows.some((row) => row.move > 0)).toBe(true);
  expect(rows.some((row) => row.move < 0)).toBe(true);
  expect(rows.some((row) => row.move === 0)).toBe(true);
  expect(rows.some((row) => row.new === true)).toBe(true);
  expect(moved[0].user_row.team_id).toBe(GAME.team_id);
});

test('Recruiting Report: no outer heading, and each conference team is a sub-heading over its recruits', async ({ page }) => {
  const story = STORIES.new_shape;
  const blocks = story.rich_lines.filter((line) => line.type === 'team_recruits');
  await openStory(page, story);
  const body = page.locator('#news-view .gob-news-body');

  // The two sub-headings stay; the heading that wrapped them is gone.
  const headings = await body.locator('.gob-news-heading').allTextContents();
  expect(headings).toContain('Top Rated Recruit Announcements');
  expect(headings.some((text) => /^Conference .+ Lean Announcements$/.test(text))).toBe(true);
  expect(headings).not.toContain(OUTER);
  await expect(body).not.toContainText(OUTER);

  // One block per team, in the stored order (national rank), the team as a sub-heading.
  const teams = body.locator('.gob-news-team');
  await expect(teams).toHaveCount(blocks.length);
  expect(blocks.length).toBeGreaterThan(1);
  for (let i = 0; i < blocks.length; i += 1) {
    const block = blocks[i];
    const team = teams.nth(i);
    const link = team.locator('h4.gob-news-team-h a.gob-team');
    await expect(link).toHaveText(block.team_name);
    await expect(link.locator('img, .gob-mark')).toHaveCount(1);            // the logo mark
    const href = new URL(await link.getAttribute('href'), 'http://x');
    expect(href.searchParams.get('tab')).toBe('team-view');
    expect(href.searchParams.get('view_team_id')).toBe(block.team_id);

    // Its recruits: one per row, name then RT, in the stored order (RT descending).
    const rows = team.locator('ul.gob-news-recruits > li');
    await expect(rows).toHaveCount(block.recruits.length);
    const drawn = await rows.evaluateAll((nodes) => nodes.map((node) => {
      const rt = node.querySelector('.gob-news-rt');
      return {
        name: node.querySelector('.gob-news-recruit').textContent,
        rt: rt.textContent,
        cls: rt.className,
        colour: getComputedStyle(rt).color,
        nameLeft: node.querySelector('.gob-news-recruit').getBoundingClientRect().left,
        rtLeft: rt.getBoundingClientRect().left,
        top: node.getBoundingClientRect().top,
      };
    }));
    const expected = await page.evaluate((recruits) => recruits.map((recruit) => {
      const probe = document.createElement('span');
      probe.className = window.getRtBucketClass(recruit.rt);
      document.body.appendChild(probe);
      const colour = getComputedStyle(probe).color;
      probe.remove();
      return { name: recruit.name, rt: window.formatRtDisplay(recruit.rt), cls: window.getRtBucketClass(recruit.rt), colour };
    }), block.recruits);
    drawn.forEach((row, index) => {
      expect(row.name).toBe(expected[index].name);
      expect(row.rt).toBe(expected[index].rt);                              // the letter, not the number
      expect(row.cls).toContain(expected[index].cls);
      expect(row.colour).toBe(expected[index].colour);                      // the canonical ramp
      expect(row.rtLeft).toBeGreaterThan(row.nameLeft);                     // name, then RT
      if (index) expect(row.top).toBeGreaterThan(drawn[index - 1].top);     // one recruit per line
    });
    const ratings = block.recruits.map((recruit) => recruit.rt);
    expect(ratings).toEqual(ratings.slice().sort((a, b) => b - a));

    // A recruit sits under the team name, indented past the mark, and is not a heading.
    const nameLeft = await link.locator('span').last().evaluate((node) => node.getBoundingClientRect().left);
    expect(drawn[0].nameLeft).toBeGreaterThan(await team.evaluate((node) => node.getBoundingClientRect().left));
    expect(Math.abs(drawn[0].nameLeft - nameLeft)).toBeLessThanOrEqual(2);
    const weights = await team.evaluate((node) => ({
      team: Number(getComputedStyle(node.querySelector('.gob-news-team-h')).fontWeight),
      recruit: Number(getComputedStyle(node.querySelector('.gob-news-recruit')).fontWeight),
    }));
    expect(weights.team).toBeGreaterThan(weights.recruit);
  }
  // No recruit name is a link (no news story links a recruit).
  await expect(body.locator('.gob-news-recruits a')).toHaveCount(0);
  // The top-rated sentences are unchanged text lines.
  const top = story.rich_lines.filter((line) => line.type === 'text');
  for (const line of top) await expect(body.locator('.gob-news-line', { hasText: line.text })).toHaveCount(1);
  await shots(page, 'recruiting-report', '.gob-news-heading:has-text("Top Rated")');

  // The team heading opens that team's page.
  await teams.first().locator('a.gob-team').click();
  await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000 }).toBe('team-view');
  expect(new URL(page.url()).searchParams.get('view_team_id')).toBe(blocks[0].team_id);
  await expect(page.locator('#team-view .gob-hero-n')).toBeVisible({ timeout: 20000 });
});

test('a Recruiting Report stored in the old plain-line shape still renders, without the outer heading', async ({ page }) => {
  const story = STORIES.old_shape;
  await openStory(page, story);
  const body = page.locator('#news-view .gob-news-body');
  const headings = await body.locator('.gob-news-heading').allTextContents();
  expect(headings).toContain('Top Rated Recruit Announcements');
  expect(headings.some((text) => /^Conference .+ Lean Announcements$/.test(text))).toBe(true);
  expect(headings).not.toContain(OUTER);
  // Every stored text line is drawn as a line, as before; there are no team blocks to draw.
  await expect(body.locator('.gob-news-team')).toHaveCount(0);
  const lines = story.rich_lines.filter((line) => line.type === 'text').map((line) => line.text);
  expect(lines.length).toBeGreaterThan(4);
  const drawn = await body.locator('p.gob-news-line:not(.gob-news-heading)').allTextContents();
  expect(drawn).toEqual(lines);
  await expect(body.locator('table.gob-tbl').first()).toBeVisible();
  await shots(page, 'recruiting-report-old-shape', '.gob-news-heading:has-text("Top Rated")');
});

// ── Rankings: team links, the "yours" row, movement, the caption, the layout ──
const MOVED = STORIES.with_movement;
const NATIONAL = MOVED.rich_lines.find((line) => line.table === 'national');
const REGION = MOVED.rich_lines.find((line) => line.table === 'region');

/** One drawn ranking row, by team id. */
function drawnRows(section) {
  return section.locator('table.gob-news-rank-tbl tbody tr').evaluateAll((nodes) => nodes.map((row) => {
    const link = row.querySelector('td.team a.gob-team');
    const mark = row.querySelector('.gob-news-mv');
    return {
      team: link ? new URL(link.getAttribute('href'), 'http://x').searchParams.get('view_team_id') : '',
      name: link ? link.querySelector('span:last-child').textContent.trim() : row.querySelector('td.team').textContent.trim(),
      logo: !!row.querySelector('td.team img, td.team .gob-mark'),
      rank: row.querySelector('.gob-news-rkn').textContent,
      move: mark ? mark.textContent : null,
      moveClass: mark ? mark.className : '',
      moveColour: mark ? getComputedStyle(mark).color : '',
      mine: row.classList.contains('me'),
      foot: row.classList.contains('is-foot'),
      score: row.lastElementChild.textContent,
    };
  }));
}

function expectedMark(row) {
  if (row.new === true) return 'NEW';
  if (!row.move) return '';
  return (row.move > 0 ? '▲' : '▼') + Math.abs(row.move);
}

test('Recruiting Report rankings: team links, the yours row, movement marks, the caption, no Week subhead', async ({ page }) => {
  await openStory(page, MOVED);
  const story = page.locator('#news-view .gob-news-story');
  const body = story.locator('.gob-news-body');

  // The headline names the week; nothing repeats it underneath.
  await expect(story.locator('.gob-news-headline')).toHaveText('Week 9 Recruiting Report');
  await expect(story.locator('.gob-news-meta')).toHaveCount(0);
  await expect(story).not.toContainText(/^\s*Week 9\s*$/m);

  // The conference is named the way the rest of the app names it.
  const headings = await body.locator('h3.gob-news-heading').allTextContents();
  expect(headings).toEqual([
    'National Recruit Rankings', 'Region A', 'Top Rated Recruit Announcements', 'Conference A1 Lean Announcements',
  ]);

  const sections = body.locator('.gob-news-ranks section.gob-news-rank');
  await expect(sections).toHaveCount(2);
  const national = sections.nth(0);
  const region = sections.nth(1);

  // One quiet caption, under National Recruit Rankings only, saying what Score is.
  await expect(body.locator('.gob-news-caption')).toHaveCount(1);
  await expect(national.locator('.gob-news-caption')).toHaveText(NATIONAL.caption);
  expect(NATIONAL.caption).toMatch(/first choice counts in full, a second choice half, a third a quarter/);
  const caption = await national.locator('.gob-news-caption').evaluate((node) => ({
    colour: getComputedStyle(node).color,
    size: parseFloat(getComputedStyle(node).fontSize),
    below: node.previousElementSibling.className,
  }));
  expect(caption.below).toContain('gob-news-heading');
  expect(caption.colour).toMatch(/^rgba\(255, 255, 255, 0\.6\d*\)$/);
  expect(caption.size).toBeLessThan(14);

  // National: every stored row, in order, then the user's own row at the foot.
  const drawn = await drawnRows(national);
  const stored = NATIONAL.rows.concat([NATIONAL.user_row]);
  expect(drawn.length).toBe(stored.length);
  drawn.forEach((row, index) => {
    const want = stored[index];
    expect(row.team, want.team).toBe(want.team_id);                    // links to the team page
    expect(row.name).toBe(want.team);
    expect(row.logo, want.team).toBe(true);                            // the logo mark
    expect(row.rank).toBe(String(want.rank));
    expect(row.score).toBe(String(want.score));
    expect(row.move, want.team).toBe(expectedMark(want));
    expect(row.foot).toBe(index === stored.length - 1);
  });
  // A team that rose, one that fell, one unchanged, one new: the real week has each.
  const rose = NATIONAL.rows.find((row) => row.move > 0);
  const fell = NATIONAL.rows.find((row) => row.move < 0);
  const held = NATIONAL.rows.find((row) => row.move === 0);
  const fresh = NATIONAL.rows.find((row) => row.new === true);
  const byTeam = {};
  drawn.forEach((row) => { byTeam[row.team] = row; });
  expect(byTeam[rose.team_id].move).toBe('▲' + rose.move);
  expect(byTeam[fell.team_id].move).toBe('▼' + Math.abs(fell.move));
  expect(byTeam[held.team_id].move).toBe('');
  expect(byTeam[fresh.team_id].move).toBe('NEW');
  // Neutral both ways: up is t87, down and NEW are t60. Never green or red.
  expect(byTeam[rose.team_id].moveColour).toMatch(/^rgba\(255, 255, 255, 0\.87\d*\)$/);
  expect(byTeam[fell.team_id].moveColour).toMatch(/^rgba\(255, 255, 255, 0\.6\d*\)$/);
  expect(byTeam[fresh.team_id].moveColour).toMatch(/^rgba\(255, 255, 255, 0\.6\d*\)$/);

  // The user's team is outside the top 25: its row is at the foot, with its real rank,
  // its own movement, and the navy "yours" treatment.
  const foot = drawn[drawn.length - 1];
  expect(foot).toMatchObject({ team: GAME.team_id, name: 'Lancaster', rank: String(NATIONAL.user_row.rank), mine: true, foot: true });
  expect(foot.move).toBe('▲' + NATIONAL.user_row.move);
  expect(drawn.filter((row) => row.mine).length).toBe(1);
  expect(drawn.filter((row) => row.foot).length).toBe(1);
  const paint = await national.locator('tr.is-foot').evaluate((row) => {
    const other = row.parentElement.querySelector('tr:not(.me)');
    return { mine: getComputedStyle(row.cells[1]).backgroundColor, other: getComputedStyle(other.cells[1]).backgroundColor };
  });
  expect(paint.mine).not.toBe(paint.other);

  // Region: the user's team is in the table, so it is the "yours" row there and there
  // is no foot row. Movement is against last week's region table.
  const regional = await drawnRows(region);
  expect(regional.length).toBe(REGION.rows.length);
  regional.forEach((row, index) => {
    expect(row.team).toBe(REGION.rows[index].team_id);
    expect(row.move, row.name).toBe(expectedMark(REGION.rows[index]));
    expect(row.foot).toBe(false);
  });
  expect(regional.filter((row) => row.mine).map((row) => row.name)).toEqual(['Lancaster']);

  // A team row opens that team's page.
  await national.locator('td.team a.gob-team').first().click();
  await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000 }).toBe('team-view');
  expect(new URL(page.url()).searchParams.get('view_team_id')).toBe(NATIONAL.rows[0].team_id);
});

test('story headings are the app\'s heading styles: a section level and a smaller sub-section level', async ({ page }) => {
  await openStory(page, MOVED);
  const body = page.locator('#news-view .gob-news-body');
  // No bold body text standing in for a heading.
  await expect(body.locator('p > strong, .gob-news-line strong')).toHaveCount(0);
  const type = await body.evaluate((root) => {
    const read = (node) => {
      const style = getComputedStyle(node);
      return { tag: node.tagName, family: style.fontFamily, size: parseFloat(style.fontSize), colour: style.color };
    };
    return {
      sections: [...root.querySelectorAll('.gob-news-heading')].map(read),
      subs: [...root.querySelectorAll('.gob-news-sub')].map(read),
      line: read(root.querySelector('p.gob-news-line')),
      display: getComputedStyle(document.documentElement).getPropertyValue('--font-display').trim(),
    };
  });
  expect(type.sections.length).toBe(4);
  expect(type.subs.length).toBeGreaterThan(0);                              // the teams under the conference
  const face = type.display.split(',')[0].replace(/["']/g, '').trim();
  type.sections.forEach((heading) => {
    expect(heading.tag).toBe('H3');
    expect(heading.family).toContain(face);                                 // the display face
    expect(heading.size).toBe(type.sections[0].size);                       // one level
    expect(heading.family).not.toBe(type.line.family);
  });
  type.subs.forEach((heading) => {
    expect(heading.tag).toBe('H4');
    expect(heading.family).toContain(face);
    expect(heading.size).toBe(type.subs[0].size);
    expect(heading.size).toBeLessThan(type.sections[0].size);               // the smaller level
  });
});

test('rankings sit side by side from 1600px and stack below it; the leans follow beneath', async ({ page }) => {
  await openStory(page, MOVED);
  const layout = () => page.evaluate(() => {
    const box = (node) => { const r = node.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom }; };
    const sections = [...document.querySelectorAll('#news-view .gob-news-rank')].map(box);
    const main = document.querySelector('html.gob-shell .main');
    return {
      national: sections[0],
      region: sections[1],
      leans: box([...document.querySelectorAll('#news-view .gob-news-heading')].find((node) => /Top Rated/.test(node.textContent))),
      overflow: main.scrollWidth - main.clientWidth,
      wraps: [...document.querySelectorAll('#news-view .gob-news-rank-tbl td.team')].filter((cell) => cell.getBoundingClientRect().height > 60).length,
    };
  });
  for (const size of [{ width: 1280, height: 720 }, { width: 1599, height: 900 }]) {
    await page.setViewportSize(size);
    await page.waitForTimeout(250);
    const stacked = await layout();
    expect(stacked.region.top, 'stacked at ' + size.width).toBeGreaterThanOrEqual(stacked.national.bottom);
    expect(Math.abs(stacked.region.left - stacked.national.left)).toBeLessThanOrEqual(1);
    expect(stacked.leans.top).toBeGreaterThanOrEqual(stacked.region.bottom);
    expect(stacked.overflow).toBeLessThanOrEqual(0);
  }
  for (const size of [{ width: 1600, height: 900 }, { width: 1920, height: 1080 }, { width: 2048, height: 1152 }, { width: 2560, height: 1440 }]) {
    await page.setViewportSize(size);
    await page.waitForTimeout(250);
    const side = await layout();
    expect(Math.abs(side.region.top - side.national.top), 'side by side at ' + size.width).toBeLessThanOrEqual(1);
    expect(side.region.left).toBeGreaterThanOrEqual(side.national.right);
    // The lean sections follow beneath both tables.
    expect(side.leans.top).toBeGreaterThanOrEqual(Math.max(side.national.bottom, side.region.bottom));
    expect(side.overflow, 'no sideways scroll at ' + size.width).toBeLessThanOrEqual(0);
    expect(side.wraps, 'no team name wraps at ' + size.width).toBe(0);
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  await shots(page, 'recruiting-report-rankings', 'top', [
    { width: 1280, height: 720 }, { width: 1920, height: 1080 }, { width: 2000, height: 1125 },
  ]);
});

test('stories stored without movement, caption or foot row show none, and keep the team links', async ({ page }) => {
  for (const story of [STORIES.old_shape, STORIES.new_shape]) {
    await page.unroute('**/*');
    await openStory(page, story);
    const body = page.locator('#news-view .gob-news-body');
    await expect(page.locator('#news-view .gob-news-meta')).toHaveCount(0);
    await expect(body.locator('.gob-news-mv')).toHaveCount(0);
    await expect(body.locator('.gob-news-caption')).toHaveCount(0);
    await expect(body.locator('tr.is-foot')).toHaveCount(0);
    const tables = story.rich_lines.filter((line) => line.type === 'ranking_table');
    const rows = tables.reduce((all, table) => all.concat(table.rows), []);
    await expect(body.locator('table.gob-news-rank-tbl tbody tr')).toHaveCount(rows.length);
    await expect(body.locator('table.gob-news-rank-tbl td.team a.gob-team')).toHaveCount(rows.length);
    // The user's team is still the "yours" row wherever it is listed.
    const mine = rows.filter((row) => row.team_id === GAME.team_id).length;
    expect(mine).toBeGreaterThan(0);
    await expect(body.locator('table.gob-news-rank-tbl tr.me')).toHaveCount(mine);
  }
});

test('another kind of story keeps its "Week N" line', async ({ page }) => {
  await openStory(page, {
    story_id: 'w3-upset-report', week: 3, type: 'upset_report', headline: 'Week 3 Upset Report',
    lines: ['Redwood High upset Pacific All-Stars by a score of 71-66.'],
  });
  await expect(page.locator('#news-view .gob-news-meta')).toHaveText('Week 3');
});
