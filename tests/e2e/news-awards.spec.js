const { test, expect } = require('@playwright/test');

test.describe.configure({ timeout: 120000 });

const FID = 'f-e2e-news';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OTHER = 'bbbbbbbbbbbbbbbbbbbbbbbb';

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 12,
    rank: 8,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 1, counts: {} },
    user_conference: 1,
    user_region: 'A',
    team_record: { wins: 10, losses: 2 },
  };
}

function newsBody() {
  return {
    week: 12,
    news: [
      {
        story_id: 'w12-upset',
        week: 12,
        type: 'upset_report',
        headline: 'Week 12 Upset Report',
        lines: ['#40. Lancaster upset #8. Four Corners by a score of 70-64.'],
      },
      {
        story_id: 'w8-recruits',
        week: 8,
        type: 'recruiting_report',
        headline: 'Week 8 Recruiting Report',
        rich_lines: [
          { type: 'heading', text: 'National' },
          {
            type: 'ranking_table',
            columns: ['Rank', 'Team', 'Score'],
            rows: [{ rank: 1, team: 'Lancaster', score: 90 }],
          },
          {
            type: 'player_table',
            players: [{
              name: 'A. Cole',
              pos: 'PG',
              year: 'SR',
              height: 74,
              weight: 180,
              attributes: { scoring: 80 },
              rt: 88,
            }],
          },
        ],
      },
    ],
    dispatches: [
      {
        week: 12,
        type: 'game_result',
        headline: 'Lancaster defeated Four Corners 70-64',
        target: '/box-score.html?game_id=g1',
        link_label: 'box score',
        yours: true,
      },
      {
        week: 8,
        type: 'training_report',
        headline: 'Week 8 training report',
        target: '/training-report.html?week=8',
        link_label: 'view',
        yours: true,
      },
    ],
  };
}

function awardsBody() {
  return {
    all_american_teams: {
      first_team: [{
        player_id: 'p1',
        name: 'A. Cole',
        year: 'Senior',
        team_id: TID,
        team_name: 'Lancaster',
        stats: { PTS: 22, REB: 5, AST: 6, STL: 2, BLK: 1, 'DEF%': 61 },
      }],
      second_team: [{
        player_id: 'p2',
        name: 'B. Dunn',
        year: 'Junior',
        team_id: OTHER,
        team_name: 'Four Corners',
        stats: { PTS: 18, REB: 8, AST: 2, STL: 1, BLK: 2, 'DEF%': 55 },
      }],
      third_team: [],
    },
  };
}

async function fulfillJson(route, body, status) {
  await route.fulfill({
    status: status || 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

async function installApi(page, opts) {
  const options = opts || {};
  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/')
      || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/')
      || pathname.startsWith('/player/')
      || pathname === '/teams'
      || pathname === '/app-config';
    if (!api) {
      await route.continue();
      return;
    }
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
    if (pathname.startsWith('/franchise/command-center/data')) {
      await fulfillJson(route, cc());
      return;
    }
    if (pathname.startsWith('/franchise/news')) {
      if (options.newsStatus) {
        await fulfillJson(route, { detail: 'no' }, options.newsStatus);
        return;
      }
      if (options.holdNews) {
        await new Promise(function (resolve) { setTimeout(resolve, 1500); });
      }
      await fulfillJson(route, options.news || newsBody());
      return;
    }
    if (pathname.startsWith('/franchise/awards')) {
      if (options.awardsStatus) {
        await fulfillJson(route, { detail: 'Awards are not available until week 35' }, options.awardsStatus);
        return;
      }
      await fulfillJson(route, options.awards || awardsBody());
      return;
    }
    await fulfillJson(route, {});
  });
}

async function openFcc(page, opts) {
  const { stubAuth } = require('./helpers/auth');
  await stubAuth(page);
  await installApi(page, opts);
  await page.goto('/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID);
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#play-now.advance');
}

async function openNews(page) {
  await page.locator('.rail [data-gob-section="news"]').evaluate(function (el) { el.click(); });
  await page.getByRole('tab', { name: 'News', exact: true }).evaluate(function (el) { el.click(); });
  await expect(page.locator('#news-view.tab-content.active')).toBeVisible();
}

test('news and awards tabs stay in the page', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  const navs = await page.evaluate(() => performance.getEntriesByType('navigation').length);
  await openNews(page);
  const hero = page.locator('#news-view .gob-news-card.is-hero');
  await expect(hero).toHaveClass(/is-yours/);
  await expect(hero).toContainText('Lancaster defeated Four Corners 70-64 (Box Score)');
  await expect(hero).toHaveAttribute('href', '/box-score.html?game_id=g1');
  await expect(page.locator('#news-view a.lnk')).toHaveCount(0);
  await expect(page.getByText('View', { exact: true })).toHaveCount(0);
  const edge = await hero.evaluate(function (el) { return getComputedStyle(el).boxShadow; });
  expect(edge).toContain('39, 64, 142');
  expect(page.url()).toContain('tab=news-view');
  expect(page.url()).not.toContain('news.html');
  expect(await page.evaluate(() => performance.getEntriesByType('navigation').length)).toBe(navs);

  await page.getByRole('tab', { name: 'Awards', exact: true }).evaluate(function (el) { el.click(); });
  await expect(page.locator('#awards-view.tab-content.active')).toBeVisible();
  await expect(page.locator('#awards-view h3').first()).toHaveText('1st Team All-American');
  await expect(page.locator('#awards-view tr.me')).toContainText('A. Cole');
  await expect(page.locator('#awards-view tr.me')).toContainText('SR');
  await expect(page.locator('#awards-view tr.me')).toContainText('61%');
  await expect(page.locator('#awards-view tbody tr').nth(1)).not.toHaveClass(/me/);
  await expect(page.locator('#awards-view .gob-awards-empty')).toHaveText('No selections');
  expect(page.url()).toContain('tab=awards-view');
  expect(page.url()).not.toContain('awards.html');
  const player = page.locator('#awards-view tr.me a.gob-player');
  await player.click();
  await expect.poll(function () { return page.url(); }).toContain('tab=player-view');
  expect(page.url()).toContain('player_id=p1');
});

test('a headline pushes the story and back restores the feed scroll', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  await openNews(page);
  await page.locator('#news-view').evaluate(function (el) { el.style.minHeight = '2400px'; });
  await page.evaluate(function () { document.querySelector('html.gob-shell .main').scrollTop = 480; });
  await page.locator('#news-view a.gob-news-card[data-story]').first().evaluate(function (el) { el.click(); });
  await expect(page.locator('#news-view .gob-news-headline')).toHaveText('Week 12 Upset Report');
  await expect(page.locator('#news-view .gob-news-line')).toContainText('Lancaster upset');
  expect(page.url()).toContain('story=w12-upset');
  await expect.poll(async () => page.evaluate(function () {
    return document.querySelector('html.gob-shell .main').scrollTop;
  })).toBe(0);
  await page.locator('#news-view .gob-dt-up').click();
  await expect(page.locator('#news-view .gob-news-card.is-hero')).toBeVisible();
  expect(page.url()).not.toContain('story=');
  await expect.poll(async () => page.evaluate(function () {
    return document.querySelector('html.gob-shell .main').scrollTop;
  })).toBeGreaterThan(400);
});

