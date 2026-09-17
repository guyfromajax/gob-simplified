# Desktop Migration Work Plan — Code Audit & Proposed Revisions

> **Superseded by [desktop_migration_work_plan_v2.md](./desktop_migration_work_plan_v2.md) (14 Sept 2026). Kept for history — do not follow.**

**Audited against:** `develop` @ `801aa5f` ("doc and animation cleanup", 14 Sep 2026)
**Audit date:** 14 September 2026
**Audited document:** `_documentation_master/projects/desktop_migration_work_plan.md` (header says "Last updated: August 2026")
**Method:** read-only. No code changed. Every claim below cites a countable fact from the tree.

---

## 0. Verdict

The plan's **architecture is sound and should not change.** Loopback FastAPI + bundled Python engine + SQLite + Electron is still the right shape, and §2's reasoning holds up.

The plan's **execution model has three defects** that would cost real weeks if discovered in November rather than now:

1. **WS-3 is mis-specified.** It treats URL-state as accidental sprawl to be eliminated. It is not — it is a deliberate, documented invariant that makes the browser build work, and the plan's proposed elimination would break the online version the product must keep. (§3 below. This is the important one.)
2. **WS-3's "definition of done" instrument does not work.** `StateTelemetry` is disabled in source and its contract asserts the *opposite* of the migration goal. Driving its log to zero is currently a no-op. (§4)
3. **Two workstreams are missing entirely** — asset payload (1.1 GB) and the portrait generation pipeline (now dynamic and server-side). Both are launch blockers, neither appears in the plan. (§6, §7)

Plus routine staleness: the calendar's premises are wrong, and two referenced companion docs no longer exist.

**Scale check against the 8 Sept state-of-play:** WS-1 through WS-6 are, by the evidence in this tree, **0% started**. Not "behind" — unstarted. The plan budgeted Aug–Sept for WS-1 and half of WS-2. That is roughly six weeks of assumed progress that has not happened, against a calendar with ~15 weeks left to the December gate.

---

## 1. Ground truth: what actually exists today

| Plan assumption | Code reality | Status |
|---|---|---|
| WS-1 persistence adapter "begun in protected time" (Aug) | No adapter, repository, or SQLite module anywhere in `BackEnd/`. `find` for `*adapter*`, `*repositor*`, `*persistence*`, `*sqlite*` returns nothing. | **Unstarted** |
| Direct `db.py` collection imports are "risk #10" | **69 non-test files** import collection handles directly (`BackEnd/utils` 32, `BackEnd/api` 15, `BackEnd/models` 5, `BackEnd/tournament` 5, `BackEnd/engine`, `BackEnd/practice_squad`, plus ~40 scripts and ~45 tests). **25 collection handles** defined at `db.py:181–252`. | **Confirmed, now quantified** |
| WS-2 engine localization "begins Sept" | No loopback profile, no compile config. `Nuitka`/`Cython`/`PyInstaller` appear nowhere in `requirements.txt`, `setup.cfg`, or `MANIFEST.in`. | **Unstarted** |
| WS-4 shell | No Electron, no Tauri, no forge config, no `.spec`. `package.json` has one devDependency: `@playwright/test`. | **Unstarted** |
| WS-5 routing split | `api-config.js` still resolves a **single** base URL by hostname sniffing. No local/remote table. | **Unstarted** |
| WS-6 build pipeline | Nothing. | **Unstarted** |

**One thing is better than the plan assumes.** `API_CONFIG` adoption is near-total: **99 files** route through it; only **2 files** still hardcode a backend URL (`adminGuard.js`, `sentryInit.js` — both server-only concerns that are excluded from the desktop profile anyway). WS-5's "one routing table, not scattered conditionals" is therefore **cheap** — a single-file change plus two cleanups. Promote WS-5's routing seam earlier; it is a days-not-weeks task and it de-risks WS-2.

**A second asset the plan doesn't credit:** `BackEnd/services/entitlements.py` already exists as the single choke point for "what is this user allowed to do?", currently returning yes for everything by design, with a `BILLING_GATING_ENABLED` master switch. The §1.4 account/entitlement bridge has its seam already built. Say so in the plan.

