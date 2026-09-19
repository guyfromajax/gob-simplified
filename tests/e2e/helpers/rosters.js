const COURT_HOME = 'Lancaster';
const COURT_AWAY = 'Four-Corners';

function courtUrl() {
  return `/static/court.html?home=${COURT_HOME}&away=${COURT_AWAY}`;
}

async function waitForCanonicalRosters(request) {
  const teams = [COURT_HOME, COURT_AWAY];
  const missing = [];
  for (const team of teams) {
    const res = await request.get(`/roster/${encodeURIComponent(team)}`);
    if (!res.ok()) {
      missing.push(`${team} → HTTP ${res.status()}`);
    }
  }
  if (missing.length) {
    throw new Error(
      `Canonical roster(s) missing: ${missing.join('; ')}. ` +
        'Playwright reused a bare `dev.py` on :8000 (empty mongomock). ' +
        'Kill that server and let webServer start tests/e2e/helpers/seed_and_serve.py.'
    );
  }
}

module.exports = { COURT_HOME, COURT_AWAY, courtUrl, waitForCanonicalRosters };
