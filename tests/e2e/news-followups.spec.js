const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * News follow-ups.
 *
 * - Upset Report: each line with a stored game carries a "Box Score" link that opens the
 *   game as a read; Back returns to the story. A story stored without games has no link.
 * - No "Week N" line under a headline that already names the week, whatever the story.
 * - Every rail item leaves a drill-in: a team or player page, a news story, a box score
 *   opened to read, a practice-squad roster. The lit item too.
 *
 * The Upset Report stories are recorded from a real offline season: `with_games` (week 9)
 * was written after lines began storing their game, `without_games` (week 8) before.
 * NF_SHOTS=1 also writes reports/news-followups/after-*.png at 1280 and 1920.
 */
test.describe.configure({ timeout: 120000 });

const SHOTS = process.env.NF_SHOTS === '1';
const OUT = path.join(__dirname, '../../reports/news-followups');
const GAME = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/boxscore-real-game.json'), 'utf8'));
const TEAM = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/team-page-real-results.json'), 'utf8'));
const UPSETS = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/upset-report-real-stories.json'), 'utf8'));
const IDENTITY = 'franchise_id=' + GAME.franchise_id + '&team_id=' + GAME.team_id;
const HUB = '/franchise-command-center.html?' + IDENTITY;

const json = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

/** The recorded season, with `stories` as the news feed. Any game id answers with the recorded game. */
async function install(page, stories) {
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
    if (pathname.startsWith('/franchise/news')) return json(route, { week: 10, news: stories || [], dispatches: [] });
    if (pathname.startsWith('/franchise/team-detail')) {
      return json(route, url.searchParams.get('team_id') === GAME.team_id ? GAME.team_detail : TEAM.team_detail_opponent);
    }
    if (pathname.startsWith('/franchise/schedule/week')) return json(route, TEAM.schedule_week_3);
    if (/^\/api\/game\/[0-9a-f]{24}\/resume-state$/.test(pathname)) return json(route, GAME.resume_state);
    if (/^\/api\/game\/[0-9a-f]{24}$/.test(pathname)) return json(route, GAME.game);
    if (pathname.startsWith('/roster/')) {
      return json(route, pathname.indexOf(GAME.opponent_id) !== -1 ? GAME.roster_opponent : GAME.roster_user);
    }
    return json(route, {});
  });
}

async function boot(page, url, ready) {
  await page.goto(url);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector(ready, { timeout: 20000 });
  // The rail widens under the pointer and covers the page's left edge.
  await page.mouse.move(800, 500);
}

