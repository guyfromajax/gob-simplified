# UX polish batches E + F — Recruiting, News, Settings (items 2, 18, 19, 20) — 2026-09-29

Branch `ux/polish-recruit-news-settings` from `origin/develop` (already had `ux/polish-league`).

No backend or sim change. Recruits already carry `image_id`; the client maps it to `imageId` and `API_CONFIG.getRecruitImageUrl` serves `recruits/white/<image_id>.png` with the shared silhouette fallback. No image source was invented.

## 0. Leftover: Team Stats ghost header

**Cause.** Foundation `.pg-head` used a vertical gradient that faded from `--bg-page-solid` into `--bg-page` (`rgba(14,16,24,.96)`). The last ~15% of the page head was translucent, so table rows sliding under the League tab row read as faint ghost header text above the pinned `thead`. Team Stats also sat in a `.gob-tcard` with `overflow: clip`, which could make that card the sticky containing block.

**Fix.**

- `html.gob-shell .pg-head` fills with solid `--bg-page-solid`.
- `#team-stats-view .gob-ts` is `overflow: visible` so the header pins to `.main` under `--gob-stick-top`.
- The Team Stats `thead` uses `--bg-page-solid` plus an upward `box-shadow` of the same colour so nothing shows through the hairline under the tabs.

After a 1400px scroll the pinned header sits flush on the solid page head. No second header copy.

## 1. Recruiting (items 2, 18)

### Headshots

Pool (`.pc-av`), invite board (`.bav`), and visits (`.vwk-av`) all go through `portraitSpan`, which now also applies the shared `.av` square atom (`border-radius: var(--radius-6)`). Images use `getRecruitImageUrl`; a miss falls back to initials on the silhouette box. Recruits do have `image_id` in `recruit_sets.assign_image_ids`.

### Pool / Leans / Visits tabs — week rules

| Weeks | Tabs |
| --- | --- |
| 1–19 | Pool, Leans, Visits stay. Search stays. Default landing is still Leans when anyone leans to you. |
| **20–26 (invite)** | **Pool, Leans, and Visits are removed.** The invite stack (calendar, board, then the pool) is the page. Search stays on the row. In-pool Leans / Watchlist / Unranked filters stay. |
| 27–34 | The three tabs return. Visits is the history calendar. |
| 35–36 | The whole row is already hidden (sign board / results). |
| Focus (`action=run`, unsaved invite board, week 35 orders) | The head — including the row — stays hidden. |

Jamie saw the tabs in week 21. They are gone for the whole invite window (20–26). If she wanted them gone in more weeks than that, say so; this batch only hides 20–26 and flags the rest as kept.

Invite weeks always force the pool stack (`showHub` maps any hub to `pool`). There is no visits-only calendar in those weeks.

### Callout

A neutral `.hub-more` control (“Recruit pool below”) sits between the board and `#hub-pool`. It is not green, orange, or navy. Click scrolls `.main` so the pool sits just under the sticky page head.

## 2. News (item 19)

- The feed is one newest-first list (week descending, then `yours` first in that week).
- Top story is a full-width hero card. The rest is a grid: **2 columns at 1280**, **3 at 1920** (`.gob-1920`, ≥1680×1000). Cards stretch to equal height in a row. No horizontal overflow.
- The whole card is the link. Separate “View” and “Box Score” `a.lnk` links are gone.
- Game-result items (`type === 'game_result'` or a box-score target) append ` (Box Score)` and open the box score. Other stories open the article the old View link used (`story_id` or the dispatch `target`).
- Your cards keep the navy inset (`--navy`).

Story bodies still render their own Box Score line when you open an article. That is inside the story, not the feed.

## 3. Settings (item 20)

- **Career record** in the Settings drawer is `12 – 5` (wins and losses) on one nowrap flex row. Never stacked.
- **Account details** (`account.html`) title-cases team names: first letter of each word upper, the rest lower. **IDA stays "IDA".** No other exceptions were added.
- **Coaching Archetypes** on the account board and on `/coaching-archetypes.html` use `grid-auto-flow: column` with row count `ceil(n / 3)`, so rank 1 is top of column 1, then down, then the next column.
- Settings panel spacing uses one rhythm: section stack `--space-24` / `--space-20`, inner stacks and the coach grid `--space-16`.

### All-caps team names in `base_league.json`

128 school names. **Fully all-caps (every letter):**

- IDA

**Names that contain an all-caps token of 2+ letters** (title-case would mangle these if Jamie wants them kept):

- GP Prep School (`GP`)
- HA Rushmore (`HA`)
- IDA (`IDA`)
- Seattle AAA (`AAA`)

