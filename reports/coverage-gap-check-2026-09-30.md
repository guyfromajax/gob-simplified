# Coverage-gap cross-check — 2026-09-30

Branch `docs/coverage-gap-check` off `origin/develop`. **Read-only; docs only** — no
product code touched. Cross-checks the legacy migration inventory
(`reports/legacy-migration-plan-2026-09-30.md`, "the plan") against every screen a
player can actually see: web HTML, the Electron shell, live-game Phaser overlays, and
error/ops pages. `check_migration_gates.py`: **passed, nothing changed** (Gate A 0/0,
Gate B 136/44).

**Colour-law note.** The plan's "law hits" are `check_ui_tokens` violations
(green/orange/reward-gold off token). The counts in this doc for the Phaser/court
overlays are **raw `#hex` + `rgb()/rgba()` occurrences** (what the task asked for:
"grep hex/rgb"), a rough size for a future visual pass — not the same metric, always ≥
the plan's law hits.

---

## 1. Every `*.html` outside node_modules/.venv/vendor

Scope = repo HTML that could serve a player. `_documentation_master/projects/**`
(≈120 files: design mockups, handoffs, frames), `playwright-report/index.html`,
`tests/e2e/fixtures/depth-harness.html`, and `js/phaser/animation/tests/*.html` are
**test/design artifacts, never served** — excluded (none are player-reachable; Netlify
publishes only `FrontEnd/static`, FastAPI mounts only `FrontEnd/static`).

Netlify `publish = FrontEnd/static`; FastAPI serves the same dir (dual-serve for
Playwright). So `FrontEnd/static/*.html` is reachable by URL; `FrontEnd/*.html` (repo
root, **not** in `static/`) is **not published or served**.

| HTML file | In the plan? | Reachable by a player? (evidence) |
|---|---|---|
| `FrontEnd/static/` app pages — recruiting, training, training-report, playbooks, game-plan, scouting, set-lineup, box-score, cut-players, playbook-report, training-playbooks, training-squad-report, play-details, franchise-command-center, account, alpha-feedback, coaching-archetypes(+leaderboard), franchise-select-team, team-builder, login, signup, reset-password, homepage(+v3), faqs, privacy, terms, tutorial(+7 core +4 advanced +persona/situation/pick-opponent), stats, team-traits, court | **yes** (inventory §1 / batches / §3) | yes — rail/route/Advance flow per plan |
| `mode-select.html` | **implicit** — "already new design" (Home Base), not a table row | yes — `START_PAGE`, rail home. On design system (`home-base.css`) |
| `trophy-case.html` | **implicit** — "already new design" | yes — Home Base / milestone link. On design system |
| Redirect stubs already in the plan: `standings`, `rankings`, `leaders`, `team-stats`, `news`, `awards`, `brackets`, `practice-squad-standings`, `practice-squad-bracket`, `training`, `game-plan`, `playbooks`, `training-report`, `player-detail`, `team-roster-view` | **yes** (§3 "already redirects") | yes — stubs → FCC in-app views |
| Admin: `fcp-skeletons`, `hct-skeletons`, `play-builder`, `play-builder-v2`, `plays-builder` | **yes** (§3 admin) | admin only (`adminGuard`) |
| Ops: `trailer.html`, `maintenance.html` | **yes** (§3 ops) | Netlify `/trailer`; maintenance = wildcard (commented) — see §4 |
| Dupe/sync: `homepage-v3-source.html` | **yes** (§3) | no — `sync:homepage` write target |
| **`schedule.html`** | **NO** | **yes** — redirect stub → FCC `?tab=league-schedule-view` (`schedule.html:6-13`; `gobShell.js:114,250`; `authGuard.js:86`). Same class as standings/etc but **not listed** |
| **`game-plans.html`, `scouting.html`, `player-attributes.html`, `team-attributes.html`** | **NO** | **yes (redirect)** — old tutorial names → `/tutorial-*.html` (`location.replace`, each `*.html:12`). Not in the stub list |
| **`index.html`** (static) | **NO** | **yes (redirect)** — `location.replace('/homepage.html')` (`index.html:15`); `_redirects` also `/  /homepage.html 200!`. Duplicate of the `/` entry |
| **`FrontEnd/games.html`, `index_legacy.html`, `player.html`, `roster.html`** | **NO** | **DEAD** — outside `FrontEnd/static` (not published, not FastAPI-mounted); **zero** references in `FrontEnd/static`, `BackEnd`, `desktop`, `netlify.toml`. Deletion candidates (ch8-cleanup bar) |

**Section-1 gaps:** `schedule.html` (reachable stub, unlisted); 4 tutorial redirect
stubs (reachable, instant redirect, unlisted); `index.html` (redirect dupe); 4 dead
`FrontEnd/` root files (delete candidates).

