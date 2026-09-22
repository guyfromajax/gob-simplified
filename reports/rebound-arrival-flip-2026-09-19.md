# Stage 2 — rebound from arrival: flipped

`GOB_REBOUND_FROM_ARRIVAL` is **ON by default** at `456e2cdd9`. `GOB_REBOUND_RACE` stays **OFF** and dormant, with its derived `REBOUND_RACE_TIME_SCALE = 0.5792` intact. **Nothing was retuned.**

**Read this first: the full test suite does not pass, and one of the failures is mine — from an earlier pass, not this flip.** `tests/test_zone_credit_shell.py::test_each_zone_credits_with_its_own_shell` was broken by **`cd2a08c3e` (the zone sink flip, 2026-09-18)**, and I missed it at the time because I ran only targeted tests. Details and the bisect are below. Everything the brief asked me to verify about *this* flip passed.

## Steps 1–2

- **Step 1 — no stale `index.lock`** in this worktree's git dir.
- **Step 2 — already done.** The Stage 1b race prototype was committed at the end of that pass as **`aa8921612`** ("Prototype the rebound RACE term behind GOB_REBOUND_RACE (default OFF)"), so the flip is already its own commit. Nothing was re-committed.

## Step 3–4 — the flip and its kill switch

**`456e2cdd9`** flips `GOB_REBOUND_FROM_ARRIVAL` from `"0"` to `"1"` and adds `tests/test_rebound_arrival_flags.py`, which guards the shipped defaults (arrival ON, race OFF, race still gated on arrival, and `REBOUND_RACE_TIME_SCALE` still the derived mean-neutral value).

**Kill switch verified — `GOB_REBOUND_FROM_ARRIVAL=0` reproduces `equiv_v3_reference_bf7ed1181_crashmodela.json`:**

| arm | `SEED_DEFENSES=1` | `SEED_DEFENSES=0` |
|---|---|---|
| sim (`_is_full_simulation` True) | **40/40 byte-identical** | **40/40** |
| played (False only inside the four gated Animator methods) | **40/40** | **40/40** |

## Step 5 — the new reference, double re-baselined

**`_documentation_master/projects/references/equiv_v3_reference_456e2cdd9_reboundarrival.json`** — both arms, both footings, per-seed rows for 8000–8039.

**The double re-baseline holds.** The worker was run a second full time at the same tree and the new reference reproduces itself:

| arm | `SEED_DEFENSES=1` | `SEED_DEFENSES=0` |
|---|---|---|
| sim | **40/40 byte-identical across two independent cuts** | **40/40** |
| played | **40/40** | **40/40** |

**Supersession is now recorded somewhere durable.** The references folder had **no index at all** — supersession lived only inside each JSON's `note` field and in scattered reports. I added **`_documentation_master/projects/references/README.md`**: the current reference, every superseded one with the flag setting that still reproduces it, the shared footing, and the three-step rule for cutting the next one. `equiv_v3_reference_bf7ed1181_crashmodela.json` is marked superseded and **kept**, as are all the others.

## Step 6 — gates

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes) | **PASS** — both arms, both footings |
| FT-honour windowed | sim 99.8% / 99.8%; played 99.7% / 99.7% |
| FT-honour strict | 96.0–96.6% |
| **§8.1 coord-continuity corrections** | **0 in every cell** (≈180–199 guard calls/game) |
| errors across 320 reference games | **0** |
| `tests/test_crash_destination.py` (signature guard + AST scan, both poisoned) | **14 passed, 1 skipped** |
| `tests/test_zone_ring_geometry.py` | **56 passed** |
| `tests/test_rebound_arrival_flags.py` (new) | **5 passed** |

### The suite, honestly

