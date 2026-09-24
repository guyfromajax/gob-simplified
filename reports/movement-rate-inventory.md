# Movement-rate derivation inventory and `_interrupted_coord` drift check

Read-only audit. No engine file changed; all instrumentation lived in a scratchpad file and
the working tree is clean.

**Footing (Rule 6e).** Branch `feature/animation-reward`, HEAD `f19a2e13a`, 0 behind
`develop`. Worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 /
traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process, **n=8
seeds 8000–8007, played arm, `SEED_DEFENSES=1` (production footing — defenses catalogue
seeded)**. Coverage only, not an outcomes measurement. **Probe proved RNG-neutral**: seed
8000 reproduced reference fp `a1d150579771387a` **and** draws `77689`
(`equiv_v3_reference_1f4af0ede_loosesag_nogate.json`). The probe rebound the wrapped names in
**25 modules** — the by-value import problem is real and a single module-attribute patch
would have under-counted.

---

## Q1 — Full inventory

### Corrections to the stated background

| stated | actual |
|---|---|
| "~31 sites that independently re-derive a player's movement rate" | **117 rate-derivation call sites.** 31 was the `_interrupted_coord` **consumer** count, which is a different thing. |
| 31 `_interrupted_coord` call sites | **32.** One is invisible to any name-based scan — see *injected callables* below. |
| FOUR definitions of `_interrupted_coord` | **Four definitions, but only TWO distinct arithmetic variants** (Q2). |
| canonical formula clamped to [0.5, 60] | Correct, but the **clamp is applied to the AG-scaled *standard* rate before the archetype multiplier**, not to the final rate. For AG 0–100 the standard rate spans 12.6–15.4, so **the clamp never binds in play**. Re-implementing it in the other order would be a silent behaviour change at extreme AG. |

### Rate producers — 117 call sites

There is exactly **one** implementation of the AG curve, `shared.py:744`:
`rate = STANDARD_GRID_PER_GAME_SEC * (0.90 + (ag/100)*0.2)`, then `max(0.5, min(rate, 60.0))`.
`_ag_grid_per_game_sec` (`animation_step_helpers.py:795`) multiplies by the archetype base.
**No site re-implements the curve arithmetic.**

| producer | call sites | notes |
|---|---|---|
| `_ag_grid_per_game_sec` | 83 | the raw archetype rate |
| `defender_movement_rate` | 27 | the AG-spread wrapper (flag OFF → identical to raw) |
| `ag_to_grid_per_game_sec` | 7 | AG-only, no archetype |

84 distinct sites were exercised in 8 games; **34 of the 117 static sites never fired**.

### Sites whose arithmetic DIFFERS from canonical

| # | file:line | expression | archetype | produces | defect |
|---|---|---|---|---|---|
| 1 | `covert_release_step_emitter.py:493` | `_ag_grid_per_game_sec(player, arch) if player else 12.0` | `arch` | ENDPOINT | **hardcoded 12.0 fallback** |
| 2 | `covert_release_step_emitter.py:1067` | same | `arch` | ENDPOINT | same |
| 3 | `covert_release_step_emitter.py:1307` | same, `"sprint"` | `sprint` | ENDPOINT | same |
| 4 | `covert_release_step_emitter.py:1718` | same | `arch` | ENDPOINT | same |

The canonical fallback for a missing player is `_ag_grid_per_game_sec(None, arch)`, which is
the archetype base (AG defaults to 50 → scale 1.0). **12.0 is wrong for every archetype:**

| archetype | canonical `None` rate | hardcoded | error |
|---|---|---|---|
| drift | 8.0 | 12.0 | **+4.0** |
| cruise | 13.0 | 12.0 | −1.0 |
| shot_motion / standard | 14.0 | 12.0 | −2.0 |
| sprint | 18.0 | 12.0 | **−6.0** |
| burst | 32.0 | 12.0 | **−20.0** |

