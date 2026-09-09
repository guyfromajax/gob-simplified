# bugs.md — Archive (resolved, superseded, retracted)

**Split out of `bugs.md` on 2026-09-04.** Everything here is CLOSED: fixed, measured and
rejected, retracted, or superseded by a later entry. Kept because the reasoning is worth
more than the conclusion — several of these record *why not to try something again*.

Open work lives in [`../bugs.md`](../bugs.md) and
[`../animation_worklist.md`](../animation_worklist.md).

---

## Resolved — stale Final Turn test import (found 2026-08-04, fixed 2026-08-11)

`test_final_turn_entry_pass_chain.py` was repointed from the retired
`_append_final_turn_entry_pass_if_needed` helper to the current
`_prepend_final_turn_handoff_if_needed` path. Its monotonic/no-self-loop contract remains
covered. The separate `roll_anchor_clock` debt was resolved earlier.

---

### `PYTHONHASHSEED` reaches simulation behaviour — game results depend on an unrecorded value (August 2026)

- **Finding:** with `sim_rng` AND the stdlib `random` both explicitly seeded per quarter, repeated
  runs of the same sim still produced different results — until `PYTHONHASHSEED=0` was set, after
  which two runs were **bit-identical** (results and RNG draw counts alike).
- **Implication:** something on the sim path iterates a `set` or `dict` of strings in an order that
  reaches behaviour. Python randomises string hashing per process by default, so **live game results
  depend on a per-process value that nobody sets, controls, or records.**
- **Why this is not just a test problem:** it means a production game is not reproducible even given
  the same seed, and any seeded investigation is only valid within a single process. It undermines
  SS&S reproducibility guarantees generally.
- **Same class as the pymongo global-stream finding** documented in `BackEnd/utils/sim_random.py`:
  an invisible external input perturbing the simulation. That one was fixed by isolating the RNG;
  this one is still open.
- **Likely fix (when authorized):** find the offending iteration (candidates: any `set` of position
  or player-id strings feeding ordered logic, `_step_locations`, read-map construction, defender
  grids) and impose a deterministic order — `sorted()` at the point of use. Pinning
  `PYTHONHASHSEED` in the runtime would mask it, not fix it, and would not help anyone reading a
  historical game.

#### PARTIAL FIX + method to finish it (August 2026)

**12 genuine hash-order dependencies found and fixed.** Each was a raw `set` iteration whose
order reached RNG draw ORDER, so every subsequent draw in the game shifted:

| file | what |
|---|---|
| `engine/attack_drive_clearance.py:1012` | `for off_pos in perimeter_moved` — set from `_apply_perimeter_relocations`; loop consumes `player_read` + `get_defender_coords` draws per element. **The primary site.** |
| `models/animator.py:1294` | `for position in all_positions` — set; sets `offensive_animations` insertion order, which flows into zone overlap resolution |
| `engine/dynamic_hct.py:1162` | `backcourt` was a set literal → now a tuple |
| `engine/dynamic_hct_step_emitter.py:273`, `utils/shared.py:2543`, `utils/transition_bridge.py:312`, `utils/stat_updater.py` ×4, `utils/playbook_weights_utils.py:245`, `models/training_execution_v2.py:268` | raw set iteration, now `sorted(..., key=str)` |

**Causally confirmed**: the first divergence between hash worlds moved 9,051 → 23,677 →
31,023 draws as sites were fixed, and `PYTHONHASHSEED` 0 and 7 now produce **identical** games
(they did not before).

**STILL NOT FIXED.** Seeds 1 and 2 still diverge. On the identity-ON arm, 96 team-games, the
between-seed spread is **points/tg 69.22–70.58 and FCP foul-outs/tg 1.04–1.35** — comparable
to the effects being measured. **The instrument is still not trustworthy for effects of this
size.** Until it is, pin `PYTHONHASHSEED` for every arm of every comparison.

**Next site**: the OREB rebounder selection. Trace shows identical RNG state through draw
31,022, then `mo_shot_roll` takes a different branch (`player_momentum.py:54` vs `:57`) via
`shot_manager.calculate_shot_score` ← `shared.resolve_offensive_rebound` ← 
`turn_manager.resolve_offensive_rebound_turn:5252`. Same draws, different rebounder — so the
selection is order-dependent, most likely a `max()`/`min()` tie broken by iteration order
rather than a raw set iteration (the static scan for those is now clean).

