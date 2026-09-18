# Zone defender placement: what it actually does

**Lead answer.** The three shells **are distinct on the floor and they do respond to the ball**: at the same ball location the mean formations sit 4–10 grid units apart per defender against a within-shell spread of ~3–4.5, each shell draws its own shape (2-3 = two up / three across, 3-2 = three up / two back, 1-3-1 = point, middle three, baseline), and on a wing-to-wing reversal defenders travel 9.3 (2-3), 10.5 (3-2) and 13.9 (1-3-1) grid units. The nearest thing to a collapse is 3-2 against 1-3-1 with the ball on the low wing (3.87, about the noise floor). **Placement reads no player attribute and no team attribute at all** — not IQ, not defensive efficiency, not discipline or chemistry. Its entire input set is the shell, the ball's spot, the five offensive players' coordinates, the aggression *slider call*, court orientation, and a `randint` jitter. Jamie's spec (IQ, team defensive efficiency) is not partially implemented; it is absent.

## Footing (rule 6e)

- **Tree:** `feature/animation-reward` at **`ed347a73c`** (read-only; nothing changed).
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, **`SEED_DEFENSES=1`** on every number below, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM.
- **Geometry tables (Q2, Q3):** sim arm, `_is_full_simulation` **True** at Pattern A. Placement is the same code on both arms (both run the same `_build_all_animations`), so the shapes are arm-independent.
- **Gate tables (Q6):** played arm, `_is_full_simulation` **False only inside the four gated Animator methods** — emitted steps exist only there.
- **Probe integrity:** sim rows **40/40** identical to `equiv_v3_sim_reference_9910cd6fd.json`; played rows **40/40** identical to `d9a4f1517`. Probe: `zn/zone_probe.py` in the session scratchpad, uncommitted.
- **Sample:** zone possessions sampled — **2-3: 711, 3-2: 758, 1-3-1: 790** (17,000+ defender-steps). Ample for every ball bucket except the corners, which are thinner (lower corner ≈ 33–41 possessions per shell); corner rows are marked and not extrapolated from.

## Q1: The placement path

**`BackEnd/engine/defender_placement.py:699 position_zone_defenders(game, offensive_animations, def_lineup, skeleton_steps, zone_assignments=None)`** positions all five defenders on a zone possession. It returns `(animations, zone_assignments)`.

Inputs it takes:
- `game` — used only for `game.offense_team.team_id` vs `away_team.team_id` (orientation), `game.defense_team.strategy_calls["aggression_call"]`, and `game.game_state["defense_playcall"]`.
- `offensive_animations` — the five offensive players' per-step coords (built earlier in the same pass).
- `def_lineup`, `skeleton_steps`.

**Where the shell enters, and whether it changes anything** (`:766-775`):

```python
defense_playcall = game.game_state.get("defense_playcall", "man")
zv = defense_zone_shell_variant(defense_playcall) or "23"
if zv == "32":    zone_boundaries = _get_32_zone_boundaries(ball_spot, is_away_offense)
elif zv == "131": zone_boundaries = _get_131_zone_boundaries(ball_spot, is_away_offense)
else:             zone_boundaries = _get_23_zone_boundaries(ball_spot, is_away_offense)
```

It resolves the catalogue id to `23` / `32` / `131` and picks a different boundary table per shell. **Yes, it changes the output** — measured in Q2. Anything unresolvable falls back to 2-3.

**Confirming the resolvers:**
- `assign_all_zone_defenders` (`BackEnd/utils/shared_defense.py:1070`) — **yes**, it is the per-step assigner, called once per defender per step at `:877`. It runs overlap detection (`_detect_overlapping_zones`, `_resolve_overlap_assignments`) then `assign_zone_defender_coords` per defender.
- `_zone_boundaries_for_spot` (`BackEnd/engine/attack_drive_clearance.py:335`) — **no, not in this path.** It is the *resolution-side* boundary resolver, used by drive clearance (`:873`) and the contest/credit reconstruction in `phase_resolution.py` (`:5484`, `:5975`, `:6994`, `:7033`). Placement uses the `_get_*_zone_boundaries` family instead. Two parallel implementations of "where is the zone", one for what is drawn and one for what some resolvers reason about.

