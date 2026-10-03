# READY — flag-registry.md (verified, with two corrections)

Verified 2026-09-25. **Accepted.** Branch `feature/flag-registry` off develop (8d6d8252d).
Not merged. Nothing retuned, no constant's value changed.

## Gates — all passed, verified independently
- equiv-v3: **240/240** fingerprint AND draws, 480/480 checks, 0 mismatches. Seed 8000 played
  SD=1 = fp `0c3389cd41d0bbef`, draws `75363` ✓. This was the gate that mattered — the refactor
  rewires every sim flag read, so a mistranscribed default would have moved it.
- Suite **3,712 passed / 0 failed** (up from 3,651; the delta is new tests, not un-skips).
- CALL-TIME READS PRESERVED: grepped `feature_flags.py` myself — the only `os.environ` mentions
  outside function bodies are docstring lines. No import-time snapshot, so the per-process env
  harnesses (`GOB_STRICT_EXCEPTIONS`, `GOB_COLLISION_*`) still behave.
- Generated parity test is genuinely GENERATED — `scratch_gen_flag_test.py` AST-walks the tree as
  it was BEFORE the registry existed. 47 passed, 45 defaults checked. This is the right method;
  hand-transcribing would have reproduced any slip twice.
- No per-game round trip: folded into the existing `/api/init-game` response. 20.2 µs to build,
  168 bytes, once per init-game. SPC-clean.
- Ops flags left alone, not published, not proposed for retirement.
- Stage 3 deleted nothing. The live undecided flags (GOB_COLLISION_*, GOB_SCREEN_*,
  GOB_COLLISION_TOLERANCE, GOB_STRICT_EXCEPTIONS, USE_DEPTH_ORDERING) correctly excluded.

## JAMIE'S EYE TEST IS SAFE — verified in code, not from the report's claim
`markerConfig.js` keeps `window.__GOB_DEPTH_ORDERING` and `window.__GOB_DEPTH_MODE` working AND at
HIGHEST priority, above the new `window.__GOB_FLAG_*` form and above the served value. Comment at
:41 says the alias is deliberate. The eye test in flight will not break.

## Headline inventory
**54 switches: 32 sim, 5 render, 17 ops.** 49 backend variables across 57 read sites — more than
the ~43 my own survey estimated, so the agent's sweep was wider than mine, not narrower.

## CORRECTION 1 — the inventory is short by four, all ops
My independent count found 57 distinct `GOB_*` names in BackEnd/. Four are absent from all three
tables:
  `GOB_BASE_LEAGUE_SQLITE`, `GOB_CATALOG_SQLITE`, `GOB_DB_MODE`, `GOB_EOG_BAND_ENABLED`
All four are persistence/DB config — ops, none sim-affecting, so there is NO security or
determinism exposure. **The mechanism of the miss is the point**: they are read through
`env.get(...)` / `db_env.process_environment.get(...)` wrappers rather than `os.environ.get(...)`,
so a sweep keyed on the latter cannot see them. That blind spot persists — any future flag added
through those wrappers will also be invisible to the registry and to this inventory. Worth a
follow-up pass keyed on the wrapper forms.

## CORRECTION 2 — the publishing gate is a TEST, not a runtime check
The report says publishing is "gated on a second, independent PUBLISHABLE allow-list". Accurate in
effect but the phrasing overstates the mechanism: `PUBLISHABLE` lives in
`tests/test_feature_flags.py:138`, not in production code. It fails CI if the payload diverges from
the allow-list, which does force a two-place edit and does catch the reclassification slip. It is
not a runtime guard — nothing stops a leak in a build where tests were not run. For a solo dev who
runs the suite before merging, that is adequate; it should just be described accurately.

## The standout piece of work
The brief said to write the boundary test first and watch it fail. The agent did, and reported
that **the first poison got through**: widening `client_flags()` to include sim flags failed 2
tests, but RECLASSIFYING one sim flag as `render` passed all 12 — because every test trusted
`kind`, the thing under test. Reclassification is the realistic slip, since classification is a
one-off judgement in a diff. The agent added the independent allow-list in response and re-ran the
poison: 2 tests now fail. That is the correct instinct and it was self-initiated.

## Defects found and correctly NOT fixed
1. `GOB_PERSISTENCE` has TWO different defaults across three read sites — `"sqlite"` at
   `api/_bootstrap.py`, none at the other two. Which one applies depends on module import order.
   Latent bug, behaviour preserved, reported. Worth fixing separately.
2. Three screen flags default to `""` rather than `"0"`. Behaviourally identical (all compare
   `== "1"`), inconsistent, recorded.

## Honest limitations the agent volunteered
- Flag-off coverage is a floor, not a truth: `no` means "no test sets the env var", not
  "untested". It threw away a first heuristic that gave obviously wrong results and said so.
- Guard counts took three attempts (a `grep -E` lookbehind silently matched nothing, reporting 0
  guards for all 19). Published numbers are floors.
- `GOB_HASH_PIN_REEXEC` declared ops but not traced.
- **The client payload is not verified end to end in a browser** — `court.html` still cannot boot
  here because of the init-game name-vs-slug defect recorded in depth-ordering.md §7. Backend
  payload and frontend precedence are each tested in isolation; the wire between them is not.
- Stage 2 changes no rendering today: every served value equals the constant it replaces.

## Retirement proposal
19 candidates, 40 guarded call sites, 183 lines of accessor, and **only 6 of 19 have any flag-off
test coverage** — which is the real argument: those branches are not merely unused, they are
largely unverified, so flipping one lands in an untested state. Ranked by dead code removed ÷ risk
(guard count first, recency second), with two non-obvious ordering constraints called out
(`ZONE_SINK_IQ` before `ZONE_SINK`; the sag/cutoff pair is not additive with the shade flags).
Lifecycle rule recommended at N = 12 weeks, explicitly flagged as a starting value. Enforcement
deliberately not built because `added` is currently a mix of dates and SHAs — correct call, since
inventing 13 dates would have been fabrication.

## Filing
Per Jamie's own bucket list this is **Operations (#5)**, not Animation (#1). Park it; do not let it
become a merge decision tonight. The one piece that belongs in the UESS requirements is the
classification principle: sim-affecting switches must be server-authoritative and never
client-settable.

## Still open
- Depth-ordering eye test on the deployed build (Animation, #1 — the live item).
- `PIN_OFFENCE_AT_AUTHORED_LOCATION` — unanswered from the tolerance sweep.
- The four wrapper-read ops flags above.
- `GOB_PERSISTENCE`'s split default.