---

## 2. Desktop app's own screens (Electron shell, not a `FrontEnd/static` page)

The plan is web-page-only; **none of these are in it**. Main window loads the web app
(`START_PAGE=/mode-select.html`) from loopback, so franchise chrome is the design
system — but the shell's own surfaces below are hand-styled and **off the design
system**.

| Surface | file:line | Looks like today | gob-tokens? | Shot |
|---|---|---|---|---|
| Main window chrome | `desktop/main.js:64-78` | 1440×900 (min 1024×700), title **"GOB"**, `backgroundColor: '#0b1020'` (raw navy) | no | — |
| App / window icon | `desktop/package.json:9` (`pack`) | `electron-packager` with **no `icon`** flag, no `productName` → **default Electron icon** | n/a | — |
| Native app menu | none — no `Menu.setApplicationMenu` in `main.js` | **default Electron menu** (File/Edit/View/Window/Help) | n/a (OS) | — |
| Splash / loading | `desktop/main.js:118` → `desktop/splash.html` | Inline `<style>`: bg `#0b1020`, text `#f4f1ea`, orange pulse `#e24a1b`, **system font** (`-apple-system…`), "GOB" + "Starting the local engine…" | **no** (no gob-tokens, no app fonts) | `desktop-splash.png` |
| Engine-crash screen | `desktop/main.js:53-60` → `desktop/error.html` | Inline `<style>`, same navy/cream, `code` block `#161b2e`, system font, "The engine stopped" + message | **no** | `desktop-error.png` |
| Native error dialogs | `main.js:58` (crash fallback), `:89` (checkout not found / first-run), `:103` (port in use) | `dialog.showErrorBox('GOB', …)` — OS-native box, no styling control | n/a (OS) | — |
| Quit / lifecycle | `main.js:149-172` (single-instance, before-quit, window-all-closed) | No custom quit confirm dialog | n/a | — |
| First-run folder picker | none — no `dialog.showOpenDialog` anywhere | Not implemented (repo auto-detected) | n/a | — |
| Auto-update dialog | none — no `autoUpdater` | Not implemented | n/a | — |

**Section-2 gap:** the entire desktop shell (window bg, default icon, default menu,
splash, crash screen, 3 native error boxes) is off the design system and absent from
the plan. Splash + crash are the two a player actually sees (every launch / on engine
death).

---

## 3. Live-game overlays (Phaser / court) — size for a sim-safe visual pass

The plan flags `court.html` as "do not migrate the sim" but does **not inventory the
individual overlays** a player sees every game. Sizes below are **raw hex+rgb** (see
top note). **DON'T TOUCH** — this table is to plan a sim-safe pass only.

| Overlay | file | Styled how | hex+rgb (raw) |
|---|---|---|---|
| Court chrome (scoreboard, stat panels, playcall center, controls) | `court.html` (inline `<style>`) | DOM + inline CSS in the page | **518** (300 hex / 218 rgb), 7,800 lines |
| Sim broadcast (fast-sim presentation, cards, worm) | `js/phaser/utils/simGamePresentation.js` | DOM/CSS (createElement) | **94** (31/63) |
| End-of-game popup | `js/phaser/utils/gameCompletionPopup.js` | DOM/CSS | **47** (11/36) |
| Pre-game experience (intro/tip-off) | `js/phaser/utils/preGameExperience.js` | DOM/CSS | **43** (14/29) |
| Defense matchups / play-call menu | `js/phaser/utils/defenseMatchupsPopup.js` (+ `matchupsUiShared.js` 17, `defenseUi.js` 0) | DOM/CSS | **35** |
| Post-game press conference modal | `js/phaser/utils/postGamePressConference.js` (+ `pgpcSammyReminderModal.js` 5) | DOM/CSS | **20** |
| Foul-out popup | `js/phaser/utils/foulOutPopup.js` | DOM/CSS | **15** |
| On-canvas scoreboard / labels | `js/phaser/gameScene.js` | **Phaser text styles** (hex in text config, 0 rgb) | **11** (4,635 lines) |
| Announcement banners | `js/phaser/utils/announcements.js` 5, `gameAnnouncements.js` 2 | Phaser text | **7** |
| Stat / active-player / strategy / playcall readouts | `statusDisplay.js` 4, `activePlayerDisplay.js` 0, `strategyBars.js` 0, `playcallDisplay.js` 0, `simCalloutCopy.js` 0 | Phaser text (canvas) | **4** |

**Split for a visual pass:** DOM/CSS overlays (completion, PGPC, matchups, foul-out,
sim broadcast, pre-game) can be reskinned like other DOM modals; the on-canvas set
(gameScene, announcements, status/strategy/playcall) needs Phaser text-style edits and
is the sim-risk zone.

