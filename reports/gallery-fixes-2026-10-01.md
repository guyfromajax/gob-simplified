# Gallery fixes: 2026-10-01

From `reports/screen-gallery-2026-10-01.md`. Branch `ux/gallery-fixes` from `origin/develop` (`c884a3b87`), in `~/gob-audit`; upstream unset. Merged develop `46d1891f9` (jamie-decisions docs) before the full run: clean. Develop did not move after that.

Everything was checked on the **desktop SQLite e2e server** with a real Week-1 franchise (Lancaster), the same state the gallery shot. Shots: `reports/gallery-fixes/{before,after}-<item>-1280.png` (Set Lineup also at 1920), `page.screenshot` at scroll 0. Measured baseline: `reports/gallery-fixes/before-metrics.json`.

## Verify first (#1 #2 #3 #6)

| # | Gallery item | Verdict | Evidence / cause | Action |
|---|---|---|---|---|
| 1 | Court pre-game "two buttons on a blank page" | **Test-data artifact (my gallery URL)** | The gallery opened `/court.html` directly with no `game_id`, so no canvas. The real route (Set Lineup → Autoset → Play Game) lands on `/court.html?…&game_id=…&court_start=play` with a visible canvas and scoreboard: the "Concord @ Lancaster" pre-game matchup screen (probe: `canvas: 1, canvasVisible: true, scoreboard: true`; direct URL: `canvas: 0`). | None. |
| 2 | Set Lineup: five "Empty" starters at Week 1 | **Real product behaviour (logic), not seed data** | The Office Advance builds the same `/set-lineup.html?mode=franchise&…` URL the gallery used (`gobAdvance.js:615`). `set-lineup.js` autosets on load **only for `mode=tutorial`** (`set-lineup.js:2666–2677`). A first franchise game therefore opens with 15 bench rows and five empty slots; Autoset fills them (`emptyAfterAutoset: 0`). | Left (behaviour). Question for Jamie: should franchise mode preset the five like the tutorial does? |
| 2 | Set Lineup: banner lettering clipped | **Real (visual)** | 80px strip, banner 1920×679 with `object-fit: cover; object-position: center 35%`. At ~1244–1864px wide, cover shows ~18% of the banner height, so no position can keep the lockup whole. | **Fixed:** `contain` on a neutral `--surface-2` strip. |
| 3 | 77 team-art 404s / letter tiles | **Real asset gap (data), not seed** | The 404s are `/static/images/teams/<slug>/<slug>_logo_square.png`. **52 of 129** team folders have a `logo_square.png`; the rest ship only `logo_primary.png`, `wordmark`, banners and court. `common.js` then draws the generated letter tile (`TeamGeneratedArt`): the designed fallback, but the requests 404 first. Same in production (static assets come from this repo). | Left (needs art). Options: produce the ~77 `logo_square.png`, or make `getTeamAssetPath('logo_square')` fall back to `logo_primary`. |
| 6 | Leaders: five boards empty, three list 0s | **Real behaviour (logic), by design** | UX_System §13: rate leaders (FG%, DEF%) need attempts ≥ floor × team games, and zero team games never qualifies. Per-game boards (Points, Assists, Rebounds) have no rows before the first game. Total boards (3-Pointers, Blocks, Steals) return rows at 0. | Logic left. **Visual fixed:** an empty board now shows the shared empty card ("No leaders yet.") and drops its floating "Full list →". |

## Fixes (visual/layout only)

| # | Before (measured) | After | Files |
|---|---|---|---|
| 4 Box score back link | `<button class="locker-room-top-button">`: no CSS for that class, so browser default (`rgb(239,239,239)`, black text, outset border) above the shell | `.brand-back-link` (standard ghost back link), moved inside `#box-score-container` above the first card; transparent, `--white-75`, no overlap | `box-score.html`, `box-score.css` |
| 5 Cut players | Title Inter. "No Cuts Required" modal: orange `Back To Locker Room` (`rgb(247,148,32)`) with a red accent. The `#cut-players-view` modal rules never applied, because `showModal()` moves the modal to `<body>`. | Title `--font-display` (`--fs-28`). No-cuts and load-error modals: neutral accent + `gob-modal-btn-secondary` (navigation is not orange). The neutral accent rule is scoped to `body.cut-players-page` so it reaches the body-level modal. Back link was already the neutral `.brand-back-link` (`rgba(255,255,255,0.76)`, guarded). | `cut-players.css`, `cut-players.js` (variant/accent strings only) |
| 8 Player Stats "clipped" | **The gallery read was wrong:** the table is not clipped or overflowing (`scrollWidth 1178 = clientWidth 1178`; last header ends at 1261px in a 1280 viewport). The last column ("F") had no right padding and sat on the card's rounded edge, which read as clipped. | `padding-right: --space-14` on the last header and cell; the table still fits (no overflow, no scroll needed). | `css/gob-tables.css` |
| 2 Set Lineup banner | `object-fit: cover` crop through the wordmark | `object-fit: contain`, centred, strip `--surface-2` | `set-lineup.css` |
| 10 Roster toggle | "Varsity15", "Practice Squad0" (0px gap) | `--space-6` before the count: "Varsity 15", "Practice Squad 0" | `css/gob-shell.css` |
| 10 Office | Two identical "Set after camp —" rows | One placeholder line | `js/shared/officeHome.js` |
| 10 Raw empty states | Plain text lines (Practice Squad, Awards), empty Leaders boards | **One shared pattern:** `.gob-empty` neutral card (`--white-2`, 1px `--line`, `--radius-10`, `--text-60`, `--fs-14`), on Practice Squad, Awards, empty Leaders boards (and the existing Standings use). Documented in UX_System "Empty states". | `css/gob-tables.css`, `practiceSquadView.js`, `awardsView.js`, `leadersView.js` (class / empty branch only) |

