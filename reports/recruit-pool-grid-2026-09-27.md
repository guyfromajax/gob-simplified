# Recruit pool grid — 27 Sep 2026

Branch `ux/recruit-pool-grid` off `d4a5ed707`. Mechanics unchanged: lean math, invite firing, signing resolution, and watchlist seeding are untouched. The seed stays client-side. Nothing writes FTD Recruits.

## Alignment

The hub page was still using its own frame. `.doc` padded 40px top and 32px on each side, `.spine` added 22px of top margin (already flattened under the shell), and the shell then padded `.spine-phase` and `.spine-body` another 20px on each side. That is the ~50px inset and the extra gap under the tab hairline in `reports/recruiting-tabs/passive-pool-1280.png`.

Under the shell those page paddings are now zero. The phase strip is the first content. The 8px under the hairline is the head's own `padding-bottom: var(--dsp-8)`. Measured on the Pool tab at 1280: phase top sits on the head's bottom edge, and that edge matches the League standings page's first content left edge.

Internal padding that the phase bodies still use (the filter card, the story strip, the 14px stack inside a phase column) is unchanged.

## Pool grid

The pool and the Leans tab share `rowHtml`. Both now use the roster grid: `table.pool.gob-tbl`, group header row, `GOB_AttrTiles.tileHtml(key, value, false)`, and `formatRtDisplay` / `getRtBucketClass` as `C+ → B+` with tooltip "Current → Potential".

Column order: watch star, recruit (headshot, name, archetype in `--text-60`), POS, RT, YR, HT, WT, RGN, Offense SC SH, Defense ID OD, Skills PS BH, Grit RB ST, Body AG ND, Mind IQ FT, Lean (the existing ladder), and the invite add/rank cell in weeks 20–26. There is no separate star-rating field on a recruit; the watch star is its own column and the subtitle is the archetype. Year stays the YR column.

Names are `--text-100`. The orange came from `a { color: var(--orange) }` in `recruiting-spine.css`. Orange stays reserved for saves.

At 1280 the table does not fit. It is a wide table: scroll inside `.pool-scroll`, header repeats every 16 rows (28 repeats on 450 rows), thead is `position: static`, and `.pool-scroll.gob-wide-wrap` still has no mask and no `contain`. The `elementFromPoint` check in `recruiting-tabs.spec.js` is unchanged.

Row emphasis: the frame does not paint a navy row for the user's own target. Recruits leaning to you keep the existing lean ladder and the `mine` / `list-mine` edge. No navy rows were added.

## Headshots

Every one of the 450 Lancaster recruits on the offline copy has `image_id: null`, so `headshotHtml` rendered an empty `.pc-av`. The local URL was also `/images/recruits/<id>.png`, which is not the white master (`recruits/white/<id>.png`) the paint-on-miss handler looks for, and no recruit portraits ship in the static tree. They live in R2. Offline `ensure` returns unconfigured without R2.

A recruit with an `image_id` now requests the white path, so a file that is present loads and a 404 still gets one paint retry. With no id, or after the image fails, the cell is the same initials monogram the roster and leaders use. The Lancaster copy shows 450 monograms and zero empty boxes. The packaging note is in `desktop/README.md`.

## The three specs

`fcc-invite-step` and `fcc-recruiting-buttons` extracted `updatePlayButton` from `franchise-command-center.js`. That function now only calls `GOBAdvance.updatePlayButton`, so the eval never set the button. Both specs load `gobAdvance.js` and call the advance API. Week 36 with results unseen is "View Recruiting Results"; once seen, it is the season transition. The week-35 click path in `gobAdvance.js` assigns `recruiting.html` and does not detour through cut players.

`recruit-visit-modal` still builds `.wow-roster`. `buildBody` calls `GOB_AttributeDisplay.displayAttr`, and the spec never loaded `attributeDisplay.js`, so the promise rejected before the table was inserted. The spec now loads that script. The modal on a page that already has the script was not broken.

## Other recruit rows

Left for a later pass. They do not use `rowHtml`:

- Invite board / dock rows (`board` markup in `recruiting-hub.js`): headshot, name, pos, RT, year, height, weight, lean. No attribute groups.
- Signing board rows (`prowHtml`).
- Visit calendar tiles and the weekly results panel.

`headshotBoxHtml` now uses the same portrait helper, so those surfaces get a monogram instead of an empty box. Their columns are unchanged.

## Performance

Lancaster copy, 450 rows, loopback on `/tmp/recruit-pool-offline.sqlite` (the Application Support database was not opened).

