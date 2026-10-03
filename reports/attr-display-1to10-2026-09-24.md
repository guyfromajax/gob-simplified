# Attribute display, first digit — 2026-09-24

Branch `ux/attr-display-1to10` cut from `develop`. Not merged. Not pushed.

Attributes stay stored raw. Every frontend surface that shows one now goes through `window.GOB_AttributeDisplay` (`FrontEnd/static/js/utils/attributeDisplay.js`). The displayed number is `Math.floor(raw / 10)`: raw 1–9 → 0, 77 → 7, 99 → 9, 105 → 10, 160 → 16. 0 is valid. There is no upper cap. The color tier is that displayed number: 0–4 low (red), 5–6 mid (yellow), 7–8 high (green), 9+ elite (blue). RT letter grades are unchanged.

## Helper

`FrontEnd/static/js/utils/attributeDisplay.js` replaced the unused ES module (`formatAttribute` / `formatNG`, imported nowhere). It is a classic script, `window.GOB_AttributeDisplay`, and `module.exports` for node, same exposure pattern as `attrTiles.js`.

- `rawAttr(attrs, key)` — `anchor_<KEY>`, then `<KEY>`. `null`, `undefined`, and `''` fall through. `0` is kept. (`attributeDisplay.js:25`)
- `displayAttr(raw)` — floor divide by 10. `null` for null, undefined, `''`, and non-numeric. (`:33`)
- `attrTier(display)` — `'low' | 'mid' | 'high' | 'elite'`, or `null`. (`:40`)

Loaded before `attrTiles.js` and before the page script on every page that formats attributes or calls `getAttrColor`: `set-lineup.html`, `player-detail.html`, `roster.html` (`/static/js/utils/…`), `team-roster-view.html`, `recruiting.html`, `franchise-command-center.html`, `training.html` (also loads `rtBucket.js`, which that page did not have), `training-report.html`, `news.html`, `cut-players.html`. E2E script lists that inject `attrTiles.js` load the helper first.

## Sites

