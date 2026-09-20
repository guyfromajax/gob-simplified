# Fast-break foul announcements now follow `foul_is_on_ball`

`GOB_FB_FOUL_ON_BALL_TEXT`, **default ON**. The fast-break drive integrations now stamp the defender-role axis onto their foul turn results, so the terminal announcement picks role-correct copy instead of assuming on-ball.

**The headline is a negative one, and it is the point of the exercise:** on the shipped footing a fast-break defensive foul is committed by the on-ball defender **100% of the time (42 of 42)**, and that is structural, not incidental. So the copy does not change — but it is now *justified* by a stamped value rather than produced by a default that happened to be right. Game results are byte-identical on all four cells. **Nothing was retuned.**

## Branch currency

`develop` is **merged in** (`db7628f25`); `git rev-list --count HEAD..develop` is 0. This merge **did** touch `BackEnd/` — it adds a SQLite persistence adapter behind `GOB_PERSISTENCE=sqlite` (`BackEnd/persistence/sqlite*.py`, `env_config.py`, `store.py`). The equiv harness runs on `GOB_DB_MODE=mongomock`, so the engine path is untouched, and I verified that before measuring anything: at the merged tree, seed 8000 reproduces `equiv_v3_reference_ec4f5acfc_poslookup2.json` on all four cells, and the full kill-switch run below confirms it 40/40.

The merge also replaced `--maxfail` with `tests/known_failures.py`. That changes the suite baseline; see **Reconciliation** below.

## Step 1 — where the value is produced, and where it is dropped

**It is never produced.** `select_foul_player` is not called on the fast-break path at all, so there was nothing to drop — the producer was simply never wired in.

Traced with a read-only `sys.monitoring`-free wrapper probe (fp 40/40, draws 40/40 against the reference). All **52** fast-break foul/charge announcements in 40 games come from `resolve_fast_break_logic` through three drive integrations:

| entry | announcements |
|---|---|
| `phase_resolution.py:1628` → `after_steal_fast_break_step_emitter` | 25 |
| `phase_resolution.py:1716` → `covert_release_step_emitter` | 15 |
| `phase_resolution.py:1657` → `rim_runner_step_emitter` | 12 |

- `turn_result` carried `foul_is_on_ball` in **0 of 52**.
- 27 of 52 carry a `roles` dict; **it never carries the key either**, and its object identity matched the dict `select_foul_player` stamps only 5 times — those were the *previous* HCO turn's foul, a temporal coincidence, not a data path.

**The four sites that build the foul turn result and stop short** (line numbers pre-fix):

| file:line | function | sets | omitted |
|---|---|---|---|
| `engine/rim_runner_drive_integration.py:343` | `build_rim_runner_drive_turn_result` | `foul_team`, `foul_player_id` | `foul_is_on_ball` |
| `engine/covert_release_drive_integration.py:338` | `build_cr_drive_turn_result` | `foul_team`, `foul_player_id` | `foul_is_on_ball` |
| `engine/after_steal_drive_integration.py:916` | after-steal terminal branch | `foul_team`, `foul_player_id` | `foul_is_on_ball` |
| `engine/after_steal_drive_integration.py:513` | `_stamp_fb_shooting_foul_on_turn` | `foul_team`, `is_shooting_foul`, `foul_player_id` | `foul_is_on_ball` |

Downstream, `fb_terminal_announce.py:112` read `turn_result.get("foul_is_on_ball", True)` — so the missing key became **on-ball copy on every fast-break defensive foul**.

## Step 2 — the rule, and what "unknown" does

A fast break has no man matchup, so `defensive_foul_is_on_ball`'s lineup-slot comparison (the half-court rule) cannot answer here. What the fast break has instead is the **stopper**: the defender who cut the ball handler off at the meet point. He is the on-ball defender by construction.

```python
def fb_defensive_foul_is_on_ball(foul_player, stopper) -> Optional[bool]:
    if foul_player is None or stopper is None:
        return None          # nothing to compare against - genuinely unknown
    return foul_player is stopper
```

All three integrations pick the fouler as `credited or stopper`, so a foul by anyone else is a help foul → `False`.

