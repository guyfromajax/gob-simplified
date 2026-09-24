# Movement-rate unification — Stage 1: mechanical de-duplication

**Byte-identical. 160/160 on the main reference, 80/80 on the loose footing, fingerprint AND
draw count, all four cells.** Nothing was fixed, no flag was added, and every known defect was
carried through unchanged — including the four hardcoded `12.0` fallbacks and the three
missing `max(0.0, …)` floors, each now commented `STAGE 2`.

Source of truth for every count below: `reports/movement-rate-inventory.md`.

---

## Footing (Rule 6e)

| | |
|---|---|
| Branch / HEAD | `feature/animation-reward`, refactor applied on top of `17c611fa4` |
| Worker | `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5 |
| Env | `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process |
| Seeds | 8000–8039 (n=40) for the references; 8000–8007 (n=8) for the coverage trace |
| **Defenses catalogue** | **`SEED_DEFENSES=1` — production footing.** The main reference also covers `SEED_DEFENSES=0` (empty-catalogue path, zones behave as man); the loose baseline defines SD=1 only. |
| Coverage trace | played arm, SD=1, RNG-neutral (reproduced seed 8000 fp `a1d150579771387a` and draws `77689`) |

---

## 1. Files changed

Nine engine files, plus one new test file. **251 insertions, 172 deletions** — and most of the
insertions are the comments explaining what was preserved and why.

| file | + | − | what changed |
|---|---|---|---|
| `BackEnd/utils/shared.py` | 102 | 0 | the rate core: `_archetype_rate`, `_defender_spread_rate`, `movement_rate` |
| `BackEnd/utils/animation_step_helpers.py` | 78 | 60 | both public rate functions became delegates; `_interrupted_coord` core + two wrappers added |
| `BackEnd/engine/covert_release_step_emitter.py` | 19 | 5 | 4 × `fallback_rate=12.0`, private stamper routed, 3 × unguarded floor annotated |
| `BackEnd/engine/fb_outlet_pass_step_emitter.py` | 12 | 24 | definition → lenient alias; private stamper routed |
| `BackEnd/engine/rim_runner_step_emitter.py` | 12 | 25 | definition → lenient alias; private stamper routed |
| `BackEnd/engine/skeleton_step_emitter.py` | 8 | 32 | `_interpolate_step_end` definition → re-export |
| `BackEnd/utils/transition_bridge.py` | 7 | 14 | definition → strict alias |
| `BackEnd/utils/reset_step_helper.py` | 7 | 12 | definition → strict alias |
| `BackEnd/engine/dynamic_hct.py` | 6 | 0 | comment only — the injection site, annotated |
| `tests/test_movement_rate_accessor.py` | new | | 20 tests |

### What was built

**One rate core** (`shared.py`). `movement_rate(player, archetype, *, apply_spread,
fallback_rate=None)`. `_ag_grid_per_game_sec` and `defender_movement_rate` in
`animation_step_helpers` are now three-line delegates, so **all 117 call sites reach the
accessor without a single call site being rewritten** — which is also why the refactor can be
byte-identical.

- `apply_spread` **is** the old `is_defender` argument. `movement_rate(p, a, apply_spread=x)`
  equals `defender_movement_rate(p, a, x)` for all x, pinned by a test.
- **The clamp order is preserved exactly**: `[0.5, 60]` is applied to the AG-scaled STANDARD
  rate inside `ag_to_grid_per_game_sec`, and the archetype multiplies afterwards. A test uses
  AG=100000 on `burst` to prove the result can exceed 60 — which is only true in that order.
- The two AG-extraction paths are **deliberately not merged**: `_archetype_rate` does not
  coerce to float and does not swallow exceptions, `_defender_spread_rate` does both. Merging
  them would move results for malformed attribute dicts.
- `DEFENDER_AG_SPREAD`, `DEFENDER_AG_SPREAD_FLAG` and `defender_ag_spread_enabled` **stay in
  `animation_step_helpers`** and are read through the module at call time, so the existing
  tests that monkeypatch them still reach the arithmetic.

**Equivalence was proved before any sim ran**: the pre-refactor module was loaded side by side
with the new one and swept over 9 archetypes × 257 player shapes (AG −50…200, plus `None`, a
non-dict `attributes`, a missing `attributes`, `AG=None`, `AG="x"`, `AG=1e9`) × both
`is_defender` values, in four flag states (unset / "1" / "0" / s=0.10). **18,504 comparisons,
0 mismatches.**

**One `_interrupted_coord` core, two named wrappers.** The four definitions are gone. Each of
the four legacy module-level names is now bound to the wrapper for the variant **that module
reached before**, so the 32 call sites did not need to be touched and cannot be mis-pointed:

