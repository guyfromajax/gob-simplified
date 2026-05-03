# Active Page Analysis

**Location:** `docs/docs_1_systems/00_General_Systems/Active_Page_Analysis.md` (moved from `docs/To Do/`).

Generated from a static trace of the FrontEnd codebase (Spring 2026). This is a **best-effort navigation map**, not a formal route table. Dynamic URLs (`?game_id=`, `?franchise_id=`, etc.) are omitted; only **page shells** are listed.

## Methodology

1. **Declared entry:** `FrontEnd/static/homepage.html` (marketing home). Production routing (`FrontEnd/static/_redirects`) sends `/` → `homepage.html` with a 200 rewrite.
2. **Followed:** `<a href>`, `window.location` / `location.replace`, and string targets in JS (`*.js` under `FrontEnd/`).
3. **Auth:** `authGuard.js` public allowlist defines pages reachable without login; all other `.html` files assume login (or redirect to `login.html?redirect=…`).
4. **Multiple passes:** Hub pages (`mode-select`, `franchise-command-center`, `tournament`, `set-lineup`, `game-plan`, `playbooks`, `errorHandler`, `gameCompletionPopup`, `box-score`, etc.) were grepped for `.html` targets.
5. **Modals / overlays (second pass):** Same tree grepped for `modal`, `backdrop`, `popup`, `overlay`, `dialog`, and known popup class names; see **Modals, overlays, and in-page popups** below.

**Limits:** Bookmark/direct URL, email links, `login.html?redirect=` to arbitrary paths, and **admin/dev** pages (play builders, skeleton testers) are noted separately—they are “active” as files but not on the casual user path from the homepage CTA.

---

## Modals, overlays, and in-page popups (second pass)

**Methodology:** Grep across `FrontEnd/**/*.html`, `**/*.js` (shared, static, phaser) for `modal`, `backdrop`, `popup`, `overlay`, `role="dialog"`, and known class names (`confirm-modal`, `game-completion-popup`, etc.). Includes **DOM-injected** UI from JS, not only static HTML.

**Categories:**

| Category | Meaning |
|----------|---------|
| **Modal dialog** | Focus-trapped or blocking overlay with OK/Cancel pattern (`role="dialog"`, `.modal`, confirm flows). |
| **Full-screen overlay** | Covers the viewport (loaders, fatal error screen). |
| **Game overlay** | Lives inside `court.html` (announcements, sim progress, pre-game shell). |
| **Dynamic popup** | Created in JS (`createElement`, template strings) and appended to `document.body`. |

### Cross-page / injected (auth & shell)

| UI | Source | Where it appears |
|----|--------|------------------|
| **First-time experience (FTE)** | `authBarInit.js` → `#fte-backdrop`, `.fte-modal` | Injected on pages that load auth bar (most authenticated pages). |
| **Choose username** | `authBarInit.js` → `#fte-username-backdrop` | Same. |
| **Account settings** | `authBarInit.js` → `#account-settings-backdrop` | Same. |
| **Maintenance banner** | `maintenanceBanner.js` | Dismissible **top banner** (not a centered modal); loaded from `authGuard` on all pages. `starts_at_iso` without `Z`/offset is interpreted as **US Eastern** (`America/New_York`); see `Deploy_To_Live_System.md`. |
| **Page load overlay** | `pageLoadOverlay.js` / inline `#page-load-overlay` | `franchise-command-center.html`, `set-lineup.html`, `court.html`, etc.—full-screen until data ready. |

### By page (static HTML or page-specific script)

| Page | Modals / overlays |
|------|-------------------|
| `mode-select.html` | **New franchise confirm:** `#new-franchise-modal` (`.confirm-modal`). **Alpha disclaimer:** `#alpha-disclaimer` (slide-in panel; not a centered modal but blocking-style notice). |
| `signup.html` | **Access request thanks:** `#access-request-modal-backdrop` + `.access-request-modal`. |
| `game-plan.html` | **Validation:** `#validation-modal` (`#modal-message`, save errors via `showModal()` in `game-plan.js`). |
| `playbooks.html` | **Save confirm:** `#save-confirm-modal` (post-save shot weights). Per-section **Even Distribution** controls and the old `#confirm-modal` confirm were removed from `playbooks.html` / `playbooks.js` (2026). |
| `set-lineup.html` | **Playbook picker:** `#playbooks-modal` + `#playbooks-modal-backdrop`, `.lineup-modal-dialog`. |
| `franchise-command-center.html` | **Loaders:** `#page-load-overlay`, `#cc-loading-overlay`. |
| `tournament.html` | **Scouting report:** `#scouting-report-modal` (`.scouting-modal`). |
| `training.html` | **Player Maximizer / custom focus:** `#custom-focus-modal`. **Auto-train confirm:** `#auto-train-modal` (`.gob-modal-overlay`). |
| `cut-players.html` | **Cut confirm / messaging:** `#cut-modal-backdrop`, `.fcc-modal-card`. |
| `recruiting-orders.html` | **Recruiting messages:** `#recruiting-modal-backdrop`, `.recruiting-modal` (also driven by `showModal()` in `recruiting-orders.js`). |

