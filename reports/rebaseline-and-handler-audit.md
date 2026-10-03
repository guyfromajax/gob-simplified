# Part A — full double re-baseline · Part B — NameError-swallowing handler audit

Two independent jobs. **Neither conclusion depends on the other.**

---

# PART A — full double re-baseline of the agspread references

## PASSED. Both references are byte-identical on an independent second pass.

**240/240 cells** reproduce on **fingerprint, draws, points_per_team, turns AND possessions** —
and, stronger than the brief asked, both reference **files regenerated from scratch are
byte-identical** to the committed ones, including the derived `arm_gap_sim_minus_played`.

**Nothing downstream is blocked.** The references can be trusted.

### Footing (Rule 6e)

| | |
|---|---|
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process, game id `0xE0000+(seed−8000)` |
| **Defenses catalogue** | **`SEED_DEFENSES=1` — production footing, seeded.** The main reference also covers `SEED_DEFENSES=0` (empty catalogue, zones play as man). |
| Flag state | `GOB_DEFENDER_AG_SPREAD` **unset** — the shipped default, which is ON since `f600628a4` |
| Pass 1 | the 240 cells the references were cut from |
| Pass 2 | **240 fresh cells, run independently into a separate directory** |

### Result

| reference | cells | fp | draws | points | turns | possessions | file byte-diff |
|---|---|---|---|---|---|---|---|
| `equiv_v3_reference_f600628a4_agspread.json` | **160/160** | ✓ | ✓ | ✓ | ✓ | ✓ | **identical** |
| `equiv_v3_loose_baseline_f600628a4_agspread.json` | **80/80** | ✓ | ✓ | ✓ | ✓ | ✓ | **identical** |
| **total** | **240/240** | | | | | | |

Zero differing cells, so there is nothing to itemise.

### One correction to the brief's arithmetic

The brief asked for the count **as X/320**, describing the main reference as "all 240 cells".
It holds **160**, not 240: n=40 seeds × 2 arms × 2 footings (`SEED_DEFENSES=1` and `=0`). With
the loose baseline's 80 (40 × 2 arms × SD=1 only), the true total across both files is **240**,
which is what I verified and what the files contain — counted directly from the committed JSON,
not assumed. **240/240 is the complete set; there is no missing 80.**

### README updated

Both rows now record **FULL DOUBLE RE-BASELINE PASSED 2026-09-24**, replacing the earlier
"independent subset (24/24, 8/8)" wording, and state that the regenerated files were
byte-identical. No reference file was modified, overwritten or deleted.

---

# PART B — audit of the handlers that can swallow a NameError

**READ-ONLY. Nothing was fixed, no handler removed, no `except` narrowed.** All
instrumentation lived in the scratchpad; the working tree carries no probe.

## Headline

**Zero `NameError` is being swallowed today**, across 8 games in the shipped default state. But
the premise needs one correction that changes the whole remedy: **the Stage 2 `NameError` was
not silent in code — it was logged at WARNING and the harness threw the log away.**

## B1 — Where

**66 handlers** on the animation / step-emission path can catch a `NameError`. Every one is
`except Exception` — **there is not a single bare `except:` on this path**, which is better than
expected. Files scanned: the step emitters, `animation_step_helpers`, `transition_bridge`,
`reset_step_helper`, the dynamic HCT/FCP path, `phase_resolution`, `animator` and `turn_manager`.

Shape of the 66:

| what the handler does | count | example |
|---|---|---|
| log then continue | 31 | `phase_resolution.py:1668` `logging.exception("🚨 [RR EMITTER EXCEPTION] …")` |
| substitute a default and continue | 21 | `animation_step_helpers.py:898` `return 14.0` |
| `pass` / `continue` — fully silent | 12 | `phase_resolution.py:3818`, `rim_runner_step_emitter.py:2198` |
| return an empty payload | 2 | `animator.py:1286` `return ({}, {})` |

### The one that swallowed the Stage 2 NameError — identified by reproduction, not inspection

I re-injected the exact failure (`NameError: name 'pid' is not defined`, raised inside
`build_shot_micro_steps`) without editing any engine file, and used `sys.monitoring`'s
`EXCEPTION_HANDLED` event to name the catching frame. In one game it fired **101 times**:

| handler | file:line | caught | what is skipped |
|---|---|---|---|
| **`_emit_hco_animation_steps`** | **`turn_manager.py:4107`** | **89** | the **entire `animation_steps` payload** for that HCO turn |
| `resolve_fast_break_logic` | `phase_resolution.py:1633` | 8 | the after-steal fast-break emit |
| `_emit_pressure_animation_steps` | `turn_manager.py:4258` | 4 | the dynamic FCP/HCT emit |

Real traceback, captured at runtime:

```
  File "BackEnd/models/turn_manager.py", line 4024, in _emit_hco_animation_steps
    anim_steps = build_skeleton_animation_steps(result, self.game)
  File "BackEnd/engine/skeleton_step_emitter.py", line 2761, in build_skeleton_animation_steps
    inject_shot_micro_before_post_shot(
  File "BackEnd/engine/shot_micro_movements.py", line 1692, in inject_shot_micro_before_post_shot
    apply_shot_micro_steps_to_chain(
  File "BackEnd/engine/shot_micro_movements.py", line 1806, in apply_shot_micro_steps_to_chain
    micro_steps = build_shot_micro_steps(
NameError: name 'pid' is not defined
```

And the handler itself (`turn_manager.py:4106-4110`):

```python
except Exception as e:
    logging.warning("build_skeleton_animation_steps (HCO) failed: %s", e)
    self._assert_eoq_animation_steps(result, anim_steps=None, context=f"emit_exc:{e}")
```

> **It logs.** The turn then proceeds with **no `animation_steps` at all** and a stamped
> `eoq_schema_emit_failed`. What made Stage 2's failure invisible was not the handler — it was
> the harness: every equiv-v3 cell runs `… > /dev/null 2>&1`, so 70–101 warnings per game went
> straight to the bin. **"Silently swallowed" describes the effect, not the mechanism.**

## B2 — What actually fires today *(the important question)*

Instrumented with `sys.monitoring` `RAISE` + `EXCEPTION_HANDLED` — observation only, no control
flow changed. **n=8 seeds 8000–8007, played arm, `SEED_DEFENSES=1`, `GOB_DEFENDER_AG_SPREAD`
unset (= ON, the shipped default).** Probe proved RNG-neutral: seed 8000 reproduced the new
default reference exactly (fp `0c3389cd41d0bbef`, draws `75363`).

### `NameError`: **0**. None. Not one, in 8 games.

That is a clean answer, and it is the answer.

Raw counts of the watched types look alarming until they are filtered:

| type | total (8 games) | per game |
|---|---|---|
| `KeyError` | 1,953,892 | 244,236 |
| `TypeError` | 11,138 | 1,392 |
| `AttributeError` | 2,852 | 357 |
| **`NameError`** | **0** | **0** |

**Almost all of it is CPython's own control flow, self-handled in the frame that raised it** —
`os.environ.__getitem__` (how `os.environ.get` is implemented, 70,236/game), `copy._keep_alive`,
`copyreg._slotnames`, `importlib` module locks, `typing.__getattr__`. None of it reaches engine
code.

Filtering the stdlib out leaves **2,048 raises in 8 games (256/game)**, and only two sites:

| type | site | per game | caught by | what is skipped |
|---|---|---|---|---|
| `AttributeError` | `player.py:269/273/276 __getattr__` | 254 | `player.py:269` (itself) and normal `hasattr`/`copy` machinery | **nothing** — `AttributeError` *is* the `__getattr__` protocol. Lookups are `__setstate__`, `_eff_slot_rating_cache`. |
| `TypeError` | `rim_runner_fast_break.py:540` | 1.6 | `except (TypeError, ValueError)` on the same line | **nothing** — `float(None)` when `ball_bounce_x` is absent; the code then uses `bounce_x = None` |

> **Not one of the 66 broad handlers fires at all in the current shipped state.** The emitter
> handlers at `turn_manager.py:4107`, `phase_resolution.py:1668` and the rest caught **zero**
> exceptions of any watched type across 8 games. They are dormant today.

## B3 — Load-bearing or not

