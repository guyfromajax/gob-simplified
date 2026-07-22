# EOG Persistence — Tier 3 Design/Plan (systematize + parallelize)

**Status:** PLAN ONLY — not implemented. Integrity-first; ship only after the dual-run proof.
**Owner context:** CPU-week persistence loop in `_complete_week_finish_cpu_and_persist` (`franchise_routes.py`). Tiers 1–2 already shipped (Tier 2 = batched `cpu_sim_job` persist + N-game heartbeat).

## Problem

The per-CPU-game end-of-game (EOG) persistence is ~15 sequential Atlas round-trips × 63 games ≈ **~950 round-trips (~20s wall)**, dominated by network latency, not compute. Built piecemeal by multiple agents, so the same **large game doc is re-loaded 3× per game** and the **`_id`-variant resolution is duplicated** across:

| Consumer | Re-reads game? | Why |
|---|---|---|
| `stat_updater.finalize_game` | 2–3× (initial + ObjectId fallback + "freshness" re-read at ~1667) | stat rollup + applied_games/matchups claim |
| `_save_game_result` | 1× (`_id` resolution find_ones) | team records |
| `update_team_attributes_after_game` (`[EOG-GAME-DOC-SELECT]`) | 1× (picks "richer" of two `_id` docs) | team-attr deltas + play/scouting decay |

Those defensive re-reads are **Feb-2026 EOG persistence guardrails** — scar tissue from the "two docs per game" (`_id` as string vs ObjectId) incident. They are *not* obviously dead; they must be proven dead before removal.

## Goal

Realize the design the EOG doc already prescribes ([`06_Gameplay_Systems/End_Of_Game_System.md`](../06_Gameplay_Systems/End_Of_Game_System.md) §"EOG Data Source & Access Method"):

> "read from **one** frozen per-game snapshot (`games.eog_inputs`)… Build and persist `eog_inputs` **once**, then compute all EOG attribute changes from `eog_inputs` only."

One snapshot in, one pass, batched flush, parallelized across games.

## ⚠️ RNG determination (drives the verification design)

**EOG DOES consume RNG.** `calculate_attr_changes` (`franchise_routes.py:1601+`) and the offensive-play / defensive-scouting decay (`training_execution_v2.py`) call **global `random.randint(...)`** per team per game (shot_threshold, discipline, fight, rebound_modifier, efficiencies, chemistry, decay bands).

Consequences:
- A naive dual-run of the same game through old vs new EOG paths produces **different** deltas unless **seeded identically AND the RNG draw order/count is preserved**.
- Therefore the new orchestrator MUST preserve the exact `random.*` draw sequence (same calls, same order) to allow a seeded byte-identical diff. If it can't, fall back to the **poison-test rule** (draw-count changes aren't verifiable by exact diff — keep the draws, poison the output; see `feedback_poison_test_rule`).
- Separately, per the capstone RNG rule (each independent subsystem gets its own stream), EOG's use of global `random` is itself a latent coupling — note it, but keep it out of scope for Tier 3 unless the orchestrator refactor makes swapping to a dedicated `eog_rng` free.

## Phase 0 — Instrumentation-first (SHIP THIS ALONE, LEAVE IT IN PROD)

Before deleting any defensive read, prove it's dead with real traffic.

- Add a counter/log that fires **only when a defensive path actually does work**:
  - `finalize_game`: log when the ObjectId fallback (`~1604`) or the "freshness" re-read (`~1667`) returns a **different/richer** doc than the first read.
  - `update_team_attributes_after_game`: log when `[EOG-GAME-DOC-SELECT]` picks the **ObjectId** doc over the string doc (i.e., the string-`_id` canonicalization did NOT already win).
  - `_save_game_result`: log when its `_id` resolution finds a **duplicate** doc to purge.
- Emit at a greppable tag, e.g. `[EOG-IDGUARD-FIRED]`, at INFO/WARNING with franchise_id/week/game_id.
- **Exit criterion:** after N real week-advances (regular + EOS), if `[EOG-IDGUARD-FIRED]` count is 0, the guardrails are dead for franchise CPU games (whose `_id` is freshly minted and written once) → safe to bypass. If it fires, the guardrail stays and we do NOT bypass that read.

## Phase 1 — One-snapshot EOG orchestrator

- Build/persist `eog_inputs` **once** per game from the in-memory sim `summary` (already have it — no read).
- Single `apply_eog_for_game(game_doc, eog_inputs, …)` that runs, from that one snapshot: stat rollup (FPD season/career + user career record), team-attr deltas, offensive-play + defensive-scouting decay, team records, momentum.
- Accumulate writes into **one FTD update per team** (team_attributes + `plays.*.effectiveness` + `scouting_data.defense.*.effectiveness`) instead of several separate `update_one`s.
- Only bypass the Phase-0-proven-dead re-reads; keep every guardrail Phase 0 shows still fires.
- Preserve exact `random.*` draw order (see RNG note) so Phase 2 can verify by seeded diff.
- Postseason freeze (weeks 27–34) and distant-sim override branches must be preserved verbatim.

## Phase 2 — Dual-run byte-identical verification (gate before ship)

- Harness: for many real staging games, run the CURRENT EOG path and the NEW orchestrator on the **same** game doc under a **fixed seed**, and assert the resulting **FPD + FTD + game-doc writes are byte-identical** (same `$set`/`$inc` keys and values). Same residual-style proof used for the ±2 scoring bug (zero residual across games).
- Because EOG consumes RNG: seed both runs identically **and** confirm identical draw counts. If the orchestrator changes draw order/count, switch that surface to poison-testing (assert the write *shape* + that outputs move together when the RNG output is poisoned), not exact diff.
- Cover: regular season, EOS weeks (bracket sync), distant-sim override, postseason freeze, and a game whose team plays only once (disjointness assumption for Phase 3).

## Phase 3 — Parallel flush

- Each week every team plays once → per-game FTD/FPD/`db.games` writes are **disjoint across games**. Persistence is I/O-bound, so a thread pool (I/O wait overlaps; no GIL issue) can take the ~20s flush toward a few seconds.
- Shared writes stay serial / atomic: the franchise doc `results` array, `cpu_sim_jobs`, and the `applied_games`/`applied_matchups` claim inside `finalize_game`. Pull them out of the parallel section or keep them as atomic ops.
- Threads (not the spawn process pool) — this is I/O wait, and pymongo clients are thread-safe (fork-unsafe, not thread-unsafe). Verify connection-pool size ≥ worker count.

## Expected payoff

- Phase 1 alone: eliminates ~2–3 large-doc re-reads/game + duplicated `_id` logic + batches FTD writes → meaningful latency + bandwidth cut.
- Phase 3: overlaps the remaining round-trips → target **~20s → a few seconds**.

## Guardrails / non-negotiables

- Integrity > speed. Nothing ships without the Phase-2 zero-residual proof.
- Do not delete a defensive `_id` read until Phase-0 prod traffic shows `[EOG-IDGUARD-FIRED]` = 0 for that path.
- Shared functions (`finalize_game`, `update_team_attributes_after_game`) are also used by the **user game (phase-a)** and **tournaments** — any optional "trusted in-memory doc" path must default to today's behavior and only activate for the CPU-week caller.
