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
