# Graceful deploy: 2026-09-30

Branch `fix/graceful-deploy` (based on develop `f8f77734b`). Not merged. **Ready for review.** Backend and deploy config only; no FrontEnd files.

## ⚠️ Jamie: set this on BOTH Railway services
| Variable | Value | Where |
|---|---|---|
| **`RAILWAY_DEPLOYMENT_DRAINING_SECONDS`** | **`180`** | Railway → project → service (`gob-backend-staging` in *resplendent-mercy*; the production backend in *motivated-liberation*) → **Variables** (or the service **Settings** pane, "Deployment teardown") |
| `GOB_GRACEFUL_SHUTDOWN_SECONDS` | leave unset (default **150**) | Only if you change the drain: keep it about 30 s **below** the Railway draining value |
| `GOB_CPU_SIM_CLAIM_STALE_SECONDS` | leave unset (default **90**) | Optional override; floored at 90 (3 heartbeats) |

**Why 180 / 150:**
- A week advance runs ~50 s on a quiet cluster and ~130 s in the slow window measured on Sep 30.
- uvicorn waits up to 150 s for in-flight requests to finish. Railway's extra 30 s leaves time for the shutdown hook before SIGKILL.

**How Railway tears down** (per [Railway docs, deployment teardown](https://docs.railway.com/deployments/deployment-teardown)):
1. The new deployment becomes active and receives all new traffic.
2. The old one stays up for `RAILWAY_DEPLOYMENT_OVERLAP_SECONDS` (no new traffic).
3. The old one then gets **SIGTERM**, and `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` later **SIGKILL**.

**Limits and defaults:**
- The docs don't state defaults. Sep 30's behaviour (in-flight requests got 502 at cutover) is consistent with little or no drain today.
- Railway staff put the draining maximum at ["a few hours"](https://station.railway.com/questions/what-is-the-max-permitted-value-for-rail-8fa552fc), so 180 is fine.
- Overlap can stay at its default; draining is what protects in-flight work.

**Until the variable is set, only the 90 s stale window below helps.** The graceful path needs the SIGTERM → SIGKILL gap.

## What changed
1. **Claim stale window 300 s → 90 s** (`franchise_routes._cpu_sim_claim_stale_seconds()`).
   - The 30 s heartbeat (merged Sep 29) means a live owner never goes 90 s without a refresh (3 missed beats).
   - Env `GOB_CPU_SIM_CLAIM_STALE_SECONDS`, floored at 3× the heartbeat.
   - A grep found nothing else relying on 300. The only hit was my own Sep 29 test assertion, now updated to 90.
   - phase-b's bounded wait (150 s) now outlasts a dead owner's claim, so a single phase-b always gets through.
2. **`CPU_SIM_RUNNING_STALE_SECONDS = 180`: unchanged, deliberately.**
   - It's **not a lock.** When the job doc is rebuilt, it resets a per-matchup row stuck in `running` to `pending` (`_build_cpu_sim_job`).
   - The CPU work list comes from results rows and game docs, not those rows. So a dead owner's `running` rows never block a re-sim.
   - `phase_b_required` depends only on phase-a being done and the job not being finalized.
   - The claim heartbeat does **not** refresh matchup rows. Shortening this below a slow pool run (which can pass 90 s) would let another request mark a live owner's in-flight games `pending`. It's a different mechanism from the claim, so the heartbeat doesn't cover it.
3. **Shutdown hook** (`api.py` `@app.on_event("shutdown")`, which runs after uvicorn's graceful drain):
   1. **`cpu_week_pool.shutdown_all_pools()`**:
      - Sets a process "shutting down" flag.
      - Cancels pending futures and terminates the worker processes of every live pool (CPU week, autotrain, practice squad; all are now tracked by `_tracked_executor`).
      - Once shutting down, the failure ladder **does not** rebuild the pool or fall back to in-process sims; it raises `ShutdownInProgress`.
      - The CPU-week persist loops (normal week and EOS/sim-rest) stop before their next game.
   2. **`franchise_routes.release_owned_cpu_sim_claims()`**:
      - Stops each claim's heartbeat.
      - Marks the claim inactive with an **owner-token filter**. Every claim this process acquires is recorded in `_owned_claims`; a claim another process has since taken is never touched.
      - It's idempotent, and it records `released_reason: "shutdown"`.
   - Startup clears the flag. Test isolation: a `conftest` autouse fixture clears it too.
4. **Graceful drain** (`start.sh`): `uvicorn … --timeout-graceful-shutdown "${GOB_GRACEFUL_SHUTDOWN_SECONDS:-150}"`.
   - On SIGTERM, uvicorn stops accepting connections and lets in-flight requests finish for up to 150 s, then runs the hook.
   - The flag exists in uvicorn 0.38 (local venv). Railway installs the latest, since `requirements.txt` doesn't pin it.
5. **Test harness:** `tests/conftest.py` gains an autouse fixture that clears the process "shutting down" flag.
   - A test that enters `with TestClient(app)` runs the app's shutdown hook. Later tests use module-level clients that never re-run startup, so without the fixture the flag would leak into them.
   - The new tests send a unique `X-Real-IP` per request. Tokenless phase-a is limited per IP (10/min), and they must not use up the shared `testclient` budget other complete-week tests rely on.

## What a player experiences if a deploy lands mid-advance
| | Before (Sep 30, observed) | After, with `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=180` | After, without it (or crash / OOM / SIGKILL) |
|---|---|---|---|
| In-flight start-cpu-sims / phase-b | Cut at cutover: **502** | **Finishes normally** if done within 150 s (typical) | Cut: 502 |
| Week advance still running after 150 s | – | The hook terminates the pool, stops the persist loop and **releases the claim** | – |
| Player's next phase-b (Locker Room retry, or the FCC resume that runs phase-b automatically) | Waited 150 s, then **503**, repeatedly, for **~5 min** until the 300 s stale window passed | **Re-claims immediately**. Only CPU games without results are re-simmed, then it finalizes | Blocked **≤ 90 s** after the last heartbeat. A single phase-b (150 s wait) outlasts it, so the player's first retry succeeds |
| Duplicate CPU results | – | None: see the tests below | None |

**Why there are no duplicate results** (tests below):
- The CPU work list skips any matchup that already has a results row or game doc.
- `results.{week}` is de-duplicated by matchup.
- `finalize_game` stats are applied once per season/week/pair (`applied_matchups`, fixed Sep 29) and once per game id (`applied_games`).

**Remaining race:** if the hook fires while the old process is **mid-write of a single game**, and the new deployment's request scans game docs in that same instant, that one matchup can get a second game doc. The finalize guards above still apply its stats once. That window is at most one game's persist (~0.2 s).

## What still can't survive a deploy (plainly)
1. **Live games in memory (`ongoing_games` / `LiveGameCache`).**
   - A player mid-quarter on the animated **Play Game** path loses the in-memory game when the process goes. The next `simulate-turn` returns **404**.
   - The client recovers from the saved doc or the last quarter-break resume anchor, so **turns played since the last quarter break are lost**.
   - The **Sim Game** path (`simulate-quarter`) reloads from Mongo at quarter granularity; the quarter in progress is re-simmed.
   - Nothing in this branch changes that. Making it survive needs per-turn persistence or sticky old-process routing (overlap) plus drain, which is a design decision.
2. **Anything past the drain.** A request still running after 150 s is cut (the hook releases its work so the retry is immediate). If the drain is unset, everything is cut at SIGTERM, as before, but with a 90 s instead of 300 s lock-out.
3. **The per-IP in-memory rate-limit counters** reset on deploy (harmless).

## Tests
`tests/test_graceful_deploy.py`, 19 tests:

| Area | Covered |
|---|---|
| Stale window | Default 90, env override, floor at 3 heartbeats, bad values. **Heartbeat 91 s old → re-claimable; 60 s old → not.** phase-b wait > stale window |
| Shutdown hook, claims | Releases **only this process's** claim (another owner's claim is untouched, byte for byte). Stops the heartbeat thread. **Idempotent** (a second call releases 0). Doesn't release a claim another process re-took after ours went stale. Normal release unregisters |
| Shutdown hook, pools | Terminates live workers and cancels futures (idempotent). Once shutting down, no new pool and **no in-process fallback**. The registered FastAPI shutdown handler runs both (called directly: entering the full app lifespan would install the process-wide RNG draw guard for every later test), and startup clears the flag |
| **Simulated mid-advance restart** (real endpoints, mongomock) | (a) The dead owner wrote the CPU results, then died holding the claim: phase-b re-claims after the stale window, finalizes, `results["1"]` has 2 rows (**each matchup once**), the CPU game is **not re-simmed** (sim core called once in total), and there's **exactly one CPU game doc**. A second phase-b is idempotent. (b) Died mid-pool with nothing persisted: phase-b re-sims the game **once** and advances. (c) A live owner (fresh heartbeat) still blocks: 503 after the wait, claim untouched. (d) After our own shutdown hook, the next phase-b succeeds **with a 0 s wait budget** |

**Real-process smoke** (local uvicorn 0.38, mongomock): the app acquired a claim, then SIGTERM.
- Log: `Shutting down` → `[CPU-SIM-CLAIM] shutdown: released 1/1 owned claim(s)` → claim `{active: False, released_reason: 'shutdown'}` → `Application shutdown complete` → exit.

**Related suites:** `test_graceful_deploy`, `test_tb_leak_detector`, `test_franchise_complete_week`, `test_endpoint_hardening_heartbeat`, `test_browse_rev` and `test_auth_hardening`: 172 passed.

## Unsure / notes
- **Suite warning count (a test-isolation trap):**
  - An early version of `test_graceful_deploy` entered `with TestClient(app)`. That runs the app's **startup** too, which installs the process-wide RNG draw guard, so every later test that drew from global `random` warned: **~42,500 warnings vs ~4,000**.
  - The test now calls the shutdown handler directly, and the warning count is back to baseline.
  - `test_tb_leak_detector` also enters the app lifespan, but it sorts near the end, so the effect is small there. Worth knowing for anyone adding lifespan tests.
- **Railway defaults:** the default `RAILWAY_DEPLOYMENT_DRAINING_SECONDS` isn't in the docs. I've assumed nothing; set it explicitly.
- **Drain and overlap don't make live games survive.** New traffic (the next `simulate-turn`) goes to the new deployment, which doesn't have the game in memory.
- **uvicorn drain vs sync endpoints:** uvicorn waits for connections to finish. A sync endpoint's worker thread keeps running if it's cut after 150 s, until the hook stops its pool and persist loop, or the process exits.

---
Gate: `Migration gates passed.`
Full suite (default config): `= 4193 passed, 20 skipped, 109 xfailed, 1 xpassed, 4142 warnings in 200.96s (0:03:20) =`. That's the baseline on the same develop (4174 passed, 4031 warnings) plus these 19 tests; no new failures; the XPASS is the pre-existing `test_resource_page_scoping` leaders-view test.