| handler | load-bearing? | evidence |
|---|---|---|
| `player.py:269` `__getattr__` `except AttributeError` | **YES, by language protocol** | 254/game. `AttributeError` is how Python signals "no such attribute"; `hasattr`, `copy` and pickling all rely on it. Removing it breaks object copying. |
| `rim_runner_fast_break.py:541` `except (TypeError, ValueError)` | **YES, expected condition** | 1.6/game. `ball_bounce_x` is genuinely optional; `float(None)` is the cheapest absence test. **Already correctly narrow — this is the model the others should follow.** |
| `animation_step_helpers.py:898` `except Exception: return 14.0` | **Unproven** | never fires in 8 games; guards a constants import that cannot realistically fail |
| the 3 emitter handlers that caught the Stage 2 error (`turn_manager.py:4107`, `:4258`, `phase_resolution.py:1633`) | **NO evidence of a legitimate dependency** | zero catches in 8 games. Their stated purpose is "the sim must continue if an emitter fails" — a real design choice, but nothing today exercises it. |
| the other ~60 `except Exception` handlers | **NO evidence either way** | zero catches in 8 games; they are dormant |

**The honest summary: two handlers are provably load-bearing and both are already narrow. The
other 64 are dormant, so this audit cannot prove they only hide bugs — it can only say that
nothing legitimate depends on them in the sampled state.** Absence of evidence over 8 games is
not proof; a rare path (a malformed skeleton, a missing role) could still need one.

## B4 — Blast radius of narrowing them

Estimated **directly from B2's counts, which are zero for every broad handler**:

| if narrowed to exclude `NameError`/`AttributeError`/`TypeError` | what starts raising today |
|---|---|
| the 3 emitter handlers | **nothing** — 0 catches in 8 games |
| the other ~60 broad handlers | **nothing** — 0 catches in 8 games |
| `player.py:269` | would break object copying — **must not be narrowed** |
| `rim_runner_fast_break.py:541` | already narrow — no change needed |

> **Distinct sites needing separate work: 2 to exempt, 64 to narrow, and on today's evidence
> zero would begin raising.** That makes the change look cheap — and that is exactly why it
> should not be done on 8 games of evidence. These handlers exist to keep the sim alive when an
> emitter fails on a rare turn; the sample simply never hit one. A safe sequencing would widen
> the census to a few hundred games *first*, to find the rare path before removing its net.

## B5 — Detection without fixing

The cheapest fix is not a code change at all: **the log already exists.** The equiv-v3 runner
discards it with `> /dev/null 2>&1`, so the single highest-value change is to stop throwing it
away — tee stderr to a per-cell file and fail the run if it contains
`build_skeleton_animation_steps … failed` or `EMITTER EXCEPTION`. That costs one line in the
harness, no engine change, and would have caught Stage 2 on the first run.

Beyond that, a `GOB_STRICT_EXCEPTIONS` debug variable, read once at import into a module
constant, would let the handlers re-raise programming errors while staying silent in
production: a tiny shared helper, `reraise_if_strict(e)`, called as the first line of each broad
handler, which re-raises when the flag is set and the exception is a `NameError`,
`AttributeError`, `TypeError` or `UnboundLocalError`, and returns otherwise. Default off means
production behaviour is byte-identical and needs no reference run; `conftest.py` sets it to `1`
for the whole suite, so any test touching an emitter path fails loudly on a typo'd name instead
of quietly emitting a turn with no animation. It is additive — no handler is removed or
narrowed, so the rare-path safety net stays intact — and it converts the 64 dormant handlers
from "hides bugs forever" to "hides bugs only in production, where that is the intended
trade". The equiv-v3 runner would set it too, which is what would have turned Stage 2's 70
swallowed errors into an immediate, unmissable failure.

---

## Anything that did not behave as expected

1. **Part A's stated total was wrong in the brief** (320 vs the actual 240); I counted the rows
   in the committed files rather than accepting the figure. Flagged above.
2. **The premise of Part B needed correcting.** The Stage 2 error was logged, not silent. The
   harness discarded it. This makes B5 much cheaper than "narrow 64 handlers".
3. **My first RNG-neutrality check on the Part B probe failed** — I compared against the old
   flag-off fingerprint (`a1d150579771387a`). Since the default flip the correct value for seed
   8000 played SD=1 is **`0c3389cd41d0bbef` / `75363`**, and the probe matches it exactly. Worth
   noting for anyone reusing the old constant: **it is stale.**
4. **No bare `except:` exists on this path** — 66 of 66 are `except Exception`. Better than the
   audit expected.
