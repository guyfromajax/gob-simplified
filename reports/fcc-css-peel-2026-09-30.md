# FCC.css peel + freeze — 2026-09-30

Branch `chore/fcc-css-peel` from `origin/develop`. Q8 (A): delete dead `franchise-command-center.css` rules, then freeze. No visual restyle except Team Stats `.training-report-styled` colour-law **if live**.

## Counts

| | Before | After |
|---|---|---|
| Lines | 4326 | 3234 |
| Style rules | 594 | 448 |
| Colour-law hits (this file) | 65 (32 green / 33 orange) | 30 |
| Repo colour-law (legacy + new) | — | 940 (new-design 0) |

Dropped 146 style rules (594 → 448), trimmed leftover selectors off 19 mixed comma-lists. Unused `@keyframes fccAttrPulse` removed after its only callers went. A first peel pass corrupted two comments that contained commas (`<tr>, so` / `cell, so`) and briefly swallowed `.fcc-season-advance`; those leftover sticky-column rules were restored.

## Team Stats `.training-report-styled`

**Not live.** Coverage-map Team Stats is `team-stats-view` (gob-tables). Coverage-map Team Attributes is `team-attributes-view` (gob-measures + `buildTeamMeasuresRadarMarkup`).

`commandCenterTabs.canonicalTab` remaps `team-stats-tab` → `team-attributes-view`. Leftover `#team-stats-tab` still contains `training-report-styled fcc-team-measures-layout` in `franchise-command-center.html`, but the shell never sets it `.active`.

The green-valued `--color-accent-orange: #34ec27` and gold/orange chemistry/pill rules lived only under `#franchise-container .training-report-styled`. Those blocks were dual-confirmed DEAD and removed. No colour-law restyle, no Team Stats / Team Attributes pixel change (0.000% both profiles).

Live radar (`.tm-radar-*`) stays. `gob-views.css` only sizes `.mradar .tm-radar-wrap` / `.tm-radar-svg`.

## Method

**(a) Static.** Parsed every style rule. Class/id tokens grepped as identifiers across `FrontEnd/static` html/js (templates, `classList`, `className`). Remapped leftover panel IDs (`roster-tab`, `team-stats-tab`, `schedule-tab`, `game-plan-tab`, `playbooks-tab`, `recruits-tab`) and leftover-only families (`.training-report-styled`, `.fcc-team-measures-*`, `.tm-side-card-*`, `.tm-linear-*`, `.tm-chemistry-*`, `.fcc-chemistry-bar-*`) classified DEAD.

**(b) Runtime.** Playwright, web + desktop profiles (`GOB_BUILD_PROFILE=desktop` on `127.0.0.1`), every coverage-map FCC tab + Settings + Feedback (web) + Recruiting entry. `document.querySelectorAll` per selector; matches tagged `live-view` / `chrome` / `leftover-remapped` / other panel.

A selector was removed only when static DEAD **and** runtime did not match a live view or chrome. Leftover hidden DOM matching `querySelector` is not a live view.

## DEAD (removed), grouped by feature

### Remapped leftover tab-content panels

Shell remaps these; rail never shows them.

- **`#roster-tab`** (22 selectors) — old roster table / attr-toolbar chrome. Live Roster is `roster-view` + gob-tables.
- **`#recruits-tab`** (29) — old in-FCC recruits table. Rail Recruiting goes to `/recruiting.html`. `gobShell` maps `recruits-tab` → `home-tab`.
- **`#schedule-tab`** (1) — `.fcc-schedule-tab-inner`. Live schedule is `team-schedule-view`.
- **`#team-stats-tab` / Team Measures leftover** — see next group.

`#game-plan-tab` / `#playbooks-tab` specific IDs were remapped; leftover card classes that JS still emits into those hidden hosts were kept when the selector was not panel-scoped (unsure).

### Leftover Team Measures / `.training-report-styled`

- `.training-report-styled` and descendants (pills, chemistry bars, card tones, `--color-accent-orange: #34ec27`) — 20 selectors.
- `.fcc-team-measures-*` layout/side cards.
- `.tm-side-card-*`, `.tm-linear-*`, `.tm-chemistry-*` — only `buildTeamMeasuresLinearCardMarkup` / leftover `#team-stats-tab`.
- `@keyframes fccAttrPulse` — no remaining callers.

### Orphaned old Office / News / Scouting / Resources chrome

Static identifier miss in html/js **and** runtime miss on every live tab:

- Old Office card chrome never called after `GOBOffice.render` took over: `.fcc-home-grid`, `.fcc-home-card`, `.fcc-home-leaders-toggle`, `.fcc-home-standings*`, `.fcc-home-locker-*`, `.fcc-home-attitude-*`, `.fcc-home-recruit-*`, `.fcc-home-chemistry-*`, `.fcc-practice-squad-title`, `.tb-eligibility`.
- Old News leftover: `.fcc-news-tab-*`, `.fcc-news-mine*`.
- Old Scouting leftover (live scouting-view uses prep-v2 CSS): `.fcc-scouting-status/layout/hero/measures/team-page-link`, etc.
- Old resources / routed pages: `.resources-btn`, `.resources-grid`, `.team-stats-page`, `.fcc-placeholder-*`.
- Old standings/schedule toggles: `.standings-fcc-note`, `.schedule-conference-*`.
- Unused radar extras not emitted: `.tm-radar-value`, `.tm-radar-point`.
- Unused tournament tone/region variants not in `fcc-tournament-style-a.js`: `.fcc-tournament-tone-*`, `.fcc-tb-region--3/4`, `.fcc-tb-region-col--solo`.