### `court.html` — live game shell (DOM + Phaser-adjacent)

| Element / class | Role |
|-----------------|------|
| `.pre-game-container` / `.pre-game-modal-box` | Pre-game / quarter entry: **Play Quarter**, **Sim Full Game**, **Sim Quarter** (functional modal region). |
| `#sim-quarter-popup` | Sim-quarter scrolling **play-by-play** panel. |
| `#announcement-overlay` | **In-game announcements** (standard + foul/and-one card variants)—overlay, not a form modal. |
| `#shooter-audible-popup` | **Audible / hot read** prompt when applicable. |

### Dynamic popups (JS modules; typically while `court.html` or game flow active)

| Module | Class / id | Purpose |
|--------|------------|---------|
| `gameCompletionPopup.js` | `.game-completion-popup` | End of game: Box Score + Locker Room. |
| `defenseMatchupsPopup.js` | (defense matchups UI) | Q1 / quarter break / timeout / foul-out resume: **defensive matchup** editor. |
| `foulOutPopup.js` | `.foul-out-popup` | **Foul out** — lineup must replace player. |
| `timeoutButtonManager.js` | `.user-timeout-popup`, `.computer-timeout-popup` | **Timeout** → navigate to lineup. |
| `gameScene.js` | `.locker-room-popup` | **Quarter break / locker room** flow (multiple code paths). |

### Other pages

| Page | Modals / overlays |
|------|-------------------|
| `box-score.js` | **Special stats** (e.g. Fast Break breakdown): `#special-stats-popup` created on demand (see `box-score.css`). |
| `cut-players.js`, `recruiting-orders.js` | Local `showModal()` helpers driving the HTML modals listed above. |
| `errorHandler.js` | **Full-screen error** (replaces `document.body` innerHTML)—not a small modal; recovery buttons to lineup / hubs. |

### In-game announcement system (not “modals” but overlay UI)

- `announcements.js`, `gameAnnouncements.js`, `turnPreparation.js` — drive **center-court announcement cards** during animation; uses shared styling with `#announcement-overlay` on court.

### What this trace did **not** catalog exhaustively

- **Phaser-only** sprites/text inside the canvas (no DOM modal).
- **Every** `alert()` / `confirm()` (grep for these separately if needed).
- **CSS-only** unused classes (e.g. `.result-popup` in `court.html` CSS with no JS reference in this pass—may be legacy).

---

## Primary user flow (homepage → game)

| Step | Page | How reached |
|------|------|-------------|
| 0 | `/` or `homepage.html` | Root redirect; logo links to `/` |
| 1 | `mode-select.html` | “Play The Alpha”, franchise card CTAs |
| 2a | `franchise-select-team.html` | New franchise / team pick |
| 2b | `franchise-command-center.html` | Existing franchise “Enter” |
| 3+ | See **Franchise locker room** below | |

Parallel paths from homepage: `tutorial.html`, `login.html`, `signup.html`, `faqs.html`, `reset-password.html` (linked from login).

---

## Active pages (in product flow from homepage / auth)

### Public (pre-login allowed by `authGuard.js`)

- `/` (rewritten to `homepage.html` in production)
- `homepage.html`
- `index.html` — immediately redirects to `/homepage.html` (legacy body below redirect is effectively dead)
- `login.html`, `signup.html`, `reset-password.html`, `faqs.html`

### Coach hub & mode

- `mode-select.html` — franchise entry; alpha leaderboard
- `franchise-select-team.html` — choose program
- `franchise-command-center.html` — franchise “locker room”
- `tournament-select.html` — pick tournament (links to `tournament.html`)
- `tournament.html` — tournament bracket / hub