| Site | Lines | Before | After |
|---|---|---|---|
| `js/shared/attrTiles.js` `tileValue` / `tierClass` | 71–84 | own anchor read + floor; tiers 10+ elite, 7–9 high, ≤3 low, else none | `displayAttr(rawAttr)`, `attrTier` → `is-elite` / `is-hi` / `is-mid` / `is-lo` |
| `set-lineup.js` sort | 1374–1382 | floor of `anchor_ ?? key ?? 0` | same number, via helper. Missing still sorts as 0 |
| `set-lineup.js` roster tail | 1623–1644 | same floor, missing 0 | same |
| `set-lineup.js` attribute pills | 3406–3415 | floor number, color `getAttrColor(ceil(raw/10))` | floor via helper, color `getAttrColor(raw)` |
| `franchise-command-center.js` `fccShownAttr` | 2440–2444 | — | missing displays and sorts as 0 |
| FCC signed-recruit `attrs` map | 2482–2495 | floor of the plain key only | `fccShownAttr` (anchor first). Tiles still use `rawAttrs` |
| FCC legacy recruit table | 2778–2780 | floor of `a.SC` etc. | `rawAttr` on the bag |
| FCC attribute sort | 3515–3516 | floor of `anchor_ ?? key ?? 0` | same number via `fccShownAttr` |
| `training-report.js` read | 947–954 | `player.attributes[attr]`, no anchor | `rawAttr` for the 12. NG / EM / MO unchanged |
| `training-report.js` cell | 1047–1048 | local floor | `displayAttr`. Missing prints 0 |
| `team-roster-view.js` | 468–475 | own anchor read + floor. Missing display `--`, sort `-Infinity` | helper. Those missing-value rules kept. `getRawAttrValue` removed |
| `news.js` | 90–93 | own anchor read + floor, `--` | helper, `--` |
| `player-detail.js` | 89–104 | `max(1, floor(raw/10))`, color from `ceil(raw/10)` | no minimum clamp. Color from the raw value |
| `recruiting-common.js` | 175–177, 208 | floor of `attrs[key]` only. Missing 0 | `rawAttr`. Missing still 0 (sort field stays a number) |
| `cut-players.js` | 125–128 | anchor if not null, else key. Missing 0 | `rawAttr`. Missing still 0 |
| `walkOnWelcomeModal.js` | 94–97 | own anchor read, `--` | helper, `--` |
| `recruitVisitModal.js` | 93–96 | own anchor read, `--` | helper, `--` |
| `roster.js` table | 32–41 | plain key, floor. NG `toFixed(2)` | `rawAttr` + `displayAttr`. NG still two decimals |
| `roster.js` cards | 137–145, 232–251 | plain key, color `ceil(raw/10)` | `rawAttr`, `getAttrColor(raw)`. NG color is the exception below |
| `playerDevelopmentGrid.js` hover values | 48–55, 99–109 | raw number | first digit. Accent stays on the code |
| `playerDevelopmentGrid.js` RT | 206, 269 | numeric RT | `formatRtDisplay` letter grade. `rtAtTrainingPosition` still returns the number |
| `training.js` Custom Focus | 649–651 | raw `row.attrs[code]` | first digit. Missing still `—` |
| `tutorial-player-attributes.html` | 113–126 | 0–40 / 41–60 / 61–80 / 81+, ticks 0 and 100+ | 0–4 / 5–6 / 7–8 / 9+, ticks 0 and 10+, note that values above 10 are possible |
| `tutorial-recruiting.html` | 221–224 | 0–29 / 30s / 40s / 50+ | F / D / C / C+ and above (`rtBucket.js`) |
| `common.js` `getAttrColor` | 1199–1214 | argument was a ceil bucket | argument is the raw attribute. Tier from `attrTier(displayAttr(raw))`. Same four hexes |
| `css/attr-tiles.css` | 49–51 | no mid class | `.is-mid` |
| `css/player-development-grid.css` | 145–158 | `justify-content: space-between`, column gap 6px | `flex-start`, intra-pair gap 4px, column gap 18px |
| `recruiting-hub.js` | was line 71 | `attrClass` never called | deleted |

Sort semantics kept: set-lineup and FCC missing → 0; team-roster missing → `-Infinity`; tiles missing → `null` and `compareByAttr` still treats that as -1.

## Where the number can change because of the anchor read

These sites previously read the plain key and ignored `anchor_<KEY>`. They now use `rawAttr`. The digit changes only when both keys are present and differ (or only the anchor key exists).

1. `recruiting-common.js:208` — the scaled `attrs` map used by `getSortValue`. The tiles already read `rawAttrs` and already preferred the anchor, so the chip does not move. A sort on that scaled field can.
2. `franchise-command-center.js:2482–2495` — the signed-recruit scaled `attrs` map. Tiles use `rawAttrs` and already preferred the anchor. Same split as recruiting.
3. `franchise-command-center.js:2780` — the legacy recruit table. These cells were the plain key. They now prefer the anchor. Visible.
4. `roster.js:37` and `roster.js:143` — table and cards. Visible, including the card bar, which now fills from the anchor raw.
5. `training-report.js:952` — the attributes view. Visible when the payload carries `anchor_<KEY>`. NG, EM, and MO are not read this way.

`training.js` Custom Focus does not change from the anchor rule. The server (`franchise_routes.py` `_build_custom_focus_roster_for_franchise`) already stores the anchor-preferred integer on the plain key. The cell changes from that raw integer to its first digit.

`''` on an anchor key now falls through to the plain key, matching the tile builder. These sites used to keep the empty string and then coerce it to 0:

