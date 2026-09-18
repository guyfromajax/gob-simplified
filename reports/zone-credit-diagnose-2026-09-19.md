# The zone credit path — Stage 1 diagnosis

**Q1 first, because everything depends on it: it is attribution-only in practice — but not by design, and not with certainty on the last few percent.**

No consumer reads the credited defender's **attributes** by a path that survives. Personal fouls never read him (`d190a7520`'s claim re-confirmed in code and at runtime). Turnovers and steals read his **identity** only — who gets the STL, the momentum, and who becomes `last_stealer` — and the one branch where his mere presence could have flipped a dead ball into a steal (`phase_resolution.py:2938`) **never fires on HCO**: 204/204 (sim) and 207/207 (played) turnovers arrive with `from_resolution_system=True`. The only attribute reads in reach — `defender.attributes["ID"]` and height, for the block threshold at `shot_manager.py:1232-1246` — sit behind `_resolve_hco_shot_defenders`, which **re-derives its own defender from the placement assignment map on 92.9% of sim shots and 97.4% of played shots**. On the residual 3–7% I could not establish whether the surviving defender is the `:8747` one or the moment defender, because the only instrumentation that would have answered it perturbed the run and was removed. **So: a box-score correctness fix, with a small unresolved tail. Not an outcome change on the evidence I have.**

**And the headline for everything below:** the empty guard map is **never legitimate**. In **214/214 (sim) and 225/225 (played)** cases where the map lacks the ball handler, he was **inside at least one zone polygon** — 0.0% legitimate, 100% defect.

## Footing (rule 6e)

- **Branch `feature/animation-reward`, SHA `f5383f2ab`.** Read-only: nothing changed, `git diff HEAD` over tracked files empty, the only new file is this report.
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- **Probe integrity: 40/40 identical to `equiv_v3_reference_1fd08c080_zonesink.json` on all four cells**, 0 probe errors.
- **One probe was discarded mid-pass and is reported rather than buried.** To count how often the moment defender overrides the credit branch I swapped `game.game_state` for a recording `dict` subclass. That **broke run integrity** — other objects alias the original dict, so the swap diverged the game. It was removed, integrity re-verified, and the moment-override rate is therefore taken from `d190a7520`'s recorded measurement, not re-measured here.
- Probe: `cr/probe.py` (session scratchpad, uncommitted).

## Q1: Attribution only, or outcome-affecting?

Every consumer of `defender_pos` from the `:8747` branch. It becomes `defender`, then `roles["defender"]` (`phase_resolution.py:8770-8787`), and that is the only thing that escapes.

| consumer | what it reads | survives to it? | outcome-affecting? |
|---|---|---|---|
| **personal fouls** — `select_foul_player` (`:810`) | **nothing** — it uses `ball_handler.position` + a 60/40 weighted roll over `def_lineup` | never | **no** |
| **steal credit** — `resolve_turnover_logic` (`:2956`) | **identity**: `record_stat("STL")`, `add_momentum`, `game_state["last_stealer"]` | yes, unless the moment defender overrode it | box score + next-possession seed |
| **turnover type** — `:2938` `random.choice(["STEAL","DEAD BALL"])` | defender **presence** | **never fires on HCO** — 411/411 turnovers came `from_resolution_system=True` | **no** |
| **steal routing** — `choose_steal_next_offensive_state` | the stealer's **coords**, and only when `last_stealer_coords` is unset | rarely | position, not attributes |
| **stealer coords** — `:2969` `defender.coords = stealer_coords.copy()` | **identity**, then mutates that player's position | yes | writes a coordinate onto whoever is blamed |
| **reach-in flourish** — `:9070` `skeleton["steps"][-1]["reach_in_def_id"]` | identity | yes | render only |
| **block / foul roll** — `shot_manager.py:1232`, `:1243`, `:1246` | **`defender.attributes["ID"]`, height, `def_attrs`** | **only 2.6–7.1% of the time** | **would be, on that tail** |

**The insulating mechanism.** For HCO, `shot_manager.py:728-740` calls `_resolve_hco_shot_defenders`, which for a zone reads **`game.zone_defender_assignments_by_step`** — the map the *animator stamped during placement* — and overwrites `roles["defender"]` when it finds anything:

| arm | re-derive calls | **overrides** | no override |
|---|---|---|---|
| sim | 3,735 | **3,468 (92.9%)** | 267 (7.1%) |
| played | 3,666 | **3,572 (97.4%)** | 94 (2.6%) |

That is a significant fact for Q5 as well: **the shot path already solved this problem, by reading the placement map instead of recomputing.** The credit path is the one site that still recomputes.

**A separate bug found on the way, reported not fixed.** `select_foul_player`'s DEFENSE branch does:

```python
        ball_handler_pos = getattr(ball_handler, 'position', None)
        matched_defender = def_lineup.get(ball_handler_pos) if ball_handler_pos else None
```

