# Desktop Migration Work Plan — GOB

**Purpose:** Practical work plan for migrating GOB from an online-only web app to the hybrid model: a standalone desktop build for single-player franchise play, with the online layer (accounts, community, recruit packs, subscription, PvP) remaining on remote infrastructure.

**Canonical companions:**
- [`Steam_Strategy.md`](../12_GTM/Steam_Strategy.md) — release and promotion calendar this migration must serve.
- [`gob-asset-architecture.md`](./gob-asset-architecture.md) — asset storage and delivery rules. WS-7 and WS-8 are this document's desktop consequences.
- [`tournament_id_sunset.md`](./tournament_id_sunset.md) — sequenced as WS-0 below.

**Last updated:** 14 September 2026 — full revision against `develop` @ `801aa5f`. Supersedes the August draft.
**Audit of record:** [`desktop_migration_plan_audit.md`](./desktop_migration_plan_audit.md) — the code-grounded evidence behind this revision. Every count cited here comes from that audit.

---

## 0. Objective and non-negotiables

**Objective:** By late December 2026, a standalone desktop build of GOB exists in which local franchise mode runs entirely on the user's machine — engine, persistence, assets, portrait generation — with no server round-trips, packaged for distribution through Steam and direct download.

**Non-negotiables:**
1. **The Python engine is not rewritten.** It is re-housed. (Precedent: FM26 replaced its entire presentation layer with Unity but kept the proprietary simulation engine intact. The engine is the crown jewels; presentation is swappable.)
2. **The web build must keep working, unchanged, throughout.** Online PvP franchise and hosted PvE both live there. Any refactor that improves the desktop build at the web build's expense is rejected — this is the rule that reshaped WS-3.
3. **The hard deadline is the January beta, not the March launch.** Alpha testers move onto the desktop build in January. That is the real shakedown; Next Fest in February is its public consequence.

---

## 1. Product model (decided 14 Sept 2026)

### 1.1 Franchise runtime is chosen at creation and never changes

Every franchise is created as one of two kinds:

| | **Local franchise** | **Hosted franchise** |
|---|---|---|
| Lives in | SQLite, in the user's save directory | Mongo, on GOB servers |
| Requires | Base game purchase | Base game purchase **+** active subscription |
| Runs on | Local loopback engine | Remote engine (Railway) |
| Leaderboard eligible | No | Yes |
| Community highlights | Read-only (see §1.3) | Full participation |
| Works offline | Yes | No |

There is no franchise type that lives in both places. A user may hold any number of each.

### 1.2 The integrity rule — why the line exists

> **A franchise is leaderboard-eligible if and only if its bytes have never been under the user's control.**

This is the single rule from which everything else in §1 follows.

**Local → hosted is permanently closed.** A local save is a file the user owns — that is a deliberate product feature (§3), not a weakness to be patched. There is no way to distinguish an untouched save from one edited in a SQLite browser, and signing does not help because the user controls the machine doing the signing. A leaderboard that accepts unvalidatable input is decorative. This direction is not a feature that was deferred; it is a thing that cannot exist.

**Hosted → local export is safe but deferred.** Moving from a trusted store to an untrusted one raises no integrity concern, because nothing downstream ever trusts the local copy again. Whether to build it is a product decision (§9, Open Decision 4), not an architectural one.

**If export is built, three properties are mandatory:**
- It is a **copy, not a move.** The hosted franchise survives intact, so a lapsed subscriber who returns can resume it. The two timelines fork at export and never rejoin — offline progress made in the interim cannot come back.
- The **one-way door is explicit at the click**, not discovered later. Use the pattern already established in `FrontEnd/static/js/team-builder/gate.js`, which gates capped-vs-uncapped as "the only irreversible decision."
- The exported save carries a **flag marking it as an offline copy**, surfaced in the UI, so a user two years on is not confused about why this franchise cannot join a league.

**What this costs today: one sentence in WS-1.** Franchise-scoped read and write must be a first-class operation on the adapter interface, not something reached through. A franchise is already a bounded document set keyed on `franchise_id`, so this is free to specify now and annoying to retrofit later. It preserves the option at zero price and commits to nothing.

### 1.3 Subscription and community packaging

The subscription grants the ability to **create and run hosted franchises**, which is what makes leaderboard and real-time community participation possible. `BackEnd/constants/billing_catalog.py` already defines `ONLINE_COMMUNITY` as a capability and `PurchaseSource.STEAM` as an acquisition source; `BackEnd/services/entitlements.py` is already the single choke point, currently returning yes to everything behind `BILLING_GATING_ENABLED`. Turning this on is a change to that function body, not new plumbing.

**Proposed, not yet locked:** split `ONLINE_COMMUNITY` into read and participate. A base-game owner who has not subscribed should see leaderboards and community highlights **read-only** rather than an empty panel. An empty panel reads as broken, not as a locked feature, and it wastes a screen that is the subscription's most natural sales surface. (§9, Open Decision 5.)

### 1.4 Build and distribution contract

The files always download to the user's computer. Revocation means refusing to authorize a build, not deleting local files.

| Build profile | Steam gate | Backend gate | Offline standalone | Product job |
|---|---:|---:|---:|---|
| **Web alpha (current)** | No | Yes | No | PMF validation on live infrastructure; the current state of the world |
| January beta (desktop) | Optional | Yes | Yes | Shakedown of the migrated architecture with existing alpha testers |
| Next Fest Demo | Steam distribution | No | Yes | Permanent public acquisition artifact with deliberate scope limits |
| Paid Steam | No required DRM gate | No for base game | Yes | Owned product that continues running offline |
| Paid direct | No | No for base game | Yes | Same owned product, delivered outside Steam |

