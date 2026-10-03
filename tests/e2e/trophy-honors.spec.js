// @ts-check
/**
 * Trophy Case: the Honors shelf. All-American and All-Conference entries already in the
 * coach's trophy log are drawn at team level ("1st Team All-American", "2nd Team
 * All-Conference") with the player, position, program and season, between Titles and
 * Milestones, in the page's own tile style and colours. With none, nothing extra.
 * TH_SHOTS=1 writes reports/v3-pages/after-*.png at 1280 and 1920.
 */
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');

test.describe.configure({ timeout: 90000 });

const SHOTS = process.env.TH_SHOTS === '1';
const OUT = path.join(__dirname, '../../reports/v3-pages');

function career(trophies) {
  return {
    user_id: 'e2e-user', username: 'Coach Demo',
    record: { wins: 73, losses: 22, total_games: 95, win_rate: 77 },
    championships_total: { conf_rs: 0, conf_t: 1, region: 1, national: 1 },
    titles_total: 3, win_pct_display: '.770', geek_points: 4060,
    seasons_completed: 4, programs: 2,
    trophies: [
      { kind: 'national', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      { kind: 'region', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      { kind: 'conf_t', season: 1, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
      { kind: 'milestone_first_signing_class', season: 1, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1' },
    ].concat(trophies || []),
    top_seasons: [],
  };
}

// Newest first in the data, as the server sends them.
const HONORS = [
  { kind: 'all_conference_2', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1',
    detail: { player_id: 'p4', player_name: 'Owen Price', position: 'C' } },
  { kind: 'all_american_1', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1',
    detail: { player_id: 'p1', player_name: 'Jalen Carter', position: 'PG' } },
  { kind: 'all_conference_1', season: 2, team_name: 'Lawrence Eagles', franchise_id: 'f1', team_id: 't-f1',
    detail: { player_id: 'p1', player_name: 'Jalen Carter', position: 'PG' } },
  // An entry from before positions were stored.
  { kind: 'all_american_3', season: 1, team_name: 'Chapel Hill Sky', franchise_id: 'f2', team_id: 't-f2',
    detail: { player_id: 'p9', player_name: 'Miles Foster' } },
];

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function openTrophyCase(page, body, width) {
  await stubAuth(page);
  await page.route('**/*', async (route) => {
    let pathname = '';
    try { pathname = new URL(route.request().url()).pathname; } catch (err) { return route.continue(); }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/') || pathname === '/teams' || pathname === '/app-config';
    if (!api) return route.continue();
    if (pathname === '/franchise/coach-career') return fulfillJson(route, body);
    if (pathname === '/app-config') return fulfillJson(route, { isAlpha: false, alphaDisclaimer: null, version: '1.0' });
    if (pathname === '/api/auth/me') return fulfillJson(route, { user_id: 'e2e-user', username: 'e2e' });
    return fulfillJson(route, {});
  });
  await page.setViewportSize({ width: width || 1280, height: width === 1920 ? 1080 : 720 });
  await page.goto('/trophy-case.html');
  await expect(page.locator('#page-load-overlay')).toBeHidden({ timeout: 30000 });
  await expect(page.locator('.tc-head h1')).toContainText('Trophy Case');
}

function readPage(page) {
  return page.evaluate(() => {
    const heads = [...document.querySelectorAll('.tc-col .sec-h h3')].map((h) => h.textContent.trim());
    const section = [...document.querySelectorAll('.tc-col .sec')].find((s) => /Honors/.test(s.textContent));
    const shelf = section ? section.nextElementSibling : null;
    const tiles = shelf ? [...shelf.querySelectorAll('.tro')] : [];
    const colour = (el) => getComputedStyle(el).color;
    const milestoneMedal = document.querySelector('.tro.sm .med.ms');
    return {
      heads,
      count: section ? (section.querySelector('.sec-h span') || {}).textContent : null,
      tiles: tiles.map((t) => ({
        letter: t.querySelector('.med').textContent,
        label: t.querySelector('b').textContent,
        sub: (t.querySelector(':scope > div > span') || {}).textContent || '',
        medal: colour(t.querySelector('.med')),
        gold: t.querySelector('.med').classList.contains('gold'),
        bold: colour(t.querySelector('b')),
      })),
      milestoneMedal: milestoneMedal ? colour(milestoneMedal) : '',
      titleMedal: colour(document.querySelector('.shelf .med.gold')),
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
}

async function shots(page, name) {
  if (!SHOTS) return;
  fs.mkdirSync(OUT, { recursive: true });
  await page.mouse.move(2, 2);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT, name), animations: 'disabled' });
}

test('Honors: All-American and All-Conference entries, between Titles and Milestones, in the page\'s tile', async ({ page }) => {
  await openTrophyCase(page, career(HONORS));
  const seen = await readPage(page);
  expect(seen.heads).toEqual(['Titles', 'Honors', 'Milestones', 'Season Reviews']);
  expect(seen.count).toBe('4');
  // Newest season first; within a season All-American before All-Conference, first team first.
  expect(seen.tiles.map((t) => t.label)).toEqual([
    '1st Team All-American', '1st Team All-Conference', '2nd Team All-Conference', '3rd Team All-American',
  ]);
  expect(seen.tiles.map((t) => t.letter)).toEqual(['A', 'C', 'C', 'A']);
  expect(seen.tiles[0].sub).toBe('Jalen Carter · PG · Lawrence Eagles · Season 2');
  expect(seen.tiles[2].sub).toBe('Owen Price · C · Lawrence Eagles · Season 2');
  // An older entry with no stored position reads without one.
  expect(seen.tiles[3].sub).toBe('Miles Foster · Chapel Hill Sky · Season 1');
  // The milestones' neutral medal, never the titles' gold.
  seen.tiles.forEach((t) => {
    expect(t.gold).toBe(false);
    expect(t.medal).toBe(seen.milestoneMedal);
    expect(t.medal).not.toBe(seen.titleMedal);
  });
  expect(seen.overflow).toBeLessThanOrEqual(0);
  await shots(page, 'after-honors-1280.png');
  // The title and milestone shelves are as they were.
  await expect(page.locator('.shelf .med.gold')).toHaveCount(3);
  await expect(page.locator('.tro.sm:not(.hon)')).toHaveCount(1);
});

test('Honors at 1920', async ({ page }) => {
  await openTrophyCase(page, career(HONORS), 1920);
  const seen = await readPage(page);
  expect(seen.heads).toEqual(['Titles', 'Honors', 'Milestones', 'Season Reviews']);
  expect(seen.tiles.length).toBe(4);
  expect(seen.overflow).toBeLessThanOrEqual(0);
  await shots(page, 'after-honors-1920.png');
});

test('no honors: nothing extra on the page', async ({ page }) => {
  await openTrophyCase(page, career([]));
  const seen = await readPage(page);
  expect(seen.heads).toEqual(['Titles', 'Milestones', 'Season Reviews']);
  await expect(page.locator('.tro.hon')).toHaveCount(0);
  await expect(page.locator('main.tc')).not.toContainText('Honors');
});