**Method to continue** (`scratchpad/hashfind.py` + `nextdiv.sh`): wrap every `sim_rng` method
to record the caller's `file:line` per draw; run one game under two hash seeds; diff the
call-site sequences to find the first differing draw index; re-run with deep stacks in a
±2 window around it. That names the function in two passes.

#### AUDIT — which earlier results were affected

The rule: **arms compared WITHIN one process share that process's hash seed and are valid;
arms run as separate invocations are not.**

| harness | structure | verdict |
|---|---|---|
| `w_sweep.py` | `for w in WS` inside one process | **valid** |
| `read_test.py` | `CONFIGS` looped in-process | **valid** |
| `lineup_analyze.py`, `gates.py` | no per-arm invocation | **valid** |
| `head2head.py`, `lineup_diag.py` | `argv[1]` is games count, single config | **valid** (absolute values are one hash world) |
| `slider_ab.py` | `ARM = sys.argv[1]` — one arm per process | **INVALID across arms** |
| `difficulty.py` | `TAG = sys.argv[1]` — one arm per process | **INVALID across arms** |
| `foul_levers.py` | one arm per process | **INVALID** as originally run; later re-run pinned |

No harness set `PYTHONHASHSEED` internally. The lineup diagnostics and gate sweep are
structurally fine; the slider A/B and difficulty comparisons should be re-run pinned before
being quoted again.

---

### MEASURED, NO EFFECT FOUND: archetype-varying objective weight `w` (2026-08-12)

**The second attempt at archetype-driven substitution, and the second one that does not pay.**

After the hysteresis pair below was rejected, `cpu_identity_design.md` §B3's archetype idea
was redirected from the NG gate to the selector objective weight `w`
(`score = w·static + (1−w)·effective`), which `db_utils.py:176` already names as *"the
intended home for archetype influence (via starter_bench_gap)"*. That redirect was right in
principle — `w` changes who the selector considers better rather than holding anyone past a
gate — but the effect is not there.

**The hypothesis, stated precisely.** `c2570c5aa` swept `w` LEAGUE-WIDE and found lower is
better (every value beat `w=1.0`; >10 effective-talent gap 20.8% → 0.7% going 1.0 → 0.25).
The spec wants `w` to go UP for top-heavy rosters. That is only defensible if the optimum
DIFFERS BY ROSTER SHAPE and the league-wide sweep averaged the difference away. So the test
is not "is high `w` good" — it is **"does the optimum differ by band."**

**Method** (`scripts/lineup_w_conditional_sweep.py`, read-only): within-game pairing — one
team gets `w=0.60`, its opponent `w=0.05`, same seed/venue/opponent, with the high arm
alternating home/away. One observation per GAME (the design is zero-sum, so per-team-game
arms are perfect negatives and a two-sample SE over them is meaningless). Matchups restricted
to a single `starter_bench_gap` band, because the bands are 96/23/9 teams and random pairing
spends ~93% of games where the answer is already known.

| gap band | games | high-`w` margin | SE | \|t\| |
|---|---|---|---|---|
| top-heavy (>19) | 32 | **−1.56** | 2.70 | 0.6 |
| shallow (<13) | 32 | **−1.22** | 2.50 | 0.5 |

**Verdict — no conditional effect.** The spec predicts these bands should have OPPOSITE
signs. They have the same sign, similar magnitude, and differ by **0.34 points — about
one-eighth of a single SE**. Both are consistent with the league-wide result that lower `w`
is better; neither supports varying it by roster shape.

**Honest limits.** 32 games/band cannot resolve a ~1.5-point effect on its own (|t| ≈ 0.5–0.6),
so this does not *prove* no effect. What it does is bound the conditional effect as small and
provide zero support for its existence, against a prior that already measured higher `w` as
worse. Single franchise, week-2 rosters, two `w` arms rather than a full sweep.

**Where `starter_bench_gap` came from.** It is not defined anywhere in the codebase — only
named in the `db_utils` comment. The sweep defines it as the mean over the five lineup slots
of (best static slot rating − second best). Static not effective (it is a roster property,
not a fatigue state); second-best per slot not "the bench" (that is who actually replaces the
starter); mean not max (one thin position should not read as top-heavy). Observed on the
identity league: min 2.0, max 29.2, mean 11.1 — so the spec's 13/19 band edges put **75% of
the league in one bucket** and were evidently cut against a different population, the same
failure as the `RT ≥ 50` bar and the frozen `SIGNAL_SCALE` constants.

