# `tournament_id` Sunset

**Status:** Proposed work plan; implementation not started  
**Created:** July 24, 2026  
**Scope:** Retire the legacy standalone Tournament Mode and its
`tournament_id` compatibility surface without disrupting Franchise tournament
weeks  
**Important:** This plan does not authorize deletion of production tournament
documents or other persisted user data.

---

## 1. Executive Summary

`tournament_id` is not 100% dormant and is not safe to delete as an isolated
variable.

The old standalone Tournament Mode is no longer exposed through the intended
mode-selection flow, but its implementation remains live and reachable. The
backend still mounts its router, its API endpoints still read and write
tournament documents, direct frontend pages can still start and resume the
mode, and shared gameplay screens still branch on `mode === "tournament"` and
propagate `tournament_id`.

The safe approach is to retire the complete standalone Tournament Mode
compatibility surface in deliberate stages. Active Franchise tournament weeks
must remain supported. They are a separate system whose authority is
`franchise_id`, franchise week state, `tournament_schedule`, and
`tournament_context`; they do not require the legacy standalone
`tournament_id`.

---

## 2. Audit Conclusion

### 2.1 What is obsolete

The sunset target is the original standalone Tournament Mode:

- tournament selection and creation outside Franchise;
- standalone tournament documents and bracket progression;
- tournament-specific game launch and resume flows;
- standalone tournament result persistence;
- standalone tournament roster, scouting, training, and team-data routes;
- shared-page branches whose only purpose is `mode === "tournament"`;
- the `tournament_id` field used to connect games and requests to that mode.

### 2.2 What remains active

The legacy system remains executable in the current codebase:

- `BackEnd/api/api.py` imports and mounts `tournament_router`;
- `BackEnd/api/tournament_routes.py` exposes creation, current-state, deletion,
  round simulation, result saving, team data, scouting, roster, training, and
  remaining-game operations;
- tournament selection and tournament management frontend assets can still
  initiate and operate the mode;
- gameplay, court entry, finalization, game-plan, playbook, roster, training,
  timeout, and navigation code still propagate or branch on `tournament_id`;
- game loading and simulation code still loads and persists tournament-linked
  records;
- ownership, pointer validation, and retention logic still recognize
  tournament documents and tournament-linked games.

Therefore, removal of only the request field or only the backend model would
break reachable paths and leave a partially retired feature.

### 2.3 What must not be removed

Franchise tournament weeks are active product behavior and are outside the
sunset target. Preserve:

- `franchise_id`;
- the Franchise season week and schedule;
- `tournament_schedule`;
- `tournament_context`;
- Franchise tournament bracket/state;
- Franchise CPU simulation and persistence;
- Franchise tournament UI and navigation;
- any generic use of the word “tournament” that refers to a Franchise
  tournament week rather than the legacy standalone mode.

The removal criterion is semantic, not a global text replacement.

---

## 3. Why an Isolated Variable Deletion Is Unsafe

`tournament_id` currently acts as more than a dormant schema field. Depending
on the path, it is used as:

- request context;
- URL/query context;
- a game-document relationship;
- the lookup key for a standalone tournament document;
- a persistence destination for results and state;
- an ownership and access-control input;
- a navigation and page-mode discriminator;
- a retention signal preventing linked games from being removed;
- a compatibility branch in shared Franchise-adjacent endpoints.

Deleting the name without retiring those behaviors would create failures such
as:

- requests accepted by the frontend but rejected by backend models;
- completed games that cannot save their result;
- old direct URLs that enter a broken partial mode;
- ownership checks against missing context;
- incorrect cleanup or retention of tournament-linked games;
- shared screens selecting the wrong data source;
- confusion between a legacy standalone tournament and an active Franchise
  tournament week.

---

## 4. Required Product Decision Before Implementation

Confirm whether existing standalone Tournament Mode saves must remain playable.

