# The zone empty-zone branch: how big is it, and what could replace it

**Lead answer — Q1.** The empty-zone branch resolves **18.6% ±0.54 of all zone defender-steps** on the sim arm and **18.05% ±0.50** on played: about **2,090 defender-steps a game**, roughly one zone defender-step in five. That is neither cosmetic nor dominant *in aggregate* — but the aggregate hides the real shape. It is the **majority behaviour for specific defenders**: the 2-3 centre spends **48.9% ±2.0** of his steps on it, the 1-3-1 power forward **48.9% ±2.2**, the 1-3-1 centre **31.7% ±1.8**, and 1-3-1 as a whole runs at **25.8% ±0.8**. And the menu is smaller in practice than on paper — the 2-3 PF picks from a 7-spot list but stands on **2.08 distinct spots a game, one of them 87% of the time**; the 2-3 PG uses **1.82 of 6**. Two findings came out of the trace that were not in the brief and change the picture: **`_point_in_zone` really is a polygon test** (ray casting over the spot list as a vertex ring), so a "nearest point in the zone area" fix *is* well-defined — but **16 of the 55 zone definitions are geometrically broken** (14 self-intersecting rings, 2 single-spot zones that `_point_in_polygon` rejects by construction), so for those defenders the empty branch is not a fallback at all, it is the only branch that can ever fire.

## Footing (rule 6e)

- **Tree:** `feature/animation-reward` at **`52b0b2d6e`** (the zone-placement-scope report commit; no engine code differs from `ed347a73c`). Read-only — nothing landed.
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, **`SEED_DEFENSES=1`**, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM.
- **Sim rows:** `ARM=sim`, `_is_full_simulation` **True** throughout the quarter loop.
- **Played rows:** `ARM=played`, `_is_full_simulation` **False only inside the four gated Animator methods** at Pattern A.
- **Probe integrity:** sim **40/40** identical (`fp`, draws, points, turns) to `equiv_v3_sim_reference_9910cd6fd.json`; played **40/40** identical between the probed and an unprobed run of the same 40 seeds at this HEAD (the played reference is the commit `d9a4f1517`, not a stored artifact, so equality was established against a clean run rather than a file). Re-verified **40/40** after the probe was re-instrumented mid-pass, and **40/40** again on each of the two side probes. Probe exceptions: **0**.
- The probe re-evaluates the ladder's predicates (all deterministic geometry) and touches no RNG. As in the previous zone pass, only the build covering the most steps is kept per turn, so repeated stamp builds do not double count.
- Probes (session scratchpad, uncommitted): `zn2/rung_probe.py`, `zn2/drawcost.py`, `zn2/guards.py`.

## Q1: How often does the branch fire?

There are **six** rungs, not five: before `assign_zone_defender_coords` is reached at all, `assign_all_zone_defenders` runs an overlap pass (`_detect_overlapping_zones` → `_resolve_overlap_assignments`) that can assign a defender outright. That rung is the largest single one and was not in the brief's list.

**Share of zone defender-steps by rung, n=40, `SEED_DEFENSES=1`:**

| rung | sim | played |
|---|---|---|
| **0** overlap — resolved before the ladder | **38.83% ±0.71** | **39.41% ±0.61** |
| **a** ball handler in zone | 15.30% ±0.23 | 15.43% ±0.23 |
| **b** deep-location mapping | **0.00% ±0.00** | **0.00% ±0.00** |
| **c** exactly one player in zone | 21.68% ±0.61 | 21.49% ±0.65 |
| **d** more than one player in zone | 5.56% ±0.27 | 5.62% ±0.25 |
| **e** **nobody in zone (the menu pick)** | **18.62% ±0.54** | **18.05% ±0.50** |
| zone defender-steps per game | 11,213 ±310 | 11,464 ±386 |

The two arms agree inside the CI on every rung, as they should — placement is the same code on both.

**Rung b never fires.** Across 448,510 sim defender-steps the deep-location branch (`shared_defense.py:824-849`) was taken **zero times**. It is dead code on this footing: by the time placement runs, the ball handler's spot is never one of `deep key` / `deep lower wing` / `deep lower baseline` / `deep upper wing` / `deep upper baseline`. Worth knowing before anyone maintains it.

**By shell (sim):**

