/**
 * WS-5a: two-axis routing table.
 *
 * Enumerates (category, runtime) and the three hostname branches of
 * _resolveBaseUrl. The web profile must produce the same host as today's
 * sniff. Desktop + runtime='local' is the seam gate: routable → loopback,
 * always-remote → remote.
 */
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const SRC = fs.readFileSync(
  path.join(ROOT, 'FrontEnd/static/js/config/api-config.js'),
  'utf8',
);

const HOST_CASES = [
  { hostname: 'geekedoutbasketball.com', remote: 'https://api.geekedoutbasketball.com' },
  { hostname: 'www.geekedoutbasketball.com', remote: 'https://api.geekedoutbasketball.com' },
  { hostname: 'staging.geekedoutbasketball.com', remote: 'https://api-staging.geekedoutbasketball.com' },
  { hostname: 'localhost', remote: 'http://localhost:8000' },
  { hostname: '127.0.0.1', remote: 'http://localhost:8000' },
  { hostname: 'gob-simplified-staging.up.railway.app', remote: 'https://gob-simplified-staging.up.railway.app' },
  { hostname: 'gob-test.netlify.app', remote: 'https://gob-simplified-staging.up.railway.app' },
  { hostname: 'gob-production.netlify.app', remote: 'https://gob-simplified-gob-backend-prod.up.railway.app' },
  { hostname: 'something.railway.app', remote: 'https://gob-simplified-gob-backend-prod.up.railway.app' },
];

const ENDPOINTS = [
  ['/api/auth/me', 'auth'],
  ['/api/auth/login', 'auth'],
  ['/app-config', 'api'],
  ['/api/billing/status', 'billing'],
  ['/api/email/send', 'email'],
  ['/api/admin/users', 'admin'],
  ['/api/feedback', 'feedback'],
  ['/api/alpha-feedback', 'alpha_feedback'],
  ['/api/leaderboard/season', 'leaderboard'],
  ['/api/community/highlights', 'community_highlights'],
  ['/franchise/start', 'franchise'],
  ['/api/gameplan', 'gameplan'],
  ['/api/playbooks', 'gameplan'],
  ['/api/plays', 'play'],
  ['/api/play/pick-and-roll', 'play'],
  ['/api/fcp-skeletons', 'skeleton'],
  ['/api/hct-skeletons', 'skeleton'],
  ['/api/run_training', 'training'],
  ['/api/teams', 'api'],
  ['/teams', 'api'],
  ['/roster', 'api'],
  ['/player-image/ensure', 'api'],
];

function loadApiConfig(overrides = {}) {
  const windowStub = {
    location: { hostname: overrides.hostname || 'localhost' },
    API_BASE_URL: overrides.API_BASE_URL,
    GOB_BUILD_PROFILE: overrides.GOB_BUILD_PROFILE,
    GOB_LOOPBACK_PORT: overrides.GOB_LOOPBACK_PORT,
    FranchiseContext: overrides.FranchiseContext,
  };
  const logs = [];
  const sandbox = {
    window: windowStub,
    console: { log: (...args) => logs.push(args), error: () => {}, warn: () => {} },
    document: undefined,
  };
  vm.runInNewContext(SRC, sandbox, { filename: 'api-config.js' });
  return { api: windowStub.API_CONFIG, window: windowStub, logs };
}

