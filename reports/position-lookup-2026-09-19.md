# Correctness fix — hard-coded position fallbacks

`GOB_LINEUP_POSITION_LOOKUP`, **default ON**. Nine sites in `BackEnd/engine/phase_resolution.py` converted from `getattr(player, 'position', None) or "<CONSTANT>"` to an identity lookup in the lineup dict that owns the player.

**Headline: the fix is provably behaviour-neutral, and the diagnosis is the deliverable.** All nine sites are dead in the shipped configuration — eight are unreachable code, and the ninth computes a value that is never read. With the flag **ON**, the current reference reproduces **40/40 byte-identical on all four cells**. No reference re-cut. **Nothing was retuned.**

## Branch currency

`feature/animation-reward` is 20 commits behind `develop`, but `git diff --stat HEAD...develop -- BackEnd/` is **empty** — those 20 commits are entirely frontend (`FranchiseContext` routing), e2e specs and docs. I did not merge: the engine is already current and `equiv_v3_reference_456e2cdd9_reboundarrival.json` remains valid. Line numbers below are the ones in this tree; the brief's estimates had drifted by ~10–60 lines.

## Stage 1 — the nine sites

Line numbers are **pre-fix** (as found). Every one of the nine reads an **offensive** player, so the correct dict is `off_lineup` in all nine cases.

| # | line | function | source var | constant | what the position is used for | lineup in scope |
|---|---|---|---|---|---|---|
| 1 | 9090 | `resolve_half_court_offense_logic` | `ball_handler` | `"PG"` | **defender selection/credit** — `def_lineup.get(ball_handler_pos) or _fb` | `off_lineup`, `def_lineup` |
| 2 | 10080 | `resolve_full_court_press_logic` | `ball_handler` | `"PG"` | keys `pos_actions` for shooter coords; seeds `derive_passer_from_steps` | `off_lineup`, `def_lineup` |
| 3 | 10091 | `resolve_full_court_press_logic` | `shooter` | `"PF"` | same — shooter coords + passer derivation | `off_lineup`, `def_lineup` |
| 4 | 10094 | `resolve_full_court_press_logic` | `passer` | `"PG"` | `shot_roles["passer_pos"]` **and** `shot_roles["ball_handler_pos"]` | `off_lineup`, `def_lineup` |
| 5 | 10250 | `resolve_full_court_press_logic` | `ball_handler` | `"PG"` | **defender selection/credit** — `def_lineup.get(ball_handler_pos) or _fb` | `off_lineup`, `def_lineup` |
| 6 | 12224 | `resolve_half_court_trap_logic` | `ball_handler` | `"PG"` | as #2 | `off_lineup`, `def_lineup` |
| 7 | 12235 | `resolve_half_court_trap_logic` | `shooter` | `"PF"` | as #3 | `off_lineup`, `def_lineup` |
| 8 | 12238 | `resolve_half_court_trap_logic` | `passer` | `"PG"` | as #4 | `off_lineup`, `def_lineup` |
| 9 | 12387 | `resolve_half_court_trap_logic` | `ball_handler` | `"PG"` | as #5 | `off_lineup`, `def_lineup` |

**Note on #1/#5/#9:** the position describes an *offensive* player but is then used to index `def_lineup`. That is the engine's existing position-on-position matchup convention, not a bug in these sites, and I have **not** changed it — the lookup resolves against `off_lineup` (where the player lives) and the result still indexes `def_lineup` exactly as before.

### Why every one of them fired unconditionally

`Player` has **no `position` attribute**, and nothing in `BackEnd/` ever assigns one (`grep` for `\.position\s*=` outside `position_ratings`: zero hits). So `getattr(player, 'position', None)` returned `None` every time and the constant was taken on 100% of executions. This is the same root cause as the `select_foul_player` 60/40 bug fixed at `d91679bef`.

## Stage 1 step 2 — the rest of the family

Whole-`BackEnd` grep for `or "<POS>"`, `.get(..., "<POS>")` and the wider `getattr(x, 'position')` family. **Reported, not fixed.**

**Same bug, different file — worth its own pass:**

