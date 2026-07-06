# FG% Tuning

**Goal:** FG% ≈ 46%, 3PT% ≈ 40%. Regressed after UESS-compliance pass — coord tracking now produces too many undefended shots, and defended-shot make % also rose.

The shot logic is **mostly shared but not fully** — three turn types funnel through one function, three have their own copies.

## 1. Defended vs Undefended
**Criteria = a defender is within Euclidean distance of the shooter.**

- Constant: `CONTEST_EUCLIDEAN_RADIUS = 11` (`BackEnd/constants/__init__.py:307`)
- Core test (HCO / Fast Break / Final Shot): `math.hypot(dx, dy) <= 11` → contested (`BackEnd/models/shot_manager.py:801-807`)
- **HCT / FCP** add a rule: within radius **AND** defender not trailing >3 spots behind on x-axis (`FB_CONTEST_MAX_X_TRAIL = 3`) (`BackEnd/utils/fast_break_shot_geometry.py:162-173`)
- **OREB** is the odd one: nearest defender is **always** the contester, so putbacks are essentially always "defended" (`BackEnd/utils/shared.py:841-868`)

## 2. Made vs Missed
**Core rule = `shot_score` vs `shot_threshold`.** Defense is folded into the score (defended shots subtract defense; undefended don't).

- Central: `made = shot_score >= shot_threshold` (`BackEnd/models/shot_manager.py:1358-1364`)
- **Two big undefended shortcuts** (likely inflated undefended make %): unguarded rim and "motion uncontested" both hard-code **~99% make** via `random.randint(1,100) != 100` (`shot_manager.py:893-895`, `:922`)
- Undefended **outside** shots use a bespoke bar instead of the normal threshold: `made = shot_score > SHOT_THRESHOLD_MAX - CH + dist_to_rim` (`shot_manager.py:1358-1361`) — always tracks the shot-threshold scale MAX (now **250**; was hardcoded 210→230, now wired to the scale so it moves with retunes)

## Shared vs separate (matters for the regression)
| Turn type | Contest logic | Make/miss |
|---|---|---|
| HCO, Fast Break, Final Shot | shared `resolve_shot` (radius 11) | shared `resolve_shot` (incl. 99% shortcuts + undefended-outside bar) |
| HCT, FCP | own: radius 11 + x-trail ≤ 3 | own `dynamic_hct_shot.py` — **no** undefended-outside bar |
| OREB | nearest defender always | inline in `shared.py` — 99% if uncontested |

## Final Shot / FLSS make/miss
"Final Shot" is **two different paths** — only one is a true buzzer-heave.

| Path | When | Make/miss rule |
|---|---|---|
| **Base Final Turn** | normal end-of-clock shot completes in time | Standard `resolve_shot` — same as HCO (undefended-outside bar, rim-99%, else `score >= threshold`). `final_turn=True` but **no** heave/time penalty. (`phase_resolution.py:6296`) |
| **FLSS – normal** (closest x-band) | base turn can't finish → reroute; shooter near enough | Standard `resolve_shot` with `roles["flss"]=True`, **no** penalty (`eoq_perfection.py:616`) |
| **FLSS – penalty** (mid x-band) | reroute, mid-range | `resolve_shot` **minus** `flss_penalty = 100 − (team_chem + CH/5)` from `shot_score` (`eoq_perfection.py:600-603`, `shot_manager.py:959-961`) |
| **FLSS – heave** (deepest x-band) | reroute, far from basket | **Bypasses `resolve_shot`** entirely — desperation formula: `shot_score = (CH − dist) / rand(1,6)`; `made = shot_score > rand(1,100)`; 3pt if `dist > 40` (`eoq_perfection.py:381-390`) |

- Reroute trigger: pacing can't hit the anchor before clock 0 → `route_flss` (`phase_resolution.py:6187-6189` → `turn_manager.py:3919` → `eoq_perfection.resolve_flss_shot_logic:393`)
- Zone (normal/penalty/heave) is derived purely from shooter x-position at buzzer (`classify_flss_zone`, `eoq_perfection.py:67-82`)
- Generic forced-shot −100 penalty is **skipped** for FLSS (guarded by `not roles["flss"]`, `shot_manager.py:956`)
- **Diagnostics:** Final Turn / FLSS-normal / FLSS-penalty count in `shot_split_tracking` (make/miss split) but are **excluded** from `fga_by_turn_type` (classify → `None`). FLSS-**heave** is in **neither** tally (never reaches `resolve_shot`; records only raw FGA/3PTA).

## Two leads for the symptoms
- **(a) Too many undefended shots** → the radius-11 contest test is missing defenders now that coords changed.
- **(b) Defended makes rising** → inside `calculate_shot_score`'s defense subtraction (`shot_manager.py:2606`), not yet opened.
