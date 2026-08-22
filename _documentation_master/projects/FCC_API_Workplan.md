# FCC API Performance Work Plan

## Purpose

Improve Franchise Command Center (FCC) load time without introducing stale state, incorrect actions, broken recovery flows, authorization regressions, or unintended changes to recruiting, postseason, modal, and Team Builder behavior.

This is a staged performance project. Each phase must be measured independently and must pass a second- and third-order-effects audit before the next phase begins. Changes with unavoidable product or architecture tradeoffs must stop at a decision gate for approval.

## Current findings

The current slowdown is plausibly application-driven, with network latency multiplying the impact:

- The full-screen loading overlay remains visible until nearly all FCC initialization work finishes.
- Cold initialization performs a long series of awaited API requests.
- `/franchise/team-data` and the user roster are each requested more than once.
- Ordinary FCC requests append `profile=1`, causing backend `cProfile` work and adding a profiling report to responses.
- `/franchise/command-center/data` builds rankings, standings-derived summaries, game summaries, recruiting state, news, modal payloads, and other optional data synchronously.
- The observed last-game lookup misses its exact query and falls back to loading and scanning every game document for the week. A post-redeploy staging sample recorded 37 identical `FCC-LAST-GAME` misses (`matched_docs=0`) in one captured range. Each miss enters the broad compatibility fallback, so this is a confirmed repeated-query pattern rather than a one-off lookup failure.
- Recent recruiting work added more computation and queries to the central command-center endpoint.

These are code-trace findings, not yet a measured attribution of total load time. Phase 1 must establish that attribution before behavior changes.

## Operating rules

1. Measure before and after every material change.
2. Make one bounded class of change at a time.
3. Do not trade correctness or authorization for speed.
4. Treat cached FCC data as non-authoritative until its scope and freshness are proven.
5. Do not parallelize calls until their dependencies and mutation behavior are understood.
6. Do not split endpoints until every response field has a documented consumer.
7. Preserve a safe recovery path for legacy franchise and game data.
8. Stop for approval when a change introduces a user-visible or operational tradeoff.

## Success criteria

The project should produce measurable improvement in:

- Time until the FCC becomes usable.
- Time until the loading overlay disappears.
- Cold- and warm-load duration.
- Command-center backend duration.
- Database query count and scanned-document count.
- Total request count and duplicate request count.
- Initial response size and JSON serialization time.
- Reliability under slow networks and partial endpoint failure.

Correctness criteria are equally important:

- No stale week, team, roster, training, recruiting, or postseason state is actionable.
- Required recovery and blocking flows still run before normal actions are exposed.
- Modal and tutorial ordering remains correct.
- Ownership and team scoping remain enforced for every endpoint.
- Existing and legacy franchise saves remain supported according to an explicit policy.

---

## Phase 1: Establish a trustworthy baseline

### Work

Instrument and measure the current FCC load sequence without changing behavior. Test:

- Cold load with empty session cache.
- Warm load with valid session cache.
- Early and late regular season.
- Recruiting weeks 20-26.
- Postseason and signing/offseason weeks 27-36.
- Active-game resume and interrupted CPU-simulation recovery.
- Core and Team Builder teams.
- Normal and simulated high-latency networks.

Capture:

- Navigation start, first meaningful FCC paint, usable-page time, and overlay dismissal.
- Duration, response size, status, and start order for every API request.
- Backend duration and query count for `/franchise/command-center/data`.
- Full-document reads, repeated helper calls, and fallback queries.
- Time spent in database access, application computation, profiling, serialization, and transfer.
- Concurrent-user behavior.

### Audit

- Confirm whether any frontend code, test, operational tool, or diagnostic process consumes `profile_summary`.
- Verify that measuring does not materially alter the load being measured.
- Determine whether time increases by franchise week, number of saved games, recruiting pool size, or franchise document size.
- Separate server time from transfer/network time.
- Confirm repeated requests are genuine and not browser-dev-tool artifacts.

### Deliverable and gate

Produce a baseline report with a critical-path timeline and percentage contribution from each request or backend stage. No performance implementation should proceed without this baseline.

---

## Phase 2: Remove automatic profiling from normal FCC traffic

### Work

- Stop adding `profile=1` to ordinary FCC, roster, state, and standings requests.
- Retain profiling behind an explicit development or diagnostic mechanism.
- Ensure diagnostic profiling is not accidentally enabled for all production users.