| shell | overlap | bh in | one | many | **empty** | steps/game |
|---|---|---|---|---|---|---|
| 2-3 | 45.0% ±0.7 | 14.2% ±0.4 | 20.3% ±0.5 | 4.1% ±0.3 | **16.5% ±0.6** | 3,496 ±223 |
| 3-2 | 32.6% ±1.7 | 15.3% ±0.5 | 35.9% ±1.4 | 3.3% ±0.2 | **13.0% ±0.6** | 3,788 ±255 |
| 1-3-1 | 39.4% ±0.9 | 16.4% ±0.3 | 9.3% ±0.5 | 9.1% ±0.6 | **25.8% ±0.8** | 3,928 ±206 |

Played agrees: 2-3 16.1% ±0.7, 3-2 13.2% ±0.6, 1-3-1 24.9% ±0.7.

**Empty share of each defender's own zone steps (sim) — this is the table that matters:**

| shell | PG | SG | SF | PF | C |
|---|---|---|---|---|---|
| 2-3 | 2.3% ±0.6 | 7.3% ±0.9 | 15.4% ±1.2 | 8.4% ±1.0 | **48.9% ±2.0** |
| 3-2 | 16.8% ±1.1 | 7.6% ±0.8 | 22.6% ±1.8 | 6.9% ±1.0 | 10.9% ±1.2 |
| 1-3-1 | 6.0% ±0.7 | 19.8% ±1.1 | 22.5% ±1.5 | **48.9% ±2.2** | 31.7% ±1.8 |

**By ball location (sim, top of the volume):** `key` 25.7% empty (3,649 steps/game), `lower wing` 18.5%, `lower lowPost` 18.4%, `upper wing` 17.4%, `upper midWing` 16.2%, `midLane` 11.1%, `lower midCorner` 3.7%, `lower midPost` 1.4%. The branch is most common with the ball at the top — exactly when a zone should be at its most shaped.

### How small is the effective menu?

For each defender, the number of **distinct spots he actually stands on** across a game when the branch fires, against the size of his spot list:

| shell\|pos | e steps/game | distinct spots/game | menu size | most-used spot |
|---|---|---|---|---|
| 2-3 PG | 15.9 ±4.2 | **1.82 ±0.41** | 6 | midLane 39% |
| 2-3 SG | 51.8 ±7.4 | 3.45 ±0.37 | 6 | midLane 55% |
| 2-3 SF | 107.7 ±11.5 | 3.65 ±0.21 | 7 | lower midPost 43% |
| 2-3 PF | 58.5 ±7.5 | **2.08 ±0.31** | 7 | **upper midPost 87%** |
| 2-3 C | 341.9 ±24.5 | 4.03 ±0.25 | 5 | midLane 42% |
| 3-2 PG | 128.6 ±13.2 | 4.47 ±0.32 | 6 | midLane 45% |
| 3-2 SG | 58.0 ±7.4 | 3.30 ±0.30 | 6 | upper midPost 51% |
| 3-2 SF | 171.5 ±17.4 | 3.73 ±0.26 | 6 | lower midPost 44% |
| 3-2 PF | 53.2 ±9.7 | **2.60 ±0.32** | 8 | midLane 63% |
| 3-2 C | 83.7 ±11.5 | 3.45 ±0.27 | 8 | midLane 39% |
| 1-3-1 PG | 46.8 ±6.2 | 3.48 ±0.35 | 10 / 6 / 8 | topLane 54% |
| 1-3-1 SG | 156.3 ±11.8 | 4.15 ±0.23 | 4 / 3 / 8 | upper wing 39% |
| 1-3-1 SF | 179.1 ±17.2 | 4.22 ±0.22 | 4 / 8 | lower wing 49% |
| 1-3-1 PF | 387.3 ±29.8 | 5.38 ±0.35 | 8 | topLane 41% |
| 1-3-1 C | 249.0 ±19.5 | 6.15 ±0.42 | 11 / 4 / 1 | midLane 47% |

Jamie's suspicion is confirmed and then some: the effective menu is **2–6 spots**, and for four of the fifteen defenders a single spot accounts for **63–87%** of every empty step. The 2-3 PF is effectively parked at `upper midPost` whenever his zone is vacant.

One eye-test note that falls out of this: **`midLane` is the most-used rest spot for six of the fifteen defenders**, including both 2-3 guards. A 2-3 guard who sinks to the middle of the lane whenever his zone empties is not what a 2-3 looks like.

### What happens to the menu pick afterwards

The (e) branch's answer is not necessarily what renders. Two passes can move it:

| rung | n (sim) | ball-handler fallback tail overwrote it | de-stacking offsets moved it |
|---|---|---|---|
| 0 overlap | 174,147 | 0.00% | 30.74% |
| a bh in | 68,603 | 0.00% | 44.88% |
| c one | 97,345 | 0.86% | 46.82% |
| d many | 24,848 | 0.24% | 52.68% |
| **e empty** | **83,567** | **2.07%** | **69.58%** |
| all | 448,510 | 0.59% | 44.84% |

The ball-handler fallback at the end of `assign_all_zone_defenders` is rare (0.59% overall). The real post-ladder mover is **`_apply_multi_defender_offsets`** (`shared_defense.py:1368`), which nudges defenders apart when two are credited with the same offensive player — and it fires on **69.6% of empty-branch steps**, because empty-zone defenders all get credited with whichever player happens to be closest to their menu spot and therefore stack. So most empty-branch positions are already being perturbed after the fact, by a de-stacking rule rather than by anything about defence.

## Q2: What does `_point_in_zone` actually test?

**It builds a polygon.** `_point_in_zone` (`shared_defense.py:557`) normalises the point, optionally flips it, and delegates:

```python
    return _point_in_polygon(x, y, zone_coords)
```

and `_point_in_polygon` (`shared_defense.py:390`) is a real ray-cast:

```python
def _point_in_polygon(point_x, point_y, polygon_coords):
    """Check if a point is inside a polygon using ray casting algorithm."""
    if len(polygon_coords) < 3:
        return False
    # PERF: bounding-box reject before the two O(n) passes below...
```

— a `< 3` guard, a bounding-box reject, an on-vertex/on-edge pass with a 0.01 cross-product tolerance, then even-odd ray casting.

So the spot list is **the polygon's vertex ring, in list order**. A "nearest point in the zone *area*" fix is therefore well-defined in principle — the area is the ray-cast interior.

**In practice, for 16 of the 55 zone definitions, it is not.** Treating the list as a vertex ring only works if the list is written as a boundary walk, and many are not:

| defect | count | which |
|---|---|---|
| **single-spot zone** — `< 3` guard makes `_point_in_polygon` return **False for every point** | **2** | `ZONE_131_LOWER_CORNER_SHIFT["C"] = ["lower corner"]`, `ZONE_131_UPPER_CORNER_SHIFT["C"] = ["upper corner"]` |
| **self-intersecting ring** — the even-odd interior is not the region the spot names describe | **14** | 2-3: NORMAL PG/SF/PF, LOWER_SHIFT SG/SF/PF, UPPER_SHIFT PG/SF/PF · 3-2: LOWER_SHIFT PF, UPPER_SHIFT C · 1-3-1: NORMAL C, LOWER_SHIFT C, UPPER_SHIFT C |
| **duplicate vertices** | 3 (subset of the above) | `ZONE_32_LOWER_SHIFT["PF"]`, `ZONE_32_UPPER_SHIFT["C"]`, `ZONE_131_NORMAL["C"]` — the `basketSpot` repeats the brief flagged. **Reported, left alone.** |

A worked example — `ZONE_23_NORMAL["SF"]`, in list order:

```
lower midCorner   (81, 7)
lower corner      (88, 6)
lower lowPost     (86, 19)
lower midPost     (80, 19)
lower apex        (80, 15)
lower bird        (85, 15)
lower midBaseline (89, 15)   -> back to (81, 7)
```

The last three vertices run back and forth along `y = 15`, crossing the edges already laid down. Rasterising the ray-cast at 0.25-unit resolution, the region actually tested is **55.2 square units against a 98.0 convex hull** — the defender's own baseline area is roughly half-covered by the test that decides whether anyone is in it. (Convex hull is an upper bound and a genuinely concave zone would sit under it legitimately; the self-intersection is the defect, the ratio is the size of it.) The most affected: `ZONE_131_NORMAL["C"]` tests **123.7 of 247.0**, `ZONE_131_UPPER_SHIFT["C"]` **13.9 of 26.5**, `ZONE_131_LOWER_SHIFT["C"]` **14.2 of 26.5**, the three 2-3 SF/PF rings **51.7–55.2 of 90–98**.

**This is why the (e) rates are what they are.** For the two single-spot centres the branch is not a fallback — `_point_in_polygon` cannot return True, so rungs a/c/d are unreachable and the defender is pinned to one coordinate by construction (180 such steps in the 40-game sim sample, all rung e). For the self-intersecting rings the zone under-tests its own area, so players standing in it are not seen, and the defender falls to the menu pick more often than the spot list implies. The 2-3 C at 48.9% and the 1-3-1 PF at 48.9% sit on top of exactly this.

