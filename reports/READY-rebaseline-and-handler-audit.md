# READY — Part A passed 240/240. Part B corrected the premise and found a one-line fix.

Report: `reports/rebaseline-and-handler-audit.md`. Verified against the brief by Claude.
Two independent jobs, neither conclusion dependent on the other.

## PART A — PASSED. References can be trusted.

**240/240 cells** reproduce on fingerprint, draws, points_per_team, turns AND possessions — and
stronger than asked, both regenerated files are **byte-identical** to the committed ones,
including the derived `arm_gap_sim_minus_played`. Pass 2 was 240 fresh cells run independently
into a separate directory. Zero differing cells. No reference file modified, overwritten or
deleted. README updated to FULL DOUBLE RE-BASELINE PASSED 2026-09-24, replacing the subset
wording.

Rule 6e footing: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 /
traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process,
`SEED_DEFENSES=1` production footing (main reference also covers SD=0), `GOB_DEFENDER_AG_SPREAD`
unset = the shipped default.

**The brief's arithmetic was wrong and the agent corrected it.** The main reference holds **160**
cells, not 240 — n=40 seeds x 2 arms x 2 footings. With the loose baseline's 80 (40 x 2 arms,
SD=1 only) the true total across both files is **240**, counted from the committed JSON rather
than assumed. There is no missing 80. The "X/320" in the brief was Claude's error.

## PART B — the premise was wrong, and that makes the fix far cheaper

**Zero `NameError` is being swallowed today** — none, across 8 games in the shipped default
state. Clean answer.

**And the Stage 2 error was never silent in code. It was logged at WARNING and the HARNESS threw
the log away.** Every equiv-v3 cell runs `... > /dev/null 2>&1`, so 70-101 warnings per game went
straight to the bin. "Silently swallowed" described the effect, not the mechanism. Claude
asserted the wrong mechanism twice; the audit corrected it.

### B1 — 66 handlers, none of them bare

All 66 on the animation/step path are `except Exception` — **not one bare `except:`**, better
than expected. Shape: 31 log-then-continue, 21 substitute-a-default, 12 fully silent
(`pass`/`continue`), 2 return an empty payload.

The one that caught the Stage 2 error, identified by **reproduction** (re-injecting the exact
NameError and using `sys.monitoring` EXCEPTION_HANDLED to name the catching frame), not by
inspection — 101 catches in one game:

| handler | file:line | caught | what is skipped |
|---|---|---|---|
| `_emit_hco_animation_steps` | `turn_manager.py:4107` | 89 | the ENTIRE `animation_steps` payload for that HCO turn |
| `resolve_fast_break_logic` | `phase_resolution.py:1633` | 8 | the after-steal fast-break emit |
| `_emit_pressure_animation_steps` | `turn_manager.py:4258` | 4 | the dynamic FCP/HCT emit |

The handler logs a warning and stamps `eoq_schema_emit_failed`, then the turn proceeds with no
animation steps at all.

### B2 — what fires today

`NameError`: **0**. Raw counts of watched types look alarming (KeyError 244,236/game) but almost
all is CPython's own control flow self-handled in the raising frame — `os.environ.__getitem__`
(70,236/game, which is how `os.environ.get` is implemented), `copy._keep_alive`,
`copyreg._slotnames`, importlib locks, `typing.__getattr__`. None reaches engine code.

Filtering stdlib leaves **256/game at only two sites**, both harmless:
`player.py:269 __getattr__` AttributeError (254/game — that IS the `__getattr__` protocol) and
`rim_runner_fast_break.py:540` TypeError (1.6/game — `float(None)` as an absence test, caught on
the same line).

**Not one of the 66 broad handlers fires at all in the current shipped state.** They are dormant.

Probe RNG-neutral, `sys.monitoring` observation only, no control flow changed.

### B3/B4 — and the agent argued against its own cheap conclusion

Two handlers are provably load-bearing and **both are already narrow**: `player.py:269` (language
protocol — narrowing breaks object copying) and `rim_runner_fast_break.py:541` (genuinely
optional field; this is the model the others should follow). The other 64 are dormant, so the
audit can only say nothing legitimate depends on them **in the sampled state** — not that they
only hide bugs.

Blast radius of narrowing all 64: **nothing starts raising on today's evidence.** The agent then
said plainly that this is exactly why it should not be done on 8 games — those handlers exist to
keep the sim alive when an emitter fails on a rare turn, and the sample never hit one. It
recommends widening the census to a few hundred games first, to find the rare path before
removing its net. Claude agrees.

### B5 — the actual recommendation

Two parts, both cheap, both additive:

1. **One line in the harness.** Stop discarding stderr: tee it per cell and fail the run if it
   contains `build_skeleton_animation_steps ... failed` or `EMITTER EXCEPTION`. No engine change.
   **This alone would have caught Stage 2 on the first run.**
2. **`GOB_STRICT_EXCEPTIONS`**, read once at import into a module constant, with a shared
   `reraise_if_strict(e)` as the first line of each broad handler: re-raises `NameError`,
   `AttributeError`, `TypeError`, `UnboundLocalError` when set, returns otherwise. Default off
   means production is byte-identical and **needs no reference run**. `conftest.py` and the
   equiv-v3 runner set it to `1`. No handler removed or narrowed, so the rare-path net stays.

Claude's read: do both, and do #1 first. It converts the 64 dormant handlers from "hides bugs
forever" to "hides bugs only in production, where that is the intended trade."

## IMPORTANT — a constant Claude has been quoting is now stale

Since the default flip, seed 8000 played SD=1 is **fp `0c3389cd41d0bbef`, draws `75363`**.
The old `a1d150579771387a` / `77689` is still correct, but ONLY as the
`GOB_DEFENDER_AG_SPREAD=0` rollback check against the superseded reference. Any future
default-state verification must quote the new pair. The agent's own first neutrality check failed
on exactly this and it flagged it.

## Confirmed untouched

No handler narrowed or removed. No Stage 3 defect touched. All instrumentation in the
scratchpad; working tree carries no probe.

No merge by Claude. Jamie merges.
