# GOB — Whole-Codebase Technical Audit + Work Plan

**Date:** 2026-09-29 (work plan added the same afternoon)
**Grounded in:** `develop` @ `8625c30` (Sep 29, "Merge fix/nav-coverage"). All file/line references are from that commit.
**Method:** seven parallel area passes (backend architecture, engine, data/persistence/desktop, security, frontend, tests/CI/tooling/docs, performance/ops). I verified every item marked **✅ verified** myself in the code; everything else is as reported by the pass and should be spot-checked before a fix is built on it.
**Scope:** a technical audit of stability, security and scalability across the whole codebase. It is broad, not line-by-line. Game-logic correctness and feature-system design are out of scope; Jamie owns those.
**Companion docs:** `pvp/pvp-technical-audit-2026-09-28.md`, `college-pro/implementation-plan-2026-09-28.md`.

**Where to look:**

| Section | Contents |
|---|---|
| §0 | Summary |
| §1–3 | Findings |
| §4 | What they mean for each plan |
| §5 | Risk register |
| **§6** | **Work plan (four lanes)** |
| §7 | Turning estimates into measurements |
| §8 | Benefits |
| §9 | Scorecard |
| §10 | Notes |

---

## 0. The short version

GOB is a big, working codebase:

| Area | Size |
|---|---|
| Python backend | ~192k lines |
| Frontend JS | ~140k lines |
| Tests | ~3,250 Python tests + 546 Playwright tests |
| Docs | 320 files |

The engine and the measurement discipline around it are genuinely strong for a solo project. **The platform around the engine is not launch-ready.** None of the problems are exotic; most are small fixes. But several silently corrupt data or let users cheat, and a few block the desktop launch outright.

**Five findings matter more than everything else:**

