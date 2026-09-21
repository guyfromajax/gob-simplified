# Stage 2a — the frozen grid, built and measured

**The two numbers that decide whether this ships:**

| | |
|---|---|
| **freeze-miss rate** | **2.25 per game** (sim SD=1), **0.0052 per turn** — 90 occurrences across 40 games. At SD=0, 0.33/game. **The acceptance test passes.** |
| **interception delta** | **+0.40 ± 0.73 per game** (sim SD=1) — **not resolvable at n=40**. Nothing else resolves either: pts/team −0.78 ± 3.19, FG% −0.83 ± 2.20, possessions +0.93 ± 2.26. |

**And the one that says it worked:** with the flag on, a stored defender row **never changes once
written** — **0** overwrites inside a stamp and **0** writes between stamps, against **11,181**
overwrites in the same 8 games flag-off.

`GOB_PLACEMENT_FREEZE` is built and **default `"0"`. Not flipped, not re-cut, not merged.** Flag off
reproduces `equiv_v3_reference_70f7dd021_b1a.json` **40/40 on fingerprint AND draws in all four
cells**. Suite **2850 passed / 0 failed / 0 XPASS**, flag off *and* on. `GOB_BOXOUT_CONTEST` still
`"0"`; no constant in any tunables table was touched; `crash_destination.py` untouched.

---

## 1. Part A — the :7683 pre-seed: the data chose the other branch

**Jamie's lean was DELETE. The measurement says KEEP, and for two independent reasons.**

Pre-registered rule: reached ~100% → delete; not reached → do not delete, report, stop.

For every beat written at `phase_resolution.py:7683`, is it later covered by a stamp's **own**
non-empty grid? (`sys.monitoring`, read-only; fp and draws **40/40 in all four cells**.)

| cell | beats seeded | visited by a stamp | **stamp's own grid non-empty** | **NEVER covered** |
|---|---|---|---|---|
| sim SD=1 | 4,255 | 3,320 (78.0 %) | 3,320 (**78.0 %**) | **935 (22.0 %)** |
| sim SD=0 | 3,793 | 3,144 (82.9 %) | 3,144 (82.9 %) | 649 (17.1 %) |
| played SD=1 | 4,080 | 3,267 (80.1 %) | 3,267 (80.1 %) | 813 (19.9 %) |
| played SD=0 | 3,822 | 3,228 (84.5 %) | 3,228 (84.5 %) | 594 (15.5 %) |

**Not ~100 % — 78–84 %.** Deleting the pre-seed would leave **one beat in five with no row at all**,
which per `reports/step-identity-key-2026-09-21.md` §6 means a silent legacy redraw: the exact defect
this stage removes.

**The second reason is stronger and is a control-flow fact, not a statistic.** The pre-seed is
consumed **synchronously, in the same block that writes it**:

```
7683    beat["_step_state"] = {"index": …, "defense": _post_def_xy}
7687    _post_def_xy, … = _hco_step_def_xy(beat, …)        ← reads it back immediately
7691    _post_separation_map = _hco_shooter_separation_map(…)
7695    post_shoot = should_shoot(…, separation_map=_post_separation_map)
```

No stamp can run between 7683 and 7687. **Even for the 78 % later covered, deletion breaks the read
at the moment it happens** and the beat's own shoot decision falls back to a redraw.

**Part A therefore produced no code change** — its own decision rule forbade the deletion — so there
is no Part A commit. The finding is this section.

### What it does to the design

"Single producer" is not achievable and was never the right target. **A step's row belongs to whoever
creates the step; the stamp is a gap-filler for everyone else.** The invariant 2a implements is:

> **One draw per step. Written once, by whichever producer creates the step. Never redrawn.**

`announce_blocked_write` exists to keep that honest: every producer that got there first is named,
rather than the claim quietly drifting back to "single producer".

## 2. What was built

