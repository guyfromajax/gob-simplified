# Screenshot Tool Build Plan

**Status:** PAUSED AT TASK 6 STOP CONDITION — PHASER WEBGL CAPTURE BLANK
**Created:** 2026-08-12  
**Objective:** Retire the non-working in-browser `html2canvas` screenshot tool and
replace it with a development-only Playwright workflow that captures the browser's
actual rendered pixels without adding code or performance overhead to the shipped app.

## Decision

The current tool should be fully retired rather than patched again.

Its architecture is inherently brittle for this application: `html2canvas` reconstructs
the DOM with its own partial renderer, while GOB combines modern CSS, fixed overlays,
SVG filters, remote images, and a Phaser WebGL canvas. The current implementation then
has to sanitize the DOM, omit unsupported assets, copy the WebGL canvas, stitch multiple
canvases, and trigger an asynchronous browser download. UI changes can repeatedly break
any of those boundaries.

The replacement will use the existing Playwright dependency to run real Chromium and
call Playwright's native screenshot API. The tool will live under `scripts/` and have no
runtime bootstrap, keyboard listener, capture badge, vendor rasterizer, or Phaser render
configuration in the deployed application.

## Scope Boundaries

### Retire

- `FrontEnd/static/js/shared/captureBootstrap.js`
- `FrontEnd/static/js/shared/captureControls.js`
- `FrontEnd/static/js/shared/captureUtils.js`
- `FrontEnd/static/js/shared/captureDom.js`
- `FrontEnd/static/js/shared/captureCourt.js`
- `FrontEnd/static/js/vendor/html2canvas.min.js`
- Screenshot bootstrap injection in `FrontEnd/static/js/config/api-config.js`
- Screenshot fallback bootstrap injection in `FrontEnd/static/js/shared/sentryInit.js`
- Capture-only `preserveDrawingBuffer` configuration in
  `FrontEnd/static/js/phaser/bootGame.js`
- Screenshot-specific tests, comments, styles, documentation references, and dead
  Netlify exceptions identified by the final consumer audit
- The archived implementation brief after its historical value has been captured in
  this plan and Git history

### Preserve

- `API_CONFIG.isCaptureEnv()` until all of its non-screenshot consumers are separately
  evaluated. It currently also gates Team Builder leak detection and development-only
  generated-art behavior; it must not be deleted as part of screenshot cleanup merely
  because its name originated with the capture tool.
- `FrontEnd/static/js/phaser/utils/oobFcpHctCapture.js`. Despite its filename, this is a
  turn-data diagnostic recorder, not the PNG screenshot system.
- Existing Playwright tests, configuration, and browser dependency.
- Normal game rendering and all staging/production environment behavior unrelated to
  screenshots.

## Product Contract

The replacement should provide:

1. A terminal command that captures a supplied local or staging URL.
2. Full-page, viewport, and selected-element capture modes.
3. Native Chromium rendering of DOM, Phaser, fixed overlays, fonts, SVG, filters, and
   modern CSS in one image.
4. Deterministic viewport presets, with a documented default suitable for marketing
   screenshots.
5. A configurable output directory outside the shipped frontend assets by default.
6. Predictable filenames containing page/moment label and timestamp.
7. Optional authenticated capture through a locally stored Playwright session file.
8. No production credentials in arguments, repository files, logs, or screenshots.
9. No code loaded by the user-facing application and no production/staging runtime cost.

The replacement does **not** need to preserve `Shift+C`, the in-app REC badge, automatic
Q4 event detection, or browser-triggered downloads. Those behaviors are part of the
failed architecture and are not compatibility requirements.

## Task 1 — Final Consumer Audit and Safe Retirement

**Status:** COMPLETE — 2026-08-12

**Goal:** remove the old tool completely without deleting adjacent diagnostics or shared
environment behavior.

1. Search the tracked tree for:
   - `GOBCapture` / `GOB_CAPTURE_BOOTSTRAPPED`;
   - `captureBootstrap`, `captureControls`, `captureDom`, `captureCourt`, and
     `captureUtils`;
   - `html2canvas`;
   - capture-related `preserveDrawingBuffer` configuration;
   - screenshot-specific Netlify headers, tests, and documentation.
