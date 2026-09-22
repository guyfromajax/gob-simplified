# Correctness fix — live position-attribute bugs outside phase_resolution

Same root cause as the nine resolver sites: `Player` has no `position` (or `pos`) attribute and nothing in `BackEnd/` ever assigns one, so every `getattr(player, "position", None)` read returned `None` and whatever followed the `or` was taken unconditionally.

Eight sites converted, all behind the existing **`GOB_LINEUP_POSITION_LOOKUP` (default ON)**. The helper **moved** to `BackEnd/utils/lineup_position.py` rather than being duplicated; `phase_resolution` re-exports it under the private names its callers and tests already use, and a test asserts the two are the same object.

**This one moves numbers.** One seed per sim footing, all of it from a single site. Reference re-cut. **Nothing was retuned.**

## Branch currency

`develop` is **merged in** (`0d290469c`); `git rev-list --count HEAD..develop` is 0. The merge brought 21 commits of frontend, e2e and docs and **touched no file under `BackEnd/`**, so `equiv_v3_reference_456e2cdd9_reboundarrival.json` was still valid as the pre-change baseline. Two untracked `READY--*.md` files blocked the merge; both were byte-identical to develop's tracked copies, so they were removed and the merge brought them back.

## Stage 1 — what each site is and whether it matters

Read-only probe: `sys.monitoring` LINE + PY_START events scoped with `set_local_events` to each site's **code object** (module-attribute wrapping would miss `turn_manager`'s module-level imports). The callback reads `f_locals` and recomputes lookups; nothing is written back.

**RNG-neutrality verified, not assumed** — every probed run reproduced the reference: **fp 40/40 and draws 40/40 on both arms**, 0 errors, across three separate probe builds.

| # | site | function | value used for | owning lineup | fires/game (sim / played) | constant or `None` path |
|---|---|---|---|---|---|---|
| 1 | `models/game_manager.py:2436` | `get_box_score` | **box-score dict key** for bench players | offense/defense **bench** (see below) | **144.2 / 141.4** | `"BENCH"` — **100% correct**, 0 would differ |
| 2 | `engine/foul_announcement_language.py:130-131` | `defensive_foul_is_on_ball` | on-ball vs off-ball **announcement copy** | fouler → `def_lineup`; ball handler → `off_lineup` | **0 / 0** | always `False`; **unreachable on the shipped default** |
| 3 | `engine/skeleton_step_emitter.py:989` | `_bh_defender_pos` | which defender is tagged **`guard_ball`** in every emitted step | `def_lineup` | **0 / 94.8** | always `None` → **no defender ever tagged** |
| 4 | `engine/covert_release_step_emitter.py:1220` | `_build_step_back_step` | step-back / HCO-setup **destination slot** | `off_lineup` | **0 / 0** | dead last resort *after* an authoritative lookup |
| 5 | `utils/shared.py:2640` | `summarize_game_state` | `"pos"` field on the **player payload** (FE + persistence) | either team's `lineup` | **0 / 0** | always `None` — which is the correct answer |
| 6 | `models/turn_manager.py:2638` | `_execute_forced_shot` | which slot **shoots** in the forced-shot skeleton | `off_lineup` | **0.03 / 0.03** | `or "PG"` — **fired 1 of 1 (sim)** |
| 7 | `engine/eoq_perfection.py:145` | `build_run_out_clock_destinations` | which slot gets the **deep run-out spot** | `off_lineup` | **0.50 / 0.55** | `or "PG"` — **fired 30% (sim) / 41% (played)** |
| 8 | `engine/eoq_perfection.py:736` | `resolve_flss_shot_logic` | FLSS **shooter slot** | `off_lineup` | **4.80 / 1.60** | `or "PG"` — **0 fires in 256 calls** |

### Site 1 — are bench players legitimately possible? Yes; they are the only thing there

That loop runs **only** for players the lineup id-set above it already excluded, so every player reaching it is genuinely off the floor. The probe confirms it: **5,768 fires (sim) / 5,656 (played) across 40 games, and the identity lookup found a lineup slot in 0 of them.**

So `"BENCH"` was the *right* answer — but the code had never established that. It arrived there because two attribute reads that can never succeed both returned `None`. The collision handler then keys the first bench player `BENCH` and the rest `BENCH_<pid[:8]>`.