---

## 2. The calendar's premises are wrong

§4's calendar is built on a playtest track that did not happen as written.

- **Plan says:** "Aug — Playtest Phase 1 live (gated)"; "Sept — Phase 1 feedback loop"; "Oct — Phase 2 controlled-open"; "Dec — Phase 3 open stress test."
- **Actual:** testers are on the **alpha on the live site**. No Steam playtest wave has run. The `alpha_feedback`, `alpha_otps`, and `access_code_requests` collections plus `alphaBanner.js` / `alphaFeedbackModal.js` are the live feedback apparatus — this is a direct-web alpha, not the Steam-distributed cohort playtest §1.1 describes.

This matters for more than tidiness. §1's build-profile table has two rows ("Playtest via Steam", "Playtest via direct download") whose entire purpose is revocability through Steam entitlement + backend auth. If the Steam playtest is not running, those rows describe a hypothetical, and the *real* current profile — web alpha, no build at all — isn't in the table.

**Proposed:** rewrite §4 as a single migration-track calendar anchored to today, add a "Web alpha (current)" row to §1's table, and state explicitly whether the Steam playtest is still planned or has been folded into the January beta. (Open question Q5 below.)

The **Nov 15 checkpoint and slip valve in §4 should be kept verbatim.** They are the best-designed part of the document and they are about to become load-bearing.

---

## 3. WS-3 is mis-specified — and this is the one to fix

### 3.1 What the plan says

> "The query string is currently a cross-page state container and resume protocol… In a desktop shell this is fragile and unnecessary."
> "Drive its logged URL-reads to zero (or fallback-only) page by page."

### 3.2 Why that framing is wrong

URL-as-identity is not drift. It is an enforced architectural rule, written down in the code:

`FrontEnd/static/js/shared/franchiseLocalStorage.js`, header comment:

> *"Identity: URL `?franchise_id=` only — never store a bare 'current' franchise id."*

And `stateTelemetry.js:29–56` encodes the same rule as a machine-checkable contract — `game_id`, `franchise_id`, `tournament_id`, `team_id` each declared `sources: ['url']`, described as *"must come from URL params only."*

That rule exists for a reason, and the reason survives into the online product: the web build is a **multi-page app with multiple concurrent franchises**. Storing a bare "current franchise" breaks the moment a user opens two franchises in two tabs. The URL is the per-tab context, and localStorage is namespaced *under* it (`franchise:{id}:week`, `franchise:{id}:user_team`, …) precisely so the two never collide.

The plan proposes to remove the mechanism that makes multi-franchise work — in a product that must keep shipping a web version for PvP and community leagues.

### 3.3 The structural cause the plan doesn't name

The app is **80 HTML pages** with **133 hard `window.location.href` navigations**. Every page transition is a full document load. The only in-memory store, `FrontEnd/static/js/state/gameStore.js`, is a plain object (151 lines, teams/colors/rosters/gameId) that is **destroyed on every navigation.**

So the URL isn't carrying state because nobody tidied up. It's carrying state because in an 80-page MPA with no persistent client context layer, **the URL is the only thing that survives a navigation.** "Remove URL state" without replacing that property is not a refactor; it's a regression.

### 3.4 Proposed reframing

Replace "eliminate URL state" with **"introduce a context provider with two backends."**

```
FranchiseContext  (new module — single read API for the whole frontend)
   ├── UrlContextProvider      → web build.  Reads/writes query string. Behavior identical to today.
   └── SessionContextProvider  → desktop build. Reads/writes a persisted local session
                                 (localStorage or local API), one context per window.
```

- Every call site migrates from `new URLSearchParams(location.search).get('franchise_id')` to `FranchiseContext.get('franchise_id')`. **That is the entire refactor.**
- The web build's behavior is bit-identical afterward — multi-tab, multi-franchise, deep links, all preserved. This is what lets the online version survive, which is a hard product requirement, not a nice-to-have.
- The desktop build swaps one provider at boot.
- It is incrementally shippable to production behind the existing alpha, file by file, with no flag day.

