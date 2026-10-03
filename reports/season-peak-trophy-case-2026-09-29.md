# Season peak + Trophy Case — 2026-09-29

Chapter 7 PR 5. Branch `app/season-peak-trophy-case`. The old ChampionshipMoments green CTA / team-color confetti is no longer the Office presentation: a championship in `moments_for_this_visit` opens one `.pk` takeover for every championship in that visit, then `season_review` opens `.rv`. The Trophy Case is a standalone page, not a franchise-shell route.

## Page vs route

Home Base is already a standalone page (`/mode-select.html`) outside the franchise shell. The Trophy Case matches that: **`/trophy-case.html`**, Home Base top bar, `← Home Base` to `/mode-select.html`. It is not an in-app FCC tab. `HB_TROPHY_CASE_HREF` in `mode-select.js` is `/trophy-case.html`, so the online career-strip “Trophy Case” link and the offline “View all →” both appear.

`authBarInit.js` skips `trophy-case.html` the same way it skips `mode-select.html`, so the site auth bar does not double the Home Base chrome.

## What replaced the old championship presentation

`ChampionshipMoments.processPendingMoments` (and `showMoment` when `SeasonPeak` is loaded) calls `SeasonPeak.showTitle` once with the full list. After Continue, each moment id is still POSTed to `/franchise/championship-moments/dismiss`. Court EOG still uses the old templates if `seasonPeak.js` is not on the page.

- CTA is `.btn-ghost.lg` (no green).
- Confetti is 60 pieces, classes `g` / `w` / `d` only (gold + white). None under `prefers-reduced-motion`.
- `playSfx(item.sting)` / `STING_SEASON_PEAK` at t≈600ms. Closing early does not cancel the sting. The review does not play it again.

## Data sources

### Title (`.pk`)

| Shown | Source |
|---|---|
| Eyebrow | Moment `season` + type (National / Region / Conference Tournament / Regular Season) |
| Headline | Moment `type` |
| Banner | `getTeamAssetPath(winner_team_name, 'banner_primary')` |
| Team | `winner_team_name` |
| Score | `score.winner`/`loser` or `home`/`away`, only if present |
| Medallions | One gold N/R/C per distinct title type in the visit list |
| Box score | `boxScoreUrlBuilder` or `game_id` |
| Queue | Server visit index / total (`1 of 2` when a review follows) |
| Sting | Queue item `sting` |

### Review (`.rv`) — live visit

`season_review` payload = `{eligible, season, **season_review_snapshot}` (`national_rank`, `season_gp`, `best_players`, `class_signed`; `region_seed` if the snapshot ever has it).

Titles on the live review come from the same-visit championship moments (existing data). Awards are the user-team All-Americans on `best_players` (`all_american`). Dismiss PATCHes `/franchise/season-review-seen`.

### Review — Trophy Case (read-only)

`season_record.detail` (wins, losses, `conf_finish`, snapshot fields) plus same-season title trophies for medallions. No queue dots. No PATCH.

### Trophy Case page

`GET /franchise/coach-career` only (loopback on desktop). Head numerals: `record` W–L, `titles_total`, `seasons_completed`, `programs`. Titles / milestones from `trophies[]` kinds. Season review rows from `season_record` trophies plus in-progress `top_seasons` (no Review). Zero community / `/api/auth/me` / leaderboard requests on the desktop profile.

## Omissions (no field → not shown)

- Program title count (“first national title”) — no field.
- Region seed — omitted even when a snapshot still carries `region_seed` (absent on region brackets).
- Live review **record** — snapshot has `season_gp`, not wins/losses. Stored Trophy Case reviews show W–L from `season_record.detail`.
- Live review **conference place** — `conf_finish` is on the stored detail, not the live snapshot.
- Live review **titles[]** — not on the snapshot; same-visit championships supply medallions instead.
- Awards list — not a separate payload; derived from `best_players[].all_american`.
- 4th Best Player stat — only `spg` (or `bpg` if present) after PPG/RPG/APG.
- Box score — omitted when the moment has no `game_id` / builder URL.
- Table finish in reward gold (frame `.gold-t`) — colour law keeps gold off the standing Trophy Case table; gold stays on title medallions and the “Trophy Case” words.

