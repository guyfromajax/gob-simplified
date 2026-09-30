# Prep Training + Training Report tokens — 2026-09-30

Branch: `ux/prep-training-tokens` from `origin/develop` (`0102814fe`).
Visual-only. Colour law wins over frames (Jamie).

## What changed

Player Training and Training Report now sit on `gob-tokens` / UX_System colour law.

- Raw green / orange / reward-gold chrome is gone except the allow-list: Advance green (`#play-now` / `#submit-btn.advance`), positive-data pill fills, committed orange (custom-focus Assign only).
- Choice controls (sliders, radios, playbook segment, focus chips) are neutral.
- `▲` glyphs are white (Jamie). Only data bands may be green.
- Player headshots are square (`--radius-6`).
- Team Report stays at 11 measures (no Momentum). Labels: Shooting, Rebounding, Offense, Defense, Fast Break, P/T Defense, Fight, Discipline, Team Chemistry, Fast Break Defense, P/T Offense.
- Standalone `training.html?mode=tutorial` is `.gob`, loads `gob-tokens.css`, and keeps `#submit-btn` visible with class `advance`.
- In-app `#training-view` / `#training-report-view` unchanged in identity: `FranchiseContext.get`, no new `URLSearchParams`.

## Per-file hit counts (colours / type / colour-law)

From `scripts/check_ui_tokens.py` on `origin/develop` vs this branch. Law is green + orange + reward-gold.

| File | Before (develop) | After | Surface |
|---|---|---|---|
| `training.css` | 246 / 122 / **51** | 36 / 28 / **0** | new-design |
| `training-report.css` | 152 / 150 / **17** | 19 / 24 / **0** | new-design |
| `css/training-newswire.css` | 35 / 45 / **3** | 4 / 17 / **0** | new-design |
| `css/player-development-grid.css` | 21 / 36 / **3** | 3 / 29 / **0** | new-design |
| `css/development-focus.css` | 11 / 10 / **1** | 0 / 0 / **0** | new-design |
| `training-report.js` | 2 / 1 / 0 | 0 / 0 / 0 | still legacy (no law) |
| `training.js` | (unused hex in tooltip registry) | 0 / 0 / 0 | still legacy |

Leftover literals are rem/`999px`/non-token greys, not law colours. `training-report.css` keeps one `rgba(255,255,255,0.85)` on the Back ghost so the develop before-metrics fixture stays green (no `--white-85` token).

`scripts/check_ui_tokens.py` `NEW_DESIGN_CSS` now includes the five CSS files above. Recruiting files were not on this branch; if the audit agent lands them later, keep both sets.

## Frame vs colour-law

Served from `_documentation_master/projects` so frame CSS loaded. Jamie: law wins.

| Frame | Conflict | Choice |
|---|---|---|
| `prep-training-1280` v1 | Gold titles, orange slider pips / req chips / focus chrome | Neutral tokens. Sliders stay grey. |
| `prep-training-1280` v2 | Already tokenized pips (`.ps b.f` = `--white-45`). Submit is Advance (disabled = grey on the frame) | Keep. Live Advance is `--green` when enabled. |
| v2 focus chips / playbook `seg` | Frame `.fc.on` is already white | Same. No orange/green on choice controls. |
| v2 RT letters `t-green` / `t-blue` | Allowed tier ramp (B green, A / 9+ blue) | Kept. |
| `prep-training-report` v1/v2 | Gold notes headers; green `+N` / orange chemistry in older live CSS | Notes headers `--text-60`. `▲` white. Pill *fills* stay `--green` (`/* colour-law: positive-data */`). |
| v2 `.dl.u` | `▲` prefix, no green paint | Match: `.change-delta` is `--text-100`. |
| Practice-player gold wash | `rgba(245,197,24,…)` | `--white-9`. No reward gold. |
| Locker-room / Back | Old live CSS used green as “accent orange” | Ghost (`--white-6` / `--white-18`). |
| Custom-focus Assign | Frame would paint it as a save | `--orange` + `/* colour-law: committed */`. |
| Standalone Submit | Frames treat Submit Training as the page Advance | `#submit-btn.advance` → `--green`. |
| Archetype colour chrome (red/purple headers) | Not “yours” navy | Neutral `--text-60` / `--arch: var(--text-38)`. |