| file | change |
|---|---|
| **`BackEnd/utils/placement_freeze.py`** (new) | the flag, the two rule-26b announcements, the counters, and `apply_frozen_grid_to_animations` |
| `phase_resolution.py` `_stamp_contest_defender_grid` | **write-once on `defense`**; all three call sites keep running and keep filling gaps |
| `phase_resolution.py:5543` `_hco_step_def_xy` | freeze-miss announcement before the legacy reconstruction |
| `phase_resolution.py:4926` shot-contest selection | freeze-miss announcement before its fallback `compute_defender_grid` |
| `skeleton_step_emitter.py:1636` | under the flag the emit **renders the frozen row** and the `_hco_render_animations` stash is not written |
| `step_state.py` `build_step_states` | becomes a **read** — it no longer overwrites the row the contest used |

**Two deliberate deviations from the brief, both measured rather than assumed:**

1. **`offense` and `guard` keep refreshing; only `defense` is frozen.** They carry no placement draw,
   and blocking them would strip `offense` from the pre-seeded beats (§1), breaking the backward scan
   at `:5030` that the **SIM arm's coord write** depends on. That would trade a small cross-build
   inconsistency for a wrong-*moment* one.
2. **`attack_drive_clearance.py:1230–1272` was NOT re-pointed at the frozen grid.** It cannot be. It
   computes `defender_end_coords` for the drive beats **it is in the middle of creating**, and consumes
   them at `:1274` inside the same function — the identical ordering trap as §1. There is no frozen
   row to read yet. It remains a separate producer for its own decision and does **not** write
   `_step_state`, so it does not contaminate the frozen grid. **Seam B stays open**, and the scope
   report's claim that Stage 2 subsumes it is wrong.

Everything else in the brief's list is in. `:4924` and `:5030` already read `_step_state` and so read
the frozen row automatically; `:4928`'s fallback now announces.

## 3. The gate — flag off

| cell | fingerprint | draws | counters inert |
|---|---|---|---|
| sim SD=1 | **40/40** | **40/40** | miss 0, blocked 0 |
| sim SD=0 | **40/40** | **40/40** | miss 0, blocked 0 |
| played SD=1 | **40/40** | **40/40** | miss 0, blocked 0 |
| played SD=0 | **40/40** | **40/40** | miss 0, blocked 0 |

## 4. The draw invariant 2a actually preserves (brief item 1)

**The scope report's "draw count unchanged" is false, and so is the weaker "draws identical until the
first turn outcome differs".** Measured, seed 8000, sim SD=1:

| | |
|---|---|
| first turn whose cumulative draw count differs | **turn 8** |
| first turn whose `result_type` differs | **turn 12** |
| turn 8's result_type, both arms | **MAKE — identical** |

A contest can read a different coordinate and take a different path *without* changing the turn's
result type. Claiming parity up to the first outcome difference would have been wrong.

**The invariant that does hold, and is verified:**

> **2a changes no individual placement build's draw cost.** Divergence is entirely a matter of *which*
> builds happen, never of what one costs.

| | |
|---|---|
| first stamp call whose **draw cost** differs | call **#12** |
| the first **11** stamp calls | draw costs **identical, element by element** — 1,022 draws, 7 complete turns |
| costs either side of the break | off `[…131, 118, 59, 62]` vs on `[…131, 162, 165, 71]` |
| `_hco_step_def_xy` legacy redraws before divergence | **0 both arms** — the fallback is not the mechanism |

Whole-game draws are therefore **not** comparable and are reported as an outcome (§6), not a check.

## 5. The freeze-miss counter — the acceptance test (brief item 2)

| cell | total (40 games) | **per game** | per turn | by consumer | by reason |
|---|---|---|---|---|---|
| **sim SD=1** | 90 | **2.25** | 0.0052 | shot-contest selection 80, `_hco_step_def_xy` 10 | `stamped_empty` 83, `appended_after_last_stamp` 7 |
| sim SD=0 | 13 | 0.33 | 0.0007 | `_hco_step_def_xy` 13 | `appended_after_last_stamp` 13 |
| played SD=1 | 96 | 2.40 | 0.0057 | shot-contest selection 86, `_hco_step_def_xy` 10 | `stamped_empty` 88, `appended_after_last_stamp` 8 |
| played SD=0 | 16 | 0.40 | 0.0009 | `_hco_step_def_xy` 16 | `appended_after_last_stamp` 16 |

**~0 on any reading, and not suppressed.** Supporting counts (per game, sim SD=1): **780** blocked
writes, **6,911** frozen rows rendered by the emit, **59** emit steps with no frozen row.