Also stored in mixed/internal caps (not all-caps, listed so they are not silent): Archbishop McClellan, Couer d'Alene, DeCatur Dei, DeLand, MiddleTEX, Pike's Prep, Queen's Guard, River's Edge, St Peters, Wash U Prep, D1 Institute, Mt Simmons, and hyphenated names (Bentley-Truman, Juneau-Nome, …). I did not add exceptions for any of these.

## Tests

New: `tests/e2e/polish-recruit-news-settings.spec.js` at 1280×720 and 1920×1080.

- Team Stats: after scroll, page head and pinned header are opaque and flush (`gap ≤ 1`).
- Recruiting week 21: no Pool / Leans / Visits tabs; square headshots (or the fallback); callout scrolls the pool.
- News: hero ends with `(Box Score)` and links to the box score; no `a.lnk` / View / Box Score links; 2 columns at 1280, 3 at 1920.
- Settings: record on one line; IDA intact and Bentley Truman title-cased; archetype grid is `column` flow.

Updated: `news-awards.spec.js`, `recruiting-tabs.spec.js` (invite weeks have no labeled tabs; search stays; week 7 landing is Leans when anyone leans), `test_player_development_grid.py` (feed flatten + yours-first sort).

`POLISH_SHOTS=1` writes `reports/polish-recruit-news-settings/`.

## Gate (UX_System §8)

- pytest (`--ignore=tests/e2e`): **4049 passed, 16 skipped, 109 xfailed, 1 xpassed, 0 failed.**
- Full Playwright (workers=1, port 8038, `CI` unset, `ps` showed no other Playwright test): **637 passed, 3 skipped, 0 failed** (640 tests, 9.5 min). Regenerated tracked report images from that run were restored and not staged.

## Self-check (every shot opened)

Colour law: green is the top-bar Advance (“Play Next Game”). Orange is not used as a save on these screens (Settings has no save toast; account page orange is the existing Alpha chip / geek-points figure / ambience switch, not a new reward gold). Navy is the News “yours” inset and the Recruiting rail item. Choice controls (scope, filters, sliders) stay neutral. Pre-existing green lean `#1` pills, Submit Invites, and the orange “this week” visit tile were not restyled.

Nothing clipped on the listed frames.

### team-stats-scrolled

- **1280:** League › Team Stats, National on, table scrolled to Club 25–40. Solid dark page head under the tab row. One faint column-label strip (the pinned `thead`) sits on that solid fill. No ghost “Standings / Rankings / …” text in the gap. Green Advance only.
- **1920:** Same, rail open with League highlighted (neutral active, not a reward colour). Pinned header flush under the tabs. Rows 15–40. No bleed.

### recruiting-week21

- **1280:** Week 21 Invite Season. No Pool / Leans / Visits tabs. Search is on the right. Visit calendar (Ada Lean in WK 20 with a square AL monogram; WK 21 outlined) and Invite Board with a square headshot on #1. Pool is below the fold.
- **1920:** Same stack, more board rows visible (Ada Lean, Cal Brooks, Eli Hart) with square monograms. Search stays. No hub tabs.

### recruiting-callout

- **1280:** After click, “Recruit pool below ↓” sits under the page head. Pool filters and six rows with square initial badges. Neutral callout, not a button colour.
- **1920:** Empty board slots still at the top of the frame, then the same callout, then the pool. Square fallbacks. Scrolled as intended.

### news

- **1280:** Hero “Lancaster defeated Four Corners 70-64 (Box Score)” full width, navy edge (yours). Two-column grid under it: Upset Report | Training report, then Leans shift | Practice Squad. No View / Box Score links. Cards in a row match height.
- **1920:** Same hero. Three-column first grid row (Upset, Training, Leans), Practice Squad starts the next row. News rail item highlighted. No overflow.

### settings

- **1280:** Drawer over News. Career record `12 – 5` on one line next to Titles `3`. Audio sliders neutral. Account username/email. Log Out ghost. Green Advance on the page behind.
- **1920:** Same, more drawer width. Record still one line, not stacked.

### settings-archetypes

- **1280:** Account page scrolled to Coaching Archetypes. Column-first: #1 Authoritarian / #2 Systems-coach in column 1, #3 Player-maximizer / #4 Culture-builder in column 2, #5 Tactician / #6 Motivator in column 3.
- **1920:** Geek points list shows **IDA**, Bentley Truman, Lancaster (title case, IDA intact). Same column-first archetype board under Settings.

STATUS: COMPLETE