| Measure | Time |
| --- | --- |
| Recruiting payload received → rows in the DOM (first load, includes shell classify) | 422 ms |
| Re-render of all 450 rows (clear the search) | 62 ms |
| Re-render narrowed to names containing "a" | 36–65 ms |

The row rebuild is under 150 ms. The 422 ms first load is over that target and includes the shell's wide-table pass, not just the HTML build. No virtualization was added.

## Screenshots

Pointer parked in `.main`. `reports/recruit-pool-grid/`.

- Real save, week 3: `real-pool-w3-*`, `real-leans-w3-*` (2 of 450 leaning).
- Fixture week 22: `fix-pool-w22-*` scrolled to the grid (invite rank column on the right; the board sits above it), `fix-leans-w22-*`.
- Fixture week 30: `fix-pool-w30-*`.

## Tests

Playwright: recruits-pool 29, recruiting-tabs, invite-board, invite-board-layout, invite-visit-calendar, invite-seed-modal, recruiting-draft, recruiting-button-state, signing-day, signing-day-hub, signing-reveal, recruit-visit-modal, fcc-recruiting-buttons, fcc-recruiting-layout, fcc-invite-step, attr-tiles, subtabs, shell-1, shell-1b, shell-2, navigation-history. All passed.

`office-frontend`: the 1440 standings window ("shown 4, expected ≥ 5") failed on two runs. That assertion was not changed.

Python: `test_recruiting_watchlist`, `test_recruiting_wire_payload`, `test_recruiting_lean_events`, `test_recruiting_week36` — 82 passed.

## Files

- `FrontEnd/static/recruiting-hub.js` — grouped grid, monogram portraits
- `FrontEnd/static/recruiting-spine.css` — column widths, name color, tile shading, repeating header
- `FrontEnd/static/recruiting.html` — `gob-tables.css`
- `FrontEnd/static/css/gob-shell.css` — hub page inset removed under the shell
- `FrontEnd/static/js/config/api-config.js` — local recruit URL is the white master
- `desktop/README.md` — unsigned portraits on the packaging checklist
- Specs listed above

## Follow-up

Clifton Aguirre's document has the fields. Best position rating is SG 90, attributes are present (Outside Defense 105, Shooting 99, Scoring 82, and the rest), and Lean rank 1 is a school. The row builder emits RT, twelve tiles, and the lean ladder for him. A fresh element screenshot of that row shows A+ → A++, the digits, and BOI. The full-page shot did not, because `.pool thead th` used `backdrop-filter` while the wide-table wrap sets `overflow-y: clip`. That pair drops the first body row's RT, tiles, and lean from the painted layer. Plain text in the same row still paints, and the cells still hit-test, so it looked like a missing payload or an off-by-one header row. It was neither. The header repeat still starts at index 16. Removing the backdrop-filter puts the first row back. Row height stayed 42px.

Tiles now use the roster size: `var(--dsz-30)` by `var(--dsz-26)`, bold `var(--font-display)` at `var(--fs-20)`. That is 30×26 with a 20px digit at 1280, and 35.5×30.5 with a 23.5px digit at 1920. Attribute columns are `calc(var(--dsz-30) + var(--space-8))`, the same formula as the compact roster, and the wide table scrolls.

The portrait is the roster circle: 28×28, `border-radius: var(--radius-round)`, initials at 11px bold, image cover at 50% 22%.

`recruits-pool` asserts the first data row has an RT grade and twelve tile digits, and that the stylesheet uses those roster tokens. The spec stubs the recruiting payload, so it cannot open the sqlite save. On the real week-3 save the first row is Clifton Aguirre, RT A+, digits 8 9 6 10 6 5 4 6 8 5 6 6.

`office-frontend` at 1440 ("standings window shown 4, expected ≥ 5") passed 3/3 on a clean `origin/develop` worktree (`d4a5ed707`) and 3/3 on this branch. The assertion was not loosened and no Office layout change was made.

Re-run: recruits-pool 29 passed. recruiting-tabs, attr-tiles, subtabs, and shell-1b passed in the same batch (59 passed, and the one failure was the tile-size check before it was pointed at the token rather than a hardcoded 30px; recruits-pool was then re-run clean). office-frontend 9 passed, three times.

Retaken: `real-pool-w3-1280.png`, `real-pool-w3-1920.png`, `fix-pool-w22-1280.png`, `fix-pool-w22-1920.png`.