| file:line | expression | effect |
|---|---|---|
| `BackEnd/models/game_manager.py:2436` | `getattr(player,"position",None) or getattr(player,"pos",None) or "BENCH"` | always falls through to **`"BENCH"`** |
| `BackEnd/engine/foul_announcement_language.py:130-131` | `_norm(getattr(foul_player,"position",None))`, same for `ball_handler` | both always `None` — **the foul announcement's positional language is dead** |
| `BackEnd/engine/skeleton_step_emitter.py:989` | `pos = getattr(defender,"position",None)` | always `None` |
| `BackEnd/engine/covert_release_step_emitter.py:1220` | `(getattr(fb_bh,"position",None) or "").upper()` | always `""` |
| `BackEnd/utils/shared.py:2640` | `getattr(p,"position",None) or getattr(p,"pos",None)` | `.pos` also unset → `None` (no constant) |

**Different class — the lookup runs first, so the constant is a genuine last resort:**

`BackEnd/models/turn_manager.py:2638`, `BackEnd/engine/eoq_perfection.py:145`, `:736` — all `get_player_position(off_lineup, x) or "PG"`. Still worth removing, but they are only wrong when the player is genuinely off the lineup.

**Not in this family (dict-sourced or unrelated), listed for completeness:** `turn_manager.py:4564` (`gate.get("bh_pos")`), `dynamic_hct_shot.py:158/1125/1187` and `dynamic_hct_step_emitter.py:1048` (`seed.get("shooter_pos")`), `franchise_routes.py:2479/2499` (CPU reference allocation, not a lineup slot), `shot_micro_movements.py:1323` (`FAMILY_BUCKET.get(family_id, "C")` — `"C"` is a family bucket, not a centre).

`phase_resolution.py:936` keeps the legacy `getattr(...,'position',None)` **on purpose**: it is the `GOB_FOUL_ON_BALL_WEIGHT=0` kill-switch path and must reproduce the old behaviour.

## Stage 1 step 3 — the probe

`sys.monitoring` LINE + PY_START events, scoped with `set_local_events` to the three resolvers' **code objects**. Code-object events cannot be aliased around, which matters here: `turn_manager` imports FCP/HCT by name at module level, so wrapping the module attribute would have missed every real call. The callback reads `f_locals` and recomputes the identity lookup; nothing is written back.

**RNG-neutrality verified, not assumed** — the probed runs reproduce the reference exactly:

| cell | arm | fingerprint | draws | errors |
|---|---|---|---|---|
| `SEED_DEFENSES=1` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=1` | played | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | sim | **40/40** | **40/40** | 0 |
| `SEED_DEFENSES=0` | played | **40/40** | **40/40** | 0 |

### Fires per game, by site

| site | sim `SD=1` | played `SD=1` | sim `SD=0` | played `SD=0` |
|---|---|---|---|---|
| **9090** HCO non-shot ball handler | **18.02 ±1.44** | **18.20 ±1.36** | **14.25 ±1.21** | **15.35 ±1.33** |
| 10080 / 10091 / 10094 / 10250 (FCP) | **0** | **0** | **0** | **0** |
| 12224 / 12235 / 12238 / 12387 (HCT) | **0** | **0** | **0** | **0** |

**The eight FCP/HCT sites are unreachable code.** The enclosing functions run often — FCP 30.6/game, HCT 29.8/game (sim, `SD=1`) — but both return at the top:

```python
if USE_DYNAMIC_HCT:   # phase_resolution.py:11296 — a module constant, hard-coded True
    return _resolve_half_court_trap_dynamic_first_cut(...)
if USE_DYNAMIC_FCP:   # phase_resolution.py:11299 — likewise
    return _resolve_full_court_press_dynamic_first_cut(...)
