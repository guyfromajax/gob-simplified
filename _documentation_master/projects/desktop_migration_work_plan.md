# Desktop Migration Work Plan — GOB

**Purpose:** Practical work plan for migrating GOB from an online-only web app to the hybrid model: a standalone desktop build for single-player franchise play, with the online layer (accounts, community, recruit packs, subscription, PvP) remaining on remote infrastructure.

**Companion docs:** `app_build_dynamics.md` (target behavior — which builds have which locks), `repo_audit.md` (codebase evidence this plan is built on), `Steam_Strategy.md` (the calendar this must serve).

**Last updated:** July 2026

---

## 0. Objective and non-negotiables

**Objective:** By late December 2026, a standalone desktop build of GOB exists in which single-player franchise mode runs entirely locally — engine, persistence, assets — with no server round-trips, packaged for distribution through Steam and direct download.

**Non-negotiables:**
1. **The Python engine is not rewritten.** It is re-housed. (Precedent: FM26 replaced its entire presentation layer with Unity but kept the proprietary simulation engine intact. The engine is the crown jewels; presentation is swappable.)
2. **The playtest does not wait for this.** The playtest ships now on the current online architecture, which is the *correct* architecture for that phase (revocable, observable, server-side iteration). This migration serves the paid launch build and the Next Fest demo only.
3. **The hard deadline is the Next Fest demo (late Dec / early Jan), not the March launch.** The demo should be built from the migrated standalone architecture — it is the launch build's public dress rehearsal.

---

## 1. Target architecture

```
┌─────────────────────────────────────────────────────┐
│                  Desktop app bundle                  │
│                                                      │
│  Existing web frontend (HTML/JS/Phaser)              │
│        │  same fetch() calls as today                │
│        ▼                                             │
│  Local FastAPI on loopback (127.0.0.1:<port>)        │
│        │                                             │
│  Python engine (Nuitka/Cython-compiled)              │
│        │                                             │
│  Persistence adapter ──► SQLite save file (.db)      │
│                                                      │
│  Bundled portrait assets (base 300 recruit set)      │
└──────────────────────┬──────────────────────────────┘
                       │ only for online features
                       ▼
        Remote backend (Railway, unchanged)
        auth · recruit packs · subscription ·
        community · leaderboards · PvP
```

**Key properties:**
- The frontend keeps calling the same REST endpoints; they resolve to loopback instead of Railway. The existing API surface *is* the engine interface — this is why no rewrite is needed.
- One franchise save = one SQLite file the user owns (portable, copyable, backupable — the OOTP-direct ownership feel, made literal; future door to save-sharing/community upload features).
- Online features route to the remote backend exactly as today. The split is at the endpoint level.

**Why SQLite (decision, closed):** Embedded, serverless, single-file, public domain, first-class JSON support (JSON1) so the Mongo document model ports without schema redesign. Bundling MongoDB locally is rejected (heavyweight server process, SSPL licensing, nobody ships this in desktop games). FM notably uses proprietary custom binary formats + in-RAM object DB instead — the product of 20 years of bespoke infrastructure and a staff to maintain it; SQLite delivers the same user-facing properties (single portable save, fast, offline) at zero infrastructure cost, and maps onto GOB's existing query-per-document access pattern where FM's load-world-into-RAM model would not.

**Why compile the engine (decision, closed):** PyInstaller-style bytecode bundling is trivially decompilable. Nuitka or Cython compilation to machine code raises the bar to native-binary levels — the same exposure OOTP/FM have accepted for decades. Accepted residual risk: no local build is crack-proof; the true moats are (a) the tuning/calibration knowledge behind the constants, not the code structure, and (b) the server-side revenue layer (packs, subscription) no decompiler reaches. Guard design docs and calibration data more carefully than the shipped binary.

---

## 2. Workstreams

Ordered so early items unblock later ones and are independently testable against the current cloud version.

### WS-1: Persistence adapter (START FIRST)
The audit's risk #10: `BackEnd/db.py` collections are imported directly throughout the backend, so there is no single boundary to swap.

- Define a repository/adapter interface covering every collection access the engine and franchise flows use.
- Implement **Mongo adapter** (wraps current behavior) and migrate all direct collection imports to go through it.
- **Validation gate:** current cloud product runs unchanged on the Mongo adapter. If this passes, nothing broke — pure refactor.
- Implement **SQLite adapter** (documents as JSON via JSON1; one DB file per franchise save).
- Adapter selected by runtime config (cloud → Mongo, desktop → SQLite).