| module | binds | variant |
|---|---|---|
| `transition_bridge`, `reset_step_helper` | `_interrupted_coord_strict` | A — no None guard, zero test `< 1e-9` |
| `rim_runner_step_emitter`, `fb_outlet_pass_step_emitter` | `_interrupted_coord_lenient` | B — None guards incl. `(50, 25)`, zero test `== 0.0` |

Keeping the module-level names matters: other modules import them **by value**
(`dynamic_hct` ← `transition_bridge`, `triangle_step_emitter` ← `rim_runner`), so the alias is
what preserves today's routing. Verified over **200,000 random inputs per variant plus every
degenerate case — 0 mismatches**, including that strict still raises `TypeError` on `None` and
lenient still returns `(50, 25)`. The `(50, 25)` branch carries
`# STAGE 2: see reports/movement-rate-inventory.md`.

All four old definitions called an arithmetically identical `_euclid`
(`(dx*dx + dy*dy) ** 0.5`) — including `rim_runner`'s private copy — so routing them all
through one module's `_euclid` is byte-identical. The other six `_euclid` variants were left
alone, as instructed.

**One combined helper.** `_interpolate_step_end` and `_motion_end_toward_dest` were verified
byte-identical over **200,000 random inputs (0 mismatches)**; one implementation now lives in
`animation_step_helpers` and `skeleton_step_emitter` re-exports the other name for its seven
callers. **Both still take a RAW rate** — a test fails if anyone wires the spread into them,
because that would be a later stage and would not be byte-identical.

**The injection is threaded, not bypassed.** `dynamic_hct.py` passes `ag_grid_fn` and
`interrupted_fn` into `fcp_offball_attack` (1,989 calls per 8 games). Both names it passes are
now the canonical ones by construction: `_ag_grid_per_game_sec` delegates to the accessor, and
`_interrupted_coord` there is the strict wrapper. The expressions were left untouched and
annotated; the test **executes** the injected callable rather than grepping for it.

**The three private stampers** (`rim_runner:297`, `fb_outlet_pass:87`, `covert_release:877`)
now call `movement_rate(..., apply_spread=False)`. They stay on the raw rate, so they are
byte-identical today and the later flip is a one-line change. They were **not** unified with
the shared stamper.

### What was preserved exactly

| preserved | where | evidence |
|---|---|---|
| hardcoded `12.0` fallback (×4) | `covert_release` 493/1067/1307/1718 → `fallback_rate=12.0` | test asserts 4 occurrences and ≥4 `STAGE 2` markers |
| missing `max(0.0, …)` floor (×3) | `covert_release` `max_traversal = rate * t` | test asserts the floor was **not** added |
| the two `_interrupted_coord` policies | strict vs lenient | test asserts they still differ exactly where they did |
| `drift_or_hold_coord` | untouched — it draws RNG inside its clamp | test asserts `r.random()` is still there and it does not use the shared clamp |
| the 11 `_euclid` definitions | untouched | — |
| the 5 duration helpers with divergent fallbacks | untouched | — |

---

## 2. Verification — 160/160 and 80/80

`equiv_v3_reference_1f4af0ede_loosesag_nogate.json`, n=40 seeds 8000–8039:

```
  SD=1 sim     40/40 fp+draws
  SD=1 played  40/40 fp+draws
  SD=0 sim     40/40 fp+draws
  SD=0 played  40/40 fp+draws
  TOTAL 160/160
```

`equiv_v3_loose_baseline_1f4af0ede_loosesag.json` (defines SD=1 only), n=40:

```
  LOOSE SD=1 sim     40/40 fp+draws
  LOOSE SD=1 played  40/40 fp+draws
  TOTAL 80/80
```

Seed 8000 reproduces **fp `a1d150579771387a`, draws `77689`** as required.

**Full suite: 3,556 passed, 20 skipped, 110 xfailed, 0 failed, 0 XPASS.** That is the
pre-refactor baseline of 3,536 completely unchanged, plus the 20 new coverage tests — so no
existing test had to be edited to accommodate this stage, which is itself evidence that
nothing observable moved.

---

## 3. Derivation pairing — unchanged

n=8 seeds 8000–8007, played arm, SD=1, 21,885 shared-stamper steps. The probe is the audit's,
adapted to hook the two wrappers instead of the four definitions, and is RNG-neutral.

| kind | now | audit | delta |
|---|---|---|---|
| COMBINED only (endpoint+duration together) | **59.36%** | 59.36% | −0.00 |
| IC only → duration RE-DERIVED by stamp | **33.29%** | 33.29% | −0.00 |
| MIXED IC + COMBINED in one step | **2.68%** | 2.68% | −0.00 |
| no clamp (endpoint set directly) | **4.68%** | 4.68% | −0.00 |

