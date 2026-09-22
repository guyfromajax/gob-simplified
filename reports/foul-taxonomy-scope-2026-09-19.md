# Foul taxonomy — who should commit each kind of foul?

**Q1, the decisive question: no, the selector does not know the foul type — and the reason is worse than a missing parameter. For ~97.6% of fouls there is no foul type at all.**

`select_foul_player` receives `OFFENSE` or `DEFENSE` and nothing else, and that is not an oversight in its signature: **nothing upstream has decided a foul type either.** The taxonomy Jamie wants to route on — shooting, reach-in, illegal screen, hand-check — exists only in `foul_announcement_language.py`, as a **weighted random draw over a table of display strings, performed after the fouler has been picked**, filtered by whether the picked player happened to be the on-ball defender. And on the live paths it barely runs: the two `stamp_foul_announcement_text` call sites are inside the **legacy** `resolve_full_court_press_logic` and `resolve_half_court_trap_logic`, which this footing never reaches (the `_dynamic_first_cut` variants do), so across 160 measured games it was called **0.00 times per game**. The only live narration is `fb_terminal_announce.py`, at **~1.25 picks per game against ~52 fouls**.

So this is **not** a sequencing problem and **not** a pass-a-parameter problem. It is a modelling gap: the type does not exist to be passed, in either order. **The working thesis — "the engine frequently already knows who the culprit is" — is half right, and it is right for a different reason than expected:** the engine does not know the *kind* of foul, but for **83.3% of fouls it never asks the selector in the first place** — those paths name a specific player directly. And where it does ask, the identifying data is already in scope **100% of the time** and simply goes unused.

## Footing (rule 6e)

- **Branch `feature/animation-reward`, SHA `f833c366c`.** Read-only: nothing changed, `git diff HEAD` over tracked files empty, the only new file is this report.
- **Measured with `GOB_FOUL_ON_BALL_WEIGHT=0`**, which is the only configuration that reproduces `equiv_v3_reference_1fd08c080_zonesink.json`. **Probe integrity 40/40 on all four cells**, 0 probe errors. *Caveat that matters for reading every number below: this is the pre-fix foul distribution. The `d42696372` weighting is now on by default, so the per-position mix has shifted; the path frequencies and data-availability findings are unaffected by the flag.*
- equiv-v3 worker, Lancaster vs Bentley-Truman, sliders 2 / traps 5, `SEED_PLAYS=1`, `PYTHONHASHSEED=0`, one game per process, `ALIGN_RNG=0`, game id `0xE0000+(seed-8000)`, seeds 8000–8039 (n=40), CI = 1.96 × SEM, `SEED_DEFENSES=1` and `=0`.
- **Sim arm:** `_is_full_simulation` **True** throughout. **Played arm:** **False only inside the four gated Animator methods** at Pattern A.
- Probes: `ft/probe.py`, `ft/avail.py`, `ft/fb.py` (session scratchpad, uncommitted).

## Q1 in full: the call sites, and where the type comes from

**Every call site of `select_foul_player`:**

| line | enclosing function | team type known? | foul type known? |
|---|---|---|---|
| `9125` | `resolve_half_court_offense_logic` | yes, from `event_type` `O_FOUL`/`D_FOUL` | **no** |
| `10264`, `10299` | `resolve_full_court_press_logic` (legacy) | yes, literal | **no** |
| `11656` | `_resolve_full_court_press_dynamic_first_cut` | yes | **no** — and only called `if foul_player is None` |
| `11906` | `_resolve_half_court_trap_dynamic_first_cut` | yes | **no** — and only called `if foul_player is None` |
| `12411`, `12445` | `resolve_half_court_trap_logic` (legacy) | yes, literal | **no** |

Two of those six carry a comment that is itself the finding: *"foul_player is literal from the engine; fall back to skeleton selection only if the engine couldn't name one."* The dynamic FCP/HCT resolvers already name a culprit and treat the selector as a **fallback**.

**Tracing backwards from the announcement, as asked.** `stamp_foul_announcement_text` → `pick_defensive_foul_text` / `pick_offensive_foul_text` → `_weighted_pick` over `_DEFENSIVE_FOUL_ROWS` (7 strings) or `_OFFENSIVE_FOUL_ROWS` (7 strings), filtered by `is_on_ball`, `is_lane_foul_context` and `is_post_up_context`. The type is **invented at narration time to fit whoever was already picked.** The only exceptions are three upstream flags that short-circuit the table — `otb_foul`, `quick_foul`, `reach_in_foul` — and those *are* real types decided before the fouler.

`foul_announcement_text` is display-only; nothing gameplay-side reads it. So today the taxonomy has no mechanical consequence whatsoever.

## Q2: The foul types and their frequencies

**By the code path that chooses the culprit** (`SEED_DEFENSES=1`, n=40, per game):

