# Single authoritative placement draw — design and price

**Headline: most of this is already built, it is pointed the wrong way round, and the plan the repo
wrote for itself is still the right one.** `StepState` already exists, already holds a per-step
defender grid, and its own docstring already says *"Option A — share the emitter's one draw."* What is
missing is that **the emitter is the producer and the engine is the consumer**, when it needs to be the
other way round. That inversion is "commit 2", it never landed, and it is the whole job.

**Two of the three seams in the brief dissolve into that one change.** Seam C is not a separate stage
(§5). The zone collapse in seam B is a real defect but a different one from the posture omission, and
the two hit **disjoint populations** (§6).

Design only. **No code changed** — `git diff` at `0cd9c4c4f` is 0 lines, the only new file is this
report, `GOB_BOXOUT_CONTEST` is still `"0"`.

---

## 1. What already exists (archaeology)

`git log -S "That is what commit 2 fixes"` lands on one commit:

**`20d3cd7c5` — "Extract defender placement to engine/defender_placement.py (commit 1/2: PURE
RELOCATION)", 6 Sep 2026.** Its message states commit 2's scope verbatim:

> *"Commit 2 takes ownership (**single producer consumed by contest and render, stash deleted**);
> deep-copy removal is a separate third change gated on a mutation probe."*

And `defender_placement.py:13–17` repeats it with the mechanism named:

> *"Commit 2 makes this the single producer consumed by contest, emitter and renderer, and **deletes
> the `_hco_render_animations` stash that currently pipes the render's draw backwards into
> `StepState`**."*

**That stash is live today.** `skeleton_step_emitter.py:1636` sets it; `step_state.py:49` reads and
clears it. The direction of flow is: emitter draws → stash → `StepState.defense`. Commit 2 reverses it.

Nothing since `20d3cd7c5` advanced it. `defender_placement.py` has had four commits, all unrelated
(zone-sink IQ, sim-arm coord write, a raise-instead-of-invent fix, a vocabulary rename).

### The StepState workstream got most of the way there

`_documentation_master/projects/Z-Completed/StepState.md` records Stages 0–3 as **complete**, and
Stage 2 was exactly "make contest and render read one value". It shipped and it worked: *"live GAP =
0% man+zone"*. The governing law is already written down:

> **resolve once → freeze into StepState → project to the emitter → draw.**

**So why is there still a 20-unit p90?** Because Stage 2 hit a circular dependency and accepted an
approximation. `StepState.md:87`:

> *"`_hco_contest_final_skeleton` stamps `compute_defender_grid` on each step pre-contest (**the
> emit's exact stash isn't available yet — contest runs pre-emit + truncates the skeleton the emit
> draws → circular**; compute_defender_grid is the same code, **~2px RNG, immaterial vs the lane
> band**)."*

**That parenthesis is the defect.** The measurement in
`reports/placement-draw-divergence-2026-09-21.md` says the redraw is **p90 3.0 grid units with a tail
to 26**, not ~2px, and that it flips the shot contest **4.8 %** of the time between the two closest
consumers. The assumption that made the circularity acceptable is quantitatively false.

`phase_resolution.py:7285` carries the same mistake in one word — *"Coverage re-stamps the final
skeleton afterward **(idempotent)**"*. It is not idempotent in value: it is a fresh build with fresh
`sim_rng` draws, and 38 % of matched-step comparisons come back different.

**Verdict on commit 2's design: still right, and now better supported.** It was written as a
tidiness/ownership change; it is actually the correctness fix, and the number that justifies it did
not exist when it was written.

### There is already a precedent for the shape of the fix

Fast break does this today. `rendered_contest.rendered_positions_for_contest` →
`fb_rendered_defender_ends` re-authors the emitter's spread **RNG-isolated** (`getstate`/`setstate`)
and the contest reads that (`fb_drive_resolution.py:227` → `rendered_defender_end_coords`, consumed at
`covert_release_drive_integration.py:401` and `rim_runner_drive_integration.py:407`).

**That trick does not transfer to HCO, and the reason matters.** FB works because *"the contesting
defender in that spread is deterministic, so the isolated re-author reproduces exactly the defender
the emitter renders"* (`rendered_contest.py:41–45`). HCO placement is **not** deterministic — it draws
per call. An isolated re-author would not reproduce it. **HCO therefore cannot re-author; it must
freeze and share.**

## 2. The question I must not dodge: what "authoritative" means

**Not one position per turn.** Defenders move; a frozen per-turn coordinate would be wrong.