Those same four sites also drop the `max(0.0, …)` guard (`max_traversal = rate * t`, no floor),
so a negative `t` would move the player *away* from the target instead of holding him at start.
**Latent, reported not fixed.** In 8 games no `covert_release` step was exercised.

No site derives a rate from distance/T instead of from the player.

### Three LOCAL COPIES of `stamp_tween_durations` that bypass the wrapper

| file:line | produces | rate expression |
|---|---|---|
| `rim_runner_step_emitter.py:297` `_stamp_tween_durations` | DURATION | `_ag_grid_per_game_sec` — **raw** |
| `fb_outlet_pass_step_emitter.py:87` `_stamp_tween_durations` | DURATION | `_ag_grid_per_game_sec` — **raw** |
| `covert_release_step_emitter.py:877` `_stamp_tween_durations` | DURATION | `_ag_grid_per_game_sec` — **raw** |

The **shared** `stamp_tween_durations` (`animation_step_helpers.py:1299`) goes through
`defender_movement_rate`. These three do not. In `rim_runner` and `fb_outlet_pass` the
*endpoints* **do** use the wrapper (7 and 2 references respectively), so **endpoint and
duration for the same player in the same step come from different derivations by
construction.** With the AG-spread flag OFF they agree; with it ON they diverge. This is a
structural cause of the divergence measured in `reports/ag-spread-callsites-2026-09-24.md`.
`covert_release` uses the raw function on both sides — self-consistent, but the AG spread can
never reach it.

### Injected callables — invisible to static analysis

`dynamic_hct.py:2629-2630` passes the functions in as arguments:

```python
ag_grid_fn=_ag_grid_per_game_sec,
interrupted_fn=_interrupted_coord,          # transition_bridge's = variant A
```

consumed at `fcp_offball_attack.py:360` (`rate = ag_grid_fn(off_lineup.get(pos), "sprint")`)
and `:364` (`interrupted_fn(...)`). **Offence-side.** The runtime trace caught this site;
the AST scan did not. It is the **32nd** `_interrupted_coord` call site.

### `_interrupted_coord` consumers — 32 sites, all canonical rates

Resolving each call's rate argument back to its assignment: **26 WRAPPER**
(`defender_movement_rate`), **5 RAW-canonical** (`_ag_grid_per_game_sec`, all offence:
`dynamic_hct.py:374, 1991, 2018, 2647`; `rim_runner_step_emitter.py:963`), **1 injected**
(`fcp_offball_attack.py:364`, offence). **No site passes a non-player constant.** All produce
**ENDPOINT only** — the duration is re-derived later by a stamper.

### Callers of the two combined helpers — ENDPOINT **and** DURATION together

Both helpers are **byte-identical to each other** (`_motion_end_toward_dest`
`animation_step_helpers.py:664`; `_interpolate_step_end` `skeleton_step_emitter.py:2936`).
Neither uses `defender_movement_rate` — **every caller passes a raw `_ag_grid_per_game_sec`
rate**, so the AG spread reaches none of them.

`_motion_end_toward_dest` — **6 callers**:

| file:line | enclosing | archetype | side |
|---|---|---|---|
| `after_steal_fast_break_step_emitter.py:137` | `_apply_drive_step_motion` | `archetypes.get(pid,"sprint")` | **MIXED** (loops all `start_coords`) |
| `fb_drive_resolution.py:163` | `_reachable_defender_ends` | `archetypes.get(pid,"sprint")` | **DEFENCE** (`def_lineup.get(pos)`) |
| `shot_micro_movements.py:1039` | `_carry_unfinished_movement` | `arch` (validated) | **MIXED** |
| `shot_micro_movements.py:1515` | `build_shot_micro_steps` | `"standard"` | **DEFENCE** (`defender_player`) |
| `animation_step_helpers.py:772` | `stamp_rebound_capture_player_motion` | `"sprint"` | **MIXED** (rebounder, either team) |
| `animation_step_helpers.py:781` | `stamp_rebound_capture_player_motion` | `attemptor_archetype` | **MIXED** |

