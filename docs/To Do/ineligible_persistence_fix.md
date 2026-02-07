# Ineligible (fouled-out) persistence on lineup screen

## Bug

- When a player fouls out, the lineup screen correctly shows them greyed out and they cannot be added.
- After the user plays more and then calls a **timeout**, when they return to the lineup screen the fouled-out player is **no longer** greyed out and **can be added** to the lineup.
- Ineligibility should persist for the rest of the game on **every** visit to the lineup screen (foul-out flow, user timeout, quarter break, etc.), and grid view and player view should both show fouled-out state consistently.

## Intended behavior

- **Backend:** `ineligible_players` is in `game_state`, saved in the game document (e.g. via `summarize_game_state` on foul-out timeout save and on each simulate-turn save), and returned by GET `/api/game/{game_id}` so the lineup screen can apply it every time.
- **Frontend:** On every lineup screen load when `game_id` is in the URL, fetch game (with `source=db`), read `ineligible_players`, and mark every matching roster player as `ineligible` and `fouled_out`. Grid view and player view both render from that same roster, so both should show greyed-out / non-draggable / non-clickable for fouled-out players for the rest of the game.

## Current flow (where it can go wrong)

1. **Backend**
   - `check_and_handle_foul_out()` appends `foul_player.player_id` to `game_state["ineligible_players"]`.
   - Foul-out timeout save and simulate-turn save use `summarize_game_state()`, which includes `ineligible_players` (see `BackEnd/utils/shared.py` ~1300). So the DB document should keep `ineligible_players` as long as every save path uses that summary.
   - GET `/api/game/{game_id}` (DB path) returns `saved.get("ineligible_players", [])` and the projection includes `"ineligible_players": 1`.

2. **Frontend**
   - Lineup screen: `init()` → `await loadRoster()`.
   - Inside `loadRoster()`: fetch roster from `/roster/{team}` → `roster = (data.players || []).map(...)` (fresh objects, no ineligible flags). Then, **only when `gameId` is present**, fetch `/api/game/${gameId}?quarter=...&source=db`, then:
     - `ineligiblePlayers = gameData.ineligible_players || []`
     - `roster.forEach(player => { if (playerId && ineligiblePlayers.includes(String(playerId))) { player.ineligible = true; player.fouled_out = true; } })`
     - Then merge game players (energy, stats) into roster, sort, `renderRoster()`.
   - So ineligibility is applied in exactly one place: inside `loadRoster()` when there is a `gameId`, using the single game fetch. Grid and player views both use the same `roster` (and `rosterDataForSorting` / card builders) and already check `p.ineligible || p.fouled_out` for styling and disabling drag/click.

So the intended behavior is already “apply on every lineup visit” (every full load runs `loadRoster()` once and applies ineligible from the game response). The bug is that on the **second** visit (after a user timeout), the same player appears eligible again. That implies either the **API is not returning** the right `ineligible_players` on that visit, or the **frontend is not matching** them to roster players.

## Likely causes

### 1. **ID format mismatch (most likely)**

- Backend stores `foul_player.player_id` (could be string or ObjectId) in `game_state["ineligible_players"]`. That list is saved to MongoDB as-is.
- When GET `/api/game` returns the document, `saved.get("ineligible_players", [])` may contain BSON ObjectIds. If the response is serialized to JSON without normalizing to strings, the frontend can receive values like `{"$oid": "..."}` or similar, so `ineligiblePlayers.includes(String(playerId))` never matches roster `_id` / `playerId` / `player_id` (which are usually strings).
- **Fix:** In the GET `/api/game` response (and any other endpoint that returns game state to the lineup screen), normalize `ineligible_players` to a **list of strings** (e.g. `[str(pid) for pid in saved.get("ineligible_players", [])]`) before sending. On the frontend, keep using `ineligiblePlayers.includes(String(playerId))` and ensure roster player IDs are compared consistently (`_id || playerId || player_id`).

