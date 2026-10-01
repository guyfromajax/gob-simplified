# Jamie's rulings batch (2026-10-01)

**Status: ready for review.** Branch `ux/jamie-rulings-batch`, pushed. Not merged. Implements rulings #1, #6, #7, #8, #10 from `reports/jamie-decisions-2026-10-01.md`. Not in scope and untouched: #2, #9 (kept) and #3, #4, #5, #11 (done by the court pass, now on develop).

Each ruling is recorded as **SETTLED** in `UX_System.md` (new "Settled rulings" table under Colour law) and in the canonical colour-law table in `Styleguide.md` (Navy row, Reward gold row, badges, Open question 1).

## What I need you to look at

| # | Item | Why |
|---|---|---|
| A | **#7: the dot is not visible anywhere today.** | Under the shell `.inbox-badge` is only ever attached to the hidden legacy tab button. It is neutral now, as ruled, but no user sees it. The orange thing on the rail is the **count badge** (`.office-rail-count`, `--badge`), a different element I did not touch. If that is what you meant, say so. |
| B | **#1: I included your team in a bracket.** | You listed Set Lineup, Playbooks and the leaderboard / lean-ladder slot. The bracket's "your team" rows were the last items held for this ruling (9 green law hits in the frozen sheet). The live Tournament view already overrode them to navy; only the big-news bracket modal still showed green. I made the base rules navy. Value edits only, no new rules. |
| C | **#1: how strong the navy is.** | Set Lineup keeps its 14% navy tint and gains a 3px `--navy-hi` left edge. Playbooks uses the design frame's recipe (35% navy, `--navy-hi` hairlines). The open-row highlight and the play-detail panel stay neutral: opening a row is not picking a play. |
| D | **#10: local static middleware changed.** | In development / test / desktop a missing `.html` is answered with the 404 page before any router runs, so the router redirect alone never fired. I added one retired-path entry to that middleware in `BackEnd/api/api.py`. No auth code touched. |
| E | **#10: I added `/homepage-v3` redirects although nothing in the repo links the page.** | Outside links cannot be grepped. Three lines in each Netlify config; drop them if unwanted. |

## #1 Navy for what you picked

| Surface | Before | After | File |
|---|---|---|---|
| Set Lineup on-court rows | 14% navy tint, no edge | same tint + 3px `--navy-hi` left edge | `set-lineup.css` (+1 rule) |
| Set Lineup selected row edge | `--navy` | `--navy-hi` | `set-lineup.css` |
| Playbooks: play in your Playcall Center (`.play.on`) | neutral `--white-11` | navy 35%, `--navy-hi` hairlines | `playbooks.css` |
| Playbooks: its slot number (`.slot`) | neutral ring | `--navy-hi` ring | `playbooks.css` |
| Playbooks: call-sheet rows (`.csr`) | neutral `--white-11` | navy 35%, `--navy-hi` ring | `playbooks.css` |
| Lean ladder, FCC sheet (`.is-you`, `.is-you-list`, `.recruit-stand-*`) | literal `#27408E` / `rgba(39,64,142,…)` | `--navy` tokens, `--navy-hi` edge | `recruiting-lean-ladder.css` |
| Lean ladder, Recruiting hub (`.lb-slot.is-you`, `.is-you-list`) | `--navy`, navy edge | `--navy`, `--navy-hi` edge (`--you-edge`) | `recruiting-spine.css` |
| Your leaderboard row (`.alb-row.is-current`) | navy + `--navy-hi` ring | unchanged, already the recipe | none |
| Your team in a bracket (`.fcc-tb-*--user`) | green `#2bd66a` | navy, as the live Tournament view | `franchise-command-center.css` (values only) |
| Bracket connector in the big-news modal | green | navy (`userConnectorNavy`) | `js/shared/bigNewsModals.js` (+1 line) |

Stay neutral, checked by the spec: the Game / Attributes / Stats toggle, the Offense / Defense tab, the weight lock, plays not in the Playcall Center, bench rows, other teams' ladder slots and bracket rows.

Frozen sheet: `franchise-command-center.css` is still 1779 lines / 230 rules. Its law hits went 13 → **4** (only the Advance fallback `.hero-btn` is left).

## #6 Senior-tribute title marks

`.st-titles s` and `.st-cti s` in `css/senior-tribute.css`: `--ink` (white, from peel 2) → `var(--reward-gold)`, annotated `/* colour-law: reward */`. Senior-tribute title marks are now the sixth reward surface in both docs.

## #7 Recruiting presence dot