**Playbooks CSS (`css/playbook-tiles.css`) sharing — correction to the plan.**
`playbook-tiles.css` is loaded **only** by `playbooks.html` and `playbooksView.js`.
**No live-game overlay loads it.** The court Playcall Center is styled by `court.html`'s
own inline CSS (`#playcall-center`, `.playcall-row`, `#defensive-playcall`,
`#offensive-playcall`); `playcallCenter.js` has 0 colours. So restyling
`playbook-tiles.css` does **not** change the live game — the plan's batch-3 risk
("touching tiles can change live game chrome") is a class-name resemblance, not a
shared stylesheet. Worth confirming with Jamie before the batch is scoped.

---

## 4. Player-facing error / ops pages

| Surface | Where | On the design system? |
|---|---|---|
| In-app view error card ("This view could not be opened." + Retry) | `js/shared/gobViews.js:101-106`; styled `.gob-view-error`/`.gob-view-retry` in `css/gob-views.css` + `gob-tables.css` (137 `var(--…)` token refs) | **yes** — on design system. Most-seen error state (any browse view fetch fail) |
| Maintenance page | `FrontEnd/static/maintenance.html` (57 lines) | **no** — inline `<style>`, raw hex (`--bg:#0f172a`), `system-ui` font, loads `/css/fonts.css` but **not** gob-tokens. Netlify wildcard is commented, so rarely served today. Shot: `maintenance.png` |
| Desktop engine-crash screen | `desktop/error.html` (§2) | **no** — inline styles, raw hex, system font |
| Custom 404 page | **none** — no `404.html`, no `_redirects`/`netlify.toml` catch-all (only `/  /homepage.html 200!` for the root). Bad URL → **Netlify's generic 404** | **no page exists** — gap |
| API "not found" (game/player) | `BackEnd/api/api.py` (e.g. `:2746` `Game … not found` 404 JSON) | JSON only; the browse view surfaces it via the gob-views error card above | via design-system card |
| Offline / connection-lost banner | no dedicated "connection lost / reconnect" screen; failures fall through to the gob-views error card + Retry, or (desktop) the engine-crash screen | error card = yes; no standalone offline screen |

**Section-4 gaps:** no branded **404** page (Netlify default), `maintenance.html` off
the design system, no dedicated offline/reconnect screen (falls back to the in-app
error card, which is on-system).

---

## Missing from the plan — ordered by how often a player would see it

1. **Live-game overlays (§3).** Seen **every game**. The plan flags `court.html` as
   "don't migrate" but never inventories the EOG popup, PGPC modal, matchup/play-call
   menu, foul-out popup, sim broadcast, pre-game, or the on-canvas scoreboard /
   announcements. Biggest coverage gap. (Also: the playbook-tiles↔court risk note is
   overstated — no live overlay loads that sheet.)
2. **Desktop shell screens (§2).** Seen **every desktop launch** (splash) and on
   engine death (crash screen), plus default icon/menu and 3 native error boxes. Whole
   surface is off the design system and absent from the plan.
3. **No custom 404 page (§4).** Any mistyped/stale URL → Netlify's unbranded 404.
   Occasional but fully off-brand.
4. **`schedule.html` redirect stub (§1).** Reachable via League Schedule; same class as
   the listed standings/rankings stubs but omitted from the plan's stub list.
5. **`maintenance.html` off design system (§4).** Rare (wildcard commented), raw hex +
   system font; note for when it's re-enabled.
6. **Tutorial redirect stubs `game-plans` / `scouting` / `player-attributes` /
   `team-attributes` (§1).** Reachable but instant `location.replace` to `/tutorial-*`
   — near-zero dwell; list them as stubs so they aren't mistaken for real pages.
7. **`index.html` (static) redirect (§1).** Duplicate of the `/` → homepage entry;
   housekeeping only.
8. **Dead `FrontEnd/` root files — `games.html`, `index_legacy.html`, `player.html`,
   `roster.html` (§1).** Never served, zero references → **zero** player visibility;
   deletion candidates (ch8-cleanup bar), not migration.

Everything else a player can see **is** accounted for in the plan (inventory,
redirect-stub list, admin/ops/dupe sections, or "already new design").

## Screenshots (`reports/coverage-gap-check/`)

- `desktop-splash.png` — Electron boot splash (1440×900): navy `#0b1020`, cream "GOB", orange pulse, system font — off design system.
- `desktop-error.png` — Electron engine-crash screen with a sample message — off design system.
- `maintenance.png` — `maintenance.html` (1280×720) — off design system.

STATUS: COMPLETE (read-only; no product code changed)