`_interpolate_step_end` — **7 callers, all MIXED** (each resolves the player with
`_player_lookup_by_id(off_lineup, def_lineup, pid)`; several branch
`"cut" if pid in off_ids else "guard_offball"` in the same loop):

| file:line | enclosing | archetype | side |
|---|---|---|---|
| `skeleton_step_emitter.py:864` | `_build_step_end_coords_with_interrupts` | `archetype.get(pid,"standard")` | MIXED |
| `skeleton_step_emitter.py:1181` | `append_hco_bat_oob_trajectory` | `arch` (validated) | MIXED |
| `skeleton_step_emitter.py:1401` | `append_hco_loose_ball_trajectory` | `arch` (validated) | MIXED |
| `skeleton_step_emitter.py:1477` | `_scramble_leg` | `LOOSE_BALL_CONVERGE_ARCHETYPE` | MIXED |
| `skeleton_step_emitter.py:3021` | `_apply_overlay_motion_to_shoot_step` | `arch` | MIXED |
| `skeleton_step_emitter.py:3082` | `_build_ball_motion_sub_step` | `arch` | MIXED |
| `shared.py:3926` | `apply_sim_crash_destinations` | `archetype` | MIXED |

**No caller of either helper is offence-only.**

### The wider clamp family — 5 more implementations

| file:line | form | produces |
|---|---|---|
| `animation_step_helpers.py:871` `drift_or_hold_coord` | `f = min(1.0, travel/dist)` | ENDPOINT — **consumes RNG** (`r.random()`) |
| `covert_release_step_emitter.py:494 / 1068 / 1719` | `max_traversal = rate * t` (no `max(0.0,…)`) | ENDPOINT |
| `dynamic_hct.py:449` | `_interpolate(start, target, travel/distance)` | ENDPOINT |

Plus 5 duration helpers with **divergent degenerate fallbacks**:
`_traversal_seconds` (`covert_release:870`, `rim_runner:239` — identical, return `0.0` when
`rate<=0`), `_traverse_seconds` (`fb_drive_resolution:73` — returns **0.5**, floors at **0.1**),
`_travel_seconds` (`final_turn_pacing:93` — returns **0.05**, floors at **0.05**),
`travel_rate` (`rebound_arrival:65`).

### Secondary drift: seven `_euclid` implementations

11 definitions, **7 distinct**. Three use `(dx*dx+dy*dy)**0.5`; four use `math.hypot`, which
is not bit-identical. The two that matter here — `animation_step_helpers.py:658` and
`rim_runner_step_emitter.py:142` — are the **same** variant, so `_euclid` adds no drift to
`_interrupted_coord`.

---

## Q2 — `_interrupted_coord` drift

**Four definitions; TWO distinct arithmetic variants** (normalised AST body hash, docstrings
stripped).

| variant | definitions | body hash |
|---|---|---|
| **A** | `utils/transition_bridge.py:112`, `utils/reset_step_helper.py:99` | `038c4987a1c8` |
| **B** | `engine/rim_runner_step_emitter.py:245`, `engine/fb_outlet_pass_step_emitter.py:62` | `e0ce1d6f14b1` |

### Verdict: **DRIFTED — but only on degenerate inputs.** For every real input they are arithmetically identical.

The only differing lines:

```diff
+if start is None and target is None:
+    return {'x': 50.0, 'y': 25.0}          # ← B only: CENTRE COURT
+if start is None:
+    return {'x': float(target['x']), 'y': float(target['y'])}
+if target is None:
+    return {'x': float(start['x']), 'y': float(start['y'])}
 dist = _euclid(start, target)
 max_traversal = max(0.0, rate * t)
-if dist <= max_traversal or dist < 1e-09:      # ← A
+if dist <= max_traversal or dist == 0.0:       # ← B
     return {'x': float(target['x']), 'y': float(target['y'])}
```

### Worked numeric examples