| path | sim | | played | | offensive or defensive | names the culprit? |
|---|---|---|---|---|---|---|
| `shot_manager.resolve_shot` | **19.38** | 35.5% | **19.43** | 37.2% | defensive (shooting) | **yes — the contest defender** |
| `phase_resolution.resolve_non_shooting_foul` | 13.18 | 24.2% | 13.72 | 26.3% | both | **no — selector** |
| `_resolve_full_court_press_dynamic_first_cut` | 9.53 | 17.5% | 8.35 | 16.0% | both | **yes, with selector fallback** |
| `_resolve_half_court_trap_dynamic_first_cut` | 9.12 | 16.7% | 7.62 | 14.6% | both | **yes, with selector fallback** |
| `shared.resolve_offensive_rebound` | 2.02 | 3.7% | 1.75 | 3.4% | either | **yes — over-the-back proximity test** |
| `after_steal_drive_integration._resolve_shot_attempt` | 0.80 | 1.5% | 0.72 | 1.4% | defensive (shooting) | yes |
| `dynamic_hct_shot.resolve_hct_fast_break_shot` | 0.28 | 0.5% | 0.33 | 0.6% | defensive (shooting) | yes |
| `rim_runner_drive_integration.resolve_attack_drive_finisher_turn` | 0.23 | 0.4% | 0.23 | 0.4% | defensive | yes |
| `after_steal_drive_integration.resolve_after_steal_...` | 0.03 | — | 0.03 | — | defensive | yes |
| `covert_release_drive_integration...` | — | — | 0.03 | — | defensive | yes |
| **total fouls** | **54.5** | | **52.2** | | | |

**The share that actually flows through `select_foul_player`: 16.7% (sim) / 18.7% (played)** — 7.90 defensive + 1.23 offensive selections a game on sim, 7.88 + 1.88 on played. **Five fouls in six are chosen by a path that already names a player.**

**The narrated type**, for the ~2.4% that get one at all (fast-break terminal announce, 4-game sample): `Push Off!` ×2, `Hand-Checking!` ×2, `Illegal Contact!` ×1. `stamp_foul_announcement_text` fired **0.00/game** across all 160 games; the flag-driven short-circuits (`otb_foul`, `quick_foul`, `reach_in_foul`) fired **0.00/game** through that path.

**One discrepancy I did not chase, flagged rather than smoothed:** `record_stat("F")` fires **54.5/game** on sim while the box score shows **52.5** — a ~2/game gap on both arms. The attribution table above sums to the `record_stat` figure, not the box figure. I have not established where the two diverge.

## Q3: Which types already have a correct culprit?

| type | path | culprit it names | is it the right one? |
|---|---|---|---|
| **shooting foul** (35.5%) | `shot_manager.resolve_shot:1272` — `defender.record_stat("F")` | the **contesting defender**, i.e. whatever `_resolve_hco_shot_defenders` resolved from `zone_defender_assignments_by_step` (the placement stamp) | **yes.** This is the best-attributed foul in the engine: it is the defender the render actually drew contesting the shot. It never touches the selector |
| **over-the-back** (3.7%) | `shared.resolve_over_the_back_foul` | its own ≤4-unit proximity test between crasher and boxer-out | **yes** — a genuine spatial test, the only one in the foul system |
| **drive contact / charge** | `_apply_drive_contact_o_foul_charge`, run **after** the weighted draw | the **driver**, from `_hco_drive_contact_driver_id` | **yes**, and it is the existing precedent for correcting identity post-draw without moving the stream. Measured: it overrides on **0.23/game of 1.23** offensive selections (sim), 0.20 of 1.88 (played) — i.e. it fires on the ~19% of offensive fouls where the driver stash is present and the draw landed on the fabricated ball handler |
| **FCP / HCT fouls** (34.2% combined) | the dynamic first-cut resolvers | a literal `foul_player` from the engine | **presumed yes** — not audited here; the selector is only their fallback, and I did not measure how often that fallback fires |

## Q4: For the types that fall through — is the culprit identifiable?

**Yes. 100% of the time, on both branches.** Measured at the moment `select_foul_player` is entered (`SEED_DEFENSES=1`, n=40):

| | sim | played |
|---|---|---|
| **OFFENSE selections** | 49 | 75 |
| `roles["screener"]` populated | **49/49 = 100.0%** | **75/75 = 100.0%** |
| skeleton contains a `screen` action | 32/49 = 65.3% | 53/75 = 70.7% |
| — naming 1 / 2 / 3+ screeners | 15 / 17 / 0 | 24 / 24 / 5 |
| **screener identifiable either way** | **100.0%** | **100.0%** |
| drive-contact stash present | 14/49 | 14/75 |
| **DEFENSE selections** | 316 | 315 |
| `roles["defender"]` populated | **316/316 = 100.0%** | **315/315 = 100.0%** |
| `_hco_moment_defender_id` present | **0/316** | **0/315** |
| `last_stealer` set | 0/316 | 0/315 |

