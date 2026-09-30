# Legacy migration batch 5 — Set Lineup onto the design system + doc fix

Branch `ux/set-lineup-tokens` off `origin/develop`. Visual-only (markup/classes/CSS);
no sim, no lineup payload/API, no `court.html`/Phaser/uiSfx.

## 0. Doc correction (UX_System §16 "team names as stored")

The pending "stragglers" note was **wrong**. Verified:
- `common.js:22` `formatTeamName(name)` → `name == null ? '' : String(name)` — returns the name **unchanged**.
- Its callers (`set-lineup.js:2343-2344`, `playbook-report.js`, `pgpcSammyReminderModal.js:30`, `franchise-command-center.js:518`) only display the result — no reformat.
- `titleCaseTeamName` (`common.js:26`) still exists but is used **only** at `common.js:1080` (`getTeamCoachAssetPath`) as a lookup key for a coach-asset abbreviation, never as a display string.
- No `toUpperCase` on a team name in the named files (the set-lineup `toUpperCase`/`toLowerCase` hits are the region letter, position keys, class-year abbrevs, and an image-slug — not display names).

Replaced the note with an accurate line stating `formatTeamName` is a no-op and `titleCaseTeamName` is asset-lookup only.

## 1–4. Set Lineup migration

**Decision applied (Jamie): colour law wins over the frame; use neutral and list each conflict.** No save state exists on this page (the lineup persists through the flow, confirmed by a neutral `showToast`), so **orange has no home here** and every orange usage became neutral / navy / red.

### Per-file colour hits (before → after)

| File | law (green/orange/gold) | raw colours | type literals | Notes |
|---|---|---|---|---|
| `set-lineup.css` | **29 → 0** | 179 → 138 | 115 → 113 | now in `NEW_DESIGN_CSS`; `--strict` passes |
| `set-lineup.html` | 0 → 0 | — | — | already new-design (`gobShell.js` PAGES); added `class="gob"` + `gob-tokens.css` link so `var(--token)` resolves |
| `set-lineup.js` | 0 → 0 | — | — | logic file (legacy); only button class names changed in HTML |

`--strict --no-write` exits **0** with `set-lineup.css` reclassified. I kept every existing `NEW_DESIGN_CSS` entry (another branch added the Prep training files) and appended `set-lineup.css`.

### Frame vs colour-law conflicts + choices

| Element | Was | Colour-law choice | Why |
|---|---|---|---|
| Play Game (`#play-now`) | green (`.lineup-btn-green`) | **green, kept** — class renamed `.lineup-btn-advance` | It is the one Advance; the `advance` selector is on the checker allow-list (no annotation needed) |
| Autoset Lineup | solid orange (`.lineup-btn-orange`) | **neutral** (`.lineup-btn-neutral`) | A non-advancing action, not a save. Token comment allows orange for "non-advancing actions"; the colour law (task) restricts orange to saves/committed → neutral, conflict listed |
| "Got It" (exhausted modal) | green (`.lineup-btn-green`) | **neutral** | Not Advance; only Advance is green |
| Pre-Game / quarter accent | orange | **neutral** (`--text-100`) | Not a save; a status label |
| On-court / selected rows + left edge | orange | **navy** (`--navy`) | Navy is the sanctioned "selected row" structure colour |
| Slot filled / drag-over / row drag-over | orange | filled **neutral**, drag-over **navy tint** | Filled = a choice; drag-over = active drop target (structural) |
| FT-shooter lock (slot border, overlay, row badge, row edge) | orange gradient | **neutral** | Informational lock status, not a save |
| Playbooks modal head | orange | **neutral** | Header accent, not a save |
| Energy ENG / next-game readiness ramp | raw green (high) + raw orange (low) | **green (positive-data, annotated) / yellow / amber `color-mix` / red** | A data ramp; matches the frame's green→amber→red; amber is a token mix so no raw orange literal |
| Player headshot border, image container | orange | **neutral** (`--line-strong`) | Square headshots (§2), neutral border |
| RT column | (unchanged) | **blue** via `rt-buckets.css` `.rt-*` | Blue is the sanctioned A-grade / 9+ / elite colour |

