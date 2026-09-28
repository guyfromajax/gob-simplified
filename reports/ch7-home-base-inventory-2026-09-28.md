# Chapter 7 — Home Base inventory (Mode Select)

Branch: `docs/ch7-home-base-inventory` (`~/gob-stats`, from `origin/develop`).  
**Home Base** = pre-franchise hub at `/mode-select.html` (“Coach's Home Base”). The in-franchise GOB shell (rail + top bar) does **not** apply here.

Screenshots (1280×720, full page):  
`reports/ch7-home-base/home-base-online-1280x720.png`, `home-base-offline-1280x720.png`.

---

## 1. Online inventory (`mode-select.html`)

### Page shell & global chrome

| Element | What it shows | Data / route | Cached? | Owner files | Click / behavior |
|--------|----------------|--------------|---------|-------------|------------------|
| **Loading panel** | “Loading Coach Home Base / Checking your session…” | None | — | `mode-select.html`, `mode-select.css` (`.mode-select-loading*`), `mode-select.js` (`revealModeSelect`) | Hidden after auth + initial franchise list fetch complete |
| **Auth bar** (injected) | Logo → homepage, **Tutorials**, YouTube, X, **Settings** (gear), **Log Out**; optional **Alpha** badge center | `authBarInit.js` loads `auth-bar.css`; `/app-config` for alpha; `/api/auth/me` refreshes username | `localStorage` auth_token / auth_user; app-config cached in `API_CONFIG` | `js/shared/authGuard.js` → `authBarInit.js`, `css/auth-bar.css` | Logo → `/homepage.html`; Tutorials → `/tutorial.html`; YT/X external; Settings → `GOBSettings.toggle()` (`gobSettings.js`); Log Out → `POST /api/auth/logout`, clear token, show logged-out bar |
| **Alpha disclaimer** | Dismissible alpha copy (attribute-system warning) | `GET /app-config` → `isAlpha`; dismiss → `localStorage` key `alpha_disclaimer_dismissed_version` | Yes (localStorage) | `mode-select.html`, `mode-select.js` (`wireAlphaBanner`) | × dismisses banner |
| **Background music** | Championship_Gridlock loop | Static `/sounds/Championship_Gridlock.mp4` | — | `mode-select.js` | Fades on navigate away (`navigateFromModeSelect`) |
| **FAQs strip** | Orange “FAQs” footer link | Static | — | `authBarInit.js` (footer injection on some pages); mode-select layout padding reserves bottom space | → `/faqs.html` (also linked inside Settings panel) |

Supporting scripts/styles on the page: `franchiseContext.js`, `gobNav.js`, `authGuard.js`, `api-config.js`, `franchiseLocalStorage.js`, `pageLoadOverlay.js`, `archetypeBadge.js`, `common.js`, `teamGeneratedArt.js`, `tierEmblem.js`, **`mode-select.css`** (no `gob-tokens.css` / `gob-components.css`).

### My Franchises (program slots)

| Element | What it shows | Data / route | Cached? | Owner | Click |
|--------|----------------|--------------|---------|-------|-------|
| Section header | “My Franchises” + “Two program slots” | Static | — | HTML + CSS | — |
| **Slot grid** `#franchise-home-slots` | Always **2** cells (01 / 02), empty or occupied | `GET /franchise/list` → `{ franchises[], max }`; per franchise `GET /franchise/command-center/data?franchise_id=` for record, next opponent, resume | List: server; resume hints from CC payload; `FranchiseLS` cleared on exit/delete | `mode-select.js` (`renderFranchiseSlots`, `buildEmptySlotHtml`, `buildOccupiedSlotHtml`) | See flows §4 |
| **Empty slot** | Ball icon, “Start Your Coaching Journey” (or “Start Another Franchise” if ≥1 exists), **Find Your Program** (orange) | — | — | `mode-select.css` (`.franchise-empty-cta`) | → `franchise-select-team.html?home_slot=1|2` (`startNewFranchiseFlow`) |
| **Occupied slot card** | Banner, team name, season/week line, Record + Next Opponent chips, tier emblem, optional **Game In Progress** or **Finishing Week** strip | List fields from `_franchise_summary_for_list`; chips from CC data + schedule helpers | Tier emblem from CC `user_conference` / `user_region` | Same + `tierEmblem.js` | Card / **Enter Franchise →** (green) → FCC or court or CPU finish (see `goToFranchiseCommandCenter`) |
| **Slot ⋯ menu** | Delete Franchise | — | — | HTML modal `#delete-franchise-modal` | Confirm → `DELETE /franchise/{id}`, `FranchiseLS.clearAllForFranchise`, reload |
| **Slots full modal** | “Delete one to start another” | Client-side `franchisesList.length >= max` | — | `#slots-full-modal` | OK dismiss |

**List payload (per franchise):** `franchise_id`, `user_team_id` (display name), `user_team_object_id`, `week`, `current_season`, colors, `home_slot`, Team Builder flags (`is_custom_team`, `team_builder_replaced_name`, etc.) — `BackEnd/api/franchise_routes.py` `_franchise_summary_for_list`.

**Also loaded:** `GET /teams` (team docs for banners / TB art).

### Head to Head — Find A Game

| Element | What it shows | Data | Cached? | Owner | Click |
|--------|----------------|------|---------|-------|-------|
| PvP teaser panel | “Head to head / Find A Game / Your program against another coach's program.” + **Coming Soon** | Static markup only (no API) | — | `mode-select.html`, `mode-select.css` (`.fag-*`) | **None** (no link; status dot + copy only) |

Planned **online-only** per PvP audit (`pvp/pvp-technical-audit-2026-09-28` — referenced in product docs; not in this repo snapshot).

### Around The League

| Element | What it shows | Data / route | Cached? | Owner | Click |
|--------|----------------|--------------|---------|-------|-------|
| Panel + 8-slot grid | Latest league-wide result cards (coach, teams, score, rank, record) or placeholders | `GET /api/community/around-the-league` → `{ slots[] }` (8 slots) | **Client:** `localStorage` `gob_atl_last_visit` (timestamps for “since last visit” styling); **sessionStorage** `gob_atl_animate_self` for self-insert animation | `mode-select.js` (`loadAroundTheLeague`, `atl*`) | Cards are display-only (no navigation) |
| Polling | Refetch every 20s + on tab visible | Same endpoint | — | `wireAroundTheLeaguePolling` | — |
| Error state | “Could not load Around The League.” | Failed / null response | — | `loadAroundTheLeague` | — |

Requires auth headers on web; category **`community_highlights`** → always **remote** in `api-config.js` (desktop still calls remote host for this path).

### Leaderboard

| Element | What it shows | Data / route | Cached? | Owner | Click |
|--------|----------------|--------------|---------|-------|-------|
| Toggle | Geek Points / Titles | Client `currentLeaderboardView` | — | `mode-select.js` | Re-renders from `currentLeaderboardData` |
| Subtitle | GP or titles helper copy | Static | — | `.ms-leaderboard-subtitle` | — |
| Rows | Top 5 + pinned current user | `GET /api/auth/leaderboard` → `{ top[], current_user, titles_top[], titles_current_user }` | In-memory `currentLeaderboardData` only | `loadCommunityLeaderboard`, render fns | — |
| **View leaders by team** | Modal A1 conference grid | `GET /api/leaderboard/by-team?view=geek_points|titles` | — | `loadLeadersByTeam`, `#leaders-by-team-modal` | Opens modal; close backdrop/✕ |
| **Coaching Archetypes** | — | — | — | inline onclick | → `/coaching-archetypes-leaderboard.html` (`navigateFromModeSelect`) |

Default HTML placeholder: “Leaderboard coming soon” until first fetch returns.

### Community Highlights

| Element | What it shows | Data / route | Cached? | Owner | Click |
|--------|----------------|--------------|---------|-------|-------|
| Feed rows | Week/game/archetype/debut highlight copy + GP chip | `GET /api/community/highlights` | — | `loadCommunityHighlights`, `renderCommunityHighlights` | Display-only |
| Empty | “No highlights yet — finish a franchise week…” | Empty `highlights[]` | — | — | — |
| Unauthenticated message | “Sign in to see community highlights.” | `safeJsonFetch` null (no token / failed) | — | — | — |

Uses `GOBArchetype.ensureManifest()` for archetype names when present.

### Modals (non-slot)

Already covered: delete franchise, slots full, leaders-by-team.

---

## Reachable flows from Home Base (online)

| Destination | Entry from Home Base | Key API / files |
|-------------|----------------------|-----------------|
| **Login** | Redirect if no token (web only) | `login.html?redirect=/mode-select.html` — `authGuard.js`, `mode-select.js` |
| **franchise-select-team.html** | Find Your Program / empty slot | `franchise-select-team.html/js/css`; `POST /franchise/select-team` or Team Builder → `team-builder.html` |
| **team-builder.html** | From select-team “Open Team Builder” / replace flow | `franchise-select-team.js` `takeThisPlace` |
| **franchise-command-center.html** | Enter Franchise on occupied slot | `?franchise_id=`; may add `finish_cpu_sims`, or route to **court.html** if mid-game |
| **tutorial.html** | Auth bar Tutorials | Static tutorial hub |
| **FTE tutorial funnel** | Auth bar logic may redirect new users (not on mode-select itself) | `authBarInit.js` tutorial_state → persona intro, select-team `?mode=tutorial`, etc. |
| **coaching-archetypes-leaderboard.html** | Leaderboard footer link | `navigateFromModeSelect` |
| **account.html** | Settings → Account details (online only) | Linked from `gobSettings.js` |
| **homepage.html** | Logo | Marketing home |
| **Settings panel** | Gear | `gobSettings.js` + `gob-settings` CSS (uses `.gob` host); coach stats from `/api/auth/me` online |

**New franchise creation (typical):** Mode Select → Find Your Program (1 click) → pick team on select-team (1 click + confirm) → **FCC** (auto redirect). Team Builder path adds select-team → Open Team Builder → TB chapters → franchise create APIs.

---

## 2. Offline / desktop profile (`GOB_BUILD_PROFILE=desktop`)

Same **HTML layout** — community panels are **not** hidden in CSS or JS. Desktop differs by **auth**, **routing**, and **remote-only APIs**.

| Area | Desktop behavior |
|------|------------------|
| **Auth** | `authGuard.js` skips login redirect; `mode-select.js` sets user label **“Coach”**, `atlCurrentUserId = 'local-desktop-user'` |
| **Auth bar** | Still injected (Tutorials, Settings, Log Out visible in screenshot). Settings → offline account note, **no** `/api/auth/me`, **no** coach stats tiles |
| **Franchise slots** | `GET /franchise/list` → **loopback** (`127.0.0.1:GOB_LOOPBACK_PORT`) against local SQLite |
| **Around The League** | Still requested → **remote** `/api/community/around-the-league` → fails offline → **“Could not load Around The League.”** |
| **Leaderboard** | Remote `/api/auth/leaderboard` → fails → **“No alpha leaderboard data yet”** (empty `top`) |
| **Community Highlights** | Remote `/api/community/highlights` → null body → **“Sign in to see community highlights.”** (misleading copy; desktop has no online session) |
| **Find A Game** | Same static “Coming Soon” panel (should remain non-actionable; PvP online-only) |
| **Log Out** | Still wired; clears localStorage tokens (low value offline) |

Screenshot capture: loopback via `tests/e2e/helpers/seed_and_serve_desktop.py` on **8767**, page init `GOB_BUILD_PROFILE=desktop`, `GOB_LOOPBACK_PORT=8767`. See `home-base-offline-1280x720.png`.

Online screenshot: mongomock `seed_and_serve.py` on **8010**, stub auth + sample ATL slots; empty franchise list. See `home-base-online-1280x720.png`. (Live production leaderboard uses `{ top, current_user }` shape from `/api/auth/leaderboard`.)

---

## 3. Data available offline for a redesigned Home Base

| Data | Offline today | Where / notes |
|------|----------------|---------------|
| **Franchise saves (0–2)** | **Exists** | SQLite via loopback `/franchise/list` + `_franchise_summary_for_list`: name, week, season, colors, `home_slot`, TB metadata |
| **Per-save record / next opponent** | **Exists** (when CC data loads) | `/franchise/command-center/data` on loopback — same as online slot cards |
| **Active game / CPU week resume** | **Exists** | CC payload `active_game_resume`, `cpu_sim_resume` |
| **Last played timestamp** | **Missing** on list card | Franchise docs may have `updated_at` server-side but **not** exposed in list summary or mode-select UI |
| **Coach career record (12–5)** | **Missing offline** | Online: `users.record` via **`GET /api/auth/me`** → Settings “Coach stats” (`gobSettings.js` `paintCoach`). Desktop **`loadIdentity` returns early** — section hidden |
| **Title counts (3 titles)** | **Missing offline** | Online: `users.championships_total` on `/api/auth/me` → Settings. **Not** on mode-select surface; **not** loaded offline |
| **Geek Points / leaderboard rank** | **Missing offline** | Remote-only API; no local mirror |
| **Around The League feed** | **Missing offline** | Remote-only; only client cache is last-visit **timestamp**, not feed body |
| **Community highlights** | **Missing offline** | Remote-only |
| **Achievements / badges** | **Missing** | No Home Base consumption; no local achievements store found for mode-select |
| **Tutorial / FTE progress** | **Partial** | `auth_user` / server `tutorial_state` online; desktop local principal — tutorial routing differs |
| **Audio / UI prefs** | **Exists** | `uiSfx` / localStorage levels in Settings |
| **Alpha disclaimer dismiss** | **Exists** | localStorage |
| **FranchiseLS keys** | **Exists** | Per-franchise client keys (`franchiseLocalStorage.js`) — resume helpers, not a home-base dashboard |

---

## 4. User flows (click counts, today)

Assumes web, authenticated, starting from loaded Home Base.

| Scenario | Steps (clicks / navigations) |
|----------|------------------------------|
| **First launch, no franchises** | 0 → see 2 empty slots → **Find Your Program** (1) → select-team → choose team (1) → FCC (auto) ≈ **2 clicks** to enter new franchise |
| **Returning, 1 program** | **Enter Franchise →** on occupied slot (1) → FCC ≈ **1 click** |
| **Returning, 2 programs** | Pick slot → **Enter Franchise →** (1) → FCC |
| **Both slots full, start another** | Find Your Program on empty slot N/A → if user triggers new via bug/workaround: **Slots full** modal (1) OK — **blocked**; must delete first |
| **Delete / archive** | ⋯ (1) → Delete Franchise (1) → confirm Delete (1) → reload ≈ **3 clicks** |
| **Continue last program** | No “last played” shortcut — user must know slot → **Enter Franchise →** (1). If mid-game: same button labeled **Resume Game →** (1) → court |
| **Settings / coach stats (online)** | Gear (1) — stats visible without extra click |
| **Tutorials** | Tutorials link (1) → tutorial hub |
| **Team Builder new program** | Find Your Program (1) → Open Team Builder (1) → TB flow (multiple) |

---

## 5. Design system state

| Question | Finding |
|----------|---------|
| **Uses gob-tokens / gob-components?** | **No** on mode-select. Standalone **`mode-select.css`** (~2k lines): hard-coded `#0b0d14`, `#F79420`, `#34EC27`, Inter + Bebas via `fonts.css` / local rules. Settings panel pulls **`gobSettings.js`** which adds `.gob` host + token-backed settings CSS when opened. Auth bar uses **`auth-bar.css`**. |
| **Shell** | Not used (correct for pre-franchise). |

**Colour-law / UX violations (GOB colour law: green = single Advance; orange = non-advancing / gated):**

| Control | Color | Role | Violation? |
|---------|-------|------|------------|
| **Find Your Program** (empty slot) | Orange gradient | Starts new franchise / save slot | **Likely yes** — primary forward action on empty slot uses **orange**, not green “Advance” |
| **Enter Franchise →** / Resume / Finish Week | Green (`#34EC27`) | Continue into franchise | **Aligned** — primary continue |
| **Find A Game** panel | Gold/orange decorative | Teaser, Coming Soon | OK as promo / gated |
| **Leaderboard current-user row** | Orange accent border | Highlight | OK (emphasis, not advance) |
| **Log Out** | Outlined neutral | Destructive exit | OK |
| **Delete Franchise** | Modal confirm (styled in mode-select.css) | Destructive | Should not be green — verify uses non-green confirm styling |

---

## 6. Constraints (Chapter 7)

| Constraint | Implication |
|------------|-------------|
| **PvP Find A Game** | Online-only when built; today non-interactive teaser. Offline Home Base should **not** imply matchmaking. |
| **Web build keeps community** | Around The League, Leaderboard, Highlights must remain on **web**; remote APIs + polling stay. |
| **Desktop must not depend on online-only routes** | Today desktop **still calls** `/api/community/*` and `/api/auth/leaderboard` (always-remote table) — failures are user-visible. A dedicated offline Home Base should use **loopback franchise data only** and omit or replace community blocks without hitting remote hosts. |
| **Jamie direction** | Offline should be a **purpose-designed** screen, not online with dead panels. |

---

## Screenshots (self-check)

| File | Notable content |
|------|-----------------|
| `home-base-online-1280x720.png` | Auth bar, dual empty slots + orange Find Your Program, Find A Game teaser, ATL grid with sample coaches, empty highlights, leaderboard placeholder, FAQs footer |
| `home-base-offline-1280x720.png` | Same layout; ATL error; highlights “Sign in…”; leaderboard empty; loopback empty slots |

---

STATUS: COMPLETE