If they do not need to remain playable, implementation may intentionally retire
the endpoints and redirect or reject old direct links. Persisted data should
still be left intact unless a separate data-retention decision explicitly
authorizes archival or deletion.

If old saves must remain playable, `tournament_id` cannot be fully sunset yet.
The appropriate result would instead be to rename and isolate the legacy
surface, clearly marking it as compatibility code.

This is the only material product decision required before beginning the
retirement.

---

## 5. Proposed Retirement Sequence

### Phase 0 — Freeze and inventory

Before changing behavior:

1. Record every executable `tournament_id` reference in backend and frontend
   code.
2. Classify each reference as:
   - legacy standalone Tournament Mode;
   - active Franchise tournament week;
   - shared generic code;
   - documentation, test, fixture, or migration only.
3. Inventory direct routes, pages, request models, stored fields, indexes,
   ownership checks, pointer checks, and retention policies.
4. Establish tests for active Franchise tournament-week launch, game play,
   CPU-week completion, result persistence, bracket advancement, training, and
   resume behavior.
5. Capture current standalone route behavior so its intentional retirement is
   distinguishable from accidental breakage.

No database cleanup is part of this phase.

### Phase 1 — Close standalone entry points

Retire user entry into the old mode before removing its internal data contract:

- remove or redirect the standalone tournament selection page;
- remove or redirect tournament management pages;
- remove legacy navigation links and launch actions;
- stop creating new standalone tournament documents;
- return an intentional, documented response for old direct URLs;
- ensure active Franchise tournament-week links continue to use
  `franchise_id`.

Closing entry points first prevents new legacy sessions from being created
while deeper compatibility paths are removed.

### Phase 2 — Retire the standalone backend router

After entry points are closed:

- unmount `tournament_router` from the application;
- remove standalone create/current/delete/state endpoints;
- remove round simulation and “sim remaining” endpoints;
- remove standalone save-result behavior;
- remove standalone team-data, scouting, roster, and training endpoints;
- remove the standalone Tournament Manager and its helpers once no caller
  remains;
- remove imports, request/response models, and tests belonging solely to that
  router.

Do not remove Franchise routes or Franchise tournament-week helpers merely
because they contain tournament terminology.

### Phase 3 — Remove shared frontend compatibility branches

Trace each shared screen from its entry context and remove only the standalone
mode branch:

- game launch and boot context;
- court/gameplay state;
- game finalization;
- game-plan and playbook loading/saving;
- roster and team-data fetches;
- training and training-report fetches;
- timeout/navigation/resume behavior;
- any local-storage, session-storage, or URL propagation;
- request payloads and query strings carrying `tournament_id`.

The surviving shared contract should distinguish normal and Franchise contexts
without a legacy standalone tournament branch.

### Phase 4 — Remove shared backend compatibility branches

Remove standalone-mode behavior from shared APIs and engine entry points:

- request models that accept `tournament_id`;
- `mode == "tournament"` branches;
- tournament-document loads during game creation and simulation;
- tournament-specific result and state persistence;
- tournament-specific roster, team-data, game-plan, playbook, scouting, and
  training lookups;
- propagation into managers and game state;
- response fields emitted only for the old mode.

Keep game-engine basketball behavior mode-agnostic wherever possible. This
sunset should simplify context selection, not alter turn resolution, RNG, or
simulation results for surviving modes.

### Phase 5 — Retire storage relationships and operational protections

Once no runtime caller depends on the relationship:

- stop writing `tournament_id` to new game documents;
- remove it from shared serializers and projections;
- remove standalone tournament pointer and ownership validation;
- update retention logic that protects games solely because they have a
  standalone `tournament_id`;
- assess obsolete indexes and schema documentation;
- decide separately whether historical fields remain tolerated on old
  documents.

Historical data should be ignored safely before any decision to migrate,
archive, or delete it.

### Phase 6 — Remove dead implementation and tests

After runtime removal is verified:

- delete legacy-only frontend assets and backend modules;
- remove fixtures and tests whose only purpose was the standalone mode;
- rewrite shared tests around the surviving normal and Franchise contracts;
- remove stale comments and documentation that imply Tournament Mode is still
  available;
- retain historical release notes where useful, clearly marking the feature as
  sunset.

### Phase 7 — Repository guard

Add a narrowly scoped guard that fails when new executable legacy references
are introduced.

The guard should check runtime source for:

- `tournament_id`;
- `mode === "tournament"`;
- `mode == "tournament"`;
- legacy standalone route paths and page names.

Allow explicit exceptions for migrations, archived documentation, or historical
fixtures only when each exception is documented. Do not require the literal
word “tournament” to disappear because Franchise tournament weeks remain
active.

---

## 6. Verification Plan

### 6.1 Franchise tournament-week regressions

Verify at minimum:

- a Franchise reaches a tournament week;
- the tournament schedule and context load;
- the user game launches and resumes;
- CPU games simulate;
- the user result and CPU results persist;
- the bracket advances correctly;
- the next Franchise week is selected correctly;
- roster, scouting, game-plan, playbook, and training screens use the Franchise
  data source;
- refresh and direct-navigation flows preserve `franchise_id`;
- no surviving request requires `tournament_id`.

### 6.2 Normal-mode regressions

Verify:

- a normal game can be created, played, resumed, and finalized;
- shared roster, playbook, game-plan, training, and navigation paths do not
  expect a tournament identifier;
- game retention and cleanup still apply their intended normal-mode policies.

### 6.3 Intentional legacy behavior

Verify:

- old standalone tournament entry URLs redirect or return the agreed sunset
  response;
- standalone APIs are unavailable after router retirement;
- old tournament-linked records do not crash generic game/history queries;
- no new standalone tournament or tournament-linked game document can be
  created;
- no persisted records are deleted by the code-removal deployment.

### 6.4 Performance and determinism

This is primarily a context and persistence cleanup, but it touches simulation
entry points. Follow `Sim_Perf_Capstone.md`:

- add no database calls inside game-engine loops;
- do not change RNG draw order;
- use seeded exact-diff verification for non-drawing changes;
- run measurements with `PYTHONHASHSEED=0`;
- compare representative full-sim timing before and after;
- do not edit source while a measurement run is in flight.

The sunset should be performance-neutral or a small improvement.

---

## 7. Acceptance Criteria

The sunset is complete only when:

1. No user-accessible flow can create or enter standalone Tournament Mode.
2. The standalone tournament router and manager are no longer mounted or
   called.
3. No executable frontend request sends `tournament_id`.
4. No executable shared backend request model or runtime branch requires
   `tournament_id`.
5. New game documents no longer store `tournament_id`.
6. Ownership, pointer, and retention logic no longer depends on the legacy
   relationship.
7. Active Franchise tournament weeks pass end-to-end regression coverage.
8. Normal game flows pass end-to-end regression coverage.
9. Historical records containing the field are tolerated without runtime
   failure.
10. A repository guard prevents accidental reintroduction of the legacy mode.
11. No production data has been deleted without a separate, explicit data
    retirement plan and authorization.

---

## 8. Non-Goals

This project does not:

- remove or redesign Franchise tournament weeks;
- rename all tournament-related concepts;
- rewrite bracket logic that is active within Franchise;
- change basketball simulation behavior;
- alter shot, block, possession, transition, or animation systems;
- delete historical database records;
- bundle unrelated persistence or performance refactors into the sunset.

---

## 9. Recommended First Implementation Slice

After the old-save policy is confirmed, begin with a reversible boundary slice:

1. add Franchise tournament-week regression coverage;
2. remove or redirect standalone frontend entry points;
3. stop creation of new standalone tournaments;
4. leave existing read paths temporarily intact;
5. verify normal and Franchise flows in staging.

This establishes that the active product no longer enters the legacy system
before shared contracts and stored relationships are removed. The remaining
phases can then proceed in small, testable changes rather than one high-risk
global deletion.

