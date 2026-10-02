const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { stubAuth } = require('./helpers/auth');
const fx = require('./helpers/tablesLeagueFixtures');

/**
 * League › Standings, NEXT. The cell is the opponent only: its mark, with its name beside
 * it when the card is wide enough (1920 two-up, not 1280 two-up). No week label: it was
 * the same on every row and read like a second streak beside STRK. The full name is the
 * tooltip and the label in every case, the cell links to the opponent's page, and a team
 * with no next game shows a quiet dash.
 * TPL_SHOTS=1 also writes reports/team-page-links/after-standings-next-*.png.
 */
test.describe.configure({ timeout: 120000 });

const SHOTS = process.env.TPL_SHOTS === '1';
const OUT = path.join(__dirname, '../../reports/team-page-links');
const FCC = '/franchise-command-center.html?franchise_id=' + fx.FID + '&team_id=' + fx.TID;
const BODY = fx.standings();
// The first team of the user's conference has no next game.
const IDLE = BODY.standings.find((row) => row.conference === BODY.user_conference && row.team_id !== fx.TID);
BODY.standings.forEach((row) => {
  if (row.team_id !== IDLE.team_id) return;
  row.next_opponent_id = null;
  row.next_opponent_name = null;
  row.next_week = null;
});

async function open(page, size) {
  await page.setViewportSize(size);
  await stubAuth(page);
  await fx.installApi(page, { week: 13 });
  await page.route('**/franchise/standings**', (route) => route.fulfill({
    status: 200, contentType: 'application/json', body: JSON.stringify(BODY),
  }));
  await page.goto(FCC + '&tab=standings-view');
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  });
  await page.waitForSelector('#standings-view a.gob-team', { timeout: 20000 });
  await page.mouse.move(size.width - 8, size.height - 8);
}

/** Every NEXT cell of the page, with the row's own team. */
function cells(page) {
  return page.locator('#standings-view .gob-conf tbody tr').evaluateAll((rows) => rows.map((row) => {
    const cell = row.lastElementChild;
    const next = cell.querySelector('.gob-next');
    const name = next && next.querySelector('.gob-next-n');
    const streak = row.children[row.children.length - 2];
    return {
      text: cell.textContent.trim(),
      tag: next ? next.tagName : '',
      none: !!(next && next.classList.contains('is-none')),
      mark: !!(next && next.querySelector('img, .gob-mark')),
      name: name ? name.textContent : '',
      nameShown: !!(name && getComputedStyle(name).display !== 'none' && name.getBoundingClientRect().width > 0),
      title: next ? next.getAttribute('title') : '',
      label: next ? next.getAttribute('aria-label') : '',
      href: next ? next.getAttribute('href') : '',
      colour: next ? getComputedStyle(next).color : '',
      streak: streak.textContent.trim(),
      height: row.getBoundingClientRect().height,
      card: row.closest('.gob-conf').getBoundingClientRect().width,
    };
  }));
}

const byTeam = {};
BODY.standings.forEach((row) => { byTeam[row.next_opponent_name] = row.next_opponent_id; });

for (const size of [{ width: 1280, height: 720, name: false }, { width: 1920, height: 1080, name: true }]) {
  test('NEXT is the opponent only at ' + size.width + ': ' + (size.name ? 'mark and name' : 'mark, name in the tooltip'), async ({ page }) => {
    await open(page, size);
    const drawn = await cells(page);
    expect(drawn.length).toBe(BODY.standings.length);
    const playing = drawn.filter((cell) => !cell.none);
    expect(playing.length).toBe(BODY.standings.length - 1);

    playing.forEach((cell) => {
      // No week label, in the cell or anywhere in its text.
      expect(cell.text).not.toMatch(/\bW\s?\d+\b/);
      expect(cell.mark).toBe(true);
      // The full name is the tooltip and the label in every case.
      expect(cell.name).toBeTruthy();
      expect(cell.title).toBe(cell.name);
      expect(cell.label).toBe('Next: ' + cell.name);
      // Shown beside the mark only where the card has room.
      expect(cell.nameShown, cell.name + ' in a ' + Math.round(cell.card) + 'px card').toBe(size.name);
      expect(cell.text).toBe(size.name ? cell.name : cell.name);     // the name is in the DOM either way
      // It links to the opponent's page.
      expect(cell.tag).toBe('A');
      const href = new URL(cell.href, 'http://x');
      expect(href.searchParams.get('tab')).toBe('team-view');
      expect(href.searchParams.get('view_team_id')).toBe(byTeam[cell.name]);
      // STRK is still the streak, and the only "W4"-like text on the row.
      expect(cell.streak).toMatch(/^[WL]\d+$/);
    });

    // A team with no next game: a quiet dash, not a link.
    const idle = drawn.filter((cell) => cell.none);
    expect(idle.length).toBe(1);
    expect(idle[0].text).toBe('—');
    expect(idle[0].tag).toBe('SPAN');
    expect(idle[0].label).toBe('No next game');
    expect(idle[0].colour).toMatch(/^rgba\(255, 255, 255, 0\.38\d*\)$/);

    // Rows keep one height, and nothing spills sideways.
    const heights = Array.from(new Set(drawn.map((cell) => Math.round(cell.height))));
    expect(heights.length).toBe(1);
    const overflow = await page.locator('html.gob-shell .main').evaluate((main) => main.scrollWidth - main.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
    const spill = await page.locator('#standings-view .gob-conf').evaluateAll((cards) => cards.filter((card) => {
      const table = card.querySelector('table');
      return table.getBoundingClientRect().right > card.getBoundingClientRect().right + 1;
    }).length);
    expect(spill).toBe(0);

    if (SHOTS) {
      fs.mkdirSync(OUT, { recursive: true });
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(OUT, 'after-standings-next-' + size.width + '.png'), animations: 'disabled' });
    }

    // The opponent opens its own page; Back returns to Standings.
    const first = page.locator('#standings-view tr.is-user a.gob-next');
    const opponent = await first.getAttribute('title');
    await first.click();
    await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 15000 }).toBe('team-view');
    expect(new URL(page.url()).searchParams.get('view_team_id')).toBe(byTeam[opponent]);
    await page.goBack();
    await expect(page.locator('#standings-view.tab-content.active')).toHaveCount(1, { timeout: 15000 });
  });
}

test('NEXT sorts by the opponent, and the team with no game sorts last', async ({ page }) => {
  await open(page, { width: 1920, height: 1080 });
  const card = page.locator('#standings-view .gob-conf.is-yours');
  await card.locator('th[data-sort="next"]').click();
  const names = await card.locator('tbody tr td:last-child').evaluateAll((nodes) => nodes.map((node) => {
    const next = node.querySelector('.gob-next');
    return next.classList.contains('is-none') ? null : next.getAttribute('title');
  }));
  expect(names[names.length - 1]).toBeNull();
  const shown = names.slice(0, -1);
  expect(shown).toEqual(shown.slice().sort((a, b) => a.localeCompare(b)));
});
