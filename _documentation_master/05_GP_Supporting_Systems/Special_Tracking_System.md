# Special tracking (game persistence)

Small, explicit fields written during gameplay for features that need facts the box score alone cannot reconstruct later.

| Name | What it is |
|------|------------|
| **Opening lineup snapshot** | The five `player_id`s who started the game for each team (`opening_lineup` on the game document), captured once at the Q1 opening tip and never changed—used for PGPC bench vs starter logic and any feature that needs “who started” instead of end-of-game lineup slots. |

**Implementation:** `BackEnd/opening_lineup_snapshot.py` (writes `game_state`), called from `BackEnd/utils/opening_tip.py`; persisted by `summarize_game_state` in `BackEnd/utils/shared.py`; restored from DB in `BackEnd/api/api.py`.
