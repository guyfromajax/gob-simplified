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

## Post-review revision (merge + layout fixes + navy hold)

**Merge.** `git merge origin/develop`. One conflict, in `scripts/check_ui_tokens.py`: kept **every** `NEW_DESIGN_CSS` entry from both sides — develop's `playbooks.css` / `css/playbook-tiles.css` and the training files, plus my `set-lineup.css`; merged the docstring's new-surface list and kept develop's FCC-freeze ceiling text. `UX_System.md` auto-merged (develop's Playbooks + FCC-freeze text and my Set Lineup section + §16 correction all present). Gates re-run green after the merge.

**2a. Bench-row stat overlap (fixed — second pass).** The Game view crammed PTS/REB/AST/DEF% into one column with inline labels. A first pass (`max-content` grid) stopped the four stats overlapping each other but the cluster still overflowed its narrow column into its **neighbours** at 1280 (ENG "100%" ↔ "PTS", "DEF%" ↔ the RT grade). Fixed properly by moving the four stats into **four real table columns** with the labels in the **header row** (PTS/REB/AST/DEF%, value-only body cells — the same shape as the Attributes/Stats views), so each stat has its own column and a real gap from ENG% and RT. `buildProductionCell` now returns four value cells; the header gained four `prod-head` th's; `colSpan` 10 → 13. That widened the table past the 843px panel at 1280 (MO clipped), so I reclaimed the width — narrowed the Game ENG bar (104 → 46px, per the review's hint), the four stat columns, PLAYER (172 → 142), and MIN (48 → 44) — until the table fits the panel exactly at 1280 **and** 1920 (no clip). No type shrunk below the scale; player names do not truncate. Verified by measuring the scroll container (`scrollWidth === clientWidth`) and every row's cell-text boxes.

**2b. Empty right-hand panel (seed data, not broken).** The panel above Autoset is `#lineup-shot-weights`, driven by the playbook's `position_shot_weights` (per the v3 Fits frame: Playbook + Play Call Center bars per position). Verified against the backend: the test seed carries **no** `position_shot_weights` — not in single mode (the `/api/playbooks` fetch has no franchise context, the render is skipped) and not in the seeded franchise (`/api/playbooks?...&franchise_id=…` returns it absent, `hasSW:false`). So the panel is empty purely from seed data; in production it fills from the franchise's shot-weight settings. Not a regression (the develop before shot is identically empty). Could not re-shoot it filled — no seed populates it. Added a small `.psw-unavailable` style so the "Shot weight data unavailable" message reads cleanly where the fetch completes without data.

**2c. Play Game green matched to the shell (fixed).** `.lineup-btn-advance` had a translucent green border (`color-mix(--green 50%, transparent)`) and no glow, which read darker than the shell Advance. Repainted with the shell's Advance tokens — `background: var(--green)`, `color: var(--bg)`, `border-color: var(--white-28)`, `box-shadow: var(--shadow-advance)` — the same paint `.gob .advance` uses in `gob-components.css`. Now identical to `#play-now` in the franchise shell.

**3. Navy HOLD.** Per the review, the on-court / selected-row **navy** (and the drag-target navy tint) is left **as-is pending Jamie's decision** on whether selected items count as "yours" (navy) or neutral across Set Lineup and Playbooks. Not changed in this revision. If the call is "neutral", it is a one-line swap of `--navy` → a neutral white on the on-court/selected rules.

**3 (paint). Play Game dim in after-default is the disabled state.** `#play-now` ships with the `disabled` class while the lineup is incomplete (`.lineup-btn.disabled { opacity: 0.48 }`), which is why it reads dim in the empty-lineup default shot. Its paint is already the shell Advance (bg `--green`, border `--white-28`) at both states — only opacity differs. The new `after-filled-1280.png` (Autoset → five on court → Play Game **enabled**, opacity 1) shows the full-strength green matching `#play-now` in the shell.