The paid base game is standalone and requires neither an account nor a network connection for local franchise play. Steam and direct customers receive the same offline runtime contract; the storefront changes delivery and purchase verification only. Steam's optional DRM wrapper remains a separate future choice and is not a dependency of this plan.

**The server-side moat is the online layer** — hosted franchises, subscriptions, recruit packs, live PvP, leaderboards, community — not a phone-home requirement in the base game.

**Demo scope:** the Demo is a permanent public artifact, not a revocable cohort, so it receives an intentional scope limit (season, team, or time cap). It is emitted from the same standalone pipeline via a build flag, never a fork. Clean rule: **revoke a cohort; constrain the Demo.**

---

## 2. Target architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Desktop app bundle                     │
│                                                           │
│  Existing frontend (HTML/JS/Phaser) — same fetch() calls  │
│        │                                                  │
│        ▼                                                  │
│  FranchiseContext ──► runtime: local | hosted             │
│        │                                                  │
│        ├── local ──► Local FastAPI on loopback (127.0.0.1)│
│        │              Python engine (Nuitka-compiled)     │
│        │              Persistence adapter ──► SQLite (.db)│
│        │              Object store adapter ──► save dir   │
│        │              Portrait generation (Pillow)        │
│        │                                                  │
│        └── hosted ─────────────────┐                      │
└────────────────────────────────────┼──────────────────────┘
                                     │  also: auth, billing,
                                     ▼  packs, community
                    Remote backend (Railway, unchanged)
                    Mongo · R2 · auth · subscription · PvP