### 2. **Game document missing `ineligible_players` on read**

- If any save path that runs after a foul out (e.g. a save triggered when the user goes to timeout or when the game is written for another reason) builds a payload that **does not** include `ineligible_players`, that save could overwrite or clear the field in the DB.
- **Check:** All code paths that update the game document (foul-out timeout save, simulate-turn save, user timeout save if any, etc.) must use a summary that includes `game_state["ineligible_players"]` (as `summarize_game_state` does). Ensure no partial update clears or omits `ineligible_players`.

### 3. **Roster and game use different ID sources**

- Roster comes from `/roster/{team}`; game and `ineligible_players` use IDs from the game’s players/lineup. If those IDs differ (e.g. roster uses one key and game uses another), matching will fail.
- **Check:** When the game is created and when fouls are recorded, the same player identifiers that the roster API returns (e.g. `_id` / `player_id`) must be what is stored in `ineligible_players`. Then the lineup screen’s `playerId = player._id || player.playerId || player.player_id` and `ineligiblePlayers.includes(String(playerId))` will align.

## What to implement (no code here; apply everywhere lineup is used)

1. **Backend**
   - **Normalize `ineligible_players` to list of strings** in every API response that the lineup screen uses (at least GET `/api/game/{game_id}` when returning from DB). Use a single helper if needed so all paths (in-memory vs DB, timeout response, etc.) return the same shape.
   - **Persist ineligible on every save:** Confirm every place that writes the game document (foul-out timeout, simulate-turn, any user-timeout or navigation save) includes `ineligible_players` (via `summarize_game_state` or equivalent). Never overwrite the game doc with a payload that drops `ineligible_players`.

2. **Frontend – same behavior on every lineup visit**
   - Keep the current rule: whenever the lineup screen loads and the URL has `game_id`, fetch game (with `source=db` or equivalent) and apply `ineligible_players` to the roster (set `player.ineligible` and `player.fouled_out`). No extra conditions (e.g. “only on foul-out return”); do it for **all** visits (after foul out, after user timeout, after quarter break, etc.).
   - Ensure this runs **before** any view-specific render: the single place (inside `loadRoster()` when `gameId` exists) is correct; just ensure the fetch always runs and the response always includes a normalized `ineligible_players` list.

3. **Grid view and player view**
   - Both already use `roster` (and derived data) and check `p.ineligible || p.fouled_out` for:
     - Greyed/dead styling (e.g. `.ineligible`, opacity, cursor).
     - Disabling drag and “click to add” so fouled-out players cannot be added to the lineup.
   - Ensure **every** place that:
     - Renders a player row/card (grid and player view), or
     - Handles drag/drop or click-to-fill
     uses the same check (`ineligible || fouled_out`) so that fouled-out players stay greyed out and unaddable for the rest of the game. No code path should allow adding an ineligible player regardless of how the user reached the lineup screen.

4. **Testing**
   - After a player fouls out, confirm the lineup screen shows them greyed out and unaddable.
   - Play more, then call a **user timeout** and return to the lineup screen: the same player(s) must still be greyed out and unaddable in both grid and player view.
   - Repeat after a quarter break and any other path that opens the lineup screen; ineligibility must persist and both views must stay in sync with the same roster and flags.

## Files to touch

- **Backend:** `BackEnd/api/api.py` – GET `/api/game/{game_id}` (and any other response that sends `ineligible_players`): normalize to list of strings; ensure all game-save paths include `ineligible_players`.
- **Backend:** `BackEnd/utils/shared.py` – `summarize_game_state` already includes `ineligible_players`; ensure no other save builder omits it.
- **Frontend:** `FrontEnd/static/set-lineup.js` – in `loadRoster()`, keep applying `ineligible_players` from the game response whenever `gameId` is present; optionally harden matching (e.g. normalize both sides to string and trim). Ensure grid and player view and all add/drag logic use `ineligible || fouled_out` everywhere a player can be selected or added.
