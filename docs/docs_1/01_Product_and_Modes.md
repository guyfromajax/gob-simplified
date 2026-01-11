# Product and Modes

## Game Modes

The Geeked Out Basketball game engine supports three distinct game modes, each with its own persistence and progression systems.

### Mode Values

**SS&S Principle:** Mode is always explicitly declared, never inferred. This ensures consistency across the codebase and prevents bugs from implicit logic.

- **`"single"`** - Single Game Mode (one-off games, no persistent state)
- **`"tournament"`** - Tournament Mode (bracket-based competition)
- **`"franchise"`** - Franchise Mode (season-based progression)

### Mode Declaration

**Frontend:**
- Mode is read from URL parameters: `?mode=single`, `?mode=tournament`, or `?mode=franchise`
- If not provided in URL, mode is determined by presence of `tournament_id` or `franchise_id`
- **Default:** If no mode is specified and no `tournament_id`/`franchise_id` exists, mode defaults to `"single"` (explicit, not inferred)

**Backend:**
- Mode is always passed explicitly in API requests
- Backend validates mode and requires appropriate IDs:
  - `mode="single"` requires `game_id`
  - `mode="tournament"` requires `tournament_id`
  - `mode="franchise"` requires `franchise_id`

### Mode-Specific Behavior

#### Single Game Mode (`mode="single"`)
- **Collection:** `games`
- **Document:** Game document (UUID string or ObjectId)
- **Team Storage:** `games.{game_id}.teams.{team_id}`
- **Playbook Settings:** Saved to game document
- **Persistence:** Settings persist for duration of game, reset for new games
- **Attributes:** Randomized per game (Single Game mode ranges)

#### Tournament Mode (`mode="tournament"`)
- **Collection:** `tournaments`
- **Document:** Tournament document (ObjectId)
- **Team Storage:** `tournaments.{tournament_id}.teams.{team_id}`
- **Playbook Settings:** Saved to tournament document
- **Persistence:** Settings persist across tournament games
- **Attributes:** Tournament-specific ranges

#### Franchise Mode (`mode="franchise"`)
- **Collection:** `franchises`
- **Document:** Franchise document (ObjectId)
- **Team Storage:** `franchises.{franchise_id}.franchise_teams.{team_id}`
- **Playbook Settings:** Saved to franchise document
- **Persistence:** Settings persist across franchise season
- **Attributes:** Franchise-specific ranges

### Mode Standardization

**Historical Note:** Previously, Single Game mode was sometimes referred to as `"standalone"` or inferred from absence of tournament/franchise IDs. This has been standardized to always use `"single"` explicitly.

**Migration:**
- All code now uses `"single"` instead of `"standalone"`
- `getMode()` function returns `"single"` for Single Game mode
- Frontend always sets `mode="single"` in URL params for Single Game mode
- Backend validates and requires explicit mode in all requests

### See Also

- `docs/docs_1_systems/01_Game_Mode_Systems/Single_Game_Systems.md` - Single Game mode detailed documentation
- `docs/docs_1_systems/01_Game_Mode_Systems/Tournament_Systems.md` - Tournament mode detailed documentation
- `docs/docs_1_systems/01_Game_Mode_Systems/Franchise_Systems.md` - Franchise mode detailed documentation