2. Classify every match as screenshot-tool code or a similarly named independent
   diagnostic.
3. Remove the five capture modules and vendored `html2canvas`.
4. Remove both bootstrap injection paths.
5. Remove only the capture-specific Phaser `preserveDrawingBuffer` branch. Do not alter
   normal Phaser renderer selection.
6. Remove capture-specific deployment configuration proven unused after deletion.
7. Retire the archived `screen_capture_tool_spec.md`, relying on Git history plus this
   replacement plan for rationale.
8. Verify there are no remaining runtime references to deleted assets or globals.

### Acceptance

- No `GOBCapture`, `html2canvas`, or screenshot bootstrap code remains in shipped files.
- No page requests a deleted capture asset.
- Phaser no longer enables `preserveDrawingBuffer` for staging merely because the page
  is capture-capable.
- Team Builder leak detection, generated-art development behavior, and OOB/FCP/HCT
  diagnostics remain intact.
- Frontend syntax checks and relevant existing tests pass.

### Completion record

- Removed the five capture modules, vendored `html2canvas`, both bootstrap loaders,
  and the capture-only Phaser `preserveDrawingBuffer` branch.
- Retired `screen_capture_tool_spec.md`; this plan and Git history retain the decision
  record.
- Preserved `API_CONFIG.isCaptureEnv()` because Team Builder leak detection and
  development generated-art behavior still consume it.
- Preserved `oobFcpHctCapture.js` because it records turn diagnostics and is unrelated
  to PNG screenshots.
- Preserved the general `/images/*` Netlify CORS header. It is not capture-runtime
  code, applies to active image delivery, and was not proven unused by the consumer
  audit.
- Verified no deleted screenshot globals, modules, rasterizer references, keyboard
  binding, or `preserveDrawingBuffer` setting remains in shipped code.
- `node --check` passed for all three edited JavaScript entry points, and
  `git diff --check` passed.

## Task 2 — Define the Playwright CLI Contract

**Status:** COMPLETE — 2026-08-12

Create one focused ESM script at:

`scripts/capture_screenshot.mjs`

Canonical interface:

```text
node scripts/capture_screenshot.mjs \
  --url https://staging.geekedoutbasketball.com/mode-select.html \
  --name mode-select \
  --viewport 1920x1080 \
  --output-dir tmp/screenshots
```

Supported options:

- `--url URL` — required absolute `http://` or `https://` URL. Localhost and staging
  are allowed. Reject embedded URL usernames/passwords and every other protocol.
- `--name LABEL` — optional filename label. Default to the URL pathname's final page
  component, or `homepage` for `/`. Normalize to lowercase ASCII letters, digits,
  hyphens, and underscores; reject a label that becomes empty.
- `--recipe NAME` — optional named screen metadata added in Task 5. It validates the
  URL pathname and supplies readiness, filename, viewport, delay, and optional crop
  defaults; explicitly supplied generic flags continue to win.
- `--viewport WIDTHxHEIGHT` — optional viewport in CSS pixels. Default `1920x1080`.
  Each dimension must be an integer from 320 through 7680.
- `--full-page` — capture the entire document instead of the viewport.
- `--selector CSS` — capture exactly one visible element. This conflicts with
  `--full-page`; multiple matches are an error rather than an implicit first match.
- `--output-dir PATH` — optional directory. Default to repo-root `tmp/screenshots`,
  which is already ignored by Git. Resolve relative paths from the repository root,
  create the directory when absent, and reject an existing non-directory target.
- `--wait-for CSS` — optional readiness selector. Wait for one matching element to be
  visible before the settling delay. Multiple readiness matches are allowed.
- `--delay-ms N` — optional post-readiness settling delay from `0` through `30000`.
  Default `1000` milliseconds.
- `--state PATH` — optional existing Playwright storage-state JSON file. Resolve
  relative paths from the current working directory, require a regular file, and never
  log or copy its contents.
- `--headed` — launch visible Chromium for debugging. It does not add an interactive
  pause; all readiness and timing rules remain deterministic.
- `--help` — print usage, defaults, constraints, and examples without launching a
  browser.