1. **Player/team season stats silently disappear from season 2 onward.** ✅ verified. The duplicate-game guard in `finalize_game` keys on `week:teamA:teamB` with **no season** and is **never reset** (`game_id_utils.py:147`, `stat_updater.py:1857`; `finish_season` doesn't clear it). Any matchup that lands on the same week number it had in an earlier season is skipped. A Monte Carlo on the real schedule generator (20 runs × 8 seasons) gives the share of regular-season games whose stats are skipped:

   | Season | 2 | 3 | 4 | 5 | 8 |
   |---|---|---|---|---|---|
   | Stats skipped | 5.2% | 11.2% | 17.7% | 21.0% | 31.2% |

   W-L and results are unaffected. Box-score stats, leaders, awards inputs and anything built on season stats are not. **Fix: S.** Add season to the key and reset it per season. Stats already lost in existing leagues can't be recovered.
2. **Anyone can rewrite any franchise.** ✅ verified (core routes). 27 mutating routes have no authentication:
   - 9 franchise-lifecycle routes, including `complete-week`, `finish-season` and `save-result`
   - 13 game-engine routes
   - 4 gameplan/playbook routes
   - `/api/run_training`, which writes the **universal** player pool every new franchise is cloned from

   `complete-week` also saves the score, box score and full game document **the client posts**, and geek points and leaderboards are built from that. Many read routes leak other users' franchises, and `GET /games` hands out live game ids.
3. **The live-game cache never releases finished games.** ✅ verified. `ongoing_games` (`api.py:810`) is only emptied on a Q1 reload or anchor restore, never when a game ends. Each entry holds the full turn log (~30–36 MB measured). The hosted server leaks memory with every game played until it restarts, and a restart drops every in-progress quarter.
4. **Desktop saves have no version, no migration path and no backups.** Every post-launch data-shape change can break existing players' saves, and the 34 Mongo backfill scripts can't reach a user's `local.sqlite`. `finish_season` can also be re-run mid-way ✅ verified: the transition token is consumed first and **re-minted** if week is still 36 (`franchise_routes.py:229–259`). A crash or double-click during rollover can age a league twice. On desktop, quitting the app during rollover is a realistic event.
5. **The server is one process doing everything.** Live games, week advances, persistence, portrait painting and response serialization all share one Python process (~one core of useful throughput). There's no admission control on week-sim pools, no alerting, and no crash reporting on desktop. Rough capacity is ~15–30 concurrently active franchises before week latency degrades. That's an estimate from measured figures, not a load test (§7). It's fine for alpha, not for a Steam launch with an online layer.

**What this means for planning:** there's a foundation block of roughly 4–6 weeks. It runs in four lanes alongside the UX overhaul and the desktop build (§6), not after them. About half of it is *already* a desktop-launch requirement regardless of features. PvP's security prerequisite is a subset of it.

---

## 1. Grades by area

| Area | Grade | One-line why |
|---|---|---|
| Game engine | **C** | Excellent verification (equiv-v3, strict mode, measured perf). But six 1,000+ line functions, outcomes coupled to animation geometry by design, two divergent "arms", a process-wide RNG with live leaks, and no ruleset |
| Backend architecture | **D+** | Business logic in route handlers (`franchise_routes.py` 20.5k lines, 92 endpoints), circular imports held together by ~770 lazy imports, 594 broad `except Exception`, random scores fabricated on sim failure |
| Data & persistence | **C+** | The adapter itself is B+ (clean local/remote split, strong prod guards, measured flat SQLite curve). Correctness is weak: no transactions on hosted, re-entrant rollover, no save versioning, the stats-claim bug |
| Security | **F** | 27 unauthenticated mutating routes, client-trusted results, read IDOR, spoofable rate limiter, debug endpoints in prod |
| Frontend | **C−** | Deliberate architecture (API routing table, FranchiseContext, ETag store). Poor hygiene: two Phaser copies loaded, duplicate module instances, no build step, ~30 copies of basic helpers, 1,431 console calls |
| Tests, CI, tooling, docs | **C** | Large seeded suite with good guards. But CI doesn't block deploys, desktop/SQLite and Playwright aren't in CI, auth is mocked for every test, billing has zero tests, ~500 MB of scratch is tracked |
| Performance & ops | **C** | A-grade measurement, D-grade launch readiness: single process, unbounded memory, no backpressure, no alerting, the week still misses its 90 s target |

---

## 2. Verified critical findings

| # | Finding | Evidence | Fix | Blocks |
|---|---|---|---|---|
| V1 | Season-less matchup claim drops stats from season 2 (5%→31%) | `game_id_utils.py:147–165`; `stat_updater.py:1857–1861`; no reset in `finish_season` `$set`; Monte Carlo on the real `ScheduleManager` | S | Everything multi-season: desktop saves, leaders/awards, PvP strength scores, college/pro career stats |
| V2 | Unauthenticated franchise lifecycle + client-posted scores | `save_result` `:5781`, `complete_week` `:9224`, `finish_season` `:19715` take no user; `CompleteWeekRequest.result` → `_save_game_result` | M–L | Paid users, leaderboards, PvP |
| V3 | `/api/run_training` writes universal `players`/`teams` with no auth | `training_routes.py:21`, mounted at `api.py:532` | S (delete) | Now |
| V4 | `ongoing_games` never evicts finished games | Removals only at `api.py:3450, 3658, 3690, 3702` (Q1 reload / anchor restore) | S | Hosted stability |
| V5 | `finish_season` re-entrant after partial failure | Token consumed, then re-minted when week==36 (`franchise_routes.py:229–259`); multi-collection writes, no transaction | M | Desktop launch |
| V6 | CPU-week claim heartbeat set once, never refreshed | Only at `franchise_routes.py:6093–6098`; 300 s stale window; desktop weeks already run 128–169 s | S | Duplicate week sims under load |
| V7 | Two Phaser versions loaded in one game page | 5 modules import 3.60, 6 import 3.70 | S | Desktop bundle/perf, cross-version bugs |
| V8 | Unescaped usernames in the Mode Select leaderboard | `mode-select.js:319, 328` | S | PvP (renders other users' names) |
| V9 | Desktop doesn't set `PYTHONHASHSEED` | Only in `start.sh:18`; `desktop/engine.js:132–138` doesn't set it | S | Desktop determinism; any future replay/verification |

---

## 3. Area findings (condensed)

### 3.1 Game engine
- **Pipeline:** `main.simulate_quarter` → `GameManager.simulate_macro_turn` (815 lines) → `TurnManager.run_micro_turn` (1,146 lines, nesting depth 15) → phase resolvers in `phase_resolution.py` (12.8k lines) → `ShotManager.resolve_shot` (2,255 lines, the largest function in the repo).
- **Outcome is coupled to presentation by design.** The UESS rule builds animations *before* resolving HCO shots, and the rendered shoot-step coordinate decides 2PT/3PT and the contest. The emitter runs twice per HCO shot: a probe with an RNG rewind, then the real emit. The game clock also comes from choreography timing. So every animation or placement tweak changes results, which is why there have been 25 reference re-cuts.
- **The two "arms" still differ in outcome logic** beyond the B1-A convergence:
  - user-team auto-timeouts only happen in sim
  - foul-outs rebuild both lineups in sim, but only one slot in played
  - FCP/HCT/triangle/FT choreography is skipped in sim
  - a sim-only clock burn worth ~4 possessions a game (`GOB_SIM_CRASH_CLOCK`)
- **Determinism.** `sim_rng` is a process-wide singleton, never seeded per game in production, so concurrent games interleave draws. These modules still use global `random` and change outcomes:
  - `dynamic_hct_shot.py:1237/1251` (who shoots, dish)
  - `covert_release_drive_integration.py:101`
  - `transition_bridge.py` (6 coordinate draws that feed outcomes via the coord sync)

  The equiv harness seeds global `random` too, so it can't detect them.
- **Mid-sim DB reads:** `turn_manager.py:3143`; `phase_resolution.py:10704, 10805, 11013, 11213`.
- **Format literals:** at least 121 backend sites (a lower bound). There is no `Ruleset` object.
- **Error noise:** ERROR-level logs fire on healthy games (`[HCO ENTRY BUG] current_bh_id is None`, `🔴🔴🔴 [DIAG] … FALLING BACK TO DB`). About 24 broad handlers aren't covered by strict mode.
- **Tests.** 157 test files touch the engine; the suite is green with 109 xfails. **equiv-v3, the real regression gate, isn't in CI.** Its runner is a tracked `scratch_*.py` at the repo root, and its aggregator lives in `/tmp`, not in the repo.

### 3.2 Backend architecture
- **Routes:** 185 endpoints across 18 router files, with inconsistent prefixes. **All of `api.py` sits inside one module-level `try:`** (lines 136–8650).
- **`franchise_routes.py`** mixes week advance, CPU sims, EOG, training, recruiting, team builder, tournament, browse, 13 copy-paste modal-seen endpoints, `finish_season`, and a 300-line commented-out dev endpoint.
  - 10 functions exceed 300 lines; the biggest is `_complete_week_finish_cpu_and_persist` at 729.
  - `_best_position` is defined twice, and the second definition silently wins.
- **Circular dependencies:** 19 imports go from utils/models *up* into api, and route modules import each other. About 770 lazy imports keep startup alive, and one real startup failure from a cycle is on record.
- **Duplication:**
  - the game loop exists 3 times
  - the CPU finalize loop exists 2 times
  - game-result persistence exists 3 times
  - 6 week-advance endpoints
  - `REGULAR_SEASON_WEEKS` is defined 3 times
  - 138 `week_35`/`week_36` literals
  - 60 inline FTD loads
  - 5 lineup builders
  - 616 raw Mongo calls
- **Fabricated results on failure:** `random.randint(50, 90)` scores at `franchise_routes.py:8854` and `franchise_manager.py:1079`.
- **Dead code:**
  - `season/` (3 empty files) and `tournament/match_scheduler.py`
  - `computer_game_constants.py`, `play_manager.py`, `payload_builder.py`, `transition_analyzer.py`, `quarter_start.py`
  - the legacy training routes and manager
  - four uncalled `FranchiseManager` methods
  - `services/entitlements.py` (only referenced in comments)
- **Config:** 88 env vars are read at 119 sites. About 16 `GOB_*` sim flags are frozen in the reference JSONs and could be hard-coded.
- **Contracts:** 86 request models, but only 3 `response_model=` in the whole API. Payloads are untyped dicts.

### 3.3 Data & persistence
- **Registries and adapter bypass.** The collection registry is copied in 4 places, and `db.py` already lags (it's missing the snapshot collections). **331 raw `db.` calls bypass the adapter**, 242 of them in `franchise_routes.py`. The adapter's bundle API (`read/write/delete_franchise`) has zero callers. **The hand-rolled franchise delete leaves 6 collection types orphaned on hosted.**
- **Document sizes:** FTD reaches 55 MB per league at week 26. `franchises` is ~1 MB. `games` are ~80–90 KB each and deleted at rollover.
- **Governance:** no schema validation, no document or save schema versions, and 34 ad-hoc migration scripts with no ledger.
- **Mixed id types.** FTD `franchise_id` is an ObjectId; FPD/FRD/games use str. **SQLite matches both; Mongo doesn't**, so desktop tests can't catch id-type bugs.
- **Atomicity.** There are no transactions on hosted. `finalize_game` claims first, then writes, so a crash loses stats silently. SQLite's `store.transaction()` is connection-wide on a shared connection, and other threads' commits become no-ops inside it.
- **Desktop SQLite.** Pool workers open the same SQLite file with the default 5 s lock timeout and no `busy_timeout`. There are **no save backups**. The `RemoteUnavailable` trap is invisible in tests, because remotes are mongomock under test.
- **Indexes.** There's no unique index on `users.email` or `alpha_otps.otp_code`, which allows duplicate-account and OTP races. Unique-index creation failures are swallowed at startup.
- **Strong:** prod-write guards (`env_config`, `GOB_DB_ACCESS`, `--confirm-db`). Staging has none.

### 3.4 Security
- **Unauthenticated mutating routes:**

  | Area | Count |
  |---|---|
  | franchise | 9 |
  | api (engine) | 13 |
  | gameplan | 4 |
  | training | 1 |

- **Client-trusted inputs:**
  - scores and `winner`
  - `game_document`: any keys are `$set` onto the game doc with upsert, then aggregated into season stats
  - `bulk_sim_used`, which controls the geek-point reduction
  - both sides' tactics and lineups in `simulate-quarter`
  - training allocations
  - community debut scores
- **Read leaks:** franchise state, roster, recruits, training and standings for any id; `GET /games`; any team's gameplan and playbook.
- **Debug surface in prod:** `/sentry-debug`, `/debug/server-state`, `/franchise/debug-names`, `/api/diagnostics/*` (unbounded disk writes), and public `/docs`. The global exception handler returns `str(exc)` and reflects *any* https origin with credentials.
- **Auth weaknesses:**
  - a dev-secret fallback unless the env name is exactly `production`
  - roles trusted straight from the JWT
  - plaintext reset tokens
  - no token revocation
  - signup reveals whether an email exists before the OTP check
  - login timing leaks the same thing
  - the bcrypt 72-byte edge
- **Rate limiting** keys on the client-controlled first `X-Forwarded-For` value (whether Railway's edge overwrites it is unverified). It's in-memory, and the 100/min default is never applied.
- **Dependencies** are almost entirely unpinned, and `mongomock` ships in prod requirements.
- **Tokens:** the JWT lives in localStorage, GTM is loaded, and there's no CSP.
- **Clean:** no injection primitives, no committed secrets.

### 3.5 Frontend
- **Structure:** 81 pages, mixed classic scripts and ES modules, 125 `window.*` globals, no build step.
- **Duplicate module instances from `?v=` cache-busting.** `gameSfx`, `animateGameTurns` and `AnimationEngine` each load twice with separate state. That causes double or un-preloaded SFX.
- **Hotspots:** `createGameScene` (~3,776 lines), `playTurnAnimation` (~2,556), and `court.html` (7,796 lines).
- **Duplicated helpers:** 18 `playSound` copies, ~30 `escapeHtml` copies, 7 fetch wrappers, and 170 raw `fetch` calls. Some game-loop calls send no auth header.
- **Dead code:** 7 legacy/POC pages, ~1.3k lines of page JS behind redirect stubs, and `.md` files in the web root.
- **Assets:** a 9.7 MB `loader1.gif` on every main page, and `images/` at 1.1 GB.
- **Leaks:** 666 `addEventListener` vs 52 removes, and one Phaser `shutdown` handler. This matters inside the shell and Electron.
- **Styling:** 1,347 CSS hex + 853 HTML hex + 450 JS hex colours, and legacy `:root` blocks that redefine token names.
- **Tests:** Playwright isn't in CI. 30 orphaned `*.test.js` files ship to Netlify.

### 3.6 Tests, CI, tooling, docs
- **Test suite.** ~3,250 Python tests, seeded per test, with an allow-list DB guard and strict exceptions. **122 known-red tests.**
- **Coverage gaps.** Auth is overridden for every test; only 6 tests exercise real auth, and there's no cross-user ownership test. Billing and entitlements have zero tests.
- **CI** runs migration gates, mongomock pytest and env-safety. **It does not run Playwright, the SQLite/desktop mode, or lint. CI doesn't gate deploys.** The runbook says `develop` → staging and `main` → production, with the CI check as a manual step.
- **Repo hygiene:**
  - `tmp/` (498 MB) and `.arm/` (25 MB) are tracked despite `.gitignore`
  - logs and clutter at the repo root
  - 859 report files (57 MB)
  - ~95 one-off data scripts
  - 218 paths with spaces
  - `.dockerignore` ships `tmp/`, reports, docs and images to Railway
- **Docs.** 104 dead file references (7%). **No root `CLAUDE.md` or `.cursor/rules`.** `bugs.md` mixes roadmap, open and resolved items. Two deploy docs conflict on `GOB_DB_ACCESS`.
- **Versions:** Python 3.11 in prod, 3.12 in CI, 3.13 locally; Node 18/20; no root lockfile.

### 3.7 Performance & ops
- **Single process, not horizontally scalable.** Live games live in process memory.
- **Hosted week** takes ~115 s against a 90 s target, and persistence dominates 5:1. EOG Tier 3 hasn't started, and the post-N+1-fix time has never been re-measured (somewhere between 21 and 95 s).
- **Week advances** each spawn a cold 8-worker pool (~1.6 GB). Autotrain and practice-squad pools stack on top, with no semaphore or queue.
- **`/api/simulate-quarter`** returns the whole game's turns so far (29–40 MB for the full-game shape), with no gzip.
- **Blocking Mongo calls** sit in `async def` handlers, including leaderboards that scan every user.
- **Portrait painting** runs in the API process. The Cloudflare Images free tier (5,000 transforms/month) will run out at launch.
- **Observability.** Sentry sends PII. There's no alerting, no uptime check, and **no desktop crash reporting**.
- **Desktop.** A week takes 128–169 s and a season ~50–65 min. **Minimum spec is still undetermined.**
- **Cost:** ~$21/month today. At saturation, a 32 vCPU/32 GB box would run roughly $950/month (estimate).

---

## 4. What this means for each plan

**Desktop launch (Dec build, Jan beta, Mar launch).** These blockers exist *independent of any new feature*:
- the stats-claim bug (V1)
- save schema version + migrate-on-open
- re-entrant `finish_season` (V5)
- save backups + SQLite `busy_timeout`
- `PYTHONHASHSEED` (V9)
- desktop crash reporting
- one Phaser copy (V7)
- asset packaging for the 1.1 GB `images/`
- a SQLite CI leg
- minimum-spec measurement

**PvP.** The PvP audit's security prerequisite is confirmed and enlarged. Amendments:
1. Run PvP sims in a **separate worker service**.
2. Run PvP games in the **played arm**. That keeps the animated replay possible and sidesteps arm divergence.
3. Fix V1 before any strength score reads season stats.

**College/pro.** The plan stands.
- `finish_season` is the hook point and it's fragile (V5), so fix it first.
- A calendar object is a prerequisite beyond the stats-model pipeline.
- New collections go into **four** registries today, so collapse the registry first.

**Agent velocity.** The cheapest multipliers are a root `CLAUDE.md`, CI that gates deploys, and SQLite/Playwright CI legs.

---

## 5. Risk register (top 15, ranked)

| # | Risk | Severity | Fix |
|---|---|---|---|
| 1 | Stats silently skipped from season 2 (V1) | Critical | S |
| 2 | Unauthenticated franchise/game/gameplan routes (V2) | Critical | M |
| 3 | Client-trusted results → leaderboards/geek points | Critical | M–L |
| 4 | Universal player pool writable anonymously (V3) | Critical | S |
| 5 | `ongoing_games` memory leak → OOM → all live games lost (V4) | Critical | S |
| 6 | Re-entrant, non-atomic `finish_season` (V5) | High | M |
| 7 | No desktop save versioning / migrations / backups | High | M |
| 8 | Single GIL-bound process; no admission control on week pools | High | L (M for a semaphore/persistent pool) |
| 9 | CI doesn't gate deploys; SQLite + Playwright untested in CI | High | S–M |
| 10 | Read IDOR + debug endpoints + spoofable rate limiter | High | M |
| 11 | Engine arm divergence + process-wide RNG + global-random leaks | High for PvP | S (leaks) / L (unify) |
| 12 | No observability/alerting; no desktop crash reporting; Sentry PII | High | M |
| 13 | simulate-quarter payload size, no gzip | Medium | S–M |
| 14 | Unpinned deps, 3 Python versions, mongomock in prod | Medium | M |
| 15 | Structural debt (20k-line routes file, cycles, 616 raw DB calls, no response models) | Medium (slows everything) | L |

---

## 6. Work plan: four lanes

**Principle:** don't wait for the UX overhaul or the desktop build to finish. Split the technical work by *what it touches*, so it runs alongside both projects without merge collisions. Timing context (Jamie, Sep 29): the UX/design overhaul finishes before the desktop build does.

**The real constraint is Jamie's review attention, not the code.** Three agent streams (UX, desktop, Lane 1) are manageable if Lane 1 stays as small, isolated briefs. If there's only room for two streams, hold Lane 1 until the UX overhaul lands. The exception is items 1–2 (stats bug, memory leak): they are hurting live leagues and should go in now regardless.

### Lane 1: now, in parallel. Backend-only, no UX files touched

| # | Task | Size | Ref |
|---|---|---|---|
| 1 | Stats-claim fix: season in the key, per-season reset, regression test | S | V1 |
| 2 | Evict finished games from `ongoing_games`; bound the cache | S | V4 |
| 3 | Delete `/api/run_training` + the legacy training manager; remove debug endpoints; disable `/docs` in prod; stop returning `str(exc)` | S | V3 |
| 4 | Refresh the CPU-claim heartbeat during long weeks | S | V6 |
| 5 | Root `CLAUDE.md` for agents; `git rm --cached tmp/ .arm/`; clear root clutter; extend `.dockerignore` | S | 3.6 |
| 6 | Make Railway/Netlify wait for CI; protect `main` | S | 3.6 |

One C+C brief per item, each on its own branch. The only overlap risk is `finalize_game`/`franchise_routes.py`, so merge these before the next large backend change lands there.

### Lane 2: fold into the desktop build. These are desktop launch requirements, not a separate queue

| # | Task | Size | Ref |
|---|---|---|---|
| 7 | Save schema version + ordered migration runner on open; compare catalog/league versions | M | §4 |
| 8 | `finish_season` phase journal / in-progress state; hold the token until the final write; SQLite transaction | M | V5 |
| 9 | Rolling save backups; SQLite `busy_timeout` | S | 3.3 |
| 10 | `PYTHONHASHSEED=0` in the Electron env (`desktop/engine.js`) | S | V9 |
| 11 | Desktop crash reporting | S–M | 3.7 |
| 12 | SQLite leg in CI | S | 3.6 |
| 13 | One Phaser version; replace the 9.7 MB loader GIF; asset packaging plan for `images/` | S–M | V7 |
| 14 | Minimum-spec measurement on a 4-core / 8 GB machine | S | 3.7 |

### Lane 3: after the UX overhaul lands. These touch the same frontend files and flows the UX agents are rewriting

| # | Task | Size | Ref |
|---|---|---|---|
| 15 | Auth + ownership on all 27 routes, with frontend headers; a router-level auth dependency; real-auth ownership tests | M | V2 |
| 16 | Server-owned game results in `complete-week` (the client stops posting scores); retire `save-result`. Waits for Prep PR 2, which moves Advance into the top bar | M–L | V2 |
| 17 | Escape usernames + a shared `esc()` helper; shared fetch client; remove `?v=` from ES import specifiers (the duplicate-module bug). Fold into the chapter 8 sweep | S–M | V8, 3.5 |
| 18 | Playwright smoke in CI, once UX flows stop moving | M | 3.6 |

### Lane 4: before the January beta. Launch ops

| # | Task | Size | Ref |
|---|---|---|---|
| 19 | Fix the rate-limiter key; apply the default limit; per-user limits on heavy routes; auth hardening (secret check on every non-dev env, token versioning, hashed reset tokens, OTP-before-email) | S–M | 3.4 |
| 20 | Admission control: a process-wide semaphore or persistent pool for week sims; a separate worker service for PvP/background jobs | M | 3.7 |
| 21 | Gzip middleware + incremental turns in `simulate-quarter` | S–M | 3.7 |
| 22 | Observability: Sentry scrubbing + releases, uptime/alerting, `verify_deploy` checks `cpus=` | M | 3.7 |
| 23 | Move equiv-v3 into `scripts/sim_verify/` with a small CI smoke | M | 3.1 |
| 24 | Pin dependencies (`uv`/pip-tools), split dev requirements, one Python version | M | 3.4 |
| 25 | Load test + hosted week re-measure (see §7). Run after item 2 lands | M | §7 |

### Deferred structural work (do it when a feature needs it)
- **Ruleset object:** when college/pro becomes playable.
- **Per-game RNG + arm unification:** for PvP v2 / ghost-live.
- **Split `franchise_routes.py`** behind a service layer, plus a repository layer and response models. Start with the pieces college/pro and PvP touch.

---

## 7. Turning estimates into measurements

The correctness and security findings are verified in code. The **scalability** conclusions are partly estimates. To make them measured facts:

| Gap | How to close it | Who |
|---|---|---|
| Concurrent capacity (~15–30 franchises is arithmetic, not a test) | Staging load test: N simulated users advancing weeks and playing games at once, stepping N up until latency breaks. Run after item 2 | C+C, briefed by Claude |
| Hosted week time (between 21 and 95 s since the N+1 fix) | Re-measure on staging | C+C |
| Atlas tier, connection limits, backups on/off | Atlas console | Jamie (~5 min) |
| Production CPU pool on/off (`FRANCHISE_CPU_SIM_USE_POOL`) | Railway variables | Jamie |
| Railway edge overwrites `X-Forwarded-For`? | One curl test | Jamie or C+C |
| Responses gzipped at the edge? | One curl test | Jamie or C+C |
| Desktop minimum spec | 4-core / 8 GB run (item 14) | Jamie when hardware is available |

---

## 8. Benefits once the plan is done

1. **Stats stay complete.** Player and team stats stop silently disappearing after season 1.
2. **No cheating.** Nobody can fake results, edit other people's teams, or mess with the shared player pool, so leaderboards and PvP mean something.
3. **Saves are safe.** Desktop players' franchises survive app updates, crashes and quitting mid-rollover, with backups if something goes wrong.
4. **The server stays up.** No memory leak slowly killing it, and heavy traffic slows things down instead of crashing them.
5. **You know your limits.** Real measured numbers for how many players the server handles and what PC the desktop game needs.
6. **You see problems first.** Crashes and errors reach you, including from desktop players, before players have to report them.
7. **Changes break less.** Tests run on desktop and web, and nothing deploys unless they pass.
8. **Agents work better.** Clear repo rules and a clean codebase mean fewer agent mistakes and less review time.
9. **You can charge money.** A secure, stable base is what a subscription, Founder's Edition or PvP needs before anyone pays.
10. **New features go in faster.** PvP and college/pro build on solid ground instead of stacking on top of hidden problems.

---

## 9. Scorecard (for the feature comparison)

| Dimension | Foundation work (§6) |
|---|---|
| Effort | ~4–6 wks agent-assisted, spread across four lanes; Lane 1 is 6 small briefs |
| Codebase risk | Low per item. Items 15–16 (auth/results) need care because they touch the week-advance flow and the frontend, which is why they wait for the UX overhaul |
| Desktop impact | High and positive. Lane 2 *is* desktop launch work |
| Target-segment pull | Indirect but real. This audience punishes lost stats, cheating and corrupted saves hardest |
| Monetization lever | Prerequisite for charging anyone (subscription, FE, PvP) |
| Standalone value if cut | Every item stands alone; Lane 1 is independently shippable |
| Dependency | None. Unblocks PvP and de-risks college/pro |

---

## 10. Notes and corrections

- **Deploy model:** `develop` → staging, `main` → production (`00_Operations/Deploy_To_Live_System.md`). Nothing enforces "CI green before promote" until item 6.
- **Paddle** isn't in the code; only Stripe (the webhook stores events and grants nothing).
- **The stats-claim Monte Carlo** used the production `ScheduleManager` code on the shipped `base_league.json` (20 seeds × 8 seasons). Real leagues may differ slightly, but the mechanism is deterministic.
