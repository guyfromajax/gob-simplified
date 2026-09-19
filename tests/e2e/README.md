# Frontend Layout E2E Tests

These Playwright tests verify the Grid-based layout refactor works correctly across different viewport sizes.

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Install Playwright browsers:**
   ```bash
   npx playwright install
   ```

## Requirements

- **Pre-game test** passes without starting the game (scoreboard, playcall center, stats panels, Play button visible).
- **Layout/viewport tests** that start the game need canonical rosters (`Lancaster`, `Four-Corners`). Playwright's webServer now runs `tests/e2e/helpers/seed_and_serve.py`, which seeds the same mongomock fixtures as pytest (`tests/roster_fixtures.py`) in the server process, then serves with `reload=False` so uvicorn does not fork an empty child.

## Running Tests

### Run all tests
```bash
npm test
```

### Run tests with UI (interactive)
```bash
npm run test:ui
```

### Run tests in headed mode (see browser)
```bash
npm run test:headed
```

### Debug a test
```bash
npm run test:debug
```

## Test Coverage

### Court Layout Tests (`court-layout.spec.js`)

- **Basic Structure**: Verifies all major components load and are visible
- **Viewport Stability**: Tests layout at 1920×1080, 2560×1440, and 3840×2160
- **No Overlapping**: Ensures playcall center never overlaps court (the original bug)
- **Responsive Behavior**: Verifies layout adapts correctly on resize
- **Grid Constraints**: Verifies playcall center respects grid-level height constraints

## Test Viewports

Tests run at these viewport sizes (matching refactor plan exit criteria):
- Desktop Standard: 1920×1080
- Desktop Large: 2560×1440
- Desktop iMac: 3840×2160 (original bug viewport)

## Configuration

Tests are configured in `playwright.config.js`:
- Base URL: `http://localhost:8000` (or `BASE_URL` env var)
- **webServer**: Playwright auto-starts `tests/e2e/helpers/seed_and_serve.py` (same `.venv` / `PYTHON_PATH` fallback as before) and waits for port 8000. If a server is already running on 8000, it is reused (`reuseExistingServer: true` when not in CI).
- Court-layout specs stub auth via `helpers/auth.js` and wait for seeded rosters via `helpers/rosters.js`.
- Screenshots on failure
- Trace collection on retry

**Warning:** `reuseExistingServer` will reuse a bare `dev.py` on :8000 (empty mongomock, roster 404s, no Phaser canvas). Kill that process first so Playwright can start `seed_and_serve.py`.

## CI/CD Integration

Add to `.github/workflows/test.yml`:

```yaml
- name: Install Node.js
  uses: actions/setup-node@v3
  with:
    node-version: '18'
    
- name: Install Playwright
  run: |
    npm install
    npx playwright install --with-deps
    
- name: Run Playwright tests
  run: npm test
```