`pytest tests/ --ignore=tests/e2e` reports **130 failed, 2692 passed, 7 skipped, 1 xfailed**. (The repo's pytest config caps at 2 failures, so a plain run stops early and hides the total — `--maxfail=1000` is needed to see it.)

**This flip causes none of them.** Run with the kill switch, the count is **identical, 130 / 2692**.

**But one of the 130 is mine, from the zone sink pass.** `test_zone_credit_shell.py::test_each_zone_credits_with_its_own_shell` bisects cleanly:

| tree | result |
|---|---|
| `3ace4a84f` (merged, pre-rings) | 6 passed |
| `5c4a2a645` (14 rings repaired) | 6 passed |
| `a431a5014` (Option B corner centres) | 6 passed |
| `b288e4346` (basketSpot into the 2-3 centre) | 6 passed |
| `c1958f8f6` (ring geometry guard) | 6 passed |
| **`cd2a08c3e` (zone sink ON)** | **1 failed** |

And at HEAD, `GOB_ZONE_SINK=0` → **6 passed**; sink on → **1 failed**. So it is the sink, not the ring repair.

The mechanism is the one documented in `reports/zone-credit-diagnose-2026-09-19.md`: the credit map asks *"which offensive player is nearest this defender's assigned coordinate"*, so moving the defenders moves the credited defender. The 2-3 shell now credits `['SG', 'C']` where the test pins the pre-sink answer. **The test is asserting the old geometry's result; the sink legitimately changed it.** I have not touched the expectation — changing a pinned expectation to match new behaviour is a decision, not a cleanup, and it belongs with the zone work rather than buried in a rebound flip.

**What I should have done at `cd2a08c3e`:** run the suite, not just the targeted guards. The 130 pre-existing failures are exactly the kind of noise that lets a new one through.

## Step 7 — the crash animation still plays on every shot attempt

Arrival is scoring-only. Verified two ways, 8 seeds per arm, `SEED_DEFENSES=1`:

| arm | config | shots/game | **destinations authored/game** | per shot | cache hits | **`player.coords` mutations** |
|---|---|---|---|---|---|---|
| sim | arrival ON | 95.6 | 739.0 | **7.73** | 385.8 | **0** |
| sim | arrival OFF | 95.9 | 740.8 | **7.73** | 0.0 | **0** |
| played | arrival ON | 90.2 | 679.6 | **7.53** | 346.6 | **0** |
| played | arrival OFF | 92.0 | 701.4 | **7.62** | 0.0 | **0** |

**The per-shot authoring rate is unchanged** — makes, misses, shooting fouls and non-foul misses all still author their crash destinations. The "cache hits" column is the later authoring loops reusing what `_prepare_crash_arrival` already drew; it is not extra authoring, and counting raw calls instead of draws would have made the flag look like it authored 50% more (11.76/shot). **Zero coord mutations** across every call, measured by snapshotting `player.coords` around `_prepare_crash_arrival` and comparing — arrival never moves a player, it only changes what selection scores.

## The outcome table — reported, not adjusted

`equiv_v3_reference_bf7ed1181_crashmodela.json` (arrival OFF) → flipped (arrival ON), n=40, like-for-like at this tree:

**`SEED_DEFENSES=1` (production):**

| metric | sim OFF | sim ON | Δ | played OFF | played ON | Δ |
|---|---|---|---|---|---|---|
| **pts/team** | 70.29 ±3.24 | 74.66 ±3.62 | **+4.38** | 70.28 ±3.37 | 74.21 ±2.89 | **+3.94** |
| OREB | 17.27 ±1.20 | 18.77 ±1.53 | +1.50 | 17.27 ±1.34 | 20.57 ±1.57 | **+3.30** |
| **OREB share** | 26.35% ±1.60 | **29.41% ±1.78** | **+3.06** | 26.06% ±1.67 | **31.56% ±1.89** | **+5.50** |
| second-chance pts | 7.67 ±1.16 | 7.28 ±1.18 | −0.40 | 5.65 ±0.75 | 9.28 ±1.40 | **+3.62** |
| FG% | 44.08 ±1.94 | 46.00 ±2.00 | +1.93 | 42.72 ±2.25 | 44.81 ±1.93 | +2.09 |
| **possessions** | 44.15 ±1.83 | **41.05 ±2.06** | **−3.10** | 44.55 ±1.74 | **39.83 ±1.91** | **−4.72** |
| **arm gap** | **+0.01 ±3.67** | → | **+0.45 ±4.04** | | | |

**`SEED_DEFENSES=0`:** OREB share +4.39 (sim) / +7.29 (played), second-chance +2.52 / +2.50, possessions −1.05 / −4.10, pts/team +0.39 / +0.71, arm gap +0.15 → −0.17.

Byte-equality does not hold against the old reference on either arm (0/40) — selection's draws now follow the crash draws, so the stream re-phases by design.

**The two movements worth your eye at the eye test:** OREB share is up materially and resolved on both arms and both footings, and possessions are down 3–5 a game. Both are the intended consequence of crash position mattering; both are tuning surface. **Nothing was adjusted.**

## Tuning-pass items (reported, not fixed)

Appended to `_documentation_master/projects/UESS_Backlog.md` §8:

1. **`_ag_grid_per_game_sec` AG sensitivity is nearly flat** — AG 10 → 12.88, AG 90 → 15.12, a **17% spread across the whole range**. It is why arrival barely separates players and why the dormant race term can only ever be a ~±7% lever. **Changing it moves all movement, every emitter and archetype — not just rebounding.**
2. **`OREB_REBOUND_SCORE_DISCOUNT` (0.8) is calibrated against a head start that no longer exists** — the defense used to stand 3.33 (sim) / 3.93 (played) units nearer the bounce; arrival collapses that to 1.00 / 1.12, leaving the discount as the only brake.
3. **Shot-moment coordinate mismatch between the arms** — played's defenders are 1.60 units nearer the bounce and its crashers 1.13 nearer their destinations. The window derivation was ruled out as a cause (identical on both arms: mean 1.550 s, same p10/p90), so this is a **coord-parity correctness item**, not tuning.

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A.

## Not covered

- **Not merged to develop.** Jamie decides after an eye test.
- **Nothing retuned:** composite, team bonus, the 0.8 discounts including `OREB_REBOUND_SCORE_DISCOUNT`, `REBOUND_DISTANCE_SCALE`, `randint(1,6)`, `_ag_grid_per_game_sec`, crash tightness 0.7 — all untouched.
- `crash_destination.py`'s allowlisted signature and its two poisoned tests: untouched. Destinations still never read the bounce.
- **Not fixed:** `test_zone_credit_shell`. Reported above with its bisect; the pinned expectation belongs to the zone workstream.
- **Not investigated:** the other 129 suite failures. They are identical with the flag on and off, and predate this pass, but I have not established how far back they go or whether any others belong to my earlier zone/foul/crash work. **Given one of them turned out to be mine, that is worth its own pass.**
