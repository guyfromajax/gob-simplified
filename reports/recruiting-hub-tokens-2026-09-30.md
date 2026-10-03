# Recruiting hub onto the design system (visual only)

Batch 1 of the legacy page migration. Recruiting stays `/recruiting.html`. No engine, API, or FCC CSS edits.

## Root cause

The live hub already loaded `gob-tokens.css` and used `html.gob`, but `recruiting-spine.css` redefined a `:root` palette as raw hex and the three hub sheets painted type, colour, and radii as literals. Several of those paints (and the deliverable frames) spent green / orange / gold / blue on chrome the colour law does not allow.

## What changed

- Remapped hub aliases (`--panel`, `--you`, `--list`, `--display`, …) onto gob tokens. `--list` is navy: on-your-list is “yours”, not reward gold.
- Replaced raw hex/rgba, `font-size` / `font-weight` / `letter-spacing` / `font-family`, and radii with `var(--fs-*)`, `var(--fw-*)`, `var(--tracking-*)`, `var(--font-body|--font-display)`, and `var(--radius-*)`.
- Square headshots: pool `.pc-av`, board `.bav` (26/40), visits `.vwk-av`, reveal `.sd-tg-av` / `.sd-shot-img`, results `.av` use `--radius-6` or `--radius-10` per UX_System §2. Dots and pills stay `--radius-round`.
- Toast success/fail is a class (`.hub-toast.is-ok` / `.is-err`), not an inline `style.borderLeftColor`.
- Reclassified the four hub CSS files as new-design in `scripts/check_ui_tokens.py`.

`recruiting-hub.js` markup/classes only (toast classes). Invite-board ranking, API calls, and `readHubParam` / `URLSearchParams` were left alone.

## Per-file hit counts (before → after)

From `scripts/check_ui_tokens.py` on `origin/develop` vs this branch. After: files are **new-design** and `--strict` is 0.

| File | Colours | Type | Colour-law |
|---|---|---|---|
| `recruiting-spine.css` | 145 → 0 | 401 → 0 | 16 → 0 |
| `recruiting-dock.css` | 55 → 0 | 94 → 0 | 17 → 0 |
| `recruiting-signing.css` | 148 → 0 | 318 → 0 | 44 → 0 |
| `recruiting-results-hub.css` | 0 → 0 | 0 → 0 | 0 → 0 |
| `recruiting.html` (inline) | 2 → 0 | 4 → 0 | 0 → 0 |

`recruiting-results-hub.css` was already tokenized; only invalid `--lh-1-4` / `--lh-1-2` were pointed at real tokens (`--lh-body`, `--lh-1p25`).

Repo-wide colour-law total 1052 → 975 (the 77 removed hits are the three live hub sheets). New-design law: **0 / 0 / 0**.

## Colour-law conflicts with a frame (law wins → neutral or navy)

Deliverable `Recruiting Hub Deliverables/recruiting-spine.css` still paints `--you` as **green** and `--list` as **gold**. The T2 pool frame and the Spine / Dock / Signing / Results HTML use orange on eyebrows, titles, week chrome, and choice controls, and blue on region letters. Live hub choices:

| Frame paint | Law | Live choice |
|---|---|---|
| `--you` / “yours” chips, ladder, region-mine as green | Navy is yours | `--navy` / `--you-soft` |
| `--list` gold (“on your list”) | Not reward gold; yours | Same navy as `--you` |
| Orange eyebrows, `.sec-num`, `.hub-hname b`, `.spine-h b`, links | Chrome, not a save | `--text-60` / `--text-100` |
| Orange filter / `pool-add` hover, stepper +/−, `tw-seg.on`, dragover, dock nudge | Choice / hint | White alpha |
| Orange budget fill | Not saved | `--white-45` |
| Gold even-odds, orange slim-odds | Not RT / not a save | `--text-60` / `--text-38` + white fills |
| Blue region letter, story week numeral, open-lean slot, `pfw.info` | Blue is RT A / 9+ only | `--text-87` / `--text-60` |
| Orange reveal Next / Go / Continue (`sd-btn.is-next`, `.is-go`, `.sd-done-cta`) | Not Advance, not a save | White outline |
| Orange `pfw.warn` | Warning is not saved | `--text-60` |
| Green board-gain wash / up-arrow / lock-odds | Positive data | Kept green + `/* colour-law: positive-data */` |
| Orange Submit Invites / Submit Orders / save / funded row / committed rail / toast | Saved / committed | Kept orange + `/* colour-law: saved */` or `committed` |
| T2 pool RT letters green/blue/yellow/red | Canonical RT ramp | Unchanged (shared `rt-buckets` / attr tiles) |