**When to revisit:** a different `w` grid is not the answer — the league-wide sweep already
mapped that curve and it is monotonic. Like hysteresis, the case for reopening is a change to
the **fatigue economy**, not a better parameter.

---

### MEASURED AND REJECTED: NG pull/return hysteresis pair (August 2026)

Implemented, swept, head-to-head'd, then **stripped** rather than left as inert plumbing —
this project has surfaced four orphaned mechanisms already, and shipping the scaffolding for
a rejected one is the same pattern. Recording the results so the work isn't lost.

**What it was:** replace the single `NG >= 0.80` eligibility gate with a pair — a player ON
THE FLOOR stays eligible until NG < PULL, and once benched cannot return until NG >= RETURN.
The late-game relaxation (0.64 in the final 4:00 of Q4/OT) composed multiplicatively
(factor 0.64/0.80) against BOTH ends, so `(0.80, 0.80)` reproduced the old behaviour exactly.

**Sweep (16 games per pair, w = 1.0 so only the gate moved):**

| pull/return | star min% | stint mean | subs/rebuild | floor NG mean | floor NG min |
|---|---|---|---|---|---|
| 0.80/0.80 (control) | 40.5%* | 1.21 | 4.01 | 0.879 | 0.600 |
| 0.75/0.85 | 40.5%* | 1.41 | 3.37 | 0.852 | 0.520 |
| 0.70/0.90 | 40.5%* | 1.46 | 3.21 | 0.842 | 0.510 |
| 0.65/0.90 | 41.4%* | 1.58 | 2.94 | 0.824 | 0.450 |
| 0.60/0.95 | 41.0%* | 1.71 | 2.68 | 0.805 | 0.420 |

\* these star-minutes figures are VOID — see the metric warning in
`06_Gameplay_Systems/CPU_Team_Rotation_System.md`. The *relative* flatness across pairs is
still informative (the defect was constant across arms); the absolute level is not.

**Head-to-head vs (0.80, 0.80), 32 games each, both directions:**

| pair | record | win% | SE | mean margin |
|---|---|---|---|---|
| 0.75/0.85 | 14-18 | 43.8% | +/-8.8 | **-1.81** |
| 0.70/0.90 | 15-17 | 46.9% | +/-8.8 | **-1.66** |
| 0.65/0.90 | 16-16 | 50.0% | +/-8.8 | -0.56 |

**Verdict — rejected.** Three findings:
1. **Churn improves genuinely** — substitutions per rebuild fall 20-33%, mean stint length
   rises 41%. This is the only real benefit, and it is cosmetic.
2. **It costs about a point a game.** No pair beat the control; all three margins are
   negative. Mechanically unsurprising: holding a tired player past PULL is by construction
   fielding someone worse than the best available alternative.
3. **It does not move star minutes at all** (flat across every pair). Star minutes are an
   equilibrium of the fatigue economy — on-floor decay ~0.015/possession
   (`_ND_DECAY_TIERS`) against bench recovery ~0.009/possession
   (`phase_resolution.py` bench recharge) — not a property of the thresholds. Widening
   hysteresis buys a longer stint and pays for it with a proportionally longer rest.

**When to revisit:** only if the FATIGUE ECONOMY changes. In a slower-decay world long
stints may arise without paying a point a game for them, at which point hysteresis might be
unnecessary rather than merely unprofitable. **Do not revisit by searching for a better
threshold pair** — the sweep covered 0.60-0.80 pull against 0.80-0.95 return and the shape
was monotonic throughout: more hysteresis, less churn, more exhaustion, same minutes.

---

### `.env.local` resolved against CWD, silently retargeting production — FIXED

- **Was:** `BackEnd/db.py` chose its env file with `os.path.exists(".env.local")`, relative to the
  **working directory**. Any script run from a subdirectory failed to find it, fell through to
  `.env`, and connected to prod. One instance of a class, not a one-off.
- **Incident:** a sim harness run from a scratch directory rewrote `position_ratings` on **192
  prod player documents across 16 teams** with the recalibrated formula, while prod runs a
  pre-recal formula. Deltas up to 38 rating points. Only that field changed — `attributes`,
  `height` and `name` verified untouched.