Not changed, as instructed:

- **#7, the colour-law question for Jamie:** on `/training.html` the weekly **"Submit Training" is green** (Advance paint). UX_System calls it the page's own primary, not the Advance (it uses SFX_COMMIT); under the colour law a commit is orange, green is only the Advance. Separately, **"Save Game Plan" and "Save Playbooks" are orange at rest**, before any change; the law reads "orange = the enabled save". Rulings needed: (a) Submit Training green or orange; (b) should the Save buttons stay dead/neutral until something changes?
- `getPswColor` (shot-distribution / shot-weight colours) and court game-state colours: untouched.

Also noted, not changed:
- Cut Players "Assign Practice Squad" is **enabled at Week 1 with 0 to assign** (`submitDisabled: false`). It is the page's save, so orange is legal when enabled; whether it should be enabled with nothing to assign is logic.
- The leave-confirm dialog's "Stay" is still the orange modal primary (navigation). Outside the listed items.

## Tests

- **New `tests/e2e/desktop-gallery-fixes.spec.js`** (desktop config; real franchise). It covers:
  - #4: ghost class, transparent background, no overlap.
  - #5: Bebas title; disabled Assign is never orange; the no-cuts modal's navigation button and accent are not orange or red.
  - #8: last header/cell padding ≥ 12px, ≥ 8px clearance from the card edge, fits or cues.
  - #2: `contain` at 1280 and 1920.
  - #10: toggle gap ≥ 5px; exactly one "Set after camp"; a `.gob-empty` card (solid border, radius, not orange) on Practice Squad, Awards and Leaders.

  `afterAll` deletes the franchise it creates, so the shared desktop sqlite's two-franchise cap is not consumed.
- **Fails on old code:** develop's 11 changed files were served via `page.route` from a scratchpad copy of the spec (soft asserts, private sqlite). **All 10 tests fail on develop:** `transparent ghost link, got rgb(239,239,239)`; `navigation button in the modal is not orange, got rgb(247,148,32)`; `no-error modal has a neutral accent, got rgb(255,109,109)`; `last header has right padding`; `banner shows the whole lockup` ×2; `space between label and count: Varsity15`; `one "Set after camp" line`; `shared .gob-empty card present` ×3. All 10 pass on the branch.
- **Changed expectation:** `tests/e2e/office-frontend.spec.js` asserted **two** "Set after camp" rows (it encoded the duplicate). It now asserts one, per this brief.

## Housekeeping (my own test data)

The screen-gallery run and this task's first investigation each created a franchise in the **shared** `/tmp/gob-desktop-e2e.sqlite`. That file is capped at two franchises, so `desktop-play-flow` and this spec would have failed with "You already have 2 active franchises". I listed the file (exactly those two IDs, `6abe97598e4d339c0875bd8f` and `6abea01d4dfeb05deb6f4291`, nothing else), deleted both through `DELETE /franchise/{id}`, and confirmed it is empty. All later runs used a private sqlite (`GOB_DESKTOP_E2E_SQLITE` in the scratchpad), and the new spec cleans up after itself.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4298 passed**, 14 skipped, 108 xfailed, 2 xpassed, **0 failed** (232.10s) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (no pipe) |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files |
| Full Playwright, one lock session (14:31:15–14:45:59), merged tree | default config `tests/e2e --workers=1`: **825 passed, 7 skipped, 0 failed** (13.9m); desktop config (`desktop-*.spec.js`, private sqlite): **12 passed** (the 10 new + `desktop-play-flow` + desktop FAQs). No failures, so no reruns. |

## Files

`FrontEnd/static/box-score.{html,css}`, `cut-players.{js,css}`, `set-lineup.css`, `css/gob-tables.css`, `css/gob-shell.css`, `js/shared/officeHome.js`, `js/shared/views/{awardsView,leadersView,practiceSquadView}.js`, `_documentation_master/11_Design_Systems/UX_System.md` ("Empty states" + related small rules), `tests/e2e/desktop-gallery-fixes.spec.js`, `tests/e2e/office-frontend.spec.js` (one expectation), this report + shots + `reports/gallery-fixes/before-metrics.json`.
