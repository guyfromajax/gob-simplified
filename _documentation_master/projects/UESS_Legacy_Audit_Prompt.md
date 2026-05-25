# UESS Legacy Audit — READ-ONLY SWEEP, NO CODE CHANGES

## Your role
You are auditing this codebase. You will NOT edit, refactor, or write any
code in this task. Your sole deliverable is a written report (a new markdown
file at `docs/audits/UESS_Legacy_Audit.md`). If you feel the urge to fix
something, DON'T — log it in the report instead. A fix in this pass is a
failure of this task.

## Context
We are migrating to the Universal End-State Sync (UESS) system. The canonical
spec is `_documentation_master/00_General_Systems/UESS_System.md` — read it in
full before doing anything else. The companion step spec is
`Step_By_Step_System.md`. Read both completely first.

Core premise of the migration: game, animation, and clock logic was historically
split across frontend and backend. UESS consolidates ALL logic to the backend;
the frontend must be a PURE RENDERER of backend-emitted `AnimationStep[]`
payloads. The migration is implemented at a base level across all turn types
but legacy code remains and is causing inconsistent execution.

## The key insight driving this audit
UESS is not just the target architecture — it is the PREDICATE for what counts
as legacy. Do not hunt for "old-looking code." Hunt for code that VIOLATES the
following invariants. Each violation is, by definition, legacy that must go.

### Invariant checklist (the things to grep for and trace)
1. FRONTEND IS A PURE RENDERER. Any frontend code that computes game logic,
   mutates player position outside of snapping to `step.end.coords`, or makes
   gameplay decisions is a violation. (Ref UESS §1, §8.1.) Specifically flag any
   FE position mutation that is NOT the end-of-step snap.
   NOTE: "frontend is a pure renderer" and "backend owns all game logic" are
   stated in §1. The narrower targets — "makes gameplay decisions" and "any FE
   clock manipulation" (see invariant 2) — are my INFERENCES from that principle,
   not phrases the spec defines. Treat them as "investigate whether this violates
   the spirit of §1," not as a defined contract test. Report findings as
   inference-grade unless the code makes it unambiguous.

2. CLOCK AUTHORITY IS LEDGER-DERIVED. `turn.time_elapsed` is derived from the
   clock event ledger, never independently tuned. Transition boundaries do NOT
   implicitly pause clocks. (Ref UESS §5.) Flag: any BE code that pauses/resets
   clocks at a transition boundary, any place `time_elapsed` is summed from
   animation step times instead of read from the ledger.
   INFERENCE (not stated verbatim in spec): any FRONTEND clock manipulation
   likely violates §5 + §1 together, since clock authority is a backend ledger
   and the FE is a renderer. Flag FE clock writes, but label them inference-grade.

3. EMITTERS NEVER WRITE player.coords MID-EMIT. Coords flow step N end →
   step N+1 start within a turn; `sync_lineup_coords_from_turn` is the SOLE
   turn→turn coord authority. (Ref UESS §8.1, §8.2.) Flag any direct
   `player.coords` write inside an emitter, and any turn→turn coord sync that
   bypasses `sync_lineup_coords_from_turn`.

4. OWNERSHIP COMMITS AT RECEIPT, NOT RELEASE. (Ref UESS §6.) Flag any
   ownership flip that happens at pass-release time.

5. SHOTMANAGER IS SOLE POST-SHOT POSITION AUTHORITY. Each player appears in at
   most one overlay map. (Ref UESS §9.1.) Flag any post-shot coord write that
   bypasses ShotManager's four overlay maps (`offense_rebounder_coords`,
   `defense_rebounder_coords`, `offense_getback_coords`, `defense_release_coords`).

6. ONE SHOT SNAPSHOT. Contest/foul/block/rebound/make-miss all resolve from the
   single `shot_state_snapshot`. (Ref UESS §7.) Flag any branch-specific coord
   fallback in shot resolution.

7. EVERY TURN EMITS THE SAME SCHEMA. (Ref UESS §3.) Flag any turn type still
   using legacy `animations[]` rather than `animation_steps[]` (except the
   knowingly un-migrated ones in §2's table: After-Steal fast break, Timeout,
   Final Shot — note them but rank as expected, not surprising).

## What I want you to do
1. Read the two spec docs in full.
2. For EACH invariant above, grep/trace the entire tree (frontend AND backend)
   and catalog every violation you find. Cite file + line + a one-line
   description of why it violates the invariant.
3. Pay special attention to the FE/BE boundary: any place the frontend is
   doing something the backend should own is a primary target.
