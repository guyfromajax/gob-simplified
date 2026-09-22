// @ts-check
/**
 * Desktop profile against SQLite. The web suite seeds mongomock and aliases
 * team_id so /roster/{name} never exercises the $replaceAll aggregate.
 */
const { test, expect } = require('@playwright/test');

const PORT = process.env.PORT || process.env.GOB_LOOPBACK_PORT || '8767';
const ALWAYS_REMOTE = [
  '/api/auth',
  '/api/community',
  '/api/leaderboard',
  '/api/billing',
  '/api/email',
  '/api/admin',
  '/api/feedback',
  '/api/alpha-feedback',
];

function isAlwaysRemote(pathname) {
  return ALWAYS_REMOTE.some((prefix) => pathname === prefix || pathname.startsWith(prefix + '/') || pathname.startsWith(prefix));
}

test.describe('desktop sqlite play flow', () => {
  /** @type {string[]} */
  const remoteHits = [];

  test.beforeEach(async ({ page }) => {
    await page.addInitScript((port) => {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = Number(port);
    }, PORT);
    page.on('request', (req) => {
      try {
        const url = new URL(req.url());
        if (url.protocol === 'data:' || url.protocol === 'blob:') return;
        const local = url.hostname === '127.0.0.1' || url.hostname === 'localhost';
        if (!local && !isAlwaysRemote(url.pathname)) {
          remoteHits.push(url.href);
        }
      } catch (_) { /* ignore */ }
    });
  });

  test('team art, app-config, lineup roster, and the FCC→court walk', async ({ page, request }) => {
    const art = {
      banner_card: '/images/teams/chapel_hill/chapel_hill_banner_card.webp',
      banner_primary: '/images/teams/chapel_hill/chapel_hill_banner_primary.jpg',
      court: '/images/teams/chapel_hill/chapel_hill_court.jpg',
      logo_square: '/images/teams/chapel_hill/chapel_hill_logo_square.png',
    };
    const artStatus = {};
    for (const [kind, path] of Object.entries(art)) {
      const res = await request.get(path);
      artStatus[kind] = { url: path, status: res.status(), type: res.headers()['content-type'] || '' };
      expect(res.status(), `${kind} ${path}`).toBe(200);
    }
    expect(artStatus.banner_card.type).toMatch(/image\/webp/);

    const otf = await request.get('/fonts/BebasNeuePro-Bold.otf');
    expect(otf.status()).toBe(200);
    const fonts = await request.get('/fonts/app-fonts.css');
    expect(fonts.status()).toBe(200);
    expect(await fonts.text()).not.toContain('fonts.googleapis.com');

    const phaser = await request.get('/js/vendor/phaser-3.60.0.esm.js');
    expect(phaser.status()).toBe(200);

    const cfg = await request.get('/app-config');
    expect(cfg.status()).toBe(200);
    const cfgBody = await cfg.json();
    expect(cfgBody).toHaveProperty('teamBuilderEnabled');

    await page.goto('/mode-select.html');
    const create = await page.request.post('/franchise/select-team', {
      data: { team_name: 'Lancaster' },
    });
    expect(create.ok(), await create.text()).toBeTruthy();
    const created = await create.json();
    const franchiseId = created.franchise_id;
    expect(franchiseId).toBeTruthy();

    const byName = await page.request.get(`/roster/Lancaster?franchise_id=${franchiseId}&profile=1`);
    expect(byName.status(), await byName.text()).toBe(200);
    const nameBody = await byName.json();
    expect((nameBody.players || []).length).toBeGreaterThan(0);

    await page.goto(`/franchise-select-team.html?franchise_id=${franchiseId}`);
    const card = page.locator('.pg-art img').first();
    await expect(card).toBeVisible();
    const cardProbe = await card.evaluate((img) => ({
      src: img.currentSrc || img.getAttribute('src'),
      w: img.naturalWidth,
      complete: img.complete,
    }));
    expect(cardProbe.w, `card src=${cardProbe.src}`).toBeGreaterThan(0);

    await page.goto(`/franchise-command-center.html?franchise_id=${franchiseId}`);
    await expect(page.locator('#team-logo')).toBeVisible();
    await expect.poll(async () => page.locator('#team-logo').getAttribute('src')).not.toBe('');

    const next = await page.request.post('/franchise/play-next-game', {
      data: { franchise_id: franchiseId },
    });
    expect(next.ok(), await next.text()).toBeTruthy();
    const matchup = await next.json();
    const lineupQs = new URLSearchParams({
      mode: 'franchise',
      franchise_id: franchiseId,
      week: String(matchup.week || 1),
      home: matchup.home,
      away: matchup.away,
      home_id: String(matchup.home_id || ''),
      away_id: String(matchup.away_id || ''),
      my_team: matchup.home === 'Lancaster' ? 'home' : 'away',
    });
    if (created.team_id || matchup.home_id) {
      const tid = String(created.user_team_id || created.team_id || matchup.home_id);
      lineupQs.set('team_id', tid);
      lineupQs.set('user_team_id', tid);
    }

    await page.goto(`/set-lineup.html?${lineupQs}`);
    await expect.poll(async () => page.locator('.roster-table tbody tr').count()).toBeGreaterThan(0);

    await page.goto(`/game-plan.html?${lineupQs}`);
    await expect(page.locator('body')).toBeVisible();
    await expect(page.locator('body')).not.toContainText('No players');

    await page.goto(`/court.html?${lineupQs}`);
    await expect(page.locator('#phaser-container')).toBeVisible();
    await expect(page.locator('#scoreboard')).toBeVisible();
    const boot = await page.request.get('/js/phaser/bootGame.js');
    expect(boot.status()).toBe(200);
    expect(await boot.text()).toContain('/js/vendor/phaser-3.60.0.esm.js');
    expect(remoteHits, `unexpected remote: ${remoteHits.join('\n')}`).toEqual([]);
  });
});