**One draw per MOMENT, where the moment is the skeleton step.** Every one of the four consumers is
already asking a per-step question — they just ask about different steps:

| consumer | the moment it asks about | is that moment a skeleton step? |
|---|---|---|
| interception / bat contest | **the step the pass occurs on** | yes — it reads `step["_step_state"]["defense"]` |
| shot contest | **the shoot step** (`_uess_sync_emitted_shot_coords` syncs every `player.coords` to the emitted shoot-step) | yes |
| drive contest | **drive completion** — attack-drive beats are appended as skeleton steps (`step["_attack_drive"]`, `_attack_drive_defender_override`) | yes |
| render → next turn | **the last rendered step** (`last_rendered_step`, `shared.py:4008`) | yes |

**All four moments are skeleton steps. None of them needs a new concept.** So "authoritative" means:

> For each `(turn, step index, defender)` there is **exactly one** coordinate, drawn **once**, and
> every consumer asking about that step reads it rather than recomputing it.

That object already exists and already has a home: **`step["_step_state"]["defense"]`**. The design
adds **no new store** — it makes the existing one the producer instead of a copy. That is what the "no
second source of truth" constraint requires, and a design that introduced a fifth map would fail it.

### The one genuinely hard property: the step list is not stable

The grid cannot simply be "computed once at turn start", because the skeleton **grows and shrinks
during resolution**:

- the walk-time contest **truncates** the skeleton the emit later draws (`StepState.md:87`);
- freelance beats are **appended after** the pre-walk stamp (`phase_resolution.py:8011–8016`);
- shot-clock recalibration **expands** it (`step_state.py` semantic note).

This is why the stamp runs 1–5 times. So the rule is not "compute once" but **write-once per step**:

> **Append-only freeze.** A step's defender grid is drawn the first time that step exists and is
> **never redrawn**. Later stamps compute only what is missing. Truncation drops steps; it never
> re-draws survivors.

That single rule is the whole correctness fix, and it is what makes the circularity harmless: the
contest and the emitter no longer need to agree by luck, because there is only one value.

## 3. The design

```
                    ┌──────────────────────────────────────┐
  resolution  ───▶  │  placement producer (write-once)     │
  (pre-emit)        │  defender_placement.build_all_...    │
                    │  writes step["_step_state"]["defense"]│
                    └──────────────┬───────────────────────┘
                                   │  one frozen grid per (step, defender)
        ┌──────────────┬───────────┼────────────────┬──────────────────┐
        ▼              ▼           ▼                ▼                  ▼
  interception   shot contest   drive contest    emitter          sync_lineup_
  /bat contest   (shoot step)   (drive-end step) (renders it)     coords_from_turn
  (pass step)                                                     (last step → next turn)
```

| | today | after |
|---|---|---|
| **who draws** | emitter (render), STAMP (1–5×), drive reconstruction — three independent producers | **one** producer, write-once per step |
| **`_hco_render_animations`** | emitter → StepState (**backwards**) | **deleted** |
| **contest** | reads STAMP's own build | reads the frozen grid |
| **shot contest** | re-emits already-built animations | unchanged — it already reads the emit, which now renders the frozen grid |
| **drive contest** | `attack_drive_clearance` rebuilds, no posture | reads the frozen grid for the drive-end step; **the reconstruction is deleted** |
| **render / next turn** | last rendered step of the emit | unchanged — the emit is now the frozen grid |
| **sim vs played** | sim takes `stamp-reuse-full-sim`, played takes `emitter-draw` (`step_state.py`) | **both read the same frozen grid** — strengthens B1-A, does not undo it |
| **direction** | rendered positions flow backwards into logic | logic freezes, emitter renders; **rendered positions feed no game logic** |

## 4. Where the brief's three seams end up

| seam | fate |
|---|---|
| **A** (SHOT vs STAMP, redraw tail) | **This is commit 2.** Fixed by the write-once rule. |
| **B** (drive, no posture) | Two *separate* defects — the posture omission and the zone collapse (§6). **Both are deleted along with the reconstruction** when the drive reads the frozen grid. A standalone posture fix is a stopgap, not a step toward A. |
| **C** (render 7–9 units off) | **Not a separate stage.** Its distance is *mostly the moment*, which is correct behaviour — the render is end-of-turn, the contests are mid-turn. Its *draw* component disappears the moment the emitter renders the frozen grid. **Nothing is left to do for C beyond confirming no consumer treats the end-of-turn position as a contest moment.** |

## 5. Staged plan

