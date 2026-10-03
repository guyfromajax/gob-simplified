# Recruiting › Pool: opaque pinned header — 2026-10-02

Branch `polish/recruiting-sticky-header`, from `origin/develop` `b24564e67`; `origin/develop` `f5bc9b66f` (player-dev-grid, office-followups) merged in before the gates.

## The bug

On Recruiting › Pool, with the table scrolled under the pinned header, digits showed through the Defense, Grit and Mind header cells and the tops of the Lean chips showed through the lines between and under the header rows. Reproduced at 1280 and 1920 (`before-pool-scrolled-*.png`).

Two causes:

| | Cause | Fix |
|---|---|---|
| Digits through the shaded columns | `.gob-tbl thead tr th.gshade { background-color: var(--group-shade) }` (a 4% tint) outranked the shell's solid header fill, so a shaded header cell was a 4% tint and nothing else. | The shade is now a **layer**: header cells keep the solid `--bg-page-solid` base and take the tint as a `background-image` gradient. Body cells are unchanged (`gob-tables.css`). Same look at rest. |
| Chip tops through the two dividers | In a collapsed table the 1px border under a row is painted by the **table** where the row is laid out. The cells pin; the border stays behind. However opaque the cells, that pixel row showed the rows. | Where a header row has that border (the group row of a grouped header; every header row of the pool) the border keeps its width and goes transparent, and each cell draws the line itself with a `th::before` hung one pixel below its box: same colour, same pixel row, same heights (`gob-shell.css`). |

Plus the hairline the brief asked for: the shell now sets `is-pinned` on a table while its header is held at the top of `.main` (`paintPinnedHeaders()` in `gobShell.js`, run on `.main` scroll and on every sync), and the line under the header's last row strengthens from `--white` 8% to 14% over the page fill (the `--line-strong` composite). At rest there is none.

An earlier attempt floored `--gob-stick-row`; it is not in the change. With a floored offset the second header row overlapped the first by half a pixel and covered the line between them at 1920 when pinned.

## Which tables

Every `.gob-tbl` with a shaded header gets the shade-as-layer rule. Which of them pin, and what changed:

| Table | Header | Pinned? | Before | Now |
|---|---|---|---|---|
| Recruiting › **Pool** (`table.pool.gob-tbl`) | two rows, grouped, shaded, Lean column | yes | digits through shaded cells; chips through both dividers | opaque; hairline when pinned; **tested at 1280 and 1920** |
| Recruiting › **Leans** | the same `table.pool` (filtered) | yes | same | same fix; **tested at 1280 and 1920** |
| Recruiting › **Visits** | no table | — | — | — |
| Command center › League › **Player Stats** (`#player-stats-view .gob-pstats`) | two rows, grouped, shaded | yes, when the table fits `.main` | shaded header cells a 4% tint; the group row's border was `#franchise-container .tab-content th`'s 12% white, table-painted | opaque: an id-bearing selector in the shell outranks the FCC rule; **tested at 1280** |
| Command center › Team › **Roster** (`rosterView.js`, `.gob-xs`) | two rows, grouped, shaded | no (`.gob-xs` headers are static) | nothing shows through a static header | shade rule applies; same look |
| Command center › League › **Team Stats** (`.gob-ts`) | one row, shaded, its own solid fill and 12px cover | yes | no leak (own fill; no border) | untouched (probed: 0 leaks before and after; no travelling line added since it has no border) |
| Training Report roster / projected five (`training-report.js`) | one row, shaded | no (static) | — | shade rule applies; same look |

The travelling line is deliberately scoped to headers that **have** the border (`tr.gob-groups th`, `.pool thead th`): the base `.gob-tbl th` has no bottom border, so a generic line would have added one under Team Stats and every plain header.

## At rest

Pixel diff of the unscrolled shots before vs after (same fixture): the only changed pixel row is the header's bottom line. It was the 8% border composited over the first body row (35,37,44; and 43,45,52 under a shaded column, where the body tint showed under the line); it is now 8% over the page fill everywhere (33,35,42). One pixel row, two to ten units darker, uniform across columns. Header heights 32.5 / 33 at 1280 (34.5 / 35 at 1920) and body rows 43 (45 at 1920), zebra `--white-2`, body shade `--group-shade`, on-board tint: unchanged (asserted).

## Shots

`reports/recruiting-sticky-header/`: `before-pool-{unscrolled,scrolled}-{1280,1920}.png` (develop code, this fixture) and `after-pool-{unscrolled,scrolled}-{1280,1920}.png`. The before shots were retaken after the fixture gained plain rows (every third recruit leans elsewhere), so before and after are the same page.