```

Full line coverage of both functions confirms it: FCP executes 8 lines (9946–9960), HCT 7 lines (12092–12104), and stops. These are **not env flags** — flipping them is a source edit, so the eight sites cannot fire in any shipped configuration.

### Site 9090: fires 18×/game, and the constant is usually wrong

| cell | fires (total, 40 games) | resolved in `off_lineup` | unresolved | **`"PG"` was correct** | true slots |
|---|---|---|---|---|---|
| sim `SD=1` | 721 | 721 (100%) | 0 | **42.0%** | PG 303, SF 193, SG 177, C 29, PF 19 |
| played `SD=1` | 728 | 728 (100%) | 0 | **38.5%** | PG 280, SF 220, SG 173, C 34, PF 21 |
| sim `SD=0` | 570 | 570 (100%) | 0 | 55.3% | — |
| played `SD=0` | 614 | 614 (100%) | 0 | 53.7% | — |

So on the live site the hard-coded `"PG"` is **wrong on ~58–61% of HCO non-shot possessions** (production footing). The identity lookup resolves **100%** of them.

### …but the value is never read

The only consumer of `ball_handler_pos` in that function is line 9114:

```python
if "defender" not in roles or not roles["defender"]:
    _fb = defender_player_from_random_slot_fallback(def_lineup)
    defender = def_lineup.get(ball_handler_pos) or _fb   # 9114
```

**Line 9114 executes 0 times across all 160 probed games, all four cells.** `roles["defender"]` is always already set — by the defender-override block, or by the Seam 3 moment defender (`_hco_moment_defender_id`) landed in the HCO roles audit. So site 9090 computes a mostly-wrong position and discards it.

That is the whole reason this change cannot move a number. **It is still worth fixing** — the guard is one edit away from being false, and the next person to touch that branch would inherit a 58%-wrong value.

*(Also worth recording: `_fb` is drawn from `sim_rng` **before** the `or`, unconditionally, so even if 9114 did run, changing `ball_handler_pos` would be draw-neutral — it changes which defender is credited, not the stream.)*

## Stage 2 — the fix

`_resolve_lineup_position(player, lineup, site, legacy_constant, game)` in `phase_resolution.py`, one shared implementation behind `_lineup_position_lookup_enabled()`:

```python
if not _lineup_position_lookup_enabled():
    return getattr(player, "position", None) or legacy_constant   # the exact legacy read
pos = next((p for p, q in (lineup or {}).items() if q is player), None)
if pos is None:
    _warn_position_unresolved(site, player, game)
return pos
```

**Identity (`is`), not equality.** The existing `get_player_position` helper uses `==`; these sites use `is` so that a future `Player.__eq__` cannot silently return the wrong slot. There is a unit test for exactly that.

**Warning discipline:** one warning per `(game, site)`, keyed on `game.game_id`, in a dict bounded to the last 8 games so a long-lived process cannot grow it without limit.

### Neutral behaviour when the lookup returns None — per site

**No site falls back to a constant.** What each does instead:

| sites | on `None` | why that is the safe choice |
|---|---|---|
| **9090, 10250, 12387** (non-shot ball handler) | `def_lineup.get(None)` → `None` → **`_fb`**, the existing random-slot fallback | `defender_player_from_random_slot_fallback` is already the site's own "cannot assign a defender" path, and its draw happens either way — so this is draw-neutral |
| **10080, 10091, 12224, 12235** (shooter) | `shooter_pos` stays `None`; **the two existing guards skip** — `if shooter_pos:` (passer derivation) and `if shooter_pos and shooter_pos in pos_actions:` (coords) | shooter coords fall through to the already-written fallback `getattr(shooter, "coords", {"x":50,"y":25})`; no credit is assigned to a guessed slot |
| **10094, 12238** (passer) | `passer_pos` / `ball_handler_pos` stay `None` in `shot_roles` | **`_ensure_skeleton_shot_role_positions` then backfills them correctly** (see below) |

**The last row is the most important finding in Stage 2.** `_ensure_skeleton_shot_role_positions(game, shot_roles)` runs a few lines later and already does the right thing:

```python
if roles.get("passer_pos") is None and roles.get("passer") is not None:
    roles["passer_pos"] = get_player_position(off_lineup, roles.get("passer"))
