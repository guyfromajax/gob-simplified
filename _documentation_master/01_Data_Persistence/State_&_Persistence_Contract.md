# State & Persistence Contract

**Version:** 1.1  
**Status:** Adopted contract (implementation complete — see `../projects/Z-Completed/Unified_State_Persistence_Work_Plan.md`, archived)  
**Last Updated:** June 2026  
**Purpose:** Establish a single source of truth strategy for all state variables in GOB, eliminating patchwork fallbacks and ensuring bulletproof persistence.

> **Mode note:** Tournament and Single Game are sunset modes (`../01_Game_Mode_Systems/Sunset_Modes.md`); their rows below remain while the code stays in the repo.

---

## 1. State Sources Policy

### Core Principles

**SS&S First:** State management must be Simple, Stable, and Scalable. Complexity is a bug, not a feature.

**One Authoritative Source Per Variable:** Every state variable has exactly ONE source of truth. No silent merging, no "which source wins?" ambiguity.

**Caches Are Disposable:** Performance caches are mirrors of truth, never truth itself. They can be dropped, invalidated, or rebuilt without affecting correctness.

**Pointers Point to Truth:** URL params hold pointers (IDs) that reference authoritative server state. They enable deep-linking and refresh-safe navigation.

**Fail Loudly:** Missing required state triggers explicit errors with clear recovery paths. No silent fallbacks or "guess and hope" logic.

---

### State Tiers

| Tier | Purpose | Authoritative | Persistence | Examples |
|------|---------|--------------|-------------|----------|
| **Truth** | Authoritative server state | Server (DB) | Permanent | Game documents, franchise data, playbook settings |
| **Pointer** | Navigation context | URL params | Session | `game_id`, `franchise_id`, `tournament_id` |
| **Cache** | Performance mirror | In-memory store | Runtime only | `ongoing_games` (backend), `gameStore` (frontend) |
| **UI-only** | Temporary UI state | Client memory | Not persisted | Selected tab, dropdown state, animation frame |

**Cache Clarification:**
- **`ongoing_games`** (Backend): Python dict storing `GameManager` objects during active gameplay. Used for fast turn-by-turn simulation without DB reads.
- **`gameStore`** (Frontend): JavaScript module storing minimal game state (teams, rosters, colors, gameId). Used for UI rendering without API calls.

---

### Precedence Rules

**Strict Hierarchy (no exceptions):**
1. **Truth (Server)** → Always authoritative, can overwrite any cache
2. **Pointer (URL)** → Required for navigation, must point to existing truth
3. **Cache (Store)** → Optional performance optimization, rebuild from truth if missing
4. **localStorage** → Explicit "Resume last game" UX only, not invisible fallback

