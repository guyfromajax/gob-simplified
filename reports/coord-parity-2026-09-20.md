# Sim-vs-played shot-moment coordinate mismatch — diagnosis

**No engine behaviour was changed.** Read-only probes only; every probed run reproduces `equiv_v3_reference_ec4f5acfc_poslookup2.json` **40/40 on fingerprint and draws**, on all four cells, so the numbers below are measured on an unperturbed engine. `develop` is merged in (`git rev-list --count HEAD..develop` = 0).

**One-line answer:** the sim arm never builds HCO animations, so the entire HCO coordinate pipeline — the schema emitter, the UESS shot-geometry sync, and the end-of-turn coord write — falls back to substitutes. **The mismatch is HCO-only.** Every other phase emits on both arms at 96–100% and is not a divergence source.

## 1. First divergence

### The chain

| # | file:line | what happens |
|---|---|---|
| 1 | **`BackEnd/models/animator.py:1214`** | `Animator.skeleton_to_animations` — `if self.game.game_state.get("_is_full_simulation", False): return []` |
| 2 | **`BackEnd/engine/skeleton_step_emitter.py:1607`** | the HCO schema emitter calls that method to build `animations` when the turn did not carry them |
| 3 | **`BackEnd/engine/skeleton_step_emitter.py:1622-1623`** | `if not skeleton_steps or not animations: return None` — on sim `animations == []`, so **the whole HCO emit returns None**. The comment five lines later says it outright: *"Sims never reach here (animations == [] above)"* |
| 4 | **`BackEnd/models/turn_manager.py:4024-4029`** | `_emit_hco_animation_steps` gets `None` and returns without ever setting `result["animation_steps"]` |
| 5 | **`BackEnd/utils/shared.py:3996`** | `sync_lineup_coords_from_turn`'s `animation_steps` layer is skipped, so `positions` never receives the rendered end coords |
| 6 | **`BackEnd/utils/shared.py:4086`** | `apply_sim_crash_destinations` (sim-only) then advances the crashers **by arithmetic** into `positions`, which is written to `Player.coords` |

**The responsible gate is `_is_full_simulation` at `animator.py:1214` specifically** — not Pattern A in general, and not `GOB_SIM_HCO_COORD_WRITE` or `GOB_SIM_CRASH_APPLY`. Those two flags are *downstream compensations* for it (see §4). The other three gated Animator methods are not implicated in the HCO path.

### The concrete turn

Seed 8000, `SEED_DEFENSES=1`. Turn 1 is an **HCO/MISS**. Traced at every writer:

| | sim | played |
|---|---|---|
| `turn_result["animation_steps"]` | **absent (0)** | **present (18 steps)** |
| `turn_result["animations"]` | **absent** | present |
| `apply_sim_crash_destinations` moved | **9 players** | 0 (guarded off — the turn has steps) |
| players `sync_lineup_coords_from_turn` wrote | 9 | 10 |

At that sync's **entry both arms are byte-identical — 0 of 24 players differ.** At its **exit, 10 of 24 differ.** The divergence is created inside `sync_lineup_coords_from_turn`.

```
player      sim              played           delta
104c7b0f    (88.0, 25.0)     (86.0, 19.0)      6.32
80f3ca79    (81.0, 19.0)     (83.0, 28.0)      9.22
f608a824    (85.0, 20.0)     (88.0, 27.0)      7.62
9c044323    (73.0, 10.0)     (68.0, 14.0)      6.40
a0a0f2d7    (82.0, 26.0)     (87.0, 24.0)      5.39
c13c8088    (84.0, 19.0)     (88.0, 22.0)      5.00
bd5dbf1f    (84.0, 22.0)     (81.0, 24.0)      3.61
e590d342    (82.0, 28.0)     (80.0, 31.0)      3.61
60d85fb6    (84.0, 27.0)     (82.0, 30.0)      3.61
7219a92c    (84.0, 27.0)     (82.0, 26.0)      2.24
```

**One earlier difference is transient and worth ruling out.** Mid-turn, at `apply_coords_from_animations_list` exit, the arms differ by 13–44 units — played has applied its animator row-ends, sim has applied nothing. `_write_sim_hco_placement_coords` (`phase_resolution.py:5024`) then runs on the sim arm and **fully reconciles it**: turn 1 ends with 0/24 differing at `turn:exit`. So `GOB_SIM_HCO_COORD_WRITE` is doing its job; it is not the leak. The leak is the *post-shot* write, one stage later.

## 2. Scope

n=40 seeds 8000–8039, both arms, both footings. Counts are over 40 games.

### The emitter and the shot-geometry sync

