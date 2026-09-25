# READY — skeleton source resolved: Probe B was wrong. 98% is MongoDB. Nothing is broken.

Report: `reports/skeleton-source-audit.md`. Branch `feature/animation-reward`, HEAD `f9b6d1eb8`.
Verified against the audit brief by Claude. **Read-only confirmed** — nothing fixed, no flag, no
behaviour change, instrumentation in gitignored `scratch_skelsrc.py`.

**RNG neutrality proved, not assumed:** 16/16 cells reproduce the reference on fingerprint AND
draws, seed 8000 played SD=1 = fp `0c3389cd41d0bbef` / draws `75363`, 0 probe errors. n=8 seeds
8000-8007 both arms, with the sample size justified rather than asserted (the split is 98/2,
nowhere near close).

## Ground truth by object identity

| | mongo | hardcoded |
|---|---|---|
| `get_hco_skeleton` calls (5,726) | **97.92%** | 2.08% |
| steps returned (40,947) | **97.97%** | 2.03% |
| steps reaching either execution point | — | **0%** |

**The hardcoded scenes are not load-bearing. Probe A was right.**

The tagging design is the reason this is trustworthy: the tag went on the **step dict**, not the
skeleton, because `get_hco_skeleton` rebuilds the skeleton dict on several paths and would drop a
skeleton-level tag — while step dicts are carried by reference and the only two copy points both
use `copy.deepcopy`, which preserves inner keys. And the arithmetic closes exactly: 119 hardcoded
calls x 7 steps (`INSIDE_SCENES`) = **833**, the hardcoded step total to the step.

## Why Probe B was wrong — `get_hco_skeleton` has THREE sources, not two

1. `_get_skeleton_from_team_plays(...)` — team plays (MongoDB)
2. **`plays_catalog.doc_by_name(playcall)` — universal plays catalogue, ALSO MongoDB**
3. the hardcoded `*_SCENES` tables

Probe B labelled a call `mongo` only if source 1 returned truthy, and `fallback` otherwise. Source
2 sits between them. So **1,928 MongoDB calls were labelled "fallback" — 94.2% of its entire
fallback bucket.** That is the whole discrepancy.

The previously-suspected trigger (`_get_skeleton_from_team_plays` returning falsy) is confirmed as
the mechanism but its consequence was misread: falsy does not mean "hardcoded", it means "not the
team-plays route", and the next route is still MongoDB.

Both candidate explanations from the prior audit were tested: (a) heuristic mis-labels
Mongo-sourced skeletons — **CONFIRMED**; (b) fallback scenes copied before the patch point —
**DISPROVEN** (the tag was injected into live module objects and 119 calls did return tagged
hardcoded steps, so the patch point is reached).

## Why patching the scenes changed nothing

All **119 of 119** hardcoded calls occur with `current_playcall == ""`. The empty string matches
no key in `playcall_map`, so `playcall_map.get(playcall, INSIDE_SCENES)` resolves to
`INSIDE_SCENES` every time — and `INSIDE_SCENES` authors **no PF at `upper lowPost`** (its PF sits
at `upper highPost`/`topLane`). The prior counterfactuals D/E patched five tables that never
execute. Real patch, live objects, wrong tables.

## LATENT BUG — a dead safety net

`phase_resolution.py:11076` reads `game_state.get("current_playcall", "Inside")`. **The default
can never apply**: `GameManager.switch_possession` (`game_manager.py:2407`) sets
`current_playcall = ""`, so the key is always present and the read returns `""`. An empty playcall
then silently routes to hardcoded `INSIDE_SCENES` instead of the authored catalogue. Same shape at
`phase_resolution.py:8530`. Small today (2% of calls, 0% reaching execution) but it is a default
that looks like a safety net and is dead. Reported, not fixed.

## THIS CORRECTS THE PREVIOUS AUDIT — and my relay of it

The coincidence audit said only the `successful` lean is authored and the other three fall back.
**That is wrong, and I passed it on.**

The lean fallback fires **0 times in 4,660 calls**. All four leans ARE authored — the three
non-`successful` ones use a **`versions` array format** with 6 versions each, across all 7 plays.
The prior audit read `skeleton["steps"]` at the top level, which is 0 for a versioned variant
because the steps live under `skeleton["versions"][i]["steps"]`. It measured the wrong key.

So the play catalogue is considerably richer than we were told: 7 plays x 4 leans, with 6 versions
on three of them.

## A THIRD CATEGORY NEITHER PROBE CONSIDERED — worth its own look

| execution point | mongo-tagged | UNTAGGED |
|---|---|---|
| `defender_placement.build_all_animations` | 64.41% | **35.59%** |
| `skeleton_step_emitter.build_skeleton_animation_steps` | 50.75% | **49.25%** |

Those untagged steps are **engine-synthesised at runtime** — FCP/HCT dynamic builders, transition
/ OREB / DREB legs — from no authored file at all. (The FCP/HCT hardcoded tables are separately
tagged and executed **0** of their 270 steps.)

The agent marks this Medium confidence and says plainly it established what those steps are NOT,
and did not enumerate what generates them. **Roughly half of what appears on screen comes from no
authored play**, which is worth knowing independently of any of this.

## Prior conclusions unaffected

The coincidence audit's counterfactuals A and C — which drove every conclusion — patched the
MongoDB source, the one carrying 98% of execution. D and E were null for a now-understood reason,
and their null result was correct.

## Q4 not applicable, with the reason given

Conditional on the hardcoded scenes being load-bearing; they are not. The "authored catalogue is
not what runs" concern does not hold. For completeness: 7 authored plays vs 6 hardcoded scenes
(one generic scene each, describing none of the authored plays), 4,160 tagged authored steps vs
45 hardcoded, and **five of the six hardcoded scenes were never reached at all** in 16 games.

No merge by Claude. Jamie merges.
