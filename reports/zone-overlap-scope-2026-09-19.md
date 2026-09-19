# The zone overlap rung — audit

**The rule, in one sentence.** When an offensive player stands inside two defenders' zones, **whichever of those defenders has no *other* offensive player in his zone takes him** — and if both have someone else, a coin flip decides which one peels off; **distance to the player is never consulted anywhere in the rule.**

**The placement-vs-credit disagreement rate.** On the production footing, the defender **placed** on the ball handler is not the defender **credited** with defending him **87.0% of the time on the sim arm and 80.1% on played** (8.00 and 7.72 zone possessions a game). The dominant component is not a coin flip going the other way: in **58% of zone possessions the credit path finds no defender on the ball handler at all**, and falls through to a branch its own comment calls *"shouldn't happen"* — which credits the defender whose **position label** matches the ball handler's position label. That is the same family as `d190a7520`, and it is larger.

## Footing (rule 6e)

- **Branch `feature/animation-reward`, SHA `0636370f9`** (not develop). Read-only: nothing changed, `git diff HEAD` over tracked files empty, the only new file is this report.
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- **Probe integrity: 40/40 identical to `equiv_v3_reference_1fd08c080_zonesink.json` on all four cells** (sim/played × `SEED_DEFENSES=1`/`=0`), 0 probe errors. The one delegating proxy (`phase_resolution.random`) forwards every attribute, so draw order and count are untouched.
- **Q6 "before"** was measured by running the same probe in a temporary detached worktree at `29e6a6792`; the worktree has been removed.
- Probes: `ov/probe.py`, `ov/diag.py` (session scratchpad, uncommitted).

## Q1: What is the rule?

`_resolve_overlap_assignments` (`BackEnd/utils/shared_defense.py:1040-1194`) first partitions the overlapping defenders into those who have **other** offensive players in their zone and those who do not:

```python
    for def_pos in overlap_defenders:
        zone_coords = zone_boundaries[def_pos]
        other_players_in_zone = []
        for off_player in offensive_players:
            if off_player.get("player_id") == overlap_player_id:
                continue  # Skip the overlap player itself
            player_coords = off_player.get("coords")
            if player_coords and _point_in_zone(player_coords, zone_coords, False):
                other_players_in_zone.append(off_player)
        if other_players_in_zone:
            defenders_with_other_players[def_pos] = other_players_in_zone
        else:
            defenders_without_other_players.append(def_pos)
```

then branches on the counts:

| case | condition | outcome |
|---|---|---|
| **1** | exactly one defender has others, exactly one does not | the **free** defender takes the overlapped player; the busy one is released to his own zone |
| **2** | **no** defender has others | **both** take him — a double team |
| **3** | **all** overlapping defenders have others | sub-branches below |
| — | anything else | **nothing is returned at all** (see Q4) |

Case 3 splits three ways. If the ball handler is one of the *other* players in someone's zone, that defender keeps him and the other defender takes whichever of its candidates has made most progress toward the basket (`_distance_toward_basket`). If the ball handler **is** the overlapped player: with one busy defender, the busy one drops to his closest-to-basket other player (`_manhattan_distance_to_basket`) and the free one stays on the ball; with two busy defenders,

```python
                def_list = list(defenders_with_other_players.keys())
                chosen_defender = random.choice(def_list)
```

the chosen one peels off to his closest-to-basket other player and the other stays on the ball. If neither has others, both stay on the ball handler.

**What decides it, then:** the **workload** of each zone — whether a defender already has somebody — plus, in one sub-branch, a random pick. Distance from a defender to the overlapped player is **never** computed. Distance appears only when choosing *which other player* an already-busy defender falls back to, and it is distance **to the basket**, not to the defender. Dict iteration order matters in two places (Q4). Zone area is never consulted.

## Q2: The ball handler specifically

**How often is the ball handler the overlapped player** (`SEED_DEFENSES=1`, n=40):

| arm | BH overlapped, per game | share of all overlap resolutions | 2-3 | 3-2 | 1-3-1 |
|---|---|---|---|---|---|
| sim | **2,277.6 ±100.6** | 21.9% | 781.7 ±54.8 | 609.9 ±68.2 | 886.0 ±72.5 |
| played | **3,073.9 ±112.1** | 21.3% | 1,076.9 ±77.6 | 823.2 ±72.8 | 1,173.8 ±77.9 |