**When Sources Conflict:**
- Server always wins (single source of truth)
- URL pointer missing → Fail with error (don't guess)
- Cache stale → Rebuild from truth (don't guess)
- localStorage missing → Not an error (explicit resume feature only)

---

### "Fail Loudly" Rules

**Missing Required Pointer:**
- **Rule:** If URL missing required ID (e.g., `game_id` for `/court.html`), show error screen
- **Error:** "Game not found. Please start a new game from the lineup screen."
- **Recovery:** Redirect to lineup screen with teams preselected (if available)

**Missing Truth:**
- **Rule:** If server doesn't have document referenced by pointer, show error screen
- **Error:** "Game document not found. This may have been deleted or expired."
- **Recovery:** Clear URL pointer, redirect to lineup screen

**Version Mismatch:**
- **Rule:** If cached state version doesn't match server version, invalidate cache
- **Action:** Rebuild cache from server truth (don't merge, don't guess)

**Multiple Sources Present:**
- **Rule:** If multiple sources present, server wins, URL required, cache optional
- **Action:** Use server truth, validate URL pointer matches, rebuild cache if needed

---

## 2. State Inventory Table

| Variable | Tier | Authoritative Source | Allowed Mirrors/Caches | Persistence | Failure Mode |
|----------|------|---------------------|------------------------|-------------|--------------|
| **game_id** | Pointer | URL params | `gameStore` (runtime cache), localStorage (explicit resume) | Must survive refresh, not device switch | Fail: Show "Game not found" error, redirect to lineup |
| **franchise_id** | Pointer | URL params | `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Show "Franchise not found" error, redirect to mode select |
| **tournament_id** | Pointer | URL params | `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Show "Tournament not found" error, redirect to mode select |
| **game document** | Truth | Server (DB: `games` collection, standalone for all modes) | `ongoing_games` (runtime cache), `gameStore` (runtime cache) | Must survive refresh, must survive device switch | Fail: Show "Game document not found" error, clear URL pointer |
| **game document (franchise)** | Truth | Server (DB: `games` collection with `franchise_id` field) | `ongoing_games` (runtime cache), `gameStore` (runtime cache) | Must survive refresh, must survive device switch | Fail: Show "Game document not found" error, clear URL pointer |
| **game document (tournament)** | Truth | Server (DB: `games` collection with `tournament_id` field) | `ongoing_games` (runtime cache), `gameStore` (runtime cache) | Must survive refresh, must survive device switch | Fail: Show "Game document not found" error, clear URL pointer |
| **franchise document** | Truth | Server (DB: `franchises` collection) | Client-side cache (runtime only) | Must survive refresh, must survive device switch | Fail: Show "Franchise not found" error, redirect to mode select |
| **tournament document** | Truth | Server (DB: `tournaments` collection) | Client-side cache (runtime only) | Must survive refresh, must survive device switch | Fail: Show "Tournament not found" error, redirect to mode select |
| **playbook_settings** | Truth | Server (DB: franchise master = `franchise_team_data` / FTD; tournament master = tournament doc; game-doc snapshot during active play; single = game doc) | `gameStore` (runtime cache), client UI state | Must survive refresh, must survive device switch | Fail: Load defaults, show warning if user-modified settings lost |
| **strategy_settings** | Truth | Server (DB: same two-stage sources as playbook_settings) | `gameStore` (runtime cache), client UI state | Must survive refresh, must survive device switch | Fail: Load defaults, show warning if user-modified settings lost |
| **home_team / away_team** | Truth | Server (DB: nested in game document) | URL params (for lineup screen), `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Show "Teams not found" error, redirect to team select |
| **user_team_side** | Truth | Server (DB: nested in game document) | URL params, `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Default to "home" if missing (non-critical) |
| **quarter** | Truth | Server (DB: in game document) | URL params, `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Default to 1 if missing (new game) |
| **clock / time_remaining** | Truth | Server (DB: in game document) | `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Default to 8:00 / 480s for Q1 if missing |
| **score** | Truth | Server (DB: in game document) | `gameStore` (runtime cache) | Must survive refresh, must survive device switch | Fail: Default to 0-0 if missing, log warning |
| **lineups** | Truth | Server (DB: in game document) | `gameStore` (runtime cache), URL params (for lineup screen) | Must survive refresh, not device switch | Fail: Auto-generate lineups if missing |
| **timeout state** | Truth | Server (DB: `timeout_next_play_type`, `timeout_offense_team_id` in game document) | `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Treat as normal quarter start if missing |
| **training allocations** | Truth | Server (DB: in franchise document only) | Client UI state (temporary form state) | Must survive refresh, must survive device switch | Fail: Load empty allocations, show warning |
| **training results** | Truth | Server (DB: `training_logs` collection, linked via `franchise_id` field) | Client UI state (display cache) | Must survive refresh, must survive device switch | Fail: Show "Training results not found" error |
| **player attributes (anchor)** | Truth | Server (DB: `franchise_players_data` / FPD `attributes.anchor_*`) | Client UI state (display cache) | Must survive refresh, must survive device switch | Fail: Default to base attributes if missing |
| **player attributes (regular)** | Truth | Server (DB: in game document `players[].attributes.*`, updated after each turn based on NG) | `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Recalculate from NG if missing |
| **season/week/round** | Truth | Server (DB: in franchise/tournament document) | URL params, `gameStore` (runtime cache) | Must survive refresh, must survive device switch | Fail: Default to 1 if missing (new season/tournament) |
| **player stats** | Truth | Server (DB: game document during play; franchise season/career stats in `franchise_players_data` / FPD) | `gameStore` (runtime cache) | Must survive refresh, must survive device switch | Fail: Default to empty stats if missing, log warning |
| **player energy (NG)** | Truth | Server (DB: in game document `players[].attributes.NG`) | `gameStore` (runtime cache) | Must survive refresh, not device switch | Fail: Default to 1.0 if missing, log warning |
| **turn data** | Truth | Server (DB: in game document `turns[]`, excluded for saves) | `gameStore` (runtime cache) | Runtime only, not persisted | Fail: Rebuild from server truth if missing |
| **animation state** | UI-only | Client memory | None | Not persisted | Fail: Reset animation state (non-critical) |
| **selected play** | UI-only | Client memory | None | Not persisted | Fail: Clear selection (non-critical) |
| **UI preferences** | Truth | Server (DB: user preferences document) | `localStorage` (optional convenience) | Must survive refresh, must survive device switch | Fail: Use defaults if missing (non-critical) |

**Note:** In franchise and tournament modes, game documents are stored in the standalone `games` collection (not nested) but include `franchise_id` or `tournament_id` fields for linking. URL params must include both `game_id` (for gameplay) and `franchise_id`/`tournament_id` (for mode context and settings).

---

## 3. Persistence Cadence Plan

### Persistence Boundaries

**When State Is Persisted:**

1. **User-Initiated Saves:**
   - Playbook settings save → Immediate write to DB
   - Game plan settings save → Immediate write to DB
   - Training allocations save → Immediate write to DB
   - Lineup selection save → Immediate write to DB

2. **Gameplay State Saves:**
   - Turn completion → Incremental stat updates to DB (via `update_game_stats()` after each turn)
   - Every 25 turns OR quarter completion → Full game state save to DB (including NG, attributes, stats)
   - Quarter completion → Save to DB (end of Q1, Q2, Q3, Q4, OT)
   - Timeout called → Save to DB (immediate, critical for resume)
   - Player foul out → Save to DB (immediate, critical for resume)
   - Quarter break → Save to DB (before navigating to lineup screen)

3. **Cache Refresh Points:**
   - After any DB write → Refresh in-memory cache from DB (if game in `ongoing_games`)
   - Before gameplay starts → Load from DB into cache
   - On timeout resume → Load from DB into cache
   - On foul out resume → Load from DB into cache
   - On quarter resume → Load from DB into cache

---

### Client Expectations After Mutations

**Response Format:**
- **Immediate mutations** (save settings, call timeout) → Return updated document snapshot
- **Gameplay mutations** (simulate turn, simulate quarter) → Return updated game state snapshot
- **Never return diffs** → Always return complete current state (simpler, safer)

**Why Complete Snapshots:**
- Eliminates sync complexity (no diff application logic)
- Server is source of truth (client just replaces state)
- Easier to debug (client always has complete state)
- Safer (no partial updates, no merge conflicts)

---

### Cache Invalidation Strategy

**When Cache Is Invalidated:**

1. **Automatic Invalidation:**
   - After any DB write → Invalidate cache, refresh from DB
   - On page navigation → Invalidate runtime cache (start fresh)
   - On version mismatch → Invalidate cache, refresh from DB

2. **Manual Invalidation:**
   - User action: "Refresh game state" → Force reload from DB
   - Error recovery: "Reload from server" → Force reload from DB

**Cache Lifecycle:**
- **Runtime cache** (`ongoing_games`, `gameStore`) → Destroyed on page unload
- **URL pointers** → Preserved across navigation, cleared on explicit "new game"
- **localStorage** → Only for explicit "Resume last game" feature, cleared on explicit "new game"

---

### Client-Side vs Server-Authoritative

**Must Be Server-Authoritative:**
- Game state (score, clock, quarter, timeouts, fouls)
- Player stats (points, rebounds, assists, etc.) - updated incrementally after each turn, full save every 25 turns
- Player energy (NG values) - updated after each turn, saved every 25 turns or quarter completion
- Player attributes (regular) - updated after each turn based on NG, saved every 25 turns or quarter completion
- Player attributes (anchor) - only changed in training, saved immediately after training
- Settings (playbook, game plan) - user-modified values
- Training results (linked to franchise via `franchise_id` field in `training_logs` collection)
- Season/tournament progress

**Can Be Client-Side Computed:**
- UI state (selected tab, dropdown state, animation frame)
- Display formatting (time display, score display)
- Temporary form state (unsaved lineup changes, unsaved training allocations)
- Animation state (sprite positions, tween progress)

**Hybrid (Client Computes, Server Validates):**
- Lineup validation → Client checks basic rules, server enforces limits
- Training allocation validation → Client checks totals, server enforces caps
- Settings validation → Client checks ranges, server enforces constraints

---

## 4. Implementation Plan

**⚠️ NOTE: Implementation details have been consolidated into the Unified Work Plan. See `../projects/Z-Completed/Unified_State_Persistence_Work_Plan.md` (archived) for the complete implementation history and all phases (1.1-1.3, 2, 3, 4, 5.1-5.7).**

**Summary:** All major implementation phases are complete. The system now follows the contract principles defined in this document.

---

## 5. Assumptions & Defaults

**Assumptions:**
- Single-user sessions (no real-time multiplayer state sync needed)
- Server is always authoritative (no offline mode)
- URL params are primary navigation mechanism (deep-linking supported)
- localStorage is optional convenience feature (not required for core flow)

**Defaults:**
- Missing non-critical state → Use safe defaults, log warning
- Missing critical state → Show error screen, require user action
- Version mismatch → Invalidate cache, rebuild from truth
- Multiple sources present → Server wins, URL required, cache optional

---

## 6. Success Criteria

**Contract Compliance:**
- ✅ Every state variable has exactly ONE authoritative source
- ✅ All pointers (URL params) always point to valid truth
- ✅ All caches are explicit mirrors, never hidden fallbacks
- ✅ All failures are explicit with clear recovery paths
- ✅ No silent merging or "which source wins?" ambiguity

**User Experience:**
- ✅ Deep-linking works (URL params always present)
- ✅ Refresh works (URL params persist, truth loaded from server)
- ✅ Settings persist correctly (saved to truth, loaded from truth)
- ✅ Errors are clear (user knows what went wrong, how to fix)

**Developer Experience:**
- ✅ Code is simple (one source per variable, no complex fallbacks)
- ✅ Bugs are obvious (missing state triggers explicit error)
- ✅ Debugging is easy (telemetry shows exactly what happened)

---

## 7. Answers to Open Questions

### 1. localStorage "Resume Last Game" - Best Practice

**Recommendation:** **Explicit user action** (e.g., "Resume Last Game" button on home screen)

**Rationale:**
- **SS&S Principle:** No invisible fallbacks. User should know what they're resuming.
- **User Control:** Explicit action gives user choice (maybe they want to start fresh).
- **Clear Intent:** User-initiated action is clearer than automatic behavior (what if user wants new game?).
- **Error Recovery:** If resume fails, user explicitly chose that path (easier to handle).

**Implementation:**
- Store `last_game_id` in `localStorage` when game starts (optional convenience).
- Show "Resume Last Game" button on mode select screen if `last_game_id` exists.
- User clicks button → Navigate to lineup screen with `game_id` from `localStorage`.
- If resume fails → Clear `localStorage`, show error, redirect to mode select.

---

### 2. Version Tracking - Do We Need Version Numbers?

**Recommendation:** **No version numbers needed** - Use `game_id`, `franchise_id`, `tournament_id` as document identity.

**Rationale:**
- **IDs are Immutable:** Document IDs never change (MongoDB `_id` is permanent).
- **Simple Identity:** ID lookup is simpler than version comparison logic.
- **Cache Invalidation:** We invalidate cache on navigation/DB writes (clearer than version checks).
- **SS&S Principle:** Simpler = better. Don't add complexity unless necessary.

**When to Reconsider:**
- If we need to detect concurrent edits (multi-user scenarios).
- If we need to track document evolution (audit trail).
- Currently single-user sessions, so not needed.

---

### 3. Offline Mode - Use Cases Explained

**What Offline Mode Would Enable:**
- Play game without internet connection (queue actions, sync when online).
- Continue game if connection drops temporarily (auto-resume when reconnected).
- Better mobile experience (play on plane, subway, poor connectivity areas).

**Do We Need It?**

**Recommendation:** **Not needed for MVP** - Server is always authoritative, require internet connection.

**Rationale:**
- **Complexity:** Offline mode adds significant complexity (conflict resolution, sync queues, state reconciliation).
- **SS&S Principle:** Simpler = better. Offline mode is a "nice to have", not core requirement.
- **Current State:** Gameplay requires server for turn resolution (can't be client-only).
- **Future Consideration:** If mobile becomes primary platform, revisit offline mode for better UX.

**Alternative (Simpler):**
- Show "No connection" error if server unavailable.
- Queue actions client-side, sync when connection restored (requires significant refactoring).

---

### 4. Multi-Tab Sync - Should We Support It?

**Recommendation:** **Yes, support multi-tab sync** - Low complexity, high value for users.

**Why Multi-Tab Sync:**
- Users open multiple tabs (common behavior, especially for research/reference).
- Prevents confusion (same game in multiple tabs should show same state).
- Enables "Command Center + Gameplay" workflows (view stats in one tab, play in another).

**Implementation Strategy:**
- **Server-Side:** Single source of truth (already exists - database).
- **Client-Side:** Use `BroadcastChannel` or `localStorage` events to sync `gameStore` across tabs.
- **Cache Invalidation:** When one tab updates state, broadcast to other tabs to invalidate cache.
- **Conflict Resolution:** Last write wins (server is authoritative, so this is safe).

**Complexity:** Low (Browser APIs handle cross-tab communication, server already handles concurrent writes).

---

### 5. Franchise/Tournament Game Docs - URL Params Complexity?

**Question:** In franchise and tournament mode, we use standalone game docs with `franchise_id`/`tournament_id` fields. Do we need both `game_id` AND `franchise_id`/`tournament_id` in URL params?

**Answer:** **Yes, both are needed, but this is NOT complex.**

**Why Both Are Needed:**
- **`game_id`** → Points to specific game document (required for gameplay).
- **`franchise_id` / `tournament_id`** → Points to mode context (required for navigation back to Command Center, settings persistence).

**Why This Isn't Complex:**
- **Different Purposes:** `game_id` is for gameplay, `franchise_id`/`tournament_id` is for mode context.
- **Clear Separation:** Settings live in franchise/tournament docs, game state lives in game doc.
- **SS&S Principle:** Each ID has one job, no ambiguity.

**URL Examples:**
- Single Game: `/court.html?game_id=abc123&mode=single`
- Franchise: `/court.html?game_id=abc123&franchise_id=xyz789&mode=franchise`
- Tournament: `/court.html?game_id=abc123&tournament_id=def456&mode=tournament`

**Implementation:**
- Always include all relevant IDs in URL (frontend responsibility).
- Backend validates IDs match (e.g., game doc's `franchise_id` matches URL's `franchise_id`).
- Fail loudly if mismatch (prevent corruption).

---

**Document Status:** Adopted. Implementation complete — see `../projects/Z-Completed/Unified_State_Persistence_Work_Plan.md` (archived) for phase history.

