# Why test_franchise_stats and test_franchise_complete_week Fail

**Conclusion: The code is not faulty. Both failures are due to outdated or incorrect test setup/expectations.**

---

## 1. `test_simulated_game_accumulates_stats` (KeyError: 'PTS')

**What the test does:** Creates a `FranchiseManager` (no `initialize_season()`, so no franchise_id), inserts two players in `players_collection`, then calls `manager.simulate_game("T0", "T1")` with a monkeypatched `run_simulation` and `summarize_game_state`. It expects `p1["stats"]["season"]["PTS"] == 7` and similar in the **core** `players_collection`.

**Why it fails:**

1. **Wrong mock shape**  
   The fake summary has:
   ```python
   "box_score": {
       "Team1": {"PG": {"name": "B Two", "PTS": 12}},
       "Team0": {"PG": {"name": "A One", "PTS": 7}},
   }
   ```
   The box_score entries do **not** include `"playerId"`.  
   In `apply_stats_from_summary`, each player is processed only when `raw_pid = player_data.get("playerId")` is set. With no `playerId`, every player is skipped, so no stats are applied and `p1["stats"]["season"]` stays `{}` → `KeyError: 'PTS'`.  
   So the test mock is **faulty**: it doesn’t match the contract (box_score must include `playerId` per player).

2. **No non-tournament path in `apply_stats_from_summary`**  
   When `franchise_id` is `None`, `simulate_game` calls `apply_stats_from_summary(summary, game_token)` with no `tournament_id`. In `stat_updater.apply_stats_from_summary`, the only updates happen inside `if tournament_id: ... if tid:`(tournament document). There is **no** branch that updates `players_collection` when `tournament_id` is `None`. So even with a correct mock, this test would still see no updates to the core players collection. The test is therefore asserting **removed or never-implemented** behavior (single-game, non-franchise, non-tournament stats written to `players_collection`).

**Verdict:** Test is faulty (bad mock + expectation on behavior that no longer exists in code). Application code is consistent with current design (franchise/tournament paths only).

---

## 2. `test_complete_week_saves_and_simulates` (assert team_a["record"]["W"] == 1)

**What the test does:** Inserts a minimal franchise doc (schedule + week) and 4 teams, then POSTs `/franchise/complete-week` with a result (team1_id "A", team2_id "B", scores). It expects `db.teams` to be updated so that `team_a["record"]["W"] == 1` and `team_b["record"]["L"] == 1`.

**Why it fails:**

- In `franchise_routes._save_game_result`, the docstring states:
  - *"This function **no longer updates** the universal teams collection. Franchise mode stores W/L and PF/PA in **franchise.results**."*
- So franchise W/L are intentionally **not** written to `db.teams`; they live in the franchise document (e.g. `franchise.results`). The test still asserts the **old** behavior (`db.teams` record W/L).

**Verdict:** Test is **outdated**. It expects deprecated behavior. The application code is correct and intentionally does not update `teams` for franchise mode.

---

## Summary

| Test | Cause | Code faulty? |
|------|--------|---------------|
| `test_simulated_game_accumulates_stats` | Mock missing `playerId` in box_score; no code path updates `players_collection` when `tournament_id`/franchise is absent | No |
| `test_complete_week_saves_and_simulates` | Asserts W/L on `db.teams`; franchise W/L are now in franchise.results only | No |

Fixing the tests would mean: (1) for the first test, adding `playerId` to the mock and either restoring a non-tournament update path in `apply_stats_from_summary` or changing the test to assert on franchise/tournament stats instead of `players_collection`; (2) for the second test, asserting on franchise document (e.g. `results`) and/or week advancement instead of `db.teams` record.