| input | variant A | variant B | |
|---|---|---|---|
| start (0,0) → target (40,0), rate 14, t 1.0 | `{x: 14.0, y: 0.0}` | `{x: 14.0, y: 0.0}` | identical |
| start (0,0) → target (5,0), rate 14, t 1.0 | `{x: 5.0, y: 0.0}` | `{x: 5.0, y: 0.0}` | identical |
| **target is None** | `TypeError` | `{x: 10.0, y: 10.0}` | **DIFFER** |
| **start is None** | `TypeError` | `{x: 10.0, y: 10.0}` | **DIFFER** |
| **both None** | `TypeError` | **`{x: 50.0, y: 25.0}`** | **DIFFER** |
| dist 5e-10, rate 0, t 1.0 | `{x: 5e-10, y: 0.0}` | `{x: 0.0, y: 0.0}` | **DIFFER** by 5e-10 |

The `1e-9` vs `0.0` difference is real but bounded by **1e-9 grid units** — numerically
irrelevant (a sprite is ~5.25 grid units wide). **The material divergence is the None guard:
variant A raises, variant B silently returns a coordinate — and when both are None it teleports
the player to centre court (50,25).** Reported, not fixed.

### Which call sites and turn types reach each variant

| variant | call sites | turn types reached (8 games, calls) |
|---|---|---|
| **A** | 22 of 32 — all of `transition_bridge` (6), `reset_step_helper` (3), `dynamic_hct` (7), `dynamic_hct_shot` (1), `dynamic_hct_step_emitter` (3), `triangle_step_emitter` (2, via re-export), `fcp_offball_attack` (1, injected) | HCT 15,344 · FCP 14,273 · HCO 35,830 · FREE_THROW 3,912 · FAST_BREAK 2,509 — **71,868** |
| **B** | 10 — `rim_runner_step_emitter` (7), `fb_outlet_pass_step_emitter` (1), plus re-exports | FAST_BREAK 1,363 · HCO 687 · FCP 160 · HCT 120 · FREE_THROW 90 — **2,420** |

Both variants are live; B is concentrated in fast-break paths but reaches every turn type.

---

## Q3 — Turn-type coverage

**22,234 stamped steps over 8 games.** Note: `offensive_state` takes only five values — the
brief's *inbound/dead ball*, *zone shell*, *rebound scramble* and *end of period* are
**sub-phases inside these states**, not separate states, so they are reported by emitter below.

### Share of steps per turn type — the blast radius

| turn type | steps | share |
|---|---|---|
| HCO | 14,738 | **66.29%** |
| FREE_THROW | 2,037 | 9.16% |
| FCP | 1,871 | 8.42% |
| HCT | 1,841 | 8.28% |
| FAST_BREAK | 1,747 | 7.86% |

### Clamp variant by turn type (calls)

| turn | IC-A | IC-B | `_interpolate_step_end` | `_motion_end_toward_dest` |
|---|---|---|---|---|
| HCO | 35,830 | 687 | 74,136 | 3,944 |
| FREE_THROW | 3,912 | 90 | 12,111 | 636 |
| FCP | 14,273 | 160 | 7,106 | 525 |
| HCT | 15,344 | 120 | 7,527 | 644 |
| FAST_BREAK | 2,509 | 1,363 | 10,369 | 2,481 |

**Every turn type reaches all four.**

### Endpoint and duration from DIFFERENT derivations — the headline

| turn type | steps | COMBINED (same derivation) | **IC only → duration RE-DERIVED** | **MIXED in one step** | no clamp |
|---|---|---|---|---|---|
| HCO | 14,630 | 60.03% | **32.00%** | 2.06% | 5.92% |
| FREE_THROW | 2,019 | 71.47% | **27.54%** | 0.20% | 0.79% |
| FCP | 1,839 | 40.24% | **48.67%** | **7.07%** | 4.02% |
| HCT | 1,817 | 45.79% | **43.20%** | **8.09%** | 2.92% |
| FAST_BREAK | 1,580 | 75.51% | **23.29%** | 0.25% | 0.95% |
| **all** | **21,885** | **59.36%** | **33.29%** | **2.68%** | 4.68% |