`Player` has no `position` attribute — it defines `position_ratings` and nothing else (the same absence documented in `reports/boxscore-display-2026-09-18.md`). Measured: **`ball_handler.position` was missing on 316/316 (sim) and 315/315 (played) defensive foul selections — 100%.** So `matched_defender` is always `None`, every defender gets weight 0.1, and **the intended 60/40 "the on-ball defender usually commits it" split never happens — defensive fouls are uniform across all five defenders.** This is not the credit path's fault and is out of scope here, but it is the reason for the Q4 foul distances below.

## Q2: Why is the map empty 58% of the time?

| arm | credit calls | empty (fallback fires) | of those, **legitimate** (BH outside every zone) | **defect** (BH inside a zone) |
|---|---|---|---|---|
| sim | 368 | **214 (58.2%)** | **0 (0.0%)** | **214 (100%)** |
| played | 386 | **225 (58.3%)** | **0 (0.0%)** | **225 (100%)** |

Broken down by how many zones actually contained him: sim 106 in one zone, 105 in two, 3 in three or more; played 120 / 102 / 3.

**"No defender on the ball handler" is never legitimate in this data.** There is always at least one defender whose polygon contains him. The map simply does not say so.

**Why: the map answers a different question.** `defender_to_offensive_player` is not "whom is this defender assigned to" — it is built at `shared_defense.py:1220-1241` as *"which offensive player in `players_to_consider` is closest to this defender's assigned coordinate"*, except on the ball-handler-in-zone branch. Proximity to a defender's final position is not containment, so a defender standing in his zone with the ball handler in it can still be nearer to a different offensive player, and the ball handler drops out of the map entirely.

**It is also a fresh computation, not the placement the render used.** `_zone_ball_handler_guards` re-runs `assign_all_zone_defenders` on **live `player.coords` at resolution time**, while the render's assignments were computed per skeleton step and stamped into `game.zone_defender_assignments_by_step`. Two independent computations over different coordinates. (The *boundaries* are not the difference: `_zone_boundaries_for_spot` dispatches to the same `_get_*_zone_boundaries` functions placement uses — the correction already recorded in `reports/zone-overlap-scope-2026-09-19.md`.)

## Q3: Why does it collapse onto one player?

| arm | maps | **all five credited to one player** | distinct guarded players per map (1/2/3/4/5) |
|---|---|---|---|
| sim | 368 | **100 (27.2%)** | 100 / 174 / 76 / 17 / 1 |
| played | 386 | **128 (33.2%)** | 128 / 165 / 82 / 11 / 0 |

**The mechanism is the same "nearest offensive player" rule, plus the fact that the defenders are much more tightly packed than the offence.** Measured means: offensive spread **33.7 grid units** (sim) / 33.5 (played) — the offence is *not* bunched — against **defender spread 21.2 / 21.0**. Five defenders inside a ~21-unit envelope all asking "who is nearest me?" will frequently converge on the same answer, particularly the player sitting in the middle of the formation. In half of all maps the five defenders between them name only **one or two** distinct offensive players.

So the audit's open question resolves as: not a coordinate bug, not bunching — an attribution rule that was never a partition. Nothing constrains the map to be one-defender-per-player, or to cover the ball handler at all.

## Q4: What the fallback does downstream

Distance from the **blamed** defender to the ball handler, `SEED_DEFENSES=1`, n=40:

| arm | context | n | median | mean | p90 | max | **>20 units away** |
|---|---|---|---|---|---|---|---|
| sim | **foul** | 316 | 15.7 | 19.4 | 38.5 | **80.0** | **126 (39.9%)** |
| sim | turnover / steal | 204 | **4.5** | 7.3 | 16.2 | 22.2 | 4 (2.0%) |
| played | **foul** | 315 | 16.2 | 19.1 | 36.4 | **78.5** | **129 (41.0%)** |
| played | turnover / steal | 207 | **4.0** | 6.8 | 14.8 | 25.6 | 10 (4.8%) |

**This splits cleanly, and not the way the brief anticipated.**

- **Steals and turnovers — the things that actually read `roles["defender"]` — land on a defender who is genuinely near the ball.** Median 4.0–4.5 grid units; only 2–5% are beyond 20. Splitting by whether the positional fallback fired makes almost no difference (sim: fallback 4.2 vs real-guard 5.0). That is consistent with `d190a7520`'s finding that the **moment defender overrides the credit branch on 154 of 155 turns** — by the time a steal is credited, the defender has usually been replaced by one derived from the walk. **The `:8747` branch is mostly inert for the consumers that matter.**
- **Fouls are the ones landing on players who were nowhere near the play** — median ~16 units, 40% beyond 20, **max 80 units (the far end of the floor)**. But fouls do **not** come from this branch: they come from `select_foul_player`, whose 60/40 weighting is dead because `ball_handler.position` does not exist (Q1). The long distances are that bug's signature, not the credit path's.