**Definition of done changes** from "zero URL reads" (wrong — the web build must keep them) to **"zero direct `URLSearchParams` / `location.search` access outside the provider."** That is grep-checkable in CI, which the current DoD is not.

### 3.5 The real scope, measured

The plan names 8 hotspot files. The actual surface:

- **312 call sites** across **76 files** touching `URLSearchParams` / `location.search` / `searchParams`.
- **~40 distinct parameters** carried. By frequency: `franchise_id` (65), `game_id` (48), `team_id` (47), `mode` (45), `tournament_id` (29), `my_team` (29), `resume_from_timeout` (25), `user_team_id` (24), `home_id` (22), `away_id` (22), `home`/`away` (15 ea), `quarter` (14), `clock` (14), `week` (11), `resume_from_anchor` (11), `quarter_break_from` (9), `consume_resume_anchor` (9), `return_url` (8), `active_resume` (8), then a long tail (`lineup_checkpoint`, `locked_exhausted_user_lineup`, `starting_possession`, `start_with_inbound`, `timeout_trace_id`, …).

**The plan's hotspot list is out of date.** Measured ranking:

| File | Call sites | In plan's list? |
|---|---:|---|
| `franchise-command-center.js` | 27 | yes |
| `set-lineup.js` | 21 | yes |
| `js/phaser/bootGame.js` | 20 | yes |
| `js/phaser/gameScene.js` | 17 | yes |
| **`training.js`** | **15** | **no** |
| **`tournament.js`** | **15** | **no** |
| `game-plan.js` | 10 | yes |
| **`franchise-select-team.js`** | **10** | **no** |
| **`court.html`** | **10** | **no** |
| `box-score.js` | 10 | yes |
| **`team-builder.js`** | **9** | **no** |
| **`js/phaser/utils/gameCompletionPopup.js`** | **7** | **no** |
| `js/shared/timeoutNavigationHelper.js` | 6 | yes |
| `common.js` | 6 | yes |
| **`js/shared/authBarInit.js`** | **6** | **no** |
| **`recruiting-common.js`** | **5** | **no** |

Six new files enter the top ten. `team-builder.js` and `recruiting-common.js` post-date the plan entirely.

**One scope reducer:** `tournament_id` (29 sites, 5th most common param) is already being retired. `_documentation_master/projects/tournament_id_sunset.md` reports Phases 0–2A complete and the standalone router unmounted. **Sequence the `tournament_id` sunset ahead of WS-3** and ~29 call sites plus the `mode === "tournament"` branches disappear before they have to be migrated. Note the doc's warning: franchise tournament weeks are a separate system keyed on `franchise_id` and must keep working.

---

## 4. `StateTelemetry` cannot serve as the WS-3 checklist

The plan makes this instrument the definition of done for WS-3, twice. It does not currently work for that:

1. **It is off.** `stateTelemetry.js:19` — `enabled: false`, with `logReads`, `logWrites`, `logViolations`, `logCache` all `false`. Comment: *"disabled by default - was for Phase 1.3 work."* There is no log to drive to zero.
2. **Its contract is inverted.** `STATE_CONTRACT` declares `url` the *only* legal source for the four identity keys. Turn it on and it flags the desktop-correct behavior — reading from a context provider — as a **contract violation**. It would fight the migration.
3. **Coverage is partial.** It is referenced in **12 files**, against **76** that touch URL state. Even enabled, it would report on ~16% of the surface.

**Proposed:** either (a) rewrite `STATE_CONTRACT` so the legal source is `FranchiseContext` and re-enable it as a real migration meter, or (b) drop it from the plan and use the grep-based DoD in §3.4, which is cheaper and covers 100% of the surface. **Recommend (b) for the gate, (a) only if runtime violation logging proves useful during the refactor.** Either way, the plan must stop citing it as-is.

---

## 5. WS-1 and WS-5 need a collection-level and route-level classification