## Files touched

- `FrontEnd/static/css/gob-tables.css`: the shade rule split into body (colour) and header (layer).
- `FrontEnd/static/css/gob-shell.css`: transparent borders + `th::before` divider for grouped headers and the pool; `is-pinned` hairline.
- `FrontEnd/static/js/shared/gobShell.js`: `paintPinnedHeaders()`; rAF-throttled `.main` scroll listener.
- `tests/e2e/helpers/recruitingHubFixture.js` (new): recruiting hub fixture (40 recruits; routes), `scrollMain`, `scrollTableUnder`, `inspectHeader`, `headerPixels`, `pixelDiff`.
- `tests/e2e/recruiting-sticky-header.spec.js` (new).
- `_documentation_master/11_Design_Systems/UX_System.md` ("Pinned header paint" paragraph), `Styleguide.md` (Column grouping note).
- `franchise-command-center.css` not touched (1779 lines). No sim / finalize / cpu_week_pool / sim_rng changes.

## Tests (`recruiting-sticky-header.spec.js`, 17 + 2 shot tests)

For Pool and Leans at 1280 and 1920:

| Test | Checks |
|---|---|
| No row content is visible inside the pinned header | The header's pixels pinned (2.5 rows under it) equal its pixels at rest, each scrolled pixel against the rest pixel at the same place and one row up/down (text snaps a pixel differently at another sub-pixel phase), tolerance 12 per channel, bottom row (the hairline) excluded; plus a 4px `elementFromPoint` lattice finds nothing from the body stacked above the header; the Lean column reaches the table's right edge. |
| Every header cell is painted opaque | No translucent fill, border or line; every `th.gshade` is `--bg-page-solid` with the `--group-shade` gradient layered on. |
| Hairline only once scrolled | Not `is-pinned` at rest and the line is the 8% composite; pinned → `is-pinned` and the 14% composite; back to rest → gone. |
| Body untouched | Nine rows: height 43 / 45, zebra `--white-2` on plain even rows, on-board tint where on the board, `--group-shade` on body shaded cells; header heights 32.5/33 (34.5/35). |

Plus Player Stats in the command center at 1280 (pinned, no leaks, nothing translucent). Shots behind `STH_SHOTS=before|after`.

Fail-on-old-code: with the three FrontEnd files reverted, **13 of 17** fail (every leak, paint and hairline test on both tables at both widths, and Player Stats; the leak tests report 1,700–6,400 leaked pixels). The 4 that pass are the "body untouched" guards.

## Gates (final tree: this branch merged with `origin/develop` `f5bc9b66f`)

| Gate | Result |
|---|---|
| `git fetch` + merge `origin/develop` | `f5bc9b66f` merged cleanly (the only overlap in my files was `UX_System.md`, no conflict). |
| `pytest --ignore=tests/e2e -q` | **4453 passed, 14 skipped, 108 xfailed, 2 xpassed** (exit 0, on the merged tree). No `FAILED` / `ERROR`. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** |
| `scripts/ci/check_migration_gates.py` | **passed** (Gate A 0; Gate B 133 lines in 43 files) |
| Full Playwright, once, under `/tmp/gob-full-playwright.lock` | **1200 passed, 45 skipped, 1 failed** (6.9 min). The one failure, `tutorials-fte-tokens.spec.js:236 colour law guards`, sampled the opponent rail mid-transition (`rgba(39, 85, 127, 0.984)` against the settled `rgb(31, 79, 122)`); re-run alone `--repeat-each=5`: **15 passed**. A tutorial-page flake, no table involved. |

- The 2 XPASS are the two already on the known-failures list (`test_resource_page_scoping.py::test_leaders_view_scope_filters_to_user_conference`, `test_settings_application_to_gameplay.py::…::test_settings_loaded_and_applied_to_gameplay`); no Python changed on this branch and the list was not edited.
- The migration gates still print the note that `newsView.js` fell 3 → 2 on develop (not from this branch; `--write-allowlist` not run).

## Unsure / for Jamie

- The header's bottom line at rest no longer picks up the body shade tint beneath it (one pixel row, uniform now; see "At rest"). I read "look the same at rest" as the header itself and kept it; if the tinted line under shaded columns was wanted, say so.
- Team Stats pins with its own single-row header and does not get the hairline (it has no divider to strengthen and its own `#team-stats-view` shadow rule outranks the shell). The brief's "same pinned header" pointed at the grouped two-row header, so I left it.
