/**
 * ch8 dead-code sweep: 1280 shots, web + desktop, wait for real webfonts.
 * FCC views + Recruiting + Home Base + Trophy Case.
 * Not a product file.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const FID = 'f-e2e-ch8sweep';
const TID = 'aaaaaaaaaaaaaaaaaaaaaaaa';
const OPP = 'bbbbbbbbbbbbbbbbbbbbbbbb';
const WEB_BASE = process.env.BASE_URL || 'http://127.0.0.1:8770';
const PORT = new URL(WEB_BASE).port || '8770';
const DESKTOP_BASE = WEB_BASE.includes('localhost')
  ? WEB_BASE.replace('localhost', '127.0.0.1')
  : WEB_BASE;
const PHASE = process.env.PHASE || 'after';
const OUT = path.join(__dirname, 'shots');

const VIEWS = [
  { id: 'home-tab', file: 'office', extra: '' },
  { id: 'roster-view', file: 'team-roster', extra: 'tab=roster-view' },
  { id: 'player-stats-view', file: 'team-player-stats', extra: 'tab=player-stats-view' },
  { id: 'team-attributes-view', file: 'team-attributes', extra: 'tab=team-attributes-view' },
  { id: 'team-schedule-view', file: 'team-schedule', extra: 'tab=team-schedule-view' },
  { id: 'practice-squad-view', file: 'team-practice-squad', extra: 'tab=practice-squad-view' },
  { id: 'game-plan-view', file: 'prep-game-plan', extra: 'tab=game-plan-view' },
  { id: 'playbooks-view', file: 'prep-playbooks', extra: 'tab=playbooks-view' },
  { id: 'scouting-view', file: 'prep-scouting', extra: 'tab=scouting-view' },
  { id: 'training-view', file: 'prep-training', extra: 'tab=training-view' },
  { id: 'standings-view', file: 'league-standings', extra: 'tab=standings-view' },
  { id: 'rankings-view', file: 'league-rankings', extra: 'tab=rankings-view' },
  { id: 'leaders-view', file: 'league-leaders', extra: 'tab=leaders-view' },
  { id: 'team-stats-view', file: 'league-team-stats', extra: 'tab=team-stats-view' },
  { id: 'league-schedule-view', file: 'league-schedule', extra: 'tab=league-schedule-view' },
  { id: 'tournament-view', file: 'league-tournament', extra: 'tab=tournament-view' },
  { id: 'news-view', file: 'news', extra: 'tab=news-view' },
  { id: 'awards-view', file: 'news-awards', extra: 'tab=awards-view' },
];

function base(profile) {
  return profile === 'desktop' ? DESKTOP_BASE : WEB_BASE;
}

function cc() {
  return {
    franchise_id: FID,
    team_id: TID,
    user_team_id: TID,
    team: 'Lancaster',
    week: 3,
    rank: 14,
    season: 1,
    current_season: 1,
    training_completed: true,
    session_type: 'in-season',
    cut_required: false,
    recruiting_wire: { board_saved_week: 3, counts: {}, events: [] },
    user_conference: 1,
    user_region: 'A',
    team_record: '10-2',
    office_digest: { state: 'in_season', week: 3 },
  };
}

function career() {
  return {
    user_id: 'e2e-user',
    username: 'e2e',
    record: { wins: 73, losses: 22, total_games: 95, win_rate: 77 },
    championships_total: { conf_rs: 1, conf_t: 1, region: 1, national: 0 },
    titles_total: 3,
    win_pct_display: '.768',
    geek_points: 4060,
    seasons_completed: 4,
    programs: 2,
    trophies: [
      { kind: 'conf_t', season: 3, team_name: 'Lancaster', franchise_id: FID, team_id: TID },
      { kind: 'region', season: 2, team_name: 'Lancaster', franchise_id: FID, team_id: TID },
      { kind: 'milestone_first_signing_class', season: 1, team_name: 'Lancaster', franchise_id: FID, team_id: TID },
    ],
    top_seasons: [
      {
        franchise_id: FID, team_name: 'Lancaster', team_slug: 'lancaster', season: 3,
        wins: 22, losses: 4, finish: 'Region Champions', finish_is_title: true,
        season_gp: 1400, in_progress: false, week: 26,
      },
    ],
  };
}

function franchiseList() {
  return {
    franchises: [{
      franchise_id: FID,
      home_slot: 1,
      user_team_id: 'Lancaster',
      user_team_object_id: TID,
      week: 3,
      current_season: 1,
      primary_color: '#27408e',
      secondary_color: '#15181f',
      last_played_at: '2026-09-21T10:00:00Z',
    }],
    count: 1,
    max: 2,
    most_recent_franchise_id: FID,
  };
}

async function fulfillJson(route, body) {
  await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
}

async function setup(page, profile) {
  await page.addInitScript(({ desktop, apiBase, port }) => {
    if (desktop) {
      window.GOB_BUILD_PROFILE = 'desktop';
      window.GOB_LOOPBACK_PORT = Number(port);
    }
    window.API_BASE_URL = apiBase;
    localStorage.setItem('auth_token', 'e2e-stub-token');
    localStorage.setItem('auth_user', JSON.stringify({
      user_id: 'e2e-user', email: 'e2e@example.com', username: 'e2e',
    }));
  }, { desktop: profile === 'desktop', apiBase: base(profile), port: PORT });

  await page.route('**/*', async (route) => {
    const request = route.request();
    let pathname = '';
    try { pathname = new URL(request.url()).pathname; } catch (err) {
      await route.continue();
      return;
    }
    const api = pathname.startsWith('/api/') || pathname.startsWith('/franchise/')
      || pathname.startsWith('/roster/') || pathname.startsWith('/player/')
      || pathname.startsWith('/recruit/')
      || pathname === '/teams' || pathname === '/app-config';
    if (!api) {
      if (/\.(png|jpe?g|webp|gif|svg)$/i.test(pathname) && !pathname.includes('loader')) {
        await route.fulfill({ status: 404, body: '' });
        return;
      }
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
    if (pathname === '/franchise/list') {
      await fulfillJson(route, franchiseList());
      return;
    }
    if (pathname === '/franchise/coach-career') {
      await fulfillJson(route, career());
      return;
    }
    if (pathname.startsWith('/api/auth/leaderboard')) {
      await fulfillJson(route, {
        top: [{ rank: 1, username: 'e2e', geek_points: 4060, is_current_user: true }],
        current_user: { rank: 1, username: 'e2e', geek_points: 4060, is_current_user: true },
        titles_top: [{ rank: 1, username: 'e2e', total_titles: 3, national_titles: 0, is_current_user: true }],
        titles_current_user: { rank: 1, username: 'e2e', total_titles: 3, national_titles: 0, is_current_user: true },
      });
      return;
    }
    if (pathname.startsWith('/api/community/around-the-league')) {
      await fulfillJson(route, { items: [] });
      return;
    }
    if (pathname.startsWith('/franchise/standings')) {
      await fulfillJson(route, {
        standings: [
          { team_id: TID, name: 'Lancaster', display_name: 'Lancaster', W: 10, L: 2, conference: 1, region: 'A', primary_color: '#27408E' },
          { team_id: OPP, name: 'York', display_name: 'York', W: 8, L: 4, conference: 1, region: 'A' },
        ],
        user_team_id: TID,
      });
      return;
    }
    if (pathname.startsWith('/franchise/team-data') || pathname.startsWith('/roster/')) {
      await fulfillJson(route, {
        team_attributes: {
          shot_threshold: 4, rebound_modifier: 0.3, offensive_efficiency: 6, defensive_efficiency: 5,
          fb_efficiency: 2, pt_efficiency: 1, fight: 8, discipline: 4, team_chemistry: 14,
        },
        measures: [
          { key: 'offensive_efficiency', label: 'Offense', value: 6, signed_scale: 20, rank: 12, rank_of: 64, percentile: 80 },
          { key: 'defensive_efficiency', label: 'Defense', value: 5, signed_scale: 20, rank: 18, rank_of: 64, percentile: 70 },
          { key: 'team_chemistry', label: 'Chemistry', value: 14, scale_max: 25, rank: 20, rank_of: 64, percentile: 65 },
        ],
        players: [],
      });
      return;
    }
    if (pathname.startsWith('/franchise/recruiting-data') || pathname.startsWith('/franchise/recruits')) {
      await fulfillJson(route, {
        week: 3,
        phase: 'passive',
        recruits: [],
        board: [],
        orders: {},
        counts: {},
      });
      return;
    }
    await fulfillJson(route, {});
  });
}