## Q3: Blast radius — this one will not keep played byte-identical

**Confirmed, and it should be stated first: placement runs on both arms.** `position_zone_defenders` is reached through `_build_all_animations` on the played arm and on the sim arm alike; the rung shares in Q1 are the same within CI on both. Every change landed this workstream has kept played byte-identical (`d9a4f1517`, 40/40, re-confirmed in this pass). **Any change to this branch breaks that, on both arms, on the first seed.** It is not a cleanup and it cannot be landed behind the kind of sim-only flag the crash and coord work used, because the thing being changed is the shared producer.

What moves when a zone defender's coordinate moves:

| consumer | how it reads placement | what changes |
|---|---|---|
| **contest / shot defence** | `rendered_positions_for_contest` → `_uess_sync_emitted_shot_coords` (HCO/FCP), and the Euclidean contest radius over the rendered defender grid | which defender contests, and at what distance — so FG%, 3PT% and block rates |
| **StepState defender grid** | `defender_grid_from_animations` (`defender_placement.py:1285`), consumed at `step_state.py:76` | every per-step defensive read built on the grid |
| **steals / interception** | the same grid, walk-time | steal rate and who gets credited |
| **rebound distances** | crash destinations are applied against rendered positions | who is nearest the ball, so OREB/DREB split and second-chance points |
| **over-the-back** | the ≤4-unit proximity test between crasher and boxer-out | in-play count and fouls called |
| **drive clearance** | `attack_drive_clearance.py`, `_zone_boundaries_for_spot` and the defender overrides | whether a drive is clear, so drive frequency and finish quality |
| **next-turn seeds** | end-of-turn `player.coords` carry into the next turn's start state | compounds across the possession chain |
| **`phase_resolution.py:8747`** | `random.choice(defenders_guarding_ball_handler)`, drawn **only when ≥2 defenders are credited with the ball handler** | **the RNG stream shifts** |

That last row is the one that makes byte-equality impossible rather than merely unlikely. Measured on sim, n=40: `_zone_ball_handler_guards` is called **9.2 times a game**, returning 0 guards 56.9% of the time, 1 guard 16.9%, and **≥2 guards 26.2% — so the draw fires about 2.4 times a game**. Small in itself, but a draw that appears or disappears re-phases every subsequent draw in the game. Any fix here is a **stream change**, and per the standing poison-test rule it cannot be validated by exact diff.

**Plainly: landing anything in this branch requires re-cutting both references — the played reference at `d9a4f1517` and `equiv_v3_sim_reference_9910cd6fd.json` — and it requires Jamie's eye-verification, because the distributional check alone will not tell you whether a 2-3 now looks like a 2-3.** Budget it as a tuning change, not a cleanup.

## Q4: Options (not implemented, no winner picked)

Terminology, because the distinction matters here: **draw-neutral** = adds and removes no RNG draws of its own; **stream-identical** = byte-identical output. **None of these options is stream-identical**, because all of them move coordinates and therefore re-phase the `:8747` draw. Draw-neutrality only says how *badly* the stream moves.

### Option A — route (e) through `get_defender_coords` like every other rung

*What the defender does instead:* the same menu spot, but passed through the shared placement routine so it picks up the aggression adjustment and the `randint` jitter that rungs a/c/d all get.

*Blast radius:* everything in Q3, at the smallest amplitude — the defender stays in the same neighbourhood, ±1–4 units.

*Draw-neutral:* **no.** Measured: `get_defender_coords` consumes **1.156 draws per call** (22,410 calls / 25,898 draws, seed 8000, sim). At ~2,090 empty steps a game that is **≈ +2,400 draws/game on a 69,190 base, about +3.5%**.

*Cost:* smallest — roughly ten lines in one branch. **But there is a semantic problem worth flagging before anyone calls this the safe option:** `get_defender_coords` positions a defender *relative to an offensive player he is guarding*. In the (e) branch there is no such player. Passing the menu spot in as if it were one would place the defender at an offset *from* the spot rather than on it, which is not the same as "jitter the spot". If the intent is only aggression + jitter, that is a narrower change than reusing the function — and it would be worth being explicit about which of the two is meant.

### Option B — a continuous position inside the defender's own area, biased toward the ball

*What the defender does instead:* instead of snapping to the nearest listed vertex, take a point on the segment from the zone's interior toward the ball handler, clamped to stay inside the polygon — a defender who *sinks toward the ball* rather than teleporting between 2–6 fixed spots.