- **Now:** resolved against the repo root (`Path(__file__).resolve().parent.parent`).
- **Plus a production access guard** in the same file: reaching `gob` requires an explicit
  per-invocation opt-in, `GOB_DB_ACCESS=read` or `=write`, read from the **real process
  environment snapshotted before dotenv load** — so it cannot be armed from a committed `.env`.
  The deployed app is recognised by any `RAILWAY_*` variable. Unrecognised process → refuse at
  import. `aggregate()` is deliberately not blocked in read mode, so `$out`/`$merge` can still
  write; tighten if that becomes a real path.

---

## EOG leveling pass (August 2026) — follow-ups

### RESOLVED + ESCALATED: the fight / discipline drift owner (August 2026)

**Diagnosed. Two of the three candidates are closed; a bigger one opened.**

**(b) reset/rollover artifact — RULED OUT.** The per-week training delta is SPREAD EVENLY
across all 26 weeks, not spiked. `fight` runs +0.4..+2.0 every week, `discipline` -0.4..-3.6;
the top three weeks hold only 20% and 29% of total movement. Controls
(`offensive_efficiency`, `fb_efficiency`, `shot_threshold`, `team_chemistry`) are equally
smooth, top-3 concentration 15-16% — so §2b is NOT absorbing large one-off EOS/camp writes
into the training column for any attribute.

**Persona coupling — RULED OUT TWICE OVER.** The nudges are equal in magnitude (±1.5 mean) and
fire at 4-of-5 sub-options each way, so they cancel at uniform selection. And they never fire
at all for CPU teams: `auto_train_one_cpu_team` pins `coaching_focus = "player-maximizer-custom"`,
so the archetype is ALWAYS `player-maximizer`. The culture-builder / authoritarian branches are
dead code on the CPU path, and 127 of 128 teams are CPU.

**(a) the CPU reference plan — CONFIRMED OWNER for fight/discipline.** Measured directly via
`auto_train_one_cpu_team(..., dry_run=True)` over 40 teams (all pymongo writes blocked; zero
write attempts):

| attribute | reference plan | §2b inferred | verdict |
|---|---|---|---|
| team_chemistry | -11.7 | -10.2 | ✅ fully explained |
| offensive_efficiency | +7.2 | +7.5 | ✅ fully explained |
| fight | **+16.2** | +27 .. +32 | direction right, ~60% of magnitude |
| discipline | **-24.1** | -35 .. -48 | direction right, ~60% of magnitude |
| **shot_threshold** | **+1.3** | **+51.4** | ❌ **40x GAP — NOT TRAINING** |

The fight/discipline residual is plausibly estimator bias: §2b conditions on BOTH endpoints
unclamped, which progressively drops teams that have drifted to the clamp and leaves only
small-delta survivors (visible as `discipline` decaying -3.55 at wk2 to -0.44 at wk14). That
biases the estimate DOWNWARD, so the true drift is probably larger than either figure.

**Action for fight/discipline:** the owner is the reference plan's drill->team-attr mapping
(`training_execution_v2.py:607-617` — discipline draws 0.25x from four categories, fight 0.5x
from two). Retune there, not in the EOG bands.

### ⚠️ RETRACTED: "shot_threshold has an unidentified writer" — it was a measurement error

**There is no mystery writer.** The claim came from a dry-run measurement taken against
END-OF-SEASON state where **123 of 128 teams sat at the 200 ceiling**, so every training gain
was clamped to zero and the plan appeared to produce +1.3/season. Re-measured with attributes
reset to mid-range, the SAME reference plan produces **+60.5/season** against §2b's +51.4 —
fully explained by training. Only three writers touch team attributes (EOG apply, CPU
auto-train, user training) and that is correct.

Also note: the "nothing in week 1" signal that motivated the hunt is an artifact. The training
delta is computed as `pre[w] - post[w-1]`, so week 1 has no value BY CONSTRUCTION. It is not
evidence of a state-dependent writer.

### (superseded by the entry above) Original fight/discipline ticket

**Measured on the identity season:** `fight` **+32.0**/season and `discipline` **−48.1**/season
from TRAINING, against EOG contributions of **+0.6** and **+14.0**. Training dominates both, so
their EOG bands were left DELIBERATELY UNTUNED in the leveling pass — compensating via EOG would
require perverse bands (see below). Revisit the bands only after this is settled.

**The persona coupling is NOT the cause — this was checked and ruled out.**
`_apply_player_training_points` (`training_execution_v2.py:745-767`) looks asymmetric but is not:

| nudge | fires when | sub-options hit |
|---|---|---|
| `fight` +1..+2 | culture-builder, sub != `culture-builder-teamwork` | 4 of 5 |
| `discipline` −2..−1 | culture-builder, sub != `culture-builder-confidence` | 4 of 5 |
| `discipline` +1..+2 | authoritarian, sub != `authoritarian-teamwork` | 4 of 5 |
| `fight` −2..−1 | authoritarian, sub != `authoritarian-rebounding` | 4 of 5 |

Equal magnitudes (±1.5 mean), equal firing rates, and `generate_random_coaching_focus` picks
uniformly from 19 options. Expected net contribution to both attributes is **zero**. The
drill mapping is symmetric too — `discipline` draws 0.25x from four categories, `fight` 0.5x
from two; both total 1.0x.

**Direct measurement contradicts the season figures.** Running `execute_training` 200x with
`generate_random_training_allocations(24)`:

| focus | Δfight/season | Δdiscipline/season |
|---|---|---|
| none | −4.5 | +4.9 |
| random | −10.8 | +3.9 |

**Opposite sign and an order of magnitude smaller** than the season's +32 / −48.

**Two candidates remain, neither yet confirmed:**
1. **CPU auto-train does not use random allocation.** `auto_train_one_cpu_team` trains a
   "coaching-quality REFERENCE" plan (see the comment above `_AUTOTRAIN_PLAYER_ATTRS` in
   `franchise_routes.py`). 127 of 128 teams in the season are CPU, so the measured drift
   reflects that reference plan, not the random path measured above. **Measure the reference
   plan's per-attribute effect first — this is the most likely owner.**
2. **The "training" figure is INFERRED, not measured.** Report §2b derives it from
   unclamped week-to-week `pre`->`post` gaps in the band log, so it attributes EVERY
   non-EOG change to training — including anything else that writes team attributes between
   games (EOS, training camp, rollover). Verify the attribution before trusting the number.

**Why not just tune EOG around it:** `fight` EOG is structurally zero (every game has exactly
one winner, so win +1 / loss −1 nets to 0 league-wide); offsetting +32 would require losses to
hurt far more than wins help, i.e. every team drifts down over a season. `discipline` would need
EOG ≈ +2.04/game, which on a ±20 range rails the ceiling in about six games.

---

## ⚠️ MEASUREMENT FRANCHISES ARE SEEDED BY PROD CODE, MEASURED BY LOCAL CODE (August 2026)

**The structural hazard behind several hours of confusion, stated once so it is not
rediscovered.** A measurement franchise is created through the UI, which talks to the
**deployed Railway backend running `main`**. The season is then driven **in-process by local
`develop` code**. So every value seeded at creation comes from prod, and everything computed
during the run comes from local. Anything changed since the last deploy **seeds wrong,
silently, and looks like data rather than an error.**

`main` is currently **158 commits behind `develop`**.

### Audit: what differs (prod `main` -> local `develop`)

| surface | prod (main) | local (develop) | consequence for a measurement franchise |
|---|---|---|---|
| **`position_ratings.py` RT model** | pre-recalibration | recalibrated | **100% of FPD players carry old-formula `position_ratings`, median delta 24, max 55.** Baked in at creation and NOT recomputed for franchise mode (`_update_position_ratings` skips `is_franchise`). Feeds `projected_starting_five` -> identity signals -> starter strength, and every lineup decision. |
| **`player_generator.py`, `recruit_generator.py`** | ABSENT | present | prod builds rosters by a different path; the player population itself may differ |
| **`TEAM_ATTR_CLAMPS` core-8** | ±10 | ±20 | prod-written attributes live in HALF the range local code assumes |
| `team_chemistry` init (franchise) | `randint(7, 10)` | `randint(8, 11)` | 21% of the league born on the 7 floor |
| `rebound_modifier` init (franchise) | 0.2 | 0.5 | floors 93/128 teams by week 3 |
| `eog_attr_bands.py` | ABSENT | present | prod has no band configuration at all |
| `team_identity.py`, `franchise_identity.py` | ABSENT | present | prod has no CPU identity |
| `TEAM_ATTR_RANGES["rebound_modifier"]` | (0.0, 0.4) | (0.0, 1.0) | no practical difference — franchise init sets the value explicitly |
| `init_team_attributes` single-mode rebound | `TEAM_ATTR_RANGES` (= 0.0-0.4) | literal 0.0-0.4 | identical behaviour |

---

## DEPLOY CHECKLIST — develop -> main (prepared 2026-08-11) — SHIPPED

