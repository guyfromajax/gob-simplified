# Office tweaks 4

Branch `office/tweaks-4` off develop.

## Files

- `FrontEnd/static/css/gob-components.css` — `.wr.up .wr-tag` uses `var(--delta-up)`; `.wr.dn .wr-tag` uses `var(--delta-down)`. Flat rows still render no arrow.
- `FrontEnd/static/js/shared/officeHome.js` — attitude bar width is `min(count, ATTITUDE_BAR_MAX) / ATTITUDE_BAR_MAX` with `ATTITUDE_BAR_MAX = 5`. The number above each bar is still the real count. Count 0 is an empty bar.
- `tests/e2e/office-frontend.spec.js` — bar widths for counts 0, 2, 5, and 7 (2 is 40%, 5 and 7 are 100%). Up and down wire arrows match the attribute-chip colors.
- `reports/office-tweaks-4/office-1280x720.png`
- `reports/office-tweaks-4/office-1920x1080.png`

## Tests

`office-frontend.spec.js`, `shell-1.spec.js`, `shell-1b.spec.js`, and `shell-2.spec.js`: 35 passed, 1 skipped (live digest dump is absent).

## Commit

`5bb2c1f18`

STATUS: COMPLETE