Order changed from the brief's, with reasons. Every stage: its own env-var kill switch, flag-off
reproduces `equiv_v3_reference_70f7dd021_b1a.json` **40/40 on all four cells**, re-cut is a double
re-baseline, no bundled commits.

### Stage 1 — B: pass posture to the drive reconstruction · `GOB_DRIVE_POSTURE`

| | |
|---|---|
| **changes** | `attack_drive_clearance.py:1253` — add `posture=` (read from `game.game_state["_hco_defense_posture"]`, as `defender_placement.py:1045` already does). One argument. |
| **population** | **Man drives only.** Posture only fires on man calls — measured: at SD=1 `posture_fired=False` has n=0 on zone turns. 848 of 1,166 drives (73 %). |
| **draws** | **ADDS draws** — `_apply_defender_posture` returns before its `random.uniform` when `posture` is None (`shared_defense.py:1969`). → stream re-phases → **re-cut required**. |
| **estimated movement** | Posture displacement is mean **3.25** units; DRIVE-vs-STAMP mean gap is **4.93**, so posture is most of it. DRIVE-vs-SHOT contest disagreement should fall from **16.0 %** toward the SHOT-vs-STAMP floor of ~5 %. At ~21 man drives/game that is **~2–3 drive contests per game changing contested status**. **This is an estimate from the measured flip rates, not a run.** |
| **verify** | Re-run the divergence probe; DRIVE-vs-STAMP mean should drop ~3 units and the flip rate roughly halve. |
| **Jamie checks** | On a man HCO drive, the help defenders should sit where the render draws them instead of a step further out. Watch a drive that ends in a pull-up: the nearest defender should be the one who looks nearest. |
| **risk** | Low blast radius, but it is outcome-moving and costs a full re-cut. **It is throwaway work** — Stage 2 deletes the line it edits. |

**Do this only as timing insurance.** If Stage 2 is going to land, skip it.

### Stage 2 — A: the write-once frozen grid ("commit 2") · `GOB_PLACEMENT_FREEZE`

| | |
|---|---|
| **changes** | `phase_resolution.py` `_stamp_contest_defender_grid` — write only where `_step_state["defense"]` is absent. `skeleton_step_emitter.py:1636` — delete the `_hco_render_animations` stash; render from the frozen grid. `step_state.py:49–95` — drop the stash branch and the `stamp-reuse-full-sim` / `compute_grid-fallback` split; one source. `attack_drive_clearance.py:1230–1272` — delete `defender_end_coords`' reconstruction, read the frozen grid. |
| **draws** | **Two sub-stages, deliberately split.** **2a** keeps the builds and changes only *which value is written/read* → **draw count unchanged**, so the change is attributable to value, not re-phasing. **2b** (Stage 3) removes the now-dead builds → fewer draws. Splitting them is the only way to tell "the contest read a different coordinate" from "the stream moved". |
| **estimated movement** | Shot-contest flips fall to ~0 between contest consumers (the 4.8 % SHOT-vs-STAMP disagreement is exactly what this removes). Interception geometry stabilises. **Estimate from flip rates.** |
| **verify** | The repo's own `🔬 STEPSTATE GAP` / REDRAW-SPREAD diagnostics (`step_state.py` docstring) should read **0** by construction, not by convergence. Re-run the divergence probe: SHOT-vs-STAMP p90 → 0. |
| **Jamie checks** | The defender who gets credited with a contest is the one on screen next to the shooter — on interceptions, pull-ups and dishes alike. This is the stage his eye can actually adjudicate. |
| **risk** | **Highest.** Step identity must survive truncation/expansion, or a frozen grid gets attached to the wrong step — worse than redrawing. Needs an explicit step-identity key, not a bare index. The `_hco_contest_final_skeleton` coverage pass is **load-bearing** (`StepState.md:91`: ≈18 % of interceptions) — it must keep running, just stop overwriting. |

### Stage 3 — A2: delete the redundant builds · `GOB_PLACEMENT_SINGLE_BUILD`

| | |
|---|---|
| **changes** | Skip the re-stamp build entirely when every step already carries a grid. |
| **draws** | **Removes draws** → re-phases → re-cut + double re-baseline. |
| **saving** | See §7 — estimated **~5 % of sim wall** at the production footing. |
| **risk** | Low once Stage 2 holds; it is pure dead-work removal. Gate on a probe that counts how often the final stamp finds nothing to do. |

### Stage 4 — Z: the zone-drive collapse (§6) · `GOB_DRIVE_ZONE_HELP_COORDS`

Fold into Stage 2 if it lands; ship standalone only if Stage 2 slips past 1 Nov.

