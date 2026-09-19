# Crash destinations — where should a player actually go?

**Q1 first, because it decides how the principle has to be enforced: the bounce spot is already decided at two of the five authoring points, and they are the ones that matter.**

| branch | line | destinations/game (sim) | share | **bounce spot decided by then?** |
|---|---|---|---|---|
| **1 — MAKE** | 2057 / 2076 | 289.0 | 39.7% | **no** — a make has no bounce at all |
| **2 — shooting foul on a miss** | 2160 / 2172 | 54.8 | 7.5% | **no — 0.0%** |
| **3 — defensive foul on a miss** | 2264 / 2279 | **0.0** | 0% | **never fires** — 0 occurrences in 160 games |
| **4 — fast-break miss** | 2444 / 2454 | 1.2 | 0.2% | **YES — 100.0%** |
| **5 — HCO miss** | 2550 / 2565 | 383.6 | **52.6%** | **YES — 100.0%** |

`bounce_spot` is computed at `:2465` (`_compute_miss_bounce_spot`), **85 lines before** the HCO crash coordinates are authored at `:2550`. So on the branch that carries **53% of all crash destinations**, the ball's landing spot is sitting in scope — both as the local `bounce_spot` and already written into `result["ball_bounce_x"]` — at the moment each crasher is told where to run.

**The clairvoyance the principle forbids is not a hypothetical risk; it is one line of code away, on the majority branch.** Any model built here has to refuse that variable deliberately, and the refusal should be written down in the code rather than left implicit, because nothing in the current structure prevents it. Played and sim agree exactly on all of this.

## Footing (rule 6e)

- **Branch `feature/animation-reward`, SHA `146d826a7`.** Read-only: nothing changed, `git diff HEAD` over tracked files empty, the only new file is this report.
- **Measured with `GOB_FOUL_ON_BALL_WEIGHT=0`** — the only configuration that reproduces `equiv_v3_reference_1fd08c080_zonesink.json`. **A re-cut is still owed**; the default tree now has that flag on. **Probe integrity 40/40 on all four cells**, 0 probe errors.
- equiv-v3 worker, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- Probe: `cd/probe.py` (session scratchpad, uncommitted) — a delegating RNG proxy that observes the crash `randint` calls by argument range and caller line, forwarding every attribute so draw order and count are untouched.

## Q1 continued: what else is in scope at each authoring point

Read from the frames at each authoring line:

| datum | available? | notes |
|---|---|---|
| which team is shooting | **yes** | `is_home_team_shooting` — the only input actually used |
| crash-pool membership | **yes** | `offense_rebounders` / `defense_rebounders`, already filtered |
| the shooter's identity | **yes** | `shooter_id_excl`, used only to exclude him |
| shot origin coordinates | **yes** | the shooter's `coords` / resolved shot grid |
| shot type | **yes** | `outside` / `attack` / `inside`, resolved earlier in `resolve_shot` |
| each crasher's `Player` object | **yes** | `rebounder_player` — so **RB, ST, IQ, AG and height are all one attribute access away** |
| each crasher's current coordinates | **yes** | via that same object |
| `defense_playcall` / zone shell | **yes** | `game_state` |
| matchup map / who is boxing out whom | **partly** | the man matchup map is reachable; in a zone there is no matchup, and the placement stamp would be the equivalent |
| **the bounce spot** | **branches 4 and 5 only** | and it must not be read |

**Nothing that a better model needs is missing.** Every input the redesign would want — origin, type, the player, his attributes, his current position — is already in the frame. The current code reaches past all of it for a team-side flag.

**One dead branch, reported not fixed:** branch 3 (defensive foul on a miss, `:2264`/`:2279`) authored **zero** destinations across 160 games on both arms and both footings. Either it is unreachable or the condition guarding it never holds. It is one of the "five identical branches" and it is not in play.

## Q2: Where the ball goes, and where the players go

**The ball already responds to shot distance. The crashers do not.** That asymmetry is the whole finding.

**Bounce distance from the rim, by shot distance** (sim, `SEED_DEFENSES=1`, n=40; distances in grid units):

| shot distance | n | bounce-to-rim median | mean | p90 | max |
|---|---|---|---|---|---|
| 0–10 (rim) | 2,732 | 7.1 | 9.6 | 19.1 | 25.4 |
| 10–18 (short) | 5,635 | 7.1 | 10.0 | 22.8 | 32.3 |
| 18–26 (mid) | 6,203 | 10.0 | 11.1 | 16.1 | 40.9 |
| 26–40 (long) | 2,839 | 11.4 | 12.5 | 18.0 | 39.7 |
| 40+ (deep) | 143 | **18.4** | 19.8 | 38.6 | 38.7 |

The relationship is real and already built: `_bounce_variance_for_shot_distance` (`shared.py:1519`) bands the x-offset as `(2,6)` under 15 units, `(2,8)` to 20, `(3,14)` to 30, `(5,22)` to 45, then `(8, …)` beyond — and the y-variance from 6 to 14. **Long shots do produce long rebounds.** It is compressed at the short end (0–10 and 10–18 both land at 7.1), but the model exists.

