# Signing Day orders panel layout + colour-law leftovers

## Root cause

Already broken on develop (before and after `ux/recruiting-hub-tokens`). Not a lost selector in the token swap.

The Your Orders aside used `class="rail"` — the same class as the office nav. Once recruiting is `html.gob` / `html.gob-shell`:

1. `html.gob-shell.gob-focus .rail { display: none !important }` hides the orders panel in focus mode (pool goes full width; `#sign-rail` stays in the DOM but is not visible).
2. `html.gob-shell.gob-1280 .rail { padding: 0 }` and `.gob .rail, .gob .rail * { margin: 0; padding: 0 }` zero every inner pad, so title, 50/50, the points bar, empty state, notes and Submit sit on the card edges.
3. `.gob .rail button { font: inherit; color: inherit; background: none; border: 0 }` beats `.rail-submit`, so Submit Orders reads as plain text, not a committed/primary action.

A second, older markup bug: `railHtml()` never closed `.rail-head`, so the list, pre-flight and foot were nested inside the head. That is why `0/15 roster spots` sat on the same row as “Nothing committed”. The deliverable frame closes the head after the budget bar.

PTS overlapping Promise: `.stepper` is `overflow: hidden` and the `pts` label lived inside it, in a points column that was only `minmax(108px, 132px)`.

## Fix

- Aside is `class="srail"` (`id="sign-rail"` unchanged). Hub CSS targets `.srail`. Shell `.rail` rules no longer apply.
- Close `</div>` on `.rail-head` after the capacity row (same structure as the Signing Board frame).
- `#sign-rail .rail-submit`: orange (`/* colour-law: saved */`), full width inside foot padding, `height: max(46px, var(--dsz-40))`.
- `pts` sits beside the stepper in `.stepper-wrap`; points / Promise columns widened; gap 12px.
- “5x odds” (`.stand-mult`) is `--text-60`. `#1` / `#n` stay navy (`--you-ink`) as “yours”.

## Blue list (hub CSS)

| Location | Was | Choice |
|---|---|---|
| `.stand-cell.s-you1 .stand-mult` / `.s-list .stand-mult` | `--you` / `--list` (navy, reads as blue) | `--text-60` — odds text is not RT A / 9+ / elite |
| `--lblue: var(--blue)` in `recruiting-spine.css` `:root` | unused alias | left unused; nothing paints with it |
| `.verdict .mk`, `.my-region-label`, `.chip.is-my-region.is-active` | `--you` navy | kept — navy is “yours” |
| `.prow-rt .v` / RT tiles | shared RT ramp | kept — blue is legal on A / 9+ / elite |

No other `--blue` / `--lblue` / `#4A90D9` / `#6BA4E0` paints in `recruiting-signing.css`, `recruiting-dock.css`, or `recruiting-results-hub.css`.

## Files touched

- `FrontEnd/static/recruiting-hub.js` (aside class, close head, stepper wrap)
- `FrontEnd/static/recruiting-signing.css`
- `tests/e2e/signing-orders-panel.spec.js`

## Screenshots

All under `reports/signing-orders-panel/`.

| State | Before | After | Frame |
|---|---|---|---|
| Signing 1280 | `before-signing-1280.png` (develop / token-migration shot) | `after-signing-1280.png` | `frame-signing.png` |
| Signing 1920 | same collision as 1280 (no separate develop 1920) | `after-signing-1920.png` | — |
| Orders 0 committed | see before-signing-1280 | `after-orders-0-1280.png`, `after-orders-0-1920.png` | `frame-signing.png` |
| Orders 2 committed + 1 promise | — | `after-orders-2-1280.png`, `after-orders-2-1920.png` | `frame-signing.png` |

E2E guards (`signing-orders-panel.spec.js`) use computed styles: head padding > 0, Submit height ≥ `.advance`, no bounding-box overlap of `.stepper-pts` and `.promise-toggle` at 1280 and 1920, `.stand-mult` not brand/tier blue.

## Unsure

- `--lblue` is still defined and unused. Left it; removing it is a drive-by.
- 1920-before was not in the previous batch; the class collision is viewport-independent.
- Unit suite **1 XPASS** (known xfail started passing). This branch does not change Python/engine; do not edit `known_failures.py`.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | 4178 passed, 16 skipped, 109 xfailed, **1 xpassed**, 0 failed |
| Playwright `tests/e2e --workers=1` (CI unset, PORT=8033) | 765 passed, 4 skipped, 0 failed (11.7m) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 |
| `scripts/ci/check_migration_gates.py` | pass; Gate A 0; Gate B 136 / 44 |