Rest of the path: `_get_zone_coords` (spot names → coords, with the away flip), `_point_in_zone` (`shared_defense.py:557`, the hot leaf), `assign_zone_defender_coords` (`:720`, priority ladder), `get_defender_coords` → `calculate_defender_coords` (`:1858`, `:~1560+`, which carries the `randint` jitter), `_find_closest_spot_in_zone_to_point`, `_map_deep_location_to_zone_location`, plus `_attack_drive_defender_override` and `_subtle_defender_should_freeze` from `defender_placement`.

**The priority ladder inside `assign_zone_defender_coords`:** ball handler in my zone → guard him; else a deep-location mapping; else exactly one offensive player in my zone → guard him; else more than one → guard the one closest to the basket; else nobody → stand at the spot in my zone closest to the ball handler.

## Q2: Are the shells distinct on the floor?

Mean defender position by shell and ball location. Coordinates are normalised so the offense always attacks the rim at x=91; "upper" = high y. sd in parentheses.

**2-3**

| ball | PG | SG | SF | PF | C |
|---|---|---|---|---|---|
| upper wing (n=973) | 71.7,34.9 (2.5,3.2) | 68.8,25.8 (4.1,5.1) | 83.9,19.9 (3.9,4.6) | 86.2,33.5 (3.7,4.9) | 82.6,31.4 (3.3,2.3) |
| key / top (n=2392) | 71.2,28.9 | 70.8,20.5 | 85.1,18.4 | 85.4,31.5 | 81.2,26.0 |
| lower wing (n=894) | 73.5,27.3 | 73.0,14.3 | 84.6,15.5 | 83.7,28.9 | 82.8,21.3 |
| upper corner (n=426) | 85.6,36.2 | 74.2,31.3 | 84.1,25.8 | 84.8,32.3 | 85.9,28.1 |
| lower corner (n=166) | 74.3,23.8 | 83.9,8.3 | 83.9,6.8 | 87.9,28.4 | 85.5,25.8 |

**3-2**

| ball | PG | SG | SF | PF | C |
|---|---|---|---|---|---|
| upper wing (n=1096) | 69.0,31.5 | 74.6,36.2 | 75.1,20.0 | 85.9,31.7 | 83.7,20.6 |
| key / top (n=2517) | 68.9,25.2 | 75.2,32.2 | 74.0,16.8 | 85.7,29.4 | 85.7,20.4 |
| lower wing (n=994) | 69.2,20.9 | 76.5,27.5 | 74.6,13.0 | 83.5,27.2 | 84.4,17.7 |
| upper corner (n=421) | 74.0,32.6 | 80.2,35.6 | 79.8,19.0 | 85.1,34.3 | 83.4,27.0 |
| lower corner (n=205) | 74.1,18.6 | 74.5,22.1 | 78.6,10.7 | 87.3,27.7 | 84.3,16.7 |

**1-3-1**

| ball | PG | SG | SF | PF | C |
|---|---|---|---|---|---|
| upper wing (n=1076) | 71.5,34.0 | 72.1,34.6 | 80.1,21.3 | 80.1,30.6 | 86.9,33.6 |
| key / top (n=2757) | 69.2,25.0 | 74.6,34.4 | 75.1,14.4 | 77.1,24.1 | 84.2,28.5 |
| lower wing (n=987) | 72.9,15.5 | 77.7,27.6 | 73.2,13.9 | 80.2,20.7 | 87.1,17.0 |
| upper corner (n=441) | 74.2,32.0 | 83.4,40.7 | 83.4,24.8 | 82.1,30.2 | 88.9,31.8 |
| lower corner (n=197) | 74.8,16.7 | 80.3,25.4 | 82.5,8.6 | 85.7,25.1 | 86.7,21.0 |

**Separation between shells** — mean per-defender distance between two shells' formations at the same ball location, against the mean within-shell sd for scale:

| ball | 2-3 vs 3-2 | 2-3 vs 1-3-1 | 3-2 vs 1-3-1 | within-shell sd |
|---|---|---|---|---|
| upper wing | 7.50 | 5.16 | 6.18 | 3.87 |
| key / top | 7.47 | 8.92 | 4.75 | 4.50 |
| lower wing | 7.48 | 10.47 | **3.87** | 4.26 |
| upper corner | 6.46 | 6.96 | 5.18 | 2.83 |
| lower corner | 7.72 | 7.14 | 4.20 | 2.99 |