Both workstreams say "split local from remote" without saying where the line falls. That line is the actual design work, and it is small enough to just do in the doc.

**25 collections, proposed classification:**

| Local (SQLite, in the save file) | Remote only (stays on Mongo/Railway) |
|---|---|
| `players`, `teams`, `games`, `plays`, `defenses` | `users`, `password_reset_tokens` |
| `franchises`, `franchise_state`, `franchise_team_data` | `alpha_otps`, `access_code_requests` |
| `franchise_players_data`, `franchise_recruits_data` | `alpha_feedback`, `community_highlights` |
| `training_sessions`, `press_conference_sessions` | `around_the_league`, `stripe_events` |
| `fcp_skeletons`, `hct_skeletons`, `tournaments` | `eog_band_log` (telemetry — see note) |

Note on `eog_band_log`: it is EOG band instrumentation with a 180-day TTL (`db.py:376`), sized at ~36,600 rows / ~13 MiB per franchise-season. Writing that into a user's local save is pure cost to them and zero value. **Decision needed:** drop it in the desktop profile, or keep it local and opt-in-upload. Default recommendation: **disabled in desktop release builds, enabled in the January beta build** so the beta still produces calibration data.

**202 routes across 19 router files.** Proposed split:

| → Local loopback | → Remote |
|---|---|
| `franchise_routes` (84), `gameplan_routes` (9), `play_routes` (7), `skeleton_routes` (6), `training_routes` (1), `tournament_routes` (17, pending sunset), most of `api.py` (28) | `auth_routes` (21), `billing_routes` (2), `email_routes` (2), `admin_routes` (1), `feedback_routes` (1), `alpha_feedback_routes` (1), `leaderboard_routes` (2), `community_highlights_routes` (3) |

**The hard part WS-5 understates: auth is wired into the game routes.** There are **91 route-level auth dependencies**, **48 of them in `franchise_routes.py`** — the router that has to run locally with no account. "Offline-first identity" is not a bullet; it is a decision about how to satisfy `Depends(get_current_user)` 48 times in the local profile. Two options, and the plan should pick one:

- **(a) Local principal.** The desktop profile injects a synthetic local user object. Zero changes to 48 call sites. Fastest, and the auth code stays uniform across both builds.
- **(b) Strip the dependency** in the local profile via a router-level override. Cleaner in principle, more surface to get wrong.

**Recommend (a).** It is a dependency-override in the app factory, roughly one file.

---

## 6. MISSING WORKSTREAM: asset payload (proposed WS-7)

The plan never states a bundle size and never mentions asset optimization. The tree:

```
FrontEnd/static/images   1.1 GB   (1,100 files — 534 png, 416 jpg, 129 webp)
  ├── players            443 MB
  ├── teams              377 MB
  ├── coaches            207 MB
  ├── loader2.gif         25 MB   ← a loading spinner
  ├── homepage-v2         16 MB   ← marketing, not game
  ├── resize.gif          12 MB
  ├── loader1.gif        9.7 MB
  └── homepage           8.5 MB   ← marketing, not game
FrontEnd/static/media     15 MB
```

That averages ~1 MB per image — these are unoptimized. Electron's own footprint is ~150 MB on top.

Consequences the plan doesn't price:

- **A >1 GB Next Fest demo download will measurably hurt conversion.** Next Fest traffic is impulse traffic; download size is a funnel step.
- **Steam depot build and upload times** scale with this, on every iteration.
- `gob-asset-architecture.md` §5 puts static league assets at ~300 MB and recommends git → R2 → serve from R2 for web. **The desktop build has no R2.** Those 300 MB either ship in the bundle or download on first run. Undecided.
- ~50 MB of the payload is loading GIFs and marketing homepage art that should not be in a game bundle at all.

**Proposed WS-7 scope:** (1) audit game-required vs web-marketing-only assets; (2) convert to WebP/AVIF at target display resolution — on a 1 MB average, 70–85% reduction is routine; (3) decide bundled vs first-run-download for the static league set; (4) set and defend an installer size budget. **Put a number in the plan.** Suggested target: **under 500 MB installed** for the paid build, **under 250 MB** for the demo.