Capture output is always PNG. The filename contract is
`<safe-name>-<UTC YYYYMMDD-HHMMSS>.png`; if that path already exists, append a numeric
suffix rather than overwrite it. On success, print the resolved output path and no
session data. Argument/validation errors use exit code `2`; navigation, readiness,
browser, and write failures use exit code `1`; success uses `0`.

Reject conflicting capture modes, unknown flags, missing flag values, invalid numeric
ranges, unusable paths, and URLs containing credentials before browser launch. CSS
syntax and page-specific selector validity are necessarily checked after Chromium has
opened the target page and must fail with a selector-specific message. The script does
not accept database credentials, application passwords, bearer tokens, cookies, or
arbitrary request headers through CLI flags or environment variables.

### Acceptance

- `--help` documents every option and example.
- Invalid URLs, viewport strings, and locally verifiable paths fail clearly before
  launch; malformed, missing, hidden, or ambiguous selectors fail clearly after page
  creation.
- Defaults are useful without hidden environment assumptions.

### Contract decisions

- Use the repository's existing `@playwright/test` dependency and direct `chromium`
  import, matching current `.mjs` browser tooling. Do not add a CLI framework package.
- The generic command accepts a URL, not a named application screen. Named recipes are
  deferred to Task 5 so the first implementation has one navigation path.
- `--wait-for` controls readiness; `--selector` controls crop scope. They may be used
  together and have deliberately separate semantics.
- No `networkidle` default: several application screens can maintain background
  traffic. Navigation waits for `domcontentloaded`, then fonts, readiness, and the
  explicit settling delay.
- Authentication is represented only by Playwright storage state. Creation and secure
  storage of that state remain Task 4.
- No overwrite flag, JavaScript-evaluation flag, cookie/header flag, automatic game
  event trigger, or production-only mode belongs in the initial contract.

## Task 3 — Implement Native Browser Capture

**Status:** COMPLETE — 2026-08-12

1. Launch Chromium using the existing `@playwright/test` dependency.
2. Set viewport and device scale factor before navigation.
3. Load optional storage state without logging its contents.
4. Navigate with a bounded timeout and wait for `domcontentloaded`.
5. Wait for `document.fonts.ready`.
6. Wait for the optional selector and settling delay.
7. Hide development-only feedback/capture chrome through Playwright-side temporary CSS
   if needed; do not add capture CSS to the application.
8. Capture through one of Playwright's native paths:
   - `page.screenshot()` for viewport/full page;
   - `locator.screenshot()` for a selected region.
9. Write the PNG directly to disk and print only the resulting safe local path.
10. Close Chromium in `finally`, including failure paths.

For court pages, native page capture is the primary strategy. Because Chromium owns the
final composite, Phaser and DOM overlays should appear together without copying the
WebGL canvas or enabling `preserveDrawingBuffer`. Verify this empirically before adding
any court-specific code.

### Acceptance

- A DOM-heavy screen captures with fonts, images, gradients, and SVG intact.
- A court screen captures Phaser plus scoreboard/playcall overlays in one image.
- No browser download prompt is involved.
- Failure messages identify navigation, readiness, selector, or file-write failures.

### Completion record

- Added `scripts/capture_screenshot.mjs` using the repository's existing Playwright
  Chromium dependency; no frontend or deployed runtime code was added.
- Implemented viewport, full-page, exact-element, readiness-selector, settling-delay,
  output-directory, storage-state, and headed modes from the Task 2 contract.
- Added pre-launch validation, credential-bearing URL rejection, bounded waits,
  collision-safe UTC filenames, explicit exit codes, and browser cleanup in `finally`.
- Verified `--help`, invalid-protocol rejection, conflicting-mode rejection, JavaScript
  syntax, and `git diff --check`.
- Captured a real local homepage viewport PNG at `1280x720` and an exact `h1` element
  PNG at `700x70`; both were validated as non-empty RGB PNG files.
- Court compositing is deliberately not claimed from a static unauthenticated page. It
  remains in the Task 6 manual acceptance matrix and must be tested with a valid game
  session before any court-specific behavior is considered. No application-side
  workaround was added.

## Task 4 — Authentication Without Credential Sprawl

**Status:** COMPLETE — LIVE STAGING SESSION ACCEPTED

Some useful screens require an authenticated franchise session. Support this with a
separate local setup command or documented Playwright workflow that writes storage state
outside tracked source, recommended location:

`~/.config/gob/playwright-storage-state.json`

Rules:

- The file must be ignored and mode `0600` where supported.
- It must never live under the repository root unless it is an explicitly ignored,
  temporary file.
- The tool must not accept or persist Mongo credentials.
- Do not automate password entry from repository env files.
- Expired state should fail with a clear instruction to refresh it.
- Logs must never print cookies, local-storage tokens, or authorization headers.

Prefer an interactive headed login/save helper over username/password CLI flags.

### Acceptance

- An authenticated staging page can be captured without hard-coded credentials.
- A missing or expired session produces a safe, actionable error.
- Static secret scans remain clean.

### Completion record

- Added `scripts/save_screenshot_session.mjs`, a headed, manual-login helper restricted
  to localhost and staging/test hosts. Production login URLs are rejected.
- The default login target is the verified active staging frontend,
  `https://gob-test.netlify.app/login.html`; the older
  `staging.geekedoutbasketball.com` hostname does not currently resolve.
- The helper accepts no username, password, token, cookie, database credential, or
  arbitrary header. It waits only for the boolean presence of the application's
  `auth_token` and `auth_user` browser keys and never prints their values.
- State defaults to `~/.config/gob/playwright-storage-state.json`; repository-local
  destinations are rejected. Newly created private directories use mode `0700`, and
  the state file is atomically installed with mode `0600` on supported platforms.
- The capture CLI now rejects repository-local or non-private state files and reports
  an actionable refresh command when a state-backed capture lands on the login screen.
- A synthetic localhost login verified the complete headed save/load path: the file
  was mode `0600`, contained the required browser-state keys without logging values,
  loaded into the capture CLI, and produced an authenticated-path PNG.
- The synthetic state was deleted after verification. A real staging session cannot
  be created without the operator completing login and remains part of the Task 6
  authenticated-staging acceptance check.

## Task 5 — Add Named Capture Recipes Only Where Valuable

**Status:** COMPLETE — 2026-08-12

Start with the generic URL command. Add a small recipe layer only after it works reliably.
Potential recipes:

- mode select / Around the League;
- franchise command center active tab;
- recruiting pool;
- set lineup;
- training;
- game preview;
- live court at a manually prepared state;
- full-game simulation presentation.

Recipes should contain only navigation/readiness metadata: URL pattern, readiness
selector, viewport, and optional hide selectors. Avoid mirroring application state or
rebuilding gameplay logic in the capture tool.

Do not restore automatic event capture in the first release. If later required, expose a
small browser-side readiness marker or use existing stable DOM state; do not reintroduce
an in-app capture engine.

### Acceptance

- Each recipe delegates to the same generic capture implementation.
- Adding a recipe does not change production frontend code.
- Recipe failures identify the missing readiness condition.

### Completion record

- Added `scripts/screenshot_recipes.mjs` as a metadata-only catalog. Every recipe is
  resolved into the existing generic capture options and uses the same navigation,
  readiness, and screenshot implementation.
- Added nine focused recipes: `mode-select`, `around-league`, `fcc`, `recruiting`,
  `set-lineup`, `training`, `game-preview`, `court`, and `full-game-sim`.
- Recipes validate their URL pathname and provide only a safe name, viewport,
  visible/hidden readiness selectors, settling delay, and—only for Around The
  League—an element crop. They do not create franchise, roster, training, or game
  state.
- Explicit generic flags override recipe defaults. A recipe-supplied crop still
  correctly conflicts with explicit `--full-page`.
- Added hidden-state readiness for the shared page-load overlay without changing the
  public generic CLI contract or any frontend code.
- Verified recipe parsing, wrong-screen rejection, JavaScript syntax, and a real
  end-to-end `training` recipe capture. The resulting PNG was `2048x1152`, confirming
  the recipe's viewport, readiness selector, default name, and generic capture path.

## Task 6 — Tests and Verification

**Status:** AUTOMATED SUITE COMPLETE — LIVE COURT ACCEPTANCE FAILED

Add focused tests for:

1. CLI parsing and conflicting options.
2. Safe filename generation and output-path handling.
3. Rejection of non-HTTP URLs.
4. Screenshot creation against a local static fixture.
5. Selector capture dimensions.
6. Missing-selector timeout behavior.
7. Storage-state path validation without exposing state contents.
8. Static assertion that shipped frontend code does not reference the retired capture
   modules, `GOBCapture`, or `html2canvas`.