**Plainly: the shells do not collapse.** At the top of the key a 2-3 puts two defenders on the perimeter (PG 71,29 and SG 71,21) and three across the back (SF 85,18 / C 81,26 / PF 85,32); a 3-2 puts three up (PG 69,25 / SG 75,32 / SF 74,17) and two back (PF 86,29 / C 86,20); a 1-3-1 puts a point defender at 69,25, a middle three at 75,34 / 77,24 / 75,14 and the C on the baseline at 84,28. Those are the right shapes. The one weak pair is **3-2 vs 1-3-1 with the ball on the low wing (3.87, at the noise floor)** — with the ball there both shells rotate into a similar three-quarter tilt.

**Visuals:** `reports/zone-shells-visual-2026-09-18.md` — an ASCII half-court per shell per ball location (upper wing, key, lower wing, upper corner), defenders marked `1`=PG `2`=SG `3`=SF `4`=PF `5`=C, ball `o`, rim `#`.

## Q3: Does the shell respond to the ball?

**It shifts and re-forms; defenders do not hold fixed spots.** Mean per-defender travel between consecutive steps of the same possession:

| shell | ball holds its spot | ball changes spot | wing-to-wing reversal |
|---|---|---|---|
| 2-3 | 2.96 (n=12,785) | 6.66 (n=6,565) | **9.25** (n=1,210) |
| 3-2 | 2.73 (n=13,675) | 5.83 (n=7,275) | **10.54** (n=1,315) |
| 1-3-1 | 2.98 (n=14,235) | 7.91 (n=7,745) | **13.88** (n=1,210) |

Per defender on a reversal: 2-3 moves the C most (11.9) and the back line least (PF 6.3); 3-2 moves the top three most (PG 11.8, SG 12.7, SF 12.3); 1-3-1 moves the point defender furthest (PG 20.3) with the baseline defender at 11.2. The shells respond differently, which is what you would want.

The mechanism is table-driven, not continuous: each `_get_*_zone_boundaries` switches between a **normal** table and named **shift** tables, and the trigger differs per shell (2-3 shifts on wing/midCorner/corner; 3-2 shifts **only** on a true corner; 1-3-1 has four shift tables including separate corner variants). The ~2.9 grid of movement while the ball "holds its spot" is the `randint` jitter in `calculate_defender_coords` plus offensive players moving within the same named spot.

## Q4: Does placement read anything about the players?

**No player attribute. No team attribute.** `grep` for `attributes`, `team_attributes`, `IQ`, `defensive_efficiency`, `team_chemistry`, `discipline` across `BackEnd/engine/defender_placement.py` and `BackEnd/utils/shared_defense.py` returns **nothing**.

The complete input set for a zone defender's position is:
1. the shell (`defense_playcall` → `23` / `32` / `131`),
2. the ball's named spot (which shift table applies),
3. the five offensive players' coordinates for that step,
4. the ball handler's coordinates,
5. `aggression_call` — a **slider-derived call** (`normal` / etc.), not an attribute,
6. `is_away_offense` (orientation),
7. `random.randint` jitter inside `calculate_defender_coords`.

Two clarifications so this is not overstated: **AG** does reach the floor, but only through the *emitter's* movement rate (`_ag_grid_per_game_sec`) — how fast a defender covers the distance, never where he is sent. And the **posture** feature (`tight`/`normal`/`loose`) is passed only on the man path; the zone path calls `get_defender_coords` without it, so zone placement has no posture either.

So: the spec's IQ and team-defensive-efficiency read is **absent**, not partial.

## Q5: Zone vs man off-ball logic

Jamie is right that these are very different paths.

| | **zone** (`position_zone_defenders`, `:699-989`) | **man** (`position_standard_defenders`, `:990-1284`) |
|---|---|---|
| who a defender relates to | nobody fixed — a **zone polygon**; the guarded player is recomputed every step | a **fixed matchup** (`off_pos_to_guard`, from the matchup map) held all possession |
| per-step decision | `assign_all_zone_defenders` → overlap resolution, then the priority ladder (BH in zone → the one player in zone → the one closest to the basket → closest spot in zone to the BH) | `get_defender_coords(off_coords …)` relative to **his man**, with the ball handler's spot passed for off-ball shading |
| ball-handler defender | whoever's polygon contains the ball | whoever is matched to the ball handler |
| shape source | the shell's boundary table + shift tables | no shape: the formation is whatever the five matchups imply |
| beaten-defender modelling | **binary freeze only** — `_subtle_defender_should_freeze` on subtle beats (`:933`) | **graded lag** — `_defender_lag_fraction` (`:1219`) interpolates the defender toward his man by the read margin |
| pass steps | no special handling | holds the pre-pass coord so the rotation renders across the pass (`:1225-1235`) |
| posture (tight/loose) | not passed | passed into `get_defender_coords` |
| shared | `_attack_drive_defender_override` (drive beats), the same `calculate_defender_coords` jitter | same |