This is not a December task. Asset conversion touches image paths across the frontend and is much cheaper to do before WS-4 packaging than after.

---

## 7. MISSING WORKSTREAM: portrait generation must run locally (proposed WS-8)

The plan's only statement on this is in WS-5:

> "base 450 portrait set ships in the bundle (no runtime R2 dependency for offline play)"

**That is no longer accurate.** Portraits are not a static set. `BackEnd/api/franchise_routes.py:18095–18200` composites them at runtime:

```
resolve_kit_keys(image_id) → (kit_key, mask_key)
  → r2_images.get(kit) + r2_images.get(mask)
  → recruit_image.make_signed_master(kit, mask, primary_color, secondary_color, mascot)
  → r2_images.put("players/master/<player_id>.png")
  → fpd.meta.image_painted = True
```

Team colors and mascot are inputs. **Team Builder lets users author teams with arbitrary colors**, so the output set is unbounded — it cannot be pre-baked at build time. The pipeline is R2-read, R2-write, server-side, and it has a hard `is_configured()` guard that silently skips and logs a warning when R2 is absent — meaning a naive desktop build **ships with missing portraits and no error the user can act on.**

This is consistent with the `gob-asset-architecture.md` rule ("a uniform is a recipe, not an image"; derivable assets regenerate at the edge) — which is the *right* architecture, and which the migration plan predates and doesn't reference.

**Proposed WS-8 scope:**
- Bundle the kit/mask source set + `Pillow` (already in `requirements.txt`) in the desktop build.
- Implement a **local object store** behind the same interface as `r2_images` (`get` / `put` / `exists` / `is_configured`) writing to the save directory. This is a small adapter and it mirrors WS-1's pattern exactly — **consider folding it into WS-1 as a second adapter seam** rather than a separate workstream.
- **Measure render cost locally.** `gob-asset-architecture.md` §3.2 flags this as an explicitly unverified assumption. A 20-player roster paint at franchise creation is the case to time, on low-end hardware.
- Replace the silent `is_configured()` skip with a real failure path in the desktop profile.
- Carry over the doc's §4.1 stated limitation: **uploaded logos cannot be regenerated offline.** Either cache on first online session or fall back to the generated banner. Decide it, don't discover it.

---

## 8. Smaller corrections

- **Dangling references.** §WS-1 cites "the audit's risk #10" and §WS-3 cites "audit §3", but `repo_audit.md` is **not in the current tree**. Neither is `app_build_dynamics.md`, which the memory notes and the Steam docs both reference. `Steam_Strategy.md` is present at `_documentation_master/12_GTM/Steam_Strategy.md` and the link resolves. Either restore the audit or inline its two cited findings — a plan that cites a document nobody can open loses its evidence base.
- **`BackEnd/main.py` is not the FastAPI app.** It has no `@app` routes and no app factory; the app is assembled in `BackEnd/api/api.py:486–501`. WS-2's "stand up the FastAPI app" should name `api.py` so the first task doesn't start in the wrong file.
- **`flask_app.py` exists** alongside the FastAPI app and also imports `db` directly. Worth one line in WS-2: is it live, and does it need a desktop story, or is it dead weight to delete before migration?
- **Sentry/GTM strip list is small** — 4 frontend files reference `Sentry`/`gtm`/`dataLayer`, plus `sentry-sdk[fastapi]` in requirements. Cheap. Keep it in WS-2, note it's a half-day.
- **Test surface for the validation gates is real:** 337 Python test files, 28 Playwright specs, plus `scripts/season_advance_harness.py` and `scripts/perf_sim_baseline.py`. WS-1's gate ("cloud runs unchanged on the Mongo adapter") and WS-2's ("full season locally, zero remote calls") both have tooling already. **Say this in the plan** — it is the strongest argument that WS-1 is genuinely low-risk.
- **`db.py`'s production access guard** (`ProdAccessBlocked` / `ProdWriteBlocked`, `GOB_DB_ACCESS`, `_ReadOnlyCollection`) is a real piece of engineering that the adapter interface must preserve, not bypass. Add it to WS-1's interface requirements explicitly, or the refactor quietly removes a safety net.
- **`env_config.py`** already resolves DB environment from a pristine-env snapshot. The adapter's runtime selection (`cloud → Mongo, desktop → SQLite`) should extend this, not add a parallel mechanism.

