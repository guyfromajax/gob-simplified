const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

/**
 * A news story's "← News", the rail's News, and the navigation keys a drill-in leaves in
 * the URL (story, view_team_id, return_tab, origin, …).
 *
 * - "← News" always lands on the News feed, at the reader's scroll when the story was
 *   opened from the feed.
 * - The rail's News always opens the feed, even with a story open.
 * - The browser's Back returns to where the reader came from.
 * - Moving to another tab or section drops the navigation keys, so they cannot steer a
 *   later control.
 *
 * One test per way into a story: the feed, another page (the Office), a link inside
 * another story, a direct URL.
 */
test.describe.configure({ timeout: 120000 });

const GAME = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/boxscore-real-game.json'), 'utf8'));
const TEAM = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/team-page-real-results.json'), 'utf8'));
const STORIES = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/recruiting-report-real-stories.json'), 'utf8'));
const IDENTITY = 'franchise_id=' + GAME.franchise_id + '&team_id=' + GAME.team_id;
const HUB = '/franchise-command-center.html?' + IDENTITY;
const REPORT = STORIES.old_shape.story_id;                    // w4-recruiting-report
const OTHER_TEAM = GAME.opponent_id;
// The parameters on Jamie's URL: a team opened from the Office earlier, never cleared.
const STALE = '&view_team_id=' + OTHER_TEAM + '&return_tab=home-tab&origin=office';
const NAV_KEYS = ['story', 'view_team_id', 'return_tab', 'origin', 'player_id', 'up', 'pager', 'return_url'];