| | sim `SD=1` | played `SD=1` | sim `SD=0` | played `SD=0` |
|---|---|---|---|---|
| `build_skeleton_animation_steps` returned **None** | **4996/4996 (100%)** | 174/8447 (2.1%) | **4992/4992 (100%)** | 0/8857 (0.0%) |
| `_uess_sync_emitted_shot_coords` returned **None** | **3437/3437 (100%)** | 87/3614 (2.4%) | **3587/3587 (100%)** | 0/3879 (0.0%) |

### By phase — `SEED_DEFENSES=1`, turns carrying `animation_steps`

| phase | sim turns | sim with steps | played turns | played with steps | diverges? |
|---|---|---|---|---|---|
| **HCO** | 4913 | **28 (0.6%)** | 4855 | **4749 (97.8%)** | **YES** |
| BASELINE_INBOUND | 2458 | 2458 (100%) | 2391 | 2391 (100%) | no |
| DREB | 1773 | 1773 (100%) | 1755 | 1755 (100%) | no |
| SIDE_INBOUND | 1665 | 1665 (100%) | 1683 | 1683 (100%) | no |
| FCP | 1140 | 1119 (98.2%) | 1067 | 1065 (99.8%) | no |
| HCT | 1118 | 1093 (97.8%) | 1113 | 1112 (99.9%) | no |
| FAST_BREAK | 906 | 630 (69.5%) | 856 | 634 (74.1%) | no (both ~70%) |
| OREB | 748 | 720 (96.3%) | 808 | 781 (96.7%) | no |
| FREE_THROW | 2042 | 0 | 2210 | 0 | no (neither emits) |

`SEED_DEFENSES=0` is the same shape: HCO sim 35/4910 (0.7%) vs played 4973/4987 (99.7%); every other phase within a point of parity.

**The mismatch lives entirely in HCO.** The fast break is ~70% on both arms, so the FB coord differences reported earlier are a *consequence* of games having already diverged, not an independent source.

### Size of the sim-side substitute

`apply_sim_crash_destinations` runs on **68.4%** of sim HCO turns (`SD=1`; 69.5% at `SD=0`) and on **0.0%** of played HCO turns.

| | sim `SD=1` | sim `SD=0` | played (both) |
|---|---|---|---|
| player-positions moved (40 games) | **29,530** | **29,946** | 9 |
| **mean displacement** | **11.80** | **11.51** | 16.45 |
| p50 | 10.85 | 10.47 | 19.11 |
| p90 | 21.15 | 20.62 | 27.51 |
| max | 48.77 | 43.38 | 27.51 |

**9 of the 10 on-court players move on every affected turn** (median 9, max 9) — everyone except the shooter, who is excluded by `canonicalize_post_shot_overlays`.

### Offense or defense — both

10 games, sim arm, `SD=1`:

| side | moves | share | mean displacement | max |
|---|---|---|---|---|
| **DEFENSE** | 4,190 | **54.7%** | **10.21** | 40.52 |
| **OFFENSE** | 3,476 | **45.3%** | **13.20** | 48.76 |
| SHOOTER | 0 | 0% | — | — |

### Accumulates or resets — it recurs, and cannot be isolated past turn 2

Turn-boundary divergence, seed 8000:

| turn | players differing | mean | max |
|---|---|---|---|
| 1 | **0** | 0.00 | 0.00 |
| 2 | **10** | 57.53 | 70.32 |
| 3 | 10 | 26.10 | 54.15 |
| 5 | 10 | 10.16 | 19.14 |
| 6 | 10 | 59.44 | 77.00 |
| 11 | 10 | 60.71 | 74.95 |
| 21 | 10 | 62.79 | 81.10 |

**It never resets.** From turn 2 onward all ten on-court players differ, in every turn, for the rest of the game. But the honest reading is stronger than "it accumulates": the means swinging between 9 and 63 units on a 100-unit court mean the two arms are running **different possessions** by then — the coordinate divergence has already produced a *behavioural* divergence, which is the whole problem. Past turn 2 the two games are no longer comparable turn-for-turn, so "does the coord error grow" is not a measurable question; what is measurable is that **the mechanism re-fires on ~68% of HCO turns in every game**, so it is continuously re-created rather than decaying.

## 3. Classification

### (a) Animation-only — not divergence sources

BASELINE_INBOUND, SIDE_INBOUND, DREB, OREB, FCP, HCT and FAST_BREAK all emit `animation_steps` on both arms at 96–100%, so both arms write `Player.coords` from the **same** source on those turns. FREE_THROW and TIMEOUT emit on neither. None of these is a divergence source.

### (b) Real — the engine's decisions read the differing coords

#### b1. HCO shot classification and the contest loop — **the largest**

