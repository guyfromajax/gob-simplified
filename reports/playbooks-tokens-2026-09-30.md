# Playbooks tokens — 2026-09-30

Visual-only migration of Playbooks onto the design system. Branch `ux/playbooks-tokens` from `origin/develop` at `10c5a81b5`. Colour law wins over frames; conflicts listed below. Work only in `~/gob-stats`.

## Loaders (before start)

`css/playbook-tiles.css` is linked only from `FrontEnd/static/playbooks.html` and `FrontEnd/static/js/shared/views/playbooksView.js` (`CSS` array). Grep of `FrontEnd/static` (`*.html`, `*.js`) found no other loaders. `court.html` and Phaser do not load it. Coverage-gap-check §3 is current; the older “shared with court” note is stale.

## Per-file hits (before → after)

Develop baseline from `audit_tree` on `origin/develop` (legacy surface). After is this branch with both files in `NEW_DESIGN_CSS`.

| File | Colours | Type | Colour-law |
|---|---:|---:|---:|
| `playbooks.css` | 110 → **0** | 79 → **0** | 12 → **0** |
| `css/playbook-tiles.css` | 99 → **0** | 75 → **30** | 33 → **0** |
| `playbooks.js` | 1 → **0** (legacy; not reclassified) | 0 → 0 | 0 → 0 |
| `play-details.html` | 33 → 33 (out of scope) | 11 → 11 | 4 → 4 (legacy) |

Tiles leftover type is leftover D2 `.et` / `.chip-*` anatomy (odd `px` sizes with no token step: 8px, 8.5px, 9px, 10.5px, 11.5px, 12.5px, 21px, 23px). Those selectors are unused by current `playbooks.js` (live tiles are `.play` / `.wb` / `.et-slider`). `--strict` only fails colour-law on new-design; both files are **0 law**.

`playbook-cmd.css` was not touched (3 colour / 1 law). CMD ramp stays there.

## Frame vs colour-law

Frames served from `_documentation_master/projects`: `design_handoff_prep/frames/prep-playbooks-1280.html` and `design_handoff_prep_v2/frames/prep-playbooks-1280.html`. Jamie: colour law wins; use neutral; list each conflict.

| Frame paint | Law | Choice |
|---|---|---|
| Enabled **Save Playbooks** orange | Orange = committed / saved | **Keep** `var(--orange)` + `/* colour-law: committed */` |
| Offense/Defense tab selected orange | Choice control | **Neutral** (`--white-11` / `--text-87`) |
| Section heading / hairline orange (Motion, etc.) | Not Advance, not committed | **Neutral** (`--text-100` / `--line-strong`) |
| Weight slider fill orange | Choice control | **Neutral** (`--white-55` / `--white-28`) |
| Open / selected play row navy | Navy = yours only | **Neutral** (`--white-11`) |
| Play-detail panel navy wash | Same | **Neutral** (`--white-4`) |
| Checkbox / drop-target / lock orange | Choice | **Neutral** |
| LIVE pill / section-total green | Not Advance, not +data | **Neutral** |
| `#ffc878` warn / noslack | Near-gold | **Neutral** (`--text-60`) |
| Tile CMD `.is-mid` green / `.is-low` gold | Law wins over `playbook-cmd` ramp on this sheet | **Neutral** on tiles. In-app CMD digits stay `--text-100`. `playbook-cmd.css` still defines `--cmd-*` (out of scope) |
| Shot-weight pills blue / green / gold / red | Agent docs: preserve the programmed shot-weight scale. Blue-on-non-RT is a channel conflict with “blue belongs to RT” | **Keep** the existing thresholds via `common.js` `getPswColor` (out of scope). Local fallback in `playbooks.js` now reads `--blue/--green/--yellow/--red` |
| Reward gold on titles | None on these frames | — |
| Frame v2 “LIVE” green pill | Same as LIVE above | **Neutral** |

In-app `#playbooks-view` was already mostly tokenized from prep v2; this pass finished standalone `playbooks.css` / `playbook-tiles.css` and the tutorial path (`playbooks.html?mode=tutorial` + `class="gob"` + `gob-tokens.css`).

## Play-details (Q3 C) — recommend **A**

`/play-details.html` is a ~1100-line standalone with its own inline gold title (`#FFD700`), blue Back, and old gradient. `playbooks.js` `buildPlayDetailsUrl` still links out to it.

- **A (recommend):** later, open the play inside `#playbooks-view` (the in-app `.pdet` inspector already exists). Do not implement A on this branch.
- **B:** restyle the standalone now. Not small and not self-contained (inline CSS + animation host). Skipped.
- **C:** leave forever. Worse than A; the page still 404s/errors without animation payload.

Before shot only: `reports/playbooks-tokens/before-play-details-1280.png` (error empty state). After capture is the same page unchanged (`after-play-details-1280.png`) so the table can sit next to the before.

## Deletions (ch8 evidence bar)

Grep of `FrontEnd/static` `*.{js,html}` (and the Playbooks JS templates) for each class: **zero** remaining uses except the CSS file itself, then the rule was removed.

Removed from `playbooks.css`:

