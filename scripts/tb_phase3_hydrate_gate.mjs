/**
 * Team Builder §3.2a — hydrate gate + single chrome producer.
 *
 * Feasibility: sync network hydrate is not possible. Resolvers own
 * ensureTeamBuilderVisualReady(); chrome paint awaits it. Sync paint
 * (applyTeamVibrantDocumentVarsNow) throws in capture/dev/staging when the
 * gate is unset; production logs only (observe-only).
 *
 * Run: node scripts/tb_phase3_hydrate_gate.mjs
 */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'FrontEnd/static/common.js'), 'utf8');

function makeSandbox({ captureEnv }) {
  const cssProps = {};
  const documentElement = {
    style: {
      setProperty(k, v) {
        cssProps[k] = v;
      },
    },
  };
  const document = {
    documentElement,
    createElement() {
      return { async: false, src: '', onload: null };
    },
    head: { appendChild() {} },
    querySelector() {
      return null;
    },
    readyState: 'loading',
    addEventListener() {},
    body: null,
  };
  const location = {
    search: '?franchise_id=fid-test&home=Concord&home_display=WrongURL',
    hostname: captureEnv ? 'localhost' : 'www.geekedoutbasketball.com',
    pathname: '/court.html',
  };
  const logs = [];
  const sandbox = {
    window: { FranchiseLS: null, location },
    document,
    location,
    localStorage: {
      getItem() {
        return null;
      },
      setItem() {},
      removeItem() {},
    },
    console: {
      log: (...a) => logs.push(['log', a]),
      warn: (...a) => logs.push(['warn', a]),
      error: (...a) => logs.push(['error', a]),
    },
    encodeURIComponent,
    String,
    Math,
    Number,
    Object,
    Array,
    Promise,
    URLSearchParams,
    fetch: async () => {
      throw new Error('fetch should not be required after payload hydrate');
    },
    API_CONFIG: {
      buildUrl: (p) => p,
      getAuthHeaders: () => ({}),
      isCaptureEnv: () => !!captureEnv,
    },
    cssProps,
    logs,
  };
  sandbox.window.document = document;
  sandbox.window.location = location;
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox);
  return sandbox;
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

// --- Strict env (dev/staging): sync paint without hydrate throws ---
{
  const s = makeSandbox({ captureEnv: true });
  let threw = false;
  try {
    s.applyTeamVibrantDocumentVarsNow(
      'Concord',
      'Ada',
      { primary_color: '#ec1d28' },
      { primary_color: '#00ff00' }
    );
  } catch (e) {
    threw = /hydration settled|Team Builder visual/i.test(String(e && e.message));
    assert(threw, 'expected hydrate-gate error, got: ' + (e && e.message));
  }
  assert(threw, 'strict env: chrome without hydrate must throw');
}

// --- Production: sync paint without hydrate logs, does not throw ---
{
  const s = makeSandbox({ captureEnv: false });
  s.location.hostname = 'www.geekedoutbasketball.com';
  s.window.location = s.location;
  let threw = false;
  try {
    s.applyTeamVibrantDocumentVarsNow(
      'Concord',
      'Ada',
      { primary_color: '#ec1d28' },
      { primary_color: '#00ff00' }
    );
  } catch (e) {
    threw = true;
  }
  assert(!threw, 'production: chrome without hydrate must not throw');
  assert(
    s.logs.some((row) => row[0] === 'error' && /hydration settled/i.test(String(row[1][0]))),
    'production: must console.error the gate miss'
  );
}

// --- After payload hydrate: visual beats URL; palette + matchup chrome ---
{
  const s = makeSandbox({ captureEnv: true });
  s.hydrateTeamBuilderVisualFromFranchisePayload(
    {
      team: 'Alexandria',
      is_custom_team: true,
      asset_strategy: 'generated',
      primary_color: '#112233',
      secondary_color: '#445566',
      team_builder_replaced_name: 'Concord',
      team_builder_replaced_primary_color: '#ec1d28',
      abbreviation: 'ALX',
      jersey_preset: 1,
    },
    'fid-test'
  );
  assert(s.isTeamBuilderVisualReady() === true, 'ready after payload hydrate');

  const label = s.resolveTeamBuilderDisplayName('Concord', 'WrongURL');
  assert(label === 'Alexandria', 'display name authority is visual, not URL; got ' + label);

  const pal = s.resolveTeamBuilderPaletteColors('Concord', { primary_color: '#ec1d28' });
  assert(pal.primary_color === '#112233', 'palette authority is visual; got ' + pal.primary_color);

  s.applyTeamVibrantDocumentVarsNow(
    'Concord',
    'Ada',
    { primary_color: '#ec1d28' },
    { primary_color: '#00ff00' }
  );
  assert(s.cssProps['--home-vibrant-color'] === '#112233', 'css home from visual');
  assert(s.cssProps['--away-vibrant-color'] === '#00ff00', 'css away from fallback');

  const homeEl = { textContent: '' };
  const awayEl = { textContent: '' };
  await s.applyTeamBuilderMatchupChrome({
    homeCore: 'Concord',
    awayCore: 'Ada',
    homeUrlDisplay: 'WrongURL',
    awayUrlDisplay: 'Ada',
    homeColors: { primary_color: '#ec1d28' },
    awayColors: { primary_color: '#00ff00' },
    homeLabelEl: homeEl,
    awayLabelEl: awayEl,
    franchiseId: 'fid-test',
  });
  assert(homeEl.textContent === 'Alexandria', 'matchup chrome label from visual');
  assert(awayEl.textContent === 'Ada', 'away unchanged');
}

console.log('tb_phase3_hydrate_gate: OK');
console.log(
  JSON.stringify(
    {
      feasibility:
        'Sync network hydrate is not feasible; resolvers own ensureTeamBuilderVisualReady(); chrome paint awaits it. Strict throw is capture/dev/staging only.',
      callers:
        'Production sync paint only via applyTeamVibrantDocumentVars / applyTeamBuilderMatchupChrome after await ensure.',
    },
    null,
    2
  )
);