- `player-detail.js` (`??` kept `''`, then the clamp showed 1)
- `set-lineup.js` sort, roster tail, and pills
- `franchise-command-center.js` attribute sort
- `cut-players.js` (`== null` only)
- `playerDevelopmentGrid.js` `attrValue` (`== null` only; `Number('')` was 0)

News, the walk-on modal, the visit modal, team-roster, and the tiles already treated `''` as missing.

## Color

`getAttrColor` now takes the raw value. Passing a pre-bucketed 8 would floor-divide again and paint red. Callers pass raw: `player-detail.js:100`, `set-lineup.js:3415`, `roster.js:251`.

Raw 85: every surface shows **8** and the high/green tier. Bars `#34EC27`. Tiles `is-hi` (existing green text `#9cf294`, not the bar hex). Raw 90: every surface shows **9** and the elite/blue tier. Bars and elite tile text `#4A90D9`. Confirmed in the browser against the real helper and `getAttrColor`: `{ raw85: "#34EC27", shown85: 8, tier85: "high", raw90: "#4A90D9", shown90: 9, tier90: "elite" }`.

Bar colors move wherever `ceil(raw/10)` crossed a tier that `floor(raw/10)` does not:

- raw 41–49: yellow → red (display 4)
- raw 61–69: green → yellow (display 6)
- raw 81–89: blue → green (display 8). This is the raw-85 bug.
- multiples of 10 stay put (80 green, 90 blue, 100 blue)

Tile colors move because the tier rule changed, not because the read changed:

- display 4: no class → `is-lo` (red)
- display 5–6: no class → `is-mid` (yellow)
- display 9: `is-hi` (green) → `is-elite` (blue)
- display 0–3, 7–8, and 10+ keep the class they had

Player detail no longer clamps the digit to 1. Raw 1–9 shows 0, and the bar fill is 0% (it was 10% because of the clamp). A displayed 16 still fills the bar to 100%. That cap is the bar width, not a data cap.

## Flagged

- **Tile mid tier.** Tiles had no yellow. Added `.attr-tile.is-mid` with background `rgba(255, 215, 0, 0.15)` (same alpha as `is-hi`) and text `#FFD700`. The other tile text colors are tints (`#9cf294`, `#ffa8a8`); this one is the styleguide yellow itself, because that hex was specified. The tile grid is otherwise untouched. A redesign is still coming.
- **Hover column gap is 18px.** The intra-pair gap stays 4px and the row uses `flex-start`, so the value sits next to its code. 18px is the widened gap between cells (was 6px). Fonts and sizes are unchanged.
- **Attribute-scale bar widths** on `tutorial-player-attributes.html` are 46% / 18% / 18% / 18%, proportional to five steps (0–4), two (5–6), two (7–8), and a 9–10 slice. The line under the legend says values above 10 are possible. The recruiting RT bar widths are unchanged (still the old 34/24/22/20 split); only the labels became letters.
- **Recruiting tutorial prose** at `tutorial-recruiting.html:226` still says a 45 could become a ~90. That sentence is about the underlying rating, not the legend. Left it.
- **NG** on `roster.js:248–251` is a coefficient, not a raw attribute. It still prints two decimals. Its bar color round-trips the old `Math.ceil(ng * 10)` bucket through `getAttrColor` by multiplying that bucket by 10. That `Math.ceil` is the one remaining attribute-adjacent bucket, and it is NG only.
- **Team Builder** (`js/team-builder/roster.js` `scaleColor`, bands at 40/60/80, values shown raw, cap 99) was left alone. The task said not to change Team Builder caps, and it is an editor of the raw number.
- **Styleguide** (`_documentation_master/11_Design_Systems/Styleguide.md` Attribute Bar Scale and Attribute Tiles) still describes 0–40 / 41–60 / 61–80 / 81+ for bars and 10+ / 7–9 / ≤3 for tiles, and it says the two scales are an unresolved design choice. This task converges them on the displayed digit. The styleguide was not edited.
- **Scouting** `BackEnd/utils/scouting_utils.py:214` is `int(float(raw)) // 10` after `anchor_` then the plain key. For positive values that matches `Math.floor(raw / 10)`. `scoutingReport.js:85–91` already consumes that integer and must not divide again. Left both.
- **`training_report_display_bucket`** (`training_execution_v2.py:200`) is the same floor divide, used for the movement arrow (`-1/0/1`), not for the cell. The cell still receives the raw value and now calls `displayAttr` once. Left the Python function.