4. Build a dependency picture: when legacy code is still firing, what is calling
   it, and what would break if it were removed? I need to know which violations
   are load-bearing.

## Schema completeness audit (per step, per turn type)
Separately from the legacy hunt, verify that EVERY step of EVERY turn type is
fully wired with all required schema fields. The required `step.start` and
`step.end` fields are exhaustively defined in UESS §3.1 / §3.2; the per-turn
step inventories are in `Step_By_Step_System.md`. For each turn type's emitter,
confirm every emitted step populates:
  - start: coords, destination, action, archetype, ball, clock, advance_trigger
    (and any conditionally-required optional fields the step needs)
  - end: coords, ball, time_elapsed, clock, next
Specifically check that every step has a valid `advance_trigger` (condition +
T_game_seconds) and that every mover has a destination (or explicit null for
stationary). The `Step_By_Step_System.md` Advance Triggers section lists the
expected trigger per step type — verify each emitted step matches.

If ANY required field is missing, malformed, or you cannot determine the correct
value from the code or docs — DO NOT GUESS and DO NOT invent a value. Raise it
to me as an explicit open question in the report (e.g. "HCO skeleton step 2 is
missing advance_trigger metadata — what should it be?") and I will provide it.
Add a dedicated "Schema gaps — needs human input" section for these.

## Known bugs — TEST whether they map to invariant violations
Below is our current bug list after the base migration. It is an INITIAL,
NON-COMPREHENSIVE list from a couple of prototype runs — expect many more bugs
to exist that are not listed here. Do not treat this list as the full failure
surface.

It is my HYPOTHESIS (not an established fact, and not something the spec
addresses) that most of these bugs are symptoms of legacy/UESS conflict rather
than independent logic errors. Your job is to TEST that hypothesis, not assume
it. For each bug, identify as many candidate root causes as the code supports,
tie each to a specific invariant violation + file/line where possible, and call
out shared root causes explicitly. Where a bug clearly maps to an invariant
violation, say so. Where a bug does NOT map to any invariant violation and looks
like an ordinary logic error, say THAT plainly — do not force a fit. Report the
overall split (how many trace to legacy vs. not), since that result tells us
whether the hypothesis holds.

Bug list:
1.  Quick HCO passes teleporting
2.  Announcements are not consistently executing
3.  Secondary swish SFX are not triggering on Bank and Rim makes
4.  Blocks are not executing properly
5.  HCO skeleton steps are not animating consistently
6.  We need clamping
7.  DREB to HCO jetting/teleport (suspect handoff + walk-up not properly implemented)
8.  Defenders moving before pass on HCO steps with a pass
9.  Some but not all HCO skeleton steps are teleporting defenders
10. Made Fast Break shots are not resolving on the Rim Sweet Spot (also look into misses)
11. Announcements not triggering properly or consistently on Shooting Fouls (makes or misses)
12. OREB to DREB to HCO transitions are broken. DREB to HCO skips handoff and walk-up; players teleport to HCO
13. SIP to HCO transition is broken, players teleporting
14. The handoff and walk-up step after a steal is happening too fast and is clumsy
15. RR FB is not reading geography — hold-ups are happening with a wide-open path to the basket
16. Some, not all, players are teleporting on shot attempts in HCO
17. Not announcing all DREBs
18. Steal to Fast Break Make: inbound passer for BIP jets to get the ball

## Report format (`docs/audits/UESS_Legacy_Audit.md`)
1. Executive summary: how bad is it, what are the 3-5 biggest themes.
2. Violations by invariant: a section per invariant (1-7 above), each a table of
   file | line | description | load-bearing? (what breaks if removed).
3. Schema gaps — needs human input: every missing/malformed/undeterminable
   schema field, as explicit questions for me to answer.
4. Bug → root cause map: a table of bug | candidate cause(s) | invariant | file:line |
   shared-with-which-other-bugs. Include the legacy-vs-not split.
5. Recommended remediation ORDER: given dependencies, what should be cleaned up
   first, second, etc., and why. Sequence by what unblocks the most / what is
   safest to cut first. Do NOT write the fixes — just the order and rationale.
6. Open questions / things you couldn't resolve from the code alone.

## Rules
- READ ONLY. No edits, no new code, no refactors. Report only.
- Cite file:line for every claim. If you're inferring rather than confirming
  from the code, label it as inference.
- Where the code and the UESS doc disagree, the CODE is ground truth — flag the
  disagreement so we can fix the doc (per UESS §1).
- Be honest about uncertainty. "I couldn't trace this fully" is more useful to
  me than a confident guess.
- DO NOT GUESS at schema values or invent data. Raise gaps as questions.
