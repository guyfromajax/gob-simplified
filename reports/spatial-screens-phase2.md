# Collision Phase 2 — spatial screens

Branch `feature/animation-reward`. Two commits, two flags, **both default OFF**, measured
separately so each result is attributable:

| Stage | Flag | Commit |
|---|---|---|
| A — screener targets the receiver's defender | `GOB_SCREEN_TARGETING` | `98a9f5a79` |
| B — fight through / go around / switch | `GOB_SCREEN_CONTEST` | `7fc0948f0` |

**Rule 6e footing** (every number below): worker `scratch_equiv3_fbdedupe.py`, Lancaster vs
Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one
game per process, game id `0xE0000+(seed−8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM,
**`SEED_DEFENSES=1` production footing** (catalogue seeded, so zone calls really play zone).

---

## Gates

| Gate | Result |
|---|---|
| Stage A, both flags off | **240/240** — fp AND draws, 480/480 checks, 0 mismatches |
| Stage B, both flags off | **240/240** — fp AND draws, 480/480 checks, 0 mismatches |
| Stage B commit, targeting-on/contest-off | **80/80 identical** to the Stage A measurement |
| Suite | 3,621 passed / 20 skipped / 110 xfailed / **0 failed**, 0 XPASS |

240 = 160 cells of `equiv_v3_reference_f600628a4_agspread.json` (2 footings × 2 arms × 40)
+ 80 of `equiv_v3_loose_baseline_f600628a4_agspread.json` (`EQUIV_MAN_POSTURE=loose`).
Seed 8000 played SD=1 = fp `0c3389cd41d0bbef`, draws `75363`, as expected.

The third row is what makes the two commits separately attributable: the Stage B commit
touches the Stage A module, so I re-ran Stage A's exact 80-cell measurement on top of it.
Byte-identical.

---

## Stage A — the premise checked out, with a number

Today `build_all_animations` sends a screener to `OFFSET_SPOTS[location]` — a fixed
per-spot nudge off **the receiver's own named spot**. It is a cosmetic anti-overlap table
(`constants/__init__.py:600`, comment: *"Offset positions for collision handling"*) and it
knows about no defender at all. It has exactly one live consumer,
`defender_placement.py:223`.

Measured, 3,162 screens over 6 games:

| distance from the screener to… | p25 | p50 | p75 | p90 |
|---|---|---|---|---|
| the **receiver** | 3.0 | **4.0** | 4.0 | 4.0 |
| the receiver's **defender** | 6.0 | **8.5** | 12.0 | 13.0 |

The screener is planted beside the man he screens *for*, roughly two sprite widths from the
man he is supposed to be screening. The flat 3.0–4.0 spread is the offset table showing
through: it is a constant, not a placement.

### What Stage A does, and its effect

| distance from the screener to… | flag OFF p50 | flag ON p50 |
|---|---|---|
| the receiver's defender | 8.5 | **2.5** |
| his OWN defender (man) | 11.0 | **3.5** |
| the receiver | 4.0 | **6.0** (p90 **17.0**) |

2.5 is the derived contact distance (2.62 for two median players). Stage A does what it
says.

**I was wrong about one risk and should say so.** I expected the screener's own defender to
be left stale, since he was placed against the pre-screen coordinate and is not re-placed.
Measured, it *improves* — 11.0 → 3.5. Moving the screener into the defence puts him closer
to everyone, not further.

### THE REAL COST — read this before flipping

**Stage A has no constraint tying the screen to the receiver.** In sag and help defences the
receiver's defender is nowhere near the receiver, so aiming at the defender drags the
screener away from the play: screener → receiver goes 4.0 → 6.0 at p50 but **17.0 at p90**.
A screen set 17 grid units from the man you are screening for is not a screen.

Related: **screener displacement p50 9.5, p90 14.5, max 19.5 grid units** — roughly a fifth
of the court, in one step, with no reachability check. Today's offense build has no
reachability check either, so this is not a new class of defect, but Stage A makes an
existing one far more visible. (This is the same concern as the repo's planned
no-teleport-by-construction reachability capstone.)

I did **not** add a proximity gate, because any threshold I picked would be a tuning
constant and Jamie tunes once, at the end. If one is wanted, the house already has a
derived candidate rather than a new number: `pass_contest.PASS_LANE_DIST = 8.0`, the
existing "close enough to contest" spatial gate, which `boxout_contest` also reused.

### Fallbacks — counted, not hidden

Stage A applies to **54.1%** of screens (n=41,731 over 80 games; 54.2% played / 53.9% sim).
The other 45.9% keep today's placement:

| reason | share of all screens |
|---|---|
| zone: no defender assigned to the receiver | 20.4% |
| receiver is not heading anywhere next | 13.7% |
| no teammate on the screener's spot → no receiver derivable | 11.8% |

Man-defence guard resolution is **100%** (1,348/1,348). Zone resolves **51.8%** — legitimately,
since nobody is assigned to a player standing in an area no defender covers.

`no_guard_man`, `guard_has_no_coord`, `dest_spot_unknown`,
`defender_already_at_destination` and `screener_has_no_movement_entry` were all **0**.

### How the receiver is identified at all

The playbook states it explicitly — `{"type": "screen", "by": X, "for": Y}` — but **those
events do not survive to the executed skeleton**. What survives is that the screener is
authored to the receiver's *own* named spot, so the receiver is the other offensive position
on the same `location` at that step. Unique match on **87.3%** of screens. Ambiguity never
occurred in 6 games; it is handled by lineup-slot order anyway, so the answer can never
depend on dict iteration.

### Clairvoyance

The target reads the receiver's **authored next spot** (play intent — the screener is running
the same play) and the defender's **current** coordinate. It never reads the step's outcome:
not the shot, not the contest, not who ends up with the ball. A test pins the mirror image
too — a spot the receiver has already left is not where he is heading.

### Why it is a post-pass, not an edit at line 223

Line 223 is inside the offense loop, which completes before any defender is placed, so the
receiver's defender has no coordinate yet — it cannot, because defenders are placed
*against* the offence. Running afterwards also keeps the dependency one-way; feeding the
screen point back into placement would make the two mutually recursive. It runs **before**
the Phase 1 separation pass, which reads offensive coordinates to decide which defenders are
pinned, and both run before the return, because the freeze stamp reads these coordinates
back out.

### No new tuning constant

The stand-off **is** `collision_separation.separation_threshold` — Phase 1's per-pair contact
distance, already derived from the frontend's `headRadiusForHeight` sprite geometry. A test
fails if anyone replaces it with a literal.

---

## Stage B — a real contest

Two stages, the house's own shape (`pass_contest`, `boxout_contest`: geometry picks who is
eligible, then `(weighted composite) × randint(1, 6)` each side). Stage A is the geometry.

1. **NAVIGATE vs HOLD** — defender wins (ties included) → **FIGHT THROUGH**.
2. Only if he lost: the two defenders' **communication vs the screen**, fresh rolls. Pair
   wins → **SWITCH**; pair loses → **GO AROUND** (he trails, arriving a contact-distance late).

Measured, 2,061 contests over 12 games:

| outcome | share |
|---|---|
| fight through | **50.3%** |
| go around | **25.9%** |
| switch | **23.9%** |

**No outcome is near 80% — this is a contest, not a formality.** A tie goes to the defender
at stage 1 (the same non-RNG tiebreak `resolve_boxout` uses); at equal attributes that is a
58.3% structural floor, and the observed 50.3% sits *below* it because real screeners (PF/C)
out-ST the guards navigating them. That is the model working, and it is reported rather than
buried.

Zone is **skipped and counted** — 36.9% of placed screens. A switch swaps two *assignments*;
a zone has none to swap, so rolling there would produce a SWITCH with nowhere to write.

### Draws are gated, not just their effect

The contest is only reachable from inside the branch that placed a screen, so with the flag
off no draw occurs. Proved by the 240/240 gate being on **draws** as well as fingerprint.
Draw count is branch-determined: two rolls on a fight-through, four otherwise.

`sim_rng`, never the global `random`. `shared.calculate_screen_score` (`shared.py:1467`)
draws from the global module — a defect, not a pattern to copy.

### Contest without targeting

`GOB_SCREEN_CONTEST=1` with `GOB_SCREEN_TARGETING=0` logs **once** and no-ops. It does not
half-apply: contesting a screen that was never placed would score a fiction and move the
draws for no modelled reason.

### No existing switch-propensity setting — searched first

There is none. Not in `strategy_calls` (its eight keys are offense/defense/aggression/tempo/
press/trap/press_trap/aggression_roll), not in `playbook_settings`, and "fight through",
"hedge", "ICE" and "go around" appear nowhere in the backend. Stage B introduces the
concept; the outcome falls out of attributes rather than a team dial, so nothing is stranded
if a dial is added later.

---

## The override layer

A SWITCH **does not mutate the matchup map**. `man_defense_matchups` is the user's Defense
Matchups choice and is persisted with the save (`shared.py:3294`) — writing a switch into it
would silently rewrite what they chose and survive into the next possession, quarter and
save file. A switch writes `man_defense_matchups_override`, layered on at read time.

An override that would break the 1-to-1 mapping is **discarded**, not applied: an offensive
player guarded twice and another guarded by nobody is worse than no switch.

**Cleared** at both possession boundaries — `GameManager.switch_possession` (live flip) and
the quarter-start assignment in `main.simulate_quarter`, the exact two-boundary split
`reset_frontcourt_state` documents — and in `reset_matchups_to_defaults` (breaks).

### The site count is 16, not 18 — and the override reaches all of them

The brief said 18. Enumerating **call sites** (not imports, not the accessor's own
definition) gives **16** pre-existing sites across 8 modules. I am flagging the discrepancy
rather than restating the brief's number.

The important structural finding is that **there are only two chokepoints, not 16 scattered
dict reads**. Every engine consumer goes through `get_matchups_for_defending_team` or
`get_defender_position_for_man_defense`, so applying the override inside those two functions
reaches all 16 with **no call-site change** — it cannot be half-applied by a site someone
missed. The only raw-key readers anywhere are `shared.py:3294-3295` (persistence),
`game_manager.py:317/324` (fresh-game init) and `api.py` (the popup endpoint); none is a
placement read.

**Proved by measurement, not inspection.** A runtime probe over 80 games recorded every
caller of both accessors and whether its return reflected a live override:

**110,113 / 110,113 asks reflected the override. 0 misses.**

| site | kind | calls | asked w/ override live | reflected |
|---|---|---|---|---|
| `screen_targeting.py:251` | map | 222,745 | 47,613 | 47,613 |
| `defender_placement.py:1122` | map | 97,675 | 30,290 | 30,290 |
| `screen_targeting.py:242` | map | 38,035 | 6,708 | 6,708 |
| `man_defense_matchups.py:213` | map | 8,879 | 3,788 | 3,788 |
| `motion_read_map.py:94` | map | 6,367 | 2,338 | 2,338 |
| `phase_resolution.py:7364` | map | 5,269 | 1,931 | 1,931 |
| `turn_manager.py:6565` | reverse | 4,603 | 1,811 | 1,811 |
| `shot_manager.py:276` | reverse | 3,654 | 1,722 | 1,722 |
| `phase_resolution.py:6607` | map | 3,468 | 1,548 | 1,548 |
| `screen_targeting.py:424` | map | 3,271 | 1,258 | 1,258 |
| `phase_resolution.py:7046` | map | 2,387 | 997 | 997 |
| `phase_resolution.py:8040` | map | 1,753 | 624 | 624 |
| `attack_drive_clearance.py:1073` | map | 1,402 | 509 | 509 |
| `phase_resolution.py:8927` | reverse | 622 | 255 | 255 |
| **TOTAL** | | **438,165** | **110,113** | **110,113** |

Five of the 16 static sites were **not exercised** in these 80 games and I am not claiming
runtime evidence for them: `collision_separation.py:273` (Phase 1, flag off),
`phase_resolution.py:3325`, `phase_resolution.py:3507`, `phase_resolution.py:7241`,
`step_state.py:148`. All five call one of the two accessors, which is where the override is
applied, so they are covered by construction — but by construction, not by measurement.

`get_defender_position_for_man_defense` had a backward-compat branch that read the raw key
directly — **the one site the override could have missed**. It now routes through the same
layering, with a test.

---

## Effect on the sim

| metric | arm | flags off | Stage A | Stage A+B |
|---|---|---|---|---|
| points/team | sim | 73.97 ± 2.80 | 74.01 ± 2.44 | 74.36 ± 3.37 |
| points/team | played | 73.61 ± 3.07 | 72.59 ± 3.02 | 73.74 ± 3.41 |
| possessions | sim | 40.58 ± 1.81 | 40.12 ± 1.72 | 39.05 ± 1.97 |
| possessions | played | 39.15 ± 1.74 | 39.75 ± 1.82 | 38.98 ± 1.85 |

**Every delta is inside CI.** Neither stage moves scoring at n=40. Nothing was retuned in
response — reporting it, per the brief.

### The finding that matters most for what comes next

Stage A reaches 54% of screens in **both** arms, yet fingerprints move in only **27/40** (sim)
and **20/40** (played) games. Moving 280+ screeners per game changes nothing at all in a third
to a half of them.

**The screener's coordinate is largely inert downstream.** It feeds the render; very little
of the simulation reads it. That frames the whole phase: geometry alone is close to a
rendering change, and it is Stage B — which changes *who guards whom* and how late a
defender recovers — that has teeth. Stage B does move the draws substantially (+900 sim,
+700 played) even though scoring is unchanged.

---

## Out of scope, as instructed

SCRA/SCRS stat tracking and `calculate_screen_score` untouched. No offensive separation. No
frontend change. Stage 3 defects untouched. `COLLISION_MAX_PASSES` and
`COLLISION_MAX_DISPLACEMENT` not tuned. Nothing merged.

### The illegal-screen opportunity — reported, not built

The brief asked me to say where it would go if I saw it. I did: **`_contest_one` in
`screen_targeting.py`, on the GO AROUND / SWITCH branch** — the moment the model has already
decided the defender was beaten by the screen. Both players needed are in hand, and the
attribute is already in the model: `ND` ("No Dumb Fouls", `shared.py:3338`) carries 0.10 of
`NAVIGATE_WEIGHTS`, so a moving-screen check on the screener and a foul-on-contact check on
the defender would both read attributes this function already loads. Not built.

## Tunable Constants

| Constant | Value | Effect |
|---|---|---|
| `GOB_SCREEN_TARGETING` | off | Stage A master switch. Off = `OFFSET_SPOTS` placement, byte-identical. |
| `GOB_SCREEN_CONTEST` | off | Stage B master switch. Requires Stage A; alone it logs once and no-ops. |
| stand-off | *derived* | `collision_separation.separation_threshold` (2.62 for two median players). Not a knob — deliberately has no constant of its own. |
| GO AROUND lag | *derived* | The same `separation_threshold`. Also not a knob. |
| `NAVIGATE_WEIGHTS` | AG .35 / ST .35 / IQ .20 / ND .10 | Getting through a screen. Sums to 1.0 (house contract for a `×rand(1,6)` composite). **The place to tune the defender.** |
| `SCREEN_HOLD_WEIGHTS` | ST .50 / IQ .30 / CH .20 | Holding a screen. Deliberately not athletic. **The place to tune the screener.** |
| `SWITCH_WEIGHTS` | IQ .70 / CH .30 | Switching as communication. Raising it moves GO AROUND → SWITCH. |
| `COURT_MAX_X` / `COURT_MAX_Y` | 100 / 50 | The playing grid itself, not a chosen margin. |

Nothing above was tuned. Jamie tunes once, at the end.

## Open items

- **Stage A's proximity cost** (screener → receiver p90 17.0) is the one thing that should be
  settled before a flip. Candidate fix uses an existing derived constant, not a new one.
- Screener displacement p90 14.5 / max 19.5 with no reachability check — feeds the planned
  no-teleport capstone.
- Five override sites covered by construction but not exercised at runtime.
- `shared.calculate_screen_score` still draws from the global `random` (pre-existing).