```

…but **only when the field is `None`**. A hard-coded `"PG"` is not `None`, so the constant was *actively suppressing the correct resolver that was already sitting right there*. Returning `None` does not merely avoid a wrong guess — it hands the field back to the code that knows the answer.

### Kill switch and outcomes

`GOB_LINEUP_POSITION_LOOKUP=0` reproduces `equiv_v3_reference_456e2cdd9_reboundarrival.json`:

| cell | arm | flag | fingerprint | draws | errors | pts/team | possessions |
|---|---|---|---|---|---|---|---|
| `SD=1` | sim | **off** | 40/40 | 40/40 | 0 | 74.66 ±3.62 | 41.05 ±2.06 |
| `SD=1` | sim | **on** | **40/40** | **40/40** | 0 | 74.66 ±3.62 | 41.05 ±2.06 |
| `SD=1` | played | **off** | 40/40 | 40/40 | 0 | 74.21 ±2.89 | 39.83 ±1.91 |
| `SD=1` | played | **on** | **40/40** | **40/40** | 0 | 74.21 ±2.89 | 39.83 ±1.91 |
| `SD=0` | sim | off / **on** | 40/40 / **40/40** | 40/40 / **40/40** | 0 | 75.58 ±3.70 (both) | 43.20 ±2.28 (both) |
| `SD=0` | played | off / **on** | 40/40 / **40/40** | 40/40 / **40/40** | 0 | 75.75 ±3.43 (both) | 43.10 ±2.13 (both) |

**The flag ON is byte-identical to the reference on all four cells**, so there is nothing to re-cut: OREB share, fouls, possessions, arm gap and draws/game are unchanged by construction, not merely within CI. **`equiv_v3_reference_456e2cdd9_reboundarrival.json` stays current** and `references/README.md` is unchanged.

**Fallback-fire count with the flag on: 0.** The legacy constant is never reached. **Logged-`None` count: 0** — `[POS LOOKUP]` appears zero times across all 160 games; every lookup resolved.

## Gates

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes, flag ON) | **PASS** — 1 distinct `(fp, draws)` in every one of the four cells |
| FT-honour windowed | sim 99.8% / 99.8%; played 99.7% / 99.7% — unchanged |
| FT-honour strict | 96.0–96.6% — unchanged |
| **§8.1 coord-continuity corrections** | **0 across all 160 games, all four cells** |
| errors across 320 reference games | **0** |
| `tests/test_lineup_position_lookup.py` (new) | **65 passed** |

### Full suite, `--maxfail=1000`

| | flag ON | flag OFF |
|---|---|---|
| failed | **129** | **129** |
| passed | **2758** | **2758** |
| skipped / xfailed | 7 / 1 | 7 / 1 |

**Set diff between the two runs: empty in both directions.** Against the post-cleanup baseline in `reports/test-cleanup-2026-09-19.md` (129 failed / 2693 passed): the failing count and composition are unchanged, and passes rise by exactly **+65**, the new file. **Nothing newly failing.**

### The new tests

`tests/test_lineup_position_lookup.py` — one parametrised case per **site class** × every lineup slot (45 combinations), proving the lookup returns the slot and not the constant, plus:

- **kill switch** — `=0` returns the constant for every site class
- **identity not equality** — a player whose `__eq__` always returns `True` sitting in the PG slot must not capture a lookup for the C slot
- **absent player → `None`**, never a constant; missing/empty lineup → `None`
- **warn once per `(game, site)`**, and the next game starts clean; the warn state stays bounded
- **source guard** — an AST walk over the three resolvers asserting no `getattr(x,'position',…) or "<POS>"` BoolOp remains, **with a poison test** proving the guard fires when one is reinstated

## Footing (rule 6e)

equiv-v3 `scratch_equiv3_fbdedupe.py`, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, n=40 seeds 8000–8039, CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`. **sim arm** = `_is_full_simulation` **True** throughout; **played arm** = **False only inside the four gated Animator methods** at Pattern A.

## Not covered

- **Not merged to develop.**
- **Nothing retuned.** No constant, weight, discount or slider was touched.
- **Not fixed:** the five same-bug sites outside `phase_resolution` (table above). `foul_announcement_language.py:130-131` is the one I would take next — it is live, unlike these nine.
- **Not changed:** `USE_DYNAMIC_FCP` / `USE_DYNAMIC_HCT`. Deleting the ~600 lines of legacy FCP/HCT they strand is a separate decision.
- **Not changed:** the offense-slot-indexes-`def_lineup` matchup convention at sites 1/5/9.