## Shared CSS left alone

- **`resource-pages.css`** — 9 law hits. Not restyled. Training aliases live under `#training-view` / `body.training-page` and `#training-report-view` / `.training-report-page`.
- **`franchise-command-center.css`** — not touched. Leftovers that still paint Training-*looking* chrome:
  - `#franchise-container .training-report-styled` (Team **Stats** tab, not Training Report): `--color-accent-orange: #34ec27`, `--color-warning: #ffcd26`, gold `.pill-center-line`, orange `.fcc-chemistry-bar-fill`, `data-tone="warning-elite"` orange wash.
  - Same block’s `.pill-fill-positive` green (legal as positive data if that tab uses it).
- **`command-center-team-styles.css`** — still loaded on FCC / court; scoped to `.training-report-styled`. Training Report markup does not use that class.
- Recruiting, `office-home.*`, `officeHome.js`, `gob_nav` / alpha-badge, sim, `uiSfx`: not touched.

## Markup / JS

- `training.html`: `class="gob"`, `gob-tokens.css`, `#submit-btn` has `advance`. Existing stub `URLSearchParams` redirect is unchanged (not a module view).
- `training.js`: dropped unused drill `color` hex; no inline gold/orange; `--arch` stays `var(--text-38)`.
- `training-report.js`: notes hero accents → tokens; ups use `change-delta`; momentum/playbook fills use tokens; placeholder `--text-38`.

## Follow-up (2026-09-30, pre-merge)

**1. Report header overlap.** Capture helper, not a product scroll. Live office drill-in and Training-submit landing are byte-identical on this branch and `origin/develop` at the moment of capture: all three scroll values are 0, `document.activeElement` is `BODY`, title and meta do not intersect, Back top equals the view top.

Office → drill-in (the flow that writes `after-report-*.png`):

| | branch | develop |
|---|---|---|
| window.scrollY | 0 | 0 |
| #gob-main.scrollTop | 0 | 0 |
| #training-report-view.scrollTop | 0 | 0 |
| activeElement | BODY | BODY |
| title | top 74 / bottom 106 | top 74 / bottom 106 |
| meta | top 124.9 / bottom 141.1 | top 124.9 / bottom 141.1 |
| Back | top 106 / bottom 148 | top 106 / bottom 148 |
| view top | 106 | 106 |
| title ∩ meta | false | false |

Training submit → report (`from=training`, `origin=prep`; Prep subtabs keep `.pg-head` at 114px):

| | branch | develop |
|---|---|---|
| window.scrollY | 0 | 0 |
| #gob-main.scrollTop | 0 | 0 |
| #training-report-view.scrollTop | 0 | 0 |
| activeElement | BODY | BODY |
| title | top 74 / bottom 106 | top 74 / bottom 106 |
| meta | top 188.9 / bottom 205.1 | top 188.9 / bottom 205.1 |
| Back | top 170 / bottom 212 | top 170 / bottom 212 |
| view top | 170 | 170 |
| title ∩ meta | false | false |

The first `after-report-1280.png` (commit `5c42806a6`) was taken after this line in `tests/e2e/prep-modules-report.spec.js` (Office drill-in), which used to run *before* the full-page shot:

```
await page.locator('#training-report-view .team-section').screenshot({
  path: path.join(nitShots, 'team-report-after-1280.png'),
});
```

Playwright's `locator.screenshot()` calls `scrollIntoViewIfNeeded`. That scrolled `#gob-main`. `.training-report-page .report-header` is `position: sticky; top: 10px`, so the meta line and Back slid under sticky `.pg-head` (~31px — Back's 42px height clipped to its bottom curve). `b6aea347f` already moved that crop after the full-page shots; the retake there matches `before-report-1280.png` in the header band (pixel energy identical y=60–200). Capture now asserts the three scroll values, no title/meta intersection, and Back top ≥ view top *immediately before* `page.screenshot()`, and only then takes element crops.