```

**Key properties:**

- **The frontend keeps calling the same REST endpoints.** They resolve to loopback or Railway depending on context. The existing API surface *is* the engine interface — this is why no rewrite is needed.
- **Routing is per-franchise, not just per-route-category.** This is the sharpest consequence of §1.1 and the most common thing to get wrong. Franchise A may be local while franchise B is hosted, in the same session, for the same user. `FranchiseContext` therefore carries a `runtime` field alongside `franchise_id`, and `api-config` resolves the base URL from it. Route category still decides the *other* axis: auth, billing, and community are always remote regardless of franchise runtime.
- **One local franchise = one SQLite file the user owns** — portable, copyable, backupable. The OOTP ownership feel, made literal.
- **The downloaded app is the client for hosted franchises too.** A subscriber plays their hosted franchise through the same installed app with the franchise routes pointed at Railway. No separate web franchise client is required to deliver hosted PvE — the routing seam is the whole mechanism.

**Why SQLite (closed):** Embedded, serverless, single-file, public domain, first-class JSON support (JSON1) so the Mongo document model ports without schema redesign. Bundling MongoDB locally is rejected — heavyweight server process, SSPL licensing, nobody ships this in desktop games. FM uses proprietary binary formats and an in-RAM object DB, the product of 20 years of bespoke infrastructure and a staff to maintain it; SQLite delivers the same user-facing properties at zero infrastructure cost and maps onto GOB's existing query-per-document access pattern where FM's load-world-into-RAM model would not.

**Why compile the engine (closed):** PyInstaller-style bytecode bundling is trivially decompilable. Nuitka or Cython compilation to machine code raises the bar to native-binary levels — the same exposure OOTP and FM have accepted for decades. Accepted residual risk: no local build is crack-proof. The true moats are (a) the tuning and calibration knowledge behind the constants, not the code structure, and (b) the server-side revenue layer no decompiler reaches. Guard design docs and calibration data more carefully than the shipped binary.

---

## 3. Where the work actually stands (14 Sept 2026)

Stated plainly, because the August draft's calendar assumed progress that did not happen: **WS-1 through WS-6 are unstarted.** Not behind — unstarted.

| | Evidence |
|---|---|
| No persistence adapter | `find` for `*adapter*`, `*repositor*`, `*persistence*`, `*sqlite*` in `BackEnd/` returns nothing |
| No engine localization | `Nuitka` / `Cython` / `PyInstaller` appear nowhere in `requirements.txt`, `setup.cfg`, `MANIFEST.in` |
| No shell | No Electron, no Tauri, no forge config. `package.json` has one devDependency: `@playwright/test` |
| No routing split | `api-config.js` resolves a single base URL by hostname sniffing |

**Three things are better than the August draft assumed, and they are why this is still achievable:**

1. **`API_CONFIG` adoption is near-total** — 99 files route through it, only 2 hardcode a URL (`adminGuard.js`, `sentryInit.js`, both server-only concerns excluded from the desktop profile anyway). The routing seam is a days-not-weeks task.
2. **`entitlements.py` already exists** as the capability choke point, with the vocabulary §1.3 needs already defined.
3. **The validation tooling for every gate below already exists** — 337 Python test files, 28 Playwright specs, `scripts/season_advance_harness.py`, `scripts/perf_sim_baseline.py`. This is the strongest argument that WS-1 is genuinely low-risk rather than merely large.

**One thing is worse:** the asset payload and the portrait pipeline (WS-7, WS-8) are launch blockers that the August draft did not contain at all.

---

## 4. Workstreams

Ordered so early items unblock later ones and each is independently testable against the live web build.

### WS-0: Complete the `tournament_id` sunset — *do first, it is scope removal*

Phases 0–2A are already done and the standalone router is unmounted (see `tournament_id_sunset.md`). Finishing it removes **~29 URL call sites** and the `mode === "tournament"` branches **before WS-3 has to migrate them**.

Constraint from that doc, restated because it is easy to violate: **franchise tournament weeks must keep working.** They are a separate system keyed on `franchise_id`, franchise week state, `tournament_schedule`, and `tournament_context`. They do not require the legacy standalone `tournament_id`.

### WS-5a: Routing seam — *promoted to first big move*

Split out of the old WS-5 because it is cheap, unblocks WS-2, and proves the local/remote split before anything depends on it.

- Replace hostname sniffing in `api-config.js` with an explicit **routing table**: one axis by route category (auth, billing, community, admin → always remote), one axis by franchise runtime (§2).
- Add the desktop profile: loopback base URL for local-franchise routes, remote base URL for everything else.
- Clean up the 2 hardcoded-URL stragglers.
- **Gate:** the live web build runs unchanged through the new table; a stub desktop profile resolves local routes to loopback.

### WS-1: Persistence adapter — *the big rock*

`BackEnd/db.py` exposes 25 collection handles (lines 181–252) imported directly by **69 non-test files** (`BackEnd/utils` 32, `BackEnd/api` 15, `BackEnd/models` 5, `BackEnd/tournament` 5, plus engine and practice_squad), and ~40 scripts and ~45 tests. There is no single boundary to swap.

- Define a repository/adapter interface covering every collection access the engine and franchise flows use.
- **Franchise-scoped read and write are first-class operations** on that interface (§1.2).
- **Preserve `db.py`'s production access guard** — `ProdAccessBlocked`, `ProdWriteBlocked`, `GOB_DB_ACCESS`, `_ReadOnlyCollection`. The adapter must express this, not bypass it. Losing it silently is the most likely way this refactor causes real damage.
- Runtime selection extends `BackEnd/env_config.py`; do not add a parallel mechanism.
- Implement the **Mongo adapter** first and migrate all direct imports onto it.
- **Gate 1:** the live web product runs unchanged on the Mongo adapter. If this passes, nothing broke — it is a pure refactor.
- Implement the **SQLite adapter** (documents as JSON via JSON1; one DB file per local franchise).
- **Gate 2:** SQLite adapter passes the same engine test suite.

**Collection classification:**

| Local (in the save file) | Remote only |
|---|---|
| `players`, `teams`, `games`, `plays`, `defenses` | `users`, `password_reset_tokens` |
| `franchises`, `franchise_state`, `franchise_team_data` | `alpha_otps`, `access_code_requests` |
| `franchise_players_data`, `franchise_recruits_data` | `alpha_feedback`, `community_highlights` |
| `training_sessions`, `press_conference_sessions` | `around_the_league`, `stripe_events` |
| `fcp_skeletons`, `hct_skeletons`, `tournaments` | `eog_band_log` — see below |

`eog_band_log` is EOG band instrumentation with a 180-day TTL (`db.py:376`), ~36,600 rows / ~13 MiB per franchise-season. Writing that into a user's save is pure cost to them. **Decision: disabled in desktop release builds, enabled in the January beta build** so the beta still produces calibration data.

### WS-8: Local object store and portrait painting — *its own workstream*

Not a small adapter. It contains a local object store, two paint paths, a bundled kit library, three compiled numeric dependencies, a bundled font, and a resolution decision that moves both size and CPU by an order of magnitude.

**What does and does not get painted.** The base league is *not* in the paint pipeline: `player_image_routes.py:91` — *"original/universal players carry no image_id"* — so the 128 base rosters ship as finished static portraits. Painting applies only to **recruits who sign, walk-ons promoted onto a roster, and Team Builder players.** This bounds the runtime work to a trickle during recruiting weeks rather than a cliff at franchise creation.

**Two paint operations, both needed offline** (`BackEnd/services/recruit_image.py`):
- `make_white_master(kit)` — un-signed recruit display portrait, no recolor.
- `make_signed_master(kit, mask, primary, secondary, wordmark)` — team recolor plus mascot wordmark stamp.

**The cross-franchise cache must be replicated locally.** `BackEnd/utils/uniform_archive.py` keys the paint by what determines the pixels — `uniforms/<image_id>__<color_key>.png`, where `color_key` is a SHA-256 of normalized primary, secondary and mascot. `player_id` is deliberately **not** an input: the legacy per-player scheme repainted byte-identical images per user forever, at ~1 s CPU and 10.5 MB each. **The local store must use the same keying.** A naive per-player scheme reintroduces exactly the bug this module was written to kill, on far weaker hardware. Colour normalization (`_norm_color`, `_norm_mascot`) comes along with it.

**Measured inventory (14 Sept 2026):**

| | Count | Note |
|---|---:|---|
| Portrait `image_id` library | **521** | `set_0001` 300 + `builder_set_0001` 150 + walk-ons 71 |
| Base league team looks | 128 | `<image_id>__<color_key>` cross product = 66,688 — **not bakeable** |
| Master resolution | 3530×3412 RGBA PNG | ~10.5 MB each; Cloudflare shrinks to 128/256/512 for display |
| Base league static portraits | 98 files / 443 MB | avg 4.6 MB — WS-7's target, not WS-8's |

**The resolution decision (Open Decision 9) is the highest-leverage question here.** The web stores print-resolution masters because Cloudflare Image Transformations resize them on the fly. **The desktop build has no Cloudflare.** Painting and storing at display resolution (512px) instead of 3530px is ~1/47th the pixels: a stored portrait goes from ~10.5 MB to perhaps 30–80 KB as WebP, and the paint itself gets dramatically cheaper — which is what relieves the §10.1 CPU pressure of painting while a live game runs.

**Scope:**
- Local object store behind the `r2_images` interface (`get` / `put` / `exists` / `is_configured`), writing to the save directory, keyed by `uniform_archive`.
- Bundle the **521 kits + masks** at the chosen paint resolution. This is WS-8's bundle floor — measure it, the kits live in R2 and are not in the repo.
- Bundle **`LiberationSans-Bold.ttf`** for the wordmark stamp. `_find_wm_font()` falls back to `/usr/share/fonts/truetype/liberation/` which will not exist on a player's machine — the bundled copy must resolve first.
- **Replace the silent `is_configured()` skip with a real failure path in the desktop profile.** Today an unconfigured store logs a warning and returns a summary; a desktop build hitting that path ships missing portraits with nothing the user can act on.
- **Local GC.** `collect_franchise_master_keys` / `delete_master_keys` exist because *"a league-wide franchise can carry hundreds of walk-on masters."* The local store needs the equivalent, or a long save accretes orphaned portraits in the user's save directory.
- **Measure paint cost at the chosen resolution**, on low-end hardware, concurrently with a live game (§10.1).

**Dependency warning — heavier than Pillow.** `recolor_and_stamp` and `_finish_rgba` import **NumPy and SciPy** (`scipy.ndimage` for binary erosion and gaussian filter) alongside Pillow. SciPy is a large, heavily-compiled scientific package and a materially harder Nuitka target. If it will not compile, the fallbacks are unattractive: rewrite the alpha-edge cleanup without `ndimage`, or ship part of the engine uncompiled. **This is the third question for the WS-2 spike.**

**Good news that keeps this tractable:** the paint is a **deterministic recolor with no AI**, and there are **no file upload endpoints anywhere in the API** (`UploadFile` / multipart: zero hits) — Team Builder collects only name, mascot, primary and secondary. Everything is derivable, so bundled kits produce byte-identical output offline with nothing to sync, and `gob-asset-architecture.md` §4.1's offline degradation does not bite today. **Keep it that way as long as possible** — the day logo upload ships, offline play gets a permanent asterisk.

### WS-2: Engine localization

- Stand up the FastAPI app as a **local loopback service** launched by the shell. Note the app is assembled in **`BackEnd/api/api.py:486–501`**, not `BackEnd/main.py` (which has no routes and no app factory).
- Resolve **`BackEnd/flask_app.py`** — it exists alongside the FastAPI app and imports `db` directly. Establish whether it is live and needs a desktop story, or is dead weight to delete before migration.
- Strip from the local profile: Sentry, GTM, email, admin, maintenance polling (4 frontend files reference `Sentry`/`gtm`/`dataLayer`, plus `sentry-sdk[fastapi]`; roughly half a day).
- **Offline identity — decision: inject a local principal.** There are **91 route-level auth dependencies, 48 of them in `franchise_routes.py`**, the router that must run locally with no account. The desktop profile injects a synthetic local user via a dependency override in the app factory — roughly one file, zero changes to 48 call sites, and auth code stays uniform across both builds.
- Compile with **Nuitka** (fallback Cython; last resort PyInstaller + PyArmor).
- **Spike the compile early, and spike the process pool inside it.** Two things must be proven against a compiled binary, in priority order:
  - **The spawn-based process pool must survive compilation.** `cpu_week_pool.py` spawns workers, which means the child re-executes the binary and must enter worker mode rather than launching a second copy of the app. This is a known hard problem for frozen/compiled Python. **If it fails, a 63-game week goes from 34.6 s pooled to ~225 s single-core** — a product-quality cliff, not a regression. This is the highest-value thing to learn in September.
  - **SciPy, NumPy and Pillow** — the paint stack (`recolor_and_stamp`, `_finish_rgba`). SciPy is the hard one: large, heavily compiled, and a materially harder Nuitka target than Pillow. Fallbacks are unattractive (rewrite the alpha-edge cleanup without `ndimage`, or ship part of the engine uncompiled), so learn this in September.
  - **Phase A under a live game on a 4-core reference machine** — find the worker count that keeps the frame rate clean (§10.1). That number is the desktop default.
- **Gate:** a full franchise season — init, turn-by-turn court play, timeouts and resume, box score, week advancement, training, recruiting, EOS — runs against loopback + SQLite with **zero remote calls**, verified by network monitor, at acceptable performance on a low-end reference machine.

### WS-3: Franchise context provider — *reframed; runs as a continuous grind*

**The August draft had this wrong and it was the most expensive error in the document.** It proposed eliminating URL state. URL-as-identity is not drift — it is an enforced invariant, written down in `franchiseLocalStorage.js` ("Identity: URL `?franchise_id=` only — never store a bare 'current' franchise id") and encoded as a machine-checkable contract in `stateTelemetry.js`. It exists because the app is **80 HTML pages with 133 hard `window.location.href` navigations**, and the only in-memory store (`gameStore.js`, 151 lines) is destroyed on every navigation. In an MPA, the URL is the only thing that survives a page load. Removing it without replacement is a regression, and it would break multi-tab multi-franchise in the web build — which non-negotiable #2 forbids.

**Introduce a context provider with two backends:**

```
FranchiseContext  — single read/write API for the whole frontend
   ├── UrlContextProvider      → web build. Query-string backed. Behavior bit-identical to today.
   └── SessionContextProvider  → desktop build. localStorage-backed singleton.