*Executed. As of 2026-09-04 `main` is 1 commit behind `develop`. The 158-commit gap described
below is historical. `scripts/verify_deploy.py` remains a live tool — see the bottom of
this section for its invocation.*

`main` is 158 commits behind. Testers are on ±10 clamps, no CPU identity, and
pre-recalibration attributes. No migration path is needed: users are told to abandon
existing franchises and start new ones.

| # | step | notes |
|---|---|---|
| 1 | **Back up prod collections** | DONE — `~/gob-measurement-archive/db_backups_predeploy/`, checksummed, reload-verified. `gob.players_backup` is NOT a usable rollback (stale; attributes differ on 1440/1536). |
| 2 | **Merge develop -> main** | code half |
| 3 | **Copy `players` + `recruit_sets`** staging -> prod | data half. NOT the skeletons — see below. |
| 4 | `GOB_DB_ACCESS=write` in Railway | redundant signal for the prod guard; `RAILWAY_*` alone also satisfies it |
| 5 | CSP: allow `fonts.googleapis.com`, `www.googletagmanager.com` | new external hosts |
| 6 | Site callout: abandon current franchises | |
| 7 | **`scripts/verify_deploy.py`** | proves the deploy took — see below |

**ORDERING IS BACKUP -> MERGE -> COPY, not copy -> merge.** New code reading old data is a
known-good combination — both measurement seasons ran 26 weeks on exactly that (local code
against prod-formula ratings). OLD code reading NEW data is untested: prod's current build
would be handling a `recruit_sets` 50% larger than it expects.

### Do NOT copy the skeletons

`fcp_skeletons` / `hct_skeletons` hash differently across databases but are **identical except
for `_id`** — every coordinate matches. Copying would churn prod for no benefit. **Heuristic
worth keeping: same byte size + different hash usually means metadata; a real content change
moves the size.** `recruit_sets` moved 146 KB -> 356 KB, and that one is real.

### `recruit_sets` 300 -> 450 is INTENTIONAL

Deliberate regeneration (`1277580c6`, 2026-08-08): 150 added recruits plus the `entry_tier` /
`position_intent` / `potential_factor` / `has_portrait` fields. It is a balance change riding
along with the attributes deploy — 50% more recruits available — and should be stated in the
callout, not discovered.

⚠️ **Prod's document claims `version=2` but holds the 300-recruit content with none of the
regen fields.** A version check would pass on stale data; only a content checksum catches it.

### Post-deploy verification — `scripts/verify_deploy.py`

Nothing else on the list confirms the deploy took, and silent divergence is the failure being
closed. `/health` now reports `commit`, `hash_seed` and `db_access` so the running build is
answerable from outside.

    scripts/verify_deploy.py --health-url https://<prod>/health   # A: build
    GOB_DB_ACCESS=read scripts/verify_deploy.py --data            # B: data (prod URI)
    scripts/verify_deploy.py --franchise-id <id> --delete         # C: seeding

C needs a throwaway franchise created in the UI (creation requires an authenticated session,
which the script deliberately does not embed) at **week 1, unplayed** — training moves the
seeded values immediately. It checks identity persisted, sliders varying, `rebound_modifier`
0.5, `team_chemistry` 8-11, `shot_threshold` 80-90, core-8 clamps ±20, then deletes the
franchise and its FTD/FPD/FRD rows.

The data check was negative-controlled against prod BEFORE the deploy and correctly FAILED on
both collections — it detects a stale copy rather than merely returning green.

---

## Sunset: `/team-roster/{team}` (removed 2026-08-17)

Removed the route, its 8 Jinja templates, the 8 "In Development" sibling pages, the
dev-only `/team-roster/` static-redirect entry, and `tests/test_team_roster_page.py`.

Why it went rather than being brought in line with the attribute-tile work:

- **Zero inbound links** anywhere in the repo — reachable only by typing the URL.
- **Wrong data source.** It read `players_collection` (the universal player pool), not
  franchise player data, so the same team showed *different numbers* than
  `team-roster-view.html`.
- **Already dead in development.** The dev middleware redirects any `/team-roster/*`
  path to `/static/...` before routing (`api.py`, static_dirs), so the page only ever
  rendered in production. That is likely why its data source drifted unnoticed.
- **No auth.** The route took no `Depends(get_current_user)` while every other roster
  surface is behind auth.

Residual risk accepted: an external bookmark or link would now 404. If that surfaces,
the fix is a 301 to `/team-roster-view.html` rather than restoring the page.
