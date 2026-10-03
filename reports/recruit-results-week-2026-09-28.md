# Recruiting week-36 Results (browse templates)

Branch `ux/recruit-results-week`. Week 36 **Signing Day Results** in `recruiting-hub.js` (`finalSigningsHtml` → `#hub-signings`). Same payload and `markSigningsSeen()` → `PATCH /franchise/week-36-results-seen` (unchanged).

## Layout

1. **Your class** — compact `gob-tcard` + `gob-tbl` (T1/T2): 28px portrait when `image_id` / recruit `imageId` exists (monogram fallback), name, Pos, Yr, RT pair (`Spine.rtClassForYear` + `Common.formatRtWithPotential`). Count in `<h2>Your class<em>n</em></h2>`. Sorted by RT desc (same as before).
2. **League** — `gob-rec-conf-grid`: 3 columns @1280, 5 @1600+, max-width 72rem. Conference order: user → sister → rest by `conferenceLabel`. Per card: quiet `.gob-rec-eye` (“Your conference” / “Sister conference”), team sub-heads with count, compact rows. User team rows: `tr.me` / `#1c2a52` navy (browse tables).
3. **Empty** — `No signings to report yet.` as `.gob-rec-empty`.

## Player links

Names link to **Franchise Command Center › player-view** when the signing entry includes **`player_id`** (`tab=player-view&player_id=…`). No `player_id` → plain text. (`recruit_id` alone is not used for player-view.)

## CSS / cleanup

- New browse styling: `recruiting-results-hub.css` (tokens via `gob-tokens.css` on `recruiting.html`).
- Removed week-36 `.ls*` block from `recruiting-signing.css` (unused elsewhere).
- Legacy `.signsum` / `.signtable` rules removed from `recruiting-results-hub.css` (were unused by hub JS).

## Fields not in payload (left out)

- Team logo / primary color on league rows (only `team_name` / map name today).
- Recruit detail deep-link by `recruit_id` only (player-view requires `player_id`).
- National rank, signing reason, points — not shown on week-36 list (same as prior league list).

## Tests

- `tests/e2e/recruit-results-week.spec.js` — order, navy rows, seen PATCH once, screenshots.
- Updated `tests/e2e/signing-reveal.spec.js` week-36 league list selectors.

Recruiting specs (recruit-results-week, signing-reveal, recruiting-tabs, fcc-invite-step, recruits-pool): **95 passed**.

Full suite: **520 passed, 3 skipped**, ~7.7m, port **8010**, `CI` unset, workers=1 (waited for other agent Playwright on 8157). Server stopped with the suite.

## Screenshots

`reports/recruit-results-week/results-w36-1280.png`, `results-w36-1920.png` — fixture with six conferences and a full user class.

STATUS: COMPLETE

## Fix pass

**Root cause:** Design tokens live under `.gob` in `gob-tokens.css`. The week-36 e2e fixture used `setContent` with inlined CSS but no `html.gob`, so `--surface-*`, `--line`, and table typography never applied (plain text, “Your class5” with no `h2 em` spacing). Production `recruiting.html` relied on `gobShell.js` to add `gob` after paint; the spec never loaded the shell.

**Fixes**
- `recruiting.html`: `class="gob"` on `<html>` so browse tokens apply as soon as the page loads (shell still adds `gob-shell`).
- `recruiting-hub.js`: league team tables get `thead` + colgroup (Name, Pos, Yr, RT) like Your class.
- `recruit-results-week.spec.js`: real `/recruiting.html` + `stubAuth`, CC + recruiting stubs, wait for `gob-pending` clear and rail; visual assertions (`.gob-tcard` border/background, Bebas RT header, visible RT cells, spaced count in `h2 em`).

**Self-check (screenshots):** Opened `results-w36-1280.png` and `results-w36-1920.png` — GOB top bar + rail, dark `gob-tcard` panels with borders, Your class table with portrait/Name/Pos/Yr/RT and count badge beside the title, conference grid with eyebrows, per-team headers, Pos/Yr/RT columns, navy `#1c2a52` only on user-team rows (`tr.me`).

**Tests:** Recruiting bundle (recruit-results-week, signing-reveal, recruiting-tabs, fcc-invite-step, recruits-pool) **95 passed**, port **8010**, workers=1, `CI` unset. Full suite deferred — another Playwright run active on port 8157 (`gob-stats`).

STATUS: COMPLETE

## Fix pass 2

**Root cause:** Week-36 tables sit in `.gob-xs`, which inherits the **1760px** `min-width` floor and horizontal scroll + `can-r` edge mask from `gob-tables.css` — same failure mode as `#news-view` story tables. Pos/Yr/RT were in the DOM but scrolled off the right of narrow conference cards.

**Fixes**
- `recruiting-results-hub.css`: `#hub-signings` content-sized table override (mirrors `#news-view .gob-news-body .gob-xs .gob-tbl`: `min-width: 0`, `width: 100%`, `table-layout: fixed`, no scroll/mask on `.gob-xs`), explicit col widths, capped name ellipsis, `min-width: 0` on cards.
- `recruiting-hub.js`: removed duplicate per-team column headers; conference eyebrow + title in `.gob-rec-conf-head` with card padding; **dropped** loose “Signing Day Results / Every signing…” block (phase strip already reads “Week 36 Results · Signings are final”).
- `recruit-results-week.spec.js`: RT bounding box inside card + `scrollWidth ≤ clientWidth`; no league `<thead>`; no `.gob-rec-lead`.

**Self-check (screenshots, column-by-column):**
- **1280 — Your class:** portrait initials L0–L4 · names Lancaster 0–4 · Pos SF · Yr JH/FR/SO/JR · RT letters A+/A+, A/A, etc. (readable, no right fade).
- **1280 — Conference E9 (user):** eyebrow “YOUR CONFERENCE” above title; South Lancaster rows show truncated names · PG/SF · JR/JH · RT grades; navy on user rows only.
- **1280 — Sister/other cards:** Pos/Yr/RT visible on each row (e.g. Sign 8 PG JR B+/A); no repeated “Name” headers per team.
- **1920:** same columns readable across Your class and all conference cards; five-column grid, no horizontal mask on rows.

**Tests:** Recruiting bundle **95 passed**; full suite **520 passed, 3 skipped** (~7.8m), port **8010**, workers=1, `CI` unset.

STATUS: COMPLETE