(These are per defender-step resolutions, not per possession — the overlap pass runs on every placement step.)

**Who takes him** (sim, share of ball-handler overlaps won):

| | PG | SG | SF | PF | C |
|---|---|---|---|---|---|
| **ball handler only** | **33.8%** | 24.8% | 17.9% | 13.3% | **10.1%** |
| all overlapped players | 16.9% | 18.4% | **26.3%** | 21.0% | 17.4% |

**Why the PG:** not because he is closest, but because he is most often the defender with an *empty* zone. The top-of-the-key zones contain fewer offensive players than the baseline zones, so the guard is the one with nothing else to do, and Case 1 hands him the ball. The centre is last for the mirror reason — his zone nearly always already contains somebody, so he is nearly always the one released.

**Is he the closest? Barely more often than chance.** Taking each defender's zone anchor (the pole of inaccessibility, which is where the sink actually puts him when his zone is empty) as the proxy for where he stands:

| | winner is also the nearest defender |
|---|---|
| all overlapped players | **62.6%** (180,043 / 287,735) |
| **ball handler only** | **59.8%** (51,972 / 86,976) |

Chance with two overlapping defenders is 50%. So the rule lands on the nearest defender **about ten points above a coin flip** — it is incidental, exactly as the code implies. Four times in ten, the man who picks up the ball handler is the further of the two.

## Q3: Does placement agree with credit?

**No, and the gap is large.** One comparison per zone possession that reaches the credit path (~9.2/game sim, ~9.7 played; 368 and 386 comparisons over 40 games):

| | sim | played |
|---|---|---|
| credited defender **was** among those placed on him | 48 (13.0%) | 77 (19.9%) |
| credited defender was **not** | 106 (28.8%) | 84 (21.8%) |
| **credit found no defender on the ball handler at all** | **214 (58.2%)** | **225 (58.3%)** |
| **disagreement rate** | **87.0%** (8.00/game) | **80.1%** (7.72/game) |
| credit list had ≥2 (the `:8747` coin flip) | 78 (21.2%) | 96 (24.9%) |
| by shell (sim) | 2-3 89%, 3-2 83%, 1-3-1 89% | 2-3 84%, 3-2 78%, 1-3-1 78% |

**What is actually happening — traced, not inferred.** It is *not* the boundary tables: `_zone_boundaries_for_spot` (`attack_drive_clearance.py:335`) dispatches to the **same** `_get_23/_get_32/_get_131_zone_boundaries` functions placement uses. *(This corrects `reports/zone-placement-scope-2026-09-18.md`, which described these as two parallel implementations — they are two dispatchers over one implementation, and they agree.)*

The disagreement comes from the attribution map itself. `_zone_ball_handler_guards` re-runs `assign_all_zone_defenders` from scratch on **live player coordinates at resolution time**, and reads `defender_to_offensive_player`, which is built by asking *"which offensive player is nearest this defender's assigned position?"*. That question frequently has an answer that is not the ball handler. In a single-game trace of the 11 real credit-side calls (the second, RNG-isolated 2-3 comparison call excluded):

- **3 of 11** had **all five defenders credited to the same offensive player** — and not because the offense was bunched (max pairwise spread was 37.5 grid units in one of them).
- **6 of 11** returned an empty guard list.

When the list is empty, `phase_resolution.py:8748-8752` takes this branch:

```python
                else:
                    # No defender assigned to guard ball handler (shouldn't happen, but fallback)
                    defender_pos = ball_handler_pos
```

**The "shouldn't happen" fallback fires on ~58% of zone possessions**, and it credits by **position label** — the ball handler is a PG, so the defending PG is blamed — which is a man-to-man assumption with no meaning in a zone. That is the single largest contributor to the 87%, and it is bigger than the `random.choice` at `:8747`, which only fires ~2.5 times a game.

**So: the sprite guarding the ball handler is usually not the player the box score blames.** Reported, not fixed.

## Q4: Determinism and bias

**It draws from `sim_rng`, and far more than anyone thought.** The `random.choice` inside Case 3 is a second RNG consumer, entirely separate from `phase_resolution.py:8747`:

| arm | resolver calls/game | **draws/game** | share of all draws | calls that drew |
|---|---|---|---|---|
| sim | 10,387 ±469 | **1,769.0 ±126.4** | **2.51%** of 70,464 | 885 |
| played | 14,401 ±486 | **2,457.5 ±144.6** | **3.01%** of 81,711 | 1,228 |
| both, `SEED_DEFENSES=0` | — | **0.0** | — | — |

That is roughly **700× the `:8747` draw** (~2.5/game), sitting inside placement where nobody was looking for it. It is also why any change to this rule re-phases the whole stream, hard.

**Dict iteration order matters in two places**, and the order is stable (Python dicts preserve literal insertion order, and `zone_boundaries` is built by iterating the table):

1. `bh_defender` is the **first** defender, in table order, whose other-players list contains the ball handler.
2. `other_defender = next(def_pos for def_pos in overlap_defenders if def_pos != bh_defender)` takes the **first** remaining defender in table order — which only matters when three zones overlap.

The order is **PG, SG, SF, PF, C in ten of the eleven tables**. `ZONE_23_UPPER_SHIFT` is **`SG, PG, SF, PF, C`** — a leftover from the mirror edit whose comment is still in the file. It is stable and deterministic, but it means that one shift table resolves its ties in a different order from every other table, for no stated reason. Reported, not changed.

**Which position wins** (sim, share of all overlaps won): SF 26.3%, PF 21.0%, SG 18.4%, C 17.4%, PG 16.9% — fairly flat overall, with the strong ball-handler skew toward the PG shown in Q2. By shell: 2-3 is the most skewed (SF 29.8% vs PG 12.1%), 3-2 the flattest (21–23% across four positions). **The skew is structural, not basketball:** it tracks how many offensive players each zone typically contains, because the rule's only input is whether a zone is otherwise occupied.

**A structural gap worth naming.** The branch conditions are exhaustive for **two** overlapping defenders but not for three:

| overlapping defenders | share | behaviour |
|---|---|---|
| 2 | 96.0% (9,968.6/game) | always matches a case |
| 3 | 4.0% (418.4/game) | matches only when 0 or 3 of them are busy |

When three zones contain the same player and one or two of them are busy, **no case matches and the resolver returns an empty dict** — every one of the three defenders falls through to the ladder as if no overlap had been detected. Measured: **256.6 ±22.6 resolutions a game return nothing at all (2.5% of all resolutions, ~61% of all three-way overlaps)**. It is silent — no log, no fallback.

## Q5: What happens to the defender who loses?

**He very often ends up on the sink.** When a defender loses an overlap, `assign_all_zone_defenders` filters the overlap player out of the list he is shown, so a zone whose only occupant was that player now reads as empty and he falls to rung (e).

Measured by recounting each rung-(e) defender-step against the **unfiltered** offensive-player list:

| arm | rung (e) from a **lost overlap** | genuinely vacant zone | share that is a lost overlap |
|---|---|---|---|
| sim | **2,010.9 ±115.1**/game | 2,754.5 ±174.6 | **42.2%** |
| played | **2,947.0 ±134.5**/game | 4,299.0 ±207.4 | **40.7%** |

**Four in ten of the empty-zone branch is not an empty zone.** It is a defender whose area *does* contain an offensive player, screened from him because a neighbour was given that player. That connects the two rungs directly and changes how both should be read:

- The sink is not only "where a defender waits when his area is vacant" — 40% of the time it is "where a defender goes after losing a coverage argument he was never told about".
- It also explains the Stage B result. The sink moved five defenders on ~18% of steps and nothing resolved; but nearly half of that 18% is a defender who *should arguably still be guarding someone*. No positioning model can fix that, because the input is wrong before the sink is reached.

## Q6: Did the ring repair change its composition?

Barely. Sim, `SEED_DEFENSES=1`, `29e6a6792` (pre-ring) → `0636370f9` (now):