### Gameplay pipeline

- `set-lineup.html` — lineup, play game, timeouts → `court.html`
- `game-plan.html` — scouting / plan (franchise & tournament)
- `court.html` — Phaser live game
- `box-score.html` — post-game / in-flow
- `gameCompletionPopup` / `box-score` / `finalizeGame` — return to `tournament.html`, `franchise-command-center.html`, or `mode-select.html`

### Resources & data (from FCC / tournament tabs and links wired in JS)

- `standings.html`, `schedule.html`, `stats.html`, `team-stats.html`, `leaders.html`, `rankings.html`, `team-traits.html`
- `team-roster-view.html` — roster table (franchise/tournament context)
- `player-detail.html` — player profile (from roster, lineup, FCC, cut players, etc.)

### Recruiting & roster management

- `recruiting.html`, `recruiting-results.html`, `recruiting-orders.html`
- `cut-players.html`
- `training.html`, `training-report.html`

### Playbooks

- `playbooks.html`, `play-details.html`, `playbook-report.html`

### System / account

- `tutorial.html` — linked from nav on homepage and auth bar injection

### Developer / admin tooling (requires auth; **not** linked from homepage CTA)

Reachable by **direct URL** or internal tooling; `adminGuard.js` restricts these to admin users:

- `play-builder.html`, `play-builder-v2.html`, `plays-builder.html`
- `fcp-skeletons.html`, `hct-skeletons.html`

These are **active for admins** but **not** part of the casual user graph from the homepage.

---

## Pages present in repo but not in the homepage trace (orphaned / legacy / ops)

These are **not** reached by following links from `homepage.html` through normal product CTAs. Some remain useful for **manual URL**, **ops**, or **legacy**.

| File | Notes |
|------|--------|
| `FrontEnd/static/scrimmage-select.html` | Old single-game picker; uses `team-select.js`. **No** references found in other pages/scripts to this path (sunset per mode-select copy). |
| `FrontEnd/static/coaching-grid.html` | Standalone; no incoming links found. |
| `FrontEnd/static/maintenance.html` | Referenced in `_redirects` as optional **maintenance mode** target; not a normal user flow. |
| `FrontEnd/static/homepage-backup.html` | Backup marketing page. |
| `FrontEnd/static/awards.html` | No `awards.html` href in `static/` JS/HTML grep. |
| `FrontEnd/static/index.html` | Redirects to homepage; duplicate legacy scrimmage markup below fold is unused after redirect. |
| `FrontEnd/index_legacy.html` | Legacy; links `roster.html`. |
| `FrontEnd/games.html` | Legacy “Past Games” + `app.js`. |
| `FrontEnd/player.html`, `FrontEnd/roster.html` | Early prototypes; not linked from traced flow. |
| `FrontEnd/static/team-roster/*.html` | Static per-team roster pages (e.g. `Bentley-Truman.html`, `team-roster-*.html`). **No** references found from main app JS. |
| `FrontEnd/static/js/phaser/animation/tests/runFCPHCTTests.html` | Test harness. |
| `FrontEnd/static/js/phaser/animation/tests/runBaselineInboundTests.html` | Test harness. |

---

## Summary counts (approximate)

- **User-facing active shells (franchise/tournament/game path):** ~35 distinct `.html` routes (excluding admin-only).
- **Admin-only active:** 5 pages (play builders + skeleton testers).
- **Orphaned / legacy / tests / ops:** listed above; static `team-roster/` multiplies the count (15+ files).

---

## Reconciliation: “all HTML files” vs “active trace”

A full file list lives under `FrontEnd/` (`**/*.html`). Anything **not** listed in **Active pages** or **Admin** sections above falls into **orphaned / legacy / ops / tests** unless your deployment adds routes not present in this repo.

---

## Suggested follow-ups

1. **Delete or archive** confirmed-sunset pages (`scrimmage-select`, `index_legacy`, `games.html`, `player.html`, `roster.html`, `homepage-backup`) after confirming no external links.
2. **Redirect** `awards.html` or wire FCC “Awards” to it if the feature is still desired (currently FCC links **Leaders** to `leaders.html`, not `awards.html`).
3. **Document** admin URLs in internal runbooks for play-builder/skeleton testers.