`.inbox-badge` in `franchise-command-center.css`: `var(--badge)` + orange glow → `var(--text-100)` + `--white-45` glow. `fcc-recruiting-layout.spec.js` now asserts `rgb(255, 255, 255)`. See item A above.

## #8 Big-news modal button

`.bn-cta` in `css/big-news-modals.css`: gold gradient → neutral plate (`--white-10`, `--white-28` border, `--text-100`). The trophy emblem, eyebrow and title glow keep the gold. One `:hover` rule added. The milestone modal has no gold button (its buttons were already neutral).

## #10 Twin pages

`sync:homepage` first:

```
$ grep sync package.json
6:    "sync:homepage": "cp FrontEnd/static/homepage.html FrontEnd/static/homepage-v3-source.html",
```

So `homepage.html` is the build **input** and `homepage-v3-source.html` is its output. `homepage-v3.html` is neither, so it is deleted. `homepage-v3-source.html` and the script are untouched.

References to the page (not the `images/homepage-v3/` folder, which the canonical homepage uses 17 times and which stays):

```
$ git grep -n -E 'homepage-v3(\.html|["'\''/ ]|$)' origin/develop -- . ':!reports' ':!FrontEnd/static/homepage*.html'   # page references, not the images/homepage-v3/ folder
FrontEnd/static/js/shared/authGuard.js:153:    "/homepage-v3.html",
FrontEnd/static/js/shared/authGuard.js:154:    "/homepage-v3",
tests/e2e/homepage-v3-auth.spec.js:5: * Covers canonical /homepage.html and the homepage-v3.html candidate (a0ea3d36d kept it).
tests/e2e/homepage-v3-auth.spec.js:9:  return ['/static/homepage.html', '/static/homepage-v3.html'];
tests/e2e/homepage-v3-auth.spec.js:30:  test('homepage-v3.html stays the marketing candidate', async ({ page }) => {
tests/e2e/homepage-v3-auth.spec.js:31:    await page.goto('/static/homepage-v3.html');
```
```
$ git grep -c 'images/homepage-v3/' origin/develop -- FrontEnd/static/homepage.html FrontEnd/static/homepage-v3-source.html   # the image folder stays: the canonical page uses it
FrontEnd/static/homepage.html:17
```

References to Play Builder V1 and V2:

```
$ git grep -n -E 'play-builder(\.html|[^-a-zA-Z0-9]|$)' origin/develop -- . ':!reports' | grep -v play-builder-v2
BackEnd/api/play_routes.py:47:@router.get("/play-builder.html")
BackEnd/api/play_routes.py:50:    return FileResponse(STATIC_DIR / "play-builder.html")
FrontEnd/static/js/shared/adminGuard.js:8:    "/play-builder.html",
FrontEnd/static/js/shared/authBarInit.js:50:    'play-builder.html',
FrontEnd/static/js/shared/authBarInit.js:64:    '/play-builder',
_documentation_master/03_UX_Systems/Team_Images_System.md:103:| **court**           | Court/game page (Phaser background); play-details; play-builder(s); default in build
_documentation_master/08_Playbooks_Systems/Plays_Page_System.md:21:**Data source note:** both routes read from the **`gob-staging` database's `plays` collection** (`get_s
docs/Admin_Only_Docs/play_builder_v2_guide.md:341:- **V1 (Original):** `/FrontEnd/static/play-builder.html`
docs/Core_System_Docs/gob-simplified-architecture.md:325:- **play-builder.html** - Custom play designer
docs/To Do/Archive/0_alpha_launch_plan.md:27:| **12** | **Admin/Support Tools** | Admin role system, admin-only pages (play-builder, HCT/FCP builders), support email/feed
docs/To Do/Archive/0_alpha_launch_plan.md:525:- [ ] **play-builder** — Admin-only (non-admins redirected or blocked)
docs/To Do/Archive/0_alpha_launch_plan.md:567:9. **Admin-Only Pages:** play-builder, HCT skeleton builder, and FCP skeleton builder are restricted to admin users. Applied
scripts/export_catalog_sidecar.py:9:already run. Staging can hold unpublished play-builder work. FCP/HCT are
```
```
$ git grep -n 'play-builder-v2' origin/develop -- . ':!reports'
BackEnd/api/play_routes.py:41:@router.get("/play-builder-v2.html")
BackEnd/api/play_routes.py:44:    return FileResponse(STATIC_DIR / "play-builder-v2.html")
FrontEnd/static/js/shared/adminGuard.js:9:    "/play-builder-v2.html",
FrontEnd/static/js/shared/authBarInit.js:51:    'play-builder-v2.html',
FrontEnd/static/js/shared/authBarInit.js:65:    '/play-builder-v2',
_documentation_master/08_Playbooks_Systems/Offense_Plays_System.md:3:> Verified vs code: set-play aliases `SET_PLAY_POSITION_ALIASES = ("target_shooter", "pos1", "pos2", 
_documentation_master/08_Playbooks_Systems/Offense_Plays_System.md:77:- Frontend: `FrontEnd/static/play-builder-v2.html`
_documentation_master/projects/Z-Completed/_documentation_sweep.md:162:- [x] `06_GMO_Supporting_Systems/Play_Builder_System.md` → **DELETED (merged) 2026-06-13** — per us
docs/Admin_Only_Docs/play_builder_v2_guide.md:342:- **V2 (Enhanced):** `/FrontEnd/static/play-builder-v2.html`
docs/Archive/Playbooks_Rework/pc_rework_brief.md:1083:  - `FrontEnd/static/play-builder-v2.html`
```

