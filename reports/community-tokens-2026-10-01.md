# Community pages on gob tokens: 2026-10-01

Branch `ux/community-tokens` from `origin/develop` (`774c341b6`), in `~/gob-audit`. Upstream unset after `checkout -b`. Merged develop `d0f534fc3` (court-chrome-2) before push: clean, `NEW_DESIGN_CSS` keeps every entry, gates re-run on the merged tree.

## Scope

The grep hits are mostly incidental (`profile` / `community` in comments, auth, analytics, Home Base). The community surfaces with their own styling:

| Page | What | Before |
|---|---|---|
| `coaching-archetypes-leaderboard.html` | 18 archetype boards, top coaches per board | inline `<style>`, 25 colour literals, 3 law hits |
| `coaching-archetypes.html` | archetype catalogue, your lead archetype highlighted | inline `<style>`, 19 / 2 |
| `account.html` | your profile: geek points, titles, settings, archetype board | inline `<style>`, 36 / 6 |

Skipped: the Home Base leaderboard (`css/home-base.css`, already `NEW_DESIGN_CSS`), and the marketing homepage (`homepage*.html`, separate rebuild). There is no public-profile or shared-league list page in `FrontEnd/static`; `account.html` is the user's own profile.

**Visual only.** HTML changes: `class="gob"`, a `gob-tokens.css` link, the inline `<style>` replaced by `css/community.css`, and body classes `community-page` + `alb-page` / `ca-page` / `acct-page`. A stray duplicate `</style>` was dropped from `coaching-archetypes.html`. No script, API, auth, ranking or points code changed.

## Colour law applied

| Element | Before | After |
|---|---|---|
| Your leaderboard row (`.alb-row.is-current`) | orange tint | **navy** ("yours"; `.ldb-r.me` recipe) |
| Your lead archetype card (`.ca-card.is-lead`) | orange ring | **navy** ring (`.agc.is-me` recipe) |
| Archetype share % (leaderboard, account board) | orange | `--text-100` (data, neutral) |
| Geek points total | orange | `--text-100` (a count; not a reward surface) |
| Status pill (Alpha / plan) | orange pill | neutral pill |
| In-Game Display segment on-state | orange (choice control) | `--white-18` |
| Tooltip focus ring | orange | `--white-45` |
| Page background | navy radial `#243049` | neutral `--white-4` lift on `--bg-chrome` |
| Avatar | navy gradient | `--surface-3` → `--surface-1` |
| Type | `--bebas` / `--inter` page vars | `--font-display` / `--font-body` |

`css/community.css` has no colour literals; it is in `NEW_DESIGN_CSS` (strict).

**Layout:** unchanged. `body.has-auth-bar` (auth-bar.css, `padding-top: 72px`) out-ranked the old inline `body {}`; the new sheet sets only sides and bottom so that still holds (guarded). One fix: on `account.html` the Titles card sat 14px below Geek Points (`.card + .card` margin inside the two-up grid). Now level (`.acct .acct-grid > .card + .card { margin-top: 0 }`); see `before-/after-account-*`.

**Team Colors Mode** (the old Styleguide community-row fade): **not live.** No code references it; it exists only in `_documentation_master/11_Design_Systems/Styleguide.md` §Team Colors Mode. Left retired; UX_System says so.

## Shots

`reports/community-tokens/{before,after}-<surface>-{1280,1920}.png`, via `page.screenshot` at scroll 0. BEFORE was captured on develop before any edit (`COMMUNITY_BEFORE=1`). Surfaces: `leaderboard`, `leaderboard-tip` (archetype definition tooltip), `archetypes`, `account`. Data stubbed: `/api/auth/me` (points, titles, archetypes, lead), `/api/leaderboard/by-archetype` (your row on two boards), `/teams`.

## Tests

- `tests/e2e/community-tokens.spec.js`: shots + computed-style guards:
  - `html.gob` and tokens resolve; `css/community.css` loaded;
  - no navy or colour wash on the page; Inter body, Bebas headings;
  - `padding-top` still 72px;
  - your row navy and not orange, other rows untinted;
  - lead card navy, not orange;
  - % / points / status / segment / focus neither orange nor green; avatar untinted.
- **Fails on old code:** ran the guards (soft) with develop's three pages served via `page.route` from a scratchpad config. They fail on every page:
  - `your row navy rgba(247,148,32,0.12)`;
  - `lead card navy rgba(247,148,32,0.6)`;
  - `account total rgb(247,148,32)`, `segOn rgba(247,148,32,0.9)`, `status …`, `pct …`;
  - `focus ring rgba(247,148,32,0.6)`;
  - `no navy/colour wash … rgb(36,48,73)`, `avatar …`, `html.gob`.

  The padding guard passes on both, as intended: it pins the layout.

## Gates

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest --ignore=tests/e2e -q` | **4298 passed**, 14 skipped, 108 xfailed, 2 xpassed, **0 failed** (231.86s). Same two XPASS as before (`known_failures.py` not edited). |
| `scripts/check_ui_tokens.py --strict --no-write` | exit 0 (no pipe), before and after the merge |
| `scripts/ci/check_migration_gates.py` | passed. Gate A 0/0, Gate B 134 lines in 43 files. No `--write-allowlist`. |
| Playwright full `tests/e2e --workers=1` under `/tmp/gob-full-playwright.lock` (PORT=8244), merged tree | **812 passed, 7 skipped, 0 failed** (13.5m). No failures, so no `--repeat-each=5` reruns. All 3 `community-tokens` tests passed. Skips: 5 existing `test.skip`s plus 2 "handoff frames" tests that skip without `FRAMES_BASE`. |
| Targeted `community-tokens.spec.js` | 3 passed |

## Files

`FrontEnd/static/css/community.css` (new), `coaching-archetypes-leaderboard.html`, `coaching-archetypes.html`, `account.html`, `scripts/check_ui_tokens.py` (`NEW_DESIGN_CSS` + docstring), `_documentation_master/11_Design_Systems/UX_System.md` ("Community pages"), `tests/e2e/community-tokens.spec.js`, this report + shots.

## Unsure

- **Geek points colour:** points read as a count, so neutral. If they should be a reward surface, that needs a colour-law clause for `--reward-gold`, which is not in the list today.
- **Archetype badges:** the badges are SVG/PNG art with their own colours (orange/blue/purple glyphs), untouched as artwork.
- **`account.html` scope:** generic class names (`.card`, `.card-label`) are now scoped under `.acct` in the shared sheet so they cannot leak to the other two pages.