**How much of a season's defensive stat line comes from this branch:** steals are the only per-player defensive stat it can set, at ~5.1 (sim) / ~5.2 (played) turnovers a game reaching `resolve_turnover_logic` on zone turns, of which the STEAL subset is smaller still — and the moment defender has usually replaced the credited defender first. **Blocks, fouls and rebounds are not attributed here at all.** Personal fouls, which looked like the largest exposure, are untouched by it.

## Q5: What is the right fix? (proposals only)

**Reframing, given Q1 and Q4:** this is a smaller and more contained problem than the 87% disagreement rate suggested. The disagreement is real, but it is mostly *invisible* because the consumers that matter have each independently routed around the broken map — the shot path by reading the placement stamp, the steal path via the moment defender. What remains is a genuinely wrong intermediate value with a small live tail, plus a `"shouldn't happen"` comment that is false 58% of the time.

| | what it does | draw-neutral? | notes |
|---|---|---|---|
| **A — read the placement map instead of recomputing** | have `_zone_ball_handler_guards` read `game.zone_defender_assignments_by_step` (the stamp the render used) rather than re-running `assign_all_zone_defenders` on live coords | **no** — it removes the entire recompute, including that call's internal overlap `random.choice` draws | **the most consistent option**: it makes credit read exactly what the sprite did, and it is what `_resolve_hco_shot_defenders` already does. **Open question that must be settled first:** the stamp accumulates across turns and is only conditionally present (`defender_placement.py:144`, `phase_resolution.py:5314` `hasattr` / `:5336` `delattr`), so whether it is populated *and current* at credit time is unverified. If it is stale, this trades a wrong answer for a differently wrong one |
| **B — fix the map so containment wins** | in `assign_all_zone_defenders`, credit a defender with the ball handler whenever the ball handler is inside his polygon, instead of only when he is the nearest offensive player | **no** — see the RNG note below | targeted at the actual defect (Q2: 100% of empty maps had him inside a zone). Also changes the map the *shot* path reads, so it is not contained to credit |
| **C — replace the fallback with nearest-defender-to-ball** | keep the map; when it comes back empty, credit the defender physically closest to the ball handler instead of the position-label match | **yes** if the distance computation is deterministic | smallest and most contained; it does not fix the map, it stops the wrong answer reaching the box score. Leaves Q3's collapse in place |
| **A or B + C** | repair the source and make the fallback sane | no | the fallback should be sane regardless, since it will still fire on any case the repair misses |

**The RNG consequence, quantified as the brief asks.** If the map returned every defender whose zone contains the ball handler, the currently-empty calls become populated, and `:8747`'s `random.choice` fires whenever there are two or more:

| arm | `:8747` today | after repair (projected) | change |
|---|---|---|---|
| sim | 78/368 calls = **1.95/game** | 186/368 = **4.65/game** | **2.4×** |
| played | 96/386 calls = **2.40/game** | 201/386 = **5.03/game** | **2.1×** |

Projected from the measured split of the empty cases (sim: 106 would yield one candidate, 108 two or more; played: 120 and 105). Roughly **+2.6 draws a game**, which is small in absolute terms but re-phases the stream from that point on — so both arms move and byte-equality will not hold, exactly as in the last three passes. Option C alone adds **no** draws and would be the only one that could plausibly stay stream-identical, though even that changes `roles["defender"]` and therefore the steal credit.

**Recommended sequencing, not a winner:** settle whether `zone_defender_assignments_by_step` is populated and current at credit time before choosing between A and B — that single fact decides which is correct rather than merely different. C is worth landing regardless, because a fallback whose comment says *"shouldn't happen"* while firing 58% of the time is a defect on its own terms.

## Not covered

- **Nothing was changed or fixed.** No commits except this report.
- `_resolve_overlap_assignments` and the overlap rule: untouched and **not pre-empted** — that is step 3, after the three-way gap.
- The sink, the rings, the ladder, `_point_in_zone` / `_point_in_polygon`, the crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1, R2 and every balance number: untouched.
- **Not established:** how often the moment defender overrides the `:8747` defender, on this tree. The measurement perturbed the run and was withdrawn; `d190a7520`'s 154/155 is quoted as prior evidence on an older tree and a different footing.
- **Not established:** on the 2.6–7.1% of shots where `_resolve_hco_shot_defenders` does not override, whether the defender whose attributes feed the block roll is the `:8747` one or the moment defender. This is the only path by which the credit branch could be outcome-affecting, and it is unresolved.
- **Not established:** whether `game.zone_defender_assignments_by_step` is populated and current at credit time. Option A depends entirely on it.
- The `select_foul_player` `ball_handler.position` bug is **reported, not fixed**, and its blast radius (uniform-random defensive fouls → foul-outs → substitutions) is not measured.
