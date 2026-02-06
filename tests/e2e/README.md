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
- **Layout/viewport tests** that start the game require the backend to have **rosters** for the teams in the URL (e.g. `Lancaster`, `Four-Corners`). If `/roster/Lancaster` or `/roster/Four-Corners` fails, the canvas never appears and those tests will timeout. Ensure your local DB has those teams (or change the test URL to use teams you have).

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
- **webServer**: Playwright auto-starts the dev server (`python dev.py`) before tests and waits for it at port 8000. If a server is already running on 8000, it is reused (`reuseExistingServer: true` when not in CI).
- Screenshots on failure
- Trace collection on retry

**Manual option:** You can instead start the server yourself in another terminal (`python dev.py`) and run tests; Playwright will reuse the existing server.

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