## Remaining `/10` hits that are not attributes

- `js/utils/attributeDisplay.js:37` — the one attribute conversion.
- `js/phaser/utils/simCalloutCadence.js:82` — `Math.floor(p.pts / 10)`, points.
- `coaching-grid.js:21` — `momentum / 10`.
- `js/phaser/gameScene.js:361` — `ev / 10`.
- `news.js` / walk-on / visit / `playerDevelopmentGrid.js` — `height / 12`.
- `BackEnd/api/franchise_routes.py:11827` — `prestige // 10`.
- `BackEnd/utils/scouting_utils.py:214` and `training_execution_v2.py:203` — the two server floors described above.
- Grid, animation, and timing divisions by 100 or 1000.

No `Math.ceil(raw / 10)` attribute bucket remains. The NG `Math.ceil(ng * 10)` on `roster.js:250` is the coefficient exception above.

## Tests

- `node --test tests/test_attribute_display.js` — 4 passed. Covers 1→0, 9→0, 10→1, 19→1, 77→7, 89→8, 90→9, 99→9, 100→10, 105→10, 160→16, null/undefined → null, and tiers 0/4 low, 5/6 mid, 7/8 high, 9/12 elite. Also raw 85 → 8 high and raw 90 → 9 elite.
- `pytest tests/test_player_development_grid.py tests/test_development_focus_surfaces.py tests/test_training_page_phase5.py` — 134 passed. The grid harness now loads the helper before `attrValue`. `rtAtTrainingPosition` is still numeric (73 / 48 / 40).
- Playwright (`attr-tiles`, `recruits-pool`, `fcc-roster-tab`, `standalone-roster`), chromium, real browser cache: **74 passed, 2 failed**. Tile tier expectations were updated to the new rule (9 is elite, 5–6 are mid, 4 is low). The two failures are `fcc-roster-tab.spec.js` “column order is Player RT POS YR HT WT Attributes” and “every header carries a sort key except the grouped attribute cell”. The header includes `DEV FOCUS` (`franchise-command-center.html:188–189`), which this branch did not add. The only FCC HTML change is the helper script tag.

`node --check` on every edited JS file passed.

## Screenshots

1280×720. The seed server has canonical rosters and no franchise session, so these are fixture renders of the shipped JS and CSS, not a logged-in FCC. Same raw bag on all four: anchor SC 85 (stale SC 40), anchor SH 90, ID 45, OD 55, PS 77, BH 65, RB 9, ST 160, AG 80, ND 100, IQ 99, FT 105.

- `reports/attr-display-fcc-roster-2026-09-24.png` — real `GOB_AttrTiles`. First row shows 8 (green) not 4, so the anchor won. 9 is blue. 16 is blue. 5 and 6 are yellow. 4 and 0 are red.
- `reports/attr-display-player-detail-2026-09-24.png` — real `getAttrColor`. SC bar green at 8, SH bar blue at 9, ID red at 4, OD yellow at 5.
- `reports/attr-display-set-lineup-2026-09-24.png` — real pill fill. Same agreement. RB 9 fills nothing because the digit is 0.
- `reports/attr-display-training-hover-2026-09-24.png` — real grid, hover open. SC is 8, not the stale 40. RT is B+ (rating 73). Values sit next to their codes.

## Not done

Not merged into `develop`. Not pushed. Team Builder, RT bands, raw data, and backend attribute math were not changed. The styleguide was not edited.
