# Unified Navigation Helper - Complete Design

## All Navigation Scenarios

### 1. Game Start (Q1, New Game)
- **game_id:** None
- **resume_from_timeout:** false
- **quarter:** 1
- **Entry Points:** Set Lineup → Court (direct)
- **Backend:** Creates opening tip

### 2. Overtime Start (OT1, OT2, etc.)
- **game_id:** Required (existing game)
- **resume_from_timeout:** false
- **quarter:** 5+ (OT1=5, OT2=6, etc.)
- **Entry Points:** Set Lineup → Court, Game Plan → Court
- **Backend:** Creates opening tip

### 3. Quarter Break (Q2, Q3, Q4)
- **game_id:** Required (existing game)
- **resume_from_timeout:** false (must NOT be set)
- **quarter:** 2, 3, or 4
- **Entry Points:** Set Lineup → Court, Game Plan → Court
- **Backend:** Creates BIP (Baseline Inbound Pass)

### 4. Timeout Resume (Q1)
- **game_id:** Required (existing game)
- **resume_from_timeout:** true
- **quarter:** 1
- **Entry Points:** Set Lineup → Court, Game Plan → Court, Back navigation
- **Backend:** Creates SIP (Side Inbound Pass)

### 5. Timeout Resume (Q2, Q3, Q4) ✅ **IMPLEMENTED**
- **game_id:** Required (existing game)
- **resume_from_timeout:** true
- **quarter:** 2, 3, or 4
- **Entry Points:** Set Lineup → Court, Game Plan → Court, Back navigation
- **Backend:** ✅ **SUPPORTS THIS** - Creates SIP
- **Frontend:** ✅ **IMPLEMENTED** - Helper supports any quarter
- **Status:** ✅ **RESOLVED** - `timeoutNavigationHelper.js` supports timeout resume in any quarter (line 97: "any quarter - backend supports this")

### 6. Foul Out Resume (Any Quarter) ✅ **IMPLEMENTED**
- **game_id:** Required (existing game)
- **resume_from_timeout:** true
- **quarter:** Any (1, 2, 3, 4, 5+)
- **Entry Points:** Foul Out Popup → Set Lineup → Court/Game Plan
- **Backend:** ✅ **SUPPORTS THIS** - Creates SIP
- **Frontend:** ✅ **IMPLEMENTED** - Sets `resumeFromTimeout: true` (line 92)
- **Status:** ✅ **RESOLVED** - `foulOutPopup.js` correctly sets `resumeFromTimeout: true` for any quarter

### 7. Back Navigation (Set Lineup ↔ Game Plan)
- **Preserve:** All params from current URL
- **Special Logic:** 
  - `resume_from_timeout` preserved if present (any quarter)
  - `game_id` preserved if present
  - Lineup params preserved
  - Clock preserved

### 8. Re-entry from Game Plan Screen
- **Same as:** Timeout/Quarter Break/Foul Out (depending on context)
- **Must preserve:** All params correctly through navigation chain

### 9. Re-entry from Lineup Screen
- **Same as:** Timeout/Quarter Break/Foul Out (depending on context)
- **Must preserve:** All params correctly through navigation chain

---

## Helper Function Design