| Done | Detail |
|---|---|
| `git rm FrontEnd/static/homepage-v3.html` | 668 lines |
| `git rm FrontEnd/static/play-builder.html` | 2286 lines. Self-contained page (inline CSS and JS), so nothing else became dead. |
| `/play-builder.html` → `/play-builder-v2.html`, 301, query kept | `BackEnd/api/play_routes.py` (hosted API), local static middleware in `BackEnd/api/api.py` (dev / test / desktop), `netlify.toml` and `FrontEnd/static/_redirects` (hosted site) |
| `/homepage-v3.html`, `/homepage-v3` → `/`, 301 | `netlify.toml`, `FrontEnd/static/_redirects` |
| `tests/e2e/homepage-v3-auth.spec.js` | Now covers `homepage.html` only; the "stays the marketing candidate" test removed. |
| `tests/test_play_builder_redirect.py` | New, 4 tests. |

Left as they are:

| Left | Why |
|---|---|
| `/homepage-v3*` in `authGuard.js` public paths; `/play-builder*` in `adminGuard.js` and `authBarInit.js` | Guard lists. An entry for a path that now redirects is harmless, and I did not want to edit auth or admin gating for a cleanup. |
| V1 mentions in older docs (`Plays_Page_System.md:21`, `docs/Admin_Only_Docs/play_builder_v2_guide.md:341`, `docs/Core_System_Docs/gob-simplified-architecture.md:325`, archive plans) | History. Say if you want them edited. |
| The Netlify redirects are not exercised by any test | Netlify config cannot run locally. The backend redirect and the middleware are tested. |

## Shots (`reports/jamie-rulings-batch/`, `page.screenshot` at scroll 0)

`before-*` from develop's copies of the changed files on the first merged tree, `after-*` from this branch. 22 files.

| Item | Stem | Sizes | Changed pixels |
|---|---|---|---|
| #1 Set Lineup | `set-lineup` | 1280, 1920 | 480 each: the 3px edge on five rows |
| #1 Playbooks | `playbooks` | 1280 | 30.5%: the picked rows and the call sheet |
| #1 Lean ladder, FCC sheet (forced, 3x) | `lean-ladder` | 1280 | 9,078: slot edges and ink |
| #1 Lean ladder, Recruiting hub (real) | `hub-leans` | 1280 | 400: your slot's edge |
| #1 Bracket + #8 button | `big-news-bracket` | 1280 | 58%: modal content (rows, connector, button) |
| #6 Senior tribute | `senior-tribute` | 1280 | 108: the three marks |
| #7 Presence dot (forced onto the rail) | `presence-dot` | 1280 | 436: the dot |
| #10 `/play-builder.html` | `play-builder-v1-path` | 1280 | whole frame: V1 before, V2 after |
| #10 `/static/homepage-v3.html` | `homepage-v3-path` | 1280 | whole frame: the copy before, the 404 page after |
| #10 `homepage.html` | `homepage` | 1280 | 0 |

Forced states, labelled in the spec: the lean ladder on the FCC (no recruit in the fixture week has one; drawn at 3x), the presence dot on the rail (item A), the bracket modal and the tribute (opened through their real entry points with fixture data).

## Computed-style guards

`tests/e2e/jamie-rulings-batch.spec.js`, 7 tests:

| Test | Asserts |
|---|---|
| #1 Set Lineup, 1280 + 1920 | 5 on-court rows; tint is navy; first-cell edge is `--navy-hi`; bench rows have neither; the view toggle is not navy |
| #1 Playbooks | picked play, call-sheet row and slot ring are navy / `--navy-hi`; an unpicked play, the Offense / Defense tab and the lock are not |
| #1 Lean ladder | your slot, list slot, dot and chips resolve from `--navy` / `--navy-hi`; another team's slot is not navy |
| #1 Bracket + #8 button | your team row, card and connector navy, no green; CTA has no gradient and no gold, white ink; eyebrow and emblem still gold |
| #6 Tribute | 3 title marks, exactly `--reward-gold` |
| #7 Dot | white, 8px, no orange or green, on both the real (hidden) element and the forced rail one |
| #10 Pages | `/play-builder.html` lands on `/play-builder-v2.html`; `homepage-v3.html` is 404 and gone from disk; `homepage.html` still 200 |

**Fails on the old code (verified):** with develop's files restored, 7 of 7 fail. On the branch: 21/21 at `--repeat-each=3`.

Existing assertions updated because the rulings reverse them:

| Spec | Was | Now |
|---|---|---|
| `fcc-recruiting-layout.spec.js` | dot contains `247, 148, 32` | dot is `rgb(255, 255, 255)` |
| `fcc-peel-2.spec.js` | dot orange via `--badge`; tribute marks `--ink`; ladder literal navy | dot neutral; marks gold; ladder navy from tokens |
| `prep-modules-playbooks.spec.js` | picked play is **not** navy | picked play **is** navy, unpicked is not |

## Gates (on `79aeb2bac`: this work + develop `76039eaf5` merged in)

| Gate | Result |
|---|---|
| `pytest --ignore=tests/e2e -q` | exit 0. **4302 passed, 14 skipped, 108 xfailed, 2 xpassed, 0 failed** (232s). +4 are the new redirect tests. |
| `scripts/check_ui_tokens.py --strict --no-write` | **exit 0** (no pipe). New-surface hits 0 / 0 / 0. Legacy 402. FCC freeze passes (1779 / 230). |
| `scripts/ci/check_migration_gates.py` | **exit 0**. Gate A 0 / 0; Gate B 134 lines / 43 files. |
| Full Playwright, one run under `/tmp/gob-full-playwright.lock`, `--workers=1`, `CI` unset, port 8017 | exit 0. **829 passed, 7 skipped, 0 failed** of 836 (14.2m). Lock taken 15:15:59, released 15:30:09. Run on `b10cd1e7f` (first merge). |
| Failure re-runs at `--repeat-each=5` | none needed |

The Playwright run was one tracked job that took and released the lock itself while I blocked on it (the foreground limit is 10 minutes; the suite takes about 14).

Merge: develop moved once while I worked (gallery fixes, which also edit `set-lineup.css`). Merged with no conflicts; both shot sets were re-captured on the merged tree. Develop then moved a second time during the Playwright run (court panels and desktop icons: `court.html`, `UX_System.md`, a spec, icon files; nothing I touch except the doc, which merged cleanly). I merged again and re-ran pytest, the token gate and the migration gates on the final tree, all green as listed. **The full Playwright suite was not run a second time**; its result above is from the first merge.

## Files

| File | Change |
|---|---|
| `FrontEnd/static/set-lineup.css`, `playbooks.css`, `recruiting-lean-ladder.css`, `recruiting-spine.css`, `franchise-command-center.css` | #1 (and #7 in the FCC sheet) |
| `FrontEnd/static/js/shared/bigNewsModals.js` | #1 connector, 1 line |
| `FrontEnd/static/css/senior-tribute.css` | #6 |
| `FrontEnd/static/css/big-news-modals.css` | #8 |
| `FrontEnd/static/homepage-v3.html`, `FrontEnd/static/play-builder.html` | deleted |
| `BackEnd/api/play_routes.py`, `BackEnd/api/api.py`, `netlify.toml`, `FrontEnd/static/_redirects` | #10 redirects |
| `_documentation_master/11_Design_Systems/UX_System.md`, `Styleguide.md` | SETTLED records |
| `tests/e2e/jamie-rulings-batch.spec.js`, `tests/test_play_builder_redirect.py` | new |
| `tests/e2e/fcc-peel-2.spec.js`, `fcc-recruiting-layout.spec.js`, `prep-modules-playbooks.spec.js`, `homepage-v3-auth.spec.js` | updated assertions |

## Noticed, not changed

- The big-news modal's confetti palette includes green (`#2bd66a`) in `bigNewsModals.js`. Decoration on a reward surface; not in the ruling.
- `css/gob-views.css` still carries the Tournament view's navy overrides for `.fcc-tb-*--user`. They now repeat the base rules and could be removed.
- `tests/e2e/zz-tb-debug.spec.js` is still on disk (untracked, comment-only); `rm` is denied to me.