async function waitReady(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  }, { timeout: 30000 });
  await page.waitForSelector('html.gob-shell .rail', { timeout: 30000 });
  const active = await page.evaluate(() => {
    const el = document.querySelector('.tab-content.active, .tab-content[style*="block"]');
    return el ? el.id : '';
  });
  if (active === 'game-plan-view') {
    await page.waitForFunction(() => {
      const root = document.getElementById('game-plan-view');
      return !!(root && (root.querySelector('.gp-save, .save-game-plan, button') && root.innerText.length > 80));
    }, { timeout: 20000 }).catch(() => {});
  }
  await page.evaluate(() => document.fonts && document.fonts.ready ? document.fonts.ready : null);
  const families = await page.evaluate(() => {
    const out = [];
    if (!document.fonts) return out;
    document.fonts.forEach((f) => {
      if (f.status === 'loaded' && /Bebas|Barlow|Inter/i.test(f.family)) out.push(f.family + ':' + f.weight);
    });
    return out.slice(0, 8);
  });
  if (!families.length) {
    console.warn('no app webfont loaded on', page.url());
  }
  await page.waitForTimeout(200);
}

async function waitHomeBase(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  }, { timeout: 30000 });
  await page.waitForSelector('#home-base.hb-root, #home-base .hb-top, #home-base .door', { timeout: 30000 });
  await page.evaluate(() => document.fonts && document.fonts.ready ? document.fonts.ready : null);
  await page.waitForTimeout(250);
}

