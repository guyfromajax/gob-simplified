# `user_team_id` vs `my_team` Redundancy Audit

**Date:** 2026-01-20  
**Purpose:** Determine if `user_team_id` can be derived from `my_team` + `home`/`away` to reduce redundancy

## Current State

### URL Parameters
- `my_team`: "home" or "away" - indicates which side the user is playing
- `user_team_id`: Team identifier (team name or ObjectId) - which team the user controls
- `home`: Home team name
- `away`: Away team name
- `team_id`: Standardized team identifier (ObjectId) - preferred over `user_team_id`

## Analysis by Game Mode

### Single Game Mode
**Relationship:**
- If `my_team = "home"`, then user's team = `home` (team name)
- If `my_team = "away"`, then user's team = `away` (team name)
- Therefore: `user_team_id` should always equal `home` or `away` based on `my_team`

**Finding:** `user_team_id` is **REDUNDANT** in single game mode - can be fully derived from `my_team` + `home`/`away`

**Example:**
```
my_team=home, home=Four+Corners, away=Lancaster
→ user_team_id = "Four Corners" (derivable from my_team + home)
```

### Franchise/Tournament Mode
**Relationship:**
- `my_team`: Varies game-to-game (user might be "home" in one game, "away" in another)
- `user_team_id`: Persistent user team identity - **does NOT change** across games
- User might play different teams, but their controlled team stays the same

**Finding:** `user_team_id` is **NOT REDUNDANT** in franchise/tournament mode - it's the persistent user team identity

**Example:**
```
Game 1: my_team=home, home=Four+Corners, away=Lancaster, user_team_id=Four+Corners
Game 2: my_team=away, home=Lancaster, away=Four+Corners, user_team_id=Four+Corners
→ user_team_id stays constant even though my_team changes
```

## Code Evidence

### Single Game Mode Derivation
**`game-plan.js` lines 64-78:**
```javascript
// Determine team name and ID
// When coming from command center, use user_team_id; otherwise use lineup-based logic
let teamName = myTeamSide === 'home' ? homeTeam : awayTeam;
let teamId = myTeamSide === 'home' ? homeId : awayId;

// If coming from command center, use team_id or user_team_id parameter (Tournament/Franchise modes)
if (modeParam && (modeParam === 'tournament' || modeParam === 'franchise')) {
  // Uses user_team_id for franchise/tournament
} else {
  // Single mode: derives from my_team + home/away
}
```

**`set-lineup.js` `resolveTeam()` function:**
```javascript
if (myTeamSide === 'home' || myTeamSide === 'away') {
  teamName = myTeamSide === 'away' ? awayTeam : homeTeam;
  return !!teamName;
}
```

### Backward Compatibility Pattern
**`timeoutNavigationHelper.js` line 75:**
```javascript
// Keep user_team_id for backward compatibility (if different from team_id)
if (userTeamId && userTeamId !== teamId) params.set('user_team_id', userTeamId);
```
**Finding:** Code is already trying to deprecate `user_team_id` in favor of `team_id`

## Recommendations

### Phase 1: Single Game Mode Cleanup
**Action:** Remove `user_team_id` from single game mode URLs - derive from `my_team` + `home`/`away`

**Files to update:**
1. `set-lineup.js` - Remove `user_team_id` from navigation params for single mode
2. `game-plan.js` - Remove `user_team_id` resolution for single mode (already derives from `my_team`)
3. `playbooks.js` - Remove `user_team_id` from navigation params for single mode
4. `timeoutNavigationHelper.js` - Only include `user_team_id` for franchise/tournament mode

**Implementation:**
```javascript
// Single game mode: derive from my_team
const userTeamId = (mode === 'single') 
  ? (myTeamSide === 'home' ? home : away)
  : urlParams.get('user_team_id'); // Only for franchise/tournament
```

### Phase 2: Standardize on `team_id`
**Action:** Migrate franchise/tournament mode from `user_team_id` to `team_id` (ObjectId format)

**Current State:** `team_id` is already preferred in most places, `user_team_id` is legacy

**Migration Plan:**
- `team_id` = ObjectId (standardized, preferred)
- `user_team_id` = Legacy team name (deprecated, for backward compatibility only)

## Impact Assessment

### Benefits
1. **Reduced URL clutter** - Fewer parameters to pass around
2. **Single source of truth** - Derive from `my_team` + `home`/`away` instead of separate param
3. **Clearer semantics** - `my_team` already indicates which team user controls
4. **Consistency** - Same pattern across all single game navigation

### Risks
1. **Breaking changes** - Any code that reads `user_team_id` directly will break
2. **Navigation edge cases** - Need to verify all navigation paths derive correctly
3. **Backward compatibility** - Old bookmarks/URLs might break

### Testing Checklist
- [ ] Single game mode: Lineup screen → Game Plan (no `user_team_id` in URL)
- [ ] Single game mode: Lineup screen → Playbooks (no `user_team_id` in URL)
- [ ] Single game mode: Lineup screen → Court (no `user_team_id` in URL)
- [ ] Franchise mode: Command Center → Lineup (preserves `user_team_id` or `team_id`)
- [ ] Tournament mode: Command Center → Lineup (preserves `user_team_id` or `team_id`)
- [ ] Timeout navigation: All modes preserve correct team identification

## Conclusion

**Single Game Mode:** `user_team_id` is redundant - can be safely removed and derived from `my_team` + `home`/`away`

**Franchise/Tournament Mode:** `user_team_id` is necessary for persistent user team identity, but should migrate to `team_id` (ObjectId)

**Next Steps:** Implement Phase 1 (single game mode cleanup) to reduce redundancy without breaking franchise/tournament functionality.

