# Simulate-quarter performance and week-15 slowdown

## Root cause: DB every turn (fixed)

**TurnManager** was calling `plays_collection.find(query)` **every turn** to get matching plays (and `plays_collection.find_one({"name": ...})` when resolving overrides). With ~200 turns per quarter, that’s **200+ MongoDB round-trips per quarter** (Railway → Atlas). At hundreds of ms per round-trip, that accounts for the ~100s per quarter.

**Fix:** Module-level caches in `BackEnd/models/turn_manager.py`:
- **`_plays_by_type_focus_cache`** – first time we need plays for a (play_type, play_focus), we `find()` and cache; every subsequent turn reuses the list.
- **`_play_doc_by_name_cache`** – first time we look up a play by name we `find_one()` and cache; later lookups are in-memory.

So we now do at most a handful of plays-collection reads per game (one per distinct query key and per distinct play name), not 200+ per quarter. Simulate-quarter should drop from ~100s to a few seconds (dominated by CPU simulation).

## Why it seemed to “break” at week 15

You used Sim Full Game for all 14 weeks and it was fine; at week 15 it slowed. The simulation code path doesn’t change for EOS. Likely explanations:
- **Same bug, different conditions:** Network/Atlas latency or load might have been lower in weeks 1–14, so 200 round-trips per quarter was “slow but acceptable.” At week 15 something (load, region, or just variance) made each round-trip slower and pushed you over the edge.
- **Larger franchise doc:** If `_load_playbook_settings` ever fell back to DB (franchise doc), that doc is bigger at week 15 (eos_tournament, 14 weeks of results), so that path would be worse. The main fix above is the plays cache; playbook fallback is still a rare path if GameManager has settings.

## Profiling in place

- **Endpoint (api.py):** Each simulate-quarter request logs:
  - `⏱️ [PERF] simulate-quarter total=Xs sim=Ys summary=Zms db_save=Wms source=... q=N full_sim=...`
  - So you can see how much of the total is: **sim** (turn loop), **summary** (building response), **db_save** (persist + refresh).
- **Turn loop (main.py):** When `full_sim=True`, after the quarter loop we log:
  - `⏱️ [PERF] full_sim loop: Q=N turns=M loop_time=Xs (Yms/turn)`
  - So you can see turn count and time per turn.

If **sim** is almost all of **total**, then the hot path is the turn loop (simulate_macro_turn). Next step is to profile inside `simulate_macro_turn` / `run_micro_turn` (e.g. with a few sampled timers or cProfile).

## Week-15 slowdown (EOS tournament)

User reported: regular season (weeks 1–14) was fine; at week 15 (first round of end-of-season tournament) things got very slow and stayed that way.

- **Simulation code:** No branching on `week` or `eos_tournament` in `main.simulate_quarter` or the turn loop. Same code path for regular season and EOS.
- **Likely explanation:** During regular season they may have been using a different flow (e.g. "Complete week" for computer games, which uses `run_simulation` server-side; or playing one quarter at a time with shorter requests). At week 15 they started "Sim Full Game" in the browser for the tournament game, which sends four simulate-quarter requests with `full_sim=True` — each ~100s. So the slowness was probably always there for full-quarter sim in the browser; they only hit that path consistently from week 15.
- **Other possibilities:** (1) Game document or `gm.turns` growing and making summary/save slower; (2) a deploy or DB change around that time; (3) something in the frontend or request payload for tournament games. The new PERF breakdown (sim vs summary vs db_save) will show whether the 100s is in the loop or in summary/db.

No EOS-specific branch was found in the simulate-quarter or turn-execution path that would make week-15+ slower.