const json = (route, body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

// Forty short stories so the feed scrolls, the two real Recruiting Reports, and a story
// whose body links to another story.
function feed() {
  const filler = [];
  for (let i = 1; i <= 40; i += 1) {
    filler.push({
      story_id: 'filler-' + i, week: 4 - Math.floor((i - 1) / 14), type: 'upset_report',
      headline: 'Upset report number ' + i, lines: ['Line ' + i],
    });
  }
  const linking = {
    story_id: 'links-out', week: 4, type: 'ps_all_stars', headline: 'A story that links to another',
    rich_lines: [
      { type: 'text', text: 'See this week\'s report.' },
      { type: 'link', label: 'Week 4 Recruiting Report', href: HUB + '&tab=news-view&story=' + REPORT },
    ],
  };
  return { week: 4, news: [STORIES.old_shape, linking].concat(filler), dispatches: [] };
}

async function install(page, profile) {
  if (profile === 'desktop') {
    await page.addInitScript(() => {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = 8791;
    });
  }
  await stubAuth(page);
  const body = feed();
  await page.route('**/*', async (route) => {
    let url;
    try { url = new URL(route.request().url()); } catch (err) { return route.continue(); }
    const pathname = url.pathname;
    if (pathname.indexOf('/images/players/') !== -1) return route.fulfill({ status: 404, body: '' });
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname.startsWith('/roster/')
      || pathname === '/app-config' || pathname === '/teams' || pathname === '/health';
    if (!api) return route.continue();
    if (pathname === '/api/auth/me') return json(route, { user_id: 'e2e-user', username: 'e2e' });
    if (pathname === '/app-config') return json(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/teams') return json(route, []);
    if (pathname.startsWith('/franchise/command-center/data')) return json(route, GAME.command_center);
    if (pathname.startsWith('/franchise/news')) return json(route, body);
    if (pathname.startsWith('/franchise/team-detail')) {
      return json(route, url.searchParams.get('team_id') === GAME.team_id ? GAME.team_detail : TEAM.team_detail_opponent);
    }
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
}

/** Where the reader is: the tab on screen, the rail, and the navigation keys in the URL. */
async function where(page) {
  return page.evaluate((keys) => {
    const q = new URLSearchParams(location.search);
    const nav = {};
    keys.forEach((key) => { if (q.get(key)) nav[key] = q.get(key); });
    return {
      tab: q.get('tab'),
      nav,
      active: [...document.querySelectorAll('.tab-content.active')].map((node) => node.id).join(','),
      rail: [...document.querySelectorAll('.rail [data-gob-section].on')].map((node) => node.getAttribute('data-gob-section')).join(','),
      story: !!document.querySelector('#news-view.active .gob-news-story'),
      feed: !!document.querySelector('#news-view.active .gob-news'),
    };
  }, NAV_KEYS);
}

async function expectFeed(page) {
  await expect.poll(async () => (await where(page)).feed, { timeout: 15000 }).toBe(true);
  const here = await where(page);
  expect(here).toEqual({ tab: 'news-view', nav: {}, active: 'news-view', rail: 'news', story: false, feed: true });
  await expect(page.locator('.pg-head h1')).toHaveText('News');
}

async function expectStory(page, id) {
  await expect(page.locator('#news-view .gob-news-story .gob-news-headline')).toBeVisible({ timeout: 15000 });
  expect(new URL(page.url()).searchParams.get('story')).toBe(id);
}

/** The rail widens under the pointer and covers the page's left edge: move off it. */
async function rail(page, section) {
  await page.locator('.rail [data-gob-section="' + section + '"]').click();
  await page.mouse.move(800, 500);
}

const backLink = (page) => page.locator('#news-view .gob-news-story a.gob-dt-up');
const scrollTop = (page) => page.locator('html.gob-shell .main').evaluate((node) => Math.round(node.scrollTop));

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
});

test('from the News feed: "← News" returns to the feed where the reader left it', async ({ page }) => {
  await install(page);
  await boot(page, HUB + '&tab=news-view', '#news-view .gob-news');
  // Read down the feed, then open a story from there.
  const card = page.locator('#news-view a.gob-news-card[data-story="filler-30"]');
  await card.scrollIntoViewIfNeeded();
  const left = await scrollTop(page);
  expect(left).toBeGreaterThan(200);
  await card.click();
  await expectStory(page, 'filler-30');
  expect(await scrollTop(page)).toBe(0);

  await backLink(page).click();
  await expectFeed(page);
  await expect.poll(() => scrollTop(page), { timeout: 10000 }).toBe(left);
  // It stepped back onto the feed's own entry: Forward is the story again.
  await page.goForward();
  await expectStory(page, 'filler-30');
  // And the browser's Back from a story is the feed it was opened from.
  await page.goBack();
  await expectFeed(page);
});

test('from the Office, with a team\'s leftovers in the URL: "← News" is the feed, Back is the Office', async ({ page }) => {
  await install(page);
  await boot(page, HUB, '#office-root a[href*="view_team_id"]');
  // An earlier drill-in from the Office: a team page, then Back to the Office.
  await page.locator('#office-root a[href*="view_team_id"]').first().click();
  await expect(page.locator('#team-view .gob-hero-n')).toBeVisible({ timeout: 20000 });
  expect((await where(page)).nav).toMatchObject({ return_tab: 'home-tab', origin: 'office' });
  await page.goBack();
  await expect(page.locator('#home-tab.tab-content.active')).toHaveCount(1);

  // The story, opened from the Office by an in-app link carrying exactly the parameters
  // on Jamie's URL.
  await page.evaluate((href) => {
    const link = document.createElement('a');
    link.id = 'e2e-office-headline';
    link.href = href;
    link.textContent = 'Week 4 Recruiting Report';
    document.getElementById('office-root').appendChild(link);
    link.click();
  }, HUB + '&tab=news-view' + STALE + '&story=' + REPORT);
  await expectStory(page, REPORT);

  await backLink(page).click();
  await expectFeed(page);                                    // the News feed, not the team, not the Office
  await expect(page.locator('#team-view.tab-content.active')).toHaveCount(0);
  // The feed took the story's place, so Back is where the reader came from.
  await page.goBack();
  await expect(page.locator('#home-tab.tab-content.active')).toHaveCount(1, { timeout: 15000 });
  expect((await where(page)).rail).toBe('office');
});

test('from the Office: the browser\'s Back out of a story returns to the Office', async ({ page }) => {
  await install(page);
  await boot(page, HUB, '#office-root');
  await page.evaluate((href) => {
    const link = document.createElement('a');
    link.href = href;
    document.getElementById('office-root').appendChild(link);
    link.click();
  }, HUB + '&tab=news-view&story=' + REPORT);
  await expectStory(page, REPORT);
  await page.goBack();
  await expect(page.locator('#home-tab.tab-content.active')).toHaveCount(1, { timeout: 15000 });
  expect((await where(page)).nav).toEqual({});
});

test('from a link inside another story: "← News" is the feed, Back is the first story', async ({ page }) => {
  await install(page);
  await boot(page, HUB + '&tab=news-view&story=links-out', '#news-view .gob-news-story a.gob-news-link');
  await page.locator('#news-view .gob-news-story a.gob-news-link').click();
  await expectStory(page, REPORT);
  await expect(page.locator('#news-view .gob-news-headline')).toHaveText('Week 4 Recruiting Report');
  expect((await where(page)).nav).toEqual({ story: REPORT });

  await backLink(page).click();
  await expectFeed(page);
  await page.goBack();
  await expectStory(page, 'links-out');
});

test('from a direct URL carrying a team\'s leftovers: "← News" is the feed', async ({ page }) => {
  await install(page);
  // Jamie's URL, as the first thing loaded.
  await boot(page, HUB + '&tab=news-view' + STALE + '&story=' + REPORT, '#news-view .gob-news-story');
  await expectStory(page, REPORT);
  expect((await where(page)).rail).toBe('news');
  await backLink(page).click();
  await expectFeed(page);
});

test('the rail\'s News opens the feed, with a story open and from Awards', async ({ page }) => {
  await install(page);
  await boot(page, HUB + '&tab=news-view' + STALE + '&story=' + REPORT, '#news-view .gob-news-story');
  await rail(page, 'news');
  await expectFeed(page);
  // The story keeps its own entry.
  await page.goBack();
  await expectStory(page, REPORT);

  // On the feed with no story open, the rail's News does nothing (no new entry).
  await rail(page, 'news');
  await expectFeed(page);
  const length = await page.evaluate(() => history.length);
  await rail(page, 'news');
  expect(await page.evaluate(() => history.length)).toBe(length);

  // From the section's other sub-tab.
  await page.getByRole('tab', { name: 'Awards', exact: true }).click();
  await expect(page.locator('#awards-view.tab-content.active')).toHaveCount(1);
  await rail(page, 'news');
  await expectFeed(page);
});

for (const profile of ['web', 'desktop']) {
  test('leftover navigation keys are dropped on a tab or section change (' + profile + ')', async ({ page }) => {
    await install(page, profile);
    await boot(page, HUB + '&tab=news-view' + STALE + '&story=' + REPORT, '#news-view .gob-news-story');

    // Jamie's Standings URL: after leaving the story for another section, nothing rides along.
    await rail(page, 'league');
    await expect(page.locator('#standings-view.tab-content.active')).toHaveCount(1, { timeout: 15000 });
    expect(await where(page)).toMatchObject({ tab: 'standings-view', nav: {}, rail: 'league' });
    // A sub-tab change.
    await page.getByRole('tab', { name: 'Rankings', exact: true }).click();
    await expect(page.locator('#rankings-view.tab-content.active')).toHaveCount(1);
    expect(await where(page)).toMatchObject({ tab: 'rankings-view', nav: {}, rail: 'league' });
    // Back to News: the feed, not the story from before.
    await rail(page, 'news');
    await expectFeed(page);

    // A drill-in still carries its own keys, and they go when the reader moves on.
    await rail(page, 'office');
    await expect(page.locator('#home-tab.tab-content.active')).toHaveCount(1);
    await page.locator('#office-root a[href*="view_team_id"]').first().click();
    await expect(page.locator('#team-view .gob-hero-n')).toBeVisible({ timeout: 20000 });
    const team = await where(page);
    expect(team.tab).toBe('team-view');
    expect(team.nav).toMatchObject({ return_tab: 'home-tab', origin: 'office' });
    expect(team.nav.view_team_id).toBeTruthy();
    await rail(page, 'team');
    await expect(page.locator('#roster-view.tab-content.active')).toHaveCount(1, { timeout: 15000 });
    expect(await where(page)).toMatchObject({ tab: 'roster-view', nav: {}, rail: 'team' });
    // The entry that was left keeps its keys: Back is the team page again.
    await page.goBack();
    await expect(page.locator('#team-view .gob-hero-n')).toBeVisible({ timeout: 20000 });
    expect((await where(page)).nav.view_team_id).toBe(team.nav.view_team_id);
  });
}