`_uess_sync_emitted_shot_coords` (`phase_resolution.py:4710`) exists to make shot logic read the rendered geometry. Its own docstring states what it fixed: *"it mis-scored 2PT/3PT classification (~25%, shooter) AND over-contested shots (~6%, defenders fully-arrived in logic but mid-move on screen)."*

**Line 4737: `if not shooter_id or not skeleton or not animations: return None`.** With `animations == []`, this returns `None` on **100% of sim HCO shots** (3,437/3,437 at `SD=1`; 3,587/3,587 at `SD=0`) and 0–2.4% of played ones.

The caller at **`phase_resolution.py:9566-9576`** then takes the other branch, and the two arms consume **two different coordinate frames by name**:

| | played | sim |
|---|---|---|
| `ShotAttemptGeometry.source` | `hco-emitter-shot-step` | `hco-stepstate-shot-step` (or `hco-final-grid-shot-step`) |
| defender coords from | `Player.coords` after the emitter pre-pass synced all ten | the skeleton shot step's StepState defender grid |
| shooter spot from | the emitted shoot-step coord | `set_shooter_coords_from_skeleton_last_step` |

Consumers: `shot_manager.resolve_shot` (via `shot_attempt_geometry`) and `_resolve_hco_shot_defenders` (`shot_manager.py:255`). **What it changes:** 2PT/3PT classification and which defenders are counted as contesting — the two quantities the July commit measured at ~25% and ~6% on the played arm.

#### b2. Rebound selection — the measured OREB gap

`_rebound_distance` (`shared.py:1687`) reads `player.coords` directly; `_rebound_entries` (`shared.py:1719`) scores every candidate on that distance, and `select_rebounder_by_score` picks the winner from it. On the played arm those coords are the emitter's interrupted positions; on the sim arm they are the crash arithmetic, **mean 11.5–11.8 units of substituted position, applied to 9 of 10 players on 68% of HCO turns**.

**What it changes:** the rebound winner. This is the already-observed asymmetry — turning on `GOB_REBOUND_FROM_ARRIVAL` moved OREB share **+3.06 on sim but +5.50 on played**, because the two arms were scoring from differently-derived positions.

#### b3. Interception / StepState defender grid

`skeleton_step_emitter.py:1625-1633`: the played arm stashes the exact `animations` it drew from on the game and StepState extracts `defense` from **those** objects, *"so the interception contest judges against the one draw that reached the screen."* The comment continues: *"Sims never reach here (animations == [] above) → StepState falls back to `compute_defender_grid`'s own single draw (no render to match)."*

**What it changes:** which defender is positioned where for the pass-interception contest — two independent draws of the same distribution, so the distributions agree but no individual turn does.

#### b4. Force-foul defender selection

`select_defender_closest_to_victim` (`phase_resolution.py:1006`) picks the closest defender by Euclidean distance over `player.coords`, and `defender_coords_by_pos_from_lineup` (`:964`) builds its input from the same. **What it changes:** which defender commits an intentional foul. Low volume, but it reads the diverging frame.

## 4. Intended or accidental

| # | site | commit | verdict |
|---|---|---|---|
| 1 | `animator.py:1214` | **`01c3dddc1`** (2026-01-08) *"Performance: Skip animation generation and skeleton loading for full simulations"* | **Deliberate** — a performance optimisation, and the root cause. Nothing about it anticipated that the coordinate pipeline would later be built on the animator's output. |
| 2 | `skeleton_step_emitter.py:1622` | **`c0645ba5d`** (2026-05-22) *"bringing Claude up to speed on UESS transition"* | **Accidental drift.** The UESS emitter was written to require `animations`, which #1 had already removed for sims four months earlier. The `return None` is a guard, not a policy. |
| 3 | `phase_resolution.py:4737` | **`0050c5ebc`** (2026-07-05) *"98% coords classification fix"* | **Deliberate for played, accidental for sim.** The fix was real and measured; it simply cannot run without animations, so **the sim arm never received it.** |
| 4 | `phase_resolution.py:5024` (`GOB_SIM_HCO_COORD_WRITE`) | **`4f856721a`** (2026-09-17) *"Write HCO player coords on the sim arm from the existing placement build"* | **Deliberate compensation** for #1. Works: it fully reconciles the pre-shot frame (§1). |
| 5 | `shared.py:3884` (`GOB_SIM_CRASH_APPLY`) | **`5febb76ad`** (2026-09-17) *"Apply post-shot crash destinations on the sim arm behind a flag"* | **Deliberate compensation** for #1, and the site of the residual gap — arithmetic where played has a render. |