W/L plates were already white/outline. No `--reward-gold` on this page.

## Left in `franchise-command-center.css`

Nothing for this hub. No `.pool`, `.spine`, `.idock`, `.spool`, `.pstrip`, `.bbtn-save`, or `.hub-*` rules. FCC recruiting chrome (rail badge, office card) stays there; not edited.

Out of scope and still legacy: `recruiting-lean-ladder.css` (hex leftovers, not linked from `recruiting.html`).

## Desktop / loopback

Hub still opens at `/recruiting.html` with `FranchiseContext` + the same data routes. No new `URLSearchParams(location.search)` reads. Toast class swap does not touch submit/save payloads.

## Screenshots

All under `reports/recruiting-hub-tokens/`. 1280 unless noted. After shots sit next to the matching deliverable frame (frames served from `_documentation_master/projects` so their CSS loads).

| State | Before (develop) | After | Deliverable frame |
|---|---|---|---|
| Pool 1280 | `before-pool-1280.png` | `after-pool-1280.png` | `frame-t2-pool.png` (T2) + `frame-spine.png` |
| Pool 1920 | `before-pool-1920.png` | `after-pool-1920.png` | — |
| Leans | `before-leans-1280.png` | `after-leans-1280.png` | `frame-spine.png` (lean object) |
| Visits preview | `before-visits-1280.png` | `after-visits-1280.png` | `frame-spine.png` (calendar) |
| Invite dock (wk 21) | `before-invite-dock-1280.png` | `after-invite-dock-1280.png` | `frame-invite-dock.png` |
| Signing Board | `before-signing-1280.png` | `after-signing-1280.png` | `frame-signing.png` |
| Results week | `before-results-1280.png` | `after-results-1280.png` | `frame-results.png` |

E2E guards (`tests/e2e/recruiting-hub-tokens.spec.js`) read **computed** `backgroundColor` / `borderRadius` (headshots 4–8px, navy you-token, orange save, no green on chips / week tiles / Submit). Team tokens stay `LAN` / `FAI` from stored `Lancaster` / `Fairview`.

## Files touched

- `FrontEnd/static/recruiting-spine.css`
- `FrontEnd/static/recruiting-dock.css`
- `FrontEnd/static/recruiting-signing.css`
- `FrontEnd/static/recruiting-results-hub.css`
- `FrontEnd/static/recruiting.html`
- `FrontEnd/static/recruiting-hub.js` (toast classes only)
- `scripts/check_ui_tokens.py` (`NEW_DESIGN_CSS` + docstring)
- `tests/e2e/recruiting-hub-tokens.spec.js` (computed-style guards + shots)
- Isolated recruiting harnesses now prepend `css/gob-tokens.css` and add `html.gob` so `var(--fs-*)` resolve: `invite-board-layout.spec.js`, `invite-board.spec.js`, `recruits-pool.spec.js`, `invite-visit-calendar.spec.js`, `invite-seed-modal.spec.js`, `signing-day.spec.js`, `signing-day-hub.spec.js`, `recruiting-draft.spec.js`, `signing-reveal.spec.js`. Pool assertions that hardcoded pre-token hex (`#4A90D9`, `#f4f5f8`) now read `--tier-blue` / `--text`.

## Unsure

- Fractional type (9.5 / 11.5 / 13.5px) snapped to the nearest `--fs-*`. Layout is the same; a few labels are 0.5px larger.
- Signing-board `prow` rows still have no headshot (they did not on develop). Square rule applied where a face already exists.
- Unit suite reported **1 XPASS** (a known xfail started passing). This branch does not change Python/engine; treat as pre-existing suite hygiene, not a list edit.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | 4178 passed, 16 skipped, 109 xfailed, **1 xpassed**, 0 failed |
| Playwright `tests/e2e --workers=1` (CI unset, PORT=8029) | 757 passed, 4 skipped, 0 failed (11.9m) |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0; new-design law 0 |
| `scripts/ci/check_migration_gates.py` | pass; Gate A 0; Gate B 136 lines / 44 files (no new reads) |