Per turn type, also identical to the audit:

| turn | steps | COMBINED | IC-only | MIXED | no-clamp |
|---|---|---|---|---|---|
| HCO | 14,630 | 60.03% | 32.00% | 2.06% | 5.92% |
| FREE_THROW | 2,019 | 71.47% | 27.54% | 0.20% | 0.79% |
| FCP | 1,839 | 40.24% | 48.67% | 7.07% | 4.02% |
| HCT | 1,817 | 45.79% | 43.20% | 8.09% | 2.92% |
| FAST_BREAK | 1,580 | 75.51% | 23.29% | 0.25% | 0.95% |

Clamp-variant call counts are identical too, which is the direct evidence that routing was
preserved rather than merely producing the same totals:

| variant | calls (now = audit) |
|---|---|
| `_interpolate_step_end` (combined) | 111,249 |
| IC-A strict | 71,868 |
| `_motion_end_toward_dest` (combined) | 8,230 |
| IC-B lenient | 2,420 |

And the wrapper-bypassing local stampers still account for exactly **349 steps**, with the same
per-turn breakdown (rim_runner 267, fb_outlet_pass 82).

---

## 4. The coverage test — `tests/test_movement_rate_accessor.py`

20 tests. Site counts measured by the test itself, all matching the brief's expectation:

| | expected | found |
|---|---|---|
| rate-producer call sites | 117 | **117** (`_ag_grid_per_game_sec` 74, `defender_movement_rate` 27, `movement_rate` 9, `ag_to_grid_per_game_sec` 7) |
| `_interrupted_coord` consumers | 32 | **32** (31 direct + 1 injected) |
| combined-helper callers | 13 | **13** |
| rate-function definitions | — | **4** (the core, the curve, and the two delegates) |

It catches both failure modes the audit exposed:

**(a) by-value imports.** `test_every_module_holds_the_canonical_rate_functions` walks every
module in `BackEnd` via `pkgutil.walk_packages` and asserts identity (`is`) for all four names
— so a module holding a stale or private copy fails, which a single module-attribute patch
would have missed. `test_no_module_defines_its_own_rate_function` additionally asserts that
only the four legitimate definitions exist.
`test_the_private_stampers_route_through_the_accessor` patches each of the three emitters'
**own** `movement_rate` attribute, which is the by-value point of failure.

**(b) injected callables.** `test_the_injected_path_receives_the_canonical_callables` asserts
`dynamic_hct` binds the canonical objects, and
`test_the_injected_rate_actually_reaches_the_accessor` **executes** the injected callable in
`fcp_offball_attack`'s call shape against a spy on `shared.movement_rate`. Grep cannot see this
site; the test does.

A new site deriving a rate outside the accessor fails
`test_the_ag_curve_has_exactly_one_implementation` (a second copy of the curve) or
`test_no_module_defines_its_own_rate_function` (a private rate function).

---

## 5. What could NOT be made byte-identical

**Nothing.** Every item in the brief's scope is byte-identical, proved three ways: exhaustive
pre/post function sweeps (18,504 + 400,000 comparisons, 0 mismatches), the two equiv-v3
references (160/160 and 80/80 on fingerprint **and** draw count), and the derivation-pairing
trace reproducing the audit's shares to the digit.

Two things are worth stating rather than leaving implied:

1. **`rim_runner_step_emitter` no longer uses its private `_euclid` for `_interrupted_coord`.**
   Its local definition is still there and still used elsewhere; the clamp now goes through
   `animation_step_helpers._euclid`. Those two are the *same* implementation
   (`(dx*dx + dy*dy) ** 0.5`, verified by normalised AST hash), so this is byte-identical — but
   it is a real change of which object is called, not just a rename.
2. **34 of the 117 producer sites never fired** in the audit's 8 games, so their byte-identity
   rests on the function-level equivalence sweep rather than on the reference run. They were
   refactored for consistency like the rest. The unexercised set is dominated by
   `covert_release_step_emitter`, which means **the four `12.0` fallbacks and the three missing
   floors are all on cold paths** — carried through unchanged, but not exercised by the
   reference.

---

## 6. Latent findings (reported, not fixed)

Nothing new beyond the audit. The three defects Stage 1 deliberately carried — the `12.0`
fallback, the missing `max(0.0, …)` floor, and the `(50, 25)` both-None return — are each
marked `STAGE 2` in source and pinned by a test that fails if someone "tidies" them away
without a flag and a reference run.