## Kept, unsure

- **`#fcc-team-stats-summary-tab` table rules** — leftover HTML still in the document; URL `?tab=fcc-team-stats-summary-tab` is still known. Mixed roster/recruits/summary comma-lists were trimmed to this panel only.
- **`#standings-tab` / `#awards-tab`** — not remapped; leftover URL can still activate. Shared `.fcc-data-card` / `.fcc-standings-full-link` kept.
- **`.tm-radar-*`** — live on Team Attributes.
- **`.fcc-tb-*` / tournament Surface A** — live JS (`fcc-tournament-style-a.js`, `franchise-tournament-brackets-render.js`). Runtime on the locked empty tournament tab did not paint them; static JS hit keeps them.
- **`.fcc-home-list-*`, `.fcc-home-matchup-*`, `.fcc-home-team-stats-*`** — still present as unused strings in `franchise-command-center.js`. `renderHomeTab` only calls `GOBOffice.render`. Kept because static grep finds the class names.
- **`.fcc-game-plan-*` / `.fcc-playbooks-*`** — JS still writes into leftover hosts if those tabs were shown. Hosts are remapped; kept when the selector was not `#game-plan-tab` / `#playbooks-tab` scoped.
- **`.fcc-invite*`** — still in this sheet (Recruiting hub has its own CSS; do not restyle here).
- **Chrome** — `:root --fcc-*`, `body`, `#franchise-container`, `.hero-btn`, `#play-now`, `.tab-content` generics. `html.gob-shell` already overrides the old card chrome.
- **`.fcc-training-head` / training leftover** — left in place where static/runtime disagreed.
- **`#roster-tab` / `#recruits-tab` sticky identity column** — leftover HTML is still in the page, and `tests/e2e/fcc-roster-tab.spec.js` mounts it in isolation. First peel pass corrupted the comment (a comma inside `/* … <tr>, so … */` was treated as a selector split) and swallowed `.fcc-season-advance`. Restored those rules. Not a live-view restyle.

## Freeze

Header on `franchise-command-center.css`:

```
/* Frozen: no new rules. Put new styles in the view's own CSS. */
```

`scripts/check_ui_tokens.py` now fails if the file grows past:

- `FCC_CSS_MAX_LINES = 3234`
- `FCC_CSS_MAX_RULES = 448`

CLAUDE.md CI gates mention the freeze. Ceilings may shrink; they must not grow.

## Pixel-diff (1280, desktop + online)

Same stubbed franchise, both profiles. Percent of pixels that changed.

| View | web % | desktop % |
|---|---|---|
| Office | 0.000 | 0.000 |
| Team Roster | 0.000 | 0.000 |
| Team Player Stats | 0.000 | 0.000 |
| Team Attributes | 0.000 | 0.000 |
| Team Schedule | 0.000 | 0.000 |
| Practice Squad | 0.000 | 0.000 |
| Prep Game Plan | 0.000 | 0.000 |
| Prep Playbooks | 0.000 | 0.000 |
| Prep Scouting | 0.000 | 0.000 |
| Prep Training | 0.000 | 0.000 |
| League Standings | 0.000 | 0.000 |
| League Rankings | 0.000 | 0.000 |
| League Leaders | 0.000 | 0.000 |
| League Team Stats | 0.000 | 0.000 |
| League Schedule | 0.000 | 0.000 |
| League Tournament | 0.000 | 0.000 |
| News | 0.000 | 0.000 |
| News Awards | 0.000 | 0.000 |
| Settings | 0.296 | 0.049 |
| Feedback | 0.000 | n/a (hidden) |
| Recruiting entry | 0.001 | 0.000 |

Nothing outside Team Stats is above 0.5%. Settings 0.296% / 0.049% is panel chrome (focus / open-frame), not FCC leftover rules. Shots: `reports/fcc-css-peel/shots/`.

## Files touched

- `FrontEnd/static/franchise-command-center.css` — dead rules removed; freeze header.
- `scripts/check_ui_tokens.py` — freeze ceilings + check.
- `CLAUDE.md` — CI gate note.
- `reports/fcc-css-peel-2026-09-30.md` + `reports/fcc-css-peel/shots/`.

Did not touch recruiting files, `office-home.*`, `officeHome.js`, Prep/training CSS, the sim, or `court.html`.

## Gates

- `.venv/bin/python -m pytest --ignore=tests/e2e -q` — **4178 passed**, 16 skipped, 109 xfailed, **1 xpassed**, 0 failed
- Full Playwright (`workers=1`, CI unset) — first run 772 passed / 2 failed (comment-split). After restore: **774 passed**, 4 skipped, 0 failed (11.2m).
- `.venv/bin/python scripts/check_ui_tokens.py --strict --no-write` — exit 0 (new-design law 0; FCC.css law 30; freeze 3234/448)
- `.venv/bin/python scripts/ci/check_migration_gates.py` — pass (Gate A 0, Gate B 136 lines / 44 files). Never `--write-allowlist`.

## Unsure / notes

- Leftover HTML panels are still in `franchise-command-center.html`. This brief peels CSS only.
- Isolated e2e shots use the stub webfont fallback (garbled labels). Before/after pairs match.
- Tournament bracket CSS is kept even though the locked tab is empty in this stub.