**Per-case behaviour, stated:**

| case | value | why |
|---|---|---|
| fouler **is** the stopper | `True` | he is the man who met the ball handler |
| fouler is a help defender | `False` | he was not on the ball |
| **shooting foul** (`_stamp_fb_shooting_foul_on_turn`) | `True` | a shooting foul is committed on the player taking the shot, who has the ball — a definition, not a guess |
| offensive foul / charge | `True` | not consulted (`pick_offensive_foul_text` ignores the axis); stamped only so the key is always present, matching `select_foul_player`'s own convention |
| **no stopper** | **`None`** | **unknown — and NOT coerced to `True`** |

**What `None` picks.** `_role_is_eligible` now admits **only the `EITHER` rows** when the role is unknown — *Illegal Contact!*, *Holding!*, *Arm Bar!*, *Pushing!*. It drops both on-ball-only lines (*Blocking Foul!*, *Hand-Checking!*) **and** *Illegal Post Defense!*, because that line asserts a role context just as strongly as the on-ball ones do. Verified distinct in a lane context:

| `is_on_ball` | copy pool at `location: midLane` |
|---|---|
| `True` | Blocking Foul!, Holding!, Illegal Contact!, Arm Bar!, Pushing! |
| `False` | **Illegal Post Defense!**, Holding!, Illegal Contact!, Arm Bar!, Pushing! |
| **`None`** | **Holding!, Illegal Contact!, Arm Bar!, Pushing!** — neutral only |

**The kill switch leaves the key absent**, and the absent-key branch still falls back to `True`, so `GOB_FB_FOUL_ON_BALL_TEXT=0` is the exact legacy path. The reader distinguishes *absent* (legacy default) from *present-and-`None`* (neutral copy).

## Steps 3 and 4 — the kill switch, and no movement

Against `equiv_v3_reference_ec4f5acfc_poslookup2.json`, n=40, at the merged tree:

| cell | arm | flag | fingerprint | draws | errors |
|---|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | **off** / **on** | **40/40** / **40/40** | **40/40** / **40/40** | 0 |
| `SEED_DEFENSES=1` | played | **off** / **on** | **40/40** / **40/40** | **40/40** / **40/40** | 0 |
| `SEED_DEFENSES=0` | sim | **off** / **on** | **40/40** / **40/40** | **40/40** / **40/40** | 0 |
| `SEED_DEFENSES=0` | played | **off** / **on** | **40/40** / **40/40** | **40/40** / **40/40** | 0 |

**Byte-identical on both flag states, all four cells, fingerprint and draws.** Text only, as expected.

**That draws column matters more than I first assumed.** `fb_terminal_announce` imports `sim_rng as _random_module` — the **fast-break announcement draws from the sim stream**, not from `announcement_rng` the way `foul_announcement_language`'s own default does. So a pool change that altered the draw count would have re-phased the whole game. `_weighted_pick` consumes exactly one `rng.random()` regardless of how many rows survive role filtering, which is why the stream is untouched; there is a unit test pinning that.

## Step 5 — the announcements

**My first attempt at this measurement was contaminated and I threw it away.** The probe recomputed the counterfactual text by restoring `sim_rng`'s state around an extra `pick_defensive_foul_text` call. State restore is not enough: the equiv draw counter is not part of the state, so `draws` came back 15/40 even though `fp` was 40/40. Rebuilt to run the counterfactual on an **isolated `random.Random` seeded from the live state**, never calling `sim_rng`. The clean run is fp 40/40, draws 40/40.

**42 fast-break DEFENSIVE foul announcements across 40 games** (the other 10 of the 52 are offensive fouls and charges, which carry no role axis):

| | count | share |
|---|---|---|
| `turn_result` now carries `foul_is_on_ball` | **42** | **100%** |
| **ON-BALL** — the fouler *is* the stopper | **42** | **100%** |
| OFF-BALL — a help defender fouled | 0 | 0% |
| UNKNOWN — no stopper, neutral copy | 0 | 0% |
| **text changed vs the old always-on-ball default** | **0** | **0%** |

By play: after_steal 23, covert_release 12, rim_runner 7.