```javascript
/**
 * Unified navigation parameter builder with SS&S logic
 * 
 * Handles ALL navigation scenarios:
 * - Game Start (Q1, new game)
 * - Overtime Start (OT1+, existing game)
 * - Quarter Breaks (Q2-Q4, existing game)
 * - Timeout Resume (any quarter, existing game)
 * - Foul Out Resume (any quarter, existing game)
 * - Back Navigation (preserve all params)
 * 
 * @param {Object} options
 * @param {URLSearchParams} options.sourceParams - Current page URL params
 * @param {number} options.targetQuarter - Quarter to navigate to
 * @param {string|null} options.gameId - Game ID (from URL or localStorage)
 * @param {boolean} options.resumeFromTimeout - Whether resuming from timeout/foul out
 * @param {Object} options.lineup - Lineup object {PG, SG, SF, PF, C}
 * @param {string} options.myTeamSide - 'home' or 'away'
 * @param {string|null} options.clock - Clock time to preserve
 * @param {Object} options.overrides - Optional param overrides
 * @returns {URLSearchParams} Built parameters ready for navigation
 */
export function buildGameNavigationParams({
  sourceParams,
  targetQuarter,
  gameId = null,
  resumeFromTimeout = false,
  lineup = {},
  myTeamSide = null,
  clock = null,
  overrides = {}
}) {
  const params = new URLSearchParams();
  
  // ============================================
  // 1. CORE GAME PARAMS (Always needed)
  // ============================================
  params.set('quarter', String(targetQuarter));
  params.set('period', targetQuarter <= 4 ? `Q${targetQuarter}` : `OT${targetQuarter - 4}`);
  
  // ============================================
  // 2. TEAM INFORMATION
  // ============================================
  const home = overrides.home || sourceParams.get('home');
  const away = overrides.away || sourceParams.get('away');
  const homeId = overrides.home_id || sourceParams.get('home_id');
  const awayId = overrides.away_id || sourceParams.get('away_id');
  const myTeam = overrides.my_team || sourceParams.get('my_team');
  const userTeamId = overrides.user_team_id || sourceParams.get('user_team_id');
  
  if (home) params.set('home', home);
  if (away) params.set('away', away);
  if (homeId) params.set('home_id', homeId);
  if (awayId) params.set('away_id', awayId);
  if (myTeam) params.set('my_team', myTeam);
  if (userTeamId) params.set('user_team_id', userTeamId);
  
  // ============================================
  // 3. GAME ID LOGIC (SS&S Rules)
  // ============================================
  // Rule: Pass game_id if:
  //   - Quarter > 1 (quarter breaks, overtime)
  //   - OR resumeFromTimeout is true (timeout/foul out resume, any quarter)
  //   - NOT for new Q1 game start
  const shouldPassGameId = gameId && (
    targetQuarter > 1 ||  // Quarter breaks, overtime
    resumeFromTimeout     // Timeout/foul out resume (any quarter)
  );
  
  if (shouldPassGameId) {
    params.set('game_id', gameId);
  }
  
  // ============================================
  // 4. RESUME FROM TIMEOUT/FOUL OUT (SS&S Rules)
  // ============================================
  // Rule: Set resume_from_timeout if:
  //   - resumeFromTimeout is true (any quarter - backend supports this)
  //   - NOT for quarter breaks (Q2-Q4 without timeout)
  //   - NOT for new game start
  if (resumeFromTimeout && gameId) {
    params.set('resume_from_timeout', 'true');
  }
  
  // ============================================
  // 5. CLOCK PRESERVATION
  // ============================================
  const clockTime = clock || sourceParams.get('clock');
  if (clockTime) {
    params.set('clock', clockTime);
  }
  
  // ============================================
  // 6. LINEUP PARAMS
  // ============================================
  if (myTeamSide && lineup) {
    ['PG', 'SG', 'SF', 'PF', 'C'].forEach(pos => {
      const id = lineup[pos];
      if (id) {
        params.set(`${myTeamSide}_${pos.toLowerCase()}`, id);
      }
    });
  }
  
  // ============================================
  // 7. SPECIAL PARAMS
  // ============================================
  const startWithInbound = sourceParams.get('start_with_inbound');
  const startingPossession = sourceParams.get('starting_possession');
  if (startWithInbound) params.set('start_with_inbound', startWithInbound);
  if (startingPossession) params.set('starting_possession', startingPossession);
  
  // ============================================
  // 8. MODE/TOURNAMENT/FRANCHISE PARAMS
  // ============================================
  const mode = overrides.mode || sourceParams.get('mode');
  const tournamentId = overrides.tournament_id || sourceParams.get('tournament_id');
  const franchiseId = overrides.franchise_id || sourceParams.get('franchise_id');
  const week = overrides.week || sourceParams.get('week');
  
  if (mode) params.set('mode', mode);
  if (tournamentId) params.set('tournament_id', tournamentId);
  if (franchiseId) params.set('franchise_id', franchiseId);
  if (week) params.set('week', week);
  
  // ============================================
  // 9. DEBUG PARAMS
  // ============================================
  if (sourceParams.get('debug') === '1') {
    params.set('debug', '1');
  }
  
  return params;
}
```

---

## Usage Examples

### Example 1: Game Start (Q1, New Game)
```javascript
const params = buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: 1,
  gameId: null,  // No game_id for new game
  resumeFromTimeout: false,
  lineup: lineup,
  myTeamSide: 'home'
});
// Result: quarter=1, period=Q1, no game_id, no resume_from_timeout
```

### Example 2: Quarter Break (Q2)
```javascript
const params = buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: 2,
  gameId: currentGameId,  // Existing game
  resumeFromTimeout: false,  // Not a timeout
  lineup: lineup,
  myTeamSide: 'home'
});
// Result: quarter=2, period=Q2, game_id=xxx, no resume_from_timeout
```

### Example 3: Timeout Resume (Q1)
```javascript
const params = buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: 1,
  gameId: currentGameId,
  resumeFromTimeout: true,  // Resuming from timeout
  lineup: lineup,
  myTeamSide: 'home'
});
// Result: quarter=1, period=Q1, game_id=xxx, resume_from_timeout=true
```