> **33.29% of steps take the endpoint from `_interrupted_coord` and then have the duration
> re-derived independently by a stamper** — two separate rate look-ups for the same player in
> the same step. A further **2.68% mix both families within a single step**, so different
> players in one step get their endpoint and duration from different derivations. FCP and HCT
> are worst (48.67% / 43.20% IC-only, 7–8% mixed).

Steps whose endpoint and duration **cannot** diverge (the combined helpers): 59.36%.

### Turn types reaching a rate derivation NOT in the static Q1 list

**One:** `fcp_offball_attack.py:360` via the injected `ag_grid_fn`, **1,989 calls**, reached
from HCO/FCP. Invisible to name-based static analysis; only the runtime trace found it.

### Wrapper-bypassing local stampers, by turn type

349 steps (**1.57%** of all steps) are stamped by a local copy that never calls
`defender_movement_rate`:

| turn type | module | steps |
|---|---|---|
| HCO | `rim_runner_step_emitter` | 99 |
| FAST_BREAK | `rim_runner_step_emitter` | 94 |
| FAST_BREAK | `fb_outlet_pass_step_emitter` | 73 |
| FCP | `rim_runner_step_emitter` | 32 |
| HCT | `rim_runner_step_emitter` | 24 |
| FREE_THROW | `rim_runner_step_emitter` | 18 |
| HCO | `fb_outlet_pass_step_emitter` | 9 |

In `rim_runner` and `fb_outlet_pass` these are exactly the steps whose **endpoints** *do* use
the wrapper — the split is by construction, not by accident.

---

## Bottom line

**Unifying the rate and `_interrupted_coord` is NOT a pure refactor. It is a behaviour change
and needs a kill switch and a full equiv-v3 run.** Collapsing the four `_interrupted_coord`
definitions into one is *almost* free — the two variants are arithmetically identical on every
real input, and the only divergences are degenerate-input handling: a 1e-9-bounded coordinate
difference that no sprite could show, and a None guard where variant A raises and variant B
returns a coordinate (centre court when both are None). Picking either behaviour changes what
happens on those paths, so even that needs a flag, though a run would almost certainly come back
byte-identical. What makes it a genuine behaviour change is everything around it. Four sites in
`covert_release_step_emitter` substitute a hardcoded **12.0** when the player lookup fails, which
is wrong for every archetype — by −20.0 on `burst` and −6.0 on `sprint` — so routing them through
the canonical fallback moves real endpoints on the covert-release path. Three emitters
(`rim_runner`, `fb_outlet_pass`, `covert_release`) carry private copies of `stamp_tween_durations`
that call the raw `_ag_grid_per_game_sec` while their endpoints call `defender_movement_rate`;
unifying them pulls 349 steps per 8 games (1.57%, concentrated in FAST_BREAK and HCO) onto the
wrapper, which is inert today only because `GOB_DEFENDER_AG_SPREAD` is OFF and would become a
live difference the moment it is flipped. The three unguarded `max_traversal = rate * t` sites
gain a `max(0.0, …)` floor they do not have. And `fcp_offball_attack` reaches both the rate and
the clamp through injected callables, so any unification must thread that injection rather than
assume a direct import — a name-based refactor would silently miss it. Separately,
`drift_or_hold_coord` consumes RNG inside its clamp, so it can never be folded into a shared
pure helper without changing the draw stream. The paths that change are therefore: covert
release (fallback rate), rim runner and FB outlet pass (duration derivation), FCP off-ball
attack (injection), and any path that today relies on variant A raising on a None coordinate.
The sound sequence is to land the mechanical de-duplication behind a flag with the *existing*
arithmetic preserved exactly — including the 12.0 and the raw-rate stampers — prove 160/160,
and only then correct each defect one flag at a time.

**Latent bugs found, not fixed:** the hardcoded 12.0 fallback (×4), the missing `max(0.0, …)`
floor (×3), and the centre-court (50,25) return when both coordinates are None.
