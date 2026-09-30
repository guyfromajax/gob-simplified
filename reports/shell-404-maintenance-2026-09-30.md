# Off-brand player-facing surfaces: desktop shell + 404 + maintenance

Date: 2026-09-30
Branch: `ux/shell-404-maintenance` from `origin/develop`

Source: `reports/coverage-gap-check-2026-09-30.md` §2 and §4.

## What changed per surface

### Desktop splash (`desktop/splash.html`)

Electron `loadFile` paints before the local engine is up, so this page cannot load `FrontEnd/static`. Needed tokens are copied inline from `css/gob-tokens.css` (`--bg` `#0b0d14`, `--text-*`, `--navy-hi`, display/body faces, `--dur-pulse`). Fonts and the wordmark are local copies in `desktop/assets/`:

- `BebasNeuePro-Bold.otf` from `/fonts/`
- `Barlow-latin.woff2` = `/fonts/google/gf-03.woff2` (the app's Barlow latin 400)
- `geekedout_logo.png` = homepage lockup `images/homepage-v3/hero-logo.png` (same GOB wordmark as `/images/geekedout_logo.png`, 760×248 instead of the 1.3MB 3892×1268 source)

No remote URLs. Copy: brand mark + "Starting the local engine…" + a navy-hi pulse. No orange. No reward gold.

Window `backgroundColor` in `desktop/main.js` is `#0b0d14` (`--bg`) so there is no colour flash before paint.

### Desktop crash (`desktop/error.html`)

Same local tokens/fonts/wordmark. Headline is "The game engine stopped". The existing message `<code>` remains; no new actions (there were none). Sample-message query is read from the query string without `URLSearchParams` (desktop file, not a module view).

### Native error boxes

Still `dialog.showErrorBox`. Title is now "Geeked-Out Basketball". Copy says what happened and what to do:

- Crash fallback: the engine message, or "Quit the app and open it again."
- Checkout not found: game files (`BackEnd/loopback.py`) missing; reinstall or run from the GOB folder.
- Port in use: another copy / leftover engine is on the stable port; quit that copy; do not change the port.

### Native menu

Replaces the default Electron File/Edit/View/Window/Help menu.

**macOS**

- Geeked-Out Basketball: About, Hide, Hide Others, Show All, Quit
- Edit: Undo, Redo, Cut, Copy, Paste, Select All
- View: Reload, Toggle Full Screen; Toggle Developer Tools only when `!app.isPackaged`

**Windows / Linux**

- File: Quit (no app-name menu)
- Edit and View: same as macOS

Native menu was not captured (Electron not driven headless). Structure is as above.

### App icon + name

`package.json` `productName` and packager `--productName` / app name are **Geeked-Out Basketball** (matches Steam/docs). `desktop/pack.js` passes `--icon=build/icon` only when `desktop/build/icon.icns` (mac) / `icon.ico` (win) exists.

**No ≥512px square brand source exists.** Candidates:

| Asset | Size | Notes |
|---|---|---|
| `FrontEnd/static/images/geekedout_logo.png` | 3892×1268 | Wordmark. Used on login / auth bar. |
| `_documentation_master/12_GTM/Key_Visual_System/assets/gob_logo.png` | 3892×1268 | Same lockup. |
| `FrontEnd/static/images/homepage-v3/hero-logo.png` | 760×248 | Homepage lockup of the same wordmark. Copied to `desktop/assets/` for splash/crash. |
| `FrontEnd/static/images/favicon.ico` | 96×96 | Square, too small. |
| `Key_Visual_System/source/orange_gp_bball.svg` | 54×54 | Basketball glyph, not the brand mark. |
| KV masters / portraits | various ≥512 | Key art, not a brand icon. `discord_icon_512x512.png` / `square_1080x1080.png` are listed in the GTM manifest but are **not in the repo**. |

Did not invent a square icon. Jamie must drop into `desktop/build/`:

- `icon.icns` — macOS (1024, 512, 256, 128, 64, 32, 16)
- `icon.ico` — Windows (256, 48, 32, 16)
- `icon.png` — 512×512 (optionally 1024)

Until those files exist, `npm run pack` uses Electron's default icon and prints a one-line warning. See `desktop/build/README.md`.

`npm run pack` from `desktop/` (no icon files) succeeded:

```
> gob-desktop@0.1.0 pack
> env -u ELECTRON_RUN_AS_NODE node pack.js

No app icon in desktop/build/; using the default. See desktop/build/README.md
Packaging app for platform darwin arm64 using electron v34.5.8
Wrote new app to: out/Geeked-Out Basketball-darwin-arm64
```

### Custom 404 (`FrontEnd/static/404.html`)

Gob tokens, app fonts, wordmark. "This page doesn't exist". One button: **Home Base** (`/mode-select.html`) when `auth_token` is set, otherwise **Homepage**. No franchise data. No `URLSearchParams`.

**Netlify:** `publish = "FrontEnd/static"`. A `404.html` at the publish root is served automatically for missing URLs. No new catch-all redirect (would fight existing pretty-URL rewrites).

**FastAPI (web + desktop loopback):** HTML `Accept` on a missing page returns `404.html` at status 404. Missing `*.html` files in the static middleware do the same. `/api/…`, `/franchise/…`, and other API prefixes stay JSON 404 with the original `detail`.

### Maintenance (`FrontEnd/static/maintenance.html`)

On tokens/fonts/wordmark. Calm copy: "We'll be right back." The Netlify wildcard stays commented.

## Screenshots

Desktop pages opened as `file://` in Playwright (Electron not driven headless). 404/maintenance hit the FastAPI server.

| Surface | File |
|---|---|
| Splash before (coverage-gap, orange pulse, system font) | `reports/shell-404-maintenance/splash-before.png` |
| Splash after | `reports/shell-404-maintenance/splash-after-1280.png` |
| Crash before | `reports/shell-404-maintenance/crash-before.png` |
| Crash after (sample message) | `reports/shell-404-maintenance/crash-after-1280.png` |
| Maintenance before | `reports/shell-404-maintenance/maintenance-before.png` |
| Maintenance after | `reports/shell-404-maintenance/maintenance-after-1280.png` |
| 404 web | `reports/shell-404-maintenance/404-web-1280.png` |
| App menu | not captured — structure listed above |

## Tests

- `tests/test_ops_pages.py`: `/some-missing-page` → HTML 404; `/no-such-view.html` → HTML 404; `/api/does-not-exist` → JSON 404.
- `tests/test_desktop_shell_local.py`: splash/error reference no remote URLs; local assets exist.
- `tests/e2e/shell-404-maintenance.spec.js`: file:// splash/crash + web 404/maintenance shots.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4242 passed**, 16 skipped, 109 xfailed, **1 xpassed**, 0 failed (263.93s). XPASS is the pre-existing leaders-scope case. |
| Playwright `tests/e2e --workers=1`, PORT=50255, CI unset | **778 passed**, 6 skipped, **0 failed** (12.9m) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0. Colour-law new-design 0. |
| `scripts/ci/check_migration_gates.py` | passed. Gate A: 0/0. Gate B: 136 lines in 44 files. Did not `--write-allowlist` (pre-existing notes that training.html / training-report.html are now clean). |

## Unsure

Pack builds without the icon files (default Electron icon + warning). Jamie still needs to drop the square icon sources into `desktop/build/` for a branded pack.

`desktop/error.html` still reads `?message=` from the query Electron already passes. That is not franchise identity.