### Expected benefit

- Reduced backend CPU work.
- Smaller JSON responses.
- Less profiler contention between concurrent requests.

### Second- and third-order audit

- Search frontend code, backend tooling, tests, and documentation for consumers of `profile_summary`.
- Compare profiled and unprofiled response bodies, excluding diagnostic fields.
- Confirm the query flag does not select any non-profiling behavior.
- Test concurrent requests with profiling disabled and with explicit profiling enabled.
- Verify developers retain a usable on-demand profiling workflow.

### Tradeoff and decision gate

Automatic per-request profiles will no longer be present in browser responses. If an active production workflow depends on them, decide whether to retain a restricted debug toggle or replace them with server-side sampled timing.

---

## Phase 3: Remove duplicate frontend requests

### Work

- Reuse the initial `/franchise/team-data` result in `loadTeamData()` where contracts match.
- Reuse the first roster result instead of requesting the same roster again.
- Define one authoritative source for header chemistry.
- Cache in-flight promises as well as completed values so concurrent consumers cannot start duplicate calls.
- Avoid shared-object mutation by copying or normalizing cached response data where necessary.

### Second- and third-order audit

- Inventory every field and transformation expected by each current consumer.
- Verify `RosterLoader` does not add state or transformations missing from a raw roster response.
- Test freshness after training, a completed game, recruiting/signing, player cuts, team modification, week advancement, and team/franchise switching.
- Confirm failed in-flight promises are evicted and retryable.
- Confirm request consolidation does not remove required authorization or franchise scoping.
- Verify session cache invalidation remains correct.

### Tradeoff and decision gate

Request reuse increases coupling and makes invalidation more important. If two consumers require materially different freshness or response contracts, retain separate calls and consider backend consolidation instead.

---

## Phase 4: Fix last-game lookup and rich game-document scanning

### Confirmed evidence

- Post-redeploy staging logs contained 37 exact last-game lookup misses in the captured range.
- The repeated lookup used the same franchise, week, user team, and matchup for many calls.
- The exact query searches `games` by `week`, string `franchise_id`, and the two `team1_id`/`team2_id` permutations.
- When it returns no documents, the current fallback loads all game documents for that franchise/week and filters their possible team-identity fields in application code.
- One miss therefore produces at least an exact query plus a broader fallback query; 37 observed misses imply approximately 74 database queries before accounting for surrounding FCC work.
- This is distinct from the environment-wide Railway slowdown that improved after redeployment. It remains a plausible contributor to FCC-specific latency and unnecessary database load.

### Work

- Identify all current and historical game-document identifier shapes.
- Determine why the exact lookup misses the observed stored games.
- Define a canonical indexed lookup compatible with valid current records.
- Use narrow projections to locate the candidate game.
- Fetch rich box-score data only for the selected game when POTG requires it.
- Resolve last-game data once per command-center request and reuse it.
- Trace the frontend and backend call graph responsible for repeatedly invoking the lookup with identical inputs; eliminate duplicate FCC requests and repeated helper evaluation without weakening freshness guarantees.
- Add bounded timing and invocation-count telemetry so the exact lookup, fallback, documents scanned, and per-request reuse can be verified before and after the change.
- Keep a measured, observable compatibility fallback for legacy records if necessary.

### Second- and third-order audit

- Test string/ObjectId differences and home/away identifier permutations.
- Verify the stored `franchise_id`, `team1_id`, `team2_id`, `home_team_id`, `away_team_id`, and nested `teams` formats before changing the canonical query.
- Test old saves, current saves, duplicate game documents, partial saves, and interrupted games.
- Preserve selection of the richest valid record when duplicates exist.
- Test overtime, forfeits, tournament games, zero-score finals, and missing box scores.
- Verify POTG remains deterministic and selects the same correct player.
- Inspect database query plans and existing indexes before proposing a new index.
- Measure storage and write-amplification cost for any new compound index.
- Confirm memoization or request reuse cannot return a previous week, previous franchise, previous controlled team, or pre-finalization game after week advancement or navigation.
- Confirm a cached miss is invalidated when a game is finalized, recovered, or rewritten during the same user session.
- Measure log volume and remove or downgrade high-frequency warning diagnostics only after replacement telemetry proves the lookup is healthy.