test('news.html and awards.html redirect into the views', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await openFcc(page);
  await page.goto('/news.html?franchise_id=' + FID + '&team_id=' + TID + '&story=w8-recruits');
  await expect(page.locator('#news-view .gob-news-headline')).toHaveText('Week 8 Recruiting Report');
  await expect(page.locator('#news-view .attr-tile')).toHaveCount(12);
  expect(page.url()).toContain('tab=news-view');
  expect(page.url()).toContain('story=w8-recruits');
  expect(page.url()).not.toContain('news.html');
  await page.goto('/awards.html?franchise_id=' + FID + '&team_id=' + TID);
  await expect(page.locator('#awards-view h3').nth(2)).toHaveText('3rd Team All-American');
  expect(page.url()).toContain('tab=awards-view');
  expect(page.url()).not.toContain('awards.html');
});

test('awards before week 35 use the existing empty copy', async ({ page }) => {
  await openFcc(page, { awardsStatus: 400 });
  await page.locator('.rail [data-gob-section="news"]').evaluate(function (el) { el.click(); });
  await page.getByRole('tab', { name: 'Awards', exact: true }).evaluate(function (el) { el.click(); });
  await expect(page.locator('#awards-view')).toContainText('Awards are not available yet.');
});

test('first open shows a skeleton and a failed news load retries', async ({ page }) => {
  await openFcc(page, { holdNews: true });
  await page.locator('.rail [data-gob-section="news"]').evaluate(function (el) { el.click(); });
  await page.getByRole('tab', { name: 'News', exact: true }).evaluate(function (el) { el.click(); });
  await expect(page.locator('#news-view .gob-view-skel')).toBeVisible();
  await expect(page.locator('#news-view .gob-news-card').first()).toBeVisible();

  await page.unroute('**/*');
  await installApi(page, { newsStatus: 500 });
  await page.reload();
  await page.waitForSelector('#play-now.advance');
  await page.locator('.rail [data-gob-section="news"]').evaluate(function (el) { el.click(); });
  await page.getByRole('tab', { name: 'News', exact: true }).evaluate(function (el) { el.click(); });
  await expect(page.locator('#news-view .gob-view-retry')).toBeVisible();
  await page.unroute('**/*');
  await installApi(page, {});
  await page.locator('#news-view .gob-view-retry').click();
  await expect(page.locator('#news-view .gob-news-card').first()).toBeVisible();
});

test('the news and awards panels do not overflow .main', async ({ page }) => {
  await openFcc(page);
  for (const size of [[1280, 720], [1920, 1080]]) {
    await page.setViewportSize({ width: size[0], height: size[1] });
    await page.goto('/news.html?franchise_id=' + FID + '&team_id=' + TID + '&story=w8-recruits');
    await expect(page.locator('#news-view .gob-tbl').first()).toBeVisible();
    const newsOverflow = await page.evaluate(function () {
      const main = document.querySelector('html.gob-shell .main');
      return main.scrollWidth > main.clientWidth + 1;
    });
    expect(newsOverflow, 'news ' + size[0]).toBe(false);
    await page.getByRole('tab', { name: 'Awards', exact: true }).evaluate(function (el) { el.click(); });
    await expect(page.locator('#awards-view table').first()).toBeVisible();
    const awardsOverflow = await page.evaluate(function () {
      const main = document.querySelector('html.gob-shell .main');
      return main.scrollWidth > main.clientWidth + 1;
    });
    expect(awardsOverflow, 'awards ' + size[0]).toBe(false);
  }
});