*Blast radius:* everything in Q3, at the largest amplitude. This is the option that actually changes what a zone looks like, and the one most likely to move FG% and rebound position. It also removes the `midLane` parking that six of fifteen defenders currently do.

*Draw-neutral:* **yes, in itself** — a deterministic geometric construction adds no draws (though the stream still re-phases via `:8747`, and any jitter added on top would not be).

*Cost:* the largest, and **it has a prerequisite**: a continuous "inside the area" position is only meaningful if the area is meaningful, and by Q2 **16 of 55 rings are not**. This option requires re-ordering those rings into proper boundary walks (and deciding what the two single-spot corner-shift centres are supposed to cover) **before** the placement change, as a separate step with its own verification. Re-ordering the rings is itself a behaviour change — it alters which rung fires — so it cannot be slipped in as a no-op.

### Option C — B on top of A

*What the defender does:* continuous sink toward the ball, then the shared aggression adjustment and jitter on top.

*Blast radius:* the union. This is the version that would look most like real zone defence and the one that most needs eye-verification.

*Draw-neutral:* **no** — inherits A's ≈ +3.5% draws.

*Cost:* A + B, and it inherits B's ring-repair prerequisite.

### A fourth thing, listed because the measurement turned it up

**Option 0 — repair the 16 broken rings and change nothing else.** Not a fix to the branch; a fix to the geometry the branch is a symptom of. It would lower the (e) rate on its own (players standing in a zone would start being seen), and it is the prerequisite for B and C anyway. Draw-neutral in itself, not stream-identical. It is the smallest change that improves the *cause* rather than the *fallback*, and it is separable from any decision about what an empty-zone defender should do. Worth considering as its own pass whichever option is chosen.

### Tunable constants these options would introduce

| option | constant | effect |
|---|---|---|
| A | none new — reuses `aggression_call` and the existing `randint` ranges in `calculate_defender_coords` | |
| B / C | a sink fraction (how far from the zone's rest position toward the ball) | 0 = current parked behaviour, 1 = full ball-side commitment |
| B / C | a clamp margin (how far inside the polygon edge the point is held) | keeps a sinking defender from standing on his own boundary |
| 0 | none | pure data repair |

## Q5: The attribute hook

Jamie is right that this is the natural place for it — **where a defender sinks when his area is empty is exactly an IQ read**, and it is the one decision in zone placement that is currently made with no information at all. But the options differ sharply on whether they leave room for it:

- **Option A leaves no room.** The menu pick is unchanged; aggression and jitter are not attributes, and there is no scalar in the branch for IQ or team defensive efficiency to modulate. Landing A first and adding the hook later would mean re-opening the same branch, re-cutting both references a second time, and asking for a second eye-verification. That is the argument against treating A as the cheap first step.
- **Options B and C are the natural carrier.** A continuous position has exactly the scalar the hook needs: the **sink fraction**. Higher IQ (or higher team defensive efficiency) sinks further and earlier toward the ball and toward the danger; lower sits at the rest position. A second scalar is available too — a *lag*, how many steps the defender takes to react to the ball moving — which is closer to what IQ means in a zone and mirrors the graded `_defender_lag_fraction` the man path already has (`defender_placement.py:1219`), so the two paths would finally share a model of "this defender reads it late".

**Recommendation on sequencing, not on which option:** if the attribute hook is part of the goal rather than a later nice-to-have, it should be **designed in from the start**, which means B or C, which means the ring repair (Option 0) comes first. Retro-fitting the hook onto A costs a second full reference re-cut and a second eye pass for the same branch.

## Not covered

- **Nothing was landed.** No placement logic, constant, threshold or balance number was touched; `git diff HEAD` over tracked files is empty and the only new file is this report.
- The duplicate `basketSpot` entries in `ZONE_131_NORMAL["C"]` (and the same pattern in `ZONE_32_LOWER_SHIFT["PF"]` / `ZONE_32_UPPER_SHIFT["C"]`) are **reported and left alone**, per the brief.
- The crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1 (Final Turn) and R2 (stopper) were not touched.
- **Not measured:** what any of the Q4 options would actually do to FG%, rebounding or the arm gap. That needs an implementation and a re-cut, which this pass explicitly did not do.
- **Not investigated:** why rung b (deep-location) never fires — only that it does not, across 448,510 defender-steps.
- The overlap rung (38.8%, the largest) was traced only far enough to separate it from the ladder; `_resolve_overlap_assignments` itself was not audited.
