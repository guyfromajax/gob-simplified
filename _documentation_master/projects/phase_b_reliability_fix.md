# Phase B Reliability Fix

**Status:** Open  
**Date filed:** 2026-07-18  
**Related:** `Z-Completed/franchise_cpu_sim_resume_plan.md`, `Press_Conference_System.md`, `End_Of_Game_System.md`

## Problem

After a franchise user game finishes, the client starts `POST /franchise/complete-week/phase-b` and holds that HTTP request open until CPU week sims + week finalize complete. Under a full week slate, that request can die (proxy timeout, worker kill, connection drop). The browser surfaces this as CORS / `Failed to fetch`, and the EOG UI treats phase B as failed even when the backend may still be working or may finish later.

This is a **reliability / architecture** issue, not a need to buy more CPU capacity first.

## Incident (staging, 2026-07-18)

### Console (user-facing)

1. Franchise game finalized successfully (`week=26`, phase A OK).
2. `POST /franchise/complete-week/start-cpu-sims` returned **409**.
3. `POST /franchise/complete-week/phase-b` failed:
   - Browser: blocked by CORS / `net::ERR_FAILED`
   - App: `[gameCompletionPopup] background phase-b failed to start: TypeError: Failed to fetch`

### Backend

- Heavy CPU-sim logging during phase B / week close for the same franchise.
- Week eventually persisted (`completed_week=26` → `next_week=27`) in the same window.
- Railway log rate limits hit (noise, not root cause).

### Red herrings (do not treat as this bug)

| Signal | Why ignore for this fix |
|---|---|
| `tournamentId is missing` | Expected for franchise games (not tournament save path). |
| `start-cpu-sims` **409** after phase A | Expected: “user game already saved; use phase-b.” Client already treats 409 as success. |
| Sentry `PYTHON-FASTAPI-6H` / `🚨 [BAT-OOB ORIENTATION]` | Separate sim orientation diagnostic (`logging.error` during a CPU sim). Does not abort phase B. That sample was also **week 25**, not the week-26 console failure. |
| Player PTS vs team score warnings | Scoring-path noise; not the fetch failure. |
| Box-score display-name vs id key warnings | Finalize keying noise; not the fetch failure. |

### Diagnosis

| Question | Answer |
|---|---|
| Logic bug in complete-week sequencing? | No — phase A succeeded; 409 on start-cpu-sims is expected after phase A. |
| Pure CORS misconfiguration? | No — missing `Access-Control-Allow-Origin` is the browser symptom when the response never returns cleanly (timeout / proxy / drop). |
| Root cause of user-facing failure? | **Long synchronous phase-B HTTP call dying under heavy CPU-sim load.** |
| Did more CPU alone fix this class of failure? | No — capacity may shorten wall time, but refresh/close/timeout still break a single long fetch. |

## Intended product behavior

1. **Early overlap:** when the user starts/sims their franchise game, `bootGame.js` fires `POST /franchise/complete-week/start-cpu-sims` so non-user games run during play.
2. **Phase A:** user result saved; week not advanced.
3. **Phase B at EOG:** started when the completion popup appears (`franchisePhaseBClient.js` / `gameCompletionPopup.js`). Should only need to finish missing CPU games + finalize/advance week.
4. **Idempotent close:** re-calling phase B after week advance should succeed safely.
5. **User never stuck** if the browser drops the in-flight request: UI should resume / retry / poll, not treat the week as dead.

## Current gap

- Phase B is still a **single long request** from the browser’s point of view.
- Frontend single-flight maps (`franchisePhaseBClient.js`, `franchiseStartCpuSimsClient.js`) are **tab-local** — lost on refresh/close.
- On `Failed to fetch`, EOG logs a warning; there is no durable “still running / retry on FCC” contract wired as the primary recovery path.
- Durable job scaffolding exists / is planned under `franchises.cpu_sim_jobs.{week}` (see resume plan), but the **product flow is not yet fully observable and resumable** across request death.

## Fix direction (priority order)

### 1. Reliability architecture (required)

Implement / finish the resumable CPU-sim job model from `Z-Completed/franchise_cpu_sim_resume_plan.md`:

- Durable `cpu_sim_jobs.{week}` with per-matchup status.
- `start-cpu-sims` and phase B run **only incomplete** matchups.
- Stale `running` reclaim after timeout.
- Phase B remains the **authority to advance the week** only when the slate is complete.
- Client **polls or safely retries** instead of depending on one unbroken fetch.

### 2. Client resilience (required, can ship incrementally)

- On phase-B network failure: treat as “simming may still be in progress,” not hard failure.
- FCC / locker navigation: re-enter phase B or job status when `franchise_complete_week_pending` is set.
- Keep “Simming Computer Games” waiting UI until job `complete` / week advanced / idempotent success.
- Do not show a dead-end error solely because the first background fetch dropped.

### 3. Overlap health (required check)

Verify early `start-cpu-sims` actually runs and makes progress **during** the user game so EOG phase B is short.

- Confirm `bootGame.js` fires once per week with a valid `week` query param.
- Confirm non-fatal client errors are not silently preventing overlap.
- Confirm 409 after phase A does not imply “CPU sims never ran” — only that the early endpoint is closed once phase A is done.

### 4. Capacity (optional, last)

Add Railway / worker capacity **only if**, after overlap + resume/retry:

- CPU matchups still cannot finish during a normal user-game duration, and
- phase B still has a large unfinished slate at EOG.

Capacity is an optimization, not the primary fix for request-death UX.

### 5. Ops hygiene (secondary)

- Reduce warning-level sim spam that hits Railway log rate limits during full-slate sims.
- Keep BAT-OOB orientation as its own gameplay bug (ball flies to wrong end); do not couple it to this reliability work.

## Acceptance criteria

- [ ] Killing or timing out the browser’s phase-B fetch does **not** leave the franchise stuck for that week.
- [ ] Returning to FCC (or re-opening EOG/locker flow) resumes or completes week close without re-simming finished matchups.
- [ ] Phase B advances the week only when all scheduled matchups have canonical results.
- [ ] Early `start-cpu-sims` measurably reduces unfinished matchups by EOG on a full week slate.
- [ ] User-facing copy stays on “Simming Computer Games” / progress until done; no false “failed to start” dead-end from a dropped fetch alone.
- [ ] Staging reproduction of the 2026-07-18 pattern (long phase B under load) no longer produces a stuck client.

## Key code pointers

| Area | Path |
|---|---|
| Early CPU kickoff | `FrontEnd/static/js/phaser/bootGame.js` → `maybeFireFranchiseStartCpuSimsOncePerWeek` |
| Start-CPU client | `FrontEnd/static/js/phaser/utils/franchiseStartCpuSimsClient.js` |
| Phase B client | `FrontEnd/static/js/phaser/utils/franchisePhaseBClient.js` |
| EOG start of phase B | `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js` |
| Start-CPU / phase B routes | `BackEnd/api/franchise_routes.py` (`/franchise/complete-week/start-cpu-sims`, `/phase-b`) |
| Full resume design | `_documentation_master/projects/Z-Completed/franchise_cpu_sim_resume_plan.md` |

## Decision log

| Date | Decision |
|---|---|
| 2026-07-18 | Classified staging “phase-b CORS / Failed to fetch after CPU sims” as **timeout under heavy synchronous phase-B load**, not a complete-week logic bug and not “buy more CPU first.” |
| 2026-07-18 | Primary fix path: **resumable/observable jobs + client retry/poll**; capacity only after overlap/resume prove insufficient. |