| # | game | role | play | before (always on-ball) | after | |
|---|---|---|---|---|---|---|
| 1 | played 8000 | True | rim_runner | Blocking Foul! | Blocking Foul! | same |
| 2 | played 8002 | True | covert_release | Hand-Checking! | Hand-Checking! | same |
| 3 | played 8002 | True | after_steal | Arm Bar! | Arm Bar! | same |
| 4 | played 8003 | True | rim_runner | Arm Bar! | Arm Bar! | same |
| 5 | played 8003 | True | covert_release | Illegal Contact! | Illegal Contact! | same |
| 6 | played 8005 | True | rim_runner | Blocking Foul! | Blocking Foul! | same |
| 7 | played 8006 | True | after_steal | Hand-Checking! | Hand-Checking! | same |
| 8 | played 8006 | True | after_steal | Pushing! | Pushing! | same |
| 9 | played 8007 | True | rim_runner | Holding! | Holding! | same |
| 10 | played 8007 | True | after_steal | Illegal Contact! | Illegal Contact! | same |

### Why 100%, and why that is structural rather than luck

The fouler is `credited or stopper`, and `credited` comes from `d8_credited_player_id`, set by `fb_drive_resolution.py:441`:

```python
d8_outcome, _ratio, credited = resolve_cutoff_contest(off_team, def_team, bh, stopper, exclude_steal=True)
```

That contest is a **1-on-1 between the ball handler and the stopper** — no other defender is a party to it — and `dynamic_hct._resolve_moment` returns `bh_defender` as the credited player for a `D_FOUL`. So `credited` is either the stopper or `None`, and `credited or stopper` is **always the stopper**.

**The off-ball and unknown branches are therefore unreachable on the fast break today.** That does not make the fix pointless: the announcement was previously correct by coincidence, with no data behind it, and the first help-defender foul or stopper-less meet would have printed *"Blocking Foul!"* at a player who was nowhere near the ball. It now prints what the data supports, and the `None` path is there so a future gap degrades to neutral copy rather than to a confident wrong answer.

## Step 6 — gates

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes, flag ON) | **PASS** — 1 distinct `(fp, draws)` in all four cells |
| FT-honour windowed | sim 99.8% / 99.8%; played 99.7% / 99.7% — unchanged |
| FT-honour strict | 95.9–96.6% — unchanged |
| **§8.1 coord-continuity corrections** | **0 across 160 games, all four cells** |
| errors across 320 games | **0** |
| `tests/test_fb_foul_on_ball_text.py` (new) | **20 passed** |

### Full suite

`pytest tests/ --ignore=tests/e2e` (no `--maxfail`; develop removed it):

| | flag ON | flag OFF |
|---|---|---|
| failed | **7** | **7** |
| passed | 2801 | 2801 |
| skipped | 20 | 20 |
| xfailed / xpassed | 110 / 2 | 110 / 2 |

**Set diff empty in both directions — this change causes none of the 7.**

## Reconciliation — `known_failures.py` (124) vs the 129 in `reports/test-triage-2026-09-19.md`

**Are the xfails strict? No.** `apply_known_failures` adds `pytest.mark.xfail(reason=..., strict=False)`, and the file's own comment says *"strict=False so XPASS is visible."* So a listed test that starts passing is reported as **XPASS** and is **visible in the summary, but does not fail the suite**. It will not break CI, and nobody is forced to prune the list. Two entries are in that state right now (below).

**Counts.** 111 `XFAIL` ids + 13 skips (5 `NODE_LOADER_SKIPS` + 6 `NODE_ESM_SKIPS` + 2 `MONGOMOCK_SKIPS`) = **124**, with no overlap between the sets. Against the **129** failing ids from the 2026-09-19 triage: **7 uncovered**, **2 covered that were not in the 129**.

The run reconciles exactly: 109 of the 111 xfails actually xfail, 2 XPASS, plus 1 pre-existing `@xfail` in the tests themselves = **110 xfailed + 2 xpassed**. 13 known-failure skips + 7 pre-existing skips = **20 skipped**.

### The 7 in the 129 that `known_failures.py` does not cover

