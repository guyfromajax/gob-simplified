# Statistics System

## OREB putback-miss rebound stats (fix)

**Bug (fixed):** When a shot missed → OREB → putback attempt → **miss** → someone grabbed the rebound, that rebounder’s OREB or DREB was never recorded (100% of the time). Other stats (e.g. FGA/FGM on a later putback make) were correct.

**Cause:** The rebound stat was recorded in `shared.resolve_offensive_rebound()` on the player returned by `determine_rebounder()` (a lineup reference). Deltas and persistence use `team.get_all_players()` (roster). When lineup and roster were different object instances for the same player, or when the later lookup by ID in `turn_manager` failed, the stat never appeared on the canonical roster player used for deltas.

**Fix:**

1. **`BackEnd/utils/shared.py`**  
   After `determine_rebounder()` returns, we resolve the **canonical roster player** with `new_team.get_player_by_id(str(pid))` and call `record_stat(new_stat)` on that player (fallback: record on the lineup player if lookup fails). Rebound event `rebounderId` is set from the same normalized ID.

2. **`BackEnd/models/turn_manager.py`**  
   - Lookup uses normalized ID comparison (`str(player_id) == str(rebounder_id)`) and a fallback via `off_team.get_player_by_id(rebounder_id_str) or def_team.get_player_by_id(rebounder_id_str)` so we always get the right `new_rebounder` for `pending_oreb`, result text, etc.  
   - We **do not** call `record_stat` again in turn_manager; the stat is recorded only once in shared.py on the canonical player, avoiding double-count.

Result: OREB/DREB are recorded on the same roster instance used for deltas and persistence, so putback-miss rebounds are always reflected in stats.

---

## PIP vs fast break points

**PIP** (Points in Paint) does **not** include fast-break field goals; those increment **FB_PTS** only. See `docs/docs_1_systems/00_General_Systems/Statistics_System.md` (PIP and Fast Break sections) and `BackEnd/models/shot_manager.py` (`pip_stat_eligible`).
