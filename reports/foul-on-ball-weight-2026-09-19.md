# The dead 60/40 defensive foul weighting — fixed, measured

**Lead: the fouler distance barely moved, and that is the most important result here.**

| distance from the selected fouler to the ball handler, `SEED_DEFENSES=1`, n=40 | n | median | mean | p90 | max | **>20 units** |
|---|---|---|---|---|---|---|
| sim, **before** | 316 | 15.7 | 19.4 | 38.5 | 80.0 | **39.9%** |
| sim, **after** | 319 | **15.3** | 18.8 | 36.7 | 80.0 | **35.7%** |
| sim, after — the on-ball 60% | 189 | **15.2** | 18.0 | 36.4 | 80.0 | 30.2% |
| sim, after — the off-ball 40% | 130 | 16.0 | 20.0 | 38.6 | 68.6 | 43.8% |
| played, **before** | 315 | 16.2 | 19.1 | 36.4 | 78.5 | **41.0%** |
| played, **after** | 296 | **14.8** | 17.8 | 36.4 | 76.0 | **33.4%** |
| played, after — the on-ball 60% | 185 | **14.1** | 15.9 | 36.4 | 60.7 | 24.3% |
| played, after — the off-ball 40% | 111 | 18.7 | 20.9 | 38.4 | 76.0 | 48.6% |

The on-ball and off-ball halves do separate — 15.2 vs 16.0 on sim, 14.1 vs 18.7 on played — so the weighting is doing something real. But **the "on-ball" defender is still a median 14–15 grid units from the ball handler, and a defender 80 units away is still being blamed.** The reason is structural and was not visible before the fix ran: `select_foul_player`'s notion of "on-ball" is *the defender occupying the same lineup slot as the ball handler* — a **positional-label match, not a spatial one**. In a zone the PG-slot defender is frequently nowhere near the PG-slot offensive player. **The fix makes the intended rule run; it does not make the intended rule good.**

**Per-position foul distribution — the fix's actual point — did land.** From `select_foul_player` directly (`SEED_DEFENSES=1`, n=40):

| arm | | PG | SG | SF | PF | C |
|---|---|---|---|---|---|---|
| sim | before | 18.7% | 20.9% | 19.3% | 19.6% | 21.5% |
| sim | **after** | **32.6%** | 26.0% | 18.8% | 12.5% | **10.0%** |
| played | before | 20.6% | 22.9% | 16.8% | 19.7% | 20.0% |
| played | **after** | **36.5%** | 23.3% | 23.3% | **7.1%** | 9.8% |
| — | ball-handler position mix (both) | ~46% | ~26% | ~23% | ~2% | ~2% |

Before: flat at ~20% each, which is the 1-in-5 uniform signature. After: it tracks the ball-handler position mix, as designed — guards foul more, bigs foul less.

## Footing (rule 6e)

- **Branch `feature/animation-reward`**; fix at `d42696372` (flag OFF), flipped at `4df7a87b4`.
- **Worker:** equiv-v3 `scratch_equiv3_fbdedupe.py`. Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- **Flag-off integrity: 40/40 identical to `equiv_v3_reference_1fd08c080_zonesink.json` on all four cells**, 0 probe errors across 320 measured games + 12 gate games.
- Probe: `fw/probe.py` (session scratchpad, uncommitted).

## The fix

`Player` defines **no `__eq__` and no `__hash__`**, so `==` already means identity. The lookup uses `is` anyway, because it states the intent and survives anyone adding `__eq__` later:

```python
            ball_handler_pos = next(
                (pos for pos, p in (off_lineup or {}).items() if p is ball_handler),
                None,
            )
```

The lineup is authoritative for position, and `off_lineup` was already a parameter. This is the same pattern as the existing `covert_release_step_emitter.py:1215`, whose comment already says to resolve position "from lineup (authoritative), not from Player.position" — that site got it right and this one did not.

**`foul_is_on_ball` was a second dead path in the same feature, fixed in the same commit.** It was stamped via `defensive_foul_is_on_ball`, which compares `foul_player.position` to `ball_handler.position` — **both always None** — so it returned False on **100%** of defensive fouls and the announcement copy always picked off-ball language. It is now stamped from what `select_foul_player` itself knows (`foul_player is matched_defender`). Measured: **0.0% → 59.2% (sim) / 62.5% (played)** true.