**Is it persisted? Yes.** `get_box_score()` feeds `game_summary_builder.build_game_summary()` — *"Create a clean dictionary for MongoDB insertion"* — called from `api.py:151`, so `BENCH` / `BENCH_xxxxxxxx` are written to Mongo as box-score keys. It also feeds `summarize_game_state` (`shared.py:2728`, `:2999`) and four `api.py` payloads.

**Nothing reads the key by value.** `potg.js:175` iterates `Object.values(teamPlayers)`; `pageLoadOverlay.js:478` iterates `Object.keys(box)` but uses the key only to index and the enumeration index only as a sort tiebreak. So the key is structural, not displayed.

### Site 2 — the announcement language is dead for a *different* reason than I reported

My previous report called this *"live, unlike these nine"*. **That was wrong, and the probe is unambiguous: `defensive_foul_is_on_ball` is entered 0 times per game on both arms.** The `GOB_FOUL_ON_BALL_WEIGHT` fix (`d91679bef`) already replaced it — `select_foul_player` now stamps `foul_is_on_ball` from the `matched_defender` it computed itself, and only the `GOB_FOUL_ON_BALL_WEIGHT=0` branch still calls this function. Its two `stamp_foul_announcement_text` callers are also inside the dead legacy FCP/HCT bodies.

**A separate, genuinely live defect surfaced while checking this.** The only reachable caller of `pick_defensive_foul_text` is the fast-break terminal announcement (`fb_terminal_announce.py:112`), and it reads `turn_result.get("foul_is_on_ball", True)`. Across 40 games (20 seeds × 2 arms) that produced **48 defensive foul announcements, and `turn_result` carried `foul_is_on_ball` in 0 of them.** Every fast-break defensive foul therefore announces with **on-ball language by default**, regardless of both flags. **Not fixed here** — it is a wiring gap, not a `.position` read, and it changes live announcement copy. Logged below.

### Site 3 — the one with real reach

`_bh_defender_pos` decides which defender carries `action: "guard_ball"` (everyone else gets `guard_offball`) in every emitted skeleton step. Returning `None` on every call means **no defender has ever been tagged `guard_ball` on this path.**

Measured at the call site (`skeleton_step_emitter.py:1641`), played arm, 40 games:

| | count | share |
|---|---|---|
| calls | **8,447** | |
| `roles["defender"]` is None — correctly unresolvable | 4,655 | 55.1% |
| **defender present and in `def_lineup`** | **3,792** | **44.9%** |
| defender present but not in `def_lineup` | 0 | 0% |

Slots: PG 1,315 · SF 764 · SG 693 · PF 575 · C 445. **Gameplay-neutral**: `_archetype_for_action` maps `guard_ball` and `guard_offball` to the same `cruise` archetype, so step timing is untouched; the label is consumed by `animateStep.js:525` only.

### Site 7 — the constant fires on a third to a half of calls

`last_ball_handler` is always a `Player` object (never `None`, never an id string). When the lookup fails it is because the player is **on the defense lineup after a possession flip** (2 of 20 sim, 8 of 22 played) or **on the bench after a substitution** (4 sim, 1 played). The old `or "PG"` handed the deep run-out spot to the offense's PG in all of those.

### The precedent the fix follows

Site 8 already had the right guard, with a comment explaining the bug it fixed:

```python
# last_ball_handler holds whoever LAST touched the ball. At an end-of-quarter
# possession flip (rebound / steal / inbound → new offense) it can still be the
# prior handler — now a DEFENDER. ... Only keep it if it is actually on the
# current offense (get_player_position is falsy otherwise).
if ball_handler is not None and not get_player_position(off_lineup, ball_handler):
    ball_handler = None
```

That guard is why site 8's `or "PG"` measured **0 fires in 256 calls** — it is already unreachable. **Sites 6 and 7 are the same situation without the guard**, so they now use it.

## Stage 2 — the fix, per site

`BackEnd/utils/lineup_position.py` — a leaf module (only `os` and `logging`, so the engine, the models and `utils.shared` can all import it without a cycle) holding `lineup_position_lookup_enabled()`, `lineup_slot()` (identity, `is` not `==`), `resolve_lineup_position()` and `warn_position_unresolved()`.