- **Illegal screen — the screener is identifiable on every single offensive foul.** `roles` is already a parameter of `select_foul_player`, and `roles["screener"]` is populated 100% of the time; independently, the skeleton names a `screen` action on 65–71% of them, sometimes more than one. **No signature change is needed for this one.**
- **Reach-in / steal attempt — a defender is already named on every defensive foul** via `roles["defender"]`, also already in scope. **But a caveat that must not be lost:** `roles["defender"]` is the credit-path defender, and `reports/zone-credit-diagnose-2026-09-19.md` established that it disagrees with the defender actually placed on the ball handler **87% of the time (sim)**. *Identifiable is not the same as correct.* Routing to it would give a plausible-looking name backed by a map that is known to be wrong.
- `_hco_moment_defender_id` is **never** present at selection time — it is popped at `phase_resolution.py:9046`, before the foul branch runs. Anything wanting the moment defender needs a re-sequence, not a lookup.
- **Genuinely away-from-the-play contact:** there is no flag for it and no path that produces it. On the current model it is indistinguishable from everything else in the 40% off-ball slot — roughly **3.2 defensive fouls a game** on sim. Uniform-random may well be right for those, but the engine cannot currently tell you which ones they are.

## Q5: The offensive branch

It works mechanically (it compares player objects, no `.position` involved), but the sample is small and the outcome is noisy:

| arm | ball handler picked | design | by slot (PG / SG / SF / PF / C) |
|---|---|---|---|
| sim | **24/49 = 49.0%** | 60% | 28.6 / 18.4 / 28.6 / 12.2 / 12.2 |
| played | **49/75 = 65.3%** | 60% | 36.0 / 16.0 / 25.3 / 12.0 / 10.7 |

At n=49 and n=75 both are consistent with 60%. **Is the model right? Only for some types.** The offensive foul table narrates seven kinds, and they split cleanly by natural culprit:

- **ball handler / driver**: `Push Off!`, `Arm Extension!`, `Hooking!`, `Illegal Use Of Hands!`, `Elbowing!`, `Illegal Post Up!` — the 60% weighting is defensible.
- **screener**: `Illegal Screen!` — the weighting is **wrong**, and the screener is known 100% of the time.
- **driver specifically**: the charge case, already corrected post-hoc.

The module's own docstring says it: *"Offensive fouls are always committed by the ball handler or a screener."* The code implements only the first half.

## Q6: Proposed routing table (no winner picked, nothing implemented)

| foul type | natural culprit | data needed | in scope at selection? | what it would take |
|---|---|---|---|---|
| **shooting** | contesting defender | `_resolve_hco_shot_defenders` | **already correct** — bypasses the selector | nothing |
| **over-the-back** | crasher inside 4 units | own proximity test | **already correct** | nothing |
| **charge / drive contact** | the driver | `_hco_drive_contact_driver_id` | yes, 14/49 offensive selections | **already correct** (post-draw override) |
| **illegal screen** | the **screener** | `roles["screener"]` | **yes — 100%** | **no signature change.** Needs a *type* to exist so the branch knows to route there — i.e. decide "this is a screen foul" before the draw |
| **reach-in / on-ball steal attempt** | the on-ball defender | `roles["defender"]` (unreliable) or the placement stamp (reliable) | yes, 100% — but wrong 87% of the time | fix the credit map first (queued), or read `zone_defender_assignments_by_step` directly |
| **away-from-play** | genuinely unknown | — | n/a | **uniform-random is defensible here**; the engine just cannot identify which fouls these are |
| **FCP / HCT** | engine-literal | already named | **already correct** | audit the fallback rate |

**The prerequisite that gates every row: a foul type has to be decided before the fouler is picked.** Today it is either absent (97.6%) or invented afterwards. Three flags (`otb_foul`, `quick_foul`, `reach_in_foul`) already prove the pattern works — they are decided upstream and short-circuit the narration. Extending that to a genuine type enum, set at the point the foul is *caused*, is the change this whole table depends on; everything else is then a lookup against data already in scope.

**Blast radius, unchanged from the last pass:** fouls drive foul-outs, substitutions and lineups, so any change here moves outcomes on **both arms**, and byte-equality will not hold. The last foul fix moved sim pts/team by **−3.84** and flipped the arm gap from **+4.10 to −1.39** — and that was a change that consumed *the same number of draws*. A type-routing change would be larger.

## Not covered

- **Nothing was changed.** No commits except this report; no retuning. Fouls still run 25–30 per team per game against ~17.5 in D1 — reported, not adjusted.
- `select_foul_player`'s behaviour, the 60/40 weights and `foul_is_on_ball`: untouched.
- The credit path, the overlap rule, the three-way gap, and the nine `or "PG"` / `or "PF"` constant-position sites: all still queued, **not traced here**.
- The sink, the rings, the ladder, the crash flags, `animator.py:1213`, the `randint(1,6)`, the rebound path, R1, R2: untouched.
- **Not measured:** how often the FCP/HCT `if foul_player is None` fallback actually fires — i.e. what share of that 34.2% really is engine-named versus selector-picked. That is the single biggest remaining unknown in the Q2 table.
- **Not resolved:** the ~2/game gap between `record_stat("F")` calls (54.5) and box-score `F` (52.5).
- **Not audited:** whether the FCP/HCT engine-literal culprits are the *right* players, only that they exist.
- All frequencies are from the **pre-fix** configuration (`GOB_FOUL_ON_BALL_WEIGHT=0`), the only one that reproduces the current reference.