**The authored destination is exactly the flat box it looks like:**

| | n | min | max | mean | uniform expectation |
|---|---|---|---|---|---|
| home-attacking x | 13,600 | 85 | 92 | **88.50** | 88.5 |
| away-attacking x | 15,546 | 8 | 15 | **11.50** | 11.5 |

**The mismatch — and it grows exactly where it should not** (|authored destination x − actual bounce x|, sim, misses only):

| shot distance | n | median | mean | p90 | max |
|---|---|---|---|---|---|
| 0–10 (rim) | 2,732 | 4.0 | 6.1 | 14.5 | 62.0 |
| 10–18 (short) | 5,635 | 4.0 | 6.6 | 19.0 | 65.0 |
| 18–26 (mid) | 6,203 | 5.0 | 6.9 | 13.0 | 58.0 |
| 26–40 (long) | 2,839 | 7.0 | 8.9 | 15.0 | 66.7 |
| 40+ (deep) | 143 | **13.0** | 17.9 | **43.5** | 49.5 |
| **all** | **17,552** | **5.0** | **7.1** | **15.8** | **66.7** |

By shot type: `outside` median 5.0 (p90 12.0), `attack` 5.0 (p90 **21.8**), `inside` 4.0 (p90 17.5).

**Read together: the ball's spread widens with shot distance and the crash box does not move at all, so the error more than triples from the rim to a deep shot.** On the shots where rebounding position matters most — long misses, where the ball comes off far from the rim — the crashers are sent to the same 7×10 box under the basket they are sent to on a layup.

**Volume:** **728.6 crash destinations a game (sim) / 710.0 (played)**, over 95.0 / 93.2 shots — **7.67 and 7.62 crashers per shot** across both pools. 438.8/game of those sit on shots that actually produce a bounce.

## Q3: Models (no winner picked)

Every model below is stated so it **never reads `bounce_spot`**. That is not a side note: on branches 4 and 5 the variable is in scope, so the refusal has to be explicit and, ideally, structural — pass the model only the inputs it is allowed to have, rather than letting it reach into the frame.

### Model A — shot-origin-driven

The destination is drawn from the *rebound distribution for that shot*, not from the outcome. Reuse the bands that already exist: take the shooter-to-rim distance, get `(x_min, x_max, y_variance)` from `_bounce_variance_for_shot_distance`, and sample the crash box from **the same distribution the ball will later be sampled from — independently**. Two draws from one distribution land in different places, which is exactly the intended "sometimes wrong".

- **Inputs:** shot origin, rim side. Nothing else.
- **On court:** a long three sends crashers out toward the elbows and the long-rebound arc; a layup keeps them tight. Crashers cluster where a miss from *that* shot usually goes, and are individually wrong about half the time.
- **Draw-neutral:** **yes** — it replaces two `randint` calls per crasher with two `randint` calls per crasher. The *ranges* change, not the count. The stream stays in phase; outcomes diverge because positions differ.
- **New tunables:** **none** if it reuses `_bounce_variance_for_shot_distance` as-is. One if a "crash tightness" multiplier is wanted to pull crashers slightly inside the ball's own spread (real crashers hedge toward the rim).
- **Computable before selection:** **yes** — depends only on the shot, which is fixed well before either point.

### Model B — role-and-position-driven

Where a player crashes depends on where he already is and what he is. Bigs to the block, guards to the elbows and the long-rebound band, the shooter's own crash behaviour separate again; each destination is an offset from the player's **current** position toward his role's rebounding area, capped by how far he could plausibly travel.

- **Inputs:** the crasher's current coords, his role (derivable from his lineup slot, or from RB/height without a new lookup), rim side.
- **On court:** the five crashers stop being interchangeable. A centre already on the block stays; a guard at the arc takes the long rebound. This is the model that most changes what a rebound *looks* like.
- **Draw-neutral:** **only if deterministic.** A pure offset model consumes **zero** draws, which *removes* ~1,457 draws a game (2 per destination × 728.6) and re-phases the stream hard. Adding a jitter to keep the draw count at two per crasher would keep it in phase.
- **New tunables:** **3–5** — a per-role target area and a travel cap, at minimum.
- **Computable before selection:** **yes**, though it reads live player coords, so it must be computed at a point where those coords are the shot-moment ones.

### Model C — contested (B plus a box-out term)

Model B, then modified by whoever is boxing him out: an ST-versus-ST comparison displaces the loser away from his target area.

- **Inputs:** everything B needs, plus the box-out pairing and both players' ST.
- **On court:** the only model where a strong rebounder visibly wins position rather than just winning a later dice roll.
- **Draw-neutral:** **no** — a contest resolution wants its own roll, and pairing is itself a decision.
- **New tunables:** **B's, plus 2–3** for the ST differential's effect.
- **Computable before selection:** **yes for man**, where the matchup map is available. **Problematic for zone** — there is no matchup, so pairing would have to come from the placement stamp, and `reports/zone-credit-diagnose-2026-09-19.md` showed that map is unreliable. **This model has a dependency on the zone work that A and B do not.**