async function waitTrophy(page) {
  await page.waitForFunction(() => {
    const overlay = document.getElementById('page-load-overlay');
    return !overlay || getComputedStyle(overlay).display === 'none';
  }, { timeout: 30000 });
  await page.waitForSelector('#trophy-case.hb-root, #trophy-case .tc-page, #trophy-case', { timeout: 30000 });
  await page.evaluate(() => document.fonts && document.fonts.ready ? document.fonts.ready : null);
  await page.waitForTimeout(250);
}

function fccUrl(profile, extra) {
  let url = base(profile) + '/franchise-command-center.html?franchise_id=' + FID + '&team_id=' + TID;
  if (extra) url += '&' + extra;
  return url;
}

async function shot(page, profile, name) {
  const dest = path.join(OUT, `${PHASE}-${profile}-${name}-1280.png`);
  await page.screenshot({ path: dest, fullPage: false });
  return dest;
}

async function runProfile(browser, profile) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  await setup(page, profile);
  const only = process.env.ONLY;
  const views = only ? VIEWS.filter((v) => v.file === only) : VIEWS;
  if (only && !views.length) {
    await context.close();
    return;
  }
  for (const view of views) {
    await page.goto(fccUrl(profile, view.extra), { waitUntil: 'domcontentloaded' });
    await waitReady(page);
    await shot(page, profile, view.file);
    console.log(PHASE, profile, view.file);
  }
  if (only) {
    await context.close();
    return;
  }
  await page.goto(base(profile) + '/recruiting.html?franchise_id=' + FID + '&team_id=' + TID, {
    waitUntil: 'domcontentloaded',
  });
  await page.waitForTimeout(800);
  await page.evaluate(() => document.fonts && document.fonts.ready ? document.fonts.ready : null);
  await shot(page, profile, 'recruiting');
  console.log(PHASE, profile, 'recruiting');

  await page.goto(base(profile) + '/mode-select.html', { waitUntil: 'domcontentloaded' });
  await waitHomeBase(page);
  await shot(page, profile, 'home-base');
  console.log(PHASE, profile, 'home-base');

  await page.goto(base(profile) + '/trophy-case.html', { waitUntil: 'domcontentloaded' });
  await waitTrophy(page);
  await shot(page, profile, 'trophy-case');
  console.log(PHASE, profile, 'trophy-case');

  await context.close();
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const chromePath = process.env.PW_CHROME
    || require('os').homedir() + '/Library/Caches/ms-playwright/chromium-1200/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
  const browser = await chromium.launch({ headless: true, executablePath: chromePath });
  await runProfile(browser, 'web');
  await runProfile(browser, 'desktop');
  await browser.close();
  console.log('done', PHASE);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