async function shots(page, name) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  for (const size of [{ width: 1280, height: 720 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(size);
    await page.mouse.move(size.width - 6, size.height - 6);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(OUT, 'after-' + name + '-' + size.width + '.png'), animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.mouse.move(800, 500);
}

const storyUrl = (id) => HUB + '&tab=news-view&story=' + encodeURIComponent(id);

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

// ── Upset Report ─────────────────────────────────────────────────────────────
test('the recorded Upset Reports are the two stored shapes', () => {
  const stored = UPSETS.with_games.rich_lines;
  expect(stored.length).toBeGreaterThan(1);
  stored.forEach((line) => {
    expect(line.type).toBe('game_result');
    expect(String(line.game_id)).toMatch(/^[0-9a-f]{24}$/);
  });
  expect(stored.map((line) => line.text)).toEqual(UPSETS.with_games.lines);
  expect(UPSETS.without_games.rich_lines).toBeUndefined();
  expect(UPSETS.without_games.lines.length).toBeGreaterThan(0);
});

test('Upset Report: each line links its game\'s box score as a read, and Back returns to the story', async ({ page }) => {
  const story = UPSETS.with_games;
  await install(page, [story]);
  await boot(page, storyUrl(story.story_id), '#news-view .gob-news-story .gob-news-line');
  const lines = page.locator('#news-view .gob-news-body p.gob-news-line');
  await expect(lines).toHaveCount(story.rich_lines.length);
  for (let i = 0; i < story.rich_lines.length; i += 1) {
    const stored = story.rich_lines[i];
    const line = lines.nth(i);
    await expect(line).toContainText(stored.text);
    const link = line.locator('a.lnk');
    await expect(link).toHaveCount(1);
    await expect(link).toHaveText('Box Score');
    expect(await link.evaluate((node) => node.hasAttribute('data-return'))).toBe(true);
    const href = new URL(await link.getAttribute('href'), 'http://x');
    expect(href.pathname).toBe('/box-score.html');
    expect(href.searchParams.get('game_id')).toBe(stored.game_id);
    expect(href.searchParams.get('franchise_id')).toBe(GAME.franchise_id);
    expect(href.searchParams.get('team_id')).toBe(GAME.team_id);
  }
  await shots(page, 'upset-report');

  await lines.first().locator('a.lnk').click();
  await expect(page).toHaveURL(/\/box-score\.html\?/, { timeout: 15000 });
  await page.waitForSelector('#home-player-stats-body tr', { timeout: 20000 });
  // The closed-game guard would send it back within a second or two: it does not.
  await page.waitForTimeout(3500);
  const here = new URL(page.url());
  expect(here.pathname).toBe('/box-score.html');
  expect(here.searchParams.get('game_id')).toBe(story.rich_lines[0].game_id);
  expect(here.searchParams.get('return_url')).toContain('story=' + story.story_id);

  await page.locator('#locker-room-button').click();
  await expect(page).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
  await expect(page.locator('#news-view.tab-content.active .gob-news-headline')).toHaveText(story.headline, { timeout: 20000 });
  expect(new URL(page.url()).searchParams.get('story')).toBe(story.story_id);
});

test('Upset Report stored without games: the lines, and no link', async ({ page }) => {
  const story = UPSETS.without_games;
  await install(page, [story]);
  await boot(page, storyUrl(story.story_id), '#news-view .gob-news-story .gob-news-line');
  const drawn = await page.locator('#news-view .gob-news-body p.gob-news-line').allTextContents();
  expect(drawn).toEqual(story.lines);
  await expect(page.locator('#news-view .gob-news-body a')).toHaveCount(0);
  await shots(page, 'upset-report-stored-without-games');
});

// ── The "Week N" line ────────────────────────────────────────────────────────
const line = (text) => ({ type: 'text', text });
const WEEK_LINE = [
  // [type, week, headline, the "Week N" line is shown]
  ['upset_report', 9, 'Week 9 Upset Report', false],
  ['recruiting_report', 9, 'Week 9 Recruiting Report', false],
  ['ps_game_results', 4, 'Week 4 Practice Squad Game Results', false],
  ['all_americans', 7, 'Projected All-Americans: week 7', false],
  // "Preseason" names week 1 in words (Jamie, 2026-10-02).
  ['all_americans', 1, 'Preseason All-Americans announced', false],
  // "end of the regular season" names week 26 in words (Jamie, 2026-10-02).
  ['all_americans', 26, 'Projected All-Americans: end of the regular season', false],
  ['all_conference', 26, 'All-Conference A2: end of the regular season', false],
  ['all_conference', 7, 'Projected All-Conference A2: week 7', false],
  ['all_conference', 1, 'Preseason All-Conference A2 teams', false],
  // A later story that happens to say "preseason" keeps its line: only week 1 is the preseason.
  ['ps_all_stars', 5, 'Preseason form carries into week five', true],
  ['ps_all_stars', 3, 'Practice Squad All-Stars', true],
  ['recruiting_movement', 3, 'Your Recruiting Board Moved', true],
  ['walk_ons_announced', 1, 'Lancaster Walk Ons Announced', true],
  ['recruiting_results', 36, 'Season 1 Recruiting Results', true],
  ['recruiting_leans', 5, 'Updated Recruiting Leans Announced', true],
  // The headline names a different week from the story's own: nothing is repeated.
  ['upset_report', 12, 'Week 2 Upset Report', true],
];

test('no "Week N" line under a headline that already names the week', async ({ page }) => {
  const stories = WEEK_LINE.map((row, index) => ({
    story_id: 'wk-' + index, type: row[0], week: row[1], headline: row[2], rich_lines: [line('Body of story ' + index + '.')],
  }));
  await install(page, stories);
  for (let i = 0; i < WEEK_LINE.length; i += 1) {
    const [type, week, headline, shown] = WEEK_LINE[i];
    if (i === 0) await boot(page, storyUrl('wk-0'), '#news-view .gob-news-story .gob-news-headline');
    else {
      await page.evaluate((url) => window.GOBViews.open(url, 'replace'), storyUrl('wk-' + i));
      await expect(page.locator('#news-view .gob-news-headline')).toHaveText(headline);
    }
    const meta = page.locator('#news-view .gob-news-story .gob-news-meta');
    if (shown) await expect(meta, type + ' "' + headline + '"').toHaveText('Week ' + week);
    else await expect(meta, type + ' "' + headline + '"').toHaveCount(0);
    await expect(page.locator('#news-view .gob-news-body')).toContainText('Body of story ' + i + '.');
  }
});

// ── The rail from drill-ins ──────────────────────────────────────────────────
const SECTIONS = [
  ['office', 'home-tab'],
  ['team', 'roster-view'],
  ['prep', 'training-view'],
  ['league', 'standings-view'],
  ['news', 'news-view'],
];
const TEAM_PAGE = '&tab=team-view&view_team_id=' + GAME.opponent_id;
const RETURN = encodeURIComponent(HUB + '&tab=team-schedule-view');
const DRILL_INS = [
  // [name, url, ready, the rail item it lights]
  ['a team page opened from the Office', HUB + TEAM_PAGE + '&return_tab=home-tab&origin=office', '#team-view .gob-hero-n', 'office'],
  ['a team page opened from Standings', HUB + TEAM_PAGE + '&return_tab=standings-view&origin=league', '#team-view .gob-hero-n', 'league'],
  ['a player page opened from the roster', HUB + '&tab=player-view&player_id=p1&return_tab=roster-view&origin=team', '#player-view', 'team'],
  ['a player page opened from the Office', HUB + '&tab=player-view&player_id=p1&return_tab=home-tab&origin=office', '#player-view', 'office'],
  ['a news story', storyUrl(UPSETS.with_games.story_id), '#news-view .gob-news-story', 'news'],
  ['a box score opened to read', '/box-score.html?game_id=' + GAME.game_id + '&mode=franchise&' + IDENTITY + '&return_url=' + RETURN, '#home-player-stats-body tr', 'league'],
  ['a practice-squad roster page', '/team-roster-view.html?mode=practice_squad&ps_team_id=x&' + IDENTITY, '.rail [data-gob-section]', 'team'],
];

for (const [name, url, ready, lit] of DRILL_INS) {
  test('every rail item leaves ' + name + ', the lit one too', async ({ page }) => {
    await install(page, [UPSETS.with_games]);
    for (const [section, landing] of SECTIONS) {
      await boot(page, url, ready);
      const on = await page.locator('.rail [data-gob-section].on').evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-gob-section')));
      expect(on, 'lit on ' + name).toEqual([lit]);
      await page.locator('.rail [data-gob-section="' + section + '"]').click();
      await page.mouse.move(800, 500);
      await expect(page, section + ' from ' + name).toHaveURL(/franchise-command-center\.html/, { timeout: 20000 });
      await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000, message: section + ' from ' + name }).toBe(landing);
      await expect(page.locator('#' + landing + '.tab-content.active')).toHaveCount(1, { timeout: 15000 });
      await expect(page.locator('.rail [data-gob-section="' + section + '"]')).toHaveClass(/\bon\b/);
      // It is the section itself: no team, player or story rides along.
      const q = new URL(page.url()).searchParams;
      ['view_team_id', 'player_id', 'story', 'return_tab', 'origin'].forEach((key) => {
        expect(q.get(key), key + ' after ' + section + ' from ' + name).toBeNull();
      });
      if (section === 'news') await expect(page.locator('#news-view.active .gob-news')).toBeVisible();
    }
  });
}