**Where they diverge most:** man has a per-defender read model (graded lag from `_defender_reads`, so a beaten defender opens a real gap); zone has only an on/off freeze and otherwise re-solves the polygon every step. Anything that depends on "this defender lost his man" exists on the man path only.

## Q6: The stationary-archetype oddity

**It is real, it is bigger than previously reported, and it is an offense-side effect — not defender placement.**

Gate steps (the emitted step's duration is set by the slowest **offensive** mover; played arm):

| archetype | zone: n / dist / T | man: n / dist / T | Δ dist | Δ clock |
|---|---|---|---|---|
| cruise | 9,086 / 11.04 / 1.21 | 10,068 / 10.10 / 1.08 | +0.94 | +2.28 s/game |
| **stationary** | **2,740 / 15.86 / 1.35** | **1,964 / 13.82 / 1.30** | **+2.04** | **+28.59 s/game** |
| shot_motion | 308 / 2.24 / 0.50 | 474 / 1.83 / 0.30 | +0.41 | +0.31 s/game |
| standard | 305 / 2.69 / 0.20 | 241 / 2.71 / 0.20 | −0.02 | +0.31 s/game |

Two things are going on:

1. **"stationary" does not mean stationary.** The archetype comes from the player's *action* on that step, and `stationary` is not in the rate table in `_ag_grid_per_game_sec` — it falls through to the **standard** rate (14 grid/game-s at AG 50). Meanwhile these gates are the **furthest-travelling** of any archetype: 15.9 grid units under zone. A player with no authored movement this step is being sent 16 units to his spot, and because he is the largest mover he sets the step's duration. Under zone these steps are **22% of all offense-gated steps (68.5/game)** against **15% (49.1/game)** under man, and they carry **92.4 s/game** of gated clock against 63.8.

2. **The extra distance is not the play mix and not the beat type.** Holding the playcall mix fixed at the man mix leaves a **+1.72** within-playcall effect (the mix explains only +0.32 of the +2.04). Within *identical step action sets* the gap is **+2.18** weighted — e.g. `[guard_offball, handle_ball, screen, stationary]` 20.06 zone vs 17.94 man (n=702/421), `[cut, guard_offball, handle_ball, stationary]` 17.88 vs 14.23.

**Where that leaves the cause:** defender placement cannot move an offensive player, so the driver is on the offense side of the zone branch. The candidate the trace points to is `build_motion_read_map` (`BackEnd/engine/motion_read_map.py:143-166`), which switches to `_zone_read_map(off_lineup, def_lineup, variant)` whenever the call is a zone. That map feeds `should_shoot` and `decide_step_action` in the per-step walk (`phase_resolution.py:7219`, `:7432`, `:7461`, `:7626`), so under zone the offense reaches different steps and fires different beats, and the player who ends up gating a step starts further from his next authored spot. **I did not isolate it further** — that needs a per-step trace of authored destinations against the read map, which is its own pass.

## Sample-size notes

Zone possessions sampled: 2-3 **711**, 3-2 **758**, 1-3-1 **790**. Every shell is well covered at the wings and the top (n ≥ 894 defender-steps per cell). The corner buckets are thinner — lower corner is 166 (2-3), 205 (3-2), 197 (1-3-1) defender-steps, roughly 33–41 possessions each — so those rows are reported as measured and nothing is extrapolated from them.

## Not covered

- No placement logic, constant or threshold was touched; no balance number; nothing landed but this report and its visual.
- The crash flags, `animator.py:1213`, the played arm, the `randint(1,6)`, the rebound path, R1 (Final Turn) and R2 (stopper) were not touched.
- The two parallel zone-boundary implementations (`_get_*_zone_boundaries` for placement vs `_zone_boundaries_for_spot` for resolution) were noted but not compared for agreement — worth a pass of its own.
- The Q6 mechanism is narrowed to the offense-side zone read path, not proven to it.