### Stage C — none

Nothing to build. Confirm in the Stage 2 verification that no consumer reads the end-of-turn position
as a contest moment, and close it.

## 6. The zone collapse — bug, and a different bug from posture (§3 of the brief)

**`attack_drive_clearance.py:1002–1007`:**

```python
for _zpos in _OFFENSE_POSITIONS:
    if def_lineup.get(_zpos) and _zpos not in _help_race_coords:
        _help_race_coords[_zpos] = get_defender_coords(
            drive_end, is_away_offense, aggression, destination_location, drive_end,
            is_ball_handler=False, ball_spot=destination_location,
        )
```

**`_zpos` is the dictionary key and nothing else.** It does not appear in the call. Every unmatched
zone defender is therefore placed against the same point with the same arguments, and lands on the
same coordinate.

Measured, n=40 games per cell, sim arm (neutrality in §8):

| | zone drives (SD=1) | man drives (SD=1) | man drives (SD=0) |
|---|---|---|---|
| drives | 318 | 848 | 1,832 |
| **all five defenders on one coordinate** | **51.9 %** | **0.0 %** | **0.0 %** |
| ≥3 on one coordinate | 59.7 % | 0.0 % | 0.1 % |
| `_help_race_coords` collapsed to 1 distinct coord | 165 of 316 filled | 0 | 0 |
| guardians within radius (mean of 5) | 4.54 | 3.48 | 3.42 |
| `is_double_team` | 99.7 % | 98.7 % | 98.6 % |

**Is it correct-by-design?** Half. The stated intent (`:994–999`) is to *count* the rim protector as a
guardian on a cleared-paint drive — and as a **count**, one shared rim-help coordinate does the job.
It became a bug when the same dict started being read as a **position**: `defender_end_coords` is a
geometry source for the drive contest, and it is one of the four consumers measured at a 16 % contest
disagreement. **A value that was only ever a proximity flag escaped into a position consumer.**

**Does passing posture fix it? No.** The arguments are position-independent by construction; adding
`posture=` leaves them position-independent. **Separate defect, separate fix** — the unmatched
defender needs his own zone anchor, which the comment itself defers to "S4 zone posture".

**How much does it move outcomes today? Very little, for an uncomfortable reason.** `is_double_team`
is **~99 % on every drive, zone or man** — collapsed (100.0 %) or not (97.8 %). `shoot_prob` is
therefore 0.25 almost always. The guardian test is **saturated**: with `ATTACK_DRIVE_CONTEST_RADIUS =
CONTEST_EUCLIDEAN_RADIUS = 11`, a mean of **3.4 of 5** defenders sit inside the radius on man drives
with entirely distinct coordinates. **Flagged, not diagnosed — it is a tuning question, not this
scope**, but it means fixing the collapse should be justified on geometry correctness, not on an
expected swing in drive outcomes.

## 7. What gets cheaper (§4 of the brief)

The repo's own shipped profiler (`BackEnd/utils/sim_profiler.py`, `GOB_SIM_PROFILE=1`), 8 games per
cell, sim arm. **fp and draws 8/8 in both cells** — the profiler wraps for timing and draws nothing.

| bucket | SD=1 (**production footing**) | SD=0 (empty catalogue) |
|---|---|---|
| mean wall / game | 4.83 s | 4.31 s |
| **`anim.position_defenders` self** | **20.1 % of wall** (509 calls/game) | **2.0 %** (518 calls/game) |
| `anim.build_all_animations` incl | 7.96 s (509 calls) | 0.85 s (518 calls) |
| `emit.animation_steps` self | 8.6 % | 10.1 % |
| `core.hco` incl | 31 % | — |

**The single most important number here is the SD=1 / SD=0 split: same call count, ten times the
cost.** Defender placement is **20 % of sim CPU on the production footing** and **2 %** on the
harness's empty-catalogue footing. The expensive path is zone placement. **Any perf work measured at
SD=0 would have concluded placement was free.** (This is the extended-rule footing item, and it is the
sharpest example of it I have seen.)

**Estimated saving from Stage 3.** Per game: 509 placement builds, of which `skeleton_to_animations`
accounts for 138 and `compute_defender_grid` 107, leaving **~264** from `_stamp_contest_defender_grid`
— consistent with 2.14 stamps × 117 HCO turns ≈ 250. Collapsing 2.14 stamps to 1 removes ~53 % of
those, i.e. **~27 % of all placement builds ≈ 5.4 % of sim wall**.