The residual has a name: **89 % of it is the shot-contest defender selection hitting a step whose
stamp produced an empty row** (`stamped_empty`), not a step the freeze failed to reach. That is a
pre-existing gap in what the build produces, surfaced — not created — by this stage. The zone-only
skew (2.25/game at SD=1 vs 0.33 at SD=0) is consistent with zone placement being where empty rows come
from.

## 6. Did the freeze actually freeze? (brief items 3 and 5)

**Yes, exactly — when you measure the stored row.** My first attempt did not: the divergence probe
from `reports/placement-draw-divergence-2026-09-21.md` captures the stamp's **`grid` local**, i.e. what
the build produced. 2a does not stop the builds, so that probe cannot see the freeze and showed
almost no movement. Re-run against `step["_step_state"]["defense"]`:

| stored row, two stamps, same step, identical offense grid (sim SD=1, n=40) | flag OFF | **flag ON** |
|---|---|---|
| **identical** | 61.62 % | **99.67 %** |
| mean | 1.154 | **0.010** |
| p90 | 3.00 | **0.00** |
| max | 26.31 | 12.81 |

And keyed by **step object** rather than step index (n=8 games, sim SD=1):

| stored defender rows that CHANGED | flag OFF | **flag ON** |
|---|---|---|
| inside a stamp call (the stamp overwrote) | 11,181 (mean 2.87, max 26.31) | **0** |
| between stamps (a different producer wrote) | 0 | **0** |

**Once written, a row is immutable.** The 0.33 % residual in the index-keyed view is not a leak — it
is the **5.6 % index movement** measured in `reports/step-identity-key-2026-09-21.md` §2 showing up as
comparison noise, which is a neat independent confirmation that the object, not the index, is the key.

### What did NOT move, and why the brief's prediction was mis-specified

| pair | flag OFF | flag ON |
|---|---|---|
| SHOT vs STAMP | mean 1.09, p90 3.61 | mean 0.86, p90 3.49 |
| RENDER vs STAMP | 7.80 / 14.87 | 7.75 / 15.00 |
| DRIVE vs STAMP | 4.93 / 11.07 | 4.87 / 10.98 |

**"SHOT-vs-STAMP p90 should go to 0" was never reachable**, and the fault is in the statistic, not the
code: that pair compares the **shoot step's** coords to the **last stamped step's** row. They are
different moments, so they cannot agree even under a perfect freeze. I inherited the definition from
the previous pass and should have caught it there. **DRIVE is unchanged as expected** (§2, deviation 2).
`STEPSTATE GAP` / `REDRAW-SPREAD` are the `_diagnose` diagnostics on the played arm; the table above is
the same quantity measured directly, and it reads 0 **by construction**.

## 7. Outcomes (brief item 4)

n=40, both arms, both footings, paired per-seed deltas, CI = 1.96 × SEM.

**sim SD=1 — the footing that matters:**

| metric | flag off | flag on | paired Δ |
|---|---|---|---|
| **interceptions** | 3.12 ± 0.53 | 3.52 ± 0.54 | **+0.40 ± 0.73** |
| pts/team | 74.30 ± 3.15 | 73.53 ± 3.06 | −0.78 ± 3.19 |
| FG% | 39.77 ± 2.00 | 38.94 ± 1.91 | −0.83 ± 2.20 |
| FGA/game | 103.05 ± 1.49 | 104.50 ± 1.39 | +1.45 ± 1.74 |
| possessions | 40.92 ± 1.91 | 41.85 ± 2.02 | +0.93 ± 2.26 |
| STEAL turns | 16.20 ± 1.42 | 16.23 ± 1.38 | +0.03 ± 2.09 |
| draws/game | 83,018 ± 825 | 83,210 ± 999 | +192 ± 1,323 |

**Every metric in every cell is within CI, with one exception**: FGA/game at **sim SD=0**,
−2.15 ± 2.14 — marginal, and one boundary crossing out of 44 metric×cell tests is what chance
produces. I am not treating it as a finding.

