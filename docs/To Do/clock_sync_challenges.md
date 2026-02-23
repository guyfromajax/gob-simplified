# Clock Sync Challenges (Real Time Clock + Shot Clock)

## Goal
Keep game clock and shot clock behavior fully consistent across:
- backend possession/turn resolution
- frontend animation timing and display countdown
- boundary rules (shot clock/game clock at 0)

## Current Reality
The system is improved, but still not perfectly synced. We currently have two partially independent timing models:
- Backend computes `time_elapsed` in game-seconds from turn logic.
- Frontend decrements visible clocks during animation execution windows.

When these diverge, the frontend clock can hit 0 before backend logic enforces boundary outcomes, or vice versa.

## Key Symptoms Observed
1. Frontend elapsed > backend elapsed on many impact turns.
   - Example pattern: FE `22` vs BE `10`, FE `32` vs BE `22`.
2. Repeated `Ignoring non-monotonic clock update` in frontend.
   - This indicates frontend already counted further down, then rejected a backend update that would move clock backward.
3. Shot clock/game clock 0 enforcement has been inconsistent.
   - Missed forced-shot/violation behavior in some cases.
   - Prior infinite-loop behavior near game clock 0 (partially improved).
4. Quarter end has occurred several turns after visual clock reached 0.
5. Timeout persistence issues surfaced during clock-system rollout (now largely corrected for user path; computer timeout path required symmetry fixes).

## Confirmed Technical Causes
1. **Single-source-of-truth conflict**
   - Backend and frontend both effectively estimate elapsed time, but from different signals.

2. **Boundary enforcement context bug**
   - Boundary checks have used mutated post-resolution context in some flows (`state`/`result_type` mismatch), causing incorrect branch decisions.
   - Seen in logs where pre-check state/result combinations are not semantically aligned with turn entry.

3. **Turn-chain complexity**
   - Shot/rebound/outlet/free-throw follow-ups can include additional animation windows that frontend counts, while backend may only count core turn elapsed.

4. **Clock speed confusion risk**
   - `350ms` is frontend wall-clock pacing for a game-second, not backend elapsed logic.
   - Backend `time_elapsed` is game-seconds only; ms speed does not fix model mismatch.

## What Has Improved
1. Added stronger tracing:
   - Backend turn entry + boundary traces.
   - Backend per-turn elapsed logs.
   - Frontend per-turn actual elapsed logs + delta vs backend.
2. Added monotonic guard in frontend to prevent backward clock jumps.
3. Timeout data persistence became more robust after frontend displayed-time reconciliation and user/computer timeout path alignment.
4. OREB shot-clock reset path was corrected.

## Why “Perfect” Is Hard in Current Design
Exact-at-0 outcomes are hard when:
- backend resolves clocks at turn boundaries,
- frontend displays second-by-second countdown during animation,
- and turn payloads include chained events with variable visual duration.

Without one authoritative timing contract, drift is expected.

## Strategic Options
1. **Backend-authoritative timing contract (recommended)**
   - Backend decides full turn elapsed and all boundary outcomes before commit.
   - Frontend renders to that contract and never invents additional elapsed seconds.

2. **Frontend-authoritative elapsed reporting (not recommended for core rules)**
   - Frontend reports actual elapsed back to backend.
   - Adds complexity/race risk for deterministic simulation and fairness.

3. **Hybrid (current trajectory)**
   - Works, but remains fragile unless contract is tightened significantly.

## Practical Path Forward
1. Make backend elapsed contract authoritative per turn.
2. Enforce boundary truncation before commit:
   - game clock precedence
   - then shot clock logic
3. Ensure boundary checks use immutable turn-entry context.
4. Keep FE monotonic guard, but reduce need for corrections by matching FE countdown windows to backend elapsed contract exactly.
5. Continue FE/BE elapsed delta logging until deltas are near-zero for all major turn classes:
   - skeleton turns (HCO/HCT/FCP)
   - CG turns (fast break style)
   - no-impact turns (FT/BIP/SIP)

## Open Questions to Resolve
1. Should every animation sub-phase consume clock, or only designated gameplay phases?
2. For shot chains, should rebound/outlet time be in the same turn elapsed or explicitly split into next turn(s)?
3. At shot clock 0, should forced-shot vs violation remain temporary 50/50, or become deterministic by tactical context?
4. Should final-turn logic use a dedicated pipeline isolated from normal turn routing to avoid state contamination?

## Bottom Line
The project is close, but current drift confirms this is a contract problem, not just a bug list.  
To make execution “perfect,” backend and frontend must share one authoritative elapsed-time model and boundary-truncation model, then instrument to verify zero drift.