function assertEqual(actual, expected, msg) {
  if (actual !== expected) {
    throw new Error(`${msg}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
  }
}

function main() {
  const { api: probe } = loadApiConfig({ hostname: 'localhost' });
  const alwaysRemote = probe.ALWAYS_REMOTE_CATEGORIES;
  const routable = probe.ROUTABLE_CATEGORIES;
  if (alwaysRemote.length !== 8) {
    throw new Error(`expected 8 always-remote categories, got ${alwaysRemote.length}`);
  }
  if (routable.length !== 6) {
    throw new Error(`expected 6 routable categories, got ${routable.length}`);
  }

  // --- hostname branches of _resolveBaseUrl (today's remote base) ---
  for (const { hostname, remote } of HOST_CASES) {
    const { api } = loadApiConfig({ hostname });
    assertEqual(api._resolveBaseUrl(hostname), remote, `_resolveBaseUrl(${hostname})`);
    assertEqual(api.getBaseUrl(), remote, `getBaseUrl() no-args on ${hostname}`);
  }

  // --- web profile: every (category, runtime) cell is the remote base ---
  for (const { hostname, remote } of HOST_CASES) {
    const { api } = loadApiConfig({ hostname });
    for (const category of [...alwaysRemote, ...routable]) {
      for (const runtime of ['hosted', 'local']) {
        const resolved = api.resolveRouteBase(category, runtime);
        assertEqual(
          resolved,
          remote,
          `web ${hostname} category=${category} runtime=${runtime}`,
        );
        assertEqual(
          api.getBaseUrl({ category, runtime }),
          remote,
          `web getBaseUrl({${category},${runtime}}) on ${hostname}`,
        );
      }
    }
    for (const [endpoint] of ENDPOINTS) {
      assertEqual(
        api.buildUrl(endpoint),
        remote + endpoint,
        `web buildUrl(${endpoint}) on ${hostname}`,
      );
    }
  }

  // --- desktop + hosted: still remote (same as today) ---
  for (const { hostname, remote } of HOST_CASES) {
    const { api } = loadApiConfig({ hostname, GOB_BUILD_PROFILE: 'desktop' });
    for (const category of [...alwaysRemote, ...routable]) {
      assertEqual(
        api.getBaseUrl({ category, runtime: 'hosted' }),
        remote,
        `desktop+hosted ${hostname} ${category}`,
      );
    }
    // No-context callers stay on the remote base even under the desktop profile.
    assertEqual(api.getBaseUrl(), remote, `desktop getBaseUrl() no-args on ${hostname}`);
  }

  // --- seam gate: desktop + runtime='local' ---
  const LOOPBACK = 'http://127.0.0.1:8000';
  for (const { hostname, remote } of HOST_CASES) {
    const { api } = loadApiConfig({ hostname, GOB_BUILD_PROFILE: 'desktop' });
    for (const category of alwaysRemote) {
      assertEqual(
        api.getBaseUrl({ category, runtime: 'local' }),
        remote,
        `desktop+local always-remote ${hostname} ${category}`,
      );
    }
    for (const category of routable) {
      assertEqual(
        api.getBaseUrl({ category, runtime: 'local' }),
        LOOPBACK,
        `desktop+local routable ${hostname} ${category}`,
      );
    }
    for (const [endpoint, category] of ENDPOINTS) {
      const expectedBase = alwaysRemote.includes(category) ? remote : LOOPBACK;
      assertEqual(
        api.buildUrl(endpoint, { runtime: 'local' }),
        expectedBase + endpoint,
        `desktop+local buildUrl(${endpoint}) on ${hostname}`,
      );
    }
  }

  // Custom loopback port
  {
    const { api } = loadApiConfig({
      hostname: 'geekedoutbasketball.com',
      GOB_BUILD_PROFILE: 'desktop',
      GOB_LOOPBACK_PORT: 8765,
    });
    assertEqual(
      api.getBaseUrl({ category: 'franchise', runtime: 'local' }),
      'http://127.0.0.1:8765',
      'GOB_LOOPBACK_PORT',
    );
    assertEqual(
      api.getBaseUrl({ category: 'auth', runtime: 'local' }),
      'https://api.geekedoutbasketball.com',
      'loopback port does not move always-remote',
    );
  }

  // Classifier
  {
    const { api } = loadApiConfig({ hostname: 'localhost' });
    for (const [endpoint, category] of ENDPOINTS) {
      assertEqual(api.classifyEndpoint(endpoint), category, `classify ${endpoint}`);
    }
    // /api/players must not be stolen by /api/play
    assertEqual(api.classifyEndpoint('/api/players'), 'api', 'classify /api/players');
  }

  // API_BASE_URL override still wins (today's behaviour)
  {
    const { api } = loadApiConfig({
      hostname: 'geekedoutbasketball.com',
      API_BASE_URL: 'http://override.example:9',
    });
    assertEqual(api.getBaseUrl(), 'http://override.example:9', 'API_BASE_URL no-args');
    assertEqual(
      api.getBaseUrl({ category: 'franchise', runtime: 'local' }),
      'http://override.example:9',
      'API_BASE_URL with context',
    );
  }

  // FranchiseContext peek is used only when context is supplied (buildUrl).
  // On the web profile it must not change the host.
  {
    const { api } = loadApiConfig({
      hostname: 'localhost',
      FranchiseContext: { runtime: 'local' },
    });
    assertEqual(api.getBaseUrl(), 'http://localhost:8000', 'peek ignored without context');
    assertEqual(
      api.getBaseUrl({ category: 'franchise' }),
      'http://localhost:8000',
      'web + FranchiseContext.local still remote',
    );
  }

  // Stragglers no longer hardcode API hosts
  const admin = fs.readFileSync(
    path.join(ROOT, 'FrontEnd/static/js/shared/adminGuard.js'),
    'utf8',
  );
  const sentry = fs.readFileSync(
    path.join(ROOT, 'FrontEnd/static/js/shared/sentryInit.js'),
    'utf8',
  );
  for (const [name, src] of [['adminGuard.js', admin], ['sentryInit.js', sentry]]) {
    if (/https:\/\/api\.geekedoutbasketball\.com/.test(src)
      || /https:\/\/api-staging\.geekedoutbasketball\.com/.test(src)
      || /https:\/\/gob-simplified/.test(src)
      || /http:\/\/localhost:8000/.test(src)) {
      throw new Error(`${name} still hardcodes an API host`);
    }
    if (!src.includes("category: \"auth\"") && !src.includes("category: 'auth'")) {
      throw new Error(`${name} does not route via always-remote category auth`);
    }
  }

  console.log(JSON.stringify({
    ok: true,
    hostCases: HOST_CASES.length,
    categories: alwaysRemote.length + routable.length,
    endpoints: ENDPOINTS.length,
  }));
}

main();
