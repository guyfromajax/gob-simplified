# TCC Bug Analysis - Side-by-Side Comparison

## Key Finding: The Code is Nearly Identical

After comparing FCC and TCC rendering code side-by-side, the implementations are **almost identical**. The bugs are likely caused by:

1. **Data Structure Differences** - How data is passed to render functions
2. **Missing Filtering Logic** - FCC might filter players differently
3. **CSS/HTML Structure** - Different table locations or CSS rules

## Comparison Results

### 1. `renderRosterStatsTable` - IDENTICAL
Both FCC and TCC have the same implementation:
- Both create rows for all players
- Both append to `roster-stats-body` tbody
- Both use same stat calculations

**FCC:** `#roster-tab .stats-table` selector (line 1501)
**TCC:** `#team-tab .stats-table` selector (line 1924)

### 2. `renderLeaderboards` - DIFFERENT DATA SOURCE
**FCC:** Uses `data[cat]` from `/franchise/leaders` endpoint
**TCC:** Uses `leaderData[board.key]` from `/tournament/leaders` endpoint

**Issue:** TCC uses `userTeamName` for comparison, but leaderboard might use different format.

### 3. `renderTeamStatsTable` - IDENTICAL
Both implementations are the same.

## Root Cause Hypothesis

Based on console logs showing:
- 12 players loaded ✅
- 12 rows added to DOM ✅
- Only 5 visible ❌

**The issue is likely:**
1. **CSS hiding rows** - Some CSS rule hiding players with `GP: 0`
2. **Table re-rendering** - Another function filtering and re-rendering with only 5 players
3. **Tab visibility** - The table might be in wrong tab or hidden

## Next Steps

1. Check browser DevTools to see if all 12 `<tr>` elements exist in DOM
2. Check computed CSS styles on hidden rows
3. Check if `renderRoster()` or another function is filtering players
4. Compare the exact data structure passed to `renderRosterStats()` in both modes