**This is an estimate and it assumes build cost scales with build count.** It does not: re-stamps run
on longer skeletons, so the true saving is probably a little higher. **B1-A cost ~7 %; Stage 3 plausibly
gives most of it back.** Worth doing, but it is the *third* reason to do this work, not the first.

There is precedent that this class of change pays: `4da067d87` ("Sim perf: reuse the stamped defender
grid instead of rebuilding it") already harvested a rebuild that was *"~33 % of all defender-grid
builds in a sim"*. Same idea, one seam earlier.

## 8. Footing and neutrality

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
seeds 8000–8039, **sim arm**. **Catalogue state stated per table** — SD=1 seeds the six real defenses;
**SD=0 leaves it empty and every zone call plays man**, which is why SD=0 has zero zone drives.

| probe | cells | fp | draws |
|---|---|---|---|
| drive-branch (`sys.monitoring`, frame reads only) | sim SD=1, n=40 | **40/40** | **40/40** |
| " | sim SD=0, n=40 | **40/40** | **40/40** |
| perf (`sim_profiler`, timing wrappers) | sim SD=1, n=8 | **8/8** | **8/8** |
| " | sim SD=0, n=8 | **8/8** | **8/8** |

Both probes are read-only and consume no RNG. **0 errors across all 96 games.**

## 9. Timing

**Stage 1 (B) is doable before 1 Nov.** One argument, one flag, one re-cut.

**Stage 2 (A) should not be rushed at 1 Nov.** It is not large in lines, but it changes the ownership
of the object three subsystems read, and its one hard property — step identity across truncation and
expansion — is exactly the kind of thing that fails silently by attaching a frozen grid to the wrong
step. That failure mode is *worse than the defect it fixes*: today's redraw is noisy but always
plausible; a mis-keyed freeze is confidently wrong. **Recommendation: land Stage 1 before 1 Nov if it
is free to do so, and schedule Stage 2 for after, with the step-identity key designed first and
verified by a probe before any behaviour changes.**

**Recommendation against doing Stage 1 at all if Stage 2 is imminent** — it edits the line Stage 2
deletes, and it costs a full re-cut plus double re-baseline to ship a stopgap.

## 10. What I did not do

- **Built nothing.** No flags, no edits, nothing retuned.
- **Did not measure the FG%/outcome consequence of a contest flip.** The flip *rate* is measured; what a
  flipped contest does to a shot needs the contested/uncontested split, which I have not run. Every
  outcome estimate in §5 is labelled an estimate and derived from flip rates only.
- **Did not diagnose the ~99 % double-team saturation** (§6). Flagged; it is a tuning question.
- **Did not scope non-HCO placement consumers** (`quarter_start.py`, `turn_manager.py`, the FB/HCT
  animator paths). They call the same leaf and are out of this scope; FB already has its own
  rendered-contest façade.
- **Did not find the kickoff doc.** Still absent from the repo and the artifact list; design
  constraints taken from the brief's restatement.

## 11. Tunable constants

| constant | where | value | relevance |
|---|---|---|---|
| `CONTEST_EUCLIDEAN_RADIUS` | `constants/__init__.py:364` | `11` | the shot-contest binary the flip rates are measured against |
| `ATTACK_DRIVE_CONTEST_RADIUS` | `attack_drive_clearance.py:42` | `= CONTEST_EUCLIDEAN_RADIUS` (11) | the guardian test; **saturated at ~99 % double-team** (§6) |
| `HELP_SAG` | `shared_defense.py:1937` | `{normal 0.30, loose 0.55}` | the posture term Stage 1 restores to the drive |
| `HELP_SAG_JITTER` | `shared_defense.py:1938` | `0.10` | the per-call draw; sub-grid-unit in effect |
| `HELP_BASKET_SHADE` / `HELP_ANCHOR_FLOOR` | `shared_defense.py:1939–1940` | `0.20` / `0.30` | posture geometry |
| `ONBALL_POSTURE_DIST` | `shared_defense.py:1932` | `{tight 2.5, normal 3.5, loose 4.5}` | on-ball cushion |
| `POSTURE_DENY_DISTANCE` | `shared_defense.py:1934` | `2.0` | off-ball deny |
| `OPENNESS_LAG_MAX` / `OPENNESS_LAG_MARGIN_SCALE` | `defender_placement.py:48–49` | `0.8` / `110.0` | beaten-defender lag, inside the producer Stage 2 makes authoritative |
| `GOB_SIM_PROFILE` | `sim_profiler.py:32` | unset | `=1` reproduces §7 |