**Guards.** The e2e guard asserts (computed): Play Game bg = `--green` and border = `--white-28` (shell Advance paint, both densities); Autoset and the view toggle are neither green nor orange; the headshot radius is square; and — the new coverage — in **every bench row, across the Game, Attributes and Stats views, at 1280 and 1920**, no two adjacent cells' **text** overlap (measured with a `Range` per cell, so it catches content spilling out of a cell, not just cell-box edges).

## 1–4. Set Lineup migration

**Decision applied (Jamie): colour law wins over the frame; use neutral and list each conflict.** No save state exists on this page (the lineup persists through the flow, confirmed by a neutral `showToast`), so **orange has no home here** and every orange usage became neutral / navy / red.

### Per-file colour hits (before → after)

| File | law (green/orange/gold) | raw colours | type literals | Notes |
|---|---|---|---|---|
| `set-lineup.css` | **29 → 0** | 179 → 138 | 115 → 113 | now in `NEW_DESIGN_CSS`; `--strict` passes |
| `set-lineup.html` | 0 → 0 | — | — | already new-design (`gobShell.js` PAGES); added `class="gob"` + `gob-tokens.css` link so `var(--token)` resolves |
| `set-lineup.js` | 0 → 0 | — | — | `buildProductionCell` now emits four value cells (labels moved to the header); `colSpan` 10 → 13. No colour literals. |

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

`tests/e2e/set-lineup-tokens.spec.js` (computed styles / text bounding boxes): Advance (`#play-now`) background **is** `--green` and its border **is** `--white-28` (the shell Advance paint), at 1280 and 1920; Autoset and the view toggle are **neither** green nor orange; the injected `.roster-headshot` radius is under a quarter of its side (square, not a circle); and, in **every bench row across the Game, Attributes and Stats views at both densities**, no two adjacent cells' text overlap. Passes. Also updated `game-start-sequence.spec.js:96` from `/lineup-btn-green/` → `/lineup-btn-advance/` (the rename).

## Gates (real numbers)

- **pytest** `--ignore=tests/e2e -q`: **4231 passed, 14 skipped, 109 xfailed, 1 xpassed, 0 failed** (240s, post-merge).
- **check_ui_tokens.py** `--strict --no-write`: **exit 0**.
- **check_migration_gates.py**: **passed** (Gate A 0/0; Gate B 136 lines/44 files — unchanged; no franchise-identity `URLSearchParams` added).
- **Full Playwright** (workers=1, port 8000, CI unset, no other run): **777 passed, 5 skipped, 0 failed** (11.7m, second review pass).

## Screenshots (`reports/set-lineup-tokens/`)

Full page at 1280 (scrolled to top), before (develop) vs after; default also at 1920. Each after pairs with the `set-lineup-handoff 2/` v3 Fits frame.

| State | Before (develop) | After |
|---|---|---|
| Default lineup @1280 | `before-default-1280.png` (orange Pre-Game + orange Autoset) | `after-default-1280.png` (neutral Pre-Game + neutral Autoset; green Play Game) |
| Fit / ratings (Attributes) @1280 | `before-ratings-1280.png` | `after-ratings-1280.png` |
| Stats view @1280 | `before-stats-1280.png` | `after-stats-1280.png` |
| Filled (Autoset → Play Game enabled) @1280 | `before-filled-1280.png` | `after-filled-1280.png` (full-strength green Advance) |
| Default @1920 | `before-default-1920.png` | `after-default-1920.png` |

Re-shot post-review: `before-*` are develop's set-lineup; `after-*` include the layout fixes above. The before-default shows the run-together stat text and orange Autoset; the after shows readable `0 PTS  0 REB  0 AST  0 DEF%` and a brighter Advance. "Changed-but-unsaved" and "saved" are not distinct visual states — this page has no save action; the lineup is live-editable and persists through the flow. (No Timeout Read shot: the seed has no live mid-game, so the resume URL only reproduces the pre-game default; that state shares set-lineup's own CSS.)

STATUS: COMPLETE
