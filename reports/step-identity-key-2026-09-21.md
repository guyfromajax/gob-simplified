# Step identity key — measured, then designed

**The best available answer, and it is the simplest one: there is no key to invent. The step dict
object is the identity, the grid already lives on it, and every consumer already reads it off the
object rather than by index.** Write-once is therefore a one-line predicate — *does this step already
carry a grid?* — with no key space, so nothing can be missing and nothing can collide.

**But the caution in the scope report was right, and the data backs it.** The bare **index moves for
5.3–5.6 % of surviving steps**, and `timestamp` is **not unique** in 23–27 % of snapshots. Either of
those, used as a key, would mis-key a real fraction of steps. The answer is not a better key — it is
to keep using no key at all.

**The number that prices Stage 2:** write-once blocks **41 % of all stamp writes**, 86 % of which
change the value, and **~18 % of realised interceptions sit on a step the coverage pass had already
overwritten** before the contest read it.

No behaviour changed. `git diff` at `cb9082f73` is **0 lines**; the only new file is this report;
`GOB_BOXOUT_CONTEST` is still `"0"`.

---

## 1. What identity a step carries today (Q1)

Inventory, from the constructors (`_create_shoot_step`, `phase_resolution.py:4580`) and from every
field observed across 197k step objects:

| field | present | usable as identity? |
|---|---|---|
| `timestamp` | always | **No** — not unique within a skeleton (§2) |
| `pos_actions` | always | content, not identity — two steps can share it |
| `events` | often | content |
| `_step_state` | after a stamp | **this is where the grid already lives** |
| `_attack_drive` / `_subtle_movement` | drive/subtle beats | payload |
| **any id / uid / index field** | **none** | — |

**There is no id field of any kind, and no monotonic counter.** `position_snapshot_ledger.py:123`
records a `step_index`, but that is a ledger row, not a property of the step.

What *does* exist: **the dict object itself**, and the fact that the grid is stored on it —
`step["_step_state"]["defense"]` — and read back off it. `_hco_step_def_xy(step, …)`
(`phase_resolution.py:5502`) takes the **step object** as its first argument and reads
`step["_step_state"]["defense"]` at line 5534. **The consumer never looks anything up by index.**

## 2. How unstable the bare index actually is (Q2)

Consecutive stamps within one HCO turn, survivors matched by object identity. n=40 seeds × 4 cells:

| | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| distinct step objects | 47,564 | 51,166 | 47,276 | 50,862 |
| survivors across a stamp pair | 27,695 | 27,327 | 27,330 | 27,226 |
| dropped (truncation) | 13,396 | 16,692 | 13,592 | 16,628 |
| new (append / expansion) | 12,772 | 15,372 | 12,724 | 15,472 |
| **bare index unchanged** | 94.40 % | 94.70 % | 94.54 % | 94.50 % |
| **bare index MOVED** | **5.60 %** | **5.30 %** | **5.46 %** | **5.50 %** |
| `timestamp` duplicated within a skeleton | 23.2 % | 26.4 % | 23.5 % | 26.7 % |

**The index is not stable, so the scope report's caution stands — but the instability is entirely
structural and predictable.** Index movement by mutation kind:

| stamp-pair mutation | index moves | survivors |
|---|---|---|
| **append only** (new steps after the last survivor) | **0** | 9,326 |
| **truncate only** | **0** | — (no pure-truncate pairs observed) |
| **both** (drop *and* add in one pair) | **1,551 — all of them** | 9,440 |
| none | 0 | 8,929 |

*(sim SD=1; the other three cells are identical in shape.)*

**Every index move happens under a single mutation: a stamp pair that both drops and adds steps.**
That is `skeleton["steps"] = list(output_steps)` after the walk (`phase_resolution.py:7410`, `:7977`,
`:8016`), which rebuilds the list — truncating unreached steps and appending beats in one operation.
Appending alone never moves an index; nor does truncating alone.

**This is the finding that makes the design small.** The brief anticipated a content-hash scheme. The
data says a content hash would be solving the wrong problem: the index moves, but **nothing that
matters is keyed on the index.**

## 3. Stage 2's blast radius, as a number (Q3)

Every write by `_stamp_contest_defender_grid`, split by whether write-once would allow it:

| | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| total writes | 75,161 | 78,493 | 74,506 | 78,088 |
| **FRESH** — no grid yet; write-once **allows** | 58.7 % | 61.2 % | 58.9 % | 61.0 % |
| **OVERWRITE** — write-once **blocks** | **41.3 %** | 38.8 % | **41.1 %** | 39.0 % |
| of blocked: value identical | 13.7 % | 14.5 % | 14.2 % | 14.6 % |
| of blocked: **value CHANGED** | **86.3 %** | 85.5 % | **85.8 %** | 85.4 % |
| blocked displacement, mean / p50 / p90 / max | 1.20 / 0.00 / 3.16 / **29.41** | 0.67 / 0.00 / 2.00 / 26.40 | 1.14 / 0.00 / 3.00 / 29.41 | 0.67 / 0.00 / 2.00 / 24.70 |
| **blocked writes crossing the 11-unit contest radius** (vs that step's ball handler) | **4.20 %** | 1.38 % | **3.88 %** | 1.34 % |

And the number that actually prices the risk — does an interception depend on one of those steps?

| | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| interception contests run | 36,346 | 33,869 | 35,773 | 33,433 |
| …on a step already overwritten | 40.0 % | 39.4 % | 39.7 % | 39.4 % |
| **interceptions realised** | 304 | 281 | 326 | 278 |
| **…on a step already overwritten** | **56 (18.4 %)** | 22 (7.8 %) | **59 (18.1 %)** | 30 (10.8 %) |

**So Stage 2 changes the geometry underlying ~18 % of interceptions at the production footing.** That
is the risk stated as a number rather than an adjective, and it is large enough that Stage 2 must be
flag-gated and measured on outcomes, not just on parity.

`StepState.md:91` independently estimated the coverage pass at *"≈18 % of interceptions"*. My 18.4 %
is a **different quantity** — interceptions whose step had been overwritten before the contest read
it, not interceptions found only by the coverage sweep. **The two agreeing to a decimal point is very
likely coincidence and I am not treating it as corroboration.** The load-bearing conclusion is the
same either way: the coverage pass must keep running.

**Note the footing split.** The radius-crossing rate is **3× higher at SD=1 than SD=0** (4.20 % vs
1.38 %), and the interception share is more than double. Zones exist only at SD=1, and zone placement
is where the divergence lives. **Measuring Stage 2 on the empty-catalogue footing would understate its
blast radius by a factor of two to three.**

## 4. The key (Q4)

> **The key is the step dict object. Write-once is: if `step["_step_state"]["defense"]` is already
> non-empty, do not write.**

Derived from nothing — that is the point. It requires no field, no hash, no counter, and no lookup
table, so there is no key to be absent, stale or duplicated.

**Why it survives all three mutations:**

| mutation | what happens | why identity holds |
|---|---|---|
| **truncation** | the list is rebuilt without some steps | survivors are *the same dict objects*; a dropped step takes its grid with it into the garbage |
| **appending** | new dicts appended | a new dict has no `_step_state`, so write-once draws it — correct |
| **expansion** | new dicts inserted, later indices shift | the shift is in the *list*, not in the objects; each survivor still carries its own grid |

The property that could have broken this is **a step being replaced by a content-identical copy** —
then the copy would look fresh and be redrawn, or worse, an index-keyed scheme would attach the wrong
grid. §5 measures it at zero.

## 5. The proof (Q5)

n=40 seeds 8000–8039, **both arms, both `SEED_DEFENSES`** — 160 games, 0 errors.

Object identity was measured via `id()`, which is only sound if ids cannot be recycled. **The probe
holds a strong reference to every step object it sees for the life of the process**, so CPython cannot
reuse an id for a different step. Without that the measurement would be worthless.

| property required | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| **a step present at stamp N and N+1 gets the same key** — measured as: the object persists and its grid persists with it. Index-moved survivors carrying a grid, grid **kept** | 395 | 208 | 432 | 185 |
| …same, grid **LOST** | **0** | **0** | **0** | **0** |
| **two distinct steps never collide** — measured as: a dropped step's content reappearing under a *new* object id (a copy/rebuild masquerading as the same step) | **0 / 47,564** | **0 / 51,166** | **0 / 47,276** | **0 / 50,862** |
| **no step object is shared between turns** (a stale grid surviving into a new turn would block a legitimate redraw) | **0** | **0** | **0** | **0** |
| survives **truncation** | 13,396 drops, 0 grid loss | 16,692 | 13,592 | 16,628 |
| survives **appending** | 9,326 survivors, **0 index moves, 0 grid loss** | — | 9,091 | — |
| survives **expansion** (the drop+add rebuild) | 9,440 survivors, 1,551 index moves, **0 grid loss** | 11,334 | 9,493 | 11,399 |

**No violations, and no special-casing was applied to reach that.** The key was not tuned: it is the
object, and the measurement asked whether the object is ever counterfeited. It is not.

### One violation of the *spirit*, found by the same probe

**~7 % of step objects already carry a grid the first time the stamp ever sees them.**

| | sim SD=1 | sim SD=0 | played SD=1 | played SD=0 |
|---|---|---|---|---|
| step objects first observed | 47,564 | 51,166 | 47,276 | 50,862 |
| **already carrying a grid at first sight** | **3,320 (6.98 %)** | 3,144 (6.14 %) | 3,267 (6.91 %) | 3,228 (6.35 %) |

Something other than `_stamp_contest_defender_grid` wrote them. It is
**`phase_resolution.py:7683`**, which writes `beat["_step_state"] = {"index": …, "defense":
_post_def_xy}` for a post-subtle beat, from `_hco_post_subtle_defender_row`'s **own independent
`compute_defender_grid` draw** on a synthetic two-step skeleton (`:5880`).

**Under write-once that pre-seeded grid wins permanently and the stamp never touches those steps.**
That is arguably correct — first writer owns the step — but it means "single producer" would be false
for 7 % of steps on day one. **This is a decision Stage 2 must take explicitly, not inherit.** Either
7683 is blessed as a legitimate first writer, or it is deleted and the stamp owns those beats. I am
not deciding it here.

## 6. Failure modes (Q6)

**The two failure modes the brief anticipates do not exist for this key**, and that is a consequence
of the design rather than luck:

- **missing key** — impossible; the predicate is a property of the object, not a lookup. A step with
  no grid *is* the fresh case, and drawing it is correct.
- **collision** — impossible; there is no key space. Two distinct steps are two distinct dicts.

**The failure mode that does exist is the opposite one: a consumer reaching a step that carries no
frozen grid.** Today `_hco_step_def_xy` handles that by **silently falling back to legacy
reconstruction** (`phase_resolution.py:5543` zone / `:5560` man) — which is *a fresh
`get_defender_coords` draw*, i.e. **exactly the defect Stage 2 exists to remove, reintroduced
silently**.

Per the two rules this is **26b, not 26**: nothing is being invented from nothing — the fallback
computes a real, plausible position — so it is a **guard that corrects**, and *"if it corrects, it
logs — every correction, with the value it replaced."* A silent redraw here would be the
`item 41` failure exactly: a healthy-looking instrument over a sick system.

**Required announcement** (shape, not code):

```
⚠️ [PLACEMENT FREEZE MISS] <consumer> read step i=<idx> with no frozen grid → legacy reconstruction
   (this is a REDRAW, not the frozen draw). turn=<game_id>/<turn_idx> steps=<n> zone=<bool>
   stamped_steps=<k>/<n> first_unstamped=<idx> reason=<appended_after_last_stamp|truncation|unknown>
```

Logged **per occurrence**, not once per turn, and counted so the rate is visible in a sweep. If that
counter is not ~0 after Stage 2, the freeze does not cover the steps consumers actually read, and the
stage is not done. **It is the stage's own acceptance test.**

A second, weaker announcement is worth having for the §5 pre-seed: when write-once blocks because
*another producer* got there first, say so once per turn with the producer's name. That keeps
"single producer" honest rather than aspirational.

## 7. The consumer list, checked against the code (Q7)

**The scope report's table was incomplete.** Verified by grepping every `_step_state` reference and
every `compute_defender_grid` / `compute_placement_grids` / `defender_grid_from_animations` caller:

### Writers of the grid — three, not one

| site | what it writes | Stage 2 |
|---|---|---|
| `phase_resolution.py:6494` `_stamp_contest_defender_grid` | `step["_step_state"]["defense"]` + `["offense"]` + `["guard"]` (zone only); 3 call sites — `:6530` coverage, `:7286` pre-walk, `:8017` freelance | **becomes write-once** |
| `phase_resolution.py:7683` | `beat["_step_state"]` from `_hco_post_subtle_defender_row` (`:5880`, its own draw) | **decide: bless or delete** (§5) |
| `step_state.py:108` `build_step_states` | `step["_step_state"] = {...}` — **overwrites the stamp**, acknowledged at `phase_resolution.py:7381` (*"NOT `_step_state`, which `build_step_states` overwrites"*) | **becomes a read, not a write** |

### Readers

| site | reads | note |
|---|---|---|
| `phase_resolution.py:5534` `_hco_step_def_xy` | `step["_step_state"]["defense"]` | the interception/bat contest; **silent legacy redraw when unstamped** (§6) |
| `phase_resolution.py:6419` | same | dish contest |
| `phase_resolution.py:4924` | `steps[shot_step_index]["_step_state"]["defense"]` → `source="hco-stepstate-shot-step"` | **shot-contest defender selection — a StepState reader the scope report missed**; falls back at `:4928` to another `compute_defender_grid` draw (`"hco-final-grid-shot-step"`) |
| `phase_resolution.py:5030` | scans steps backward for the last complete stamp | **the SIM arm's coord write** — this is the site that makes "sim and played read the same draw" true or false |
| `phase_resolution.py:7049` | `step["_step_state"]["guard"]` | zone guard map — a **second payload** on the same object |
| `phase_resolution.py:6894` | presence only | BAT-OOB orientation diagnostic, not a consumer of the value |
| `step_state.py:93` | the stamp, on the sim path | `"stamp-reuse-full-sim"` |

### Independent producers that bypass the grid entirely

| site | note |
|---|---|
| `attack_drive_clearance.py:1230–1272` | the drive reconstruction — no posture, zone collapse |
| `phase_resolution.py:5880` `_hco_post_subtle_defender_row` | own `compute_defender_grid` on a synthetic 2-step skeleton |
| `phase_resolution.py:4928` | shot-contest fallback draw |
| `skeleton_step_emitter.py:1636` | the `_hco_render_animations` stash — commit 2 deletes it |

**That is six readers, three writers and four independent producers** — against the scope report's
"four consumers". The design does not change, but the work is larger than that table implied, and
`:4924` / `:5030` in particular must be in Stage 2's scope or the sim arm and the shot contest will
keep reading something else.

## 8. Footing and neutrality

Rule 6e: equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5,
`SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed−8000)`,
n=40 seeds 8000–8039, **both arms, both `SEED_DEFENSES`** — 160 games, **0 errors**.
**Catalogue state: SD=1 seeds the six real defenses; SD=0 leaves it empty and every zone call plays
man** — which is why §3's blast radius is 3× larger at SD=1 and why Stage 2 must be measured there.

The probe reads frame locals under `sys.monitoring`, calls no engine code and draws no RNG:

| cell | fp vs `equiv_v3_reference_70f7dd021_b1a.json` | draws |
|---|---|---|
| sim SD=1 | **40/40** | **40/40** |
| sim SD=0 | **40/40** | **40/40** |
| played SD=1 | **40/40** | **40/40** |
| played SD=0 | **40/40** | **40/40** |

## 9. Residual risk in the key itself

**One, and it fails safe.** Object identity holds because nothing in the pipeline rebuilds a step
from scratch mid-turn (0 / 197k). If a future change introduced one:

- a `deepcopy` would copy `_step_state` too → write-once still blocks → **no change**;
- a genuine **rebuild** would produce a step with no grid → write-once draws it → **today's
  behaviour**.

Neither corrupts a grid onto the wrong step, which is the failure the scope report warned was worse
than the defect. **A mis-keyed freeze is not reachable with this key**, because there is no key to
mis-apply. That is the main reason to prefer it over any content hash.

The one thing that *is* worth a guard: `_apply_set_play_runtime_position_mapping`
(`phase_resolution.py:165`) **deep-copies steps** — at skeleton load, before any stamp, so it is
harmless today. If it ever moved later in the pipeline it would be the first thing to check.

## 10. What I did not do

- **Began nothing.** No freeze, no flag, no edits. Tracked diff 0 lines.
- **Did not decide the `:7683` pre-seed question** (§5). It is a Stage 2 design decision and it needs
  an owner call, not a measurement.
- **Did not measure what blocking the overwrites does to outcomes.** §3 gives the blast radius
  (41 % of writes, 4.2 % crossing the contest radius, ~18 % of interceptions); the FG%/turnover
  consequence needs the flag to exist and a re-cut, which is Stage 2 proper.
- **Did not verify `:4924` / `:5030` behaviour under write-once** — they are newly added to the
  consumer list and their reads were not separately instrumented.
- **Did not look at FB / HCT / pressure step-state modules** (`fb_step_state.py`,
  `pressure_step_state.py`). They have their own `_fb_step_state` / `_pressure_step_state` payloads
  and are out of HCO scope.

## 11. Tunable constants

| constant | where | value | relevance |
|---|---|---|---|
| `CONTEST_EUCLIDEAN_RADIUS` | `constants/__init__.py:364` | `11` | the threshold §3's 4.20 % crossing rate is measured against |
| `ATTACK_DRIVE_CONTEST_RADIUS` | `attack_drive_clearance.py:42` | `= CONTEST_EUCLIDEAN_RADIUS` | drive guardian test |
| `OPENNESS_LAG_MAX` / `OPENNESS_LAG_MARGIN_SCALE` / `OPENNESS_ANCHOR_MOVE_EPS` | `defender_placement.py:48–50` | `0.8` / `110.0` / `1.0` | inside the producer that write-once would freeze |
| `HELP_SAG` / `HELP_SAG_JITTER` | `shared_defense.py:1937–1938` | `{0.30, 0.55}` / `0.10` | the per-call draw write-once stops repeating |
| `GOB_SIM_PROFILE` | `sim_profiler.py:32` | unset | `=1` for the placement CPU share |