Green survives only on the Advance button and the annotated positive-data ramps; navy marks selection; everything else that was green/orange is neutral or red.

### Deletions (same evidence bar as ch8-cleanup-1)

| Removed | Evidence |
|---|---|
| `.momentum-bar-container` / `-left` / `-right` / `-center` (set-lineup.css) | Zero refs in `set-lineup.js` / `.html`; the live game's momentum bar is `court.html`'s own inline CSS. Removed the green hit at old line 262. |
| `.player-rating` rule | Zero refs anywhere in the repo (js/html). Removed the orange hit at old line 545. |
| `.context-stat-value.is-accent` selector | Never applied (zero refs); only `.context-inline-value-quarter` is live. |

### Structural: `.gob` + tokens

`set-lineup.html` now carries `<html class="gob">` and loads `css/gob-tokens.css` (the tokens are `.gob`-scoped, so `var(--token)` is inert without both — same pattern as `training.html`). The `.gob` block is purely custom-property definitions, so it adds tokens without restyling; the page does **not** load the shell, so its layout is unchanged.

### Timeout Read / Game Plan overlap

`set-lineup.html` does **not** load `game-plan.css`; the Timeout Read state reuses set-lineup's own markup and CSS (only the context-bar data differs — live quarter/score/time vs "Pre-Game"). **No shared style lives in `game-plan.*`**, so nothing there was touched. (The seed has no live mid-game, so the Timeout Read URL fell back to the pre-game shell in the screenshot; the colour treatment is identical to default.)

### Shared CSS still loaded (not in scope, left as-is)

`resource-pages.css`, `playbook-cmd.css`, `rt-buckets.css` remain linked. `rt-buckets.css` is the sanctioned RT ramp (kept). `resource-pages.css` is a shared legacy sheet used by other modules — not migrated here; noted for a later batch.

## e2e guard

`tests/e2e/set-lineup-tokens.spec.js` (computed styles): Advance (`#play-now`) background **is** green; Autoset and the view toggle are **neither** green nor orange; the injected `.roster-headshot` radius is under a quarter of its side (square, not a circle). Passes. Also updated `game-start-sequence.spec.js:96` from `/lineup-btn-green/` → `/lineup-btn-advance/` (the rename).

## Gates (real numbers)

- **pytest** `--ignore=tests/e2e -q`: **4199 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed** (233s).
- **check_ui_tokens.py** `--strict --no-write`: **exit 0**.
- **check_migration_gates.py**: **passed** (Gate A 0/0; Gate B 136 lines/44 files — unchanged; no franchise-identity `URLSearchParams` added).
- **Full Playwright** (workers=1, port 8000, CI unset, no other run): **775 passed, 4 skipped, 0 failed** (10.6m).

## Screenshots (`reports/set-lineup-tokens/`)

Full page at 1280 (scrolled to top), before (develop) vs after; default also at 1920. Each after pairs with the `set-lineup-handoff 2/` v3 Fits frame.

| State | Before (develop) | After |
|---|---|---|
| Default lineup @1280 | `before-default-1280.png` (orange Pre-Game + orange Autoset) | `after-default-1280.png` (neutral Pre-Game + neutral Autoset; green Play Game) |
| Fit / ratings (Attributes) @1280 | `before-ratings-1280.png` | `after-ratings-1280.png` |
| Stats view @1280 | `before-stats-1280.png` | `after-stats-1280.png` |
| Changed (post-Autoset) @1280 | `before-changed-1280.png` | `after-changed-1280.png` |
| Default @1920 | `before-default-1920.png` | `after-default-1920.png` |
| Timeout Read* @1280 | `before-timeout-1280.png` | `after-timeout-1280.png` |

\* No live mid-game in the seed, so the resume URL fell back to the pre-game shell; the shot still shows the after styling (neutral controls, green Advance). "Changed-but-unsaved" and "saved" are not distinct visual states — this page has no save action; the lineup is live-editable and persists through the flow.

STATUS: COMPLETE