Manual acceptance matrix:

| Surface | Required result |
|---|---|
| Pure DOM | Text, fonts, colors, images, and layout match Chromium viewport |
| FCC radar/SVG | SVG and filters are present without special rasterizer handling |
| Set Lineup | Full roster and lineup layout capture at selected viewport |
| Court | Phaser court and all visible DOM overlays appear together |
| Authenticated staging | Storage state loads without credential prompts or leakage |

### Acceptance

- Focused automated suite passes.
- At least one DOM and one court PNG are manually inspected.
- `git diff --check` and environment/secret safety scans pass.

### Automated completion record

- Added `tests/test_screenshot_tool.py` with eight focused tests covering CLI defaults
  and conflicts, recipe overrides, filename sanitization and collision handling,
  non-HTTP rejection, private storage-state validation without secret leakage,
  production/session-path restrictions, recipe metadata boundaries, real Chromium
  viewport and selector capture, bounded missing-selector failure, and static
  protection against reintroducing the retired frontend runtime.
- Updated hosted CI to install Node dependencies and Playwright Chromium before pytest,
  ensuring the browser checks run rather than existing as an unexecuted local suite.
- Focused result: `8 passed`.
- Real fixture results: viewport PNG `640x480`; exact element PNG `320x180`, including
  native text and SVG rendering.
- `node --check`, `git diff --check`, and `scripts/check_env_safety.py` all pass.

### Manual acceptance status

| Surface | Status | Evidence / next requirement |
|---|---|---|
| Pure DOM | PASS | Native homepage PNG visually inspected; typography, images, gradients, and layout render together correctly. |
| FCC | PASS | Authenticated staging FCC rendered data, team art, typography, panels, and layout correctly. Radar-specific tab acceptance remains optional follow-up coverage. |
| Set Lineup | PASS | Authenticated staging roster, banner, lineup controls, and all visible columns rendered correctly. |
| Game Preview | PASS WITH EXPECTED LIMIT | Authenticated pregame DOM presentation rendered correctly; Phaser canvas does not exist until Play Quarter is selected. |
| Court | FAIL — STOP CONDITION | After an acceptance-only Play Quarter click, the Phaser canvas existed and DOM game state initialized, but its WebGL pixels captured as a blank dark rectangle. Scoreboard, rosters, team branding, and controls rendered correctly around it. |
| Authenticated staging | PASS | Private `0600` storage state loaded FCC, Set Lineup, and Court without exposing credentials. |

The court result triggers the plan's explicit stop condition: native Playwright court
capture omits the WebGL render surface. Do not add application-side render flags,
canvas copying, compositing, or gameplay hooks under Task 6. The project remains paused
until a new bounded technical investigation selects a solution.

The acceptance-only helper used to click Play Quarter was deleted after the test and
was never added to the generic command or recipe catalog.

## Task 7 — Documentation and Closeout

1. Add a concise operator guide under `00_Operations` covering installation, session
   refresh, example commands, output location, and troubleshooting.
2. State explicitly that screenshots are generated by a local Playwright operator tool,
   not by the deployed application.
3. Remove obsolete references to `Shift+C`, the REC badge, `html2canvas`, and automatic
   browser downloads.
4. Mark this plan complete only after DOM, court, and authenticated staging acceptance.
5. Move this plan to `projects/Z-Completed` after closeout if that remains the project's
   documentation convention.

## Execution Order

1. Audit and retire the old in-app implementation.
2. Lock the generic CLI contract.
3. Implement native Playwright capture.
4. Add safe authenticated-session support.
5. Add only the highest-value named recipes.
6. Run automated and visual verification.
7. Update operations documentation and close the project.

## Stop Conditions

Stop and report rather than adding application-side workarounds if:

- native Playwright court capture omits the WebGL canvas;
- authentication requires storing credentials inside the repository;
- a target screen cannot expose a stable readiness condition;
- reliable capture would require changing gameplay timing or rendering in production.

Any exception should be proven with a minimal fixture first. The replacement's defining
constraint is that screenshot tooling remains outside the shipped application.