## Motion

Title: eyebrow fade, scale-in headline, gold rule, gold/white confetti, staggered team / score / medallions, footer. Review: section stagger, medallion pop. Reduced motion: final state, no confetti, no scale/translate. Sound still follows audio settings.

## Screenshots

`reports/season-peak-trophy-case/`

- `peak-title-1280.png`, `peak-title-1920.png`
- `peak-review-1280.png`, `peak-review-1920.png`
- `trophy-case-populated-1280.png`, `trophy-case-populated-1920.png`
- `trophy-case-empty-1280.png`
- `trophy-case-desktop-1280.png`
- `review-from-trophy-case-1280.png`
- `compare-title-1280.png`, `compare-title-1920.png`
- `compare-review-1280.png`, `compare-review-1920.png`
- `compare-trophy-populated-1280.png`, `compare-trophy-populated-1920.png`
- `compare-trophy-empty-1280.png`

(Frame captures `frame-*.png` sit next to the compares.)

### Remaining differences vs frames (and why)

- **Sample copy / art.** Frames use Lawrence Eagles + placeholder portraits. Product shots use the e2e Lancaster / Johnnies banner and square `.av` initials (task: square headshots; no player image on the fixture).
- **Office chrome under the peak.** The frame composites the Office behind `.pk`. Product is a full-viewport takeover, which is the spec.
- **Live review record + region seed + five-recruit class.** The frame invents `31–5`, “1 seed · Region B”, and a five-name class. The live payload does not have those fields; they are omitted. The stored Trophy Case review *does* show `31–5` and conference place from `season_record.detail`.
- **Queue on title-only shots.** Frame title is “1 of 2”. Title-only fixture has no review, so no `.mq`.
- **Trophy Case network chrome.** Frame trophy page is always the offline top bar. The populated e2e shot is online (Log Out). `trophy-case-desktop-1280.png` is the offline bar.
- **Finish gold on the reviews table.** Frame colours a title finish gold. Colour law: gold on title medallions only on this page.
- **Empty titles shelf.** Both show three open medallions + the same helper line. Frame capture of the empty titles row is faint; product matches the markup.
- **Frame `.gob-1280` / `.gob-1920` fixed artboard** vs product filling the viewport.

## Tests + gate

- `tests/e2e/season-peak-trophy-case.spec.js` — title gold / confetti / no green / reduced-motion / one sting / consume-all dismiss; 1 of 2 / 2 of 2; review-alone PATCH; Trophy Case populated / empty / desktop (no community); Review →; Home Base href.
- Home Base flag tests flipped from “link hidden” to “routes to `/trophy-case.html`”.

**§8 (this run):**

- pytest `--ignore=tests/e2e -q`: **4108 passed**, 16 skipped, 109 xfailed, 1 xpassed, **0 failed**.
- Playwright: full `tests/e2e`, workers=1, `CI` unset, `PORT=8013`, `BASE_URL=http://localhost:8013`: **695 passed**, 3 skipped, **0 failed**.

## Files

- `FrontEnd/static/css/season-peak.css`, `js/shared/seasonPeak.js`
- `FrontEnd/static/trophy-case.html`, `css/trophy-case.css`, `js/shared/trophyCase.js`
- `momentQueue.js`, `championshipMoments.js`, `franchise-command-center.html` / `.js`
- `mode-select.js` (`HB_TROPHY_CASE_HREF`), `authBarInit.js` (skip list)
- `tests/e2e/season-peak-trophy-case.spec.js`, Home Base online/offline flag tests

Did not touch office weekly (`officeHome.js`, `office-home.css`, `office_digest.py`) or Training Report.

STATUS: COMPLETE