## Verification that the fix fires

| arm | | selections | matched defender resolves | **matched defender picked** | `foul_is_on_ball` true | BH missing from `off_lineup` |
|---|---|---|---|---|---|---|
| sim | before | 316 | 100.0% | **18.0%** | 0.0% | 0 |
| sim | **after** | 319 | 100.0% | **59.2%** | 59.2% | 0 |
| played | before | 315 | 100.0% | **19.7%** | 0.0% | 0 |
| played | **after** | 296 | 100.0% | **62.5%** | 62.5% | 0 |

- **"Matched resolves 100%" in the *before* column is the proof of the bug, not a contradiction.** That column is my probe re-deriving the position from `off_lineup` independently — it always worked. Production simply was not using it. The 18.0% / 19.7% pick rate is the 1-in-5 uniform rate: the weighting genuinely never ran.
- **59.2% / 62.5% against an intended 60%** — the weighting now fires at the designed rate.
- **The `off_lineup` fallback never fired: 0 of 631 selections.** The logged uniform fallback for substitution edge cases exists but has no live traffic in this footing. That is a clean finding, not a silent gap.

## Draws: in phase at the call site, divergent downstream

The brief asked which of the two it is. **Both, and the distinction matters.**

| arm | draws inside `select_foul_player` | calls | draws per call |
|---|---|---|---|
| sim, before | 9.1/game | 9.1 | **1.00** |
| sim, after | 9.4/game | 9.4 | **1.00** |
| played, before | 9.8/game | 9.8 | **1.00** |
| played, after | 9.2/game | 9.2 | **1.00** |

`random.choices` consumes **exactly one draw per call regardless of weights**, so the call site is draw-neutral and the stream stays in phase *there*. Total draws still move (sim −937, played −826 on `SEED_DEFENSES=1`) because a **different player fouls**, which changes foul-outs, lineups and the rest of the game. Nothing else changed: the divergence is the intended cascade, not a second edit.

`fp` match before vs after: **4/40 on `SEED_DEFENSES=1`** (both arms), 0/40 on `=0`. The four identical seeds are games where no defensive foul selection happened to land differently.

## Outcomes — this changes the game, and by more than a label fix implies

**`SEED_DEFENSES=1` (production), n=40:**

| metric | sim before | sim after | Δ | played before | played after | Δ |
|---|---|---|---|---|---|---|
| **pts/team** | 75.66 ±3.40 | **71.83 ±3.25** | **−3.84** | 71.56 ±2.60 | **73.21 ±2.39** | +1.65 |
| team fouls | 26.27 ±1.37 | 25.05 ±1.27 | −1.22 | 25.77 ±1.11 | 25.64 ±1.11 | −0.14 |
| **foul-outs** | 2.88 ±0.66 | 2.65 ±0.54 | −0.23 | 3.00 ±0.54 | 2.90 ±0.59 | −0.10 |
| FTA | 26.43 ±2.36 | 23.86 ±1.94 | −2.56 | 25.52 ±1.77 | 25.84 ±1.89 | +0.31 |
| FG% | 46.53 ±1.93 | 44.62 ±2.16 | −1.91 | 43.96 ±1.84 | 44.96 ±1.77 | +1.00 |
| possessions | 42.67 ±1.88 | 44.15 ±2.29 | +1.48 | 43.90 ±1.95 | 44.55 ±1.97 | +0.65 |
| draws | 70,464 ±1,107 | 69,528 ±1,012 | −937 | 81,711 ±747 | 80,885 ±769 | −826 |
| **arm gap** | **+4.10 ±4.25** | **−1.39 ±3.46** | | | | |

**`SEED_DEFENSES=0` — not a control here, and it moves as expected.** `select_foul_player` runs on man defence too, so this column was never going to hold, and it did not: team fouls **+0.94 (sim) / +1.04 (played)**, foul-outs **+0.77 (sim) / +0.23 (played)**, FTA **+1.02 / +2.61**, pts/team +0.30 / +1.50. **This is not a leak into the man path — it is the man path, correctly affected.**