**A note that applies to all three:** the current destinations are *uniform in a box*, so today every crasher's destination is independent of every other's. Models B and C introduce correlation between crashers (they no longer all aim at the same place). That is the intent, but it means the crash formation becomes a joint object, and clustering behaviour should be eyeballed before it is tuned.

## Q4: Should the five branches share one model?

They currently share one constant; they should not share one model.

| branch | share a model with? | reason |
|---|---|---|
| **5 — HCO miss** | the reference case | 52.6% of destinations; this is what "crashing the boards" means and it is where a shot-aware model pays |
| **4 — fast-break miss** | **differ** | a fast break has fewer bodies, they arrive from range, and the get-back players are a separate pool. Shot origin is known but the *approach* is what differs — crashers are still running. 0.2% of destinations, so it can inherit branch 5's model initially without much cost |
| **2 — shooting foul on a miss** | **differ, and it is arguably the odd one** | play is **dead**. Nobody is rebounding a whistled shot; these coordinates exist to place bodies for the free-throw setup that follows. A rebound-distribution model is the wrong shape here — a free-throw lane formation is the right one |
| **1 — MAKE** | **differ, emphatically** | 39.7% of all destinations, and **there is no rebound**. These players are not crashing; they are transitioning. Sending them to a rebound box under the basket after a made shot is a modelling error independent of everything else in this report |
| **3 — defensive foul on a miss** | n/a | never fires |

**The single biggest observation in Q4: 47.2% of all crash destinations (branches 1 and 2) are authored for situations where no rebound will occur.** Whatever model replaces the box, those two branches want a different answer entirely, and fixing them is independent of — and probably cheaper than — the rebound model.

## Q5: Ordering — can each model be computed before selection?

`select_rebounder_by_score` runs at `:2483`, before the HCO destinations at `:2550`/`:2565`. The reorder that would let selection read crash arrivals is **not in this pass** (it is scoped in `reports/rebound-crash-selection-scope-2026-09-17.md` and needs `uses_shot_arc` moved).

| model | computable before selection? | what it would need |
|---|---|---|
| **A — shot-origin** | **yes, trivially** | depends only on the shot, which is fixed long before `:2483`. It could be authored at any point after the shot resolves |
| **B — role-and-position** | **yes** | needs the crashers' shot-moment coordinates, which exist before `:2483` |
| **C — contested** | **yes for man; zone depends on the placement stamp** | and that stamp's currency at this point is unverified — the same open question flagged in the credit diagnosis |

**None of the three is blocked by the ordering, and none would need redesigning after the reorder.** That is the property the brief asked for and all three have it. A is the only one with no dependency on anything else queued.

## Q6: Arrival

**Arrival cannot be computed at the authoring points, and it does not need the full shared-kinematics work either — it needs one thing that is genuinely absent.**

The arithmetic is the same that made crash parity free: `distance / _ag_grid_per_game_sec(player, archetype)` gives travel time, compared against the step's duration. Of those, the **player and his AG are in scope** at authoring (the `Player` object is right there) and the **distance** is known once a destination is chosen. What is missing is the **step duration** — there is no `duration`, `time_elapsed` or rate reference anywhere between lines 2000 and 2600 of `shot_manager.py`. Step timing is decided later, in the emitters.

So: **arrival is computable, but not here.** Either the destination model returns an *intent* that the emitter resolves into an arrival when it knows the duration, or the authoring point gains access to the post-shot window (which `sim_post_shot_window_seconds` already computes for the crash-clock flag). The second is the smaller change and reuses work already landed. **Not built, per the brief.**

## Not covered

- **Nothing was changed.** No destination logic, no constants, no commits except this report; no tuning.
- `select_rebounder_by_score`, the `randint(1, 6)`, the selection order and `uses_shot_arc`: untouched and **not re-opened** — the dice stay, per Jamie's decision.
- `rebound_modifier`, `team_chemistry`, `fight`, `discipline`: previously reported as inert or absent, **not re-examined**.
- The zone work, the foul system, the crash flags, `animator.py:1213`, `_point_in_zone`, R1, R2: untouched.
- **Not established:** why branch 3 never fires. It is reported as dead, not diagnosed.
- **Not measured:** the y-axis of the mismatch. The probe captured the x draw (the one whose range identifies the branch) and not the paired `randint(20, 30)` y draw, so every distance above is on the x axis only. The y box is 11 units wide against a bounce y-variance that reaches ±14, so the y mismatch is real but unquantified here.
- **Not measured:** the crash-pool composition by player role — who actually ends up in `offense_rebounders` / `defense_rebounders`, which Model B would depend on.
- All numbers are from the pre-foul-fix configuration (`GOB_FOUL_ON_BALL_WEIGHT=0`); a reference re-cut is owed before the next landing pass.