**2. Player Development “develops” codes.** Information, not a committed control. The hover card copy is `{position} · {focusLabel} develops {codes}` (or `adds {codes}` when the focus is not Standard). That names which attributes the training-matrix profile raises for that position + focus. The focus itself is a roster choice; the orange was on the derived codes, which are a read-out. Neutralized to `--text-87`. `tests/test_player_development_grid.py` now asserts that token and no `colour-law: committed`.

## e2e

Computed-style guards (not class names):

- Training in-season: sliders / radios / toggles must not compute green or orange; headshot `border-radius` has no `%` and ≤ 8px.
- Report office drill-in: same for toggles; portrait radius ≤ 8px.
- Existing geometry before-metrics (`reports/prep-modules-training/before-metrics.json` and report notes/headshot/Back fixture) stay green.

## Screenshots

All under `reports/prep-training-tokens/`. After shots taken at the listed viewport (open each, not a crop unless noted).

| State | Before | After | Frame (beside) |
|---|---|---|---|
| Training in-season 1280 | `before-in-season-1280.png` | `after-in-season-1280.png` | `frame-training-v2-1280.png` (also v1) |
| Training in-season 1920 | `before-in-season-1920.png` | `after-in-season-1920.png` | — |
| Camp (week 1) 1280 | `before-camp-1280.png` | `after-camp-1280.png` | same training frames |
| Post-week-26 1280 | `before-post-week-26-1280.png` | `after-post-week-26-1280.png` | — |
| Custom-focus modal 1280 | `before-custom-focus-1280.png` | `after-custom-focus-1280.png` | — (Assign orange) |
| Tutorial standalone 1280 | `before-tutorial-1280.png` | `after-tutorial-1280.png` | — (`#submit-btn` visible, green) |
| Training Report 1280 | `before-report-1280.png` | `after-report-1280.png` | `frame-training-report-v2-1280.png` (also v1) |
| Report notes only | — | `after-report-notes-1280.png` | notes column on the v2 frame |
| Team Report only | — | `after-report-team-1280.png` | Team Report on the v2 frame |
| Training Report 1920 | `before-report-1920.png` | `after-report-1920.png` | — |

## Gates

- `.venv` via `../gob-simplified/.venv/bin/python -m pytest --ignore=tests/e2e -q`: **4180 passed**, 14 skipped, 109 xfailed, **1 xpassed** (`test_leaders_view_scope_filters_to_user_conference` — known; list not edited). **0 failed.** (A sandbox rerun without `PLAYWRIGHT_BROWSERS_PATH` failed 3 screenshot/loopback tests; those 3 pass with the cache path set.)
- Targeted Playwright (training + report specs, workers=1, PORT=8183): **18 passed** (includes capture-time header guard).
- Full Playwright (`env -u CI PORT=8178 BASE_URL=http://localhost:8178 … --workers=1`): **755 passed**, 4 skipped, **0 failed** (11.1m).
- `scripts/check_ui_tokens.py --strict --no-write`: **exit 0**, new-design law **0**.
- `scripts/ci/check_migration_gates.py`: **pass**. Gate A 0/0, Gate B 136/44. `--write-allowlist` not used.

## Files touched

- `FrontEnd/static/training.css`
- `FrontEnd/static/training-report.css`
- `FrontEnd/static/training.html`
- `FrontEnd/static/training.js`
- `FrontEnd/static/training-report.js`
- `FrontEnd/static/css/training-newswire.css`
- `FrontEnd/static/css/development-focus.css`
- `FrontEnd/static/css/player-development-grid.css`
- `scripts/check_ui_tokens.py`
- `tests/e2e/prep-modules-training.spec.js`
- `tests/e2e/prep-modules-report.spec.js`
- `tests/test_player_development_grid.py` (develops codes are `--text-87`, not committed orange)
- `reports/prep-training-tokens-2026-09-30.md`
- `reports/prep-training-tokens/*`

`tmp/remap-training-tokens.py` is a local remapper — **not committed**.