**Can n=40 resolve this? No — and that is the honest answer to the brief's question.** The blast
radius predicted ~18 % of interceptions sit on an overwritten step, and interceptions are ~3.1 per
game, so the population at risk is ~0.6 interceptions/game. The observed +0.40 ± 0.73 is exactly the
scale where n=40 has no power. **Resolving a change this small needs a much larger n, or a paired
design on the sub-population (interceptions whose step was overwritten) rather than on the game total.**
What n=40 *does* establish is that nothing large or unexpected happened.

## 8. Gates

| | flag off | flag on |
|---|---|---|
| **§8.1 per-player coord-continuity corrections** | **0** (179.1 guard calls/game) | **0** (188.2 calls/game) |
| errors across all games | 0 | 0 |
| FT honour (windowed), n=8 | 51.1 % | 59.1 % |
| **suite** | **2850 passed, 20 skipped, 112 xfailed, 0 failed, 0 XPASS** | **identical** |

## 9. CPU (brief item 7)

Repo profiler (`GOB_SIM_PROFILE=1`), n=8, sim SD=1:

| | flag off | flag on |
|---|---|---|
| **mean wall / game** | 4.96 s | **5.50 s (+11 %)** |
| `anim.position_defenders` self | 7.96 s (20.1 %) | 8.47 s (19.3 %) |
| placement build calls/game | 509.2 | 508.9 |
| `emit.animation_steps` calls/game | 448.4 | 467.0 |

**2a is not free.** Build counts are flat (as designed — 2a keeps every build), so the cost is the
extra `apply_frozen_grid_to_animations` pass plus 4 % more emit calls. **Caveat: n=8 wall-clock, and
an identical flag-off configuration drifted 4.83 s → 4.96 s (+2.7 %) between two runs today, so the
noise floor is ~3 %.** +11 % is above that but thinly measured. **Worth a cleaner read before the
flip**, and it strengthens the case for Stage 3 (which deletes the redundant builds and is where the
~5 % saving lives).

## 10. Footing

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
n=40 seeds 8000–8039, **both arms × both `SEED_DEFENSES`** = 320 games for §3/§5/§7, **0 errors**.
**Catalogue state stated per table**: SD=1 seeds the six real defenses; **SD=0 leaves it empty and
every zone call plays man** — which is why the freeze-miss rate is 7× higher at SD=1 and why SD=1 is
the footing that decides.

All probes read-only (`sys.monitoring` frame reads, or the shipped profiler's timing wrappers) and
each reproduces the reference on its cells, stated in its own table.

## 11. What I did not do

- **Did not flip the flag, re-cut the reference, or merge.** Default stays `"0"`.
- **Did not close seam B** (§2, deviation 2) — the drive reconstruction cannot read a grid that does
  not exist when it runs. The scope report was wrong that Stage 2 subsumes it; it needs its own design.
- **Did not remove any build** — that is Stage 3, and it is where the CPU saving is.
- **Did not make `:7683` merge rather than replace.** It assigns `beat["_step_state"]` wholesale; the
  object-keyed measurement shows it causes no observed row change today, but it is the one writer that
  could, and 2b should make it a merge.
- **Did not re-measure the divergence pass's consumer pairs on a corrected same-moment definition**
  (§6). The pairs as defined cannot reach 0 and should be redefined before being used as a gate again.
- **Did not resolve the outcome question** (§7). n=40 cannot.

## 12. Tunable constants

**Nothing was retuned.** No constant in the tunables tables of the two prior reports was touched.

| new knob | where | default | effect |
|---|---|---|---|
| `GOB_PLACEMENT_FREEZE` | `placement_freeze.py:24` | **`"0"`** | the whole stage; off = byte-identical |

| unchanged, for reference | where | value |
|---|---|---|
| `CONTEST_EUCLIDEAN_RADIUS` | `constants/__init__.py:364` | `11` |
| `ATTACK_DRIVE_CONTEST_RADIUS` | `attack_drive_clearance.py:42` | `= CONTEST_EUCLIDEAN_RADIUS` |
| `HELP_SAG` / `HELP_SAG_JITTER` | `shared_defense.py:1937–1938` | `{0.30, 0.55}` / `0.10` |
| `GOB_BOXOUT_CONTEST` | `utils/boxout_contest.py` | `"0"` |