**The narrative:** a January performance gate removed animation building for sims. The May–July UESS migration then built the HCO coordinate pipeline *on top of* that animation output and made the played arm's shot logic read rendered geometry. Two September commits added sim-side substitutes for the pre-shot frame (which works) and the post-shot frame (which approximates). The residual mismatch is the gap between the approximation and the render — and, more consequentially, the fact that `_uess_sync_emitted_shot_coords` never runs on the sim arm at all.

**The engine already knows.** `turn_manager.py:2299` logs `[SHOT-NO-SCHEMA] shot left turn_manager gate with no animation_steps … animations_len=0` — **654 times in 8 sim games**, and never with a non-zero `animations_len`. The condition has been observable all along.

## 5. Options — nothing implemented

### For b1 (shot classification + contest) — the one that matters most

| option | makes identical | cost | risk |
|---|---|---|---|
| **B1-A. Build animations for sims inside the emitter only.** Drop the `_is_full_simulation` early return in `skeleton_to_animations` *when called from the emitter*, keeping the packet unbuilt for the FE. | The emitter runs on both arms → `animation_steps` present on both → `_uess_sync_emitted_shot_coords` runs on both → **b1, b2 and b3 all collapse at once**, and `GOB_SIM_HCO_COORD_WRITE` / `GOB_SIM_CRASH_APPLY` become dead. | **Re-phases the RNG stream** — the animator draws (defender-placement shade), so every sim game changes. Full reference re-cut. Also gives back some of the January perf win; needs a timing measurement against the ~155s Railway budget. | Highest blast radius, but it removes the *class* of defect rather than another substitute. |
| **B1-B. Give `_uess_sync_emitted_shot_coords` a sim path** that syncs from the StepState grid it already has, instead of returning None. | The *shape* of the contest read (all ten players synced to one frame) on both arms; not the values. | Re-cut likely; no new draws if it reuses the existing stamp. | Cheaper, but it is a third substitute — it makes the arms *similar*, not identical, and the next audit finds the residue again. |
| **B1-C. Leave it; document the two `source` values** and make `ShotAttemptGeometry.source` a first-class reported field. | Nothing. | None. | Honest but concedes the goal that a simmed and a played game resolve the same way. |

**I would pick B1-A**, with B1-C as the immediate step while the perf question is answered. B1-A is the only option that makes the two arms read the same coordinates by construction rather than by approximation, and it retires three substitutes (#2, #4, #5 above) instead of adding a fourth. It is also the only one that fixes b2 and b3 for free.

### For b2 (rebound selection)

| option | makes identical | cost | risk |
|---|---|---|---|
| **B2-A. Subsumed by B1-A.** | Everything — selection reads the same coords. | as B1-A | — |
| **B2-B. Score rebounds from `arrival_coords` on both arms, always**, never from `player.coords`. | The distance term, regardless of which arm wrote the coords. | Re-cut; arrival is already ON, so this is narrowing a fallback, not a new model. | Leaves the *destination* derivation still arm-dependent, so it narrows the gap without closing it. |

**I would pick B2-A** — do not spend a separate change here; it is a symptom of b1's cause.

### For b3 (StepState / interception)

| option | makes identical | cost | risk |
|---|---|---|---|
| **B3-A. Subsumed by B1-A.** | The grid is the rendered one on both arms. | as B1-A | — |
| **B3-B. Make the played arm use `compute_defender_grid` too**, discarding the render-matching. | Both arms on one draw. | Re-cut; **reverses** a deliberate UESS fix (contest == render). | Wrong direction — it fixes parity by making the played arm worse. |

**B3-A.** B3-B is listed only to be rejected.

### For b4 (force-foul defender)

No separate option. It reads `player.coords` like everything else and follows whatever b1/b2 resolve to.

### What I would put to Jamie

One decision, not four: **is the January perf gate still worth its cost?** Everything else here is downstream of it. The measurement that decides it is sim wall-clock with the emitter's animator build restored — if it fits the budget, B1-A retires the whole class; if it does not, B1-B is the honest fallback and the report should say plainly that the arms will stay approximately equal rather than equal.

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A.

Every probe in this report is read-only (wrappers that snapshot `player.coords` and pass return values through) and every probed cell reproduces the current reference **40/40 on fingerprint and draws**. The offense/defense split is 10 games rather than 40; all other numbers are n=40.

## Not covered

- **No fix, no flag, no engine change.** Nothing was retuned and nothing was committed beyond this report.
- **Not measured:** the wall-clock cost of restoring the animator build for sims — the number B1-A turns on.
- **Not measured:** whether the ~25% classification / ~6% contest figures from `0050c5ebc` still hold at today's tree; they are quoted from that commit's own docstring, not re-derived here.
- **Not investigated:** the 2.1% of played HCO turns where the emitter returns None anyway (`SD=1`; 0% at `SD=0`), or why that rate is footing-dependent.