| # | what it does now | on `None` |
|---|---|---|
| 1 | `lineup_slot(team.lineup, player)`; `"BENCH"` is **derived** from the lookup coming back empty, and a lineup player reaching this branch now logs a warning (it would mean the id-set exclusion disagreed with the lineup) | `"BENCH"` — established, not guessed. **Key unchanged.** |
| 2 | takes `off_lineup` / `def_lineup` and compares the fouler's **defense** slot to the ball handler's **offense** slot | either unresolved → `False`, exactly as before |
| 3 | `lineup_slot(def_lineup, defender)`; caller passes the `def_lineup` already in scope | `None` → that step tags nobody `guard_ball`, the current behaviour |
| 4 | identity lookup **after** the authoritative `player_id` match, which cannot work when the ball handler has no id; the `.position` read is now kill-switch only | `None` → `return None`, the function's existing bail |
| 5 | `lineup_slot(team_obj.lineup, player_obj)` | `None` — which is the contract the sibling loop and `gameScene.js:1669` (*"Only include players in current lineup"*) already assume |
| 6 | an off-offense `last_ball_handler` is **dropped and re-picked from the lineup** (site 8's guard), so the lookup cannot miss | unreachable; kill switch restores `or "PG"` |
| 7 | same guard as 6 | unreachable; kill switch restores `or "PG"` |
| 8 | drops the dead `or "PG"`; the function's own guard already guarantees the lookup | unreachable; kill switch restores `or "PG"` |

**Lineup used per site — offense vs defense:** `off_lineup` at 4, 6, 7, 8 and for the ball handler at 2; `def_lineup` at 3 and for the fouler at 2; the **owning team's** lineup at 1 and 5 (whichever team the loop is on).

Sites 6 and 7 are the only ones where the neutral choice is "replace the player" rather than "return `None`". Returning `None` there would leave the forced shot with nobody shooting and the run-out with nobody deep; re-picking is the function's own documented fallback for the adjacent case, so it keeps the contract without inventing a position.

## Kill switch and outcomes

**`GOB_LINEUP_POSITION_LOOKUP=0` reproduces `equiv_v3_reference_456e2cdd9_reboundarrival.json`, verified at the committed tree:**

| cell | arm | fingerprint | draws | errors |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=1` | played | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | played | **40/40** | **40/40** | 0 |

**With the flag on:**

| cell | arm | matches the old reference | diverging seeds |
|---|---|---|---|
| `SEED_DEFENSES=1` | **played** | **40/40 byte-identical** | — |
| `SEED_DEFENSES=0` | **played** | **40/40 byte-identical** | — |
| `SEED_DEFENSES=1` | sim | 39/40 | **8002** |
| `SEED_DEFENSES=0` | sim | 39/40 | **8038** |

**The played arm being byte-identical is the load-bearing result.** Site 3 fires 3,792 times per 40 played games and site 7's constant fires 9 times, and neither moves a fingerprint or a draw — which is the direct evidence that site 3 is render-only and site 7's re-pick is draw-neutral.

**Both diverging seeds are site 6.** Seed 8002 is the *only* sim seed at `SEED_DEFENSES=1` where `_execute_forced_shot`'s constant fired, and it is exactly the seed that diverges. Once the shooter changes, the RNG stream re-phases and the rest of the game follows.

### Outcome table — reported, not adjusted

`SEED_DEFENSES=1`, n=40, like-for-like at this tree (flag off → flag on):

| metric | sim OFF | sim ON | Δ | played OFF | played ON | Δ |
|---|---|---|---|---|---|---|
| **pts/team** | 74.66 ±3.62 | 74.56 ±3.65 | −0.10 | 74.21 ±2.89 | 74.21 ±2.89 | **0.00** |
| **OREB share** | 29.41% ±1.78 | 29.61% ±1.73 | +0.20 | 31.56% ±1.89 | 31.56% ±1.89 | **0.00** |
| OREB | 18.77 ±1.53 | 18.95 ±1.48 | +0.18 | 20.57 ±1.57 | 20.57 ±1.57 | 0.00 |
| **fouls (both teams)** | 52.38 ±2.37 | 52.17 ±2.52 | −0.21 | unchanged | unchanged | **0.00** |
| **possessions** | 41.05 ±2.06 | 41.12 ±2.05 | +0.08 | 39.83 ±1.91 | 39.83 ±1.91 | **0.00** |
| FG% | 46.00 ±2.00 | 45.89 ±2.01 | −0.12 | 44.81 ±1.93 | 44.81 ±1.93 | 0.00 |
| **draws/game** | 69,274 ±1,223 | 69,337 ±1,195 | +63 | 81,705 ±1,039 | 81,705 ±1,039 | **0.00** |
| turns | 430.35 ±10.32 | 430.43 ±10.28 | +0.07 | 430.00 ±6.94 | 430.00 ±6.94 | 0.00 |
| **arm gap** (sim − played) | **+0.45** | → | **+0.35** | | | |

Every delta is a fraction of its own CI, and all of it comes from one seed: seed 8002's fouls went 38 → 30 and it is the only seed in the sim arm whose foul count changed at all. The played arm's numbers are identical by construction, not merely within CI.

### The new reference

**`_documentation_master/projects/references/equiv_v3_reference_ec4f5acfc_poslookup2.json`** — both arms, both footings, per-seed rows for 8000–8039, cut at the committed tree.

**The double re-baseline holds.** The worker was run a second full time at the same tree and the new reference reproduces itself:

| cell | arm | cut 1 vs cut 2 | file vs cut 2 |
|---|---|---|---|
| `SEED_DEFENSES=1` | sim | **40/40 fp + draws** | **40/40** |
| `SEED_DEFENSES=1` | played | **40/40** | **40/40** |
| `SEED_DEFENSES=0` | sim | **40/40** | **40/40** |
| `SEED_DEFENSES=0` | played | **40/40** | **40/40** |

`references/README.md` now lists it as current and moves `equiv_v3_reference_456e2cdd9_reboundarrival.json` to *Superseded* with `GOB_LINEUP_POSITION_LOOKUP=0` recorded as what reproduces it. **The old file is kept**, as are all the others.

One detail worth recording for the next cut: `arm_gap_sim_minus_played` is the **paired per-seed** difference, not the two CIs added in quadrature. I confirmed the method by recomputing the previous reference's own gap from its `per_seed` rows — `[0.45, 4.04]` and `[-0.17, 2.99]`, both exact.

## The 10 foul announcements

Under `GOB_FOUL_ON_BALL_WEIGHT=0` — the only configuration where site 2 is reachable — 20 seeds × 2 arms produced 48 defensive foul announcements, 35 of which the probe could pair with their `select_foul_player` call. `legacy` is the real `defensive_foul_is_on_ball` called the old way; `fixed` is the same function called with the two lineups.

- **legacy returned `True` 0 of 35.** Fixed returns `True` **6 of 35**, exactly matching "fouler's defense slot == ball handler's offense slot".
- **The text would change on 25 of 35 (71%).**

| # | game | fouler | bh | legacy | fixed | text today | text with the fix | |
|---|---|---|---|---|---|---|---|---|
| 1 | played 8000 | C | SF | False | False | Hand-Checking! | **Holding!** | changed |
| 2 | played 8002 | C | SG | False | False | Hand-Checking! | **Holding!** | changed |
| 3 | played 8002 | SG | PG | False | False | Arm Bar! | Arm Bar! | same |
| 4 | played 8003 | PF | PG | False | False | Arm Bar! | Arm Bar! | same |
| 5 | played 8004 | C | PG | False | False | Blocking Foul! | **Illegal Contact!** | changed |
| 6 | played 8004 | PG | PG | False | **True** | Blocking Foul! | Blocking Foul! | same |
| 7 | played 8005 | PF | PG | False | False | Holding! | **Arm Bar!** | changed |
| 8 | played 8008 | PG | SF | False | False | Arm Bar! | Arm Bar! | same |
| 9 | played 8009 | SG | PG | False | False | Arm Bar! | **Pushing!** | changed |
| 10 | played 8009 | PG | PG | False | **True** | Arm Bar! | Arm Bar! | same |

**None of this reaches a player today.** "Text today" is what the live fast-break path prints, and it prints it with `is_on_ball=True` because `turn_result` never carries `foul_is_on_ball` at all (0 of 48). The fixed column is what the copy *would* say once that value is wired through. `_weighted_pick` makes exactly one `announcement_rng.random()` call either way, and the probe saved and restored that state around the counterfactual, so the stream is untouched.

## Gates

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes, flag ON) | **PASS** — 1 distinct `(fp, draws)` in all four cells |
| FT-honour windowed | sim 99.8% / 99.8%; played 99.7% / 99.7% — unchanged |
| FT-honour strict | 95.9–96.6% — unchanged |
| **§8.1 coord-continuity corrections** | **0 across 160 games, all four cells** |
| `[POS LOOKUP]` unresolved warnings | **0 across 160 games** |
| errors across 320 reference games | **0** |

### Full suite, `--maxfail=1000`

| | flag ON | flag OFF |
|---|---|---|
| failed | **129** | **129** |
| passed | **2772** | **2772** |
| skipped / xfailed | 7 / 1 | 7 / 1 |

**Set diff empty in both directions, and the flag-on failing set is identical to the established 129.** Passes rise from 2,758 to 2,772: +14, the new tests in this pass (develop's merged `tests/test_franchise_context.py` collects 0).

**One test did break on the way, and it was a real incompatibility, not a flake.** `test_cr_empty_owner.py::test_step_back_omits_owner_key_when_fb_bh_id_missing` builds a stub with `player_id=None` **and** a `position` attribute, and depended on the dead `.position` last resort to rescue it — the `player_id` match cannot work without an id. Gating that branch broke it. The fix is not to allowlist the test: site 4 now does an **identity** lookup after the id match, which resolves that player correctly for the right reason. The test passes unmodified.

### Tests

`tests/test_lineup_position_lookup.py`, **79 passed** (was 65). New: one test per new site class (3, 2, 1, 4), the off-floor-ball-handler contract for 6 and 7, a guard that site 8's precondition still exists, and a check that `phase_resolution` re-exports the shared helper rather than holding a second copy.

**The AST source guard now walks all of `BackEnd/`,** not the three resolvers. It flags every `getattr(x, "position"/"pos")` and tolerates one **only** when it is lexically inside a `GOB_LINEUP_POSITION_LOOKUP=0` branch — it understands `if enabled(): … else:`, `if not enabled():`, `if <cond> and not enabled():`, and the `A if enabled() else B` conditional. The single explicit allowlist entry is **`engine/phase_resolution.py` :: `select_foul_player`**, the `GOB_FOUL_ON_BALL_WEIGHT=0` kill-switch path. Three poison tests: an unguarded read is reported, a correctly-guarded one is not, and an early-return kill switch written without an explicit `not` branch **is** reported (the guard requires the branch to be legible).

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A. OREB/foul aggregates come from the final box score via a harness-only wrapper; the reference itself is cut by the canonical worker.

## Reported, not fixed

1. **`foul_is_on_ball` never reaches the fast-break announcement.** `turn_result` carried it in **0 of 48** defensive foul announcements, so `pick_defensive_foul_text` always defaults to on-ball language on the only live path. Wiring it through would change live copy on ~71% of those announcements. **A decision, not a cleanup.**
2. **`defensive_foul_is_on_ball` and both `stamp_foul_announcement_text` call sites are unreachable on the shipped default** — the first needs `GOB_FOUL_ON_BALL_WEIGHT=0`, the other two sit in the dead legacy FCP/HCT bodies behind `USE_DYNAMIC_FCP` / `USE_DYNAMIC_HCT`. Fixed for correctness; it cannot change anything today.
3. **My previous report was wrong about site 2 being live.** I flagged it from a grep without tracing the caller. Corrected above.
4. **Box-score bench keys (`BENCH`, `BENCH_<pid[:8]>`) are persisted to Mongo** and nothing reads them by value. Whether they should instead carry a natural position is a product question — `Player` has only `position_ratings`, so deriving one is a design decision, not a correctness fix.

## Not covered

- **Not merged to develop.**
- **Nothing retuned.** No constant, weight, discount or slider was touched.
- **Not changed:** `USE_DYNAMIC_FCP` / `USE_DYNAMIC_HCT`, the offense-slot-indexes-`def_lineup` matchup convention, or the `randint(1,6)` / archetype / crash-tightness surfaces.
