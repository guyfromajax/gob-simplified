# Resolving the skeleton-source contradiction

Branch `feature/animation-reward`, HEAD `f9b6d1eb8`. **READ-ONLY**: nothing fixed, no flag, no
behaviour change. Instrumentation lives in `scratch_skelsrc.py` (gitignored) and a scratch cell.
All feature flags OFF.

**Rule 6e footing**: worker `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2
/ traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, `ALIGN_RNG=0`, one game per process,
`SEED_DEFENSES=1`, `GOB_DEFENDER_AG_SPREAD` unset (ON). **n=8 seeds 8000–8007, both arms = 16
games**, which is ample: the split is 98/2, nowhere near close.

**RNG neutrality proved, not assumed.** All **16/16** cells reproduce the reference on
fingerprint AND draws; seed 8000 played SD=1 = fp `0c3389cd41d0bbef`, draws `75363`. Probe
errors: **0**.

---

## Q1 — Ground truth by object identity

Tagging is by **object identity**, not heuristic. The tag is on the **step dict**, not the
skeleton: `get_hco_skeleton` rebuilds the skeleton dict on several paths
(`{"steps": ..., "version": ...}`), which would drop a skeleton-level tag, whereas step dicts are
carried by reference everywhere and the only two copy points —
`plays_catalog.doc_by_name` and `_apply_set_play_runtime_position_mapping` — both use
`copy.deepcopy`, which preserves inner keys.

Tag points (both installed before the worker seeds): every step in the seeded play catalogue →
`mongo`; every step in the six `BackEnd/playcall_skeletons/*_SCENES` tables → `hardcoded`; every
step in `fcp_skeletons` / `hct_skeletons` → `fcp_hct_hardcoded` (a separate family, tagged
distinctly so it cannot be mistaken for the HCO fallback).

Tagged at source: 215 mongo steps, 45 hardcoded steps, 270 FCP/HCT steps.

### (a) `get_hco_skeleton` calls by true source (n=5,726)

| source | calls | share |
|---|---|---|
| **mongo** | 5,607 | **97.92%** |
| **hardcoded** | 119 | **2.08%** |

### (b) Steps returned by true source (n=40,947)

| source | steps | share |
|---|---|---|
| **mongo** | 40,114 | **97.97%** |
| **hardcoded** | 833 | **2.03%** |

### (c) Distinct skeletons executed, by source

Per-game distinct counts, summed over 16 games: **mongo 252** (≈15.8 per game), **hardcoded 16**
(= **exactly 1 per game**).

One distinct hardcoded skeleton per game, and the arithmetic closes exactly: each `*_SCENES`
table holds **one** scene, `INSIDE_SCENES` is 7 steps, and 119 × 7 = **833** — the hardcoded step
total above, to the step.

### (d) Executed steps, counted per step by its own tag

| execution point | steps | mongo | untagged |
|---|---|---|---|
| `defender_placement.build_all_animations` | 44,642 | 28,754 (**64.41%**) | 15,888 (35.59%) |
| `skeleton_step_emitter.build_skeleton_animation_steps` | 23,211 | 11,780 (**50.75%**) | 11,431 (49.25%) |

**Hardcoded steps never reach either execution point** (0 of 44,642 and 0 of 23,211), and neither
do the FCP/HCT hardcoded tables — 270 steps tagged at source, **0 executed**.

The `untagged` remainder is a **third category neither probe considered**: steps synthesised at
runtime by the engine (FCP/HCT dynamic builders, transition/OREB/DREB legs) rather than read from
any authored file. It is not a hardcoded-scene contribution.

### Answer

**The hardcoded scenes are not load-bearing: 2.08% of calls, 2.03% of returned steps, and 0% of
steps that reach either execution point.** Probe A was right.

---

## Q2 — Why Probe B was wrong

Probe B labelled a call `mongo` if `_get_skeleton_from_team_plays` returned truthy during it, and
`fallback` otherwise.

| true source | Probe B said | calls | |
|---|---|---|---|
| mongo | mongo | 3,679 | correct |
| **mongo** | **fallback** | **1,928** | **MISLABELLED** |
| hardcoded | fallback | 119 | correct |

**Probe B called 2,047 calls (35.7%) "fallback". 1,928 of them — 94.2% of its fallback bucket —
were MongoDB-sourced.**

The cause is structural, and it is the thing neither earlier probe noticed: **`get_hco_skeleton`
has three sources, not two.**

1. `_get_skeleton_from_team_plays(...)` — team plays → universal plays collection
2. **`plays_catalog.doc_by_name(playcall)` — the universal plays catalogue, also MongoDB**
3. the hardcoded `*_SCENES` tables — final fallback

Probe B's heuristic was binary. Source 2 returns *after* source 1 has returned falsy and *before*
the hardcoded fallback is reached, so every skeleton served from the universal catalogue was
counted as "fallback". That is 1,928 of 5,726 calls, and it is the entire discrepancy.

The suspected trigger named in the previous audit — "`_get_skeleton_from_team_plays` returning
falsy" — is therefore **confirmed as the mechanism**, but its consequence was misread: falsy does
not mean "hardcoded", it means "not the team-plays route", and the very next route is still
MongoDB.

### The two candidate explanations from the previous audit, both tested

- **(a) "the attribution heuristic mis-labels Mongo-sourced skeletons" — CONFIRMED.** Measured
  directly above: 1,928 mislabelled calls.
- **(b) "the fallback scenes are copied before the patch point" — DISPROVEN.** They are not
  copied; they are simply never reached in a way that matters. The tag was injected into the live
  module objects and 119 calls did return tagged hardcoded steps, so the patch point is reached
  and the objects are the live ones. Those 119 calls just never survive to execution.

### And why patching them changed nothing (the Probe A result, now explained)

All 119 hardcoded calls occur with **`current_playcall == ""`** (119 of 119). The empty string
matches no key in `playcall_map` (`"Inside"/"Outside"/"Attack"/"Set"/"Freelance"/"Base"`), so
`playcall_map.get(playcall, INSIDE_SCENES)` resolves to **`INSIDE_SCENES` every time**.

That closes the loop on the previous audit's counterfactuals D/E: they moved `PF` off
`upper lowPost` in the fallback tables, but `INSIDE_SCENES` — the only table ever reached —
authors **no PF at `upper lowPost`** (its PF sits at `upper highPost`/`topLane`). The patch was
real, the objects were the live ones, and the edit was simply to five tables that never execute.

### Latent bug found, reported not fixed

`phase_resolution.py:11076` reads
`game_context.game_state.get("current_playcall", "Inside")`. The default **can never apply**:
`GameManager.switch_possession` (`game_manager.py:2407`) sets
`game_state["current_playcall"] = ""`, so the key is always present and the read returns `""`,
not `"Inside"`. An empty playcall then silently routes to the hardcoded `INSIDE_SCENES` instead
of the authored catalogue. `phase_resolution.py:8530` has the same `get(..., "Inside")` shape.

It is small (2% of calls, and those steps do not reach execution here) but it is a real
defect-shaped thing: a default that looks like a safety net and is dead.

---

## Q3 — The lean fallback is a different mechanism, and it never fires

Measured separately, as instructed.

| | calls | share |
|---|---|---|
| `get_skeleton_by_lean` calls | 4,660 | — |
| **served the requested variant** | **4,660** | **100.00%** |
| **fell back to `successful`** | **0** | **0.00%** |

| requested → served | n |
|---|---|
| successful → successful | 3,848 |
| contested → contested | 358 |
| mid_play_change → mid_play_change | 323 |
| broken → broken | 131 |

Cross-tab with the whole-skeleton source: the lean fallback fires **0 times**, so the two
mechanisms do not overlap at all. Whole-skeleton hardcoded fallback = 2.08% of calls; lean
fallback = 0%.

### This corrects the previous audit

`reports/coincidence-origin-audit.md` states that only the `successful` lean is authored and that
`mid_play_change`, `contested` and `broken` are empty and fall back. **That is wrong.** All four
leans are authored; the three non-`successful` ones use the **`versions` array format**, with
6 versions each:

| play | successful | mid_play_change | contested | broken |
|---|---|---|---|---|
| 4-1 Motion | 7 steps | 4 steps / 6 versions | 8 / 6 | 9 / 6 |
| 4-1 Flex Motion | 9 | 7 / 6 | 10 / 6 | 9 / 6 |
| 5-0 Motion | 9 | 7 / 6 | 10 / 6 | 12 / 6 |
| 3-2 Motion | 6 | 6 / 6 | 7 / 6 | 10 / 6 |
| Pick & Roll (Lower Wing) | 7 | 8 / 6 | 9 / 6 | 7 / 6 |
| Double Screen For SG | 8 | 5 / 6 | 9 / 6 | 9 / 6 |
| Base Post Play | 5 | 5 / 6 | 6 / 6 | 7 / 6 |

The previous audit read `skeleton["steps"]` at the top level, which is `0` for a versioned
variant because the steps live under `skeleton["versions"][i]["steps"]`. It measured the wrong
key and concluded the variants were empty.

**Was either probe conflating the two fallbacks?** Probe B, yes — implicitly. Its single
`fallback` label covered "not the team-plays route", which bundles the universal-catalogue route
(97.9% of everything) with the genuinely-hardcoded route. It said nothing about leans, but the
previous audit's narrative then joined the two into one story about "fallbacks", which is where
the confusion compounded. Probe A was not conflating anything; it was a clean negative result
that was disbelieved because Probe B contradicted it.

---

## Q4 — Not applicable, with the reason stated

Q4 was conditional on the hardcoded scenes being load-bearing. They are not (2.08% of calls, 0%
of executed steps), so the "the play catalogue someone authors is not what runs" concern **does
not hold**. For completeness, the comparison is small either way:

| | authored catalogue | hardcoded scenes |
|---|---|---|
| plays / scenes | 7 plays | 6 scenes (one per file) |
| variants | 4 leans, 3 of them × 6 versions | none |
| total authored steps | 4,160 tagged | 45 tagged |
| reached in 16 games | 252 distinct skeletons | 1 distinct scene (`INSIDE_SCENES`) |

The six hardcoded scenes do not describe the seven authored plays; they are a single generic
scene each. **Five of the six were never reached at all** in 16 games, because the only route to
them is an empty playcall, which always selects `INSIDE_SCENES`.

---

## Bottom line

| question | answer | confidence |
|---|---|---|
| Where does execution come from? | **97.9% of `get_hco_skeleton` calls and 98.0% of returned steps are MongoDB-sourced. 2.1% / 2.0% are hardcoded — and 0% of hardcoded steps reach either execution point.** | **High** — by object identity, 16/16 RNG-neutral cells, 0 probe errors, and the step arithmetic closes exactly (119 × 7 = 833) |
| Which probe was wrong? | **Probe B.** Its binary heuristic could not see the middle route (`plays_catalog.doc_by_name`), so it labelled 1,928 MongoDB calls "fallback" — 94.2% of its fallback bucket | **High** — measured directly against the tag |
| Why did patching the scenes do nothing? | The patch was applied to the live objects and was reached, but an empty playcall always selects `INSIDE_SCENES`, and `INSIDE_SCENES` has no `PF → upper lowPost` to patch | **High** — 119/119 calls had `current_playcall == ""` |
| Lean fallback | **Fires 0 times in 4,660 calls.** All four leans are authored; three use the `versions` format the previous audit did not read | **High** |
| Untagged executed steps | 35.6% / 49.3% of executed steps are **engine-synthesised at runtime**, from no authored file. This audit establishes what they are *not*; it did not enumerate what generates them | **Medium** — the negative is solid, the positive breakdown was not attempted |

The previous audit's conclusions about coincidence are **unaffected**: its counterfactuals A and
C, which drove every conclusion, patched the MongoDB source — the one that carries 98% of
execution. D and E were null for a now-understood reason, and their null result was correct.

## Tunable Constants

None. This audit changed no constant, added no flag and landed no code.