**All 7 still fail in a full run** — they are exactly the 7 failures reported above. None was deleted; all 7 still exist.

| # | id | status | why it is missing from the list |
|---|---|---|---|
| 1 | `test_alpha_access.py::test_check_access_code_rate_limit` | **fails everywhere**, including in isolation | **Environmental**, and it belongs with the 13 skips: `slowapi` is not installed, so rate limiting never arms and the assertion `429 in statuses` sees `[200, 200, …]`. A genuine gap — this is the same class as the mongomock and node skips. |
| 2 | `test_sa1_within_step_pass.py::TestSeamGuard::test_poison_truncate_without_carry_fires` | **passes alone, fails in a full run** | **Order-dependent**, so a per-file triage pass sees it green. |
| 3 | `test_unrendered_and_ball_seam.py::TestUnrenderedTail::test_poison_appended_after_turn_stop_is_named` | same | same |
| 4 | `…::TestSyncReadsDrawable::test_sync_reads_the_drawn_step_not_the_ghost` | same | same |
| 5 | `…::TestSyncReadsDrawable::test_final_ball_helpers_read_drawable` | same | same |
| 6 | `…::TestBallOwnerSeam::test_item_47_poison_names_step_owners_and_family` | same | same |
| 7 | `…::TestPostStealPrematureAttach::test_poison_start_attached_stealer_is_named` | same | same |

Running ids 2–7 by themselves gives **27 passed**. In a full run they fail on assertions like:

```
assert "[UESS UNRENDERED] coord sync skipped undrawn tail FAST_BREAK/MAKE" in caplog.text
AssertionError: assert '...' in ''
```

`caplog.text` is **empty**, not wrong — something earlier in the suite reconfigures logging (a disable, a handler swap, or `propagate=False`) so the records never reach pytest's capture handler. That is why a per-file triage classifies them as passing and a full run does not. **Not fixed here.**

### The 2 covered that were not in the 129

| id | status |
|---|---|
| `test_simulate_quarter_endpoint.py::test_simulate_quarter_restores_team_stats_from_unified_teams` | **XPASS** |
| `test_simulate_quarter_endpoint.py::test_simulate_quarter_restores_team_stats_from_legacy_team_fields` | **XPASS** |

Both were passing in the 2026-09-19 run and still pass. They are xfailed with reason *"broken-harness: request must be a Starlette Request"* — a condition that does not hold on this machine. Because the marks are non-strict they surface as XPASS and cost nothing; they are simply two entries the list no longer needs.

**Net:** `known_failures.py` covers 122 of the 129 correctly, over-covers 2, and misses 7 — 1 environmental gap and 6 order-dependent tests that look green when their files are run alone.

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A.

## Reported, not fixed

1. **The 7 uncovered suite failures**, above. The `test_alpha_access` one is a one-line addition to `MONGOMOCK_SKIPS`-style environment gating; the other 6 need the logging-capture order dependence found first. Both belong to the test-hygiene backlog item in `bugs.md`, not to this pass.
2. **`fb_terminal_announce` draws from `sim_rng`.** Announcement copy is on the gameplay stream, so any future change to the copy tables or their weights re-phases every game after that point. `foul_announcement_language`'s own default is `announcement_rng`, so the two paths disagree about which stream announcements belong on. Worth aligning, but it is a reference-moving change.
3. **Offensive fast-break fouls can have no fouler.** `_resolve_moment` returns `None` as the credited player for `O_FOUL`, and the integrations set `foul_player = credited` on that branch, so `foul_player` is `None` and no `record_stat("F")` runs. Pre-existing, unrelated to the announcement axis, not touched.

## Not covered

- **Not merged to develop.**
- **Nothing retuned.** No copy table, weight, or slider was touched; the only table change is which rows are *eligible* when the role is unknown.
- **Not changed:** `defensive_foul_is_on_ball` (the half-court rule), `select_foul_player`, or the `GOB_FOUL_ON_BALL_WEIGHT` and `GOB_LINEUP_POSITION_LOOKUP` paths.
- **Reference unchanged** — `equiv_v3_reference_ec4f5acfc_poslookup2.json` still current, reproduced 40/40 on all four cells with the flag both on and off.
