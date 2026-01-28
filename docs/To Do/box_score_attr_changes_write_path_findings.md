# Box Score Attribute Changes – Write Path Findings

**Date:** Jan 2026  
**Issue:** `team_attribute_changes` often missing on game doc → not shown in box score.

---

## 1. Where we write `team_attribute_changes`

| Location | When it runs | Writes to game doc? |
|----------|----------------|---------------------|
| **complete-week** | After user’s franchise game ends; frontend POSTs to `/franchise/complete-week` | ✅ Yes – `db.games.update_one(..., {"$set": {"team_attribute_changes": ...}})` |
| **save-result** | POST to `/franchise/save-result` | ✅ Yes – same `$set` |
| **simulate_quarter** | Never for franchise | ❌ No – only finalizes scrimmage |

**Important:** The frontend **never** calls `/franchise/save-result`. Franchise always uses **complete-week** as the only write path for `team_attribute_changes`.

---

## 2. When complete-week runs (frontend)

- **Play Quarter** (Q4 ends): `gameScene` → `finalizeGame` → POST to complete-week.  
  `final_game_document` comes from simulate-quarter response when `is_final`.
- **Sim Full Game**: `bootGame` → `handleGameCompletion` → `finalizeGame` → POST to complete-week.  
  `simData` = `lastSummary` (last Q4 simulate-quarter response), which includes `final_game_document`.  
  So we **do** pass `game_document` for Sim Full Game when the backend includes it.
- **Sim Quarter** (single quarter, game ends): same pattern as Play Quarter when `is_final`.

complete-week is only called when `franchiseId && !tournamentId && Number.isInteger(week) && week >= 1`.  
If `week` is missing or invalid, we **never** call complete-week → **never** write `team_attribute_changes`.

---

## 3. What complete-week does

1. `_save_game_result(...)` – updates game with `team1_id`, `team2_id`, scores, `week`, etc. Does **not** touch `team_attribute_changes`.
2. `finalize_game(game_id, mode="franchise", ...)` – applies player stats to franchise, etc.
3. `update_team_attributes_after_game(...)` – computes attribute deltas.
4. **Only if `attribute_changes` is truthy:**  
   `db.games.update_one({"_id": game_id}, {"$set": {"team_attribute_changes": attribute_changes}})`

If `attribute_changes` is `{}` or we skip the `$set` for any reason, the game doc **never** gets `team_attribute_changes`.

---

## 4. Gaps that prevent `team_attribute_changes` from being written

1. **complete-week never called**
   - `week` missing or not `>= 1` (e.g. not in URL / `simData` for Sim Full Game).
   - `franchiseId` missing.
   - User navigates away or errors before `finalizeGame` finishes (e.g. before complete-week POST).

2. **complete-week runs but we never `$set`**
   - We **only** `$set` when `attribute_changes` is truthy. If `update_team_attributes_after_game` returns `{}` and we treat that as “no changes,” we skip the write.  
   - In practice we usually return `{ home_team_id: {...}, away_team_id: {...} }`. If both are `{}`, we still `$set` unless we explicitly skip “empty” results.
   - **Exception** in `update_team_attributes_after_game` or before the `$set` → we log and never `$set`.

3. **Wrong game_id**
   - We `$set` on `user_game_id_final`. If that doesn’t match the game doc we later use for the box score (e.g. different `game_id` sent or resolved), we’d write to a different document than the one we view.

4. **`game_id` missing**
   - We use the “legacy” path (lookup by week + team IDs). We still run attribute update and `$set` there. If legacy lookup fails, we never run the attribute update for the user game.

---

## 5. Summary

- **Single write path for franchise:** complete-week (save-result unused by frontend).
- **complete-week** is the only place we `$set` `team_attribute_changes` on the game doc.
- **If it’s missing,** either complete-week was never called (e.g. `week` / `franchiseId`), we threw before the `$set`, we skipped the `$set` when we shouldn’t, or we wrote to a different `game_id` than the one used for the box score.

---

## 6. Recommended next steps

1. **Always `$set` `team_attribute_changes`** when we’ve run `update_team_attributes_after_game` for the user game, even when the result is `{}`. That way the field always exists for that game; frontend can hide “Attribute Changes” when empty.
2. **Add logging** around complete-week: when we run attribute update, whether we `$set`, and the `game_id` we write to. Makes it easy to see if we never run, never write, or write to the wrong game.
3. **Verify `week`** is always sent for franchise (Sim Full Game and Play Quarter), and that we never skip complete-week due to `week` or `franchiseId` checks.

---

## 7. Implemented fixes (Jan 2026)

- **Backend (complete-week + save-result):** Always `$set` `team_attribute_changes` (use `attribute_changes or {}`). Log `game_id` and keys when we `$set`. Removed "skip when empty" behavior.
- **Frontend (finalizeGame.js):** Fallback `week` from `simData.final_game_document?.week` when URL/localStorage/simData.week missing. Log when we skip complete-week due to missing or invalid `week` (`Skipping complete-week: missing or invalid week` with `week`, `fromUrl`, `fromSimData`, `fromFinalDoc`).

- **Root cause (game_document path):** When `game_document` is provided, we used `user_game_id_final = str(summary.get("_id"))`. The frontend sends the raw game doc; `_id` can be `{"$oid":"..."}`. `str()` on that yields an invalid id, so `ObjectId(user_game_id_final)` threw in the attribute-update block. We caught, logged, never `$set`, still returned 200. **Fix:** Use `req.game_id` as `user_game_id_final` when we have `game_document`. Only use `summary["_id"]` when we looked up from DB. Also: return 404 when game not found (instead of bare `return`); log `$set` as `logger.warning` so it appears in Railway.