**Box-score fouls by lineup slot** (starters at the final buzzer) move much less than the selector distribution does — sim PG 23.7% → 25.2%, C 18.2% → 14.5%; played SG 21.9% → 26.4%, PF 16.2% → 13.7%. The selector's distribution is sharply concentrated but the box score dilutes it, because bench players absorb fouls once starters sit and the slot labels are a buzzer-time snapshot (see `reports/boxscore-display-2026-09-18.md`).

**Substitution churn is not reported.** The census counter `substitutions_hco` reads 0.00 on `SEED_DEFENSES=1` and ~60 on `=0` in both before and after, which is a census-scope quirk rather than a game difference, so I have no trustworthy churn number. **Foul-outs are the honest proxy** and they moved very little (−0.23 / −0.10 on the production footing).

**Nothing was retuned.** Fouls still run 25–30 per team per game against ~17.5 in D1. This fix **redistributes** fouls; it does not reduce them. Flagged, not adjusted.

## Gates

| gate | result |
|---|---|
| independence (seed 8000 × 3 processes) | **PASS** — both arms, both footings |
| FT-honour windowed | sim 99.5% / 99.6%; played 99.6% / 99.6% |
| FT-honour strict | 95.4–96.3% |
| errors, 320 measured + 12 gate games | **0** |
| flag-off reproduces the reference | **40/40 on all four cells** |

**`equiv_v3_reference_1fd08c080_zonesink.json` no longer describes the default tree** — only `GOB_FOUL_ON_BALL_WEIGHT=0` reproduces it. This brief did not ask for a re-cut, so I have not cut one; it is the obvious next action before anything else lands.

## The `.position` family — checked, not fixed

This attribute has now caused **three** defects (box-score labels, the foul weighting, and `foul_is_on_ball`). It is a family, not a pair. **16 non-test reads** of `getattr(<player>, "position")` exist:

| file:line | read | consequence |
|---|---|---|
| `engine/phase_resolution.py:883` | `ball_handler.position` | **fixed in this pass** |
| `engine/foul_announcement_language.py:130`, `:131` | fouler / BH position | **routed around in this pass**; the function itself is still dead |
| `engine/phase_resolution.py:9081` | `... or "PG"` | **always "PG"** |
| `engine/phase_resolution.py:10071`, `:12220` | `ball_handler ... or "PG"` | **always "PG"** |
| `engine/phase_resolution.py:10082`, `:12231` | `shooter ... or "PF"` | **always "PF"** |
| `engine/phase_resolution.py:10085`, `:12234` | `passer ... or "PG"` | **always "PG"** |
| `engine/phase_resolution.py:10241`, `:12383` | `ball_handler ... or "PG"` | **always "PG"** |
| `engine/skeleton_step_emitter.py:989` | `defender.position` | always None |
| `engine/covert_release_step_emitter.py:1220` | `fb_bh.position` | always None — but that site **already resolves from the lineup first** and only falls back here, so it is correct |
| `models/game_manager.py:2432` | `player.position` | always None → the `BENCH_<id>` labels; established as not player-visible |
| `utils/shared.py:2585` | `player_obj.position` | always None → a `pos` field in a payload |

**Nine of the sixteen have a hard-coded `or "PG"` / `or "PF"` fallback**, which means they are not merely returning None — they are silently returning a **constant position** on every call. Whether any of those nine matters depends on what consumes them, which I did not trace. That is the shape of the next question, and it is bigger than this pass.

## Not covered

- The credit path, the overlap rule, the three-way gap and the guard map: **untouched and not pre-empted.**
- The sink, the rings, the ladder, the crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1, R2: untouched.
- **No retuning.** The foul rate is reported and left alone.
- The nine `or "PG"` / `or "PF"` sites are **inventoried, not traced and not fixed**.
- `defensive_foul_is_on_ball` is now bypassed for defensive fouls but still exists and is still broken for any other caller.
- Substitution churn: no trustworthy measurement, stated above rather than estimated.
- References were **not** re-cut.