```

`SessionContextProvider` is **trivial** because desktop is one franchise per window (decided 14 Sept): no namespacing, no per-window isolation — the save file is the namespace. It must still be *persisted* rather than in-memory, because Electron performs the same 133 hard navigations.

`FranchiseContext` carries `runtime` (`local` | `hosted`) alongside `franchise_id`, per §2.

**Scope, measured:** 312 call sites across 76 files, ~40 distinct params. By frequency: `franchise_id` (65), `game_id` (48), `team_id` (47), `mode` (45), `tournament_id` (29 — removed by WS-0), `my_team` (29), `resume_from_timeout` (25), `user_team_id` (24), `home_id`/`away_id` (22 each), then a long tail.

**Corrected hotspot order** (the August draft's list was stale; six of the top ten were missing):

| File | Sites | | File | Sites |
|---|---:|---|---|---:|
| `franchise-command-center.js` | 27 | | `franchise-select-team.js` | 10 |
| `set-lineup.js` | 21 | | `court.html` | 10 |
| `js/phaser/bootGame.js` | 20 | | `box-score.js` | 10 |
| `js/phaser/gameScene.js` | 17 | | `team-builder.js` | 9 |
| `training.js` | 15 | | `js/phaser/utils/gameCompletionPopup.js` | 7 |
| `tournament.js` | 15 | | `timeoutNavigationHelper.js`, `common.js`, `authBarInit.js` | 6 each |
| `game-plan.js` | 10 | | `recruiting-common.js` | 5 |

**Definition of done:** zero direct `URLSearchParams` / `location.search` / `searchParams` access **outside the provider**. Grep-checkable, enforceable in CI, covers 100% of the surface. *Not* "zero URL reads" — the web build must keep them.

**Do not use `StateTelemetry` as the gate.** It is `enabled: false` in source (line 19), its `STATE_CONTRACT` declares `url` the only legal source for the four identity keys — so enabling it would flag desktop-correct behavior as a violation — and it is referenced in 12 of the 76 relevant files. Either rewrite its contract to name `FranchiseContext` and keep it as runtime violation logging during the refactor, or retire it. The grep gate above is the gate either way.

**This workstream is incrementally shippable to the live web build, file by file, with no flag day.** That is why it runs as a continuous grind alongside the big rocks rather than as a blocking phase.

### WS-7: Asset payload — *new; runs as a continuous grind*

**The repo tree is 1.1 GB of images, but the three big directories are three different problems.** Measured 14 Sept 2026:

| Directory | Size | Serves from | Desktop problem |
|---|---:|---|---|
| `images/players` | 443 MB / **98 files, avg 4.6 MB** | **R2** via `assets.geekedoutgames.com` | Local copies are a dev fallback — likely **deletable**, definitely convertible |
| `images/teams` | 377 MB | **local static only** | No remote path, no seam. Ships in the bundle or not at all |
| `images/coaches` | 207 MB | **local static only** | Same |
| `static/sounds` | **53.8 MB (131 LFS files)** | local static only | Ships in the bundle; 64 uncompressed WAVs |
| Loading GIFs + marketing art | ~50 MB | local static | Should not be in a game bundle at all |

**Players are the easy case and already have the seam.** `api-config.js` carries `PLAYER_IMAGE_REMOTE_BASE` (the R2 custom domain) and `usePlayerImageRemote()` — localhost serves local static, staging and prod serve from R2 with **Cloudflare Image Transformations** resizing and converting to AVIF/WebP on the fly at named sizes (`thumb` 128, `card` 256, `modal` 512, `full`). So production does not ship those 443 MB. **Confirm the local set is genuinely dev-only, then delete rather than convert** — deleting always beats compressing. At display resolution those 98 portraits are a few MB total.

**Teams and coaches are the real problem and have no seam.** Verified: the remote path exists *only* for players — every `usePlayerImageRemote()` call site in `api-config.js` is a player function. Team images are hardcoded `images/teams/...` paths across **31 files**, coaches across **6**, with no config layer and no remote fallback. 584 MB, compression the only lever.

> **Sequencing note worth a decision:** `gob-asset-architecture.md` §5 already argues for moving static league assets to R2 for the web. Building that seam for teams and coaches **before** the desktop build means building it once and getting both. Doing it after means building it twice.

**Audio ships in the bundle and the build must fetch it.** `.gitattributes` puts `FrontEnd/static/sounds/*.{mp3,wav,ogg,mp4}` on Git LFS — 131 files, **53.8 MB real** (66 mp3, 64 wav, 1 mp4). LFS is confined to this one directory; nothing else in the tree is a pointer. The 64 uncompressed WAVs are an obvious conversion target.

**Scope:** (1) confirm and delete the redundant player set; (2) audit game-required vs web-marketing-only across the rest; (3) convert teams, coaches and remaining assets to WebP/AVIF at display resolution — on these averages, 90%+ reduction is routine; (4) convert WAV SFX; (5) hold an installer size budget (§9, Open Decision 1).

**Hard exclusion — anything the animation system takes measurements from.** Court art, player sprites, and any asset whose dimensions feed coordinate math are **out of scope for compression**. A sprite sheet that changes dimensions during a WebP conversion breaks coordinate math and presents as a UESS regression, which is an expensive thing to debug from the wrong end. If such an asset must be touched, it is re-verified against the animation harness in the same PR.

**Must precede WS-4 packaging.** It touches image paths across the frontend and is far cheaper before packaging than after. It is also the best filler work when other tracks are blocked.

### WS-4: Desktop shell and packaging

- **Default: Electron.** Chromium bundled means Phaser behavior is identical to today — lowest behavioral risk for a Phaser game. Tauri is lighter but uses the OS webview; only evaluate it with explicit WebView2/WKWebView testing of Phaser, audio, and canvas. Revisit only if bundle size proves painful after WS-7.
- Shell responsibilities: launch and supervise the local engine process, port selection, splash while the engine boots, save-file location in the OS user-data dir, crash recovery, app menus, auto-update.
- Windows first. macOS timing is Open Decision 3.

### WS-6: Build pipeline and distribution

- **`git lfs pull` is a mandatory build step.** All 131 audio files are LFS pointers. A clean CI checkout without it produces a build that ships 131 text files named `.wav` — the game boots, animations run, and every sound silently fails. This passes automated tests and gets found by a tester. Same trap applies to any spike or agent working from a fresh clone.
- Reproducible build script: compile engine → bundle frontend, shell, and assets → installer artifacts.
- SteamPipe depot configuration; internal branch first; install and play through the Steam client as a real tester.
- Direct-download variant from the same build — one standalone build, two storefronts.
- **Demo variant:** same pipeline with the §1.4 scope limit compiled in. Build flag, never a fork.

---

## 5. Calendar

Two tracks, because solo-dev reality is that grind work fills the gaps around big rocks rather than queuing behind them.

| Window | Big rock | Continuous grind |
|---|---|---|
| **Sep 15 – Oct 3** | WS-0 `tournament_id` sunset; WS-5a routing seam; **WS-2 compile spike early** (Nuitka + Pillow) | WS-3 build `FranchiseContext`, migrate top-5 hotspots |
| **Oct 6 – Nov 7** | **WS-1 Mongo adapter + 69-file migration → Gate 1 on live web** | WS-3 grind; WS-7 asset audit + conversion |
| **Nov 10 – Nov 28** | WS-1 SQLite adapter → Gate 2; WS-8 local object store + portrait paint | WS-3 grind; WS-7 conversion completes |
| **Dec 1 – Dec 19** | WS-2 engine localization → full offline season gate; WS-4 shell; WS-6 pipeline + Demo variant | WS-3 finishes; grep gate green |
| **January** | **Beta: alpha testers move onto the desktop build.** Hardening from findings. Press Preview demo submission (~4 wks pre-fest) | |
| **February** | **Next Fest** — demo built from migrated architecture | |
| **March** | **Paid launch** | |

**Solo-dev operating rule:** the migration gets *protected calendar time* — minimum viable, 2 fixed days per week untouchable by alpha firefighting. The failure mode to guard against is that alpha support consumes every week and December arrives with the migration 20% done. As of this revision that failure mode is **live, not hypothetical**: roughly six weeks of assumed August–September progress did not happen.

**Nov 15 checkpoint.** The gate is binary and specific: **is WS-1 Gate 1 green on the live web build, and is the Nuitka+Pillow compile spike green?** If either is no, take the slip valve deliberately at the checkpoint rather than by drift.

**Slip valve.** If the checkpoint fails, the fallback is a January beta and a Next Fest demo on the *current online architecture* (Steam permits online-only demos), with the standalone build landing for March launch instead. This trades away the demo-as-dress-rehearsal benefit and accepts a forever-free build with server cost. It is a fallback, not a plan.

---

## 6. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Alpha workload starves migration | **High** (solo dev; already realized once) | Protected time rule; Nov 15 checkpoint; slip valve |
| WS-1's 69-file migration silently drops the prod access guard | Medium | Guard expressed in the adapter interface as an explicit requirement; `test_db_read_only_proxy.py` extended to cover the adapter |
| **Spawn-based process pool does not survive Nuitka compilation** | **Medium–High** | **Spiked in September as the first WS-2 task.** Failure means ~225 s weeks instead of 34.6 s. Fallbacks: worker-mode entry point, or a separate uncompiled engine launcher |
| **Phase A CPU sims degrade the live animated game on a player's machine** | **High if unaddressed** | §10.1 pool-sizing policy: live game is the priority workload, phase A sized from cores minus a renderer reserve and allowed to spill into phase B. The default of 8 is a Railway number, not a laptop number. Measured in the WS-2 spike |
| **Nuitka fails on SciPy** (or NumPy/Pillow) | **Medium** | Spiked in September. SciPy is the likeliest failure of the three. Fallback: drop `ndimage` from the alpha-edge cleanup, or ship the paint service uncompiled |
| Engine assumes Mongo-specific behavior beyond the seam (ObjectId semantics, implicit ordering) | Medium | Gate 1 on live cloud catches most; full-season local sim catches the rest |
| WS-3 grind stalls at ~70% and the desktop build ships with mixed state paths | Medium | Grep gate in CI from day one, failing on new direct URL access |
| Asset payload discovered late, forcing a rushed conversion after packaging | Medium | WS-7 runs Oct–Nov as grind work, before WS-4 |
| Local portrait render too slow on low-end hardware | Low–Medium | Measured in WS-8; disposable cache if slow — architecture unchanged |
| Per-franchise routing (§2) implemented as per-build routing | **Medium** | Single routing table in WS-5a carries both axes from the start |
| Scope creep: migrating online features that should stay remote | Medium | The §4 WS-1 collection table and the WS-5a routing table are the contract |

---

## 7. Definition of done

### 7.1 Per workstream

- **WS-0:** standalone tournament surface retired; franchise tournament weeks unaffected; ~29 URL sites gone.
- **WS-5a:** live web build runs unchanged through the routing table; desktop profile resolves local routes to loopback; both routing axes present.
- **WS-1:** live web product runs on the Mongo adapter with zero behavior change; SQLite adapter passes the same engine test suite; prod access guard intact; franchise-scoped read/write is a first-class interface operation.
- **WS-8:** local object store passes the `r2_images` interface contract; a full roster paints offline within the measured perf budget; unconfigured store fails loudly.
- **WS-2:** full franchise season completes locally and offline, network monitor showing zero remote calls; performance acceptable on low-end reference hardware.
- **WS-3:** zero direct `URLSearchParams` / `location.search` access outside the provider, enforced in CI; web build behavior unchanged.
- **WS-7:** installer within budget; no marketing-only assets in the bundle.
- **WS-4:** installable build on a clean Windows machine with no dev tooling; cold start to playable under threshold.
- **WS-6:** one pipeline emits Steam depot build, direct installer, and scope-limited demo from one source tree; the Steam-installed build passes a real-player session.

### 7.2 Per build profile

| Profile | Acceptance gate |
|---|---|
| January beta | Alpha testers complete full seasons on the desktop build; local and hosted franchises both reachable from the same install. **No tester at or above minimum spec reports animation degradation during phase A** (§10.1) — solicited explicitly, not waited for, since testers under-report stutter as "it felt a bit off" |
| Demo | Produced from the common pipeline with its scope limit; installs cleanly; depends on no credentials |
| Paid Steam | Base franchise mode completes a full offline season after Steam install; hosted franchises require subscription only when created |
| Paid direct | Same contracts from the direct installer; update mechanism per Open Decision 6 |

---

## 8. Closed decisions

1. **SQLite for local saves** — §2.
2. **Compile the engine (Nuitka, fallback Cython)** — §2.
3. **Franchise runtime chosen at creation; never changes** — §1.1.
4. **Local → hosted is permanently closed** — §1.2.
5. **One franchise per window on desktop** — simplifies `SessionContextProvider` (WS-3).
6. **Team Builder is in scope for offline play** — makes WS-8 mandatory.
7. **Hosted PvE is delivered through the downloaded app**, not a separate web client — §2.
8. **Electron by default** — §WS-4, revisit only after WS-7.
9. **Offline identity via injected local principal**, not dependency stripping — §WS-2.
10. **`eog_band_log`: off in release builds, on in the January beta** — §WS-1.
11. **WS-3 gate is grep-based, not `StateTelemetry`** — §WS-3.
12. **Animation quality outranks phase A throughput on constrained hardware** (decided 14 Sept 2026). On a weak machine, phase A gets fewer workers and spills into phase B. The user may wait after their game; they must not watch a degraded one. The tradeoff is chosen; **the worker count that delivers it is not yet measured** — WS-2 spike sets it, the §7.2 beta gate confirms it.

---

## 9. Open decisions

1. **Installer size budget.** Everything in WS-7 keys off this number, and it is a Next Fest conversion decision as much as an engineering one. Suggested starting target: **under 500 MB installed** for the paid build, **under 250 MB** for the demo. *Needed before WS-7 begins (early Oct).*
2. **Steam playtest — still happening, or folded into the January beta?** §1.4's profile table and §5's calendar assume the latter. If a separate Steam playtest is still planned, both need a row and a window back. *Needed for §1.4 to be accurate.*
3. **macOS timing** — with March launch or post-launch. Alpha testers' actual OS mix should decide it, and it changes the WS-4 spike. *Needed before WS-4 (Dec).*
4. **Build hosted → local export?** Safe, cheap, and a real answer to subscription-churn objections; also not required for March. The WS-1 interface requirement (§1.2) keeps the option free either way. *Deferrable past launch.*
5. **Split `ONLINE_COMMUNITY` into read and participate?** §1.3. *Needed when billing gating goes live.*
6. **Direct-build auto-update mechanism** — updater vs manual. *Deferrable past launch.*
7. **Minimum spec — cores and RAM.** The WS-2 spike (§10.1) outputs two numbers: worker count per core tier, and the hardware floor below which the parallel phase A week is not promised at all. Needed for the Steam store page regardless, so it is not extra work. *Needed by the WS-2 spike (Sept–Oct).*
8. **Desktop paint and store resolution (§WS-8).** The web keeps 3530×3412 masters because Cloudflare resizes on demand; desktop has no Cloudflare. Painting and storing at display resolution (512px) is ~1/47th the pixels — it moves both installer size and paint CPU by more than an order of magnitude, and it is the single highest-leverage choice in WS-8. Needs the installer budget (Decision 1) to settle. *Needed before WS-8 begins.*
9. **Move teams and coaches to R2 for the web before the desktop build?** 584 MB with no remote seam today. Building it once serves both web and desktop; building it after the migration means building it twice. *Needed before WS-7 conversion work.*
10. **Demo scope limit** — season, team, or time cap. Decide with the Demo build in December, informed by alpha engagement data.

---

## 10. Performance and UESS constraints

The migration must be [`Sim_Perf_Capstone.md`](./Sim_Perf_Capstone.md) compliant and must not degrade live animated gameplay. This section states what that means concretely, because the threat is not where it looks.

### 10.1 The real threat: pool defaults are Railway numbers, not laptop numbers

**The CPU week is designed to run concurrently with the user's live game, and that is a feature.** `bootGame.js` fires `POST /franchise/complete-week/start-cpu-sims` once per week at game boot — *"Call when the user begins their franchise game for this week (e.g. first Play Quarter)."* Phase A sims the 62 non-user matchups while the user plays; phase B merges the user's result and finalizes the week afterward. This hides ~35 s of CPU sim behind time the user is already spending. **Do not "fix" this by serializing it.**

The consequence for desktop is that **the contention is real and unavoidable by scheduling.** `FRANCHISE_CPU_SIM_POOL_WORKERS` defaults to **8**, chosen at 6.51× / 81% efficiency explicitly *"leaving headroom so live user games never contend."* On Railway's 32 vCPU that headroom is 24 cores. **On a 4- or 8-core laptop there is none** — eight spawned workers take every core while the Phaser scene is animating.

**The cost lands in the worst possible place.** The user does not see "advancing week, please wait." They see *their own game stutter*. A visible spinner is honest; a janky animation reads as a broken game.

Desktop requires a **policy, not a constant**, built on one rule:

> **The live game is the priority workload. Phase A yields to it.**

- Size phase A's pool from actual core count **minus a reserve for the live game and the renderer**. Cap harder on low-core machines.
- **Accept that phase A may not finish during the quarter on a weak box.** This is fine and requires no new machinery: phase B already exists to finish the slate afterward. The two-phase design degrades gracefully into "some of it finishes after you're done" rather than breaking.
- **Memory:** ~200 MB RSS per worker. Eight workers is ~1.6 GB before Electron's share — untenable on an 8 GB machine. Worker count is bounded by RAM as well as cores.
- **`[POOL-OVERLAP]` becomes an error condition.** Three pooled paths share `cpu_week_pool.py` (CPU week, autotrain, practice squad), each sizing itself independently, so two live at once silently request 2× the intended workers. Survivable at 32 cores; fatal at 8 with a live game running.

`PS_SIM_POOL_WORKERS` already exists as a separate lever and is the right shape for this.

**Measure it in the WS-2 spike:** on a 4-core reference machine, run phase A concurrently with a live animated game and find the worker count that keeps the frame rate clean. That number, not the Railway default, is the desktop default.

### 10.2 SQLite improves sim performance

The capstone's figures normalize DB wait to Railway's colocated Atlas (~1–3 ms). **Local SQLite is sub-millisecond with no network hop**, so every DB wait in those tables shrinks. The persistence migration is a performance *tailwind* for the sim, not a cost.

### 10.3 RNG isolation is what makes WS-1 verifiable — protect it

Phase 2 established that `pymongo`'s `bulk_write` consumes the **global** `random` stream: a write matching zero documents still shifted final scores under a fixed seed. Because the engine was isolated onto `sim_rng` (`BackEnd/utils/sim_random.py`, 52 modules), removing pymongo entirely does not perturb the engine's draw sequence.

**Consequence: the Mongo → SQLite swap is verifiable by seeded exact-diff.** Draw count is unchanged, so byte-identical refstats prove the basketball did not change. Without Phase 2's isolation this migration would have been unverifiable by any available instrument. Two conditions:

- **The persistence adapter must never draw from `random` itself** — bind `sim_rng` or draw nothing.
- **The global-draw guard stays armed** (`log_only=True`) at loopback FastAPI startup, exactly as in production today.

**WS-1 Gate 2 is therefore stated as a verification run, not "tests pass":**

```bash
PYTHONHASHSEED=0 python3 scripts/perf_sim_baseline.py \
  --franchise <identity-ON fixture> --week 4 --games 63 --mode both \
  --seed <seed> --no-profile --workers 1 --tag sqlite-adapter
python3 scripts/sim_verify/diffstats.py <mongo refstats> <sqlite refstats>
```

Byte-identical output ⇒ the adapter changed storage and nothing else. Use an **identity-ON franchise** (capstone, 2026-08-14: a flat fixture understates pressure-path cost by ~40%). `PYTHONHASHSEED=0` is required for seeded runs; the desktop shell sets it at engine launch for harness use — production self-seeds and does not need it.

### 10.4 UESS compliance

The migration **does not touch UESS**, by design. UESS is backend-authority / frontend-pure-renderer; the migration changes *where the backend runs*, not what it emits. `animation_steps` are identical whether the engine is on loopback or Railway.

Two places to hold the line:

- **`gameScene.js`, `bootGame.js`, and `court.html` are simultaneously the top UESS files and the top WS-3 files.** WS-3 touches only how they learn *which game this is*, never how they render steps. The "migrate the file before doing animation work in it" rule (§WS-3) matters more here than anywhere else in the tree.
- **WS-7's animation-asset exclusion** (see WS-7) exists for the same reason: a dimension change in a measured asset presents as a UESS regression.

### 10.5 Standing capstone rules that apply to migration PRs

Restated because they are easy to violate during a refactor:

1. **Draw-count changes → poison-stash test, not exact diff.** The adapter should not change draw count; if a PR does, it needs the right instrument.
2. **No source edits while a measurement run is in flight.** Python does not reload imported modules, so the *next* run in a sequence silently picks up the edit and invalidates the comparison.
3. **Call counts are the only contention-proof instrument.** Wall-clock is ±5% even on a quiet box, and CPU-time is not immune either — on heterogeneous P/E-core CPUs a loaded box bills the same work 2.5× (measured 148 s → 375 s, 2026-08-17). Prefer `cProfile` ncalls and phase `calls` for any migration perf claim.

---

## 11. Reference note

Two documents cited by the August draft — `repo_audit.md` and `app_build_dynamics.md` — are **not in the current tree**. Their findings have been inlined here where they were load-bearing (the `db.py` direct-import problem, the URL-state problem), both re-derived from the code rather than taken on trust. Either restore them or treat this document plus the audit as self-contained. A plan that cites a document nobody can open has no evidence base.