| | before | after | Δ |
|---|---|---|---|
| overlap resolutions/game | 10,093.1 ±438.7 | 10,387.0 ±468.5 | +293.8 |
| BH overlapped/game | 2,176.3 ±97.5 | 2,277.6 ±100.6 | +101.3 |
| resolver draws/game | 1,731.5 ±95.9 | 1,769.0 ±126.4 | +37.4 |
| **returned-empty/game** | **194.1 ±17.1** | **256.6 ±22.6** | **+62.5 (+32%)** |
| double-team assignments/game | 661.5 ±53.4 | 599.2 ±42.3 | −62.3 |

Winner share moved ≤1.1 points for any position (PF +1.1, the largest). Court region of the overlapped player moved ≤0.8 points in any bucket. Zone-pair composition: `131_C+PF` −1.1, `23_PF+PG` +1.2, everything else under a point. Rung-(e) composition: lost-overlap 2,000.0 → 2,010.9, genuinely vacant 2,864.4 → 2,754.5.

**So the answer to the brief's premise is: same steps, and substantially the same players in the same places.** Doubling the double-covered *area* did not change who gets overlapped, because the added area is floor offensive players rarely stand on — the same reason the empty rung did not move. The one composition change worth noting is that **three-way overlaps became more common enough to push the silent no-assignment case up 32%**.

## Q7: Is the rule good basketball?

**Partly, and it is defensible as a first pass — but two specific things are not.**

What is right: "the defender who has nobody else takes the extra man" is real zone logic. It is how a zone avoids leaving a man completely unguarded, and it is the reason the ball handler most often ends up with a guard rather than a big.

What is not:

1. **Distance is never consulted.** A rule that lands on the nearest defender 62.6% of the time — ten points above a coin flip — will regularly have the far defender close out while the near one stands still. That is the most visible on-court defect, and it is the one Jamie will see.
2. **Three-way overlaps silently do nothing 61% of the time.** Not a design trade-off; a gap in the branch conditions. 256.6 resolutions a game.

The credit disagreement (Q3) is not this rule's fault — it lives in the attribution map and the positional-label fallback — but it is the higher-value defect, and it is cheaper to fix because it does not touch placement.

**Options, no winner picked.** All of them move **both arms** and re-phase the stream, exactly like the ring and sink passes; and because this rule consumes ~1,770 draws a game, the re-phasing is more violent than either.

| | what changes | blast radius | draw-neutral? |
|---|---|---|---|
| **A — tie-break the existing rule by distance** | keep the workload rule; when it is indifferent (Case 2, Case 3's coin flip, the three-way gap), pick the **nearest** defender instead of the first/random one | smallest. Removes the `random.choice`, so **−885 draws/game** on sim. Changes ~2.5% of resolutions outright and the BH sub-branch | **no** — removes draws |
| **B — close the three-way gap only** | add the missing branch conditions so 3+ overlaps always resolve | very small and surgical; touches 4.0% of resolutions. Does not address distance | **yes** in itself |
| **C — replace the rule with nearest-defender-with-capacity** | assign the overlapped player to the closest defender who is not already committed; workload becomes the tie-break instead of the rule | largest. Rewrites the primary input from occupancy to geometry; would change who guards the ball on ~40% of BH overlaps and would substantially change what feeds rung (e) | **no** — removes the draw, changes the stream everywhere |

Worth stating alongside them, because it cuts across all three: **any of these changes the 42% of rung (e) that is a lost overlap**, and therefore changes what the sink is being asked to do. The overlap rule and the sink are one system, not two, and tuning either in isolation will keep producing the null results we have seen twice now.

## Not covered

- **Nothing was changed and nothing was fixed.** No placement logic, constant or threshold; the sink, the rings and the ladder are untouched. No commits except this report.
- `_point_in_zone` / `_point_in_polygon`, the zone spot lists, the crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1, R2 and every balance number: untouched.
- **The credit-side attribution map itself** (`defender_to_offensive_player` in `assign_all_zone_defenders`) was traced only far enough to explain Q3. Why it collapses onto one offensive player in ~3 of 11 calls is **not** established, and it is the obvious next question.
- The `:8752` positional-label fallback is measured at ~58% of zone possessions but its **downstream effect on the box score** — which player actually receives the steal, foul or turnover — was not traced.
- The nearest-defender figures use each zone's **anchor** as a proxy for where the defender stands. That is exact when his zone is empty (the sink puts him there) and approximate otherwise.
- The Q6 "before" run covers sim `SEED_DEFENSES=1` only.