- Legacy table: `.playbook-table*`, `.playbooks-table-wrap`, `.col-*`, `.control-check*`, `.spin-btns`, `.number-input-wrap`, `.play-name-*`, `.row-dead`, `.eff-score`, `.sort-btn`
- Dropped save-confirm modal (already specified gone in Playbooks redesign spec): `.modal*`, `.save-confirm-*`
- Old PCC slot cards: `.pc-header`, `.pc-sections`, `.pc-column`, `.pc-slot*`
- Unused chrome: `.section-toolbar*`, `.section-heading-block`, `.pc-section-label`, `.playbooks-page-actions`, `.playbooks-action-btn*`
- Unused `CHK_SVG` in `playbooks.js` (defined, never referenced)

Kept: standalone `#toast` on `playbooks.html` (tutorial save still uses it), live `.csr` / `.pc-list` / `.pc-remove-btn` / `.playbooks-save-btn`.

`resource-pages.css` was not restyled. No new global rules.

## Shared CSS leftovers

**`franchise-command-center.css` (do not touch — list only):**

- `#franchise-container #playbooks-franchise` / `.needs-playbook-save` / `.active` (old FCC playbooks card, ~583–605)
- `#franchise-container .fcc-playbooks-*` card/section/item layout (~2630–2782, plus 1280/1920 tweaks ~2880–2905)
- Comment “CMD band colors → css/playbook-cmd.css”
- `#franchise-container .training-report-styled .playbook-summary-section` (~3488)

None of those are the Playbooks module view. Audit agent is cleaning dead FCC rules separately.

**`playbook-cmd.css`:** still the CMD hue ramp (`--cmd-good` blue / `--cmd-mid` green / `--cmd-low` gold). Out of scope. In-app Playbooks no longer paints tiles with those classes.

**`resource-pages.css`:** unchanged. Tutorial still loads it; Playbooks-specific overrides stay under `body.playbooks-page` / `#playbooks-view`.

**`common.js` `getPswColor` / `renderShotWeights`:** still the hex ramp. Tutorial and in-app call this when present. Out of scope.

## UX_System

One sentence added on the existing Save-feedback / Playbooks paragraph: choice chrome (tabs, sliders, open-row) is neutral; only enabled Save uses `--orange`. No other UX_System sections edited.

## Geometry fixture

`tests/e2e/fixtures/playbooks-before-metrics.json` stayed green (≤2px). Not updated. Save disabled paint still matches the fixture (`samePaint`). Enabled Save is asserted orange in the unsaved test.

## Screenshots

All under `reports/playbooks-tokens/`. Full-page `page.screenshot` after `scrollTo(0,0)` (and `#playbooks-view` / `.main` scroll 0). Header/meta not scrolled off.

| State | Before | After | Frame (beside) |
|---|---|---|---|
| Main tables 1280 | `before-main-1280.png` | `after-main-1280.png` | `frame-v2-playbooks-1280.png` (also `frame-v1-playbooks-1280.png`) |
| Main 1920 | `before-main-1920.png` | `after-main-1920.png` | — |
| Playcall Center 1280 | `before-pcc-1280.png` (same viewport as main; PCC is the right column) | `after-pcc-1280.png` | same frames |
| Unsaved + enabled Save 1280 | `before-unsaved-1280.png` | `after-unsaved-1280.png` | — |
| Saved toast | — | `after-saved-toast-1280.png` | — |
| Tutorial standalone 1280 | `before-tutorial-1280.png` | `after-tutorial-1280.png` | — |
| play-details 1280 | `before-play-details-1280.png` | `after-play-details-1280.png` (unchanged; rec A) | — |

## Gates

- `.venv` via `../gob-simplified/.venv/bin/python -m pytest --ignore=tests/e2e -q`: **4199 passed**, 14 skipped, 109 xfailed, **1 xpassed** (`test_leaders_view_scope_filters_to_user_conference` — known; list not edited). **0 failed.**
- Targeted Playwright (`tests/e2e/prep-modules-playbooks.spec.js`, workers=1, `PORT=8212`, `FRAMES_BASE=http://127.0.0.1:8197`): **10 passed** (geometry fixture, computed-style guards, frames).
- Full Playwright (`env -u CI PORT=8214 BASE_URL=http://localhost:8214 … --workers=1`): **776 passed**, 5 skipped, **0 failed** (10.8m).
- `scripts/check_ui_tokens.py --strict --no-write`: **exit 0**, new-design law **0**.
- `scripts/ci/check_migration_gates.py`: **pass**. Gate A 0/0, Gate B 136/44. `--write-allowlist` not used.

## Files touched

- `FrontEnd/static/playbooks.css`
- `FrontEnd/static/css/playbook-tiles.css`
- `FrontEnd/static/playbooks.html` (`class="gob"`, `gob-tokens.css`)
- `FrontEnd/static/playbooks.js` (toast accents neutralized; unused `CHK_SVG` removed; local shot-weight fallback uses tokens)
- `scripts/check_ui_tokens.py` (`NEW_DESIGN_CSS` + docstring)
- `tests/e2e/prep-modules-playbooks.spec.js` (token shots, scroll-0 full-page capture, computed-style guards)
- `_documentation_master/11_Design_Systems/UX_System.md` (Playbooks Save/choice sentence only)
- `reports/playbooks-tokens-2026-09-30.md` + `reports/playbooks-tokens/*.png`

Not touched: `franchise-command-center.css`, recruiting, `office-home.*`, `officeHome.js`, training files, `court.html`, Phaser, the sim, `uiSfx`.