### Tradeoff and decision gate

An indexed canonical query is fast but may not recognize malformed legacy records. Decide whether to:

- Support the fallback indefinitely.
- Backfill/migrate legacy records and retire it.
- Support the fallback temporarily with telemetry and a removal threshold.

---

## Phase 5: Parallelize independent initialization work

### Work

Build an explicit request dependency graph. Keep identity, ownership, recovery, and required state ordered; run independent secondary calls concurrently with bounded concurrency.

Likely structure:

```text
Authoritative shell
|-- recovery decision
|-- roster/state
|-- standings
|-- team data
|-- team metadata/colors
`-- playbook status
```

### Second- and third-order audit

- Verify authentication and authoritative team identity exist before team-scoped calls start.
- Audit all GET handlers for hidden writes or state creation before parallelizing them.
- Add stale-response protection for navigation, team changes, and week changes.
- Test partial failures and retries.
- Measure database connection-pool pressure and server CPU under concurrency.
- Confirm faster browser completion does not increase total database work.
- Test two or more simultaneous FCC users.

### Tradeoff and decision gate

Parallelism lowers wall-clock time but increases instantaneous backend load. Choose the concurrency limit using measured server and database capacity.

---

## Phase 6: Separate page usability from complete hydration

### Work

Define the minimum authoritative FCC shell required before dismissing the full-screen overlay. Load secondary cards and inactive tabs behind localized loading states.

Likely critical data:

- Ownership/access result.
- Authoritative week, season, team ID, and team identity.
- Training and progression state.
- Active-game and CPU-simulation recovery state.
- Mandatory cut or other blocking state.
- Primary action-button state.

Likely deferrable data:

- Full rankings and standings.
- Full roster details.
- Team measures and game-plan summaries.
- Playbook warning decoration.
- News and recruiting presentation.
- Opponent leaders and POTG presentation.
- Inactive-tab data.

### Second- and third-order audit

- Ensure stale cached actions can never be clicked.
- Test session-cache data from a previous week or controlled team.
- Ensure required recovery and mandatory modals occur at the correct time.
- Audit tutorial, championship, recruiting, walk-on, region-bye, and archetype modal sequencing.
- Provide accessible localized loading and error states.
- Ensure secondary failures offer retry or a stable error state.
- Prevent deferred responses from overwriting newer state.
- Verify analytics and music initialization still occur once and at the intended lifecycle point.

### Tradeoff and decision gate

Progressive rendering provides the largest perceived improvement but allows individual cards to populate after the main page appears. Product approval is required to choose between:

- Progressive rendering with safe localized loading states.
- Atomic rendering while optimizing only the underlying request path.

---

## Phase 7: Reduce the command-center endpoint's scope

### Work

Create a field-to-consumer inventory for the complete `/franchise/command-center/data` response. Classify fields into:

- Required shell data.
- Home-tab summaries.
- Recruiting state.
- Rankings and standings.
- Modal/event data.
- Inactive-tab data.

Then remove unnecessary initial computation or introduce focused section endpoints. Prefer a small authoritative shell plus lazily loaded sections unless measurements support another boundary.

### Second- and third-order audit

- Search JavaScript, HTML, shared modules, tests, and documentation for every response field.
- Audit dynamic property access that static search may miss.
- Preserve mandatory modal and recovery payload availability.
- Prevent inconsistent snapshots during week transitions.
- Preserve ownership checks on every new endpoint.
- Confirm recruiting data cannot leak across teams.
- Test regular season, recruiting, postseason, offseason, and legacy saves.
- Ensure one optional-section failure no longer fails the entire FCC.
- Compare total requests, queries, payload size, and backend time after splitting.

### Tradeoff and decision gate

- Focused endpoints improve isolation and caching but add round trips.
- A composite endpoint reduces round trips but risks recreating the current bottleneck.
- Section responses may represent slightly different moments if state changes mid-load.

Approve endpoint boundaries only after reviewing the field-consumer inventory and consistency requirements.

---

## Phase 8: Audit and optimize recent recruiting additions

### Work

Measure and audit:

- Recruiting-wire generation.
- Recruit-name queries.
- Team-name map generation.
- Invite-recruit resolution.
- Potential-rating calculation.
- Signing-result and recruiting modal payload construction.
- Repeated team-map and last-game helper calls.

Apply optimizations in this order:

1. Skip computation outside relevant weeks and states.
2. Reuse request-scoped team, recruit, and last-game data.
3. Move presentation-only recruiting data off the shell endpoint.
4. Consider durable precomputed summaries only if the first three are insufficient.

### Second- and third-order audit

- Preserve unseen counts and exact seen-week semantics.
- Prevent recruiting or walk-on spoilers before their intended reveals.
- Test weeks 1-19, 20-26, 27-34, 35, 36, and season rollover.
- Test empty pools, full boards, signed recruits, walk-ons, and legacy recruits.
- Keep projected-potential values consistent across FCC, roster, recruiting hub, and signing reveal.
- Preserve Team Builder display names without replacing stable identity keys.
- If precomputation is introduced, audit invalidation after every recruiting mutation and recovery from partial writes.

### Tradeoff and decision gate

Durable precomputation speeds reads but adds complexity and failure modes to recruiting writes. It requires explicit approval and clear evidence that conditional calculation and request-scoped reuse are inadequate.

---

## Phase 9: Database-query and payload audit

### Work

For every FCC endpoint:

- Count queries and documents examined.
- Record query shape, projection, and query plan.
- Find repeated reads of franchises, FTD, teams, recruits, and games.
- Identify full-document reads where narrow projections are sufficient.
- Measure serialized response size and encoding time.
- Check whether large embedded franchise fields are loaded unnecessarily.
- Review existing indexes before adding new ones.

### Second- and third-order audit

- Ensure narrower projections include every legacy-branch dependency.
- Avoid redundant indexes.
- Measure index storage, memory, and write costs.
- Ensure caches cannot cross user or franchise boundaries.
- Do not treat process-local caches as authoritative in multi-worker deployments.
- Confirm cached objects are not mutated globally.

### Deliverable

Provide a before/after table of query count, documents examined, payload size, backend duration, and total load time for each baseline scenario.

---

## Phase 10: Regression and side-effect validation

Every implementation phase must pass four audits:

1. **Functional audit:** all FCC features still behave correctly.
2. **State/freshness audit:** cached, deferred, or out-of-order data cannot expose an incorrect action or view.
3. **Security audit:** ownership and team scoping remain enforced.
4. **Performance audit:** elapsed time, query count, payload size, or resource use measurably improves without simply shifting the cost.

### Required scenario matrix

- Cold and warm cache.
- Fast and slow network.
- New and mature franchises.
- Regular season, recruiting, postseason, and offseason.
- Before and after training.
- Before and after game completion.
- Interrupted game and CPU-simulation recovery.
- Core and Team Builder teams.
- Current and legacy save shapes.
- Secondary endpoint failure and retry.
- Rapid reload and double navigation.
- Team and franchise switching.
- Multiple concurrent FCC users.

Use targeted unit and integration tests plus a browser-level load test for each material phase.

## Recommended implementation order

1. Establish the baseline and performance harness.
2. Remove automatic profiling.
3. Eliminate duplicate requests.
4. Fix the last-game fallback query.
5. Parallelize proven-independent requests.
6. Shorten the loading overlay's critical path.
7. Slim or split the command-center endpoint.
8. Optimize recruiting computation.
9. Complete the database, payload, regression, and concurrency audit.

The first four items are comparatively bounded and should produce measurable gains without redesigning the FCC lifecycle. Overlay and endpoint-boundary changes have the largest second- and third-order risk and should follow the contract and timing audits.

## Approval-required decisions

Pause implementation and present evidence, alternatives, and measured tradeoffs before:

- Showing the FCC while secondary cards are still loading.
- Relaxing atomic consistency between FCC sections.
- Adding indexes with meaningful storage or write cost.
- Dropping support for malformed legacy game documents.
- Introducing durable recruiting-summary precomputation.
- Increasing parallel backend traffic beyond measured capacity.
- Changing tutorial, reveal, recovery, or mandatory-modal timing.

## Completion definition

The work is complete only when:

- The agreed performance targets are met across the scenario matrix.
- No unresolved correctness, freshness, security, or lifecycle regression remains.
- All accepted tradeoffs are documented.
- Any rejected optimization is recorded with its evidence and reason.
- Performance instrumentation remains available for future regression detection without imposing automatic profiling overhead on ordinary users.