test('the Recruiting rail item leaves a drill-in for the recruiting page', async ({ page }) => {
  await install(page, []);
  await boot(page, HUB + TEAM_PAGE + '&return_tab=home-tab&origin=office', '#team-view .gob-hero-n');
  await page.locator('.rail [data-gob-section="recruiting"]').click();
  await expect(page).toHaveURL(/\/recruiting\.html/, { timeout: 20000 });
});

test('on a section\'s own page the lit rail item still does nothing', async ({ page }) => {
  await install(page, []);
  await boot(page, HUB + '&tab=standings-view', '#standings-view.tab-content.active');
  const before = await page.evaluate(() => ({ url: location.href, length: history.length }));
  await page.locator('.rail [data-gob-section="league"]').click();
  await page.mouse.move(800, 500);
  await page.waitForTimeout(600);
  expect(await page.evaluate(() => ({ url: location.href, length: history.length }))).toEqual(before);
});

// ── Recruiting Report: the Score caption hides the formula ───────────────────
test('Recruiting Report: the Score caption says "Class strength so far" and explains nothing', async ({ page }) => {
  const stories = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/recruiting-report-real-stories.json'), 'utf8'));
  const story = stories.with_movement;
  await install(page, [story]);
  await boot(page, storyUrl(story.story_id), '#news-view .gob-news-story .gob-news-caption');
  const caption = page.locator('#news-view .gob-news-caption');
  await expect(caption).toHaveCount(1);
  await expect(caption).toHaveText('Class strength so far');
  await expect(page.locator('#news-view .gob-news-story')).not.toContainText(
    /first choice|second choice|counts in full|a quarter|adds up|ratings of the recruits|\d+\s*%/i,
  );
  await shots(page, 'recruiting-report-caption');
});