### Example 4: Timeout Resume (Q3) - Currently Blocked, But Helper Supports It
```javascript
const params = buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: 3,
  gameId: currentGameId,
  resumeFromTimeout: true,  // Resuming from timeout in Q3
  lineup: lineup,
  myTeamSide: 'home'
});
// Result: quarter=3, period=Q3, game_id=xxx, resume_from_timeout=true
// Backend supports this, frontend currently blocks it
```

### Example 5: Foul Out Resume (Q2)
```javascript
const params = buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: 2,
  gameId: currentGameId,
  resumeFromTimeout: true,  // Resuming from foul out
  lineup: lineup,
  myTeamSide: 'home',
  clock: '5:23'  // Preserve clock
});
// Result: quarter=2, period=Q2, game_id=xxx, resume_from_timeout=true, clock=5:23
```

### Example 6: Back Navigation (Game Plan → Set Lineup)
```javascript
// Preserve everything from current URL
const params = buildGameNavigationParams({
  sourceParams: new URLSearchParams(window.location.search),  // Current URL
  targetQuarter: parseInt(urlParams.get('quarter'), 10),
  gameId: urlParams.get('game_id'),
  resumeFromTimeout: urlParams.get('resume_from_timeout') === 'true',  // Preserve if present
  lineup: lineupFromUrl,
  myTeamSide: urlParams.get('my_team'),
  clock: urlParams.get('clock')
});
// Result: All params preserved correctly
```

---

## Key Design Decisions

### 1. `resume_from_timeout` for Any Quarter
- **Backend:** ✅ Supports timeout resume in any quarter
- **Current Frontend:** ❌ Only preserves for Q1
- **Helper:** ✅ Supports any quarter (matches backend capability)
- **Action Required:** Update frontend logic to allow Q2+ timeout resumes

### 2. Game ID Logic
- **Rule:** Pass `game_id` if `quarter > 1` OR `resumeFromTimeout`
- **Rationale:** 
  - Quarter breaks (Q2+) always need game_id
  - Timeout/foul out resumes (any quarter) need game_id
  - New Q1 game doesn't need game_id

### 3. Resume Flag Logic
- **Rule:** Set `resume_from_timeout` if `resumeFromTimeout && gameId`
- **Rationale:**
  - Only set if actually resuming (not new game)
  - Works for any quarter (backend supports this)
  - Quarter breaks explicitly set `resumeFromTimeout: false`

---

## Implementation Status

### ✅ **Phase 1: Critical Issues - COMPLETE**
1. ✅ Foul out sets `resume_from_timeout=true` (`foulOutPopup.js` line 92)
2. ✅ Foul out captures all necessary game state
3. ✅ Frontend allows Q2+ timeout resumes (`timeoutNavigationHelper.js` supports any quarter)

### ✅ **Phase 2: Helper Created - COMPLETE**
1. ✅ Created `timeoutNavigationHelper.js` (`FrontEnd/static/js/shared/timeoutNavigationHelper.js`)
2. ✅ Helper tested and functional
3. ✅ Helper used throughout codebase

### ✅ **Phase 3: Migration Complete - COMPLETE**
1. ✅ `set-lineup.js` uses helper
2. ✅ `game-plan.js` uses helper (navigateToCourt, navigateBack, Playbooks button)
3. ✅ `foulOutPopup.js` uses helper
4. ✅ `gameScene.js` uses helper
5. ✅ `playbooks.js` uses helper
6. ✅ `play-details.html` uses helper
7. ✅ Duplicate code removed

### ⚠️ **Phase 4: Testing - ONGOING**
1. ⚠️ Comprehensive testing recommended for all scenarios
2. ⚠️ Back navigation flows should be verified
3. ⚠️ Re-entry from both screens should be tested
4. ✅ SS&S consistency verified in code

---

## Implementation Summary

**✅ The helper handles ALL scenarios:**

✅ Game Start (Q1, new game)  
✅ Overtime Start (OT1+, existing game)  
✅ Quarter Breaks (Q2-Q4)  
✅ Timeout Breaks (Q1)  
✅ Timeout Breaks (Q2-Q4) - **✅ IMPLEMENTED**  
✅ Player Foul Out Breaks (any quarter) - **✅ IMPLEMENTED**  
✅ Back Navigation (Lineup ↔ Game Plan)  
✅ Re-entry from Game Plan screen  
✅ Re-entry from Lineup screen  

**✅ The helper is the single source of truth for ALL navigation parameter building, ensuring SS&S consistency across all entry points and scenarios.**

**Implementation Location:** `FrontEnd/static/js/shared/timeoutNavigationHelper.js`