---

## 9. Proposed revised workstream ordering

The plan's ordering is broadly right. Three changes, all justified above:

| | Workstream | Change | Why |
|---|---|---|---|
| 1 | **WS-5a: routing seam only** | **moved up** from WS-5 | 99 files already use `API_CONFIG`; it's one file plus two cleanups. Unblocks WS-2 and proves the local/remote split before anything depends on it. |
| 2 | **WS-1: persistence adapter** (+ local object store seam from WS-8) | unchanged position, scope widened | Still the correct first big rock. Add the `r2_images` interface as a second adapter — same pattern, same sprint. |
| 3 | **`tournament_id` sunset completion** | **new, inserted** | Removes ~29 WS-3 call sites before they need migrating. Already Phases 0–2A done. |
| 4 | **WS-7: asset payload** | **new** | Must precede WS-4 packaging. Independent of everything else — good filler work when other tracks are blocked. |
| 5 | **WS-2: engine localization** | unchanged | Compile spike early, as the plan already says. |
| 6 | **WS-3: context provider** | reframed per §3 | No longer "delete URL state." Incrementally shippable to the live alpha. |
| 7 | **WS-4 / WS-6: shell, packaging, pipeline** | unchanged | |

WS-5b (entitlement bridge, offline identity, graceful degradation) stays where it is, with the auth decision from §5 made up front.

---

## 10. Open questions — these change the plan's shape and I can't answer them from code

1. **Does the desktop build need multiple franchises open simultaneously?** This is the single biggest input to WS-3. If one-franchise-per-window is acceptable, `SessionContextProvider` is trivial. If not, it needs per-window context isolation and the design gets meaningfully harder. The web build's multi-tab behavior does *not* settle this.
2. **What happens to franchise mode on the web after March?** Does the online version keep full single-player franchise (meaning both context providers are maintained forever), or does web narrow to PvP/leagues/community only (meaning the URL provider can eventually be retired)? This decides whether §3.4's dual-provider is permanent architecture or a transition scaffold.
3. **Is Team Builder in scope for the offline base game?** If yes, WS-8's local paint pipeline is mandatory and needs a perf budget. If Team Builder is an online-only feature, WS-8 shrinks to bundling a fixed kit set and the whole problem gets much smaller.
4. **What is the installer size budget?** Everything in WS-7 keys off this number. It's also a Next Fest conversion decision, not just an engineering one.
5. **Is the Steam playtest still happening before the January beta, or has it been folded in?** §1's build-profile table and §4's calendar both assume it. If it's folded into the beta, two profile rows and half the calendar are describing something that won't exist.
6. **Windows-only for the beta?** The plan says Windows first, macOS second, and defers the macOS timing decision to §6. Given the January beta runs with existing alpha testers, their actual OS mix should decide this — and it's worth knowing now, because a macOS requirement changes the WS-4 spike.

---

## 11. Sections to keep verbatim

Not everything needs changing, and it's worth being explicit about what's still good so revision doesn't churn it:

- **§0 non-negotiables** — all three still correct, especially "the Python engine is not rewritten."
- **§2 target architecture diagram and both closed decisions** (SQLite; compile the engine). The reasoning is sound and nothing in the code contradicts it.
- **§1.3 / §1.4** — the offline-base-game + server-side-moat split is exactly right, and `entitlements.py` now gives it a real seam.
- **§4 solo-dev protected-time rule, Nov 15 checkpoint, and slip valve.** Keep word for word. Given §1's finding that all six workstreams are unstarted, the slip valve is now the most important paragraph in the document — and the failure mode it names ("December arrives with the migration 20% done") is live, not hypothetical.
