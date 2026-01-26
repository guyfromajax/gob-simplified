# Franchise Players Bio Data Refactor

## Problem

Currently, the `/roster/{team_identifier}` endpoint (and other roster endpoints) need to query the universal `players` collection to get bio data (height, weight, jersey, year) even when loading from `franchise.players` for trained attributes.

**Current Flow:**
1. Load attributes from `franchise.players` (trained values) ✅
2. Load bio data from universal `players` collection (height, weight, jersey, year) ❌

**Why This Is Inefficient:**
- Requires two database queries (franchise document + universal players collection)
- Universal collection is only needed once during franchise initialization
- After initialization, bio data never changes, so it should be stored in `franchise.players.meta`

## Solution

Store bio data in `franchise.players[player_id].meta` during franchise initialization, then roster endpoints can load everything from the franchise document without querying the universal collection.

## Changes Needed

### 1. Franchise Initialization (`BackEnd/models/franchise_manager.py`)

**Current (lines 144-164):**
```python
meta = {
    "first_name": p.get("first_name", ""),
    "last_name": p.get("last_name", ""),
    "team": p.get("team", ""),
}
```

**Update to:**
```python
meta = {
    "first_name": p.get("first_name", ""),
    "last_name": p.get("last_name", ""),
    "team": p.get("team", ""),
    "height": p.get("height"),  # ✅ ADD
    "weight": p.get("weight"),  # ✅ ADD
    "jersey": p.get("jersey"),  # ✅ ADD
    "year": p.get("year"),      # ✅ ADD
}
```

### 2. Roster Loader (`BackEnd/utils/roster_loader.py`)

**Current (lines 36-48):** Loads bio data from universal collection as fallback

**Update to:**
- Remove universal collection query for bio data
- Get bio data directly from `franchise_player_data.get("meta", {})`
- Only query universal collection if bio data missing (backward compatibility)

### 3. Roster Endpoints

**Files to update:**
- `BackEnd/api/api.py` - `/roster/{team_identifier}` endpoint
- `BackEnd/api/franchise_routes.py` - `/franchise/roster` endpoint
- `BackEnd/api/tournament_routes.py` - `/tournament/roster` endpoint (if applicable)

**Changes:**
- Remove universal collection batch queries for bio data
- Get bio data from `franchise.players[player_id].meta` or `tournament.players[player_id].meta`

### 4. Backward Compatibility

**Migration Strategy:**
- Check if bio data exists in `meta` first
- If missing, fall back to universal collection query (for existing franchises)
- Log warning when fallback is used (so we know which franchises need migration)

**Migration Script:**
- Optional: Create script to backfill bio data into existing franchise documents
- Query universal collection once per franchise
- Update `franchise.players[player_id].meta` with bio data

## Benefits

1. **Performance:** One database query instead of two
2. **Consistency:** All player data in one place (franchise document)
3. **Simplicity:** Roster endpoints don't need universal collection access
4. **SS&S:** Single source of truth for all franchise player data

## Testing

1. Create new franchise → verify bio data stored in `meta`
2. Load roster → verify bio data comes from `franchise.players.meta`
3. Existing franchises → verify fallback to universal collection works
4. Training → verify trained attributes still load correctly

## Related Files

- `BackEnd/models/franchise_manager.py` - Franchise initialization
- `BackEnd/utils/roster_loader.py` - Roster loading logic
- `BackEnd/api/api.py` - `/roster/{team_identifier}` endpoint
- `BackEnd/api/franchise_routes.py` - `/franchise/roster` endpoint
- `docs/Data_Docs/player_data_structure.md` - Player data structure documentation

## Status

- [ ] Update franchise initialization to store bio data in `meta`
- [ ] Update roster loader to use `meta` for bio data
- [ ] Update roster endpoints to remove universal collection queries
- [ ] Add backward compatibility fallback
- [ ] Test with new franchises
- [ ] Test with existing franchises
- [ ] Update documentation

