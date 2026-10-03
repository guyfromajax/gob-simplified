# READY — Phase 2: gates clean, contest is real, but THREE MEASUREMENTS ARE MISSING

Report: `reports/spatial-screens-phase2.md`. Verified against the Phase 2 brief by Claude.
Two commits, two flags, both default OFF: `98a9f5a79` (`GOB_SCREEN_TARGETING`),
`7fc0948f0` (`GOB_SCREEN_CONTEST`).

## Gates — clean, with a third the brief did not ask for

240/240 both stages, fingerprint AND draws, seed 8000 played SD=1 = fp `0c3389cd41d0bbef`,
draws `75363`. Suite 3,621 passed / 0 failed.

The extra gate is the good one: **the Stage B commit, run targeting-on/contest-off, reproduces
Stage A's exact 80-cell measurement byte-identically.** Stage B touches Stage A's module, so
without that check the two stages would not have been separately attributable. Rule 6e footing
stated throughout, SD=1 production footing.

## MISSING FROM THE REPORT — three items the brief asked for

1. **The exact-coincidence stacks, before and after.** This was checkpoint A item 1 and the
   headline question: did the O-C/O-PF stack (baseline 3,367) collapse? The report gives
   DISTANCES instead — informative, but not the same measurement. **We still do not know
   whether the stack broke.**
2. **Screen-vs-game divergence vs the 0.0221% baseline** (checkpoint A item 4, B item 9). Not
   reported for either stage. That is the tripwire for writing after the freeze stamp.
3. **Outcomes were run at n=40, not n=120** (seeds 8000-8039 rather than 8000-8119). CIs are
   correspondingly wider, so "every delta inside CI" is a weaker claim than the brief intended.

None of these is a failure — the build looks sound. But the three together are exactly the
evidence needed to decide a flip, so they should be filled in before one.

## Stage A works, and costs something real

Screener -> receiver's defender, p50 **8.5 -> 2.5** (2.5 is the derived contact distance). The
screener's OWN defender also improved, 11.0 -> 3.5 — the agent had predicted a stale-defender
risk and reported being wrong about it.

**The cost, and the one thing to settle before flipping:** Stage A has no constraint tying the
screen to the receiver. In sag and help defences the receiver's defender is nowhere near the
receiver, so screener -> receiver goes 4.0 -> 6.0 at p50 but **17.0 at p90**. A screen set 17
grid units from the man you are screening for is not a screen.

Related: **screener displacement p50 9.5, p90 14.5, max 19.5** grid units in one step, with no
reachability check. Today's offence build has no reachability check either, so this is not a new
defect class — Stage A makes an existing one far more visible. Feeds the planned no-teleport
capstone.

The agent deliberately did NOT add a proximity gate, because any threshold would be a tuning
constant and Jamie tunes once. It offers an existing derived candidate rather than a new number:
`pass_contest.PASS_LANE_DIST = 8.0`, already reused by `boxout_contest`.

Coverage: Stage A applies to **54.1%** of screens. Man-defence guard resolution 100%
(1,348/1,348); zone 51.8%, legitimately — nobody is assigned to a player standing in an
uncovered area. Fallback reasons counted, five possible failure modes all zero.

**Architectural finding worth keeping:** the playbook states screens explicitly as
`{"type":"screen","by":X,"for":Y}`, but **those events do not survive to the executed skeleton**.
The receiver has to be inferred as the other offensive position on the same `location` — unique
on 87.3% of screens. The intent is being thrown away somewhere upstream.

## Stage B is a real contest

| outcome | share |
|---|---|
| fight through | **50.3%** |
| go around | 25.9% |
| switch | 23.9% |

Nothing near 80%. Better: a tie goes to the defender (the same non-RNG tiebreak `resolve_boxout`
uses), which puts a **58.3% structural floor** at equal attributes — and the observed 50.3% sits
BELOW it because real screeners (PF/C) out-ST the guards navigating them. That is the attribute
model doing work, and the agent surfaced it rather than burying it.

Zone skipped and counted (36.9% of placed screens): a switch swaps assignments and a zone has
none to swap. Draws gated by branch, not just their effect — proved by the 240/240 being on draws
as well as fingerprints. `sim_rng`, never global `random`. Contest-without-targeting logs once
and no-ops.

**No existing switch-propensity setting exists** — searched `strategy_calls` (all eight keys),
`playbook_settings`, and the backend for "fight through" / "hedge" / "ICE" / "go around".
Stage B introduces the concept, driven by attributes rather than a team dial.

## The override layer — and the catch that matters

A SWITCH does **not** mutate the matchup map, because **`man_defense_matchups` is the USER'S
Defense Matchups choice and is persisted with the save** (`shared.py:3294`). Mutating it would
silently rewrite what Jamie chose and carry into the next possession, quarter and save file.
That is a genuinely important catch. A switch writes `man_defense_matchups_override`, layered at
read time, cleared at both possession boundaries and in `reset_matchups_to_defaults`. An override
that would break the 1-to-1 mapping is discarded, not applied.

**Site count is 16, not 18** — the agent enumerated call sites rather than restating the brief's
number, and flagged the discrepancy. The structural finding is better than the count: there are
only **two chokepoints** (`get_matchups_for_defending_team`,
`get_defender_position_for_man_defense`), so the override applies inside those and reaches all 16
with no call-site change — it cannot be half-applied by a site someone missed.

Proved by runtime probe over 80 games: **110,113 / 110,113 asks reflected the override, 0 misses.**
Five of the 16 sites were not exercised and the agent says plainly they are covered by
construction, not by measurement.

And it found the one place the override could have leaked:
`get_defender_position_for_man_defense` had a backward-compat branch reading the raw key
directly. Now routed through the layering, with a test.

## Effect on the sim

Every delta inside CI at n=40, both arms, both stages. Nothing retuned.

**The finding that reframes the phase:** Stage A reaches 54% of screens in both arms, yet
fingerprints move in only **27/40 (sim) and 20/40 (played)** games. Moving 280+ screeners per
game changes nothing at all in a third to a half of them. **The screener's coordinate is largely
inert downstream** — it feeds the render; very little of the simulation reads it.

So Stage A is close to a rendering change, and **Stage B is where the teeth are** — it changes
who guards whom and how late a defender recovers, and moves the draws substantially (+900 sim,
+700 played) even with scoring unchanged.

## Illegal screen — located, not built

`_contest_one` in `screen_targeting.py`, on the GO AROUND / SWITCH branch: the moment the model
has already decided the defender was beaten. Both players are in hand and `ND` ("No Dumb Fouls")
already carries 0.10 of `NAVIGATE_WEIGHTS`, so both checks would read attributes the function
already loads.

## Out of scope, confirmed

SCRA/SCRS and `calculate_screen_score` untouched. No offensive separation. No frontend change.
Stage 3 defects untouched. Phase 1 constants not tuned. Nothing merged.

## What to do next

Fill the three missing measurements (coincidence stacks, divergence, n=120 outcomes) before any
flip decision, and settle the screener -> receiver p90 of 17.0.

No merge by Claude. Jamie merges.