*Why first:* self-contained, testable in production without risk, unlocks everything else, and can proceed in small protected-time increments while the playtest runs.

### WS-2: Engine localization
- Stand up the FastAPI app as a **local loopback service** launched by the desktop shell (or in-process bridge if simpler): same routes, local port.
- Strip/flag server-only concerns from the local profile: Sentry, GTM, email routes, admin routes, maintenance polling, community/leaderboard/auth routes (these stay remote — see WS-5 routing split).
- Compile engine + API with **Nuitka** (fallback: Cython; last resort: PyInstaller + PyArmor).
- **Validation gate:** a full franchise season — init game, turn-by-turn court play, timeouts/resume, box score, week advancement, training, recruiting, EOS — runs against localhost + SQLite with zero remote calls (verify with network monitor).

### WS-3: URL-state refactor (the audit §3 problem)
The query string is currently a cross-page state container and resume protocol (game IDs, lineups, clock/score, resume anchors). In a desktop shell this is fragile and unnecessary.

- Introduce a **client-side session state module** (single source of truth object, persisted to localStorage or the local API) that owns what the URL currently carries: identity pointers (`franchise_id`, `game_id`, `team_id`, `mode`), live game state, resume anchors, return-flow context.
- Refactor in dependency order, hotspots first (audit's multi-category files): `bootGame.js`, `gameScene.js`, `set-lineup.js`, `game-plan.js`, `timeoutNavigationHelper.js`, `box-score.js`, `common.js`, `franchise-command-center.js`.
- Keep URL params working as a **fallback read path** during transition (read state module first, URL second) so cloud playtest and desktop builds share frontend code throughout.
- **Use `StateTelemetry` as the migration checklist:** it already instruments URL reads/writes. Drive its logged URL-reads to zero (or fallback-only) page by page. That log is the definition of done for this workstream.
- Also in scope here: `api-config.js` gains a desktop profile (loopback base URL for game routes, remote base URL for online routes) replacing hostname sniffing, which currently has no defined desktop/`file://` mapping.

### WS-4: Desktop shell & packaging
- **Decision needed:** Electron vs Tauri. Electron = mature, heavier (~150MB+), Chromium bundled (Phaser behavior identical to today). Tauri = lighter, uses OS webview (test Phaser/audio/canvas behavior on WebView2 & WKWebView before committing). Default lean: **Electron** for lowest behavioral risk with a Phaser game; revisit only if bundle size proves painful.
- Shell responsibilities: launch/supervise the local engine process, port selection, splash while engine boots, save-file location (OS user-data dir), crash recovery, app menus, auto-update strategy (Steam handles updates for Steam builds; direct builds need an updater or manual downloads).
- Windows first (Steam's dominant platform), macOS second, Linux only if demand appears.

### WS-5: Online/offline seam & entitlement
- **Endpoint routing split:** game/franchise routes → local; auth, community, leaderboards, feedback, recruit-pack, subscription routes → remote. One routing table in the API config, not scattered conditionals.
- **Offline-first identity:** single-player must work with no account and no network (the OOTP-direct promise). A GOB account is required only to *link* online features (per `app_build_dynamics.md` §6 — the account bridge for pack redemption and subscription across both storefronts).
- Recruit-pack delivery to desktop: purchased packs download through authenticated remote calls and install into local assets/DB; base 300 portrait set ships in the bundle (no runtime R2 dependency for offline play).
- Graceful degradation: online panels (community highlights, leaderboards) render an offline state rather than blocking anything.

### WS-6: Build pipeline & distribution
- Reproducible build script: compile engine → bundle frontend + shell → installer artifacts.
- SteamPipe depot configuration; internal branch first; install and play via Steam client as a real tester (per original onboarding checklist).
- Direct-download variant of the same build (the "one standalone build, two storefronts" model).
- **Demo variant:** same pipeline with scope limits compiled in (per `app_build_dynamics.md` §3 — the Demo is permanent, so it is constrained: e.g., season cap/team cap). Build flag, not a fork.

---

## 3. Calendar (integrates with Steam_Strategy.md §6)

| Window | Playtest track (current architecture) | Migration track |
|---|---|---|
| **Aug** | Playtest Phase 1 live (gated); Coming Soon page live; founder sales open | WS-1 persistence adapter begun in protected time |
| **Sept** | Phase 1 feedback loop; server-side iteration | WS-1 complete + validated on cloud; WS-2 engine localization begins |
| **Oct** | Phase 2 (controlled-open); PMF metric readout | WS-2 first full-season local validation; WS-3 URL refactor begins (hotspot files) |
| **Nov** | Phase 2 continues; bug burn-down | WS-3 substantially done (StateTelemetry near-zero); WS-4 shell packaging; WS-5 seam/entitlement |
| **Dec** | Phase 3 (open stress test of *remote* backend for online-layer confidence) | WS-6 pipeline; **Demo variant built from migrated architecture**; register for Feb Next Fest |
| **Jan** | Final playtest wave runs the **standalone demo build** — the new architecture's shakedown with real users | Hardening from shakedown findings; Press Preview demo submission (~4 wks pre-fest) |
| **Feb** | — | **Next Fest** (demo = standalone architecture) |
| **Mar** | — | **Paid launch** |

**Solo-dev operating rule:** the migration gets *protected calendar time* (minimum viable: 2 fixed days/week untouchable by playtest firefighting). Playtest waves are sequenced to create quiet — gated Phase 1 is small and forgiving precisely so the migration track can spin up underneath it. Failure mode to guard against: playtest support consumes every week and December arrives with the migration 20% done.

**Slip valve:** if by ~Nov 15 WS-2/WS-3 are materially behind, the fallback is a Next Fest demo on the *current online architecture* (allowed — Steam permits online-only demos) with the standalone build landing for March launch instead. This trades away the demo-as-dress-rehearsal benefit and accepts a forever-free build with server cost; it is a fallback, not a plan. Decide deliberately at the Nov 15 checkpoint, not by drift.

---

## 4. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Playtest workload starves migration | High (solo dev) | Protected time rule; Nov 15 checkpoint; slip valve above |
| Engine assumes Mongo-specific behavior beyond adapter seam (e.g. ObjectId semantics, implicit ordering) | Medium | WS-1 validation gate on cloud catches most; full-season local sim in WS-2 catches the rest |
| Nuitka compilation issues with dependency set | Medium | Spike early in WS-2 (compile hello-world FastAPI+engine slice first); fallbacks identified |
| Phaser/audio quirks in non-Chromium webview | Medium if Tauri | Default to Electron; only evaluate Tauri with explicit testing |
| URL fallback path hides incomplete refactor | Medium | StateTelemetry zero-read definition of done; disable fallback in desktop debug builds |
| Local engine perf differs from server (user hardware variance) | Low–Medium | Full-season sim benchmark in WS-2 on a low-end reference machine |
| Scope creep: migrating online features that should stay remote | Medium | WS-5 routing table is the contract; anything not in the local list stays remote |

---

## 5. Open decisions

1. **Electron vs Tauri** — default Electron; close after WS-4 spike.
2. **Loopback service vs in-process bridge** — default loopback (zero frontend changes); close during WS-2.
3. **Nuitka vs Cython** — close after WS-2 compilation spike.
4. **Demo scope limits** — season cap vs team cap vs time cap; decide with Demo build (Dec), informed by playtest engagement data.
5. **macOS timing** — with March launch or post-launch.
6. **Direct-build auto-update mechanism** — updater vs manual; can defer past launch.

---

## 6. Definition of done (per milestone)

- **WS-1:** cloud product runs on Mongo adapter with zero behavior change; SQLite adapter passes the same engine test suite.
- **WS-2:** full franchise season completes locally, offline, network monitor showing zero remote calls; sim performance within acceptable range on reference low-end hardware.
- **WS-3:** StateTelemetry reports zero primary URL reads across the full game flow; desktop build runs with URL fallback disabled.
- **WS-4:** installable build on a clean Windows machine with no dev tooling; cold start to playable under acceptable threshold.
- **WS-5:** fresh install plays a full offline season with no account; account link + pack purchase installs content into local DB.
- **WS-6:** same pipeline emits Steam depot build, direct installer, and scope-limited demo from one source tree; Steam-installed build passes a real-player test session.
