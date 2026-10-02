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
 * Both stories are recorded from a real offline season: `new_shape` was written after
 * the section became team blocks, `old_shape` before, as plain lines.
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

async function shots(page, name, focus) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(size);
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.locator(focus).first().evaluate((node) => node.scrollIntoView({ block: 'start' }));
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
    const link = team.locator('h3.gob-news-team-h a.gob-team');
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
